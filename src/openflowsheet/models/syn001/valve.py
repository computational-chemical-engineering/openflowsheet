"""`syn001.valve` — an isenthalpic throttle to a specified outlet pressure (T05 spec §8).

The outlet is a lifted TP-state stream, heater style (`lift_two_phase_stream`), whose temperature
is a free column fixed by `VLV-energy`: flashing across the valve is a supported result. There is
no energy port: the valve is adiabatic and does no work by definition, so `UnitEvaluation.duty` is
`None`, not `0.0`.

**Why the outlet pressure and not a drop** (R-040): both reference tools model a valve this way,
and an outlet-pressure row fixes a node of the pressure network, so a loop through a valve closes
on a specification rather than on a sum of drops.

**The direction constraint `P_out <= P_in` is an inequality on the state**, so it is a validity
check and not a row: the causal evaluator refuses `P_spec > P_in` as `pressure_rise(valve)` and
the verifier checks it on a converged state (spec §12). Equality is allowed.
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
    Initialization,
    Port,
    SpecificationError,
    UnitEvaluation,
    Validity,
    Wiring,
    flow_id,
    manifest_document,
    origin,
    pressure_id,
    row_id,
)
from openflowsheet.models.rows import balance_row, energy_row, specification_row
from openflowsheet.models.syn001 import (
    COMPONENTS,
    MOLAR_FLOW,
    P_MAX,
    P_MIN,
    POWER,
    PRESSURE,
    PROVIDER_ID,
    REFERENCE_CONVENTION,
    T_MAX,
    T_MIN,
)
from openflowsheet.models.syn001.ph_kernel import (
    PHState,
    closure_failure,
    ph_state,
    port_enthalpy,
    typed_failure,
)
from openflowsheet.models.syn001.tp_state import lift_two_phase_stream, stream_enthalpy_terms
from openflowsheet.thermo import Phase, PropertyProvider, StreamState

MODEL_ID: Final = "syn001.valve"

SPECIFICATION: Final = "docs/derivations/T05-unit-models-spec.md §8"

_NO_HOLDUP: Final = "a throttling point with no volume by the model's definition"

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
)

EQUATIONS: Final[tuple[DeclaredEquation, ...]] = (
    DeclaredEquation(
        equation_id="VLV-mole",
        statement="n_in,i - n_out,i = 0 for every component i",
        dependencies=("inlet.state.n", "outlet.state.n"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="zero_holdup_balance", reason=_NO_HOLDUP),
        dimension=MOLAR_FLOW,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="VLV-P",
        statement="P_out - P_spec = 0",
        dependencies=("outlet.state.P", "parameters.P_spec"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=PRESSURE,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="VLV-energy",
        statement="Hdot_in - Hdot_out = 0 (adiabatic, no work: isenthalpic)",
        dependencies=("inlet.state", "outlet.state"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="zero_holdup_balance", reason=_NO_HOLDUP),
        dimension=POWER,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="VLV-equilibrium",
        statement=(
            "the outlet is the TP flash result at (T_out, P_out): v_i L - K_i(T_out, P_out) l_i V "
            "= 0 over the outlet's lifted split"
        ),
        dependencies=("outlet.state",),
        conditional_class="phase_conditional",
        accumulation=Accumulation(kind="algebraic"),
        source=SPECIFICATION,
    ),
)

_SENSITIVITY_NOTE: Final = (
    "The residual rows are differentiated exactly through K01, but the sensitivity of the outlet "
    "state to the inlet state or the outlet pressure runs through the PH closure, whose implicit "
    "dT/dH* changes slope at every phase boundary; no interface supplies it, so it is declared "
    "unavailable and reported as absent rather than as zeros (T05 spec §4.5, blueprint §5.2)."
)


@cache
def _artifact_hash() -> str:
    return file_sha256(Path(__file__))


@dataclass(frozen=True)
class Valve:
    """One valve instance: a specified outlet pressure; the outlet temperature is calculated."""

    unit_id: str
    provider: PropertyProvider
    #: `P_spec`, Pa, in the provider's domain.
    outlet_pressure: float
    context: EvaluationContext
    #: The declared regime of the inlet; `None` means its split is lifted by its producer.
    inlet_phase: Phase | None = "LIQUID"
    components: tuple[str, ...] = COMPONENTS

    def __post_init__(self) -> None:
        if not P_MIN <= self.outlet_pressure <= P_MAX:
            raise SpecificationError(
                "pressure_outside_domain(outlet_pressure)\n"
                f"{self.unit_id}: outlet pressure {self.outlet_pressure} Pa is outside the "
                f"declared domain [{P_MIN}, {P_MAX}] Pa"
            )

    @property
    def model_id(self) -> str:
        return MODEL_ID

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
            title="SYN-001 valve",
            description=(
                "Isenthalpic throttle to a specified outlet pressure; the outlet temperature and "
                "phase split are calculated."
            ),
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
                    output="residuals",
                    with_respect_to=("free_variables",),
                    method="ad",
                    regime="all",
                    notes=(
                        "The outlet's phase split is lifted into variables and its temperature "
                        "is a free column fixed by the energy row, so every row is differentiated "
                        "exactly through the K01 adapter; the K-value and enthalpy blocks supply "
                        "their declared-sparse analytic derivatives (T05 spec §4.5)."
                    ),
                ),
            ),
            initialization=Initialization(
                strategy="local_initializer",
                notes=(
                    "The causal evaluator: the PH kernel at the specified outlet pressure and "
                    "the inlet's enthalpy (T05 spec §4.4)."
                ),
            ),
            validity=Validity(
                components=self.components,
                phases=("liquid", "vapor", "vapor_liquid", "zero_flow"),
                limitations=(
                    "Ideal VLE from the provider's TP flash; no third phase (T05 spec §4.6). A "
                    "two-phase outlet is a supported result: flashing across the valve.",
                    "The outlet pressure must not exceed the inlet's: P_spec > P_in is refused as "
                    "pressure_rise(valve) by the evaluator and checked by the verifier; it is an "
                    "inequality on the state, not a row (R-040).",
                    "A single flowing component takes the PH kernel's saturation route (T05 spec "
                    "§4.4). A dormant inlet: the causal face labels the outlet with the inlet "
                    "temperature.",
                    "Every answer of the PH kernel is accepted only if the closure's energy, "
                    "equilibrium and material rows hold at K04's registered tolerances, the "
                    "provider's K and h taken as exact; a near-pure outlet enthalpy inside the "
                    "latent jump that the temperature route misses is answered by the "
                    "saturation-band route. Above about 1e8 mol/s, where tau_E is below the "
                    "double resolution of H, the answer is ph_ill_conditioned (T05b spec "
                    "§5.1-§5.3).",
                    "On the EO path a single flowing component in the latent jump, a near-pure "
                    "outlet and a dormant inlet are solved and certified under the phase contract "
                    "T05b-phase-contract-v2 (T05b spec §11). SolvePolicy's default, "
                    "T03-phase-contract-v1, keeps T05's contract rules verbatim: under it a "
                    "single flowing component in the jump is never VERIFIED and a dormant outlet "
                    "whose label must move is not CONVERGED (T05b spec §6.6, B08-B10, B16).",
                    "Relies on Hdot_TP being strictly increasing in T on the domain, which "
                    "holds for SYN-001 (T05 spec §4.2) and is not a PropertyCapabilities field.",
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
            package="T05",
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

        inlet_keys, inlet_blocks, inlet_inputs = stream_enthalpy_terms(
            self.provider, self.components, self.context, inlet, self.inlet_phase
        )
        lifted, outlet_keys = lift_two_phase_stream(
            unit_id=self.unit_id,
            model_id=MODEL_ID,
            equilibrium_equation_id="VLV-equilibrium",
            stream=outlet,
            provider=self.provider,
            components=self.components,
            context=self.context,
        )

        equations: list[EquationSpec] = []
        for component in self.components:
            equations.append(
                EquationSpec(
                    equation_id=row_id(self.unit_id, "VLV-mole", component),
                    build=balance_row((flow_id(inlet, component),), (flow_id(outlet, component),)),
                    accumulation="zero_holdup_balance",
                    origin=origin(MODEL_ID, "VLV-mole"),
                )
            )
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "VLV-P"),
                build=specification_row(pressure_id(outlet), self.pressure_parameter),
                accumulation="algebraic",
                origin=origin(MODEL_ID, "VLV-P"),
            )
        )
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "VLV-energy"),
                build=energy_row(inlet_keys, outlet_keys),
                accumulation="zero_holdup_balance",
                origin=origin(MODEL_ID, "VLV-energy"),
            )
        )

        kinds: dict[str, QuantityKind] = {
            row_id(self.unit_id, "VLV-mole", component): "molar_flow"
            for component in self.components
        }
        kinds[row_id(self.unit_id, "VLV-P")] = "pressure"
        kinds[row_id(self.unit_id, "VLV-energy")] = "heat_rate"

        return Contribution(
            variable_ids=lifted.variable_ids,
            equations=(*equations, *lifted.equations),
            variable_kinds=dict(lifted.variable_kinds),
            row_kinds={**kinds, **lifted.row_kinds},
            blocks=(*inlet_blocks, *lifted.blocks),
            block_inputs={**inlet_inputs, **lifted.block_inputs},
            parameter_ids=(self.pressure_parameter,),
            parameters={self.pressure_parameter: float(self.outlet_pressure)},
        )

    # -- evaluator ---------------------------------------------------------------------------

    def evaluate(
        self, inlets: Mapping[str, Sequence[StreamState]], context: EvaluationContext
    ) -> UnitEvaluation:
        return self.evaluate_with_closure(inlets, context)[0]

    def evaluate_with_closure(
        self, inlets: Mapping[str, Sequence[StreamState]], context: EvaluationContext
    ) -> tuple[UnitEvaluation, PHState | None]:
        """`evaluate`, and the PH kernel's answer (route and lifted split) where it was reached."""
        connected = tuple(inlets.get("inlet", ()))
        if len(connected) != 1 or set(inlets) - {"inlet"}:
            raise SpecificationError(
                f"{self.unit_id}: a valve takes exactly one inlet stream, got {inlets!r}"
            )
        feed = connected[0]
        if len(feed.n) != len(self.components):
            raise SpecificationError(
                f"{self.unit_id}: inlet carries {len(feed.n)} components, expected "
                f"{len(self.components)}"
            )
        outlet_pressure = float(self.outlet_pressure)

        # Dormant: the outlet temperature is a retained label, the inlet's (spec §4.7).
        if feed.is_dormant:
            dormant = StreamState(
                n=tuple(0.0 for _ in self.components),
                temperature=feed.temperature,
                pressure=outlet_pressure,
            )
            return (
                UnitEvaluation(
                    status="ok",
                    outlets={"outlet": dormant},
                    phase_signature="ZERO_FLOW",
                    reference_convention=REFERENCE_CONVENTION,
                ),
                None,
            )

        # Direction.
        if outlet_pressure > feed.pressure:
            return (
                typed_failure(
                    "out_of_domain",
                    "pressure_rise(valve)",
                    f"P_spec = {outlet_pressure} Pa exceeds the inlet's {feed.pressure} Pa",
                ),
                None,
            )

        # Inlet enthalpy (spec §5.2 (3)).
        inlet = port_enthalpy(
            self.provider, feed, self.inlet_phase, self.components, context, port="inlet"
        )
        if inlet.failure is not None:
            return inlet.failure, None
        assert inlet.enthalpy_flow is not None

        closure = ph_state(self.provider, feed.n, outlet_pressure, inlet.enthalpy_flow, context)
        if closure.status != "ok":
            return closure_failure(closure), closure
        assert closure.temperature is not None and closure.split is not None

        return (
            UnitEvaluation(
                status="ok",
                outlets={
                    "outlet": StreamState(
                        n=feed.n, temperature=closure.temperature, pressure=outlet_pressure
                    )
                },
                phase_signature=closure.split.phase_signature,
                iterations=closure.evaluations,
                provider_id=closure.split.provider_id,
                reference_convention=closure.split.reference_convention,
                closure=closure,
            ),
            closure,
        )
