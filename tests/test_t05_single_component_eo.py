"""T05 A30: a single flowing component in the latent jump on the EO path (spec §4.7 (b); ruling
round Q-R8, review S3; register R-050).

Two mini-revisions with instances from `SYN-001-UL-C1.yaml`, run through the common path
(`plan_revision` → `execute_plan` → `verify_revision` when `CONVERGED`, policy `T05-W13`):

- P3: feed `(0, 2, 0)` at 370 K and `1.8e5 Pa`, `liquid` → `U-VLV` (`P_spec = P_r`) → `S2`
  (`vapor_liquid`) → sink.
- P4: PHF-6's inputs as the feed → `U-PHF` (`Q_spec = 42 000 W`, `ΔP = 0`) → two sinks.

The causal answers are closed forms (P3) or registered (P4). The EO outcome is never `VERIFIED`;
the typed outcomes measured on 2026-09-25 are pinned as **regression values** — self-generated,
not validation; a change is reported to the design lane, not re-pinned. The control, P4 with
`1e-6 mol/s` of A in the feed, converges.
"""

from __future__ import annotations

from typing import Any

import pytest
from t05_support import (
    BETA_TOLERANCE,
    ENERGY_TOLERANCE,
    REF,
    TEMPERATURE_TOLERANCE,
    assert_close,
    assert_flows,
)
from t05_w12_support import (
    Feed,
    Outlet,
    bind,
    connection_pin,
    duty_pin,
    mini_revision,
    unit_instance,
)
from test_t05_coupled import POLICY

from openflowsheet.application.revision_binding import RevisionBinding
from openflowsheet.models import UnitEvaluation
from openflowsheet.models.syn001.ph_flash import PHFlash
from openflowsheet.models.syn001.ph_kernel import PHState
from openflowsheet.models.syn001.valve import Valve
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import execute_plan
from openflowsheet.orchestrator.revision import plan_revision
from openflowsheet.thermo import StreamState
from openflowsheet.verify.certificate import verify_revision

P_R = 1.0e5
PHF_6 = REF["unit_cases"]["PHF-6"]

#: Regression values (measured 2026-09-25, review P3/P4 reproduced): the typed outcomes. P4's
#: moved at T05b W9.5 (K03 §5.3 as amended, R-064; T05b B33 (d) names it, as SC-2 under
#: `T05-W13`): `BOUND_BLOCKED` → `ACTIVE_SET_CYCLING`, still never `VERIFIED`. T05's evidence at
#: `91ac010` records the old value for its commit.
MEASURED_OUTCOME = {"P3": "ACTIVE_SET_CYCLING", "P4": "ACTIVE_SET_CYCLING"}


def p3() -> tuple[dict[str, Any], StreamState]:
    feed = StreamState(n=(0.0, 2.0, 0.0), temperature=370.0, pressure=1.8e5)
    document = mini_revision(
        "A30-P3",
        unit_instance("SYN-001-UL-C1", "U-VLV"),
        [Feed("inlet", "S1", "liquid", (0.0, 2.0, 0.0), feed.temperature, feed.pressure)],
        [Outlet("outlet", "S2", "vapor_liquid")],
        [connection_pin("SPEC-valve-P", "S2", "state.P", P_R)],
    )
    return document, feed


def p4(trace_of_a: float = 0.0) -> tuple[dict[str, Any], StreamState]:
    inlet = PHF_6["inputs"]["inlet"]
    registered = tuple(float(value) for value in inlet["n_mol_per_s"])
    flows = (registered[0] + trace_of_a, registered[1], registered[2])
    feed = StreamState(n=flows, temperature=float(inlet["T_K"]), pressure=float(inlet["P_Pa"]))
    assert PHF_6["inputs"]["inlet_phase"] == "LIQUID"
    assert float(PHF_6["inputs"]["pressure_drop"]) == 0.0
    document = mini_revision(
        "A30-P4",
        unit_instance("SYN-001-UL-C1", "U-PHF"),
        [Feed("inlet", "S1", "liquid", flows, feed.temperature, feed.pressure)],
        [Outlet("vapor", "S2", "vapor"), Outlet("liquid", "S3", "liquid")],
        [duty_pin("SPEC-phf-Q", "U-PHF", float(PHF_6["inputs"]["duty"]))],
    )
    return document, feed


