"""The region's trial screen (T03 §4.3, K03 §8.2, T05b §6.2, §7.3, §7.8).

`_attempt_screen` picks an attempt's screen: T03's (`_screen`) under v1, else `_build_screen`'s
v2 screen, which answers a flagged PH-type unit by its band ends or its PH closure, checks each
split's dormancy against its regime, and reads each dormancy form's item off the trial.

Split from `orchestrator.region` (S19 RS), which re-exports the three names. Of the region solver
this module imports `region_phase` and `region_problem`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Literal

from openflowsheet.compiled import EvaluationContext, PhaseSignature
from openflowsheet.models import temperature_id
from openflowsheet.models.c1.phase import classify
from openflowsheet.models.lifted import AdmissibilityRefusal, DormancyForm, LiftedSplit, Regime
from openflowsheet.numerics.newton import Evaluation
from openflowsheet.numerics.solve_record import AttemptSignature
from openflowsheet.orchestrator.budget import BudgetExhaustedError
from openflowsheet.orchestrator.region_phase import (
    TP_REGIME,
    ClosureMemo,
    _admissible,
    _band_regime,
    _closure_key,
    _dormant_feed,
    _KernelAnswer,
    _ph_closure,
    _pr_c1,
    _split_enthalpy,
)
from openflowsheet.orchestrator.region_problem import _items
from openflowsheet.thermo import FlashRequest, PropertyProvider, StreamState


def _attempt_screen(
    *,
    splits: Sequence[LiftedSplit],
    regimes: Mapping[str, Regime],
    provider: PropertyProvider,
    context: EvaluationContext,
    epsilon: float,
    ph_units: frozenset[str],
    v2: bool = False,
    dormancy: Sequence[DormancyForm] = (),
    temperatures: Mapping[str, tuple[str, ...]] | None = None,
    memo: ClosureMemo | None = None,
) -> Callable[[dict[str, float]], AttemptSignature | Evaluation]:
    """The attempt's screen: T03's (`_screen`) under v1 — every v1 attempt, called exactly as
    before — else the same screen with F2's kernel on the PH-type units (T05b spec §6.2), the
    dormancy agreement of every split (§7.3), and each dormancy form's item read off the trial
    (§7.8 (iii)). `temperatures` and `memo` are the openings' (§6.2 as amended): a full PH
    closure the screen asks is kept in `memo` for an opening at the same state."""
    if not v2:
        return _screen(
            splits=splits, regimes=regimes, provider=provider, context=context, epsilon=epsilon
        )
    return _build_screen(
        splits,
        regimes,
        provider,
        context,
        epsilon,
        ph_units,
        v2=True,
        dormancy=dormancy,
        temperatures=temperatures,
        memo=memo,
    )


def _screen(
    *,
    splits: Sequence[LiftedSplit],
    regimes: Mapping[str, Regime],
    provider: PropertyProvider,
    context: EvaluationContext,
    epsilon: float,
) -> Callable[[dict[str, float]], AttemptSignature | Evaluation]:
    """T03 §4.3: K03 §8.2 on each single-phase unit at a trial; the kernel on a flagged one."""
    return _build_screen(splits, regimes, provider, context, epsilon, frozenset())


def _build_screen(
    splits: Sequence[LiftedSplit],
    regimes: Mapping[str, Regime],
    provider: PropertyProvider,
    context: EvaluationContext,
    epsilon: float,
    ph_units: frozenset[str],
    v2: bool = False,
    dormancy: Sequence[DormancyForm] = (),
    temperatures: Mapping[str, tuple[str, ...]] | None = None,
    memo: ClosureMemo | None = None,
) -> Callable[[dict[str, float]], AttemptSignature | Evaluation]:
    """`_screen`'s body. The flag is v1's under both literals; under v2 a flagged PH-type unit
    (`ph_units`) reports its PH closure's regime, and the TP flash's only when the closure gives
    none (T05b spec §6.2). As amended (Q-S10, R-053) the regime is read off the band's end
    enthalpies (`_band_regime`, (s1)–(s2)); only inside a `τ_E` zone of an end, or when an
    evaluation there is not `ok`, is the full closure asked (s3), and its answer is kept in
    `memo` (with `temperatures`' columns, as an opening would ask it) for the opening.

    Under v2 (`v2`) every split is first checked for T05b spec §7.3's agreement — one comparison:
    a dormant feed reports `ZERO_FLOW`; a `ZERO_FLOW` split whose feed flows reports the TP
    flash's regime (it is leaving, and its pinned split carries no enthalpy, §7.4) at the
    leaving answer's inputs — for a PH-type split its feed's `T` (Q-S15 (3)). After the
    splits, each dormancy form's item is reported from the trial's trigger dormancy (§7.8 (iii),
    one comparison per outlet): an item the attempt does not run, or runs against a flowing
    trigger, makes the reported signature differ, and the trial is phase-rejected."""

    def screen(state: dict[str, float]) -> AttemptSignature | Evaluation:
        # The screen calls the provider outside the compiled residual, so it converts a refusal
        # exactly as the residual does (review S1): a spent budget is an `error` evaluation (the
        # executor reports `BUDGET_EXHAUSTED` from its meter), a provider that will not give the
        # K-values is `invalid_trial_state`. Neither may escape the attempt loop.
        try:
            return reported_signature(state)
        except BudgetExhaustedError as exhausted:
            return Evaluation(status="error", message=str(exhausted))
        except AdmissibilityRefusal as refused:
            return Evaluation(status="invalid_trial_state", message=str(refused))

    def reported_signature(state: dict[str, float]) -> AttemptSignature | Evaluation:
        reported: list[tuple[str, PhaseSignature]] = []
        for split in splits:
            regime = regimes[split.unit]
            if v2 and _dormant_feed(split, state):
                reported.append((split.unit, "ZERO_FLOW"))
                continue
            if v2 and regime == "ZERO_FLOW":
                # §7.4 as amended (Q-S15 (3)): a PH-type split reports the TP flash at the
                # leaving answer's inputs — its feed's `T` (`_contract_kernel`), not its own
                # `T` column, the zero-flow label of an earlier feed.
                leaving = _tp_flash_regime(
                    provider, context, split, state, leaving=split.unit in ph_units
                )
                if isinstance(leaving, Evaluation):
                    return leaving
                reported.append((split.unit, leaving))
                continue
            if regime == "TWO_PHASE":
                reported.append((split.unit, regime))
                continue
            ok, _ = _admissible(provider, context, split, regime, state, epsilon)
            if ok:
                reported.append((split.unit, regime))
                continue
            if split.unit in ph_units:
                screened = _band_screened_regime(provider, context, split, state)
                if screened is not None and screened != TP_REGIME:
                    reported.append((split.unit, screened))
                    continue
                if screened is None:
                    answer = asked(split, state)
                    if answer is not None:
                        reported.append((split.unit, answer.regime))
                        continue
            kernel = _tp_flash_regime(provider, context, split, state)
            if isinstance(kernel, Evaluation):
                return kernel
            reported.append((split.unit, kernel))
        return (*reported, *_items(dormancy, state))

    def asked(split: LiftedSplit, state: dict[str, float]) -> _KernelAnswer | None:
        """§6.2 (s3): the full closure, kept for an opening at the same state."""
        key = _closure_key(split, state)
        if memo is not None and key in memo:
            return memo[key]
        answer = _ph_closure(provider, context, split, state, (temperatures or {}).get(split.unit))
        if memo is not None:
            memo[key] = answer
        return answer

    return screen


def _tp_flash_regime(
    provider: PropertyProvider,
    context: EvaluationContext,
    split: LiftedSplit,
    state: dict[str, float],
    *,
    leaving: bool = False,
) -> PhaseSignature | Evaluation:
    """The provider's TP flash of the split's feed at the trial, or its refusal: at the
    split's own `T`, or — for a PH-type split `leaving` `ZERO_FLOW` — at its feed's `T`,
    as the opening's leaving answer asks it (`_contract_kernel`)."""
    temperature = temperature_id(split.stream) if leaving else split.temperature
    stream = StreamState(
        n=tuple(state[name] for name in split.feed),
        temperature=state[temperature],
        pressure=state[split.pressure],
    )
    band: PhaseSignature | None = None
    if _pr_c1(provider):
        # M02 design note §14.2 B14: the kernel's regime, so the dew band reads VAPOR here as
        # in `_kernel` (build log D38).
        band, _, flashed = classify(
            provider, context, stream.n, stream.temperature, stream.pressure
        )
    else:
        flashed = provider.flash(FlashRequest(state=stream), context)
    if flashed.status != "ok" or flashed.phase_signature is None:
        # The provider's own status (review N3; K03 §5.5: the unit, the status and the
        # message). Newton halves on any of them but `error`, which ends the attempt.
        return Evaluation(
            status="invalid_trial_state" if flashed.status == "ok" else flashed.status,
            message=(
                f"the kernel refused {split.unit}'s regime ({split.stream}) at the "
                f"trial: {flashed.status}: {flashed.message}"
            ),
        )
    if band == "VAPOR":
        return band
    if flashed.phase_signature in ("LIQUID", "VAPOR"):
        return flashed.phase_signature
    return "TWO_PHASE"


def _band_screened_regime(
    provider: PropertyProvider,
    context: EvaluationContext,
    split: LiftedSplit,
    state: dict[str, float],
) -> Regime | Literal["tp"] | None:
    """§6.2 (s1)–(s2): the band ends' regime, `TP_REGIME`, or `None` for (s3)."""
    target = _split_enthalpy(provider, context, split, state)
    if target is None:
        return None
    feed = tuple(state[name] for name in split.feed)
    return _band_regime(provider, context, feed, state[split.pressure], target)
