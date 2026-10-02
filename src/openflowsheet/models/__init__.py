"""Model and property contracts layer.

Owns unit-operation equations and evaluators, state definitions, validity domains, derivative
declarations, and initialization recipes (blueprint §3 layer table, §5). A model declares what
it can differentiate and where it is valid; capability absence is an explicit result, never an
invented derivative. It must not own the global solve strategy, undeclared mutations of shared
state, or permission decisions.

The contract below is introduced by package K02, together with the six SYN-001 units in
`models.syn001`.

**A unit model has two faces, and it owes both.** Blueprint §5.1 says a native equation model
"contributes residuals and inspectable equations to an EO system" and "may also supply a causal
evaluator and local initializer". For SYN-001 both are obligations, not options:

- the *declaration* — ports, equations and their accumulation kinds — is fixed normatively by
  ADR 0008 D3.5 and by the six manifests P01 wrote, and ADR 0008 D4.3 names K02's residual
  explicitly and gives two of its values exactly;
- the *evaluator* is what plan §4.2's acceptance evidence exercises (nominal, single-phase,
  zero-flow, cache on/off, perturbed input), and the mixer's enthalpy closure is an inner
  bracketed solve that has no residual form in v0.0 at all.

Keeping them in one object is the point: `manifest()` and `contribute()` are checked against each
other, so a row that no manifest declares, or a declared equation that contributes no row, is a
test failure rather than a discrepancy nobody looks for.

**Variable and row naming is a convention, and conventions get permuted.** Every id is built by
the helpers below rather than by f-strings at the call sites, so there is exactly one place where
`"S2.n.A"` is spelled and exactly one place a test has to pin.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Protocol

from openflowsheet.compile.spec import (
    EquationSpec,
    ProblemSpec,
    PropertyBlock,
    QuantityKind,
)
from openflowsheet.compiled import EvaluationContext, PhaseSignature, RowAccumulation
from openflowsheet.thermo import PropertyStatus, StreamState

if TYPE_CHECKING:
    from openflowsheet.models.syn001.ph_kernel import PHState

__all__ = [
    "assemble",
    "stream_variable_kinds",
    "stream_variables",
    "DerivativeDeclaration",
    "IMPLEMENTED_VERSION",
    "Initialization",
    "Validity",
    "manifest_document",
    "Accumulation",
    "Contribution",
    "DeclaredEquation",
    "Holdup",
    "Port",
    "SpecificationError",
    "UnitEvaluation",
    "UnitModel",
    "Wiring",
    "duty_id",
    "flow_id",
    "origin",
    "pressure_id",
    "row_id",
    "temperature_id",
]

PortKind = Literal["material", "energy", "signal"]
PortDirection = Literal["inlet", "outlet"]
#: The manifest's phase vocabulary, which is lowercase and includes `vapor_liquid` and
#: `zero_flow`. It is deliberately *not* `thermo.Phase`: that one names a phase a property can be
#: evaluated in, and `vapor_liquid` is not one of those.
PhaseCapability = Literal["liquid", "vapor", "vapor_liquid"]
ConditionalClass = Literal["unconditional", "phase_conditional", "regime_conditional"]

#: Seven SI base-dimension exponents in the order the `Quantity` schema fixes.
Dimension = tuple[int, int, int, int, int, int, int]


class SpecificationError(ValueError):
    """A unit was asked for something that is not a model failure but a malformed problem.

    Raised at construction, never returned as a status. ADR 0001 D4.4 requires a heater given both
    an outlet temperature and a duty to be "rejected at validation as a structural conflict"; the
    derivation §5 requires a splitter at `r = 1` to be "rejected rather than clipped". Neither is a
    state at which the model has a typed answer, so neither may travel as a `UnitEvaluation`.
    """


# --------------------------------------------------------------------------------------- naming


def flow_id(stream: str, component: str) -> str:
    """The free variable holding one component's molar flow in one stream, mol/s."""
    return f"{stream}.n.{component}"


def temperature_id(stream: str) -> str:
    return f"{stream}.T"


