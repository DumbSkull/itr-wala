"""ITR1_IncomeDeductions: salary, one house property (PropertyDetails), other sources,
Chapter VI-A, total income.

Rule: every figure is either copied from the engine's computation or is a
line-item breakdown the filer supplied that is checked to SUM to an engine
figure. Nothing here re-derives tax law; where the portal wants a split the
engine doesn't model, the split comes from FilerMetadata and is reconciled.
"""

from __future__ import annotations

from .. import codes
from ..context import BuildContext, rupees

# Chapter VI-A keys in the ITR-1 schema (both UsrDeductUndChapVIA and
# DeductUndChapVIA). Emitted zero-filled because the schema lists them as
# required. Order mirrors the form.
CHAP_VIA_KEYS = (
    "Section80C", "Section80CCC", "Section80CCDEmployeeOrSE", "Section80CCD1B",
    "Section80CCDEmployer", "Section80D", "Section80DD", "Section80DDB", "Section80E",
    "Section80EE", "Section80EEA", "Section80EEB", "Section80G", "Section80GG",
    "Section80GGA", "Section80GGC", "Section80U", "Section80TTA", "Section80TTB",
    "AnyOthSec80CCH",
)

# engine deduction key -> schema key. 80tta_ttb splits on age below.
_ENGINE_TO_SCHEMA = {
    "80c": "Section80C",
    "80ccd_1b": "Section80CCD1B",
    "80ccd_2": "Section80CCDEmployer",
}

# Deductions the v1 builder refuses in the OLD regime because the form needs a
# supporting schedule (80D -> Schedule 80D, 80G -> Schedule 80G) or because
# the engine's single 'other' bucket cannot be split or capped correctly
# (80CCC/80CCD(1) share the s.80CCE 1.5L cap with 80C).
UNSUPPORTED_OLD_REGIME = {
    "80d": "80D needs Schedule 80D (policy/insurer details), not yet supported",
    "80g": "80G needs Schedule 80G (donee PAN/address), not yet supported",
    "other": "the engine's 'other' deduction bucket can't be mapped to a specific section",
}


def _salary(ctx: BuildContext) -> dict:
    sal_in = ctx.salary_in
    sal = ctx.heads["salary"]
    if not sal:  # no salary at all
        return {
            "GrossSalary": 0, "Salary": 0, "PerquisitesValue": 0, "ProfitsInSalary": 0,
            "NetSalary": 0, "DeductionUs16": 0, "DeductionUs16ia": 0,
            "EntertainmentAlw16ii": 0, "ProfessionalTaxUs16iii": 0, "IncomeFromSal": 0,
        }

    gross = rupees(sal["gross"])
    parts = [sal_in.get(k) for k in ("form16_17_1", "form16_17_2", "form16_17_3")]
    if all(p is None for p in parts):
        s171, s172, s173 = gross, 0, 0
        ctx.log.warn("SALARY_SPLIT_ASSUMED",
                     "Form 16 split (17(1)/17(2)/17(3)) not provided - the whole gross is "
                     "reported as salary u/s 17(1). Fill it from Form 16 Part B if you had "
                     "perquisites.", "income.salary.form16_17_1")
    else:
        s171, s172, s173 = (rupees(p) for p in parts)
        if s171 + s172 + s173 != gross:
            ctx.log.error("SALARY_SPLIT_MISMATCH",
                          f"17(1)+17(2)+17(3) = {s171 + s172 + s173:,} but gross salary is {gross:,}.",
                          "income.salary")

    # -- s.10 exemptions: reconcile filer line items to engine totals --
    eng_retire = rupees(sal["exempt_retirement"])
    eng_allow = rupees(sal["exempt_allowances"])  # 0 in the new regime
    lines = []
    sum_retire = sum_allow = 0
    for i, ea in enumerate(ctx.filer.exempt_allowances):
        field = f"filer.exempt_allowances[{i}]"
        if ea.section not in codes.EXEMPT_ALLOWANCE_CODES:
            ctx.log.error("UNKNOWN_EXEMPTION_CODE", f"Unknown s.10 code {ea.section!r}.", field)
            continue
        if ea.section == "OTH" and not ea.description:
            ctx.log.error("EXEMPTION_DESCRIPTION_REQUIRED", "'OTH' exemptions need a description.", field)
        if ea.section in codes.RETIREMENT_EXEMPTION_CODES:
            sum_retire += ea.amount
        else:
            sum_allow += ea.amount
            if ctx.regime == "new":
                continue  # withdrawn by s.115BAC; engine already ignored it
        row = {"SalNatureDesc": ea.section, "SalOthAmount": ea.amount}
        if ea.section == "OTH":
            row["SalOthNatOfInc"] = ea.description
        lines.append(row)

    raw_retire = rupees(sal_in.get("exempt_retirement"))
    raw_allow = rupees(sal_in.get("exempt_allowances"))
    if sum_retire != raw_retire:
        ctx.log.error("EXEMPTION_BREAKDOWN_MISMATCH",
                      f"Retirement exemption lines sum to {sum_retire:,} but "
                      f"income.salary.exempt_retirement is {raw_retire:,}.", "filer.exempt_allowances")
    if sum_allow != raw_allow:
        ctx.log.error("EXEMPTION_BREAKDOWN_MISMATCH",
                      f"Allowance exemption lines (HRA/LTA/...) sum to {sum_allow:,} but "
                      f"income.salary.exempt_allowances is {raw_allow:,}.", "filer.exempt_allowances")
    if raw_retire != eng_retire:
        # engine caps retirement exemptions at gross salary
        ctx.log.error("EXEMPTION_EXCEEDS_SALARY",
                      "Retirement exemptions exceed gross salary - check the Form 16 figures.",
                      "income.salary.exempt_retirement")
    if ctx.regime == "new" and raw_allow:
        ctx.log.info("NEW_REGIME_ALLOWANCES_DROPPED",
                     f"HRA/LTA-type exemptions of {raw_allow:,} are not available in the new regime "
                     "and were left out.", "filer.exempt_allowances")

    total_exempt = eng_retire + eng_allow
    net_salary = gross - total_exempt
    std = rupees(sal["standard_deduction"])
    ptax = rupees(sal["professional_tax"])
    income_from_sal = rupees(sal["net"])
    if net_salary - std - ptax != income_from_sal:
        ctx.log.error("INTERNAL_SALARY_RECONCILE",
                      f"Internal mismatch: {net_salary} - {std} - {ptax} != engine net {income_from_sal}. "
                      "Please report this.")

    out = {
        "GrossSalary": gross,
        "Salary": s171,
        "PerquisitesValue": s172,
        "ProfitsInSalary": s173,
    }
    if lines:
        out["AllwncExemptUs10"] = {"AllwncExemptUs10Dtls": lines, "TotalAllwncExemptUs10": total_exempt}
    out.update({
        "NetSalary": net_salary,
        "DeductionUs16": std + ptax,
        "DeductionUs16ia": std,
        "EntertainmentAlw16ii": 0,
        "ProfessionalTaxUs16iii": ptax,
        "IncomeFromSal": income_from_sal,
    })
    return out


