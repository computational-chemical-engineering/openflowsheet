"""T07 W3b: `validate()` for revision-built flowsheets (T06 F5) and its provenance (gate G9, R3).

Design note `docs/design/T07-jobs-and-bindings.md` §12.4 as amended by ruling round 1 R1 (the
trigger, the precedence of refusals, G9 restated) and R3 (provenance in the frozen
`validation-report` shape); ADR 0020 D5.

- **The fallback.** The legacy binder stays first; on its `unsupported` or `incomplete` the
  revision binder's flowsheet is analysed with `plan_revision`'s inputs; a legacy `conflict` never
  falls back. When both refuse, the higher-ranked refusal is reported. The **tie** is split by
  kind (ruling round 3, Q2, amending R1.2): an `incomplete` tie reports the legacy binder's
  refusal (the corpus's one tie, STR-02, and T06 A04), an `unsupported` tie the revision
  binder's. Q2-A1…A5 are in `test_t07_w3f_tie_by_kind.py`.
- **G9** (R1.4 (a)–(d), and (a′), (e) of ruling round 6, B1) is judged against `select_route`'s
  route and its plan builder's analysis, over W0.2's 50 revisions, ruling round 6's V17
  documents (G-R6-3) and ruling round 7's m1–m16 (G-R7-5); (e) also asks `legacy_admission`.
- **The moves.** Exactly W0.4's 27 statuses plus NET-02 go `DRAFT` → `READY_FOR_SIMULATION` (R1,
  "What moves"); nothing else in any report moves but `provenance`. The identity keys are proved
  unmoved by the identity protocol (`docs/t07-measurements.md`, W3b).
- **R3.** Every report the code emits validates against `schemas/validation-report.schema.json`.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml
from t07_corpus import A02_FILES, CORPUS
from t07_r7_documents import MUTATIONS, mutated
from t07_v17_c1_documents import g_r6_3_documents
from test_t07_w2d_noncanonical import NONCANONICAL, REVISIONS, _numeric_leaves, _with

import openflowsheet.application.binding as binding_module
import openflowsheet.application.revision_binding as revision_binding_module
from openflowsheet.application.binding import (
    Binding,
    Unbound,
    bind_revision_or_reason,
    legacy_admission,
    legacy_answers,
)
from openflowsheet.application.policies import resolve_policy
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.application.revision_run import NoRoute, Route, legacy_plan, select_route
from openflowsheet.application.revisions import Revision
from openflowsheet.application.transactions import Application, ChangeSet, Edit
from openflowsheet.application.types import schema_errors
from openflowsheet.application.validation import (
    FALLBACK_PRODUCED_BY,
    MISSING_REVISION_ID,
    PRODUCED_BY,
    REQUIRED_KEYS,
    SCHEMA_ONLY_PRODUCED_BY,
    ValidationReport,
    utc_timestamp,
    validate,
)
from openflowsheet.graph.analysis import analyse
from openflowsheet.orchestrator.execution import ExecutionPlan, declaration_identity
from openflowsheet.orchestrator.revision import plan_revision

SCHEMA = "validation-report.schema.json"
STRUCTURAL = ("STR-01", "STR-02", "STR-03", "STR-04", "STR-05")
AT = "2026-09-27T12:00:00.000000Z"

#: R1 "What moves": W0.4's 27 revisions and NET-02, `DRAFT` → `READY_FOR_SIMULATION`.
MOVED_TO_READY = frozenset(
    {
        "T05b:DZ-3",
        "T05b:DZ-7",
        "T05b:NP-1",
        "T05b:SC-1",
        "T05b:SC-2",
        "T05b:SC-3",
        "SYN-001-T06-NET02",
        "SYN-001-T06-NET03",
        "SYN-001-T06-NET06",
        "SYN-001-T06-NET10",
        "SYN-001-T06-NET11",
        "SYN-001-T06-PC2",
        *(f"SYN-001-T06-REF0{index}" for index in range(1, 8)),
        "SYN-001-T06-STA02",
        "SYN-001-T06-STA04",
        "SYN-001-T06-THM01",
        "SYN-001-T06-THM02",
        "SYN-001-T06-THM10",
        "SYN-001-UL-C1",
        "SYN-001-UL-C2",
        "SYN-001-UL-C3",
        "SYN-001-UL-C3X",
    }
)
#: W0.4: the revisions that were already `READY_FOR_SIMULATION` (the legacy binder binds them).
ALREADY_READY = frozenset(
    {
        *A02_FILES,
        "SYN-001-T06-NET09",
        "SYN-001-T06-STA03-degC",
        "SYN-001-T06-STA03-kgs",
        "SYN-001-all-liquid-310K",
        "SYN-001-all-vapor-420K",
        "SYN-001-high-recycle",
        "SYN-001-nominal",
        "SYN-001-once-through",
    }
)
#: W0.4 / R1: the statuses that do not move.
NOT_READY = {
    "SYN-001-T06-STR02": "DRAFT",
    "SYN-001-T06-STR06": "INVALID",
    "SYN-001-conflicting-heater-spec": "INVALID",
}


def _report(name: str) -> ValidationReport:
    return validate(CORPUS[name](), now=lambda: AT)


def _core(report: ValidationReport) -> dict[str, Any]:
    document = report.as_document()
    del document["provenance"]
    return document


# -- the moves (R1) -----------------------------------------------------------------------------


def test_the_statuses_are_r1s() -> None:
    assert len(MOVED_TO_READY) == 28 and len(ALREADY_READY) == 19
    assert set(CORPUS) == MOVED_TO_READY | ALREADY_READY | set(NOT_READY)
    statuses = {name: _report(name).status for name in CORPUS}
    assert {name for name, status in statuses.items() if status == "READY_FOR_SIMULATION"} == (
        MOVED_TO_READY | ALREADY_READY
    )
    assert {name: statuses[name] for name in NOT_READY} == NOT_READY


def test_the_str02_and_str06_reports_are_the_registered_ones() -> None:
    """STR-02 keeps the legacy binder's refusal on its `incomplete` tie (ruling round 3, Q2):
    `DRAFT`, every structural check `NOT_RUN`, the missing specification named. STR-06's legacy
    `conflict` never falls back: `STR-04 FAIL`, `INVALID`."""
    str02 = _report("SYN-001-T06-STR02")
    assert str02.structural_counts_absent_reason == (
        "the revision is incomplete: a specification the flowsheet needs is not declared: heater "
        "outlet temperature"
    )
    assert [c.result for c in str02.checks if c.id in STRUCTURAL] == ["NOT_RUN"] * 5
    assert str02.provenance["produced_by"] == PRODUCED_BY
    str06 = _report("SYN-001-T06-STR06")
    results = {check.id: check.result for check in str06.checks}
    assert results["STR-04"] == "FAIL"
    assert str06.provenance["produced_by"] == PRODUCED_BY


@pytest.mark.parametrize("name", sorted(CORPUS))
def test_provenance_names_the_binder_that_was_analysed(name: str) -> None:
    report = _report(name)
    legacy = isinstance(bind_revision_or_reason(CORPUS[name]()), Binding)
    fallback = not legacy and isinstance(bind_revision_flowsheet(CORPUS[name]()), RevisionBinding)
    assert report.provenance == {
        "produced_by": PRODUCED_BY + (FALLBACK_PRODUCED_BY if fallback else ""),
        "timestamp": AT,
    }


# -- the trigger and the precedence (R1.1, R1.2) ------------------------------------------------


def _patched(
    monkeypatch: pytest.MonkeyPatch, legacy: Unbound | None, revision: Unbound | None
) -> ValidationReport:
    """`validate(SYN-001-T06-NET03)` with either binder's answer replaced by a refusal."""
    if legacy is not None:
        monkeypatch.setattr(binding_module, "bind_revision_or_reason", lambda document: legacy)
    if revision is not None:
        monkeypatch.setattr(
            revision_binding_module, "bind_revision_flowsheet", lambda document, **_: revision
        )
    return validate(CORPUS["SYN-001-T06-NET03"](), now=lambda: AT)


