"""OPT WO-5 (design §4.7): held-regime phase admissibility rows, Q4's held mode and
`REGIME_MARGIN_UNDEFINED`, in the default install.

The lifted split's row is checked against the SYN-001 coefficient table in mpmath
(`benchmarks/opt/analytic.py`'s `k_value`, independent of the provider code); the thermal rows
against the kernel's saturation temperature; the gray box's twin path against the float reference
path bitwise, and its Jacobian against central differences of that path.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import math
from pathlib import Path
from typing import Any

import mpmath as mp
import numpy as np
import pytest
from test_opt_revision_host import _certified
from test_opt_revision_optimize import AVAILABLE, _case, _optimize

from openflowsheet.application.types import schema_errors
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.thermal.kernel import saturation
from openflowsheet.studies.nlp.formulation import (
    Decision,
    FullSpaceNlp,
    NlpFormulation,
    QuadraticExpression,
)
from openflowsheet.studies.nlp.host import RegimeRecord
from openflowsheet.studies.nlp.phase import PHASE_COMPONENT, PhaseRows, phase_rows
from openflowsheet.studies.nlp.revision_host import RevisionNlpHost
from openflowsheet.studies.sensitivity import TAU_REGIME, OutputFunctional, StudyParameter

REPO = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("opt_analytic", REPO / "benchmarks/opt/analytic.py")
assert _SPEC is not None and _SPEC.loader is not None
analytic = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(analytic)


def _context(host: RevisionNlpHost, point: Any) -> EvaluationContext:
    metadata = host._compiled_at(point).metadata
    return EvaluationContext(
        model_version=metadata.model_version,
        constants_sha256=metadata.constants_sha256,
        phase_signature=None,
    )


def test_a_held_liquid_split_gets_its_bubble_row() -> None:
    """The PH flash held LIQUID (1 mol/s each of A, B, C at 1 bar): one row
    `(Σ n − Σ n K(T, P))/N₀`, equal to the coefficient table's value in mpmath and to the split's
    TP margin times the feed total; twin = float path bitwise; Jacobian = central differences."""
    host, point, _ = _certified("PHF")
    rows = host.phase_rows(point)
    assert rows.ids == ("phase.U-PHF.bubble",) and rows.undefined == ()
    (row,) = rows.rows
    assert (row.unit, row.kind, row.nominal) == ("U-PHF", "split_liquid", 3.0)
    assert point.state is not None
    state = point.state
    value = rows.values(state)[row.row_id]
    t, p = mp.mpf(state["S2.T"]), mp.mpf(state["S2.P"])
    flows = {c: mp.mpf(state[f"S1.n.{c}"]) for c in ("A", "B", "C")}
    expected = sum(n * (1 - analytic.k_value(c, t, p)) for c, n in flows.items()) / 3
    assert abs(value - float(expected)) <= 1e-12 * abs(float(expected)), (value, expected)
    (split,) = host.regimes(point).splits
    assert split.margin is not None
    assert math.isclose(value, split.margin * sum(map(float, flows.values())) / 3, rel_tol=1e-14)
    (parameter,) = host.decisions.parameters.values()
    assert point.spec is not None
    x = np.array([state[name] for name in point.spec.variable_ids], dtype=np.float64)
    decisions = {parameter: point.spec.parameters[parameter]}
    twin = rows.twin((parameter,))
    assert np.asarray(twin.residual(x, decisions)).tolist() == [value]
    d_dx, _ = rows.linearize(x, decisions)
    position = {name: k for k, name in enumerate(point.spec.variable_ids)}
    for name, derivative in d_dx[row.row_id].items():
        step = 1e-6 * max(abs(x[position[name]]), 1.0)
        plus, minus = dict(state), dict(state)
        plus[name] += step
        minus[name] -= step
        central = (rows.values(plus)[row.row_id] - rows.values(minus)[row.row_id]) / (2 * step)
        assert abs(derivative - central) <= 1e-6 * max(abs(central), 1e-8), (name, derivative)


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("TH-C1", {"S1": "port_liquid", "S2": "port_liquid", "S3": "port_vapor"}),
        ("TH-V1", {"S1": "port_liquid"}),
    ],
)
def test_declared_thermal_ports_get_saturation_rows(case: str, expected: dict[str, str]) -> None:
    """F4: a declared liquid port's row is `T_sat(P) − T`, a vapour port's `T − T_sat(P)` (1 K),
    with T_sat the thermal kernel's; wet ports and lifted-split-free cases have no other rows."""
    host, point, _ = _certified(case)
    rows = host.phase_rows(point)
    assert {row.unit: row.kind for row in rows.rows} == expected
    assert rows.undefined == ()
    assert point.state is not None
    values = rows.values(point.state)
    route = host.route
    assert route is not None
    provider = route.binding.flowsheet.provider
    for row in rows.rows:
        sat = saturation(provider, point.state[f"{row.unit}.P"], _context(host, point))
        distance = sat.temperature - point.state[f"{row.unit}.T"]  # type: ignore[union-attr]
        sign = 1.0 if row.kind == "port_liquid" else -1.0
        assert values[row.row_id] == sign * distance, (row, values[row.row_id])
        assert values[row.row_id] > 0.0


