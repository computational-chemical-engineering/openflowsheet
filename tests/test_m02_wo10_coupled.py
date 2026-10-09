"""M02 WO-10: the `revision_coupled` route end to end — G8 (a)–(d), (f) end to end, (g), G6 (c),
and R3 replay from the record (design note §4.2–§4.4, §7, §10.1; ADR 0034 D2–D6; register R-225,
R-227).

- G8 (a): `C1-LOOP-M02-v1` with the stand-in solves through a `solve` job: `CONVERGED` at k = 1
  with exactly two experiments, certificate `VERIFIED`, both coupling checks `pass`, the ξ check's
  value ≤ 1e-12 and the T check's exactly 0.0; the bundle holds `external-coupling.json`, valid
  against `experiment.schema.json#/$defs/coupling`.
- G8 (b): the flowsheet's element balance, makeup = NH3 product + purge, ≤ 1e-10 of the makeup's
  element flow for H, N, Ar and C.
- G8 (c): every variable of the final state within 1e-8 relative of an independent sequential
  substitution (`tests/m02_loop_oracle.py`: `pr-c1-v1`'s flash and the stand-in's closed form).
- G8 (d): `reproduce` → `MATCH`, the stand-in re-evaluated.
- G8 (f) end to end: a test-only in-process variant with ξ = (0.15 + 2 (y_inert,in − 0.05))
  n_N2,in and T_out = T_in + 80 K + 1000 K (y_NH3,in − 0.02) converges on the loop with ρ ≤ 1 in
  at most 15 iterations and needs more than two.
- G8 (g): a cancel at k = 1 leaves `partial_solve_trace` plus the experiment artifacts only.
- G6 (c): a (synthetic, out-of-process) child that reports another fingerprint at k = 1 ends
  `EVALUATION_ERROR` `external_environment_changed(reactor)`, no certificate.
- R3 (§7.2): a run with an out-of-process variant is R3; `reproduce` replays its results from the
  record (`MATCH`, `external_results_replayed_from_record(2)`), and a recomputed request that is
  not the record's is a `MISMATCH` naming `external_request(<k>, <unit>)`.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import sys
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT
from m02_variant_support import register_variants
from t07_jobs_support import commit, lifecycle_violations, response_schema_violations

from openflowsheet.adapters import variants
from openflowsheet.adapters.experiments.backends import InProcessBackend
from openflowsheet.adapters.experiments.runner import ExperimentRunner
from openflowsheet.adapters.experiments.store import ExperimentStore, ListArtifactSink
from openflowsheet.application.coupled_run import (
    LiveExperiments,
    RecordedExperiments,
    ReplayDivergenceError,
    external_units,
)
from openflowsheet.application.jobs import runner as job_runner
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import dispatch
from openflowsheet.application.policies import T06_REVISION_V2
from openflowsheet.application.revision_run import (
    Route,
    reproduce_bundle,
    run_revision_session,
    select_route,
)
from openflowsheet.application.types import schema_errors
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.c1.boundary import TubeInlet, TubeOutlet
from openflowsheet.orchestrator.coupling import UnitInlet
from openflowsheet.run.bundle import read_artifact, read_manifest
from openflowsheet.run.compare import CURRENT_POLICY_ID
from openflowsheet.thermo.pr_c1 import COMPONENTS, PrC1Provider
from openflowsheet.verify.certificate import CheckPolicy

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from m02_schema_fixtures import synthetic_backend, synthetic_variant  # noqa: E402

LOOP_PATH = REPO_ROOT / "benchmarks" / "m02" / "c1-loop-standin.json"
STANDIN = variants.registered_variant("standin-x025-v1")
REAL = variants.registered_variant("pymrm-6089593-g2-nz800-s123-v2")
COUPLING = "experiment.schema.json#/$defs/coupling"
#: The elements of the five components (H2, N2, NH3, Ar, CH4).
ELEMENTS = {
    "H": (2, 0, 3, 0, 4),
    "N": (0, 2, 1, 0, 0),
    "Ar": (0, 0, 0, 1, 0),
    "C": (0, 0, 0, 0, 1),
}


def loop() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(LOOP_PATH.read_text(encoding="utf-8"))
    return document


def flows(state: Mapping[str, float], stream: str) -> tuple[float, ...]:
    return tuple(state[f"{stream}.n.{c}"] for c in COMPONENTS)


def runner_in(root: Path, **options: Any) -> ExperimentRunner:
    return ExperimentRunner(
        ExperimentStore(root, ListArtifactSink()),
        PrC1Provider(),
        EvaluationContext(model_version="m02-wo10", constants_sha256="0" * 64),
        **options,
    )


def solve(
    document: Mapping[str, Any], directory: Path, experiments: Any
) -> tuple[Any, dict[str, Any]]:
    route = select_route(document)
    assert isinstance(route, Route) and route.solve_path == "revision_coupled"
    manifest = run_revision_session(
        route,
        document,
        directory,
        run_id="run-wo10",
        policy=T06_REVISION_V2,
        check_policy=CheckPolicy(),
        policy_requested="default",
        experiments=experiments,
    )
    return manifest, {name: read_artifact(directory, name) for name in manifest.artifacts}


def pinned(document: Mapping[str, Any], variant: variants.Variant) -> dict[str, Any]:
    """`document` with its reactor pinned to `variant`."""
    pinned_document = copy.deepcopy(dict(document))
    for item in pinned_document["instances"]:
        if item["id"] == "reactor":
            item["model"] = {
                "id": variant.model_id,
                "version": variant.variant_id,
                "artifact_ref": variant.sha256,
            }
    return pinned_document


@pytest.fixture
def register(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Register test-only variants for the binder (a registry patched for the test only)."""
    return register_variants(monkeypatch)


