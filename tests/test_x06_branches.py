"""X06-WO2: branches, ADR 0078 D2 (E-X06-6, E-X06-8, E-X06-9, E-X06-10).

A branch is the store's `refs` row `branches/<name>`; `head` keeps its row. These tests drive
`LocalApplication` (the Python transport); the conformance scenario runs the same operations on
every transport (`tests/test_t07_conformance.py`). E-X06-7 is `test_x06_change_set_golden.py`.
"""

from __future__ import annotations

import json
import multiprocessing
import random
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import x06_branch_support as support
from t07_corpus import CORPUS
from t07_jobs_support import commit

from openflowsheet.application.errors import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import dispatch
from openflowsheet.application.store import BRANCH_PREFIX, HEAD
from openflowsheet.application.transaction_types import Change, Edit
from openflowsheet.canonical import canonical_json

SPAWN = multiprocessing.get_context("spawn")
#: E-X06-8: rounds per race and transport of the race.
TRIALS = 20


def title(text: str, branch: str | None = None) -> Change:
    return Change(edits=(Edit("set", ("title",), text),), branch=branch)


@pytest.fixture
def app(tmp_path: Path) -> Iterator[LocalApplication]:
    """A project with two head revisions, `rev-000001` and `rev-000002` (the head)."""
    application = LocalApplication.create(tmp_path / "p")
    assert application.commit_change(title("one"), None, "seed-1").revision_id == "rev-000001"
    assert application.commit_change(title("two"), "rev-000001", "seed-2").status == "committed"
    yield application
    application.close()


def refs(application: LocalApplication) -> dict[str, str]:
    with application.store.reading() as connection:
        rows = connection.execute("SELECT name, revision_id FROM refs").fetchall()
    return {str(name): str(tip) for name, tip in rows}


def refused(call: Any) -> dict[str, Any]:
    with pytest.raises(ApplicationError) as caught:
        call()
    return caught.value.error.as_document()


# ------------------------------------------------------------------------------- E-X06-6


def test_e_x06_6_the_branch_lifecycle(app: LocalApplication) -> None:
    created = app.create_branch(name="what-if", revision_id="rev-000001", idempotency_key="c1")
    assert created.as_document() == {
        "status": "created",
        "name": "what-if",
        "revision_id": "rev-000001",
        "conflict": None,
    }
    assert refs(app) == {HEAD: "rev-000002", BRANCH_PREFIX + "what-if": "rev-000001"}

    # A commit on the branch moves the branch and leaves the head.
    on_branch = app.commit_change(title("b1", "what-if"), "rev-000001", "b1")
    assert on_branch.status == "committed"
    tip = on_branch.revision_id
    assert tip == "rev-000003"
    assert refs(app) == {HEAD: "rev-000002", BRANCH_PREFIX + "what-if": tip}
    assert app.get_revision(tip, pointer="/title", depth=1, cursor=None, limit=50).value == "b1"

    # A stale or null expected revision on a branch is a conflict with the branch tip.
    stale = app.commit_change(title("b2", "what-if"), "rev-000001", "b2")
    assert (stale.status, stale.conflict) == ("conflict", {"expected": "rev-000001", "actual": tip})
    first = app.commit_change(title("b3", "what-if"), None, "b3")
    assert (first.status, first.conflict) == ("conflict", {"expected": None, "actual": tip})

    # A create of an existing name is a conflict, whatever the revision asked for.
    again = app.create_branch(name="what-if", revision_id=tip, idempotency_key="c2")
    assert again.as_document() == {
        "status": "conflict",
        "name": "what-if",
        "revision_id": tip,
        "conflict": {"expected": None, "actual": tip},
    }

    # Delete with a stale tip is a conflict; with the tip, `deleted`.
    late = app.delete_branch(name="what-if", expected_revision="rev-000001", idempotency_key="d1")
    assert late.as_document() == {
        "status": "conflict",
        "name": "what-if",
        "revision_id": tip,
        "conflict": {"expected": "rev-000001", "actual": tip},
    }
    deleted = app.delete_branch(name="what-if", expected_revision=tip, idempotency_key="d2")
    assert deleted.as_document() == {
        "status": "deleted",
        "name": "what-if",
        "revision_id": None,
        "conflict": None,
    }
    assert refs(app) == {HEAD: "rev-000002"}
    # Every revision stays readable after its branch is deleted.
    assert app.get_revision(tip, pointer="/title", depth=1, cursor=None, limit=50).value == "b1"
    assert [summary.revision_id for summary in app.list_revisions().items] == [
        "rev-000001",
        "rev-000002",
        "rev-000003",
    ]


