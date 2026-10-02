"""`syn001.ph_flash` — a two-outlet flash at a specified duty and pressure drop (T05 spec §5).

K02's `TPFlash` with the temperature freed: the two outlets are the phase split (flash style,
`FLASH-equilibrium`'s division-free form over the outlet streams and their lifted totals), and the
row that fixes the temperature is the energy balance, with the heat input a variable pinned by its
own specification row (`PHF-Q`, the heater's pattern, so an A02 binding can free it, spec §5.1).

**The causal face is the PH kernel** (`ph_kernel.ph_state`, spec §4.4): a bracketed solve of
`Hdot_TP(n, T, P_out) = Hdot_in + Q_spec` on the provider's TP flash, with an explicit saturation
route for a single flowing component. The provider is asked for nothing it did not already offer.

**The inlet's regime is configuration, not state** (`inlet_phase`): a declared single phase is
checked by R-007's admissibility criterion before its enthalpy is used, so the evaluator's
`Hdot_in` is the one the rows write (spec F7 found K02's flash omits that check); `None` means the
producer lifted the inlet's split and this unit reads the producer's blocks.

**A dormant inlet is singular in the EO face** (spec §4.7): at zero flow no row but `PHF-T` reads
the outlet temperatures, so v0.1 does not solve an EO system with a dormant PH-flash inlet. The
causal face answers it: dormant outlets labelled with the inlet's temperature, and a nonzero
specified duty is `duty_into_dormant_stream`, because the energy row would force it to zero.
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
from openflowsheet.models.rows import (
    balance_row,
    definition_row,
    energy_row,
    equilibrium_row,
    offset_row,
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
from openflowsheet.models.syn001.blocks import LnKBlock
from openflowsheet.models.syn001.flash import total_flow_id
from openflowsheet.models.syn001.ph_kernel import (
    PHState,
    closure_failure,
    ph_state,
    port_enthalpy,
    typed_failure,
)
from openflowsheet.models.syn001.tp_state import (
    lnk_block_id,
    single_phase_enthalpy,
    stream_enthalpy_terms,
)
from openflowsheet.thermo import Phase, PropertyProvider, StreamState

MODEL_ID: Final = "syn001.ph_flash"

#: Where the equations are stated. T05's models are specified by the T05 document, not SYN-001's.
SPECIFICATION: Final = "docs/derivations/T05-unit-models-spec.md §5"

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
        name="vapor",
        kind="material",
        direction="outlet",
        multiplicity=1,
        component_mapping="revision_component_set",
        state_definition="nTP-v1",
        phase_capabilities=("vapor",),
    ),
    Port(
        name="liquid",
        kind="material",
        direction="outlet",
        multiplicity=1,
        component_mapping="revision_component_set",
        state_definition="nTP-v1",
        phase_capabilities=("liquid",),
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
        equation_id="PHF-mole",
        statement="n_in,i - n_vap,i - n_liq,i = 0 for every component i",
        dependencies=("inlet.state.n", "vapor.state.n", "liquid.state.n"),
        conditional_class="unconditional",
        accumulation=Accumulation(
            kind="holdup_balance",
            holdup=Holdup(
                symbol="N_i", quantity="component moles held in the flash drum", dimension=MOLE
            ),
        ),
        dimension=MOLAR_FLOW,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="PHF-equilibrium",
        statement="n_vap,i N_liq - K_i(T_vap, P_vap) n_liq,i N_vap = 0 for every component i",
        dependencies=("vapor.state", "liquid.state.n"),
        conditional_class="phase_conditional",
        accumulation=Accumulation(kind="algebraic"),
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="PHF-T",
        statement="T_vap - T_liq = 0",
        dependencies=("vapor.state.T", "liquid.state.T"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=TEMPERATURE,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="PHF-pressure",
        statement="P_out - P_in + dP = 0 for the vapor and the liquid outlet",
        dependencies=(
            "inlet.state.P",
            "vapor.state.P",
            "liquid.state.P",
            "parameters.pressure_drop",
        ),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=PRESSURE,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="PHF-duty",
        statement="Q + Hdot_in - Hdot_vap - Hdot_liq = 0, Q positive into the unit",
        dependencies=("inlet.state", "vapor.state", "liquid.state", "duty.Q"),
        conditional_class="unconditional",
        accumulation=Accumulation(
            kind="holdup_balance",
            holdup=Holdup(
                symbol="U",
                quantity="internal energy of the flash drum contents",
                dimension=ENERGY,
            ),
        ),
        dimension=POWER,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="PHF-Q",
        statement="Q - Q_spec = 0",
        dependencies=("duty.Q", "parameters.Q_spec"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=POWER,
        source=SPECIFICATION,
    ),
)

_SENSITIVITY_NOTE: Final = (
    "The residual rows are differentiated exactly through K01, but the sensitivity of an outlet "
    "state to an inlet state or a specification runs through the PH closure, whose implicit "
    "dT/dH* changes slope at every phase boundary; no interface supplies it, so it is declared "
    "unavailable and reported as absent rather than as zeros (T05 spec §4.5, blueprint §5.2)."
)


@cache
def _artifact_hash() -> str:
    return file_sha256(Path(__file__))


@dataclass(frozen=True)
class PHFlash:
    """One flash instance: a specified duty and pressure drop; the temperature is calculated."""

    unit_id: str
    provider: PropertyProvider
    #: `Q_spec`, W, positive into the unit; any finite value, `0` is adiabatic.
    duty: float
    context: EvaluationContext
    #: Declared pressure drop, Pa, `>= 0`.
    pressure_drop: float = 0.0
    #: The declared regime of the inlet; `None` means its split is lifted by its producer.
    inlet_phase: Phase | None = "LIQUID"
    components: tuple[str, ...] = COMPONENTS

    def __post_init__(self) -> None:
        # Spec §5.1 as amended (ruling round §3 block, U1 (2), review N6): a non-finite pinned
        # input is misuse, refused here; a NaN duty used to reach the kernel and come back as
        # ph_ill_conditioned, a typed answer with the wrong name.
        for label, number in (("duty", self.duty), ("pressure_drop", self.pressure_drop)):
            if not math.isfinite(number):
                raise ValueError(f"{self.unit_id}: {label} = {number} is not finite")
        if self.pressure_drop < 0.0:
            raise SpecificationError(
                "negative_pressure_drop\n"
                f"{self.unit_id}: pressure_drop = {self.pressure_drop} Pa; a flash does not "
                "raise its pressure"
            )

    @property
    def model_id(self) -> str:
        return MODEL_ID

    @property
    def duty_parameter(self) -> str:
        return f"{self.unit_id}.Q_spec"

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
            title="SYN-001 PH flash",
            description=(
                "Two-outlet equilibrium flash at a specified duty and pressure drop; the "
                "temperature is calculated from the energy balance."
            ),
            ports=PORTS,
            equations=EQUATIONS,
            derivatives=(
                DerivativeDeclaration(
                    output="vapor.state",
                    with_respect_to=("inlet.state", "specifications"),
                    method="unavailable",
                    regime="all",
                    notes=_SENSITIVITY_NOTE,
                ),
                DerivativeDeclaration(
                    output="liquid.state",
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
                        "The two outlets are the phase split and the temperature is a free "
                        "column fixed by the energy row, so every row is written over flowsheet "
                        "variables and differentiated exactly through the K01 adapter; the "
                        "K-value and enthalpy blocks supply their declared-sparse analytic "
                        "derivatives (T05 spec §4.5)."
                    ),
                ),
            ),
            initialization=Initialization(
                strategy="local_initializer",
                notes=(
                    "The causal evaluator: the PH kernel's bracketed solve on the provider's TP "
                    "flash, with the saturation route for a single flowing component "
                    "(T05 spec §4.4)."
                ),
            ),
            validity=Validity(
                components=self.components,
                phases=("liquid", "vapor", "vapor_liquid", "zero_flow"),
                limitations=(
                    "Ideal VLE from the provider's TP flash; no third phase and no stability "
                    "claim beyond the provider's two-phase classification (T05 spec §4.6).",
                    "A single flowing component takes the saturation route: T = T_sat(P) and "
                    "the split by the lever rule, because Hdot_TP jumps at the boiling point "
                    "and no temperature reproduces an enthalpy inside the jump (T05 spec §4.2).",
                    "Every answer of the PH kernel is accepted only if the closure's energy, "
                    "equilibrium and material rows hold at K04's registered tolerances, the "
                    "provider's K and h taken as exact; a near-pure target inside the latent jump "
                    "that the temperature route misses is answered by the saturation-band route. "
                    "Above about 1e8 mol/s, where tau_E is below the double resolution of H, the "
                    "answer is ph_ill_conditioned (T05b spec §5.1-§5.3).",
                    "On the EO path a single flowing component in the latent jump, a near-pure "
                    "outlet and a dormant inlet are solved and certified under the phase contract "
                    "T05b-phase-contract-v2 (T05b spec §11). SolvePolicy's default, "
                    "T03-phase-contract-v1, keeps T05's contract rules verbatim: under it a "
                    "single flowing component in the jump is never VERIFIED and a dormant outlet "
                    "whose label must move is not CONVERGED (T05b spec §6.6, B08-B10, B16).",
                    "A dormant inlet: the causal face labels the outlets with the inlet "
                    "temperature and refuses a nonzero duty as duty_into_dormant_stream. On the "
                    "EO path under T05b-phase-contract-v2 the same specification closes "
                    "SPECIFICATION_CONFLICT with zero_flow_conflict naming the duty row; no other "
                    "attempt signature is searched for (T05b spec §7.8 (iv), §17).",
                    "On the EO path a flash whose solution lies exactly on its dew or bubble "
                    "point with one product zero — for example a zero-duty, zero-pressure-drop "
                    "flash fed a saturated vapour or liquid — is not certified. The lifted "
                    "equilibrium rows are singular there. A solve that ends at that point is "
                    "certified UNVERIFIED with regularity RANK_DEFICIENT. A solve that "
                    "approaches it in the two-phase form can stop at a nearby state, which the "
                    "verifier fails as a detected false success (T05b spec B31 (b), §17).",
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
        vapor = wiring.one("vapor")
        liquid = wiring.one("liquid")
        duty = duty_id(self.unit_id)
        total_vapor, total_liquid = total_flow_id(vapor), total_flow_id(liquid)

        lnk = LnKBlock(self.provider, self.components, self.context, block_id=lnk_block_id(vapor))
        vapor_block, vapor_feeding, vapor_keys = single_phase_enthalpy(
            self.provider, self.components, self.context, vapor, "VAPOR"
        )
        liquid_block, liquid_feeding, liquid_keys = single_phase_enthalpy(
            self.provider, self.components, self.context, liquid, "LIQUID"
        )
        inlet_keys, inlet_blocks, inlet_inputs = stream_enthalpy_terms(
            self.provider, self.components, self.context, inlet, self.inlet_phase
        )

        equations: list[EquationSpec] = []
        for component in self.components:
            equations.append(
                EquationSpec(
                    equation_id=row_id(self.unit_id, "PHF-mole", component),
                    build=balance_row(
                        (flow_id(inlet, component),),
                        (flow_id(vapor, component), flow_id(liquid, component)),
                    ),
                    accumulation="holdup_balance",
                    origin=origin(MODEL_ID, "PHF-mole"),
                )
            )
        for component in self.components:
            equations.append(
                EquationSpec(
                    equation_id=row_id(self.unit_id, "PHF-equilibrium", component),
                    build=equilibrium_row(
                        flow_id(vapor, component),
                        flow_id(liquid, component),
                        total_vapor,
                        total_liquid,
                        f"{lnk.block_id}.lnK_{component}",
                    ),
                    accumulation="algebraic",
                    origin=origin(MODEL_ID, "PHF-equilibrium"),
                )
            )
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "PHF-T"),
                build=balance_row((temperature_id(vapor),), (temperature_id(liquid),)),
                accumulation="algebraic",
                origin=origin(MODEL_ID, "PHF-T"),
            )
        )
        for port, stream in (("vapor", vapor), ("liquid", liquid)):
            equations.append(
                EquationSpec(
                    equation_id=row_id(self.unit_id, "PHF-pressure", port),
                    build=offset_row(
                        pressure_id(stream), pressure_id(inlet), self.pressure_drop_parameter
                    ),
                    accumulation="algebraic",
                    origin=origin(MODEL_ID, "PHF-pressure"),
                )
            )
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "PHF-duty"),
                build=energy_row(inlet_keys, (*vapor_keys, *liquid_keys), source=duty),
                accumulation="holdup_balance",
                origin=origin(MODEL_ID, "PHF-duty"),
            )
        )
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "PHF-Q"),
                build=specification_row(duty, self.duty_parameter),
                accumulation="algebraic",
                origin=origin(MODEL_ID, "PHF-Q"),
            )
        )
        for port, stream, total in (
            ("vapor", vapor, total_vapor),
            ("liquid", liquid, total_liquid),
        ):
            equations.append(
                EquationSpec(
                    equation_id=row_id(self.unit_id, "Ndef", port),
                    build=definition_row(
                        total, tuple(flow_id(stream, name) for name in self.components)
                    ),
                    accumulation="algebraic",
                    origin=origin(MODEL_ID, "lifting"),
                )
            )

        kinds: dict[str, QuantityKind] = {}
        for component in self.components:
            kinds[row_id(self.unit_id, "PHF-mole", component)] = "molar_flow"
            kinds[row_id(self.unit_id, "PHF-equilibrium", component)] = "molar_flow_squared"
        kinds[row_id(self.unit_id, "PHF-T")] = "temperature"
        for port in ("vapor", "liquid"):
            kinds[row_id(self.unit_id, "PHF-pressure", port)] = "pressure"
            kinds[row_id(self.unit_id, "Ndef", port)] = "molar_flow"
        kinds[row_id(self.unit_id, "PHF-duty")] = "heat_rate"
        kinds[row_id(self.unit_id, "PHF-Q")] = "heat_rate"

        return Contribution(
            variable_ids=(duty, total_vapor, total_liquid),
            equations=tuple(equations),
            variable_kinds={
                duty: "heat_rate",
                total_vapor: "molar_flow",
                total_liquid: "molar_flow",
            },
            row_kinds=kinds,
            blocks=(lnk, vapor_block, liquid_block, *inlet_blocks),
            block_inputs={
                lnk.block_id: (temperature_id(vapor), pressure_id(vapor)),
                vapor_block.block_id: vapor_feeding,
                liquid_block.block_id: liquid_feeding,
                **inlet_inputs,
            },
            parameter_ids=(self.duty_parameter, self.pressure_drop_parameter),
            parameters={
                self.duty_parameter: float(self.duty),
                self.pressure_drop_parameter: float(self.pressure_drop),
            },
        )

    # -- evaluator ---------------------------------------------------------------------------

    def evaluate(
        self, inlets: Mapping[str, Sequence[StreamState]], context: EvaluationContext
    ) -> UnitEvaluation:
        return self.evaluate_with_closure(inlets, context)[0]

    def evaluate_with_closure(
        self, inlets: Mapping[str, Sequence[StreamState]], context: EvaluationContext
    ) -> tuple[UnitEvaluation, PHState | None]:
        """`evaluate`, and the PH kernel's answer where the kernel was reached.

        The kernel's route (`saturation` or `bracket`) and split are part of what spec §5.3
        registers, and `UnitEvaluation` has no field for either; the second element carries them.
        It is `None` when the evaluator stopped before the kernel (a dormant inlet, an outlet
        pressure off the domain, an inadmissible inlet).
        """
        connected = tuple(inlets.get("inlet", ()))
        if len(connected) != 1 or set(inlets) - {"inlet"}:
            raise SpecificationError(
                f"{self.unit_id}: a PH flash takes exactly one inlet stream, got {inlets!r}"
            )
        feed = connected[0]
        if len(feed.n) != len(self.components):
            raise SpecificationError(
                f"{self.unit_id}: inlet carries {len(feed.n)} components, expected "
                f"{len(self.components)}"
            )
        outlet_pressure = feed.pressure - float(self.pressure_drop)

        # (1) Spec §4.7: dormant outlets carry the inlet temperature as a label.
        if feed.is_dormant:
            if self.duty != 0.0:
                return (
                    typed_failure(
                        "error",
                        "duty_into_dormant_stream",
                        f"Q_spec = {self.duty} W into a dormant stream; PHF-duty forces Q = 0",
                    ),
                    None,
                )
            dormant = StreamState(
                n=tuple(0.0 for _ in self.components),
                temperature=feed.temperature,
                pressure=outlet_pressure,
            )
            return (
                UnitEvaluation(
                    status="ok",
                    outlets={"vapor": dormant, "liquid": dormant},
                    duty=0.0,
                    phase_signature="ZERO_FLOW",
                    reference_convention=REFERENCE_CONVENTION,
                ),
                None,
            )

        # (2)
        if not P_MIN <= outlet_pressure <= P_MAX:
            return (
                typed_failure(
                    "out_of_domain",
                    "pressure_outside_domain(outlet)",
                    f"P_in - dP = {outlet_pressure} Pa outside [{P_MIN}, {P_MAX}] Pa",
                ),
                None,
            )

        # (3)
        inlet = port_enthalpy(
            self.provider, feed, self.inlet_phase, self.components, context, port="inlet"
        )
        if inlet.failure is not None:
            return inlet.failure, None
        assert inlet.enthalpy_flow is not None

        # (4)
        closure = ph_state(
            self.provider, feed.n, outlet_pressure, inlet.enthalpy_flow + self.duty, context
        )
        if closure.status != "ok":
            return closure_failure(closure), closure
        split = closure.split
        assert split is not None and split.vapor is not None and split.liquid is not None

        # (5)
        return (
            UnitEvaluation(
                status="ok",
                outlets={"vapor": split.vapor, "liquid": split.liquid},
                duty=float(self.duty),
                phase_signature=split.phase_signature,
                iterations=closure.evaluations,
                provider_id=split.provider_id,
                reference_convention=split.reference_convention,
                closure=closure,
            ),
            closure,
        )
