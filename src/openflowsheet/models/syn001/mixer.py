"""`syn001.adiabatic_mixer` — the one v0.0 unit whose closure is an inner solve.

Component and pressure balance are trivial. The energy balance is not: the outlet temperature is
whatever makes `sum_k Hdot_in(k) = Hdot_out(T_out)`, and inverting an enthalpy for a temperature
is a PH problem. Plan §3.2 restricts v0.0 to "a bracketed scalar thermal solve restricted to the
subcooled-liquid domain with a typed failure outside it; general PH support is T05".

**The bracket rests on two properties of the package, and both are stated.** With every inlet
liquid and the outlet composition the sum of the inlets,

    Hdot_out(T) - sum_k Hdot_in(k) = sum_k sum_i n_k,i [h_i^L(T, P) - h_i^L(T_k, P)],

which is non-positive at `T = min_k T_k` and non-negative at `T = max_k T_k`, so
`[min T_in, max T_in]` brackets the root — which is what the manifest means by "the outlet
temperature bracket is built from the inlet temperatures".

The step that telescopes the double sum needs `Hdot = sum_i n_i h_i^L`, that is **no excess
enthalpy of mixing**; with an `h^E(x, T, P)` term the outlet's enthalpy is not the sum of the
inlets' per-component contributions and the cancellation fails. The sign then needs `h_i^L`
**increasing in T**. SYN-001 has both — derivation §2 shows the mixture enthalpy is
`sum_i n_i h_i` with no excess term, and `dh^L/dT = c_p > 0` — and a provider with either
property absent would need a different bracket. The earlier version of this docstring claimed
only monotonicity; the Fable review of K02 pointed out that ideal mixing is load-bearing too.

If the bracket does not straddle, the closure reports `not_converged` with both endpoint values
rather than widening into territory the argument does not cover.

When every inlet is at the same temperature the bracket is a point and the answer is that
temperature *exactly* — the SYN-001 r = 0 case, where T_mix is 300 K and not 300 K plus a
solver's residue.

**Admissibility is checked on the enthalpy, not on the phase label.** The registered SYN-001
recycle is the flash's own saturated liquid, so `sum_i z_i K_i` is 1 to the last bit — in double
precision it comes out `1.0000000000000002` and the provider correctly classifies the stream
`TWO_PHASE` with a vapour fraction of 1.3e-17, while Fable's 20-digit reference registers
`recycle_phase_signature: LIQUID`. A check on the label therefore rejects the *nominal* variant,
and loosening the label check would be inventing an epsilon for a phase boundary.

The check used is `tp_state.single_phase_admissible`, shared with the heater: the enthalpy gap
converted to the temperature error it would cause, against ADR 0001 D6's registered temperature
tolerance. The first version of this module bounded the gap in **watts** against the registered
energy tolerance, which is an extensive bound on an intensive question: it admitted a 45%-vapour
stream at 1e-8 mol/s and reported an outlet 64 K too cold with status `ok`. Found by the Fable
review of K02 and measured before it was fixed.

The *inlet* enthalpies used are then the liquid ones, which is what `MIX-energy`'s blocks compute
and what the reference `H_recycle_W` is, so the row and the evaluator describe the same
function.

**Two typed failures, and neither is a fallback.** An inlet or an outlet that is not admissible
in that sense is `unsupported` naming T05 — the capability is absent, not approximated
(blueprint §6.3's final phase admissibility check). Inlets at different pressures are an `error`:
ADR 0001 D4.5 makes a pressure mismatch a validation failure and forbids the unit from repairing
it.

**No duty port.** Adiabatic means `Q` is identically zero and is not an unknown, so `MIX-energy`
has no source term at all. A mixer that carried a duty variable would be a different model.
"""

