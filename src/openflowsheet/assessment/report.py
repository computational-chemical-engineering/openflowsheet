"""The assessment report and the §4.9 uncertainty pass (E01 design §4.2.1, §4.5.5, §4.9, §4.11).

`build_report(program, x, state_sha256=...)` evaluates the program at `x` on the float path and
returns a document valid against `schemas/assessment-report.schema.json`:

- every output, grouped by its catalogue entry (`capex`, `opex`, `annual`, `derived`, `lca`;
  sizes inside their item), keyed by its unprefixed id (§4.1). An output withheld by planning
  (`program.unavailable`), or undefined at `x`, is `null` (§4.9, A40);
- the regime (signature, sha256, and each entry with its admissibility rows' values at `x`);
- the contributors' sections (`basis`, `items`, `excluded`, `defaulted_inputs`, LCA `tables`);
- `uncertainty`: the AACE class over costed items (`none` when one is extrapolated or has no
  class) and the first-order propagation over every θ with a declared relative range — the
  document's `uncertainty` entry for a θ, else the θ's own (a set entry's or a quote's) — with
  each quantity labelled by its assumptions;
- `status` (`COMPLETE`, `PARTIAL`, `REFUSED`), the refusals, limitations and the statement.

`provenance` (versions, a timestamp) lies outside every hash: two evaluations of one program at
one state give byte-identical canonical reports without it (A39).
"""

from __future__ import annotations

import datetime
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Final

from openflowsheet import __version__
from openflowsheet.assessment.cost import uncertainty as aace
from openflowsheet.assessment.program import Linearization, Refusal, _feasibility_tolerance
from openflowsheet.assessment.quantities import classify
from openflowsheet.compile.casadi_backend import TwinEvaluationError, TwinMatrix

if TYPE_CHECKING:
    from openflowsheet.assessment.program import AssessmentProgram

__all__ = ["SCHEMA_REFERENCE", "SCHEMA_VERSION", "build_report", "propagate", "report_body"]

SCHEMA_REFERENCE: Final = "assessment-report.schema.json"
SCHEMA_VERSION: Final = "assessment-report-v1"

#: Catalogue entry → report group (§4.11). `size` lives in its item; `adm` in the regime.
_GROUP: Final = {
    "capex.purchased": "capex",
    "capex.bare_module": "capex",
    "capex.sum": "capex",
    "capex.step": "capex",
    "opex.total": "opex",
    "opex.utility": "opex",
    "opex.material": "opex",
    "opex.waste": "opex",
    "opex.fixed": "opex",
    "revenue.total": "annual",
    "revenue": "annual",
    "annual.capital_charge": "annual",
    "tac": "annual",
    "profit": "annual",
    "product.annual": "annual",
    "lcox": "annual",
    "inventory": "inventory",
    "impact": "impacts",
    "derived": "derived",
}


def _column(matrix: TwinMatrix, j: int) -> dict[int, float]:
    return {
        matrix.indices[k]: matrix.data[k] for k in range(matrix.indptr[j], matrix.indptr[j + 1])
    }


