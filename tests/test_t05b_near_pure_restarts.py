"""T05b B33: near-pure feeds restart into two phases (spec §6.2 step 3 as amended 2026-09-25,
ruling Q-S11; review S2; K03 §5.3 as amended, R-064).

- **(a)** An opening that takes a PH closure's answer **sets** every temperature column of the
  split's streams to the closure's `T` — for a products-style split, both products (Q-S11 (a)).
  Checked at every restart opening of a products-style PH-type split under v2 in SC-3, DZ-12 and
  B31's restart cases: both products' temperatures equal the kernel answer's `T` bitwise. The
  liquid product's column is read off the case's wiring, not off `splits.split_temperatures`.
- **(b)** NP-1…NP-3 and NP-G from the **liquid-form start** (`initial_state` with
  `S3.n := S2.n + S3.n`, `S2.n := 0`, the totals updated, `S2.T = S3.T = 300 K`; review P5) are
  `CONVERGED` and `VERIFIED`: NP-1 and NP-2 judged degenerate, NP-3 resolved, NP-G unresolved;
  NP-1…NP-3 within §13's EO allowances of `ref.near_pure_cases`, NP-G's temperature within
  `1e-5 K` and its split not compared (as B13). Before W9.4 and W9.5 NP-2 and NP-G ended
  `BOUND_BLOCKED` at iteration 0 on `S2.n.A` (review P5, P6); with W9.4 alone NP-G converges and
  NP-2 still blocks (*measured*, `docs/t05b-measurements.md`).
- **(c)** K03 §5.3's release at the level of the bound-aware step (`newton._bound_aware_step`).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from decimal import Decimal
from functools import cache
from typing import Any

import numpy as np
import pytest
import scipy.sparse as sp
from t05_w12_support import bind, planned_step
from t05b_support import (
    POLICY_V2,
    REF,
    dz12,
    near_pure,
    registered_state,
    sc3,
    solve_from_v2,
)
from test_t05b_openings import CASES as B31_CASES

from openflowsheet.application.revision_binding import RevisionBinding
from openflowsheet.models import temperature_id
from openflowsheet.numerics.newton import _bound_aware_step, _released, _trial_point
from openflowsheet.orchestrator import region as region_module
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import execute_plan
from openflowsheet.orchestrator.region import LiftedSplit, RegionResult, _KernelAnswer
from openflowsheet.orchestrator.revision import initial_state, plan_revision
from openflowsheet.orchestrator.splits import closure_types
from openflowsheet.orchestrator.trace import Trace
from openflowsheet.verify.certificate import SolutionCertificate, verify_revision


@dataclass(frozen=True)
class Opening:
    """One restart opening where a products-style PH-type split took a PH closure's answer."""

    unit: str
    closure_temperature: float
    vapor_temperature: float
    liquid_temperature: float


@pytest.fixture
def openings(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[Opening]]:
    """Spies on `_contract_kernel` (the kernel an opening asks) and `_LiftedOps._settled` (every
    restart opening, after the kernel answers are set): each products-style PH-type split whose
    regime the opening changed to the answer of a PH closure (no `tp` record, not `ZERO_FLOW`)
    gives one `Opening`, read off the settled state."""
    found: list[Opening] = []
    answers: dict[str, _KernelAnswer] = {}
    kernel, settled = region_module._contract_kernel, region_module._LiftedOps._settled

    def spy_kernel(*args: Any, **kwargs: Any) -> _KernelAnswer:
        answer = kernel(*args, **kwargs)
        split: LiftedSplit = args[2]
        answers[split.unit] = answer
        return answer

    def spy_settled(
        self: Any,
        state: Mapping[str, float],
        regimes: Mapping[str, Any],
        fallbacks: Any = (),
    ) -> Any:
        result = settled(self, state, regimes, fallbacks)
        opened = result[0]
        for split in self._splits:
            answer = answers.get(split.unit)
            if (
                answer is None
                or split.unit not in self._ph_units
                or answer.fallback == "tp"
                or answer.regime in ("ZERO_FLOW", self._regimes[split.unit])
                or regimes[split.unit] != answer.regime
            ):
                continue
            liquid = temperature_id(LIQUID_PRODUCT[split.unit])
            found.append(
                Opening(
                    split.unit,
                    answer.values[split.temperature],
                    opened[split.temperature],
                    opened[liquid],
                )
            )
        answers.clear()
        return result

    monkeypatch.setattr(region_module, "_contract_kernel", spy_kernel)
    monkeypatch.setattr(region_module._LiftedOps, "_settled", spy_settled)
    yield found