@pytest.fixture
def app(tmp_path: Path) -> Iterator[LocalApplication]:
    application = LocalApplication.create(tmp_path / "project")
    try:
        yield application
        assert lifecycle_violations(application) == {}
        assert response_schema_violations(application) == []
    finally:
        application.close()


def submit_solve(app: LocalApplication, key: str, revision_id: str) -> dict[str, Any]:
    body = {"revision_id": revision_id}
    request = {"operation": "solve", "idempotency_key": key, "body": body}
    job: dict[str, Any] = dispatch(app, "submit_job", request)["job"]
    return job


def bundle_of(app: LocalApplication, job: Mapping[str, Any]) -> Path:
    (ref,) = [output for output in job["outputs"] if output["kind"] == "replay_bundle"]
    row = app.store.artifact(ref["artifact_id"])
    assert row is not None
    return app.files_root / row.relpath


# == G8 (a), (b), (c), (d) through the contract ===================================================


@pytest.fixture
def solved(app: LocalApplication) -> tuple[LocalApplication, dict[str, Any], Path]:
    revision_id = commit(app, loop())
    job = submit_solve(app, "g8", revision_id)
    return app, job, bundle_of(app, job)


def test_the_loop_routes_on_revision_coupled() -> None:
    route = select_route(loop())
    assert isinstance(route, Route) and route.solve_path == "revision_coupled"
    assert [unit.unit_id for unit in external_units(route.binding)] == ["reactor"]


