"""M04.A08, A16–A24 at the library level: the surrogate study end to end on in-process parents.

`run_study` runs a registered plan through M02's `ExperimentRunner` (cache first, one by one) on
the WO-4 synthetic parents (`tests/support/m04_synthetic_parents.py`), whose answers are exactly
known, and the expectations are the generator's (`benchmarks/m04/reference_values.json` →
`pipeline`, 50-digit). The job operation around it is `tests/test_m04_study_job.py` (A16 there,
through the application with the registered stand-in).

Tolerances are the specification's, each with its floor (spec §11): coefficients 10⁻¹⁰ × ‖β_ref‖∞
(A10; κ = 8.1 times the records' roundoff ≈ 10⁻¹⁴ relative), q̂ 10⁻¹⁰ absolute (A17, A19; scores
≈ 10⁻¹³) or 10⁻⁹ relative (A18), L 10⁻⁹ (A06), gradient errors 10⁻⁸ absolute (≈ 10⁻¹² floor). Every
integer — failed indices, N_ok, H, n, m, k, h_min — is exact.
"""

from __future__ import annotations

import ast
import copy
import json
import math
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT

from openflowsheet.adapters.experiments.runner import ExperimentRunner
from openflowsheet.adapters.experiments.store import ExperimentStore, ListArtifactSink
from openflowsheet.canonical import canonical_json, document_sha256
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.c1 import COMPONENTS
from openflowsheet.studies.surrogate import plan as sp
from openflowsheet.studies.surrogate.manifest import (
    Q0,
    QUALIFICATIONS,
    check_manifest,
    schema_errors,
)
from openflowsheet.studies.surrogate.quadratic import fit_quadratic
from openflowsheet.studies.surrogate.study import StudyOutcome, run_study
from openflowsheet.thermo import StreamState
from openflowsheet.thermo.pr_c1 import PrC1Provider

sys.path.insert(0, str(REPO_ROOT / "tests" / "support"))
import m04_synthetic_parents as parents  # noqa: E402

REFERENCE = json.loads(
    (REPO_ROOT / "benchmarks" / "m04" / "reference_values.json").read_text(encoding="utf-8")
)
PIPELINE = REFERENCE["pipeline"]
PLENTY = 10_000


@dataclass
class Study:
    root: Path
    variant_id: str
    plan_id: str
    outcome: StudyOutcome

    def runner(self, transient: tuple[Any, ...] = ()) -> ExperimentRunner:
        return _runner(self.root, transient)

    @property
    def manifest(self) -> dict[str, Any]:
        assert self.outcome.manifest is not None
        return dict(self.outcome.manifest)


def _runner(root: Path, transient: tuple[Any, ...] = ()) -> ExperimentRunner:
    return ExperimentRunner(
        ExperimentStore(root, ListArtifactSink()),
        PrC1Provider(),
        EvaluationContext(model_version="m04-study", constants_sha256="0" * 64),
        backend_for=parents.backend_for(transient),
    )


def _study(root: Path, variant_id: str, plan_id: str, budget: int = PLENTY) -> Study:
    variant = parents.synthetic_variant(variant_id)
    outcome = run_study(_runner(root), variant, plan_id, budget)
    return Study(root, variant_id, plan_id, outcome)


@pytest.fixture(scope="module")
def smooth_full(tmp_path_factory: pytest.TempPathFactory) -> Study:
    return _study(tmp_path_factory.mktemp("smooth-full"), parents.SMOOTH_ID, "it1")


@pytest.fixture(scope="module")
def smooth_prefix(tmp_path_factory: pytest.TempPathFactory) -> Study:
    return _study(tmp_path_factory.mktemp("smooth-prefix"), parents.SMOOTH_ID, "it1-prefix")


@pytest.fixture(scope="module")
def rough_prefix(tmp_path_factory: pytest.TempPathFactory) -> Study:
    return _study(tmp_path_factory.mktemp("rough-prefix"), parents.ROUGH_ID, "it1-prefix")


def _attempt_files(root: Path) -> list[Path]:
    return sorted(root.glob("experiments/*/*/attempt-*.json"))


