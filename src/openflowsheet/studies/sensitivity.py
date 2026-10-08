"""Implicit parameter sensitivities at a qualified regular root. M03 spec §3; ADR 0031 D1-D4.

At a root `x*` of `F(x; p) = 0` the sensitivity of the outputs `y = C x` to the pinned inputs `p` is
`S = C X` with `F_x X = −F_p` — blueprint §10's "Fₓ xₚ = −Fₚ using the converged Jacobian". Every
part of that sentence is a claim this module checks before it is allowed to publish a number:

- **"F_p"** comes from the parametric twin (spec §3.2), which must reproduce the base problem's
  residual and Jacobian bit for bit at `x*` (Q0′); nothing is differenced (R-010).
- **"a root"** is `‖S_F,K⁻¹ F_K(x*)‖_∞ ≤ τ_root` (Q1) and, where the caller supplies one, a K04
  certificate `VERIFIED` for the same state (Q1′, the SYN-001 study level).
- **"F_x"** is the K04 target — rows `K` (the alias-eliminated rows removed), every column, scaled
  by `S_F,K` and `S_x` — the matrix the [A08] screen judges; it must be `NO_RANK_LOSS_DETECTED`
  (Q2). Residual satisfaction is not regularity (blueprint §8.1): `x² − p` at `p = 0` has residual
  exactly 0 and is refused.
- The eliminated alias rows are not part of the solve, but a direction `X_j` that leaves them is
  the derivative along a direction off the solution set, so each column is checked against them
  (Q3) and refused alone when it fails.
- Within `τ_regime` of a phase boundary the derivative may be one-sided or undefined (blueprint
  §6.3), so the caller's phase-split margins are judged too (Q4, Q4′).

Every failing qualification is listed in the specification's table order; a refused request or
column carries `None`, never zeros and never the values the solve would have produced. Forward and
adjoint solves share **one** factorization (`KeptFactorization.solve_transposed`), and the
regularity screen factorizes what it judges: two factorizations per request, whatever the number of
parameters and outputs (A10).

All products with the output and parameter matrices are sparse-by-dense, so each entry is a fixed
sum over that row's non-zeros: a column's values do not depend on which other columns were
requested (A17 holds them bitwise equal).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Literal

import numpy as np
import numpy.typing as npt
import scipy.sparse as sp

from openflowsheet.canonical import state_sha256
from openflowsheet.compile.casadi_backend import (
    ParameterNotDifferentiableError,
    ParametricTwin,
    TwinEvaluationError,
    TwinMatrix,
    compile_parametric_twin,
)
from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.compiled import (
    CompiledProblem,
    EvaluationContext,
    EvaluationResult,
    JacobianResult,
)
from openflowsheet.numerics.linear import LinearSolveRecord, solve_linear_kept
from openflowsheet.numerics.scaling import Scaling
from openflowsheet.verify.regularity import PAIRING_FIELDS, RegularityEvidence, screen

#: Spec §3.5: the policy every sensitivity result names. A different threshold is a new id.
POLICY_ID: Final = "M03-sensitivity-v1"
#: Q1. K03's `ETA_INNER` precedent; a root error of 1e-10 moves a sensitivity by ~1e-10 relative.
TAU_ROOT: Final = 1e-10
#: Q3. Measured exactly 0.0 for the five registered SYN-001 parameters and 1.0 for each pressure.
TAU_ALIAS: Final = 1e-8
#: Q4 (spec §3.4). The screen notices a phase boundary only at margins ~1e-6; this refuses at
#: 1e-4, while the Jacobian is still demonstrably regular, so the refusal names the boundary.
TAU_REGIME: Final = 1e-4
#: Spec §4.7: the forward/adjoint consistency recorded in mode `both`, `τ_abs + τ_rel max|Ŝ|`.
TAU_CONSISTENCY_ABS: Final = 1e-11
TAU_CONSISTENCY_REL: Final = 1e-10
#: Blueprint §5.2's derivative declaration for the published values.
DERIVATIVE_PROVENANCE: Final = "implicit-exact"

Mode = Literal["forward", "adjoint", "both"]
ResultStatus = Literal["QUALIFIED", "PARTIALLY_QUALIFIED", "REFUSED"]
ColumnStatus = Literal["QUALIFIED", "REFUSED"]
Outcome = Literal["pass", "fail", "not_evaluated", "not_applicable"]
RefusalScope = Literal["request", "column"]
RefusalCode = Literal[
    "IDENTITY_MISMATCH",
    "TWIN_MISMATCH",
    "UNKNOWN_PARAMETER",
    "PARAMETER_NOT_DIFFERENTIABLE",
    "ROOT_NOT_CONVERGED",
    "ROOT_NOT_VERIFIED",
    "UNSUPPORTED_RANK_STRUCTURE",
    "RANK_DEFICIENT",
    "ILL_CONDITIONED",
    "REGULARITY_INCONCLUSIVE",
    "INCONSISTENT_WITH_ELIMINATED_ROWS",
    "PHASE_BOUNDARY",
    "REGIME_MARGIN_UNSUPPORTED",
]
Regime = Literal["LIQUID", "VAPOR", "TWO_PHASE", "ZERO_FLOW"]

#: Spec §3.5's table order, which is the order refusals are listed in.
QUALIFICATIONS: Final = ("Q0", "Q0'", "Q0''", "Q1", "Q1'", "Q2", "Q3", "Q4", "Q4'")

_SCREEN_REFUSAL: Final[Mapping[str, RefusalCode]] = {
    "RANK_DEFICIENT": "RANK_DEFICIENT",
    "ILL_CONDITIONED": "ILL_CONDITIONED",
    "INCONCLUSIVE": "REGULARITY_INCONCLUSIVE",
}


# -- the request -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class StudyParameter:
    """ADR 0031 D1: a pinned input, declared by the study with a finite domain and a scale."""

    parameter_id: str
    scale: float
    lower: float
    upper: float

    def __post_init__(self) -> None:
        if not (math.isfinite(self.scale) and self.scale > 0.0):
            raise ValueError(f"{self.parameter_id}: a scale divides, so it must be finite and > 0")
        if not (
            math.isfinite(self.lower) and math.isfinite(self.upper) and self.lower < self.upper
        ):
            raise ValueError(f"{self.parameter_id}: the domain must be finite with lower < upper")


@dataclass(frozen=True)
class OutputFunctional:
    """Spec §2: an output is a variable, or a linear functional `{variable_id: coefficient}`."""

    output_id: str
    coefficients: Mapping[str, float]
    scale: float

    def __post_init__(self) -> None:
        if not self.coefficients:
            raise ValueError(f"output {self.output_id!r} has no coefficients")
        if not (math.isfinite(self.scale) and self.scale > 0.0):
            raise ValueError(f"output {self.output_id!r}: the scale must be finite and > 0")

    @classmethod
    def of_variable(cls, variable_id: str, scale: float) -> OutputFunctional:
        return cls(output_id=variable_id, coefficients={variable_id: 1.0}, scale=scale)


@dataclass(frozen=True)
class SensitivityRequest:
    """Spec §3.5: a context, the requested parameters, the outputs and a mode (the state is
    passed beside it)."""

    context: EvaluationContext
    parameters: tuple[StudyParameter, ...]
    outputs: tuple[OutputFunctional, ...]
    mode: Mode

    def __post_init__(self) -> None:
        if not self.parameters or not self.outputs:
            raise ValueError("a sensitivity request names at least one parameter and one output")
        for label, ids in (
            ("parameter", [parameter.parameter_id for parameter in self.parameters]),
            ("output", [output.output_id for output in self.outputs]),
        ):
            if len(set(ids)) != len(ids):
                raise ValueError(f"{label} ids repeat: {ids}")
        if self.mode not in ("forward", "adjoint", "both"):
            raise ValueError(f"mode {self.mode!r} is not forward, adjoint or both")

    @property
    def parameter_ids(self) -> tuple[str, ...]:
        return tuple(parameter.parameter_id for parameter in self.parameters)


@dataclass(frozen=True)
class SensitivityHost:
    """What the core needs of a problem: the compiled problem and the spec it was compiled from
    (the twin compiles the same spec), its K03 scales, and the alias-eliminated rows."""

    spec: ProblemSpec
    compiled: CompiledProblem
    scaling: Scaling
    eliminated_rows: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        unknown = sorted(set(self.eliminated_rows) - set(self.spec.equation_ids))
        if unknown:
            raise ValueError(f"eliminated rows {unknown} are not rows of the problem")


@dataclass(frozen=True)
class CertificateEvidence:
    """Q1′'s input: the verdict and the state of a K04 certificate (`SolutionCertificate`)."""

    certificate_id: str
    verification_status: str
    target_state_sha256: str

    @classmethod
    def of(cls, certificate: Any) -> CertificateEvidence:
        return cls(
            certificate_id=certificate.certificate_id,
            verification_status=certificate.verification_status,
            target_state_sha256=certificate.target_state_sha256,
        )


