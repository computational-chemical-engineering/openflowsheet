"""M04.A36 (WO-15): when a later iteration may run, its predecessors and its family-wise bound.

Spec §5.5 and §18 A1.2 (ADR 0036 Amendment 1 D2, R-290): `it<i>`, i ≥ 2, is admitted only when every
`it<j>`, j < i, of the same parent has a manifest with verdict NOT_PROMOTABLE, `not_promotable ==
["coverage_bound_below_minimum"]` and no INSUFFICIENT_EVIDENCE reason; otherwise `invalid_request`
with `detail.reason` `iteration_not_permitted`. The `it<i>` manifest lists those manifests as
`predecessors` and records the family-wise bound 0.05 × i.

- The predicate on (verdict, reason lists): permitted; earlier PROMOTABLE; earlier width failure;
  coverage with another reason; earlier IE.
- The guard over stored manifests: earlier manifest missing; another parent's or the prefix plan's
  manifest does not count; A17's PROMOTABLE `it1` refuses `it2`; a manifest that fails the checker,
  two distinct manifests of one iteration, and a broken chain refuse; a coverage-only failure
  permits, and `it3` needs both.
- `it2` end to end on the smooth parent's A17 store: the 562 inherited draws are served by the cache
  (cold 488, so a budget of 487 is refused and 488 runs), the inherited failures stay failures, the
  manifest lists its predecessor and the bound 0.1, and passes the checker.
- Through the application with the stand-in: `it2` before any `it1`, and after a PROMOTABLE `it1`,
  is `invalid_request` / `iteration_not_permitted`; after a registered coverage-only `it1` it is
  admitted and its manifest names that predecessor.

A coverage-only failure does not occur on the registered parents (a correct pipeline fails the
test with probability ≈ 0.10), so `coverage_failed` builds one from a real manifest: test scores
moved past q̂ until H < h_min, with H, L, Q6 and the verdict re-derived as the checker re-derives
them. It is a constructed input of the guard, never evidence.
"""

from __future__ import annotations

import copy
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT

from openflowsheet.adapters import variants
from openflowsheet.adapters.experiments.runner import ExperimentRunner
from openflowsheet.adapters.experiments.store import ExperimentStore, ListArtifactSink
from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.store import ArtifactRow
from openflowsheet.canonical import canonical_json, document_sha256
from openflowsheet.compiled import EvaluationContext
from openflowsheet.studies.surrogate import plan as sp
from openflowsheet.studies.surrogate.conformal import (
    clopper_pearson_lower,
    coverage_hits,
    h_min,
)
from openflowsheet.studies.surrogate.iterations import (
    StoredManifest,
    coverage_only_failure,
    predecessors,
)
from openflowsheet.studies.surrogate.manifest import check_manifest, qualifications
from openflowsheet.studies.surrogate.study import StudyOutcome, run_study
from openflowsheet.thermo.pr_c1 import PrC1Provider

sys.path.insert(0, str(REPO_ROOT / "tests" / "support"))
import m04_synthetic_parents as parents  # noqa: E402
from test_m04_study_job import body, read, result_of, submit  # noqa: E402

SMOOTH = parents.synthetic_variant(parents.SMOOTH_ID)
STANDIN = variants.registered_variant("standin-x025-v1")
CODE = "iteration_not_permitted"


def _runner(root: Path, variant: variants.Variant | None = None) -> ExperimentRunner:
    if variant is None:  # the synthetic parents, in process
        return ExperimentRunner(
            ExperimentStore(root, ListArtifactSink()),
            PrC1Provider(),
            EvaluationContext(model_version="m04-study", constants_sha256="0" * 64),
            backend_for=parents.backend_for(),
        )
    return ExperimentRunner(  # a registered parent, as the job builds its runner
        ExperimentStore(root, ListArtifactSink()),
        PrC1Provider(),
        EvaluationContext(model_version=variant.variant_id, constants_sha256=variant.sha256),
    )


