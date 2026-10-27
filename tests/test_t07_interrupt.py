"""T07 W4b: the cooperative interruption hook (design note §8.1, §15 W4b, gate G5's record-k leg).

`Trace.record` calls `orchestrator.trace.INTERRUPT_CHECK`'s check before building its event;
`application.jobs.interrupt.interruptible` installs one that raises `JobInterrupted` (a
`BaseException`) once the cancel signal is set or the deadline has passed. What is held here:

- **Interruption at the k-th record**, k ∈ {1, 2, 3, 5, 8, 13, 21, 34, 55, 89}, on three corpus
  revisions through T06's revision path (`bind_revision_flowsheet` → `plan_revision` →
  `execute_plan`, as `benchmarks/t06/ensemble.py` runs it, under the registry's
  `T06-revision-v2`): `JobInterrupted` leaves `execute_plan` with its reason and is never an
  outcome; the check ran exactly k times; the plan's trace is exactly the uninterrupted trace up
  to the last event it had completed before the k-th record; numpy's global generator is where it
  was. Where k exceeds the run's records the solve completes, equal to the uninterrupted one.
- **Interruption inside `verify_revision`**, raised within `inverse_one_norm_estimate`'s seeded
  region (the verifier records no events, so the check is injected there): it propagates, and the
  `finally` restores the generator.
- **Inertness**: with no check, a no-op check and a counting check, five corpus solves give the
  same `solve-events` bytes (the hook changes nothing it does not raise from). Equality with the
  pre-hook base is the identity protocol's and `docs/t07-measurements.md` § W4b's (the event
  digests hold floats, which are not pinned across architectures).
- **The lint**: no handler in `src/` can swallow a `BaseException` (below, `test_no_broad_except`).

**Records versus events.** A region step runs on its own trace, whose events `execute_plan` copies
into the plan's trace when the region returns (`orchestrator/executor.py::_absorb`); each copy is a
second `record`. So the k-th check is the k-th `record` on any trace, and the plan trace an
interruption leaves ends at the last event *it* had completed — for a single-trace solve that is
event k − 1, here it is the prefix the reference run measured. The interrupted region's own events
never reach the plan trace.

Overhead (G18: the hook ≤ 2 % of the median solve time) is measured, not tested here; the numbers
are in `docs/t07-measurements.md` § W4b.
"""

from __future__ import annotations

import ast
import ctypes
import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import scipy
from conftest import REPO_ROOT, TERMINAL_REPORT
from t06_ensemble_support import STARTS_FILE, ensemble_cases

from benchmarks.t06 import ensemble, generator
from openflowsheet.application.jobs.interrupt import (
    JobInterrupted,
    interrupt_check,
    interruptible,
)
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.canonical import canonical_json
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import PlanResult, execute_plan
from openflowsheet.orchestrator.revision import plan_revision
from openflowsheet.orchestrator.trace import INTERRUPT_CHECK, Trace
from openflowsheet.verify import regularity
from openflowsheet.verify.certificate import verify_revision

