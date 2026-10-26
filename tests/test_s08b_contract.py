"""S08b (a) — signature items by declaration (design note `docs/derivations/S08b-design.md` §5.1,
§7 A1–A4 and A7; R-790), and the items `_proposal` hands `choose` (S08b review F2).

A signature entry is a dormancy-form item iff its key is one of the attempt's declared items;
every other entry is a signature unit, whatever its spelling — S01 cascade and column stage ids
contain `.` (`S02.stage.4`) and are units. The guards that the T05b rule keeps its values (A5) are
`test_t05b_dormancy.py` and `test_t05b_zero_flow.py`; P1's pinned message (A6) is S02 A12's and
S08 A06's.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from openflowsheet.numerics.newton import NewtonResult
from openflowsheet.orchestrator.phase_contract import (
    Candidate,
    Conversion,
    WallObserver,
    _changes,
    _proposal,
    adjacent,
)
from openflowsheet.orchestrator.region import (
    DormancyForm,
    LiftedSplit,
    _LiftedOps,
    _units_and_items_disjoint,
)
from openflowsheet.orchestrator.trace import Counters, SolvePolicy

STAGE_1_2P = ("S.stage.1", "TWO_PHASE")
LIQUID = (STAGE_1_2P, ("S.stage.2", "LIQUID"))
TWO_PHASE = (STAGE_1_2P, ("S.stage.2", "TWO_PHASE"))
VAPOR = (STAGE_1_2P, ("S.stage.2", "VAPOR"))
POLICY = SolvePolicy(policy_id="S08b", residual_tolerances={}, scales={})


def test_a1_dotted_unit_ids_are_units() -> None:
    """A1: with no declared items, dotted stage ids are judged by T03 §4.4's lattice."""
    none: frozenset[str] = frozenset()
    assert adjacent(LIQUID, TWO_PHASE, items=none)
    assert adjacent(TWO_PHASE, LIQUID, items=none)
    assert not adjacent(LIQUID, VAPOR, items=none)  # LIQUID -> VAPOR is two steps
    assert not adjacent(LIQUID, LIQUID, items=none)  # identical: nothing different
    assert not adjacent(LIQUID, (STAGE_1_2P,), items=none)  # different stage lists
    assert not adjacent(LIQUID, (("S.stage.2", "LIQUID"), STAGE_1_2P), items=none)  # order


def test_a1_items_is_keyword_only_and_required() -> None:
    """§5.1: a forgotten `items` must not silently turn items into units."""
    with pytest.raises(TypeError):
        adjacent(LIQUID, TWO_PHASE)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        adjacent(LIQUID, TWO_PHASE, frozenset())  # type: ignore[misc]


def test_a2_the_change_list_names_the_stages() -> None:
    """A2: with `declared = {}` each changed stage is listed, in signature order, `", "`-joined."""
    assert _changes(LIQUID, TWO_PHASE, {}) == "S.stage.2:LIQUID->TWO_PHASE"
    three = (("S.stage.1", "LIQUID"), ("S.stage.2", "TWO_PHASE"), ("S.stage.3", "VAPOR"))
    moved = (("S.stage.1", "TWO_PHASE"), ("S.stage.2", "TWO_PHASE"), ("S.stage.3", "TWO_PHASE"))
    assert _changes(three, moved, {}) == "S.stage.1:LIQUID->TWO_PHASE, S.stage.3:VAPOR->TWO_PHASE"


def test_a3_a_mixed_signature() -> None:
    """A3: a column stage with a pump's dormancy item; only the declared key is an item."""
    declared = {"U-PUMP.outlet": "LIQUID"}
    frozen = (("C.stage.1", "TWO_PHASE"), ("U-PUMP.outlet", "ZERO_FLOW"))
    other = (("C.stage.1", "LIQUID"),)
    assert adjacent(frozen, other, items={"U-PUMP.outlet"})
    assert adjacent(other, frozen, items=frozenset(declared))
    assert _changes(frozen, other, declared) == (
        "C.stage.1:TWO_PHASE->LIQUID, U-PUMP.outlet:ZERO_FLOW->LIQUID"
    )
    # Without the declaration the pump's entry is a unit: the unit lists differ.
    assert not adjacent(frozen, other, items=frozenset())


