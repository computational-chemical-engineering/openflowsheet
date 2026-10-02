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

**T07.** The transaction core — `apply_edits` and `semantic_diff` here, persistence and the
ledger in `LocalApplication.commit_change` — is shared: K06's `Application` below is a thin
façade over an in-memory `LocalApplication`, and `Edit`, `ChangeSet`, `SemanticDiff` and
`TransactionResult` are the contract's own types, re-exported from here.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from openflowsheet.application.revisions import (
    CONTENT_HASH_EXCLUDED,
    Revision,
    RevisionError,
)
from openflowsheet.application.store import AuditEntry
from openflowsheet.application.types import (
    ChangeSet,
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
    "Application",
    "ChangeSet",
    "Edit",
    "EditPathError",
    "Operation",
    "RevisionStoreView",
    "SemanticDiff",
    "TransactionResult",
    "apply_edits",
    "json_pointer",
    "semantic_diff",
]


# ==================================================================== the transaction core


class EditPathError(ValueError):
    """§5.2 `edit_path_invalid`: edit `edit_index` cannot be applied at `pointer`."""

    def __init__(self, edit_index: int, pointer: str, reason: str) -> None:
        super().__init__(f"edit {edit_index} at {pointer or '/'}: {reason}")
        self.edit_index = edit_index
        self.pointer = pointer
        self.reason = reason


def json_pointer(path: Sequence[str | int]) -> str:
    """RFC 6901: `/`-joined, `~` as `~0` and `/` as `~1`."""
    return "".join("/" + str(part).replace("~", "~0").replace("/", "~1") for part in path)


def apply_edits(base: Mapping[str, Any], edits: Sequence[Edit]) -> dict[str, Any]:
    """Apply `edits` in order to a copy of `base`; `EditPathError` names the first bad one.

    §5.2: strings index objects and integers index arrays. `set` on an object key creates or
    replaces it, creating missing *object* parents (K06); on an array index the index must
    exist. `append` needs an existing array at its path. `remove` on an object key removes it,
    and an absent key — or an absent parent — is a no-op (K06); on an array index the index must
    exist and later elements shift down. Anything else is refused, never guessed at.

    Applied to a copy: a failure part way through leaves the base untouched, which is what
    "grouped atomically" has to mean for a draft nobody wants half-edited.
    """
    document = copy.deepcopy(dict(base))
    for index, edit in enumerate(edits):
        _apply(document, edit, index)
    return document


def _apply(document: dict[str, Any], edit: Edit, index: int) -> None:
    path = edit.path
    walk = path if edit.operation == "append" else path[:-1]
    node: Any = document
    for depth, key in enumerate(walk):
        here = json_pointer(path[: depth + 1])
        if isinstance(node, dict):
            if not isinstance(key, str):
                raise EditPathError(index, here, "an integer indexes an array; this is an object")
            if key not in node:
                following = path[depth + 1] if depth + 1 < len(path) else None
                if edit.operation == "remove":
                    return  # an absent parent holds no key to remove
                if edit.operation == "set" and isinstance(following, str):
                    node[key] = {}
                else:
                    raise EditPathError(index, here, "no such member")
        elif isinstance(node, list):
            if not isinstance(key, int):
                raise EditPathError(index, here, "a string indexes an object; this is an array")
            if key >= len(node):
                raise EditPathError(index, here, f"index {key} is past the array's {len(node)}")
        else:
            raise EditPathError(index, here, "the path runs through a scalar")
        node = node[key]

    if edit.operation == "append":
        if not isinstance(node, list):
            raise EditPathError(index, json_pointer(path), "append needs an array here")
        node.append(copy.deepcopy(edit.value))
        return

    last = path[-1]
    here = json_pointer(path)
    if isinstance(node, dict):
        if not isinstance(last, str):
            raise EditPathError(index, here, "an integer indexes an array; this is an object")
        if edit.operation == "set":
            node[last] = copy.deepcopy(edit.value)
        else:
            node.pop(last, None)
    elif isinstance(node, list):
        if not isinstance(last, int):
            raise EditPathError(index, here, "a string indexes an object; this is an array")
        if last >= len(node):
            raise EditPathError(index, here, f"index {last} is past the array's {len(node)}")
        if edit.operation == "set":
            node[last] = copy.deepcopy(edit.value)
        else:
            del node[last]
    else:
        raise EditPathError(index, json_pointer(path[:-1]), "the path runs through a scalar")


def semantic_diff(before: Mapping[str, Any], after: Mapping[str, Any]) -> SemanticDiff:
    """Paths added, removed and changed in the revision's content.

    Descriptive fields are excluded on purpose: two revisions differing only in their title are
    the same process, and a diff that said otherwise would make every retitle look like an
    edit to the model.
    """
    added: list[str] = []
    removed: list[str] = []
    changed: list[str] = []

    def walk(left: Any, right: Any, path: str) -> None:
        if isinstance(left, Mapping) and isinstance(right, Mapping):
            for key in sorted(set(left) | set(right)):
                if not path and key in CONTENT_HASH_EXCLUDED:
                    continue
                where = f"{path}.{key}" if path else key
                if key not in left:
                    added.append(where)
                elif key not in right:
                    removed.append(where)
                else:
                    walk(left[key], right[key], where)
        elif left != right:
            changed.append(path)

    walk(before, after, "")
    return SemanticDiff(tuple(added), tuple(removed), tuple(changed))


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
