"""Closed forms of the P02 compiled subsystem, in double precision.

Specification: `docs/derivations/P02-composition-spec.md` §2 (subsystem, orderings, Jacobian),
§4.1 (pattern). Every formula here is transcribed from that document, which in turn follows
`docs/derivations/SYN-001.md` §2–§3. This module is the judge's expectation: it must not import a
backend, `openflowsheet`, or the SYN-001 oracle, and the harnesses must not import it.

Assertion A00 ties this module to `benchmarks/p02/reference_values.yaml`, which is generated
independently at 40 digits by `docs/derivations/scripts/p02_reference.py`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

# --- SYN-001 constants (plan §3.1) -------------------------------------------------------------

R: Final = 8.31446261815324
T_REF: Final = 300.0
P_REF: Final = 100000.0
C_P: Final = 100.0
T_BOIL: Final = (320.0, 360.0, 400.0)
L_VAP: Final = (25000.0, 30000.0, 35000.0)
V_MOLAR: Final = (1e-4, 1e-4, 1e-4)
COMPONENTS: Final = ("A", "B", "C")

T_MIN: Final = 280.0
T_MAX: Final = 440.0
P_MIN: Final = 50000.0
P_MAX: Final = 200000.0

# --- orderings (specification §2.4 and §2.6; asserted by A01) ----------------------------------

VARIABLE_IDS_L: Final[tuple[str, ...]] = (
    "v_A",
    "v_B",
    "v_C",
    "l_A",
    "l_B",
    "l_C",
    "V",
    "L",
    "lnK_A",
    "lnK_B",
    "lnK_C",
    "hL_A",
    "hL_B",
    "hL_C",
    "T",
    "P",
    "Q",
)
EQUATION_IDS_L: Final[tuple[str, ...]] = (
    "bal_A",
    "bal_B",
    "bal_C",
    "Vdef",
    "Ldef",
    "eq_A",
    "eq_B",
    "eq_C",
    "kdef_A",
    "kdef_B",
    "kdef_C",
    "hdef_A",
    "hdef_B",
    "hdef_C",
    "energy",
    "tspec",
    "pspec",
)
VARIABLE_IDS_I: Final[tuple[str, ...]] = (
    "v_A",
    "v_B",
    "v_C",
    "l_A",
    "l_B",
    "l_C",
    "V",
    "L",
    "T",
    "P",
    "Q",
)
EQUATION_IDS_I: Final[tuple[str, ...]] = (
    "bal_A",
    "bal_B",
    "bal_C",
    "Vdef",
    "Ldef",
    "eq_A",
    "eq_B",
    "eq_C",
    "energy",
    "tspec",
    "pspec",
)

_FLOW_SCALE: Final = 3.0
_TEMPERATURE_SCALE: Final = 100.0
_PRESSURE_SCALE: Final = 1e5
_ENERGY_SCALE: Final = 1e5

COLUMN_SCALES: Final[dict[str, float]] = {
    **{f"{p}_{c}": _FLOW_SCALE for p in ("v", "l") for c in COMPONENTS},
    "V": _FLOW_SCALE,
    "L": _FLOW_SCALE,
    **{f"lnK_{c}": 1.0 for c in COMPONENTS},
    **{f"hL_{c}": _ENERGY_SCALE for c in COMPONENTS},
    "T": _TEMPERATURE_SCALE,
    "P": _PRESSURE_SCALE,
    "Q": _ENERGY_SCALE,
}
ROW_SCALES: Final[dict[str, float]] = {
    **{f"bal_{c}": _FLOW_SCALE for c in COMPONENTS},
    "Vdef": _FLOW_SCALE,
    "Ldef": _FLOW_SCALE,
    **{f"eq_{c}": _FLOW_SCALE * _FLOW_SCALE for c in COMPONENTS},
    **{f"kdef_{c}": 1.0 for c in COMPONENTS},
    **{f"hdef_{c}": _ENERGY_SCALE for c in COMPONENTS},
    "energy": _ENERGY_SCALE,
    "tspec": _TEMPERATURE_SCALE,
    "pspec": _PRESSURE_SCALE,
}


class DomainError(ValueError):
    """Raised when a state leaves the closed SYN-001 domain (specification §2.2)."""


@dataclass(frozen=True)
class Parameters:
    """Fixed parameters of one registered evaluation state (specification §5)."""

    feed: tuple[float, float, float]
    h_feed: float
    t_spec: float
    p_spec: float


def normalize_zero(value: float) -> float:
    """Return +0.0 for either signed zero (ADR 0001 D1.5)."""
    return 0.0 if value == 0.0 else value


def check_domain(temperature: float, pressure: float) -> None:
    """Raise `DomainError` naming the offending value if the state leaves the closed domain."""
    if not T_MIN <= temperature <= T_MAX:
        raise DomainError(f"temperature {temperature!r} K outside [{T_MIN}, {T_MAX}] K")
    if not P_MIN <= pressure <= P_MAX:
        raise DomainError(f"pressure {pressure!r} Pa outside [{P_MIN}, {P_MAX}] Pa")


# --- block closed forms (specification §2.3) ---------------------------------------------------


def ln_k(temperature: float, pressure: float) -> tuple[float, float, float]:
    """ln K_i(T, P) for the three components, in component order."""
    check_domain(temperature, pressure)
    return tuple(  # type: ignore[return-value]
        math.log(P_REF / pressure)
        + (L_VAP[i] / R) * (1.0 / T_BOIL[i] - 1.0 / temperature)
        + V_MOLAR[i] * (pressure - P_REF) / (R * temperature)
        for i in range(3)
    )


def d_ln_k_d_temperature(temperature: float, pressure: float) -> tuple[float, float, float]:
    """∂lnK_i/∂T = [L_i − v_i (P − P_r)] / (R T²)."""
    check_domain(temperature, pressure)
    return tuple(  # type: ignore[return-value]
        (L_VAP[i] - V_MOLAR[i] * (pressure - P_REF)) / (R * temperature * temperature)
        for i in range(3)
    )


def d_ln_k_d_pressure(temperature: float, pressure: float) -> tuple[float, float, float]:
    """∂lnK_i/∂P = −1/P + v_i/(R T); identical for all components in this fixture."""
    check_domain(temperature, pressure)
    return tuple(  # type: ignore[return-value]
        -1.0 / pressure + V_MOLAR[i] / (R * temperature) for i in range(3)
    )


def h_liquid(temperature: float, pressure: float) -> tuple[float, float, float]:
    """Liquid molar enthalpies h_i^L(T, P) = c_p (T − T_r) + v_i (P − P_r), J/mol."""
    return tuple(  # type: ignore[return-value]
        C_P * (temperature - T_REF) + V_MOLAR[i] * (pressure - P_REF) for i in range(3)
    )


def h_vapor(temperature: float) -> tuple[float, float, float]:
    """Vapor molar enthalpies h_i^V(T) = c_p (T − T_r) + L_i, J/mol; independent of P."""
    return tuple(  # type: ignore[return-value]
        C_P * (temperature - T_REF) + L_VAP[i] for i in range(3)
    )


# --- L-form (specification §2.4, §2.5) ---------------------------------------------------------


def residual_l_form(x: dict[str, float], parameters: Parameters) -> dict[str, float]:
    """Residual of the lifted form, keyed by equation id (specification §2.4)."""
    v = [x[f"v_{c}"] for c in COMPONENTS]
    liquid = [x[f"l_{c}"] for c in COMPONENTS]
    ln_k_state = [x[f"lnK_{c}"] for c in COMPONENTS]
    h_lifted = [x[f"hL_{c}"] for c in COMPONENTS]
    total_v, total_l = x["V"], x["L"]
    temperature, pressure, duty = x["T"], x["P"], x["Q"]

    ln_k_block = ln_k(temperature, pressure)
    h_l_block = h_liquid(temperature, pressure)
    h_v_state = h_vapor(temperature)

    residual = {f"bal_{c}": v[i] + liquid[i] - parameters.feed[i] for i, c in enumerate(COMPONENTS)}
    residual["Vdef"] = total_v - sum(v)
    residual["Ldef"] = total_l - sum(liquid)
    for i, c in enumerate(COMPONENTS):
        residual[f"eq_{c}"] = v[i] * total_l - math.exp(ln_k_state[i]) * liquid[i] * total_v
    for i, c in enumerate(COMPONENTS):
        residual[f"kdef_{c}"] = ln_k_state[i] - ln_k_block[i]
    for i, c in enumerate(COMPONENTS):
        residual[f"hdef_{c}"] = h_lifted[i] - liquid[i] * h_l_block[i]
    residual["energy"] = (
        sum(v[i] * h_v_state[i] for i in range(3)) + sum(h_lifted) - parameters.h_feed - duty
    )
    residual["tspec"] = temperature - parameters.t_spec
    residual["pspec"] = pressure - parameters.p_spec
    return {key: normalize_zero(value) for key, value in residual.items()}


def jacobian_l_form(x: dict[str, float], parameters: Parameters) -> dict[str, float]:
    """All 60 structural nonzeros of the lifted Jacobian, keyed `"<row>|<col>"` (§2.5)."""
    del parameters  # the L-form Jacobian does not depend on the fixed parameters
    v = [x[f"v_{c}"] for c in COMPONENTS]
    liquid = [x[f"l_{c}"] for c in COMPONENTS]
    k_state = [math.exp(x[f"lnK_{c}"]) for c in COMPONENTS]
    total_v, total_l = x["V"], x["L"]
    temperature, pressure = x["T"], x["P"]

    h_l_block = h_liquid(temperature, pressure)
    h_v_state = h_vapor(temperature)
    d_t = d_ln_k_d_temperature(temperature, pressure)
    d_p = d_ln_k_d_pressure(temperature, pressure)

    entries: dict[str, float] = {}
    for i, c in enumerate(COMPONENTS):
        entries[f"bal_{c}|v_{c}"] = 1.0
        entries[f"bal_{c}|l_{c}"] = 1.0
        entries[f"Vdef|v_{c}"] = -1.0
        entries[f"Ldef|l_{c}"] = -1.0
        entries[f"eq_{c}|v_{c}"] = total_l
        entries[f"eq_{c}|l_{c}"] = -k_state[i] * total_v
        entries[f"eq_{c}|V"] = -k_state[i] * liquid[i]
        entries[f"eq_{c}|L"] = v[i]
        entries[f"eq_{c}|lnK_{c}"] = -k_state[i] * liquid[i] * total_v
        entries[f"kdef_{c}|lnK_{c}"] = 1.0
        entries[f"kdef_{c}|T"] = -d_t[i]
        entries[f"kdef_{c}|P"] = -d_p[i]
        entries[f"hdef_{c}|hL_{c}"] = 1.0
        entries[f"hdef_{c}|l_{c}"] = -h_l_block[i]
        entries[f"hdef_{c}|T"] = -liquid[i] * C_P
        entries[f"hdef_{c}|P"] = -liquid[i] * V_MOLAR[i]
        entries[f"energy|v_{c}"] = h_v_state[i]
        entries[f"energy|hL_{c}"] = 1.0
    entries["Vdef|V"] = 1.0
    entries["Ldef|L"] = 1.0
    entries["energy|T"] = C_P * sum(v)
    entries["energy|Q"] = -1.0
    entries["tspec|T"] = 1.0
    entries["pspec|P"] = 1.0
    return {key: normalize_zero(value) for key, value in entries.items()}


# --- I-form (specification §2.6) ---------------------------------------------------------------


def residual_i_form(x: dict[str, float], parameters: Parameters) -> dict[str, float]:
    """Residual of the inlined form, keyed by equation id (specification §2.6)."""
    v = [x[f"v_{c}"] for c in COMPONENTS]
    liquid = [x[f"l_{c}"] for c in COMPONENTS]
    total_v, total_l = x["V"], x["L"]
    temperature, pressure, duty = x["T"], x["P"], x["Q"]

    k_block = [math.exp(value) for value in ln_k(temperature, pressure)]
    h_l_block = h_liquid(temperature, pressure)
    h_v_state = h_vapor(temperature)

    residual = {f"bal_{c}": v[i] + liquid[i] - parameters.feed[i] for i, c in enumerate(COMPONENTS)}
    residual["Vdef"] = total_v - sum(v)
    residual["Ldef"] = total_l - sum(liquid)
    for i, c in enumerate(COMPONENTS):
        residual[f"eq_{c}"] = v[i] * total_l - k_block[i] * liquid[i] * total_v
    residual["energy"] = (
        sum(v[i] * h_v_state[i] for i in range(3))
        + sum(liquid[i] * h_l_block[i] for i in range(3))
        - parameters.h_feed
        - duty
    )
    residual["tspec"] = temperature - parameters.t_spec
    residual["pspec"] = pressure - parameters.p_spec
    return {key: normalize_zero(value) for key, value in residual.items()}


def jacobian_i_form(x: dict[str, float], parameters: Parameters) -> dict[str, float]:
    """All 43 structural nonzeros of the inlined Jacobian, keyed `"<row>|<col>"` (§2.6)."""
    del parameters
    v = [x[f"v_{c}"] for c in COMPONENTS]
    liquid = [x[f"l_{c}"] for c in COMPONENTS]
    total_v, total_l = x["V"], x["L"]
    temperature, pressure = x["T"], x["P"]

    k_block = [math.exp(value) for value in ln_k(temperature, pressure)]
    h_l_block = h_liquid(temperature, pressure)
    h_v_state = h_vapor(temperature)
    d_t = d_ln_k_d_temperature(temperature, pressure)
    d_p = d_ln_k_d_pressure(temperature, pressure)

    entries: dict[str, float] = {}
    for i, c in enumerate(COMPONENTS):
        entries[f"bal_{c}|v_{c}"] = 1.0
        entries[f"bal_{c}|l_{c}"] = 1.0
        entries[f"Vdef|v_{c}"] = -1.0
        entries[f"Ldef|l_{c}"] = -1.0
        entries[f"eq_{c}|v_{c}"] = total_l
        entries[f"eq_{c}|l_{c}"] = -k_block[i] * total_v
        entries[f"eq_{c}|V"] = -k_block[i] * liquid[i]
        entries[f"eq_{c}|L"] = v[i]
        entries[f"eq_{c}|T"] = -k_block[i] * liquid[i] * total_v * d_t[i]
        entries[f"eq_{c}|P"] = -k_block[i] * liquid[i] * total_v * d_p[i]
        entries[f"energy|v_{c}"] = h_v_state[i]
        entries[f"energy|l_{c}"] = h_l_block[i]
    entries["Vdef|V"] = 1.0
    entries["Ldef|L"] = 1.0
    entries["energy|T"] = C_P * (sum(v) + sum(liquid))
    entries["energy|P"] = sum(liquid[i] * V_MOLAR[i] for i in range(3))
    entries["energy|Q"] = -1.0
    entries["tspec|T"] = 1.0
    entries["pspec|P"] = 1.0
    return {key: normalize_zero(value) for key, value in entries.items()}


_PROBE_PARAMETERS: Final = Parameters((1.0, 1.0, 1.0), 0.0, 1.0, 1.0)
_PROBE_X_L: Final = {**dict.fromkeys(VARIABLE_IDS_L, 1.0), "T": 360.0, "P": P_REF}
_PROBE_X_I: Final = {**dict.fromkeys(VARIABLE_IDS_I, 1.0), "T": 360.0, "P": P_REF}

#: The structural pattern of each form, as `"<row>|<col>"` keys. It is a property of the
#: formulation, identical at every state (specification §4.2, asserted by A09), so probing the
#: closed forms at an arbitrary in-domain point yields it.
PATTERN_L: Final[tuple[str, ...]] = tuple(sorted(jacobian_l_form(_PROBE_X_L, _PROBE_PARAMETERS)))
PATTERN_I: Final[tuple[str, ...]] = tuple(sorted(jacobian_i_form(_PROBE_X_I, _PROBE_PARAMETERS)))
