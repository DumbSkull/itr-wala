"""Structured failures. Raised = the request needs different information.

The private app maps these to "we need different information" UI. They are
never swallowed and never replaced by a default.
"""

from __future__ import annotations

from .schemas import Issue, Severity


class BuildError(Exception):
    def __init__(self, issues: list[Issue]):
        self.issues = issues
        super().__init__("; ".join(f"{i.code}: {i.message}" for i in issues))

    @classmethod
    def one(cls, code: str, message: str, field: str | None = None) -> "BuildError":
        return cls([Issue(code=code, severity=Severity.blocking, message=message, field=field)])


class IssueLog:
    """Collects warnings while building; `require` collects hard errors so the
    caller sees ALL problems at once instead of fixing them one round-trip at a time."""

    def __init__(self) -> None:
        self.warnings: list[Issue] = []
        self.errors: list[Issue] = []

    def warn(self, code: str, message: str, field: str | None = None,
             severity: Severity = Severity.review) -> None:
        self.warnings.append(Issue(code=code, severity=severity, message=message, field=field))

    def info(self, code: str, message: str, field: str | None = None) -> None:
        self.warn(code, message, field, Severity.info)

    def blocking(self, code: str, message: str, field: str | None = None) -> None:
        """Output is still produced, but must not be uploaded as-is."""
        self.warn(code, message, field, Severity.blocking)

    def error(self, code: str, message: str, field: str | None = None) -> None:
        """Input cannot produce a correct return. No JSON is emitted."""
        self.errors.append(Issue(code=code, severity=Severity.blocking, message=message, field=field))

    def raise_if_errors(self) -> None:
        if self.errors:
            raise BuildError(self.errors)
