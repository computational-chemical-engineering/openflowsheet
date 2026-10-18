"""Shared fixtures for the W27 campaign-record tests (registration §23, WO-17a): a drawn campaign
directory, its confirmation, stub canary attempts and a stub campaign, all without a model call.

The committed tree is clean only after a commit, so the tests that need a clean tree replace
`harness.git_state` (`clean_head`); every other check reads the real HEAD.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Final

import pytest

from benchmarks.m06.w27 import harness, preflight, registration, sample, stubs

#: Registration §23.6, W27-A77: the two model ids of `p7_states`.
MODELS: Final[Mapping[str, str]] = {"M1": "claude-test-m1", "M2": "claude-test-m2"}
#: W27-A76: "K is a fixed other 40-hex commit".
K: Final[str] = "f" * 40
NAME: Final[str] = "c"


def head() -> str:
    return preflight._git("rev-parse", "HEAD")


def clean_head(monkeypatch: pytest.MonkeyPatch) -> str:
    """HEAD, with `harness.git_state` reporting it and a clean tree."""
    commit = head()
    monkeypatch.setattr(
        harness, "git_state", lambda runs_root: {"commit": commit, "tree_clean": True}
    )
    return commit


def drawn(runs_root: Path, coverage: Mapping[str, Any] | None = None, name: str = NAME) -> Path:
    """`runs_root/<name>/` with `coverage.json` (the committed Tier 0 one unless given) and its
    registered draw `sample.json`."""
    directory = runs_root / name
    directory.mkdir(parents=True)
    data = (
        registration.COVERAGE_JSON.read_bytes() if coverage is None else registration.dump(coverage)
    )
    (directory / "coverage.json").write_bytes(data)
    document = sample.sample_document(json.loads(data), data)
    (directory / "sample.json").write_bytes(registration.dump(document))
    return directory


def context(directory: Path, **changes: Any) -> preflight.Campaign:
    values: dict[str, Any] = {
        "name": directory.name,
        "runs_root": directory.parent,
        "coverage_path": directory / "coverage.json",
        "sample_path": directory / "sample.json",
        "model": MODELS["M1"],
        "claude_code_version": stubs.STUB_VERSION,
    }
    return preflight.Campaign(**{**values, **changes})


def canary_cases(directory: Path) -> list[str]:
    cases: list[str] = json.loads((directory / "sample.json").read_bytes())["canaries"]
    return cases


def canary_chain(directory: Path) -> dict[str, str]:
    """The digests a canary attempt's `run.json` names (registration §23.2)."""
    return {
        "coverage_sha256": registration.sha256_file(directory / "coverage.json"),
        "sample_sha256": registration.sha256_file(directory / "sample.json"),
        "confirmation_sha256": registration.sha256_file(directory / harness.CONFIRMATION_FILE),
    }


def stub_campaign(runs_root: Path, commit: str) -> preflight.Campaign:
    """Records 1–4 of §23.2 at `commit`: coverage (the committed one with its snapshot commit set
    to `commit`), the draw, the confirmation (needs `clean_head`) and three passing stub canary
    attempts, 01 without `--model` pinning M1."""
    coverage = json.loads(registration.COVERAGE_JSON.read_bytes())
    coverage["snapshot"]["git_commit"] = commit
    directory = drawn(runs_root, coverage)
    harness.confirm(directory.name, runs_root=runs_root)
    chain = canary_chain(directory)
    for n, case_id in enumerate(canary_cases(directory), start=1):
        stubs.canary_attempt(
            directory,
            n,
            case_id,
            commit=commit,
            passed=True,
            model=None if n == 1 else MODELS["M1"],
            init_model=MODELS["M1"],
            chain=chain,
        )
    return context(directory)


def passing(campaign: preflight.Campaign) -> dict[str, Any]:
    del campaign
    return {"passed": True, "not_run": "replaced in this test"}


#: P1–P8 with P2 (the generator's checks against the archive) and P3 (a snapshot rebuilt at
#: HEAD) replaced: the rest are the real checks.
FAST_CHECKS: Final[Mapping[str, Callable[[preflight.Campaign], dict[str, Any]]]] = {
    **preflight.CHECKS,
    "P2": passing,
    "P3": passing,
}


class StopRunsError(Exception):
    pass


def stub_runs(commit: str, stop_after: int) -> Callable[..., Path]:
    """A `run_one` that records a stub `run.json` (commit, tree, the digests it is given) and
    stops the campaign after `stop_after` runs."""
    made: list[int] = []

    def run_one(case_id: str, order: int, campaign: str, **keywords: Any) -> Path:
        run_dir = keywords["runs_root"] / campaign / f"{order:02d}-{case_id}"
        run_dir.mkdir(parents=True)
        record = {
            "commit": commit,
            "tree_clean": True,
            "model": keywords["config"].model,
            "coverage_sha256": registration.sha256_file(keywords["coverage_path"]),
            **keywords["chain"],
        }
        (run_dir / "run.json").write_text(json.dumps(record), encoding="utf-8")
        made.append(order)
        if len(made) == stop_after:
            raise StopRunsError
        return run_dir

    return run_one
