"""The operations table and the one dispatch every binding goes through (§4.3, §10.4, §11.6).

`OPERATIONS` is the only routing source: one row per protocol method — `Application`'s four,
`JobControl`'s seven, `Inspection`'s thirteen (`list_audit` is ADR 0019 Amendment 3's, `explain`
ADR 0058 D7's, `get_stream_table` ADR 0068's, `list_capabilities` and `check_admission` ADR 0060
D11's) — and
`artifact_bytes`, the raw export. A row names its method, the right it needs, its request and
response schemas, its HTTP verb and path, its MCP tool, the transports that carry it and its tool
description. Python (through `dispatch`), the
CLI, HTTP and MCP read this table and nothing else, and add nothing to what it says.

`dispatch(app, name, request)` does, in this order:

1. the canonical form (R-088 Q29, §12.5) — a NaN, an infinity, an integer that is not the
   canonical spelling of a binary64 (ADR 0002 Amendment 1), a node outside JSON or a string
   holding a lone surrogate is refused `document_not_canonical` with its pointer
   (`canonical.first_noncanonical`);
2. the operation's request schema — `invalid_request` with the pointer of the first error;
3. the decoding into typed arguments, with the rules no schema states — an idempotency key with
   the reserved prefix `auto:` (§5.1: in-process `solve` and `reproduce` only) is refused here;
4. the method itself, which authorizes from the credential and nothing else (§10.1);
5. `project_response`: every `ApiError` the result holds explained (MSG §3.3), then every string
   and key of the result bounded (§10.4).

A refusal at steps 1–3 is audited (§10.7) and raised; a refusal from the method was audited
there. Every `ApiError` leaves `dispatch` bounded like a response. The Python methods themselves
return raw typed objects — bounding is a contract function the transports share, not something
each adds (§10.4).

**Schemas.** A request with a published schema uses it (`change-set`, `job_request`). The others
are the method's parameters as one flat object, stated here and `$ref`-ing the published
patterns (§5.1 ids, job ids, artifact ids); a path parameter is a member like any other (§11.3).
The JobControl and Inspection results with no schema of their own (`SubmitResult`, `JobWait`,
the pages, `Projection`, …) are the `$defs` of `schemas/application-results.schema.json`
(ruling round 4, W5a-Q2; ADR 0019 Amendment 1), which each row `$ref`s; the tests hold every
produced response to its operation's response schema.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import cache
from typing import Any, Final, Literal, Protocol

from openflowsheet.application.contract import (
    Application,
    ApplicationError,
    Inspection,
    JobControl,
    Page,
    api_error,
)
from openflowsheet.application.projection import (
    MAX_DEPTH,
    MAX_PAGE,
    TEXT_LIMIT,
    bound_document,
    bound_text,
)
from openflowsheet.application.types import (
    SCHEMA_BASE,
    ApiError,
    ApiErrorCode,
    AuditRecord,
    Change,
    DocumentSchemaError,
    Job,
    JobEvent,
    JobRequest,
    ReplayPolicy,
    RevisionSummary,
    Right,
    published_schemas,
    validate_inline,
)
from openflowsheet.canonical import first_noncanonical

Transport = Literal["python", "cli", "http", "mcp"]
ALL_TRANSPORTS: Final[tuple[Transport, ...]] = ("python", "cli", "http", "mcp")
#: §5.1: the idempotency-key prefix of in-process `solve` and `reproduce`; transports refuse it.
RESERVED_KEY_PREFIX: Final[str] = "auto:"
#: §4.2, §11.3: `wait_job`'s time-out over a transport is capped at this.
TRANSPORT_WAIT_CAP_S: Final[float] = 30.0
#: §11.4: event pages (default 100, at most 500).
MAX_EVENT_PAGE: Final[int] = 500


class Dispatchable(Application, JobControl, Inspection, Protocol):
    """What `dispatch` calls: the three protocols, the raw export, and the audit of a refusal
    made before a method was reached (`LocalApplication`)."""

    def artifact_bytes(self, artifact_id: str) -> bytes: ...

    def audit_refusal(self, operation: str, code: ApiErrorCode) -> None: ...


@dataclass(frozen=True)
class Operation:
    """One row of §4.3's table."""

    name: str
    #: The `LocalApplication` method, which is also the protocol method's name.
    method: str
    right: Right
    request_schema: Mapping[str, Any]
    #: `None` for the raw export, whose response is bytes, not a document.
    response_schema: Mapping[str, Any] | None
    #: `(verb, path)`, or `None` where HTTP does not carry the operation.
    http: tuple[str, str] | None
    mcp_tool: str | None
    transports: tuple[Transport, ...]
    #: `bindings/descriptions/<operation>.md` for an MCP tool (W6c writes and reviews them).
    description_file: str | None
    #: The request document as the method's keyword arguments, after the schema accepted it.
    decode: Callable[[Mapping[str, Any]], dict[str, Any]]
    #: The method's result as its response document (before bounding).
    encode: Callable[[Any], Any]


