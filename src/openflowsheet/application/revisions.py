"""Immutable revisions and the store that holds them. K06.

Blueprint §4.4 and D16: a revision is content-addressed and never edited in place. A `DRAFT`
may be incomplete or under-specified and is still committable — "a syntactically valid draft
can be committed without being executable" — because the alternative is that a user cannot save
work in progress, and a tool that refuses to hold an unfinished thought gets worked around.

`content_hash` is computed here and never accepted from a caller. The P01 case files leave it
absent on purpose, with a note saying why: a hash written before ADR 0002's canonical encoding
existed would have been a fabricated identity. The encoding exists now, so this fills it in.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from openflowsheet.canonical import canonical_json

#: ADR 0002 D4: the fields a content hash excludes, because they describe the revision rather
#: than being part of it. Two revisions differing only in their title are the same process.
CONTENT_HASH_EXCLUDED: Final[frozenset[str]] = frozenset(
    {"content_hash", "revision_id", "parent_revision", "title", "description", "provenance"}
)


class RevisionError(RuntimeError):
    """A revision that cannot be stored or retrieved as asked."""


class RevisionConflictError(RevisionError):
    """Optimistic concurrency: the store moved under the caller (blueprint §11).

    The name carries the `Error` suffix the lint rule wants; what a caller sees in a
    transaction result is the word `conflict`, which is the domain's term.

    Carries both revisions so the caller can diff rather than guess what it missed.
    """

    def __init__(self, expected: str | None, actual: str | None) -> None:
        super().__init__(
            f"the transaction expected revision {expected!r} and the store is at {actual!r}; "
            "re-read, re-diff and retry rather than overwriting"
        )
        self.expected = expected
        self.actual = actual


def content_hash(document: Mapping[str, Any]) -> str:
    """ADR 0002 D4's canonical JSON over the semantic content, excluding the description."""
    content = {key: value for key, value in document.items() if key not in CONTENT_HASH_EXCLUDED}
    return hashlib.sha256(canonical_json(content)).hexdigest()


@dataclass(frozen=True)
class Revision:
    """One immutable revision. `content_hash` is derived, never supplied."""

    revision_id: str
    document: Mapping[str, Any]
    parent_revision: str | None = None

    @property
    def content_hash(self) -> str:
        return content_hash(self.document)

    def as_document(self) -> dict[str, Any]:
        return {
            **dict(self.document),
            "revision_id": self.revision_id,
            "parent_revision": self.parent_revision,
            "content_hash": self.content_hash,
        }


@dataclass
class RevisionStore:
    """An append-only store. Nothing is ever replaced; a change is a new revision.

    In memory for v0.0. The contract is what K06 owes a later HTTP binding (blueprint D15),
    so the methods are the ones a transport would expose and nothing else.
    """

    _revisions: dict[str, Revision] = field(default_factory=dict)
    _head: str | None = None
    _order: list[str] = field(default_factory=list)

    @property
    def head(self) -> str | None:
        return self._head

    def get(self, revision_id: str) -> Revision:
        if revision_id not in self._revisions:
            raise RevisionError(f"no revision {revision_id!r}")
        return self._revisions[revision_id]

    def history(self) -> tuple[str, ...]:
        return tuple(self._order)

    def put(self, revision: Revision) -> Revision:
        """Store a revision. Re-storing an identical one is not an error; it is a no-op.

        Immutability is enforced rather than assumed: putting a *different* document under an
        existing id raises, because silently accepting it would make every hash in every
        manifest that cites it a lie.
        """
        existing = self._revisions.get(revision.revision_id)
        if existing is not None:
            if existing.content_hash != revision.content_hash:
                raise RevisionError(
                    f"revision {revision.revision_id!r} already exists with different content "
                    f"({existing.content_hash[:12]} against {revision.content_hash[:12]}); a "
                    "revision is immutable and a change is a new revision"
                )
            return existing
        self._revisions[revision.revision_id] = revision
        self._order.append(revision.revision_id)
        self._head = revision.revision_id
        return revision
