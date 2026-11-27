"""The v2 replay bundle: a v2-compiled run's archive. ADR 0067 D3, D4 (F8-WO2).

DRAFT until ADR 0067 is Accepted. `run/bundle.py` is untouched (D3): a v1-path run, lowered v2
documents included (D1, ADR 0062 D8), writes its bundle there exactly as before. In 0.6 nothing in
`src/` writes a v2 bundle; v2-compiled runs come with F6 (F8-WO6), and the only writer is F8-WO2's
test-only factory (`tests/f8_bundle_v2_support.py`).

D3's layout, beside the v1 artifacts:

    artifacts/data-lock.json            the run's data lock; its SHA is `data_lock_sha256`
    artifacts/registry-snapshot.json    ADR 0060 D10's snapshot; its SHA is
                                        `environment.registry.snapshot_sha256`
    artifacts/records-index.json        one entry per record SHA the lock names, sorted by SHA
    artifacts/records/<sha>.json        each embedded record, the store's canonical bytes

`run-evidence.json` (D6) is F8-WO4's and is not written here; the decision records and the
trajectory (D8) are TX's.

**D4, rights-aware embedding.** For every record SHA the lock names, each source's effective
assessment (ADR 0061 D11, `records.rights.effective`) is read from the project register and the
repository register as they stand when the bundle is written. The record is embedded iff every
one is `permitted`, otherwise referenced by SHA only; the index keeps the assessments and
conditions for audit. Rights enter no hash: the index is an artifact, outside `structural_sha256`
(the `artifacts` map is `NON_STRUCTURAL`) and outside the R0 projection (`run.identity`), and the
lock never carries them. Nothing here opens a network connection.

**Integrity.** As in v1, the manifest's `artifacts` index is built from the bytes written and
covers every file under `artifacts/`, records included, so `verify_bundle` re-hashes them all.
It adds what a rebuilt index cannot hide: `data-lock.json` and `registry-snapshot.json` must
hash to the manifest's values, the index must name exactly the lock's records, and the record
files must be exactly the embedded ones, each hashing to its own name.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, Final

from openflowsheet.canonical import canonical_json, document_sha256, file_sha256
from openflowsheet.records.lock import data_lock_sha256
from openflowsheet.records.rights import embeddable, record_rights, record_sources
from openflowsheet.records.stack import StoreStack

# The v1 cross-checks of a revision bundle's solution state and solve path apply unchanged to the
# v1 artifacts a v2 bundle carries; D3 leaves `run/bundle.py` untouched, so they are reused here.
from openflowsheet.run.bundle import (
    ARTIFACT_DIR,
    MANIFEST_NAME,
    BundleError,
    BundleIntegrity,
    _cross_check_solution_state,
    _cross_check_solve_path,
)
from openflowsheet.run.manifest_v2 import RunManifestV2

#: D3's file names (the same as `application.jobs.model.ARTIFACT_FILE_NAMES` gives their kinds).
DATA_LOCK_NAME: Final = "data-lock.json"
REGISTRY_SNAPSHOT_NAME: Final = "registry-snapshot.json"
RECORDS_INDEX_NAME: Final = "records-index.json"
#: D3: the directory under `artifacts/` holding the embedded records, one `<sha>.json` each.
RECORDS_DIR: Final = "records"
#: The names the writer owns; a caller's artifact may not take one.
V2_NAMES: Final = frozenset({DATA_LOCK_NAME, REGISTRY_SNAPSHOT_NAME, RECORDS_INDEX_NAME})


def record_name(sha: str) -> str:
    """The artifact name of embedded record `sha`: `records/<sha>.json`."""
    return f"{RECORDS_DIR}/{sha}.json"


def locked_records(lock: Mapping[str, Any]) -> tuple[str, ...]:
    """D4: every record SHA the lock names (`components[].record`, `parameter_sets`), sorted,
    each once."""
    shas = {item["record"] for item in lock["components"]} | set(lock["parameter_sets"])
    return tuple(sorted(shas))


def records_index(
    lock: Mapping[str, Any],
    stack: StoreStack,
    *,
    repository: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """D3's `records-index.json` of `lock`: per record SHA (sorted), whether it is embedded (D4:
    every source's effective assessment `permitted`) and each source's (id, SHA, assessment,
    conditions), sorted by source id. The project register is `stack.project`'s rights table;
    `repository` defaults to the package's register (`records.rights.repository_rows`). Raises
    `RecordStoreError` (`data_unavailable(<sha>)`) for a record no layer holds."""
    project = stack.project.rights_rows()
    entries = []
    for sha in locked_records(lock):
        record = stack.record(sha)
        rights = record_rights(record, sha, project=project, repository=repository)
        shas = record_sources(record)
        sources = [
            {
                "source_id": ident,
                "source_sha256": shas[ident],
                "assessment": item.assessment,
                "conditions": item.conditions,
            }
            for ident, item in sorted(rights.items())
        ]
        entries.append({"sha256": sha, "embedded": embeddable(rights), "sources": sources})
    return {"records": entries}


def write_bundle(
    directory: Path,
    manifest: RunManifestV2,
    artifacts: Mapping[str, Any],
    *,
    lock: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    stack: StoreStack,
    repository: Sequence[Mapping[str, Any]] | None = None,
) -> RunManifestV2:
    """Write D3's bundle of a v2-compiled run and return the manifest with its `artifacts` index
    filled in from the bytes written.

    `artifacts` are the run's v1 artifact documents (written as canonical JSON, as in v1);
    `lock` is its data lock and `snapshot` the registry snapshot it ran under. The manifest's
    `data_lock_sha256` and `environment.registry` must be those documents' SHAs: they are the
    run's, so a mismatch is refused (`BundleError`), never overwritten. Each record the lock names
    is embedded or referenced by D4 (`records_index`), embedded ones as `stack`'s stored bytes."""
    directory = Path(directory)
    clashes = sorted(
        name for name in artifacts if name in V2_NAMES or name.startswith(f"{RECORDS_DIR}/")
    )
    if clashes:
        raise BundleError(f"artifacts {clashes} take names D3 reserves for the v2 writer")
    if manifest.data_lock_sha256 != data_lock_sha256(lock):
        raise BundleError("the manifest's data_lock_sha256 is not the lock's SHA")
    if manifest.environment_registry.snapshot_sha256 != document_sha256(snapshot):
        raise BundleError(
            "the manifest's environment.registry.snapshot_sha256 is not the snapshot's"
        )
    if manifest.environment_registry.registry_sha256 != snapshot["registry_sha256"]:
        raise BundleError(
            "the manifest's environment.registry.registry_sha256 is not the snapshot's"
        )

    index = records_index(lock, stack, repository=repository)
    documents = {
        **artifacts,
        DATA_LOCK_NAME: lock,
        REGISTRY_SNAPSHOT_NAME: snapshot,
        RECORDS_INDEX_NAME: index,
    }
    payloads = {name: canonical_json(document) for name, document in documents.items()}
    for entry in index["records"]:
        if entry["embedded"]:
            payloads[record_name(entry["sha256"])] = stack.object_bytes(entry["sha256"])

    root = directory / ARTIFACT_DIR
    root.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    for name, data in sorted(payloads.items()):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        hashes[name] = file_sha256(path)

    complete = replace(manifest, artifacts=hashes)
    (directory / MANIFEST_NAME).write_bytes(canonical_json(complete.as_document()))
    return complete


