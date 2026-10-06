"""Form 16 (TRACES Part A + Part B annexure) -> field proposals.

Part B's line items are matched by their statutory reference (e.g.
"section 17(1)", "section 10(13A)") rather than by item numbers, because
employers' payroll tools renumber items but always print the section.
"""

from __future__ import annotations

import re

from ..json_builder import codes
from .common import (PAN_RE, TAN_RE, Collector, Doc, amount_after, amounts, find_line,
                     last_amount)

# Part B s.10 lines: (regex on the section reference, portal code)
EXEMPTION_LINES = [
    (r"section\s*10\s*\(\s*5\s*\)", "10(5)"),
    (r"section\s*10\s*\(\s*10\s*\)(?!\s*\()", "10(10)"),
    (r"section\s*10\s*\(\s*10\s*A\s*\)", "10(10A)"),
    (r"section\s*10\s*\(\s*10\s*AA\s*\)", "10(10AA)"),
    (r"section\s*10\s*\(\s*13\s*A\s*\)", "10(13A)"),
]

# Chapter VI-A: (regex, income.json key, label). Deductible amount = last figure on the line.
CHAPTER_VIA_LINES = [
    (r"section\s*80\s*C(?!\s*C)(?![A-Z])", "80c", "80C (PF, PPF, LIC, ELSS ...)"),
    (r"section\s*80\s*CCD\s*\(\s*1\s*B\s*\)", "80ccd_1b", "80CCD(1B) (your own extra NPS)"),
    (r"section\s*80\s*CCD\s*\(\s*2\s*\)", "80ccd_2", "80CCD(2) (employer's NPS contribution)"),
    (r"section\s*80\s*D(?![A-Z])", "80d", "80D (health insurance)"),
]


def looks_like_form16(doc: Doc) -> bool:
    t = doc.text.upper()
    return "FORM NO. 16" in t or "FORM NO.16" in t or "FORM 16" in t


def parse(doc: Doc) -> Collector:
    c = Collector("form16")
    if not looks_like_form16(doc):
        c.warn("NOT_FORM16", "This doesn't look like a Form 16. Check you uploaded the right file.")
        return c

    _part_a(doc, c)
    _part_b(doc, c)

    if not c.has("income.salary.gross"):
        c.warn("FORM16_PART_B_MISSING",
               "Couldn't find Part B (the salary breakdown). Some employers send Part A and Part B "
               "as separate PDFs - upload Part B too, or type the figures in.")
    return c


def _part_a(doc: Doc, c: Collector) -> None:
    hit = find_line(doc, r"PAN\s+of\s+the\s+Employee")
    pans = []
    if hit:
        page = hit[0]
        lines = doc.pages[page - 1].lines
        i = lines.index(hit[1])
        for ln in lines[i:i + 3]:
            pans += PAN_RE.findall(ln)
    if not pans:
        pans = PAN_RE.findall(doc.text)
    # Part A prints the employer's PAN beside the employee's; the employee's is
    # the one whose 4th letter is P (an individual).
    emp_pans = [p for p in dict.fromkeys(pans) if p[3] == "P"]
    if emp_pans:
        c.add("filer.pan", emp_pans[-1], hit[0] if hit else 1, hit[1] if hit else "PAN of the Employee",
              confidence="high" if len(emp_pans) == 1 else "medium", label="Your PAN")

    tan = None
    hit_tan = find_line(doc, r"TAN\s+of\s+the\s+(Deductor|Employer)")
    if hit_tan:
        lines = doc.pages[hit_tan[0] - 1].lines
        i = lines.index(hit_tan[1])
        for ln in lines[i:i + 3]:
            m = TAN_RE.search(ln)
            if m:
                tan = m.group(0)
                break
    if tan is None:
        m = TAN_RE.search(doc.text)
        tan = m.group(0) if m else None

    employer = None
    hit_emp = find_line(doc, r"Name\s+and\s+address\s+of\s+the\s+Employer")
    if hit_emp:
        lines = doc.pages[hit_emp[0] - 1].lines
        i = lines.index(hit_emp[1])
        if i + 1 < len(lines):
            employer = re.split(r"\s{2,}|\|", lines[i + 1])[0].strip()[:125] or None

    # Quarterly summary "Total (Rs.)  <amount paid>  <tax deducted>  <tax deposited>"
    tds = None
    tds_line = None
    for page, line in doc.iter_lines():
        if re.match(r"^\s*Total\s*\(?\s*Rs\.?\s*\)?", line, re.I):
            a = amounts(line)
            if len(a) >= 2:
                tds, tds_line = (a[1], (page, line))
                break
    if tds is not None:
        c.add("source.form16_total_tds", tds, tds_line[0], tds_line[1], label="Tax deducted by employer (Part A total)")

    chargeable = amount_after(doc, r"Income\s+chargeable\s+under\s+the\s+head\s+.?Salaries")
    if tan or employer or tds is not None:
        row = {"tan": tan, "employer_name": employer, "tds": tds,
               "income_chargeable": chargeable[0] if chargeable else None}
        conf = "high" if tan and employer and tds is not None and chargeable else "medium"
        page = (tds_line or hit_tan or hit_emp or (1, ""))[0]
        c.add("filer.salary_tds", row, page, f"TAN {tan or '?'} / {employer or '?'}", confidence=conf,
              label="Employer and tax deducted")
        if not employer:
            c.warn("EMPLOYER_NAME_UNREAD", "Couldn't read the employer's name - please type it.",
                   "filer.salary_tds.employer_name")


