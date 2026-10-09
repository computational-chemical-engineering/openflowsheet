"""The model replacement check: blueprint §5.3's facets, run on a commit that changes a model
reference (M02 design note §6.2; ADR 0035 D2, D3; register R-228).

**When.** A change set that alters any instance's `model.{id, version, artifact_ref}` — an instance
id present before and after — where the old or the new model is variant-backed (`replacements`).
A change between two native models keeps v0.1's behaviour (R-228's watch-for), and an instance
added or removed is not a replacement.

**What.** `check_replacement` judges nine facets, each `pass`, `fail` or `not_applicable` with a
detail, from the old and the new revision (each bound afresh), their units' manifests, the
registered signatures' ports and, where a side is variant-backed, its variant:

- `resolvable`: the new model is in `MODEL_BUILDERS` and, if variant-backed, its variant
  resolves with the stated hash;
- `ports` (from the registered signatures): the same port names; per port equal kind, direction,
  multiplicity, state definition and component mapping; the new phase capabilities ⊇ the old;
- `components`: the manifests' `validity` components equal as ordered tuples;
- `conserved_quantities`: an equal multiset of (accumulation kind, holdup quantity, holdup
  dimension) over the declared equations that carry a holdup;
- `reference_states`: an equal property provider and reference convention;
- `boundary_condition`: both sides variant-backed — equal variant `boundary` blocks, `hard_domain`
  and `data_domain` excluded (they are `validity`'s); otherwise equal declared equation ids with
  equal dependencies, accumulation kind, dimension and conditional class;
- `degrees_of_freedom`: the new revision binds, is `STRUCTURALLY_CLOSED`, and the instance
  contributes as many rows and owned variables as before;
- `derivatives`: every (output, with respect to) the old manifest declares with an EO-capable
  method, the new one declares with an EO-capable method;
- `validity`: the new declared domain contains the old — the temperature and pressure intervals,
  the phases, and the variant hard domain (T, P, H2/N2, inerts, per-tube flow; an absent bound is
  unbounded, an absent inert floor is 0).

`synthetic` is reported, not judged (§6.2). A facet that needs a side that does not bind is
`not_applicable` with the binder's reason; `degrees_of_freedom` then fails, so the report is not
`compatible`. `FACETS` is the order of the report; M04 adds its own facet on its branch.
"""

from __future__ import annotations

import copy
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Final, Literal

from openflowsheet.adapters import variants
from openflowsheet.adapters.variants import Variant
from openflowsheet.application.binding import Unbound
from openflowsheet.application.revision_binding import (
    MODEL_BUILDERS,
    MODEL_SIGNATURES,
    RevisionBinding,
    bind_revision_flowsheet,
)
from openflowsheet.canonical import canonical_json
from openflowsheet.orchestrator.execution import EO_CAPABLE_METHODS

__all__ = [
    "FACETS",
    "REPORT_VERSION",
    "FacetResult",
    "ReplacementReport",
    "check_replacement",
    "check_replacements",
    "replacements",
    "variant_backed_models",
]

REPORT_VERSION: Final = "model-replacement-v1"
#: §6.2: the boundary block's members that `validity` judges, not `boundary_condition`.
DOMAIN_MEMBERS: Final = frozenset({"hard_domain", "data_domain"})
#: The variant hard domain's intervals.
HARD_INTERVALS: Final = ("T_K", "P_Pa", "H2_N2", "tube_flow_mol_s")
DETAIL_MAX: Final = 2048

FacetOutcome = Literal["pass", "fail", "not_applicable"]


@dataclass(frozen=True)
class FacetResult:
    facet: str
    result: FacetOutcome
    detail: str

    def as_document(self) -> dict[str, Any]:
        return {"facet": self.facet, "result": self.result, "detail": self.detail[:DETAIL_MAX]}


@dataclass(frozen=True)
class _Side:
    """One side of a replacement: the instance's model reference, its variant, and its unit as
    the side's revision binds it (`None` with the binder's reason when it does not)."""

    reference: Mapping[str, Any]
    backed: bool
    variant: Variant | None
    binding: RevisionBinding | None
    unbound: str | None
    unit: Any

    @property
    def manifest(self) -> Mapping[str, Any] | None:
        return None if self.unit is None else self.unit.manifest()

    def document(self) -> dict[str, Any]:
        """The report's `from` / `to`; a malformed value (a draft may hold any) as its canonical
        JSON text, so that the report says what the revision holds and stays schema-valid."""
        model_id, version, artifact_ref = (
            self.reference.get(key) for key in ("id", "version", "artifact_ref")
        )
        return {
            "id": _text(model_id),
            "version": None if version is None else _text(version),
            "artifact_ref": None if artifact_ref is None else _text(artifact_ref),
            "synthetic": bool(self.variant is not None and self.variant.synthetic),
        }


