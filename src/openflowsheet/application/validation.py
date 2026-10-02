"""Task validation: `DRAFT`, `READY_FOR_SIMULATION`, `INVALID`. K06, blueprint §4.3 and D16.

The sentence that shapes this module is §4.3's: **"These are validation results tied to a
revision and task, not editable badges."** So there is no setter. A status is computed from a
revision and a task every time it is asked for, and a caller that wants a different answer has
to change the revision.

And §4.3's other one: "Physical checks distinguish fixed specifications, tentative initial
guesses, and solved states: a poor guess is not proof that the specified process is
impossible." Nothing here fails a revision for being hard to solve.

**What this validator does not do.** Blueprint §4.3 lists matching and Dulmage–Mendelsohn
decomposition as the structural analysis; that is T01's and does not exist. So the closure
check here is a *count* — variables against equations after fixed-variable elimination — and
`structural_counts_absent_reason` says so when it cannot even do that. A count is not a
matching: it cannot see a structurally singular system whose totals happen to agree, and it
says as much rather than implying otherwise.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, Final, Literal

from openflowsheet.canonical import first_noncanonical

if TYPE_CHECKING:
    from openflowsheet.application.binding import Unbound
    from openflowsheet.application.contract import ApplicationError

Task = Literal["simulation", "optimization"]
ValidationStatus = Literal["DRAFT", "READY_FOR_SIMULATION", "READY_FOR_OPTIMIZATION", "INVALID"]

#: The keys a revision must carry to be a revision at all (schema `required`).
REQUIRED_KEYS: Final[tuple[str, ...]] = (
    "schema_version",
    "revision_id",
    "component_set",
    "instances",
    "connections",
    "specifications",
    "provenance",
)


#: T07 ruling round 1 R3: `provenance.produced_by` of each path, in the frozen schema's shape.
PRODUCED_BY: Final[str] = "K06 validator; T01 declaration-traced incidence v1, increment 1"
#: Appended when the structural stage analysed the revision binder's flowsheet (§12.4, R1).
FALLBACK_PRODUCED_BY: Final[str] = "; revision binder fallback (T07)"
#: The early returns, which stop before any analysis.
SCHEMA_ONLY_PRODUCED_BY: Final[str] = "K06 validator; schema only"
#: R3: the report's `revision_id` when the document carries none (SCHEMA-01's FAIL names it).
MISSING_REVISION_ID: Final[str] = "(missing)"


def utc_timestamp() -> str:
    """T07 design note §5.1's timestamp: RFC 3339 UTC with microseconds. Never R0."""
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _revision_id(document: Mapping[str, Any]) -> str:
    """R3: the document's `revision_id` when it is non-empty (its `str()` if it is not a
    string), else `"(missing)"` — the frozen schema requires a non-empty string."""
    value = document.get("revision_id")
    text = "" if value is None else str(value)
    return text or MISSING_REVISION_ID


#: Blueprint §4.3's stage order, as the frozen `validation-report.schema.json` enumerates it.
Stage = Literal[
    "schema",
    "dimensions",
    "graph_connectivity",
    "component_reference_compatibility",
    "conditional_classification",
    "capability",
    "structural_analysis",
]
Result = Literal["PASS", "FAIL", "WARN", "NOT_RUN"]
#: Blueprint §4.3: a rank or conflict search must label which of these it is. T01 emits only
#: `structural` and assertion A23 holds it to that; the other two belong to K04 and T06.
EvidenceClass = Literal["structural", "local_numerical", "verified_minimal_subset"]


@dataclass(frozen=True)
class Check:
    """One validation check, in the vocabulary the frozen schema fixes.

    `result` distinguishes a check that ran and failed (`FAIL`) from one that could not run
    (`NOT_RUN`) — the distinction K06 carried as `scope` and the schema carries here. Both are
    kept: `passed` and `scope` remain as derived properties because the CLI and the evidence
    generators read them, and because "did it pass" and "did it run" are different questions.
    """

    id: str
    stage: Stage
    result: Result
    message: str
    implicated_objects: tuple[str, ...] = ()
    evidence_class: EvidenceClass = "structural"

    @property
    def passed(self) -> bool:
        return self.result == "PASS"

    @property
    def scope(self) -> Literal["evaluated", "unsupported"]:
        return "unsupported" if self.result == "NOT_RUN" else "evaluated"

    @property
    def detail(self) -> str:
        return self.message

    def as_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "stage": self.stage,
            "result": self.result,
            "message": self.message,
            "implicated_objects": list(self.implicated_objects),
            "evidence_class": self.evidence_class,
        }


