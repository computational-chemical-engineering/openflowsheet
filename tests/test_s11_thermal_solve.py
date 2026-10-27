"""S11 WO-C6: the `thermal.*` flowsheets solved through the region (S11 units design §5.2 C6, §6.1).

The spike first (Q18): does the region backtrack on a block's `invalid_trial_state` during a Newton
trial? A duty-mode heater with a liquid outlet, started cold, takes a full Newton step past T_sat;
the liquid block refuses it (`phase_not_stable`, a `DomainError`), the compiled boundary reports
`invalid_trial_state`, and the Newton core halves the step. TH-V1 (valve → drum) is the first
registered case through the region. The seven models are registered in monkeypatched tables
(`s11_thermal_support`), as I1b has not registered them yet; "VERIFIED" here is the C5 check set
(`test_s11_thermal_verifier.verifier_checks`, the I1b hook's assembly) at x_final, every check
computed and passing.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from m02_c1_support import connection, quantity
from s11_thermal_support import CASES, _water, committed_case, solve
from test_s11_thermal_binding import duty, feed, instance, outlet_temperature, register
from test_s11_thermal_verifier import evaluated_state, verifier_checks

from openflowsheet.models.revision_flowsheet import parse_revision
from openflowsheet.orchestrator.executor import PlanResult
from openflowsheet.orchestrator.splits import DORMANCY_RULES, DormancyRule
from openflowsheet.thermo import PropertyProvider
from openflowsheet.verify import CheckResult
from openflowsheet.verify.checks import KIND_TOLERANCE

TAU_E = KIND_TOLERANCE["heat_rate"]
TAU_FLOW = KIND_TOLERANCE["molar_flow"]
TAU_T = KIND_TOLERANCE["temperature"]


@pytest.fixture
def registered(monkeypatch: pytest.MonkeyPatch) -> None:
    register(monkeypatch)


def accepted_steps(run: PlanResult) -> int:
    return sum(1 for event in run.trace.events if event.kind == "step_accepted")


def all_pass(
    document: Mapping[str, Any],
    state: Mapping[str, float],
    provider: PropertyProvider | None = None,
) -> list[CheckResult]:
    """Every C5 check at `state` is computed and passes (the column-free `independent_split`
    rows are `not_applicable` by design, C5's A64 test)."""
    checks = verifier_checks(parse_revision(document), state, provider)
    assert checks
    for check in checks:
        if check.category == "independent_split":
            assert (check.result, check.reason) == ("not_applicable", "temperature_degenerate")
            continue
        assert check.result == "pass", (check.id, check.result, check.value, check.reason)
    return checks


@pytest.mark.parametrize("name", sorted(CASES))
def test_the_committed_case_is_the_generated_one(name: str) -> None:
    """`benchmarks/s11/thermal/<name>.json` is `CASES[name]()` (regenerate with
    `python tests/s11_thermal_support.py`)."""
    assert committed_case(name) == CASES[name]()


# -- Q18: the spike --------------------------------------------------------------------------------


def _heater(specification: dict[str, Any]) -> dict[str, Any]:
    """Liquid H2O at 1 MPa, 300 K → heater (liquid outlet) → sink."""
    return _water(
        "S11-C6-SPIKE",
        [
            instance("F", "syn001.feed_source"),
            instance("H", "thermal.heater"),
            instance("K", "syn001.product_sink"),
        ],
        [
            connection("S1", ("F", "outlet"), ("H", "inlet"), "liquid"),
            connection("S2", ("H", "outlet"), ("K", "inlet"), "liquid"),
        ],
        [*feed("S1", "H2O", 300.0, 1.0e6), specification],
    )


def test_q18_the_region_backtracks_on_a_blocks_invalid_trial_state(registered: None) -> None:
    """Q18: the duty that takes 300 K liquid to 452.5 K at 1 MPa (T_sat 453.03 K), solved from a
    start with the outlet at 300 K. The first full Newton step lands above T_sat; the trial is
    rejected `invalid_trial` with the liquid block's `phase_not_stable`, the step halves, and
    the solve converges to the T-mode root."""
    _, by_temperature = solve(_heater(outlet_temperature("H", 452.5)))
    assert by_temperature.outcome == "CONVERGED"
    assert by_temperature.state is not None
    q = by_temperature.state["H.Q"]
    document = _heater(duty("H", q))
    start = dict(by_temperature.state)
    start["S2.T"] = 300.0
    _, run = solve(document, user_start=start)
    assert run.outcome == "CONVERGED", run.message
    assert run.state is not None
    rejected = [
        event
        for event in run.trace.events
        if event.kind == "trial" and event.rejection_reason == "invalid_trial"
    ]
    assert rejected, "no trial was rejected: the start no longer probes Q18"
    for event in rejected:
        assert event.alpha == 1.0
        assert "phase_not_stable" in event.message and "LIQUID" in event.message
    halved = [e for e in run.trace.events if e.kind == "step_accepted" and e.alpha == 0.5]
    assert len(halved) == len(rejected)
    assert abs(run.state["S2.T"] - 452.5) <= TAU_T


# -- TH-V1 -----------------------------------------------------------------------------------------


def test_th_v1_valve_to_drum_converges_and_verifies(registered: None) -> None:
    """TH-V1 through the region from the traversal start: CONVERGED; the state is the units' own
    sequential evaluation; every C5 check passes; Ḣ_S1 = Ḣ_S3 + Ḣ_S4 (Q = 0) within τ_E."""
    document = committed_case("TH-V1")
    binding, run = solve(document)
    assert run.outcome == "CONVERGED", run.message
    assert run.state is not None
    state = dict(run.state)
    sequential = evaluated_state(document)
    for column in binding.spec.variable_ids:
        kind = binding.spec.variable_kinds[column]
        assert abs(state[column] - sequential[column]) <= KIND_TOLERANCE[kind], column
    checks = {check.id: check for check in all_pass(document, state)}
    for stream in ("S2", "S3", "S4"):
        assert checks[f"phase_admissibility.stream.{stream}.saturation"].result == "pass"
        assert checks[f"phase_admissibility.stream.{stream}.fraction"].result == "pass"
    assert state["S3.sat.L"] == 0.0 and state["S4.sat.V"] == 0.0
    beta = state["S2.sat.V"] / state["S2.n.H2O"]
    assert 0.0 < beta < 1.0
    assert abs(state["S3.n.H2O"] - beta * state["S1.n.H2O"]) <= TAU_FLOW


# -- §4.9: the dormancy registry, and S11.A62 ------------------------------------------------------


def test_the_dormancy_registry_holds_the_thermal_entries() -> None:
    """§4.9, literally: one rule per single-phase outlet whose temperature no row reads at
    dormancy; every other configuration a key with no rule; `thermal.flash` absent."""
    forms = ("LIQUID", "VAPOR", "SATURATED")
    expected: dict[tuple[str, str | None], tuple[DormancyRule, ...]] = {
        **{("thermal.heater", f"{m}:{f}"): () for m in ("T", "duty", "quality") for f in forms},
        **{
            (model, f): ()
            for model in (
                "thermal.valve",
                "thermal.mixer",
                "thermal.pump",
                "thermal.compressor",
                "thermal.turbine",
            )
            for f in forms
        },
    }
    for key, swapped, form in (
        (("thermal.heater", "duty:LIQUID"), "TH-energy", "LIQUID"),
        (("thermal.heater", "duty:VAPOR"), "TH-energy", "VAPOR"),
        (("thermal.valve", "LIQUID"), "TV-energy", "LIQUID"),
        (("thermal.valve", "VAPOR"), "TV-energy", "VAPOR"),
        (("thermal.mixer", "LIQUID"), "TM-energy", "LIQUID"),
        (("thermal.mixer", "VAPOR"), "TM-energy", "VAPOR"),
        (("thermal.pump", "LIQUID"), "TPU-energy", "LIQUID"),
        (("thermal.compressor", "VAPOR"), "TCO-energy", "VAPOR"),
        (("thermal.turbine", "VAPOR"), "TTU-energy", "VAPOR"),
    ):
        expected[key] = (DormancyRule("outlet", "inlet", swapped, None, form),)
    thermal = {key: rules for key, rules in DORMANCY_RULES.items() if key[0].startswith("thermal.")}
    assert thermal == expected


def _dormant_heater(q: float) -> dict[str, Any]:
    """F → splitter (fraction 0) → recycle → heater (duty `q`, liquid outlet) → sink; the purge to
    a sink. The heater's inlet is exactly dormant."""
    return _water(
        "S11-C6-A62",
        [
            instance("F", "syn001.feed_source"),
            instance(
                "SP",
                "syn001.stream_splitter",
                {"split_fraction": quantity(0.0, "1", "dimensionless", [0] * 7)},
            ),
            instance("H", "thermal.heater"),
            instance("K1", "syn001.product_sink"),
            instance("K2", "syn001.product_sink"),
        ],
        [
            connection("S1", ("F", "outlet"), ("SP", "inlet"), "liquid"),
            connection("S2", ("SP", "recycle"), ("H", "inlet"), "liquid"),
            connection("S3", ("SP", "purge"), ("K2", "inlet"), "liquid"),
            connection("S4", ("H", "outlet"), ("K1", "inlet"), "liquid"),
        ],
        [*feed("S1", "H2O", 300.0, 1.0e6), duty("H", q)],
    )


def test_a62_a_dormant_heater_with_zero_duty_converges_on_the_label_row(registered: None) -> None:
    """S11.A62 (Q_spec = 0, `T05b-phase-contract-v2`): CONVERGED in the attempt whose signature
    holds `H.outlet` ZERO_FLOW, the outlet at its label temperature."""
    _, run = solve(_dormant_heater(0.0))
    assert run.outcome == "CONVERGED", run.message
    assert run.state is not None
    (step,) = run.steps
    assert step.detail.attempts[-1].signature == (("H.outlet", "ZERO_FLOW"),)
    assert run.state["S2.n.H2O"] == 0.0 and run.state["S4.n.H2O"] == 0.0
    assert run.state["S4.T"] == run.state["S2.T"] == 300.0
    assert run.state["H.Q"] == 0.0


def test_a62_a_dormant_heater_with_a_duty_is_a_specification_conflict(registered: None) -> None:
    """S11.A62 (Q_spec = 1 kW): `SPECIFICATION_CONFLICT` `zero_flow_conflict(H:TH-energy)`."""
    _, run = solve(_dormant_heater(1.0e3))
    assert run.outcome == "SPECIFICATION_CONFLICT"
    assert run.message == "zero_flow_conflict(H:TH-energy)"
