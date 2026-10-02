"""`syn001.conversion_reactor` — one reaction at a specified conversion of its key reactant (§6).

The outlet is a lifted TP-state stream, heater style (`lift_two_phase_stream`): a reaction may
leave the product two-phase, and that is a supported result. The extent `xi` is a free variable
fixed by `RX-conversion`; the duty `Q` is a free variable fixed, together with the outlet
temperature, by `RX-duty` and `RX-spec` — the specification row pins either `T_out`
(`outlet_temperature`, the heater's pattern: the duty is calculated) or `Q` (`duty`, the PH flash's
pattern: the temperature is calculated by the PH closure, T05 spec §4).

**The energy balance is in total-enthalpy form** (ADR 0011 D2): `Q + Hdot_in - Hdot_out = 0`,
with both enthalpies on the provider's formation datum. The heat of reaction is carried by the
outlet's changed composition and is never added as a separate `xi dh_r` term, which would count it
twice. That form is right only over a provider whose component enthalpies share one datum, so a
reactor is constructed only over a provider whose `reference_convention` is in the registered
reaction-consistent set, today `{"SYN-001-ref-v1"}`; otherwise construction refuses with
`reference_convention_not_reaction_consistent(<convention>)`.

**Mass conservation is a construction check, not a row**: `|sum nu_i M_i| <= 1e-9 sum |nu_i| M_i`
(spec §6.2). The component rows then conserve mass by construction; K04 checks components, not
mass (spec §12.5, INJ-T3). The provider declares no molar masses (`PropertyCapabilities` has no
such field, and `thermo/syn001.py` is not edited, ADR 0011 D3), so SYN-001's are stated here and a
test compares them with the component records.

**A reactant driven negative is refused, never clipped** (ADR 0001 D2.3): the first component, in
component order, whose outlet flow would be negative is `out_of_domain`,
`reactant_exhausted(<c>)`.

**A dormant inlet** (spec §4.7) gives a dormant outlet labelled with `T_spec` or the inlet's `T`,
`xi = 0` and `Q = 0`; in duty mode a nonzero `Q_spec` is `duty_into_dormant_stream`, because the
energy row forces it to zero. In duty mode no row reads the dormant outlet's temperature, so v0.1
does not solve an EO system with a dormant duty-mode reactor inlet.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Final, Literal

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
from openflowsheet.models.rows import (
    energy_row,
    extent_row,
    offset_row,
    reaction_balance_row,
    specification_row,
)
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
    TEMPERATURE,
)
from openflowsheet.models.syn001.admission import provider_refusal
from openflowsheet.models.syn001.ph_kernel import (
    PHState,
    closure_failure,
    ph_state,
    port_enthalpy,
    typed_failure,
)
from openflowsheet.models.syn001.tp_state import (
    TPState,
    lift_two_phase_stream,
    stream_enthalpy_terms,
    tp_state,
)
from openflowsheet.thermo import Phase, PropertyProvider, StreamState

MODEL_ID: Final = "syn001.conversion_reactor"

SPECIFICATION: Final = "docs/derivations/T05-unit-models-spec.md §6"

#: ADR 0011 D2's registered reaction-consistent reference conventions: those whose component
#: enthalpies share one formation datum, so that `sum nu_i h_i` is an enthalpy of reaction.
#: Extending the set takes a new decision recorded the same way, naming the convention's datum.
REACTION_CONSISTENT_CONVENTIONS: Final = frozenset({"SYN-001-ref-v1"})

#: SYN-001's molar masses, kg/mol, in `COMPONENTS` order (`docs/derivations/SYN-001.md`, component
#: table; `benchmarks/syn001/components.yaml`). Read only by the mass-conservation check.
MOLAR_MASSES: Final[tuple[float, ...]] = (0.100, 0.100, 0.100)

#: Spec §6.2: `|sum nu_i M_i| > 1e-9 sum |nu_i| M_i` is not mass-conserving.
MASS_CONSERVATION_RELATIVE: Final = 1e-9

EnergySpecification = Literal["outlet_temperature", "duty"]
ENERGY_SPECIFICATIONS: Final[tuple[EnergySpecification, ...]] = ("outlet_temperature", "duty")

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

_COMMON_EQUATIONS: Final[tuple[DeclaredEquation, ...]] = (
    DeclaredEquation(
        equation_id="RX-mole",
        statement="n_in,i - n_out,i + nu_i xi = 0 for every component i",
        dependencies=("inlet.state.n", "outlet.state.n", "extent.xi", "parameters.nu"),
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
        equation_id="RX-conversion",
        statement="xi - X n_in,k / (-nu_k) = 0, k the key reactant",
        dependencies=("inlet.state.n", "extent.xi", "parameters.conversion", "parameters.nu"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=MOLAR_FLOW,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="RX-pressure",
        statement="P_out - P_in + dP = 0",
        dependencies=("inlet.state.P", "outlet.state.P", "parameters.pressure_drop"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=PRESSURE,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="RX-equilibrium",
        statement=(
            "the outlet is the TP flash result at (T_out, P_out): v_i L - K_i(T_out, P_out) l_i V "
            "= 0 over the outlet's lifted split"
        ),
        dependencies=("outlet.state",),
        conditional_class="phase_conditional",
        accumulation=Accumulation(kind="algebraic"),
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="RX-duty",
        statement=(
            "Q + Hdot_in - Hdot_out = 0, Q positive into the unit; enthalpies on the provider's "
            "formation datum (ADR 0011 D2), so the heat of reaction is carried by Hdot and never "
            "added separately"
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
)

#: `RX-spec` is the one equation whose content depends on configuration (spec §6.2).
EQUATIONS: Final[Mapping[EnergySpecification, tuple[DeclaredEquation, ...]]] = {
    "outlet_temperature": (
        *_COMMON_EQUATIONS,
        DeclaredEquation(
            equation_id="RX-spec",
            statement="T_out - T_spec = 0",
            dependencies=("outlet.state.T", "parameters.T_spec"),
            conditional_class="unconditional",
            accumulation=Accumulation(kind="algebraic"),
            dimension=TEMPERATURE,
            source=SPECIFICATION,
        ),
    ),
    "duty": (
        *_COMMON_EQUATIONS,
        DeclaredEquation(
            equation_id="RX-spec",
            statement="Q - Q_spec = 0",
            dependencies=("duty.Q", "parameters.Q_spec"),
            conditional_class="unconditional",
            accumulation=Accumulation(kind="algebraic"),
            dimension=POWER,
            source=SPECIFICATION,
        ),
    ),
}

_SENSITIVITY_NOTE: Final = (
    "The residual rows are differentiated exactly through K01, but the sensitivity of the outlet "
    "state or the duty to the inlet state or a specification runs through the causal evaluator "
    "(the TP split at T_spec, or the PH closure, whose implicit dT/dH* changes slope at every "
    "phase boundary); no interface supplies it, so it is declared unavailable and reported as "
    "absent rather than as zeros (T05 spec §4.5, blueprint §5.2)."
)


def extent_id(unit: str) -> str:
    """The free variable holding a reactor's extent, mol/s (spec §3.2)."""
    return f"{unit}.xi"


