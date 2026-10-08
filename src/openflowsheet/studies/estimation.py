"""Weighted least-squares parameter estimation over pinned inputs, with exact sensitivities and a
rank-based identifiability verdict. M03 spec §7; ADR 0031 D6.

The estimator minimizes `½ Σ_k ((y_k(θ) − y_obs,k)/σ_k)²` with SciPy's `least_squares` (`trf`,
bounds, `x_scale` the parameters' scales). Every residual evaluation is a production solve of the
flowsheet at θ from the registered initializer and a K04 certificate (`VERIFIED` required); the
Jacobian is M03's **forward** sensitivity at that same state (`QUALIFIED` required). Evaluations
are cached on the exact θ tuple (CLAUDE.md: exact caches key on exact inputs). A solve, certificate
or sensitivity refused at an iterate ends the fit `FAILED` with that refusal — there is no fallback
derivative, and `least_squares` is never handed a finite-difference `jac`.

**Identifiability** is decided at θ̂ (and recorded at θ₀) from `J̃ = W^½ J S_θ`, the weighted,
scaled sensitivity matrix — which is exactly the scaled sensitivity `Ŝ` of the measurements when
each measurement's output scale is its σ, so it is read off the sensitivity result directly:

- `rank = #{σ_i > τ_id σ₁}` with `τ_id = 1e-8` (K04's `τ_ill`); `IDENTIFIABLE` iff full rank, else
  `UNIDENTIFIABLE` with each null direction (sign fixed so its largest component is positive);
- a parameter is `determined` iff its component in every null direction is below 1e-6; only a
  determined parameter gets an estimate, and only an identifiable fit gets a covariance
  (`S_θ (J̃ᵀJ̃)⁻¹ S_θ`, the declared-σ basis, not rescaled by χ²/dof);
- a held-out prediction gets a standard error and a normalized residual when the fit is
  identifiable; otherwise it is `determined` iff its scaled gradient is orthogonal to every null
  direction to 1e-3, and an undetermined prediction gets no value.

The report carries the data's evidence class and statement verbatim: data generated from the model
itself verify the machinery; they are not empirical validation. The observations are inputs; this
module contains no noise generator.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Literal

import numpy as np
import numpy.typing as npt
from scipy.optimize import least_squares

from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
from openflowsheet.studies.sensitivity import (
    OutputFunctional,
    SensitivityResult,
    StudyParameter,
)
from openflowsheet.studies.syn001 import (
    CertifiedSolve,
    output_values,
    solve_certified,
    syn001_sensitivity,
    with_pinned,
)

#: Spec §7.4: the identifiability threshold (K04's `τ_ill`, for the same reason).
TAU_ID: Final = 1e-8
#: Spec §7.4: a parameter is determined iff every null direction's component on it is below this.
TAU_DETERMINED: Final = 1e-6
#: Spec §7.4: a prediction is determined iff `|∇̃v · n| ≤ 1e-3 ‖∇̃v‖` for every null direction n.
TAU_PREDICTION: Final = 1e-3
#: Spec §7.3, verbatim: the estimator and its pinned settings.
ESTIMATOR: Final[Mapping[str, Any]] = {
    "function": "scipy.optimize.least_squares",
    "method": "trf",
    "ftol": 1e-14,
    "xtol": 1e-14,
    "gtol": 1e-14,
    "max_nfev": 100,
    "jac": "M03 forward sensitivities (implicit-exact)",
}
COVARIANCE_BASIS: Final = "declared_sigma"

EstimationStatus = Literal["IDENTIFIABLE", "UNIDENTIFIABLE", "FAILED"]
SensitivityFunction = Callable[..., SensitivityResult]


# -- the problem ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Measurement:
    """A measured (or held-out) linear functional of the state, with its declared σ."""

    measurement_id: str
    coefficients: Mapping[str, float]
    sigma: float
    observed: float

    def __post_init__(self) -> None:
        if not (math.isfinite(self.sigma) and self.sigma > 0.0):
            raise ValueError(f"{self.measurement_id}: sigma must be finite and > 0")
        if not math.isfinite(self.observed):
            raise ValueError(f"{self.measurement_id}: the observation must be finite")

    @property
    def output(self) -> OutputFunctional:
        """The measurement as a sensitivity output whose scale is σ, so that its scaled
        sensitivity row is the weighted row of `J̃` (spec §7.4)."""
        return OutputFunctional(self.measurement_id, dict(self.coefficients), self.sigma)

    def as_document(self) -> dict[str, Any]:
        return {
            "id": self.measurement_id,
            "coefficients": dict(self.coefficients),
            "sigma": self.sigma,
            "observed": self.observed,
        }


@dataclass(frozen=True)
class DataProvenance:
    """Where the observations came from, carried into the report verbatim (spec §7.2, A29)."""

    evidence_class: str
    statement: str
    seed: int
    noise_model: Mapping[str, str]
    theta_true: Mapping[str, float]

    def as_document(self) -> dict[str, Any]:
        return {
            "evidence_class": self.evidence_class,
            "statement": self.statement,
            "seed": self.seed,
            "noise_model": dict(self.noise_model),
            "theta_true": dict(self.theta_true),
        }


@dataclass(frozen=True)
class EstimationProblem:
    """A fit of pinned inputs θ (each with its scale and bounds) to measurements."""

    fit_id: str
    flowsheet: Syn001Flowsheet
    parameters: tuple[StudyParameter, ...]
    start: tuple[float, ...]
    measurements: tuple[Measurement, ...]
    validation: tuple[Measurement, ...]
    provenance: DataProvenance

    def __post_init__(self) -> None:
        if len(self.start) != len(self.parameters):
            raise ValueError("one start value per parameter")
        for parameter, value in zip(self.parameters, self.start, strict=True):
            if not parameter.lower < value < parameter.upper:
                raise ValueError(f"{parameter.parameter_id}: the start must be inside the bounds")
        if len(self.measurements) < len(self.parameters):
            raise ValueError("fewer measurements than parameters")
        ids = [item.measurement_id for item in self.measurements + self.validation]
        if len(set(ids)) != len(ids):
            raise ValueError(f"measurement ids repeat: {ids}")


# -- the report -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Identifiability:
    """Spec §7.4 at one θ: the weighted, scaled singular values and the null space."""

    theta: tuple[float, ...]
    singular_values: tuple[float, ...]
    singular_value_ratio: float
    rank: int
    status: Literal["IDENTIFIABLE", "UNIDENTIFIABLE"]
    #: Right singular vectors of the singular values at or below `τ_id σ₁`, scaled coordinates.
    null_directions: tuple[tuple[float, ...], ...]
    right_singular_vectors: tuple[tuple[float, ...], ...]

    def as_document(self) -> dict[str, Any]:
        return {
            "theta": list(self.theta),
            "singular_values_scaled": list(self.singular_values),
            "singular_value_ratio": self.singular_value_ratio,
            "rank": self.rank,
            "tau_id": TAU_ID,
            "status": self.status,
            "null_directions_scaled": [list(vector) for vector in self.null_directions],
            "right_singular_vectors_scaled": [
                list(vector) for vector in self.right_singular_vectors
            ],
        }


@dataclass(frozen=True)
class ParameterEstimate:
    """One parameter at the end of the fit. `estimate` only when `determined`; `standard_error`
    only when the fit is identifiable; `final_iterate` always."""

    parameter_id: str
    final_iterate: float
    determined: bool
    estimate: float | None
    standard_error: float | None
    at_bound: bool

    def as_document(self) -> dict[str, Any]:
        return {
            "id": self.parameter_id,
            "final_iterate": self.final_iterate,
            "determined": self.determined,
            "estimate": self.estimate,
            "standard_error": self.standard_error,
            "at_bound": self.at_bound,
        }


@dataclass(frozen=True)
class Prediction:
    """A held-out output at θ̂ (spec §7.4)."""

    validation_id: str
    observed: float
    sigma: float
    determined: bool
    predicted: float | None
    standard_error: float | None
    normalized_residual: float | None
    #: `max_n |∇̃v · n| / ‖∇̃v‖` over the null directions; `0.0` for an identifiable fit.
    null_projection_relative: float

    def as_document(self) -> dict[str, Any]:
        return {
            "id": self.validation_id,
            "observed": self.observed,
            "sigma": self.sigma,
            "determined": self.determined,
            "predicted": self.predicted,
            "prediction_standard_error": self.standard_error,
            "normalized_residual": self.normalized_residual,
            "null_projection_relative": self.null_projection_relative,
        }


@dataclass(frozen=True)
class FitFailure:
    """Why a fit ended `FAILED`: the stage, the refusal codes, and the iterate it happened at."""

    stage: Literal["solve", "sensitivity", "estimator"]
    codes: tuple[str, ...]
    detail: str
    iterate: tuple[float, ...]

    def as_document(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "codes": list(self.codes),
            "detail": self.detail,
            "iterate": list(self.iterate),
        }


@dataclass(frozen=True)
class EstimationReport:
    """Spec §7.4's `estimation_report`."""

    fit_id: str
    status: EstimationStatus
    problem: EstimationProblem
    failure: FitFailure | None
    estimator_result: Mapping[str, Any]
    evaluations: Mapping[str, int]
    parameters: tuple[ParameterEstimate, ...]
    identifiability: Identifiability | None
    identifiability_at_start: Identifiability | None
    covariance: tuple[tuple[float, ...], ...] | None
    correlation: tuple[tuple[float, ...], ...] | None
    chi2: float | None
    degrees_of_freedom: int | None
    validation: tuple[Prediction, ...]
    certificate_id: str | None
    state_sha256: str | None
    sensitivity_policy_id: str | None
    covariance_basis: str = COVARIANCE_BASIS
    estimator: Mapping[str, Any] = field(default_factory=lambda: dict(ESTIMATOR))

    def estimate(self, parameter_id: str) -> ParameterEstimate:
        return next(item for item in self.parameters if item.parameter_id == parameter_id)

    def prediction(self, validation_id: str) -> Prediction:
        return next(item for item in self.validation if item.validation_id == validation_id)

    def as_document(self) -> dict[str, Any]:
        problem = self.problem
        return {
            "fit_id": self.fit_id,
            "status": self.status,
            **problem.provenance.as_document(),
            "parameters_declared": [
                {
                    "id": parameter.parameter_id,
                    "scale": parameter.scale,
                    "bounds": [parameter.lower, parameter.upper],
                    "start": start,
                }
                for parameter, start in zip(problem.parameters, problem.start, strict=True)
            ],
            "measurements": [item.as_document() for item in problem.measurements],
            "validation_measurements": [item.as_document() for item in problem.validation],
            "estimator": dict(self.estimator),
            "estimator_result": dict(self.estimator_result),
            "evaluations": dict(self.evaluations),
            "failure": self.failure.as_document() if self.failure else None,
            "parameters": [item.as_document() for item in self.parameters],
            "identifiability": (
                self.identifiability.as_document() if self.identifiability else None
            ),
            "identifiability_at_start": (
                self.identifiability_at_start.as_document()
                if self.identifiability_at_start
                else None
            ),
            "covariance_basis": self.covariance_basis,
            "covariance": [list(row) for row in self.covariance] if self.covariance else None,
            "correlation": [list(row) for row in self.correlation] if self.correlation else None,
            "chi2": self.chi2,
            "degrees_of_freedom": self.degrees_of_freedom,
            "validation": [item.as_document() for item in self.validation],
            "certificate_id": self.certificate_id,
            "state_sha256": self.state_sha256,
            "sensitivity_policy_id": self.sensitivity_policy_id,
        }


