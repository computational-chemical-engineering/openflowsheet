"""S11 WO-B4: the column's verifier checks (design note §4.8, §10.11; assertions S11.A35–A38).

Each committed column flowsheet case (`benchmarks/s11/flowsheets/*.json`) is solved once, then
certified by `verify_revision` with the column registered for the test (I1 registers it, and its
`MODEL_CHECKS` entry, for good): the staged splits reach the certificate's `lifted_splits` call,
the stage keys resolve to their column through the owner map, and `verify.column` adds the
column's balance, specification and stage rows. The mutations inject a state (`state=`, K04 §9).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import replace
from functools import cache
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from s11_column_support import (
    COLUMN_CASES,
    RECYCLE_CASE,
    WILSON_CASES,
    WILSON_STRIPPER,
    column_case_spec,
    column_registered,
    committed_case,
)

from openflowsheet.application.policies import T06_REVISION_V2
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compile.reference import state_vector
from openflowsheet.models import flow_id
from openflowsheet.models.revision_flowsheet import parse_revision
from openflowsheet.models.syn001.cascade import stage_duty_id, stage_temperature_id
from openflowsheet.models.syn001.cascade_solve import S01_DEFAULT_V1
from openflowsheet.models.syn001.column import ColumnSpec
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import execute_plan
from openflowsheet.orchestrator.revision import plan_revision
from openflowsheet.orchestrator.splits import STAGED_MODELS, lifted_splits, split_owners
from openflowsheet.verify import CheckResult
from openflowsheet.verify.certificate import (
    BoundDeclaration,
    CheckPolicy,
    SolutionCertificate,
    _staged_splits,
    fresh_provider,
    verify_revision,
)
from openflowsheet.verify.checks import DERIVATIVE_TOLERANCE, derivative_witness, one_sided_columns
from openflowsheet.verify.zero_flow import zero_flow_splits

BASES = frozenset({"syn001", "wilson-ig-v2"})


@pytest.fixture
def registered(monkeypatch: pytest.MonkeyPatch) -> Iterator[pytest.MonkeyPatch]:
    with column_registered(monkeypatch, BASES):
        yield monkeypatch


@cache
def solved(name: str) -> tuple[RevisionBinding, dict[str, Any], Any, Any]:
    """The case bound, planned and executed once per session (A29's run)."""
    policy = T06_REVISION_V2 if name == RECYCLE_CASE else S01_DEFAULT_V1
    document = committed_case(name)
    with pytest.MonkeyPatch.context() as patch, column_registered(patch, BASES):
        binding = bind_revision_flowsheet(document)
        assert isinstance(binding, RevisionBinding), binding
        plan, _ = plan_revision(binding, policy)
        assert isinstance(plan, ExecutionPlan), plan
        run = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=policy)
    assert run.outcome == "CONVERGED", run.message
    return binding, document, run, plan.steps[-1].solve_plan


def certify(name: str, state: Mapping[str, float] | None = None) -> SolutionCertificate:
    binding, document, run, solve_plan = solved(name)
    return verify_revision(binding, document, run, solve_plan=solve_plan, state=state)


def by_id(certificate: SolutionCertificate) -> dict[str, CheckResult]:
    return {check.id: check for check in certificate.checks}


def column_items(spec: ColumnSpec, checks: Mapping[str, CheckResult]) -> dict[str, CheckResult]:
    """The rows §4.8 names for the column `spec.unit_id`, by id."""
    unit = spec.unit_id
    ids = [f"material_balance.{unit}.{c}" for c in spec.components]
    ids.append(f"energy_balance.{unit}")
    ids += [f"specification.{unit}.{end}" for end in spec.ends() if spec.end_specification(end)]
    ids += [f"phase_admissibility.{unit}.stage.{j}" for j in range(1, spec.stage_count + 1)]
    missing = [identifier for identifier in ids if identifier not in checks]
    assert not missing, missing
    return {identifier: checks[identifier] for identifier in ids}


