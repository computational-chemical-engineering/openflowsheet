"""Local transactions: expected revision, idempotency key, semantic diff. K06, blueprint §11.

§11's sentence: "Transactions accept an expected revision and idempotency key. They return
validation, semantic diff, and downstream invalidations. Draft edits can be grouped
atomically. … Retrying an idempotent request cannot duplicate an expensive experiment."

Three properties, and each is a specific failure it prevents.

**Optimistic concurrency.** A caller states the revision it read. If the store has moved, the
commit is refused with both ids, so the caller can diff rather than guess. The alternative —
last write wins — silently discards whatever the other agent did, which in a system where
agents edit concurrently is a lost experiment rather than a lost keystroke.

**Idempotency.** A retried request returns the *original* result, not a second one. The point
is not tidiness: a solve is expensive, and a client that times out and retries must not pay
twice or, worse, get two different answers it cannot choose between. Since T07 (ADR 0019 D3) the
key is scoped to `(principal, operation, key)` and checked against the request's hash: the same
key with a *different* request is refused `idempotency_key_reused` rather than silently handed
the old answer, which is what K06's key-only lookup did.

**Atomic grouping.** A `ChangeSet` applies whole or not at all, so a draft is never left half
edited by a failure in the middle.

**T07.** The transaction core — `apply_edits` and `semantic_diff` in `revision_edits` (S17 R2,
re-exported here), persistence and the ledger in `LocalApplication.commit_change` — is shared:
K06's `Application` below is a thin façade over an in-memory `LocalApplication`, and `Edit`,
`ChangeSet`, `SemanticDiff` and `TransactionResult` are the contract's own types, re-exported
from here.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from openflowsheet.application.revision_edits import ELEMENT_MEMBERS as ELEMENT_MEMBERS
from openflowsheet.application.revision_edits import EditPathError as EditPathError
from openflowsheet.application.revision_edits import apply_edits as apply_edits
from openflowsheet.application.revision_edits import element_diff as element_diff
from openflowsheet.application.revision_edits import json_pointer as json_pointer
from openflowsheet.application.revision_edits import revision_diff as revision_diff
from openflowsheet.application.revision_edits import semantic_diff as semantic_diff
from openflowsheet.application.revisions import (
    Revision,
    RevisionError,
)
from openflowsheet.application.store import AuditEntry
from openflowsheet.application.types import (
    ChangeSet,
    DiffElement,
    Edit,
    EditOperation,
    SemanticDiff,
    TransactionResult,
)

if TYPE_CHECKING:
    from openflowsheet.application.local import LocalApplication

#: K06's name for an edit's operation, now the contract's `set | remove | append`.
Operation = EditOperation

__all__ = [
    "ELEMENT_MEMBERS",
    "Application",
    "ChangeSet",
    "DiffElement",
    "Edit",
    "EditPathError",
    "Operation",
    "RevisionStoreView",
    "SemanticDiff",
    "TransactionResult",
    "apply_edits",
    "element_diff",
    "json_pointer",
    "revision_diff",
    "semantic_diff",
]


# ================================================================ K06's façade over the core


class RevisionStoreView:
    """K06's `RevisionStore` surface — `head`, `get`, `history`, `put` — over a project store."""

    def __init__(self, application: LocalApplication) -> None:
        self._application = application

    @property
    def head(self) -> str | None:
        store = self._application.store
        with store.reading() as connection:
            return store.head(connection)

    def get(self, revision_id: str) -> Revision:
        store = self._application.store
        with store.reading() as connection:
            revision = store.get_revision(connection, revision_id)
        if revision is None:
            raise RevisionError(f"no revision {revision_id!r}")
        return revision

    def history(self) -> tuple[str, ...]:
        store = self._application.store
        with store.reading() as connection:
            return store.revision_ids(connection)

    def put(self, revision: Revision) -> Revision:
        """Store a revision and move the head to it; an identical re-put is a no-op.

        Immutability is enforced rather than assumed: a *different* document under an existing
        id raises, because silently accepting it would make every hash that cites it a lie.
        """
        application = self._application
        store = application.store
        with store.writing() as connection:
            existing = store.get_revision(connection, revision.revision_id)
            if existing is not None:
                if existing.content_hash != revision.content_hash:
                    raise RevisionError(
                        f"revision {revision.revision_id!r} already exists with different "
                        f"content ({existing.content_hash[:12]} against "
                        f"{revision.content_hash[:12]}); a revision is immutable and a change is "
                        "a new revision"
                    )
                return existing
            store.commit_revision(
                connection,
                revision,
                principal_id=application.principal_id,
                capability_id=application.capability_id,
                policy_sha256=application.policy.policy_sha256,
            )
            store.audit(
                connection,
                AuditEntry(
                    principal_id=application.principal_id,
                    capability_id=application.capability_id,
                    operation="put_revision",
                    outcome="allowed",
                    effect=f"revision:{revision.revision_id}",
                ),
            )
        return revision


class Application:
    """K06's local contract: a façade over `LocalApplication`'s transaction core (ADR 0019 D1).

    Blueprint D15: no mandatory network round trip for local scientific use, and the local and
    remote clients share a contract rather than growing two. It runs as the local owner on an
    in-memory project unless given one. The one behaviour change from K06 is ADR 0019 D3: a key
    reused with a different change set raises `ApplicationError(idempotency_key_reused)`.
    """

    def __init__(self, application: LocalApplication | None = None) -> None:
        from openflowsheet.application.local import LocalApplication

        self.application = application if application is not None else LocalApplication.in_memory()
        self.store = RevisionStoreView(self.application)
        #: Runs recorded by the caller, outside the contract's jobs, against a revision. Their
        #: ids join the contract's own `run-<job_id>` invalidations.
        self._runs: dict[str, str] = {}

    def record_run(self, run_id: str, revision_id: str) -> None:
        self._runs[run_id] = revision_id

    def commit(self, change_set: ChangeSet) -> TransactionResult:
        """Apply a change set atomically, or refuse and say what moved."""
        result = self.application.commit_change(
            change_set.change, change_set.expected_revision, change_set.idempotency_key
        )
        recorded = {
            run_id
            for run_id, revision_id in self._runs.items()
            if revision_id == change_set.expected_revision
        }
        if result.status in ("committed", "replayed") and recorded:
            result = replace(
                result, invalidations=tuple(sorted(set(result.invalidations) | recorded))
            )
        return result