def _text(value: Any) -> str:
    return value if isinstance(value, str) else canonical_json(value).decode("utf-8")


@dataclass(frozen=True)
class ReplacementReport:
    """`model-replacement.schema.json`: one instance's replacement, judged."""

    instance_id: str
    old: Mapping[str, Any]
    new: Mapping[str, Any]
    facets: tuple[FacetResult, ...]

    @property
    def compatible(self) -> bool:
        return all(facet.result != "fail" for facet in self.facets)

    @property
    def failed(self) -> tuple[str, ...]:
        return tuple(facet.facet for facet in self.facets if facet.result == "fail")

    def as_document(self) -> dict[str, Any]:
        return {
            "schema_version": REPORT_VERSION,
            "instance_id": self.instance_id,
            "from": dict(self.old),
            "to": dict(self.new),
            "facets": [facet.as_document() for facet in self.facets],
            "compatible": self.compatible,
        }


def variant_backed_models() -> frozenset[str]:
    """The model ids a registered variant names (§6.1)."""
    return frozenset(variants.registered_variant(name).model_id for name in variants.registry())


def _instances(document: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    items = document.get("instances")
    if not isinstance(items, list):
        return {}
    return {
        str(item["id"]): item
        for item in items
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }


def _reference(instance: Mapping[str, Any]) -> dict[str, Any]:
    model = instance.get("model")
    if not isinstance(model, Mapping):
        return {"id": None, "version": None, "artifact_ref": None}
    return {key: model.get(key) for key in ("id", "version", "artifact_ref")}


def _backed(model_id: Any, backed: frozenset[str]) -> bool:
    """A model id names a variant-backed model; a document may hold any JSON value there."""
    return isinstance(model_id, str) and model_id in backed


def replacements(before: Mapping[str, Any], after: Mapping[str, Any]) -> tuple[str, ...]:
    """The instance ids whose model reference the change alters, where either side is
    variant-backed (§6.2), in instance-id order. Total over any document: a malformed reference
    is compared as the value it is."""
    old, new = _instances(before), _instances(after)
    backed = variant_backed_models()
    found = []
    for instance_id in sorted(set(old) & set(new)):
        left, right = _reference(old[instance_id]), _reference(new[instance_id])
        if left != right and (_backed(left["id"], backed) or _backed(right["id"], backed)):
            found.append(instance_id)
    return tuple(found)


def _side(
    document: Mapping[str, Any],
    instance_id: str,
    bound: RevisionBinding | Unbound,
    backed: frozenset[str],
) -> _Side:
    reference = _reference(_instances(document)[instance_id])
    model_id, version, artifact_ref = (reference[key] for key in ("id", "version", "artifact_ref"))
    is_backed = _backed(model_id, backed)
    variant = (
        variants.resolve(model_id, version, artifact_ref)
        if is_backed and isinstance(version, str) and isinstance(artifact_ref, str)
        else None
    )
    if isinstance(bound, Unbound):
        return _Side(reference, is_backed, variant, None, f"{bound.kind}({bound.detail})", None)
    units = [unit for unit in bound.flowsheet.instances if unit.unit_id == instance_id]
    return _Side(reference, is_backed, variant, bound, None, units[0] if units else None)


def _differences(old: Mapping[str, Any], new: Mapping[str, Any]) -> list[str]:
    return sorted(key for key in set(old) | set(new) if old.get(key) != new.get(key))


def _unavailable(facet: str, old: _Side, new: _Side) -> FacetResult | None:
    for name, side in (("old", old), ("new", new)):
        if side.unit is None:
            reason = side.unbound or "the instance is not in its binding"
            return FacetResult(
                facet, "not_applicable", f"the {name} revision does not bind: {reason}"
            )
    return None


# -- the facets -----------------------------------------------------------------------------------


def _resolvable(new: _Side) -> FacetResult:
    model_id = new.reference["id"]
    if not isinstance(model_id, str) or model_id not in MODEL_BUILDERS:
        return FacetResult("resolvable", "fail", f"{model_id!r} is not a registered model")
    if new.backed and new.variant is None:
        return FacetResult(
            "resolvable",
            "fail",
            f"variant {new.reference['version']!r} @ {new.reference['artifact_ref']!r} does not "
            f"resolve for {model_id!r} (model_variant_mismatch)",
        )
    what = f"variant {new.variant.variant_id}" if new.variant is not None else "a native model"
    return FacetResult("resolvable", "pass", f"{model_id} binds as {what}")


def _ports(old: _Side, new: _Side) -> FacetResult:
    left_signature = MODEL_SIGNATURES.get(str(old.reference["id"]))
    right_signature = MODEL_SIGNATURES.get(str(new.reference["id"]))
    if left_signature is None or right_signature is None:
        return FacetResult("ports", "not_applicable", "a side has no registered signature")
    left = {port.name: port for port in left_signature.ports}
    right = {port.name: port for port in right_signature.ports}
    if set(left) != set(right):
        return FacetResult("ports", "fail", f"port names {sorted(left)} -> {sorted(right)}")
    problems = []
    for name in sorted(left):
        a, b = left[name], right[name]
        for member in (
            "kind",
            "direction",
            "multiplicity",
            "state_definition",
            "component_mapping",
        ):
            if getattr(a, member) != getattr(b, member):
                problems.append(
                    f"{name}.{member}: {getattr(a, member)!r} -> {getattr(b, member)!r}"
                )
        lost = sorted(set(a.phase_capabilities) - set(b.phase_capabilities))
        if lost:
            problems.append(f"{name}.phase_capabilities: {lost} lost")
    if problems:
        return FacetResult("ports", "fail", "; ".join(problems))
    return FacetResult("ports", "pass", f"ports {sorted(left)} equal")


def _components(old: _Side, new: _Side) -> FacetResult:
    unavailable = _unavailable("components", old, new)
    if unavailable is not None:
        return unavailable
    assert old.manifest is not None and new.manifest is not None
    left = tuple(old.manifest["validity"]["domain"]["components"])
    right = tuple(new.manifest["validity"]["domain"]["components"])
    if left != right:
        return FacetResult("components", "fail", f"{list(left)} -> {list(right)}")
    return FacetResult("components", "pass", f"{list(left)}")


def _equations(manifest: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return list(manifest["mathematics"]["equations"])


def _conserved(manifest: Mapping[str, Any]) -> Counter[tuple[Any, ...]]:
    found: Counter[tuple[Any, ...]] = Counter()
    for equation in _equations(manifest):
        accumulation = equation["accumulation"]
        holdup = accumulation.get("holdup")
        if holdup is not None:
            found[(accumulation["kind"], holdup["quantity"], tuple(holdup["dimension"]))] += 1
    return found


def _conserved_quantities(old: _Side, new: _Side) -> FacetResult:
    unavailable = _unavailable("conserved_quantities", old, new)
    if unavailable is not None:
        return unavailable
    assert old.manifest is not None and new.manifest is not None
    left, right = _conserved(old.manifest), _conserved(new.manifest)
    if left != right:
        return FacetResult(
            "conserved_quantities",
            "fail",
            f"lost {sorted(map(str, left - right))}, gained {sorted(map(str, right - left))}",
        )
    return FacetResult(
        "conserved_quantities", "pass", f"{sum(left.values())} holdup balances, equal"
    )


def _reference_states(old: _Side, new: _Side) -> FacetResult:
    unavailable = _unavailable("reference_states", old, new)
    if unavailable is not None:
        return unavailable
    assert old.manifest is not None and new.manifest is not None
    names = ("property_provider", "reference_convention")
    left = {name: old.manifest["execution_requirements"].get(name) for name in names}
    right = {name: new.manifest["execution_requirements"].get(name) for name in names}
    if left != right:
        return FacetResult("reference_states", "fail", f"{left} -> {right}")
    return FacetResult(
        "reference_states", "pass", f"{left['property_provider']}, {left['reference_convention']}"
    )


def _equation_structure(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(equation["id"]): (
            tuple(equation["dependencies"]),
            equation["accumulation"]["kind"],
            tuple(equation["dimension"]),
            equation["conditional_class"],
        )
        for equation in _equations(manifest)
    }


def _boundary_condition(old: _Side, new: _Side) -> FacetResult:
    if old.variant is not None and new.variant is not None:
        left = {k: v for k, v in old.variant.boundary.items() if k not in DOMAIN_MEMBERS}
        right = {k: v for k, v in new.variant.boundary.items() if k not in DOMAIN_MEMBERS}
        differing = _differences(left, right)
        if differing:
            return FacetResult(
                "boundary_condition",
                "fail",
                "; ".join(f"boundary.{k}: {left.get(k)!r} -> {right.get(k)!r}" for k in differing),
            )
        return FacetResult(
            "boundary_condition", "pass", "the variants' boundary contracts are equal"
        )
    unavailable = _unavailable("boundary_condition", old, new)
    if unavailable is not None:
        return unavailable
    assert old.manifest is not None and new.manifest is not None
    left_rows, right_rows = _equation_structure(old.manifest), _equation_structure(new.manifest)
    differing = _differences(left_rows, right_rows)
    if differing:
        return FacetResult("boundary_condition", "fail", f"declared equations differ: {differing}")
    return FacetResult(
        "boundary_condition", "pass", f"{len(left_rows)} declared equations, equal in structure"
    )


def _contribution(side: _Side, instance_id: str) -> tuple[int, int]:
    """(rows, owned variables) the instance contributes to its side's binding."""
    assert side.binding is not None and side.unit is not None
    rows = sum(1 for unit in side.binding.row_units.values() if unit == instance_id)
    flowsheet = side.binding.flowsheet
    contribution = side.unit.contribute(flowsheet.wiring[instance_id], flowsheet.components)
    return rows, len(contribution.variable_ids)


def _degrees_of_freedom(
    old: _Side, new: _Side, instance_id: str, after: Mapping[str, Any]
) -> FacetResult:
    # `revision_run` imports this module's callers' layer; the route is read lazily.
    from openflowsheet.application.revision_run import Route, route_analysis, select_route

    if new.binding is None:
        return FacetResult(
            "degrees_of_freedom", "fail", f"the new revision does not bind: {new.unbound}"
        )
    route = select_route(after)
    if not isinstance(route, Route):
        return FacetResult("degrees_of_freedom", "fail", f"no route: {route.reason}")
    finding = route_analysis(route).finding
    if finding != "STRUCTURALLY_CLOSED":
        return FacetResult("degrees_of_freedom", "fail", f"the new revision is {finding}")
    if new.unit is None:
        return FacetResult("degrees_of_freedom", "fail", "the instance is not in the new binding")
    right = _contribution(new, instance_id)
    if old.binding is None or old.unit is None:
        return FacetResult(
            "degrees_of_freedom",
            "pass",
            f"STRUCTURALLY_CLOSED; {right[0]} rows, {right[1]} owned variables (the old "
            f"revision does not bind: {old.unbound})",
        )
    left = _contribution(old, instance_id)
    if left != right:
        return FacetResult(
            "degrees_of_freedom",
            "fail",
            f"rows, owned variables {left} -> {right}",
        )
    return FacetResult(
        "degrees_of_freedom",
        "pass",
        f"STRUCTURALLY_CLOSED; {right[0]} rows, {right[1]} owned variables, as before",
    )


def _eo_capable(manifest: Mapping[str, Any]) -> set[tuple[str, tuple[str, ...]]]:
    return {
        (str(entry["output"]), tuple(entry["with_respect_to"]))
        for entry in manifest["derivatives"]
        if entry["method"] in EO_CAPABLE_METHODS
    }


def _derivatives(old: _Side, new: _Side) -> FacetResult:
    unavailable = _unavailable("derivatives", old, new)
    if unavailable is not None:
        return unavailable
    assert old.manifest is not None and new.manifest is not None
    lost = sorted(_eo_capable(old.manifest) - _eo_capable(new.manifest))
    if lost:
        return FacetResult("derivatives", "fail", f"EO-capable derivatives lost: {lost}")
    return FacetResult(
        "derivatives", "pass", f"{len(_eo_capable(old.manifest))} EO-capable declarations kept"
    )


def _interval(domain: Mapping[str, Any], name: str) -> tuple[float, float] | None:
    bounds = domain.get(name)
    if not isinstance(bounds, Mapping):
        return None
    return float(bounds["min"]), float(bounds["max"])


def _contains(outer: Any, inner: Any) -> bool:
    """An interval `outer` contains `inner`; `None` is unbounded."""
    if outer is None:
        return True
    if inner is None:
        return False
    return float(outer[0]) <= float(inner[0]) and float(inner[1]) <= float(outer[1])


def _validity(old: _Side, new: _Side) -> FacetResult:
    unavailable = _unavailable("validity", old, new)
    if unavailable is not None:
        return unavailable
    assert old.manifest is not None and new.manifest is not None
    left = old.manifest["validity"]["domain"]
    right = new.manifest["validity"]["domain"]
    narrower: list[str] = []
    for name in ("temperature_K", "pressure_Pa"):
        if not _contains(_interval(right, name), _interval(left, name)):
            narrower.append(f"{name} {_interval(left, name)} -> {_interval(right, name)}")
    lost = sorted(set(left.get("phases", ())) - set(right.get("phases", ())))
    if lost:
        narrower.append(f"phases {lost} lost")
    old_hard = None if old.variant is None else old.variant.boundary["hard_domain"]
    new_hard = None if new.variant is None else new.variant.boundary["hard_domain"]
    if new_hard is not None:
        for name in HARD_INTERVALS:
            inner = None if old_hard is None else old_hard.get(name)
            if not _contains(new_hard.get(name), inner):
                narrower.append(f"hard_domain.{name} {inner} -> {new_hard.get(name)}")
        inner_max = None if old_hard is None else old_hard.get("inert_max")
        if inner_max is None or float(new_hard["inert_max"]) < float(inner_max):
            narrower.append(f"hard_domain.inert_max {inner_max} -> {new_hard['inert_max']}")
        # ADR 0027 Amendment 3: an absent inert floor is 0, and a higher floor is narrower.
        inner_min = None if old_hard is None else old_hard.get("inert_min")
        outer_min = new_hard.get("inert_min")
        if float(outer_min or 0.0) > float(inner_min or 0.0):
            narrower.append(f"hard_domain.inert_min {inner_min} -> {outer_min}")
    if narrower:
        return FacetResult(
            "validity", "fail", "the new domain does not contain the old: " + "; ".join(narrower)
        )
    return FacetResult("validity", "pass", "the new declared domain contains the old")


@dataclass(frozen=True)
class _Pair:
    """What a facet judges: the two sides, the instance and the new revision's document."""

    old: _Side
    new: _Side
    instance_id: str
    after: Mapping[str, Any]


#: The facets in the report's order, each a function of the pair. A later package's facet (M04's
#: surrogate evidence, on its branch) is one more row here and one more value in the schema's
#: `facet` enum; `FACETS` is this table's names.
FACET_CHECKS: Final[tuple[tuple[str, Callable[[_Pair], FacetResult]], ...]] = (
    ("resolvable", lambda pair: _resolvable(pair.new)),
    ("ports", lambda pair: _ports(pair.old, pair.new)),
    ("components", lambda pair: _components(pair.old, pair.new)),
    ("conserved_quantities", lambda pair: _conserved_quantities(pair.old, pair.new)),
    ("reference_states", lambda pair: _reference_states(pair.old, pair.new)),
    ("boundary_condition", lambda pair: _boundary_condition(pair.old, pair.new)),
    (
        "degrees_of_freedom",
        lambda pair: _degrees_of_freedom(pair.old, pair.new, pair.instance_id, pair.after),
    ),
    ("derivatives", lambda pair: _derivatives(pair.old, pair.new)),
    ("validity", lambda pair: _validity(pair.old, pair.new)),
)


#: §6.2's nine facets, in the report's order.
FACETS: Final[tuple[str, ...]] = tuple(name for name, _ in FACET_CHECKS)


def check_replacement(
    before: Mapping[str, Any], after: Mapping[str, Any], instance_id: str
) -> ReplacementReport:
    """§6.2's report for `instance_id` between the revisions `before` and `after`."""
    backed = variant_backed_models()
    old = _side(before, instance_id, bind_revision_flowsheet(copy.deepcopy(dict(before))), backed)
    new = _side(after, instance_id, bind_revision_flowsheet(copy.deepcopy(dict(after))), backed)
    pair = _Pair(old, new, instance_id, after)
    facets = tuple(check(pair) for _, check in FACET_CHECKS)
    assert tuple(facet.facet for facet in facets) == FACETS
    return ReplacementReport(instance_id, old.document(), new.document(), facets)


def check_replacements(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> tuple[ReplacementReport, ...]:
    """Every replacement `after` makes of `before` (`replacements`), judged."""
    return tuple(
        check_replacement(before, after, instance_id) for instance_id in replacements(before, after)
    )