def coverage_failed(manifest: dict[str, Any], moved: int = 30) -> dict[str, Any]:
    """`manifest` with its first `moved` finite test scores set to 0.5 (past q̂, within the width)
    and H, L, Q6 and the verdict re-derived: NOT_PROMOTABLE on the coverage test alone."""
    failed = copy.deepcopy(manifest)
    evaluation = failed["evaluation"]
    q_hat = failed["calibration"]["q_hat"]
    assert q_hat is not None and q_hat < 0.5
    finite = [i for i, s in enumerate(evaluation["scores"]) if s is not None]
    for i in finite[:moved]:
        evaluation["scores"][i] = 0.5
    m = evaluation["m"]
    hits = coverage_hits(tuple(evaluation["scores"]), q_hat)
    assert hits < h_min(m)
    evaluation["hits"] = hits
    evaluation["lower_bound"] = clopper_pearson_lower(hits, m)
    calibration = failed["calibration"]
    failed["qualifications"] = qualifications(
        failed["synthetic"], calibration["n"], calibration["k"], evaluation["lower_bound"], m
    )
    failed["promotion"].update(
        verdict="NOT_PROMOTABLE", insufficient=[], not_promotable=["coverage_bound_below_minimum"]
    )
    assert check_manifest(failed) == []
    return failed


def stored(document: dict[str, Any]) -> StoredManifest:
    return StoredManifest(document_sha256(document), document)


@pytest.fixture(scope="module")
def smooth_it1(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, StudyOutcome]:
    root = tmp_path_factory.mktemp("smooth-it1")
    outcome = run_study(_runner(root), SMOOTH, "it1", 10_000)
    assert outcome.verdict == "PROMOTABLE"  # A17
    return root, outcome


@pytest.fixture(scope="module")
def it1_manifest(smooth_it1: tuple[Path, StudyOutcome]) -> dict[str, Any]:
    manifest = smooth_it1[1].manifest
    assert manifest is not None
    return dict(manifest)


# -- the predicate --------------------------------------------------------------------------------


def _promotion(verdict: str, insufficient: list[str], not_promotable: list[str]) -> dict[str, Any]:
    return {"verdict": verdict, "insufficient": insufficient, "not_promotable": not_promotable}


@pytest.mark.parametrize(
    ("promotion", "permitted"),
    [
        (_promotion("NOT_PROMOTABLE", [], ["coverage_bound_below_minimum"]), True),
        (_promotion("PROMOTABLE", [], []), False),
        (_promotion("NOT_PROMOTABLE", [], ["width_limit_exceeded"]), False),
        (
            _promotion(
                "NOT_PROMOTABLE", [], ["coverage_bound_below_minimum", "gradient_limit_exceeded"]
            ),
            False,
        ),
        (_promotion("INSUFFICIENT_EVIDENCE", ["plan_incomplete"], []), False),
        (
            _promotion(
                "INSUFFICIENT_EVIDENCE",
                ["gradient_check_incomplete"],
                ["coverage_bound_below_minimum"],
            ),
            False,
        ),
    ],
    ids=["permitted", "promotable", "width", "coverage_and_gradient", "ie", "ie_and_coverage"],
)
def test_a36_the_iteration_predicate(promotion: dict[str, Any], permitted: bool) -> None:
    assert coverage_only_failure(promotion) is permitted


# -- the guard over stored manifests --------------------------------------------------------------


def _refused(plan_id: str, manifests: list[StoredManifest], variant: Any = SMOOTH) -> str:
    with pytest.raises(sp.PlanRefusedError) as refused:
        predecessors(variant, plan_id, manifests)
    assert refused.value.code == CODE
    return str(refused.value)


def test_a36_iteration_1_has_no_predecessors() -> None:
    assert predecessors(SMOOTH, "it1", []) == ()
    assert predecessors(SMOOTH, "it1-prefix", []) == ()


def test_a36_an_earlier_manifest_missing_refuses() -> None:
    assert "it1 has no manifest" in _refused("it2", [])


def test_a36_it2_after_a17s_promotable_it1_is_not_permitted(it1_manifest: dict[str, Any]) -> None:
    assert "ended PROMOTABLE" in _refused("it2", [stored(it1_manifest)])


def test_a36_a_coverage_only_failure_permits_it2(it1_manifest: dict[str, Any]) -> None:
    failed = coverage_failed(it1_manifest)
    assert predecessors(SMOOTH, "it2", [stored(failed)]) == (document_sha256(failed),)


def test_a36_only_the_same_parents_iteration_manifests_count(it1_manifest: dict[str, Any]) -> None:
    failed = coverage_failed(it1_manifest)
    other = copy.deepcopy(failed)
    other["parent"]["variant_sha256"] = "0" * 64
    assert "it1 has no manifest" in _refused("it2", [stored(other)])
    prefix = copy.deepcopy(failed)
    prefix["plan_id"] = "it1-prefix"
    assert "it1 has no manifest" in _refused("it2", [stored(prefix)])


