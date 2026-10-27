"""What every `thermal.*` unit shares: ports, stream faces, saturated rows, inlet enthalpy, outlets.

S11 units design §4.1 and §4.4 "Common to all seven". A unit is built with its port-to-stream map
and each stream's declared form (S11C_DECISIONS C2-1): a saturated outlet's owned columns and every
typed refusal name the stream, which a port name alone cannot.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any, Final

from openflowsheet.canonical import file_sha256
from openflowsheet.compile.spec import EquationSpec, PropertyBlock, QuantityKind
from openflowsheet.compiled import EvaluationContext, PhaseSignature
from openflowsheet.models import (
    Accumulation,
    DeclaredEquation,
    DerivativeDeclaration,
    DerivativeMethod,
    Initialization,
    Port,
    SpecificationError,
    Validity,
    Wiring,
    flow_id,
    manifest_document,
    origin,
    pressure_id,
    row_id,
    temperature_id,
)
from openflowsheet.models.rows import balance_row
from openflowsheet.models.syn001 import MOLAR_FLOW, TEMPERATURE, TEMPERATURE_TOLERANCE
from openflowsheet.models.thermal import FORM_CAPABILITY, Form
from openflowsheet.models.thermal.blocks import (
    PhaseFlowBlock,
    SaturatedFlowBlock,
    phase_block_id,
    saturated_block_id,
)
from openflowsheet.models.thermal.kernel import (
    Failure,
    declared_admissible,
    phase_properties,
    saturation,
)
from openflowsheet.models.thermal.rows import saturation_temperature_row
from openflowsheet.models.thermal.state import (
    SaturatedStreamState,
    carried_fraction,
    liquid_id,
    saturated_owned,
    vapor_id,
)
from openflowsheet.thermo import Phase, PropertyProvider, StreamState

__all__ = [
    "NO_HOLDUP",
    "Outcome",
    "StreamFace",
    "check_wiring",
    "energy_port",
    "inlet_enthalpy",
    "material_port",
    "outlet",
    "saturated_declarations",
    "saturated_rows",
    "stream_face",
]

NO_HOLDUP: Final = "a thermal unit with no inventory by the model's definition"
ALL_FORMS: Final[tuple[Form, ...]] = ("LIQUID", "VAPOR", "SATURATED")


def material_port(name: str, direction: str, forms: Sequence[Form], *, many: bool = False) -> Port:
    return Port(
        name=name,
        kind="material",
        direction=direction,  # type: ignore[arg-type]
        multiplicity="many" if many else 1,
        component_mapping="revision_component_set",
        state_definition="nTP-v1",
        phase_capabilities=tuple(FORM_CAPABILITY[form] for form in forms),  # type: ignore[misc]
    )


def energy_port(name: str) -> Port:
    return Port(
        name=name,
        kind="energy",
        direction="inlet",
        multiplicity=1,
        component_mapping=None,
        state_definition=None,
        phase_capabilities=(),
    )


def check_wiring(
    unit_id: str,
    streams: Mapping[str, tuple[str, ...]],
    forms: Mapping[str, Form],
    wiring: Wiring | None = None,
) -> None:
    """Construction (and `contribute`) check: every material stream has a declared form, and the
    wiring a unit is contributed with is the one it was built for."""
    for port, connected in streams.items():
        for stream in connected:
            if forms.get(stream) not in ALL_FORMS:
                raise SpecificationError(
                    f"{unit_id}: stream {stream!r} on port {port!r} has no declared form"
                )
    if wiring is not None:
        for port, connected in streams.items():
            if tuple(wiring.streams.get(port, ())) != tuple(connected):
                raise SpecificationError(
                    f"{unit_id}: port {port!r} wired to {list(wiring.streams.get(port, ()))}, "
                    f"built for {list(connected)}"
                )


# -- the EO face of one stream --------------------------------------------------------------------


@dataclass(frozen=True)
class StreamFace:
    """A stream's enthalpy block, what feeds it, and the key an energy row sums."""

    block: PropertyBlock
    feeding: tuple[str, ...]
    key: str


def stream_face(
    provider: PropertyProvider,
    component: str,
    context: EvaluationContext,
    stream: str,
    form: Form,
) -> StreamFace:
    """`PF_<S>_<phase>` fed by (n, T, P), or `PFsat_<S>` fed by (V, L, P) (§4.1). Every reader of
    a stream declares the identical block; `assemble` deduplicates it by id."""
    if form == "SATURATED":
        saturated = SaturatedFlowBlock(
            provider, component, context, block_id=saturated_block_id(stream)
        )
        feeding = (vapor_id(stream), liquid_id(stream), pressure_id(stream))
        return StreamFace(saturated, feeding, f"{saturated.block_id}.H")
    single = PhaseFlowBlock(
        provider, component, form, context, block_id=phase_block_id(stream, form)
    )
    feeding = (flow_id(stream, component), temperature_id(stream), pressure_id(stream))
    return StreamFace(single, feeding, f"{single.block_id}.H")


