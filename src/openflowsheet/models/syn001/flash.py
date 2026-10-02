"""`syn001.tp_flash` — an isothermal, isobaric two-outlet equilibrium flash.

The unit that gives SYN-001 its name. Its two outlets *are* the phase split, so unlike the
heater it lifts nothing: `FLASH-equilibrium` relates two streams that the flowsheet already has.
It owns only the two phase totals the division-free equilibrium form needs, and its duty.

**The equilibrium form is `n_vap,i N_liq - K_i n_liq,i N_vap`**, from the P02 spec. Written in
mole fractions it would divide by a total flow, which ADR 0001 D3.2 forbids outright; written
this way it is exact when a component is absent and exact when a whole phase has vanished, which
is three of the five registered variants.

**Classification order** is the liquid test, then the vapour test, then two-phase, and derivation
§5.1 proves that unambiguous on the SYN-001 domain by Cauchy-Schwarz. It is not a general
stability test and makes no claim about a third phase. The kernel does not re-derive it: the
provider's flash owns it, and this unit reports what it returns.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Final

from openflowsheet.canonical import file_sha256
from openflowsheet.compile.spec import EquationSpec, QuantityKind
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import (
    Accumulation,
    Contribution,
    DeclaredEquation,
    DerivativeDeclaration,
    Holdup,
    Initialization,
    Port,
    SpecificationError,
    UnitEvaluation,
    Validity,
    Wiring,
    duty_id,
    flow_id,
    manifest_document,
    origin,
    pressure_id,
    row_id,
    temperature_id,
)
from openflowsheet.models.rows import (
    balance_row,
    definition_row,
    energy_row,
    equilibrium_row,
    specification_row,
)
from openflowsheet.models.syn001 import (
    COMPONENTS,
    DERIVATION,
    ENERGY,
    MOLAR_FLOW,
    MOLE,
    P_MAX,
    P_MIN,
    POWER,
    PRESSURE,
    PROVIDER_ID,
    REFERENCE_CONVENTION,
    T_MAX,
    T_MIN,
    TEMPERATURE,
)
from openflowsheet.models.syn001.blocks import LnKBlock
from openflowsheet.models.syn001.tp_state import (
    lnk_block_id,
    single_phase_enthalpy,
    tp_state,
)
from openflowsheet.thermo import Phase, PropertyProvider, StreamState

MODEL_ID: Final = "syn001.tp_flash"


def total_flow_id(stream: str) -> str:
    """A stream's total molar flow, lifted so the equilibrium row needs no division."""
    return f"{stream}.N"


PORTS: Final[tuple[Port, ...]] = (
    Port(
        name="inlet",
        kind="material",
        direction="inlet",
        multiplicity=1,
        component_mapping="revision_component_set",
        state_definition="nTP-v1",
        phase_capabilities=("liquid", "vapor", "vapor_liquid"),
    ),
    Port(
        name="vapor",
        kind="material",
        direction="outlet",
        multiplicity=1,
        component_mapping="revision_component_set",
        state_definition="nTP-v1",
        phase_capabilities=("vapor",),
    ),
    Port(
        name="liquid",
        kind="material",
        direction="outlet",
        multiplicity=1,
        component_mapping="revision_component_set",
        state_definition="nTP-v1",
        phase_capabilities=("liquid",),
    ),
    Port(
        name="duty",
        kind="energy",
        direction="inlet",
        multiplicity=1,
        component_mapping=None,
        state_definition=None,
        phase_capabilities=(),
    ),
)

