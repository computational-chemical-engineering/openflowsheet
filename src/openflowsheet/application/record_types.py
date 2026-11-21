"""The `Records` results (ADR 0061 D13, ADR 0019 Amendment 8): one type per operation, each the
`application-results` `$def` of its snake_case name.

A result holds its members as documents already (a record, a rights row, a finding is a JSON
object); `as_document()` is the response every transport carries.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RecordPage:
    """`search_records`: one page of the matching records, by SHA, each with its D11 effective
    rights per source; `resolution` (D9) is over every match, not the page; `next_cursor`
    continues after this page's last item, `None` on the last page."""

    items: tuple[Mapping[str, Any], ...]
    resolution: Mapping[str, Any]
    next_cursor: str | None

    def as_document(self) -> dict[str, Any]:
        return {
            "items": [dict(item) for item in self.items],
            "resolution": dict(self.resolution),
            "next_cursor": self.next_cursor,
        }


@dataclass(frozen=True)
class RecordView:
    """`get_record`: the record's identity projection, its `registrations` rows (D8; none for a
    record only the legacy store holds), the layer it is read from, and its rights: the
    effective assessment per source and every register row that names one of its sources."""

    record_sha256: str
    record: Mapping[str, Any]
    registrations: tuple[Mapping[str, Any], ...]
    store: str
    effective: Mapping[str, Any]
    rows: tuple[Mapping[str, Any], ...]

    def as_document(self) -> dict[str, Any]:
        return {
            "record_sha256": self.record_sha256,
            "record": dict(self.record),
            "registrations": [dict(row) for row in self.registrations],
            "store": self.store,
            "rights": {"effective": dict(self.effective), "rows": [dict(r) for r in self.rows]},
        }


@dataclass(frozen=True)
class RecordRegistrationResult:
    """`register_record`: per record, in submission order, its SHA, whether this call created
    its object (D8) and this submission's findings."""

    results: tuple[Mapping[str, Any], ...]

    def as_document(self) -> dict[str, Any]:
        return {"results": [dict(item) for item in self.results]}


@dataclass(frozen=True)
class RecordValidationReport:
    """`validate_record`: D7's errors and findings of every record and reaction the request
    names, and the SHA of its `record`, `None` when it is refused or not given."""

    errors: Sequence[Mapping[str, Any]]
    findings: Sequence[Mapping[str, Any]]
    record_sha256: str | None

    def as_document(self) -> dict[str, Any]:
        return {
            "errors": [dict(item) for item in self.errors],
            "findings": [dict(item) for item in self.findings],
            "record_sha256": self.record_sha256,
        }


@dataclass(frozen=True)
class RightsAssessmentResult:
    """`assess_rights`: the project register row the call appended (with its insertion
    sequence) and the effective assessment of (source, record) after it."""

    row: Mapping[str, Any]
    effective: Mapping[str, Any]

    def as_document(self) -> dict[str, Any]:
        return {"row": dict(self.row), "effective": dict(self.effective)}
