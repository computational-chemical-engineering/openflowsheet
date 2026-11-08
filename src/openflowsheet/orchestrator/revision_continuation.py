"""Revision continuation: recovery edge 3's continuation for a revision-built region (ADR 0072).

Design note `docs/design/RRC-revision-region-continuation.md` §5.1, §5.3 and §5.6. Under
`globalization.eo_recovery = "homotopy_or_revision_continuation_or_sequential_restart"`
(`RRC-revision-v1`), a region with no specification continuation is continued from the **nearest
ancestor revision with a `VERIFIED` solve**: `H(x, λ) = F(x; p(λ))`,
`p(λ) = p* + (1 − λ)(p_src − p*)`, ADR 0010 D2's map, over exactly the pinned inputs whose
values differ between the ancestor's declaration and the target's. The λ = 0 level is then the
ancestor's certified problem, bit for bit, and it opens from the ancestor certificate's root in
that certificate's final signature.

The application layer finds and assembles the candidate (it has the store and the revision
documents) and hands it down as a `RevisionContinuationCandidate`, or a typed
`RevisionContinuationRefusal`; the orchestrator never reads a store. This module holds the types,
the record's constants and the pure checks that run at the edge (`revision_continuation`, §5.6):
no I/O, no compilation, no float threshold. Every decision is an id comparison, a canonical-encoding
comparison of document constants or a digest equality, and the first failure decides:

- **R5** `model_version` equals the target's, else `rejected("model_version")`. With it equal, the
  candidate's parameter ids are the declaration's, as a set; anything else is a defect
  (`ValueError`), since equal structure means equal ids.
- **R6** the continued set `D` is non-empty, else `rejected("no_changed_specification")`: the
  ancestor would be a verified root of the target itself, which is a warm start (ADR 0024), not a
  path.
- **R8** the λ = 0 level's `declaration_identity` is the candidate's `(model_version,
  constants_sha256)`, else `rejected("level_identity")`.
- **R9a** every unit of the region's signature is in the candidate's signature, else
  `rejected("opening(coverage:<first missing unit, in signature_units order>)")`.

A refusal is recorded as one `initializer_rejected` event, `revision_continuation_<status>:
<reason>` (`refusal_message`), and the ADR 0015 sequential restart follows unchanged.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from typing import Final, Literal

from openflowsheet.canonical import encode_doubles
from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.orchestrator.execution import Region, declaration_identity
from openflowsheet.orchestrator.homotopy import Continuation, level_values, rebind

__all__ = [
    "RECORD",
    "REFUSAL_HEAD",
    "REVISION_CONTINUATION_SOURCE",
    "SELECTION",
    "RevisionContinuationCandidate",
    "RevisionContinuationRecord",
    "RevisionContinuationRefusal",
    "RevisionContinuationStatus",
    "continued_parameters",
    "refusal_message",
    "revision_continuation",
]

#: The recovery item's `initializer_source` (§5.8): a free string, not a policy chain entry.
REVISION_CONTINUATION_SOURCE: Final = "revision_continuation_source"
#: `solve-path.json`'s `revision_continuation` member's record version (§5.8).
RECORD: Final = "RRC-revision-continuation-v1"
#: §5.3's selection rule.
SELECTION: Final = "store-nearest-verified-ancestor-v1"
#: The refusal message's head: `revision_continuation_<status>: <reason>` (§5.8).
REFUSAL_HEAD: Final = "revision_continuation"

RevisionContinuationStatus = Literal["absent", "rejected", "not_reached", "taken"]


@dataclass(frozen=True)
class RevisionContinuationCandidate:
    """The assembled source (§5.3): the nearest verified ancestor's identity, root and declaration.

    `signature` is the source certificate's final `branch_provenance` signature, `(unit, regime)`
    in recorded order; `state` is the solution-state values (the certificate's root, whose
    digest is `full_state_sha256`); `parameters` is the ancestor declaration's full pinned-input
    vector. The ids are provenance only.
    """

    job_id: str | None
    revision_id: str | None
    model_version: str
    constants_sha256: str
    full_state_sha256: str
    signature: tuple[tuple[str, str], ...]
    state: Mapping[str, float]
    parameters: Mapping[str, float]


@dataclass(frozen=True)
class RevisionContinuationRefusal:
    """A typed refusal (§5.3, §5.5, §5.6): `absent` before any candidate exists, `rejected` after.
    `reason` is an R0 string; it never carries a float."""

    status: Literal["absent", "rejected"]
    reason: str


@dataclass(frozen=True)
class RevisionContinuationRecord:
    """The step's account of the edge (§5.5): what was decided, and on `taken` what was continued.

    `parameter_ids` is `D` and `start_values` the ancestor's values of it, in the same order; both
    are empty unless `status` is `taken`."""

    status: RevisionContinuationStatus
    reason: str | None = None
    parameter_ids: tuple[str, ...] = ()
    start_values: tuple[float, ...] = ()


def refusal_message(refusal: RevisionContinuationRefusal) -> str:
    """The `initializer_rejected` event's message for a refusal (§5.8)."""
    return f"{REFUSAL_HEAD}_{refusal.status}: {refusal.reason}"


def continued_parameters(source: Mapping[str, float], spec: ProblemSpec) -> tuple[str, ...]:
    """`D` (§5.1): the target's pinned inputs whose values differ from the source's, in
    `spec.parameter_ids` order, compared under the per-value encoding `constants_sha256` hashes
    (so `-0.0` and `+0.0` are one value, as they are one constant)."""
    return tuple(
        pid
        for pid in spec.parameter_ids
        if encode_doubles((source[pid],)) != encode_doubles((spec.parameters[pid],))
    )


def revision_continuation(
    candidate: RevisionContinuationCandidate, spec: ProblemSpec, region: Region
) -> Continuation | RevisionContinuationRefusal:
    """§5.6's pure checks R5, R6, R8 and R9a, in that order; the continuation when all pass."""
    model_version, _ = declaration_identity(spec)
    if candidate.model_version != model_version:
        return RevisionContinuationRefusal("rejected", "model_version")
    if set(candidate.parameters) != set(spec.parameter_ids):
        raise ValueError(
            "a candidate with the target's model_version must pin exactly the target's inputs"
        )
    continued = continued_parameters(candidate.parameters, spec)
    if not continued:
        return RevisionContinuationRefusal("rejected", "no_changed_specification")
    continuation = Continuation(
        type="revision_continuation",
        parameter_ids=continued,
        variable_ids=(),
        start_values=tuple(float(candidate.parameters[pid]) for pid in continued),
    )
    opening = rebind(spec, level_values(continuation, spec.parameters, {}, Fraction(0)))
    if declaration_identity(opening) != (candidate.model_version, candidate.constants_sha256):
        return RevisionContinuationRefusal("rejected", "level_identity")
    covered = {unit for unit, _ in candidate.signature}
    for unit in region.signature_units:
        if unit not in covered:
            return RevisionContinuationRefusal("rejected", f"opening(coverage:{unit})")
    return continuation
