"""ITR-1 (Sahaj) builder for AY 2026-27.

    build(income, filer, regime, ay_spec, form_spec, schema_ver, today)
        -> (itr_json, summary, IssueLog)

Raises errors.BuildError when the input can't produce a correct ITR-1 -
including when the filer simply needs a different form. Never guesses.
"""

from __future__ import annotations

import copy
from datetime import date
from typing import Any

from .. import engine
from ..errors import BuildError, IssueLog
from ..schemas import FilerMetadata
from . import codes
from .context import BuildContext, rupees
from .schedules import income as sch_income
from .schedules import personal as sch_personal
from .schedules import tax as sch_tax

ITR1_INCOME_LIMIT = 5_000_000
ITR1_AGRI_LIMIT = 5_000


def _age_on(dob: date, on: date) -> int:
    return on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))


def _eligibility(income: dict, filer: FilerMetadata, fy_end: date, log: IssueLog) -> None:
    """Pre-computation gates. Everything here means 'ITR-1 is the wrong form'
    or 'v1 doesn't support this yet' - the message says which."""
    inc = income.get("income") or {}
    if income.get("residential_status", "resident") != "resident":
        log.error("ITR1_NOT_RESIDENT", "ITR-1 is only for residents (not RNOR/non-resident). Needs ITR-2.",
                  "income.residential_status")
    if rupees(inc.get("business_presumptive_income")):
        log.error("WRONG_FORM_ITR4", "Business/professional income can't go in ITR-1 - use ITR-4.",
                  "income.business_presumptive_income")
    cg = inc.get("capital_gains") or {}
    if rupees(cg.get("ltcg_112a")):
        log.error("LTCG_112A_UNSUPPORTED",
                  "ITR-1 allows LTCG u/s 112A up to 1,25,000, but this tool doesn't support it yet.",
                  "income.capital_gains.ltcg_112a")
    for k in ("stcg_111a", "stcg_slab", "ltcg_other", "vda"):
        if rupees(cg.get(k)):
            log.error("WRONG_FORM_ITR2", f"Capital gains ({k}) can't go in ITR-1. Needs ITR-2.",
                      f"income.capital_gains.{k}")
    if rupees((inc.get("other_sources") or {}).get("winnings")):
        log.error("WRONG_FORM_ITR2", "Lottery/online-game winnings can't go in ITR-1. Needs ITR-2.",
                  "income.other_sources.winnings")
    hp = inc.get("house_property") or []
    if isinstance(hp, list) and len(hp) > 1:
        log.error("WRONG_FORM_ITR2", "ITR-1 allows only one house property. Needs ITR-2.",
                  "income.house_property")
    if filer.exempt_agricultural_income > ITR1_AGRI_LIMIT:
        log.error("WRONG_FORM_ITR2", "Agricultural income above 5,000 rules out ITR-1. Needs ITR-2.",
                  "filer.exempt_agricultural_income")

    # Age band must agree with the date of birth: it changes old-regime slabs,
    # 80TTB and the advance-tax waiver. "Age 60 at any time during the FY".
    age = _age_on(filer.dob, fy_end)
    expected = "super_senior" if age >= 80 else "senior" if age >= 60 else "regular"
    given = income.get("age_category", "regular")
    if given != expected:
        log.error("AGE_CATEGORY_MISMATCH",
                  f"Date of birth gives age {age} on {fy_end.isoformat()} ('{expected}'), "
                  f"but income.age_category is '{given}'.", "income.age_category")
    if fy_end.month == 3 and filer.dob.month == 4 and filer.dob.day == 1:
        log.warn("AGE_BOUNDARY_BIRTHDAY",
                 "Born on 1 April: in law you attain an age the day before your birthday, so the "
                 "age band may be one higher than shown. Confirm before filing.", "filer.dob")


def _return_section(filer: FilerMetadata, filing: date, due: date, ay, regime: str, log: IssueLog) -> int:
    if filer.revised is not None:
        if filing > ay.revised_deadline:
            log.error("REVISED_DEADLINE_PASSED",
                      f"Revised returns for AY {ay.ay} must be filed by {ay.revised_deadline.isoformat()}.")
        if filer.revised.original_filing_date > filing:
            log.error("REVISED_BEFORE_ORIGINAL", "Original filing date is after this filing date.",
                      "filer.revised.original_filing_date")
        if regime == "old" and filer.revised.original_filing_date > due:
            log.error("OLD_REGIME_BELATED",
                      "The original return was belated, so the old regime can't be chosen (s.115BAC(6)).")
        return codes.RETURN_SEC_139_5
    if filing <= due:
        return codes.RETURN_SEC_139_1
    if filing <= ay.belated_deadline:
        log.warn("BELATED_RETURN",
                 f"Filing after the {due.isoformat()} due date: this is a belated return u/s 139(4). "
                 "Late fee u/s 234F and interest u/s 234A apply, and losses can't be carried forward.",
                 "income.filing_date")
        if regime == "old":
            log.error("OLD_REGIME_BELATED",
                      "The old regime can't be chosen in a belated return (s.115BAC(6)). Use the new regime.")
        return codes.RETURN_SEC_139_4
    log.error("BELATED_DEADLINE_PASSED",
              f"The last date for a belated AY {ay.ay} return was {ay.belated_deadline.isoformat()}. "
              "Only an updated return (ITR-U) is possible now - not supported.")
    return codes.RETURN_SEC_139_4


