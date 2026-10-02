"""T06 W5: every corpus case measured against its registration (T6-A01…A20, A63, A64).

Spec `docs/derivations/T06-corpus-spec.md` as amended (Amendment 1) §3.2 and §13's corpus
assertions; the registration is `benchmarks/registry.yaml`'s `corpus` section (W4). A case whose
outcome an earlier package already asserts is not run again: `MEASURED_BY` names the test that
measures it, and `test_every_case_is_measured_by_an_existing_test` keeps the map from rotting.
What is measured here is what nothing else measured under the registration:

- **A02** on the revision path under the registered policy (`T06-revision-v2`; STA-04 also under
  `T05b-v2`) for every revision-built `verified_at_reference` case, including STA-03's two unit
  variants: `CONVERGED` from `traversal-G0-v1`, `VERIFIED`, and every registered coordinate within
  T02 §6.4's allowances of the case's registered root. The T05b fixtures were registered under
  `T05b-v2` and T05's under `T05-W13`; A1 moved the revision path to `T06-revision-v1`, and A4
  to `T06-revision-v2`.
- **A02, NUM-04:** the certificate of the EO region started at NET-01's tear root (T02 A23
  asserts the solve, and no test certified it).
- **A11:** STA-02's absent component is `+0.0` in every certified coordinate.
- **A04:** STR-02's validation report; **A04/A08:** neither STR-02 nor STR-06 is compiled or
  solved by `validate()` or by either binding.
- **A63:** NET-02's control under both edge-off policies, against every field the registry gives it.
- **A19, VER-02/VER-03:** REG-ε refused `INCONCLUSIVE(identity_mismatch)` (W5's strict xfail:
  K04's identity refusal did not exist; T06 W14 implements it, A82).
- **A20:** no case of a kind other than `verified_at_reference` is registered to end `VERIFIED`
  (STR-05's twin and ADV-06 L excepted), and each is measured by a test (ADV-06: W7's).
"""

from __future__ import annotations

import copy
import importlib
import math
import sys
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from decimal import Decimal
from functools import cache
from typing import Any

import numpy as np
import pytest
import scipy.sparse as sp
import t05b_support as t05b
import yaml
from conftest import REPO_ROOT, load_yaml
from t06_support import ALLOWANCE, registered_root, worst_ratio
from test_t05_w1c_executor import _reference as nominal_reference
from test_t06_w4_registry import BY_ID, CASES, CONSTRUCTED

from openflowsheet.application.binding import Binding, Unbound, bind_revision_or_reason
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.application.validation import validate
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.graph.analysis import analyse
from openflowsheet.graph.trace import trace_declaration
from openflowsheet.orchestrator import tear
from openflowsheet.orchestrator.execution import (
    ExecutionPlan,
    build_execution_plan,
    declaration_identity,
)
from openflowsheet.orchestrator.executor import PlanResult, execute_plan
from openflowsheet.orchestrator.region import solve_region, syn001_lifted_splits
from openflowsheet.orchestrator.revision import INITIALIZER_ID, plan_revision
from openflowsheet.orchestrator.tear import solve_tear
from openflowsheet.verify.certificate import verify_bound, verify_revision
from openflowsheet.verify.regularity import screen

Document = dict[str, Any]
Root = dict[str, tuple[Decimal, float]]

#: The corpus fixtures that are not files: T05b's revisions, built by `t05b_support`.
BUILDERS: dict[str, Callable[[], Document]] = {
    "T05b:DZ-3": t05b.dz3,
    "T05b:DZ-7": t05b.dz7,
    "T05b:NP-1": lambda: t05b.near_pure("NP-1"),
    "T05b:SC-1": t05b.sc1,
    "T05b:SC-2": t05b.sc2,
    "T05b:SC-3": t05b.sc3,
}


def _document(fixture: str, path: str | None) -> Document:
    if path is None:
        return BUILDERS[fixture]()
    loaded: Document = yaml.safe_load((REPO_ROOT / path).read_text("utf-8"))
    return loaded


