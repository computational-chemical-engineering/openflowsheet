"""Shared fixtures for the repository test suite (P00 baseline, extended by P01)."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The reason a test that reads the pre-0.1.0 development history skips where that history is not.
ARCHIVED_HISTORY = "pre-0.1.0 development history is archived in openflowsheet-dev (R-150)"
#: v0.1.0 on the public line: the root commit of `computational-chemical-engineering/openflowsheet`,
#: whose tree is the archive's v0.1.0 tree but which has none of its history (R-150).
PUBLIC_ROOT = "5a350199f1334e52cfd789109a0e1dc944ef328c"
#: 0.2.0a1 as released: the commit tagged `v0.2.0a1` (2026-10-17; release run 39045791146), R-456.
ALPHA_TAG_COMMIT = "423ae9c54d903f9dcf0ea90fe9639222c1acbda4"
#: 0.2.0 as released: the commit tagged `v0.2.0` (2026-10-20), R-564.
RELEASE_0_2_0_COMMIT = "5c82b4cc40dd4fefd3dbce45352910006e5dee13"


#: Lines a test reports on every run, passing or failing; `pytest_terminal_summary` prints them
#: (R-796, C1: T07 THM-09/4's uncapped record length, so CI's `-q` logs carry it).
TERMINAL_REPORT: list[str] = []


def pytest_terminal_summary(terminalreporter: Any) -> None:
    """Print `TERMINAL_REPORT`'s lines at the end of the run, then MSG-G3's findings."""
    for line in TERMINAL_REPORT:
        terminalreporter.write_line(line)
    for line in _msg_audit_findings():
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
    from openflowsheet.messages import audit

    audit.enable()


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
    if _msg_audit_findings() and exitstatus == 0:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


# -- MSG WO-6 (design note §4.8): the converse of `RunResult.failure`'s invariant --------------

#: Every run result the suite built: (results, with a failure).
RUN_RESULTS_SEEN = [0, 0]


@pytest.fixture(autouse=True, scope="session")
def _msg_failure_iff_failure_bundle() -> Any:
    """Every `RunResult` `_run_result` builds has `failure` non-null iff its outputs hold a
    `failure_bundle` (`__post_init__` checks one direction; this wrapper checks the other, over
    every solve the suite reads back). The count goes to the terminal summary."""
    from openflowsheet.application.local import LocalApplication

    built = LocalApplication._run_result

    def checked(self: Any, job: Any) -> Any:
        result = built(self, job)
        bundled = any(output.kind == "failure_bundle" for output in result.outputs)
        assert (result.failure is not None) == bundled, (job.job_id, result.outputs)
        RUN_RESULTS_SEEN[0] += 1
        RUN_RESULTS_SEEN[1] += result.failure is not None
        return result

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(LocalApplication, "_run_result", checked)
        yield
    TERMINAL_REPORT.append(
        f"MSG WO-6: {RUN_RESULTS_SEEN[0]} run results checked, {RUN_RESULTS_SEEN[1]} with a "
        "failure; failure non-null iff a failure_bundle output in every one"
    )


#: MSG §4.6: bundles the suite wrote, scanned for the sidecar's keys.
BUNDLES_SCANNED = [0]
SIDECAR_KEYS = (b'"diagnosis":', b'"diagnostic":')


@pytest.fixture(autouse=True, scope="session")
def _msg_sidecar_in_no_bundle() -> Any:
    """MSG §4.6's carrier rule (WO-5a): no artifact, event or manifest of any bundle the suite
    writes holds the key `diagnosis` or `diagnostic`; the sidecar lives only in the job store's
    `run.diagnosis`. Wraps `write_bundle` where the two session paths import it."""
    import openflowsheet.application.revision_run as revision_run
    import openflowsheet.run.session as session

    written = session.write_bundle

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
    TERMINAL_REPORT.append(
        f"MSG WO-5a: {BUNDLES_SCANNED[0]} bundles scanned; no sidecar key in any written document"
    )


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
