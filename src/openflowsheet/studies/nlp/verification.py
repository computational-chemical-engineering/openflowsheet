"""Verification of an optimization candidate on the re-solved, certified simulation (V1-V6).

M03 spec §8.5; ADR 0032 D3. Termination is not feasibility and stationarity is not optimality: the
**candidate is the decision vector d** a solver returned, and everything claimed about it is
computed on the flowsheet **re-solved at d** by the production solver from the registered
initializer — never on the optimizer's own state or measures:

- **V1** the re-solve converges and its K04 certificate is `VERIFIED`;
- **V2** a gross-error check of the optimizer's state against it (`‖S_x⁻¹(x_opt − x_sim)‖_∞ ≤
  1e-6`; a different branch or a negative-flow pseudo-solution, not a precision claim);
- **V3** the decisions inside their box exactly, every inequality `ĝ ≥ −τ_feas` on `x_sim`, the
  constraint values, slacks and the active set;
- **V4** every TP split in the formulation's (the start's) regime with margin `≥ τ_regime`;
- **V5** a reduced KKT check independent of the optimizer: the scaled gradients of the objective
  and of every constraint with respect to the decisions from M03's **adjoint** sensitivities at
  `x_sim` (`QUALIFIED` required); multipliers by least squares on the active set; the stationarity
  residual, the multiplier signs and LICQ; second order per spec §8.3;
- **V6** the objective and constraint values, from `x_sim`.

With an assessment (E01 §4.10.3) the objective and constraints may name `assessment:<id>`: its
values come from `program.evaluate(x_sim, d)`, the float reference path (V6); the closure's
admissibility rows are inequalities `adm ≥ 0` checked like any declared one (V3); an output's
gradient is `∇ₓG·X + ∂G/∂d`, `linearize` plus the adjoint (V5); and

- **V7** `program.select(x_sim, d)` returns the held regime, dormancy entries given to the rule
  (exact: a zero flow stays zero), else `ASSESSMENT_REGIME_CHANGED(<entry>)`. A failure leaves the
  candidate unverified, as V2's does. Without an assessment V7 is absent and nothing changes.

Every check is evaluated that can be, and every failure is listed.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Literal

import numpy as np
import numpy.typing as npt

from openflowsheet.assessment.program import Linearization, Refusal
from openflowsheet.assessment.quantities import ASSESSMENT_PREFIX
from openflowsheet.compile.casadi_backend import TwinEvaluationError
from openflowsheet.compile.reference import state_vector
from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
from openflowsheet.numerics.scaling import Scaling
from openflowsheet.studies.nlp.formulation import (
    AssessmentBinding,
    AssessmentClosure,
    InequalityConstraint,
    NlpFormulation,
    QuadraticExpression,
    assessment_closure,
    assessment_twin,
    is_assessment_name,
)
from openflowsheet.studies.nlp.host import (
    CertifiedPoint,
    DecisionRefusedError,
    HeldSystem,
    NlpHost,
    RegimeRecord,
    as_host,
)
from openflowsheet.studies.nlp.phase import PHASE_PREFIX, PhaseRows
from openflowsheet.studies.sensitivity import (
    TAU_REGIME,
    OutputFunctional,
    SensitivityResult,
    StudyParameter,
)

#: Spec §8.5's thresholds.
TAU_GROSS: Final = 1e-6
TAU_FEAS: Final = 1e-8
TAU_ACTIVE: Final = 1e-6
TAU_KKT: Final = 1e-6
TAU_SIGN: Final = 1e-8
TAU_LICQ: Final = 1e-8
#: Spec §8.3: at a vertex every multiplier must exceed this for the critical cone to be {0}.
TAU_VERTEX_MULTIPLIER: Final = 1e-8
#: The output id of the objective's linearization in the V5 sensitivity request.
OBJECTIVE_OUTPUT: Final = "objective"

CheckOutcome = Literal["pass", "fail", "not_evaluated"]
SecondOrder = Literal["not_assessed", "vacuous_at_vertex"]
CHECKS: Final = ("V1", "V2", "V3", "V4", "V5", "V6", "V7")
#: M03's checks; V7 (E01 §4.10.3) is recorded only for a formulation with an assessment.
M03_CHECKS: Final = CHECKS[:6]
#: E01 §4.10.3 V7's code, with the entry as its argument.
REGIME_CHANGED: Final = "ASSESSMENT_REGIME_CHANGED"
#: OPT §4.6 V4's code on a held system, with the unit as its argument.
PHASE_REGIME_CHANGED: Final = "PHASE_REGIME_CHANGED"


def _names_decisions(formulation: NlpFormulation) -> bool:
    """An expression names a decision (OPT §4.3); M03's never do."""
    ids = set(formulation.decision_ids)
    return any(name in ids for name in formulation.variables)


