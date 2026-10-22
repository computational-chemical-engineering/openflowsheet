"""C9 / WO-C9-1: W27 registration version 2 behind the version switch.

Normative text: `docs/derivations/W27-registration-v2.md` (W27v2-R01, R04…R09; the states of §5.2;
assertions W27v2-A19…A22). Expected values are read from `registration_v2.json`, written by the
design lane's generator, which this file runs only as a subprocess (`--check`).

Held-out discipline (C2 SPLIT-R08…R10): the tests that read the archive's case facts or the
committed coverage rows filter both to `split.json#/development` before classifying anything, and
print no row or count. No version 2 record is written to a committed path.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from benchmarks.m06.w27 import coverage, facts, registration, snapshot

ROOT = registration.ROOT
V2 = registration.load_v2()
STATES = V2["states"]
SPLIT_JSON = registration.RECORDS / "split.json"
GENERATOR_V2 = ROOT / "docs" / "derivations" / "scripts" / "w27_registration_v2.py"


def provider_table(name: str) -> dict[str, str]:
    """§5.2's provider tables, each with `#/test_provider_methods` added (W27-A02)."""
    tables = {
        "v1": registration.provider_methods(1),
        "v2": registration.provider_methods(2),
        "v1+lib": {**registration.provider_methods(1), "pr-lib-v1": "cubic_pr"},
    }
    return {**tables[name], **V2["test_provider_methods"]}


def triples(row: dict[str, Any]) -> list[list[Any]]:
    return [[r["kind"], r["subject"], r["detail"]] for r in row["reasons"]]


# =================================================================================================
# W27v2-A19: every registered state through the production classifier
# =================================================================================================


@pytest.mark.parametrize("state", STATES, ids=[s["id"] for s in STATES])
def test_a19_registered_state(state: dict[str, Any]) -> None:
    snap = V2["snapshots"][state["snapshot"]]
    case = V2["cases"][state["case"]]
    table = provider_table(state["provider_table"])
    version = state["registration_version"]
    expected = state["expected"]
    try:
        coverage.check_snapshot(snap, {"cases": [case]}, table, registration_version=version)
    except coverage.RefusalError as refusal:
        assert "refusal" in expected, f"{state['id']}: unexpected refusal {refusal}"
        assert str(refusal) == expected["refusal"]
        return
    assert "refusal" not in expected, f"{state['id']}: expected a refusal"
    row = coverage.classify_case(case, snap, table, registration_version=version)
    assert row["class"] == expected["class"]
    assert row["units_judged_on"] == expected["units_judged_on"]
    assert triples(row) == expected["reasons"]


def test_a19_the_states_are_the_registered_seventeen() -> None:
    assert [s["id"] for s in STATES] == [f"W27v2-A{n:02d}" for n in range(1, 18)]


def test_version_switch_refuses_other_versions() -> None:
    snap = V2["snapshots"]["S1"]
    case = V2["cases"]["H2"]
    for version in (0, 3, True):
        with pytest.raises(ValueError, match="not 1 or 2"):
            coverage.check_snapshot(snap, {"cases": [case]}, registration_version=version)
        with pytest.raises(ValueError, match="not 1 or 2"):
            coverage.classify_case(case, snap, registration_version=version)
        with pytest.raises(ValueError, match="not 1 or 2"):
            coverage.classify({"cases": [case]}, snap, registration_version=version)
        with pytest.raises(ValueError, match="not 1 or 2"):
            coverage.coverage_document({"cases": [case]}, snap, registration_version=version)
    with pytest.raises(ValueError, match="not 1 or 2"):
        registration.provider_methods(3)


def test_tables_are_read_from_registration_v2() -> None:
    assert registration.provider_methods(2) == V2["tables"]["provider_methods"]
    assert registration.provider_methods() == registration.provider_methods(1)
    assert registration.case_distinct() == {
        k: frozenset(v["distinct_from"]) for k, v in V2["tables"]["case_distinct"].items()
    }


def test_v2_defaults_to_its_own_provider_table() -> None:
    """Without an explicit table, version 2 judges S2 with W27v2-R02's (W27v2-A02)."""
    snap = V2["snapshots"]["S2"]
    case = V2["cases"]["H2"]
    coverage.check_snapshot(snap, {"cases": [case]}, registration_version=2)
    row = coverage.classify_case(case, snap, registration_version=2)
    assert (row["class"], row["units_judged_on"]) == ("CANDIDATE", "pr-c1-v1")
    with pytest.raises(coverage.RefusalError, match=r"unregistered provider ids \['pr-lib-v1'\]"):
        coverage.check_snapshot(snap, {"cases": [case]})


# =================================================================================================
# W27v2-A20: version 2 equals version 1 on the development rows (W27v2-R10)
# =================================================================================================


