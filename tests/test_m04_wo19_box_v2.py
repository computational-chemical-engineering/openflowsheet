"""M04 Amendment 2, WO-19: box v2 `m04-c1-box7-v2` and its plan family `b2` (spec §19 A2.3, A2.12).

* **M04.A43 — plans and admission.** Production derives `b2-it1` (562 draws, 5 centres, 70
  stencils), `b2-it2` and `b2-it3` bitwise equal to `benchmarks/m04/plan-b2-it<i>.json`, with
  training origins expanded within `b2` (562 and 980 requests), the keys distinct. Admission:
  (v3, `b2-it1`) and (v2, `b2-it1`) are admitted; (v3, `it1`) is `invalid_request` with
  `plan_not_registered_for_parent`; (smooth, `it1-prefix`) is admitted as before; (v3, `b2-it2`)
  without a `b2-it1` manifest is `iteration_not_permitted`. The P_ref registry gives box v2's
  (lo, hi, centre, half_width) bitwise equal to `constants.box_v2` and box v1's to `constants.box`.
* **M04.A44 — the `b2` path end to end on a synthetic parent** (wiring; no statistic asserted).
  `run_study` on `m04-synthetic-smooth-v1` with `b2-it1` (632 in-process experiments): the
  manifest names P_ref v2 and `b2-it1`, carries box v2 bitwise and `b2-it1`'s keys, and passes
  the checker. The unit bound to it through the resolver and evaluated causally at L673 (the
  673.15 K loop inlet of `benchmarks/m02/g12-real-loop-v3.json`, N_tubes = 1000) equals
  Σ β φ(z) with z from `constants.box_v2` by this module's own basis code within 1e-12 relative,
  and differs from the box-v1 expression by more than 1e-6. The checker refuses the manifest with
  box v1's coordinates or v1's P_ref id.
"""

from __future__ import annotations

import json
import math
import sys
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

import pytest
from conftest import REPO_ROOT, load_json
from m02_variant_support import register_variants
from test_m04_wo7_surrogate_unit import bound, evaluated

from openflowsheet.adapters import variants
from openflowsheet.adapters.experiments.runner import ExperimentRunner
from openflowsheet.adapters.experiments.store import ExperimentStore, ListArtifactSink
from openflowsheet.application.admission import admit_surrogate_study
from openflowsheet.application.types import (
    ApiError,
    Budgets,
    Limits,
    SurrogateStudyBody,
    SurrogateStudyParent,
    schema_errors,
)
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.c1 import COMPONENTS
from openflowsheet.studies.surrogate import plan as sp
from openflowsheet.studies.surrogate.iterations import StoredManifest, predecessors
from openflowsheet.studies.surrogate.manifest import check_manifest
from openflowsheet.studies.surrogate.study import run_study
from openflowsheet.thermo import StreamState
from openflowsheet.thermo.pr_c1 import PrC1Provider

sys.path.insert(0, str(REPO_ROOT / "tests" / "support"))
import m04_synthetic_parents as parents  # noqa: E402

BENCH = REPO_ROOT / "benchmarks" / "m04"
CONSTANTS: Mapping[str, Any] = load_json(BENCH / "reference_values.json")["constants"]
PLANS: Mapping[int, Mapping[str, Any]] = {
    i: load_json(BENCH / f"plan-b2-it{i}.json") for i in (1, 2, 3)
}
V1, V2 = sp.REFERENCE_DISTRIBUTION_ID, sp.REFERENCE_DISTRIBUTION_ID_V2
REAL_V3 = variants.registered_variant("pymrm-6089593-g2-nz800-s123-v3")
REAL_V2 = variants.registered_variant("pymrm-6089593-g2-nz800-s123-v2")
SMOOTH = parents.synthetic_variant(parents.SMOOTH_ID)


def _hex(values: Sequence[float]) -> list[str]:
    return [float(x).hex() for x in values]


def _request_hex(request: StreamState) -> list[str]:
    return _hex([*request.n, request.temperature, request.pressure])