@dataclass(frozen=True)
class ValidationReport:
    """Tied to a revision and a task. Recomputed on demand, never stored as a badge."""

    revision_id: str
    task: Task
    status: ValidationStatus
    checks: tuple[Check, ...]
    structural_counts: Mapping[str, int] | None = None
    structural_counts_absent_reason: str | None = None
    #: `{produced_by, timestamp}` (R3): production metadata, not part of the result. `status`
    #: and every check are a pure function of (document, task); two reports of one revision
    #: differ at most here, so equality ignores it — and every byte-identity or idempotency
    #: comparison compares `as_document()` without it.
    provenance: Mapping[str, Any] = field(default_factory=dict, compare=False)

    def as_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "revision_id": self.revision_id,
            "task": self.task,
            "status": self.status,
            "checks": [check.as_document() for check in self.checks],
            "provenance": dict(self.provenance),
        }
        if self.structural_counts is not None:
            document["structural_counts"] = dict(self.structural_counts)
        else:
            document["structural_counts"] = None
            document["structural_counts_absent_reason"] = self.structural_counts_absent_reason
        return document

    @property
    def ready(self) -> bool:
        return self.status in ("READY_FOR_SIMULATION", "READY_FOR_OPTIMIZATION")


def task_unsupported(task: str) -> ApplicationError:
    """U05's refusal of a task v0.1 does not validate for, ready to raise (T08 review 2, Ruling 1).
    `LocalApplication.validate` raises it audited, before reading the revision."""
    from openflowsheet.application.contract import api_error

    return api_error("unsupported", f"task_unsupported({task})", pointer="/task")


