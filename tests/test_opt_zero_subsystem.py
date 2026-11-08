"""OPT §9 A-2 (WO-5b): the structurally zero subsystem of a revision point; gate G23 (a), (b), (d)
and the static half of (c).

C-MW's feed carries exactly zero C2H5OH, so every ethanol flow of the column is `0.0` at a
certified start (Z) and the ethanol rows (R) enter no other free column and no decision there:
the host holds Z at `+0.0` and drops R. (c)'s report bytes are compared in the audited NLP
environment (`scripts/opt_report_dump.py`); here: Z = ∅ at the analytic cases' starts.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import pytest

from openflowsheet.application.policies import DEFAULT_POLICY_ID, resolve_policy
from openflowsheet.application.revision_routes import REVISION_ROUTES
from openflowsheet.compiled import EvaluationContext
from openflowsheet.orchestrator import region as region_module
from openflowsheet.studies.nlp import revision_host
from openflowsheet.studies.nlp.host import CertifiedPoint, HeldSystem, ZeroSubsystem
from openflowsheet.studies.nlp.revision_host import (
    DecisionBox,
    DecisionMap,
    RevisionNlpHost,
    decision_map,
)
from openflowsheet.studies.nlp.verification import ZERO_SUBSYSTEM_CHANGED, _regimes
from openflowsheet.verify.certificate import CheckPolicy

REPO = Path(__file__).resolve().parents[1]
C_MW = REPO / "benchmarks" / "s11" / "flowsheets" / "C-MW.json"
OPT = REPO / "benchmarks" / "opt"
POLICY = resolve_policy(DEFAULT_POLICY_ID, "revision_eo")
assert POLICY is not None
#: C-MW's feed temperature as committed (`benchmarks/opt/performance.py`).
C_MW_FEED_T = 348.6155803604359
#: The feed's C2H5OH flow specification (G23 (d)).
ETHANOL_FEED = "SPEC-S-IN1-n-C2H5OH"


def _host(document: Mapping[str, Any], boxes: list[DecisionBox]) -> RevisionNlpHost:
    found = decision_map(document, boxes, routes=REVISION_ROUTES)
    assert isinstance(found, DecisionMap), found
    assert POLICY is not None
    return RevisionNlpHost(
        document, found, solve_policy=POLICY, check_policy=CheckPolicy(), routes=REVISION_ROUTES
    )


@cache
def _c_mw() -> tuple[RevisionNlpHost, CertifiedPoint, tuple[float, ...]]:
    """C-MW's host (decision: the feed temperature), its point at the committed value and the
    converged attempt's final Newton residual."""
    document = json.loads(C_MW.read_bytes())
    host = _host(document, [DecisionBox("SPEC-S-IN1-T", 335.0, C_MW_FEED_T, "K")])
    residuals: list[tuple[float, ...]] = []
    original = getattr(region_module, "solve_newton")  # noqa: B009 - not re-exported

    def spy(*args: Any, **kwargs: Any) -> Any:
        result = original(*args, **kwargs)
        residuals.append(tuple(result.residual))
        return result

    setattr(region_module, "solve_newton", spy)  # noqa: B010
    try:
        point = host.certify({"U-FEED1.T_spec": C_MW_FEED_T})
    finally:
        setattr(region_module, "solve_newton", original)  # noqa: B010
    assert point.verified, (point.outcome, point.message)
    return host, point, residuals[-1]


def _attempt(point: CertifiedPoint) -> HeldSystem:
    """The converged attempt's system, unreduced (§4.2.1 as before A-2)."""
    handle = revision_host._handle(point)
    region = handle.region
    assert region is not None and region.final_system is not None and point.spec is not None
    assert handle.run is not None and handle.run.solve_plan is not None
    eliminated = tuple(row.row_id for row in handle.run.solve_plan.eliminated_rows)
    return HeldSystem.of_attempt(point.spec, region.final_system, eliminated)


def _context(host: RevisionNlpHost, point: CertifiedPoint) -> EvaluationContext:
    metadata = host._compiled_at(point).metadata
    return EvaluationContext(
        model_version=metadata.model_version,
        constants_sha256=metadata.constants_sha256,
        phase_signature=None,
    )


def test_the_decision_parameter_is_the_feed_temperature() -> None:
    host, _, _ = _c_mw()
    assert dict(host.decisions.parameters) == {"SPEC-S-IN1-T": "U-FEED1.T_spec"}


# -- G23 (a): exactness of the reduction at C-MW's certified start ---------------------------------


