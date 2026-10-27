"""`thermal.flash` — a pure-fluid separator drum at a specified duty and pressure drop (§4.4).

Both products are saturated (declared `vapor_liquid`, ADR 0051 D4 and Q26): the vapour product
carries no liquid and the liquid product no vapour. Rows: `TF-mole:<c>`, `TF-pressure:vapor`,
`TF-pressure:liquid` (P_out - P_I + dP), `TF-duty`, `TF-energy` (Q + H_I - H_V - H_L), the
saturated rows of both products, and `sat-fix:vapor` (L_V = 0), `sat-fix:liquid` (V_L = 0).
DOF 11 = 11. The causal face is the kernel's PH closure at the drum pressure, which must be
SATURATED; beta = 0 or 1 gives a dormant product (ADR 0001 D3.4).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from openflowsheet.compiled import EvaluationContext, PhaseSignature
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
)
from openflowsheet.models.rows import balance_row, energy_row, offset_row, specification_row
from openflowsheet.models.syn001 import MOLAR_FLOW, POWER, PRESSURE
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
from openflowsheet.models.thermal.kernel import Failure, ph_closure
from openflowsheet.models.thermal.rows import vanishing_row
from openflowsheet.models.thermal.state import liquid_id, vapor_id
from openflowsheet.thermo import PropertyProvider, StreamState

MODEL_ID: Final = "thermal.flash"
SPECIFICATION: Final = "docs/derivations/S11-units-design.md §4.4"

EQUATIONS: Final[tuple[DeclaredEquation, ...]] = (
    DeclaredEquation(
        equation_id="TF-mole",
        statement="n_I,c - n_V,c - n_L,c = 0",
        dependencies=("inlet.state.n", "vapor.state.n", "liquid.state.n"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="zero_holdup_balance", reason=NO_HOLDUP),
        dimension=MOLAR_FLOW,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="TF-pressure",
        statement="P_out - P_I + dP = 0 for each product",
        dependencies=("inlet.state.P", "vapor.state.P", "liquid.state.P"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=PRESSURE,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="TF-duty",
        statement="Q - Q_spec = 0",
        dependencies=("duty.Q", "parameters.Q_spec"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=POWER,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="TF-energy",
        statement="Q + Hdot_I - Hdot_V - Hdot_L = 0, Q positive into the unit",
        dependencies=("inlet.state", "vapor.state", "liquid.state", "duty.Q"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="zero_holdup_balance", reason=NO_HOLDUP),
        dimension=POWER,
        source=SPECIFICATION,
    ),
    *saturated_declarations(SPECIFICATION),
    DeclaredEquation(
        equation_id="sat-fix",
        statement="L_V = 0 (vapour product) and V_L = 0 (liquid product)",
        dependencies=("vapor.sat.L", "liquid.sat.V"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=MOLAR_FLOW,
        source=SPECIFICATION,
    ),
)

PORTS: Final[tuple[Port, ...]] = (
    material_port("inlet", "inlet", ("LIQUID", "VAPOR", "SATURATED")),
    material_port("vapor", "outlet", ("SATURATED",)),
    material_port("liquid", "outlet", ("SATURATED",)),
    energy_port("duty"),
)

_TWO_PHASE_HINT: Final = "thermal.flash needs a two-phase state at the drum pressure"


@dataclass(frozen=True)
class ThermalFlash:
    """One drum instance: a specified duty Q_spec and pressure drop."""

    unit_id: str
    provider: PropertyProvider
    context: EvaluationContext
    streams: Mapping[str, tuple[str, ...]]
    forms: Mapping[str, Form]
    duty: float = 0.0
    pressure_drop: float = 0.0

    def __post_init__(self) -> None:
        admitted_identity(self.provider, self.unit_id, MODEL_ID)
        check_wiring(self.unit_id, self.streams, self.forms)
        for port in ("vapor", "liquid"):
            if self.forms[self.stream(port)] != "SATURATED":
                raise SpecificationError(
                    f"specification_unsupported({self.unit_id}.{port})\n"
                    "a drum's products are saturated (ADR 0051 D4)"
                )

    @property
    def model_id(self) -> str:
        return MODEL_ID

    @property
    def component(self) -> str:
        (component,) = self.provider.describe().components
        return component

    def stream(self, port: str) -> str:
        (stream,) = self.streams[port]
        return stream

    @property
    def dormancy_configuration(self) -> str:
        return "SATURATED"

    @property
    def duty_parameter(self) -> str:
        return f"{self.unit_id}.Q_spec"

    @property
    def pressure_drop_parameter(self) -> str:
        return f"{self.unit_id}.pressure_drop"

    def ports(self) -> tuple[Port, ...]:
        return PORTS

    def declared_equations(self) -> tuple[DeclaredEquation, ...]:
        return EQUATIONS

    def manifest(self) -> Mapping[str, Any]:
        return manifest(
            model_id=MODEL_ID,
            title="Pure-fluid separator drum",
            description=(
                "Separates a pure-fluid stream at a specified duty and pressure drop into a "
                "saturated vapour and a saturated liquid product."
            ),
            ports=PORTS,
            equations=EQUATIONS,
            provider=self.provider,
            method="analytic",
            notes=(
                "Every row is linear in flowsheet variables and enthalpy-block outputs; the "
                "saturated blocks declare analytic first derivatives along the saturation line."
            ),
            initialization="The causal evaluator: the kernel's PH closure at the drum pressure.",
            limitations=(
                *LIMITATIONS,
                "The drum's state at its pressure must be two-phase (0 <= beta <= 1); otherwise "
                "phase_regime_mismatch(<inlet>).",
            ),
            module=__name__,
            path=Path(__file__),
        )

    def contribute(self, wiring: Wiring, components: Sequence[str]) -> Contribution:
        component = self.component
        if tuple(components) != (component,):
            raise SpecificationError(f"{self.unit_id}: wired into {tuple(components)}")
        check_wiring(self.unit_id, self.streams, self.forms, wiring)
        inlet, vapour, liquid = self.stream("inlet"), self.stream("vapor"), self.stream("liquid")
        duty = duty_id(self.unit_id)
        faces = [
            stream_face(self.provider, component, self.context, stream, self.forms[stream])
            for stream in (inlet, vapour, liquid)
        ]
        rows = Rows()
        rows.own(duty, "heat_rate")
        rows.add(
            self.unit_id,
            MODEL_ID,
            "TF-mole",
            balance_row(
                (flow_id(inlet, component),),
                (flow_id(vapour, component), flow_id(liquid, component)),
            ),
            "molar_flow",
            "zero_holdup_balance",
            (component,),
        )
        for port, stream in (("vapor", vapour), ("liquid", liquid)):
            rows.add(
                self.unit_id,
                MODEL_ID,
                "TF-pressure",
                offset_row(pressure_id(stream), pressure_id(inlet), self.pressure_drop_parameter),
                "pressure",
                suffix=(port,),
            )
        rows.add(
            self.unit_id,
            MODEL_ID,
            "TF-duty",
            specification_row(duty, self.duty_parameter),
            "heat_rate",
        )
        rows.add(
            self.unit_id,
            MODEL_ID,
            "TF-energy",
            energy_row((faces[0].key,), (faces[1].key, faces[2].key), source=duty),
            "heat_rate",
            "zero_holdup_balance",
        )
        for port, stream in (("vapor", vapour), ("liquid", liquid)):
            saturated_rows(rows, self.unit_id, MODEL_ID, port, stream, component)
        rows.add(
            self.unit_id,
            MODEL_ID,
            "sat-fix",
            vanishing_row(liquid_id(vapour)),
            "molar_flow",
            suffix=("vapor",),
        )
        rows.add(
            self.unit_id,
            MODEL_ID,
            "sat-fix",
            vanishing_row(vapor_id(liquid)),
            "molar_flow",
            suffix=("liquid",),
        )
        return Contribution(
            variable_ids=tuple(rows.owned),
            equations=tuple(rows.equations),
            variable_kinds=rows.owned_kinds,
            row_kinds=rows.row_kinds,
            blocks=tuple(face.block for face in faces),
            block_inputs={face.block.block_id: face.feeding for face in faces},
            parameter_ids=(self.duty_parameter, self.pressure_drop_parameter),
            parameters={
                self.duty_parameter: float(self.duty),
                self.pressure_drop_parameter: float(self.pressure_drop),
            },
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
            raise SpecificationError(f"{self.unit_id}: a drum takes exactly one inlet stream")
        feed = connected[0]
        described = self.provider.describe()
        inlet, vapour, liquid = self.stream("inlet"), self.stream("vapor"), self.stream("liquid")
        pressure = feed.pressure - float(self.pressure_drop)
        if feed.is_dormant:
            products = [
                outlet(stream, "SATURATED", (0.0,), feed.temperature, pressure)
                for stream in (vapour, liquid)
            ]
            return UnitEvaluation(
                status="ok",
                outlets={"vapor": products[0].state, "liquid": products[1].state},
                duty=0.0,
                phase_signature="ZERO_FLOW",
                reference_convention=described.reference_convention,
                owned={**products[0].owned, **products[1].owned},
            )
        entering = inlet_enthalpy(self.provider, feed, self.forms[inlet], "inlet", inlet, context)
        if isinstance(entering, Failure):
            return self._failure(entering)
        total = feed.total_flow
        closure = ph_closure(self.provider, total, pressure, entering + float(self.duty), context)
        if isinstance(closure, Failure):
            return self._failure(closure)
        if closure.regime != "SATURATED":
            return self._failure(
                Failure(
                    "unsupported",
                    f"phase_regime_mismatch({inlet})",
                    f"{_TWO_PHASE_HINT}; closure {closure.regime} at {pressure!r} Pa",
                )
            )
        beta = closure.beta
        assert beta is not None
        vapour_flow = beta * total
        top = outlet(vapour, "SATURATED", (vapour_flow,), closure.temperature, pressure, 1.0)
        bottom = outlet(
            liquid, "SATURATED", (total - vapour_flow,), closure.temperature, pressure, 0.0
        )
        signature: PhaseSignature = (
            "LIQUID" if beta == 0.0 else "VAPOR" if beta == 1.0 else "TWO_PHASE"
        )
        return UnitEvaluation(
            status="ok",
            outlets={"vapor": top.state, "liquid": bottom.state},
            duty=float(self.duty),
            phase_signature=signature,
            iterations=closure.iterations,
            provider_id=described.provider_id,
            reference_convention=described.reference_convention,
            owned={**top.owned, **bottom.owned},
        )