def pressure_id(stream: str) -> str:
    return f"{stream}.P"


def duty_id(unit: str) -> str:
    """The free variable holding a unit's duty, W, positive into the unit (ADR 0001 D4.1)."""
    return f"{unit}.Q"


def row_id(unit: str, equation: str, *suffix: str) -> str:
    """The id of one assembled residual row.

    A manifest declares an equation *family* — `HEAT-mole` is "for every component i" — and the
    assembled system has one row per component. The suffix carries the index, so the family is
    still legible in a row id and `origin` still points at the declaration.
    """
    return ":".join((unit, equation, *suffix))


def origin(model_id: str, equation_id: str) -> str:
    """`EquationSpec.origin` for a row: which manifest equation authored it.

    This is the link ADR 0008 D4.4 needs. A row whose origin names no declared equation, or a
    declared unconditional equation that authors no row, is caught by
    `tests/test_k02_unit_models.py` rather than discovered when a Jacobian entry cannot be traced.
    """
    return f"{model_id}#{equation_id}"


# -------------------------------------------------------------------------------- declarations


@dataclass(frozen=True)
class Holdup:
    """What a `holdup_balance` row accumulates (ADR 0008 D3)."""

    symbol: str
    quantity: str
    dimension: Dimension

    def as_document(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "dimension": list(self.dimension),
        }


@dataclass(frozen=True)
class Accumulation:
    """ADR 0008 D3: every equation says what it conserves. There is no default.

    The invariants the schema states are re-checked here, in code, because a manifest is validated
    against the schema only when it is serialized and a row is built long before that.
    """

    kind: RowAccumulation
    #: Required when `kind == "zero_holdup_balance"`: *why* the holdup is identically zero.
    reason: str = ""
    #: Required when `kind == "holdup_balance"`.
    holdup: Holdup | None = None

    def __post_init__(self) -> None:
        if self.kind == "absent":
            raise ValueError(
                "a declared equation is never 'absent'. ADR 0008 D4.4 reserves that for a row "
                "from an opaque evaluator; a model that declares the row knows what it is"
            )
        if self.kind == "zero_holdup_balance" and not self.reason:
            raise ValueError(
                "zero_holdup_balance requires a reason: the claim is that the holdup is zero by "
                "the model's definition, and an unstated reason cannot be reviewed"
            )
        if self.kind == "holdup_balance" and self.holdup is None:
            raise ValueError("holdup_balance must name the accumulated quantity")
        if self.kind != "holdup_balance" and self.holdup is not None:
            raise ValueError(f"{self.kind} must not name a holdup")
        if self.kind != "zero_holdup_balance" and self.reason:
            raise ValueError(f"{self.kind} carries no reason field in the manifest schema")

    @property
    def is_balance(self) -> bool:
        """Whether ADR 0008 D4.3's sign rule applies to rows built from this declaration."""
        return self.kind in ("holdup_balance", "zero_holdup_balance")

    def as_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {"kind": self.kind}
        if self.kind == "zero_holdup_balance":
            document["reason"] = self.reason
        if self.holdup is not None:
            document["holdup"] = self.holdup.as_document()
        return document


@dataclass(frozen=True)
class DeclaredEquation:
    """One entry of `ModelManifest.mathematics.equations`."""

    equation_id: str
    statement: str
    dependencies: tuple[str, ...]
    conditional_class: ConditionalClass
    accumulation: Accumulation
    #: The schema requires a dimension on every balance row and permits one elsewhere.
    dimension: Dimension | None = None
    source: str = ""

    def __post_init__(self) -> None:
        if self.accumulation.is_balance and self.dimension is None:
            raise ValueError(
                f"{self.equation_id}: the manifest schema requires a dimension on a balance row, "
                "because a conserved quantity without units cannot be checked against a holdup"
            )

    def as_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "id": self.equation_id,
            "statement": self.statement,
            "dependencies": list(self.dependencies),
            "conditional_class": self.conditional_class,
            "accumulation": self.accumulation.as_document(),
        }
        if self.dimension is not None:
            document["dimension"] = list(self.dimension)
        if self.source:
            document["source"] = self.source
        return document


