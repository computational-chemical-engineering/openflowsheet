"""T04 implementation review (`docs/reviews/T04-review.md`): the reviewer's probes, as tests.

- **M1** (P1, P1b): a Jacobian evaluation that fails is a defect, never a zero matrix. At a PTC
  pseudo-step, at the polish and in the Newton core it ends the attempt `EVALUATION_ERROR` — not
  `PTC_STALLED` (an edge-3 trigger), not a rejected polish over a `CONVERGED` stop (a false
  success), not a SuperLU crash through the plan executor.
- **S5** (P1c): `solve_linear` refuses a structurally singular matrix before SuperLU, which under
  ADR 0004's options segfaulted on P1b's 42 × 42 of structural rank 8.
- **S1**, **S2** (P2): the identity guard reads the solve's identity from the result only, and ties
  `verify_bound`'s revision document to its binding.

Whatever can kill the interpreter runs in a subprocess, so a regression fails a test instead of
the session.
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from test_t04_ptc_region import HIGH, case, solve, start

from openflowsheet.orchestrator.recovery import eo_recovery_due
from openflowsheet.verify.checks import VerifierError

REPO_ROOT = Path(__file__).resolve().parents[1]


class FailingJacobian:
    """The compiled problem, delegating every call; the Jacobian calls whose 1-based index is in
    `bad` return `status = "error"` with empty data, exactly as the casadi backend does when a
    derivative block raises (`compile/casadi_backend.py`)."""

    def __init__(self, inner: Any, bad: tuple[int, ...] = (), status: str = "error") -> None:
        self._inner, self._bad, self._status = inner, set(bad), status
        self.calls = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def jacobian(self, x: Any, context: Any) -> Any:
        self.calls += 1
        result = self._inner.jacobian(x, context)
        if self.calls in self._bad:
            return dataclasses.replace(
                result,
                status=self._status,
                indptr=(0,) * (len(result.col_ids) + 1),
                indices=(),
                data=(),
                message="probe: the derivative block raised",
            )
        return result


def jacobian_calls(which: str, core: str = "ptc") -> int:
    item = case(HIGH)
    counting = FailingJacobian(item.compiled)
    result = solve(item, start(item, which), core=core, compiled=counting)
    assert result.outcome == "CONVERGED"
    return counting.calls


# ------------------------------------------------------------------ M1


STATUSES = ["error", "invalid_trial_state"]


@pytest.mark.parametrize("status", STATUSES)
def test_m1_j1_a_failed_polish_jacobian_ends_the_attempt_evaluation_error(status: str) -> None:
    """P1 J1 (r = 0.95 initializer; the polish's is the run's last Jacobian call). Before the fix:
    `CONVERGED` with `polish = rejected:linear_solve_failed`. §7.5 as amended: the Jacobian at x_c
    returning `error` *or otherwise not `ok`* is recorded `polish(rejected:error)` with x_c kept,
    and ends the attempt `EVALUATION_ERROR`."""
    from openflowsheet.orchestrator.trace import Trace

    item = case(HIGH)
    last = jacobian_calls("initializer")
    trace = Trace()
    result = solve(
        item,
        start(item, "initializer"),
        trace=trace,
        compiled=FailingJacobian(item.compiled, (last,), status),
    )
    (attempt,) = result.attempts
    assert result.outcome == attempt.solver_outcome == "EVALUATION_ERROR"
    assert attempt.ptc is not None and attempt.ptc.polish == "rejected:error"
    assert attempt.iterations == 39 and attempt.ptc.stopped_x is not None
    assert np.array_equal(
        attempt.ptc.stopped_x, [attempt.end_state[n] for n in _free(item, attempt)]
    )
    polish = [e for e in trace.of_kind("trial") if e.message.startswith("polish")]
    assert [e.message for e in polish] == ["polish(rejected:error)"]
    assert not eo_recovery_due(result.outcome, result.budget)


def _free(item: Any, attempt: Any) -> list[str]:
    from test_t04_ptc_region import attempt_system

    free, _, _ = attempt_system(item, dict(attempt.signature))
    return list(free)


@pytest.mark.parametrize("status", STATUSES)
def test_m1_j2_a_failed_pseudo_step_jacobian_is_not_a_stall(status: str) -> None:
    """P1 J2 (pseudo-step 4's Jacobian, the fifth call). Before the fix: eleven
    `linear_solve_failed` retries of `M̂/Δτ` over a zero matrix and `PTC_STALLED` — an edge-3
    trigger. §7.3 as amended: a Jacobian at an accepted iterate that is not `ok`, whatever its
    status, ends the attempt `EVALUATION_ERROR` — at pseudo-step 4, no retry, not a trigger."""
    item = case(HIGH)
    failing = FailingJacobian(item.compiled, (5,), status)
    result = solve(item, start(item, "initializer"), compiled=failing)
    (attempt,) = result.attempts
    assert result.outcome == attempt.solver_outcome == "EVALUATION_ERROR"
    assert attempt.iterations == 4
    assert attempt.ptc is not None and attempt.ptc.rejections == ()
    assert not eo_recovery_due(result.outcome, result.budget)


def test_m1_j3_no_converged_result_exists_to_certify() -> None:
    """P1 J3 (OFF-B, the polish's Jacobian). Before the fix: `CONVERGED` at the unpolished stop and
    K04 `FAILED` with `false_success_detected` on `material_balance.envelope.C`. Now the solve ends
    `EVALUATION_ERROR`, and K04 issues no certificate for it."""
    from openflowsheet.verify.certificate import verify

    item = case(HIGH)
    last = jacobian_calls("OFF-B")
    result = solve(item, start(item, "OFF-B"), compiled=FailingJacobian(item.compiled, (last,)))
    assert result.outcome == "EVALUATION_ERROR"
    assert [a.solver_outcome for a in result.attempts] == [
        "PHASE_UPDATE_REQUIRED",
        "EVALUATION_ERROR",
    ]
    assert result.root_fingerprint is None
    with pytest.raises(VerifierError, match="receives no certificate"):
        verify(item.flowsheet, result)


@pytest.mark.parametrize("status", STATUSES)
def test_m1_the_newton_core_ends_evaluation_error_on_a_failed_jacobian(status: str) -> None:
    """The Newton half of M1 (K03 §5.5 as amended): the region Newton core, its second Jacobian
    not `ok` (whatever its status), ends the attempt `EVALUATION_ERROR` instead of factoring a
    zero matrix."""
    item = case(HIGH)
    result = solve(
        item,
        start(item, "initializer"),
        core="newton",
        compiled=FailingJacobian(item.compiled, (2,), status),
    )
    (attempt,) = result.attempts
    assert result.outcome == attempt.solver_outcome == "EVALUATION_ERROR"
    assert attempt.iterations == 1


PLAN_PROBE = textwrap.dedent(
    """
    import dataclasses, json, sys
    import yaml
    sys.path.insert(0, "tests")
    import openflowsheet.orchestrator.executor as executor_module
    from test_t04_edge3 import CASES, plan_run, region_step
    from openflowsheet.compile.casadi_backend import compile_problem as real_compile
    from openflowsheet.orchestrator.trace import GlobalizationPolicy, SolvePolicy

    count = {"calls": 0}

    class Failing:
        def __init__(self, inner):
            self._inner = inner
        def __getattr__(self, name):
            return getattr(self._inner, name)
        def jacobian(self, x, context):
            count["calls"] += 1
            result = self._inner.jacobian(x, context)
            if count["calls"] > 2:
                return dataclasses.replace(
                    result, status="error", indptr=(0,) * (len(result.col_ids) + 1),
                    indices=(), data=(), message="probe",
                )
            return result

    executor_module.compile_problem = lambda spec: Failing(real_compile(spec))
    document = yaml.safe_load((CASES / "SYN-001-A02-360.yaml").read_text())
    policy = SolvePolicy(
        policy_id="probe", residual_tolerances={}, scales={},
        globalization=GlobalizationPolicy(eo_core="ptc"),
    )
    step = region_step(plan_run(document, policy).result)
    print(json.dumps({"outcome": step.outcome, "eo_recovery": step.eo_recovery}))
    """
)


def test_m1_p1b_through_the_executor_on_the_a02_region() -> None:
    """P1b: `SYN-001-A02-360` under `eo_core: ptc` with every Jacobian after the second failing.
    Before the fix the third factorization (pseudo-step 2's `M̂/Δτ` over a zero Jacobian) killed
    the interpreter with SIGSEGV. Now the region step ends `EVALUATION_ERROR` and edge 3 does not
    fire. In a subprocess, so that a regression fails this test rather than the session."""
    run = subprocess.run(
        [sys.executable, "-c", PLAN_PROBE],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert run.returncode == 0, f"exit {run.returncode}: {run.stderr[-2000:]}"
    reported = json.loads(run.stdout.strip().splitlines()[-1])
    assert reported == {"outcome": "EVALUATION_ERROR", "eo_recovery": None}


# ------------------------------------------------------------------ S5

#: P1b's matrix, as the reviewer dumped it: `M̂/Δτ` over a zero Jacobian at pseudo-step 2 of
#: `SYN-001-A02-360` under PTC — 42 × 42, 29 stored entries, structural rank 8.
P1B_MATRIX = [
    (10, 8, 0.23273565165450585), (10, 9, 0.00016446718178659634), (19, 10, 0.5016729320419099),
    (29, 10, 0.4665558267989762), (21, 11, 0.5016729320419099), (29, 11, 0.5418067666052627),
    (23, 12, 0.5016729320419099), (29, 12, 0.6170577064115491), (29, 13, 0.06826810757064013),
    (19, 15, 0.5016729320419099), (29, 15, 0.09030112776754377), (21, 16, 0.5016729320419099),
    (29, 16, 0.09030112776754377), (23, 17, 0.5016729320419099), (29, 17, 0.09030112776754377),
    (29, 18, 0.16446754408386574), (29, 19, 0.00016446754408386575), (6, 31, 0.5016729320419099),
    (10, 31, 0.4665552369752687), (7, 32, 0.5016729320419099), (10, 32, 0.5418061767815553),
    (8, 33, 0.5016729320419099), (10, 33, 0.6170571165878417), (6, 34, 0.5016729320419099),
    (10, 34, 0.09030053794383634), (7, 35, 0.5016729320419099), (10, 35, 0.09030053794383634),
    (8, 36, 0.5016729320419099), (10, 36, 0.09030053794383634),
]  # fmt: skip

SPLU_PROBE = textwrap.dedent(
    """
    import json, sys
    import numpy as np, scipy.sparse as sp
    from openflowsheet.numerics.linear import LinearSolveFailedError, solve_linear
    rows, columns, values = zip(*json.loads(sys.argv[1]))
    matrix = sp.csc_matrix((values, (rows, columns)), shape=(42, 42))
    try:
        solve_linear(matrix, np.ones(42))
        print(json.dumps({"solved": True}))
    except LinearSolveFailedError as failure:
        print(json.dumps({"reason": failure.reason, "message": str(failure)}))
    """
)


def test_s5_a_structurally_singular_matrix_is_refused_not_factored() -> None:
    """P1c: under ADR 0004's options SuperLU segfaulted on P1B_MATRIX (every run). Now
    `solve_linear` refuses it `exactly_singular` before factorizing, in a subprocess."""
    run = subprocess.run(
        [sys.executable, "-c", SPLU_PROBE, json.dumps(P1B_MATRIX)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert run.returncode == 0, f"exit {run.returncode}"
    assert json.loads(run.stdout) == {
        "reason": "exactly_singular",
        "message": "structurally singular: rank 8 of 42",
    }


def test_s5_the_options_are_adr_0004s_unchanged() -> None:
    from openflowsheet.numerics.linear import SUPERLU_OPTIONS

    assert dict(SUPERLU_OPTIONS) == {
        "permc_spec": "COLAMD",
        "diag_pivot_thresh": 1.0,
        "relax": 1,
        "panel_size": 10,
        "options": {"Equil": False, "IterRefine": "NOREFINE", "SymmetricMode": False},
    }


# ------------------------------------------------------------------ S1


def test_s1_the_callers_solve_plan_is_not_the_results_identity() -> None:
    """P2 G1b/G1c. Before the fix an object with neither fingerprint nor plan was judged once the
    caller passed `solve_plan=` — `VERIFIED` on the right state, `FAILED` with false success on a
    moved one. The identity is the result's (§4.8 item 1): both are `declaration_unidentified`."""
    from test_t04_certificate import solved

    from openflowsheet.verify.certificate import verify_bound

    item = solved("SYN-001-A02-360")
    for shift in (0.0, 0.5):
        state = dict(item.result.state)
        state["S3.T"] += shift
        anonymous = SimpleNamespace(outcome="CONVERGED", state=state)
        with pytest.raises(VerifierError, match=r"^declaration_unidentified$"):
            verify_bound(item.binding, item.document, anonymous, solve_plan=item.solve_plan)


# ------------------------------------------------------------------ S2


def test_s2_a_revision_document_that_is_not_the_bindings_is_refused() -> None:
    """P2 G2. Before the fix A02-360's binding with A02-365's document and A02-360's own result
    gave `FAILED`, `false_success_detected`, on `specification.U-FLASH.Q` — a false alarm on a
    correct root. Now `declaration_mismatch(revision)`, before any check; the matching pair G2′
    is `VERIFIED`."""
    from test_t04_certificate import solved

    from openflowsheet.verify.certificate import verify_bound

    a360, a365 = solved("SYN-001-A02-360"), solved("SYN-001-A02-365")
    with pytest.raises(VerifierError, match=r"^declaration_mismatch\(revision\)$"):
        verify_bound(a360.binding, a365.document, a360.result, solve_plan=a360.solve_plan)
    control = verify_bound(a360.binding, a360.document, a360.result, solve_plan=a360.solve_plan)
    assert control.verification_status == "VERIFIED"


# ------------------------------------------------------------------ N9


def test_n9_the_guards_state_hash_is_the_residuals_and_the_fingerprints() -> None:
    """Review N9 (P5): at HOM-01's recovered state the guard's hash, the compiled residual's
    `state_sha256` and the fingerprint's `full_state_sha256` are one hash."""
    from test_t04_certificate import solved

    from openflowsheet.canonical import state_sha256
    from openflowsheet.compile.casadi_backend import compile_problem
    from openflowsheet.compile.reference import state_vector
    from openflowsheet.compiled import EvaluationContext

    item = solved("HOM-01")
    spec = item.binding.spec
    compiled = compile_problem(spec)
    vector = state_vector(spec, item.result.state)
    context = EvaluationContext(
        model_version=compiled.metadata.model_version,
        constants_sha256=compiled.metadata.constants_sha256,
        phase_signature=None,
    )
    residual = compiled.residual(np.array(vector), context)
    guard = state_sha256(vector, spec.variable_ids)
    assert guard == residual.state_sha256 == item.result.root_fingerprint["full_state_sha256"]
