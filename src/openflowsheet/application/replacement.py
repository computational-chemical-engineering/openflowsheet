"""The model replacement check: blueprint §5.3's facets, run on a commit that changes a model
reference (M02 design note §6.2; ADR 0035 D2, D3; register R-228), and its surrogate side (M04 spec
§8.3; ADR 0037 D3).

**When.** A change set that alters any instance's `model.{id, version, artifact_ref}` — an instance
id present before and after — where the old or the new model is variant-backed or surrogate-backed
(`replacements`). A change between two native models keeps v0.1's behaviour (R-228's watch-for),
and an instance added or removed is not a replacement.

**What.** `check_replacement` judges ten facets, each `pass`, `fail` or `not_applicable` with a
detail, from the old and the new revision (each bound afresh, surrogates resolved by the project's
resolver), their units' manifests, the registered signatures' ports and, where a side is
variant-backed, its variant; where it is surrogate-backed, its SurrogateManifest, whose `parent`
block stands in for the variant (its `boundary` the side's boundary block, its hard domain the
side's):

- `resolvable`: the new model is in `MODEL_BUILDERS` and, if variant-backed, its variant
  resolves with the stated hash; if surrogate-backed, its manifest resolves by hash and passes
  its checker;
- `ports` (from the registered signatures): the same port names; per port equal kind, direction,
  multiplicity, state definition and component mapping; the new phase capabilities ⊇ the old;
- `components`: the manifests' `validity` components equal as ordered tuples;
- `conserved_quantities`: an equal multiset of (accumulation kind, holdup quantity, holdup
  dimension) over the declared equations that carry a holdup;
- `reference_states`: an equal property provider and reference convention;
- `boundary_condition`: both sides with a boundary block (variant- or surrogate-backed) — equal
  `boundary` blocks, `hard_domain` and `data_domain` excluded (they are `validity`'s); otherwise
  equal declared equation ids with equal dependencies, accumulation kind, dimension and
  conditional class;
- `degrees_of_freedom`: the new revision binds, is `STRUCTURALLY_CLOSED`, and the instance
  contributes as many rows and owned variables as before;
- `derivatives`: every (output, with respect to) the old manifest declares with an EO-capable
  method, the new one declares with an EO-capable method — except that, when the new model is the
  old surrogate's parent exactly, what the parent declares `unavailable` is not a loss (detail
  `restores_parent_declaration`);
- `validity`: the new declared domain contains the old — the temperature and pressure intervals,
  the phases, and the hard domain (T, P, H2/N2, inerts, per-tube flow; an absent bound is
  unbounded, an absent inert floor is 0);
- `surrogate_evidence`: `not_applicable` unless a side is a surrogate. A new surrogate passes iff
  its verdict, re-derived from its stored metrics, is PROMOTABLE and the old model is its parent
  exactly or a surrogate of the same parent (details `verdict=<v>`, `parent_mismatch`); a new
  non-surrogate replacing a surrogate passes iff it is that surrogate's parent exactly (rollback),
  else fails `replace_via_parent`.

**Unchecked surrogates** (M04 spec §20 A3.1, register R-360). A surrogate-backed instance of the
new revision that no replacement judges — added, renamed, in the first revision, or carried over —
whose manifest resolves must re-derive PROMOTABLE; otherwise `unpromoted_surrogates` names it and
the commit is rejected (`surrogate_not_promoted(<instance>)`).

`synthetic` is reported, not judged (§6.2). A facet that needs a side that does not bind is
`not_applicable` with the binder's reason; `degrees_of_freedom` then fails, so the report is not
`compatible`. `FACETS` is the order of the report.
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
    SurrogateResolver,
    bind_revision_flowsheet,
    resolve_surrogate,
)
from openflowsheet.canonical import canonical_json
from openflowsheet.orchestrator.execution import EO_CAPABLE_METHODS
from openflowsheet.studies.surrogate import reactor as c1_surrogate
from openflowsheet.studies.surrogate.manifest import derived_verdict

__all__ = [
    "FACETS",
    "REPORT_VERSION",
    "SURROGATE_MODELS",
    "FacetResult",
    "ReplacementReport",
    "check_replacement",
    "check_replacements",
    "replacements",
    "unpromoted_surrogates",
    "variant_backed_models",
]

REPORT_VERSION: Final = "model-replacement-v1"
#: §6.2: the boundary block's members that `validity` judges, not `boundary_condition`.
DOMAIN_MEMBERS: Final = frozenset({"hard_domain", "data_domain"})
#: The variant hard domain's intervals.
HARD_INTERVALS: Final = ("T_K", "P_Pa", "H2_N2", "tube_flow_mol_s")
DETAIL_MAX: Final = 2048
#: The surrogate-backed model ids (M04 spec §8.3): pinned by a SurrogateManifest, not a variant.
SURROGATE_MODELS: Final = frozenset({c1_surrogate.MODEL_ID})
PROMOTABLE: Final = "PROMOTABLE"

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
    """One side of a replacement: the instance's model reference, its variant or its surrogate's
    manifest (M04 spec §8.3), and its unit as the side's revision binds it (`None` with the
    binder's reason when it does not)."""

    reference: Mapping[str, Any]
    backed: bool
    variant: Variant | None
    binding: RevisionBinding | None
    unbound: str | None
    unit: Any
    surrogate_backed: bool = False
    #: The resolved and checked SurrogateManifest; `None` when not surrogate-backed or unresolved.
    surrogate: Mapping[str, Any] | None = None

    @property
    def manifest(self) -> Mapping[str, Any] | None:
        return None if self.unit is None else self.unit.manifest()

    @property
    def key(self) -> tuple[Any, Any, Any]:
        """(id, version, artifact_ref): what "exactly" compares (spec §8.3)."""
        return self.reference["id"], self.reference["version"], self.reference["artifact_ref"]

    @property
    def parent(self) -> tuple[Any, Any, Any] | None:
        """A resolved surrogate's parent as a reference key (model id, variant id, SHA-256)."""
        if self.surrogate is None:
            return None
        block = self.surrogate["parent"]
        return block["model_id"], block["variant_id"], block["variant_sha256"]

    @property
    def boundary(self) -> Mapping[str, Any] | None:
        """The variant's `boundary` block, or a surrogate's verbatim copy of its parent's."""
        if self.variant is not None:
            return self.variant.boundary
        if self.surrogate is None:
            return None
        copied: Mapping[str, Any] = self.surrogate["parent"]["boundary"]
        return copied

    @property
    def hard_domain(self) -> Mapping[str, Any] | None:
        """The variant's hard domain, or a surrogate manifest's (= its parent's)."""
        if self.variant is not None:
            declared: Mapping[str, Any] = self.variant.boundary["hard_domain"]
            return declared
        if self.surrogate is None:
            return None
        hard: Mapping[str, Any] = self.surrogate["domain"]["hard"]
        return hard

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
            "synthetic": bool(
                (self.variant is not None and self.variant.synthetic)
                or (self.surrogate is not None and self.surrogate["synthetic"])
            ),
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
    variant-backed (§6.2) or surrogate-backed (M04 spec §8.3), in instance-id order. Total over
    any document: a malformed reference is compared as the value it is."""
    old, new = _instances(before), _instances(after)
    backed = variant_backed_models() | SURROGATE_MODELS
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
    surrogates: SurrogateResolver | None,
) -> _Side:
    reference = _reference(_instances(document)[instance_id])
    model_id, version, artifact_ref = (reference[key] for key in ("id", "version", "artifact_ref"))
    is_backed = _backed(model_id, backed)
    pinned = isinstance(version, str) and isinstance(artifact_ref, str)
    variant = variants.resolve(model_id, version, artifact_ref) if is_backed and pinned else None
    surrogate_backed = _backed(model_id, SURROGATE_MODELS)
    surrogate = None
    if surrogate_backed and pinned:
        surrogate = resolve_surrogate(version, artifact_ref, surrogates)
    found = (surrogate_backed, surrogate)
    if isinstance(bound, Unbound):
        reason = f"{bound.kind}({bound.detail})"
        return _Side(reference, is_backed, variant, None, reason, None, *found)
    units = [unit for unit in bound.flowsheet.instances if unit.unit_id == instance_id]
    return _Side(reference, is_backed, variant, bound, None, units[0] if units else None, *found)


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
    if new.surrogate_backed and new.surrogate is None:
        return FacetResult(
            "resolvable",
            "fail",
            f"surrogate {new.reference['version']!r} @ {new.reference['artifact_ref']!r} does not "
            f"resolve to a manifest that passes its checker (surrogate_manifest_mismatch)",
        )
    if new.variant is not None:
        what = f"variant {new.variant.variant_id}"
    elif new.surrogate is not None:
        what = f"surrogate {new.surrogate['surrogate_id']}"
    else:
        what = "a native model"
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
    if old.boundary is not None and new.boundary is not None:
        left = {k: v for k, v in old.boundary.items() if k not in DOMAIN_MEMBERS}
        right = {k: v for k, v in new.boundary.items() if k not in DOMAIN_MEMBERS}
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
    old: _Side,
    new: _Side,
    instance_id: str,
    after: Mapping[str, Any],
    surrogates: SurrogateResolver | None = None,
) -> FacetResult:
    # `revision_run` imports this module's callers' layer; the route is read lazily.
    from openflowsheet.application.revision_run import Route, route_analysis, select_route

    if new.binding is None:
        return FacetResult(
            "degrees_of_freedom", "fail", f"the new revision does not bind: {new.unbound}"
        )
    route = select_route(after, surrogates=surrogates)
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


def _declared_unavailable(manifest: Mapping[str, Any]) -> set[tuple[str, tuple[str, ...]]]:
    return {
        (str(entry["output"]), tuple(entry["with_respect_to"]))
        for entry in manifest["derivatives"]
        if entry["method"] == "unavailable"
    }


def _derivatives(old: _Side, new: _Side) -> FacetResult:
    unavailable = _unavailable("derivatives", old, new)
    if unavailable is not None:
        return unavailable
    assert old.manifest is not None and new.manifest is not None
    lost = sorted(_eo_capable(old.manifest) - _eo_capable(new.manifest))
    # M04 spec §8.3 (ADR 0037 D3): back to the old surrogate's own parent, what the parent
    # declares `unavailable` (its outlet w.r.t. inlet) is its declaration restored, not a loss.
    restored = []
    if lost and old.parent is not None and new.key == old.parent:
        declared = _declared_unavailable(new.manifest)
        restored = [entry for entry in lost if entry in declared]
        lost = [entry for entry in lost if entry not in declared]
    if lost:
        return FacetResult("derivatives", "fail", f"EO-capable derivatives lost: {lost}")
    if restored:
        return FacetResult(
            "derivatives",
            "pass",
            f"restores_parent_declaration: the parent declares {restored} unavailable",
        )
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
    old_hard, new_hard = old.hard_domain, new.hard_domain
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


def _named(key: tuple[Any, Any, Any] | None) -> str:
    if key is None:
        return "unknown (the manifest does not resolve)"
    model_id, version, artifact_ref = key
    return f"{model_id} {version} @ {artifact_ref}"


def _surrogate_evidence(old: _Side, new: _Side) -> FacetResult:
    """M04 spec §8.3's new facet. Promotion: the new surrogate's verdict re-derived from its
    stored metrics (`derived_verdict`, never `promotion.verdict`), and its parent the old model or
    the old surrogate's parent; the detail always states the verdict, then any mismatch, so both
    reasons are reported when both hold. Rollback: the new model is the old surrogate's parent."""
    if not (old.surrogate_backed or new.surrogate_backed):
        return FacetResult("surrogate_evidence", "not_applicable", "neither side is a surrogate")
    if new.surrogate_backed:
        if new.surrogate is None:
            return FacetResult(
                "surrogate_evidence",
                "fail",
                "the new surrogate's manifest does not resolve (surrogate_manifest_mismatch)",
            )
        verdict = derived_verdict(new.surrogate).verdict
        parent = new.parent
        if old.key == parent:
            relation = f"the old model is its parent {_named(parent)}"
        elif old.parent is not None and old.parent == parent:
            relation = f"the old model is a surrogate of the same parent {_named(parent)}"
        else:
            relation = None
        reasons = [f"verdict={verdict}"]
        if relation is None:
            reasons.append(
                f"parent_mismatch: the old model {_named(old.key)} is neither its parent "
                f"{_named(parent)} nor a surrogate of it (old surrogate's parent "
                f"{_named(old.parent) if old.surrogate_backed else 'n/a'})"
            )
        else:
            reasons.append(relation)
        result: FacetOutcome = "pass" if verdict == PROMOTABLE and relation is not None else "fail"
        return FacetResult("surrogate_evidence", result, "; ".join(reasons))
    if old.parent is not None and new.key == old.parent:
        return FacetResult(
            "surrogate_evidence",
            "pass",
            f"rollback to the old surrogate's parent {_named(old.parent)}",
        )
    return FacetResult(
        "surrogate_evidence",
        "fail",
        f"replace_via_parent: the new model {_named(new.key)} is not the old surrogate's parent "
        f"{_named(old.parent)}",
    )


