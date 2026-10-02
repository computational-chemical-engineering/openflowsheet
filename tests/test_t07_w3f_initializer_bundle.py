"""T07 W3f: the design note's ruling round 3, Q1 — a registered initializer's refusal gets a
failure bundle (`verify.failure.initializer_bundle`).

Design note `docs/design/T07-jobs-and-bindings.md`, "Ruling round 3", Q1-A1…A4. Q1-A6 (the job) is
in `test_t07_w4a_jobs.py`; Q1-A5 is the identity protocol (`docs/t07-measurements.md`, W3f).

The expected bundle documents are item 3's table written out as literals; the digests the note
gives, computed by a prototype of the rule and not by the code under test, are a cross-check only.

**T08 build-first Amendment 1 §Am1.6 (Q-P1-1).** Item 3's `replay_identity` row is amended: the
bundle carries the executed plan's four ids, the values the run manifest records. The expected
document takes them from the manifest; the new canonical digests are pinned beside the note's,
and the move is shown to be the substitution `"" → id` only: the bundle with the four values set
back to `""` is the note's document, byte for byte.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from t07_corpus import CORPUS
from test_k04_schemas import errors_for

import openflowsheet.application.revision_run as revision_run
from openflowsheet.application.policies import DEFAULT_POLICY_ID, resolve_policy
from openflowsheet.application.revision_run import (
    Route,
    RunUnsupportedError,
    reproduce_bundle,
    run_revision_session,
    select_route,
    solve_route,
)
from openflowsheet.canonical import canonical_json
from openflowsheet.orchestrator.executor import StepResult
from openflowsheet.orchestrator.trace import Counters, Trace
from openflowsheet.run.bundle import read_artifact, verify_bundle
from openflowsheet.run.identity import r0_projection
from openflowsheet.verify.certificate import CheckPolicy
from openflowsheet.verify.failure import initializer_bundle, initializer_source

COUNTERS = (
    "property_calls",
    "requested_evaluations",
    "cache_hits",
    "residual_calls",
    "jacobian_calls",
    "factorizations",
)


# == Q1: a registered initializer's refusal gets a failure bundle ===============================


#: The replay identity's four members (item 3's table as amended, §Am1.6).
IDENTITY = ("constants_sha256", "model_version", "plan_id", "policy_id")


def _expected(message: str, source: str, identity: Mapping[str, str]) -> dict[str, Any]:
    """Q1 item 3's table, as amended by §Am1.6: `identity` is the run manifest's four ids."""
    return {
        "outcome": "INITIALIZATION_FAILED",
        "taxonomy": "initialization and recycle failures",
        "observations": {
            "attempts": 0,
            "closing_event": "region_closed",
            "counters": dict.fromkeys(COUNTERS, 0),
            "iterations": 0,
            "last_linear": None,
            "message": message,
            "residual_inf_unscaled": None,
        },
        "inferred_causes": [],
        "implicated_sources": [source],
        "attempt_tree": [],
        "replay_identity": {name: identity[name] for name in IDENTITY},
        "best_checkpoint": None,
        "check_report": None,
        "suggested_actions": [
            {
                "action": "supply_initial_guess",
                "preconditions": (
                    "the initialization and recycle failures reported above is what a reader "
                    "would act on"
                ),
                "requires_permission": True,
            }
        ],
    }


#: name -> (route, message, source, the note's `document_sha256` with the four ids empty, its
#: length in bytes).
Q1_ROWS: Mapping[str, tuple[str, str, str, str, int]] = {
    "SYN-001-UL-C3X": (
        "revision_eo",
        "initializer_failed(U-HX): temperature_cross(cold_end)",
        "U-HX",
        "e07f19c53fd3861e99d80dd40ad671afbd4029802d53f267024926473bfa379f",
        792,
    ),
    "SYN-001-A02-360-no-guess": (
        "legacy_eo",
        "missing_initial_guess(S3.T)",
        "S3.T",
        "6eeb77579a8d4c04af9059aa0cc2de7ef2d6e199091fede1c54226e49bbe6368",
        766,
    ),
}
#: §Am1.6: name -> (`document_sha256`, length) with the four ids filled, measured at T08 by this
#: test's substitution proof (the move from `Q1_ROWS`'s is `"" → id` in four members only), and
#: re-registered for the rename to `openflowsheet` (R-149): the ids name the SYN-001 provider's new
#: self-hash; with the pre-rename one they are `Q1_FILLED_PRE_RENAME`
#: (`tests/test_t08_rename_substitution.py`).
Q1_FILLED: Mapping[str, tuple[str, int]] = {
    "SYN-001-UL-C3X": ("e44e68a07a521553fbe01d7af3f50fb81eb07230980f3c544e162afd463a3fac", 1062),
    "SYN-001-A02-360-no-guess": (
        "c0c0c1f6cb4fa63cb206caabbf24853fcb7122fbee1bad2f837a77b879cfc349",
        1006,
    ),
}
Q1_FILLED_PRE_RENAME: Mapping[str, tuple[str, int]] = {
    "SYN-001-UL-C3X": ("7a3c76f16ba5c6a6ce0ac7a1f08876e26f5e2b460e1d64f2bbcb20ec39eab695", 1062),
    "SYN-001-A02-360-no-guess": (
        "f2cc8c5aabc33af439379b10a792909a0e1f6724e32145716658d897001393d3",
        1006,
    ),
}


@pytest.fixture(scope="module")
def sessions(tmp_path_factory: pytest.TempPathFactory) -> dict[str, dict[str, Any]]:
    return run_sessions(tmp_path_factory.mktemp("w3f"))


def run_sessions(root: Path) -> dict[str, dict[str, Any]]:
    """Each Q1 row through `run_revision_session` under `"default"`, and its same-host rerun."""
    out: dict[str, dict[str, Any]] = {}
    for name in Q1_ROWS:
        document = CORPUS[name]()
        route = select_route(document)
        assert isinstance(route, Route), name
        policy = resolve_policy(DEFAULT_POLICY_ID, route.solve_path)
        assert policy is not None
        directory = root / name
        manifest = run_revision_session(
            route,
            document,
            directory,
            run_id=f"run-{name}",
            policy=policy,
            check_policy=CheckPolicy(),
            policy_requested=DEFAULT_POLICY_ID,
        )
        reproduction = reproduce_bundle(
            directory, rerun=True, rerun_directory=root / f"{name}.rerun", run_id="rerun"
        )
        out[name] = {
            "route": route,
            "manifest": manifest,
            "directory": directory,
            "rerun_directory": root / f"{name}.rerun",
            "reproduction": reproduction,
        }
    return out


@pytest.mark.parametrize("name", sorted(Q1_ROWS))
def test_q1_a1_the_bundle_is_item_3s_table(sessions: dict[str, Any], name: str) -> None:
    solve_path, message, source, digest, size = Q1_ROWS[name]
    session = sessions[name]
    assert session["route"].solve_path == solve_path
    manifest, directory = session["manifest"], session["directory"]
    assert (manifest.outcome, manifest.verification_status) == ("INITIALIZATION_FAILED", None)
    names = set(manifest.artifacts)
    assert "failure-bundle.json" in names
    assert not names & {"solution-certificate.json", "solution-state.json"}
    assert not (directory / "artifacts" / "solution-state.json").exists()
    bundle = read_artifact(directory, "failure-bundle.json")
    assert errors_for("failure_bundle", bundle) == []
    identity = {name: getattr(manifest, name) for name in IDENTITY}
    assert all(identity.values()), identity
    assert identity["plan_id"].endswith(f"-{manifest.policy_id}-execution")
    assert bundle == _expected(message, source, identity)
    data = canonical_json(bundle)
    assert (hashlib.sha256(data).hexdigest(), len(data)) == Q1_FILLED[name]
    # §Am1.6's substitution proof: the four ids set back to "" give the note's document, whose
    # digest (a prototype's, not this code's) is the cross-check.
    emptied = canonical_json({**bundle, "replay_identity": dict.fromkeys(IDENTITY, "")})
    assert (len(emptied), hashlib.sha256(emptied).hexdigest()) == (size, digest)


def _event(trace: Trace, kind: str, counters: Counters, **fields: Any) -> None:
    trace.record(
        kind=kind,
        attempt=0,
        iteration=0,
        signature=(),
        state_sha256="",
        residual_inf_unscaled=float("nan"),
        merit=float("nan"),
        counters=counters,
        **fields,
    )


def test_q1_a2_the_counters_are_the_steps_own_difference() -> None:
    """Opened at (1, …, 6) and closed at (11, …, 66): the step metered (10, …, 60). An earlier
    step's events, with an attempt of their own, are not the step's."""
    message = "initializer_failed(U-HX): temperature_cross(cold_end)"
    opened = Counters(*range(1, 7))
    closed = Counters(*(11 * value for value in range(1, 7)))
    trace = Trace()
    trace.open_step(0)
    _event(trace, "region_opened", Counters())
    _event(trace, "attempt_closed", Counters(), outcome="MAX_ITERATIONS")
    _event(trace, "region_closed", opened, outcome="CONVERGED")
    trace.close_step()
    trace.open_step(1)
    _event(trace, "region_opened", opened)
    _event(trace, "initializer_rejected", opened, message=message)
    _event(trace, "region_closed", closed, outcome="INITIALIZATION_FAILED", message=message)
    trace.close_step()
    step = StepResult(1, "solve_eo", ("U-HX",), "INITIALIZATION_FAILED", message=message)
    document = initializer_bundle(step, trace).as_document()
    assert [document["observations"]["counters"][name] for name in COUNTERS] == [
        10,
        20,
        30,
        40,
        50,
        60,
    ]
    assert document["observations"]["attempts"] == 0
    assert document["attempt_tree"] == []
    assert document["implicated_sources"] == ["U-HX"]


@pytest.mark.parametrize(
    ("message", "source"),
    [
        ("initializer_failed(U-HX): temperature_cross(cold_end)", "U-HX"),
        ("missing_initial_guess(S3.T)", "S3.T"),
        ("initializer_failed(U-PHF): ph_outside_domain(above)", "U-PHF"),
        ("initializer_failed U-HX", None),
        ("missing_initial_guess(S3.T) extra", None),
        ("initializer_failed(U-HX): ", None),
        ("", None),
        ("specification_region_unsupported(revision_flowsheet)", None),
    ],
)
def test_q1_a3_initializer_source(message: str, source: str | None) -> None:
    assert initializer_source(message) == source


def test_q1_a3_an_unaccepted_message_stays_unmapped(monkeypatch: pytest.MonkeyPatch) -> None:
    """UL-C3X's failed step with its message changed in one feature: the mapping refuses it."""
    execute_plan = revision_run.execute_plan

    def garbled(**kwargs: Any) -> Any:
        run = execute_plan(**kwargs)
        last = replace(run.steps[-1], message="initializer_failed U-HX")
        return replace(run, steps=(*run.steps[:-1], last))

    monkeypatch.setattr(revision_run, "execute_plan", garbled)
    document = CORPUS["SYN-001-UL-C3X"]()
    route = select_route(document)
    assert isinstance(route, Route)
    policy = resolve_policy(DEFAULT_POLICY_ID, route.solve_path)
    assert policy is not None
    with pytest.raises(RunUnsupportedError) as raised:
        solve_route(route, document, policy=policy, check_policy=CheckPolicy())
    assert raised.value.code == "failure_bundle_unmapped(INITIALIZATION_FAILED,solve_eo,NoneType)"


@pytest.mark.parametrize("name", sorted(Q1_ROWS))
def test_q1_a4_integrity_rerun_and_r0(sessions: dict[str, Any], name: str) -> None:
    session = sessions[name]
    directory = session["directory"]
    assert verify_bundle(directory).ok
    report = session["reproduction"].report
    assert report.verdict == "MATCH", (report.reasons, report.differences[:5])
    rerun = session["rerun_directory"] / "artifacts" / "failure-bundle.json"
    assert rerun.read_bytes() == (directory / "artifacts" / "failure-bundle.json").read_bytes()
    manifest = session["manifest"]
    artifacts = {entry: read_artifact(directory, entry) for entry in manifest.artifacts}
    assert r0_projection(artifacts)["failure"] == {
        "outcome": "INITIALIZATION_FAILED",
        "taxonomy": "initialization and recycle failures",
        "implicated_sources": [Q1_ROWS[name][2]],
        "suggested_actions": ["supply_initial_guess"],
        "solver_counters": {"residual_calls": 0, "jacobian_calls": 0, "factorizations": 0},
    }
