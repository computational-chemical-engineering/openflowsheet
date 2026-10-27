"""The assessment document: load, validate, and its identity (E01 design §4.1, §4.11).

An `AssessmentSpec` is a document valid against `schemas/assessment.schema.json`, with canonical
JSON nodes only (ADR 0002 D3), identified by `assessment_sha256`, the canonical hash of the whole
document. Every data file it uses (correlation set, index series, exchange rates, LCA tables) is
named inside it by `{id, sha256}`, so this hash covers data content too. A document that fails
either check raises `AssessmentDocumentError` listing every error: a malformed request is the
caller's mistake, not an evaluation result (§4.12's refusals are for evaluation).
"""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final

from openflowsheet.application.types import schema_errors
from openflowsheet.canonical import document_sha256, first_noncanonical

__all__ = ["SCHEMA_REFERENCE", "AssessmentDocumentError", "AssessmentSpec", "load_assessment"]

#: The schema an assessment document is validated against, by its file name under `schemas/`.
SCHEMA_REFERENCE: Final = "assessment.schema.json"


class AssessmentDocumentError(ValueError):
    """The document is not a valid, canonical assessment; `errors` lists every reason."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class AssessmentSpec:
    """A validated assessment document and its identity. The document is a private deep copy."""

    document: Mapping[str, Any]
    assessment_sha256: str

    @property
    def assessment_id(self) -> str:
        return str(self.document["assessment_id"])

    def section(self, name: str) -> Any:
        """A top-level section, or `None` when the document does not have it."""
        return self.document.get(name)


def load_assessment(source: Mapping[str, Any] | str | Path) -> AssessmentSpec:
    """An `AssessmentSpec` from a document or a JSON file; `AssessmentDocumentError` otherwise."""
    if isinstance(source, str | Path):
        document: Any = json.loads(Path(source).read_text(encoding="utf-8"))
    else:
        document = copy.deepcopy(dict(source))
    pointer = first_noncanonical(document)
    if pointer is not None:
        raise AssessmentDocumentError(
            [f"{pointer or '/'}: no canonical JSON form (ADR 0002 D3); the identity is undefined"]
        )
    errors = schema_errors(SCHEMA_REFERENCE, document)
    if errors:
        raise AssessmentDocumentError(errors)
    return AssessmentSpec(MappingProxyType(document), document_sha256(document))
