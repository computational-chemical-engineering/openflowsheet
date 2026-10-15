"""M04 WO-8: the replacement check's surrogate side (spec §8.3; ADR 0037 D3) — A25, A27–A30 at the
check level, on `C1-LOOP-M02-v1` with its reactor bound to the synthetic smooth parent.

`check_replacement` is called with a resolver over the study manifests, as a project's commit
passes its own (`LocalApplication._surrogates`). The manifests are A19's (the committed fixture,
smooth parent, prefix plan, PROMOTABLE), and A17's, A18's and the stand-in's prefix study, each run
here in process (`run_study`, < 2 s each; `tests/test_m04_study.py` pins their numbers). The project
and transaction level (commit, invalidation, preview, rollback reuse) is WO-9's.

M04.A48 (spec §20 A3.1, register R-360): a surrogate-backed instance that no replacement judges —
renamed, added, in the first revision, carried over — is named by `unpromoted_surrogates` when
its manifest resolves and re-derives a verdict other than PROMOTABLE.

A27's rough surrogate also has another parent (`m04-synthetic-rough-v1`), so its
`surrogate_evidence` detail states both reasons, the verdict first (build decision E15).
"""

from __future__ import annotations

import copy
import json
import sys
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT
from m02_variant_support import register_variants

from openflowsheet.adapters import variants
from openflowsheet.adapters.experiments.runner import ExperimentRunner
from openflowsheet.adapters.experiments.store import ExperimentStore, ListArtifactSink
from openflowsheet.application.replacement import (
    FACETS,
    ReplacementReport,
    check_replacement,
    replacements,
    unpromoted_surrogates,
)
from openflowsheet.canonical import document_sha256
from openflowsheet.compiled import EvaluationContext
from openflowsheet.studies.surrogate import reactor as sr
from openflowsheet.studies.surrogate.manifest import check_manifest, derived_verdict
from openflowsheet.studies.surrogate.study import run_study
from openflowsheet.thermo.pr_c1 import PrC1Provider

sys.path.insert(0, str(REPO_ROOT / "tests" / "support"))
import m04_synthetic_parents as parents  # noqa: E402

LOOP_PATH: Path = REPO_ROOT / "benchmarks" / "m02" / "c1-loop-standin.json"
STANDIN = variants.registered_variant("standin-x025-v1")
SMOOTH = parents.synthetic_variant(parents.SMOOTH_ID)
A19: Mapping[str, Any] = json.loads(
    (
        REPO_ROOT
        / "tests"
        / "fixtures"
        / "schemas"
        / "surrogate_manifest"
        / "valid"
        / "a19_smooth_prefix.json"
    ).read_text(encoding="utf-8")
)


def _manifest(root: Path, variant: variants.Variant, plan_id: str) -> dict[str, Any]:
    runner = ExperimentRunner(
        ExperimentStore(root, ListArtifactSink()),
        PrC1Provider(),
        EvaluationContext(model_version="m04-wo8", constants_sha256="0" * 64),
        backend_for=parents.backend_for(),
    )
    outcome = run_study(runner, variant, plan_id, 10_000)
    assert outcome.manifest is not None
    manifest = dict(outcome.manifest)
    assert check_manifest(manifest) == []
    return manifest


@pytest.fixture(scope="module")
def studies(tmp_path_factory: pytest.TempPathFactory) -> dict[str, dict[str, Any]]:
    """A17 (smooth, full plan), A18 (rough, prefix) and the stand-in's prefix surrogate."""
    rough = parents.synthetic_variant(parents.ROUGH_ID)
    return {
        "A17": _manifest(tmp_path_factory.mktemp("a17"), SMOOTH, "it1"),
        "A18": _manifest(tmp_path_factory.mktemp("a18"), rough, "it1-prefix"),
        "standin": _manifest(tmp_path_factory.mktemp("standin"), STANDIN, "it1-prefix"),
    }


@pytest.fixture
def smooth(monkeypatch: pytest.MonkeyPatch) -> Iterator[variants.Variant]:
    """The smooth parent registered for the binder (a registry patched for the test only)."""
    yield register_variants(monkeypatch)(SMOOTH)


def resolver(*manifests: Mapping[str, Any]) -> Callable[[str], Mapping[str, Any] | None]:
    table = {document_sha256(m): m for m in manifests}
    return table.get


