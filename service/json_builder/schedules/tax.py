"""ITR1_TaxComputation, TaxPaid, Refund, TDSonSalaries, TDSonOthThanSals,
TaxPayments.

Tax figures come from the engine. Payment line items (TDS rows, challans)
come from FilerMetadata and must reconcile EXACTLY to the totals the engine
computed interest on - otherwise the return claims credit the computation
never saw.
"""

from __future__ import annotations

from collections import Counter

from ..context import BuildContext, rupees


def tax_computation(ctx: BuildContext) -> dict:
    t = ctx.tax
    i = ctx.interest
    if rupees(t["surcharge"]) or rupees(t["special_tax"]):
        ctx.log.error("INTERNAL_ITR1_SURCHARGE_OR_SPECIAL",
                      "Surcharge/special-rate tax present - eligibility should have excluded this.")

    slab_tax = rupees(t["slab_tax"])
    # The portal has a single rebate box; engine splits out new-regime marginal relief.
    rebate = rupees(t["rebate_87a"]) + rupees(t["marginal_relief_87a"])
    if rupees(t["marginal_relief_87a"]):
        ctx.log.warn("REBATE_INCLUDES_MARGINAL_RELIEF",
                     f"87A rebate shown as {rebate:,} including {rupees(t['marginal_relief_87a']):,} "
                     "of marginal relief - confirm the Offline Utility shows the same.",
                     "ITR1_TaxComputation.Rebate87A")
    after_rebate = rupees(t["tax_after_rebate"])
    cess = rupees(t["cess"])
    gross_liab = after_rebate + cess
    relief_89 = rupees(t["relief_89"])
    net_liab = rupees(t["total_tax_liability"])  # s.288B-rounded by the engine
    if abs((gross_liab - relief_89) - net_liab) > 5:
        ctx.log.error("INTERNAL_TAX_RECONCILE",
                      f"Gross {gross_liab} - 89 relief {relief_89} vs engine net {net_liab}.")
    elif gross_liab - relief_89 != net_liab:
        ctx.log.warn("ROUNDING_288B",
                     f"Net tax liability rounded to {net_liab:,} (s.288B) from "
                     f"{gross_liab - relief_89:,}. Confirm the Offline Utility rounds the same way.",
                     "ITR1_TaxComputation.NetTaxLiability")

    intr = {
        "IntrstPayUs234A": rupees(i["234A"]),
        "IntrstPayUs234B": rupees(i["234B"]),
        "IntrstPayUs234C": rupees(i["234C"]),
        "LateFilingFee234F": rupees(i["234F"]),
    }
    total_intr = sum(intr.values())
    return {
        "TotalTaxPayable": slab_tax,
        "Rebate87A": rebate,
        "TaxPayableOnRebate": after_rebate,
        "EducationCess": cess,
        "GrossTaxLiability": gross_liab,
        "Section89": relief_89,
        "NetTaxLiability": net_liab,
        "TotalIntrstPay": total_intr,
        "IntrstPay": intr,
        "TotTaxPlusIntrstPay": net_liab + total_intr,
    }


def tds_on_salaries(ctx: BuildContext) -> dict | None:
    rows = ctx.filer.salary_tds
    if not rows:
        return None
    total_chargeable = sum(r.income_chargeable for r in rows)
    inc_sal = rupees(ctx.heads["salary"].get("net", 0)) if ctx.heads["salary"] else 0
    if total_chargeable != rupees(ctx.heads["salary"].get("gross", 0)) and total_chargeable != inc_sal:
        ctx.log.warn("SALARY_TDS_INCOME_MISMATCH",
                     f"Income chargeable across Form 16s ({total_chargeable:,}) matches neither gross "
                     f"salary nor computed salary income ({inc_sal:,}). Usual with a job change or "
                     "unclaimed HRA - check each Form 16 Part B.", "filer.salary_tds")
    return {
        "TDSonSalary": [{
            "EmployerOrDeductorOrCollectDetl": {"TAN": r.tan, "EmployerOrDeductorOrCollecterName": r.employer_name},
            "IncChrgSal": r.income_chargeable,
            "TotalTDSSal": r.tds,
        } for r in rows],
        "TotalTDSonSalaries": sum(r.tds for r in rows),
    }


def tds_on_others(ctx: BuildContext) -> dict | None:
    rows = ctx.filer.other_tds
    if not rows:
        return None
    return {
        "TDSonOthThanSal": [{
            "EmployerOrDeductorOrCollectDetl": {"TAN": r.tan, "EmployerOrDeductorOrCollecterName": r.deductor_name},
            "AmtForTaxDeduct": r.amount_paid,
            "DeductedYr": r.deducted_year,
            "TotTDSOnAmtPaid": r.tds_deducted,
            "ClaimOutOfTotTDSOnAmtPaid": r.tds_claimed,
        } for r in rows],
        "TotalTDSonOthThanSals": sum(r.tds_claimed for r in rows),
    }


