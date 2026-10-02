"""T08.A33: unchanged-physics evidence for the recovery edges that had none (review 2, Ruling 5).

Release spec §5.6 as amended by Ruling 6: evidence is (i) `identity_compared` — a test compares
the edge's instance with the failed or target one in `model_version`, `constants_sha256` and
specifications, or, for an edge acting inside one call on a caller-owned problem, shows every
evaluation before and after the edge made on the same problem object with equal pinned values;
(ii) `verified_certificate`; (iii) `guard`. Each test below is the one Ruling 5 names for its row of
`docs/recovery-edges.yaml`, and each first asserts that its edge fired.

- **E1** (Anderson restart): REC-05's map, wrapped in a recorder, through `solve_recycle` as T02's
  A14 runs it. A restart fires; every map evaluation is a call of the same map object with the
  same parameters.
- **E5** (structural-zero release): B35a's problem through `solve_newton`, with `_released`
  spied on. A non-empty set is released; every residual and Jacobian evaluation is made on the
  same `Problem` with the same pinned values.
- **E10** (the verifier's fresh-flash fallback): SYN-001-nominal's revision-route solve, verified
  twice — as it is, and with the projection's factorization raising. The patched certificate is
  judged at `final_state` (`linear_solve_failed`); both certify the bound declaration.
- **E12** (the PTC core): the lowest-index PTC-R1 start that W5's committed records list
  `CONVERGED` under the PTC arm, solved under `T08-ptc-v1`. Its plan and root fingerprint carry
  the bound declaration's identity.

And Ruling 8's reachability test for E1 and E2, which makes those rows `library-only`: no
`MODEL_BUILDERS` unit and no offered policy reaches an Anderson recycle iteration.

- **E7** (the PH closure without an answer → the TP flash; description review, Ruling 1 as ruled
  in its addendum): B31 (i)'s CH-UP-DP start (`test_b31i`'s `CASES`) through the full revision
  solve under `T06-revision-v2`, patched (`_ph_closure` gives no answer) and unpatched. The patch
  fires on `U-PHF` with a flowing feed and `fallback(U-PHF, tp)` is recorded, which the unpatched
  run does not record; the patched run is `CONVERGED` and `VERIFIED` against the bound declaration
  (kind `verified_certificate`). `U-PHF2`'s label is not asserted on: the leaving-`ZERO_FLOW`
  producer writes it too.
"""

from __future__ import annotations

import copy
import dataclasses
import json
from collections.abc import Callable, Mapping
from typing import Any

import numpy as np
import numpy.typing as npt
import pytest
import yaml
from conftest import REPO_ROOT
from t07_corpus import CORPUS
from test_t02_recycle import manufactured, recycle_problem
from test_t05b_openings import CASES as B31_CASES
from test_t05b_release_opening import POLICY as RELEASE_POLICY
from test_t05b_release_opening import START as RELEASE_START
from test_t05b_release_opening import affine

from benchmarks.t08.ptc_r1 import compare
from openflowsheet.application.binding import Binding, bind_revision_or_reason
from openflowsheet.application.policies import (
    APPLICATION_POLICIES,
    DEFAULT_POLICY_ID,
    T08_PTC_V1,
    resolve_policy,
)
from openflowsheet.application.revision_binding import (
    MODEL_BUILDERS,
    RevisionBinding,
    bind_revision_flowsheet,
)
from openflowsheet.application.revision_run import Route, legacy_plan, select_route, solve_route
from openflowsheet.canonical import document_sha256
from openflowsheet.numerics import newton
from openflowsheet.numerics.anderson import RecyclePolicy, solve_recycle
from openflowsheet.numerics.newton import Evaluation, Problem, solve_newton
from openflowsheet.orchestrator import region as region_module
from openflowsheet.orchestrator.execution import (
    ExecutionPlan,
    declaration_identity,
    eo_capability,
)
from openflowsheet.orchestrator.executor import execute_plan
from openflowsheet.orchestrator.region import RegionResult
from openflowsheet.orchestrator.revision import plan_revision
from openflowsheet.orchestrator.trace import Trace
from openflowsheet.verify import certificate as certificate_module
from openflowsheet.verify import projection
from openflowsheet.verify.certificate import CheckPolicy, verify_revision

# -- E1 ------------------------------------------------------------------------------------------


def _closure(function: Callable[..., Any]) -> tuple[Any, ...]:
    """The values a map closes over (its parameters), copied: arrays as arrays, the rest as is."""
    cells = function.__closure__ or ()
    return tuple(copy.deepcopy(cell.cell_contents) for cell in cells)