@dataclass(frozen=True)
class VerificationCheck:
    check: str
    outcome: CheckOutcome
    detail: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # The document spreads `detail` beside `check` and `outcome`: a detail key of either name
        # would silently replace the verdict in the serialized record.
        clashing = sorted({"check", "outcome"} & set(self.detail))
        if clashing:
            raise ValueError(f"{self.check}: detail keys {clashing} would overwrite the check")

    def as_document(self) -> dict[str, Any]:
        return {"check": self.check, "outcome": self.outcome, **self.detail}


@dataclass(frozen=True)
class ActiveConstraint:
    """One member of the active set, written as `c(d̂) ≥ 0` in scaled decision coordinates:
    `kind` `constraint` (a declared inequality's `lower` or `upper` side) or `bound` (a decision's
    box)."""

    name: str
    kind: Literal["constraint", "bound"]
    target: str
    side: Literal["lower", "upper"]
    slack: float

    def as_document(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "target": self.target,
            "side": self.side,
            "slack": self.slack,
        }


@dataclass(frozen=True)
class KktEvidence:
    """V5: `∇φ̂ = Σ μ_i ∇ĉ_i` on the active set, in scaled decision coordinates."""

    objective_gradient: tuple[float, ...]
    constraint_gradients: Mapping[str, tuple[float, ...]]
    multipliers: Mapping[str, float]
    stationarity_residual: float
    multipliers_nonnegative: bool
    licq: bool
    licq_singular_values: tuple[float, ...]
    second_order: SecondOrder

    def as_document(self) -> dict[str, Any]:
        return {
            "objective_gradient_scaled": list(self.objective_gradient),
            "constraint_gradients_scaled": {
                name: list(values) for name, values in self.constraint_gradients.items()
            },
            "multipliers": dict(self.multipliers),
            "stationarity_residual_inf": self.stationarity_residual,
            "tau_kkt": TAU_KKT,
            "multipliers_nonnegative": self.multipliers_nonnegative,
            "licq": self.licq,
            "licq_singular_values": list(self.licq_singular_values),
            "second_order": self.second_order,
        }


@dataclass(frozen=True)
class CandidateVerification:
    """V1-V6 (and V7 with an assessment) for one candidate decision vector."""

    decisions: Mapping[str, float]
    checks: tuple[VerificationCheck, ...]
    objective: float | None
    constraint_values: Mapping[str, float]
    slacks: Mapping[str, Mapping[str, float]]
    active_set: tuple[ActiveConstraint, ...]
    kkt: KktEvidence | None
    certificate_id: str | None
    state_sha256: str | None
    simulation_state: Mapping[str, float] | None
    sensitivity: SensitivityResult | None
    #: E01 §4.10.3 V6: the closure's assessment values at `x_sim`; `None` without an assessment.
    assessment_values: Mapping[str, float] | None = None
    #: OPT §4.6: V1's certified re-solve (its bundle, its document); in memory only, never
    #: compared or serialised.
    point: CertifiedPoint | None = field(default=None, compare=False, repr=False)

    def outcome(self, check: str) -> CheckOutcome:
        return next(item.outcome for item in self.checks if item.check == check)

    @property
    def passed(self) -> bool:
        """V1-V5 all `pass`, and V7 where recorded — the condition for `KKT_POINT_VERIFIED`
        (spec §8.5; E01 §4.10.3)."""
        recorded = {item.check for item in self.checks}
        return all(self.outcome(check) == "pass" for check in CHECKS[:5]) and (
            "V7" not in recorded or self.outcome("V7") == "pass"
        )

    @property
    def failures(self) -> tuple[str, ...]:
        return tuple(item.check for item in self.checks if item.outcome == "fail")

    @property
    def active_names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.active_set)

    def as_document(self) -> dict[str, Any]:
        return {
            "decisions": dict(self.decisions),
            "checks": [item.as_document() for item in self.checks],
            "objective": self.objective,
            "constraint_values": dict(self.constraint_values),
            "slacks": {name: dict(values) for name, values in self.slacks.items()},
            "active_set": [item.as_document() for item in self.active_set],
            "kkt": self.kkt.as_document() if self.kkt else None,
            "certificate_id": self.certificate_id,
            "state_sha256": self.state_sha256,
        }