#: Filled per case before its solve: each PH-type unit's liquid product stream, off the wiring.
LIQUID_PRODUCT: dict[str, str] = {}


def _wire(binding: Any) -> None:
    flowsheet = binding.flowsheet
    LIQUID_PRODUCT.clear()
    for unit in flowsheet.units():
        wiring = flowsheet.wiring[unit.unit_id]
        if closure_types([unit]).get(unit.unit_id) == "PH" and "liquid" in wiring.streams:
            LIQUID_PRODUCT[unit.unit_id] = wiring.one("liquid")


def _sc3() -> None:
    binding = bind(sc3())
    _wire(binding)
    plan, _ = plan_revision(binding, POLICY_V2)
    assert isinstance(plan, ExecutionPlan), plan
    run = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=POLICY_V2)
    assert run.outcome == "CONVERGED", run.message


def _dz12() -> None:
    binding = bind(dz12())
    _wire(binding)
    start = registered_state(REF["dormant_non_lifted_cases"]["DZ-12"]["start"])
    result = solve_from_v2(binding, start)
    assert result.outcome == "CONVERGED", result.message


def _b31(case: str) -> None:
    document, start = B31_CASES[case]()
    binding = bind(document)
    _wire(binding)
    result = solve_from_v2(binding, start)
    assert result.outcome == "CONVERGED", result.message


RUNS = {
    "SC-3": _sc3,
    "DZ-12": _dz12,
    **{
        case: (lambda case=case: _b31(case))
        for case in ("CH-UP", "CH-DZ12", "CH-3", "CH-UP/PHF2-first")
    },
}


@pytest.mark.parametrize("case", RUNS)
def test_b33a_both_products_take_the_closures_temperature(
    case: str, openings: list[Opening]
) -> None:
    RUNS[case]()
    assert openings, f"{case}: no restart opening took a PH closure's answer"
    for opening in openings:
        assert opening.vapor_temperature == opening.closure_temperature, opening
        assert opening.liquid_temperature == opening.closure_temperature, opening


# ------------------------------------------------------------ (b) NP from the liquid-form start

COMPONENTS = ("A", "B", "C")
ALLOWANCE: dict[str, float] = {
    kind: float(value) for kind, value in REF["tolerances"]["coupled_allowances"].items()
}
#: Spec B13: NP-G's temperature is compared at `1e-5 K`; its split is not compared.
NP_G_TEMPERATURE = 1e-5
#: The attempt-1 cause B33 (b) names, and (*regression*, measured 2026-09-25, W9.5) the band-route
#: record NP-1's and NP-2's PH closure adds there.
CAUSE = "phase_update(phase_wall(patience, U-PHF:LIQUID->TWO_PHASE)"
BAND_ITEM = {"NP-1": True, "NP-2": True, "NP-3": False, "NP-G": False}
#: Regression values (W9.5): each attempt's iterations — attempt 0 `LIQUID`, attempt 1
#: `TWO_PHASE`.
ITERATIONS = {"NP-1": (2, 1), "NP-2": (2, 1), "NP-3": (2, 2), "NP-G": (2, 1)}