@pytest.mark.parametrize(
    ("legacy_kind", "revision_kind", "reported"),
    [
        ("unsupported", "unsupported", "revision"),  # a tie: ruling round 3, Q2
        ("unsupported", "incomplete", "revision"),
        ("unsupported", "conflict", "revision"),
        ("incomplete", "unsupported", "legacy"),
        ("incomplete", "incomplete", "legacy"),  # a tie: ruling round 3, Q2 (STR-02's)
        ("incomplete", "conflict", "revision"),
    ],
)
def test_when_both_binders_refuse_the_higher_ranked_refusal_is_reported(
    monkeypatch: pytest.MonkeyPatch, legacy_kind: str, revision_kind: str, reported: str
) -> None:
    legacy = Unbound(legacy_kind, "legacy-detail", ("legacy-object",))  # type: ignore[arg-type]
    revision = Unbound(revision_kind, "revision-detail", ("revision-object",))  # type: ignore[arg-type]
    report = _patched(monkeypatch, legacy, revision)
    detail = f"{reported}-detail"
    checks = {check.id: check for check in report.checks}
    assert detail in (report.structural_counts_absent_reason or "")
    kind = legacy_kind if reported == "legacy" else revision_kind
    if kind == "conflict":
        assert report.status == "INVALID"
        assert checks["STR-04"].result == "FAIL"
        assert checks["STR-04"].implicated_objects == (f"{reported}-object",)
    else:
        assert report.status == "DRAFT"
        assert [checks[check_id].result for check_id in STRUCTURAL] == ["NOT_RUN"] * 5
    assert report.provenance["produced_by"] == PRODUCED_BY


