"""OPT §9 A-1: the failure branches of the phase-boundary form's (e4) and (e5) (OPT review S5),
default env.

At OPT-A3's candidate Q̂ (G10b: the certificate rank-limited, U-PHF held LIQUID at its bubble
point) `boundary.judge` is called with the clauses (e1)–(e3) as the host gives them and one
ingredient altered:

- **(e5)** the boundary split's pinned set replaced by as many *other* columns, the liquid-side
  flows (and the state zeroed there, so that (e4)'s value test does not decide first): B then
  keeps the singular direction, the incipient vapour flows, and must screen rank-limited. A
  `boundary_form` that deleted too much would pass G10a (A = ∅) and G10c unchanged;
- **(e4)** three synthetic negatives: |P| ≠ |D|, a pinned column ≠ 0.0 at the re-solve, and a
  dropped row that is alias-eliminated.

A control first: unaltered, the harness passes, as the host's own `phase_boundary` does in G10b.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from functools import cache
from typing import Any

from test_opt_boundary import Q_HAT, _a3, _at, _heater, _target

from openflowsheet.studies.nlp.boundary import BoundaryVerdict, CertificateTarget, judge
from openflowsheet.studies.nlp.host import CertifiedPoint


@cache
def _candidate() -> CertifiedPoint:
    point = _at(_a3(), Q_HAT)
    assert point.outcome == "CERTIFICATE_NOT_VERIFIED" and point.state is not None
    return point


def _judge(
    split: Any,
    *,
    state: Mapping[str, float] | None = None,
    target: CertificateTarget | None = None,
) -> BoundaryVerdict:
    """`judge` at Q̂ with A = {(`split`, LIQUID)}, the certificate's own target unless given."""
    point = _candidate()
    assert point.state is not None
    found: Sequence[tuple[Any, Any]] = ((split, "LIQUID"),)
    return judge(
        converged=True,
        certificate=point.certificate,
        policy=_a3().check_policy,
        held_signature=point.signature,
        signature=point.signature,
        state=dict(point.state if state is None else state),
        boundary=lambda: found,
        target=lambda: _target(point) if target is None else target,
    )


def test_the_unaltered_harness_passes() -> None:
    verdict = _judge(_heater(_a3(), _candidate()))
    assert verdict.passed, (verdict.clause, verdict.reason)


def test_e5_a_boundary_form_keeping_the_singular_direction_screens_rank_limited() -> None:
    point, split = _candidate(), _heater(_a3(), _candidate())
    assert point.state is not None
    other = dataclasses.replace(split, vapor=split.liquid, vapor_total=split.liquid_total)
    assert len(other.pinned("LIQUID")) == len(split.pinned("LIQUID"))
    assert set(other.pinned("LIQUID")).isdisjoint(split.pinned("LIQUID"))
    state = {**point.state, **dict.fromkeys(other.pinned("LIQUID"), 0.0)}
    verdict = _judge(other, state=state)
    assert not verdict.passed and verdict.clause == "e5", (verdict.clause, verdict.reason)
    assert verdict.form is not None
    assert verdict.form.regularity.status != "NO_RANK_LOSS_DETECTED"
    assert verdict.form.columns_removed == other.pinned("LIQUID")


def test_e4_pinned_and_dropped_sets_of_different_size() -> None:
    split = _heater(_a3(), _candidate())
    short = dataclasses.replace(split, vapor=split.vapor[:-1])
    verdict = _judge(short)
    assert not verdict.passed and verdict.clause == "e4" and "|P|" in verdict.reason


def test_e4_a_pinned_column_not_zero_at_the_resolve() -> None:
    point, split = _candidate(), _heater(_a3(), _candidate())
    assert point.state is not None
    column = split.pinned("LIQUID")[0]
    assert point.state[column] == 0.0
    verdict = _judge(split, state={**point.state, column: 1e-300})
    assert not verdict.passed and verdict.clause == "e4", (verdict.clause, verdict.reason)
    assert column in verdict.reason


def test_e4_a_dropped_row_that_is_alias_eliminated() -> None:
    point, split = _candidate(), _heater(_a3(), _candidate())
    row = split.dropped("LIQUID")[0]
    target = _target(point)
    assert row not in target.eliminated
    aliased = dataclasses.replace(target, eliminated=target.eliminated | {row})
    verdict = _judge(split, target=aliased)
    assert not verdict.passed and verdict.clause == "e4", (verdict.clause, verdict.reason)
    assert "alias-eliminated" in verdict.reason and row in verdict.reason
