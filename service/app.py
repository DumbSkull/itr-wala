"""FastAPI shell. All behaviour lives in core.py; this file only maps HTTP.

    uvicorn service.app:app --port 8000

Status codes the private app relies on:
    200  success (always check warnings[]; severity 'blocking' = don't upload)
    422  the input needs to change - body is ErrorResponse{errors: [Issue]}
    500  our bug (schema violation / integrity) - never shown as user error
"""

from __future__ import annotations

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import core, engine
from .errors import BuildError
from .json_builder import ay_registry
from .schema_store import SchemaIntegrityError
from .schemas import (BuildJsonRequest, BuildJsonResponse, ComputeRequest, ComputeResponse,
                      ErrorResponse, FormType, Issue, Severity)

app = FastAPI(
    title="itr-wala engine service",
    version=engine.ENGINE_VERSION,
    description="Deterministic Indian income-tax computation + ITR portal JSON builder. "
                "Stateless; stores nothing.",
)


@app.exception_handler(BuildError)
async def _build_error(_: Request, exc: BuildError) -> JSONResponse:
    return JSONResponse(status_code=422, content=ErrorResponse(errors=exc.issues).model_dump(mode="json"))


@app.exception_handler(RequestValidationError)
async def _req_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    issues = [Issue(code="REQUEST_INVALID", severity=Severity.blocking, message=e.get("msg", ""),
                    field=".".join(str(p) for p in e.get("loc", ()) if p != "body"))
              for e in exc.errors()]
    return JSONResponse(status_code=422, content=ErrorResponse(errors=issues).model_dump(mode="json"))


@app.exception_handler(core.SchemaViolation)
async def _schema_violation(_: Request, exc: core.SchemaViolation) -> JSONResponse:
    return JSONResponse(status_code=500, content={"error": "SCHEMA_VIOLATION", "violations": exc.violations})


@app.exception_handler(SchemaIntegrityError)
async def _integrity(_: Request, exc: SchemaIntegrityError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"error": "SCHEMA_INTEGRITY", "detail": str(exc)})


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "engine_version": engine.ENGINE_VERSION, "engine_ay": engine.ENGINE_AY,
            "supported_ays": ay_registry.supported_ays()}


@app.post("/compute", response_model=ComputeResponse,
          responses={422: {"model": ErrorResponse}})
def compute(req: ComputeRequest) -> ComputeResponse:
    return core.compute(req)


@app.post("/build-json", response_model=BuildJsonResponse,
          responses={422: {"model": ErrorResponse}})
def build_json(req: BuildJsonRequest,
               form: FormType = Query(...),
               ay: str = Query("2026-27", pattern=r"^\d{4}-\d{2}$")) -> BuildJsonResponse:
    return core.build_json(req, form, ay)
