"""`thermal.mixer` — an adiabatic mixer of pure-fluid streams at equal pressure (§4.4).

Rows: `TM-mole:<c>`, `TM-pressure:<k>` (P_k - P_O for every inlet k, as `MIX-pressure`),
`TM-energy` (sum H_k - H_O), and the saturated rows of a saturated outlet (§4.1). Dormant inlets
are absent from the causal closure; unequal flowing pressures are refused, as the K02 mixer refuses
them (ADR 0001 D4.5: the unit never repairs an invalid pressure).
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
from openflowsheet.models.rows import balance_row, energy_row
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
from openflowsheet.models.thermal.state import ThermalEvaluation
from openflowsheet.thermo import PropertyProvider, StreamState

MODEL_ID: Final = "thermal.mixer"
SPECIFICATION: Final = "docs/derivations/S11-units-design.md §4.4"

_BASE: Final[tuple[DeclaredEquation, ...]] = (
    DeclaredEquation(
        equation_id="TM-mole",
        statement="sum_k n_k,c - n_O,c = 0",
        dependencies=("inlet.state.n", "outlet.state.n"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="zero_holdup_balance", reason=NO_HOLDUP),
        dimension=MOLAR_FLOW,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="TM-pressure",
        statement="P_k - P_O = 0 for every inlet k",
        dependencies=("inlet.state.P", "outlet.state.P"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=PRESSURE,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="TM-energy",
        statement="sum_k Hdot_k - Hdot_O = 0 (adiabatic)",
        dependencies=("inlet.state", "outlet.state"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="zero_holdup_balance", reason=NO_HOLDUP),
        dimension=POWER,
        source=SPECIFICATION,
    ),
)

PORTS: Final[tuple[Port, ...]] = (
    material_port("inlet", "inlet", ("LIQUID", "VAPOR", "SATURATED"), many=True),
    material_port("outlet", "outlet", ("LIQUID", "VAPOR", "SATURATED")),
)


@dataclass(frozen=True)
class ThermalMixer:
    """One adiabatic mixer instance."""

    unit_id: str
    provider: PropertyProvider
    context: EvaluationContext
    streams: Mapping[str, tuple[str, ...]]
    forms: Mapping[str, Form]

    def __post_init__(self) -> None:
        admitted_identity(self.provider, self.unit_id, MODEL_ID)
        check_wiring(self.unit_id, self.streams, self.forms)
        if not self.streams.get("inlet"):
            raise SpecificationError(f"{self.unit_id}: a mixer needs at least one inlet stream")

    @property
    def model_id(self) -> str:
        return MODEL_ID

    @property
    def component(self) -> str:
        (component,) = self.provider.describe().components
        return component

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

    def ports(self) -> tuple[Port, ...]:
        return PORTS

    def declared_equations(self) -> tuple[DeclaredEquation, ...]:
        if self.outlet_form == "SATURATED":
            return (*_BASE, *saturated_declarations(SPECIFICATION))
        return _BASE

    def manifest(self) -> Mapping[str, Any]:
        return manifest(
            model_id=MODEL_ID,
            title="Pure-fluid adiabatic mixer",
            description=(
                "Mixes pure-fluid streams at equal pressure adiabatically into an outlet of a "
                "declared phase; a saturated outlet carries its vapour fraction."
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
                "Flowing inlets at unequal pressures are refused (ADR 0001 D4.5).",
            ),
            module=__name__,
            path=Path(__file__),
        )

    def contribute(self, wiring: Wiring, components: Sequence[str]) -> Contribution:
        component = self.component
        if tuple(components) != (component,):
            raise SpecificationError(f"{self.unit_id}: wired into {tuple(components)}")
        check_wiring(self.unit_id, self.streams, self.forms, wiring)
        inlets, out = self.streams["inlet"], self.outlet_stream
        faces = [
            stream_face(self.provider, component, self.context, stream, self.forms[stream])
            for stream in inlets
        ]
        outlet_face = stream_face(self.provider, component, self.context, out, self.outlet_form)
        rows = Rows()
        rows.add(
            self.unit_id,
            MODEL_ID,
            "TM-mole",
            balance_row(
                tuple(flow_id(stream, component) for stream in inlets), (flow_id(out, component),)
            ),
            "molar_flow",
            "zero_holdup_balance",
            (component,),
        )
        rows.add(
            self.unit_id,
            MODEL_ID,
            "TM-energy",
            energy_row(tuple(face.key for face in faces), (outlet_face.key,)),
            "heat_rate",
            "zero_holdup_balance",
        )
        for index, stream in enumerate(inlets):
            rows.add(
                self.unit_id,
                MODEL_ID,
                "TM-pressure",
                balance_row((pressure_id(stream),), (pressure_id(out),)),
                "pressure",
                suffix=(str(index),),
            )
        if self.outlet_form == "SATURATED":
            saturated_rows(rows, self.unit_id, MODEL_ID, "outlet", out, component)
        blocks = [*(face.block for face in faces), outlet_face.block]
        feeding = {face.block.block_id: face.feeding for face in (*faces, outlet_face)}
        return Contribution(
            variable_ids=tuple(rows.owned),
            equations=tuple(rows.equations),
            variable_kinds=rows.owned_kinds,
            row_kinds=rows.row_kinds,
            blocks=tuple(blocks),
            block_inputs=feeding,
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
        streams = self.streams["inlet"]
        if len(connected) != len(streams) or set(inlets) - {"inlet"}:
            raise SpecificationError(
                f"{self.unit_id}: built for {len(streams)} inlet streams, got {inlets!r}"
            )
        described = self.provider.describe()
        out, form = self.outlet_stream, self.outlet_form
        flowing = [
            (stream, state)
            for stream, state in zip(streams, connected, strict=True)
            if not state.is_dormant
        ]
        if not flowing:
            first = connected[0]
            dormant = outlet(out, form, (0.0,), first.temperature, first.pressure)
            return ThermalEvaluation(
                status="ok",
                outlets={"outlet": dormant.state},
                phase_signature="ZERO_FLOW",
                reference_convention=described.reference_convention,
                owned=dormant.owned,
            )
        pressures = {state.pressure for _, state in flowing}
        if len(pressures) != 1:
            return UnitEvaluation(
                status="error",
                message=(
                    f"inlet pressures {sorted(pressures)} are not equal. TM-pressure declares "
                    "them equal to the outlet pressure and ADR 0001 D4.5 makes a mismatch a "
                    "validation failure; the unit never silently repairs an invalid pressure"
                ),
                reference_convention=described.reference_convention,
            )
        pressure = flowing[0][1].pressure
        total = 0.0
        entering = 0.0
        for stream, state in flowing:
            enthalpy = inlet_enthalpy(
                self.provider, state, self.forms[stream], "inlet", stream, context
            )
            if isinstance(enthalpy, Failure):
                return self._failure(enthalpy)
            total += state.total_flow
            entering += enthalpy
        closed = declared_state(self.provider, total, pressure, entering, form, "h", context)
        if isinstance(closed, Failure):
            return self._failure(closed)
        if isinstance(closed, Mismatch):
            return self._failure(closed.failure(out))
        done = outlet(out, form, (total,), closed.temperature, pressure, closed.beta)
        return ThermalEvaluation(
            status="ok",
            outlets={"outlet": done.state},
            phase_signature=done.signature,
            iterations=closed.iterations,
            provider_id=described.provider_id,
            reference_convention=described.reference_convention,
            owned=done.owned,
        )
