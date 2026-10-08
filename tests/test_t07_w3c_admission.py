"""T07 W3c: solve admission (§5.3 steps 1–8, ruling round 1 R2.6) and `inspect_structure` (R1.5).

Design note `docs/design/T07-jobs-and-bindings.md` §5.3, §5.8, §10.5 (I3), ruling round 1 R2.3,
R2.6, R1.5 and R5. Every refusal is a typed `ApiError` that validates against
`schemas/api-error.schema.json`, with the `detail` member §5.8 names for its code; the first
failing step is the one reported. The expectations are the note's, not read back from the code.
"""

from __future__ import annotations

from typing import Any

import pytest
from t07_corpus import CORPUS
from test_t06_w4_registry import REGISTRY
from test_t07_w3b_validation import ALREADY_READY, MOVED_TO_READY

import openflowsheet.application.admission as admission_module
from openflowsheet.application.admission import SolveAdmission, admit_budgets, admit_solve
from openflowsheet.application.binding import Unbound
from openflowsheet.application.policies import ROUTE_DEFAULT_POLICY
from openflowsheet.application.revision_run import (
    NoRoute,
    Route,
    route_structure,
    select_route,
)
from openflowsheet.application.types import ApiError, Budgets, Limits, SolveBody, schema_errors
from openflowsheet.application.validation import structural_refusal, validate
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.revision import plan_revision
from openflowsheet.run.manifest import policy_sha256
from openflowsheet.verify.certificate import REGISTERED_POLICY_ID, CheckPolicy
from openflowsheet.verify.checks import KIND_TOLERANCE

READY = sorted(MOVED_TO_READY | ALREADY_READY)
#: `project grant`'s agent defaults (§5.9).
AGENT = Limits(default_wall_time_s=300, max_wall_time_s=1800, max_active_jobs=4)
NONE = Limits()


def _admit(
    name: str | None,
    *,
    limits: Limits = AGENT,
    active_jobs: int = 0,
    budgets: Budgets | None = None,
    **body: Any,
) -> SolveAdmission | ApiError:
    document = CORPUS[name]() if name is not None else None
    return admit_solve(
        name or "no-such-revision",
        document,
        SolveBody(revision_id=name or "no-such-revision", **body),
        budgets=budgets or Budgets(),
        limits=limits,
        active_jobs=active_jobs,
    )


def _refused(result: SolveAdmission | ApiError, code: str) -> ApiError:
    assert isinstance(result, ApiError), result
    assert result.code == code, result
    assert schema_errors("api-error.schema.json", result.as_document()) == []
    return result


# -- admitted -----------------------------------------------------------------------------------


@pytest.mark.parametrize("name", READY)
def test_every_ready_corpus_revision_is_admitted_on_its_route(name: str) -> None:
    for policy_id in ("default", "T06-revision-v2"):
        admitted = _admit(name, policy_id=policy_id)
        assert isinstance(admitted, SolveAdmission), admitted
        route = select_route(CORPUS[name]())
        assert isinstance(route, Route)
        assert admitted.route.solve_path == route.solve_path
        assert admitted.policy_requested == policy_id
        resolved = ROUTE_DEFAULT_POLICY[route.solve_path] if policy_id == "default" else policy_id
        assert admitted.policy.policy_id == resolved
        assert policy_sha256(admitted.policy) == REGISTRY["policies"][resolved]["sha256"]
        # R5: tightening factor 1 is the registered check policy byte for byte.
        assert admitted.check_policy.sha256 == CheckPolicy().sha256
        assert admitted.check_policy.is_registered
        assert admitted.wall_time_s == AGENT.default_wall_time_s


def test_a_named_policy_is_honoured_on_either_route() -> None:
    """R2.3: `T04-W12` on a `revision_eo` revision, `T06-revision-v2` on a `legacy_eo` one."""
    on_revision = _admit("SYN-001-T06-NET03", policy_id="T04-W12")
    on_legacy = _admit("SYN-001-A02-360", policy_id="T06-revision-v2")
    assert isinstance(on_revision, SolveAdmission) and isinstance(on_legacy, SolveAdmission)
    assert (on_revision.route.solve_path, on_revision.policy.policy_id) == (
        "revision_eo",
        "T04-W12",
    )
    assert (on_legacy.route.solve_path, on_legacy.policy.policy_id) == (
        "legacy_eo",
        "T06-revision-v2",
    )


