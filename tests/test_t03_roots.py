"""T03 §8: which root a solve returned — branch provenance, the root fingerprint, `same_root`.

A19–A22 against `benchmarks/t03/reference_values.yaml` (`multiple_roots`): REC-05 with γ = 0.1 has
two registered fixed points, the designed `t*` and a second genuine root `S1`, 0.963 apart in
scaled coordinates. Three solves reach them by different routes; the fingerprint says which, and
`same_root` decides at `δ_root = 1e-4`. On SYN-001, one root reached three ways is `SAME` with
three histories. Nothing here claims uniqueness or stability (`claims` are `NOT_ASSESSED`).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from openflowsheet.numerics.anderson import RecyclePolicy
from openflowsheet.orchestrator.merge import ConvergeResult, converge_with_merge
from openflowsheet.orchestrator.roots import DELTA_ROOT, same_root
from openflowsheet.orchestrator.trace import Trace

REPO_ROOT = Path(__file__).resolve().parents[1]
IDENTITY = ("REC-05-gamma-0.1@t03", "0" * 64)


@pytest.fixture(scope="module")
def t02() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(
        (REPO_ROOT / "benchmarks" / "t02" / "reference_values.yaml").read_text()
    )
    return loaded


@pytest.fixture(scope="module")
def t03() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(
        (REPO_ROOT / "benchmarks" / "t03" / "reference_values.yaml").read_text()
    )
    return loaded


def rec_05_run(
    t02: dict[str, Any], start: str, policy: RecyclePolicy | None = None
) -> ConvergeResult:
    """REC-05 (γ = 0.1) through the recycle and, if it stalls, T02 §4.4's merge edge."""
    from test_t02_merge import rec_05

    loop, t_110 = rec_05(t02, 0.1)
    t_star = np.array([1.0, 2.0, 3.0])
    t0 = {"1.1 t*": t_110, "t*": t_star}[start]
    trace = Trace()
    return converge_with_merge(
        loop.problem,
        t0,
        policy=policy,
        merge=loop.region(trace),
        trace=trace,
        identity=IDENTITY,
    )


def as_state(result: ConvergeResult) -> dict[str, float]:
    return {f"t{i}": float(value) for i, value in enumerate(result.x)}


SCALES = {"t0": 3.0, "t1": 3.0, "t2": 3.0}
IDS = ("t0", "t1", "t2")


def near(result: ConvergeResult, point: list[Any]) -> bool:
    return max(abs(float(v) - float(p)) / 3.0 for v, p in zip(result.x, point, strict=True)) <= (
        DELTA_ROOT
    )


def test_a19_rec_05_three_routes_two_roots(t02: dict[str, Any], t03: dict[str, Any]) -> None:
    roots = t03["multiple_roots"]["REC-05 gamma=0.1"]
    mr_a = rec_05_run(t02, "1.1 t*")
    mr_b = rec_05_run(t02, "t*")
    mr_c = rec_05_run(t02, "1.1 t*", RecyclePolicy(depth_max=0))

    assert mr_a.outcome == "CONVERGED" and near(mr_a, roots["S1"])
    assert mr_b.outcome == "CONVERGED" and mr_b.recycle.iterations == 0
    assert near(mr_b, roots["t_star"])
    assert mr_c.recycle.outcome == "RECYCLE_STAGNATION" and mr_c.recycle.iterations == 20
    assert mr_c.outcome == "CONVERGED" and mr_c.merged.iterations <= 5
    assert near(mr_c, roots["S1"])

    for result in (mr_a, mr_b, mr_c):
        first = result.branch_provenance[0]
        assert first["initializer_source"] == "user_guess"
        assert len(first["opening_state_sha256"]) == 64
    cores = [(item["core"], item["opening_source"]) for item in mr_c.branch_provenance]
    assert cores == [("anderson", "initializer"), ("newton", "merge_best_iterate")]

    assert mr_a.root_fingerprint is not None and mr_b.root_fingerprint is not None
    assert mr_c.root_fingerprint is not None
    assert (
        same_root(
            mr_a.root_fingerprint,
            as_state(mr_a),
            mr_b.root_fingerprint,
            as_state(mr_b),
            SCALES,
            IDS,
        )
        == "DISTINCT"
    )
    assert (
        same_root(
            mr_a.root_fingerprint,
            as_state(mr_a),
            mr_c.root_fingerprint,
            as_state(mr_c),
            SCALES,
            IDS,
        )
        == "SAME"
    ), "one root, two histories"
    assert mr_a.branch_provenance != mr_c.branch_provenance


