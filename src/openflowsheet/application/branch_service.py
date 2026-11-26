"""The `Branches` operations (ADR 0078 D2, ADR 0019 Amendment 18): named refs in the store's
`refs` table.

A branch is the `refs` row `branches/<name>` (D2.1); `head` keeps its row and its meaning, and no
table, column or store schema changes. `list_branches` reads `head` and the branch rows;
`create_branch` and `delete_branch` write one row each, under the idempotency ledger (ADR 0019
D3, scope `(principal, operation, key)`), each in one `BEGIN IMMEDIATE` transaction. Each
operation first checks its request as `dispatch` does (the canonical form, then the operation's
request schema), so the Python transport refuses what the others refuse (rule C1), then
authorizes. A commit on a branch is `commit_change` with `Change.branch` (`RevisionService`);
promoting one is `commit_change` on `head` with `restore_from` its tip.

`LocalApplication` delegates the three operations here; their contract documentation is the
facade's.
"""

from __future__ import annotations

import base64
import binascii
import json
import sqlite3
from collections.abc import Mapping
from typing import Any, Final, NoReturn

from openflowsheet.application.contract import Page
from openflowsheet.application.documents import validate_inline
from openflowsheet.application.operations import OPERATIONS
from openflowsheet.application.policy_types import CapabilityReference
from openflowsheet.application.service_core import ServiceCore
from openflowsheet.application.store import BRANCH_PREFIX, HEAD
from openflowsheet.application.store_records import AuditEntry, LedgerRow
from openflowsheet.application.transaction_types import HEAD_REF, Branch, BranchResult
from openflowsheet.canonical import canonical_json, document_sha256, first_noncanonical
from openflowsheet.schema_check import DocumentSchemaError

#: ADR 0078 D2.3: `detail.code` of `head` given as a branch name (`invalid_request`).
BRANCH_NAME_RESERVED: Final = "branch_name_reserved"
#: ADR 0078 D2.4: `detail.code` of a branch with no `refs` row (`not_found`).
BRANCH_NOT_FOUND: Final = "branch_not_found"


def ref_name(branch: str | None) -> str:
    """ADR 0078 D2.1: the `refs` row a ChangeSet's `branch` names: `head` for none (or
    `"head"`), else `branches/<branch>`."""
    return HEAD if branch is None or branch == HEAD_REF else BRANCH_PREFIX + branch


