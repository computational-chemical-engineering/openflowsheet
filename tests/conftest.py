"""Shared fixtures for the repository test suite (P00 baseline, extended by P01)."""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
#: X07a: the `bash` a test runs a shell script with. On Windows CreateProcess searches System32
#: before PATH and finds the WSL launcher (run 44618922484: "... wsl.exe --install <Distro>"), so
#: the PATH's bash (Git's on the CI runner) is named by its full path; elsewhere the bare name.
BASH = (shutil.which("bash") or "bash") if sys.platform == "win32" else "bash"


# -- X07a: replay and floating-point limits off the registered platforms (ruling R2, P1 to P5) ---
# Each use below carries the id of its row in the platform-limit table of `docs/X07a_DECISIONS.md`
# (`X07a-L<n>`); `tests/test_x07a_platform_rows.py` asserts the two sets of ids are equal.

#: This host's `(platform.machine(), platform.system())`, as `run.replay.decide_mode` sees it.
HOST_PLATFORM: tuple[str, str] = (platform.machine(), platform.system())

#: P2: where the committed bitwise baselines (`float.hex()`, `repr` or byte goldens) were recorded
#: or measured bit-identical. Registering a replay platform never adds to it (ADR 0007 D3.2).
BITWISE_BASELINE_PLATFORMS: frozenset[tuple[str, str]] = frozenset(
    {("x86_64", "Linux"), ("aarch64", "Linux")}
)
#: The start of the skip reason of a `bitwise_baseline` node off those platforms.
BITWISE_BASELINE_OFF_PLATFORM = "bitwise_baseline_off_platform"

#: P3c: per unregistered platform and test node, the row and the exact set of paths that differ
#: beyond the numerical policy there. An extra path fails, and so does a registered path that no
#: longer differs. No registered platform is a key (asserted by the rows test).
PLATFORM_DIFFERENCES: dict[tuple[str, str], dict[str, tuple[str, frozenset[str]]]] = {
    ("arm64", "Darwin"): {
        "tests/test_st_cli.py::test_th_c1_a_fresh_solve_is_the_json_golden_under_the_policy": (
            "X07a-L5",
            frozenset({"<root>.certificate_id", "<root>.energy.overall.closure"}),
        ),
        "tests/test_m03_schemas.py::test_the_fixtures_are_what_real_runs_emit_today": (
            "X07a-L3",
            frozenset(
                {
                    "study/sensitivity_result/valid/b1_forward_phase_boundary.json: "
                    "<root>.qualification.outcomes[8].splits[1].margin",
                    "study/sensitivity_result/valid/b1_forward_phase_boundary.json: "
                    "<root>.qualification.regularity.inverse_one_norm_estimate",
                    "study/sensitivity_result/valid/b1_forward_phase_boundary.json: "
                    "<root>.qualification.regularity.solution_error_bound_scaled",
                    "study/sensitivity_result/valid/b1_forward_phase_boundary.json: "
                    "<root>.qualification.splits[1].margin",
                    "study/sensitivity_result/valid/b1_forward_phase_boundary.json: "
                    "<root>.refusals[0].message (float 0 of its text)",
                }
            ),
        ),
    },
}


def platform_differences(node: str) -> frozenset[str]:
    """P3c: the paths registered to differ beyond the policy for `node` on this host; empty on a
    registered platform and for a node without a row."""
    return PLATFORM_DIFFERENCES.get(HOST_PLATFORM, {}).get(node, ("", frozenset()))[1]


#: The note `run.replay.replay` appends when it re-runs nothing (`revision_replay._inspected`
#: keeps it); P1c accepts it after the `running on` reason and nowhere else (X07a D-20).
NOT_RERUN_NOTE = "no rerun was supplied"