def test_g23a_c_mw_holds_its_ethanol_subsystem() -> None:
    host, point, final_residual = _c_mw()
    system, attempt = host.held_system(point), _attempt(point)
    assert point.state is not None and point.spec is not None
    zero = system.zero
    assert zero is not None and zero.status == "held"
    assert len(zero.columns) == len(zero.rows) == 63  # recorded in OPT_DECISIONS (F7)
    assert all(name.endswith(".C2H5OH") for name in zero.columns)
    # Every free flow exactly 0.0 at the point, and nothing else.
    kinds = point.spec.variable_kinds
    assert set(zero.columns) == {
        name for name in attempt.free if kinds[name] == "molar_flow" and point.state[name] == 0.0
    }
    # rows − R, free − Z, held + {z: +0.0}, labels and the rest unchanged.
    assert system.rows == tuple(row for row in attempt.rows if row not in set(zero.rows))
    assert system.free == tuple(name for name in attempt.free if name not in set(zero.columns))
    assert dict(system.held) == {**attempt.held, **dict.fromkeys(zero.columns, 0.0)}
    assert all(np.float64(system.held[name]).tobytes() == b"\0" * 8 for name in zero.columns)
    assert system.labels == attempt.labels and system.eliminated == attempt.eliminated
    assert system.signature == attempt.signature
    # J[R, ¬Z ∪ decisions] == 0.0 entry by entry; J[R, Z] nonsingular.
    spec = point.spec
    x = np.array([point.state[name] for name in spec.variable_ids], dtype=np.float64)
    jacobian = host._compiled_at(point).jacobian(x, _context(host, point))
    assert jacobian.status == "ok"
    dense = np.zeros((len(jacobian.row_ids), len(jacobian.col_ids)))
    for column in range(len(jacobian.col_ids)):
        for offset in range(jacobian.indptr[column], jacobian.indptr[column + 1]):
            dense[jacobian.indices[offset], column] = jacobian.data[offset]
    row_at = {name: index for index, name in enumerate(jacobian.row_ids)}
    col_at = {name: index for index, name in enumerate(jacobian.col_ids)}
    r = [row_at[name] for name in zero.rows]
    others = [col_at[name] for name in attempt.free if name not in set(zero.columns)]
    assert np.all(dense[np.ix_(r, others)] == 0.0)
    block = dense[np.ix_(r, [col_at[name] for name in zero.columns])]
    assert np.linalg.matrix_rank(block) == len(zero.rows)
    twin = host.twin(("U-FEED1.T_spec",))
    parameters = twin.jacobian_p(x, {"U-FEED1.T_spec": point.parameters["U-FEED1.T_spec"]})
    for column in range(len(parameters.col_ids)):
        for offset in range(parameters.indptr[column], parameters.indptr[column + 1]):
            if parameters.row_ids[parameters.indices[offset]] in set(zero.rows):
                assert parameters.data[offset] == 0.0
    # The reduced system's residual (held columns written in) is the converged attempt's on the
    # remaining rows, bit for bit.
    held_x = x.copy()
    for name, value in system.held.items():
        held_x[col_at[name]] = value
    evaluation = host._compiled_at(point).residual(held_x, _context(host, point))
    assert evaluation.status == "ok" and evaluation.values is not None
    by_id = dict(zip(evaluation.equation_ids, evaluation.values, strict=True))
    final = dict(zip(attempt.rows, final_residual, strict=True))
    assert np.array([by_id[row] for row in system.rows]).tobytes() == (
        np.array([final[row] for row in system.rows]).tobytes()
    )


def test_g23a_the_held_zeros_leave_the_bounds() -> None:
    host, point, _ = _c_mw()
    bounds = host.bounds(point)
    zero = host.held_system(point).zero
    assert zero is not None
    assert not set(bounds) & set(zero.columns)
    kinds = host.held_system(point).spec.variable_kinds
    flows = {name: bound for name, bound in bounds.items() if kinds[name] == "molar_flow"}
    assert {(b.lower, b.upper, b.reason) for b in flows.values()} == {
        (0.0, None, "nonnegative_flow")
    }


# -- G23 (b): derivatives through the reduced and the unreduced system ----------------------------


def _tangent(
    host: RevisionNlpHost, point: CertifiedPoint, system: HeldSystem, outputs: list[str]
) -> npt.NDArray[np.float64]:
    """dy/dd = −C J⁻¹ F_d over `system` (its rows and free columns; C-MW has no label rows) at
    the point, from the compiled Jacobian and the twin's ∂F/∂d."""
    assert point.state is not None and point.spec is not None and not system.labels
    spec = point.spec
    x = np.array([point.state[name] for name in spec.variable_ids], dtype=np.float64)
    jacobian = host._compiled_at(point).jacobian(x, _context(host, point))
    twin = host.twin(("U-FEED1.T_spec",))
    parameters = twin.jacobian_p(x, {"U-FEED1.T_spec": point.parameters["U-FEED1.T_spec"]})
    row_at = {name: index for index, name in enumerate(system.rows)}
    col_at = {name: index for index, name in enumerate(system.free)}
    j = np.zeros((len(system.rows), len(system.free)))
    for column, name in enumerate(jacobian.col_ids):
        if name not in col_at:
            continue
        for offset in range(jacobian.indptr[column], jacobian.indptr[column + 1]):
            row = jacobian.row_ids[jacobian.indices[offset]]
            if row in row_at:
                j[row_at[row], col_at[name]] = jacobian.data[offset]
    f_d = np.zeros(len(system.rows))
    for offset in range(parameters.indptr[0], parameters.indptr[1]):
        row = parameters.row_ids[parameters.indices[offset]]
        if row in row_at:
            f_d[row_at[row]] = parameters.data[offset]
    dx = np.linalg.solve(j, -f_d)
    return np.array([dx[col_at[name]] for name in outputs])


