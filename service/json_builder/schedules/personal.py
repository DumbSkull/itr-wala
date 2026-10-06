"""CreationInfo, Form_ITR1, PersonalInfo, FilingStatus, Verification - the
identity/administrative parts of the return. No tax arithmetic here."""

from __future__ import annotations

import os
from datetime import date

from .. import codes
from ..context import BuildContext

# SWCreatedBy / JSONCreatedBy are IDs the dept assigns to registered return-
# preparation software (pattern SW + 8 digits). We are NOT a registered
# utility vendor, so there is no legitimate value to put here. It is an env
# var so a deployment cannot accidentally ship a borrowed ID, and the builder
# flags any output carrying the placeholder as blocking.
SW_ID_PLACEHOLDER = "SW00000000"


def software_id() -> str:
    return os.environ.get("ITR_SOFTWARE_ID", SW_ID_PLACEHOLDER)


def creation_info(ctx: BuildContext, today: date) -> dict:
    sw = software_id()
    if sw == SW_ID_PLACEHOLDER:
        ctx.log.blocking(
            "SOFTWARE_ID_UNREGISTERED",
            "CreationInfo.SWCreatedBy is a placeholder - this JSON is not from a registered "
            "utility. Import it into the department's Offline Utility and re-generate the JSON "
            "there before uploading (the utility stamps its own ID).",
            "CreationInfo.SWCreatedBy")
    return {
        "SWVersionNo": "1.0",
        "SWCreatedBy": sw,
        "JSONCreatedBy": sw,
        "JSONCreationDate": today.isoformat(),
        "IntermediaryCity": "Delhi",
        "Digest": "-",
    }


def personal_info(ctx: BuildContext) -> dict:
    f = ctx.filer
    name: dict = {}
    if f.name.first_name:
        name["FirstName"] = f.name.first_name.upper()
    if f.name.middle_name:
        name["MiddleName"] = f.name.middle_name.upper()
    name["SurNameOrOrgName"] = f.name.last_name.upper()

    a = f.address
    addr: dict = {"ResidenceNo": a.residence_no}
    if a.residence_name:
        addr["ResidenceName"] = a.residence_name
    if a.road_or_street:
        addr["RoadOrStreet"] = a.road_or_street
    addr.update({
        "LocalityOrArea": a.locality_or_area,
        "CityOrTownOrDistrict": a.city_or_town_or_district,
        "StateCode": a.state_code,
        "CountryCode": codes.COUNTRY_INDIA,
        "PinCode": a.pin_code,
        "CountryCodeMobile": int(codes.COUNTRY_INDIA),
        "MobileNo": int(a.mobile_no),
        "EmailAddress": a.email,
    })

    out = {
        "AssesseeName": name,
        "PAN": f.pan,
        "Address": addr,
        "SecondaryAdd": "N",
        "DOB": f.dob.isoformat(),
        "EmployerCategory": f.employer_category,
    }
    if f.aadhaar_no:
        out["AadhaarCardNo"] = f.aadhaar_no
    else:
        ctx.log.warn("AADHAAR_MISSING",
                     "No Aadhaar number given. s.139AA requires it unless exempt; the portal "
                     "will refuse the return if PAN-Aadhaar are not linked.",
                     "filer.aadhaar_no")
    return out


def filing_status(ctx: BuildContext) -> dict:
    out = {
        "ReturnFileSec": ctx.return_sec,
        "OptOutNewTaxRegime": codes.OPT_OUT_YES if ctx.regime == "old" else codes.OPT_OUT_NO,
        "SeventhProvisio139": "N",
        "AsseseeRepFlg": "N",  # filing for oneself, not as a representative assessee
        "ItrFilingDueDate": ctx.due_date.isoformat(),
    }
    if ctx.return_sec == codes.RETURN_SEC_139_5:
        r = ctx.filer.revised
        assert r is not None  # guaranteed by the form builder
        out["ReceiptNo"] = r.original_ack_no
        out["OrigRetFiledDate"] = r.original_filing_date.isoformat()
    ctx.log.warn(
        "SEVENTH_PROVISO_ASSUMED_NO",
        "Assumed you are NOT filing only because of the 7th proviso to s.139(1) (e.g. deposits "
        "> 1 crore in a current account, foreign travel > 2 lakh, electricity bill > 1 lakh). "
        "If any of those apply, tell us.",
        "FilingStatus.SeventhProvisio139")
    return out


def verification(ctx: BuildContext) -> dict:
    f = ctx.filer
    full = " ".join(p for p in (f.name.first_name, f.name.middle_name, f.name.last_name) if p).upper()
    return {
        "Declaration": {
            "AssesseeVerName": full,
            "FatherName": f.father_name.upper(),
            "AssesseeVerPAN": f.pan,
        },
        "Capacity": codes.CAPACITY_SELF,
        "Place": f.verification_place.upper(),
    }