def test_a20_development_rows_equal_the_committed_rows() -> None:
    development = set(json.loads(SPLIT_JSON.read_bytes())["development"]["case_ids"])
    every = facts.load_facts()
    dev_facts = {**every, "cases": [c for c in every["cases"] if c["case_id"] in development]}
    committed = json.loads(registration.COVERAGE_JSON.read_bytes())
    committed_rows = {r["case_id"]: r for r in committed["rows"] if r["case_id"] in development}
    del every, committed["rows"]
    rows = coverage.classify(dev_facts, committed["snapshot"], registration_version=2)["rows"]
    assert {r["case_id"] for r in rows} == development
    assert set(committed_rows) == development
    differing = [r["case_id"] for r in rows if r != committed_rows[r["case_id"]]]
    assert differing == []


# =================================================================================================
# W27v2-A21: the version 2 record
# =================================================================================================


def test_a21_the_version_2_record() -> None:
    snap = V2["snapshots"]["S2"]
    case_facts = {"cases": [V2["cases"]["H2"]]}
    document = coverage.coverage_document(case_facts, snap, registration_version=2)
    v2_sha = hashlib.sha256(registration.REGISTRATION_V2_JSON.read_bytes()).hexdigest()
    v1_sha = hashlib.sha256(registration.REGISTRATION_JSON.read_bytes()).hexdigest()
    assert document["schema"] == "w27-coverage-v2"
    assert document["registration_version"] == 2
    assert document["registration_v2_sha256"] == v2_sha
    assert document["registration_sha256"] == v1_sha
    assert document["snapshot"] == snap
    assert document["snapshot_sha256"] == registration.sha256_bytes(registration.dump(snap))
    assert document["case_facts_sha256"] == registration.sha256_bytes(facts.dump_facts(case_facts))
    assert [r["units_judged_on"] for r in document["rows"]] == ["pr-c1-v1"]
    v1_members = set(json.loads(registration.COVERAGE_JSON.read_bytes()))
    assert set(document) == v1_members | {"registration_version", "registration_v2_sha256"}
    v1_document = coverage.coverage_document(case_facts, V2["snapshots"]["S1"])
    assert set(v1_document) == v1_members
    assert v1_document["schema"] == "w27-coverage-v1"


# =================================================================================================
# W27v2-A22: the CLI refuses a version 2 run onto no path or the committed path
# =================================================================================================


def _no_classification(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the refusal must come before any snapshot or classification")

    for module, name in (
        (snapshot, "build_snapshot"),
        (facts, "load_facts"),
        (coverage, "check_snapshot"),
        (coverage, "classify_case"),
        (coverage, "_check_snapshot_v2"),
        (coverage, "_classify_case_v2"),
    ):
        monkeypatch.setattr(module, name, forbidden)


@pytest.mark.parametrize("out", ["absent", "committed", "committed-relative"])
def test_a22_cli_refuses_v2_onto_the_committed_record(
    out: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    before = registration.COVERAGE_JSON.read_bytes()
    _no_classification(monkeypatch)
    argv = ["--registration-version", "2"]
    if out == "committed":
        argv += ["--out", str(registration.COVERAGE_JSON)]
    elif out == "committed-relative":
        monkeypatch.chdir(tmp_path)
        argv += ["--out", os.path.relpath(registration.COVERAGE_JSON, tmp_path)]
    assert coverage.main(argv) == 2
    assert "SPLIT-R10" in capsys.readouterr().err
    assert registration.COVERAGE_JSON.read_bytes() == before
    assert list(tmp_path.iterdir()) == []


def test_cli_writes_v2_to_another_path_and_v1_to_its_default(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Positive controls on the synthetic H2 case only (no archive case is classified). G14 needs
    450 rows, so one row gives exit 1 after the record is written."""
    monkeypatch.setattr(facts, "load_facts", lambda: {"cases": [V2["cases"]["H2"]]})
    for name in ("S1", "S2"):
        (tmp_path / f"{name}.json").write_bytes(registration.dump(V2["snapshots"][name]))
    out_v2 = tmp_path / "heldout" / "v2.json"
    out_v2.parent.mkdir()
    argv = ["--registration-version", "2", "--snapshot", str(tmp_path / "S2.json")]
    assert coverage.main([*argv, "--out", str(out_v2)]) == 1
    written = json.loads(out_v2.read_bytes())
    assert (written["schema"], written["registration_version"]) == ("w27-coverage-v2", 2)
    assert written["rows"][0]["units_judged_on"] == "pr-c1-v1"
    default_v1 = tmp_path / "coverage.json"
    monkeypatch.setattr(registration, "COVERAGE_JSON", default_v1)
    assert coverage.main(["--snapshot", str(tmp_path / "S1.json")]) == 1
    assert json.loads(default_v1.read_bytes())["schema"] == "w27-coverage-v1"
    capsys.readouterr()


# =================================================================================================
# The generator's committed output is current (GC-V2-1…8)
# =================================================================================================


def test_generator_check() -> None:
    result = subprocess.run(
        [sys.executable, str(GENERATOR_V2), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-2000:]