# -- the fit --------------------------------------------------------------------------------------


class _FitFailedError(Exception):
    def __init__(self, failure: FitFailure) -> None:
        super().__init__(failure.detail)
        self.failure = failure


@dataclass
class _Point:
    """One θ: its certified solve, the measured and held-out outputs, and (lazily) the forward
    sensitivity at the same state."""

    theta: tuple[float, ...]
    sheet: Syn001Flowsheet
    solve: CertifiedSolve
    values: tuple[float, ...]
    sensitivity: SensitivityResult | None = None


class _Evaluator:
    """The exact-θ cache behind `least_squares`'s `fun` and `jac` (spec §7.3)."""

    def __init__(self, problem: EstimationProblem, sensitivity: SensitivityFunction) -> None:
        self.problem = problem
        self.sensitivity_function = sensitivity
        self.outputs = tuple(item.output for item in problem.measurements + problem.validation)
        self.observed = np.array([item.observed for item in problem.measurements])
        self.sigma = np.array([item.sigma for item in problem.measurements])
        self.scales = np.array([parameter.scale for parameter in problem.parameters])
        self.points: dict[tuple[float, ...], _Point] = {}
        self.solves = 0
        self.sensitivities = 0
        self.residual_calls = 0
        self.jacobian_calls = 0

    def point(self, theta: Sequence[float]) -> _Point:
        key = tuple(float(value) for value in theta)
        cached = self.points.get(key)
        if cached is not None:
            return cached
        values = {
            parameter.parameter_id: value
            for parameter, value in zip(self.problem.parameters, key, strict=True)
        }
        sheet = with_pinned(self.problem.flowsheet, values)
        self.solves += 1
        solve = solve_certified(sheet)
        state = solve.final_state
        if not solve.verified or state is None:
            raise _FitFailedError(FitFailure("solve", (solve.outcome,), solve.message, key))
        point = _Point(key, sheet, solve, output_values(state, self.outputs))
        self.points[key] = point
        return point

    def sensitivity(self, point: _Point) -> SensitivityResult:
        if point.sensitivity is None:
            self.sensitivities += 1
            point.sensitivity = self.sensitivity_function(
                point.sheet,
                point.solve.result,
                parameters=self.problem.parameters,
                outputs=self.outputs,
                mode="forward",
                certificate=point.solve.certificate,
            )
        result = point.sensitivity
        if result.status != "QUALIFIED" or result.forward is None:
            raise _FitFailedError(
                FitFailure(
                    "sensitivity",
                    result.refusal_codes,
                    "; ".join(refusal.detail for refusal in result.refusals)
                    or f"sensitivity {result.status}",
                    point.theta,
                )
            )
        return result

    def scaled_sensitivity(self, point: _Point) -> npt.NDArray[np.float64]:
        """`Ŝ` at the point: rows the measurements then the held-out outputs, columns θ."""
        forward = self.sensitivity(point).forward
        assert forward is not None
        return np.array(forward.scaled, dtype=np.float64)

    # -- least_squares's callbacks ---------------------------------------------------------------

    def residuals(self, theta: Sequence[float]) -> npt.NDArray[np.float64]:
        self.residual_calls += 1
        point = self.point(theta)
        measured = np.array(point.values[: len(self.observed)])
        return np.asarray((measured - self.observed) / self.sigma, dtype=np.float64)

    def jacobian(self, theta: Sequence[float]) -> npt.NDArray[np.float64]:
        # `∂f_k/∂θ_j = Ŝ_kj / s_j`: `Ŝ_kj = (∂y_k/∂θ_j) s_j / σ_k` and `f_k = (y_k − y_obs)/σ_k`.
        self.jacobian_calls += 1
        weighted = self.scaled_sensitivity(self.point(theta))[: len(self.observed)]
        return np.asarray(weighted / self.scales, dtype=np.float64)


