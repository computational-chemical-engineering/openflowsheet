"""REL.A17 and RP §6.7: `ci.yml`'s `release_rc` dispatch, step 1's record and step 17's wrapper.

ADR 0055 D4.2–D4.4, RP §6.2 and §6.10. The workflow is read as text and as YAML; each job's `if`
is evaluated for a push and for a dispatch with only `release_rc` set, so the dispatch's job list
and the push run's `check` on both architectures are both pinned. Step 1's record is built by
`scripts/release_rc.py` from fixtures of `gh run view`'s JSON: a green push run (`pass`), no run
(`fail`), and a red aarch64 leg (`fail`).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import release_rc  # noqa: E402

CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"
WORKFLOW = yaml.safe_load(CI.read_text(encoding="utf-8"))
JOBS: dict[str, Any] = WORKFLOW["jobs"]
CHECK_IF = "${{ !(github.event_name == 'workflow_dispatch' && inputs.release_rc) }}"
#: RP §6.10: the jobs a `release_rc` dispatch runs (with `ptc-r1` while the PTC-R1 item stands).
RELEASE_RC_JOBS = {
    "rc-steps",
    "rc-coolprop",
    "rc-ensemble",
    "dist",
    "clean-install",
    "bundle-set",
    "bundle-replay",
    "ptc-r1",
}


def _truth(expression: str, event: str, inputs: set[str]) -> bool:
    """A job's `if`, evaluated for `event` with exactly `inputs` set (`always()` is true)."""
    text = expression.strip().removeprefix("${{").removesuffix("}}")
    text = text.replace("github.event_name", repr(event)).replace("always()", "True")
    text = re.sub(r"inputs\.([a-z0-9_]+)", lambda m: str(m.group(1) in inputs), text)
    text = text.replace("&&", " and ").replace("||", " or ")
    text = re.sub(r"!(?!=)", " not ", text)
    return bool(eval(text, {"__builtins__": {}}))  # noqa: S307 - the workflow's own expressions


def _runs(event: str, inputs: set[str]) -> set[str]:
    runs: set[str] = set()
    for name, job in JOBS.items():  # needs come earlier in the file
        needs = job.get("needs", [])
        needs = [needs] if isinstance(needs, str) else needs
        if all(need in runs for need in needs) and _truth(
            str(job.get("if", "always()")), event, inputs
        ):
            runs.add(name)
    return runs


def test_a17_check_s_if() -> None:
    assert JOBS["check"]["if"] == CHECK_IF
    assert JOBS["check"]["strategy"]["matrix"]["runner"] == ["ubuntu-latest", "ubuntu-24.04-arm"]


def test_a17_the_release_rc_input() -> None:
    entry = WORKFLOW[True]["workflow_dispatch"]["inputs"]["release_rc"]
    assert (entry["type"], entry["default"]) == ("boolean", False)


def test_a17_the_release_rc_job_list() -> None:
    assert _runs("workflow_dispatch", {"release_rc"}) == RELEASE_RC_JOBS


def test_a17_a_push_runs_check_and_no_rc_job() -> None:
    for event in ("push", "pull_request"):
        runs = _runs(event, set())
        assert {"check", "identity", "default-install"} <= runs
        assert not runs & RELEASE_RC_JOBS
    assert "check" in _runs("workflow_dispatch", {"rc_alpha"})  # the legacy dispatches unchanged
    assert _runs("workflow_dispatch", {"rc_alpha"}) - {"check", "identity", "default-install"} == (
        RELEASE_RC_JOBS - {"ptc-r1"}
    )


def test_a17_the_junit_uploads() -> None:
    steps = JOBS["check"]["steps"]
    runs = [step.get("run", "") for step in steps]
    checks = next(i for i, run in enumerate(runs) if "./scripts/check.sh" in run)
    assert steps[checks]["env"]["OPENFLOWSHEET_JUNIT_DIR"] == "${{ runner.temp }}/junit"
    (upload,) = [
        step for step in steps if str(step.get("with", {}).get("name", "")).startswith("junit-")
    ]
    assert upload["with"]["name"] == "junit-${{ runner.arch == 'ARM64' && 'aarch64' || 'x86_64' }}"
    assert upload["with"]["path"] == "${{ runner.temp }}/junit/"
    assert upload["with"]["if-no-files-found"] == "error"
    assert upload["if"] == "${{ !cancelled() }}"
    script = (REPO_ROOT / "scripts" / "check.sh").read_text(encoding="utf-8")
    assert '--junitxml="${OPENFLOWSHEET_JUNIT_DIR}/pytest.xml"' in script
    assert '--test-reporter-destination="${OPENFLOWSHEET_JUNIT_DIR}/node.xml"' in script


