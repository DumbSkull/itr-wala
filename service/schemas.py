"""Request/response models for the engine service.

Two deliberately separate inputs:

* ``income`` - the upstream itr-wala income.json, passed through untouched and
  validated by upstream ``validate_income.check``. It never contains identity
  data (the upstream validator rejects PAN/Aadhaar-shaped strings).
* ``filer`` (FilerMetadata) - portal-only fields: name, PAN, address, bank,
  deductor/challan line items. Needed only by /build-json, so the private app
  can show the regime comparison before it has collected any of this.

These models are the source of truth for the OpenAPI spec that the private
app codegens its Zod types from - change them deliberately.
"""

from __future__ import annotations

import re
from datetime import date
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
TAN_RE = re.compile(r"^[A-Z]{4}[0-9]{5}[A-Z]$")
IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")


def _check_tan(v: str) -> str:
    v = v.upper()
    if not TAN_RE.match(v):
        raise ValueError("TAN must look like ABCD12345E")
    return v


class _Strict(BaseModel):
    # Unknown keys are an error, never silently dropped: a misspelled field
    # would otherwise vanish from the return without anyone noticing.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---------------------------------------------------------------------------
# Warnings / errors (shared by /compute and /build-json)
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    info = "info"          # FYI, nothing to do
    review = "review"      # user must look at this before uploading
    blocking = "blocking"  # the JSON must NOT be uploaded until resolved


class Issue(BaseModel):
    code: str
    severity: Severity
    message: str
    field: Optional[str] = None


class ErrorResponse(BaseModel):
    """422 body: 'we need different information', never a silent default."""
    errors: list[Issue]


# ---------------------------------------------------------------------------
# /compute
# ---------------------------------------------------------------------------

class ComputeRequest(_Strict):
    income: dict[str, Any] = Field(
        description="Upstream itr-wala income.json (see skills/itr-wala/references/input-schema.md).")


class ComputeResponse(BaseModel):
    engine_version: str
    ay: str
    result: dict[str, Any] = Field(description="Upstream tax_engine.compute() output, verbatim.")
    validator_warnings: list[str]
    warnings: list[Issue]


# ---------------------------------------------------------------------------
# /build-json - filer metadata
# ---------------------------------------------------------------------------

class FormType(str, Enum):
    ITR1 = "ITR1"
    ITR4 = "ITR4"


class Name(_Strict):
    first_name: Optional[str] = Field(None, max_length=25)
    middle_name: Optional[str] = Field(None, max_length=25)
    last_name: str = Field(min_length=1, max_length=75,
                           description="Surname exactly as on PAN. Single-name PANs put it here.")


class Address(_Strict):
    residence_no: str = Field(min_length=1, max_length=50)
    residence_name: Optional[str] = Field(None, max_length=50)
    road_or_street: Optional[str] = Field(None, max_length=50)
    locality_or_area: str = Field(min_length=1, max_length=50)
    city_or_town_or_district: str = Field(min_length=1, max_length=50)
    state_code: str = Field(pattern=r"^[0-9]{2}$", description="Portal 2-digit state code, e.g. '27' Maharashtra.")
    pin_code: int = Field(ge=110000, le=999999)
    mobile_no: str = Field(pattern=r"^[6-9][0-9]{9}$")
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=125)


class BankAccount(_Strict):
    ifsc: str
    bank_name: str = Field(min_length=1, max_length=125)
    account_no: str = Field(pattern=r"^[0-9A-Za-z]{1,20}$")
    account_type: Literal["SB", "CA", "CC", "OD", "NRO", "OTH"] = "SB"
    use_for_refund: bool = False

    @field_validator("ifsc")
    @classmethod
    def _ifsc(cls, v: str) -> str:
        v = v.upper()
        if not IFSC_RE.match(v):
            raise ValueError("IFSC must look like ABCD0123456")
        return v


class SalaryTDS(_Strict):
    """One row of TDS u/s 192 - from each employer's Form 16 Part A."""
    tan: str
    employer_name: str = Field(min_length=1, max_length=125)
    income_chargeable: int = Field(ge=0, description="Income chargeable under 'Salaries' for this employer.")
    tds: int = Field(ge=0)

    @field_validator("tan")
    @classmethod
    def _tan(cls, v: str) -> str:
        return _check_tan(v)


