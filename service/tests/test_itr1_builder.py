"""ITR-1 builder: golden mapping tests + rejection tests.

Golden: fixtures/itr1_cases/NN_*.input.json -> NN_*.expected.json, compared
exactly. Every expected figure has been hand-verified (docs/golden-review.md).

Rejection: inputs that must NOT produce a return, with the reason code the
private app keys its UI copy on.
"""

from __future__ import annotations

import copy
import json
import unittest
from datetime import date

from service import core
from service.errors import BuildError
from service.schemas import BuildJsonRequest, FormType
from service.tests.helpers import cases, expected_path, golden_view, run_case

CASES = cases("itr1_cases")
BASE = json.loads(CASES[0].read_text())


class GoldenITR1(unittest.TestCase):
    def test_fixtures_present(self):
        self.assertGreaterEqual(len(CASES), 7)

    def test_golden(self):
        for p in CASES:
            with self.subTest(case=p.name):
                exp = expected_path(p)
                self.assertTrue(exp.exists(), f"missing {exp.name} - run regen_golden and REVIEW it")
                got = golden_view(run_case(p))
                self.assertEqual(json.loads(exp.read_text()), json.loads(json.dumps(got)))

    def test_invariants(self):
        """Arithmetic identities that must hold in every return, independent of goldens."""
        for p in CASES:
            with self.subTest(case=p.name):
                r = run_case(p).itr_json["ITR"]["ITR1"]
                inc, tc, tp = r["ITR1_IncomeDeductions"], r["ITR1_TaxComputation"], r["TaxPaid"]
                self.assertEqual(inc["GrossSalary"], inc["Salary"] + inc["PerquisitesValue"] + inc["ProfitsInSalary"])
                self.assertEqual(inc["IncomeFromSal"], inc["NetSalary"] - inc["DeductionUs16"])
                self.assertEqual(inc["GrossTotIncome"],
                                 inc["IncomeFromSal"] + inc["TotalIncomeChargeableUnHP"] + inc["IncomeOthSrc"])
                via = inc["DeductUndChapVIA"]
                self.assertEqual(via["TotalChapVIADeductions"],
                                 sum(v for k, v in via.items() if k != "TotalChapVIADeductions"))
                self.assertLess(abs(inc["GrossTotIncome"] - via["TotalChapVIADeductions"] - inc["TotalIncome"]), 10)
                self.assertEqual(tc["TaxPayableOnRebate"], tc["TotalTaxPayable"] - tc["Rebate87A"])
                self.assertEqual(tc["TotTaxPlusIntrstPay"], tc["NetTaxLiability"] + tc["TotalIntrstPay"])
                paid = tp["TaxesPaid"]
                self.assertEqual(paid["TotalTaxesPaid"],
                                 paid["AdvanceTax"] + paid["TDS"] + paid["TCS"] + paid["SelfAssessmentTax"])
                self.assertFalse(tp["BalTaxPayable"] and r["Refund"]["RefundDue"])
                tds = r.get("TDSonSalaries", {}).get("TotalTDSonSalaries", 0) + \
                    r.get("TDSonOthThanSals", {}).get("TotalTDSonOthThanSals", 0)
                self.assertEqual(tds, paid["TDS"])

    def test_deterministic(self):
        a = golden_view(run_case(CASES[0]))
        b = golden_view(run_case(CASES[0]))
        self.assertEqual(a, b)


def _req(mutate) -> BuildJsonRequest:
    case = copy.deepcopy(BASE)
    mutate(case["request"])
    return BuildJsonRequest.model_validate(case["request"])


def _codes(mutate, regime=None) -> set[str]:
    def m(r):
        mutate(r)
        if regime:
            r["regime"] = regime
    try:
        core.build_json(_req(m), FormType.ITR1, "2026-27", date(2026, 7, 15))
    except BuildError as e:
        return {i.code for i in e.issues}
    return set()


