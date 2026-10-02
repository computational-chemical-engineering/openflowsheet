"""The one linear solve, with its evidence. ADR 0004.

Every linear solve on a K03 path goes through `solve_linear`: the 44 x 44 inner block of the
Schur complement, the 3 x 3 reduced tear system, and NUM-02. There is no dense fallback, no
`spsolve`, and no path that skips the record (ADR 0004 D2). A 3 x 3 system is converted to CSC
and factorized like any other, so that every solve in a trace carries the same evidence rather
than the small ones carrying none.

**The recorded residual is the factorization's own.** Iterative refinement is off, because a
refined residual would hide a poor factorization behind a corrected solve; ADR 0004 D3 makes a
poor factorization a typed result instead. Above `1e-12` the solve fails: at n = 44, `n ε` is
about 1e-14 and the measured worst is 1.3e-16, so a residual two decades above the theory means
the factorization is not a factorization of *this* matrix — a corrupted pattern, or a CSC fill
order that permuted it — which is exactly what should stop a Newton.

**`min |U_ii|` is a screen and not a rank test.** Blueprint [A08] puts the rank statement on the
final unregularized Jacobian with a factorization-based condition estimate, and that is K04's. A
small pivot here only sets `linear_suspect`; it never changes the outcome.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Literal

import numpy as np
import numpy.typing as npt
import scipy.sparse as sp
from scipy.sparse.csgraph import structural_rank
from scipy.sparse.linalg import splu

#: ADR 0004 D1.1, verbatim. Recorded once per plan and referenced by later events.
SUPERLU_OPTIONS: Final[Mapping[str, Any]] = {
    "permc_spec": "COLAMD",
    "diag_pivot_thresh": 1.0,
    "relax": 1,
    "panel_size": 10,
    "options": {"Equil": False, "IterRefine": "NOREFINE", "SymmetricMode": False},
}

#: ADR 0004 D3.2.
RESIDUAL_THRESHOLD: Final = 1e-12
#: ADR 0004 D3.4. A screen, never an outcome.
SUSPECT_PIVOT_RATIO: Final = 1e-10

LinearFailureReason = Literal["residual", "exactly_singular"]


class LinearSolveFailedError(RuntimeError):
    """`LINEAR_SOLVE_FAILED`, with the reason ADR 0004 D3 registers.

    The class name carries the `Error` suffix the lint rule wants; the *outcome code* a trace
    records is `LINEAR_SOLVE_FAILED`, which is the specification's vocabulary and is what a
    reader of a `SolveEvent` sees.

    Not a fallback point: nothing is regularized and nothing is re-solved by least squares
    (blueprint §7.7 makes a regularized step a later recovery edge, and never permission to
    discard equations).
    """

    def __init__(self, reason: LinearFailureReason, message: str) -> None:
        super().__init__(message)
        self.reason: LinearFailureReason = reason


@dataclass(frozen=True)
class LinearSolveRecord:
    """What ADR 0004 D3.1 requires on the `SolveEvent` of every solve."""

    residual_normalized: float
    min_abs_u_diagonal: float
    max_abs_u_diagonal: float
    nnz_l: int
    nnz_u: int
    dimension: int
    #: D3.4: `min |U_ii| / max |U_ii| < 1e-10`. Recorded, never acted on.
    linear_suspect: bool
    #: ADR 0004 D1, recorded on the event. Defaulted rather than passed so that a caller cannot
    #: record options it did not use.
    options: Mapping[str, Any] = field(default_factory=lambda: SUPERLU_OPTIONS)


def normalized_residual(
    matrix: sp.csc_matrix,
    solution: npt.NDArray[np.float64],
    rhs: npt.NDArray[np.float64],
) -> float:
    """ADR 0004 D3.1: `‖A x − b‖∞ / (‖A‖max ‖x‖∞ + ‖b‖∞)`.

    The denominator is the scale the numerator is only meaningful against; when it is zero the
    system was `0 x = 0` and the residual is exactly zero rather than undefined.
    """
    numerator = float(np.max(np.abs(matrix @ solution - rhs))) if rhs.size else 0.0
    largest = float(np.max(np.abs(matrix.data))) if matrix.nnz else 0.0
    scale = float(np.max(np.abs(solution))) if solution.size else 0.0
    offset = float(np.max(np.abs(rhs))) if rhs.size else 0.0
    denominator = largest * scale + offset
    return 0.0 if denominator == 0.0 else numerator / denominator


class StructurallySingularError(RuntimeError):
    """A matrix singular for every value its stored pattern can hold; SuperLU never saw it."""


def factorize(csc: sp.csc_matrix) -> Any:
    """`splu` under ADR 0004's options, with D3.3's structural refusal in front of it.

    The **only** call of `splu` in the package (a test pins that). T04 review S5: under ADR
    0004's options (`relax = 1`) SuperLU segfaults on some structurally singular patterns
    (measured: a 42 x 42 of structural rank 8) instead of raising; T05 A28 found the same crash
    in K04's regularity screen (an 18 x 18 target of structural rank 15), which had its own
    `splu` call. ADR 0004 D3.3 as amended 2026-09-25 makes the refusal a precondition of every
    factorization, so it lives here once. The check reads the stored pattern only, so every
    structurally nonsingular matrix is factorized exactly as before. The refusal is a
    `RuntimeError`, which every caller already takes as "exactly singular".
    """
    if csc.shape[0] != csc.shape[1]:
        raise ValueError(f"a factorization needs a square matrix, got {csc.shape}")
    size = csc.shape[0]
    rank = int(structural_rank(csc)) if size else 0
    if rank < size:
        raise StructurallySingularError(f"structurally singular: rank {rank} of {size}")
    return splu(csc, **SUPERLU_OPTIONS)


def solve_linear(
    matrix: sp.spmatrix | npt.NDArray[np.float64],
    rhs: Sequence[float] | npt.NDArray[np.float64],
) -> tuple[npt.NDArray[np.float64], LinearSolveRecord]:
    """Factorize and solve under ADR 0004, returning the solution and its evidence.

    `matrix` is converted to CSC whatever it arrives as, including a dense 3 x 3: D2 is that
    there is one path, so a small system is not quietly solved another way.

    `rhs` may be a single vector `(n,)` or several columns `(n, k)`, and the solution comes
    back the same shape. **One factorization either way** — that is the whole reason the
    multi-column form exists: the Schur complement needs `Ĵ_φu⁻¹ Ĵ_φt`, three columns against
    one 44 x 44 matrix, and calling this function once per column factorized it three times.
    ADR 0004 D2's "one code path" is about the options and the record, but the Consequences
    section costs the factorization once, and the specification's §3.4 says "three solves
    against one factorization" in as many words. The residual recorded for a multi-column solve
    is the worst over the columns, so the record cannot be better than the weakest column.
    """
    solution, record, _ = solve_linear_kept(matrix, rhs)
    return solution, record


class KeptFactorization:
    """The factorization a `solve_linear_kept` call used, kept for later back-solves.

    ADR 0018 C1: the terminal refinement's chord correction `Ĵ_{k−1}⁻¹ F̂(x_k)` is one more
    back-solve against the attempt's last factorization — no new Jacobian and no new
    factorization. Each back-solve is judged and recorded exactly as `solve_linear`'s solve is
    (ADR 0004 D3: the residual against the matrix factorized, the same threshold, the same
    record), so a kept factorization is never a way around the evidence."""

    def __init__(self, matrix: sp.csc_matrix, factorization: Any) -> None:
        self._matrix = matrix
        self._factorization = factorization

    def solve(
        self, rhs: Sequence[float] | npt.NDArray[np.float64]
    ) -> tuple[npt.NDArray[np.float64], LinearSolveRecord]:
        b = np.asarray(rhs, dtype=np.float64)
        shape = self._matrix.shape
        if b.ndim not in (1, 2) or b.shape[0] != shape[0]:
            raise ValueError(f"right-hand side {b.shape} does not match matrix {shape}")
        return _solved(self._matrix, self._factorization, b)


def solve_linear_kept(
    matrix: sp.spmatrix | npt.NDArray[np.float64],
    rhs: Sequence[float] | npt.NDArray[np.float64],
) -> tuple[npt.NDArray[np.float64], LinearSolveRecord, KeptFactorization]:
    """`solve_linear`, also returning the factorization for later back-solves (ADR 0018 C1).

    The solution and the record are `solve_linear`'s bit for bit: it is this function."""
    csc = sp.csc_matrix(matrix)
    b = np.asarray(rhs, dtype=np.float64)
    if csc.shape[0] != csc.shape[1]:
        raise ValueError(f"the linear solve needs a square matrix, got {csc.shape}")
    if b.ndim not in (1, 2) or b.shape[0] != csc.shape[0]:
        raise ValueError(f"right-hand side {b.shape} does not match matrix {csc.shape}")

    try:
        factorization = factorize(csc)
    except StructurallySingularError as error:
        raise LinearSolveFailedError("exactly_singular", str(error)) from None
    except RuntimeError as error:
        # ADR 0004 D3.3. The registered state is NUM-02 at r = 1, where dR/dt is identically 0.
        raise LinearSolveFailedError("exactly_singular", f"SuperLU: {error}") from error

    solution, record = _solved(csc, factorization, b)
    return solution, record, KeptFactorization(csc, factorization)


