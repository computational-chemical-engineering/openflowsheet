"""E-F2-7 (ADR 0062): foundation rulings Q3.A1-A3 and Q3.A6 on `openflowsheet.material.basis`.

**Every expectation is read from the reference**,
`docs/derivations/scripts/f2_basis_reference.json`, whose generator decides each case by exact
rational arithmetic on the rulings' definitions, by routes other than the module's (Bareiss ranks
and rank-nullity, breakpoint search for Q3.R1 (iii), Cramer's rule for Q3.R7, the normal equations
for Q3.R5's C, the ruling's own stated Π), imports nothing from `openflowsheet`, and refuses to
emit when a ruling's claim fails. Every comparison is exact: a verdict, an integer matrix, or a
binary64 bit for bit (`struct.pack("<d", x)`).

- Q3.A1: the true preset is A = I, R = ∅, and `b = A n` returns `n` bitwise;
- Q3.A2: (i), (ii), (iii), dim(ker A ∩ ker zᵀ) and full row rank for each of the 11 bases (the
  seven of Q3.A2's cases and the four further bases of Q3.A6), and each basis's M_g and μ
  (Q3.R7), with the electron-mass control;
- Q3.A3: the K2SO4-rich outlet is an invalid trial under the neutral reciprocal groups and
  admissible under the charged groups;
- Q3.A6: the five boundary cases, (c) in both directions, with C, Π and the dropped species, and
  the former rule's verdict on each (the control).
"""

from __future__ import annotations

import json
import random
import struct
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from openflowsheet.material.basis import (
    SpeciesBasis,
    boundary,
    check_basis,
    former_boundary_rule,
    group_amounts,
    group_molar_masses,
    negative_groups,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "docs" / "derivations" / "scripts" / "f2_basis_reference.py"
REFERENCE: dict[str, Any] = json.loads(SCRIPT.with_suffix(".json").read_text(encoding="utf-8"))
BASES: dict[str, dict[str, Any]] = REFERENCE["bases"]
BOUNDARIES: dict[str, dict[str, Any]] = REFERENCE["boundaries"]


def _bits(values: list[float] | tuple[float, ...]) -> list[bytes]:
    return [struct.pack("<d", value) for value in values]


def _basis(name: str) -> SpeciesBasis:
    entry = BASES[name]
    return SpeciesBasis(
        species=tuple(entry["species"]),
        groups=tuple(entry["groups"]),
        content=tuple(tuple(row) for row in entry["content"]),
        charges=tuple(entry["charges"]),
        reactions=tuple(tuple(Fraction(v) for v in row) for row in entry["reactions"]),
    )


def test_the_reference_is_current() -> None:
    """The committed reference is what its generator emits now (its claims all hold)."""
    done = subprocess.run(  # noqa: S603
        [sys.executable, "-I", str(SCRIPT), "--check"], capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, done.stdout + done.stderr


def test_the_reference_holds_every_case() -> None:
    assert len(BASES) == 11
    assert sorted(BOUNDARIES) == ["a", "b", "c", "c_reverse", "d", "e"]


# -- Q3.A1 --------------------------------------------------------------------------------------


def test_q3_a1_the_true_preset_is_the_identity_and_carries_amounts_bitwise() -> None:
    species = ("A", "B", "C", "D")
    true = SpeciesBasis.true_basis(species, (0, 0, 0, 0))
    assert true.groups == species
    assert true.content == ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))
    assert true.reactions == ()
    verdict = check_basis(true)
    assert verdict.valid and verdict.monotone and verdict.invariant_dimension == 0
    draw = random.Random(20261126)
    specials = [0.0, 5e-324, 2.2250738585072014e-308, 1.0, 1e300, 0.1]
    for _ in range(2000):
        n = tuple(
            draw.choice(specials)
            if draw.random() < 0.2
            else draw.uniform(0.0, 10.0) * 10.0 ** draw.randint(-30, 30)
            for _ in species
        )
        assert _bits(group_amounts(true.content, n)) == _bits(n)