def read_manifest(directory: Path) -> tuple[RunManifestV2, dict[str, Any]]:
    """A v2 bundle's manifest, typed and raw (as `run.bundle.read_manifest` returns a v1 one).
    Raises `BundleError` when there is none, when it is not a v2 manifest, or when it carries a
    member the typed manifest does not reproduce."""
    path = Path(directory) / MANIFEST_NAME
    if not path.is_file():
        raise BundleError(f"no {MANIFEST_NAME} in {directory}")
    document = json.loads(path.read_text(encoding="utf-8"))
    try:
        manifest = RunManifestV2.from_document(document)
    except (KeyError, TypeError, ValueError) as error:
        raise BundleError(f"{MANIFEST_NAME} is not a readable v2 manifest: {error}") from error
    unknown = sorted(set(document) - set(manifest.as_document()))
    if unknown:
        raise BundleError(
            f"{MANIFEST_NAME} carries fields this reader does not know: {unknown}. A manifest "
            "it cannot fully reconstruct is one it cannot check."
        )
    return manifest, document


def verify_bundle(directory: Path) -> BundleIntegrity:
    """Re-hash every artifact against the index (records included), run the v1 cross-checks and
    D3's own, and check the manifest against itself."""
    directory = Path(directory)
    manifest, document = read_manifest(directory)
    root = directory / ARTIFACT_DIR

    missing: list[str] = []
    tampered: list[str] = []
    for name, recorded in sorted(manifest.artifacts.items()):
        path = root / name
        if not path.is_file():
            missing.append(name)
        elif file_sha256(path) != recorded:
            tampered.append(name)
    present = {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()}
    unexpected = sorted(present - set(manifest.artifacts))

    _cross_check_solution_state(directory, manifest.artifacts, missing, tampered)
    _cross_check_solve_path(directory, manifest, missing, tampered)
    _cross_check_v2(root, manifest, missing, tampered)

    if document.get("manifest_sha256") != manifest.manifest_sha256:
        tampered.append(MANIFEST_NAME)
    elif document.get("structural_sha256") != manifest.structural_sha256:
        tampered.append(MANIFEST_NAME)

    return BundleIntegrity(
        ok=not (missing or tampered or unexpected),
        missing=tuple(sorted(set(missing))),
        tampered=tuple(sorted(set(tampered))),
        unexpected=tuple(unexpected),
    )