def saturated_declarations(source: str) -> tuple[DeclaredEquation, ...]:
    """`sat-T` and `sat-split`, declared once per model that produces a saturated outlet."""
    return (
        DeclaredEquation(
            equation_id="sat-T",
            statement="T_S - T_sat(P_S) = 0 for a saturated outlet S",
            dependencies=("outlet.state.T", "outlet.state.P"),
            conditional_class="unconditional",
            accumulation=Accumulation(kind="algebraic"),
            dimension=TEMPERATURE,
            source=source,
        ),
        DeclaredEquation(
            equation_id="sat-split",
            statement="V_S + L_S - n_S = 0 for a saturated outlet S (the carried split)",
            dependencies=("outlet.state.n", "outlet.sat.V", "outlet.sat.L"),
            conditional_class="unconditional",
            accumulation=Accumulation(kind="algebraic"),
            dimension=MOLAR_FLOW,
            source=source,
        ),
    )


@dataclass
class Rows:
    """Rows, kinds and owned columns a unit accumulates in `contribute`."""

    equations: list[EquationSpec] = field(default_factory=list)
    row_kinds: dict[str, QuantityKind] = field(default_factory=dict)
    owned: list[str] = field(default_factory=list)
    owned_kinds: dict[str, QuantityKind] = field(default_factory=dict)

    def add(
        self,
        unit_id: str,
        model_id: str,
        family: str,
        build: object,
        kind: QuantityKind,
        accumulation: str = "algebraic",
        suffix: tuple[str, ...] = (),
    ) -> None:
        equation_id = row_id(unit_id, family, *suffix)
        self.equations.append(
            EquationSpec(
                equation_id=equation_id,
                build=build,  # type: ignore[arg-type]
                accumulation=accumulation,  # type: ignore[arg-type]
                origin=origin(model_id, family),
            )
        )
        self.row_kinds[equation_id] = kind

    def own(self, variable: str, kind: QuantityKind) -> None:
        self.owned.append(variable)
        self.owned_kinds[variable] = kind


def saturated_rows(
    rows: Rows, unit_id: str, model_id: str, port: str, stream: str, component: str
) -> None:
    """The producer's part of a saturated outlet (§4.1): the columns `<S>.sat.V`, `<S>.sat.L` and
    the rows `sat-T:<port>` and `sat-split:<port>`. The block is the stream face's."""
    rows.own(vapor_id(stream), "molar_flow")
    rows.own(liquid_id(stream), "molar_flow")
    rows.add(
        unit_id,
        model_id,
        "sat-T",
        saturation_temperature_row(temperature_id(stream), f"{saturated_block_id(stream)}.Tsat"),
        "temperature",
        suffix=(port,),
    )
    rows.add(
        unit_id,
        model_id,
        "sat-split",
        balance_row((vapor_id(stream), liquid_id(stream)), (flow_id(stream, component),)),
        "molar_flow",
        suffix=(port,),
    )


# -- the causal face ------------------------------------------------------------------------------


def _single(form: Form) -> Phase:
    assert form != "SATURATED"
    return form


def inlet_enthalpy(
    provider: PropertyProvider,
    state: StreamState,
    form: Form,
    port: str,
    stream: str,
    context: EvaluationContext,
) -> float | Failure:
    """An inlet's enthalpy flow as the rows write it (§4.4 "Inlet enthalpy in the evaluate").

    Single-phase: `adm` must hold, else `inadmissible_phase(<port>, <PHASE>)`; n h^phase(T, P).
    Saturated: |T - T_sat(P)| <= tau_T, else `carried_split_inconsistent(<S>)`;
    n [h^L_sat + beta (h^V_sat - h^L_sat)]. A dormant inlet is 0.0.
    """
    if state.is_dormant:
        return 0.0
    total = state.total_flow
    if form == "SATURATED":
        beta = carried_fraction(state, stream)
        if isinstance(beta, Failure):
            return beta
        sat = saturation(provider, state.pressure, context)
        if isinstance(sat, Failure):
            return sat
        if not abs(state.temperature - sat.temperature) <= TEMPERATURE_TOLERANCE:
            return Failure(
                "unsupported",
                f"carried_split_inconsistent({stream})",
                f"T = {state.temperature!r} K is not T_sat({state.pressure!r} Pa) = "
                f"{sat.temperature!r} K within {TEMPERATURE_TOLERANCE} K",
            )
        liquid, vapour = sat.value("LIQUID", "h"), sat.value("VAPOR", "h")
        return total * (liquid + beta * (vapour - liquid))
    phase = _single(form)
    admissible = declared_admissible(provider, state.temperature, state.pressure, phase, context)
    if isinstance(admissible, Failure):
        return admissible
    if not admissible:
        return Failure(
            "unsupported",
            f"inadmissible_phase({port}, {phase})",
            f"{stream} at ({state.temperature!r} K, {state.pressure!r} Pa) is not {phase}",
        )
    jets = phase_properties(provider, context, state.temperature, state.pressure, phase, ("h",))
    if isinstance(jets, Failure):
        return jets
    return total * jets["h"][0]