def verify_candidate(
    flowsheet: NlpHost | Syn001Flowsheet,
    formulation: NlpFormulation,
    decisions: Sequence[float],
    *,
    regimes: Mapping[str, str],
    optimizer_state: Mapping[str, float] | None = None,
    closure: AssessmentClosure | None = None,
    held: HeldSystem | None = None,
    phase: PhaseRows | None = None,
) -> CandidateVerification:
    """V1-V6 at `decisions` (spec §8.5), and V7 with an assessment (E01 §4.10.3). `regimes` are
    the formulation's declared regimes (the start's, `RegimeRecord.declared`); `optimizer_state` is
    the solver's final state by variable id, and without it V2 is `not_evaluated` — so such a
    candidate is never `passed`. `closure` is the gray box's (`FullSpaceNlp.closure`); without
    it the binding's closure is computed at `x_sim` (the pattern is structural). `flowsheet` is
    an NLP host or a SYN-001 flowsheet (`as_host`); the re-solve is the host's `certify`.

    `held` is the start's held system on a revision host (OPT §4.6): V2 then also compares its
    held columns exactly, and V4 requires the re-solve's attempt signature to equal the start's
    exactly (`PHASE_REGIME_CHANGED(<unit>)` otherwise). Without it (SYN-001) neither is judged.
    An expression may name a decision (OPT §4.3): its value is the decision's, and in V5 its
    derivative is direct, as an assessment output's `∂G/∂d` is.

    `phase` is the start's phase rows (OPT §4.7, the gray box's `FullSpaceNlp.phase`): each is an
    inequality `row ≥ 0` on `x_sim` (float path) in V3 and a candidate of V5's active set by the
    chain rule; a split whose row is active is exempt from V4's margin and is passed to the
    sensitivity as held (Q4's held mode). Without it nothing changes."""
    host = as_host(flowsheet)
    values = formulation.decision_values(decisions)
    try:
        point = host.certify(values)
    except DecisionRefusedError as error:
        # M03 raised the pinning refusal itself here; it still does (the host wraps it).
        raise error.__cause__ or error from None
    binding = formulation.assessment
    names = CHECKS if binding is not None else M03_CHECKS
    checks: dict[str, VerificationCheck] = {}
    certificate = point.certificate
    checks["V1"] = VerificationCheck(
        "V1",
        "pass" if point.verified else "fail",
        {
            "resolve_outcome": point.outcome,
            "message": point.message,
            "certificate_status": certificate.verification_status if certificate else None,
        },
    )
    state = point.state
    # A revision host's held system and regimes exist only at a certified point (OPT §4.2.1):
    # a re-solve that converged without a VERIFIED certificate fails V1 and is judged no further.
    if state is None or (held is not None and not point.verified):
        reason = "no_simulation" if state is None else "resolve_not_certified"
        for check in names[1:]:
            checks[check] = VerificationCheck(check, "not_evaluated", {"reason": reason})
        return CandidateVerification(
            decisions=values,
            checks=tuple(checks[check] for check in names),
            objective=None,
            constraint_values={},
            slacks={},
            active_set=(),
            kkt=None,
            certificate_id=None,
            state_sha256=None,
            simulation_state=None,
            sensitivity=None,
            point=point,
        )

    assert point.spec is not None  # a point with a state was bound
    scaling = Scaling.from_spec(point.spec)
    checks["V2"] = _gross(scaling, state, optimizer_state, held)
    record = host.regimes(point)
    checks["V4"] = _regimes(record, regimes, held, point.signature)
    assessment: _Assessment | None = None
    if binding is not None:
        evaluated = _assessment(point.spec, formulation, binding, state, values, closure)
        checks["V7"] = _regime_held(binding, state, values)
        if isinstance(evaluated, str):
            for check in ("V3", "V5", "V6"):
                checks[check] = VerificationCheck(
                    check, "not_evaluated", {"reason": f"assessment_not_evaluable: {evaluated}"}
                )
            return CandidateVerification(
                decisions=values,
                checks=tuple(checks[check] for check in names),
                objective=None,
                constraint_values={},
                slacks={},
                active_set=(),
                kkt=None,
                certificate_id=certificate.certificate_id if certificate else None,
                state_sha256=certificate.target_state_sha256 if certificate else None,
                simulation_state=dict(state),
                sensitivity=None,
                point=point,
            )
        assessment = evaluated
    resolved = point
    at = state if assessment is None else assessment.point
    if _names_decisions(formulation):
        at = {**at, **values}
    constraints = formulation.constraints if assessment is None else assessment.constraints
    rows: _PhaseTerms | None = None
    if phase is not None and phase.rows:
        found = _phase_terms(point.spec, phase, state, values)
        if isinstance(found, str):
            for check in ("V3", "V5", "V6"):
                checks[check] = VerificationCheck(
                    check, "not_evaluated", {"reason": f"phase_rows_not_evaluable: {found}"}
                )
            return CandidateVerification(
                decisions=values,
                checks=tuple(checks[check] for check in names),
                objective=None,
                constraint_values={},
                slacks={},
                active_set=(),
                kkt=None,
                certificate_id=certificate.certificate_id if certificate else None,
                state_sha256=certificate.target_state_sha256 if certificate else None,
                simulation_state=dict(state),
                sensitivity=None,
                point=point,
            )
        rows = found
        constraints = (*constraints, *rows.constraints)
        at = {**at, **rows.point}
    constraint_values = {
        constraint.constraint_id: constraint.expression.value(at) for constraint in constraints
    }
    slacks, active, checks["V3"] = _feasibility(formulation, constraints, values, constraint_values)
    held_units: tuple[str, ...] = ()
    if phase is not None:
        # OPT §4.6 V4: a split whose phase row is active is recorded, not judged by its margin.
        active_rows = [item.target for item in active if item.target in set(phase.ids)]
        held_units = tuple(phase.row(row).unit for row in active_rows if phase.row(row).split)
        checks["V4"] = _regimes(
            record, regimes, held, point.signature, phase_active=held_units, phase_rows=active_rows
        )
    sensitivity, kkt, checks["V5"] = _kkt(
        host, resolved, formulation, constraints, at, active, assessment, rows, held_units
    )
    objective = formulation.objective.value(at)
    v6: dict[str, Any] = {"objective": objective, "constraint_values": dict(constraint_values)}
    if assessment is not None:
        v6["assessment_values"] = dict(assessment.values)
    checks["V6"] = VerificationCheck("V6", "pass", v6)
    return CandidateVerification(
        decisions=values,
        checks=tuple(checks[check] for check in names),
        objective=objective,
        constraint_values=constraint_values,
        slacks=slacks,
        active_set=active,
        kkt=kkt,
        certificate_id=certificate.certificate_id if certificate else None,
        state_sha256=certificate.target_state_sha256 if certificate else None,
        simulation_state=dict(state),
        sensitivity=sensitivity,
        assessment_values=None if assessment is None else dict(assessment.values),
        point=point,
    )