def propagate(
    program: AssessmentProgram,
    x: Mapping[str, float],
    values: Mapping[str, float],
    outputs: Sequence[str],
) -> tuple[dict[str, list[float]], dict[str, float], list[dict[str, Any]], list[Refusal]]:
    """§4.9's first-order propagation of `outputs` at `x`.

    Every θ with a declared relative range `[lo, hi]` is symbolic in one twin; `g_k = ∂y/∂θ_k·θ_k`.
    Returns the linear worst-case intervals, the RSS standard deviations, the parameters used
    (θ order) and the refusals: a declared range on a structural θ (`ASSESSMENT_PARAMETER_
    STRUCTURAL`) or on a θ the program does not have (`ASSESSMENT_VARIABLE_UNKNOWN`)."""
    declared = dict(program.context.spec.document.get("uncertainty", {}))
    refusals = [
        Refusal("ASSESSMENT_VARIABLE_UNKNOWN", name, "a declared range names no θ of the program")
        for name in sorted(declared)
        if name not in program.theta
    ]
    ranged: list[tuple[str, float, tuple[float, float]]] = []
    for theta_id, theta in program.theta.items():
        if theta_id in declared:
            lo, hi = declared[theta_id]["relative_range"]
            span: tuple[float, float] | None = (float(lo), float(hi))
        else:
            span = theta.relative_range
        if span is None:
            continue
        if theta.structural:
            refusals.append(
                Refusal("ASSESSMENT_PARAMETER_STRUCTURAL", theta_id, "a ranged θ selects a regime")
            )
            continue
        ranged.append((theta_id, theta.value, span))
    parameters = [{"theta": t, "value": v, "relative_range": list(span)} for t, v, span in ranged]
    if not ranged or not outputs:
        return {}, {}, parameters, refusals
    lin = program.linearize(x, {}, list(outputs), [t for t, _, _ in ranged])
    if isinstance(lin, Refusal):
        return {}, {}, parameters, [*refusals, lin]
    assert isinstance(lin, Linearization)
    columns = [_column(lin.d_dp, j) for j in range(len(ranged))]
    spans = [span for _, _, span in ranged]
    intervals: dict[str, list[float]] = {}
    sigmas: dict[str, float] = {}
    for i, output_id in enumerate(outputs):
        g = [
            column.get(i, 0.0) * value
            for column, (_, value, _) in zip(columns, ranged, strict=True)
        ]
        low, high = aace.worst_case(values[output_id], g, spans)
        intervals[output_id] = [low, high]
        sigmas[output_id] = aace.rss(g, spans)
    return intervals, sigmas, parameters, refusals


def _estimate_class(items: Sequence[Mapping[str, Any]]) -> int | None:
    """§4.9: the maximum class over costed items; `none` when one was extrapolated or carries no
    class (a quote without `accuracy_class`). Included drives and excluded items do not count."""
    costed = [i for i in items if i["status"] == "costed"]
    unknown = any(i["accuracy_class"] is None for i in costed)
    extrapolated = any(i["extrapolated"] for i in costed)
    return aace.estimate_class(
        (int(i["accuracy_class"]) for i in costed if i["accuracy_class"] is not None),
        extrapolated or unknown,
    )


