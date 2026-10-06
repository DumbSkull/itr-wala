"""FastAPI shell. All behaviour lives in core.py; this file only maps HTTP.

    uvicorn service.app:app --port 8000

Status codes the private app relies on:
    200  success (always check warnings[]; severity 'blocking' = don't upload)
    422  the input needs to change - body is ErrorResponse{errors: [Issue]}
    500  our bug (schema violation / integrity) - never shown as user error

/parse/* returns 200 with field proposals, or 422 ParseErrorResponse when
the file can't be read (wrong password, scanned image, not a PDF).
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import core, engine, parsers
from .errors import BuildError
from .json_builder import ay_registry
from .schema_store import SchemaIntegrityError
from .schemas_parse import ParseErrorResponse, ParseResponse

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
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


@app.exception_handler(parsers.PdfUnreadable)
async def _unreadable(_: Request, exc: parsers.PdfUnreadable) -> JSONResponse:
    return JSONResponse(status_code=422,
                        content=ParseErrorResponse(error=exc.code, message=exc.message).model_dump())


async def _read(file: UploadFile) -> bytes:
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise parsers.PdfUnreadable("FILE_TOO_LARGE", "That file is over 10 MB - Form 16 and AIS PDFs are much smaller.")
    return data


@app.post("/parse/form16", response_model=ParseResponse, responses={422: {"model": ParseErrorResponse}})
async def parse_form16(file: UploadFile = File(...), password: Optional[str] = Form(None)) -> ParseResponse:
    return parsers.parse("form16", await _read(file), password)


@app.post("/parse/ais", response_model=ParseResponse, responses={422: {"model": ParseErrorResponse}})
async def parse_ais(file: UploadFile = File(...), password: Optional[str] = Form(None)) -> ParseResponse:
    return parsers.parse("ais", await _read(file), password)
