# ADR 0076 I-12d: placement of every def and module-level binding of application/local.py

Base: `wp/S19-w4` 617099ef (W4 run 17, brief S19-W4-17). local.py 1785 NLOC (codehealth scan).

## Method

An AST pass over local.py at the base (script: `ast.walk` over each `LocalApplication` method and each
module-level def or binding; an edge `A -> B` when A reads `self.B` / `application.B` / `view.B`, or
the module-level name B). Homes, in this order of precedence:

1. The facade keeps the lifecycle (`__init__`, `create`, `open`, `in_memory`, `authenticated`,
   `close`, the context manager) and the properties, each property a one-line delegation to the
   core (ADR).
2. The ADR's core list (`_surrogates`, `_context`, `_caller`, `_authorize`, `_refuse`,
   `_refuse_error`, `_audit_refusal`), public without the underscore.
3. The ADR's family lists. A pattern (`_admit*`, `_artifact_*`) names its members explicitly and
   wins over the source range `_submit .. _import_bundle` (lines 882-1294) of the Job family.
   "cursor helpers" (Job family) is read as `_check_sequence`, `_decode_cursor`, `_encode_cursor`
   (reading B, see below).
4. An unlisted name goes to the home of its only callers; with callers in two homes, to the lower
   one (iterated to a fixed point). Order, top to bottom: facade, job, validation, artifact,
   revision, inspection, core.

A private name whose callers sit in another module becomes public in its home (ADR helper rule).

