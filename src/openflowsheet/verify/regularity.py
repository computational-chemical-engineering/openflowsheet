"""The [A08] regularity screen and the solution-error bound. K04 §7.

**Which matrix.** The scaled target Jacobian after alias elimination: 47 rows (the 49 assembled
rows minus the two eliminated pressure rows) by 47 columns. Not the 3x3 tear derivative, not
the 44x44 inner block, not the rectangular 49x47. [A08]'s words are "the unregularized target
Jacobian for the closed simulation problem after legitimate fixed-variable/alias elimination",
and this is that matrix — the one an equation-oriented Newton would factorize, so its
nonsingularity is what "the root is locally unique" means for the flowsheet. In K03's partition
it is block-triangular after elimination, so it covers the inner block and the tear derivative
at once; either smaller choice would mask a singularity in the other.

**Scaled, and the difference is not cosmetic.** The same matrices unscaled give `rcond` between
9e-12 and 5.9e-11 at the registered solutions — a fixed threshold on the unscaled matrix would
call every correct answer ill-conditioned. [A08] says "recorded scales" for this reason.

**The U-diagonal never decides.** Blueprint [A08] and ADR 0004 D3.4 both say it is an
inexpensive warning screen and not a rank-revealing test; the triangular fixtures below have
`min|U_ii|/max|U_ii|` exactly 1 at every size while being in turn well conditioned,
ill conditioned and rank deficient. It is recorded and ignored.

**And a relative condition number is not enough.** `rcond_1` is scale free, so it says nothing
about whether the *evaluation noise* of the residual, amplified through the Jacobian, stays
inside the tolerance. That is [A08]'s "thresholds account for scales and derivative/evaluation
uncertainty" clause, and §7.4 (amended 2026-09-22) makes it concrete as an **absolute**
conditioning limit: `||J^-1||_1 <= tau_min / (n eps)`. Residual noise is about `n eps`; through
the inverse it becomes `||J^-1|| n eps` in solution terms, and it must stay below the tolerance
or the residual test is measuring nothing.

For SYN-001 (n = 47, tau_min = 1e-8) the limit is 9.58e5 against a measured maximum of 476 —
a margin of 2000. For the plan's `x^2 = 0` seed it has a closed-form bite: K03's Newton stops
at `x = sqrt(tau)`, so `||J^-1|| = 1/(2 sqrt(tau))` against `tau/eps`, and the limit trips only
for very tight tolerances. At `tau = 1e-8` it passes (8192 against 4.5e7) and the verdict is
VERIFIED with the bound `2^-15` *recorded*; at `tau = 1e-12` it trips (524288 against 4503.6)
and the verdict is UNVERIFIED. Measured, the transition sits between 2.5e-11 and 3e-11 — the
specification's closed form `tau^(3/2) < eps` puts it at 3.7e-11, which drops a factor of two
and in any case cannot be exact, because the halving quantizes `x` to a power of two.

**The bound itself is recorded, never a check** (§7.4 as amended). A certificate certifies
residual accuracy; `b` is the disclosure of what that implies for the solution, and a third
required statement says so.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Final, Literal

import numpy as np
import numpy.typing as npt
import scipy.sparse as sp
from scipy.sparse.linalg import LinearOperator, onenormest

from openflowsheet.numerics.linear import SUPERLU_OPTIONS, factorize
from openflowsheet.numerics.scaling import REGISTERED_NOMINALS
from openflowsheet.verify import RegularityStatus
from openflowsheet.verify.zero_flow import ZeroFlowSplit

#: §7.2. Six orders above the Jacobian's own entry error (~n eps, measured 5.3e-15 against
#: closed forms), so nonsingularity is decided rather than guessed; and `kappa <= 1e8` keeps a
#: sensitivity computed from this Jacobian within 1e-6 relative of exact.
TAU_ILL: Final = 1e-8
#: §7.2. Above this the dense SVD is not attempted and the status is `INCONCLUSIVE`, retained.
SVD_DIMENSION_CAP: Final = 2000
#: §5.3: the smallest scaled tolerance in the registered table, at the temperature rows.
TAU_SCALED_MIN: Final = 1e-8
#: T06 spec §8.1 (ADR 0014 D4; register R-069): numpy's legacy global generator is seeded with
#: this around each `onenormest` call, so the estimate is a function of the matrix alone.
ONENORMEST_SEED: Final = 20260925
#: ADR 0008 D2.4's pairing fields: a Jacobian is the target's only if all four are the target's
#: (T06 spec §8.4 (A2), register R-084).
PAIRING_FIELDS: Final = ("model_version", "constants_sha256", "state_sha256", "phase_signature")


def inverse_one_norm_estimate(operator: LinearOperator) -> float:
    """Plan §6.3's `onenormest` (`t = 2`) of `operator`, with numpy's legacy global generator
    saved, seeded with `ONENORMEST_SEED` and restored (T06 spec §8.1).

    scipy draws the estimator's random starting columns from `np.random` with no generator
    argument, so unguarded the estimate — and `rcond₁` and `b` with it — depended on whatever the
    caller had drawn before (M5: C2's `b` took two values over 20 global seeds, C3's three), and
    the call moved the caller's stream. The recipe, the method string, the thresholds and the
    statuses are unchanged; only which of the estimator's answers is returned is now fixed."""
    saved = np.random.get_state()
    try:
        np.random.seed(ONENORMEST_SEED)
        return float(onenormest(operator))
    finally:
        np.random.set_state(saved)


