"""Semantic admission of a solve (T07 design note §5.3 steps 1–8, as amended by ruling round 1).

`admit_solve` runs after the request has passed its schema, its canonical check and the idempotency
ledger (§4.2 `submit_job` steps 1–6), and before a job exists. Its answer is either a
`SolveAdmission` — the route, the resolved and effective policies and budgets the job will run
under — or the first refusal, as a typed `ApiError` (`schemas/api-error.schema.json`). A refusal
creates no job and no ledger row (§5.3); the caller audits it.

The steps, in order:

1. the revision exists, else `not_found`;
2. `validate(revision, "simulation")` is `READY_FOR_SIMULATION`, else `revision_not_ready` with the
   report in `detail.report`;
3. `select_route` gives a route, else `revision_unsupported` with `detail.unbound` =
   `<revision reason>; <legacy reason>` (R2.6) and `detail.hint`, the revision binder's hint
   (ruling round 6, B1);
4. `policy_id` is `"default"` or offered; a registered id that is not offered is `unsupported`
   (V17 spec F3), any other `not_found`; a (policy, route) pair listed in
   `POLICY_UNSUPPORTED_ON_ROUTE` is refused (R2.3; the list is empty — W3a measured no pair that
   raises untyped, `docs/t07-measurements.md` W3a.4);
5. each `check_tolerances` value is at most the registered `KIND_TOLERANCE` value, else
   `verification_weakening_refused` naming the kind; an unknown kind is `invalid_request` (I3);
6. `max_property_calls` is at most the resolved policy's, else `budget_exceeds_ceiling`;
7. `wall_time_s` is at most the capability's `max_wall_time_s`, else `budget_exceeds_ceiling`;
8. the caller's active jobs are fewer than `max_active_jobs`, else `limit_exceeded`.

A `reproduce` is admitted by `admit_reproduce`: its bundle artifact exists (`not_found`) and is a
`replay_bundle` (`invalid_request`), then steps 7–8, which bound every job (`admit_budgets`).
An `experiment` (ADR 0033 D9, M02 design note §3.5) by `admit_experiment`: its model reference
resolves to a registered variant whose SHA-256 is `artifact_ref` (`invalid_request` at
`/body/model/artifact_ref`), its components are the variant's boundary's, in order, with one flow
each (`invalid_request` at `/body/inlet/components` or `/body/inlet/n`), then steps 7–8.
A `surrogate_study` (ADR 0037 D6, M04 spec §10.3) by `admit_surrogate_study`: its parent resolves
to a registered variant (`invalid_request` at `/body/parent/variant_sha256`) and its plan is
registered for that parent with every request inside the box, the hard domain and the data domain
(`invalid_request` at `/body/plan_id`, detail `reason` the plan guard's code); an `it<i>`,
i ≥ 2, is admitted only when the project's manifests of `it1` … `it<i−1>` of the same parent each
failed on the coverage test alone (`iteration_not_permitted`, spec §18 A1.2); then steps 7–8.

**Only tightening is admitted** (I3). The effective check policy keeps `REGISTERED_POLICY_ID`, so
tightening factor 1 is the registered policy byte for byte (R5); the effective solve policy is the
resolved one with `max_property_calls` replaced when the request lowers it, and it is the one
hashed and stored (ADR 0020 D3).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Final

from openflowsheet.adapters import variants
from openflowsheet.application.policies import (
    APPLICATION_POLICIES,
    DEFAULT_POLICY_ID,
    REGISTERED_POLICY_IDS,
    SolvePath,
    resolve_policy,
)
from openflowsheet.application.revision_run import Route, select_route
from openflowsheet.application.store import ProjectStore
from openflowsheet.application.types import (
    ApiError,
    Budgets,
    ExperimentBody,
    Limits,
    ReproduceBody,
    SolveBody,
    SurrogateStudyBody,
)
from openflowsheet.application.validation import validate
from openflowsheet.canonical import file_sha256
from openflowsheet.models.c1 import COMPONENTS as C1_COMPONENTS
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.studies.surrogate.iterations import StoredManifest
from openflowsheet.studies.surrogate.iterations import predecessors as iteration_predecessors
from openflowsheet.studies.surrogate.plan import PlanRefusedError
from openflowsheet.studies.surrogate.study import prepare
from openflowsheet.verify.certificate import REGISTERED_POLICY_ID, CheckPolicy
from openflowsheet.verify.checks import KIND_TOLERANCE

__all__ = [
    "POLICY_UNSUPPORTED_ON_ROUTE",
    "SolveAdmission",
    "admit_budgets",
    "admit_experiment",
    "admit_surrogate_study",
    "stored_surrogate_manifests",
    "admit_reproduce",
    "admit_solve",
    "resolve_policies",
]

#: R2.3: (policy id, route) pairs a named policy may not run on, each logged with the untyped
#: error that put it here. Empty: no registered pair raised untyped over the corpus (W3a.4).
POLICY_UNSUPPORTED_ON_ROUTE: Final[frozenset[tuple[str, SolvePath]]] = frozenset()


@dataclass(frozen=True)
class SolveAdmission:
    """What an admitted solve runs: the route, and the policies and budgets in effect."""

    revision_id: str
    route: Route
    #: The id as submitted (`"default"` or a registered id) — `solve-path.json`'s
    #: `policy_requested`; `request_sha256` hashes the request as submitted (R2.3).
    policy_requested: str
    #: The resolved and tightened policy: `RunResult.policy_id`/`policy_sha256` and
    #: `solve-policy.json` carry it.
    policy: SolvePolicy
    check_policy: CheckPolicy
    #: The job's wall-time budget: the request's, else the capability's default, else none.
    wall_time_s: float | None


def _error(code: Any, message: str, **detail: Any) -> ApiError:
    return ApiError(code=code, message=message, retryable=code == "limit_exceeded", detail=detail)


def admit_solve(
    revision_id: str,
    document: Mapping[str, Any] | None,
    body: SolveBody,
    *,
    budgets: Budgets,
    limits: Limits,
    active_jobs: int,
) -> SolveAdmission | ApiError:
    """§5.3's semantic admission of `body` for the stored revision `document` (`None` when the
    store has no revision `revision_id`). `limits` are the caller's capability's; `active_jobs`
    counts the caller's queued and running jobs."""
    # 1. The revision exists.
    if document is None:
        return _error("not_found", f"no revision {revision_id!r}", revision_id=revision_id)

    # 2. It is ready for simulation.
    report = validate(document, "simulation")
    if report.status != "READY_FOR_SIMULATION":
        return _error(
            "revision_not_ready",
            f"revision {revision_id!r} validates {report.status}, not READY_FOR_SIMULATION",
            report=report.as_document(),
        )

    # 3. A route exists (R2.6).
    route = select_route(document)
    if not isinstance(route, Route):
        return _error(
            "revision_unsupported",
            f"no solve route binds revision {revision_id!r}",
            unbound=route.reason,
            hint=route.hint,
        )

    # 4–6. The policies the solve runs under.
    resolved = resolve_policies(route, body)
    if isinstance(resolved, ApiError):
        return resolved
    policy, check_policy = resolved

    # 7–8. The wall time and the caller's active jobs are within the capability's limits.
    wall_time_s = admit_budgets(budgets, limits, active_jobs)
    if isinstance(wall_time_s, ApiError):
        return wall_time_s

    return SolveAdmission(
        revision_id=revision_id,
        route=route,
        policy_requested=body.policy_id,
        policy=policy,
        check_policy=check_policy,
        wall_time_s=wall_time_s,
    )


