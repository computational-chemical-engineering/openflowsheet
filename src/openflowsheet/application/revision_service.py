"""`RevisionService`: the revision operations, the change transaction (K06) and the stored
revisions' reads (ADR 0076 I-12d, above `InspectionService`).

`LocalApplication` delegates `commit_change`, `preview_change`, `list_revisions`, `get_revision` and
`diff_revisions` here; their contract documentation is the facade's. The stored-revision read
(`revision`), the projection checks (`check_view`, `project`) and the
list cursor (`decode_cursor`, `encode_cursor`) are shared with the services above.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any, Final

from openflowsheet.application import validation
from openflowsheet.application.contract import Page, Projection
from openflowsheet.application.errors import ApiError, ApiErrorCode, ApplicationError
from openflowsheet.application.inspection_service import InspectionService
from openflowsheet.application.inspection_types import RevisionSummary
from openflowsheet.application.projection import MAX_PAGE, check_view_arguments, project
from openflowsheet.application.replacement import (
    ReplacementReport,
    check_replacements,
    unpromoted_surrogates,
)
from openflowsheet.application.revision_edits import (
    EditPathError,
    apply_edits,
    revision_diff,
    semantic_diff,
)
from openflowsheet.application.revisions import Revision
from openflowsheet.application.service_core import ServiceCore
from openflowsheet.application.store import ProjectStore, atomic_write_bytes
from openflowsheet.application.store_records import ArtifactRow, AuditEntry, LedgerRow
from openflowsheet.application.transaction_types import Change, SemanticDiff, TransactionResult
from openflowsheet.application.validation_report import ValidationReport
from openflowsheet.canonical import canonical_json, document_sha256, first_noncanonical
from openflowsheet.schema_check import DocumentSchemaError, validate_document

#: ADR 0035 D3: where a promotion's reports live under the files root.
REPLACEMENTS_DIR: Final = "replacements"


class RevisionService:
    """The revision operations over one caller's `ServiceCore`. Each public method is the
    `LocalApplication` method of the same name, documented there; it takes every argument
    explicitly (the defaults are the facade's). Public methods without a facade namesake serve the
    services above this one."""

    def __init__(self, core: ServiceCore, inspection: InspectionService) -> None:
        self._core = core
        self._inspection = inspection

    def commit_change(
        self, change: Change, expected_revision: str | None, idempotency_key: str
    ) -> TransactionResult:
        operation = "commit_change"
        caller = self._core.authorize(operation)
        request = change.as_change_set(expected_revision, idempotency_key)
        rejected = self._check_request(request, operation, idempotency_key)
        if rejected is not None:
            return rejected
        request_sha256 = document_sha256(request)
        principal_id = caller.principal_id
        store = self._core.store

        with store.reading() as connection:
            prior = store.ledger_lookup(connection, principal_id, operation, idempotency_key)
            head = store.head(connection)
        if prior is not None:
            return self._replayed(prior, request_sha256, idempotency_key)
        if expected_revision != head:
            return _conflict(expected_revision, head, idempotency_key)

        prepared = self._prepare(change, expected_revision, idempotency_key, operation)
        if isinstance(prepared, TransactionResult):
            return prepared

        revision = prepared.revision
        result: TransactionResult | None = None
        with store.writing() as connection:
            prior = store.ledger_lookup(connection, principal_id, operation, idempotency_key)
            actual = store.head(connection)
            taken = store.get_revision(connection, revision.revision_id) is not None
            if prior is None and actual == expected_revision and not taken:
                store.commit_revision(
                    connection,
                    revision,
                    principal_id=principal_id,
                    capability_id=caller.capability_id,
                    policy_sha256=self._core.policy.current().policy_sha256,
                )
                # ADR 0035 D3: a promotion's reports, stored and registered with the revision.
                self._store_replacements(connection, revision.revision_id, prepared.replacements)
                invalidations = (
                    tuple(store.evidence_for_revision(connection, expected_revision))
                    if expected_revision is not None
                    else ()
                )
                result = TransactionResult(
                    status="committed",
                    revision_id=revision.revision_id,
                    validation=prepared.report,
                    diff=prepared.diff,
                    invalidations=invalidations,
                    idempotency_key=idempotency_key,
                )
                store.ledger_insert(
                    connection,
                    principal_id,
                    operation,
                    idempotency_key,
                    request_sha256,
                    result.as_document(),
                )
                store.audit(
                    connection,
                    AuditEntry(
                        principal_id=principal_id,
                        capability_id=caller.capability_id,
                        operation=operation,
                        outcome="allowed",
                        request_sha256=request_sha256,
                        effect=f"revision:{revision.revision_id}",
                    ),
                )
        if result is not None:
            return result
        # Another writer got in between the snapshot and the lock; say which way it moved.
        if prior is not None:
            return self._replayed(prior, request_sha256, idempotency_key)
        if actual != expected_revision:
            return _conflict(expected_revision, actual, idempotency_key)
        return self._rejected(
            operation,
            idempotency_key,
            "invalid_request",
            f"revision id {revision.revision_id!r} is taken; a revision is never replaced",
            pointer="/new_revision_id",
            reason="revision_id_taken",
        )

    def decode_cursor(self, cursor: str | None, operation: str) -> int:
        if cursor is None:
            return 0
        try:
            decoded = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        except (ValueError, TypeError, binascii.Error):
            decoded = None
        ordinal = decoded.get("ordinal") if isinstance(decoded, dict) else None
        if (
            not isinstance(decoded, dict)
            or set(decoded) != {"ordinal"}
            or isinstance(ordinal, bool)
            or not isinstance(ordinal, int)
            or ordinal < 0
        ):
            self._core.refuse(
                "invalid_request",
                "cursor is not one this list issued",
                operation=operation,
                pointer="/cursor",
            )
        return int(ordinal)

    def preview_change(self, change: Change, expected_revision: str | None) -> TransactionResult:
        operation = "preview_change"
        self._core.authorize(operation)
        # The key is `commit_change`'s, not the preview's; a placeholder satisfies the schema.
        rejected = self._check_request(
            change.as_change_set(expected_revision, "preview"), operation, ""
        )
        if rejected is not None:
            return rejected
        prepared = self._prepare(change, expected_revision, "", operation)
        if isinstance(prepared, TransactionResult):
            return prepared
        return TransactionResult(
            status="previewed",
            revision_id=None,
            validation=prepared.report,
            diff=prepared.diff,
        )

    def list_revisions(self, *, cursor: str | None, limit: int) -> Page[RevisionSummary]:
        operation = "list_revisions"
        self._core.authorize(operation)
        self._inspection.check_limit(limit, MAX_PAGE, operation)
        after = self.decode_cursor(cursor, operation)
        rows, more = self._core.store.list_revisions(after_ordinal=after, limit=limit)
        next_cursor = encode_cursor(rows[-1][0]) if more else None
        return Page(items=tuple(summary for _, summary in rows), next_cursor=next_cursor)

    def get_revision(
        self, revision_id: str, *, pointer: str, depth: int, cursor: str | None, limit: int
    ) -> Projection:
        operation = "get_revision"
        self._core.authorize(operation)
        self.check_view(operation, pointer, depth, cursor, limit)
        document = self.revision(revision_id, operation).as_document()
        return self.project(
            operation,
            document,
            revision_id,
            document_sha256(document),
            pointer,
            depth,
            cursor,
            limit,
        )

    def diff_revisions(self, from_revision: str, to_revision: str) -> SemanticDiff:
        operation = "diff_revisions"
        self._core.authorize(operation)
        before = self.revision(from_revision, operation)
        after = self.revision(to_revision, operation)
        return revision_diff(before.document, after.document)

    def revision(self, revision_id: str, operation: str) -> Revision:
        with self._core.store.reading() as connection:
            revision = self._core.store.get_revision(connection, revision_id)
        if revision is None:
            self._core.refuse(
                "not_found", "no such revision", operation=operation, revision_id=revision_id
            )
        return revision

    def check_view(
        self, operation: str, pointer: object, depth: object, cursor: object, limit: object
    ) -> None:
        """§11.4's argument rules, before any document is read or built."""
        try:
            check_view_arguments(pointer, depth, cursor, limit)
        except ApplicationError as refused:
            self._core.refuse_error(refused.error, operation, None)

    def project(
        self,
        operation: str,
        document: Any,
        subject_id: str,
        sha256: str,
        pointer: str,
        depth: int,
        cursor: str | None,
        limit: int,
    ) -> Projection:
        try:
            return project(
                document,
                subject_id=subject_id,
                sha256=sha256,
                pointer=pointer,
                depth=depth,
                cursor=cursor,
                limit=limit,
            )
        except ApplicationError as refused:
            self._core.refuse_error(refused.error, operation, None)

    def _check_request(
        self, request: dict[str, Any], operation: str, idempotency_key: str
    ) -> TransactionResult | None:
        """Q29 first (a non-canonical value is `rejected`), then the ChangeSet schema (raised)."""
        pointer = first_noncanonical(request)
        if pointer is not None:
            return self._rejected(
                operation,
                idempotency_key,
                "document_not_canonical",
                "a value has no canonical JSON form (NaN, an infinity, an integer beyond 2^53 that "
                "is not a binary64's canonical spelling, or not JSON at all)",
                pointer=pointer,
            )
        try:
            validate_document("change-set.schema.json", request)
        except DocumentSchemaError as error:
            self._core.refuse(
                "invalid_request", error.message, operation=operation, pointer=error.pointer
            )
        return None

    def _prepare(
        self,
        change: Change,
        expected_revision: str | None,
        idempotency_key: str,
        operation: str,
    ) -> _Prepared | TransactionResult:
        """Steps 4–6 from one snapshot: the new document, its validation and its diff.

        Raised: an optimization task (U05). Rejected: an expected or restore revision that does not
        exist, a new revision id that is taken, and, from `_new_document`, an edit path that does
        not resolve and a promotion `_check_promotion` refuses."""
        if change.task == "optimization":
            # U05 (T08 review 2, Ruling 1), as `validate` refuses it: no optimization formulation
            # is checked in v0.1. Audited, before the snapshot is read or anything is built.
            self._core.refuse(
                "unsupported",
                "task_unsupported(optimization)",
                operation=operation,
                pointer="/task",
            )
        store = self._core.store
        # A refusal is audited, and the audit writes; it is issued after the snapshot closes. An
        # in-memory store is one connection, where a write inside the open read would nest a
        # transaction (T07 review M2).
        refusal: tuple[ApiErrorCode, str, dict[str, Any]] | None = None
        revision_id = ""
        with store.reading() as connection:
            expected: Mapping[str, Any] = {}
            if expected_revision is not None:
                found = store.get_revision(connection, expected_revision)
                if found is None:
                    refusal = (
                        "not_found",
                        "the expected revision does not exist",
                        {"pointer": "/expected_revision"},
                    )
                else:
                    expected = found.document
            start = expected
            if refusal is None and change.restore_from is not None:
                restored = store.get_revision(connection, change.restore_from)
                if restored is None:
                    refusal = (
                        "not_found",
                        "the revision to restore from does not exist",
                        {"pointer": "/restore_from"},
                    )
                else:
                    start = restored.document
            if refusal is None and change.new_revision_id is not None:
                if store.get_revision(connection, change.new_revision_id) is not None:
                    refusal = (
                        "invalid_request",
                        f"revision id {change.new_revision_id!r} is taken; a revision is never "
                        "replaced",
                        {"pointer": "/new_revision_id", "reason": "revision_id_taken"},
                    )
                else:
                    revision_id = change.new_revision_id
            elif refusal is None:
                revision_id = _assigned_revision_id(store, connection)
        if refusal is not None:
            code, message, detail = refusal
            return self._rejected(operation, idempotency_key, code, message, **detail)
        new = self._new_document(expected, start, change, operation, idempotency_key)
        if isinstance(new, TransactionResult):
            return new
        document, reports = new
        revision = Revision(
            revision_id=revision_id, document=document, parent_revision=expected_revision
        )
        return _Prepared(
            revision=revision,
            report=validation.validate(
                revision.as_document(), change.task, surrogates=self._core.surrogates()
            ),
            diff=semantic_diff(expected, document),
            replacements=reports,
        )

    def _new_document(
        self,
        expected: Mapping[str, Any],
        start: Mapping[str, Any],
        change: Change,
        operation: str,
        idempotency_key: str,
    ) -> tuple[Any, tuple[ReplacementReport, ...]] | TransactionResult:
        """`_prepare`'s new document and its promotion reports: `change.edits` applied to `start`,
        the result canonical, the promotions from `expected` checked (`_check_promotion`) and, when
        there are any, their report hashes written into the provenance. Rejected: an edit path
        that does not resolve, and a promotion `_check_promotion` refuses."""
        try:
            built = apply_edits(start, change.edits)
        except EditPathError as error:
            return self._rejected(
                operation,
                idempotency_key,
                "invalid_request",
                str(error),
                pointer=f"/edits/{error.edit_index}/path",
                reason="edit_path_invalid",
                edit_index=error.edit_index,
                document_pointer=error.pointer,
            )
        # What is validated is exactly what is stored: the canonical document, read back.
        document = json.loads(canonical_json(built))
        # ADR 0035 D2–D3 (M02 design note §6.2): a change of a variant-backed model reference is a
        # promotion (M04 spec §8.3: or a surrogate-backed one, judged with the project's
        # resolver), checked before anything is validated (`_check_promotion`). A compatible one
        # writes each report's SHA-256 into the provenance (outside the content hash), so the
        # preview and the commit name the same document.
        reports = check_replacements(expected, document, surrogates=self._core.surrogates())
        rejected = self._check_promotion(expected, document, reports, operation, idempotency_key)
        if rejected is not None:
            return rejected
        if reports:
            document = json.loads(canonical_json(_with_report_hashes(document, reports)))
        return document, reports

    def _check_promotion(
        self,
        expected: Mapping[str, Any],
        document: Mapping[str, Any],
        reports: tuple[ReplacementReport, ...],
        operation: str,
        idempotency_key: str,
    ) -> TransactionResult | None:
        """ADR 0035 D2–D3 and M04 spec §20 A3.1: a change's promotions, judged (`rejected`,
        audited): the first incompatible replacement of `reports` (any failed facet rejects it,
        with its report), then the first surrogate of `document` that no replacement judged and
        that is not promoted against `expected`; `None` when there is neither."""
        incompatible = [report for report in reports if not report.compatible]
        if incompatible:
            report = incompatible[0]
            return self._rejected(
                operation,
                idempotency_key,
                "model_replacement_incompatible",
                f"model_replacement_incompatible({report.instance_id}: {', '.join(report.failed)})",
                report=report.as_document(),
            )
        # M04 spec §20 A3.1 (R-360): a surrogate that no replacement judged — added, renamed, in
        # the first revision — enters only with a PROMOTABLE re-derived verdict.
        unpromoted = unpromoted_surrogates(expected, document, surrogates=self._core.surrogates())
        if unpromoted:
            instance_id, why = unpromoted[0]
            reason = f"surrogate_not_promoted({instance_id})"
            return self._rejected(
                operation,
                idempotency_key,
                "model_replacement_incompatible",
                f"model_replacement_incompatible({reason}: {why})",
                reason=reason,
                instance_id=instance_id,
                cause=why,
            )
        return None

    def _store_replacements(
        self,
        connection: sqlite3.Connection,
        revision_id: str,
        reports: tuple[ReplacementReport, ...],
    ) -> None:
        """ADR 0035 D3: each report as an artifact (kind `model_replacement_report`, no job),
        its bytes the canonical document whose SHA-256 the revision's provenance names."""
        for report in reports:
            data = canonical_json(report.as_document())
            relpath = f"{REPLACEMENTS_DIR}/{revision_id}/{report.instance_id}.json"
            (self._core.files_root / relpath).parent.mkdir(parents=True, exist_ok=True)
            atomic_write_bytes(self._core.files_root / relpath, data)
            self._core.store.register_artifacts(
                connection,
                [
                    ArtifactRow(
                        artifact_id=f"{revision_id}:model_replacement:{report.instance_id}",
                        job_id=None,
                        kind="model_replacement_report",
                        name=f"model-replacement-{report.instance_id}.json",
                        sha256=hashlib.sha256(data).hexdigest(),
                        size_bytes=len(data),
                        relpath=relpath,
                    )
                ],
            )

    def _replayed(
        self, prior: LedgerRow, request_sha256: str, idempotency_key: str
    ) -> TransactionResult:
        """§7: the original result, `replayed`; a different request under the key is refused."""
        if prior.request_sha256 != request_sha256:
            self._core.refuse(
                "idempotency_key_reused",
                "this idempotency key was used with a different change set; use a new key for a "
                "new change",
                operation="commit_change",
                request_sha256=request_sha256,
                original_request_sha256=prior.request_sha256,
            )
        return replace(TransactionResult._build(prior.result), status="replayed")

    def _rejected(
        self,
        operation: str,
        idempotency_key: str,
        code: ApiErrorCode,
        message: str,
        **detail: Any,
    ) -> TransactionResult:
        """A `rejected` domain result, audited as a refusal (§10.7)."""
        self._core.audit_refusal(operation, code, None)
        return TransactionResult(
            status="rejected",
            revision_id=None,
            validation=None,
            diff=None,
            idempotency_key=idempotency_key,
            error=ApiError(code=code, message=message, retryable=False, detail=detail),
        )


@dataclass(frozen=True)
class _Prepared:
    revision: Revision
    report: ValidationReport
    diff: SemanticDiff
    #: ADR 0035: the compatible promotions this change makes (empty for any other change).
    replacements: tuple[ReplacementReport, ...] = ()


def _with_report_hashes(
    document: Mapping[str, Any], reports: tuple[ReplacementReport, ...]
) -> dict[str, Any]:
    """`document` with `provenance.artifact_hashes["model_replacement:<instance>"]` = each
    report's SHA-256 (ADR 0035 D3; outside the content hash, ADR 0002 D4). A document without a
    provenance object is returned as it is: its validation reports the missing member."""
    provenance = document.get("provenance")
    if not isinstance(provenance, Mapping):
        return dict(document)
    hashes = dict(provenance.get("artifact_hashes") or {})
    for report in reports:
        hashes[f"model_replacement:{report.instance_id}"] = document_sha256(report.as_document())
    return {**document, "provenance": {**provenance, "artifact_hashes": hashes}}


def _conflict(expected: str | None, actual: str | None, idempotency_key: str) -> TransactionResult:
    return TransactionResult(
        status="conflict",
        revision_id=None,
        validation=None,
        diff=None,
        conflict={"expected": expected, "actual": actual},
        idempotency_key=idempotency_key,
    )


def _assigned_revision_id(store: ProjectStore, connection: sqlite3.Connection) -> str:
    """§5.2: `rev-<ordinal:06d>`, stepping past an id a caller already took by name."""
    ordinal = store.next_revision_ordinal(connection)
    while store.get_revision(connection, f"rev-{ordinal:06d}") is not None:
        ordinal += 1
    return f"rev-{ordinal:06d}"


def encode_cursor(ordinal: int) -> str:
    """§11.4: a list's cursor, `base64url(canonical_json({"ordinal": k}))` unpadded, `k` the
    ordinal of the last item returned."""
    encoded = base64.urlsafe_b64encode(canonical_json({"ordinal": ordinal}))
    return encoded.decode("ascii").rstrip("=")
