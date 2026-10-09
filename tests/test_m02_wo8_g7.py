"""M02 WO-8.5: M01 spec §7's six registered tests of the PR units and gate G7 (a)–(e) (design note
§8, §10.1 G7, §14.2 *Gates as amended*, §14.3 C3; register R-230, R-254–R-258, R-282).

One test per rule of M01 §7 (with Amendment 3), then G7 (a)–(e) on solves through the revision
path under `T06-revision-v2`. Expectations are the provider's own flash and enthalpies (M01.A15–A22
verified them against 50-digit closed forms) and the rulings' exact statements. G7 (f) is WO-9's.

**G7 (a) as amended** (§14.3): F1's and F11's compositions are fed as vapour at 673.15 K into the
flash at their T and P, and certify VERIFIED. Fed at their own state they are two-phase feeds
outside the unit, whose declared-vapour inlet correctly fails (recorded).

**G7 (c) as amended** (§14.3 C3, R-282): the dew point is a bifurcation. At F4 exactly, E's and
Ldef's rows are proportional in (L, l_NH3), so the certificate is UNVERIFIED with regularity
RANK_DEFICIENT — the registered expectation, not a failure. F4 × (1 ± δ) records the near-dew
window on both sides: rcond_1 = 4.23e-4 δ on each, VERIFIED from δ ≈ 2.5e-4 on the VAPOR side
(the regularity screen's absolute limit, ‖J⁻¹‖₁ ≤ τ_min/(n ε)) and from δ ≈ 5.5e-4 on the
TWO_PHASE side (where the witness's central stencil first fits inside the liquid NH3 flow).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pytest
from conftest import REPO_ROOT, load_yaml
from m02_c1_support import connection, feed_specifications, instance, revision, specification
from m02_wo8_support import POLICY, Solved, bind, flash_revision, is_positive_zero, solve

from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.c1 import TAU_DEW
from openflowsheet.models.c1.flash import TPFlash
from openflowsheet.models.c1.phase import classify
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import execute_plan
from openflowsheet.orchestrator.region import _admissible, _kernel
from openflowsheet.orchestrator.revision import instances_of, plan_revision
from openflowsheet.orchestrator.splits import closure_types, lifted_splits
from openflowsheet.thermo import FlashRequest, PropertyRequest, StreamState
from openflowsheet.thermo.pr_c1 import COMPONENTS, PrC1Provider
from openflowsheet.verify import pr_c1
from openflowsheet.verify.certificate import SolutionCertificate, verify_revision

FLASH: Mapping[str, Any] = load_yaml(REPO_ROOT / "benchmarks" / "m01" / "reference_values.yaml")[
    "closed_form"
]["flash_states"]
PHASES: Mapping[str, Any] = load_yaml(REPO_ROOT / "benchmarks" / "m01" / "reference_values.yaml")[
    "closed_form"
]["phase_states"]
CONTEXT = EvaluationContext(model_version="m02-wo8-g7", constants_sha256="0" * 64)
PROVIDER = PrC1Provider()
P = 1.0e7
F1 = tuple(FLASH["F1"]["n_mol_s"])
F4 = tuple(FLASH["F4"]["n_mol_s"])
V1 = tuple(PHASES["V1"]["n_mol_s"])
PURE = (0.0, 0.0, 1.0, 0.0, 0.0)
LIGHT_ROWS = tuple(f"U:C1FL-equilibrium:{c}" for c in ("H2", "N2", "Ar", "CH4"))


def _certify(solved: Solved, document: Mapping[str, Any]) -> SolutionCertificate:
    assert solved.run.outcome == "CONVERGED", solved.run.message
    return verify_revision(
        solved.binding, document, solved.run, solve_plan=solved.plan.steps[-1].solve_plan
    )


def _h(n: tuple[float, ...], t: float, phase: Any, p: float = P) -> float:
    if all(v == 0.0 for v in n):
        return 0.0
    result = PROVIDER.evaluate_phase(
        PropertyRequest(
            state=StreamState(n=n, temperature=t, pressure=p), phase=phase, properties=("h",)
        ),
        CONTEXT,
    )
    assert result.status == "ok", result.message
    return sum(n) * result.values["h"]


def _rows(solved: Solved) -> dict[str, float]:
    """The compiled declaration's rows at the solved state."""
    spec = solved.binding.spec
    compiled = compile_problem(spec)
    context = EvaluationContext(
        model_version=compiled.metadata.model_version,
        constants_sha256=compiled.metadata.constants_sha256,
    )
    assert solved.run.state is not None
    x = np.array([solved.run.state[name] for name in spec.variable_ids], dtype=np.float64)
    result = compiled.residual(x, context)
    assert result.status == "ok" and result.values is not None
    return dict(zip(result.equation_ids, result.values, strict=True))


