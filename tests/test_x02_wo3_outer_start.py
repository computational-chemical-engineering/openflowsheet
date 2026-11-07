"""X02 WO-3: the declared outer start w₀ (ADR 0070 D3, D9; design note
`docs/design/X02-warm-starts.md` §5.2, §5.4, §5.7, §5.8; gate G3 and G6's W14-path cases) on the
stand-in loop (`benchmarks/m02/c1-loop-standin.json`).

J_c is a cold `default` solve of the loop. Every cold experiment it ran is in the project's
experiment store afterwards, so a later cold coupling serves each of them from the cache: the
reference for "the record is the cold coupling's alone" is J_c′, a second cold run, under the
same cache state (build decision D-10).

- **G3 (a)** `job_id = J_c`, same revision: VERIFIED in one outer iteration (k = 0), the final w
  bitwise J_c's, one experiment evaluated (a cache hit: the k = 0 inner solve from J_c's
  solution state returns its inlet bit for bit).
- **(b)** iterate = J_c's w + (0.01, +5 K): VERIFIED, and the Δû bound holds.
- **(c)** an iterate whose k = 0 inner solve fails: `rejected`
  `warm_start_rejected(coupling_opening)`, no experiment at w₀, `external-coupling.json` byte-equal
  to J_c′'s. No in-bounds w makes the inner solve of the registered loop fail (every corner of
  the bounds converges), so the loop is taken with its H₂ make-up lowered to 0.725 mol/s: X = 0.95
  then asks for more H₂ than the loop holds, while the stand-in's fixed point X = 0.25 does not
  (build decision D-11). The test first proves the inner solve fails at that w and converges at
  the variant's `coupling.initial`.
- **(d)** an iterate naming a non-external instance: admitted (A2 holds), `rejected`
  `…(coupling_compatibility)`, record byte-equal to J_c′'s.
- **(e)** replay of (a), (b), (c): `MATCH`. **(f)** a forged `coupling.declared`: not `MATCH`.
- **G6, W14 path.** Iterates at the bounds corners (0, −50) and (0.95, 250) end VERIFIED with
  every EXT-COUPLING check passing at the converged state, or not VERIFIED; never VERIFIED with a
  failing check.
- **Records.** The `coupling` sub-record (§5.7), its R0 (§5.7), bounds projections, the
  `absent`/`not_declared` inner members of an iterate-only declaration, the routes without an
  outer iteration (`revision_eo` → `coupling_compatibility`, `legacy_eo` → `route`), integrity at
  resolution, and the trace messages (§5.9).
"""

from __future__ import annotations

import copy
import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from conftest import REPO_ROOT
from t07_corpus import CORPUS
from t07_jobs_support import commit

from openflowsheet.adapters.experiments.runner import ExperimentRunner
from openflowsheet.adapters.experiments.store import ExperimentStore, ListArtifactSink
from openflowsheet.application import coupled_run
from openflowsheet.application.coupled_run import (
    LiveExperiments,
    at_coupling,
    coupling_block,
    external_units,
    iterate_start,
    job_coupling_start,
    solve_coupled,
)
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import dispatch
from openflowsheet.application.policies import resolve_policy
from openflowsheet.application.revision_run import Route, bind_route
from openflowsheet.application.types import ReplayPolicy
from openflowsheet.compiled import EvaluationContext
from openflowsheet.orchestrator.execution import PlanRefusal
from openflowsheet.orchestrator.executor import execute_plan
from openflowsheet.orchestrator.revision import plan_revision
from openflowsheet.orchestrator.trace import Trace
from openflowsheet.run.bundle import read_artifact, read_manifest, write_bundle
from openflowsheet.run.identity import r0_projection
from openflowsheet.thermo.pr_c1 import PrC1Provider

LOOP_PATH = REPO_ROOT / "benchmarks" / "m02" / "c1-loop-standin.json"
COUPLING = "external-coupling.json"
#: D-11: the H₂ make-up at which X = 0.95 is infeasible for the inner solve and X = 0.25 is not.
TIGHT_H2 = 0.725
OPENING_W = (0.95, -50.0)


