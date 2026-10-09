"""`c1.tp_flash` — the C1 separator: an isothermal, isobaric flash of a light-gas-bearing vapour
into a vapour and pure liquid NH3 (design note §8, §14.2 B11, B12, B14, B16; M01 spec §7 with its
Amendment 3; register R-254, R-256).

**Rows** (B12), the equilibrium family in component order:

| Row | Kind | Equation |
| --- | --- | --- |
| `<U>:C1FL-mole:<c>`, all five | molar_flow | `n_in,c − v_c − l_c` |
| `<U>:C1FL-equilibrium:NH3` | molar_flow_squared | `E = L v_NH3 exp(λ^V) − V l_NH3 exp(λ^L)` |
| `<U>:C1FL-equilibrium:<i>`, i light | molar_flow | `l_i` |
| `<U>:Ndef:vapor`, `<U>:Ndef:liquid` | molar_flow | `V − Σ v_c`, `L − Σ l_c` |
| `<U>:C1FL-T:<port>`, `<U>:C1FL-P:<port>` | temperature, pressure | SYN-001's `FLASH-T`, `-P` |
| `<U>:C1FL-duty` | heat_rate | `Q − (Ḣ_V + Ḣ_L − Ḣ_in)` |

`E` is R-008's pairwise form `v_i L − K_i l_i V` with `K_NH3 = φ^L/φ^V`, multiplied through by `φ^V`
(B11): on TWO_PHASE it is `L V (y φ^V − φ^L)`, whose root set is M01 §7 rule 2's; on VAPOR (`L = l =
0`) and LIQUID (`V = v = 0`) it is exactly `0.0`, because B17's blocks answer finitely at the
dormant side. `λ^V` is ln φ_NH3 of the vapour product, `λ^L` that of the pure liquid product. The
light-gas liquid flows are columns (`models.assemble` allocates every flow of every stream) fixed by
the rows `l_i = 0`, which a TWO_PHASE attempt pins and drops through the split's `VapourOnlyForm`
(B12, B13): M01 §7 rule 2's "not variables".

**The causal evaluate** (B16) refuses a feed with no light gas flowing (`unsupported`,
`pure_nh3_flash_unsupported`: the LIQUID regime and the pure-NH3 saturation route are deferred,
R-230), and otherwise returns the provider's split classified by B14: a VAPOR answer reached
through the dew band reports vapour = feed bitwise and liquid `+0.0`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from openflowsheet.canonical import file_sha256
from openflowsheet.compile.spec import Algebra, EquationSpec, Expr, QuantityKind, RowBuilder
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
from openflowsheet.models.c1 import (
    COMPONENTS,
    ENERGY,
    MOLAR_FLOW,
    MOLE,
    POWER,
    PRESSURE,
    PROVIDER_ID,
    REFERENCE_CONVENTION,
    TEMPERATURE,
)
from openflowsheet.models.c1.blocks import (
    LiquidEnthalpyFlow,
    LiquidLnPhiNH3,
    VapourEnthalpyFlow,
    VapourLnPhiNH3,
    block_feeding,
    hdot_block_id,
    lnphi_block_id,
)
from openflowsheet.models.c1.phase import classify
from openflowsheet.models.c1.units import (
    DESIGN_NOTE,
    P_RANGE,
    PACKAGE,
    T_RANGE,
    c1_components,
    c1_provider,
    enthalpy_flow,
)
from openflowsheet.models.rows import balance_row, definition_row, energy_row, specification_row
from openflowsheet.models.syn001.flash import total_flow_id  # `<S>.N`: one naming site
from openflowsheet.thermo import PropertyProvider, StreamState
from openflowsheet.thermo.pr_c1 import LIGHT, P_MAX, P_MIN, T_MAX, T_MIN

MODEL_ID: Final = "c1.tp_flash"
#: The component whose liquid exists (R-143); every other is vapour-only (`SplitRule.vapour_only`).
CONDENSABLE: Final = "NH3"
VAPOUR_ONLY: Final[tuple[str, ...]] = tuple(c for c in COMPONENTS if c != CONDENSABLE)


PORTS: Final[tuple[Port, ...]] = (
    Port(
        name="inlet",
        kind="material",
        direction="inlet",
        multiplicity=1,
        component_mapping="revision_component_set",
        state_definition="nTP-v1",
        phase_capabilities=("vapor",),
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
        equation_id="C1FL-mole",
        statement="n_in,i - n_vap,i - n_liq,i = 0 for every component i",
        dependencies=("inlet.state.n", "vapor.state.n", "liquid.state.n"),
        conditional_class="unconditional",
        accumulation=Accumulation(
            kind="holdup_balance",
            holdup=Holdup(
                symbol="N_i",
                quantity="component moles held in the flash drum, vapour plus liquid",
                dimension=MOLE,
            ),
        ),
        dimension=MOLAR_FLOW,
        source=DESIGN_NOTE,
    ),
    DeclaredEquation(
        equation_id="C1FL-equilibrium",
        statement=(
            "NH3: L n_vap,NH3 exp(ln phi^V_NH3(T, P, n_vap)) - V n_liq,NH3 exp(ln phi^L_NH3(T, P)) "
            "= 0, R-008's pairwise form, exactly zero on a single-phase branch; every light gas "
            "i: n_liq,i = 0 (the liquid is pure NH3, R-143)"
        ),
        dependencies=("vapor.state", "liquid.state"),
        conditional_class="phase_conditional",
        accumulation=Accumulation(kind="algebraic"),
        source=DESIGN_NOTE,
    ),
    DeclaredEquation(
        equation_id="C1FL-T",
        statement="T_vap - T_spec = 0 and T_liq - T_spec = 0",
        dependencies=("specifications.SPEC-flash-T",),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=TEMPERATURE,
        source=DESIGN_NOTE,
    ),
    DeclaredEquation(
        equation_id="C1FL-P",
        statement="P_vap - P_spec = 0, P_liq - P_spec = 0, P_in - P_spec = 0 with dP = 0 declared",
        dependencies=("specifications.SPEC-flash-P", "parameters.pressure_drop"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=PRESSURE,
        source=DESIGN_NOTE,
    ),
    DeclaredEquation(
        equation_id="C1FL-duty",
        statement="Q - (Hdot_V(vap) + Hdot_L(liq) - Hdot_V(in)) = 0, Q positive into the unit",
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
        source=DESIGN_NOTE,
    ),
)


def pairwise_equilibrium_row(
    vapor: str,
    liquid: str,
    total_vapor: str,
    total_liquid: str,
    vapor_ln_phi_key: str,
    liquid_ln_phi_key: str,
) -> RowBuilder:
    """B11's `E = L · v · exp(λ^V) − V · l · exp(λ^L)`, formed left to right as written."""

    def build(
        variables: Mapping[str, Expr],
        blocks: Mapping[str, Expr],
        parameters: Mapping[str, float],
        algebra: Algebra,
    ) -> Expr:
        return variables[total_liquid] * variables[vapor] * algebra.exp(
            blocks[vapor_ln_phi_key]
        ) - variables[total_vapor] * variables[liquid] * algebra.exp(blocks[liquid_ln_phi_key])

    return build


