"""V03 RC job record producer `scripts/v03_rc.py` (V03 spec §4 steps 15, 17a–17e; review F-V3).

Step 17c's record is written by the producer and read by `mr12_extras_v03` (the M07a script's
measure, which the S13 manifest calls): the round trip runs here at `HEAD` over a synthetic runner
summary, with a failed check and a missing record as controls. V03.A17's wheel reading and A19's
verdicts run on constructed inputs with one control per clause; A19's probe runs in-process with
`thermo/wilson_ig.py`'s checkout lookup switched off, as in a wheel.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import m07a_evidence_manifest as manifest  # noqa: E402
import v03_rc  # noqa: E402

from openflowsheet.thermo import wilson_ig  # noqa: E402


def _head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def _runner(tmp_path: Path, codes: dict[str, int]) -> tuple[Path, Path]:
    logs = tmp_path / "logs"
    logs.mkdir()
    lines = []
    for label, code in codes.items():
        lines.append(f"{label} exit {code} :: some command")
        (logs / f"{label}.log").write_text(f"output of {label}\n", encoding="utf-8")
    summary = tmp_path / "summary.txt"
    summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary, logs


def _step17c(tmp_path: Path, codes: dict[str, int]) -> tuple[int, dict[str, Any], Path]:
    head = _head()
    summary, logs = _runner(tmp_path, codes)
    rc = tmp_path / "artifacts" / "rc"
    argv = ["step17c", "--rc", str(rc), "--commit", head, "--summary", str(summary)]
    exit_code = v03_rc.main([*argv, "--logs", str(logs)])
    record = json.loads((rc / manifest.STEP17C_RECORD).read_text(encoding="utf-8"))
    return exit_code, record, rc


def _measure(tmp_path: Path, rc: Path | None) -> tuple[str, dict[str, Any]]:
    """The measure as the S13 manifest calls it, over `rc`'s record committed at `<C>/rc/`."""
    head = _head()
    evidence = tmp_path / "evidence"
    committed = evidence / head / "rc"
    committed.mkdir(parents=True)
    if rc is not None:
        (committed / "step17").mkdir()
        shutil.copy(rc / manifest.STEP17C_RECORD, committed / manifest.STEP17C_RECORD)
    inputs = manifest.Inputs(commit=head, tests=None, evidence=evidence)  # type: ignore[arg-type]
    return manifest.MEASURES["mr12_extras_v03"](inputs)


ALL_PASS = {"step17c-coolprop": 0, "step17c-lca": 0}


def test_step17c_record_round_trips_through_the_measure(tmp_path: Path) -> None:
    exit_code, record, rc = _step17c(tmp_path, ALL_PASS)
    assert exit_code == 0
    assert record["passed"] is True
    assert record["provenance"]["commit"] == _head()
    ids = [check["id"] for check in record["checks"]]
    commands = [audit["check"] for audit in manifest.MR12_AUDITS_V03.values()]
    assert ids == [*commands, "a22.17c.mr12_extras_v03"]
    assert record["checks"][-1]["measure"]["new_since_v0_2_0"] == ["coolprop", "lca"]
    result, value = _measure(tmp_path, rc)
    assert result == "pass", value
    assert value["new_since_v0_2_0"] == ["coolprop", "lca"]


@pytest.mark.parametrize("label", sorted(ALL_PASS))
def test_step17c_a_failed_check_fails_the_record_and_the_measure(
    tmp_path: Path, label: str
) -> None:
    exit_code, record, rc = _step17c(tmp_path, {**ALL_PASS, label: 1})
    assert exit_code == 1
    assert record["passed"] is False
    assert record["checks"][-1]["result"] == "fail"
    assert _measure(tmp_path, rc)[0] == "fail"


def test_step17c_an_absent_command_fails(tmp_path: Path) -> None:
    exit_code, record, _ = _step17c(tmp_path, {"step17c-coolprop": 0})
    assert exit_code == 1
    assert [check["result"] for check in record["checks"]] == ["pass", "fail", "fail"]


def test_a_missing_17c_record_fails_the_measure(tmp_path: Path) -> None:
    result, value = _measure(tmp_path, None)
    assert result == "fail"
    assert all(entry["check_result"] is None for entry in value["extras"].values())