@dataclass(frozen=True)
class Port:
    """One connection point. Mirrors `ModelManifest.ports`."""

    name: str
    kind: PortKind
    direction: PortDirection
    multiplicity: int | Literal["many"]
    component_mapping: Literal["revision_component_set"] | tuple[str, ...] | None
    state_definition: Literal["nTP-v1"] | None
    phase_capabilities: tuple[PhaseCapability, ...]

    def as_document(self) -> dict[str, Any]:
        mapping: Any = self.component_mapping
        if isinstance(mapping, tuple):
            mapping = list(mapping)
        return {
            "name": self.name,
            "kind": self.kind,
            "direction": self.direction,
            "multiplicity": self.multiplicity,
            "component_mapping": mapping,
            "state_definition": self.state_definition,
            "phase_capabilities": list(self.phase_capabilities),
        }


# ------------------------------------------------------------------------------- contributions


@dataclass(frozen=True)
class Wiring:
    """Which streams are connected to which ports of one unit instance.

    A port with `multiplicity: many` may carry several stream ids; every other port carries
    exactly one. The unit checks that, because a mixer silently wired to one inlet still produces
    a plausible number.
    """

    streams: Mapping[str, tuple[str, ...]]

    def one(self, port: str) -> str:
        connected = self.streams.get(port, ())
        if len(connected) != 1:
            raise SpecificationError(
                f"port {port!r} takes exactly one stream, got {len(connected)}: {list(connected)}"
            )
        return connected[0]

    def many(self, port: str) -> tuple[str, ...]:
        connected = tuple(self.streams.get(port, ()))
        if not connected:
            raise SpecificationError(f"port {port!r} has no stream connected")
        return connected


@dataclass(frozen=True)
class Contribution:
    """What one unit instance adds to a `ProblemSpec`.

    `variable_ids` names only what the unit *owns* — its duty. Stream variables belong to the
    flowsheet, because two units share every internal stream and neither may claim it.
    """

    variable_ids: tuple[str, ...] = ()
    equations: tuple[EquationSpec, ...] = ()
    blocks: tuple[PropertyBlock, ...] = ()
    block_inputs: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    parameter_ids: tuple[str, ...] = ()
    parameters: Mapping[str, float] = field(default_factory=dict)
    column_scales: Mapping[str, float] = field(default_factory=dict)
    row_scales: Mapping[str, float] = field(default_factory=dict)
    #: The physical kind of every variable this unit owns and every row it authors. Declared, not
    #: inferred: K03 turns these into scales from the registered nominals, and a missing kind is
    #: a refusal to build a plan rather than a silent 1.0 (K03 spec §4.3).
    variable_kinds: Mapping[str, QuantityKind] = field(default_factory=dict)
    row_kinds: Mapping[str, QuantityKind] = field(default_factory=dict)


@dataclass(frozen=True)
class UnitEvaluation:
    """The causal evaluator's answer: outlet states, duty, and what was actually solved.

    `duty` is `None` where the unit has no energy port at all, and `0.0` where it has one and the
    duty is exactly zero — a dormant inlet, for instance (ADR 0001 D3.4). Those are different
    answers and the type keeps them apart.

    On any status other than `ok`, `outlets` is empty and `duty` is `None`. A partial answer that
    looks like a result is the placeholder success path this project forbids.

    `work`, `extent` and `transferred_duty` are T05's (spec F6): the shaft work into a machine, a
    reactor's extent, and the heat an exchanger moves from its hot to its cold side. Like `duty`,
    each is `None` where the unit has no such quantity, and `None` on any status other than `ok`.
    No K02 unit sets them.

    `closure` is T05b's (spec §6.4, ADR 0012 D5 and D10 F1): the PH kernel's answer where the
    unit's outlet is a PH closure's — the valve, the PH flash, the duty-mode reactor — carrying its
    route and its split, from which the traversal start seeds a lifted split and records a band
    route. `None` for every other unit, for a dormant inlet, and on any status other than `ok`.
    """

    status: PropertyStatus
    outlets: Mapping[str, StreamState] = field(default_factory=dict)
    duty: float | None = None
    phase_signature: PhaseSignature | None = None
    iterations: int = 0
    provider_id: str = ""
    reference_convention: str = ""
    message: str = ""
    work: float | None = None
    extent: float | None = None
    transferred_duty: float | None = None
    closure: PHState | None = None

    def __post_init__(self) -> None:
        answered = (self.duty, self.work, self.extent, self.transferred_duty, self.closure)
        if self.status != "ok" and (self.outlets or any(v is not None for v in answered)):
            raise ValueError(
                f"status {self.status!r} carries outlets or a duty; a failed evaluation reports "
                "what went wrong and nothing a caller could mistake for an answer"
            )


