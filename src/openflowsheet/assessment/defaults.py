"""Every default the E01 design states, with its value, unit, text and section.

E01 design §4.4–§4.7, §7 Q9/Q12 (register R-856). A default is a value the assessment uses when
the document does not state one; every use is reported under `defaulted_inputs` (§4.9, assertion
A41, which enumerates this table). Two inputs have **no** default on purpose: the overall
heat-transfer coefficient `U` and each utility's `ΔT_min` (§4.4.1–§4.4.2). They are listed in
`REQUIRED` so that the absence is stated, not forgotten.

Keys are the names the assessment document's `defaults` object overrides them by
(`schemas/assessment.schema.json`), except the `operation.*` and `basis.*` keys, which are
overridden in those sections of the document.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

__all__ = ["DEFAULTS", "REQUIRED", "Default", "default"]


@dataclass(frozen=True)
class Default:
    key: str
    value: float | str
    unit: str
    text: str
    section: str


_TABLE: Final[tuple[Default, ...]] = (
    Default("F_T", 1.0, "1", "LMTD correction factor of an exchanger", "§4.4.1"),
    Default(
        "service_at_zero_duty",
        "heating",
        "",
        "service of an exchanger whose duty is exactly 0.0 and which declares none",
        "§4.3.2 rule 1",
    ),
    Default("drum_orientation", "vertical", "", "flash-drum orientation", "§4.4.4"),
    Default("drum_residence_time", 300.0, "s", "liquid residence time τ of a flash drum", "§4.4.4"),
    Default("drum_fill_fraction", 0.5, "1", "liquid fill fraction φ_fill of a drum", "§4.4.4"),
    Default("drum_LD", 3.0, "1", "length-to-diameter ratio of a drum", "§4.4.4"),
    Default("drum_K_SB", 0.07, "m/s", "Souders–Brown coefficient of a drum", "§4.4.4"),
    Default(
        "drive_efficiency",
        0.95,
        "1",
        "pump or compressor drive efficiency when the set defines no motor-efficiency correlation",
        "§4.4.5",
    ),
    Default("generator_efficiency", 0.95, "1", "turbine generator efficiency η_gen", "§4.4.5"),
    Default("column_C_SB", 0.09, "m/s", "flooding Souders–Brown coefficient of a tray", "§4.4.6"),
    Default("column_flooding_fraction", 0.80, "1", "design fraction of flooding f_flood", "§4.4.6"),
    Default("column_active_area_fraction", 0.85, "1", "active-area fraction φ_active", "§4.4.6"),
    Default("column_tray_spacing", 0.6096, "m", "tray spacing s_tray (24 in)", "§4.4.6"),
    Default("column_overall_efficiency", 0.70, "1", "overall tray efficiency E_o", "§4.4.6"),
    Default("column_H_top", 1.2192, "m", "shell height above the top tray (4 ft)", "§4.4.6"),
    Default("column_H_bottom", 3.048, "m", "shell height below the bottom tray (10 ft)", "§4.4.6"),
    Default("reactor_LD", 3.0, "1", "length-to-diameter ratio of a reactor vessel", "§4.4.7"),
    Default("operation.hours_per_year", 8000.0, "h/yr", "operating hours per year h_op", "§4.7.3"),
    Default("operation.lifetime_years", 20.0, "yr", "plant lifetime n", "§4.7.3"),
    Default("operation.discount_rate", 0.08, "1/yr", "real discount rate i", "§4.7.3"),
    Default("basis.location_factor", 1.0, "1", "location factor LF", "§4.6"),
    Default(
        "electricity_export_price",
        "import",
        "",
        "electricity export price equal to the import price (netting; ELECTRICITY_NETTED)",
        "§4.7.2, §7 Q12",
    ),
    Default(
        "escalation_series.USD",
        "bls-ppi-wpu11-annual-v1",
        "",
        "escalation series of a USD basis (BLS PPI WPU11)",
        "§4.6, §7 Q14",
    ),
    Default(
        "escalation_series.EUR",
        "eurostat-ppi-c28-ea-annual-v1",
        "",
        "escalation series of a EUR basis (Eurostat PPI NACE C28, euro area)",
        "§4.6, §7 Q14",
    ),
    Default(
        "exchange_rates",
        "frb-g5a-annual-v1",
        "",
        "annual exchange rates (Federal Reserve G.5A)",
        "§4.6",
    ),
)

#: Every default, by key, in the order above.
DEFAULTS: Final = MappingProxyType({entry.key: entry for entry in _TABLE})

#: Inputs with no built-in value (R-856): an item without them is refused
#: `SIZING_INPUT_MISSING(<item>.<input>)`.
REQUIRED: Final[tuple[str, ...]] = ("U", "dT_min")


def default(key: str) -> Default:
    """The default `key`; a `KeyError` names the table, because an unknown default is a defect."""
    try:
        return DEFAULTS[key]
    except KeyError:
        raise KeyError(
            f"{key!r} is not a default of the E01 design (assessment.defaults)"
        ) from None