# -- steps 1–3 ----------------------------------------------------------------------------------


def test_step1_a_missing_revision_is_not_found() -> None:
    error = _refused(_admit(None), "not_found")
    assert error.detail["revision_id"] == "no-such-revision"


@pytest.mark.parametrize(
    ("name", "status"),
    [
        ("SYN-001-T06-STR02", "DRAFT"),
        ("SYN-001-T06-STR06", "INVALID"),
        ("SYN-001-conflicting-heater-spec", "INVALID"),
    ],
)
def test_step2_a_revision_not_ready_is_refused_with_its_report(name: str, status: str) -> None:
    # A later step's fault (an unknown policy) is not reached: the first failing step reports.
    error = _refused(_admit(name, policy_id="no-such-policy"), "revision_not_ready")
    report = validate(CORPUS[name]())
    expected = report.as_document()
    actual = dict(error.detail["report"])
    assert actual["status"] == status
    assert {k: v for k, v in actual.items() if k != "provenance"} == {
        k: v for k, v in expected.items() if k != "provenance"
    }


def test_step3_no_route_is_revision_unsupported(monkeypatch: pytest.MonkeyPatch) -> None:
    """R2.6. G9 (a)/(d) make it unreachable after `READY` on the corpus, so a `READY` revision's
    route is replaced by `NoRoute`."""
    none = NoRoute(
        Unbound("unsupported", "revision-reason", hint="revision-hint"),
        Unbound("incomplete", "legacy-reason"),
    )
    monkeypatch.setattr(admission_module, "select_route", lambda document: none)
    error = _refused(_admit("SYN-001-T06-NET03"), "revision_unsupported")
    assert error.detail["unbound"] == ("unsupported(revision-reason); incomplete(legacy-reason)")
    # Ruling round 6, B1 item 4: the revision binder's hint.
    assert error.detail["hint"] == "revision-hint"


def test_step3_a_legacy_route_not_admitted_carries_the_revision_binders_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R2.6 as amended by ruling round 6, B1: the legacy reason is
    `unsupported(legacy_route_not_admitted(<code>))` and `detail.hint` the revision binder's."""
    from t07_v17_c1_documents import c1_document, schema_conformant

    document = schema_conformant(c1_document("T02-2", "rev-000002"))
    route = select_route(document)
    assert isinstance(route, NoRoute)
    monkeypatch.setattr(admission_module, "select_route", lambda document: route)
    error = _refused(_admit("SYN-001-T06-NET03"), "revision_unsupported")
    assert error.detail["unbound"] == (
        "incomplete(specification_missing(S4.P)); "
        "unsupported(legacy_route_not_admitted(specification_missing))"
    )
    assert error.detail["hint"] == route.revision.hint
    assert error.detail["hint"] is not None and "path: state.P" in error.detail["hint"]


# -- step 4 -------------------------------------------------------------------------------------


@pytest.mark.parametrize("policy_id", ["no-such-policy", ""])
def test_step4_an_unregistered_policy_is_not_found(policy_id: str) -> None:
    error = _refused(_admit("SYN-001-T06-NET03", policy_id=policy_id), "not_found")
    assert error.detail["policy_id"] == policy_id


@pytest.mark.parametrize("policy_id", ["T05b-v2", "SYN-001-K03", "T06-revision-v1"])
def test_step4_a_registered_policy_not_offered_is_unsupported(policy_id: str) -> None:
    """Registered in the benchmark registry is not offered by the application (§12.2); V17 spec
    F3 (`v17-c1` B3) refuses it `unsupported`, not `not_found` (`test_t07_b3_policies.py`)."""
    error = _refused(_admit("SYN-001-T06-NET03", policy_id=policy_id), "unsupported")
    assert error.detail["policy_id"] == policy_id


def test_step4_a_listed_pair_is_unsupported(monkeypatch: pytest.MonkeyPatch) -> None:
    assert admission_module.POLICY_UNSUPPORTED_ON_ROUTE == frozenset()
    monkeypatch.setattr(
        admission_module,
        "POLICY_UNSUPPORTED_ON_ROUTE",
        frozenset({("T04-W12", "revision_eo")}),
    )
    error = _refused(_admit("SYN-001-T06-NET03", policy_id="T04-W12"), "unsupported")
    assert error.message == "policy_unsupported_on_route(T04-W12,revision_eo)"
    # `"default"` resolves to the route's own policy, which is not listed.
    assert isinstance(_admit("SYN-001-T06-NET03"), SolveAdmission)


