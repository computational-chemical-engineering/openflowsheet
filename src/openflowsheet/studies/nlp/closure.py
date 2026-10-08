"""The study-level optimization closure: readiness, the report, and `optimize()`'s unsupported path.

M03 spec §8.6, §8.7; ADR 0032 D5, D6 (D16's M03 half). `optimization_readiness` returns
`READY_FOR_OPTIMIZATION` only when the formulation closes **and** an audited NLP solver is
importable; otherwise `unsupported` with every failing reason, in the specification's order:

| Reason | Condition that failed |
| --- | --- |
| `UNKNOWN_DECISION` | every decision id is a pinned input |
| `BOUNDS_UNDECLARED` | every decision has a finite box with lower < upper |
| `START_OUTSIDE_BOUNDS` | every start inside the box |
| `DECISION_INCONSISTENT_WITH_ELIMINATED_ROWS` | the decisions pass Q3 at every start |
| `UNKNOWN_VARIABLE` | every variable the objective and constraints name exists |
| `HESSIAN_UNAVAILABLE` | the Hessian policy is the limited-memory approximation |
| `SIMULATION_NOT_READY` | every start solves and certifies `VERIFIED` |
| `NLP_SOLVER_UNAVAILABLE` | the `nlp` extra and its adapter installed; [A10] verdict `PASS` |

`optimize()` calls it first and returns an `OptimizationReport` with status `UNSUPPORTED` and those
reasons — never an `ImportError`, never a partial success. When it is ready, every other status
comes from `classify_starts` (spec §8.5, Amendment 1): each start classified from Ipopt's return
status and the V1-V5 outcomes on the re-solved simulation, the report taking the highest
classification under `KKT_POINT_VERIFIED` > `NOT_VERIFIED` > `INFEASIBLE_REPORTED` >
`SOLVER_FAILED`. Whether a solver is available is decided without importing one
(`importlib.util.find_spec`), so the default install never loads Pyomo or cyipopt (gate G6).

R-129 is unchanged: `Application.validate(…, task="optimization")` stays typed `unsupported`,
because a `ProcessRevision` has no place to declare decisions, an objective or constraints
(ADR 0032 D6). This closure is study-level; it is what an optimizer sits behind.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Literal

from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.models import SpecificationError
from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
from openflowsheet.studies.nlp.formulation import (
    FORMULATION_KIND,
    HESSIAN_APPROXIMATION,
    HESSIAN_POLICY,
    IPOPT_OPTIONS,
    NlpFormulation,
)
from openflowsheet.studies.nlp.verification import CHECKS, CheckOutcome, declared_regimes
from openflowsheet.studies.sensitivity import TAU_ALIAS, OutputFunctional, StudyParameter
from openflowsheet.studies.syn001 import solve_certified, syn001_sensitivity, with_pinned

SCHEMA_VERSION: Final = "optimization-report-v1"
#: The [A10] audit of the optional NLP path (spec §9): the document, its gate and its verdict.
AUDIT_DOCUMENT: Final = "docs/m03-ipopt-audit.md"
AUDIT_GATE: Final = "G-A10"
AUDIT_VERDICT: Final = "PASS"
#: The audited `libpynumero_ASL.so` (audit §4.3, the inventory's `$ENV/share/pyomo/lib` object):
#: the adapter refuses to solve with any other build PyNumero finds (audit §9 item 2).
AUDITED_PYNUMERO_ASL_SHA256: Final = (
    "6646bbdd51332c3a5b306604fe0f6bd572d7cec352af994c76bfe1cdf550161c"
)
#: N1, Frank's answer on the licences of the `nlp` extra's stack (audit §8; ADR 0032 D5), is
#: pending. The capability needs both this acceptance and the extra (`pyproject.toml`): declining
#: N1 reverts the commit that sets this to True and the one that declares the extra, and re-takes
#: the inventory (`scripts/m03_ipopt_inventory.py --env <env>`). Without the acceptance,
#: `audited_solver()` is unavailable, so `optimize()` reports `UNSUPPORTED(NLP_SOLVER_UNAVAILABLE)`
#: and solves nothing, even in the audited environment (M03 review F4).
NLP_LICENCES_ACCEPTED: Final = True
#: The one module allowed to import Pyomo and cyipopt (WO-8), and the libraries it needs.
ADAPTER_MODULE: Final = "openflowsheet.studies.nlp.greybox"
NLP_LIBRARIES: Final = ("pyomo", "cyipopt")

ReadinessCode = Literal[
    "UNKNOWN_DECISION",
    "BOUNDS_UNDECLARED",
    "START_OUTSIDE_BOUNDS",
    "DECISION_INCONSISTENT_WITH_ELIMINATED_ROWS",
    "UNKNOWN_VARIABLE",
    "HESSIAN_UNAVAILABLE",
    "SIMULATION_NOT_READY",
    "NLP_SOLVER_UNAVAILABLE",
]
#: Spec §8.7's order, which is the order reasons are listed in.
READINESS_ORDER: Final[tuple[ReadinessCode, ...]] = (
    "UNKNOWN_DECISION",
    "BOUNDS_UNDECLARED",
    "START_OUTSIDE_BOUNDS",
    "DECISION_INCONSISTENT_WITH_ELIMINATED_ROWS",
    "UNKNOWN_VARIABLE",
    "HESSIAN_UNAVAILABLE",
    "SIMULATION_NOT_READY",
    "NLP_SOLVER_UNAVAILABLE",
)
ReadinessStatus = Literal["READY_FOR_OPTIMIZATION", "unsupported"]
ReportStatus = Literal[
    "KKT_POINT_VERIFIED", "NOT_VERIFIED", "INFEASIBLE_REPORTED", "SOLVER_FAILED", "UNSUPPORTED"
]
StartClassification = Literal[
    "KKT_POINT_VERIFIED", "NOT_VERIFIED", "INFEASIBLE_REPORTED", "SOLVER_FAILED"
]
#: Spec §8.5 (Amendment 1): the report's status is its starts' highest classification, in this
#: order. A refuted claim of success outranks Ipopt's local, heuristic infeasibility verdict.
STATUS_PRECEDENCE: Final[tuple[StartClassification, ...]] = (
    "KKT_POINT_VERIFIED",
    "NOT_VERIFIED",
    "INFEASIBLE_REPORTED",
    "SOLVER_FAILED",
)
#: Ipopt's `ApplicationReturnStatus` (`IpReturnCodes_inc.h`), the integer cyipopt reports as
#: `info["status"]`. Only rules 2 and 3 of spec §8.5 read a value; the names are for the detail.
IPOPT_STATUS_NAMES: Final[Mapping[int, str]] = {
    0: "Solve_Succeeded",
    1: "Solved_To_Acceptable_Level",
    2: "Infeasible_Problem_Detected",
    3: "Search_Direction_Becomes_Too_Small",
    4: "Diverging_Iterates",
    5: "User_Requested_Stop",
    6: "Feasible_Point_Found",
    -1: "Maximum_Iterations_Exceeded",
    -2: "Restoration_Failed",
    -3: "Error_In_Step_Computation",
    -4: "Maximum_CpuTime_Exceeded",
    -5: "Maximum_WallTime_Exceeded",
    -10: "Not_Enough_Degrees_Of_Freedom",
    -11: "Invalid_Problem_Definition",
    -12: "Invalid_Option",
    -13: "Invalid_Number_Detected",
    -100: "Unrecoverable_Exception",
    -101: "NonIpopt_Exception_Thrown",
    -102: "Insufficient_Memory",
    -199: "Internal_Error",
}
#: Spec §8.5 rule 2: the statuses with which Ipopt claims a solution.
IPOPT_CLAIMS_SOLUTION: Final = frozenset({0, 1})
#: Spec §8.5 rule 3: `Infeasible_Problem_Detected`.
IPOPT_INFEASIBLE: Final = 2


# -- the solver --------------------------------------------------------------------------------


@dataclass(frozen=True)
class SolverAvailability:
    """Whether an audited NLP solver can be used, and why not."""

    available: bool
    detail: str
    versions: Mapping[str, str | None] = field(default_factory=dict)
    audit_document: str = AUDIT_DOCUMENT
    audit_gate: str = AUDIT_GATE
    audit_verdict: str = AUDIT_VERDICT

    def as_document(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "detail": self.detail,
            "versions": dict(self.versions),
            "audit": {
                "document": self.audit_document,
                "gate": self.audit_gate,
                "verdict": self.audit_verdict,
            },
        }


def audited_solver() -> SolverAvailability:
    """The `nlp` extra's state, found without importing it (G6), and N1's licence acceptance."""
    versions = {name: _version(name) for name in ("ipopt", "cyipopt", "pyomo")}
    missing = [name for name in NLP_LIBRARIES if importlib.util.find_spec(name) is None]
    problems = []
    if missing:
        problems.append(f"the optional `nlp` extra is not installed ({', '.join(missing)} absent)")
    if importlib.util.find_spec(ADAPTER_MODULE) is None:
        problems.append(f"the gray-box adapter {ADAPTER_MODULE} (WO-8) is not present")
    if AUDIT_VERDICT != "PASS":
        problems.append(f"the [A10] verdict is {AUDIT_VERDICT}")
    if not NLP_LICENCES_ACCEPTED:
        problems.append("the licences of the `nlp` extra's stack are not accepted (N1)")
    if problems:
        return SolverAvailability(
            False,
            "; ".join(problems) + f" — see {AUDIT_DOCUMENT} ({AUDIT_GATE}: {AUDIT_VERDICT})",
            versions,
        )
    return SolverAvailability(True, f"audited by {AUDIT_DOCUMENT} ({AUDIT_GATE})", versions)


def _version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


SolverProbe = Callable[[], SolverAvailability]


# -- readiness ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class ReadinessReason:
    code: ReadinessCode
    detail: str
    subject: str | None = None

    def as_document(self) -> dict[str, Any]:
        return {"code": self.code, "detail": self.detail, "subject": self.subject}


@dataclass(frozen=True)
class StartReadiness:
    """What readiness found at one start: the certified solve, its regimes, Q3's residuals."""

    start: tuple[float, ...]
    outcome: str
    message: str
    certificate_status: str | None
    regimes: Mapping[str, str] | None
    alias_residuals: Mapping[str, float | None] | None
    state: Mapping[str, float] | None = None

    def as_document(self) -> dict[str, Any]:
        return {
            "start": list(self.start),
            "outcome": self.outcome,
            "message": self.message,
            "certificate_status": self.certificate_status,
            "regimes": dict(self.regimes) if self.regimes is not None else None,
            "alias_residuals": (
                dict(self.alias_residuals) if self.alias_residuals is not None else None
            ),
        }


