"""T05b W6: the phase contract `T05b-phase-contract-v2` (spec §6.2–§6.5; ADR 0012 D4, D10 F2).

Every case runs the common path — `plan_revision` → `execute_plan` → `verify_revision` when
`CONVERGED` — under the policy `T05b-v2` (`t05b_support.POLICY_V2`, spec §6.6), and where the
spec asks, under `T05-W13` (v1) from the same revision. Expectations are `ref` =
`benchmarks/t05b/reference_values.yaml` (the design lane's 40-digit twin); a state is compared at
spec §13's EO allowances (T02 §6.4: `3.1e-7 mol/s`, `1e-5 K`, `0.1 Pa`, `1e-2 W`), a certificate
check at its own `τ_kind`. Values marked *regression* are self-generated: pinned beside their
assertion, reported to the design lane if they move, never re-pinned.

- B07: C1, C2, C3, C3X under v2 give the R0 projection of their v1 runs, the policy's identity
  aside (its id, and the plan ids that embed it).
- B08–B11: SC-1…SC-4, one flowing component (spec §12.3).
- B12, B13: NP-1…NP-3 and NP-G, near-pure feeds (spec §12.4).
- B20 (a)–(c): every switch recorded, deterministically; (b) is the contract's kernel at KS-1…KS-3
  (spec §12.7). B20 (d) (form switches of a non-lifted outlet) is W7b's.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from functools import cache
from typing import Any

import pytest
import yaml
from t05_support import CONTEXT, PROVIDER
from t05_w12_support import bind
from t05b_support import (
    NEAR_PURE_CASES,
    POLICY_V2,
    REF,
    REPO_ROOT,
    SINGLE_COMPONENT_CASES,
    judged_where,
    near_pure,
    number,
    revision_projection,
    sc1,
)
from test_t05_certificates import certify
from test_t05_coupled import CASE_DIR
from test_t05_coupled import POLICY as POLICY_V1
from test_t05_coupled import Solved as CoupledSolved

from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.models.revision_flowsheet import parse_revision
from openflowsheet.models.syn001.ph_kernel import port_enthalpy
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import PlanResult, execute_plan
from openflowsheet.orchestrator.region import RegionResult, _contract_kernel
from openflowsheet.orchestrator.revision import TraversalStart, plan_revision, traversal_start
from openflowsheet.orchestrator.splits import closure_types, lifted_splits
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.run.identity import execution_plan_r0, r0_projection
from openflowsheet.verify import CheckResult
from openflowsheet.verify.certificate import SolutionCertificate, verify_revision
from openflowsheet.verify.checks import KIND_TOLERANCE
from openflowsheet.verify.saturation import band_ends, split_route
from openflowsheet.verify.table import SPLIT_ENTHALPY_NOTE, UNRESOLVED_ENTHALPY_NOTE

K04F9_REF: dict[str, Any] = yaml.safe_load(
    (REPO_ROOT / "benchmarks" / "k04f9" / "reference_values.yaml").read_text()
)

COMPONENTS = ("A", "B", "C")
ALLOWANCE: Mapping[str, float] = {
    kind: number(value) for kind, value in REF["tolerances"]["coupled_allowances"].items()
}
CASES: dict[str, Any] = {
    **{name: build for name, build in SINGLE_COMPONENT_CASES.items()},
    **{name: (lambda name=name: near_pure(name)) for name in NEAR_PURE_CASES},
}

#: Regression values (measured 2026-09-25, W6): the `T05-W13` outcomes of SC-1…SC-3. SC-1 and
#: SC-3 are T05b W0.1's. None of them is ever `VERIFIED`. SC-2's moved at W9.5 (K03 §5.3 as
#: amended, R-064; the move B33 (d) names): its `VAPOR` attempt was `BOUND_BLOCKED` at iteration 0
#: on released structural zeros; it now runs two iterations and the contract cycles back to
#: `LIQUID` — `ACTIVE_SET_CYCLING` (was `BOUND_BLOCKED`), still no certificate.
V1_OUTCOME = {
    "SC-1": "ACTIVE_SET_CYCLING",
    "SC-2": "ACTIVE_SET_CYCLING",
    "SC-3": "ACTIVE_SET_CYCLING",
}
#: Regression values (W6): SC-3's attempt count and its attempts' iterations under v2.
#: Re-registered at W9.4 (spec §6.2 step 3 as amended, Q-S11 (a)): attempt 1 opens with both
#: products at the closure's `T` (the liquid's was the trial's 365.08 K), which is KS-1's root, and
#: closes at iteration 0 (was 1).
SC3_ITERATIONS = (2, 0)
#: Regression values (W6), spec B13 and B20 (a): NP-G's verdict; NP-2's and NP-G's band records.
NP_G_VERDICT = "VERIFIED"
BAND_RECORDS = {"NP-1": 1, "NP-2": 1, "NP-3": 0, "NP-G": 0}


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

    def checks(self) -> dict[str, CheckResult]:
        assert self.certificate is not None
        return {check.id: check for check in self.certificate.checks}

    def messages(self, kind: str) -> list[str]:
        return [event.message for event in self.run.trace.events if event.kind == kind]


def solve(document: dict[str, Any], policy: SolvePolicy) -> Solved:
    binding = bind(document)
    plan, _ = plan_revision(binding, policy)
    assert isinstance(plan, ExecutionPlan), plan
    run = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=policy)
    certificate = None
    if run.outcome == "CONVERGED":
        certificate = verify_revision(binding, document, run, solve_plan=plan.steps[-1].solve_plan)
    return Solved(document, binding, plan, run, certificate)


@cache
def solved(case: str, contract: str = "v2") -> Solved:
    return solve(CASES[case](), POLICY_V2 if contract == "v2" else POLICY_V1)


def _near(got: float, expected: str, allowance: float, what: str) -> None:
    difference = float(abs(Decimal(got) - Decimal(expected)))
    assert difference <= allowance, (what, got, expected, difference)


def _stream(state: Mapping[str, float], stream: str, entry: Mapping[str, Any]) -> None:
    """A registered stream entry against the state, at spec §13's EO allowances."""
    for index, component in enumerate(COMPONENTS):
        if "n_mol_per_s" in entry:
            _near(
                state[f"{stream}.n.{component}"],
                entry["n_mol_per_s"][index],
                ALLOWANCE["flow"],
                f"{stream}.n.{component}",
            )
        for key, prefix in (("vapor_mol_per_s", "vap"), ("liquid_mol_per_s", "liq")):
            if key in entry:
                _near(
                    state[f"{stream}.{prefix}.{component}"],
                    entry[key][index],
                    ALLOWANCE["flow"],
                    f"{stream}.{prefix}.{component}",
                )
    if "T_K" in entry:
        _near(state[f"{stream}.T"], entry["T_K"], ALLOWANCE["T"], f"{stream}.T")
    if "P_Pa" in entry:
        _near(state[f"{stream}.P"], entry["P_Pa"], ALLOWANCE["P"], f"{stream}.P")


