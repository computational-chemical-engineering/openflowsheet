"""T05b B34: every kernel answer at a phase-rejected candidate is taken at the candidate (spec
§7.8 (ii) 5, ruling Q-S12, 2026-09-25; re-review M2).

T03 §4.5 opens a restart at "the candidate's full state, each changed unit's split from the kernel
*there*". Before the ruling `_LiftedOps.at_candidate` asked the changed units in turn and wrote each
answer before asking the next, so a downstream flash whose feed an upstream answer had rewritten
was asked at a state the screen never saw, and review N4's guard raised an untyped
`RuntimeError: defect: the kernel reports U-PHF2 VAPOR at the candidate the screen reported
TWO_PHASE` — 15 of the 104 solved runs of the sweep below, all with `U-PHF` declared first
(re-review P10, P11; present before W9). Now every changed unit is asked at the unmodified
candidate, each regime checked there, and only then are the answers written (disjoint columns);
the opening's fixed point then settles dormancy.

- (a) The sweep (re-review P10, registered): CH-UP's flowsheet with `U-PHF2`'s duty
  `Q2 ∈ {0, −3 000, +3 000}` W; every ordered pair `(Q_s, Q_t)` of distinct `U-PHF` duties in
  `{0, 30 000, 90 000, 115 000, 125 000}` W; start `initial_state` at `(Q_s, Q2)`, target
  `(Q_t, Q2)`; both declaration orders — 120 runs, the 16 with `Q2 ≠ 0` and `Q_s = 0` a start that
  refuses (`duty_into_dormant_stream`). No solved run raises; both orders agree on the outcome
  and, when `CONVERGED`, on the final regimes and the final state within §13's EO allowances.
  The outcome counts and the certificate tally of the `CONVERGED` runs are regression values,
  re-registered after B36 (Q-S15 (1)), the tally again by T06 A92 (the saturation closure, T06
  spec §8.8); both orders agree on each run's verification status.
- (b) At the function level, at P11's candidate (`U-PHF` and `U-PHF2` both `VAPOR → TWO_PHASE`
  going 125 kW → 90 kW at `Q2 = 0`): `U-PHF2`'s kernel is asked with `S2` bitwise the
  candidate's; the opening is bitwise the same with the two units listed in either order; the
  pre-ruling loop on the same candidate raises P11's `RuntimeError` (the control).
- (c) Inertness is the protocol's (SYN-001's identity, T02's floats, the `t05` and `t05b` keys,
  the K05 identity, B07): unchanged on the rule's own commit.
"""

from __future__ import annotations

import dataclasses
import itertools
from collections import Counter
from functools import cache
from typing import Any

import pytest
from t05_w12_support import bind, duty_pin, planned_step
from t05b_support import (
    P_R,
    POLICY_V2,
    REF,
    Document,
    Link,
    Product,
    Source,
    instance,
    revision,
    solve_from_v2,
)

from openflowsheet.orchestrator import region as region_module
from openflowsheet.orchestrator.phase_contract import Candidate
from openflowsheet.orchestrator.region import RegionResult
from openflowsheet.orchestrator.revision import InitialStateFailure, initial_state
from openflowsheet.verify import NEAR_THRESHOLD_MARGIN
from openflowsheet.verify.certificate import CheckPolicy, SolutionCertificate, verify_revision

FEED = (1.0, 1.0, 1.0)
DUTIES = (0.0, 30_000.0, 90_000.0, 115_000.0, 125_000.0)
DOWNSTREAM_DUTIES = (0.0, -3_000.0, 3_000.0)
#: Spec §13's EO allowances (T02 §6.4), as `ref.tolerances.coupled_allowances` states them.
ALLOWANCE: dict[str, float] = {
    kind: float(value) for kind, value in REF["tolerances"]["coupled_allowances"].items()
}


def _allowance(column: str) -> float:
    kind = column.rsplit(".", 1)[-1]
    return {"T": ALLOWANCE["T"], "P": ALLOWANCE["P"], "Q": ALLOWANCE["duty"]}.get(
        kind, ALLOWANCE["flow"]
    )


