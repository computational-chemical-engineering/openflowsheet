"""V17's store export: `store-export.json` after a session, as `local-owner` (T07 W7c).

Normative text: `docs/derivations/T07-v17-tasks-spec.md` §4.8 (finding F2) and §4.3 (the session
boundary); design note §14.2. The export is a read of the project after the session ended,
through `LocalApplication` opened as `LOCAL_OWNER` (the in-process owner, whom no transport can
present) and its store; the agent produces none of it. Every member is written, whether or not a
measure reads it today:

- `session_start`: `{audit_seq, job_ordinal, revision_ordinal}`, recorded before the session;
- `revisions`: `[{ordinal, revision_id, principal_id, content_sha256, document}]`, the
  document as `get_revision` returns it;
- `refs`: `{"head": …}`;
- `ledger`: the `commit_change` ledger rows' `TransactionResult` documents, in commit order;
- `jobs`: every Job document, in acceptance order; `events`: `{job_id: [JobEvent]}`;
- `run_results`: `{job_id: RunResult}` for every ended solve job, from `get_job_result`;
- `artifacts`: `[{artifact_id, job_id, kind, name, sha256, parent_artifact_id}]`, by id;
- `artifact_documents`: `{artifact_id: document}` for the kinds of `DOCUMENT_KINDS`, bundle
  members and imported bundles' members included (`read_document` reads them);
- `audit`: every audit row, by `seq`;
- `registered_check_tolerances`: `verify.checks.KIND_TOLERANCE`.

The file is canonical JSON (ADR 0002), so two exports of one store are byte-identical.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from openflowsheet.application.local import LocalApplication
from openflowsheet.canonical import CanonicalizationError, canonical_json
from openflowsheet.verify.checks import KIND_TOLERANCE

EXPORT_FILE: Final[str] = "store-export.json"
#: §4.8: the artifact kinds whose documents the oracles and the system counter read.
DOCUMENT_KINDS: Final[frozenset[str]] = frozenset(
    {
        "solution_certificate",
        "failure_bundle",
        "run_manifest",
        "replay_report",
        "solution_state",
        "revision_document",
    }
)
#: §6.3: the statuses a job can end in; `get_job_result` is `not_ready` before.
_ENDED: Final[frozenset[str]] = frozenset({"completed", "failed", "cancelled", "timed_out"})


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document = dict(pairs)
    if len(document) != len(pairs):
        raise CanonicalizationError("a key is repeated in one object (ADR 0002 D3.6)")
    return document


def read_document(data: bytes) -> Any:
    """An artifact file's JSON document, no repeated key. An integer text needs no reader of its
    own: one that spells a binary64 (`592612204108959000` for 5.92612204108959e17) is canonical
    as the `int` the parser gives (ADR 0002 D3.3, Amendment 1)."""
    return json.loads(data, object_pairs_hook=_unique)


def export(project: Path, session_start: dict[str, int]) -> dict[str, Any]:
    """§4.8's export of `project`, read as `LOCAL_OWNER` once the session has ended."""
    with LocalApplication.open(project) as app:
        store = app.store
        with store.reading() as connection:
            head = store.head(connection)
            revision_rows = connection.execute(
                "SELECT ordinal, revision_id, principal_id, content_sha256 FROM revisions"
                " ORDER BY ordinal"
            ).fetchall()
            revisions = []
            for ordinal, revision_id, principal_id, content_sha256 in revision_rows:
                revision = store.get_revision(connection, revision_id)
                assert revision is not None
                revisions.append(
                    {
                        "ordinal": int(ordinal),
                        "revision_id": revision_id,
                        "principal_id": principal_id,
                        "content_sha256": content_sha256,
                        "document": revision.as_document(),
                    }
                )
            ledger = [
                json.loads(row[0])
                for row in connection.execute(
                    "SELECT result FROM ledger WHERE operation = 'commit_change'"
                    " ORDER BY created_at, rowid"
                ).fetchall()
            ]
            artifact_rows = connection.execute(
                "SELECT artifact_id, job_id, kind, name, sha256, parent_artifact_id"
                " FROM artifacts ORDER BY artifact_id"
            ).fetchall()
        jobs = [store.get_job(job_id) for job_id in store.job_ids()]
        run_results: dict[str, Any] = {}
        events: dict[str, Any] = {}
        for job in jobs:
            assert job is not None
            events[job.job_id] = [event.as_document() for event in store.job_events(job.job_id)]
            if job.operation == "solve" and job.status in _ENDED:
                result = app.get_job_result(job.job_id).run_result
                assert result is not None
                run_results[job.job_id] = result.as_document()
        artifacts = [
            {
                "artifact_id": artifact_id,
                "job_id": job_id,
                "kind": kind,
                "name": name,
                "sha256": sha256,
                "parent_artifact_id": parent,
            }
            for artifact_id, job_id, kind, name, sha256, parent in artifact_rows
        ]
        documents = {
            row["artifact_id"]: read_document(app.artifact_bytes(row["artifact_id"]))
            for row in artifacts
            if row["kind"] in DOCUMENT_KINDS
        }
        return {
            "session_start": dict(session_start),
            "revisions": revisions,
            "refs": {"head": head},
            "ledger": ledger,
            "jobs": [job.as_document() for job in jobs if job is not None],
            "events": events,
            "run_results": run_results,
            "artifacts": artifacts,
            "artifact_documents": documents,
            "audit": store.audit_rows(),
            "registered_check_tolerances": dict(KIND_TOLERANCE),
        }


def write(project: Path, session_start: dict[str, int], directory: Path) -> Path:
    """`export` written as canonical JSON to `directory/store-export.json`."""
    path = directory / EXPORT_FILE
    path.write_bytes(canonical_json(export(project, session_start)))
    return path