# ================================================================================== schemas


def _ref(reference: str) -> dict[str, str]:
    return {"$ref": SCHEMA_BASE + reference}


#: The replay report's schema is published under its own base (K05).
REPLAY_REPORT_SCHEMA: Final[str] = (
    "https://raw.githubusercontent.com/computational-chemical-engineering/clearsheet/main/"
    "schemas/replay-report.schema.json"
)
ID: Final = _ref("job.schema.json#/$defs/id")
JOB_ID: Final = _ref("job.schema.json#/$defs/job_id")
ARTIFACT_ID: Final = _ref("job.schema.json#/$defs/artifact_id")
CURSOR: Final = {"type": ["string", "null"], "maxLength": 1024}
POINTER: Final = {"type": "string", "maxLength": 8192}
#: ADR 0075 D8: a display preference's text; its grammar is `units.parse_display_units`'s.
DISPLAY_UNITS: Final = {"type": "string", "minLength": 1, "maxLength": 1024}
#: ADR 0058 D7: a message code as `explain` takes it (MSG §3.5).
MESSAGE_CODE: Final = {
    "type": "string",
    "minLength": 1,
    "maxLength": 128,
    "pattern": "^[A-Za-z0-9][A-Za-z0-9_.-]*$",
}


#: ADR 0060 D11: an extension's kind, id and version as the registry's descriptor states them.
EXTENSION_KIND: Final = _ref("extension-descriptor.schema.json#/properties/kind")
EXTENSION_ID: Final = _ref("extension-descriptor.schema.json#/$defs/id")
EXTENSION_VERSION: Final = _ref("extension-descriptor.schema.json#/properties/version")


def _limit(maximum: int) -> dict[str, Any]:
    return {"type": "integer", "minimum": 1, "maximum": maximum}


