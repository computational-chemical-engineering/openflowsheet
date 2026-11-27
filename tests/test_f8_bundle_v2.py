"""F8-WO2 (ADR 0067 D3, D4): the v2 bundle writer `run.bundle_v2` and its test-only factory.

Two corpus cases are rerun as F0 runs them and recorded as v2 (`tests/f8_bundle_v2_support.py`):
`GP-C1` (S11 gamma-phi; three `legacy.s10` components and the `S10-wilson-ig-real-v1` parameter
set) and `TH-C1` (S11 thermal; one `legacy.s05` component). Every corpus source is `permitted` in
the repository register, so E-F8-3's referenced records are made by the test's own project
register (DECISION F8-WO2-4): before `GP-C1` is written, a record-scoped project row assesses the
parameter set's source `refused` and one component's source `unknown`.

E-F8-2: each bundle round-trips: its manifest validates against `run-manifest.schema.json` and
reads back equal; `data-lock.json` and `registry-snapshot.json` hash to `data_lock_sha256` and
`environment.registry.snapshot_sha256`; `verify_bundle` re-hashes `artifacts/records/*`, so a
mutated record byte fails it, as does a forged index. E-F8-3: a record whose sources are all
`permitted` is embedded with the store's canonical bytes; `unknown` and `refused` are referenced
only; re-assessing afterwards changes the embedding and no `data_lock_sha256`, `structural_sha256`
or R0 hash. E-F8-10's WO2 half: the v1 bundle the rerun writes is a v1 bundle, and the v2 bundle
carries its artifacts byte for byte.
"""

from __future__ import annotations

import dataclasses
import json
import shutil
import socket
from pathlib import Path
from typing import Any

import pytest
from f8_bundle_v2_support import Recorded, legacy_stack, record_v2, schema_errors

from openflowsheet.application.jobs.model import ARTIFACT_FILE_NAMES
from openflowsheet.canonical import canonical_json, file_sha256
from openflowsheet.records.lock import data_lock_sha256
from openflowsheet.records.rights import record_sources
from openflowsheet.records.stack import StoreStack
from openflowsheet.run import bundle as bundle_v1
from openflowsheet.run import bundle_v2
from openflowsheet.run.bundle import BundleError, read_artifact
from openflowsheet.run.identity import r0_projection, r0_sha256
from openflowsheet.run.manifest_v2 import BUNDLE_FORMAT

#: The parameter set and the component whose sources the test's project register reassesses.
REFUSED_SET = "S10-wilson-ig-real-v1"
UNKNOWN_COMPONENT = "C2H5OH"


def _row(stack: StoreStack, sha: str, assessment: str) -> None:
    """A record-scoped project row (ADR 0061 D11's first precedence row) for each source of
    record `sha`."""
    for ident, source in record_sources(stack.record(sha)).items():
        stack.project.append_rights(
            {
                "source_id": ident,
                "source_sha256": source,
                "record_sha256": sha,
                "assessment": assessment,
                "conditions": None,
                "basis": "F8-WO2 test register (DECISION F8-WO2-4)",
                "decided_by": "tests/test_f8_bundle_v2.py",
                "date": "2026-11-27",
            }
        )


def _record_sha(recorded: Recorded, ident: str) -> str:
    for item in recorded.lock["components"]:
        if item["id"] == ident:
            return str(item["record"])
    (sha,) = recorded.lock["parameter_sets"]
    record = recorded.stack.record(sha)
    assert record["id"] == ident
    return str(sha)


def _gp_stack(tmp: Path) -> tuple[StoreStack, Recorded]:
    """`GP-C1`'s first recording's stack, its lock's records adopted: rows can then name them."""
    stack = legacy_stack()
    return stack, record_v2("s11-gp", "GP-C1", tmp / "probe", stack)


@pytest.fixture(scope="module")
def gp(tmp_path_factory: pytest.TempPathFactory) -> Recorded:
    """`GP-C1` recorded as v2 with the parameter set `refused` and one component `unknown`."""
    tmp = tmp_path_factory.mktemp("gp")
    stack, probe = _gp_stack(tmp)
    _row(stack, _record_sha(probe, REFUSED_SET), "refused")
    _row(stack, _record_sha(probe, UNKNOWN_COMPONENT), "unknown")
    return record_v2("s11-gp", "GP-C1", tmp / "case", stack)


@pytest.fixture(scope="module")
def th(tmp_path_factory: pytest.TempPathFactory) -> Recorded:
    """`TH-C1` recorded as v2 under the registers as they ship."""
    return record_v2("s11-th", "TH-C1", tmp_path_factory.mktemp("th"), legacy_stack())


@pytest.fixture(params=["gp", "th"])
def case(request: pytest.FixtureRequest) -> Recorded:
    recorded: Recorded = request.getfixturevalue(request.param)
    return recorded


