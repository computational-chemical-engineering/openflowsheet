"""S08b (b): S02 §8 item 6's saturation consistency for S01 cascades (S08b-design §5.2, §7 B1–B3).

`TWO_PHASE_SATURATION_TOLERANCE` and the body of the column's saturation pairs moved to
`cascade_solve` (`saturation_pairs`); S01 §8 gains the clause (Amendment 2, R-791) under
`SATURATION_PREFIX`, and the column delegates to the same function.

- B1 (wiring): with the cascade tolerance patched to `-1.0`, `solve_cascade(C2)` raises
  `AcceptanceDefectError` with exactly the six saturation strings of its three stages.
- B2 (margin, regression): on C1–C5 as registered, the largest error ≤ 1e-5 K (the value is
  printed and recorded in the S08b evidence manifest).
- B3 (columns unchanged): the column's `_saturation_pairs` equals `cascade_solve.saturation_pairs`
  bitwise at F1's Stage-A state and at J8's root; the tolerance is one object, not a copy.
"""

from __future__ import annotations

import re

import pytest
from test_s01_cascade_wo1 import CASES, REFERENCE, UNIT, _spec
from test_s01_cascade_wo2 import PROVIDER, solved
from test_s02_column_wo1 import PROVIDER as COLUMN_PROVIDER
from test_s06_column_wo1 import J_CASES
from test_s08_item6 import _regimes, _stage_a_f1

import openflowsheet.models.syn001.cascade_solve as cascade_solve_module
import openflowsheet.models.syn001.column_solve as column_solve_module
from openflowsheet.models.syn001.cascade_solve import (
    SATURATION_PREFIX,
    TWO_PHASE_SATURATION_TOLERANCE,
    AcceptanceDefectError,
    saturation_pairs,
    solve_cascade,
)
from openflowsheet.models.syn001.column_solve import ColumnSolution, solve_column

_FAILURE = re.compile(r"§8 saturation: TWO_PHASE stage (\d+): (bubble|dew) error (\S+) K")


def _cascade_pairs(case: str) -> dict[int, tuple[float, float]]:
    spec = _spec(REFERENCE["cases"][case])
    answer = solved(case)
    regimes = dict(enumerate(answer.signature, start=1))
    return saturation_pairs(UNIT, spec.components, PROVIDER, answer.state, regimes)


def _bits(pairs: dict[int, tuple[float, float]]) -> dict[int, tuple[str, str]]:
    return {stage: (bubble.hex(), dew.hex()) for stage, (bubble, dew) in pairs.items()}


def test_the_constants_are_the_registered_ones_and_moved_not_copied() -> None:
    assert TWO_PHASE_SATURATION_TOLERANCE == 1e-4
    assert SATURATION_PREFIX == "§8 saturation: "
    assert column_solve_module.TWO_PHASE_SATURATION_TOLERANCE is TWO_PHASE_SATURATION_TOLERANCE
    assert column_solve_module.saturation_pairs is saturation_pairs


def test_b1_a_patched_tolerance_raises_exactly_the_six_saturation_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Kills: the clause left out of `acceptance_failures`, or not reached from `solve_cascade`."""
    expected = _cascade_pairs("C2")
    assert set(expected) == {1, 2, 3}
    monkeypatch.setattr(cascade_solve_module, "TWO_PHASE_SATURATION_TOLERANCE", -1.0)
    with pytest.raises(AcceptanceDefectError) as raised:
        solve_cascade(_spec(REFERENCE["cases"]["C2"]), PROVIDER)
    failures = raised.value.failures
    assert len(failures) == 6, failures
    assert all(failure.startswith(SATURATION_PREFIX) for failure in failures), failures
    assert failures == tuple(
        f"§8 saturation: TWO_PHASE stage {stage}: {side} error {error!r} K"
        for stage in (1, 2, 3)
        for side, error in zip(("bubble", "dew"), expected[stage], strict=True)
    )
    assert all(_FAILURE.fullmatch(failure) for failure in failures), failures


def test_b2_every_registered_cascade_root_passes_with_margin() -> None:
    worst = 0.0
    for case in CASES:
        pairs = _cascade_pairs(case)
        assert pairs, case  # every registered case has a TWO_PHASE stage
        worst = max(worst, *(max(errors) for errors in pairs.values()))
    # §7 B2's bound; the value is recorded in the S08b evidence manifest.
    print(f"S08b.B2 worst registered S01 saturation error {worst!r} K")
    assert worst <= 1e-5


def test_b3_the_column_pairs_are_the_cascade_function_at_f1_stage_a() -> None:
    spec, provider, _, state, regimes = _stage_a_f1()
    column = column_solve_module._saturation_pairs(spec, provider, state, regimes)
    cascade = saturation_pairs(spec.unit_id, spec.components, provider, state, regimes)
    assert _bits(column) == _bits(cascade)
    assert column[4][0] >= 0.3 or column[4][1] >= 0.3  # S08 §3 F1's 0.379 K at stage 4


def test_b3_the_column_pairs_are_the_cascade_function_at_j8() -> None:
    spec = J_CASES["J8"]
    answer = solve_column(spec, COLUMN_PROVIDER)
    assert isinstance(answer, ColumnSolution) and answer.outcome == "CONVERGED"
    regimes = _regimes(spec, answer)
    column = column_solve_module._saturation_pairs(spec, COLUMN_PROVIDER, answer.state, regimes)
    cascade = saturation_pairs(
        spec.unit_id, spec.components, COLUMN_PROVIDER, answer.state, regimes
    )
    assert column, "J8 has a TWO_PHASE stage"
    assert _bits(column) == _bits(cascade)