def test_a17_step_8_under_release_rc_is_the_alpha_s_surface_chain() -> None:
    steps = JOBS["rc-steps"]["steps"]
    (step,) = [s for s in steps if "release_rc.py surface" in s.get("run", "")]
    assert step["if"] == "always() && inputs.release_rc"
    assert "/m07a_rc.py" in Path(release_rc.__file__).read_text(encoding="utf-8")


# -- step 1's record (§6.2) ----------------------------------------------------------------------

C = "c" * 40
JUNIT = (
    b'<testsuites><testsuite><testcase classname="t.a" name="x">'
    b'<skipped message="why"/></testcase></testsuite></testsuites>'
)


def _run(**conclusions: str) -> dict[str, Any]:
    return {
        "databaseId": 7,
        "attempt": 1,
        "status": "completed",
        "conclusion": "success",
        "event": "push",
        "headSha": C,
        "jobs": [
            {"name": f"check ({runner})", "conclusion": conclusions.get(arch, "success")}
            for arch, runner in release_rc.LEGS.items()
        ],
    }


def _results(checks: list[dict[str, Any]]) -> dict[str, str]:
    return {entry["id"]: entry["result"] for entry in checks}


IDS = ["s1.push_run", "s1.check.x86_64", "s1.check.aarch64", "s1.junit"]
JUNITS = {"x86_64": {"pytest.xml": JUNIT}, "aarch64": {"pytest.xml": JUNIT}}


def test_a17_step1_a_green_push_run_passes() -> None:
    checks = release_rc.step1_checks(_run(), JUNITS, {"x86_64": "log", "aarch64": "log"})
    assert list(_results(checks)) == IDS
    assert set(_results(checks).values()) == {"pass"}


def test_a17_step1_a_missing_run_fails() -> None:
    checks = release_rc.step1_checks(None, dict.fromkeys(release_rc.LEGS), {})
    assert _results(checks) == dict.fromkeys(IDS, "fail")


def test_a17_step1_a_red_aarch64_leg_fails() -> None:
    checks = release_rc.step1_checks(_run(aarch64="failure"), JUNITS, {})
    assert _results(checks) == {**dict.fromkeys(IDS, "pass"), "s1.check.aarch64": "fail"}


def test_step1_missing_junit_fails() -> None:
    checks = release_rc.step1_checks(_run(), {**JUNITS, "x86_64": None}, {})
    assert _results(checks)["s1.junit"] == "fail"


def test_step1_selects_the_greatest_push_run_at_c() -> None:
    runs = [
        {"databaseId": 9, "event": "workflow_dispatch", "headSha": C},
        {"databaseId": 5, "event": "push", "headSha": C},
        {"databaseId": 8, "event": "push", "headSha": C},
        {"databaseId": 99, "event": "push", "headSha": "d" * 40},
    ]
    selected = release_rc.push_run(runs, C)
    assert selected is not None and selected["databaseId"] == 8
    assert release_rc.push_run(runs[:1], C) is None


def test_step1_skips_and_ratio_lines() -> None:
    assert release_rc.junit_skips(JUNIT) == ["t.a::x: why"]
    log = (
        "check (ubuntu-latest)\tS11 thermal reference line\t2026-11-06T10:00:00.1234Z worst 0.01\n"
    )
    log += "check (ubuntu-latest)\tRun checks\t2026-11-06T10:00:00Z other\n"
    assert release_rc.ratio_lines(log) == ["worst 0.01"]


# -- step 17's wrapper (§6.7) ----------------------------------------------------------------------


def test_items_substitution_and_unset_names() -> None:
    values = {"C": C, "RC_OUT": "/rc", "NLP_PREFIX": None, "NLP_CACHE": None}
    assert release_rc.substitute(["python", "x.py", "--commit", "$C"], values) == [
        "python",
        "x.py",
        "--commit",
        C,
    ]
    assert release_rc.substitute(["bash", "s.sh", "$NLP_PREFIX"], values) == "NLP_PREFIX"


