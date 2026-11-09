"""X05.A13-A17 (ADR 0069 §6.2): an installed package replays its own bundles, end to end.

The installed package is the checkout's `src/openflowsheet` copied (links followed, so the packaged
lock is its bytes) into a scratch `site-packages` beneath a **stray** `requirements.lock` — the
packaged lock plus one comment line, so it would itself verify and only reading it could give its
hash. The **shadow** is a directory, first on `sys.path`, holding only a `numpy` dist-info at
another version: `importlib.metadata` sees it while the real numpy is imported. The states and
bundles are driven through `scripts/t08_rc.py lock-check`, the command CI's clean-install job runs
on the real wheel (X05.A21), and every expectation is read from
`benchmarks/x05/reference_values.json`. Replaces T08.A19's `test_t08_r3_a19_lock_lookup.py`
(ADR 0069 D7.2).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT

from openflowsheet.run.manifest import environment

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import t08_rc  # noqa: E402

REFERENCE = json.loads((REPO_ROOT / "benchmarks/x05/reference_values.json").read_text("utf-8"))
E2E = REFERENCE["end_to_end"]
LOCKED = REFERENCE["lock"]["sha256"]
E2E_PINS = {row["name"]: row["locked"] for row in REFERENCE["lock"]["runtime_closure"]}
UNKNOWN = "the dependency set is unknown on "


def _python(*arguments: str, cwd: Path, pythonpath: str | None) -> subprocess.CompletedProcess[str]:
    environment_ = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    environment_.update({name: "1" for name in t08_rc.THREAD_VARIABLES})
    if pythonpath is not None:
        environment_["PYTHONPATH"] = pythonpath
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=cwd,
        env=environment_,
        capture_output=True,
        text=True,
        check=False,
    )


def _solve(out: Path, *, cwd: Path, pythonpath: str) -> dict[str, Any]:
    solved = _python(
        "-c",
        "import sys; from openflowsheet.application.cli import main; "
        "sys.exit(main(['solve', 'SYN-001-nominal', '--out', sys.argv[1]]))",
        str(out),
        cwd=cwd,
        pythonpath=pythonpath,
    )
    assert solved.returncode == 0, solved.stderr[-2000:]
    document: dict[str, Any] = json.loads((out / "run-manifest.json").read_text("utf-8"))
    return document


@pytest.fixture(scope="module")
def construct(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """§6.2's constructs and the records of the five `lock-check` states."""
    here = environment()
    if (here.lock_sha256, here.lock_findings) != (LOCKED, ()):
        pytest.fail(
            "the running environment does not verify the lock, so no matched cell can be judged: "
            + "; ".join(here.lock_findings)
        )
    tmp = tmp_path_factory.mktemp("x05")
    scratch = tmp / "scratch"
    site = scratch / "venv" / "lib" / "python3.13" / "site-packages"
    shutil.copytree(
        REPO_ROOT / "src" / "openflowsheet",
        site / "openflowsheet",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    stray = scratch / "requirements.lock"
    stray.write_bytes(
        (REPO_ROOT / "requirements.lock").read_bytes() + E2E["stray"]["suffix"].encode()
    )
    shadow = tmp / "shadow"
    (shadow / E2E["shadow"]["dist_info"]).parent.mkdir(parents=True)
    (shadow / E2E["shadow"]["dist_info"]).write_text(E2E["shadow"]["metadata"], encoding="utf-8")

    bundles = {
        "on": _solve(scratch / "on", cwd=scratch, pythonpath=str(site)),
        "off": _solve(scratch / "off", cwd=scratch, pythonpath=f"{shadow}{os.pathsep}{site}"),
    }
    records: dict[str, dict[str, Any]] = {}
    for state in t08_rc.LOCK_STATES:
        out = tmp / f"lock-{state}.json"
        ran = _python(
            str(REPO_ROOT / "scripts" / "t08_rc.py"),
            "lock-check",
            "--state",
            state,
            "--bundle-on",
            str(scratch / "on"),
            "--bundle-off",
            str(scratch / "off"),
            "--shadow",
            str(shadow),
            "--nolock-root",
            str(scratch / "nolock"),
            "--out",
            str(out),
            cwd=scratch,
            pythonpath=str(site) if state.startswith("installed") else None,
        )
        records[state] = {"returncode": ran.returncode, "output": ran.stdout + ran.stderr[-2000:]}
        if out.is_file():
            records[state]["document"] = json.loads(out.read_text("utf-8"))
    return {"stray": stray, "site": site, "bundles": bundles, "records": records}


def _checks(construct: dict[str, Any], state: str) -> dict[str, dict[str, Any]]:
    record = construct["records"][state]
    assert record["returncode"] == 0, record["output"]
    document = record["document"]
    # V02 alpha spec §18.3 (R-347): the record names the host's registered machine class.
    assert document["provenance"]["machine_class"] == t08_rc.machine_class()
    return {entry["id"]: entry for entry in document["checks"]}


def test_the_stray_is_the_registered_one(construct: dict[str, Any]) -> None:
    digest = hashlib.sha256(construct["stray"].read_bytes()).hexdigest()
    assert digest == E2E["stray"]["sha256"] != LOCKED


def test_a13_installed_beneath_a_verifiable_stray_records_the_packaged_lock(
    construct: dict[str, Any],
) -> None:
    checks = _checks(construct, "installed")
    located = checks["x05.installed_outside_the_tree_beneath_the_stray"]
    assert str(construct["stray"].resolve()) in located["strays"]
    assert not Path(located["package"]).is_relative_to(REPO_ROOT)
    found = checks["x05.environment"]
    assert (found["lock_sha256"], found["lock_findings"]) == (LOCKED, [])
    assert found["lock_sha256"] != E2E["stray"]["sha256"]
    # Control: read explicitly, the stray verifies under its own hash.
    assert checks["x05.control_the_stray_would_verify"]["lock_sha256"] == E2E["stray"]["sha256"]


def test_a14_installed_without_its_lock_records_empty_never_the_strays(
    construct: dict[str, Any],
) -> None:
    checks = _checks(construct, "installed-nolock")
    found = checks["x05.environment"]
    expected = E2E["missing_lock"]
    assert (found["lock_sha256"], found["lock_findings"]) == (
        expected["lock_sha256"],
        expected["lock_findings"],
    )
    assert (
        str(construct["stray"].resolve())
        in checks["x05.installed_outside_the_tree_beneath_the_stray"]["strays"]
    )
    assert checks["x05.never_the_strays_hash"]["result"] == "pass"
    assert construct["records"]["installed-nolock"]["document"]["replayed"] == []
    # The copy was made beside the environment; the installed tree still carries its lock.
    assert (construct["site"] / "openflowsheet" / "_data" / "requirements.lock").is_file()


@pytest.mark.parametrize("state", ["installed-off", "checkout-off"])
def test_a15_one_closure_distribution_off_records_empty_naming_it(
    construct: dict[str, Any], state: str
) -> None:
    checks = _checks(construct, state)
    found = checks["x05.environment"]
    expected = E2E["states"][state]
    assert (found["lock_sha256"], found["lock_findings"]) == (
        expected["lock_sha256"],
        expected["lock_findings"],
    )
    assert (
        construct["bundles"]["off"]["environment"]["lock_sha256"]
        == (E2E["bundles"]["off"]["lock_sha256"])
    )
    # Control: the same package without the shadow verifies (A13; the checkout's A11).
    assert (
        construct["bundles"]["on"]["environment"]["lock_sha256"]
        == (E2E["bundles"]["on"]["lock_sha256"])
    )


@pytest.mark.parametrize("cell", E2E["replays"], ids=lambda c: f"{c['state']}-{c['bundle']}")
def test_a16_a17_the_replay_matrix(construct: dict[str, Any], cell: dict[str, Any]) -> None:
    replay = _checks(construct, cell["state"])[f"x05.replay_{cell['bundle']}"]
    assert (replay["mode"], replay["verdict"]) == (cell["mode"], cell["verdict"])
    if cell["mode"] == "exact_replay":  # A16
        assert replay["integrity_ok"] is True
        assert replay["reasons"] == cell["reasons"]
    else:  # A17
        assert replay["reasons"][0] == cell["reason0"]
        assert not any(reason.startswith(UNKNOWN) for reason in replay["reasons"][1:])
    assert replay["result"] == "pass"


def test_every_state_passes_every_check(construct: dict[str, Any]) -> None:
    for state in t08_rc.LOCK_STATES:
        failed = [c["id"] for c in _checks(construct, state).values() if c["result"] != "pass"]
        assert failed == [], state


@pytest.mark.parametrize("moved", [None, "99.1.0"])
def test_a25_the_unconstrained_state_names_a_floating_member_off_the_lock(
    construct: dict[str, Any], moved: str | None, tmp_path: Path
) -> None:
    """X05.A25 as restated (ADR 0069 Amendment 1, Frank's Q-F1 = no), through the command CI's
    unconstrained environment runs: a floating member at another version (a shadow `attrs`
    dist-info, as a plain resolver could pick) records `""` naming it, and the replay reason names
    it; at the lock's versions the same state verifies."""
    templates, pins = REFERENCE["templates"], E2E_PINS
    arguments = ["lock-check", "--state", t08_rc.UNCONSTRAINED_STATE]
    if moved is not None:
        shadow = tmp_path / "shadow"
        info = shadow / f"attrs-{moved}.dist-info" / "METADATA"
        info.parent.mkdir(parents=True)
        info.write_text(f"Metadata-Version: 2.1\nName: attrs\nVersion: {moved}\n", "utf-8")
        arguments += ["--shadow", str(shadow)]
    out = tmp_path / "free.json"
    ran = _python(
        str(REPO_ROOT / "scripts" / "t08_rc.py"),
        *arguments,
        "--out",
        str(out),
        cwd=construct["stray"].parent,
        pythonpath=str(construct["site"]),
    )
    assert ran.returncode == 0, ran.stdout + ran.stderr[-2000:]
    document = json.loads(out.read_text("utf-8"))
    checks = {entry["id"]: entry for entry in document["checks"]}
    assert all(entry["result"] == "pass" for entry in checks.values()), checks
    findings = (
        []
        if moved is None
        else [templates["F4"].format(name="attrs", installed=moved, locked=pins["attrs"])]
    )
    environment_ = checks["x05.environment"]
    assert (environment_["lock_sha256"], environment_["lock_findings"]) == (
        "" if findings else LOCKED,
        findings,
    )
    reason = checks["x05.a25_the_replay_reason_names_the_members_off_the_lock"]
    if findings:
        assert reason["reasons"] == [templates["R_THIS"].format(findings=findings[0])]
    else:
        assert not any(r.startswith(UNKNOWN) for r in reason["reasons"])
