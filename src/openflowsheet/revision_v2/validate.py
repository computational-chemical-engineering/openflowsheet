"""The rules of a v2 revision a schema cannot state (ADR 0062 D3, D4, D9 to D11), as typed codes.

`validate(revision, context)` returns `(errors, notices)`, each sorted by code and then params
(UTF-8), duplicates dropped. The codes are ADR 0062's catalogue table and, for a structural
fault it names no code for, the existing catalogue's: `id_duplicate(id)`, `component_unknown
(component)`, `instance_missing(instance)`, `model_unsupported(instance, model)`,
`port_unsupported(instance, port)`, `connection_kind_unsupported(connection, port)`,
`port_direction_conflict(connection, port)`, `specification_target_unknown(specification)`, and
`schema_invalid(pointer)` for a rule of D3 or D11 the catalogue has no code for (a reference that
resolves to nothing, a reduced coefficient, one `mixed` substream, increasing grid edges; F2
decision WO4-4). A port is named `<instance>.<port>`.

`context` holds what the document refers to and does not contain: each component's facts (from
its record, ADR 0061), each attribute kind's payload (D5), each model's ports and manipulable
parameters (its manifest), the legacy providers and native conventions known, the components a
property method confines to a phase model (Q8.R7) and those it can form an equilibrium solid of
(Q8.R1). F2-WO6 builds it from the stores; tests build it by hand.

Notices are recorded limitations, not refusals: `species_basis_not_monotone(definition,
substream)` (Q3.R1 (iii)) and `molar_mass_inconsistent(definition, substream, species)` (Q3.R7,
the validation class, as the record service reports it).

`state_refusals` checks one material state of a laid-out connection (D4, Q3.R1 (iii), Q3.R4):
`attribute_on_zero_parent`, `group_amount_negative` and, for a feed, `feed_not_electroneutral`.
Energy and signal connections, probes and parameter sinks are validated here and refused at
binding (`construct_unavailable(<construct>, F6)`, D9), which is F2-WO6's.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Final

from openflowsheet.material.basis import check_basis, group_molar_masses
from openflowsheet.material.definitions import LEGACY_TEMPLATE, normalise_instance, species_basis
from openflowsheet.material.layout import (
    AttributeKind,
    ComponentFacts,
    ConnectionLayout,
    MaterialFacts,
    MaterialLayout,
    Slot,
    Vector,
    draft_connection,
)
from openflowsheet.registry.tokens import Coded
from openflowsheet.revision_v2.parse import RevisionV2

__all__ = [
    "CONVENTION_ELEMENTAL",
    "ELECTRONEUTRALITY_TOLERANCE",
    "ModelFacts",
    "PortFacts",
    "ValidationContext",
    "mixed_solid_candidates",
    "state_refusals",
    "validate",
]

#: D11: the convention every revision may name; a provider's native one comes from the context.
CONVENTION_ELEMENTAL: Final = "ELEMENTAL-ref-v1"
#: Q3.A4: a feed's charge residual |Σ ζ_g b_g| may be at most this times Σ |ζ_g| b_g.
ELECTRONEUTRALITY_TOLERANCE: Final = 1e-12
#: Amount kinds a `kg`-basis component refuses (Q7.R5: a molar input, `amount_basis_mismatch`).
_MOLAR_KINDS: Final = frozenset({"molar_flow", "segment_molar_flow"})
_ENERGY_KINDS: Final = {"heat-v1": "heat_rate", "work-v1": "power"}
_SOLID_KINDS: Final = frozenset({"solid", "nonconventional"})


@dataclass(frozen=True, slots=True)
class PortFacts:
    """One port of a model's manifest: its connection kind, direction, the definition templates
    it accepts (`nTP-v1`, `mat-v1`, `heat-v1`, `work-v1`, `signal-v1`) and, for a signal port,
    its quantity kind."""

    kind: str
    direction: str
    definitions: frozenset[str]
    quantity_kind: str | None = None


@dataclass(frozen=True, slots=True)
class ModelFacts:
    """What the validator reads of a model's manifest: its ports, its manipulable parameters
    (name -> quantity kind, D9) and whether it is a generic transport unit taking one definition
    on all its material ports (D11)."""

    ports: Mapping[str, PortFacts]
    manipulable: Mapping[str, str] = field(default_factory=dict)
    one_definition: bool = False


@dataclass(frozen=True, slots=True)
class ValidationContext:
    """What a v2 document refers to (see the module docstring), each by id."""

    components: Mapping[str, ComponentFacts]
    attribute_kinds: Mapping[str, AttributeKind]
    models: Mapping[str, ModelFacts]
    providers: frozenset[str] = frozenset()
    conventions: frozenset[str] = frozenset()
    confined: frozenset[str] = frozenset()
    solid_candidates: frozenset[str] = frozenset()


def mixed_solid_candidates(
    instance: Mapping[str, Any], candidates: Sequence[str]
) -> tuple[str, ...]:
    """Q8.R2 at the definition level (E-F2-8's Q8.A2): of a method's equilibrium-solid
    candidates (component ids, in its order), those `mixed` may form in a `mat-v1` instance: the
    `mixed` substream's components that no `solid` or `nonconventional` substream holds."""
    substreams = instance["substreams"]
    mixed = {c for s in substreams if s["kind"] == "mixed" for c in s["components"]}
    solid = {c for s in substreams if s["kind"] in _SOLID_KINDS for c in s["components"]}
    return tuple(c for c in candidates if c in mixed and c not in solid)


# -- helpers ------------------------------------------------------------------------------------


def _coded(code: str, **params: str) -> Coded:
    return Coded(code, params)


def _schema(pointer: str) -> Coded:
    return _coded("schema_invalid", pointer=pointer)


def _duplicates(ids: Sequence[str]) -> Iterator[Coded]:
    for ident, count in Counter(ids).items():
        if count > 1:
            yield _coded("id_duplicate", id=ident)


def _port_name(endpoint: Mapping[str, Any]) -> str:
    return f"{endpoint['instance']}.{endpoint['port']}"


class _Checker:
    """One validation pass; `errors` and `notices` collect as it goes."""

    def __init__(self, revision: RevisionV2, context: ValidationContext) -> None:
        self.document = revision.document
        self.revision = revision
        self.context = context
        self.errors: list[Coded] = []
        self.notices: list[Coded] = []
        self.components = revision.components
        self.definitions: dict[str, Mapping[str, Any]] = {
            d["id"]: d for d in self.document["materials"]["definitions"]
        }
        self.instances = {i["id"]: i for i in self.document["instances"]}
        self.connections = {c["id"]: c for c in self.document["connections"]}
        self.specifications = {s["id"]: s for s in self.document["specifications"]}
        self.reaction_sets = {r["id"]: r for r in self.document["reaction_sets"]}
        self.undrafted = False

    # -- ids, components, methods, conventions ---------------------------------------------

    def ids(self) -> None:
        d = self.document
        for listed in (
            self.components,
            [i["id"] for i in d["instances"]],
            [c["id"] for c in d["connections"]],
            [s["id"] for s in d["specifications"]],
            [m["id"] for m in d["materials"]["definitions"]],
            [r["id"] for r in d["reaction_sets"]],
        ):
            self.errors += _duplicates(listed)
        for reaction_set in d["reaction_sets"]:
            self.errors += _duplicates([r["id"] for r in reaction_set["reactions"]])
        for component in self.components:
            if component not in self.context.components:
                self.errors.append(_coded("component_unknown", component=component))
        for key in d["materials"].get("phase_order_keys", ()):
            if key not in self.components:
                self.errors.append(_coded("component_unknown", component=key))

    def methods(self) -> None:
        convention = self.document["convention"]
        if convention != CONVENTION_ELEMENTAL and convention not in self.context.conventions:
            self.errors.append(
                _coded(
                    "construct_unavailable", construct=f"convention:{convention}", foundation="F4"
                )
            )
        methods = self.document["property_methods"]
        default = methods["default"]
        if methods["overrides"] or not (
            isinstance(default, str) and default in self.context.providers
        ):
            self.errors.append(
                _coded("construct_unavailable", construct="property_methods", foundation="F4")
            )

    # -- reaction sets ------------------------------------------------------------------------

    def substream_components(self, substream: str) -> set[str]:
        return {
            c
            for d in self.definitions.values()
            for s in d["substreams"]
            if s["id"] == substream
            for c in s["components"]
        }

    def reactions(self) -> None:
        for i, reaction_set in enumerate(self.document["reaction_sets"]):
            for j, reaction in enumerate(reaction_set["reactions"]):
                at = f"/reaction_sets/{i}/reactions/{j}"
                scope = set()
                for k, substream in enumerate(reaction["scope"]):
                    found = self.substream_components(substream)
                    if not found:
                        self.errors.append(_schema(f"{at}/scope/{k}"))
                    scope |= found
                for component, (p, q) in reaction["stoichiometry"].items():
                    if component not in self.components:
                        self.errors.append(_coded("component_unknown", component=component))
                    elif math.gcd(p, q) != 1:
                        self.errors.append(_schema(f"{at}/stoichiometry/{component}"))
                    elif scope and component not in scope:
                        self.errors.append(_schema(f"{at}/stoichiometry/{component}"))

    def fast_reactions(self, name: str | None) -> list[dict[str, Fraction]] | None:
        if name is None:
            return []
        if name not in self.reaction_sets:
            return None
        return [
            {c: Fraction(p, q) for c, (p, q) in r["stoichiometry"].items()}
            for r in self.reaction_sets[name]["reactions"]
        ]

    # -- definitions (D3, D11) -----------------------------------------------------------------

    def definition_rules(self) -> None:
        coordinate = self.document["materials"]["thermal_coordinate"]
        placed: dict[tuple[str, str], list[str]] = {}
        for i, (name, definition) in enumerate(self.definitions.items()):
            at = f"/materials/definitions/{i}"
            if definition["thermal_coordinate"] != coordinate:
                self.errors.append(_coded("thermal_coordinate_mismatch", definition=name))
            substreams = definition["substreams"]
            self.errors += _duplicates([s["id"] for s in substreams])
            if sum(s["kind"] == "mixed" for s in substreams) > 1:
                self.errors.append(_schema(f"{at}/substreams"))
            for k, substream in enumerate(substreams):
                where = f"{at}/substreams/{k}"
                self.substream_rules(name, where, substream)
                for component in substream["components"]:
                    placed.setdefault((name, component), []).append(substream["kind"])
        for (_, component), kinds in placed.items():
            if len(kinds) > 1 and sorted(kinds) != ["mixed", "solid"]:
                self.errors.append(_coded("solid_role_conflict", component=component))
            if any(kind in _SOLID_KINDS for kind in kinds) and component in self.context.confined:
                self.errors.append(_coded("solid_role_conflict", component=component))

    def substream_rules(self, name: str, at: str, substream: Mapping[str, Any]) -> None:
        components: list[str] = substream["components"]
        known = [c for c in components if c in self.context.components]
        positions = [self.components.index(c) for c in components if c in self.components]
        for component in components:
            if component not in self.components:
                self.errors.append(_coded("component_unknown", component=component))
        if positions != sorted(positions):
            self.errors.append(_schema(f"{at}/components"))
        if substream["kind"] == "nonconventional":
            for component in known:
                if self.context.components[component].amount_basis != "kg":
                    self.errors.append(_coded("amount_basis_mismatch", component=component))
        grids = {}
        for g, grid in enumerate(substream["grids"]):
            edges = grid["edges"]
            if any(not left < right for left, right in zip(edges, edges[1:], strict=False)):
                self.errors.append(_schema(f"{at}/grids/{g}/edges"))
            grids[grid["id"]] = grid
        self.errors += _duplicates([grid["id"] for grid in substream["grids"]])
        group_basis = "groups" in substream["conserved_basis"]
        self.attribute_rules(name, at, substream, grids, group_basis)
        if group_basis and len(known) == len(components):
            self.basis_rules(name, at, substream)

    def attribute_rules(
        self,
        name: str,
        at: str,
        substream: Mapping[str, Any],
        grids: Mapping[str, Any],
        group_basis: bool,
    ) -> None:
        sid = substream["id"]
        components = set(substream["components"])
        seen: set[tuple[str, tuple[str, ...] | None]] = set()
        partitioned: set[str] = set()
        mixed = substream["kind"] == "mixed"
        equilibrium = self.context.confined | self.context.solid_candidates
        for a, attribute in enumerate(substream["attributes"]):
            where = f"{at}/attributes/{a}"
            kind_id: str = attribute["kind"]
            named = attribute["components"]
            params = {"definition": name, "substream": sid, "kind": kind_id}
            key = (kind_id, None if named is None else tuple(named))
            if key in seen:
                self.errors.append(Coded("attribute_redundant", params))
            seen.add(key)
            kind = self.context.attribute_kinds.get(kind_id)
            if kind is None:
                self.errors.append(_coded("capability_unknown", kind=kind_id))
                continue
            if (kind.scope == "component") != (named is not None):
                self.errors.append(_schema(f"{where}/components"))
            for component in named or ():
                if component not in components:
                    self.errors.append(_coded("component_unknown", component=component))
                elif mixed and component in equilibrium:
                    self.errors.append(_coded("solid_role_conflict", component=component))
            if kind.classed != (attribute["grid"] is not None) or (
                kind.classed and attribute["grid"] not in grids
            ):
                self.errors.append(Coded("attribute_grid_mismatch", params))
            if kind.partition:
                if group_basis:
                    self.errors.append(_schema(f"{where}/kind"))
                for component in named or ():
                    if component in partitioned:
                        self.errors.append(Coded("attribute_redundant", params))
                    partitioned.add(component)

    def basis_rules(self, name: str, at: str, substream: Mapping[str, Any]) -> None:
        sid = substream["id"]
        basis = substream["conserved_basis"]
        species = basis["species"]
        if set(species) != set(substream["components"]) or any(
            set(group["content"]) - set(species) for group in basis["groups"]
        ):
            self.errors.append(_schema(f"{at}/conserved_basis/species"))
            return
        reactions = self.fast_reactions(basis["fast_reactions"])
        if reactions is None:
            self.errors.append(_schema(f"{at}/conserved_basis/fast_reactions"))
            return
        params = {"definition": name, "substream": sid}
        charges = {c: self.context.components[c].charge for c in species}
        normal = normalise_instance({"substreams": [substream]})["substreams"][0]
        try:
            built = species_basis(normal, charges, reactions)
        except ValueError:
            self.errors.append(Coded("species_basis_incompatible", params))
            return
        check = check_basis(built)
        if not check.full_row_rank:
            self.errors.append(Coded("species_basis_redundant", params))
            return
        if not (check.reactions_conserve_groups and check.invariants_fixed):
            self.errors.append(Coded("species_basis_incompatible", params))
            return
        if not check.monotone:
            self.notices.append(Coded("species_basis_not_monotone", params))
        masses = [self.context.components[s].molar_mass for s in built.species]
        if all(mass is not None for mass in masses):
            known = [m or 0.0 for m in masses]
            for species_id in group_molar_masses(built, known).inconsistent:
                self.notices.append(
                    Coded("molar_mass_inconsistent", {**params, "species": species_id})
                )

    # -- connections (D9, D11) -------------------------------------------------------------------

    def template(self, connection: Mapping[str, Any]) -> str | None:
        name = connection["definition"]
        if connection["kind"] != "material" or name == LEGACY_TEMPLATE:
            return str(name)
        return "mat-v1" if name in self.definitions else None

    def port(self, connection: Mapping[str, Any], end: str) -> tuple[str, PortFacts] | None:
        """The port at `end` (`from`, `to`) of `connection`, its structural refusals reported."""
        endpoint = connection[end]
        instance = self.instances.get(endpoint["instance"])
        if instance is None:
            self.errors.append(_coded("instance_missing", instance=endpoint["instance"]))
            return None
        model = self.context.models.get(instance["model"]["id"])
        if model is None:
            return None
        port = model.ports.get(endpoint["port"])
        name = _port_name(endpoint)
        if port is None:
            self.errors.append(
                _coded("port_unsupported", instance=instance["id"], port=endpoint["port"])
            )
            return None
        if port.kind != connection["kind"]:
            self.errors.append(
                _coded("connection_kind_unsupported", connection=connection["id"], port=name)
            )
            return None
        if port.direction != ("outlet" if end == "from" else "inlet"):
            self.errors.append(
                _coded("port_direction_conflict", connection=connection["id"], port=name)
            )
        return name, port

    def connection_rules(self) -> None:
        for instance in self.instances.values():
            if instance["model"]["id"] not in self.context.models:
                self.errors.append(
                    _coded(
                        "model_unsupported", instance=instance["id"], model=instance["model"]["id"]
                    )
                )
        for c, connection in enumerate(self.document["connections"]):
            template = self.template(connection)
            if template is None:
                self.errors.append(_schema(f"/connections/{c}/definition"))
                continue
            for end in ("from", "to"):
                if "port" not in connection[end]:
                    continue
                found = self.port(connection, end)
                if found is None:
                    continue
                name, port = found
                cid = connection["id"]
                if template not in port.definitions:
                    self.errors.append(_coded("definition_incompatible", connection=cid, port=name))
                if (
                    connection["kind"] == "signal"
                    and port.quantity_kind != connection["quantity_kind"]
                ):
                    self.errors.append(_coded("signal_kind_mismatch", connection=cid))
                definition = self.definitions.get(connection["definition"])
                instance = connection[end]["instance"]
                model_id: str = self.instances[instance]["model"]["id"]
                if (
                    definition is not None
                    and definition["thermal_coordinate"] == "h_mass"
                    and not model_id.startswith("std.")
                ):
                    self.errors.append(
                        _coded(
                            "unit_coordinate_unsupported", instance=instance, coordinate="h_mass"
                        )
                    )
        self.one_definition_rules()

    def one_definition_rules(self) -> None:
        """D11: a generic transport unit takes one definition on all its material ports; two that
        differ only in grid edges are `attribute_grid_mismatch`, any other difference
        `definition_incompatible` (subset fill and declared maps are ADR-F6's)."""
        for instance in self.instances.values():
            model = self.context.models.get(instance["model"]["id"])
            if model is None or not model.one_definition:
                continue
            ends = [
                (connection, end)
                for connection in self.document["connections"]
                if connection["kind"] == "material"
                for end in ("from", "to")
                if connection[end].get("instance") == instance["id"]
            ]
            if not ends:
                continue
            first = ends[0][0]["definition"]
            for connection, end in ends[1:]:
                if connection["definition"] == first:
                    continue
                params = {"connection": connection["id"], "port": _port_name(connection[end])}
                same_but_grids = _without_edges(self.definitions.get(first)) == _without_edges(
                    self.definitions.get(connection["definition"])
                )
                code = "attribute_grid_mismatch" if same_but_grids else "definition_incompatible"
                self.errors.append(Coded(code, params))

    # -- targets, specifications, signal sinks (D9, D10) ------------------------------------

    def variables(self) -> dict[str, tuple[ConnectionLayout, Slot]]:
        """Every connection's variable ids, rendered from the layout's draft (never parsed)."""
        facts = MaterialFacts(
            self.components,
            {
                c: self.context.components[c]
                for c in self.components
                if c in self.context.components
            },
            self.context.attribute_kinds,
        )
        found: dict[str, tuple[ConnectionLayout, Slot]] = {}
        for given in self.revision.connection_inputs():
            try:
                draft = draft_connection(given, facts)
            except (KeyError, ValueError):
                # Its definition's refusal is reported by `definition_rules`; its ids are not
                # known, so an unresolved variable target is not reported on top (WO4-6).
                self.undrafted = True
                continue
            for slot in draft.slots:
                found[draft.variable_id(slot)] = (draft, slot)
        return found

    def target_kind(
        self, target: Mapping[str, Any], subject: Coded, variables: Mapping[str, Any]
    ) -> tuple[str | None, Slot | None]:
        """The quantity kind of a D10 target (`None` for v1's form, whose kinds v1 decides), and
        the slot of a variable target; `subject` is the refusal for a target that resolves to
        nothing."""
        if "variable" in target:
            if target["variable"] not in variables:
                if not self.undrafted:
                    self.errors.append(subject)
                return None, None
            slot = variables[target["variable"]][1]
            return slot.quantity_kind, slot
        if "derived" in target:
            construct = f"derived:{target['derived']}"
            self.errors.append(
                _coded("construct_unavailable", construct=construct, foundation="F4")
            )
            return None, None
        for form, kinds in (("energy", _ENERGY_KINDS), ("signal", None)):
            if form in target:
                connection = self.connections.get(target[form])
                if connection is None or connection["kind"] != form:
                    self.errors.append(subject)
                    return None, None
                if kinds is None:
                    return str(connection["quantity_kind"]), None
                return kinds[connection["definition"]], None
        object_id = target["object_id"]
        if target["object_type"] == "instance":
            known = object_id in self.instances
        else:
            connection = self.connections.get(object_id)
            known = connection is not None and connection["definition"] == LEGACY_TEMPLATE
        if not known:
            self.errors.append(subject)
        component = target.get("component")
        if component is not None and component not in self.components:
            self.errors.append(_coded("component_unknown", component=component))
        return None, None

    def specification_rules(self, variables: Mapping[str, Any]) -> None:
        for spec in self.document["specifications"]:
            sid = spec["id"]
            subject = _coded("specification_target_unknown", specification=sid)
            kind, slot = self.target_kind(spec["target"], subject, variables)
            if kind is None or kind == spec["kind"]:
                continue
            if (
                slot is not None
                and slot.quantity_kind == "mass_flow"
                and spec["kind"] in _MOLAR_KINDS
            ):
                # A `kg`-basis component's amount (D3, WO3-4: `n` of kind `mass_flow`), Q7.R5.
                self.errors.append(_coded("amount_basis_mismatch", component=str(slot.index[0])))
            else:
                self.errors.append(_coded("quantity_kind_mismatch", specification=sid))

    def signal_rules(self, variables: Mapping[str, Any]) -> None:
        bindings: Counter[str] = Counter()
        for spec in self.document["specifications"]:
            target = spec["target"]
            path = target.get("path", "")
            if target.get("object_type") == "instance" and path.startswith("parameters."):
                bindings[f"{target['object_id']}.{path.removeprefix('parameters.')}"] += 1
        for connection in self.document["connections"]:
            if connection["kind"] != "signal":
                continue
            cid, kind = connection["id"], connection["quantity_kind"]
            source, sink = connection["from"], connection["to"]
            if "probe" in source:
                subject = _coded("specification_target_unknown", specification=cid)
                found, _ = self.target_kind(source["probe"], subject, variables)
                if found is not None and found != kind:
                    self.errors.append(_coded("signal_kind_mismatch", connection=cid))
            if "parameter" in sink:
                instance = self.instances.get(sink["instance"])
                if instance is None:
                    self.errors.append(_coded("instance_missing", instance=sink["instance"]))
                    continue
                bindings[f"{sink['instance']}.{sink['parameter']}"] += 1
                model = self.context.models.get(instance["model"]["id"])
                if model is None:
                    continue
                manipulable = model.manipulable.get(sink["parameter"])
                if manipulable is None:
                    self.errors.append(
                        _coded(
                            "parameter_not_manipulable",
                            instance=sink["instance"],
                            parameter=sink["parameter"],
                        )
                    )
                elif manipulable != kind:
                    self.errors.append(_coded("signal_kind_mismatch", connection=cid))
            if "specification" in sink:
                spec = self.specifications.get(sink["specification"])
                if spec is None:
                    self.errors.append(
                        _coded("specification_target_unknown", specification=sink["specification"])
                    )
                    continue
                bindings[f"specification:{spec['id']}"] += 1
                if spec["kind"] != kind:
                    self.errors.append(_coded("signal_kind_mismatch", connection=cid))
        for target, count in bindings.items():
            if count > 1:
                self.errors.append(_coded("parameter_binding_conflict", target=target))


def _without_edges(definition: Mapping[str, Any] | None) -> Any:
    if definition is None:
        return None
    normal = normalise_instance({k: v for k, v in definition.items() if k != "id"})
    for substream in normal["substreams"]:
        for grid in substream["grids"]:
            grid["edges"] = None
    return normal


def _sorted(found: list[Coded]) -> tuple[Coded, ...]:
    unique = {(c.code, tuple(sorted(c.params.items()))): c for c in found}
    return tuple(sorted(unique.values(), key=Coded.sort_key))


def validate(
    revision: RevisionV2, context: ValidationContext
) -> tuple[tuple[Coded, ...], tuple[Coded, ...]]:
    """`(errors, notices)` of a parsed v2 revision against `context` (module docstring)."""
    checker = _Checker(revision, context)
    checker.ids()
    checker.methods()
    checker.reactions()
    checker.definition_rules()
    checker.connection_rules()
    variables = checker.variables()
    checker.specification_rules(variables)
    checker.signal_rules(variables)
    return _sorted(checker.errors), _sorted(checker.notices)


def state_refusals(
    revision: RevisionV2,
    context: ValidationContext,
    layout: MaterialLayout,
    x: Vector,
    connection: str,
    *,
    feed: bool = False,
) -> tuple[Coded, ...]:
    """The typed refusals of `connection`'s material state in `x` (`layout` built from
    `revision`): a non-zero attribute on a dormant parent (D4, Q6.R3: a component-scoped
    attribute's parent is its component's carried amounts, a substream-scoped one's the
    substream), a negative group amount (Q3.R1 (iii)), and for a feed a charge residual above
    `ELECTRONEUTRALITY_TOLERANCE` relative (Q3.R4, Q3.A4) where a charge row ζ exists."""
    placed = layout.connection(connection)
    given = next(g for g in revision.connection_inputs() if g.connection == connection)
    instance = normalise_instance(given.instance)
    definitions = {s["id"]: s for s in instance.get("substreams", ())}
    found: list[Coded] = []
    for substream in placed.substreams:
        sid = substream.substream
        carried = [
            (placed.slots[p], float(x[placed.slots[p].variable_index])) for p in substream.carried
        ]
        where = {"connection": connection, "substream": sid}
        for p in substream.attributes:
            slot = placed.slots[p]
            if float(x[slot.variable_index]) == 0.0:
                continue
            kind = str(slot.index[0])
            scoped = context.attribute_kinds[kind].scope == "component"
            parent = [v for s, v in carried if not scoped or s.index[0] == slot.index[1]]
            if all(v == 0.0 for v in parent):
                found.append(Coded("attribute_on_zero_parent", {**where, "kind": kind}))
        definition = definitions.get(sid)
        if definition is None:
            continue
        basis = definition["conserved_basis"]
        if "groups" in basis:
            for slot, value in carried:
                if value < 0.0:
                    found.append(
                        Coded("group_amount_negative", {**where, "group": str(slot.index[0])})
                    )
        if not feed:
            continue
        members = basis["species"] if "groups" in basis else definition["components"]
        charges = {c: context.components[c].charge for c in members}
        reactions = []
        if "groups" in basis and basis["fast_reactions"] is not None:
            sets = {r["id"]: r for r in revision.document["reaction_sets"]}
            reactions = [
                {c: Fraction(p, q) for c, (p, q) in r["stoichiometry"].items()}
                for r in sets[basis["fast_reactions"]]["reactions"]
            ]
        built = species_basis(definition, charges, reactions)
        row = check_basis(built).charge_row
        if row is None:
            continue
        zeta = dict(zip(built.groups, (float(z) for z in row), strict=True))
        residual = math.fsum(zeta[str(s.index[0])] * v for s, v in carried)
        scale = math.fsum(abs(zeta[str(s.index[0])]) * v for s, v in carried)
        if abs(residual) > ELECTRONEUTRALITY_TOLERANCE * scale:
            found.append(Coded("feed_not_electroneutral", where))
    return _sorted(found)