def test_two_phase_splits_have_no_rows() -> None:
    """M1's seven TWO_PHASE column stages: held by `V, L ≥ 0`, no row, nothing undefined."""
    host, point, _ = _certified("M1")
    regimes = {split.regime for split in host.regimes(point).splits}
    assert regimes == {"TWO_PHASE"}
    rows = host.phase_rows(point)
    assert rows.rows == () and rows.undefined == () and rows.spec is None


def test_a_held_single_phase_split_without_a_margin_is_undefined() -> None:
    """§4.7: a held LIQUID split whose closure judges it by another test (D-12: no margin) has no
    row; it is named in `undefined`."""
    host, point, _ = _certified("PHF")
    (split,) = host.regimes(point).splits
    unmargined = dataclasses.replace(split, margin=None)
    route = host.route
    assert route is not None and point.spec is not None and point.state is not None
    flowsheet = route.binding.flowsheet
    feed = tuple(f"S1.n.{c}" for c in flowsheet.components)
    rows = phase_rows(
        point.spec,
        point.state,
        [(unmargined, feed, "S2.T", "S2.P")],
        flowsheet.provider,
        flowsheet.components,
        _context(host, point),
    )
    assert rows.rows == () and rows.undefined == ("U-PHF",)


def test_the_gray_box_holds_the_phase_rows_as_its_second_block() -> None:
    """§4.4/§4.7: the rows are an output block of their own (`phase_admissibility`), scale 1."""
    host, point, _ = _certified("PHF")
    (parameter,) = host.decisions.parameters.values()
    formulation = NlpFormulation(
        problem_id="phase-block",
        objective=QuadraticExpression(linear={"S3.T": -1.0}, text="-S3.T"),
        decisions=(Decision(parameter, 0.0, 5000.0, 1000.0),),
        constraints=(),
        starts=((point.parameters[parameter],),),
    )
    nlp = FullSpaceNlp(host, formulation, point, (point.parameters[parameter],))
    assert [block.name for block in nlp.output_blocks] == ["phase"]
    (block,) = nlp.output_blocks
    assert block.constraint == PHASE_COMPONENT
    assert nlp.output_ids == ("phase.U-PHF.bubble",)
    assert nlp.output_scales == {"phase.U-PHF.bubble": 1.0}
    assert nlp.admissibility_nominals == {"phase.U-PHF.bubble": 3.0}
    z = nlp.initial_point()
    assert point.state is not None
    assert nlp.output_values(z).tolist() == [
        host.phase_rows(point).values(point.state)[nlp.output_ids[0]]
    ]
    assert nlp.output_jacobian(z).shape == (1, len(nlp.primal_ids))


def test_q4_held_mode_records_instead_of_refusing() -> None:
    """§4.7: a split inside τ_regime is refused `PHASE_BOUNDARY` by Q4; passed as `held` (its
    phase row active at a candidate) Q4 records it and passes."""
    host, point, _ = _certified("PHF")
    record = host.regimes(point)
    (split,) = record.splits
    near = RegimeRecord(record.signature, (dataclasses.replace(split, margin=0.1 * TAU_REGIME),))
    (parameter,) = host.decisions.parameters.values()
    duty = point.parameters[parameter]
    arguments = (
        point,
        [StudyParameter(parameter, duty, 0.0, 2.0 * duty)],
        [OutputFunctional.of_variable("S3.T", 1.0)],
    )
    original = RevisionNlpHost.regimes
    RevisionNlpHost.regimes = lambda self, point: near  # type: ignore[assignment,method-assign]
    try:
        refused = host.sensitivity(*arguments, mode="adjoint")
        held = host.sensitivity(*arguments, mode="adjoint", held=("U-PHF",))
    finally:
        RevisionNlpHost.regimes = original  # type: ignore[method-assign]
    assert refused.outcome("Q4").outcome == "fail"
    assert "PHASE_BOUNDARY" in refused.refusal_codes
    q4 = held.outcome("Q4")
    assert q4.outcome == "pass" and q4.detail["held"] == ["U-PHF"]
    assert held.status == "QUALIFIED", held.refusals
    assert held.adjoint is not None


def test_a_start_with_an_undefined_regime_margin_is_not_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§4.7: a held regime no row can hold refuses the start at the start phase —
    `START_NOT_CERTIFIED(<k>, REGIME_MARGIN_UNDEFINED): REGIME_MARGIN_UNDEFINED(<unit>)`; with no
    start left the report is `UNSUPPORTED` and no Ipopt is reached."""
    document, request = _case("OPT-A1")
    monkeypatch.setattr(
        RevisionNlpHost,
        "phase_rows",
        lambda self, point: PhaseRows((), ("U-PHF",), None),
    )
    outcome = _optimize(document, request, tmp_path / "record", AVAILABLE)
    report = outcome.report.as_document()
    assert report["status"] == "UNSUPPORTED"
    (reason,) = report["reasons"]
    assert reason["code"] == "SIMULATION_NOT_READY"
    assert reason["detail"] == (
        "START_NOT_CERTIFIED(0, REGIME_MARGIN_UNDEFINED): REGIME_MARGIN_UNDEFINED(U-PHF)"
    )
    assert schema_errors("optimization-report.schema.json", report) == []