# -- registered roots, read where each registration keeps them ----------------------------------


def _allowance(column: str) -> float:
    """T02 §6.4's allowance by column kind: `T`, `P`, duty, work; every other column is a flow
    (`n.<c>`, `vap.<c>`, `liq.<c>`, phase totals `V`, `L`, products-style `N`)."""
    suffix = column.rsplit(".", 1)[1]
    return ALLOWANCE[suffix] if suffix in ("T", "P", "Q", "W") else ALLOWANCE["n"]


def _stream_root(root: Mapping[str, Any]) -> Root:
    """T05b's two root shapes: a flat `{column: value}` (DZ-3, DZ-7), or per-stream records beside
    flat unit columns (SC-1…SC-3). A key that is neither a stream record nor a dotted column is a
    derived quantity (`U-PHF_beta`), not a state coordinate, and is not compared."""
    out: Root = registered_root(
        {"streams": {key: value for key, value in root.items() if isinstance(value, dict)}}
    )
    for key, value in root.items():
        if not isinstance(value, dict) and "." in key:
            out[key] = (Decimal(value), _allowance(key))
    return out


def _near_pure_root(root: Mapping[str, Any]) -> Root:
    """T05b's NP shape (as `test_t05b_contract._near_pure_root` reads it): S2 is the vapour
    product and S3 the liquid, both at the flash temperature."""
    out: Root = {}
    for stream, key in (("S2", "vapor_mol_per_s"), ("S3", "liquid_mol_per_s")):
        for component, value in zip("ABC", root[key], strict=True):
            out[f"{stream}.n.{component}"] = (Decimal(value), ALLOWANCE["n"])
        out[f"{stream}.T"] = (Decimal(root["T_K"]), ALLOWANCE["T"])
    return out


def _nominal_root() -> Root:
    """P01's 20-digit SYN-001-nominal state, per stream coordinate (`test_t05_w1c_executor`)."""
    return {
        column: (Decimal(repr(value)), _allowance(column))
        for column, value in nominal_reference().items()
        if column.startswith("S")
    }


def expected_root(expected: Mapping[str, Any]) -> Root:
    key = expected["reference_key"]
    if key == "variants[case_id=SYN-001-nominal]":
        return _nominal_root()
    entry: Any = load_yaml(REPO_ROOT / expected["reference"])
    for part in key.split("."):
        entry = entry[part]
    if "streams" in entry:
        return registered_root(entry)
    if key.startswith("near_pure_cases."):
        return _near_pure_root(entry)
    return _stream_root(entry)


# -- A02 on the revision path ----------------------------------------------------------------


@dataclass(frozen=True)
class Run:
    case: str
    fixture: str
    revision: str | None
    policy: str


def _revision_runs() -> Iterator[Run]:
    """Every registered revision-path run of a `verified_at_reference` case: the case's own
    registration and each `also_registered` one, per unit variant."""
    for case in CASES:
        if case["expected"]["outcome"] != "verified_at_reference":
            continue
        runs = [(case["path"], case.get("policy"))]
        runs += [(extra["path"], extra["policy"]) for extra in case.get("also_registered", ())]
        for path, policy in runs:
            if path != "revision_eo":
                continue
            for variant in case.get("variants") or [case]:
                yield Run(case["id"], variant["fixture"], variant["revision"], policy)


REVISION_RUNS = list(_revision_runs())


@dataclass(frozen=True)
class Solved:
    document: Document
    binding: RevisionBinding
    plan: ExecutionPlan
    run: PlanResult


@cache
def solved(run: Run) -> Solved:
    document = _document(run.fixture, run.revision)
    binding = bind_revision_flowsheet(document)
    assert isinstance(binding, RevisionBinding), binding
    policy = CONSTRUCTED[run.policy]
    plan, _ = plan_revision(binding, policy)
    assert isinstance(plan, ExecutionPlan), plan
    result = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=policy)
    return Solved(document, binding, plan, result)