def _expected_request_hex(document: Mapping[str, Any]) -> list[str]:
    return _hex([*document["n"], document["T"], document["P"]])


def _box_hex(rows: Sequence[Mapping[str, Any]], name: str = "coordinate") -> list[list[str]]:
    return [
        [row[name], row["unit"], *_hex([row[k] for k in ("lo", "hi", "centre", "half_width")])]
        for row in rows
    ]


def _registry_hex(box: Sequence[sp.BoxCoordinate]) -> list[list[str]]:
    return [[b.name, b.unit, *_hex([b.lo, b.hi, b.centre, b.half_width])] for b in box]


# == M04.A43 =======================================================================================


@pytest.mark.parametrize(("iteration", "origins"), [(1, 144), (2, 562), (3, 980)])
def test_a43a_the_b2_plans_are_derived_bitwise(iteration: int, origins: int) -> None:
    """(a) Every draw, origin, centre and stencil of `b2-it<i>` equals its file bitwise; the
    origins resolve within `b2`; the plan's requests are distinct and pass the v3 guard."""
    plan = sp.registered_plan(f"b2-it{iteration}", synthetic_parent=False)
    document = PLANS[iteration]
    assert document["schema_version"] == "m04-plan-v2"
    assert (document["plan_id"], document["reference_distribution"]) == (plan.plan_id, V2)
    assert plan.reference_distribution == V2 and plan.box == sp.BOX_V2
    assert plan.iteration == document["iteration"] == iteration
    assert plan.counts == document["counts"]
    assert plan.counts == {"training": origins, "calibration": 118, "test": 300, "gradient": 5}
    assert plan.seeds == document["seeds"] == {s: sp.seed(iteration, s) for s in sp.SPLITS}
    for row, expected in zip(plan.training, document["training"], strict=True):
        assert row.index == expected["index"]
        source = expected
        if iteration > 1:
            origin = expected["origin"]
            assert row.origin == sp.Origin(origin["iteration"], origin["split"], origin["index"])
            assert origin["iteration"] < iteration
            source = PLANS[origin["iteration"]][origin["split"]][origin["index"]]
        assert _hex(row.u) == _hex(source["u"]), f"training[{row.index}].u"
        assert _request_hex(row.request) == _expected_request_hex(source["request"])
    for split in ("calibration", "test"):
        rows = getattr(plan, split)
        assert len(rows) == len(document[split])
        for row, expected in zip(rows, document[split], strict=True):
            assert row.index == expected["index"] and row.origin is None
            assert _hex(row.u) == _hex(expected["u"]), f"{split}[{row.index}].u"
            assert _request_hex(row.request) == _expected_request_hex(expected["request"])
    stencils = 0
    for centre, expected in zip(plan.gradient, document["gradient"], strict=True):
        assert _hex(centre.u) == _hex(expected["u"])
        assert _request_hex(centre.request) == _expected_request_hex(expected["request"])
        for point, stencil in zip(centre.stencil, expected["stencil"], strict=True):
            assert (point.coordinate, point.sign) == (stencil["coordinate"], stencil["sign"])
            assert _hex(point.u) == _hex(stencil["u"])
            assert _request_hex(point.request) == _expected_request_hex(stencil["request"])
            stencils += 1
    assert (len(plan.gradient), stencils) == (5, 70)
    requests = plan.requests()
    assert len(requests) == origins + 488
    assert len({tuple(_request_hex(r)) for _, r in requests}) == len(requests)
    assert sp.check_plan(plan, lambda _: []) is None


def _body(variant: variants.Variant, plan_id: str) -> SurrogateStudyBody:
    """The request body, valid against the served schema's `surrogate_study_body`."""
    document = {
        "parent": {
            "model_id": variant.model_id,
            "variant_id": variant.variant_id,
            "variant_sha256": variant.sha256,
        },
        "plan_id": plan_id,
        "budget": {"max_cold_experiments": 1000},
    }
    assert (
        schema_errors("surrogate-manifest.schema.json#/$defs/surrogate_study_body", document) == []
    )
    parent = document["parent"]
    return SurrogateStudyBody(
        parent=SurrogateStudyParent(
            model_id=parent["model_id"],
            variant_id=parent["variant_id"],
            variant_sha256=parent["variant_sha256"],
        ),
        plan_id=plan_id,
        max_cold_experiments=1000,
    )


