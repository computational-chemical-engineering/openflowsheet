"""T08.A24: the verifier's alias-pressure-shift rule at its thresholds (T08 release spec §5.4).

ADR 0014 D5 (T06 spec §8.2) moves the pressure column at 0-based position `j` of `variable_ids` by
`997 (j + 1)` Pa — up if SYN-001's domain admits it, else down, else the alias certificates are
`unsupported(pressure_shift_outside_domain)`. §5.4's closed form: the column is certifiable iff
`997 (j + 1) <= max(200 000 - P, P - 50 000)`. The states are §9's: P = 100 kPa at `j` = 99, 100;
P = 180 kPa at `j` = 19, 20, 129, 130. The declaration is constructed: `BoundDeclaration._shifted`
reads only the declaration's `variable_ids` and `variable_kinds`, so the columns are placed exactly
where the assertion wants them, with temperature columns filling the other positions. Every value
is an exact integer in binary floating point, so the comparisons are exact.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Literal

import pytest

from openflowsheet.thermo.syn001 import P_MAX, P_MIN
from openflowsheet.verify.certificate import BoundDeclaration

Direction = Literal["up", "down", "unsupported"]


def _declaration(positions: tuple[int, ...]) -> BoundDeclaration:
    """A declaration whose pressure columns sit at `positions` of `variable_ids`."""
    size = max(positions) + 1
    names = tuple(f"P{i}" if i in positions else f"T{i}" for i in range(size))
    kinds = {name: "pressure" if name.startswith("P") else "temperature" for name in names}
    declaration = object.__new__(BoundDeclaration)
    declaration.spec = SimpleNamespace(variable_ids=names, variable_kinds=kinds)  # type: ignore[assignment]
    return declaration


def _state(positions: tuple[int, ...], pressure: float) -> dict[str, float]:
    size = max(positions) + 1
    return {
        f"P{i}" if i in positions else f"T{i}": pressure if i in positions else 300.0
        for i in range(size)
    }


def _directions(positions: tuple[int, ...], pressure: float) -> tuple[list[Direction], str]:
    state = _state(positions, pressure)
    shifted, reason = _declaration(positions)._shifted(state)
    found: list[Direction] = []
    for j in positions:
        step = 997.0 * (j + 1)
        moved = shifted[f"P{j}"]
        if moved == pressure + step:
            found.append("up")
        elif moved == pressure - step:
            found.append("down")
        else:
            assert moved == pressure and reason == "pressure_shift_outside_domain", (j, moved)
            found.append("unsupported")
    return found, reason


def _closed_form(j: int, pressure: float) -> bool:
    return 997 * (j + 1) <= max(P_MAX - pressure, pressure - P_MIN)


def test_the_shift_constant_and_domain_are_section_5_4s() -> None:
    assert BoundDeclaration.PRESSURE_SHIFT == 997.0
    assert (P_MIN, P_MAX) == (50_000.0, 200_000.0)


@pytest.mark.parametrize(
    ("pressure", "j", "expected"),
    [
        (100_000.0, 99, "up"),
        (100_000.0, 100, "unsupported"),
        (180_000.0, 19, "up"),
        (180_000.0, 20, "down"),
        (180_000.0, 129, "down"),
        (180_000.0, 130, "unsupported"),
    ],
)
def test_a24_one_pressure_column_at_the_threshold_positions(
    pressure: float, j: int, expected: Direction
) -> None:
    (direction,), reason = _directions((j,), pressure)
    assert direction == expected
    assert reason == ("pressure_shift_outside_domain" if expected == "unsupported" else "")


def test_a24_the_four_columns_at_180_kpa_in_one_declaration() -> None:
    """19, 20, 129 move up, down, down and the copy is built; adding 130 refuses it."""
    assert _directions((19, 20, 129), 180_000.0) == (["up", "down", "down"], "")
    directions, reason = _directions((19, 20, 129, 130), 180_000.0)
    assert directions[-1] == "unsupported"
    assert reason == "pressure_shift_outside_domain"


@pytest.mark.parametrize("pressure", [50_000.0, 100_000.0, 125_000.0, 180_000.0, 200_000.0])
def test_a24_the_rule_is_the_closed_form_and_monotone_to_400(pressure: float) -> None:
    """Every position 0..400 at the generator's five pressures: certifiable iff §5.4 says so, and
    the certifiable positions are a prefix (monotone in `j`)."""
    certifiable = [_directions((j,), pressure)[1] == "" for j in range(401)]
    assert certifiable == [_closed_form(j, pressure) for j in range(401)]
    first_unsupported = certifiable.index(False)
    assert not any(certifiable[first_unsupported:])
    assert (
        first_unsupported
        == {
            50_000.0: 150,
            100_000.0: 100,
            125_000.0: 75,
            180_000.0: 130,
            200_000.0: 150,
        }[pressure]
    )