@dataclass(frozen=True)
class Readiness:
    status: ReadinessStatus
    reasons: tuple[ReadinessReason, ...]
    solver: SolverAvailability
    starts: tuple[StartReadiness, ...]

    @property
    def codes(self) -> tuple[ReadinessCode, ...]:
        return tuple(dict.fromkeys(reason.code for reason in self.reasons))

    @property
    def declared_regimes(self) -> Mapping[str, str] | None:
        """The formulation's regimes: the first verified start's."""
        return next((start.regimes for start in self.starts if start.regimes is not None), None)

    def as_document(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reasons": [reason.as_document() for reason in self.reasons],
            "solver": self.solver.as_document(),
            "starts": [start.as_document() for start in self.starts],
        }


def optimization_readiness(
    formulation: NlpFormulation,
    flowsheet: Syn001Flowsheet,
    *,
    solver_probe: SolverProbe = audited_solver,
) -> Readiness:
    """Spec §8.7: every failing reason, or `READY_FOR_OPTIMIZATION`.

    `solver_probe` decides `NLP_SOLVER_UNAVAILABLE`; it is replaceable so that a test can check
    each other reason alone, and READY, without the audited environment."""
    reasons: list[ReadinessReason] = []
    try:
        spec = flowsheet.spec()
    except SpecificationError as error:
        spec = None
        reasons.append(ReadinessReason("SIMULATION_NOT_READY", f"the flowsheet: {error}"))

    known_decisions = True
    if spec is not None:
        for decision_id in formulation.decision_ids:
            if decision_id not in spec.parameter_ids:
                known_decisions = False
                reasons.append(
                    ReadinessReason(
                        "UNKNOWN_DECISION",
                        f"{decision_id!r} is not a pinned input of {spec.label!r}",
                        decision_id,
                    )
                )
    bounded = True
    for decision in formulation.decisions:
        if not decision.bounded:
            bounded = False
            reasons.append(
                ReadinessReason(
                    "BOUNDS_UNDECLARED",
                    f"{decision.parameter_id}: the box [{decision.lower}, {decision.upper}] is "
                    "not finite with lower < upper",
                    decision.parameter_id,
                )
            )
    for index, start in enumerate(formulation.starts):
        for decision, value in zip(formulation.decisions, start, strict=True):
            if decision.bounded and not decision.lower <= value <= decision.upper:  # type: ignore[operator]
                reasons.append(
                    ReadinessReason(
                        "START_OUTSIDE_BOUNDS",
                        f"start {index}: {decision.parameter_id} = {value!r} is outside "
                        f"[{decision.lower!r}, {decision.upper!r}]",
                        decision.parameter_id,
                    )
                )
    if spec is not None:
        for name in formulation.variables:
            if name not in spec.variable_ids:
                reasons.append(
                    ReadinessReason(
                        "UNKNOWN_VARIABLE", f"{name!r} is not a variable of {spec.label!r}", name
                    )
                )
    if formulation.hessian != HESSIAN_APPROXIMATION:
        reasons.append(
            ReadinessReason(
                "HESSIAN_UNAVAILABLE",
                f"Hessian {formulation.hessian!r} requested; Capabilities.hessian is absent and "
                f"the only policy is Ipopt's {HESSIAN_APPROXIMATION} approximation",
            )
        )

    starts: list[StartReadiness] = []
    if spec is not None and known_decisions:
        for index, start in enumerate(formulation.starts):
            record, found = _start(formulation, flowsheet, index, start, bounded, spec)
            starts.append(record)
            reasons.extend(found)

    solver = solver_probe()
    if not solver.available:
        reasons.append(ReadinessReason("NLP_SOLVER_UNAVAILABLE", solver.detail, AUDIT_DOCUMENT))

    order = {code: index for index, code in enumerate(READINESS_ORDER)}
    ordered = tuple(sorted(reasons, key=lambda reason: order[reason.code]))
    return Readiness(
        status="unsupported" if ordered else "READY_FOR_OPTIMIZATION",
        reasons=ordered,
        solver=solver,
        starts=tuple(starts),
    )