def test_g8a_converged_at_k1_with_two_experiments_and_verified(
    solved: tuple[LocalApplication, dict[str, Any], Path],
) -> None:
    app, job, bundle = solved
    assert (job["status"], job["error"]) == ("completed", None)
    kinds = [output["kind"] for output in job["outputs"]]
    assert kinds == [
        *("experiment_request", "experiment_attempt", "experiment_result") * 2,
        "solution_certificate",
        "run_manifest",
        "replay_bundle",
    ]
    result = dispatch(app, "get_job_result", {"job_id": job["job_id"]})["run_result"]
    assert (result["solve_path"], result["outcome"], result["verification_status"]) == (
        "revision_coupled",
        "CONVERGED",
        "VERIFIED",
    )
    record = read_artifact(bundle, "external-coupling.json")
    assert schema_errors(COUPLING, record) == []
    assert (record["outcome"], record["reason"]) == ("CONVERGED", None)
    assert [item["k"] for item in record["iterations"]] == [0, 1]
    assert all(len(item["units"]) == 1 for item in record["iterations"])
    assert record["iterations"][1]["rho"] <= 1.0
    assert record["iterations"][1]["w"] == pytest.approx([0.25, 0.0], abs=1e-15)
    certificate = read_artifact(bundle, "solution-certificate.json")
    checks = {check["id"]: check for check in certificate["checks"]}
    xi, t = checks["EXT-COUPLING:reactor:xi"], checks["EXT-COUPLING:reactor:T"]
    assert (xi["result"], t["result"]) == ("pass", "pass")
    assert (xi["category"], xi["tolerance"], t["tolerance"]) == ("residual", 1e-5, 1e-2)
    assert xi["value"] <= 1e-12
    assert t["value"] == 0.0
    assert not xi["near_threshold"] and not t["near_threshold"]
    external = [item for item in certificate["limitations"] if item["kind"] == "external_model"]
    assert external == [
        {
            "kind": "external_model",
            "unit": "reactor",
            "variant_id": "standin-x025-v1",
            "synthetic": True,
            "reproducibility": "R1",
            "discretization_estimate": None,
        }
    ]
    assert certificate["derivative_provenance"]["external_map"] == {"reactor": "unavailable"}
    # §14.3 C3: the record G8 carries — the flash's L/n_tot and the certificate's rcond_1.
    state = read_artifact(bundle, "solution-state.json")["variables"]
    assert sum(flows(state, "S6")) / sum(flows(state, "S4")) == pytest.approx(0.12806, rel=1e-3)
    assert certificate["regularity"]["rcond_1"] == pytest.approx(1.4238e-4, rel=1e-3)


def test_g8a_the_experiments_were_evaluated_at_the_certified_inlet(
    solved: tuple[LocalApplication, dict[str, Any], Path],
) -> None:
    _, _, bundle = solved
    record = read_artifact(bundle, "external-coupling.json")
    state = read_artifact(bundle, "solution-state.json")["variables"]
    inputs = record["iterations"][-1]["units"]["reactor"]["request"]["inputs"]
    assert [float(v).hex() for v in inputs["n"]] == [v.hex() for v in flows(state, "S3")]
    assert (inputs["T"], inputs["P"]) == (state["S3.T"], state["S3.P"])


def test_g8b_the_flowsheets_element_balance_closes(
    solved: tuple[LocalApplication, dict[str, Any], Path],
) -> None:
    _, _, bundle = solved
    state = read_artifact(bundle, "solution-state.json")["variables"]
    makeup, product, purge = flows(state, "S1"), flows(state, "S6"), flows(state, "S7")
    for element, counts in ELEMENTS.items():
        into = sum(a * n for a, n in zip(counts, makeup, strict=True))
        out = sum(a * n for a, n in zip(counts, product, strict=True)) + sum(
            a * n for a, n in zip(counts, purge, strict=True)
        )
        assert abs(into - out) <= 1e-10 * into, (element, into, out)