def absolute_conditioning_threshold(
    dimension: int, tau_scaled_min: float = TAU_SCALED_MIN
) -> float:
    """§7.4 as amended: `tau_min / (n eps)`. Residual noise amplified must stay inside tolerance."""
    return tau_scaled_min / (dimension * EPS)


EPS: Final = float(np.finfo(np.float64).eps)


@dataclass(frozen=True)
class RegularityEvidence:
    """§12.3. What the screen recorded, including what it declined to decide."""

    matrix: Literal["target_after_alias_elimination"]
    dimension: int
    nnz: int
    scales_provenance: str
    one_norm: float
    inverse_one_norm_estimate: float
    rcond_1: float | None
    u_diagonal_ratio: float | None
    status: RegularityStatus
    #: `"relative"` when `rcond_1 < tau_ill`, `"absolute"` when the conditioning limit of §7.4
    #: is exceeded. `None` unless the status is `ILL_CONDITIONED`.
    ill_conditioned_reason: str | None = None
    inverse_one_norm_threshold: float | None = None
    solution_error_bound_scaled: float | None = None
    method: Literal["splu_onenormest_rcond1"] = "splu_onenormest_rcond1"
    escalation: dict[str, Any] | None = None
    inconclusive_reason: str | None = None
    factorization_source: Literal["evaluated_at_final_state"] = "evaluated_at_final_state"
    jacobian_identity: dict[str, Any] = field(default_factory=dict)
    derivative_accuracy: str = "exact-ad-double"

    def as_document(self) -> dict[str, Any]:
        return {
            "matrix": self.matrix,
            "dimension": self.dimension,
            "nnz": self.nnz,
            "scales_provenance": self.scales_provenance,
            "method": self.method,
            "superlu_options": dict(SUPERLU_OPTIONS),
            "one_norm": self.one_norm,
            "inverse_one_norm_estimate": self.inverse_one_norm_estimate,
            "rcond_1": self.rcond_1,
            "u_diagonal_ratio": self.u_diagonal_ratio,
            "status": self.status,
            "ill_conditioned_reason": self.ill_conditioned_reason,
            "inverse_one_norm_threshold": self.inverse_one_norm_threshold,
            "solution_error_bound_scaled": self.solution_error_bound_scaled,
            "escalation": self.escalation,
            "inconclusive_reason": self.inconclusive_reason,
            "thresholds": {
                "tau_ill": TAU_ILL,
                "svd_rank_tolerance": "n eps sigma_max",
                "svd_dimension_cap": SVD_DIMENSION_CAP,
            },
            "factorization_source": self.factorization_source,
            "jacobian_identity": dict(self.jacobian_identity),
            "derivative_accuracy": self.derivative_accuracy,
        }


def screen(
    matrix: sp.csc_matrix,
    *,
    scales_provenance: str = "SolvePlan.row_scales and column_scales",
    jacobian_identity: dict[str, Any] | None = None,
    target_identity: Mapping[str, Any] | None = None,
    scaled_residual: npt.NDArray[np.float64] | None = None,
    tau_scaled_min: float = TAU_SCALED_MIN,
) -> RegularityEvidence:
    """§7.2's recipe and §7.3's escalation, on the scaled matrix as given.

    The input is a matrix and never a factorization: §7.5 is that the screen factorizes what it
    is judging. **The identity refusal** (K04 §7.5 and A24's REG-ε, implemented by T06 §8.4 (A2),
    A82; register R-084): given `target_identity` — ADR 0008 D2.4's four `PAIRING_FIELDS` of the
    state being judged — a `jacobian_identity` that is missing, lacks one of the four, or differs
    in any makes the status `INCONCLUSIVE(identity_mismatch)` with `ill_conditioned_reason`
    `None`. Every number is still measured on the matrix given and recorded; the refusal, not
    the matrix, decides the status. That is what stops a regularized or stale matrix (VER-02,
    VER-03) from masking the target's rank loss. Without `target_identity` nothing is compared.
    """
    refused = target_identity is not None and _identity_mismatch(jacobian_identity, target_identity)
    evidence = _measure(
        matrix,
        scales_provenance=scales_provenance,
        jacobian_identity=jacobian_identity,
        scaled_residual=scaled_residual,
        tau_scaled_min=tau_scaled_min,
    )
    if refused:
        return replace(
            evidence,
            status="INCONCLUSIVE",
            inconclusive_reason="identity_mismatch",
            ill_conditioned_reason=None,
        )
    return evidence