# -- step 5 (I3, R5) ----------------------------------------------------------------------------


@pytest.mark.parametrize("kind", sorted(KIND_TOLERANCE))
@pytest.mark.parametrize("factor", [1.0, 0.5, 0.1, 0.01])
def test_step5_a_tightened_check_tolerance_is_admitted(kind: str, factor: float) -> None:
    value = KIND_TOLERANCE[kind] * factor
    admitted = _admit("SYN-001-T06-NET03", check_tolerances={kind: value})
    assert isinstance(admitted, SolveAdmission)
    assert admitted.check_policy.policy_id == REGISTERED_POLICY_ID
    assert admitted.check_policy.tolerances[kind] == value
    assert admitted.check_policy.relaxations() == []
    assert admitted.check_policy.is_registered is (factor == 1.0)


@pytest.mark.parametrize("kind", sorted(KIND_TOLERANCE))
def test_step5_a_looser_check_tolerance_is_refused(kind: str) -> None:
    looser = KIND_TOLERANCE[kind] * 1.0000001
    error = _refused(
        _admit("SYN-001-T06-NET03", check_tolerances={kind: looser}),
        "verification_weakening_refused",
    )
    assert error.detail["kind"] == kind
    assert error.message == f"verification_weakening_refused({kind})"


def test_step5_an_unknown_kind_is_invalid_request() -> None:
    error = _refused(
        _admit("SYN-001-T06-NET03", check_tolerances={"no_such_kind": 1e-12}), "invalid_request"
    )
    assert error.detail["pointer"] == "/body/check_tolerances/no_such_kind"


# -- steps 6–8 ----------------------------------------------------------------------------------


def test_step6_the_property_call_budget_only_tightens() -> None:
    # `SolvePolicy.max_property_calls` of `T06-revision-v2`: the registered constant.
    ceiling = 10_000
    admitted = _admit("SYN-001-T06-NET03", max_property_calls=5000)
    assert isinstance(admitted, SolveAdmission)
    assert admitted.policy.max_property_calls == 5000
    # The effective policy is the one hashed: a tightened budget is a different policy document.
    assert policy_sha256(admitted.policy) != REGISTRY["policies"]["T06-revision-v2"]["sha256"]
    same = _admit("SYN-001-T06-NET03", max_property_calls=ceiling)
    assert isinstance(same, SolveAdmission)
    assert policy_sha256(same.policy) == REGISTRY["policies"]["T06-revision-v2"]["sha256"]
    error = _refused(
        _admit("SYN-001-T06-NET03", max_property_calls=ceiling + 1), "budget_exceeds_ceiling"
    )
    assert error.detail["budget"] == "max_property_calls"


def test_step7_the_wall_time_is_within_the_capabilitys_ceiling() -> None:
    error = _refused(
        _admit("SYN-001-T06-NET03", budgets=Budgets(wall_time_s=1800.5)), "budget_exceeds_ceiling"
    )
    assert error.detail["budget"] == "wall_time_s"
    admitted = _admit("SYN-001-T06-NET03", budgets=Budgets(wall_time_s=1800))
    assert isinstance(admitted, SolveAdmission) and admitted.wall_time_s == 1800
    unlimited = _admit("SYN-001-T06-NET03", limits=NONE, budgets=Budgets(wall_time_s=1e9))
    assert isinstance(unlimited, SolveAdmission) and unlimited.wall_time_s == 1e9
    unset = _admit("SYN-001-T06-NET03", limits=NONE)
    assert isinstance(unset, SolveAdmission) and unset.wall_time_s is None


# -- ruling round 5b, S5: the ceiling bounds the default and the absence of one --------------


def test_s5_t1_limits_refuses_a_default_above_the_ceiling_and_a_non_positive_wall_time() -> None:
    with pytest.raises(ValueError, match="default_wall_time_s 3600 exceeds max_wall_time_s 1800"):
        Limits(default_wall_time_s=3600, max_wall_time_s=1800)
    for default, ceiling in ((1800, 1800), (None, None), (300, None), (None, 1800)):
        Limits(default_wall_time_s=default, max_wall_time_s=ceiling)
    for field in ("default_wall_time_s", "max_wall_time_s"):
        for value in (0, -1, float("nan"), float("inf")):
            with pytest.raises(ValueError, match=f"{field} .* is not a finite number > 0"):
                Limits(**{field: value})


