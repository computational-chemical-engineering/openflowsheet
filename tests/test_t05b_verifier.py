"""T05b W4: the verifier's judgement of temperature-degenerate streams (spec §9.1–§9.2), and its
inertness on every registered certificate (B14). B15's v1 half — zero-flow roots, §9.3 — is
`test_t05_dormant_outlet.py`; the verifier's R-016 independence is
`test_t05_table_independence.py`.

**B18, INJ-B1, INJ-B2, INJ-B2p** (spec §9.4, §12.6; `ref.injections`): three states at SC-1's
registered root, judged by `verify_revision(..., state=<injected>)` — K04 §9's injection route, in
which the solver claims `CONVERGED` and the verifier must judge the state it is handed. The claim
is SC-1's own solve under the policy `T05b-v2` (spec §6.6; `CONVERGED` since T05b W6, B08), with
its plan; under v1 SC-1 cycles (T05b W0.1: `ACTIVE_SET_CYCLING`) and has no claim to judge.
Expected values are the twin's closed forms, each compared at its check's own tolerance `τ_kind`.

**K04-F9 (ADR 0013 D1; spec §10.5)**: INJ-B2's state — every compiled row inside its tolerance, 2
`τ_T` from SC-1's root — is re-registered as **PRJ-B2** and `VERIFIED` at the verifier's projection
(X12; finding F1); **INJ-B2′** (2e-5 K) keeps the window's outer side (X14); INJ-B2p's balance is
judged at the projection (X13). T05b's registered INJ-B2 and INJ-B2p values stay asserted at
`x_final`, through the table evaluated there unprojected (`benchmarks/k04f9/reference_values.yaml`
registers the new expectations).

**§9.2** on a converged v1 solve: pure B vapour at `T_sat` fed to a PH flash's inlet declared
`vapor` (R-007 admits it since W3, `δ = 0`). The feed belongs to no split, so the verifier reads
its enthalpy in its declared phase; the fresh flash, which says `LIQUID` at `K_B = 1`, would miss
the PH flash's energy balance by the latent heat. The `vapor_liquid` branch of §9.2 cannot be
bound (T05 S1), so it is exercised on the parsed revision alone.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import pytest
import yaml
from t05_support import CONTEXT, PROVIDER
from t05_syn001_shaped import shaped_revision
from t05_w12_support import POLICY, bind, duty_pin, unit_instance
from t05b_support import (
    P_R,
    POLICY_V2,
    PURE_B,
    REF,
    REPO_ROOT,
    Product,
    Source,
    error,
    inj_b2_prime,
    judged_where,
    number,
    prj_b2,
    revision,
    revision_projection,
    sc1,
    sc1_root,
)
from test_t05_coupled import CASE_DIR
from test_t05_coupled import CASES as COUPLED_CASES
from test_t05_coupled import solve as solve_coupled
from test_t05_w1d_verifier import _solve as solve_w1d

from openflowsheet.models import flow_id, pressure_id, temperature_id
from openflowsheet.models.revision_flowsheet import RevisionView, parse_revision
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import execute_plan
from openflowsheet.orchestrator.revision import initial_state, plan_revision
from openflowsheet.orchestrator.splits import lifted_splits
from openflowsheet.verify import CheckResult
from openflowsheet.verify import saturation as verifier_band
from openflowsheet.verify.certificate import SolutionCertificate, verify_revision
from openflowsheet.verify.checks import KIND_TOLERANCE, enthalpy_flow, stream_of
from openflowsheet.verify.table import (
    DECLARED_ENTHALPY_NOTE,
    SPLIT_ENTHALPY_NOTE,
    Degeneracy,
    degeneracy,
    revision_checks,
)

INJECTIONS: dict[str, Any] = REF["injections"]
K04F9_REF: dict[str, Any] = yaml.safe_load(
    (REPO_ROOT / "benchmarks" / "k04f9" / "reference_values.yaml").read_text()
)
#: Spec §12.6 / §13: an injection fails by at least `10³ τ`; INJ-B2p stays `10×` inside.
DETECTION_FACTOR = 1e3


# -- B18: the injections at SC-1's root ------------------------------------------------------


def _injected(name: str) -> dict[str, float]:
    state = sc1_root()
    if name == "INJ-B1":
        # The TP kernel's answer at T_sat: all liquid, V = 0, L = 2.
        for c in "ABC":
            state[f"S2.liq.{c}"] = state[flow_id("S2", c)]
            state[f"S2.vap.{c}"] = 0.0
        state["S2.V"], state["S2.L"] = 0.0, sum(state[f"S2.liq.{c}"] for c in "ABC")
    elif name == "PRJ-B2":
        state = prj_b2()
    elif name == "INJ-B2′":
        state = inj_b2_prime()
    elif name == "INJ-B2p":
        state["S2.T"] = 360.0000005
    return state


#: The states judged against SC-1's v2 claim: the root, T05b's injections and K04-F9's.
JUDGED = ("SC-1", "INJ-B1", "PRJ-B2", "INJ-B2p", "INJ-B2′")


@pytest.fixture(scope="module")
def judged() -> dict[str, SolutionCertificate]:
    """SC-1's v2 solve claims `CONVERGED`; each injected state is judged against that claim."""
    document = sc1()
    binding = bind(document)
    plan, _ = plan_revision(binding, POLICY_V2)
    assert isinstance(plan, ExecutionPlan), plan
    claim = execute_plan(
        plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=POLICY_V2
    )
    assert claim.outcome == "CONVERGED", claim.message
    solve_plan = plan.steps[-1].solve_plan
    assert solve_plan is not None
    return {
        name: verify_revision(
            binding, document, claim, state=_injected(name), solve_plan=solve_plan
        )
        for name in JUDGED
    }