def _admitted(variant: variants.Variant, plan_id: str) -> float | None | ApiError:
    return admit_surrogate_study(
        _body(variant, plan_id), budgets=Budgets(), limits=Limits(), active_jobs=0
    )


@pytest.fixture
def smooth_registered(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    register_variants(monkeypatch)(SMOOTH)
    yield


@pytest.mark.parametrize("variant", [REAL_V3, REAL_V2], ids=["v3", "v2"])
def test_a43b_b2_it1_is_admitted_for_the_real_parents(variant: variants.Variant) -> None:
    assert not isinstance(_admitted(variant, "b2-it1"), ApiError)


def test_a43b_the_v1_plans_are_refused_for_a_real_parent() -> None:
    for plan_id in ("it1", "it2", "it3", "it1-prefix"):
        refused = _admitted(REAL_V3, plan_id)
        assert isinstance(refused, ApiError), plan_id
        assert refused.code == "invalid_request"
        assert refused.detail["pointer"] == "/body/plan_id"
        assert refused.detail["reason"] == "plan_not_registered_for_parent"


def test_a43b_the_prefix_plan_is_admitted_for_the_smooth_parent(smooth_registered: None) -> None:
    assert not isinstance(_admitted(SMOOTH, "it1-prefix"), ApiError)


def test_a43b_b2_it2_needs_a_b2_it1_manifest_of_the_parent() -> None:
    refused = _admitted(REAL_V3, "b2-it2")
    assert isinstance(refused, ApiError)
    assert (refused.code, refused.detail["reason"]) == (
        "invalid_request",
        "iteration_not_permitted",
    )
    # The guard reads the same family: an `it1` manifest of v3 does not stand for `b2-it1`.
    parent = {
        "model_id": REAL_V3.model_id,
        "variant_id": REAL_V3.variant_id,
        "variant_sha256": REAL_V3.sha256,
    }
    other_family = StoredManifest("0" * 64, {"plan_id": "it1", "parent": parent})
    with pytest.raises(sp.PlanRefusedError) as raised:
        predecessors(REAL_V3, "b2-it2", [other_family])
    assert raised.value.code == "iteration_not_permitted"
    assert "b2-it1 has no manifest" in str(raised.value)


def test_a43c_the_registry_boxes_are_the_generators() -> None:
    registry = sp.REFERENCE_DISTRIBUTIONS
    assert _registry_hex(registry[V2].box) == _box_hex(CONSTANTS["box_v2"])
    assert _registry_hex(registry[V1].box) == _box_hex(CONSTANTS["box"])
    owned = {
        reference: [
            p for p, r in sp.REGISTERED_PLANS.items() if r.reference_distribution == reference
        ]
        for reference in registry
    }
    assert owned == CONSTANTS["reference_distributions"]
    assert (registry[V1].synthetic_only, registry[V2].synthetic_only) == (True, False)


# == M04.A44 =======================================================================================


def _basis(z: Sequence[float]) -> list[float]:
    """[1, z1…z7, z_i z_j (i <= j, lexicographic)]: spec §3.4's basis, written out here."""
    return [1.0, *z, *(z[i] * z[j] for i in range(7) for j in range(i, 7))]


def _z(state: StreamState, n_tubes: float, box: Sequence[Mapping[str, Any]]) -> list[float]:
    n = state.n
    n_tot = (((n[0] + n[1]) + n[2]) + n[3]) + n[4]
    u = (
        state.temperature,
        state.pressure,
        n[0] / n[1],
        n[2] / n_tot,
        n[3] / n_tot,
        n[4] / n_tot,
        n_tot / n_tubes,
    )
    return [(u[k] - row["centre"]) / row["half_width"] for k, row in enumerate(box)]


def _expected(beta: Sequence[float], z: Sequence[float]) -> float:
    return math.fsum(b * f for b, f in zip(beta, _basis(z), strict=True))


def _l673() -> StreamState:
    record = json.loads((REPO_ROOT / "benchmarks/m02/g12-real-loop-v3.json").read_text("utf-8"))
    inlet = record["summary"]["reactor_inlet"]
    assert (inlet["T_K"], inlet["P_Pa"]) == (673.15, 1.0e7)
    return StreamState(n=tuple(inlet["n_mol_s"]), temperature=673.15, pressure=1.0e7)


@pytest.fixture(scope="module")
def b2_smooth(tmp_path_factory: pytest.TempPathFactory) -> tuple[dict[str, Any], ExperimentRunner]:
    runner = ExperimentRunner(
        ExperimentStore(tmp_path_factory.mktemp("b2"), ListArtifactSink()),
        PrC1Provider(),
        EvaluationContext(model_version="m04-study", constants_sha256="0" * 64),
        backend_for=parents.backend_for(),
    )
    outcome = run_study(runner, SMOOTH, "b2-it1", 1000)
    assert outcome.manifest is not None
    assert outcome.cold_experiments == 632
    return dict(outcome.manifest), runner


def test_a44a_the_manifest_carries_box_v2_and_b2_it1s_keys(
    b2_smooth: tuple[dict[str, Any], ExperimentRunner],
) -> None:
    manifest, runner = b2_smooth
    assert manifest["reference_distribution"]["id"] == V2
    assert manifest["plan_id"] == "b2-it1"
    assert manifest["input_map"]["id"] == sp.INPUT_MAP_ID
    assert _box_hex(manifest["input_map"]["coordinates"], "name") == _box_hex(CONSTANTS["box_v2"])
    planned = [
        runner.request(SMOOTH, state, COMPONENTS, 1.0)["experiment_key"]
        for _, state in sp.registered_plan("b2-it1", synthetic_parent=True).requests()
    ]
    keys = [key for split in sp.SPLITS for key in manifest["splits"][split]["keys"]]
    assert keys == planned and len(set(keys)) == 632
    assert check_manifest(manifest) == []


def test_a44b_the_unit_scales_by_its_manifests_box(
    b2_smooth: tuple[dict[str, Any], ExperimentRunner],
) -> None:
    manifest, _ = b2_smooth
    inlet = _l673()
    _, binding = bound(inlet, manifest, n_tubes=1000.0)
    result = evaluated(binding, inlet)
    assert result.status == "ok", result.message
    outlet = result.outlets["outlet"]
    x_hat = 1.0 - outlet.n[1] / inlet.n[1]
    dt_hat = outlet.temperature - inlet.temperature
    beta = manifest["predictor"]["coefficients"]
    z_v2 = _z(inlet, 1000.0, CONSTANTS["box_v2"])
    x_v2, dt_v2 = _expected(beta["X"], z_v2), _expected(beta["dT_K"], z_v2)
    assert abs(x_hat - x_v2) <= 1e-12 * abs(x_v2)
    assert abs(dt_hat - dt_v2) <= 1e-12 * abs(dt_v2)
    # Non-vacuity: box v1's scaling would give another X.
    x_v1 = _expected(beta["X"], _z(inlet, 1000.0, CONSTANTS["box"]))
    assert abs(x_v1 - x_hat) > 1e-6


def test_a44c_the_checker_refuses_another_box_or_p_ref(
    b2_smooth: tuple[dict[str, Any], ExperimentRunner],
) -> None:
    manifest, _ = b2_smooth
    v1_box = [
        {
            "name": row["coordinate"],
            "unit": row["unit"],
            **{k: row[k] for k in ("lo", "hi", "centre", "half_width")},
        }
        for row in CONSTANTS["box"]
    ]
    swapped_box = {**manifest, "input_map": {**manifest["input_map"], "coordinates": v1_box}}
    swapped_id = {
        **manifest,
        "reference_distribution": {**manifest["reference_distribution"], "id": V1},
    }
    for document in (swapped_box, swapped_id):
        found = check_manifest(document)
        assert any(finding.startswith("input_map") for finding in found), found