def _index(directory: Path) -> dict[str, Any]:
    document: dict[str, Any] = read_artifact(directory, bundle_v2.RECORDS_INDEX_NAME)
    return document


def _entries(directory: Path) -> dict[str, dict[str, Any]]:
    return {entry["sha256"]: entry for entry in _index(directory)["records"]}


def _identity(directory: Path) -> tuple[str, str, str, str]:
    """(`data_lock_sha256`, `structural_sha256`, the recorded `artifact_r0_sha256`, the R0 hash
    recomputed from every artifact in the bundle)."""
    manifest, _ = bundle_v2.read_manifest(directory)
    artifacts = {
        name: read_artifact(directory, name)
        for name in manifest.artifacts
        if not name.startswith(f"{bundle_v2.RECORDS_DIR}/")
    }
    recomputed = r0_sha256(r0_projection(artifacts))
    return (
        manifest.data_lock_sha256,
        manifest.structural_sha256,
        manifest.artifact_r0_sha256,
        recomputed,
    )


def _copy(recorded: Recorded, tmp_path: Path) -> Path:
    target = tmp_path / "bundle"
    shutil.copytree(recorded.v2, target)
    return target


def _reindex(directory: Path, name: str) -> None:
    """A forger's step: rebuild the manifest's index entry of `name` and both self-hashes."""
    manifest, _ = bundle_v2.read_manifest(directory)
    artifacts = dict(manifest.artifacts)
    artifacts[name] = file_sha256(directory / bundle_v1.ARTIFACT_DIR / name)
    forged = dataclasses.replace(manifest, artifacts=artifacts)
    (directory / bundle_v1.MANIFEST_NAME).write_bytes(canonical_json(forged.as_document()))


# ------------------------------------------------------------------------------------- E-F8-2


def test_e_f8_2_the_manifest_validates_and_round_trips(case: Recorded) -> None:
    manifest, document = bundle_v2.read_manifest(case.v2)
    assert schema_errors("run-manifest.schema.json", document) == []
    assert document["bundle_format"] == BUNDLE_FORMAT
    assert manifest == case.manifest
    raw = (case.v2 / bundle_v1.MANIFEST_NAME).read_bytes()
    assert raw == canonical_json(manifest.as_document())
    assert bundle_v2.verify_bundle(case.v2).as_document() == {
        "ok": True,
        "missing": [],
        "tampered": [],
        "unexpected": [],
    }


def test_e_f8_2_the_lock_and_the_snapshot_hash_to_their_manifest_values(case: Recorded) -> None:
    manifest = case.manifest
    root = case.v2 / bundle_v1.ARTIFACT_DIR
    lock_sha = file_sha256(root / bundle_v2.DATA_LOCK_NAME)
    assert lock_sha == manifest.data_lock_sha256 == data_lock_sha256(case.lock)
    snapshot_sha = file_sha256(root / bundle_v2.REGISTRY_SNAPSHOT_NAME)
    assert snapshot_sha == manifest.environment_registry.snapshot_sha256
    snapshot = read_artifact(case.v2, bundle_v2.REGISTRY_SNAPSHOT_NAME)
    assert snapshot["registry_sha256"] == manifest.environment_registry.registry_sha256
    assert schema_errors("data-lock.schema.json", case.lock) == []
    assert schema_errors("registry-snapshot.schema.json", snapshot) == []
    assert schema_errors("records-index.schema.json", _index(case.v2)) == []


def test_e_f8_2_the_index_covers_every_file_under_artifacts(case: Recorded) -> None:
    root = case.v2 / bundle_v1.ARTIFACT_DIR
    files = {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()}
    assert files == set(case.manifest.artifacts)
    embedded = {sha for sha, entry in _entries(case.v2).items() if entry["embedded"]}
    assert {bundle_v2.record_name(sha) for sha in embedded} <= files


def test_e_f8_2_a_mutated_record_byte_fails_the_integrity_check(
    gp: Recorded, tmp_path: Path
) -> None:
    target = _copy(gp, tmp_path)
    name = next(n for n in gp.manifest.artifacts if n.startswith("records/"))
    path = target / bundle_v1.ARTIFACT_DIR / name
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 0x01
    path.write_bytes(bytes(data))
    integrity = bundle_v2.verify_bundle(target)
    assert not integrity.ok and integrity.tampered == (name,)

    # A forger who also rebuilds the index and the self-hashes is caught by the record's own
    # name: an embedded record must hash to its SHA.
    _reindex(target, name)
    integrity = bundle_v2.verify_bundle(target)
    assert not integrity.ok and integrity.tampered == (name,)