def validate(
    document: Mapping[str, Any],
    task: Task = "simulation",
    *,
    now: Callable[[], str] = utc_timestamp,
) -> ValidationReport:
    """Blueprint §4.3's order: schema, dimensions, connectivity, components, then structural
    analysis.

    `now` is read once, when the report is made, for `provenance.timestamp` (T07 ruling round 1
    R3); it is injectable so that a test can fix it. Nothing else in the report depends on it.

    `task="optimization"` raises ADR 0019's `unsupported`, detail `task_unsupported(optimization)`,
    and builds no report (T08 review 2, Ruling 1; envelope U05): blueprint §4.3 defines
    `READY_FOR_OPTIMIZATION` as "requires a valid optimization formulation", and v0.1 checks none
    and has no optimizer, so the status would be a placeholder success. The value stays in the
    frozen enum, unused.
    """
    if task == "optimization":
        raise task_unsupported(task)
    checks: list[Check] = []

    # R-088 Q29 (T07 design note §12.5): a document with no canonical JSON form — a NaN, an
    # infinity, an integer that is not the canonical spelling of a binary64 (ADR 0002
    # Amendment 1) anywhere, read or not — is refused here, naming the node,
    # before any later stage can reach a digest that would raise untyped. A canonical document
    # never enters this branch, so its report is unchanged byte for byte.
    pointer = first_noncanonical(document)
    if pointer is not None:
        return ValidationReport(
            revision_id=_revision_id(document),
            task=task,
            status="INVALID",
            checks=(
                Check(
                    id="SCHEMA-01",
                    stage="schema",
                    result="FAIL",
                    message=f"document_not_canonical({pointer})",
                    implicated_objects=(pointer,),
                ),
            ),
            structural_counts=None,
            structural_counts_absent_reason="the revision is not well formed",
            provenance={"produced_by": SCHEMA_ONLY_PRODUCED_BY, "timestamp": now()},
        )

    missing = [key for key in REQUIRED_KEYS if key not in document]
    checks.append(
        Check(
            id="SCHEMA-01",
            stage="schema",
            result="PASS" if not missing else "FAIL",
            message="every required key present" if not missing else f"missing {missing}",
            implicated_objects=tuple(missing),
        )
    )
    if missing:
        return ValidationReport(
            revision_id=_revision_id(document),
            task=task,
            status="INVALID",
            checks=tuple(checks),
            structural_counts=None,
            structural_counts_absent_reason="the revision is not well formed",
            provenance={"produced_by": SCHEMA_ONLY_PRODUCED_BY, "timestamp": now()},
        )

    # T07 ruling round 5, S3: the frozen revision schema, applied. A document it refuses has a
    # shape the later stages were never written for, and reached them untyped (review S3). The
    # first error in `schema_errors`' order (by path, `_raise_first`'s rule) is reported. The PASS
    # message above stays: every required key is still present.
    schema_error = _first_schema_error(document)
    if schema_error is not None:
        pointer, message = schema_error
        return ValidationReport(
            revision_id=_revision_id(document),
            task=task,
            status="INVALID",
            checks=(
                Check(
                    id="SCHEMA-01",
                    stage="schema",
                    result="FAIL",
                    message=f"schema_invalid({pointer}): {message}",
                    # The root's pointer is empty and names no object; the report's own schema
                    # requires a non-empty id.
                    implicated_objects=(pointer,) if pointer else (),
                ),
            ),
            structural_counts=None,
            structural_counts_absent_reason="the revision is not well formed",
            provenance={"produced_by": SCHEMA_ONLY_PRODUCED_BY, "timestamp": now()},
        )

    instances = list(document.get("instances") or [])
    connections = list(document.get("connections") or [])
    specifications = list(document.get("specifications") or [])

    checks.append(
        _dimensions(
            list((document.get("component_set") or {}).get("components") or []),
            instances,
            specifications,
        )
    )
    checks.append(
        Check(
            id="GRAPH-01",
            stage="graph_connectivity",
            result="PASS" if instances else "FAIL",
            message=f"{len(instances)} instances",
        )
    )
    checks += _connectivity(instances, connections)
    checks += _components(document, instances)

    # Task-specific structure. A draft is not a failure: D16 makes an incomplete revision
    # persistable and committable, and only a *run* requires a revision validated for its task.
    if not specifications:
        checks.append(
            Check(
                id="COND-01",
                stage="conditional_classification",
                result="WARN",
                message="no specifications; the system is under-determined and this is a draft",
            )
        )
        status: ValidationStatus = "DRAFT"
    else:
        checks.append(
            Check(
                id="COND-01",
                stage="conditional_classification",
                result="PASS",
                message=f"{len(specifications)} specifications declared",
            )
        )
        status = "READY_FOR_SIMULATION"

    structural, counts, absent_reason, fallback = _structural(document)
    checks += structural

    failed = {check.id for check in checks if check.result == "FAIL"}
    if failed == {"STR-02"}:
        # Structural under-specification and nothing else wrong: a specification the flowsheet
        # needs is missing, which R-022 maps to `DRAFT` (blueprint §4.3: "`DRAFT` revisions may
        # be incomplete or under-specified"). T01 §12.3 read any STR-02 FAIL as `INVALID`; T02
        # A26 is the first registered revision to reach it through `validate()` — the A02
        # revision with the heater's temperature freed and no duty specification — and a
        # revision one specification short is incomplete, not defective. The check stays `FAIL`:
        # the finding is real, only the status it implies differs.
        status = "DRAFT"
    elif failed:
        status = "INVALID"
    elif (
        any(check.result == "NOT_RUN" for check in structural) and status == "READY_FOR_SIMULATION"
    ):
        # **A revision is not ready because nobody could look at it — and it is not wrong
        # either.** Blueprint §4.3 makes `READY_FOR_SIMULATION` conditional on an appropriately
        # closed system, so an analysis that did not run withdraws the ready verdict (M3 of the
        # Fable review of T01). What replaces it depends on *why* it did not run, decided by Frank
        # on 2026-09-24 (register R-022):
        #
        # - a revision missing a specification is incomplete, and §4.3 says in so many words that
        #   "`DRAFT` revisions may be incomplete or under-specified";
        # - a revision this tool cannot read may be perfectly fine, and `INVALID` would state a
        #   defect nobody found. `DRAFT` is the only status that claims neither closure nor a
        #   fault, and it blocks a run exactly as `INVALID` does. A fourth status (T01 Q1) is
        #   the accurate answer and needs an ADR, because the schema is frozen;
        # - a revision whose specifications contradict each other *is* wrong, and reaches here
        #   as an `STR-04 FAIL`, so the branch above has already made it `INVALID`.
        status = "DRAFT"

    return ValidationReport(
        revision_id=_revision_id(document),
        task=task,
        status=status,
        checks=tuple(checks),
        structural_counts=counts,
        structural_counts_absent_reason=absent_reason,
        provenance={
            "produced_by": PRODUCED_BY + (FALLBACK_PRODUCED_BY if fallback else ""),
            "timestamp": now(),
        },
    )


def _first_schema_error(document: Mapping[str, Any]) -> tuple[str, str] | None:
    """The first `process-revision.schema.json` error of a canonical `document`, as `(pointer,
    message)`, or `None`. The document is read as JSON reads it (a tuple is an array, any mapping
    an object): the schema judges the document's canonical form, not its Python spelling."""
    from openflowsheet.application.types import schema_errors

    errors = schema_errors("process-revision.schema.json", _as_json(document))
    if not errors:
        return None
    pointer, _, message = errors[0].partition(": ")
    return pointer, message