def build(income: dict, filer: FilerMetadata, regime: str, ay, form, schema_ver: str | None,
          today: date) -> tuple[dict, dict, IssueLog]:
    log = IssueLog()

    errors, vwarnings = engine.validate(income)
    for e in errors:
        log.error("INPUT_INVALID", e, "income")
    for w in vwarnings:
        log.warn("INPUT_CHECK", w, "income")

    if engine.ENGINE_AY != ay.ay:
        log.error("ENGINE_AY_MISMATCH", f"Engine computes AY {engine.ENGINE_AY}, not {ay.ay}.")

    filing_raw = income.get("filing_date")
    try:
        filing = date.fromisoformat(filing_raw) if filing_raw else None
    except (TypeError, ValueError):
        filing = None
    if filing is None:
        log.error("FILING_DATE_REQUIRED",
                  "income.filing_date (YYYY-MM-DD) is required: 234A/B/C interest and the late fee "
                  "depend on it. Use the date you'll actually upload.", "income.filing_date")
    log.raise_if_errors()  # can't go on without valid input + a filing date
    assert filing is not None
    if filing < today:
        log.warn("FILING_DATE_IN_PAST",
                 "Filing date is in the past - interest is computed only up to that date.",
                 "income.filing_date")
    log.info("INTEREST_DATE_SENSITIVE",
             f"Interest and late fee are computed for upload on {filing.isoformat()}. "
             "Upload later and they change - rebuild the JSON.")

    _eligibility(income, filer, ay.fy_end, log)
    due = form.due_date
    if income.get("due_date") and income["due_date"] != due.isoformat():
        log.warn("DUE_DATE_OVERRIDDEN",
                 f"income.due_date {income['due_date']} replaced by the ITR-1 statutory due date "
                 f"{due.isoformat()}.", "income.due_date")
    return_sec = _return_section(filer, filing, due, ay, regime, log)
    log.raise_if_errors()

    # Interest/fee date. For a revised return, 234A/234F turn on when the
    # ORIGINAL return was furnished (s.234F: "return ... under s.139(1) not
    # furnished within time"), so the engine is run as of that date. Additional
    # tax surfacing only in the revision has its own 234B nuance - flagged.
    interest_date = filing
    if filer.revised is not None:
        interest_date = filer.revised.original_filing_date
        log.warn("REVISED_INTEREST_BASIS",
                 f"Interest/late fee computed as of the original filing date "
                 f"({interest_date.isoformat()}). If this revision raises your tax, s.234B interest "
                 "on the extra amount may run further - confirm with the Offline Utility.",
                 "filer.revised")

    eng_in: dict[str, Any] = copy.deepcopy(income)
    eng_in["regime"] = regime
    eng_in["due_date"] = due.isoformat()
    eng_in["filing_date"] = interest_date.isoformat()
    result = engine.compute(eng_in)
    comp = result[regime]

    if comp["total_income"] > ITR1_INCOME_LIMIT:
        log.error("WRONG_FORM_ITR2", f"Total income {comp['total_income']:,} is above 50,00,000 - "
                  "ITR-1 not allowed. Needs ITR-2.")
        log.raise_if_errors()
    for w in comp.get("warnings", []):
        log.info("ENGINE_NOTE", w)
    for a in comp.get("interest_and_fees", {}).get("assumptions", []):
        log.info("ENGINE_ASSUMPTION", a)

    ctx = BuildContext(income=income, filer=filer, regime=regime, comp=comp, ay=ay.ay,
                       due_date=due, filing_date=filing, return_sec=return_sec, log=log)

    itr1: dict[str, Any] = {
        "CreationInfo": sch_personal.creation_info(ctx, today),
        "Form_ITR1": {
            "FormName": form.form_name,
            "Description": form.description,
            "AssessmentYear": ay.assessment_year,
            "SchemaVer": schema_ver or "Ver1.0",
            "FormVer": schema_ver or "Ver1.0",
        },
        "PersonalInfo": sch_personal.personal_info(ctx),
        "FilingStatus": sch_personal.filing_status(ctx),
        "ITR1_IncomeDeductions": sch_income.income_deductions(ctx),
    }
    tax_comp = sch_tax.tax_computation(ctx)
    itr1["ITR1_TaxComputation"] = tax_comp
    taxes_paid, refund = sch_tax.taxes_paid_and_refund(ctx, tax_comp)
    itr1["TaxPaid"] = taxes_paid
    itr1["Refund"] = refund
    for key, block in (("TDSonSalaries", sch_tax.tds_on_salaries(ctx)),
                       ("TDSonOthThanSals", sch_tax.tds_on_others(ctx)),
                       ("TaxPayments", sch_tax.tax_payments(ctx))):
        if block is not None:
            itr1[key] = block
    itr1["Verification"] = sch_personal.verification(ctx)

    log.raise_if_errors()

    summary = {
        "form": form.form_name,
        "ay": ay.ay,
        "regime": regime,
        "return_type": {11: "original (s.139(1))", 12: "belated (s.139(4))",
                        17: "revised (s.139(5))"}[return_sec],
        "gross_total_income": itr1["ITR1_IncomeDeductions"]["GrossTotIncome"],
        "deductions": itr1["ITR1_IncomeDeductions"]["DeductUndChapVIA"]["TotalChapVIADeductions"],
        "total_income": itr1["ITR1_IncomeDeductions"]["TotalIncome"],
        "tax_liability": tax_comp["NetTaxLiability"],
        "interest_and_fee": tax_comp["TotalIntrstPay"],
        "taxes_paid": taxes_paid["TaxesPaid"]["TotalTaxesPaid"],
        "balance_payable": taxes_paid["BalTaxPayable"],
        "refund": refund["RefundDue"],
        "filing_date_assumed": filing.isoformat(),
    }
    return {"ITR": {"ITR1": itr1}}, summary, log