`_audit_refusal` (the core's `audit_refusal(operation, code, request_sha256)`, called by `_refuse`,
`_refuse_error`, `_rejected` and the public method) is not the facade's public `audit_refusal(operation,
code)` (InspectionService, the contract operation `dispatch` calls for a request refused before it
reaches a method); the latter calls the former with `request_sha256=None`.

## Upward edges under the ADR's lists (R1)

Run 17 stopped on E1 to E3 (R1). The orchestrator's ruling of 2026-11-17 (brief S19-W4-18; the
reviewer confirms or overturns it at the I-12d review) decides each by the ADR's own rule: "a method
whose family is not listed goes where its only callers are; callers in two services, the lower one";
a listed home that would make a service call one above it yields to that rule. E1 to E3 now stand in
the table with basis "R1 ruling 2026-11-17": `_job` -> ArtifactService `job`; `_decode_cursor`,
`_encode_cursor` -> RevisionService (`decode_cursor`, module-level `encode_cursor`); `_check_request`
-> RevisionService. Run 17's reading B of "cursor helpers" stands, so E4 does not arise. Any other
upward edge found later is still a STOP.

| edge | file:line at 617099ef | caller home | callee home (ADR) |
|---|---|---|---|
| E1 `get_stream_table -> _job` | local.py:1672 | artifact | job (range `_submit .. _import_bundle`) |
| E2 `list_revisions -> _decode_cursor`, `_encode_cursor` | local.py:1485, :1487 | revision | job ("cursor helpers") |
| E3 `commit_change -> _check_request`, `preview_change -> _check_request` | local.py:614, :1410 | revision | validation (listed) |
| E4 (reading A only) `list_audit -> _check_limit`, `_decode_audit_cursor`, `_encode_audit_cursor`; `list_capabilities -> _check_limit`; `list_revisions -> _check_limit` | local.py:1772, :1773, :1781, :1821, :1484 | inspection, revision | job, if "cursor helpers" also covers `_check_limit` and the audit cursor |

Reading A ("cursor helpers" = every `*cursor*` helper plus `_check_limit` and `_check_sequence`)
adds E4; reading B (the job-list cursor of §11.4) does not, and under B `_check_limit` and the
audit cursor go to InspectionService by rule 4. E1 to E3 stand under either reading. No core
member calls a service. Steps 1 (ServiceCore, InspectionService) touch none of E1 to E3. With the
ruling, no service calls one above it: `job` (store, core) and `check_request` (`rejected`, core) call
nothing above their new homes, and the cursor pair calls only the core.

## Table

| line | name | home | name at home | basis | callers at the base |
|---|---|---|---|---|---|
| 159 | `Executor` | facade | stays | only caller | `open` |
| 160 | `TASKS` | validation | `validation_service.TASKS` | only caller | `validate` |
| 162 | `WAIT_POLL_S` | job | `job_service.WAIT_POLL_S` | only caller | `_wait` |
| 164 | `MAX_JOB_PAGE` | job | `job_service.MAX_JOB_PAGE` | only caller | `list_jobs` |
| 166 | `AUDIT_ORDERS` | inspection | `inspection_service.AUDIT_ORDERS` | only caller | `_decode_audit_cursor`, `list_audit` |
| 167 | `_AUDIT_OPERATION_LIMIT` | inspection | `inspection_service._AUDIT_OPERATION_LIMIT` | only caller | `list_audit` |
| 168 | `MAX_EVENT_PAGE` | job | `job_service.MAX_EVENT_PAGE` | only caller | `list_job_events` |
| 170 | `MAX_LISTED_MEMBERS` | artifact | `artifact_service.MAX_LISTED_MEMBERS` | only caller | `_missing_member` |
| 173 | `STREAM_TABLE_DEPTH` | artifact | `artifact_service.STREAM_TABLE_DEPTH` | only caller | `get_stream_table` |
| 190 | `__init__` | facade | stays | lifecycle/property (ADR) | - |
| 211 | `create` | facade | stays | lifecycle/property (ADR) | - |
| 273 | `open` | facade | stays | lifecycle/property (ADR) | `create` |
| 338 | `in_memory` | facade | stays | lifecycle/property (ADR) | - |
| 354 | `authenticated` | facade | stays | lifecycle/property (ADR) | - |
| 371 | `close` | facade | stays | lifecycle/property (ADR) | `__exit__`, `open` |
| 379 | `__enter__` | facade | stays | lifecycle/property (ADR) | - |
| 382 | `__exit__` | facade | stays | lifecycle/property (ADR) | - |
| 388 | `store` | facade | stays | lifecycle/property (ADR) | - |
| 392 | `project_id` | facade | stays (one-line delegation to `ServiceCore`) | lifecycle/property (ADR) | `get_project` |
| 396 | `principal_id` | facade | stays (one-line delegation to `ServiceCore`) | lifecycle/property (ADR) | `_audit_refusal`, `cancel_job` |
| 400 | `capability_id` | facade | stays (one-line delegation to `ServiceCore`) | lifecycle/property (ADR) | `_audit_refusal` |
| 404 | `policy` | facade | stays (one-line delegation to `ServiceCore`) | lifecycle/property (ADR) | - |
| 409 | `executor` | facade | stays | lifecycle/property (ADR) | - |
| 414 | `files_root` | facade | stays (one-line delegation to `ServiceCore`) | lifecycle/property (ADR) | `_artifact_path`, `_context`, `_import_bundle`, `_store_replacements`, `_surrogate_study_admission`, `_surrogates`, `artifact_bytes`, `get_artifact`, `get_stream_table` |
| 423 | `_surrogates` | core | `service_core.ServiceCore.surrogates` (public: crosses modules) | ADR core list | `_check_promotion`, `_prepare`, `_resolution`, `_solve_admission`, `inspect_structure`, `validate` |
| 432 | `_context` | core | `service_core.ServiceCore.context` (public: crosses modules) | ADR core list | `_submit`, `open` |
| 439 | `_caller` | core | `service_core.ServiceCore._caller` | ADR core list | `_authorize` |
| 456 | `_authorize` | core | `service_core.ServiceCore.authorize` (public: crosses modules) | ADR core list | `artifact_bytes`, `cancel_job`, `check_admission`, `commit_change`, `diff_revisions`, `explain`, `get_artifact`, `get_job`, `get_job_result`, `get_project`, `get_revision`, `get_stream_table`, `inspect_structure`, `list_audit`, `list_capabilities`, `list_job_events`, `list_jobs`, `list_models`, `list_revisions`, `preview_change`, `reproduce`, `solve`, `submit_job`, `validate`, `wait_job` |
| 477 | `_refuse` | core | `service_core.ServiceCore.refuse` (public: crosses modules) | ADR core list | `_artifact_row`, `_authorize`, `_caller`, `_check_limit`, `_check_request`, `_check_sequence`, `_decode_audit_cursor`, `_decode_cursor`, `_display_units`, `_import_bundle`, `_job`, `_prepare`, `_refuse_key_reused`, `_replayed`, `_result`, `_revision`, `_submit`, `_wait`, `artifact_bytes`, `explain`, `get_stream_table`, `list_audit`, `list_job_events`, `list_jobs`, `reproduce`, `validate`, `wait_job` |
| 491 | `_audit_refusal` | core | `service_core.ServiceCore.audit_refusal` (public: crosses modules) | ADR core list | `_refuse`, `_refuse_error`, `_rejected`, `audit_refusal` |
| 505 | `validate` | validation | `validation_service.ValidationService.validate` | ADR family list | - |
| 577 | `commit_change` | revision | `revision_service.RevisionService.commit_change` | ADR family list | - |
| 697 | `solve` | job | `job_service.JobService.solve` | ADR family list | - |
| 734 | `reproduce` | job | `job_service.JobService.reproduce` | ADR family list | - |
| 758 | `submit_job` | job | `job_service.JobService.submit_job` | ADR family list | - |
| 767 | `get_job` | job | `job_service.JobService.get_job` | ADR family list | - |
| 772 | `list_jobs` | job | `job_service.JobService.list_jobs` | ADR family list | - |
| 791 | `list_job_events` | job | `job_service.JobService.list_job_events` | ADR family list | - |
| 808 | `wait_job` | job | `job_service.JobService.wait_job` | ADR family list | - |
| 831 | `cancel_job` | job | `job_service.JobService.cancel_job` | ADR family list | - |
| 856 | `get_job_result` | job | `job_service.JobService.get_job_result` | ADR family list | - |
| 869 | `_display_units` | artifact | `artifact_service.ArtifactService.display_units` (public: crosses modules) | ADR family list | `get_job_result`, `get_stream_table` |
| 882 | `_submit` | job | `job_service.JobService._submit` | ADR range `_submit .. _import_bundle` | `reproduce`, `solve`, `submit_job` |
| 935 | `_replayed_job` | job | `job_service.JobService._replayed_job` | ADR range `_submit .. _import_bundle` | `_submit` |
| 941 | `_refuse_key_reused` | job | `job_service.JobService._refuse_key_reused` | ADR range `_submit .. _import_bundle` | `_replayed_job`, `_submit` |
| 951 | `_admit` | validation | `validation_service.ValidationService.admit` (public: crosses modules) | ADR `_admit*` | `_submit` |
| 981 | `_solve_admission` | validation | `validation_service.ValidationService._solve_admission` | ADR `_admit*` | `_admit` |
| 1009 | `_experiment_admission` | validation | `validation_service.ValidationService._experiment_admission` | ADR `_admit*` | `_admit` |
| 1021 | `_surrogate_study_admission` | validation | `validation_service.ValidationService._surrogate_study_admission` | ADR `_admit*` | `_admit` |
| 1043 | `_optimize_admission` | validation | `validation_service.ValidationService._optimize_admission` | ADR `_admit*` | `_admit` |
| 1056 | `_reproduce_admission` | validation | `validation_service.ValidationService._reproduce_admission` | ADR `_admit*` | `_admit` |
| 1073 | `_job` | artifact | `artifact_service.ArtifactService.job` (public: crosses modules) | R1 ruling 2026-11-17 (E1: callers in job+artifact, the lower) | `_replayed_job`, `_result`, `_submit`, `cancel_job`, `get_job`, `get_stream_table` |
| 1079 | `_wait` | job | `job_service.JobService._wait` | ADR range `_submit .. _import_bundle` | `_wait_until_ended`, `wait_job` |
| 1092 | `_wait_until_ended` | job | `job_service.JobService._wait_until_ended` | ADR range `_submit .. _import_bundle` | `reproduce`, `solve` |
| 1100 | `_result` | job | `job_service.JobService._result` | ADR range `_submit .. _import_bundle` | `get_job_result`, `reproduce`, `solve` |
| 1159 | `_experiment_answer` | job | `job_service.JobService._experiment_answer` | ADR range `_submit .. _import_bundle` | `_result` |
| 1170 | `_run_result` | job | `job_service.JobService._run_result` | ADR family list | `_result` |
| 1202 | `_run_failure` | job | `job_service.JobService._run_failure` | ADR family list | `_run_result` |
| 1266 | `_resolution` | job | `job_service.JobService._resolution` | ADR range `_submit .. _import_bundle` | `_run_result` |
| 1289 | `_artifact_path` | artifact | `artifact_service.ArtifactService.artifact_path` (public: crosses modules) | ADR `_artifact_*` | `_experiment_answer`, `_result`, `_run_failure` |
| 1294 | `_import_bundle` | job | `job_service.JobService._import_bundle` | ADR range `_submit .. _import_bundle` | `reproduce` |
| 1347 | `_check_limit` | inspection | `inspection_service.InspectionService.check_limit` (public: crosses modules) | callers in inspection+revision+job, the lower | `list_audit`, `list_capabilities`, `list_job_events`, `list_jobs`, `list_revisions` |
| 1356 | `_check_sequence` | job | `job_service.JobService._check_sequence` | ADR 'cursor helpers' (reading B) | `list_job_events`, `wait_job` |
| 1369 | `_decode_cursor` | revision | `revision_service.RevisionService.decode_cursor` (public: crosses modules) | R1 ruling 2026-11-17 (E2: callers in job+revision, the lower) | `list_jobs`, `list_revisions` |
| 1392 | `_refuse_error` | core | `service_core.ServiceCore.refuse_error` (public: crosses modules) | ADR core list | `_admit`, `_check_view`, `_project`, `_submit`, `check_admission`, `list_capabilities` |
| 1401 | `preview_change` | revision | `revision_service.RevisionService.preview_change` | ADR family list | - |
| 1427 | `get_project` | inspection | `inspection_service.InspectionService.get_project` | ADR family list | - |
| 1461 | `list_models` | inspection | `inspection_service.InspectionService.list_models` | ADR family list | - |
| 1478 | `list_revisions` | revision | `revision_service.RevisionService.list_revisions` | ADR family list | - |
| 1490 | `get_revision` | revision | `revision_service.RevisionService.get_revision` | ADR family list | - |
| 1516 | `diff_revisions` | revision | `revision_service.RevisionService.diff_revisions` | ADR family list | - |
| 1527 | `inspect_structure` | validation | `validation_service.ValidationService.inspect_structure` | ADR family list | - |
| 1555 | `get_artifact` | artifact | `artifact_service.ArtifactService.get_artifact` | ADR family list | - |
| 1622 | `get_stream_table` | artifact | `artifact_service.ArtifactService.get_stream_table` | ADR family list | - |
| 1736 | `list_audit` | inspection | `inspection_service.InspectionService.list_audit` | ADR family list | - |
| 1784 | `explain` | inspection | `inspection_service.InspectionService.explain` | ADR family list | - |
| 1806 | `list_capabilities` | inspection | `inspection_service.InspectionService.list_capabilities` | ADR family list | - |
| 1829 | `check_admission` | validation | `validation_service.ValidationService.check_admission` | ADR family list | - |
| 1848 | `_decode_audit_cursor` | inspection | `inspection_service.InspectionService._decode_audit_cursor` | only caller | `list_audit` |
| 1881 | `artifact_bytes` | artifact | `artifact_service.ArtifactService.artifact_bytes` | ADR family list | - |
| 1908 | `audit_refusal` | inspection | `inspection_service.InspectionService.audit_refusal` | ADR family list | - |
| 1913 | `_revision` | revision | `revision_service.RevisionService.revision` (public: crosses modules) | ADR family list | `diff_revisions`, `get_revision`, `inspect_structure` |
| 1922 | `_artifact_row` | artifact | `artifact_service.ArtifactService._artifact_row` | ADR `_artifact_*` | `artifact_bytes`, `get_artifact`, `get_stream_table` |
| 1934 | `_missing_member` | artifact | `artifact_service.ArtifactService._missing_member` | ADR family list | `_artifact_row`, `get_stream_table` |
| 1962 | `_run_outcome` | artifact | `artifact_service.ArtifactService._run_outcome` | only caller | `_missing_member`, `get_stream_table` |
| 1973 | `_check_view` | revision | `revision_service.RevisionService.check_view` (public: crosses modules) | callers in revision+artifact+validation, the lower | `get_artifact`, `get_revision`, `get_stream_table`, `inspect_structure` |
| 1982 | `_project` | revision | `revision_service.RevisionService.project` (public: crosses modules) | callers in revision+artifact+validation, the lower | `get_artifact`, `get_revision`, `get_stream_table`, `inspect_structure` |
| 2008 | `_check_request` | revision | `revision_service.RevisionService._check_request` | R1 ruling 2026-11-17 (E3: only callers in revision) | `commit_change`, `preview_change` |
| 2030 | `_prepare` | revision | `revision_service.RevisionService._prepare` | ADR family list | `commit_change`, `preview_change` |
| 2133 | `_check_promotion` | revision | `revision_service.RevisionService._check_promotion` | ADR family list | `_prepare` |
| 2172 | `_store_replacements` | revision | `revision_service.RevisionService._store_replacements` | ADR family list | `commit_change` |
| 2200 | `_replayed` | revision | `revision_service.RevisionService._replayed` | ADR family list | `commit_change` |
| 2215 | `_rejected` | revision | `revision_service.RevisionService.rejected` (public: crosses modules) | ADR family list | `_check_promotion`, `_check_request`, `_prepare`, `commit_change` |
| 2236 | `_Prepared` | revision | `revision_service._Prepared` | only caller | `_prepare` |
| 2245 | `REPLACEMENTS_DIR` | revision | `revision_service.REPLACEMENTS_DIR` | only caller | `_store_replacements` |
| 2248 | `_with_report_hashes` | revision | `revision_service._with_report_hashes` | only caller | `_prepare` |
| 2263 | `_displayed` | job | `job_service._displayed` | only caller | `get_job_result` |
| 2275 | `_explained` | job | `job_service._explained` | only caller | `_displayed` |
| 2284 | `_unproduced` | job | `job_service._unproduced` | only caller | `reproduce` |
| 2299 | `_conflict` | revision | `revision_service._conflict` | only caller | `commit_change` |
| 2310 | `_assigned_revision_id` | revision | `revision_service._assigned_revision_id` | only caller | `_prepare` |
| 2318 | `_model_view` | inspection | `inspection_service._model_view` | only caller | `list_models` |
| 2355 | `_unique_members` | artifact | `artifact_service._unique_members` | only caller | `_file_document` |
| 2362 | `_file_document` | artifact | `artifact_service._file_document` | only caller | `get_artifact` |
| 2379 | `_encode_audit_cursor` | inspection | `inspection_service._encode_audit_cursor` | only caller | `list_audit` |
| 2386 | `_encode_cursor` | revision | `revision_service.encode_cursor` (public: crosses modules) | R1 ruling 2026-11-17 (E2: callers in job+revision, the lower) | `list_jobs`, `list_revisions` |
| 2394 | `_conforms` (under `TYPE_CHECKING`) | facade | stays | checks the facade against `contract.Application` | - |