def liquid_form(binding: RevisionBinding) -> dict[str, float]:
    """Review P5's start: the traversal's state with the PH flash's products all liquid at 300 K."""
    start = initial_state(binding.flowsheet, binding.spec.variable_ids)
    assert isinstance(start, dict), start
    for component in COMPONENTS:
        start[f"S3.n.{component}"] = start[f"S2.n.{component}"] + start[f"S3.n.{component}"]
        start[f"S2.n.{component}"] = 0.0
    start["S2.N"] = 0.0
    start["S3.N"] = sum(start[f"S3.n.{component}"] for component in COMPONENTS)
    start["S2.T"] = start["S3.T"] = 300.0
    return start


@dataclass(frozen=True)
class NearPure:
    result: RegionResult
    opened: list[str]
    certificate: SolutionCertificate | None


@cache
def from_liquid(case: str) -> NearPure:
    document = near_pure(case)
    binding = bind(document)
    trace = Trace()
    result = solve_from_v2(binding, liquid_form(binding), trace=trace)
    certificate = None
    if result.outcome == "CONVERGED":
        step = planned_step(binding, POLICY_V2)
        certificate = verify_revision(
            binding, document, result, state=dict(result.state), solve_plan=step.solve_plan
        )
    opened = [event.message for event in trace.events if event.kind == "attempt_opened"]
    return NearPure(result, opened, certificate)


def _near(got: float, expected: str, allowance: float, what: str) -> None:
    difference = float(abs(Decimal(got) - Decimal(expected)))
    assert difference <= allowance, (what, got, expected, difference)


@pytest.mark.parametrize("case", ["NP-1", "NP-2", "NP-3", "NP-G"])
def test_b33b_near_pure_from_the_liquid_form_start(case: str) -> None:
    run = from_liquid(case)
    result = run.result
    assert result.outcome == "CONVERGED", result.message
    assert [list(map(list, a.signature)) for a in result.attempts] == [
        [["U-PHF", "LIQUID"]],
        [["U-PHF", "TWO_PHASE"]],
    ]
    assert run.opened[1].startswith(CAUSE), run.opened
    assert ("fallback(U-PHF, ph-band)" in run.opened[1]) == BAND_ITEM[case]  # regression
    assert tuple(a.iterations for a in result.attempts) == ITERATIONS[case]  # regression
    certificate = run.certificate
    assert certificate is not None
    assert certificate.verification_status == "VERIFIED", [
        (c.id, c.result, c.value) for c in certificate.checks if c.result != "pass"
    ]
    checks = {check.id: check for check in certificate.checks}
    entry = REF["near_pure_cases"][case]
    root, state = entry["root"], result.state
    if case == "NP-G":
        split = checks["independent_split.U-PHF.S1"]
        assert (split.result, split.reason) == ("not_applicable", "fresh_flash_unresolved")
        for stream in ("S2", "S3"):
            _near(state[f"{stream}.T"], root["T_K"], NP_G_TEMPERATURE, f"{stream}.T")
        return
    for index, component in enumerate(COMPONENTS):
        _near(state[f"S2.n.{component}"], root["vapor_mol_per_s"][index], ALLOWANCE["flow"], "S2")
        _near(state[f"S3.n.{component}"], root["liquid_mol_per_s"][index], ALLOWANCE["flow"], "S3")
    for stream in ("S2", "S3"):
        _near(state[f"{stream}.T"], root["T_K"], ALLOWANCE["T"], f"{stream}.T")
    if entry["degenerate"]:
        assert checks["phase_admissibility.U-PHF.S1.saturation"].result == "pass"
        split = checks["independent_split.U-PHF.S1"]
        assert (split.result, split.reason) == ("not_applicable", "temperature_degenerate")
    else:
        assert "phase_admissibility.U-PHF.S1.saturation" not in checks
        for suffix in ("total", *COMPONENTS):
            assert checks[f"independent_split.U-PHF.S1.{suffix}"].result == "pass", suffix


# ------------------------------------------------------------- (c) the bound-aware step's release

#: Two components on `x ≥ 0`: `a` at `+0.0` (at the opening too), `b = 1`.
X = np.array([0.0, 1.0])
LOWER = np.array([0.0, 0.0])
#: The factorization's roundoff on `a` (outward), and a real step on `b` that stays inside.
DIRECTION = np.array([-1e-30, -0.5])


