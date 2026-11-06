"""RP §3.6 and §6.7: the scripts of the 0.4 line's `local:` rc items (ADR 0055 WO-R6).

`scripts/wheel_data_check.py` (item `WHEEL-DATA`) carries V03.A17's and V03.A19's checks out of
the legacy `scripts/v03_rc.py` with their controls: the functions are 17e's, so the controls are
`tests/test_v03_rc.py`'s, re-run against the standing owner. `scripts/e01_evidence_manifest.py
--a48-release-check` (item `E01-A48`) exits 0 iff `a48_release_check()` returns `pass`.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import e01_evidence_manifest  # noqa: E402
import v03_rc  # noqa: E402
import wheel_data_check  # noqa: E402

from openflowsheet.thermo import wilson_ig  # noqa: E402

# -- V03.A17 over a wheel's members --------------------------------------------------------------

SHIPS = {"benchmarks/s10/records.yaml": wheel_data_check.sha256(b"records")}
E01 = {"openflowsheet/_data/assessment/cost/chains.json": wheel_data_check.sha256(b"chains")}
ONLY = ["benchmarks/s10/fit-report.json"]
MEMBERS = {
    "openflowsheet/_data/benchmarks/s10/records.yaml": b"records",
    "openflowsheet/_data/assessment/cost/chains.json": b"chains",
    "openflowsheet/__init__.py": b"",
}


def _a17(members: dict[str, bytes]) -> bool:
    found = wheel_data_check.wheel_findings(members, SHIPS, E01, ONLY)
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


def test_the_moved_functions_judge_as_17e_did() -> None:
    """The standing owner decides exactly as the legacy step 17e on the same inputs."""
    for members in (
        MEMBERS,
        {**MEMBERS, "openflowsheet/_data/benchmarks/s10/fit-report.json": b""},
    ):
        assert wheel_data_check.wheel_findings(members, SHIPS, E01, ONLY) == v03_rc.wheel_findings(
            members, SHIPS, E01, ONLY
        )
    assert wheel_data_check.A19_STATES == v03_rc.A19_STATES
    assert wheel_data_check.a19_findings(_installed(), {"c": {}}, RECORDS_SHA256) == (
        v03_rc.a19_findings(_installed(), {"c": {}}, RECORDS_SHA256)
    )


# -- V03.A19 ---------------------------------------------------------------------------------------

RECORDS_SHA256 = wheel_data_check.sha256((REPO_ROOT / wilson_ig.RECORDS_PATH).read_bytes())


def test_a19_states_are_s10s_real_reference_states() -> None:
    reference = yaml.safe_load(
        (REPO_ROOT / "benchmarks/s10/reference_values_real.yaml").read_text(encoding="utf-8")
    )
    for name in ("RE1", "RE2", "RE3"):
        state = reference["closed_form"]["evaluate_phase"][name]["state"]
        assert wheel_data_check.A19_STATES[name] == (tuple(state["n"]), state["T"], state["P"])


def test_exact_is_bitwise() -> None:
    assert wheel_data_check.exact({"b": 0.1, "a": (1.0, [2.5])}) == {
        "a": ["0x1.0000000000000p+0", ["0x1.4000000000000p+1"]],
        "b": (0.1).hex(),
    }
    assert wheel_data_check.exact(0.1) != wheel_data_check.exact(0.1 + 2**-56 * 8)


def test_a19_probe_in_process_as_in_a_wheel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wilson_ig, "_checkout_records", lambda: None)
    installed = wheel_data_check.probe(checkout=False)
    checkout = {
        "c": wheel_data_check.answers(
            wilson_ig.WilsonIdealGasProvider(REPO_ROOT / wilson_ig.RECORDS_PATH)
        )
    }
    found = wheel_data_check.a19_findings(installed, checkout, RECORDS_SHA256)
    assert found["site_packages"] is False  # a checkout, not an installed wheel
    assert {key: found[key] for key in "abcd"} == dict.fromkeys("abcd", True), installed


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
    assert all(wheel_data_check.a19_findings(_installed(), checkout, RECORDS_SHA256).values())
    found = wheel_data_check.a19_findings({**_installed(), **edit}, checkout, RECORDS_SHA256)
    assert found[clause] is False


def test_the_item_refuses_a_checkout_not_at_c() -> None:
    done = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "wheel_data_check.py"), "--commit", "0" * 40],
        capture_output=True,
        text=True,
    )
    assert done.returncode == 2
    assert "not at " + "0" * 40 in done.stderr


# -- E01-A48 ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(("result", "code"), [("pass", 0), ("fail", 1)])
def test_a48_release_check_exits_on_the_result(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], result: str, code: int
) -> None:
    monkeypatch.setattr(
        e01_evidence_manifest, "a48_release_check", lambda: (result, {"unverified": 0})
    )
    monkeypatch.setattr(sys, "argv", ["e01_evidence_manifest.py", "--a48-release-check"])
    assert e01_evidence_manifest.main() == code
    assert capsys.readouterr().out.splitlines()[-1] == f"a48_release_check: {result}"


def test_a48_release_check_at_this_checkout() -> None:
    done = subprocess.run(
        [sys.executable, "scripts/e01_evidence_manifest.py", "--a48-release-check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(REPO_ROOT / "src"), "PATH": "/usr/bin:/bin"},
    )
    assert (done.returncode, done.stdout.splitlines()[-1]) == (0, "a48_release_check: pass")
