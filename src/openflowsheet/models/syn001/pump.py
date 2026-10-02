"""`syn001.liquid_pump` — a liquid pump to a specified outlet pressure and efficiency (T05 §9).

**The ideal work is the isothermal liquid enthalpy rise, and that is the isentropic work.**
SYN-001's liquid entropy does not depend on `P` (an incompressible liquid with `(dv/dT)_P = 0`),
so an isentropic compression is isothermal and its work is `int v dP = Hdot^L(n, T_in, P_out) -
Hdot^L(n, T_in, P_in)`. `PUMP-work` writes exactly that with a second liquid enthalpy block fed by
`(n_in, T_in, P_out)`, so no PS flash is needed (spec §9.3). A provider whose liquid entropy
depends on `P` would need one, and the manifest says so.

**Work is positive into the pump** (ADR 0001 D4.1) and is reported in `UnitEvaluation.work`; the
pump has no heat port, so `duty` is `None`. The excess `(1/eta - 1) W_s` heats the liquid.

**The inlet must be liquid**, checked by R-007's admissibility criterion rather than by a label,
so a saturated liquid (PUMP-4) is admitted and a vapour or two-phase inlet is the typed refusal
`inadmissible_phase(inlet, LIQUID)`. The inlet's phase is not configuration: a pump has one.
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
    temperature_id,
)
from openflowsheet.models.rows import balance_row, energy_row, specification_row, work_row
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
from openflowsheet.models.syn001.blocks import EnthalpyFlowBlock
from openflowsheet.models.syn001.ph_kernel import (
    MAX_EVALUATIONS,
    bracketed_root,
    port_enthalpy,
    typed_failure,
)
from openflowsheet.models.syn001.tp_state import (
    enthalpy_block_id,
    enthalpy_flow,
    single_phase_enthalpy,
)
from openflowsheet.thermo import PropertyProvider, PropertyStatus, StreamState

MODEL_ID: Final = "syn001.liquid_pump"

SPECIFICATION: Final = "docs/derivations/T05-unit-models-spec.md §9"

_NO_HOLDUP: Final = "an ideal machine with no inventory by the model's definition"

PORTS: Final[tuple[Port, ...]] = (
    Port(
        name="inlet",
        kind="material",
        direction="inlet",
        multiplicity=1,
        component_mapping="revision_component_set",
        state_definition="nTP-v1",
        phase_capabilities=("liquid",),
    ),
    Port(
        name="outlet",
        kind="material",
        direction="outlet",
        multiplicity=1,
        component_mapping="revision_component_set",
        state_definition="nTP-v1",
        phase_capabilities=("liquid",),
    ),
    Port(
        name="work",
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
        equation_id="PUMP-mole",
        statement="n_in,i - n_out,i = 0 for every component i",
        dependencies=("inlet.state.n", "outlet.state.n"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="zero_holdup_balance", reason=_NO_HOLDUP),
        dimension=MOLAR_FLOW,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="PUMP-P",
        statement="P_out - P_spec = 0",
        dependencies=("outlet.state.P", "parameters.P_spec"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=PRESSURE,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="PUMP-work",
        statement="eta W - [Hdot^L(n_in, T_in, P_out) - Hdot^L(n_in, T_in, P_in)] = 0",
        dependencies=("inlet.state", "outlet.state.P", "work.W", "parameters.efficiency"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=POWER,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="PUMP-energy",
        statement="W + Hdot_in - Hdot_out = 0, W positive into the unit (adiabatic)",
        dependencies=("inlet.state", "outlet.state", "work.W"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="zero_holdup_balance", reason=_NO_HOLDUP),
        dimension=POWER,
        source=SPECIFICATION,
    ),
)

_SENSITIVITY_NOTE: Final = (
    "The residual rows are differentiated exactly through K01, but the sensitivity of the outlet "
    "state or the work to the inlet state or a specification runs through the causal "
    "evaluator's inversion of the liquid enthalpy; no interface supplies it, so it is declared "
    "unavailable and reported as absent rather than as zeros (blueprint §5.2)."
)


def work_id(unit: str) -> str:
    """The free variable holding a machine's shaft work, W, positive into the unit (§3.2)."""
    return f"{unit}.W"