def _reconcile_challans(ctx: BuildContext, kind: str, income_key: str) -> int:
    """Challan rows must match income.taxes_paid.<key> exactly, date for date -
    those dates drove the engine's 234B/234C."""
    ch = [(c.date_deposited.isoformat(), c.amount) for c in ctx.filer.challans if c.kind == kind]
    if kind == "advance":
        # s.211: only payments inside the FY are advance tax. The engine silently
        # reclassifies stray ones; the return must not report them as advance tax.
        fy = ctx.ay.split("-")[0]  # "2026" -> FY ends 31-Mar-2026
        late = [d for d, _ in ch if not (f"{int(fy) - 1}-04-01" <= d <= f"{fy}-03-31")]
        if late:
            ctx.log.error("ADVANCE_TAX_OUTSIDE_FY",
                          f"Advance-tax challans dated {late} fall outside the financial year - "
                          "they are self-assessment tax. Mark them so in both the income data "
                          "and the challan list.", "filer.challans")
    eng = [(str(p.get("date")), rupees(p.get("amount"))) for p in (ctx.taxes_in.get(income_key) or [])]
    if Counter(ch) != Counter(eng):
        ctx.log.error("CHALLAN_MISMATCH",
                      f"{kind.replace('_', '-')} challans {sorted(ch)} don't match the payments the tax "
                      f"was computed on {sorted(eng)} (income.taxes_paid.{income_key}).",
                      "filer.challans")
    return sum(a for _, a in ch)


def tax_payments(ctx: BuildContext) -> dict | None:
    if not ctx.filer.challans:
        return None
    rows = sorted(ctx.filer.challans, key=lambda c: c.date_deposited)
    return {
        "TaxPayment": [{
            "BSRCode": c.bsr_code,
            "DateDep": c.date_deposited.isoformat(),
            "SrlNoOfChaln": int(c.challan_serial),
            "Amt": c.amount,
        } for c in rows],
        "TotalTaxPayments": sum(c.amount for c in rows),
    }


def taxes_paid_and_refund(ctx: BuildContext, tax_comp: dict) -> tuple[dict, dict]:
    tds_rows = sum(r.tds for r in ctx.filer.salary_tds) + sum(r.tds_claimed for r in ctx.filer.other_tds)
    tds_eng = rupees(ctx.taxes_in.get("tds"))
    if tds_rows != tds_eng:
        ctx.log.error("TDS_MISMATCH",
                      f"TDS rows add up to {tds_rows:,} but the tax was computed with TDS of "
                      f"{tds_eng:,} (income.taxes_paid.tds).", "filer.salary_tds")
    if rupees(ctx.taxes_in.get("tcs")):
        ctx.log.error("TCS_UNSUPPORTED", "TCS credit needs Schedule TCS - not yet supported.",
                      "income.taxes_paid.tcs")
    adv = _reconcile_challans(ctx, "advance", "advance_tax")
    sat = _reconcile_challans(ctx, "self_assessment", "self_assessment")

    total_paid = tds_rows + adv + sat
    liability = tax_comp["TotTaxPlusIntrstPay"]
    diff = liability - total_paid
    # s.288B: payable/refund rounded to the nearest 10. Engine does the same;
    # cross-check so a drift between the two shows up.
    eng_final = ctx.interest["final_payable_or_refund"]
    bal = (1 if diff >= 0 else -1) * (int(abs(diff) / 10.0 + 0.5) * 10)
    if bal != eng_final:
        ctx.log.error("INTERNAL_BALANCE_RECONCILE",
                      f"Balance {bal} vs engine {eng_final}. Please report this.")

    taxes_paid = {
        "TaxesPaid": {
            "AdvanceTax": adv, "TDS": tds_rows, "TCS": 0,
            "SelfAssessmentTax": sat, "TotalTaxesPaid": total_paid,
        },
        "BalTaxPayable": max(bal, 0),
    }
    if bal > 0:
        ctx.log.blocking("TAX_DUE",
                         f"{bal:,} is still payable. Pay it as self-assessment tax (challan 280), add "
                         "the challan, and rebuild - a return with unpaid tax is defective u/s 139(9).",
                         "TaxPaid.BalTaxPayable")

    banks = [{
        "IFSCCode": b.ifsc,
        "BankName": b.bank_name,
        "BankAccountNo": b.account_no,
        "AccountType": b.account_type,
        "UseForRefund": "true" if b.use_for_refund else "false",
    } for b in ctx.filer.bank_accounts]
    refund = {"RefundDue": max(-bal, 0), "BankAccountDtls": {"AddtnlBankDetails": banks}}
    return taxes_paid, refund