#: G5's record indices.
K = (1, 2, 3, 5, 8, 13, 21, 34, 55, 89)
#: (case, published start index, or `None` for the registered initializer). Measured at the base
#: (records / plan-trace events / outcome): STR-01 from the initializer 8 / 6 / CONVERGED, so
#: k ≥ 13 completes; NET-03 start 18 126 / 65 / CONVERGED; THM-09 start 4 154 / 79 /
#: BUDGET_EXHAUSTED.
#: Since R-782 (K03's release at every step; S10-C absent-component note §4.7 item 4), measured on
#: ref-x86-64: THM-09 start 4 94 / 49 / CONVERGED (every k ∈ K still interrupts inside it), and
#: under the test-local `max_property_calls = 100` (`WITNESS_CAP`) 24 / 14 / BUDGET_EXHAUSTED.
#: The uncapped length differs by machine class (CI run 40295317759 at 1bc65b86: 94 on ci-x86-64,
#: 136 on ci-aarch64), so its pin is `THM09_RECORDS`, keyed by `ensemble.machine_class()`.
RUNS = (("STR-01", None), ("NET-03", 18), ("THM-09", 4))
#: THM-09 start 4's uncapped record length since R-782, per registered machine class (note §4.7
#: item 4, §8.2). Every k ∈ K interrupts inside the run on each (89 < 94). On an unregistered
#: class the length is not pinned (T06 §7.5: reported, never gated); the interrupts still run.
#: ci-x86-64 is not pinned either: its runners' CPU varies (EPYC 7763 / 9V74, note §8 Q-C) and the
#: length with it — 94 in CI run 40295317759, 136 in CI run 40359016227 (S08b build decision T07-1).
#: Every run, on every class, reports the length in the terminal summary (R-796, C1; the lines go
#: to `docs/t07-measurements.md` § W4b.5); a (class, `cpu_model`, OpenBLAS core) key is pinned only
#: under R-796's re-pin rule.
THM09_RECORDS = {"ref-x86-64": 94, "ci-aarch64": 136}
#: The test-local property budget that keeps a budget refusal in the every-record leg since R-782
#: (THM-09 start 4 converges in 424 calls uncapped). The registry's `T06-revision-v2` is unchanged.
WITNESS_CAP = 100
#: The inertness set: W0.8's five timed revisions, from the initializer.
INERT = ("STR-01", "STA-02", "THM-09", "NET-03", "NET-10")


@dataclass(frozen=True)
class Prepared:
    case_id: str
    document: dict[str, Any]
    binding: RevisionBinding
    plan: ExecutionPlan
    policy: Any
    start: dict[str, float] | None


def _starts() -> dict[str, list[dict[str, Any]]]:
    return {c["case"]: c["starts"] for c in json.loads(STARTS_FILE.read_text())["cases"]}


def prepare(case_id: str, start: int | None, policy: Any = None) -> Prepared:
    """A fresh binding and plan of the case's revision (nothing carried between solves), under
    the registry's policy or, when given, `policy` (a test-local override of it)."""
    (case,) = [c for c in ensemble_cases() if c.case == case_id]
    assert case.path == "revision_eo" and case.policy.policy_id == "T06-revision-v2", case_id
    policy = case.policy if policy is None else policy
    document = case.document()
    binding = bind_revision_flowsheet(document)
    assert isinstance(binding, RevisionBinding), binding
    plan, _ = plan_revision(binding, policy)
    assert isinstance(plan, ExecutionPlan), plan
    vector = None
    if start is not None:
        (record,) = [s for s in _starts()[case_id] if s["start"] == start]
        vector = {name: float(value) for name, value in record["vector"].items()}
    return Prepared(case_id, document, binding, plan, policy, vector)


def solve(prepared: Prepared, trace: Trace) -> PlanResult:
    return execute_plan(
        plan=prepared.plan,
        flowsheet=prepared.binding.flowsheet,
        spec=prepared.binding.spec,
        policy=prepared.policy,
        trace=trace,
        user_start=prepared.start,
    )


def events(trace: Trace) -> list[str]:
    """Each event's document as exact text (`repr` floats round-trip; NaN and ±inf allowed)."""
    return [json.dumps(event.as_document(), sort_keys=True) for event in trace.events]


def rng_state() -> tuple[Any, ...]:
    return tuple(np.random.get_state())


def assert_same_rng(before: tuple[Any, ...], after: tuple[Any, ...]) -> None:
    assert before[0] == after[0]
    assert np.array_equal(before[1], after[1])
    assert before[2:] == after[2:]


@pytest.fixture(autouse=True)
def _global_generator() -> Iterator[None]:
    """Move numpy's global generator off any seeded state (so a missing restore shows), and hand
    the suite back the state it had."""
    saved = np.random.get_state()
    np.random.seed(7)
    np.random.random(5)
    try:
        yield
    finally:
        np.random.set_state(saved)
    assert INTERRUPT_CHECK.get() is None