def _as_json(node: Any) -> Any:
    """A canonical document's JSON data model in the types a JSON parser returns."""
    if isinstance(node, Mapping):
        return {key: _as_json(value) for key, value in node.items()}
    if isinstance(node, list | tuple):
        return [_as_json(item) for item in node]
    return node


#: T07 ruling round 1 R1.2: when both binders refuse, the refusal of higher rank is reported.
#: Ruling round 5 S3 adds `inadmissible` between `conflict` and `incomplete`.
_REFUSAL_RANK: Final[Mapping[str, int]] = {
    "conflict": 3,
    "inadmissible": 2,
    "incomplete": 1,
    "unsupported": 0,
}


def _not_run(reason: str, hint: str | None) -> str:
    """A structural check's `NOT_RUN` message for a refusal: its reason, then the refusal's hint,
    what would be accepted (ruling round 6, B2). `structural_counts_absent_reason` stays the
    reason alone."""
    return f"not run: {reason}" if hint is None else f"not run: {reason}. {hint}"


def _analysed(
    document: Mapping[str, Any],
) -> tuple[Any, Unbound | None, Mapping[str, tuple[str, ...]], bool]:
    """`_structural`'s choice of binder: the analysed report, if any; the refusal it reports, if
    any (which then decides the checks); the specification labels of the revision binder's
    columns; and whether that binder was the one analysed."""
    from openflowsheet.application.binding import (
        Binding,
        bind_revision_or_reason,
        legacy_admission,
    )
    from openflowsheet.application.revision_binding import (
        RevisionBinding,
        bind_revision_flowsheet,
    )
    from openflowsheet.graph.analysis import analyse
    from openflowsheet.models.revision_flowsheet import pin_specifications
    from openflowsheet.orchestrator.execution import declaration_identity

    binding = bind_revision_or_reason(document)
    refusal: Unbound | None = None
    report: Any = None
    pins: Mapping[str, tuple[str, ...]] = {}
    fallback = False
    if isinstance(binding, Binding):
        report = analyse(
            binding.spec,
            binding.graph,
            model_version=binding.model_version,
            constants_sha256=binding.constants_sha256,
            specification_ids=binding.specification_ids,
            row_units=binding.row_units,
        )
        if report.finding == "STRUCTURALLY_CLOSED":
            # Ruling rounds 6 (B1) and 7 (M1, M2): a closed legacy analysis is READY only if
            # `legacy_eo` may solve the revision. When `legacy_admission` refuses it, the legacy
            # binder would solve a different problem, so its refusal is the one reported, through
            # the refusal path below. A legacy finding that is not closed stands: it is already
            # not READY.
            revision = bind_revision_flowsheet(document)
            if not isinstance(revision, RevisionBinding):
                refusal = legacy_admission(document, revision, binding)
    elif binding.kind in ("conflict", "inadmissible"):
        refusal = binding
    else:
        revision = bind_revision_flowsheet(document)
        if not isinstance(revision, RevisionBinding):
            revision = _free_class_refusal(document, revision)
        if isinstance(revision, RevisionBinding):
            model_version, constants = declaration_identity(revision.spec)
            report = analyse(
                revision.spec,
                revision.graph,
                model_version=model_version,
                constants_sha256=constants,
                specification_ids={},
                row_units=revision.row_units,
            )
            pins = pin_specifications(document)
            fallback = True
        elif (
            _REFUSAL_RANK[revision.kind] > _REFUSAL_RANK[binding.kind]
            or revision.kind == binding.kind == "unsupported"
        ):
            refusal = revision
        else:
            # T07 design note, ruling round 3, Q2 (amending R1.2): a tie is split by kind. An
            # `incomplete` tie reports the legacy refusal, which names and implicates the quantity
            # in the declaration's words (T06 A04, STR-02); an `unsupported` tie reports the
            # revision binder's, since the legacy one speaks only of SYN-001's declaration. In the
            # free class the revision side is the probe's refusal (ruling round 7, S1).
            refusal = binding

    return report, refusal, pins, fallback


def _free_class_refusal(document: Mapping[str, Any], refusal: Unbound) -> Unbound:
    """The revision side of the rank-and-tie comparison when the legacy binder refuses (T07
    design note, ruling round 7, S1, amending round 3's Q2). In the free class (`legacy_answers`),
    `refusal` says only that the binder cannot read the free role; with every free specification
    carrying a value, the probe's `incomplete` or `unsupported` refusal — what the binder says of
    the rest of the document, read with `free` as `fixed` — is compared instead. A probe
    `inadmissible` or `conflict` may be a start, which is never a finding, and without a value
    there is no start to probe with: `refusal` stands."""
    from openflowsheet.application.binding import legacy_answers, revision_probe

    if not legacy_answers(document, refusal):
        return refusal
    free = [e for e in document.get("specifications") or () if e.get("role") == "free"]
    if any(entry.get("value") is None for entry in free):
        return refusal
    probed, _ = revision_probe(document, None)
    if probed is not None and probed.kind in ("incomplete", "unsupported"):
        return probed
    return refusal


