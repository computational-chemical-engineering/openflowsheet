"""`c1.adiabatic_mixer` — two or more C1 vapours into one vapour (design note §8, §14.2 B16;
M02 WO-8.2).

**Rows.** Component balances `Σ_k n_in(k),i − n_out,i`, the energy balance `Σ_k Ḣ_V(in k) −
Ḣ_V(out)` over the vapour enthalpy-flow blocks (B17's convention at a dormant stream), and SYN-001's
pressure rows `P_in(k) − P_out`, one per inlet. No duty: adiabatic means `Q ≡ 0`. With every inlet
exactly dormant the outlet's temperature is read by no row (the energy row's `T_out` coefficient is
`−∂Ḣ_V/∂T = 0` there, B17), so the outlet is a dormancy-form outlet (`splits.DORMANCY_RULES`, B13).

**Phase.** The outlet port is `vapor`. The mixer's regime lattice is {VAPOR, ZERO_FLOW}: a flowing
inlet and the outlet must each be VAPOR by M01 §7 rule 3 with τ_dew (`classify`), else the causal
evaluate refuses `vapour_phase_inadmissible` (B16). There is no solve-time screen of this outlet:
a solve that converges with it two-phase fails the certificate's declared-port check (B15 item 5).

**The causal closure** solves `Ḣ_V(n_out, T, P) = Σ_k Ḣ_V(in k)` for T. Peng–Robinson mixes
non-ideally, so — unlike SYN-001's liquid mixer — the inlet temperatures do not bracket the root
exactly, and equal inlet temperatures do not give the outlet that temperature: the bracket
`[min T_in, max T_in]` is widened outward in doubling steps from 1 K, inside the provider's domain,
until it straddles (the vapour enthalpy rises with T), then closed by safeguarded Newton on the
bracket. It is an initializer for the EO solve, whose row is the balance above.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Final

from openflowsheet.canonical import file_sha256, normalize_zero
from openflowsheet.compile.spec import EquationSpec, QuantityKind
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import (
    Accumulation,
    Contribution,
    DeclaredEquation,
    DerivativeDeclaration,
    Initialization,
    Port,
    SpecificationError,
    UnitEvaluation,
    Validity,
    Wiring,
    flow_id,
    manifest_document,
    origin,
    pressure_id,
    row_id,
)
from openflowsheet.models.c1 import (
    COMPONENTS,
    MOLAR_FLOW,
    POWER,
    PRESSURE,
    PROVIDER_ID,
    REFERENCE_CONVENTION,
)
from openflowsheet.models.c1.blocks import VapourEnthalpyFlow, block_feeding, hdot_block_id
from openflowsheet.models.c1.units import (
    DESIGN_NOTE,
    P_RANGE,
    PACKAGE,
    T_RANGE,
    c1_components,
    c1_provider,
    enthalpy_flow,
    vapour_refusal,
)
from openflowsheet.models.rows import balance_row, energy_row
from openflowsheet.thermo import PropertyProvider, PropertyRequest, StreamState
from openflowsheet.thermo.pr_c1 import T_MAX, T_MIN

MODEL_ID: Final = "c1.adiabatic_mixer"

#: The closure's iteration ceiling: bisection halves at most 800 K to one ulp in about 60 steps.
_MAX_ITERATIONS: Final = 200

PORTS: Final[tuple[Port, ...]] = (
    Port(
        name="inlet",
        kind="material",
        direction="inlet",
        multiplicity="many",
        component_mapping="revision_component_set",
        state_definition="nTP-v1",
        phase_capabilities=("vapor",),
    ),
    Port(
        name="outlet",
        kind="material",
        direction="outlet",
        multiplicity=1,
        component_mapping="revision_component_set",
        state_definition="nTP-v1",
        phase_capabilities=("vapor",),
    ),
)

_JUNCTION: Final = (
    "The adiabatic mixer is a junction with no volume; its outlet is the instantaneous sum of its "
    "inlets, so the holdup is identically zero by the model's definition (ADR 0008 D3.5)."
)

EQUATIONS: Final[tuple[DeclaredEquation, ...]] = (
    DeclaredEquation(
        equation_id="C1MIX-mole",
        statement="sum_k n_in(k),i - n_out,i = 0 for every component i",
        dependencies=("inlet.state.n", "outlet.state.n"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="zero_holdup_balance", reason=_JUNCTION),
        dimension=MOLAR_FLOW,
        source=DESIGN_NOTE,
    ),
    DeclaredEquation(
        equation_id="C1MIX-energy",
        statement=(
            "sum_k Hdot_V(in k) - Hdot_V(out) = 0 (adiabatic: Q = 0, W = 0), Hdot_V = Sum(n) h "
            "of the pr-c1-v1 vapour; at an exactly dormant stream 0 with the ideal-gas flow "
            "derivatives (design note §14.2 B17)"
        ),
        dependencies=("inlet.state", "outlet.state"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="zero_holdup_balance", reason=_JUNCTION),
        dimension=POWER,
        source=DESIGN_NOTE,
    ),
    DeclaredEquation(
        equation_id="C1MIX-pressure",
        statement="P_in(k) - P_out = 0 for every inlet k",
        dependencies=("inlet.state.P", "outlet.state.P"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=PRESSURE,
        source=DESIGN_NOTE,
    ),
)


@cache
def _artifact_hash() -> str:
    return file_sha256(Path(__file__))


@dataclass(frozen=True)
class AdiabaticMixer:
    """One C1 adiabatic mixer instance: two or more vapour inlets, one vapour outlet, no duty."""

    unit_id: str
    provider: PropertyProvider
    context: EvaluationContext
    components: tuple[str, ...] = COMPONENTS

    def __post_init__(self) -> None:
        c1_components(self.unit_id, self.components)
        c1_provider(self.unit_id, self.provider)

    @property
    def model_id(self) -> str:
        return MODEL_ID

    def ports(self) -> tuple[Port, ...]:
        return PORTS

    def declared_equations(self) -> tuple[DeclaredEquation, ...]:
        return EQUATIONS

    def manifest(self) -> Mapping[str, Any]:
        return manifest_document(
            model_id=MODEL_ID,
            title="C1 adiabatic vapour mixer",
            description="Mixes two or more C1 vapour streams adiabatically into one vapour.",
            ports=PORTS,
            equations=EQUATIONS,
            derivatives=(
                DerivativeDeclaration(
                    output="residuals",
                    with_respect_to=("free_variables",),
                    method="ad",
                    regime="all",
                    notes=(
                        "Balances are affine; the energy row sums vapour enthalpy-flow blocks "
                        "with the provider's analytic derivatives (M01 §4.6), and B17's "
                        "ideal-gas limit at an exactly dormant stream."
                    ),
                ),
            ),
            initialization=Initialization(
                strategy="local_initializer",
                notes=(
                    "Energy closure for the outlet temperature: the inlet-temperature bracket, "
                    "widened outward until it straddles, closed by safeguarded Newton."
                ),
            ),
            validity=Validity(
                components=self.components,
                phases=("vapor", "zero_flow"),
                limitations=(
                    f"Vapour only, on {PROVIDER_ID} under {REFERENCE_CONVENTION}: every flowing "
                    "inlet and the outlet must be VAPOR by M01 spec §7 rule 3 with tau_dew = "
                    "1e-10 (a TP flash TWO_PHASE with liquid NH3 <= tau_dew n_tot reads VAPOR); "
                    "otherwise the causal evaluate refuses vapour_phase_inadmissible. Two-phase "
                    "mixers are not provided (R-230).",
                    "No solve-time screen of the outlet: a solve converging with it two-phase is "
                    "CONVERGED with a FAILED certificate naming its declared-port check "
                    "(design note §14.2 B15, B16).",
                    "Peng-Robinson mixes non-ideally: equal inlet temperatures do not give that "
                    "outlet temperature exactly.",
                    "At an exactly dormant stream the vapour enthalpy flow is 0 with the "
                    "ideal-gas flow derivatives h_ig,j(T) (B17); with every inlet dormant the "
                    "outlet runs its dormancy form (ADR 0012 D12, A4).",
                    "Light gases never condense and the only liquid is pure NH3 (R-143).",
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

    def _block(self, stream: str) -> VapourEnthalpyFlow:
        return VapourEnthalpyFlow(
            self.provider, self.context, block_id=hdot_block_id(stream, "VAPOR")
        )

    def contribute(self, wiring: Wiring, components: Sequence[str]) -> Contribution:
        if tuple(components) != self.components:
            raise SpecificationError(
                f"{self.unit_id}: wired into components {tuple(components)}, built for "
                f"{self.components}"
            )
        inlets = wiring.many("inlet")
        if len(inlets) < 2:
            raise SpecificationError(
                f"{self.unit_id}: a mixer wired to {len(inlets)} inlet(s) still produces a "
                "plausible number, which is why it is refused here"
            )
        outlet = wiring.one("outlet")
        blocks = [self._block(stream) for stream in (*inlets, outlet)]
        keys = [f"{block.block_id}.{block.output_ids[0]}" for block in blocks]

        equations: list[EquationSpec] = []
        for component in self.components:
            equations.append(
                EquationSpec(
                    equation_id=row_id(self.unit_id, "C1MIX-mole", component),
                    build=balance_row(
                        tuple(flow_id(stream, component) for stream in inlets),
                        (flow_id(outlet, component),),
                    ),
                    accumulation="zero_holdup_balance",
                    origin=origin(MODEL_ID, "C1MIX-mole"),
                )
            )
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "C1MIX-energy"),
                build=energy_row(tuple(keys[:-1]), (keys[-1],)),
                accumulation="zero_holdup_balance",
                origin=origin(MODEL_ID, "C1MIX-energy"),
            )
        )
        for index, stream in enumerate(inlets):
            equations.append(
                EquationSpec(
                    equation_id=row_id(self.unit_id, "C1MIX-pressure", str(index)),
                    build=balance_row((pressure_id(stream),), (pressure_id(outlet),)),
                    accumulation="algebraic",
                    origin=origin(MODEL_ID, "C1MIX-pressure"),
                )
            )
        kinds: dict[str, QuantityKind] = {
            row_id(self.unit_id, "C1MIX-mole", component): "molar_flow"
            for component in self.components
        }
        kinds[row_id(self.unit_id, "C1MIX-energy")] = "heat_rate"
        for index in range(len(inlets)):
            kinds[row_id(self.unit_id, "C1MIX-pressure", str(index))] = "pressure"
        return Contribution(
            equations=tuple(equations),
            blocks=tuple(blocks),
            block_inputs={
                block.block_id: block_feeding(stream)
                for block, stream in zip(blocks, (*inlets, outlet), strict=True)
            },
            row_kinds=kinds,
        )

    # -- evaluator ---------------------------------------------------------------------------

    def evaluate(
        self, inlets: Mapping[str, Sequence[StreamState]], context: EvaluationContext
    ) -> UnitEvaluation:
        connected = tuple(inlets.get("inlet", ()))
        if len(connected) < 2 or set(inlets) - {"inlet"}:
            raise SpecificationError(
                f"{self.unit_id}: a mixer takes two or more inlet streams, got {inlets!r}"
            )
        for stream in connected:
            if len(stream.n) != len(self.components):
                raise SpecificationError(
                    f"{self.unit_id}: an inlet carries {len(stream.n)} components, expected "
                    f"{len(self.components)}"
                )
        pressures = {stream.pressure for stream in connected}
        if len(pressures) != 1:
            return UnitEvaluation(
                status="error",
                message=(
                    f"inlet pressures {sorted(pressures)} are not equal. C1MIX-pressure declares "
                    "them equal to the outlet pressure and ADR 0001 D4.5 makes a mismatch a "
                    "validation failure, not something the unit repairs"
                ),
                reference_convention=REFERENCE_CONVENTION,
            )
        pressure = connected[0].pressure
        combined = tuple(
            normalize_zero(sum(stream.n[index] for stream in connected))
            for index in range(len(self.components))
        )
        flowing = [
            (index, stream) for index, stream in enumerate(connected) if not stream.is_dormant
        ]
        if not flowing:
            # ADR 0001 D3.1/D3.4: every inlet dormant, so the outlet is dormant; its temperature
            # is a retained label (the first inlet's), not a computed value.
            return UnitEvaluation(
                status="ok",
                outlets={
                    "outlet": StreamState(
                        n=combined, temperature=connected[0].temperature, pressure=pressure
                    )
                },
                duty=None,
                phase_signature="ZERO_FLOW",
                reference_convention=REFERENCE_CONVENTION,
                message="every inlet is dormant; the outlet temperature is a retained label",
            )

        target = 0.0
        for index, stream in flowing:
            refused = vapour_refusal(self.provider, context, f"inlet {index}", stream)
            if refused is not None:
                return refused
            contribution, failure = enthalpy_flow(self.provider, context, stream, "VAPOR")
            if failure is not None:
                return failure
            target += contribution

        low = min(stream.temperature for _, stream in flowing)
        high = max(stream.temperature for _, stream in flowing)
        temperature, iterations, message = self._close_energy(
            combined, pressure, low, high, target, context
        )
        if temperature is None:
            return UnitEvaluation(
                status="not_converged",
                iterations=iterations,
                message=message,
                reference_convention=REFERENCE_CONVENTION,
            )
        outlet = StreamState(n=combined, temperature=temperature, pressure=pressure)
        refused = vapour_refusal(self.provider, context, "outlet", outlet)
        if refused is not None:
            return refused
        return UnitEvaluation(
            status="ok",
            outlets={"outlet": outlet},
            duty=None,
            phase_signature="VAPOR",
            iterations=iterations,
            provider_id=PROVIDER_ID,
            reference_convention=REFERENCE_CONVENTION,
        )

    def _close_energy(
        self,
        flows: tuple[float, ...],
        pressure: float,
        low: float,
        high: float,
        target: float,
        context: EvaluationContext,
    ) -> tuple[float | None, int, str]:
        """Solve `Ḣ_V(flows, T, pressure) = target` for T. Returns `(T, iterations, message)`,
        `T` `None` when no root was bracketed or the provider refused; never a midpoint as if it
        were a root."""
        total = sum(flows)

        def residual(temperature: float) -> tuple[float, float] | None:
            result = self.provider.evaluate_phase(
                PropertyRequest(
                    state=StreamState(n=flows, temperature=temperature, pressure=pressure),
                    phase="VAPOR",
                    properties=("h",),
                    derivatives=("T",),
                ),
                context,
            )
            if result.status != "ok":
                return None
            return (
                total * result.values["h"] - target,
                total * result.derivatives["h"]["T"],
            )

        # Widen the bracket outward until it straddles: Ḣ_V rises with T, and the excess enthalpy
        # of mixing moves the root off the inlet-temperature interval by a small amount.
        f_low, f_high = residual(low), residual(high)
        step = 1.0
        while f_low is not None and f_low[0] > 0.0 and low > T_MIN:
            low, step = max(low - step, T_MIN), 2.0 * step
            f_low = residual(low)
        step = 1.0
        while f_high is not None and f_high[0] < 0.0 and high < T_MAX:
            high, step = min(high + step, T_MAX), 2.0 * step
            f_high = residual(high)
        if f_low is None or f_high is None:
            return None, 0, "the energy closure: the provider refused a bracket endpoint"
        if f_low[0] > 0.0 or f_high[0] < 0.0:
            return (
                None,
                0,
                f"the energy closure has no root in the provider's domain: f({low}) = "
                f"{f_low[0]}, f({high}) = {f_high[0]}",
            )
        if f_low[0] == 0.0:
            return low, 0, ""
        if f_high[0] == 0.0:
            return high, 0, ""

        guess = 0.5 * (low + high)
        for iteration in range(1, _MAX_ITERATIONS + 1):
            evaluated = residual(guess)
            if evaluated is None:
                return None, iteration, "the energy closure: the provider refused an iterate"
            value, slope = evaluated
            if value == 0.0:
                return guess, iteration, ""
            if value < 0.0:
                low = guess
            else:
                high = guess
            proposed = guess - value / slope if slope > 0.0 else guess
            if not low < proposed < high:
                proposed = 0.5 * (low + high)
            if proposed == guess or high - low <= 2.0 * math.ulp(high):
                return guess, iteration, ""
            guess = proposed
        return (
            None,
            _MAX_ITERATIONS,
            f"the energy closure did not converge in {_MAX_ITERATIONS} iterations on "
            f"[{low}, {high}]",
        )
