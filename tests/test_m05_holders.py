"""M05 WO-3: the `ExternalFunction` holder contract (design note §6.3; ADR 0038 D5; R-262), in
the default gate — the holder imports neither Pyomo nor a truth, so every rule is checked here on
plain boxes; `tests/test_m05_trf.py` checks the same rules through a TRF run (`nlp`).
"""

from __future__ import annotations

import copy
import math
import threading
import time
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest

from openflowsheet.compile.spec import DomainError
from openflowsheet.studies.trust_region.holders import (
    TRF_PMP_VALUE,
    TRF_START_VALUE,
    TRF_TRIAL_VALUE,
    BoxValues,
    ColdBudget,
    EFHolder,
    PropertyBlockBox,
    RunState,
    TruthBox,
    TruthRefused,
)


class CountingBox:
    """Two outputs of two inputs: (a·b, a − b), Jacobian ((b, a), (1, −1))."""

    n_in = 2
    n_out = 2

    def __init__(self, delay: float = 0.0, poison: float | None = None) -> None:
        self.value_calls = 0
        self.jacobian_calls = 0
        self.delay = delay
        self.poison = poison
        self._lock = threading.Lock()

    def values(self, inputs: tuple[float, ...]) -> BoxValues:
        with self._lock:
            self.value_calls += 1
        time.sleep(self.delay)
        a, b = inputs
        if self.poison is not None and a == self.poison:
            return BoxValues((math.nan, a - b))
        return BoxValues((a * b, a - b))

    def jacobian(self, inputs: tuple[float, ...]) -> tuple[tuple[float, ...], ...]:
        self.jacobian_calls += 1
        a, b = inputs
        if self.poison is not None and a == self.poison:
            return ((math.inf, a), (1.0, -1.0))
        return ((b, a), (1.0, -1.0))


def holder(box: Any = None, scales: Sequence[float] = (1.0, 1.0)) -> EFHolder:
    return EFHolder("box", box if box is not None else CountingBox(), scales, kind="truth")


# -- identity under TRF's clone (probe P2′) -------------------------------------------------------


def test_deepcopy_returns_the_holder_itself_and_its_callbacks_survive_a_deepcopy() -> None:
    h = holder()
    value, gradient = h.value_callback(0), h.gradient_callback(0)
    assert copy.deepcopy(h) is h
    assert copy.copy(h) is h
    copied = copy.deepcopy({"value": value, "gradient": gradient, "owner": h})
    assert copied["value"] is value and copied["gradient"] is gradient and copied["owner"] is h
    copied["value"](2.0, 3.0)
    assert h.summary()["value_cold"] == 1


# -- the exact-key memo ---------------------------------------------------------------------------


def test_a_repeated_key_is_a_memo_hit_and_the_box_is_called_once() -> None:
    box = CountingBox()
    h = holder(box)
    assert h.request_values((2.0, 3.0)) == (6.0, -1.0)
    assert h.request_values([2.0, 3.0, 99.0]) == (6.0, -1.0)  # only the first n_in are the key
    assert box.value_calls == 1
    assert [entry.served for entry in h.ledger] == ["cold", "memo_hit"]


def test_the_key_is_exact_binary64_not_quantized() -> None:
    box = CountingBox()
    h = holder(box)
    h.request_values((2.0, 3.0))
    h.request_values((math.nextafter(2.0, 3.0), 3.0))
    assert box.value_calls == 2


def test_signed_zeros_are_one_key() -> None:
    """ADR 0001 D1.5: −0.0 and +0.0 are the same state."""
    box = CountingBox()
    h = holder(box)
    h.request_values((0.0, 1.0))
    h.request_values((-0.0, 1.0))
    assert box.value_calls == 1


def test_the_callbacks_divide_by_the_power_of_two_scale_exactly() -> None:
    h = holder(scales=(8.0, 0.5))
    assert h.value_callback(0)(3.0, 5.0) == 15.0 / 8.0
    assert h.value_callback(1)(3.0, 5.0) == -2.0 / 0.5
    assert h.gradient_callback(0)([3.0, 5.0], None) == [5.0 / 8.0, 3.0 / 8.0]
    assert h.gradient_callback(1)([3.0, 5.0], None) == [2.0, -2.0]
    assert isinstance(h.gradient_callback(1)([3.0, 5.0], None), list)  # Pyomo appends to it


def test_jacobians_are_memoized_separately_from_values() -> None:
    box = CountingBox()
    h = holder(box)
    h.request_values((1.0, 2.0))
    h.request_jacobian((1.0, 2.0))
    h.request_jacobian((1.0, 2.0))
    assert (box.value_calls, box.jacobian_calls) == (1, 1)
    summary = h.summary()
    assert (summary["jacobian_cold"], summary["jacobian_memo_hit"]) == (1, 1)