def _failed_indices(manifest: dict[str, Any]) -> dict[str, list[int]]:
    return {
        split: [entry["index"] for entry in manifest["splits"][split]["failed"]]
        for split in ("training", "calibration", "test")
    }


def _coefficients_within(manifest: dict[str, Any], case: str) -> None:
    """A10: within 10⁻¹⁰ × ‖β_ref‖∞ per output; the singular-value ratio within 10⁻⁸ relative."""
    reference = PIPELINE[case]
    for output, key in (("X", "X"), ("dT_K", "dT")):
        expected = [float(b) for b in reference["coefficients"][key]]
        measured = manifest["predictor"]["coefficients"][output]
        scale = max(abs(b) for b in expected)
        worst = max(abs(a - b) for a, b in zip(measured, expected, strict=True))
        assert worst <= 1e-10 * scale, (output, worst / scale)
    ratio = manifest["predictor"]["fit"]["singular_value_ratio"]
    assert ratio == pytest.approx(float(reference["singular_value_ratio"]), rel=1e-8)


def _gradient_within(manifest: dict[str, Any], case: str) -> None:
    registered = PIPELINE[case]["gradient"]
    centres = manifest["gradient"]["centres"]
    assert (
        [c["status"] for c in centres]
        == [r["status"] for r in registered]
        == ["ok"] * len(registered)
    )
    for centre, reference in zip(centres, registered, strict=True):
        for output, key in (("X", "X"), ("dT_K", "dT")):
            expected = float(reference[key]["relative_error"])
            assert abs(centre["errors"][output] - expected) <= 1e-8, (centre["index"], output)


# -- A17: the smooth parent, the full plan -------------------------------------------------------


def test_a17_smooth_full_plan(smooth_full: Study) -> None:
    reference = PIPELINE["smooth_full"]
    outcome, manifest = smooth_full.outcome, smooth_full.manifest
    assert (outcome.verdict, outcome.insufficient, outcome.not_promotable) == ("PROMOTABLE", (), ())
    assert (outcome.cold_experiments, outcome.cache_hits, outcome.cache_misses) == (632, 0, 632)
    assert _failed_indices(manifest) == reference["failed_indices"]
    assert manifest["predictor"]["fit"]["training_ok"] == reference["training_ok"] == 142
    _coefficients_within(manifest, "smooth_full")
    q_hat = manifest["calibration"]["q_hat"]
    assert abs(q_hat - 0.022440174316072) <= 1e-10
    assert abs(q_hat - float(reference["result"]["q_hat"])) <= 1e-10
    assert manifest["evaluation"]["hits"] == 283
    assert abs(manifest["evaluation"]["lower_bound"] - 0.916211187) <= 1e-9
    _gradient_within(manifest, "smooth_full")
    promotion = manifest["promotion"]
    assert (promotion["verdict"], promotion["insufficient"], promotion["not_promotable"]) == (
        "PROMOTABLE",
        [],
        [],
    )
    assert manifest["domain"]["inadmissible_predictions"] == reference["inadmissible"] == 0
    assert manifest["domain"]["parent_extrapolated"] == 0


def test_a17_the_scores_are_the_registered_scores(smooth_full: Study) -> None:
    """Every calibration and test score within 10⁻¹⁰ of the 50-digit one, failures exactly null."""
    reference = PIPELINE["smooth_full"]
    for split, key in (("calibration", "calibration_scores"), ("evaluation", "test_scores")):
        measured = smooth_full.manifest[split]["scores"]
        expected = [None if s is None else float(s) for s in reference[key]]
        assert [s is None for s in measured] == [s is None for s in expected]
        worst = max(abs(a - b) for a, b in zip(measured, expected, strict=True) if a is not None)
        assert worst <= 1e-10, (split, worst)


def test_a08_the_full_plans_denominators(smooth_full: Study) -> None:
    manifest = smooth_full.manifest
    calibration, evaluation = manifest["calibration"], manifest["evaluation"]
    assert (calibration["n"], calibration["k"], evaluation["m"], evaluation["h_min"]) == (
        118,
        114,
        300,
        279,
    )
    assert len(calibration["scores"]) == 118 and len(evaluation["scores"]) == 300