def test_the_revision_runs_are_the_registered_ones() -> None:
    """20 revision-built `verified_at_reference` cases, STA-04 once more under `T05b-v2`, and
    STA-03's two unit variants on the revision path (A56's path)."""
    assert len(REVISION_RUNS) == 23
    assert {run.policy for run in REVISION_RUNS} == {"T06-revision-v2", "T05b-v2"}
    assert [run.case for run in REVISION_RUNS if run.policy == "T05b-v2"] == ["STA-04"]
    assert sorted(run.fixture for run in REVISION_RUNS if run.case == "STA-03") == [
        "SYN-001-T06-STA03-degC",
        "SYN-001-T06-STA03-kgs",
    ]


@pytest.mark.parametrize("run", REVISION_RUNS, ids=lambda r: f"{r.case}:{r.fixture}:{r.policy}")
def test_a02_every_revision_case_is_verified_at_its_registered_root(run: Run) -> None:
    item = solved(run)
    assert item.run.outcome == "CONVERGED", (item.run.outcome, item.run.message)
    assert item.run.state is not None
    certificate = verify_revision(
        item.binding, item.document, item.run, solve_plan=item.plan.steps[-1].solve_plan
    )
    assert certificate.verification_status == "VERIFIED", [
        (check.id, check.result) for check in certificate.checks if check.result != "pass"
    ]
    ratio, column = worst_ratio(item.run.state, expected_root(BY_ID[run.case]["expected"]))
    assert ratio <= 1.0, (ratio, column)


def test_a02_net02_takes_its_registered_items() -> None:
    """NET-02 under `T06-revision-v2`: the registered provenance (A64's; G1 asserts the rest)."""
    (run,) = [run for run in REVISION_RUNS if run.case == "NET-02"]
    (step,) = [step for step in solved(run).run.steps if step.kind == "solve_eo"]
    registered = BY_ID["NET-02"]["expected"]
    assert step.eo_recovery == registered["eo_recovery"] == "taken"
    items = [
        [item["opening_source"], item["initializer_source"], item["core_outcome"]]
        for item in step.detail.branch_provenance
    ]
    assert items == registered["items"]


def test_a11_sta02s_absent_component_is_positive_zero_everywhere() -> None:
    (run,) = [run for run in REVISION_RUNS if run.case == "STA-02"]
    state = solved(run).run.state
    assert state is not None
    absent = {
        column: value
        for column, value in state.items()
        if column.endswith((".n.B", ".vap.B", ".liq.B"))
    }
    assert len(absent) >= 8, sorted(absent)  # every stream's n.B, and the lifted splits'
    not_positive_zero = {
        column: value
        for column, value in absent.items()
        if not (value == 0.0 and math.copysign(1.0, value) == 1.0)
    }
    assert not_positive_zero == {}


# -- A02, NUM-04: the exact initial root's certificate --------------------------------------


