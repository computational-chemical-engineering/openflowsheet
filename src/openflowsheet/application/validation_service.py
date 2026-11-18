"""`ValidationService`: validation, the admission check and structure inspection of a stored
revision, and the job admission they share with the job service (ADR 0076 I-12d, above
`RevisionService`).

`LocalApplication` delegates `validate`, `check_admission` and `inspect_structure` here; their
contract documentation is the facade's. A job's semantic admission (`admit`, §5.3) is shared
with the job service above.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, get_args

from openflowsheet.application import capabilities, validation
from openflowsheet.application.admission import (
    admit_experiment,
    admit_optimize,
    admit_reproduce,
    admit_solve,
    admit_surrogate_study,
    stored_surrogate_manifests,
)
from openflowsheet.application.contract import Projection
from openflowsheet.application.errors import ApiError, ApplicationError
from openflowsheet.application.inspection_types import AdmissionReport
from openflowsheet.application.job_records import EffectiveBudgets
from openflowsheet.application.job_requests import (
    ExperimentBody,
    JobRequest,
    OptimizeBody,
    ReproduceBody,
    SolveBody,
    SurrogateStudyBody,
)
from openflowsheet.application.policy_types import CapabilityReference
from openflowsheet.application.revision_service import RevisionService
from openflowsheet.application.service_core import ServiceCore
from openflowsheet.application.structure_inspection import route_structure
from openflowsheet.application.validation_report import Task, ValidationReport
from openflowsheet.canonical import document_sha256
from openflowsheet.registry import default_registry

TASKS: tuple[str, ...] = get_args(Task)


class ValidationService:
    """The validation operations over one caller's `ServiceCore`. Each public method is the
    `LocalApplication` method of the same name, documented there; it takes every argument
    explicitly (the defaults are the facade's). Public methods without a facade namesake serve the
    services above this one."""

    def __init__(self, core: ServiceCore, revisions: RevisionService) -> None:
        self._core = core
        self._revisions = revisions

    def validate(
        self, revision_id: str, task: Task, optimization: Mapping[str, Any] | None
    ) -> ValidationReport:
        self._core.authorize("validate")
        if task not in TASKS:
            self._core.refuse(
                "invalid_request",
                f"task is one of {list(TASKS)}",
                operation="validate",
                pointer="/task",
            )
        if task == "optimization":
            # OPT design §4.11 (ADR 0071 D8, lifting R-129 and U05's refusal): the solver probe
            # first, at U05's place, before the revision is read; then the request.
            from openflowsheet.studies.nlp.closure import audited_solver

            availability = audited_solver()
            if not availability.available:
                self._core.refuse(
                    "unsupported",
                    "nlp_solver_unavailable",
                    operation="validate",
                    pointer="/task",
                )
            if optimization is None:
                self._core.refuse(
                    "invalid_request",
                    "task optimization needs an optimization request",
                    operation="validate",
                    pointer="/optimization",
                )
        with self._core.store.reading() as connection:
            revision = self._core.store.get_revision(connection, revision_id)
        if revision is None:
            self._core.refuse(
                "not_found", "no such revision", operation="validate", revision_id=revision_id
            )
        if task != "optimization":
            return validation.validate(
                revision.as_document(), task, surrogates=self._core.surrogates()
            )
        return validation.validate(
            revision.as_document(),
            task,
            surrogates=self._core.surrogates(),
            optimization=optimization,
            solver_probe=lambda: availability,
        )

    def admit(
        self,
        request: JobRequest,
        caller: CapabilityReference,
        operation: str,
        request_sha256: str,
    ) -> EffectiveBudgets:
        """§5.3's semantic admission; a refusal creates no job and no ledger row, and is
        audited. The effective budgets the job will run under.

        One admission per job family: `_solve_admission`, `_experiment_admission`,
        `_surrogate_study_admission`, `_optimize_admission` and `_reproduce_admission`. Raised: the
        family's refusal (`ServiceCore.refuse_error`)."""
        active = self._core.store.active_job_count(caller.principal_id)
        body = request.body
        budgets: EffectiveBudgets | ApiError
        if isinstance(body, SolveBody):
            budgets = self._solve_admission(body, request, caller, active)
        elif isinstance(body, ExperimentBody):
            budgets = self._experiment_admission(body, request, caller, active)
        elif isinstance(body, SurrogateStudyBody):
            budgets = self._surrogate_study_admission(body, request, caller, active)
        elif isinstance(body, OptimizeBody):
            budgets = self._optimize_admission(body, request, caller, active)
        else:
            budgets = self._reproduce_admission(body, request, caller, active)
        if isinstance(budgets, ApiError):
            self._core.refuse_error(budgets, operation, request_sha256)
        return budgets

    def _solve_admission(
        self, body: SolveBody, request: JobRequest, caller: CapabilityReference, active: int
    ) -> EffectiveBudgets | ApiError:
        """`admit_solve` on the revision and the declared warm-start source as the store is at
        admission: the solve's budgets, or the refusal."""
        store = self._core.store
        declared = body.warm_start.job_id if body.warm_start is not None else None
        with store.reading() as connection:
            revision = store.get_revision(connection, body.revision_id)
            # ADR 0070 A1: the declared source, as the store is at admission.
            source = store.solution_of_job(connection, declared) if declared is not None else None
        admission = admit_solve(
            body.revision_id,
            revision.as_document() if revision is not None else None,
            body,
            budgets=request.budgets,
            limits=caller.limits,
            active_jobs=active,
            surrogates=self._core.surrogates(),
            warm_source_found=source is not None,
        )
        if isinstance(admission, ApiError):
            return admission
        return EffectiveBudgets(
            wall_time_s=admission.wall_time_s,
            max_property_calls=admission.policy.max_property_calls,
        )

    def _experiment_admission(
        self, body: ExperimentBody, request: JobRequest, caller: CapabilityReference, active: int
    ) -> EffectiveBudgets | ApiError:
        """`admit_experiment`: the experiment's budgets, or the refusal."""
        admitted = admit_experiment(
            body, budgets=request.budgets, limits=caller.limits, active_jobs=active
        )
        if isinstance(admitted, ApiError):
            return admitted
        # R-233: an experiment's property calls are its own, never a solve's budget.
        return EffectiveBudgets(wall_time_s=admitted[1], max_property_calls=None)

    def _surrogate_study_admission(
        self,
        body: SurrogateStudyBody,
        request: JobRequest,
        caller: CapabilityReference,
        active: int,
    ) -> EffectiveBudgets | ApiError:
        """`admit_surrogate_study` against the stored surrogate manifests: the study's budgets,
        or the refusal."""
        store = self._core.store
        study = admit_surrogate_study(
            body,
            budgets=request.budgets,
            limits=caller.limits,
            active_jobs=active,
            manifests=lambda: stored_surrogate_manifests(store, self._core.files_root),
        )
        if isinstance(study, ApiError):
            return study
        # R-233 again: a study's experiments are experiments; their calls are their own.
        return EffectiveBudgets(wall_time_s=study, max_property_calls=None)

    def _optimize_admission(
        self, body: OptimizeBody, request: JobRequest, caller: CapabilityReference, active: int
    ) -> EffectiveBudgets | ApiError:
        """`admit_optimize`: the optimization's budgets, or the refusal."""
        optimize = admit_optimize(
            body, budgets=request.budgets, limits=caller.limits, active_jobs=active
        )
        if isinstance(optimize, ApiError):
            return optimize
        # OPT §4.10: the property-call budget is each production solve's (its policy's), as
        # requested; the policies resolve in the job.
        return EffectiveBudgets(wall_time_s=optimize, max_property_calls=body.max_property_calls)

    def _reproduce_admission(
        self, body: ReproduceBody, request: JobRequest, caller: CapabilityReference, active: int
    ) -> EffectiveBudgets | ApiError:
        """`admit_reproduce` on the kind of the archive the body names: the rerun's budgets, or
        the refusal."""
        archive = self._core.store.artifact(body.bundle_artifact_id)
        wall_time_s = admit_reproduce(
            archive.kind if archive is not None else None,
            body,
            budgets=request.budgets,
            limits=caller.limits,
            active_jobs=active,
        )
        if isinstance(wall_time_s, ApiError):
            return wall_time_s
        return EffectiveBudgets(wall_time_s=wall_time_s, max_property_calls=None)

    def inspect_structure(
        self, revision_id: str, *, pointer: str, depth: int, cursor: str | None, limit: int
    ) -> Projection:
        operation = "inspect_structure"
        self._core.authorize(operation)
        self._revisions.check_view(operation, pointer, depth, cursor, limit)
        revision = self._revisions.revision(revision_id, operation)
        document = route_structure(revision.as_document(), surrogates=self._core.surrogates())
        return self._revisions.project(
            operation,
            document,
            revision_id,
            document_sha256(document),
            pointer,
            depth,
            cursor,
            limit,
        )

    def check_admission(
        self, *, pair: Mapping[str, Any] | None, revision: Mapping[str, Any] | None
    ) -> AdmissionReport:
        name = "check_admission"
        self._core.authorize(name)
        try:
            return capabilities.admission_report(default_registry(), pair=pair, revision=revision)
        except ApplicationError as refused:
            self._core.refuse_error(refused.error, name, None)
