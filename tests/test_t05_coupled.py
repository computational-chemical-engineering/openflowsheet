"""T05 W13: the coupled cases C1, C2 and C3 solved on the common path, against the twin.

Spec `docs/derivations/T05-unit-models-spec.md` §11 (A17–A19, A26; §11.5's allowances), §19 Q10
and §22 W0.9; design note `docs/design/T05-generalization.md` §2.1 (the path:
`bind_revision_flowsheet` → `plan_revision` → `execute_plan`), §2.4 (per case) and §9 Q-B.

The expectation is `ref.coupled_cases.<case>` (`benchmarks/t05/reference_values.yaml`, the design
lane's 40-digit twin, read through `t05_support.REF`); no registered number is copied here. Every
column of the solved state is compared with it at its full registered precision.

**The mapping from the reference to the solver's columns** (`reference_columns`):

| `ref.coupled_cases.<case>` | column | kind |
| --- | --- | --- |
| `streams.<S>.n_mol_per_s[i]` | `<S>.n.<c_i>` | molar_flow |
| `streams.<S>.T_K`, `.P_Pa` | `<S>.T`, `<S>.P` | temperature, pressure |
| a lifted stream's `vapor_n_mol_per_s[i]` | `<S>.vap.<c_i>` | molar_flow |
| a lifted stream's `liquid_n_mol_per_s[i]` | `<S>.liq.<c_i>` | molar_flow |
| the sums of those two lists | `<S>.V`, `<S>.L` | molar_flow |
| the sum of `streams.<S>.n_mol_per_s` (a flash product) | `<S>.N` | molar_flow |
| `duty_W.<U>`, `work_W.<U>` | `<U>.Q`, `<U>.W` | heat_rate |
| `extent_mol_per_s.<U>` | `<U>.xi` | molar_flow |

`c_i` is `constants.components[i]`. Sums are taken exactly over the registered decimals. The test
asserts both directions: every solver column has a reference value, and every registered stream
coordinate, duty, work and extent is a solver column — so nothing registered goes unchecked.

A20's first branch (C3X: `INITIALIZATION_FAILED`, `initializer_failed(U-HX):
temperature_cross(cold_end)`) is `tests/test_t05_c3x_initializer.py`; it is not repeated here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from t05_support import REF

from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.graph.report import StructuralReport
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import PlanResult, execute_plan
from openflowsheet.orchestrator.region import RegionResult
from openflowsheet.orchestrator.revision import INITIALIZER_ID, plan_revision
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.verify.certificate import BoundDeclaration, alias_document

CASE_DIR = Path(__file__).resolve().parent.parent / "benchmarks" / "t05" / "cases"
CASES = ("SYN-001-UL-C1", "SYN-001-UL-C2", "SYN-001-UL-C3")
POLICY = SolvePolicy(policy_id="T05-W13", residual_tolerances={}, scales={})
COMPONENTS: tuple[str, ...] = tuple(REF["constants"]["components"])
#: Spec §11.5 (T02 §6.4): ten times each kind's residual tolerance. Work is a `heat_rate` column.
ALLOWANCE: Mapping[str, float] = {
    "molar_flow": 3.1e-7,
    "temperature": 1e-5,
    "pressure": 0.1,
    "heat_rate": 1e-2,
}


@dataclass(frozen=True)
class Solved:
    binding: RevisionBinding
    plan: ExecutionPlan
    report: StructuralReport
    run: PlanResult

    @property
    def region(self) -> RegionResult:
        (step,) = self.run.steps
        assert isinstance(step.detail, RegionResult), step.detail
        return step.detail


def solve(case: str) -> Solved:
    """Design note §2.1 steps 1–3, verbatim."""
    binding = bind_revision_flowsheet(yaml.safe_load((CASE_DIR / f"{case}.yaml").read_text()))
    assert isinstance(binding, RevisionBinding), binding
    plan, report = plan_revision(binding, POLICY)
    assert isinstance(plan, ExecutionPlan), plan
    run = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=POLICY)
    return Solved(binding, plan, report, run)


@pytest.fixture(scope="module")
def solved() -> dict[str, Solved]:
    return {case: solve(case) for case in CASES}


def reference_columns(case: str) -> tuple[dict[str, Decimal], set[str]]:
    """`ref.coupled_cases.<case>` by column id (the module docstring's table), at full precision;
    and the columns that are registered directly rather than as a sum."""
    entry = REF["coupled_cases"][case]
    values: dict[str, Decimal] = {}
    primary: set[str] = set()

    def put(column: str, value: Decimal, *, registered: bool = True) -> None:
        values[column] = value
        if registered:
            primary.add(column)

    for stream, state in entry["streams"].items():
        flows = [Decimal(n) for n in state["n_mol_per_s"]]
        for component, n in zip(COMPONENTS, flows, strict=True):
            put(f"{stream}.n.{component}", n)
        put(f"{stream}.T", Decimal(state["T_K"]))
        put(f"{stream}.P", Decimal(state["P_Pa"]))
        put(f"{stream}.N", sum(flows, Decimal(0)), registered=False)
        if "vapor_n_mol_per_s" in state:
            for phase, key, total in (("vap", "vapor", "V"), ("liq", "liquid", "L")):
                split = [Decimal(n) for n in state[f"{key}_n_mol_per_s"]]
                for component, n in zip(COMPONENTS, split, strict=True):
                    put(f"{stream}.{phase}.{component}", n)
                put(f"{stream}.{total}", sum(split, Decimal(0)), registered=False)
    for field, suffix in (("duty_W", "Q"), ("work_W", "W"), ("extent_mol_per_s", "xi")):
        for unit, value in (entry.get(field) or {}).items():
            put(f"{unit}.{suffix}", Decimal(value))
    return values, primary


def deviations(solved: Solved, case: str) -> dict[str, tuple[float, str]]:
    """Per kind, the worst `|x - x_ref|` over the solved state and the column it is at."""
    expected, _ = reference_columns(case)
    state = solved.run.state
    assert state is not None
    kinds = solved.binding.spec.variable_kinds
    worst: dict[str, tuple[float, str]] = {}
    for column in solved.binding.spec.variable_ids:
        error = float(abs(Decimal(state[column]) - expected[column]))
        kind = kinds[column]
        if kind not in worst or error > worst[kind][0]:
            worst[kind] = (error, column)
    return worst


# -- A17, A18, A19 -------------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES)
def test_the_case_converges_on_the_common_path(case: str, solved: dict[str, Solved]) -> None:
    """One `solve_eo` region from `traversal-G0-v1`, `CONVERGED` in one attempt (design Q-A)."""
    result = solved[case]
    (step,) = result.plan.steps
    assert step.kind == "solve_eo"
    assert result.run.outcome == "CONVERGED", result.run.message
    assert [s.outcome for s in result.run.steps] == ["CONVERGED"]
    region = result.region
    assert len(region.attempts) == 1
    assert region.branch_provenance[0]["initializer_source"] == INITIALIZER_ID


@pytest.mark.parametrize("case", CASES)
def test_the_mapping_covers_the_solver_and_the_reference(
    case: str, solved: dict[str, Solved]
) -> None:
    expected, primary = reference_columns(case)
    columns = set(solved[case].binding.spec.variable_ids)
    assert sorted(columns - set(expected)) == [], "solver columns with no reference value"
    assert sorted(primary - columns) == [], "registered values with no solver column"


@pytest.mark.parametrize("case", CASES)
def test_every_column_is_the_twins_within_the_allowance(
    case: str, solved: dict[str, Solved]
) -> None:
    """A17 (C1), A18 (C2), A19 (C3): streams, duties, work and extent within §11.5."""
    outside = {
        kind: (error, column)
        for kind, (error, column) in deviations(solved[case], case).items()
        if not error <= ALLOWANCE[kind]
    }
    assert outside == {}


@pytest.mark.parametrize("case", CASES)
def test_the_unit_phase_signatures_are_the_twins(case: str, solved: dict[str, Solved]) -> None:
    (signature,) = solved[case].region.signatures
    assert dict(signature) == REF["coupled_cases"][case]["signatures"]


# -- A26: `branch_found` -------------------------------------------------------------------------

#: Spec A26 / design note §2.4, exact and in declaration order.
BRANCH_FOUND = {
    "SYN-001-UL-C1": [["U-HEAT", "LIQUID"], ["U-VLV", "TWO_PHASE"], ["U-PHF", "TWO_PHASE"]],
    "SYN-001-UL-C2": [["U-RX", "LIQUID"]],
    "SYN-001-UL-C3": [["U-PHF", "TWO_PHASE"]],
}


@pytest.mark.parametrize("case", CASES)
def test_the_root_fingerprint_lists_the_registered_branch(
    case: str, solved: dict[str, Solved]
) -> None:
    fingerprint = solved[case].region.root_fingerprint
    assert fingerprint is not None
    found = [list(entry) for entry in fingerprint["branch_found"]]
    assert found == BRANCH_FOUND[case]
    order = [unit.unit_id for unit in solved[case].binding.flowsheet.units()]
    assert [unit for unit, _ in found] == sorted((u for u, _ in found), key=order.index)


# -- W0.9 (spec Q10) and design Q-B --------------------------------------------------------------

#: Every copy-shaped row of each case (`+/-1` over two columns of one kind, or one column and a
#: constant of zero drop), T05's and K02's, and how T01 classifies it: `certified` — it closes a
#: cycle of copies, is eliminated from the closure count with a certificate, and is still
#: evaluated; `retained` — a tree edge of the copy forest, an ordinary matched row. No case has an
#: `uncertified_affine` row. Measured: `docs/t05-measurements.md`, "W0.9 / Q-B".
COPY_ROWS: Mapping[str, Mapping[str, str]] = {
    "SYN-001-UL-C1": {
        "U-HEAT:HEAT-pressure": "retained",
        "U-PHF:PHF-T": "retained",
        "U-PHF:PHF-pressure:vapor": "retained",
        "U-PHF:PHF-pressure:liquid": "retained",
    },
    "SYN-001-UL-C2": {
        "U-MIX:MIX-pressure:0": "retained",
        "U-MIX:MIX-pressure:1": "retained",
        "U-RX:RX-pressure": "retained",
        "U-SEP:SEP-T:top": "retained",
        "U-SEP:SEP-T:bottom": "retained",
        "U-SEP:SEP-P:top": "certified",
        "U-SEP:SEP-P:bottom": "retained",
    },
    "SYN-001-UL-C3": {
        "U-HX:HX-pressure:hot": "retained",
        "U-HX:HX-pressure:cold": "retained",
        "U-MIX:MIX-pressure:0": "retained",
        "U-MIX:MIX-pressure:1": "retained",
        "U-PHF:PHF-T": "retained",
        "U-PHF:PHF-pressure:vapor": "retained",
        "U-PHF:PHF-pressure:liquid": "retained",
        "U-SPLIT:SPLIT-T:recycle": "retained",
        "U-SPLIT:SPLIT-T:purge": "retained",
        "U-SPLIT:SPLIT-P:recycle": "certified",
        "U-SPLIT:SPLIT-P:purge": "retained",
    },
}
#: The certificates themselves: the retained rows each certified row repeats, with signs.
CERTIFIED: Mapping[str, list[tuple[str, list[list[Any]]]]] = {
    "SYN-001-UL-C1": [],
    "SYN-001-UL-C2": [
        ("U-SEP:SEP-P:top", [["U-MIX:MIX-pressure:1", 1], ["U-RX:RX-pressure", -1]]),
    ],
    "SYN-001-UL-C3": [
        (
            "U-SPLIT:SPLIT-P:recycle",
            [["U-MIX:MIX-pressure:1", 1], ["U-PHF:PHF-pressure:liquid", -1]],
        ),
    ],
}


def _classification(report: StructuralReport, row: str) -> str:
    certified = {c.row_id for c in report.certificates if c.consistent}
    if row in certified:
        return "certified"
    if row in report.uncertified_affine_rows:
        return "uncertified_affine"
    return "retained"


@pytest.mark.parametrize("case", CASES)
def test_t01_classifies_the_copy_rows(case: str, solved: dict[str, Solved]) -> None:
    result = solved[case]
    report = result.report
    assert report.finding == "STRUCTURALLY_CLOSED"
    assert report.uncertified_affine_rows == ()
    assert report.conflicts == ()
    rows = set(result.binding.spec.equation_ids)
    assert sorted(set(COPY_ROWS[case]) - rows) == []
    got = {row: _classification(report, row) for row in COPY_ROWS[case]}
    assert got == COPY_ROWS[case]
    documents = [c.as_document() for c in report.certificates]
    assert [(d["row_id"], d["equals"]) for d in documents] == CERTIFIED[case]
    assert all(d["constant_mismatch"] == 0.0 for d in documents)
    # T01's canonical matching (column -> row) leaves exactly the certified rows unmatched: a
    # retained copy row is matched like any other row.
    matched = set(report.canonical_matching.values())
    assert sorted(rows - matched) == sorted(row for row, _ in CERTIFIED[case])


@pytest.mark.parametrize("case", CASES)
def test_the_certified_aliases_at_x_final_are_the_plans(
    case: str, solved: dict[str, Solved]
) -> None:
    """Design Q-B: `verify_revision`'s step-2 comparison (note §4.2), made here directly — the
    declaration's certified aliases re-derived at `x_final` equal the region plan's, and both are
    T01's certificates."""
    result = solved[case]
    state = result.run.state
    assert state is not None
    (step,) = result.plan.steps
    assert step.solve_plan is not None
    target = BoundDeclaration(result.binding.spec, compile_problem(result.binding.spec), state)
    found = [alias_document(row) for row in target.partition.elimination.eliminated]
    planned = [alias_document(row) for row in step.solve_plan.eliminated_rows]
    assert found == planned
    assert [(d["row_id"], d["equals"]) for d in planned] == CERTIFIED[case]