def chain(duty: float, downstream: float, *, phf2_first: bool) -> Document:
    """CH-UP's flowsheet (spec B31): feed `(1,1,1)` 300 K → `U-PHF` (`Q = duty`) → `S2` vap →
    `U-PHF2` (`Q = downstream`) → `S4` vap, `S5` liq; `S3` liq → sink."""
    phf = instance("SYN-001-UL-C1", "U-PHF")
    phf2 = instance("SYN-001-UL-C1", "U-PHF", "U-PHF2")
    return revision(
        f"B34-{duty:g}-{downstream:g}" + ("-phf2-first" if phf2_first else ""),
        [phf2, phf] if phf2_first else [phf, phf2],
        [Source("S1", "U-PHF", "inlet", "liquid", FEED, 300.0, P_R)],
        [Link("S2", ("U-PHF", "vapor"), ("U-PHF2", "inlet"), "vapor")],
        [
            Product("S3", ("U-PHF", "liquid"), "liquid"),
            Product("S4", ("U-PHF2", "vapor"), "vapor"),
            Product("S5", ("U-PHF2", "liquid"), "liquid"),
        ],
        [
            duty_pin("SPEC-phf-Q", "U-PHF", duty),
            duty_pin("SPEC-phf2-Q", "U-PHF2", downstream),
        ],
    )


def _start(duty: float, downstream: float, phf2_first: bool) -> Any:
    binding = bind(chain(duty, downstream, phf2_first=phf2_first))
    return initial_state(binding.flowsheet, binding.spec.variable_ids)


# ------------------------------------------------------------------------------ (a) the sweep

#: `(Q2, Q_s, Q_t, phf2_first)`, the sweep's 120 runs.
RUNS = tuple(
    (downstream, source, target, first)
    for downstream in DOWNSTREAM_DUTIES
    for source, target in itertools.permutations(DUTIES, 2)
    for first in (False, True)
)


@cache
def sweep() -> dict[tuple[float, float, float, bool], RegionResult | InitialStateFailure]:
    """Each run's region result, or its start's refusal; an exception propagates (none may)."""
    results: dict[tuple[float, float, float, bool], RegionResult | InitialStateFailure] = {}
    for downstream, source, target, first in RUNS:
        start = _start(source, downstream, first)
        if isinstance(start, InitialStateFailure):
            results[downstream, source, target, first] = start
            continue
        assert isinstance(start, dict), start
        results[downstream, source, target, first] = solve_from_v2(
            bind(chain(target, downstream, phf2_first=first)), start
        )
    return results


def test_b34a_no_solved_run_raises_and_the_refusals_are_the_dormant_duty_starts() -> None:
    """(a) 120 runs: the 16 with `Q2 ≠ 0` and `Q_s = 0` refuse at the start
    (`duty_into_dormant_stream` at `U-PHF2`, asserted as that refusal); the other 104 solve, and
    each ends in a typed outcome (an exception would propagate out of `sweep`)."""
    results = sweep()
    assert len(results) == 120
    refused = {key: r for key, r in results.items() if isinstance(r, InitialStateFailure)}
    assert set(refused) == {key for key in RUNS if key[0] != 0.0 and key[1] == 0.0}
    assert len(refused) == 16
    assert all(
        (r.unit, r.code.splitlines()[0]) == ("U-PHF2", "duty_into_dormant_stream")
        for r in refused.values()
    ), set(refused.values())
    solved = [r for r in results.values() if isinstance(r, RegionResult)]
    assert len(solved) == 104
    assert all(isinstance(r.outcome, str) and r.outcome for r in solved)


def _final_regimes(result: RegionResult) -> frozenset[tuple[str, str]]:
    return frozenset(tuple(entry) for entry in result.attempts[-1].signature)


def test_b34a_both_declaration_orders_agree() -> None:
    """(a) For every `(Q2, Q_s, Q_t)` both declaration orders end with the same outcome and, when
    `CONVERGED`, the same final regimes (as a set of `(unit, regime)`) and the same final state
    within §13's EO allowances."""
    results = sweep()
    differing = []
    for downstream, source, target in {key[:3] for key in RUNS}:
        first = results[downstream, source, target, False]
        variant = results[downstream, source, target, True]
        if isinstance(first, InitialStateFailure) or isinstance(variant, InitialStateFailure):
            assert first == variant
            continue
        if first.outcome != variant.outcome:
            differing.append((downstream, source, target, first.outcome, variant.outcome))
            continue
        if first.outcome != "CONVERGED":
            continue
        assert _final_regimes(first) == _final_regimes(variant), (downstream, source, target)
        assert set(first.state) == set(variant.state)
        for column, value in first.state.items():
            got = variant.state[column]
            assert abs(got - value) <= _allowance(column), (
                (downstream, source, target),
                column,
                got,
                value,
            )
    assert differing == []


