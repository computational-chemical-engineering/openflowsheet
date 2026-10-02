"""The SYN-001 property provider: a synthetic, internally consistent ideal package.

**SYN-001 is a fixture, not a thermodynamic model of anything.** Its constants are invented, it is
not fitted to data, and no number it produces is evidence about a real substance. It exists so the
runtime has a provider with an *independent closed-form reference* to be judged against, and its
`PropertyCapabilities` says so where a caller will see it.

**This implementation is deliberately separate from `benchmarks/syn001/oracle.py`.** Plan §3.2:
"Implement the oracle separately from the production flash/recycle solver." The oracle is the
expectation; if the production provider imported it, the comparison would be a tautology. Both are
transcriptions of the same derivation (`docs/derivations/SYN-001.md`), which is the shared root —
that is validation of the derivation, not of this code, and `tests/test_k02_syn001_provider.py`
says so.

**The reference convention is `SYN-001-ref-v1`** (ADR 0001 D5.1): pure liquid at `T_r = 300 K`,
`P_r = 100 000 Pa` has `h_i^L = 0`; the vapour reference offset is `L_i`. Enthalpy flows are
comparable only between streams sharing provider implementation, data and reference convention
(D5.2), which is why all three are declared.

**Zero flow is answered, not special-cased away.** A dormant feed (`n_tot == 0` exactly, ADR 0001
D3.1) flashes to two dormant outlets with exactly zero duty and `ZERO_FLOW`, which D3.4 calls a
valid result and not a failure. Nothing here divides by a total flow without first establishing it
is positive (D3.2).
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from openflowsheet.compiled import EvaluationContext
from openflowsheet.thermo import (
    FlashRequest,
    FlashResult,
    Phase,
    PropertyCapabilities,
    PropertyRequest,
    PropertyResult,
    StreamState,
)

#: Gas constant, CODATA exact. The only constant here that is not invented.
R: Final = 8.31446261815324

T_REF: Final = 300.0
P_REF: Final = 100_000.0
C_P: Final = 100.0
COMPONENTS: Final[tuple[str, ...]] = ("A", "B", "C")
T_BOIL: Final[tuple[float, ...]] = (320.0, 360.0, 400.0)
L_VAP: Final[tuple[float, ...]] = (25_000.0, 30_000.0, 35_000.0)
V_MOLAR: Final[tuple[float, ...]] = (1e-4, 1e-4, 1e-4)

T_MIN: Final = 280.0
T_MAX: Final = 440.0
P_MIN: Final = 50_000.0
P_MAX: Final = 200_000.0

REFERENCE_CONVENTION: Final = "SYN-001-ref-v1"
STATE_DEFINITION: Final = "nTP-v1"
PROVIDER_ID: Final = "syn001"

#: The Rachford-Rice solve is bracketed and its limit is declared rather than left to a `while`.
#: Bisection on a bracket of width 1 reaches 1e-16 in 53 halvings; 200 is room for the Newton steps
#: to be rejected every time and still converge, and a bound that is never reached in practice is
#: still a bound a reader can check.
_MAX_ITERATIONS: Final = 200
#: Absolute tolerance on the Rachford-Rice residual, which is dimensionless and O(1).
_TOLERANCE: Final = 1e-14


class Syn001Provider:
    """A `PropertyProvider` for the SYN-001 synthetic package.

    Stateless and therefore thread-safe: every method is a pure function of its arguments and the
    module constants. That is declared in `describe()` rather than assumed by a caller.
    """

    def describe(self) -> PropertyCapabilities:
        return PropertyCapabilities(
            provider_id=PROVIDER_ID,
            implementation_sha256=_implementation_sha256(),
            data_sha256=_data_sha256(),
            reference_convention=REFERENCE_CONVENTION,
            state_definition=STATE_DEFINITION,
            components=COMPONENTS,
            phases=("LIQUID", "VAPOR"),
            properties=("h", "lnK"),
            flashes=("TP",),
            # First order in T and P, exactly, from closed forms. Second order exists in closed
            # form too but is not offered, because nothing in v0.0 consumes it and declaring a
            # capability no test exercises is the kind of claim this project does not make.
            derivative_order={"T": 1, "P": 1},
            domain={"T": (T_MIN, T_MAX), "P": (P_MIN, P_MAX)},
            uncertainty=(
                "None. SYN-001 is a synthetic fixture with invented constants, not a correlation "
                "fitted to data, so it has no measurement uncertainty and no applicability range "
                "beyond the declared domain."
            ),
            data_provenance=(
                "docs/derivations/SYN-001.md, transcribed independently of "
                "benchmarks/syn001/oracle.py. Invented constants; no experimental source."
            ),
            thread_safety="thread_safe",
            numerical_limitations=(
                "TP flash only; no PH flash in v0.0 (plan §3.2).",
                "Ideal mixing with temperature- and pressure-dependent K-values; no activity or "
                "fugacity model, no critical-region handling, no liquid-liquid split.",
                "The Rachford-Rice solve is bracketed bisection with Newton acceleration and a "
                f"declared limit of {_MAX_ITERATIONS} iterations; it reports `not_converged` "
                "rather than returning an unconverged split.",
            ),
        )

    # -- properties ----------------------------------------------------------------------------

    def evaluate_phase(
        self, request: PropertyRequest, context: EvaluationContext
    ) -> PropertyResult:
        del context
        state = request.state
        outside = _domain_violation(state.temperature, state.pressure)
        if outside is not None:
            return self._failed(request, "out_of_domain", outside)

        unknown = [name for name in request.properties if name not in ("h", "lnK")]
        if unknown:
            return self._failed(request, "unsupported", f"unknown properties {unknown}")
        undifferentiable = [name for name in request.derivatives if name not in ("T", "P")]
        if undifferentiable:
            return self._failed(
                request, "unsupported", f"no declared derivative with respect to {undifferentiable}"
            )

        values: dict[str, float] = {}
        derivatives: dict[str, dict[str, float]] = {}
        for prop in request.properties:
            for index, component in enumerate(COMPONENTS):
                key = f"{prop}_{component}"
                if prop == "h":
                    values[key] = (
                        h_liquid(state.temperature, state.pressure, index)
                        if request.phase == "LIQUID"
                        else h_vapor(state.temperature, index)
                    )
                    entry = {"T": C_P}
                    if request.phase == "LIQUID":
                        entry["P"] = V_MOLAR[index]
                    else:
                        # The vapour reference offset is a constant, so h^V does not depend on P.
                        # Declaring 0.0 is a statement that the derivative is zero, which is true
                        # here and is not the same as omitting it.
                        entry["P"] = 0.0
                else:
                    values[key] = ln_k(state.temperature, state.pressure, index)
                    entry = {
                        "T": d_ln_k_d_temperature(state.temperature, state.pressure, index),
                        "P": d_ln_k_d_pressure(state.temperature, state.pressure, index),
                    }
                if request.derivatives:
                    derivatives[key] = {name: entry[name] for name in request.derivatives}

        return PropertyResult(
            status="ok",
            phase_signature="ZERO_FLOW" if state.is_dormant else request.phase,
            values=values,
            derivatives=derivatives,
            provider_id=PROVIDER_ID,
            reference_convention=REFERENCE_CONVENTION,
        )

    def _failed(self, request: PropertyRequest, status: str, message: str) -> PropertyResult:
        return PropertyResult(
            status=status,  # type: ignore[arg-type]
            phase_signature=None,
            values={},
            provider_id=PROVIDER_ID,
            reference_convention=REFERENCE_CONVENTION,
            message=message,
        )

    # -- flash ---------------------------------------------------------------------------------

    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult:
        del context
        if request.specification != "TP":
            return _flash_failure(
                "unsupported", f"flash specification {request.specification!r}; v0.0 offers TP only"
            )
        state = request.state
        temperature, pressure = state.temperature, state.pressure

        if state.is_dormant:
            # ADR 0001 D3.4, verbatim consequence: two dormant outlets, exactly zero duty,
            # ZERO_FLOW. A valid result, not a failure — and the composition it would have had is
            # undefined, so no K-value is reported.
            dormant = StreamState(
                n=(0.0,) * len(COMPONENTS), temperature=temperature, pressure=pressure
            )
            return FlashResult(
                status="ok",
                phase_signature="ZERO_FLOW",
                vapor_fraction=None,
                vapor=dormant,
                liquid=dormant,
                provider_id=PROVIDER_ID,
                reference_convention=REFERENCE_CONVENTION,
                message="dormant feed: composition undefined (ADR 0001 D3.1, D3.4)",
            )

        outside = _domain_violation(temperature, pressure)
        if outside is not None:
            return _flash_failure("out_of_domain", outside)

        total = state.total_flow
        k_values = tuple(math.exp(ln_k(temperature, pressure, i)) for i in range(len(COMPONENTS)))
        z = tuple(value / total for value in state.n)

        sum_zk = sum(z[i] * k_values[i] for i in range(len(COMPONENTS)))
        sum_z_over_k = sum(z[i] / k_values[i] for i in range(len(COMPONENTS)))

        if sum_zk <= 1.0:
            return self._single_phase(state, "LIQUID", k_values, 0.0)
        if sum_z_over_k <= 1.0:
            return self._single_phase(state, "VAPOR", k_values, 1.0)

        beta, iterations, converged = _rachford_rice(z, k_values)
        if iterations == 0:
            # The bracket decided (ADR 0017 D1): the feed is within one rounding of saturation
            # and the exact β within roundoff of the 0 or 1 returned.
            return self._single_phase(state, "LIQUID" if beta == 0.0 else "VAPOR", k_values, beta)
        if not converged:
            return _flash_failure(
                "not_converged",
                f"Rachford-Rice did not reach {_TOLERANCE} in {_MAX_ITERATIONS} iterations",
            )

        x = tuple(z[i] / (1.0 + beta * (k_values[i] - 1.0)) for i in range(len(COMPONENTS)))
        y = tuple(k_values[i] * x[i] for i in range(len(COMPONENTS)))
        vapor_total, liquid_total = beta * total, (1.0 - beta) * total
        return FlashResult(
            status="ok",
            phase_signature="TWO_PHASE",
            vapor_fraction=beta,
            vapor=StreamState(
                n=tuple(vapor_total * value for value in y),
                temperature=temperature,
                pressure=pressure,
            ),
            liquid=StreamState(
                n=tuple(liquid_total * value for value in x),
                temperature=temperature,
                pressure=pressure,
            ),
            k_values=dict(zip(COMPONENTS, k_values, strict=True)),
            iterations=iterations,
            provider_id=PROVIDER_ID,
            reference_convention=REFERENCE_CONVENTION,
        )

    def _single_phase(
        self, state: StreamState, phase: Phase, k_values: Sequence[float], beta: float
    ) -> FlashResult:
        """One outlet carries the whole feed; the other is dormant with the same T and P.

        The dormant outlet keeps `T` and `P` because ADR 0001 D3.1 retains them as labels — they
        may be needed as initialization hints and as pressure-network values — while its
        composition is undefined and its flows are exactly zero.
        """
        empty = StreamState(
            n=(0.0,) * len(COMPONENTS),
            temperature=state.temperature,
            pressure=state.pressure,
        )
        return FlashResult(
            status="ok",
            phase_signature=phase,
            vapor_fraction=beta,
            vapor=state if phase == "VAPOR" else empty,
            liquid=state if phase == "LIQUID" else empty,
            k_values=dict(zip(COMPONENTS, k_values, strict=True)),
            provider_id=PROVIDER_ID,
            reference_convention=REFERENCE_CONVENTION,
        )


# -- the closed forms (docs/derivations/SYN-001.md §3) -------------------------------------------


def ln_k(temperature: float, pressure: float, index: int) -> float:
    """`ln K_i = ln(P_r/P) + (L_i/R)(1/T_b,i − 1/T) + v_i (P − P_r)/(R T)`."""
    return (
        math.log(P_REF / pressure)
        + (L_VAP[index] / R) * (1.0 / T_BOIL[index] - 1.0 / temperature)
        + V_MOLAR[index] * (pressure - P_REF) / (R * temperature)
    )


def d_ln_k_d_temperature(temperature: float, pressure: float, index: int) -> float:
    """`∂lnK_i/∂T = [L_i − v_i (P − P_r)] / (R T²)`."""
    return (L_VAP[index] - V_MOLAR[index] * (pressure - P_REF)) / (R * temperature * temperature)


def d_ln_k_d_pressure(temperature: float, pressure: float, index: int) -> float:
    """`∂lnK_i/∂P = −1/P + v_i/(R T)`.

    Identical across components here because every `v_i` is the same, which the P02 specification
    §12 already records as a place where the fixture's data carries no ordering evidence: a
    provider that used `V_MOLAR[0]` for every component would agree with this everywhere. The
    index is kept in the signature because the *formula* depends on the component even where this
    fixture's numbers do not.
    """
    return -1.0 / pressure + V_MOLAR[index] / (R * temperature)


def h_liquid(temperature: float, pressure: float, index: int) -> float:
    """`h_i^L(T, P) = c_p (T − T_r) + v_i (P − P_r)`, J/mol, zero at the reference state."""
    return C_P * (temperature - T_REF) + V_MOLAR[index] * (pressure - P_REF)


def h_vapor(temperature: float, index: int) -> float:
    """`h_i^V(T) = c_p (T − T_r) + L_i`, J/mol. Independent of pressure in this fixture."""
    return C_P * (temperature - T_REF) + L_VAP[index]


def _domain_violation(temperature: float, pressure: float) -> str | None:
    """The declared domain is part of the public contract, so leaving it is reported by name."""
    if not math.isfinite(temperature) or not math.isfinite(pressure):
        return f"non-finite state (T = {temperature!r} K, P = {pressure!r} Pa)"
    if not T_MIN <= temperature <= T_MAX:
        return f"temperature {temperature!r} K outside [{T_MIN}, {T_MAX}] K"
    if not P_MIN <= pressure <= P_MAX:
        return f"pressure {pressure!r} Pa outside [{P_MIN}, {P_MAX}] Pa"
    return None


def _flash_failure(status: str, message: str) -> FlashResult:
    """No outlets and no vapour fraction: an unsolved flash reports absence, not a split."""
    return FlashResult(
        status=status,  # type: ignore[arg-type]
        phase_signature=None,
        vapor_fraction=None,
        vapor=None,
        liquid=None,
        provider_id=PROVIDER_ID,
        reference_convention=REFERENCE_CONVENTION,
        message=message,
    )


def _rachford_rice(z: Sequence[float], k_values: Sequence[float]) -> tuple[float, int, bool]:
    """Solve `Σ z_i (K_i − 1) / (1 + β (K_i − 1)) = 0` for `β` in the physical window.

    Bracketed bisection with a Newton step taken only when it stays inside the bracket. The
    function is monotonically decreasing in β, so the bracket is an invariant rather than a hope,
    and a Newton step that leaves it is rejected instead of trusted — which is what makes the
    iteration count a bound rather than an aspiration.

    The bracket is the *Rachford-Rice window* `(1/(1 − K_max), 1/(1 − K_min))` narrowed to `[0, 1]`,
    because the caller has already established that the mixture is two-phase.

    Except within one rounding of saturation (ADR 0017, finding F6): there the caller's
    `fl(Σ z_i K_i) > 1` (or `fl(Σ z_i/K_i) > 1`) and this function's `f(0)` (or `f(1)`) are two
    roundings of one exact quantity that straddle zero, and `f(0)`, `f(1)` share a sign. The
    bracket's signs then name the phase — both negative, liquid (`β = 0`); both positive, vapour
    (`β = 1`) — and that is returned with **zero iterations**, which only this branch reports.
    """

    def residual(beta: float) -> float:
        return sum(
            z[i] * (k_values[i] - 1.0) / (1.0 + beta * (k_values[i] - 1.0)) for i in range(len(z))
        )

    low, high = 0.0, 1.0
    f_low, f_high = residual(low), residual(high)
    if f_low * f_high > 0.0:
        return (0.0 if f_low < 0.0 else 1.0), 0, True

    beta = 0.5
    for iteration in range(1, _MAX_ITERATIONS + 1):
        value = residual(beta)
        if abs(value) <= _TOLERANCE:
            return beta, iteration, True
        if value * f_low > 0.0:
            low, f_low = beta, value
        else:
            high, f_high = beta, value

        derivative = -sum(
            z[i] * (k_values[i] - 1.0) ** 2 / (1.0 + beta * (k_values[i] - 1.0)) ** 2
            for i in range(len(z))
        )
        candidate = beta - value / derivative if derivative != 0.0 else beta
        beta = candidate if low < candidate < high else 0.5 * (low + high)

    return beta, _MAX_ITERATIONS, False


def _implementation_sha256() -> str:
    """Hash of this module's own source. Blueprint §6.4 puts it in the exact cache key."""
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _data_sha256() -> str:
    """Hash of the constants, separately from the code (blueprint §6.4).

    Same code with different constants is a different provider for caching; so is the same data
    under changed code. Hashing them together would make one indistinguishable from the other.
    """
    from openflowsheet.canonical import hash_named_doubles

    names = (
        ("R", R),
        ("T_REF", T_REF),
        ("P_REF", P_REF),
        ("C_P", C_P),
        *((f"T_BOIL_{c}", T_BOIL[i]) for i, c in enumerate(COMPONENTS)),
        *((f"L_VAP_{c}", L_VAP[i]) for i, c in enumerate(COMPONENTS)),
        *((f"V_MOLAR_{c}", V_MOLAR[i]) for i, c in enumerate(COMPONENTS)),
    )
    return hash_named_doubles(dict(names), tuple(name for name, _ in names))