def _identity_mismatch(
    jacobian_identity: Mapping[str, Any] | None, target_identity: Mapping[str, Any]
) -> bool:
    """Whether the matrix's identity fails to be the target's on any of D2.4's four fields."""
    incomplete = [name for name in PAIRING_FIELDS if name not in target_identity]
    if incomplete:
        raise ValueError(f"target_identity lacks ADR 0008 D2.4's pairing fields {incomplete}")
    if not jacobian_identity:
        return True
    return any(
        name not in jacobian_identity or jacobian_identity[name] != target_identity[name]
        for name in PAIRING_FIELDS
    )


def _measure(
    matrix: sp.csc_matrix,
    *,
    scales_provenance: str,
    jacobian_identity: dict[str, Any] | None,
    scaled_residual: npt.NDArray[np.float64] | None,
    tau_scaled_min: float,
) -> RegularityEvidence:
    """§7.2's recipe and §7.3's escalation: what the matrix says of itself."""
    csc = sp.csc_matrix(matrix)
    dimension = csc.shape[0]
    if csc.shape[0] != csc.shape[1]:
        raise ValueError(f"the regularity screen needs a square matrix, got {csc.shape}")
    one_norm = float(abs(csc).sum(axis=0).max()) if csc.nnz else 0.0

    common: dict[str, Any] = {
        "matrix": "target_after_alias_elimination",
        "dimension": dimension,
        "nnz": int(csc.nnz),
        "scales_provenance": scales_provenance,
        "one_norm": one_norm,
        "jacobian_identity": dict(jacobian_identity or {}),
    }

    try:
        factorization = factorize(csc)
    except RuntimeError:
        # Exactly singular. The rank is whatever the SVD says; `x^2 = 0` at the root is the
        # registered case and has rank 0.
        return _escalate(
            csc, dict(common, inverse_one_norm_estimate=float("inf"), rcond_1=None), None
        )

    diagonal = np.abs(factorization.U.diagonal())
    smallest = float(np.min(diagonal)) if diagonal.size else 0.0
    largest = float(np.max(diagonal)) if diagonal.size else 0.0
    ratio = (smallest / largest) if largest > 0.0 else None

    operator = LinearOperator(
        csc.shape,
        matvec=lambda b: factorization.solve(b),
        rmatvec=lambda b: factorization.solve(b, trans="T"),
        dtype=np.float64,
    )
    estimate = inverse_one_norm_estimate(operator)
    rcond = None if not np.isfinite(estimate) or estimate == 0.0 else 1.0 / (one_norm * estimate)

    limit = absolute_conditioning_threshold(dimension, tau_scaled_min)
    bound = (
        estimate * float(np.max(np.abs(scaled_residual)))
        if scaled_residual is not None and scaled_residual.size
        else None
    )
    common = dict(
        common,
        inverse_one_norm_estimate=estimate,
        u_diagonal_ratio=ratio,
        rcond_1=rcond,
        inverse_one_norm_threshold=limit,
        solution_error_bound_scaled=bound,
    )

    if rcond is None or not np.isfinite(rcond) or rcond < TAU_ILL:
        return _escalate(csc, common, ratio)

    # §7.4 as amended: the *absolute* limit, which a scale-free `rcond_1` cannot see. Residual
    # evaluation noise is about `n eps`; amplified through the inverse it must stay inside the
    # tolerance, or a passing residual says nothing about the solution.
    if estimate > limit:
        return RegularityEvidence(
            status="ILL_CONDITIONED", ill_conditioned_reason="absolute", **common
        )
    return RegularityEvidence(status="NO_RANK_LOSS_DETECTED", **common)