from __future__ import annotations

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
from openflowsheet.models.rows import balance_row, energy_row
from openflowsheet.models.syn001 import (
    COMPONENTS,
    DERIVATION,
    MOLAR_FLOW,
    P_MAX,
    P_MIN,
    POWER,
    PRESSURE,
    PROVIDER_ID,
    REFERENCE_CONVENTION,
    T_MAX,
    T_MIN,
    TEMPERATURE_TOLERANCE,
)
from openflowsheet.models.syn001.tp_state import (
    single_phase_admissible,
    single_phase_enthalpy,
)
from openflowsheet.thermo import PropertyProvider, PropertyRequest, StreamState

MODEL_ID: Final = "syn001.adiabatic_mixer"

#: The bracketed solve's iteration ceiling. Bisection halves an interval of at most 160 K down to
#: one ulp in about 60 steps, so reaching this limit means the function is not what the bracket
#: argument assumed, and the unit says `not_converged` rather than returning the midpoint.
_MAX_ITERATIONS: Final = 200

PORTS: Final[tuple[Port, ...]] = (
    Port(
        name="inlet",
        kind="material",
        direction="inlet",
        multiplicity="many",
        component_mapping="revision_component_set",
        state_definition="nTP-v1",
        phase_capabilities=("liquid",),
    ),
    Port(
        name="outlet",
        kind="material",
        direction="outlet",
        multiplicity=1,
        component_mapping="revision_component_set",
        state_definition="nTP-v1",
        phase_capabilities=("liquid",),
    ),
)

