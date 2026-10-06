"""HTTP contract tests (FastAPI TestClient). Skipped where FastAPI isn't
installed; CI installs it, so the contract is always exercised there."""

from __future__ import annotations

import json
import unittest

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover
    TestClient = None

from service.tests.helpers import cases


@unittest.skipIf(TestClient is None, "fastapi not installed")
class API(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from service.app import app
        cls.client = TestClient(app)
        cls.case = json.loads(cases("itr1_cases")[0].read_text())

    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["engine_ay"], "2026-27")

    def test_compute_both_regimes(self):
        r = self.client.post("/compute", json={"income": self.case["request"]["income"]})
        self.assertEqual(r.status_code, 200, r.text)
        res = r.json()["result"]
        self.assertIn("new", res)
        self.assertIn("old", res)
        self.assertIn("comparison", res)

    def test_compute_rejects_pan_in_income(self):
        inc = dict(self.case["request"]["income"], pan="ABCPE1234F")
        r = self.client.post("/compute", json={"income": inc})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["errors"][0]["code"], "INPUT_INVALID")

    def test_build_json(self):
        r = self.client.post("/build-json?form=ITR1&ay=2026-27", json=self.case["request"])
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn("ITR1", body["itr_json"]["ITR"])
        self.assertTrue(any(w["severity"] == "blocking" for w in body["warnings"]))

    def test_build_json_422_shape(self):
        req = json.loads(json.dumps(self.case["request"]))
        req["filer"]["pan"] = "bad"
        r = self.client.post("/build-json?form=ITR1", json=req)
        self.assertEqual(r.status_code, 422)
        err = r.json()["errors"][0]
        self.assertEqual(err["code"], "REQUEST_INVALID")
        self.assertIn("filer.pan", err["field"])

    def test_itr4_not_implemented_is_422(self):
        r = self.client.post("/build-json?form=ITR4", json=self.case["request"])
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["errors"][0]["code"], "FORM_NOT_IMPLEMENTED")

    def test_openapi_has_contract_models(self):
        spec = self.client.get("/openapi.json").json()
        for name in ("FilerMetadata", "BuildJsonResponse", "ComputeResponse", "Issue"):
            self.assertIn(name, spec["components"]["schemas"])


if __name__ == "__main__":
    unittest.main()