#: *Regression*, re-registered 2026-09-25 (Q-S15 (1), spec B34 (a)); 80/12/6/4/2 at ruling. B36
#: (the leaving flash at the feed's `T`, Q-S14) moved the sweep's leaving runs — `Q2 = 0`,
#: `Q_s = 0`, both orders, 8 runs — which B36 (c) as completed by Q-S15 (1) lists:
#: `(0, 0, 115 kW)` goes from `ACTIVE_SET_CYCLING` to `CONVERGED` in both orders; the others move
#: only their records (attempt counts at 90 and 125 kW; at 90 kW `U-PHF2`'s final regime
#: `TWO_PHASE` → `VAPOR`, a dew-point regression value, B31 (b)).
OUTCOMES = {
    "CONVERGED": 82,
    "ACTIVE_SET_CYCLING": 10,
    "SPECIFICATION_CONFLICT": 6,
    "STAGNATION": 4,
    "BOUND_BLOCKED": 2,
}


def _counts() -> dict[str, int]:
    return dict(Counter(r.outcome for r in sweep().values() if isinstance(r, RegionResult)))


def test_b34a_the_outcome_counts() -> None:
    assert _counts() == OUTCOMES


@cache
def certificates() -> dict[tuple[float, float, float, bool], SolutionCertificate]:
    """`verify_revision` on every `CONVERGED` run of the sweep, at its final state."""
    certified: dict[tuple[float, float, float, bool], SolutionCertificate] = {}
    for key, result in sweep().items():
        if not isinstance(result, RegionResult) or result.outcome != "CONVERGED":
            continue
        downstream, _, target, first = key
        document = chain(target, downstream, phf2_first=first)
        binding = bind(document)
        certified[key] = verify_revision(
            binding,
            document,
            result,
            state=dict(result.state),
            solve_plan=planned_step(binding, POLICY_V2).solve_plan,
        )
    return certified


#: *Regression* (spec B34 (a), Q-S15 (1); measured at `8427abd`; **re-registered by T06 A92**
#: after T06 spec §8.8's saturation closure, measured at W19): the certificate tally of the
#: sweep's `CONVERGED` runs, and the regularity statuses of its `UNVERIFIED` ones. Before §8.8 it
#: was 66 / 10 (6 `RANK_DEFICIENT`, 4 `ILL_CONDITIONED`) / 6: four of the `RANK_DEFICIENT` runs
#: are false two-phase labels the vacuous `Σ(v/V) − Σ(l/L)` passed, now `FAILED` on their
#: closure (`MOVED_BY_CLOSURE`).
TALLY = {"VERIFIED": 66, "UNVERIFIED": 6, "FAILED": 10}
UNVERIFIED_REGULARITY = {"RANK_DEFICIENT": 2, "ILL_CONDITIONED": 4}
#: The six `FAILED` before §8.8: `(0, Q_s, 30 kW)` for `Q_s` ∈ {90, 115, 125} kW, both orders —
#: §17's dew-point singularity acting on the solve (`U-PHF2` ends `TWO_PHASE` off its dew-point
#: root).
FAILED_BEFORE_CLOSURE = frozenset(
    (0.0, source, 30_000.0, first)
    for source in (90_000.0, 115_000.0, 125_000.0)
    for first in (False, True)
)
#: T06 A92: `(0, Q_s, 90 kW)` for `Q_s` ∈ {115, 125} kW, both orders — `U-PHF2.S2` labelled
#: `TWO_PHASE` 30.70 K and 23.78 K off saturation (§8.8's value in kelvin, measured at W19 on
#: `ref-x86-64`). The values are *recorded*, not asserted (A92 (A5)): only the keys are.
MOVED_BY_CLOSURE = {
    (0.0, source, 90_000.0, first): kelvin
    for source, kelvin in ((115_000.0, 30.69953770685356), (125_000.0, 23.77737323355069))
    for first in (False, True)
}
FAILED = FAILED_BEFORE_CLOSURE | frozenset(MOVED_BY_CLOSURE)
#: T06 A92 (A5): every `FAILED` dew-point state fails its closure by at least `100 τ_T` (1e-4 K),
#: a decade beyond K04's near-threshold band `(τ_T/10, 10 τ_T]` (ADR 0007 D2.4's margin of ten), so
#: a closure that shrank tenfold on another machine would still not be a near-threshold call.
#: Computed from the verifier's constant and the check policy's temperature tolerance, never typed.
#: *Measured (A5):* the ten at 9.494e-4 (×2), 3.209e-2 (×2), 3.331e-2 (×2), 23.78 (×2) and
#: 30.70 (×2) K; the minimum is 9.49× the floor.
TAU_T = CheckPolicy().tolerances["temperature"]
DEW_POINT_CLOSURE_FLOOR = NEAR_THRESHOLD_MARGIN**2 * TAU_T