def test_g8c_the_state_agrees_with_an_independent_sequential_substitution(
    solved: tuple[LocalApplication, dict[str, Any], Path],
) -> None:
    from m02_loop_oracle import solve_loop

    _, _, bundle = solved
    state = read_artifact(bundle, "solution-state.json")["variables"]
    oracle = solve_loop()
    expected: dict[str, float] = {"reactor.xi": oracle.xi}
    for stream, (n, temperature, pressure) in oracle.streams.items():
        expected.update({f"{stream}.n.{c}": v for c, v in zip(COMPONENTS, n, strict=True)})
        expected[f"{stream}.T"], expected[f"{stream}.P"] = temperature, pressure
    expected.update({f"{unit}.Q": q for unit, q in oracle.duties.items()})
    # The flash's outlet totals (its lifted split's columns).
    expected["S5.N"], expected["S6.N"] = sum(oracle.streams["S5"][0]), sum(oracle.streams["S6"][0])
    assert set(expected) == set(state)  # every variable of the final state is compared
    worst = max(
        (abs(state[name] - value) / abs(value) if value != 0.0 else abs(state[name]), name)
        for name, value in expected.items()
    )
    # Measured: 3.0e-14 (S2.T, the mixer's adiabatic temperature), 1643 passes.
    assert worst[0] <= 1e-8, worst


def test_g8d_reproduce_matches_with_the_stand_in_reevaluated(
    solved: tuple[LocalApplication, dict[str, Any], Path],
) -> None:
    app, job, _ = solved
    (ref,) = [output for output in job["outputs"] if output["kind"] == "replay_bundle"]
    body = {"bundle_artifact_id": ref["artifact_id"], "rerun": True}
    request = {"operation": "reproduce", "idempotency_key": "replay", "body": body}
    reproduce = dispatch(app, "submit_job", request)["job"]
    assert (reproduce["status"], reproduce["error"]) == ("completed", None)
    report = dispatch(app, "get_job_result", {"job_id": reproduce["job_id"]})["replay_report"]
    assert report["verdict"] == "MATCH", report["differences"]
    assert report["bitwise_floats"] is True
    assert "external_results_replayed_from_record(0)" in report["reasons"]
    assert "external_results_reevaluated(2)" in report["reasons"]
    frozen = report["recorded_environment"]["external_fingerprints"]
    assert set(frozen) == {"reactor"}


def test_a_second_solve_serves_both_experiments_from_the_cache(
    solved: tuple[LocalApplication, dict[str, Any], Path],
) -> None:
    app, first, _ = solved
    revision_id = dispatch(app, "get_job_result", {"job_id": first["job_id"]})["run_result"][
        "revision_id"
    ]
    second = submit_solve(app, "again", revision_id)
    kinds = [output["kind"] for output in second["outputs"]]
    assert kinds[:2] == ["experiment_result", "experiment_result"]  # the hits' rows
    assert "experiment_attempt" not in kinds


# == G8 (f) end to end ===========================================================================


class NonlinearBackend(InProcessBackend):
    """G8 (f)'s test-only map per tube: ξ = (0.15 + 2 (y_inert − 0.05)) F y_N2 and
    T_out = T_in + 80 K + 1000 K (y_NH3 − 0.02)."""

    def evaluate(self, tube: TubeInlet, *args: Any) -> Any:
        y = tube.composition
        feed = tuple(tube.flow * value for value in y)
        xi = (0.15 + 2.0 * (y[3] + y[4] - 0.05)) * feed[1]
        nu = (-3.0, -1.0, 2.0, 0.0, 0.0)
        outlet = TubeOutlet(
            flows=tuple(f + n * xi for f, n in zip(feed, nu, strict=True)),
            temperature=tube.temperature + 80.0 + 1000.0 * (y[2] - 0.02),
            pressure_drop=0.0,
        )
        execution = super().evaluate(tube, *args)
        return dataclasses.replace(execution, answer=outlet, tube_outlet=dataclasses.asdict(outlet))