def test_e_f8_2_a_removed_record_or_a_forged_lock_fails_the_integrity_check(
    gp: Recorded, tmp_path: Path
) -> None:
    target = _copy(gp, tmp_path)
    name = next(n for n in gp.manifest.artifacts if n.startswith("records/"))
    (target / bundle_v1.ARTIFACT_DIR / name).unlink()
    integrity = bundle_v2.verify_bundle(target)
    assert not integrity.ok and integrity.missing == (name,)

    target = _copy(gp, tmp_path / "lock")
    lock = dict(gp.lock, method_options={"wilson-ig-v2": {"forged": True}})
    (target / bundle_v1.ARTIFACT_DIR / bundle_v2.DATA_LOCK_NAME).write_bytes(canonical_json(lock))
    _reindex(target, bundle_v2.DATA_LOCK_NAME)
    integrity = bundle_v2.verify_bundle(target)
    assert not integrity.ok and bundle_v2.DATA_LOCK_NAME in integrity.tampered


def test_e_f8_2_an_index_not_naming_the_locks_records_fails_the_integrity_check(
    gp: Recorded, tmp_path: Path
) -> None:
    target = _copy(gp, tmp_path)
    index = _index(target)
    index["records"] = index["records"][1:]
    path = target / bundle_v1.ARTIFACT_DIR / bundle_v2.RECORDS_INDEX_NAME
    path.write_bytes(canonical_json(index))
    _reindex(target, bundle_v2.RECORDS_INDEX_NAME)
    integrity = bundle_v2.verify_bundle(target)
    assert not integrity.ok and bundle_v2.RECORDS_INDEX_NAME in integrity.tampered


def test_the_v1_reader_does_not_read_a_v2_bundle(gp: Recorded) -> None:
    """D5: a v2 bundle is read by its own reader (WO3 dispatches); the untouched v1 reader fails
    on it (at `Environment(registry=...)`, before its unknown-member check) rather than reading it
    with members dropped."""
    with pytest.raises(TypeError, match="registry"):
        bundle_v1.read_manifest(gp.v2)


# ------------------------------------------------------------------------------------- E-F8-3


def test_e_f8_3_a_record_whose_sources_are_all_permitted_is_embedded(case: Recorded) -> None:
    entries = _entries(case.v2)
    permitted = {
        sha
        for sha, entry in entries.items()
        if all(source["assessment"] == "permitted" for source in entry["sources"])
    }
    assert permitted, "each case embeds at least one record"
    for sha in permitted:
        assert entries[sha]["embedded"] is True
        written = (case.v2 / bundle_v1.ARTIFACT_DIR / bundle_v2.record_name(sha)).read_bytes()
        assert written == case.stack.object_bytes(sha) == case.stack.project.object_bytes(sha)


def test_e_f8_3_the_conditions_are_copied_into_the_index(th: Recorded) -> None:
    (entry,) = _index(th.v2)["records"]
    (source,) = entry["sources"]
    assert source["source_id"] == "legacy.s05" and source["assessment"] == "permitted"
    assert source["conditions"].startswith("Publication in whole or in part is allowed")


def test_e_f8_3_unknown_and_refused_records_are_referenced_only(gp: Recorded) -> None:
    entries = _entries(gp.v2)
    assessed = {
        sha: {source["assessment"] for source in entry["sources"]} for sha, entry in entries.items()
    }
    refused = _record_sha(gp, REFUSED_SET)
    unknown = _record_sha(gp, UNKNOWN_COMPONENT)
    assert assessed[refused] == {"refused"} and assessed[unknown] == {"unknown"}
    assert sorted(sha for sha, entry in entries.items() if not entry["embedded"]) == sorted(
        [refused, unknown]
    )
    for sha in (refused, unknown):
        name = bundle_v2.record_name(sha)
        assert name not in gp.manifest.artifacts
        assert not (gp.v2 / bundle_v1.ARTIFACT_DIR / name).exists()
    assert sum(entry["embedded"] for entry in entries.values()) == 2


def test_e_f8_3_reassessing_a_source_changes_no_identity(gp: Recorded, tmp_path: Path) -> None:
    """Re-assessing after writing flips the embedding both ways and moves no `data_lock_sha256`,
    `structural_sha256` or R0 hash; the lock's bytes do not move either."""
    before = _identity(gp.v2)
    assert before[2] == before[3], "the R0 hash recomputed from the bundle is the recorded one"

    stack, _ = _gp_stack(tmp_path)
    for sha in gp.lock["parameter_sets"]:
        _row(stack, sha, "permitted")
    _row(stack, _record_sha(gp, UNKNOWN_COMPONENT), "permitted")
    _row(stack, _record_sha(gp, "H2O"), "refused")
    rewritten = gp.rewrite(tmp_path / "again", stack=stack)

    entries = _entries(tmp_path / "again")
    assert entries[_record_sha(gp, REFUSED_SET)]["embedded"] is True
    assert entries[_record_sha(gp, UNKNOWN_COMPONENT)]["embedded"] is True
    assert entries[_record_sha(gp, "H2O")]["embedded"] is False
    assert _identity(tmp_path / "again") == before
    assert rewritten.manifest_sha256 != gp.manifest.manifest_sha256  # the index moved
    lock = bundle_v1.ARTIFACT_DIR + "/" + bundle_v2.DATA_LOCK_NAME
    assert (tmp_path / "again" / lock).read_bytes() == (gp.v2 / lock).read_bytes()
    assert bundle_v2.verify_bundle(tmp_path / "again").ok