def _root(case: str, result: Solved) -> None:
    """`ref.single_component_cases.<case>.root` against the solved state."""
    state = result.run.state
    assert state is not None
    for key, entry in REF["single_component_cases"][case]["root"].items():
        if isinstance(entry, dict):
            _stream(state, key, entry)
        elif key.endswith((".Q", ".W")):
            _near(state[key], entry, ALLOWANCE["duty"], key)


def _degenerate(checks: Mapping[str, CheckResult], unit: str, feed: str) -> None:
    """Spec §9.1's judgement of a degenerate split (B08): `.saturation` within 1e-9 K of 0 (every
    SC root is at `T_sat` exactly), `independent_split` `not_applicable`, no fresh-flash ids."""
    saturation = checks[f"phase_admissibility.{unit}.{feed}.saturation"]
    assert saturation.result == "pass" and saturation.value is not None
    assert abs(saturation.value) <= 1e-9, saturation.value
    split = checks[f"independent_split.{unit}.{feed}"]
    assert (split.result, split.reason) == ("not_applicable", "temperature_degenerate")
    assert not any(name.startswith(f"independent_split.{unit}.{feed}.") for name in checks)


def _verified(result: Solved) -> dict[str, CheckResult]:
    assert result.certificate is not None, result.run.message
    checks = result.checks()
    assert result.certificate.verification_status == "VERIFIED", [
        (c.id, c.result, c.value) for c in result.certificate.checks if c.result != "pass"
    ]
    assert result.certificate.regularity is not None
    assert result.certificate.regularity.status == "NO_RANK_LOSS_DETECTED"
    for name, check in checks.items():
        if name.startswith("energy_balance."):
            assert check.result == "pass", name
    return checks


