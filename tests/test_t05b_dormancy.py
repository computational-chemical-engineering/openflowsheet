"""T05b W7b: the zero-flow form of a dormant non-lifted outlet (spec §7.6–§7.10; ADR 0012 D12).

- B23: the dormancy-form registry (`splits.DORMANCY_RULES`) is `ref.dormancy_forms`; the forms it
  builds for each case are the registered ones; `check_agreement` (g) refuses a form that
  disagrees with the declaration. (The verifier's own table is compared with it in
  `test_t05_table_independence.py`.)
- The verifier (§9.3): the reduction of a dormant non-lifted outlet chosen from the state alone —
  so a `T05-W13` solve of DZ-6…DZ-9, which converges at iteration 0 in the declared form, is
  judged on the zero-flow form (§7.10; B24's and B25's v1 halves); the exchanger's terminal checks
  at a dormant side; F9's feed condition on a lifted reduction; B29's INJ-B5.
- The region under `T05b-v2` (§7.8): B24 (DZ-6 pump, DZ-9 mixer), B25 (DZ-7, DZ-8 exchanger) at
  iteration 0 in the zero-flow form; B26 (DZ-10, a moving label on a pump outlet); B27 (DZ-12, a
  restart leaving the form, with §7.8 (ii)'s outlet reset); B28's non-lifted half (DZ-11,
  `zero_flow_conflict(U-HX:HX-energy-hot)`); B29's INJ-B4; B20 (d) (form switches recorded,
  deterministically); B30 (a) (no item on any registered case); the lattice and the cause grammar
  with items (§7.8 (i)).

Values marked *regression* are self-generated: pinned beside their assertion, reported to the
design lane if they move, never re-pinned. `revision` names its feeds `U-FEED-0`, `U-FEED-1`; the
registry names them `U-FEED`, `U-FEED2` (`t05b_support.registered_name`).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import cache
from typing import Any

import pytest
from t05_w12_support import bind, planned_step
from t05b_support import (
    DORMANT_CASES,
    DORMANT_NON_LIFTED_CASES,
    NEAR_PURE_CASES,
    POLICY_V2,
    REF,
    SINGLE_COMPONENT_CASES,
    dz1,
    dz3,
    dz6,
    dz7,
    dz9,
    dz10,
    dz11,
    dz12,
    error,
    fresh_flash_ratios,
    judged_where,
    near_pure,
    registered_name,
    registered_state,
    revision_projection,
    solve_from_v2,
)
from test_t05_coupled import POLICY as POLICY_V1
from test_t05_w11_cases import case_document

from openflowsheet.application.revision_binding import RevisionBinding
from openflowsheet.graph.trace import trace_declaration
from openflowsheet.models.revision_flowsheet import parse_revision
from openflowsheet.models.syn001 import TEMPERATURE_TOLERANCE
from openflowsheet.orchestrator.execution import ExecutionPlan, declaration_identity
from openflowsheet.orchestrator.executor import PlanResult, execute_plan
from openflowsheet.orchestrator.region import DormancyForm, RegionResult
from openflowsheet.orchestrator.revision import instances_of, plan_revision
from openflowsheet.orchestrator.splits import (
    DORMANCY_RULES,
    check_agreement,
    closure_types,
    dormancy_forms,
    lifted_splits,
    zero_flow_forms,
)
from openflowsheet.orchestrator.trace import SolvePolicy, Trace
from openflowsheet.verify import CheckResult
from openflowsheet.verify.certificate import SolutionCertificate, verify_revision
from openflowsheet.verify.zero_flow import zero_flow_splits

CASES: dict[str, Any] = REF["dormant_non_lifted_cases"]
CONFLICTS: dict[str, Any] = REF["zero_flow_conflicts"]


def _registered(case: str) -> dict[str, Any]:
    return CASES[case] if case in CASES else CONFLICTS[case]


def _forms(binding: RevisionBinding) -> tuple[DormancyForm, ...]:
    flowsheet = binding.flowsheet
    return dormancy_forms(instances_of(flowsheet), flowsheet.units(), flowsheet.components)


# ------------------------------------------------------------------- B23: the registry


def _rendered(model: str, configuration: str | None) -> list[dict[str, str]]:
    """The registry's rules for one key in `ref.dormancy_forms`' notation."""
    return [
        {
            "item": f"<U>.{rule.outlet}",
            "trigger": f"every stream of port {rule.trigger} exactly dormant",
            "swapped_row": f"<U>:{rule.swapped}",
            "label_row": "<U>:zero-flow-label" + (f":{rule.side}" if rule.side else ""),
            "label": f"T({rule.outlet}) - T(first stream of {rule.trigger})",
            "declared_phase": rule.declared_phase,
        }
        for rule in DORMANCY_RULES[(model, configuration)]
    ]


def test_b23_the_registry_is_the_registered_one() -> None:
    """Spec §7.6's table, exactly: each model and configuration, its outlets, item keys, trigger
    ports, swapped rows, label rows, label ports and declared phases, in signature order."""
    rendered = {
        model if configuration is None else f"{model}(specification={configuration})": _rendered(
            model, configuration
        )
        for model, configuration in DORMANCY_RULES
        # M02 design note §14.2 B13: restricted to the `syn001.` keys, the reference unchanged;
        # the full key set and the `c1.` entry are pinned by `test_m02_wo8_registries`.
        if model.startswith("syn001.")
    }
    assert rendered == REF["dormancy_forms"]


@pytest.mark.parametrize("case", DORMANT_NON_LIFTED_CASES)
def test_b23_each_cases_forms_are_the_registered_ones(case: str) -> None:
    """The forms built for a case's flowsheet, restricted to the ones whose triggers are dormant
    at its registered root (DZ-11: end state), are its registered items, swapped rows and label
    rows; and (g) holds."""
    binding = bind(DORMANT_NON_LIFTED_CASES[case]())
    forms = _forms(binding)
    registered = _registered(case)
    state = registered["root"] if "root" in registered else registered["end_state"]
    active = [
        form for form in forms if all(float(state[name]) == 0.0 for name in form.trigger_flows)
    ]
    items = [form.item for form in active]
    swapped = [form.swapped for form in active]
    if case in CASES:
        assert items == registered["items"]
        assert swapped == registered["swapped_rows"]
        assert {
            label: {"T_out": outlet, "T_label": source}
            for label, outlet, source in (form.label for form in active)
        } == registered["label_rows"]
    else:
        assert items == [item for item, _ in registered["signature"]]
        assert swapped == list(registered["swapped_row_at_end_W"])
    _agreement(binding, forms)


def test_b23_c1_to_c3x_have_the_registered_outlets() -> None:
    """W0.10's table on the implementation: C1's pump, C2's mixer, C3's and C3X's mixer and cold
    side (their hot side is temperature-specified: no form)."""
    found = {
        case: [form.item for form in _forms(bind(case_document(case)))]
        for case in ("SYN-001-UL-C1", "SYN-001-UL-C2", "SYN-001-UL-C3", "SYN-001-UL-C3X")
    }
    assert found == {
        "SYN-001-UL-C1": ["U-PUMP.outlet"],
        "SYN-001-UL-C2": ["U-MIX.outlet"],
        "SYN-001-UL-C3": ["U-HX.cold_outlet", "U-MIX.outlet"],
        "SYN-001-UL-C3X": ["U-HX.cold_outlet", "U-MIX.outlet"],
    }


def test_b23_the_mixers_label_is_its_first_inlet_in_connection_order() -> None:
    """DZ-9: `S1` (330 K) before `S2` (310 K), so the label source is `S1.T`; the reset sums the
    inlets in that order."""
    (form,) = _forms(bind(dz9()))
    assert form.triggers == ("S1", "S2")
    assert form.label == ("U-MIX:zero-flow-label", "S3.T", "S1.T")
    assert form.balance[0] == ("S3.n.A", ("S1.n.A", "S2.n.A"))
    assert form.declared == "LIQUID"


# ------------------------------------------------------- B23: `check_agreement` (g)


def _agreement(binding: RevisionBinding, forms: tuple[DormancyForm, ...]) -> None:
    flowsheet = binding.flowsheet
    instances = instances_of(flowsheet)
    splits = lifted_splits(instances, flowsheet.components)
    model_version, constants = declaration_identity(binding.spec)
    declaration = trace_declaration(
        binding.spec,
        row_units=binding.row_units,
        model_version=model_version,
        constants_sha256=constants,
    )
    check_agreement(
        instances,
        splits,
        binding.spec,
        binding.row_units,
        declaration,
        zero_flow_forms(instances, splits, closure_types(flowsheet.units()), flowsheet.components),
        forms,
    )


@pytest.mark.parametrize(
    ("build", "corrupt", "message"),
    [
        (
            # A row the pump authored that does not read its outlet's temperature.
            dz6,
            lambda f: replace(f, swapped="U-PUMP:PUMP-P"),
            r"^dormancy_form_disagrees\(U-PUMP\.outlet, U-PUMP:PUMP-P\): not a row of U-PUMP "
            r"reading S2\.T$",
        ),
        (
            # A row reading the outlet's temperature that another unit authored.
            dz6,
            lambda f: replace(f, swapped="U-FEED-0:FEED-T"),
            r"^dormancy_form_disagrees\(U-PUMP\.outlet, U-FEED-0:FEED-T\)",
        ),
        (
            # A trigger port the instance does not wire.
            dz6,
            lambda f: replace(f, trigger_port="feed"),
            r"^dormancy_form_disagrees\(U-PUMP\.outlet\): outlet carries \['S2'\], "
            r"feed carries \[\]",
        ),
        (
            # An outlet port the instance does not wire.
            dz7,
            lambda f: replace(f, outlet_port="warm_outlet"),
            r"^dormancy_form_disagrees\(U-HX\.hot_outlet\): warm_outlet carries \[\], hot_inlet",
        ),
        (
            # A label read from the wrong inlet (DZ-9's second).
            dz9,
            lambda f: replace(f, label=(f.label[0], f.label[1], "S2.T")),
            r"^dormancy_form_disagrees\(U-MIX\.outlet\): the label reads S3\.T and S2\.T$",
        ),
    ],
    ids=["swapped-not-reading-T", "foreign-row", "unwired-trigger", "unwired-outlet", "label"],
)
def test_b23_agreement_refuses_a_form_that_disagrees(
    build: Any, corrupt: Any, message: str
) -> None:
    binding = bind(build())
    forms = _forms(binding)
    _agreement(binding, forms)
    with pytest.raises(ValueError, match=message):
        _agreement(binding, (corrupt(forms[0]), *forms[1:]))


# -------------------------------------------------- the verifier (§9.3), on `T05-W13` solves


@dataclass(frozen=True)
class Solved:
    document: dict[str, Any]
    binding: RevisionBinding
    plan: ExecutionPlan
    run: PlanResult
    certificate: SolutionCertificate | None

    @property
    def region(self) -> RegionResult:
        (step,) = self.run.steps
        assert isinstance(step.detail, RegionResult), step.detail
        return step.detail


def _solve(document: dict[str, Any], policy: SolvePolicy) -> Solved:
    binding = bind(document)
    plan, _ = plan_revision(binding, policy)
    assert isinstance(plan, ExecutionPlan), plan
    run = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=policy)
    certificate = None
    if run.outcome == "CONVERGED":
        certificate = verify_revision(binding, document, run, solve_plan=plan.steps[-1].solve_plan)
    return Solved(document, binding, plan, run, certificate)


@cache
def _solved(case: str, contract: str) -> Solved:
    return _solve(DORMANT_NON_LIFTED_CASES[case](), POLICY_V2 if contract == "v2" else POLICY_V1)


#: B24, B25: each traversal-start case's label checks and its zero-flow form's dimension.
AT_THE_START = {
    case: (
        [f"residual.{label}" for label in CASES[case]["label_rows"]],
        CASES[case]["zero_flow_form"]["dimension"],
    )
    for case in ("DZ-6", "DZ-7", "DZ-8", "DZ-9")
}


def _verified_on_the_zero_flow_form(solved: Solved, case: str) -> None:
    """`VERIFIED`, `NO_RANK_LOSS_DETECTED` at the zero-flow form's dimension; each label row's
    check present and `0.0`, no other label check; every compiled residual `== 0.0`."""
    labels, dimension = AT_THE_START[case]
    certificate = solved.certificate
    assert certificate is not None
    assert certificate.verification_status == "VERIFIED", [
        (c.id, c.value) for c in certificate.checks if c.result in ("fail", "unsupported")
    ]
    assert certificate.regularity is not None
    assert certificate.regularity.status == "NO_RANK_LOSS_DETECTED"
    assert certificate.regularity.dimension == dimension
    residuals = {c.id: c for c in certificate.checks if c.category == "residual"}
    assert [check_id for check_id in residuals if ":zero-flow-label" in check_id] == labels
    for check_id in labels:
        assert (residuals[check_id].value, residuals[check_id].result) == (0.0, "pass")
        residuals.pop(check_id)
    assert residuals and all(c.value == 0.0 for c in residuals.values()), residuals


@pytest.mark.parametrize("case", AT_THE_START)
def test_b24_b25_under_v1_converged_in_the_declared_form_and_verified(case: str) -> None:
    """Spec §7.10: `T05-W13` never selects a form — `CONVERGED` at iteration 0 with no Jacobian
    call, signature `[]` — and the verifier's reduction, chosen from the state alone, judges the
    root on the zero-flow form: `VERIFIED` (before W7b: `UNVERIFIED`, `RANK_DEFICIENT`)."""
    solved = _solved(case, "v1")
    assert solved.run.outcome == "CONVERGED", solved.run.message
    assert solved.run.counters.jacobian_calls == 0
    assert [(a.iterations, a.signature) for a in solved.region.attempts] == [(0, ())]
    _verified_on_the_zero_flow_form(solved, case)


@pytest.mark.parametrize("case", ["DZ-7", "DZ-8"])
def test_b25_the_exchangers_terminal_checks_at_a_dormant_side(case: str) -> None:
    """Spec §9.3 (F8): at a dormant side `hot_end` and `cold_end` are `not_applicable` — DZ-7's
    dormant hot side is 10 K below the cold inlet, so judging them would fail both by 10 K
    (`ref…terminal_differences_if_judged_K`) — while `heat_flow` reads only `Q` and passes."""
    solved = _solved(case, "v1")
    assert solved.certificate is not None
    by_id: dict[str, CheckResult] = {c.id: c for c in solved.certificate.checks}
    for end in ("hot_end", "cold_end"):
        check = by_id[f"bounds_and_domain.U-HX.{end}"]
        assert (check.result, check.reason) == ("not_applicable", "ZERO_FLOW")
    heat_flow = by_id["bounds_and_domain.U-HX.heat_flow"]
    assert (heat_flow.result, heat_flow.value) == ("pass", -0.0)
    if case == "DZ-7":
        state = solved.run.state
        assert state is not None
        judged = CASES["DZ-7"]["terminal_differences_if_judged_K"]
        assert state["S1.T"] - state["S4.T"] == float(judged["hot_end"])
        assert state["S2.T"] - state["S3.T"] == float(judged["cold_end"])


def test_b25_dz8_reduces_the_cold_side_only() -> None:
    """DZ-8: both sides dormant, the hot one temperature-specified — no hot label, and `S2.T` is
    the specification's 345 K, not the hot inlet's 350 K."""
    solved = _solved("DZ-8", "v1")
    assert solved.certificate is not None
    ids = {c.id for c in solved.certificate.checks}
    assert "residual.U-HX:zero-flow-label:cold" in ids
    assert "residual.U-HX:zero-flow-label:hot" not in ids
    assert solved.run.state is not None
    assert (solved.run.state["S2.T"], solved.run.state["S4.T"]) == (345.0, 300.0)


def test_f9_a_lifted_reduction_needs_the_feed_dormant() -> None:
    """Spec §9.3 as ruled (finding F9): DZ-1's root with 2 mol/s of B in the valve's feed and its
    split still empty (`V = L = 0`) is not reduced; the dormant root is."""
    document = dz1()
    binding = bind(document)
    view = parse_revision(document)
    flowsheet = binding.flowsheet
    splits = lifted_splits(instances_of(flowsheet), flowsheet.components)
    root = registered_state(REF["dormant_cases"]["DZ-1"]["root"])
    assert [split.unit for split in zero_flow_splits(view, splits, root)] == ["U-VLV"]
    flowing = {**root, "S1.n.B": 2.0, "S2.n.B": 2.0}
    assert zero_flow_splits(view, splits, flowing) == ()


def test_b29_inj_b5_a_label_from_the_wrong_inlet() -> None:
    """INJ-B5: DZ-9's root with `S3.T = 310 K`, inlet 1's temperature: every compiled row is still
    exactly 0 (the mixer's energy row reads nothing at zero flow), and only the label row catches
    it, by `ref…INJ-B5` (−20 K, `2e7 τ_T`); the reduced form stays regular."""
    solved = _solved("DZ-9", "v1")
    state = dict(registered_state(CASES["DZ-9"]["root"]))
    state["S3.T"] = 310.0
    certificate = verify_revision(
        solved.binding,
        solved.document,
        solved.run,
        state=state,
        solve_plan=solved.plan.steps[-1].solve_plan,
    )
    assert certificate.verification_status == "FAILED"
    judged_where(certificate, "final_state", "residual_not_passed")  # K04-F9 X01
    by_id: dict[str, CheckResult] = {c.id: c for c in certificate.checks}
    label = by_id["residual.U-MIX:zero-flow-label"]
    registered = REF["dormant_non_lifted_injections"]["INJ-B5"]
    assert label.result == "fail" and label.value is not None and label.tolerance is not None
    assert error(label.value, registered["residual_U-MIX:zero-flow-label_K"]) <= label.tolerance
    assert abs(label.value) >= 1e5 * TEMPERATURE_TOLERANCE
    compiled = [c for c in certificate.checks if c.category == "residual" and c.id != label.id]
    assert compiled and all(c.result == "pass" for c in compiled)
    assert max(abs(c.value or 0.0) for c in compiled) == float(registered["compiled_rows_max"])
    assert certificate.regularity is not None
    assert certificate.regularity.status == "NO_RANK_LOSS_DETECTED"


# ------------------------------------------------------ the region under `T05b-v2` (§7.8)

#: Spec §13's EO allowances (T02 §6.4), as `ref.tolerances.coupled_allowances` states them.
ALLOWANCE: dict[str, float] = {
    kind: float(value) for kind, value in REF["tolerances"]["coupled_allowances"].items()
}
#: B24, B25: each case's item, its outlet's registered temperature and what else is exact.
AT_THE_START_V2 = {
    "DZ-6": ("U-PUMP.outlet", {"S2.T": 330.0, "U-PUMP.W": 0.0}),
    "DZ-7": ("U-HX.hot_outlet", {"S2.T": 290.0, "S4.T": 300.0, "U-HX.Q": 0.0}),
    "DZ-8": ("U-HX.cold_outlet", {"S2.T": 345.0, "S4.T": 300.0, "U-HX.Q": 0.0}),
    # Inlet 0's label, not inlet 1's 310.0.
    "DZ-9": ("U-MIX.outlet", {"S3.T": 330.0}),
}


def _allowance(column: str) -> float:
    kind = column.rsplit(".", 1)[-1]
    return {"T": ALLOWANCE["T"], "P": ALLOWANCE["P"], "Q": ALLOWANCE["duty"]}.get(
        kind, ALLOWANCE["flow"]
    )


def _flows(state: dict[str, float] | Any) -> list[float]:
    return [v for k, v in state.items() if k.split(".")[1] in ("n", "vap", "liq", "V", "L", "N")]


@pytest.mark.parametrize("case", AT_THE_START_V2)
def test_b24_b25_converged_at_iteration_zero_in_the_zero_flow_form(case: str) -> None:
    """Under `T05b-v2`: `CONVERGED` at iteration 0 with no Jacobian call; the signature is the
    item alone (no lifted unit: the plan's `signature_units` is `[]`, and `branch_found` `[]`);
    the attempt's rows (compiled, then the label) and free columns are `ref…zero_flow_form`'s as
    sets — the swapped energy row out, the label row in, DZ-9's `U-MIX:MIX-pressure:1` eliminated
    by the plan; every flow `== 0.0`, the outlet at its label; `VERIFIED` on the reduced form."""
    item, exact = AT_THE_START_V2[case]
    solved = _solved(case, "v2")
    assert solved.run.outcome == "CONVERGED", solved.run.message
    assert solved.run.counters.jacobian_calls == 0
    region = solved.region
    assert [(a.iterations, [list(e) for e in a.signature]) for a in region.attempts] == [
        (0, [[item, "ZERO_FLOW"]])
    ]
    assert [list(e) for e in region.contexts[0].active_phases] == [[item, "ZERO_FLOW"]]
    assert [p["signature"] for p in region.branch_provenance] == [[[item, "ZERO_FLOW"]]]
    step = solved.plan.steps[-1]
    assert step.region is not None and step.region.signature_units == ()
    assert region.root_fingerprint is not None
    assert region.root_fingerprint["branch_found"] == []
    (context,) = region.contexts
    registered = CASES[case]["zero_flow_form"]
    rows = list(context.row_scales)
    assert sorted(map(registered_name, rows)) == sorted(registered["rows"])
    assert sorted(context.column_scales) == sorted(registered["columns"])
    assert context.jacobian_pattern is not None
    assert context.jacobian_pattern["rows"] == registered["dimension"]
    (label,) = CASES[case]["label_rows"]
    (swapped,) = CASES[case]["swapped_rows"]
    assert rows[-1] == label and swapped not in rows
    if case == "DZ-9":
        eliminated = [row.row_id for row in step.solve_plan.eliminated_rows]
        assert eliminated == CASES["DZ-9"]["eliminated_rows"] == ["U-MIX:MIX-pressure:1"]
    state = solved.run.state
    assert state is not None
    if case != "DZ-7":  # DZ-7's cold side flows; its root below pins it.
        assert _flows(state) and all(value == 0.0 for value in _flows(state))
    assert {column: state[column] for column in exact} == exact
    assert {c: state[c] for c in CASES[case]["root"]} == registered_state(CASES[case]["root"])
    _verified_on_the_zero_flow_form(solved, case)


def test_b24_dz9_declared_mixer_first() -> None:
    """Spec B24 (ruled 2026-09-25, Q-S4 (1)): DZ-9 declared mixer first is solved as declared feeds
    first — `CONVERGED` at iteration 0, `VERIFIED` on a zero-flow form of dimension 15, `S3.T ==
    330.0` — with the other redundant pressure row removed: the attempt's rows are the zero-flow
    form (`ref…zero_flow_form`'s rows with the registered `U-MIX:MIX-pressure:1` restored) minus
    the plan's `eliminated_rows`, which hold exactly the second feed's `FEED-P` (*regression*:
    T01 §8.2's choice in this order, not registered by the twin)."""
    solved = _solve(dz9(mixer_first=True), POLICY_V2)
    assert [entry["id"] for entry in solved.document["instances"]][0] == "U-MIX"
    assert solved.run.outcome == "CONVERGED", solved.run.message
    region = solved.region
    assert [(a.iterations, [list(e) for e in a.signature]) for a in region.attempts] == [
        (0, [["U-MIX.outlet", "ZERO_FLOW"]])
    ]
    step = solved.plan.steps[-1]
    eliminated = [registered_name(row.row_id) for row in step.solve_plan.eliminated_rows]
    assert eliminated == ["U-FEED2:FEED-P"]
    registered = CASES["DZ-9"]
    form = {*registered["zero_flow_form"]["rows"], *registered["eliminated_rows"]}
    (context,) = region.contexts
    assert sorted(map(registered_name, context.row_scales)) == sorted(form - set(eliminated))
    assert context.jacobian_pattern is not None
    assert context.jacobian_pattern["rows"] == registered["zero_flow_form"]["dimension"] == 15
    state = solved.run.state
    assert state is not None
    assert state["S3.T"] == 330.0
    assert _flows(state) and all(value == 0.0 for value in _flows(state))
    _verified_on_the_zero_flow_form(solved, "DZ-9")


def test_b25_dz8_has_no_hot_item_or_label() -> None:
    """DZ-8's hot side is dormant but temperature-specified: no hot item, no hot label row."""
    solved = _solved("DZ-8", "v2")
    (context,) = solved.region.contexts
    assert "U-HX:zero-flow-label:hot" not in context.row_scales
    assert "U-HX:HX-energy-hot" in context.row_scales
    assert "U-HX:HX-energy-cold" not in context.row_scales


@pytest.mark.parametrize("case", ["DZ-7", "DZ-8"])
def test_b25_v2_terminal_checks_at_a_dormant_side(case: str) -> None:
    certificate = _solved(case, "v2").certificate
    assert certificate is not None
    by_id: dict[str, CheckResult] = {c.id: c for c in certificate.checks}
    for end in ("hot_end", "cold_end"):
        assert by_id[f"bounds_and_domain.U-HX.{end}"].result == "not_applicable"
    assert by_id["bounds_and_domain.U-HX.heat_flow"].result == "pass"


# ----------------------------------------------------------- B26: DZ-10, a moving label

DZ10 = CASES["DZ-10"]
#: Regression value (measured 2026-09-25, W7b): the `T05-W13` outcome from DZ-10's registered
#: start. The declared form's first Jacobian is singular (the dormant pump outlet's `S5.T` column
#: is empty, spec §7.7), so v1 cannot take a step — as for DZ-3.
DZ10_V1 = "LINEAR_SOLVE_FAILED"


@cache
def _dz10(contract: str = "v2") -> tuple[RegionResult, Trace]:
    trace = Trace()
    policy = POLICY_V2 if contract == "v2" else POLICY_V1
    result = solve_from_v2(bind(dz10()), registered_state(DZ10["start"]), policy, trace=trace)
    return result, trace


def test_b26_dz10_the_label_moves() -> None:
    """From the registered start (`S2.T … S6.T` each +1 K): `CONVERGED`; every attempt ends its
    signature with the item, no cause names it (Newton keeps the dormant inlet exactly `+0.0`);
    `S5` dormant, `S5.T` back on `S4.T` to `1e-9 K`, `S4.T` on PHF-1's to `1e-5 K`."""
    result, trace = _dz10()
    assert result.outcome == "CONVERGED", result.message
    for attempt in result.attempts:
        assert attempt.signature[-1] == ("U-PUMP.outlet", "ZERO_FLOW")
        assert "U-PUMP.outlet" not in attempt.reason
    assert all("U-PUMP.outlet" not in event.message for event in trace.events)
    state = result.state
    assert all(state[f"S{k}.n.{c}"] == 0.0 for k in (4, 5) for c in "ABC")
    assert abs(state["S5.T"] - state["S4.T"]) <= 1e-9
    assert error(state["S4.T"], DZ10["phf1_T_K"]) <= ALLOWANCE["T"]
    (context, *_) = result.contexts
    registered = DZ10["zero_flow_form"]
    assert sorted(map(registered_name, context.row_scales)) == sorted(registered["rows"])
    assert sorted(context.column_scales) == sorted(registered["columns"])


def _dz10_certificate() -> SolutionCertificate:
    result, _ = _dz10()
    binding = bind(dz10())
    step = planned_step(binding, POLICY_V2)
    return verify_revision(
        binding, dz10(), result, state=dict(result.state), solve_plan=step.solve_plan
    )


#: K04-F9 X08 (regression, measured 2026-09-25, F9 W5): DZ-10's PH flash stops where DZ-3's
#: does (B16), its equilibrium rows at 0.173, 0.197, 0.119 `τ_eq`, flagged, not failing.
DZ10_EQUILIBRIUM_FLAGS = {"A": 0.173, "B": 0.197, "C": 0.119}


def test_b26_dz10_verified() -> None:
    """K04-F9 X08 (B26 amended; ADR 0013 D1): as DZ-3's X07 — `VERIFIED` at the projection, every
    fresh-flash value there ≤ 1e-3 of its tolerance, the dormancy form's label row, every
    residual and the screen (dimension 34) pass, flags only on the equilibrium rows."""
    certificate = _dz10_certificate()
    assert certificate.verification_status == "VERIFIED", [
        (c.id, c.value) for c in certificate.checks if c.result == "fail"
    ]
    judged_where(certificate, "projection")
    ratios = fresh_flash_ratios(certificate.checks)
    assert ratios and max(ratios.values()) <= 1e-3, max(ratios.items(), key=lambda i: i[1])
    by_id = {c.id: c for c in certificate.checks}
    assert by_id["residual.U-PUMP:zero-flow-label"].result == "pass"
    assert all(c.result == "pass" for c in certificate.checks if c.category == "residual")
    assert certificate.regularity is not None
    assert certificate.regularity.status == "NO_RANK_LOSS_DETECTED"
    assert certificate.regularity.dimension == DZ10["zero_flow_form"]["dimension"] == 34
    flagged = {c.id for c in certificate.checks if c.near_threshold}
    assert flagged == {f"residual.U-PHF:PHF-equilibrium:{c}" for c in "ABC"}
    for component, ratio in DZ10_EQUILIBRIUM_FLAGS.items():
        check = by_id[f"residual.U-PHF:PHF-equilibrium:{component}"]
        assert check.value is not None and check.tolerance is not None
        assert abs(check.value) / check.tolerance == pytest.approx(ratio, abs=5e-4)


def test_b26_dz10_what_the_fresh_flash_reads_at_newtons_stop() -> None:
    """The measured failure behind B26's former xfail (2026-09-25, W7b), kept as evidence through
    the table at `x_final` itself (unprojected; *regression*). DZ-10 is DZ-3 with the valve
    replaced by a pump, so its PH flash stops as DZ-3's does, `S2.T` 8.1e-7 K above PHF-1's, and
    the fresh flash of its feed misses the stored split by −9.09e-8 mol/s (2.9 `τ_flow`) and the
    energy balance by −1.33e-3 W (1.3 `τ_E`) — B16's numbers. **Re-registered by T06 A92**
    (W19), as B16: the list gains `phase_admissibility.U-PHF.S1.closure` at 1.0055e-6 K (T06 spec
    §8.8), which the projection resolves (the certificate stays `VERIFIED`)."""
    result, _ = _dz10()
    _, unprojected = revision_projection(bind(dz10()), dz10(), dict(result.state))
    failing = {c.id for c in unprojected if c.result == "fail"}
    assert failing <= {
        "energy_balance.U-PHF",
        "energy_balance.envelope",
        "phase_admissibility.U-PHF.S1.closure",
        "independent_split.U-PHF.S1.total",
        *(f"independent_split.U-PHF.S1.{c}" for c in "ABC"),
    }, failing
    by_id = {c.id: c for c in unprojected}
    split = by_id["independent_split.U-PHF.S1.total"]
    assert split.result == "fail" and split.value == pytest.approx(-9.087e-8, rel=1e-3)
    balance = by_id["energy_balance.U-PHF"]
    assert balance.result == "fail" and balance.value == pytest.approx(-1.3272e-3, rel=1e-3)
    closure = by_id["phase_admissibility.U-PHF.S1.closure"]
    assert closure.result == "fail" and closure.value == pytest.approx(1.0055e-6, rel=1e-3)


def test_b26_dz10_under_v1_is_not_converged() -> None:
    result, _ = _dz10("v1")
    assert result.outcome != "CONVERGED"
    assert result.outcome == DZ10_V1  # regression value


# ------------------------------------------------- B27: DZ-12, leaving the form at a restart

DZ12 = CASES["DZ-12"]
#: Regression values (measured 2026-09-25, W7b): attempt 1's Newton iterations under v2, and the
#: `T05-W13` outcome from DZ-12's start (v1 projects the PH flash's split by the TP flash at
#: 400 K, `VAPOR`, and its declared form's first Jacobian is singular at the dormant `S4`).
DZ12_ATTEMPT1_ITERATIONS = 1
DZ12_V1 = "LINEAR_SOLVE_FAILED"


@cache
def _dz12(contract: str = "v2") -> tuple[RegionResult, Trace]:
    trace = Trace()
    policy = POLICY_V2 if contract == "v2" else POLICY_V1
    result = solve_from_v2(bind(dz12()), registered_state(DZ12["start"]), policy, trace=trace)
    return result, trace


def test_b27_dz12_attempt_0_runs_the_form() -> None:
    """Attempt 0 opens on the liquid-form root: `U-PHF` `LIQUID` and `S2` dormant, so the hot
    side runs its form — 30 rows including `U-HX:zero-flow-label:hot`, excluding
    `U-HX:HX-energy-hot` — and every row vanishes at the start (iteration 0); its `LIQUID` branch
    is inadmissible (`Σ x K = 3.424` at 400 K)."""
    result, _ = _dz12()
    assert result.outcome == "CONVERGED", result.message
    assert len(result.attempts) == 2
    first = result.attempts[0]
    assert [list(e) for e in first.signature] == DZ12["attempt0"]["signature"]
    assert (first.solver_outcome, first.iterations) == ("CONVERGED", 0)
    assert first.reason == "inadmissible(S1, all_liquid)"
    context = result.contexts[0]
    assert context.jacobian_pattern is not None
    assert context.jacobian_pattern["rows"] == DZ12["attempt0"]["form"]["dimension"] == 30
    assert "U-HX:zero-flow-label:hot" in context.row_scales
    assert "U-HX:HX-energy-hot" not in context.row_scales
    measured = first.observations["admissibility:S1"]
    assert abs(measured - float(DZ12["attempt0"]["closure"].rsplit("= ", 1)[1])) <= 1e-9


def test_b27_dz12_attempt_1_leaves_the_form() -> None:
    """The PH closure at `H_split = 30 000 W` answers `TWO_PHASE`; `S2` flows, so the item leaves,
    recomputed after the split is set (§7.8 (ii)) — in no cause string; attempt 1 runs 34 rows with
    `U-HX:HX-energy-hot` back, its opening reset `S4.n := S2.n`, and converges (not
    `LINEAR_SOLVE_FAILED`)."""
    result, trace = _dz12()
    second = result.attempts[1]
    assert [list(e) for e in second.signature] == DZ12["attempt1"]["signature"]
    assert (second.outcome, second.solver_outcome) == ("CONVERGED", "CONVERGED")
    assert second.iterations == DZ12_ATTEMPT1_ITERATIONS  # regression value
    context = result.contexts[1]
    assert context.jacobian_pattern is not None
    assert (
        context.jacobian_pattern["rows"]
        == DZ12["attempt1"]["opening_with_outlet_reset"]["dimension"]
    )
    assert "U-HX:HX-energy-hot" in context.row_scales
    assert "U-HX:zero-flow-label:hot" not in context.row_scales
    opened = [event.message for event in trace.events if event.kind == "attempt_opened"]
    assert opened == ["initial", DZ12["attempt1"]["opening_message"]]
    assert all("U-HX.hot_outlet" not in event.message for event in trace.events)


def test_b27_dz12_the_root_is_registered_and_verified() -> None:
    result, _ = _dz12()
    for column, value in DZ12["root"].items():
        assert error(result.state[column], value) <= _allowance(column), column
    binding = bind(dz12())
    step = planned_step(binding, POLICY_V2)
    certificate = verify_revision(
        binding, dz12(), result, state=dict(result.state), solve_plan=step.solve_plan
    )
    assert certificate.verification_status == "VERIFIED", [
        (c.id, c.value) for c in certificate.checks if c.result == "fail"
    ]
    assert certificate.regularity is not None
    assert certificate.regularity.dimension == DZ12["zero_flow_form"]["dimension"]
    assert not any("zero-flow-label" in c.id for c in certificate.checks)


def test_b27_without_the_outlet_reset_attempt_1_cannot_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The negative control for F7: with §7.8 (ii)'s reset disabled, attempt 1 opens with
    `S4 = 0`, so `HX-energy-hot`'s `S4.T` coefficient is zero, the `S4.T` column empty
    (`ref…opening_without_outlet_reset`: rank 33 of 34), and Newton fails its first solve."""
    from openflowsheet.orchestrator import region as region_module

    # §7.8 (ii)'s reset is `_reset_outlet` inside the opening's fixed point (W9.3, Q-S9).
    monkeypatch.setattr(region_module, "_reset_outlet", lambda state, form: False)
    result = solve_from_v2(bind(dz12()), registered_state(DZ12["start"]))
    assert [a.solver_outcome for a in result.attempts] == ["CONVERGED", "LINEAR_SOLVE_FAILED"]
    assert DZ12["attempt1"]["opening_without_outlet_reset"]["rank"] == 33


def test_b27_dz12_under_v1() -> None:
    result, _ = _dz12("v1")
    assert result.outcome != "CONVERGED"
    assert result.outcome == DZ12_V1  # regression value


# ---------------------------------------- B28 (non-lifted half): DZ-11, a zero-flow conflict

DZ11 = CONFLICTS["DZ-11"]
#: Regression value (measured 2026-09-25, W7b): the `T05-W13` outcome from DZ-11's start.
DZ11_V1 = "LINEAR_SOLVE_FAILED"


@cache
def _dz11(contract: str = "v2") -> RegionResult:
    policy = POLICY_V2 if contract == "v2" else POLICY_V1
    return solve_from_v2(bind(dz11()), registered_state(DZ11["start"]), policy)


def test_b28_dz11_closes_specification_conflict() -> None:
    """Spec §7.8 (iv) 2: the form converges in one Newton step (`Q` moves to 1 000 W, `S4.T` to
    303.33 K) but the swapped `U-HX:HX-energy-hot` equals `−Q` at a dormant hot side, so the
    region closes `SPECIFICATION_CONFLICT`, `zero_flow_conflict(U-HX:HX-energy-hot)` — no root, no
    certificate."""
    result = _dz11()
    expected = DZ11["expected"]
    assert result.outcome == expected["outcome"] == "SPECIFICATION_CONFLICT"
    assert result.message.splitlines()[0] == expected["message"]
    assert result.root_fingerprint is None
    assert result.checkpoint is not None and result.checkpoint.label == "partial"
    (attempt,) = result.attempts
    assert [list(e) for e in attempt.signature] == DZ11["signature"]
    assert (attempt.outcome, attempt.solver_outcome) == ("SPECIFICATION_CONFLICT", "CONVERGED")
    (context,) = result.contexts
    registered = DZ11["zero_flow_form"]
    assert sorted(map(registered_name, context.row_scales)) == sorted(registered["rows"])
    assert sorted(context.column_scales) == sorted(registered["columns"])


def test_b28_dz11_its_end_state_and_the_observed_row() -> None:
    result = _dz11()
    for column, value in DZ11["end_state"].items():
        assert error(result.state[column], value) <= _allowance(column), column
    (attempt,) = result.attempts
    row = "U-HX:HX-energy-hot"
    observed = attempt.observations[f"swapped_row:{row}"]
    assert error(observed, DZ11["swapped_row_at_end_W"][row]) <= ALLOWANCE["duty"]
    assert "1000" not in result.message


def test_b28_dz11_the_traversal_refuses_it() -> None:
    solved = _solve(dz11(), POLICY_V2)
    assert solved.run.outcome == "INITIALIZATION_FAILED"
    assert solved.run.message.splitlines()[0] == (
        "initializer_failed(U-HX): specification_unsatisfiable_with_dormant_side"
    )


def test_b28_dz11_under_v1_is_not_converged() -> None:
    result = _dz11("v1")
    assert result.outcome != "CONVERGED"
    assert result.outcome == DZ11_V1  # regression value


def _without_the_swapped_row_test(monkeypatch: pytest.MonkeyPatch) -> RegionResult:
    from openflowsheet.orchestrator import region as region_module

    monkeypatch.setattr(region_module, "_swapped_row_test", lambda *args: None)
    return solve_from_v2(bind(dz11()), registered_state(DZ11["start"]))


def test_b28_without_the_swapped_row_test_dz11_would_close_converged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F6's negative control, non-lifted: without the test the region closes `CONVERGED` on a
    state whose `HX-energy-hot` is 1 000 W off."""
    result = _without_the_swapped_row_test(monkeypatch)
    assert result.outcome == "CONVERGED"
    assert result.state["U-HX.Q"] == 1000.0


# --------------------------------------------------------------------- B29: INJ-B4


def test_b29_inj_b4_the_certificate_catches_the_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    """INJ-B4: DZ-11's end state given to the verifier, with the `CONVERGED` claim a region
    without the swapped-row test makes there: `FAILED`, `false_success_detected`;
    `residual.U-HX:HX-energy-hot` fails at −1 000 W while the label check passes at `0.0` — the
    swapped row stays a checked compiled residual, so the certificate catches the conflict
    independently of the solver's test."""
    claim = _without_the_swapped_row_test(monkeypatch)
    binding = bind(dz11())
    step = planned_step(binding, POLICY_V2)
    end_state = registered_state(DZ11["end_state"])
    certificate = verify_revision(
        binding, dz11(), claim, state=end_state, solve_plan=step.solve_plan
    )
    registered = REF["dormant_non_lifted_injections"]["INJ-B4"]
    assert certificate.verification_status == "FAILED"
    assert certificate.false_success_detected is True
    judged_where(certificate, "final_state", "residual_not_passed")  # K04-F9 X01
    by_id: dict[str, CheckResult] = {c.id: c for c in certificate.checks}
    swapped = by_id["residual.U-HX:HX-energy-hot"]
    assert swapped.result == "fail" and swapped.value is not None
    assert swapped.tolerance is not None
    assert error(swapped.value, registered["residual_U-HX:HX-energy-hot_W"]) <= swapped.tolerance
    assert abs(swapped.value) >= 1e5 * swapped.tolerance
    label = by_id["residual.U-HX:zero-flow-label:hot"]
    assert (label.result, label.value) == ("pass", 0.0)
    failing = [c.id for c in certificate.checks if c.result == "fail"]
    # Spec B29 as ruled (2026-09-25, Q-S4 (3)): the exchanger's balances are per side, and the
    # table's `energy_balance.U-HX` reads `energy_balance.U-HX.hot` (the dormant side's).
    assert set(failing) <= {
        "residual.U-HX:HX-energy-hot",
        "energy_balance.U-HX.hot",
        "energy_balance.envelope",
    }, failing
    assert failing[0] == "residual.U-HX:HX-energy-hot"
    # The retained `HX-energy-cold` holds at DZ-11's end state and the liquid cold stream's fresh
    # flash reads it liquid: a verifier that swapped the sides would fail `.cold` instead.
    assert by_id["energy_balance.U-HX.cold"].result == "pass"
    for check_id, key in (
        ("energy_balance.U-HX.hot", "energy_balance_U-HX_in_minus_out_W"),
        ("energy_balance.envelope", "energy_balance_envelope_in_minus_out_W"),
    ):
        value = by_id[check_id].value
        assert value is not None and error(value, registered[key]) <= ALLOWANCE["duty"], check_id


# ------------------------------------------- B20 (d): form switches recorded, deterministic


def _records(result: RegionResult, trace: Trace) -> dict[str, Any]:
    return {
        "outcome": result.outcome,
        "message": result.message,
        "signatures": [a.signature for a in result.attempts],
        "reasons": [a.reason for a in result.attempts],
        "events": [(event.kind, event.message) for event in trace.events],
        "fingerprint": result.root_fingerprint,
        "provenance": result.branch_provenance,
    }


@pytest.mark.parametrize("case", ["DZ-10", "DZ-12", "DZ-11"])
def test_b20d_solved_twice_gives_identical_records(case: str) -> None:
    """Each case with a supplied start, solved twice in one process: identical outcomes, messages,
    signatures, causes, events, fingerprints and provenance."""
    build = {"DZ-10": dz10, "DZ-12": dz12, "DZ-11": dz11}[case]
    start = registered_state(_registered(case)["start"])
    runs = []
    for _ in range(2):
        trace = Trace()
        runs.append(_records(solve_from_v2(bind(build()), start, trace=trace), trace))
    assert runs[0] == runs[1]


@pytest.mark.parametrize("case", ["DZ-6", "DZ-7", "DZ-8", "DZ-9"])
def test_b20d_the_traversal_cases_twice(case: str) -> None:
    first, second = (_solve(DORMANT_NON_LIFTED_CASES[case](), POLICY_V2) for _ in range(2))
    for solved in (first, second):
        assert solved.certificate is not None
    assert [(e.kind, e.message) for e in first.run.trace.events] == [
        (e.kind, e.message) for e in second.run.trace.events
    ]
    assert first.region.root_fingerprint == second.region.root_fingerprint
    assert first.certificate is not None and second.certificate is not None
    assert first.certificate.as_document() == second.certificate.as_document()


def test_b20d_a_screen_reported_switch_names_the_item() -> None:
    """Spec §7.8 (i), (iii): the screen reports each trial's items from its trigger dormancy, and
    a wall at a toggled item is named `<U>.<port>:<from>-><to>`, the absent side by the outlet's
    declared phase: `phase_wall(…, U-PUMP.outlet:LIQUID->ZERO_FLOW)`."""
    from openflowsheet.orchestrator.phase_contract import _changes
    from openflowsheet.orchestrator.region import _attempt_screen

    binding = bind(dz6())
    flowsheet = binding.flowsheet
    (form,) = _forms(binding)
    root = registered_state(CASES["DZ-6"]["root"])

    def reported(state: dict[str, float]) -> Any:
        screen = _attempt_screen(
            splits=(),
            regimes={},
            provider=flowsheet.provider,
            context=flowsheet.context,
            epsilon=POLICY_V2.admissibility_epsilon,
            ph_units=frozenset(),
            v2=True,
            dormancy=(form,),
        )
        return screen(dict(state))

    assert reported(root) == (("U-PUMP.outlet", "ZERO_FLOW"),)
    assert reported({**root, "S1.n.B": 1.0}) == ()
    declared = {form.item: form.declared}
    item = (("U-PUMP.outlet", "ZERO_FLOW"),)
    assert _changes((), item, declared) == "U-PUMP.outlet:LIQUID->ZERO_FLOW"
    assert _changes(item, (), declared) == "U-PUMP.outlet:ZERO_FLOW->LIQUID"
    lifted = (("U-PHF", "TWO_PHASE"),)
    assert (
        _changes((("U-PHF", "LIQUID"), *item), lifted, declared)
        == "U-PHF:LIQUID->TWO_PHASE, U-PUMP.outlet:ZERO_FLOW->LIQUID"
    )
    # The exchanger names its absent side by that side's declared phase (DZ-12's hot side: VAPOR).
    (hot, _) = _forms(bind(dz12()))
    assert _changes((("U-HX.hot_outlet", "ZERO_FLOW"),), (), {hot.item: hot.declared}) == (
        "U-HX.hot_outlet:ZERO_FLOW->VAPOR"
    )


def test_items_are_one_step_in_the_lattice() -> None:
    """Spec §7.8 (i): an item's absence and presence are one step apart; with the same entries the
    lattice is T03 §4.4's (and §7.3's) unchanged."""
    from openflowsheet.orchestrator.phase_contract import adjacent

    item = ("U-PUMP.outlet", "ZERO_FLOW")
    phf = ("U-PHF", "TWO_PHASE")
    assert adjacent((phf,), (phf, item))
    assert adjacent((phf, item), (phf,))
    assert adjacent((("U-PHF", "LIQUID"), item), (phf,))
    assert not adjacent((("U-PHF", "LIQUID"), item), (("U-PHF", "VAPOR"),))
    assert not adjacent((phf, item), (phf, item))
    # A lifted unit is never absent: an entry in one signature only that is not `ZERO_FLOW`.
    assert not adjacent((phf,), (phf, ("U-VLV", "LIQUID")))
    # The entries both carry must come in the same order.
    other = ("U-VLV", "LIQUID")
    assert not adjacent((phf, other), (other, phf, item))


# ------------------------------------------------------- B30 (a): inert on registered cases


def _registered_runs() -> dict[str, list[Any]]:
    """Every attempt signature (and every provenance item's) of C1, C2, C3, C3X, SC-1…SC-4,
    NP-1…NP-3, NP-G and DZ-1…DZ-5 under `T05b-v2`."""
    documents: dict[str, dict[str, Any]] = {
        case: case_document(case)
        for case in ("SYN-001-UL-C1", "SYN-001-UL-C2", "SYN-001-UL-C3", "SYN-001-UL-C3X")
    }
    documents.update({case: build() for case, build in SINGLE_COMPONENT_CASES.items()})
    documents.update({case: near_pure(case) for case in NEAR_PURE_CASES})
    documents.update(
        {case: build() for case, build in DORMANT_CASES.items() if case not in ("DZ-3", "DZ-2C")}
    )
    found: dict[str, list[Any]] = {}
    for case, document in documents.items():
        run = _solve(document, POLICY_V2).run
        found[case] = [
            [tuple(entry) for entry in item["signature"]]
            for step in run.steps
            if isinstance(step.detail, RegionResult)
            for item in step.detail.branch_provenance
        ] + [
            attempt.signature
            for step in run.steps
            if isinstance(step.detail, RegionResult)
            for attempt in step.detail.attempts
        ]
    dz3_result = solve_from_v2(bind(dz3()), registered_state(REF["dormant_cases"]["DZ-3"]["start"]))
    found["DZ-3"] = [attempt.signature for attempt in dz3_result.attempts]
    return found


def test_b30a_no_registered_case_carries_an_item() -> None:
    for case, signatures in _registered_runs().items():
        for signature in signatures:
            assert not any("." in unit for unit, _ in signature), (case, signature)
