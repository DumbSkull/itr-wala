"""Form 16 / AIS parsers against the synthetic fixtures (make_pdf_fixtures.py),
plus the HTTP shape of /parse/*. The fixtures mirror golden case 01 (Asha
Verma), so a parse here should reproduce that case's inputs."""

from __future__ import annotations

import unittest
from pathlib import Path

from service import parsers

DOCS = Path(__file__).resolve().parent / "fixtures" / "documents"
AIS_PASSWORD = "abcpe1234f14051990"


def fields(kind: str, name: str, password: str | None = None) -> dict:
    r = parsers.parse(kind, (DOCS / name).read_bytes(), password)
    return {f.key: f.value for f in r.fields}


class Form16(unittest.TestCase):
    def test_part_a_and_b(self):
        f = fields("form16", "form16_asha.pdf")
        self.assertEqual(f["filer.pan"], "ABCPE1234F")
        self.assertEqual(f["income.salary.gross"], 1_500_000)
        self.assertEqual((f["income.salary.form16_17_1"], f["income.salary.form16_17_2"],
                          f["income.salary.form16_17_3"]), (1_450_000, 50_000, 0))
        self.assertEqual(f["income.salary.exempt_allowances"], 120_000)
        self.assertEqual(f["filer.exempt_allowances"], [{"section": "10(13A)", "amount": 120_000}])
        self.assertEqual(f["income.salary.professional_tax"], 2_500)
        self.assertEqual(f["source.form16_total_tds"], 72_000)
        self.assertEqual(f["filer.salary_tds"], {"tan": "PNEA12345B", "employer_name": "EXAMPLE TECH PVT LTD",
                                                 "tds": 72_000, "income_chargeable": 1_500_000})
        self.assertEqual(f["income.deductions.80c"], 150_000)
        self.assertEqual(f["income.deductions.80ccd_2"], 50_000)
        self.assertNotIn("income.deductions.80ccd_1b", f)  # zero lines are not proposed
        self.assertEqual(f["meta.employer_regime"], "new")

    def test_wrong_document(self):
        r = parsers.parse("form16", (DOCS / "not_a_form16.pdf").read_bytes())
        self.assertFalse(r.recognised)
        self.assertEqual([w.code for w in r.warnings], ["NOT_FORM16"])

    def test_scanned(self):
        with self.assertRaises(parsers.PdfUnreadable) as cm:
            parsers.parse("form16", (DOCS / "scanned.pdf").read_bytes())
        self.assertEqual(cm.exception.code, "SCANNED_PDF")

    def test_not_a_pdf(self):
        with self.assertRaises(parsers.PdfUnreadable) as cm:
            parsers.parse("form16", b"hello, I am a text file")
        self.assertEqual(cm.exception.code, "NOT_A_PDF")


class AIS(unittest.TestCase):
    def test_entries(self):
        f = fields("ais", "ais_asha.pdf")
        self.assertEqual(f["filer.pan"], "ABCPE1234F")
        self.assertEqual(f["filer.dob"], "1990-05-14")
        self.assertEqual(f["filer.full_name"], "ASHA VERMA")
        self.assertEqual(f["income.other_sources.savings_interest"], 12_000)
        self.assertEqual(f["income.other_sources.fd_interest"], 30_000)
        self.assertEqual(f["source.ais_total_tds"], 75_000)
        self.assertEqual(f["filer.other_tds"], [{
            "tan": "MUMH01234C", "deductor_name": "HDFC BANK LIMITED", "tds_section": "94A",
            "amount_paid": 30_000, "tds_deducted": 3_000, "tds_claimed": 3_000}])
        self.assertEqual(f["ais.salary_tds"]["tds"], 72_000)

    def test_password(self):
        with self.assertRaises(parsers.PdfUnreadable) as cm:
            parsers.parse("ais", (DOCS / "ais_asha_protected.pdf").read_bytes())
        self.assertEqual(cm.exception.code, "PASSWORD_REQUIRED")
        with self.assertRaises(parsers.PdfUnreadable) as cm:
            parsers.parse("ais", (DOCS / "ais_asha_protected.pdf").read_bytes(), "nope")
        self.assertEqual(cm.exception.code, "PASSWORD_WRONG")
        self.assertEqual(fields("ais", "ais_asha_protected.pdf", AIS_PASSWORD)["filer.pan"], "ABCPE1234F")


try:
    from fastapi.testclient import TestClient
    from service.app import app
except ImportError:  # pragma: no cover
    TestClient = None


@unittest.skipIf(TestClient is None, "fastapi not installed")
class ParseHTTP(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_form16_upload(self):
        with open(DOCS / "form16_asha.pdf", "rb") as fh:
            r = self.client.post("/parse/form16", files={"file": ("f16.pdf", fh, "application/pdf")})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["recognised"])
        gross = next(f for f in body["fields"] if f["key"] == "income.salary.gross")
        self.assertEqual(gross["source"]["document"], "form16")
        self.assertGreaterEqual(gross["source"]["page"], 1)

    def test_password_error_is_422(self):
        with open(DOCS / "ais_asha_protected.pdf", "rb") as fh:
            r = self.client.post("/parse/ais", files={"file": ("ais.pdf", fh, "application/pdf")})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["error"], "PASSWORD_REQUIRED")


if __name__ == "__main__":
    unittest.main()