@dataclass(frozen=True)
class SplitRegime:
    """Q4's input for one lifted phase split (spec §3.4): its kind, regime and margin.

    A `PH` split has no M03 margin (`margin` `None`) and is refused `REGIME_MARGIN_UNSUPPORTED`."""

    unit_id: str
    streams: str
    kind: Literal["TP", "PH"]
    regime: Regime | None
    margin: float | None

    def as_document(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "streams": self.streams,
            "kind": self.kind,
            "regime": self.regime,
            "margin": self.margin,
        }


# -- the result ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Refusal:
    """One failing qualification: its code, its scope and what was measured."""

    code: RefusalCode
    scope: RefusalScope
    qualification: str
    detail: str
    parameter_id: str | None = None

    def as_document(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "scope": self.scope,
            "qualification": self.qualification,
            "detail": self.detail,
            "parameter_id": self.parameter_id,
        }


@dataclass(frozen=True)
class QualificationOutcome:
    """One row of spec §3.5's table as it was evaluated at this state."""

    qualification: str
    outcome: Outcome
    detail: Mapping[str, Any] = field(default_factory=dict)

    def as_document(self) -> dict[str, Any]:
        return {"qualification": self.qualification, "outcome": self.outcome, **self.detail}


@dataclass(frozen=True)
class ParameterColumn:
    """A requested parameter, as the result records it."""

    parameter_id: str
    scale: float
    lower: float
    upper: float
    status: ColumnStatus
    #: Q3's scaled tangent residual of the eliminated rows; `None` when Q3 was not evaluated.
    alias_residual: float | None

    def as_document(self) -> dict[str, Any]:
        return {
            "parameter_id": self.parameter_id,
            "scale": self.scale,
            "domain": [self.lower, self.upper],
            "status": self.status,
            "alias_residual": self.alias_residual,
        }


