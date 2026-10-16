"""T07 ruling round 6, B1 (R6-W1): `legacy_eo` only for what it was admitted for, and the refusal
is reported.

Design note `docs/design/T07-jobs-and-bindings.md`, "Ruling round 6", B1 items 1–3, amending
R2.1, §12.1, §12.4 and R1.4.

- **The route rule.** `legacy_answers(doc, rb)`: the revision binder's refusal is
  `unsupported(specification_role_unsupported(…))` and every non-`fixed` specification is `free`.
  Any other refusal, with the legacy binder binding, is no route, and the legacy reason is
  `unsupported(legacy_route_not_admitted(<code>))`.
- **`validate()`.** When the legacy binder binds and its analysis is closed, a revision-binder
  refusal `legacy_answers` does not admit is the one reported, through the unchanged refusal path.
- **G-R6-1**: 36 `revision_eo`, 11 `legacy_eo`, 3 with no route over W0.2's 50; the `legacy_eo`
  set is W3a.3's minus every revision without a `free` specification.
- **G-R6-2** (reports): every corpus `validate()` report, without `provenance`, is byte-identical
  to `9165894`'s — pinned here by the digest of all 50, measured at `9165894` (whose `src/` is
  `d01a4d7`'s). The identity keys are the identity protocol's (`docs/T07_DECISIONS.md`, rf3a).
- **G-R6-3** is `test_t07_w3b_validation.py::test_g_r6_3_*` (G9 (a′), (e) over the V17 documents).
- **G-R7-6** (ruling round 7, which makes `legacy_answers` clause C0 of `legacy_admission`): the
  digest of every binder and reported refusal and every route over G-R6-5 (iii)'s perturbed set,
  and the moved documents' class. G-R7-1/-4 are `test_t07_r7_admission.py`. Re-measured at rf6
  (C5, review-2 S3), whose moves are listed and classed beside round 7's.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

import pytest
from conftest import REPO_ROOT
from t07_corpus import A02_FILES, CORPUS
from t07_v17_c1_documents import c1_document, schema_conformant
from t08_d1_substitution import d1_reversed

import openflowsheet.application.revision_binding as revision_binding_module
from openflowsheet.application.binding import (
    Binding,
    Unbound,
    bind_revision_or_reason,
    legacy_answers,
    refusal_code,
)
from openflowsheet.application.revision_binding import bind_revision_flowsheet
from openflowsheet.application.revision_run import NoRoute, Route, select_route
from openflowsheet.application.validation import validate
from openflowsheet.canonical import canonical_json

AT = "2026-09-27T12:00:00.000000Z"
STRUCTURAL = ("STR-01", "STR-02", "STR-03", "STR-04", "STR-05")
#: W3a.3: the corpus revisions routed to `legacy_eo` before ruling round 6.
W3A3_LEGACY = frozenset({*A02_FILES, "SYN-001-conflicting-heater-spec"})
#: G-R6-2: SHA-256 of `canonical_json({name: report minus provenance})` over W0.2's 50, measured
#: at `9165894` (rf3a, before any change). Checked with T08 D1's substitution reversed
#: (`t08_d1_substitution`); the reports as written since D1 and its STR-05 extension are
#: `CORPUS_REPORTS_SHA256_D1` (with STR-03's substitution alone it was `a8b389b2…`).
CORPUS_REPORTS_SHA256 = "5b92f32e44ac4e359827561ae15ffc1bf4dbeba983ff2846de9d7eb23115997b"
CORPUS_REPORTS_SHA256_D1 = "17856982abd04df47d38ae8db404b3231009b6434d95a4501a8c2544adf7f2a9"
#: G-R7-6 (ruling round 7; review 2, N1): SHA-256 of `scripts/t07_perturbed_refusals.py`'s mapping
#: over G-R6-5 (iii)'s 5485 perturbed documents — both binders' refusals, the reported refusal and
#: the route — measured at rf6 (C5, review-2 S3). At `86ab418` it was `67704ff5…`; at rf5 R7-W2
#: (`9297dd8`) `907a26c4…`: the binders' refusals are the post-W6 set unchanged, and the 427
#: documents whose reported refusal or route moved (`docs/t07-g-r7-6-moves.json`) are all in the
#: free class. C5 moved 11 more (`docs/t07-rf6-c5-moves.json`): route only, from `legacy_eo`.
PERTURBED_REFUSALS_SHA256 = "6fa3109ddce42c06e4bff7f8699a9c386533a64eb169d8d91847a8beea09faf1"
MOVES = REPO_ROOT / "docs" / "t07-g-r7-6-moves.json"
C5_MOVES = REPO_ROOT / "docs" / "t07-rf6-c5-moves.json"


def _roles(document: dict[str, Any]) -> set[str]:
    return {entry["role"] for entry in document.get("specifications") or ()}


# -- the rule -----------------------------------------------------------------------------------


def test_refusal_code_is_the_detail_up_to_its_first_parenthesis() -> None:
    assert refusal_code("specification_missing(S4.P)") == "specification_missing"
    assert refusal_code("a(b(c))") == "a"
    assert refusal_code("no parenthesis") == "no parenthesis"


def _with_roles(*roles: str) -> dict[str, Any]:
    return {"specifications": [{"id": f"S{i}", "role": role} for i, role in enumerate(roles)]}


ROLE = Unbound("unsupported", "specification_role_unsupported(S1)")


@pytest.mark.parametrize(
    ("document", "refusal", "answers"),
    [
        (_with_roles("fixed", "free"), ROLE, True),
        (_with_roles("free"), ROLE, True),
        (_with_roles("fixed", "free", "free"), ROLE, True),
        # A `decision` role is outside the class: the legacy binder does not read it (G-R6-7 m4).
        (_with_roles("fixed", "free", "decision"), ROLE, False),
        (_with_roles("fixed", "decision"), ROLE, False),
        (_with_roles("fixed"), ROLE, False),
        (
            _with_roles("fixed", "free"),
            Unbound("incomplete", "specification_role_unsupported(S1)"),
            False,
        ),
        (_with_roles("fixed", "free"), Unbound("incomplete", "specification_missing(S4.P)"), False),
        (
            _with_roles("fixed", "free"),
            Unbound("unsupported", "port_phase_unsupported(U.o)"),
            False,
        ),
        (
            _with_roles("fixed", "free"),
            Unbound("unsupported", "specification_unconsumed(X)"),
            False,
        ),
    ],
)
def test_legacy_answers(document: dict[str, Any], refusal: Unbound, answers: bool) -> None:
    assert legacy_answers(document, refusal) is answers


# -- G-R6-1 -------------------------------------------------------------------------------------


def test_g_r6_1_routes_over_the_corpus() -> None:
    routes = {name: select_route(CORPUS[name]()) for name in CORPUS}
    paths = {
        name: route.solve_path if isinstance(route, Route) else None
        for name, route in routes.items()
    }
    counts = {path: list(paths.values()).count(path) for path in set(paths.values())}
    assert counts == {"revision_eo": 36, "legacy_eo": 11, None: 3}
    legacy = {name for name, path in paths.items() if path == "legacy_eo"}
    assert legacy == {name for name in W3A3_LEGACY if "free" in _roles(CORPUS[name]())}
    assert {name for name, path in paths.items() if path is None} == {
        "SYN-001-T06-STR02",
        "SYN-001-T06-STR06",
        "SYN-001-conflicting-heater-spec",
    }
    moved = routes["SYN-001-conflicting-heater-spec"]
    assert isinstance(moved, NoRoute)
    assert isinstance(bind_revision_or_reason(CORPUS["SYN-001-conflicting-heater-spec"]()), Binding)
    assert moved.legacy == Unbound(
        "unsupported", "legacy_route_not_admitted(specification_unconsumed)"
    )
    # It is `INVALID` before and after: its legacy finding is not closed, and stands.
    assert validate(CORPUS["SYN-001-conflicting-heater-spec"]()).status == "INVALID"


# -- G-R6-2 (reports) ---------------------------------------------------------------------------


def corpus_reports_sha256(*, reverse_d1: bool = False) -> str:
    reports = {}
    for name in sorted(CORPUS):
        document = validate(CORPUS[name](), now=lambda: AT).as_document()
        del document["provenance"]
        if reverse_d1:
            document["checks"] = d1_reversed(document["checks"])
        reports[name] = document
    return hashlib.sha256(canonical_json(reports)).hexdigest()


def test_g_r6_2_every_corpus_report_is_9165894s() -> None:
    assert corpus_reports_sha256(reverse_d1=True) == CORPUS_REPORTS_SHA256
    assert corpus_reports_sha256() == CORPUS_REPORTS_SHA256_D1


# -- G-R7-6 -------------------------------------------------------------------------------------


def _perturbed() -> Any:
    import importlib.util

    path = REPO_ROOT / "scripts" / "t07_perturbed_refusals.py"
    spec = importlib.util.spec_from_file_location("t07_perturbed_refusals", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_g_r7_6_the_perturbed_refusals_are_rf6s() -> None:
    perturbed = _perturbed()
    refusals = perturbed.perturbed_refusals()
    assert len(refusals) == 5485
    assert perturbed.digest(refusals) == PERTURBED_REFUSALS_SHA256


def test_g_r7_6_every_moved_document_is_in_the_free_class() -> None:
    """R7-O1: the documents G-R7-6 lists as moved are each in round 6's class at the revision
    binder's refusal, which ruling round 7 does not change."""
    moved = json.loads(MOVES.read_text(encoding="utf-8"))
    assert len(moved) == 427
    documents = dict(_perturbed().documents())
    outside = []
    for name in moved:
        refusal = bind_revision_flowsheet(copy.deepcopy(documents[name]))
        if not (isinstance(refusal, Unbound) and legacy_answers(documents[name], refusal)):
            outside.append(name)
    assert outside == []