# -- A18, A19: the prefix plan ---------------------------------------------------------------------


def test_a18_rough_prefix_plan(rough_prefix: Study) -> None:
    manifest = rough_prefix.manifest
    q_hat = manifest["calibration"]["q_hat"]
    assert q_hat == pytest.approx(1.6139880778, rel=1e-9)
    assert manifest["evaluation"]["hits"] == 59
    assert rough_prefix.outcome.verdict == "NOT_PROMOTABLE"
    assert manifest["promotion"]["not_promotable"] == ["width_limit_exceeded"]
    assert manifest["promotion"]["insufficient"] == []
    assert _failed_indices(manifest) == PIPELINE["rough_prefix"]["failed_indices"]
    _coefficients_within(manifest, "rough_prefix")
    _gradient_within(manifest, "rough_prefix")


def test_a19_smooth_prefix_plan(smooth_prefix: Study) -> None:
    manifest = smooth_prefix.manifest
    assert abs(manifest["calibration"]["q_hat"] - 0.024916065269) <= 1e-10
    assert manifest["evaluation"]["hits"] == 59
    assert smooth_prefix.outcome.verdict == "PROMOTABLE"
    assert _failed_indices(manifest) == PIPELINE["smooth_prefix"]["failed_indices"]
    _coefficients_within(manifest, "smooth_prefix")
    _gradient_within(manifest, "smooth_prefix")
    # The band A26 will read: (q̂ w_X, q̂ w_ΔT) within 10⁻¹⁰ relative.
    band = PIPELINE["smooth_prefix"]["band"]
    q_hat = manifest["calibration"]["q_hat"]
    assert q_hat * 0.0025 == pytest.approx(float(band["X"]), rel=1e-10)
    assert q_hat * 1.5 == pytest.approx(float(band["dT"]), rel=1e-10)


@pytest.mark.parametrize("case", ["smooth_prefix", "rough_prefix"])
def test_a08_the_prefix_plans_denominators(case: str, request: pytest.FixtureRequest) -> None:
    manifest = request.getfixturevalue(case).manifest
    calibration, evaluation = manifest["calibration"], manifest["evaluation"]
    assert (calibration["n"], calibration["k"], evaluation["m"], evaluation["h_min"]) == (
        39,
        38,
        60,
        59,
    )


# -- A20: the budget -------------------------------------------------------------------------------


def test_a20_a_budget_below_the_misses_refuses_before_anything_runs(tmp_path: Path) -> None:
    refused = _study(tmp_path, parents.SMOOTH_ID, "it1-prefix", budget=198)
    outcome = refused.outcome
    assert (outcome.verdict, outcome.insufficient, outcome.not_promotable) == (
        "INSUFFICIENT_EVIDENCE",
        ("budget_below_plan",),
        (),
    )
    assert outcome.cache_misses == 199
    assert (outcome.cold_experiments, outcome.cache_hits) == (0, 0)
    assert outcome.manifest is None and outcome.evidence is None and outcome.evaluation is None
    assert _attempt_files(tmp_path) == []
    assert list(tmp_path.glob("experiments/*/*/*.json")) == []


def test_a20_with_every_record_cached_a_zero_budget_reproduces_the_manifest_bitwise(
    smooth_prefix: Study,
) -> None:
    before = _attempt_files(smooth_prefix.root)
    again = run_study(
        smooth_prefix.runner(), parents.synthetic_variant(parents.SMOOTH_ID), "it1-prefix", 0
    )
    assert (again.cold_experiments, again.cache_hits, again.cache_misses) == (0, 199, 0)
    assert again.manifest is not None and again.evidence is not None
    assert canonical_json(again.manifest) == canonical_json(smooth_prefix.manifest)
    assert canonical_json(again.evidence) == canonical_json(smooth_prefix.outcome.evidence)
    assert _attempt_files(smooth_prefix.root) == before


# -- A21: an incomplete plan -----------------------------------------------------------------------


