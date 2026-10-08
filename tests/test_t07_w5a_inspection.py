"""T07 W5a: the `Inspection` methods on `LocalApplication`, and the raw export.

Design note `docs/design/T07-jobs-and-bindings.md` §4.1–§4.2 (the eight methods), §11.4 (the
bundle projection, as amended by ruling round 2: `solution-state.json` listed and read by
pointer), and the V17 spec's F4: `read` covers every principal's artifacts (a), and an imported
bundle's members are registered `<import id>/<file>` and reachable through `get_artifact` (b).
W4a tested F4's jobs half; this is the artifacts half. Also W3e's items for W5a: a value read at
`/variables/<id>` is the file's binary64, and (e) an interrupted solve has no solution state to
read.

Expectations are independent of the code under test: file bytes and values are read from disk
with `json`, signatures from `MODEL_SIGNATURES`, hashes recomputed.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import struct
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from t07_corpus import CORPUS
from t07_jobs_support import commit, lifecycle_violations

from openflowsheet.application.authz import grant
from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.policies import APPLICATION_POLICIES
from openflowsheet.application.revision_binding import MODEL_BUILDERS, MODEL_SIGNATURES
from openflowsheet.application.store import STORE_SCHEMA
from openflowsheet.application.types import (
    Change,
    Edit,
    Job,
    JobRequest,
    ReplayPolicy,
    SolveBody,
)
from openflowsheet.canonical import document_sha256, file_sha256
from openflowsheet.run.bundle import ARTIFACT_DIR, MANIFEST_NAME
from openflowsheet.run.manifest import policy_sha256

NOMINAL = "SYN-001-nominal"


@pytest.fixture
def app(tmp_path: Path) -> Iterator[LocalApplication]:
    application = LocalApplication.create(tmp_path / "project", project_id="w5a")
    yield application
    try:
        assert lifecycle_violations(application) == {}
    finally:
        application.close()


def _solve(app: LocalApplication, revision_id: str, key: str) -> Job:
    job = app.submit_job(JobRequest("solve", key, SolveBody(revision_id))).job
    assert job.status == "completed", job
    return job


def _file(app: LocalApplication, artifact_id: str) -> Path:
    row = app.store.artifact(artifact_id)
    assert row is not None, artifact_id
    return app.files_root / row.relpath


def _refused(call: Any, code: str) -> dict[str, Any]:
    with pytest.raises(ApplicationError) as raised:
        call()
    assert raised.value.code == code, raised.value.error
    return dict(raised.value.error.detail)


def _bits(value: float) -> bytes:
    return struct.pack(">d", float(value))


# ============================================================================== the project


def test_get_project_states_the_project_and_the_caller(app: LocalApplication) -> None:
    empty = app.get_project()
    assert (empty.project_id, empty.head, empty.revision_count) == ("w5a", None, 0)
    assert dict(empty.job_counts) == dict.fromkeys(
        ("queued", "running", "completed", "failed", "cancelled", "timed_out"), 0
    )
    assert empty.solve_policies == tuple(
        (policy_id, policy_sha256(policy))
        for policy_id, policy in sorted(APPLICATION_POLICIES.items())
    )
    # T08 offers `T08-warm-v1` (ADR 0024 D1) and `T08-ptc-v1` (ADR 0023) beside the two routes'
    # registered policies.
    assert {policy_id for policy_id, _ in empty.solve_policies} == {
        "T06-revision-v2",
        "T04-W12",
        "T08-ptc-v1",
        "T08-warm-v1",
    }
    assert empty.default_policy_id == "default"
    assert (empty.principal_id, empty.capability_id) == ("local-owner", "local-owner")
    assert len(empty.rights) == 6
    assert empty.server.store_schema == STORE_SCHEMA and empty.server.git_commit is None

    revision_id = commit(app, CORPUS[NOMINAL]())
    _solve(app, revision_id, "counted")
    summary = app.get_project()
    assert (summary.head, summary.revision_count) == (revision_id, 1)
    assert summary.job_counts["completed"] == 1 and sum(summary.job_counts.values()) == 1

    directory = app.store.directory
    assert directory is not None
    reader, _ = grant(directory, principal_id="reader", rights=("read",))
    with LocalApplication.open(directory, capability=reader) as opened:
        seen = opened.get_project()
        assert (seen.principal_id, seen.capability_id) == ("reader", reader.capability_id)
        assert (seen.rights, seen.limits) == (("read",), reader.limits)


def test_list_models_is_the_signatures_and_constructs_nothing(
    app: LocalApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    import openflowsheet.application.revision_binding as binding

    def refuse(*_: Any, **__: Any) -> Any:
        raise AssertionError("list_models constructed a unit")

    monkeypatch.setattr(binding, "MODEL_BUILDERS", {key: refuse for key in MODEL_BUILDERS})
    view = app.list_models()
    assert [model["model_id"] for model in view.models] == sorted(MODEL_BUILDERS)
    for model in view.models:
        signature = MODEL_SIGNATURES[model["model_id"]]
        assert model["ports"] == [
            {
                "name": port.name,
                "direction": port.direction,
                "multiplicity": port.multiplicity,
                "kind": port.kind,
            }
            for port in signature.ports
        ]
        assert (model["required"], model["zero"]) == (
            list(signature.required),
            list(signature.zero),
        )
        assert [pin["name"] for pin in model["pins"]] == [pin.name for pin in signature.pins]
        assert [choice["name"] for choice in model["choices"]] == [
            choice.name for choice in signature.choices
        ]
    assert any(model["pins"] or model["choices"] for model in view.models), "pins are listed"


# ============================================================================ revisions


def test_list_revisions_pages_in_commit_order(app: LocalApplication) -> None:
    ids = []
    for index in range(5):
        document = {**CORPUS[NOMINAL](), "title": f"title {index} ‮"}
        ids.append(commit(app, document))
    first = app.list_revisions(limit=2)
    assert [summary.revision_id for summary in first.items] == ids[:2]
    assert first.next_cursor is not None
    second = app.list_revisions(cursor=first.next_cursor, limit=2)
    third = app.list_revisions(cursor=second.next_cursor, limit=2)
    assert [s.revision_id for s in (*second.items, *third.items)] == ids[2:]
    assert third.next_cursor is None
    everything = app.list_revisions()
    assert [s.head for s in everything.items] == [False] * 4 + [True]
    assert [s.title for s in everything.items] == [f"title {i} ‮" for i in range(5)]
    assert [s.parent_revision for s in everything.items] == [None, *ids[:4]]
    with app.store.reading() as connection:
        stored = [app.store.get_revision(connection, rid) for rid in ids]
    assert [s.content_sha256 for s in everything.items] == [r.content_hash for r in stored if r]
    for arguments, member in (({"limit": 0}, "/limit"), ({"cursor": "nope"}, "/cursor")):
        assert _refused(lambda a=arguments: app.list_revisions(**a), "invalid_request") == {
            "pointer": member
        }


def test_get_revision_diff_and_structure(app: LocalApplication) -> None:
    before = commit(app, CORPUS[NOMINAL]())
    with app.store.reading() as connection:
        head = app.store.get_revision(connection, before)
    assert head is not None
    retitled = app.commit_change(
        Change(edits=(Edit("set", ("title",), "another title"),)), before, "retitle"
    ).revision_id
    assert retitled is not None
    diff = app.diff_revisions(before, retitled)
    assert diff.empty, "a title is not content"
    changed = app.commit_change(
        Change(edits=(Edit("set", ("connections",), head.document["connections"][:-1]),)),
        retitled,
        "drop-a-connection",
    ).revision_id
    assert changed is not None
    assert app.diff_revisions(retitled, changed).changed

    shown = app.get_revision(before, depth=12)
    assert shown.value == head.as_document()
    assert shown.sha256 == document_sha256(head.as_document())
    assert app.get_revision(before, pointer="/title").value == head.document["title"]
    structure = app.inspect_structure(before, pointer="/solve_path")
    assert structure.value == "revision_eo"

    assert _refused(lambda: app.get_revision("rev-missing"), "not_found") == {
        "revision_id": "rev-missing"
    }
    assert _refused(lambda: app.diff_revisions(before, "rev-missing"), "not_found")
    assert _refused(lambda: app.get_revision(before, pointer="/nope"), "not_found") == {
        "pointer": "/nope"
    }
    assert _refused(lambda: app.inspect_structure(before, depth=13), "invalid_request") == {
        "pointer": "/depth"
    }
    refusals = [row for row in app.store.audit_rows() if row["outcome"] == "refused"]
    assert {row["operation"] for row in refusals} >= {
        "get_revision",
        "diff_revisions",
        "inspect_structure",
    }


def test_a_revision_no_route_binds_has_a_structure_reason(app: LocalApplication) -> None:
    revision_id = commit(app, {"title": "nothing to bind"})
    # Ruling round 6, B1: with no route, `{not_run_reason, hint}`; a document refused before the
    # structural stage reports no hint.
    assert app.inspect_structure(revision_id).value["hint"] is None
    # ADR 0019 Amendment 3 (A3.1) adds three members, by addition only (M06 WO-1).
    assert set(app.inspect_structure(revision_id).value) == {
        "not_run_reason",
        "hint",
        "validation_structural_report",
        "rows",
        "columns",
    }


# ============================================================================ artifacts


def test_the_bundle_projection_lists_its_members_and_the_solution_state(
    app: LocalApplication,
) -> None:
    """§11.4 as amended by ruling round 2: `{manifest, files}`, `solution-state.json` listed."""
    job = _solve(app, commit(app, CORPUS[NOMINAL]()), "bundle")
    bundle_id = f"{job.job_id}:bundle"
    bundle = app.get_artifact(bundle_id, depth=12)
    row = app.store.artifact(bundle_id)
    assert row is not None and bundle.sha256 == row.sha256
    directory = app.files_root / row.relpath
    assert bundle.value["manifest"] == json.loads((directory / MANIFEST_NAME).read_bytes())
    files = {entry["name"]: entry for entry in bundle.value["files"]}
    on_disk = {MANIFEST_NAME, *(p.name for p in (directory / ARTIFACT_DIR).iterdir())}
    assert set(files) == on_disk
    assert files["solution-state.json"]["kind"] == "solution_state"
    for name, entry in files.items():
        path = directory / (name if name == MANIFEST_NAME else f"{ARTIFACT_DIR}/{name}")
        assert entry == {
            "name": name,
            "kind": entry["kind"],
            "artifact_id": f"{bundle_id}/{name}",
            "sha256": file_sha256(path),
            "size_bytes": path.stat().st_size,
        }
    paged = app.get_artifact(bundle_id, pointer="/files", limit=3)
    assert [entry["name"] for entry in paged.value] == [e["name"] for e in bundle.value["files"]][
        :3
    ]


def test_a_value_read_by_pointer_is_the_files_binary64(app: LocalApplication) -> None:
    """W3e for W5a: `get_artifact(<bundle>/solution-state.json, pointer="/variables/<id>")`."""
    job = _solve(app, commit(app, CORPUS[NOMINAL]()), "values")
    state_id = f"{job.job_id}:bundle/solution-state.json"
    on_disk = json.loads(_file(app, state_id).read_bytes())
    assert len(on_disk["variable_ids"]) == 47
    for variable_id in on_disk["variable_ids"]:
        pointer = "/variables/" + variable_id.replace("~", "~0").replace("/", "~1")
        value = app.get_artifact(state_id, pointer=pointer).value
        assert _bits(value) == _bits(on_disk["variables"][variable_id]), variable_id
    whole = app.get_artifact(state_id, pointer="/variables")
    assert whole.value == on_disk["variables"] and whole.next_cursor is None
    assert not whole.truncated, "objects are not paged, and this one fits"
    ids: list[str] = []
    cursor = None
    while True:
        page = app.get_artifact(state_id, pointer="/variable_ids", cursor=cursor, limit=10)
        assert len(page.value) == min(10, 47 - len(ids))
        ids.extend(page.value)
        cursor = page.next_cursor
        if cursor is None:
            break
    assert ids == on_disk["variable_ids"]
    assert app.get_artifact(state_id).sha256 == file_sha256(_file(app, state_id))


def test_the_raw_export_is_the_stored_bytes(app: LocalApplication) -> None:
    job = _solve(app, commit(app, CORPUS[NOMINAL]()), "raw")
    bundle_id = f"{job.job_id}:bundle"
    members = app.store.artifact_children(bundle_id)
    assert len(members) >= 8
    for member in members:
        raw = app.artifact_bytes(member.artifact_id)
        assert raw == (app.files_root / member.relpath).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == member.sha256
    assert _refused(lambda: app.artifact_bytes(bundle_id), "unsupported")
    assert _refused(lambda: app.artifact_bytes("job-999999:bundle/x.json"), "not_found")
    assert _refused(lambda: app.get_artifact("../../etc/passwd"), "not_found")


def test_read_covers_every_principals_artifacts(app: LocalApplication) -> None:
    """V17 spec F4 (a), the artifacts half: a `read`-only principal reads the owner's
    artifacts exactly as the owner does; without `read`, nothing."""
    job = _solve(app, commit(app, CORPUS[NOMINAL]()), "owners")
    directory = app.store.directory
    assert directory is not None
    reader, _ = grant(directory, principal_id="reader", rights=("read",))
    drafter, _ = grant(directory, principal_id="drafter", rights=("draft", "execute"))
    ids = [
        f"{job.job_id}:bundle",
        *(m.artifact_id for m in app.store.artifact_children(f"{job.job_id}:bundle")),
    ]
    with LocalApplication.open(directory, capability=reader) as other:
        for artifact_id in ids:
            assert other.get_artifact(artifact_id) == app.get_artifact(artifact_id)
            if artifact_id != f"{job.job_id}:bundle":
                assert other.artifact_bytes(artifact_id) == app.artifact_bytes(artifact_id)
        assert other.list_revisions() == app.list_revisions()
    with LocalApplication.open(directory, capability=drafter) as blind:
        for call in (
            lambda: blind.get_artifact(ids[1]),
            lambda: blind.artifact_bytes(ids[1]),
            blind.list_revisions,
            blind.get_project,
            blind.list_models,
        ):
            _refused(call, "forbidden")


def test_an_imported_bundles_members_are_reachable(app: LocalApplication, tmp_path: Path) -> None:
    """V17 spec F4 (b): `reproduce` registers `import-<n>:bundle/<file>` for each member, and
    `get_artifact` reads each, the solution state's values included."""
    job = _solve(app, commit(app, CORPUS[NOMINAL]()), "to-import")
    source = _file(app, f"{job.job_id}:bundle")
    outside = tmp_path / "outside"
    shutil.copytree(source, outside)
    report = app.reproduce(outside, ReplayPolicy(rerun=False))
    assert report.mode == "inspected_archived_results"
    imported = app.get_artifact("import-000001:bundle", depth=12)
    names = {entry["name"] for entry in imported.value["files"]}
    assert names == {MANIFEST_NAME, *(p.name for p in (outside / ARTIFACT_DIR).iterdir())}
    for entry in imported.value["files"]:
        assert entry["artifact_id"] == f"import-000001:bundle/{entry['name']}"
        original = outside / (
            entry["name"] if entry["name"] == MANIFEST_NAME else f"{ARTIFACT_DIR}/{entry['name']}"
        )
        assert app.artifact_bytes(entry["artifact_id"]) == original.read_bytes()
        assert app.get_artifact(entry["artifact_id"]).sha256 == file_sha256(original)
    manifest = app.get_artifact(f"import-000001:bundle/{MANIFEST_NAME}", depth=12).value
    assert manifest == json.loads((outside / MANIFEST_NAME).read_bytes())
    assert imported.value["manifest"] == manifest
    state = json.loads((outside / ARTIFACT_DIR / "solution-state.json").read_bytes())
    variable_id = state["variable_ids"][0]
    value = app.get_artifact(
        "import-000001:bundle/solution-state.json", pointer=f"/variables/{variable_id}"
    ).value
    assert _bits(value) == _bits(state["variables"][variable_id])


