"""Framework-free service logic. app.py is a thin HTTP shell over this, so
the whole contract is testable without a web server."""

from __future__ import annotations

from datetime import date
from typing import Optional

from . import engine, schema_store
from .errors import BuildError, IssueLog
from .json_builder import ay_registry
from .schemas import (BuildJsonRequest, BuildJsonResponse, ComputeRequest, ComputeResponse,
                      FormType)


class SchemaViolation(RuntimeError):
    """The builder produced JSON the dept schema rejects. That's OUR bug,
    not the user's input - surfaced as a 500 with every violation listed."""

    def __init__(self, violations: list[str]):
        self.violations = violations
        super().__init__(f"{len(violations)} schema violation(s)")


def compute(req: ComputeRequest) -> ComputeResponse:
    errors, vwarnings = engine.validate(req.income)
    log = IssueLog()
    for e in errors:
        log.error("INPUT_INVALID", e, "income")
    log.raise_if_errors()
    if not req.income.get("filing_date"):
        log.info("FILING_DATE_DEFAULTED",
                 "No filing_date: interest/late fee computed as if filing today.", "income.filing_date")
    result = engine.compute(req.income)
    return ComputeResponse(engine_version=engine.ENGINE_VERSION, ay=engine.ENGINE_AY, result=result,
                           validator_warnings=vwarnings, warnings=log.warnings)


def build_json(req: BuildJsonRequest, form: FormType, ay: str,
               today: Optional[date] = None) -> BuildJsonResponse:
    today = today or date.today()
    try:
        ay_spec = ay_registry.get(ay)
    except KeyError as e:
        raise BuildError.one("AY_UNSUPPORTED", str(e), "ay") from None
    spec = ay_spec.forms.get(form.value)
    if spec is None or spec.builder is None:
        raise BuildError.one("FORM_NOT_IMPLEMENTED",
                             f"{form.value} for AY {ay} is not implemented yet.", "form")

    loaded = schema_store.load(ay_spec.schema_dir, spec.schema_file)  # SchemaIntegrityError -> 500
    itr_json, summary, log = spec.builder(req.income, req.filer, req.regime, ay_spec, spec,
                                          loaded.version if loaded else None, today)

    validated = False
    if loaded is None:
        log.blocking("SCHEMA_NOT_VENDORED",
                     f"The department's {spec.form_name} schema for AY {ay} isn't vendored, so this "
                     "JSON was NOT checked against it. Field names and codes follow the previous "
                     "year's schema and may be wrong. Do not upload.")
    else:
        violations = schema_store.validate(loaded, itr_json)
        if violations:
            raise SchemaViolation(violations)
        validated = True

    return BuildJsonResponse(
        itr_json=itr_json, form=form, ay=ay,
        schema_version=loaded.version if loaded else None,
        schema_validated=validated, warnings=log.warnings, summary=summary)
