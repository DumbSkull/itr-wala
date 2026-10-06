"""Annual Information Statement (AIS) PDF -> field proposals.

AIS rows carry an information code: TDS-<section> for tax deducted,
SFT-<n> for bank-reported interest/dividends. Each summary row is
"<sr> <code> <description> <source name> (<TAN/PAN>) <count> <amount>", and
TDS rows are followed by quarter-wise detail rows whose second-to-last
figure is the tax deducted.

Built from the portal's published AIS layout; confidence is "medium" on
every value until it has been checked against more real statements.
"""

from __future__ import annotations

import re
from datetime import datetime

from .common import PAN_RE, Collector, Doc, amounts, find_line

ROW_RE = re.compile(r"\b(TDS|TCS|SFT)-([0-9A-Z]+(?:\([0-9A-Za-z]+\))?)\b")
SOURCE_RE = re.compile(r"^(?P<name>.*?)\s*\((?P<id>[A-Z]{4}[0-9]{5}[A-Z]|[A-Z]{5}[0-9]{4}[A-Z])\)")
QUARTER_RE = re.compile(r"\bQ[1-4]\b|\b\d{2}/\d{2}/\d{4}\b")

# statutory TDS section (as AIS prints it after "TDS-") -> portal TDSSection code
TDS_SECTION_MAP = {
    "192A": "192A", "193": "193", "194": "194", "194A": "94A", "194C": "94C",
    "194DA": "4DA", "194EE": "4EE", "194H": "4H", "194I(a)": "4-IA", "194IA": "4-IA",
    "194I(b)": "4-IB", "194IB": "4IB", "194J(a)": "94J-A", "194JA": "94J-A",
    "194J(b)": "94J-B", "194JB": "94J-B", "194K": "94K", "194O": "94O", "194R": "94R",
}


def looks_like_ais(doc: Doc) -> bool:
    t = doc.text.upper()
    return "ANNUAL INFORMATION STATEMENT" in t or "(AIS)" in t


def _classify_sft(desc: str) -> str | None:
    d = desc.lower()
    if "dividend" in d:
        return "dividends"
    if "saving" in d:
        return "savings_interest"
    if "deposit" in d or "time deposit" in d or "term deposit" in d:
        return "fd_interest"
    return None


def parse(doc: Doc) -> Collector:
    c = Collector("ais")
    if not looks_like_ais(doc):
        c.warn("NOT_AIS", "This doesn't look like an Annual Information Statement (AIS).")
        return c
    _part_a(doc, c)
    _rows(doc, c)
    return c


def _value_after_label(doc: Doc, label: str):
    rx = rf"^(?:{label})\s*[:\-]\s*(?P<v>.+)$"
    hit = find_line(doc, rx)
    if not hit:
        return None
    m = re.search(rx, hit[1], re.I)
    return (m.group("v").strip(), hit[0], hit[1]) if m else None


def _part_a(doc: Doc, c: Collector) -> None:
    pan = _value_after_label(doc, r"Permanent\s+Account\s+Number\s*\(PAN\)|PAN")
    if pan:
        m = PAN_RE.search(pan[0])
        if m:
            c.add("filer.pan", m.group(0), pan[1], pan[2], label="Your PAN")
    name = _value_after_label(doc, r"Name(\s+of\s+(the\s+)?Assessee)?")
    if name and not PAN_RE.search(name[0]):
        c.add("filer.full_name", name[0][:125], name[1], name[2], confidence="medium", label="Your name")
    dob = _value_after_label(doc, r"Date\s+of\s+Birth(/Incorporation)?")
    if dob:
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d-%b-%Y", "%Y-%m-%d"):
            try:
                v = datetime.strptime(dob[0].split()[0], fmt).date().isoformat()
                c.add("filer.dob", v, dob[1], dob[2], label="Date of birth")
                break
            except ValueError:
                continue
    mob = _value_after_label(doc, r"Mobile(\s+Number)?")
    if mob:
        m = re.search(r"[6-9]\d{9}", mob[0].replace(" ", ""))
        if m:
            c.add("filer.address.mobile_no", m.group(0), mob[1], mob[2], confidence="medium", label="Mobile")
    email = _value_after_label(doc, r"E-?mail(\s+Address)?")
    if email:
        m = re.search(r"[^@\s]+@[^@\s]+\.[^@\s]+", email[0])
        if m:
            c.add("filer.address.email", m.group(0).lower(), email[1], email[2], confidence="medium", label="Email")


