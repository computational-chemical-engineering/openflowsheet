"""S11 WO-D6: the Wilson (γ–φ) flowsheets solved through the region (units design §5.3 D6, §6.1).

The spike first (Q18, D6's half): do the region's γ–φ paths carry the five K02/T05 units on
`wilson-ig-v2`? GP-C1 (heater → TP flash on S10 C-MW's feed) is the first case through the region:
from the units' own start it closes with no Newton step, and from a perturbed start Newton iterates
on the γ–φ rows (`GammaPhiLnKBlock`, the mixture enthalpy blocks) back to the same root.

"VERIFIED" is `verify_revision`'s certificate with the v2 basis dispatched to the γ–φ form
(`s11_gp_support.dispatch_gamma_phi`, I1b's hook), every check passing. Each certificate's
derivative witness records |Z| (S11 rulings item 2, R-831: the exactly-zero component columns
beside a positive sibling, differenced one-sided) and the one-sided part's worst, which must stay
≤ `DERIVATIVE_TOLERANCE`/10 (a larger value is a stop, never a widening).
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

import pytest
from s11_gp_support import (
    CASES,
    admit_wilson,
    committed_case,
    dispatch_gamma_phi,
    solve,
)

from openflowsheet.application.policies import T06_REVISION_V2
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import flow_id, pressure_id, temperature_id
from openflowsheet.models.revision_flowsheet import WILSON_BASIS, parse_revision
from openflowsheet.orchestrator.executor import execute_plan
from openflowsheet.thermo import FlashRequest, StreamState
from openflowsheet.verify.certificate import BoundDeclaration, fresh_provider, verify_revision
from openflowsheet.verify.checks import (
    DERIVATIVE_TOLERANCE,
    KIND_TOLERANCE,
    derivative_witness,
    one_sided_columns,
)

TAU_E = KIND_TOLERANCE["heat_rate"]
TAU_FLOW = KIND_TOLERANCE["molar_flow"]
CONTEXT = EvaluationContext(model_version="t", constants_sha256="0" * 64, phase_signature=None)


@pytest.fixture(autouse=True)
def wilson_admitted(monkeypatch: pytest.MonkeyPatch) -> None:
    admit_wilson(monkeypatch)


@pytest.fixture
def gamma_phi(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    return dispatch_gamma_phi(monkeypatch)


@pytest.mark.parametrize("name", sorted(CASES))
def test_the_committed_case_is_the_generated_one(name: str) -> None:
    """`benchmarks/s11/gp/<name>.json` is `CASES[name]()` (regenerate with
    `python tests/s11_gp_support.py`)."""
    assert committed_case(name) == CASES[name]()


def _stream(state: Mapping[str, float], stream: str) -> StreamState:
    return StreamState(
        n=tuple(state[flow_id(stream, c)] for c in WILSON_BASIS.components),
        temperature=state[temperature_id(stream)],
        pressure=state[pressure_id(stream)],
    )


def certified(
    document: Mapping[str, Any], dispatched: list[int]
) -> tuple[Any, dict[str, float], dict[str, Any], float]:
    """Solve `document`, certify it, and measure its one-sided witness part (R-831): the
    certificate, x_final, `{"Z": |Z|, "one_sided_worst": ...}` and the solve's wall time."""
    start = time.perf_counter()
    binding, plan, run = solve(document)
    elapsed = time.perf_counter() - start
    assert run.outcome == "CONVERGED", run.message
    assert run.state is not None
    state = dict(run.state)
    certificate = verify_revision(binding, document, run, solve_plan=plan.steps[-1].solve_plan)
    assert dispatched and all(count > 0 for count in dispatched)
    view = parse_revision(document)
    domain = fresh_provider(view.basis).describe().domain["P"]
    target = BoundDeclaration(
        binding.spec, compile_problem(binding.spec), state, pressure_domain=domain
    )
    z = one_sided_columns(binding.spec.variable_ids, state, view.components)
    witness: dict[str, Any] = {"Z": len(z), "one_sided_worst": None}
    if z:
        rest = frozenset(binding.spec.variable_ids) - z
        one_sided = derivative_witness(target, state, unstenciled=rest, one_sided=z)
        assert [c.result for c in one_sided] == ["pass", "pass"], one_sided
        witness["one_sided_worst"] = max(c.value or 0.0 for c in one_sided)
    return certificate, state, witness, elapsed


