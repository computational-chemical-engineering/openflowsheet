"""S11 WO-B3d/B3e: the column solved in a flowsheet (design note §4.7.5, §6.1, §10.8, §10.11).

S11.A28 (a column under a phase-contract-v1 policy is refused before the traversal); A29 on the
SYN-001 cases (`benchmarks/s11/flowsheets/*.json`: S02 M1–M4, S06 J1–J8 and the recycle case)
and the Wilson cases C-MW and C-EW; Q11 (a Wilson column with a `none` end, admitted because
`solve_column` accepts it); A24′ (no edge-3 continuation on a column region, as on every revision
region); Q29 (the PTC policy: a typed refusal). The column is
registered for the test only (`s11_column_support.column_registered`), as I1 has not registered
it yet.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from s11_column_support import (
    COLUMN_CASES,
    RECYCLE_CASE,
    WILSON_CASES,
    WILSON_STRIPPER,
    column_case,
    column_case_spec,
    column_registered,
    column_revision,
    committed_case,
)
from test_s02_column_wo1 import SPECS
from test_s02_column_wo2 import FLOW_ABS, FLOW_REL, Q_ABS, T_ABS, ref_state
from test_s06_column_wo2 import expected_root
from test_s10c_blocks import REAL
from test_s10c_columns import deviations, root, worst
from test_t05_w11_cases import case_document

from openflowsheet.application.policies import T04_W12, T06_REVISION_V2, T08_PTC_V1
from openflowsheet.application.revision_binding import (
    SELECTABLE_BASES,
    RevisionBinding,
    basis_provider,
    bind_revision_flowsheet,
)
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.models import flow_id, pressure_id, temperature_id
from openflowsheet.models.revision_flowsheet import WILSON_BASIS, WILSON_RECORDS
from openflowsheet.models.syn001.cascade import stage_duty_id, stage_temperature_id
from openflowsheet.models.syn001.cascade_solve import S01_DEFAULT_V1
from openflowsheet.models.syn001.column import ColumnSpec
from openflowsheet.models.syn001.column_solve import ColumnSolution, product_columns, solve_column
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import PlanResult, execute_plan
from openflowsheet.orchestrator.homotopy import continuation_parameter
from openflowsheet.orchestrator.revision import plan_revision
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.thermo.wilson_ig_v2 import WilsonIdealGasProviderV2
from openflowsheet.verify.certificate import fresh_provider

M1 = SPECS["M1"]


@pytest.fixture
def registered(monkeypatch: pytest.MonkeyPatch) -> Iterator[pytest.MonkeyPatch]:
    with column_registered(monkeypatch):
        yield monkeypatch


@pytest.fixture
def registered_wilson(monkeypatch: pytest.MonkeyPatch) -> Iterator[pytest.MonkeyPatch]:
    """The column admitted on both of I1's bases (`MODEL_BASES = {syn001, wilson-ig-v2}`)."""
    with column_registered(monkeypatch, frozenset({"syn001", "wilson-ig-v2"})):
        yield monkeypatch


def _run(document: dict[str, object], policy: SolvePolicy) -> PlanResult:
    binding = bind_revision_flowsheet(document)
    assert isinstance(binding, RevisionBinding), binding
    plan, _ = plan_revision(binding, policy)
    assert isinstance(plan, ExecutionPlan), plan
    return execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=policy)


# -- S11.A28 ---------------------------------------------------------------------------------------


def test_a_column_under_a_v1_policy_is_capability_unavailable(
    registered: pytest.MonkeyPatch,
) -> None:
    """S11.A28: `CAPABILITY_UNAVAILABLE phase_contract_unsupported(syn001.column)`, before the
    traversal: no attempt is opened."""
    assert T04_W12.phase_contract == "T03-phase-contract-v1"
    run = _run(column_revision(M1), T04_W12)
    assert run.outcome == "CAPABILITY_UNAVAILABLE"
    (step,) = run.steps
    assert step.outcome == "CAPABILITY_UNAVAILABLE"
    assert step.message == "phase_contract_unsupported(syn001.column)"
    assert step.detail is None and run.counters.property_calls == 0


