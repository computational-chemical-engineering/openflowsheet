"""F3-WO5a: reaction consistency (ADR 0061 D7, Q7.A3), exit test E-F3-10 [gen].

The records are the legacy import's (`m01`, `l01`, `s10`). Every expectation comes from the ADR:
the three stated ratios |Σ ν M| / Σ |ν M| (6.4e-18, 3.6e-17, 7.8e-6) are recomputed here from the
legacy YAML files' `molecular_weight` values, exactly, and compared with the ADR's two digits and
with 4ε, never read from the module. The generated reactions are balanced by construction (an
integer null-space basis of each file's element matrix, computed here with `Fraction`s).
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping
from fractions import Fraction
from functools import cache
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT

from openflowsheet.records.importers import legacy
from openflowsheet.records.reactions import check_reactions
from openflowsheet.registry.tokens import Coded

#: D7: 4ε, ε = 2⁻⁵².
TOLERANCE = 4 * Fraction(1, 2**52)
AMMONIA: dict[str, Any] = {
    "id": "ammonia_synthesis",
    "stoichiometry": {"N2": -1, "H2": -3, "NH3": 2},
}
WATER: dict[str, Any] = {"id": "water_formation", "stoichiometry": {"H2": -2, "O2": -1, "H2O": 2}}
#: E-F3-10: one atomic-weight table per file.
GENERATED_FILES = ("m01", "l01", "s10")
GENERATED = 1000
#: The dimension of each file's reaction space: components less the rank of the element matrix
#: (m01: N2 + 3 H2 -> 2 NH3 only; l01: H2, CH4, H2O, CO2, O2, C2H6, C3H8 over C, H, O;
#: s10: 2 CH3OH -> C2H5OH + H2O only).
REACTION_SPACE = {"m01": 1, "l01": 4, "s10": 1}


@cache
def _components(profile: str) -> dict[str, Mapping[str, Any]]:
    """The legacy import's component records of `profile`, by id."""
    found = legacy.profile_named(profile)
    imported = legacy.import_file(found, (REPO_ROOT / found.file).read_bytes())
    return {
        outcome.record["id"]: outcome.record
        for outcome in imported.records
        if outcome.record["record_type"] == "component"
    }


@cache
def _file_masses(profile: str) -> dict[str, float]:
    """The `molecular_weight` values of `profile`'s YAML file, by component id."""
    document = yaml.safe_load((REPO_ROOT / legacy.profile_named(profile).file).read_bytes())
    return {c["id"]: c["molecular_weight"]["value"] for c in document["components"]}


def _ratio(terms: list[tuple[int, float]]) -> Fraction:
    products = [Fraction(nu) * Fraction(mass) for nu, mass in terms]
    return abs(sum(products, Fraction(0))) / sum((abs(p) for p in products), Fraction(0))


def _two_digits(ratio: Fraction) -> float:
    """`ratio` to the ADR's two significant digits."""
    return float(f"{float(ratio):.1e}")


def _notice(reaction: str) -> Coded:
    return Coded("molar_mass_inconsistent", {"reaction": reaction})


def _with(record: Mapping[str, Any], **members: Any) -> dict[str, Any]:
    return {**record, **members}


# -- the three stated reactions -------------------------------------------------------------------


def test_e_f3_10_ammonia_on_m01_passes_all_three_checks() -> None:
    masses = _file_masses("m01")
    ratio = _ratio([(-1, masses["N2"]), (-3, masses["H2"]), (2, masses["NH3"])])
    assert _two_digits(ratio) == 6.4e-18
    assert ratio <= TOLERANCE
    assert check_reactions([AMMONIA], _components("m01")) == ((), ())


def test_e_f3_10_water_on_l01_passes() -> None:
    masses = _file_masses("l01")
    ratio = _ratio([(-2, masses["H2"]), (-1, masses["O2"]), (2, masses["H2O"])])
    assert _two_digits(ratio) == 3.6e-17
    assert ratio <= TOLERANCE
    assert check_reactions([WATER], _components("l01")) == ((), ())


