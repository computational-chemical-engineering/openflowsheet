"""The phase-policy kernel of the EO region solver (T03, T05b): lifted splits, the PH closure
and the admissibility screens.

Moved verbatim from `orchestrator.region` (S19 B1); `region` re-exports what its callers and
tests read there. This module reaches nothing in `region` or `region_problem`.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import temperature_id
from openflowsheet.models.c1.phase import classify
from openflowsheet.models.lifted import (
    AdmissibilityRefusal,
    Branch,
    LiftedSplit,
    Regime,
    VapourOnlyForm,
    ZeroFlowForm,
)
from openflowsheet.models.syn001 import ENERGY_TOLERANCE, gamma_phi
from openflowsheet.models.syn001.equilibrium_form import composition_dependent
from openflowsheet.models.syn001.ph_kernel import ph_state
from openflowsheet.models.syn001.saturation_band import BandError, band_temperature
from openflowsheet.models.syn001.tp_state import enthalpy_flow, tp_state
from openflowsheet.thermo import FlashRequest, Phase, PropertyProvider, PropertyRequest, StreamState
from openflowsheet.thermo.pr_c1 import LIGHT
from openflowsheet.thermo.pr_c1 import PROVIDER_ID as PR_C1_PROVIDER_ID


class _KernelRefusedError(ValueError):
    """The provider would not split a lifted stream (review S5). Never escapes `solve_region`:
    it becomes the `EVALUATION_ERROR` the outcome vocabulary has for it."""

    def __init__(self, stream: str, status: str, message: str) -> None:
        super().__init__(
            f"the kernel could not split {stream}: the provider returned {status}"
            + (f" ({message})" if message else "")
        )


def _kernel(
    provider: PropertyProvider,
    context: EvaluationContext,
    split: LiftedSplit,
    state: Mapping[str, float],
    *,
    temperature: str | None = None,
) -> tuple[Regime, dict[str, float]]:
    """The provider's regime and split at the stream's `(n, T, P)` (K03 §8.3): the feed's flows,
    the split's pressure and the split's temperature — or the `temperature` column named."""
    stream = StreamState(
        n=tuple(state[name] for name in split.feed),
        temperature=state[split.temperature if temperature is None else temperature],
        pressure=state[split.pressure],
    )
    if _pr_c1(provider):
        # M02 design note §14.2 B14: M01 §7 rule 3 with τ_dew. A VAPOR answer — the provider's,
        # or a TWO_PHASE one inside the dew band — opens as `_pin(VAPOR)` sets it.
        band, _, result = classify(provider, context, stream.n, stream.temperature, stream.pressure)
        if band == "VAPOR" and result.status == "ok":
            return "VAPOR", _vapour_pinned(split, stream.n)
    else:
        result = provider.flash(FlashRequest(state=stream), context)
    if result.status != "ok" or result.vapor is None or result.liquid is None:
        raise _KernelRefusedError(split.stream, str(result.status), result.message)
    regime: Regime = "TWO_PHASE"
    if result.phase_signature == "LIQUID":
        regime = "LIQUID"
    elif result.phase_signature == "VAPOR":
        regime = "VAPOR"
    values = {
        **dict(zip(split.vapor, result.vapor.n, strict=True)),
        **dict(zip(split.liquid, result.liquid.n, strict=True)),
        split.vapor_total: float(sum(result.vapor.n)),
        split.liquid_total: float(sum(result.liquid.n)),
    }
    return regime, values


def _pr_c1(provider: PropertyProvider) -> bool:
    """Whether `provider` is `pr-c1-v1` (B14's dispatch; `describe` is uncounted)."""
    return provider.describe().provider_id == PR_C1_PROVIDER_ID


def _vapour_pinned(split: LiftedSplit, feed: Sequence[float]) -> dict[str, float]:
    """A VAPOR split's values as `_pin(VAPOR)` writes them: the vapour the feed bitwise, the
    liquid `+0.0`, `V = float(sum(feed))`, `L = 0.0`."""
    values = dict(zip(split.vapor, feed, strict=True))
    values.update(dict.fromkeys(split.liquid, 0.0))
    values[split.vapor_total] = float(sum(feed))
    values[split.liquid_total] = 0.0
    return values


@dataclass(frozen=True)
class _KernelAnswer:
    """The contract's kernel at one split and state: its regime, the split's values it opens with
    (and, from a PH closure, the split's temperature), and F2's record (T05b spec §6.5): `""`
    for a primary answer, `ph-band` or `tp` for a fallback's."""

    regime: Regime
    values: dict[str, float]
    fallback: str = ""


def _zero_flow_answer(split: LiftedSplit) -> _KernelAnswer:
    """T05b spec §6.2 step 1 and §7.1: a dormant feed's regime is `ZERO_FLOW`, and every lifted
    flow of its split is `+0.0` (§7.4: entering pins them and leaves every other value)."""
    names = (*split.vapor, *split.liquid, split.vapor_total, split.liquid_total)
    return _KernelAnswer("ZERO_FLOW", dict.fromkeys(names, 0.0))


def _dormant_feed(split: LiftedSplit, state: Mapping[str, float]) -> bool:
    """ADR 0001 D3.1: every flow of the split's feed exactly zero (`-0.0 == 0.0`)."""
    return all(state[name] == 0.0 for name in split.feed)


def _split_enthalpy(
    provider: PropertyProvider,
    context: EvaluationContext,
    split: LiftedSplit,
    state: Mapping[str, float],
) -> float | None:
    """T05b spec §6.2 step 2's `H_split = Σ v_i h_i^V(T, P) + Σ l_i h_i^L(T, P)`, with `T`, `P`
    the split's temperature and pressure columns; `None` when the provider refuses an enthalpy."""
    temperature, pressure = state[split.temperature], state[split.pressure]
    components = provider.describe().components
    target = 0.0
    phases: tuple[tuple[Phase, tuple[str, ...]], ...] = (
        ("VAPOR", split.vapor),
        ("LIQUID", split.liquid),
    )
    for phase, names in phases:
        stream = StreamState(
            n=tuple(state[name] for name in names), temperature=temperature, pressure=pressure
        )
        status, contribution, _ = enthalpy_flow(provider, stream, phase, components, context)
        if status != "ok":
            return None
        target += contribution
    return target


#: `_band_regime`'s (s1) answer: `ph_state` would refuse the target as outside the domain, so the
#: screen reports the TP flash's regime at the trial, as step 4 does.
TP_REGIME: Final = "tp"


def _band_regime(
    provider: PropertyProvider,
    context: EvaluationContext,
    feed: tuple[float, ...],
    pressure: float,
    target: float,
) -> Regime | Literal["tp"] | None:
    """T05b spec §6.2 (s1)–(s2) as amended (ruling Q-S10, R-053; review S1): the regime of a flagged
    PH-type trial of the flowing `feed` at `(P, H_split = target)`, from the band's end
    enthalpies instead of the full closure.

    (s1) `target` below `Ḣ_TP(feed, T_min, P)` or above `Ḣ_TP(feed, T_max, P)` — `ph_state`'s own
    step-3 test on the same function — gives `TP_REGIME`. (s2) Else, with `T_b = T(0)`,
    `T_d = T(1)` (`band_temperature`, its sign oracle: a band end below the domain is `−∞`, above
    it `+∞`), `H_0 = Σ n_i h_i^L(T_b, P)` and `H_1 = Σ n_i h_i^V(T_d, P)`: `LIQUID` below
    `H_0 − τ_E`, `TWO_PHASE` strictly between `H_0 + τ_E` and `H_1 − τ_E`, `VAPOR` above
    `H_1 + τ_E`. (s3) `None` — ask the full closure — within `τ_E` of an end, or when any
    evaluation here is not `ok`.

    Exact wherever `ph_state` answers `ok` (§6.2: an `ok` answer carries the target to `τ_E`, and
    the phase regions are ordered by enthalpy, §4.2); floating-point error in `H_0`, `H_1` is far
    below the `τ_E` margin. Costs two `T(β)` bisections, two TP flashes and two enthalpy sums."""
    t_min, t_max = provider.describe().domain["T"]
    for end in (t_min, t_max):
        at_end = tp_state(
            provider, StreamState(n=feed, temperature=end, pressure=pressure), context
        )
        if at_end.status != "ok" or at_end.enthalpy_flow is None:
            return None
        if (end == t_min and target < at_end.enthalpy_flow) or (
            end == t_max and target > at_end.enthalpy_flow
        ):
            return TP_REGIME
    components = provider.describe().components
    ends: list[float] = []
    band_ends: tuple[tuple[float, Phase], ...] = ((0.0, "LIQUID"), (1.0, "VAPOR"))
    for beta, phase in band_ends:
        try:
            at = band_temperature(provider, feed, pressure, beta, context)
        except BandError:
            return None
        if at.temperature is None:
            ends.append(-math.inf if at.position == "below" else math.inf)
            continue
        stream = StreamState(n=feed, temperature=at.temperature, pressure=pressure)
        status, value, _ = enthalpy_flow(provider, stream, phase, components, context)
        if status != "ok":
            return None
        ends.append(value)
    h_0, h_1 = ends
    if target < h_0 - ENERGY_TOLERANCE:
        return "LIQUID"
    if h_0 + ENERGY_TOLERANCE < target < h_1 - ENERGY_TOLERANCE:
        return "TWO_PHASE"
    if target > h_1 + ENERGY_TOLERANCE:
        return "VAPOR"
    return None


#: T05b spec §6.2 as amended, "carrying": a PH closure (steps 2–3) the screen asked at a trial,
#: by unit and the exact inputs (`_closure_key`), which an opening at the same state reuses.
type ClosureMemo = dict[tuple[str, tuple[str, ...]], "_KernelAnswer | None"]


def _closure_key(split: LiftedSplit, state: Mapping[str, float]) -> tuple[str, tuple[str, ...]]:
    """`_ph_closure`'s inputs, exactly (`float.hex`: `-0.0` is not `+0.0`)."""
    names = (*split.feed, *split.vapor, *split.liquid, split.temperature, split.pressure)
    return split.unit, tuple(float(state[name]).hex() for name in names)


def _ph_closure(
    provider: PropertyProvider,
    context: EvaluationContext,
    split: LiftedSplit,
    state: Mapping[str, float],
    temperatures: Sequence[str] | None = None,
) -> _KernelAnswer | None:
    """T05b spec §6.2 steps 2–3 (F2's primary): the PH closure of the split's feed at the split's
    own enthalpy, `H_split = Σ v_i h_i^V(T, P) + Σ l_i h_i^L(T, P)` with `T`, `P` the split's
    temperature and pressure columns. `None` when it gives no answer — a provider refusal of the
    enthalpy, or any non-`ok` closure — and the caller falls back to the TP flash (step 4).

    `temperatures` are every temperature column of the split's streams
    (`splits.split_temperatures`); the answer sets each to the closure's `T` (step 3 as amended,
    Q-S11 (a)). `None` names the split's own column only."""
    feed = tuple(state[name] for name in split.feed)
    if all(value == 0.0 for value in feed):
        # Spec §6.2 step 1: the regime is `ZERO_FLOW`.
        return _zero_flow_answer(split)
    target = _split_enthalpy(provider, context, split, state)
    if target is None:
        return None
    closure = ph_state(provider, feed, state[split.pressure], target, context)
    if closure.status != "ok":
        return None
    answer = closure.split
    assert answer is not None and answer.vapor is not None and answer.liquid is not None
    assert closure.temperature is not None
    regime: Regime = "TWO_PHASE"
    if answer.phase_signature == "LIQUID":
        regime = "LIQUID"
    elif answer.phase_signature == "VAPOR":
        regime = "VAPOR"
    values = {
        **dict(zip(split.vapor, answer.vapor.n, strict=True)),
        **dict(zip(split.liquid, answer.liquid.n, strict=True)),
        split.vapor_total: float(sum(answer.vapor.n)),
        split.liquid_total: float(sum(answer.liquid.n)),
        # §6.2 step 3 as amended (Q-S11 (a)): the opening sets every temperature column of the
        # split's streams to the closure's — a products-style split's liquid product too.
        **dict.fromkeys(
            (split.temperature,) if temperatures is None else temperatures, closure.temperature
        ),
    }
    return _KernelAnswer(regime, values, "ph-band" if closure.route == "band" else "")


def _contract_kernel(
    provider: PropertyProvider,
    context: EvaluationContext,
    split: LiftedSplit,
    state: Mapping[str, float],
    ph_units: frozenset[str],
    *,
    v2: bool = False,
    regime: Regime | None = None,
    temperatures: Sequence[str] | None = None,
    memo: ClosureMemo | None = None,
) -> _KernelAnswer:
    """ADR 0005's "kernel" of one split under the policy's rule set: the TP flash (`_kernel`) —
    every split under v1, a TP-type split under v2 — or, for a PH-type split under v2 (`ph_units`
    is empty under v1), F2: the PH closure, then the TP flash recorded `tp` (T05b spec §6.2).

    Under v2 (`v2`), for either closure type (spec §7.1, §7.4): a dormant feed is `ZERO_FLOW`;
    a split whose attempt `regime` is `ZERO_FLOW` and whose feed flows is leaving it, and its
    pinned split carries no enthalpy, so the TP flash answers — recorded `tp` when PH-type. As
    amended (Q-S14) a PH-type split's leaving flash is taken at its feed's `n` and `T` and its
    own (outlet) `P`, and that `T` is written to every column of `temperatures`: the split's own
    `T` is the zero-flow label of an earlier feed, i.e. attempt history. A TP-type split flashes
    at its own specified `T`.

    `temperatures` are the split's temperature columns (`splits.split_temperatures`), which a PH
    closure's answer and a PH-type leaving answer set. `memo` holds the closures the attempt's
    screen asked (§6.2 as amended, "carrying"): one at the same inputs is reused, not asked
    again."""
    if v2 and _dormant_feed(split, state):
        return _zero_flow_answer(split)
    if v2 and regime == "ZERO_FLOW":
        if split.unit not in ph_units:
            leaving, values = _kernel(provider, context, split, state)
            return _KernelAnswer(leaving, values)
        # The stream `split.feed` names: a products-style split's inlet; an outlet-style split's
        # own outlet, whose `T` is `split.temperature` — there the flash is unchanged and there is
        # nothing to write.
        feed = temperature_id(split.stream)
        leaving, values = _kernel(provider, context, split, state, temperature=feed)
        written = (split.temperature,) if temperatures is None else tuple(temperatures)
        values.update({column: state[feed] for column in written if column != feed})
        return _KernelAnswer(leaving, values, "tp")
    if split.unit in ph_units:
        key = _closure_key(split, state)
        if memo is not None and key in memo:
            answer = memo[key]
        else:
            answer = _ph_closure(provider, context, split, state, temperatures)
        if answer is not None:
            return answer
        regime, values = _kernel(provider, context, split, state)
        return _KernelAnswer(regime, values, "tp")
    regime, values = _kernel(provider, context, split, state)
    return _KernelAnswer(regime, values)


def _reference_k_values(
    provider: PropertyProvider,
    temperature: float,
    pressure: float,
    context: EvaluationContext,
) -> tuple[float, ...]:
    """`K_i(T, P)` from the provider, for the ideal-K admissibility sums of K03 §8.2.

    The verifier's `k_values` restated: the same request and the same `math.exp`,
    so bitwise the same K. Restated because the region may not import the verifier (R-016, ADR
    0076 I-15); `tests/test_s19_i15_admissibility_refusal.py` pins the two equal."""
    reference = StreamState(n=(1.0, 1.0, 1.0), temperature=temperature, pressure=pressure)
    result = provider.evaluate_phase(
        PropertyRequest(state=reference, phase="LIQUID", properties=("lnK",)), context
    )
    if result.status != "ok":
        raise AdmissibilityRefusal(f"the verifier's own K-values returned {result.status}")
    return tuple(math.exp(result.values[f"lnK_{component}"]) for component in ("A", "B", "C"))


def _admissible(
    provider: PropertyProvider,
    context: EvaluationContext,
    split: LiftedSplit,
    regime: Branch,
    state: Mapping[str, float],
    epsilon: float,
) -> tuple[bool, float]:
    """K03 §8.2 on a single-phase branch: a liquid that would boil, a vapour that would condense.

    A `ZERO_FLOW` branch (`V = L = 0`, ADR 0012 D6) is admissible iff its feed is exactly dormant
    (T05b spec §7.3's closure rule, which §8 applies under every literal): a split with nothing
    in either phase is right only when nothing flows into it. The value is the feed's total."""
    if regime == "TWO_PHASE":
        return True, 0.0
    if regime == "ZERO_FLOW":
        feed = sum(state[name] for name in split.feed)
        return all(state[name] == 0.0 for name in split.feed), feed
    if _pr_c1(provider):
        return _pr_admissible(provider, context, split, regime, state)
    if composition_dependent(provider):
        return _gamma_phi_admissible(provider, context, split, regime, state, epsilon)
    constants = _reference_k_values(
        provider, state[split.temperature], state[split.pressure], context
    )
    side = split.liquid if regime == "LIQUID" else split.vapor
    amounts = [state[name] for name in side]
    total = sum(amounts)
    if total == 0.0:
        return True, 0.0
    fractions = [amount / total for amount in amounts]
    if regime == "LIQUID":
        value = sum(x * k for x, k in zip(fractions, constants, strict=True))
    else:
        value = sum(y / k for y, k in zip(fractions, constants, strict=True))
    return value <= 1.0 + epsilon, value


def admissibility_value(
    provider: PropertyProvider,
    context: EvaluationContext,
    split: LiftedSplit,
    regime: Literal["LIQUID", "VAPOR"],
    state: Mapping[str, float],
) -> float | None:
    """The value `_admissible` judges a single-phase branch by at `state` (K03 §8.2): the closure's
    own test, admissible iff `value ≤ 1 + ε` — ideal K: `Σ x K` (LIQUID) or `Σ y/K` (VAPOR) over the
    side's composition; a composition-dependent K: `Σ x K(x)` or the incipient-liquid `ΣW`. A pure
    addition for OPT's regime margins (OPT design §9 A-3); the closure keeps calling `_admissible`.

    `None` where the closure judges the branch by another form (`pr-c1-v1`: `classify`, and a
    light-gas fraction that must be exactly zero — not "value ≤ 1 + ε") or where the test raises
    at `state`."""
    if _pr_c1(provider):
        return None
    try:
        # ε only decides the flag, never the value.
        _, value = _admissible(provider, context, split, regime, state, 0.0)
    except (AdmissibilityRefusal, BandError, ValueError, ArithmeticError):
        return None
    return float(value)


def _gamma_phi_admissible(
    provider: PropertyProvider,
    context: EvaluationContext,
    split: LiftedSplit,
    regime: Branch,
    state: Mapping[str, float],
    epsilon: float,
) -> tuple[bool, float]:
    """K03 §8.2 for a composition-dependent K (S10-C design note §4.10): LIQUID's value is
    `Σ x_i K_i(T, P, x)` with `x` the liquid side's composition (`gamma_phi.ln_k`), VAPOR's is
    `ΣW` of the incipient liquid against the vapour side (`gamma_phi.incipient_liquid`); admissible
    iff `value ≤ 1 + ε`. An empty side is admissible with value `0.0`, as in the SYN-001 rule. A
    `BandError` is an `AdmissibilityRefusal`, which the screen converts to `invalid_trial_state`."""
    side = split.liquid if regime == "LIQUID" else split.vapor
    amounts = [state[name] for name in side]
    total = sum(amounts)
    if total == 0.0:
        return True, 0.0
    fractions = tuple(amount / total for amount in amounts)
    temperature, pressure = state[split.temperature], state[split.pressure]
    try:
        if regime == "LIQUID":
            ln_k, _, _ = gamma_phi.ln_k(provider, temperature, pressure, fractions, context)
            value = sum(x * math.exp(lnk) for x, lnk in zip(fractions, ln_k, strict=True))
        else:
            value, _ = gamma_phi.incipient_liquid(
                provider, temperature, pressure, fractions, context
            )
    except BandError as error:
        raise AdmissibilityRefusal(
            f"the kernel refused {split.unit}'s regime ({split.stream}): {error.status}: "
            f"{error.message}"
        ) from error
    return value <= 1.0 + epsilon, value


def _pr_admissible(
    provider: PropertyProvider,
    context: EvaluationContext,
    split: LiftedSplit,
    regime: Branch,
    state: Mapping[str, float],
) -> tuple[bool, float]:
    """B14 on a single-phase branch of a `pr-c1-v1` split, `admissibility_epsilon` unread:
    VAPOR iff `classify` of the feed at the split's `(T, P)` is VAPOR, with its value; LIQUID iff
    no light gas flows in the feed and `classify` is LIQUID, with value `n_light / n_tot`. A
    provider refusal is an `AdmissibilityRefusal`, which the screen converts to
    `invalid_trial_state`. A dormant feed is admissible with value `0.0`, as the K03 rule's empty
    side is."""
    feed = tuple(state[name] for name in split.feed)
    total = sum(feed)
    if total == 0.0:
        return True, 0.0
    answer, value, result = classify(
        provider, context, feed, state[split.temperature], state[split.pressure]
    )
    if answer is None:
        raise AdmissibilityRefusal(
            f"the kernel refused {split.unit}'s regime ({split.stream}): {result.status}: "
            f"{result.message}"
        )
    if regime == "VAPOR":
        return answer == "VAPOR", value
    light = sum(feed[k] for k in LIGHT)
    return all(feed[k] == 0.0 for k in LIGHT) and answer == "LIQUID", light / total


def _branch(split: LiftedSplit, state: Mapping[str, float], v2: bool = False) -> str:
    """Which branch a supplied split is on, for the projection record; under v2 an empty split
    (`V = L = 0`) is `zero_flow` (T05b spec §6.5's branch word), under v1 `two_phase` as before."""
    vapor, liquid = state[split.vapor_total], state[split.liquid_total]
    if v2 and vapor == 0.0 and liquid == 0.0:
        return "zero_flow"
    if vapor == 0.0 and liquid > 0.0:
        return "all_liquid"
    if liquid == 0.0 and vapor > 0.0:
        return "all_vapor"
    return "two_phase"


def _pin(state: dict[str, float], split: LiftedSplit, regime: Regime) -> None:
    """§6.3.3's restart point: the phase that left is exactly zero, the other takes the feed."""
    feed = [state[name] for name in split.feed]
    if regime == "LIQUID":
        state.update(dict.fromkeys(split.vapor, 0.0))
        state[split.vapor_total] = 0.0
        state.update(dict(zip(split.liquid, feed, strict=True)))
        state[split.liquid_total] = float(sum(feed))
    elif regime == "VAPOR":
        state.update(dict.fromkeys(split.liquid, 0.0))
        state[split.liquid_total] = 0.0
        state.update(dict(zip(split.vapor, feed, strict=True)))
        state[split.vapor_total] = float(sum(feed))


def _form(split: LiftedSplit, forms: Mapping[str, ZeroFlowForm]) -> ZeroFlowForm:
    form = forms.get(split.unit)
    if form is None:
        raise ValueError(f"defect: {split.unit} is in ZERO_FLOW and the region has no form for it")
    return form


def _pinned(
    split: LiftedSplit,
    regime: Regime,
    forms: Mapping[str, ZeroFlowForm],
    vapour_only: Mapping[str, VapourOnlyForm] | None = None,
) -> tuple[str, ...]:
    """The columns an attempt holds at `+0.0` for one split: its `ZeroFlowForm`'s in `ZERO_FLOW`
    (T05b spec §7.2), `LiftedSplit.pinned`'s otherwise — and, in `TWO_PHASE`, its
    `VapourOnlyForm`'s (M02 design note §14.2 B13)."""
    if regime == "ZERO_FLOW":
        return _form(split, forms).columns
    if regime == "TWO_PHASE" and vapour_only and split.unit in vapour_only:
        return (*split.pinned(regime), *vapour_only[split.unit].columns)
    return split.pinned(regime)


def _dropped(
    split: LiftedSplit,
    regime: Regime,
    forms: Mapping[str, ZeroFlowForm],
    vapour_only: Mapping[str, VapourOnlyForm] | None = None,
) -> tuple[str, ...]:
    """The rows an attempt drops for one split, as `_pinned`."""
    if regime == "ZERO_FLOW":
        return _form(split, forms).rows
    if regime == "TWO_PHASE" and vapour_only and split.unit in vapour_only:
        return (*split.dropped(regime), *vapour_only[split.unit].rows)
    return split.dropped(regime)
