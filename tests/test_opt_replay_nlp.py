"""OPT WO-6 gate G13 (design §4.9, §6; §9.5's OPT-A3 extension), the audited half: an optimisation
record replays to `MATCH`, and the controls fail as they must.

- OPT-A2's record (3 starts, all verified) and OPT-A3's (V1 on the phase-boundary form, B
  recomputed): `replay_optimization(rerun=True)` → `MATCH`, no difference, every bundle re-run.
- One byte of a start's `candidate-revision.json` changed → integrity failure (`tampered`), not
  re-run (`NOT_RUN`).
- A verification float (V6's objective) moved beyond the registered comparison policy, with the
  manifest's hash re-made so that integrity passes → `MISMATCH` naming that member; on OPT-A3 the
  boundary form's rcond₁ likewise.
- Without `rerun`: `inspected_archived_results`, `NOT_RUN`.

The committed fixture that the default environment (and the aarch64 CI leg) replays without Ipopt
is `tests/fixtures/opt/replay/OPT-A2`, written by `OPT_WRITE_REPLAY_FIXTURE=<dir>` on this test
(`tests/test_opt_replay.py` replays it).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from openflowsheet.application.policies import DEFAULT_POLICY_ID, resolve_policy
from openflowsheet.canonical import canonical_json
from openflowsheet.studies.nlp.replay import MANIFEST, replay_optimization
from openflowsheet.studies.nlp.revision import OptimizationOutcome, optimize_revision
from openflowsheet.verify.certificate import CheckPolicy

pytestmark = pytest.mark.nlp

OPT = Path(__file__).resolve().parents[1] / "benchmarks" / "opt"
EXPECTED = json.loads((OPT / "expected.json").read_bytes())
POLICY = resolve_policy(DEFAULT_POLICY_ID, "revision_eo")
assert POLICY is not None


@pytest.fixture(scope="module")
def records(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("opt-replay")


@cache
def _run(case: str, directory: Path) -> OptimizationOutcome:
    flowsheet = EXPECTED["flowsheets"][case]
    document = json.loads((OPT / "flowsheets" / f"{flowsheet}.json").read_bytes())
    request = json.loads((OPT / "requests" / f"{case}.json").read_bytes())
    return optimize_revision(
        document,
        request,
        directory=directory / case,
        solve_policy=POLICY,
        check_policy=CheckPolicy(),
    )


def _copy(case: str, records: Path, name: str) -> Path:
    outcome = _run(case, records)
    assert outcome.record_dir is not None
    target = records / f"{case}-{name}"
    shutil.copytree(outcome.record_dir, target)
    return target


def _rehash(record: Path, relative: str) -> None:
    """Re-make `relative`'s hash in the manifest, so that integrity passes over an edit."""
    manifest = json.loads((record / MANIFEST).read_bytes())
    payload = (record / relative).read_bytes()
    manifest["members"][relative] = hashlib.sha256(payload).hexdigest()
    (record / MANIFEST).write_bytes(canonical_json(manifest))


@pytest.mark.parametrize("case", ["OPT-A2", "OPT-A3"])
def test_g13_a_record_replays_to_match(case: str, records: Path, tmp_path: Path) -> None:
    record = _copy(case, records, "match")
    report = replay_optimization(record, rerun=True, rerun_directory=tmp_path / "rerun")
    assert report.integrity.ok
    assert report.differences == (), report.differences
    assert (report.mode, report.verdict) in {
        ("exact_replay", "MATCH"),
        ("compatible_reproduction", "MATCH"),
    }, report.as_document()
    inspected = replay_optimization(record, rerun=False, rerun_directory=tmp_path / "unused")
    assert (inspected.mode, inspected.verdict) == ("inspected_archived_results", "NOT_RUN")
    target = os.environ.get("OPT_WRITE_REPLAY_FIXTURE")
    if target and case == "OPT-A2":
        destination = Path(target) / case
        shutil.rmtree(destination, ignore_errors=True)
        shutil.copytree(record, destination)


def test_g13_one_tampered_byte_is_an_integrity_failure(records: Path, tmp_path: Path) -> None:
    record = _copy("OPT-A2", records, "tampered")
    member = record / "starts" / "0" / "candidate-revision.json"
    payload = bytearray(member.read_bytes())
    payload[len(payload) // 2] ^= 0x01
    member.write_bytes(bytes(payload))
    report = replay_optimization(record, rerun=True, rerun_directory=tmp_path / "rerun")
    assert not report.integrity.ok
    assert report.integrity.tampered == ("starts/0/candidate-revision.json",)
    assert (report.mode, report.verdict) == ("inspected_archived_results", "NOT_RUN")


def _edit(record: Path, relative: str, edit: Any) -> None:
    document = json.loads((record / relative).read_bytes())
    edit(document)
    (record / relative).write_bytes(canonical_json(document))
    _rehash(record, relative)


def test_g13_an_edited_verification_float_is_a_mismatch(records: Path, tmp_path: Path) -> None:
    record = _copy("OPT-A2", records, "edited")
    relative = "starts/1/verification.json"

    def moved(document: dict[str, Any]) -> None:
        document["objective"] = document["objective"] * (1 + 1e-6)

    _edit(record, relative, moved)
    report = replay_optimization(record, rerun=True, rerun_directory=tmp_path / "rerun")
    assert report.integrity.ok
    assert report.verdict == "MISMATCH"
    assert [d for d in report.differences if d.startswith(relative)], report.differences


def test_g13_opt_a3_an_edited_boundary_rcond_is_a_mismatch(records: Path, tmp_path: Path) -> None:
    """§9.5: the boundary form's rcond₁ (V1's detail) moved beyond the policy → `MISMATCH`."""
    record = _copy("OPT-A3", records, "rcond")
    relative = "starts/0/verification.json"
    found: list[str] = []

    def moved(node: Any, path: str = "") -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if "rcond" in key and isinstance(value, float):
                    node[key] = value * 1.5
                    found.append(f"{path}/{key}")
                else:
                    moved(value, f"{path}/{key}")
        elif isinstance(node, list):
            for index, item in enumerate(node):
                moved(item, f"{path}/{index}")

    _edit(record, relative, moved)
    assert found, "OPT-A3's verification records no rcond"
    report = replay_optimization(record, rerun=True, rerun_directory=tmp_path / "rerun")
    assert report.integrity.ok
    assert report.verdict == "MISMATCH"
    assert [d for d in report.differences if d.startswith(relative)], report.differences