def _at_x_final(name: str) -> dict[str, CheckResult]:
    """The table at the injected state itself, unprojected (K04-F9 spec §10.5: T05b's registered
    values of INJ-B2 and INJ-B2p remain true of the states at `x_final`)."""
    _, unprojected = revision_projection(bind(sc1()), sc1(), _injected(name))
    return {check.id: check for check in unprojected}


def _by_id(certificate: SolutionCertificate) -> dict[str, CheckResult]:
    return {check.id: check for check in certificate.checks}


def _registered(check: CheckResult, expected: str) -> None:
    """Within the check's own `τ_kind` of the registered closed form."""
    assert check.value is not None and check.tolerance is not None, check.id
    assert error(check.value, expected) <= check.tolerance, (check.id, check.value, expected)


def _degenerate_judgement(by_id: Mapping[str, CheckResult], distance: str) -> None:
    saturation = by_id["phase_admissibility.U-VLV.S2.saturation"]
    assert saturation.result == "pass" and saturation.value is not None
    assert error(saturation.value, distance) <= 1e-12, saturation.value
    split = by_id["independent_split.U-VLV.S2"]
    assert (split.result, split.reason) == ("not_applicable", "temperature_degenerate")
    assert not any(name.startswith("independent_split.U-VLV.S2.") for name in by_id)
    assert not any(
        name.startswith("phase_admissibility.U-VLV.S2.") and not name.endswith(".saturation")
        for name in by_id
    )
    note = SPLIT_ENTHALPY_NOTE.format(stream="S2")
    for name in ("energy_balance.U-VLV", "energy_balance.envelope"):
        qualification = by_id[name].independence_qualification
        assert qualification is not None and qualification.endswith(note), name


def test_b18_sc1s_root_is_verified_on_the_stored_split(
    judged: dict[str, SolutionCertificate],
) -> None:
    """The control: SC-1's registered root itself, degenerate (`δ = 0`), `VERIFIED`."""
    certificate = judged["SC-1"]
    assert certificate.verification_status == "VERIFIED", [
        c.id for c in certificate.checks if c.result != "pass"
    ]
    judged_where(certificate, "projection")
    by_id = _by_id(certificate)
    _degenerate_judgement(by_id, "0.0")
    assert by_id["energy_balance.U-VLV"].result == "pass"


def test_b18_inj_b1_a_wrong_vapour_fraction_fails_the_energy_balance(
    judged: dict[str, SolutionCertificate],
) -> None:
    entry = INJECTIONS["INJ-B1"]
    certificate = judged["INJ-B1"]
    assert certificate.verification_status == "FAILED"
    assert certificate.false_success_detected
    judged_where(certificate, "final_state", "residual_not_passed")
    by_id = _by_id(certificate)
    _degenerate_judgement(by_id, entry["degeneracy_K"])
    balance = by_id["energy_balance.U-VLV"]
    assert balance.result == "fail"
    _registered(balance, entry["energy_balance_U-VLV_W"])
    assert balance.value is not None and balance.tolerance is not None
    assert abs(balance.value) >= DETECTION_FACTOR * balance.tolerance
    # Spec §12.6 (ruled, second pass): the failing checks are exactly these three, each 2 016 W
    # as inlet minus outlet — the compiled energy row reads the stored split as the balances do.
    failing = {c.id for c in certificate.checks if c.result == "fail"}
    assert failing == {
        "residual.U-VLV:VLV-energy",
        "energy_balance.U-VLV",
        "energy_balance.envelope",
    }
    _registered(by_id["residual.U-VLV:VLV-energy"], entry["compiled_energy_row_W"])
    _registered(by_id["energy_balance.envelope"], entry["energy_balance_envelope_in_minus_out_W"])


