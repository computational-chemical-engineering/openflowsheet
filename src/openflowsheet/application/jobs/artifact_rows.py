"""The `artifacts` rows of a replay bundle and of an optimisation record (T07 design note §5.4;
OPT design §4.9): what `jobs.runner` registers for a bundle a job wrote and `JobService` for one
it imports. Moved verbatim from `jobs.runner` (X06 decision X06-CI1-5).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Final

from openflowsheet.application.jobs.model import ARTIFACT_FILE_NAMES
from openflowsheet.application.store_records import ArtifactRow
from openflowsheet.canonical import directory_hash, file_sha256
from openflowsheet.run.bundle import ARTIFACT_DIR, MANIFEST_NAME
from openflowsheet.studies.nlp.replay import MANIFEST as OPTIMIZATION_MANIFEST

#: §5.4: the producer kind of each fixed file name.
KIND_OF_FILE: Final[Mapping[str, str]] = {
    name: kind for kind, name in ARTIFACT_FILE_NAMES.items() if name is not None
}


def bundle_rows(
    root: Path, directory: Path, bundle_id: str, job_id: str | None, *, producer: bool
) -> tuple[ArtifactRow, list[ArtifactRow]]:
    """The bundle's own row and its members' (`<bundle id>/<file>`), for `artifacts` (§5.4).

    `producer` is this code's own bundle, where a file name outside §5.4's table is a defect
    (`ValueError`); an imported bundle's unknown files are simply not registered.
    """
    members: list[ArtifactRow] = []
    files = [directory / MANIFEST_NAME]
    artifacts = directory / ARTIFACT_DIR
    if artifacts.is_dir():
        files.extend(sorted(path for path in artifacts.iterdir() if path.is_file()))
    for path in files:
        kind = KIND_OF_FILE.get(path.name)
        if kind is None:
            if producer:
                raise ValueError(f"producer defect: {path.name!r} has no artifact kind (§5.4)")
            continue
        members.append(
            ArtifactRow(
                artifact_id=f"{bundle_id}/{path.name}",
                job_id=job_id,
                kind=kind,
                name=path.name,
                sha256=file_sha256(path),
                size_bytes=path.stat().st_size,
                relpath=path.relative_to(root).as_posix(),
                parent_artifact_id=bundle_id,
            )
        )
    size = sum(path.stat().st_size for path in directory.rglob("*") if path.is_file())
    bundle = ArtifactRow(
        artifact_id=bundle_id,
        job_id=job_id,
        kind="replay_bundle",
        name=directory.name,
        sha256=directory_hash(directory),
        size_bytes=size,
        relpath=directory.relative_to(root).as_posix(),
    )
    return bundle, members


def record_rows(
    root: Path, directory: Path, record_id: str, job_id: str | None
) -> tuple[ArtifactRow, list[ArtifactRow]]:
    """An imported optimisation record's row and its manifest's (OPT design §4.9): the record is
    a `replay_bundle` (what `reproduce` takes; `reproduce` dispatches on its manifest's format),
    its member `<record id>/optimization-manifest.json` an `optimization_manifest`."""
    path = directory / OPTIMIZATION_MANIFEST
    manifest = ArtifactRow(
        artifact_id=f"{record_id}/{OPTIMIZATION_MANIFEST}",
        job_id=job_id,
        kind="optimization_manifest",
        name=OPTIMIZATION_MANIFEST,
        sha256=file_sha256(path),
        size_bytes=path.stat().st_size,
        relpath=path.relative_to(root).as_posix(),
        parent_artifact_id=record_id,
    )
    record = ArtifactRow(
        artifact_id=record_id,
        job_id=job_id,
        kind="replay_bundle",
        name=directory.name,
        sha256=directory_hash(directory),
        size_bytes=sum(item.stat().st_size for item in directory.rglob("*") if item.is_file()),
        relpath=directory.relative_to(root).as_posix(),
    )
    return record, [manifest]
