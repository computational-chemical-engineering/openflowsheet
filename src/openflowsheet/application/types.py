"""The typed documents of the application contract v1 (T07 design note §5, ADR 0019 D2).

Every class here is a frozen dataclass with `as_document()` and a `from_document()` that
validates against its published schema under `schemas/` before building anything. `as_document`
always writes every member, defaults included, so a request's document is its normalized form and
`request_sha256` of an omitted default equals that of the default spelt out (§5.3).

**J5, closed for producers and open for consumers.** `from_document` is strict by default: it
validates against the schemas as published, whose artifact- and event-kind enums are closed.
`from_document(..., lenient=True)` is the consumer's reader. It opens the artifact-kind enum, and
reads an event whose kind it does not know through its common members only — `job_id`,
`sequence`, `kind`, `ends_job`, `recorded_at` — keeping the rest as an opaque `payload`, so an
unknown event that ends the job is still seen to end it.

`Edit`, `ChangeSet`, `SemanticDiff` and `TransactionResult` are defined here once and re-exported
from K06's `transactions.py`, whose imports keep working; the transaction core that produces them
lives there (W2b).
"""

from __future__ import annotations

import copy
import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache
from importlib.resources.abc import Traversable
from typing import TYPE_CHECKING, Any, Final, Literal, Self, get_args

from jsonschema import Draft202012Validator
from referencing import Registry
from referencing.jsonschema import DRAFT202012

from openflowsheet.application.jobs.model import (
    ARTIFACT_KINDS,
    ENDS_JOB,
    EVENT_KINDS,
    EVENT_PAYLOAD,
    PAYLOAD_MEMBERS,
    EndingReason,
    Interruption,
    JobOperation,
    JobStatus,
    TerminalStatus,
)
from openflowsheet.application.validation import (
    Check,
    Task,
    ValidationReport,
)
from openflowsheet.canonical import document_sha256
from openflowsheet.resources import packaged

if TYPE_CHECKING:
    from openflowsheet.run.replay import ReplayReport

#: The published schemas (the repository's `schemas/`), as the package carries them: through
#: `importlib.resources`, so a source checkout, an editable install and an installed wheel read the
#: same bytes (T08 W4.2, `openflowsheet.resources`).
SCHEMA_DIR: Final[Traversable] = packaged("schemas")
SCHEMA_BASE: Final[str] = "https://github.com/frankp/process-runtime/schemas/"

#: §5.3 as amended by ruling round 1 R2.3: `policies.DEFAULT_POLICY_ID`, the reserved id that
#: resolves at admission to the route's registered policy; the schema default of
#: `solve_body.policy_id`.
DEFAULT_SOLVE_POLICY_ID: Final[str] = "default"

ApiErrorCode = Literal[
    "invalid_request",
    "document_not_canonical",
    "unauthenticated",
    "forbidden",
    "not_found",
    "idempotency_key_reused",
    "not_ready",
    "revision_not_ready",
    "revision_unsupported",
    "verification_weakening_refused",
    "budget_exceeds_ceiling",
    "limit_exceeded",
    "unsupported",
    "internal_error",
    # ADR 0035 D3 (M02 design note §6.2): a promotion whose replacement check failed.
    "model_replacement_incompatible",
]
#: §5.8's HTTP status of each code.
API_ERROR_HTTP_STATUS: Final[Mapping[str, int]] = {
    "invalid_request": 422,
    "document_not_canonical": 422,
    "unauthenticated": 401,
    "forbidden": 403,
    "not_found": 404,
    "idempotency_key_reused": 409,
    "not_ready": 409,
    "revision_not_ready": 422,
    "revision_unsupported": 422,
    "verification_weakening_refused": 422,
    "budget_exceeds_ceiling": 422,
    "limit_exceeded": 429,
    "unsupported": 501,
    "internal_error": 500,
    "model_replacement_incompatible": 422,
}
#: Blueprint §11.3's six rights (ADR 0019 D4).
Right = Literal["read", "draft", "execute", "install", "policy", "publish"]
RIGHTS: Final[tuple[str, ...]] = get_args(Right)
#: §10.2: the built-in in-process owner's principal and capability id. Reserved: no grant in a
#: project policy may carry either, so no credential can share the owner's ledger scope or jobs.
LOCAL_OWNER_PRINCIPAL: Final[str] = "local-owner"
EditOperation = Literal["set", "remove", "append"]
TransactionStatus = Literal["committed", "replayed", "conflict", "rejected", "previewed"]
#: The certificate's own verdicts (ruling round 1 R5): copied into `RunResult`, never mapped.
VerificationStatus = Literal["VERIFIED", "RELAXED", "UNVERIFIED", "FAILED"]
#: `policies.SolvePath` (ruling round 1 R2.4), restated so this module imports no solver code.
SolvePath = Literal["revision_eo", "legacy_eo"]

EVENT_COMMON_MEMBERS: Final[tuple[str, ...]] = (
    "job_id",
    "sequence",
    "kind",
    "ends_job",
    "recorded_at",
)


# ============================================================================ schema validation


class DocumentSchemaError(ValueError):
    """A document its schema refuses. `pointer` is the RFC 6901 pointer of the first error."""

    def __init__(self, schema: str, pointer: str, message: str) -> None:
        super().__init__(f"{schema}{'#' + pointer if pointer else ''}: {message}")
        self.schema = schema
        self.pointer = pointer
        self.message = message


@cache
def _published() -> Mapping[str, Mapping[str, Any]]:
    documents: dict[str, Mapping[str, Any]] = {}
    for path in sorted(SCHEMA_DIR.iterdir(), key=lambda entry: entry.name):
        if not path.name.endswith(".schema.json"):
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        documents[document["$id"]] = document
    return documents