def test_a22_a_root_of_another_problem_is_not_comparable(t02: dict[str, Any]) -> None:
    mr_a = rec_05_run(t02, "1.1 t*")
    assert mr_a.root_fingerprint is not None
    state = as_state(mr_a)
    for key, value in (("model_version", "another@model"), ("variable_ids_sha256", "f" * 64)):
        other = {**mr_a.root_fingerprint, key: value}
        assert (
            same_root(mr_a.root_fingerprint, state, other, state, SCALES, IDS) == "NOT_COMPARABLE"
        )


def test_a20_syn001_one_root_three_histories(monkeypatch: pytest.MonkeyPatch) -> None:
    """A02-360 from 358 K (one attempt), PHS-02 from 350 K (LIQUID → TWO_PHASE) and PHS-03 from
    400 K (VAPOR → TWO_PHASE): pairwise `SAME`, with different histories and starting points."""
    from test_t03_phase import run_case

    from openflowsheet.numerics.scaling import Scaling

    runs = {
        case_id: run_case(case_id, monkeypatch).result
        for case_id in (
            "SYN-001-A02-360",
            "SYN-001-A02-360-liquid-guess",
            "SYN-001-A02-360-vapor-guess",
        )
    }
    assert [len(result.branch_provenance) for result in runs.values()] == [1, 2, 2]
    starts = {result.branch_provenance[0]["opening_state_sha256"] for result in runs.values()}
    assert len(starts) == 3
    from test_t02_a02 import revision, structure

    scales = Scaling.from_spec(structure(revision("SYN-001-A02-360")).binding.spec).column
    results = list(runs.values())
    for a in range(3):
        for b in range(a + 1, 3):
            fa, fb = results[a].root_fingerprint, results[b].root_fingerprint
            assert fa is not None and fb is not None
            ids = tuple(results[a].state)
            assert same_root(fa, results[a].state, fb, results[b].state, scales, ids) == "SAME"


def test_a21_no_overclaim_and_the_certificate_carries_the_history() -> None:
    """OFF-B's certificate lists its two attempts in the new item shape, carries a fingerprint
    whose claims are `NOT_ASSESSED`, and validates against the extended schema."""
    from test_k03_attempts import OFF_B, flowsheet_for, variants

    from openflowsheet.orchestrator.tear import solve_tear
    from openflowsheet.verify.certificate import verify

    reference = yaml.safe_load(
        (REPO_ROOT / "benchmarks" / "syn001" / "reference_values.yaml").read_text()
    )
    flowsheet = flowsheet_for(variants(reference)["SYN-001-nominal"])
    result, _ = solve_tear(flowsheet, initial_recycle=OFF_B)
    certificate = verify(flowsheet, result).as_document()

    history = [
        (dict(item["signature"])["U-FLASH"], item["decision"], item["cause"])
        for item in certificate["branch_provenance"]
    ]
    assert history == [
        ("LIQUID", "restart", "phase_wall(patience, U-FLASH:LIQUID->TWO_PHASE)"),
        ("TWO_PHASE", "converged", ""),
    ]
    fingerprint = certificate["root_fingerprint"]
    assert fingerprint["claims"] == {
        "uniqueness": "NOT_ASSESSED",
        "dynamic_stability": "NOT_ASSESSED",
    }
    # Review M1: from the reconstructed state, every lifted split (was the flash alone).
    assert fingerprint["branch_found"] == [["U-HEAT", "LIQUID"], ["U-FLASH", "TWO_PHASE"]]

    documents = [
        json.loads(path.read_text()) for path in (REPO_ROOT / "schemas").glob("*.schema.json")
    ]
    registry = Registry().with_resources(
        (document["$id"], Resource.from_contents(document))
        for document in documents
        if "$id" in document
    )
    schema = next(d for d in documents if d.get("title") == "SolutionCertificate")
    errors = list(Draft202012Validator(schema, registry=registry).iter_errors(certificate))
    assert not errors, errors[0].message
    text = json.dumps(certificate).lower()
    assert "unique root" not in text and "stable" not in text.replace("dynamic_stability", "")