def test_g_r7_6_c5_moves_only_routes_whose_binding_is_not_one_pair() -> None:
    """rf6 (C5, review-2 S3): each document C5 moved was on `legacy_eo` and now has no route, with
    `specification_pairing_unsupported`; its reported refusal did not move (every one is a legacy
    finding that is not closed, which `validate()` reports as it did); and its legacy binding does
    not pair one freed coordinate with one target."""
    moved = json.loads(C5_MOVES.read_text(encoding="utf-8"))
    assert len(moved) == 11
    documents = dict(_perturbed().documents())
    for name, move in moved.items():
        assert move["old"]["route"] == "legacy_eo", name
        assert move["new"]["reported"] == move["old"]["reported"], name
        route = move["new"]["route"]
        assert route.startswith("unsupported(specification_pairing_unsupported("), name
        legacy = bind_revision_or_reason(copy.deepcopy(documents[name]))
        assert isinstance(legacy, Binding)
        assert (len(legacy.freed), len(legacy.promoted)) != (1, 1), name


# -- validate() reports the refusal (item 2) ----------------------------------------------------


def test_t02_2s_document_reports_the_missing_drum_pressure() -> None:
    """B1 on the T02-2 agent's `rev-000002` (schema-conformant; see `t07_v17_c1_documents`): the
    legacy binder binds and its analysis is closed; the revision binder's `specification_missing
    (S4.P)` is not admitted, so it is reported and the revision is `DRAFT`, not READY."""
    document = schema_conformant(c1_document("T02-2", "rev-000002"))
    assert isinstance(bind_revision_or_reason(copy.deepcopy(document)), Binding)
    report = validate(document, now=lambda: AT)
    assert report.status == "DRAFT"
    checks = {check.id: check for check in report.checks}
    for check_id in STRUCTURAL:
        assert checks[check_id].result == "NOT_RUN"
        assert "specification_missing(S4.P)" in checks[check_id].message
    assert report.structural_counts is None
    assert report.structural_counts_absent_reason == (
        "the revision is incomplete: specification_missing(S4.P)"
    )