def _consumer_job_schema(document: Mapping[str, Any]) -> dict[str, Any]:
    """`job.schema.json` with the artifact-kind enum opened: J5's consumer reading."""
    opened = copy.deepcopy(dict(document))
    opened["$defs"]["artifact_ref"]["properties"]["kind"] = {"type": "string", "minLength": 1}
    return opened


@cache
def _registry(consumer: bool) -> Registry[Any]:
    resources = []
    for schema_id, document in _published().items():
        if consumer and schema_id == SCHEMA_BASE + "job.schema.json":
            document = _consumer_job_schema(document)
        resources.append((schema_id, DRAFT202012.create_resource(document)))
    return Registry().with_resources(resources)


@cache
def _validator(reference: str, consumer: bool = False) -> Draft202012Validator:
    return Draft202012Validator({"$ref": SCHEMA_BASE + reference}, registry=_registry(consumer))


def _event_common_schema() -> dict[str, Any]:
    """The common members of a job event, whatever its kind (J5's consumer rule)."""
    published = _published()[SCHEMA_BASE + "job-event.schema.json"]["properties"]
    properties = {name: published[name] for name in EVENT_COMMON_MEMBERS}
    properties["kind"] = {"type": "string", "minLength": 1}
    return {"type": "object", "required": list(EVENT_COMMON_MEMBERS), "properties": properties}


@cache
def _event_common_validator() -> Draft202012Validator:
    return Draft202012Validator(_event_common_schema(), registry=_registry(True))


def _consumer_event_schema(document: Mapping[str, Any]) -> dict[str, Any]:
    """`job-event.schema.json` as `JobEvent.from_document(lenient=True)` reads it (J5): a known
    kind is held to the producer schema, any other kind to the common members only."""
    producer = {key: value for key, value in document.items() if key not in ("$schema", "$id")}
    return {
        "$schema": document["$schema"],
        "$id": document["$id"],
        "title": document["title"],
        "description": document["description"],
        "if": {"required": ["kind"], "properties": {"kind": {"enum": list(EVENT_KINDS)}}},
        "then": producer,
        "else": _event_common_schema(),
    }


@cache
def published_schemas(*, consumer: bool = False) -> Mapping[str, Mapping[str, Any]]:
    """The published schemas under `schemas/`, by `$id`.

    `consumer`: J5's consumer reading, the one `from_document(..., lenient=True)` applies — the
    artifact-kind enum of `job.schema.json` opened, and `job-event.schema.json` holding an event
    of a kind not in `EVENT_KINDS` to its common members only. A binding that publishes the
    schema of a response it serves from the store (MCP's `outputSchema`, §11.3) publishes this
    reading, so a kind a newer producer wrote never makes a response fail its own schema (§5.6).
    """
    documents = dict(_published())
    if consumer:
        job = SCHEMA_BASE + "job.schema.json"
        event = SCHEMA_BASE + "job-event.schema.json"
        documents[job] = _consumer_job_schema(documents[job])
        documents[event] = _consumer_event_schema(documents[event])
    return documents


def _pointer(path: Sequence[str | int]) -> str:
    return "".join("/" + str(part).replace("~", "~0").replace("/", "~1") for part in path)


def schema_errors(reference: str, document: Any, *, consumer: bool = False) -> list[str]:
    """Every error of `document` against `schemas/<reference>`, as `<pointer>: <message>`."""
    validator = _validator(reference, consumer)
    return [
        f"{_pointer(list(error.absolute_path))}: {error.message}"
        for error in sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))
    ]


def validate_document(reference: str, document: Any, *, consumer: bool = False) -> None:
    """Raise `DocumentSchemaError` unless `document` satisfies `schemas/<reference>`."""
    _raise_first(reference, _validator(reference, consumer), document)


def _raise_first(reference: str, validator: Draft202012Validator, document: Any) -> None:
    errors = sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))
    if errors:
        first = errors[0]
        raise DocumentSchemaError(reference, _pointer(list(first.absolute_path)), first.message)


def _checked[T](
    reference: str, build: Callable[[Mapping[str, Any]], T], document: Mapping[str, Any]
) -> T:
    """Build after validation; an invariant the schema cannot state is reported the same way."""
    try:
        return build(document)
    except ValueError as error:
        if isinstance(error, DocumentSchemaError):
            raise
        raise DocumentSchemaError(reference, "", str(error)) from error


# ================================================================================ ApiError §5.8


