"""`thermal.valve` — isenthalpic throttling of a pure fluid to a specified pressure (§4.4).

Rows: `TV-mole:<c>`, `TV-P` (P_O - P_spec), `TV-energy` (H_I - H_O), and the saturated rows of a
saturated outlet (§4.1). A rise in pressure is refused `pressure_rise(valve)`, as the SYN-001 valve
refuses it; it is an inequality on the state, not a row.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import (
    Accumulation,
    Contribution,
    DeclaredEquation,
    Port,
    SpecificationError,
    UnitEvaluation,
    Wiring,
    flow_id,
    pressure_id,
)
from openflowsheet.models.rows import balance_row, energy_row, specification_row
from openflowsheet.models.syn001 import MOLAR_FLOW, POWER, PRESSURE
from openflowsheet.models.thermal import Form, admitted_identity
from openflowsheet.models.thermal.common import (
    LIMITATIONS,
    NO_HOLDUP,
    Rows,
    check_wiring,
    inlet_enthalpy,
    manifest,
    material_port,
    outlet,
    saturated_declarations,
    saturated_rows,
    stream_face,
)
from openflowsheet.models.thermal.kernel import Failure, Mismatch, declared_state
from openflowsheet.thermo import PropertyProvider, StreamState

MODEL_ID: Final = "thermal.valve"
SPECIFICATION: Final = "docs/derivations/S11-units-design.md §4.4"

_BASE: Final[tuple[DeclaredEquation, ...]] = (
    DeclaredEquation(
        equation_id="TV-mole",
        statement="n_I,c - n_O,c = 0",
        dependencies=("inlet.state.n", "outlet.state.n"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="zero_holdup_balance", reason=NO_HOLDUP),
        dimension=MOLAR_FLOW,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="TV-P",
        statement="P_O - P_spec = 0",
        dependencies=("outlet.state.P", "parameters.P_spec"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=PRESSURE,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="TV-energy",
        statement="Hdot_I - Hdot_O = 0 (isenthalpic)",
        dependencies=("inlet.state", "outlet.state"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="zero_holdup_balance", reason=NO_HOLDUP),
        dimension=POWER,
        source=SPECIFICATION,
    ),
)

PORTS: Final[tuple[Port, ...]] = (
    material_port("inlet", "inlet", ("LIQUID", "VAPOR", "SATURATED")),
    material_port("outlet", "outlet", ("LIQUID", "VAPOR", "SATURATED")),
)


@dataclass(frozen=True)
class ThermalValve:
    """One valve instance: a specified outlet pressure, at most the inlet's."""

    unit_id: str
    provider: PropertyProvider
    context: EvaluationContext
    streams: Mapping[str, tuple[str, ...]]
    forms: Mapping[str, Form]
    outlet_pressure: float

    def __post_init__(self) -> None:
        admitted_identity(self.provider, self.unit_id, MODEL_ID)
        check_wiring(self.unit_id, self.streams, self.forms)

    @property
    def model_id(self) -> str:
        return MODEL_ID

    @property
    def component(self) -> str:
        (component,) = self.provider.describe().components
        return component

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
        return self.outlet_form

    @property
    def pressure_parameter(self) -> str:
        return f"{self.unit_id}.P_spec"

    def ports(self) -> tuple[Port, ...]:
        return PORTS

    def declared_equations(self) -> tuple[DeclaredEquation, ...]:
        if self.outlet_form == "SATURATED":
            return (*_BASE, *saturated_declarations(SPECIFICATION))
        return _BASE

    def manifest(self) -> Mapping[str, Any]:
        return manifest(
            model_id=MODEL_ID,
            title="Pure-fluid throttling valve",
            description=(
                "Throttles a pure-fluid stream isenthalpically to a specified outlet pressure at "
                "a declared outlet phase; a saturated outlet carries its vapour fraction."
            ),
            ports=PORTS,
            equations=self.declared_equations(),
            provider=self.provider,
            method="analytic",
            notes=(
                "Every row is linear in flowsheet variables and enthalpy-block outputs; the "
                "blocks declare analytic first derivatives."
            ),
            initialization="The causal evaluator: the kernel's declared-regime PH closure.",
            limitations=(
                *LIMITATIONS,
                "P_spec above the inlet pressure is refused pressure_rise(valve); it is an "
                "inequality on the state, not a row.",
            ),
            module=__name__,
            path=Path(__file__),
        )

    def contribute(self, wiring: Wiring, components: Sequence[str]) -> Contribution:
        component = self.component
        if tuple(components) != (component,):
            raise SpecificationError(f"{self.unit_id}: wired into {tuple(components)}")
        check_wiring(self.unit_id, self.streams, self.forms, wiring)
        inlet, out = self.inlet_stream, self.outlet_stream
        inlet_face = stream_face(self.provider, component, self.context, inlet, self.forms[inlet])
        outlet_face = stream_face(self.provider, component, self.context, out, self.outlet_form)
        rows = Rows()
        rows.add(
            self.unit_id,
            MODEL_ID,
            "TV-mole",
            balance_row((flow_id(inlet, component),), (flow_id(out, component),)),
            "molar_flow",
            "zero_holdup_balance",
            (component,),
        )
        rows.add(
            self.unit_id,
            MODEL_ID,
            "TV-P",
            specification_row(pressure_id(out), self.pressure_parameter),
            "pressure",
        )
        rows.add(
            self.unit_id,
            MODEL_ID,
            "TV-energy",
            energy_row((inlet_face.key,), (outlet_face.key,)),
            "heat_rate",
            "zero_holdup_balance",
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
            parameter_ids=(self.pressure_parameter,),
            parameters={self.pressure_parameter: float(self.outlet_pressure)},
        )

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
            raise SpecificationError(f"{self.unit_id}: a valve takes exactly one inlet stream")
        feed = connected[0]
        described = self.provider.describe()
        out, form = self.outlet_stream, self.outlet_form
        pressure = float(self.outlet_pressure)
        if feed.is_dormant:
            dormant = outlet(out, form, (0.0,), feed.temperature, pressure)
            return UnitEvaluation(
                status="ok",
                outlets={"outlet": dormant.state},
                phase_signature="ZERO_FLOW",
                reference_convention=described.reference_convention,
                owned=dormant.owned,
            )
        if pressure > feed.pressure:
            return self._failure(
                Failure(
                    "out_of_domain",
                    "pressure_rise(valve)",
                    f"P_spec = {pressure} Pa is above the inlet's {feed.pressure} Pa",
                )
            )
        entering = inlet_enthalpy(
            self.provider, feed, self.forms[self.inlet_stream], "inlet", self.inlet_stream, context
        )
        if isinstance(entering, Failure):
            return self._failure(entering)
        closed = declared_state(
            self.provider, feed.total_flow, pressure, entering, form, "h", context
        )
        if isinstance(closed, Failure):
            return self._failure(closed)
        if isinstance(closed, Mismatch):
            return self._failure(closed.failure(out))
        done = outlet(out, form, feed.n, closed.temperature, pressure, closed.beta)
        return UnitEvaluation(
            status="ok",
            outlets={"outlet": done.state},
            phase_signature=done.signature,
            iterations=closed.iterations,
            provider_id=described.provider_id,
            reference_convention=described.reference_convention,
            owned=done.owned,
        )
