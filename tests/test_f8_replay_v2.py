"""F8-WO3: replay of a v2 bundle, ADR 0067 D5 (exits E-F8-1, E-F8-4, E-F8-5, E-F8-6).

The v2 bundles are F8-WO2's factory's (`f8_bundle_v2_support.record_v2`): GP-C1 and TH-C1, the
registered v2 cases. Each is replayed through `run.replay_v2.replay_v2` with the environment it
recorded as this side, against a rerun of its recorded revision (`rerun_v2`, under
`registry.usage()`).

- **E-F8-1** is shown on the 52 committed 0.3.0 bundles in four fixed scenarios
  (`scripts/f8_v1_replay_reports.py`): each report's canonical JSON has the SHA it had at
  `ddac950f`, before F8's replay. F0's M7 reruns the same bundles for real (mode, verdict,
  reasons; 52/52).
- **E-F8-4**'s local store is a stack the test builds: the shipped records with the absent ones
  filtered out, or no records at all.
- **E-F8-5**'s current registry is `edited_registry`: a shallow copy of the process registry in
  which named descriptors carry another `self_sha256` (and, for the non-built-in case, the origin
  `installed`) or are removed (DECISION F8-WO3-6).
- **E-F8-6**'s hidden `resolve` wraps `revision_run.run_revision_session` so that the rerun asks
  the registry for a unit model its recorded identity does not name.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT, load_json
from f8_bundle_v2_support import (
    V2_CASES,
    Recorded,
    edited_registry,
    legacy_stack,
    record_v2,
    rerecord,
    rerun_v2,
    schema_errors,
)

from openflowsheet.application import cli, revision_run
from openflowsheet.application.revision_replay import V2_RERUN_UNAVAILABLE, reproduce_bundle
from openflowsheet.canonical import canonical_json, document_sha256, file_sha256
from openflowsheet.records.importers.legacy import available_records
from openflowsheet.records.lock import data_lock_sha256
from openflowsheet.records.rights import record_sources
from openflowsheet.records.stack import LegacyStore, StoreStack
from openflowsheet.records.store import RecordStore, object_bytes
from openflowsheet.registry import Registry, default_registry
from openflowsheet.run import bundle_v2
from openflowsheet.run.bundle import ARTIFACT_DIR, MANIFEST_NAME, read_artifact
from openflowsheet.run.manifest import Environment
from openflowsheet.run.manifest_v2 import ReplayModeRefusedError
from openflowsheet.run.replay import (
    REGISTERED_PLATFORMS,
    ReplayReport,
    Rerun,
    decide_mode,
    replay,
    unknown_policy_reason,
)
from openflowsheet.run.replay_v2 import (
    FAILED_INTEGRITY,
    NO_RERUN,
    NO_USAGE,
    RerunV2,
    bundle_format,
    replay_v2,
    served_stack,
)

sys.path.insert(0, str(REPO_ROOT / "scripts"))

import corpus_identity as gate  # noqa: E402
import f8_v1_replay_reports as v1_reports  # noqa: E402

#: DECISION F8-WO2-4's reassessment: GP-C1's parameter set refused, one component unknown, so
#: the bundle references both and embeds the other two components.
REFERENCED = ("S10-wilson-ig-real-v1", "C2H5OH")


# ------------------------------------------------------------------------------------ helpers


def _row(stack: StoreStack, sha: str, assessment: str) -> None:
    """A record-scoped project rights row (ADR 0061 D11) for each source of record `sha`."""
    for ident, source in record_sources(stack.record(sha)).items():
        stack.project.append_rights(
            {
                "source_id": ident,
                "source_sha256": source,
                "record_sha256": sha,
                "assessment": assessment,
                "conditions": None,
                "basis": "F8-WO3 test register (DECISION F8-WO2-4)",
                "decided_by": "tests/test_f8_replay_v2.py",
                "date": "2026-11-27",
            }
        )


def _sha_of(recorded: Recorded, ident: str) -> str:
    for item in recorded.lock["components"]:
        if item["id"] == ident:
            return str(item["record"])
    for sha in recorded.lock["parameter_sets"]:
        if recorded.stack.record(sha)["id"] == ident:
            return str(sha)
    raise KeyError(ident)


def _local(without: frozenset[str] = frozenset()) -> StoreStack:
    """A local store: an empty project store over the shipped records less `without`."""

    def loader() -> list[Any]:
        return [record for record in available_records() if object_bytes(record)[0] not in without]

    return StoreStack(RecordStore.in_memory(), LegacyStore(loader))


def _environment(recorded: Recorded) -> Environment:
    return recorded.manifest.environment


def _replay(
    recorded: Recorded,
    rerun: Rerun | None,
    *,
    registry: Registry | None = None,
    store: StoreStack | None = None,
    directory: Path | None = None,
) -> ReplayReport:
    return replay_v2(
        recorded.v2 if directory is None else directory,
        rerun,
        current=_environment(recorded),
        registry=registry,
        store=_local() if store is None else store,
    )


def _valid(report: ReplayReport) -> ReplayReport:
    assert schema_errors("replay-report.schema.json", report.as_document()) == []
    return report


def _used(recorded: Recorded, kind: str) -> tuple[str, str, str]:
    for row in recorded.manifest.extensions_used:
        if row[0] == kind:
            return row[0], row[1], row[2]
    raise KeyError(kind)


def _unused(recorded: Recorded, kind: str) -> tuple[str, str, str]:
    """A registered (kind, id, version) the run did not use."""
    used = {row[:3] for row in recorded.manifest.extensions_used}
    for row in default_registry().snapshot()["extensions"]:
        key = (row["kind"], row["id"], row["version"])
        if row["kind"] == kind and key not in used:
            return key
    raise KeyError(kind)


# ----------------------------------------------------------------------------------- fixtures


@pytest.fixture(scope="module", params=[name for _, name in V2_CASES])
def plain(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> Recorded:
    """A registered v2 case recorded under the registers as they ship: every record embedded."""
    run_set = dict((name, run_set) for run_set, name in V2_CASES)[request.param]
    with gate.pinned_threads():
        return record_v2(run_set, request.param, tmp_path_factory.mktemp("plain"), legacy_stack())


@pytest.fixture(scope="module")
def plain_rerun(plain: Recorded, tmp_path_factory: pytest.TempPathFactory) -> RerunV2:
    return rerun_v2(plain.v2, tmp_path_factory.mktemp("rerun") / "run")


@pytest.fixture(scope="module")
def gp(tmp_path_factory: pytest.TempPathFactory) -> Recorded:
    """GP-C1 recorded with its parameter set and C2H5OH referenced (DECISION F8-WO2-4)."""
    tmp = tmp_path_factory.mktemp("gp")
    stack = legacy_stack()
    probe = record_v2("s11-gp", "GP-C1", tmp / "probe", stack)
    _row(stack, _sha_of(probe, REFERENCED[0]), "refused")
    _row(stack, _sha_of(probe, REFERENCED[1]), "unknown")
    with gate.pinned_threads():
        return record_v2("s11-gp", "GP-C1", tmp / "case", stack)


@pytest.fixture(scope="module")
def gp_rerun(gp: Recorded, tmp_path_factory: pytest.TempPathFactory) -> RerunV2:
    return rerun_v2(gp.v2, tmp_path_factory.mktemp("gp-rerun") / "run")


@pytest.fixture(scope="module")
def baseline(plain: Recorded, plain_rerun: RerunV2) -> ReplayReport:
    """The replay with nothing changed: recorded with the thread pins F0 sets and replayed in the
    recorded environment, an exact replay that matches."""
    report = _valid(_replay(plain, plain_rerun))
    assert (report.mode, report.verdict, report.reasons) == ("exact_replay", "MATCH", ())
    assert report.differences == ()
    return report


# ------------------------------------------------------------------------------------- E-F8-1


def test_e_f8_1_every_committed_0_3_0_bundle_replays_byte_identically() -> None:
    """Every committed 0.3.0 bundle, in each of the four scenarios, gives the report whose
    canonical JSON has the SHA computed at `ddac950f` (before F8's replay)."""
    expected = load_json(v1_reports.EXPECTED)
    measured = v1_reports.digests()
    assert len(measured) == 52
    assert measured == expected


def test_e_f8_1_a_v1_report_carries_no_amendment_12_member() -> None:
    directory = v1_reports.bundle_directories()[0]
    assert bundle_format(directory) is None
    for document in v1_reports.reports(directory).values():
        assert "registry_comparison" not in document
        assert "data_availability" not in document


def test_e_f8_1_forced_replay_stays_refused() -> None:
    """Amendment 12's `forced_replay` is a `ReplayMode` member that no report may take until
    F8-WO7 (WO1-6)."""
    directory = v1_reports.bundle_directories()[0]
    template = v1_reports.reports(directory)["inspect"]
    with pytest.raises(ReplayModeRefusedError, match=r"construct_unavailable\(forced_replay, TX\)"):
        ReplayReport(
            mode="forced_replay",
            verdict="NOT_RUN",
            integrity=replay(directory, None).integrity,
            recorded_environment=template["recorded_environment"],
            current_environment=template["current_environment"],
        )


# ----------------------------------------------------------------- D5 steps 1, 2 and the dispatch


def test_the_v1_entry_point_dispatches_a_v2_bundle(plain: Recorded, plain_rerun: RerunV2) -> None:
    """`run.replay.replay` hands a manifest with `bundle_format` to `replay_v2` (its default
    registry and store)."""
    through_v1 = replay(plain.v2, plain_rerun, current=_environment(plain))
    direct = replay_v2(plain.v2, plain_rerun, current=_environment(plain))
    assert through_v1 == direct
    assert through_v1.registry_comparison is not None


def test_an_unknown_bundle_format_is_unsupported(plain: Recorded, tmp_path: Path) -> None:
    directory = tmp_path / "bundle"
    shutil.copytree(plain.v2, directory)
    path = directory / MANIFEST_NAME
    document = json.loads(path.read_text(encoding="utf-8"))
    document["bundle_format"] = "openflowsheet-bundle-v3"
    path.write_text(json.dumps(document), encoding="utf-8")
    report = _valid(replay(directory, Rerun({}), current=_environment(plain)))
    assert (report.mode, report.verdict) == ("inspected_archived_results", "NOT_RUN")
    assert report.reasons == ("bundle_format_unsupported(openflowsheet-bundle-v3)",)
    assert report.integrity.ok
    assert report.registry_comparison is None and report.data_availability is None


def _reformatted(source: Path, directory: Path, value: str) -> Path:
    """A copy of the bundle `source` whose manifest names `bundle_format` `value`."""
    shutil.copytree(source, directory)
    path = directory / MANIFEST_NAME
    document = json.loads(path.read_text(encoding="utf-8"))
    document["bundle_format"] = value
    path.write_text(json.dumps(document), encoding="utf-8")
    return directory


@pytest.mark.parametrize("rerun", [False, True], ids=["inspect", "rerun"])
def test_the_served_reproduce_of_a_v2_bundle_is_inspected(
    plain: Recorded, tmp_path: Path, rerun: bool
) -> None:
    """Review F8 M2: `reproduce_bundle` dispatches on `bundle_format` before the v1 reader. A v2
    bundle is inspected, and with a rerun asked the reason names the construct F8-WO6 owes
    (DECISION F8-FR-2)."""
    with gate.pinned_threads():
        result = reproduce_bundle(
            plain.v2, rerun=rerun, rerun_directory=tmp_path / "rerun", run_id="f8-fr-m2"
        )
    report = _valid(result.report)
    assert (report.mode, report.verdict) == ("inspected_archived_results", "NOT_RUN")
    assert report.integrity.ok
    assert report.reasons == ((V2_RERUN_UNAVAILABLE,) if rerun else (NO_RERUN,)), report.reasons
    assert result.rerun_manifest is None
    assert not (tmp_path / "rerun").exists()


@pytest.mark.parametrize("rerun", [False, True], ids=["inspect", "rerun"])
def test_the_served_reproduce_of_an_unknown_format_is_unsupported(
    plain: Recorded, tmp_path: Path, rerun: bool
) -> None:
    directory = _reformatted(plain.v2, tmp_path / "bundle", "openflowsheet-bundle-v3")
    result = reproduce_bundle(
        directory, rerun=rerun, rerun_directory=tmp_path / "rerun", run_id="f8-fr-m2"
    )
    report = _valid(result.report)
    assert (report.mode, report.verdict) == ("inspected_archived_results", "NOT_RUN")
    assert report.reasons == ("bundle_format_unsupported(openflowsheet-bundle-v3)",)
    assert result.rerun_manifest is None


def test_the_cli_inspects_a_v2_bundle(plain: Recorded, capsys: pytest.CaptureFixture[str]) -> None:
    """Review F8 M2: `inspect` reads a v2 bundle with the v2 reader."""
    assert cli.main(["inspect", str(plain.v2)]) == 0
    out = capsys.readouterr().out
    assert f"structural sha256 {plain.manifest.structural_sha256}" in out
    assert "integrity         ok" in out


def test_the_cli_refuses_to_inspect_an_unknown_format(
    plain: Recorded, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = _reformatted(plain.v2, tmp_path / "bundle", "openflowsheet-bundle-v3")
    assert cli.main(["inspect", str(directory)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "bundle_format_unsupported(openflowsheet-bundle-v3)" in captured.err


@pytest.mark.parametrize(
    "artifacts", [None, ["solution-state.json"], "x"], ids=["kept", "a-list", "a-string"]
)
def test_an_unknown_format_lists_a_failed_integrity_check_first(
    plain: Recorded, tmp_path: Path, artifacts: Any
) -> None:
    """Review F8 S1: step 1 comes before step 2, so a `-v3` bundle that fails its integrity check
    is reported with `FAILED_INTEGRITY` before `bundle_format_unsupported`. An `artifacts` member
    that is not an object indexes nothing: every file is unexpected."""
    directory = _reformatted(plain.v2, tmp_path / "bundle", "x-v3")
    if artifacts is None:
        (directory / ARTIFACT_DIR / "solution-state.json").write_text("garbage", encoding="utf-8")
    else:
        path = directory / MANIFEST_NAME
        document = json.loads(path.read_text(encoding="utf-8"))
        document["artifacts"] = artifacts
        path.write_text(json.dumps(document), encoding="utf-8")
    report = _valid(replay(directory, None, current=_environment(plain)))
    assert (report.mode, report.verdict) == ("inspected_archived_results", "NOT_RUN")
    assert report.reasons == (FAILED_INTEGRITY, "bundle_format_unsupported(x-v3)")
    assert not report.integrity.ok
    if artifacts is None:
        assert report.integrity.tampered == ("solution-state.json",)
    else:
        assert report.integrity.missing == report.integrity.tampered == ()
        assert "solution-state.json" in report.integrity.unexpected


def test_a_failed_integrity_check_reruns_nothing(
    plain: Recorded, plain_rerun: RerunV2, tmp_path: Path
) -> None:
    directory = tmp_path / "bundle"
    shutil.copytree(plain.v2, directory)
    (directory / ARTIFACT_DIR / bundle_v2.DATA_LOCK_NAME).write_text("{}", encoding="utf-8")
    report = _valid(_replay(plain, plain_rerun, directory=directory))
    assert (report.mode, report.verdict) == ("inspected_archived_results", "NOT_RUN")
    assert report.reasons[0] == FAILED_INTEGRITY
    assert report.differences == ()


@pytest.mark.parametrize(
    ("name", "text"),
    [
        (bundle_v2.RECORDS_INDEX_NAME, "not json"),
        (bundle_v2.RECORDS_INDEX_NAME, "[]"),
        (bundle_v2.RECORDS_INDEX_NAME, '{"records": [{}]}'),
        (bundle_v2.DATA_LOCK_NAME, "not json"),
    ],
    ids=["index-not-json", "index-a-list", "index-entry-empty", "lock-not-json"],
)
def test_a_malformed_v2_document_is_reported_tampered_not_raised(
    plain: Recorded, tmp_path: Path, name: str, text: str
) -> None:
    """Review F8 M1: D5 step 1 reports a tampered lock or records index; it does not raise on
    one that does not parse or does not have D3's shape."""
    directory = tmp_path / "bundle"
    shutil.copytree(plain.v2, directory)
    (directory / ARTIFACT_DIR / name).write_text(text, encoding="utf-8")
    report = _valid(replay(directory, None, current=_environment(plain)))
    assert (report.mode, report.verdict) == ("inspected_archived_results", "NOT_RUN")
    assert report.reasons[0] == FAILED_INTEGRITY
    assert not report.integrity.ok
    assert name in report.integrity.tampered


# ------------------------------------------------------------------------------------- E-F8-4


def test_e_f8_4_a_referenced_record_absent_from_the_store_is_data_unavailable(
    gp: Recorded, gp_rerun: RerunV2
) -> None:
    absent = _sha_of(gp, REFERENCED[1])
    report = _valid(_replay(gp, gp_rerun, store=_local(frozenset({absent}))))
    assert (report.mode, report.verdict) == ("inspected_archived_results", "NOT_RUN")
    assert report.reasons == (f"data_unavailable({absent})",)
    assert report.data_availability == {"embedded": 2, "from_store": 1, "missing": [absent]}
    assert report.differences == ()


def test_e_f8_4_two_absent_records_are_both_listed_in_sorted_order(
    gp: Recorded, gp_rerun: RerunV2
) -> None:
    absent = sorted(_sha_of(gp, ident) for ident in REFERENCED)
    report = _valid(_replay(gp, gp_rerun, store=_local(frozenset(absent))))
    assert (report.mode, report.verdict) == ("inspected_archived_results", "NOT_RUN")
    assert report.reasons == tuple(f"data_unavailable({sha})" for sha in absent)
    assert report.data_availability == {"embedded": 2, "from_store": 0, "missing": absent}


def test_e_f8_4_referenced_records_in_the_store_rerun_and_match(
    gp: Recorded, gp_rerun: RerunV2
) -> None:
    report = _valid(_replay(gp, gp_rerun))
    assert report.verdict == "MATCH", report.differences
    assert report.data_availability == {"embedded": 2, "from_store": 2, "missing": []}


def test_e_f8_4_embedded_records_need_no_store_and_the_replay_matches(
    plain: Recorded, plain_rerun: RerunV2, baseline: ReplayReport
) -> None:
    """Every record embedded, a local store holding none: step 6 resolves each from the bundle,
    the rerun runs and matches."""
    empty = StoreStack(RecordStore.in_memory())
    report = _valid(_replay(plain, plain_rerun, store=empty))
    count = len(bundle_v2.locked_records(plain.lock))
    assert report.data_availability == {"embedded": count, "from_store": 0, "missing": []}
    assert (report.mode, report.verdict) == (baseline.mode, "MATCH"), report.differences
    assert report.reasons == baseline.reasons


def test_e_f8_4_the_rerun_reads_the_records_the_bundle_embeds(plain: Recorded) -> None:
    """DECISION F8-WO3-1's premise, measured: the served stack gives every locked record from the
    bundle before the store, and the records the recorded (v1) revision's binder reads, the
    shipped legacy files as imported (`available_records`), are byte for byte the embedded
    ones."""
    served = served_stack(plain.v2, StoreStack(RecordStore.in_memory()))
    shipped = LegacyStore(available_records).store()
    assert served.layers()[0] is served.bundle
    for sha in bundle_v2.locked_records(plain.lock):
        embedded = (plain.v2 / ARTIFACT_DIR / bundle_v2.record_name(sha)).read_bytes()
        assert served.bundle.object_bytes(sha) == embedded
        assert served.object_bytes(sha) == embedded
        assert shipped.object_bytes(sha) == embedded


def test_a_non_canonical_embedded_record_is_store_object_corrupt(
    plain: Recorded, plain_rerun: RerunV2, tmp_path: Path
) -> None:
    """Step 6 re-applies the identity rule to an embedded record. A forger who writes a record's
    content in other bytes, names the file by their hash and rebuilds the lock, the index and the
    manifest passes the integrity check; step 6 refuses the bytes `store_object_corrupt(<sha>)`."""
    directory = tmp_path / "bundle"
    shutil.copytree(plain.v2, directory)
    root = directory / ARTIFACT_DIR
    old = bundle_v2.locked_records(plain.lock)[0]
    data = json.dumps(json.loads((root / bundle_v2.record_name(old)).read_bytes()), indent=1)
    forged = hashlib.sha256(data.encode("utf-8")).hexdigest()
    (root / bundle_v2.record_name(old)).unlink()
    (root / bundle_v2.record_name(forged)).write_text(data, encoding="utf-8")
    lock = json.loads(json.dumps(plain.lock).replace(old, forged))
    (root / bundle_v2.DATA_LOCK_NAME).write_bytes(canonical_json(lock))
    index = read_artifact(directory, bundle_v2.RECORDS_INDEX_NAME)
    for entry in index["records"]:
        entry["sha256"] = forged if entry["sha256"] == old else entry["sha256"]
    index["records"].sort(key=lambda entry: entry["sha256"])
    (root / bundle_v2.RECORDS_INDEX_NAME).write_bytes(canonical_json(index))
    manifest, _ = bundle_v2.read_manifest(directory)
    rebuilt = dataclasses.replace(
        manifest,
        artifacts={
            str(path.relative_to(root)): file_sha256(path)
            for path in sorted(root.rglob("*"))
            if path.is_file()
        },
        data_lock_sha256=data_lock_sha256(lock),
    )
    (directory / MANIFEST_NAME).write_bytes(canonical_json(rebuilt.as_document()))
    assert bundle_v2.verify_bundle(directory).ok

    report = _valid(_replay(plain, plain_rerun, directory=directory))
    assert (report.mode, report.verdict) == ("inspected_archived_results", "NOT_RUN")
    assert f"store_object_corrupt({forged})" in report.reasons
    assert (
        served_stack(directory, StoreStack(RecordStore.in_memory())).bundle.record(forged) is None
    )


# ------------------------------------------------------------------------------------- E-F8-5


def test_e_f8_5_the_recorded_snapshot_is_adr_0060_d10s_document(plain: Recorded) -> None:
    snapshot = read_artifact(plain.v2, bundle_v2.REGISTRY_SNAPSHOT_NAME)
    assert snapshot == default_registry().snapshot()
    assert schema_errors("registry-snapshot.schema.json", snapshot) == []
    registry = plain.manifest.environment_registry
    assert document_sha256(snapshot) == registry.snapshot_sha256
    assert (
        snapshot["registry_sha256"]
        == registry.registry_sha256
        == default_registry().registry_sha256
    )


def test_e_f8_5_nothing_changed_compares_nothing_changed(baseline: ReplayReport) -> None:
    assert baseline.registry_comparison is not None
    assert baseline.registry_comparison["changed"] == []
    assert baseline.registry_comparison["missing"] == []
    assert baseline.registry_comparison["unused_differences"] == 0
    assert not any(reason.startswith("extension_") for reason in baseline.reasons)


def test_e_f8_5_a_changed_used_non_built_in_is_not_run(
    plain: Recorded, plain_rerun: RerunV2
) -> None:
    key = _used(plain, "unit_model")
    registry = edited_registry({key: {"self_sha256": "0" * 64, "origin": "installed"}})
    report = _valid(_replay(plain, plain_rerun, registry=registry))
    assert (report.mode, report.verdict) == ("inspected_archived_results", "NOT_RUN")
    assert report.reasons == (f"extension_changed({', '.join(key)})",)
    assert report.registry_comparison is not None
    assert report.registry_comparison["changed"] == [list(key)]
    assert report.registry_comparison["current_registry_sha256"] == registry.registry_sha256
    assert (
        report.registry_comparison["current_registry_sha256"]
        != (report.registry_comparison["recorded_registry_sha256"])
    )
    assert report.differences == ()


def test_e_f8_5_a_changed_used_built_in_reruns_as_a_compatible_reproduction(
    plain: Recorded, plain_rerun: RerunV2
) -> None:
    key = _used(plain, "unit_model")
    registry = edited_registry({key: {"self_sha256": "0" * 64}})
    report = _valid(_replay(plain, plain_rerun, registry=registry))
    assert report.mode == "compatible_reproduction"
    assert report.reasons == (f"extension_changed({', '.join(key)})",)
    # Rerun and compared: the code did not really change, so the comparison finds nothing.
    assert report.verdict == "MATCH", report.differences
    assert report.bitwise_floats is True
    assert report.registry_comparison is not None
    assert report.registry_comparison["changed"] == [list(key)]


def test_e_f8_5_a_missing_used_extension_is_unavailable(
    plain: Recorded, plain_rerun: RerunV2
) -> None:
    key = _used(plain, "data_source")
    registry = edited_registry({key: None})
    report = _valid(_replay(plain, plain_rerun, registry=registry))
    assert (report.mode, report.verdict) == ("inspected_archived_results", "NOT_RUN")
    assert report.reasons == (f"extension_unavailable({', '.join(key)})",)
    assert report.registry_comparison is not None
    assert report.registry_comparison["missing"] == [list(key)]
    assert report.registry_comparison["unused_differences"] == 0


def test_e_f8_5_a_changed_unused_extension_changes_neither_mode_nor_verdict(
    plain: Recorded, plain_rerun: RerunV2, baseline: ReplayReport
) -> None:
    key = _unused(plain, "unit_model")
    registry = edited_registry({key: {"self_sha256": "0" * 64}})
    report = _valid(_replay(plain, plain_rerun, registry=registry))
    assert (report.mode, report.verdict, report.reasons) == (
        baseline.mode,
        baseline.verdict,
        baseline.reasons,
    )
    assert report.registry_comparison is not None
    assert report.registry_comparison["unused_differences"] == 1
    assert report.registry_comparison["changed"] == []


# ------------------------------------------------------- D5 steps 3 and 4, and the order of steps


def _other_platform(recorded: Recorded) -> Environment:
    """The recorded environment on the other registered architecture."""
    here = _environment(recorded)
    other = v1_reports.OTHER_ARCHITECTURE.get(here.architecture, "x86_64")
    return dataclasses.replace(here, architecture=other)


def test_d5_another_platform_and_a_changed_built_in_rerun_as_a_compatible_reproduction(
    plain: Recorded, plain_rerun: RerunV2
) -> None:
    """Review F8 S2 (a): step 4's compatible reproduction stays one when a used built-in also
    changed; the reasons are the environment's, then step 5's; the rerun is compared."""
    recorded = _environment(plain)
    if (recorded.architecture, recorded.os_name) not in REGISTERED_PLATFORMS:
        # The bundle is recorded on this host; a compatible reproduction needs both sides on a
        # registered platform (Linux x86_64 and aarch64 legs run it). DECISION F8-CI1-2.
        pytest.skip(f"recorded on {recorded.architecture}/{recorded.os_name}, not registered")
    key = _used(plain, "unit_model")
    registry = edited_registry({key: {"self_sha256": "0" * 64}})
    current = _other_platform(plain)
    mode, environment_reasons = decide_mode(_environment(plain), current)
    assert mode == "compatible_reproduction" and len(environment_reasons) == 1
    report = _valid(
        replay_v2(plain.v2, plain_rerun, current=current, registry=registry, store=_local())
    )
    assert report.mode == "compatible_reproduction"
    assert report.reasons == (*environment_reasons, f"extension_changed({', '.join(key)})")
    assert report.verdict == "MATCH", report.differences
    assert report.bitwise_floats is True


def test_d5_a_changed_lock_and_a_changed_built_in_rerun_nothing(
    plain: Recorded, plain_rerun: RerunV2
) -> None:
    """Review F8 S2 (b): a changed built-in turns only an exact replay into a compatible
    reproduction; under a changed lock the archive is inspected (ADR 0007 D4), never rerun."""
    key = _used(plain, "unit_model")
    registry = edited_registry({key: {"self_sha256": "0" * 64}})
    current = dataclasses.replace(_environment(plain), lock_sha256="f" * 64)
    mode, environment_reasons = decide_mode(_environment(plain), current)
    assert mode == "inspected_archived_results" and len(environment_reasons) == 1
    report = _valid(
        replay_v2(plain.v2, plain_rerun, current=current, registry=registry, store=_local())
    )
    assert (report.mode, report.verdict) == ("inspected_archived_results", "NOT_RUN")
    assert report.reasons == (*environment_reasons, f"extension_changed({', '.join(key)})")
    assert report.differences == ()


@pytest.mark.parametrize("platform", ["recorded", "other"])
def test_d5_reasons_accumulate_in_step_order(
    gp: Recorded, gp_rerun: RerunV2, tmp_path: Path, platform: str
) -> None:
    """Review F8 S2 (c): an unknown policy (step 3), a missing used extension (step 5) and an
    absent referenced record (step 6) are all listed, in step order, and nothing is rerun. On the
    other registered platform step 4's reason sits between steps 3 and 5."""
    directory = tmp_path / "bundle"
    shutil.copytree(gp.v2, directory)
    unknown = "x-unknown-policy-v9"
    manifest, _ = bundle_v2.read_manifest(directory)
    edited = dataclasses.replace(manifest, numerical_policy_id=unknown)
    (directory / MANIFEST_NAME).write_bytes(canonical_json(edited.as_document()))
    assert bundle_v2.verify_bundle(directory).ok

    key = _used(gp, "data_source")
    absent = _sha_of(gp, REFERENCED[1])
    current = _environment(gp) if platform == "recorded" else _other_platform(gp)
    _, environment_reasons = decide_mode(_environment(gp), current)
    assert len(environment_reasons) == (0 if platform == "recorded" else 1)
    report = _valid(
        replay_v2(
            directory,
            gp_rerun,
            current=current,
            registry=edited_registry({key: None}),
            store=_local(frozenset({absent})),
        )
    )
    assert (report.mode, report.verdict) == ("inspected_archived_results", "NOT_RUN")
    assert report.reasons == (
        unknown_policy_reason(unknown),
        *environment_reasons,
        f"extension_unavailable({', '.join(key)})",
        f"data_unavailable({absent})",
    )
    assert report.differences == ()


# ------------------------------------------------------------------------------------- E-F8-6


def test_e_f8_6_the_usage_set_is_within_extensions_used(
    plain: Recorded, plain_rerun: RerunV2, baseline: ReplayReport
) -> None:
    assert plain_rerun.usage is not None
    declared = {row[:3] for row in plain.manifest.extensions_used}
    assert set(plain_rerun.usage) <= declared
    # Review F8 S3: the clause holds vacuously on this line. The factory's reruns are of v1
    # revisions, whose binder resolves nothing through the registry, so the usage set is empty;
    # the hidden-resolve control below is the evidence. Real v2 runs (F8-WO6) make it non-empty,
    # and this assertion then fails so the clause is judged for real.
    assert plain_rerun.usage == ()
    assert not any("extension_use_undeclared" in entry for entry in baseline.differences)


def test_e_f8_6_a_hidden_resolve_is_extension_use_undeclared(
    plain: Recorded, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    hidden = _unused(plain, "unit_model")
    session: Callable[..., Any] = revision_run.run_revision_session

    def resolving(*arguments: Any, **keywords: Any) -> Any:
        default_registry().resolve(hidden[0], hidden[1], hidden[2])
        return session(*arguments, **keywords)

    monkeypatch.setattr(revision_run, "run_revision_session", resolving)
    rerun = rerun_v2(plain.v2, tmp_path / "run")
    assert rerun.usage is not None and hidden in rerun.usage
    report = _valid(_replay(plain, rerun))
    assert report.verdict == "MISMATCH"
    assert report.differences == (f"extension_use_undeclared({hidden[0]}, {hidden[1]})",)


def test_e_f8_6_a_rerun_without_a_usage_set_does_not_match(
    plain: Recorded, plain_rerun: RerunV2
) -> None:
    rerun = Rerun(plain_rerun.artifacts, variable_kinds=plain_rerun.variable_kinds)
    report = _valid(_replay(plain, rerun))
    assert report.verdict == "MISMATCH"
    assert report.differences == (NO_USAGE,)


# ------------------------------------------------------------------------- the re-record tool


def test_rerecord_after_a_built_in_changed_replays_exactly_again(
    plain: Recorded, plain_rerun: RerunV2, baseline: ReplayReport, tmp_path: Path
) -> None:
    """A built-in changed on purpose: the old bundle replays as a compatible reproduction with
    `extension_changed`; the case re-recorded under the changed registry (its records from the
    bundle, the local store empty) replays as the baseline does, nothing changed."""
    key = _used(plain, "unit_model")
    registry = edited_registry({key: {"self_sha256": "0" * 64}})
    old = _replay(plain, plain_rerun, registry=registry)
    assert f"extension_changed({', '.join(key)})" in old.reasons

    with gate.pinned_threads():
        again = rerecord(
            plain.v2, tmp_path / "again", StoreStack(RecordStore.in_memory()), registry=registry
        )
    assert again.manifest.data_lock_sha256 == plain.manifest.data_lock_sha256
    assert again.manifest.structural_sha256 != plain.manifest.structural_sha256
    assert again.manifest.artifact_r0_sha256 == plain.manifest.artifact_r0_sha256
    report = _valid(
        replay_v2(
            again.v2,
            plain_rerun,
            current=_environment(plain),
            registry=registry,
            store=StoreStack(RecordStore.in_memory()),
        )
    )
    assert (report.mode, report.verdict, report.reasons) == (
        baseline.mode,
        "MATCH",
        baseline.reasons,
    ), report.differences
