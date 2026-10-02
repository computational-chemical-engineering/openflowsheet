"""The common SuperLU solve and its linear-residual evidence (specification §9, requirement D03).

The solve runs in the *repository* environment on the matrices each backend exported, so the
solver, its configuration and this code path are identical for both routes; only the matrix
source differs. The backend environments' own SciPy builds are never used for this evidence.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import scipy.sparse as sparse
import scipy.sparse.linalg as sparse_linalg

from benchmarks.p02 import expected as closed_form
from benchmarks.p02.judge import PASS, Check, _entries, load_artifacts
from benchmarks.p02.reference import load_reference

#: The explicit SuperLU configuration, recorded verbatim in the evidence manifest.
SUPERLU_OPTIONS: dict[str, Any] = {
    "permc_spec": "COLAMD",
    "diag_pivot_thresh": 1.0,
    "options": {"Equil": False, "SymmetricMode": False},
}

#: Rows that are affine in the L-form, used by A23.2.
AFFINE_ROWS = ("bal_A", "bal_B", "bal_C", "Vdef", "Ldef", "tspec", "pspec")

Matrix = npt.NDArray[np.float64]


@dataclass(frozen=True)
class SolveRecord:
    """One state's linear-solve evidence."""

    state_id: str
    scaled_linear_residual: float
    condition_scaled: float
    condition_unscaled: float
    recovered_direction_error: float
    affine_rows_after_step: float | None
    message: str = ""


def _dense(entries: Mapping[str, float]) -> Matrix:
    rows = closed_form.EQUATION_IDS_L
    columns = closed_form.VARIABLE_IDS_L
    matrix = np.zeros((len(rows), len(columns)), dtype=np.float64)
    for index, row in enumerate(rows):
        for column_index, column in enumerate(columns):
            matrix[index, column_index] = entries.get(f"{row}|{column}", 0.0)
    return matrix


def _scaling() -> tuple[Matrix, Matrix]:
    row_scales = np.array(
        [closed_form.ROW_SCALES[row] for row in closed_form.EQUATION_IDS_L], dtype=np.float64
    )
    column_scales = np.array(
        [closed_form.COLUMN_SCALES[column] for column in closed_form.VARIABLE_IDS_L],
        dtype=np.float64,
    )
    return row_scales, column_scales


def scaled_matrix(entries: Mapping[str, float]) -> tuple[Matrix, Matrix, Matrix]:
    """Return `J`, `J_s = D_r⁻¹ J D_c`, and the column scales."""
    dense = _dense(entries)
    row_scales, column_scales = _scaling()
    return dense, (dense / row_scales[:, None]) * column_scales[None, :], column_scales


def _factorize(scaled: Matrix) -> Any:
    return sparse_linalg.splu(sparse.csc_matrix(scaled), **SUPERLU_OPTIONS)


def solve_state(entries: Mapping[str, float], rhs: Sequence[float] | None) -> SolveRecord:
    """Factorize one exported matrix and produce its linear evidence."""
    dense, scaled, _ = scaled_matrix(entries)
    row_scales, _ = _scaling()
    factorization = _factorize(scaled)

    direction = np.array(load_reference().directions["u_L"], dtype=np.float64)
    right_hand_side = scaled @ direction
    recovered = factorization.solve(right_hand_side)
    recovery_error = float(np.max(np.abs(recovered - direction)))

    linear_residual = 0.0
    if rhs is not None:
        scaled_rhs = -np.array(rhs, dtype=np.float64) / row_scales
        step = factorization.solve(scaled_rhs)
        residual = scaled @ step - scaled_rhs
        denominator = float(np.max(np.abs(scaled))) * float(np.max(np.abs(step))) + float(
            np.max(np.abs(scaled_rhs))
        )
        linear_residual = float(np.max(np.abs(residual)) / denominator)

    return SolveRecord(
        state_id="",
        scaled_linear_residual=linear_residual,
        condition_scaled=float(np.linalg.cond(scaled)),
        condition_unscaled=float(np.linalg.cond(dense)),
        recovered_direction_error=recovery_error,
        affine_rows_after_step=None,
    )


def newton_step_evidence(
    entries: Mapping[str, float], residual: Sequence[float], x: Mapping[str, float]
) -> tuple[float, float, Matrix]:
    """A23.1 and A23.2: the Newton step, its linear residual, and the affine rows after it."""
    _, scaled, column_scales = scaled_matrix(entries)
    row_scales, _ = _scaling()
    factorization = _factorize(scaled)
    scaled_rhs = -np.array(residual, dtype=np.float64) / row_scales
    step = factorization.solve(scaled_rhs)
    residual_vector = scaled @ step - scaled_rhs
    denominator = float(np.max(np.abs(scaled))) * float(np.max(np.abs(step))) + float(
        np.max(np.abs(scaled_rhs))
    )
    linear_residual = float(np.max(np.abs(residual_vector)) / denominator)

    updated = {
        name: x[name] + column_scales[index] * step[index]
        for index, name in enumerate(closed_form.VARIABLE_IDS_L)
    }
    reference = load_reference()
    parameters = reference.states["S1"].parameters
    after = closed_form.residual_l_form(updated, parameters)
    worst_affine = max(abs(after[row]) / closed_form.ROW_SCALES[row] for row in AFFINE_ROWS)
    return linear_residual, float(worst_affine), step