def loop(model: Mapping[str, Any]) -> dict[str, Any]:
    """`C1-LOOP-M02-v1` with its reactor's model reference `model`."""
    document: dict[str, Any] = json.loads(LOOP_PATH.read_text(encoding="utf-8"))
    (reactor,) = (i for i in document["instances"] if i["id"] == "reactor")
    reactor["model"] = dict(model)
    return document


def parent_of(variant: variants.Variant) -> dict[str, Any]:
    return {"id": variant.model_id, "version": variant.variant_id, "artifact_ref": variant.sha256}


def surrogate(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": sr.MODEL_ID,
        "version": manifest["surrogate_id"],
        "artifact_ref": document_sha256(manifest),
    }


def judged(
    before: Mapping[str, Any], after: Mapping[str, Any], *manifests: Mapping[str, Any]
) -> ReplacementReport:
    old, new = loop(before), loop(after)
    assert replacements(old, new) == ("reactor",)
    return check_replacement(old, new, "reactor", surrogates=resolver(*manifests))


def results(report: ReplacementReport) -> dict[str, str]:
    return {facet.facet: facet.result for facet in report.facets}


def detail(report: ReplacementReport, name: str) -> str:
    (found,) = (facet.detail for facet in report.facets if facet.facet == name)
    return found


def test_the_surrogate_evidence_facet_is_last_in_the_report() -> None:
    assert FACETS[-1] == "surrogate_evidence" and len(FACETS) == 10


def test_a25_the_a19_surrogate_in_place_of_its_parent_passes_every_facet(
    smooth: variants.Variant,
) -> None:
    report = judged(parent_of(smooth), surrogate(A19), A19)
    assert results(report) == {facet: "pass" for facet in FACETS}
    assert report.compatible
    assert detail(report, "resolvable") == f"{sr.MODEL_ID} binds as surrogate {A19['surrogate_id']}"
    assert detail(report, "surrogate_evidence") == (
        f"verdict=PROMOTABLE; the old model is its parent c1.reactor {parents.SMOOTH_ID} @ "
        f"{smooth.sha256}"
    )
    # The surrogate's boundary block is its manifest's copy of the parent's (ADR 0037 D3).
    assert detail(report, "boundary_condition") == "the variants' boundary contracts are equal"
    document = report.as_document()
    assert document["from"]["synthetic"] is True and document["to"]["synthetic"] is True


def test_a27_the_rough_surrogate_is_refused_on_its_verdict(
    smooth: variants.Variant, studies: dict[str, dict[str, Any]]
) -> None:
    rough = studies["A18"]
    report = judged(parent_of(smooth), surrogate(rough), rough)
    assert not report.compatible
    assert "surrogate_evidence" in report.failed
    text = detail(report, "surrogate_evidence")
    assert text.split("; ")[0] == "verdict=NOT_PROMOTABLE"
    # E15: its parent is the rough one, so the mismatch is reported after the verdict.
    assert text.split("; ")[1].startswith("parent_mismatch")


def test_a28_a_surrogate_of_the_standin_in_place_of_the_smooth_parent_is_a_parent_mismatch(
    smooth: variants.Variant, studies: dict[str, dict[str, Any]]
) -> None:
    other = studies["standin"]
    report = judged(parent_of(smooth), surrogate(other), other)
    assert results(report)["surrogate_evidence"] == "fail"
    reasons = detail(report, "surrogate_evidence").split("; ")
    assert reasons[0] == f"verdict={derived_verdict(other).verdict}"
    assert reasons[1].startswith("parent_mismatch")


def test_a29_rollback_to_the_parent_restores_its_derivative_declaration(
    smooth: variants.Variant,
) -> None:
    report = judged(surrogate(A19), parent_of(smooth), A19)
    assert results(report) == {facet: "pass" for facet in FACETS}
    assert detail(report, "derivatives").startswith("restores_parent_declaration")
    assert detail(report, "surrogate_evidence").startswith("rollback to the old surrogate's parent")


def test_a30_a_surrogate_of_the_same_parent_replaces_another(
    smooth: variants.Variant, studies: dict[str, dict[str, Any]]
) -> None:
    full = studies["A17"]
    report = judged(surrogate(A19), surrogate(full), A19, full)
    assert results(report)["surrogate_evidence"] == "pass"
    assert report.compatible, report.as_document()
    assert detail(report, "surrogate_evidence").startswith(
        "verdict=PROMOTABLE; the old model is a surrogate of the same parent"
    )


