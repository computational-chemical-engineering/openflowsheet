"""Compatible warm starts: blueprint §7.4's second initialization source on the revision path.

ADR 0024; T08 build-first specification Part B (§B1–§B2). A policy opts in by naming
`compatible_warm_start` in its `initializer_chain` (`T08-warm-v1`); every other policy's chain is
empty and nothing here runs. The application layer finds the candidate (`jobs/runner.py`, which
has the store) and hands it down as a `WarmStartCandidate`; the orchestrator never reads a store.

The candidate is checked, in §B2's order, before the region opens from it:

1. `integrity` — a `solution-state-v1` document whose ids are its keys and whose `state_sha256`
   recomputes (T07 ruling round 2 F1.4's first three checks, `run.solution_state`);
2. `compatibility` — its `variable_ids`, as a set, are the target declaration's;
3. `bounds` — a molar flow below `0.0` is projected to it and logged (K03 §10.1's rule), never a
   rejection;
4. `evaluation` — the region's residual at the projected candidate evaluates `ok`;
5. `opening` — T03 §5.1's six checks on attempt 0's opening (`region.solve_region`).

The first failure is `initializer_rejected` with `warm_start_rejected(<check>)` and the next
source follows; the run never fails because of the warm start. The candidate supplies only `x₀`:
nothing here writes a specification, bound, tolerance or check policy.

`WarmStartRecord.as_document()` is `solve-path.json`'s `warm_start` member (§B2's table), from
which a rerun rebuilds the candidate (`WarmStartCandidate.from_record`) without a lookup.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, Literal

from openflowsheet.compile.spec import ProblemSpec

__all__ = [
    "RECORD",
    "SELECTION",
    "WARM_START_REJECTED",
    "WARM_START_SOURCE",
    "WarmStartCandidate",
    "WarmStartRecord",
    "WarmStartStatus",
    "compatible",
    "intact",
    "project_bounds",
]

#: The source's id in `SolvePolicy.initializer_chain` and item 0's `initializer_source` (T03 §8.1).
WARM_START_SOURCE: Final = "compatible_warm_start"
#: The rejection message's head: `warm_start_rejected(<check>)`, no float.
WARM_START_REJECTED: Final = "warm_start_rejected"
#: §B1's selection rule, the only one in v0.1.
SELECTION: Final = "store-latest-verified-lineage-v1"
#: The record's version (§B2's table).
RECORD: Final = "warm-start-v1"

WarmStartStatus = Literal["absent", "accepted", "rejected"]


@dataclass(frozen=True)
class WarmStartCandidate:
    """The source-2 candidate: the solution-state document as found, and where it came from.

    `document` is the parsed `solution-state.json` of the selected job, or `None` when the file
    could not be parsed (an `integrity` rejection). The ids are provenance only (ADR 0024 D4).
    """

    document: Any
    source_job_id: str | None
    source_revision_id: str | None
    selection: str = SELECTION

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> WarmStartCandidate | None:
        """ADR 0024 D5: a rerun's candidate, from the bundle's own record; `None` if absent."""
        if record.get("status") == "absent":
            return None
        return cls(
            document=record.get("candidate"),
            source_job_id=record.get("source_job_id"),
            source_revision_id=record.get("source_revision_id"),
            selection=str(record.get("selection", SELECTION)),
        )


@dataclass(frozen=True)
class WarmStartRecord:
    """`solve-path.json`'s `warm_start` member (§B2's table)."""

    status: WarmStartStatus
    reason: str | None = None
    candidate: WarmStartCandidate | None = None
    #: `(variable_id, from, to)` of each bounds projection, in declaration order.
    projections: tuple[tuple[str, float, float], ...] = ()
    selection: str = SELECTION

    def as_document(self) -> dict[str, Any]:
        candidate = self.candidate
        return {
            "record": RECORD,
            "selection": candidate.selection if candidate is not None else self.selection,
            "status": self.status,
            "reason": self.reason,
            "source_job_id": candidate.source_job_id if candidate is not None else None,
            "source_revision_id": candidate.source_revision_id if candidate is not None else None,
            "candidate": candidate.document if candidate is not None else None,
            "projections": [[name, before, after] for name, before, after in self.projections],
        }


def intact(document: Any) -> bool:
    """`integrity`: F1.4's checks 1–3 (schema, ids equal keys, `state_sha256` recomputes). The
    certificate checks (4, 5) have no subject here — the candidate travels without one."""
    if not isinstance(document, Mapping):
        return False
    from openflowsheet.run.solution_state import inconsistencies

    return inconsistencies(document, None) == ("certificate_missing",)


def compatible(document: Mapping[str, Any], spec: ProblemSpec) -> bool:
    """`compatibility`: the candidate's ids, as a set, are the declaration's (§B1)."""
    return set(document["variable_ids"]) == set(spec.variable_ids)


def project_bounds(
    values: Mapping[str, float], spec: ProblemSpec
) -> tuple[dict[str, float], tuple[tuple[str, float, float], ...]]:
    """`bounds`: every molar flow below its lower bound `0.0` is set to it; the start over
    `spec.variable_ids` and the `(id, from, to)` of each projection (K03 §10.1)."""
    start = {name: float(values[name]) for name in spec.variable_ids}
    projections: list[tuple[str, float, float]] = []
    for name in spec.variable_ids:
        if spec.variable_kinds.get(name) == "molar_flow" and start[name] < 0.0:
            projections.append((name, start[name], 0.0))
            start[name] = 0.0
    return start, tuple(projections)
