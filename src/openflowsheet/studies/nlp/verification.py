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

Every check is evaluated that can be, and every failure is listed.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Literal

import numpy as np
import numpy.typing as npt

from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
from openflowsheet.numerics.scaling import Scaling
from openflowsheet.studies.nlp.formulation import NlpFormulation, QuadraticExpression
from openflowsheet.studies.sensitivity import (
    TAU_REGIME,
    OutputFunctional,
    SensitivityResult,
    StudyParameter,
)
from openflowsheet.studies.syn001 import (
    solve_certified,
    split_regimes,
    syn001_sensitivity,
    with_pinned,
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
CHECKS: Final = ("V1", "V2", "V3", "V4", "V5", "V6")


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
    """V1-V6 for one candidate decision vector."""

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

    def outcome(self, check: str) -> CheckOutcome:
        return next(item.outcome for item in self.checks if item.check == check)

    @property
    def passed(self) -> bool:
        """V1-V5 all `pass` — the condition for `KKT_POINT_VERIFIED` (spec §8.5)."""
        return all(self.outcome(check) == "pass" for check in CHECKS[:5])

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


def declared_regimes(flowsheet: Syn001Flowsheet, state: Mapping[str, float]) -> dict[str, str]:
    """The regime of every TP split at a verified start: the formulation's declared regimes."""
    return {split.unit_id: str(split.regime) for split in split_regimes(flowsheet, state)}


def verify_candidate(
    flowsheet: Syn001Flowsheet,
    formulation: NlpFormulation,
    decisions: Sequence[float],
    *,
    regimes: Mapping[str, str],
    optimizer_state: Mapping[str, float] | None = None,
) -> CandidateVerification:
    """V1-V6 at `decisions` (spec §8.5). `regimes` are the formulation's declared regimes (the
    start's, `declared_regimes`); `optimizer_state` is the solver's final state by variable id,
    and without it V2 is `not_evaluated` — so such a candidate is never `passed`."""
    values = formulation.decision_values(decisions)
    sheet = with_pinned(flowsheet, values)
    solve = solve_certified(sheet)
    checks: dict[str, VerificationCheck] = {}
    certificate = solve.certificate
    checks["V1"] = VerificationCheck(
        "V1",
        "pass" if solve.verified else "fail",
        {
            "resolve_outcome": solve.outcome,
            "message": solve.message,
            "certificate_status": certificate.verification_status if certificate else None,
        },
    )
    state = solve.final_state
    if state is None:
        for check in CHECKS[1:]:
            checks[check] = VerificationCheck(check, "not_evaluated", {"reason": "no_simulation"})
        return CandidateVerification(
            decisions=values,
            checks=tuple(checks[check] for check in CHECKS),
            objective=None,
            constraint_values={},
            slacks={},
            active_set=(),
            kkt=None,
            certificate_id=None,
            state_sha256=None,
            simulation_state=None,
            sensitivity=None,
        )

    scaling = Scaling.from_spec(sheet.spec())
    checks["V2"] = _gross(scaling, state, optimizer_state)
    constraint_values = {
        constraint.constraint_id: constraint.expression.value(state)
        for constraint in formulation.constraints
    }
    slacks, active, checks["V3"] = _feasibility(formulation, values, constraint_values)
    checks["V4"] = _regimes(sheet, state, regimes)
    sensitivity, kkt, checks["V5"] = _kkt(sheet, solve, formulation, state, active)
    objective = formulation.objective.value(state)
    checks["V6"] = VerificationCheck(
        "V6", "pass", {"objective": objective, "constraint_values": dict(constraint_values)}
    )
    return CandidateVerification(
        decisions=values,
        checks=tuple(checks[check] for check in CHECKS),
        objective=objective,
        constraint_values=constraint_values,
        slacks=slacks,
        active_set=active,
        kkt=kkt,
        certificate_id=certificate.certificate_id if certificate else None,
        state_sha256=certificate.target_state_sha256 if certificate else None,
        simulation_state=dict(state),
        sensitivity=sensitivity,
    )


# -- the checks -----------------------------------------------------------------------------------


def _gross(
    scaling: Scaling,
    state: Mapping[str, float],
    optimizer_state: Mapping[str, float] | None,
) -> VerificationCheck:
    """V2: `‖S_x⁻¹ (x_opt − x_sim)‖_∞ ≤ 1e-6`."""
    if optimizer_state is None:
        return VerificationCheck("V2", "not_evaluated", {"reason": "no optimizer state supplied"})
    worst_name, worst = "", 0.0
    for name, value in state.items():
        difference = abs(optimizer_state[name] - value) / scaling.column[name]
        if difference > worst or not math.isfinite(difference):
            worst_name, worst = name, difference
    return VerificationCheck(
        "V2",
        "pass" if worst <= TAU_GROSS else "fail",
        {"scaled_difference_inf": worst, "worst_variable": worst_name, "threshold": TAU_GROSS},
    )


def _feasibility(
    formulation: NlpFormulation,
    decisions: Mapping[str, float],
    constraint_values: Mapping[str, float],
) -> tuple[dict[str, dict[str, float]], tuple[ActiveConstraint, ...], VerificationCheck]:
    """V3: the box exactly, `ĝ ≥ −τ_feas` on every inequality side, and the active set."""
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
    for constraint in formulation.constraints:
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
    sheet: Syn001Flowsheet, state: Mapping[str, float], declared: Mapping[str, str]
) -> VerificationCheck:
    """V4: every TP split in its declared regime, at least `τ_regime` from the boundary."""
    splits = split_regimes(sheet, state)
    changed = [split.unit_id for split in splits if declared.get(split.unit_id) != split.regime]
    near = [
        split.unit_id for split in splits if split.margin is None or not split.margin >= TAU_REGIME
    ]
    return VerificationCheck(
        "V4",
        "fail" if changed or near else "pass",
        {
            "splits": [split.as_document() for split in splits],
            "declared": dict(declared),
            "regime_changed": changed,
            "inside_tau_regime": near,
            "tau_regime": TAU_REGIME,
        },
    )


