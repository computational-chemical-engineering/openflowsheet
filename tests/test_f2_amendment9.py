"""F2-WO6b: v2 documents through the application (ADR 0062 D8, D12; ADR 0019 Amendment 9).

- **E-F2-3, run half.** Every revision of F0's run set (`scripts/corpus_identity.py`
  `run_corpus`: its 47 `g8` revisions and the 9 basis cases; the 5 `k05` runs are SYN-001 variants
  the CLI solves by name, not revision documents), raised to v2 and submitted as a run as F0
  submits it (`select_route`, `run_revision_session`), writes the bundle of its v1 run: the same
  artifact index (every artifact's SHA-256, `revision.json` and `solution-state.json` included),
  `artifact_r0_sha256` equal to the run's and to F0's registered M3, and the same state hashes.
  The three M1 revisions outside the run set route as their v1 documents do (no route, the same
  refusal).
- **The dispatch map** (`docs/F2_DECISIONS.md`, "WO6b dispatch map"): one test per row.
"""

from __future__ import annotations

import copy
import json
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from f2.legacy_providers import legacy_providers as test_providers

from openflowsheet.models.revision_flowsheet import (
    RevisionError,
    legacy_providers,
    lowered_document,
    parse_revision,
    pin_specifications,
)
from openflowsheet.revision_v2.raise_v1 import raise_v1

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import corpus_identity as gate  # noqa: E402
from t07_corpus import CORPUS  # noqa: E402

#: A SYN-001 revision of the corpus: three components, seven `nTP-v1` connections.
BASE = "SYN-001-T06-NET02"
#: F0's registered measures (`benchmarks/f0/corpus.json`).
REGISTRY = json.loads(gate.REGISTRY.read_text(encoding="utf-8"))["measures"]
#: The run set's revisions (`g8` and the basis cases), by `<set>/<name>`.
RUNS = [(run_set, name) for run_set, name in gate.run_corpus() if run_set != "k05"]


def _raised(document: dict[str, Any]) -> dict[str, Any]:
    return raise_v1(document, legacy_providers())


_SOLVED: dict[tuple[str, str], tuple[Path, Path]] = {}