def estimate(
    problem: EstimationProblem,
    *,
    sensitivity: SensitivityFunction = syn001_sensitivity,
) -> EstimationReport:
    """Fit `problem` (spec §7.3), then judge identifiability and validate (§7.4).

    `sensitivity` is the SYN-001 sensitivity binding; it is replaceable only so that a test can
    force a refusal at a chosen Jacobian evaluation (A30)."""
    evaluator = _Evaluator(problem, sensitivity)
    lower = np.array([parameter.lower for parameter in problem.parameters])
    upper = np.array([parameter.upper for parameter in problem.parameters])
    try:
        fitted = least_squares(
            evaluator.residuals,
            np.array(problem.start, dtype=np.float64),
            jac=evaluator.jacobian,
            bounds=(lower, upper),
            method=ESTIMATOR["method"],
            x_scale=evaluator.scales,
            ftol=ESTIMATOR["ftol"],
            xtol=ESTIMATOR["xtol"],
            gtol=ESTIMATOR["gtol"],
            max_nfev=ESTIMATOR["max_nfev"],
        )
    except _FitFailedError as failed:
        return _failed(problem, evaluator, failed.failure, {})

    summary = {
        "status": int(fitted.status),
        "message": str(fitted.message),
        "success": bool(fitted.success),
        "nfev": int(fitted.nfev),
        "njev": int(fitted.njev) if fitted.njev is not None else None,
        "cost": float(fitted.cost),
        "optimality": float(fitted.optimality),
        "active_mask": [int(value) for value in fitted.active_mask],
    }
    theta_hat = tuple(float(value) for value in fitted.x)
    if fitted.status <= 0:
        # `max_nfev` reached (0) or an improper input (−1): θ̂ is not a converged estimate, and
        # reporting one would be a placeholder success.
        failure = FitFailure(
            "estimator", ("ESTIMATOR_NOT_CONVERGED",), str(fitted.message), theta_hat
        )
        return _failed(problem, evaluator, failure, summary)
    try:
        point = evaluator.point(theta_hat)
        scaled = evaluator.scaled_sensitivity(point)
        start_point = evaluator.point(problem.start)
        start_scaled = evaluator.scaled_sensitivity(start_point)
    except _FitFailedError as failed:
        return _failed(problem, evaluator, failed.failure, summary)

    m = len(problem.measurements)
    j_tilde = scaled[:m]
    verdict = identifiability(theta_hat, j_tilde)
    at_start = identifiability(tuple(problem.start), start_scaled[:m])
    residuals = (np.array(point.values[:m]) - evaluator.observed) / evaluator.sigma
    chi2 = math.fsum(float(value) ** 2 for value in residuals)
    scales = evaluator.scales

    covariance = None
    if verdict.status == "IDENTIFIABLE":
        # `Cov = S_θ (J̃ᵀJ̃)⁻¹ S_θ`, through the SVD: `(J̃ᵀJ̃)⁻¹ = V Σ⁻² Vᵀ`.
        _, singular, vt = np.linalg.svd(j_tilde, full_matrices=False)
        scaled_covariance = (vt.T / singular**2) @ vt
        covariance = scaled_covariance * np.outer(scales, scales)

    estimates = []
    for index, parameter in enumerate(problem.parameters):
        determined = all(abs(vector[index]) < TAU_DETERMINED for vector in verdict.null_directions)
        estimates.append(
            ParameterEstimate(
                parameter_id=parameter.parameter_id,
                final_iterate=theta_hat[index],
                determined=determined,
                estimate=theta_hat[index] if determined else None,
                standard_error=(
                    math.sqrt(float(covariance[index, index])) if covariance is not None else None
                ),
                at_bound=bool(fitted.active_mask[index] != 0),
            )
        )

    correlation = None
    if covariance is not None:
        deviation = np.sqrt(np.diag(covariance))
        correlation = covariance / np.outer(deviation, deviation)

    predictions = []
    for row, item in enumerate(problem.validation, start=m):
        predictions.append(
            _prediction(item, point.values[row], scaled[row], covariance, verdict, scales)
        )

    certificate = point.solve.certificate
    assert certificate is not None and point.sensitivity is not None
    return EstimationReport(
        fit_id=problem.fit_id,
        status=verdict.status,
        problem=problem,
        failure=None,
        estimator_result=summary,
        evaluations=_counts(evaluator),
        parameters=tuple(estimates),
        identifiability=verdict,
        identifiability_at_start=at_start,
        covariance=_rows(covariance),
        correlation=_rows(correlation),
        chi2=chi2,
        degrees_of_freedom=m - verdict.rank,
        validation=tuple(predictions),
        certificate_id=certificate.certificate_id,
        state_sha256=certificate.target_state_sha256,
        sensitivity_policy_id=point.sensitivity.policy_id,
    )