def test_e_f3_10_water_over_two_atomic_weight_tables_is_a_notice_not_a_refusal() -> None:
    l01, s10 = _file_masses("l01"), _file_masses("s10")
    ratio = _ratio([(-2, l01["H2"]), (-1, l01["O2"]), (2, s10["H2O"])])
    assert _two_digits(ratio) == 7.8e-6
    assert ratio > TOLERANCE
    mixed = {"H2": _components("l01")["H2"], "O2": _components("l01")["O2"]}
    mixed["H2O"] = _components("s10")["H2O"]
    assert check_reactions([WATER], mixed) == ((), (_notice("water_formation"),))


# -- 10³ generated balanced reactions [gen] -------------------------------------------------------


def _null_space(matrix: list[list[Fraction]]) -> list[list[int]]:
    """An integer basis of the null space of `matrix` (rows: elements, columns: components), by
    reduction to row echelon form over the rationals."""
    rows = [row[:] for row in matrix]
    columns = len(rows[0]) if rows else 0
    pivots: list[int] = []
    rank = 0
    for column in range(columns):
        found = next((r for r in range(rank, len(rows)) if rows[r][column] != 0), None)
        if found is None:
            continue
        rows[rank], rows[found] = rows[found], rows[rank]
        rows[rank] = [value / rows[rank][column] for value in rows[rank]]
        for r in range(len(rows)):
            if r != rank and rows[r][column] != 0:
                factor = rows[r][column]
                rows[r] = [a - factor * b for a, b in zip(rows[r], rows[rank], strict=True)]
        pivots.append(column)
        rank += 1
    basis = []
    for free in (c for c in range(columns) if c not in pivots):
        vector = [Fraction(0)] * columns
        vector[free] = Fraction(1)
        for r, column in enumerate(pivots):
            vector[column] = -rows[r][free]
        scale = math.lcm(*(v.denominator for v in vector))
        basis.append([int(v * scale) for v in vector])
    return basis


def _balanced(profile: str, rng: random.Random, number: int) -> dict[str, Any]:
    """A random balanced reaction over `profile`'s components: a random integer combination of
    the null-space basis, divided by a random power of two (exact in binary64)."""
    records = _components(profile)
    keys = sorted(records)
    elements = sorted({e for record in records.values() for e in record["elements"]})
    matrix = [[Fraction(records[k]["elements"].get(e, 0)) for k in keys] for e in elements]
    basis = _null_space(matrix)
    assert len(basis) == REACTION_SPACE[profile]
    nu = [0] * len(keys)
    while not any(nu):
        weights = [rng.randint(-4, 4) for _ in basis]
        nu = [sum(w * b[i] for w, b in zip(weights, basis, strict=True)) for i in range(len(keys))]
    scale = 2 ** rng.randint(0, 3)
    for e in range(len(elements)):  # balanced by construction, checked here
        assert sum(n * matrix[e][i] for i, n in enumerate(nu)) == 0
    stoichiometry = {k: n / scale for k, n in zip(keys, nu, strict=True) if n}
    return {"id": f"{profile}-{number}", "stoichiometry": stoichiometry}


def test_e_f3_10_generated_balanced_reactions_within_one_file_pass() -> None:
    """[gen] 10³ balanced reactions, each within the `m01`, the `l01` or the `s10` records (one
    atomic-weight table each), pass all three checks; none over `s07` is asserted."""
    rng = random.Random(20261118)
    reactions: dict[str, list[dict[str, Any]]] = {profile: [] for profile in GENERATED_FILES}
    for number in range(GENERATED):
        profile = GENERATED_FILES[number % len(GENERATED_FILES)]
        reactions[profile].append(_balanced(profile, rng, number))
    assert sum(len(found) for found in reactions.values()) == GENERATED
    for profile, found in reactions.items():
        assert check_reactions(found, _components(profile)) == ((), ()), profile


# -- what refuses and what notices ----------------------------------------------------------------