def _start(
    formulation: NlpFormulation,
    flowsheet: Syn001Flowsheet,
    index: int,
    start: Sequence[float],
    bounded: bool,
    spec: Any,
) -> tuple[StartReadiness, list[ReadinessReason]]:
    """One start: it must solve and certify; then Q3 for every decision at its state."""
    values = formulation.decision_values(start)
    try:
        sheet = with_pinned(flowsheet, values)
    except ValueError as error:
        reason = ReadinessReason("SIMULATION_NOT_READY", f"start {index}: {error}")
        return StartReadiness(
            tuple(start), "SPECIFICATION_REFUSED", str(error), None, None, None
        ), [reason]
    solve = solve_certified(sheet)
    certificate = solve.certificate
    status = certificate.verification_status if certificate else None
    state = solve.final_state
    if not solve.verified or state is None:
        reason = ReadinessReason(
            "SIMULATION_NOT_READY", f"start {index}: {solve.outcome}: {solve.message}"
        )
        return StartReadiness(tuple(start), solve.outcome, solve.message, status, None, None), [
            reason
        ]
    regimes = declared_regimes(sheet, state)
    if not bounded:
        # Q3 needs `StudyParameter`s, which need a finite box; BOUNDS_UNDECLARED is already listed.
        return (
            StartReadiness(
                tuple(start), solve.outcome, solve.message, status, regimes, None, state
            ),
            [],
        )
    parameters = tuple(
        StudyParameter(decision.parameter_id, decision.scale, decision.lower, decision.upper)  # type: ignore[arg-type]
        for decision in formulation.decisions
    )
    # Q3 is a property of each column and does not depend on the outputs requested.
    probe = OutputFunctional.of_variable(spec.variable_ids[0], 1.0)
    sensitivity = syn001_sensitivity(
        sheet,
        solve.result,
        parameters=parameters,
        outputs=(probe,),
        mode="forward",
        certificate=certificate,
    )
    residuals = {column.parameter_id: column.alias_residual for column in sensitivity.parameters}
    found = []
    for name, residual in residuals.items():
        if residual is None:
            found.append(
                ReadinessReason(
                    "SIMULATION_NOT_READY",
                    f"start {index}: Q3 could not be evaluated for {name} "
                    f"(sensitivity {sensitivity.status}: {list(sensitivity.refusal_codes)})",
                    name,
                )
            )
        elif residual > TAU_ALIAS:
            found.append(
                ReadinessReason(
                    "DECISION_INCONSISTENT_WITH_ELIMINATED_ROWS",
                    f"start {index}: {name}'s alias residual {residual:.3e} > tau_alias "
                    f"{TAU_ALIAS:g}",
                    name,
                )
            )
    return (
        StartReadiness(
            tuple(start), solve.outcome, solve.message, status, regimes, residuals, state
        ),
        found,
    )