def zero_row(variable: str) -> RowBuilder:
    """`l_i`: a light gas's liquid flow, which reads exactly its own column (B12)."""

    def build(
        variables: Mapping[str, Expr],
        blocks: Mapping[str, Expr],
        parameters: Mapping[str, float],
        algebra: Algebra,
    ) -> Expr:
        return variables[variable]

    return build


def _artifact_hash() -> str:
    """The module source's SHA-256. Not cached: T07 G20 lists every per-process cache, and this
    one would only save a file read per manifest (build log D37 (f))."""
    return file_sha256(Path(__file__))


@dataclass(frozen=True)
class TPFlash:
    """One C1 flash at a specified temperature and pressure."""

    unit_id: str
    provider: PropertyProvider
    temperature: float
    pressure: float
    context: EvaluationContext
    components: tuple[str, ...] = COMPONENTS

    def __post_init__(self) -> None:
        c1_components(self.unit_id, self.components)
        c1_provider(self.unit_id, self.provider)
        if not T_MIN <= self.temperature <= T_MAX:
            raise SpecificationError(
                f"{self.unit_id}: specified temperature {self.temperature} K is outside the "
                f"provider's domain [{T_MIN}, {T_MAX}] K"
            )
        if not P_MIN <= self.pressure <= P_MAX:
            raise SpecificationError(
                f"{self.unit_id}: specified pressure {self.pressure} Pa is outside the "
                f"provider's domain [{P_MIN}, {P_MAX}] Pa"
            )

    @property
    def model_id(self) -> str:
        return MODEL_ID

    @property
    def temperature_parameter(self) -> str:
        return f"{self.unit_id}.T_spec"

    @property
    def pressure_parameter(self) -> str:
        return f"{self.unit_id}.P_spec"

    def ports(self) -> tuple[Port, ...]:
        return PORTS

    def declared_equations(self) -> tuple[DeclaredEquation, ...]:
        return EQUATIONS

    def manifest(self) -> Mapping[str, Any]:
        return manifest_document(
            model_id=MODEL_ID,
            title="C1 isothermal-isobaric flash",
            description=(
                "Splits a light-gas-bearing C1 vapour into a vapour and pure liquid NH3 at a "
                "specified temperature and pressure."
            ),
            ports=PORTS,
            equations=EQUATIONS,
            derivatives=(
                DerivativeDeclaration(
                    output="residuals",
                    with_respect_to=("free_variables",),
                    method="ad",
                    regime="all",
                    notes=(
                        "The products are the phase split, so every row is written over "
                        "flowsheet variables; the ln phi and enthalpy-flow blocks supply the "
                        "provider's analytic derivatives (M01 §4.6) and B17's convention at an "
                        "exactly dormant product."
                    ),
                ),
            ),
            initialization=Initialization(
                strategy="local_initializer",
                notes=(
                    "The provider's TP flash (M01 §5.4), classified by M01 §7 rule 3 with "
                    "tau_dew: a dew-band answer is the feed as vapour."
                ),
            ),
            validity=Validity(
                components=self.components,
                phases=("vapor", "vapor_liquid", "zero_flow"),
                limitations=(
                    f"On {PROVIDER_ID} under {REFERENCE_CONVENTION} and phase contract "
                    "T05b-phase-contract-v2 with M01 spec §7: H2, N2, Ar and CH4 are vapour-only "
                    "and the liquid is pure NH3 (R-143); no dissolved gases.",
                    "Regimes VAPOR, TWO_PHASE and ZERO_FLOW. A feed with no light gas flowing is "
                    "refused unsupported pure_nh3_flash_unsupported: the LIQUID regime and the "
                    "pure-NH3 saturation route are deferred (R-230).",
                    "The dew band: a TP flash TWO_PHASE with liquid NH3 <= tau_dew n_tot "
                    "(tau_dew = 1e-10) reads VAPOR (M01 §7 rule 3), in the kernel, the screen, "
                    "the causal evaluate and the certificate. Just past the band the TWO_PHASE "
                    "Jacobian approaches the dew point's singularity (design note §11 K18).",
                    "A flash whose solution lies within the near-dew window of its dew point is "
                    "certified UNVERIFIED with a rank limitation, because the equilibrium and "
                    "liquid-total rows are singular at the dew point (design note §14.3 C3, "
                    "R-282). Measured at M01's F4 (0.89 mol/s at 268.15 K, 1e7 Pa; 24 columns): "
                    "rcond_1 = 4.2e-4 delta on both sides, delta the relative NH3 excess or "
                    "deficit against the dew composition (on the TWO_PHASE side rcond_1 = 6.9e-3 "
                    "L/n_tot). On the VAPOR side the certificate is VERIFIED from delta = 2.5e-4, "
                    "where the regularity screen's absolute limit ||J^-1||_1 <= tau_min/(n eps) "
                    "is met; on the TWO_PHASE side from L/n_tot = 3.4e-5 (delta = 5.5e-4), below "
                    "which the derivative witness's central stencil (one step 3e-5 mol/s) cannot "
                    "difference the liquid NH3 flow; tau_ill = 1e-8 alone would bind at L/n_tot "
                    "= 1.4e-6 and the absolute limit at 1.5e-5. The window grows with the "
                    "declaration's size and shrinks with the stream's flow. tau_dew does not "
                    "move.",
                    "The NH3 equilibrium row is R-008's pairwise form L v phi^V - V l phi^L "
                    "(kind molar_flow_squared), exactly zero on a single-phase branch (M01 spec "
                    "§7 Amendment 3); the light-gas liquid flows are columns fixed by zero rows "
                    "and pinned in a TWO_PHASE attempt.",
                    "A dormant feed produces two dormant products, exactly zero duty and phase "
                    "signature ZERO_FLOW (ADR 0001 D3.4).",
                    "C1FL-P imposes the specified pressure on the inlet as well as on both "
                    "products; in a loop whose pressure drops are all zero that row is linearly "
                    "dependent on the chain upstream of it, and K03's structural analysis "
                    "reports the rank.",
                ),
                temperature_k=T_RANGE,
                pressure_pa=P_RANGE,
            ),
            module=__name__,
            artifact_hash=_artifact_hash(),
            execution_class="native_equation",
            thread_safety="not_thread_safe",
            evaluation_cost_class="moderate",
            property_provider=PROVIDER_ID,
            reference_convention=REFERENCE_CONVENTION,
            package=PACKAGE,
        )

    # -- rows --------------------------------------------------------------------------------

    def contribute(self, wiring: Wiring, components: Sequence[str]) -> Contribution:
        if tuple(components) != self.components:
            raise SpecificationError(
                f"{self.unit_id}: wired into components {tuple(components)}, built for "
                f"{self.components}"
            )
        inlet, vapor, liquid = wiring.one("inlet"), wiring.one("vapor"), wiring.one("liquid")
        duty = duty_id(self.unit_id)
        total_vapor, total_liquid = total_flow_id(vapor), total_flow_id(liquid)

        hdot_in = VapourEnthalpyFlow(
            self.provider, self.context, block_id=hdot_block_id(inlet, "VAPOR")
        )
        hdot_vapor = VapourEnthalpyFlow(
            self.provider, self.context, block_id=hdot_block_id(vapor, "VAPOR")
        )
        hdot_liquid = LiquidEnthalpyFlow(
            self.provider, self.context, block_id=hdot_block_id(liquid, "LIQUID")
        )
        phi_vapor = VapourLnPhiNH3(
            self.provider, self.context, block_id=lnphi_block_id(vapor, "VAPOR")
        )
        phi_liquid = LiquidLnPhiNH3(
            self.provider, self.context, block_id=lnphi_block_id(liquid, "LIQUID")
        )
        fed = (
            (hdot_in, inlet),
            (hdot_vapor, vapor),
            (hdot_liquid, liquid),
            (phi_vapor, vapor),
            (phi_liquid, liquid),
        )

        def key(block: Any) -> str:
            return f"{block.block_id}.{block.output_ids[0]}"

        equations: list[EquationSpec] = []
        kinds: dict[str, QuantityKind] = {}
        for component in self.components:
            mole = row_id(self.unit_id, "C1FL-mole", component)
            equations.append(
                EquationSpec(
                    equation_id=mole,
                    build=balance_row(
                        (flow_id(inlet, component),),
                        (flow_id(vapor, component), flow_id(liquid, component)),
                    ),
                    accumulation="holdup_balance",
                    origin=origin(MODEL_ID, "C1FL-mole"),
                )
            )
            kinds[mole] = "molar_flow"
            equilibrium = row_id(self.unit_id, "C1FL-equilibrium", component)
            if component == CONDENSABLE:
                build = pairwise_equilibrium_row(
                    flow_id(vapor, component),
                    flow_id(liquid, component),
                    total_vapor,
                    total_liquid,
                    key(phi_vapor),
                    key(phi_liquid),
                )
                kinds[equilibrium] = "molar_flow_squared"
            else:
                build = zero_row(flow_id(liquid, component))
                kinds[equilibrium] = "molar_flow"
            equations.append(
                EquationSpec(
                    equation_id=equilibrium,
                    build=build,
                    accumulation="algebraic",
                    origin=origin(MODEL_ID, "C1FL-equilibrium"),
                )
            )
        for port, stream in (("vapor", vapor), ("liquid", liquid)):
            row = row_id(self.unit_id, "C1FL-T", port)
            equations.append(
                EquationSpec(
                    equation_id=row,
                    build=specification_row(temperature_id(stream), self.temperature_parameter),
                    accumulation="algebraic",
                    origin=origin(MODEL_ID, "C1FL-T"),
                )
            )
            kinds[row] = "temperature"
        for port, stream in (("vapor", vapor), ("liquid", liquid), ("inlet", inlet)):
            row = row_id(self.unit_id, "C1FL-P", port)
            equations.append(
                EquationSpec(
                    equation_id=row,
                    build=specification_row(pressure_id(stream), self.pressure_parameter),
                    accumulation="algebraic",
                    origin=origin(MODEL_ID, "C1FL-P"),
                )
            )
            kinds[row] = "pressure"
        row = row_id(self.unit_id, "C1FL-duty")
        equations.append(
            EquationSpec(
                equation_id=row,
                build=energy_row((key(hdot_in),), (key(hdot_vapor), key(hdot_liquid)), source=duty),
                accumulation="holdup_balance",
                origin=origin(MODEL_ID, "C1FL-duty"),
            )
        )
        kinds[row] = "heat_rate"
        for port, stream, total in (
            ("vapor", vapor, total_vapor),
            ("liquid", liquid, total_liquid),
        ):
            row = row_id(self.unit_id, "Ndef", port)
            equations.append(
                EquationSpec(
                    equation_id=row,
                    build=definition_row(
                        total, tuple(flow_id(stream, name) for name in self.components)
                    ),
                    accumulation="algebraic",
                    origin=origin(MODEL_ID, "lifting"),
                )
            )
            kinds[row] = "molar_flow"

        return Contribution(
            variable_ids=(duty, total_vapor, total_liquid),
            equations=tuple(equations),
            blocks=tuple(block for block, _ in fed),
            block_inputs={block.block_id: block_feeding(stream) for block, stream in fed},
            parameter_ids=(self.temperature_parameter, self.pressure_parameter),
            parameters={
                self.temperature_parameter: float(self.temperature),
                self.pressure_parameter: float(self.pressure),
            },
            variable_kinds={
                duty: "heat_rate",
                total_vapor: "molar_flow",
                total_liquid: "molar_flow",
            },
            row_kinds=kinds,
        )

    # -- evaluator ---------------------------------------------------------------------------

    def evaluate(
        self, inlets: Mapping[str, Sequence[StreamState]], context: EvaluationContext
    ) -> UnitEvaluation:
        connected = tuple(inlets.get("inlet", ()))
        if len(connected) != 1 or set(inlets) - {"inlet"}:
            raise SpecificationError(
                f"{self.unit_id}: a flash takes exactly one inlet stream, got {inlets!r}"
            )
        feed = connected[0]
        if len(feed.n) != len(self.components):
            raise SpecificationError(
                f"{self.unit_id}: inlet carries {len(feed.n)} components, expected "
                f"{len(self.components)}"
            )
        if feed.pressure != self.pressure:
            # C1FL-P declares P_in = P_spec; ADR 0001 D4.5 makes a mismatch a validation failure.
            return UnitEvaluation(
                status="error",
                message=(
                    f"inlet pressure {feed.pressure} Pa does not equal the specified "
                    f"{self.pressure} Pa; C1FL-P declares them equal and the unit does not "
                    "repair a pressure network"
                ),
                reference_convention=REFERENCE_CONVENTION,
            )
        temperature, pressure = float(self.temperature), float(self.pressure)
        dormant = StreamState(n=(0.0,) * 5, temperature=temperature, pressure=pressure)
        if feed.is_dormant:
            return UnitEvaluation(
                status="ok",
                outlets={"vapor": dormant, "liquid": dormant},
                duty=0.0,
                phase_signature="ZERO_FLOW",
                reference_convention=REFERENCE_CONVENTION,
            )
        if all(feed.n[k] == 0.0 for k in LIGHT):
            return UnitEvaluation(
                status="unsupported",
                message=(
                    "pure_nh3_flash_unsupported: the feed carries no light gas; the LIQUID "
                    "regime and the pure-NH3 saturation route are deferred (R-230)"
                ),
                reference_convention=REFERENCE_CONVENTION,
            )
        regime, _, result = classify(self.provider, context, feed.n, temperature, pressure)
        if regime is None:
            return UnitEvaluation(
                status=result.status,
                message=f"flash: {result.message}",
                reference_convention=REFERENCE_CONVENTION,
            )
        if regime == "VAPOR":
            # B14/B16: the provider's VAPOR, or a TWO_PHASE answer in the dew band — the feed as
            # vapour, bitwise, and the liquid `+0.0`, never the flash's ulp-sized liquid.
            vapour = StreamState(n=feed.n, temperature=temperature, pressure=pressure)
            liquid = dormant
        elif regime == "TWO_PHASE" and result.vapor is not None and result.liquid is not None:
            vapour, liquid = result.vapor, result.liquid
        else:
            return UnitEvaluation(
                status="error",
                message=f"flash: regime {regime} for a feed carrying light gas",
                reference_convention=REFERENCE_CONVENTION,
            )
        h_in, failure = enthalpy_flow(self.provider, context, feed, "VAPOR")
        if failure is not None:
            return failure
        h_vapour, failure = enthalpy_flow(self.provider, context, vapour, "VAPOR")
        if failure is not None:
            return failure
        h_liquid, failure = enthalpy_flow(self.provider, context, liquid, "LIQUID")
        if failure is not None:
            return failure
        return UnitEvaluation(
            status="ok",
            outlets={"vapor": vapour, "liquid": liquid},
            duty=h_vapour + h_liquid - h_in,
            phase_signature=regime,
            iterations=result.iterations,
            provider_id=PROVIDER_ID,
            reference_convention=REFERENCE_CONVENTION,
        )
