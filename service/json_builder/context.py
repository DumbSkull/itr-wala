"""Everything a schedule module needs, computed once by the form builder."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from ..errors import IssueLog
from ..schemas import FilerMetadata


@dataclass(frozen=True)
class BuildContext:
    income: dict[str, Any]          # upstream income.json (as submitted)
    filer: FilerMetadata
    regime: str                     # "new" | "old" - the confirmed choice
    comp: dict[str, Any]            # tax_engine.compute(...)[regime]
    ay: str                         # "2026-27"
    due_date: date
    filing_date: date
    return_sec: int                 # codes.RETURN_SEC_*
    log: IssueLog

    # -- convenience accessors over the upstream structures --
    @property
    def heads(self) -> dict[str, Any]:
        return self.comp["heads"]

    @property
    def tax(self) -> dict[str, Any]:
        return self.comp["tax"]

    @property
    def interest(self) -> dict[str, Any]:
        return self.comp["interest_and_fees"]

    @property
    def salary_in(self) -> dict[str, Any]:
        return self.income.get("income", {}).get("salary") or {}

    @property
    def taxes_in(self) -> dict[str, Any]:
        return self.income.get("taxes_paid") or {}


def rupees(x: Any) -> int:
    """Portal amounts are whole rupees. Engine amounts are already rounded per
    s.288A/288B where the law requires; this only drops float noise."""
    return int(round(float(x or 0)))