def _attempts(solved: Solved) -> list[Any]:
    region = solved.run.steps[-1].detail
    return [(a.signature, a.outcome, a.iterations, a.reason) for a in region.attempts]


# == M01 spec §7: one test per rule =============================================================


def _split_and_state(n: tuple[float, ...], t: float) -> tuple[Any, dict[str, float]]:
    binding = bind(flash_revision(F1, 268.15))
    (split,) = lifted_splits(instances_of(binding.flowsheet), COMPONENTS)
    state = dict.fromkeys((*split.vapor, *split.liquid, split.vapor_total, split.liquid_total), 1.0)
    state.update(zip(split.feed, n, strict=True))
    state[split.temperature], state[split.pressure] = t, P
    return split, state


def test_m01_s7_rule_1_the_lattice_and_liquids_exclusion_with_light_gas() -> None:
    """With light gas flowing the kernel answers VAPOR or TWO_PHASE, never LIQUID, and LIQUID is
    inadmissible; LIQUID is admissible only for a feed without light gas (whose flash the unit
    refuses, the pure-NH3 route being deferred, R-230)."""
    for fid, state in FLASH.items():
        n = tuple(state["n_mol_s"])
        if sum(n) == 0.0 or all(n[k] == 0.0 for k in (0, 1, 3, 4)):
            continue
        split, values = _split_and_state(n, state["T_K"])
        values[split.pressure] = state["P_Pa"]
        regime, _ = _kernel(PROVIDER, CONTEXT, split, values)
        assert regime in ("VAPOR", "TWO_PHASE"), fid
        ok, _ = _admissible(PROVIDER, CONTEXT, split, "LIQUID", values, 0.0)
        assert ok is False, fid
    split, values = _split_and_state(PURE, 268.15)
    assert _admissible(PROVIDER, CONTEXT, split, "LIQUID", values, 0.0) == (True, 0.0)
    unit = TPFlash("U", PROVIDER, 268.15, P, CONTEXT)
    refused = unit.evaluate(
        {"inlet": (StreamState(n=PURE, temperature=268.15, pressure=P),)}, CONTEXT
    )
    assert refused.status == "unsupported"
    assert refused.message.startswith("pure_nh3_flash_unsupported")