def assert_inspected_off_registered(report: Any, row: str) -> None:
    """P1c: a committed bundle recorded on a registered platform, replayed on an unregistered one,
    gets the policy's answer: inspected, `NOT_RUN`, integrity intact, and for each replayed member
    (an optimization record prefixes `<member>: `) the `running on` reason, followed at most by
    `NOT_RERUN_NOTE`. The comparison claim stays judged on the registered legs. `report` is a
    `ReplayReport` or its document; `row` is the `X07a-L<n>` id of the platform-limit row."""
    from openflowsheet.run.replay import REGISTERED_PLATFORMS

    document = report.as_document() if hasattr(report, "as_document") else report
    assert HOST_PLATFORM not in REGISTERED_PLATFORMS, (row, HOST_PLATFORM)
    assert document["mode"] == "inspected_archived_results", (row, document["mode"])
    assert document["verdict"] == "NOT_RUN", (row, document["verdict"])
    assert document["integrity"]["ok"], (row, document["integrity"])
    machine, system = HOST_PLATFORM
    running_on = f"running on {machine}/{system}, which is not a registered platform"
    members: dict[str, list[str]] = {}
    for reason in document["reasons"]:
        member, separator, text = reason.partition(": ")
        if not separator or member.startswith("running on"):
            member, text = "", reason
        members.setdefault(member, []).append(text)
    assert members, (row, document["reasons"])
    for member, texts in members.items():
        assert texts[0].startswith(running_on), (row, member, texts)
        assert texts[1:] in ([], [NOT_RERUN_NOTE]), (row, member, texts)


def pytest_runtest_setup(item: Any) -> None:
    """P2: a `bitwise_baseline` node runs only where its baseline's bits were recorded."""
    marker = item.get_closest_marker("bitwise_baseline")
    if marker is not None and HOST_PLATFORM not in BITWISE_BASELINE_PLATFORMS:
        row = marker.kwargs.get("row", "")
        pytest.skip(
            f"{BITWISE_BASELINE_OFF_PLATFORM}: {row}: the expectation is bitwise, recorded on "
            f"{sorted(BITWISE_BASELINE_PLATFORMS)}; this is {HOST_PLATFORM} (X07a ruling P2)"
        )


#: The reason a test that reads the pre-0.1.0 development history skips where that history is not.
ARCHIVED_HISTORY = "pre-0.1.0 development history is archived in openflowsheet-dev (R-150)"
#: v0.1.0 on the public line: the root commit of `computational-chemical-engineering/openflowsheet`,
#: whose tree is the archive's v0.1.0 tree but which has none of its history (R-150).
PUBLIC_ROOT = "5a350199f1334e52cfd789109a0e1dc944ef328c"
#: 0.2.0a1 as released: the commit tagged `v0.2.0a1` (2026-10-17; release run 39045791146), R-456.
ALPHA_TAG_COMMIT = "423ae9c54d903f9dcf0ea90fe9639222c1acbda4"
#: 0.2.0 as released: the commit tagged `v0.2.0` (2026-10-20), R-564.
RELEASE_0_2_0_COMMIT = "5c82b4cc40dd4fefd3dbce45352910006e5dee13"
#: 0.3.0 as released: the commit tagged `v0.3.0` (2026-10-31; release run 41186226024).
RELEASE_0_3_0_COMMIT = "b8f47a044ea5ee2a89230ff95bd6a934f541f615"


#: Lines a test reports on every run, passing or failing; `pytest_terminal_summary` prints them
#: (R-796, C1: T07 THM-09/4's uncapped record length, so CI's `-q` logs carry it).
TERMINAL_REPORT: list[str] = []


#: Under pytest-xdist the fixtures below run in the workers and the terminal summary on the
#: controller: each worker hands its counts, report lines and audit findings over in
#: `config.workeroutput`, and the controller sums them in `_XdistForwarding.pytest_testnodedown`.
#: `None` without xdist.
FORWARDED: dict[str, Any] | None = None
MSG_COUNT_PREFIXES = ("MSG WO-6:", "MSG WO-5a:")


def _msg_run_results_line(seen: int, failed: int) -> str:
    return (
        f"MSG WO-6: {seen} run results checked, {failed} with a "
        "failure; failure non-null iff a failure_bundle output in every one"
    )


def _msg_bundles_line(scanned: int) -> str:
    return f"MSG WO-5a: {scanned} bundles scanned; no sidecar key in any written document"


