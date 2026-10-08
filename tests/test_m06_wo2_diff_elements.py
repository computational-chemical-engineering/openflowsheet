"""M06 WO-2: `diff_revisions` gains element-level detail (Ask 6).

Design note `docs/design/M06-web-shell.md` §4.2, gate G5; ADR 0019 Amendment 3, A3.2. The G5
pair is the W26 fixture project's rev-000001 -> rev-000002 (§8: NET-02, then NET-02 with
`instances[U-SPLIT].parameters.split_fraction.value` 0.95 -> 0.90). The coarse members of every
ordered pair of the 50 corpus revisions are pinned by a digest taken before WO-2 (at `f085d14`,
whose `transactions.semantic_diff` is `67029fa`'s) with the pre-amendment function.
"""

from __future__ import annotations

import copy
import hashlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from t07_corpus import CORPUS
from t07_jobs_support import commit

from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import dispatch
from openflowsheet.application.transactions import element_diff, revision_diff, semantic_diff
from openflowsheet.application.types import Change, DiffElement, Edit, schema_errors
from openflowsheet.canonical import canonical_json

NET02 = "SYN-001-T06-NET02"
#: SHA-256 of `canonical_json([[from, to, added, removed, changed], ...])` over the 2500 ordered
#: pairs of `sorted(CORPUS)`, computed with the pre-amendment `semantic_diff` at `f085d14`.
COARSE_PAIRS_SHA256 = "db95054fb9e4d0b33af56949a1cde6ad6a03c7460e78aa88b9f51869c9047f3d"


def _split_edited() -> dict[str, Any]:
    document = CORPUS[NET02]()
    (splitter,) = [item for item in document["instances"] if item["id"] == "U-SPLIT"]
    assert splitter["parameters"]["split_fraction"]["value"] == 0.95
    splitter["parameters"]["split_fraction"]["value"] = 0.90
    return document


@pytest.fixture(scope="module")
def application(tmp_path_factory: pytest.TempPathFactory) -> Iterator[LocalApplication]:
    with LocalApplication.create(
        tmp_path_factory.mktemp("m06-wo2") / "p", project_id="m06-wo2"
    ) as app:
        yield app


# -- G5 ------------------------------------------------------------------------------------------


def test_g5_the_fixture_pair(application: LocalApplication) -> None:
    first = commit(application, CORPUS[NET02]())
    second = commit(application, _split_edited())
    assert (first, second) == ("rev-000001", "rev-000002")
    diff = application.diff_revisions(first, second)
    assert diff.changed == ("instances",)
    assert (diff.added, diff.removed) == ((), ())
    response = dispatch(
        application, "diff_revisions", {"from_revision": first, "to_revision": second}
    )
    assert response["elements"] == [
        {
            "member": "instances",
            "id": "U-SPLIT",
            "change": "changed",
            "paths": [["parameters", "split_fraction", "value"]],
        }
    ]
    assert schema_errors("application-results.schema.json#/$defs/semantic_diff", response) == []


def test_g5_coarse_members_equal_the_pre_amendment_output_on_every_corpus_pair() -> None:
    names = sorted(CORPUS)
    documents = {name: CORPUS[name]() for name in names}
    rows = []
    for left in names:
        for right in names:
            diff = revision_diff(documents[left], documents[right])
            assert diff.elements is not None
            rows.append([left, right, list(diff.added), list(diff.removed), list(diff.changed)])
    assert len(rows) == 2500
    assert hashlib.sha256(canonical_json(rows)).hexdigest() == COARSE_PAIRS_SHA256


def test_elements_stay_out_of_transaction_results(application: LocalApplication) -> None:
    """R-172's watch item: `commit_change` and `preview_change` carry the diff without
    `elements`, so `transaction-result.schema.json` and every ledger replay are unchanged."""
    with application.store.reading() as connection:
        head = application.store.head(connection)
    edit = Change(edits=(Edit("set", ("title",), "retitled"),))
    preview = application.preview_change(edit, head)
    committed = application.commit_change(edit, head, "m06-wo2-retitle")
    for result in (preview, committed):
        assert result.diff is not None and result.diff.elements is None
        document = result.as_document()
        assert set(document["diff"]) == {"added", "removed", "changed"}
        assert schema_errors("transaction-result.schema.json", document) == []


# -- the rule (design note §4.2) ------------------------------------------------------------------