def _hp_address(ctx: BuildContext, hp_meta, self_occupied: bool) -> dict:
    if hp_meta and hp_meta.address:
        a = hp_meta.address
        detail, city, state, pin = a.addr_detail, a.city_or_town_or_district, a.state_code, a.pin_code
    else:
        if not self_occupied:
            ctx.log.error("HP_ADDRESS_REQUIRED", "A let-out property needs its address.",
                          "filer.house_property.address")
        else:
            ctx.log.info("HP_ADDRESS_FROM_RESIDENCE",
                         "Self-occupied property: your residential address was used as the "
                         "property address.", "filer.house_property.address")
        r = ctx.filer.address
        detail = ", ".join(p for p in (r.residence_no, r.residence_name, r.road_or_street,
                                       r.locality_or_area) if p)[:50]
        city, state, pin = r.city_or_town_or_district, r.state_code, r.pin_code
    return {"AddrDetail": detail, "CityOrTownOrDistrict": city, "StateCode": state,
            "CountryCode": codes.COUNTRY_INDIA, "PinCode": pin}


def _section_24b(ctx: BuildContext, hp_meta, interest: int) -> dict | None:
    loans = hp_meta.home_loans if hp_meta else []
    if not interest:
        return None
    if not loans:
        ctx.log.warn("HOME_LOAN_DETAILS_MISSING",
                     f"Home-loan interest of {interest:,} is claimed but no loan details were "
                     "given. The portal asks for lender, account number, sanction date and "
                     "outstanding amount - take them from the lender's interest certificate.",
                     "filer.house_property.home_loans")
        return None
    if sum(l.interest for l in loans) != interest:
        ctx.log.error("HOME_LOAN_INTEREST_MISMATCH",
                      f"Interest on the listed loans sums to {sum(l.interest for l in loans):,} "
                      f"but income.house_property interest_paid is {interest:,}.",
                      "filer.house_property.home_loans")
    return {"Section24BDtls": [{
        "LoanTknFrom": l.lender_type,
        "BankOrInstnName": l.lender_name,
        "LoanAccNoOfBankOrInstnRefNo": l.loan_account_no,
        "DateofLoan": l.sanction_date.isoformat(),
        "TotalLoanAmt": l.total_loan_amount,
        "LoanOutstndngAmt": l.outstanding_amount,
        "InterestUs24B": l.interest,
    } for l in loans], "TotalInterestUs24B": sum(l.interest for l in loans)}


