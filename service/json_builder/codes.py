"""Portal enumeration codes used by the ITR-1/ITR-4 JSON.

Checked against the vendored AY 2026-27 ITR-1 schema (Ver1.1);
test_schema_validation.py re-checks the enums on every run, so a schema
revision that drops a code fails the suite.

Keeping them in one module means a schema revision is a one-file diff.
"""

# PropertyDetails[].ifLetOut
HP_SELF_OCCUPIED = "S"
HP_LET_OUT = "L"

# FilingStatus.ReturnFileSec
RETURN_SEC_139_1 = 11      # original, on time
RETURN_SEC_139_4 = 12      # belated
RETURN_SEC_139_5 = 17      # revised

# ITR1_IncomeDeductions.AllwncExemptUs10.AllwncExemptUs10Dtls[].SalNatureDesc
EXEMPT_ALLOWANCE_CODES = {
    "10(5)": "Leave travel concession/assistance",
    "10(6)": "Remuneration received as an official of an embassy of a foreign state",
    "10(7)": "Allowances or perquisites paid outside India by the Government",
    "10(10)": "Death-cum-retirement gratuity",
    "10(10A)": "Commuted value of pension",
    "10(10AA)": "Earned leave encashment on retirement",
    "10(10B)(i)": "Retrenchment compensation (first proviso)",
    "10(10B)(ii)": "Retrenchment compensation (second proviso)",
    "10(10C)": "Voluntary retirement compensation",
    "10(10CC)": "Tax paid by employer on non-monetary perquisite",
    "10(13A)": "House rent allowance",
    "10(14)(i)": "Prescribed allowances for official duties",
    "10(14)(ii)": "Prescribed allowances for personal expenses",
    "OTH": "Any other",
}

# Exemptions that survive the new regime (s.115BAC withdraws 10(5), 10(13A),
# most of 10(14), 10(17), 10(32)). These are fed by income.salary.exempt_retirement;
# everything else is fed by income.salary.exempt_allowances (old regime only).
RETIREMENT_EXEMPTION_CODES = {"10(10)", "10(10A)", "10(10AA)", "10(10B)(i)", "10(10B)(ii)", "10(10C)"}

# ITR1_IncomeDeductions.OthersInc.OthersIncDtlsOthSrc[].OthSrcNatureDesc
OTHER_SOURCE_CODES = {
    "savings_interest": "SAV",   # Interest from savings account
    "fd_interest": "IFD",        # Interest from deposits (bank / PO / co-op)
    "dividends": "DIV",          # Dividend
    "family_pension": "FAP",     # Family pension
    "other": "OTH",              # Any other (needs OthSrcOthNatOfInc text)
}

# TDSonOthThanSals.TDSonOthThanSal[].TDSSection - the subset an ITR-1/ITR-4
# filer realistically has (full list in the schema's description). 192 salary
# codes (92A/92B/92C) are excluded: salary TDS goes in TDSonSalaries.
TDS_SECTION_CODES = {
    "192A": "s.192A - PF withdrawal",
    "193": "s.193 - interest on securities",
    "194": "s.194 - dividends",
    "94A": "s.194A - interest other than on securities (bank/post office FD)",
    "94C": "s.194C - payments to contractors",
    "4DA": "s.194DA - life insurance policy payout",
    "4EE": "s.194EE - NSS deposits",
    "4H": "s.194H - commission or brokerage",
    "4-IA": "s.194I(a) - rent on plant and machinery",
    "4-IB": "s.194I(b) - rent on land/building",
    "4IB": "s.194IB - rent paid by certain individuals/HUF",
    "94J-A": "s.194J(a) - fees for technical services",
    "94J-B": "s.194J(b) - professional fees / royalty",
    "94K": "s.194K - mutual fund units",
    "94O": "s.194O - e-commerce operators",
    "94R": "s.194R - business perquisites",
}

# FilingStatus.OptOutNewTaxRegime
OPT_OUT_YES = "Y"
OPT_OUT_NO = "N"

# Verification.Capacity
CAPACITY_SELF = "S"

# PersonalInfo.Address.CountryCode / CountryCodeMobile for residents
COUNTRY_INDIA = "91"