def structural_refusal(document: Mapping[str, Any]) -> Unbound | None:
    """The binder refusal `validate()`'s structural stage reports for `document`, or `None` when
    it analyses one (T07 ruling round 6, B1: `inspect_structure`'s `hint` is this refusal's)."""
    return _analysed(document)[1]


def _structural(
    document: Mapping[str, Any],
) -> tuple[list[Check], Mapping[str, int] | None, str | None, bool]:
    """T01's checks `STR-01`..`STR-05` (specification §12.3), or the reason there are none; and
    whether the revision binder's flowsheet was the one analysed.

    The analysis needs a compiled declaration. The legacy binder (`bind_revision_or_reason`, the
    registered SYN-001 declaration) is tried first, so every SYN-001-topology report is unchanged.
    When it binds and its analysis is closed, the revision binder is asked too, and when it refuses,
    `legacy_admission`'s refusal is reported unless it admits the legacy route (ruling rounds 6,
    B1, and 7, M1 and M2): READY promises a route that solves the problem the document states.
    When it refuses with `unsupported` or `incomplete` — statements about that binder's one
    declaration, not about the document — the revision binder's flowsheet is analysed with the
    inputs `plan_revision` passes (T07 design note §12.4 as amended by ruling round 1 R1; ADR 0020
    D5), and implicated columns are labelled with the specification ids that pin them. A legacy
    `conflict` is a statement about the document and never falls back, and neither does an
    `inadmissible` one (ruling round 5, S3): the revision binder would build the same model with
    the same value and refuse it too. When both binders refuse, the higher-ranked refusal is
    reported (`conflict`, `inadmissible`, `incomplete`, `unsupported`; see the tie below).

    An `inadmissible` refusal — a value the document fixes that the model it names refuses at
    construction — is `CAP-01`'s finding (stage `capability`), with the structural checks
    `NOT_RUN`; so the revision is `INVALID`, as a `conflict` is.

    A revision no binder reads gets `NOT_RUN` checks and a named reason rather than a silent pass
    — a validator that reported `READY_FOR_SIMULATION` because it could not look would be the
    placeholder success the repository's rules forbid.
    """
    report, refusal, pins, fallback = _analysed(document)

    if refusal is not None:
        if refusal.kind == "conflict":
            # A real defect, found before any analysis: two specifications fix one quantity to
            # different values. It is `STR-04`'s finding, reported as one.
            reason = f"the structural analysis did not run: {refusal.detail}"
            return (
                [
                    Check(
                        id=check_id,
                        stage="structural_analysis",
                        result="FAIL" if check_id == "STR-04" else "NOT_RUN",
                        message=refusal.detail
                        if check_id == "STR-04"
                        else _not_run(reason, refusal.hint),
                        implicated_objects=refusal.implicated if check_id == "STR-04" else (),
                    )
                    for check_id in ("STR-01", "STR-02", "STR-03", "STR-04", "STR-05")
                ],
                None,
                reason,
                fallback,
            )
        if refusal.kind == "inadmissible":
            # Ruling round 5, S3: the document asks the model it names for a value outside that
            # model's declared domain. A finding about the document, as `DIM-01`'s is.
            reason = f"the structural analysis did not run: {refusal.detail}"
            capability = Check(
                id="CAP-01",
                stage="capability",
                result="FAIL",
                message=refusal.detail,
                implicated_objects=refusal.implicated,
            )
            return (
                [
                    capability,
                    *(
                        Check(
                            id=check_id,
                            stage="structural_analysis",
                            result="NOT_RUN",
                            message=_not_run(reason, refusal.hint),
                        )
                        for check_id in ("STR-01", "STR-02", "STR-03", "STR-04", "STR-05")
                    ),
                ],
                None,
                reason,
                fallback,
            )
        reason = (
            f"the revision is incomplete: {refusal.detail}"
            if refusal.kind == "incomplete"
            else f"this revision cannot be analysed by T01's binding: {refusal.detail}"
        )
        return (
            [
                Check(
                    id=check_id,
                    stage="structural_analysis",
                    result="NOT_RUN",
                    message=_not_run(reason, refusal.hint),
                    implicated_objects=refusal.implicated,
                )
                for check_id in ("STR-01", "STR-02", "STR-03", "STR-04", "STR-05")
            ],
            None,
            reason,
            fallback,
        )

    if report.finding == "UNSUPPORTED":
        detail = report.unsupported[0].detail if report.unsupported else "the trace failed"
        row = report.unsupported[0].row_id if report.unsupported else None
        reason = f"the structural trace could not read row {row!r}: {detail}"
        return (
            [
                Check(
                    id=check_id,
                    stage="structural_analysis",
                    result="NOT_RUN",
                    message=f"not run: {reason}",
                    implicated_objects=() if row is None else (row,),
                )
                for check_id in ("STR-01", "STR-02", "STR-03", "STR-04", "STR-05")
            ],
            None,
            reason,
            fallback,
        )

    # §12.4: the labels do not change the finding; a column a specification pins is named by that
    # specification's id, as the legacy binder's `specification_ids` names its rows.
    checks = [
        replace(
            check,
            implicated_objects=tuple(
                label for item in check.implicated_objects for label in (pins.get(item) or (item,))
            ),
        )
        for check in structural_checks(report)
    ]
    return checks, report.structural_counts, None, fallback


