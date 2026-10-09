"""M02 WO-11, gate G9: model replacement and promotion as a checked commit (design note §6.2–§6.3,
§10.1; ADR 0035; register R-228).

On a project with `C1-LOOP-M02-v1` (stand-in) solved once:

- G9 (a) as the gate states it — stand-in → `c1.reactor` @ the real variant, every facet `pass` —
  is a strict xfail: §6.2's `validity` includes the variant hard domain, and the real variant
  bounds the per-tube flow (ADR 0034 D10) where the stand-in does not, so the real domain does not
  contain the stand-in's (build log D61, escalated). Its measured outcome is asserted beside it.
  The commit's machinery is (a) in the direction §6.2 allows: a compatible promotion (to a
  test-only copy of the stand-in, and real → stand-in) is `committed`, every facet `pass`,
  `invalidations == ["run-<that job>"]`, the coarse diff names `instances` and `diff_revisions`'
  `elements` the instance's `model.*` paths, and the report is an artifact whose SHA-256 is in the
  new revision's provenance.
- G9 (b) — the plan's acceptance item "incompatible pressure boundary rejected": a test-only
  variant with `pressure_convention: "outlet_specified"` → `rejected`,
  `model_replacement_incompatible`, `boundary_condition` `fail`, the report in `error.detail`.
- G9 (c): a narrower T domain → `validity` `fail`; a renamed port → `ports` `fail`.
- G9 (d): `preview_change` returns (a)–(c)'s outcomes and commits nothing.
- G9 (e): a rollback commit to the stand-in, then a coupled solve: both experiments are cache
  hits (no new attempt).
- ADR 0035 D4: `invalidations` lists the evidence jobs of the expected revision only (an
  experiment job is never one); a change between native models is not a replacement.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT
from m02_variant_support import register_variants
from t07_jobs_support import commit, lifecycle_violations, response_schema_violations

from openflowsheet.adapters import variants
from openflowsheet.application import revision_binding
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import dispatch
from openflowsheet.application.replacement import FACETS, check_replacement, replacements
from openflowsheet.application.revision_binding import ModelSignature
from openflowsheet.application.types import Change, Edit, TransactionResult, schema_errors
from openflowsheet.canonical import document_sha256
from openflowsheet.models import Port
from openflowsheet.models.c1.reactor import PORTS
from openflowsheet.models.revision_flowsheet import RevisionError

LOOP_PATH = REPO_ROOT / "benchmarks" / "m02" / "c1-loop-standin.json"
STANDIN = variants.registered_variant("standin-x025-v1")
REAL = variants.registered_variant("pymrm-6089593-g2-nz800-s123-v2")
REPORT = "model-replacement.schema.json"


def loop() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(LOOP_PATH.read_text(encoding="utf-8"))
    return document


REACTOR = next(i for i, item in enumerate(loop()["instances"]) if item["id"] == "reactor")


def reference(variant: variants.Variant) -> dict[str, Any]:
    return {"id": variant.model_id, "version": variant.variant_id, "artifact_ref": variant.sha256}


def standin_like(variant_id: str, **boundary: Any) -> variants.Variant:
    """A test-only copy of the stand-in variant, its boundary members replaced as given."""
    document = {
        **STANDIN.document,
        "variant_id": variant_id,
        "boundary": {**STANDIN.document["boundary"], **boundary},
    }
    return variants.variant_from_document(document)


def change(model: Mapping[str, Any]) -> Change:
    return Change(edits=(Edit("set", ("instances", REACTOR, "model"), dict(model)),))


def head(app: LocalApplication) -> str:
    with app.store.reading() as connection:
        found = app.store.head(connection)
    assert found is not None
    return found


def facets(result: TransactionResult) -> dict[str, str]:
    assert result.error is not None
    return {facet["facet"]: facet["result"] for facet in result.error.detail["report"]["facets"]}


def solve(app: LocalApplication, key: str, revision_id: str) -> dict[str, Any]:
    request = {"operation": "solve", "idempotency_key": key, "body": {"revision_id": revision_id}}
    job: dict[str, Any] = dispatch(app, "submit_job", request)["job"]
    return job


@pytest.fixture
def app(tmp_path: Path) -> Iterator[LocalApplication]:
    application = LocalApplication.create(tmp_path / "project")
    try:
        yield application
        assert lifecycle_violations(application) == {}
        assert response_schema_violations(application) == []
    finally:
        application.close()


@pytest.fixture
def solved(app: LocalApplication) -> tuple[LocalApplication, str, dict[str, Any]]:
    """The project of G9: `C1-LOOP-M02-v1` with the stand-in, solved once."""
    revision_id = commit(app, loop())
    job = solve(app, "first", revision_id)
    assert job["status"] == "completed"
    return app, revision_id, job


@pytest.fixture
def register(monkeypatch: pytest.MonkeyPatch) -> Any:
    return register_variants(monkeypatch)


def valid(result: TransactionResult) -> None:
    assert schema_errors("transaction-result.schema.json", result.as_document()) == []
    if result.error is not None and "report" in result.error.detail:
        assert schema_errors(REPORT, result.error.detail["report"]) == []


def test_the_report_facets_are_the_schemas_in_its_order() -> None:
    """§6.2's nine facets; a later package's facet is added to both (M04's on its branch)."""
    schema = json.loads((REPO_ROOT / "schemas" / REPORT).read_text(encoding="utf-8"))
    facet = schema["properties"]["facets"]["items"]["properties"]["facet"]
    assert list(FACETS) == facet["enum"]


# == G9 (a) ======================================================================================


@pytest.mark.xfail(
    strict=True,
    reason=(
        "G9 (a) vs §6.2 (escalated, build log D61): the real variant's hard domain bounds the "
        "per-tube flow to [0.5, 2] F_nom (ADR 0034 D10), the stand-in's does not, so `validity` "
        "(the new domain contains the old) fails"
    ),
)
def test_g9a_standin_to_the_real_reactor_commits_with_every_facet_passing(
    solved: tuple[LocalApplication, str, dict[str, Any]],
) -> None:
    app, revision_id, _ = solved
    result = app.commit_change(change(reference(REAL)), revision_id, "promote")
    assert result.status == "committed"


def test_g9a_standin_to_the_real_reactor_as_section_6_2_judges_it(
    solved: tuple[LocalApplication, str, dict[str, Any]],
) -> None:
    """The measured outcome the escalation cites: every facet but `validity` passes."""
    app, revision_id, _ = solved
    result = app.commit_change(change(reference(REAL)), revision_id, "promote")
    valid(result)
    assert result.status == "rejected" and result.error is not None
    assert result.error.code == "model_replacement_incompatible"
    assert facets(result) == {facet: "pass" for facet in FACETS} | {"validity": "fail"}
    (validity,) = [f for f in result.error.detail["report"]["facets"] if f["facet"] == "validity"]
    assert "hard_domain.tube_flow_mol_s None" in validity["detail"]
    report = result.error.detail["report"]
    assert report["from"]["synthetic"] is True and report["to"]["synthetic"] is False
    assert head(app) == revision_id


def test_g9a_a_compatible_promotion_commits_with_its_report(
    solved: tuple[LocalApplication, str, dict[str, Any]], register: Any
) -> None:
    app, revision_id, job = solved
    copy = register(standin_like("test-standin-copy-v1"))
    result = app.commit_change(change(reference(copy)), revision_id, "promote")
    valid(result)
    assert result.status == "committed", result.error
    assert result.invalidations == (f"run-{job['job_id']}",)
    assert result.diff is not None and "instances" in result.diff.changed
    new = result.revision_id
    assert new is not None
    elements = app.diff_revisions(revision_id, new).elements
    (element,) = [e for e in elements if e.member == "instances" and e.id == "reactor"]
    assert element.change == "changed"
    assert set(element.paths) == {("model", "artifact_ref"), ("model", "version")}
    row = app.store.artifact(f"{new}:model_replacement:reactor")
    assert row is not None
    assert (row.kind, row.job_id) == ("model_replacement_report", None)
    stored = json.loads((app.files_root / row.relpath).read_bytes())
    assert schema_errors(REPORT, stored) == []
    assert stored["compatible"] is True
    assert [facet["result"] for facet in stored["facets"]] == ["pass"] * len(FACETS)
    assert [facet["facet"] for facet in stored["facets"]] == list(FACETS)
    with app.store.reading() as connection:
        revision = app.store.get_revision(connection, new)
    assert revision is not None
    provenance = revision.document["provenance"]
    assert provenance["artifact_hashes"]["model_replacement:reactor"] == row.sha256
    assert row.sha256 == document_sha256(stored)


def test_g9a_real_to_standin_is_allowed_and_reports_synthetic(app: LocalApplication) -> None:
    """§6.2: `synthetic` is reported, not judged; real → stand-in changes the model id too."""
    document = loop()
    document["instances"][REACTOR]["model"] = reference(REAL)
    revision_id = commit(app, document)
    result = app.commit_change(change(reference(STANDIN)), revision_id, "demote")
    valid(result)
    assert result.status == "committed", result.error
    new = result.revision_id
    assert new is not None
    (element,) = [e for e in app.diff_revisions(revision_id, new).elements if e.id == "reactor"]
    assert set(element.paths) == {("model", "artifact_ref"), ("model", "id"), ("model", "version")}
    row = app.store.artifact(f"{new}:model_replacement:reactor")
    assert row is not None
    stored = json.loads((app.files_root / row.relpath).read_bytes())
    assert (stored["from"]["synthetic"], stored["to"]["synthetic"]) == (False, True)
    assert stored["compatible"] is True


# == G9 (b), (c) =================================================================================


def test_g9b_an_incompatible_pressure_convention_is_rejected(
    solved: tuple[LocalApplication, str, dict[str, Any]], register: Any
) -> None:
    """The plan's acceptance item: "incompatible pressure boundary rejected"."""
    app, revision_id, _ = solved
    outlet = register(
        standin_like("test-standin-outlet-p-v1", pressure_convention="outlet_specified")
    )
    result = app.commit_change(change(reference(outlet)), revision_id, "outlet")
    valid(result)
    assert result.status == "rejected" and result.error is not None
    assert result.error.code == "model_replacement_incompatible"
    assert facets(result) == {facet: "pass" for facet in FACETS} | {"boundary_condition": "fail"}
    report = result.error.detail["report"]
    assert report["compatible"] is False and report["instance_id"] == "reactor"
    (boundary,) = [f for f in report["facets"] if f["facet"] == "boundary_condition"]
    assert "pressure_convention" in boundary["detail"]
    assert head(app) == revision_id


def test_g9c_a_narrower_temperature_domain_fails_validity(
    solved: tuple[LocalApplication, str, dict[str, Any]], register: Any
) -> None:
    app, revision_id, _ = solved
    hard = {**STANDIN.document["boundary"]["hard_domain"], "T_K": [600.0, 750.0]}
    narrow = register(standin_like("test-standin-narrow-t-v1", hard_domain=hard))
    result = app.commit_change(change(reference(narrow)), revision_id, "narrow")
    valid(result)
    assert result.status == "rejected"
    assert facets(result) == {facet: "pass" for facet in FACETS} | {"validity": "fail"}


def test_g9c_a_renamed_port_fails_ports(
    solved: tuple[LocalApplication, str, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A test-only model with the reactor's ports, its inlet renamed `feed`."""
    app, revision_id, _ = solved
    model_id = "test.reactor_renamed_port"
    ports = tuple(
        Port(**{**port.__dict__, "name": "feed"}) if port.name == "inlet" else port
        for port in PORTS
    )
    signature = ModelSignature(model_id=model_id, ports=ports, required=("n_tubes",))

    def builder(view: Any, *_: Any) -> Any:
        # A unit whose inlet is `feed` finds no stream on it: the binder's refusal.
        raise RevisionError("unsupported", f"port_unconnected({view.unit_id}.feed)")

    monkeypatch.setitem(revision_binding.MODEL_SIGNATURES, model_id, signature)  # type: ignore[index]
    monkeypatch.setitem(revision_binding.MODEL_BUILDERS, model_id, builder)  # type: ignore[index]
    monkeypatch.setitem(revision_binding.MODEL_BASES, model_id, frozenset({"pr-c1-v1"}))  # type: ignore[index]
    result = app.commit_change(
        change({"id": model_id, "version": "0.0.0-declared", "artifact_ref": None}),
        revision_id,
        "renamed",
    )
    valid(result)
    assert result.status == "rejected"
    outcome = facets(result)
    assert outcome["ports"] == "fail"
    assert outcome["degrees_of_freedom"] == "fail"  # the new revision does not bind
    (ports_facet,) = [f for f in result.error.detail["report"]["facets"] if f["facet"] == "ports"]  # type: ignore[union-attr]
    assert "feed" in ports_facet["detail"]


# == G9 (d) ======================================================================================


def test_g9d_preview_returns_each_outcome_and_commits_nothing(
    solved: tuple[LocalApplication, str, dict[str, Any]], register: Any
) -> None:
    app, revision_id, _ = solved
    copy = register(standin_like("test-standin-copy-v1"))
    outlet = register(
        standin_like("test-standin-outlet-p-v1", pressure_convention="outlet_specified")
    )
    hard = {**STANDIN.document["boundary"]["hard_domain"], "T_K": [600.0, 750.0]}
    narrow = register(standin_like("test-standin-narrow-t-v1", hard_domain=hard))
    with app.store.reading() as connection:
        before = app.store.revision_count(connection)
    previewed = app.preview_change(change(reference(copy)), revision_id)
    valid(previewed)
    assert previewed.status == "previewed" and previewed.error is None
    for variant, failing in (
        (outlet, "boundary_condition"),
        (narrow, "validity"),
        (REAL, "validity"),
    ):
        preview = app.preview_change(change(reference(variant)), revision_id)
        valid(preview)
        assert preview.status == "rejected"
        assert preview.error is not None and preview.error.code == "model_replacement_incompatible"
        assert facets(preview)[failing] == "fail"
        committed = app.commit_change(change(reference(variant)), revision_id, variant.variant_id)
        assert committed.error is not None
        assert committed.error.detail["report"] == preview.error.detail["report"]
    with app.store.reading() as connection:
        assert app.store.revision_count(connection) == before
    assert head(app) == revision_id
    assert app.store.artifact(f"{revision_id}:model_replacement:reactor") is None


# == G9 (e) ======================================================================================


def test_g9e_a_rollback_to_the_standin_reuses_its_experiments(
    solved: tuple[LocalApplication, str, dict[str, Any]], register: Any
) -> None:
    app, revision_id, first = solved
    copy = register(standin_like("test-standin-copy-v1"))
    promoted = app.commit_change(change(reference(copy)), revision_id, "promote")
    assert promoted.status == "committed" and promoted.revision_id is not None
    rolled = app.commit_change(change(reference(STANDIN)), promoted.revision_id, "rollback")
    valid(rolled)
    assert rolled.status == "committed" and rolled.revision_id is not None
    assert rolled.invalidations == ()  # nothing ran on the promoted revision
    job = solve(app, "after-rollback", rolled.revision_id)
    assert job["status"] == "completed"
    kinds = [output["kind"] for output in job["outputs"]]
    assert kinds[:2] == ["experiment_result", "experiment_result"]  # two cache hits' rows
    assert "experiment_attempt" not in kinds and "experiment_request" not in kinds
    first_records = [o["sha256"] for o in first["outputs"] if o["kind"] == "experiment_result"]
    assert [o["sha256"] for o in job["outputs"][:2]] == first_records


# == ADR 0035 D4 =================================================================================


def test_invalidations_list_evidence_jobs_and_never_experiments(
    solved: tuple[LocalApplication, str, dict[str, Any]], register: Any
) -> None:
    app, revision_id, first = solved
    second = solve(app, "second", revision_id)
    body = {
        "model": reference(STANDIN),
        "inlet": {
            "components": ["H2", "N2", "NH3", "Ar", "CH4"],
            "n": [2.79, 0.93, 0.11, 0.1, 0.15],
            "T": 673.15,
            "P": 1.0e7,
        },
        "n_tubes": 1000.0,
    }
    experiment = dispatch(
        app, "submit_job", {"operation": "experiment", "idempotency_key": "x", "body": body}
    )["job"]
    assert experiment["status"] == "completed"
    copy = register(standin_like("test-standin-copy-v1"))
    result = app.commit_change(change(reference(copy)), revision_id, "promote")
    assert result.invalidations == (f"run-{first['job_id']}", f"run-{second['job_id']}")


def test_a_change_between_native_models_is_not_a_replacement() -> None:
    before = loop()
    after = loop()
    mixer = next(i for i, item in enumerate(after["instances"]) if item["id"] == "mixer")
    after["instances"][mixer]["model"]["version"] = "0.0.1-declared"
    assert replacements(before, after) == ()
    after["instances"][REACTOR]["model"] = reference(REAL)
    assert replacements(before, after) == ("reactor",)


@pytest.mark.parametrize("value", [["c1.reactor"], {"id": 1}, 3.5, None, True])
def test_the_check_is_total_over_malformed_references(value: Any) -> None:
    """A draft may hold any JSON value in a model reference (T07 S3.6's fuzz found the gap): the
    check judges it, it never raises."""
    after = loop()
    for key in ("id", "version", "artifact_ref"):
        after["instances"][REACTOR]["model"] = {**reference(STANDIN), key: value}
        found = replacements(loop(), after)
        if found:
            report = check_replacement(loop(), after, "reactor")
            assert not report.compatible
            assert schema_errors(REPORT, report.as_document()) == []
