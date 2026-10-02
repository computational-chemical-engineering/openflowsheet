"""`syn001.kinetic_cstr` — a cooled CSTR with one first-order reaction (T08 build-first §A1).

The model that realises T04 §8.4's PTC-R1 inside the v0.1 envelope (ADR 0023). One reaction with
stoichiometry `nu`, first order in its key reactant `k`, at the synthetic Frank-Kamenetskii rate

    r = Da exp((T_out - T_ref)/T_s) n_out,k        (mol/s; no Arrhenius claim, §A1.1 (3))

and a coolant of capacity rate `F_c c_c` that leaves at the vessel temperature (§A1.1 (2)). The
rate constant and the residence time enter only as their product, the Damköhler number at
`T_ref`, so no time or conductance kind is needed and no frozen schema changes.

**The rate is substituted, not owned** (§A1.1 (4)): there is no extent variable. The unknowns are
the outlet flows, `T_out`, `P_out` and `Q`; the rows are `CSTR-mole` per component, `CSTR-duty`,
`CSTR-cooling` and `CSTR-pressure` (§A1.3).

**The energy balance is in total-enthalpy form** (ADR 0011 D2), as the conversion reactor's: the
heat of reaction is carried by the outlet's changed composition, never added as a separate term.
On SYN-001 every mass-conserving liquid reaction is thermoneutral, so an exothermic CSTR is a
vapour-phase one (§A1.1 (1)).

**The outlet is single-phase by declaration** (`phase`, the outlet connection's declared phase),
with R-007's admissibility criterion, as K02's heater and mixer and T05's pump (T05 §3.4). The
inlet is read as the conversion reactor reads it: declared, or lifted by its producer.

**The causal evaluator is an initializer, not a steady state** (§A1.4). A kinetic CSTR can have
several steady states (PTC-R1 has three), so it has no unique causal answer. `evaluate` returns
the isothermal state at `T_init` (`T_c` for a dormant inlet with `F_c c_c > 0`, else `T_in`):
its mole, cooling and pressure rows hold, its energy row only by coincidence.

**Zero flow** (§A1.4). A dormant inlet with `F_c c_c > 0` gives a dormant outlet at `T_c` and
`Q = 0`, an exact root with a regular Jacobian (`CSTR-cooling` reads `T_out`). With `F_c c_c = 0`
no row reads a dormant outlet's temperature: T05 §4.7 (a)'s singularity, a registered limitation.
"""

from __future__ import annotations

import math
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
from openflowsheet.models.rows import cooling_row, energy_row, kinetic_balance_row, offset_row
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
from openflowsheet.models.syn001.conversion_reactor import (
    MASS_CONSERVATION_RELATIVE,
    MOLAR_MASSES,
    REACTION_CONSISTENT_CONVENTIONS,
    reactant_exhausted,
    reference_convention_not_reaction_consistent,
)
from openflowsheet.models.syn001.ph_kernel import port_enthalpy, typed_failure
from openflowsheet.models.syn001.tp_state import single_phase_enthalpy, stream_enthalpy_terms
from openflowsheet.thermo import Phase, PropertyProvider, StreamState

MODEL_ID: Final = "syn001.kinetic_cstr"

SPECIFICATION: Final = "docs/derivations/T08-build-first-spec.md §A1"

#: §A1.2: `(T_max - T_ref)/T_s` above this is `rate_exponent_overflow`, so `exp` is finite at every
#: in-domain state (`math.exp` overflows past about 709.78).
MAX_RATE_EXPONENT: Final = 700.0

#: §A1.4: what `validity.limitations` and every `ok` evaluation state about the causal evaluator.
INITIALIZER_LIMITATION: Final = (
    "causal evaluation is the isothermal local initializer, not a steady state"
)