@dataclass(frozen=True)
class _Pair:
    """What a facet judges: the two sides, the instance, the new revision's document and the
    project's SurrogateManifest resolver."""

    old: _Side
    new: _Side
    instance_id: str
    after: Mapping[str, Any]
    surrogates: SurrogateResolver | None = None


#: The facets in the report's order, each a function of the pair: ADR 0035's nine, then M04's
#: `surrogate_evidence` (spec §8.3); the schema's `facet` enum is this table's names (`FACETS`).
FACET_CHECKS: Final[tuple[tuple[str, Callable[[_Pair], FacetResult]], ...]] = (
    ("resolvable", lambda pair: _resolvable(pair.new)),
    ("ports", lambda pair: _ports(pair.old, pair.new)),
    ("components", lambda pair: _components(pair.old, pair.new)),
    ("conserved_quantities", lambda pair: _conserved_quantities(pair.old, pair.new)),
    ("reference_states", lambda pair: _reference_states(pair.old, pair.new)),
    ("boundary_condition", lambda pair: _boundary_condition(pair.old, pair.new)),
    (
        "degrees_of_freedom",
        lambda pair: _degrees_of_freedom(
            pair.old, pair.new, pair.instance_id, pair.after, pair.surrogates
        ),
    ),
    ("derivatives", lambda pair: _derivatives(pair.old, pair.new)),
    ("validity", lambda pair: _validity(pair.old, pair.new)),
    ("surrogate_evidence", lambda pair: _surrogate_evidence(pair.old, pair.new)),
)


