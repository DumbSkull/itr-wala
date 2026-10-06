"""Vendored department schemas: integrity check + validation.

service/schema/AY<ay>/ holds the dept's JSON schemas byte-for-byte as
downloaded, plus sources.json (machine-readable provenance written by
scripts/fetch_schemas.py) and SOURCES.md (the same, for humans).

A schema file whose sha256 doesn't match sources.json is refused - that
catches hand edits and half-finished downloads.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import jsonschema


@dataclass(frozen=True)
class LoadedSchema:
    path: Path
    sha256: str
    schema: dict[str, Any]
    version: Optional[str]          # e.g. "Ver1.1", read from the schema itself


class SchemaIntegrityError(RuntimeError):
    pass


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _find_schema_ver(schema: Any) -> Optional[str]:
    """The dept schemas pin SchemaVer as an enum/const/pattern inside the Form_ITRx
    definition. Walk the tree for the first such pin."""
    stack = [schema]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            sv = node.get("SchemaVer")
            if isinstance(sv, dict):
                if isinstance(sv.get("enum"), list) and sv["enum"]:
                    return str(sv["enum"][0])
                if "const" in sv:
                    return str(sv["const"])
                # AY 2026-27 schemas pin it as a bare regex, e.g. "pattern": "Ver1.0"
                if isinstance(sv.get("pattern"), str) and sv["pattern"].startswith("Ver"):
                    return sv["pattern"]
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return None


@lru_cache(maxsize=None)
def load(schema_dir: Path, file_name: str) -> Optional[LoadedSchema]:
    """Returns None when the schema hasn't been vendored yet."""
    path = schema_dir / file_name
    if not path.exists():
        return None
    manifest_path = schema_dir / "sources.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    entry = manifest.get(file_name)
    digest = _sha256(path)
    if not entry or entry.get("sha256") != digest:
        raise SchemaIntegrityError(
            f"{path} does not match sources.json (sha256 {digest}). Re-run "
            "scripts/fetch_schemas.py - never hand-edit vendored schemas.")
    schema = json.loads(path.read_text(encoding="utf-8-sig"))
    return LoadedSchema(path=path, sha256=digest, schema=schema, version=_find_schema_ver(schema))


def validate(loaded: LoadedSchema, instance: dict) -> list[str]:
    """All violations, as 'json.path: message' strings (empty list = valid)."""
    cls = jsonschema.validators.validator_for(loaded.schema)
    v = cls(loaded.schema)
    out = []
    for err in sorted(v.iter_errors(instance), key=lambda e: list(e.absolute_path)):
        path = "/".join(str(p) for p in err.absolute_path) or "(root)"
        out.append(f"{path}: {err.message}")
    return out
