"""T05b B36: the leaving TP flash reads the feed, not the split's label (spec §7.4 and
§7.8 (ii) 1 (a) as amended 2026-09-25, ruling Q-S14; re-review N-W1).

A PH-type split leaving `ZERO_FLOW` takes its regime and split from the provider's TP flash at its
feed's `n` and `T` and its own (outlet) `P`, and that `T` is written to every temperature column of
the split's streams. Before the ruling the flash took the split's own `T` column — the zero-flow
label of an earlier feed, i.e. attempt history (re-review P9: 400 K in CH-UP while the feed was at
352.005 K). A TP-type split flashes at its own specified `T`, as before; an outlet-style PH-type
split's feed is its own outlet stream, so its flash is unchanged.

- (a) At the function level, CH-UP's restart opening with `U-PHF2` leaving `ZERO_FLOW` and its
  products' `T` set to 300 K (the feed `S2` flowing at `U-PHF`'s answer, 352.005 K): the flash is
  asked at `(S2.n, S2.T, S4.P)`, answers `VAPOR`, and `S4.T`, `S5.T` equal `S2.T` bitwise; the
  pre-ruling flash on the same opening (the split's own `T`, 300 K) answers another regime.
- (b) CH-UP-DP (B31 (i)): the leaving flash's pressure is `S4.P = 90 000` Pa, not `S2.P`.
- (c) What moved (re-registered in `test_t05b_openings.py`): the attempt-1 iteration counts of
  B31's leaving cases; see `docs/t05b-measurements.md` for before → after. As completed by
  Q-S15 (1) the list also holds the B34 sweep's leaving runs (`Q2 = 0`, `Q_s = 0`, both orders,
  8 runs), which B36 (c) first omitted: `(0, 0, 115 kW)` goes from `ACTIVE_SET_CYCLING` to
  `CONVERGED`, the others move only their records; re-registered in
  `test_t05b_candidate_answers.py` with that reason.
- (d) (Q-S15 (3)) The screen's leaving report reads the opening's inputs: (i) at (a)'s state as a
  trial with `U-PHF2` in `ZERO_FLOW` the v2 screen reports `VAPOR`, (a)'s leaving answer; the
  pre-ruling screen (the split's own `T`) reports another regime (the control). (ii) The `tp`
  exemption no longer covers a leaving answer: with the reported regime stubbed, `at_candidate`
  raises review N4's `RuntimeError`. (iii) Inertness is the protocol's (the full gate, the
  `t05b`, `t05` and SYN-001 keys, B31's records, B34 (a)'s counts and tally): unchanged on the
  change's own commit.
"""

from __future__ import annotations

from functools import cache
from typing import Any

import numpy as np
import pytest
from t05_w12_support import bind
from t05b_support import POLICY_V2, solve_from_v2
from test_t05b_openings import CASES, DP, QUP, _traversal, ch

from openflowsheet.orchestrator import region as region_module
from openflowsheet.orchestrator.phase_contract import Candidate
from openflowsheet.orchestrator.region import _attempt_screen, _contract_kernel, _kernel
from openflowsheet.orchestrator.revision import instances_of
from openflowsheet.orchestrator.splits import closure_types, lifted_splits, split_temperatures

#: `U-PHF`'s TWO_PHASE answer at DZ-12's duty (`ref…DZ-12.root`'s `S2.T`, 352.005 K), to 1e-3 K.
S2_T = 352.005


class _Recording:
    """The flowsheet's provider, recording every TP flash request."""

    def __init__(self, provider: Any) -> None:
        self._provider = provider
        self.requests: list[Any] = []

    def flash(self, request: Any, context: Any) -> Any:
        self.requests.append(request.state)
        return self._provider.flash(request, context)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._provider, name)


def _ch_up_opening() -> tuple[Any, Any, Any, dict[str, float], frozenset[str], tuple[str, ...]]:
    binding = bind(ch(QUP))
    flowsheet = binding.flowsheet
    instances = instances_of(flowsheet)
    splits = lifted_splits(instances, flowsheet.components)
    split = next(entry for entry in splits if entry.unit == "U-PHF2")
    types = closure_types(flowsheet.units())
    ph_units = frozenset(unit for unit, kind in types.items() if kind == "PH")
    temperatures = split_temperatures(instances, splits)["U-PHF2"]
    state = _traversal(ch(QUP))
    assert all(state[f"S2.n.{c}"] > 0.0 for c in "ABC")
    assert abs(state["S2.T"] - S2_T) <= 1e-3, state["S2.T"]
    state["S4.T"] = state["S5.T"] = 300.0
    return flowsheet, split, binding, state, ph_units, temperatures