def _escalate(
    csc: sp.csc_matrix, common: dict[str, Any], ratio: float | None
) -> RegularityEvidence:
    """§7.3: a dense SVD under a budget, and `INCONCLUSIVE` retained rather than guessed."""
    common.setdefault("u_diagonal_ratio", ratio)
    dimension = common["dimension"]
    if dimension > SVD_DIMENSION_CAP:
        return RegularityEvidence(
            status="INCONCLUSIVE",
            inconclusive_reason="svd_budget",
            escalation={
                "performed": False,
                "rank": None,
                "sigma_min": None,
                "sigma_max": None,
                "tolerance": None,
                "cap": SVD_DIMENSION_CAP,
            },
            **common,
        )

    singular = np.linalg.svd(csc.toarray(), compute_uv=False)
    sigma_max = float(singular[0]) if singular.size else 0.0
    tolerance = dimension * EPS * sigma_max
    rank = int(np.count_nonzero(singular > tolerance))
    escalation = {
        "performed": True,
        "rank": rank,
        "sigma_min": float(singular[-1]) if singular.size else 0.0,
        "sigma_max": sigma_max,
        "tolerance": tolerance,
    }
    status: RegularityStatus = "RANK_DEFICIENT" if rank < dimension else "ILL_CONDITIONED"
    if status == "ILL_CONDITIONED":
        common.setdefault("ill_conditioned_reason", "relative")
    return RegularityEvidence(status=status, escalation=escalation, **common)


def solution_error_bound(
    matrix: sp.csc_matrix, scaled_residual: npt.NDArray[np.float64]
) -> float | None:
    """§7.4: `b = ||J^-1||_1 * ||F||_inf` in scaled coordinates. `None` if J is singular.

    It bounds the scaled Newton correction the certified residual still admits, which is the
    quantity a residual tolerance does *not* bound near a singular root. At `x^2 = 0` from
    `x0 = 1` the answer is `2^-15`, three thousand times the scaled tolerance, while the rank
    test reports a perfectly regular matrix — and it is right to.
    """
    csc = sp.csc_matrix(matrix)
    try:
        factorization = factorize(csc)
    except RuntimeError:
        return None
    operator = LinearOperator(
        csc.shape,
        matvec=lambda b: factorization.solve(b),
        rmatvec=lambda b: factorization.solve(b, trans="T"),
        dtype=np.float64,
    )
    estimate = inverse_one_norm_estimate(operator)
    residual_inf = float(np.max(np.abs(scaled_residual))) if scaled_residual.size else 0.0
    return estimate * residual_inf


def target_jacobian(
    tear: Any, state: Any, zero_flow: Sequence[ZeroFlowSplit] = ()
) -> tuple[sp.csc_matrix, npt.NDArray[np.float64], dict[str, Any]]:
    """§7.1: the scaled target Jacobian, the scaled residual and the Jacobian's identity.

    `assemble_target` with the residual's identity left out; see there."""
    assembled = assemble_target(tear, state, zero_flow)
    return assembled.matrix, assembled.scaled_residual, assembled.jacobian_identity


@dataclass(frozen=True)
class TargetAssembly:
    """`assemble_target`'s answer: the matrix and residual, and the identity of each."""

    matrix: sp.csc_matrix
    scaled_residual: npt.NDArray[np.float64]
    #: ADR 0008 D2.4's four `PAIRING_FIELDS` of the `JacobianResult` the matrix was built from.
    jacobian_identity: dict[str, Any]
    #: The same four of the `EvaluationResult` evaluated in the same call — the state the matrix
    #: is judged for, which `screen` takes as `target_identity` (T06 §8.4 (A2)).
    residual_identity: dict[str, Any]


def _pairing_identity(result: Any) -> dict[str, Any]:
    return {name: getattr(result, name) for name in PAIRING_FIELDS}


