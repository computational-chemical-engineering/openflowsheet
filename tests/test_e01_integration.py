"""E01 WO-I1 (design §5.4, §9.5): the end-to-end runs on the registered configurations.

The configurations (§5.4; the naming is logged in `docs/E01B_DECISIONS.md`, WO-I1):
- **P1** = S11's TH-C1 (pump, boiler, turbine, condenser), with TH-R1 (heater, flash, pump) for the
  flash drum: no registered S11 case holds all four of §5.4's P1 units. P1's reports are
  `tests/test_e01_a_report.py`'s fixtures; A30 and A31 run on TH-C1 in
  `tests/test_e01_b_studies.py`.
  No P1 exchanger exceeds 2000 psig (QA4): the boiler is in pressure piece 1 and costed.
- **P2** = SYN-001 (M03's host), with the document `P2_DOCUMENT` below: the registered cost and
  derived contributors on SSLW (`sslw-idaes-v1`), no test contributor. Here: A33, A34 (`nlp`
  environment) and A36.
- **P3** = S11's M1 (column on syn001): `tests/test_e01_a_report.py`'s fixture, A12 in
  `tests/test_e01_b_cost_hand.py`.
- **P4** = TH-C1 with an LCA section on `test-background-v1` and `gwp100-ipcc-ar6-v1`: A25 in
  `tests/test_e01_b_lca.py` (hand superposition) and `tests/test_e01_b_brightway.py` (`lca` env).

§9.7's risk, measured on P2: the heater and the flash duty exchanger sit in `floor`; the flash
drum is sized (`units:1`), so `∂tac/∂x` has capital rows as well as the utility rows.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from functools import cache
from typing import Any

import numpy as np
import pytest
from m03_support import flowsheet
from test_e01_b_nlp import base, bound, full_space, m03_readiness, verify

from openflowsheet.assessment.cost.contributor import CostContributor
from openflowsheet.assessment.cost.derived import DerivedContributor
from openflowsheet.assessment.program import AssessmentProgram, Linearization
from openflowsheet.assessment.regimes import Regime
from openflowsheet.assessment.spec import load_assessment
from openflowsheet.assessment.views import view_of
from openflowsheet.studies.nlp.closure import StartEvidence, classify_starts
from openflowsheet.studies.nlp.formulation import FullSpaceNlp
from openflowsheet.studies.nlp.verification import CHECKS, TAU_FEAS

#: P2's assessment: SSLW on SYN-001's heater and flash, the bare-module chain, 2023 USD. The
#: F_BM values are test inputs (as P1's and P3's fixture documents).
P2_DOCUMENT: dict[str, Any] = {
    "schema_version": "assessment-v1",
    "assessment_id": "e01-i1-p2",
    "basis": {"currency": "USD", "year": 2023},
    "operation": {"hours_per_year": 8000.0, "lifetime_years": 20, "discount_rate": 0.08},
    "correlation_set": "sslw-idaes-v1",
    "defaults": {"U_by_service": {"heating": 800.0, "cooling": 500.0}},
    "items": {
        "U-HEAT": {"F_BM": 3.17},
        "U-FLASH.duty": {"F_BM": 3.17},
        "U-FLASH.drum": {"F_BM": 4.16},
    },
    "utilities": [
        {
            "utility_id": "HPS",
            "kind": "heating",
            "T_supply": 520.0,
            "dT_min": 10.0,
            "price": {"value": 20.0, "per": "GJ"},
        },
        {
            "utility_id": "CW",
            "kind": "cooling",
            "T_supply": 293.15,
            "T_return": 303.15,
            "dT_min": 5.0,
            "price": {"value": 0.5, "per": "GJ"},
        },
    ],
    "capital": {"chain": "bare-module-total"},
}
#: A36's held dormancy entry: the drum's vapour product, which flows at every M03 start.
DORMANT = "U-FLASH.drum.S4.dormant"


def p2_program(regime: Regime | None = None) -> AssessmentProgram:
    sheet, state = base()
    built = AssessmentProgram.build(
        view_of(sheet),
        sheet.spec(),
        load_assessment(P2_DOCUMENT),
        state,
        regime,
        contributors=[CostContributor(), DerivedContributor()],
    )
    assert isinstance(built, AssessmentProgram), built
    return built


@cache
def p2() -> AssessmentProgram:
    return p2_program()


def test_p2_is_a_complete_sslw_program_with_floored_exchangers_and_a_sized_drum() -> None:
    p = p2()
    assert p.refusals == ()
    _, state = base()
    values = p.evaluate(state)
    assert isinstance(values, Mapping)
    assert values["tac"] > 0.0
    for item in ("U-HEAT", "U-FLASH.duty", "U-FLASH.drum"):
        assert f"capex.purchased.{item}" in p.output_ids
    entries = dict(p.regime.entries)
    assert entries["U-HEAT.size"] == entries["U-FLASH.duty.size"] == "floor"
    assert entries["U-FLASH.drum.size"] == "units:1"
    assert entries[DORMANT] == "active"


def test_a36_a_drum_stream_held_dormant_that_flows_at_x_sim_is_not_verified() -> None:
    held = p2_program(Regime({DORMANT: "dormant"}))
    assert held.regime.choice(DORMANT) == "dormant"
    result = verify(bound(held, "tac"))
    v7 = next(check for check in result.checks if check.check == "V7")
    assert v7.outcome == "fail"
    # Held dormant, the drum is sized without its vapour, so its controlling member moves too.
    assert sorted(v7.detail["codes"]) == [
        f"ASSESSMENT_REGIME_CHANGED({DORMANT})",
        "ASSESSMENT_REGIME_CHANGED(U-FLASH.drum.controlling)",
    ]
    assert v7.detail["regime_changed"] == [DORMANT, "U-FLASH.drum.controlling"]
    # V7 hands every dormancy entry to the rule; the vapour product's is the one that moved.
    assert sorted(v7.detail["dormancy_released"]) == [DORMANT, "U-FLASH.drum.S5.dormant"]
    assert not result.passed
    evidence = StartEvidence(0, {check.check: check.outcome for check in result.checks})
    assert classify_starts([evidence]).status == "NOT_VERIFIED"
    # Control: the same start with the regime the rule selects passes V7.
    assert verify(bound(p2(), "tac")).outcome("V7") == "pass"


def _positions(matrix: Any) -> set[tuple[int, int]]:
    csc = matrix.tocsc()
    return {
        (int(csc.indices[k]), j)
        for j in range(csc.shape[1])
        for k in range(csc.indptr[j], csc.indptr[j + 1])
    }


def _twin_positions(p: AssessmentProgram, nlp: FullSpaceNlp) -> set[tuple[int, int]]:
    """The twin's structural pattern in the gray box's column order (states, then decisions)."""
    x, decisions = nlp.split(nlp.initial_point())
    state = dict(zip(nlp.variable_ids, (float(v) for v in x), strict=True))
    lin = p.linearize(state, decisions, nlp.output_ids, symbolic=nlp.decision_ids)
    assert isinstance(lin, Linearization), lin
    found = set()
    for matrix, offset in ((lin.d_dx, 0), (lin.d_dp, nlp.n_variables)):
        for j in range(len(matrix.col_ids)):
            for k in range(matrix.indptr[j], matrix.indptr[j + 1]):
                found.add((int(matrix.indices[k]), offset + j))
    return found


def _start_tacs(p: AssessmentProgram) -> list[tuple[float, dict[str, float]]]:
    """`tac` and the violated sides at each M03 start. A start is feasible (the ruling on ESC-I1,
    `docs/E01B_DECISIONS.md`) when the formulation's constraints hold within their stated
    tolerance there: each decision inside its box exactly and each inequality side's slack at
    least `−τ_feas`, V3's rule (`verification._feasibility`). The map holds each violated side's
    slack; it is empty at a feasible start."""
    f = bound(p, "tac")
    found = []
    for record in m03_readiness().starts:
        assert record.state is not None
        decisions = f.decision_values(record.start)
        values = p.evaluate(record.state, decisions)
        assert isinstance(values, Mapping)
        violated: dict[str, float] = {}
        for decision in f.decisions:
            value = decisions[decision.parameter_id]
            for side, limit in (("lower", decision.lower), ("upper", decision.upper)):
                if limit is None or not math.isfinite(limit):
                    continue
                slack = value - limit if side == "lower" else limit - value
                if slack < 0.0:
                    violated[f"{decision.parameter_id}:{side}"] = slack
        for constraint in f.constraints:
            value = constraint.expression.value(record.state)
            for side, limit in (("lower", constraint.lower), ("upper", constraint.upper)):
                if limit is None:
                    continue
                slack = value - limit if side == "lower" else limit - value
                if slack < -TAU_FEAS:
                    violated[f"{constraint.constraint_id}:{side}"] = slack
        found.append((values["tac"], violated))
    return found


def test_a33_m03_starts_0_and_1_are_infeasible_for_recovery(
    record_property: Any,
) -> None:
    """The fact behind ESC-I1: two of M03's three starts violate `recovery_A ≥ 0`, and their `tac`
    is below the constrained optimum's (84481.6); the feasible start's is above it. A33 compares
    the candidate with the feasible start only (the ruling); the infeasible ones are recorded."""
    found = _start_tacs(p2())
    assert [bool(violated) for _, violated in found] == [True, True, False]
    for index, (tac, violated) in enumerate(found):
        record_property(f"a33_start_{index}", {"tac": tac, "violated": violated})


@pytest.mark.nlp
def test_a33_a34_p2_tac_objective_from_every_start(
    monkeypatch: pytest.MonkeyPatch, record_property: Any
) -> None:
    from openflowsheet.studies.nlp import greybox
    from openflowsheet.studies.nlp.closure import optimize

    p = p2()
    f = bound(p, "tac")
    scale = f.assessment.output_scales["tac"]
    _, state = base()
    tac_x0 = p.evaluate(state)
    assert isinstance(tac_x0, Mapping) and scale == abs(tac_x0["tac"])
    patterns: list[set[tuple[int, int]]] = []
    jacobian = FullSpaceNlp.output_jacobian

    def recorded(self: FullSpaceNlp, z: Any) -> Any:
        matrix = jacobian(self, z)
        patterns.append(_positions(matrix))
        return matrix

    finals: list[tuple[dict[str, float], dict[str, float]]] = []
    verify_at = greybox.verify_candidate

    def captured(*args: Any, **kwargs: Any) -> Any:
        _, formulation, decisions = args
        finals.append((dict(kwargs["optimizer_state"]), formulation.decision_values(decisions)))
        return verify_at(*args, **kwargs)

    monkeypatch.setattr(FullSpaceNlp, "output_jacobian", recorded)
    monkeypatch.setattr(greybox, "verify_candidate", captured)
    report = optimize(f, flowsheet({})).as_document()
    monkeypatch.undo()

    # A33: every start (M03's three; at least the two A33 names) passes V1-V7.
    assert report["status"] == "KKT_POINT_VERIFIED"
    assert len(report["starts"]) >= 2
    for start in report["starts"]:
        assert start["ipopt_status"] == 0
        assert [check["check"] for check in start["checks"]] == list(CHECKS)
        assert [check["outcome"] for check in start["checks"]] == ["pass"] * len(CHECKS)
    candidate = report["candidate"]
    assert [check["outcome"] for check in candidate["checks"]] == ["pass"] * len(CHECKS)
    v6 = next(check for check in candidate["checks"] if check["check"] == "V6")
    at_x_sim = v6["assessment_values"]["tac"]
    # The optimizer's output: the twin's `tac` (what the gray box hands Ipopt) at the final primal
    # of the start whose decisions are the candidate's.
    decisions = candidate["decisions"]
    (x_opt, d_opt), *_ = [final for final in finals if final[1] == decisions]
    lin = p.linearize(x_opt, d_opt, ("tac",), symbolic=tuple(d_opt))
    assert isinstance(lin, Linearization), lin
    assert abs(at_x_sim - lin.values["tac"]) <= 1e-6 * abs(at_x_sim)
    # A33 as restated by the ruling on ESC-I1 (design §6.1's erratum): tac(candidate) ≤ tac(start)
    # over the feasible starts (start 2); the infeasible starts 0 and 1 are recorded with their
    # violations, not compared.
    starts = _start_tacs(p)
    feasible = [tac for tac, violated in starts if not violated]
    assert feasible
    assert all(at_x_sim <= tac for tac in feasible)
    record_property("a33_tac_candidate", at_x_sim)
    for index, (tac, violated) in enumerate(starts):
        record_property(
            f"a33_start_{index}", {"tac": tac, "violated": violated, "compared": not violated}
        )

    # A34: one pattern through every evaluation of every start, the twin's structural one.
    assert patterns
    assert all(pattern == patterns[0] for pattern in patterns)
    assert patterns[0] == _twin_positions(p, full_space(f))
    assert np.isfinite(at_x_sim)