def test_the_17c_verdict_needs_both_extras_and_their_checks() -> None:
    passing = {
        "new_since_v0_2_0": ["coolprop", "lca"],
        "extras": {"coolprop": {"check_result": "pass"}, "lca": {"check_result": "pass"}},
    }
    assert v03_rc.mr12_v03_check("pass", passing)
    assert not v03_rc.mr12_v03_check("fail", passing)
    assert not v03_rc.mr12_v03_check("pass", {**passing, "new_since_v0_2_0": ["coolprop"]})
    lca_failed = {**passing, "extras": {**passing["extras"], "lca": {"check_result": "fail"}}}
    assert not v03_rc.mr12_v03_check("pass", lca_failed)


def test_the_a48_verdict() -> None:
    assert v03_rc.a48_check("pass", {"unverified_primary_ranges": 0})
    assert not v03_rc.a48_check("fail", {"unverified_primary_ranges": 0})
    assert not v03_rc.a48_check("pass", {"unverified_primary_ranges": 1})


def test_step15_reads_the_carry_line(tmp_path: Path) -> None:
    head = _head()
    summary, logs = _runner(tmp_path, {"step15-carry": 0, "step15-check": 0, "step15-replay": 0})
    (logs / "step15-carry.log").write_text("RC step 15: the journey at J carried\n", "utf-8")
    rc = tmp_path / "rc"
    argv = ["step15", "--rc", str(rc), "--commit", head, "--summary", str(summary)]
    assert v03_rc.main([*argv, "--logs", str(logs), "--journey", "2d945b5d"]) == 0
    (logs / "step15-carry.log").write_text("RC step 15: the journey at J: JOURNEY_RERUN\n", "utf-8")
    assert v03_rc.main([*argv, "--logs", str(logs), "--journey", "2d945b5d"]) == 1


def test_the_producer_refuses_another_commit(tmp_path: Path) -> None:
    summary, logs = _runner(tmp_path, ALL_PASS)
    argv = ["step17c", "--rc", str(tmp_path), "--commit", "0" * 40, "--summary", str(summary)]
    assert v03_rc.main([*argv, "--logs", str(logs)]) == 2


# -- step 17d's node reading ---------------------------------------------------------------------

JUNIT = """<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest">
<testcase classname="tests.test_e01_integration" name="test_a33_a34_p2[0]"/>
<testcase classname="tests.test_e01_integration" name="test_a36_dormant"><skipped/></testcase>
<testcase classname="tests.test_e01_b_nlp" name="test_a35_m03s"><failure/></testcase>
</testsuite></testsuites>"""


def test_junit_outcomes_and_citations(tmp_path: Path) -> None:
    junit = tmp_path / "n.xml"
    junit.write_text(JUNIT, encoding="utf-8")
    outcomes = v03_rc.junit_outcomes(junit)
    assert outcomes == {
        "tests/test_e01_integration.py::test_a33_a34_p2[0]": "passed",
        "tests/test_e01_integration.py::test_a36_dormant": "skipped",
        "tests/test_e01_b_nlp.py::test_a35_m03s": "failed",
    }
    assert v03_rc.totals(outcomes) == {"passed": 1, "failed": 1, "skipped": 1}
    import e01_evidence_manifest

    cited = e01_evidence_manifest.cited
    assert list(v03_rc.cited_nodes(outcomes, "A34", cited)) == [
        "tests/test_e01_integration.py::test_a33_a34_p2[0]"
    ]
    assert v03_rc.cited_nodes(outcomes, "A24", cited) == {}


# -- V03.A17 over a wheel's members --------------------------------------------------------------

SHIPS = {"benchmarks/s10/records.yaml": v03_rc.sha256(b"records")}
E01 = {"openflowsheet/_data/assessment/cost/chains.json": v03_rc.sha256(b"chains")}
ONLY = ["benchmarks/s10/fit-report.json"]
MEMBERS = {
    "openflowsheet/_data/benchmarks/s10/records.yaml": b"records",
    "openflowsheet/_data/assessment/cost/chains.json": b"chains",
    "openflowsheet/__init__.py": b"",
}


def _a17(members: dict[str, bytes]) -> bool:
    found = v03_rc.wheel_findings(members, SHIPS, E01, ONLY)
    return (
        all(row["ok"] for row in found["ship_set"].values())
        and all(row["ok"] for row in found["e01_data"].values())
        and not found["repository_only_present"]
    )