def identifiability(theta: Sequence[float], j_tilde: npt.NDArray[np.float64]) -> Identifiability:
    """Spec §7.4's rank test on the weighted, scaled sensitivity matrix `J̃` (rows measurements)."""
    n = j_tilde.shape[1]
    _, singular, vt = np.linalg.svd(j_tilde, full_matrices=True)
    values = np.zeros(n)
    values[: singular.size] = singular
    largest = float(values[0])
    rank = int(np.count_nonzero(values > TAU_ID * largest)) if largest > 0.0 else 0
    vectors = tuple(_signed(vt[index]) for index in range(n))
    return Identifiability(
        theta=tuple(float(value) for value in theta),
        singular_values=tuple(float(value) for value in values),
        singular_value_ratio=float(values[-1] / largest) if largest > 0.0 else 0.0,
        rank=rank,
        status="IDENTIFIABLE" if rank == n else "UNIDENTIFIABLE",
        null_directions=vectors[rank:],
        right_singular_vectors=vectors,
    )


def _signed(vector: npt.NDArray[np.float64]) -> tuple[float, ...]:
    """Spec §7.4: the sign is fixed so that the largest component is positive."""
    largest = int(np.argmax(np.abs(vector)))
    sign = 1.0 if vector[largest] > 0.0 else -1.0
    return tuple(float(sign * value) + 0.0 for value in vector)