class OtherTDS(_Strict):
    """TDS other than salary (bank FD interest u/s 194A etc.) - from Form 16A / 26AS."""
    tan: str
    deductor_name: str = Field(min_length=1, max_length=125)
    amount_paid: int = Field(ge=0, description="Gross amount on which tax was deducted.")
    tds_deducted: int = Field(ge=0)
    tds_claimed: int = Field(ge=0, description="Portion claimed this year (usually == tds_deducted).")
    deducted_year: int = Field(2025, ge=2010, le=2026)

    @field_validator("tan")
    @classmethod
    def _tan(cls, v: str) -> str:
        return _check_tan(v)

    @model_validator(mode="after")
    def _claim_le_deducted(self) -> "OtherTDS":
        if self.tds_claimed > self.tds_deducted:
            raise ValueError("tds_claimed cannot exceed tds_deducted")
        return self


class Challan(_Strict):
    """A tax payment (advance or self-assessment) - from the challan receipt."""
    kind: Literal["advance", "self_assessment"]
    bsr_code: str = Field(pattern=r"^[0-9]{7}$")
    date_deposited: date
    challan_serial: str = Field(pattern=r"^[0-9]{5}$")
    amount: int = Field(gt=0)


class ExemptAllowance(_Strict):
    """One s.10 exemption line from Form 16 Part B (HRA, LTA, gratuity ...)."""
    section: str = Field(description="Portal nature code, e.g. '10(13A)'. See json_builder/codes.py.")
    amount: int = Field(gt=0)
    description: Optional[str] = Field(None, max_length=125, description="Required when section is 'OTH'.")


class RevisedReturn(_Strict):
    original_ack_no: str = Field(pattern=r"^[0-9]{15}$", description="Acknowledgement number of the original return.")
    original_filing_date: date


class FilerMetadata(_Strict):
    pan: str
    aadhaar_no: Optional[str] = Field(None, pattern=r"^[0-9]{12}$")
    name: Name
    father_name: str = Field(min_length=1, max_length=125, description="For the verification declaration.")
    dob: date
    address: Address
    employer_category: Literal["CGOV", "SGOV", "PSU", "PE", "PESG", "PEPS", "PEO", "OTH", "NA"]
    bank_accounts: list[BankAccount] = Field(min_length=1)
    salary_tds: list[SalaryTDS] = Field(default_factory=list)
    other_tds: list[OtherTDS] = Field(default_factory=list)
    challans: list[Challan] = Field(default_factory=list)
    exempt_allowances: list[ExemptAllowance] = Field(
        default_factory=list,
        description="Line-item breakdown of income.salary.exempt_allowances + exempt_retirement. "
                    "Must sum to those totals.")
    other_income_description: Optional[str] = Field(
        None, max_length=125,
        description="What income.other_sources.other is (e.g. 'interest on bonds'). Required if that field > 0.")
    exempt_agricultural_income: int = Field(0, ge=0)
    revised: Optional[RevisedReturn] = None
    verification_place: str = Field(min_length=1, max_length=75)

    @field_validator("pan")
    @classmethod
    def _pan(cls, v: str) -> str:
        v = v.upper()
        if not PAN_RE.match(v):
            raise ValueError("PAN must look like ABCDE1234F")
        if v[3] != "P":
            raise ValueError("4th PAN character must be 'P' (individual) for ITR-1/ITR-4 filers")
        return v

    @model_validator(mode="after")
    def _one_refund_account(self) -> "FilerMetadata":
        n = sum(1 for b in self.bank_accounts if b.use_for_refund)
        if n != 1:
            raise ValueError("exactly one bank account must have use_for_refund=true")
        return self


class BuildJsonRequest(_Strict):
    income: dict[str, Any]
    filer: FilerMetadata
    regime: Literal["new", "old"] = Field(description="The regime the user CONFIRMED after seeing /compute.")


class BuildJsonResponse(BaseModel):
    itr_json: dict[str, Any]
    form: FormType
    ay: str
    schema_version: Optional[str] = Field(description="SchemaVer of the vendored schema, or null if not vendored.")
    schema_validated: bool = Field(description="False means the JSON was NOT checked against the dept schema.")
    warnings: list[Issue]
    summary: dict[str, Any] = Field(description="Headline figures for the 'what you're about to upload' screen.")