class UnitModel(Protocol):
    """A SYN-001 unit: a declaration, a set of residual rows, and a causal evaluator."""

    @property
    def model_id(self) -> str:
        """The manifest id, e.g. `syn001.tp_heater`. Shared by every instance of the model."""

    @property
    def unit_id(self) -> str:
        """This instance's id in the flowsheet, e.g. `U-HEAT`. Prefixes its rows and variables."""

    def ports(self) -> tuple[Port, ...]: ...

    def declared_equations(self) -> tuple[DeclaredEquation, ...]: ...

    def manifest(self) -> Mapping[str, Any]:
        """The `ModelManifest` document for this model, validating against the frozen schema."""

    def contribute(self, wiring: Wiring, components: Sequence[str]) -> Contribution:
        """The rows and owned variables this instance adds to a `ProblemSpec`."""

    def evaluate(
        self, inlets: Mapping[str, Sequence[StreamState]], context: EvaluationContext
    ) -> UnitEvaluation:
        """Compute the outlets causally from the inlets, keyed by port name.

        Every unit takes a context, including the ones that hold no property provider, because a
        caller should not have to know which is which. A provider-free unit ignores it.
        """


# ------------------------------------------------------------------------------ manifest parts

DerivativeMethod = Literal["analytic", "ad", "implicit", "finite_difference", "unavailable"]
InitializationStrategy = Literal[
    "none", "registered_initializer", "local_initializer", "upstream_propagation"
]
ManifestStatus = Literal["declared", "implemented", "tested", "reviewed", "released"]
ThreadSafety = Literal["unknown", "not_thread_safe", "thread_safe"]
CostClass = Literal["unknown", "cheap", "moderate", "expensive"]

#: What a K02 manifest says in place of P01's `0.0.0-declared`. The real identity of the code is
#: `implementation_artifact.artifact_hash`, which changes whenever the module does; this string
#: only records that the document no longer describes an intention.
IMPLEMENTED_VERSION = "0.0.0-tested"

#: The ladder CLAUDE.md keeps apart. K02's models are `tested`: they are implemented, and the
#: gate exercises them against Fable's independent 20-digit references at every registered
#: variant. They are **not** `reviewed` — that needs human numerical and process-modeling
#: sign-off, which no agent may claim, and `manifest_document` will refuse to write it.
UNCLAIMABLE_STATUS: frozenset[str] = frozenset({"reviewed", "released"})


@dataclass(frozen=True)
class DerivativeDeclaration:
    """Blueprint §5.2: declared per output and regime, with `unavailable` an honest answer."""

    output: str
    with_respect_to: tuple[str, ...]
    method: DerivativeMethod
    regime: str = ""
    notes: str = ""

    def as_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "output": self.output,
            "with_respect_to": list(self.with_respect_to),
            "method": self.method,
        }
        if self.regime:
            document["regime"] = self.regime
        if self.notes:
            document["notes"] = self.notes
        return document