@dataclass(frozen=True)
class ApiError:
    """§5.8: the one error shape. Domain outcomes are results, never an `ApiError`."""

    code: ApiErrorCode
    message: str
    retryable: bool
    detail: Mapping[str, Any] = field(default_factory=dict)

    @property
    def http_status(self) -> int:
        return API_ERROR_HTTP_STATUS[self.code]

    def as_document(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "detail": dict(self.detail),
            "retryable": self.retryable,
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> Self:
        validate_document("api-error.schema.json", document)
        return cls._build(document)

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        return cls(
            code=document["code"],
            message=document["message"],
            retryable=document["retryable"],
            detail=dict(document["detail"]),
        )


def _error_document(error: ApiError | None) -> dict[str, Any] | None:
    return error.as_document() if error is not None else None


def _error_build(document: Mapping[str, Any] | None) -> ApiError | None:
    return ApiError._build(document) if document is not None else None


# ===================================================================== ChangeSet §5.2 and Edit


@dataclass(frozen=True)
class Edit:
    """§5.2. `set` and `append` carry a `value` (possibly null); `remove` carries none."""

    operation: EditOperation
    path: tuple[str | int, ...]
    value: Any = None

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("an edit needs a path")
        for part in self.path:
            if isinstance(part, bool) or not isinstance(part, str | int):
                raise ValueError(f"a path element is a string or an integer, not {part!r}")
            if isinstance(part, int) and part < 0:
                raise ValueError(f"an array index is at least 0, not {part}")
        if self.operation == "remove" and self.value is not None:
            raise ValueError("a remove carries no value; supplying one hides a mistake")

    def as_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {"operation": self.operation, "path": list(self.path)}
        if self.operation != "remove":
            document["value"] = self.value
        return document

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> Self:
        reference = "change-set.schema.json#/$defs/edit"
        validate_document(reference, document)
        return _checked(reference, cls._build, document)

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        return cls(
            operation=document["operation"],
            path=tuple(document["path"]),
            value=document.get("value"),
        )


@dataclass(frozen=True)
class Change:
    """§5.2: a ChangeSet without `expected_revision` and `idempotency_key`.

    Those two are `commit_change`'s own parameters, so a `Change` has no document of its own: its
    document is the ChangeSet, written by `as_change_set` and read by `from_change_set`.
    """

    edits: tuple[Edit, ...] = ()
    new_revision_id: str | None = None
    restore_from: str | None = None
    task: Task = "simulation"
    author: str = "unknown"

    def as_change_set(self, expected_revision: str | None, idempotency_key: str) -> dict[str, Any]:
        return {
            "edits": [edit.as_document() for edit in self.edits],
            "expected_revision": expected_revision,
            "idempotency_key": idempotency_key,
            "new_revision_id": self.new_revision_id,
            "restore_from": self.restore_from,
            "task": self.task,
            "author": self.author,
        }

    @classmethod
    def from_change_set(cls, document: Mapping[str, Any]) -> tuple[Self, str | None, str]:
        """`(change, expected_revision, idempotency_key)`, omitted members at their defaults."""
        reference = "change-set.schema.json"
        validate_document(reference, document)
        change = _checked(
            reference,
            lambda d: cls(
                edits=tuple(Edit._build(edit) for edit in d["edits"]),
                new_revision_id=d.get("new_revision_id"),
                restore_from=d.get("restore_from"),
                task=d.get("task", "simulation"),
                author=d.get("author", "unknown"),
            ),
            document,
        )
        return change, document["expected_revision"], document["idempotency_key"]


@dataclass(frozen=True)
class ChangeSet:
    """§5.2 as one object: a `Change` with its `expected_revision` and `idempotency_key`.

    K06's `Application.commit` takes this; the contract's `commit_change` takes its three parts.
    `new_revision_id = None` lets the store assign `rev-<ordinal:06d>`.
    """

    edits: tuple[Edit, ...]
    expected_revision: str | None
    idempotency_key: str
    new_revision_id: str | None = None
    task: Task = "simulation"
    author: str = "unknown"
    restore_from: str | None = None

    @property
    def change(self) -> Change:
        return Change(
            edits=self.edits,
            new_revision_id=self.new_revision_id,
            restore_from=self.restore_from,
            task=self.task,
            author=self.author,
        )

    def as_document(self) -> dict[str, Any]:
        """The normalized ChangeSet: every member written, defaults included."""
        return self.change.as_change_set(self.expected_revision, self.idempotency_key)

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> Self:
        change, expected_revision, idempotency_key = Change.from_change_set(document)
        return cls(
            edits=change.edits,
            expected_revision=expected_revision,
            idempotency_key=idempotency_key,
            new_revision_id=change.new_revision_id,
            task=change.task,
            author=change.author,
            restore_from=change.restore_from,
        )


# ========================================================================= TransactionResult


@dataclass(frozen=True)
class SemanticDiff:
    """What changed, by path, in the revision's *content* — not its title or provenance."""

    added: tuple[str, ...]
    removed: tuple[str, ...]
    changed: tuple[str, ...]

    @property
    def empty(self) -> bool:
        return not (self.added or self.removed or self.changed)

    def as_document(self) -> dict[str, Any]:
        return {
            "added": list(self.added),
            "removed": list(self.removed),
            "changed": list(self.changed),
        }


def _validation_report_build(document: Mapping[str, Any]) -> ValidationReport:
    """The inverse of `ValidationReport.as_document` for a schema-valid document."""
    return ValidationReport(
        revision_id=document["revision_id"],
        task=document["task"],
        status=document["status"],
        checks=tuple(
            Check(
                id=check["id"],
                stage=check["stage"],
                result=check["result"],
                message=check["message"],
                implicated_objects=tuple(check["implicated_objects"]),
                evidence_class=check["evidence_class"],
            )
            for check in document["checks"]
        ),
        structural_counts=(
            dict(document["structural_counts"])
            if document["structural_counts"] is not None
            else None
        ),
        structural_counts_absent_reason=document.get("structural_counts_absent_reason"),
        provenance=dict(document["provenance"]),
    )


@dataclass(frozen=True)
class TransactionResult:
    """§5.2: `commit_change`'s and `preview_change`'s result. `rejected` carries `error`."""

    status: TransactionStatus
    revision_id: str | None
    validation: ValidationReport | None
    diff: SemanticDiff | None
    invalidations: tuple[str, ...] = ()
    conflict: Mapping[str, str | None] | None = None
    idempotency_key: str = ""
    error: ApiError | None = None

    def as_document(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "revision_id": self.revision_id,
            "validation": self.validation.as_document() if self.validation else None,
            "diff": self.diff.as_document() if self.diff else None,
            "invalidations": list(self.invalidations),
            "conflict": dict(self.conflict) if self.conflict is not None else None,
            "idempotency_key": self.idempotency_key,
            "error": _error_document(self.error),
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> Self:
        validate_document("transaction-result.schema.json", document)
        return cls._build(document)

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        """The inverse of `as_document`, unvalidated: for documents this code wrote itself."""
        diff = document["diff"]
        return cls(
            status=document["status"],
            revision_id=document["revision_id"],
            validation=(
                _validation_report_build(document["validation"])
                if document["validation"] is not None
                else None
            ),
            diff=(
                SemanticDiff(
                    added=tuple(diff["added"]),
                    removed=tuple(diff["removed"]),
                    changed=tuple(diff["changed"]),
                )
                if diff is not None
                else None
            ),
            invalidations=tuple(document["invalidations"]),
            conflict=dict(document["conflict"]) if document["conflict"] is not None else None,
            idempotency_key=document["idempotency_key"],
            error=_error_build(document["error"]),
        )


# ===================================================================== JobRequest §5.3 (J3)


@dataclass(frozen=True)
class Budgets:
    """§5.3 `$defs/budgets`. `None`: the capability's default, else no limit (§8.3)."""

    wall_time_s: float | None = None

    def as_document(self) -> dict[str, Any]:
        return {"wall_time_s": self.wall_time_s}

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        return cls(wall_time_s=document.get("wall_time_s"))


@dataclass(frozen=True)
class SolveBody:
    """§5.3 `$defs/solve_body`."""

    revision_id: str
    policy_id: str = DEFAULT_SOLVE_POLICY_ID
    check_tolerances: Mapping[str, float] = field(default_factory=dict)
    max_property_calls: int | None = None

    def as_document(self) -> dict[str, Any]:
        return {
            "revision_id": self.revision_id,
            "policy_id": self.policy_id,
            "check_tolerances": dict(self.check_tolerances),
            "max_property_calls": self.max_property_calls,
        }

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        return cls(
            revision_id=document["revision_id"],
            policy_id=document.get("policy_id", DEFAULT_SOLVE_POLICY_ID),
            check_tolerances=dict(document.get("check_tolerances", {})),
            max_property_calls=document.get("max_property_calls"),
        )


@dataclass(frozen=True)
class ReproduceBody:
    """§5.3 `$defs/reproduce_body`."""

    bundle_artifact_id: str
    rerun: bool = True

    def as_document(self) -> dict[str, Any]:
        return {"bundle_artifact_id": self.bundle_artifact_id, "rerun": self.rerun}

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        return cls(
            bundle_artifact_id=document["bundle_artifact_id"],
            rerun=document.get("rerun", True),
        )


#: J3: one body type per operation, as one `oneOf` branch per enum value in the schema.
_BODY_TYPES: Final[Mapping[str, type[SolveBody] | type[ReproduceBody]]] = {
    "solve": SolveBody,
    "reproduce": ReproduceBody,
}


@dataclass(frozen=True)
class JobRequest:
    """§5.3 `job.schema.json#/$defs/job_request`: the operation selects the body (J3)."""

    operation: JobOperation
    idempotency_key: str
    body: SolveBody | ReproduceBody
    budgets: Budgets = field(default_factory=Budgets)

    def __post_init__(self) -> None:
        expected = _BODY_TYPES.get(self.operation)
        if expected is None:
            raise ValueError(f"operation {self.operation!r} is not one of {sorted(_BODY_TYPES)}")
        if not isinstance(self.body, expected):
            raise ValueError(
                f"operation {self.operation!r} takes a {expected.__name__}, "
                f"not a {type(self.body).__name__}"
            )

    def as_document(self) -> dict[str, Any]:
        """The normalized request: every optional member written, at its default if omitted."""
        return {
            "operation": self.operation,
            "idempotency_key": self.idempotency_key,
            "budgets": self.budgets.as_document(),
            "body": self.body.as_document(),
        }

    @property
    def request_sha256(self) -> str:
        """§5.3: SHA-256 of the canonical JSON of the normalized request. Not policy-resolved."""
        return document_sha256(self.as_document())

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> Self:
        reference = "job.schema.json#/$defs/job_request"
        validate_document(reference, document)
        return _checked(reference, cls._build, document)

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        operation = document["operation"]
        if operation not in _BODY_TYPES:
            # A schema-valid operation this build cannot run yet (M02's `experiment` until its
            # job body, WO-6): refused here, typed, never routed to another operation's body.
            raise ValueError(f"operation {operation!r} is not executable by this build")
        return cls(
            operation=operation,
            idempotency_key=document["idempotency_key"],
            body=_BODY_TYPES[operation]._build(document["body"]),
            budgets=Budgets._build(document.get("budgets", {})),
        )


def normalize_job_request(document: Mapping[str, Any]) -> dict[str, Any]:
    """§5.3: the request with every omitted optional member filled by its schema default."""
    return JobRequest.from_document(document).as_document()


def request_sha256(document: Mapping[str, Any]) -> str:
    """§5.3: the hash of the *normalized* request, so an omitted default equals it spelt out."""
    return JobRequest.from_document(document).request_sha256


# ============================================================= ArtifactRef, Progress, Ending


@dataclass(frozen=True)
class ArtifactRef:
    """§5.4 (J1). `kind` is a `str`: a consumer keeps a kind it does not know (J5)."""

    kind: str
    artifact_id: str
    sha256: str
    size_bytes: int
    name: str

    @property
    def known(self) -> bool:
        return self.kind in ARTIFACT_KINDS

    def as_document(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "artifact_id": self.artifact_id,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "name": self.name,
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any], *, lenient: bool = False) -> Self:
        validate_document("job.schema.json#/$defs/artifact_ref", document, consumer=lenient)
        return cls._build(document)

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        return cls(
            kind=document["kind"],
            artifact_id=document["artifact_id"],
            sha256=document["sha256"],
            size_bytes=document["size_bytes"],
            name=document["name"],
        )


@dataclass(frozen=True)
class Progress:
    """§5.5 and §6.4 (J6): operation-neutral stage counts."""

    completed: int
    total: int | None
    stage: str | None

    def as_document(self) -> dict[str, Any]:
        return {"completed": self.completed, "total": self.total, "stage": self.stage}

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        return cls(
            completed=document["completed"], total=document["total"], stage=document["stage"]
        )


@dataclass(frozen=True)
class JobEnding:
    """§5.5 `$defs/job_ending`: how a job ended. The schema ties each reason to its status."""

    status: TerminalStatus
    reason: EndingReason
    interruption: Interruption | None = None

    def as_document(self) -> dict[str, Any]:
        return {"status": self.status, "reason": self.reason, "interruption": self.interruption}

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        return cls(
            status=document["status"],
            reason=document["reason"],
            interruption=document["interruption"],
        )


@dataclass(frozen=True)
class EffectiveBudgets:
    """§5.5: the budgets the job runs under, after the capability and policy resolved them."""

    wall_time_s: float | None = None
    max_property_calls: int | None = None

    def as_document(self) -> dict[str, Any]:
        return {"wall_time_s": self.wall_time_s, "max_property_calls": self.max_property_calls}

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        return cls(
            wall_time_s=document["wall_time_s"],
            max_property_calls=document["max_property_calls"],
        )


# ================================================================================ Job §5.5


@dataclass(frozen=True)
class Job:
    """§5.5 (J1, J3). `completed` means the operation ran to its end, never that it verified.

    Cross-field rules — the operation is the request's, the status is the ending's, the outputs
    are the output events' — are the lifecycle checker's (§6.3), not this constructor's, so that
    the checker can be shown a job that breaks them.
    """

    job_id: str
    operation: JobOperation
    request: JobRequest
    request_sha256: str
    principal_id: str
    capability_id: str
    policy_sha256: str
    status: JobStatus
    outputs: tuple[ArtifactRef, ...]
    progress: Progress | None
    effective_budgets: EffectiveBudgets
    cancel_requested: bool
    event_count: int
    created_at: str
    started_at: str | None = None
    ended_at: str | None = None
    ending: JobEnding | None = None
    error: ApiError | None = None

    def as_document(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "operation": self.operation,
            "request": self.request.as_document(),
            "request_sha256": self.request_sha256,
            "principal_id": self.principal_id,
            "capability_id": self.capability_id,
            "policy_sha256": self.policy_sha256,
            "status": self.status,
            "outputs": [output.as_document() for output in self.outputs],
            "progress": self.progress.as_document() if self.progress is not None else None,
            "effective_budgets": self.effective_budgets.as_document(),
            "cancel_requested": self.cancel_requested,
            "event_count": self.event_count,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "ending": self.ending.as_document() if self.ending is not None else None,
            "error": _error_document(self.error),
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any], *, lenient: bool = False) -> Self:
        """Strict for a producer; `lenient` keeps outputs of kinds this code does not know."""
        reference = "job.schema.json"
        validate_document(reference, document, consumer=lenient)
        return _checked(reference, cls._build, document)

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        return cls(
            job_id=document["job_id"],
            operation=document["operation"],
            request=JobRequest._build(document["request"]),
            request_sha256=document["request_sha256"],
            principal_id=document["principal_id"],
            capability_id=document["capability_id"],
            policy_sha256=document["policy_sha256"],
            status=document["status"],
            outputs=tuple(ArtifactRef._build(output) for output in document["outputs"]),
            progress=(
                Progress._build(document["progress"]) if document["progress"] is not None else None
            ),
            effective_budgets=EffectiveBudgets._build(document["effective_budgets"]),
            cancel_requested=document["cancel_requested"],
            event_count=document["event_count"],
            created_at=document["created_at"],
            started_at=document["started_at"],
            ended_at=document["ended_at"],
            ending=(
                JobEnding._build(document["ending"]) if document["ending"] is not None else None
            ),
            error=_error_build(document["error"]),
        )