def _signatures(result: Solved) -> list[list[list[str]]]:
    return [[list(item) for item in attempt.signature] for attempt in result.region.attempts]


# ------------------------------------------------------------------------------------ B07


def _coupled_r0(case: str, policy: SolvePolicy) -> dict[str, Any]:
    """`scripts/t05_identity._case` under `policy`: the same projections of the same run."""
    binding = bind_revision_flowsheet(yaml.safe_load((CASE_DIR / f"{case}.yaml").read_text()))
    assert isinstance(binding, RevisionBinding), binding
    plan, report = plan_revision(binding, policy)
    assert isinstance(plan, ExecutionPlan), plan
    run = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=policy)
    artifacts: dict[str, Any] = {
        "solve-events.json": [event.as_document() for event in run.trace.events],
        "structural-report.json": report.as_document(),
    }
    converged = run.outcome == "CONVERGED"
    if converged:
        artifacts["solution-certificate.json"] = certify(
            CoupledSolved(binding, plan, report, run), case
        ).as_document()
    detail = run.steps[-1].detail if run.steps else None
    fingerprint = (
        detail.root_fingerprint if converged and isinstance(detail, RegionResult) else None
    )
    return {
        "plan": execution_plan_r0(plan.as_document()),
        "outcome": run.outcome,
        **r0_projection(artifacts),
        # The whole fingerprint, its state digests included: stronger than `t05_identity`'s
        # R0 projection (T03's drops them) — the two literals reach the same root bit for bit.
        "root_fingerprint": fingerprint,
        "message": run.message.splitlines()[0] if run.message else "",
        # Not R0 (messages are not in `r0_projection`): the attempt records, compared too.
        "records": [(event.kind, event.message) for event in run.trace.events],
    }


def _without_policy(document: Any, policy_id: str) -> Any:
    """The policy's identity out of an R0 document: its id, and the plan ids that embed it."""
    if isinstance(document, dict):
        return {
            key: _without_policy(value, policy_id)
            for key, value in document.items()
            if key != "policy_id"
        }
    if isinstance(document, list | tuple):
        return [_without_policy(value, policy_id) for value in document]
    if isinstance(document, str):
        return re.sub(rf"-{re.escape(policy_id)}(?=-|$)", "-<policy>", document)
    return document


@pytest.mark.parametrize(
    "case", ["SYN-001-UL-C1", "SYN-001-UL-C2", "SYN-001-UL-C3", "SYN-001-UL-C3X"]
)
def test_b07_v2_is_a_conservative_extension_on_t05s_coupled_cases(case: str) -> None:
    v1 = _coupled_r0(case, POLICY_V1)
    v2 = _coupled_r0(case, POLICY_V2)
    assert v1["plan"]["policy_id"] == POLICY_V1.policy_id
    assert v2["plan"]["policy_id"] == POLICY_V2.policy_id
    assert _without_policy(v2, POLICY_V2.policy_id) == _without_policy(v1, POLICY_V1.policy_id)
    # B30 (a), as far as W6 reaches: no attempt of either literal names a dormancy item.
    assert all("." not in unit for event in v2["events"] for unit, _ in (event["signature"] or []))