Matrix = tuple[tuple[float | None, ...], ...]


@dataclass(frozen=True)
class SensitivityBlock:
    """Rows are outputs, columns are parameters; `None` where the column (or request) is refused."""

    scaled: Matrix
    unscaled: Matrix

    def as_document(self) -> dict[str, Any]:
        return {
            "scaled": [list(row) for row in self.scaled],
            "unscaled": [list(row) for row in self.unscaled],
        }


@dataclass(frozen=True)
class SensitivityResult:
    """Spec §3.7. The pairing identity is the base evaluation's at `x*`."""

    policy_id: str
    model_version: str
    constants_sha256: str
    state_sha256: str
    phase_signature: Any
    parameters: tuple[ParameterColumn, ...]
    outputs: tuple[OutputFunctional, ...]
    mode: Mode
    status: ResultStatus
    refusals: tuple[Refusal, ...]
    qualification: tuple[QualificationOutcome, ...]
    scaled_residual_inf: float | None
    regularity: RegularityEvidence | None
    splits: tuple[SplitRegime, ...]
    forward: SensitivityBlock | None
    adjoint: SensitivityBlock | None
    #: Mode `both`: `max |Ŝ_fwd − Ŝ_adj|` over the qualified entries, its tolerance and verdict.
    consistency: Mapping[str, Any] | None
    linear_solves: tuple[LinearSolveRecord, ...]
    derivative_provenance: str = DERIVATIVE_PROVENANCE

    def outcome(self, qualification: str) -> QualificationOutcome:
        return next(item for item in self.qualification if item.qualification == qualification)

    @property
    def refusal_codes(self) -> tuple[RefusalCode, ...]:
        return tuple(refusal.code for refusal in self.refusals)

    def as_document(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "identity": {
                "model_version": self.model_version,
                "constants_sha256": self.constants_sha256,
                "state_sha256": self.state_sha256,
                "phase_signature": self.phase_signature,
            },
            "parameters": [column.as_document() for column in self.parameters],
            "outputs": [
                {
                    "output_id": output.output_id,
                    "coefficients": dict(output.coefficients),
                    "scale": output.scale,
                }
                for output in self.outputs
            ],
            "mode": self.mode,
            "status": self.status,
            "refusals": [refusal.as_document() for refusal in self.refusals],
            "qualification": {
                "outcomes": [item.as_document() for item in self.qualification],
                "scaled_residual_inf": self.scaled_residual_inf,
                "regularity": self.regularity.as_document() if self.regularity else None,
                "splits": [split.as_document() for split in self.splits],
                "alias_residuals": {
                    column.parameter_id: column.alias_residual for column in self.parameters
                },
            },
            "forward": self.forward.as_document() if self.forward else None,
            "adjoint": self.adjoint.as_document() if self.adjoint else None,
            "consistency": dict(self.consistency) if self.consistency is not None else None,
            "linear_solves": [
                {
                    "residual_normalized": record.residual_normalized,
                    "min_abs_u_diagonal": record.min_abs_u_diagonal,
                    "max_abs_u_diagonal": record.max_abs_u_diagonal,
                    "nnz_l": record.nnz_l,
                    "nnz_u": record.nnz_u,
                    "dimension": record.dimension,
                    "linear_suspect": record.linear_suspect,
                }
                for record in self.linear_solves
            ],
            "derivative_provenance": self.derivative_provenance,
        }


# -- the core --------------------------------------------------------------------------------------

TwinFactory = Callable[[ProblemSpec, Sequence[str]], ParametricTwin]


def evaluate_sensitivity(
    host: SensitivityHost,
    x: npt.NDArray[np.float64],
    request: SensitivityRequest,
    *,
    certificate: CertificateEvidence | None = None,
    splits: Sequence[SplitRegime] = (),
    twin_factory: TwinFactory = compile_parametric_twin,
) -> SensitivityResult:
    """Spec §3.5-§3.7: qualify the state, then solve once, forward and/or adjoint.

    `certificate` is Q1′'s evidence; `None` means no study-level certificate is required (the
    toys) and Q1′ is recorded `not_applicable`. `splits` are the lifted phase splits at `x` with
    their margins (Q4, Q4′); empty means the problem has none. `twin_factory` is the twin's
    compiler, replaceable only so that a test can hand the guard a twin that is not the base.

    The base problem's `residual` and `jacobian` are evaluated once each, and the twin's
    `residual`, `jacobian_x` and `jacobian_p` once each (A03). Nothing is solved by differencing.
    """
    variable_ids = host.spec.variable_ids
    if x.shape != (len(variable_ids),):
        raise ValueError(
            f"state has shape {x.shape}; the problem has {len(variable_ids)} variables"
        )
    known = set(variable_ids)
    for output in request.outputs:
        unknown = sorted(set(output.coefficients) - known)
        if unknown:
            raise ValueError(f"output {output.output_id!r} names unknown variables {unknown}")

    run = _Run(host, x, request, certificate, tuple(splits), twin_factory)
    return run.result()