def isothermal_block_id(inlet: str) -> str:
    """The liquid enthalpy block fed by `(n_in, T_in, P_out)` (spec §3.2).

    Named after the inlet stream, which only one unit consumes, so it is unique per pump; the
    token rule is `enthalpy_block_id`'s.
    """
    return f"{enthalpy_block_id(inlet, 'LIQUID')}_isothermal"


@cache
def _artifact_hash() -> str:
    return file_sha256(Path(__file__))


@dataclass(frozen=True)
class LiquidPump:
    """One pump instance: a specified outlet pressure and efficiency; the work is calculated."""

    unit_id: str
    provider: PropertyProvider
    #: `P_spec`, Pa, in the provider's domain.
    outlet_pressure: float
    #: `eta` in `(0, 1]`.
    efficiency: float
    context: EvaluationContext
    components: tuple[str, ...] = COMPONENTS

    def __post_init__(self) -> None:
        if not 0.0 < self.efficiency <= 1.0:
            raise SpecificationError(
                "efficiency_outside_interval\n"
                f"{self.unit_id}: efficiency {self.efficiency} is outside (0, 1]"
            )
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

    @property
    def efficiency_parameter(self) -> str:
        return f"{self.unit_id}.efficiency"

    # -- declaration -------------------------------------------------------------------------

    def ports(self) -> tuple[Port, ...]:
        return PORTS

    def declared_equations(self) -> tuple[DeclaredEquation, ...]:
        return EQUATIONS

    def manifest(self) -> Mapping[str, Any]:
        return manifest_document(
            model_id=MODEL_ID,
            title="SYN-001 liquid pump",
            description=(
                "Raises a liquid to a specified outlet pressure at a specified efficiency; the "
                "shaft work and the outlet temperature are calculated."
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
                    output="work.W",
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
                        "Every row is written over flowsheet variables and three liquid "
                        "enthalpy blocks, and is differentiated exactly through the K01 adapter. "
                        "For SYN-001 the partial of PUMP-work with respect to T_in cancels "
                        "exactly: the isothermal rise does not depend on T_in."
                    ),
                ),
            ),
            initialization=Initialization(
                strategy="local_initializer",
                notes=(
                    "The causal evaluator: the ideal work from two liquid enthalpies, the "
                    "outlet temperature by a bracketed inversion of the outlet's liquid "
                    "enthalpy (T05 spec §9.2)."
                ),
            ),
            validity=Validity(
                components=self.components,
                phases=("liquid", "zero_flow"),
                limitations=(
                    "The ideal work is the isothermal liquid enthalpy rise, which equals the "
                    "isentropic work only because the provider's liquid entropy does not depend "
                    "on P (SYN-001: incompressible liquid). A provider whose liquid entropy "
                    "depends on P needs a PS route this model does not have (T05 spec §9.3).",
                    "A vapour or two-phase inlet is refused as inadmissible_phase(inlet, "
                    "LIQUID) by R-007's admissibility criterion; a saturated liquid is admitted.",
                    "The outlet pressure must not be below the inlet's: P_spec < P_in is "
                    "refused as pressure_fall(pump); it is an inequality on the state, not a "
                    "row.",
                    "A dormant inlet: the causal face labels the outlet with the inlet "
                    "temperature and reports W = 0. On the EO path under T05b-phase-contract-v2 "
                    "the outlet's zero-flow form swaps PUMP-energy for that label (T05b spec "
                    "§7.6-§7.7); under SolvePolicy's default, T03-phase-contract-v1, the declared "
                    "form runs, and a dormant inlet whose outlet label must move is not CONVERGED "
                    "(T05b spec §7.10, B26).",
                    "The shaft work W carries the heat_rate scaling kind (R-043).",
                ),
                temperature_k=(T_MIN, T_MAX),
                pressure_pa=(P_MIN, P_MAX),
            ),
            module=__name__,
            artifact_hash=_artifact_hash(),
            execution_class="native_equation",
            thread_safety="not_thread_safe",
            evaluation_cost_class="cheap",
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
        work = work_id(self.unit_id)

        inlet_block, inlet_feeding, inlet_keys = single_phase_enthalpy(
            self.provider, self.components, self.context, inlet, "LIQUID"
        )
        outlet_block, outlet_feeding, outlet_keys = single_phase_enthalpy(
            self.provider, self.components, self.context, outlet, "LIQUID"
        )
        raised_block = EnthalpyFlowBlock(
            self.provider,
            self.components,
            "LIQUID",
            self.context,
            block_id=isothermal_block_id(inlet),
        )
        raised_feeding = (
            *(flow_id(inlet, name) for name in self.components),
            temperature_id(inlet),
            pressure_id(outlet),
        )
        raised_keys = tuple(
            f"{raised_block.block_id}.{output}" for output in raised_block.output_ids
        )

        equations: list[EquationSpec] = []
        for component in self.components:
            equations.append(
                EquationSpec(
                    equation_id=row_id(self.unit_id, "PUMP-mole", component),
                    build=balance_row((flow_id(inlet, component),), (flow_id(outlet, component),)),
                    accumulation="zero_holdup_balance",
                    origin=origin(MODEL_ID, "PUMP-mole"),
                )
            )
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "PUMP-P"),
                build=specification_row(pressure_id(outlet), self.pressure_parameter),
                accumulation="algebraic",
                origin=origin(MODEL_ID, "PUMP-P"),
            )
        )
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "PUMP-work"),
                build=work_row(work, self.efficiency_parameter, raised_keys, inlet_keys),
                accumulation="algebraic",
                origin=origin(MODEL_ID, "PUMP-work"),
            )
        )
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "PUMP-energy"),
                build=energy_row(inlet_keys, outlet_keys, source=work),
                accumulation="zero_holdup_balance",
                origin=origin(MODEL_ID, "PUMP-energy"),
            )
        )

        kinds: dict[str, QuantityKind] = {
            row_id(self.unit_id, "PUMP-mole", component): "molar_flow"
            for component in self.components
        }
        kinds[row_id(self.unit_id, "PUMP-P")] = "pressure"
        kinds[row_id(self.unit_id, "PUMP-work")] = "heat_rate"
        kinds[row_id(self.unit_id, "PUMP-energy")] = "heat_rate"

        return Contribution(
            variable_ids=(work,),
            equations=tuple(equations),
            # R-043: W is scaled as a heat rate; a new scaling kind would move K04's policy hash.
            variable_kinds={work: "heat_rate"},
            row_kinds=kinds,
            blocks=(inlet_block, outlet_block, raised_block),
            block_inputs={
                inlet_block.block_id: inlet_feeding,
                outlet_block.block_id: outlet_feeding,
                raised_block.block_id: raised_feeding,
            },
            parameter_ids=(self.pressure_parameter, self.efficiency_parameter),
            parameters={
                self.pressure_parameter: float(self.outlet_pressure),
                self.efficiency_parameter: float(self.efficiency),
            },
        )

    # -- evaluator ---------------------------------------------------------------------------

    def evaluate(
        self, inlets: Mapping[str, Sequence[StreamState]], context: EvaluationContext
    ) -> UnitEvaluation:
        connected = tuple(inlets.get("inlet", ()))
        if len(connected) != 1 or set(inlets) - {"inlet"}:
            raise SpecificationError(
                f"{self.unit_id}: a pump takes exactly one inlet stream, got {inlets!r}"
            )
        feed = connected[0]
        if len(feed.n) != len(self.components):
            raise SpecificationError(
                f"{self.unit_id}: inlet carries {len(feed.n)} components, expected "
                f"{len(self.components)}"
            )
        outlet_pressure = float(self.outlet_pressure)

        # (1) Dormant: zero work, the outlet temperature a retained label (spec §4.7).
        if feed.is_dormant:
            dormant = StreamState(
                n=tuple(0.0 for _ in self.components),
                temperature=feed.temperature,
                pressure=outlet_pressure,
            )
            return UnitEvaluation(
                status="ok",
                outlets={"outlet": dormant},
                work=0.0,
                phase_signature="ZERO_FLOW",
                reference_convention=REFERENCE_CONVENTION,
            )

        # (2)
        if outlet_pressure < feed.pressure:
            return typed_failure(
                "out_of_domain",
                "pressure_fall(pump)",
                f"P_spec = {outlet_pressure} Pa is below the inlet's {feed.pressure} Pa",
            )

        # (3) R-007 on the inlet as liquid; its enthalpy is the single-phase one the rows write.
        inlet = port_enthalpy(self.provider, feed, "LIQUID", self.components, context, port="inlet")
        if inlet.failure is not None:
            return inlet.failure
        assert inlet.enthalpy_flow is not None

        # (4) The ideal work: the isothermal liquid enthalpy rise.
        status, raised, message = enthalpy_flow(
            self.provider,
            StreamState(n=feed.n, temperature=feed.temperature, pressure=outlet_pressure),
            "LIQUID",
            self.components,
            context,
        )
        if status != "ok":
            return _surfaced(status, "isothermal outlet enthalpy", message)
        ideal = raised - inlet.enthalpy_flow
        work = ideal / float(self.efficiency)

        # (5) T_out from Hdot^L(n, T_out, P_spec) = Hdot_in + W, a bracketed inversion.
        target = inlet.enthalpy_flow + work
        inverted = self._invert_liquid_enthalpy(feed.n, outlet_pressure, target, context)
        if isinstance(inverted, UnitEvaluation):
            return inverted
        temperature, evaluations = inverted
        outlet = StreamState(n=feed.n, temperature=temperature, pressure=outlet_pressure)

        # (6) R-007 on the outlet.
        checked = port_enthalpy(
            self.provider, outlet, "LIQUID", self.components, context, port="outlet"
        )
        if checked.failure is not None:
            return checked.failure

        return UnitEvaluation(
            status="ok",
            outlets={"outlet": outlet},
            work=work,
            phase_signature="LIQUID",
            iterations=evaluations,
            provider_id=PROVIDER_ID,
            reference_convention=REFERENCE_CONVENTION,
        )

    def _invert_liquid_enthalpy(
        self,
        flows: tuple[float, ...],
        pressure: float,
        target: float,
        context: EvaluationContext,
    ) -> tuple[float, int] | UnitEvaluation:
        """Solve `Hdot^L(n, T, P) = target` for `T` on the domain; strictly increasing in `T`."""

        def g(temperature: float) -> tuple[float, None]:
            status, value, message = enthalpy_flow(
                self.provider,
                StreamState(n=flows, temperature=temperature, pressure=pressure),
                "LIQUID",
                self.components,
                context,
            )
            if status != "ok":
                raise _RefusedError(
                    _surfaced(status, f"outlet enthalpy at T = {temperature!r}", message)
                )
            return value - target, None

        try:
            g_lo, _ = g(T_MIN)
            g_hi, _ = g(T_MAX)
            if g_lo > 0.0 or g_hi < 0.0:
                return typed_failure(
                    "out_of_domain",
                    "outlet_outside_domain",
                    "the outlet temperature the energy balance requires is outside "
                    f"[{T_MIN}, {T_MAX}] K",
                )
            root = bracketed_root(
                g, (T_MIN, g_lo, None), (T_MAX, g_hi, None), evaluations=2, budget=MAX_EVALUATIONS
            )
        except _RefusedError as refused:
            return refused.answer
        if not root.converged:
            # Bisection between two doubles in [T_MIN, T_MAX] closes in at most about 60 halvings,
            # so this is a broken invariant, not a state of the model: no code is registered for
            # it and none is invented.
            raise RuntimeError(
                f"{self.unit_id}: the liquid-enthalpy inversion did not close in "
                f"{MAX_EVALUATIONS} evaluations"
            )
        return root.point, root.evaluations


class _RefusedError(Exception):
    """A provider refusal inside the inversion; carries the unit's answer."""

    def __init__(self, answer: UnitEvaluation) -> None:
        super().__init__(answer.message)
        self.answer = answer


def _surfaced(status: PropertyStatus, what: str, detail: str) -> UnitEvaluation:
    """A provider refusal the pump has no code for, surfaced with its own status (§3.3)."""
    if status == "out_of_domain":
        return typed_failure(status, "state_outside_domain(outlet)", f"{what}: {detail}")
    return UnitEvaluation(
        status=status, message=f"{what}: {detail}", reference_convention=REFERENCE_CONVENTION
    )