class Count:
    """A check that only counts."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> None:
        self.calls += 1


class SetAt:
    """A cancel signal that becomes set at its `k`-th query: `is_set` is asked once per check."""

    def __init__(self, k: int) -> None:
        self.k = k
        self.calls = 0

    def is_set(self) -> bool:
        self.calls += 1
        return self.calls >= self.k


@dataclass(frozen=True)
class Reference:
    events: list[str]
    #: The plan trace's length at each check, in order: `lengths[j]` is how many plan-trace
    #: events existed when the (j + 1)-th `record` (on any trace) was called.
    lengths: list[int]
    outcome: str


def reference(case_id: str, start: int | None, policy: Any = None) -> Reference:
    prepared = prepare(case_id, start, policy)
    trace = Trace()
    lengths: list[int] = []
    token = INTERRUPT_CHECK.set(lambda: lengths.append(len(trace)))
    try:
        result = solve(prepared, trace)
    finally:
        INTERRUPT_CHECK.reset(token)
    assert result.trace is trace
    return Reference(events(trace), lengths, result.outcome)


def interrupt_at(
    case_id: str, start: int | None, ref: Reference, k: int, policy: Any = None
) -> None:
    """Solve with the cancel signal set at the k-th record and check G5's record-k clauses."""
    records = len(ref.lengths)
    prepared = prepare(case_id, start, policy)
    trace = Trace()
    signal = SetAt(k)
    before = rng_state()
    with interruptible(signal, None) as check:
        assert INTERRUPT_CHECK.get() is check
        if k <= records:
            with pytest.raises(JobInterrupted) as raised:
                solve(prepared, trace)
            assert raised.value.reason == "cancel_requested"
            assert signal.calls == k, (k, signal.calls)
            expected = ref.events[: ref.lengths[k - 1]]
            assert events(trace) == expected, (case_id, k)
            assert [e.sequence for e in trace.events] == list(range(len(expected)))
        else:
            result = solve(prepared, trace)
            assert signal.calls == records
            assert result.outcome == ref.outcome
            assert events(trace) == ref.events
    assert INTERRUPT_CHECK.get() is None
    assert_same_rng(before, rng_state())


def openblas_core(package: Any, pattern: str, symbol: str) -> str:
    """The OpenBLAS core `package`'s bundled library (`<package>.libs/<pattern>`) selected at
    run time, read through its `symbol`; `unknown` on any failure (R-796, C1)."""
    try:
        libs = Path(package.__file__).parent.parent / f"{package.__name__}.libs"
        (library,) = libs.glob(pattern)
        corename = getattr(ctypes.CDLL(str(library)), symbol)
        corename.restype = ctypes.c_char_p
        return str(corename().decode())
    except Exception:
        return "unknown"


def thm09_report(ref: Reference) -> str:
    """R-796's one line for THM-09 start 4's uncapped run: what the length is measured on, and the
    length."""
    numpy_core = openblas_core(np, "libscipy_openblas64_*.so", "scipy_openblas_get_corename64_")
    scipy_core = openblas_core(scipy, "libscipy_openblas*.so", "scipy_openblas_get_corename")
    return (
        f"T07 THM-09/4 uncapped: machine_class={ensemble.machine_class()}"
        f" cpu_model={generator._cpu_model()} openblas_numpy={numpy_core}"
        f" openblas_scipy={scipy_core} records={len(ref.lengths)} outcome={ref.outcome}"
    )


@pytest.mark.parametrize(("case_id", "start"), RUNS, ids=[f"{c}-{s}" for c, s in RUNS])
def test_interrupt_at_record_k(case_id: str, start: int | None) -> None:
    ref = reference(case_id, start)
    if case_id == "THM-09":
        report = thm09_report(ref)
        TERMINAL_REPORT.append(report)
        machine = ensemble.machine_class()
        if machine in THM09_RECORDS:
            assert len(ref.lengths) == THM09_RECORDS[machine], report
    else:
        assert len(ref.lengths) == {"STR-01": 8, "NET-03": 126}[case_id]
    assert len(ref.lengths) > max(K) or case_id == "STR-01"
    for k in K:
        interrupt_at(case_id, start, ref, k)