class _Run:
    """One request's evaluation, in the specification's table order."""

    def __init__(
        self,
        host: SensitivityHost,
        x: npt.NDArray[np.float64],
        request: SensitivityRequest,
        certificate: CertificateEvidence | None,
        splits: tuple[SplitRegime, ...],
        twin_factory: TwinFactory,
    ) -> None:
        self.host = host
        self.x = x
        self.request = request
        self.certificate = certificate
        self.splits = splits
        self.twin_factory = twin_factory
        self.outcomes: dict[str, QualificationOutcome] = {}
        self.refusals: list[Refusal] = []
        eliminated = set(host.eliminated_rows)
        self.kept_rows = tuple(name for name in host.spec.equation_ids if name not in eliminated)
        self.alias_rows = tuple(name for name in host.spec.equation_ids if name in eliminated)

    # -- bookkeeping ---------------------------------------------------------------------------

    def _record(self, qualification: str, outcome: Outcome, **detail: Any) -> None:
        self.outcomes[qualification] = QualificationOutcome(qualification, outcome, detail)

    def _refuse(
        self,
        qualification: str,
        code: RefusalCode,
        detail: str,
        *,
        scope: RefusalScope = "request",
        parameter_id: str | None = None,
    ) -> None:
        self.refusals.append(Refusal(code, scope, qualification, detail, parameter_id))

    # -- the evaluation ------------------------------------------------------------------------

    def result(self) -> SensitivityResult:
        request, metadata = self.request, self.host.compiled.metadata
        identity = {
            "model_version": metadata.model_version,
            "constants_sha256": metadata.constants_sha256,
            "state_sha256": state_sha256(self.x, self.host.spec.variable_ids),
            "phase_signature": request.context.phase_signature,
        }

        # Q0. Refused before any evaluation: under a context that names another problem every
        # number below would describe that problem while claiming this one's identity.
        mismatched = [
            name
            for name in ("model_version", "constants_sha256")
            if getattr(request.context, name) != getattr(metadata, name)
        ]
        if mismatched:
            self._record("Q0", "fail", mismatched=mismatched)
            self._refuse(
                "Q0", "IDENTITY_MISMATCH", f"the context pins a different {', '.join(mismatched)}"
            )
            for qualification in QUALIFICATIONS[1:]:
                self._record(qualification, "not_evaluated", reason="identity_mismatch")
            return self._assemble(identity, None, None, None)
        self._record("Q0", "pass")

        evaluation = self.host.compiled.residual(self.x, request.context)
        jacobian = self.host.compiled.jacobian(self.x, request.context)
        if evaluation.status == "ok":
            identity = {name: getattr(evaluation, name) for name in PAIRING_FIELDS}

        twin = self._twin()
        parameter_jacobian = self._guard(twin, evaluation, jacobian)
        scaled_residual = self._root(evaluation)
        self._certificate(evaluation)
        target, regularity = self._screen(evaluation, jacobian, scaled_residual)

        solved: _Solved | None = None
        if target is not None and parameter_jacobian is not None:
            solved = _solve(self.host, target, jacobian, parameter_jacobian, self.request)
            self._aliases(solved)
        else:
            self._record("Q3", "not_evaluated", reason=_not_evaluated_reason(target, twin))
        self._regimes()
        return self._assemble(identity, scaled_residual, regularity, solved)

    def _twin(self) -> ParametricTwin | None:
        """Q0″: every requested id is a pinned input and the twin builds."""
        parameter_ids = self.request.parameter_ids
        unknown = [name for name in parameter_ids if name not in self.host.spec.parameters]
        if unknown:
            self._record("Q0''", "fail", unknown=unknown)
            self._refuse("Q0''", "UNKNOWN_PARAMETER", f"not pinned inputs: {unknown}")
            return None
        try:
            twin = self.twin_factory(self.host.spec, parameter_ids)
        except ParameterNotDifferentiableError as error:
            self._record(
                "Q0''",
                "fail",
                not_differentiable=list(error.parameter_ids),
                equation_id=error.equation_id,
            )
            for name in error.parameter_ids:
                self._refuse(
                    "Q0''",
                    "PARAMETER_NOT_DIFFERENTIABLE",
                    str(error),
                    parameter_id=name,
                )
            return None
        self._record("Q0''", "pass")
        return twin

    def _guard(
        self,
        twin: ParametricTwin | None,
        evaluation: EvaluationResult,
        jacobian: JacobianResult,
    ) -> TwinMatrix | None:
        """Q0′, spec §3.2: residual and x-Jacobian bitwise equal to the base's at `(x*, p₀)`.

        Returns the parameter Jacobian `F_p` from the same twin, only when the guard passed."""
        if twin is None:
            self._record("Q0'", "not_evaluated", reason="no_twin")
            return None
        if evaluation.status != "ok" or evaluation.values is None or jacobian.status != "ok":
            self._record(
                "Q0'",
                "not_evaluated",
                reason=f"base evaluation {evaluation.status}/{jacobian.status}",
            )
            return None
        p0 = {name: self.host.spec.parameters[name] for name in twin.parameter_ids}
        try:
            twin_residual = _normalized(twin.residual(self.x, p0))
            twin_jacobian = _normalized(_dense(twin.jacobian_x(self.x, p0)))
        except TwinEvaluationError as error:
            self._record("Q0'", "fail", twin_error=str(error))
            self._refuse("Q0'", "TWIN_MISMATCH", f"the twin could not be evaluated: {error}")
            return None
        base_residual = _normalized(evaluation.values)
        base_jacobian = _normalized(_dense(jacobian))
        residual_differs = int(np.count_nonzero(twin_residual != base_residual))
        jacobian_differs = int(np.count_nonzero(twin_jacobian != base_jacobian))
        same_version = twin.model_version == self.host.compiled.metadata.model_version
        if residual_differs or jacobian_differs or not same_version:
            worst = max(
                float(np.max(np.abs(twin_residual - base_residual), initial=0.0)),
                float(np.max(np.abs(twin_jacobian - base_jacobian), initial=0.0)),
            )
            self._record(
                "Q0'",
                "fail",
                residual_entries_differing=residual_differs,
                jacobian_entries_differing=jacobian_differs,
                max_abs_difference=worst,
                model_version_equal=same_version,
            )
            self._refuse(
                "Q0'",
                "TWIN_MISMATCH",
                f"{residual_differs} residual and {jacobian_differs} Jacobian entries differ "
                f"(max {worst:.3e}); model_version equal: {same_version}",
            )
            return None
        self._record("Q0'", "pass", entries_compared=base_residual.size + base_jacobian.size)
        return twin.jacobian_p(self.x, p0)

    def _root(self, evaluation: EvaluationResult) -> npt.NDArray[np.float64] | None:
        """Q1: `‖S_F,K⁻¹ F_K(x*)‖_∞ ≤ τ_root` on the kept rows."""
        if evaluation.status != "ok" or evaluation.values is None:
            self._record("Q1", "fail", residual_status=evaluation.status)
            self._refuse(
                "Q1",
                "ROOT_NOT_CONVERGED",
                f"the residual could not be evaluated: {evaluation.status}: {evaluation.message}",
            )
            return None
        by_id = dict(zip(evaluation.equation_ids, evaluation.values, strict=True))
        row = self.host.scaling.row
        scaled = np.array([by_id[name] / row[name] for name in self.kept_rows])
        norm = float(np.max(np.abs(scaled))) if scaled.size else 0.0
        if norm <= TAU_ROOT:
            self._record("Q1", "pass", scaled_residual_inf=norm, threshold=TAU_ROOT)
        else:
            self._record("Q1", "fail", scaled_residual_inf=norm, threshold=TAU_ROOT)
            self._refuse(
                "Q1", "ROOT_NOT_CONVERGED", f"scaled residual {norm:.3e} > tau_root {TAU_ROOT:g}"
            )
        return scaled

    def _certificate(self, evaluation: EvaluationResult) -> None:
        """Q1′: a K04 certificate `VERIFIED` for the same `state_sha256` (when one is required)."""
        evidence = self.certificate
        if evidence is None:
            self._record("Q1'", "not_applicable", reason="no study-level certificate required")
            return
        state = state_sha256(self.x, self.host.spec.variable_ids)
        if evaluation.status == "ok":
            state = evaluation.state_sha256
        same_state = evidence.target_state_sha256 == state
        verified = evidence.verification_status == "VERIFIED"
        detail = {
            "certificate_id": evidence.certificate_id,
            "verification_status": evidence.verification_status,
            "same_state": same_state,
        }
        if same_state and verified:
            self._record("Q1'", "pass", **detail)
            return
        self._record("Q1'", "fail", **detail)
        reason = (
            f"certificate {evidence.verification_status}"
            if same_state
            else "the certificate is for another state"
        )
        self._refuse("Q1'", "ROOT_NOT_VERIFIED", reason)

    def _screen(
        self,
        evaluation: EvaluationResult,
        jacobian: JacobianResult,
        scaled_residual: npt.NDArray[np.float64] | None,
    ) -> tuple[sp.csc_matrix | None, RegularityEvidence | None]:
        """Q2: K04's screen on the reduced scaled Jacobian, judged for this state's identity.

        Returns the matrix only when the screen found no rank loss — the one it is safe to solve."""
        if self.outcomes["Q1"].outcome != "pass" or scaled_residual is None:
            self._record("Q2", "not_evaluated", reason="root_not_converged")
            return None, None
        if jacobian.status != "ok":
            self._record("Q2", "not_evaluated", reason=f"jacobian {jacobian.status}")
            return None, None
        if len(self.kept_rows) != len(self.host.spec.variable_ids):
            shape = f"{len(self.kept_rows)}x{len(self.host.spec.variable_ids)}"
            self._record("Q2", "fail", reduced_shape=shape)
            self._refuse(
                "Q2",
                "UNSUPPORTED_RANK_STRUCTURE",
                f"the reduced system is {shape}, not square",
            )
            return None, None
        target = _target(self.host, jacobian, self.kept_rows)
        evidence = screen(
            target,
            jacobian_identity={name: getattr(jacobian, name) for name in PAIRING_FIELDS},
            target_identity={name: getattr(evaluation, name) for name in PAIRING_FIELDS},
            scaled_residual=scaled_residual,
        )
        if evidence.status == "NO_RANK_LOSS_DETECTED":
            self._record("Q2", "pass", status=evidence.status, rcond_1=evidence.rcond_1)
            return target, evidence
        self._record(
            "Q2",
            "fail",
            status=evidence.status,
            rcond_1=evidence.rcond_1,
            ill_conditioned_reason=evidence.ill_conditioned_reason,
            inconclusive_reason=evidence.inconclusive_reason,
        )
        reason = evidence.ill_conditioned_reason or evidence.inconclusive_reason
        self._refuse(
            "Q2",
            _SCREEN_REFUSAL[evidence.status],
            f"[A08] screen {evidence.status}" + (f" ({reason})" if reason else ""),
        )
        return None, evidence

    def _aliases(self, solved: _Solved) -> None:
        """Q3, per column: `‖Ĵ_E X̂_j + F̂_p,E,j‖_∞ ≤ τ_alias`."""
        failing = []
        for column, name in enumerate(self.request.parameter_ids):
            residual = solved.alias_residuals[column]
            if residual > TAU_ALIAS:
                failing.append(name)
                self._refuse(
                    "Q3",
                    "INCONSISTENT_WITH_ELIMINATED_ROWS",
                    f"alias residual {residual:.3e} > tau_alias {TAU_ALIAS:g}",
                    scope="column",
                    parameter_id=name,
                )
        self._record(
            "Q3",
            "fail" if failing else "pass",
            eliminated_rows=list(self.alias_rows),
            threshold=TAU_ALIAS,
            refused_columns=failing,
        )

    def _regimes(self) -> None:
        """Q4 and Q4′: every TP split at least `τ_regime` from its boundary; every split TP."""
        tp = [split for split in self.splits if split.kind == "TP"]
        ph = [split for split in self.splits if split.kind != "TP"]
        if not tp:
            self._record("Q4", "not_applicable", reason="no TP-type lifted split")
        else:
            near = [split for split in tp if split.margin is None or not split.margin >= TAU_REGIME]
            self._record(
                "Q4",
                "fail" if near else "pass",
                threshold=TAU_REGIME,
                splits=[split.as_document() for split in tp],
            )
            for split in near:
                self._refuse(
                    "Q4",
                    "PHASE_BOUNDARY",
                    f"{split.unit_id} ({split.streams}) is {split.regime} with margin "
                    f"{split.margin} < tau_regime {TAU_REGIME:g}",
                )
        if not self.splits:
            self._record("Q4'", "not_applicable", reason="no lifted split")
        elif ph:
            self._record("Q4'", "fail", unsupported=[split.unit_id for split in ph])
            for split in ph:
                self._refuse(
                    "Q4'",
                    "REGIME_MARGIN_UNSUPPORTED",
                    f"{split.unit_id} is a {split.kind}-type split; M03 defines no margin for it",
                )
        else:
            self._record("Q4'", "pass")

    # -- the record ----------------------------------------------------------------------------

    def _assemble(
        self,
        identity: Mapping[str, Any],
        scaled_residual: npt.NDArray[np.float64] | None,
        regularity: RegularityEvidence | None,
        solved: _Solved | None,
    ) -> SensitivityResult:
        order = {name: index for index, name in enumerate(QUALIFICATIONS)}
        refusals = tuple(sorted(self.refusals, key=lambda refusal: order[refusal.qualification]))
        request_refused = any(refusal.scope == "request" for refusal in refusals)
        refused_columns = {
            refusal.parameter_id for refusal in refusals if refusal.scope == "column"
        }
        qualified = [
            not request_refused and name not in refused_columns
            for name in self.request.parameter_ids
        ]
        status: ResultStatus
        if not any(qualified):
            status = "REFUSED"
        elif all(qualified):
            status = "QUALIFIED"
        else:
            status = "PARTIALLY_QUALIFIED"

        columns = tuple(
            ParameterColumn(
                parameter_id=parameter.parameter_id,
                scale=parameter.scale,
                lower=parameter.lower,
                upper=parameter.upper,
                status="QUALIFIED" if ok else "REFUSED",
                alias_residual=(
                    float(solved.alias_residuals[index]) if solved is not None else None
                ),
            )
            for index, (parameter, ok) in enumerate(
                zip(self.request.parameters, qualified, strict=True)
            )
        )

        mode = self.request.mode
        forward_scaled = adjoint_scaled = None
        records: tuple[LinearSolveRecord, ...] = ()
        consistency: dict[str, Any] | None = None
        if solved is not None:
            records = (solved.forward_record,)
        if solved is not None and status != "REFUSED":
            if mode in ("forward", "both"):
                forward_scaled = solved.forward
            if mode in ("adjoint", "both"):
                adjoint_scaled, transposed_record = solved.adjoint()
                records = (solved.forward_record, transposed_record)
            if mode == "both" and forward_scaled is not None and adjoint_scaled is not None:
                consistency = _consistency(forward_scaled, adjoint_scaled, qualified)

        def block(values: npt.NDArray[np.float64] | None) -> SensitivityBlock:
            return _block(values, qualified, self.request)

        return SensitivityResult(
            policy_id=POLICY_ID,
            model_version=identity["model_version"],
            constants_sha256=identity["constants_sha256"],
            state_sha256=identity["state_sha256"],
            phase_signature=identity["phase_signature"],
            parameters=columns,
            outputs=self.request.outputs,
            mode=mode,
            status=status,
            refusals=refusals,
            qualification=tuple(self.outcomes[name] for name in QUALIFICATIONS),
            scaled_residual_inf=(
                (float(np.max(np.abs(scaled_residual))) if scaled_residual.size else 0.0)
                if scaled_residual is not None
                else None
            ),
            regularity=regularity,
            splits=self.splits,
            forward=block(forward_scaled) if mode in ("forward", "both") else None,
            adjoint=block(adjoint_scaled) if mode in ("adjoint", "both") else None,
            consistency=consistency,
            linear_solves=records,
        )