def _final_state(name: str) -> dict[str, float]:
    run = solved(name)[2]
    assert run.state is not None
    return dict(run.state)


# -- S11.A35 ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", [*COLUMN_CASES, RECYCLE_CASE])
def test_a35_the_syn001_column_certificates_verify(
    name: str, registered: pytest.MonkeyPatch
) -> None:
    """S11.A35: material, energy and specification rows within tolerance, every stage item
    passes (no failing acceptance item), and the certificate is VERIFIED."""
    certificate = certify(name)
    checks = by_id(certificate)
    items = column_items(column_case_spec(name), checks)
    failing = {k: (c.result, c.value, c.reason) for k, c in items.items() if c.result != "pass"}
    assert not failing, failing
    stages = [c for k, c in items.items() if ".stage." in k]
    assert all(c.value == 0.0 and c.reason == "" for c in stages)
    assert certificate.verification_status == "VERIFIED", [
        (c.id, c.result, c.reason) for c in certificate.checks if c.result != "pass"
    ]


#: S11 rulings item 2 (R-831): each Wilson case's absent component (S10-C: C-MW is methanol-water,
#: C-EW ethanol-water, the stripper C-MW's feed) and the measured |Z| (63, 63, 34).
ABSENT = {"C-MW": ("C2H5OH", 63), "C-EW": ("CH3OH", 63), WILSON_STRIPPER: ("C2H5OH", 34)}


def _target(name: str) -> tuple[BoundDeclaration, dict[str, float], frozenset[str]]:
    """The certificate's target at the case's converged state, and its Z (R-831)."""
    binding, document, _, _ = solved(name)
    view = parse_revision(document)
    state = _final_state(name)
    domain = fresh_provider(view.basis).describe().domain["P"]
    target = BoundDeclaration(
        binding.spec, compile_problem(binding.spec), state, pressure_domain=domain
    )
    return target, state, one_sided_columns(binding.spec.variable_ids, state, view.components)


@pytest.mark.parametrize("name", [*WILSON_CASES, WILSON_STRIPPER])
def test_a35_the_wilson_column_rows_pass(name: str, registered: pytest.MonkeyPatch) -> None:
    """S11.A35 on C-MW, C-EW and the stripper, as restated by S11 rulings item 2 (R-831): every
    row passes and the certificate is VERIFIED. The absent component's exactly-zero columns beside
    a positive sibling (Z) are differenced by the forward five-point stencil, whose part of the
    witness is at roundoff: <= DERIVATIVE_TOLERANCE/10 (measured 6.09e-10, 6.22e-10, 3.27e-10)."""
    certificate = certify(name)
    checks = by_id(certificate)
    column_items(column_case_spec(name), checks)
    failing = {k: (c.result, c.reason) for k, c in checks.items() if c.result != "pass"}
    assert not failing, failing
    assert certificate.verification_status == "VERIFIED"
    assert not [x for x in certificate.limitations if x.kind == "derivative_witness_partial"]

    absent, size = ABSENT[name]
    target, state, z = _target(name)
    assert len(z) == size
    assert all(column.rpartition(".")[2] == absent for column in z), sorted(z)
    witness = [c for c in certificate.checks if c.category == "derivative_witness"]
    assert [c.id for c in witness] == [
        "derivative_witness.on_pattern",
        "derivative_witness.off_pattern",
    ]
    assert all(c.value is not None and c.value <= DERIVATIVE_TOLERANCE for c in witness)
    # The one-sided part alone: every column outside Z left undifferenced.
    rest = frozenset(target.spec.variable_ids) - z
    one_sided = derivative_witness(target, state, unstenciled=rest, one_sided=z)
    assert [c.result for c in one_sided] == ["pass", "pass"]
    worst = max(c.value or 0.0 for c in one_sided)
    assert worst <= DERIVATIVE_TOLERANCE / 10, worst