def _solved(
    csc: sp.csc_matrix, factorization: Any, b: npt.NDArray[np.float64]
) -> tuple[npt.NDArray[np.float64], LinearSolveRecord]:
    """One back-solve against `factorization` of `csc`, with ADR 0004 D3's record and test."""
    solution = np.asarray(factorization.solve(b), dtype=np.float64)
    # `np.min(values, initial=0.0)` would take the minimum *with* 0.0 and so report 0.0 for any
    # positive diagonal, which silently turns the pivot screen into a constant. The empty case is
    # handled explicitly instead.
    diagonal = np.abs(factorization.U.diagonal())
    smallest = float(np.min(diagonal)) if diagonal.size else 0.0
    largest = float(np.max(diagonal)) if diagonal.size else 0.0
    if b.ndim == 1:
        residual = normalized_residual(csc, solution, b)
    else:
        residual = max(
            (normalized_residual(csc, solution[:, k], b[:, k]) for k in range(b.shape[1])),
            default=0.0,
        )

    record = LinearSolveRecord(
        residual_normalized=residual,
        min_abs_u_diagonal=smallest,
        max_abs_u_diagonal=largest,
        nnz_l=int(factorization.L.nnz),
        nnz_u=int(factorization.U.nnz),
        dimension=int(csc.shape[0]),
        linear_suspect=bool(largest > 0.0 and smallest / largest < SUSPECT_PIVOT_RATIO),
    )
    if residual > RESIDUAL_THRESHOLD:
        raise LinearSolveFailedError(
            "residual",
            f"normalized linear residual {residual:.3e} exceeds the registered "
            f"{RESIDUAL_THRESHOLD:g} (ADR 0004 D3.2) on a {csc.shape[0]}x{csc.shape[0]} system; "
            "the factorization is not a factorization of this matrix",
        )
    return solution, record
