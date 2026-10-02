"""T05 W13: A21, the certificates of C1, C2 and C3's actual solves; W0.5–W0.7 read off them.

Spec `docs/derivations/T05-unit-models-spec.md` §15 A21, §11.5 (W0.6's bound `<= 1e-8`), §12.6
(T04 F9: a failure is reported, never loosened), §14's derivative-witness row (W0.5) and §19 Q5/Q6;
design note `docs/design/T05-generalization.md` §2.1 step 4 (`verify_revision(binding, document,
run, solve_plan=plan.steps[-1].solve_plan)`) and §4.2–§4.3.

W12 (`tests/test_t05_w12_table.py`) judged the table at the twin's states; this file judges the
states the common path actually converged to (`test_t05_coupled.solve`, policy `T05-W13`). The
§12.2 ids per case are W12's pinned lists (`TABLE_IDS`, written out from the spec); the generic
ids are derived here from the declaration. The measured numbers are in `docs/t05-measurements.md`,
"W13b — certificates, W0.5–W0.7".
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest
import yaml
from test_t05_coupled import CASE_DIR, CASES, Solved, solve
from test_t05_w12_table import _GENERIC, TABLE_IDS, worst_ratios

from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.thermo.syn001 import Syn001Provider
from openflowsheet.verify.certificate import (
    BoundDeclaration,
    SolutionCertificate,
    verify_revision,
)
from openflowsheet.verify.checks import DERIVATIVE_TOLERANCE, FD_RELATIVE_STEP, qualification
from openflowsheet.verify.regularity import target_jacobian
from openflowsheet.verify.table import REACTION_DATUM_NOTE

#: Spec §11.5 / W0.6: one tenth of the smallest scaled allowance of §11.5.
SOLUTION_ERROR_BOUND = 1e-8


def _document(case: str) -> dict[str, Any]:
    document: dict[str, Any] = yaml.safe_load((CASE_DIR / f"{case}.yaml").read_text())
    return document


def certify(solved: Solved, case: str) -> SolutionCertificate:
    """Design note §2.1 step 4, verbatim."""
    assert solved.run.outcome == "CONVERGED", solved.run.message
    return verify_revision(
        solved.binding,
        _document(case),
        solved.run,
        solve_plan=solved.plan.steps[-1].solve_plan,
    )


@pytest.fixture(scope="module")
def certified() -> dict[str, tuple[Solved, SolutionCertificate]]:
    out: dict[str, tuple[Solved, SolutionCertificate]] = {}
    for case in CASES:
        solved = solve(case)
        out[case] = (solved, certify(solved, case))
    return out


@pytest.mark.parametrize("case", CASES)
def test_a21_the_certificate_is_verified_with_every_check_passing(
    case: str, certified: dict[str, tuple[Solved, SolutionCertificate]]
) -> None:
    """`VERIFIED` with no limitation; every check `pass` and none `near_threshold`; the §12.2 ids
    that apply present in §4.3's order, and the generic ones for this declaration."""
    solved, certificate = certified[case]
    assert certificate.verification_status == "VERIFIED", certificate.limitations
    assert not certificate.limitations
    assert not certificate.false_success_detected
    assert [(c.id, c.result) for c in certificate.checks if c.result != "pass"] == []
    assert [c.id for c in certificate.checks if c.near_threshold] == []
    ids = [c.id for c in certificate.checks]
    assert [i for i in ids if not i.startswith(_GENERIC)] == TABLE_IDS[case]
    spec = solved.binding.spec
    assert [i for i in ids if i.startswith("residual.")] == [
        f"residual.{row}" for row in spec.equation_ids
    ]
    (step,) = solved.plan.steps
    assert step.solve_plan is not None
    assert [i for i in ids if i.startswith("alias_certificate.")] == [
        f"alias_certificate.{kind}.{row.row_id}"
        for row in step.solve_plan.eliminated_rows
        for kind in ("identity", "satisfied")
    ]
    assert [i for i in ids if i.startswith("derivative_witness.")] == [
        "derivative_witness.on_pattern",
        "derivative_witness.off_pattern",
    ]
    # Outside the near-threshold band by the ratio as well as by the flag (§12.6, W0.7).
    (two, _), (one, _) = worst_ratios(certificate)
    assert two < 1.0 / 10 and one < 1.0 / 10