def test_e_x06_6_head_is_reserved_on_create_and_delete_and_names_the_main_line(
    app: LocalApplication,
) -> None:
    for call in (
        lambda: app.create_branch(name="head", revision_id="rev-000001", idempotency_key="h1"),
        lambda: app.delete_branch(
            name="head", expected_revision="rev-000002", idempotency_key="h2"
        ),
    ):
        error = refused(call)
        assert error["code"] == "invalid_request"
        assert (error["detail"]["code"], error["detail"]["pointer"]) == (
            "branch_name_reserved",
            "/name",
        )
    assert refs(app) == {HEAD: "rev-000002"}
    # As the branch of a change, `head` is the main line.
    moved = app.commit_change(title("three", "head"), "rev-000002", "on-head")
    assert moved.status == "committed"
    assert refs(app) == {HEAD: moved.revision_id}


def test_e_x06_6_an_unknown_branch_is_not_found(app: LocalApplication) -> None:
    for call in (
        lambda: app.commit_change(title("x", "nowhere"), "rev-000002", "u1"),
        lambda: app.preview_change(title("x", "nowhere"), "rev-000002"),
        lambda: app.delete_branch(
            name="nowhere", expected_revision="rev-000002", idempotency_key="u2"
        ),
    ):
        error = refused(call)
        assert error["code"] == "not_found"
        assert error["detail"]["code"] == "branch_not_found"
        assert error["message"].startswith("branch_not_found:")
    # An unknown revision to branch from is `not_found` too, and creates nothing.
    error = refused(
        lambda: app.create_branch(name="x", revision_id="rev-999999", idempotency_key="u3")
    )
    assert (error["code"], error["detail"]["pointer"]) == ("not_found", "/revision_id")
    assert refs(app) == {HEAD: "rev-000002"}
    assert [row["code"] for row in app.store.audit_rows() if row["outcome"] == "refused"] == [
        "not_found"
    ] * 4


@pytest.mark.parametrize("name", ["", "a/b", "-lead", "x" * 65, "é", "has space"])
def test_e_x06_6_a_name_outside_the_pattern_is_an_invalid_request(
    app: LocalApplication, name: str
) -> None:
    error = refused(
        lambda: app.create_branch(name=name, revision_id="rev-000001", idempotency_key="n1")
    )
    assert (error["code"], error["detail"]["pointer"]) == ("invalid_request", "/name")
    error = refused(lambda: app.commit_change(title("x", name), "rev-000002", "n2"))
    assert (error["code"], error["detail"]["pointer"]) == ("invalid_request", "/branch")


def test_e_x06_6_list_branches_orders_and_pages_120_branches(app: LocalApplication) -> None:
    names = [f"{prefix}{i:03d}" for i, prefix in enumerate("aBz9._-Q" * 15)]
    names = [name if name[0].isalnum() else "n" + name for name in names]
    assert len(set(names)) == 120
    shuffled = random.Random(7).sample(names, len(names))
    for index, name in enumerate(shuffled):
        assert app.create_branch(
            name=name, revision_id="rev-000001", idempotency_key=f"k{index}"
        ).status == ("created")
    pages = []
    cursor = None
    while True:
        page = app.list_branches(cursor=cursor, limit=50)
        pages.append([(item.name, item.revision_id) for item in page.items])
        cursor = page.next_cursor
        if cursor is None:
            break
    assert [len(page) for page in pages] == [50, 50, 21]
    listed = [entry for page in pages for entry in page]
    assert listed[0] == ("head", "rev-000002")
    assert [name for name, _ in listed[1:]] == sorted(names, key=lambda n: n.encode("utf-8"))
    assert {tip for _, tip in listed[1:]} == {"rev-000001"}
    # Through `dispatch`, the documents are the published shape.
    document = dispatch(app, "list_branches", {"limit": 2})
    assert document["items"] == [
        {"name": "head", "revision_id": "rev-000002"},
        {"name": sorted(names, key=str.encode)[0], "revision_id": "rev-000001"},
    ]
    error = refused(lambda: app.list_branches(cursor="not-a-cursor", limit=5))
    assert (error["code"], error["detail"]["pointer"]) == ("invalid_request", "/cursor")


def test_e_x06_6_a_project_without_a_head_lists_only_branches() -> None:
    application = LocalApplication.in_memory()
    try:
        assert application.list_branches().items == ()
        assert application.list_branches().next_cursor is None
    finally:
        application.close()


def test_e_x06_6_promotion_is_a_head_commit_restoring_the_branch_tip(
    app: LocalApplication,
) -> None:
    app.create_branch(name="w", revision_id="rev-000002", idempotency_key="c")
    tip = app.commit_change(title("what-if", "w"), "rev-000002", "b").revision_id
    promoted = app.commit_change(Change(restore_from=tip), "rev-000002", "promote")
    assert promoted.status == "committed"
    assert refs(app)[HEAD] == promoted.revision_id
    assert app.get_revision(promoted.revision_id, pointer="/title", depth=1, cursor=None, limit=5)
    assert (
        app.get_revision(
            promoted.revision_id, pointer="/title", depth=1, cursor=None, limit=5
        ).value
        == "what-if"
    )