def beyond_the_floor(closure: float) -> bool:
    """A92 (A5)'s bound on a `FAILED` dew-point state's closure, in kelvin."""
    return closure >= DEW_POINT_CLOSURE_FLOOR


def test_a92_the_floor_is_a_decade_beyond_the_near_threshold_band() -> None:
    """A92 (A5): a closure of 5e-4 K (500 `τ_T`) is beyond the floor; 5e-5 K (50 `τ_T`, above
    K04's band but inside a tenfold shrink of it) is not."""
    assert beyond_the_floor(5e-4)
    assert not beyond_the_floor(5e-5)
    assert DEW_POINT_CLOSURE_FLOOR > TAU_T * NEAR_THRESHOLD_MARGIN


def test_b34a_the_certificate_tally() -> None:
    """(a) 66 `VERIFIED`, 6 `UNVERIFIED` (2 `RANK_DEFICIENT`, 4 `ILL_CONDITIONED`), 10 `FAILED`.
    Each `FAILED` is a false success the verifier catches (`false_success_detected`) and fails
    `phase_admissibility.U-PHF2.S2.closure` (T06 §8.8) by `100 τ_T` or more (A92 (A5)), and every
    non-`VERIFIED` run has `Q2 = 0` and `Q_t` ∈ {30, 90} kW, where `U-PHF2` is fed a saturated
    vapour: a `FAILED` without `false_success_detected`, or a `VERIFIED` inside that set, stops
    the build lane."""
    certified = certificates()
    assert len(certified) == OUTCOMES["CONVERGED"]
    assert dict(Counter(c.verification_status for c in certified.values())) == TALLY
    regularity = Counter(
        None if c.regularity is None else c.regularity.status
        for c in certified.values()
        if c.verification_status == "UNVERIFIED"
    )
    assert dict(regularity) == UNVERIFIED_REGULARITY
    failed = {key for key, c in certified.items() if c.verification_status == "FAILED"}
    assert failed == FAILED
    assert all(certified[key].false_success_detected for key in failed)
    for key in failed:
        (closure,) = (
            check
            for check in certified[key].checks
            if check.id == "phase_admissibility.U-PHF2.S2.closure"
        )
        assert closure.result == "fail", key
        assert closure.tolerance == TAU_T, key
        assert closure.value is not None and beyond_the_floor(closure.value), key
        if key in MOVED_BY_CLOSURE:
            # Where these two false successes land is machine-dependent (a state beside a singular
            # dew point; ADR 0007): the reference machine measured `MOVED_BY_CLOSURE`, both CI
            # runners (x86-64 and aarch64) land (0, 125 kW, 90 kW) 16.16 K from saturation
            # (CI 36270210365, bbabf9a). The value is recorded, not asserted; what is asserted on
            # every machine is the verdict: `FAILED`, by at least the floor (above), on the closure
            # alone (below).
            # The closure alone moved them: every other check passes or does not apply.
            failing = [check.id for check in certified[key].checks if check.result == "fail"]
            assert failing == [closure.id], key
    dew_point = {key for key in certified if key[0] == 0.0 and key[2] in (30_000.0, 90_000.0)}
    verified = {key for key, c in certified.items() if c.verification_status == "VERIFIED"}
    assert set(certified) - verified == dew_point, sorted(dew_point & verified)


def test_b34a_both_declaration_orders_agree_on_the_certificate() -> None:
    """(a) Each `(Q2, Q_s, Q_t)` gets the same verification status in both declaration orders
    (both converge or neither does: `test_b34a_both_declaration_orders_agree`)."""
    certified = certificates()
    differing = []
    for triple in sorted({key[:3] for key in certified}):
        first, variant = certified[(*triple, False)], certified[(*triple, True)]
        if first.verification_status != variant.verification_status:
            differing.append((triple, first.verification_status, variant.verification_status))
    assert differing == []


# ------------------------------------------------------------- (b) at the function level


class _StopError(Exception):
    """Ends the solve at the candidate (b) examines, with the region's state as it was there."""


@dataclasses.dataclass(frozen=True)
class Caught:
    ops: Any
    candidate: Candidate
    cause: str