@dataclass(frozen=True)
class Outcome:
    """One outlet of a causal evaluation: its state, owned columns and phase signature."""

    state: StreamState
    owned: dict[str, float]
    signature: PhaseSignature


def outlet(
    stream: str,
    form: Form,
    flows: tuple[float, ...],
    temperature: float,
    pressure: float,
    beta: float | None = None,
) -> Outcome:
    """The outlet in its form's class; a dormant one is labelled, with beta = 0.0 (§4.4)."""
    total = sum(flows)
    if form != "SATURATED":
        signature: PhaseSignature = "ZERO_FLOW" if total == 0.0 else form
        return Outcome(StreamState(flows, temperature, pressure), {}, signature)
    fraction = 0.0 if total == 0.0 else beta
    if fraction is None:
        raise ValueError(f"a saturated outlet {stream} needs its vapour fraction")
    state = SaturatedStreamState(flows, temperature, pressure, vapor_fraction=fraction)
    if total == 0.0:
        signature = "ZERO_FLOW"
    elif fraction == 0.0:
        signature = "LIQUID"
    elif fraction == 1.0:
        signature = "VAPOR"
    else:
        signature = "TWO_PHASE"
    return Outcome(state, saturated_owned(stream, total, fraction), signature)


_SENSITIVITY: Final = (
    "The rows are differentiated exactly through K01 from the blocks' declared derivatives; the "
    "sensitivity of the outlet state to the inlet or a specification runs through the causal "
    "evaluator's closure, which no interface supplies, so it is declared unavailable (blueprint "
    "§5.2)."
)


def manifest(
    *,
    model_id: str,
    title: str,
    description: str,
    ports: Sequence[Port],
    equations: Sequence[DeclaredEquation],
    provider: PropertyProvider,
    method: DerivativeMethod,
    notes: str,
    initialization: str,
    limitations: tuple[str, ...],
    module: str,
    path: Path,
) -> dict[str, Any]:
    """§4.4 "Manifests": provider fields and the domain from `describe()`, `native_equation`,
    status `tested`, the module's `file_sha256` as the artifact hash."""
    described = provider.describe()
    t_low, t_high = described.domain["T"]
    p_low, p_high = described.domain["P"]
    return manifest_document(
        model_id=model_id,
        title=title,
        description=description,
        ports=ports,
        equations=equations,
        derivatives=(
            DerivativeDeclaration(
                output="outlet.state",
                with_respect_to=("inlet.state", "specifications"),
                method="unavailable",
                regime="all",
                notes=_SENSITIVITY,
            ),
            DerivativeDeclaration(
                output="residuals",
                with_respect_to=("free_variables",),
                method=method,
                regime="all",
                notes=notes,
            ),
        ),
        initialization=Initialization(strategy="local_initializer", notes=initialization),
        validity=Validity(
            components=described.components,
            phases=("liquid", "vapor", "vapor_liquid", "zero_flow"),
            limitations=limitations,
            temperature_k=(float(t_low), float(t_high)),
            pressure_pa=(float(p_low), float(p_high)),
        ),
        module=module,
        artifact_hash=_artifact_hash(str(path)),
        execution_class="native_equation",
        thread_safety=described.thread_safety,
        evaluation_cost_class="moderate",
        property_provider=described.provider_id,
        reference_convention=described.reference_convention,
        package="S11",
    )


@cache
def _artifact_hash(path: str) -> str:
    return file_sha256(Path(path))


#: Common limitations, in every thermal manifest.
LIMITATIONS: Final[tuple[str, ...]] = (
    "Pure-fluid regimes are declared, not discovered (ADR 0051 D1): a closure landing outside a "
    "stream's declared phase_capability is refused phase_regime_mismatch(<S>), naming the "
    "declaration to use.",
    "vapor_liquid means saturated: T = T_sat(P) with a carried split <S>.sat.V, <S>.sat.L "
    "(ADR 0051 D2); only thermal.* units produce such a stream (D4).",
    "A dormant inlet labels its outlet with the inlet temperature at the outlet pressure and "
    "reports zero duty or work (ADR 0001 D3.4).",
)