def test_e_f8_3_a_repository_row_reassesses_too(th: Recorded, tmp_path: Path) -> None:
    """The repository layer (D11's last rows): a whole-source `refused` row after the seed
    references `TH-C1`'s record; nothing in identity moves."""
    (entry,) = _index(th.v2)["records"]
    (source,) = entry["sources"]
    from openflowsheet.records.rights import repository_rows  # noqa: PLC0415

    refusal = {
        "source_id": source["source_id"],
        "source_sha256": source["source_sha256"],
        "record_sha256": None,
        "assessment": "refused",
        "conditions": None,
        "basis": "F8-WO2 test register",
        "decided_by": "tests/test_f8_bundle_v2.py",
        "date": "2026-11-27",
    }
    th.rewrite(tmp_path, stack=legacy_stack(), repository=[*repository_rows(), refusal])
    (again,) = _index(tmp_path)["records"]
    assert again["embedded"] is False and again["sources"][0]["assessment"] == "refused"
    assert _identity(tmp_path) == _identity(th.v2)


def test_d4_no_network_access_while_writing(
    gp: Recorded, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access while writing a bundle")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    gp.rewrite(tmp_path)
    assert bundle_v2.verify_bundle(tmp_path).ok


# ------------------------------------------------------------------------------- the writer


def test_the_writer_refuses_a_manifest_that_disagrees_with_its_documents(
    gp: Recorded, tmp_path: Path
) -> None:
    wrong = dataclasses.replace(gp.manifest, data_lock_sha256="0" * 64)
    with pytest.raises(BundleError, match="data_lock_sha256"):
        bundle_v2.write_bundle(
            tmp_path, wrong, gp.artifacts, lock=gp.lock, snapshot=gp.snapshot, stack=gp.stack
        )
    registry = dataclasses.replace(gp.manifest.environment_registry, snapshot_sha256="0" * 64)
    wrong = dataclasses.replace(gp.manifest, environment_registry=registry)
    with pytest.raises(BundleError, match="snapshot_sha256"):
        bundle_v2.write_bundle(
            tmp_path, wrong, gp.artifacts, lock=gp.lock, snapshot=gp.snapshot, stack=gp.stack
        )
    clash = {**gp.artifacts, bundle_v2.DATA_LOCK_NAME: {}}
    with pytest.raises(BundleError, match="reserves"):
        bundle_v2.write_bundle(
            tmp_path, gp.manifest, clash, lock=gp.lock, snapshot=gp.snapshot, stack=gp.stack
        )


def test_d3_file_names_are_the_job_artifact_kinds_names() -> None:
    assert ARTIFACT_FILE_NAMES["data_lock"] == bundle_v2.DATA_LOCK_NAME
    assert ARTIFACT_FILE_NAMES["registry_snapshot"] == bundle_v2.REGISTRY_SNAPSHOT_NAME
    assert ARTIFACT_FILE_NAMES["records_index"] == bundle_v2.RECORDS_INDEX_NAME
    assert ARTIFACT_FILE_NAMES["record"] is None


# ------------------------------------------------------------------------------------ E-F8-10


def test_e_f8_10_the_rerun_writes_a_v1_bundle_and_the_v2_one_carries_its_artifacts(
    case: Recorded,
) -> None:
    manifest, document = bundle_v1.read_manifest(case.v1)
    assert "bundle_format" not in document and "registry" not in document["environment"]
    assert bundle_v1.verify_bundle(case.v1).ok
    for name in manifest.artifacts:
        v1_bytes = (case.v1 / bundle_v1.ARTIFACT_DIR / name).read_bytes()
        assert (case.v2 / bundle_v1.ARTIFACT_DIR / name).read_bytes() == v1_bytes, name
    hashes = ("artifacts", "environment", "manifest_sha256", "structural_sha256")
    v1_fields = {k: v for k, v in document.items() if k not in hashes}
    v2_document = json.loads((case.v2 / bundle_v1.MANIFEST_NAME).read_text(encoding="utf-8"))
    assert {k: v2_document[k] for k in v1_fields} == v1_fields
