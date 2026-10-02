"""T05b W4: `branch_found`'s `ZERO_FLOW` arm and the closure rule for a `ZERO_FLOW` branch.

Spec §8 (ADR 0012 D6; amends T03 §8.2 and R-029): per split, from the state, `V = L = 0` →
`ZERO_FLOW`, `V = 0 < L` → `LIQUID`, `L = 0 < V` → `VAPOR`, else `TWO_PHASE` — under every
phase-contract literal. And because the arm applies under v1, so does spec §7.3's closure rule:
a `ZERO_FLOW` branch is admissible iff the split's feed is exactly dormant, else
`inadmissible(<stream>, zero_flow)` and a restart in the kernel's regime. A v1 dormant split
therefore converges exactly as before (B15's v1 half, `test_t05_dormant_outlet.py`).
"""

from __future__ import annotations

import pytest
from t05_support import CONTEXT, PROVIDER

from openflowsheet.orchestrator.region import (
    INADMISSIBLE_BRANCH,
    _admissible,
    syn001_lifted_splits,
)
from openflowsheet.orchestrator.roots import branch_found

COMPONENTS = ("A", "B", "C")
HEATER, FLASH = syn001_lifted_splits(COMPONENTS)


def _state(vapor: float, liquid: float, feed: tuple[float, float, float]) -> dict[str, float]:
    """The heater split's columns: `V`, `L`, the feed `S3.n`, and a temperature and pressure."""
    state = {HEATER.vapor_total: vapor, HEATER.liquid_total: liquid}
    state.update(dict(zip(HEATER.feed, feed, strict=True)))
    state.update(dict.fromkeys(HEATER.vapor, 0.0))
    state.update(dict.fromkeys(HEATER.liquid, 0.0))
    state[HEATER.temperature], state[HEATER.pressure] = 350.0, 1.0e5
    return state


@pytest.mark.parametrize(
    ("vapor", "liquid", "expected"),
    [
        (0.0, 0.0, "ZERO_FLOW"),
        (-0.0, 0.0, "ZERO_FLOW"),
        (0.0, 1.0, "LIQUID"),
        (1.0, 0.0, "VAPOR"),
        (1.0, 1.0, "TWO_PHASE"),
        # Not a root's branch; the arms are exact comparisons, never thresholds.
        (1e-300, 0.0, "VAPOR"),
    ],
)
def test_branch_found_arms(vapor: float, liquid: float, expected: str) -> None:
    assert branch_found([HEATER], _state(vapor, liquid, (0.0, 0.0, 0.0))) == [
        (HEATER.unit, expected)
    ]


def test_a_zero_flow_branch_is_admissible_iff_its_feed_is_exactly_dormant() -> None:
    dormant = _state(0.0, 0.0, (0.0, -0.0, 0.0))
    assert _admissible(PROVIDER, CONTEXT, HEATER, "ZERO_FLOW", dormant, 1e-12) == (True, 0.0)
    flowing = _state(0.0, 0.0, (0.0, 1e-20, 0.0))
    assert _admissible(PROVIDER, CONTEXT, HEATER, "ZERO_FLOW", flowing, 1e-12) == (False, 1e-20)


def test_the_inadmissible_vocabulary_names_zero_flow() -> None:
    """Spec §6.5: `zero_flow` joins `all_liquid` and `all_vapor`; a `TWO_PHASE` branch is always
    admissible, so it has no entry."""
    assert dict(INADMISSIBLE_BRANCH) == {
        "LIQUID": "all_liquid",
        "VAPOR": "all_vapor",
        "ZERO_FLOW": "zero_flow",
    }