# -- linear algebra -------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Solved:
    """The forward solve on the qualified target, and the adjoint it can still do on the same
    factorization."""

    forward: npt.NDArray[np.float64]
    forward_record: LinearSolveRecord
    alias_residuals: npt.NDArray[np.float64]
    adjoint: Callable[[], tuple[npt.NDArray[np.float64], LinearSolveRecord]]


def _solve(
    host: SensitivityHost,
    target: sp.csc_matrix,
    jacobian: JacobianResult,
    parameter_jacobian: TwinMatrix,
    request: SensitivityRequest,
) -> _Solved:
    """Spec §3.6: factorize `Ĵ` once; `Ĵ X̂ = −F̂_p` for every column at once; Q3 on `X̂`."""
    kept = [name for name in host.spec.equation_ids if name not in set(host.eliminated_rows)]
    eliminated = [name for name in host.spec.equation_ids if name in set(host.eliminated_rows)]
    parameter_scales = np.array([parameter.scale for parameter in request.parameters])
    f_p_kept = _scaled_parameter_jacobian(host, parameter_jacobian, kept, parameter_scales)
    rhs = -f_p_kept.toarray()
    solution, record, factorization = solve_linear_kept(target, rhs)

    if eliminated:
        j_e = _scaled_rows(host, jacobian, eliminated)
        f_p_e = _scaled_parameter_jacobian(host, parameter_jacobian, eliminated, parameter_scales)
        tangent = j_e @ solution + f_p_e.toarray()
        alias = np.max(np.abs(tangent), axis=0)
    else:
        alias = np.zeros(len(request.parameters))

    c_hat = _scaled_outputs(host, request)
    forward = np.asarray(c_hat @ solution, dtype=np.float64)

    def adjoint() -> tuple[npt.NDArray[np.float64], LinearSolveRecord]:
        # `Ĵᵀ Λ̂ = −Ĉᵀ` on the same factorization; `Ŝ_adj = Λ̂ᵀ F̂_p = (F̂_pᵀ Λ̂)ᵀ`.
        lam, transposed = factorization.solve_transposed(-c_hat.T.toarray())
        values = np.asarray((sp.csr_matrix(f_p_kept.T) @ lam).T, dtype=np.float64)
        return values, transposed

    return _Solved(forward, record, np.asarray(alias, dtype=np.float64), adjoint)