#: The declared outlet phases (§A1.2: `phase ∈ {vapor, liquid}`).
OUTLET_PHASES: Final[tuple[Phase, ...]] = ("VAPOR", "LIQUID")

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
        phase_capabilities=("liquid", "vapor"),
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
        equation_id="CSTR-mole",
        statement=(
            "n_in,i - n_out,i + nu_i r = 0, r = Da exp((T_out - T_ref)/T_s) n_out,k "
            "(synthetic rate law)"
        ),
        dependencies=(
            "inlet.state.n",
            "outlet.state.n",
            "outlet.state.T",
            "parameters.nu",
            "parameters.damkohler",
            "parameters.T_ref",
            "parameters.T_scale",
        ),
        conditional_class="unconditional",
        accumulation=Accumulation(
            kind="holdup_balance",
            holdup=Holdup(
                symbol="N_i", quantity="component moles held in the reactor", dimension=MOLE
            ),
        ),
        dimension=MOLAR_FLOW,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="CSTR-duty",
        statement=(
            "Q + Hdot_in - Hdot_out = 0 on the provider's formation datum (ADR 0011 D2); the heat "
            "of reaction is carried by Hdot"
        ),
        dependencies=("inlet.state", "outlet.state", "duty.Q"),
        conditional_class="unconditional",
        accumulation=Accumulation(
            kind="holdup_balance",
            holdup=Holdup(
                symbol="U", quantity="internal energy of the reactor contents", dimension=ENERGY
            ),
        ),
        dimension=POWER,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="CSTR-cooling",
        statement="Q - F_c c_c (T_c - T_out) = 0, a coolant leaving at the reactor temperature",
        dependencies=(
            "duty.Q",
            "outlet.state.T",
            "parameters.coolant_flow",
            "parameters.coolant_cp",
            "parameters.T_coolant",
        ),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=POWER,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="CSTR-pressure",
        statement="P_out - P_in + dP = 0",
        dependencies=("inlet.state.P", "outlet.state.P", "parameters.pressure_drop"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=PRESSURE,
        source=SPECIFICATION,
    ),
)

_SENSITIVITY_NOTE: Final = (
    "The residual rows are differentiated exactly through K01, but a kinetic CSTR can have "
    "several steady states, so the outlet state has no unique causal sensitivity to the inlet "
    "state or the parameters; it is declared unavailable and reported as absent rather than as "
    "zeros (T05 spec §4.5, blueprint §5.2)."
)


@cache
def _artifact_hash() -> str:
    return file_sha256(Path(__file__))


