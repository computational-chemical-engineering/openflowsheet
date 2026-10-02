"""K06: local transactions, task validation and the CLI. Gates G02 and G06.

Blueprint §11 gives transactions three properties and each prevents a specific failure. An
expected revision stops a concurrent agent's work being silently overwritten — in a system
where agents edit in parallel that is a lost experiment, not a lost keystroke. An idempotency
key stops a timed-out client paying twice for an expensive solve, or receiving two answers it
cannot choose between. And a change set applies whole or not at all, so a draft is never left
half edited.

Blueprint §4.3's sentence shapes the validation tests: statuses are "validation results tied
to a revision and task, **not editable badges**". So the test that matters is that there is no
way to set one.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT

from openflowsheet.application.cli import main
from openflowsheet.application.revisions import (
    Revision,
    RevisionError,
    RevisionStore,
    content_hash,
)
from openflowsheet.application.transactions import (
    Application,
    ChangeSet,
    Edit,
    semantic_diff,
)
from openflowsheet.application.validation import validate

CASE = REPO_ROOT / "benchmarks" / "syn001" / "cases" / "SYN-001-nominal.yaml"


@pytest.fixture
def revision() -> dict[str, Any]:
    return yaml.safe_load(CASE.read_text(encoding="utf-8"))


@pytest.fixture
def application(revision: dict[str, Any]) -> Application:
    app = Application()
    app.store.put(Revision(revision_id=revision["revision_id"], document=revision))
    return app


def change_set(app: Application, key: str, new_id: str, **edits: Any) -> ChangeSet:
    return ChangeSet(
        edits=tuple(Edit("set", (name,), value) for name, value in edits.items()),
        expected_revision=app.store.head,
        idempotency_key=key,
        new_revision_id=new_id,
    )


def test_g02_a_revision_is_content_addressed_and_the_hash_is_never_supplied(
    revision: dict[str, Any],
) -> None:
    """The P01 case files leave `content_hash` absent with a note saying why.

    A hash written before ADR 0002's canonical encoding existed would have been a fabricated
    identity — which is exactly what `process_revision/invalid/fabricated-content-hash.yaml`
    is a fixture of. The encoding exists now, so it is computed here and never accepted.
    """
    assert "content_hash" not in revision, "the case files leave it out on purpose"

    stored = Revision(revision_id=revision["revision_id"], document=revision)
    assert stored.content_hash == content_hash(revision)
    assert len(stored.content_hash) == 64

    # Descriptive fields are excluded: two revisions differing only in their title are the
    # same process, and a hash that said otherwise would make every retitle a new model.
    retitled = {**revision, "title": "a different title", "description": "and description"}
    assert content_hash(retitled) == stored.content_hash

    # And a real change moves it.
    changed = {**revision, "specifications": []}
    assert content_hash(changed) != stored.content_hash


def test_a_revision_is_immutable(revision: dict[str, Any]) -> None:
    """Re-storing the same content is a no-op; storing different content under an id is not.

    Accepting the second silently would make every hash in every manifest citing that id a
    lie, which is the kind of failure nobody notices until a replay disagrees months later.
    """
    store = RevisionStore()
    first = store.put(Revision(revision_id="r1", document=revision))
    assert store.put(Revision(revision_id="r1", document=revision)) is first

    with pytest.raises(RevisionError, match="immutable"):
        store.put(Revision(revision_id="r1", document={**revision, "specifications": []}))


def test_an_optimistic_conflict_names_both_revisions(application: Application) -> None:
    """§11: a caller states what it read; a moved store refuses and says what it is at now."""
    first = application.commit(change_set(application, "k1", "rev-2", title="second"))
    assert first.status == "committed"

    stale = ChangeSet(
        edits=(Edit("set", ("title",), "third"),),
        expected_revision="SYN-001-nominal-r1",
        idempotency_key="k2",
        new_revision_id="rev-3",
    )
    result = application.commit(stale)
    assert result.status == "conflict"
    assert result.revision_id is None
    assert result.conflict == {"expected": "SYN-001-nominal-r1", "actual": "rev-2"}
    assert application.store.head == "rev-2", "a refused transaction changes nothing"


def test_an_idempotent_retry_returns_the_original_result(application: Application) -> None:
    """§11: "retrying an idempotent request cannot duplicate an expensive experiment"."""
    request = change_set(application, "same-key", "rev-2", title="once")
    first = application.commit(request)
    assert first.status == "committed"
    before = application.store.history()

    again = application.commit(request)
    assert again.status == "replayed"
    assert again.revision_id == first.revision_id
    assert again.diff is not None and first.diff is not None
    assert again.diff.as_document() == first.diff.as_document()
    assert application.store.history() == before, "no second revision was created"


def test_a_change_set_applies_whole_or_not_at_all(application: Application) -> None:
    """Grouped atomically: a draft is never left half edited."""
    head = application.store.head
    request = ChangeSet(
        edits=(
            Edit("set", ("title",), "new title"),
            Edit("set", ("description",), "new description"),
        ),
        expected_revision=head,
        idempotency_key="atomic",
        new_revision_id="rev-2",
    )
    result = application.commit(request)
    assert result.status == "committed"

    stored = application.store.get("rev-2").document
    assert stored["title"] == "new title"
    assert stored["description"] == "new description"
    # The base is untouched: a revision is never edited in place.
    assert application.store.get(head or "").document["title"] != "new title"


def test_a_transaction_reports_downstream_invalidations(application: Application) -> None:
    """§11: a committed edit tells the caller which runs are now against a stale revision."""
    application.record_run("run-a", "SYN-001-nominal-r1")
    application.record_run("run-b", "some-other-revision")

    result = application.commit(change_set(application, "k", "rev-2", title="moved"))
    assert result.status == "committed"
    assert result.invalidations == ("run-a",), (
        "the run against the superseded revision is named; the unrelated one is not"
    )


def test_the_semantic_diff_ignores_description_and_sees_content(
    revision: dict[str, Any],
) -> None:
    assert semantic_diff(revision, {**revision, "title": "x"}).empty

    changed = semantic_diff(revision, {**revision, "component_set": {"components": ["A"]}})
    assert not changed.empty
    assert any("component_set" in path for path in changed.changed + changed.removed)


def test_a_status_is_computed_and_there_is_no_way_to_set_one(
    revision: dict[str, Any],
) -> None:
    """Blueprint §4.3: "not editable badges". The test is that no setter exists."""
    from dataclasses import FrozenInstanceError

    report = validate(revision)
    assert report.status == "READY_FOR_SIMULATION"
    assert report.ready

    with pytest.raises(FrozenInstanceError):
        report.status = "READY_FOR_OPTIMIZATION"  # type: ignore[misc]

    # A revision carrying a status field does not get to keep it: the status is recomputed. The
    # frozen revision schema has no such member, and SCHEMA-01 applies it (T07 ruling round 5,
    # S3), so the claim is itself the finding; without it, the contents decide.
    claimed = {**revision, "status": "READY_FOR_SIMULATION", "specifications": []}
    report = validate(claimed)
    assert report.status == "INVALID"
    assert [(c.id, c.result, c.message) for c in report.checks] == [
        (
            "SCHEMA-01",
            "FAIL",
            "schema_invalid(): Additional properties are not allowed ('status' was unexpected)",
        )
    ]
    assert validate({**revision, "specifications": []}).status == "DRAFT", (
        "a revision that asserts its own readiness is still validated on its contents"
    )


def test_d16_an_incomplete_draft_is_committable(application: Application) -> None:
    """D16: "a syntactically valid draft can be committed without being executable".

    A tool that refuses to hold an unfinished thought gets worked around, and the work then
    happens somewhere with no provenance at all.
    """
    result = application.commit(
        ChangeSet(
            edits=(Edit("set", ("specifications",), []),),
            expected_revision=application.store.head,
            idempotency_key="draft",
            new_revision_id="draft-1",
        )
    )
    assert result.status == "committed", "an under-specified revision still commits"
    assert result.validation is not None
    assert result.validation.status == "DRAFT"
    assert not result.validation.ready


def test_a_malformed_revision_is_invalid_not_a_draft() -> None:
    """`DRAFT` means incomplete; `INVALID` means it is not a revision. Different answers."""
    report = validate({"revision_id": "broken"})
    assert report.status == "INVALID"
    assert any(not check.passed for check in report.checks)


def test_validation_computes_the_structural_counts(revision: dict[str, Any]) -> None:
    """T01 increment 1 replaced the absence this test used to pin (T01 specification A24).

    The counts are now produced and `structural_counts_absent_reason` is `None`; what remains
    unsupported is named by `STR-05` as a `NOT_RUN` check rather than by a null field.
    """
    report = validate(revision)
    assert report.structural_counts == {
        "free_variables": 47,
        "equations": 49,
        "matched": 47,
        "unmatched": 2,
    }
    assert report.structural_counts_absent_reason is None
    metrics = next(check for check in report.checks if check.id == "STR-05")
    assert metrics.result == "PASS"
    assert "24 blocks" in metrics.message, "the block metrics are reported, not implied by a null"


# ------------------------------------------------------------------------------- the CLI (G02)


def test_g02_the_cli_validates_a_revision(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", str(CASE)]) == 0
    printed = capsys.readouterr().out
    assert "READY_FOR_SIMULATION" in printed
    assert "structural counts: 49 equations" in printed
    assert "STR-05" in printed, "what it did not do is on screen, not buried"


def test_the_cli_emits_machine_readable_output(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", str(CASE), "--json"]) == 0
    document = json.loads(capsys.readouterr().out)
    assert document["status"] == "READY_FOR_SIMULATION"
    assert document["structural_counts"]["matched"] == 47


def test_g06_solve_inspect_and_replay_end_to_end(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """**Gate G06**: the end-to-end example is inspectable without unrelated code.

    Three commands, no imports, no test to read: solve a registered case, inspect what the run
    claimed and did not claim, replay the bundle. A reader who runs these three has the whole
    vertical slice in front of them.
    """
    from openflowsheet.run.manifest import THREAD_VARIABLES

    for variable in THREAD_VARIABLES:
        monkeypatch.setenv(variable, "1")

    bundle = tmp_path / "bundle"
    assert main(["solve", "SYN-001-nominal", "--out", str(bundle)]) == 0
    solved = capsys.readouterr().out
    assert "CONVERGED" in solved and "VERIFIED" in solved

    assert main(["inspect", str(bundle)]) == 0
    inspected = capsys.readouterr().out
    for expected in (
        "=== run",
        "=== environment",
        "=== certificate",
        "=== what this certificate does not claim",
        "=== trace",
        "NO_RANK_LOSS_DETECTED",
        "not an experimental validation",
        "no finite test suite",
    ):
        assert expected.lower() in inspected.lower(), expected

    assert main(["replay", str(bundle)]) == 0
    replayed = capsys.readouterr().out
    assert "inspected_archived_results" in replayed or "exact_replay" in replayed
    assert "NOT_RUN" in replayed


def test_the_cli_refuses_an_unregistered_case(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["solve", "SYN-001-invented", "--out", "/tmp/nowhere"]) == 2
    assert "no registered case" in capsys.readouterr().err