def test_items_a_ci_item_passes_only_when_every_leg_succeeded() -> None:
    jobs = [
        {"name": "rc-coolprop (ubuntu-latest)", "conclusion": "success"},
        {"name": "rc-coolprop (ubuntu-24.04-arm)", "conclusion": "failure"},
        {"name": "ptc-r1 (ubuntu-latest)", "conclusion": "success"},
        {"name": "ptc-r1 (ubuntu-24.04-arm)", "conclusion": "success"},
    ]
    assert release_rc.ci_item_result(jobs, "ptc-r1")[0] is True
    assert release_rc.ci_item_result(jobs, "rc-coolprop")[0] is False
    assert release_rc.ci_item_result(jobs, "rc-ensemble") == (False, {})


LINE = json.loads((REPO_ROOT / "release" / "lines" / "0.4.json").read_text(encoding="utf-8"))
ITEMS = {item["id"]: item for item in LINE["rc_items"]}


def test_items_records_and_unsupported(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake(argv: list[str], log: Path, environment: dict[str, str]) -> int:
        calls.append(argv)
        log.write_text("ran\n", encoding="utf-8")
        (tmp_path / "step17" / "WHEEL-DATA" / "own.json").write_text("{}", encoding="utf-8")
        return 0

    values = {"C": C, "RC_OUT": str(tmp_path), "NLP_PREFIX": None, "NLP_CACHE": None}
    found = release_rc.item_check(
        ITEMS["WHEEL-DATA"], tmp_path, {"project": "/py"}, values, None, fake
    )
    assert (found["id"], found["result"], found["exit_status"]) == ("WHEEL-DATA", "pass", 0)
    assert calls == [["/py", "scripts/wheel_data_check.py", "--commit", C]]
    assert found["records"] == {"step17/WHEEL-DATA/own.json": release_rc.sha256(b"{}")}
    nlp = release_rc.item_check(ITEMS["E01-G6-nlp"], tmp_path, {}, values, None, fake)
    lca = release_rc.item_check(
        ITEMS["E01-G5-lca"], tmp_path, {"project": "/py"}, values, None, fake
    )
    ci = release_rc.item_check(ITEMS["PTC-R1"], tmp_path, {}, values, None, fake)
    assert [nlp["result"], lca["result"], ci["result"]] == ["unsupported"] * 3
    assert len(calls) == 1


@pytest.mark.parametrize("code", [1, 2])
def test_items_a_failing_command_fails(tmp_path: Path, code: int) -> None:
    def fake(argv: list[str], log: Path, environment: dict[str, str]) -> int:
        log.write_text("", encoding="utf-8")
        return code

    values = {"C": C, "RC_OUT": str(tmp_path), "NLP_PREFIX": None, "NLP_CACHE": None}
    found = release_rc.item_check(
        ITEMS["E01-A48"], tmp_path, {"project": "/py"}, values, None, fake
    )
    assert (found["result"], found["exit_status"]) == ("fail", code)


# -- amendment A-4 (RP §6.2, §6.10; review S-3, S-4) and S-7 -------------------------------------

RUNS_AT_C = [
    {
        "databaseId": 12,
        "event": "workflow_dispatch",
        "headSha": C,
        "attempt": 2,
        "conclusion": "success",
    },
    {
        "databaseId": 10,
        "event": "workflow_dispatch",
        "headSha": C,
        "attempt": 1,
        "conclusion": "failure",
    },
    {"databaseId": 8, "event": "push", "headSha": C, "attempt": 1, "conclusion": "success"},
    {"databaseId": 13, "event": "workflow_dispatch", "headSha": "d" * 40, "attempt": 1},
]


def test_a4_the_release_rc_dispatch_is_the_greatest_run_id_at_c() -> None:
    """A red dispatch and a green retry at C: only the greatest run id is the dispatch; another
    commit's run never is. Control: the greatest is accepted."""
    selected = release_rc.rc_dispatch(RUNS_AT_C, C)
    assert selected is not None and selected["databaseId"] == 12
    assert release_rc.dispatch_problem(12, RUNS_AT_C, C) is None
    assert release_rc.dispatch_problem(10, RUNS_AT_C, C) == (
        f"run 10 is not the release_rc dispatch at {C}: that is run 12, the greatest run id "
        "(RP §6.10, A-4)"
    )
    assert "is not the release_rc dispatch" in str(release_rc.dispatch_problem(8, RUNS_AT_C, C))
    assert "no workflow_dispatch run" in str(release_rc.dispatch_problem(13, RUNS_AT_C[2:], C))


def test_a4_step_1_lists_every_run_at_c() -> None:
    listed = release_rc.runs_at_c(RUNS_AT_C, C)
    assert [(run["databaseId"], run["event"], run["attempt"]) for run in listed] == [
        (8, "push", 1),
        (10, "workflow_dispatch", 1),
        (12, "workflow_dispatch", 2),
    ]
    assert listed[1]["conclusion"] == "failure"


def test_s4_c_pushed_beneath_a_later_commit_has_no_push_run_and_names_the_remedy() -> None:
    """GitHub starts a push run only for the pushed head: C pushed beneath a later commit has none,
    and step 1 fails with A-4's remedy. Control: C pushed as a head."""
    beneath = [{"databaseId": 9, "event": "push", "headSha": "d" * 40}]
    assert release_rc.push_run(beneath, C) is None
    (push, *_) = release_rc.step1_checks(None, dict.fromkeys(release_rc.LEGS), {}, commit=C)
    assert push["result"] == "fail"
    assert push["remedy"] == (
        f"push C on its own, as a branch head: git push origin {C}:refs/heads/rc/{C[:7]} "
        "(RP §6.2, A-4)"
    )
    (control, *_) = release_rc.step1_checks(_run(), JUNITS, {}, commit=C)
    assert control["result"] == "pass" and "remedy" not in control


@pytest.mark.parametrize("command", ["ci", "items"])
def test_a4_ci_and_items_refuse_a_run_that_is_not_the_dispatch(
    command: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    head = release_rc._t08_rc().git("rev-parse", "HEAD").strip()
    runs = [{**run, "headSha": head} for run in RUNS_AT_C[:3]]
    monkeypatch.setattr(release_rc, "_gh_runs", lambda commit: runs)
    reached: list[str] = []
    monkeypatch.setattr(release_rc, "items", lambda *a, **k: reached.append("items") or 0)

    def fetch_ci(*arguments: Any) -> int:
        reached.append("ci")
        return 0

    monkeypatch.setattr(release_rc._local_lib(), "fetch_ci", fetch_ci)
    argv = [command, "--rc", str(tmp_path), "--commit", head]
    argv += ["--line", "0.4"] if command == "items" else []
    assert release_rc.main([*argv, "--ci-run", "10"]) == 2
    assert capsys.readouterr().err.startswith("refused: run 10 is not the release_rc dispatch")
    assert reached == []
    assert release_rc.main([*argv, "--ci-run", "12"]) == 0
    assert reached == [command]


def test_s7_a_ci_item_whose_download_failed_fails(tmp_path: Path) -> None:
    """Review S-7: the item's check records `gh run download`'s exit status and file count; a
    failed download is `fail` though every leg succeeded. Control: a download that exited 0."""
    jobs = [
        {"name": "ptc-r1 (ubuntu-latest)", "conclusion": "success"},
        {"name": "ptc-r1 (ubuntu-24.04-arm)", "conclusion": "success"},
    ]
    values = {"C": C, "RC_OUT": str(tmp_path), "NLP_PREFIX": None, "NLP_CACHE": None}
    failed = {"run_id": 12, "attempt": 2, "exit_status": 1, "files": 0}
    found = release_rc.item_check(ITEMS["PTC-R1"], tmp_path, {}, values, jobs, download=failed)
    assert (found["result"], found["download"]) == ("fail", failed)
    fetched = {**failed, "exit_status": 0, "files": 4}
    found = release_rc.item_check(ITEMS["PTC-R1"], tmp_path, {}, values, jobs, download=fetched)
    assert (found["result"], found["download"]["files"]) == ("pass", 4)
    assert release_rc.item_check(ITEMS["PTC-R1"], tmp_path, {}, values, jobs)["result"] == "fail"