def test_a36_a_manifest_failing_the_checker_does_not_permit(it1_manifest: dict[str, Any]) -> None:
    edited = copy.deepcopy(it1_manifest)  # a verdict edited by hand: the checker re-derives it
    edited["promotion"].update(
        verdict="NOT_PROMOTABLE", not_promotable=["coverage_bound_below_minimum"]
    )
    assert "fails the checker" in _refused("it2", [stored(edited)])


def test_a36_two_distinct_manifests_of_one_iteration_are_ambiguous(
    it1_manifest: dict[str, Any],
) -> None:
    first, second = coverage_failed(it1_manifest, 30), coverage_failed(it1_manifest, 31)
    assert "predecessor is ambiguous" in _refused("it2", [stored(first), stored(second)])
    # The same manifest twice (a fully cached rerun writes it bitwise again) is one.
    assert predecessors(SMOOTH, "it2", [stored(first), stored(first)]) == (document_sha256(first),)


@pytest.fixture(scope="module")
def smooth_it2(
    smooth_it1: tuple[Path, StudyOutcome], it1_manifest: dict[str, Any]
) -> tuple[StudyOutcome, StudyOutcome, tuple[str, ...]]:
    """`it2` on A17's store, after a coverage-only `it1`: first with a budget one below its cache
    misses (refused, nothing run), then with exactly its misses."""
    root, _ = smooth_it1
    chain = (document_sha256(coverage_failed(it1_manifest)),)
    short = run_study(_runner(root), SMOOTH, "it2", 487, predecessors=chain)
    outcome = run_study(_runner(root), SMOOTH, "it2", 488, predecessors=chain)
    return short, outcome, chain


def test_a36_it3_needs_both_earlier_iterations_and_their_chain(
    smooth_it1: tuple[Path, StudyOutcome],
    it1_manifest: dict[str, Any],
    smooth_it2: tuple[StudyOutcome, StudyOutcome, tuple[str, ...]],
) -> None:
    it1 = coverage_failed(it1_manifest)
    it2_manifest = smooth_it2[1].manifest
    assert it2_manifest is not None
    it2 = coverage_failed(dict(it2_manifest))
    assert "it2 has no manifest" in _refused("it3", [stored(it1)])
    assert predecessors(SMOOTH, "it3", [stored(it2), stored(it1)]) == (
        document_sha256(it1),
        document_sha256(it2),
    )
    # An it2 whose own predecessor is another it1 (fully cached, so cheap) breaks the chain.
    root, _ = smooth_it1
    other = run_study(_runner(root), SMOOTH, "it2", 0, predecessors=("f" * 64,))
    assert other.manifest is not None
    unchained = coverage_failed(dict(other.manifest))
    assert "lists predecessors" in _refused("it3", [stored(it1), stored(unchained)])


# -- it2 end to end at the library level ----------------------------------------------------------


def test_a36_it2_runs_its_inherited_draws_from_the_cache(
    smooth_it1: tuple[Path, StudyOutcome],
    it1_manifest: dict[str, Any],
    smooth_it2: tuple[StudyOutcome, StudyOutcome, tuple[str, ...]],
) -> None:
    root, _ = smooth_it1
    short, outcome, chain = smooth_it2
    # A1.2: a cached record costs nothing against the budget; only the 488 fresh are misses.
    assert (short.insufficient, short.cache_misses, short.manifest) == (
        ("budget_below_plan",),
        488,
        None,
    )
    assert (outcome.cold_experiments, outcome.cache_hits, outcome.cache_misses) == (488, 562, 488)
    manifest = outcome.manifest
    assert manifest is not None
    assert (manifest["plan_id"], manifest["iteration"]) == ("it2", 2)
    assert manifest["predecessors"] == list(chain)
    assert manifest["promotion"]["familywise_false_pass_bound"] == 0.1
    assert manifest["surrogate_id"] == f"m04q7-{parents.SMOOTH_ID}-it2"
    assert check_manifest(manifest) == []
    # The inherited keys are it1's training, calibration and test keys, in that order, and its
    # deterministic failures are failures again (cached, excluded from the fit).
    splits = it1_manifest["splits"]
    inherited = [
        *splits["training"]["keys"],
        *splits["calibration"]["keys"],
        *splits["test"]["keys"],
    ]
    assert manifest["splits"]["training"]["keys"] == inherited
    offsets = {"training": 0, "calibration": 144, "test": 262}
    expected_failed = sorted(
        offsets[split] + entry["index"] for split in offsets for entry in splits[split]["failed"]
    )
    assert [e["index"] for e in manifest["splits"]["training"]["failed"]] == expected_failed
    assert manifest["predictor"]["fit"]["training_ok"] == 562 - len(expected_failed)
    assert (manifest["calibration"]["n"], manifest["evaluation"]["m"]) == (118, 300)
    # Rerun fully cached: bitwise the same manifest.
    again = run_study(_runner(root), SMOOTH, "it2", 0, predecessors=chain)
    assert canonical_json(again.manifest) == canonical_json(manifest)


