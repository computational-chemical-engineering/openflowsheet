"""REL060 D-3 TO-1 to TO-6: `scripts/release_rc.py junit-cases` on fixture junit files.

`gh` is mocked (no network): the push run, step 1's record and the downloaded artifacts are
fixtures. One passing case and the six controls (a) to (f), each failing exactly its named check.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import release_rc  # noqa: E402

LEGS = ["x86_64", "aarch64", "Windows-X64", "macOS-ARM64"]
FILE = "tests/test_f2_amendment9.py"
RUN_CASE = f"{FILE}::test_e_f2_3_raised_run_writes_the_v1_bundle"
COUNT_CASE = f"{FILE}::test_e_f2_3_run_set_is_47_g8_and_9_basis_cases"
CASES = [RUN_CASE, COUNT_CASE]
CLASS = "tests.test_f2_amendment9"
PARAMS = ("g8-a", "g8-b", "basis-a")


def _xml(*, skip: str | None = None, fail: str | None = None, drop: str | None = None) -> bytes:
    rows = [("test_e_f2_3_run_set_is_47_g8_and_9_basis_cases", None)]
    rows += [(f"test_e_f2_3_raised_run_writes_the_v1_bundle[{p}]", p) for p in PARAMS]
    rows += [("test_other", None)]
    body = ""
    for name, param in rows:
        if param is not None and param == drop:
            continue
        child = ""
        if param is not None and param == skip:
            child = '<skipped message="no"/>'
        if param is not None and param == fail:
            child = '<failure message="bad"/>'
        body += f'<testcase classname="{CLASS}" name="{name}">{child}</testcase>'
    body += (
        '<testcase classname="tests.test_x" name="test_e_f2_3_run_set_is_47_g8_and_9_basis_cases"/>'
    )
    return f"<testsuites><testsuite>{body}</testsuite></testsuites>".encode()


def _sha(data: bytes) -> str:
    return release_rc.sha256(data)


def _step1(junit: dict[str, dict[str, bytes] | None], run_id: int = 7) -> dict:
    # The record step 1 writes (R-REV F-2): built by `step1_checks`, not by hand.
    run = {"databaseId": run_id, "status": "completed", "jobs": []}
    legs = {leg: found for leg, found in junit.items() if leg in ("x86_64", "aarch64")}
    return {"checks": release_rc.step1_checks(run, legs, {})}


def _fixture(**overrides: dict[str, bytes] | None):
    junit: dict[str, dict[str, bytes] | None] = {leg: {"pytest.xml": _xml()} for leg in LEGS}
    junit.update(overrides)
    return junit


def _run(junit, *, run_id: int = 7, step1_run: int = 7, cases=CASES, selected=True):
    run = {"databaseId": run_id, "status": "completed"} if selected else None
    return release_rc.junit_cases_checks(
        selected=run,
        step1_record=_step1(junit, step1_run),
        junit=junit,
        legs=LEGS,
        cases=cases,
    )


def _failed(checks) -> set[str]:
    return {c["id"] for c in checks if c["result"] != "pass"}


def test_to6_passing_case() -> None:
    checks, body = _run(_fixture())
    assert _failed(checks) == set()
    junit = [c for c in checks if c["id"] == "legs.junit"][0]
    assert junit["compared_with_step1"] == ["x86_64", "aarch64"]
    assert len({d for d in body["set_sha256"].values()}) == 1
    assert body["matched"]["x86_64"][RUN_CASE]["count"] == len(PARAMS)
    assert body["matched"]["x86_64"][COUNT_CASE]["count"] == 1  # the other classname is not matched


def test_to6_a_skipped_case_fails_passed() -> None:
    checks, _ = _run(_fixture(**{"macOS-ARM64": {"pytest.xml": _xml(skip="g8-b")}}))
    assert _failed(checks) == {"legs.passed"}


def test_to6_b_failure_child_fails_passed() -> None:
    checks, _ = _run(_fixture(aarch64={"pytest.xml": _xml(fail="basis-a")}))
    assert _failed(checks) == {"legs.passed"}


def test_to6_c_missing_parametrised_case_fails_same_set() -> None:
    checks, _ = _run(_fixture(**{"Windows-X64": {"pytest.xml": _xml(drop="g8-a")}}))
    assert _failed(checks) == {"legs.same_set"}


def test_to6_d_case_matching_nothing_fails_cases() -> None:
    checks, _ = _run(_fixture(), cases=[*CASES, f"{FILE}::test_nothing"])
    assert "legs.cases" in _failed(checks)


def test_to6_e_absent_artifact_fails_junit() -> None:
    checks, _ = _run(_fixture(**{"Windows-X64": None}))
    assert "legs.junit" in _failed(checks)
    assert [c for c in checks if c["id"] == "legs.junit"][0]["absent"] == ["Windows-X64"]


def test_to6_f_other_run_id_fails_push_run() -> None:
    checks, _ = _run(_fixture(), run_id=8, step1_run=7)
    assert _failed(checks) == {"legs.push_run"}


def test_to1_absent_step1_record_or_run_fails() -> None:
    kwargs = dict(junit=_fixture(), legs=LEGS, cases=CASES)
    checks, _ = release_rc.junit_cases_checks(
        selected={"databaseId": 7, "status": "completed"}, step1_record=None, **kwargs
    )
    assert _failed(checks) == {"legs.push_run"}
    checks, _ = release_rc.junit_cases_checks(selected=None, step1_record=_step1({}), **kwargs)
    assert "legs.push_run" in _failed(checks)


def test_to2_hash_differing_from_step1_fails() -> None:
    other = {"pytest.xml": _xml(drop="g8-a")}
    checks, _ = release_rc.junit_cases_checks(
        selected={"databaseId": 7, "status": "completed"},
        step1_record=_step1(_fixture(x86_64=other)),
        junit=_fixture(),
        legs=LEGS,
        cases=CASES,
    )
    assert _failed(checks) == {"legs.junit"}


def test_classname_reading() -> None:
    assert release_rc._case_selector(RUN_CASE) == (
        CLASS,
        "test_e_f2_3_raised_run_writes_the_v1_bundle",
    )
    with pytest.raises(ValueError):
        release_rc._case_selector("no-separator")


@pytest.fixture
def mocked(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(release_rc._t08_rc(), "git", lambda *a: "C0\n")
    monkeypatch.setattr(
        release_rc,
        "_gh_runs",
        lambda commit: [{"databaseId": 7, "headSha": "C0", "event": "push", "status": "completed"}],
    )
    junit = _fixture()
    monkeypatch.setattr(release_rc, "_gh_junit", lambda run, leg, into: junit[leg])
    (tmp_path / "step1").mkdir()
    (tmp_path / "step1" / "rc-step1.json").write_text(json.dumps(_step1(junit)), encoding="utf-8")
    monkeypatch.setattr(release_rc, "_finish", _finish_stub)
    return tmp_path


def _finish_stub(out: Path, step: str, checks, **body) -> int:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"step": step, "checks": checks, **body}), encoding="utf-8")
    return 0 if all(c["result"] == "pass" for c in checks) else 1


def _argv(rc: Path, commit: str = "C0") -> list[str]:
    argv = ["junit-cases", "--commit", commit, "--rc", str(rc), "--id", "F2-THREE-OS"]
    argv += ["--legs", ",".join(LEGS)]
    for case in CASES:
        argv += ["--case", case]
    return argv


def test_main_writes_the_record_and_exits_0(mocked: Path) -> None:
    assert release_rc.main(_argv(mocked)) == 0
    record = json.loads((mocked / "step17" / "F2-THREE-OS" / "junit-cases.json").read_text())
    assert record["run_id"] == 7 and record["step"] == "junit cases (F2-THREE-OS)"


def test_main_exits_2_off_c_and_on_malformed_arguments(mocked: Path) -> None:
    assert release_rc.main(_argv(mocked, commit="C1")) == 2
    bad = _argv(mocked)[:-1] + ["no-separator"]
    assert release_rc.main(bad) == 2