@dataclass(frozen=True)
class KineticCSTR:
    """One cooled CSTR instance: one reaction, first order in its key reactant (§A1.2)."""

    unit_id: str
    provider: PropertyProvider
    #: `nu_i`, in `components` order; pinned inputs. Mass-conserving by the construction check.
    stoichiometry: tuple[float, ...]
    #: The key reactant `k`, a component id with `nu_k < 0`. Configuration, not a pinned input.
    key_component: str
    #: `Da`, the Damköhler number at `T_ref`, `>= 0`. A pinned input.
    damkohler: float
    #: `T_ref`, K, in the provider's domain. A pinned input.
    reference_temperature: float
    #: `T_s`, K (a temperature difference), `> 0`. A pinned input.
    temperature_scale: float
    #: `F_c`, mol/s, `>= 0`. A pinned input.
    coolant_flow: float
    #: `c_c`, J/(mol K), `> 0`. A pinned input.
    coolant_cp: float
    #: `T_c`, K, in the provider's domain. A pinned input.
    coolant_temperature: float
    #: The outlet's declared phase, `VAPOR` or `LIQUID`. Configuration.
    phase: Phase
    context: EvaluationContext
    #: Declared pressure drop, Pa, `>= 0`. A pinned input.
    pressure_drop: float = 0.0
    #: The declared regime of the inlet; `None` means its split is lifted by its producer.
    inlet_phase: Phase | None = "VAPOR"
    components: tuple[str, ...] = COMPONENTS
    #: `M_i`, kg/mol, in `components` order; read only by the mass-conservation check.
    molar_masses: tuple[float, ...] = MOLAR_MASSES

    def __post_init__(self) -> None:
        count = len(self.components)
        if len(self.stoichiometry) != count or len(self.molar_masses) != count:
            raise ValueError(
                f"{self.unit_id}: {len(self.stoichiometry)} stoichiometric coefficients and "
                f"{len(self.molar_masses)} molar masses for {count} components {self.components}"
            )
        if self.phase not in OUTLET_PHASES:
            raise ValueError(
                f"{self.unit_id}: outlet phase {self.phase!r} is not one of {OUTLET_PHASES}"
            )
        # A non-finite pin is misuse with no registered code (T05 spec §3.5 as amended): the
        # revision path refuses it before construction (`parameter_quantity_invalid`).
        scalars = {
            "damkohler": self.damkohler,
            "T_ref": self.reference_temperature,
            "T_scale": self.temperature_scale,
            "coolant_flow": self.coolant_flow,
            "coolant_cp": self.coolant_cp,
            "T_coolant": self.coolant_temperature,
            "pressure_drop": self.pressure_drop,
        }
        for name, value in scalars.items():
            if not math.isfinite(value):
                raise ValueError(f"{self.unit_id}: {name} = {value} is not finite")
        if not all(math.isfinite(mass) for mass in self.molar_masses):
            raise ValueError(f"{self.unit_id}: molar masses {self.molar_masses} are not finite")

        # §A1.2's construction refusals: the three carried from T05 §6.2 in the conversion
        # reactor's order, then the eight new ones in the order the spec lists them.
        if self.key_component not in self.components or not (
            self.stoichiometry[self.key_index] < 0.0
        ):
            raise SpecificationError(
                "key_not_reactant\n"
                f"{self.unit_id}: the key component {self.key_component!r} is not a reactant of "
                f"nu = {self.stoichiometry} over {self.components}; its coefficient must be "
                "negative"
            )
        pairs = tuple(zip(self.stoichiometry, self.molar_masses, strict=True))
        finite = all(math.isfinite(coefficient) for coefficient in self.stoichiometry)
        net = math.fsum(coefficient * mass for coefficient, mass in pairs) if finite else math.nan
        gross = math.fsum(abs(coefficient) * mass for coefficient, mass in pairs)
        if not abs(net) <= MASS_CONSERVATION_RELATIVE * gross:
            raise SpecificationError(
                "stoichiometry_not_mass_conserving\n"
                f"{self.unit_id}: nu = {self.stoichiometry} with M = {self.molar_masses} kg/mol "
                f"gives sum nu_i M_i = {net} kg/mol, past {MASS_CONSERVATION_RELATIVE} x "
                f"sum |nu_i| M_i"
            )
        described = self.provider.describe()
        convention = described.reference_convention
        if convention not in REACTION_CONSISTENT_CONVENTIONS:
            raise SpecificationError(
                f"{reference_convention_not_reaction_consistent(convention)}\n"
                f"{self.unit_id}: the provider's reference convention {convention!r} is not in "
                f"ADR 0011 D2's reaction-consistent set {sorted(REACTION_CONSISTENT_CONVENTIONS)}; "
                "a total-enthalpy balance over it would not carry an enthalpy of reaction"
            )
        if not self.damkohler >= 0.0:
            raise SpecificationError(
                "damkohler_negative\n"
                f"{self.unit_id}: damkohler = {self.damkohler}; a rate constant is not negative"
            )
        if not self.temperature_scale > 0.0:
            raise SpecificationError(
                "temperature_scale_not_positive\n"
                f"{self.unit_id}: T_scale = {self.temperature_scale} K must be positive"
            )
        if not self.coolant_flow >= 0.0:
            raise SpecificationError(
                "coolant_flow_negative\n"
                f"{self.unit_id}: coolant_flow = {self.coolant_flow} mol/s is negative"
            )
        if not self.coolant_cp > 0.0:
            raise SpecificationError(
                "coolant_cp_not_positive\n"
                f"{self.unit_id}: coolant_cp = {self.coolant_cp} J/(mol K) must be positive"
            )
        low, high = described.domain["T"]
        if not low <= self.reference_temperature <= high:
            raise SpecificationError(
                "reference_temperature_outside_domain\n"
                f"{self.unit_id}: T_ref = {self.reference_temperature} K is outside the provider's "
                f"domain [{low}, {high}] K"
            )
        if not low <= self.coolant_temperature <= high:
            raise SpecificationError(
                "coolant_temperature_outside_domain\n"
                f"{self.unit_id}: T_coolant = {self.coolant_temperature} K is outside the "
                f"provider's domain [{low}, {high}] K"
            )
        if not self.pressure_drop >= 0.0:
            raise SpecificationError(
                "pressure_drop_negative\n"
                f"{self.unit_id}: pressure_drop = {self.pressure_drop} Pa; a reactor does not "
                "raise its pressure"
            )
        exponent = (high - self.reference_temperature) / self.temperature_scale
        if not exponent <= MAX_RATE_EXPONENT:
            raise SpecificationError(
                "rate_exponent_overflow\n"
                f"{self.unit_id}: (T_max - T_ref)/T_s = {exponent} past {MAX_RATE_EXPONENT}; the "
                "rate's exponential would not be finite over the whole domain"
            )

    @property
    def model_id(self) -> str:
        return MODEL_ID

    @property
    def key_index(self) -> int:
        return self.components.index(self.key_component)

    def stoichiometry_parameter(self, component: str) -> str:
        return f"{self.unit_id}.nu.{component}"

    @property
    def damkohler_parameter(self) -> str:
        return f"{self.unit_id}.damkohler"

    @property
    def reference_temperature_parameter(self) -> str:
        return f"{self.unit_id}.T_ref"

    @property
    def temperature_scale_parameter(self) -> str:
        return f"{self.unit_id}.T_scale"

    @property
    def coolant_flow_parameter(self) -> str:
        return f"{self.unit_id}.coolant_flow"

    @property
    def coolant_cp_parameter(self) -> str:
        return f"{self.unit_id}.coolant_cp"

    @property
    def coolant_temperature_parameter(self) -> str:
        return f"{self.unit_id}.T_coolant"

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
            title="SYN-001 kinetic CSTR",
            description=(
                "A cooled, well-mixed reactor with one reaction, first order in its key reactant "
                "at a synthetic Frank-Kamenetskii rate; the outlet flows, temperature and "
                "pressure and the coolant duty are calculated."
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
                        "The rate is substituted into the mole rows and the duty is a free "
                        "variable, so every row is differentiated exactly through the K01 "
                        "adapter; the enthalpy blocks supply their declared-sparse analytic "
                        "derivatives (T08 build-first §A1.4)."
                    ),
                ),
            ),
            initialization=Initialization(
                strategy="local_initializer",
                notes=(
                    "The isothermal state at T_init (T_c for a dormant inlet with F_c c_c > 0, "
                    "else T_in): the key's outlet n_in,k / (1 + |nu_k| Da e(T_init)), the others "
                    "from the stoichiometry, P_in - dP, and Q = F_c c_c (T_c - T_init). Not a "
                    "steady state (T08 build-first §A1.4)."
                ),
            ),
            validity=Validity(
                components=self.components,
                phases=("liquid", "vapor", "zero_flow"),
                limitations=(
                    "One reaction, first order in a key reactant, at the synthetic rate "
                    "r = Da exp((T_out - T_ref)/T_s) n_out,k: no Arrhenius or real-chemistry "
                    "claim; the coolant is a capacity rate F_c c_c leaving at the reactor "
                    "temperature (the high-NTU limit) (L-CSTR-1).",
                    "The energy balance is in total-enthalpy form on the provider's formation "
                    "datum; constructed only over a provider whose reference convention is in "
                    "ADR 0011 D2's reaction-consistent set {SYN-001-ref-v1}. On SYN-001 every "
                    "mass-conserving liquid reaction is exactly thermoneutral and a vapour "
                    "reaction has dh_r = sum nu_i L_i.",
                    "Mass conservation is a construction check with SYN-001's molar masses "
                    "(0.100 kg/mol each), |sum nu_i M_i| <= 1e-9 sum |nu_i| M_i, not a row.",
                    "The outlet is single-phase by declaration (vapor or liquid) and is checked "
                    "by R-007's admissibility criterion; an inadmissible one is "
                    "inadmissible_phase(outlet, <PHASE>).",
                    f"The {INITIALIZER_LIMITATION} (L-CSTR-3); a kinetic CSTR may have several "
                    "steady states.",
                    "A dormant inlet with F_c c_c > 0 gives a dormant outlet at T_c and Q = 0, "
                    "regular. With F_c c_c = 0 no row reads a dormant outlet's temperature: v0.1 "
                    "does not certify an EO solve in which such a temperature appears (T05 spec "
                    "§4.7 (a); L-CSTR-2).",
                    "(T_max - T_ref)/T_s must not exceed 700, so the rate is finite over the "
                    "whole domain (rate_exponent_overflow).",
                    "P_in - dP and T_init must lie in the provider's domain.",
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
            package="T08",
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

        inlet_keys, inlet_blocks, inlet_inputs = stream_enthalpy_terms(
            self.provider, self.components, self.context, inlet, self.inlet_phase
        )
        outlet_block, outlet_feeding, outlet_keys = single_phase_enthalpy(
            self.provider, self.components, self.context, outlet, self.phase
        )

        key_flow = flow_id(outlet, self.key_component)
        equations: list[EquationSpec] = [
            EquationSpec(
                equation_id=row_id(self.unit_id, "CSTR-mole", component),
                build=kinetic_balance_row(
                    flow_id(inlet, component),
                    flow_id(outlet, component),
                    self.stoichiometry_parameter(component),
                    self.damkohler_parameter,
                    temperature_id(outlet),
                    self.reference_temperature_parameter,
                    self.temperature_scale_parameter,
                    key_flow,
                ),
                accumulation="holdup_balance",
                origin=origin(MODEL_ID, "CSTR-mole"),
            )
            for component in self.components
        ]
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "CSTR-duty"),
                build=energy_row(inlet_keys, outlet_keys, source=duty),
                accumulation="holdup_balance",
                origin=origin(MODEL_ID, "CSTR-duty"),
            )
        )
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "CSTR-cooling"),
                build=cooling_row(
                    duty,
                    self.coolant_flow_parameter,
                    self.coolant_cp_parameter,
                    self.coolant_temperature_parameter,
                    temperature_id(outlet),
                ),
                accumulation="algebraic",
                origin=origin(MODEL_ID, "CSTR-cooling"),
            )
        )
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "CSTR-pressure"),
                build=offset_row(
                    pressure_id(outlet), pressure_id(inlet), self.pressure_drop_parameter
                ),
                accumulation="algebraic",
                origin=origin(MODEL_ID, "CSTR-pressure"),
            )
        )

        kinds: dict[str, QuantityKind] = {
            row_id(self.unit_id, "CSTR-mole", component): "molar_flow"
            for component in self.components
        }
        kinds[row_id(self.unit_id, "CSTR-duty")] = "heat_rate"
        kinds[row_id(self.unit_id, "CSTR-cooling")] = "heat_rate"
        kinds[row_id(self.unit_id, "CSTR-pressure")] = "pressure"

        parameters: dict[str, float] = {
            self.stoichiometry_parameter(component): float(coefficient)
            for component, coefficient in zip(self.components, self.stoichiometry, strict=True)
        }
        parameters[self.damkohler_parameter] = float(self.damkohler)
        parameters[self.reference_temperature_parameter] = float(self.reference_temperature)
        parameters[self.temperature_scale_parameter] = float(self.temperature_scale)
        parameters[self.coolant_flow_parameter] = float(self.coolant_flow)
        parameters[self.coolant_cp_parameter] = float(self.coolant_cp)
        parameters[self.coolant_temperature_parameter] = float(self.coolant_temperature)
        parameters[self.pressure_drop_parameter] = float(self.pressure_drop)

        return Contribution(
            variable_ids=(duty,),
            equations=tuple(equations),
            variable_kinds={duty: "heat_rate"},
            row_kinds=kinds,
            blocks=(*inlet_blocks, outlet_block),
            block_inputs={**inlet_inputs, outlet_block.block_id: outlet_feeding},
            parameter_ids=tuple(parameters),
            parameters=parameters,
        )

    # -- evaluator ---------------------------------------------------------------------------

    def evaluate(
        self, inlets: Mapping[str, Sequence[StreamState]], context: EvaluationContext
    ) -> UnitEvaluation:
        """§A1.4: the isothermal local initializer at `T_init`, never a steady state."""
        connected = tuple(inlets.get("inlet", ()))
        if len(connected) != 1 or set(inlets) - {"inlet"}:
            raise SpecificationError(
                f"{self.unit_id}: a CSTR takes exactly one inlet stream, got {inlets!r}"
            )
        feed = connected[0]
        if len(feed.n) != len(self.components):
            raise SpecificationError(
                f"{self.unit_id}: inlet carries {len(feed.n)} components, expected "
                f"{len(self.components)}"
            )
        capacity = self.coolant_flow * self.coolant_cp
        dormant = feed.is_dormant
        initial = self.coolant_temperature if dormant and capacity > 0.0 else feed.temperature
        outlet_pressure = feed.pressure - float(self.pressure_drop)

        # (1) The outlet state's domain, checked before the exponential is formed (§A1.2).
        domain = self.provider.describe().domain
        low, high = domain["T"]
        if not low <= initial <= high:
            return typed_failure(
                "out_of_domain",
                "temperature_outside_domain(outlet)",
                f"T_init = {initial} K outside [{low}, {high}] K",
            )
        low, high = domain["P"]
        if not low <= outlet_pressure <= high:
            return typed_failure(
                "out_of_domain",
                "pressure_outside_domain(outlet)",
                f"P_in - dP = {outlet_pressure} Pa outside [{low}, {high}] Pa",
            )
        duty = capacity * (self.coolant_temperature - initial)

        # (2) A dormant inlet (§A1.4): a dormant outlet labelled with T_init, Q from the cooling
        # row — exactly 0.0 when F_c c_c > 0, since then T_init = T_c.
        if dormant:
            return UnitEvaluation(
                status="ok",
                outlets={
                    "outlet": StreamState(
                        n=tuple(0.0 for _ in self.components),
                        temperature=initial,
                        pressure=outlet_pressure,
                    )
                },
                duty=duty,
                phase_signature="ZERO_FLOW",
                provider_id=PROVIDER_ID,
                reference_convention=REFERENCE_CONVENTION,
                message=INITIALIZER_LIMITATION,
            )

        # (3) The isothermal outlet: the key's closed form, the others from the stoichiometry,
        # never clipped (ADR 0001 D2.3). The rate is formed as the rows form it.
        key = self.key_index
        scaled = self.damkohler * math.exp(
            (initial - self.reference_temperature) / self.temperature_scale
        )
        key_out = feed.n[key] / (1.0 + abs(self.stoichiometry[key]) * scaled)
        rate = scaled * key_out
        n_out = tuple(
            key_out if index == key else flow + coefficient * rate
            for index, (flow, coefficient) in enumerate(
                zip(feed.n, self.stoichiometry, strict=True)
            )
        )
        for component, flow in zip(self.components, n_out, strict=True):
            if flow < 0.0:
                return typed_failure(
                    "out_of_domain",
                    reactant_exhausted(component),
                    f"the isothermal rate r = {rate} mol/s at T_init = {initial} K gives "
                    f"n_out = {n_out} mol/s",
                )

        # (4) The inlet, as its rows write it: declared-phase admission or its producer's split.
        inlet = port_enthalpy(
            self.provider, feed, self.inlet_phase, self.components, context, port="inlet"
        )
        if inlet.failure is not None:
            return inlet.failure

        # (5) The declared outlet phase, by R-007's criterion at the initializer's state.
        outlet = StreamState(n=n_out, temperature=initial, pressure=outlet_pressure)
        admitted = port_enthalpy(
            self.provider, outlet, self.phase, self.components, context, port="outlet"
        )
        if admitted.failure is not None:
            return admitted.failure

        return UnitEvaluation(
            status="ok",
            outlets={"outlet": outlet},
            duty=duty,
            phase_signature=self.phase,
            provider_id=PROVIDER_ID,
            reference_convention=REFERENCE_CONVENTION,
            message=INITIALIZER_LIMITATION,
        )