# --------------------------------------------------------------------------- B08–B11: SC


def test_b08_sc1() -> None:
    result = solved("SC-1")
    assert result.run.outcome == "CONVERGED", result.run.message
    assert _signatures(result) == [[["U-VLV", "TWO_PHASE"]]]
    assert result.messages("initializer_candidate") == []  # no projection of S2, no band route
    _root("SC-1", result)
    checks = _verified(result)
    _degenerate(checks, "U-VLV", "S2")
    note = SPLIT_ENTHALPY_NOTE.format(stream="S2")
    for name in ("energy_balance.U-VLV", "energy_balance.envelope"):
        assert note in (checks[name].independence_qualification or ""), name
    assert result.region.root_fingerprint is not None
    assert result.region.root_fingerprint["branch_found"] == [["U-VLV", "TWO_PHASE"]]


def test_b09_sc2() -> None:
    result = solved("SC-2")
    assert result.run.outcome == "CONVERGED", result.run.message
    assert _signatures(result) == [[["U-PHF", "TWO_PHASE"]]]
    assert result.messages("initializer_candidate") == []
    _root("SC-2", result)
    checks = _verified(result)
    _degenerate(checks, "U-PHF", "S1")
    for name in ("energy_balance.U-PHF", "energy_balance.envelope"):
        qualification = checks[name].independence_qualification or ""
        for stream in ("S2", "S3"):
            assert SPLIT_ENTHALPY_NOTE.format(stream=stream) in qualification, (name, stream)
    assert result.region.root_fingerprint is not None
    assert result.region.root_fingerprint["branch_found"] == [["U-PHF", "TWO_PHASE"]]


def test_b10_sc3() -> None:
    result = solved("SC-3")
    entry = REF["single_component_cases"]["SC-3"]
    assert result.run.outcome == "CONVERGED", result.run.message
    signatures = _signatures(result)
    assert signatures[0] == entry["signatures"]["opening"]
    assert signatures[-1] == entry["signatures"]["final"]
    opened = result.messages("attempt_opened")
    updates = [message for message in opened if message.startswith("phase_update(")]
    assert len(updates) == 1, opened
    # KS-1's primary answer: the PH closure's `TWO_PHASE`, no fallback item.
    assert updates == ["phase_update(phase_wall(patience, U-PHF:LIQUID->TWO_PHASE))"]
    _root("SC-3", result)
    checks = _verified(result)
    _degenerate(checks, "U-VLV", "S2")
    _degenerate(checks, "U-PHF", "S2")
    # Regression values: the attempt count and iterations.
    assert tuple(attempt.iterations for attempt in result.region.attempts) == SC3_ITERATIONS


def test_b11_sc4() -> None:
    result = solved("SC-4")
    entry = REF["single_component_cases"]["SC-4"]
    # The traversal succeeds; U-PHF2's causal inlet admissibility is `δ = 0` (spec §10).
    start = traversal_start(result.binding.flowsheet, result.binding.spec.variable_ids)
    assert isinstance(start, TraversalStart), start
    flowsheet = result.binding.flowsheet
    traversed = flowsheet.traverse({})
    assert traversed.status == "ok"
    admitted = port_enthalpy(
        flowsheet.provider,
        traversed.streams["S2"],
        "VAPOR",
        flowsheet.components,
        flowsheet.context,
        port="inlet",
    )
    assert admitted.failure is None
    assert admitted.admissibility == number(entry["r007"]["U-PHF2.inlet_degeneracy_K"]) == 0.0
    assert result.run.outcome == "CONVERGED", result.run.message
    assert _signatures(result) == [[list(item) for item in entry["signature"]]]
    _root("SC-4", result)
    checks = _verified(result)
    for name in ("phase_admissibility.U-PHF2.inlet", "phase_admissibility.U-PUMP.inlet"):
        value = checks[name].value
        assert checks[name].result == "pass" and value is not None and abs(value) <= 1e-9, name