def test_g8f_a_nonlinear_in_process_variant_converges_end_to_end(
    tmp_path: Path, register: Any
) -> None:
    document = {**STANDIN.document, "variant_id": "test-nonlinear-v1"}
    variant = register(variants.variant_from_document(document))
    runner = runner_in(
        tmp_path / "records",
        backend_for=lambda v: (
            NonlinearBackend(v) if v.sha256 == variant.sha256 else InProcessBackend(v)
        ),
    )
    manifest, artifacts = solve(
        pinned(loop(), variant), tmp_path / "bundle", LiveExperiments(runner)
    )
    record = artifacts["external-coupling.json"]
    assert schema_errors(COUPLING, record) == []
    assert (manifest.outcome, manifest.verification_status) == ("CONVERGED", "VERIFIED")
    accepted = [item for item in record["iterations"] if item["rho"] is not None]
    assert 2 < len(accepted) <= 15
    assert accepted[-1]["rho"] <= 1.0
    # Measured: four accepted iterates, ρ 964.5, 227.0, 91.2, 0.257.


# == G8 (g) ======================================================================================


def test_g8g_a_cancel_at_k1_leaves_the_partial_trace_and_the_experiments_only(
    app: LocalApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = job_runner._Body._outer_iteration

    def cancel_at_k1(body: Any, k: int, max_outer: int) -> None:
        if k == 1:  # a cancel_job arriving as the second outer iteration starts
            body.context.store.request_cancel(body.job.job_id)
        original(body, k, max_outer)

    monkeypatch.setattr(job_runner._Body, "_outer_iteration", cancel_at_k1)
    job = submit_solve(app, "cancel", commit(app, loop()))
    assert (job["status"], job["error"]) == ("cancelled", None)
    kinds = [output["kind"] for output in job["outputs"]]
    assert kinds == [
        "experiment_request",
        "experiment_attempt",
        "experiment_result",
        "partial_solve_trace",
    ]


# == G6 (c) and R3 with a synthetic out-of-process child =========================================


def out_of_process(name: str, hooks: list[str]) -> variants.Variant:
    """A test-only out-of-process variant run by the synthetic child (closed forms per tube, as the
    stand-in's). `synthetic` is false and the accuracy block is the real variant's so that the
    embedded unit's manifest has the real reactor's limitations to state (an out-of-process
    synthetic variant has no stand-in conversion for them); the floor ratios are then those of
    ε_eval = 1e-6. Never registered outside the test."""
    base = synthetic_variant(name, hooks).document
    document = {**base, "synthetic": False, "accuracy": REAL.document["accuracy"]}
    return variants.variant_from_document(document)


def test_g6c_a_changed_fingerprint_at_k1_ends_evaluation_error(
    tmp_path: Path, register: Any
) -> None:
    variant = register(out_of_process("wo10-g6c", ["ok"]))
    runner = runner_in(tmp_path / "records", backend_for=synthetic_backend(tmp_path / "env"))

    def at_k1() -> None:
        # From the second experiment on, the child reports another interpreter.
        backend = runner.backend(variant)
        backend.configuration = {**backend.configuration, "hooks": ["fingerprint(alt)"]}

    manifest, artifacts = solve(
        pinned(loop(), variant), tmp_path / "bundle", LiveExperiments(runner, on_evaluated=at_k1)
    )
    assert manifest.outcome == "EVALUATION_ERROR"
    assert "solution-certificate.json" not in artifacts
    failure = artifacts["failure-bundle.json"]
    assert failure["observations"]["reason"] == "external_environment_changed(reactor)"
    record = artifacts["external-coupling.json"]
    assert schema_errors(COUPLING, record) == []
    assert (record["outcome"], record["reason"]) == (
        "EVALUATION_ERROR",
        "external_environment_changed(reactor)",
    )
    assert [item["k"] for item in record["iterations"]] == [0, 1]
    last = record["iterations"][1]["units"]["reactor"]
    assert last["result"] is None
    assert last["attempts"][-1]["execution"]["status"] == "environment_changed"


@pytest.fixture
def r3_run(tmp_path: Path, register: Any) -> tuple[Path, Any, dict[str, Any], Path]:
    variant = register(out_of_process("wo10-r3", ["ok"]))
    runner = runner_in(tmp_path / "records", backend_for=synthetic_backend(tmp_path / "env"))
    manifest, artifacts = solve(
        pinned(loop(), variant), tmp_path / "bundle", LiveExperiments(runner)
    )
    return tmp_path / "bundle", manifest, artifacts, tmp_path


def test_r3_an_out_of_process_coupled_run_is_r3_and_its_checks_say_so(
    r3_run: tuple[Path, Any, dict[str, Any], Path],
) -> None:
    _, manifest, artifacts, _ = r3_run
    assert (manifest.outcome, manifest.verification_status) == ("CONVERGED", "VERIFIED")
    assert manifest.reproducibility_class == "R3"
    record = artifacts["external-coupling.json"]
    assert schema_errors(COUPLING, record) == []
    assert set(record["frozen"]) == {"reactor"}
    certificate = artifacts["solution-certificate.json"]
    checks = [c for c in certificate["checks"] if c["id"].startswith("EXT-COUPLING:")]
    assert {c["independence_qualification"] for c in checks} == {"external model, R3"}
    unit = record["iterations"][-1]["units"]["reactor"]
    # §4.2: the floor ratios at ε_eval = 1e-6 (the note's 59 x and 13 x at the nominal point).
    assert 10.0 < unit["floor_ratio_T"] < unit["floor_ratio_xi"]
    assert not any(c["near_threshold"] for c in checks)


def test_r3_reproduce_replays_the_results_from_the_record(
    r3_run: tuple[Path, Any, dict[str, Any], Path],
) -> None:
    bundle, _, _, tmp_path = r3_run
    reproduction = reproduce_bundle(
        bundle, rerun=True, rerun_directory=tmp_path / "rerun", run_id="run-rerun"
    )
    report = reproduction.report
    assert report.verdict == "MATCH", report.differences
    assert "external_results_replayed_from_record(2)" in report.reasons
    assert not any(reason.startswith("external_results_reevaluated") for reason in report.reasons)
    frozen = report.recorded_environment["external_fingerprints"]["reactor"]
    assert frozen["fingerprint"]["runner_sha256"]


def test_r3_a_request_that_is_not_the_records_is_a_mismatch_naming_it(
    r3_run: tuple[Path, Any, dict[str, Any], Path],
) -> None:
    _, _, artifacts, tmp_path = r3_run
    record = artifacts["external-coupling.json"]
    route = select_route(read_artifact(tmp_path / "bundle", "revision.json"))
    assert isinstance(route, Route)
    (unit,) = external_units(route.binding)
    variant = variants.Variant(
        record["variants"]["reactor"], record["frozen"]["reactor"]["variant_sha256"]
    )
    recorded = RecordedExperiments(
        record, provider=PrC1Provider(), scratch=tmp_path / "scratch", policy_id=CURRENT_POLICY_ID
    )
    inputs = record["iterations"][0]["units"]["reactor"]["request"]["inputs"]
    at = UnitInlet(n=tuple(inputs["n"]), T=inputs["T"], P=inputs["P"], n_key=inputs["n"][1])
    assert recorded.evaluate(unit, variant, at).status == "ok"  # the record's own inlet
    moved = dataclasses.replace(at, T=at.T * (1.0 + 1e-6))
    with pytest.raises(ReplayDivergenceError) as raised:
        recorded.evaluate(unit, variant, moved)
    assert raised.value.difference.startswith("external_request(1, reactor).inputs")
    assert recorded.replayed == 1


def test_the_bundle_member_is_registered_with_its_kind(
    solved: tuple[LocalApplication, dict[str, Any], Path],
) -> None:
    app, job, bundle = solved
    manifest, _ = read_manifest(bundle)
    assert "external-coupling.json" in manifest.artifacts
    row = app.store.artifact(f"{job['job_id']}:bundle/external-coupling.json")
    assert row is not None and row.kind == "external_coupling"