def assemble_target(
    tear: Any, state: Any, zero_flow: Sequence[ZeroFlowSplit] = ()
) -> TargetAssembly:
    """§7.1: assemble the scaled 47 x 47 target Jacobian and the scaled residual beside it.

    Rows are the 49 assembled rows minus the two `SolvePlan.eliminated_rows`; columns are every
    variable. The residual is returned with it because §7.4's bound needs the two at the *same*
    state, and ADR 0008 D2.4's pairing identity is what makes "the same state" checkable rather
    than assumed.

    With `zero_flow` (T05b spec §9.3; ADR 0012 D7) — the splits whose branch at `state` is
    `ZERO_FLOW` — each is reduced to its zero-flow form after the alias elimination: its pinned
    columns and dropped rows leave, and a PH-type split's label row `T_out − T_label` is appended
    after the compiled rows, in the splits' order, with its two exact entries scaled as a
    temperature row and its value in the scaled residual. Empty (every registered state), the
    matrix and residual are exactly the ones above.
    """
    from openflowsheet.compile.reference import state_vector

    vector = np.array(state_vector(tear.spec, state))
    evaluation = tear.compiled.residual(vector, tear.context)
    jacobian = tear.compiled.jacobian(vector, tear.context)
    if evaluation.status != "ok" or jacobian.status != "ok" or evaluation.values is None:
        raise ValueError(
            f"the target Jacobian could not be assembled: {evaluation.status}/{jacobian.status}"
        )

    rows, columns, data = [], [], []
    for column in range(len(jacobian.col_ids)):
        for offset in range(jacobian.indptr[column], jacobian.indptr[column + 1]):
            rows.append(jacobian.indices[offset])
            columns.append(column)
            data.append(jacobian.data[offset])
    scaled = tear.scaling.scale_jacobian_entries(
        data, rows, columns, jacobian.row_ids, jacobian.col_ids
    )
    dense = sp.csr_matrix(
        (scaled, (rows, columns)), shape=(len(jacobian.row_ids), len(jacobian.col_ids))
    ).toarray()

    eliminated = {row.row_id for row in tear.partition.elimination.eliminated}
    keep = [index for index, name in enumerate(jacobian.row_ids) if name not in eliminated]
    if len(keep) != len(jacobian.col_ids):
        raise ValueError(
            f"the target after alias elimination is {len(keep)}x{len(jacobian.col_ids)} and not "
            "square; UNSUPPORTED_RANK_STRUCTURE"
        )

    residual_by_id = dict(zip(evaluation.equation_ids, evaluation.values, strict=True))
    scaled_residual = np.array(
        [
            residual_by_id[jacobian.row_ids[index]] / tear.scaling.row[jacobian.row_ids[index]]
            for index in keep
        ]
    )
    identity = _pairing_identity(jacobian)
    if evaluation.state_sha256 != jacobian.state_sha256:
        raise ValueError("ADR 0008 D2.4: the residual and the Jacobian are not at the same state")
    if not zero_flow:
        return TargetAssembly(
            sp.csc_matrix(dense[keep, :]), scaled_residual, identity, _pairing_identity(evaluation)
        )
    matrix, residual = _zero_flow_form(
        tear,
        state,
        dense[keep, :],
        [jacobian.row_ids[index] for index in keep],
        list(jacobian.col_ids),
        scaled_residual,
        zero_flow,
    )
    return TargetAssembly(matrix, residual, identity, _pairing_identity(evaluation))


def _zero_flow_form(
    tear: Any,
    state: Any,
    matrix: npt.NDArray[np.float64],
    row_ids: list[str],
    col_ids: list[str],
    scaled_residual: npt.NDArray[np.float64],
    zero_flow: Sequence[ZeroFlowSplit],
) -> tuple[sp.csc_matrix, npt.NDArray[np.float64]]:
    """T05b spec §7.2 on the scaled target: remove each split's columns and rows, append labels."""
    removed_rows = {name for split in zero_flow for name in split.rows}
    removed_columns = {name for split in zero_flow for name in split.columns}
    missing = sorted((removed_rows - set(row_ids)) | (removed_columns - set(col_ids)))
    if missing:
        raise ValueError(f"the zero-flow form names ids the target does not have: {missing}")
    rows = [index for index, name in enumerate(row_ids) if name not in removed_rows]
    columns = [index for index, name in enumerate(col_ids) if name not in removed_columns]
    kept_columns = [col_ids[index] for index in columns]
    position = {name: offset for offset, name in enumerate(kept_columns)}
    reduced = matrix[np.ix_(rows, columns)]
    residual = scaled_residual[rows]
    labels = [split.label for split in zero_flow if split.label is not None]
    if labels:
        scale = REGISTERED_NOMINALS["temperature"]
        extra = np.zeros((len(labels), len(kept_columns)))
        values = np.zeros(len(labels))
        for offset, (_, outlet, source) in enumerate(labels):
            extra[offset, position[outlet]] += tear.scaling.column[outlet] / scale
            extra[offset, position[source]] -= tear.scaling.column[source] / scale
            values[offset] = (state[outlet] - state[source]) / scale
        reduced = np.vstack([reduced, extra])
        residual = np.concatenate([residual, values])
    if reduced.shape[0] != reduced.shape[1]:
        raise ValueError(
            f"the zero-flow form is {reduced.shape[0]}x{reduced.shape[1]} and not square; "
            "UNSUPPORTED_RANK_STRUCTURE"
        )
    return sp.csc_matrix(reduced), np.asarray(residual, dtype=np.float64)