def test_m01_s7_rule_2_the_rows_structural_zeros_and_es_division_free_form() -> None:
    """Amendment 3's E is exactly 0.0 on VAPOR (L = l = 0) and on LIQUID (V = v = 0), equals
    `L V (y φ^V − φ^L)` at a TWO_PHASE state, and the light-gas zero rows read their own column."""
    binding = bind(flash_revision(F1, 268.15))
    spec = binding.spec
    compiled = compile_problem(spec)
    context = EvaluationContext(
        model_version=compiled.metadata.model_version,
        constants_sha256=compiled.metadata.constants_sha256,
    )

    def rows(state: Mapping[str, float]) -> dict[str, float]:
        x = np.array([state[name] for name in spec.variable_ids], dtype=np.float64)
        result = compiled.residual(x, context)
        assert result.status == "ok" and result.values is not None, result.message
        return dict(zip(result.equation_ids, result.values, strict=True))

    def state(
        feed: tuple[float, ...],
        vapor: tuple[float, ...],
        liquid: tuple[float, ...],
        t: float,
        feed_t: float | None = None,
    ) -> dict[str, float]:
        values: dict[str, float] = {}
        for stream, flows, temperature in (
            ("S1", feed, t if feed_t is None else feed_t),
            ("S2", vapor, t),
            ("S3", liquid, t),
        ):
            values.update({f"{stream}.n.{c}": v for c, v in zip(COMPONENTS, flows, strict=True)})
            values[f"{stream}.T"], values[f"{stream}.P"] = temperature, P
        values["S2.N"], values["S3.N"] = float(sum(vapor)), float(sum(liquid))
        values["U.Q"] = 0.0
        return values

    zero = (0.0,) * 5
    on_vapour = rows(state(V1, V1, zero, 673.15))
    assert on_vapour["U:C1FL-equilibrium:NH3"] == 0.0
    on_liquid = rows(state(PURE, zero, PURE, 268.15, feed_t=420.0))
    assert on_liquid["U:C1FL-equilibrium:NH3"] == 0.0
    flashed = PROVIDER.flash(
        FlashRequest(state=StreamState(n=F1, temperature=268.15, pressure=P)), CONTEXT
    )
    assert flashed.vapor and flashed.liquid
    two = rows(state(F1, flashed.vapor.n, flashed.liquid.n, 268.15))
    v, liq = flashed.vapor.n, flashed.liquid.n
    phi_v = PROVIDER.evaluate_phase(
        PropertyRequest(state=flashed.vapor, phase="VAPOR", properties=("lnphi_NH3",)), CONTEXT
    ).values["lnphi_NH3"]
    phi_l = PROVIDER.evaluate_phase(
        PropertyRequest(state=flashed.liquid, phase="LIQUID", properties=("lnphi_NH3",)), CONTEXT
    ).values["lnphi_NH3"]
    big_v, big_l = sum(v), sum(liq)
    expected = big_l * big_v * (v[2] / big_v * np.exp(phi_v) - np.exp(phi_l))
    assert abs(two["U:C1FL-equilibrium:NH3"] - expected) <= 1e-12
    assert abs(two["U:C1FL-equilibrium:NH3"]) <= 9.3e-8  # K04's molar_flow_squared tolerance
    # Off the root the row is nonzero: it is not satisfied identically on TWO_PHASE.
    off = rows(state(F1, flashed.vapor.n, flashed.liquid.n, 269.15))
    assert abs(off["U:C1FL-equilibrium:NH3"]) > 1e-4
    for row in LIGHT_ROWS:
        assert two[row] == 0.0
    from openflowsheet.graph.trace import trace_declaration
    from openflowsheet.orchestrator.execution import declaration_identity

    model_version, constants = declaration_identity(spec)
    declaration = trace_declaration(
        spec, model_version=model_version, constants_sha256=constants, row_units=binding.row_units
    )
    for row, c in zip(LIGHT_ROWS, ("H2", "N2", "Ar", "CH4"), strict=True):
        assert set(declaration.rows[row].columns) == {f"S3.n.{c}"}


def test_m01_s7_rule_3_the_admissibility_screens_at_the_dew_band() -> None:
    """VAPOR is admissible iff the flash is VAPOR or TWO_PHASE with `l_NH3 ≤ τ_dew n_tot`."""
    split, _ = _split_and_state(F4, 268.15)
    for delta, expected in ((0.0, True), (8.1e-10, True), (3.2e-9, False), (1e-5, False)):
        n = (*F4[:2], F4[2] * (1.0 + delta), *F4[3:])
        _, values = _split_and_state(n, 268.15)
        ok, value = _admissible(PROVIDER, CONTEXT, split, "VAPOR", values, 0.0)
        regime, band_value, _ = classify(PROVIDER, CONTEXT, n, 268.15, P)
        assert ok is expected and value == band_value, delta
        assert (value <= TAU_DEW) is expected


def test_m01_s7_rule_4_a_light_gas_stream_is_never_temperature_degenerate() -> None:
    """The flash is TP-type (no PH closure, so the band route is never taken), the region records
    no `closure_route`, and the certificate carries no `.saturation` check and no degenerate or
    unresolved routing."""
    document = flash_revision(F1, 268.15, feed_temperature=673.15)
    solved = solve(document)
    assert closure_types(solved.binding.flowsheet.units()) == {"U": "TP"}
    messages = [event.message for event in solved.run.trace.events]
    assert not any("closure_route(" in message for message in messages)
    certificate = _certify(solved, document)
    assert certificate.verification_status == "VERIFIED", certificate.limitations
    for check in certificate.checks:
        assert not check.id.endswith(".saturation"), check.id
        assert check.reason not in ("temperature_degenerate", "fresh_flash_unresolved"), check.id