def test_the_same_column_under_the_revision_policy_converges(
    registered: pytest.MonkeyPatch,
) -> None:
    """A28's control: the application's revision policy carries phase contract v2."""
    assert T06_REVISION_V2.phase_contract == "T05b-phase-contract-v2"
    run = _run(column_revision(M1), T06_REVISION_V2)
    assert run.outcome == "CONVERGED", run.message


# -- the committed cases --------------------------------------------------------------------------


@pytest.mark.parametrize("name", [*COLUMN_CASES, RECYCLE_CASE, *WILSON_CASES, WILSON_STRIPPER])
def test_the_committed_case_is_the_generated_one(name: str) -> None:
    """`benchmarks/s11/flowsheets/<name>.json` is `column_case(name)`, so the two cannot drift
    (regenerate with `python tests/s11_column_support.py`)."""
    assert committed_case(name) == column_case(name)


# -- S11.A29 ---------------------------------------------------------------------------------------

#: A29's Newton budget from the traversal start (the standalone root) with no recycle.
NEWTON_BUDGET = 3


def _expected(name: str) -> dict[str, float]:
    """The registered standalone root: S02's `ref.cases.<M>.target`, S06's `<J>.target`."""
    return ref_state(name, "target") if name.startswith("M") else expected_root(name)


def _worst(
    spec: ColumnSpec, expected: dict[str, float], state: dict[str, float]
) -> dict[str, float]:
    """A29's deviations, each in units of the case's registered state tolerance (S02 §10, S01's
    R-514: flows rel 1e-6 + 10·τ_flow, T 1e-4 K, Q 1e-2 W; P pinned, 0.01 Pa): every product
    flow, the products' T and P, Q₁ and Q_N."""
    unit, count = spec.unit_id, spec.stage_count
    columns = product_columns(spec)
    worst: dict[str, float] = {}
    for port, stream, stage in (("distillate", "S-DISTILLATE", 1), ("bottoms", "S-BOTTOMS", count)):
        for c, column in zip(spec.components, columns[port], strict=True):
            target = expected[column]
            worst[f"{port}.n.{c}"] = abs(state[flow_id(stream, c)] - target) / (
                FLOW_REL * abs(target) + FLOW_ABS
            )
        temperature = expected[stage_temperature_id(unit, stage)]
        worst[f"{port}.T"] = abs(state[temperature_id(stream)] - temperature) / T_ABS
        worst[f"{port}.P"] = abs(state[pressure_id(stream)] - spec.pressures[stage - 1]) / 0.01
    for stage in (1, count):
        duty = stage_duty_id(unit, stage)
        worst[f"Q{stage}"] = abs(state[duty] - expected[duty]) / Q_ABS
    return worst


@pytest.mark.parametrize("name", COLUMN_CASES)
def test_the_column_in_a_flowsheet_reproduces_its_registered_root(
    name: str, registered: pytest.MonkeyPatch
) -> None:
    """S11.A29: `feed_source(s) → column → 2 product_sinks` under the standalone policy object
    reproduces the registered standalone values (max |Δ|/tol ≤ 1) in ≤ 3 Newton iterations."""
    spec = column_case_spec(name)
    run = _run(committed_case(name), S01_DEFAULT_V1)
    assert run.outcome == "CONVERGED", run.message
    (step,) = run.steps
    assert step.iterations <= NEWTON_BUDGET
    assert run.state is not None
    worst = _worst(spec, _expected(name), dict(run.state))
    assert max(worst.values()) <= 1.0, worst


def test_the_column_with_a_recycle_converges_and_closes(registered: pytest.MonkeyPatch) -> None:
    """S11.A29's recycle case: M1's bottoms split 0.2 back to a side feed on stage 5 converges,
    under the application's revision policy; the overall balance closes (feed = distillate +
    purge per component, within the flow tolerance) with a non-zero recycle."""
    run = _run(committed_case(RECYCLE_CASE), T06_REVISION_V2)
    assert run.outcome == "CONVERGED", run.message
    assert run.state is not None
    (feed,) = column_case_spec(RECYCLE_CASE).inlets()
    for c, n in zip("ABC", feed.state.n, strict=True):
        out = run.state[flow_id("S-DISTILLATE", c)] + run.state[flow_id("S-PURGE", c)]
        assert abs(out - n) <= FLOW_REL * n + FLOW_ABS
        assert run.state[flow_id("S-REC", c)] > 0.0


