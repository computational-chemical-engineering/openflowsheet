"""`syn001.tp_heater` — a heater with a TP-state outlet and a calculated duty.

Plan §3.2 models the heater this way "from the start", so a two-phase outlet is a supported
result rather than an error, and it is: three of the five registered SYN-001 variants have one
(derivation §7 finding 2). The duty may also be negative — at r = 0.95 the adiabatic mixer
outlet is 354.73 K, above the 350 K setpoint, so the unit removes about 16 144.6 W. ADR 0001
D4.2 makes that a supported result, and an implementation asserting `Q >= 0` fails a registered
variant.

**The outlet's phase split is lifted** (`docs/derivations/P02-composition-spec.md`), so
`HEAT-equilibrium` is a real row over real variables rather than a claim about an inner solve.
The heater *produces* the outlet stream, so it is the unit that allocates that split and authors
its five lifting rows; a downstream unit reading the same stream refers to the same variables.

**The inlet's phase regime is declared, not discovered.** An EO row needs to know which
enthalpy to write before it can be written, so the constructor takes the inlet's declared regime
and the evaluator performs blueprint §6.3's "final phase admissibility check".

That check is `tp_state.single_phase_admissible`, the same one the mixer uses, and for the same
reason: a comparison of phase *labels* refuses the registered SYN-001 recycle, which is a
saturated liquid that double precision places two ulps on the two-phase side. The first version
of this module compared labels while the mixer compared enthalpies, so the heater would have
refused a stream the mixer had just admitted. Found by the Fable review of K02.
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
    energy_row,
    offset_row,
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
    TEMPERATURE_TOLERANCE,
)
from openflowsheet.models.syn001.tp_state import (
    lift_two_phase_stream,
    single_phase_admissible,
    single_phase_enthalpy,
    tp_state,
)
from openflowsheet.thermo import Phase, PropertyProvider, StreamState

MODEL_ID: Final = "syn001.tp_heater"

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
        name="outlet",
        kind="material",
        direction="outlet",
        multiplicity=1,
        component_mapping="revision_component_set",
        state_definition="nTP-v1",
        phase_capabilities=("liquid", "vapor", "vapor_liquid"),
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
        equation_id="HEAT-mole",
        statement="n_in,i - n_out,i = 0 for every component i",
        dependencies=("inlet.state.n", "outlet.state.n"),
        conditional_class="unconditional",
        accumulation=Accumulation(
            kind="holdup_balance",
            holdup=Holdup(
                symbol="N_i", quantity="component moles held in the heater", dimension=MOLE
            ),
        ),
        dimension=MOLAR_FLOW,
        source=DERIVATION,
    ),
    DeclaredEquation(
        equation_id="HEAT-T",
        statement="T_out - T_spec = 0",
        dependencies=("specifications.SPEC-heater-outlet-T",),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=TEMPERATURE,
        source=DERIVATION,
    ),
    DeclaredEquation(
        equation_id="HEAT-pressure",
        statement="P_out - P_in + dP = 0 with dP = 0 declared",
        dependencies=("inlet.state.P", "outlet.state.P", "parameters.pressure_drop"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=PRESSURE,
        source=DERIVATION,
    ),
    DeclaredEquation(
        equation_id="HEAT-equilibrium",
        statement=(
            "the outlet is the TP flash result at (T_out, P_out): y_i = K_i(T,P) x_i for each "
            "flowing phase"
        ),
        dependencies=("outlet.state",),
        conditional_class="phase_conditional",
        accumulation=Accumulation(kind="algebraic"),
        source=DERIVATION,
    ),
    DeclaredEquation(
        equation_id="HEAT-duty",
        statement="Q - (Hdot_out - Hdot_in) = 0, Q positive into the unit",
        dependencies=("inlet.state", "outlet.state", "duty.Q"),
        conditional_class="unconditional",
        accumulation=Accumulation(
            kind="holdup_balance",
            holdup=Holdup(
                symbol="U", quantity="internal energy of the heater contents", dimension=ENERGY
            ),
        ),
        dimension=POWER,
        source=DERIVATION,
    ),
)

_SENSITIVITY_NOTE: Final = (
    "K02 implements the model and K01 supplies the residual derivative route, but the sensitivity "
    "of an outlet state to an inlet state runs through the inner TP flash and would need the "
    "implicit-function route of blueprint §5.1. K02 exposes no such interface, so this stays "
    "`unavailable` and is reported as absent rather than as zeros (blueprint §5.2)."
)


@cache
def _artifact_hash() -> str:
    return file_sha256(Path(__file__))


@dataclass(frozen=True)
class TPHeater:
    """One heater instance: a specified outlet temperature and a calculated duty."""

    unit_id: str
    provider: PropertyProvider
    outlet_temperature: float
    context: EvaluationContext
    #: The declared phase regime of the inlet stream, which fixes which enthalpy its rows write.
    #: `None` means the inlet's split is lifted by the unit that produces it.
    inlet_phase: Phase | None = "LIQUID"
    #: Declared pressure drop, Pa. Zero throughout SYN-001, and an explicit row either way
    #: (ADR 0001 D4.5): a unit copies its inlet pressure as an *equation*, not as an assumption.
    pressure_drop: float = 0.0
    #: A heater given both an outlet temperature and a duty is over-specified (ADR 0001 D4.4).
    specified_duty: float | None = None
    components: tuple[str, ...] = COMPONENTS

    def __post_init__(self) -> None:
        if self.specified_duty is not None:
            raise SpecificationError(
                f"{self.unit_id}: outlet temperature and duty are both fixed. ADR 0001 D4.4 "
                "rejects that at validation as a structural over-specification (STR-03); it is "
                "not a state at which the heater has an answer"
            )
        if not T_MIN <= self.outlet_temperature <= T_MAX:
            raise SpecificationError(
                f"{self.unit_id}: outlet temperature {self.outlet_temperature} K is outside the "
                f"declared domain [{T_MIN}, {T_MAX}] K"
            )

    @property
    def model_id(self) -> str:
        return MODEL_ID

    @property
    def temperature_parameter(self) -> str:
        return f"{self.unit_id}.T_spec"

    @property
    def pressure_drop_parameter(self) -> str:
        return f"{self.unit_id}.pressure_drop"

    # -- declaration -------------------------------------------------------------------------

    def ports(self) -> tuple[Port, ...]:
        return PORTS

    def declared_equations(self) -> tuple[DeclaredEquation, ...]:
        return EQUATIONS

    def manifest(self) -> Mapping[str, Any]:
        return manifest_document(
            model_id=MODEL_ID,
            title="SYN-001 heater with a TP-state outlet",
            description="Brings a stream to a specified outlet temperature; duty is calculated.",
            ports=PORTS,
            equations=EQUATIONS,
            derivatives=(
                DerivativeDeclaration(
                    output="outlet.state",
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
                        "The outlet's phase split is lifted into variables, so every row is "
                        "differentiable by CasADi through the K01 adapter, with the property "
                        "blocks supplying their own declared-sparse analytic derivatives. No "
                        "inner solve sits inside a residual evaluation."
                    ),
                ),
            ),
            initialization=Initialization(
                strategy="local_initializer",
                notes=(
                    "The TP flash kernel initializes its own Rachford-Rice bracket from the "
                    "K-values at the specified outlet state; no guess is carried across units."
                ),
            ),
            validity=Validity(
                components=self.components,
                phases=("liquid", "vapor", "vapor_liquid", "zero_flow"),
                limitations=(
                    "The duty may be negative: at r = 0.95 the mixer outlet is above the "
                    "setpoint and the unit removes about 16144.6 W. An implementation asserting "
                    "Q >= 0 fails the registered SYN-001-high-recycle variant (ADR 0001 D4.2).",
                    "A two-phase outlet is a supported result and occurs in three of the five "
                    "registered variants (derivation §7 finding 2).",
                    "A dormant inlet gives a dormant outlet and exactly zero duty (ADR 0001 D3.4).",
                    "Shares one TP-state kernel with the flash. No PH flash in v0.0.",
                    "The inlet's phase regime is declared at construction and checked after "
                    "evaluation (blueprint §6.3, fixed phase set with a final admissibility "
                    "check). The rows cannot be written without it.",
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
        outlet = wiring.one("outlet")
        duty = duty_id(self.unit_id)

        if self.inlet_phase is None:
            raise SpecificationError(
                f"{self.unit_id}: a lifted inlet split is not wired in v0.0. The SYN-001 heater "
                "reads the mixer outlet, which is restricted to the subcooled-liquid domain"
            )
        inlet_block, inlet_feeding, inlet_keys = single_phase_enthalpy(
            self.provider, self.components, self.context, inlet, self.inlet_phase
        )
        lifted, outlet_keys = lift_two_phase_stream(
            unit_id=self.unit_id,
            model_id=MODEL_ID,
            equilibrium_equation_id="HEAT-equilibrium",
            stream=outlet,
            provider=self.provider,
            components=self.components,
            context=self.context,
        )

        equations: list[EquationSpec] = []
        for component in self.components:
            equations.append(
                EquationSpec(
                    equation_id=row_id(self.unit_id, "HEAT-mole", component),
                    build=balance_row((flow_id(inlet, component),), (flow_id(outlet, component),)),
                    accumulation="holdup_balance",
                    origin=origin(MODEL_ID, "HEAT-mole"),
                )
            )
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "HEAT-T"),
                build=specification_row(temperature_id(outlet), self.temperature_parameter),
                accumulation="algebraic",
                origin=origin(MODEL_ID, "HEAT-T"),
            )
        )
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "HEAT-pressure"),
                build=offset_row(
                    pressure_id(outlet), pressure_id(inlet), self.pressure_drop_parameter
                ),
                accumulation="algebraic",
                origin=origin(MODEL_ID, "HEAT-pressure"),
            )
        )
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "HEAT-duty"),
                build=energy_row(inlet_keys, outlet_keys, source=duty),
                accumulation="holdup_balance",
                origin=origin(MODEL_ID, "HEAT-duty"),
            )
        )

        kinds: dict[str, QuantityKind] = {
            row_id(self.unit_id, "HEAT-mole", component): "molar_flow"
            for component in self.components
        }
        kinds[row_id(self.unit_id, "HEAT-T")] = "temperature"
        kinds[row_id(self.unit_id, "HEAT-pressure")] = "pressure"
        kinds[row_id(self.unit_id, "HEAT-duty")] = "heat_rate"

        return Contribution(
            variable_ids=(duty, *lifted.variable_ids),
            equations=(*equations, *lifted.equations),
            variable_kinds={duty: "heat_rate", **lifted.variable_kinds},
            row_kinds={**kinds, **lifted.row_kinds},
            blocks=(inlet_block, *lifted.blocks),
            block_inputs={inlet_block.block_id: inlet_feeding, **lifted.block_inputs},
            parameter_ids=(self.temperature_parameter, self.pressure_drop_parameter),
            parameters={
                self.temperature_parameter: float(self.outlet_temperature),
                self.pressure_drop_parameter: float(self.pressure_drop),
            },
        )

    # -- evaluator ---------------------------------------------------------------------------

    def evaluate(
        self, inlets: Mapping[str, Sequence[StreamState]], context: EvaluationContext
    ) -> UnitEvaluation:
        connected = tuple(inlets.get("inlet", ()))
        if len(connected) != 1 or set(inlets) - {"inlet"}:
            raise SpecificationError(
                f"{self.unit_id}: a heater takes exactly one inlet stream, got {inlets!r}"
            )
        feed = connected[0]
        if len(feed.n) != len(self.components):
            raise SpecificationError(
                f"{self.unit_id}: inlet carries {len(feed.n)} components, expected "
                f"{len(self.components)}"
            )
        outlet_pressure = feed.pressure - float(self.pressure_drop)

        if feed.is_dormant:
            # ADR 0001 D3.4: a dormant inlet gives a dormant outlet and exactly zero duty. The
            # provider is never consulted, because there is nothing to consult it about.
            dormant = StreamState(
                n=tuple(0.0 for _ in self.components),
                temperature=float(self.outlet_temperature),
                pressure=outlet_pressure,
            )
            return UnitEvaluation(
                status="ok",
                outlets={"outlet": dormant},
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
        if self.inlet_phase is not None:
            # Blueprint §6.3: a fixed phase set is allowed for a declared domain, with a final
            # admissibility check and a failure if the assumed regime is inconsistent. The test
            # is on the enthalpy the rows would write, converted to the temperature error it
            # would cause, not on the phase label -- see the module docstring.
            admissible, _, equivalent, status, message = single_phase_admissible(
                self.provider, feed, self.inlet_phase, self.components, context
            )
            if status != "ok":
                return UnitEvaluation(
                    status=status,
                    message=f"inlet admissibility: {message}",
                    reference_convention=REFERENCE_CONVENTION,
                )
            if not admissible:
                return UnitEvaluation(
                    status="unsupported",
                    message=(
                        f"the inlet was declared {self.inlet_phase}, and writing its enthalpy "
                        f"that way would be wrong by {equivalent:.3g} K, past the registered "
                        f"{TEMPERATURE_TOLERANCE:g} K. The rows were written for the declared "
                        "regime, so answering would be answering about a different function"
                    ),
                    reference_convention=REFERENCE_CONVENTION,
                )

        outlet_state = tp_state(
            self.provider,
            feed,
            context,
            temperature=float(self.outlet_temperature),
            pressure=outlet_pressure,
        )
        if outlet_state.status != "ok":
            return UnitEvaluation(
                status=outlet_state.status,
                message=f"outlet state: {outlet_state.message}",
                reference_convention=outlet_state.reference_convention,
            )
        assert inlet_state.enthalpy_flow is not None
        assert outlet_state.enthalpy_flow is not None

        outlet = StreamState(
            n=feed.n,
            temperature=float(self.outlet_temperature),
            pressure=outlet_pressure,
        )
        return UnitEvaluation(
            status="ok",
            outlets={"outlet": outlet},
            duty=outlet_state.enthalpy_flow - inlet_state.enthalpy_flow,
            phase_signature=outlet_state.phase_signature,
            iterations=inlet_state.iterations + outlet_state.iterations,
            provider_id=outlet_state.provider_id,
            reference_convention=outlet_state.reference_convention,
        )