def test_m01_s7_rule_5_zero_flow() -> None:
    """ADR 0012 D4 (c): a dormant feed opens ZERO_FLOW; every lifted flow `+0.0`, Q `+0.0`."""
    document = flash_revision((0.0,) * 5, 268.15)
    solved = solve(document)
    assert solved.run.outcome == "CONVERGED"
    assert [signature for signature, *_ in _attempts(solved)] == [(("U", "ZERO_FLOW"),)]
    state = solved.run.state
    assert state is not None
    for name in (*(f"S{s}.n.{c}" for s in (2, 3) for c in COMPONENTS), "S2.N", "S3.N", "U.Q"):
        assert is_positive_zero(state[name]), name


def test_m01_s7_rule_6_the_verifiers_fresh_flash_of_a_vapour_at_its_own_dew_point() -> None:
    """F1's vapour product is a vapour at its own dew point: a fresh flash of it is VAPOR or
    TWO_PHASE with an O(ε) liquid, read as VAPOR (D2's analogue) — its fresh-flash enthalpy is
    the vapour's, bitwise, and the τ_dew test passes."""
    flashed = PROVIDER.flash(
        FlashRequest(state=StreamState(n=F1, temperature=268.15, pressure=P)), CONTEXT
    )
    assert flashed.vapor is not None
    vapour = flashed.vapor
    again = PROVIDER.flash(FlashRequest(state=vapour), CONTEXT)
    assert again.phase_signature in ("VAPOR", "TWO_PHASE")
    regime, value = pr_c1.band(PROVIDER, CONTEXT, vapour.n, 268.15, P, COMPONENTS)
    assert regime == "VAPOR" and value <= TAU_DEW
    assert pr_c1.enthalpy_flow(PROVIDER, vapour, CONTEXT, COMPONENTS) == 0.0 + _h(
        vapour.n, 268.15, "VAPOR"
    )


# == G7 (a)–(e) ===================================================================================


#: G7 (a) as amended (§14.3): the registered compositions are fed as vapour at this temperature.
VAPOUR_FEED_T = 673.15


@pytest.mark.parametrize("fid", ["F1", "F11"])
def test_g7a_the_flash_at_a_registered_two_phase_state(fid: str) -> None:
    """The registered composition fed as vapour at 673.15 K into the flash at the registered T
    and P (§14.3 "G7 (a) amended"): the EO solve's vapour fraction and `y*_NH3` agree with
    `pr-c1-v1.flash` within 1e-9 relative; material closure ≤ 1e-12 n_tot; energy closure ≤ 1e-9
    |Ḣ_in|; the certificate `VERIFIED`. The start is the exact split, so no Newton iteration."""
    registered = FLASH[fid]
    n, t, p = tuple(registered["n_mol_s"]), registered["T_K"], registered["P_Pa"]
    document = flash_revision(n, t, p, feed_temperature=VAPOUR_FEED_T)
    solved = solve(document)
    assert solved.run.outcome == "CONVERGED"
    state = solved.run.state
    assert state is not None
    flashed = PROVIDER.flash(
        FlashRequest(state=StreamState(n=n, temperature=t, pressure=p)), CONTEXT
    )
    assert flashed.vapor_fraction is not None
    total = sum(n)
    fraction = state["S2.N"] / total
    y_star = state["S2.n.NH3"] / state["S2.N"]
    assert abs(fraction - flashed.vapor_fraction) <= 1e-9 * flashed.vapor_fraction
    assert abs(y_star - flashed.k_values["NH3"]) <= 1e-9 * flashed.k_values["NH3"]
    assert abs(fraction - registered["vapor_fraction"]) <= 1e-9 * registered["vapor_fraction"]
    assert abs(y_star - registered["y_star"]) <= 1e-9 * registered["y_star"]
    material = max(
        abs(state[f"S1.n.{c}"] - state[f"S2.n.{c}"] - state[f"S3.n.{c}"]) for c in COMPONENTS
    )
    assert material <= 1e-12 * total
    vapour = tuple(state[f"S2.n.{c}"] for c in COMPONENTS)
    liquid = tuple(state[f"S3.n.{c}"] for c in COMPONENTS)
    h_in = _h(n, VAPOUR_FEED_T, "VAPOR", p)
    energy = state["U.Q"] - (_h(vapour, t, "VAPOR", p) + _h(liquid, t, "LIQUID", p) - h_in)
    assert abs(energy) <= 1e-9 * abs(h_in)
    certificate = _certify(solved, document)
    assert certificate.verification_status == "VERIFIED", [
        (c.id, c.result) for c in certificate.checks if c.result != "pass"
    ]