def structural_checks(report: Any) -> list[Check]:
    """`STR-01`..`STR-06` from a `StructuralReport` (T01 §12.3).

    Separated from `_structural` so that a check reachable only by a synthetic declaration — the
    `STR-06` warning, which no registered revision provokes — can still be exercised by a test
    rather than recorded as untested (M5(b) of the Fable review of T01).
    """
    from openflowsheet.application.binding import instance_named
    from openflowsheet.graph.report import STATEMENTS

    counts = report.structural_counts
    assert counts is not None
    # T08 D1: a message names what the user wrote. `over_specified_units` holds the declaration's
    # unit ids (the legacy binder's `U-HEAT`; T01's registered field, unchanged); each is named by
    # the revision instance that authored it, as `implicated_objects` already is. The T08 review's
    # §3.3 extends the rule to `STR-04`'s row ids and `STR-05`'s units, through one helper.
    instance_of = {entry.unit_id: entry.instance_id for entry in report.unit_degrees_of_freedom}

    def named(identifiers: Sequence[str]) -> list[str]:
        return [instance_named(identifier, instance_of) for identifier in identifiers]

    over_specified = named(report.over_specified_units)
    checks = [
        Check(
            id="STR-01",
            stage="structural_analysis",
            result="PASS",
            message=(
                f"{report.finding}: {counts['equations']} equations over "
                f"{counts['free_variables']} free variables, structural rank {counts['matched']}, "
                f"{report.nnz} declared incidences. {STATEMENTS['S1']} {STATEMENTS['S2']} "
                f"{STATEMENTS['S3']}"
            ),
        ),
        Check(
            id="STR-02",
            stage="structural_analysis",
            result="PASS" if report.deficit == 0 else "FAIL",
            message=(
                "no structural under-specification"
                if report.deficit == 0
                else (
                    f"STRUCTURAL_UNDER_SPECIFICATION: deficit {report.deficit}. {STATEMENTS['S4']}"
                )
            ),
            implicated_objects=(
                ()
                if report.deficit == 0
                else report.dm_after_certificates.under_cols
                if report.dm_after_certificates is not None
                else ()
            ),
        ),
        Check(
            id="STR-03",
            stage="structural_analysis",
            result="PASS" if report.excess == 0 else "FAIL",
            message=(
                "no structural over-specification after certified redundancy"
                if report.excess == 0
                else (
                    f"STRUCTURAL_OVER_SPECIFICATION: excess {report.excess}; "
                    f"over-specified units {over_specified}; candidate "
                    f"specifications {list(report.candidate_specifications)}. "
                    f"{STATEMENTS['S4']} {STATEMENTS['S5']}"
                )
            ),
            implicated_objects=() if report.excess == 0 else report.implicated_objects,
        ),
        Check(
            id="STR-04",
            stage="structural_analysis",
            result="PASS" if not report.conflicts else "FAIL",
            message=(
                f"{len(report.certificates)} certified redundant rows, all consistent. "
                f"{STATEMENTS['S6']}"
                if not report.conflicts
                else (
                    "SPECIFICATION_CONFLICT: "
                    + "; ".join(
                        f"{instance_named(entry.row_id, instance_of)} repeats "
                        f"{named([name for name, _ in entry.equals])} but "
                        f"disagrees by {entry.constant_mismatch:g}, beyond {entry.tolerance:g}"
                        for entry in report.conflicts
                    )
                )
            ),
            implicated_objects=() if not report.conflicts else report.implicated_objects,
        ),
        _block_metrics(report, named),
    ]
    if report.uncertified_affine_rows:
        checks.append(
            Check(
                id="STR-06",
                stage="structural_analysis",
                result="WARN",
                message=(
                    "consistency not established for affine rows this policy does not read: "
                    f"{list(report.uncertified_affine_rows)}. They are retained, not certified "
                    "and not discarded"
                ),
                implicated_objects=report.uncertified_affine_rows,
            )
        )
    return checks