def test_b36a_the_leaving_flash_is_at_the_feeds_t_and_writes_it() -> None:
    """(a) The flash at `(S2.n, S2.T, S4.P)`; `VAPOR`, recorded `tp`; `S4.T`, `S5.T` equal
    `S2.T` bitwise."""
    flowsheet, split, _, state, ph_units, temperatures = _ch_up_opening()
    assert temperatures == ("S4.T", "S5.T")
    provider = _Recording(flowsheet.provider)
    answer = _contract_kernel(
        provider,  # type: ignore[arg-type]
        flowsheet.context,
        split,
        state,
        ph_units,
        v2=True,
        regime="ZERO_FLOW",
        temperatures=temperatures,
    )
    (asked,) = provider.requests
    assert asked.n == tuple(state[f"S2.n.{c}"] for c in "ABC")
    assert asked.temperature == state["S2.T"]
    assert asked.pressure == state["S4.P"]
    assert (answer.regime, answer.fallback) == ("VAPOR", "tp")
    for column in ("S4.T", "S5.T"):
        assert repr(answer.values[column]) == repr(state["S2.T"])


def test_b36a_control_the_split_s_own_t_answers_another_regime() -> None:
    """(a)'s control: the pre-ruling flash on the same opening — the feed's flows at the split's
    own `T` (300 K) — does not answer `VAPOR`: the input decides."""
    flowsheet, split, _, state, _, _ = _ch_up_opening()
    regime, _ = _kernel(flowsheet.provider, flowsheet.context, split, state)
    assert regime != "VAPOR", regime


def test_b36b_off_the_dew_point_the_leaving_flash_is_at_the_outlet_pressure() -> None:
    """(b) CH-UP-DP end to end: every leaving flash of `U-PHF2` is asked at `S4.P = 90 000` Pa
    (its outlet), not at its feed's `S2.P`, and at the feed's `T`."""
    document, start = CASES["CH-UP-DP"]()
    asked: list[tuple[float, float, float, float, float]] = []
    real = region_module._kernel

    def kernel(provider: Any, context: Any, split: Any, state: Any, **kwargs: Any) -> Any:
        if split.unit == "U-PHF2" and kwargs.get("temperature") is not None:
            asked.append(
                (
                    state[split.pressure],
                    state["S2.P"],
                    state["S4.P"],
                    state[kwargs["temperature"]],
                    state["S2.T"],
                )
            )
        return real(provider, context, split, state, **kwargs)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(region_module, "_kernel", kernel)
        result = solve_from_v2(bind(document), start)
    assert result.outcome == "CONVERGED", result.message
    assert asked
    for pressure, feed_pressure, outlet_pressure, temperature, feed_temperature in asked:
        assert pressure == outlet_pressure == 100_000.0 - DP
        assert feed_pressure != pressure
        assert temperature == feed_temperature


# ------------------------------------------------- (d) the screen reads the opening's inputs

#: A trial of an attempt with `U-PHF2` in `ZERO_FLOW`; `U-PHF` `TWO_PHASE` (its answer at (a)'s
#: state), which the screen reports without a flash.
TRIAL_REGIMES = {"U-PHF": "TWO_PHASE", "U-PHF2": "ZERO_FLOW"}


def _screened(ph_units: frozenset[str]) -> Any:
    flowsheet, _, _, state, _, _ = _ch_up_opening()
    instances = instances_of(flowsheet)
    splits = lifted_splits(instances, flowsheet.components)
    screen = _attempt_screen(
        splits=splits,
        regimes=TRIAL_REGIMES,  # type: ignore[arg-type]
        provider=flowsheet.provider,
        context=flowsheet.context,
        epsilon=POLICY_V2.admissibility_epsilon,
        ph_units=ph_units,
        v2=True,
        temperatures=split_temperatures(instances, splits),
    )
    return screen(dict(state))