# =========================================================================== JobEvent §5.6


@dataclass(frozen=True)
class JobEvent:
    """§5.6 (J2, J5, J6). Whether the event ends the job is `ends_job`, never `kind`.

    For a producer kind, the payload members are exactly its branch's (`EVENT_PAYLOAD`), and
    `ends_job` is the kind's (`ENDS_JOB`); the constructor refuses anything else. An event of a
    kind this code does not know exists only as a consumer read it (`from_document(lenient=True)`):
    its payload is kept whole in `payload`, unread.
    """

    job_id: str
    sequence: int
    kind: str
    ends_job: bool
    recorded_at: str
    progress: Progress | None = None
    output: ArtifactRef | None = None
    ending: JobEnding | None = None
    error: ApiError | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.known:
            if any(getattr(self, member) is not None for member in PAYLOAD_MEMBERS):
                raise ValueError(f"an event of unknown kind {self.kind!r} has no typed payload")
            return
        if self.payload:
            raise ValueError(f"a {self.kind!r} event keeps no opaque payload")
        if self.ends_job != ENDS_JOB[self.kind]:
            raise ValueError(f"a {self.kind!r} event has ends_job = {ENDS_JOB[self.kind]}")
        carried = EVENT_PAYLOAD[self.kind]
        for member in PAYLOAD_MEMBERS:
            value = getattr(self, member)
            if member not in carried and value is not None:
                raise ValueError(f"a {self.kind!r} event carries no {member!r}")
            if member in carried and member != "error" and value is None:
                raise ValueError(f"a {self.kind!r} event carries {member!r}")

    @property
    def known(self) -> bool:
        return self.kind in EVENT_KINDS

    def as_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "job_id": self.job_id,
            "sequence": self.sequence,
            "kind": self.kind,
            "ends_job": self.ends_job,
            "recorded_at": self.recorded_at,
        }
        if not self.known:
            document.update(self.payload)
            return document
        for member in EVENT_PAYLOAD[self.kind]:
            value = getattr(self, member)
            document[member] = value.as_document() if value is not None else None
        return document

    @classmethod
    def from_document(cls, document: Mapping[str, Any], *, lenient: bool = False) -> Self:
        """Strict: the producer schema. `lenient`: J5's consumer rule (module docstring)."""
        reference = "job-event.schema.json"
        if lenient and document.get("kind") not in EVENT_KINDS:
            _raise_first(reference, _event_common_validator(), document)
            return cls(
                **{member: document[member] for member in EVENT_COMMON_MEMBERS},
                payload={
                    key: value for key, value in document.items() if key not in EVENT_COMMON_MEMBERS
                },
            )
        validate_document(reference, document, consumer=lenient)
        return _checked(reference, cls._build, document)

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        progress = document.get("progress")
        output = document.get("output")
        ending = document.get("ending")
        return cls(
            job_id=document["job_id"],
            sequence=document["sequence"],
            kind=document["kind"],
            ends_job=document["ends_job"],
            recorded_at=document["recorded_at"],
            progress=Progress._build(progress) if progress is not None else None,
            output=ArtifactRef._build(output) if output is not None else None,
            ending=JobEnding._build(ending) if ending is not None else None,
            error=_error_build(document.get("error")),
        )