@pytest.mark.parametrize("fid", ["F1", "F11"])
def test_g7a_fed_at_its_own_state_the_declared_vapour_inlet_fails(fid: str) -> None:
    """Recorded (§14.3 "G7 (a) amended"): the registered state fed at its own T and P is a
    two-phase feed outside the unit, so the flash's declared-vapour inlet fails
    `phase_admissibility.U.inlet` and the certificate is `FAILED` — correctly."""
    registered = FLASH[fid]
    n, t, p = tuple(registered["n_mol_s"]), registered["T_K"], registered["P_Pa"]
    document = flash_revision(n, t, p)
    certificate = _certify(solve(document), document)
    failed = sorted(c.id for c in certificate.checks if c.result == "fail")
    assert certificate.verification_status == "FAILED"
    assert "phase_admissibility.U.inlet" in failed


def test_g7b_a_vapour_feed() -> None:
    """V1 at 673.15 K: regime VAPOR, `n_L,NH3 = 0` exactly, every `C1FL-equilibrium` row exactly
    0.0 at the root, the certificate `VERIFIED`."""
    document = flash_revision(V1, 673.15)
    solved = solve(document)
    assert [signature for signature, *_ in _attempts(solved)] == [(("U", "VAPOR"),)]
    state = solved.run.state
    assert state is not None
    assert is_positive_zero(state["S3.n.NH3"]) and is_positive_zero(state["S3.N"])
    rows = _rows(solved)
    for c in COMPONENTS:
        assert rows[f"U:C1FL-equilibrium:{c}"] == 0.0, c
    certificate = _certify(solved, document)
    assert certificate.verification_status == "VERIFIED", certificate.limitations
    (dew,) = [c for c in certificate.checks if c.id == "phase_admissibility.U.S1.dew"]
    assert dew.result == "pass" and dew.value == 0.0


def _f4(delta: float = 0.0, feed_temperature: float = 300.0) -> tuple[dict[str, Any], Solved]:
    n = (*F4[:2], F4[2] * (1.0 + delta), *F4[3:])
    document = flash_revision(n, 268.15, feed_temperature=feed_temperature)
    return document, solve(document)


def test_g7c_a_feed_at_its_own_dew_point_opens_vapour_and_is_unverified_rank_deficient() -> None:
    """F4 (§14.3 C3, R-282): the kernel opens VAPOR, the solve converges there, `.dew` is 0.0
    (≤ τ_dew / 10); the certificate is UNVERIFIED with regularity RANK_DEFICIENT and a
    `rank_limitation` — the registered expectation at a dew point, where E's and Ldef's rows are
    proportional in (L, l_NH3) (build log D41)."""
    document, solved = _f4()
    assert _attempts(solved) == [((("U", "VAPOR"),), "CONVERGED", 0, "")]
    state = solved.run.state
    assert state is not None
    assert all(is_positive_zero(state[f"S3.n.{c}"]) for c in COMPONENTS)
    certificate = _certify(solved, document)
    (dew,) = [c for c in certificate.checks if c.id == "phase_admissibility.U.S1.dew"]
    assert dew.result == "pass" and dew.value == 0.0 and dew.value <= TAU_DEW / 10
    assert certificate.regularity is not None
    assert certificate.regularity.status == "RANK_DEFICIENT"
    assert certificate.regularity.rcond_1 is not None and certificate.regularity.rcond_1 < 1e-15
    assert certificate.verification_status == "UNVERIFIED"
    assert [item.detail for item in certificate.limitations if item.kind == "rank_limitation"] == [
        {"status": "RANK_DEFICIENT", "reason": None}
    ]


