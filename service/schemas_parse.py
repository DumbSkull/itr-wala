"""Response models for /parse/*.

Field keys are the private app's field namespace: `income.*` paths go into
the upstream income.json, `filer.*` paths into FilerMetadata, `source.*` into
income.source_totals. The app shows every field for confirmation; nothing
here is ever used as a final figure without the user seeing it.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel

from .schemas import Issue


class SourceRef(BaseModel):
    document: Literal["form16", "ais"]
    page: int
    text: str  # the printed line the value was read from


class Extracted(BaseModel):
    key: str
    value: Any
    label: str
    confidence: Literal["high", "medium", "low"]
    source: SourceRef


class ParseResponse(BaseModel):
    document: Literal["form16", "ais"]
    recognised: bool  # False: didn't look like this document type at all
    fields: list[Extracted]
    warnings: list[Issue]
    parser_version: str = "0.1.0"


class ParseErrorResponse(BaseModel):
    error: str
    message: str
    hint: Optional[str] = None