# -- the status rule ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StartEvidence:
    """What spec §8.5's status rule reads of one start: Ipopt's return status, `None` when the run
    ended without one (an evaluation error that ended it, an exception in the adapter); and the
    outcomes of the V checks on the re-solved simulation at the decisions the start returned,
    empty when it returned none. `detail` says why a start has neither."""

    ipopt_status: int | None
    checks: Mapping[str, CheckOutcome]
    detail: str | None = None

    def __post_init__(self) -> None:
        unknown = sorted(set(self.checks) - set(CHECKS))
        if unknown:
            raise ValueError(f"{unknown} are not V checks ({', '.join(CHECKS)})")
        outcomes = set(self.checks.values()) - {"pass", "fail", "not_evaluated"}
        if outcomes:
            raise ValueError(f"{sorted(outcomes)} are not check outcomes")

    @property
    def verified(self) -> bool:
        """V1-V5 all `pass` (V6 records values and decides nothing)."""
        return all(self.checks.get(check) == "pass" for check in CHECKS[:5])


@dataclass(frozen=True)
class StartReason:
    """A report reason for one start not classified `KKT_POINT_VERIFIED` (spec §8.5): its
    classification as the code, Ipopt's status name and the failing V checks as the detail, and
    `start <i>` as the subject. The same document shape as a `ReadinessReason`."""

    code: StartClassification
    detail: str
    subject: str

    def as_document(self) -> dict[str, Any]:
        return {"code": self.code, "detail": self.detail, "subject": self.subject}


