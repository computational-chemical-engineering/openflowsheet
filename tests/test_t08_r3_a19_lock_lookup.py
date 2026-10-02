"""T08.A19 (release spec Amendment R3 5, R-140): the lock lookup is confined to the source checkout.

`run/manifest.py` used to walk every parent directory of the module (and fall back to the working
directory), so an installed package beneath any unrelated file named `requirements.lock` recorded
that file's hash as its dependency set. The three states, as `scripts/t08_rc.py lock-check` asserts
them in the clean-install CI job: (a) the source checkout records the registered lock `ead4edf1…`;
(b) an installed package beneath a stray `requirements.lock` records `""`; (c) a `SYN-001-nominal`
bundle written by (b)'s CLI replays `inspected_archived_results` / `NOT_RUN`, the dependency set
named unknown, from (b) and from (a). Here the installed package is the checkout's `src/` copied
into a scratch `site-packages` (what a wheel installs; T08.A43 checks the wheel's contents).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import REPO_ROOT

from openflowsheet.run import manifest

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import t08_rc  # noqa: E402

PYPROJECT = '[project]\nname = "openflowsheet"\nversion = "0"\n'


def _layout(root: Path, *, pyproject: str | None = PYPROJECT, lock: bool = True) -> Path:
    module = root / "src" / "openflowsheet" / "run" / "manifest.py"
    module.parent.mkdir(parents=True)
    module.write_text("", encoding="utf-8")
    if pyproject is not None:
        (root / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    if lock:
        (root / "requirements.lock").write_text("a==1\n", encoding="utf-8")
    return module


# -- the rule, on constructed trees -------------------------------------------------------------


def test_a_the_checkout_records_the_registered_lock() -> None:
    assert manifest._repository_lock() == REPO_ROOT / "requirements.lock"
    assert manifest.environment().lock_sha256 == t08_rc.LOCK_SHA256


def test_a_checkout_layout_finds_its_own_lock(tmp_path: Path) -> None:
    assert manifest._checkout_lock(_layout(tmp_path)) == tmp_path / "requirements.lock"


@pytest.mark.parametrize(
    ("pyproject", "lock"),
    [
        (PYPROJECT, False),
        (PYPROJECT.replace("openflowsheet", "someone-else"), True),
        ("[project\n", True),
        (None, True),
    ],
    ids=["no-lock", "another-project", "unreadable-pyproject", "no-pyproject"],
)
def test_anything_but_this_projects_checkout_has_no_lock(
    tmp_path: Path, pyproject: str | None, lock: bool
) -> None:
    assert manifest._checkout_lock(_layout(tmp_path, pyproject=pyproject, lock=lock)) is None


def test_b_an_installed_layout_beneath_a_stray_lock_has_none(tmp_path: Path) -> None:
    # A stray lock and even this project's pyproject above `site-packages` are not a checkout.
    (tmp_path / "requirements.lock").write_text("unrelated==1\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    module = tmp_path / "venv/lib/python3.13/site-packages/openflowsheet/run/manifest.py"
    module.parent.mkdir(parents=True)
    module.write_text("", encoding="utf-8")
    assert manifest._checkout_lock(module) is None
    assert manifest._checkout_lock(tmp_path / "manifest.py") is None


# -- the three states end to end (`t08_rc.py lock-check`) --------------------------------------


def _python(*arguments: str, cwd: Path, pythonpath: str | None) -> subprocess.CompletedProcess[str]:
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    environment.update({name: "1" for name in t08_rc.THREAD_VARIABLES})
    if pythonpath is not None:
        environment["PYTHONPATH"] = pythonpath
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_three_states_end_to_end(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    site = scratch / "venv" / "lib" / "python3.13" / "site-packages"
    shutil.copytree(
        REPO_ROOT / "src" / "openflowsheet",
        site / "openflowsheet",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    (scratch / "requirements.lock").write_text("unrelated==1.0\n", encoding="utf-8")
    bundle = scratch / "bundle"
    solved = _python(
        "-c",
        "import sys; from openflowsheet.application.cli import main; "
        "sys.exit(main(['solve', 'SYN-001-nominal', '--out', sys.argv[1]]))",
        str(bundle),
        cwd=scratch,
        pythonpath=str(site),
    )
    assert solved.returncode == 0, solved.stderr[-2000:]
    written = json.loads((bundle / "run-manifest.json").read_text(encoding="utf-8"))
    assert written["environment"]["lock_sha256"] == ""

    records = {}
    for state, pythonpath in (("installed", str(site)), ("checkout", None)):
        out = tmp_path / f"lock-{state}.json"
        ran = _python(
            str(REPO_ROOT / "scripts" / "t08_rc.py"),
            "lock-check",
            "--state",
            state,
            "--bundle",
            str(bundle),
            "--out",
            str(out),
            cwd=scratch,
            pythonpath=pythonpath,
        )
        assert ran.returncode == 0, ran.stdout + ran.stderr[-2000:]
        records[state] = {c["id"]: c for c in json.loads(out.read_text("utf-8"))["checks"]}
    installed, checkout = records["installed"], records["checkout"]
    strays = installed["a19.b_installed_outside_the_tree_beneath_a_stray_lock"]["strays"]
    assert strays == [str((scratch / "requirements.lock").resolve())]
    assert installed["a19.b_lock_sha256_empty"]["found"] == ""
    assert checkout["a19.a_lock_sha256_registered"]["found"] == t08_rc.LOCK_SHA256
    for state, record in records.items():
        replay = record[f"a19.c_replay_by_{state}"]
        assert (replay["mode"], replay["verdict"]) == ("inspected_archived_results", "NOT_RUN")
        assert replay["reasons"][0].startswith(
            f"the dependency set is unknown on {t08_rc.A19_UNKNOWN_SIDE[state]}"
        )
