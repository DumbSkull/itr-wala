"""Shared PDF plumbing for the document parsers.

A parser never decides a number for the return. It returns *proposals*:
each extracted value carries where it came from (page + the printed line),
and the private app shows every one to the user to confirm or correct.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Optional

import pdfplumber
from pdfminer.pdfdocument import PDFPasswordIncorrect

from ..schemas_parse import Extracted, ParseResponse, SourceRef
from ..schemas import Issue, Severity

# Pages whose text layer has fewer characters than this are treated as
# scanned images. TRACES/portal PDFs carry thousands per page.
MIN_TEXT_CHARS_PER_PAGE = 40

AMOUNT_RE = re.compile(r"(?<![\w.])-?(?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d{1,2})?(?![\w])")
PAN_RE = re.compile(r"\b[A-Z]{3}[ABCFGHLJPT][A-Z][0-9]{4}[A-Z]\b")
TAN_RE = re.compile(r"\b[A-Z]{4}[0-9]{5}[A-Z]\b")


class PdfUnreadable(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class Page:
    number: int  # 1-based
    lines: list[str]


@dataclass
class Doc:
    pages: list[Page]

    def iter_lines(self):
        for p in self.pages:
            for ln in p.lines:
                yield p.number, ln

    @property
    def text(self) -> str:
        return "\n".join(ln for p in self.pages for ln in p.lines)


def open_pdf(data: bytes, password: Optional[str] = None) -> Doc:
    try:
        pdf = pdfplumber.open(io.BytesIO(data), password=password or "")
    except Exception as exc:  # pdfplumber wraps pdfminer's errors in PdfminerException
        cause = exc.args[0] if exc.args else None
        if not (isinstance(exc, PDFPasswordIncorrect) or isinstance(cause, PDFPasswordIncorrect)):
            raise PdfUnreadable("NOT_A_PDF", f"Couldn't read this file as a PDF ({type(exc).__name__}).")
        raise PdfUnreadable(
            "PASSWORD_REQUIRED" if not password else "PASSWORD_WRONG",
            ("That password didn't open the PDF. " if password else "This PDF is password-protected. ") +
            "For AIS the password is your PAN in lowercase "
            "followed by your date of birth as DDMMYYYY (e.g. abcde1234f01011990).")
    with pdf:
        pages = []
        try:
            for i, pg in enumerate(pdf.pages, start=1):
                text = pg.extract_text(x_tolerance=1.5, y_tolerance=3) or ""
                pages.append(Page(i, [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines() if ln.strip()]))
        except Exception as exc:
            raise PdfUnreadable("NOT_A_PDF", f"Couldn't read this PDF's text ({type(exc).__name__}).")
    if not pages:
        raise PdfUnreadable("EMPTY_PDF", "This PDF has no pages.")
    if sum(len("".join(p.lines)) for p in pages) < MIN_TEXT_CHARS_PER_PAGE * len(pages):
        raise PdfUnreadable(
            "SCANNED_PDF",
            "This looks like a scan or photo. Please upload the original PDF downloaded from "
            "TRACES / your employer / the income-tax portal - those have readable text.")
    return Doc(pages)


def to_rupees(token: str) -> int:
    """'1,23,456.50' -> 123457 (whole rupees, half-up)."""
    v = float(token.replace(",", ""))
    return int(v + 0.5) if v >= 0 else -int(-v + 0.5)


def amounts(line: str) -> list[int]:
    return [to_rupees(m.group(0)) for m in AMOUNT_RE.finditer(line)]


@dataclass
class Collector:
    doc_kind: str
    fields: list[Extracted] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)

    def add(self, key: str, value, page: int, line: str, confidence: str = "high", label: str = ""):
        self.fields.append(Extracted(key=key, value=value, confidence=confidence, label=label or key,
                                     source=SourceRef(document=self.doc_kind, page=page, text=line[:200])))

    def has(self, key: str) -> bool:
        return any(f.key == key for f in self.fields)

    def warn(self, code: str, message: str, field_: Optional[str] = None, severity=Severity.review):
        self.warnings.append(Issue(code=code, severity=severity, message=message, field=field_))

    def response(self, detected: bool) -> ParseResponse:
        return ParseResponse(document=self.doc_kind, recognised=detected, fields=self.fields,
                             warnings=self.warnings)


def last_amount(line: str) -> Optional[int]:
    a = amounts(line)
    return a[-1] if a else None


def find_line(doc: Doc, pattern: str, flags=re.I):
    rx = re.compile(pattern, flags)
    for page, line in doc.iter_lines():
        if rx.search(line):
            return page, line
    return None


def amount_after(doc: Doc, pattern: str, lookahead: int = 2):
    """Amount printed on the matching line, or (wrapped label) within the
    next `lookahead` lines. Returns (value, page, line) or None."""
    rx = re.compile(pattern, re.I)
    for p in doc.pages:
        for i, line in enumerate(p.lines):
            if not rx.search(line):
                continue
            # strip the section reference itself so "17(1)" isn't read as an amount
            tail = rx.split(line, maxsplit=1)[-1]
            v = last_amount(tail)
            if v is not None:
                return v, p.number, line
            for nxt in p.lines[i + 1:i + 1 + lookahead]:
                if re.match(r"^\(?[a-z0-9]{1,3}[.)]\s", nxt, re.I):
                    break  # next numbered item - the label had no amount
                v = last_amount(nxt)
                if v is not None:
                    return v, p.number, f"{line} {nxt}"
    return None