def _block_metrics(report: Any, named: Callable[[Sequence[str]], list[str]]) -> Check:
    """`STR-05`: the block-triangular form and the tear. Informational; it never fails.

    T08 D1, extended to `STR-05` (Frank, 2026-09-29, Q-P1-2): a loop's units and the attempt
    signature are named by the revision instances that authored them (`named`, as `STR-03`'s
    over-specified units are), not by the declaration's unit ids.

    A declaration that is not structurally closed has no square system to decompose, so this
    reports `NOT_RUN` with that as the reason rather than a partial decomposition of something
    that does not decompose (T01 §7.1).
    """
    form, tear = report.block_triangular_form, report.tear
    if form is None:
        return Check(
            id="STR-05",
            stage="structural_analysis",
            result="NOT_RUN",
            message=(
                f"not run: the block-triangular form and the tear are defined on a structurally "
                f"closed system, and the finding is {report.finding}"
            ),
        )
    largest = max(form.block_sizes_sorted) if form.block_sizes_sorted else 0
    total = sum(form.block_sizes_sorted)
    loops = () if tear is None else tear.loops
    torn = "; ".join(
        f"loop {named(loop.units)} torn at {loop.chosen_stream} "
        f"({len(loop.tear_variables)} variables, by {loop.tie_break_used})"
        if loop.chosen_stream is not None
        else f"loop {named(loop.units)}: {loop.unsupported}"
        for loop in loops
    )
    return Check(
        id="STR-05",
        stage="structural_analysis",
        result="PASS",
        message=(
            f"{form.block_count} blocks, largest {largest}/{total}; "
            + (torn or "no process loop")
            + (
                ""
                if tear is None
                else f"; inner {len(tear.inner_rows)}x{len(tear.inner_variables)}, "
                f"attempt signature {named(tear.signature_units)}"
            )
        ),
    )


def _connectivity(
    instances: Sequence[Mapping[str, Any]], connections: Sequence[Mapping[str, Any]]
) -> list[Check]:
    known = {str(instance.get("id")) for instance in instances}
    dangling: list[str] = []
    for connection in connections:
        for end in ("from", "to"):
            reference = connection.get(end)
            target = reference.get("instance") if isinstance(reference, Mapping) else reference
            if target is not None and str(target) not in known:
                dangling.append(f"{connection.get('id', '?')}.{end} -> {target}")
    return [
        Check(
            id="GRAPH-02",
            stage="graph_connectivity",
            result="PASS" if not dangling else "FAIL",
            message=(
                f"{len(connections)} connections resolve"
                if not dangling
                else f"dangling references: {dangling}"
            ),
            implicated_objects=tuple(dangling),
        )
    ]