def _house_property(ctx: BuildContext) -> dict:
    props_in = ctx.income.get("income", {}).get("house_property") or []
    if isinstance(props_in, dict):
        props_in = [props_in]
    detail = ctx.heads["house_property"]["properties"]
    if not props_in:
        return {"TotalIncomeChargeableUnHP": 0}
    # Eligibility already rejected >1 property.
    p, d = props_in[0], detail[0]
    eng_income = rupees(d["income"])
    interest = rupees(p.get("interest_paid"))
    meta = ctx.filer.house_property
    self_occ = p.get("type", "self_occupied") == "self_occupied"
    if meta and meta.co_owned:
        ctx.log.error("HP_CO_OWNED_UNSUPPORTED",
                      "Co-owned property isn't supported yet (the portal needs each co-owner's "
                      "share and PAN).", "filer.house_property.co_owned")

    if self_occ:
        allowed = -eng_income  # engine: -min(interest, 2L) old / 0 new
        rent = {
            "AnnualLetableValue": 0, "RentNotRealized": 0, "LocalTaxes": 0,
            "TotalUnrealizedAndTax": 0, "BalanceALV": 0, "AnnualOfPropOwned": 0,
            "ThirtyPercentOfBalance": 0, "IntOnBorwCap": allowed,
            "TotalDeduct": allowed, "ArrearsUnrealizedRentRcvd": 0, "IncomeOfHP": eng_income,
        }
        if interest and interest > allowed and ctx.regime == "old":
            ctx.log.info("HP_INTEREST_CAPPED",
                         f"Home-loan interest of {interest:,} capped at {allowed:,} (s.24(b)).")
        loan_interest = interest if ctx.regime == "old" else 0
    else:
        gross = rupees(p.get("rent_received"))
        muni = min(rupees(p.get("municipal_taxes")), gross)
        nav = gross - muni
        std = rupees(0.30 * nav)
        line_income = nav - std - interest
        if abs(line_income - eng_income) > 1:
            ctx.log.error("INTERNAL_HP_RECONCILE",
                          f"Internal mismatch on let-out property: {line_income} vs engine {eng_income}. "
                          "Please report this.")
        if line_income < 0 and ctx.regime == "new":
            ctx.log.error("ITR1_HP_LOSS_NEW_REGIME",
                          "A let-out property loss can't be set off in the new regime and must be "
                          "carried forward - ITR-1 can't carry losses forward. This needs ITR-2.",
                          "income.house_property")
        if line_income < -200_000:
            ctx.log.error("ITR1_HP_LOSS_CARRY_FORWARD",
                          "House-property loss above 2,00,000 must be carried forward - ITR-1 can't do "
                          "that. This needs ITR-2.", "income.house_property")
        rent = {
            "AnnualLetableValue": gross, "RentNotRealized": 0, "LocalTaxes": muni,
            "TotalUnrealizedAndTax": muni, "BalanceALV": nav, "AnnualOfPropOwned": nav,
            "ThirtyPercentOfBalance": std, "IntOnBorwCap": interest,
            "TotalDeduct": std + interest, "ArrearsUnrealizedRentRcvd": 0, "IncomeOfHP": eng_income,
        }
        loan_interest = interest
        if not (meta and meta.tenants):
            ctx.log.warn("TENANT_DETAILS_MISSING",
                         "No tenant details given for the let-out property. The portal asks for "
                         "the tenant's name (and PAN if rent TDS was deducted).",
                         "filer.house_property.tenants")

    s24b = _section_24b(ctx, meta, loan_interest)
    if s24b:
        rent["Section24B"] = s24b
    prop = {
        "HPSNo": 1,
        "AddressDetailWithZipCode": _hp_address(ctx, meta, self_occ),
        "PropertyOwner": meta.owner if meta else "SE",
        "PropCoOwnedFlg": "NO",
        "ifLetOut": codes.HP_SELF_OCCUPIED if self_occ else codes.HP_LET_OUT,
    }
    if meta and meta.tenants and not self_occ:
        prop["TenantDetails"] = [
            {"TenantSNo": i + 1, "NameofTenant": t.name, **({"PANofTenant": t.pan} if t.pan else {})}
            for i, t in enumerate(meta.tenants)]
    prop["Rentdetails"] = rent
    return {
        "PropertyDetails": [prop],
        "TotalIncomeChargeableUnHP": rupees(ctx.heads["house_property"]["income"]),
    }