# -- the assessment (E01 §4.10.3) -----------------------------------------------------------------


@dataclass(frozen=True)
class _Assessment:
    """The assessment at `(x_sim, d)`: the closure's values (float path), the state augmented by
    their `assessment:<id>` names, the constraints with the closure's admissibility rows
    appended (`adm ≥ 0`), and the linearization: `∂y/∂x` by output as `{variable_id: value}`
    and `∂y/∂d` by output in decision order."""

    values: Mapping[str, float]
    point: Mapping[str, float]
    constraints: tuple[InequalityConstraint, ...]
    d_dx: Mapping[str, Mapping[str, float]]
    d_dd: Mapping[str, npt.NDArray[np.float64]]


def _assessment(
    spec: ProblemSpec,
    formulation: NlpFormulation,
    binding: AssessmentBinding,
    state: Mapping[str, float],
    decisions: Mapping[str, float],
    closure: AssessmentClosure | None,
) -> _Assessment | str:
    """The assessment at `x_sim`, or why it cannot be evaluated there."""
    program = binding.program
    decision_ids = formulation.decision_ids
    try:
        if closure is None:
            twin = assessment_twin(binding, spec.variable_ids, decision_ids)
            x = np.array(state_vector(spec, state), dtype=np.float64)
            closure = assessment_closure(binding, twin, x, decisions)
        evaluated = program.evaluate(state, decisions)
        lin = program.linearize(state, decisions, list(closure.output_ids), decision_ids)
    except TwinEvaluationError as error:
        return f"{error}"
    if isinstance(evaluated, Refusal):
        return f"{evaluated.code}({evaluated.target})"
    if isinstance(lin, Refusal):
        return f"{lin.code}({lin.target})"
    assert isinstance(lin, Linearization)
    rows: dict[str, dict[str, float]] = {name: {} for name in closure.output_ids}
    matrix = lin.d_dx
    for j, variable_id in enumerate(matrix.col_ids):
        for k in range(matrix.indptr[j], matrix.indptr[j + 1]):
            rows[matrix.row_ids[matrix.indices[k]]][variable_id] = float(matrix.data[k])
    direct = {name: np.zeros(len(decision_ids)) for name in closure.output_ids}
    matrix = lin.d_dp
    for j in range(len(matrix.col_ids)):
        for k in range(matrix.indptr[j], matrix.indptr[j + 1]):
            direct[matrix.row_ids[matrix.indices[k]]][j] = float(matrix.data[k])
    values = {name: float(evaluated[name]) for name in closure.output_ids}
    admissibility = tuple(
        InequalityConstraint(
            name,
            QuadraticExpression(linear={f"{ASSESSMENT_PREFIX}{name}": 1.0}, text=f"{name} >= 0"),
            lower=0.0,
        )
        for name in closure.admissibility
    )
    return _Assessment(
        values=values,
        point={**state, **{f"{ASSESSMENT_PREFIX}{name}": value for name, value in values.items()}},
        constraints=(*formulation.constraints, *admissibility),
        d_dx=rows,
        d_dd=direct,
    )