def _entries(matrix: TwinMatrix | JacobianResult) -> tuple[list[int], list[int], list[float]]:
    rows, columns, data = [], [], []
    for column in range(len(matrix.col_ids)):
        for offset in range(matrix.indptr[column], matrix.indptr[column + 1]):
            rows.append(matrix.indices[offset])
            columns.append(column)
            data.append(matrix.data[offset])
    return rows, columns, data


def _dense(matrix: TwinMatrix | JacobianResult) -> npt.NDArray[np.float64]:
    rows, columns, data = _entries(matrix)
    result = np.zeros((len(matrix.row_ids), len(matrix.col_ids)))
    result[rows, columns] = data
    return result


def _normalized(values: Sequence[float] | npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    """Spec §3.2's signed-zero normalization: `v + 0.0` turns −0.0 into +0.0, nothing else."""
    return np.asarray(values, dtype=np.float64) + 0.0


def _scaled_dense(host: SensitivityHost, jacobian: JacobianResult) -> npt.NDArray[np.float64]:
    """`S_F⁻¹ J S_x` with K04's arithmetic (`assemble_target`), as a dense array."""
    rows, columns, data = _entries(jacobian)
    scaled = host.scaling.scale_jacobian_entries(
        data, rows, columns, jacobian.row_ids, jacobian.col_ids
    )
    return np.asarray(
        sp.csr_matrix(
            (scaled, (rows, columns)), shape=(len(jacobian.row_ids), len(jacobian.col_ids))
        ).toarray(),
        dtype=np.float64,
    )


def _target(
    host: SensitivityHost, jacobian: JacobianResult, kept_rows: Sequence[str]
) -> sp.csc_matrix:
    """Spec §3.3: the K04 target — rows `K`, every column, scaled — bitwise K04's matrix."""
    return _scaled_rows(host, jacobian, kept_rows)


def _scaled_rows(
    host: SensitivityHost, jacobian: JacobianResult, row_ids: Sequence[str]
) -> sp.csc_matrix:
    dense = _scaled_dense(host, jacobian)
    position = {name: index for index, name in enumerate(jacobian.row_ids)}
    return sp.csc_matrix(dense[[position[name] for name in row_ids], :])


def _scaled_parameter_jacobian(
    host: SensitivityHost,
    parameter_jacobian: TwinMatrix,
    row_ids: Sequence[str],
    parameter_scales: npt.NDArray[np.float64],
) -> sp.csc_matrix:
    """`F̂_p = S_F⁻¹ F_p S_p` on `row_ids`, entry by entry and by name."""
    position = {name: index for index, name in enumerate(row_ids)}
    rows, columns, data = [], [], []
    for row, column, value in zip(*_entries(parameter_jacobian), strict=True):
        name = parameter_jacobian.row_ids[row]
        if name in position:
            rows.append(position[name])
            columns.append(column)
            data.append(value * parameter_scales[column] / host.scaling.row[name])
    return sp.csc_matrix(
        (data, (rows, columns)), shape=(len(row_ids), len(parameter_jacobian.col_ids))
    )


def _scaled_outputs(host: SensitivityHost, request: SensitivityRequest) -> sp.csr_matrix:
    """`Ĉ = S_y⁻¹ C S_x`, rows the outputs and columns `variable_ids`."""
    position = {name: index for index, name in enumerate(host.spec.variable_ids)}
    rows, columns, data = [], [], []
    for index, output in enumerate(request.outputs):
        for variable_id, coefficient in output.coefficients.items():
            rows.append(index)
            columns.append(position[variable_id])
            data.append(float(coefficient) * host.scaling.column[variable_id] / output.scale)
    return sp.csr_matrix(
        (data, (rows, columns)), shape=(len(request.outputs), len(host.spec.variable_ids))
    )


def _consistency(
    forward: npt.NDArray[np.float64],
    adjoint: npt.NDArray[np.float64],
    qualified: Sequence[bool],
) -> dict[str, Any]:
    """Blueprint §5.2's `vᵀ(Ju) = (Jᵀv)ᵀu`, entry by entry, over the qualified columns."""
    columns = [index for index, ok in enumerate(qualified) if ok]
    difference = np.abs(forward[:, columns] - adjoint[:, columns])
    worst = float(np.max(difference)) if difference.size else 0.0
    largest = float(np.max(np.abs(forward[:, columns]))) if difference.size else 0.0
    tolerance = TAU_CONSISTENCY_ABS + TAU_CONSISTENCY_REL * largest
    return {
        "max_abs_difference": worst,
        "tolerance": tolerance,
        "within_tolerance": worst <= tolerance,
    }


def _block(
    values: npt.NDArray[np.float64] | None,
    qualified: Sequence[bool],
    request: SensitivityRequest,
) -> SensitivityBlock:
    """`Ŝ` and `S = S_y Ŝ S_p⁻¹`, with `None` in every refused column (or everywhere)."""
    scaled: list[tuple[float | None, ...]] = []
    unscaled: list[tuple[float | None, ...]] = []
    for row, output in enumerate(request.outputs):
        scaled_row: list[float | None] = []
        unscaled_row: list[float | None] = []
        for column, parameter in enumerate(request.parameters):
            if values is None or not qualified[column]:
                scaled_row.append(None)
                unscaled_row.append(None)
                continue
            value = float(values[row, column])
            scaled_row.append(value)
            unscaled_row.append(output.scale * value / parameter.scale)
        scaled.append(tuple(scaled_row))
        unscaled.append(tuple(unscaled_row))
    return SensitivityBlock(tuple(scaled), tuple(unscaled))


def _not_evaluated_reason(target: sp.csc_matrix | None, twin: ParametricTwin | None) -> str:
    if twin is None:
        return "no_twin"
    if target is None:
        return "no_qualified_target"
    return "twin_mismatch"
