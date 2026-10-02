"""T07 W5d: lone surrogates are non-canonical (design note §12.5 as amended by ruling round 4,
W5a-Q1; gate R4-G2).

A string value or key holding a code point in U+D800–U+DFFF has no UTF-8 form, and RFC 8785
constrains its input to I-JSON (RFC 7493 §2.1), which excludes it. `first_noncanonical` names it
— a value by its own pointer, a key by its member with U+FFFD in place of each surrogate — and
`canonical_json` refuses it with `CanonicalizationError`. So every caller refuses it typed:
`validate()`, both revision binders, in-process `commit_change` and `dispatch`, which no longer
needs a pass of its own.

R4-G2's matrix: each of the three strings × three placements in the SYN-001 revision — a string
leaf (`/title`), a numeric leaf (`/specifications/0/value`) and a key at depth 2
(`/provenance/<key>`). The expected pointers are written out here, not read back from the code;
`dispatch`'s are the ones `operations.first_unencodable` gave at `b13d556`, bounded.
"""

from __future__ import annotations

import copy
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from t07_corpus import CORPUS
from t07_jobs_support import commit, lifecycle_violations
from test_t07_w2d_noncanonical import SURROGATES

from openflowsheet.application.binding import Unbound, bind_revision_or_reason
from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import dispatch
from openflowsheet.application.revision_binding import bind_revision_flowsheet
from openflowsheet.application.types import Change, Edit, schema_errors
from openflowsheet.application.validation import validate
from openflowsheet.canonical import CanonicalizationError, canonical_json, first_noncanonical

NOMINAL = "SYN-001-nominal"
REPLACEMENT = "\ufffd"
PLACEMENTS = ("string_leaf", "numeric_leaf", "key_at_depth_2")


def _shown(text: str) -> str:
    """`text` with each surrogate replaced by U+FFFD, written out independently."""
    return "".join(REPLACEMENT if 0xD800 <= ord(c) <= 0xDFFF else c for c in text)


def _placed(placement: str, text: str) -> tuple[dict[str, Any], str]:
    """The SYN-001 revision with `text` at `placement`, and the pointer expected for it."""
    document = CORPUS[NOMINAL]()
    if placement == "string_leaf":
        document["title"] = text
        return document, "/title"
    if placement == "numeric_leaf":
        assert isinstance(document["specifications"][0]["value"], int | float)
        document["specifications"][0]["value"] = text
        return document, "/specifications/0/value"
    assert isinstance(document["provenance"], dict)
    document["provenance"][text] = 1
    return document, f"/provenance/{_shown(text)}"


def _edit(placement: str, text: str) -> Edit:
    """The change that makes `_placed`'s mutation (the key case: one member under `provenance`)."""
    if placement == "string_leaf":
        return Edit("set", ("title",), text)
    if placement == "numeric_leaf":
        return Edit("set", ("specifications", 0, "value"), text)
    return Edit("set", ("provenance",), {text: 1})


#: What `dispatch` refused with at `b13d556` (`first_unencodable`, then bounded), for the request
#: carrying `_edit`: the edit's value, or the key inside it.
DISPATCH_POINTER_AT_B13D556: dict[tuple[str, str], str] = {
    **{(p, s): "/edits/0/value" for p in PLACEMENTS[:2] for s in SURROGATES},
    ("key_at_depth_2", SURROGATES[0]): "/edits/0/value/\ufffd",
    ("key_at_depth_2", SURROGATES[1]): "/edits/0/value/a\ufffdb",
    ("key_at_depth_2", SURROGATES[2]): "/edits/0/value/\ufffd\ufffd",
}

CASES = [
    pytest.param(placement, text, id=f"{placement}-{ascii(text)}")
    for placement in PLACEMENTS
    for text in SURROGATES
]