def test_x12_prj_b2_a_state_correct_to_its_tolerance_is_verified(
    judged: dict[str, SolutionCertificate],
) -> None:
    """K04-F9 X12 (finding F1; the former INJ-B2): SC-1's root with `S2.T = 360.000002 K`. Every
    compiled row is inside its tolerance, so the fresh-flash categories are judged at the
    projection, which is SC-1's root: `.saturation` at roundoff, the balances closed."""
    entry = K04F9_REF["closed_form"]["cases"]["PRJ-B2"]
    certificate = judged["PRJ-B2"]
    assert certificate.verification_status == "VERIFIED", [
        (c.id, c.value) for c in certificate.checks if c.result != "pass"
    ]
    judged_where(certificate, "projection")
    by_id = _by_id(certificate)
    saturation = by_id["phase_admissibility.U-VLV.S2.saturation"]
    assert saturation.result == "pass" and saturation.value is not None
    assert abs(saturation.value) <= 1e-9, saturation.value
    for name in ("energy_balance.U-VLV", "energy_balance.envelope"):
        check = by_id[name]
        assert check.value is not None and check.tolerance is not None
        assert abs(check.value) <= 1e-3 * check.tolerance, (name, check.value)
    row = by_id["residual.U-VLV:VLV-energy"]
    assert row.result == "pass" and row.near_threshold and row.value is not None
    assert error(row.value, entry["compiled_energy_row_W"]) <= 1e-9, row.value


def test_x12_prj_b2_at_x_final_is_t05bs_registered_inj_b2(
    judged: dict[str, SolutionCertificate],
) -> None:
    """Spec §10.5, Q6: T05b's INJ-B2 entry stays true of the state at `x_final` — outside the
    degeneracy window (`δ = 2e-6 K`), the fresh flash says `VAPOR` and misses the lever-rule split
    by 1.93 mol/s — which is what the certificate no longer judges it by."""
    entry = INJECTIONS["INJ-B2"]
    by_id = _at_x_final("PRJ-B2")
    assert "phase_admissibility.U-VLV.S2.saturation" not in by_id
    for name, expected in (
        ("independent_split.U-VLV.S2.total", entry["independent_split_total_mol_per_s"]),
        ("energy_balance.U-VLV", entry["energy_balance_U-VLV_W"]),
    ):
        check = by_id[name]
        assert check.result == "fail", name
        _registered(check, expected)
    certificate = judged["PRJ-B2"]
    certified = _by_id(certificate)
    _registered(certified["residual.U-VLV:VLV-energy"], entry["compiled_energy_row_W"])
    _registered(certified["residual.U-VLV:VLV-equilibrium:B"], entry["compiled_equilibrium_row_B"])


def test_x14_inj_b2_prime_off_saturation_fails_at_x_final(
    judged: dict[str, SolutionCertificate],
) -> None:
    """K04-F9 X14: SC-1's root with `S2.T = 360.00002 K` (20 `τ_T`), the lever-rule split kept —
    the window's outer side end to end. Its compiled energy row fails, so every category is
    judged at `x_final`, where the fresh flash says `VAPOR`: split and balances fail by ≥ 10³ τ."""
    entry = K04F9_REF["closed_form"]["injections"]["INJ-B2-prime"]
    certificate = judged["INJ-B2′"]
    assert certificate.verification_status == "FAILED"
    assert certificate.false_success_detected
    judged_where(certificate, "final_state", "residual_not_passed")
    by_id = _by_id(certificate)
    failing = {c.id for c in certificate.checks if c.result == "fail"}
    row = by_id["residual.U-VLV:VLV-energy"]
    assert row.id in failing and row.value is not None
    assert error(row.value, entry["compiled_energy_row_W"]) <= 1e-9, row.value
    for name, key in (
        ("energy_balance.U-VLV", "energy_balance_U-VLV_W"),
        ("energy_balance.envelope", "energy_balance_U-VLV_W"),
        ("independent_split.U-VLV.S2.total", "independent_split_total_mol_per_s"),
        ("independent_split.U-VLV.S2.B", "independent_split_B_mol_per_s"),
    ):
        check = by_id[name]
        assert name in failing and check.value is not None and check.tolerance is not None
        assert error(check.value, entry[key]) <= 1e-9 * abs(number(entry[key])), (name, check.value)
        assert abs(check.value) >= DETECTION_FACTOR * check.tolerance, name
    equilibrium = by_id["residual.U-VLV:VLV-equilibrium:B"]
    assert equilibrium.result == "pass" and equilibrium.value is not None
    expected = entry["compiled_equilibrium_row_B"]
    assert error(equilibrium.value, expected) <= 1e-9 * abs(number(expected)), equilibrium.value
    assert "phase_admissibility.U-VLV.S2.saturation" not in by_id