def test_m1_one_root_by_the_tear_and_by_the_eo_path_is_the_same_root() -> None:
    """Review M1 (P1): SYN-001's nominal root solved by the tear and by the EO region is 4.4e-16
    apart in scaled coordinates; its fingerprint must not depend on the path."""
    from test_t02_region import case, initializer, solve

    from openflowsheet.numerics.scaling import Scaling
    from openflowsheet.orchestrator.tear import INITIALIZER_ID, solve_tear

    item = case("SYN-001-nominal")
    tear, _ = solve_tear(item.flowsheet)
    eo = solve(item, initializer(item), source=INITIALIZER_ID)
    assert tear.root_fingerprint is not None and eo.root_fingerprint is not None
    assert tear.final_state is not None
    assert tear.root_fingerprint["branch_found"] == eo.root_fingerprint["branch_found"]
    scales = Scaling.from_spec(item.spec).column
    ids = item.spec.variable_ids
    verdict = same_root(
        tear.root_fingerprint, tear.final_state, eo.root_fingerprint, eo.state, scales, ids
    )
    assert verdict == "SAME"


def test_s3_same_root_refuses_states_it_cannot_vouch_for(t02: dict[str, Any]) -> None:
    """Review S3 (P8): empty scales, or a fingerprint paired with another state, raise — they
    used to return `SAME` for REC-05's two roots, 0.963 apart."""
    from openflowsheet.orchestrator.roots import RootComparisonError

    mr_a = rec_05_run(t02, "1.1 t*")
    mr_b = rec_05_run(t02, "t*")
    assert mr_a.root_fingerprint is not None and mr_b.root_fingerprint is not None
    with pytest.raises(RootComparisonError):
        same_root(
            mr_a.root_fingerprint, as_state(mr_a), mr_b.root_fingerprint, as_state(mr_b), {}, IDS
        )
    with pytest.raises(RootComparisonError):
        same_root(
            mr_a.root_fingerprint,
            as_state(mr_b),
            mr_b.root_fingerprint,
            as_state(mr_b),
            SCALES,
            IDS,
        )


def test_a21_a_solve_that_did_not_converge_receives_no_certificate() -> None:
    """The review's A21 ruling (K04 §3, A20): OFF-B with `max_attempts = 1` ends
    `ATTEMPTS_EXHAUSTED`; `verify` refuses it (no certificate exists), and the solve result
    itself carries its one attempt — a restart the budget refused."""
    from test_k03_attempts import OFF_B, flowsheet_for, variants

    from openflowsheet.orchestrator.tear import solve_tear
    from openflowsheet.orchestrator.trace import SolvePolicy
    from openflowsheet.verify.certificate import verify
    from openflowsheet.verify.checks import VerifierError

    reference = yaml.safe_load(
        (REPO_ROOT / "benchmarks" / "syn001" / "reference_values.yaml").read_text()
    )
    flowsheet = flowsheet_for(variants(reference)["SYN-001-nominal"])
    policy = SolvePolicy(policy_id="t03-a21", residual_tolerances={}, scales={}, max_attempts=1)
    result, _ = solve_tear(flowsheet, initial_recycle=OFF_B, policy=policy)
    assert result.outcome == "ATTEMPTS_EXHAUSTED"
    with pytest.raises(VerifierError):
        verify(flowsheet, result)
    (item,) = result.branch_provenance
    assert item["decision"] == "restart" and item["cause"].startswith("phase_wall(patience, ")
    assert result.root_fingerprint is None