def test_t02_3s_rev3_reports_the_refused_heater_phase() -> None:
    report = validate(schema_conformant(c1_document("T02-3", "rev-000003")), now=lambda: AT)
    assert report.status == "DRAFT"
    assert "port_phase_unsupported(U-HEAT.outlet)" in (report.structural_counts_absent_reason or "")


def test_the_c1_t02_documents_as_committed_fail_schema_01() -> None:
    """As committed, the T02-2 and T02-3 documents are `INVALID` on `SCHEMA-01` (ruling round 5,
    S3, after the campaign) at `9165894` already; nothing here moved that."""
    for run, revision in (
        ("T02-2", "rev-000002"),
        ("T02-3", "rev-000002"),
        ("T02-3", "rev-000003"),
    ):
        report = validate(c1_document(run, revision), now=lambda: AT)
        assert report.status == "INVALID"
        assert [check.id for check in report.checks if check.result == "FAIL"] == ["SCHEMA-01"]


@pytest.mark.parametrize(
    ("kind", "status", "failed"),
    [
        ("incomplete", "DRAFT", set()),
        ("unsupported", "DRAFT", set()),
        ("conflict", "INVALID", {"STR-04"}),
        ("inadmissible", "INVALID", {"CAP-01"}),
    ],
)
def test_a_closed_legacy_analysis_reports_a_refusal_not_admitted(
    monkeypatch: pytest.MonkeyPatch, kind: str, status: str, failed: set[str]
) -> None:
    """Item 2: the existing refusal path, unchanged, for each kind."""
    refusal = Unbound(kind, "revision-detail(X)", ("revision-object",))  # type: ignore[arg-type]
    monkeypatch.setattr(
        revision_binding_module, "bind_revision_flowsheet", lambda document, **_: refusal
    )
    report = validate(CORPUS["SYN-001-nominal"](), now=lambda: AT)
    assert report.status == status
    assert {check.id for check in report.checks if check.result == "FAIL"} == failed
    assert "revision-detail(X)" in (report.structural_counts_absent_reason or "")


def test_a_closed_legacy_analysis_stands_when_the_legacy_route_is_admitted() -> None:
    """The A02 files: the revision binder refuses `role: free`, `legacy_answers` holds, and the
    legacy report stands (READY)."""
    for name in A02_FILES:
        assert validate(CORPUS[name](), now=lambda: AT).status == "READY_FOR_SIMULATION", name