def test_a21_a_request_without_a_deterministic_result_makes_the_plan_incomplete(
    tmp_path: Path,
) -> None:
    plan = sp.registered_plan("it1-prefix", synthetic_parent=True)
    centre = plan.gradient[1]
    designated = centre.stencil[0]  # gradient[1].T+
    variant = parents.synthetic_variant(parents.TRANSIENT_ID)
    for _ in range(2):  # a resumed job meets the same failure: never promotable
        runner = _runner(tmp_path, (designated.request,))
        outcome = run_study(runner, variant, "it1-prefix", PLENTY)
        assert outcome.verdict == "INSUFFICIENT_EVIDENCE"
        assert "plan_incomplete" in outcome.insufficient
        manifest = outcome.manifest
        assert manifest is not None
        (named,) = manifest["splits"]["gradient"]["incomplete"]
        assert named["label"] == "gradient[1].T+"
        assert (named["status"], named["code"]) == ("error", "external_crashed")
        key = manifest["splits"]["gradient"]["keys"][named["index"]]
        assert runner.records.result(key) is None  # never cached
        assert [c["status"] for c in manifest["gradient"]["centres"]] == ["ok", "incomplete"]
        assert all(not manifest["splits"][s]["incomplete"] for s in ("training", "test"))
        assert check_manifest(manifest) == []


# -- A22, A23: failures and split integrity --------------------------------------------------------


def test_a22_registered_failures_are_kept_with_their_label_and_no_score(
    smooth_full: Study,
) -> None:
    manifest = smooth_full.manifest
    records = smooth_full.runner().records
    for split, scores in (
        ("training", None),
        ("calibration", manifest["calibration"]["scores"]),
        ("test", manifest["evaluation"]["scores"]),
    ):
        block = manifest["splits"][split]
        for entry in block["failed"]:
            assert (entry["status"], entry["code"]) == (
                "not_converged",
                "reactor_not_accepted(synthetic_failure_region)",
            )
            if scores is not None:
                assert scores[entry["index"]] is None
            result = records.result(block["keys"][entry["index"]])
            assert result is not None
            envelope = result["envelope"]
            assert envelope["outlet"] is None and envelope["xi"] is None and envelope["Q"] is None
    assert (manifest["calibration"]["n"], manifest["evaluation"]["m"]) == (118, 300)
    # The failed draws are exactly the null scores: no score is null for another reason.
    for split, key in (("calibration", "calibration"), ("test", "evaluation")):
        failed = {entry["index"] for entry in manifest["splits"][split]["failed"]}
        nulls = {i for i, s in enumerate(manifest[key]["scores"]) if s is None}
        assert failed == nulls


def test_a23_split_integrity_and_a_bitwise_refit(smooth_full: Study) -> None:
    manifest = smooth_full.manifest
    evidence = smooth_full.outcome.evidence
    assert evidence is not None
    splits = manifest["splits"]
    keys = {split: splits[split]["keys"] for split in sp.SPLITS}
    every = [key for split in sp.SPLITS for key in keys[split]]
    assert len(every) == len(set(every)) == 632  # pairwise disjoint, no repeats
    # Equal to the plan's request keys in plan order.
    runner = smooth_full.runner()
    variant = parents.synthetic_variant(parents.SMOOTH_ID)
    planned = [
        runner.request(variant, state, COMPONENTS, 1.0)["experiment_key"]
        for _, state in sp.registered_plan("it1", synthetic_parent=True).requests()
    ]
    assert every == planned
    assert [
        {
            "split": split,
            "count": splits[split]["count"],
            "keys_sha256": splits[split]["keys_sha256"],
        }
        for split in sp.SPLITS
    ] == evidence["data"]
    for split in sp.SPLITS:
        assert splits[split]["keys_sha256"] == document_sha256(keys[split])
    # Amendment 1 §A1.4: the evidence names its manifest by SHA-256.
    assert evidence["subject"]["artifact_ref"] == document_sha256(manifest)
    # Refitting from the listed training records reproduces the coefficients bitwise.
    z, x, dt = [], [], []
    for key in keys["training"]:
        result = runner.records.result(key)
        request = runner.records.read(runner.records.request_path(key))
        assert result is not None and request is not None
        if result["envelope"]["status"] != "ok":
            continue
        inputs = request["inputs"]
        n = [float(v) for v in inputs["n"]]
        state = StreamState(n=tuple(n), temperature=float(inputs["T"]), pressure=float(inputs["P"]))
        u = sp.coordinates(state, 1.0)
        assert u is not None
        z.append(sp.scaled(u))
        x.append(float(result["envelope"]["xi"]) / n[1])
        dt.append(float(result["envelope"]["outlet"]["T"]) - float(inputs["T"]))
    refit = fit_quadratic(z, x, dt)
    assert refit.surrogate is not None
    assert list(refit.surrogate.coefficients_x) == manifest["predictor"]["coefficients"]["X"]
    assert list(refit.surrogate.coefficients_dt) == manifest["predictor"]["coefficients"]["dT_K"]