# ========================================================================== RunResult §5.7


@dataclass(frozen=True)
class RunResult:
    """§5.7: what a solve job produced. `job_status` is not `verification_status`."""

    job_id: str
    run_id: str | None
    revision_id: str
    revision_content_sha256: str
    policy_id: str
    policy_sha256: str | None
    check_policy_sha256: str | None
    job_status: TerminalStatus
    outcome: str | None
    verification_status: VerificationStatus | None
    structural_sha256: str | None
    outputs: tuple[ArtifactRef, ...]
    error: ApiError | None = None
    solve_path: SolvePath = "revision_eo"

    def __post_init__(self) -> None:
        certified = any(output.kind == "solution_certificate" for output in self.outputs)
        if self.verification_status is not None and not certified:
            raise ValueError(
                "verification_status is copied from a solution certificate, and no "
                "solution_certificate output exists (§5.7)"
            )

    def as_document(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "run_id": self.run_id,
            "revision_id": self.revision_id,
            "revision_content_sha256": self.revision_content_sha256,
            "policy_id": self.policy_id,
            "policy_sha256": self.policy_sha256,
            "check_policy_sha256": self.check_policy_sha256,
            "solve_path": self.solve_path,
            "job_status": self.job_status,
            "outcome": self.outcome,
            "verification_status": self.verification_status,
            "structural_sha256": self.structural_sha256,
            "outputs": [output.as_document() for output in self.outputs],
            "error": _error_document(self.error),
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any], *, lenient: bool = False) -> Self:
        reference = "run-result.schema.json"
        validate_document(reference, document, consumer=lenient)
        return _checked(
            reference,
            lambda d: cls(
                job_id=d["job_id"],
                run_id=d["run_id"],
                revision_id=d["revision_id"],
                revision_content_sha256=d["revision_content_sha256"],
                policy_id=d["policy_id"],
                policy_sha256=d["policy_sha256"],
                check_policy_sha256=d["check_policy_sha256"],
                job_status=d["job_status"],
                outcome=d["outcome"],
                verification_status=d["verification_status"],
                structural_sha256=d["structural_sha256"],
                outputs=tuple(ArtifactRef._build(output) for output in d["outputs"]),
                error=_error_build(d["error"]),
                solve_path=d["solve_path"],
            ),
            document,
        )


