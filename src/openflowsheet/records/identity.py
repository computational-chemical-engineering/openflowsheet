"""Record identity (ADR 0061 D2): the normaliser, validation and the SHA, in D2's order.

`identify` is the one path that hashes a record: D2 steps 1 to 5 (`normalize`), step 6
(`validate`), step 7 (`record_sha256`). The SHA is that of the canonical JSON (ADR 0002 D3) of the
identity projection, the normalised record without its top-level `volatile` member (Q9.R2), so
what moves it is a schema fact (Q9.A1). A refused record has no SHA.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from openflowsheet.canonical import document_sha256
from openflowsheet.records.model import RecordOutcome
from openflowsheet.records.normalize import normalize
from openflowsheet.records.validate import validate

if TYPE_CHECKING:
    from openflowsheet.registry import Registry


def identify(
    source: str | bytes | Mapping[str, Any], *, registry: Registry | None = None
) -> RecordOutcome:
    """D2 on one record (JSON or YAML text, or a parsed document) against `registry`'s record
    types and correlation forms (the process registry when `None`). The outcome's `errors` are
    the normaliser's and step 6's; its `findings` D6's notices and step 6's; its `record_sha256`
    is `None` when there is an error. A record the normaliser refuses is not validated."""
    normalized = normalize(source)
    if normalized.errors and not normalized.record:
        return RecordOutcome(normalized.record, normalized.volatile, None, normalized.errors)
    if registry is None:
        from openflowsheet.registry import default_registry

        registry = default_registry()
    errors, findings = validate(
        normalized.record,
        normalized.volatile,
        anchor_derived=normalized.anchor_derived,
        registry=registry,
    )
    errors = normalized.errors + errors
    return RecordOutcome(
        normalized.record,
        normalized.volatile,
        None if errors else record_sha256(normalized.record),
        errors,
        normalized.findings + findings,
    )


def record_sha256(projection: Mapping[str, Any]) -> str:
    """D2 step 7: SHA-256 of the canonical JSON of a normalised identity projection."""
    return document_sha256(projection)
