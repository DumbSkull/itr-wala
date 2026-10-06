"""In-process bridge to the vendored upstream engine.

The upstream scripts under skills/itr-wala/scripts/ are kept byte-identical to
karanb192/itr-wala so they stay pullable. This module is the ONLY place that
knows where they live; nothing else in service/ imports them directly.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

_SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "itr-wala" / "scripts"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"itr_wala_{name}", _SCRIPTS / f"{name}.py")
    if spec is None or spec.loader is None:  # pragma: no cover - packaging error
        raise ImportError(f"cannot load upstream {name}.py from {_SCRIPTS}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tax_engine = _load("tax_engine")
validate_income = _load("validate_income")

ENGINE_VERSION: str = "1.2.0"  # mirrors the value tax_engine.compute() stamps
ENGINE_AY: str = tax_engine.AY
ENGINE_FY: str = tax_engine.FY


def validate(income: dict) -> tuple[list[str], list[str]]:
    """Run upstream validate_income.check(). Returns (errors, warnings).

    The raw-text pass (PAN / Aadhaar sniffing) runs on the serialised input so
    identity data can never ride along inside the computation payload.
    """
    return validate_income.check(income, json.dumps(income))


def compute(income: dict) -> dict:
    """Run upstream tax_engine.compute(). Pure function of its input."""
    return tax_engine.compute(income)