def assert_verified(certificate: Any) -> None:
    failing = [
        (c.id, c.result, c.value, c.reason) for c in certificate.checks if c.result != "pass"
    ]
    assert not failing, failing
    assert certificate.verification_status == "VERIFIED"
    assert not [x for x in certificate.limitations if x.kind == "derivative_witness_partial"]
    witness = [c for c in certificate.checks if c.category == "derivative_witness"]
    assert [c.id for c in witness] == [
        "derivative_witness.on_pattern",
        "derivative_witness.off_pattern",
    ]


# -- Q18 and S11.A69: GP-C1 --------------------------------------------------------------------


def test_q18_the_region_carries_the_gamma_phi_heater_and_flash() -> None:
    """Q18 (D6): GP-C1 from a start 1 % off its root in every flow, split and temperature (the
    root is the units' own start, closed with no step): Newton iterates on the γ–φ rows and
    returns to the same root (measured: 5 accepted steps, max |Δx| 1.1e-9)."""
    binding, plan, run = solve(committed_case("GP-C1"))
    assert run.outcome == "CONVERGED" and run.state is not None, run.message
    assert [step.iterations for step in run.steps] == [0]
    root = dict(run.state)
    moved = {
        k: v * 1.01
        if v != 0.0 and (k.endswith(".T") or ".n." in k or ".vap." in k or ".liq." in k)
        else v
        for k, v in root.items()
    }
    again = execute_plan(
        plan=plan,
        flowsheet=binding.flowsheet,
        spec=binding.spec,
        policy=T06_REVISION_V2,
        user_start=moved,
    )
    assert again.outcome == "CONVERGED" and again.state is not None, again.message
    accepted = sum(1 for e in again.trace.events if e.kind == "step_accepted")
    assert accepted >= 1
    assert max(abs(again.state[k] - v) for k, v in root.items()) <= TAU_FLOW


def test_a69_gp_c1_heater_to_tp_flash(gamma_phi: list[int]) -> None:
    """S11.A69: CONVERGED and VERIFIED; the flash products equal the provider's own TP flash at
    the solved (n, T, P) within τ_flow per component; the energy balances ≤ τ_E. Measured: 0
    Newton steps; energy_balance H −1.19e-9 W, D 1.22e-9 W, envelope 2.2e-11 W; |Z| = 6 (the six
    ethanol flow columns), one-sided worst 1.19e-10, central on-pattern 3.5e-9."""
    certificate, state, witness, _ = certified(committed_case("GP-C1"), gamma_phi)
    assert_verified(certificate)
    energy = [c for c in certificate.checks if c.category == "energy_balance"]
    assert {c.id for c in energy} == {
        "energy_balance.H",
        "energy_balance.D",
        "energy_balance.envelope",
    }
    assert all(c.value is not None and abs(c.value) <= TAU_E for c in energy)
    provider = fresh_provider(WILSON_BASIS)
    inlet = _stream(state, "S2")
    drum = StreamState(
        n=inlet.n, temperature=state[temperature_id("S3")], pressure=state[pressure_id("S3")]
    )
    flash = provider.flash(FlashRequest(drum), CONTEXT)
    assert flash.status == "ok" and flash.vapor is not None and flash.liquid is not None
    for k, c in enumerate(WILSON_BASIS.components):
        assert abs(state[flow_id("S3", c)] - flash.vapor.n[k]) <= TAU_FLOW, c
        assert abs(state[flow_id("S4", c)] - flash.liquid.n[k]) <= TAU_FLOW, c
    assert witness["Z"] == 6
    assert witness["one_sided_worst"] <= DERIVATIVE_TOLERANCE / 10, witness