def test_b18_inj_b2p_inside_the_window_balances(
    judged: dict[str, SolutionCertificate],
) -> None:
    """K04-F9 X13 (B18 amended): `VERIFIED` at the projection — `.saturation` at roundoff and the
    balance closed there; T05b's registered −1e-4 W is the balance at `x_final` (spec §10.5)."""
    entry = INJECTIONS["INJ-B2p"]
    certificate = judged["INJ-B2p"]
    assert certificate.verification_status == "VERIFIED"
    judged_where(certificate, "projection")
    by_id = _by_id(certificate)
    saturation = by_id["phase_admissibility.U-VLV.S2.saturation"]
    assert saturation.result == "pass" and saturation.value is not None
    assert abs(saturation.value) <= 1e-9, saturation.value
    balance = by_id["energy_balance.U-VLV"]
    assert balance.result == "pass" and balance.value is not None
    assert balance.tolerance is not None
    assert abs(balance.value) <= 1e-3 * balance.tolerance, balance.value
    # At x_final: T05b's registered judgement, unchanged.
    at_x_final = _at_x_final("INJ-B2p")
    _degenerate_judgement(at_x_final, entry["degeneracy_K"])
    unprojected = at_x_final["energy_balance.U-VLV"]
    assert unprojected.value is not None and unprojected.tolerance is not None
    # −1e-4 W, 10× inside τ_E; the double resolution of Ḣ(S2) ≈ 7e4 W is ~1e-11 W.
    assert error(unprojected.value, entry["energy_balance_U-VLV_W"]) <= 1e-9, unprojected.value
    assert abs(unprojected.value) * 10.0 <= unprojected.tolerance * (1.0 + 1e-6)


# -- §9.2: a degenerate stream outside any split, in its declared phase ---------------------


def _saturated_vapour_feed() -> dict[str, Any]:
    """Pure B vapour at 360 K, `P_r` → `U-PHF` (inlet `vapor`, `Q = 2 000 W`, `ΔP = 0`) → `S2`
    vapour, `S3` liquid (dormant at the root: the outlet is superheated vapour)."""
    return revision(
        "SAT-VAPOUR-FEED",
        [unit_instance("SYN-001-UL-C1", "U-PHF")],
        [Source("S1", "U-PHF", "inlet", "vapor", PURE_B, 360.0, P_R)],
        [],
        [Product("S2", ("U-PHF", "vapor"), "vapor"), Product("S3", ("U-PHF", "liquid"), "liquid")],
        [duty_pin("SPEC-phf-Q", "U-PHF", 2_000.0)],
    )


def test_s92_a_saturated_feed_is_read_in_its_declared_phase() -> None:
    document = _saturated_vapour_feed()
    binding = bind(document)
    plan, _ = plan_revision(binding, POLICY)
    assert isinstance(plan, ExecutionPlan), plan
    run = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=POLICY)
    assert run.outcome == "CONVERGED", run.message
    assert run.state is not None
    view = parse_revision(document)
    splits = lifted_splits(
        [(i.unit_id, i.model_id, i.wiring) for i in view.instances], view.components
    )
    found = degeneracy(view, splits, run.state, PROVIDER, CONTEXT)
    assert found.splits == {} and found.unlifted == frozenset()
    note = DECLARED_ENTHALPY_NOTE.format(stream="S1", phase="VAPOR")
    assert found.notes == {"S1": note}
    certificate = verify_revision(binding, document, run, solve_plan=plan.steps[-1].solve_plan)
    assert certificate.verification_status == "VERIFIED", [
        (c.id, c.value) for c in certificate.checks if c.result != "pass"
    ]
    by_id = _by_id(certificate)
    for name in (
        "energy_balance.U-PHF",
        "energy_balance.envelope",
        "phase_admissibility.U-PHF.inlet",
    ):
        qualification = by_id[name].independence_qualification
        assert qualification is not None and qualification.endswith(note), name
    assert by_id["energy_balance.U-PHF"].result == "pass"
    # What the fresh flash says instead: `LIQUID` at `K_B = 1`, the latent heat of 2 mol/s of B
    # (2 × 30 000 W) short — the energy balance would fail by `6e7 τ_E`.
    fresh = enthalpy_flow(PROVIDER, stream_of(run.state, "S1"), CONTEXT)
    assert found.enthalpy["S1"] - fresh == pytest.approx(60_000.0, abs=1e-6)