def _step(
    residual: tuple[float, ...], jacobian: list[list[float]], opening: np.ndarray = X
) -> tuple[np.ndarray, float, tuple[int, ...], tuple[int, ...]]:
    return _bound_aware_step(
        X,
        DIRECTION,
        LOWER,
        opening=opening,
        residual=residual,
        jacobian=sp.csc_matrix(np.array(jacobian)),
    )


def test_b33c_i_a_released_structural_zero_steps_at_alpha_max() -> None:
    """Row 0 is `F = 2a`, zero at `a = 0` with its one entry on `a`: `{a}` is released."""
    direction, alpha, landing, released = _step((0.0, 0.5), [[2.0, 0.0], [1.0, 1.0]])
    assert released == (0,)
    assert alpha == 1.0 and landing == ()
    assert direction[0] == 0.0 and direction[1] == -0.5
    trial = _trial_point(X, direction, alpha, LOWER, landing)
    assert trial[0] == 0.0 and np.copysign(1.0, trial[0]) == 1.0  # `+0.0`
    assert trial[1] == 0.5


def test_b33c_ii_a_row_of_the_set_off_zero_stays_blocked() -> None:
    """The same with row 0 at `F ≠ 0` (K03 BND-02's case): `BOUND_BLOCKED` on `a`."""
    direction, alpha, blocked, released = _step((1e-3, 0.5), [[2.0, 0.0], [1.0, 1.0]])
    assert (alpha, blocked, released) == (0.0, (0,), ())
    assert direction is DIRECTION


def test_b33c_iii_a_component_not_on_its_bound_at_the_opening_is_never_released() -> None:
    """`a` reached its bound during the attempt (T02 §6.3.3's disappearance): not released."""
    opening = np.array([0.25, 1.0])
    _, alpha, blocked, released = _step((0.0, 0.5), [[2.0, 0.0], [1.0, 1.0]], opening)
    assert (alpha, blocked, released) == (0.0, (0,), ())


def test_b33c_iv_fewer_closed_rows_than_columns_is_not_released() -> None:
    """`a` and `b` both on their bounds; the one closed row reads both, the other row is off
    zero: no set has as many closed rows as columns."""
    x = np.array([0.0, 0.0])
    direction = np.array([-1e-30, 0.5])
    _, alpha, blocked, released = _bound_aware_step(
        x,
        direction,
        LOWER,
        opening=x,
        residual=(0.0, 1.0),
        jacobian=sp.csc_matrix(np.array([[1.0, 1.0], [0.0, 1.0]])),
    )
    assert (alpha, blocked, released) == (0.0, (0,), ())


def test_b33c_v_a_blocker_outside_the_released_set_keeps_the_original_blockers() -> None:
    """Re-review N-W4: `Z* = {a}` is non-empty (row 0, `F = 2a`, closed on `a` alone), but `b`,
    also on its bound and pointing out, has no closed row (row 1 is off zero), so it still blocks
    once `a`'s direction is zeroed: nothing is released, and the blockers are the original
    direction's — `a` included (`newton._bound_aware_step`'s `alpha_kept == 0.0` branch)."""
    x = np.array([0.0, 0.0, 1.0])
    lower = np.array([0.0, 0.0, 0.0])
    direction = np.array([-1e-30, -0.5, -0.25])
    jacobian = sp.csc_matrix(np.array([[2.0, 0.0, 0.0], [0.0, 1.0, 1.0], [1.0, 0.0, 1.0]]))
    residual = (0.0, 1e-3, 0.5)
    assert _released(x, x, lower, residual, jacobian) == (0,)
    taken, alpha, blocked, released = _bound_aware_step(
        x, direction, lower, opening=x, residual=residual, jacobian=jacobian
    )
    assert (alpha, blocked, released) == (0.0, (0, 1), ())
    assert taken is direction