def test_s5_t2_the_budget_is_the_requests_else_the_default_else_the_ceiling() -> None:
    ceiling_only = Limits(max_wall_time_s=10)
    assert admit_budgets(Budgets(), ceiling_only, 0) == 10.0
    assert admit_budgets(Budgets(), Limits(default_wall_time_s=5, max_wall_time_s=10), 0) == 5.0
    assert admit_budgets(Budgets(wall_time_s=7), ceiling_only, 0) == 7.0
    _refused(admit_budgets(Budgets(wall_time_s=11), ceiling_only, 0), "budget_exceeds_ceiling")
    assert admit_budgets(Budgets(), Limits(), 0) is None


def test_step8_the_active_job_limit() -> None:
    assert isinstance(_admit("SYN-001-T06-NET03", active_jobs=3), SolveAdmission)
    error = _refused(_admit("SYN-001-T06-NET03", active_jobs=4), "limit_exceeded")
    assert error.retryable is True
    assert error.detail["max_active_jobs"] == 4
    assert isinstance(_admit("SYN-001-T06-NET03", limits=NONE, active_jobs=99), SolveAdmission)


def test_the_first_failing_step_is_reported() -> None:
    """Steps 4–8 all fail here; step 4 is reported."""
    error = _refused(
        _admit(
            "SYN-001-T06-NET03",
            policy_id="no-such-policy",
            check_tolerances={"molar_flow": 1.0},
            max_property_calls=10**9,
            budgets=Budgets(wall_time_s=1e9),
            active_jobs=99,
        ),
        "not_found",
    )
    assert error.detail["policy_id"] == "no-such-policy"


# -- inspect_structure (R1.5) -------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(CORPUS))
def test_inspect_structure_reports_the_formulation_solve_uses(name: str) -> None:
    document = CORPUS[name]()
    structure = route_structure(document)
    route = select_route(CORPUS[name]())
    if isinstance(route, NoRoute):
        # `validate()`'s reason, or the route's where validate analysed a declaration no route
        # solves (the conflicting spec, since ruling round 6, B1); and the hint of the refusal
        # validate reports, if it reports one (ruling round 6, B1 item 4).
        refusal = structural_refusal(CORPUS[name]())
        # ADR 0019 Amendment 3 (A3.1) adds three members, by addition only (M06 WO-1).
        added = {"validation_structural_report", "rows", "columns"}
        assert added <= set(structure)
        assert {key: value for key, value in structure.items() if key not in added} == {
            "not_run_reason": validate(CORPUS[name]()).structural_counts_absent_reason
            or route.reason,
            "hint": None if refusal is None else refusal.hint,
        }
        return
    assert isinstance(route, Route)
    assert structure["solve_path"] == route.solve_path
    assert structure["route_reason"] == route.reason
    if route.solve_path == "revision_eo":
        # The plan builder's own analysis: what `solve` plans from.
        plan, report = plan_revision(route.binding, _default_policy(route))
        assert isinstance(plan, ExecutionPlan)
        assert structure["structural_report"] == report.as_document()


def _default_policy(route: Route) -> Any:
    from openflowsheet.application.policies import resolve_policy

    return resolve_policy("default", route.solve_path)


def test_inspect_structure_names_the_revision_formulation_where_validate_names_the_legacy() -> None:
    """R1.3/R1.5: NET-09 validates on the SYN-001 declaration (49/47/47) and solves, and is
    inspected, on its revision-built formulation (50/48/48)."""
    structure = route_structure(CORPUS["SYN-001-T06-NET09"]())
    counts = structure["structural_report"]["structural_counts"]
    assert structure["solve_path"] == "revision_eo"
    assert (counts["equations"], counts["free_variables"], counts["matched"]) == (50, 48, 48)
    report = validate(CORPUS["SYN-001-T06-NET09"]())
    assert report.structural_counts is not None
    assert (
        report.structural_counts["equations"],
        report.structural_counts["free_variables"],
        report.structural_counts["matched"],
    ) == (49, 47, 47)