def test_run_study_requires_one_predecessor_per_earlier_iteration(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="0 predecessors for iteration 2"):
        run_study(_runner(tmp_path), SMOOTH, "it2", 10_000)
    with pytest.raises(ValueError, match="1 predecessors for iteration 1"):
        run_study(_runner(tmp_path), SMOOTH, "it1-prefix", 10_000, predecessors=("0" * 64,))


def test_the_checker_requires_the_predecessors_and_the_bound(it1_manifest: dict[str, Any]) -> None:
    extra = {**copy.deepcopy(it1_manifest), "predecessors": ["0" * 64]}
    assert any("1 predecessors; iteration 1 has 0" in f for f in check_manifest(extra))
    loose = copy.deepcopy(it1_manifest)
    loose["promotion"]["familywise_false_pass_bound"] = 0.1
    assert any("familywise_false_pass_bound" in f for f in check_manifest(loose))


# -- through the application ----------------------------------------------------------------------


@pytest.fixture
def app(tmp_path: Path) -> Iterator[LocalApplication]:
    application = LocalApplication.create(tmp_path / "project")
    try:
        yield application
    finally:
        application.close()


def _refused_submission(app: LocalApplication, key: str, document: dict[str, Any]) -> str:
    with pytest.raises(ApplicationError) as raised:
        submit(app, key, document)
    error = raised.value.error
    assert (error.code, error.detail["pointer"], error.detail["reason"]) == (
        "invalid_request",
        "/body/plan_id",
        CODE,
    )
    return error.message


def test_a36_it2_of_the_standin_through_the_application(app: LocalApplication) -> None:
    assert "it1 has no manifest" in _refused_submission(app, "early", body(plan_id="it2"))
    job = submit(app, "it1", body(plan_id="it1"))["job"]
    assert result_of(app, job["job_id"])["surrogate_study"]["verdict"] == "PROMOTABLE"
    assert "ended PROMOTABLE" in _refused_submission(app, "after", body(plan_id="it2"))
    assert len(dispatch_jobs(app)) == 1  # a refusal creates no job


def test_a36_it2_is_admitted_after_a_coverage_only_it1(
    app: LocalApplication, tmp_path: Path
) -> None:
    library = run_study(_runner(tmp_path / "library", STANDIN), STANDIN, "it1", 10_000)
    assert library.manifest is not None
    failed = coverage_failed(dict(library.manifest))
    sha256 = register_manifest(app, failed)
    job = submit(app, "it2", body(plan_id="it2", budget=2000))["job"]
    assert job["status"] == "completed"
    answer = result_of(app, job["job_id"])["surrogate_study"]
    assert answer["surrogate_id"] == "m04q7-standin-x025-v1-it2"
    assert (answer["cold_experiments"], answer["cache_hits"]) == (1050, 0)
    manifest = read(app, job["outputs"][0]["artifact_id"])
    assert manifest["predecessors"] == [sha256]
    assert manifest["promotion"]["familywise_false_pass_bound"] == 0.1
    assert check_manifest(manifest) == []
    # it2 was PROMOTABLE, so it3 is not permitted.
    assert answer["verdict"] == "PROMOTABLE"
    assert "it2 ended PROMOTABLE" in _refused_submission(app, "it3", body(plan_id="it3"))


def dispatch_jobs(app: LocalApplication) -> list[Any]:
    from openflowsheet.application.operations import dispatch

    items: list[Any] = dispatch(app, "list_jobs", {})["items"]
    return items


def register_manifest(app: LocalApplication, document: dict[str, Any]) -> str:
    """Register `document` as a `surrogate_manifest` artifact of the project (as a job writes
    one: canonical bytes under the files root) and return its SHA-256."""
    data = canonical_json(document)
    relpath = "imports/m04-constructed/surrogate-manifest.json"
    path = app.files_root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    sha256 = document_sha256(document)
    row = ArtifactRow(
        artifact_id="m04-constructed:surrogate-manifest.json",
        job_id=None,
        kind="surrogate_manifest",
        name="surrogate-manifest.json",
        sha256=sha256,
        size_bytes=len(data),
        relpath=relpath,
    )
    with app.store.writing() as connection:
        app.store.register_artifacts(connection, [row])
    assert json.loads(path.read_bytes()) == document
    return sha256