# ======================================================================= JobResult (R4)


def _replay_report_build(document: Mapping[str, Any]) -> ReplayReport:
    """The inverse of `ReplayReport.as_document` for a schema-valid document."""
    from openflowsheet.run.bundle import BundleIntegrity
    from openflowsheet.run.replay import ReplayReport

    integrity = document["integrity"]
    return ReplayReport(
        mode=document["mode"],
        verdict=document["verdict"],
        integrity=BundleIntegrity(
            ok=integrity["ok"],
            missing=tuple(integrity["missing"]),
            tampered=tuple(integrity["tampered"]),
            unexpected=tuple(integrity["unexpected"]),
        ),
        recorded_environment=dict(document["recorded_environment"]),
        current_environment=dict(document["current_environment"]),
        reasons=tuple(document["reasons"]),
        differences=tuple(document["differences"]),
        bitwise_floats=document["bitwise_floats"],
        verdict_changed_near_threshold=tuple(document["verdict_changed_near_threshold"]),
    )


@dataclass(frozen=True)
class JobResult:
    """§4.2 as amended by ruling round 1 R4 (`job.schema.json#/$defs/job_result`).

    `run_result` is present iff the operation is `solve` (a failed or cancelled solve has one
    too); `replay_report` only for a `reproduce` whose report was produced; `error` is the job's.
    """

    operation: JobOperation
    run_result: RunResult | None
    replay_report: ReplayReport | None
    error: ApiError | None

    def __post_init__(self) -> None:
        if (self.run_result is not None) != (self.operation == "solve"):
            raise ValueError("a job result carries a run result iff its operation is 'solve'")
        if self.replay_report is not None and self.operation != "reproduce":
            raise ValueError("only a 'reproduce' job result carries a replay report")

    def as_document(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "run_result": self.run_result.as_document() if self.run_result is not None else None,
            "replay_report": (
                self.replay_report.as_document() if self.replay_report is not None else None
            ),
            "error": _error_document(self.error),
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any], *, lenient: bool = False) -> Self:
        reference = "job.schema.json#/$defs/job_result"
        validate_document(reference, document, consumer=lenient)
        return _checked(
            reference,
            lambda d: cls(
                operation=d["operation"],
                run_result=(
                    RunResult.from_document(d["run_result"], lenient=lenient)
                    if d["run_result"] is not None
                    else None
                ),
                replay_report=(
                    _replay_report_build(d["replay_report"])
                    if d["replay_report"] is not None
                    else None
                ),
                error=_error_build(d["error"]),
            ),
            document,
        )