def report_body(
    program: AssessmentProgram, x: Mapping[str, float], *, state_sha256: str, uncertainty: bool
) -> dict[str, Any]:
    """The report without `provenance` (the part A39 compares byte for byte)."""
    refusals: list[Refusal] = list(program.refusals)
    withheld: dict[str, str] = dict(program.unavailable)
    values: Mapping[str, float] | None
    try:
        evaluated = program.evaluate(x)
    except TwinEvaluationError as error:
        refusals.append(Refusal("ASSESSMENT_EVALUATION_FAILED", "", str(error)))
        values = None
    else:
        assert isinstance(evaluated, Mapping)
        values = evaluated
    if values is not None:
        tau = _feasibility_tolerance()
        violated = [n for n in program.admissibility_ids if values[n] < -tau]
        if violated:
            refusals.append(
                Refusal("ASSESSMENT_REGIME_INADMISSIBLE", ",".join(violated), f"tau_feas={tau}")
            )
            values = None
    plans = program.plans
    sections = {
        name: plan.section(values if values is not None else {})
        for name, plan in plans.items()
        if plan.section is not None and (values is not None or name != "derived")
    }
    derived = sections.get("derived", {})
    for output_id in derived.get("undefined", ()):
        refusals.append(Refusal("METRIC_UNDEFINED", output_id, "denominator ≤ 0 at the state"))
        withheld[output_id] = "non-positive denominator at the state"
    for output_id in derived.get("withheld", ()):
        withheld[output_id] = "depends on an undefined derived output"

    def value(output_id: str) -> float | None:
        if values is None or output_id in withheld:
            return None
        return float(values[output_id])

    reported = [n for n in program.output_ids if n not in program.admissibility_ids]
    groups: dict[str, dict[str, float | None]] = {
        g: {} for g in ("capex", "opex", "annual", "derived", "inventory", "impacts")
    }
    for output_id in sorted({*reported, *withheld}):
        catalogued = classify(output_id)
        assert catalogued is not None, output_id
        group = _GROUP.get(catalogued.name)
        if group is not None:
            groups[group][output_id] = value(output_id)
    cost = sections.get("cost", {})
    items: list[dict[str, Any]] = list(cost.get("items", ()))
    for item in items:
        item["size"] = {q: value(f"size.{item['item_id']}.{q}") for q in item["size"]}
        for key in ("purchased", "bare_module"):
            item[f"{key}_value"] = value(item[key]) if item[key] else None
    entries = []
    for entry in program.entries:
        rows = {
            row.row_id: value(f"adm.{entry.entry_id}.{row.row_id}") for row in entry.admissibility
        }
        entries.append(
            {
                "entry_id": entry.entry_id,
                "kind": entry.kind,
                "choice": entry.choice,
                "rule": entry.rule_text,
                "admissibility": rows,
            }
        )
    status_unc: dict[str, Any] = {
        "aace_class": None,
        "aace_range": None,
        "linear_interval": {},
        "rss_sigma": {},
        "parameters": [],
        "assumptions": {
            "linear_interval": aace.ASSUMPTIONS["worst_case"],
            "rss_sigma": aace.ASSUMPTIONS["rss"],
        },
    }
    klass = _estimate_class(items)
    status_unc["aace_class"] = klass
    if klass is not None:
        low, high = aace.AACE_RANGES[klass]
        status_unc["aace_range"] = {"low": list(low), "high": list(high)}
    if uncertainty and values is not None:
        targets = [n for n in reported if value(n) is not None]
        intervals, sigmas, parameters, more = propagate(program, x, values, targets)
        status_unc |= {"linear_interval": intervals, "rss_sigma": sigmas, "parameters": parameters}
        refusals.extend(more)
    built = [n for n in reported if value(n) is not None]
    if values is None or not built:
        status = "REFUSED"
    elif refusals or withheld:
        status = "PARTIAL"
    else:
        status = "COMPLETE"
    lca = sections.get("lca", {})
    defaulted = [d for s in sections.values() for d in s.get("defaulted_inputs", ())]
    return {
        "schema_version": SCHEMA_VERSION,
        "assessment_id": program.context.spec.assessment_id,
        "assessment_sha256": program.context.spec.assessment_sha256,
        "state_sha256": state_sha256,
        "regime": {
            "signature": program.regime.signature,
            "sha256": program.regime.sha256,
            "entries": entries,
        },
        "status": status,
        "basis": cost.get("basis", dict(program.context.spec.document["basis"])),
        "items": items,
        "capex": groups["capex"],
        "opex": groups["opex"],
        "annual": groups["annual"],
        "lca": {
            "inventory": _listed(program, groups["inventory"]),
            "impacts": _listed(program, groups["impacts"]),
            "tables": list(lca.get("tables", ())),
        },
        "derived": groups["derived"],
        "uncertainty": status_unc,
        "defaulted_inputs": defaulted,
        "limitations": [lim.as_document() for lim in program.limitations],
        "refusals": [r.as_document() for r in refusals],
        "unavailable": dict(sorted(withheld.items())),
        "excluded": list(cost.get("excluded", ())),
        "statement": aace.STATEMENT,
    }


def _listed(program: AssessmentProgram, group: Mapping[str, float | None]) -> list[dict[str, Any]]:
    return [
        {"id": output_id, "value": v, "unit": program.units.get(output_id)}
        for output_id, v in group.items()
    ]


def build_report(
    program: AssessmentProgram,
    x: Mapping[str, float],
    *,
    state_sha256: str,
    uncertainty: bool = True,
) -> dict[str, Any]:
    """The report at `x` (§4.11); `provenance` is outside every hash."""
    body = report_body(program, x, state_sha256=state_sha256, uncertainty=uncertainty)
    body["provenance"] = {
        "openflowsheet_version": __version__,
        "generated_utc": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        "program_label": program.label,
    }
    return body
