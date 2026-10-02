"""T05b B15, the `T05-W13` (v1) half: DZ-1 and DZ-2, the dormant PH-type outlets (T05b spec §8,
§9.3, §12.5; ADR 0012 D6, D7). Replaces T05 A28, retired by ADR 0012 (spec §16).

Two mini-flowsheets with instances from `SYN-001-UL-C1.yaml` and a feed of `(0, 0, 0)` at 330 K
and `P_r`: DZ-1, feed → `U-VLV` (`P_spec = 9e4 Pa`) → `S2` (`vapor_liquid`) → sink; DZ-2, feed →
`U-PHF` (`Q_spec = 0`, `ΔP = 0`) → `S2` (vapour), `S3` (liquid) → sinks. Each runs
`plan_revision` → `execute_plan` (policy `T05-W13`, the v1 contract) → `verify_revision`.

What T05 registered and what moved. Under v1 the start is the exact root, so the solve is
`CONVERGED` at iteration 0 in the `TWO_PHASE` form with no Jacobian formed, as before. The
declaration's full form at that root still has exactly its three equilibrium rows identically
zero, rank 15 of 18 (`ref.dormant_cases.*.full_form`). What changed (ADR 0012): `branch_found`
reports `ZERO_FLOW` for a split with `V = L = 0` under every literal (D6), and the verifier
judges the root on the split's zero-flow form (D7, spec §9.3) — 10 × 10, the label row
`<U>:zero-flow-label` in place of the unit's energy row — so the certificate is `VERIFIED`,
`NO_RANK_LOSS_DETECTED`. The v2 half of B15 (a `ZERO_FLOW` attempt, its free columns) is
`test_t05b_zero_flow.py` (T05b W7).

`scripts/t05_evidence_manifest.py` records A28 retired (T05b W8) and imports nothing from here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pytest
from t05_w12_support import Feed, Outlet, connection_pin, duty_pin, mini_revision, unit_instance
from t05b_support import REF, number

from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compile.reference import state_vector
from openflowsheet.models.revision_flowsheet import parse_revision
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import PlanResult, execute_plan
from openflowsheet.orchestrator.region import RegionResult
from openflowsheet.orchestrator.revision import plan_revision
from openflowsheet.orchestrator.splits import lifted_splits
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.verify.certificate import (
    BoundDeclaration,
    SolutionCertificate,
    verify_revision,
)
from openflowsheet.verify.regularity import screen, target_jacobian
from openflowsheet.verify.zero_flow import zero_flow_splits

POLICY = SolvePolicy(policy_id="T05-W13", residual_tolerances={}, scales={})
#: The dormant feed: `(0, 0, 0)` at 330 K and `P_r`.
FEED = (Feed("inlet", "S1", "liquid", (0.0, 0.0, 0.0), 330.0, 1.0e5),)
DORMANT: dict[str, Any] = REF["dormant_cases"]


@dataclass(frozen=True)
class Case:
    unit: str
    equilibrium: str
    document: dict[str, Any]
    outlets: tuple[str, ...]
    #: Its registered case in `ref.dormant_cases`.
    registered: str


CASES = {
    "valve": Case(
        unit="U-VLV",
        equilibrium="VLV-equilibrium",
        document=mini_revision(
            "A28-valve",
            unit_instance("SYN-001-UL-C1", "U-VLV"),
            FEED,
            [Outlet("outlet", "S2", "vapor_liquid")],
            [connection_pin("SPEC-valve-P", "S2", "state.P", 9.0e4)],
        ),
        outlets=("S2",),
        registered="DZ-1",
    ),
    "ph_flash": Case(
        unit="U-PHF",
        equilibrium="PHF-equilibrium",
        document=mini_revision(
            "A28-ph-flash",
            unit_instance("SYN-001-UL-C1", "U-PHF"),
            FEED,
            [Outlet("vapor", "S2", "vapor"), Outlet("liquid", "S3", "liquid")],
            [duty_pin("SPEC-phf-Q", "U-PHF", 0.0)],
        ),
        outlets=("S2", "S3"),
        registered="DZ-2",
    ),
}


@dataclass(frozen=True)
class Solved:
    binding: RevisionBinding
    plan: ExecutionPlan
    run: PlanResult


def _solve(case: Case) -> Solved:
    binding = bind_revision_flowsheet(case.document)
    assert isinstance(binding, RevisionBinding), binding
    plan, _ = plan_revision(binding, POLICY)
    assert isinstance(plan, ExecutionPlan), plan
    run = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=POLICY)
    return Solved(binding, plan, run)


@pytest.fixture(scope="module")
def solved() -> dict[str, Solved]:
    return {name: _solve(case) for name, case in CASES.items()}


def _certificate(case: Case, solved: Solved) -> SolutionCertificate:
    return verify_revision(
        solved.binding,
        case.document,
        solved.run,
        solve_plan=solved.plan.steps[-1].solve_plan,
    )


@pytest.mark.parametrize("name", CASES)
def test_b15_v1_converged_at_iteration_zero_in_the_two_phase_form(
    name: str, solved: dict[str, Solved]
) -> None:
    run = solved[name].run
    assert run.outcome == "CONVERGED", run.message
    assert run.counters.jacobian_calls == 0
    (step,) = run.steps
    assert isinstance(step.detail, RegionResult)
    assert [a.iterations for a in step.detail.attempts] == [0]
    assert [list(map(list, a.signature)) for a in step.detail.attempts] == [
        [[CASES[name].unit, "TWO_PHASE"]]
    ]


@pytest.mark.parametrize("name", CASES)
def test_b15_the_root_is_exact(name: str, solved: dict[str, Solved]) -> None:
    case, run = CASES[name], solved[name].run
    assert run.state is not None
    root = DORMANT[case.registered]["root"]
    assert {column: run.state[column] for column in root} == {
        column: number(value) for column, value in root.items()
    }
    flows = {
        column: value
        for column, value in run.state.items()
        if column.split(".")[1] in ("n", "vap", "liq", "V", "L", "N")
    }
    assert flows and all(value == 0.0 for value in flows.values()), flows
    assert [run.state[f"{stream}.T"] for stream in case.outlets] == [330.0] * len(case.outlets)
    if name == "ph_flash":
        assert run.state["U-PHF.Q"] == 0.0


@pytest.mark.parametrize("name", CASES)
def test_b15_the_full_form_keeps_t05s_structure(name: str, solved: dict[str, Solved]) -> None:
    """The declaration's own target at the dormant root: exactly the split's equilibrium rows
    vanish identically, rank 15 of 18 (`ref.*.full_form`, T05 A28's structure re-derived). This
    is why the verifier does not judge a `ZERO_FLOW` root on it."""
    case, entry = CASES[name], solved[name]
    registered = DORMANT[case.registered]["full_form"]
    state = entry.run.state
    assert state is not None
    target = BoundDeclaration(entry.binding.spec, compile_problem(entry.binding.spec), state)
    matrix, scaled_residual, identity = target_jacobian(target, state)
    eliminated = {row.row_id for row in target.partition.elimination.eliminated}
    rows = [
        row
        for row in target.compiled.jacobian(
            np.array(state_vector(target.spec, state)), target.context
        ).row_ids
        if row not in eliminated
    ]
    dense = matrix.toarray()
    assert dense.shape == (registered["dimension"],) * 2
    zero = [rows[i] for i in range(dense.shape[0]) if not np.any(dense[i])]
    assert zero == registered["identically_zero_rows"]
    assert zero == [f"{case.unit}:{case.equilibrium}:{c}" for c in "ABC"]
    evidence = screen(matrix, jacobian_identity=identity, scaled_residual=scaled_residual)
    assert evidence.status == "RANK_DEFICIENT"
    assert evidence.as_document()["escalation"]["rank"] == registered["rank"]


@pytest.mark.parametrize("name", CASES)
def test_b15_the_zero_flow_form_is_the_registered_one(name: str, solved: dict[str, Solved]) -> None:
    """The verifier's reduction (spec §7.2, §9.3) keeps exactly `ref.*.zero_flow_form`'s rows and
    columns: the declaration's rows and columns minus the split's, plus the label row."""
    case, entry = CASES[name], solved[name]
    registered = DORMANT[case.registered]["zero_flow_form"]
    state = entry.run.state
    assert state is not None
    view = parse_revision(case.document)
    splits = lifted_splits(
        [(i.unit_id, i.model_id, i.wiring) for i in view.instances], view.components
    )
    (form,) = zero_flow_splits(view, splits, state)
    assert form.unit == case.unit
    spec = entry.binding.spec
    kept_rows = [row for row in spec.equation_ids if row not in form.rows]
    assert form.label is not None
    label, outlet, source = form.label
    label_entry = DORMANT[case.registered]["label"]
    assert (label, outlet, source) == (
        label_entry["row"],
        label_entry["T_out"],
        label_entry["T_label"],
    )
    # `mini_revision` names its feed `U-FEED-0`; the registry names it `U-FEED`.
    renamed = [row.replace("U-FEED-0:", "U-FEED:", 1) for row in (*kept_rows, label)]
    assert sorted(renamed) == sorted(registered["rows"])
    assert sorted(c for c in spec.variable_ids if c not in form.columns) == sorted(
        registered["columns"]
    )


@pytest.mark.parametrize("name", CASES)
def test_b15_v1_verified_on_the_zero_flow_form(name: str, solved: dict[str, Solved]) -> None:
    """Spec §9.3: `VERIFIED`, `NO_RANK_LOSS_DETECTED` with dimension 10 and the registered
    scaled `rcond₁`; `residual.<U>:zero-flow-label` present and `0.0`; every compiled residual
    `0.0`; nothing fails."""
    case, entry = CASES[name], solved[name]
    registered = DORMANT[case.registered]["zero_flow_form"]
    certificate = _certificate(case, entry)
    assert certificate.verification_status == "VERIFIED", certificate.limitations
    assert not certificate.false_success_detected
    assert certificate.regularity is not None
    assert certificate.regularity.status == "NO_RANK_LOSS_DETECTED"
    assert certificate.regularity.dimension == registered["dimension"]
    assert certificate.regularity.rcond_1 is not None
    # `ref` registers it to six decimals.
    assert abs(certificate.regularity.rcond_1 - float(registered["rcond1_scaled"])) <= 5e-7
    residuals = {c.id: c for c in certificate.checks if c.category == "residual"}
    label = residuals.pop(f"residual.{case.unit}:zero-flow-label")
    assert label.value == 0.0 and label.result == "pass"
    assert label.tolerance == 1e-6
    assert residuals and all(c.value == 0.0 for c in residuals.values()), residuals
    assert [c.id for c in certificate.checks if c.result == "fail"] == []


@pytest.mark.parametrize("name", CASES)
def test_b15_v1_branch_found_is_zero_flow(name: str, solved: dict[str, Solved]) -> None:
    """ADR 0012 D6: `V = L = 0` → `ZERO_FLOW`, under v1 too (the attempt ran `TWO_PHASE`);
    the certificate's `phase_branch` records every stream `ZERO_FLOW`, as before."""
    case, entry = CASES[name], solved[name]
    detail = entry.run.steps[-1].detail
    assert isinstance(detail, RegionResult) and detail.root_fingerprint is not None
    assert detail.root_fingerprint["branch_found"] == [[case.unit, "ZERO_FLOW"]]
    certificate = _certificate(case, entry)
    assert certificate.root_fingerprint is not None
    assert certificate.root_fingerprint["branch_found"] == [[case.unit, "ZERO_FLOW"]]
    streams = ("S1", *case.outlets)
    assert {s: certificate.phase_branch[s] for s in streams} == dict.fromkeys(streams, "ZERO_FLOW")