@pytest.fixture(scope="module", autouse=True)
def _scratch(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Where `_bundles` writes, for this module only."""
    _SOLVED.clear()
    _SOLVED[("", "")] = (tmp_path_factory.mktemp("f2-wo6b"), Path())
    yield
    _SOLVED.clear()


def _bundles(run_set: str, name: str) -> tuple[Path, Path]:
    """The v1 run and the raised v2 document's run of one revision, solved as F0 solves it."""
    if (run_set, name) in _SOLVED:
        return _SOLVED[(run_set, name)]
    scratch = _SOLVED[("", "")][0] / f"{run_set}-{name}"
    original = gate.revision_document(run_set, name)
    raised = _raised(copy.deepcopy(original))
    assert raised["schema_version"] == 2
    with gate.pinned_threads():
        gate.solve(run_set, name, scratch / "v1", original)
        gate.solve(run_set, name, scratch / "v2", raised)
    _SOLVED[(run_set, name)] = (scratch / "v1", scratch / "v2")
    return _SOLVED[(run_set, name)]


def test_e_f2_3_run_set_is_47_g8_and_9_basis_cases() -> None:
    """56 runs: F0's run set without the 5 `k05` cases, which are not revision documents."""
    assert sum(run_set == "g8" for run_set, _ in RUNS) == 47
    assert len(RUNS) == 56


@pytest.mark.parametrize(("run_set", "name"), RUNS, ids=[f"{s}/{n}" for s, n in RUNS])
def test_e_f2_3_raised_run_writes_the_v1_bundle(run_set: str, name: str) -> None:
    """E-F2-3 (run half): the v2 run's manifest identity and artifact index equal the v1 run's,
    its `artifact_r0_sha256` is F0's registered M3, and `solution-state.json` is the same bytes."""
    v1, v2 = (gate.artifacts(directory) for directory in _bundles(run_set, name))
    (manifest1, documents1), (manifest2, documents2) = v1, v2
    for field in (
        "run_id",
        "model_version",
        "constants_sha256",
        "policy_id",
        "plan_id",
        "check_policy_sha256",
        "policy_sha256",
        "artifact_r0_sha256",
        "numerical_policy_id",
        "artifacts",
        "outcome",
        "verification_status",
        "reproducibility_class",
    ):
        assert getattr(manifest2, field) == getattr(manifest1, field), field
    key = f"{run_set}/{name}"
    assert manifest2.artifact_r0_sha256 == REGISTRY["M3"][key]["artifact_r0_sha256"]
    assert list(gate.state_hashes(documents2)) == list(gate.state_hashes(documents1))
    state = "solution-state.json"
    if state in documents1:
        directory1, directory2 = _bundles(run_set, name)
        assert (directory2 / "artifacts" / state).read_bytes() == (
            directory1 / "artifacts" / state
        ).read_bytes()
        assert documents2[state]["schema_version"] == "solution-state-v1"


def test_e_f2_3_m1_revisions_outside_the_run_set_route_as_v1() -> None:
    """The M1 revisions with no registered run: the raised document routes as the v1 one."""
    from openflowsheet.application.revision_run import NoRoute, Route, select_route  # noqa: PLC0415

    outside = sorted(set(CORPUS) - {name for _, name in RUNS})
    assert len(outside) == 3
    for name in outside:
        original = CORPUS[name]()
        v1, v2 = select_route(original), select_route(_raised(original))
        assert type(v1) is type(v2), name
        if isinstance(v1, NoRoute):
            assert isinstance(v2, NoRoute)
            assert (v2.reason, v2.hint) == (v1.reason, v1.hint), name
        else:
            assert isinstance(v1, Route) and isinstance(v2, Route)
            assert (v2.solve_path, v2.reason) == (v1.solve_path, v1.reason), name


# -- the dispatch map ---------------------------------------------------------------------------


def _base() -> dict[str, Any]:
    return CORPUS[BASE]()


def _energy(document: dict[str, Any]) -> dict[str, Any]:
    """`document` with its first connection made an energy connection: not v1-expressible."""
    changed = copy.deepcopy(document)
    connection = changed["connections"][0]
    connection["kind"] = "energy"
    connection["definition"] = "heat-v1"
    connection.pop("phase_capability", None)
    return changed


def test_row_14_legacy_providers_equal_the_test_builder() -> None:
    """Row 14 (F2 decisions WO6a-1, WO6b-1): the production selection is the test-only one,
    built independently from `component_basis` and the providers' modules."""
    assert legacy_providers() == test_providers()


def test_row_1_parse_revision_reads_v2_as_its_lowering() -> None:
    """Row 1: `parse_revision` dispatches on `schema_version`; a v1 document is read as given."""
    original = _base()
    raised = _raised(original)
    assert parse_revision(raised) == parse_revision(original)
    assert pin_specifications(raised) == pin_specifications(original)
    assert lowered_document(original) is original


def test_row_1_a_v2_document_is_never_read_as_v1() -> None:
    """ADR 0002 D7.5: a v2 document the v2 schema refuses is `schema_invalid`, not a v1 reading."""
    raised = _raised(_base())
    del raised["convention"]
    with pytest.raises(RevisionError) as caught:
        parse_revision(raised)
    assert (caught.value.kind, caught.value.code) == ("unsupported", "schema_invalid()")


def test_row_1_a_non_expressible_document_is_refused_typed() -> None:
    """Row 1: a v2 document `lower` refuses raises the first `construct_unavailable`."""
    raised = _energy(_raised(_base()))
    with pytest.raises(RevisionError) as caught:
        parse_revision(raised)
    assert caught.value.kind == "unsupported"
    assert caught.value.code.startswith("construct_unavailable(")


@pytest.mark.parametrize(
    "bind",
    [
        "openflowsheet.application.revision_binding:bind_revision_flowsheet",
        "openflowsheet.application.binding:bind_revision_or_reason",
    ],
)
def test_rows_2_3_binders_bind_the_lowered_document(bind: str) -> None:
    """Rows 2 and 3: each binder binds a v2 document as its lowering, digest included."""
    module, name = bind.split(":")
    binder: Callable[[dict[str, Any]], Any] = getattr(__import__(module, fromlist=[name]), name)
    original = _base()
    v1, v2 = binder(copy.deepcopy(original)), binder(_raised(original))
    assert type(v1) is type(v2)
    if hasattr(v1, "revision_sha256"):
        assert v2.revision_sha256 == v1.revision_sha256
    else:
        assert (v2.kind, v2.detail) == (v1.kind, v1.detail)


def test_rows_2_3_a_non_expressible_document_is_unbound() -> None:
    from openflowsheet.application.binding import bind_revision_or_reason  # noqa: PLC0415
    from openflowsheet.application.revision_binding import (  # noqa: PLC0415
        bind_revision_flowsheet,
    )

    raised = _energy(_raised(_base()))
    for refused in (bind_revision_flowsheet(raised), bind_revision_or_reason(raised)):
        assert refused.kind == "unsupported"
        assert refused.detail.startswith("construct_unavailable(")


def test_rows_4_5_6_readers_of_a_bundle_read_the_lowered_document() -> None:
    """Rows 4 to 6: the stream table, the verifier and the NLP boundary read a v2 revision as its
    lowering. The verifier and the stream table are driven through a v2 run's bundle; the NLP
    boundary's target reads it as the binder did."""
    from openflowsheet.application.revision_binding import (  # noqa: PLC0415
        bind_revision_flowsheet,
    )
    from openflowsheet.application.stream_table import _inputs  # noqa: PLC0415
    from openflowsheet.studies.nlp.boundary import certificate_target  # noqa: PLC0415
    from openflowsheet.thermo import syn001  # noqa: PLC0415

    _, directory = _bundles("g8", BASE)
    _, documents = gate.artifacts(directory)
    raised = _raised(_base())
    state = documents["solution-state.json"]
    certificate = documents["solution-certificate.json"]
    provider = syn001.Syn001Provider()
    v2 = _inputs(raised, state, certificate, provider, "revision_eo")
    v1 = _inputs(_base(), state, certificate, provider, "revision_eo")
    assert v2 == v1
    binding = bind_revision_flowsheet(raised)
    values = dict(state["variables"])
    target2 = certificate_target(binding, raised, values)
    target1 = certificate_target(binding, _base(), values)
    assert (target2.row_ids, target2.column_ids) == (target1.row_ids, target1.column_ids)


def test_row_11_content_hash_of_a_v2_document_is_revision_v2s() -> None:
    from openflowsheet.application.revisions import Revision, content_hash  # noqa: PLC0415
    from openflowsheet.revision_v2 import content_hash as v2_content_hash  # noqa: PLC0415

    original = _base()
    raised = _raised(original)
    assert content_hash(raised) == v2_content_hash(raised)
    assert content_hash(raised) != content_hash(original)
    assert Revision(raised["revision_id"], raised).content_hash == v2_content_hash(raised)


def test_row_12_the_bundle_holds_the_lowered_revision() -> None:
    """Row 12 (D8): `revision.json` of a v2 run is the lowered v1 document."""
    _, directory = _bundles("g8", BASE)
    _, documents = gate.artifacts(directory)
    assert documents["revision.json"]["schema_version"] == 1


def test_row_13_verify_bundle_judges_a_v2_state_by_its_own_rules() -> None:
    """Row 13: `verify_bundle` dispatches on the solution state's version: a v2 run's bundle (v1
    state) verifies, and a `solution-state-v2` is judged by `inconsistencies_v2`."""
    from openflowsheet.run import bundle  # noqa: PLC0415
    from openflowsheet.run import solution_state as states  # noqa: PLC0415

    _, directory = _bundles("g8", BASE)
    assert bundle.verify_bundle(directory).ok
    seen: list[str] = []

    def spy(name: str) -> Callable[..., tuple[str, ...]]:
        def judged(state: Any, certificate: Any) -> tuple[str, ...]:
            seen.append(name)
            return ()

        return judged

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(states, "inconsistencies", spy("v1"))
        patch.setattr(states, "inconsistencies_v2", spy("v2"))
        document = json.loads((directory / "artifacts" / "solution-state.json").read_bytes())
        for version, expected in (("solution-state-v1", "v1"), ("solution-state-v2", "v2")):
            document["schema_version"] = version
            patch.setattr(bundle, "read_artifact", lambda _d, _n, doc=document: doc)
            bundle._cross_check_solution_state(
                directory, {states.NAME: ""}, missing=[], tampered=[]
            )
            assert seen[-1] == expected


# -- rows 7 to 10: validation, admission and the revision operations (Amendment 9) ---------------


def _now() -> str:
    return "2026-11-27T00:00:00Z"


@pytest.mark.parametrize("name", sorted(CORPUS))
def test_row_7_validate_reports_a_raised_revision_as_its_v1_document(name: str) -> None:
    """Row 7: `validate` reads a v2 document with the v2 schema and F2's rules, then reports its
    lowering's report: equal to the v1 document's for 49 of M1's 50. `SYN-001-T06-STR06` names a
    component outside the set in a specification, which v1 reports at COMP-03 and the v2 rules
    refuse at SCHEMA-01 (`component_unknown(D)`); both `INVALID`."""
    from openflowsheet.application.validation import validate  # noqa: PLC0415

    original = CORPUS[name]()
    v1 = validate(original, now=_now).as_document()
    v2 = validate(_raised(original), now=_now).as_document()
    if name == "SYN-001-T06-STR06":
        assert (v1["status"], v2["status"]) == ("INVALID", "INVALID")
        assert [c["message"] for c in v2["checks"]] == ["component_unknown(D)"]
    else:
        assert v2 == v1


def test_row_7_validate_refuses_by_the_v2_schema_and_by_lowering() -> None:
    from openflowsheet.application.validation import validate  # noqa: PLC0415

    raised = _raised(_base())
    del raised["convention"]
    (check,) = validate(raised, now=_now).checks
    assert (check.id, check.result) == ("SCHEMA-01", "FAIL")
    assert check.message.startswith("schema_invalid()")
    (check,) = validate(_energy(_raised(_base())), now=_now).checks
    assert (check.id, check.result) == ("SCHEMA-01", "FAIL")
    assert "construct_unavailable(" in check.message


def test_rows_8_9_check_admission_admits_a_v2_draft_as_its_lowering() -> None:
    """Rows 8 and 9: the draft form reads a v2 revision; its pairs are the v1 draft's."""
    from openflowsheet.application.local import LocalApplication  # noqa: PLC0415

    with LocalApplication.in_memory() as app:
        v1 = app.check_admission(revision=_base()).as_document()
        v2 = app.check_admission(revision=_raised(_base())).as_document()
    assert v2 == v1


def test_rows_8_9_check_admission_refuses_a_non_expressible_v2_draft() -> None:
    from openflowsheet.application.errors import ApplicationError  # noqa: PLC0415
    from openflowsheet.application.local import LocalApplication  # noqa: PLC0415

    with LocalApplication.in_memory() as app, pytest.raises(ApplicationError) as caught:
        app.check_admission(revision=_energy(_raised(_base())))
    error = caught.value.error
    assert error.code == "revision_unsupported"
    # The energy connection on a material port: the validator's refusal first (sorted), and the
    # lowering's `construct_unavailable` beside it.
    assert error.detail["unbound"] == "unsupported(connection_kind_unsupported(S1, U-FEED.outlet))"
    assert "construct_unavailable(energy:S1, F6)" in error.detail["hint"]


def test_rows_10_11_12_commit_preview_diff_and_run_a_v2_revision() -> None:
    """Row 10: `preview_change` and `commit_change` accept a v2 document (its `ChangeSet` paths
    address v2 fields), `diff_revisions` diffs two v2 revisions; row 11: the stored hash is v2's;
    row 12: `solve` runs it and the run result references the v2 revision."""
    from openflowsheet.application.local import LocalApplication  # noqa: PLC0415
    from openflowsheet.application.transaction_types import Change, Edit  # noqa: PLC0415
    from openflowsheet.revision_v2 import content_hash  # noqa: PLC0415

    raised = _raised(_base())
    body = {k: v for k, v in raised.items() if k not in ("revision_id", "parent_revision")}
    with LocalApplication.in_memory() as app:
        change = Change(edits=tuple(Edit("set", (key,), value) for key, value in body.items()))
        preview = app.preview_change(change, None)
        assert preview.status == "previewed", preview
        committed = app.commit_change(change, None, "f2-wo6b-1")
        assert committed.status == "committed", committed
        first = committed.revision_id
        assert first is not None
        assert committed.validation is not None
        assert committed.validation.status == "READY_FOR_SIMULATION"
        stored = app.get_revision(first).as_document()
        assert stored["value"]["content_hash"] == content_hash({**raised, "revision_id": first})
        edit = Change(edits=(Edit("set", ("specifications", 0, "value"), 2.0),))
        second = app.commit_change(edit, first, "f2-wo6b-2")
        assert second.status == "committed", second
        assert second.revision_id is not None
        diff = app.diff_revisions(first, second.revision_id).as_document()
        assert diff != app.diff_revisions(first, first).as_document()
        result = app.solve(first, "default")
        assert result.revision_id == first
        assert result.revision_content_sha256 == stored["value"]["content_hash"]
        assert result.outcome == "CONVERGED", result
    original = {k: v for k, v in _base().items() if k not in ("revision_id", "parent_revision")}
    with LocalApplication.in_memory() as app:
        change = Change(edits=tuple(Edit("set", (key,), value) for key, value in original.items()))
        committed = app.commit_change(change, None, "f2-wo6b-v1")
        assert committed.revision_id == first
        v1 = app.solve(first, "default")
    # The job's run is the v1 run: the same structural identity (D8).
    assert (result.structural_sha256, result.solve_path) == (v1.structural_sha256, v1.solve_path)


@pytest.mark.nlp
def test_the_optimization_of_a_raised_revision_is_the_optimization_of_its_v1_document(
    tmp_path: Path,
) -> None:
    """OPT-A2's revision raised to v2 optimizes to the v1 document's optimum (the report's status,
    decisions and objective), and, by D8, with the v1 run's identity: the same run ids and the
    same `revision.json` in every start's bundles."""
    from openflowsheet.application.revision_routes import REVISION_ROUTES
    from openflowsheet.orchestrator.policies import DEFAULT_POLICY_ID, resolve_policy
    from openflowsheet.studies.nlp.revision import optimize_revision
    from openflowsheet.verify.verdict import CheckPolicy

    opt = ROOT / "benchmarks" / "opt"
    flowsheet = json.loads((opt / "expected.json").read_bytes())["flowsheets"]["OPT-A2"]
    document = json.loads((opt / "flowsheets" / f"{flowsheet}.json").read_bytes())
    request = json.loads((opt / "requests" / "OPT-A2.json").read_bytes())
    policy = resolve_policy(DEFAULT_POLICY_ID, "revision_eo")
    assert policy is not None
    raised = _raised(copy.deepcopy(document))
    assert raised["schema_version"] == 2

    def optimum(name: str, revision: dict[str, Any]) -> tuple[dict[str, Any], dict[str, bytes]]:
        outcome = optimize_revision(
            revision,
            request,
            directory=tmp_path / name,
            solve_policy=policy,
            check_policy=CheckPolicy(),
            routes=REVISION_ROUTES,
        )
        assert outcome.record_dir is not None
        assert outcome.report.status == "KKT_POINT_VERIFIED"
        record = outcome.record_dir
        bundles = {
            path.relative_to(record).as_posix(): path.read_bytes()
            for path in sorted(record.rglob("revision.json"))
        }
        manifests = {
            path.parent.relative_to(record).as_posix(): json.loads(path.read_bytes())["run_id"]
            for path in sorted(record.rglob("run-manifest.json"))
        }
        report = outcome.report.as_document()
        found = {"candidate": report["candidate"]["decisions"], "run_ids": manifests}
        return found, bundles

    (found1, files1), (found2, files2) = optimum("v1", document), optimum("v2", raised)
    assert found2["candidate"] == found1["candidate"]
    assert found2["run_ids"] == found1["run_ids"]
    assert files2 == files1


def _lineage_bundles(root: Path, raised: bool) -> tuple[bytes, bytes, str]:
    """RRC's N1 lineage in a store (`tests/test_rrc_application.py`): NET-02 at split 0.5 solved
    under `default`, then its child at 0.95 under `RRC-revision-v1`, which continues from the
    ancestor; committed as the v1 documents or as their raised forms. The ancestor's and the
    child's `solve-path.json` bytes and the child's `artifact_r0_sha256`."""
    from t07_jobs_support import commit  # noqa: PLC0415

    from openflowsheet.application.job_requests import JobRequest, SolveBody  # noqa: PLC0415
    from openflowsheet.application.local import LocalApplication  # noqa: PLC0415
    from openflowsheet.run.bundle import MANIFEST_NAME  # noqa: PLC0415

    def document(split: float) -> dict[str, Any]:
        found = _base()
        unit = next(i for i in found["instances"] if i["id"] == "U-SPLIT")
        unit["parameters"]["split_fraction"]["value"] = split
        if raised:
            found = _raised(found)
        for key in ("revision_id", "parent_revision"):
            found.pop(key, None)
        return found

    with LocalApplication.create(root / "lineage", project_id="f2-wo8-lineage") as app:
        directories = []
        for count, (split, policy_id) in enumerate(((0.5, "default"), (0.95, "RRC-revision-v1"))):
            revision_id = commit(app, document(split))
            request = JobRequest("solve", f"f2-wo8-{count}", SolveBody(revision_id, policy_id))
            job = app.submit_job(request).job
            assert job.status == "completed", (job.status, job.error)
            directories.append(app.files_root / "jobs" / job.job_id / "bundle")
        ancestor, child = directories
        manifest = json.loads((child / MANIFEST_NAME).read_bytes())
        return (
            (ancestor / "artifacts" / "solve-path.json").read_bytes(),
            (child / "artifacts" / "solve-path.json").read_bytes(),
            manifest["artifact_r0_sha256"],
        )


def test_m1_a_raised_lineage_continues_as_its_v1_lineage(tmp_path: Path) -> None:
    """F2 review M1 (D8): revision continuation reads a v2 ancestor as its lowering, so a
    two-revision lineage committed as raised documents writes the v1 lineage's `solve-path.json`
    byte for byte (the `revision_continuation` member `taken`, its `source_document` the v1
    document) and the same `artifact_r0_sha256`."""
    v1 = _lineage_bundles(tmp_path / "v1", raised=False)
    v2 = _lineage_bundles(tmp_path / "v2", raised=True)
    member = json.loads(v1[1])["revision_continuation"]
    assert (member["status"], member["reason"]) == ("taken", None)
    assert member["source_document"]["schema_version"] == 1
    assert v2 == v1
