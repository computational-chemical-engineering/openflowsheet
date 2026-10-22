"""C8 — the "multiple steady states possible" warning on duty-only column specifications
(Frank, Q-S02-4; S02 spec §18.1 item 3 and §14). The warning is decided from the specification
alone and rides on `ColumnSolution.warnings` / `CascadeFailure.warnings`; no numerics, state hash
or record identity moves. The expected duty-only sets are read off the registered cases and
variants of `docs/derivations/S02-spec.md` §9 (`ref.variants`), not computed by the function."""

from __future__ import annotations

from dataclasses import replace

import pytest
from test_s02_column_wo1 import PROVIDER, REFERENCE, SPECS, _variant
from test_s02_column_wo2b import R2, solved

from openflowsheet.models.syn001.cascade import CascadeFailure
from openflowsheet.models.syn001.column import (
    MULTIPLE_STEADY_STATES_WARNING,
    ColumnSpec,
    EndSpecification,
    column_warnings,
)
from openflowsheet.models.syn001.column_solve import ColumnSolution, solve_column

WARNING = ("multiple_steady_states_possible(duty_only)",)

#: Registered specification sets whose every end specification is a duty: V-M1 and V-M2
#: `(duty, duty)`, M3 (its reboiler duty is its only end) and its phase case P1.
DUTY_ONLY: tuple[tuple[str, str | None], ...] = (
    ("M1", "duty+duty"),
    ("M2", "duty+duty"),
    ("M3", None),
    ("P1", None),
)
#: Every other registered set: the four cases (M4's single end is a distillate rate) and the
#: variants with at least one ratio or rate specification.
NOT_DUTY_ONLY: tuple[tuple[str, str | None], ...] = (
    ("M1", None),
    ("M2", None),
    ("M4", None),
    *(
        (case, variant)
        for case in ("M1", "M2")
        for variant in REFERENCE["variants"][case]
        if variant != "duty+duty"
    ),
)


def _spec(case: str, variant: str | None) -> ColumnSpec:
    return SPECS[case] if variant is None else _variant(case, variant)


def test_the_warning_text_is_the_stable_code() -> None:
    assert (MULTIPLE_STEADY_STATES_WARNING,) == WARNING


def test_the_partition_is_the_registered_sets() -> None:
    """The two lists above cover every registered case and variant exactly once."""
    registered = {(case, None) for case in SPECS} | {
        (case, variant) for case in ("M1", "M2") for variant in REFERENCE["variants"][case]
    }
    assert set(DUTY_ONLY) | set(NOT_DUTY_ONLY) == registered
    assert not set(DUTY_ONLY) & set(NOT_DUTY_ONLY)


@pytest.mark.parametrize(("case", "variant"), DUTY_ONLY)
def test_every_duty_only_set_carries_exactly_the_warning(case: str, variant: str | None) -> None:
    spec = _spec(case, variant)
    assert all(spec.end_specification(end).kind == "duty" for end in spec.ends())  # type: ignore[union-attr]
    assert column_warnings(spec) == WARNING


@pytest.mark.parametrize(("case", "variant"), NOT_DUTY_ONLY)
def test_no_other_set_carries_a_warning(case: str, variant: str | None) -> None:
    assert column_warnings(_spec(case, variant)) == ()


def test_a_mixed_specification_is_the_negative_control() -> None:
    """M1 with one duty end and one ratio end (`reflux_ratio+duty`), and the same pair swapped."""
    mixed = replace(SPECS["M1"], reboiler_spec=EndSpecification("duty", 1.0e4))
    swapped = replace(
        SPECS["M1"],
        condenser_spec=EndSpecification("duty", -1.0e4),
        reboiler_spec=EndSpecification("boilup_ratio", 1.5),
    )
    assert column_warnings(mixed) == () and column_warnings(swapped) == ()


def test_a_column_without_ends_has_no_warning() -> None:
    """`all([])` is true, but a column with no end specification is not a duty specification."""
    bare = replace(
        SPECS["M3"], reboiler="none", reboiler_spec=None, duties=(0.0,) * SPECS["M3"].stage_count
    )
    assert bare.ends() == ()
    assert column_warnings(bare) == ()


@pytest.mark.parametrize(("case", "variant"), [pair for pair in DUTY_ONLY if pair[0] != "P1"])
def test_the_converged_answer_of_a_duty_only_set_carries_the_warning(
    case: str, variant: str | None
) -> None:
    answer = solved(case, variant)
    assert answer.outcome == "CONVERGED"
    assert answer.warnings == WARNING


def test_the_warning_is_on_v_m2_duty_duty_r2() -> None:
    """The set whose returned root is `R2`, not M2's (S02 §18.1 item 3, A07, A21)."""
    answer = solved(*R2)
    assert answer.outcome == "CONVERGED"
    assert answer.warnings == WARNING


@pytest.mark.parametrize(("case", "variant"), [("M1", None), ("M1", "reflux_ratio+duty")])
def test_the_converged_answer_of_another_set_carries_none(case: str, variant: str | None) -> None:
    answer = solved(case, variant)
    assert isinstance(answer, ColumnSolution)
    assert answer.warnings == ()


def test_a_failure_for_a_duty_only_spec_carries_the_warning() -> None:
    """S02 A02's `R7-duty-duty`: H* outside its domain, refused before any solve."""
    spec = replace(_variant("M1", "duty+duty"), condenser_spec=EndSpecification("duty", -1.0e7))
    failure = solve_column(spec, PROVIDER)
    assert isinstance(failure, CascadeFailure)
    assert failure.cause == "infeasible_spec(energy_outside_domain)"
    assert failure.warnings == WARNING


def test_a_failure_for_another_spec_carries_none() -> None:
    failure = solve_column(replace(SPECS["M1"], condenser="subcooled"), PROVIDER)
    assert isinstance(failure, CascadeFailure)
    assert failure.warnings == ()
