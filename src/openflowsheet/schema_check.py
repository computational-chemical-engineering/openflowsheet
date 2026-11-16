"""Document validation against the published schemas under `schemas/` (ADR 0076 I-5).

`schema_errors` lists every error of a document against `schemas/<reference>`. `validate_document`
raises `DocumentSchemaError` for the first error in the same order. The schemas, their `$ref`
registry (the producer reading and J5's consumer reading) and one validator per reference are built
once from the packaged schema files and cached for the process's life. Foundation code: it imports
no application, solver or model module, so the assessment spec and the application layer validate
documents the same way (S19 A12, from `application.types`).
"""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
from functools import cache
from importlib.resources.abc import Traversable
from typing import Any, Final

from jsonschema import Draft202012Validator
from referencing import Registry
from referencing.jsonschema import DRAFT202012

from openflowsheet.resources import packaged

#: The published schemas (the repository's `schemas/`), as the package carries them: through
#: `importlib.resources`, so a source checkout, an editable install and an installed wheel read the
#: same bytes (T08 W4.2, `openflowsheet.resources`).
SCHEMA_DIR: Final[Traversable] = packaged("schemas")
SCHEMA_BASE: Final[str] = "https://github.com/frankp/process-runtime/schemas/"


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