def _prediction(
    item: Measurement,
    value: float,
    scaled_row: npt.NDArray[np.float64],
    covariance: npt.NDArray[np.float64] | None,
    verdict: Identifiability,
    scales: npt.NDArray[np.float64],
) -> Prediction:
    # The held-out output's scale is its σ, so `Ŝ_v σ_v` is `∂v/∂θ · S_θ` (the scaled gradient
    # ∇̃v) and `Ŝ_v σ_v / s_θ` is `∂v/∂θ`.
    scaled_gradient = scaled_row * item.sigma
    if covariance is not None:
        gradient = scaled_gradient / scales
        error = math.sqrt(float(gradient @ covariance @ gradient))
        return Prediction(
            validation_id=item.measurement_id,
            observed=item.observed,
            sigma=item.sigma,
            determined=True,
            predicted=value,
            standard_error=error,
            normalized_residual=(item.observed - value) / math.sqrt(item.sigma**2 + error**2),
            null_projection_relative=0.0,
        )
    norm = float(np.linalg.norm(scaled_gradient))
    projection = max(
        (
            abs(float(scaled_gradient @ np.array(direction))) / norm if norm > 0.0 else 0.0
            for direction in verdict.null_directions
        ),
        default=0.0,
    )
    determined = projection <= TAU_PREDICTION
    return Prediction(
        validation_id=item.measurement_id,
        observed=item.observed,
        sigma=item.sigma,
        determined=determined,
        predicted=value if determined else None,
        standard_error=None,
        normalized_residual=None,
        null_projection_relative=projection,
    )


def _rows(matrix: npt.NDArray[np.float64] | None) -> tuple[tuple[float, ...], ...] | None:
    if matrix is None:
        return None
    return tuple(tuple(float(value) for value in row) for row in matrix)


def _counts(evaluator: _Evaluator) -> dict[str, int]:
    return {
        "residual_calls": evaluator.residual_calls,
        "jacobian_calls": evaluator.jacobian_calls,
        "solves": evaluator.solves,
        "sensitivities": evaluator.sensitivities,
    }


def _failed(
    problem: EstimationProblem,
    evaluator: _Evaluator,
    failure: FitFailure,
    summary: Mapping[str, Any],
) -> EstimationReport:
    return EstimationReport(
        fit_id=problem.fit_id,
        status="FAILED",
        problem=problem,
        failure=failure,
        estimator_result=dict(summary),
        evaluations=_counts(evaluator),
        parameters=(),
        identifiability=None,
        identifiability_at_start=None,
        covariance=None,
        correlation=None,
        chi2=None,
        degrees_of_freedom=None,
        validation=(),
        certificate_id=None,
        state_sha256=None,
        sensitivity_policy_id=None,
    )
