"""Shared fixture plumbing for the builder tests."""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

from service import core
from service.schemas import BuildJsonRequest, BuildJsonResponse, FormType

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def cases(form_dir: str) -> list[Path]:
    return sorted((FIXTURES / form_dir).glob("*.input.json"))


def expected_path(input_path: Path) -> Path:
    return input_path.with_name(input_path.name.replace(".input.json", ".expected.json"))


def run_case(input_path: Path) -> BuildJsonResponse:
    os.environ.pop("ITR_SOFTWARE_ID", None)  # goldens always carry the placeholder
    case = json.loads(input_path.read_text())
    req = BuildJsonRequest.model_validate(case["request"])
    return core.build_json(req, FormType(case["form"]), case["ay"], date.fromisoformat(case["today"]))


def golden_view(resp: BuildJsonResponse) -> dict:
    """What a golden file pins: the full portal JSON, the summary, and which
    warnings fire (codes + severity; message wording is free to improve)."""
    return {
        "itr_json": resp.itr_json,
        "summary": resp.summary,
        "warnings": sorted(f"{w.severity.value}:{w.code}" for w in resp.warnings),
    }