def test_a02_num04_the_region_at_the_tear_root_converges_at_iteration_0_and_is_verified() -> None:
    """NUM-04 (T02 A23 on SYN-001-nominal's legacy binding): the EO region started from the tear
    solve's reconstructed state converges at iteration 0 with no Jacobian, and its certificate on
    the bound declaration is `VERIFIED` at P01's root."""
    case = BY_ID["NUM-04"]
    document = _document(case["fixture"], case["revision"])
    binding = bind_revision_or_reason(document)
    assert isinstance(binding, Binding), binding
    policy = CONSTRUCTED[case["policy"]]
    spec, flowsheet = binding.spec, binding.flowsheet
    model_version, constants = declaration_identity(spec)
    report = analyse(
        spec,
        binding.graph,
        row_units=binding.row_units,
        model_version=model_version,
        constants_sha256=constants,
    )
    plan = build_execution_plan(
        spec=spec,
        declaration=trace_declaration(
            spec,
            row_units=binding.row_units,
            model_version=model_version,
            constants_sha256=constants,
        ),
        graph=binding.graph,
        report=report,
        manifests={unit.unit_id: unit.manifest() for unit in flowsheet.units()},
        policy=policy,
    )
    (step,) = [step for step in plan.steps if step.kind == "solve_eo"]
    assert step.region is not None
    root, _ = solve_tear(flowsheet)
    assert root.outcome == "CONVERGED" and root.final_state is not None
    result = solve_region(
        compiled=compile_problem(spec),
        spec=spec,
        region=step.region,
        state=dict(root.final_state),
        splits=syn001_lifted_splits(flowsheet.components),
        provider=flowsheet.provider,
        policy=policy,
        initializer_source="user_guess",
    )
    registered = case["expected"]
    assert result.outcome == registered["core_outcome"] == "CONVERGED"
    assert result.iterations == registered["iterations"] == 0
    assert result.counters.jacobian_calls == registered["jacobian_calls"] == 0
    certificate = verify_bound(binding, document, result, solve_plan=step.solve_plan)
    assert certificate.verification_status == registered["verdict"] == "VERIFIED"
    ratio, column = worst_ratio(result.state, expected_root(registered))
    assert ratio <= 1.0, (ratio, column)


# -- A63: NET-02's edge-off control, against the registry --------------------------------------


@pytest.mark.parametrize("policy", BY_ID["NET-02"]["controls"][0]["policies"])
def test_a63_net02s_control_meets_its_registration(policy: str) -> None:
    (control,) = BY_ID["NET-02"]["controls"]
    case = BY_ID["NET-02"]
    item = solved(Run(case["id"], case["fixture"], case["revision"], policy))
    (step,) = [step for step in item.run.steps if step.kind == "solve_eo"]
    assert item.run.outcome == step.outcome == control["code"] == "BOUND_BLOCKED"
    assert (step.eo_recovery, step.eo_recovery_unsupported) == (
        control["eo_recovery"],
        control["eo_recovery_unsupported"],
    )
    assert step.iterations == control["iteration"] == 1
    assert [item["initializer_source"] for item in step.detail.branch_provenance] == [
        INITIALIZER_ID
    ]


# -- A04, A08: STR-02 and STR-06 are diagnosed, never compiled or solved -------------------------


def _checks(report: Any) -> dict[str, Any]:
    return {check.id: check for check in report.checks}


def test_a04_str02_is_a_draft_that_names_the_missing_specification() -> None:
    case = BY_ID["STR-02"]
    registered = case["expected"]
    report = validate(_document(case["fixture"], case["revision"]))
    assert report.status == registered["status"] == "DRAFT"
    checks = _checks(report)
    assert [checks[name].result for name in registered["not_run"]] == ["NOT_RUN"] * 5
    naming = [
        check
        for check in report.checks
        if registered["message_names"] in check.message
        and list(check.implicated_objects) == registered["implicated"]
    ]
    assert naming, [(c.id, c.result, c.message, c.implicated_objects) for c in report.checks]
    assert not [check for check in report.checks if check.result == "FAIL"]


#: The four entry points that compile or solve (`compile_problem`, `solve_tear`, `execute_plan`,
#: `solve_region`), found wherever a module imported them.
_SPIED = (
    ("openflowsheet.compile.casadi_backend", "compile_problem"),
    ("openflowsheet.orchestrator.tear", "solve_tear"),
    ("openflowsheet.orchestrator.executor", "execute_plan"),
    ("openflowsheet.orchestrator.region", "solve_region"),
)