class _XdistForwarding:
    """The controller's xdist hook, registered only where xdist is loaded (the hook is unknown
    to pluggy without it)."""

    def pytest_testnodedown(self, node: Any, error: Any) -> None:
        """Sum the counts and collect the lines a worker forwarded."""
        global FORWARDED
        if FORWARDED is None:
            FORWARDED = {"results": [0, 0], "bundles": 0, "report": [], "findings": []}
        output = getattr(node, "workeroutput", None)
        if not output or "msg_results" not in output:
            return  # a worker that crashed forwards nothing
        FORWARDED["results"][0] += output["msg_results"][0]
        FORWARDED["results"][1] += output["msg_results"][1]
        FORWARDED["bundles"] += output["msg_bundles"]
        FORWARDED["report"] += output["msg_report"]
        FORWARDED["findings"] += output["msg_findings"]


def pytest_terminal_summary(terminalreporter: Any) -> None:
    """Print `TERMINAL_REPORT`'s lines at the end of the run, then MSG-G3's findings."""
    lines = list(TERMINAL_REPORT)
    findings = _msg_audit_findings()
    if FORWARDED is not None:
        lines += [
            _msg_run_results_line(*FORWARDED["results"]),
            _msg_bundles_line(FORWARDED["bundles"]),
        ]
        lines += FORWARDED["report"]
        findings += FORWARDED["findings"]
        lines = list(dict.fromkeys(lines))
        findings = sorted(set(findings))
    for line in lines:
        terminalreporter.write_line(line)
    for line in findings:
        terminalreporter.write_line(line, red=True)


# -- MSG-G6 (design note §3.6): the corpus's golden texts -------------------------------------


def pytest_addoption(parser: Any) -> None:
    parser.addoption(
        "--msg-update",
        action="store_true",
        default=False,
        help="rewrite the stored texts of tests/fixtures/msg/corpus.yaml (MSG-G6); review the diff",
    )


# -- MSG-G3 (design note §4.2.8): the runtime audit of emitted codes ---------------------------


def pytest_configure(config: Any) -> None:
    """Every code the package emits at the four audit hooks must have a catalogue entry."""
    # ADR 0076 I-14: the test process installs the catalogue's before-freeze hook, as every entry
    # point does.
    import openflowsheet.registry  # noqa: F401
    from openflowsheet.messages import audit

    audit.enable()
    if config.pluginmanager.hasplugin("xdist"):
        config.pluginmanager.register(_XdistForwarding(), "msg-xdist-forwarding")


def _msg_audit_findings() -> list[str]:
    from openflowsheet.messages import audit

    auditor = audit.auditor
    if auditor is None:
        return []
    lines = [
        f"MSG-G3 miss: {code} (first emitted by {where})" for code, where in auditor.misses.items()
    ]
    lines += [f"MSG-G3 defect: {key} (in {where!r})" for key, where in auditor.defects.items()]
    return sorted(lines)


def pytest_sessionfinish(session: Any, exitstatus: int) -> None:
    """MSG-G3: a code without an entry, or a rendering defect, fails the session."""
    forwarded = FORWARDED["findings"] if FORWARDED is not None else []
    if (_msg_audit_findings() or forwarded) and exitstatus == 0:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
    workeroutput = getattr(session.config, "workeroutput", None)
    if workeroutput is not None:  # an xdist worker: forward to the controller
        workeroutput["msg_results"] = list(RUN_RESULTS_SEEN)
        workeroutput["msg_bundles"] = BUNDLES_SCANNED[0]
        workeroutput["msg_report"] = [
            line for line in TERMINAL_REPORT if not line.startswith(MSG_COUNT_PREFIXES)
        ]
        workeroutput["msg_findings"] = _msg_audit_findings()


# -- MSG WO-6 (design note §4.8): the converse of `RunResult.failure`'s invariant --------------

#: Every run result the suite built: (results, with a failure).
RUN_RESULTS_SEEN = [0, 0]


@pytest.fixture(autouse=True, scope="session")
def _msg_failure_iff_failure_bundle() -> Any:
    """Every `RunResult` `_run_result` builds has `failure` non-null iff its outputs hold a
    `failure_bundle` (`__post_init__` checks one direction; this wrapper checks the other, over
    every solve the suite reads back). The count goes to the terminal summary."""
    from openflowsheet.application.job_service import JobService

    built = JobService._run_result

    def checked(self: Any, job: Any, **keywords: Any) -> Any:
        result = built(self, job, **keywords)
        bundled = any(output.kind == "failure_bundle" for output in result.outputs)
        assert (result.failure is not None) == bundled, (job.job_id, result.outputs)
        RUN_RESULTS_SEEN[0] += 1
        RUN_RESULTS_SEEN[1] += result.failure is not None
        return result

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(JobService, "_run_result", checked)
        yield
    TERMINAL_REPORT.append(_msg_run_results_line(*RUN_RESULTS_SEEN))