# -- Q3.A2 and Q3.R7 ----------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(BASES))
def test_q3_a2_admissibility_of_each_basis(name: str) -> None:
    expected = BASES[name]["verdict"]
    verdict = check_basis(_basis(name))
    assert {
        "reactions_conserve_groups": verdict.reactions_conserve_groups,
        "invariants_fixed": verdict.invariants_fixed,
        "monotone": verdict.monotone,
        "invariant_dimension": verdict.invariant_dimension,
        "full_row_rank": verdict.full_row_rank,
    } == expected


@pytest.mark.parametrize("name", sorted(BASES))
def test_q3_r7_group_molar_masses_of_each_basis(name: str) -> None:
    expected = BASES[name]["group_masses"]
    found = group_molar_masses(_basis(name), BASES[name]["masses"])
    assert _bits(found.group_masses) == _bits(expected["group_masses"])
    assert _bits((found.mu,)) == _bits((expected["mu"],))
    assert list(found.deciding_species) == expected["deciding_species"]
    assert list(found.inconsistent) == expected["inconsistent"] == []


def test_q3_r7_the_electron_mass_shift_is_reported() -> None:
    control = REFERENCE["electron_mass_control"]
    found = group_molar_masses(_basis("a2b_nacl_solid"), control["masses"])
    assert list(found.inconsistent) == control["group_masses"]["inconsistent"] == ["NaCl"]
    assert _bits(found.group_masses) == _bits(control["group_masses"]["group_masses"])


def test_q3_r4_a_charge_row_exists_only_for_charged_groups() -> None:
    assert check_basis(_basis("a2d_charged_groups")).charge_row == tuple(
        Fraction(z) for z in BASES["a2d_charged_groups"]["charges"]
    )
    for neutral in ("a2a_nacl_apparent", "a2c_mea", "a2d_neutral_reciprocal"):
        assert check_basis(_basis(neutral)).charge_row is None


# -- Q3.A3 --------------------------------------------------------------------------------------


def test_q3_a3_negative_decomposition() -> None:
    entry = REFERENCE["negative_decomposition"]
    state = [Fraction(v) for v in entry["state"]]
    neutral, charged = _basis("a2d_neutral_reciprocal"), _basis("a2d_charged_groups")
    exact = [
        sum((x * y for x, y in zip(row, state, strict=True)), Fraction(0))
        for row in neutral.content
    ]
    assert [str(v) for v in exact] == entry["neutral_amounts"]
    assert (
        list(negative_groups(neutral.groups, exact)) == entry["neutral_negative_groups"] == ["NaCl"]
    )
    floats = tuple(float(v) for v in state)
    assert negative_groups(neutral.groups, group_amounts(neutral.content, floats)) == ("NaCl",)
    assert negative_groups(charged.groups, group_amounts(charged.content, floats)) == ()
    assert [str(Fraction(v)) for v in group_amounts(charged.content, floats)] == [
        str(Fraction(float(Fraction(v)))) for v in entry["charged_amounts"]
    ]


# -- Q3.A6 --------------------------------------------------------------------------------------


@pytest.mark.parametrize("case", sorted(BOUNDARIES))
def test_q3_a6_boundary_admissibility(case: str) -> None:
    entry = BOUNDARIES[case]
    producer, consumer = _basis(entry["producer"]), _basis(entry["consumer"])
    found = boundary(producer, consumer, entry["solid_candidates"])
    expected = entry["new_rule"]
    assert found.admitted is expected["admitted"]
    if found.admitted:
        assert [list(row) for row in found.conversion or ()] == expected["conversion"]
        assert [[name, list(image)] for name, image in found.projection] == expected["projection"]
        assert [[item.code, item.subject] for item in found.limitations] == expected["limitations"]
    else:
        assert found.conversion is None and found.reason


@pytest.mark.parametrize("case", sorted(BOUNDARIES))
def test_q3_a6_control_the_former_rule(case: str) -> None:
    entry = BOUNDARIES[case]
    found = former_boundary_rule(_basis(entry["producer"]), _basis(entry["consumer"]))
    assert found is entry["former_rule_admitted"]


def test_q3_a6_the_new_rule_admits_what_the_former_refused_only_in_a_and_d() -> None:
    differ = sorted(
        case
        for case, entry in BOUNDARIES.items()
        if entry["new_rule"]["admitted"] != entry["former_rule_admitted"]
    )
    assert differ == ["a", "d"]
