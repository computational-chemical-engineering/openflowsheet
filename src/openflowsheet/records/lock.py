"""The data lock (ADR 0061 D10; `schemas/data-lock.schema.json`), F3-WO4.

```
{ "lock_format": "openflowsheet-data-lock-v1",
  "components":     [{"id", "record"}…],     # revision order, ids unique
  "parameter_sets": [<sha256>…],             # ascending, unique
  "methods":        [{"substream", "method", "version", "implementation_sha256"}…],
                                             # sorted by (substream, method, version key)
  "method_options": {<method id>: {…}} }     # keys ⊆ the methods' ids
data_lock_sha256 = document_sha256(lock)
```

The lock is derived, never stored in a revision: from the revision's record SHAs and method ids
and versions, and the F1 registry (`implementation_sha256` of a method descriptor, ADR 0060 D3).
`build_lock` normalises the order, checks that each SHA resolves in the store stack
(`data_unavailable(<sha>)`), copies each named record into the project store (D8) and checks D5's
parameter-set matching (`parameter_set_component_missing(<set>, <key>)`). Rights never enter it
(Q9.A2). The per-provider narrowed lock (`data_sha256`, ADR 0063 D2) is F4's.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from typing import Any, Final

from openflowsheet.canonical import canonical_json, document_sha256
from openflowsheet.records.stack import StoreStack
from openflowsheet.records.store import RecordStoreError
from openflowsheet.registry.descriptor import Registered, version_key
from openflowsheet.registry.tokens import Coded

#: D10: the lock's format id.
LOCK_FORMAT: Final = "openflowsheet-data-lock-v1"
#: D10: a `methods` row's members.
METHOD_FIELDS: Final = ("substream", "method", "version", "implementation_sha256")


class DataLockError(ValueError):
    """A lock `build_lock` refuses: `coded` is `data_unavailable(<sha>)` or
    `parameter_set_component_missing(<set>, <key>)`, or `None` for inputs off D10's shape (a
    caller's bug: duplicate component ids or methods, an option for an unlocked method, a SHA
    naming a record of the wrong type)."""

    def __init__(self, coded: Coded | None, message: str = "") -> None:
        super().__init__(message or (coded.code if coded is not None else "data lock error"))
        self.coded = coded


def implementation_sha256(descriptor: Registered) -> str:
    """D10, ADR 0060 D3: `sha256(canonical_json([descriptor_sha256, self_sha256]))` of a
    registered method descriptor."""
    preimage = canonical_json([descriptor.descriptor_sha256, descriptor.self_sha256])
    return hashlib.sha256(preimage).hexdigest()


def method_entry(substream: str, descriptor: Registered) -> dict[str, str]:
    """D10's `methods` row of the registered method `descriptor` bound on `substream`."""
    return {
        "substream": substream,
        "method": descriptor.id,
        "version": descriptor.version,
        "implementation_sha256": implementation_sha256(descriptor),
    }


def data_lock_sha256(lock: Mapping[str, Any]) -> str:
    """D10: `document_sha256(lock)`."""
    return document_sha256(lock)


def build_lock(
    components: Iterable[tuple[str, str]],
    parameter_sets: Iterable[str],
    methods: Iterable[Mapping[str, str]],
    method_options: Mapping[str, Mapping[str, Any]],
    stack: StoreStack,
) -> dict[str, Any]:
    """D10's lock of the revision's (component id, record SHA) pairs in revision order, its
    parameter-set SHAs, its `methods` rows (`method_entry`) and its options by method id.

    The order is normalised (`parameter_sets` ascending and unique, `methods` sorted by
    (substream, method, version key) in UTF-8 byte order); each SHA must resolve in `stack` to a
    record of its type, and each parameter set's components must match (D5); then each named
    record is copied into the project store (`StoreStack.adopt`, D8). Raises `DataLockError`, coded
    `data_unavailable(<sha>)` or `parameter_set_component_missing(<set id>, <key>)`, and
    `RecordStoreError` (`store_object_corrupt`) from a corrupt stored file."""
    bound = [{"id": ident, "record": sha} for ident, sha in components]
    if len({item["id"] for item in bound}) != len(bound):
        raise DataLockError(None, "component ids are not unique")
    sets = sorted(set(parameter_sets))
    rows = [{name: row[name] for name in METHOD_FIELDS} for row in methods]
    rows.sort(key=_method_key)
    if len({_method_key(row) for row in rows}) != len(rows):
        raise DataLockError(None, "a (substream, method, version) is locked twice")
    unlocked = sorted(set(method_options) - {row["method"] for row in rows})
    if unlocked:
        raise DataLockError(None, f"options for methods not in the lock: {unlocked}")
    records = {item["record"]: _resolved(stack, item["record"], "component") for item in bound}
    for sha in sets:
        _matched(_resolved(stack, sha, "parameter_set"), records)
    for sha in [*records, *sets]:
        stack.adopt(sha)
    return {
        "lock_format": LOCK_FORMAT,
        "components": bound,
        "parameter_sets": sets,
        "methods": rows,
        "method_options": {key: dict(value) for key, value in method_options.items()},
    }


def _method_key(row: Mapping[str, str]) -> tuple[bytes, bytes, tuple[int, int, int]]:
    return (row["substream"].encode(), row["method"].encode(), version_key(row["version"]))


def _resolved(stack: StoreStack, sha: str, record_type: str) -> Mapping[str, Any]:
    """Record `sha` from `stack`, of `record_type`; `data_unavailable(<sha>)` when no layer
    holds it."""
    try:
        record = stack.record(sha)
    except RecordStoreError as error:
        if error.coded is not None and error.coded.code == "data_unavailable":
            raise DataLockError(error.coded) from error
        raise
    if record["record_type"] != record_type:
        raise DataLockError(None, f"{sha} is a {record['record_type']}, not a {record_type}")
    return record


def _matched(parameter_set: Mapping[str, Any], bound: Mapping[str, Mapping[str, Any]]) -> None:
    """D5: each of the set's components matches a bound record, by its SHA (`match.record`) or
    by an InChIKey the record carries (`match.inchikey`)."""
    keys = {record.get("identifiers", {}).get("inchikey") for record in bound.values()}
    for component in parameter_set.get("components", ()):
        match = component["match"]
        if match.get("record") in bound or match.get("inchikey") in keys - {None}:
            continue
        coded = Coded(
            "parameter_set_component_missing",
            {"set": parameter_set["id"], "key": component["key"]},
        )
        raise DataLockError(coded)