@pytest.fixture(scope="module")
def app(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[LocalApplication, str]]:
    """One project whose head is the SYN-001 revision; nothing below may move it."""
    application = LocalApplication.create(tmp_path_factory.mktemp("w5d") / "p", project_id="w5d")
    head = commit(application, CORPUS[NOMINAL]())
    yield application, head
    try:
        assert lifecycle_violations(application) == {}
    finally:
        application.close()


def test_the_strings_are_lone_surrogates() -> None:
    assert [len(text) for text in SURROGATES] == [1, 3, 2]
    for text in SURROGATES:
        with pytest.raises(UnicodeEncodeError):
            text.encode("utf-8")


@pytest.mark.parametrize(("placement", "text"), CASES)
def test_r4_g2_first_noncanonical_and_canonical_json(placement: str, text: str) -> None:
    document, pointer = _placed(placement, text)
    assert first_noncanonical(document) == pointer
    assert pointer.encode("utf-8").decode("utf-8") == pointer  # the pointer can be written
    with pytest.raises(CanonicalizationError):
        canonical_json(document)


@pytest.mark.parametrize(("placement", "text"), CASES)
def test_r4_g2_validate_and_both_binders(placement: str, text: str) -> None:
    document, pointer = _placed(placement, text)
    expected = f"document_not_canonical({pointer})"
    report = validate(copy.deepcopy(document))
    (check,) = report.checks
    assert (report.status, check.id, check.result, check.message, check.implicated_objects) == (
        "INVALID",
        "SCHEMA-01",
        "FAIL",
        expected,
        (pointer,),
    )
    canonical_json(report.as_document())  # the report itself can be stored and served
    assert bind_revision_or_reason(copy.deepcopy(document)) == Unbound("unsupported", expected)
    assert bind_revision_flowsheet(copy.deepcopy(document)) == Unbound("unsupported", expected)


@pytest.mark.parametrize(("placement", "text"), CASES)
def test_r4_g2_commit_change_is_rejected_typed(
    app: tuple[LocalApplication, str], placement: str, text: str
) -> None:
    application, head = app
    result = application.commit_change(
        Change(edits=(_edit(placement, text),)), head, f"w5d-{placement}-{SURROGATES.index(text)}"
    )
    assert result.status == "rejected" and result.error is not None
    assert result.error.code == "document_not_canonical"
    assert result.error.detail["pointer"] == DISPATCH_POINTER_AT_B13D556[(placement, text)]
    assert schema_errors("api-error.schema.json", result.error.as_document()) == []
    with application.store.reading() as connection:
        assert application.store.head(connection) == head


@pytest.mark.parametrize(("placement", "text"), CASES)
def test_r4_g2_dispatch_refuses_at_the_door_with_the_old_pointer(
    app: tuple[LocalApplication, str], placement: str, text: str
) -> None:
    application, head = app
    request = Change(edits=(_edit(placement, text),)).as_change_set(head, "w5d-dispatch")
    with pytest.raises(ApplicationError) as raised:
        dispatch(application, "commit_change", request)
    refused = raised.value.error.as_document()
    assert schema_errors("api-error.schema.json", refused) == []
    assert refused["code"] == "document_not_canonical"
    assert refused["detail"] == {"pointer": DISPATCH_POINTER_AT_B13D556[(placement, text)]}


def test_no_unicode_encode_error_escapes_the_canonical_entries(tmp_path: Path) -> None:
    """The docstring's equivalence, over every placement and a few shapes more: `None` from
    `first_noncanonical` exactly when `canonical_json` returns, and a refusal is always typed."""
    documents: list[object] = [_placed(p, s)[0] for p in PLACEMENTS for s in SURROGATES]
    documents += [s for s in SURROGATES] + [[s] for s in SURROGATES]
    documents += [{s: {s: s}} for s in SURROGATES] + [{"a": 1, s: 2, "b": 3} for s in SURROGATES]
    for document in documents:
        assert first_noncanonical(document) is not None
        try:
            canonical_json(document)
        except CanonicalizationError:
            continue
        raise AssertionError(f"canonical_json accepted {ascii(document)[:80]}")