def test_a_file_that_is_not_a_canonical_json_document_reads_as_its_lines(
    app: LocalApplication, tmp_path: Path
) -> None:
    """An imported member is whatever it holds: not JSON, a repeated key or a NaN reads as text
    lines, never as a parse error and never as a JSON value it is not."""
    job = _solve(app, commit(app, CORPUS[NOMINAL]()), "to-mangle")
    outside = tmp_path / "mangled"
    shutil.copytree(_file(app, f"{job.job_id}:bundle"), outside)
    texts = {
        "solve-events.json": b"not json\n\x1b[2Jsecond line",
        "solve-plan.json": b'{"a": 1, "a": 2}',
        "execution-plan.json": b'{"a": NaN}',
    }
    for name, text in texts.items():
        (outside / ARTIFACT_DIR / name).write_bytes(text)
    app.reproduce(outside, ReplayPolicy(rerun=False))
    for name, text in texts.items():
        artifact_id = f"import-000001:bundle/{name}"
        assert app.get_artifact(artifact_id).value == text.decode().splitlines()
        assert app.artifact_bytes(artifact_id) == text


def test_an_interrupted_solve_has_no_solution_state(app: LocalApplication) -> None:
    """W3e (e) through the contract: an interrupted solve registers no bundle, so there is no
    solution state to read; its partial trace is readable, an array that pages."""
    revision_id = commit(app, CORPUS[NOMINAL]())

    def cancel_at(job_id: str, check: int) -> None:
        if check == 8:
            app.cancel_job(job_id)

    app.executor.test_hook_on_check = cancel_at
    try:
        job = app.submit_job(JobRequest("solve", "interrupted", SolveBody(revision_id))).job
    finally:
        app.executor.test_hook_on_check = None
    assert job.status == "cancelled"
    for missing in (f"{job.job_id}:bundle", f"{job.job_id}:bundle/solution-state.json"):
        assert _refused(lambda m=missing: app.get_artifact(m), "not_found") == {
            "artifact_id": missing
        }
    (partial,) = job.outputs
    events = json.loads(_file(app, partial.artifact_id).read_bytes())
    assert len(events) >= 2
    read: list[Any] = []
    cursor = None
    while True:
        page = app.get_artifact(partial.artifact_id, limit=1, depth=12, cursor=cursor)
        read.extend(page.value)
        cursor = page.next_cursor
        if cursor is None:
            break
    assert read == events