def _cross_check_v2(
    root: Path, manifest: RunManifestV2, missing: list[str], tampered: list[str]
) -> None:
    """D3: the lock and the snapshot hash to the manifest's values; the records index names
    exactly the lock's records; the record files are exactly the embedded ones, each hashing to
    its own SHA. A file the index omits is reported missing here, since a forger who drops a file
    drops its index entry with it."""
    expected = {
        DATA_LOCK_NAME: manifest.data_lock_sha256,
        REGISTRY_SNAPSHOT_NAME: manifest.environment_registry.snapshot_sha256,
    }
    for name, sha in expected.items():
        path = root / name
        if name not in manifest.artifacts or not path.is_file():
            missing.append(name)
        elif file_sha256(path) != sha:
            tampered.append(name)

    index_path = root / RECORDS_INDEX_NAME
    lock_path = root / DATA_LOCK_NAME
    if RECORDS_INDEX_NAME not in manifest.artifacts or not index_path.is_file():
        missing.append(RECORDS_INDEX_NAME)
        return
    if not lock_path.is_file():
        return
    index = json.loads(index_path.read_text(encoding="utf-8"))
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    entries = index.get("records", [])
    if [entry["sha256"] for entry in entries] != list(locked_records(lock)):
        tampered.append(RECORDS_INDEX_NAME)
    embedded = {record_name(entry["sha256"]) for entry in entries if entry["embedded"]}
    stored = {name for name in manifest.artifacts if name.startswith(f"{RECORDS_DIR}/")}
    if stored - embedded:
        tampered.append(RECORDS_INDEX_NAME)
    for name in sorted(embedded):
        path = root / name
        if name not in manifest.artifacts or not path.is_file():
            missing.append(name)
        elif file_sha256(path) != name.removeprefix(f"{RECORDS_DIR}/").removesuffix(".json"):
            tampered.append(name)
