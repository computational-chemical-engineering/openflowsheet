"""`syn001.heat_exchanger` — one duty-coupled, countercurrent two-stream exchanger (T05 spec §10).

Two sides, each a stream in one **declared** phase at constant pressure, coupled by the heat `Q`
the hot side gives the cold side. One specification closes it: the cold outlet temperature, the
hot outlet temperature, or the duty. The shell is adiabatic, so the unit has **no energy port**:
its external duty is identically zero, and `UnitEvaluation.duty` is `None`. `Q` is an owned
variable with the declared mapping ADR 0001 D4.1 requires of a unit with another convention —
the duty into the cold side and minus the duty into the hot side — and the evaluator reports it
as `transferred_duty`.

**Why the second-law check is three inequalities** (spec §10.4, R-042). For a side in one phase
at constant pressure with SYN-001's constant `c_p`, `Hdot` is affine in `T`, so the temperature
difference along a countercurrent exchanger is affine in the transferred heat and its minimum is
at a terminal. Heat flows from hot to cold everywhere iff `Q >= 0` and both terminal differences
are `>= 0` — exact, not an approximation, for this class. A pinch (a terminal difference of
exactly zero) is allowed. A side that changes phase would make the profile piecewise and need a
zoned check; v0.1 refuses it through R-007 on each port (§19 Q2), which is why every port is in a
declared phase and none is lifted (R-039).

**The typed failures are ordered** (spec §10.2), and each registered failure case fails exactly
one of them. `assess` evaluates every check it can, so that a test sees the whole list, and
`evaluate` returns the first. Three checks end the assessment because nothing after them is
defined: a dormant side whose specification cannot hold, an inadmissible inlet, and an outlet
temperature outside the domain.

**Inverting a declared-phase enthalpy.** The side that is not specified gets its outlet
temperature from `Hdot_phase(n, T, P) = target`. The domain endpoints bracket the root exactly
when the target lies between their enthalpies (the declared-phase enthalpy increases in `T`), so
"outside the domain" is decided before any iteration; inside, a Newton step safeguarded by the
bracket converges — in one step for SYN-001's affine enthalpy, and to adjacent doubles by
bisection for any increasing one.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Final, Literal

from openflowsheet.canonical import file_sha256
from openflowsheet.compile.spec import EquationSpec, PropertyBlock, QuantityKind
from openflowsheet.compiled import EvaluationContext, PhaseSignature
from openflowsheet.models import (
    Accumulation,
    Contribution,
    DeclaredEquation,
    DerivativeDeclaration,
    Dimension,
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
from openflowsheet.models.rows import balance_row, energy_row, specification_row
from openflowsheet.models.syn001 import (
    COMPONENTS,
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
)
from openflowsheet.models.syn001.admission import admitted_enthalpy, provider_refusal
from openflowsheet.models.syn001.tp_state import single_phase_enthalpy
from openflowsheet.thermo import (
    Phase,
    PropertyProvider,
    PropertyRequest,
    PropertyStatus,
    StreamState,
)

MODEL_ID: Final = "syn001.heat_exchanger"

#: Where the equations are stated. T05's models cite their own specification, not SYN-001 §4.
SPECIFICATION: Final = "docs/derivations/T05-unit-models-spec.md §10"

Specification = Literal["cold_outlet_temperature", "hot_outlet_temperature", "duty"]
SPECIFICATIONS: Final[tuple[Specification, ...]] = (
    "cold_outlet_temperature",
    "hot_outlet_temperature",
    "duty",
)

_DECLARABLE: Final[tuple[Phase, ...]] = ("LIQUID", "VAPOR")

#: The registered codes of spec §10.2 that take no argument (§13.3).
DORMANT_SIDE: Final = "specification_unsatisfiable_with_dormant_side"
OUTLET_OUTSIDE_DOMAIN: Final = "outlet_outside_domain"
HEAT_FLOW_REVERSED: Final = "heat_flow_reversed"
CROSS_HOT_END: Final = "temperature_cross(hot_end)"
CROSS_COLD_END: Final = "temperature_cross(cold_end)"

#: A bisection on a bracket of doubles ends when no double lies between its ends; 200 halvings
#: exceed the 64 needed to get there from any finite interval, so hitting the cap is a bug.
_MAX_ITERATIONS: Final = 200


def unknown_specification(name: str) -> str:
    """The registered construction code for a specification mode §10.1 does not offer."""
    return f"unknown_specification({name})"


def _material_port(name: str, direction: Literal["inlet", "outlet"]) -> Port:
    return Port(
        name=name,
        kind="material",
        direction=direction,
        multiplicity=1,
        component_mapping="revision_component_set",
        state_definition="nTP-v1",
        phase_capabilities=("liquid", "vapor"),
    )


PORTS: Final[tuple[Port, ...]] = (
    _material_port("hot_inlet", "inlet"),
    _material_port("hot_outlet", "outlet"),
    _material_port("cold_inlet", "inlet"),
    _material_port("cold_outlet", "outlet"),
)


def _holdup_balance(symbol: str, quantity: str, dimension: Dimension) -> Accumulation:
    return Accumulation(
        kind="holdup_balance",
        holdup=Holdup(symbol=symbol, quantity=quantity, dimension=dimension),
    )


#: Holdup balances because the exchanger is two vessels with contents: the heater's
#: classification (ADR 0008 Q1, answered by Frank for the heater), spec §10.1 and §13.2.
EQUATIONS: Final[tuple[DeclaredEquation, ...]] = (
    DeclaredEquation(
        equation_id="HX-mole-hot",
        statement="n_hot_in,i - n_hot_out,i = 0 for every component i",
        dependencies=("hot_inlet.state.n", "hot_outlet.state.n"),
        conditional_class="unconditional",
        accumulation=_holdup_balance(
            "N_hot_i", "component moles held on the hot side of the exchanger", MOLE
        ),
        dimension=MOLAR_FLOW,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="HX-mole-cold",
        statement="n_cold_in,i - n_cold_out,i = 0 for every component i",
        dependencies=("cold_inlet.state.n", "cold_outlet.state.n"),
        conditional_class="unconditional",
        accumulation=_holdup_balance(
            "N_cold_i", "component moles held on the cold side of the exchanger", MOLE
        ),
        dimension=MOLAR_FLOW,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="HX-pressure",
        statement="P_hot_out - P_hot_in = 0 and P_cold_out - P_cold_in = 0; no pressure drop",
        dependencies=(
            "hot_inlet.state.P",
            "hot_outlet.state.P",
            "cold_inlet.state.P",
            "cold_outlet.state.P",
        ),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=PRESSURE,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="HX-energy-hot",
        statement=(
            "Hdot_hot_in - Hdot_hot_out - Q = 0, Q the heat transferred from the hot to the cold "
            "side"
        ),
        dependencies=("hot_inlet.state", "hot_outlet.state", "Q"),
        conditional_class="unconditional",
        accumulation=_holdup_balance(
            "U_hot", "internal energy of the hot-side contents of the exchanger", ENERGY
        ),
        dimension=POWER,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="HX-energy-cold",
        statement="Hdot_cold_in - Hdot_cold_out + Q = 0",
        dependencies=("cold_inlet.state", "cold_outlet.state", "Q"),
        conditional_class="unconditional",
        accumulation=_holdup_balance(
            "U_cold", "internal energy of the cold-side contents of the exchanger", ENERGY
        ),
        dimension=POWER,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="HX-spec",
        statement=(
            "T_cold_out - T_spec = 0, or T_hot_out - T_spec = 0, or Q - Q_spec = 0, by the "
            "configured specification"
        ),
        dependencies=("specifications.T_spec", "specifications.Q_spec"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        source=SPECIFICATION,
    ),
)

_SENSITIVITY_NOTE: Final = (
    "The outlet temperature of the unspecified side is the inverse of a declared-phase enthalpy, "
    "and T05 exposes no sensitivity interface (spec §4.5): the unit offers residual rows and a "
    "causal evaluator that returns values. This stays `unavailable` and is reported as absent "
    "rather than as zeros (blueprint §5.2)."
)


@cache
def _artifact_hash() -> str:
    return file_sha256(Path(__file__))


@dataclass(frozen=True)
class ExchangerAssessment:
    """Every §10.2 check the evaluator could evaluate, in order, and the state they were judged at.

    `failures` is empty exactly when the exchanger has an answer. When a terminating check fails
    (1, 2 or 4) it is the only entry and the state fields are `None`; otherwise the state is the
    one §10.2 (3) computed, and `failures` lists every one of (5)–(8) that fails, so a registered
    failure case can be shown to fail its one check and pass the others.
    """

    failures: tuple[str, ...]
    #: `(status, message)` for each entry of `failures`; a message starts with its code.
    refusals: tuple[UnitEvaluation, ...]
    transferred_duty: float | None = None
    hot_outlet: StreamState | None = None
    cold_outlet: StreamState | None = None
    #: `T_hot_in - T_cold_out` and `T_hot_out - T_cold_in`, K. `None` with a dormant side.
    hot_end: float | None = None
    cold_end: float | None = None
    phase_signature: PhaseSignature | None = None


def _refusal(status: PropertyStatus, code: str, detail: str) -> UnitEvaluation:
    return UnitEvaluation(
        status=status, message=f"{code}\n{detail}", reference_convention=REFERENCE_CONVENTION
    )


def _code(evaluation: UnitEvaluation) -> str:
    return evaluation.message.splitlines()[0] if evaluation.message else ""


@dataclass(frozen=True)
class HeatExchanger:
    """One exchanger instance: declared phase per side and one specification."""

    unit_id: str
    provider: PropertyProvider
    #: `cold_outlet_temperature`, `hot_outlet_temperature` or `duty` (spec §10.1).
    specification: str
    #: `T_spec`, K, or `Q_spec`, W, according to `specification`. A pinned input.
    value: float
    context: EvaluationContext
    hot_phase: Phase
    cold_phase: Phase
    components: tuple[str, ...] = COMPONENTS

    def __post_init__(self) -> None:
        if self.specification not in SPECIFICATIONS:
            raise SpecificationError(
                f"{unknown_specification(self.specification)}\n"
                f"{self.unit_id}: an exchanger is specified by one of {list(SPECIFICATIONS)}; "
                "an approach-temperature or UA specification is not in v0.1 (spec §19 Q9)"
            )
        for label, phase in (("hot_phase", self.hot_phase), ("cold_phase", self.cold_phase)):
            if phase not in _DECLARABLE:
                raise ValueError(f"{self.unit_id}: {label} must be LIQUID or VAPOR, got {phase!r}")
        if not math.isfinite(self.value):
            raise ValueError(f"{self.unit_id}: the specified value {self.value} is not finite")

    @property
    def model_id(self) -> str:
        return MODEL_ID

    @property
    def specification_parameter(self) -> str:
        """`<U>.Q_spec` for a duty specification, `<U>.T_spec` for either temperature."""
        suffix = "Q_spec" if self.specification == "duty" else "T_spec"
        return f"{self.unit_id}.{suffix}"

    # -- declaration -------------------------------------------------------------------------

    def ports(self) -> tuple[Port, ...]:
        return PORTS

    def declared_equations(self) -> tuple[DeclaredEquation, ...]:
        return EQUATIONS

    def manifest(self) -> Mapping[str, Any]:
        return manifest_document(
            model_id=MODEL_ID,
            title="SYN-001 two-stream countercurrent heat exchanger",
            description=(
                "Transfers heat Q from a hot to a cold stream, each in a declared single phase at "
                "constant pressure, closed by a cold-outlet temperature, a hot-outlet "
                "temperature or a duty; adiabatic shell, no energy port."
            ),
            ports=PORTS,
            equations=EQUATIONS,
            derivatives=(
                DerivativeDeclaration(
                    output="hot_outlet.state",
                    with_respect_to=("hot_inlet.state", "cold_inlet.state", "specifications"),
                    method="unavailable",
                    regime="all",
                    notes=_SENSITIVITY_NOTE,
                ),
                DerivativeDeclaration(
                    output="cold_outlet.state",
                    with_respect_to=("hot_inlet.state", "cold_inlet.state", "specifications"),
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
                        "Every row is written over flowsheet variables, the owned Q and "
                        "declared-phase enthalpy blocks, so the backend differentiates it exactly "
                        "through K01; the blocks supply their own declared-sparse analytic "
                        "derivatives. No inner solve sits inside a residual."
                    ),
                ),
            ),
            initialization=Initialization(
                strategy="local_initializer",
                notes=(
                    "The causal evaluator: Q from the specification, the unspecified outlet "
                    "temperature by inverting its declared-phase enthalpy on the domain bracket."
                ),
            ),
            validity=Validity(
                components=self.components,
                phases=("liquid", "vapor", "zero_flow"),
                limitations=(
                    "Each side is one declared phase (hot_phase, cold_phase) at every port, "
                    "admitted by R-007's criterion; a side that would change phase is a typed "
                    "unsupported inadmissible_phase(<port>, <PHASE>) (spec §19 Q2, R-039).",
                    "The second law is checked as Q >= 0 and both terminal differences >= 0. "
                    "That is exact only for single-phase sides at constant pressure with a "
                    "constant c_p, and relies on K_i increasing in T so that the interior of a "
                    "side stays in its phase when both ends do (spec §10.4). A pinch is allowed.",
                    "No pressure drop: each side's outlet pressure copies its inlet's.",
                    "Adiabatic shell and no energy port: Q is the heat transferred from the hot "
                    "to the cold side, reported as transferred_duty, and the unit's duty is None.",
                    "A dormant side forces Q = 0; the specification must then be a zero duty, an "
                    "outlet temperature on the dormant side (its retained label), or the flowing "
                    "side's inlet temperature, else error "
                    "specification_unsatisfiable_with_dormant_side. On the EO path under "
                    "T05b-phase-contract-v2 such a specification closes SPECIFICATION_CONFLICT "
                    "with zero_flow_conflict naming the side's energy row; no other attempt "
                    "signature is searched for (T05b spec §7.8 (iv), §17).",
                    "At a dormant side the terminal differences are not judged (not_applicable): "
                    "nothing is claimed about a dormant side's outlet temperature beyond its "
                    "label (T05b spec §9.3, §17).",
                    "No approach-temperature or UA specification in v0.1 (spec §19 Q9).",
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
            raise ValueError(
                f"{self.unit_id}: wired into components {tuple(components)}, built for "
                f"{self.components}"
            )
        hot_in = wiring.one("hot_inlet")
        hot_out = wiring.one("hot_outlet")
        cold_in = wiring.one("cold_inlet")
        cold_out = wiring.one("cold_outlet")
        duty = duty_id(self.unit_id)

        blocks: list[PropertyBlock] = []
        block_inputs: dict[str, tuple[str, ...]] = {}
        keys: dict[str, tuple[str, ...]] = {}
        for stream, phase in (
            (hot_in, self.hot_phase),
            (hot_out, self.hot_phase),
            (cold_in, self.cold_phase),
            (cold_out, self.cold_phase),
        ):
            block, feeding, outputs = single_phase_enthalpy(
                self.provider, self.components, self.context, stream, phase
            )
            blocks.append(block)
            block_inputs[block.block_id] = feeding
            keys[stream] = outputs

        equations: list[EquationSpec] = []
        kinds: dict[str, QuantityKind] = {}
        for equation, inlet, outlet in (
            ("HX-mole-hot", hot_in, hot_out),
            ("HX-mole-cold", cold_in, cold_out),
        ):
            for component in self.components:
                equation_id = row_id(self.unit_id, equation, component)
                equations.append(
                    EquationSpec(
                        equation_id=equation_id,
                        build=balance_row(
                            (flow_id(inlet, component),), (flow_id(outlet, component),)
                        ),
                        accumulation="holdup_balance",
                        origin=origin(MODEL_ID, equation),
                    )
                )
                kinds[equation_id] = "molar_flow"
        for side, inlet, outlet in (("hot", hot_in, hot_out), ("cold", cold_in, cold_out)):
            equation_id = row_id(self.unit_id, "HX-pressure", side)
            equations.append(
                EquationSpec(
                    equation_id=equation_id,
                    build=balance_row((pressure_id(outlet),), (pressure_id(inlet),)),
                    accumulation="algebraic",
                    origin=origin(MODEL_ID, "HX-pressure"),
                )
            )
            kinds[equation_id] = "pressure"
        equation_id = row_id(self.unit_id, "HX-energy-hot")
        equations.append(
            EquationSpec(
                equation_id=equation_id,
                build=energy_row(keys[hot_in], keys[hot_out], sink=duty),
                accumulation="holdup_balance",
                origin=origin(MODEL_ID, "HX-energy-hot"),
            )
        )
        kinds[equation_id] = "heat_rate"
        equation_id = row_id(self.unit_id, "HX-energy-cold")
        equations.append(
            EquationSpec(
                equation_id=equation_id,
                build=energy_row(keys[cold_in], keys[cold_out], source=duty),
                accumulation="holdup_balance",
                origin=origin(MODEL_ID, "HX-energy-cold"),
            )
        )
        kinds[equation_id] = "heat_rate"

        specified: str
        spec_kind: QuantityKind
        if self.specification == "duty":
            specified, spec_kind = duty, "heat_rate"
        elif self.specification == "cold_outlet_temperature":
            specified, spec_kind = temperature_id(cold_out), "temperature"
        else:
            specified, spec_kind = temperature_id(hot_out), "temperature"
        equation_id = row_id(self.unit_id, "HX-spec")
        equations.append(
            EquationSpec(
                equation_id=equation_id,
                build=specification_row(specified, self.specification_parameter),
                accumulation="algebraic",
                origin=origin(MODEL_ID, "HX-spec"),
            )
        )
        kinds[equation_id] = spec_kind

        return Contribution(
            variable_ids=(duty,),
            equations=tuple(equations),
            variable_kinds={duty: "heat_rate"},
            row_kinds=kinds,
            blocks=tuple(blocks),
            block_inputs=block_inputs,
            parameter_ids=(self.specification_parameter,),
            parameters={self.specification_parameter: float(self.value)},
        )

    # -- evaluator ---------------------------------------------------------------------------

    def evaluate(
        self, inlets: Mapping[str, Sequence[StreamState]], context: EvaluationContext
    ) -> UnitEvaluation:
        assessment = self.assess(inlets, context)
        if assessment.failures:
            # §10.2's order: the first failing check is the answer.
            return assessment.refusals[0]
        assert assessment.hot_outlet is not None
        assert assessment.cold_outlet is not None
        return UnitEvaluation(
            status="ok",
            outlets={"hot_outlet": assessment.hot_outlet, "cold_outlet": assessment.cold_outlet},
            # No energy port: the shell is adiabatic and the unit's external duty is not a
            # quantity it has (UnitEvaluation keeps None and 0.0 apart).
            duty=None,
            transferred_duty=assessment.transferred_duty,
            phase_signature=assessment.phase_signature,
            provider_id=PROVIDER_ID,
            reference_convention=REFERENCE_CONVENTION,
        )

    def assess(
        self, inlets: Mapping[str, Sequence[StreamState]], context: EvaluationContext
    ) -> ExchangerAssessment:
        """Run §10.2's checks in order; see `ExchangerAssessment` for what is returned."""
        hot_in, cold_in = self._inlets(inlets)

        # (1) A dormant side forces Q = 0.
        if hot_in.is_dormant or cold_in.is_dormant:
            return self._dormant(hot_in, cold_in, context)

        # (2) Inlet enthalpies in the declared phases, admitted by R-007.
        enthalpies: dict[str, float] = {}
        for port, stream, phase in (
            ("hot_inlet", hot_in, self.hot_phase),
            ("cold_inlet", cold_in, self.cold_phase),
        ):
            answer = self._admitted(port, stream, phase, context)
            if isinstance(answer, UnitEvaluation):
                return _terminal(answer)
            enthalpies[port] = answer

        # (3) Q from the specification; the other outlet by inverting its declared-phase
        # enthalpy. (4) is decided inside: a temperature outside the domain is never evaluated.
        solved = self._close(hot_in, cold_in, enthalpies, context)
        if isinstance(solved, UnitEvaluation):
            return _terminal(solved)
        duty, hot_out, cold_out = solved

        refusals: list[UnitEvaluation] = []
        # (5) R-007 on the outlets, hot first.
        for port, stream, phase in (
            ("hot_outlet", hot_out, self.hot_phase),
            ("cold_outlet", cold_out, self.cold_phase),
        ):
            answer = self._admitted(port, stream, phase, context)
            if isinstance(answer, UnitEvaluation):
                refusals.append(answer)
        # (6)-(8) The second law, exact for this class (§10.4). A pinch is allowed.
        hot_end = hot_in.temperature - cold_out.temperature
        cold_end = hot_out.temperature - cold_in.temperature
        if duty < 0.0:
            refusals.append(
                _refusal(
                    "out_of_domain",
                    HEAT_FLOW_REVERSED,
                    f"{self.unit_id}: the specification makes Q = {duty!r} W, heat flowing from "
                    "the cold side to the hot side",
                )
            )
        if hot_end < 0.0:
            refusals.append(
                _refusal(
                    "out_of_domain",
                    CROSS_HOT_END,
                    f"{self.unit_id}: T_hot_in - T_cold_out = {hot_end!r} K < 0",
                )
            )
        if cold_end < 0.0:
            refusals.append(
                _refusal(
                    "out_of_domain",
                    CROSS_COLD_END,
                    f"{self.unit_id}: T_hot_out - T_cold_in = {cold_end!r} K < 0",
                )
            )
        return ExchangerAssessment(
            failures=tuple(_code(refusal) for refusal in refusals),
            refusals=tuple(refusals),
            transferred_duty=duty,
            hot_outlet=hot_out,
            cold_outlet=cold_out,
            hot_end=hot_end,
            cold_end=cold_end,
            # Two declared regimes are not one signature; only ZERO_FLOW is reported.
            phase_signature=None,
        )

    # -- evaluator parts ---------------------------------------------------------------------

    def _inlets(self, inlets: Mapping[str, Sequence[StreamState]]) -> tuple[StreamState, ...]:
        if set(inlets) != {"hot_inlet", "cold_inlet"}:
            raise ValueError(
                f"{self.unit_id}: an exchanger takes hot_inlet and cold_inlet, got {inlets!r}"
            )
        streams: list[StreamState] = []
        for port in ("hot_inlet", "cold_inlet"):
            connected = tuple(inlets[port])
            if len(connected) != 1:
                raise ValueError(f"{self.unit_id}: port {port} takes exactly one stream")
            if len(connected[0].n) != len(self.components):
                raise ValueError(
                    f"{self.unit_id}: {port} carries {len(connected[0].n)} components, expected "
                    f"{len(self.components)}"
                )
            streams.append(connected[0])
        return tuple(streams)

    def _admitted(
        self, port: str, stream: StreamState, phase: Phase, context: EvaluationContext
    ) -> float | UnitEvaluation:
        return admitted_enthalpy(
            self.provider,
            self.components,
            context,
            unit_id=self.unit_id,
            port=port,
            stream=stream,
            phase=phase,
        )

    def _dormant(
        self, hot_in: StreamState, cold_in: StreamState, context: EvaluationContext
    ) -> ExchangerAssessment:
        """§10.2 (1): Q = 0, and the specification must be satisfiable with it.

        Satisfiable means a zero duty, an outlet temperature on a dormant side (it becomes that
        side's retained label), or the flowing side's outlet temperature equal to its inlet's —
        exactly, since with Q = 0 the flowing outlet *is* the inlet. The flowing side is still
        admitted by R-007, because the rows write its enthalpy in the declared phase. The
        terminal differences are not judged: no heat flows, and a dormant side's temperature is a
        label, not a state a profile runs through.
        """
        labels = {"hot": hot_in.temperature, "cold": cold_in.temperature}
        dormant = {"hot": hot_in.is_dormant, "cold": cold_in.is_dormant}
        if self.specification == "duty":
            satisfiable = self.value == 0.0
        else:
            side = "cold" if self.specification == "cold_outlet_temperature" else "hot"
            satisfiable = dormant[side] or self.value == labels[side]
            if dormant[side]:
                labels[side] = float(self.value)
        if not satisfiable:
            return _terminal(
                _refusal(
                    "error",
                    DORMANT_SIDE,
                    f"{self.unit_id}: a dormant side forces Q = 0, and the specification "
                    f"{self.specification} = {self.value!r} cannot hold with it",
                )
            )
        for side, label in labels.items():
            if not T_MIN <= label <= T_MAX:
                return _terminal(
                    _refusal(
                        "out_of_domain",
                        OUTLET_OUTSIDE_DOMAIN,
                        f"{self.unit_id}: the {side} outlet temperature {label!r} K is outside "
                        f"[{T_MIN}, {T_MAX}] K",
                    )
                )
        for port, stream, phase in (
            ("hot_inlet", hot_in, self.hot_phase),
            ("cold_inlet", cold_in, self.cold_phase),
        ):
            answer = self._admitted(port, stream, phase, context)
            if isinstance(answer, UnitEvaluation):
                return _terminal(answer)
        hot_out = StreamState(n=hot_in.n, temperature=labels["hot"], pressure=hot_in.pressure)
        cold_out = StreamState(n=cold_in.n, temperature=labels["cold"], pressure=cold_in.pressure)
        return ExchangerAssessment(
            failures=(),
            refusals=(),
            transferred_duty=0.0,
            hot_outlet=hot_out,
            cold_outlet=cold_out,
            phase_signature="ZERO_FLOW" if dormant["hot"] and dormant["cold"] else None,
        )

    def _close(
        self,
        hot_in: StreamState,
        cold_in: StreamState,
        enthalpies: Mapping[str, float],
        context: EvaluationContext,
    ) -> tuple[float, StreamState, StreamState] | UnitEvaluation:
        """§10.2 (3) and (4): `(Q, hot_outlet, cold_outlet)`, or `outlet_outside_domain`."""
        hot_enthalpy, cold_enthalpy = enthalpies["hot_inlet"], enthalpies["cold_inlet"]
        if self.specification == "duty":
            duty = float(self.value)
            hot_temperature = self._invert(
                "hot_outlet", hot_in, self.hot_phase, hot_enthalpy - duty, context
            )
            if isinstance(hot_temperature, UnitEvaluation):
                return hot_temperature
            cold_temperature = self._invert(
                "cold_outlet", cold_in, self.cold_phase, cold_enthalpy + duty, context
            )
            if isinstance(cold_temperature, UnitEvaluation):
                return cold_temperature
        elif self.specification == "cold_outlet_temperature":
            cold_temperature = float(self.value)
            outlet = self._enthalpy_at(
                "cold_outlet", cold_in, self.cold_phase, cold_temperature, context
            )
            if isinstance(outlet, UnitEvaluation):
                return outlet
            duty = outlet - cold_enthalpy
            hot_temperature = self._invert(
                "hot_outlet", hot_in, self.hot_phase, hot_enthalpy - duty, context
            )
            if isinstance(hot_temperature, UnitEvaluation):
                return hot_temperature
        else:
            hot_temperature = float(self.value)
            outlet = self._enthalpy_at(
                "hot_outlet", hot_in, self.hot_phase, hot_temperature, context
            )
            if isinstance(outlet, UnitEvaluation):
                return outlet
            duty = hot_enthalpy - outlet
            cold_temperature = self._invert(
                "cold_outlet", cold_in, self.cold_phase, cold_enthalpy + duty, context
            )
            if isinstance(cold_temperature, UnitEvaluation):
                return cold_temperature
        return (
            duty,
            StreamState(n=hot_in.n, temperature=hot_temperature, pressure=hot_in.pressure),
            StreamState(n=cold_in.n, temperature=cold_temperature, pressure=cold_in.pressure),
        )

    def _outside(self, temperature: float) -> UnitEvaluation:
        return _refusal(
            "out_of_domain",
            OUTLET_OUTSIDE_DOMAIN,
            f"{self.unit_id}: an outlet temperature of {temperature!r} K is outside "
            f"[{T_MIN}, {T_MAX}] K",
        )

    def _slope_at(
        self,
        port: str,
        stream: StreamState,
        phase: Phase,
        temperature: float,
        context: EvaluationContext,
    ) -> tuple[float, float] | UnitEvaluation:
        """`(Hdot_phase, dHdot_phase/dT)` of `stream`'s flows at `temperature` and its pressure."""
        state = StreamState(n=stream.n, temperature=temperature, pressure=stream.pressure)
        result = self.provider.evaluate_phase(
            PropertyRequest(state=state, phase=phase, properties=("h",), derivatives=("T",)),
            context,
        )
        if result.status != "ok":
            return provider_refusal(port, result.status, result.message)
        enthalpy = 0.0
        slope = 0.0
        for component, flow in zip(self.components, stream.n, strict=True):
            enthalpy += flow * result.values[f"h_{component}"]
            slope += flow * result.derivatives[f"h_{component}"]["T"]
        return enthalpy, slope

    def _enthalpy_at(
        self,
        port: str,
        stream: StreamState,
        phase: Phase,
        temperature: float,
        context: EvaluationContext,
    ) -> float | UnitEvaluation:
        """A specified outlet's declared-phase enthalpy; (4) first, so nothing out of domain is
        asked of the provider."""
        if not T_MIN <= temperature <= T_MAX:
            return self._outside(temperature)
        answer = self._slope_at(port, stream, phase, temperature, context)
        if isinstance(answer, UnitEvaluation):
            return answer
        return answer[0]

    def _invert(
        self,
        port: str,
        stream: StreamState,
        phase: Phase,
        target: float,
        context: EvaluationContext,
    ) -> float | UnitEvaluation:
        """The `T` in the domain with `Hdot_phase(n, T, P) = target`, or `outlet_outside_domain`.

        Starts from the side's inlet temperature — a zero duty returns it exactly, since the
        target is then that very enthalpy — and takes Newton steps kept strictly inside the
        bracket, bisecting otherwise, until the residual is exactly zero or no double lies
        between the bracket ends. Returns the end with the smaller residual, never a midpoint.
        """
        low, high = T_MIN, T_MAX
        ends: list[tuple[float, float]] = []
        for end in (low, high):
            answer = self._slope_at(port, stream, phase, end, context)
            if isinstance(answer, UnitEvaluation):
                return answer
            ends.append((answer[0] - target, answer[1]))
        f_low, f_high = ends[0][0], ends[1][0]
        if f_low > 0.0:
            return self._outside(low)
        if f_high < 0.0:
            return self._outside(high)
        if f_low == 0.0:
            return low
        if f_high == 0.0:
            return high

        guess = stream.temperature
        for _ in range(_MAX_ITERATIONS):
            answer = self._slope_at(port, stream, phase, guess, context)
            if isinstance(answer, UnitEvaluation):
                return answer
            value, slope = answer[0] - target, answer[1]
            if value == 0.0:
                return guess
            if value < 0.0:
                low, f_low = guess, value
            else:
                high, f_high = guess, value
            proposed = guess - value / slope if slope > 0.0 else 0.5 * (low + high)
            if not low < proposed < high:
                proposed = 0.5 * (low + high)
            if not low < proposed < high:
                # No double lies strictly between the ends: the root is one of them.
                return low if abs(f_low) <= abs(f_high) else high
            if proposed == guess:
                return guess
            guess = proposed
        raise RuntimeError(
            f"{self.unit_id}: the enthalpy inversion did not end in {_MAX_ITERATIONS} steps on "
            f"[{low}, {high}] K; a bracketed bisection on doubles cannot do that, so this is a bug"
        )


def _terminal(refusal: UnitEvaluation) -> ExchangerAssessment:
    """A check after which nothing in §10.2 is defined: it is the assessment's only failure."""
    return ExchangerAssessment(failures=(_code(refusal),), refusals=(refusal,))
