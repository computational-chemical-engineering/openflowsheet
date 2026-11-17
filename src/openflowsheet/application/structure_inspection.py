"""`inspect_structure`'s document: the structural report of a revision's route, and its index.

`route_structure` serves `LocalApplication.inspect_structure` (T07 §4.2; ADR 0019 Amendment 3,
A3.1) and is in no identity key. It sits above `validation` (ADR 0076 I-10): its fallback, when no
route binds, reads `validate()`'s reason and the structural stage's report, while the run path in
`revision_run` never calls `validate`. The structural stage stays in `validation` and
`traced_analysis` in `revision_run`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from openflowsheet.application.binding import Binding
from openflowsheet.application.model_builders import SurrogateResolver
from openflowsheet.application.revision_binding import RevisionBinding
from openflowsheet.application.revision_run import Route, route_declaration, select_route
from openflowsheet.application.structure_index import structure_index
from openflowsheet.graph.process import ProcessGraph
from openflowsheet.graph.trace import Declaration

__all__ = ["route_structure"]


def _index(
    declaration: Declaration | None,
    graph: ProcessGraph | None,
    binding: Binding | RevisionBinding,
    document: Mapping[str, Any],
) -> dict[str, Any]:
    """The `rows` and `columns` members (M06 design note §4.1); both `None` when no declaration
    was traced."""
    if declaration is None or graph is None:
        return {"rows": None, "columns": None}
    return structure_index(declaration, graph, binding, document)


def route_structure(
    document: Mapping[str, Any], *, surrogates: SurrogateResolver | None = None
) -> dict[str, Any]:
    """`inspect_structure`'s document (§4.2 as amended by ruling round 1 R1.5 and ruling round 6,
    B1): the structural report of the formulation `solve` will use, naming its `solve_path` and
    its `route_reason` (the revision binder's refusal on `legacy_eo`, `None` on `revision_eo`) —
    or, when no route binds the revision, `validate()`'s reason that the structural analysis did
    not run and the `hint` of the refusal it reports. New in T07 and in no identity key; W5
    projects it.

    ADR 0019 Amendment 3 (A3.1) adds, beside the report and never inside it, the row and column
    index of the declaration that produced it (`rows`, `columns`); and, when no route binds, the
    structural report `validate()` analysed for the document (`validation_structural_report`)
    with the index of its declaration — each `None` when no structural stage ran."""
    from openflowsheet.application.validation import structural_analysis, validate

    route = select_route(document, surrogates=surrogates)
    if not isinstance(route, Route):
        report = validate(document, "simulation", surrogates=surrogates)
        # The hint of the refusal `validate()` reports, when its structural stage ran (ruling
        # round 6, B1 item 4); a document refused before that stage reports none.
        ran = any(check.stage == "structural_analysis" for check in report.checks)
        analysis = structural_analysis(document, surrogates=surrogates) if ran else None
        reported = None if analysis is None else analysis.refusal
        structure: dict[str, Any] = {
            "not_run_reason": report.structural_counts_absent_reason or route.reason,
            "hint": None if reported is None else reported.hint,
            "validation_structural_report": None,
            "rows": None,
            "columns": None,
        }
        if analysis is not None and analysis.report is not None:
            structure["validation_structural_report"] = analysis.report.as_document()
            structure.update(
                _index(analysis.declaration, analysis.graph, analysis.binding, document)
            )
        return structure
    analysis_report, declaration = route_declaration(route)
    return {
        "solve_path": route.solve_path,
        "route_reason": route.reason,
        "structural_report": analysis_report.as_document(),
        **_index(declaration, route.binding.graph, route.binding, document),
    }