EQUATIONS: Final[tuple[DeclaredEquation, ...]] = (
    DeclaredEquation(
        equation_id="FLASH-mole",
        statement="n_in,i - n_vap,i - n_liq,i = 0 for every component i",
        dependencies=("inlet.state.n", "vapor.state.n", "liquid.state.n"),
        conditional_class="unconditional",
        accumulation=Accumulation(
            kind="holdup_balance",
            holdup=Holdup(
                symbol="N_i",
                quantity="component moles held in the flash drum, vapor plus liquid",
                dimension=MOLE,
            ),
        ),
        dimension=MOLAR_FLOW,
        source=DERIVATION,
    ),
    DeclaredEquation(
        equation_id="FLASH-equilibrium",
        statement=(
            "y_i - K_i(T, P) x_i = 0 for every component present in a flowing phase; written in "
            "K-value form so that ln(0) is never evaluated for an absent component"
        ),
        dependencies=("vapor.state", "liquid.state"),
        conditional_class="phase_conditional",
        accumulation=Accumulation(kind="algebraic"),
        source=DERIVATION,
    ),
    DeclaredEquation(
        equation_id="FLASH-T",
        statement="T_vap - T_spec = 0 and T_liq - T_spec = 0",
        dependencies=("specifications.SPEC-flash-T",),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=TEMPERATURE,
        source=DERIVATION,
    ),
    DeclaredEquation(
        equation_id="FLASH-P",
        statement="P_vap - P_spec = 0, P_liq - P_spec = 0, P_in - P_spec = 0 with dP = 0 declared",
        dependencies=("specifications.SPEC-flash-P", "parameters.pressure_drop"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=PRESSURE,
        source=DERIVATION,
    ),
    DeclaredEquation(
        equation_id="FLASH-duty",
        statement="Q - (Hdot_vap + Hdot_liq - Hdot_in) = 0, Q positive into the unit",
        dependencies=("inlet.state", "vapor.state", "liquid.state", "duty.Q"),
        conditional_class="unconditional",
        accumulation=Accumulation(
            kind="holdup_balance",
            holdup=Holdup(
                symbol="U",
                quantity="internal energy of the flash drum contents",
                dimension=ENERGY,
            ),
        ),
        dimension=POWER,
        source=DERIVATION,
    ),
)

_SENSITIVITY_NOTE: Final = (
    "K02 implements the model and K01 supplies the residual derivative route, but the sensitivity "
    "of an outlet state to the inlet state is a derivative through the equilibrium system and "
    "would need the implicit-function route of blueprint §5.1. K02 exposes no such interface, so "
    "this stays `unavailable` and is reported as absent rather than as zeros (blueprint §5.2)."
)


@cache
def _artifact_hash() -> str:
    return file_sha256(Path(__file__))


@dataclass(frozen=True)
class TPFlash:
    """One isothermal-isobaric flash at a specified temperature and pressure."""

    unit_id: str
    provider: PropertyProvider
    temperature: float
    pressure: float
    context: EvaluationContext
    #: The declared phase regime of the *inlet*. `None` means its split is lifted upstream, which
    #: is the SYN-001 case: the heater produces a possibly-two-phase stream and lifts it.
    inlet_phase: Phase | None = None
    components: tuple[str, ...] = COMPONENTS

    def __post_init__(self) -> None:
        if not T_MIN <= self.temperature <= T_MAX:
            raise SpecificationError(
                f"{self.unit_id}: specified temperature {self.temperature} K is outside the "
                f"declared domain [{T_MIN}, {T_MAX}] K"
            )
        if not P_MIN <= self.pressure <= P_MAX:
            raise SpecificationError(
                f"{self.unit_id}: specified pressure {self.pressure} Pa is outside the declared "
                f"domain [{P_MIN}, {P_MAX}] Pa"
            )

    @property
    def model_id(self) -> str:
        return MODEL_ID

    @property
    def temperature_parameter(self) -> str:
        return f"{self.unit_id}.T_spec"

    @property
    def pressure_parameter(self) -> str:
        return f"{self.unit_id}.P_spec"

    # -- declaration -------------------------------------------------------------------------

    def ports(self) -> tuple[Port, ...]:
        return PORTS

    def declared_equations(self) -> tuple[DeclaredEquation, ...]:
        return EQUATIONS

    def manifest(self) -> Mapping[str, Any]:
        return manifest_document(
            model_id=MODEL_ID,
            title="SYN-001 isothermal-isobaric flash",
            description="Two-outlet equilibrium flash at a specified temperature and pressure.",
            ports=PORTS,
            equations=EQUATIONS,
            derivatives=(
                DerivativeDeclaration(
                    output="vapor.state",
                    with_respect_to=("inlet.state", "specifications"),
                    method="unavailable",
                    regime="all",
                    notes=_SENSITIVITY_NOTE,
                ),
                DerivativeDeclaration(
                    output="liquid.state",
                    with_respect_to=("inlet.state", "specifications"),
                    method="unavailable",
                    regime="all",
                    notes=_SENSITIVITY_NOTE,
                ),
                DerivativeDeclaration(
                    output="duty.Q",
                    with_respect_to=("inlet.state", "specifications"),
                    method="unavailable",
                    regime="all",
                    notes=_SENSITIVITY_NOTE,
                ),
                DerivativeDeclaration(
                    output="residuals",
                    with_respect_to=("free_variables",),
                    method="ad",
                    regime="all",
                    notes=(
                        "The two outlets are the phase split, so every row is written over "
                        "flowsheet variables and CasADi differentiates it exactly through the "
                        "K01 adapter; the K-value and enthalpy blocks supply their own "
                        "declared-sparse analytic derivatives."
                    ),
                ),
            ),
            initialization=Initialization(
                strategy="local_initializer",
                notes=(
                    "Safeguarded Rachford-Rice on a bracket derived from the active-set "
                    "K-values, with explicit single-phase endpoints (blueprint §6.2)."
                ),
            ),
            validity=Validity(
                components=self.components,
                phases=("liquid", "vapor", "vapor_liquid", "zero_flow"),
                limitations=(
                    "Classification order is the liquid test, then the vapor test, then "
                    "two-phase. Derivation §5.1 proves that unambiguous on the SYN-001 domain; "
                    "it is not a general-purpose stability test and makes no claim about a third "
                    "phase.",
                    "A dormant feed produces two dormant outlets, exactly zero duty and phase "
                    "signature ZERO_FLOW. That is a valid result, not a failure (ADR 0001 D3.4).",
                    "V = 0 or L = 0 with a flowing feed produces one dormant outlet; the unit's "
                    "own signature is then LIQUID or VAPOR.",
                    "Nothing divides by total flow before that flow has been tested against "
                    "exact zero, and compositions are never renormalized to force solvability.",
                    "FLASH-P imposes the specified pressure on the *inlet* as well as on both "
                    "outlets, as declared. In a loop whose pressure drops are all zero that row "
                    "is linearly dependent on the chain upstream of it; K03's structural "
                    "analysis is what reports the rank, and this unit does not drop the row to "
                    "make a count come out.",
                ),
                temperature_k=(T_MIN, T_MAX),
                pressure_pa=(P_MIN, P_MAX),
            ),
            module=__name__,
            artifact_hash=_artifact_hash(),
            execution_class="native_equation",
            thread_safety="not_thread_safe",
            evaluation_cost_class="moderate",
            property_provider=PROVIDER_ID,
            reference_convention=REFERENCE_CONVENTION,
        )

    # -- rows --------------------------------------------------------------------------------

    def contribute(self, wiring: Wiring, components: Sequence[str]) -> Contribution:
        if tuple(components) != self.components:
            raise SpecificationError(
                f"{self.unit_id}: wired into components {tuple(components)}, built for "
                f"{self.components}"
            )
        inlet = wiring.one("inlet")
        vapor = wiring.one("vapor")
        liquid = wiring.one("liquid")
        duty = duty_id(self.unit_id)
        total_vapor, total_liquid = total_flow_id(vapor), total_flow_id(liquid)

        lnk = LnKBlock(self.provider, self.components, self.context, block_id=lnk_block_id(vapor))
        vapor_block, vapor_feeding, vapor_keys = single_phase_enthalpy(
            self.provider, self.components, self.context, vapor, "VAPOR"
        )
        liquid_block, liquid_feeding, liquid_keys = single_phase_enthalpy(
            self.provider, self.components, self.context, liquid, "LIQUID"
        )
        inlet_keys, inlet_blocks, inlet_inputs = self._inlet_enthalpy(inlet)

        equations: list[EquationSpec] = []
        for component in self.components:
            equations.append(
                EquationSpec(
                    equation_id=row_id(self.unit_id, "FLASH-mole", component),
                    build=balance_row(
                        (flow_id(inlet, component),),
                        (flow_id(vapor, component), flow_id(liquid, component)),
                    ),
                    accumulation="holdup_balance",
                    origin=origin(MODEL_ID, "FLASH-mole"),
                )
            )
            equations.append(
                EquationSpec(
                    equation_id=row_id(self.unit_id, "FLASH-equilibrium", component),
                    build=equilibrium_row(
                        flow_id(vapor, component),
                        flow_id(liquid, component),
                        total_vapor,
                        total_liquid,
                        f"{lnk.block_id}.lnK_{component}",
                    ),
                    accumulation="algebraic",
                    origin=origin(MODEL_ID, "FLASH-equilibrium"),
                )
            )
        for port, stream in (("vapor", vapor), ("liquid", liquid)):
            equations.append(
                EquationSpec(
                    equation_id=row_id(self.unit_id, "FLASH-T", port),
                    build=specification_row(temperature_id(stream), self.temperature_parameter),
                    accumulation="algebraic",
                    origin=origin(MODEL_ID, "FLASH-T"),
                )
            )
        for port, stream in (("vapor", vapor), ("liquid", liquid), ("inlet", inlet)):
            equations.append(
                EquationSpec(
                    equation_id=row_id(self.unit_id, "FLASH-P", port),
                    build=specification_row(pressure_id(stream), self.pressure_parameter),
                    accumulation="algebraic",
                    origin=origin(MODEL_ID, "FLASH-P"),
                )
            )
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "FLASH-duty"),
                build=energy_row(inlet_keys, (*vapor_keys, *liquid_keys), source=duty),
                accumulation="holdup_balance",
                origin=origin(MODEL_ID, "FLASH-duty"),
            )
        )
        for port, stream, total in (
            ("vapor", vapor, total_vapor),
            ("liquid", liquid, total_liquid),
        ):
            equations.append(
                EquationSpec(
                    equation_id=row_id(self.unit_id, "Ndef", port),
                    build=definition_row(
                        total, tuple(flow_id(stream, name) for name in self.components)
                    ),
                    accumulation="algebraic",
                    origin=origin(MODEL_ID, "lifting"),
                )
            )

        kinds: dict[str, QuantityKind] = {}
        for component in self.components:
            kinds[row_id(self.unit_id, "FLASH-mole", component)] = "molar_flow"
            kinds[row_id(self.unit_id, "FLASH-equilibrium", component)] = "molar_flow_squared"
        for port in ("vapor", "liquid"):
            kinds[row_id(self.unit_id, "FLASH-T", port)] = "temperature"
            kinds[row_id(self.unit_id, "Ndef", port)] = "molar_flow"
        for port in ("vapor", "liquid", "inlet"):
            kinds[row_id(self.unit_id, "FLASH-P", port)] = "pressure"
        kinds[row_id(self.unit_id, "FLASH-duty")] = "heat_rate"

        return Contribution(
            variable_ids=(duty, total_vapor, total_liquid),
            equations=tuple(equations),
            variable_kinds={
                duty: "heat_rate",
                total_vapor: "molar_flow",
                total_liquid: "molar_flow",
            },
            row_kinds=kinds,
            blocks=(lnk, vapor_block, liquid_block, *inlet_blocks),
            block_inputs={
                lnk.block_id: (temperature_id(vapor), pressure_id(vapor)),
                vapor_block.block_id: vapor_feeding,
                liquid_block.block_id: liquid_feeding,
                **inlet_inputs,
            },
            parameter_ids=(self.temperature_parameter, self.pressure_parameter),
            parameters={
                self.temperature_parameter: float(self.temperature),
                self.pressure_parameter: float(self.pressure),
            },
        )

    def _inlet_enthalpy(
        self, inlet: str
    ) -> tuple[tuple[str, ...], tuple[Any, ...], dict[str, tuple[str, ...]]]:
        """The block outputs whose sum is `Hdot_in`.

        When the inlet's split is lifted upstream — the SYN-001 case, where the heater produces a
        possibly two-phase stream — this unit declares no block of its own and refers to the two
        the producer already named after the stream. `assemble` deduplicates by block id, so both
        units may name them and only one is compiled.
        """
        from openflowsheet.models.syn001.tp_state import (  # noqa: PLC0415
            liquid_flow_id,
            vapor_flow_id,
        )

        if self.inlet_phase is not None:
            block, feeding, single_keys = single_phase_enthalpy(
                self.provider, self.components, self.context, inlet, self.inlet_phase
            )
            return single_keys, (block,), {block.block_id: feeding}

        from openflowsheet.models.syn001.blocks import EnthalpyFlowBlock  # noqa: PLC0415
        from openflowsheet.models.syn001.tp_state import enthalpy_block_id  # noqa: PLC0415

        blocks = []
        inputs: dict[str, tuple[str, ...]] = {}
        keys: list[str] = []
        for phase, ids in (("VAPOR", vapor_flow_id), ("LIQUID", liquid_flow_id)):
            block = EnthalpyFlowBlock(
                self.provider,
                self.components,
                phase,  # type: ignore[arg-type]
                self.context,
                block_id=enthalpy_block_id(inlet, phase),  # type: ignore[arg-type]
            )
            blocks.append(block)
            inputs[block.block_id] = (
                *(ids(inlet, name) for name in self.components),
                temperature_id(inlet),
                pressure_id(inlet),
            )
            keys.extend(f"{block.block_id}.{output}" for output in block.output_ids)
        return tuple(keys), tuple(blocks), inputs

    # -- evaluator ---------------------------------------------------------------------------

    def evaluate(
        self, inlets: Mapping[str, Sequence[StreamState]], context: EvaluationContext
    ) -> UnitEvaluation:
        connected = tuple(inlets.get("inlet", ()))
        if len(connected) != 1 or set(inlets) - {"inlet"}:
            raise SpecificationError(
                f"{self.unit_id}: a flash takes exactly one inlet stream, got {inlets!r}"
            )
        feed = connected[0]
        if len(feed.n) != len(self.components):
            raise SpecificationError(
                f"{self.unit_id}: inlet carries {len(feed.n)} components, expected "
                f"{len(self.components)}"
            )
        if feed.pressure != self.pressure:
            # FLASH-P declares P_in = P_spec. ADR 0001 D4.5: a pressure mismatch is a validation
            # failure, not something a unit silently repairs.
            return UnitEvaluation(
                status="error",
                message=(
                    f"inlet pressure {feed.pressure} Pa does not equal the specified "
                    f"{self.pressure} Pa; FLASH-P declares them equal and the unit does not "
                    "repair a pressure network"
                ),
                reference_convention=REFERENCE_CONVENTION,
            )

        if feed.is_dormant:
            dormant = StreamState(
                n=tuple(0.0 for _ in self.components),
                temperature=float(self.temperature),
                pressure=float(self.pressure),
            )
            return UnitEvaluation(
                status="ok",
                outlets={"vapor": dormant, "liquid": dormant},
                duty=0.0,
                phase_signature="ZERO_FLOW",
                reference_convention=REFERENCE_CONVENTION,
            )

        inlet_state = tp_state(self.provider, feed, context)
        if inlet_state.status != "ok":
            return UnitEvaluation(
                status=inlet_state.status,
                message=f"inlet state: {inlet_state.message}",
                reference_convention=inlet_state.reference_convention,
            )
        outlet_state = tp_state(
            self.provider,
            feed,
            context,
            temperature=float(self.temperature),
            pressure=float(self.pressure),
        )
        if outlet_state.status != "ok":
            return UnitEvaluation(
                status=outlet_state.status,
                message=f"flash: {outlet_state.message}",
                reference_convention=outlet_state.reference_convention,
            )
        assert inlet_state.enthalpy_flow is not None
        assert outlet_state.enthalpy_flow is not None
        assert outlet_state.vapor is not None
        assert outlet_state.liquid is not None

        return UnitEvaluation(
            status="ok",
            outlets={"vapor": outlet_state.vapor, "liquid": outlet_state.liquid},
            duty=outlet_state.enthalpy_flow - inlet_state.enthalpy_flow,
            phase_signature=outlet_state.phase_signature,
            iterations=inlet_state.iterations + outlet_state.iterations,
            provider_id=outlet_state.provider_id,
            reference_convention=outlet_state.reference_convention,
        )
