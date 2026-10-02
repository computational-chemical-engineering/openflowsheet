"""T05: a non-finite numeric constructor input is refused at construction (spec §3.5, §5.1 as
amended; ruling round §3 block, engineers' interpretation U1 (2); review N6).

The table runs over the six T05 constructors × every numeric constructor input (each component
of a vector input separately) × `{nan, +inf, -inf}`. Each is built from its model's nominal
registered instance (`test_t05_manifests.MODELS`) with one field replaced; `dataclasses.replace`
re-runs the constructor's checks. The expectation is the registered code where one applies — an
interval or domain test that the value fails (the valve's and the pump's outlet pressure, the
pump's efficiency, a split fraction, the conversion, the stoichiometry's ordered checks of §6.2)
— and `ValueError` where none does (spec §3.5: the PH flash's `Q_spec` and `pressure_drop`,
§5.1; the reactor's and the exchanger's specified values; the reactor's pressure drop and its
molar masses, which no registered code names).

Before the ruling round the PH flash accepted every non-finite `duty` and a NaN or `+inf`
`pressure_drop`, and the reactor accepted a `+inf` `pressure_drop` and an infinite molar mass.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any

import pytest
from t05_support import first_line
from test_t05_manifests import MODELS

from openflowsheet.models import SpecificationError, UnitModel

NON_FINITE = {"nan": math.nan, "+inf": math.inf, "-inf": -math.inf}

#: `(model id, configuration changes, field, component index or None, value label)` →
#: the registered code, or `None` for `ValueError`.
Expectation = str | None


def _row(
    model_id: str,
    field: str,
    index: int | None,
    expected: dict[str, Expectation] | Expectation,
    changes: dict[str, Any] | None = None,
) -> list[Any]:
    by_value = expected if isinstance(expected, dict) else dict.fromkeys(NON_FINITE, expected)
    suffix = "" if index is None else f"[{index}]"
    configured = "" if not changes else "-" + "-".join(map(str, changes.values()))
    return [
        pytest.param(
            model_id,
            changes or {},
            field,
            index,
            label,
            by_value[label],
            id=f"{model_id}{configured}.{field}{suffix}={label}",
        )
        for label in NON_FINITE
    ]


MASS = "stoichiometry_not_mass_conserving"
TABLE = [
    # syn001.ph_flash (§5.1): no registered code applies; ValueError.
    *_row("syn001.ph_flash", "duty", None, None),
    *_row("syn001.ph_flash", "pressure_drop", None, None),
    # syn001.valve (§8): the domain test on P_spec.
    *_row("syn001.valve", "outlet_pressure", None, "pressure_outside_domain(outlet_pressure)"),
    # syn001.liquid_pump (§9.1).
    *_row(
        "syn001.liquid_pump", "outlet_pressure", None, "pressure_outside_domain(outlet_pressure)"
    ),
    *_row("syn001.liquid_pump", "efficiency", None, "efficiency_outside_interval"),
    # syn001.component_separator (§7): every component's fraction.
    *(
        row
        for index, component in enumerate(("A", "B", "C"))
        for row in _row(
            "syn001.component_separator",
            "split",
            index,
            f"split_fraction_outside_unit_interval({component})",
        )
    ),
    # syn001.heat_exchanger (§10.1): the specified value, in each specification mode; ValueError.
    *(
        row
        for mode in ("cold_outlet_temperature", "hot_outlet_temperature", "duty")
        for row in _row("syn001.heat_exchanger", "value", None, None, {"specification": mode})
    ),
    # syn001.conversion_reactor (§6.2), nominal RX-1: key A, nu = (-2, -1, 3).
    # The key's coefficient: `nu_k < 0` (key_not_reactant) is tested before the mass balance,
    # and NaN and +inf fail it; -inf passes it and leaves the mass balance undefined.
    *_row(
        "syn001.conversion_reactor",
        "stoichiometry",
        0,
        {"nan": "key_not_reactant", "+inf": "key_not_reactant", "-inf": MASS},
    ),
    *_row("syn001.conversion_reactor", "stoichiometry", 1, MASS),
    *_row("syn001.conversion_reactor", "stoichiometry", 2, MASS),
    *_row("syn001.conversion_reactor", "conversion", None, "conversion_outside_unit_interval"),
    *(
        row
        for mode in ("outlet_temperature", "duty")
        for row in _row(
            "syn001.conversion_reactor", "value", None, None, {"energy_specification": mode}
        )
    ),
    *_row("syn001.conversion_reactor", "pressure_drop", None, None),
    *(
        row
        for index in range(3)
        for row in _row("syn001.conversion_reactor", "molar_masses", index, None)
    ),
]


def test_the_table_covers_every_numeric_constructor_input() -> None:
    """Every `float` or `tuple[float, ...]` field of the six constructors is in the table, with
    each component of a vector field."""
    covered = {
        (model_id, field, index) for model_id, _, field, index, _, _ in (p.values for p in TABLE)
    }
    assert set(MODELS) == {model_id for model_id, _, _ in covered}
    for model_id, model in MODELS.items():
        unit = model.unit()
        for field in dataclasses.fields(unit):  # type: ignore[arg-type]
            value = getattr(unit, field.name)
            if isinstance(value, float):
                assert (model_id, field.name, None) in covered, (model_id, field.name)
            elif isinstance(value, tuple) and value and all(isinstance(v, float) for v in value):
                for index in range(len(value)):
                    assert (model_id, field.name, index) in covered, (model_id, field.name, index)


@pytest.mark.parametrize(("model_id", "changes", "field", "index", "label", "expected"), TABLE)
def test_a_non_finite_constructor_input_is_refused_at_construction(
    model_id: str,
    changes: dict[str, Any],
    field: str,
    index: int | None,
    label: str,
    expected: Expectation,
) -> None:
    nominal: UnitModel = MODELS[model_id].unit(**changes)
    number = NON_FINITE[label]
    if index is None:
        value: Any = number
    else:
        vector = list(getattr(nominal, field))
        vector[index] = number
        value = tuple(vector)
    if expected is None:
        with pytest.raises(ValueError, match="not finite") as refused:
            dataclasses.replace(nominal, **{field: value})  # type: ignore[type-var]
        assert not isinstance(refused.value, SpecificationError)
    else:
        with pytest.raises(SpecificationError) as refused:
            dataclasses.replace(nominal, **{field: value})  # type: ignore[type-var]
        assert first_line(str(refused.value)) == expected
