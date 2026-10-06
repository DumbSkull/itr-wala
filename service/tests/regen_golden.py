"""Rewrite *.expected.json from the current builder output.

    python -m service.tests.regen_golden            # all forms
    python -m service.tests.regen_golden itr1_cases

DANGER: this makes the golden tests pass by definition. Only run it after a
deliberate builder change, then review `git diff service/tests/fixtures` line
by line and hand-verify every changed rupee figure (docs/golden-review.md
records the working for each case). A golden file nobody checked is worthless.
"""

from __future__ import annotations

import json
import sys

from service.errors import BuildError
from service.tests.helpers import cases, expected_path, golden_view, run_case


def main(argv: list[str]) -> int:
    dirs = argv[1:] or ["itr1_cases", "itr4_cases"]
    for d in dirs:
        for p in cases(d):
            try:
                view = golden_view(run_case(p))
            except BuildError as e:
                print(f"SKIP {p.name}: build error {e}")
                continue
            expected_path(p).write_text(json.dumps(view, indent=2, ensure_ascii=False) + "\n")
            print(f"wrote {expected_path(p).name}")
    print("\nNow review: git diff service/tests/fixtures")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