@pytest.mark.parametrize("case", ["SC-1", "SC-2", "SC-3"])
def test_b08_b10_under_v1_never_verified(case: str) -> None:
    result = solved(case, "v1")
    assert result.run.outcome == V1_OUTCOME[case]  # regression value
    assert result.certificate is None


# ------------------------------------------------------------------------- B12, B13: NP


def _near_pure_root(case: str, result: Solved) -> None:
    root = REF["near_pure_cases"][case]["root"]
    state = result.run.state
    assert state is not None
    for index, component in enumerate(COMPONENTS):
        _near(state[f"S2.n.{component}"], root["vapor_mol_per_s"][index], ALLOWANCE["flow"], "S2")
        _near(state[f"S3.n.{component}"], root["liquid_mol_per_s"][index], ALLOWANCE["flow"], "S3")
    for stream in ("S2", "S3"):
        _near(state[f"{stream}.T"], root["T_K"], ALLOWANCE["T"], f"{stream}.T")


@pytest.mark.parametrize("case", ["NP-1", "NP-2", "NP-3"])
def test_b12_near_pure(case: str) -> None:
    result = solved(case)
    assert result.run.outcome == "CONVERGED", result.run.message
    assert _signatures(result) == [[["U-PHF", "TWO_PHASE"]]]
    _near_pure_root(case, result)
    checks = _verified(result)
    if REF["near_pure_cases"][case]["degenerate"]:
        saturation = checks["phase_admissibility.U-PHF.S1.saturation"]
        assert saturation.result == "pass"
        split = checks["independent_split.U-PHF.S1"]
        assert (split.result, split.reason) == ("not_applicable", "temperature_degenerate")
    else:
        assert "phase_admissibility.U-PHF.S1.saturation" not in checks
        for suffix in ("total", *COMPONENTS):
            assert checks[f"independent_split.U-PHF.S1.{suffix}"].result == "pass", suffix
    assert result.certificate is not None
    judged_where(result.certificate, "projection")
    # K04-F9 X10: no NP-1…NP-3 split is unresolved (ADR 0013 D3).
    assert not any(
        "fresh flash unresolved" in (c.independence_qualification or "") for c in checks.values()
    )
    if case == "NP-1":
        candidates = result.messages("initializer_candidate")
        assert candidates == ["closure_route(U-PHF, band)"]
        kinds = [event.kind for event in result.run.trace.events]
        at = kinds.index("initializer_candidate")
        assert kinds[at + 1] == "initializer_accepted"
        assert kinds.index("attempt_opened") > at + 1


def _floor_at_the_projection(result: Solved) -> tuple[str, float | None]:
    """ADR 0013 D3's routing of `U-PHF` at the verifier's projection of the solved state."""
    state = result.run.state
    assert state is not None
    projection, _ = revision_projection(result.binding, result.document, dict(state))
    assert projection.judged_at == "projection", projection.reason
    at = projection.state
    view = parse_revision(result.document)
    (split,) = lifted_splits(
        [(i.unit_id, i.model_id, i.wiring) for i in view.instances], view.components
    )
    feed = tuple(at[column] for column in split.feed)
    t_bubble, t_dew = band_ends(PROVIDER, feed, at[split.pressure], CONTEXT)
    return split_route(
        at[split.temperature],
        sum(feed),
        t_bubble,
        t_dew,
        two_phase=at[split.vapor_total] > 0.0 and at[split.liquid_total] > 0.0,
        flow_tolerance=KIND_TOLERANCE["molar_flow"],
    )


