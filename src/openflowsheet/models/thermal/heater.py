"""`thermal.heater` — a pure-fluid heater or cooler (S11 units design §4.4; ADR 0051).

Exactly one specification: the outlet temperature (mode T), the duty (mode duty), or the outlet
vapour fraction (mode quality, a saturated outlet). The outlet's form is declared: an outlet at a
specified temperature is single-phase, a quality outlet is saturated, and a duty outlet is
whichever was declared, its closure refused `phase_regime_mismatch(<O>)` when it lands elsewhere.

Rows: `TH-mole:<c>`, `TH-pressure` (P_O - P_I + dP), `TH-energy` (Q + H_I - H_O, Q positive into
the unit, ADR 0001 D4.1), one of `TH-T`, `TH-duty`, `TH-quality` (V_O - beta_spec n_O), and the
saturated rows of a saturated outlet (§4.1). Owned: Q, and `<O>.sat.V`, `<O>.sat.L`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import (
    Accumulation,
    Contribution,
    DeclaredEquation,
    Port,
    SpecificationError,
    UnitEvaluation,
    Wiring,
    duty_id,
    flow_id,
    pressure_id,
    temperature_id,
)
from openflowsheet.models.rows import balance_row, energy_row, offset_row, specification_row
from openflowsheet.models.syn001 import MOLAR_FLOW, POWER, PRESSURE, TEMPERATURE
from openflowsheet.models.thermal import Form, admitted_identity
from openflowsheet.models.thermal.common import (
    LIMITATIONS,
    NO_HOLDUP,
    Rows,
    check_wiring,
    energy_port,
    inlet_enthalpy,
    manifest,
    material_port,
    outlet,
    saturated_declarations,
    saturated_rows,
    stream_face,
)
from openflowsheet.models.thermal.kernel import (
    Failure,
    Mismatch,
    declared_admissible,
    declared_state,
    phase_properties,
    saturation,
)
from openflowsheet.models.thermal.rows import quality_row
from openflowsheet.models.thermal.state import vapor_id
from openflowsheet.thermo import PropertyProvider, StreamState

MODEL_ID: Final = "thermal.heater"
SPECIFICATION: Final = "docs/derivations/S11-units-design.md §4.4"

Mode = Literal["T", "duty", "quality"]

_BASE: Final[tuple[DeclaredEquation, ...]] = (
    DeclaredEquation(
        equation_id="TH-mole",
        statement="n_I,c - n_O,c = 0",
        dependencies=("inlet.state.n", "outlet.state.n"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="zero_holdup_balance", reason=NO_HOLDUP),
        dimension=MOLAR_FLOW,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="TH-pressure",
        statement="P_O - P_I + dP = 0",
        dependencies=("inlet.state.P", "outlet.state.P", "parameters.pressure_drop"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=PRESSURE,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="TH-energy",
        statement="Q + Hdot_I - Hdot_O = 0, Q positive into the unit",
        dependencies=("inlet.state", "outlet.state", "duty.Q"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="zero_holdup_balance", reason=NO_HOLDUP),
        dimension=POWER,
        source=SPECIFICATION,
    ),
)
_SPECIFICATION_ROWS: Final[dict[str, DeclaredEquation]] = {
    "T": DeclaredEquation(
        equation_id="TH-T",
        statement="T_O - T_spec = 0",
        dependencies=("outlet.state.T", "parameters.T_spec"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=TEMPERATURE,
        source=SPECIFICATION,
    ),
    "duty": DeclaredEquation(
        equation_id="TH-duty",
        statement="Q - Q_spec = 0",
        dependencies=("duty.Q", "parameters.Q_spec"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=POWER,
        source=SPECIFICATION,
    ),
    "quality": DeclaredEquation(
        equation_id="TH-quality",
        statement="V_O - beta_spec n_O = 0",
        dependencies=("outlet.sat.V", "outlet.state.n", "parameters.outlet_vapor_fraction"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=MOLAR_FLOW,
        source=SPECIFICATION,
    ),
}

#: Every configuration's equations, keyed by (specification mode, saturated outlet): the
#: module-level declaration ADR 0008's readiness checks read (U1, E1); `declared_equations` returns
#: one of them.
EQUATIONS: Final[dict[tuple[Mode, bool], tuple[DeclaredEquation, ...]]] = {
    (mode, saturated): (
        *_BASE,
        row,
        *(saturated_declarations(SPECIFICATION) if saturated else ()),
    )
    for mode, row in _SPECIFICATION_ROWS.items()
    for saturated in (False, True)
}

PORTS: Final[tuple[Port, ...]] = (
    material_port("inlet", "inlet", ("LIQUID", "VAPOR", "SATURATED")),
    material_port("outlet", "outlet", ("LIQUID", "VAPOR", "SATURATED")),
    energy_port("duty"),
)


def _refused(unit_id: str, what: str, hint: str) -> SpecificationError:
    return SpecificationError(f"specification_unsupported({unit_id}.{what})\n{hint}")


@dataclass(frozen=True)
class ThermalHeater:
    """One heater instance; exactly one of `outlet_temperature`, `duty`, `outlet_vapor_fraction`."""

    unit_id: str
    provider: PropertyProvider
    context: EvaluationContext
    #: Port -> connected stream ids (`inlet`, `outlet`).
    streams: Mapping[str, tuple[str, ...]]
    #: Stream id -> declared form.
    forms: Mapping[str, Form]
    outlet_temperature: float | None = None
    duty: float | None = None
    outlet_vapor_fraction: float | None = None
    pressure_drop: float = 0.0

    def __post_init__(self) -> None:
        admitted_identity(self.provider, self.unit_id, MODEL_ID)
        check_wiring(self.unit_id, self.streams, self.forms)
        given = [
            name
            for name, value in (
                ("outlet.T", self.outlet_temperature),
                ("duty.Q", self.duty),
                ("outlet_vapor_fraction", self.outlet_vapor_fraction),
            )
            if value is not None
        ]
        if len(given) != 1:
            raise _refused(
                self.unit_id,
                "specification",
                f"exactly one of outlet.T, duty.Q, outlet_vapor_fraction; got {given}",
            )
        form = self.outlet_form
        if self.outlet_temperature is not None and form == "SATURATED":
            raise _refused(
                self.unit_id,
                "outlet.T",
                "a pure-fluid outlet at a specified temperature is single-phase; specify "
                "outlet_vapor_fraction or the duty",
            )
        if self.outlet_vapor_fraction is not None:
            if form != "SATURATED":
                raise _refused(
                    self.unit_id, "outlet_vapor_fraction", "declare the outlet vapor_liquid"
                )
            if not 0.0 <= self.outlet_vapor_fraction <= 1.0:
                raise _refused(
                    self.unit_id,
                    "outlet_vapor_fraction",
                    f"{self.outlet_vapor_fraction!r} is outside [0, 1]",
                )

    @property
    def model_id(self) -> str:
        return MODEL_ID

    @property
    def component(self) -> str:
        (component,) = self.provider.describe().components
        return component

    @property
    def mode(self) -> Mode:
        if self.outlet_temperature is not None:
            return "T"
        return "duty" if self.duty is not None else "quality"

    @property
    def inlet_stream(self) -> str:
        (stream,) = self.streams["inlet"]
        return stream

    @property
    def outlet_stream(self) -> str:
        (stream,) = self.streams["outlet"]
        return stream

    @property
    def outlet_form(self) -> Form:
        return self.forms[self.outlet_stream]

    @property
    def dormancy_configuration(self) -> str:
        """`<spec>:<form>` (§4.9), read by WO-C6's `_CONFIGURED_BY` entry."""
        return f"{self.mode}:{self.outlet_form}"

    def _parameter(self, name: str) -> str:
        return f"{self.unit_id}.{name}"

    @property
    def specification_parameter(self) -> str:
        return self._parameter(
            {"T": "T_spec", "duty": "Q_spec", "quality": "outlet_vapor_fraction"}[self.mode]
        )

    @property
    def specification_value(self) -> float:
        value = {
            "T": self.outlet_temperature,
            "duty": self.duty,
            "quality": self.outlet_vapor_fraction,
        }[self.mode]
        assert value is not None
        return float(value)

    # -- declaration ---------------------------------------------------------------------------

    def ports(self) -> tuple[Port, ...]:
        return PORTS

    def declared_equations(self) -> tuple[DeclaredEquation, ...]:
        """This configuration's equations (S11C_DECISIONS C2-2)."""
        return EQUATIONS[(self.mode, self.outlet_form == "SATURATED")]

    def manifest(self) -> Mapping[str, Any]:
        return manifest(
            model_id=MODEL_ID,
            title="Pure-fluid heater or cooler",
            description=(
                "Brings a pure-fluid stream to a specified outlet temperature, duty or outlet "
                "vapour fraction at a declared outlet phase; the duty or the outlet state is "
                "calculated."
            ),
            ports=PORTS,
            equations=self.declared_equations(),
            provider=self.provider,
            method="analytic",
            notes=(
                "Every row is linear in flowsheet variables and enthalpy-block outputs; the "
                "blocks declare analytic first derivatives from the provider's (T, P) "
                "derivatives and its dT_sat/dP."
            ),
            initialization="The causal evaluator: the kernel's declared-regime closure.",
            limitations=LIMITATIONS,
            module=__name__,
            path=Path(__file__),
        )

    # -- rows ----------------------------------------------------------------------------------

    def contribute(self, wiring: Wiring, components: Sequence[str]) -> Contribution:
        component = self.component
        if tuple(components) != (component,):
            raise SpecificationError(f"{self.unit_id}: wired into {tuple(components)}")
        check_wiring(self.unit_id, self.streams, self.forms, wiring)
        inlet, out = self.inlet_stream, self.outlet_stream
        duty = duty_id(self.unit_id)
        inlet_face = stream_face(self.provider, component, self.context, inlet, self.forms[inlet])
        outlet_face = stream_face(self.provider, component, self.context, out, self.outlet_form)
        drop = self._parameter("pressure_drop")
        spec = self.specification_parameter

        rows = Rows()
        rows.own(duty, "heat_rate")
        rows.add(
            self.unit_id,
            MODEL_ID,
            "TH-mole",
            balance_row((flow_id(inlet, component),), (flow_id(out, component),)),
            "molar_flow",
            "zero_holdup_balance",
            (component,),
        )
        rows.add(
            self.unit_id,
            MODEL_ID,
            "TH-pressure",
            offset_row(pressure_id(out), pressure_id(inlet), drop),
            "pressure",
        )
        rows.add(
            self.unit_id,
            MODEL_ID,
            "TH-energy",
            energy_row((inlet_face.key,), (outlet_face.key,), source=duty),
            "heat_rate",
            "zero_holdup_balance",
        )
        if self.mode == "T":
            rows.add(
                self.unit_id,
                MODEL_ID,
                "TH-T",
                specification_row(temperature_id(out), spec),
                "temperature",
            )
        elif self.mode == "duty":
            rows.add(self.unit_id, MODEL_ID, "TH-duty", specification_row(duty, spec), "heat_rate")
        else:
            rows.add(
                self.unit_id,
                MODEL_ID,
                "TH-quality",
                quality_row(vapor_id(out), spec, (flow_id(out, component),)),
                "molar_flow",
            )
        if self.outlet_form == "SATURATED":
            saturated_rows(rows, self.unit_id, MODEL_ID, "outlet", out, component)

        return Contribution(
            variable_ids=tuple(rows.owned),
            equations=tuple(rows.equations),
            variable_kinds=rows.owned_kinds,
            row_kinds=rows.row_kinds,
            blocks=(inlet_face.block, outlet_face.block),
            block_inputs={
                inlet_face.block.block_id: inlet_face.feeding,
                outlet_face.block.block_id: outlet_face.feeding,
            },
            parameter_ids=(spec, drop),
            parameters={spec: self.specification_value, drop: float(self.pressure_drop)},
        )

    # -- evaluator -----------------------------------------------------------------------------

    def _failure(self, failure: Failure) -> UnitEvaluation:
        return UnitEvaluation(
            status=failure.status,
            message=failure.message,
            reference_convention=self.provider.describe().reference_convention,
        )

    def evaluate(
        self, inlets: Mapping[str, Sequence[StreamState]], context: EvaluationContext
    ) -> UnitEvaluation:
        connected = tuple(inlets.get("inlet", ()))
        if len(connected) != 1 or set(inlets) - {"inlet"}:
            raise SpecificationError(f"{self.unit_id}: a heater takes exactly one inlet stream")
        feed = connected[0]
        described = self.provider.describe()
        out, form = self.outlet_stream, self.outlet_form
        pressure = feed.pressure - float(self.pressure_drop)

        if feed.is_dormant:
            dormant = outlet(out, form, (0.0,), feed.temperature, pressure)
            return UnitEvaluation(
                status="ok",
                outlets={"outlet": dormant.state},
                duty=0.0,
                phase_signature="ZERO_FLOW",
                reference_convention=described.reference_convention,
                owned=dormant.owned,
            )

        entering = inlet_enthalpy(
            self.provider, feed, self.forms[self.inlet_stream], "inlet", self.inlet_stream, context
        )
        if isinstance(entering, Failure):
            return self._failure(entering)
        total = feed.total_flow
        iterations = 0

        if self.mode == "T":
            assert self.outlet_temperature is not None and form != "SATURATED"
            temperature = float(self.outlet_temperature)
            admissible = declared_admissible(self.provider, temperature, pressure, form, context)
            if isinstance(admissible, Failure):
                return self._failure(admissible)
            if not admissible:
                other: Form = "VAPOR" if form == "LIQUID" else "LIQUID"
                return self._failure(Mismatch(form, other, None).failure(out))
            jets = phase_properties(self.provider, context, temperature, pressure, form, ("h",))
            if isinstance(jets, Failure):
                return self._failure(jets)
            leaving = total * jets["h"][0]
            done = outlet(out, form, feed.n, temperature, pressure)
            duty = leaving - entering
        elif self.mode == "duty":
            assert self.duty is not None
            duty = float(self.duty)
            closed = declared_state(
                self.provider, total, pressure, entering + duty, form, "h", context
            )
            if isinstance(closed, Failure):
                return self._failure(closed)
            if isinstance(closed, Mismatch):
                return self._failure(closed.failure(out))
            iterations = closed.iterations
            done = outlet(out, form, feed.n, closed.temperature, pressure, closed.beta)
        else:
            assert self.outlet_vapor_fraction is not None
            beta = float(self.outlet_vapor_fraction)
            sat = saturation(self.provider, pressure, context)
            if isinstance(sat, Failure):
                return self._failure(sat)
            liquid, vapour = sat.value("LIQUID", "h"), sat.value("VAPOR", "h")
            leaving = total * (liquid + beta * (vapour - liquid))
            done = outlet(out, form, feed.n, sat.temperature, pressure, beta)
            duty = leaving - entering

        return UnitEvaluation(
            status="ok",
            outlets={"outlet": done.state},
            duty=duty,
            phase_signature=done.signature,
            iterations=iterations,
            provider_id=described.provider_id,
            reference_convention=described.reference_convention,
            owned=done.owned,
        )