@dataclass(frozen=True)
class _PhaseTerms:
    """The phase rows at `(x_sim, d)` (OPT §4.7): their values (float path) under their
    `phase:<id>` names, the inequalities `row ≥ 0`, and their linearization (`∂a/∂x` by row as
    `{variable_id: value}`, `∂a/∂d` in decision order)."""

    point: Mapping[str, float]
    constraints: tuple[InequalityConstraint, ...]
    d_dx: Mapping[str, Mapping[str, float]]
    d_dd: Mapping[str, npt.NDArray[np.float64]]


def _phase_terms(
    spec: ProblemSpec,
    phase: PhaseRows,
    state: Mapping[str, float],
    decisions: Mapping[str, float],
) -> _PhaseTerms | str:
    """The phase rows at `x_sim`, or why they cannot be evaluated there."""
    try:
        evaluated = phase.values(state)
        x = np.array(state_vector(spec, state), dtype=np.float64)
        d_dx, d_dd = phase.linearize(x, decisions)
    except TwinEvaluationError as error:
        return f"{error}"
    constraints = tuple(
        InequalityConstraint(
            name,
            QuadraticExpression(linear={f"{PHASE_PREFIX}{name}": 1.0}, text=f"{name} >= 0"),
            lower=0.0,
        )
        for name in phase.ids
    )
    return _PhaseTerms(
        point={f"{PHASE_PREFIX}{name}": float(evaluated[name]) for name in phase.ids},
        constraints=constraints,
        d_dx=d_dx,
        d_dd=d_dd,
    )


def _regime_held(
    binding: AssessmentBinding, state: Mapping[str, float], decisions: Mapping[str, float]
) -> VerificationCheck:
    """V7: `select(x_sim, d)` with the held regime returns it; dormancy entries (no rows) are
    given to the rule, which compares their flow with 0.0 exactly."""
    program = binding.program
    held = program.regime
    dormant = [entry.entry_id for entry in program.entries if entry.kind == "dormant"]
    try:
        selected = program.select(state, decisions, release=dormant).entries
    except TwinEvaluationError as error:
        return VerificationCheck(
            "V7", "fail", {"reason": f"not evaluable: {error}", "held": dict(held.entries)}
        )
    changed = sorted(
        name
        for name in set(held.entries) | set(selected)
        if held.entries.get(name) != selected.get(name)
    )
    return VerificationCheck(
        "V7",
        "fail" if changed else "pass",
        {
            "regime_sha256": held.sha256,
            "held": dict(held.entries),
            "selected": dict(selected),
            "regime_changed": changed,
            "codes": [f"{REGIME_CHANGED}({name})" for name in changed],
            "dormancy_released": dormant,
        },
    )


# -- the checks -----------------------------------------------------------------------------------


