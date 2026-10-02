"""T07 W1a: the application contract's schemas and typed documents (design note §5, ADR 0019 D2).

What is held here:
- every new schema is a valid 2020-12 schema under the repository's `$id` base;
- every typed document round-trips `as_document` → schema → `from_document` → equal object;
- the producer vocabularies of `jobs/model.py` and `types.py` equal the schema enums, and every
  schema `default` equals the dataclass default that normalization writes;
- `request_sha256` is taken over the normalized request (§5.3): an omitted default hashes equal
  to the default spelt out;
- producers are closed and consumers open (J5): an unknown artifact or event kind is refused by
  the strict reader and kept, opaque, by the lenient one.

J3 (the operation discriminator) and ADR 0008 A1 (b) are in `test_t07_adr0008_jobs.py`; the
lifecycle checker is in `test_t07_lifecycle.py`. The round-trip documents are constructed here, not
fixtures: `job` and `job-event` fixtures come from real jobs in W4a (R-015).
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, get_args

import pytest
from conftest import REPO_ROOT, load_json, load_yaml
from jsonschema import Draft202012Validator
from t07_support import AT, COMPLETED, DIGEST, JOB_ID, completed_solve, event, job, ref

from openflowsheet.application.jobs import model
from openflowsheet.application.transactions import SemanticDiff
from openflowsheet.application.types import (
    API_ERROR_HTTP_STATUS,
    DEFAULT_SOLVE_POLICY_ID,
    RIGHTS,
    SCHEMA_BASE,
    SCHEMA_DIR,
    ApiError,
    ApiErrorCode,
    ArtifactRef,
    Budgets,
    CapabilityReference,
    Change,
    DocumentSchemaError,
    Edit,
    ExecutorSettings,
    Job,
    JobEnding,
    JobEvent,
    JobRequest,
    JobWait,
    Limits,
    ProjectPolicy,
    ReplayPolicy,
    ReproduceBody,
    RunResult,
    SolveBody,
    SubmitResult,
    TransactionResult,
    normalize_job_request,
    request_sha256,
    schema_errors,
    validate_document,
)
from openflowsheet.application.validation import validate

T07_SCHEMAS = (
    "api-error",
    "capability-reference",
    "change-set",
    "job",
    "job-event",
    "project-policy",
    "run-result",
    "transaction-result",
)


def schema(name: str) -> dict[str, Any]:
    document: dict[str, Any] = load_json(REPO_ROOT / "schemas" / f"{name}.schema.json")
    return document


# ------------------------------------------------------------------------------ the schemas


def test_types_read_the_repository_schemas() -> None:
    # Since T08 W4.2 through the package's `_data/schemas` link (`openflowsheet.resources`),
    # which in a checkout resolves to the repository's `schemas/`.
    assert Path(str(SCHEMA_DIR)).resolve() == (REPO_ROOT / "schemas").resolve()


@pytest.mark.parametrize("name", T07_SCHEMAS)
def test_each_schema_is_a_valid_2020_12_schema_under_the_repository_base(name: str) -> None:
    document = schema(name)
    Draft202012Validator.check_schema(document)
    assert document["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert document["$id"] == f"{SCHEMA_BASE}{name}.schema.json"
    assert document["additionalProperties"] is False


def test_the_schema_readme_lists_every_t07_schema() -> None:
    readme = (REPO_ROOT / "schemas" / "README.md").read_text(encoding="utf-8")
    for name in T07_SCHEMAS:
        assert f"`{name}.schema.json`" in readme, name


@pytest.mark.parametrize(
    ("value", "valid"),
    [
        ("key-1", True),
        ("auto:0123abcd", True),
        ("a.b_c:d~e-f", True),
        ("x" * 128, True),
        ("x" * 129, False),
        ("", False),
        ("has space", False),
        ("slash/not-allowed", False),
    ],
)
def test_the_id_pattern(value: str, valid: bool) -> None:
    assert (schema_errors("job.schema.json#/$defs/id", value) == []) is valid


@pytest.mark.parametrize(
    ("value", "valid"),
    [
        ("job-000001/solution-certificate.json", True),
        ("import-1:bundle", True),
        ("a/..b/c", True),
        ("x" * 256, True),
        ("x" * 257, False),
        ("/rooted", False),
        ("..", False),
        ("a/../b", False),
        ("a/..", False),
        ("a b", False),
    ],
)
def test_the_artifact_id_pattern_refuses_escapes(value: str, valid: bool) -> None:
    assert (schema_errors("job.schema.json#/$defs/artifact_id", value) == []) is valid


@pytest.mark.parametrize(
    ("value", "valid"),
    [
        ("2026-09-27T12:00:00.000000Z", True),
        ("2026-09-27T12:00:00Z", False),
        ("2026-09-27T12:00:00.000000+00:00", False),
        ("2026-09-27 12:00:00.000000Z", False),
    ],
)
def test_the_timestamp_pattern(value: str, valid: bool) -> None:
    assert (schema_errors("job.schema.json#/$defs/timestamp", value) == []) is valid


# ----------------------------------------------- producer vocabularies equal the schema enums


def test_the_kind_tables_are_the_schema_enums() -> None:
    job_defs = schema("job")["$defs"]
    assert list(model.JOB_OPERATIONS) == job_defs["operation"]["enum"]
    assert list(model.JOB_STATUSES) == job_defs["job_status"]["enum"]
    assert sorted(model.TERMINAL_STATUSES) == sorted(job_defs["terminal_status"]["enum"])
    assert list(model.ARTIFACT_KINDS) == job_defs["artifact_ref"]["properties"]["kind"]["enum"]
    assert set(model.ARTIFACT_FILE_NAMES) == set(model.ARTIFACT_KINDS)
    assert list(model.EVENT_KINDS) == schema("job-event")["properties"]["kind"]["enum"]


def test_the_ending_reasons_are_the_schema_branches() -> None:
    ending = schema("job")["$defs"]["job_ending"]
    branches = {
        branch["properties"]["status"]["const"]: set(branch["properties"]["reason"]["enum"])
        for branch in ending["oneOf"]
    }
    assert branches == {status: set(reasons) for status, reasons in model.ENDING_REASONS.items()}
    assert set(ending["properties"]["reason"]["enum"]) == set().union(*branches.values())
    assert set(get_args(model.EndingReason)) == set().union(*branches.values())


def test_each_event_kind_has_one_branch_with_its_ends_job_and_payload() -> None:
    event_schema = schema("job-event")
    branches: dict[str, dict[str, Any]] = {}
    for branch in event_schema["oneOf"]:
        kind = branch["properties"]["kind"]["const"]
        assert kind not in branches, f"{kind} has two branches"
        branches[kind] = branch
    assert list(branches) == list(model.EVENT_KINDS)
    for kind, branch in branches.items():
        assert branch["properties"]["ends_job"]["const"] is model.ENDS_JOB[kind]
        forbidden = {name for name, rule in branch["properties"].items() if rule is False}
        carried = set(model.EVENT_PAYLOAD[kind])
        assert set(branch.get("required", [])) == carried, kind
        assert forbidden == set(model.PAYLOAD_MEMBERS) - carried, kind


def test_the_error_codes_and_rights_are_the_schema_enums() -> None:
    codes = schema("api-error")["properties"]["code"]["enum"]
    assert list(get_args(ApiErrorCode)) == codes
    assert list(API_ERROR_HTTP_STATUS) == codes
    assert list(RIGHTS) == schema("capability-reference")["properties"]["rights"]["items"]["enum"]


def test_schema_defaults_are_the_defaults_normalization_writes() -> None:
    """§5.3: normalization fills the *schema* default; the dataclass must agree with it."""
    job_defs = schema("job")["$defs"]
    solve = job_defs["solve_body"]["properties"]
    assert DEFAULT_SOLVE_POLICY_ID == solve["policy_id"]["default"]
    assert SolveBody(revision_id="r").as_document() == {
        "revision_id": "r",
        **{name: rule["default"] for name, rule in solve.items() if "default" in rule},
    }
    reproduce = job_defs["reproduce_body"]["properties"]
    assert ReproduceBody("b").as_document() == {
        "bundle_artifact_id": "b",
        "rerun": reproduce["rerun"]["default"],
    }
    assert Budgets().as_document() == job_defs["job_request"]["properties"]["budgets"]["default"]
    assert Budgets().as_document() == {
        "wall_time_s": job_defs["budgets"]["properties"]["wall_time_s"]["default"]
    }
    change = schema("change-set")["properties"]
    written = Change().as_change_set(None, "k")
    for name, rule in change.items():
        if "default" in rule:
            assert written[name] == rule["default"], name
    executor = schema("project-policy")["properties"]["executor"]["properties"]
    assert ExecutorSettings().as_document() == {
        name: rule["default"] for name, rule in executor.items()
    }


# ------------------------------------------------------------------------------ round trips


def _report() -> Any:
    """A real validator report of a SYN-001 case, its provenance in the frozen schema's shape.

    The K06 validator writes `provenance = {validator, analysis}`, which the frozen
    `validation-report.schema.json` refuses (it requires `produced_by` and `timestamp`); that gap
    is reported to the design lane with W1 and is W2's to resolve, so the report here carries
    the schema's provenance and the validator's checks and counts.
    """
    case = load_yaml(
        REPO_ROOT / "benchmarks" / "syn001" / "cases" / "SYN-001-A02-355-dew-guess.yaml"
    )
    report = validate(case, "simulation")
    assert report.status == "READY_FOR_SIMULATION"
    return dataclasses.replace(
        report, provenance={"produced_by": "openflowsheet K06 validator", "timestamp": AT}
    )


def _round_trip_cases() -> list[tuple[str, Any, str]]:
    finished, events = completed_solve()
    error = ApiError(
        code="revision_not_ready",
        message="validation is not READY_FOR_SIMULATION",
        retryable=False,
        detail={"report": {"status": "DRAFT"}},
    )
    capability = CapabilityReference(
        capability_id="cap-agent-1",
        principal_id="agent-1",
        rights=("draft", "execute", "read"),
        token_sha256="a" * 64,
        limits=Limits(default_wall_time_s=300, max_wall_time_s=1800, max_active_jobs=4),
        expires_at=None,
        note="granted for V17",
    )
    return [
        ("api-error.schema.json", error, "ApiError"),
        (
            "change-set.schema.json#/$defs/edit",
            Edit(operation="set", path=("instances", 0, "id"), value=None),
            "Edit set to null",
        ),
        (
            "change-set.schema.json#/$defs/edit",
            Edit(operation="remove", path=("title",)),
            "Edit remove",
        ),
        (
            "transaction-result.schema.json",
            TransactionResult(
                status="committed",
                revision_id="rev-000002",
                validation=_report(),
                diff=SemanticDiff(added=("/a",), removed=(), changed=("/b",)),
                invalidations=("run-job-000001",),
                idempotency_key="key-1",
            ),
            "TransactionResult committed",
        ),
        (
            "transaction-result.schema.json",
            TransactionResult(
                status="conflict",
                revision_id=None,
                validation=None,
                diff=None,
                conflict={"expected": "rev-000001", "actual": "rev-000002"},
                idempotency_key="key-2",
            ),
            "TransactionResult conflict",
        ),
        (
            "transaction-result.schema.json",
            TransactionResult(
                status="rejected",
                revision_id=None,
                validation=None,
                diff=None,
                idempotency_key="key-3",
                error=ApiError(
                    code="invalid_request",
                    message="edit path invalid",
                    retryable=False,
                    detail={"pointer": "/edits/0/path"},
                ),
            ),
            "TransactionResult rejected",
        ),
        (
            "job.schema.json#/$defs/job_request",
            JobRequest(
                operation="solve",
                idempotency_key="key-1",
                body=SolveBody(
                    revision_id="rev-1",
                    policy_id="T06-revision-v2",
                    check_tolerances={"mass_balance": 1e-10},
                    max_property_calls=5000,
                ),
                budgets=Budgets(wall_time_s=60.0),
            ),
            "JobRequest solve",
        ),
        (
            "job.schema.json#/$defs/job_request",
            JobRequest(
                operation="reproduce",
                idempotency_key="auto:0f",
                body=ReproduceBody(bundle_artifact_id="import-000001:bundle", rerun=False),
            ),
            "JobRequest reproduce",
        ),
        (
            "job.schema.json#/$defs/artifact_ref",
            ref("worker_log", name="worker.log"),
            "ArtifactRef",
        ),
        ("job.schema.json", job(), "Job queued"),
        ("job.schema.json", finished, "Job completed"),
        (
            "job.schema.json",
            job(
                status="failed",
                started_at=AT,
                ended_at=AT,
                ending=JobEnding(status="failed", reason="worker_lost", interruption="forced"),
                error=ApiError(
                    code="internal_error",
                    message="the worker exited with no result",
                    retryable=True,
                    detail={"exitcode": -9},
                ),
            ),
            "Job failed",
        ),
        *[("job-event.schema.json", item, f"JobEvent {item.kind}") for item in events],
        (
            "job-event.schema.json",
            event(2, "cancel_requested"),
            "JobEvent cancel_requested",
        ),
        (
            "run-result.schema.json",
            RunResult(
                job_id=JOB_ID,
                run_id=f"run-{JOB_ID}",
                revision_id="rev-1",
                revision_content_sha256=DIGEST,
                policy_id="T06-revision-v2",
                policy_sha256="b" * 64,
                check_policy_sha256="c" * 64,
                job_status="completed",
                outcome="CONVERGED",
                verification_status="VERIFIED",
                structural_sha256="d" * 64,
                outputs=finished.outputs,
            ),
            "RunResult verified",
        ),
        (
            "run-result.schema.json",
            RunResult(
                job_id=JOB_ID,
                run_id=None,
                revision_id="rev-1",
                revision_content_sha256=DIGEST,
                policy_id="T06-revision-v2",
                policy_sha256=None,
                check_policy_sha256=None,
                job_status="cancelled",
                outcome=None,
                verification_status=None,
                structural_sha256=None,
                outputs=(ref("partial_solve_trace", name="partial-solve-events.json"),),
            ),
            "RunResult interrupted",
        ),
        ("capability-reference.schema.json", capability, "CapabilityReference"),
        (
            "project-policy.schema.json",
            ProjectPolicy(
                project_id="demo",
                capabilities=(
                    capability,
                    CapabilityReference(
                        capability_id="cap-operator",
                        principal_id="operator",
                        rights=("policy", "read"),
                        token_sha256=None,
                    ),
                ),
                executor=ExecutorSettings(max_workers=2, grace_s=0.5),
            ),
            "ProjectPolicy",
        ),
    ]


ROUND_TRIPS = _round_trip_cases()


@pytest.mark.parametrize(
    ("reference", "instance"),
    [(reference, instance) for reference, instance, _ in ROUND_TRIPS],
    ids=[label for _, _, label in ROUND_TRIPS],
)
def test_each_typed_document_round_trips_through_its_schema(reference: str, instance: Any) -> None:
    document = instance.as_document()
    assert schema_errors(reference, document) == []
    rebuilt = type(instance).from_document(document)
    assert rebuilt == instance
    assert rebuilt.as_document() == document


def test_a_change_round_trips_through_its_change_set() -> None:
    change = Change(
        edits=(
            Edit("set", ("instances", 0, "parameters", "T"), 350.0),
            Edit("append", ("connections",), {"from": "a", "to": "b"}),
            Edit("remove", ("title",)),
        ),
        new_revision_id=None,
        restore_from="rev-000001",
        task="optimization",
        author="agent-1",
    )
    document = change.as_change_set("rev-000003", "key-9")
    assert schema_errors("change-set.schema.json", document) == []
    assert Change.from_change_set(document) == (change, "rev-000003", "key-9")


def test_a_change_set_with_only_its_required_members_takes_the_defaults() -> None:
    minimal = {"edits": [], "expected_revision": None, "idempotency_key": "first"}
    assert Change.from_change_set(minimal) == (Change(), None, "first")


@pytest.mark.parametrize(
    "instance",
    [
        ReplayPolicy(rerun=False),
        SubmitResult(job=job(), replayed=True),
        JobWait(job=completed_solve()[0], events=tuple(completed_solve()[1]), ended=True),
    ],
    ids=["ReplayPolicy", "SubmitResult", "JobWait"],
)
def test_the_composite_results_round_trip(instance: Any) -> None:
    assert type(instance).from_document(instance.as_document()) == instance


def test_a_capability_policy_hash_is_the_document_hash() -> None:
    policy = ProjectPolicy(project_id="p", capabilities=())
    from openflowsheet.canonical import document_sha256

    assert policy.policy_sha256 == document_sha256(policy.as_document())


# ------------------------------------------------------------- request_sha256 normalization §5.3


def test_an_omitted_default_hashes_equal_to_the_default_spelt_out() -> None:
    omitted = {"operation": "solve", "idempotency_key": "k", "body": {"revision_id": "rev-1"}}
    explicit = {
        "operation": "solve",
        "idempotency_key": "k",
        "budgets": {"wall_time_s": None},
        "body": {
            "revision_id": "rev-1",
            "policy_id": "default",
            "check_tolerances": {},
            "max_property_calls": None,
        },
    }
    assert normalize_job_request(omitted) == explicit
    assert request_sha256(omitted) == request_sha256(explicit)
    partly = {"operation": "solve", "idempotency_key": "k", "budgets": {}, "body": omitted["body"]}
    assert request_sha256(partly) == request_sha256(explicit)


def test_a_reproduce_request_normalizes_its_rerun_default() -> None:
    omitted = {
        "operation": "reproduce",
        "idempotency_key": "k",
        "body": {"bundle_artifact_id": "b"},
    }
    explicit = {
        "operation": "reproduce",
        "idempotency_key": "k",
        "budgets": {"wall_time_s": None},
        "body": {"bundle_artifact_id": "b", "rerun": True},
    }
    assert request_sha256(omitted) == request_sha256(explicit)
    assert request_sha256(omitted) != request_sha256(
        {**explicit, "body": {"bundle_artifact_id": "b", "rerun": False}}
    )


def test_the_hash_is_of_the_canonical_json_so_an_integral_float_equals_its_integer() -> None:
    body = {"revision_id": "rev-1"}
    as_int = {"operation": "solve", "idempotency_key": "k", "budgets": {"wall_time_s": 300}}
    as_float = {"operation": "solve", "idempotency_key": "k", "budgets": {"wall_time_s": 300.0}}
    assert request_sha256({**as_int, "body": body}) == request_sha256({**as_float, "body": body})


@pytest.mark.parametrize(
    "change",
    [
        {"idempotency_key": "other"},
        {"budgets": {"wall_time_s": 60}},
        {"body": {"revision_id": "rev-2"}},
        {"body": {"revision_id": "rev-1", "policy_id": "T06-revision-v1"}},
        {"body": {"revision_id": "rev-1", "check_tolerances": {"mass_balance": 1e-12}}},
        {"body": {"revision_id": "rev-1", "max_property_calls": 10}},
    ],
)
def test_a_different_request_hashes_differently(change: dict[str, Any]) -> None:
    base = {"operation": "solve", "idempotency_key": "k", "body": {"revision_id": "rev-1"}}
    assert request_sha256(base) != request_sha256({**base, **change})


def test_the_typed_request_hash_is_the_document_hash() -> None:
    request = JobRequest(operation="solve", idempotency_key="k", body=SolveBody("rev-1"))
    assert request.request_sha256 == request_sha256(
        {
            "operation": "solve",
            "idempotency_key": "k",
            "body": {"revision_id": "rev-1"},
        }
    )


# ------------------------------------------------ J5: closed for producers, open for consumers


def _output_event(kind: str) -> dict[str, Any]:
    return event(3, "output", output=ref("solve_trace")).as_document() | {
        "output": ref("solve_trace").as_document() | {"kind": kind}
    }


def test_the_producer_schema_refuses_an_unknown_event_kind() -> None:
    document = event(2, "started").as_document() | {"kind": "simulated_time_progress"}
    assert schema_errors("job-event.schema.json", document) != []
    with pytest.raises(DocumentSchemaError):
        JobEvent.from_document(document)


def test_the_producer_schema_refuses_an_unknown_artifact_kind() -> None:
    assert schema_errors("job-event.schema.json", _output_event("trajectory")) != []
    with pytest.raises(DocumentSchemaError):
        JobEvent.from_document(_output_event("trajectory"))
    finished = completed_solve()[0].as_document()
    finished["outputs"][0]["kind"] = "trajectory"
    assert schema_errors("job.schema.json", finished) != []
    with pytest.raises(DocumentSchemaError):
        Job.from_document(finished)
    with pytest.raises(DocumentSchemaError):
        ArtifactRef.from_document(finished["outputs"][0])


def test_a_producer_cannot_construct_an_event_outside_its_kind_table() -> None:
    with pytest.raises(ValueError, match="ends_job"):
        event(1, "started", ends_job=True)
    with pytest.raises(ValueError, match="carries 'output'"):
        event(1, "output")
    with pytest.raises(ValueError, match="carries no 'output'"):
        event(5, "ended", ending=COMPLETED, output=ref("solve_trace"))
    with pytest.raises(ValueError, match="no typed payload"):
        JobEvent(JOB_ID, 1, "unknown_kind", False, AT, progress=None, output=ref("solve_trace"))


def test_the_consumer_keeps_an_unknown_event_opaque_and_honours_ends_job() -> None:
    document = {
        "job_id": JOB_ID,
        "sequence": 4,
        "kind": "trajectory_segment_closed",
        "ends_job": True,
        "recorded_at": AT,
        "segment": {"t_end": 10.0},
    }
    read = JobEvent.from_document(document, lenient=True)
    assert not read.known
    assert read.ends_job is True
    assert read.payload == {"segment": {"t_end": 10.0}}
    assert read.as_document() == document


def test_the_consumer_still_refuses_an_unknown_event_without_its_common_members() -> None:
    document = {"job_id": JOB_ID, "sequence": 4, "kind": "new_kind", "recorded_at": AT}
    with pytest.raises(DocumentSchemaError):
        JobEvent.from_document(document, lenient=True)


def test_the_consumer_keeps_an_output_of_an_unknown_artifact_kind() -> None:
    read = JobEvent.from_document(_output_event("trajectory"), lenient=True)
    assert read.output is not None and read.output.kind == "trajectory"
    assert not read.output.known
    finished = completed_solve()[0].as_document()
    finished["outputs"].insert(1, ref("trajectory", 7).as_document())
    kept = Job.from_document(finished, lenient=True)
    assert [output.kind for output in kept.outputs] == [
        "solution_certificate",
        "trajectory",
        "run_manifest",
        "replay_bundle",
    ]
    assert kept.as_document() == finished


def test_the_consumer_reads_known_kinds_as_strictly_as_the_producer() -> None:
    document = event(2, "started").as_document() | {"progress": None}
    with pytest.raises(DocumentSchemaError):
        JobEvent.from_document(document, lenient=True)


# ----------------------------------------------------------------- shapes the schema refuses


@pytest.mark.parametrize(
    ("edit", "why"),
    [
        ({"operation": "set", "path": ["a"]}, "set needs a value"),
        ({"operation": "append", "path": ["a"]}, "append needs a value"),
        ({"operation": "remove", "path": ["a"], "value": None}, "remove carries none"),
        ({"operation": "set", "path": [], "value": 1}, "empty path"),
        ({"operation": "set", "path": [-1], "value": 1}, "negative index"),
        ({"operation": "set", "path": [True], "value": 1}, "a boolean is not an index"),
        ({"operation": "set", "path": [1.5], "value": 1}, "a float is not an index"),
        ({"operation": "move", "path": ["a"], "value": 1}, "unknown operation"),
    ],
)
def test_an_ill_formed_edit_is_refused(edit: dict[str, Any], why: str) -> None:
    assert schema_errors("change-set.schema.json#/$defs/edit", edit) != [], why
    with pytest.raises(DocumentSchemaError):
        Edit.from_document(edit)


@pytest.mark.parametrize(
    ("ending", "valid"),
    [
        ({"status": "completed", "reason": "operation_completed", "interruption": None}, True),
        ({"status": "cancelled", "reason": "cancel_requested", "interruption": "forced"}, True),
        ({"status": "timed_out", "reason": "wall_time_exhausted", "interruption": None}, True),
        ({"status": "completed", "reason": "cancel_requested", "interruption": None}, False),
        ({"status": "failed", "reason": "wall_time_exhausted", "interruption": None}, False),
        ({"status": "running", "reason": "operation_completed", "interruption": None}, False),
    ],
)
def test_an_ending_reason_belongs_to_its_status(ending: dict[str, Any], valid: bool) -> None:
    assert (schema_errors("job.schema.json#/$defs/job_ending", ending) == []) is valid


def test_the_accepted_event_is_sequence_zero() -> None:
    document = event(0, "accepted").as_document()
    assert schema_errors("job-event.schema.json", document) == []
    assert schema_errors("job-event.schema.json", document | {"sequence": 1}) != []


def test_the_ended_event_requires_its_error_member_even_when_null() -> None:
    document = event(9, "ended", ending=COMPLETED, error=None).as_document()
    assert document["error"] is None
    assert schema_errors("job-event.schema.json", document) == []
    del document["error"]
    assert schema_errors("job-event.schema.json", document) != []


def test_verification_status_needs_a_certificate_output() -> None:
    with pytest.raises(ValueError, match="solution_certificate"):
        RunResult(
            job_id=JOB_ID,
            run_id=None,
            revision_id="rev-1",
            revision_content_sha256=DIGEST,
            policy_id="p",
            policy_sha256=None,
            check_policy_sha256=None,
            job_status="completed",
            outcome="BUDGET_EXHAUSTED",
            verification_status="FAILED",
            structural_sha256=None,
            outputs=(ref("failure_bundle"),),
        )


def test_run_result_outcome_is_a_k03_outcome_word() -> None:
    finished = completed_solve()[0]
    document = RunResult(
        job_id=JOB_ID,
        run_id=f"run-{JOB_ID}",
        revision_id="rev-1",
        revision_content_sha256=DIGEST,
        policy_id="p",
        policy_sha256=None,
        check_policy_sha256=None,
        job_status="completed",
        outcome="CONVERGED",
        verification_status=None,
        structural_sha256=None,
        outputs=finished.outputs,
    ).as_document()
    assert schema_errors("run-result.schema.json", document) == []
    assert schema_errors("run-result.schema.json", document | {"outcome": "SOLVED"}) != []


@pytest.mark.parametrize("rights", [("read", "draft"), ("read", "read"), ("admin",)])
def test_rights_are_known_unique_and_sorted(rights: tuple[str, ...]) -> None:
    with pytest.raises(ValueError):
        CapabilityReference("c", "p", rights, None)  # type: ignore[arg-type]
    document = CapabilityReference("c", "p", ("read",), None).as_document()
    with pytest.raises(DocumentSchemaError):
        CapabilityReference.from_document(document | {"rights": list(rights)})


def test_a_project_policy_refuses_a_repeated_capability_id_or_token() -> None:
    first = CapabilityReference("cap-1", "p1", ("read",), "a" * 64)
    same_id = CapabilityReference("cap-1", "p2", ("read",), "b" * 64)
    same_token = CapabilityReference("cap-2", "p2", ("read",), "a" * 64)
    for second in (same_id, same_token):
        document = ProjectPolicy("p", (first,)).as_document()
        document["capabilities"].append(second.as_document())
        with pytest.raises(DocumentSchemaError):
            ProjectPolicy.from_document(document)
    untokened = (
        CapabilityReference("cap-3", "p3", ("read",), None),
        CapabilityReference("cap-4", "p4", ("read",), None),
    )
    assert len(ProjectPolicy("p", untokened).capabilities) == 2


def test_a_project_policy_file_is_refused_rather_than_defaulted() -> None:
    document = ProjectPolicy("p", ()).as_document()
    for broken in (
        {**document, "schema_version": "project-policy-v0"},
        {key: value for key, value in document.items() if key != "executor"},
        {**document, "executor": {"max_workers": 0}},
        {**document, "executor": {"grace_s": 0.1}},
        {**document, "extra": True},
    ):
        with pytest.raises(DocumentSchemaError):
            ProjectPolicy.from_document(broken)
    assert ProjectPolicy.from_document({**document, "executor": {}}).executor == ExecutorSettings()


def test_validate_document_names_the_pointer_of_the_first_error() -> None:
    document = job().as_document()
    document["outputs"] = [ref("solve_trace").as_document() | {"size_bytes": -1}]
    with pytest.raises(DocumentSchemaError) as raised:
        validate_document("job.schema.json", document)
    assert raised.value.pointer == "/outputs/0/size_bytes"