def _worst_wilson(spec: ColumnSpec, case: str, state: dict[str, float]) -> tuple[float, str]:
    """A29 on a Wilson case: S10-C A41's `|Δ|/tolerance` over every registered variable
    (`ref.columns.<case>.root`: stage T and flows, T_c, D, B, x_D, x_B, Q_c, Q_r, reflux and
    distillate flows), plus the product streams against the same entries and tolerances, and their
    pressures (pinned, 0.01 Pa)."""
    found = deviations(case, state)
    ref, bottom = root(case), spec.stage_count
    condenser, stages = ref["condenser"], ref["stages"][str(bottom)]
    found["product"] = []
    for i, c in enumerate(spec.components):
        found["product"] += [
            (
                abs(state[flow_id("S-DISTILLATE", c)] - float(condenser["distillate_n"][i]))
                / float(condenser["tolerance"]["reflux_n_and_distillate_n"]),
                f"S-DISTILLATE.n.{c}",
            ),
            (
                abs(state[flow_id("S-BOTTOMS", c)] - float(stages["liquid_n"][i]))
                / float(stages["tolerance"]["liquid_n"]),
                f"S-BOTTOMS.n.{c}",
            ),
        ]
    found["product"] += [
        (
            abs(state[temperature_id("S-DISTILLATE")] - float(condenser["T"]))
            / float(condenser["tolerance"]["T"]),
            "S-DISTILLATE.T",
        ),
        (
            abs(state[temperature_id("S-BOTTOMS")] - float(stages["T"]))
            / float(stages["tolerance"]["T"]),
            "S-BOTTOMS.T",
        ),
        (abs(state[pressure_id("S-DISTILLATE")] - spec.pressures[0]) / 0.01, "S-DISTILLATE.P"),
        (abs(state[pressure_id("S-BOTTOMS")] - spec.pressures[-1]) / 0.01, "S-BOTTOMS.P"),
    ]
    return worst(found)


def _equals_library_root(spec: ColumnSpec, state: dict[str, float]) -> None:
    """The flowsheet's column columns equal `solve_column`'s accepted root exactly (|Δ| = 0, as
    measured for every SYN-001 case in B3a)."""
    library = solve_column(spec, REAL)
    assert isinstance(library, ColumnSolution), library
    shared = [name for name in library.state if name in state]
    assert shared
    moved = {name: state[name] - library.state[name] for name in shared}
    assert not any(moved.values()), {k: v for k, v in moved.items() if v}


@pytest.mark.parametrize("name", WILSON_CASES)
def test_the_wilson_column_in_a_flowsheet_reproduces_its_registered_root(
    name: str, registered_wilson: pytest.MonkeyPatch
) -> None:
    """S11.A29 (C-MW, C-EW): on `wilson-ig-v2`, the flowsheet reproduces S10-C's registered root
    (max |Δ|/tol ≤ 1) in ≤ 3 Newton iterations, and equals the standalone `solve_column` root."""
    spec = column_case_spec(name)
    run = _run(committed_case(name), S01_DEFAULT_V1)
    assert run.outcome == "CONVERGED", run.message
    (step,) = run.steps
    assert step.iterations <= NEWTON_BUDGET
    assert run.state is not None
    state = dict(run.state)
    largest = _worst_wilson(spec, name, state)
    assert largest[0] <= 1.0, largest
    _equals_library_root(spec, state)


# -- S11.A79 (units design §4.6, WO-D5) ------------------------------------------------------------