def _spy(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []
    for module_name, name in _SPIED:
        original = getattr(importlib.import_module(module_name), name)

        def spy(*args: Any, _name: str = name, _original: Any = original, **kwargs: Any) -> Any:
            calls.append(_name)
            return _original(*args, **kwargs)

        for module in list(sys.modules.values()):
            if (
                module is not None
                and module.__name__.startswith("openflowsheet")
                and getattr(module, name, None) is original
            ):
                monkeypatch.setattr(module, name, spy)
    return calls


@pytest.mark.parametrize("case_id", ["STR-02", "STR-06"])
def test_a04_a08_a_diagnosed_case_is_never_compiled_or_solved(
    case_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = BY_ID[case_id]
    document = _document(case["fixture"], case["revision"])
    calls = _spy(monkeypatch)
    report = validate(document)
    legacy = bind_revision_or_reason(document)
    general = bind_revision_flowsheet(document)
    assert report.status == case["expected"]["status"]
    assert isinstance(legacy, Unbound), legacy
    assert isinstance(general, Unbound), general
    assert calls == []
    assert (case["expected"]["compiled"], case["expected"]["solved"]) == (False, False)
    # The spy is live: the parent, SYN-001-nominal, solved through it is counted.
    nominal = bind_revision_or_reason(_document("SYN-001-nominal", BY_ID["NET-01"]["revision"]))
    assert isinstance(nominal, Binding), nominal
    result, _ = tear.solve_tear(nominal.flowsheet)
    assert result.outcome == "CONVERGED"
    assert calls[0] == "solve_tear" and "compile_problem" in calls, calls


# -- A19: VER-02 and VER-03 -----------------------------------------------------------------


def test_a19_ver02_ver03_a_regularized_matrix_with_a_stale_identity_is_refused() -> None:
    """K04 §7.6 REG-ε: SQ-0's screen on `J + 1e-6` with an identity that is not the target's.

    W5 held this as a strict xfail: `screen` recorded `jacobian_identity` and compared nothing
    (measured `NO_RANK_LOSS_DETECTED`, `rcond₁ = 1.0` — the regularized matrix masks SQ-0's rank
    loss). T06 W14 implements the refusal (§8.4 (A2), A82, R-084); VER-03's stale Jacobian is
    `tests/test_t06_w14_identity.py::test_a82_ver03_a_stale_jacobian_is_refused`."""
    registered = BY_ID["VER-02"]["expected"]
    assert registered["regularity"] == BY_ID["VER-03"]["expected"]["regularity"]
    target = {
        "model_version": "SQ-0@" + "0" * 64,
        "constants_sha256": "0" * 64,
        "state_sha256": "f" * 64,
        "phase_signature": None,
    }
    evidence = screen(
        sp.csc_matrix(np.array([[0.0 + 1e-6]])),
        jacobian_identity=dict(target, state_sha256="0" * 64),
        target_identity=target,
    )
    assert f"{evidence.status}({evidence.inconclusive_reason})" == registered["regularity"]
    assert evidence.rcond_1 == 1.0, "the matrix's numbers are still recorded"


# -- A20 and the measurement map ------------------------------------------------------------

_HERE = "tests/test_t06_w5_corpus.py::"
_W7 = "tests/test_t06_w7_adv06.py::"
_A02 = _HERE + "test_a02_every_revision_case_is_verified_at_its_registered_root"
_K04_VERIFIED = (
    "tests/test_k04_checks.py::test_a03_to_a08_every_check_passes_at_the_registered_solutions"
)
_K03_TEAR = "tests/test_k03_tear.py::test_the_tear_converges_to_the_twenty_digit_recycle"
_K03_PRODUCTS = (
    "tests/test_k03_attempts.py::"
    "test_g00_the_solved_flowsheet_reproduces_the_registered_products_and_duties"
)

#: Where each corpus case's registered outcome is measured. A case measured by an earlier
#: package's test is not run again here (T06 W5's brief: reuse, do not duplicate).
MEASURED_BY: dict[str, tuple[str, ...]] = {
    "STR-01": (_A02,),
    "STR-02": (
        _HERE + "test_a04_str02_is_a_draft_that_names_the_missing_specification",
        _HERE + "test_a04_a08_a_diagnosed_case_is_never_compiled_or_solved",
    ),
    "STR-03": (
        "tests/test_t01_structural.py::"
        "test_a09_the_conflicting_heater_revision_is_rejected_at_validation",
    ),
    "STR-04": (
        "tests/test_t01_structural.py::"
        "test_a18_sq_1_is_square_by_totals_and_defective_in_both_directions",
    ),
    "STR-05": (
        "tests/test_t05b_openings.py::test_b31b_leaving_zero_flow_downstream_converges",
        "tests/test_t05b_openings.py::test_b31b_the_certificate_is_unverified_at_the_dew_point",
        "tests/test_t05b_openings.py::test_b31i_off_the_dew_point_the_restart_certifies",
    ),
    "STR-06": (
        "tests/test_t06_w1a_units.py::test_str06_component_references_are_checked",
        _HERE + "test_a04_a08_a_diagnosed_case_is_never_compiled_or_solved",
    ),
    "STA-01": (_A02,),
    "STA-02": (_A02, _HERE + "test_a11_sta02s_absent_component_is_positive_zero_everywhere"),
    "STA-03": (
        _A02,
        "tests/test_t06_w1a_units.py::test_a55_validation_records_the_conversion",
        "tests/test_t06_w1a_units.py::test_a55_the_tear_solve_and_certificate_are_nominals",
        "tests/test_t06_w1a_units.py::test_a56_the_revision_solve_and_certificate_are_nominals",
        "tests/test_t06_w1a_units.py::test_a57_an_unconverted_unit_or_kind_is_refused",
    ),
    "STA-04": (
        _A02,
        "tests/test_t06_w1b_order.py::test_a59_sta04_solves_and_certifies_as_c2",
        "tests/test_t06_w1b_order.py::test_a60_every_order_of_c2_is_c2",
    ),
    "STA-05": (_A02,),
    "NUM-01": (
        "tests/test_k03_newton.py::test_bnd01_lands_on_its_bound_exactly_and_then_converges",
        "tests/test_k03_newton.py::test_bnd01_first_iterate_is_positive_zero_bit_for_bit",
    ),
    "NUM-02": (
        "tests/test_k03_newton.py::test_num02_converges_in_exactly_one_step_to_the_analytic_answer",
    ),
    "NUM-03": (_A02,),
    "NUM-04": (
        "tests/test_t02_region.py::test_a23_the_region_solves_the_same_function_as_the_tear",
        _HERE
        + "test_a02_num04_the_region_at_the_tear_root_converges_at_iteration_0_and_is_verified",
    ),
    "NUM-05": (
        "tests/test_k03_newton.py::test_num05_a_residual_with_no_root_stagnates_and_claims_nothing",
    ),
    "NUM-06": (
        "tests/test_k03_newton.py::test_num06_exhausts_the_line_search_on_an_evaluator_domain",
    ),
    "THM-01": (_A02,),
    "THM-02": (_A02,),
    "THM-03": (_K03_TEAR, _K03_PRODUCTS, _K04_VERIFIED),
    "THM-04": (_K03_TEAR, _K03_PRODUCTS, _K04_VERIFIED),
    "THM-05": ("tests/test_t05_reactor.py::test_reactor_construction_refusal",),
    "THM-06": (
        "tests/test_k02_cache.py::test_a_one_ulp_change_of_temperature_misses",
        "tests/test_k02_cache.py::test_a_negative_zero_component_hits_because_it_is_the_same_state",
        "tests/test_k02_heater_flash.py::test_the_cache_changes_nothing_a_unit_reports",
    ),
    "THM-07": (_A02,),
    "THM-08": (_A02,),
    "THM-09": (_A02,),
    "THM-10": (_A02,),
    "NET-01": (_K03_TEAR, _K03_PRODUCTS, _K04_VERIFIED),
    "NET-02": (
        _A02,
        _HERE + "test_a02_net02_takes_its_registered_items",
        _HERE + "test_a63_net02s_control_meets_its_registration",
        "tests/test_t06_f4_edge3.py::test_g1_net02_is_solved_through_the_restart_and_certified",
        "tests/test_t06_f4_edge3.py::test_g2_the_edge_off_control_is_unchanged",
    ),
    "NET-03": (_A02,),
    "NET-04": (
        "tests/test_t02_recycle.py::test_a07_linear_variants_terminate_at_exactly_iteration_4",
        "tests/test_t02_recycle.py::test_a08_nonlinear_variants_follow_the_twin",
        "tests/test_t02_recycle.py::test_a09_rec_01_substitution_detects_oscillation_and_damps",
    ),
    "NET-05": (
        "tests/test_t02_a02.py::"
        "test_a28_a29_the_specified_duty_is_met_at_the_registered_heater_temperature",
        "tests/test_t04_certificate.py::"
        "test_a30_the_registered_states_are_verified_on_the_bound_declaration",
    ),
    "NET-06": (_A02,),
    "NET-07": (_A02,),
    "NET-08": (_A02,),
    "NET-09": (_A02,),
    "NET-10": (_A02,),
    "NET-11": (_A02, "tests/test_t06_w2_verifier.py::test_a39_net11_is_verified_at_the_twin"),
    "ADV-01": (
        "tests/test_t04_edge3.py::test_a04_a08_edge_3_takes_the_registered_path",
        "tests/test_t04_certificate.py::"
        "test_a30_the_registered_states_are_verified_on_the_bound_declaration",
        "tests/test_t04_edge3.py::test_a09_hom_n_with_the_edge_off_phs_05_cycles_exactly_as_t03_a12",
    ),
    "ADV-02": (
        "tests/test_t04_homotopy.py::"
        "test_a03_a_stall_leaves_a_partial_checkpoint_at_its_level_and_no_certificate",
    ),
    "ADV-03": (
        "tests/test_t04_homotopy.py::"
        "test_a03_a_stall_leaves_a_partial_checkpoint_at_its_level_and_no_certificate",
    ),
    "ADV-04": (
        "tests/test_t04_ptc_region.py::test_a14_an_invalid_mapping_is_refused_before_anything_runs",
    ),
    "ADV-05": ("tests/test_t03_roots.py::test_a19_rec_05_three_routes_two_roots",),
    "VER-01": (
        "tests/test_k04_injections.py::test_a17_inj1_wrong_energy_bookkeeping",
        "tests/test_t05_w12_injections.py::"
        "test_inj_t1_the_valves_trivial_root_is_caught_by_the_fresh_flash_and_the_split",
    ),
    "VER-02": (
        _HERE + "test_a19_ver02_ver03_a_regularized_matrix_with_a_stale_identity_is_refused",
    ),
    "VER-03": (
        _HERE + "test_a19_ver02_ver03_a_regularized_matrix_with_a_stale_identity_is_refused",
        "tests/test_t06_w14_identity.py::test_a82_ver03_a_stale_jacobian_is_refused",
        "tests/test_t04_certificate.py::test_a31_iii_a_state_that_is_not_the_fingerprinted_one_is_refused",
    ),
    "VER-04": (
        "tests/test_k04_regularity.py::test_a24_an_exactly_singular_matrix_is_rank_deficient_not_a_crash",
        "tests/test_k04_regularity.py::test_a25_the_bound_is_recorded_and_the_verdict_is_verified",
        "tests/test_k04_regularity.py::test_a34_a_tolerance_tight_enough_trips_the_absolute_limit",
    ),
    "VER-05": ("tests/test_k04_injections.py::test_a16_inj4_a_relaxed_policy_is_never_verified",),
    "ADV-06": (
        _W7 + "test_the_double_is_bound_under_every_compiled_evaluation",
        _W7 + "test_a16_h_is_never_verified_or_relaxed",
        _W7 + "test_a17_m_converges_unverified_on_the_witness_alone",
        _W7 + "test_a18_l_converges_verified",
    ),
}

#: Registered cases no test measures yet, with what will (none since W7).
PENDING: dict[str, str] = {}

#: T6-A01…A20 and the two A1 corpus facts, to the corpus cases that carry them in the registry;
#: A01 is the table itself (W4), A09/A10 are superseded by A55–A60 (STA-03, STA-04).
ASSERTION_TESTS: dict[str, tuple[str, ...]] = {
    "T6-A01": (
        "tests/test_t06_w4_registry.py::test_a01_the_corpus_is_the_twins_table",
        "tests/test_t06_w4_registry.py::test_a01_the_counts_are_the_twins_and_the_spec",
    ),
}


def _exists(node: str) -> bool:
    path, name = node.split("::")
    module = importlib.import_module(path.removeprefix("tests/").removesuffix(".py"))
    return callable(getattr(module, name, None))


def test_every_case_is_measured_by_an_existing_test() -> None:
    assert set(MEASURED_BY).isdisjoint(PENDING)
    assert sorted({*MEASURED_BY, *PENDING}) == sorted(BY_ID)
    missing = [
        node
        for nodes in (*MEASURED_BY.values(), *ASSERTION_TESTS.values())
        for node in nodes
        if not _exists(node)
    ]
    assert missing == []


def test_every_corpus_assertion_is_carried_by_a_case() -> None:
    """A02…A20 (less A09/A10, superseded) each name at least one registered case or control;
    A63/A64 too."""
    named = [case["assertion"] for case in CASES]
    named += [control["assertion"] for case in CASES for control in case.get("controls", ())]
    carried = {assertion.strip() for text in named for assertion in text.split(",")}
    expected = {f"T6-A{number:02d}" for number in range(2, 21)} - {"T6-A09", "T6-A10"}
    assert expected | {"T6-A63", "T6-A64"} <= carried


#: A20's exceptions: the registered sub-fixtures of a non-`verified_at_reference` case that end
#: `VERIFIED`, and the key of the registration that says so. A20's text names STR-05's twin and
#: ADV-06 L; §3.2's own rows also register VER-01's twin (K04 INJ-1's uninjected solve) and
#: VER-04's SQ-1 (`b = 2^-15`) `VERIFIED` — reported to the design lane as a wording gap in A20.
A20_EXCEPTIONS: dict[str, tuple[str, str]] = {
    "STR-05": ("twin", "verdict"),
    "ADV-06": ("levels", "L"),
    "VER-01": ("twin_verdict", ""),
    "VER-04": ("SQ-1", ""),
}


def _verified_claims(value: Any) -> Iterator[str]:
    """Every string in a registered expectation that claims `VERIFIED`: one whose first word is
    `VERIFIED`, or a `CONVERGED; VERIFIED` level. A value under `never` is a prohibition."""
    if isinstance(value, str):
        words = value.replace(";", " ").split()
        if words[:1] == ["VERIFIED"] or words[:2] == ["CONVERGED", "VERIFIED"]:
            yield value
    elif isinstance(value, Mapping):
        for key, item in value.items():
            if key != "never":
                yield from _verified_claims(item)
    elif isinstance(value, list):
        for item in value:
            yield from _verified_claims(item)


def test_a20_no_other_kind_is_registered_to_end_verified() -> None:
    """A20: a case of a kind other than `verified_at_reference` never ends `VERIFIED`, except the
    registered sub-fixtures of `A20_EXCEPTIONS`; each case's outcome is measured by the tests
    `MEASURED_BY` names."""
    for case in CASES:
        expected = copy.deepcopy(case["expected"])
        if expected["outcome"] == "verified_at_reference":
            continue
        assert case["id"] in MEASURED_BY or case["id"] in PENDING, case["id"]
        if case["id"] in A20_EXCEPTIONS:
            key, inner = A20_EXCEPTIONS[case["id"]]
            excepted = expected.pop(key) if not inner else expected[key].pop(inner)
            assert list(_verified_claims(excepted)), (case["id"], excepted)
        assert list(_verified_claims(expected)) == [], case["id"]
    assert [
        case["id"]
        for case in CASES
        if case["expected"]["outcome"] != "verified_at_reference"
        and list(_verified_claims(case["expected"]))
    ] == sorted(A20_EXCEPTIONS, key=list(BY_ID).index)