@pytest.mark.parametrize(("profile", "reaction"), [("m01", AMMONIA), ("l01", WATER)])
@pytest.mark.parametrize("which", [0, 1, 2])
def test_e_f3_10_one_molar_mass_scaled_by_one_plus_1e_9_is_a_notice(
    profile: str, reaction: Mapping[str, Any], which: int
) -> None:
    records = dict(_components(profile))
    key = list(reaction["stoichiometry"])[which]
    mass = records[key]["molar_mass"]
    records[key] = _with(records[key], molar_mass={**mass, "value": mass["value"] * (1 + 1e-9)})
    assert check_reactions([reaction], records) == ((), (_notice(reaction["id"]),))


@pytest.mark.parametrize("element", ["N", "H"])
def test_e_f3_10_one_element_count_off_is_an_element_imbalance(element: str) -> None:
    records = dict(_components("m01"))
    nh3 = records["NH3"]
    records["NH3"] = _with(nh3, elements={**nh3["elements"], element: nh3["elements"][element] + 1})
    errors, findings = check_reactions([AMMONIA], records)
    assert errors == (
        Coded("reaction_element_imbalance", {"reaction": "ammonia_synthesis", "element": element}),
    )
    assert findings == ()


def test_a_charged_record_is_a_charge_imbalance() -> None:
    records = dict(_components("l01"))
    records["H2O"] = _with(records["H2O"], charge=1)
    assert check_reactions([WATER], records) == (
        (Coded("reaction_charge_imbalance", {"reaction": "water_formation"}),),
        (),
    )


def test_a_component_without_elements_leaves_the_element_balance_unchecked() -> None:
    records = dict(_components("m01"))
    records["NH3"] = {k: v for k, v in records["NH3"].items() if k != "elements"}
    records["N2"] = _with(records["N2"], elements=None)
    off = {**AMMONIA, "stoichiometry": {**AMMONIA["stoichiometry"], "H2": -4}}
    errors, findings = check_reactions([off], records)
    assert errors == ()  # H is off by 2, but the balance is not judged
    assert findings == (
        _notice("ammonia_synthesis"),
        Coded("reaction_element_unchecked", {"reaction": "ammonia_synthesis", "component": "N2"}),
        Coded("reaction_element_unchecked", {"reaction": "ammonia_synthesis", "component": "NH3"}),
    )


def test_findings_are_sorted_across_reactions() -> None:
    records = dict(_components("l01"))
    records["H2O"] = _with(records["H2O"], charge=1, elements={"H": 2, "O": 2})
    second = {**WATER, "id": "a_second"}
    errors, _ = check_reactions([WATER, second], records)
    assert [(e.code, e.params["reaction"]) for e in errors] == [
        ("reaction_charge_imbalance", "a_second"),
        ("reaction_charge_imbalance", "water_formation"),
        ("reaction_element_imbalance", "a_second"),
        ("reaction_element_imbalance", "water_formation"),
    ]


@pytest.mark.parametrize("nu", [True, "2", float("nan"), float("inf"), None])
def test_a_coefficient_that_is_not_a_finite_number_is_a_callers_error(nu: object) -> None:
    reaction = {"id": "r", "stoichiometry": {"H2": nu}}
    with pytest.raises(ValueError, match="r: ν of H2"):
        check_reactions([reaction], _components("l01"))


def test_a_key_without_a_record_is_a_callers_error() -> None:
    with pytest.raises(ValueError, match="no record for component key 'NH3'"):
        check_reactions([AMMONIA], {k: v for k, v in _components("m01").items() if k != "NH3"})


def test_a_rational_coefficient_is_taken_exactly_and_its_double_is_not() -> None:
    """R-1054 (F3 review 2, S5, C7): ν may be a `Fraction` (F2's rational coefficients); a third
    as a double is not a third, so the same reaction in doubles is an element imbalance in H
    (3 · fl(2/3) ≠ 2; N balances, as fl(2/3) = 2 · fl(1/3))."""
    rational = {"N2": Fraction(-1, 3), "H2": Fraction(-1), "NH3": Fraction(2, 3)}
    reaction = {"id": "third", "stoichiometry": rational}
    assert check_reactions([reaction], _components("m01")) == ((), ())
    doubles = {"id": "third", "stoichiometry": {k: float(v) for k, v in rational.items()}}
    errors, _ = check_reactions([doubles], _components("m01"))
    assert errors == (Coded("reaction_element_imbalance", {"reaction": "third", "element": "H"}),)