def _revision(**members: Any) -> dict[str, Any]:
    return {"title": "t", **members}


def test_added_removed_and_changed_by_id_in_code_point_order() -> None:
    before = _revision(
        instances=[{"id": "a", "x": 1}, {"id": "B", "x": 1}, {"id": "gone", "x": 1}],
    )
    after = _revision(
        instances=[{"id": "é", "x": 1}, {"id": "B", "x": 2}, {"id": "a", "x": 1}],
    )
    assert element_diff(before, after) == (
        DiffElement("instances", "B", "changed", (("x",),)),
        DiffElement("instances", "gone", "removed"),
        DiffElement("instances", "é", "added"),
    )


def test_paths_are_every_key_added_removed_or_changed_with_arrays_atomic() -> None:
    before = _revision(
        specifications=[
            {"id": "S", "target": {"path": "state.T", "component": None}, "old": 1, "v": [1, 2]}
        ]
    )
    after = _revision(
        specifications=[
            {"id": "S", "target": {"path": "state.P", "component": None}, "new": 1, "v": [1, 3]}
        ]
    )
    (element,) = element_diff(before, after)
    assert element.paths == (("new",), ("old",), ("target", "path"), ("v",))
    assert element.as_document()["paths"] == [["new"], ["old"], ["target", "path"], ["v"]]


def test_order_alone_gives_no_entry() -> None:
    before = _revision(connections=[{"id": "S1", "k": 1}, {"id": "S2", "k": 2}])
    after = _revision(connections=[{"id": "S2", "k": 2}, {"id": "S1", "k": 1}])
    assert semantic_diff(before, after).changed == ("connections",)
    assert element_diff(before, after) == ()


@pytest.mark.parametrize(
    "items",
    [
        [{"id": "x"}, {"id": "x", "k": 1}],  # not unique
        [{"id": "x"}, {"k": 1}],  # an item without an id
        [{"id": 1}],  # a non-string id
        [{"id": "x"}, "text"],  # an item that is not an object
        {"id": "x"},  # not an array
    ],
)
def test_unpairable_members_are_one_entry_without_an_id(items: Any) -> None:
    before = _revision(instances=[{"id": "x"}])
    after = _revision(instances=items)
    assert element_diff(before, after) == (DiffElement("instances", None, "changed"),)
    assert element_diff(after, after) == ()


def test_members_in_order_and_descriptive_members_excluded() -> None:
    before = _revision(
        instances=[{"id": "u", "notes": "a"}],
        connections=[{"id": "c"}],
        specifications=[{"id": "s", "value": 1.0}],
        description="before",
    )
    after = copy.deepcopy(before)
    after["title"] = "other"
    after["description"] = "after"
    assert element_diff(before, after) == ()
    after["specifications"][0]["value"] = 2.0
    after["instances"][0]["notes"] = "b"  # descriptive inside an item is content
    after["connections"].append({"id": "d"})
    assert [(e.member, e.id, e.change) for e in element_diff(before, after)] == [
        ("instances", "u", "changed"),
        ("connections", "d", "added"),
        ("specifications", "s", "changed"),
    ]


def test_a_member_absent_from_one_revision() -> None:
    assert element_diff(_revision(), _revision(connections=[{"id": "c"}])) == (
        DiffElement("connections", None, "changed"),
    )
    assert element_diff(_revision(), _revision()) == ()


def test_the_corpus_pairs_are_schema_valid_and_name_only_coarse_members() -> None:
    names = sorted(CORPUS)
    checked = 0
    for left in names[::7]:
        for right in names[::5]:
            diff = revision_diff(CORPUS[left](), CORPUS[right]())
            document = diff.as_document()
            assert (
                schema_errors("application-results.schema.json#/$defs/semantic_diff", document)
                == []
            ), (left, right)
            assert {e["member"] for e in document["elements"]} <= set(diff.changed)
            checked += 1
    assert checked == 80


def test_the_diff_is_independent_of_the_project(tmp_path: Path) -> None:
    """The same pair diffs the same in a second project (no store state enters)."""
    with LocalApplication.create(tmp_path / "q", project_id="m06-wo2-q") as other:
        first = commit(other, CORPUS[NET02]())
        second = commit(other, _split_edited())
        assert other.diff_revisions(first, second) == revision_diff(
            CORPUS[NET02](), _split_edited()
        )