class BranchService:
    """The branch operations over one caller's `ServiceCore`. Each public method is the
    `LocalApplication` method of the same name, documented there; it takes every argument
    explicitly (the defaults are the facade's)."""

    def __init__(self, core: ServiceCore) -> None:
        self._core = core

    def list_branches(self, *, cursor: str | None, limit: int) -> Page[Branch]:
        operation = "list_branches"
        self._checked(operation, {"cursor": cursor, "limit": limit})
        self._core.authorize(operation)
        after = self._decode_cursor(cursor, operation)
        store = self._core.store
        items: list[Branch] = []
        with store.reading() as connection:
            head = store.head(connection) if after is None else None
            if head is not None:
                items.append(Branch(HEAD_REF, head))
            branch_after = None if after in (None, HEAD_REF) else after
            rows = store.branch_rows(connection, branch_after, limit + 1 - len(items))
        items.extend(Branch(name, tip) for name, tip in rows)
        more = len(items) > limit
        items = items[:limit]
        return Page(items=tuple(items), next_cursor=encode_cursor(items[-1].name) if more else None)

    def create_branch(self, *, name: str, revision_id: str, idempotency_key: str) -> BranchResult:
        operation = "create_branch"
        request = {"name": name, "revision_id": revision_id, "idempotency_key": idempotency_key}
        self._checked(operation, request)
        caller = self._core.authorize(operation)
        self._unreserved(operation, name)
        request_sha256 = document_sha256(request)
        store = self._core.store
        ref = BRANCH_PREFIX + name
        result: BranchResult | None = None
        prior: LedgerRow | None = None
        known = True
        with store.writing() as connection:
            prior = store.ledger_lookup(connection, caller.principal_id, operation, idempotency_key)
            tip = store.ref(connection, ref)
            known = store.get_revision(connection, revision_id) is not None
            if prior is None and tip is not None:
                result = BranchResult("conflict", name, tip, {"expected": None, "actual": tip})
            elif prior is None and known:
                store.set_ref(connection, ref, revision_id)
                result = BranchResult("created", name, revision_id)
                self._record(connection, caller, operation, idempotency_key, request_sha256, result)
        if prior is not None:
            return self._replayed(operation, prior, request_sha256)
        if result is None:
            self._core.refuse(
                "not_found",
                "no such revision",
                operation=operation,
                pointer="/revision_id",
                revision_id=revision_id,
            )
        return result

    def delete_branch(
        self, *, name: str, expected_revision: str, idempotency_key: str
    ) -> BranchResult:
        operation = "delete_branch"
        request = {
            "name": name,
            "expected_revision": expected_revision,
            "idempotency_key": idempotency_key,
        }
        self._checked(operation, request)
        caller = self._core.authorize(operation)
        self._unreserved(operation, name)
        request_sha256 = document_sha256(request)
        store = self._core.store
        ref = BRANCH_PREFIX + name
        result: BranchResult | None = None
        prior: LedgerRow | None = None
        with store.writing() as connection:
            prior = store.ledger_lookup(connection, caller.principal_id, operation, idempotency_key)
            tip = store.ref(connection, ref)
            if prior is None and tip is not None and tip != expected_revision:
                result = BranchResult(
                    "conflict", name, tip, {"expected": expected_revision, "actual": tip}
                )
            elif prior is None and tip is not None:
                store.delete_ref(connection, ref)
                result = BranchResult("deleted", name, None)
                self._record(connection, caller, operation, idempotency_key, request_sha256, result)
        if prior is not None:
            return self._replayed(operation, prior, request_sha256)
        if result is None:
            self._core.refuse(
                "not_found",
                f"{BRANCH_NOT_FOUND}: no branch {name!r} in this project",
                operation=operation,
                pointer="/name",
                code=BRANCH_NOT_FOUND,
                name=name,
            )
        return result

    # ------------------------------------------------------------------------------ helpers

    def _checked(self, name: str, request: Mapping[str, Any]) -> None:
        """`dispatch`'s steps 1 and 2 for a Python caller: the canonical form, then the request
        schema, over the members given (an argument left at its default is not a member); a
        refusal is audited and raised."""
        present = {key: value for key, value in request.items() if value is not None}
        at = first_noncanonical(present)
        if at is not None:
            self._core.refuse(
                "document_not_canonical",
                "a value has no canonical JSON form",
                operation=name,
                pointer=at,
            )
        try:
            validate_inline(name, OPERATIONS[name].request_schema, present)
        except DocumentSchemaError as error:
            self._core.refuse(
                "invalid_request", error.message, operation=name, pointer=error.pointer
            )

    def _unreserved(self, operation: str, name: str) -> None:
        """D2.3: `head` names the main line and is never a branch's name."""
        if name == HEAD_REF:
            self._core.refuse(
                "invalid_request",
                f"{BRANCH_NAME_RESERVED}: {HEAD_REF!r} names the main line, not a branch",
                operation=operation,
                pointer="/name",
                code=BRANCH_NAME_RESERVED,
                name=name,
            )

    def _decode_cursor(self, cursor: str | None, operation: str) -> str | None:
        """The name of the last item the previous page returned, or `None` for the first page."""
        if cursor is None:
            return None
        try:
            decoded = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        except (ValueError, TypeError, binascii.Error):
            decoded = None
        after = decoded.get("after") if isinstance(decoded, dict) else None
        if not isinstance(decoded, dict) or set(decoded) != {"after"} or not isinstance(after, str):
            self._core.refuse(
                "invalid_request",
                "cursor is not one this list issued",
                operation=operation,
                pointer="/cursor",
            )
        return after

    def _record(
        self,
        connection: sqlite3.Connection,
        caller: CapabilityReference,
        operation: str,
        idempotency_key: str,
        request_sha256: str,
        result: BranchResult,
    ) -> None:
        """The ledger row and the `allowed` audit row of a write, in its transaction."""
        store = self._core.store
        store.ledger_insert(
            connection,
            caller.principal_id,
            operation,
            idempotency_key,
            request_sha256,
            result.as_document(),
        )
        verb = "created" if result.status == "created" else "deleted"
        store.audit(
            connection,
            AuditEntry(
                principal_id=caller.principal_id,
                capability_id=caller.capability_id,
                operation=operation,
                outcome="allowed",
                request_sha256=request_sha256,
                effect=f"branch:{result.name}:{verb}",
            ),
        )

    def _replayed(self, operation: str, prior: LedgerRow, request_sha256: str) -> BranchResult:
        """ADR 0019 D3: the original result, `replayed`; another request under the key is
        refused."""
        if prior.request_sha256 != request_sha256:
            self._refuse_reused(operation, prior, request_sha256)
        original = BranchResult._build(prior.result)
        return BranchResult("replayed", original.name, original.revision_id, original.conflict)

    def _refuse_reused(self, operation: str, prior: LedgerRow, request_sha256: str) -> NoReturn:
        self._core.refuse(
            "idempotency_key_reused",
            "this idempotency key was used with a different request; use a new key for a new "
            "request",
            operation=operation,
            request_sha256=request_sha256,
            original_request_sha256=prior.request_sha256,
        )


def encode_cursor(name: str) -> str:
    """§11.4: a branch list's cursor, `base64url(canonical_json({"after": name}))` unpadded,
    `name` that of the last item returned (`head` before the first branch)."""
    return base64.urlsafe_b64encode(canonical_json({"after": name})).decode("ascii").rstrip("=")