#: MSG §4.6: bundles the suite wrote, scanned for the sidecar's keys.
BUNDLES_SCANNED = [0]
SIDECAR_KEYS = (b'"diagnosis":', b'"diagnostic":')


@pytest.fixture(autouse=True, scope="session")
def _msg_sidecar_in_no_bundle() -> Any:
    """MSG §4.6's carrier rule (WO-5a): no artifact, event or manifest of any bundle the suite
    writes holds the key `diagnosis` or `diagnostic`; the sidecar lives only in the job store's
    `run.diagnosis`. Wraps `write_bundle` where the two session paths import it."""
    import openflowsheet.application.revision_run as revision_run
    import openflowsheet.application.run_session as session
    import openflowsheet.run.bundle as bundle

    written = bundle.write_bundle

    def scanned(directory: Any, manifest: Any, artifacts: Any) -> Any:
        complete = written(directory, manifest, artifacts)
        for path in Path(directory).rglob("*.json"):
            content = path.read_bytes()
            assert not any(key in content for key in SIDECAR_KEYS), path
        BUNDLES_SCANNED[0] += 1
        return complete

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(revision_run, "write_bundle", scanned)
        monkeypatch.setattr(session, "write_bundle", scanned)
        yield
    TERMINAL_REPORT.append(_msg_bundles_line(BUNDLES_SCANNED[0]))


def _git_ok(*arguments: str) -> bool:
    completed = subprocess.run(["git", *arguments], cwd=REPO_ROOT, capture_output=True)
    return completed.returncode == 0


def require_archived_history(*commits: str, in_history_of_head: bool = False) -> None:
    """Skip the calling test unless each of `commits`, pre-0.1.0 commits the test reads, is in
    this repository (`git cat-file -e`) and, with `in_history_of_head`, an ancestor of `HEAD`.

    The development history up to v0.1.0 is archived in the private `openflowsheet-dev`; the
    public repository starts at `PUBLIC_ROOT` without it (R-150). A test that reads the log or a
    range of `HEAD` needs the commit in `HEAD`'s history, not only in the object store (a
    worktree of a development checkout holds the archive's objects beside the public line).
    Where the history is present, the test runs unchanged.
    """
    for commit in commits:
        present = _git_ok("cat-file", "-e", f"{commit}^{{commit}}")
        if not present or (
            in_history_of_head and not _git_ok("merge-base", "--is-ancestor", commit, "HEAD")
        ):
            pytest.skip(f"{ARCHIVED_HISTORY}: {commit} is not in this repository's history")


def in_public_root(path: Path) -> bool:
    """Whether `path` (under `REPO_ROOT`) is a file of v0.1.0 as `PUBLIC_ROOT` released it."""
    return _git_ok("cat-file", "-e", f"{PUBLIC_ROOT}:{path.relative_to(REPO_ROOT).as_posix()}")


def sha256_of(path: Path) -> str:
    """Return the SHA-256 hex digest of a file's exact bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_yaml(path: Path) -> Any:
    """Load one YAML document with the safe loader."""
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """The repository root that contains docs/, schemas/, src/, benchmarks/ and evidence/."""
    return REPO_ROOT


@pytest.fixture(scope="session")
def reference_values() -> dict[str, Any]:
    """Fable's 20-digit SYN-001 reference values, independent of the oracle implementation.

    Read-only. It is never regenerated from the oracle: doing so would turn an independent
    expectation into a self-generated regression fixture (CLAUDE.md, "Scientific conduct").
    """
    loaded = load_yaml(REPO_ROOT / "benchmarks" / "syn001" / "reference_values.yaml")
    assert isinstance(loaded, dict)
    return loaded


@pytest.fixture(scope="session")
def registry() -> dict[str, Any]:
    """`benchmarks/registry.yaml`: the registered case semantics, tolerances and budgets."""
    loaded = load_yaml(REPO_ROOT / "benchmarks" / "registry.yaml")
    assert isinstance(loaded, dict)
    return loaded
