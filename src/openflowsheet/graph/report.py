"""`StructuralReport`, and the six sentences that fix what a structural finding may claim.

T01 specification §11 and §12.2. The sentences are frozen here and carried verbatim by every
report and every check, which is the device K04 used for `VERIFIED` and for the same reason: the
number a structural analysis produces is easy to over-read, and the qualification has to travel
with it rather than live in a document nobody opens.

The one that does the most work is **S4**. After certificates, the conflicting SYN-001 revision's
over-determined part holds ten specification rows, and relaxing any one of them closes the system.
The list of candidates is therefore *complete and not minimal*, and a report that named one of
them as "the" conflict would be inventing a minimal conflict set it has not computed.

`INVALID` from a T01 finding means, and only means, *as declared, this is not a closed simulation
task*. It is not a claim of infeasibility. Blueprint §4.3 makes `READY_FOR_SIMULATION` conditional
on an appropriately closed system, and that is the whole of what is being denied.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Literal

from openflowsheet.graph.blocks import BlockTriangularForm
from openflowsheet.graph.certificates import Certificate
from openflowsheet.graph.dof import UnitDegreesOfFreedom
from openflowsheet.graph.matching import DulmageMendelsohn
from openflowsheet.graph.tear import TearAnalysis

__all__ = [
    "STATEMENTS",
    "Finding",
    "StructuralReport",
    "Unsupported",
    "r0_of",
]

Finding = Literal[
    "STRUCTURALLY_CLOSED",
    "STRUCTURAL_UNDER_SPECIFICATION",
    "STRUCTURAL_OVER_SPECIFICATION",
    "SPECIFICATION_CONFLICT",
    "UNSUPPORTED",
]

#: §11's six sentences, verbatim. Carried by every report; the first three also by `STR-01`.
STATEMENTS: Final[Mapping[str, str]] = {
    "S1": (
        "This finding is structural: it is a statement about the declared equations and "
        "variables and about which of them reference which. It was made without evaluating any "
        "equation."
    ),
    "S2": (
        "Structurally closed means that after the certified redundant rows are removed, every "
        "remaining equation can be assigned a distinct variable it references. It does not "
        "establish that a solution exists, that it is unique, or that any Jacobian is "
        "nonsingular."
    ),
    "S3": (
        "Numerical rank and conditioning are decided by the certificate's regularity screen on "
        "the unregularized target Jacobian at a converged state (blueprint [A08]); this report "
        "makes no such claim, in either direction."
    ),
    "S4": (
        "Over-specified by k means that k more equations are declared than the variables can "
        "absorb after certified redundancy. Every listed candidate is an equation that could be "
        "the one in excess; relaxing any one of them lowers k by one. The list is complete and "
        "is not a minimal conflict set."
    ),
    "S5": (
        "A unit is named as over-specified because the specifications targeting its outlet and "
        "internal variables outnumber the degrees of freedom its own equations leave, with its "
        "inlets treated as known. This is a count of declarations, not a proof that the "
        "specifications contradict each other numerically."
    ),
    "S6": (
        "A certified redundant equation is one shown from the declaration to equal a signed sum "
        "of retained equations up to a constant computed from the specifications; it is retained "
        "in the residual, evaluated by the solver and the verifier, and never discarded."
    ),
}


@dataclass(frozen=True)
class Unsupported:
    """A capability this analysis did not exercise, named. Never silence, never a pass (§12.4)."""

    #: §12.4 names three kinds. `not_applicable` extends that table for the one case it does not
    #: cover: a declaration that is not structurally closed has no square system, so the
    #: block-triangular form is not *unimplemented*, it is undefined (should-fix S7 of the Fable
    #: review of T01, which found the wrong label in use).
    kind: Literal[
        "structure_unavailable",
        "not_implemented",
        "multi_edge_feedback_set",
        "not_applicable",
    ]
    detail: str
    row_id: str | None = None

    def as_document(self) -> dict[str, object]:
        document: dict[str, object] = {"kind": self.kind, "detail": self.detail}
        if self.row_id is not None:
            document["row_id"] = self.row_id
        return document


@dataclass(frozen=True)
class StructuralReport:
    """The whole structural result. Integers, ids and booleans, plus the certificate mismatches.

    The R0 projection (ADR 0007) is this document with the mismatch floats replaced by their
    `consistent` booleans; everything that remains is exactly reproducible on any platform, which
    is what lets gate G05 compare it byte for byte between the two CI architectures.
    """

    model_version: str
    constants_sha256: str
    finding: Finding
    structural_counts: Mapping[str, int] | None
    nnz: int
    dm_full: DulmageMendelsohn | None
    dm_after_certificates: DulmageMendelsohn | None
    certificates: tuple[Certificate, ...] = ()
    uncertified_affine_rows: tuple[str, ...] = ()
    candidate_specification_rows: tuple[str, ...] = ()
    candidate_specifications: tuple[str, ...] = ()
    unit_degrees_of_freedom: tuple[UnitDegreesOfFreedom, ...] = ()
    over_specified_units: tuple[str, ...] = ()
    implicated_objects: tuple[str, ...] = ()
    canonical_matching: Mapping[str, str] = field(default_factory=dict)
    #: The block-triangular form of the square system, when there is one. A declaration that is
    #: not structurally closed has no square system, so this is `None` rather than a partial
    #: decomposition of something that does not decompose (§7.1).
    block_triangular_form: BlockTriangularForm | None = None
    tear: TearAnalysis | None = None
    unsupported: tuple[Unsupported, ...] = ()
    provenance: Mapping[str, Any] = field(default_factory=dict)

    @property
    def excess(self) -> int:
        return 0 if self.dm_after_certificates is None else self.dm_after_certificates.excess

    @property
    def deficit(self) -> int:
        return 0 if self.dm_after_certificates is None else self.dm_after_certificates.deficit

    @property
    def conflicts(self) -> tuple[Certificate, ...]:
        return tuple(entry for entry in self.certificates if not entry.consistent)

    def as_document(self) -> dict[str, Any]:
        return {
            "model_version": self.model_version,
            "constants_sha256": self.constants_sha256,
            "finding": self.finding,
            "structural_counts": (
                None if self.structural_counts is None else dict(self.structural_counts)
            ),
            "nnz": self.nnz,
            "excess": self.excess,
            "deficit": self.deficit,
            "dm_full": None if self.dm_full is None else self.dm_full.as_document(),
            "dm_after_certificates": (
                None
                if self.dm_after_certificates is None
                else self.dm_after_certificates.as_document()
            ),
            "certificates": [entry.as_document() for entry in self.certificates],
            "uncertified_affine_rows": list(self.uncertified_affine_rows),
            "candidate_specification_rows": list(self.candidate_specification_rows),
            "candidate_specifications": list(self.candidate_specifications),
            "unit_degrees_of_freedom": [
                entry.as_document() for entry in self.unit_degrees_of_freedom
            ],
            "over_specified_units": list(self.over_specified_units),
            "implicated_objects": list(self.implicated_objects),
            "canonical_matching": dict(self.canonical_matching),
            "block_triangular_form": (
                None
                if self.block_triangular_form is None
                else self.block_triangular_form.as_document()
            ),
            "tear": None if self.tear is None else self.tear.as_document(),
            "unsupported": [entry.as_document() for entry in self.unsupported],
            "statements": dict(STATEMENTS),
            "provenance": dict(self.provenance),
        }

    def r0_projection(self) -> dict[str, Any]:
        """See `r0_of`. Kept as a method because most callers hold the report, not its document."""
        return r0_of(self.as_document())


def r0_of(document: Mapping[str, Any]) -> dict[str, Any]:
    """A structural report's document with every float replaced by the decision it supports.

    ADR 0007 R0. A certificate's mismatch is a single subtraction of registered doubles and the
    largest-block fraction is one IEEE division of small integers, so both are in fact identical
    across the registered platform pair — but §8.3 keeps floats out of an R0 promise, and what
    the report *decides* from them is an integer or a boolean.

    **There is one of these.** `run/identity.py` used to hand-pick a subset of the report for the
    G05 comparison, which omitted the canonical block order and every `depends_on` — the sequences
    §6.4 says G05 exists to compare — while this method implemented §12.2. Two projections of one
    document are one projection and one rumour (should-fix S3 of the Fable review of T01, and the
    same shape as M4 of the K05 review).
    """
    document = dict(document)
    form = document.get("block_triangular_form")
    if isinstance(form, dict):
        form = dict(form)
        sizes = form["block_sizes_sorted"]
        form.pop("largest_block_fraction", None)
        form["largest_block"] = max(sizes) if sizes else 0
        form["total_size"] = sum(sizes)
        document["block_triangular_form"] = form
    document["certificates"] = [
        {
            key: value
            for key, value in entry.items()
            if key not in {"constant_mismatch", "tolerance"}
        }
        for entry in document["certificates"]
    ]
    return document


def implicated_from(
    units: Sequence[UnitDegreesOfFreedom],
    specification_ids: Mapping[str, str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The over-specified units and the revision objects a finding names.

    A report names what the user wrote — the revision's instance and specification ids — not the
    assembler's internal row and unit ids.
    """
    over = tuple(entry.unit_id for entry in units if entry.over_specified)
    implicated: list[str] = []
    for entry in units:
        if not entry.over_specified:
            continue
        for row_id in entry.specification_rows:
            name = specification_ids.get(row_id)
            if name is not None and name not in implicated:
                implicated.append(name)
        implicated.append(entry.instance_id)
    return over, tuple(implicated)