def _loop(h2: float | None = None) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(LOOP_PATH.read_text(encoding="utf-8"))
    if h2 is not None:
        (spec,) = [s for s in document["specifications"] if s["id"] == "SPEC-S1-n-H2"]
        spec["value"] = h2
    return document


@dataclass(frozen=True)
class Solved:
    job_id: str
    status: str
    verdict: str | None
    bundle: Path
    record_bytes: bytes
    solve_path: dict[str, Any]
    #: `Experiments.evaluate` calls the job made.
    evaluations: int

    @property
    def record(self) -> dict[str, Any]:
        parsed: dict[str, Any] = json.loads(self.record_bytes)
        return parsed

    @property
    def coupling(self) -> dict[str, Any]:
        member: dict[str, Any] = self.solve_path["warm_start"]["coupling"]
        return member


class Counting:
    """Counts `LiveExperiments.evaluate` calls (the experiments a job evaluated, hit or not)."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.calls = 0
        original = LiveExperiments.evaluate

        def counted(experiments: LiveExperiments, *args: Any, **kwargs: Any) -> Any:
            self.calls += 1
            return original(experiments, *args, **kwargs)

        monkeypatch.setattr(LiveExperiments, "evaluate", counted)


def _solve(
    app: LocalApplication,
    counting: Counting,
    revision_id: str,
    warm_start: dict[str, Any] | None = None,
) -> Solved:
    body: dict[str, Any] = {"revision_id": revision_id, "policy_id": "default"}
    if warm_start is not None:
        body["warm_start"] = warm_start
    key = f"x02-wo3-{len(app.list_jobs(limit=200).items)}"
    before = counting.calls
    job = dispatch(app, "submit_job", {"operation": "solve", "idempotency_key": key, "body": body})[
        "job"
    ]
    assert (job["status"], job["error"]) == ("completed", None)
    (ref,) = [output for output in job["outputs"] if output["kind"] == "replay_bundle"]
    row = app.store.artifact(ref["artifact_id"])
    assert row is not None
    bundle = app.files_root / row.relpath
    result = dispatch(app, "get_job_result", {"job_id": job["job_id"]})["run_result"]
    return Solved(
        job["job_id"],
        job["status"],
        result["verification_status"],
        bundle,
        coupling.read_bytes() if (coupling := bundle / "artifacts" / COUPLING).is_file() else b"",
        read_artifact(bundle, "solve-path.json"),
        counting.calls - before,
    )


def _iterate(w: tuple[float, float], unit: str = "reactor") -> dict[str, Any]:
    return {"coupling": {unit: {"X": w[0], "dT_K": w[1]}}}


@dataclass(frozen=True)
class Loop:
    app: LocalApplication
    cold: Solved
    again: Solved
    same: Solved
    near: Solved
    foreign: Solved
    clipped: Solved
    corners: dict[tuple[float, float], Solved]


@pytest.fixture(scope="module")
def loop(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Loop]:
    with (
        pytest.MonkeyPatch.context() as monkeypatch,
        LocalApplication.create(
            tmp_path_factory.mktemp("x02wo3") / "p", project_id="x02-wo3"
        ) as app,
    ):
        counting = Counting(monkeypatch)
        revision_id = commit(app, _loop())
        cold = _solve(app, counting, revision_id)
        again = _solve(app, counting, revision_id)
        same = _solve(app, counting, revision_id, {"job_id": cold.job_id})
        x, dt = cold.record["iterations"][-1]["w"]
        near = _solve(app, counting, revision_id, _iterate((x + 0.01, dt + 5.0)))
        foreign = _solve(app, counting, revision_id, _iterate((0.2, 80.0), unit="mixer"))
        clipped = _solve(app, counting, revision_id, _iterate((1.2, 300.0)))
        corners = {
            w: _solve(app, counting, revision_id, _iterate(w))
            for w in ((0.0, -50.0), (0.95, 250.0))
        }
        yield Loop(app, cold, again, same, near, foreign, clipped, corners)


@dataclass(frozen=True)
class Tight:
    app: LocalApplication
    revision: dict[str, Any]
    cold: Solved
    again: Solved
    opening: Solved


@pytest.fixture(scope="module")
def tight(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Tight]:
    with (
        pytest.MonkeyPatch.context() as monkeypatch,
        LocalApplication.create(
            tmp_path_factory.mktemp("x02wo3t") / "p", project_id="x02-wo3-tight"
        ) as app,
    ):
        counting = Counting(monkeypatch)
        document = _loop(TIGHT_H2)
        revision_id = commit(app, document)
        cold = _solve(app, counting, revision_id)
        again = _solve(app, counting, revision_id)
        opening = _solve(app, counting, revision_id, _iterate(OPENING_W))
        yield Tight(app, document, cold, again, opening)


def _bits(values: list[float]) -> list[str]:
    return [float(value).hex() for value in values]


# -- G3 (a): the same-revision restart ------------------------------------------------------------


def test_g3a_the_same_revision_restart_converges_at_k0_with_w_bitwise(loop: Loop) -> None:
    cold, same = loop.cold.record, loop.same.record
    assert (loop.cold.verdict, loop.same.verdict) == ("VERIFIED", "VERIFIED")
    assert len(cold["iterations"]) == 2
    assert [item["k"] for item in same["iterations"]] == [0]
    assert same["iterations"][0]["step"]["kind"] == "converged"
    assert _bits(same["iterations"][-1]["w"]) == _bits(cold["iterations"][-1]["w"])
    assert loop.same.evaluations == 1
    # Reported (design note G3a, F1): k = 0 was a cache hit — the inner solve from J_c's solution
    # state at J_c's w reproduced its inlet bit for bit.
    assert same["iterations"][0]["units"]["reactor"]["cache_hit"] is True
    assert same["iterations"][0]["inner"]["start"] == "compatible_warm_start"
    member = loop.same.solve_path["warm_start"]
    assert (member["selection"], member["status"]) == ("explicit-v1", "accepted")
    x, dt = cold["iterations"][-1]["w"]
    assert loop.same.coupling == {
        "record": "coupling-start-v1",
        "source": "job",
        "status": "accepted",
        "reason": None,
        "declared": {"reactor": {"X": x, "dT_K": dt}},
        "projections": [],
    }


# -- G3 (b): a neighbouring iterate and the Δû bound ----------------------------------------------


def _final(record: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    block = record["coupling_block"]
    scales = np.array([block["scales"]["X"], block["scales"]["dT_K"]])
    final = record["iterations"][-1]
    entry = final["units"]["reactor"]
    u = np.array(final["w"]) / scales
    r = np.array([entry["r_xi"], entry["r_T"]]) / scales
    return u, r


def test_g3b_a_neighbouring_iterate_verifies_within_the_bound(loop: Loop) -> None:
    assert loop.near.verdict == "VERIFIED"
    assert (loop.near.coupling["source"], loop.near.coupling["status"]) == ("iterate", "accepted")
    u_w, r_w = _final(loop.near.record)
    u_c, r_c = _final(loop.cold.record)
    matrices = [item["step"]["B"] for item in loop.cold.record["iterations"]]
    known = [matrix for matrix in matrices if matrix is not None]
    b_c = np.array(known[-1]) if known else -np.eye(2)
    bound = (
        2.0
        * np.linalg.norm(np.linalg.inv(b_c), np.inf)
        * (np.linalg.norm(r_w, np.inf) + np.linalg.norm(r_c, np.inf))
    )
    assert np.linalg.norm(u_w - u_c, np.inf) <= bound
    # The start is the declared one, not the variant's.
    assert loop.near.record["iterations"][0]["w"] != loop.cold.record["iterations"][0]["w"]


# -- G3 (c): a w₀ whose inner solve fails is rejected at opening -----------------------------------


def _inner_outcome(document: dict[str, Any], w: tuple[float, float]) -> str:
    route = bind_route("revision_coupled", copy.deepcopy(document))
    assert isinstance(route, Route)
    policy = resolve_policy("default", "revision_coupled")
    assert policy is not None
    bound = at_coupling(route.binding, {"reactor": w})
    plan, _ = plan_revision(bound, policy)
    assert not isinstance(plan, PlanRefusal)
    run = execute_plan(plan=plan, flowsheet=bound.flowsheet, spec=bound.spec, policy=policy)
    return str(run.outcome)


def test_g3c_the_inner_solve_fails_at_the_opening_w_and_not_at_the_initial(tight: Tight) -> None:
    """The precondition, independently of the feature."""
    route = bind_route("revision_coupled", copy.deepcopy(tight.revision))
    assert isinstance(route, Route)
    block, _ = coupling_block(external_units(route.binding))
    assert _inner_outcome(tight.revision, OPENING_W) != "CONVERGED"
    assert _inner_outcome(tight.revision, block.initial) == "CONVERGED"


def test_g3c_a_failing_opening_is_rejected_and_the_coupling_starts_cold(tight: Tight) -> None:
    assert tight.opening.coupling == {
        "record": "coupling-start-v1",
        "source": "iterate",
        "status": "rejected",
        "reason": "warm_start_rejected(coupling_opening)",
        "declared": {"reactor": {"X": OPENING_W[0], "dT_K": OPENING_W[1]}},
        "projections": [],
    }
    assert tight.opening.verdict == tight.again.verdict == "VERIFIED"
    # No experiment ran at the rejected w₀, and the record is the cold coupling's alone.
    assert tight.opening.evaluations == tight.again.evaluations == tight.cold.evaluations
    assert tight.opening.record_bytes == tight.again.record_bytes
    assert tight.opening.record["iterations"][0]["w"] == [0.15, 80.0]


# -- G3 (d): an iterate naming a non-external instance ---------------------------------------------


def test_g3d_an_iterate_on_another_instance_is_rejected_for_compatibility(loop: Loop) -> None:
    assert loop.foreign.coupling["status"] == "rejected"
    assert loop.foreign.coupling["reason"] == "warm_start_rejected(coupling_compatibility)"
    assert loop.foreign.coupling["declared"] == {"mixer": {"X": 0.2, "dT_K": 80.0}}
    assert loop.foreign.record_bytes == loop.again.record_bytes
    assert loop.foreign.evaluations == loop.again.evaluations


# -- G3 (e), (f): replay ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", ["same", "near", "opening"])
def test_g3e_replay_reproduces_the_record_and_matches(
    case: str, loop: Loop, tight: Tight, tmp_path: Path
) -> None:
    solved = tight.opening if case == "opening" else getattr(loop, case)
    with LocalApplication.create(tmp_path / "fresh", project_id="x02-wo3-replay") as fresh:
        report = fresh.reproduce(solved.bundle, ReplayPolicy(rerun=True))
    assert report.mode in ("exact_replay", "compatible_reproduction"), report.reasons
    assert report.verdict == "MATCH", report.differences


def test_g3f_a_forged_declared_iterate_does_not_match(loop: Loop, tmp_path: Path) -> None:
    manifest, _ = read_manifest(loop.near.bundle)
    artifacts = {name: read_artifact(loop.near.bundle, name) for name in manifest.artifacts}
    declared = artifacts["solve-path.json"]["warm_start"]["coupling"]["declared"]["reactor"]
    declared["X"] += 0.05
    write_bundle(tmp_path / "forged", manifest, artifacts)
    report = loop.app.reproduce(tmp_path / "forged", ReplayPolicy(rerun=True))
    assert report.verdict != "MATCH"


# -- G6: the W14 path — a far iterate is only ever a start -----------------------------------------


@pytest.mark.parametrize("w", [(0.0, -50.0), (0.95, 250.0)])
def test_g6_a_far_iterate_never_verifies_with_a_failing_coupling_check(
    w: tuple[float, float], loop: Loop
) -> None:
    solved = loop.corners[w]
    assert solved.coupling["source"] == "iterate"
    if solved.verdict == "VERIFIED":
        certificate = read_artifact(solved.bundle, "solution-certificate.json")
        checks = [c for c in certificate["checks"] if c["id"].startswith("EXT-COUPLING:")]
        assert len(checks) == 2
        assert {check["result"] for check in checks} == {"pass"}
        assert solved.record["outcome"] == "CONVERGED"
    else:
        assert solved.record["outcome"] != "CONVERGED" or solved.verdict is None


def test_g6_the_corner_outcomes_as_measured(loop: Loop) -> None:
    """The stand-in at the two corners (regression, not a correctness claim): from (0, −50) the
    k = 0 experiment refuses (`nh3_below_trace`) and the run ends as a cold one would — there is
    no fallback after acceptance; from (0.95, 250) it converges and verifies."""
    low, high = loop.corners[(0.0, -50.0)], loop.corners[(0.95, 250.0)]
    assert (low.coupling["status"], low.record["outcome"]) == ("accepted", "COUPLING_NOT_CONVERGED")
    assert low.record["reason"] == "external_refused(nh3_below_trace)"
    assert len(low.record["iterations"]) == 1
    assert (high.coupling["status"], high.verdict) == ("accepted", "VERIFIED")


# -- records ---------------------------------------------------------------------------------------


def test_bounds_project_the_declared_iterate_and_log_each_clip(loop: Loop) -> None:
    member = loop.clipped.coupling
    assert (member["status"], member["reason"]) == ("accepted", None)
    assert member["declared"] == {"reactor": {"X": 1.2, "dT_K": 300.0}}
    assert member["projections"] == [["reactor", "X", 1.2, 0.95], ["reactor", "dT_K", 300.0, 250.0]]
    # `couple` opens at u = w₀ / scales (§5.4), so the recorded w is w₀ through that round trip.
    scales = np.array([0.1, 10.0])
    assert loop.clipped.record["iterations"][0]["w"] == list(
        np.array([0.95, 250.0]) / scales * scales
    )


def test_an_iterate_only_declaration_records_the_inner_members_not_declared(loop: Loop) -> None:
    member = loop.near.solve_path["warm_start"]
    assert {key: member[key] for key in ("record", "selection", "status", "reason")} == {
        "record": "warm-start-v1",
        "selection": "explicit-v1",
        "status": "absent",
        "reason": "not_declared",
    }
    assert member["candidate"] is None
    assert loop.near.record["iterations"][0]["inner"]["start"] == "route_initializer"


def test_cold_runs_write_no_member(loop: Loop) -> None:
    assert "warm_start" not in loop.cold.solve_path
    assert "warm_start" not in loop.again.solve_path


def _r0(solved: Solved) -> dict[str, Any]:
    manifest, _ = read_manifest(solved.bundle)
    artifacts = {name: read_artifact(solved.bundle, name) for name in manifest.artifacts}
    projection: dict[str, Any] = r0_projection(artifacts)
    return projection


def test_r0_projects_statuses_and_ids_never_values(loop: Loop) -> None:
    assert _r0(loop.clipped)["warm_start"]["coupling"] == {
        "source": "iterate",
        "status": "accepted",
        "reason": None,
        "units": ["reactor"],
        "projected": [["reactor", "X"], ["reactor", "dT_K"]],
    }
    assert _r0(loop.foreign)["warm_start"]["coupling"]["units"] == ["mixer"]
    # Two declared iterates that differ only in value project equally.
    assert _r0(loop.near)["warm_start"] == _r0(loop.corners[(0.95, 250.0)])["warm_start"]
    assert "warm_start" not in _r0(loop.cold)


# -- the routes without an outer iteration (§5.2) -------------------------------------------------


@pytest.mark.parametrize(
    ("case", "path", "reason"),
    [
        ("SYN-001-nominal", "revision_eo", "warm_start_rejected(coupling_compatibility)"),
        ("SYN-001-A02-360", "legacy_eo", "warm_start_rejected(route)"),
    ],
)
def test_a_declared_iterate_off_the_coupled_route_is_recorded_rejected(
    case: str, path: str, reason: str, tmp_path: Path
) -> None:
    with (
        pytest.MonkeyPatch.context() as monkeypatch,
        LocalApplication.create(tmp_path / "p", project_id="x02-wo3-eo") as app,
    ):
        counting = Counting(monkeypatch)
        document = CORPUS[case]()
        revision_id = commit(app, document)
        unit = document["instances"][0]["id"]
        declared = _solve(app, counting, revision_id, _iterate((0.3, 10.0), unit=unit))
        cold = _solve(app, counting, revision_id)
        assert declared.solve_path["solve_path"] == path
        member = declared.solve_path["warm_start"]
        expected_inner = (
            ("rejected", "route") if path == "legacy_eo" else ("absent", "not_declared")
        )
        assert (member["status"], member["reason"]) == expected_inner
        assert (member["coupling"]["status"], member["coupling"]["reason"]) == ("rejected", reason)
        assert declared.verdict == cold.verdict
        assert read_artifact(declared.bundle, "solution-state.json") == read_artifact(
            cold.bundle, "solution-state.json"
        )
        report = app.reproduce(declared.bundle, ReplayPolicy(rerun=True))
    assert report.verdict == "MATCH", report.differences


# -- integrity at resolution (§5.2, D3 step 1) -----------------------------------------------------


def test_integrity_of_a_job_source(loop: Loop, tmp_path: Path) -> None:
    source = loop.cold.bundle / "artifacts" / COUPLING
    accepted = job_coupling_start(source)
    x, dt = loop.cold.record["iterations"][-1]["w"]
    assert (accepted.source, accepted.record["status"]) == ("job", "accepted")
    assert accepted.declared == {"reactor": (x, dt)}
    absent = job_coupling_start(None)
    assert (absent.record["status"], absent.record["reason"]) == ("absent", "no_coupling_record")
    assert job_coupling_start(tmp_path / "missing.json").record["status"] == "absent"

    def tampered(edit: Any) -> dict[str, Any]:
        record = json.loads(source.read_bytes())
        edit(record)
        path = tmp_path / f"t{len(list(tmp_path.iterdir()))}.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        return dict(job_coupling_start(path).record)

    def unconverged(record: dict[str, Any]) -> None:
        record["outcome"], record["reason"] = "COUPLING_NOT_CONVERGED", "max_outer"

    def short(record: dict[str, Any]) -> None:
        record["iterations"][-1]["w"] = record["iterations"][-1]["w"][:1]

    def invalid(record: dict[str, Any]) -> None:
        del record["coupling_block"]

    for edit in (unconverged, short, invalid):
        member = tampered(edit)
        assert (member["status"], member["reason"], member["declared"]) == (
            "rejected",
            "warm_start_rejected(coupling_integrity)",
            None,
        ), edit.__name__
    garbage = tmp_path / "garbage.json"
    garbage.write_bytes(b"{not json")
    assert job_coupling_start(garbage).record["status"] == "rejected"


# -- the coupled solve itself: trace messages and the second opening (§5.4, §5.9) ------------------


def test_solve_coupled_rejects_the_opening_with_its_trace_messages(
    tight: Tight, tmp_path: Path
) -> None:
    route = bind_route("revision_coupled", copy.deepcopy(tight.revision))
    assert isinstance(route, Route)
    policy = resolve_policy("default", "revision_coupled")
    assert policy is not None
    experiments = LiveExperiments(
        ExperimentRunner(
            ExperimentStore(tmp_path, ListArtifactSink()),
            PrC1Provider(),
            EvaluationContext(model_version="x02-wo3", constants_sha256="0" * 64),
        )
    )
    trace, opened = Trace(), []
    solved = solve_coupled(
        route.binding,
        policy=policy,
        experiments=experiments,
        trace=trace,
        coupled_start=iterate_start({"reactor": OPENING_W}),
        on_iteration=lambda k, _: opened.append(k),
    )
    assert solved.coupling_start is not None
    assert solved.coupling_start["reason"] == "warm_start_rejected(coupling_opening)"
    assert solved.coupling.outcome == "CONVERGED"
    messages = [
        (event.kind, event.message)
        for event in trace.events
        if event.message.startswith(("coupling_warm_start", "warm_start_rejected(coupling"))
    ]
    assert messages == [
        ("initializer_candidate", "coupling_warm_start(present)"),
        ("initializer_rejected", "warm_start_rejected(coupling_opening)"),
    ]
    # k = 0 fires twice: once for the rejected opening, once for the cold coupling.
    assert opened[:2] == [0, 0]
    assert coupled_run.COUPLING_START == "coupling-start-v1"