def test_replacing_a_surrogate_by_another_model_than_its_parent_fails_replace_via_parent(
    smooth: variants.Variant,
) -> None:
    report = judged(surrogate(A19), parent_of(STANDIN), A19)
    assert results(report)["surrogate_evidence"] == "fail"
    assert detail(report, "surrogate_evidence").startswith("replace_via_parent")
    # Not the parent, so the derivatives exception does not apply either.
    assert results(report)["derivatives"] == "fail"


def test_a_surrogate_that_does_not_resolve_fails_resolvable_and_surrogate_evidence(
    smooth: variants.Variant,
) -> None:
    report = judged(parent_of(smooth), surrogate(A19))  # no manifest in the resolver
    assert results(report)["resolvable"] == "fail"
    assert "surrogate_manifest_mismatch" in detail(report, "resolvable")
    assert results(report)["surrogate_evidence"] == "fail"
    assert results(report)["degrees_of_freedom"] == "fail"  # the new revision does not bind


def test_the_verdict_is_rederived_from_the_stored_metrics_not_read(
    studies: dict[str, dict[str, Any]],
) -> None:
    tampered = copy.deepcopy(studies["A18"])
    tampered["promotion"]["verdict"] = "PROMOTABLE"
    assert derived_verdict(tampered).verdict == "NOT_PROMOTABLE"
    assert derived_verdict(A19).verdict == "PROMOTABLE"
    # The checker refuses the tampered manifest, so it never resolves as a surrogate (A24).
    assert any("verdict" in problem for problem in check_manifest(tampered))


# == M04.A48 (R-360): a surrogate that no replacement judges =======================================


def renamed(model: Mapping[str, Any], new_id: str = "reactor_b") -> dict[str, Any]:
    """The loop with its reactor renamed to `new_id`, bound to `model`, and S3/S4 rewired: the
    reviewer's probe (four `set` edits) as a document."""
    document = loop(model)
    (reactor,) = (i for i in document["instances"] if i["id"] == "reactor")
    reactor["id"] = new_id
    for connection in document["connections"]:
        for end in ("from", "to"):
            if connection[end].get("instance") == "reactor":
                connection[end]["instance"] = new_id
    return document


def test_a48_a_renamed_instance_bound_to_the_rough_surrogate_is_unpromoted(
    smooth: variants.Variant, studies: dict[str, dict[str, Any]]
) -> None:
    rough = studies["A18"]
    before, after = loop(parent_of(smooth)), renamed(surrogate(rough))
    assert replacements(before, after) == ()  # no replacement judges it: the MF1 gap
    assert unpromoted_surrogates(before, after, surrogates=resolver(rough)) == (
        ("reactor_b", "verdict=NOT_PROMOTABLE"),
    )


def test_a48_an_added_instance_and_a_first_revision_are_judged(
    smooth: variants.Variant, studies: dict[str, dict[str, Any]]
) -> None:
    rough = studies["A18"]
    added = renamed(surrogate(rough), "reactor_c")
    added["instances"].append(loop(parent_of(smooth))["instances"][REACTOR_INDEX])
    assert unpromoted_surrogates(loop(parent_of(smooth)), added, surrogates=resolver(rough)) == (
        ("reactor_c", "verdict=NOT_PROMOTABLE"),
    )
    assert unpromoted_surrogates({}, loop(surrogate(rough)), surrogates=resolver(rough)) == (
        ("reactor", "verdict=NOT_PROMOTABLE"),
    )
    # Carried over unchanged, it is still judged: no revision holds an unpromoted surrogate.
    carried = loop(surrogate(rough))
    assert unpromoted_surrogates(carried, carried, surrogates=resolver(rough)) == (
        ("reactor", "verdict=NOT_PROMOTABLE"),
    )


def test_a48_a_promotable_surrogate_enters(
    smooth: variants.Variant,
) -> None:
    assert unpromoted_surrogates({}, renamed(surrogate(A19)), surrogates=resolver(A19)) == ()
    # Unresolved, it is the binder's `surrogate_manifest_mismatch`.
    assert unpromoted_surrogates({}, loop(surrogate(A19)), surrogates=resolver()) == ()
    # A judged replacement is `surrogate_evidence`'s, not named twice.
    before, after = loop(parent_of(smooth)), loop(surrogate(A19))
    assert replacements(before, after) == ("reactor",)
    assert unpromoted_surrogates(before, after, surrogates=resolver()) == ()


REACTOR_INDEX = next(i for i, item in enumerate(loop({})["instances"]) if item["id"] == "reactor")