def evidence(root: Path, backend: str) -> tuple[list[Check], dict[str, Any]]:
    """Produce the A23 checks and the recorded numbers for one backend."""
    artifacts = load_artifacts(root, backend)
    reference = load_reference()
    if not artifacts.jacobians:
        return (
            [
                Check(
                    f"P02.A23.{backend}",
                    "unsupported",
                    "exported matrices",
                    "see §9",
                    None,
                    "no artifacts",
                )
            ],
            {},
        )

    records: dict[str, Any] = {"superlu": SUPERLU_OPTIONS, "states": {}}
    recovery_errors: list[tuple[float, str]] = []
    singular: list[str] = []
    condition_problems: list[str] = []

    for (state_id, form), payload in sorted(artifacts.jacobians.items()):
        if form != "L" or payload["status"] != "ok":
            continue
        entries = _entries(payload)
        try:
            record = solve_state(entries, None)
        except RuntimeError as error:
            singular.append(f"{state_id}: {error}")
            continue
        recovery_errors.append((record.recovered_direction_error, state_id))
        records["states"][state_id] = {
            "condition_scaled": record.condition_scaled,
            "condition_unscaled": record.condition_unscaled,
            "recovered_direction_error": record.recovered_direction_error,
        }
        registered_conditions = dict(
            reference.linear_solve.get("condition_numbers_scaled_L_form", {})
        )
        newton_record = reference.linear_solve.get("S1_perturbed_newton_step", {})
        if "kappa2_scaled_at_x_pert" in newton_record:
            registered_conditions.setdefault("S1p", newton_record["kappa2_scaled_at_x_pert"])
        expected_condition = registered_conditions.get(state_id)
        if expected_condition is not None:
            relative = abs(record.condition_scaled - float(expected_condition)) / float(
                expected_condition
            )
            if relative > 0.01:
                condition_problems.append(
                    f"{state_id}: kappa2 {record.condition_scaled:.4g} vs registered "
                    f"{float(expected_condition):.4g}"
                )

    newton: dict[str, Any] = {}
    perturbed = artifacts.jacobians.get(("S1p", "L"))
    perturbed_residual = artifacts.residuals.get(("S1p", "L"))
    if perturbed and perturbed_residual and perturbed["status"] == "ok":
        # Keyed by name, never by position: the exported column order is asserted by A01, but the
        # perturbed state is a mapping and zipping it against col_ids would depend on both.
        registered = reference.linear_solve["S1_perturbed_newton_step"]["x_pert"]
        state_x = {name: float(registered[name]) for name in closed_form.VARIABLE_IDS_L}
        linear_residual, worst_affine, step = newton_step_evidence(
            _entries(perturbed), perturbed_residual["values"], state_x
        )
        newton = {
            "scaled_linear_residual_inf": linear_residual,
            "affine_rows_after_step_max_abs_over_scale": worst_affine,
            "step_scaled_inf_norm": float(np.max(np.abs(step))),
        }
        records["newton_step"] = newton

    worst_recovery = max(recovery_errors, default=(0.0, ""))
    checks = [
        Check(
            f"P02.A23.1.{backend}",
            PASS if newton and newton["scaled_linear_residual_inf"] <= 1e-14 else "fail",
            "scaled linear residual <= 1e-14",
            "1e-14",
            newton.get("scaled_linear_residual_inf"),
            "Newton step at S1p",
        ),
        Check(
            f"P02.A23.2.{backend}",
            PASS
            if newton and newton["affine_rows_after_step_max_abs_over_scale"] <= 1e-12
            else "fail",
            "affine rows after the step <= 1e-12 s_r",
            "1e-12 s_r",
            newton.get("affine_rows_after_step_max_abs_over_scale"),
            "the affine part of the Jacobian is the exact derivative of the residual",
        ),
        Check(
            f"P02.A23.3.{backend}",
            PASS if worst_recovery[0] <= 1e-11 else "fail",
            "recovered direction error <= 1e-11",
            "1e-11",
            worst_recovery[0],
            f"worst at {worst_recovery[1]}",
        ),
        Check(
            f"P02.A23.4.{backend}",
            PASS if not condition_problems else "fail",
            "condition numbers within 1 percent of the registered values",
            "1 percent",
            len(condition_problems),
            "; ".join(condition_problems[:3]),
        ),
        Check(
            f"P02.A23.5.{backend}",
            PASS if not singular else "fail",
            "no state is singular",
            "typed failure recorded",
            len(singular),
            "; ".join(singular[:3]),
        ),
    ]
    return checks, records


def main() -> int:
    """Print the linear-solve evidence for every backend that produced results."""
    root = Path(__file__).resolve().parents[2] / "spikes" / "p02" / "results"
    for backend in ("casadi", "pyomo"):
        checks, records = evidence(root, backend)
        for check in checks:
            print(f"{check.result:12s} {check.id:24s} {check.value}")
        if records.get("states"):
            print(json.dumps(records, indent=1)[:600])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