@pytest.mark.parametrize("case", CASES)
def test_a21_energy_and_phase_checks_carry_the_qualification(
    case: str, certified: dict[str, tuple[Solved, SolutionCertificate]]
) -> None:
    """[A09] on every energy, admissibility and independent-split check and on nothing else; ADR
    0011 D2's note on the reactor's energy balance and, with a reactor present (C2), the
    envelope's."""
    _, certificate = certified[case]
    provider = Syn001Provider()
    note = qualification(provider)
    reaction = note + REACTION_DATUM_NOTE.format(
        convention=provider.describe().reference_convention
    )
    reacting = case == "SYN-001-UL-C2"
    energy = [c for c in certificate.checks if c.category == "energy_balance"]
    assert energy and all(c.result == "pass" for c in energy)
    for check in certificate.checks:
        shares = check.category in ("energy_balance", "phase_admissibility", "independent_split")
        assert (check.independence_qualification is not None) == shares, check.id
    for check in energy:
        carries = reacting and check.id in ("energy_balance.U-RX", "energy_balance.envelope")
        assert check.independence_qualification == (reaction if carries else note), check.id
    if reacting:
        assert {c.id for c in energy} >= {"energy_balance.U-RX", "energy_balance.envelope"}


@pytest.mark.parametrize("case", CASES)
def test_a21_w0_6_the_solution_error_bound(
    case: str, certified: dict[str, tuple[Solved, SolutionCertificate]]
) -> None:
    """K04 §7.4's recorded `||J^-1||_1 ||F||_inf` (scaled) is `<= 1e-8` (§11.5, W0.6).

    Ruling round Q-R6: A21 is judged on the **exact** `||J^-1||_1`, from the dense inverse of the
    target Jacobian at the final state, because K04's `onenormest` is a lower estimate (6 % low at
    C3). The certificate keeps K04's estimate. Both factors are in `docs/t05-measurements.md`."""
    solved, certificate = certified[case]
    bound = certificate.solution_error_bound_scaled
    assert bound is not None
    assert bound <= SOLUTION_ERROR_BOUND, bound
    assert certificate.as_document()["solution_error_bound_scaled"] == bound

    state = solved.run.state
    assert state is not None
    target = BoundDeclaration(solved.binding.spec, compile_problem(solved.binding.spec), state)
    matrix, scaled_residual, _ = target_jacobian(target, state)
    assert matrix.shape[0] == matrix.shape[1] <= 64
    exact = float(np.linalg.norm(np.linalg.inv(matrix.toarray()), 1))
    residual = float(np.max(np.abs(scaled_residual)))
    assert exact * residual <= SOLUTION_ERROR_BOUND, (exact, residual)
    # `onenormest` is `||J^-1 x||_1` for some unit `x`: never above the exact norm but by rounding.
    assert bound <= exact * residual * (1.0 + 1e-10), (bound, exact * residual)


@pytest.mark.parametrize("case", CASES)
def test_w0_5_the_derivative_witness_at_the_solution(
    case: str, certified: dict[str, tuple[Solved, SolutionCertificate]]
) -> None:
    """Spec §14's last row: central differences at `delta = 1e-5` against the AD Jacobian, judged
    at `1e-7` scaled; both witness checks pass at each case's converged state."""
    assert FD_RELATIVE_STEP == 1e-5 and DERIVATIVE_TOLERANCE == 1e-7
    _, certificate = certified[case]
    witness = {c.id: c for c in certificate.checks if c.category == "derivative_witness"}
    assert set(witness) == {"derivative_witness.on_pattern", "derivative_witness.off_pattern"}
    for check in witness.values():
        assert check.result == "pass" and not check.near_threshold, check
        assert check.tolerance == DERIVATIVE_TOLERANCE
        assert check.value is not None and 0.0 <= check.value <= DERIVATIVE_TOLERANCE / 10