def _part_b(doc: Doc, c: Collector) -> None:
    def take(pattern: str, key: str, label: str, confidence="high"):
        hit = amount_after(doc, pattern)
        if hit:
            c.add(key, hit[0], hit[1], hit[2], confidence=confidence, label=label)
        return hit[0] if hit else None

    s1 = take(r"section\s*17\s*\(\s*1\s*\)", "income.salary.form16_17_1", "Salary u/s 17(1)")
    s2 = take(r"section\s*17\s*\(\s*2\s*\)", "income.salary.form16_17_2", "Perquisites u/s 17(2)")
    s3 = take(r"section\s*17\s*\(\s*3\s*\)", "income.salary.form16_17_3", "Profits in lieu of salary u/s 17(3)")

    # 1(d) Total - the first "Total" after the 17(3) line
    gross = None
    hit3 = find_line(doc, r"section\s*17\s*\(\s*3\s*\)")
    if hit3:
        lines = doc.pages[hit3[0] - 1].lines
        i = lines.index(hit3[1])
        for ln in lines[i + 1:i + 5]:
            if re.match(r"^\(?d\)?\s*Total\b", ln, re.I) or re.match(r"^Total\b", ln, re.I):
                gross = last_amount(ln)
                if gross is not None:
                    c.add("income.salary.gross", gross, hit3[0], ln, label="Gross salary")
                    c.add("source.form16_gross_salary", gross, hit3[0], ln, label="Gross salary (Form 16 total)")
                break
    if gross is None and None not in (s1, s2, s3):
        gross = s1 + s2 + s3
        c.add("income.salary.gross", gross, hit3[0] if hit3 else 1, "17(1)+17(2)+17(3)",
              confidence="medium", label="Gross salary")
    elif gross is not None and None not in (s1, s2, s3) and s1 + s2 + s3 != gross:
        c.warn("FORM16_GROSS_MISMATCH",
               f"17(1)+17(2)+17(3) = {s1 + s2 + s3:,} but the Form 16 total says {gross:,}.",
               "income.salary.gross")

    other_employer = amount_after(doc, r"salary\s+received\s+from\s+other\s+employer")
    if other_employer and other_employer[0]:
        c.warn("OTHER_EMPLOYER_SALARY",
               f"This Form 16 includes {other_employer[0]:,} of salary from a previous employer. "
               "Upload that employer's Form 16 too so the salary isn't counted twice.")

    lines_out = []
    allow = retire = 0
    for rx, code in EXEMPTION_LINES:
        hit = amount_after(doc, rx)
        if hit and hit[0] > 0:
            lines_out.append({"section": code, "amount": hit[0]})
            if code in codes.RETIREMENT_EXEMPTION_CODES:
                retire += hit[0]
            else:
                allow += hit[0]
    total_exempt = take(r"Total\s+amount\s+of\s+exemption\s+claimed\s+under\s+section\s*10",
                        "source.form16_total_exemption", "Total s.10 exemptions", confidence="high")
    if total_exempt is not None and total_exempt > allow + retire:
        diff = total_exempt - allow - retire
        lines_out.append({"section": "OTH", "amount": diff, "description": "Other s.10 exemption per Form 16"})
        allow += diff
        c.warn("FORM16_OTHER_EXEMPTION",
               f"{diff:,} of s.10 exemptions aren't itemised (e.g. children's education allowance). "
               "Check the description.", "filer.exempt_allowances")
    hit10 = find_line(doc, r"section\s*10")
    if lines_out:
        c.add("filer.exempt_allowances", lines_out, hit10[0] if hit10 else 1, "Part B item 2 (s.10)",
              label="Exempt allowances")
    if allow:
        c.add("income.salary.exempt_allowances", allow, hit10[0] if hit10 else 1, "HRA/LTA-type exemptions",
              label="HRA, LTA and similar exemptions (old regime only)")
    if retire:
        c.add("income.salary.exempt_retirement", retire, hit10[0] if hit10 else 1,
              "gratuity/pension/leave encashment", label="Retirement exemptions")

    take(r"Tax\s+on\s+employment|section\s*16\s*\(\s*iii\s*\)", "income.salary.professional_tax",
         "Professional tax")

    hit_reg = find_line(doc, r"opt(ing|ed)?\s+out\s+of\s+taxation\s+u/?s\.?\s*115BAC")
    if hit_reg:
        val = "old" if re.search(r"\bYes\b", hit_reg[1], re.I) else "new" if re.search(r"\bNo\b", hit_reg[1], re.I) else None
        if val:
            c.add("meta.employer_regime", val, hit_reg[0], hit_reg[1], label="Regime your employer used")

    for rx, key, label in CHAPTER_VIA_LINES:
        hit = amount_after(doc, rx)
        if hit and hit[0] > 0:
            c.add(f"income.deductions.{key}", hit[0], hit[1], hit[2], confidence="medium", label=label)
