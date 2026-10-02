"""T04 W8: the basin-comparison harness (T04 §8.3, A23's basin clause).

W0.2 ran the harness before any count was encoded (T04 §18), and it stopped on a difference: the
implementation's traversal refused 27 of the 45 lattice guesses where the first `ref` admitted 37.
The twin judged the *mixed* feed at `T_mix`; the implemented mixer refuses an *inlet* — the recycle
guess at the flash temperature — that is not subcooled itself, which is K03 §10.1's registered
margin (`1 − Σ z_i K_i(T_f)` of the candidate). The design lane ruled the twin wrong (T04 §17 F14)
and re-registered the comparison on the mixer's rule: 27 refused, 18 admitted, A23 asserted.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from benchmarks.t04.basin import BasinComparison, basin_comparison, criterion, lattice_guesses

REPO_ROOT = Path(__file__).resolve().parents[1]
REF: dict[str, Any] = yaml.safe_load(
    (REPO_ROOT / "benchmarks" / "t04" / "reference_values.yaml").read_text()
)
REGISTERED = REF["policy_simulation"]["basin_comparison_r095"]


@pytest.fixture(scope="module")
def basin() -> BasinComparison:
    return basin_comparison()


def test_the_lattice_is_the_registered_one() -> None:
    """45 guesses, magnitude-major, in `ref`'s order: `m ∈ {0.3, 3, 30}` × the fifteen
    quarter-lattice directions on the simplex."""
    guesses = lattice_guesses()
    assert len(guesses) == len(REGISTERED) == 45
    for (magnitude, quarters, guess), entry in zip(guesses, REGISTERED, strict=True):
        assert magnitude == float(entry["magnitude_mol_per_s"])
        assert list(quarters) == entry["direction_quarters"]
        assert guess == tuple(magnitude * q / 4 for q in quarters)


def test_every_refusal_is_the_mixers_and_ref_s_refusals_are_among_them(
    basin: BasinComparison,
) -> None:
    """Every start the traversal refuses is refused by `U-MIX` with its typed status (K03 §10.1),
    never by a solve, and the refused set is exactly `ref`'s 27 (T04 §8.3 as amended, F14)."""
    refused = {(s.magnitude, s.quarters) for s in basin.starts if s.refused is not None}
    for start in basin.starts:
        if start.refused is not None:
            assert start.refused.startswith("unsupported: U-MIX:"), start.refused
            assert not start.runs
    registered = {
        (float(e["magnitude_mol_per_s"]), tuple(e["direction_quarters"]))
        for e in REGISTERED
        if e.get("start") == "refused_by_the_mixer"
    }
    assert len(registered) == 27
    assert registered == refused


def test_every_admitted_run_that_converges_is_the_p01_root_and_every_polish_is_accepted(
    basin: BasinComparison,
) -> None:
    """T04 §8.3's per-run facts, as properties of whatever the harness admits: a `CONVERGED` region
    solve by either core ends at P01's root within T02 A28's allowances, and every PTC stop's
    polish is accepted."""
    assert basin.admitted
    for start in basin.admitted:
        for core, run in start.runs.items():
            if run.outcome == "CONVERGED":
                assert run.same_root, (start.magnitude, start.quarters, core)
        assert start.runs["ptc"].polish == "accepted"


def test_a23_the_basin_comparison_is_the_registered_one(basin: BasinComparison) -> None:
    """T04 A23's basin clause (re-registered, F14): the 45 guesses, 27 refused by the mixer, the 18
    others with Newton's and PTC's outcomes, attempt signatures and counts equal `ref`, every
    converged state the P01 root."""
    for start, entry in zip(basin.starts, REGISTERED, strict=True):
        if entry.get("start") == "refused_by_the_mixer":
            assert start.refused is not None
            continue
        assert start.refused is None, (start.magnitude, start.quarters, start.refused)
        for core in ("newton", "ptc"):
            run, registered = start.runs[core], entry[core]  # type: ignore[index]
            assert run.outcome == registered["outcome"]
            assert [list(a) for a in run.attempts] == registered["attempts"]
            assert run.same_root == registered["same_root"]
            if core == "ptc":
                assert run.polish == registered["polish"]


@pytest.mark.parametrize(
    ("newton", "ptc", "verdict"),
    [
        (frozenset({1, 2, 3}), frozenset({1, 2, 3}), "experimental"),
        (frozenset({1, 2, 3}), frozenset({1, 2}), "experimental"),
        (frozenset({1, 2}), frozenset({1, 2, 3}), "qualified"),
        (frozenset({1, 2}), frozenset({3}), "qualified"),
    ],
)
def test_the_criterion_is_section_8_1s(
    newton: frozenset[int], ptc: frozenset[int], verdict: str
) -> None:
    """T04 §8.1's basin half: qualified iff PTC's success set is not contained in Newton's; else
    experimental, with V14's qualified-PTC clause incomplete."""
    fields = criterion(newton, ptc)
    assert fields["verdict"] == verdict
    assert fields["improves_a_tested_basin"] == (verdict == "qualified")
    assert fields["v14_qualified_ptc_clause"] == (
        "complete" if verdict == "qualified" else "incomplete"
    )
