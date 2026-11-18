"""The transaction documents of the application contract v1 (T07 design note §5.2, ADR 0019 D2;
ADR 0076 I-12a): `Edit`, `Change`, `ChangeSet`, `SemanticDiff` and `TransactionResult`.

They are defined here once (K06's `transactions.py` facade is gone, ADR 0076 I-11); the
transaction core that produces them (`apply_edits`, `semantic_diff`) lives in `revision_edits`
(W2b; S17 R2).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, Self

from openflowsheet.application.documents import checked
from openflowsheet.application.errors import ApiError
from openflowsheet.application.validation_report import (
    Check,
    Task,
    ValidationReport,
)
from openflowsheet.schema_check import validate_document

EditOperation = Literal["set", "remove", "append"]
TransactionStatus = Literal["committed", "replayed", "conflict", "rejected", "previewed"]


# ================================================================================ ApiError §5.8


def error_document(error: ApiError | None) -> dict[str, Any] | None:
    return error.as_document() if error is not None else None


def error_build(document: Mapping[str, Any] | None) -> ApiError | None:
    return ApiError._build(document) if document is not None else None


# ===================================================================== ChangeSet §5.2 and Edit


@dataclass(frozen=True)
class Edit:
    """§5.2. `set` and `append` carry a `value` (possibly null); `remove` carries none.

    Parameters
    ----------
    operation
        `"set"`, `"append"` or `"remove"`.
    path
        The JSON path into the revision document: member names and array indices, for example
        `("specifications", 4, "value")`.
    value
        The new value for `set` and `append`; omitted for `remove`.
    """

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
        return checked(reference, cls._build, document)

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

    Parameters
    ----------
    edits
        The edits, applied in order to the head revision (`Edit`).
    new_revision_id
        The new revision's id; the project assigns `rev-<ordinal>` when omitted.
    restore_from
        A revision to restore as the new head instead of editing.
    task
        The task the new revision is validated for.
    author
        Recorded in the revision's provenance.
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
        change = checked(
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


#: ADR 0019 Amendment 3 (A3.2): the list members whose items `diff_revisions` pairs by `id`.
DiffMember = Literal["instances", "connections", "specifications"]
DiffChange = Literal["added", "removed", "changed"]


@dataclass(frozen=True)
class DiffElement:
    """ADR 0019 Amendment 3 (A3.2; M06 design note §4.2): one item of `instances`, `connections`
    or `specifications` that differs between two revisions. `id` is `None` when the member's
    items cannot be paired by id; `paths` are the key paths inside a `changed` item, from its
    root, in code-point order (empty for `added`, `removed` and an unpaired member)."""

    member: DiffMember
    id: str | None
    change: DiffChange
    paths: tuple[tuple[str, ...], ...] = ()

    def as_document(self) -> dict[str, Any]:
        return {
            "member": self.member,
            "id": self.id,
            "change": self.change,
            "paths": [list(path) for path in self.paths],
        }


@dataclass(frozen=True)
class SemanticDiff:
    """What changed, by path, in the revision's *content* — not its title or provenance.

    `elements` is `diff_revisions`'s alone (ADR 0019 Amendment 3, A3.2): `None` — and absent from
    the document — in `commit_change`'s and `preview_change`'s `TransactionResult.diff`, whose
    schema and ledger replays it does not change."""

    added: tuple[str, ...]
    removed: tuple[str, ...]
    changed: tuple[str, ...]
    elements: tuple[DiffElement, ...] | None = None

    @property
    def empty(self) -> bool:
        return not (self.added or self.removed or self.changed)

    def as_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "added": list(self.added),
            "removed": list(self.removed),
            "changed": list(self.changed),
        }
        if self.elements is not None:
            document["elements"] = [element.as_document() for element in self.elements]
        return document


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
            "error": error_document(self.error),
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
            error=error_build(document["error"]),
        )