@dataclass(frozen=True)
class StatusVerdict:
    """Each start's classification, the report's status and its reasons (spec §8.5)."""

    classifications: tuple[StartClassification, ...]
    status: StartClassification
    reasons: tuple[StartReason, ...]

    @property
    def local_stationarity(self) -> bool:
        """`claims.local_stationarity`: true exactly when the status is `KKT_POINT_VERIFIED`."""
        return self.status == "KKT_POINT_VERIFIED"

    @property
    def verified_starts(self) -> tuple[int, ...]:
        """The starts a candidate may come from — empty unless the status is
        `KKT_POINT_VERIFIED`, so the candidate is `null` for every other status."""
        return tuple(
            index
            for index, classification in enumerate(self.classifications)
            if classification == "KKT_POINT_VERIFIED"
        )

    def start_records(self, records: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
        """The report's `starts`: each start's record with its `classification` (spec §8.6)."""
        if len(records) != len(self.classifications):
            raise ValueError(
                f"{len(records)} start records for {len(self.classifications)} classified starts"
            )
        annotated = []
        for record, classification in zip(records, self.classifications, strict=True):
            if record.get("classification", classification) != classification:
                raise ValueError(
                    f"a start record says {record['classification']}, the rule {classification}"
                )
            annotated.append({**record, "classification": classification})
        return tuple(annotated)


def classify_starts(starts: Sequence[StartEvidence]) -> StatusVerdict:
    """Spec §8.5 (Amendment 1), as one pure function of `(Ipopt status, V1-V5)` per start.

    Each start is classified by the first rule that applies: (1) V1-V5 all `pass` →
    `KKT_POINT_VERIFIED`, whatever Ipopt returned; (2) Ipopt status 0 or 1 → `NOT_VERIFIED`, a
    claimed solution the re-solved simulation refuted; (3) status 2 → `INFEASIBLE_REPORTED`;
    (4) anything else, no status included → `SOLVER_FAILED`. The status is the highest
    classification under `STATUS_PRECEDENCE`; `reasons` lists, in start order, every start not
    classified `KKT_POINT_VERIFIED`, so a refuted claim stays visible beside a verified candidate.
    The adapter (WO-8) computes no status of its own."""
    if not starts:
        raise ValueError("a report with no start is refused before any solve (UNSUPPORTED)")
    classifications = tuple(_classification(start) for start in starts)
    status = min(classifications, key=STATUS_PRECEDENCE.index)
    reasons = tuple(
        StartReason(classification, _start_detail(start), f"start {index}")
        for index, (start, classification) in enumerate(zip(starts, classifications, strict=True))
        if classification != "KKT_POINT_VERIFIED"
    )
    return StatusVerdict(classifications, status, reasons)


def _classification(start: StartEvidence) -> StartClassification:
    if start.verified:
        return "KKT_POINT_VERIFIED"
    if start.ipopt_status in IPOPT_CLAIMS_SOLUTION:
        return "NOT_VERIFIED"
    if start.ipopt_status == IPOPT_INFEASIBLE:
        return "INFEASIBLE_REPORTED"
    return "SOLVER_FAILED"


def _start_detail(start: StartEvidence) -> str:
    """Ipopt's status name and the failing V checks (spec §8.5), and the start's own detail."""
    if start.ipopt_status is None:
        parts = ["no Ipopt status"]
    else:
        name = IPOPT_STATUS_NAMES.get(start.ipopt_status, "unknown status")
        parts = [f"Ipopt {name} ({start.ipopt_status})"]
    failing = [check for check in CHECKS if start.checks.get(check) == "fail"]
    parts.append(f"failing V checks: {', '.join(failing) if failing else 'none'}")
    unevaluated = [check for check in CHECKS[:5] if start.checks.get(check, "") != "pass"]
    unevaluated = [check for check in unevaluated if check not in failing]
    if unevaluated:
        parts.append(f"not evaluated: {', '.join(unevaluated)}")
    if start.detail:
        parts.append(start.detail)
    return "; ".join(parts)


# -- the report --------------------------------------------------------------------------------


@dataclass(frozen=True)
class OptimizationReport:
    """Spec §8.6 (blueprint Appendix A: model/study hash, candidate, feasibility, stationarity
    evidence, truth evaluations, domains, starts, budget and limits)."""

    formulation: Mapping[str, Any]
    model: Mapping[str, Any]
    solver: Mapping[str, Any]
    hessian_policy: Mapping[str, Any]
    starts: tuple[Mapping[str, Any], ...]
    candidate: Mapping[str, Any] | None
    distinct_local_solutions: int
    status: ReportStatus
    #: §8.7's readiness reasons when `UNSUPPORTED`; otherwise one per start not verified (§8.5).
    reasons: tuple[ReadinessReason | StartReason, ...]
    claims: Mapping[str, Any]
    limits: Mapping[str, Any]
    schema_version: str = SCHEMA_VERSION

    @property
    def reason_codes(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(reason.code for reason in self.reasons))

    def as_document(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "formulation": dict(self.formulation),
            "model": dict(self.model),
            "solver": dict(self.solver),
            "hessian_policy": dict(self.hessian_policy),
            "starts": [dict(start) for start in self.starts],
            "candidate": dict(self.candidate) if self.candidate is not None else None,
            "distinct_local_solutions": self.distinct_local_solutions,
            "status": self.status,
            "reasons": [reason.as_document() for reason in self.reasons],
            "claims": dict(self.claims),
            "limits": dict(self.limits),
        }


def solver_record(
    solver: SolverAvailability, environment: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """The report's `solver`: versions, the linear solver, §8.4's options verbatim, the audit, and
    the environment the numbers were produced in (`greybox.solver_environment`; `None` when no
    solve ran).

    M03 review F2: ADR 0007 D6 makes the thread count part of the environment identity, and WO-8
    measured that it moves the result (48 OpenMP threads: NLP-1's r by one ulp, NLP-INF 498
    iterations against 597). It is recorded, not enforced (review ruling Q2)."""
    return {
        "ipopt": solver.versions.get("ipopt"),
        "cyipopt": solver.versions.get("cyipopt"),
        "pyomo": solver.versions.get("pyomo"),
        "linear_solver": IPOPT_OPTIONS["linear_solver"],
        "options": dict(IPOPT_OPTIONS),
        "audit": {
            "document": solver.audit_document,
            "gate": solver.audit_gate,
            "verdict": solver.audit_verdict,
        },
        "available": solver.available,
        "detail": solver.detail,
        "environment": dict(environment) if environment is not None else None,
    }


def report_limits() -> dict[str, Any]:
    return {
        "max_iter": IPOPT_OPTIONS["max_iter"],
        "max_wall_time": IPOPT_OPTIONS["max_wall_time"],
        "regime_restriction": (
            "every lifted TP split keeps the start's regime with margin >= tau_regime"
        ),
        "hessian": "absent (limited-memory approximation only)",
    }


def formulation_record(
    formulation: NlpFormulation, regimes: Mapping[str, str] | None
) -> dict[str, Any]:
    return {**formulation.as_document(), "kind": FORMULATION_KIND, "declared_regimes": regimes}


def model_record(flowsheet: Syn001Flowsheet) -> dict[str, Any]:
    """The base problem's identity, or `None` fields where the flowsheet does not compile."""
    try:
        metadata = compile_problem(flowsheet.spec()).metadata
    except SpecificationError:
        return {"model_version": None, "constants_sha256": None}
    return {"model_version": metadata.model_version, "constants_sha256": metadata.constants_sha256}


def unsupported_report(
    formulation: NlpFormulation, flowsheet: Syn001Flowsheet, readiness: Readiness
) -> OptimizationReport:
    """`UNSUPPORTED`: refused before any solve, with every reason; no candidate, no claim."""
    return OptimizationReport(
        formulation=formulation_record(formulation, readiness.declared_regimes),
        model=model_record(flowsheet),
        solver=solver_record(readiness.solver),
        hessian_policy=dict(HESSIAN_POLICY),
        starts=(),
        candidate=None,
        distinct_local_solutions=0,
        status="UNSUPPORTED",
        reasons=readiness.reasons,
        claims={
            "global_optimality": False,
            "local_stationarity": False,
            "second_order": "not_assessed",
        },
        limits=report_limits(),
    )


def optimize(
    formulation: NlpFormulation,
    flowsheet: Syn001Flowsheet,
    *,
    solver_probe: SolverProbe = audited_solver,
) -> OptimizationReport:
    """Spec §8.7: readiness first; `UNSUPPORTED` with its reasons unless ready.

    When ready, the gray-box adapter (WO-8, `ADAPTER_MODULE`) solves and assembles the report.
    It is imported only here and only then, so the default install never loads it; if it cannot
    be imported after all, the result is still a typed `UNSUPPORTED`, never an `ImportError`. Any
    `Exception` raised while importing it counts (a Pyomo or cyipopt import can fail otherwise
    than with `ImportError`; M03 review F8.1): §8.7's `optimize()` never raises for it."""
    readiness = optimization_readiness(formulation, flowsheet, solver_probe=solver_probe)
    if readiness.status != "READY_FOR_OPTIMIZATION":
        return unsupported_report(formulation, flowsheet, readiness)
    try:
        adapter = importlib.import_module(ADAPTER_MODULE)
    except Exception as error:  # noqa: BLE001 -- §8.7: a typed report, never an exception
        missing = Readiness(
            status="unsupported",
            reasons=(
                ReadinessReason(
                    "NLP_SOLVER_UNAVAILABLE",
                    f"the gray-box adapter could not be imported: {error} — see "
                    f"{AUDIT_DOCUMENT} ({AUDIT_GATE}: {AUDIT_VERDICT})",
                    AUDIT_DOCUMENT,
                ),
            ),
            solver=readiness.solver,
            starts=readiness.starts,
        )
        return unsupported_report(formulation, flowsheet, missing)
    report: OptimizationReport = adapter.optimize(formulation, flowsheet, readiness)
    return report