def test_concurrent_requests_at_one_key_evaluate_it_once() -> None:
    """§6.3 threading: one lock guards the memo and the ledger; a second request waits for the
    first's evaluation instead of repeating it."""
    box = CountingBox(delay=0.05)
    h = holder(box)
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(lambda _: h.request_values((4.0, 5.0)), range(8)))
    assert results == [(20.0, -1.0)] * 8
    assert box.value_calls == 1
    summary = h.summary()
    assert (summary["value_cold"], summary["value_memo_hit"]) == (1, 7)


# -- never a non-finite value (probe P7) ----------------------------------------------------------


def test_a_non_finite_output_is_refused_and_remembered() -> None:
    box = CountingBox(poison=7.0)
    h = holder(box)
    with pytest.raises(TruthRefused) as refused:
        h.request_values((7.0, 1.0))
    assert refused.value.code == "non_finite_output:box"
    with pytest.raises(TruthRefused):
        h.value_callback(1)(7.0, 1.0)  # the finite output of the same refused evaluation
    assert box.value_calls == 1
    assert [entry.served for entry in h.ledger] == ["cold", "memo_hit"]
    assert all(entry.status == "non_finite_output:box" for entry in h.ledger)
    assert [r.code for r in h.refusals] == ["non_finite_output:box"]


def test_a_non_finite_jacobian_is_refused() -> None:
    h = holder(CountingBox(poison=7.0))
    with pytest.raises(TruthRefused, match="non_finite_output:box"):
        h.request_jacobian((7.0, 1.0))


def test_a_non_finite_input_is_refused_before_the_box_is_called() -> None:
    box = CountingBox()
    h = holder(box)
    with pytest.raises(TruthRefused) as refused:
        h.request_values((math.nan, 1.0))
    assert refused.value.status == "non_finite_input"
    assert box.value_calls == 0


# -- typed refusals -------------------------------------------------------------------------------


class Block:
    block_id = "blk"
    input_ids = ("u", "v")
    output_ids = ("p", "q")

    def jacobian_pattern(self) -> tuple[tuple[int, int], ...]:
        return ((0, 0), (1, 1))

    def values(self, inputs: Sequence[float]) -> Sequence[float]:
        if inputs[0] < 0.0:
            raise DomainError("u below its domain")
        return [2.0 * inputs[0], 3.0 * inputs[1]]

    def jacobian(self, inputs: Sequence[float]) -> Sequence[tuple[int, int, float]]:
        if inputs[0] < 0.0:
            raise DomainError("u below its domain")
        return [(0, 0, 2.0), (1, 1, 3.0)]


def test_a_property_domain_error_is_a_typed_refusal() -> None:
    h = EFHolder("block:blk", PropertyBlockBox(Block()), (1.0, 1.0), kind="property_block")
    with pytest.raises(TruthRefused) as refused:
        h.request_values((-1.0, 1.0))
    assert (refused.value.status, refused.value.reason) == ("property_domain_error", "blk")
    assert "u below its domain" in refused.value.detail
    with pytest.raises(TruthRefused, match="property_domain_error:blk"):
        h.request_jacobian((-1.0, 1.0))


def test_a_property_block_jacobian_is_densified_from_its_declared_triples() -> None:
    box = PropertyBlockBox(Block())
    assert box.jacobian((1.0, 1.0)) == ((2.0, 0.0), (0.0, 3.0))


class FakeTruth:
    def __init__(self, meta: Mapping[str, Any]) -> None:
        self.meta = meta

    def describe(self) -> Mapping[str, Any]:
        return {"kind": "synthetic", "id": "fake-truth", "sha256": "0" * 64}

    def evaluate(self, inlet: Sequence[float]) -> tuple[float, float, Mapping[str, Any]]:
        return 0.1, 80.0, self.meta

    def gradient(self, inlet: Sequence[float]) -> Sequence[Sequence[float]]:
        return [[0.0] * 7, [1.0] * 7]


def test_a_truth_status_other_than_ok_is_a_refusal_with_that_status() -> None:
    truth = FakeTruth({"status": "out_of_domain"})
    h = EFHolder("link:R", TruthBox(truth), (1.0, 128.0), kind="truth")
    with pytest.raises(TruthRefused) as refused:
        h.request_values((1.0,) * 7)
    assert refused.value.code == "out_of_domain:fake-truth"


def test_a_store_served_truth_value_is_a_store_hit() -> None:
    truth = FakeTruth({"status": "ok", "cache_hit": True})
    h = EFHolder("link:R", TruthBox(truth), (1.0, 128.0), kind="truth")
    assert h.request_values((1.0,) * 7) == (0.1, 80.0)
    assert [entry.served for entry in h.ledger] == ["store_hit"]


