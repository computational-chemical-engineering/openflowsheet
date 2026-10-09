"""T05b W7: the `ZERO_FLOW` regime of a lifted split (spec §6.1, §7.1–§7.5; ADR 0012 D4 (c)).

- §6.1: the split registry's ids for the zero-flow form — split rows, a PH-type split's energy
  row and label source — read off each model's rule (`splits.zero_flow_forms`) and checked against
  the declaration by `check_agreement`, with a negative control per check.
- §7.3: the lattice (`ZERO_FLOW` adjacent to each regime); the screen's dormancy agreement and the
  kernel on entering and leaving `ZERO_FLOW` (§7.4), with their records (§6.5).
- B15 (v2 half; the v1 half is `test_t05_dormant_outlet.py`) and B17: DZ-1, DZ-2, DZ-4, DZ-5 run
  `plan_revision` → `execute_plan` → `verify_revision` under `T05b-v2` and converge at iteration 0
  in their zero-flow form.
- B16: DZ-3, the moving label, a region solve from `ref.dormant_cases.DZ-3.start`.
- B18 INJ-B3: DZ-1's root with a stale label, judged against DZ-1's v2 claim.
- B28's lifted half: DZ-2C, a dormant PH flash asked for 1 000 W — `SPECIFICATION_CONFLICT`,
  `zero_flow_conflict(U-PHF:PHF-duty)`, never a false `CONVERGED` (spec §7.8 (iv) 2, finding F6).

Values marked *regression* are self-generated: pinned beside their assertion, reported to the
design lane if they move, never re-pinned.

Expected sets are `ref.dormant_cases.<case>.zero_flow_form` (`ref` =
`benchmarks/t05b/reference_values.yaml`, the design lane's twin). `revision` names its feed
`U-FEED-0`; the registry names it `U-FEED`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import cache
from typing import Any

import pytest
from t05_w12_support import bind, planned_step
from t05b_support import (
    POLICY_V2,
    REF,
    dz1,
    dz2,
    dz2c,
    dz3,
    dz4,
    dz5,
    error,
    fresh_flash_ratios,
    judged_where,
    registered_state,
    revision_projection,
    solve_from_v2,
)
from test_t05_coupled import POLICY as POLICY_V1

from openflowsheet.application.revision_binding import RevisionBinding
from openflowsheet.graph.trace import Declaration, trace_declaration
from openflowsheet.models.syn001 import TEMPERATURE_TOLERANCE
from openflowsheet.orchestrator import splits as splits_module
from openflowsheet.orchestrator.execution import ExecutionPlan, declaration_identity
from openflowsheet.orchestrator.executor import PlanResult, execute_plan
from openflowsheet.orchestrator.region import (
    RegionResult,
    ZeroFlowForm,
    _attempt_screen,
    _contract_kernel,
)
from openflowsheet.orchestrator.revision import instances_of, plan_revision
from openflowsheet.orchestrator.splits import (
    SPLIT_RULES,
    check_agreement,
    closure_types,
    lifted_splits,
    zero_flow_forms,
)
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.verify import CheckResult
from openflowsheet.verify.certificate import SolutionCertificate, verify_revision

DORMANT: dict[str, Any] = REF["dormant_cases"]
CONFLICTS: dict[str, Any] = REF["zero_flow_conflicts"]
REGISTERED_FORMS = {"DZ-1": dz1, "DZ-2": dz2, "DZ-4": dz4, "DZ-5": dz5}
#: B15 and B17: each case's unit, its dormant outlet streams, and whether it has a label row.
AT_THE_START = {
    "DZ-1": ("U-VLV", ("S2",), True),
    "DZ-2": ("U-PHF", ("S2", "S3"), True),
    "DZ-4": ("U-RX", ("S2",), True),
    "DZ-5": ("U-HEAT", ("S2",), False),
}
#: Spec §13's EO allowances (T02 §6.4), as `ref.tolerances.coupled_allowances` states them.
ALLOWANCE: dict[str, float] = {
    kind: float(value) for kind, value in REF["tolerances"]["coupled_allowances"].items()
}
#: Regression values (measured 2026-09-25, W7): the `T05-W13` outcomes from DZ-3's and DZ-2C's
#: registered starts. In both the declared form's first Jacobian is singular (the dormant split's
#: three equilibrium rows vanish identically, spec §7.5), so v1 cannot take a step.
V1_FROM_THE_START = {"DZ-3": "LINEAR_SOLVE_FAILED", "DZ-2C": "LINEAR_SOLVE_FAILED"}


def _renamed(name: str) -> str:
    return name.replace("U-FEED-0:", "U-FEED:", 1)


def _declaration(binding: RevisionBinding) -> Declaration:
    model_version, constants = declaration_identity(binding.spec)
    return trace_declaration(
        binding.spec,
        row_units=binding.row_units,
        model_version=model_version,
        constants_sha256=constants,
    )


def _forms(binding: RevisionBinding) -> dict[str, ZeroFlowForm]:
    flowsheet = binding.flowsheet
    instances = instances_of(flowsheet)
    splits = lifted_splits(instances, flowsheet.components)
    return zero_flow_forms(
        instances, splits, closure_types(flowsheet.units()), flowsheet.components
    )


# ------------------------------------------------------------------------ §6.1: the registry


def test_the_registry_names_each_models_zero_flow_ids() -> None:
    """Spec §6.1, §7.2: split rows `split:<c>` (heater style) or `<EQ>-mole:<c>` (products
    style); an energy row for exactly the models that can be PH-type (the reactor by its
    configuration)."""
    # M02 design note §14.2 B13: restricted to the `syn001.` keys, the literal unchanged; the full
    # key set and the `c1.` entries are pinned by `test_m02_wo8_registries`.
    assert {
        model: (rule.closure, rule.split_rows, rule.energy)
        for model, rule in SPLIT_RULES.items()
        if model.startswith("syn001.")
    } == {
        "syn001.tp_heater": ("TP", "split", None),
        "syn001.tp_flash": ("TP", "FLASH-mole", None),
        "syn001.valve": ("PH", "split", "VLV-energy"),
        "syn001.conversion_reactor": (None, "split", "RX-duty"),
        "syn001.ph_flash": ("PH", "PHF-mole", "PHF-duty"),
    }


@pytest.mark.parametrize("case", REGISTERED_FORMS)
def test_the_forms_reduce_the_declaration_to_the_registered_form(case: str) -> None:
    """The declaration's rows minus the form's, plus its label row, and its columns minus the
    form's, are exactly `ref.dormant_cases.<case>.zero_flow_form`; the label is `ref`'s."""
    binding = bind(REGISTERED_FORMS[case]())
    (form,) = _forms(binding).values()
    registered = DORMANT[case]["zero_flow_form"]
    label = DORMANT[case]["label"]
    rows = [row for row in binding.spec.equation_ids if row not in form.rows]
    if form.label is not None:
        rows.append(form.label[0])
    assert sorted(map(_renamed, rows)) == sorted(registered["rows"])
    columns = [c for c in binding.spec.variable_ids if c not in form.columns]
    assert sorted(columns) == sorted(registered["columns"])
    assert len(rows) == len(columns) == registered["dimension"]
    if label is None:
        assert (form.label, form.swapped) == (None, "")
    else:
        assert form.label == (label["row"], label["T_out"], label["T_label"])
        assert form.swapped == form.rows[-1]
        assert form.swapped not in {_renamed(row) for row in rows}


def test_a_reactor_is_ph_type_by_its_duty_pin() -> None:
    """DZ-4's reactor has its duty pinned (`energy_specification = duty`): its form swaps
    `RX-duty`; the same reactor with its outlet temperature pinned (C2's) swaps nothing."""
    (form,) = _forms(bind(dz4())).values()
    assert form.swapped == "U-RX:RX-duty"
    from test_t05_w11_cases import case_document

    c2 = _forms(bind(case_document("SYN-001-UL-C2")))
    assert (c2["U-RX"].swapped, c2["U-RX"].label) == ("", None)


# ---------------------------------------------------- §6.1: `check_agreement` on the forms


def _agreement(binding: RevisionBinding, forms: dict[str, ZeroFlowForm]) -> None:
    flowsheet = binding.flowsheet
    instances = instances_of(flowsheet)
    check_agreement(
        instances,
        lifted_splits(instances, flowsheet.components),
        binding.spec,
        binding.row_units,
        _declaration(binding),
        forms,
    )


@pytest.mark.parametrize("case", REGISTERED_FORMS)
def test_the_registered_forms_agree_with_the_rows(case: str) -> None:
    binding = bind(REGISTERED_FORMS[case]())
    _agreement(binding, _forms(binding))


@pytest.mark.parametrize(
    ("corrupt", "message"),
    [
        (
            # A swapped row the unit authored that does not read the split's temperature.
            lambda f: replace(f, swapped="U-VLV:VLV-P", rows=(*f.rows[:-1], "U-VLV:VLV-P")),
            r"^zero_flow_form_disagrees\(U-VLV, U-VLV:VLV-P\): does not read S2\.T$",
        ),
        (
            lambda f: replace(f, label=(f.label[0], f.label[1], "S9.T")),
            r"^zero_flow_form_disagrees\(U-VLV\): the label reads S2\.T and S9\.T$",
        ),
        (
            lambda f: replace(f, rows=(*f.rows, "U-FEED-0:FEED-T")),
            r"^zero_flow_form_disagrees\(U-VLV\): not rows the unit authored: "
            r"\['U-FEED-0:FEED-T'\]$",
        ),
        (
            lambda f: replace(f, rows=(*f.rows, "U-VLV:no-such-row")),
            r"^zero_flow_form_disagrees\(U-VLV\): not rows the unit authored",
        ),
    ],
    ids=["swapped-not-reading-T", "label-not-a-column", "foreign-row", "absent-row"],
)
def test_agreement_refuses_a_form_that_disagrees(corrupt: Any, message: str) -> None:
    binding = bind(dz1())
    forms = _forms(binding)
    with pytest.raises(ValueError, match=message):
        _agreement(binding, {"U-VLV": corrupt(forms["U-VLV"])})
    with pytest.raises(ValueError, match=r"^zero_flow_form_disagrees\(U-VLV\): no form$"):
        _agreement(binding, {})


def test_syn001s_own_splits_have_forms_that_agree() -> None:
    """SYN-001's flowsheet (the executor's `_zero_flow_forms`, from SYN-001's wiring): both of its
    splits are TP-type — `U-HEAT` drops `split:<c>`, `U-FLASH` its `FLASH-mole:<c>` — and (f)
    holds on its declaration."""
    from openflowsheet.application.binding import structural_inputs
    from openflowsheet.compiled import EvaluationContext
    from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
    from openflowsheet.orchestrator.executor import _zero_flow_forms
    from openflowsheet.thermo.syn001 import Syn001Provider

    flowsheet = Syn001Flowsheet(
        provider=Syn001Provider(),
        context=EvaluationContext(
            model_version="t05b-w7", constants_sha256="0" * 64, phase_signature=None
        ),
    )
    forms = _zero_flow_forms(flowsheet)
    assert {unit: (form.swapped, form.label) for unit, form in forms.items()} == {
        "U-HEAT": ("", None),
        "U-FLASH": ("", None),
    }
    assert forms["U-HEAT"].rows[3:6] == ("U-HEAT:split:A", "U-HEAT:split:B", "U-HEAT:split:C")
    assert forms["U-FLASH"].rows[3:6] == tuple(f"U-FLASH:FLASH-mole:{c}" for c in "ABC")
    spec, _, row_units = structural_inputs(flowsheet)
    model_version, constants = declaration_identity(spec)
    declaration = trace_declaration(
        spec, model_version=model_version, constants_sha256=constants, row_units=row_units
    )
    from openflowsheet.models.syn001.flowsheet import WIRING
    from openflowsheet.orchestrator.region import syn001_lifted_splits

    instances = [(u.unit_id, u.model_id, WIRING[u.unit_id]) for u in flowsheet.units()]
    check_agreement(
        instances,
        syn001_lifted_splits(flowsheet.components),
        spec,
        row_units,
        declaration,
        forms,
    )


def test_plan_revision_checks_the_forms(monkeypatch: pytest.MonkeyPatch) -> None:
    """`plan_revision` runs (f) under every literal: a rule naming the wrong energy row is a
    defect, raised before anything is solved."""
    rule = SPLIT_RULES["syn001.valve"]
    monkeypatch.setitem(
        splits_module.SPLIT_RULES,  # type: ignore[arg-type]
        "syn001.valve",
        replace(rule, energy="VLV-P"),
    )
    with pytest.raises(ValueError, match=r"^zero_flow_form_disagrees\(U-VLV, U-VLV:VLV-P\)"):
        plan_revision(bind(dz1()), POLICY_V2)


# ----------------------------------------------------------------------- §7.3: the lattice


def test_zero_flow_is_adjacent_to_each_regime() -> None:
    """Spec §7.3: `LIQUID — TWO_PHASE — VAPOR` with `ZERO_FLOW` adjacent to each of the three;
    ADR 0005 D2's adjacency of signatures unchanged otherwise (`LIQUID`, `VAPOR` two apart)."""
    from openflowsheet.orchestrator.phase_contract import adjacent

    for regime in ("LIQUID", "TWO_PHASE", "VAPOR"):
        assert adjacent((("U", "ZERO_FLOW"),), (("U", regime),))
        assert adjacent((("U", regime),), (("U", "ZERO_FLOW"),))
    assert not adjacent((("U", "ZERO_FLOW"),), (("U", "ZERO_FLOW"),))
    assert not adjacent((("U", "LIQUID"),), (("U", "VAPOR"),))
    assert adjacent((("U", "ZERO_FLOW"), ("W", "LIQUID")), (("U", "VAPOR"), ("W", "TWO_PHASE")))
    assert not adjacent((("U", "ZERO_FLOW"), ("W", "LIQUID")), (("U", "VAPOR"), ("W", "VAPOR")))


# ------------------------------------------- §7.3–§7.4: the screen and the kernel, entering/leaving


def _split(binding: RevisionBinding) -> Any:
    flowsheet = binding.flowsheet
    (split,) = lifted_splits(instances_of(flowsheet), flowsheet.components)
    return split


def _flowing(state: dict[str, float], stream: str) -> dict[str, float]:
    """DZ-1's root with 2 mol/s of B in the valve's outlet (a feed that flows, an empty split)."""
    changed = dict(state)
    changed[f"{stream}.n.B"] = 2.0
    return changed


@pytest.mark.parametrize(
    ("case", "ph_type"), [("DZ-1", True), ("DZ-5", False)], ids=["valve", "heater"]
)
def test_the_screen_reports_dormancy_agreement(case: str, ph_type: bool) -> None:
    """Spec §7.3's screen, under v2, for both closure types: a trial whose feed is exactly dormant
    reports `ZERO_FLOW` whatever the frozen regime; a `ZERO_FLOW` split whose feed flows reports
    the TP flash's regime (it is leaving, §7.4). Under v1 the dormancy is not looked at."""
    binding = bind(REGISTERED_FORMS[case]())
    flowsheet, split = binding.flowsheet, _split(binding)
    root = registered_state(DORMANT[case]["root"])
    units = frozenset({split.unit}) if ph_type else frozenset()

    def reported(regime: str, state: dict[str, float], v2: bool = True) -> Any:
        screen = _attempt_screen(
            splits=(split,),
            regimes={split.unit: regime},  # type: ignore[dict-item]
            provider=flowsheet.provider,
            context=flowsheet.context,
            epsilon=POLICY_V2.admissibility_epsilon,
            ph_units=units if v2 else frozenset(),
            v2=v2,
        )
        return screen(dict(state))

    for regime in ("LIQUID", "TWO_PHASE", "VAPOR", "ZERO_FLOW"):
        assert reported(regime, root) == ((split.unit, "ZERO_FLOW"),)
    # 2 mol/s of B at 330 K and below 1 bar: the TP flash says LIQUID.
    assert reported("ZERO_FLOW", _flowing(root, split.stream)) == ((split.unit, "LIQUID"),)
    # v1: a dormant LIQUID split is admissible (nothing on its liquid side to boil) and stays so.
    assert reported("LIQUID", root, v2=False) == ((split.unit, "LIQUID"),)


@pytest.mark.parametrize(
    ("case", "ph_type"), [("DZ-1", True), ("DZ-5", False)], ids=["valve", "heater"]
)
def test_the_kernel_entering_and_leaving_zero_flow(case: str, ph_type: bool) -> None:
    """Spec §6.2 step 1, §7.1, §7.4, §6.5: under v2 a dormant feed's kernel is `ZERO_FLOW` with
    every lifted flow `+0.0` and no record; a `ZERO_FLOW` split whose feed flows takes the TP
    flash's regime and split, recorded `tp` for a PH-type split (its pinned split carries no
    enthalpy) and nothing for a TP-type one. Under v1 the TP flash answers a dormant feed."""
    binding = bind(REGISTERED_FORMS[case]())
    flowsheet, split = binding.flowsheet, _split(binding)
    root = registered_state(DORMANT[case]["root"])
    units = frozenset({split.unit}) if ph_type else frozenset()
    entering = _contract_kernel(
        flowsheet.provider, flowsheet.context, split, root, units, v2=True, regime="LIQUID"
    )
    lifted = (*split.vapor, *split.liquid, split.vapor_total, split.liquid_total)
    assert (entering.regime, entering.fallback) == ("ZERO_FLOW", "")
    assert entering.values == dict.fromkeys(lifted, 0.0)
    flowing = _flowing(root, split.stream)
    leaving = _contract_kernel(
        flowsheet.provider, flowsheet.context, split, flowing, units, v2=True, regime="ZERO_FLOW"
    )
    assert (leaving.regime, leaving.fallback) == ("LIQUID", "tp" if ph_type else "")
    assert leaving.values[f"{split.stream}.liq.B"] == 2.0
    assert leaving.values[split.liquid_total] == 2.0
    assert split.temperature not in leaving.values
    v1 = _contract_kernel(flowsheet.provider, flowsheet.context, split, root, frozenset())
    assert (v1.regime, v1.fallback) == ("TWO_PHASE", "")


# ------------------------------------------------ B15 (v2 half), B17: at the traversal start


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
def _solved(case: str) -> Solved:
    return _solve(REGISTERED_FORMS[case](), POLICY_V2)


@pytest.mark.parametrize("case", AT_THE_START)
def test_b15_b17_converged_at_iteration_zero_in_the_zero_flow_form(case: str) -> None:
    unit, _, _ = AT_THE_START[case]
    run = _solved(case).run
    assert run.outcome == "CONVERGED", run.message
    assert run.counters.jacobian_calls == 0
    region = _solved(case).region
    assert [a.iterations for a in region.attempts] == [0]
    assert [[list(item) for item in a.signature] for a in region.attempts] == [
        [[unit, "ZERO_FLOW"]]
    ]
    assert region.root_fingerprint is not None
    assert region.root_fingerprint["branch_found"] == [[unit, "ZERO_FLOW"]]


@pytest.mark.parametrize("case", AT_THE_START)
def test_b15_b17_the_attempt_is_the_registered_zero_flow_form(case: str) -> None:
    """The attempt's rows (compiled, then its label row) and free columns are exactly
    `ref.dormant_cases.<case>.zero_flow_form`'s; its `jacobian_pattern` counts them, the label's
    two exact entries included; the swapped energy row is not among them."""
    registered = DORMANT[case]["zero_flow_form"]
    (context,) = _solved(case).region.contexts
    rows, columns = list(context.row_scales), list(context.column_scales)
    assert sorted(map(_renamed, rows)) == sorted(registered["rows"])
    assert sorted(columns) == sorted(registered["columns"])
    assert context.jacobian_pattern is not None
    assert context.jacobian_pattern["rows"] == context.jacobian_pattern["columns"]
    assert context.jacobian_pattern["rows"] == registered["dimension"]
    label = DORMANT[case]["label"]
    if label is not None:
        assert rows[-1] == label["row"]
        assert context.row_scales[label["row"]] == 100.0  # K03 §4.2's temperature nominal


@pytest.mark.parametrize("case", AT_THE_START)
def test_b15_b17_the_root_is_exact(case: str) -> None:
    """Every registered column of the root `==` (the traversal's labels, Newton at iteration 0):
    every flow `0.0`, every dormant outlet at its label, every duty `0.0`."""
    state = _solved(case).run.state
    assert state is not None
    root = registered_state(DORMANT[case]["root"])
    assert {column: state[column] for column in root} == root
    flows = [
        value
        for column, value in state.items()
        if column.split(".")[1] in ("n", "vap", "liq", "V", "L", "N")
    ]
    assert flows and all(value == 0.0 for value in flows)


@pytest.mark.parametrize("case", AT_THE_START)
def test_b15_b17_verified_on_the_zero_flow_form(case: str) -> None:
    """Spec §9.3: `VERIFIED`, `NO_RANK_LOSS_DETECTED` at the registered dimension;
    `residual.<U>:zero-flow-label` present and `0.0` for a PH-type split and absent for DZ-5's
    TP-type heater; every compiled residual `0.0`."""
    unit, _, has_label = AT_THE_START[case]
    certificate = _solved(case).certificate
    assert certificate is not None
    assert certificate.verification_status == "VERIFIED", certificate.limitations
    assert certificate.regularity is not None
    assert certificate.regularity.status == "NO_RANK_LOSS_DETECTED"
    assert certificate.regularity.dimension == DORMANT[case]["zero_flow_form"]["dimension"]
    residuals = {c.id: c for c in certificate.checks if c.category == "residual"}
    label = residuals.pop(f"residual.{unit}:zero-flow-label", None)
    if has_label:
        assert label is not None and (label.value, label.result) == (0.0, "pass")
    else:
        assert label is None
    assert residuals and all(c.value == 0.0 for c in residuals.values()), residuals


# ----------------------------------------------------------------- B16: DZ-3, a moving label


@cache
def _dz3(contract: str = "v2") -> tuple[RevisionBinding, RegionResult]:
    binding = bind(dz3())
    start = registered_state(DORMANT["DZ-3"]["start"])
    return binding, solve_from_v2(binding, start, POLICY_V2 if contract == "v2" else POLICY_V1)


def test_b16_dz3_the_label_moves() -> None:
    """From the registered perturbed start (`S2.T … S6.T` each +1 K): `CONVERGED`, `U-VLV` in
    `ZERO_FLOW` in every attempt, `S5.T` back on `S4.T` to `1e-9 K`, `S4.T` on PHF-1's `T` to
    `1e-5 K`, and the recycle `S4` still exactly `+0.0` (spec §18 Q8)."""
    _, result = _dz3()
    assert result.outcome == "CONVERGED", result.message
    for attempt in result.attempts:
        assert dict(attempt.signature)["U-VLV"] == "ZERO_FLOW"
    state = result.state
    assert abs(state["S5.T"] - state["S4.T"]) <= 1e-9
    assert error(state["S4.T"], DORMANT["DZ-3"]["root"]["S4.T"]) <= ALLOWANCE["T"]
    assert all(state[f"S4.n.{c}"] == 0.0 for c in "ABC")
    assert all(state[f"S5.{kind}.{c}"] == 0.0 for kind in ("n", "vap", "liq") for c in "ABC")
    (context, *_) = result.contexts
    registered = DORMANT["DZ-3"]["zero_flow_form"]
    assert sorted(map(_renamed, context.row_scales)) == sorted(registered["rows"])
    assert sorted(context.column_scales) == sorted(registered["columns"])


def _dz3_certificate() -> SolutionCertificate:
    binding, result = _dz3()
    step = planned_step(binding, POLICY_V2)
    return verify_revision(
        binding, dz3(), result, state=dict(result.state), solve_plan=step.solve_plan
    )


#: K04-F9 X07 (regression, measured 2026-09-25, F9 W5): Newton's stop leaves the PH flash's
#: equilibrium rows at 0.173, 0.197, 0.119 `τ_eq` — inside D2.4's band, flagged, not failing.
DZ3_EQUILIBRIUM_FLAGS = {"A": 0.173, "B": 0.197, "C": 0.119}
#: K04-F9 X07: the zero-flow form's dimension and `rcond₁` (regression, T05b W7).
DZ3_SCREEN = (33, 0.013055)


def test_b16_dz3_verified() -> None:
    """K04-F9 X07 (B16 amended; ADR 0013 D1): `VERIFIED`, its fresh-flash categories judged at
    the verifier's projection — every value there ≤ 1e-3 of its tolerance; the label row, every
    residual and the screen pass; the only flags are the equilibrium rows Newton stopped at."""
    certificate = _dz3_certificate()
    assert certificate.verification_status == "VERIFIED", [
        (c.id, c.value) for c in certificate.checks if c.result == "fail"
    ]
    judged_where(certificate, "projection")
    ratios = fresh_flash_ratios(certificate.checks)
    assert ratios and max(ratios.values()) <= 1e-3, max(ratios.items(), key=lambda i: i[1])
    by_id = {c.id: c for c in certificate.checks}
    assert by_id["residual.U-VLV:zero-flow-label"].result == "pass"
    assert all(c.result == "pass" for c in certificate.checks if c.category == "residual")
    assert certificate.regularity is not None
    assert certificate.regularity.status == "NO_RANK_LOSS_DETECTED"
    assert certificate.regularity.dimension == DZ3_SCREEN[0]
    assert certificate.regularity.rcond_1 == pytest.approx(DZ3_SCREEN[1], abs=5e-7)
    flagged = {c.id for c in certificate.checks if c.near_threshold}
    assert flagged == {f"residual.U-PHF:PHF-equilibrium:{c}" for c in "ABC"}
    for component, ratio in DZ3_EQUILIBRIUM_FLAGS.items():
        check = by_id[f"residual.U-PHF:PHF-equilibrium:{component}"]
        assert check.value is not None and check.tolerance is not None
        assert abs(check.value) / check.tolerance == pytest.approx(ratio, abs=5e-4)


def test_b16_dz3_what_the_fresh_flash_reads_at_newtons_stop() -> None:
    """The measured failure behind B16's former xfail (2026-09-25, W7), kept as evidence through
    the table evaluated at `x_final` itself (unprojected; *regression*). Newton closes attempt 0
    after 2 iterations (the largest row `U-PHF:PHF-equilibrium:B` at 1.8e-8 (mol/s)², 0.2
    `τ_eq`) at `S2.T` 8.1e-7 K above PHF-1's — inside spec §13's 1e-5 K allowance. The fresh
    flash of the PH flash's feed at that state misses the stored split by 9.1e-8 mol/s (2.9
    `τ_flow`) and, through the liquid product 2.1e-8 past its bubble point, the energy balance by
    −1.33e-3 W (1.3 `τ_E`): T04 F9's mechanism, which ADR 0013 D1's projection removes.

    **Re-registered by T06 A92** (W19): with T06 spec §8.8's saturation closure the list gains
    `phase_admissibility.U-PHF.S1.closure` at 1.0055e-6 K (1.01 `τ_T`) — the same liquid past its
    bubble point, which the projection resolves as it resolves the energy and split checks (the
    certificate stays `VERIFIED`, `test_b16_dz3_verified`)."""
    binding, result = _dz3()
    _, unprojected = revision_projection(binding, dz3(), dict(result.state))
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


def test_b16_dz3_under_v1_is_not_converged() -> None:
    """The declared form at the start is singular (41 × 41 of rank 38): v1 takes no step."""
    _, result = _dz3("v1")
    assert result.outcome != "CONVERGED"
    assert result.outcome == V1_FROM_THE_START["DZ-3"]  # regression value


# -------------------------------------------------------------- B18 INJ-B3: a stale label


def test_b18_inj_b3_a_stale_label_fails_the_label_row() -> None:
    """DZ-1's v2 solve claims `CONVERGED`; its root with `S2.T = 331 K` fails exactly its label
    row, by `ref.injections.INJ-B3.label_residual_K` (`10⁶ τ_T`)."""
    solved = _solved("DZ-1")
    state = dict(registered_state(DORMANT["DZ-1"]["root"]))
    state["S2.T"] = 331.0
    solve_plan = solved.plan.steps[-1].solve_plan
    certificate = verify_revision(
        solved.binding, solved.document, solved.run, state=state, solve_plan=solve_plan
    )
    assert certificate.verification_status == "FAILED"
    judged_where(certificate, "final_state", "residual_not_passed")  # K04-F9 X01
    by_id: dict[str, CheckResult] = {c.id: c for c in certificate.checks}
    label = by_id["residual.U-VLV:zero-flow-label"]
    assert label.result == "fail" and label.value is not None and label.tolerance is not None
    assert error(label.value, REF["injections"]["INJ-B3"]["label_residual_K"]) <= label.tolerance
    assert abs(label.value) >= 1e3 * TEMPERATURE_TOLERANCE


# ------------------------------------------ B28 (lifted half): DZ-2C, a zero-flow conflict


@cache
def _dz2c(contract: str = "v2") -> RegionResult:
    binding = bind(dz2c())
    start = registered_state(CONFLICTS["DZ-2C"]["start"])
    return solve_from_v2(binding, start, POLICY_V2 if contract == "v2" else POLICY_V1)


def test_b28_dz2c_closes_specification_conflict() -> None:
    """Spec §7.8 (iv) 2 (finding F6): the zero-flow form converges in one Newton step (`Q` moves
    to its 1 000 W specification), but the swapped `U-PHF:PHF-duty` equals `Q` at dormancy, so the
    region closes `SPECIFICATION_CONFLICT`, `zero_flow_conflict(U-PHF:PHF-duty)` — never a false
    `CONVERGED` on a state that violates a declared row by 1 000 W (`9.9e5 τ_E`)."""
    result = _dz2c()
    expected = CONFLICTS["DZ-2C"]["expected"]
    assert result.outcome == expected["outcome"] == "SPECIFICATION_CONFLICT"
    assert result.message.splitlines()[0] == expected["message"]
    # No root: no fingerprint, and the checkpoint is not a candidate root.
    assert result.root_fingerprint is None
    assert result.checkpoint is not None and result.checkpoint.label == "partial"
    (attempt,) = result.attempts
    assert [list(item) for item in attempt.signature] == CONFLICTS["DZ-2C"]["signature"]
    assert (attempt.outcome, attempt.solver_outcome) == ("SPECIFICATION_CONFLICT", "CONVERGED")
    (context,) = result.contexts
    registered = CONFLICTS["DZ-2C"]["zero_flow_form"]
    assert sorted(map(_renamed, context.row_scales)) == sorted(registered["rows"])
    assert sorted(context.column_scales) == sorted(registered["columns"])


def test_b28_dz2c_its_end_state_and_the_observed_row() -> None:
    """The end state against `ref.zero_flow_conflicts.DZ-2C.end_state` at spec §13's allowances,
    and the swapped row's value, `+1 000 W`, within `1e-2 W` in the attempt's non-R0
    observations (never in the message)."""
    result = _dz2c()
    for column, value in CONFLICTS["DZ-2C"]["end_state"].items():
        kind = column.rsplit(".", 1)[-1]
        allowance = {"T": ALLOWANCE["T"], "P": ALLOWANCE["P"], "Q": ALLOWANCE["duty"]}.get(
            kind, ALLOWANCE["flow"]
        )
        assert error(result.state[column], value) <= allowance, (column, result.state[column])
    (attempt,) = result.attempts
    row = "U-PHF:PHF-duty"
    observed = attempt.observations[f"swapped_row:{row}"]
    assert error(observed, CONFLICTS["DZ-2C"]["swapped_row_at_end_W"][row]) <= ALLOWANCE["duty"]
    assert "1000" not in result.message


def test_b28_dz2c_the_traversal_refuses_it() -> None:
    """Why DZ-2C starts from a supplied state: the causal PH flash refuses a duty into a dormant
    stream, so the plan's own start ends `INITIALIZATION_FAILED`."""
    solved = _solve(dz2c(), POLICY_V2)
    assert solved.run.outcome == "INITIALIZATION_FAILED"
    assert solved.run.message.splitlines()[0] == (
        "initializer_failed(U-PHF): duty_into_dormant_stream"
    )


def test_b28_dz2c_under_v1_is_not_converged() -> None:
    result = _dz2c("v1")
    assert result.outcome != "CONVERGED"
    assert result.outcome == V1_FROM_THE_START["DZ-2C"]  # regression value


def test_b28_without_the_swapped_row_test_dz2c_would_close_converged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The negative control for F6: with the swapped-row test disabled the same solve closes
    `CONVERGED` at a state whose `PHF-duty` row is 1 000 W off — the false success §7.8 (iv) 2
    exists to close."""
    from openflowsheet.orchestrator import region as region_module

    monkeypatch.setattr(region_module, "_swapped_row_test", lambda *args: None)
    binding = bind(dz2c())
    start = registered_state(CONFLICTS["DZ-2C"]["start"])
    result = solve_from_v2(binding, start)
    assert result.outcome == "CONVERGED"
    assert result.state["U-PHF.Q"] == 1000.0
