"""The verifier's Newton projection: where the fresh-flash categories are judged. ADR 0013 D1.

K04-F9 spec §5.1 (R-059). A Newton solve stops when every row is inside its tolerance, and at
that state a fresh flash of a lifted stream disagrees with the stored split by the lifted block's
amplification of the rows' residual (up to ~200 τ on the A02 family), and a saturated product's
fresh flash sees the kink across its phase boundary. So the certificate path takes **one Newton
step of the very matrix the regularity screen factorized**, from the certified state,

    x̃ = x_final + S_x · δ̂,      Ĵ δ̂ = −F̂,

and judges `energy_balance`, `phase_admissibility` and `independent_split` at `x̃`. The step
removes the first-order error the row tolerance admits and leaves the second-order one (≤ 2.1e-5
of the thresholds over the A02 family); every tolerance is unchanged, and a wrong root — a root of
the compiled rows by construction — projects onto itself and is judged as before (spec §5.6).

**What it reads** (R-016): the certificate's own residual checks, the screen's status, and the
screen's scaled target Jacobian and residual (K04 §7.1, zero-flow forms included; ADR 0008 D2.4's
pairing identity is the screen's), factorized by `numerics.linear.factorize` exactly as the
screen factorizes it. No solver state, no row builder, no kernel.

**Exact zeros are kept.** A molar-flow column that is exactly zero at `x_final` is structural (an
absent component, the pinned side of a single-phase split, a dormant stream): the exact Newton step
is zero on it, and the factorization's roundoff (≤ 2.87e-22 mol/s measured) would otherwise turn
`V = 0.0` into `V ≠ 0` and a branch's `.bubble` check into `.closure`. The discarded magnitude is
returned (`Projection.discarded`) for the tests, never recorded.

**Preconditions and acceptance, in order; the first that fails names the refusal**, and every
category is then judged at `x_final` (today's rule): every residual check passes
(`residual_not_passed`); the screen says `NO_RANK_LOSS_DETECTED` (`regularity_<STATUS>`); the
solve returns a finite step (`linear_solve_failed`); every flow of `x̃` is nonnegative and every
flowing stream's `(T, P)` is inside the provider's domain (`projection_outside_domain`); every
compiled row and zero-flow label at `x̃`, evaluated afresh, passes under the certificate's policy
(`projection_rows_not_passed`).

**The guards route, so they read the routing tolerance** (ADR 0013 Amendment 2): "passes" in
guards 1 and 5 is `|value| ≤ ρ_k` of the row's kind, ρ_k = max(τ_k(policy), τ_k(registered))
(`checks.routing_tolerances`, which the caller passes as `tolerances`). A policy that only
tightens is therefore projected exactly as the registered one; at the registered policy ρ = τ
and the comparisons are today's, on the same floats.

`run_checks` (a partial checkpoint's `CheckReport`, K04 §8.3) never projects: a partial state is
not a converged one (ADR 0013 D5).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, Literal

import numpy as np
import numpy.typing as npt
import scipy.sparse as sp

from openflowsheet.numerics.linear import factorize
from openflowsheet.verify import CheckResult
from openflowsheet.verify.checks import (
    VerifierError,
    is_flow_column,
    label_checks,
    residual_checks,
    stream_of,
)

if TYPE_CHECKING:
    from openflowsheet.verify.zero_flow import ZeroFlowSplit

__all__ = ["PROJECTED_CATEGORIES", "Projection", "project"]

#: Spec §5.1's table and §5.5's record: the categories judged at `x̃` when the projection holds.
PROJECTED_CATEGORIES: Final = ("energy_balance", "phase_admissibility", "independent_split")

JudgedAt = Literal["projection", "final_state"]


@dataclass(frozen=True)
class Projection:
    """Where the fresh-flash categories are judged, and why (spec §5.5)."""

    #: `x̃` when `judged_at` is `"projection"`, else the certified state itself.
    state: Mapping[str, float]
    judged_at: JudgedAt
    #: `""` exactly when `judged_at` is `"projection"`; else the first failing precondition.
    reason: str
    #: The largest `|S_x δ̂|` discarded at an exactly-zero molar-flow column (spec §7, X03).
    #: Evidence for the tests, never a certificate field (spec §12 Q5).
    discarded: float = 0.0

    def as_document(self) -> dict[str, Any]:
        """`transformations.projection`: R0, float-free (spec §5.5)."""
        return {
            "judged_at": self.judged_at,
            "reason": self.reason,
            "categories": list(PROJECTED_CATEGORIES),
        }


def _refused(state: Mapping[str, float], reason: str, discarded: float = 0.0) -> Projection:
    return Projection(state=state, judged_at="final_state", reason=reason, discarded=discarded)


def project(
    target: Any,
    state: Mapping[str, float],
    *,
    residual: Sequence[CheckResult],
    regularity_status: str,
    matrix: sp.csc_matrix,
    scaled_residual: npt.NDArray[np.float64],
    zero_flow: Sequence[ZeroFlowSplit],
    streams: Sequence[str],
    domain: Mapping[str, tuple[float, float]],
    tolerances: Mapping[str, float],
) -> Projection:
    """Spec §5.1 at the certified `state`.

    `target` carries the declaration (`spec`, `compiled`, `context`, `scaling`); `residual` is
    the certificate's residual checks at `state` (the compiled rows and the zero-flow labels);
    `regularity_status`, `matrix` and `scaled_residual` are the screen's, over the columns of
    `target.spec` minus those `zero_flow` removed, in that order; `streams` the flowsheet's;
    `domain` the provider's declared `T` and `P` ranges; and `tolerances` the routing
    tolerances ρ, one per kind (`checks.routing_tolerances`), which guards 1 and 5 read."""
    # 1. The certified rows pass under ρ (precondition 1), re-judged from their values: a check's
    #    own `result` is judged at the policy's τ, which may be tighter (ADR 0013 A2).
    labels = {split.label[0] for split in zero_flow if split.label is not None}
    row_kinds = target.spec.row_kinds
    for check in residual:
        if check.category != "residual":
            continue
        if check.subject in row_kinds:
            kind = row_kinds[check.subject]
        elif check.subject in labels:
            kind = "temperature"
        else:
            raise VerifierError(f"residual check {check.id!r} is neither a row nor a label")
        if check.value is None or not abs(check.value) <= tolerances[kind]:
            return _refused(state, "residual_not_passed")
    # 2. The screen found the matrix regular.
    if regularity_status != "NO_RANK_LOSS_DETECTED":
        return _refused(state, f"regularity_{regularity_status}")

    removed = {column for split in zero_flow for column in split.columns}
    columns = [name for name in target.spec.variable_ids if name not in removed]
    if len(columns) != matrix.shape[1]:
        raise VerifierError(
            f"the projection's columns ({len(columns)}) are not the screened matrix's "
            f"({matrix.shape[1]})"
        )

    # 3. One Newton step with the screen's factorization (defensive after 2).
    try:
        factorization = factorize(sp.csc_matrix(matrix))
        step = -factorization.solve(np.asarray(scaled_residual, dtype=np.float64))
    except (RuntimeError, ValueError):
        return _refused(state, "linear_solve_failed")
    if not bool(np.all(np.isfinite(step))):
        return _refused(state, "linear_solve_failed")

    kinds = target.spec.variable_kinds
    projected: dict[str, float] = {name: float(value) for name, value in state.items()}
    discarded = 0.0
    for index, name in enumerate(columns):
        delta = float(target.scaling.column[name]) * float(step[index])
        if kinds.get(name) == "molar_flow" and state[name] == 0.0:
            # Structural: the exact step is zero here (spec §5.1).
            discarded = max(discarded, abs(delta))
            continue
        projected[name] = float(state[name]) + delta

    # 4. Nonnegative flows, flowing streams inside the provider's domain.
    if any(is_flow_column(name) and value < 0.0 for name, value in projected.items()):
        return _refused(state, "projection_outside_domain", discarded)
    low_t, high_t = domain["T"]
    low_p, high_p = domain["P"]
    for stream in streams:
        carried = stream_of(projected, stream)
        if carried.is_dormant:
            continue
        if not (low_t <= carried.temperature <= high_t and low_p <= carried.pressure <= high_p):
            return _refused(state, "projection_outside_domain", discarded)

    # 5. Every compiled row and label, evaluated afresh at x̃, passes under ρ. A row the compiled
    #    problem cannot evaluate there does not pass.
    try:
        rows, _ = residual_checks(
            target.compiled,
            target.spec,
            projected,
            target.context,
            target.spec.row_kinds,
            tolerances,
        )
    except VerifierError:
        return _refused(state, "projection_rows_not_passed", discarded)
    rows += label_checks(zero_flow, projected, tolerances)
    if not all(check.result == "pass" for check in rows):
        return _refused(state, "projection_rows_not_passed", discarded)

    return Projection(state=projected, judged_at="projection", reason="", discarded=discarded)