def _gross(
    scaling: Scaling,
    state: Mapping[str, float],
    optimizer_state: Mapping[str, float] | None,
    held: HeldSystem | None = None,
) -> VerificationCheck:
    """V2: `‖S_x⁻¹ (x_opt − x_sim)‖_∞ ≤ 1e-6`; on a held system over its free columns, and its
    held columns equal to the re-solve's exactly (OPT §4.6)."""
    if optimizer_state is None:
        return VerificationCheck("V2", "not_evaluated", {"reason": "no optimizer state supplied"})
    worst_name, worst = "", 0.0
    held_columns = held.held if held is not None else {}
    for name, value in state.items():
        if name in held_columns:
            continue
        difference = abs(optimizer_state[name] - value) / scaling.column[name]
        if difference > worst or not math.isfinite(difference):
            worst_name, worst = name, difference
    detail: dict[str, Any] = {
        "scaled_difference_inf": worst,
        "worst_variable": worst_name,
        "threshold": TAU_GROSS,
    }
    moved: list[str] = []
    if held is not None:
        moved = sorted(name for name, value in held_columns.items() if state[name] != value)
        detail["held_columns"] = len(held_columns)
        detail["held_changed"] = moved
    return VerificationCheck("V2", "pass" if worst <= TAU_GROSS and not moved else "fail", detail)


def _feasibility(
    formulation: NlpFormulation,
    constraints: Sequence[InequalityConstraint],
    decisions: Mapping[str, float],
    constraint_values: Mapping[str, float],
) -> tuple[dict[str, dict[str, float]], tuple[ActiveConstraint, ...], VerificationCheck]:
    """V3: the box exactly, `ĝ ≥ −τ_feas` on every inequality side of `constraints` (the
    formulation's, then an assessment's admissibility rows), and the active set."""
    active: list[ActiveConstraint] = []
    outside_box: list[str] = []
    violated: list[str] = []
    slacks: dict[str, dict[str, float]] = {}
    for decision in formulation.decisions:
        value = decisions[decision.parameter_id]
        for side, bound in (("lower", decision.lower), ("upper", decision.upper)):
            if bound is None or not math.isfinite(bound):
                continue
            slack = (value - bound if side == "lower" else bound - value) / decision.scale
            if slack < 0.0:
                outside_box.append(f"{decision.parameter_id}:{side}")
            if abs(slack) <= TAU_ACTIVE:
                active.append(
                    ActiveConstraint(
                        f"{decision.parameter_id}:{side}",
                        "bound",
                        decision.parameter_id,
                        side,  # type: ignore[arg-type]
                        slack,
                    )
                )
    for constraint in constraints:
        value = constraint_values[constraint.constraint_id]
        sides = [
            (side, bound)
            for side, bound in (("lower", constraint.lower), ("upper", constraint.upper))
            if bound is not None
        ]
        slacks[constraint.constraint_id] = {}
        for side, bound in sides:
            slack = value - bound if side == "lower" else bound - value
            slacks[constraint.constraint_id][side] = slack
            name = (
                constraint.constraint_id
                if len(sides) == 1
                else f"{constraint.constraint_id}:{side}"
            )
            if slack < -TAU_FEAS:
                violated.append(name)
            if abs(slack) <= TAU_ACTIVE:
                active.append(
                    ActiveConstraint(name, "constraint", constraint.constraint_id, side, slack)  # type: ignore[arg-type]
                )
    return (
        slacks,
        tuple(active),
        VerificationCheck(
            "V3",
            "fail" if outside_box or violated else "pass",
            {
                "outside_box": outside_box,
                "violated": violated,
                "tau_feas": TAU_FEAS,
                "tau_active": TAU_ACTIVE,
                "active_set": [item.name for item in active],
            },
        ),
    )


def _regimes(
    record: RegimeRecord,
    declared: Mapping[str, str],
    held: HeldSystem | None = None,
    signature: Any = None,
    *,
    phase_active: Sequence[str] | None = None,
    phase_rows: Sequence[str] = (),
) -> VerificationCheck:
    """V4: every TP split in its declared regime, at least `τ_regime` from the boundary; on a
    held system also the re-solve's attempt signature equal to the start's exactly, else
    `PHASE_REGIME_CHANGED(<unit>)` for each item that differs (OPT §4.6). With phase rows
    (`phase_active` not `None`, OPT §4.7) a split whose row is active is not judged by its
    margin: it and the active rows are recorded under `phase_bounds_active`."""
    splits = record.splits
    changed = [split.unit_id for split in splits if declared.get(split.unit_id) != split.regime]
    exempt = set(phase_active or ())
    near = [
        split.unit_id
        for split in splits
        if (split.margin is None or not split.margin >= TAU_REGIME) and split.unit_id not in exempt
    ]
    detail: dict[str, Any] = {
        "splits": [split.as_document() for split in splits],
        "declared": dict(declared),
        "regime_changed": changed,
        "inside_tau_regime": near,
        "tau_regime": TAU_REGIME,
    }
    moved: list[str] = []
    if held is not None:
        moved = _signature_changes(held.signature, signature)
        detail["held_signature"] = _signature_document(held.signature)
        detail["signature"] = _signature_document(signature)
        detail["phase_regime_changed"] = [f"{PHASE_REGIME_CHANGED}({unit})" for unit in moved]
    if phase_active is not None:
        detail["phase_bounds_active"] = {"units": list(phase_active), "rows": list(phase_rows)}
    return VerificationCheck("V4", "fail" if changed or near or moved else "pass", detail)