def test_g23b_sensitivities_agree_through_both_systems() -> None:
    host, point, _ = _c_mw()
    outputs = ["COL.stage.20.Q", "S-DISTILLATE.n.CH3OH", "S-BOTTOMS.n.H2O"]
    reduced = _tangent(host, point, host.held_system(point), outputs)
    full_system = _attempt(point)
    unreduced = _tangent(host, point, full_system, outputs)
    assert np.all(unreduced != 0.0)
    assert np.all(np.abs(reduced - unreduced) <= 1e-10 * np.abs(unreduced)), (reduced, unreduced)
    # Through the unreduced system dx_Z/dd is zero up to the dense LU's rounding (it does not
    # exploit the block-triangular structure that makes it exactly zero).
    zero = host.held_system(point).zero
    assert zero is not None
    every = _tangent(host, point, full_system, list(full_system.free))
    at_zero = _tangent(host, point, full_system, list(zero.columns))
    assert np.max(np.abs(at_zero)) <= 1e-12 * np.max(np.abs(every))


# -- G23 (c), static: the analytic cases have no zero subsystem ------------------------------------


@pytest.mark.parametrize(
    ("flowsheet", "boxes", "points"),
    [
        ("OPT-A1", [DecisionBox("SPEC-Q", 1000.0, 20000.0, "W")], [{}, {"SPEC-Q": 14000.0}]),
        (
            "OPT-A2",
            [DecisionBox("SPEC-r", 0.05, 0.95, "1"), DecisionBox("SPEC-Q", 500.0, 6000.0, "W")],
            [{}, {"SPEC-r": 0.7, "SPEC-Q": 5500.0}],
        ),
        (
            "OPT-A2b",
            [DecisionBox("SPEC-r", 0.05, 0.95, "1"), DecisionBox("SPEC-T", 305.0, 336.0, "K")],
            [{}, {"SPEC-r": 0.7, "SPEC-T": 325.0}],
        ),
    ],
)
def test_g23c_the_analytic_cases_have_no_zero_subsystem(
    flowsheet: str, boxes: list[DecisionBox], points: list[dict[str, float]]
) -> None:
    document = json.loads((OPT / "flowsheets" / f"{flowsheet}.json").read_bytes())
    host = _host(document, boxes)
    parameters = host.decisions.parameters
    base = host.base_spec().parameters
    for moved in points:
        values = {
            parameter: moved.get(spec, base[parameter]) for spec, parameter in parameters.items()
        }
        point = host.certify(values)
        assert point.verified, (flowsheet, moved, point.outcome)
        system = host.held_system(point)
        assert system.zero is None
        assert system == _attempt(point)


# -- G23 (d): a zero flow a decision moves is unresolved -------------------------------------------


def test_g23d_a_decision_on_the_zero_feed_leaves_the_subsystem_unresolved() -> None:
    document = json.loads(C_MW.read_bytes())
    host = _host(
        document,
        [
            DecisionBox("SPEC-S-IN1-T", 335.0, C_MW_FEED_T, "K"),
            DecisionBox(ETHANOL_FEED, 0.0, 0.1, "mol/s"),
        ],
    )
    base = host.base_spec().parameters
    point = host.certify({name: base[name] for name in host.decisions.parameters.values()})
    assert point.verified, point.outcome
    system = host.held_system(point)
    zero = system.zero
    assert zero is not None and zero.status == "unresolved"
    assert len(zero.columns) == 63 and len(zero.rows) == 62
    assert system == dataclasses.replace(_attempt(point), zero=zero)
    bounds = host.bounds(point)
    for name in zero.columns:
        assert bounds[name].lower == 0.0 and bounds[name].upper is None
        assert bounds[name].reason == "zero_at_start_unresolved"


# -- V4's clause ----------------------------------------------------------------------------------


def test_v4_fails_when_the_zero_subsystem_moves() -> None:
    host, point, _ = _c_mw()
    system = host.held_system(point)
    record = host.regimes(point)
    declared = record.declared()
    zero = system.zero
    assert zero is not None
    same = _regimes(record, declared, system, point.signature, zero=(zero, zero))
    assert same.detail["zero_subsystem"]["codes"] == []
    assert same.detail["zero_subsystem"]["columns"] == 63
    smaller = ZeroSubsystem("unresolved", zero.columns, zero.rows[1:])
    moved = _regimes(record, declared, system, point.signature, zero=(zero, smaller))
    assert moved.outcome == "fail"
    assert moved.detail["zero_subsystem"]["codes"] == [ZERO_SUBSYSTEM_CHANGED]
    assert moved.detail["zero_subsystem"]["rows_changed"] == [zero.rows[0]]
    gone = _regimes(record, declared, system, point.signature, zero=(zero, None))
    assert gone.outcome == "fail" and gone.detail["zero_subsystem"]["resolve"] is None
    # Empty at both: no member, as before A-2.
    empty = _regimes(record, declared, system, point.signature, zero=(None, None))
    assert "zero_subsystem" not in empty.detail
