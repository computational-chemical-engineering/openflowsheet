"""The published schemas and the document checks of the application contract v1 (T07 design note
§5, ADR 0019 D2; ADR 0076 I-12a).

Every typed document's `from_document()` validates against its published schema under `schemas/`
before building anything, and reports an invariant the schema cannot state the same way
(`checked`).

**J5, closed for producers and open for consumers.** `from_document` is strict by default: it
validates against the schemas as published, whose artifact- and event-kind enums are closed.
`from_document(..., lenient=True)` is the consumer's reader. It opens the artifact-kind enum, and
reads an event whose kind it does not know through its common members only — `job_id`,
`sequence`, `kind`, `ends_job`, `recorded_at` — keeping the rest as an opaque `payload`, so an
unknown event that ends the job is still seen to end it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from functools import cache
from typing import Any, Final

from jsonschema import Draft202012Validator

from openflowsheet.application.jobs.model import EVENT_KINDS
from openflowsheet.schema_check import (
    SCHEMA_BASE,
    DocumentSchemaError,
    _consumer_job_schema,
    _published,
    _raise_first,
    _registry,
)

EVENT_COMMON_MEMBERS: Final[tuple[str, ...]] = (
    "job_id",
    "sequence",
    "kind",
    "ends_job",
    "recorded_at",
)


# ============================================================================ schema validation


def _event_common_schema() -> dict[str, Any]:
    """The common members of a job event, whatever its kind (J5's consumer rule)."""
    published = _published()[SCHEMA_BASE + "job-event.schema.json"]["properties"]
    properties = {name: published[name] for name in EVENT_COMMON_MEMBERS}
    properties["kind"] = {"type": "string", "minLength": 1}
    return {"type": "object", "required": list(EVENT_COMMON_MEMBERS), "properties": properties}


@cache
def event_common_validator() -> Draft202012Validator:
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


def checked[T](
    reference: str, build: Callable[[Mapping[str, Any]], T], document: Mapping[str, Any]
) -> T:
    """Build after validation; an invariant the schema cannot state is reported the same way."""
    try:
        return build(document)
    except ValueError as error:
        if isinstance(error, DocumentSchemaError):
            raise
        raise DocumentSchemaError(reference, "", str(error)) from error


def validate_inline(label: str, schema: Mapping[str, Any], document: Any) -> None:
    """Raise `DocumentSchemaError` (named `label`) unless `document` satisfies `schema`: a schema
    that is not published itself but may `$ref` the published ones — `operations`' request and
    composite-response envelopes."""
    _raise_first(label, Draft202012Validator(schema, registry=_registry(False)), document)