def _signature_changes(held: Any, resolved: Any) -> list[str]:
    """The units whose attempt-signature items differ between the start and the re-solve (a
    lifted split's `(unit, regime)` or a dormancy item), in first-appearance order."""
    if held == resolved:
        return []
    before, after = tuple(held or ()), tuple(resolved or ())
    units: list[str] = []
    for item in (*before, *after):
        if (item in before) != (item in after):
            unit = str(item[0]) if isinstance(item, tuple) and item else str(item)
            if unit not in units:
                units.append(unit)
    return units or ["<signature>"]


def _signature_document(signature: Any) -> list[list[str]] | None:
    if signature is None:
        return None
    return [
        [str(part) for part in item] if isinstance(item, tuple) else [str(item)]
        for item in signature
    ]


def _functional(
    output_id: str,
    expression: QuadraticExpression,
    state: Mapping[str, float],
    assessment: _Assessment | None,
    n: int,
    decision_ids: Sequence[str] = (),
    phase: _PhaseTerms | None = None,
) -> tuple[OutputFunctional | None, npt.NDArray[np.float64] | None]:
    """The expression's linearization at `state`, as a sensitivity output of scale 1: its
    sensitivity is then the scaled gradient with respect to the decisions.

    An `assessment:<id>` term enters by the chain rule (E01 §4.10.3 V5): its coefficient times
    `∂y/∂x` joins the functional, and times `∂y/∂d` the direct term returned beside it (`None`
    for an expression without one, whose functional is M03's exactly). The functional is `None`
    when no state variable is left in it. A `phase:<id>` term (OPT §4.7) enters by the chain rule
    as an assessment output's does, from the phase rows' linearization."""
    gradient = expression.gradient(state)
    position = {name: index for index, name in enumerate(decision_ids)}
    named = [
        name
        for name in gradient
        if is_assessment_name(name) or name in position or name.startswith(PHASE_PREFIX)
    ]
    if not named:
        return OutputFunctional(output_id, gradient, 1.0), None
    parts: dict[str, list[float]] = {
        name: [value] for name, value in gradient.items() if name not in set(named)
    }
    direct = np.zeros(n)
    for name in named:
        coefficient = gradient[name]
        if name in position:
            # OPT §4.3: a decision named in an expression; its derivative is direct.
            direct[position[name]] += coefficient
            continue
        terms: _Assessment | _PhaseTerms | None = assessment
        output = name[len(ASSESSMENT_PREFIX) :]
        if name.startswith(PHASE_PREFIX):
            terms, output = phase, name[len(PHASE_PREFIX) :]
        assert terms is not None
        for variable_id, value in terms.d_dx[output].items():
            parts.setdefault(variable_id, []).append(coefficient * value)
        direct += coefficient * terms.d_dd[output]
    coefficients = {name: math.fsum(values) for name, values in parts.items()}
    return (OutputFunctional(output_id, coefficients, 1.0) if coefficients else None), direct


