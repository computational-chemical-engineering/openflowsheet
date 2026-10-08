"""The solver side's reading of a `pr-c1-v1` TP flash: M01 spec §7 rule 3 with τ_dew.

One function, `classify` (design note §14.2 B14; register R-256), used wherever the solve side asks
what phase a C1 stream is in: the region's kernel and admissibility screen for a lifted PR split,
and the causal evaluates of the mixer, the heater and the flash (B16).

**The band.** A vapour at its own dew point flashes TWO_PHASE with a liquid of order ε n_tot (M01
F4), and there the TWO_PHASE Jacobian is singular: the dew point is where the two branches
bifurcate. So a TWO_PHASE answer whose liquid NH3 fraction `l_NH3 / n_tot` is at most τ_dew
(`models.c1.TAU_DEW`) is read as VAPOR. τ_dew is the provider convention's (R-230), not the
solve policy's: `SolvePolicy.admissibility_epsilon` is never read for `pr-c1-v1`.

The verifier keeps its own copy of the rule (`verify.pr_c1`, R-016); a test compares the two as
data (gate G7 (k)).
"""

from __future__ import annotations

from collections.abc import Sequence

from openflowsheet.compiled import EvaluationContext, PhaseSignature
from openflowsheet.models.c1 import TAU_DEW
from openflowsheet.thermo import FlashRequest, FlashResult, PropertyProvider, StreamState
from openflowsheet.thermo.pr_c1 import I_NH3, LIGHT

__all__ = ["classify"]


def classify(
    provider: PropertyProvider,
    context: EvaluationContext,
    n: Sequence[float],
    temperature: float,
    pressure: float,
) -> tuple[PhaseSignature | None, float, FlashResult]:
    """The provider's TP flash of `(n, T, P)` read by M01 spec §7 rule 3 with τ_dew.

    Returns `(regime, value, result)`:
    - ZERO_FLOW → `(ZERO_FLOW, 0.0)`; VAPOR → `(VAPOR, 0.0)`;
    - LIQUID → `(LIQUID, n_light / n_tot)`;
    - TWO_PHASE → value `l_NH3 / n_tot` (`l_NH3` the result's liquid NH3, `n_tot = sum(n)`), and
      the regime is VAPOR iff the value is at most τ_dew, else TWO_PHASE.

    On a status other than `ok` the regime is `None` and the value NaN; the caller handles the
    refusal exactly as it handles any provider refusal there (B14).
    """
    state = StreamState(
        n=tuple(float(value) for value in n), temperature=temperature, pressure=pressure
    )
    result = provider.flash(FlashRequest(state=state), context)
    if result.status != "ok" or result.phase_signature is None:
        return None, float("nan"), result
    signature = result.phase_signature
    if signature in ("ZERO_FLOW", "VAPOR"):
        return signature, 0.0, result
    total = state.total_flow
    if signature == "LIQUID":
        return "LIQUID", sum(state.n[k] for k in LIGHT) / total, result
    assert result.liquid is not None  # an `ok` TWO_PHASE flash carries both outlets
    value = result.liquid.n[I_NH3] / total
    return ("VAPOR" if value <= TAU_DEW else "TWO_PHASE"), value, result