def _other_sources(ctx: BuildContext) -> dict:
    os_ = ctx.heads["other_sources"]
    rows = []
    for key, code in codes.OTHER_SOURCE_CODES.items():
        amt = rupees(os_.get(key))
        if not amt:
            continue
        row = {"OthSrcNatureDesc": code, "OthSrcOthAmount": amt}
        if code == "OTH":
            desc = ctx.filer.other_income_description
            if not desc:
                ctx.log.error("OTHER_INCOME_DESCRIPTION_REQUIRED",
                              "income.other_sources.other is set - say what it is.",
                              "filer.other_income_description")
            row["OthSrcOthNatOfInc"] = desc or ""
        rows.append(row)
    out = {"IncomeOthSrc": rupees(os_["total"])}
    if rows:
        out["OthersInc"] = {"OthersIncDtlsOthSrc": rows}
    out["DeductionUs57iia"] = rupees(os_.get("deduction_57iia"))
    return out


def _chapter_via(ctx: BuildContext) -> tuple[dict, dict, int]:
    d_in = ctx.income.get("deductions") or {}
    allowed_eng = ctx.comp["deductions"]
    senior = ctx.income.get("age_category", "regular") in ("senior", "super_senior")
    tta_key = "Section80TTB" if senior else "Section80TTA"

    if ctx.regime == "old":
        for k, why in UNSUPPORTED_OLD_REGIME.items():
            if rupees(d_in.get(k)):
                ctx.log.error("DEDUCTION_UNSUPPORTED", f"{k.upper()}: {why}.", f"income.deductions.{k}")
        ctx.log.warn("SECTION_80C_COMPONENTS",
                     "All 80C-family investments are reported under Section 80C. Pension-fund "
                     "(80CCC) and own NPS (80CCD(1)) amounts belong in separate boxes - not yet "
                     "supported, so don't include them.", "income.deductions.80c")

    claimed = {k: 0 for k in CHAP_VIA_KEYS}
    allowed = {k: 0 for k in CHAP_VIA_KEYS}
    for ek, sk in _ENGINE_TO_SCHEMA.items():
        if ctx.regime == "new" and ek != "80ccd_2":
            continue  # not claimable in the new regime; engine ignored it
        claimed[sk] = rupees(d_in.get(ek))
        allowed[sk] = rupees(allowed_eng.get(ek))
    if ctx.regime == "old":
        tta = rupees(allowed_eng.get("80tta_ttb"))
        claimed[tta_key] = rupees(d_in.get("80tta_ttb")) or tta  # engine auto-derives when omitted
        allowed[tta_key] = tta

    unmapped = set(allowed_eng) - set(_ENGINE_TO_SCHEMA) - {"80tta_ttb"}
    if unmapped:
        ctx.log.error("INTERNAL_DEDUCTION_UNMAPPED",
                      f"Engine allowed deductions with no ITR-1 mapping: {sorted(unmapped)}.")

    claimed["TotalChapVIADeductions"] = sum(claimed[k] for k in CHAP_VIA_KEYS)
    allowed["TotalChapVIADeductions"] = sum(allowed[k] for k in CHAP_VIA_KEYS)
    if allowed["TotalChapVIADeductions"] != rupees(ctx.comp["deductions_total"]):
        ctx.log.error("INTERNAL_DEDUCTION_RECONCILE",
                      f"Mapped deductions {allowed['TotalChapVIADeductions']} != engine "
                      f"{ctx.comp['deductions_total']}. Please report this.")
    return claimed, allowed, allowed["TotalChapVIADeductions"]


def income_deductions(ctx: BuildContext) -> dict:
    out: dict = {}
    sal = _salary(ctx)
    out.update(sal)
    hp = _house_property(ctx)
    out.update(hp)
    oth = _other_sources(ctx)
    out.update(oth)

    gti = sal["IncomeFromSal"] + hp["TotalIncomeChargeableUnHP"] + oth["IncomeOthSrc"]
    if abs(gti - ctx.comp["gross_total_income"]) >= 10:
        ctx.log.error("INTERNAL_GTI_RECONCILE",
                      f"Gross total income {gti} vs engine {ctx.comp['gross_total_income']}. "
                      "Please report this.")
    out["GrossTotIncome"] = gti
    out["GrossTotIncomeIncLTCG112A"] = gti  # 112A not supported in v1 (eligibility rejects it)

    claimed, allowed, ded_total = _chapter_via(ctx)
    out["UsrDeductUndChapVIA"] = claimed
    out["DeductUndChapVIA"] = allowed

    total_income = rupees(ctx.comp["total_income"])  # s.288A-rounded by the engine
    if abs((gti - ded_total) - total_income) >= 10:
        ctx.log.error("INTERNAL_TOTAL_INCOME_RECONCILE",
                      f"GTI {gti} - deductions {ded_total} vs engine total income {total_income}.")
    out["TotalIncome"] = total_income

    agri = ctx.filer.exempt_agricultural_income
    if agri:
        out["ExemptIncAgriOthUs10"] = {
            "ExemptIncAgriOthUs10Dtls": [{"NatureDesc": "AGRI", "OthAmount": agri}],
            "ExemptIncAgriOthUs10Total": agri,
        }
    return out
