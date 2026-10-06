"""Document parsers: PDF bytes -> field proposals for the user to confirm."""

from __future__ import annotations

from typing import Optional

from ..schemas_parse import ParseResponse
from . import ais, form16
from .common import PdfUnreadable, open_pdf

PARSERS = {"form16": form16, "ais": ais}


def parse(kind: str, data: bytes, password: Optional[str] = None) -> ParseResponse:
    doc = open_pdf(data, password)
    mod = PARSERS[kind]
    detected = (mod.looks_like_form16 if kind == "form16" else mod.looks_like_ais)(doc)
    return mod.parse(doc).response(detected)


__all__ = ["parse", "PdfUnreadable", "PARSERS"]