def test_s92_an_unlifted_degenerate_stream_makes_its_readers_unsupported() -> None:
    """The branch T05's S1 ruling makes unreachable: a `vapor_liquid` feed straight into a sink
    (parsed, never bound). The envelope, which reads it, is `unsupported` with the typed reason."""
    document = _saturated_vapour_feed()
    document["instances"] = [
        i for i in document["instances"] if i["id"] in ("U-FEED-0", "U-SINK-0")
    ]
    document["connections"] = [
        dict(c, to={"instance": "U-SINK-0", "port": "inlet"}, phase_capability="vapor_liquid")
        for c in document["connections"]
        if c["id"] == "S1"
    ]
    document["specifications"] = [s for s in document["specifications"] if "S1" in s["id"]]
    view = parse_revision(document)
    assert [i.phases for i in view.instances] == [{"outlet": None}, {"inlet": None}]
    state = {"S1.n.A": 0.0, "S1.n.B": 2.0, "S1.n.C": 0.0, "S1.T": 360.0, "S1.P": P_R}
    found = degeneracy(view, (), state, PROVIDER, CONTEXT)
    assert found == Degeneracy(unlifted=frozenset({"S1"}))
    checks = {
        c.id: c
        for c in revision_checks(
            view, (), state, provider=PROVIDER, context=CONTEXT, tolerances=KIND_TOLERANCE
        )
    }
    envelope = checks["energy_balance.envelope"]
    assert (envelope.result, envelope.reason) == (
        "unsupported",
        "temperature_degenerate_unlifted(S1)",
    )


# -- B14: inert on every registered certificate ----------------------------------------------


def _distances(view: RevisionView, state: Mapping[str, float]) -> list[float]:
    """The verifier's `δ` at every flowing stream's own `(n, T, P)` and every flowing split's feed
    at the split's `(T, P)` (T05b W0.5's items)."""
    splits = lifted_splits(
        [(i.unit_id, i.model_id, i.wiring) for i in view.instances], view.components
    )
    found: list[float] = []
    for stream in view.streams:
        n = tuple(state[flow_id(stream, c)] for c in view.components)
        if any(value > 0.0 for value in n):
            found.append(
                verifier_band.degeneracy_distance(
                    PROVIDER, n, state[temperature_id(stream)], state[pressure_id(stream)], CONTEXT
                )
            )
    for split in splits:
        n = tuple(state[column] for column in split.feed)
        if any(value > 0.0 for value in n):
            found.append(
                verifier_band.degeneracy_distance(
                    PROVIDER, n, state[split.temperature], state[split.pressure], CONTEXT
                )
            )
    return found


def _registered_minimum(case: str) -> float:
    return min(number(value) for value in REF["degeneracy_at_registered_states_K"][case].values())


def _registered_states() -> dict[str, tuple[dict[str, Any], Mapping[str, float], str | None]]:
    document = shaped_revision()
    binding, _, run = solve_w1d(document)
    assert run.state is not None
    start = initial_state(binding.flowsheet, binding.spec.variable_ids)
    assert isinstance(start, dict), start
    states: dict[str, tuple[dict[str, Any], Mapping[str, float], str | None]] = {
        "W1.d root": (document, run.state, "SYN-001-nominal"),
        "W1.d x0": (document, start, None),
    }
    for case in COUPLED_CASES:
        solved = solve_coupled(case)
        assert solved.run.state is not None
        coupled = yaml.safe_load((CASE_DIR / f"{case}.yaml").read_text())
        states[f"{case} root"] = (coupled, solved.run.state, case.removeprefix("SYN-001-UL-"))
    return states


def test_b14_no_registered_state_is_degenerate() -> None:
    """At W1.d's root and start and C1–C3's roots `degeneracy` finds nothing — so the table is
    exactly K04's there — and every `δ` is ≥ 1 K; at the roots the minimum is the twin's."""
    for label, (document, state, registered) in _registered_states().items():
        view = parse_revision(document)
        splits = lifted_splits(
            [(i.unit_id, i.model_id, i.wiring) for i in view.instances], view.components
        )
        assert degeneracy(view, splits, state, PROVIDER, CONTEXT) == Degeneracy(), label
        distances = _distances(view, state)
        assert distances and all(math.isfinite(d) for d in distances), label
        assert min(distances) >= 1.0, (label, min(distances))
        if registered is not None:
            assert abs(min(distances) - _registered_minimum(registered)) <= 1e-6, label