# -- A16 at the library level, A24: the records and the checker -----------------------------------


def test_the_records_validate_and_carry_their_qualifications(
    smooth_full: Study, smooth_prefix: Study
) -> None:
    for study in (smooth_full, smooth_prefix):
        manifest, evidence = study.manifest, study.outcome.evidence
        assert schema_errors("surrogate-manifest.schema.json", manifest) == []
        assert schema_errors("model-evidence.schema.json", evidence) == []
        assert evidence is not None
        assert evidence["subject"]["artifact_ref"] == document_sha256(manifest)
        assert "evidence_sha256" not in manifest
        assert manifest["qualifications"][0] == Q0
        assert manifest["qualifications"][1:6] == list(QUALIFICATIONS[:5])
        assert manifest["qualifications"][7] == QUALIFICATIONS[6]
        assert evidence is not None and evidence["scope"]["evidence_class"] == (
            "synthetic_verification"
        )
        assert manifest["surrogate_id"] == f"m04q7-{parents.SMOOTH_ID}-{study.plan_id}"
        assert manifest["promotion"]["familywise_false_pass_bound"] == 0.05
    q6 = smooth_full.manifest["qualifications"][6]
    assert q6 == (
        "nominal 0.95 (finite-sample k/(n+1) = 114/119 = 0.957983); one-sided 95 % lower bound "
        "0.916211 from 300 independent test draws; declared minimum 0.90"
    )


def _mutations() -> Iterator[tuple[str, Any, str]]:
    def q_hat(m: dict[str, Any]) -> None:
        scores = sorted(s for s in m["calibration"]["scores"] if s is not None)
        m["calibration"]["q_hat"] = scores[m["calibration"]["k"]]  # the (k+1)-th

    def hits(m: dict[str, Any]) -> None:
        m["evaluation"]["hits"] -= 1

    def verdict(m: dict[str, Any]) -> None:
        m["promotion"]["verdict"] = "NOT_PROMOTABLE"
        m["promotion"]["not_promotable"] = ["width_limit_exceeded"]

    def score_behind_verdict(m: dict[str, Any]) -> None:
        # A stored test score moved past q̂: H, the bound and the verdict no longer follow.
        m["evaluation"]["scores"][0] = 5.0

    def missing(m: dict[str, Any]) -> None:
        del m["qualifications"][2]

    def unfilled(m: dict[str, Any]) -> None:
        m["qualifications"][6] = QUALIFICATIONS[5]

    def overlapping(m: dict[str, Any]) -> None:
        splits = m["splits"]
        splits["test"]["keys"][0] = splits["training"]["keys"][0]
        splits["test"]["keys_sha256"] = document_sha256(splits["test"]["keys"])

    def n_short(m: dict[str, Any]) -> None:
        m["calibration"]["scores"].pop()
        m["calibration"]["n"] -= 1

    def m_short(m: dict[str, Any]) -> None:
        m["evaluation"]["scores"].pop()
        m["evaluation"]["m"] -= 1

    def non_finite(m: dict[str, Any]) -> None:
        m["predictor"]["coefficients"]["X"][3] = math.inf

    def not_a_number(m: dict[str, Any]) -> None:
        m["gradient"]["centres"][0]["errors"]["X"] = math.nan

    yield from (
        ("q_hat", q_hat, "is not the k-th smallest stored score"),
        ("hits", hits, "is not #{score <= q_hat}"),
        ("verdict", verdict, "is inconsistent with the stored metrics"),
        ("score_behind_verdict", score_behind_verdict, "is not #{score <= q_hat}"),
        ("missing_qualification", missing, "qualifications;"),
        ("unfilled_qualification", unfilled, "unfilled field"),
        ("overlapping_splits", overlapping, "overlapping splits"),
        ("n_short", n_short, "the plan's is 118"),
        ("m_short", m_short, "the plan's is 300"),
        ("non_finite", non_finite, "non-finite number"),
        ("not_a_number", not_a_number, "non-finite number"),
    )