@cache
def p11_candidate() -> Caught:
    """P11's candidate: `U-PHF` declared first, `Q2 = 0`, the start at 125 kW (both flashes
    `VAPOR`), the target at 90 kW; the first candidate reporting both units changed."""
    caught: list[Caught] = []
    real = region_module._LiftedOps.at_candidate

    def spy(self: Any, candidate: Candidate, cause: str) -> Any:
        changed = [
            unit
            for unit, regime in candidate.signature
            if self._regimes.get(unit, regime) != regime
        ]
        if changed == ["U-PHF", "U-PHF2"]:
            caught.append(Caught(self, candidate, cause))
            raise _StopError
        return real(self, candidate, cause)

    start = _start(125_000.0, 0.0, False)
    assert isinstance(start, dict), start
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(region_module._LiftedOps, "at_candidate", spy)
        with pytest.raises(_StopError):
            solve_from_v2(bind(chain(90_000.0, 0.0, phf2_first=False)), start)
    (found,) = caught
    assert dict(found.candidate.signature) == {"U-PHF": "TWO_PHASE", "U-PHF2": "TWO_PHASE"}
    assert found.ops._regimes == {"U-PHF": "VAPOR", "U-PHF2": "VAPOR"}
    return found


def _candidate_state(caught: Caught) -> dict[str, float]:
    state = dict(caught.ops._end)
    state.update(zip(caught.ops._free, (float(v) for v in caught.candidate.x), strict=True))
    return state


def _feed(state: dict[str, float]) -> dict[str, float]:
    return {name: value for name, value in state.items() if name.startswith("S2.")}


def test_b34b_the_downstream_kernel_is_asked_at_the_candidate() -> None:
    """(b) `U-PHF2`'s kernel is asked with `S2`'s columns bitwise the candidate's, although
    `U-PHF`'s answer rewrites them."""
    caught = p11_candidate()
    asked: dict[str, dict[str, float]] = {}
    real = caught.ops._answer

    def answer(split: Any, state: Any) -> Any:
        asked[split.unit] = _feed(dict(state))
        return real(split, state)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(caught.ops, "_answer", answer)
        conversion = caught.ops.at_candidate(caught.candidate, caught.cause)
    at = _feed(_candidate_state(caught))
    assert set(asked) == {"U-PHF", "U-PHF2"}
    assert asked["U-PHF2"] == at and all(
        repr(asked["U-PHF2"][name]) == repr(value) for name, value in at.items()
    )
    opened, _ = conversion.opening
    assert _feed(opened) != at  # `U-PHF`'s answer did rewrite `U-PHF2`'s feed


def test_b34b_the_opening_does_not_depend_on_the_listing_order() -> None:
    """(b) The conversion's opening is bitwise the same with the two units listed in either
    order."""
    caught = p11_candidate()
    listed = caught.candidate
    swapped = dataclasses.replace(listed, signature=tuple(reversed(listed.signature)))
    assert [unit for unit, _ in swapped.signature] == ["U-PHF2", "U-PHF"]
    one = caught.ops.at_candidate(listed, caught.cause)
    other = caught.ops.at_candidate(swapped, caught.cause)
    (state_one, regimes_one), (state_other, regimes_other) = one.opening, other.opening
    assert one.signature == other.signature
    assert regimes_one == regimes_other
    assert list(state_one) == list(state_other)
    assert all(repr(state_one[name]) == repr(state_other[name]) for name in state_one)


def _pre_ruling(caught: Caught) -> None:
    """The loop `at_candidate` ran before Q-S12: each changed unit asked, checked and written in
    turn (the N4 guard as it was)."""
    ops, candidate = caught.ops, caught.candidate
    opened = _candidate_state(caught)
    for unit, regime in candidate.signature:
        if unit in ops._regimes and regime != ops._regimes[unit]:
            split = next(entry for entry in ops._splits if entry.unit == unit)
            answer = ops._answer(split, opened)
            sanctioned = split.unit in ops._ph_units and answer.fallback == "tp"
            if answer.regime != regime and not sanctioned:
                raise RuntimeError(
                    f"defect: the kernel reports {unit} {answer.regime} at the candidate the "
                    f"screen reported {regime} at (iteration {candidate.iteration}, halving "
                    f"{candidate.halving})"
                )
            opened.update(answer.values)


def test_b34b_control_the_pre_ruling_loop_raises_at_this_candidate() -> None:
    """(b)'s control: the answers written in turn, on the same candidate, reach P11's defect —
    `U-PHF2` asked at `U-PHF`'s rewritten `S2` answers `VAPOR`."""
    caught = p11_candidate()
    with pytest.raises(RuntimeError) as raised:
        _pre_ruling(caught)
    assert str(raised.value).startswith(
        "defect: the kernel reports U-PHF2 VAPOR at the candidate the screen reported TWO_PHASE"
    )