def _dimensions(
    components: Sequence[str],
    instances: Sequence[Mapping[str, Any]],
    specifications: Sequence[Mapping[str, Any]],
) -> Check:
    """`DIM-01` (ADR 0016; T06 spec §8.5, reader R4; register R-077): `unit-conversion-v2`
    applied to every specification value and, through R6, to every instance parameter.

    A unit `unit-conversion-v2` does not convert for its target is a defect found, `FAIL` and
    `INVALID`, not R-022's "cannot read". The codes are the revision binding's, which both
    bindings also refuse with. A specification whose component is outside the component set is
    not judged: `COMP-03` fails it, and the unit never changes the diagnosis of a component error
    (ADR 0016 D5); the message says which were skipped. Specifications are judged first, in
    document order, then parameters by instance declaration order and, within an instance, by
    parameter name in code-point order (ADR 0016 D6).
    """
    from openflowsheet.application.binding import HINT_LIMIT
    from openflowsheet.application.projection import bound_text
    from openflowsheet.models.revision_flowsheet import (
        RevisionError,
        convert_specification,
        read_parameter,
    )
    from openflowsheet.units import UNIT_CONVERSION_ID, UnitConversion, read_number

    def _with_hint(error: RevisionError) -> str:
        """The code, then its hint (ruling round 6, B2), bounded as an `Unbound`'s is."""
        if error.hint is None:
            return error.code
        return f"{error.code}. {bound_text(error.hint, HINT_LIMIT)}"

    conversions: list[UnitConversion] = []
    refusals: list[tuple[str, str]] = []
    skipped: list[str] = []
    for entry in specifications:
        name = str(entry.get("id", ""))
        component = (entry.get("target") or {}).get("component")
        if component is not None and component not in components:
            skipped.append(name)
            continue
        raw = entry.get("value")
        # A value that is not a number is not a unit's fault; the binding refuses it on its own
        # code. Its unit and kind are still judged.
        value = read_number(raw)
        try:
            _, conversion = convert_specification(entry, value)
        except RevisionError as error:
            refusals.append((name, _with_hint(error)))
            continue
        if conversion is not None:
            conversions.append(conversion)
    for instance in instances:
        unit = str(instance.get("id", ""))
        parameters = instance.get("parameters") or {}
        for parameter in sorted(str(name) for name in parameters):
            try:
                _, conversion = read_parameter(unit, parameter, parameters[parameter])
            except RevisionError as error:
                refusals.append((f"{unit}.{parameter}", _with_hint(error)))
                continue
            if conversion is not None:
                conversions.append(conversion)

    if refusals:
        return Check(
            id="DIM-01",
            stage="dimensions",
            result="FAIL",
            message="; ".join(code for _, code in refusals),
            implicated_objects=tuple(name for name, _ in refusals),
        )
    unjudged = (
        f"; not judged for a component outside the set: {', '.join(skipped)}" if skipped else ""
    )
    if not conversions:
        return Check(
            id="DIM-01",
            stage="dimensions",
            result="PASS",
            message=(
                "every judged specification and parameter is in its kind's internal SI unit"
                + unjudged
                if skipped
                else "every specification and parameter is in its kind's internal SI unit"
            ),
        )
    return Check(
        id="DIM-01",
        stage="dimensions",
        result="PASS",
        message=f"converted by {UNIT_CONVERSION_ID}: "
        + "; ".join(
            f"{c.input_id} {c.value!r} {c.unit} -> {c.si_value!r} {c.si_unit}"
            + (f" (M_{c.component} = {c.molar_mass!r} kg/mol)" if c.rule == "mass_to_molar" else "")
            for c in conversions
        )
        + unjudged,
        implicated_objects=tuple(c.input_id for c in conversions),
    )


#: The parameter families keyed by component id (`nu.<c>`, `conversion.<c>`, `split.<c>`).
_COMPONENT_KEYED_PARAMETERS: Final[frozenset[str]] = frozenset({"nu", "conversion", "split"})


def _component_references(
    components: Sequence[str],
    instances: Sequence[Mapping[str, Any]],
    specifications: Sequence[Mapping[str, Any]],
) -> Check:
    """`COMP-03` (T06 spec §8.5, register R-071): every specification's `target.component`, and
    every component-keyed parameter name — declared on an instance or pinned through a
    specification's `parameters.<name>` path — names a member of the component set."""

    def outside(parameter: str) -> str | None:
        family, _, component = parameter.partition(".")
        if family in _COMPONENT_KEYED_PARAMETERS and component and component not in components:
            return component
        return None

    unknown: list[tuple[str, str]] = []
    for instance in instances:
        unit = str(instance.get("id", ""))
        for parameter in instance.get("parameters") or {}:
            component = outside(str(parameter))
            if component is not None:
                unknown.append((f"{unit}.{parameter}", component))
    for entry in specifications:
        name = str(entry.get("id", ""))
        target = entry.get("target") or {}
        component = target.get("component")
        if component is not None and component not in components:
            unknown.append((name, str(component)))
            continue
        path = str(target.get("path", ""))
        if path.startswith("parameters."):
            named = outside(path.removeprefix("parameters."))
            if named is not None:
                unknown.append((name, named))

    return Check(
        id="COMP-03",
        stage="component_reference_compatibility",
        result="FAIL" if unknown else "PASS",
        message=(
            "; ".join(
                f"{name} names component {component!r}, which is not in the component set "
                f"{list(components)}"
                for name, component in unknown
            )
            if unknown
            else f"every component reference names a member of the component set {list(components)}"
        ),
        implicated_objects=tuple(name for name, _ in unknown),
    )


def _components(document: Mapping[str, Any], instances: Sequence[Mapping[str, Any]]) -> list[Check]:
    component_set = document.get("component_set") or {}
    components = list(component_set.get("components") or [])
    specifications = list(document.get("specifications") or [])
    return [
        Check(
            id="COMP-01",
            stage="component_reference_compatibility",
            result="PASS" if components else "FAIL",
            message=f"{len(components)} components: {components}" if components else "none",
        ),
        Check(
            id="COMP-02",
            stage="component_reference_compatibility",
            result="PASS" if component_set.get("record_source") else "FAIL",
            message=str(component_set.get("record_source") or "no record source declared"),
        ),
        _component_references(components, instances, specifications),
    ]