def _floor_reference(key: str) -> Fraction:
    """`N ulp(T) / (w τ_flow)` from `ref.closed_form.routing.<key>`'s 20-digit fields, exactly;
    the registered ratio is this printed to six digits (K04-F9 spec §9)."""
    entry = K04F9_REF["closed_form"]["routing"][key]
    width = Fraction(entry["T_dew_K"]) - Fraction(entry["T_bubble_K"])
    exact = (
        Fraction(entry["N_mol_per_s"])
        * Fraction(math.ulp(float(entry["T_K"])))
        / (width * Fraction(KIND_TOLERANCE["molar_flow"]))
    )
    printed = Fraction(entry["floor_over_tau_flow"])
    assert abs(exact - printed) <= Fraction(5, 10**6) * printed, (float(exact), printed)
    return exact


def test_b13_np_g_the_residual_limitation() -> None:
    """K04-F9 X09 (B13 amended; ADR 0013 D3): NP-G is `VERIFIED` by rule, not by luck. Its PH
    flash's feed band is 4.12 µK wide, so one ulp of `T` moves the fresh flash's vapour flow by
    0.89 `τ_flow`: the split is unresolved, its independent split `not_applicable`
    (`fresh_flash_unresolved`), its admissibility the two-phase closure, its products' enthalpies
    from the stored split (the D3 note) — and the energy balances close at the projection."""
    result = solved("NP-G")
    assert result.run.outcome == "CONVERGED", result.run.message
    assert result.certificate is not None
    checks = result.checks()
    assert "phase_admissibility.U-PHF.S1.saturation" not in checks
    verdict = result.certificate.verification_status
    assert verdict == NP_G_VERDICT == "VERIFIED", [
        (c.id, c.value) for c in result.certificate.checks if c.result == "fail"
    ]
    judged_where(result.certificate, "projection")
    split = checks["independent_split.U-PHF.S1"]
    assert (split.result, split.reason) == ("not_applicable", "fresh_flash_unresolved")
    assert not any(name.startswith("independent_split.U-PHF.S1.") for name in checks)
    closure = checks["phase_admissibility.U-PHF.S1.closure"]
    assert closure.result == "pass" and closure.value is not None
    for name in ("energy_balance.U-PHF", "energy_balance.envelope"):
        check = checks[name]
        qualification = check.independence_qualification or ""
        for stream in ("S2", "S3"):
            assert UNRESOLVED_ENTHALPY_NOTE.format(stream=stream) in qualification, (name, stream)
        assert check.value is not None and check.tolerance is not None
        assert abs(check.value) <= 1e-3 * check.tolerance, (name, check.value)
    assert not any(c.result == "unsupported" for c in result.certificate.checks)
    assert not any(
        c.category == "residual" and c.result == "fail" for c in result.certificate.checks
    )
    route, floor = _floor_at_the_projection(result)
    assert route == "unresolved" and floor is not None
    exact = _floor_reference("NP-G:U-PHF.S1")
    assert abs(Fraction(floor) - exact) <= Fraction(1, 10**6) * exact, (floor, float(exact))


def test_x10_np_3_is_resolved() -> None:
    """K04-F9 X10 (B12 unchanged): NP-3's band is 214 µK wide, its floor 0.0171 `τ_flow` (5.8×
    under the threshold) — resolved: the fresh flash judges its split, and no D3 note."""
    result = solved("NP-3")
    checks = _verified(result)
    for suffix in ("total", *COMPONENTS):
        assert checks[f"independent_split.U-PHF.S1.{suffix}"].result == "pass", suffix
    assert not any(
        "fresh flash unresolved" in (c.independence_qualification or "") for c in checks.values()
    )
    route, floor = _floor_at_the_projection(result)
    assert route == "resolved" and floor is not None
    exact = _floor_reference("NP-3:U-PHF.S1")
    assert abs(Fraction(floor) - exact) <= Fraction(1, 10**6) * exact, (floor, float(exact))


# ------------------------------------------------------------------------------------ B20


@pytest.mark.parametrize("case", sorted(CASES))
def test_b20a_closure_route_records(case: str) -> None:
    result = solved(case)
    records = [
        m for m in result.messages("initializer_candidate") if m.startswith("closure_route(")
    ]
    expected = BAND_RECORDS.get(case, 0)  # SC-1…SC-4: none
    assert records == ["closure_route(U-PHF, band)"] * expected


