"""T07 W3f: the design note's ruling round 3, Q2 — `validate()`'s tie between two refusals of equal
rank is split by kind (`incomplete` → the legacy binder's, `unsupported` → the revision binder's).

Design note `docs/design/T07-jobs-and-bindings.md`, "Ruling round 3", Q2-A1…A5. Q2-A5's
before/after comparison over the 50 and the identity keys are W3f's measurement
(`docs/t07-measurements.md`); here, that the one changed condition meets no corpus revision.
"""

from __future__ import annotations

from typing import Any

from t07_corpus import CORPUS

from openflowsheet.application.binding import Binding, Unbound, bind_revision_or_reason
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.application.validation import validate

STRUCTURAL = ("STR-01", "STR-02", "STR-03", "STR-04", "STR-05")


def _reason(document: dict[str, Any]) -> tuple[str, str]:
    report = validate(document)
    return report.status, report.structural_counts_absent_reason or ""


def _refusals(document: dict[str, Any]) -> tuple[str, str]:
    legacy = bind_revision_or_reason(document)
    revision = bind_revision_flowsheet(document)
    assert isinstance(legacy, Unbound) and isinstance(revision, Unbound)
    return legacy.kind, revision.kind


def test_q2_a1_str02_keeps_the_legacy_refusal_on_its_incomplete_tie() -> None:
    document = CORPUS["SYN-001-T06-STR02"]()
    assert _refusals(document) == ("incomplete", "incomplete")
    report = validate(document)
    assert report.status == "DRAFT"
    assert "heater outlet temperature" in (report.structural_counts_absent_reason or "")
    checks = [check for check in report.checks if check.id in STRUCTURAL]
    assert [check.result for check in checks] == ["NOT_RUN"] * 5
    assert [list(check.implicated_objects) for check in checks] == [
        ["heater outlet temperature"]
    ] * 5


def test_q2_a2_an_unsupported_tie_reports_the_revision_binders_refusal() -> None:
    document = CORPUS["SYN-001-T06-THM01"]()
    (sink,) = [instance for instance in document["instances"] if instance["id"] == "U-SINK-L"]
    sink["model"]["id"] = "syn001.nonexistent"
    assert _refusals(document) == ("unsupported", "unsupported")
    status, reason = _reason(document)
    assert status == "DRAFT"
    assert "model_unsupported(syn001.nonexistent)" in reason
    assert "SYN-001 flowsheet's topology" not in reason


def test_q2_a3_the_same_tie_on_syn001s_own_topology() -> None:
    document = CORPUS["SYN-001-nominal"]()
    for instance in document["instances"]:
        instance["model"]["id"] = "unknown.model"
    assert _refusals(document) == ("unsupported", "unsupported")
    status, reason = _reason(document)
    assert status == "DRAFT"
    assert "cannot be analysed" in reason
    assert "model_unsupported(unknown.model)" in reason


def test_q2_a4_t01s_incomplete_tie_still_names_the_feed_temperature() -> None:
    document = CORPUS["SYN-001-nominal"]()
    document["specifications"] = [
        entry for entry in document["specifications"] if entry["id"] != "SPEC-feed-T"
    ]
    assert _refusals(document) == ("incomplete", "incomplete")
    status, reason = _reason(document)
    assert status == "DRAFT"
    assert "feed temperature" in reason


def test_q2_a5_no_corpus_revision_is_an_unsupported_tie() -> None:
    """The ruling's one code change acts only where both binders refuse `unsupported`, and no
    revision of W0.2's 50 does, so no corpus report can move (the before/after comparison over
    all 50 is W3f's measurement in `docs/t07-measurements.md`)."""
    assert len(CORPUS) == 50
    ties = []
    for name, build in CORPUS.items():
        legacy = bind_revision_or_reason(build())
        if isinstance(legacy, Binding) or legacy.kind == "conflict":
            continue
        revision = bind_revision_flowsheet(build())
        if not isinstance(revision, RevisionBinding) and revision.kind == legacy.kind:
            ties.append((name, legacy.kind))
    assert ties == [("SYN-001-T06-STR02", "incomplete")]