@pytest.mark.parametrize("delta", [1e-8, 1e-7, 1e-5])
def test_g7c_k18_just_past_the_band_is_recorded(delta: float) -> None:
    """K18: F4 × (1 + δ), `l/n_tot ≈ 0.0616 δ`, past τ_dew: the outcome, `rcond_1` and the verdict,
    recorded (design note §14.2 G7 (c); §14.3 C3: δ = 1e-5 UNVERIFIED). Measured: TWO_PHASE,
    CONVERGED in 0 iterations, ILL_CONDITIONED (`relative`, rcond_1 < τ_ill) with rcond_1 ≈ 4.2e-4
    δ, UNVERIFIED. Never handled by widening τ_dew."""
    document, solved = _f4(delta)
    assert _attempts(solved) == [((("U", "TWO_PHASE"),), "CONVERGED", 0, "")]
    certificate = _certify(solved, document)
    assert certificate.regularity is not None
    rcond = certificate.regularity.rcond_1
    assert rcond is not None and rcond == pytest.approx(RCOND_PER_DELTA * delta, rel=1e-3)
    assert certificate.regularity.status == "ILL_CONDITIONED"
    assert certificate.regularity.ill_conditioned_reason == "relative"
    assert certificate.verification_status == "UNVERIFIED"
    (closure,) = [c for c in certificate.checks if c.id == "phase_admissibility.U.S1.closure"]
    assert closure.result == "pass"


#: The measured near-dew law at F4 (§14.3 C3): rcond_1 = 4.2316e-4 δ on both sides of the dew
#: point, δ the relative NH3 excess (TWO_PHASE) or deficit (VAPOR) against the dew composition.
RCOND_PER_DELTA = 4.2316e-4


def test_g7c_at_delta_1e_4_two_phase_is_recorded_unverified() -> None:
    """§14.3 C3 expected δ = 1e-4 VERIFIED near threshold (τ_ill alone). Measured: UNVERIFIED, by
    two registered limits τ_ill does not include. rcond_1 = 4.23e-8 passes τ_ill = 1e-8, but
    ‖J⁻¹‖₁ = 4.66e6 exceeds the screen's absolute limit τ_min/(n ε) = 1.88e6 (n = 24;
    ILL_CONDITIONED, `absolute`). And the liquid NH3 flow, 6.2e-6 n_tot = 5.5e-6 mol/s, is
    below one witness step (1e-5 × 3 mol/s), so the central stencil leaves the domain there."""
    document, solved = _f4(1e-4)
    assert _attempts(solved) == [((("U", "TWO_PHASE"),), "CONVERGED", 0, "")]
    certificate = _certify(solved, document)
    regularity = certificate.regularity
    assert regularity is not None and regularity.rcond_1 is not None
    assert regularity.rcond_1 == pytest.approx(RCOND_PER_DELTA * 1e-4, rel=1e-3)
    assert regularity.rcond_1 > 1e-8
    assert (regularity.status, regularity.ill_conditioned_reason) == ("ILL_CONDITIONED", "absolute")
    assert regularity.inverse_one_norm_threshold is not None
    assert regularity.inverse_one_norm_estimate is not None
    assert regularity.inverse_one_norm_estimate > regularity.inverse_one_norm_threshold
    witness = [
        (c.result, c.reason) for c in certificate.checks if c.category == "derivative_witness"
    ]
    assert witness == [("unsupported", "witness_stencil_invalid_trial_state(S3.n.NH3)")] * 2
    assert certificate.verification_status == "UNVERIFIED"


def test_g7c_at_delta_1e_3_two_phase_is_verified_and_not_near_threshold() -> None:
    """§14.3 C3: F4 × (1 + 1e-3) is VERIFIED, with no near-threshold flag (the gate's stop
    condition: were it not, the work would go to the design lane)."""
    document, solved = _f4(1e-3)
    assert _attempts(solved) == [((("U", "TWO_PHASE"),), "CONVERGED", 0, "")]
    certificate = _certify(solved, document)
    assert certificate.verification_status == "VERIFIED", certificate.limitations
    regularity = certificate.regularity
    assert regularity is not None and regularity.status == "NO_RANK_LOSS_DETECTED"
    assert regularity.rcond_1 == pytest.approx(RCOND_PER_DELTA * 1e-3, rel=1e-3)
    assert not any(item.kind == "near_threshold" for item in certificate.limitations)
    assert not any(check.near_threshold for check in certificate.checks)


