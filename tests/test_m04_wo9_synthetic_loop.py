"""M04 WO-9: promotion and rollback on the synthetic loop, end to end through a project (spec §11,
"Promotion and rollback"; M04.A25–A30; ADR 0037 D2–D4).

The project: `C1-LOOP-M02-v1` with its reactor bound to `m04-synthetic-smooth-v1`, solved once on
`revision_coupled` (as M02 G8 binds its test-only variant). Its surrogates are written by the
project's own `surrogate_study` jobs: the smooth parent's prefix study (A19's), its full-plan study
(A17's), the rough parent's prefix study (A18's) and the stand-in's prefix study.

Test-only, as M02's registry patch (`m02_variant_support.register_variants`): the synthetic parents
are registered for the test, and the experiment runner's in-process backend is
`m04_synthetic_parents.backend_for()` (the synthetic parents by id; every other variant the real
`InProcessBackend`), because the synthetic parents' module is not package data (build decision
E22). Everything else is the production path: admission, the jobs, the replacement check with the
project's resolver, the transaction, invalidation, the routes and the certificate.

The project is built once per module and copied per test (`shutil.copytree` of the closed
project), so each test starts at the solved base revision.

M04.A47 (spec §19 A2.10, register R-325): the job's A19 manifest and evidence equal the committed
fixtures member by member outside a closed set E of environment-identity members (the
fingerprint, the request keys and their digests, and the evidence's subject hash); exact and R0
members exactly, R1/R2 floats within the numerical policy's floors (ADR 0007 D2.1, spec §18 A1.3).
E may differ only when the run's fingerprint differs from the fixture's: the fingerprint hashes
`models/c1/boundary.py`, which the M02 merge changed after the fixture was taken (build decision
E23). A member outside E that differs fails, for the design lane; it is never added to E. The
band of A26 is checked against `pipeline.smooth_prefix.band`, the registered value.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml
from m02_variant_support import register_variants
from t07_jobs_support import commit, lifecycle_violations, response_schema_violations
from test_m04_study_job import attempts, body, read, submit
from test_m04_wo7_surrogate_unit import assert_conserved

from openflowsheet.adapters import variants
from openflowsheet.adapters.experiments import runner as runner_module
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import dispatch
from openflowsheet.application.replacement import FACETS
from openflowsheet.application.types import Change, Edit, TransactionResult
from openflowsheet.canonical import document_sha256
from openflowsheet.models.c1 import COMPONENTS
from openflowsheet.run.bundle import read_artifact
from openflowsheet.studies.surrogate import reactor as sr
from openflowsheet.studies.surrogate.manifest import Q0

sys.path.insert(0, str(REPO_ROOT / "tests" / "support"))
import m04_synthetic_parents as parents  # noqa: E402

LOOP_PATH: Path = REPO_ROOT / "benchmarks" / "m02" / "c1-loop-standin.json"
REFERENCE = json.loads(
    (REPO_ROOT / "benchmarks" / "m04" / "reference_values.json").read_text(encoding="utf-8")
)
#: `pipeline.smooth_prefix.band`: (q̂ w_X, q̂ w_ΔT) of the A19 surrogate (M04.A26).
BAND = REFERENCE["pipeline"]["smooth_prefix"]["band"]
A19_FIXTURE: Mapping[str, Any] = json.loads(
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
STANDIN = variants.registered_variant("standin-x025-v1")
SMOOTH = parents.synthetic_variant(parents.SMOOTH_ID)
ROUGH = parents.synthetic_variant(parents.ROUGH_ID)
STUDIES: Mapping[str, tuple[variants.Variant, str]] = {
    "A19": (SMOOTH, "it1-prefix"),
    "A17": (SMOOTH, "it1"),
    "A18": (ROUGH, "it1-prefix"),
    "standin": (STANDIN, "it1-prefix"),
}


@dataclass(frozen=True)
class World:
    """The template project (closed): its solved base revision and its studies."""

    directory: Path
    base: str
    solve_job: str
    manifests: Mapping[str, tuple[dict[str, Any], str]]
    #: The A19 job's ModelEvidence (its second output).
    a19_evidence: Mapping[str, Any]


def reference(variant: variants.Variant) -> dict[str, Any]:
    return {"id": variant.model_id, "version": variant.variant_id, "artifact_ref": variant.sha256}


def surrogate(world: World, name: str) -> dict[str, Any]:
    manifest, sha256 = world.manifests[name]
    return {"id": sr.MODEL_ID, "version": manifest["surrogate_id"], "artifact_ref": sha256}


def loop() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(LOOP_PATH.read_text(encoding="utf-8"))
    (reactor,) = (i for i in document["instances"] if i["id"] == "reactor")
    reactor["model"] = reference(SMOOTH)
    return document


REACTOR = next(i for i, item in enumerate(loop()["instances"]) if item["id"] == "reactor")


def change(model: Mapping[str, Any]) -> Change:
    return Change(edits=(Edit("set", ("instances", REACTOR, "model"), dict(model)),))


def head(app: LocalApplication) -> str:
    with app.store.reading() as connection:
        found = app.store.head(connection)
    assert found is not None
    return found


def solve(app: LocalApplication, key: str, revision_id: str) -> dict[str, Any]:
    request = {"operation": "solve", "idempotency_key": key, "body": {"revision_id": revision_id}}
    job: dict[str, Any] = dispatch(app, "submit_job", request)["job"]
    return job


def bundle_of(app: LocalApplication, job: Mapping[str, Any]) -> Path:
    (ref,) = [output for output in job["outputs"] if output["kind"] == "replay_bundle"]
    row = app.store.artifact(ref["artifact_id"])
    assert row is not None
    return app.files_root / row.relpath


def report_of(result: TransactionResult) -> dict[str, Any]:
    """The replacement report of a rejected commit (in the error) or a committed one (stored)."""
    if result.error is not None:
        found: dict[str, Any] = result.error.detail["report"]
        return found
    raise AssertionError("committed: read the stored report with `stored_report`")


def stored_report(app: LocalApplication, revision_id: str) -> tuple[dict[str, Any], str]:
    row = app.store.artifact(f"{revision_id}:model_replacement:reactor")
    assert row is not None and row.kind == "model_replacement_report"
    document: dict[str, Any] = json.loads((app.files_root / row.relpath).read_bytes())
    return document, row.sha256


def facets(report: Mapping[str, Any]) -> dict[str, tuple[str, str]]:
    return {f["facet"]: (f["result"], f["detail"]) for f in report["facets"]}


def committed(app: LocalApplication, model: Mapping[str, Any], key: str) -> str:
    result = app.commit_change(change(model), head(app), key)
    assert result.status == "committed", result.error
    assert result.revision_id is not None
    return result.revision_id


@pytest.fixture(scope="module")
def patched() -> Iterator[None]:
    """The synthetic parents registered and evaluated, for this module only."""
    with pytest.MonkeyPatch.context() as monkeypatch:
        add = register_variants(monkeypatch)
        add(SMOOTH)
        add(ROUGH)
        monkeypatch.setattr(runner_module, "InProcessBackend", parents.backend_for())
        yield


@pytest.fixture(scope="module")
def world(patched: None, tmp_path_factory: pytest.TempPathFactory) -> World:
    directory = tmp_path_factory.mktemp("wo9") / "project"
    application = LocalApplication.create(directory)
    try:
        base = commit(application, loop())
        job = solve(application, "base", base)
        assert job["status"] == "completed", job["error"]
        manifests = {}
        evidence: dict[str, Any] = {}
        for name, (variant, plan_id) in STUDIES.items():
            study = submit(application, f"study-{name}", body(variant, plan_id=plan_id))["job"]
            assert study["status"] == "completed", study["error"]
            output = study["outputs"][0]
            assert output["kind"] == "surrogate_manifest"
            manifest = read(application, output["artifact_id"])
            assert document_sha256(manifest) == output["sha256"]
            manifests[name] = (manifest, str(output["sha256"]))
            if name == "A19":
                (record,) = [o for o in study["outputs"] if o["kind"] == "model_evidence"]
                evidence = read(application, record["artifact_id"])
    finally:
        application.close()
    return World(directory, base, str(job["job_id"]), manifests, evidence)


@pytest.fixture
def app(world: World, tmp_path: Path) -> Iterator[LocalApplication]:
    shutil.copytree(world.directory, tmp_path / "project")
    application = LocalApplication.open(tmp_path / "project")
    try:
        assert head(application) == world.base
        yield application
        assert lifecycle_violations(application) == {}
        assert response_schema_violations(application) == []
    finally:
        application.close()


# == the project ===================================================================================


def test_the_base_revision_solved_once_on_the_coupled_route(
    app: LocalApplication, world: World
) -> None:
    job = dispatch(app, "get_job", {"job_id": world.solve_job})
    assert job["status"] == "completed"
    assert read_artifact(bundle_of(app, job), "solve-path.json")["solve_path"] == "revision_coupled"
    assert len(attempts(app)) > 0


# == M04.A47 ======================================================================================

#: The numerical policy's rules (spec §18 A1.3): a float's class and floor by its path.
POLICY: Mapping[str, Any] = load_yaml(
    REPO_ROOT / "benchmarks" / "m04" / "numerical_policy_surrogate.yaml"
)["numerical_policy_surrogate"]
A19_EVIDENCE_FIXTURE: Mapping[str, Any] = json.loads(
    (
        REPO_ROOT
        / "tests"
        / "fixtures"
        / "schemas"
        / "model_evidence"
        / "valid"
        / "a19_smooth_prefix.json"
    ).read_text(encoding="utf-8")
)
#: The closed set E (spec §A2.12, M04.A47): environment-identity members. Never extended to make
#: a comparison pass; a difference outside E is a finding for the design lane.
E_MANIFEST: tuple[re.Pattern[str], ...] = (
    re.compile(r"\.parent\.fingerprint_sha256s(\[\d+\])?"),
    re.compile(r"\.splits\.\w+\.keys(\[\d+\])?"),
    re.compile(r"\.splits\.\w+\.keys_sha256"),
    re.compile(r"\.splits\.gradient\.centres\[\d+\]\.stencil_keys(\[\d+\])?"),
    re.compile(r"\.splits\.\w+\.incomplete\[\d+\]\.key"),
)
E_EVIDENCE: tuple[re.Pattern[str], ...] = (*E_MANIFEST, re.compile(r"\.subject\.artifact_ref"))
#: w_o, the scale of a floor given in units of w_o (spec §6.1).
WIDTH = {"X": 0.0025, "dT_K": 1.5}


def _leaves(node: Any, path: str = "") -> dict[str, Any]:
    if isinstance(node, dict):
        out: dict[str, Any] = {f"{path}{{}}": sorted(node)}  # the member set is compared too
        for key, value in node.items():
            out.update(_leaves(value, f"{path}.{key}"))
        return out
    if isinstance(node, list):
        out = {f"{path}[]": len(node)}
        for index, value in enumerate(node):
            out.update(_leaves(value, f"{path}[{index}]"))
        return out
    return {path: node}


def _floor(rule: Mapping[str, Any], path: str, reference: Mapping[str, Any]) -> float:
    """floor(path) in the member's own units (ADR 0007 D2.2; the policy's `floor_unit`)."""
    unit = str(rule["floor_unit"])
    output = re.search(r"\.(X|dT_K)\b", path)
    if unit.startswith("max_i |beta_o,i|"):
        assert output is not None
        coefficients = reference["predictor"]["coefficients"][output.group(1)]
        return float(rule["floor"]) * max(abs(b) for b in coefficients)
    if unit == "w_o" and output is not None:
        return float(rule["floor"]) * WIDTH[output.group(1)]
    # "1", "score", or w_o for a member already stored over w_o (`domain.admissibility_margin`).
    return float(rule["floor"])


def a47_differences(
    run: Mapping[str, Any],
    fixture: Mapping[str, Any],
    rules: Sequence[Mapping[str, Any]],
    environment: Sequence[re.Pattern[str]],
) -> tuple[list[str], list[str]]:
    """(differences outside E, members of E that differ), member by member."""
    compiled = [(re.compile(rule["path"]), rule) for rule in rules]
    ran, expected = _leaves(run), _leaves(fixture)
    outside: list[str] = []
    in_e: list[str] = []
    for path in sorted(set(ran) | set(expected)):
        if path not in ran or path not in expected:
            outside.append(f"{path}: present on one side only")
            continue
        a, b = ran[path], expected[path]
        member = path.removesuffix("[]").removesuffix("{}")
        if any(pattern.fullmatch(member) for pattern in environment):
            if a != b:
                in_e.append(member)
            continue
        if isinstance(a, float) or isinstance(b, float):
            matched = [rule for pattern, rule in compiled if pattern.fullmatch(path)]
            if not matched:
                outside.append(f"{path}: an unclassified float (ADR 0007 D2.3)")
            elif matched[0]["class"] == "r1_r2":
                floor = _floor(matched[0], path, fixture)
                if not abs(a - b) <= max(1e-9 * max(abs(a), abs(b)), floor):
                    outside.append(f"{path}: {a!r} vs {b!r} (floor {floor!r})")
            elif float(a).hex() != float(b).hex():
                outside.append(f"{path}: {a!r} vs {b!r} (exact)")
        elif a != b or type(a) is not type(b):
            outside.append(f"{path}: {a!r} vs {b!r}")
    return outside, in_e


def _fingerprints_equal(world: World) -> bool:
    manifest, _ = world.manifests["A19"]
    return bool(
        manifest["parent"]["fingerprint_sha256s"] == A19_FIXTURE["parent"]["fingerprint_sha256s"]
    )


def test_a47_the_jobs_a19_manifest_is_the_fixture_outside_the_environment(world: World) -> None:
    manifest, _ = world.manifests["A19"]
    outside, in_e = a47_differences(
        manifest, A19_FIXTURE, POLICY["rules"]["surrogate_manifest"], E_MANIFEST
    )
    assert outside == []
    if _fingerprints_equal(world):
        assert in_e == []


#: Finding E29 (build log): the evidence's `data[*].keys_sha256` are its copies of the manifest's
#: per-split key digests, which E names on the manifest side only. They are allowed here only as
#: exactly those four members and only where each equals the run manifest's own digest; the design
#: lane rules whether E names them (spec §A2.10). Any other difference fails.
E29_COPIES: tuple[str, ...] = tuple(f".data[{i}].keys_sha256" for i in range(4))


def test_a47_the_jobs_a19_evidence_is_the_fixture_outside_the_environment(world: World) -> None:
    manifest, sha256 = world.manifests["A19"]
    evidence = world.a19_evidence
    assert evidence["subject"]["artifact_ref"] == sha256
    outside, in_e = a47_differences(
        evidence, A19_EVIDENCE_FIXTURE, POLICY["rules"]["model_evidence"], E_EVIDENCE
    )
    assert [d.split(":")[0] for d in outside] in ([], list(E29_COPIES)), outside
    for block in evidence["data"]:
        assert block["keys_sha256"] == manifest["splits"][block["split"]]["keys_sha256"]
    if _fingerprints_equal(world):
        assert (outside, in_e) == ([], [])


def test_a47_the_comparison_is_not_vacuous() -> None:
    """A moved coefficient beyond its floor, a moved count and a moved E member are each caught
    where they belong."""
    rules = POLICY["rules"]["surrogate_manifest"]
    moved = json.loads(json.dumps(A19_FIXTURE))
    beta = moved["predictor"]["coefficients"]["X"]
    beta[3] += 1e-6 * max(abs(b) for b in beta)
    moved["calibration"]["k"] += 1
    moved["parent"]["fingerprint_sha256s"] = ["f" * 64]
    outside, in_e = a47_differences(moved, A19_FIXTURE, rules, E_MANIFEST)
    assert [d.split(":")[0] for d in outside] == [
        ".calibration.k",
        ".predictor.coefficients.X[3]",
    ]
    assert in_e == [".parent.fingerprint_sha256s[0]"]
    within = json.loads(json.dumps(A19_FIXTURE))
    within["predictor"]["coefficients"]["X"][3] *= 1 + 1e-12
    assert a47_differences(within, A19_FIXTURE, rules, E_MANIFEST) == ([], [])


# == M04.A25, A26 ==================================================================================


def test_a25_the_a19_surrogate_in_place_of_its_parent_is_committed(
    app: LocalApplication, world: World
) -> None:
    result = app.commit_change(change(surrogate(world, "A19")), world.base, "promote")
    assert result.status == "committed", result.error
    assert result.invalidations == (f"run-{world.solve_job}",)
    new = result.revision_id
    assert new is not None
    report, sha256 = stored_report(app, new)
    assert report["compatible"] is True
    assert {name: value[0] for name, value in facets(report).items()} == dict.fromkeys(
        FACETS, "pass"
    )
    assert facets(report)["surrogate_evidence"][1].startswith("verdict=PROMOTABLE; ")
    with app.store.reading() as connection:
        revision = app.store.get_revision(connection, new)
    assert revision is not None
    assert revision.document["provenance"]["artifact_hashes"]["model_replacement:reactor"] == sha256
    assert sha256 == document_sha256(report)


def test_a26_the_surrogate_revision_solves_on_revision_eo_with_no_experiment(
    app: LocalApplication, world: World
) -> None:
    promoted = committed(app, surrogate(world, "A19"), "promote")
    before = attempts(app)
    assert app.inspect_structure(promoted).value["solve_path"] == "revision_eo"
    job = solve(app, "surrogate", promoted)
    assert job["status"] == "completed", job["error"]
    assert attempts(app) == before  # zero experiment attempts
    bundle = bundle_of(app, job)
    assert read_artifact(bundle, "solve-path.json")["solve_path"] == "revision_eo"
    certificate = read_artifact(bundle, "solution-certificate.json")
    assert certificate["verification_status"] == "VERIFIED", certificate["limitations"]
    # The rows of §3.2 hold to the solve's registered tolerance (the certificate's residual checks).
    residual = {c["subject"]: c for c in certificate["checks"] if c["category"] == "residual"}
    for row_id in ("reactor:C1RX-extent", "reactor:C1RX-temperature"):
        assert residual[row_id]["result"] == "pass", residual[row_id]
    (check,) = (c for c in certificate["checks"] if c["id"] == "SURROGATE-DOMAIN:reactor")
    assert (check["category"], check["result"]) == ("bounds_and_domain", "pass")
    (model,) = (item for item in certificate["limitations"] if item["kind"] == "surrogate_model")
    manifest, sha256 = world.manifests["A19"]
    assert (model["unit"], model["manifest_sha256"]) == ("reactor", sha256)
    assert abs(model["band"]["X"] / float(BAND["X"]) - 1.0) <= 1e-10
    assert abs(model["band"]["dT_K"] / float(BAND["dT"]) - 1.0) <= 1e-10
    assert model["qualifications"] == manifest["qualifications"]
    assert model["qualifications"][0] == Q0 and len(model["qualifications"]) == 8
    # M04.A13 at the solution.
    state = read_artifact(bundle, "solution-state.json")["variables"]
    n_in = tuple(state[f"S3.n.{c}"] for c in COMPONENTS)
    n_out = tuple(state[f"S4.n.{c}"] for c in COMPONENTS)
    assert_conserved(n_in, n_out)


# == M04.A27, A28 ==================================================================================


def test_a27_the_rough_surrogate_is_rejected_and_preview_returns_the_same_report(
    app: LocalApplication, world: World
) -> None:
    preview = app.preview_change(change(surrogate(world, "A18")), world.base)
    result = app.commit_change(change(surrogate(world, "A18")), world.base, "rough")
    assert result.status == "rejected" and result.error is not None
    assert result.error.code == "model_replacement_incompatible"
    report = report_of(result)
    outcome, detail = facets(report)["surrogate_evidence"]
    assert outcome == "fail"
    # E15: the verdict first; the rough parent is not the smooth one, reported after it.
    assert detail.split("; ")[0] == "verdict=NOT_PROMOTABLE"
    assert detail.split("; ")[1].startswith("parent_mismatch")
    assert head(app) == world.base
    assert preview.error is not None and preview.error.detail["report"] == report
    assert head(app) == world.base  # the preview committed nothing


def test_a28_a_surrogate_of_the_standin_is_a_parent_mismatch(
    app: LocalApplication, world: World
) -> None:
    result = app.commit_change(change(surrogate(world, "standin")), world.base, "standin")
    assert result.status == "rejected" and result.error is not None
    outcome, detail = facets(report_of(result))["surrogate_evidence"]
    verdict = world.manifests["standin"][0]["promotion"]["verdict"]
    assert outcome == "fail"
    assert detail.split("; ")[:1] == [f"verdict={verdict}"]
    assert detail.split("; ")[1].startswith("parent_mismatch")
    assert head(app) == world.base


# == M04.A48 (spec §20 A3.1, register R-360) =======================================================


def _connection(end: str) -> int:
    return next(
        i for i, item in enumerate(loop()["connections"]) if item[end]["instance"] == "reactor"
    )


def rename(model: Mapping[str, Any]) -> Change:
    """The reviewer's MF1 probe: one change renames `reactor` to `reactor_b`, binds it to
    `model` and rewires S3/S4 — no instance is replaced, so no replacement judges it."""
    return Change(
        edits=(
            Edit("set", ("instances", REACTOR, "id"), "reactor_b"),
            Edit("set", ("instances", REACTOR, "model"), dict(model)),
            Edit("set", ("connections", _connection("to"), "to", "instance"), "reactor_b"),
            Edit("set", ("connections", _connection("from"), "from", "instance"), "reactor_b"),
        )
    )


def test_a48_renaming_the_reactor_onto_the_rough_surrogate_is_rejected(
    app: LocalApplication, world: World
) -> None:
    probe = rename(surrogate(world, "A18"))
    preview = app.preview_change(probe, world.base)
    result = app.commit_change(probe, world.base, "rename-rough")
    assert result.status == "rejected" and result.error is not None
    assert result.error.code == "model_replacement_incompatible"
    assert result.error.detail["reason"] == "surrogate_not_promoted(reactor_b)"
    assert result.error.detail["cause"] == "verdict=NOT_PROMOTABLE"
    assert head(app) == world.base
    assert preview.error is not None and preview.error.detail == result.error.detail
    # The same rename onto the PROMOTABLE A19 surrogate is committed.
    accepted = app.commit_change(rename(surrogate(world, "A19")), world.base, "rename-a19")
    assert accepted.status == "committed", accepted.error


# == M04.A29, A30 ==================================================================================


def test_a29_rollback_to_the_parent_and_its_coupled_solve_reuses_every_experiment(
    app: LocalApplication, world: World
) -> None:
    committed(app, surrogate(world, "A19"), "promote")
    rolled_back = committed(app, reference(SMOOTH), "rollback")
    report, _ = stored_report(app, rolled_back)
    outcome, detail = facets(report)["derivatives"]
    assert outcome == "pass" and detail.startswith("restores_parent_declaration")
    assert facets(report)["surrogate_evidence"][0] == "pass"
    before = attempts(app)
    job = solve(app, "rolled-back", rolled_back)
    assert job["status"] == "completed", job["error"]
    assert read_artifact(bundle_of(app, job), "solve-path.json")["solve_path"] == "revision_coupled"
    assert attempts(app) == before  # every experiment a cache hit


def test_a30_the_full_plan_surrogate_replaces_the_prefix_one(
    app: LocalApplication, world: World
) -> None:
    committed(app, surrogate(world, "A19"), "promote")
    replaced = committed(app, surrogate(world, "A17"), "full")
    report, _ = stored_report(app, replaced)
    outcome, detail = facets(report)["surrogate_evidence"]
    assert outcome == "pass"
    assert "the old model is a surrogate of the same parent" in detail
