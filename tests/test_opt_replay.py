"""OPT WO-6 gate G13, the default-environment half (design §4.9, §6): the committed OPT-A2 record
(`tests/fixtures/opt/replay/OPT-A2`, written on x86-64 in the audited environment by
`tests/test_opt_replay_nlp.py`) replays to `MATCH` here — on the aarch64 CI leg too — with no
Ipopt and no `nlp` extra: replay re-checks the certified chain (production re-solves, V1–V7,
the classification), never the search. And it imports neither Pyomo nor cyipopt (G11).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from openflowsheet.studies.nlp.replay import (
    MANIFEST,
    is_optimization_record,
    record_integrity,
    replay_optimization,
)

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests" / "fixtures" / "opt" / "replay" / "OPT-A2"


def test_g13_the_committed_record_is_an_intact_optimization_record() -> None:
    assert is_optimization_record(FIXTURE)
    assert not is_optimization_record(FIXTURE / "starts" / "0" / "start")
    assert record_integrity(FIXTURE).ok
    manifest = json.loads((FIXTURE / MANIFEST).read_bytes())
    assert manifest["format"] == "openflowsheet-optimization-v1"
    size = sum(path.stat().st_size for path in FIXTURE.rglob("*") if path.is_file())
    assert size <= 2_000_000


def test_g13_the_committed_record_replays_to_match_without_ipopt(tmp_path: Path) -> None:
    record = tmp_path / "OPT-A2"
    shutil.copytree(FIXTURE, record)
    report = replay_optimization(record, rerun=True, rerun_directory=tmp_path / "rerun")
    assert report.integrity.ok
    assert report.differences == (), report.differences
    assert report.verdict == "MATCH", report.as_document()
    assert report.mode in ("exact_replay", "compatible_reproduction")


def test_g13_an_unexpected_file_fails_integrity(tmp_path: Path) -> None:
    record = tmp_path / "OPT-A2"
    shutil.copytree(FIXTURE, record)
    (record / "starts" / "0" / "extra.json").write_bytes(b"{}")
    report = replay_optimization(record, rerun=True, rerun_directory=tmp_path / "rerun")
    assert report.integrity.unexpected == ("starts/0/extra.json",)
    assert (report.mode, report.verdict) == ("inspected_archived_results", "NOT_RUN")


_NO_NLP_IMPORT = """
import sys, tempfile
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from openflowsheet.studies.nlp.replay import replay_optimization
import shutil
with tempfile.TemporaryDirectory() as work:
    record = Path(work) / "r"
    shutil.copytree(sys.argv[2], record)
    report = replay_optimization(record, rerun=True, rerun_directory=Path(work) / "x")
print(report.verdict, sorted(m for m in ("pyomo", "cyipopt") if m in sys.modules))
"""


def test_g11_replay_imports_neither_pyomo_nor_cyipopt() -> None:
    found = subprocess.run(
        [sys.executable, "-c", _NO_NLP_IMPORT, str(REPO / "src"), str(FIXTURE)],
        capture_output=True,
        text=True,
        check=True,
        timeout=600,
    )
    assert found.stdout.split("\n")[-2] == "MATCH []", found.stdout[-2000:]


# -- §4.9's dispatch: `reproduce` and the CLI's `replay` ------------------------------------------


def test_g13_reproduce_imports_and_replays_an_optimization_record(tmp_path: Path) -> None:
    """`LocalApplication.reproduce` imports the record whole (its `starts/` tree), registers it as
    a `replay_bundle` with its manifest as member, and the `reproduce` job dispatches on the
    manifest's format: `MATCH`, the re-run bundles artifacts of the job, the report its one
    output. Without `rerun`: `inspected_archived_results`."""
    from openflowsheet.application.local import LocalApplication
    from openflowsheet.application.types import ReplayPolicy

    with LocalApplication.create(tmp_path / "project", project_id="opt-replay") as app:
        report = app.reproduce(FIXTURE, ReplayPolicy(rerun=True))
        assert report.differences == (), report.differences
        assert report.verdict == "MATCH", report.as_document()
        imported = app.store.artifact("import-000001:bundle")
        assert imported is not None and imported.kind == "replay_bundle"
        copy = app.files_root / imported.relpath
        assert record_integrity(copy).ok
        assert [row.name for row in app.store.artifact_children(imported.artifact_id)] == [MANIFEST]
        viewed = app.get_artifact(imported.artifact_id)
        recorded = json.loads((FIXTURE / MANIFEST).read_bytes())
        assert viewed.value["manifest"]["format"] == recorded["format"]
        assert viewed.value["manifest"]["members"] == recorded["members"]
        reruns = sorted(
            row.artifact_id
            for row in app.store.artifacts_of_kind("replay_bundle")
            if ":rerun/" in row.artifact_id
        )
        starts = sorted(path.name for path in (FIXTURE / "starts").iterdir())
        assert len(reruns) == 2 * len(starts), reruns
        inspected = app.reproduce(FIXTURE, ReplayPolicy(rerun=False))
        assert (inspected.mode, inspected.verdict) == ("inspected_archived_results", "NOT_RUN")


def test_g13_the_cli_replays_an_optimization_record(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from openflowsheet.application.cli import main

    record = tmp_path / "OPT-A2"
    shutil.copytree(FIXTURE, record)
    assert main(["replay", str(record), "--rerun", "--json"]) == 0
    document = json.loads(capsys.readouterr().out)
    assert (document["verdict"], document["differences"]) == ("MATCH", [])
    assert main(["replay", str(record)]) == 0
    assert "inspected_archived_results" in capsys.readouterr().out
    (record / "starts" / "0" / "candidate-revision.json").write_bytes(b"{}")
    assert main(["replay", str(record), "--rerun", "--json"]) == 1
    document = json.loads(capsys.readouterr().out)
    assert document["integrity"]["tampered"] == ["starts/0/candidate-revision.json"]