def test_b36d_i_the_screen_reports_the_leaving_answer() -> None:
    """(d) (i) At (a)'s state as a trial (`S4.T = S5.T = 300 K`, `S2` flowing at 352.005 K) the
    v2 screen reports `U-PHF2` `VAPOR`, equal to (a)'s leaving answer at the same state."""
    flowsheet, split, _, state, ph_units, temperatures = _ch_up_opening()
    reported = _screened(ph_units)
    assert reported == (("U-PHF", "TWO_PHASE"), ("U-PHF2", "VAPOR"))
    answer = _contract_kernel(
        flowsheet.provider,
        flowsheet.context,
        split,
        state,
        ph_units,
        v2=True,
        regime="ZERO_FLOW",
        temperatures=temperatures,
    )
    assert dict(reported)["U-PHF2"] == answer.regime


def test_b36d_i_control_the_pre_ruling_screen_reports_another_regime() -> None:
    """(d) (i)'s control: the pre-ruling screen flashed a leaving split at its own `T` column
    (300 K here). With no PH-type unit the screen still does exactly that, and on this trial
    nothing else differs (`U-PHF` is `TWO_PHASE`, reported without a flash): it does not report
    `VAPOR`."""
    reported = _screened(frozenset())
    assert dict(reported)["U-PHF"] == "TWO_PHASE"
    assert dict(reported)["U-PHF2"] != "VAPOR", reported


@cache
def _ch_up_operations() -> dict[str, Any]:
    """The keyword arguments of CH-UP's attempt-0 operations (`U-PHF` `LIQUID`, `U-PHF2`
    `ZERO_FLOW`)."""
    caught: list[dict[str, Any]] = []
    real = region_module._LiftedOps.__init__

    def spy(self: Any, **kwargs: Any) -> None:
        caught.append(kwargs)
        real(self, **kwargs)

    document, start = CASES["CH-UP"]()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(region_module._LiftedOps, "__init__", spy)
        solve_from_v2(bind(document), start)
    given = caught[0]
    assert dict(given["regimes"]) == {"U-PHF": "LIQUID", "U-PHF2": "ZERO_FLOW"}
    return given


def _leaving_candidate(reported: str) -> tuple[Any, Candidate]:
    """(a)'s state as a candidate of an attempt of CH-UP's region with `U-PHF` `TWO_PHASE` and
    `U-PHF2` `ZERO_FLOW` — the operations of CH-UP's attempt 0 with those regimes — on which only
    `U-PHF2` is reported changed, as `reported`. (In CH-UP's own attempt 0 `U-PHF` is `LIQUID`, its
    vapour product pinned, so `U-PHF2`'s feed is dormant at every candidate: the leaving answer
    at a candidate needs the upstream flash already two-phase in the attempt.)"""
    _, _, _, state, _, _ = _ch_up_opening()
    given = {**_ch_up_operations(), "regimes": TRIAL_REGIMES, "end_state": state}
    ops = region_module._LiftedOps(**given)
    candidate = Candidate(
        iteration=0,
        halving=1,
        alpha=0.5,
        x=np.array([state[name] for name in given["free"]]),
        signature=(("U-PHF", "TWO_PHASE"), ("U-PHF2", reported)),  # type: ignore[arg-type]
    )
    return ops, candidate


def test_b36d_ii_a_leaving_answer_that_differs_from_the_report_raises() -> None:
    """(d) (ii) The reported regime stubbed (`LIQUID`, the pre-ruling screen's report of a stale
    label): `at_candidate` raises the N4 `RuntimeError` although the leaving answer is recorded
    `tp` — which the exemption covered before Q-S15 (3)."""
    ops, candidate = _leaving_candidate("LIQUID")
    split = next(entry for entry in ops._splits if entry.unit == "U-PHF2")
    state = dict(ops._end)
    state.update(zip(ops._free, (float(v) for v in candidate.x), strict=True))
    answer = ops._answer(split, state)
    assert (answer.regime, answer.fallback) == ("VAPOR", "tp")
    with pytest.raises(RuntimeError) as raised:
        ops.at_candidate(candidate, "stub")
    assert str(raised.value).startswith(
        "defect: the kernel reports U-PHF2 VAPOR at the candidate the screen reported LIQUID"
    ), raised.value


def test_b36d_ii_control_the_matching_report_opens_the_answer() -> None:
    """(d) (ii)'s control: the same candidate reported `VAPOR` opens `U-PHF2` `VAPOR`, recorded
    `fallback(U-PHF2, tp)` — the raise is the disagreement's."""
    ops, candidate = _leaving_candidate("VAPOR")
    conversion = ops.at_candidate(candidate, "stub")
    assert dict(conversion.signature)["U-PHF2"] == "VAPOR"
    assert ("U-PHF2", "tp") in conversion.fallbacks