def _object(
    required: Mapping[str, Any], optional: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """A closed object schema: `required` members and `optional` ones."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": sorted(required),
        "properties": {**required, **(optional or {})},
    }


VIEW_MEMBERS: Final[Mapping[str, Any]] = {
    "pointer": POINTER,
    "depth": {"type": "integer", "minimum": 1, "maximum": MAX_DEPTH},
    "cursor": CURSOR,
    "limit": _limit(MAX_PAGE),
}


def _change_set_member(name: str) -> dict[str, str]:
    return _ref(f"change-set.schema.json#/properties/{name}")


#: §4.3: `preview_change`'s body is the ChangeSet without its idempotency key.
PREVIEW_REQUEST: Final = _object(
    {
        "edits": _change_set_member("edits"),
        "expected_revision": _change_set_member("expected_revision"),
    },
    {
        name: _change_set_member(name)
        for name in ("new_revision_id", "restore_from", "task", "author")
    },
)


def _result(name: str) -> dict[str, str]:
    """A JobControl or Inspection response shape: `$defs/<name>` of
    `application-results.schema.json` (ADR 0019 Amendment 1)."""
    return _ref(f"application-results.schema.json#/$defs/{name}")


#: ADR 0060 D11: `list_capabilities`. `kind` is one kind or several: over HTTP a query member
#: carries one value (a repeated one is refused, §11.3), so one kind travels as a string.
LIST_CAPABILITIES_REQUEST: Final = _object(
    {},
    {
        "kind": {
            "anyOf": [
                EXTENSION_KIND,
                {"type": "array", "minItems": 1, "uniqueItems": True, "items": EXTENSION_KIND},
            ]
        },
        "id_prefix": {"type": "string", "minLength": 1, "maxLength": 128},
        "cursor": CURSOR,
        "limit": _limit(MAX_PAGE),
    },
)
#: ADR 0060 D11: `check_admission`, exactly one of the pair form and the draft form (a revision
#: document, which F1-WO4b's check reads; this schema asks only for an object).
CHECK_ADMISSION_REQUEST: Final = {
    **_object(
        {},
        {
            "pair": _object(
                {"unit": EXTENSION_ID, "method": EXTENSION_ID},
                {
                    "definition": EXTENSION_ID,
                    "unit_version": EXTENSION_VERSION,
                    "method_version": EXTENSION_VERSION,
                },
            ),
            "revision": {"type": "object"},
        },
    ),
    "minProperties": 1,
    "maxProperties": 1,
}


# ================================================================================= decoding


def _members(*names: str) -> Callable[[Mapping[str, Any]], dict[str, Any]]:
    """The request members named, those present, as keyword arguments of the same names."""

    def decode(document: Mapping[str, Any]) -> dict[str, Any]:
        return {name: document[name] for name in names if name in document}

    return decode


def _unreserved(key: str, name: str) -> None:
    if key.startswith(RESERVED_KEY_PREFIX):
        raise DocumentSchemaError(
            name,
            "/idempotency_key",
            f"the key prefix {RESERVED_KEY_PREFIX!r} is reserved for in-process solve and "
            "reproduce; choose another key",
        )


def _decode_commit(document: Mapping[str, Any]) -> dict[str, Any]:
    change, expected_revision, idempotency_key = Change.from_change_set(document)
    _unreserved(idempotency_key, "commit_change")
    return {
        "change": change,
        "expected_revision": expected_revision,
        "idempotency_key": idempotency_key,
    }


#: §4.2: a preview has no key of its own; this placeholder completes the ChangeSet to build it.
PREVIEW_KEY: Final[str] = "preview"


def _decode_preview(document: Mapping[str, Any]) -> dict[str, Any]:
    change, expected_revision, _ = Change.from_change_set(
        {**document, "idempotency_key": PREVIEW_KEY}
    )
    return {"change": change, "expected_revision": expected_revision}


def _decode_submit(document: Mapping[str, Any]) -> dict[str, Any]:
    request = JobRequest.from_document(document)
    _unreserved(request.idempotency_key, "submit_job")
    return {"request": request}


def _decode_reproduce(document: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "bundle_path": document["bundle_path"],
        "policy": ReplayPolicy.from_document(document["policy"]),
    }


def _decode_wait(document: Mapping[str, Any]) -> dict[str, Any]:
    arguments = _members("job_id", "after_sequence", "timeout_s")(document)
    if "timeout_s" in arguments:
        arguments["timeout_s"] = min(float(arguments["timeout_s"]), TRANSPORT_WAIT_CAP_S)
    return arguments


def _document(result: Any) -> Any:
    return result.as_document()


def _page_of(item: Callable[[Any], Any]) -> Callable[[Page[Any]], dict[str, Any]]:
    return lambda page: page.as_document(item)


def _raw(result: bytes) -> bytes:
    return result


# ================================================================================== the table


def _row(
    name: str,
    right: Right,
    request_schema: Mapping[str, Any],
    response_schema: Mapping[str, Any] | None,
    http: tuple[str, str] | None,
    *,
    decode: Callable[[Mapping[str, Any]], dict[str, Any]],
    encode: Callable[[Any], Any] = _document,
    mcp_tool: str | None = None,
    transports: tuple[Transport, ...] = ALL_TRANSPORTS,
) -> Operation:
    if "mcp" in transports and mcp_tool is None:
        mcp_tool = name
    return Operation(
        name=name,
        method=name,
        right=right,
        request_schema=request_schema,
        response_schema=response_schema,
        http=http,
        mcp_tool=mcp_tool,
        transports=transports,
        description_file=f"descriptions/{name}.md" if "mcp" in transports else None,
        decode=decode,
        encode=encode,
    )


_VIEW = ("pointer", "depth", "cursor", "limit")

#: §4.3, in its order. The right of each row is §10.1's and equals `authz.OPERATION_RIGHTS`
#: (a test pins the two together; this module imports nothing outside the contract).
OPERATIONS: Final[Mapping[str, Operation]] = {
    row.name: row
    for row in (
        # Application (frozen)
        _row(
            "validate",
            "read",
            _object(
                {"revision_id": ID, "task": {"enum": ["simulation", "optimization"]}},
                {"optimization": _ref("optimization-request.schema.json")},
            ),
            _ref("validation-report.schema.json"),
            ("POST", "/v1/revisions/{revision_id}/validate"),
            decode=_members("revision_id", "task", "optimization"),
            mcp_tool="validate_revision",
        ),
        _row(
            "commit_change",
            "draft",
            _ref("change-set.schema.json"),
            _ref("transaction-result.schema.json"),
            ("POST", "/v1/changes"),
            decode=_decode_commit,
        ),
        _row(
            "solve",
            "execute",
            _object({"revision_id": ID, "policy_id": ID}),
            _ref("run-result.schema.json"),
            None,
            decode=_members("revision_id", "policy_id"),
            transports=("python", "cli"),
        ),
        _row(
            "reproduce",
            "execute",
            _object(
                {
                    "bundle_path": {"type": "string", "minLength": 1, "maxLength": 4096},
                    "policy": _object({"rerun": {"type": "boolean"}}),
                }
            ),
            {"$ref": REPLAY_REPORT_SCHEMA},
            None,
            decode=_decode_reproduce,
            transports=("python", "cli"),
        ),
        # JobControl
        _row(
            "submit_job",
            "execute",
            _ref("job.schema.json#/$defs/job_request"),
            _result("submit_result"),
            ("POST", "/v1/jobs"),
            decode=_decode_submit,
        ),
        _row(
            "get_job",
            "read",
            _object({"job_id": JOB_ID}),
            _ref("job.schema.json"),
            ("GET", "/v1/jobs/{job_id}"),
            decode=_members("job_id"),
        ),
        _row(
            "list_jobs",
            "read",
            _object(
                {},
                {
                    "status": {
                        "anyOf": [_ref("job.schema.json#/$defs/job_status"), {"type": "null"}]
                    },
                    "cursor": CURSOR,
                    "limit": _limit(MAX_PAGE),
                },
            ),
            _result("job_page"),
            ("GET", "/v1/jobs"),
            decode=_members("status", "cursor", "limit"),
            encode=_page_of(Job.as_document),
        ),
        _row(
            "list_job_events",
            "read",
            _object(
                {"job_id": JOB_ID},
                {
                    "after_sequence": {"type": "integer", "minimum": -1},
                    "limit": _limit(MAX_EVENT_PAGE),
                },
            ),
            _result("job_event_page"),
            ("GET", "/v1/jobs/{job_id}/events"),
            decode=_members("job_id", "after_sequence", "limit"),
            encode=_page_of(JobEvent.as_document),
        ),
        _row(
            "wait_job",
            "read",
            _object(
                {"job_id": JOB_ID},
                {
                    "after_sequence": {"type": "integer", "minimum": -1},
                    "timeout_s": {"type": "number", "minimum": 0},
                },
            ),
            _result("job_wait"),
            ("GET", "/v1/jobs/{job_id}/wait"),
            decode=_decode_wait,
        ),
        _row(
            "cancel_job",
            "execute",
            _object({"job_id": JOB_ID}),
            _ref("job.schema.json"),
            ("POST", "/v1/jobs/{job_id}/cancel"),
            decode=_members("job_id"),
        ),
        # ADR 0075 D8 (ADR 0019 Amendment 17): an optional display preference, echoed.
        _row(
            "get_job_result",
            "read",
            _object({"job_id": JOB_ID}, {"display_units": DISPLAY_UNITS}),
            _ref("job.schema.json#/$defs/job_result"),
            ("GET", "/v1/jobs/{job_id}/result"),
            decode=_members("job_id", "display_units"),
        ),
        # Inspection
        _row(
            "get_project",
            "read",
            _object({}),
            _result("project_summary"),
            ("GET", "/v1/project"),
            decode=_members(),
        ),
        _row(
            "list_models",
            "read",
            _object({}),
            _result("model_registry_view"),
            ("GET", "/v1/models"),
            decode=_members(),
        ),
        _row(
            "list_revisions",
            "read",
            _object({}, {"cursor": CURSOR, "limit": _limit(MAX_PAGE)}),
            _result("revision_page"),
            ("GET", "/v1/revisions"),
            decode=_members("cursor", "limit"),
            encode=_page_of(RevisionSummary.as_document),
        ),
        _row(
            "get_revision",
            "read",
            _object({"revision_id": ID}, VIEW_MEMBERS),
            _result("projection"),
            ("GET", "/v1/revisions/{revision_id}"),
            decode=_members("revision_id", *_VIEW),
        ),
        _row(
            "diff_revisions",
            "read",
            _object({"from_revision": ID, "to_revision": ID}),
            _result("semantic_diff"),
            ("GET", "/v1/revisions/{from_revision}/diff/{to_revision}"),
            decode=_members("from_revision", "to_revision"),
        ),
        _row(
            "inspect_structure",
            "read",
            _object({"revision_id": ID}, VIEW_MEMBERS),
            _result("projection"),
            ("GET", "/v1/revisions/{revision_id}/structure"),
            decode=_members("revision_id", *_VIEW),
        ),
        _row(
            "preview_change",
            "read",
            PREVIEW_REQUEST,
            _ref("transaction-result.schema.json"),
            ("POST", "/v1/changes/preview"),
            decode=_decode_preview,
        ),
        _row(
            "get_artifact",
            "read",
            _object({"artifact_id": ARTIFACT_ID}, VIEW_MEMBERS),
            _result("projection"),
            ("GET", "/v1/artifacts/{artifact_id}"),
            decode=_members("artifact_id", *_VIEW),
        ),
        # ADR 0068 (ST, ADR 0019 Amendment 13): an ended job's stream table, computed on read;
        # ADR 0075 D8 (ADR 0019 Amendment 17): an optional display preference, echoed.
        _row(
            "get_stream_table",
            "read",
            _object({"job_id": ID}, {**VIEW_MEMBERS, "display_units": DISPLAY_UNITS}),
            _result("projection"),
            ("GET", "/v1/jobs/{job_id}/stream-table"),
            decode=_members("job_id", *_VIEW, "display_units"),
        ),
        # ADR 0019 Amendment 3 (A3.3): the audit, by `seq`. Python, CLI and HTTP; no MCP tool
        # (an MCP tool needs a reviewed description). `order` is a string, not a boolean: the
        # HTTP binding converts only numeric query values.
        _row(
            "list_audit",
            "read",
            _object(
                {},
                {
                    "principal_id": {"anyOf": [ID, {"type": "null"}]},
                    "operation": {"type": ["string", "null"], "minLength": 1, "maxLength": 128},
                    "order": {"enum": ["ascending", "descending"]},
                    "cursor": CURSOR,
                    "limit": _limit(MAX_PAGE),
                },
            ),
            _result("audit_page"),
            ("GET", "/v1/audit"),
            decode=_members("principal_id", "operation", "order", "cursor", "limit"),
            encode=_page_of(AuditRecord.as_document),
            transports=("python", "cli", "http"),
        ),
        # ADR 0058 D7 (MSG §3.5): a message-catalogue entry; it reads no project state.
        _row(
            "explain",
            "read",
            _object({"code": MESSAGE_CODE}),
            _result("message_entry"),
            ("GET", "/v1/explain/{code}"),
            decode=_members("code"),
        ),
        # ADR 0060 D11 (F1, ADR 0019 Amendment 7): the extension registry; neither reads the
        # project.
        _row(
            "list_capabilities",
            "read",
            LIST_CAPABILITIES_REQUEST,
            _result("capability_page"),
            ("GET", "/v1/capabilities"),
            decode=_members("kind", "id_prefix", "cursor", "limit"),
        ),
        _row(
            "check_admission",
            "read",
            CHECK_ADMISSION_REQUEST,
            _result("admission_report"),
            ("POST", "/v1/admission/check"),
            decode=_members("pair", "revision"),
        ),
        # The raw export (Python, CLI, HTTP; never MCP)
        _row(
            "artifact_bytes",
            "read",
            _object({"artifact_id": ARTIFACT_ID}),
            None,
            ("GET", "/v1/artifacts/{artifact_id}/raw"),
            decode=_members("artifact_id"),
            encode=_raw,
            transports=("python", "cli", "http"),
        ),
    )
}

#: An unknown operation's name, as the audit records it: bounded, since it is request text.
_UNKNOWN_NAME_LIMIT: Final[int] = 128


# ================================================================================= dispatch


def project_error(error: ApiError) -> ApiError:
    """§10.4 over an error: its explanation attached as `detail.explanation` (MSG §3.3), then its
    message and every string and key of its detail bounded. Idempotent: an error projected
    once keeps the explanation it carries."""
    explained = explained_detail(error.as_document())
    return ApiError(
        code=error.code,
        message=bound_text(error.message, TEXT_LIMIT),
        retryable=error.retryable,
        detail=bound_document(explained["detail"]),
    )


def project_response(operation: Operation, document: Any) -> Any:
    """§10.4: the response every transport carries for `document` (`operation.encode` of the
    method's result) — every `ApiError` document it holds explained (MSG §3.3), then bounded;
    the raw export's bytes pass as they are."""
    if operation.response_schema is None:
        return document
    for location in error_locations(operation.name):
        document = _explained_at(document, location)
    return bound_document(document)


# ============================================================== explanations (MSG §3.3, §4.7)

_ERROR_SCHEMA: Final[str] = SCHEMA_BASE + "api-error.schema.json#"
#: A location's step into any array item or any member of a map.
ANY: Final[str] = "*"


def explained_detail(document: Mapping[str, Any]) -> dict[str, Any]:
    """An `ApiError` document with `detail.explanation` (surface null) attached, unless it
    carries one already. The explanation is rendered on the way out and stored nowhere (I2)."""
    from openflowsheet.messages.render import render_error

    detail = document.get("detail")
    if not isinstance(detail, Mapping):
        return dict(document)
    if isinstance(detail.get("explanation"), Mapping):
        return {**document, "detail": dict(detail)}
    return {**document, "detail": {**detail, "explanation": render_error(document)}}


@cache
def error_locations(name: str) -> tuple[tuple[str, ...], ...]:
    """Where `name`'s response schema `$ref`s `api-error.schema.json`: member names, and `ANY`
    for an array item or a map member. Read from the resolved response schema, so a new
    `ApiError` member of a result is explained without being listed anywhere."""
    schema = OPERATIONS[name].response_schema
    found: set[tuple[str, ...]] = set()
    if schema is not None:
        _error_refs(schema, published_schemas(), None, (), (), found)
    return tuple(sorted(found))


def _error_refs(
    node: Any,
    documents: Mapping[str, Mapping[str, Any]],
    base: str | None,
    path: tuple[str, ...],
    active: tuple[str, ...],
    found: set[tuple[str, ...]],
) -> None:
    if not isinstance(node, Mapping):
        return
    reference = node.get("$ref")
    if isinstance(reference, str):
        address, _, fragment = reference.partition("#")
        document_id = address or base
        if document_id is None or document_id not in documents:
            raise ValueError(f"$ref {reference!r} is not into a published schema")
        if f"{document_id}#{fragment}" == _ERROR_SCHEMA:
            found.add(path)
        elif f"{document_id}#{fragment}" not in active:
            target: Any = documents[document_id]
            for token in fragment.split("/")[1:]:
                token = token.replace("~1", "/").replace("~0", "~")
                target = target[int(token)] if isinstance(target, list) else target[token]
            _error_refs(
                target, documents, document_id, path, (*active, f"{document_id}#{fragment}"), found
            )
    for keyword in ("allOf", "anyOf", "oneOf"):
        for branch in node.get(keyword, ()):
            _error_refs(branch, documents, base, path, active, found)
    for keyword in ("if", "then", "else"):
        _error_refs(node.get(keyword), documents, base, path, active, found)
    for member, schema in (node.get("properties") or {}).items():
        _error_refs(schema, documents, base, (*path, member), active, found)
    for schema in (node.get("patternProperties") or {}).values():
        _error_refs(schema, documents, base, (*path, ANY), active, found)
    for keyword in ("additionalProperties", "items"):
        _error_refs(node.get(keyword), documents, base, (*path, ANY), active, found)
    for schema in node.get("prefixItems", ()):
        _error_refs(schema, documents, base, (*path, ANY), active, found)


def _explained_at(document: Any, location: tuple[str, ...]) -> Any:
    """`document` with the `ApiError` documents at `location` explained (new containers along
    the location; nothing the caller holds is mutated)."""
    if not location:
        if isinstance(document, Mapping) and isinstance(document.get("code"), str):
            return explained_detail(document)
        return document
    step, rest = location[0], location[1:]
    if step == ANY:
        if isinstance(document, list):
            return [_explained_at(item, rest) for item in document]
        if isinstance(document, Mapping):
            return {key: _explained_at(value, rest) for key, value in document.items()}
        return document
    if isinstance(document, Mapping) and step in document:
        return {**document, step: _explained_at(document[step], rest)}
    return document


def dispatch(app: Dispatchable, name: str, request: Any) -> Any:
    """§4.3: the one path from a request document to a response, for every binding.

    Raises `ApplicationError` carrying a bounded `ApiError` for every refusal; returns the
    bounded response document (the raw export: bytes).
    """
    operation = OPERATIONS.get(name) if isinstance(name, str) else None
    if operation is None:
        shown = bound_text(str(name), _UNKNOWN_NAME_LIMIT)
        app.audit_refusal(shown, "invalid_request")
        raise ApplicationError(
            project_error(
                ApiError(
                    code="invalid_request",
                    message="no such operation",
                    retryable=False,
                    detail={"operation": shown, "operations": sorted(OPERATIONS)},
                )
            )
        )
    arguments = _decoded(app, operation, request)
    try:
        result = getattr(app, operation.method)(**arguments)
    except ApplicationError as refused:
        raise ApplicationError(project_error(refused.error)) from None
    return project_response(operation, operation.encode(result))


def _decoded(app: Dispatchable, operation: Operation, request: Any) -> dict[str, Any]:
    """Steps 1–3: canonical form, schema, typed arguments; a refusal is audited and raised."""
    pointer = first_noncanonical(request)
    if pointer is not None:
        app.audit_refusal(operation.name, "document_not_canonical")
        raise ApplicationError(
            project_error(
                ApiError(
                    code="document_not_canonical",
                    message="a value has no canonical JSON form (NaN, an infinity, an integer "
                    "beyond 2^53 that is not a binary64's canonical spelling, or not JSON at "
                    "all)",
                    retryable=False,
                    detail={"pointer": pointer},
                )
            )
        )
    try:
        validate_inline(operation.name, operation.request_schema, request)
        return operation.decode(request)
    except DocumentSchemaError as error:
        app.audit_refusal(operation.name, "invalid_request")
        refused = api_error("invalid_request", error.message, pointer=error.pointer)
        raise ApplicationError(project_error(refused.error)) from None
