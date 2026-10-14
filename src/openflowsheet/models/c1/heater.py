"""`c1.tp_heater` — a C1 vapour heated or cooled to a specified temperature (design note §8, §14.2
B16; M02 WO-8.2).

**Rows.** Component balances `n_in,i − n_out,i`, the outlet temperature `T_out − T_spec`, the
pressure `P_out − P_in + dP` (dP = 0 declared, a zero-only parameter), and the duty
`Q − (Ḣ_V(out) − Ḣ_V(in)) = 0` over the vapour enthalpy-flow blocks, Q positive into the unit.
Nothing is lifted: the outlet port is `vapor`.

**Phase.** The regime lattice is {VAPOR, ZERO_FLOW}. A flowing inlet and the outlet must each be
VAPOR by M01 §7 rule 3 with τ_dew (`classify`), else the causal evaluate refuses
`vapour_phase_inadmissible` (B16); there is no solve-time screen, and a solve converging with the
outlet two-phase fails the certificate's declared-port check. A cooler into the two-phase region
is modelled as `c1.tp_flash` (design note §8).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
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
from openflowsheet.models.c1 import (
    COMPONENTS,
    ENERGY,
    MOLAR_FLOW,
    MOLE,
    POWER,
    PRESSURE,
    PROVIDER_ID,
    REFERENCE_CONVENTION,
    TEMPERATURE,
)
from openflowsheet.models.c1.blocks import VapourEnthalpyFlow, block_feeding, hdot_block_id
from openflowsheet.models.c1.units import (
    DESIGN_NOTE,
    P_RANGE,
    PACKAGE,
    T_RANGE,
    c1_components,
    c1_provider,
    enthalpy_flow,
    vapour_refusal,
)
from openflowsheet.models.rows import balance_row, energy_row, offset_row, specification_row
from openflowsheet.thermo import PropertyProvider, StreamState
from openflowsheet.thermo.pr_c1 import T_MAX, T_MIN

MODEL_ID: Final = "c1.tp_heater"

PORTS: Final[tuple[Port, ...]] = (
    Port(
        name="inlet",
        kind="material",
        direction="inlet",
        multiplicity=1,
        component_mapping="revision_component_set",
        state_definition="nTP-v1",
        phase_capabilities=("vapor",),
    ),
    Port(
        name="outlet",
        kind="material",
        direction="outlet",
        multiplicity=1,
        component_mapping="revision_component_set",
        state_definition="nTP-v1",
        phase_capabilities=("vapor",),
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
        equation_id="C1HEAT-mole",
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
        source=DESIGN_NOTE,
    ),
    DeclaredEquation(
        equation_id="C1HEAT-T",
        statement="T_out - T_spec = 0",
        dependencies=("specifications.SPEC-heater-outlet-T",),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=TEMPERATURE,
        source=DESIGN_NOTE,
    ),
    DeclaredEquation(
        equation_id="C1HEAT-pressure",
        statement="P_out - P_in + dP = 0 with dP = 0 declared",
        dependencies=("inlet.state.P", "outlet.state.P", "parameters.pressure_drop"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=PRESSURE,
        source=DESIGN_NOTE,
    ),
    DeclaredEquation(
        equation_id="C1HEAT-duty",
        statement=(
            "Q - (Hdot_V(out) - Hdot_V(in)) = 0, Q positive into the unit; Hdot_V = Sum(n) h of "
            "the pr-c1-v1 vapour, 0 with the ideal-gas flow derivatives at an exactly dormant "
            "stream (design note §14.2 B17)"
        ),
        dependencies=("inlet.state", "outlet.state", "duty.Q"),
        conditional_class="unconditional",
        accumulation=Accumulation(
            kind="holdup_balance",
            holdup=Holdup(
                symbol="U", quantity="internal energy of the heater contents", dimension=ENERGY
            ),
        ),
        dimension=POWER,
        source=DESIGN_NOTE,
    ),
)


def _artifact_hash() -> str:
    """The module source's SHA-256. Not cached: T07 G20 lists every per-process cache, and this
    one would only save a file read per manifest (build log D37 (f))."""
    return file_sha256(Path(__file__))


@dataclass(frozen=True)
class TPHeater:
    """One C1 vapour heater or cooler at a specified outlet temperature."""

    unit_id: str
    provider: PropertyProvider
    outlet_temperature: float
    context: EvaluationContext
    pressure_drop: float = 0.0
    components: tuple[str, ...] = COMPONENTS

    def __post_init__(self) -> None:
        c1_components(self.unit_id, self.components)
        c1_provider(self.unit_id, self.provider)
        if not T_MIN <= self.outlet_temperature <= T_MAX:
            raise SpecificationError(
                f"{self.unit_id}: specified outlet temperature {self.outlet_temperature} K is "
                f"outside the provider's domain [{T_MIN}, {T_MAX}] K"
            )
        if self.pressure_drop != 0.0:
            raise SpecificationError(
                f"{self.unit_id}: pressure drop {self.pressure_drop} Pa; the C1 heater declares "
                "dP = 0"
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

    def ports(self) -> tuple[Port, ...]:
        return PORTS

    def declared_equations(self) -> tuple[DeclaredEquation, ...]:
        return EQUATIONS

    def manifest(self) -> Mapping[str, Any]:
        return manifest_document(
            model_id=MODEL_ID,
            title="C1 vapour heater",
            description=(
                "Heats or cools a C1 vapour to a specified temperature at zero pressure drop."
            ),
            ports=PORTS,
            equations=EQUATIONS,
            derivatives=(
                DerivativeDeclaration(
                    output="residuals",
                    with_respect_to=("free_variables",),
                    method="ad",
                    regime="all",
                    notes=(
                        "Balances and specifications are affine; the duty row reads vapour "
                        "enthalpy-flow blocks with the provider's analytic derivatives "
                        "(M01 §4.6), and B17's ideal-gas limit at an exactly dormant stream."
                    ),
                ),
            ),
            initialization=Initialization(
                strategy="local_initializer",
                notes="The outlet is the inlet at T_spec; the duty is the enthalpy difference.",
            ),
            validity=Validity(
                components=self.components,
                phases=("vapor", "zero_flow"),
                limitations=(
                    f"Vapour only, on {PROVIDER_ID} under {REFERENCE_CONVENTION}: a flowing "
                    "inlet and the outlet must be VAPOR by M01 spec §7 rule 3 with tau_dew = "
                    "1e-10; otherwise the causal evaluate refuses vapour_phase_inadmissible. A "
                    "cooler into the two-phase region is modelled as c1.tp_flash (R-230).",
                    "No solve-time screen of the outlet: a solve converging with it two-phase is "
                    "CONVERGED with a FAILED certificate naming its declared-port check "
                    "(design note §14.2 B15, B16).",
                    "Zero pressure drop only (dP = 0 declared).",
                    "A dormant inlet gives a dormant outlet labelled T_spec and exactly zero "
                    "duty (ADR 0001 D3.4); the vapour enthalpy flow there is 0 with the "
                    "ideal-gas flow derivatives (B17).",
                    "Light gases never condense and the only liquid is pure NH3 (R-143).",
                ),
                temperature_k=T_RANGE,
                pressure_pa=P_RANGE,
            ),
            module=__name__,
            artifact_hash=_artifact_hash(),
            execution_class="native_equation",
            thread_safety="not_thread_safe",
            evaluation_cost_class="moderate",
            property_provider=PROVIDER_ID,
            reference_convention=REFERENCE_CONVENTION,
            package=PACKAGE,
        )

    def contribute(self, wiring: Wiring, components: Sequence[str]) -> Contribution:
        if tuple(components) != self.components:
            raise SpecificationError(
                f"{self.unit_id}: wired into components {tuple(components)}, built for "
                f"{self.components}"
            )
        inlet, outlet = wiring.one("inlet"), wiring.one("outlet")
        duty = duty_id(self.unit_id)
        blocks = [
            VapourEnthalpyFlow(self.provider, self.context, block_id=hdot_block_id(stream, "VAPOR"))
            for stream in (inlet, outlet)
        ]
        inlet_key, outlet_key = (f"{block.block_id}.{block.output_ids[0]}" for block in blocks)

        equations: list[EquationSpec] = [
            EquationSpec(
                equation_id=row_id(self.unit_id, "C1HEAT-mole", component),
                build=balance_row((flow_id(inlet, component),), (flow_id(outlet, component),)),
                accumulation="holdup_balance",
                origin=origin(MODEL_ID, "C1HEAT-mole"),
            )
            for component in self.components
        ]
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "C1HEAT-T"),
                build=specification_row(temperature_id(outlet), self.temperature_parameter),
                accumulation="algebraic",
                origin=origin(MODEL_ID, "C1HEAT-T"),
            )
        )
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "C1HEAT-pressure"),
                build=offset_row(
                    pressure_id(outlet), pressure_id(inlet), self.pressure_drop_parameter
                ),
                accumulation="algebraic",
                origin=origin(MODEL_ID, "C1HEAT-pressure"),
            )
        )
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "C1HEAT-duty"),
                build=energy_row((inlet_key,), (outlet_key,), source=duty),
                accumulation="holdup_balance",
                origin=origin(MODEL_ID, "C1HEAT-duty"),
            )
        )
        kinds: dict[str, QuantityKind] = {
            row_id(self.unit_id, "C1HEAT-mole", component): "molar_flow"
            for component in self.components
        }
        kinds[row_id(self.unit_id, "C1HEAT-T")] = "temperature"
        kinds[row_id(self.unit_id, "C1HEAT-pressure")] = "pressure"
        kinds[row_id(self.unit_id, "C1HEAT-duty")] = "heat_rate"
        return Contribution(
            variable_ids=(duty,),
            equations=tuple(equations),
            blocks=tuple(blocks),
            block_inputs={
                block.block_id: block_feeding(stream)
                for block, stream in zip(blocks, (inlet, outlet), strict=True)
            },
            parameter_ids=(self.temperature_parameter, self.pressure_drop_parameter),
            parameters={
                self.temperature_parameter: float(self.outlet_temperature),
                self.pressure_drop_parameter: float(self.pressure_drop),
            },
            variable_kinds={duty: "heat_rate"},
            row_kinds=kinds,
        )

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
        outlet = StreamState(
            n=feed.n,
            temperature=float(self.outlet_temperature),
            pressure=feed.pressure - float(self.pressure_drop),
        )
        if feed.is_dormant:
            # ADR 0001 D3.4: a dormant inlet, a dormant outlet labelled T_spec, exactly zero duty.
            return UnitEvaluation(
                status="ok",
                outlets={
                    "outlet": StreamState(
                        n=(0.0,) * 5, temperature=outlet.temperature, pressure=outlet.pressure
                    )
                },
                duty=0.0,
                phase_signature="ZERO_FLOW",
                reference_convention=REFERENCE_CONVENTION,
            )
        for where, stream in (("inlet", feed), ("outlet", outlet)):
            refused = vapour_refusal(self.provider, context, where, stream)
            if refused is not None:
                return refused
        h_in, failure = enthalpy_flow(self.provider, context, feed, "VAPOR")
        if failure is not None:
            return failure
        h_out, failure = enthalpy_flow(self.provider, context, outlet, "VAPOR")
        if failure is not None:
            return failure
        return UnitEvaluation(
            status="ok",
            outlets={"outlet": outlet},
            duty=h_out - h_in,
            phase_signature="VAPOR",
            provider_id=PROVIDER_ID,
            reference_convention=REFERENCE_CONVENTION,
        )
