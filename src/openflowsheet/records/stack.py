"""The store stack (ADR 0061 D8): reads through `[project store, legacy store]`, writes to the
project store.

A record already in the project store is not written again (the write protocol keeps an existing
object). A legacy record the project registers, or that a data lock built for it names (F3-WO4),
is copied into the project store (`adopt`), so the project keeps it however the package is
installed. A SHA no layer holds is `data_unavailable(<sha>)`.

The **legacy store** is read-only and virtual: on first access it stores, in memory, the records
its loader gives (F3-WO3's import of the profiled files available as package data or in a source
checkout, with its drift check against the committed legacy index). A file that is not available
contributes no records.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from openflowsheet.records.model import RecordOutcome
from openflowsheet.records.store import RecordStore, RecordStoreError, Registration
from openflowsheet.registry.tokens import Coded

#: What a legacy loader returns: the normalised identity projections of the available records.
LegacyLoader = Callable[[], Iterable[Mapping[str, Any]]]


def unavailable(sha: str) -> Coded:
    """Q9.R7's `data_unavailable(<sha>)`: no store of the stack holds the record."""
    return Coded("data_unavailable", {"sha": sha})


class LegacyStore:
    """D8's read-only virtual legacy store: an in-memory store filled from `loader` at its
    first access (the loader runs once)."""

    def __init__(self, loader: LegacyLoader) -> None:
        self._loader = loader
        self._store: RecordStore | None = None
        self._lock = threading.Lock()

    def store(self) -> RecordStore:
        """The filled in-memory store (filled at the first call)."""
        with self._lock:
            if self._store is None:
                store = RecordStore.in_memory()
                for record in self._loader():
                    store.add(record)
                self._store = store
            return self._store


class StoreStack:
    """D8's stack over a project store and, when given, the legacy store. It is the `KeyIndex`
    resolution (`records.resolve`) reads."""

    def __init__(self, project: RecordStore, legacy: LegacyStore | None = None) -> None:
        self.project = project
        self.legacy = legacy

    def layers(self) -> tuple[RecordStore, ...]:
        """The stores in read order: the project store, then the legacy store."""
        return (self.project,) if self.legacy is None else (self.project, self.legacy.store())

    def object_bytes(self, sha: str) -> bytes:
        """The verified bytes of record `sha` from the first layer holding it. Raises
        `data_unavailable(<sha>)` when none does, `store_object_corrupt` from a corrupt file."""
        for layer in self.layers():
            data = layer.object_bytes(sha)
            if data is not None:
                return data
        raise RecordStoreError(unavailable(sha))

    def record(self, sha: str) -> Mapping[str, Any]:
        """The identity projection of record `sha` from the first layer holding it. Raises as
        `object_bytes` does."""
        for layer in self.layers():
            found = layer.record(sha)
            if found is not None:
                return found
        raise RecordStoreError(unavailable(sha))

    def shas_for(
        self, scheme: str, value: str, *, record_type: str | None = None
    ) -> frozenset[str]:
        """The SHAs, over every layer, of the records (of `record_type`, when given) holding D9
        key `scheme:value`."""
        found: frozenset[str] = frozenset()
        for layer in self.layers():
            found |= layer.shas_for(scheme, value, record_type=record_type)
        return found

    def register(
        self, outcome: RecordOutcome, *, principal: str, at: str | None = None
    ) -> Registration:
        """Register an identified record in the project store (`RecordStore.register`); a legacy
        record registered so is thereby copied into it."""
        return self.project.register(outcome, principal=principal, at=at)

    def adopt(self, sha: str) -> bool:
        """Copy record `sha` into the project store from the first lower layer holding it (D8:
        a data lock names it); returns whether this call wrote the object. A record the
        project store holds already is not written again. Raises `data_unavailable(<sha>)` when
        no layer holds it."""
        if self.project.object_bytes(sha) is not None:
            return False
        record = self.record(sha)
        return self.project.add(record, expected=sha)[1]