def _functional(
    output_id: str, expression: QuadraticExpression, state: Mapping[str, float]
) -> OutputFunctional:
    """The expression's linearization at `state`, as a sensitivity output of scale 1: its
    sensitivity is then the scaled gradient with respect to the decisions."""
    return OutputFunctional(output_id, expression.gradient(state), 1.0)


def _kkt(
    sheet: Syn001Flowsheet,
    solve: Any,
    formulation: NlpFormulation,
    state: Mapping[str, float],
    active: Sequence[ActiveConstraint],
) -> tuple[SensitivityResult | None, KktEvidence | None, VerificationCheck]:
    """V5, from M03's adjoint sensitivities at `x_sim`."""
    if not all(decision.bounded for decision in formulation.decisions):
        return None, None, VerificationCheck("V5", "not_evaluated", {"reason": "bounds_undeclared"})
    parameters = tuple(
        StudyParameter(decision.parameter_id, decision.scale, decision.lower, decision.upper)  # type: ignore[arg-type]
        for decision in formulation.decisions
    )
    outputs = (_functional(OBJECTIVE_OUTPUT, formulation.objective, state),) + tuple(
        _functional(constraint.constraint_id, constraint.expression, state)
        for constraint in formulation.constraints
    )
    sensitivity = syn001_sensitivity(
        sheet,
        solve.result,
        parameters=parameters,
        outputs=outputs,
        mode="adjoint",
        certificate=solve.certificate,
    )
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
    rows = np.array(sensitivity.adjoint.scaled, dtype=np.float64)
    objective_gradient = rows[0]
    gradients = {
        constraint.constraint_id: rows[index]
        for index, constraint in enumerate(formulation.constraints, start=1)
    }
    n = len(formulation.decisions)
    position = {
        decision.parameter_id: index for index, decision in enumerate(formulation.decisions)
    }
    active_rows = []
    for item in active:
        if item.kind == "bound":
            row = np.zeros(n)
            row[position[item.target]] = 1.0
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
