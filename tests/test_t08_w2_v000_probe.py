"""T08.A35: the v0.0.0 bundle probe (T08 release spec §4.1 clause (e), §9).

The fixture `tests/fixtures/t08/v0.0.0-syn001-nominal/` is a replay bundle written by the CLI *at
tag `v0.0.0`* (`9a4391f`), not by today's code: a detached worktree at the tag, a throwaway Python
3.13.5 venv holding exactly the tag's `requirements.lock` (sha256 `b9c509b5…a313`; `pip freeze`
equal to it apart from the editable project), the project installed editable from the worktree, and
`process-runtime solve SYN-001-nominal --out <bundle>` run there on ref-x86-64 (2026-10-01:
`CONVERGED`, `VERIFIED`, structural sha256 `0eba5175…75e6`). The worktree and venv were removed
afterwards. The four files are committed unmodified (56 152 bytes).

Clause (e) is met iff today's `replay` returns a typed report — `inspected_archived_results` with
`NOT_RUN`, or a typed refusal naming the schema version — and `inspect` renders the bundle, with no
unhandled exception. Today's answer is the first: the bundle's integrity holds and the recorded
lock differs from the current one, so nothing is rerun.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
from pathlib import Path

import pytest
from conftest import REPO_ROOT

from openflowsheet.application.cli import main

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "t08" / "v0.0.0-syn001-nominal"
V000_LOCK_SHA256 = "b9c509b5d13aef089cf2de4c6b394463c0c5f687ff343a490d6812499c14a313"


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    copy = tmp_path / "bundle"
    shutil.copytree(FIXTURE, copy)
    return copy


def _cli(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(list(argv))
    return code, out.getvalue()


def test_a35_the_fixture_is_the_v000_bundle() -> None:
    manifest = json.loads((FIXTURE / "run-manifest.json").read_text(encoding="utf-8"))
    assert manifest["run_id"] == "SYN-001-nominal"
    assert manifest["environment"]["lock_sha256"] == V000_LOCK_SHA256
    assert (manifest["outcome"], manifest["verification_status"]) == ("CONVERGED", "VERIFIED")
    assert sorted(path.name for path in (FIXTURE / "artifacts").iterdir()) == sorted(
        manifest["artifacts"]
    )


def test_a35_replay_returns_a_typed_report(bundle: Path) -> None:
    code, out = _cli("replay", "--json", str(bundle))
    report = json.loads(out)
    assert code == 0
    assert report["mode"] == "inspected_archived_results"
    assert report["verdict"] == "NOT_RUN"
    assert report["integrity"] == {"missing": [], "ok": True, "tampered": [], "unexpected": []}
    assert report["recorded_environment"]["lock_sha256"] == V000_LOCK_SHA256
    assert any(reason.startswith("the lock file differs") for reason in report["reasons"])


def test_a35_replay_rerun_is_typed_too(bundle: Path) -> None:
    """Not required by A35; recorded so that `--rerun` on an old bundle is known not to raise."""
    code, out = _cli("replay", str(bundle), "--rerun")
    assert code == 1
    assert "mode      inspected_archived_results" in out
    assert "verdict   NOT_RUN" in out


def test_a35_inspect_renders_the_bundle(bundle: Path) -> None:
    code, out = _cli("inspect", str(bundle))
    assert code == 0
    for line in (
        "=== run",
        "id                SYN-001-nominal",
        "outcome           CONVERGED",
        "verification      VERIFIED",
        "integrity         ok",
        "=== certificate  VERIFIED",
        "=== trace  8 events",
    ):
        assert line in out, line
