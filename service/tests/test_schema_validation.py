"""Layer 1: builder output validates against the department's own schema.

These tests SKIP (loudly) until the schema has been vendored with
scripts/fetch_schemas.py. CI sets REQUIRE_SCHEMAS=1 so a missing schema
fails the build instead of skipping once it has been vendored.
"""

from __future__ import annotations

import json
import os
import unittest

from service import schema_store
from service.json_builder import ay_registry
from service.tests.helpers import cases, run_case

AY = ay_registry.get("2026-27")


def _loaded(form: str):
    return schema_store.load(AY.schema_dir, AY.forms[form].schema_file)


class SchemaConformance(unittest.TestCase):
    def _need(self, form: str):
        loaded = _loaded(form)
        if loaded is None:
            msg = (f"{AY.forms[form].schema_file} not vendored for AY {AY.ay} - "
                   "run scripts/fetch_schemas.py")
            if os.environ.get("REQUIRE_SCHEMAS") == "1":
                self.fail(msg)
            self.skipTest(msg)
        return loaded

    def test_itr1_goldens_validate(self):
        loaded = self._need("ITR1")
        for p in cases("itr1_cases"):
            with self.subTest(case=p.name):
                resp = run_case(p)  # core already validates; assert the flag too
                self.assertTrue(resp.schema_validated)
                self.assertEqual(schema_store.validate(loaded, resp.itr_json), [])

    def test_itr1_schema_version_detected(self):
        loaded = self._need("ITR1")
        self.assertIsNotNone(loaded.version, "could not find SchemaVer pin inside the vendored schema")

    def test_codes_exist_in_schema(self):
        """Every enum code the builder can emit must appear somewhere in the schema."""
        loaded = self._need("ITR1")
        from service.json_builder import codes
        text = json.dumps(loaded.schema)
        for code in list(codes.EXEMPT_ALLOWANCE_CODES) + list(codes.OTHER_SOURCE_CODES.values()):
            with self.subTest(code=code):
                self.assertIn(json.dumps(code), text)


class Provenance(unittest.TestCase):
    def test_every_vendored_file_is_in_manifest(self):
        d = AY.schema_dir
        manifest_p = d / "sources.json"
        manifest = json.loads(manifest_p.read_text()) if manifest_p.exists() else {}
        for p in d.iterdir():
            if p.name in ("sources.json", "SOURCES.md", ".gitkeep"):
                continue
            with self.subTest(file=p.name):
                self.assertIn(p.name, manifest, "vendored file without provenance")
                self.assertEqual(manifest[p.name]["sha256"], schema_store._sha256(p))


if __name__ == "__main__":
    unittest.main()