@pytest.mark.parametrize(
    ("delta", "status", "reason", "verdict"),
    [
        (1e-6, "ILL_CONDITIONED", "relative", "UNVERIFIED"),
        (1e-4, "ILL_CONDITIONED", "absolute", "UNVERIFIED"),
        (1e-2, "NO_RANK_LOSS_DETECTED", None, "VERIFIED"),
    ],
)
def test_g7c_the_vapour_side_law_is_recorded(
    delta: float, status: str, reason: str | None, verdict: str
) -> None:
    """§14.3 C3: F4 × (1 − δ), an undersaturated vapour: VAPOR, `.dew` 0.0, and rcond_1 =
    4.23e-4 δ — the TWO_PHASE side's law mirrored (within 8e-4 relative at δ = 1e-2)."""
    n = (*F4[:2], F4[2] * (1.0 - delta), *F4[3:])
    document = flash_revision(n, 268.15, feed_temperature=300.0)
    solved = solve(document)
    assert [signature for signature, *_ in _attempts(solved)] == [(("U", "VAPOR"),)]
    certificate = _certify(solved, document)
    (dew,) = [c for c in certificate.checks if c.id == "phase_admissibility.U.S1.dew"]
    assert dew.result == "pass" and dew.value == 0.0
    regularity = certificate.regularity
    assert regularity is not None and regularity.rcond_1 is not None
    assert regularity.rcond_1 == pytest.approx(RCOND_PER_DELTA * delta, rel=1e-3)
    assert (regularity.status, regularity.ill_conditioned_reason) == (status, reason)
    assert certificate.verification_status == verdict


@pytest.mark.parametrize(
    ("delta", "verdict"),
    [(-2.4e-4, "UNVERIFIED"), (-2.6e-4, "VERIFIED"), (5.3e-4, "UNVERIFIED"), (5.7e-4, "VERIFIED")],
)
def test_g7c_the_near_dew_window_edges_as_the_manifest_states_them(
    delta: float, verdict: str
) -> None:
    """The window's edges, bisected at F4 and stated in `c1.tp_flash`'s manifest: on the VAPOR
    side (δ < 0) VERIFIED from |δ| = 2.483e-4, where ‖J⁻¹‖₁ meets the absolute limit; on the
    TWO_PHASE side from δ = 5.480e-4 (L/n_tot = 3.37e-5), where the liquid NH3 flow reaches one
    witness step. Each edge is asserted 3-4 % to either side."""
    document, solved = _f4(delta)
    assert _certify(solved, document).verification_status == verdict


@pytest.mark.parametrize(
    ("delta", "verdict"),
    [(1e-4, "UNVERIFIED"), (-1e-4, "UNVERIFIED"), (1e-3, "VERIFIED"), (-1e-2, "VERIFIED")],
)
def test_g7c_as_amended_by_r282(delta: float, verdict: str) -> None:
    """G7 (c) as amended (design note §14.4 D1, R-282 amended): at F4 × (1 + δ) the certificate is
    UNVERIFIED at δ = ±1e-4, inside the measured window on both sides, and VERIFIED at δ = +1e-3
    (TWO_PHASE) and δ = −1e-2 (VAPOR). The edges are the bisection test's above."""
    document, solved = _f4(delta)
    regime = "TWO_PHASE" if delta > 0 else "VAPOR"
    assert [signature for signature, *_ in _attempts(solved)] == [(("U", regime),)]
    assert _certify(solved, document).verification_status == verdict


def test_g7c_the_manifest_states_the_window_at_the_measured_state() -> None:
    """R-282 amended: `c1.tp_flash`'s manifest states the window "at the measured state", with
    the two bisected edges the test above asserts (|δ| = 2.5e-4 VAPOR, L/n_tot = 3.4e-5
    TWO_PHASE, δ = 5.5e-4)."""
    manifest = TPFlash("U", PROVIDER, 268.15, P, CONTEXT).manifest()
    limitations = manifest["validity"]["limitations"]
    (window,) = [text for text in limitations if "near-dew window" in text]
    assert "R-282 as amended" in window and "At the measured state" in window
    assert "VAPOR side the certificate is VERIFIED from delta = 2.5e-4" in window
    assert "TWO_PHASE side from L/n_tot = 3.4e-5 (delta = 5.5e-4)" in window
    assert "tau_dew does not move" in window


