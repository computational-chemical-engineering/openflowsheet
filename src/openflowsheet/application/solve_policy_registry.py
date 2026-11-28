"""A project's registered solve policies in its store (ADR 0078 D4.4, D4.6, X06).

A registered policy is a job-less artifact row (as ADR 0035 D3's `model_replacement_report`):
`artifact_id = "solve-policy:" + policy_id`, `job_id NULL`, `kind = "solve_policy"`,
`name = policy_id + ".json"`, `sha256` the policy's `policy_sha256`, and the canonical bytes in
`solve-policies/<sha256>.json` (named by hash, so ids that differ only in case never collide on
a case-insensitive file system). The file is written first, then the row, in the caller's write
transaction; an id is never re-bound. No table or store schema changes.

`load` is the one reader admission and the job runner resolve project policies through; it
verifies each file against its row, and a mismatch raises `SolvePolicyStoreError`
(`internal_error` at admission, the ending reason `store_error` in the runner).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Final

from openflowsheet.application.store import ProjectStore, atomic_write_bytes
from openflowsheet.application.store_records import ArtifactRow
from openflowsheet.numerics.solve_record import SolvePolicy

#: D4.4: the artifact kind of a registered policy (a job's `solve-policy.json` member shares it;
#: a registered policy is the row without a job under `ARTIFACT_PREFIX`).
KIND: Final = "solve_policy"
#: D4.4: a registered policy's artifact id is this prefix and its `policy_id`.
ARTIFACT_PREFIX: Final = "solve-policy:"
#: D4.4: the directory under the project's files root that holds the policy files.
POLICY_DIR: Final = "solve-policies"


class SolvePolicyStoreError(Exception):
    """A registered policy whose file is missing or does not hash to its row."""

    def __init__(self, policy_id: str, reason: str) -> None:
        super().__init__(f"registered solve policy {policy_id!r}: {reason}")
        self.policy_id = policy_id


def artifact_id(policy_id: str) -> str:
    return ARTIFACT_PREFIX + policy_id


def registered_rows(store: ProjectStore) -> list[ArtifactRow]:
    """The registered policies' rows, by id in bytewise ascending order."""
    rows = [
        row
        for row in store.artifacts_of_kind(KIND)
        if row.job_id is None and row.artifact_id.startswith(ARTIFACT_PREFIX)
    ]
    return sorted(rows, key=lambda row: row.artifact_id.encode())


def read_bytes(row: ArtifactRow, files_root: Path) -> bytes:
    """A registered policy's canonical bytes, checked against its row."""
    policy_id = row.artifact_id.removeprefix(ARTIFACT_PREFIX)
    try:
        data = (files_root / row.relpath).read_bytes()
    except OSError as error:
        raise SolvePolicyStoreError(policy_id, f"its file is unreadable ({error})") from error
    if hashlib.sha256(data).hexdigest() != row.sha256:
        raise SolvePolicyStoreError(policy_id, "its file does not hash to its row")
    return data


def load(store: ProjectStore, files_root: Path) -> dict[str, SolvePolicy]:
    """D4.6: every registered policy of the project by id, each file verified against its row.
    Raised: `SolvePolicyStoreError`."""
    loaded: dict[str, SolvePolicy] = {}
    for row in registered_rows(store):
        policy_id = row.artifact_id.removeprefix(ARTIFACT_PREFIX)
        try:
            policy = SolvePolicy.from_document(json.loads(read_bytes(row, files_root)))
        except (KeyError, TypeError, ValueError) as error:
            raise SolvePolicyStoreError(policy_id, f"its file is not a policy ({error})") from error
        if policy.policy_id != policy_id:
            raise SolvePolicyStoreError(policy_id, "its file names another policy")
        loaded[policy_id] = policy
    return loaded


def bind(
    connection: sqlite3.Connection, files_root: Path, policy_id: str, data: bytes
) -> ArtifactRow:
    """D4.4: write `data` (a policy's canonical bytes) and bind `policy_id` to it, in the
    caller's write transaction, which has found the id unbound."""
    sha256 = hashlib.sha256(data).hexdigest()
    relpath = f"{POLICY_DIR}/{sha256}.json"
    path = files_root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(path, data)
    row = ArtifactRow(
        artifact_id=artifact_id(policy_id),
        job_id=None,
        kind=KIND,
        name=policy_id + ".json",
        sha256=sha256,
        size_bytes=len(data),
        relpath=relpath,
    )
    ProjectStore.register_artifacts(connection, [row])
    return row