def _kkt(
    nlp_host: NlpHost,
    point: CertifiedPoint,
    formulation: NlpFormulation,
    constraints: Sequence[InequalityConstraint],
    state: Mapping[str, float],
    active: Sequence[ActiveConstraint],
    assessment: _Assessment | None,
    phase: _PhaseTerms | None = None,
    held: Sequence[str] = (),
) -> tuple[SensitivityResult | None, KktEvidence | None, VerificationCheck]:
    """V5, from M03's adjoint sensitivities at `x_sim` (plus `∂G/∂d` for assessment terms);
    `held` are the splits whose phase row is active (Q4's held mode, OPT §4.7)."""
    if not all(decision.bounded for decision in formulation.decisions):
        return None, None, VerificationCheck("V5", "not_evaluated", {"reason": "bounds_undeclared"})
    parameters = tuple(
        StudyParameter(decision.parameter_id, decision.scale, decision.lower, decision.upper)  # type: ignore[arg-type]
        for decision in formulation.decisions
    )
    n = len(formulation.decisions)
    ids = formulation.decision_ids
    built = [
        _functional(OBJECTIVE_OUTPUT, formulation.objective, state, assessment, n, ids, phase)
    ] + [
        _functional(
            constraint.constraint_id, constraint.expression, state, assessment, n, ids, phase
        )
        for constraint in constraints
    ]
    outputs = tuple(functional for functional, _ in built if functional is not None)
    if not outputs:
        return None, None, VerificationCheck("V5", "not_evaluated", {"reason": "state_independent"})
    if held:
        sensitivity = nlp_host.sensitivity(
            point, parameters, outputs, mode="adjoint", held=tuple(held)
        )
    else:
        sensitivity = nlp_host.sensitivity(point, parameters, outputs, mode="adjoint")
    if sensitivity.status != "QUALIFIED" or sensitivity.adjoint is None:
        return (
            sensitivity,
            None,
            VerificationCheck(
                "V5",
                "fail",
                {
                    "sensitivity_status": sensitivity.status,
                    "refusals": list(sensitivity.refusal_codes),
                },
            ),
        )
    host = np.array(sensitivity.adjoint.scaled, dtype=np.float64)
    scales = np.array([decision.scale for decision in formulation.decisions], dtype=np.float64)
    rows: list[npt.NDArray[np.float64]] = []
    position = 0
    for functional, direct in built:
        if functional is not None:
            row = host[position]
            position += 1
        else:
            row = np.zeros(n)
        rows.append(row if direct is None else row + direct * scales)
    objective_gradient = rows[0]
    gradients = {
        constraint.constraint_id: rows[index]
        for index, constraint in enumerate(constraints, start=1)
    }
    position_of = {
        decision.parameter_id: index for index, decision in enumerate(formulation.decisions)
    }
    active_rows = []
    for item in active:
        if item.kind == "bound":
            row = np.zeros(n)
            row[position_of[item.target]] = 1.0
        else:
            row = gradients[item.target].copy()
        active_rows.append(row if item.side == "lower" else -row)
    kkt = _stationarity(objective_gradient, active_rows, active, gradients)
    passed = kkt.stationarity_residual <= TAU_KKT and kkt.multipliers_nonnegative and kkt.licq
    return (
        sensitivity,
        kkt,
        VerificationCheck(
            "V5",
            "pass" if passed else "fail",
            {
                "stationarity_residual_inf": kkt.stationarity_residual,
                "tau_kkt": TAU_KKT,
                "multipliers_nonnegative": kkt.multipliers_nonnegative,
                "licq": kkt.licq,
                "second_order": kkt.second_order,
                "sensitivity_status": sensitivity.status,
            },
        ),
    )


def _stationarity(
    objective_gradient: npt.NDArray[np.float64],
    active_rows: Sequence[npt.NDArray[np.float64]],
    active: Sequence[ActiveConstraint],
    gradients: Mapping[str, npt.NDArray[np.float64]],
) -> KktEvidence:
    """`∇φ̂ = Gᵀ μ` by least squares, `G` the active rows (each `∇ĉ_i` of `ĉ_i ≥ 0`)."""
    n = objective_gradient.size
    if active_rows:
        g = np.vstack(active_rows)
        multipliers, *_ = np.linalg.lstsq(g.T, objective_gradient, rcond=None)
        residual = objective_gradient - g.T @ multipliers
        singular = np.linalg.svd(g, compute_uv=False)
        licq = len(active_rows) <= n and float(singular[-1]) >= TAU_LICQ * float(singular[0])
    else:
        multipliers = np.zeros(0)
        residual = objective_gradient
        singular = np.zeros(0)
        licq = True  # an empty active set has linearly independent gradients vacuously
    nonnegative = bool(np.all(multipliers >= -TAU_SIGN))
    vertex = len(active_rows) == n and licq and bool(np.all(multipliers > TAU_VERTEX_MULTIPLIER))
    return KktEvidence(
        objective_gradient=tuple(float(value) for value in objective_gradient),
        constraint_gradients={
            name: tuple(float(value) for value in values) for name, values in gradients.items()
        },
        multipliers={
            item.name: float(value) for item, value in zip(active, multipliers, strict=True)
        },
        stationarity_residual=float(np.max(np.abs(residual))) if residual.size else 0.0,
        multipliers_nonnegative=nonnegative,
        licq=bool(licq),
        licq_singular_values=tuple(float(value) for value in singular),
        second_order="vacuous_at_vertex" if vertex else "not_assessed",
    )