# ------------------------------------------------------------------------------- E-X06-10


def test_e_x06_10_create_delete_and_branch_commit_replay_their_original_result(
    app: LocalApplication,
) -> None:
    created = app.create_branch(name="w", revision_id="rev-000001", idempotency_key="c")
    committed = app.commit_change(title("on w", "w"), "rev-000001", "b")
    tip = committed.revision_id
    deleted = app.delete_branch(name="w", expected_revision=tip, idempotency_key="d")
    # Replays, after the branch was deleted: each the original result, `replayed`.
    replayed_create = app.create_branch(name="w", revision_id="rev-000001", idempotency_key="c")
    assert replayed_create.as_document() == {**created.as_document(), "status": "replayed"}
    replayed_commit = app.commit_change(title("on w", "w"), "rev-000001", "b")
    assert (replayed_commit.status, replayed_commit.revision_id) == ("replayed", tip)
    replayed_delete = app.delete_branch(name="w", expected_revision=tip, idempotency_key="d")
    assert replayed_delete.as_document() == {**deleted.as_document(), "status": "replayed"}
    assert refs(app) == {HEAD: "rev-000002"}
    # The same key with another body is refused.
    for call in (
        lambda: app.create_branch(name="w2", revision_id="rev-000001", idempotency_key="c"),
        lambda: app.commit_change(title("other", "w"), "rev-000001", "b"),
        lambda: app.delete_branch(name="w", expected_revision="rev-000001", idempotency_key="d"),
    ):
        assert refused(call)["code"] == "idempotency_key_reused"
    assert refs(app) == {HEAD: "rev-000002"}
    # The branch, not only the body, is part of a commit's request: the same key and edits on
    # `head` are another request.
    assert refused(lambda: app.commit_change(title("on w"), "rev-000001", "b"))["code"] == (
        "idempotency_key_reused"
    )


def test_e_x06_10_the_branch_writes_are_audited_once(app: LocalApplication) -> None:
    app.create_branch(name="w", revision_id="rev-000001", idempotency_key="c")
    app.create_branch(name="w", revision_id="rev-000001", idempotency_key="c")
    app.delete_branch(name="w", expected_revision="rev-000001", idempotency_key="d")
    rows = [
        (row["operation"], row["effect"])
        for row in app.store.audit_rows()
        if row["outcome"] == "allowed" and row["operation"].endswith("_branch")
    ]
    assert rows == [("create_branch", "branch:w:created"), ("delete_branch", "branch:w:deleted")]


def test_e_x06_10_a_reserved_key_is_refused_on_the_transports(app: LocalApplication) -> None:
    for name, request in (
        ("create_branch", {"name": "w", "revision_id": "rev-000001", "idempotency_key": "auto:x"}),
        (
            "delete_branch",
            {"name": "w", "expected_revision": "rev-000001", "idempotency_key": "auto:x"},
        ),
    ):
        with pytest.raises(ApplicationError) as caught:
            dispatch(app, name, request)
        assert caught.value.error.code == "invalid_request"
        assert caught.value.error.detail["pointer"] == "/idempotency_key"


# ------------------------------------------------------------------------------- E-X06-8


def _prepare_races(application: LocalApplication) -> str:
    """The races' branches, `a<t>` and `c<t>` at the head; the head's id."""
    with application.store.reading() as connection:
        base = application.store.head(connection)
    assert base is not None
    for t in range(TRIALS):
        for name in (f"a{t}", f"c{t}"):
            created = application.create_branch(
                name=name, revision_id=base, idempotency_key=f"setup-{name}"
            )
            assert created.status == "created"
    return base


def _judge(
    application: LocalApplication, kind: str, base: str, outcomes: dict[int, list[Any]]
) -> None:
    tips = refs(application)
    head_before = base
    for t in range(TRIALS):
        statuses = sorted(outcomes[role][t][0] for role in (0, 1))
        if kind == "commit":
            assert statuses == ["committed", "conflict"], (t, outcomes)
            (won,) = [outcomes[r][t][1] for r in (0, 1) if outcomes[r][t][0] == "committed"]
            assert tips[BRANCH_PREFIX + f"a{t}"] == won
        elif kind == "create":
            assert statuses == ["conflict", "created"], (t, outcomes)
            assert tips[BRANCH_PREFIX + f"b{t}"] == base
            (lost,) = [outcomes[r][t][1] for r in (0, 1) if outcomes[r][t][0] == "conflict"]
            assert lost == base
        else:
            assert statuses == ["committed", "committed"], (t, outcomes)
            assert tips[BRANCH_PREFIX + f"c{t}"] == outcomes[1][t][1]
            head_before = outcomes[0][t][1]
    if kind == "mixed":
        assert tips[HEAD] == head_before
        # Each head commit's parent is the previous head commit: no branch commit moved it.
        chain = [base] + [outcomes[0][t][1] for t in range(TRIALS)]
        with application.store.reading() as connection:
            for parent, child in zip(chain, chain[1:], strict=False):
                revision = application.store.get_revision(connection, child)
                assert revision is not None and revision.parent_revision == parent
    else:
        assert tips[HEAD] == base