def test_a24_the_checker_accepts_the_full_plans_manifest(smooth_full: Study) -> None:
    assert check_manifest(smooth_full.manifest) == []


@pytest.mark.parametrize(("name", "mutate", "reason"), list(_mutations()))
def test_a24_the_checker_rejects_each_single_mutation(
    smooth_full: Study, name: str, mutate: Any, reason: str
) -> None:
    """Each mutation is rejected, and for its own reason (not for an incidental one)."""
    mutated = copy.deepcopy(smooth_full.manifest)
    mutate(mutated)
    findings = check_manifest(mutated)
    assert any(reason in finding for finding in findings), (name, findings)


# -- the runner's request and the layering ---------------------------------------------------------


def test_the_runner_keys_a_request_without_writing_and_handshakes_once(tmp_path: Path) -> None:
    variant = parents.synthetic_variant(parents.SMOOTH_ID)
    runner = _runner(tmp_path)
    plan = sp.registered_plan("it1-prefix", synthetic_parent=True)
    _, state = plan.requests()[0]
    request = runner.request(variant, state, COMPONENTS, 1.0)
    assert list(tmp_path.rglob("*.json")) == []
    assert len(runner._handshakes) == 1
    outcome = runner.run(variant, state, COMPONENTS, 1.0)
    assert dict(outcome.request) == request
    assert len(runner._handshakes) == 1


def test_studies_never_import_the_application_layer() -> None:
    """`application` runs a study (the `surrogate_study` job); no module of `studies` imports
    `openflowsheet.application`, lazily or not (the R-237 rule for `adapters`, held here too)."""
    root = REPO_ROOT / "src" / "openflowsheet" / "studies"
    offending = {}
    for path in sorted(root.rglob("*.py")):
        found = {
            node.module or ""
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(node, ast.ImportFrom)
        } | {
            alias.name
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        upward = sorted(n for n in found if n.startswith("openflowsheet.application"))
        if upward:
            offending[str(path.relative_to(root))] = upward
    assert offending == {}


class _Stop(Exception):  # noqa: N818 - a test's interruption, not an error type
    pass


def test_an_interrupted_study_keeps_its_records_and_resumes_from_the_cache(
    tmp_path: Path, smooth_prefix: Study
) -> None:
    """Spec §10.3: a cancelled study keeps its experiment records; resuming re-reads them through
    the cache and gives the uninterrupted study's manifest bitwise."""
    variant = parents.synthetic_variant(parents.SMOOTH_ID)
    calls = 0

    def stop_after_50() -> None:
        nonlocal calls
        calls += 1
        if calls > 50:
            raise _Stop

    with pytest.raises(_Stop):
        run_study(_runner(tmp_path), variant, "it1-prefix", PLENTY, between=stop_after_50)
    assert len(list(tmp_path.glob("experiments/*/*/result.json"))) == 50
    resumed = run_study(_runner(tmp_path), variant, "it1-prefix", 149)
    assert (resumed.cold_experiments, resumed.cache_hits, resumed.cache_misses) == (149, 50, 149)
    assert resumed.manifest is not None
    assert canonical_json(resumed.manifest) == canonical_json(smooth_prefix.manifest)