def test_g7d_a_zero_flow_feed() -> None:
    """ADR 0012 D4 (c)'s forms, Q = +0.0, and the certificate `VERIFIED`."""
    document = flash_revision((0.0,) * 5, 268.15)
    solved = solve(document)
    state = solved.run.state
    assert state is not None and is_positive_zero(state["U.Q"])
    certificate = _certify(solved, document)
    assert certificate.verification_status == "VERIFIED", certificate.limitations
    admissibility = [c for c in certificate.checks if c.category == "phase_admissibility"]
    assert {c.result for c in admissibility} == {"not_applicable"}


def test_g7e_a_pure_nh3_feed_is_refused_by_the_flash() -> None:
    """Through the solve: the traversal stops at the flash with `pure_nh3_flash_unsupported`."""
    document = flash_revision(PURE, 268.15)
    traversed = bind(document).flowsheet.traverse({})
    assert (traversed.status, traversed.failed_unit) == ("unsupported", "U")
    assert traversed.code.startswith("pure_nh3_flash_unsupported")
    solved = solve(document)
    assert solved.run.outcome == "INITIALIZATION_FAILED"


#: G7 (e): y_NH3 = 0.15, the rest F1's light gases in proportion.
Y15 = (0.85 * 0.6 / 0.835, 0.85 * 0.2 / 0.835, 0.15, 0.85 * 0.015 / 0.835, 0.85 * 0.02 / 0.835)


def _heater(outlet_temperature: float) -> dict[str, Any]:
    return revision(
        [
            instance("F", "c1.feed_source"),
            instance("H", "c1.tp_heater"),
            instance("K", "c1.product_sink"),
        ],
        [
            connection("S1", ("F", "outlet"), ("H", "inlet")),
            connection("S2", ("H", "outlet"), ("K", "inlet")),
        ],
        [
            *feed_specifications("S1", Y15, 673.15, P),
            specification(
                "SPEC-S2-T", "connection", "S2", "state.T", outlet_temperature, "temperature"
            ),
        ],
    )


def test_g7e_a_converged_state_with_the_heater_outlet_two_phase_fails_the_certificate() -> None:
    """The heater to 253.15 K, 1e7 Pa at y_NH3 = 0.15: its evaluate refuses (WO-8.2), so the EO
    solve is opened from a constructed start (`user_start`: the outlet at 253.15 K, Q its vapour
    enthalpy change). It converges — every row is vapour-written — and the certificate fails
    `phase_admissibility.H.outlet` with the outlet's liquid NH3 fraction: CONVERGED, FAILED (B16:
    no solve-time screen and no new outcome)."""
    document = _heater(253.15)
    binding = bind(document)
    plan, _ = plan_revision(binding, POLICY)
    assert isinstance(plan, ExecutionPlan)
    start: dict[str, float] = {}
    for stream, temperature in (("S1", 673.15), ("S2", 253.15)):
        start.update({f"{stream}.n.{c}": v for c, v in zip(COMPONENTS, Y15, strict=True)})
        start[f"{stream}.T"], start[f"{stream}.P"] = temperature, P
    start["H.Q"] = _h(Y15, 253.15, "VAPOR") - _h(Y15, 673.15, "VAPOR")
    run = execute_plan(
        plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=POLICY, user_start=start
    )
    assert run.outcome == "CONVERGED", run.message
    certificate = verify_revision(binding, document, run, solve_plan=plan.steps[-1].solve_plan)
    assert certificate.verification_status == "FAILED"
    (outlet,) = [c for c in certificate.checks if c.id == "phase_admissibility.H.outlet"]
    _, value, _ = classify(PROVIDER, CONTEXT, Y15, 253.15, P)
    assert outlet.result == "fail" and outlet.value == value and value > TAU_DEW
    # The fresh flash also reads the two-phase outlet's real enthalpy, so the energy balances
    # fail with it (measured: 2323.0 W against the vapour enthalpy the duty row wrote).
    assert [c.id for c in certificate.checks if c.result == "fail"] == [
        "energy_balance.H",
        "energy_balance.envelope",
        "phase_admissibility.H.outlet",
    ]