# -- the budget -----------------------------------------------------------------------------------


def test_a_cap_is_never_exceeded_and_its_refusal_is_not_a_request() -> None:
    """G7's mechanism: exactly `cap` cold requests, then `budget:budget_exhausted`; memo hits are
    free; the refused admission is a refusal, not a ledger entry."""
    box = CountingBox()
    h = holder(box)
    run_cap, study_cap = ColdBudget("run", 2), ColdBudget("study", 10)
    h.begin_run(RunState("r"), (run_cap, study_cap))
    h.request_values((1.0, 1.0))
    h.request_values((2.0, 1.0))
    h.request_values((1.0, 1.0))
    with pytest.raises(TruthRefused) as refused:
        h.request_values((3.0, 1.0))
    assert refused.value.code == "budget:budget_exhausted"
    assert (run_cap.used, study_cap.used, box.value_calls) == (2, 2, 2)
    summary = h.summary()
    assert (summary["value_cold"], summary["value_memo_hit"]) == (2, 1)
    assert len(h.ledger) == 3
    assert [r.code for r in h.refusals] == ["budget:budget_exhausted"]
    with pytest.raises(TruthRefused):  # the key was not remembered as refused: still no room
        h.request_values((3.0, 1.0))
    assert box.value_calls == 2


def test_one_budget_is_shared_by_every_holder_given_it() -> None:
    shared = ColdBudget("study", 3)
    first, second = holder(CountingBox()), holder(CountingBox())
    first.begin_run(RunState("r"), (shared,))
    second.begin_run(RunState("r"), (shared,))
    first.request_values((1.0, 1.0))
    second.request_values((1.0, 1.0))
    first.request_values((2.0, 1.0))
    with pytest.raises(TruthRefused, match="budget:budget_exhausted"):
        second.request_values((2.0, 1.0))
    assert shared.used == 3


def test_jacobians_are_not_charged_to_a_budget() -> None:
    h = holder()
    cap = ColdBudget("run", 1)
    h.begin_run(RunState("r"), (cap,))
    h.request_values((1.0, 1.0))
    h.request_jacobian((1.0, 1.0))
    h.request_jacobian((2.0, 1.0))
    assert cap.used == 1


def test_a_negative_cap_is_refused() -> None:
    with pytest.raises(ValueError):
        ColdBudget("run", -1)


# -- the ledger and TRF's call order (design note §8.3) -------------------------------------------


def test_the_first_request_at_each_key_gets_its_call_order_purpose() -> None:
    h = holder()
    run = RunState("trf-1")
    h.begin_run(run)
    h.request_values((2.0, 1.0))  # EFReplacement: the start value
    h.request_values((2.0, 1.0))  # the same key again: a memo hit, no purpose
    h.request_values((1.5, 1.0))  # the PMP point
    h.request_jacobian((1.5, 1.0))
    run.last_logged_iteration = 0
    h.request_values((1.4, 1.0))  # iteration 1's trial point
    run.last_logged_iteration = 1
    h.request_values((1.4, 1.0))  # the accepted iterate again
    h.request_values((1.3, 1.0), purpose="trf_fd_point")
    rows = [(e.call, e.served, e.purpose, e.trf_iteration) for e in h.ledger]
    assert rows == [
        ("value", "cold", TRF_START_VALUE, 0),
        ("value", "memo_hit", None, 0),
        ("value", "cold", TRF_PMP_VALUE, 0),
        ("jacobian", "cold", None, 0),
        ("value", "cold", TRF_TRIAL_VALUE, 1),
        ("value", "memo_hit", None, 2),
        ("value", "cold", "trf_fd_point", 2),
    ]
    assert {e.run_id for e in h.ledger} == {"trf-1"}
    assert [e.seq for e in h.ledger] == list(range(7))


def test_a_holder_serves_one_run_at_a_time() -> None:
    h = holder()
    h.begin_run(RunState("a"))
    with pytest.raises(RuntimeError, match="already serves"):
        h.begin_run(RunState("b"))
    h.end_run()
    h.begin_run(RunState("b"))


def test_requests_outside_a_run_carry_no_run_and_no_purpose() -> None:
    h = holder()
    h.request_values((1.0, 1.0))
    (entry,) = h.ledger
    assert (entry.run_id, entry.purpose, entry.trf_iteration) == (None, None, None)
    assert entry.as_document()["inputs_sha256"] == entry.inputs_sha256


def test_scales_must_match_the_outputs() -> None:
    with pytest.raises(ValueError, match="2 outputs"):
        EFHolder("box", CountingBox(), (1.0,), kind="truth")