def test_a35_a_wrong_ad_entry_in_a_one_sided_column_fails_the_witness(
    registered: pytest.MonkeyPatch,
) -> None:
    """S11 rulings item 2 (R-831), mutation: on C-MW, the AD entry of largest scaled magnitude in a
    Z column set to 0.0 makes `derivative_witness.on_pattern` FAIL, so the one-sided stencil
    witnesses those columns."""
    target, state, z = _target("C-MW")
    compiled, scaling = target.compiled, target.scaling
    base = compiled.jacobian(np.array(state_vector(target.spec, state)), target.context)
    largest, at = 0.0, -1
    for column, name in enumerate(base.col_ids):
        if name not in z:
            continue
        for offset in range(base.indptr[column], base.indptr[column + 1]):
            row_id = base.row_ids[base.indices[offset]]
            scaled = abs(base.data[offset]) * scaling.column[name] / scaling.row[row_id]
            if scaled > largest:
                largest, at = scaled, offset
    assert at >= 0 and largest > 0.0

    class Mutated:
        def residual(self, x: Any, context: Any) -> Any:
            return compiled.residual(x, context)

        def jacobian(self, x: Any, context: Any) -> Any:
            found = compiled.jacobian(x, context)
            data = list(found.data)
            data[at] = 0.0
            return replace(found, data=tuple(data))

    tear = SimpleNamespace(
        spec=target.spec, compiled=Mutated(), context=target.context, scaling=scaling
    )
    checks = {c.id: c for c in derivative_witness(tear, state, one_sided=z)}
    assert checks["derivative_witness.on_pattern"].result == "fail"
    assert (checks["derivative_witness.on_pattern"].value or 0.0) >= largest / 2


# -- S11.A36 ---------------------------------------------------------------------------------------


def test_a36_a_condenser_duty_off_by_ten_tolerances_fails_the_energy_balance(
    registered: pytest.MonkeyPatch,
) -> None:
    spec = column_case_spec("M1")
    state = _final_state("M1")
    tolerance = CheckPolicy().tolerances["heat_rate"]
    state[stage_duty_id(spec.unit_id, 1)] += 10.0 * tolerance
    checks = by_id(certify("M1", state))
    energy = checks[f"energy_balance.{spec.unit_id}"]
    assert energy.result == "fail" and abs(energy.value or 0.0) >= 9.0 * tolerance
    assert by_id(certify("M1"))[f"energy_balance.{spec.unit_id}"].result == "pass"


def test_a36_swapping_two_stage_temperatures_fails_residuals_and_stage_items(
    registered: pytest.MonkeyPatch,
) -> None:
    spec = column_case_spec("M1")
    unit = spec.unit_id
    state = _final_state("M1")
    upper, lower = stage_temperature_id(unit, 3), stage_temperature_id(unit, 4)
    state[upper], state[lower] = state[lower], state[upper]
    checks = by_id(certify("M1", state))
    residuals = [k for k, c in checks.items() if k.startswith("residual.") and c.result == "fail"]
    assert any(f"{unit}:stage:3:" in k for k in residuals), residuals
    stages = {j: checks[f"phase_admissibility.{unit}.stage.{j}"] for j in (3, 4)}
    assert all(c.result == "fail" and (c.value or 0.0) > 0.0 for c in stages.values()), stages


# -- S11.A37 ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", WILSON_CASES)
def test_a37_every_wilson_stage_liquid_is_stable(name: str, registered: pytest.MonkeyPatch) -> None:
    spec = column_case_spec(name)
    checks = by_id(certify(name))
    found = {
        j: checks[f"phase_stability.{spec.unit_id}.stage.{j}"] for j in spec.equilibrium_stages()
    }
    failing = {j: (c.result, c.value) for j, c in found.items() if c.result != "pass"}
    assert not failing, failing


def test_a37_no_stability_rows_on_syn001(registered: pytest.MonkeyPatch) -> None:
    """The γ–φ rows only: SYN-001's K-values are composition-independent."""
    assert not any(k.startswith("phase_stability.") for k in by_id(certify("M1")))