def test_a79_the_wilson_record_source_selects_v2() -> None:
    """The Wilson `SELECTABLE_BASES` entry is `wilson-ig-v2`, the count stays 127, and the binder
    and the verifier each construct v2 for it."""
    wilson = [b for b in SELECTABLE_BASES if b.record_source == WILSON_RECORDS]
    assert len(SELECTABLE_BASES) == 127
    assert wilson == [WILSON_BASIS] and WILSON_BASIS.provider_id == "wilson-ig-v2"
    assert type(basis_provider(WILSON_BASIS)) is WilsonIdealGasProviderV2
    assert type(fresh_provider(WILSON_BASIS)) is WilsonIdealGasProviderV2
    assert "wilson-ig-v1" not in {b.provider_id for b in SELECTABLE_BASES}


@pytest.mark.parametrize("name", [*WILSON_CASES, WILSON_STRIPPER])
def test_a79_the_wilson_columns_on_v2_equal_v1s_library_root(name: str) -> None:
    """The column cases' x_final on the selected `wilson-ig-v2` basis (the registry rows, not a
    patch) equal `solve_column`'s root on a `wilson-ig-v1` provider exactly: the switch moves no
    value (measured before and after D5: 1508 values over six runs, `float.hex` equal)."""
    binding = bind_revision_flowsheet(committed_case(name))
    assert isinstance(binding, RevisionBinding), binding
    (unit,) = (u for u in binding.flowsheet.units() if u.model_id == "syn001.column")
    assert unit.provider.describe().provider_id == "wilson-ig-v2"
    assert REAL.describe().provider_id == "wilson-ig-v1"
    run = _run(committed_case(name), T06_REVISION_V2)
    assert run.outcome == "CONVERGED", run.message
    assert run.state is not None
    _equals_library_root(column_case_spec(name), dict(run.state))


# -- §7 Q11 ----------------------------------------------------------------------------------------


def test_a_wilson_column_with_a_none_end_is_admitted(registered_wilson: pytest.MonkeyPatch) -> None:
    """§7 Q11 (recorded): `solve_column` accepts a Wilson stripper (no condenser) at library level,
    so the flowsheet admits it; under both the standalone policy object and the application's
    revision policy it converges to the library root exactly."""
    spec = column_case_spec(WILSON_STRIPPER)
    assert spec.condenser == "none" and spec.top is not None
    for policy in (S01_DEFAULT_V1, T06_REVISION_V2):
        run = _run(committed_case(WILSON_STRIPPER), policy)
        assert run.outcome == "CONVERGED", run.message
        (step,) = run.steps
        assert step.iterations <= NEWTON_BUDGET
        assert run.state is not None
        _equals_library_root(spec, dict(run.state))


# -- S11.A24′ --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "document",
    [lambda: committed_case("M1"), lambda: case_document("SYN-001-UL-C1")],
    ids=["M1-column", "T05-C1"],
)
def test_a_revision_region_has_no_edge_3_continuation(
    document: Callable[[], dict[str, Any]], registered: pytest.MonkeyPatch
) -> None:
    """S11.A24′ (§10.8, L-COL-9): the column's region has no specification rows and no
    continuation parameter, exactly as the registered T05 heater→flash revision."""
    binding = bind_revision_flowsheet(document())
    assert isinstance(binding, RevisionBinding), binding
    plan, _ = plan_revision(binding, T06_REVISION_V2)
    assert isinstance(plan, ExecutionPlan), plan
    (step,) = plan.steps
    assert step.region is not None and step.region.specification_rows == ()
    found = continuation_parameter(
        specification_rows=step.region.specification_rows,
        target_variables=step.region.target_variables,
        spec=binding.spec,
        structural_pattern=compile_problem(binding.spec).structural_pattern(),
    )
    assert found is None


# -- Q29 -------------------------------------------------------------------------------------------


def test_a_column_under_the_ptc_policy_is_refused_typed(registered: pytest.MonkeyPatch) -> None:
    """§10.13 Q29 (recorded): `eo_core = "ptc"` maps no holdup for the column's stage rows, so
    the region ends `PTC_MAPPING_INVALID` before any attempt (L-COL-10 at I1), not an exception."""
    run = _run(committed_case("M1"), T08_PTC_V1)
    assert run.outcome == "PTC_MAPPING_INVALID"
    (step,) = run.steps
    assert step.message.startswith("ptc_mapping_invalid(S02:stage:1:mole:A")
