"""Portal enumeration codes used by the ITR-1/ITR-4 JSON.

EVERY value here must be confirmed against the vendored dept schema
(service/schema/AY2026-27/*.json) - the schema-conformance tests do that
automatically once the schema is present. Until then these are the codes as
used in the AY 2024-25 / 2025-26 ITR-1 schemas and are marked UNVERIFIED in
the /build-json response.

Keeping them in one module means a schema revision is a one-file diff.
"""

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

# FilingStatus.OptOutNewTaxRegime
OPT_OUT_YES = "Y"
OPT_OUT_NO = "N"

# Verification.Capacity
CAPACITY_SELF = "S"

# PersonalInfo.Address.CountryCode / CountryCodeMobile for residents
COUNTRY_INDIA = "91"
