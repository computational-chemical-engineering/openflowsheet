"""T03 A02–A05 and A13–A18: the contract's mechanics, beyond the registered trajectories.

One decision function for both controllers (A02); [A01]'s frozen attempt — its own context objects,
its pinned variables exactly `+0.0` (A03); a screen that reads a trial and never alters it (A04),
through the closure check's own callable, asking the kernel only on flagged trials (A05); T02's
cases under the contract (A13); adjacency on the tear path with exact dyadic arithmetic (A14); the
sparsity record (A15); the opening checks and their typed refusal (A16); the opening record (A17);
bounded cycling and the budget (A18).

Facts the trace does not carry are observed: the region's per-attempt residual and Jacobian are
wrapped (the wrapper records, the solver computes exactly what it would have), and the constructed
refusals of A16 are test doubles at the opening check — T03 §5.1: "Registered bites are
constructed", since no registered path produces an incompatible state.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import scipy.sparse as sp
import yaml

import openflowsheet.orchestrator.phase_contract as phase_contract
import openflowsheet.orchestrator.region as region_module
from openflowsheet.canonical import state_sha256
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.numerics.newton import Evaluation, Problem
from openflowsheet.numerics.scaling import Scaling
from openflowsheet.orchestrator.attempts import solve_with_attempts
from openflowsheet.orchestrator.region import RegionResult, solve_region, syn001_lifted_splits
from openflowsheet.orchestrator.tear import solve_tear
from openflowsheet.orchestrator.trace import SolvePolicy, Trace

REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY = SolvePolicy(policy_id="T03", residual_tolerances={}, scales={})

GRAMMAR = re.compile(
    r"^(initial"
    r"|phase_update\((phase_wall\((patience|stall), [\w-]+:\w+->\w+(, [\w-]+:\w+->\w+)*\)"
    r"|phase_disappeared\([\w-]+, (vapor|liquid), [\w.]+\)"
    r"|inadmissible\(\w+, all_(liquid|vapor)\)"
    r"|kernel_disagrees\([\w-]+, \w+\))\))$"
)


@pytest.fixture(scope="module")
def ref() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(
        (REPO_ROOT / "benchmarks" / "t03" / "reference_values.yaml").read_text()
    )
    return loaded


@dataclass
class Observed:
    result: RegionResult
    trace: Trace
    #: per attempt: every residual call's free vector, and the call's evaluation
    calls: dict[int, list[tuple[np.ndarray, Evaluation]]] = field(default_factory=dict)
    #: per attempt: every Jacobian's shape and nonzero positions
    jacobians: dict[int, list[tuple[tuple[int, int], set[tuple[int, int]]]]] = field(
        default_factory=dict
    )
    #: per attempt: the context object each compiled residual call received
    contexts: dict[int, list[int]] = field(default_factory=dict)
    #: per attempt: (free ids, row ids)
    shapes: dict[int, tuple[tuple[str, ...], tuple[str, ...]]] = field(default_factory=dict)
    #: per attempt: the plain (unscreened) residual of the same attempt
    plain: dict[int, Callable[[np.ndarray], Evaluation]] = field(default_factory=dict)
    #: per attempt: kernel flash calls made by the screen
    screen_flashes: dict[int, int] = field(default_factory=dict)


def observe(
    case_id: str, monkeypatch: pytest.MonkeyPatch, policy: SolvePolicy = POLICY
) -> Observed:
    from test_t02_a02 import revision, structure, the_region

    item = structure(revision(case_id))
    flowsheet = item.binding.flowsheet
    pre, _ = solve_tear(flowsheet)
    assert pre.final_state is not None
    compiled = compile_problem(item.binding.spec)
    trace = Trace()
    seen = Observed(result=None, trace=trace)  # type: ignore[arg-type]
    original = region_module._region_problem
    original_screen = region_module._screen

    def observed(compiled_, context, spec, scaling, base, free, rows, screen=None, opening=None):  # type: ignore[no-untyped-def]
        attempt = len(seen.calls)
        seen.calls[attempt], seen.jacobians[attempt], seen.contexts[attempt] = [], [], []
        seen.shapes[attempt] = (tuple(free), tuple(rows))
        seen.plain[attempt] = original(compiled_, context, spec, scaling, base, free, rows).residual
        problem = original(compiled_, context, spec, scaling, base, free, rows, screen, opening)
        residual, jacobian = problem.residual, problem.jacobian

        def spied_residual(x):  # type: ignore[no-untyped-def]
            out = residual(x)
            seen.calls[attempt].append((np.array(x, dtype=np.float64), out))
            return out

        def spied_jacobian(x):  # type: ignore[no-untyped-def]
            matrix = sp.csc_matrix(jacobian(x))
            coo = matrix.tocoo()
            seen.jacobians[attempt].append(
                (matrix.shape, {(int(i), int(j)) for i, j in zip(coo.row, coo.col, strict=True)})
            )
            return matrix

        seen.contexts[attempt].append(id(context))
        return replace(problem, residual=spied_residual, jacobian=spied_jacobian)

    def counted_screen(*, splits, regimes, provider, context, epsilon):  # type: ignore[no-untyped-def]
        attempt = len(seen.calls)
        seen.screen_flashes[attempt] = 0

        class Counting:
            def __getattr__(self, name: str) -> Any:
                return getattr(provider, name)

            def flash(self, request, context_):  # type: ignore[no-untyped-def]
                seen.screen_flashes[attempt] += 1
                return provider.flash(request, context_)

        return original_screen(
            splits=splits,
            regimes=regimes,
            provider=Counting(),
            context=context,
            epsilon=epsilon,
        )

    monkeypatch.setattr(region_module, "_region_problem", observed)
    monkeypatch.setattr(region_module, "_screen", counted_screen)
    seen.result = solve_region(
        compiled=compiled,
        spec=item.binding.spec,
        region=the_region(item),
        state=dict(pre.final_state),
        splits=syn001_lifted_splits(flowsheet.components),
        provider=flowsheet.provider,
        policy=policy,
        trace=trace,
        initializer_source="user_guess",
    )
    return seen


# ------------------------------------------------------------------------------------ A02


def test_a02_one_decision_function_for_both_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """`decide` is called once per attempt closure on the tear path (OFF-B) and the lifted path
    (PHS-01, PHS-04, PHS-05); neither controller keeps its own cycle or budget check."""
    tear_calls: list[str] = []
    region_calls: list[str] = []
    real = phase_contract.decide

    def spy_on(log: list[str]) -> Callable[..., Any]:
        def spy(*arguments: Any, **keywords: Any) -> Any:
            log.append(str(keywords["frozen"]))
            return real(*arguments, **keywords)

        return spy

    import openflowsheet.orchestrator.attempts as attempts_module

    monkeypatch.setattr(attempts_module, "decide", spy_on(tear_calls))
    monkeypatch.setattr(region_module, "decide", spy_on(region_calls))

    from test_k03_attempts import OFF_B, flowsheet_for, variants

    reference = yaml.safe_load(
        (REPO_ROOT / "benchmarks" / "syn001" / "reference_values.yaml").read_text()
    )
    tear, _ = solve_tear(
        flowsheet_for(variants(reference)["SYN-001-nominal"]), initial_recycle=OFF_B
    )
    assert len(tear_calls) == tear.attempts == 2
    for case_id in (
        "SYN-001-A02-355-liquid-guess",
        "SYN-001-A02-340-two-phase-guess",
        "SYN-001-A02-355-dew-guess",
    ):
        before = len(region_calls)
        result = observe(case_id, monkeypatch).result
        assert len(region_calls) - before == len(result.attempts)

    source = (REPO_ROOT / "src" / "openflowsheet" / "orchestrator").glob("*.py")
    producing = [path.name for path in source if "active_set_cycling(" in path.read_text()]
    assert producing == ["phase_contract.py"], "the cycling refusal is produced in one place"
    for name in ("attempts.py", "region.py"):
        text = (REPO_ROOT / "src" / "openflowsheet" / "orchestrator" / name).read_text()
        assert "ACTIVE_SET_CYCLING" not in text, f"{name} keeps no cycle rule of its own"
        assert " in used" not in text, f"{name} tests no used signatures itself"


# ------------------------------------------------------------------------------------ A03


@pytest.mark.parametrize(
    "case_id",
    [
        "SYN-001-A02-355-liquid-guess",
        "SYN-001-A02-360-liquid-guess",
        "SYN-001-A02-360-vapor-guess",
        "SYN-001-A02-340-two-phase-guess",
        "SYN-001-A02-355-dew-guess",
    ],
)
def test_a03_a01_every_attempt_is_frozen_and_its_own(
    case_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = observe(case_id, monkeypatch)
    contexts = seen.result.contexts
    assert len({id(context.evaluation_context) for context in contexts}) == len(contexts)
    for index, context in enumerate(contexts):
        assert seen.contexts[index] == [id(context.evaluation_context)]
        free, rows = seen.shapes[index]
        assert set(context.column_scales) == set(free)
        assert set(context.row_scales) == set(rows)
        attempt = seen.result.attempts[index]
        pinned = [
            name
            for split in syn001_lifted_splits(("A", "B", "C"))
            for name in split.pinned(dict(attempt.signature)[split.unit])
        ]
        for name in pinned:
            value = attempt.end_state[name]
            assert value == 0.0 and math.copysign(1.0, value) == 1.0, name
        # every event of attempt k except rejected trials carries σ_k
        for event in seen.trace.events:
            if event.attempt == index and event.kind in ("step_accepted", "attempt_opened"):
                assert event.signature == attempt.signature


# ------------------------------------------------------------------------------------ A04


def test_a04_the_screen_reads_a_trial_and_never_alters_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """At every trial of PHS-01 the screened residual's values are bit-identical to the frozen
    formulation's; only the reported signature differs — at iteration 0's α = 1 trial,
    `U-HEAT:VAPOR`."""
    seen = observe("SYN-001-A02-355-liquid-guess", monkeypatch)
    checked = 0
    for attempt, calls in seen.calls.items():
        for x, evaluation in calls:
            plain = seen.plain[attempt](x)
            assert plain.status == evaluation.status
            if evaluation.status == "ok":
                assert plain.values == evaluation.values, "bit-identical"
                checked += 1
    assert checked > 20
    first_trial = seen.calls[0][1][1]
    assert dict(first_trial.signature)["U-HEAT"] == "VAPOR"


# ------------------------------------------------------------------------------------ A05


@pytest.mark.parametrize(
    ("case_id", "flashes"),
    [
        ("SYN-001-A02-355-liquid-guess", 13),
        ("SYN-001-A02-360-liquid-guess", 12),
        ("SYN-001-A02-360-vapor-guess", 6),
    ],
)
def test_a05_the_kernel_is_asked_only_on_flagged_trials(
    case_id: str, flashes: int, monkeypatch: pytest.MonkeyPatch, ref: dict[str, Any]
) -> None:
    """The screen calls K03 §8.2's own check (the closure check's callable) and flashes once per
    flagged trial: 13, 12, 6 on attempt 1 (T03 §4.3's registered counts)."""
    screened: list[tuple[int, str]] = []
    real = region_module._admissible
    seen_box: list[Observed] = []

    def spy(provider, context, split, regime, state, epsilon):  # type: ignore[no-untyped-def]
        assert epsilon == POLICY.admissibility_epsilon, "the closure check's own ε"
        screened.append((len(seen_box[0].calls) - 1 if seen_box else -1, split.unit))
        return real(provider, context, split, regime, state, epsilon)

    monkeypatch.setattr(region_module, "_admissible", spy)
    original_observe_calls = Observed.__init__

    def remember(self: Observed, *arguments: Any, **keywords: Any) -> None:
        original_observe_calls(self, *arguments, **keywords)
        seen_box.append(self)

    monkeypatch.setattr(Observed, "__init__", remember)
    seen = observe(case_id, monkeypatch)
    assert seen.screen_flashes[0] == flashes
    in_first = [unit for attempt, unit in screened if attempt == 0]
    assert in_first, "the screen goes through the closure check's own callable"
    assert set(in_first) == {"U-HEAT"}, "the TWO_PHASE flash is never screened"


def test_a05_the_opening_state_is_not_screened(
    monkeypatch: pytest.MonkeyPatch, ref: dict[str, Any]
) -> None:
    """PHS-04's LIQUID attempt opens at a state its own screen would refuse (1.0754…) and
    converges."""
    from openflowsheet.compiled import EvaluationContext

    seen = observe("SYN-001-A02-340-two-phase-guess", monkeypatch)
    assert seen.result.outcome == "CONVERGED"
    first = seen.result.attempts[0]
    opening = dict(first.end_state)
    heater = syn001_lifted_splits(("A", "B", "C"))[0]
    region_module._pin(opening, heater, "LIQUID")
    context = EvaluationContext(
        model_version="t03", constants_sha256="0" * 64, phase_signature=None
    )
    from test_t02_a02 import revision, structure

    provider = structure(revision("SYN-001-A02-340-two-phase-guess")).binding.flowsheet.provider
    ok, value = region_module._admissible(provider, context, heater, "LIQUID", opening, 1e-12)
    registered = ref["policy_simulation"]["cases"]["SYN-001-A02-340-two-phase-guess"]
    expected = float(registered["attempts"][1]["opening_screen_value"])
    assert not ok and abs(value - expected) <= 1e-9 * expected


# ------------------------------------------------------------------------------------ A13


def test_a13_t02s_successes_keep_one_attempt_and_their_counts(
    monkeypatch: pytest.MonkeyPatch, ref: dict[str, Any]
) -> None:
    registered = ref["t02_successes_under_the_contract"]
    for case_id, target in (
        ("SYN-001-A02-355", "SYN-001-A02-355 (guess 358 K)"),
        ("SYN-001-A02-360", "SYN-001-A02-360 (guess 358 K)"),
        ("SYN-001-A02-365", "SYN-001-A02-365 (guess 358 K)"),
    ):
        seen = observe(case_id, monkeypatch)
        assert seen.result.outcome == "CONVERGED"
        assert len(seen.result.attempts) == registered[target]["attempts"] == 1
        assert seen.result.attempts[0].iterations == registered[target]["core_iterations"]
        accepted = [e for e in seen.trace.events if e.kind == "step_accepted"]
        assert all(float(e.alpha) == 1.0 for e in accepted), "no landing"


def test_a13_the_nominal_eo_case_closes_by_a_block_with_the_same_numbers() -> None:
    """T02 A21 under the contract: attempt 1's core ends `BOUND_BLOCKED` on a vapour variable of
    the heater, converted to `phase_disappeared`; attempt 2 LIQUID converges within 5."""
    from test_t02_region import case, initializer, solve

    from openflowsheet.orchestrator.tear import INITIALIZER_ID

    item = case("SYN-001-nominal")
    result = solve(item, initializer(item), source=INITIALIZER_ID)
    first, second = result.attempts
    assert first.solver_outcome == "BOUND_BLOCKED"
    assert first.reason.startswith("phase_disappeared(U-HEAT, vapor, S3.vap.")
    assert second.outcome == "CONVERGED" and second.iterations <= 5
    assert result.branch_provenance[1]["opening_source"] == "pinned_iterate"


# ------------------------------------------------------------------------------------ A14


def synthetic(b1: float, b2: float) -> tuple[Problem, Callable[[np.ndarray], Any], list[float]]:
    """T03 §6.6: `r = x − 3` in every regime; LIQUID below b₁, TWO_PHASE to b₂, VAPOR above."""
    evaluated: list[float] = []

    def regime(x: float) -> Any:
        return (("U-SYN", "LIQUID" if x < b1 else "TWO_PHASE" if x < b2 else "VAPOR"),)

    def residual(x: np.ndarray) -> Evaluation:
        evaluated.append(float(x[0]))
        return Evaluation(status="ok", values=(float(x[0]) - 3.0,), signature=regime(float(x[0])))

    problem = Problem(
        variable_ids=("x",),
        row_ids=("r",),
        residual=residual,
        jacobian=lambda x: sp.csc_matrix(np.array([[1.0]])),
        scaling=Scaling(column={"x": 1.0}, row={"r": 1.0}),
        row_tolerance={"r": 1e-12},
    )
    return problem, lambda x: regime(float(x[0])), evaluated


@pytest.mark.parametrize(
    ("name", "bounds"), [("PHS-SYN-1", (1.0, 2.0)), ("PHS-SYN-2", (1.0, 1.01))]
)
def test_a14_adjacency_on_the_tear_path_in_exact_arithmetic(
    name: str, bounds: tuple[float, float], ref: dict[str, Any]
) -> None:
    from openflowsheet.compiled import EvaluationContext

    registered = ref["policy_simulation"]["synthetic_tear_seeds"][name]
    problem, signature_of, evaluated = synthetic(*bounds)
    context = EvaluationContext(
        model_version="syn", constants_sha256="0" * 64, phase_signature=None
    )
    trace = Trace()
    result = solve_with_attempts(
        problem_for=lambda attempt: problem,
        x0=[0.0],
        signature_of=signature_of,
        policy=POLICY,
        trace=trace,
        evaluation_context=context,
        flowsheet_context=context,
        column_scales={"x": 1.0},
        row_scales={"r": 1.0},
        variable_ids=("x",),
    )
    assert result.outcome == registered["outcome"] == "CONVERGED"
    assert float(result.x[0]) == float(registered["x"])
    assert len(result.branch_provenance) == len(registered["attempts"])
    expected_points: list[float] = []
    for attempt in registered["attempts"]:
        expected_points.append(float(attempt["opening_x"]))
        for iteration in attempt["iterations"]:
            expected_points.extend(float(trial["x"]) for trial in iteration)
    assert evaluated == expected_points, "every trial, exactly (dyadic rationals)"
    for item, attempt in zip(result.branch_provenance, registered["attempts"], strict=True):
        assert dict(item["signature"])["U-SYN"] == attempt["signature"]


def test_a14_off_b_restarts_where_k03_did() -> None:
    """Every OFF-B candidate is TWO_PHASE, so the adjacent rule takes K03's largest-α one."""
    from test_k03_attempts import OFF_B, flowsheet_for, variants

    reference = yaml.safe_load(
        (REPO_ROOT / "benchmarks" / "syn001" / "reference_values.yaml").read_text()
    )
    result, trace = solve_tear(
        flowsheet_for(variants(reference)["SYN-001-nominal"]), initial_recycle=OFF_B
    )
    assert result.outcome == "CONVERGED" and result.attempts == 2
    item = result.branch_provenance[1]
    assert item["opening_source"] == "phase_rejected_trial"
    rejected = [
        e
        for e in trace.events
        if e.kind == "trial"
        and e.attempt == 0
        and e.rejection_reason == "phase_update_required"
        and e.iteration == item["opening_trial"]["iteration"]
    ]
    assert rejected[0].alpha == max(e.alpha for e in rejected), "the largest-α candidate"


# ------------------------------------------------------------------------------------ A15


def test_a15_the_sparsity_rebuild_is_recorded_and_true(
    monkeypatch: pytest.MonkeyPatch, ref: dict[str, Any]
) -> None:
    shapes = ref["closed_form"]["region_shapes_rows_by_columns"]
    seen = observe("SYN-001-A02-355-liquid-guess", monkeypatch)
    from test_t02_a02 import revision, structure

    compiled = compile_problem(structure(revision("SYN-001-A02-355-liquid-guess")).binding.spec)
    structure_entries = compiled.structural_pattern()
    for index, context in enumerate(seen.result.contexts):
        key = ",".join(f"{u}:{r}" for u, r in context.signature)
        pattern = context.jacobian_pattern
        assert pattern is not None
        assert [pattern["rows"], pattern["columns"]] == shapes[key]
        free, rows = seen.shapes[index]
        allowed = {
            (rows.index(r), free.index(c)) for r, c in structure_entries if r in rows and c in free
        }
        # Review S5: not recomputed with the function that produced it — the count against the
        # declared entries restricted by id here, and every stored entry inside it.
        assert pattern["nnz"] == len(allowed) < pattern["rows"] * pattern["columns"]
        for shape, entries in seen.jacobians[index]:
            assert shape == (pattern["rows"], pattern["columns"])
            assert entries <= allowed, "no stored entry outside the recorded pattern"
    digests = [context.jacobian_pattern["sha256"] for context in seen.result.contexts]  # type: ignore[index]
    assert len(set(digests)) == len(digests), "each signature's rebuild is its own pattern"


def test_a15_the_tear_pattern_is_the_same_across_attempts_and_the_cache_is_kept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from test_k03_attempts import OFF_B, flowsheet_for, variants

    from openflowsheet.thermo.cache import ExactPropertyCache

    sizes: list[int] = []
    caches: list[Any] = []
    real_init = ExactPropertyCache.__init__

    def capture(self: Any, *arguments: Any, **keywords: Any) -> None:
        real_init(self, *arguments, **keywords)
        caches.append(self)

    monkeypatch.setattr(ExactPropertyCache, "__init__", capture)
    reference = yaml.safe_load(
        (REPO_ROOT / "benchmarks" / "syn001" / "reference_values.yaml").read_text()
    )
    real_record = Trace.record

    def record(self: Trace, **fields: Any) -> Any:
        if fields.get("kind") == "attempt_opened" and caches:
            sizes.append(len(caches[-1]._entries))
        return real_record(self, **fields)

    monkeypatch.setattr(Trace, "record", record)
    result, _ = solve_tear(
        flowsheet_for(variants(reference)["SYN-001-nominal"]), initial_recycle=OFF_B
    )
    patterns = [context.jacobian_pattern for context in result.contexts]
    assert len(patterns) == 2 and patterns[0] == patterns[1] and patterns[0] is not None
    assert sizes == sorted(sizes) and sizes[-1] > 0, "the exact cache is never cleared"


# ------------------------------------------------------------------------------------ A16


@pytest.mark.parametrize(
    ("check", "subject", "observed", "corrupt"),
    [
        ("scale_segment", "scale_segment", None, lambda state: replace(state, scale_segment=1)),
        (
            "identity",
            "model_version",
            None,
            lambda state: replace(state, model_version="another@model"),
        ),
        # T08 review 2, Ruling 6 (recovery edge E4): the identity check's second field, injected.
        pytest.param(
            "identity",
            "constants_sha256",
            None,
            lambda state: replace(state, constants_sha256="0" * 64),
            id="identity-constants_sha256",
        ),
        (
            "bounds",
            "S3.liq.B",
            -1e-9,
            lambda state: replace(state, values={**state.values, "S3.liq.B": -1e-9}),
        ),
    ],
)
def test_a16_an_incompatible_opening_is_refused_and_opens_nothing(
    check: str,
    subject: str,
    observed: float | None,
    corrupt: Callable[[Any], Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = region_module.check_opening

    def corrupted(state: Any, requirement: Any) -> Any:
        return real(corrupt(state), requirement)

    monkeypatch.setattr(region_module, "check_opening", corrupted)
    assert_refused(observe("SYN-001-A02-355-liquid-guess", monkeypatch), check, subject, observed)


def test_a16_a_pinned_variable_that_is_not_zero_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`S3.vap.A = 1e-3` under a LIQUID signature: PHS-04's restart into LIQUID, corrupted."""
    real = region_module._LiftedOps.blocked

    def corrupted(self: Any, result: Any) -> Any:
        conversion = real(self, result)
        if conversion is None:
            return None
        state, regimes = conversion.opening
        return replace(conversion, opening=({**state, "S3.vap.A": 1e-3}, regimes))

    monkeypatch.setattr(region_module._LiftedOps, "blocked", corrupted)
    assert_refused(
        observe("SYN-001-A02-340-two-phase-guess", monkeypatch), "active_set", "S3.vap.A", 1e-3
    )


#: A float as `repr` writes one (review S4): no R0 string may carry one.
FLOAT = re.compile(r"\d\.\d|\de[-+]?\d|\binf\b|\bnan\b")


def assert_refused(seen: Observed, check: str, subject: str, observed: float | None) -> None:
    """A16's refusal, and S4's R0 form: `checkpoint_incompatible(<check>, <variable or field>)`
    with the offending number on the attempt record instead."""
    from openflowsheet.verify.failure import ACTIONS, OUTCOME_ACTIONS, TAXONOMY

    result = seen.result
    assert result.outcome == "CHECKPOINT_INCOMPATIBLE"
    assert result.message == f"checkpoint_incompatible({check}, {subject})"
    assert not FLOAT.search(result.message)
    expected = {} if observed is None else {f"{check}:{subject}": observed}
    assert dict(result.attempts[-1].observations) == expected
    opened = [e for e in seen.trace.events if e.kind == "attempt_opened"]
    assert len(opened) == len(result.attempts) == 1, "the refused attempt never opened"
    closed_at = max(e.sequence for e in seen.trace.events if e.kind == "attempt_closed")
    after = [e for e in seen.trace.events if e.sequence > closed_at]
    assert not [e for e in after if e.kind in ("trial", "step_accepted", "jacobian")]
    assert result.checkpoint is not None and result.checkpoint.label == "partial"
    assert result.root_fingerprint is None, "no certificate target"
    assert TAXONOMY["CHECKPOINT_INCOMPATIBLE"] == "homotopy/PTC/active-set stalls"
    assert OUTCOME_ACTIONS["CHECKPOINT_INCOMPATIBLE"] == "report_defect"
    assert ACTIONS[TAXONOMY["CHECKPOINT_INCOMPATIBLE"]] != "report_defect", (
        "an override, not the class's"
    )


def test_a16_every_registered_opening_passes_all_six_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    refusals: list[Any] = []
    real = region_module.check_opening

    def watched(state: Any, requirement: Any) -> Any:
        outcome = real(state, requirement)
        refusals.append(outcome)
        return outcome

    monkeypatch.setattr(region_module, "check_opening", watched)
    for case_id in (
        "SYN-001-A02-355-liquid-guess",
        "SYN-001-A02-360-liquid-guess",
        "SYN-001-A02-360-vapor-guess",
        "SYN-001-A02-340-two-phase-guess",
    ):
        observe(case_id, monkeypatch)
    lifted = len(refusals)
    # Review S5: the tear path's one registered restart, OFF-B, through its own call site.
    from test_k03_attempts import OFF_B, flowsheet_for, variants

    import openflowsheet.orchestrator.attempts as attempts_module

    monkeypatch.setattr(attempts_module, "check_opening", watched)
    reference = yaml.safe_load(
        (REPO_ROOT / "benchmarks" / "syn001" / "reference_values.yaml").read_text()
    )
    result, _ = solve_tear(
        flowsheet_for(variants(reference)["SYN-001-nominal"]), initial_recycle=OFF_B
    )
    assert result.attempts == 2
    assert lifted >= 4 and len(refusals) == lifted + 1
    assert all(outcome is None for outcome in refusals)


# ------------------------------------------------------------------------------------ A17


@pytest.mark.parametrize(
    "case_id",
    [
        "SYN-001-A02-355-liquid-guess",
        "SYN-001-A02-340-two-phase-guess",
        "SYN-001-A02-355-dew-guess",
    ],
)
def test_a17_the_opening_record(case_id: str, monkeypatch: pytest.MonkeyPatch) -> None:
    seen = observe(case_id, monkeypatch)
    events = seen.trace.events
    for index, item in enumerate(seen.result.branch_provenance):
        (opened,) = [e for e in events if e.kind == "attempt_opened" and e.attempt == index]
        free, _ = seen.shapes[index]
        x0 = seen.calls[index][0][0]
        assert opened.state_sha256 == state_sha256(x0, free) == item["opening_state_sha256"]
        assert GRAMMAR.match(opened.message), opened.message
        if item["opening_source"] == "phase_rejected_trial":
            trial = item["opening_trial"]
            line_search = [
                e
                for e in events
                if e.attempt == index - 1
                and e.iteration == trial["iteration"]
                and e.kind in ("trial", "step_accepted")
            ]
            assert opened.alpha == line_search[trial["halving"]].alpha
        else:
            assert opened.alpha is None
        if index > 0:
            context = seen.result.contexts[index]
            assert context.opened_from is not None
            assert context.opened_from.checkpoint_id == f"region-attempt-{index - 1}"


# ------------------------------------------------------------------------------------ A18


def test_a18_the_attempt_budget_ends_the_solve_through_the_one_function(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PHS-01 with `max_attempts = 1`: the patience closure is refused by the budget."""
    seen = observe("SYN-001-A02-355-liquid-guess", monkeypatch, replace(POLICY, max_attempts=1))
    assert seen.result.outcome == "ATTEMPTS_EXHAUSTED"
    assert len(seen.result.attempts) == 1
    assert seen.result.checkpoint is not None and seen.result.checkpoint.label == "partial"


# ------------------------------------------------------------------------------------ A23


def test_a23_the_identity_document_carries_t03s_r0_fields() -> None:
    """The K05 identity document includes ADR 0005's R0 fields for the five cases A23 names, and
    stays floats-free; CI compares it byte for byte across x86-64 and aarch64."""
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from t03_identity import identity

    document = identity()
    assert set(document) == {"OFF-B", "PHS-01", "PHS-04", "PHS-05", "MR-A"}
    assert document["PHS-05"]["terminal_message"].startswith("active_set_cycling(")
    for name in ("OFF-B", "PHS-01", "PHS-04", "PHS-05"):
        assert document[name]["phase_contract"] == "T03-phase-contract-v1"
        assert all(pattern["sha256"] for pattern in document[name]["jacobian_patterns"])

    def floats(value: Any) -> list[float]:
        if isinstance(value, dict):
            return [f for item in value.values() for f in floats(item)]
        if isinstance(value, list):
            return [f for item in value for f in floats(item)]
        return [value] if isinstance(value, float) else []

    assert not floats(document)
    assert identity() == document, "the same twice on one machine"


# ------------------------------------------------------------------------------------ M3 (A03)


def test_m3_off_b_every_call_inside_an_attempt_is_that_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review M3 (P5): on the tear path the Jacobian's reconstruction traversed under the base
    flowsheet context. Now, inside attempt k: every compiled residual/Jacobian call passes
    attempt k's evaluation context object, and every provider call the tear code makes itself
    (traversal, reconstruction, re-split) passes attempt k's flowsheet context object.

    Provider calls made *inside* the compiled problem, by its property blocks, carry the context
    the blocks were assembled with (K01/K02: one compiled problem serves every attempt, and its
    blocks bind their provider context at assembly). That context is field-equal to the
    attempt's and is asserted so; routing the attempt's object into the CasADi callbacks is a
    change to the compiled boundary, recorded as a limitation for the design lane."""
    from test_k03_attempts import OFF_B, flowsheet_for, variants

    from openflowsheet.compile.casadi_backend import CasadiCompiledProblem
    from openflowsheet.orchestrator.attempts import _context_document
    from openflowsheet.thermo.cache import ExactPropertyCache

    open_attempt: list[int | None] = [None]
    in_compiled = [0]
    compiled_calls: list[tuple[int, int]] = []
    tear_calls: list[tuple[int, int]] = []
    block_calls: list[tuple[int, Any]] = []
    real_record = Trace.record

    def record(self: Trace, **fields: Any) -> Any:
        if fields.get("kind") == "attempt_opened":
            open_attempt[0] = fields["attempt"]
        elif fields.get("kind") == "attempt_closed":
            open_attempt[0] = None
        return real_record(self, **fields)

    def compiled_spy(name: str) -> Callable[..., Any]:
        real = getattr(CasadiCompiledProblem, name)

        def spy(self: Any, x: Any, context: Any) -> Any:
            if open_attempt[0] is not None:
                compiled_calls.append((open_attempt[0], id(context)))
            in_compiled[0] += 1
            try:
                return real(self, x, context)
            finally:
                in_compiled[0] -= 1

        return spy

    def provider_spy(name: str) -> Callable[..., Any]:
        real = getattr(ExactPropertyCache, name)

        def spy(self: Any, request: Any, context: Any) -> Any:
            if open_attempt[0] is not None:
                if in_compiled[0]:
                    block_calls.append((open_attempt[0], context))
                else:
                    tear_calls.append((open_attempt[0], id(context)))
            return real(self, request, context)

        return spy

    monkeypatch.setattr(Trace, "record", record)
    for name in ("residual", "jacobian"):
        monkeypatch.setattr(CasadiCompiledProblem, name, compiled_spy(name))
    for name in ("flash", "evaluate_phase"):
        monkeypatch.setattr(ExactPropertyCache, name, provider_spy(name))
    reference = yaml.safe_load(
        (REPO_ROOT / "benchmarks" / "syn001" / "reference_values.yaml").read_text()
    )
    result, _ = solve_tear(
        flowsheet_for(variants(reference)["SYN-001-nominal"]), initial_recycle=OFF_B
    )
    assert result.attempts == 2 and compiled_calls and tear_calls and block_calls
    for attempt, context_id in compiled_calls:
        assert context_id == id(result.contexts[attempt].evaluation_context), attempt
    for attempt, context_id in tear_calls:
        assert context_id == id(result.contexts[attempt].flowsheet_context), attempt
    for attempt, context in block_calls:
        own = result.contexts[attempt].flowsheet_context
        assert _context_document(context) == _context_document(own), attempt


def test_m3_the_compiled_residual_sees_pinned_variables_as_exactly_plus_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review M3: read the pinned positions of the vectors the compiled residual *received*, not
    values written into the end state afterwards."""
    from test_t02_a02 import revision, structure

    received: list[np.ndarray] = []
    real_compile = compile_problem

    def spying_compile(spec: Any) -> Any:
        compiled = real_compile(spec)
        real_residual = compiled.residual

        def residual(x: Any, context: Any) -> Any:
            received.append(np.array(x, dtype=np.float64))
            return real_residual(x, context)

        compiled.residual = residual  # type: ignore[method-assign]
        return compiled

    monkeypatch.setattr("test_t03_contract.compile_problem", spying_compile, raising=False)
    import sys

    monkeypatch.setattr(sys.modules[__name__], "compile_problem", spying_compile)
    seen = observe("SYN-001-A02-340-two-phase-guess", monkeypatch)
    spec = structure(revision("SYN-001-A02-340-two-phase-guess")).binding.spec
    order = {name: index for index, name in enumerate(spec.variable_ids)}
    heater = syn001_lifted_splits(("A", "B", "C"))[0]
    pinned = [order[name] for name in heater.pinned("LIQUID")]
    liquid_attempt = [e for e in seen.trace.events if e.kind == "attempt_opened" and e.attempt == 1]
    assert liquid_attempt and received
    liquid_vectors = [x for x in received if all(x[i] == 0.0 for i in pinned)]
    assert liquid_vectors, "the LIQUID attempt's calls reached the compiled residual"
    for x in liquid_vectors:
        assert all(math.copysign(1.0, x[i]) == 1.0 for i in pinned), "+0.0, sign bit clear"


# ------------------------------------------------------------------ review S1


def capped_phs_01(cap: int) -> tuple[Any, list[str]]:
    """PHS-01 through the plan executor under a property-call cap, with where the refused call was
    made: in the screen, in the decision's kernel calls, or elsewhere (the compiled residual)."""
    import traceback

    import test_t02_executor as t02
    from test_t02_executor import CASES

    from openflowsheet.application.binding import Binding, bind_revision
    from openflowsheet.orchestrator import budget

    binding = bind_revision(
        yaml.safe_load((CASES / "SYN-001-A02-355-liquid-guess.yaml").read_text())
    )
    assert isinstance(binding, Binding)
    sites: list[str] = []
    real_init = budget.BudgetExhaustedError.__init__

    def init(self: Any, *args: Any) -> None:
        frames = {frame.name for frame in traceback.extract_stack()}
        sites.append(
            "screen" if "reported_signature" in frames else "decide" if "decide" in frames else ""
        )
        real_init(self, *args)

    budget.BudgetExhaustedError.__init__ = init  # type: ignore[method-assign]
    try:
        run = t02.run_flowsheet(
            binding.flowsheet,
            binding.spec,
            binding.graph,
            binding.row_units,
            SolvePolicy(
                policy_id="T03-capped", residual_tolerances={}, scales={}, max_property_calls=cap
            ),
            specification_ids=binding.specification_ids,
            freed=binding.freed,
            promoted=binding.promoted,
        )
    finally:
        budget.BudgetExhaustedError.__init__ = real_init  # type: ignore[method-assign]
    return run, sites


@pytest.mark.parametrize(
    ("cap", "site", "trial"),
    [
        # refused in the screen at attempt 0's second iteration, after 351.232 K was accepted
        (265, "screen", "first accepted"),
        # refused building the patience restart: attempt 0 is over, its end state is kept
        (346, "decide", "end"),
    ],
)
def test_s1_a_refusal_outside_the_residual_keeps_the_attempts(
    cap: int, site: str, trial: str, ref: dict[str, Any]
) -> None:
    """Review S1 (P3b): a budget refusal in the screen or in the closure's kernel calls escaped the
    attempt loop, and the region result forgot its attempts, provenance and checkpoint and reported
    the start (`S3.T = 350`). Now it reports the last accepted iterate — the registered one."""
    run, sites = capped_phs_01(cap)
    assert sites[:1] == [site]
    assert run.result.outcome == "BUDGET_EXHAUSTED"
    assert run.result.counters.property_calls == cap
    region = run.result.steps[-1].detail
    assert isinstance(region, RegionResult)
    assert len(region.attempts) == 1 and len(region.branch_provenance) == 1
    assert region.checkpoint is not None and region.checkpoint.label == "partial"
    attempt = ref["policy_simulation"]["cases"]["SYN-001-A02-355-liquid-guess"]["attempts"][0]
    expected = (
        attempt["end_S3_T_K"]
        if trial == "end"
        else next(t["S3_T_K"] for t in attempt["trials"] if t["verdict"] == "accepted")
    )
    assert math.isclose(region.state["S3.T"], float(expected), rel_tol=1e-9)


def test_s1_every_cap_past_the_opening_keeps_every_attempt_it_made() -> None:
    """The sweep behind S1: at every cap that lets the region open, the region result carries one
    provenance item per attempt it recorded, and the count is exactly the cap."""
    for cap in range(156, 420, 9):
        run, _ = capped_phs_01(cap)
        assert run.result.outcome == "BUDGET_EXHAUSTED", cap
        assert run.result.counters.property_calls == cap, cap
        region = run.result.steps[-1].detail
        assert isinstance(region, RegionResult)
        opened = [e for e in run.result.trace.events if e.kind == "attempt_opened"]
        assert region.attempts, cap
        assert len(region.branch_provenance) == len(region.attempts), cap
        assert len(opened) == len(region.attempts) + 1, cap  # the pre-solve's attempt 0


# ------------------------------------------------------------------ review S2


def test_s2_item_0_names_the_source_of_the_executors_region_start() -> None:
    """Review S2 (P7): the executor's region recorded `user_guess` for every start. The nominal
    flowsheet under `eo` starts from the registered initializer's reconstruction; a
    specification region (A02-360) from the user's value, through the pre-solve."""
    from test_t02_executor import nominal, policy, revision_run

    from openflowsheet.orchestrator.tear import INITIALIZER_ID

    for run, expected in (
        (nominal(policy("eo")), INITIALIZER_ID),
        (revision_run("SYN-001-A02-360"), "user_guess"),
    ):
        region = run.result.steps[-1].detail
        assert isinstance(region, RegionResult) and region.outcome == "CONVERGED"
        first = region.branch_provenance[0]
        assert first["initializer_source"] == expected
        assert first["opening_source"] == "initializer" and first["attempt"] == 0


def test_s2_a_merged_region_continues_the_loops_provenance() -> None:
    """Review S2: the plan executor's merge recorded the region as a fresh attempt 0 opened from
    an initializer. §8.1: the loop's item proposes the merge and the region's follow it."""
    from test_t02_executor import nominal, policy

    run = nominal(policy("anderson", max_iterations_per_attempt=1))
    (converge,) = [step for step in run.result.steps if step.kind == "converge"]
    assert converge.merge_into_eo == "taken" and converge.recycle is not None
    loop = converge.recycle.branch_provenance
    items = converge.detail.branch_provenance
    assert [item["attempt"] for item in items] == list(range(len(items)))
    assert [dict(item) for item in items[: len(loop) - 1]] == [dict(i) for i in loop[:-1]]
    proposer, merged = items[len(loop) - 1], items[len(loop)]
    assert proposer["core"] == "anderson" and proposer["opening_source"] == "initializer"
    assert (proposer["decision"], proposer["cause"]) == ("restart", "merge_into_eo")
    assert merged["core"] == "newton" and merged["opening_source"] == "merge_best_iterate"
    assert merged["initializer_source"] is None
    assert items[-1]["decision"] == "converged"


# ------------------------------------------------------------------ review S5


LIQ: Any = (("U-HEAT", "LIQUID"),)
TWO: Any = (("U-HEAT", "TWO_PHASE"),)
VAP: Any = (("U-HEAT", "VAPOR"),)


def newton(outcome: str, iterations: int = 3, **extra: Any) -> Any:
    from openflowsheet.numerics.newton import NewtonResult
    from openflowsheet.orchestrator.trace import Counters

    return NewtonResult(
        outcome=outcome,  # type: ignore[arg-type]
        x=np.zeros(1),
        residual=(0.0,),
        residual_inf=0.0,
        merit=0.0,
        iterations=iterations,
        counters=Counters(),
        converged=outcome == "CONVERGED",
        message=f"core {outcome}",
        **extra,
    )


@dataclass
class StubOps:
    """A `PathOps` whose every answer is set by the row, and which logs what `decide` asked."""

    lifted: bool = True
    on_converged: Any = None
    on_blocked: Any = None
    on_kernel: Any = None
    refusal: Any = None
    asked: list[str] = field(default_factory=list)

    def converged(self, result: Any) -> Any:
        self.asked.append("converged")
        return self.on_converged

    def blocked(self, result: Any) -> Any:
        self.asked.append("blocked")
        return self.on_blocked

    def kernel_disagrees(self, result: Any) -> Any:
        self.asked.append("kernel_disagrees")
        return self.on_kernel

    def at_candidate(self, candidate: Any, cause: str) -> Any:
        self.asked.append("at_candidate")
        return phase_contract.Conversion(
            candidate.signature, "candidate", "phase_rejected_trial", cause, trial=candidate
        )

    def opening_check(self, conversion: Any) -> Any:
        self.asked.append("opening_check")
        return self.refusal


def conversion(signature: Any, source: str, cause: str, **extra: Any) -> Any:
    return phase_contract.Conversion(signature, "opening", source, cause, **extra)  # type: ignore[arg-type]


def walled(iterations: tuple[int, ...], signature: Any = TWO) -> Any:
    """A wall observer that saw a phase-rejected trial into `signature` at each iteration."""
    wall = phase_contract.WallObserver(POLICY)
    for iteration in iterations:
        wall.rejected(iteration, 0.5, np.zeros(1), "phase_update_required", signature)
    return wall


# (row id, core result, wall, ops, expected (kind, outcome, message), expected ops asked)
DECIDE_ROWS: list[tuple[str, Any, Any, Any, tuple[str, str, str], list[str]]] = [
    (
        "1 converged, admissible",
        newton("CONVERGED"),
        walled(()),
        StubOps(),
        ("converged", "CONVERGED", ""),
        ["converged"],
    ),
    (
        "1 converged, inadmissible -> 4.7(a)",
        newton("CONVERGED"),
        walled(()),
        StubOps(
            on_converged=conversion(
                TWO,
                "closure_projection",
                "inadmissible(S3, all_liquid)",
                observations={"admissibility:S3": 1.03},
            )
        ),
        ("restart", "PHASE_UPDATE_REQUIRED", "phase_update(inadmissible(S3, all_liquid))"),
        ["converged", "opening_check"],
    ),
    (
        "2 patience",
        newton("PHASE_UPDATE_REQUIRED"),
        walled((1, 2)),
        StubOps(),
        (
            "restart",
            "PHASE_UPDATE_REQUIRED",
            "phase_update(phase_wall(patience, U-HEAT:LIQUID->TWO_PHASE))",
        ),
        ["at_candidate", "opening_check"],
    ),
    (
        "3 watched variable blocked",
        newton("BOUND_BLOCKED", blocked_by=("S3.vap.A",)),
        walled((2,)),
        StubOps(
            on_blocked=conversion(
                VAP, "pinned_iterate", "phase_disappeared(U-HEAT, liquid, S3.liq.A)"
            )
        ),
        (
            "restart",
            "PHASE_UPDATE_REQUIRED",
            "phase_update(phase_disappeared(U-HEAT, liquid, S3.liq.A))",
        ),
        ["blocked", "opening_check"],
    ),
    (
        # the brief's question: rows 3-5 — an unwatched block with a wall in the window is not a
        # stall (row 4 names no BOUND_BLOCKED), so it falls to the kernel (row 5)
        "3->5 unwatched block, wall in window",
        newton("BOUND_BLOCKED", iterations=3, blocked_by=("S1.T",)),
        walled((2,)),
        StubOps(on_kernel=None),
        ("terminal", "BOUND_BLOCKED", "core BOUND_BLOCKED"),
        ["blocked", "kernel_disagrees"],
    ),
    (
        "4 stall with the wall in the window",
        newton("LINE_SEARCH_FAILED", iterations=4),
        walled((2,)),
        StubOps(),
        (
            "restart",
            "PHASE_UPDATE_REQUIRED",
            "phase_update(phase_wall(stall, U-HEAT:LIQUID->TWO_PHASE))",
        ),
        ["at_candidate", "opening_check"],
    ),
    (
        "5 stagnation, wall outside the window, kernel disagrees -> 4.7(b)",
        newton("STAGNATION", iterations=9),
        walled((1,)),
        StubOps(
            on_kernel=conversion(TWO, "closure_projection", "kernel_disagrees(U-HEAT, TWO_PHASE)")
        ),
        (
            "restart",
            "PHASE_UPDATE_REQUIRED",
            "phase_update(kernel_disagrees(U-HEAT, TWO_PHASE))",
        ),
        ["kernel_disagrees", "opening_check"],
    ),
    (
        "5 wall-free line-search failure, kernel agrees",
        newton("LINE_SEARCH_FAILED"),
        walled(()),
        StubOps(),
        ("terminal", "LINE_SEARCH_FAILED", "core LINE_SEARCH_FAILED"),
        ["kernel_disagrees"],
    ),
    (
        "5 newton-iteration budget",
        newton("BUDGET_EXHAUSTED", budget="newton_iterations"),
        walled(()),
        StubOps(),
        ("terminal", "BUDGET_EXHAUSTED", "core BUDGET_EXHAUSTED"),
        ["kernel_disagrees"],
    ),
    (
        "6 property budget: no kernel call",
        newton("BUDGET_EXHAUSTED", budget="property_calls"),
        walled(()),
        StubOps(),
        ("terminal", "BUDGET_EXHAUSTED", "core BUDGET_EXHAUSTED"),
        [],
    ),
    (
        "6 tear stagnation without a wall",
        newton("STAGNATION"),
        walled(()),
        StubOps(lifted=False),
        ("terminal", "STAGNATION", "core STAGNATION"),
        [],
    ),
    (
        "6 linear solve failed",
        newton("LINEAR_SOLVE_FAILED"),
        walled((1, 2)),
        StubOps(),
        ("terminal", "LINEAR_SOLVE_FAILED", "core LINEAR_SOLVE_FAILED"),
        [],
    ),
]


@pytest.mark.parametrize(
    ("row", "result", "wall", "ops", "expected", "asked"),
    DECIDE_ROWS,
    ids=[row[0] for row in DECIDE_ROWS],
)
def test_s5_decide_follows_the_precedence_table(
    row: str, result: Any, wall: Any, ops: StubOps, expected: Any, asked: list[str]
) -> None:
    """Review S5: T03 §4.8's table, one row per line, with a stub `PathOps` — including rows 3-5,
    which no registered case reaches, and both conversions T02 left with no test."""
    decision = phase_contract.decide(
        result, attempt_index=0, frozen=LIQ, wall=wall, ops=ops, policy=POLICY, used=[LIQ]
    )
    assert (decision.kind, decision.outcome, decision.message) == expected
    assert ops.asked == asked
    assert GRAMMAR.match(decision.message) or decision.kind != "restart"
    if decision.conversion is not None:
        assert dict(decision.observations) == dict(decision.conversion.observations)


@pytest.mark.parametrize(
    ("attempt_index", "used", "refusal", "outcome", "message", "asked"),
    [
        # (i) the budget comes first, whatever (ii) and (iii) would say
        (
            POLICY.max_attempts - 1,
            [LIQ, TWO],
            phase_contract.OpeningRefusal("bounds", "S3.liq.B", -1e-9),
            "ATTEMPTS_EXHAUSTED",
            f"{POLICY.max_attempts} attempts without convergence, against a policy maximum of "
            f"{POLICY.max_attempts}",
            ["at_candidate"],
        ),
        # (ii) cycling before the opening checks
        (
            0,
            [LIQ, TWO],
            phase_contract.OpeningRefusal("bounds", "S3.liq.B", -1e-9),
            "ACTIVE_SET_CYCLING",
            "active_set_cycling(U-HEAT:TWO_PHASE; phase_wall(patience, U-HEAT:LIQUID->TWO_PHASE))",
            ["at_candidate"],
        ),
        # (iii) the opening checks; the number goes to the observations, not the message
        (
            0,
            [LIQ],
            phase_contract.OpeningRefusal("bounds", "S3.liq.B", -1e-9),
            "CHECKPOINT_INCOMPATIBLE",
            "checkpoint_incompatible(bounds, S3.liq.B)",
            ["at_candidate", "opening_check"],
        ),
    ],
)
def test_s5_the_restart_gate_in_its_order(
    attempt_index: int,
    used: list[Any],
    refusal: Any,
    outcome: str,
    message: str,
    asked: list[str],
) -> None:
    ops = StubOps(refusal=refusal)
    decision = phase_contract.decide(
        newton("PHASE_UPDATE_REQUIRED"),
        attempt_index=attempt_index,
        frozen=LIQ,
        wall=walled((1, 2)),
        ops=ops,
        policy=POLICY,
        used=used,
    )
    assert (decision.kind, decision.outcome, decision.message) == ("terminal", outcome, message)
    assert ops.asked == asked
    assert decision.conversion is not None, "the proposed restart is kept for the provenance"
    assert not FLOAT.search(decision.message)
    if outcome == "CHECKPOINT_INCOMPATIBLE":
        assert dict(decision.observations) == {"bounds:S3.liq.B": -1e-9}


def test_s5_both_retained_conversions_on_a_physical_state(
    ref: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """§4.7(a) and (b) through `decide` with the real lifted operations, at a state the registered
    twin knows: PHS-01 attempt 0's flagged trial (`S3.T` = 352.4649 K, all liquid, `Σ x K` =
    1.02734 — registered). As a converged end state it is inadmissible; as a stagnated one the
    kernel disagrees. The causes are R0 (no number); the value is on the decision (review S4)."""
    attempt = ref["policy_simulation"]["cases"]["SYN-001-A02-355-liquid-guess"]["attempts"][0]
    flagged_trial = next(
        t for t in attempt["trials"] if (t["iteration"], t.get("halving")) == (0, 4)
    )
    assert flagged_trial["reported_heater_regime"] == "TWO_PHASE"
    flagged_t, flagged_value = float(flagged_trial["S3_T_K"]), float(flagged_trial["screen_value"])
    assert math.isclose(flagged_t, 352.4648902392, rel_tol=1e-12)

    kwargs: list[dict[str, Any]] = []
    flagged: list[dict[str, float]] = []
    real_init, real_admissible = region_module._LiftedOps.__init__, region_module._admissible

    def init(self: Any, **given: Any) -> None:
        kwargs.append(given)
        real_init(self, **given)

    def admissible(provider, context, split, regime, state, epsilon):  # type: ignore[no-untyped-def]
        ok, value = real_admissible(provider, context, split, regime, state, epsilon)
        if not ok and math.isclose(state[split.temperature], flagged_t, rel_tol=1e-9):
            flagged.append(dict(state))
        return ok, value

    monkeypatch.setattr(region_module._LiftedOps, "__init__", init)
    monkeypatch.setattr(region_module, "_admissible", admissible)
    observe("SYN-001-A02-355-liquid-guess", monkeypatch)
    assert flagged, "the registered flagged trial was screened"
    given = {**kwargs[0], "end_state": flagged[0]}
    opening = tuple((split.unit, given["regimes"][split.unit]) for split in given["splits"])
    assert dict(opening)["U-HEAT"] == "LIQUID"

    def decided(result: Any) -> Any:
        return phase_contract.decide(
            result,
            attempt_index=0,
            frozen=opening,
            wall=walled(()),
            ops=region_module._LiftedOps(**given),
            policy=POLICY,
            used=[opening],
        )

    inadmissible = decided(newton("CONVERGED"))
    assert inadmissible.message == "phase_update(inadmissible(S3, all_liquid))"
    assert inadmissible.conversion is not None
    assert inadmissible.conversion.source == "closure_projection"
    assert dict(inadmissible.conversion.signature)["U-HEAT"] == "TWO_PHASE"
    ((key, value),) = inadmissible.observations.items()
    assert key == "admissibility:S3" and math.isclose(value, flagged_value, rel_tol=1e-9)

    disagrees = decided(newton("STAGNATION", iterations=9))
    assert disagrees.message == "phase_update(kernel_disagrees(U-HEAT, TWO_PHASE))"
    assert disagrees.conversion is not None
    assert disagrees.conversion.source == "closure_projection"
    for decision in (inadmissible, disagrees):
        assert GRAMMAR.match(decision.message) and not FLOAT.search(decision.message)


def test_n4_a_candidate_the_kernel_disagrees_with_is_a_defect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review N4: `at_candidate` checks, rather than assumes, that the kernel's regime at the
    candidate is the one the screen reported; a disagreement is a defect, never a silent mismatch
    between the cause and the new signature."""
    real = region_module._kernel
    in_restart = [False]
    real_at_candidate = region_module._LiftedOps.at_candidate

    def at_candidate(self: Any, candidate: Any, cause: str) -> Any:
        in_restart[0] = True
        try:
            return real_at_candidate(self, candidate, cause)
        finally:
            in_restart[0] = False

    def kernel(provider, context, split, state):  # type: ignore[no-untyped-def]
        regime, values = real(provider, context, split, state)
        return ("VAPOR" if in_restart[0] else regime), values

    monkeypatch.setattr(region_module._LiftedOps, "at_candidate", at_candidate)
    monkeypatch.setattr(region_module, "_kernel", kernel)
    with pytest.raises(RuntimeError, match="defect: the kernel reports U-HEAT VAPOR"):
        observe("SYN-001-A02-355-liquid-guess", monkeypatch)


@pytest.mark.parametrize(
    ("status", "expected"), [("not_converged", "not_converged"), ("error", "error")]
)
def test_n3_the_screen_passes_the_kernels_refusal_through(
    status: str, expected: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review N3: a kernel that will not split a flagged trial is reported with its own status,
    naming the unit and the stream — never translated."""
    from openflowsheet.thermo import FlashResult

    seen: list[Evaluation] = []
    real_screen = region_module._screen

    def screen(*, splits, regimes, provider, context, epsilon):  # type: ignore[no-untyped-def]
        class Refusing:
            def __getattr__(self, name: str) -> Any:
                return getattr(provider, name)

            def flash(self, request, context_):  # type: ignore[no-untyped-def]
                return FlashResult(
                    status=status,  # type: ignore[arg-type]
                    phase_signature=None,
                    vapor_fraction=None,
                    vapor=None,
                    liquid=None,
                    message="stub refusal",
                )

        inner = real_screen(
            splits=splits, regimes=regimes, provider=Refusing(), context=context, epsilon=epsilon
        )

        def spied(state: dict[str, float]) -> Any:
            out = inner(state)
            if isinstance(out, Evaluation):
                seen.append(out)
            return out

        return spied

    monkeypatch.setattr(region_module, "_screen", screen)
    from test_t02_a02 import POLICY as T02_POLICY
    from test_t02_a02 import revision, structure, the_region

    item = structure(revision("SYN-001-A02-355-liquid-guess"))
    pre, _ = solve_tear(item.binding.flowsheet)
    assert pre.final_state is not None
    solve_region(
        compiled=compile_problem(item.binding.spec),
        spec=item.binding.spec,
        region=the_region(item),
        state=dict(pre.final_state),
        splits=syn001_lifted_splits(item.binding.flowsheet.components),
        provider=item.binding.flowsheet.provider,
        policy=T02_POLICY,
        initializer_source="user_guess",
    )
    assert seen, "PHS-01's first flagged trial reached the kernel"
    assert seen[0].status == expected
    assert seen[0].message == (
        f"the kernel refused U-HEAT's regime (S3) at the trial: {status}: stub refusal"
    )


def test_n2_every_way_a_builder_reads_a_parameter_is_recorded() -> None:
    """Review N2: the orphaned-parameter drop relies on `parameters_read`; a builder reading by
    `.get`, `in` or iteration must not see its parameter dropped silently."""
    from openflowsheet.graph.trace import _ReadTokens

    def fresh() -> Any:
        return _ReadTokens({"a": 1, "b": 2, "c": 3})  # type: ignore[dict-item]

    tokens = fresh()
    _ = tokens["a"]
    assert tokens.read == {"a"}
    tokens = fresh()
    tokens.get("b", 0)
    assert tokens.read == {"b"}
    tokens = fresh()
    _ = "c" in tokens
    assert tokens.read == {"c"}
    for walk in (list, lambda t: t.keys(), lambda t: t.values(), lambda t: t.items()):
        tokens = fresh()
        walk(tokens)
        assert tokens.read == {"a", "b", "c"}
