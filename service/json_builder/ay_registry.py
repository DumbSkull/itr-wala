"""Assessment-year dispatch.

Each AY is a frozen bundle: its statutory dates, its vendored schema folder
and the builder functions written against that schema. Adding AY 2027-28 means
adding a new entry (and new builders if the schema changed) - never editing
the 2026-27 one, so prior-year output can't silently change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable, Optional

SCHEMA_ROOT = Path(__file__).resolve().parent.parent / "schema"


@dataclass(frozen=True)
class FormSpec:
    form_name: str                 # "ITR-1"
    description: str               # Form_ITR1.Description
    due_date: date                 # s.139(1) due date for this form (non-audit)
    schema_file: str               # file name inside the AY schema folder
    builder: Optional[Callable] = None   # None => not implemented yet


@dataclass(frozen=True)
class AYSpec:
    ay: str                        # "2026-27"
    assessment_year: str           # value of Form_*.AssessmentYear ("2026")
    fy_start: date
    fy_end: date
    belated_deadline: date         # s.139(4)
    revised_deadline: date         # s.139(5)
    forms: dict[str, FormSpec] = field(default_factory=dict)

    @property
    def schema_dir(self) -> Path:
        return SCHEMA_ROOT / f"AY{self.ay}"


def _ay_2026_27() -> AYSpec:
    from . import itr1_builder  # local import: builders import this module too

    return AYSpec(
        ay="2026-27",
        assessment_year="2026",
        fy_start=date(2025, 4, 1),
        fy_end=date(2026, 3, 31),
        belated_deadline=date(2026, 12, 31),
        revised_deadline=date(2027, 3, 31),
        forms={
            "ITR1": FormSpec(
                form_name="ITR-1",
                description="For Indls having Income from Salary, Pension, family pension and Interest",
                due_date=date(2026, 7, 31),
                schema_file="itr1_schema.json",
                builder=itr1_builder.build,
            ),
            "ITR4": FormSpec(
                form_name="ITR-4",
                description="For Presumptive Income from Business & Profession",
                due_date=date(2026, 8, 31),   # Finance Act 2026: non-audit ITR-3/4
                schema_file="itr4_schema.json",
                builder=None,  # next milestone: needs a 44AD/44ADA/44AE layer first
            ),
        },
    )


_REGISTRY: dict[str, Callable[[], AYSpec]] = {"2026-27": _ay_2026_27}


def supported_ays() -> list[str]:
    return sorted(_REGISTRY)


def get(ay: str) -> AYSpec:
    try:
        return _REGISTRY[ay]()
    except KeyError:
        raise KeyError(f"AY {ay!r} not supported (have {supported_ays()})") from None