#: §6.2's nine facets and M04's tenth, in the report's order.
FACETS: Final[tuple[str, ...]] = tuple(name for name, _ in FACET_CHECKS)


def check_replacement(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    instance_id: str,
    *,
    surrogates: SurrogateResolver | None = None,
) -> ReplacementReport:
    """§6.2's report for `instance_id` between the revisions `before` and `after`; `surrogates`
    is the project's SurrogateManifest resolver (M04 spec §8.2), which both bindings and a
    surrogate side's facets read. Without one a surrogate side does not resolve."""
    backed = variant_backed_models()

    def side(document: Mapping[str, Any]) -> _Side:
        bound = bind_revision_flowsheet(copy.deepcopy(dict(document)), surrogates=surrogates)
        return _side(document, instance_id, bound, backed, surrogates)

    old, new = side(before), side(after)
    pair = _Pair(old, new, instance_id, after, surrogates)
    facets = tuple(check(pair) for _, check in FACET_CHECKS)
    assert tuple(facet.facet for facet in facets) == FACETS
    return ReplacementReport(instance_id, old.document(), new.document(), facets)


def check_replacements(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    surrogates: SurrogateResolver | None = None,
) -> tuple[ReplacementReport, ...]:
    """Every replacement `after` makes of `before` (`replacements`), judged."""
    return tuple(
        check_replacement(before, after, instance_id, surrogates=surrogates)
        for instance_id in replacements(before, after)
    )


def unpromoted_surrogates(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    surrogates: SurrogateResolver | None = None,
) -> tuple[tuple[str, str], ...]:
    """M04 spec §20 A3.1 (R-360): each surrogate-backed instance of `after` that no replacement
    judges (`replacements`) and whose manifest re-derives a verdict other than PROMOTABLE
    (`derived_verdict`), as (instance id, detail), in instance-id order. A judged instance's
    promotion is `surrogate_evidence`'s; an unresolved manifest is the binder's
    (`surrogate_manifest_mismatch`)."""
    judged = set(replacements(before, after))
    found = []
    for instance_id, instance in sorted(_instances(after).items()):
        reference = _reference(instance)
        if instance_id in judged or not _backed(reference["id"], SURROGATE_MODELS):
            continue
        version, artifact_ref = reference["version"], reference["artifact_ref"]
        manifest = None
        if isinstance(version, str) and isinstance(artifact_ref, str):
            manifest = resolve_surrogate(version, artifact_ref, surrogates)
        if manifest is None:
            continue
        verdict = derived_verdict(manifest).verdict
        if verdict != PROMOTABLE:
            found.append((instance_id, f"verdict={verdict}"))
    return tuple(found)