def _kernel_state(entry: Mapping[str, Any]) -> dict[str, float]:
    state = {"S2.T": number(entry["T_K"]), "S2.P": number(entry["P_Pa"])}
    for index, component in enumerate(COMPONENTS):
        state[f"S2.n.{component}"] = number(entry["feed_mol_per_s"][index])
        state[f"S2.vap.{component}"] = number(entry["vapor_mol_per_s"][index])
        state[f"S2.liq.{component}"] = number(entry["liquid_mol_per_s"][index])
    state["S2.V"] = sum(state[f"S2.vap.{c}"] for c in COMPONENTS)
    state["S2.L"] = sum(state[f"S2.liq.{c}"] for c in COMPONENTS)
    return state


@pytest.mark.parametrize("state_id", ["KS-1", "KS-2", "KS-3"])
def test_b20b_the_contract_kernel_of_a_ph_type_split(state_id: str) -> None:
    """Spec §12.7: a valve outlet frozen `LIQUID` at a trial. The PH closure at the split's own
    enthalpy answers KS-1 (saturation route) and KS-2 (band route); KS-3's enthalpy is below the
    domain, so the TP flash answers."""
    entry = REF["contract_kernel_states"][state_id]
    binding = bind(sc1())
    flowsheet = binding.flowsheet
    (split,) = lifted_splits(
        [
            (unit.unit_id, unit.model_id, flowsheet.wiring[unit.unit_id])
            for unit in flowsheet.units()
        ],
        flowsheet.components,
    )
    assert closure_types(flowsheet.units()) == {"U-VLV": "PH"}
    answer = _contract_kernel(
        flowsheet.provider, flowsheet.context, split, _kernel_state(entry), frozenset({"U-VLV"})
    )
    assert answer.regime == entry["expected_regime"]
    record = f"fallback(U-VLV, {answer.fallback})" if answer.fallback else ""
    assert record == entry["expected_record"]
    if "expected_T_K" in entry:
        _near(answer.values["S2.T"], entry["expected_T_K"], 1e-6, "T")
        feed = sum(number(value) for value in entry["feed_mol_per_s"])
        beta = answer.values["S2.V"] / feed
        _near(beta, entry["expected_beta"], 1e-9, "beta")
        for component in COMPONENTS:
            assert answer.values[f"S2.vap.{component}"] + answer.values[
                f"S2.liq.{component}"
            ] == pytest.approx(_kernel_state(entry)[f"S2.n.{component}"], abs=3.1e-8)
    else:
        # The TP flash's answer carries no temperature: the trial's stays.
        assert "S2.T" not in answer.values
        assert answer.values["S2.V"] == 0.0
    # The TP flash would have said `tp_regime` (KS-1, KS-2: the far regime).
    tp = _contract_kernel(
        flowsheet.provider, flowsheet.context, split, _kernel_state(entry), frozenset()
    )
    assert (tp.regime, tp.fallback) == (entry["tp_regime"], "")


_FLOAT = re.compile(r"\d\.\d|\d[eE][-+]?\d")


@pytest.mark.parametrize("case", sorted(CASES))
def test_b20c_deterministic_and_float_free(case: str) -> None:
    first, second = (solve(CASES[case](), POLICY_V2) for _ in range(2))

    def projection(result: Solved) -> dict[str, Any]:
        artifacts: dict[str, Any] = {
            "solve-events.json": [event.as_document() for event in result.run.trace.events]
        }
        if result.certificate is not None:
            artifacts["solution-certificate.json"] = result.certificate.as_document()
        return {
            **r0_projection(artifacts),
            "outcome": result.run.outcome,
            "records": [(event.kind, event.message) for event in result.run.trace.events],
            "fingerprint": result.region.root_fingerprint,
        }

    assert projection(first) == projection(second)
    for event in first.run.trace.events:
        if event.kind in ("attempt_opened", "initializer_candidate", "initializer_accepted"):
            assert not _FLOAT.search(event.message), event.message
    assert not _FLOAT.search(first.run.message.splitlines()[0] if first.run.message else "")


