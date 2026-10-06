"""Generate the synthetic Form 16 / AIS PDFs used by test_parsers.py.

    python -m service.tests.make_pdf_fixtures

Fictional people and numbers, laid out like the TRACES Form 16 and the
portal's AIS. Real documents may differ in spacing and wording - whenever a
real one parses badly, add an anonymised copy of its layout here as a new
fixture rather than tuning the parser blind.

Needs reportlab (dev-only; not a service dependency).
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

OUT = Path(__file__).resolve().parent / "fixtures" / "documents"


def _write(path: Path, pages: list[list[str]], password: str | None = None) -> None:
    kw = {}
    if password:
        from reportlab.lib import pdfencrypt
        kw["encrypt"] = pdfencrypt.StandardEncryption(password, canPrint=1)
    c = canvas.Canvas(str(path), pagesize=A4, **kw)
    for lines in pages:
        y = 280 * mm
        for ln in lines:
            c.setFont("Helvetica-Bold" if ln.isupper() else "Helvetica", 9)
            c.drawString(15 * mm, y, ln)
            y -= 5.2 * mm
        c.showPage()
    c.save()


FORM16_PART_A = [
    "FORM NO. 16",
    "[See rule 31(1)(a)]",
    "PART A",
    "Certificate under section 203 of the Income-tax Act, 1961 for tax deducted at source on salary",
    "Certificate No. ABCDEFG  Last updated on 10-Jun-2026",
    "Name and address of the Employer/Specified Bank",
    "EXAMPLE TECH PVT LTD",
    "4th Floor, Baner Road, Pune - 411045, Maharashtra",
    "PAN of the Deductor  TAN of the Deductor  PAN of the Employee/Specified senior citizen",
    "AAACE1234K  PNEA12345B  ABCPE1234F",
    "Assessment Year 2026-27  Period with the Employer From 01-Apr-2025 To 31-Mar-2026",
    "Summary of amount paid/credited and tax deducted at source thereon in respect of the employee",
    "Quarter(s)  Receipt Numbers  Amount paid/credited  Amount of tax deducted (Rs.)  Amount of tax deposited (Rs.)",
    "Q1  QWERTYUI  375000.00  18000.00  18000.00",
    "Q2  ASDFGHJK  375000.00  18000.00  18000.00",
    "Q3  ZXCVBNML  375000.00  18000.00  18000.00",
    "Q4  POIUYTRE  375000.00  18000.00  18000.00",
    "Total (Rs.)  1500000.00  72000.00  72000.00",
]

FORM16_PART_B = [
    "FORM NO. 16",
    "PART B",
    "Details of Salary Paid and any other income and tax deducted",
    "Whether opting out of taxation u/s 115BAC(1A)?  No",
    "1. Gross Salary",
    "(a) Salary as per provisions contained in section 17(1)  1450000.00",
    "(b) Value of perquisites under section 17(2) (as per Form No. 12BA, wherever applicable)  50000.00",
    "(c) Profits in lieu of salary under section 17(3) (as per Form No. 12BA, wherever applicable)  0.00",
    "(d) Total  1500000.00",
    "(e) Reported total amount of salary received from other employer(s)  0.00",
    "2. Less: Allowances to the extent exempt under section 10",
    "(a) Travel concession or assistance under section 10(5)  0.00",
    "(b) Death-cum-retirement gratuity under section 10(10)  0.00",
    "(c) Commuted value of pension under section 10(10A)  0.00",
    "(d) Cash equivalent of leave salary encashment under section 10(10AA)  0.00",
    "(e) House rent allowance under section 10(13A)  120000.00",
    "(f) Amount of any other exemption under section 10  0.00",
    "(h) Total amount of exemption claimed under section 10  120000.00",
    "3. Total amount of salary received from current employer [1(d)-2(h)]  1380000.00",
    "4. Less: Deductions under section 16",
    "(a) Standard deduction under section 16(ia)  75000.00",
    "(b) Entertainment allowance under section 16(ii)  0.00",
    "(c) Tax on employment under section 16(iii)  2500.00",
    "5. Total amount of deductions under section 16 [4(a)+4(b)+4(c)]  77500.00",
    "6. Income chargeable under the head \"Salaries\" [(3+1(e)-5]  1500000.00",
    "10. Deductions under Chapter VI-A  Gross Amount  Deductible Amount",
    "(a) Deduction in respect of life insurance premia, contributions to provident fund etc. under section 80C  150000.00  150000.00",
    "(d) Deduction in respect of contribution by taxpayer to pension scheme under section 80CCD(1B)  0.00  0.00",
    "(e) Deduction in respect of contribution by Employer to pension scheme under section 80CCD(2)  50000.00  50000.00",
    "(f) Deduction in respect of health insurance premia under section 80D  0.00  0.00",
]

AIS_PAGES = [[
    "ANNUAL INFORMATION STATEMENT (AIS)",
    "Financial Year 2025-26  Assessment Year 2026-27",
    "PART A - GENERAL INFORMATION",
    "Permanent Account Number (PAN): ABCPE1234F",
    "Name of the Assessee: ASHA VERMA",
    "Date of Birth: 14/05/1990",
    "Mobile Number: 9876543210",
    "E-mail Address: asha@example.com",
    "PART B1 - INFORMATION RELATING TO TAX DEDUCTED OR COLLECTED AT SOURCE",
    "SR. NO. INFORMATION CODE INFORMATION DESCRIPTION INFORMATION SOURCE COUNT AMOUNT",
    "1 TDS-192 Salary received (Section 192) EXAMPLE TECH PVT LTD (PNEA12345B) 4 15,00,000",
    "Q1(Apr-Jun) 30/06/2025 3,75,000 18,000 18,000",
    "Q2(Jul-Sep) 30/09/2025 3,75,000 18,000 18,000",
    "Q3(Oct-Dec) 31/12/2025 3,75,000 18,000 18,000",
    "Q4(Jan-Mar) 31/03/2026 3,75,000 18,000 18,000",
    "2 TDS-194A Interest other than Interest on securities (Section 194A) HDFC BANK LIMITED (MUMH01234C) 1 30,000",
    "Q4(Jan-Mar) 31/03/2026 30,000 3,000 3,000",
    "PART B2 - INFORMATION RELATING TO SPECIFIED FINANCIAL TRANSACTION (SFT)",
    "3 SFT-016(SB) Interest income - savings bank HDFC BANK LIMITED (AAACH2702H) 1 12,000",
    "4 SFT-016(TD) Interest income - time deposit HDFC BANK LIMITED (AAACH2702H) 1 30,000",
]]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _write(OUT / "form16_asha.pdf", [FORM16_PART_A, FORM16_PART_B])
    _write(OUT / "ais_asha.pdf", AIS_PAGES)
    _write(OUT / "ais_asha_protected.pdf", AIS_PAGES, password="abcpe1234f14051990")
    _write(OUT / "not_a_form16.pdf", [["BANK STATEMENT", "Opening balance 10,000.00 and lots of other text here."]])
    _write(OUT / "scanned.pdf", [[""]])
    print(f"wrote fixtures to {OUT}")


if __name__ == "__main__":
    main()
