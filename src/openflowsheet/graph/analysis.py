"""The structural analysis: declaration in, `StructuralReport` out. Evaluates nothing.

T01 specification §8.1 fixes the order in which findings are decided, and the order matters:

1. a certificate whose mismatch exceeds its kind's tolerance is a **`SPECIFICATION_CONFLICT`** —
   the declared specifications contradict each other and no state satisfies both;
2. an under-determined part is **`STRUCTURAL_UNDER_SPECIFICATION`**;
3. an over-determined part, *after the certified rows are removed*, is
   **`STRUCTURAL_OVER_SPECIFICATION`**;
4. otherwise the declaration is **`STRUCTURALLY_CLOSED`**.

**Why "after the certified rows are removed" carries the whole rule.** The nominal, valid SYN-001
is itself over-determined: 49 rows over 47 columns, with a seven-row over-determined block. A
validator that rejected an over-determined block would reject the flowsheet this project is built
on. What separates it from the conflicting revision is not *whether* there is a block but whether
everything in it carries a certificate — and blueprint §7.7 allows an equation to be discharged
only with one.

A declaration can be both under- and over-determined at once (`SQ-1`), and the report says both.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.graph.blocks import BlockTriangularForm, block_triangular_form
from openflowsheet.graph.certificates import certify
from openflowsheet.graph.dof import unit_degrees_of_freedom
from openflowsheet.graph.matching import canonical_matching, dulmage_mendelsohn
from openflowsheet.graph.process import ProcessGraph
from openflowsheet.graph.report import (
    Finding,
    StructuralReport,
    Unsupported,
    implicated_from,
)
from openflowsheet.graph.tear import TearAnalysis, analyse_tear
from openflowsheet.graph.trace import (
    Declaration,
    StructureUnavailableError,
    trace_declaration,
)

__all__ = ["analyse", "analyse_declaration"]

_PROVENANCE: Mapping[str, object] = {
    "analysis": "T01 declaration-traced incidence v1",
    "increment": 2,
    "tie_break_rules": [
        "lexicographic-least-matching",
        "least-row-index-block-order",
        "dimension/boundary-distance/declaration-order",
    ],
}


def analyse(
    spec: ProblemSpec,
    graph: ProcessGraph,
    *,
    model_version: str = "",
    constants_sha256: str = "",
    specification_ids: Mapping[str, str] | None = None,
    row_units: Mapping[str, str] | None = None,
) -> StructuralReport:
    """Trace `spec` and analyse it. A row that cannot be traced is `UNSUPPORTED`, never a pass."""
    try:
        declaration = trace_declaration(
            spec,
            model_version=model_version,
            constants_sha256=constants_sha256,
            specification_ids=specification_ids,
            row_units=row_units,
        )
    except StructureUnavailableError as error:
        return StructuralReport(
            model_version=model_version,
            constants_sha256=constants_sha256,
            finding="UNSUPPORTED",
            structural_counts=None,
            nnz=0,
            dm_full=None,
            dm_after_certificates=None,
            unsupported=(
                Unsupported(kind="structure_unavailable", detail=error.reason, row_id=error.row_id),
            ),
            provenance=dict(_PROVENANCE),
        )
    return analyse_declaration(declaration, graph, specification_ids=specification_ids)


def analyse_declaration(
    declaration: Declaration,
    graph: ProcessGraph,
    *,
    specification_ids: Mapping[str, str] | None = None,
) -> StructuralReport:
    """§8.1's rule on an already-traced declaration."""
    names = dict(specification_ids or {})
    incidence = declaration.incidence()
    rows, columns = list(declaration.row_ids), list(declaration.column_ids)

    dm_full = dulmage_mendelsohn(rows, columns, incidence)
    matching = canonical_matching(rows, columns, incidence)

    redundancy = certify(declaration)
    certified = set(redundancy.certified_rows)
    retained = [row_id for row_id in rows if row_id not in certified]
    dm_kept = dulmage_mendelsohn(
        retained, columns, {row_id: incidence[row_id] for row_id in retained}
    )

    units = unit_degrees_of_freedom(declaration, graph, retained_rows=retained)
    over_specified, implicated = implicated_from(units, names)

    candidate_rows = tuple(
        row_id for row_id in dm_kept.over_rows if declaration.rows[row_id].is_specification_row
    )
    candidate_specifications: list[str] = []
    for row_id in candidate_rows:
        name = names.get(row_id)
        if name is not None and name not in candidate_specifications:
            candidate_specifications.append(name)

    finding: Finding
    implicated_objects: tuple[str, ...] = tuple(implicated)
    if redundancy.conflicts:
        finding = "SPECIFICATION_CONFLICT"
        conflicting = redundancy.conflicts[0]
        implicated_objects = (conflicting.row_id, *(name for name, _ in conflicting.equals))
        over_specified = ()
    elif dm_kept.deficit > 0:
        finding = "STRUCTURAL_UNDER_SPECIFICATION"
        implicated_objects = dm_kept.under_cols
        over_specified = ()
    elif dm_kept.excess > 0:
        finding = "STRUCTURAL_OVER_SPECIFICATION"
        if not implicated_objects:
            implicated_objects = tuple(candidate_specifications) or dm_kept.over_rows
    else:
        finding = "STRUCTURALLY_CLOSED"
        implicated_objects = ()
        over_specified = ()

    form: BlockTriangularForm | None = None
    tear: TearAnalysis | None = None
    absent: list[Unsupported] = []
    if finding == "STRUCTURALLY_CLOSED":
        square = canonical_matching(
            retained, columns, {row_id: incidence[row_id] for row_id in retained}
        )
        form = block_triangular_form(
            retained, {row_id: incidence[row_id] for row_id in retained}, square
        )
        tear = analyse_tear(declaration, graph, retained_rows=retained, square_form=form)
        absent.extend(
            Unsupported(
                kind="multi_edge_feedback_set",
                detail=f"no single edge breaks the loop {list(loop.units)}",
            )
            for loop in tear.loops
            if loop.unsupported == "multi_edge_feedback_set"
        )
    else:
        # §7.1 defines the block-triangular form on a square, perfectly matched incidence. A
        # declaration that is not closed has no such system, and decomposing part of one would
        # describe a problem nobody posed.
        absent.append(
            Unsupported(
                kind="not_applicable",
                detail=(
                    f"block_triangular_form and tear: not applicable while the finding is "
                    f"{finding}; both are defined on a structurally closed system (§7.1)"
                ),
            )
        )

    matched = dm_full.structural_rank
    counts = {
        "free_variables": len(columns),
        "equations": len(rows),
        "matched": matched,
        "unmatched": (len(rows) - matched) + (len(columns) - matched),
    }

    return StructuralReport(
        model_version=declaration.model_version,
        constants_sha256=declaration.constants_sha256,
        finding=finding,
        structural_counts=counts,
        nnz=declaration.nnz,
        dm_full=dm_full,
        dm_after_certificates=dm_kept,
        certificates=redundancy.certificates,
        uncertified_affine_rows=redundancy.uncertified_affine_rows,
        candidate_specification_rows=candidate_rows,
        candidate_specifications=tuple(candidate_specifications),
        unit_degrees_of_freedom=units,
        over_specified_units=over_specified,
        implicated_objects=implicated_objects,
        canonical_matching=matching,
        block_triangular_form=form,
        tear=tear,
        unsupported=tuple(absent),
        provenance=dict(_PROVENANCE),
    )


def with_rows_removed(spec: ProblemSpec, row_ids: frozenset[str]) -> ProblemSpec:
    """A spec without the named rows, for the synthetic refusals of §13. Not used in production."""
    return replace(
        spec,
        equations=tuple(
            equation for equation in spec.equations if equation.equation_id not in row_ids
        ),
    )
