"""schema_store mechanics, exercised with a synthetic schema (the real one
may not be vendored yet)."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from service import schema_store

SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "required": ["ITR"],
    "properties": {"ITR": {"type": "object", "required": ["ITR1"], "properties": {"ITR1": {
        "type": "object", "required": ["Form_ITR1"],
        "properties": {"Form_ITR1": {"type": "object", "properties": {
            "SchemaVer": {"type": "string", "enum": ["Ver1.1"]}}}}}}}},
}


class SchemaStore(unittest.TestCase):
    def setUp(self):
        schema_store.load.cache_clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        raw = json.dumps(SCHEMA).encode()
        (self.d / "s.json").write_bytes(raw)
        (self.d / "sources.json").write_text(json.dumps({"s.json": {"sha256": hashlib.sha256(raw).hexdigest()}}))

    def tearDown(self):
        self.tmp.cleanup()
        schema_store.load.cache_clear()

    def test_missing_is_none(self):
        self.assertIsNone(schema_store.load(self.d, "nope.json"))

    def test_load_and_version(self):
        s = schema_store.load(self.d, "s.json")
        self.assertEqual(s.version, "Ver1.1")

    def test_validate(self):
        s = schema_store.load(self.d, "s.json")
        self.assertEqual(schema_store.validate(s, {"ITR": {"ITR1": {"Form_ITR1": {"SchemaVer": "Ver1.1"}}}}), [])
        errs = schema_store.validate(s, {"ITR": {"ITR1": {"Form_ITR1": {"SchemaVer": "Ver9"}}}})
        self.assertEqual(len(errs), 1)
        self.assertTrue(errs[0].startswith("ITR/ITR1/Form_ITR1/SchemaVer"))

    def test_hand_edit_refused(self):
        (self.d / "s.json").write_text(json.dumps(SCHEMA) + " ")
        with self.assertRaises(schema_store.SchemaIntegrityError):
            schema_store.load(self.d, "s.json")


if __name__ == "__main__":
    unittest.main()
