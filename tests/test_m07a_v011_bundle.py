"""M07a.A42: the v0.1.1 bundle probe (V02 alpha release spec MR-10; T08 §4.1 clause (e)).

v0.1.0 was released and schemas changed after it under ADRs (ADR 0019 Amendment 3; ADR 0033–0035),
so by T08 §4.1's own reasoning V11 (e) now also covers a bundle emitted by the predecessor release.
T08.A35's v0.0.0 probe (`tests/test_t08_w2_v000_probe.py`) is carried unchanged beside this one.

The fixture `tests/fixtures/m07a/v0.1.1-syn001-nominal/` is a replay bundle written by the CLI *at
tag `v0.1.1`* (`5473b51`), not by today's code: a detached worktree at the tag, a throwaway Python
3.13.5 venv holding exactly the tag's `requirements.lock` (sha256 `ead4edf1…b9c4`; `pip freeze
--exclude-editable` equal to it), the project installed editable from the worktree, and
`openflowsheet solve SYN-001-nominal --out <bundle>` run there on ref-x86-64 (AMD Ryzen
Threadripper PRO 5965WX; 2026-10-09; thread pins unset; `CONVERGED`, `VERIFIED`, structural sha256
`16ae2bd4…773b`). The worktree and venv were removed afterwards. The five files are committed
unmodified (70 727 bytes); their sha256 are pinned below.

The clause is met iff today's `replay` returns a typed report — `exact_replay` or
`compatible_reproduction` with `MATCH`, `inspected_archived_results` with `NOT_RUN` and its reason,
or a typed refusal naming the schema version — and `inspect` renders the bundle, with no unhandled
exception (spec §10, "exact (pattern), as T08.A35"). Measured at this commit on ref-x86-64, with
the thread pins unset or all `1`: `replay --rerun` gives `compatible_reproduction` `MATCH` with
bitwise-equal floats (the thread pins are unknown or differ, so it is never `exact_replay`), and
`replay` without `--rerun` gives `compatible_reproduction` `NOT_RUN` ("no rerun was supplied"),
which is a typed report but not one of the clause's outcomes, so the clause is judged on
`--rerun`. A later lock makes the first `inspected_archived_results` `NOT_RUN`, which the clause
also admits; a `MISMATCH` fails it.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import shutil
from pathlib import Path

import pytest
from conftest import REPO_ROOT

from openflowsheet.application.cli import main

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "m07a" / "v0.1.1-syn001-nominal"
V011_LOCK_SHA256 = "ead4edf1ea3577287a7576d56a9e5db550e5a5be459dd634b10806fdc655b9c4"
V011_STRUCTURAL_SHA256 = "16ae2bd4ab03810597147f4daa3894fb123ead2bb0e36548ef75fd28b3ce773b"
#: The files as the v0.1.1 CLI wrote them.
FIXTURE_SHA256 = {
    "run-manifest.json": "79db2daf823a973acf0c832eb1b63bd2701c5cdecb29fbfc2f8a86babe097d1f",
    "artifacts/solution-certificate.json": (
        "3cb9083f678702548514941a961c38f4240ccb087026f81d8f36cc673d2b8229"
    ),
    "artifacts/solve-events.json": (
        "2ce6ddaee2cc171edd05e32d9fabc73813e0a96a2e80642670e23d44025085c8"
    ),
    "artifacts/solve-plan.json": "9e9097a33c882792d0b8f3475f125dceb8a4a682c636e4fc9c9c061813e37cf7",
    "artifacts/structural-report.json": (
        "9d515044db4dedf09caa99a2aeba4d86bcce8e8e55bc8262766ce69a40a93143"
    ),
}
#: A42's admissible outcomes of `replay`, other than a typed refusal naming the schema version.
TYPED = {
    ("exact_replay", "MATCH"),
    ("compatible_reproduction", "MATCH"),
    ("inspected_archived_results", "NOT_RUN"),
}


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


def test_a42_the_fixture_is_the_v011_bundle() -> None:
    found = {
        path.relative_to(FIXTURE).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(FIXTURE.rglob("*"))
        if path.is_file()
    }
    assert found == FIXTURE_SHA256
    manifest = json.loads((FIXTURE / "run-manifest.json").read_text(encoding="utf-8"))
    assert manifest["run_id"] == "SYN-001-nominal"
    assert manifest["environment"]["lock_sha256"] == V011_LOCK_SHA256
    assert manifest["structural_sha256"] == V011_STRUCTURAL_SHA256
    assert manifest["numerical_policy_id"] == "T08-numerical-policy-v2"
    assert (manifest["outcome"], manifest["verification_status"]) == ("CONVERGED", "VERIFIED")
    assert sorted(f"artifacts/{name}" for name in manifest["artifacts"]) == sorted(
        path for path in FIXTURE_SHA256 if path.startswith("artifacts/")
    )


def test_a42_replay_returns_a_typed_report(bundle: Path) -> None:
    code, out = _cli("replay", "--json", "--rerun", str(bundle))
    report = json.loads(out)
    assert (report["mode"], report["verdict"]) in TYPED, report
    if report["mode"] != "exact_replay":
        assert report["reasons"], report  # a reproduction or an inspection names its reason
    assert report["integrity"] == {"missing": [], "ok": True, "tampered": [], "unexpected": []}
    assert report["recorded_environment"]["lock_sha256"] == V011_LOCK_SHA256
    assert code == (0 if report["verdict"] == "MATCH" else 1)


def test_a42_replay_without_rerun_is_typed_too(bundle: Path) -> None:
    """Not the clause's outcome (see the module docstring); recorded so that inspecting a v0.1.1
    bundle without a rerun is known not to raise."""
    code, out = _cli("replay", "--json", str(bundle))
    report = json.loads(out)
    assert code == 0
    assert report["verdict"] == "NOT_RUN" and report["reasons"]


def test_a42_inspect_renders_the_bundle(bundle: Path) -> None:
    code, out = _cli("inspect", str(bundle))
    assert code == 0
    for line in (
        "=== run",
        "id                SYN-001-nominal",
        "outcome           CONVERGED",
        "verification      VERIFIED",
        f"structural sha256 {V011_STRUCTURAL_SHA256}",
        "integrity         ok",
        "=== certificate  VERIFIED",
        "=== trace  8 events",
    ):
        assert line in out, line