class RejectITR1(unittest.TestCase):
    def assertRejects(self, code, mutate, regime=None):
        got = _codes(mutate, regime)
        self.assertIn(code, got, f"expected {code}, got {got or 'a successful build'}")

    def test_baseline_builds(self):
        self.assertEqual(_codes(lambda r: None), set())

    def test_capital_gains_needs_itr2(self):
        self.assertRejects("WRONG_FORM_ITR2",
                           lambda r: r["income"]["income"].update(capital_gains={"stcg_111a": 1000}))

    def test_ltcg_112a_not_yet(self):
        self.assertRejects("LTCG_112A_UNSUPPORTED",
                           lambda r: r["income"]["income"].update(capital_gains={"ltcg_112a": 50000}))

    def test_business_income_needs_itr4(self):
        self.assertRejects("WRONG_FORM_ITR4",
                           lambda r: r["income"]["income"].update(business_presumptive_income=300000))

    def test_two_house_properties(self):
        hp = [{"type": "self_occupied", "interest_paid": 0}, {"type": "let_out", "rent_received": 100000}]
        self.assertRejects("WRONG_FORM_ITR2", lambda r: r["income"]["income"].update(house_property=hp))

    def test_income_above_50_lakh(self):
        def m(r):
            s = r["income"]["income"]["salary"]
            s.update(gross=6000000, form16_17_1=5950000)
            r["income"]["source_totals"]["form16_gross_salary"] = 6000000
        self.assertRejects("WRONG_FORM_ITR2", m)

    def test_agri_above_5000(self):
        self.assertRejects("WRONG_FORM_ITR2", lambda r: r["filer"].update(exempt_agricultural_income=6000))

    def test_non_resident(self):
        # upstream validator rejects non-residents first; the builder gate is defence in depth
        self.assertRejects("INPUT_INVALID", lambda r: r["income"].update(residential_status="nri"))

    def test_filing_date_required(self):
        self.assertRejects("FILING_DATE_REQUIRED", lambda r: r["income"].pop("filing_date"))

    def test_old_regime_belated(self):
        self.assertRejects("OLD_REGIME_BELATED",
                           lambda r: r["income"].update(filing_date="2026-09-01"), regime="old")

    def test_after_belated_deadline(self):
        self.assertRejects("BELATED_DEADLINE_PASSED", lambda r: r["income"].update(filing_date="2027-01-05"))

    def test_tds_rows_must_match(self):
        self.assertRejects("TDS_MISMATCH", lambda r: r["filer"]["salary_tds"][0].update(tds=70000))

    def test_challans_must_match(self):
        ch = [{"kind": "advance", "bsr_code": "0510308", "date_deposited": "2025-12-10",
               "challan_serial": "11111", "amount": 5000}]
        self.assertRejects("CHALLAN_MISMATCH", lambda r: r["filer"].update(challans=ch))

    def test_advance_tax_outside_fy_upstream(self):
        # upstream validate_income already refuses this in the computation input
        self.assertRejects("INPUT_INVALID", lambda r: r["income"]["taxes_paid"].update(
            advance_tax=[{"date": "2026-04-10", "amount": 5000}]))

    def test_advance_challan_outside_fy(self):
        # ...and the builder refuses a challan mislabelled as advance tax
        def m(r):
            r["income"]["taxes_paid"]["self_assessment"] = [{"date": "2026-04-10", "amount": 5000}]
            r["filer"]["challans"] = [{"kind": "advance", "bsr_code": "0510308", "date_deposited": "2026-04-10",
                                       "challan_serial": "11111", "amount": 5000}]
        self.assertRejects("ADVANCE_TAX_OUTSIDE_FY", m)

    def test_age_category_must_match_dob(self):
        self.assertRejects("AGE_CATEGORY_MISMATCH", lambda r: r["filer"].update(dob="1955-01-01"))

    def test_80d_old_regime_unsupported(self):
        self.assertRejects("DEDUCTION_UNSUPPORTED",
                           lambda r: r["income"]["deductions"].update({"80d": 25000}), regime="old")

    def test_exemption_breakdown_must_match(self):
        self.assertRejects("EXEMPTION_BREAKDOWN_MISMATCH",
                           lambda r: r["filer"]["exempt_allowances"][0].update(amount=100000))

    def test_unknown_exemption_code(self):
        self.assertRejects("UNKNOWN_EXEMPTION_CODE",
                           lambda r: r["filer"]["exempt_allowances"][0].update(section="10(99)"))

    def test_upstream_validator_runs(self):
        # PAN inside the computation payload is refused by upstream validate_income
        self.assertRejects("INPUT_INVALID", lambda r: r["income"].update(pan="ABCPE1234F"))

    def test_tcs_unsupported(self):
        self.assertRejects("TCS_UNSUPPORTED", lambda r: r["income"]["taxes_paid"].update(tcs=1000))

    def test_all_errors_reported_together(self):
        def m(r):
            r["filer"]["salary_tds"][0]["tds"] = 1
            r["filer"]["exempt_allowances"][0]["amount"] = 1
        got = _codes(m)
        self.assertTrue({"TDS_MISMATCH", "EXEMPTION_BREAKDOWN_MISMATCH"} <= got, got)


class FormAndAY(unittest.TestCase):
    def test_itr4_not_implemented(self):
        with self.assertRaises(BuildError) as cm:
            core.build_json(_req(lambda r: None), FormType.ITR4, "2026-27", date(2026, 7, 15))
        self.assertEqual(cm.exception.issues[0].code, "FORM_NOT_IMPLEMENTED")

    def test_unknown_ay(self):
        with self.assertRaises(BuildError) as cm:
            core.build_json(_req(lambda r: None), FormType.ITR1, "2025-26", date(2026, 7, 15))
        self.assertEqual(cm.exception.issues[0].code, "AY_UNSUPPORTED")

    def test_pydantic_rejects_bad_metadata(self):
        from pydantic import ValidationError
        for mutate in (lambda r: r["filer"].update(pan="ABCDE1234F"),        # not an individual PAN
                       lambda r: r["filer"].update(unexpected_field=1),       # extra keys forbidden
                       lambda r: r["filer"]["bank_accounts"][0].update(use_for_refund=False)):
            with self.subTest(), self.assertRaises(ValidationError):
                _req(mutate)


if __name__ == "__main__":
    unittest.main()