def resolve_policies(route: Route, body: SolveBody) -> tuple[SolvePolicy, CheckPolicy] | ApiError:
    """§5.3 steps 4–6 on an admitted route: the effective solve policy and check policy of `body`,
    or the first refusal. Pure, and shared by admission and the job runner, which re-resolves a
    job's request at its `resolve` stage (§6.4) rather than trusting a stored copy."""
    # 4. The policy is `"default"` or registered, and not refused on this route. A policy the
    # registry registers but the contract does not offer is `unsupported` (V17 spec F3; `v17-c1`
    # B3: "no registered solve policy" was false for it); an unknown id stays `not_found`.
    if body.policy_id != DEFAULT_POLICY_ID and body.policy_id not in APPLICATION_POLICIES:
        if body.policy_id in REGISTERED_POLICY_IDS:
            return _error(
                "unsupported",
                f"solve policy {body.policy_id!r} is registered but not offered in v0.1",
                policy_id=body.policy_id,
                offered=sorted(APPLICATION_POLICIES),
            )
        return _error(
            "not_found",
            f"no registered solve policy {body.policy_id!r}",
            policy_id=body.policy_id,
            registered=sorted(APPLICATION_POLICIES),
        )
    policy = resolve_policy(body.policy_id, route.solve_path)
    assert policy is not None
    if (policy.policy_id, route.solve_path) in POLICY_UNSUPPORTED_ON_ROUTE:
        return _error(
            "unsupported",
            f"policy_unsupported_on_route({policy.policy_id},{route.solve_path})",
            policy_id=policy.policy_id,
            solve_path=route.solve_path,
        )

    # 5. Check tolerances only tighten (I3).
    for kind, value in sorted(body.check_tolerances.items()):
        if kind not in KIND_TOLERANCE:
            return _error(
                "invalid_request",
                f"check_tolerances names no registered quantity kind {kind!r}",
                pointer=f"/body/check_tolerances/{kind}",
                registered=sorted(KIND_TOLERANCE),
            )
        if not value <= KIND_TOLERANCE[kind]:
            return _error(
                "verification_weakening_refused",
                f"verification_weakening_refused({kind})",
                kind=kind,
                registered=KIND_TOLERANCE[kind],
                requested=value,
            )
    check_policy = CheckPolicy(
        policy_id=REGISTERED_POLICY_ID,
        tolerances={**KIND_TOLERANCE, **body.check_tolerances},
    )

    # 6. The property-call budget only tightens the policy's.
    if body.max_property_calls is not None:
        if body.max_property_calls > policy.max_property_calls:
            return _error(
                "budget_exceeds_ceiling",
                "budget_exceeds_ceiling(max_property_calls)",
                budget="max_property_calls",
                requested=body.max_property_calls,
                ceiling=policy.max_property_calls,
            )
        policy = replace(policy, max_property_calls=body.max_property_calls)

    return policy, check_policy