@dataclass(frozen=True)
class Initialization:
    """An initializer supplies a guess; a guess is not a specification (blueprint §4.3)."""

    strategy: InitializationStrategy
    notes: str
    registered_initializer: str | None = None

    def as_document(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "registered_initializer": self.registered_initializer,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class Validity:
    """`ModelManifest.validity`. An empty `limitations` asserts there are none."""

    components: tuple[str, ...]
    phases: tuple[str, ...]
    limitations: tuple[str, ...]
    temperature_k: tuple[float, float] | None = None
    pressure_pa: tuple[float, float] | None = None

    def as_document(self) -> dict[str, Any]:
        domain: dict[str, Any] = {}
        if self.temperature_k is not None:
            domain["temperature_K"] = {"min": self.temperature_k[0], "max": self.temperature_k[1]}
        if self.pressure_pa is not None:
            domain["pressure_Pa"] = {"min": self.pressure_pa[0], "max": self.pressure_pa[1]}
        domain["components"] = list(self.components)
        domain["phases"] = list(self.phases)
        return {"domain": domain, "limitations": list(self.limitations)}


def manifest_document(
    *,
    model_id: str,
    title: str,
    description: str,
    ports: Sequence[Port],
    equations: Sequence[DeclaredEquation],
    derivatives: Sequence[DerivativeDeclaration],
    initialization: Initialization,
    validity: Validity,
    module: str,
    artifact_hash: str,
    execution_class: Literal["native_equation", "explicit_reduced", "experiment_provider"],
    thread_safety: ThreadSafety,
    evaluation_cost_class: CostClass,
    property_provider: str | None,
    reference_convention: str | None,
    status: ManifestStatus = "tested",
    version: str = IMPLEMENTED_VERSION,
    package: str = "K02",
) -> dict[str, Any]:
    """Assemble a `ModelManifest` document, validating against `schemas/model-manifest.schema.json`.

    `implementation_artifact.state` is `"source"` and `artifact_hash` is the SHA-256 of the module
    that implements the model, so the document's claim about which code it describes is a fact a
    test can recompute rather than a label.

    `package` names the work package that introduced the model (K02's six; T05's six, spec F3).

    `reviewed` and `released` are refused outright. Human numerical and process-modeling sign-off
    is recorded separately and is not something an agent may write into a manifest.
    """
    if status in UNCLAIMABLE_STATUS:
        raise ValueError(
            f"a model manifest may not be written with status {status!r}: that needs human "
            "numerical and process-modeling sign-off, recorded separately (CLAUDE.md)"
        )
    return {
        "id": model_id,
        "version": version,
        "status": status,
        "title": title,
        "description": description,
        "introduced_by_package": package,
        "ports": [port.as_document() for port in ports],
        "mathematics": {"equations": [equation.as_document() for equation in equations]},
        "derivatives": [declaration.as_document() for declaration in derivatives],
        "initialization": initialization.as_document(),
        "validity": validity.as_document(),
        "implementation_artifact": {
            "state": "source",
            "module": module,
            "artifact_hash": artifact_hash,
            "planned_package": package,
        },
        "execution_requirements": {
            "execution_class": execution_class,
            "thread_safety": thread_safety,
            "evaluation_cost_class": evaluation_cost_class,
            "property_provider": property_provider,
            "reference_convention": reference_convention,
        },
    }


# ------------------------------------------------------------------------------------ assembly


#: The kind of each variable a material stream owns, in `stream_variables` order. The flowsheet
#: allocates those variables, so it is the flowsheet that knows their kinds.
def stream_variable_kinds(stream: str, components: Sequence[str]) -> dict[str, QuantityKind]:
    kinds: dict[str, QuantityKind] = {flow_id(stream, name): "molar_flow" for name in components}
    kinds[temperature_id(stream)] = "temperature"
    kinds[pressure_id(stream)] = "pressure"
    return kinds


def stream_variables(stream: str, components: Sequence[str]) -> tuple[str, ...]:
    """The free variables one material stream owns, in a fixed order.

    Component flows first, in the flowsheet's component order, then temperature, then pressure.
    The order is a convention and conventions get permuted, so it lives here and nowhere else.
    """
    return (
        *(flow_id(stream, name) for name in components),
        temperature_id(stream),
        pressure_id(stream),
    )


def assemble(
    *,
    label: str,
    units: Sequence[UnitModel],
    wiring: Mapping[str, Wiring],
    streams: Sequence[str],
    components: Sequence[str],
) -> ProblemSpec:
    """Collect unit contributions into one `ProblemSpec`.

    Stream variables belong to the flowsheet and are allocated here, once, in `streams` order;
    unit-owned variables (duties) follow in `units` order. Nothing is solved and nothing is
    eliminated: a specification row and the variable it fixes both stay, because K01's compiler
    and K03's structural analysis are the things entitled to remove them, and removing a row here
    would hide it from `row_accumulation`.

    Scales are left empty on purpose (ADR 0001 D3.5 gives scale construction to K03).
    """

    variable_ids: list[str] = []
    variable_kinds: dict[str, QuantityKind] = {}
    row_kinds: dict[str, QuantityKind] = {}
    for stream in streams:
        variable_ids.extend(stream_variables(stream, components))
        variable_kinds.update(stream_variable_kinds(stream, components))

    equations: list[EquationSpec] = []
    blocks: list[PropertyBlock] = []
    declared_blocks: dict[str, PropertyBlock] = {}
    block_inputs: dict[str, tuple[str, ...]] = {}
    parameter_ids: list[str] = []
    parameters: dict[str, float] = {}

    for unit in units:
        connected = wiring.get(unit.unit_id)
        if connected is None:
            raise SpecificationError(f"unit {unit.unit_id!r} has no wiring")
        contribution = unit.contribute(connected, components)
        for name in contribution.variable_ids:
            # A two-phase stream's lifted split is named after the *stream*, so the unit that
            # produces it and the unit that reads it ask for the same variables. Seen twice is
            # the same variable; seen twice with a different shape is a bug.
            if name not in variable_ids:
                variable_ids.append(name)
        equations.extend(contribution.equations)
        for block in contribution.blocks:
            existing = declared_blocks.get(block.block_id)
            if existing is None:
                declared_blocks[block.block_id] = block
                blocks.append(block)
            elif (existing.input_ids, existing.output_ids) != (block.input_ids, block.output_ids):
                raise SpecificationError(
                    f"two units declare block {block.block_id!r} with different shapes"
                )
        for block_id, feeding in contribution.block_inputs.items():
            if block_inputs.get(block_id, feeding) != feeding:
                raise SpecificationError(
                    f"two units feed block {block_id!r} from different variables"
                )
            block_inputs[block_id] = feeding
        for name in contribution.parameter_ids:
            if name not in parameter_ids:
                parameter_ids.append(name)
        # `what` and not `label`: `label` is this function's own parameter, and shadowing it
        # here silently renamed every assembled problem to "row@<digest>". The gate did not
        # catch that -- the identity tests compare two model_versions to each other, and both
        # were equally wrong -- so it is named for what it is.
        for mapping, target, what in (
            (contribution.variable_kinds, variable_kinds, "variable"),
            (contribution.row_kinds, row_kinds, "row"),
        ):
            for name, kind in mapping.items():
                if target.get(name, kind) != kind:
                    raise SpecificationError(
                        f"two units declare {what} {name!r} with different kinds: "
                        f"{target[name]!r} and {kind!r}"
                    )
                target[name] = kind
        for name, value in contribution.parameters.items():
            if name in parameters and parameters[name] != value:
                raise SpecificationError(
                    f"two units bind pinned input {name!r} to different values: "
                    f"{parameters[name]} and {value}"
                )
            parameters[name] = value

    return ProblemSpec(
        label=label,
        variable_ids=tuple(variable_ids),
        equations=tuple(equations),
        parameter_ids=tuple(parameter_ids),
        parameters=parameters,
        blocks=tuple(blocks),
        block_inputs=block_inputs,
        variable_kinds=variable_kinds,
        row_kinds=row_kinds,
    )