def _equal(left: Any, right: Any) -> bool:
    if isinstance(left, np.ndarray) or isinstance(right, np.ndarray):
        return bool(np.array_equal(left, right))
    if isinstance(left, tuple) and isinstance(right, tuple):
        return len(left) == len(right) and all(map(_equal, left, right))
    return bool(left == right)


def test_e1_an_anderson_restart_reevaluates_the_same_map() -> None:
    reference = yaml.safe_load(
        (REPO_ROOT / "benchmarks" / "t02" / "reference_values.yaml").read_text()
    )
    case = reference["cases_rec"]["REC-05"]
    g, t0 = manufactured(case, 0.1)
    trace = Trace()
    #: Per evaluation: the map object called, its parameters, and the events recorded before it.
    calls: list[tuple[Any, tuple[Any, ...], int]] = []

    def recorded(t: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        calls.append((g, _closure(g), len(trace)))
        return g(t)

    scale = [float(case["scale_mol_per_s"])] * 3
    result = solve_recycle(
        recycle_problem(recorded, scale), t0, policy=RecyclePolicy(depth_max=0), trace=trace
    )
    # A14's run, unchanged by the recorder and the trace.
    assert result.outcome == "RECYCLE_STAGNATION"
    assert result.stagnation_closures == (10, 15, 20)

    restarts = [index for index, event in enumerate(trace.events) if event.kind == "restart"]
    assert restarts, "no restart fired"
    first = restarts[0]
    before = [call for call in calls if call[2] <= first]
    after = [call for call in calls if call[2] > first]
    assert before and after
    assert len(calls) == result.residual_calls
    map_object, parameters, _ = calls[0]
    assert map_object is g
    for called, values, _ in calls:
        assert called is map_object
        assert _equal(values, parameters)


# -- E5 ------------------------------------------------------------------------------------------


def _pinned(problem: Problem) -> tuple[Any, ...]:
    """What fixes the B35a problem: its declared ids, tolerances, bounds and scaling, and the
    affine map's matrix and right-hand side."""
    from test_t05b_release_opening import JACOBIAN, RHS

    return (
        problem.variable_ids,
        problem.row_ids,
        dict(problem.row_tolerance),
        dict(problem.lower_bounds),
        dict(problem.scaling.column),
        dict(problem.scaling.row),
        JACOBIAN.tobytes(),
        RHS.tobytes(),
    )


def test_e5_the_release_reevaluates_the_same_problem(monkeypatch: pytest.MonkeyPatch) -> None:
    released: list[Any] = []
    real_released = newton._released

    def spy(*args: Any, **kwargs: Any) -> Any:
        answer = real_released(*args, **kwargs)
        released.append(answer)
        return answer

    monkeypatch.setattr(newton, "_released", spy)

    base = affine()
    evaluations: list[tuple[str, Problem, tuple[Any, ...]]] = []
    owner: list[Problem] = []

    def residual(x: npt.NDArray[np.float64]) -> Evaluation:
        evaluations.append(("residual", owner[0], _pinned(owner[0])))
        return base.residual(x)

    def jacobian(x: npt.NDArray[np.float64]) -> Any:
        evaluations.append(("jacobian", owner[0], _pinned(owner[0])))
        return base.jacobian(x)

    problem = Problem(
        variable_ids=base.variable_ids,
        row_ids=base.row_ids,
        residual=residual,
        jacobian=jacobian,
        scaling=base.scaling,
        row_tolerance=base.row_tolerance,
        lower_bounds=base.lower_bounds,
    )
    owner.append(problem)
    result = solve_newton(problem, RELEASE_START, RELEASE_POLICY, trace=Trace())
    # B35a's run, unchanged by the spy.
    assert (result.outcome, result.iterations) == ("CONVERGED", 1)

    assert any(released), "the release never fired"
    kinds = [kind for kind, _, _ in evaluations]
    assert kinds.count("residual") == result.counters.residual_calls
    assert kinds.count("jacobian") == result.counters.jacobian_calls
    _, first_problem, first_pinned = evaluations[0]
    assert first_problem is problem
    for _, evaluated_on, pinned in evaluations:
        assert evaluated_on is first_problem
        assert pinned == first_pinned


# -- E7 ------------------------------------------------------------------------------------------


def test_e7_a_ph_closure_without_an_answer_certifies_the_same_declaration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy = APPLICATION_POLICIES["T06-revision-v2"]
    document, start = B31_CASES["CH-UP-DP"]()
    _, again = B31_CASES["CH-UP-DP"]()
    assert list(start) == list(again)
    assert [np.float64(v).tobytes() for v in start.values()] == [
        np.float64(v).tobytes() for v in again.values()
    ]
    binding = bind_revision_flowsheet(document)
    assert isinstance(binding, RevisionBinding)
    assert document_sha256(document) == binding.revision_sha256

    def solve(user_start: Mapping[str, float]) -> tuple[ExecutionPlan, Any]:
        plan, _ = plan_revision(binding, policy)
        assert isinstance(plan, ExecutionPlan)
        run = execute_plan(
            plan=plan,
            flowsheet=binding.flowsheet,
            spec=binding.spec,
            policy=policy,
            user_start=user_start,
        )
        return plan, run

    def recorded(run: Any) -> str:
        return " ".join(event.message for event in run.trace.events)

    plain_plan, plain = solve(start)
    assert plain.outcome == "CONVERGED", plain.message
    assert "fallback(U-PHF, tp)" not in recorded(plain)

    #: Per `_ph_closure` call: the split's unit and whether its feed is all zero.
    calls: list[tuple[str, bool]] = []

    def no_answer(provider: Any, context: Any, split: Any, state: Any, *_: Any) -> None:
        calls.append((split.unit, all(state[name] == 0.0 for name in split.feed)))
        return None

    monkeypatch.setattr(region_module, "_ph_closure", no_answer)
    plan, patched = solve(again)
    monkeypatch.undo()

    # It fired: the no-answer branch on a flowing feed, not a `ZERO_FLOW` split.
    assert ("U-PHF", False) in calls
    assert "fallback(U-PHF, tp)" in recorded(patched)

    revisions: list[bool] = []
    real_guard = certificate_module._guard

    def guard(*args: Any, **kwargs: Any) -> Any:
        revisions.append(kwargs["revision_matches"])
        return real_guard(*args, **kwargs)

    monkeypatch.setattr(certificate_module, "_guard", guard)
    assert patched.outcome == "CONVERGED", patched.message
    solve_plan = plan.steps[-1].solve_plan
    assert solve_plan is not None
    certificate = verify_revision(binding, document, patched, solve_plan=solve_plan)
    assert certificate.verification_status == "VERIFIED", [
        (c.id, c.value) for c in certificate.checks if c.result in ("fail", "unsupported")
    ]
    identity = declaration_identity(binding.spec)
    assert (certificate.model_version, certificate.constants_sha256) == identity
    assert (solve_plan.model_version, solve_plan.constants_sha256) == identity
    plain_solve_plan = plain_plan.steps[-1].solve_plan
    assert plain_solve_plan is not None
    assert (plain_solve_plan.model_version, plain_solve_plan.constants_sha256) == identity
    assert revisions == [True]


# -- E10 -----------------------------------------------------------------------------------------


def test_e10_a_refused_projection_certifies_the_same_declaration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = CORPUS["SYN-001-nominal"]()
    route = select_route(document)
    assert isinstance(route, Route) and route.solve_path == "revision_eo"
    policy = resolve_policy(DEFAULT_POLICY_ID, route.solve_path)
    assert policy is not None
    check_policy = CheckPolicy()
    run = solve_route(route, document, policy=policy, check_policy=check_policy)
    assert run.outcome == "CONVERGED" and run.run is not None
    binding = route.binding

    revisions: list[bool] = []
    real_guard = certificate_module._guard

    def guard(*args: Any, **kwargs: Any) -> Any:
        revisions.append(kwargs["revision_matches"])
        return real_guard(*args, **kwargs)

    monkeypatch.setattr(certificate_module, "_guard", guard)

    def verified() -> Any:
        return verify_revision(
            binding, document, run.run, policy=check_policy, solve_plan=run.solve_plan
        )

    plain = verified()

    def refused(*_: Any, **__: Any) -> Any:
        raise RuntimeError("injected: the projection's factorization fails")

    monkeypatch.setattr(projection, "factorize", refused)
    patched = verified()

    assert plain.transformations["projection"]["judged_at"] == "projection"
    assert patched.transformations["projection"]["judged_at"] == "final_state"
    assert patched.transformations["projection"]["reason"] == "linear_solve_failed"

    # The bound declaration, judged both times: its identity, its revision, the check policy.
    model_version, constants = declaration_identity(binding.spec)
    for certificate in (plain, patched):
        assert certificate.model_version == model_version
        assert certificate.constants_sha256 == constants
        assert certificate.check_policy_sha256 == check_policy.sha256
    assert revisions == [True, True]
    assert document_sha256(document) == binding.revision_sha256


# -- E12 -----------------------------------------------------------------------------------------


def _lowest_converged_ptc_start() -> list[Any]:
    """The first start, in `start_rows`' order, that W5's committed reference records list
    `CONVERGED` on the PTC arm (`benchmarks/t08/ptc_r1/results-ref-x86-64.json`)."""
    results = json.loads((compare.CASE_DIR / "results-ref-x86-64.json").read_text())
    converged = {
        (record["i"], record["j"])
        for record in results["records"]
        if record["arm"] == "ptc" and record["outcome"] == "CONVERGED"
    }
    return next(row for row in compare.start_rows() if (row[0], row[1]) in converged)


def test_e12_a_ptc_solve_keeps_the_declaration() -> None:
    row = _lowest_converged_ptc_start()
    document = compare.revision_document()
    binding = bind_revision_flowsheet(document)
    assert isinstance(binding, RevisionBinding)
    assert T08_PTC_V1.globalization.eo_core == "ptc"
    plan, _ = plan_revision(binding, T08_PTC_V1)
    assert isinstance(plan, ExecutionPlan)
    run = execute_plan(
        plan=plan,
        flowsheet=binding.flowsheet,
        spec=binding.spec,
        policy=T08_PTC_V1,
        user_start=compare.start_vector(row),
    )
    assert run.outcome == "CONVERGED", run.message
    (step,) = [step for step in run.steps if step.kind == "solve_eo"]
    detail = step.detail
    assert isinstance(detail, RegionResult) and detail.root_fingerprint is not None

    identity = declaration_identity(binding.spec)
    solve_plan = plan.steps[-1].solve_plan
    assert solve_plan is not None
    assert (solve_plan.model_version, solve_plan.constants_sha256) == identity
    fingerprint: Mapping[str, Any] = detail.root_fingerprint
    assert (fingerprint["model_version"], fingerprint["constants_sha256"]) == identity


# -- E1, E2: library-only (Ruling 8) -------------------------------------------------------------


def _manifests_by_model() -> dict[str, list[Mapping[str, Any]]]:
    """Every unit manifest of the revisions that bind: the T07 corpus and PTC-R1's revision
    (the kinetic CSTR's only registered instance), by model id."""
    documents = [CORPUS[name]() for name in sorted(CORPUS)] + [compare.revision_document()]
    found: dict[str, list[Mapping[str, Any]]] = {}
    for document in documents:
        binding = bind_revision_flowsheet(copy.deepcopy(document))
        if isinstance(binding, RevisionBinding):
            for unit in binding.flowsheet.units():
                manifest = unit.manifest()
                found.setdefault(manifest["id"], []).append(manifest)
    return found


def test_e1_e2_no_offered_policy_or_unit_reaches_a_recycle_iteration() -> None:
    """E1 and E2 run only in an Anderson recycle iteration: a `converge` step whose method
    `build_execution_plan` resolves to `anderson` — requested, or `auto` with a loop unit that
    does not declare exact derivatives (`execution.py`, `eo_capability`).

    (1) Every `MODEL_BUILDERS` model that can sit in a loop — one with an outlet port — declares
    exact residual derivatives, by the predicate `auto` resolves with. A model without an outlet
    (the product sink, whose manifest declares `unavailable` because it has no output) is in no
    loop, and is the only kind exempted. (2) No policy of `APPLICATION_POLICIES` requests
    `anderson`, and on SYN-001-nominal's loop each plans a `newton_tear` converge step through
    `build_execution_plan`; the same plan with `anderson` requested does plan one, so the check
    can fail. Either part fails when a unit or an offered policy reaches the edge."""
    manifests = _manifests_by_model()
    assert set(manifests) == set(MODEL_BUILDERS), "a model with no bound instance to read"
    exempt = set()
    for model_id, entries in manifests.items():
        for manifest in entries:
            if not any(port["direction"] == "outlet" for port in manifest["ports"]):
                exempt.add(model_id)
                continue
            capable, method = eo_capability(manifest)
            assert capable, f"{model_id} declares {method!r}: `auto` resolves to anderson"
    assert exempt == {"syn001.product_sink"}

    binding = bind_revision_or_reason(copy.deepcopy(CORPUS["SYN-001-nominal"]()))
    assert isinstance(binding, Binding)

    def methods(policy: Any) -> list[str | None]:
        plan, _ = legacy_plan(binding, policy)
        assert isinstance(plan, ExecutionPlan)
        return [step.method for step in plan.steps if step.kind == "converge"]

    for policy_id, policy in APPLICATION_POLICIES.items():
        assert policy.recycle.method != "anderson", policy_id
        assert methods(policy) == ["newton_tear"], policy_id
    some = next(iter(APPLICATION_POLICIES.values()))
    requested = dataclasses.replace(
        some, recycle=dataclasses.replace(some.recycle, method="anderson")
    )
    assert methods(requested) == ["anderson"]
