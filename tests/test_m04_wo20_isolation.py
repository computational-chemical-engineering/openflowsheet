"""M04 Amendment 2, WO-20: `surrogate_evidence`'s decision table and the synthetic parents'
isolation (spec §19 A2.7–A2.9, A2.12; register R-323, R-324).

* **M04.A45** (facet level). Each failure cause of `surrogate_evidence` fails the facet on its own,
  and no reason hides another (build log E15, E16): the rough parent replaced by its own
  NOT_PROMOTABLE surrogate fails on the verdict alone; by the smooth parent's PROMOTABLE surrogate,
  on `parent_mismatch` alone; a surrogate whose manifest does not resolve fails closed on either
  side. The sides are resolved as the project path resolves them: `check_replacement` with a
  resolver over the study manifests, as a commit passes its own (WO-8, WO-9). With A25 and A30
  (same parent, PROMOTABLE: `pass`) and A27 (both causes: both items) the table is complete.
* **M04.A46.** The shipped variant registry lists no `m04-synthetic-*` id, and a production
  `InProcessBackend` refuses a synthetic parent with its typed unknown-variant refusal.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT
from m02_variant_support import register_variants
from test_m04_wo8_replacement import (
    A19,
    _manifest,
    detail,
    judged,
    parent_of,
    results,
    surrogate,
)

from openflowsheet.adapters import variants
from openflowsheet.adapters.experiments import backends
from openflowsheet.adapters.experiments import runner as runner_module
from openflowsheet.adapters.experiments.runner import ExperimentRunner
from openflowsheet.adapters.experiments.store import ExperimentStore, ListArtifactSink
from openflowsheet.compiled import EvaluationContext
from openflowsheet.thermo.pr_c1 import PrC1Provider

sys.path.insert(0, str(REPO_ROOT / "tests" / "support"))
import m04_synthetic_parents as parents  # noqa: E402

SMOOTH = parents.synthetic_variant(parents.SMOOTH_ID)
ROUGH = parents.synthetic_variant(parents.ROUGH_ID)
#: A surrogate reference whose manifest is in no resolver (spec §A2.8): A19's id, another hash.
UNRESOLVED: Mapping[str, Any] = {**surrogate(A19), "artifact_ref": "0" * 64}


@pytest.fixture
def synthetic(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Both synthetic parents registered for the binder (the registry patched for the test only)."""
    add = register_variants(monkeypatch)
    add(SMOOTH)
    add(ROUGH)
    yield


@pytest.fixture(scope="module")
def rough(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """A18's surrogate: the rough parent's prefix study, NOT_PROMOTABLE (run here, < 2 s)."""
    return _manifest(tmp_path_factory.mktemp("a18"), ROUGH, "it1-prefix")


def items(text: str) -> list[str]:
    return text.split("; ")


# == M04.A45 =======================================================================================


def test_a45_case1_the_rough_parents_own_surrogate_fails_on_the_verdict_alone(
    synthetic: None, rough: dict[str, Any]
) -> None:
    assert rough["parent"]["variant_id"] == parents.ROUGH_ID
    report = judged(parent_of(ROUGH), surrogate(rough), rough)
    assert results(report)["surrogate_evidence"] == "fail"
    found = items(detail(report, "surrogate_evidence"))
    assert found[0] == "verdict=NOT_PROMOTABLE"
    assert found[1].startswith("the old model is its parent")
    assert not any(item.startswith("parent_mismatch") for item in found)


def test_a45_case2_a_promotable_surrogate_of_another_parent_fails_on_parent_mismatch_alone(
    synthetic: None,
) -> None:
    report = judged(parent_of(ROUGH), surrogate(A19), A19)
    assert results(report)["surrogate_evidence"] == "fail"
    found = items(detail(report, "surrogate_evidence"))
    assert found[0] == "verdict=PROMOTABLE"
    assert found[1].startswith("parent_mismatch")


def test_a45_case3_an_unresolvable_new_surrogate_fails_closed(synthetic: None) -> None:
    report = judged(parent_of(SMOOTH), UNRESOLVED, A19)
    assert results(report)["surrogate_evidence"] == "fail"
    assert "surrogate_manifest_mismatch" in detail(report, "surrogate_evidence")
    assert results(report)["resolvable"] == "fail"


def test_a45_case4_an_unresolvable_old_surrogate_makes_a_new_one_a_parent_mismatch(
    synthetic: None,
) -> None:
    report = judged(UNRESOLVED, surrogate(A19), A19)
    assert results(report)["surrogate_evidence"] == "fail"
    found = items(detail(report, "surrogate_evidence"))
    assert any(item.startswith("parent_mismatch") for item in found), found


def test_a45_case5_an_unresolvable_old_surrogate_is_not_replaced_by_a_parent(
    synthetic: None,
) -> None:
    report = judged(UNRESOLVED, parent_of(SMOOTH), A19)
    assert results(report)["surrogate_evidence"] == "fail"
    assert detail(report, "surrogate_evidence").startswith("replace_via_parent")


# == M04.A46 =======================================================================================


def test_a46a_the_shipped_registry_lists_no_synthetic_parent() -> None:
    path = REPO_ROOT / "src" / "openflowsheet" / "adapters" / "variants" / "registry.json"
    shipped = json.loads(path.read_text(encoding="utf-8"))
    assert not [variant_id for variant_id in shipped if variant_id.startswith("m04-synthetic-")]
    # The registry the binder reads is the shipped one: neither parent resolves.
    for variant in (SMOOTH, ROUGH):
        with pytest.raises(variants.VariantError, match="unknown variant"):
            variants.registered_variant(variant.variant_id)
        assert variants.resolve(variant.model_id, variant.variant_id, variant.sha256) is None


def test_a46b_a_production_in_process_backend_refuses_a_synthetic_parent(
    tmp_path: Path,
) -> None:
    # No injection is in force here: the runner's backend is the production class.
    assert runner_module.InProcessBackend is backends.InProcessBackend
    with pytest.raises(ValueError, match="not an in-process variant this build runs"):
        backends.InProcessBackend(SMOOTH)
    runner = ExperimentRunner(
        ExperimentStore(tmp_path, ListArtifactSink()),
        PrC1Provider(),
        EvaluationContext(model_version="m04-a46", constants_sha256="0" * 64),
    )
    with pytest.raises(ValueError, match="not an in-process variant this build runs"):
        runner.backend(SMOOTH)