def admit_budgets(budgets: Budgets, limits: Limits, active_jobs: int) -> float | None | ApiError:
    """§5.3 steps 7–8, which bound any job, not only a solve: the job's wall-time budget (the
    request's, else the capability's default, else the ceiling, else none; §8.3), or the first
    refusal. Only the request's value is checked against the ceiling: the default and the ceiling
    are within it by the `Limits` invariant (ruling round 5b, S5)."""
    # 7. The wall time is within the capability's ceiling.
    wall_time_s = budgets.wall_time_s
    if (
        wall_time_s is not None
        and limits.max_wall_time_s is not None
        and wall_time_s > limits.max_wall_time_s
    ):
        return _error(
            "budget_exceeds_ceiling",
            "budget_exceeds_ceiling(wall_time_s)",
            budget="wall_time_s",
            requested=wall_time_s,
            ceiling=limits.max_wall_time_s,
        )
    if wall_time_s is None:
        wall_time_s = limits.default_wall_time_s
    if wall_time_s is None:
        wall_time_s = limits.max_wall_time_s

    # 8. The caller's active jobs are below the limit.
    refused = active_jobs_refusal(limits, active_jobs)
    if refused is not None:
        return refused
    return wall_time_s


def active_jobs_refusal(limits: Limits, active_jobs: int) -> ApiError | None:
    """§5.3 step 8: `limit_exceeded(max_active_jobs)` when the caller's `active_jobs` are not
    below the capability's limit. Admission checks it early; the store checks it again inside
    the accepting transaction, where the count cannot change (T07 review S4)."""
    if limits.max_active_jobs is not None and active_jobs >= limits.max_active_jobs:
        return _error(
            "limit_exceeded",
            "limit_exceeded(max_active_jobs)",
            limit="max_active_jobs",
            active_jobs=active_jobs,
            max_active_jobs=limits.max_active_jobs,
        )
    return None