EQUATIONS: Final[tuple[DeclaredEquation, ...]] = (
    DeclaredEquation(
        equation_id="MIX-mole",
        statement="sum_k n_in(k),i - n_out,i = 0 for every component i",
        dependencies=("inlet.state.n", "outlet.state.n"),
        conditional_class="unconditional",
        accumulation=Accumulation(
            kind="zero_holdup_balance",
            reason=(
                "The adiabatic mixer is a junction with no volume; its outlet is the "
                "instantaneous sum of its inlets, so the component holdup is identically zero by "
                "the model's definition. A mixing vessel with holdup is a different model with "
                "its own manifest (ADR 0008 D3.5)."
            ),
        ),
        dimension=MOLAR_FLOW,
        source=DERIVATION,
    ),
    DeclaredEquation(
        equation_id="MIX-energy",
        statement="sum_k Hdot_in(k) - Hdot_out = 0 (adiabatic: Q = 0, W = 0)",
        dependencies=("inlet.state", "outlet.state"),
        conditional_class="unconditional",
        accumulation=Accumulation(
            kind="zero_holdup_balance",
            reason=(
                "Junction with no volume and no thermal inertia by the model's definition; the "
                "energy holdup is identically zero. A mixing vessel is a different model "
                "(ADR 0008 D3.5)."
            ),
        ),
        dimension=POWER,
        source=DERIVATION,
    ),
    DeclaredEquation(
        equation_id="MIX-pressure",
        statement="P_in(k) - P_out = 0 for every inlet k",
        dependencies=("inlet.state.P", "outlet.state.P"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=PRESSURE,
        source=DERIVATION,
    ),
    DeclaredEquation(
        equation_id="MIX-dormant-inlet",
        statement=(
            "an inlet with total flow exactly zero contributes exactly zero to both sums and its "
            "composition is never evaluated"
        ),
        dependencies=("inlet.state.n",),
        conditional_class="phase_conditional",
        accumulation=Accumulation(kind="algebraic"),
        source=DERIVATION,
    ),
)

#: `MIX-dormant-inlet` states a property of how the two balance rows are written, not a residual
#: of its own: a dormant inlet's component terms are exactly zero because the balance is linear,
#: and its enthalpy term is exactly zero because the enthalpy block returns zeros without
#: consulting the provider (ADR 0001 D3.1). It therefore authors no row, and
#: `tests/test_k02_mixer.py` checks the behaviour instead of the row.
BEHAVIOURAL_EQUATIONS: Final[frozenset[str]] = frozenset({"MIX-dormant-inlet"})

_SENSITIVITY_NOTE: Final = (
    "K02 implements the model and K01 supplies the residual derivative route, but the outlet "
    "temperature comes from an inner bracketed solve, so its sensitivity would need the "
    "implicit-function route of blueprint §5.1. K02 exposes no such interface, so this stays "
    "`unavailable` and is reported as absent rather than as zeros (blueprint §5.2)."
)


@cache
def _artifact_hash() -> str:
    return file_sha256(Path(__file__))


@dataclass(frozen=True)
class AdiabaticMixer:
    """One adiabatic mixer instance. Two or more inlets, one outlet, no duty."""

    unit_id: str
    provider: PropertyProvider
    context: EvaluationContext
    components: tuple[str, ...] = COMPONENTS

    @property
    def model_id(self) -> str:
        return MODEL_ID

    # -- declaration -------------------------------------------------------------------------

    def ports(self) -> tuple[Port, ...]:
        return PORTS

    def declared_equations(self) -> tuple[DeclaredEquation, ...]:
        return EQUATIONS

    def manifest(self) -> Mapping[str, Any]:
        return manifest_document(
            model_id=MODEL_ID,
            title="SYN-001 adiabatic mixer",
            description="Combines the fresh feed and the liquid recycle at constant pressure.",
            ports=PORTS,
            equations=EQUATIONS,
            derivatives=(
                DerivativeDeclaration(
                    output="outlet.state.n",
                    with_respect_to=("inlet.state.n",),
                    method="unavailable",
                    regime="all",
                    notes=_SENSITIVITY_NOTE,
                ),
                DerivativeDeclaration(
                    output="outlet.state.T",
                    with_respect_to=("inlet.state.n", "inlet.state.T"),
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
                        "The rows carry the energy balance as a residual in T_out, so the "
                        "equation-oriented route needs no inner solve and CasADi differentiates "
                        "it exactly through the K01 adapter. The inner bracketed solve is the "
                        "*causal* evaluator, used for sequential traversal and initialization."
                    ),
                ),
            ),
            initialization=Initialization(
                strategy="upstream_propagation",
                notes="The outlet temperature bracket is built from the inlet temperatures.",
            ),
            validity=Validity(
                components=self.components,
                phases=("liquid", "zero_flow"),
                limitations=(
                    "v0.0 restricts the enthalpy closure to the subcooled-liquid domain with a "
                    "typed failure outside it; general PH support is T05 (plan §3.2, §4.2 K02).",
                    "No registered SYN-001 r-variant leaves that domain, so K02 needs a separate "
                    "case (for example a fresh feed above its bubble point) to exercise the "
                    "typed failure (derivation §7 finding 5).",
                    "All inlet pressures must equal the outlet pressure. A mismatch is a "
                    "validation failure; the unit never silently repairs an invalid pressure "
                    "network.",
                    "Adiabatic by definition: there is no duty port and no duty variable, so "
                    "MIX-energy has no source term. A mixer with a duty is a different model.",
                    "MIX-dormant-inlet authors no residual row. It states a property of how the "
                    "two balance rows are written, and is tested as behaviour.",
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
        )

    # -- rows --------------------------------------------------------------------------------

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

        blocks = []
        block_inputs: dict[str, tuple[str, ...]] = {}
        inflow_keys: list[str] = []
        for stream in inlets:
            block, feeding, keys = single_phase_enthalpy(
                self.provider, self.components, self.context, stream, "LIQUID"
            )
            blocks.append(block)
            block_inputs[block.block_id] = feeding
            inflow_keys.extend(keys)
        outlet_block, outlet_feeding, outlet_keys = single_phase_enthalpy(
            self.provider, self.components, self.context, outlet, "LIQUID"
        )
        blocks.append(outlet_block)
        block_inputs[outlet_block.block_id] = outlet_feeding

        equations: list[EquationSpec] = []
        for component in self.components:
            equations.append(
                EquationSpec(
                    equation_id=row_id(self.unit_id, "MIX-mole", component),
                    build=balance_row(
                        tuple(flow_id(stream, component) for stream in inlets),
                        (flow_id(outlet, component),),
                    ),
                    accumulation="zero_holdup_balance",
                    origin=origin(MODEL_ID, "MIX-mole"),
                )
            )
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "MIX-energy"),
                build=energy_row(tuple(inflow_keys), tuple(outlet_keys)),
                accumulation="zero_holdup_balance",
                origin=origin(MODEL_ID, "MIX-energy"),
            )
        )
        for index, stream in enumerate(inlets):
            equations.append(
                EquationSpec(
                    equation_id=row_id(self.unit_id, "MIX-pressure", str(index)),
                    build=balance_row((pressure_id(stream),), (pressure_id(outlet),)),
                    accumulation="algebraic",
                    origin=origin(MODEL_ID, "MIX-pressure"),
                )
            )

        kinds: dict[str, QuantityKind] = {
            row_id(self.unit_id, "MIX-mole", component): "molar_flow"
            for component in self.components
        }
        kinds[row_id(self.unit_id, "MIX-energy")] = "heat_rate"
        for index in range(len(inlets)):
            kinds[row_id(self.unit_id, "MIX-pressure", str(index))] = "pressure"

        return Contribution(
            equations=tuple(equations),
            blocks=tuple(blocks),
            block_inputs=block_inputs,
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
                    f"inlet pressures {sorted(pressures)} are not equal. MIX-pressure declares "
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
        flowing = [stream for stream in connected if not stream.is_dormant]
        if not flowing:
            # ADR 0001 D3.1/D3.4: every inlet dormant, so the outlet is dormant. Its temperature
            # is a retained label, not a computed value; the first inlet's is as good as any and
            # the closure was never solved.
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
        for index, stream in enumerate(flowing):
            admissible, liquid, equivalent, failure = self._liquid_enthalpy(stream, context)
            if failure is not None:
                return failure
            if not admissible:
                return UnitEvaluation(
                    status="unsupported",
                    message=(
                        f"inlet {index} is not admissible as a liquid: writing its enthalpy as "
                        f"liquid would misplace the outlet temperature by {equivalent:.3g} K, "
                        f"past the registered {TEMPERATURE_TOLERANCE:g} K, so it carries a "
                        "vapour phase the v0.0 closure cannot account for. The closure is "
                        "restricted to the subcooled-liquid domain; general PH support is T05 "
                        "(plan §3.2)"
                    ),
                    reference_convention=REFERENCE_CONVENTION,
                )
            target += liquid

        low = min(stream.temperature for stream in flowing)
        high = max(stream.temperature for stream in flowing)
        outlet_temperature, iterations, converged, message = self._close_energy(
            combined, pressure, low, high, target, context
        )
        if not converged:
            return UnitEvaluation(
                status="not_converged",
                iterations=iterations,
                message=message,
                reference_convention=REFERENCE_CONVENTION,
            )

        outlet = StreamState(n=combined, temperature=outlet_temperature, pressure=pressure)
        # Blueprint §6.3: the fixed phase set is allowed for a declared domain *with* a final
        # admissibility check. This is that check. It fails rather than reporting a liquid
        # enthalpy for a state whose real enthalpy is materially different.
        admissible, _, equivalent, failure = self._liquid_enthalpy(outlet, context)
        if failure is not None:
            return failure
        if not admissible:
            return UnitEvaluation(
                status="unsupported",
                message=(
                    f"the closure put the outlet at {outlet_temperature} K, where writing its "
                    f"enthalpy as liquid would be wrong by {equivalent:.3g} K, past the "
                    f"registered {TEMPERATURE_TOLERANCE:g} K: the outlet is not subcooled "
                    "liquid there. The v0.0 closure is restricted to the subcooled-liquid "
                    "domain; general PH support is T05 (plan §3.2)"
                ),
                reference_convention=REFERENCE_CONVENTION,
            )

        return UnitEvaluation(
            status="ok",
            outlets={"outlet": outlet},
            duty=None,
            phase_signature="LIQUID",
            iterations=iterations,
            provider_id=PROVIDER_ID,
            reference_convention=REFERENCE_CONVENTION,
        )

    def _liquid_enthalpy(
        self, stream: StreamState, context: EvaluationContext
    ) -> tuple[bool, float, float, UnitEvaluation | None]:
        """`(admissible, liquid enthalpy flow, equivalent temperature error, failure)`.

        Delegates to the shared kernel, so the heater and the mixer answer "may this stream be
        written as a single phase" the same way. `failure` is non-`None` only when the provider
        itself refused, which is passed through rather than reinterpreted.
        """
        admissible, liquid, equivalent, status, message = single_phase_admissible(
            self.provider, stream, "LIQUID", self.components, context
        )
        if status != "ok":
            return (
                False,
                0.0,
                0.0,
                UnitEvaluation(
                    status=status,
                    message=f"liquid enthalpy: {message}",
                    reference_convention=REFERENCE_CONVENTION,
                ),
            )
        return admissible, liquid, equivalent, None

    def _close_energy(
        self,
        flows: tuple[float, ...],
        pressure: float,
        low: float,
        high: float,
        target: float,
        context: EvaluationContext,
    ) -> tuple[float, int, bool, str]:
        """Solve `Hdot_out(T) = target` on `[low, high]`. Bisection, Newton where it stays inside.

        Returns `(temperature, iterations, converged, message)`. Never returns a midpoint as if it
        were a root.
        """
        if low == high:
            # Every flowing inlet at one temperature: the outlet is at that temperature exactly,
            # by the same algebra that builds the bracket. SYN-001 at r = 0 lands here.
            return low, 0, True, ""

        def residual(temperature: float) -> tuple[float, float, bool]:
            state = StreamState(n=flows, temperature=temperature, pressure=pressure)
            result = self.provider.evaluate_phase(
                PropertyRequest(state=state, phase="LIQUID", properties=("h",), derivatives=("T",)),
                context,
            )
            if result.status != "ok":
                return 0.0, 0.0, False
            value = -target
            slope = 0.0
            for component, flow in zip(self.components, flows, strict=True):
                value += flow * result.values[f"h_{component}"]
                slope += flow * result.derivatives[f"h_{component}"]["T"]
            return value, slope, True

        f_low, _, ok_low = residual(low)
        f_high, _, ok_high = residual(high)
        if not (ok_low and ok_high):
            return 0.0, 0, False, "the provider refused a bracket endpoint"
        if f_low > 0.0 or f_high < 0.0:
            return (
                0.0,
                0,
                False,
                f"the inlet temperatures do not bracket the closure: f({low}) = {f_low}, "
                f"f({high}) = {f_high}. The bracket is only valid when every inlet is liquid and "
                "the liquid enthalpy increases with temperature",
            )

        guess = 0.5 * (low + high)
        for iteration in range(1, _MAX_ITERATIONS + 1):
            value, slope, ok = residual(guess)
            if not ok:
                return 0.0, iteration, False, "the provider refused an iterate"
            if value == 0.0:
                return guess, iteration, True, ""
            if value < 0.0:
                low, f_low = guess, value
            else:
                high, f_high = guess, value
            if high - low <= 0.0:
                return guess, iteration, True, ""

            proposed = guess - value / slope if slope > 0.0 else guess
            if not low < proposed < high:
                proposed = 0.5 * (low + high)
            if proposed == guess:
                return guess, iteration, True, ""
            guess = proposed

        return (
            0.0,
            _MAX_ITERATIONS,
            False,
            f"the energy closure did not converge in {_MAX_ITERATIONS} iterations on "
            f"[{low}, {high}]",
        )
