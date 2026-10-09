"""M05 WO-5: M02's inner solve at pinned w (the additive accessor
`revision_binding.with_coupling`) and TR-E2's independent reference T_ref (design note §5.2,
§12 WO-5; ADR 0039 D2).

The accessor is proved inert: it builds the binding M02's own WO-9 test support builds
(`test_m02_wo9_reactor.at_coupling`), the same spec and a bitwise-equal inner solve, and at the
document's own w the spec the binder built. The reference is test support
(`tests/support/m05_reference.py`): Newton on w to 1e-12 scaled, golden section to 0.05 K.
Default gate: no Pyomo, no reactor environment.
"""

from __future__ import annotations

import json
import sys
from functools import cache
from typing import Any

import pytest
from conftest import REPO_ROOT
from test_m02_wo9_reactor import LOOP_PATH, W_STAR, at_coupling

from openflowsheet.application.revision_binding import (
    RevisionBinding,
    bind_revision_flowsheet,
    with_coupling,
)
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.orchestrator.executor import execute_plan
from openflowsheet.orchestrator.revision import plan_revision

sys.path.insert(0, str(REPO_ROOT / "tests" / "support"))
import m05_reference as reference  # noqa: E402


def loop() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(LOOP_PATH.read_text(encoding="utf-8"))
    return document


def bound() -> RevisionBinding:
    binding = bind_revision_flowsheet(loop())
    assert isinstance(binding, RevisionBinding), binding
    return binding


def solved_state(binding: RevisionBinding) -> dict[str, float]:
    plan, _ = plan_revision(binding, reference.POLICY)
    run = execute_plan(
        plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=reference.POLICY
    )
    assert run.outcome == "CONVERGED" and run.state is not None, run.message
    return dict(run.state)


def identity(binding: RevisionBinding) -> tuple[str, str]:
    """The compiled spec's identity: `model_version` (the structure) and `constants_sha256`."""
    metadata = compile_problem(binding.spec).metadata
    return metadata.model_version, metadata.constants_sha256


def _bits(state: dict[str, float]) -> dict[str, str]:
    return {name: float(value).hex() for name, value in state.items()}


# == the accessor =================================================================================


def test_the_accessor_is_m02s_rebinding_at_pinned_w() -> None:
    binding = bound()
    ours = with_coupling(binding, "reactor", *W_STAR)
    theirs = at_coupling(binding, "reactor", W_STAR)
    assert identity(ours) == identity(theirs)
    assert ours.spec.parameters == theirs.spec.parameters
    assert ours.spec.parameters["reactor.coupling.X"] == 0.25
    assert ours.spec.parameters["reactor.coupling.dT"] == 0.0
    assert _bits(solved_state(ours)) == _bits(solved_state(theirs))


def test_the_accessor_at_the_documents_own_w_rebuilds_the_bound_spec() -> None:
    binding = bound()
    same = with_coupling(binding, "reactor", 0.15, 80.0)
    assert identity(same) == identity(binding)
    assert _bits(solved_state(same)) == _bits(solved_state(binding))


def test_the_accessor_refuses_a_unit_that_is_not_a_c1_reactor() -> None:
    with pytest.raises(ValueError, match="not an embedded C1 reactor"):
        with_coupling(bound(), "preheater", 0.25, 0.0)


# == the reference ================================================================================


@cache
def golden() -> Any:
    return reference.golden_section(loop())


def test_the_reference_couples_each_point_to_1e_12_scaled() -> None:
    """Every point of the search is the loop coupled to the synthetic truth: ‖F‖_scaled ≤ 1e-12,
    and the inner solve's reactor inlet is at the point's T_in."""
    result = golden()
    assert all(point.residual <= reference.TOLERANCE for point in result.points)
    stream = "S3"
    assert all(point.state[f"{stream}.T"] == point.temperature for point in result.points)


def test_the_reference_brackets_an_interior_optimum_to_0_05_k() -> None:
    """Golden section over [653.15, 693.15] K: 2 + 14 evaluations, a final bracket ≤ 0.05 K that
    holds T_ref, T_ref interior. Recorded (regression, this machine): T_ref = 673.6434377969885 K,
    J = 0.45591460765032843 mol/s, w = (0.19223145, 88.92714 K); Newton takes 4 iterations at
    every point."""
    result = golden()
    low, high = result.bracket
    assert high - low <= reference.BRACKET and len(result.points) == 16
    assert low <= result.best.temperature <= high
    assert reference.BOX[0] + 1.0 < result.best.temperature < reference.BOX[1] - 1.0
    assert result.best.temperature == pytest.approx(673.6434377969885, abs=1e-6)
    assert result.best.objective == pytest.approx(0.45591460765032843, rel=1e-12)
    # Unimodal on the evaluated points: J rises to T_ref and falls after it.
    ordered = sorted(result.points, key=lambda point: point.temperature)
    peak = ordered.index(result.best)
    rising = [point.objective for point in ordered[: peak + 1]]
    falling = [point.objective for point in ordered[peak:]]
    assert rising == sorted(rising) and falling == sorted(falling, reverse=True)