# ================================================== CapabilityReference and ProjectPolicy §5.9


@dataclass(frozen=True)
class Limits:
    """§5.9: a capability's budget ceilings. `None`: no limit.

    Each non-null wall time is finite and `> 0`, and a default is at most the ceiling (ruling
    round 5b, S5). A violating grant is refused, never clamped.
    """

    default_wall_time_s: float | None = None
    max_wall_time_s: float | None = None
    max_active_jobs: int | None = None

    def __post_init__(self) -> None:
        for name in ("default_wall_time_s", "max_wall_time_s"):
            value = getattr(self, name)
            if value is not None and not (math.isfinite(value) and value > 0):
                raise ValueError(f"{name} {value} is not a finite number > 0")
        default, ceiling = self.default_wall_time_s, self.max_wall_time_s
        if default is not None and ceiling is not None and default > ceiling:
            raise ValueError(f"default_wall_time_s {default} exceeds max_wall_time_s {ceiling}")

    def as_document(self) -> dict[str, Any]:
        return {
            "default_wall_time_s": self.default_wall_time_s,
            "max_wall_time_s": self.max_wall_time_s,
            "max_active_jobs": self.max_active_jobs,
        }

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        return cls(
            default_wall_time_s=document["default_wall_time_s"],
            max_wall_time_s=document["max_wall_time_s"],
            max_active_jobs=document["max_active_jobs"],
        )