def test_interrupt_at_every_record() -> None:
    """Every record of the longest run (THM-09 start 4: regions, recovery), and one past the end;
    then every record of the same start under the test-local `WITNESS_CAP`, which ends in the
    budget refusal (the uncapped run converges since R-782), and one past its end. A record
    reached from inside a CasADi callback would fail here: CasADi turns a `BaseException` raised
    in a Python callback into a `RuntimeError`, which the backend's `except Exception` makes an
    `error` evaluation (measured, CasADi 3.8.0)."""
    ref = reference("THM-09", 4)
    for k in range(1, len(ref.lengths) + 2):
        interrupt_at("THM-09", 4, ref, k)
    (case,) = [c for c in ensemble_cases() if c.case == "THM-09"]
    capped = replace(case.policy, max_property_calls=WITNESS_CAP)
    ref = reference("THM-09", 4, capped)
    assert ref.outcome == "BUDGET_EXHAUSTED", ref.outcome
    for k in range(1, len(ref.lengths) + 2):
        interrupt_at("THM-09", 4, ref, k, capped)


def test_wall_time_exhausted_at_record_k() -> None:
    """The deadline leg of the same check: a clock that advances one unit per query crosses a
    deadline of 20.5 at the 21st record."""
    ref = reference("NET-03", 18)
    ticks = iter(range(1, 10_000))
    prepared = prepare("NET-03", 18)
    trace = Trace()
    before = rng_state()
    with interruptible(SetAt(10_000), 20.5, clock=lambda: float(next(ticks))):
        with pytest.raises(JobInterrupted) as raised:
            solve(prepared, trace)
    assert raised.value.reason == "wall_time_exhausted"
    assert events(trace) == ref.events[: ref.lengths[20]]
    assert_same_rng(before, rng_state())