@pytest.mark.parametrize("kind", ["commit", "create", "mixed"])
def test_e_x06_8_races_in_threads(tmp_path: Path, kind: str) -> None:
    directory = tmp_path / "p"
    owner = LocalApplication.create(directory)
    owner.commit_change(title("base"), None, "seed")
    base = _prepare_races(owner)
    barrier = threading.Barrier(2)
    outcomes: dict[int, list[Any]] = {}

    def racer(role: int) -> None:
        application = LocalApplication.open(directory)
        try:
            outcomes[role] = support.race_trials(
                application, kind, role, TRIALS, base, barrier.wait
            )
        finally:
            application.close()

    threads = [threading.Thread(target=racer, args=(role,)) for role in (0, 1)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(300)
    assert sorted(outcomes) == [0, 1]
    try:
        _judge(owner, kind, base, outcomes)
    finally:
        owner.close()


@pytest.mark.parametrize("kind", ["commit", "create", "mixed"])
def test_e_x06_8_races_in_two_processes(tmp_path: Path, kind: str) -> None:
    directory = tmp_path / "p"
    owner = LocalApplication.create(directory)
    owner.commit_change(title("base"), None, "seed")
    base = _prepare_races(owner)
    barrier = SPAWN.Barrier(2)
    results = SPAWN.Queue()
    children = [
        SPAWN.Process(
            target=support.race_process,
            args=(str(directory), kind, role, TRIALS, base, barrier, results),
        )
        for role in (0, 1)
    ]
    for child in children:
        child.start()
    outcomes = dict(results.get(timeout=300) for _ in children)
    for child in children:
        child.join(60)
        assert child.exitcode == 0
    try:
        _judge(owner, kind, base, outcomes)
    finally:
        owner.close()


# ------------------------------------------------------------------------------- E-X06-9

PROBE = "c7probe-branch"


def _bundle_files(application: LocalApplication, job_id: str) -> dict[str, bytes]:
    job = application.get_job(job_id)
    (bundle,) = [output for output in job.outputs if output.kind == "replay_bundle"]
    row = application.store.artifact(bundle.artifact_id)
    assert row is not None
    root = application.files_root / row.relpath
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _find(document: Any, key: str) -> list[Any]:
    if isinstance(document, dict):
        found = [document[key]] if key in document else []
        return found + [hit for value in document.values() for hit in _find(value, key)]
    if isinstance(document, list):
        return [hit for value in document for hit in _find(value, key)]
    return []


def test_e_x06_9_a_branch_is_in_no_stored_document_and_changes_no_result(tmp_path: Path) -> None:
    application = LocalApplication.create(tmp_path / "p")
    try:
        parent = commit(application, CORPUS["SYN-001-nominal"]())
        application.create_branch(name=PROBE, revision_id=parent, idempotency_key="c")
        edit = Change(edits=(Edit("set", ("title",), "the same edit"),))
        on_head = application.commit_change(edit, parent, "h")
        on_branch = application.commit_change(Change(edits=edit.edits, branch=PROBE), parent, "b")
        assert on_head.status == on_branch.status == "committed"
        summaries = {s.revision_id: s for s in application.list_revisions().items}
        assert on_head.revision_id is not None and on_branch.revision_id is not None
        assert (
            summaries[on_head.revision_id].content_sha256
            == summaries[on_branch.revision_id].content_sha256
        )
        with application.store.reading() as connection:
            for revision_id in application.store.revision_ids(connection):
                stored = application.store.get_revision(connection, revision_id)
                assert stored is not None
                assert PROBE.encode() not in canonical_json(stored.as_document())
        runs = [
            application.solve(rev, "default")
            for rev in (on_head.revision_id, on_branch.revision_id)
        ]
        assert [(r.outcome, r.verification_status) for r in runs] == [("CONVERGED", "VERIFIED")] * 2
        files = [_bundle_files(application, run.job_id) for run in runs]
        state = [f["artifacts/solution-state.json"] for f in files]
        assert state[0] == state[1]
        hashes = [_find(json.loads(s), "state_sha256") for s in state]
        assert hashes[0] and hashes[0] == hashes[1]
        for bundle in files:
            assert not [name for name, data in bundle.items() if PROBE.encode() in data]
    finally:
        application.close()