@pytest.mark.parametrize("kind", ["unsupported", "incomplete"])
def test_a_legacy_unsupported_or_incomplete_falls_back(
    monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    report = _patched(monkeypatch, Unbound(kind, "legacy-detail"), None)  # type: ignore[arg-type]
    assert report.status == "READY_FOR_SIMULATION"
    assert report.provenance["produced_by"] == PRODUCED_BY + FALLBACK_PRODUCED_BY


def test_a_legacy_conflict_never_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []

    def spy(document: Any) -> Any:
        called.append("revision binder")
        raise AssertionError("the revision binder must not be asked after a legacy conflict")

    monkeypatch.setattr(revision_binding_module, "bind_revision_flowsheet", spy)
    report = _patched(monkeypatch, Unbound("conflict", "legacy-detail", ("x",)), None)
    assert report.status == "INVALID" and called == []


def test_fallback_labels_implicated_columns_with_their_specifications(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """§12.4: on the fallback, an implicated column a specification pins is named by that
    specification's id, and any other object is kept; the labels do not change the finding. No
    corpus revision's fallback analysis implicates a column, so the check list is replaced."""
    import openflowsheet.application.validation as validation_module
    from openflowsheet.application.validation import Check
    from openflowsheet.models.revision_flowsheet import pin_specifications

    document = CORPUS["SYN-001-T06-NET03"]()
    pins = pin_specifications(document)
    column = sorted(pins)[0]
    original = validation_module.structural_checks

    def with_column(report: Any) -> list[Check]:
        checks = original(report)
        return [
            Check(**{**vars(checks[0]), "implicated_objects": (column, "not-a-column")}),
            *checks[1:],
        ]

    monkeypatch.setattr(validation_module, "structural_checks", with_column)
    report = validate(document, now=lambda: AT)
    (str01,) = [check for check in report.checks if check.id == "STR-01"]
    assert str01.implicated_objects == (*pins[column], "not-a-column")
    assert report.status == "READY_FOR_SIMULATION"


# -- G9 (R1.4) ----------------------------------------------------------------------------------


def _route_report(route: Route) -> Any:
    """T01's analysis of the route's formulation, with its plan builder's inputs."""
    binding = route.binding
    model_version, constants = declaration_identity(binding.spec)
    return analyse(
        binding.spec,
        binding.graph,
        model_version=model_version,
        constants_sha256=constants,
        specification_ids=binding.specification_ids if route.solve_path == "legacy_eo" else {},
        row_units=binding.row_units,
    )


def _finding(report: ValidationReport) -> str:
    (str01,) = [check for check in report.checks if check.id == "STR-01"]
    return str01.message.split(":", 1)[0]


def _g9(name: str, factory: Callable[[], dict[str, Any]] | None = None) -> tuple[int, int] | None:
    """G9 (a)–(e) for one revision (ruling round 6, B1 adds (a′) and (e)); the (Δequations,
    Δfree) offset where both binders bind. `factory` defaults to the corpus revision `name`."""
    factory = factory or CORPUS[name]
    document = factory()
    report = validate(copy.deepcopy(document), now=lambda: AT)
    route = select_route(document)
    ready = report.status == "READY_FOR_SIMULATION"

    # (d) no route ⇒ not READY.
    if isinstance(route, NoRoute):
        assert not ready
        return None
    assert isinstance(route, Route)

    # (e) a route of `legacy_eo` ⇒ `legacy_answers(doc, <revision refusal>)`, and (ruling round
    # 7) `legacy_admission` admits it.
    if route.solve_path == "legacy_eo":
        refusal = bind_revision_flowsheet(factory())
        assert isinstance(refusal, Unbound), name
        assert legacy_answers(factory(), refusal), name
        assert legacy_admission(factory(), refusal, route.binding) is None, name

    # (a) READY ⇒ the route's plan builder returns an ExecutionPlan, no structural refusal;
    # (a′) on `legacy_eo`, with exactly one `solve_eo` step.
    if ready:
        policy = resolve_policy("default", route.solve_path)
        assert policy is not None
        if route.solve_path == "revision_eo":
            plan, _ = plan_revision(route.binding, policy)
        else:
            plan, _ = legacy_plan(route.binding, policy)
            assert [step.kind for step in plan.steps].count("solve_eo") == 1, name
        assert isinstance(plan, ExecutionPlan), name

    # (b) every check before the structural stage passes ⇒ a structural finding, the route's.
    before = [check for check in report.checks if check.stage != "structural_analysis"]
    if not all(check.result == "PASS" for check in before):
        return None
    route_report = _route_report(route)
    assert _finding(report) == route_report.finding, name
    # "STR-01…05 not NOT_RUN": the analysis ran. T01 §12.3 leaves STR-05 (the block-triangular
    # form) `NOT_RUN` on a system that is not structurally closed, with its own reason; that is a
    # finding, not an analysis that did not run.
    not_run = [
        check for check in report.checks if check.id in STRUCTURAL and check.result == "NOT_RUN"
    ]
    if route_report.finding == "STRUCTURALLY_CLOSED":
        assert not_run == [], name
    else:
        assert [check.id for check in not_run] == ["STR-05"], name
        assert "structurally closed system" in not_run[0].message, name

    # (c) counts: equal where validate analysed the route's own binder; where both bind (it
    # analysed the legacy declaration), equal structural deficiencies.
    counts, theirs = report.structural_counts, route_report.structural_counts
    assert counts is not None and theirs is not None
    both = route.solve_path == "revision_eo" and isinstance(
        bind_revision_or_reason(factory()), Binding
    )
    if not both:
        assert dict(counts) == dict(theirs), name
        return None
    assert (
        counts["equations"] - counts["matched"],
        counts["free_variables"] - counts["matched"],
    ) == (
        theirs["equations"] - theirs["matched"],
        theirs["free_variables"] - theirs["matched"],
    ), name
    return (
        theirs["equations"] - counts["equations"],
        theirs["free_variables"] - counts["free_variables"],
    )


@pytest.mark.parametrize("name", sorted(CORPUS))
def test_g9_validate_agrees_with_the_routes_plan_builder(name: str) -> None:
    _g9(name)


#: G-R6-3: ruling round 6's V17 documents, keyed `<run>/<revision>[/<form>]`.
V17_DOCUMENTS = g_r6_3_documents()


@pytest.mark.parametrize("key", sorted(V17_DOCUMENTS))
def test_g_r6_3_g9_holds_on_the_v17_documents(key: str) -> None:
    _g9(key, lambda: copy.deepcopy(V17_DOCUMENTS[key]))


@pytest.mark.parametrize("name", sorted(MUTATIONS, key=lambda name: int(name[1:])))
def test_g_r7_5_g9_holds_on_the_round_7_documents(name: str) -> None:
    _g9(name, lambda: mutated(name))


#: G9 (c): the offsets of the route's formulation over the legacy declaration where both binders
#: bind, measured (`docs/t07-measurements.md`, W3b). NET-09 is W0.4's (+1, +1).
BOTH_BIND_OFFSETS: dict[str, tuple[int, int]] = {
    "SYN-001-T06-NET09": (1, 1),
    "SYN-001-T06-STA03-degC": (0, 0),
    "SYN-001-T06-STA03-kgs": (0, 0),
    "SYN-001-all-liquid-310K": (0, 0),
    "SYN-001-all-vapor-420K": (0, 0),
    "SYN-001-high-recycle": (0, 0),
    "SYN-001-nominal": (0, 0),
    "SYN-001-once-through": (0, 0),
}


def test_g9_the_offsets_where_both_binders_bind() -> None:
    offsets = {name: _g9(name) for name in sorted(CORPUS)}
    measured = {name: offset for name, offset in offsets.items() if offset is not None}
    assert measured["SYN-001-T06-NET09"] == (1, 1)
    assert measured == BOTH_BIND_OFFSETS


# -- R3: every report the code emits validates against the frozen schema -----------------------


@pytest.mark.parametrize("task", ["simulation", "optimization"])
def test_r3_every_corpus_report_validates(task: str) -> None:
    """T08 review 2, Ruling 1 (U05) moved the `optimization` case: no report is built for that
    task, so every corpus document is refused `unsupported` instead."""
    from openflowsheet.application.contract import ApplicationError

    for name, build in CORPUS.items():
        if task == "optimization":
            with pytest.raises(ApplicationError) as refused:
                validate(build(), task)
            assert (refused.value.code, refused.value.error.message) == (
                "unsupported",
                "task_unsupported(optimization)",
            ), name
            continue
        report = validate(build(), task)  # type: ignore[arg-type]
        assert schema_errors(SCHEMA, report.as_document()) == [], name


@pytest.mark.parametrize("key", REQUIRED_KEYS)
def test_r3_every_missing_key_report_validates(key: str) -> None:
    document = CORPUS["SYN-001-nominal"]()
    del document[key]
    report = validate(document)
    assert report.status == "INVALID"
    assert schema_errors(SCHEMA, report.as_document()) == []
    assert report.provenance["produced_by"] == SCHEMA_ONLY_PRODUCED_BY
    if key == "revision_id":
        assert report.revision_id == MISSING_REVISION_ID


@pytest.mark.parametrize(
    ("value", "expected"), [("", MISSING_REVISION_ID), (None, MISSING_REVISION_ID), (7, "7")]
)
def test_r3_revision_id_is_the_documents_or_missing(value: Any, expected: str) -> None:
    document = CORPUS["SYN-001-nominal"]()
    document["revision_id"] = value
    report = validate(document)
    assert report.revision_id == expected
    assert schema_errors(SCHEMA, report.as_document()) == []


def test_r3_every_noncanonical_report_validates() -> None:
    """G10's mutations: every numeric leaf of the five revisions × the non-canonical numbers."""
    count = 0
    for path in REVISIONS:
        document = load_yaml(REPO_ROOT / path)
        for leaf in _numeric_leaves(document):
            for value in NONCANONICAL:
                report = validate(_with(document, leaf, value))
                assert report.status == "INVALID"
                assert schema_errors(SCHEMA, report.as_document()) == [], (path, leaf)
                assert report.provenance["produced_by"] == SCHEMA_ONLY_PRODUCED_BY
                count += 1
    assert count > 1000


def test_r3_every_transaction_result_validation_validates() -> None:
    """K06's façade: the report a committed, and a replayed, transaction carries."""
    revision = CORPUS["SYN-001-nominal"]()
    app = Application()
    app.store.put(Revision(revision_id=revision["revision_id"], document=revision))
    results = []
    for key, name, edits in (
        ("k1", "r1", (Edit("set", ("description",), "one"),)),
        ("k2", "r2", (Edit("set", ("specifications",), []),)),
        ("k3", "r3", (Edit("remove", ("provenance",)),)),
    ):
        change = ChangeSet(
            edits=edits,
            expected_revision=app.store.head,
            idempotency_key=key,
            new_revision_id=name,
        )
        results += [app.commit(change), app.commit(change)]
    assert [result.status for result in results] == ["committed", "replayed"] * 3
    for result in results:
        assert result.validation is not None
        assert schema_errors(SCHEMA, result.validation.as_document()) == []


# -- R3: the clock and what equality ignores ----------------------------------------------------


def test_r3_the_timestamp_is_read_once_from_the_injected_clock() -> None:
    reads: list[str] = []

    def clock() -> str:
        reads.append(AT)
        return AT

    report = validate(CORPUS["SYN-001-T06-NET03"](), now=clock)
    assert reads == [AT] and report.provenance["timestamp"] == AT
    assert schema_errors("job.schema.json#/$defs/timestamp", utc_timestamp()) == []


def test_r3_equality_ignores_provenance() -> None:
    """R3: status and every check are a pure function of (document, task); two reports of one
    revision at two times are equal, and byte-identical without `provenance`."""
    first = validate(CORPUS["SYN-001-T06-NET03"](), now=lambda: AT)
    second = validate(CORPUS["SYN-001-T06-NET03"](), now=lambda: "2030-01-01T00:00:00.000000Z")
    assert first == second
    assert first.provenance != second.provenance
    assert _core(first) == _core(second)


def test_g8s_eligible_revisions_are_exactly_the_ready_ones() -> None:
    """G8 solves "every eligible corpus revision": W3a's list is exactly the `READY` set."""
    from test_t07_w3a_revision_runs import ELIGIBLE

    assert set(ELIGIBLE) == MOVED_TO_READY | ALREADY_READY