def reactant_exhausted(component: str) -> str:
    """The registered code for a reactant the specified conversion would drive negative."""
    return f"reactant_exhausted({component})"


def reference_convention_not_reaction_consistent(convention: str) -> str:
    """The registered construction code for a provider outside ADR 0011 D2's set (§13.3)."""
    return f"reference_convention_not_reaction_consistent({convention})"


@cache
def _artifact_hash() -> str:
    return file_sha256(Path(__file__))


@dataclass(frozen=True)
class ConversionReactor:
    """One reactor instance: one reaction, a key reactant's conversion, and one energy spec."""

    unit_id: str
    provider: PropertyProvider
    #: `nu_i`, in `components` order; pinned inputs. Mass-conserving by the construction check.
    stoichiometry: tuple[float, ...]
    #: The key reactant `k`, a component id with `nu_k < 0`. Configuration, not a pinned input.
    key_component: str
    #: `X` in `[0, 1]`, the fraction of the key reactant's inlet flow converted. A pinned input.
    conversion: float
    #: `outlet_temperature` (`value` is `T_spec`, K, in the domain) or `duty` (`value` is
    #: `Q_spec`, W, positive into the unit).
    energy_specification: str
    #: `T_spec` or `Q_spec` according to `energy_specification`. A pinned input.
    value: float
    context: EvaluationContext
    #: Declared pressure drop, Pa, `>= 0`.
    pressure_drop: float = 0.0
    #: The declared regime of the inlet; `None` means its split is lifted by its producer.
    inlet_phase: Phase | None = "LIQUID"
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
        if self.energy_specification not in ENERGY_SPECIFICATIONS:
            raise SpecificationError(
                f"unknown_specification({self.energy_specification})\n"
                f"{self.unit_id}: a reactor's energy is specified by one of "
                f"{list(ENERGY_SPECIFICATIONS)}"
            )
        if not math.isfinite(self.value):
            raise ValueError(f"{self.unit_id}: the specified value {self.value} is not finite")
        # A non-finite pressure drop or molar mass is misuse with no registered code (spec §3.5
        # as amended, ruling round §3 block, U1 (2)): `+inf` passed the sign test below, and an
        # infinite molar mass passed the mass check (`inf <= 1e-9 inf`).
        if not math.isfinite(self.pressure_drop):
            raise ValueError(f"{self.unit_id}: pressure_drop = {self.pressure_drop} is not finite")
        if not all(math.isfinite(mass) for mass in self.molar_masses):
            raise ValueError(f"{self.unit_id}: molar masses {self.molar_masses} are not finite")

        # Spec §6.2's construction refusals, in the order it lists them.
        if not 0.0 <= self.conversion <= 1.0:
            raise SpecificationError(
                "conversion_outside_unit_interval\n"
                f"{self.unit_id}: conversion {self.conversion} is outside [0, 1]"
            )
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
        convention = self.provider.describe().reference_convention
        if convention not in REACTION_CONSISTENT_CONVENTIONS:
            raise SpecificationError(
                f"{reference_convention_not_reaction_consistent(convention)}\n"
                f"{self.unit_id}: the provider's reference convention {convention!r} is not in "
                f"ADR 0011 D2's reaction-consistent set {sorted(REACTION_CONSISTENT_CONVENTIONS)}; "
                "a total-enthalpy balance over it would not carry an enthalpy of reaction"
            )
        if self.energy_specification == "outlet_temperature" and not (T_MIN <= self.value <= T_MAX):
            raise SpecificationError(
                "outlet_temperature_outside_domain\n"
                f"{self.unit_id}: T_spec = {self.value} K is outside the declared domain "
                f"[{T_MIN}, {T_MAX}] K"
            )
        if not self.pressure_drop >= 0.0:
            raise SpecificationError(
                "negative_pressure_drop\n"
                f"{self.unit_id}: pressure_drop = {self.pressure_drop} Pa; a reactor does not "
                "raise its pressure"
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
    def conversion_parameter(self) -> str:
        return f"{self.unit_id}.conversion"

    @property
    def pressure_drop_parameter(self) -> str:
        return f"{self.unit_id}.pressure_drop"

    @property
    def specification_parameter(self) -> str:
        """`<U>.T_spec` in outlet-temperature mode, `<U>.Q_spec` in duty mode."""
        suffix = "T_spec" if self.energy_specification == "outlet_temperature" else "Q_spec"
        return f"{self.unit_id}.{suffix}"

    # -- declaration -------------------------------------------------------------------------

    def ports(self) -> tuple[Port, ...]:
        return PORTS

    def declared_equations(self) -> tuple[DeclaredEquation, ...]:
        return EQUATIONS["duty" if self.energy_specification == "duty" else "outlet_temperature"]

    def manifest(self) -> Mapping[str, Any]:
        return manifest_document(
            model_id=MODEL_ID,
            title="SYN-001 conversion reactor",
            description=(
                "One reaction at a specified conversion of its key reactant, with a specified "
                "outlet temperature or duty; the extent, the outlet phase split and the duty or "
                "the outlet temperature are calculated."
            ),
            ports=PORTS,
            equations=self.declared_equations(),
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
                        "The extent and the duty are free variables, the outlet's phase split is "
                        "lifted into variables and its temperature is a free column, so every "
                        "row is differentiated exactly through the K01 adapter; the K-value and "
                        "enthalpy blocks supply their declared-sparse analytic derivatives "
                        "(T05 spec §4.5)."
                    ),
                ),
            ),
            initialization=Initialization(
                strategy="local_initializer",
                notes=(
                    "The causal evaluator: the extent from the conversion, the outlet flows from "
                    "the stoichiometry, then the TP split at T_spec or the PH kernel at the "
                    "inlet's enthalpy plus Q_spec (T05 spec §6.3)."
                ),
            ),
            validity=Validity(
                components=self.components,
                phases=("liquid", "vapor", "vapor_liquid", "zero_flow"),
                limitations=(
                    "One reaction at a specified conversion of a key reactant; no chemical "
                    "equilibrium and no kinetics (T05 spec §19 Q7).",
                    "The energy balance is in total-enthalpy form on the provider's formation "
                    "datum; constructed only over a provider whose reference convention is in "
                    "ADR 0011 D2's reaction-consistent set {SYN-001-ref-v1}. On SYN-001 every "
                    "mass-conserving liquid reaction is exactly thermoneutral and a vapour "
                    "reaction has dh_r = sum nu_i L_i (T05 spec §6.1).",
                    "Mass conservation is a construction check with SYN-001's molar masses "
                    "(0.100 kg/mol each), |sum nu_i M_i| <= 1e-9 sum |nu_i| M_i, not a row.",
                    "A conversion that would drive a reactant negative is refused as "
                    "reactant_exhausted(<c>), never clipped (ADR 0001 D2.3).",
                    "Ideal VLE from the provider's TP flash; no third phase (T05 spec §4.6). A "
                    "two-phase outlet is a supported result.",
                    "In duty mode a single flowing component takes the PH kernel's saturation "
                    "route (T05 spec §4.4).",
                    "In duty mode every answer of the PH kernel is accepted only if the "
                    "closure's energy, equilibrium and material rows hold at K04's registered "
                    "tolerances, the provider's K and h taken as exact; a near-pure outlet "
                    "enthalpy inside the latent jump that the temperature route misses is "
                    "answered by the saturation-band route. Above about 1e8 mol/s, where tau_E is "
                    "below the double resolution of H, the answer is ph_ill_conditioned (T05b "
                    "spec §5.1-§5.3).",
                    "In duty mode, on the EO path a single flowing component in the latent jump, "
                    "a near-pure outlet and a dormant inlet are solved and certified under the "
                    "phase contract T05b-phase-contract-v2 (T05b spec §11). SolvePolicy's "
                    "default, T03-phase-contract-v1, keeps T05's contract rules verbatim: under "
                    "it a single flowing component in the jump is never VERIFIED and a dormant "
                    "outlet whose label must move is not CONVERGED (T05b spec §6.6, B08-B10, "
                    "B16).",
                    "A dormant inlet: the causal face labels the outlet with the inlet "
                    "temperature (T_spec in outlet-temperature mode, where RX-spec reads it) and "
                    "refuses a nonzero duty as duty_into_dormant_stream. In duty mode, on the EO "
                    "path under T05b-phase-contract-v2 the same specification closes "
                    "SPECIFICATION_CONFLICT with zero_flow_conflict naming the duty row; no other "
                    "attempt signature is searched for (T05b spec §7.8 (iv), §17).",
                    "P_in - dP must lie in the provider's pressure domain.",
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
        duty = duty_id(self.unit_id)
        extent = extent_id(self.unit_id)

        inlet_keys, inlet_blocks, inlet_inputs = stream_enthalpy_terms(
            self.provider, self.components, self.context, inlet, self.inlet_phase
        )
        lifted, outlet_keys = lift_two_phase_stream(
            unit_id=self.unit_id,
            model_id=MODEL_ID,
            equilibrium_equation_id="RX-equilibrium",
            stream=outlet,
            provider=self.provider,
            components=self.components,
            context=self.context,
        )

        equations: list[EquationSpec] = []
        for component in self.components:
            equations.append(
                EquationSpec(
                    equation_id=row_id(self.unit_id, "RX-mole", component),
                    build=reaction_balance_row(
                        flow_id(inlet, component),
                        self.stoichiometry_parameter(component),
                        extent,
                        flow_id(outlet, component),
                    ),
                    accumulation="holdup_balance",
                    origin=origin(MODEL_ID, "RX-mole"),
                )
            )
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "RX-conversion"),
                build=extent_row(
                    extent,
                    self.conversion_parameter,
                    flow_id(inlet, self.key_component),
                    self.stoichiometry_parameter(self.key_component),
                ),
                accumulation="algebraic",
                origin=origin(MODEL_ID, "RX-conversion"),
            )
        )
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "RX-pressure"),
                build=offset_row(
                    pressure_id(outlet), pressure_id(inlet), self.pressure_drop_parameter
                ),
                accumulation="algebraic",
                origin=origin(MODEL_ID, "RX-pressure"),
            )
        )
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "RX-duty"),
                build=energy_row(inlet_keys, outlet_keys, source=duty),
                accumulation="holdup_balance",
                origin=origin(MODEL_ID, "RX-duty"),
            )
        )
        specified = (
            temperature_id(outlet) if self.energy_specification == "outlet_temperature" else duty
        )
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "RX-spec"),
                build=specification_row(specified, self.specification_parameter),
                accumulation="algebraic",
                origin=origin(MODEL_ID, "RX-spec"),
            )
        )

        kinds: dict[str, QuantityKind] = {
            row_id(self.unit_id, "RX-mole", component): "molar_flow"
            for component in self.components
        }
        kinds[row_id(self.unit_id, "RX-conversion")] = "molar_flow"
        kinds[row_id(self.unit_id, "RX-pressure")] = "pressure"
        kinds[row_id(self.unit_id, "RX-duty")] = "heat_rate"
        kinds[row_id(self.unit_id, "RX-spec")] = (
            "temperature" if self.energy_specification == "outlet_temperature" else "heat_rate"
        )

        parameters: dict[str, float] = {
            self.stoichiometry_parameter(component): float(coefficient)
            for component, coefficient in zip(self.components, self.stoichiometry, strict=True)
        }
        parameters[self.conversion_parameter] = float(self.conversion)
        parameters[self.pressure_drop_parameter] = float(self.pressure_drop)
        parameters[self.specification_parameter] = float(self.value)

        return Contribution(
            variable_ids=(duty, extent, *lifted.variable_ids),
            equations=(*equations, *lifted.equations),
            variable_kinds={duty: "heat_rate", extent: "molar_flow", **lifted.variable_kinds},
            row_kinds={**kinds, **lifted.row_kinds},
            blocks=(*inlet_blocks, *lifted.blocks),
            block_inputs={**inlet_inputs, **lifted.block_inputs},
            parameter_ids=tuple(parameters),
            parameters=parameters,
        )

    # -- evaluator ---------------------------------------------------------------------------

    def evaluate(
        self, inlets: Mapping[str, Sequence[StreamState]], context: EvaluationContext
    ) -> UnitEvaluation:
        return self.evaluate_with_split(inlets, context)[0]

    def evaluate_with_split(
        self, inlets: Mapping[str, Sequence[StreamState]], context: EvaluationContext
    ) -> tuple[UnitEvaluation, TPState | None]:
        """`evaluate`, and the outlet's phase split where one was computed (spec §6.3).

        The split — the TP flash at `T_spec`, or the PH kernel's at `T*` — is what the lifted
        outlet's variables hold at the physical root, and `UnitEvaluation` has no field for it.
        It is `None` when the evaluator stopped before the split (a dormant inlet, an exhausted
        reactant, an outlet pressure off the domain, an inadmissible inlet, a failed closure).
        """
        connected = tuple(inlets.get("inlet", ()))
        if len(connected) != 1 or set(inlets) - {"inlet"}:
            raise SpecificationError(
                f"{self.unit_id}: a reactor takes exactly one inlet stream, got {inlets!r}"
            )
        feed = connected[0]
        if len(feed.n) != len(self.components):
            raise SpecificationError(
                f"{self.unit_id}: inlet carries {len(feed.n)} components, expected "
                f"{len(self.components)}"
            )
        outlet_pressure = feed.pressure - float(self.pressure_drop)
        by_temperature = self.energy_specification == "outlet_temperature"

        # (1) Spec §4.7: a dormant outlet carries T_spec or the inlet temperature as a label.
        if feed.is_dormant:
            if not by_temperature and self.value != 0.0:
                return (
                    typed_failure(
                        "error",
                        "duty_into_dormant_stream",
                        f"Q_spec = {self.value} W into a dormant stream; RX-duty forces Q = 0",
                    ),
                    None,
                )
            dormant = StreamState(
                n=tuple(0.0 for _ in self.components),
                temperature=float(self.value) if by_temperature else feed.temperature,
                pressure=outlet_pressure,
            )
            return (
                UnitEvaluation(
                    status="ok",
                    outlets={"outlet": dormant},
                    duty=0.0,
                    extent=0.0,
                    phase_signature="ZERO_FLOW",
                    reference_convention=REFERENCE_CONVENTION,
                ),
                None,
            )

        # (2) The extent and the outlet flows; no clipping. The key's outlet is `n_k - X n_k`,
        # the same function as the rows' `n_k + nu_k xi` but written so that rounding cannot
        # push it below zero (`fl(X n_k) <= n_k` for `X <= 1`): at `X = 1` it is exactly 0.0
        # for every `nu_k`, not only a power of two (spec §6.3 as amended, R-051, review S2).
        # Every other component keeps `n_i + nu_i xi`, so only a non-key can be exhausted.
        key = self.key_index
        converted = self.conversion * feed.n[key]
        extent = converted / (-self.stoichiometry[key])
        n_out = tuple(
            feed.n[key] - converted if index == key else flow + coefficient * extent
            for index, (flow, coefficient) in enumerate(
                zip(feed.n, self.stoichiometry, strict=True)
            )
        )
        for component, flow in zip(self.components, n_out, strict=True):
            if flow < 0.0:
                return (
                    typed_failure(
                        "out_of_domain",
                        reactant_exhausted(component),
                        f"conversion {self.conversion} of {self.key_component} gives xi = "
                        f"{extent} mol/s and n_out = {n_out} mol/s",
                    ),
                    None,
                )

        # (3)
        if not P_MIN <= outlet_pressure <= P_MAX:
            return (
                typed_failure(
                    "out_of_domain",
                    "pressure_outside_domain(outlet)",
                    f"P_in - dP = {outlet_pressure} Pa outside [{P_MIN}, {P_MAX}] Pa",
                ),
                None,
            )

        # (4) Inlet enthalpy (spec §5.2 (3)).
        inlet = port_enthalpy(
            self.provider, feed, self.inlet_phase, self.components, context, port="inlet"
        )
        if inlet.failure is not None:
            return inlet.failure, None
        assert inlet.enthalpy_flow is not None

        # (5) The outlet: the TP split at T_spec and the duty it takes, or the PH closure.
        closure: PHState | None = None
        if by_temperature:
            outlet_temperature = float(self.value)
            split = tp_state(
                self.provider,
                StreamState(n=n_out, temperature=outlet_temperature, pressure=outlet_pressure),
                context,
            )
            if split.status != "ok":
                return provider_refusal("outlet", split.status, split.message), None
            assert split.enthalpy_flow is not None
            duty = split.enthalpy_flow - inlet.enthalpy_flow
            iterations = split.iterations
        else:
            closure = ph_state(
                self.provider, n_out, outlet_pressure, inlet.enthalpy_flow + self.value, context
            )
            if closure.status != "ok":
                return closure_failure(closure), None
            assert closure.temperature is not None and closure.split is not None
            outlet_temperature, split = closure.temperature, closure.split
            duty = float(self.value)
            iterations = closure.evaluations

        return (
            UnitEvaluation(
                status="ok",
                outlets={
                    "outlet": StreamState(
                        n=n_out, temperature=outlet_temperature, pressure=outlet_pressure
                    )
                },
                duty=duty,
                extent=extent,
                phase_signature=split.phase_signature,
                iterations=iterations,
                provider_id=split.provider_id,
                reference_convention=split.reference_convention,
                closure=closure,
            ),
            split,
        )