# -- S11.A38 ---------------------------------------------------------------------------------------


def test_a38_a_recovery_with_no_component_feed_fails(registered: pytest.MonkeyPatch) -> None:
    """S11.A38: J2's condenser recovery of A, with the feed's A flow set to 0 at `x_final`: the
    recovery is undefined, and the check fails however small `n_A − ν*·F_A` is."""
    spec = column_case_spec("J2")
    given = spec.condenser_spec
    assert given is not None and given.kind == "recovery" and given.component == "A"
    state = _final_state("J2")
    state[flow_id("S-IN1", "A")] = 0.0
    check = by_id(certify("J2", state))[f"specification.{spec.unit_id}.condenser"]
    assert check.result == "fail" and check.reason == "recovery_feed_not_positive(A)"
    stage = by_id(certify("J2", state))[f"phase_admissibility.{spec.unit_id}.stage.1"]
    assert stage.result == "unsupported" and stage.reason.startswith("acceptance_undefined(")
    control = by_id(certify("J2"))[f"specification.{spec.unit_id}.condenser"]
    assert control.result == "pass"


# -- the owner map in the verifier (§10.11) ----------------------------------------------------


@pytest.mark.parametrize("name", ["M1", "C-MW"])
def test_s1_the_verifiers_staged_splits_are_the_column_units_own(
    name: str, registered: pytest.MonkeyPatch
) -> None:
    """S11 review S1 (§10.2 step 7, §10.11 B4): the verifier's `StagedSplits`, built from
    `parse_revision`'s view of the column instance, equal (frozen-dataclass `==`) the copy the
    binder's builder holds and the solver reads — on SYN-001's M1 and on Wilson's C-MW."""
    binding, document, _, _ = solved(name)
    staged = _staged_splits(parse_revision(document))
    units = {u.unit_id: u for u in binding.flowsheet.units() if u.model_id in STAGED_MODELS}
    assert list(staged) == list(units) == [column_case_spec(name).unit_id]
    for unit_id, unit in units.items():
        assert staged[unit_id] is not unit.staged_splits()
        assert staged[unit_id] == unit.staged_splits()


def test_the_certificate_lifts_the_column_stages(registered: pytest.MonkeyPatch) -> None:
    """The verifier's splits are the column's stages, keyed `stage_unit(U, j)`, and each owner
    is the column; the phase branch records each stage split."""
    spec = column_case_spec("M1")
    _, document, run, _ = solved("M1")
    view = parse_revision(document)
    staged = _staged_splits(view)
    assert list(staged) == [spec.unit_id]
    splits = lifted_splits(
        [(i.unit_id, i.model_id, i.wiring) for i in view.instances], view.components, staged=staged
    )
    keys = [f"{spec.unit_id}.stage.{j}" for j in spec.equilibrium_stages()]
    assert [s.unit for s in splits] == keys
    branch = certify("M1").phase_branch
    assert all(f"{key}:{key}" in branch for key in keys)


def test_a_dormant_stage_has_no_zero_flow_reading_yet(registered: pytest.MonkeyPatch) -> None:
    """A stage split at `V = L = 0` with a dormant feed would be reduced by the column's own
    per-stage zero-flow form, which the verifier has no reading of (escalated, S11 B4): it is
    refused by name, never reduced as a heater."""
    _, document, _, _ = solved("M1")
    view = parse_revision(document)
    staged = _staged_splits(view)
    splits = lifted_splits(
        [(i.unit_id, i.model_id, i.wiring) for i in view.instances], view.components, staged=staged
    )
    owners = split_owners(staged)
    state = _final_state("M1")
    assert zero_flow_splits(view, splits, state, owners) == ()
    stage = splits[2]
    for name in (stage.vapor_total, stage.liquid_total, *stage.feed):
        state[name] = 0.0
    with pytest.raises(ValueError, match=r"^zero_flow_form_unknown\(syn001\.column\)$"):
        zero_flow_splits(view, splits, state, owners)