def test_a17_control_and_its_three_failures() -> None:
    assert _a17(MEMBERS)
    assert not _a17({**MEMBERS, "openflowsheet/_data/benchmarks/s10/records.yaml": b"edited"})
    assert not _a17({k: v for k, v in MEMBERS.items() if "chains" not in k})
    assert not _a17({**MEMBERS, "openflowsheet/_data/benchmarks/s10/fit-report.json": b"{}"})


# -- V03.A19 ---------------------------------------------------------------------------------------

RECORDS_SHA256 = v03_rc.sha256((REPO_ROOT / wilson_ig.RECORDS_PATH).read_bytes())


def test_a19_states_are_s10s_real_reference_states() -> None:
    reference = yaml.safe_load(
        (REPO_ROOT / "benchmarks/s10/reference_values_real.yaml").read_text(encoding="utf-8")
    )
    for name in ("RE1", "RE2", "RE3"):
        state = reference["closed_form"]["evaluate_phase"][name]["state"]
        assert v03_rc.A19_STATES[name] == (tuple(state["n"]), state["T"], state["P"])


def test_exact_is_bitwise() -> None:
    assert v03_rc.exact({"b": 0.1, "a": (1.0, [2.5])}) == {
        "a": ["0x1.0000000000000p+0", ["0x1.4000000000000p+1"]],
        "b": (0.1).hex(),
    }
    assert v03_rc.exact(0.1) != v03_rc.exact(0.1 + 2**-56 * 8)


@pytest.fixture
def as_in_a_wheel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wilson_ig, "_checkout_records", lambda: None)


def test_a19_probe_in_process_as_in_a_wheel(as_in_a_wheel: None) -> None:
    """The probe's (a)–(d) hold with the checkout lookup off; (c) equals the checkout's answers."""
    installed = v03_rc.probe(checkout=False)
    checkout = {
        "c": v03_rc.answers(wilson_ig.WilsonIdealGasProvider(REPO_ROOT / wilson_ig.RECORDS_PATH))
    }
    found = v03_rc.a19_findings(installed, checkout, RECORDS_SHA256)
    assert found["site_packages"] is False  # a checkout, not an installed wheel
    assert {key: found[key] for key in "abcd"} == dict.fromkeys("abcd", True), installed
    assert sorted(installed["c"]) == sorted(v03_rc.A19_STATES)


def test_a19_probe_in_checkout() -> None:
    found = v03_rc.probe(checkout=True)
    assert sorted(found["c"]) == sorted(v03_rc.A19_STATES)
    assert found["checkout_records"]


def _installed() -> dict[str, Any]:
    return {
        "module_file": "/v/lib/python3.13/site-packages/openflowsheet/__init__.py",
        "checkout_records": "",
        "a": {"is_file": True, "sha256": RECORDS_SHA256},
        "b": {
            "provider_id": "wilson-ig-v2",
            "data_sha256": RECORDS_SHA256,
            "certificate_describes_equal": True,
        },
        "c": {"RE1": {"x": "0x1p+0"}},
        "d": {"type": "RecordError", "message": "records_missing: from a source checkout only"},
    }


@pytest.mark.parametrize(
    ("clause", "edit"),
    [
        ("site_packages", {"module_file": "/repo/src/openflowsheet/__init__.py"}),
        ("a", {"a": {"is_file": True, "sha256": "0" * 64}}),
        ("b", {"b": {"provider_id": "wilson-ig-v1"}}),
        ("c", {"c": {"RE1": {"x": "0x1.0000000000001p+0"}}}),
        ("c", {"c": {}}),
        ("d", {"d": {"type": "KeyError", "message": "records_missing: x"}}),
        ("d", {"d": {"type": None, "message": "no exception"}}),
    ],
)
def test_a19_each_clause_has_a_failing_control(clause: str, edit: dict[str, Any]) -> None:
    checkout = {"c": _installed()["c"]}
    assert all(v03_rc.a19_findings(_installed(), checkout, RECORDS_SHA256).values())
    found = v03_rc.a19_findings({**_installed(), **edit}, checkout, RECORDS_SHA256)
    assert found[clause] is False