@pytest.mark.parametrize("reason", ["cancel_requested", "wall_time_exhausted", "server_shutdown"])
@pytest.mark.parametrize(("case_id", "start"), [RUNS[0], RUNS[1]], ids=["STR-01", "NET-03-18"])
def test_interrupt_inside_verify(
    case_id: str, start: int | None, reason: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Raised inside `inverse_one_norm_estimate`'s seeded region, after scipy has drawn from the
    seeded generator: `verify_revision` lets it through, and the generator is restored."""
    prepared = prepare(case_id, start)
    result = solve(prepared, Trace())
    assert result.outcome == "CONVERGED"

    cancel = threading.Event()
    now = [0.0]
    real = regularity.onenormest
    fired: list[bool] = []

    def interrupted_onenormest(operator: Any) -> Any:
        estimate = real(operator)  # draws from the generator `inverse_one_norm_estimate` seeded
        if reason == "wall_time_exhausted":
            now[0] = 2.0
        else:
            cancel.set()
        check = INTERRUPT_CHECK.get()
        assert check is not None
        fired.append(True)
        check()
        return estimate

    monkeypatch.setattr(regularity, "onenormest", interrupted_onenormest)
    before = rng_state()
    with interruptible(
        cancel,
        1.0,
        cancel_reason=lambda: "server_shutdown"
        if reason == "server_shutdown"
        else "cancel_requested",
        clock=lambda: now[0],
    ):
        with pytest.raises(JobInterrupted) as raised:
            verify_revision(
                prepared.binding,
                prepared.document,
                result,
                solve_plan=prepared.plan.steps[-1].solve_plan,
            )
    assert fired == [True]
    assert raised.value.reason == reason
    assert_same_rng(before, rng_state())


def test_inert_without_a_raising_check() -> None:
    """No check, a no-op check and a counting check: the same `solve-events` bytes and outcome."""
    for case_id in INERT:
        digests = []
        count = Count()
        for installed in (None, lambda: None, count):
            prepared = prepare(case_id, None)
            token = INTERRUPT_CHECK.set(installed)
            try:
                result = solve(prepared, Trace())
            finally:
                INTERRUPT_CHECK.reset(token)
            document = [event.as_document() for event in result.trace.events]
            digests.append((result.outcome, canonical_json(document)))
        assert digests[0] == digests[1] == digests[2], case_id
        assert count.calls >= len(json.loads(digests[0][1])), case_id


def test_check_semantics() -> None:
    cancel = threading.Event()
    now = [0.0]
    check = interrupt_check(cancel, 5.0, clock=lambda: now[0])
    check()  # neither holds
    now[0] = 5.0
    with pytest.raises(JobInterrupted) as raised:
        check()
    assert raised.value.reason == "wall_time_exhausted"
    cancel.set()  # a requested cancellation is reported ahead of the deadline
    with pytest.raises(JobInterrupted) as raised:
        check()
    assert raised.value.reason == "cancel_requested"
    interrupt_check(threading.Event(), None)()  # no deadline: no limit
    assert not isinstance(JobInterrupted("cancel_requested"), Exception)
    assert isinstance(JobInterrupted("cancel_requested"), BaseException)


def test_interruptible_scope() -> None:
    """Installed for the body only, restored on `JobInterrupted`, invisible to another thread."""
    assert INTERRUPT_CHECK.get() is None
    seen: list[object] = []
    with interruptible(threading.Event(), None) as check:
        assert INTERRUPT_CHECK.get() is check
        worker = threading.Thread(target=lambda: seen.append(INTERRUPT_CHECK.get()))
        worker.start()
        worker.join()
    assert seen == [None]
    assert INTERRUPT_CHECK.get() is None
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(JobInterrupted):
        with interruptible(cancel, None) as check:
            check()
    assert INTERRUPT_CHECK.get() is None


# ------------------------------------------------------------------------------------ the lint


def _names_base_exception(node: ast.expr | None) -> bool:
    if node is None:
        return True  # bare `except:`
    if isinstance(node, ast.Tuple):
        return any(_names_base_exception(element) for element in node.elts)
    if isinstance(node, ast.Name):
        return node.id == "BaseException"
    if isinstance(node, ast.Attribute):
        return node.attr == "BaseException"
    return False


def _reraises_unconditionally(handler: ast.ExceptHandler) -> bool:
    """The body ends in `raise` (or `raise <its own name>`), and nothing in it can leave the
    handler another way (`return`, `break`, `continue`, outside nested functions)."""
    last = handler.body[-1]
    if not isinstance(last, ast.Raise) or last.cause is not None:
        return False
    if last.exc is not None and not (
        isinstance(last.exc, ast.Name) and handler.name is not None and last.exc.id == handler.name
    ):
        return False
    pending: list[ast.AST] = list(handler.body)
    while pending:
        node = pending.pop()
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda | ast.ClassDef):
            continue
        if isinstance(node, ast.Return | ast.Break | ast.Continue):
            return False
        pending.extend(ast.iter_child_nodes(node))
    return True


def broad_handlers() -> tuple[list[str], list[str]]:
    """(`src/` handlers that could swallow a `BaseException`, those that re-raise it)."""
    swallowing, reraising = [], []
    for path in sorted((REPO_ROOT / "src").rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and _names_base_exception(node.type):
                where = f"{path.relative_to(REPO_ROOT)}:{node.lineno}"
                (reraising if _reraises_unconditionally(node) else swallowing).append(where)
    return swallowing, reraising


def test_no_broad_except() -> None:
    """§8.1: `src/` has no bare `except:` and no `except BaseException` that could keep a
    `JobInterrupted` from reaching the runner. A cleanup handler that re-raises unconditionally
    cannot, and is allowed (the store's transaction rollback and `LocalApplication.open`'s
    close-on-failure, W2)."""
    swallowing, reraising = broad_handlers()
    assert swallowing == []
    assert all(where.startswith("src/openflowsheet/application/") for where in reraising)


def test_lint_detects() -> None:
    """The lint's own adversarial cases."""

    def classify(source: str) -> list[bool]:
        return [
            _reraises_unconditionally(node)
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.ExceptHandler) and _names_base_exception(node.type)
        ]

    assert classify("try:\n    pass\nexcept:\n    pass\n") == [False]
    assert classify("try:\n    pass\nexcept BaseException:\n    x = 1\n") == [False]
    assert classify("try:\n    pass\nexcept (ValueError, BaseException):\n    pass\n") == [False]
    assert classify(
        "def f():\n    try:\n        pass\n    except BaseException:\n"
        "        return 1\n        raise\n"
    ) == [False]
    assert classify(
        "try:\n    pass\nexcept BaseException as e:\n    raise RuntimeError() from e\n"
    ) == [False]
    assert classify("try:\n    pass\nexcept BaseException:\n    cleanup()\n    raise\n") == [True]
    assert classify("try:\n    pass\nexcept BaseException as e:\n    raise e\n") == [True]
    assert classify("try:\n    pass\nexcept Exception:\n    pass\n") == []