def _rows(doc: Doc, c: Collector) -> None:
    other_tds: list[dict] = []
    salary_tds: list[dict] = []
    sft: dict[str, int] = {}
    sft_src: dict[str, tuple[int, str]] = {}
    current = None  # the TDS row whose detail lines we are summing
    tds_total = 0
    first_page = None

    for page, line in doc.iter_lines():
        m = ROW_RE.search(line)
        if m:
            kind, code = m.group(1), m.group(2)
            rest = line[m.end():].strip()
            src = SOURCE_RE.search(rest)
            amt = amounts(rest[src.end():] if src else rest)
            amount = amt[-1] if amt else None
            current = None
            first_page = first_page or page
            if kind == "TDS":
                desc_and_name = src.group("name") if src else rest
                row = {"section": code, "tan": src.group("id") if src else None,
                       "deductor_name": _deductor_name(desc_and_name), "amount_paid": amount, "tds": 0,
                       "page": page, "line": line}
                (salary_tds if code == "192" else other_tds).append(row)
                current = row
            elif kind == "SFT":
                head = _classify_sft(rest)
                if head and amount is not None:
                    sft[head] = sft.get(head, 0) + amount
                    sft_src.setdefault(head, (page, line))
            continue
        if current is not None and QUARTER_RE.search(line):
            a = amounts(QUARTER_RE.sub(" ", line))
            if len(a) >= 3:
                current["tds"] += a[-2]
                tds_total += a[-2]

    for row in salary_tds:
        c.add("ais.salary_tds", {k: row[k] for k in ("tan", "deductor_name", "amount_paid", "tds")},
              row["page"], row["line"], confidence="medium", label="Salary TDS reported in AIS")
    out = []
    for row in other_tds:
        code = TDS_SECTION_MAP.get(row["section"])
        if code is None:
            c.warn("AIS_TDS_SECTION_UNMAPPED",
                   f"TDS under section {row['section']} isn't supported in ITR-1 yet.", "filer.other_tds")
            continue
        out.append({"tan": row["tan"], "deductor_name": row["deductor_name"], "tds_section": code,
                    "amount_paid": row["amount_paid"], "tds_deducted": row["tds"], "tds_claimed": row["tds"]})
    if out:
        c.add("filer.other_tds", out, other_tds[0]["page"], other_tds[0]["line"], confidence="medium",
              label="Tax deducted by banks and others")
    if salary_tds or other_tds:
        c.add("source.ais_total_tds", tds_total, first_page or 1, "sum of TDS detail rows",
              confidence="medium", label="Total TDS in AIS")
    for head, amt in sft.items():
        page, line = sft_src[head]
        c.add(f"income.other_sources.{head}", amt, page, line, confidence="medium",
              label={"savings_interest": "Savings account interest", "fd_interest": "Fixed deposit interest",
                     "dividends": "Dividends"}[head])
        if head in ("savings_interest", "dividends"):
            c.add(f"source.ais_{head}", amt, page, line, confidence="medium", label=f"AIS {head.replace('_', ' ')}")


def _deductor_name(text: str) -> str:
    # "Interest other than ... (Section 194A) HDFC BANK LIMITED" -> "HDFC BANK LIMITED"
    t = re.sub(r"^.*\(\s*Section\s*[0-9A-Za-z()]+\s*\)\s*", "", text).strip()
    return (t or text).strip()[:125]