def test_a4_choose_prefers_the_adjacent_candidate_on_dotted_ids() -> None:
    """A4 (ADR 0005 D4 for columns): the first candidate moves a stage `LIQUID -> VAPOR` (not
    adjacent), the second is adjacent; `choose` returns the second. Before S08b every dotted entry
    was an "item", nothing was adjacent, and the first was returned."""
    wall = WallObserver(POLICY)
    x = np.zeros(2)
    wall.rejected(3, 0.5, x, "phase_update_required", VAPOR)
    wall.rejected(3, 0.25, x, "phase_update_required", TWO_PHASE)
    chosen = wall.choose(LIQUID, items=frozenset())
    assert chosen is wall.candidates[1]
    assert chosen is not None and chosen.signature == TWO_PHASE and chosen.alpha == 0.25
    # With no adjacent candidate, the first (largest α) is still the answer (T03 §4.5).
    alone = WallObserver(POLICY)
    alone.rejected(3, 0.5, x, "phase_update_required", VAPOR)
    assert alone.choose(LIQUID, items=frozenset()) is alone.candidates[0]


class _PumpOps:
    """A lifted `PathOps` with one declared dormancy item; only `at_candidate` may be asked."""

    lifted = True
    declared_phases = {"U-PUMP.outlet": "LIQUID"}

    def at_candidate(self, candidate: Candidate, cause: str) -> Conversion:
        return Conversion(
            candidate.signature, "candidate", "phase_rejected_trial", cause, trial=candidate
        )

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"_proposal asked {name}")


@pytest.mark.parametrize(
    ("outcome", "row"), [("PHASE_UPDATE_REQUIRED", "patience"), ("LINE_SEARCH_FAILED", "stall")]
)
def test_f2_proposal_hands_choose_the_declared_items(outcome: str, row: str) -> None:
    """Review F2: both of `_proposal`'s `choose` calls pass the declared items. The first wall
    candidate moves a stage `LIQUID -> VAPOR` (not adjacent); the second adds the pump's entry,
    adjacent only if that entry is an item. Items dropped at either call return the first."""
    frozen = (("C.stage.1", "LIQUID"),)
    pumped = (("C.stage.1", "LIQUID"), ("U-PUMP.outlet", "ZERO_FLOW"))
    wall = WallObserver(POLICY)
    x = np.zeros(2)
    wall.rejected(3, 0.5, x, "phase_update_required", (("C.stage.1", "VAPOR"),))
    wall.rejected(3, 0.25, x, "phase_update_required", pumped)
    result = NewtonResult(
        outcome=outcome,  # type: ignore[arg-type]
        x=x,
        residual=(0.0,),
        residual_inf=0.0,
        merit=0.0,
        iterations=4,
        counters=Counters(),
    )
    conversion = _proposal(result, frozen, wall, _PumpOps())  # type: ignore[arg-type]
    assert conversion is not None and conversion.trial is wall.candidates[1]
    assert conversion.cause == f"phase_wall({row}, U-PUMP.outlet:LIQUID->ZERO_FLOW)"


def _split(unit: str) -> LiftedSplit:
    return LiftedSplit(unit, "S", (), "T", "P", (), (), "V", "L", (), "v", "l")


def _form(item: str) -> DormancyForm:
    unit, port = item.rsplit(".", 1)
    return DormancyForm(
        item, unit, port, "inlet", "S", (), (), (), "row", ("r", "T", "T0"), "LIQUID"
    )


def test_a7_lifted_units_and_dormancy_items_are_disjoint() -> None:
    """A7: a lifted unit id equal to a dormancy item key is a defect; disjoint pairs pass."""
    stages = [_split(f"C.stage.{j}") for j in (1, 2, 3)]
    assert _units_and_items_disjoint(stages, [_form("U-PUMP.outlet")]) is None
    assert _units_and_items_disjoint(stages, []) is None
    assert _units_and_items_disjoint([], [_form("U-PUMP.outlet")]) is None
    with pytest.raises(ValueError, match=r"^defect: \['U-PUMP.outlet'\]"):
        _units_and_items_disjoint([*stages, _split("U-PUMP.outlet")], [_form("U-PUMP.outlet")])
    # `_LiftedOps` runs the check on construction; nothing before it reads the other arguments.
    unused: Any = None
    with pytest.raises(ValueError, match=r"^defect: \['U-PUMP.outlet'\]"):
        _LiftedOps(
            splits=[*stages, _split("U-PUMP.outlet")],
            regimes={},
            end_state={},
            free=(),
            provider=unused,
            context=unused,
            policy=POLICY,
            region=unused,
            spec=unused,
            identity=("", ""),
            dormancy=[_form("U-PUMP.outlet")],
        )