# ------------------------------------------------------------------------ the tear path


def test_v2_on_syn001s_tear_path_runs_v1s_rules() -> None:
    """The tear path has no lifted split, so no PH-type kernel and no `ZERO_FLOW` regime: under
    v2 it runs v1's rules (the W5 refusal is gone), bit for bit — the same state and trace."""
    from openflowsheet.compiled import EvaluationContext
    from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
    from openflowsheet.orchestrator.tear import solve_tear
    from openflowsheet.thermo.syn001 import Syn001Provider

    def run(policy: SolvePolicy) -> Any:
        context = EvaluationContext(model_version="T05b-W6@" + "0" * 64, constants_sha256="0" * 64)
        return solve_tear(
            Syn001Flowsheet(provider=Syn001Provider(), context=context), policy=policy
        )

    (v1, v1_trace), (v2, v2_trace) = run(POLICY_V1), run(POLICY_V2)
    assert v1.outcome == v2.outcome == "CONVERGED"
    assert v1.x.tobytes() == v2.x.tobytes()
    assert v1.signatures == v2.signatures
    assert _without_policy(
        [(e.kind, e.message) for e in v1_trace.events], POLICY_V1.policy_id
    ) == _without_policy([(e.kind, e.message) for e in v2_trace.events], POLICY_V2.policy_id)


# ------------------------------------------------------------ since W7: ZERO_FLOW under v2


@pytest.mark.parametrize("name", ["valve", "ph_flash"])
def test_a_v2_solve_of_a_dormant_split_runs_zero_flow(name: str) -> None:
    """Spec §7.1: under v2 a split whose feed is exactly dormant is in `ZERO_FLOW` (W7; until W7
    such a solve raised `phase_contract_unimplemented`). The v1 half's own revisions (DZ-1 and
    DZ-2, `test_t05_dormant_outlet.py`) converge at iteration 0 in the zero-flow form and are
    `VERIFIED`; B15's full v2 assertions are `test_t05b_zero_flow.py`'s."""
    from test_t05_dormant_outlet import CASES as DORMANT_CASES

    case = DORMANT_CASES[name]
    result = solve(case.document, POLICY_V2)
    assert result.run.outcome == "CONVERGED", result.run.message
    assert _signatures(result) == [[[case.unit, "ZERO_FLOW"]]]
    assert [a.iterations for a in result.region.attempts] == [0]
    # A dormant stream's enthalpy checks are `not_applicable`, so not `_verified`'s all-pass.
    assert result.certificate is not None
    assert result.certificate.verification_status == "VERIFIED", result.certificate.limitations


def test_b20_the_fallback_record_grammar() -> None:
    """Spec §6.5: one item per F2 fallback of the opening, in signature order; none, v1's text."""
    from openflowsheet.orchestrator.phase_contract import Conversion, restart_message

    def conversion(*fallbacks: tuple[str, str]) -> Conversion:
        return Conversion(
            signature=(("U-VLV", "TWO_PHASE"), ("U-PHF", "TWO_PHASE")),
            opening=None,
            source="phase_rejected_trial",
            cause="phase_wall(patience, U-VLV:LIQUID->TWO_PHASE, U-PHF:LIQUID->TWO_PHASE)",
            fallbacks=fallbacks,
        )

    cause = "phase_wall(patience, U-VLV:LIQUID->TWO_PHASE, U-PHF:LIQUID->TWO_PHASE)"
    assert restart_message(conversion()) == f"phase_update({cause})"
    assert (
        restart_message(conversion(("U-VLV", "ph-band"), ("U-PHF", "tp")))
        == f"phase_update({cause}; fallback(U-VLV, ph-band), fallback(U-PHF, tp))"
    )