def causal(
    binding: RevisionBinding, unit_id: str, feed: StreamState
) -> tuple[UnitEvaluation, PHState | None]:
    """The bound unit's own causal answer on the feed (the kernel's closure included)."""
    (unit,) = (unit for unit in binding.flowsheet.instances if unit.unit_id == unit_id)
    assert isinstance(unit, PHFlash | Valve), unit
    return unit.evaluate_with_closure({"inlet": (feed,)}, binding.flowsheet.context)


def run(document: dict[str, Any]) -> tuple[str, str]:
    """The common path; `(outcome, verification status or "")`."""
    binding = bind(document)
    plan, _ = plan_revision(binding, POLICY)
    assert isinstance(plan, ExecutionPlan), plan
    result = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=POLICY)
    if result.outcome != "CONVERGED":
        return result.outcome, ""
    certificate = verify_revision(binding, document, result, solve_plan=plan.steps[-1].solve_plan)
    return result.outcome, certificate.verification_status


# ------------------------------------------------------------------------ (1) causal answers


def test_a30_p3_the_valve_flashes_pure_b_by_the_lever_rule() -> None:
    """Closed form: `β = (2 c_p·70 K + 2 v·8e4 Pa − 2 c_p·60 K)/(2 L_B) = 2 016/60 000`."""
    document, feed = p3()
    result, closure = causal(bind(document), "U-VLV", feed)
    assert result.status == "ok", result.message
    assert closure is not None and closure.route == "saturation"
    assert result.phase_signature == "TWO_PHASE"
    assert closure.temperature is not None and closure.split is not None
    assert abs(closure.temperature - 360.0) <= TEMPERATURE_TOLERANCE
    assert closure.split.vapor_fraction is not None
    assert abs(closure.split.vapor_fraction - 2_016.0 / 60_000.0) <= BETA_TOLERANCE


def test_a30_p4_the_ph_flash_gives_phf_6s_registered_values() -> None:
    document, feed = p4()
    result, closure = causal(bind(document), "U-PHF", feed)
    expected = PHF_6["expected"]
    assert result.status == expected["status"], result.message
    assert result.phase_signature == expected["signature"]
    assert closure is not None and closure.route == expected["route"]
    assert_close(closure.temperature, expected["T_K"], TEMPERATURE_TOLERANCE, "T")
    assert closure.split is not None
    assert_close(closure.split.vapor_fraction, expected["beta"], BETA_TOLERANCE, "beta")
    assert_close(result.duty, expected["duty_W"], ENERGY_TOLERANCE, "duty")
    for port in ("vapor", "liquid"):
        assert_flows(result.outlets[port].n, expected[port]["n_mol_per_s"], f"{port}.n")


# ------------------------------------------------------------------- (2) never VERIFIED


@pytest.mark.parametrize("case", ["P3", "P4"])
def test_a30_the_eo_path_never_verifies_a_single_flowing_component_in_the_jump(case: str) -> None:
    document, _ = p3() if case == "P3" else p4()
    outcome, status = run(document)
    assert status != "VERIFIED", (outcome, status)
    if outcome == "CONVERGED":
        assert status in {"UNVERIFIED", "FAILED"}
    # Regression value (self-generated): reported to the design lane if it moves.
    assert outcome == MEASURED_OUTCOME[case]


# -------------------------------------------------------------------------- (3) the control


def test_a30_control_a_trace_of_a_converges() -> None:
    document, _ = p4(trace_of_a=1e-6)
    outcome, _ = run(document)
    assert outcome == "CONVERGED"
