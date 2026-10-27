"""`thermal.pump`, `thermal.compressor`, `thermal.turbine` — pure-fluid machines (S11 units design
§4.4; ADR 0051).

One class configured as one of the three. The outlet pressure is pinned and the isentropic
efficiency eta is a parameter; the ideal work is the isentropic enthalpy rise at the outlet
pressure, read from the machine's `PFs_<U>` block (§4.3), whose variant the inlet's and the
isentropic state's forms pick:

- pump: `pure-single/single` (L, L), or `pure-sat/single` from a saturated inlet at beta = 0;
  the isentropic state is LIQUID;
- compressor: `pure-single/single` (V, V), or `pure-sat/single` at beta = 1; VAPOR;
- turbine: `pure-single/*` or, at beta = 1, `pure-sat/*`, with `*` = `single` or `sat` by
  `isentropic_phase` (vapor or vapor_liquid, default the outlet's form).

Rows (family F = TPU, TCO, TTU): `F-mole:<c>`, `F-P` (P_O - P_spec), `F-work` (pump and
compressor eta W - (Hs - H_I); turbine W - eta (Hs - H_I)), `F-energy` (W + H_I - H_O, W positive
into the unit, ADR 0001 D4.1), and the saturated rows of a saturated turbine outlet (§4.1).
Owned: W (kind heat_rate, R-043), and `<O>.sat.V`, `<O>.sat.L`.

The additive-vapour (Wilson) compressor and turbine (§4.4's Wilson path, on `wilson-ig-v2`) are
single-phase vapour on both ports (L-GP-2): the faces are `tp_state.single_phase_enthalpy`'s
mixture blocks, shared with any syn001 unit reading the stream (§4.3); the mole rows are per
component; the isentropic block is `additive-vapour`. The evaluate inverts the outlet's vapour
enthalpy at P_spec on the provider's T domain and asks the provider's `stability()` of the outlet,
which must be STABLE_WITHIN_TESTED_SCOPE, else `phase_regime_mismatch(<O>)`.
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
    flow_id,
    pressure_id,
    temperature_id,
)
from openflowsheet.models.rows import balance_row, energy_row, specification_row, work_row
from openflowsheet.models.syn001 import MOLAR_FLOW, POWER, PRESSURE
from openflowsheet.models.syn001.gamma_phi import enthalpy_and_slope
from openflowsheet.models.syn001.ph_kernel import failure_labels, port_enthalpy, typed_failure
from openflowsheet.models.syn001.pump import work_id
from openflowsheet.models.syn001.tp_state import single_phase_enthalpy
from openflowsheet.models.thermal import ADDITIVE_VAPOUR, Form, admitted_identity
from openflowsheet.models.thermal.blocks import (
    IsentropicEnthalpyBlock,
    Variant,
    isentropic_block_id,
    isentropic_state,
)
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
    ISENTROPIC_FORM_CODES,
    Failure,
    Mismatch,
    _refusal,
    _solve,
    declared_state,
)
from openflowsheet.models.thermal.rows import expansion_work_row
from openflowsheet.models.thermal.state import carried_fraction
from openflowsheet.thermo import Phase, PropertyProvider, StreamState

SPECIFICATION: Final = "docs/derivations/S11-units-design.md §4.4"

Machine = Literal["pump", "compressor", "turbine"]
IsentropicPhase = Literal["vapor", "vapor_liquid"]

MACHINE_MODEL_IDS: Final[dict[str, str]] = {
    "pump": "thermal.pump",
    "compressor": "thermal.compressor",
    "turbine": "thermal.turbine",
}
#: The model ids this module serves, as the tuple ADR 0008's readiness checks read (U1, E1).
MODEL_IDS: Final[tuple[str, ...]] = tuple(MACHINE_MODEL_IDS.values())
FAMILIES: Final[dict[str, str]] = {"pump": "TPU", "compressor": "TCO", "turbine": "TTU"}
#: The inlet's phase: its single-phase form, and the side a saturated inlet must sit on.
_INLET_PHASE: Final[dict[str, Phase]] = {
    "pump": "LIQUID",
    "compressor": "VAPOR",
    "turbine": "VAPOR",
}
#: The exact vapour fraction a saturated inlet must carry (§4.4 "Isentropic variant").
_INLET_BETA: Final[dict[str, float]] = {"pump": 0.0, "compressor": 1.0, "turbine": 1.0}
#: The outlet forms each machine admits (§4.4 "Bind-time refusals").
_OUTLET_FORMS: Final[dict[str, tuple[Form, ...]]] = {
    "pump": ("LIQUID",),
    "compressor": ("VAPOR",),
    "turbine": ("VAPOR", "SATURATED"),
}
_ISENTROPIC_FORM: Final[dict[str, Form]] = {"vapor": "VAPOR", "vapor_liquid": "SATURATED"}

_TITLES: Final[dict[str, str]] = {
    "pump": "Pure-fluid liquid pump",
    "compressor": "Pure-fluid vapour compressor",
    "turbine": "Pure-fluid turbine (expander)",
}
_DESCRIPTIONS: Final[dict[str, str]] = {
    "pump": (
        "Raises a liquid or saturated-liquid pure-fluid stream to a specified pressure at an "
        "isentropic efficiency; the shaft work and the outlet state are calculated."
    ),
    "compressor": (
        "Compresses a vapour or saturated-vapour pure-fluid stream to a specified pressure at an "
        "isentropic efficiency; the shaft work and the outlet state are calculated."
    ),
    "turbine": (
        "Expands a vapour or saturated-vapour pure-fluid stream to a specified pressure at an "
        "isentropic efficiency, to a vapour or a saturated outlet; the shaft work (negative) and "
        "the outlet state are calculated."
    ),
}


#: §4.4's bind refusal of a Wilson machine's non-vapour port, and the binder's (L-GP-2).
WILSON_PORT_HINT: Final = "no γ–φ two-phase PS closure (L-GP-2)"
_STABLE: Final = "STABLE_WITHIN_TESTED_SCOPE"
_WILSON_LIMITATION: Final = (
    "L-GP-2: an additive-vapour (Wilson) machine is single-phase vapour on both ports, within "
    "the records' domain; its outlet must be judged STABLE_WITHIN_TESTED_SCOPE by the provider's "
    "stability(), else phase_regime_mismatch(<O>): there is no γ–φ two-phase PS closure. An "
    "isentropic vapour state that stability() judges UNSTABLE is refused "
    "isentropic_state_two_phase(<U>)."
)


def _refused(unit_id: str, what: str, hint: str) -> SpecificationError:
    return SpecificationError(f"specification_unsupported({unit_id}.{what})\n{hint}")


def _equations(machine: str) -> tuple[DeclaredEquation, ...]:
    family = FAMILIES[machine]
    if machine == "turbine":
        work_statement = "W - eta [Hs(n_I, s_I, P_O) - Hdot_I] = 0, W negative (work out)"
    else:
        work_statement = "eta W - [Hs(n_I, s_I, P_O) - Hdot_I] = 0"
    return (
        DeclaredEquation(
            equation_id=f"{family}-mole",
            statement="n_I,c - n_O,c = 0",
            dependencies=("inlet.state.n", "outlet.state.n"),
            conditional_class="unconditional",
            accumulation=Accumulation(kind="zero_holdup_balance", reason=NO_HOLDUP),
            dimension=MOLAR_FLOW,
            source=SPECIFICATION,
        ),
        DeclaredEquation(
            equation_id=f"{family}-P",
            statement="P_O - P_spec = 0",
            dependencies=("outlet.state.P", "parameters.P_spec"),
            conditional_class="unconditional",
            accumulation=Accumulation(kind="algebraic"),
            dimension=PRESSURE,
            source=SPECIFICATION,
        ),
        DeclaredEquation(
            equation_id=f"{family}-work",
            statement=work_statement,
            dependencies=("inlet.state", "outlet.state.P", "work.W", "parameters.efficiency"),
            conditional_class="unconditional",
            accumulation=Accumulation(kind="algebraic"),
            dimension=POWER,
            source=SPECIFICATION,
        ),
        DeclaredEquation(
            equation_id=f"{family}-energy",
            statement="W + Hdot_I - Hdot_O = 0, W positive into the unit (adiabatic)",
            dependencies=("inlet.state", "outlet.state", "work.W"),
            conditional_class="unconditional",
            accumulation=Accumulation(kind="zero_holdup_balance", reason=NO_HOLDUP),
            dimension=POWER,
            source=SPECIFICATION,
        ),
    )


def _ports(machine: str) -> tuple[Port, ...]:
    inlet_forms: tuple[Form, ...] = (_INLET_PHASE[machine], "SATURATED")
    return (
        material_port("inlet", "inlet", inlet_forms),
        material_port("outlet", "outlet", _OUTLET_FORMS[machine]),
        energy_port("work"),
    )


#: Machine -> its ports, as the unit's `ports()` gives them (read by the binder's signatures).
PORTS: Final[dict[str, tuple[Port, ...]]] = {
    machine: _ports(machine) for machine in MACHINE_MODEL_IDS
}

#: Every configuration's equations, keyed by (machine, saturated outlet): the module-level
#: declaration ADR 0008's readiness checks read (U1, E1); `declared_equations` returns one of them.
EQUATIONS: Final[dict[tuple[str, bool], tuple[DeclaredEquation, ...]]] = {
    (machine, saturated): (
        *_equations(machine),
        *(saturated_declarations(SPECIFICATION) if saturated else ()),
    )
    for machine in MACHINE_MODEL_IDS
    for saturated in (False, True)
    if not saturated or "SATURATED" in _OUTLET_FORMS[machine]
}


@dataclass(frozen=True)
class ThermalMachine:
    """One pump, compressor or turbine instance; `isentropic_phase` is the turbine's choice."""

    unit_id: str
    machine: Machine
    provider: PropertyProvider
    context: EvaluationContext
    #: Port -> connected stream ids (`inlet`, `outlet`).
    streams: Mapping[str, tuple[str, ...]]
    #: Stream id -> declared form.
    forms: Mapping[str, Form]
    outlet_pressure: float
    efficiency: float
    isentropic_phase: IsentropicPhase | None = None

    def __post_init__(self) -> None:
        if self.machine not in MACHINE_MODEL_IDS:
            raise SpecificationError(
                f"{self.unit_id}: machine {self.machine!r} is not one of {tuple(MACHINE_MODEL_IDS)}"
            )
        identity = admitted_identity(
            self.provider,
            self.unit_id,
            self.model_id,
            additive_vapour=self.machine != "pump",
        )
        check_wiring(self.unit_id, self.streams, self.forms)
        if identity in ADDITIVE_VAPOUR:
            for port, form in (("inlet", self.inlet_form), ("outlet", self.outlet_form)):
                if form != "VAPOR":
                    raise _refused(self.unit_id, port, WILSON_PORT_HINT)
            if self.isentropic_phase not in (None, "vapor"):
                raise _refused(self.unit_id, "isentropic_phase", WILSON_PORT_HINT)
        if not 0.0 < self.efficiency <= 1.0:
            raise SpecificationError(
                "efficiency_outside_interval\n"
                f"{self.unit_id}: efficiency {self.efficiency} is outside (0, 1]"
            )
        phase = _INLET_PHASE[self.machine]
        if self.inlet_form not in (phase, "SATURATED"):
            raise _refused(
                self.unit_id,
                "inlet",
                f"a {self.machine}'s inlet is {phase.lower()} or saturated "
                f"(vapor_liquid at beta = {_INLET_BETA[self.machine]}), declared "
                f"{self.inlet_form.lower()}",
            )
        if self.outlet_form not in _OUTLET_FORMS[self.machine]:
            raise _refused(
                self.unit_id,
                "outlet",
                f"a {self.machine}'s outlet is "
                f"{' or '.join(form.lower() for form in _OUTLET_FORMS[self.machine])}, declared "
                f"{self.outlet_form.lower()}",
            )
        if self.isentropic_phase is not None:
            if self.machine != "turbine":
                raise _refused(
                    self.unit_id,
                    "isentropic_phase",
                    f"only a turbine chooses its isentropic phase; a {self.machine}'s is "
                    f"{phase.lower()}",
                )
            if self.isentropic_phase not in _ISENTROPIC_FORM:
                raise _refused(
                    self.unit_id,
                    "isentropic_phase",
                    f"{self.isentropic_phase!r} is not one of {tuple(_ISENTROPIC_FORM)}",
                )
            if self.isentropic_phase == "vapor" and self.outlet_form == "SATURATED":
                raise _refused(
                    self.unit_id,
                    "isentropic_phase",
                    "inconsistent: a wet outlet has a wetter isentropic state",
                )

    @property
    def model_id(self) -> str:
        return MACHINE_MODEL_IDS[self.machine]

    @property
    def family(self) -> str:
        return FAMILIES[self.machine]

    @property
    def additive(self) -> bool:
        """The additive-vapour (Wilson) configuration: the provider's identity is in
        `ADDITIVE_VAPOUR` (§4.3)."""
        described = self.provider.describe()
        return (described.provider_id, described.reference_convention) in ADDITIVE_VAPOUR

    @property
    def components(self) -> tuple[str, ...]:
        return tuple(self.provider.describe().components)

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
    def inlet_form(self) -> Form:
        return self.forms[self.inlet_stream]

    @property
    def outlet_form(self) -> Form:
        return self.forms[self.outlet_stream]

    @property
    def isentropic_form(self) -> Form:
        """LIQUID (pump), VAPOR (compressor), or the turbine's `isentropic_phase`, defaulting to
        the outlet's form (§4.4)."""
        if self.machine != "turbine":
            return _INLET_PHASE[self.machine]
        if self.isentropic_phase is None:
            return self.outlet_form
        return _ISENTROPIC_FORM[self.isentropic_phase]

    @property
    def variant(self) -> Variant:
        if self.additive:
            return "additive-vapour"
        inlet = "sat" if self.inlet_form == "SATURATED" else "single"
        state = "sat" if self.isentropic_form == "SATURATED" else "single"
        return f"pure-{inlet}/{state}"  # type: ignore[return-value]

    @property
    def _isentropic_phase(self) -> Phase:
        """The block's single-phase isentropic phase (unused by the saturated variants)."""
        form = self.isentropic_form
        return "VAPOR" if form == "SATURATED" else form

    @property
    def dormancy_configuration(self) -> str:
        """The outlet's form (§4.9), read by WO-C6's `_CONFIGURED_BY` entry."""
        return self.outlet_form

    def _parameter(self, name: str) -> str:
        return f"{self.unit_id}.{name}"

    @property
    def pressure_parameter(self) -> str:
        return self._parameter("P_spec")

    @property
    def efficiency_parameter(self) -> str:
        return self._parameter("efficiency")

    # -- declaration ---------------------------------------------------------------------------

    def ports(self) -> tuple[Port, ...]:
        return _ports(self.machine)

    def declared_equations(self) -> tuple[DeclaredEquation, ...]:
        """This configuration's equations (S11C_DECISIONS C2-2)."""
        return EQUATIONS[(self.machine, self.outlet_form == "SATURATED")]

    def manifest(self) -> Mapping[str, Any]:
        return manifest(
            model_id=self.model_id,
            title=_TITLES[self.machine],
            description=_DESCRIPTIONS[self.machine],
            ports=self.ports(),
            equations=self.declared_equations(),
            provider=self.provider,
            method="implicit",
            notes=(
                "Every row is linear in flowsheet variables and block outputs. The enthalpy blocks "
                "declare analytic derivatives; the isentropic block PFs_<U> declares implicit "
                "ones, by the implicit function theorem on its inner PS equation (or on beta_s "
                "for a saturated isentropic state). W carries the heat_rate scaling kind (R-043)."
            ),
            initialization=(
                "The causal evaluator: the isentropic state, the work, then the kernel's "
                "declared-regime PH closure at the outlet pressure."
            ),
            limitations=(
                *LIMITATIONS,
                f"P_spec on the wrong side of the inlet pressure is refused "
                f"{self._bound_code()}; it is an inequality on the state, not a row.",
                "An isentropic state past the declared single-phase one (a wet compressor, pump "
                "or vapour-turbine state) is refused "
                f"isentropic_state_two_phase({self.unit_id}); a single-phase isentropic state "
                "where vapor_liquid is declared (beta_s outside [0, 1]), or a root outside the "
                "saturation range whose label is not the declared phase, is refused "
                f"isentropic_state_single_phase({self.unit_id}).",
                *((_WILSON_LIMITATION,) if self.additive else ()),
            ),
            module=__name__,
            path=Path(__file__),
        )

    # -- rows ----------------------------------------------------------------------------------

    def _isentropic_block(self) -> IsentropicEnthalpyBlock:
        if self.additive:
            return IsentropicEnthalpyBlock(
                self.provider,
                self.components,
                self.context,
                block_id=isentropic_block_id(self.unit_id),
                variant="additive-vapour",
                inlet_phase="VAPOR",
                isentropic_phase="VAPOR",
            )
        return IsentropicEnthalpyBlock(
            self.provider,
            self.component,
            self.context,
            block_id=isentropic_block_id(self.unit_id),
            variant=self.variant,
            inlet_phase=_INLET_PHASE[self.machine],
            isentropic_phase=self._isentropic_phase,
        )

    def contribute(self, wiring: Wiring, components: Sequence[str]) -> Contribution:
        if self.additive:
            return self._additive_contribution(wiring, components)
        component = self.component
        if tuple(components) != (component,):
            raise SpecificationError(f"{self.unit_id}: wired into {tuple(components)}")
        check_wiring(self.unit_id, self.streams, self.forms, wiring)
        inlet, out = self.inlet_stream, self.outlet_stream
        work = work_id(self.unit_id)
        inlet_face = stream_face(self.provider, component, self.context, inlet, self.inlet_form)
        outlet_face = stream_face(self.provider, component, self.context, out, self.outlet_form)
        ideal = self._isentropic_block()
        if self.inlet_form == "SATURATED":
            ideal_feeding: tuple[str, ...] = (
                flow_id(inlet, component),
                pressure_id(inlet),
                pressure_id(out),
            )
        else:
            ideal_feeding = (
                flow_id(inlet, component),
                temperature_id(inlet),
                pressure_id(inlet),
                pressure_id(out),
            )
        ideal_key = f"{ideal.block_id}.Hs"
        pressure, efficiency = self.pressure_parameter, self.efficiency_parameter
        family = self.family

        rows = Rows()
        # R-043: W is scaled as a heat rate, as the SYN-001 pump's.
        rows.own(work, "heat_rate")
        rows.add(
            self.unit_id,
            self.model_id,
            f"{family}-mole",
            balance_row((flow_id(inlet, component),), (flow_id(out, component),)),
            "molar_flow",
            "zero_holdup_balance",
            (component,),
        )
        rows.add(
            self.unit_id,
            self.model_id,
            f"{family}-P",
            specification_row(pressure_id(out), pressure),
            "pressure",
        )
        if self.machine == "turbine":
            work_build = expansion_work_row(work, efficiency, ideal_key, (inlet_face.key,))
        else:
            work_build = work_row(work, efficiency, (ideal_key,), (inlet_face.key,))
        rows.add(self.unit_id, self.model_id, f"{family}-work", work_build, "heat_rate")
        rows.add(
            self.unit_id,
            self.model_id,
            f"{family}-energy",
            energy_row((inlet_face.key,), (outlet_face.key,), source=work),
            "heat_rate",
            "zero_holdup_balance",
        )
        if self.outlet_form == "SATURATED":
            saturated_rows(rows, self.unit_id, self.model_id, "outlet", out, component)

        return Contribution(
            variable_ids=tuple(rows.owned),
            equations=tuple(rows.equations),
            variable_kinds=rows.owned_kinds,
            row_kinds=rows.row_kinds,
            blocks=(inlet_face.block, outlet_face.block, ideal),
            block_inputs={
                inlet_face.block.block_id: inlet_face.feeding,
                outlet_face.block.block_id: outlet_face.feeding,
                ideal.block_id: ideal_feeding,
            },
            parameter_ids=(pressure, efficiency),
            parameters={
                pressure: float(self.outlet_pressure),
                efficiency: float(self.efficiency),
            },
        )

    def _additive_contribution(self, wiring: Wiring, components: Sequence[str]) -> Contribution:
        """The Wilson rows (§4.4): the faces are `single_phase_enthalpy`'s VAPOR mixture blocks
        (`<block>.H` = n_tot h^V), one mole row per component, and the `additive-vapour`
        isentropic block fed by the inlet's flows, T_I, P_I and P_O."""
        names = self.components
        if tuple(components) != names:
            raise SpecificationError(f"{self.unit_id}: wired into {tuple(components)}")
        check_wiring(self.unit_id, self.streams, self.forms, wiring)
        inlet, out = self.inlet_stream, self.outlet_stream
        work = work_id(self.unit_id)
        inlet_block, inlet_feeding, inlet_keys = single_phase_enthalpy(
            self.provider, names, self.context, inlet, "VAPOR"
        )
        outlet_block, outlet_feeding, outlet_keys = single_phase_enthalpy(
            self.provider, names, self.context, out, "VAPOR"
        )
        ideal = self._isentropic_block()
        ideal_feeding = (
            *(flow_id(inlet, name) for name in names),
            temperature_id(inlet),
            pressure_id(inlet),
            pressure_id(out),
        )
        ideal_key = f"{ideal.block_id}.Hs"
        pressure, efficiency = self.pressure_parameter, self.efficiency_parameter
        family = self.family

        rows = Rows()
        rows.own(work, "heat_rate")
        for name in names:
            rows.add(
                self.unit_id,
                self.model_id,
                f"{family}-mole",
                balance_row((flow_id(inlet, name),), (flow_id(out, name),)),
                "molar_flow",
                "zero_holdup_balance",
                (name,),
            )
        rows.add(
            self.unit_id,
            self.model_id,
            f"{family}-P",
            specification_row(pressure_id(out), pressure),
            "pressure",
        )
        if self.machine == "turbine":
            work_build = expansion_work_row(work, efficiency, ideal_key, inlet_keys)
        else:
            work_build = work_row(work, efficiency, (ideal_key,), inlet_keys)
        rows.add(self.unit_id, self.model_id, f"{family}-work", work_build, "heat_rate")
        rows.add(
            self.unit_id,
            self.model_id,
            f"{family}-energy",
            energy_row(inlet_keys, outlet_keys, source=work),
            "heat_rate",
            "zero_holdup_balance",
        )
        return Contribution(
            variable_ids=tuple(rows.owned),
            equations=tuple(rows.equations),
            variable_kinds=rows.owned_kinds,
            row_kinds=rows.row_kinds,
            blocks=(inlet_block, outlet_block, ideal),
            block_inputs={
                inlet_block.block_id: inlet_feeding,
                outlet_block.block_id: outlet_feeding,
                ideal.block_id: ideal_feeding,
            },
            parameter_ids=(pressure, efficiency),
            parameters={
                pressure: float(self.outlet_pressure),
                efficiency: float(self.efficiency),
            },
        )

    # -- evaluator -----------------------------------------------------------------------------

    def _bound_code(self) -> str:
        """The SYN-001 pump's bound code, mirrored for the expander (S11C_DECISIONS C3-5)."""
        return (
            "pressure_rise(turbine)"
            if self.machine == "turbine"
            else (f"pressure_fall({self.machine})")
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
            raise SpecificationError(
                f"{self.unit_id}: a {self.machine} takes exactly one inlet stream"
            )
        feed = connected[0]
        described = self.provider.describe()
        out, form = self.outlet_stream, self.outlet_form
        pressure = float(self.outlet_pressure)

        # (0) Dormant: zero work; the outlet labelled with the inlet's T at P_spec (§4.4).
        if feed.is_dormant:
            dormant = outlet(out, form, (0.0,) * len(feed.n), feed.temperature, pressure)
            return UnitEvaluation(
                status="ok",
                outlets={"outlet": dormant.state},
                work=0.0,
                phase_signature="ZERO_FLOW",
                reference_convention=described.reference_convention,
                owned=dormant.owned,
            )

        # Bounds: an inequality on the state, as the SYN-001 pump's.
        expanding = self.machine == "turbine"
        if (pressure > feed.pressure) if expanding else (pressure < feed.pressure):
            side = "above" if expanding else "below"
            return self._failure(
                Failure(
                    "out_of_domain",
                    self._bound_code(),
                    f"P_spec = {pressure!r} Pa is {side} the inlet's {feed.pressure!r} Pa",
                )
            )

        if self.additive:
            return self._additive_evaluate(feed, pressure, context)

        # (1) A saturated inlet's vapour fraction is the stated one, exactly.
        phase = _INLET_PHASE[self.machine]
        inlet_stream, inlet_form = self.inlet_stream, self.inlet_form
        if inlet_form == "SATURATED":
            beta = carried_fraction(feed, inlet_stream)
            if isinstance(beta, Failure):
                return self._failure(beta)
            if beta != _INLET_BETA[self.machine]:
                return self._failure(
                    Failure(
                        "unsupported",
                        f"inadmissible_phase(inlet, {phase})",
                        f"{inlet_stream} carries vapour fraction {beta!r}; a {self.machine} "
                        f"takes a saturated inlet at beta = {_INLET_BETA[self.machine]} exactly",
                    )
                )
        entering = inlet_enthalpy(self.provider, feed, inlet_form, "inlet", inlet_stream, context)
        if isinstance(entering, Failure):
            return self._failure(entering)
        total = feed.total_flow

        # (2) The isentropic state at P_spec.
        ideal = isentropic_state(
            self.provider,
            context,
            self.variant,
            phase,
            self._isentropic_phase,
            None if inlet_form == "SATURATED" else feed.temperature,
            feed.pressure,
            pressure,
        )
        if isinstance(ideal, Failure):
            if ideal.code in ISENTROPIC_FORM_CODES:
                return self._failure(
                    Failure("unsupported", f"{ideal.code}({self.unit_id})", ideal.detail)
                )
            return self._failure(ideal)

        # (3) The work, as the work row writes it.
        rise = total * ideal.h - entering
        efficiency = float(self.efficiency)
        work = efficiency * rise if expanding else rise / efficiency

        # (4) The outlet: the declared-regime PH closure at P_spec.
        closed = declared_state(self.provider, total, pressure, entering + work, form, "h", context)
        if isinstance(closed, Failure):
            return self._failure(closed)
        if isinstance(closed, Mismatch):
            return self._failure(closed.failure(out))
        done = outlet(out, form, feed.n, closed.temperature, pressure, closed.beta)
        return UnitEvaluation(
            status="ok",
            outlets={"outlet": done.state},
            work=work,
            phase_signature=done.signature,
            iterations=closed.iterations,
            provider_id=described.provider_id,
            reference_convention=described.reference_convention,
            owned=done.owned,
        )

    def _additive_evaluate(
        self, feed: StreamState, pressure: float, context: EvaluationContext
    ) -> UnitEvaluation:
        """§4.4's Wilson path for a flowing feed inside the bounds: the inlet's vapour enthalpy
        (R-007's admissibility), Ḣ_s from the machine's own `PFs_<U>` block (the function the
        work row reads) with the provider's `stability()` of the isentropic state, W, then the
        outlet's vapour h-inversion at P_spec on the provider's T domain and the provider's
        `stability()` of the outlet. Every failure carries R-840's labels."""
        described = self.provider.describe()
        labels = failure_labels(described.provider_id, described.reference_convention)
        names = self.components
        out = self.outlet_stream

        def failed(failure: Failure) -> UnitEvaluation:
            return typed_failure(failure.status, failure.code, failure.detail, **labels)

        entering = port_enthalpy(
            self.provider, feed, "VAPOR", names, context, port="inlet", labels=labels
        )
        if entering.failure is not None:
            return entering.failure
        assert entering.enthalpy_flow is not None
        ideal = self._isentropic_block().additive_state(
            (*feed.n, feed.temperature, feed.pressure, pressure)
        )
        if isinstance(ideal, Failure):
            return failed(ideal)
        isentropic_temperature, isentropic = ideal
        # §4.4 step 2 on Wilson (S11D WO-I1b B): the isentropic state is a vapour; one the
        # provider judges UNSTABLE is past it.
        judged = self.provider.stability(  # type: ignore[attr-defined]
            StreamState(feed.n, isentropic_temperature, pressure), "VAPOR", context
        )
        if judged.label == "UNSTABLE":
            return failed(
                Failure(
                    "unsupported",
                    f"isentropic_state_two_phase({self.unit_id})",
                    f"stability() of the isentropic vapour state at ({isentropic_temperature!r} "
                    f"K, {pressure!r} Pa) is UNSTABLE; {WILSON_PORT_HINT}",
                )
            )

        rise = isentropic - entering.enthalpy_flow
        efficiency = float(self.efficiency)
        work = efficiency * rise if self.machine == "turbine" else rise / efficiency
        target = entering.enthalpy_flow + work

        def residual(temperature: float) -> tuple[float, float] | Failure:
            status, enthalpy, slope, message = enthalpy_and_slope(
                self.provider, StreamState(feed.n, temperature, pressure), "VAPOR", context
            )
            if status != "ok":
                return _refusal(status, message)
            return enthalpy - target, slope

        t_low, t_high = (float(value) for value in described.domain["T"])
        solved = _solve(
            residual,
            t_low,
            t_high,
            start=feed.temperature,
            what=f"{out}'s vapour enthalpy at {pressure!r} Pa",
        )
        if isinstance(solved, Failure):
            return failed(solved)
        temperature, evaluations = solved
        state = StreamState(feed.n, temperature, pressure)
        report = self.provider.stability(state, "VAPOR", context)  # type: ignore[attr-defined]
        if report.label != _STABLE:
            return failed(
                Failure(
                    "unsupported",
                    f"phase_regime_mismatch({out})",
                    f"declared vapor; stability() of the vapour outlet at ({temperature!r} K, "
                    f"{pressure!r} Pa) is {report.label}"
                    + (f" ({report.reason})" if report.reason else "")
                    + f"; {WILSON_PORT_HINT}",
                )
            )
        return UnitEvaluation(
            status="ok",
            outlets={"outlet": state},
            work=work,
            phase_signature="VAPOR",
            iterations=evaluations,
            provider_id=described.provider_id,
            reference_convention=described.reference_convention,
        )
