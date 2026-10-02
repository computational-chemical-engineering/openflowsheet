"""T08.A17: CLI `replay --rerun` is the application's `reproduce_bundle` (T08 review 2, Ruling 11).

T07 kept a CLI fallback (design note §12.3, §17 D-Q6): a bundle whose `run_id` was no registered
case was compared with SYN-001-nominal's rerun. The CLI never read `revision.json`, so every
revision-built bundle — a job id is not a registered case — was compared with another problem and
ended a structural `MISMATCH`, exit 1. Ruling 11 removes the fallback:

- (a) a revision-built bundle reruns its **recorded** route, `MATCH`, exit 0;
- (b) a K05 bundle whose `run_id` is no registered case is not rerun: `NOT_RUN`, reason
  `rerun_unsupported(no_revision_document)`, exit 1.
"""

from __future__ import annotations

import contextlib
import io
from pathlib import Path
from typing import Any

import pytest
from t07_corpus import CORPUS

from openflowsheet.application import revision_run
from openflowsheet.application.cli import main
from openflowsheet.application.policies import DEFAULT_POLICY_ID, resolve_policy
from openflowsheet.application.revision_run import (
    Route,
    registered_case,
    registered_flowsheet,
    run_revision_session,
    select_route,
)
from openflowsheet.run.bundle import read_artifact, read_manifest
from openflowsheet.run.manifest import THREAD_VARIABLES
from openflowsheet.run.session import run_session
from openflowsheet.verify.certificate import CheckPolicy


@pytest.fixture(autouse=True)
def single_threaded(monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR 0007 D4: an exact replay needs the thread variables pinned, in the run and the rerun."""
    for variable in THREAD_VARIABLES:
        monkeypatch.setenv(variable, "1")


@pytest.fixture
def reruns(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Any]]:
    """Every rerun `reproduce_bundle` starts: `("revision", solve_path)` or `("registered", id)`."""
    started: list[tuple[str, Any]] = []
    revision_session = revision_run.run_revision_session
    registered = revision_run.rerun_registered

    def on_route(route: Route, *args: Any, **kwargs: Any) -> Any:
        started.append(("revision", route.solve_path))
        return revision_session(route, *args, **kwargs)

    def on_case(case: Any, *args: Any, **kwargs: Any) -> Any:
        started.append(("registered", case))
        return registered(case, *args, **kwargs)

    monkeypatch.setattr(revision_run, "run_revision_session", on_route)
    monkeypatch.setattr(revision_run, "rerun_registered", on_case)
    return started


def replay_rerun(bundle: Path) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(["replay", str(bundle), "--rerun"])
    return code, out.getvalue()


def test_a17_a_revision_built_bundle_reruns_its_recorded_route(
    tmp_path: Path, reruns: list[tuple[str, Any]]
) -> None:
    document = CORPUS["SYN-001-nominal"]()
    route = select_route(document)
    assert isinstance(route, Route)
    policy = resolve_policy(DEFAULT_POLICY_ID, route.solve_path)
    assert policy is not None
    bundle = tmp_path / "bundle"
    run_revision_session(
        route,
        document,
        bundle,
        run_id="job-000001",
        policy=policy,
        check_policy=CheckPolicy(),
        policy_requested=DEFAULT_POLICY_ID,
    )
    manifest, _ = read_manifest(bundle)
    # The case T07's fallback got wrong: a revision bundle whose run id is no registered case.
    assert "revision.json" in manifest.artifacts
    assert registered_case(manifest.run_id) is None
    recorded = read_artifact(bundle, "solve-path.json")["solve_path"]

    code, out = replay_rerun(bundle)
    assert reruns == [("revision", recorded)]
    assert "verdict   MATCH\n" in out
    assert code == 0


def test_a17_an_unregistered_k05_bundle_is_not_rerun(
    tmp_path: Path, reruns: list[tuple[str, Any]]
) -> None:
    case = registered_case("SYN-001-nominal")
    assert case is not None
    bundle = tmp_path / "bundle"
    run_session(registered_flowsheet(case), bundle, run_id="not-a-registered-case")
    manifest, _ = read_manifest(bundle)
    assert "revision.json" not in manifest.artifacts
    assert registered_case(manifest.run_id) is None

    code, out = replay_rerun(bundle)
    assert reruns == []
    assert "verdict   NOT_RUN\n" in out
    assert out.rstrip("\n").splitlines()[-1] == "  reason  rerun_unsupported(no_revision_document)"
    assert code == 1
