"""The validation report's vocabulary: blueprint §4.3, as the frozen schema fixes it.

`ValidationReport` and `Check`, the `Literal` vocabularies `Task`, `ValidationStatus`, `Stage`,
`Result` and `EvidenceClass`, and `utc_timestamp`, the timestamp the report's provenance, the
store and authorization stamp with. Nothing is validated here: the validator is
`openflowsheet.application.validation`, which re-exports every name. This module is a leaf, so
types, store and authz import it without importing the validator.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

Task = Literal["simulation", "optimization"]
ValidationStatus = Literal["DRAFT", "READY_FOR_SIMULATION", "READY_FOR_OPTIMIZATION", "INVALID"]


def utc_timestamp() -> str:
    """T07 design note §5.1's timestamp: RFC 3339 UTC with microseconds. Never R0."""
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


#: Blueprint §4.3's stage order, as the frozen `validation-report.schema.json` enumerates it.
Stage = Literal[
    "schema",
    "dimensions",
    "graph_connectivity",
    "component_reference_compatibility",
    "conditional_classification",
    "capability",
    "structural_analysis",
]
Result = Literal["PASS", "FAIL", "WARN", "NOT_RUN"]
#: Blueprint §4.3: a rank or conflict search must label which of these it is. T01 emits only
#: `structural` and assertion A23 holds it to that; the other two belong to K04 and T06.
EvidenceClass = Literal["structural", "local_numerical", "verified_minimal_subset"]


@dataclass(frozen=True)
class Check:
    """One validation check, in the vocabulary the frozen schema fixes.

    `result` distinguishes a check that ran and failed (`FAIL`) from one that could not run
    (`NOT_RUN`) — the distinction K06 carried as `scope` and the schema carries here. Both are
    kept: `passed` and `scope` remain as derived properties because the CLI and the evidence
    generators read them, and because "did it pass" and "did it run" are different questions.
    """

    id: str
    stage: Stage
    result: Result
    message: str
    implicated_objects: tuple[str, ...] = ()
    evidence_class: EvidenceClass = "structural"

    @property
    def passed(self) -> bool:
        return self.result == "PASS"

    @property
    def scope(self) -> Literal["evaluated", "unsupported"]:
        return "unsupported" if self.result == "NOT_RUN" else "evaluated"

    @property
    def detail(self) -> str:
        return self.message

    def as_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "stage": self.stage,
            "result": self.result,
            "message": self.message,
            "implicated_objects": list(self.implicated_objects),
            "evidence_class": self.evidence_class,
        }


@dataclass(frozen=True)
class ValidationReport:
    """Tied to a revision and a task. Recomputed on demand, never stored as a badge."""

    revision_id: str
    task: Task
    status: ValidationStatus
    checks: tuple[Check, ...]
    structural_counts: Mapping[str, int] | None = None
    structural_counts_absent_reason: str | None = None
    #: `{produced_by, timestamp}` (R3): production metadata, not part of the result. `status`
    #: and every check are a pure function of (document, task); two reports of one revision
    #: differ at most here, so equality ignores it — and every byte-identity or idempotency
    #: comparison compares `as_document()` without it.
    provenance: Mapping[str, Any] = field(default_factory=dict, compare=False)

    def as_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "revision_id": self.revision_id,
            "task": self.task,
            "status": self.status,
            "checks": [check.as_document() for check in self.checks],
            "provenance": dict(self.provenance),
        }
        if self.structural_counts is not None:
            document["structural_counts"] = dict(self.structural_counts)
        else:
            document["structural_counts"] = None
            document["structural_counts_absent_reason"] = self.structural_counts_absent_reason
        return document

    @property
    def ready(self) -> bool:
        return self.status in ("READY_FOR_SIMULATION", "READY_FOR_OPTIMIZATION")