@dataclass(frozen=True)
class CapabilityReference:
    """§5.9 and §10.1: what a credential grants. `note` is untrusted and never read for authority.

    `rights` is unique and sorted; an unsorted or repeated list is refused, not reordered.
    """

    capability_id: str
    principal_id: str
    rights: tuple[Right, ...]
    token_sha256: str | None
    limits: Limits = field(default_factory=Limits)
    expires_at: str | None = None
    note: str = ""

    def __post_init__(self) -> None:
        unknown = sorted(right for right in self.rights if right not in RIGHTS)
        if unknown:
            raise ValueError(f"unknown rights {unknown}")
        if list(self.rights) != sorted(set(self.rights)):
            raise ValueError(f"rights are unique and sorted, not {list(self.rights)}")

    def as_document(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "principal_id": self.principal_id,
            "rights": list(self.rights),
            "token_sha256": self.token_sha256,
            "limits": self.limits.as_document(),
            "expires_at": self.expires_at,
            "note": self.note,
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> Self:
        reference = "capability-reference.schema.json"
        validate_document(reference, document)
        return _checked(reference, cls._build, document)

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        try:
            limits = Limits._build(document["limits"])
        except ValueError as error:  # name the grant, so the operator can find it (S5)
            raise ValueError(f"capability {document['capability_id']!r}: {error}") from error
        return cls(
            capability_id=document["capability_id"],
            principal_id=document["principal_id"],
            rights=tuple(document["rights"]),
            token_sha256=document["token_sha256"],
            limits=limits,
            expires_at=document["expires_at"],
            note=document["note"],
        )


@dataclass(frozen=True)
class ExecutorSettings:
    """§5.9 `executor`: worker count and the forced-stop grace period (§8.2)."""

    max_workers: int = 1
    grace_s: float = 10

    def as_document(self) -> dict[str, Any]:
        return {"max_workers": self.max_workers, "grace_s": self.grace_s}

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        return cls(max_workers=document.get("max_workers", 1), grace_s=document.get("grace_s", 10))


@dataclass(frozen=True)
class ProjectPolicy:
    """§5.9 and §10.3: `project-policy.json`. An invalid file is refused, never defaulted.

    `capability_id` and every non-null `token_sha256` are unique: a presented token must name one
    capability. A null token is never presentable (§10.2), so several may coexist. No grant may
    name `LOCAL_OWNER_PRINCIPAL`, as principal or as capability: a credential sharing the owner's
    principal would share its idempotency scope and its jobs.
    """

    project_id: str
    capabilities: tuple[CapabilityReference, ...]
    executor: ExecutorSettings = field(default_factory=ExecutorSettings)
    schema_version: Literal["project-policy-v1"] = "project-policy-v1"

    def __post_init__(self) -> None:
        ids = [capability.capability_id for capability in self.capabilities]
        if len(ids) != len(set(ids)):
            raise ValueError(f"capability ids repeat: {sorted(ids)}")
        tokens = [c.token_sha256 for c in self.capabilities if c.token_sha256 is not None]
        if len(tokens) != len(set(tokens)):
            raise ValueError("two capabilities share a token_sha256")
        reserved = [
            c.capability_id
            for c in self.capabilities
            if LOCAL_OWNER_PRINCIPAL in (c.principal_id, c.capability_id)
        ]
        if reserved:
            raise ValueError(
                f"{LOCAL_OWNER_PRINCIPAL!r} is reserved for the in-process owner; "
                f"grants {reserved} name it"
            )

    @property
    def policy_sha256(self) -> str:
        """The document hash a job records at acceptance (§5.5 `policy_sha256`)."""
        return document_sha256(self.as_document())

    def as_document(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "capabilities": [capability.as_document() for capability in self.capabilities],
            "executor": self.executor.as_document(),
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> Self:
        reference = "project-policy.schema.json"
        validate_document(reference, document)
        return _checked(
            reference,
            lambda d: cls(
                project_id=d["project_id"],
                capabilities=tuple(CapabilityReference._build(c) for c in d["capabilities"]),
                executor=ExecutorSettings._build(d["executor"]),
                schema_version=d["schema_version"],
            ),
            document,
        )


# ================================================ Composite results (§4.2; no schema of their own)


@dataclass(frozen=True)
class ReplayPolicy:
    """§4.2: `reproduce`'s policy. The comparison policy is always `run.compare.POLICY_ID`."""

    rerun: bool = True

    def as_document(self) -> dict[str, Any]:
        return {"rerun": self.rerun}

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> Self:
        if set(document) != {"rerun"} or not isinstance(document["rerun"], bool):
            raise DocumentSchemaError("ReplayPolicy", "", "a replay policy is {rerun: boolean}")
        return cls(rerun=document["rerun"])


@dataclass(frozen=True)
class SubmitResult:
    """§4.2: `submit_job`'s result. `replayed`: the key and body matched an existing job."""

    job: Job
    replayed: bool

    def as_document(self) -> dict[str, Any]:
        return {"job": self.job.as_document(), "replayed": self.replayed}

    @classmethod
    def from_document(cls, document: Mapping[str, Any], *, lenient: bool = False) -> Self:
        if set(document) != {"job", "replayed"} or not isinstance(document["replayed"], bool):
            raise DocumentSchemaError("SubmitResult", "", "a submit result is {job, replayed}")
        return cls(
            job=Job.from_document(document["job"], lenient=lenient), replayed=document["replayed"]
        )


@dataclass(frozen=True)
class JobWait:
    """§4.2: `wait_job`'s result — the job, the events after the caller's sequence, and `ended`."""

    job: Job
    events: tuple[JobEvent, ...]
    ended: bool

    def as_document(self) -> dict[str, Any]:
        return {
            "job": self.job.as_document(),
            "events": [event.as_document() for event in self.events],
            "ended": self.ended,
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any], *, lenient: bool = False) -> Self:
        if (
            set(document) != {"job", "events", "ended"}
            or not isinstance(document["events"], list)
            or not isinstance(document["ended"], bool)
        ):
            raise DocumentSchemaError("JobWait", "", "a job wait is {job, events, ended}")
        return cls(
            job=Job.from_document(document["job"], lenient=lenient),
            events=tuple(
                JobEvent.from_document(event, lenient=lenient) for event in document["events"]
            ),
            ended=document["ended"],
        )


# ================================================ Inspection results (§4.2; no schema of their own)


@dataclass(frozen=True)
class ServerInfo:
    """§4.2 `get_project`'s `server`: the package, its commit when known, the store's schema."""

    package_version: str
    git_commit: str | None
    store_schema: str

    def as_document(self) -> dict[str, Any]:
        return {
            "package_version": self.package_version,
            "git_commit": self.git_commit,
            "store_schema": self.store_schema,
        }


@dataclass(frozen=True)
class ProjectSummary:
    """§4.2 `get_project`: the project, its head and counts, the solve policies it offers, and
    the caller as the credential makes it — its principal, capability, rights and limits."""

    project_id: str
    head: str | None
    revision_count: int
    #: Every job status, with the number of the project's jobs in it (zero included).
    job_counts: Mapping[str, int]
    #: `(policy_id, policy_sha256)` of each registered application solve policy.
    solve_policies: tuple[tuple[str, str], ...]
    default_policy_id: str
    principal_id: str
    capability_id: str
    rights: tuple[Right, ...]
    limits: Limits
    server: ServerInfo

    def as_document(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "head": self.head,
            "revision_count": self.revision_count,
            "job_counts": dict(self.job_counts),
            "solve_policies": [
                {"policy_id": policy_id, "policy_sha256": sha256}
                for policy_id, sha256 in self.solve_policies
            ],
            "default_policy_id": self.default_policy_id,
            "principal_id": self.principal_id,
            "capability_id": self.capability_id,
            "rights": list(self.rights),
            "limits": self.limits.as_document(),
            "server": self.server.as_document(),
        }


@dataclass(frozen=True)
class ModelRegistryView:
    """§4.2 `list_models`: each registered model's declarative signature as a document —
    `{model_id, ports, required, zero, pins, choices}` — in model-id order, each pin and option
    with the `specifications` that pin it (ADR 0019 Amendment 2). Built from the signatures
    alone; nothing is constructed."""

    models: tuple[Mapping[str, Any], ...]

    def as_document(self) -> dict[str, Any]:
        return {"models": [dict(model) for model in self.models]}


@dataclass(frozen=True)
class RevisionSummary:
    """§4.2 `list_revisions`: one stored revision without its document. `title` is the
    document's own (untrusted) text, or `None` when it has no string title."""

    revision_id: str
    parent_revision: str | None
    content_sha256: str
    title: str | None
    principal_id: str
    created_at: str
    head: bool

    def as_document(self) -> dict[str, Any]:
        return {
            "revision_id": self.revision_id,
            "parent_revision": self.parent_revision,
            "content_sha256": self.content_sha256,
            "title": self.title,
            "principal_id": self.principal_id,
            "created_at": self.created_at,
            "head": self.head,
        }


def validate_inline(label: str, schema: Mapping[str, Any], document: Any) -> None:
    """Raise `DocumentSchemaError` (named `label`) unless `document` satisfies `schema`: a schema
    that is not published itself but may `$ref` the published ones — `operations`' request and
    composite-response envelopes."""
    _raise_first(label, Draft202012Validator(schema, registry=_registry(False)), document)
