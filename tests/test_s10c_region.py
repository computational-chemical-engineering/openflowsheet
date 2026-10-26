"""S10-C WO-2: the orchestrator's single-phase admissibility (K03 §8.2) for a composition-dependent
K (design note `docs/derivations/S10C-design.md` §4.10; ADR 0049).

LIQUID's value is `Σ x_i K_i(T, P, x)`, VAPOR's is `ΣW` of the incipient liquid. Expectations come
from the definitions and the 50-digit band points of `benchmarks/s10c/reference_values.yaml`, not
from the code: at the bubble point `Σ z_i K_i(T_b, z) = 1` (β = 0's Rachford–Rice row), at the dew
point the liquid trial is stationary with `ΣW = 1` (`tm* = 0`, S10-C spec §2.3), and on either side
the sign follows from T1 and T2 (`Σ z_i K_i` and `tm*` strictly increasing in T).
"""

from __future__ import annotations

from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT

from openflowsheet.compiled import EvaluationContext
from openflowsheet.orchestrator.region import LiftedSplit, _admissible
from openflowsheet.thermo.wilson_ig import WilsonIdealGasProvider
from openflowsheet.verify.checks import VerifierError

CONTEXT = EvaluationContext(model_version="S10C-WO2@" + "0" * 64, constants_sha256="0" * 64)
REF = yaml.safe_load((REPO_ROOT / "benchmarks" / "s10c" / "reference_values.yaml").read_text())
PROVIDER = WilsonIdealGasProvider(REPO_ROOT / "benchmarks" / "s10" / "records.yaml")
#: G3's fixed-point tolerance: the band point's rows at the reference root (spec §5.1).
TOL_ROWS: float = REF["tolerances"]["G3"]["fixed_point_rows"]
#: BP-R01: ethanol–water, water side (real records, 101 325 Pa).
FEED = REF["band_points"]["BP-R01"]
assert FEED["records"] == "real"
POINTS = {point["beta"]: point for point in FEED["points"]}
T_BUBBLE: float = POINTS[0.0]["T"]
T_DEW: float = POINTS[1.0]["T"]

SPLIT = LiftedSplit(
    unit="F",
    stream="S",
    feed=("S.n.MeOH", "S.n.EtOH", "S.n.H2O"),
    temperature="F.T",
    pressure="F.P",
    vapor=("F.v.MeOH", "F.v.EtOH", "F.v.H2O"),
    liquid=("F.l.MeOH", "F.l.EtOH", "F.l.H2O"),
    vapor_total="F.V",
    liquid_total="F.L",
    equilibrium_rows=(),
    vapor_definition="F.Vdef",
    liquid_definition="F.Ldef",
)


def _state(side: str, flows: tuple[float, ...], temperature: float) -> dict[str, Any]:
    """A single-phase state: `flows` on `side`, the other side exactly `+0.0`."""
    other = "vapor" if side == "liquid" else "liquid"
    state: dict[str, Any] = dict(zip(SPLIT.feed, flows, strict=True))
    state.update(dict(zip(getattr(SPLIT, side), flows, strict=True)))
    state.update(dict.fromkeys(getattr(SPLIT, other), 0.0))
    state[SPLIT.temperature] = temperature
    state[SPLIT.pressure] = float(FEED["P"])
    return state


Z = tuple(float(value) for value in FEED["n"])


def test_liquid_value_is_one_at_the_bubble_point() -> None:
    _, value = _admissible(PROVIDER, CONTEXT, SPLIT, "LIQUID", _state("liquid", Z, T_BUBBLE), 0.0)
    assert abs(value - 1.0) <= TOL_ROWS


def test_liquid_is_admissible_below_the_bubble_point_only() -> None:
    below = _admissible(
        PROVIDER, CONTEXT, SPLIT, "LIQUID", _state("liquid", Z, T_BUBBLE - 1.0), 0.0
    )
    above = _admissible(
        PROVIDER, CONTEXT, SPLIT, "LIQUID", _state("liquid", Z, T_BUBBLE + 1.0), 0.0
    )
    assert below[0] is True and below[1] < 1.0
    assert above[0] is False and above[1] > 1.0
    # ε widens the test and nothing else: the value is unchanged.
    widened = _admissible(
        PROVIDER, CONTEXT, SPLIT, "LIQUID", _state("liquid", Z, T_BUBBLE + 1.0), 1.0
    )
    assert widened == (True, above[1])


def test_vapour_value_is_one_at_the_dew_point() -> None:
    _, value = _admissible(PROVIDER, CONTEXT, SPLIT, "VAPOR", _state("vapor", Z, T_DEW), 0.0)
    assert abs(value - 1.0) <= TOL_ROWS


def test_vapour_is_admissible_above_the_dew_point_only() -> None:
    above = _admissible(PROVIDER, CONTEXT, SPLIT, "VAPOR", _state("vapor", Z, T_DEW + 1.0), 0.0)
    below = _admissible(PROVIDER, CONTEXT, SPLIT, "VAPOR", _state("vapor", Z, T_DEW - 1.0), 0.0)
    assert above[0] is True and above[1] < 1.0
    assert below[0] is False and below[1] > 1.0


@pytest.mark.parametrize("regime", ["LIQUID", "VAPOR"])
def test_an_empty_side_is_admissible_with_value_zero(regime: str) -> None:
    side = "vapor" if regime == "LIQUID" else "liquid"  # the named side is the empty one
    state = _state(side, Z, T_BUBBLE)
    assert _admissible(PROVIDER, CONTEXT, SPLIT, regime, state, 0.0) == (True, 0.0)  # type: ignore[arg-type]


@pytest.mark.parametrize(("regime", "side"), [("LIQUID", "liquid"), ("VAPOR", "vapor")])
def test_a_provider_refusal_is_a_verifier_error(regime: str, side: str) -> None:
    """Outside the records' T domain the provider refuses; the screen's `VerifierError`."""
    with pytest.raises(VerifierError, match="the kernel refused F's regime"):
        _admissible(PROVIDER, CONTEXT, SPLIT, regime, _state(side, Z, 250.0), 0.0)  # type: ignore[arg-type]


@pytest.mark.parametrize("regime", ["TWO_PHASE", "ZERO_FLOW"])
def test_two_phase_and_zero_flow_branches_are_unchanged(regime: str) -> None:
    if regime == "TWO_PHASE":
        state = _state("liquid", Z, T_BUBBLE)
        assert _admissible(PROVIDER, CONTEXT, SPLIT, "TWO_PHASE", state, 0.0) == (True, 0.0)
    else:
        state = _state("liquid", (0.0, 0.0, 0.0), T_BUBBLE)
        assert _admissible(PROVIDER, CONTEXT, SPLIT, "ZERO_FLOW", state, 0.0) == (True, 0.0)