def admit_reproduce(
    bundle_kind: str | None,
    body: ReproduceBody,
    *,
    budgets: Budgets,
    limits: Limits,
    active_jobs: int,
) -> float | None | ApiError:
    """§5.3's admission of a `reproduce`: the bundle artifact exists (`bundle_kind` is its
    registered kind, `None` when there is no such artifact) and is a `replay_bundle`, then steps
    7–8. The job's wall-time budget, or the first refusal."""
    if bundle_kind is None:
        return _error(
            "not_found",
            f"no artifact {body.bundle_artifact_id!r}",
            artifact_id=body.bundle_artifact_id,
        )
    if bundle_kind != "replay_bundle":
        return _error(
            "invalid_request",
            f"artifact {body.bundle_artifact_id!r} is a {bundle_kind}, not a replay_bundle",
            pointer="/body/bundle_artifact_id",
            kind=bundle_kind,
        )
    return admit_budgets(budgets, limits, active_jobs)


def admit_experiment(
    body: ExperimentBody,
    *,
    budgets: Budgets,
    limits: Limits,
    active_jobs: int,
) -> tuple[variants.Variant, float | None] | ApiError:
    """§3.5's admission of an `experiment`: the variant, then the inlet's components, then steps
    7–8. The resolved variant and the job's wall-time budget, or the first refusal."""
    model = body.model
    variant = variants.resolve(model.id, model.version, model.artifact_ref)
    if variant is None:
        return _error(
            "invalid_request",
            f"model {model.id!r} @ {model.version!r} with artifact_ref {model.artifact_ref!r} is "
            "not a registered variant at that SHA-256",
            pointer="/body/model/artifact_ref",
        )
    if body.inlet.components != C1_COMPONENTS:
        return _error(
            "invalid_request",
            f"the variant's components are {list(C1_COMPONENTS)}, in that order",
            pointer="/body/inlet/components",
        )
    if len(body.inlet.n) != len(body.inlet.components):
        return _error(
            "invalid_request",
            "n has one flow per component",
            pointer="/body/inlet/n",
        )
    wall_time_s = admit_budgets(budgets, limits, active_jobs)
    if isinstance(wall_time_s, ApiError):
        return wall_time_s
    return variant, wall_time_s


def stored_surrogate_manifests(store: ProjectStore, root: Path) -> list[StoredManifest]:
    """Every SurrogateManifest artifact of the project whose file is intact (its bytes hash to
    the row's SHA-256), with that SHA-256 — what an iteration's admission judges (spec §18
    A1.2). A file that no longer matches its row is not that manifest and is not read."""
    found = []
    for row in store.artifacts_of_kind("surrogate_manifest"):
        path = root / row.relpath
        if path.is_file() and file_sha256(path) == row.sha256:
            found.append(StoredManifest(row.sha256, json.loads(path.read_bytes())))
    return found


def admit_surrogate_study(
    body: SurrogateStudyBody,
    *,
    budgets: Budgets,
    limits: Limits,
    active_jobs: int,
    manifests: Callable[[], Sequence[StoredManifest]] = list,
) -> float | None | ApiError:
    """M04 spec §10.3's admission of a `surrogate_study`: the parent is a registered variant, the
    plan is registered for it and every request lies in the box, the hard domain and the data
    domain (spec §5.1, M04.A03); an `it<i>`, i ≥ 2, only when the earlier iterations' manifests
    permit it (`manifests`, read only then; spec §18 A1.2, `iteration_not_permitted`); then steps
    7–8. The job's wall-time budget, or the first refusal, with the guard's code in
    `detail.reason`. The budget of cold experiments is judged by the study against the cache."""
    parent = body.parent
    variant = variants.resolve(parent.model_id, parent.variant_id, parent.variant_sha256)
    if variant is None:
        return _error(
            "invalid_request",
            f"model {parent.model_id!r} @ {parent.variant_id!r} with SHA-256 "
            f"{parent.variant_sha256!r} is not a registered variant at that SHA-256",
            pointer="/body/parent/variant_sha256",
        )
    try:
        plan = prepare(variant, body.plan_id)
        if plan.iteration > 1:
            iteration_predecessors(variant, body.plan_id, manifests())
    except PlanRefusedError as refused:
        return _error(
            "invalid_request",
            str(refused),
            pointer="/body/plan_id",
            reason=refused.code,
        )
    return admit_budgets(budgets, limits, active_jobs)
