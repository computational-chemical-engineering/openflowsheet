"""E01 WO-B4 (design §5.3, §9.2.4, §9.5): independent cost expectations.

Track B's transcription of the IDAES SSLW costing methods used by E01, made directly from the pinned
source and from nothing else: idaes-pse 2.13.0, `idaes/models/costing/SSLW.py` (sha256 below), with
`idaes/core/base/costing_base.py` for the CE 394 currency unit. Every number taken from the source
carries its line (`SSLW.py:<n>`). This script imports nothing from `openflowsheet` and reads none of
track A's code or data (`_data/assessment/cost/sslw-idaes-v1.json` included); the two transcriptions
meet only in `tests/test_e01_b_cost_hand.py`. Arithmetic is mpmath at 30 digits on the binary64
inputs written in the YAML, so a test feeds the package exactly the same floats.

Where the design note departs from IDAES on purpose (§9.2.2), this script follows the note:
  1. ranges (IDAES enforces none): §4.3.2 and §9.2.5 (size floor, parallel units, input floors);
  2. tray count factor: exact max(1, 2.25/1.0414**N), not IDAES's smooth_max (SSLW.py:841);
  3. vessel: `cost_vessel` (SSLW.py:509-727) with the options passed through;
  4. vertical platforms: a piece on L (12-40 ft piece 1, 40-170 ft piece 2, floors at L = 12 ft
     and D = 3 ft), where IDAES takes `aspect_ratio_range` as a user option;
  5. number of units: the size regime's N for parallel forms (IDAES fixes 1);
  6. compressor drive: ElectricMotor only (F_D = 1);
  7. exchanger design pressure: an input here (the package's rule picks it), IDAES reads the hot
     side's inlet (SSLW.py:472-485).

Sections of the YAML:
  - `forms`: each entry at S_min, sqrt(S_min*S_max), S_max (the S_max point is targeted at
    S_max*(1 - 1e-14) so that binary64 rounding of the size cannot cross into `units:2`, a
    discontinuous regime), at each floor bound and 1e-6 relative inside it, below a floor, and
    above S_max for parallel forms; options at IDAES's argument defaults (QA2);
  - `p_sizes`: the items of P1 (S11 TH-C1, TH-R1) and P3 (M1) at the sizes their committed report
    fixtures record (tests/fixtures/schemas/assessment_report/valid/; transcribed below with each
    fixture's state_sha256);
  - `design_note`: the numbers §6.1/§9.6 state (A10, A21, A44, A20), recomputed;
  - `sizing`: A11 (TH-R1's flash drum) and A12 (M1's column shell) from the recorded solved states
    in `recorded_states.yaml` (written by `tests/test_e01_b_cost_hand.py --write-states`, which
    also checks them against a fresh solve), the identity volumes (RT/P, Amagat) computed here;
  - `chain`: escalation, the `ebtf-prisma-v1` chain, CRF and tac on P1 (TH-C1).

Usage: `python benchmarks/e01/cost_hand/cost_hand.py` writes `cost_hand.yaml` beside it;
`--print` writes it to stdout; `--check` exits 1 if the committed YAML is not current.
"""

from __future__ import annotations

import hashlib
import math
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import mpmath  # type: ignore[import-untyped]
import yaml

mpmath.mp.dps = 30
HERE = Path(__file__).resolve().parent
F = mpmath.mpf
Num = Any  # mpmath.mpf

SOURCE = {
    "package": "idaes-pse",
    "version": "2.13.0",
    "wheel_sha256": "2b67301afe6dc0c2f0e7342253ebcbab6e91607c0204d9bd663a2735f1ec85f9",
    "file": "idaes/models/costing/SSLW.py",
    "file_sha256": "362b0a22e78ad578c4ce6408224aa6193fc6330cb7041fc1d4aaee0e060b1184",
    "aux": {
        "file": "idaes/core/base/costing_base.py",
        "sha256": "cdd71f362a2b59e5c1ed4261e8811f7fc749d0999aba0d01d32ad1999b0bfc38",
    },
}

# -- Units, from their definitions (pint's, which IDAES's pyomo.units uses) ------------------------
FT = F("0.3048")  # m
INCH = F("0.0254")  # m
GALLON = 231 * INCH**3  # US gallon, m3 (= 3.785411784e-3)
LB = F("0.45359237")  # kg
LBF = LB * F("9.80665")  # N
HP = 550 * FT * LBF  # mechanical horsepower, W (= 745.69987158227022)
PSI = LBF / INCH**2  # Pa
ATM = F(101325)  # Pa
KAPPA_A = 1 / FT**2  # ft2 per m2
KAPPA_Q = 60 / GALLON  # gpm per m3/s
KAPPA_W = 1 / HP  # hp per W
CE_RATIO = F(500) / F("394.0")  # costing_base.py:66, "USD_CE394 = 500/394.0 * USD_CE500"
PI = mpmath.pi  # IDAES Constants.pi (SSLW.py:663)


# -- Transcription (every number with its SSLW.py line) --------------------------------------------
def n(value: str, line: int) -> tuple[Num, str]:
    return F(value), f"SSLW.py:{line}"


# I. cost_heat_exchanger (SSLW.py:327-507)
HX_ALPHA = {  # :400-405, exp(a1 - a2 ln z + a3 ln z^2) (:418-422)
    "floating_head": (n("11.9052", 401), n("0.8709", 401), n("0.09005", 401)),
    "fixed_head": (n("11.2927", 402), n("0.8228", 402), n("0.09861", 402)),
    "Utube": (n("11.3852", 403), n("0.9186", 403), n("0.09790", 403)),
    "kettle_vap": (n("12.2052", 404), n("0.8709", 404), n("0.09005", 404)),
}
HX_MATERIAL = {  # :438-449, F_M = A + (area/100 ft2)^B (:458-461); CS/CS gives 1 (:455-456)
    "CarbonSteelCarbonSteel": (n("0.00", 439), n("0.00", 439)),
    "CarbonSteelBrass": (n("1.08", 440), n("0.05", 440)),
    "CarbonSteelStainlessSteel": (n("1.75", 441), n("0.13", 441)),
    "CarbonSteelMonel": (n("2.10", 442), n("0.13", 442)),
    "CarbonSteelTitanium": (n("5.20", 443), n("0.16", 443)),
    "CarbonSteelCrMoSteel": (n("1.55", 444), n("0.05", 444)),
    "CrMoSteelCrMoSteel": (n("1.70", 445), n("0.07", 445)),
    "StainlessSteelStainlessSteel": (n("2.70", 446), n("0.07", 446)),
    "MonelMonel": (n("3.30", 447), n("0.08", 447)),
    "TitaniumTitanium": (n("9.60", 448), n("0.06", 448)),
}
HX_LENGTH = {  # :384 c_fl
    "EightFoot": n("1.25", 384),
    "TwelveFoot": n("1.12", 384),
    "SixteenFoot": n("1.05", 384),
    "TwentyFoot": n("1.00", 384),
}
HX_OVERSIZE = n("1.1", 393)
HX_AREA_REF = n("100", 460)  # ft2
HX_PRESSURE = (n("0.9803", 494), n("0.0180", 495), n("0.0017", 496))  # u = p/(100 psi) (:495)
HX_PRESSURE_REF = n("100", 495)  # psi
HX_PRESSURE_RANGE = (F(100), F(2000))  # psig, comment at :492 "valid from 100 pisg to 2000 psig"
HX_DEFAULTS = {
    "hx_type": "Utube",
    "material": "StainlessSteelStainlessSteel",
    "tube_length": "TwelveFoot",
}  # :329-331
HX_AREA_RANGE = (F(150), F(12000))  # ft2, primary (§9.2.4 I; QA1, not in the source)

# II. cost_vessel (SSLW.py:509-727) and _cost_platforms_ladders (:728-776)
VESSEL_MATERIAL = {  # :620-631, (factor, density lb/in3)
    "CarbonSteel": (n("1.0", 621), n("0.284", 621)),
    "LowAlloySteel": (n("1.2", 622), n("0.271", 622)),
    "StainlessSteel304": (n("1.7", 623), n("0.270", 623)),
    "StainlessSteel316": (n("2.1", 624), n("0.276", 624)),
    "Carpenter20CB3": (n("3.2", 625), n("0.29", 625)),
    "Nickel200": (n("5.4", 626), n("0.3216", 626)),
    "Monel400": (n("3.6", 627), n("0.319", 627)),
    "Inconel600": (n("3.9", 628), n("0.3071", 628)),
    "Incoloy825": (n("3.7", 629), n("0.2903", 629)),
    "Titanium": (n("7.7", 630), n("0.1628", 630)),
}
VESSEL_T_SHELL_IN = n("1.25", 513)  # inch
VESSEL_W_LENGTH = n("0.8", 665)  # W = pi (D+t)(L + 0.8 D) t rho (:662-668)
VESSEL_ALPHA = {  # :673-679, exp(a1 + a2 ln W + a3 ln W^2) (:688-694)
    ("horizontal", "1"): (n("8.9552", 674), n("-0.2330", 674), n("0.04333", 674)),
    ("vertical", "1"): (n("7.0132", 676), n("0.18255", 676), n("0.02297", 676)),
    ("vertical", "2"): (n("7.2756", 677), n("0.18255", 677), n("0.02297", 677)),
}
VESSEL_W_RANGE = {"1": (F(1000), F(920000)), "2": (F(4200), F(1000000))}  # lb, docstring :534
PL_HORIZONTAL = (n("2005", 749), n("0.20294", 749))  # C = 2005 D^0.20294
PL_VERTICAL = {  # piece: (c, D exponent, L exponent); L and D ranges from the docstring :537
    1: (n("361.8", 758), n("0.73960", 759), n("0.70684", 760)),
    2: (n("309.9", 765), n("0.63316", 766), n("0.80161", 767)),
}
PL_L_PIECES = {1: (F(12), F(40)), 2: (F(40), F(170))}  # ft; §9.2.4 II (piece 2 from 40 ft)
PL_D_RANGE = {1: (F(3), F(21)), 2: (F(3), F(24))}  # ft, :537
VESSEL_DEFAULTS = {
    "material": "CarbonSteel",
    "weight_limit": "1",
    "platforms_ladders": True,
}  # :512, :514, :516

# III. _cost_distillation_trays (SSLW.py:777-868)
TRAY_TYPE = {"Sieve": n("1", 804), "Valve": n("1.18", 805), "BubbleCap": n("1.87", 806)}
TRAY_MATERIAL = {  # :816-822, F_TM = a1 + a2 D_ft (:828-830)
    "CarbonSteel": (n("1", 817), n("0", 817)),
    "StainlessSteel303": (n("1.189", 818), n("0.0577", 818)),
    "StainlessSteel316": (n("1.401", 819), n("0.0724", 819)),
    "Carpenter20CB3": (n("1.525", 820), n("0.0788", 820)),
    "Monel": (n("2.306", 821), n("0.1120", 821)),
}
TRAY_NT = (n("2.25", 842), n("1.0414", 842))  # max(1, 2.25/1.0414**N) (:841-843)
TRAY_COST = (n("468.00", 856), n("0.1739", 856))  # 468 exp(0.1739 D_ft) (:855-857)
TRAY_D_RANGE = (F(2), F(16))  # ft, comment at :825 "eqn. valid for 2 to 16 ft"
TRAY_DEFAULTS = {"tray_type": "Sieve", "tray_material": "CarbonSteel"}  # :521-522

# IV. cost_pump (SSLW.py:1387-1623); base cost at CE 394 (:1579)
PUMP_MATERIAL = {
    "nonreciprocating": {  # :1528-1538
        "CastIron": n("1.00", 1529),
        "DuctileIron": n("1.15", 1530),
        "CastSteel": n("1.35", 1531),
        "Bronze": n("1.90", 1532),
        "StainlessSteel": n("2.00", 1533),
        "HastelloyC": n("2.95", 1534),
        "Monel": n("3.30", 1535),
        "Nickel": n("3.50", 1536),
        "Titanium": n("9.70", 1537),
    },
    "Reciprocating": {  # :1540-1545
        "DuctileIron": n("1.00", 1541),
        "StainlessSteel": n("2.20", 1542),
        "NiAlBronze": n("1.15", 1543),
        "CarbonSteel": n("1.50", 1544),
    },
}
PUMP_TYPE_FACTOR = {  # :1554-1561, Centrifugal only; others 1 (:1571)
    "1.1": n("1.00", 1555),
    "1.2": n("1.50", 1556),
    "1.3": n("1.70", 1557),
    "1.4": n("2.00", 1558),
    "2.1": n("2.70", 1559),
    "2.2": n("8.90", 1560),
}
PUMP_OTHER_TYPE_FACTOR = n("1", 1571)
PUMP_HEAD_EXPONENT = n("0.5", 1523)  # S = Q H^0.5 (:1513-1523)
PUMP_BASE = {  # :1585-1602, exp(a0 + a1 ln s + a2 ln s^2) with s = S, Q (gpm), W (hp)
    "Centrifugal": (n("9.7171", 1587), n("-0.6019", 1588), n("0.0519", 1589)),
    "ExternalGear": (n("7.6964", 1593), n("0.1986", 1594), n("0.0291", 1595)),
    "Reciprocating": (n("7.8103", 1599), n("0.26986", 1600), n("0.06718", 1601)),
}
PUMP_SIZE_RANGE = {  # primary (§9.2.4 IV; QA1)
    "Centrifugal": (F(400), F(100000)),
    "ExternalGear": (F(10), F(900)),
    "Reciprocating": (F(1), F(200)),
}
PUMP_DEFAULTS = {
    "pump_type": "Centrifugal",
    "material": "StainlessSteel",
    "pump_type_factor": "1.4",
}  # :1389-1391

# V. pump motor (SSLW.py:1624-1677); base cost at CE 394 (:1647)
MOTOR_TYPE = {"Open": n("1", 1626), "Enclosed": n("1.4", 1627), "ExplosionProof": n("1.8", 1628)}
MOTOR_ETA = (n("0.80", 1638), n("0.0319", 1639), n("-0.00182", 1640))
MOTOR_BASE = (
    n("5.8259", 1655),
    n("0.13141", 1656),
    n("0.053255", 1657),
    n("0.028628", 1658),
    n("-0.0035549", 1659),
)
MOTOR_RANGE = (F(1), F(700))  # hp, primary (§9.2.4 V; QA1)
MOTOR_DEFAULTS = {"motor_type": "Open"}  # :1392

# VI. cost_compressor (SSLW.py:1080-1178)
COMPRESSOR_ALPHA = {  # :1155-1159, exp(a1 + a2 ln W_hp) (:1165-1167)
    "Centrifugal": (n("7.58", 1156), n("0.8", 1156)),
    "Reciprocating": (n("7.9661", 1157), n("0.8", 1157)),
    "Screw": (n("8.1238", 1158), n("0.7243", 1158)),
}
COMPRESSOR_DRIVE = {
    "ElectricMotor": n("1", 1136)
}  # departure 6 (SteamTurbine/gasTurbine not offered)
COMPRESSOR_MATERIAL = {
    "CarbonSteel": n("1", 1145),
    "StainlessSteel": n("2.5", 1146),
    "NickelAlloy": n("5.0", 1147),
}
COMPRESSOR_RANGE = {
    "Centrifugal": (F(200), F(30000)),
    "Reciprocating": (F(100), F(20000)),
    "Screw": (F(10), F(750)),
}  # hp, primary (§9.2.4 VI; QA1)
COMPRESSOR_DEFAULTS = {
    "compressor_type": "Centrifugal",
    "drive_type": "ElectricMotor",
    "material": "StainlessSteel",
}  # :1082-1084

# VII. cost_turbine (SSLW.py:1338-1386)
TURBINE = (n("530", 1382), n("0.81", 1383))  # 530 W_hp^0.81, W_hp = -W (:1374-1376)


# -- Regime helpers (§4.3.2, §9.2.5) ---------------------------------------------------------------
def size_regime(s: Num, lo: Num, hi: Num, parallel: bool) -> tuple[str, int]:
    """`floor` below S_min; `units:1` up to S_max; above: `units:ceil(S/S_max)` or `refused`."""
    if s < lo:
        return "floor", 1
    if s <= hi:
        return "units:1", 1
    if not parallel:
        return "refused", 1
    units = int(mpmath.ceil(s / hi))
    return f"units:{units}", units


def v(x: Num) -> Num:
    return x[0]


# -- The seven forms -------------------------------------------------------------------------------
def exchanger(x: Mapping[str, float], opt: Mapping[str, str]) -> dict[str, Any]:
    a_total = F(x["area_m2"]) * KAPPA_A
    regime, units = size_regime(a_total, *HX_AREA_RANGE, parallel=True)
    a_unit = HX_AREA_RANGE[0] if regime == "floor" else a_total / units
    z = a_unit * v(HX_OVERSIZE)
    a1, a2, a3 = (v(c) for c in HX_ALPHA[opt["hx_type"]])
    c_b = mpmath.exp(a1 - a2 * mpmath.log(z) + a3 * mpmath.log(z) ** 2)
    if opt["material"] == "CarbonSteelCarbonSteel":
        f_m = F(1)
    else:
        am, bm = (v(c) for c in HX_MATERIAL[opt["material"]])
        f_m = am + (a_unit / v(HX_AREA_REF)) ** bm
    p = (F(x["P_Pa"]) - ATM) / PSI
    lo, hi = HX_PRESSURE_RANGE
    if p > hi:
        return {"regime": {"size": regime, "pressure": "refused"}, "C_P": None}
    piece = "floor" if p < lo else "1"
    u = (lo if piece == "floor" else p) / v(HX_PRESSURE_REF)
    p0, p1, p2 = (v(c) for c in HX_PRESSURE)
    f_p = p0 + p1 * u + p2 * u**2
    f_l = v(HX_LENGTH[opt["tube_length"]])
    c_p1 = f_p * f_m * f_l * c_b
    return {
        "regime": {"size": regime, "pressure": piece},
        "quantities": {
            "area_ft2": a_total,
            "area_ft2_per_unit": a_unit,
            "z": z,
            "C_B": c_b,
            "F_M": f_m,
            "p_psig": p,
            "F_P": f_p,
            "F_L": f_l,
        },
        "C_P1": c_p1,
        "C_P": units * c_p1,
    }


def platforms_vertical(d_ft: Num, l_ft: Num) -> tuple[dict[str, str], Num | None]:
    if l_ft > PL_L_PIECES[2][1]:
        return {"L": "refused"}, None
    l_piece = "floor" if l_ft < PL_L_PIECES[1][0] else ("1" if l_ft < PL_L_PIECES[2][0] else "2")
    formula = 1 if l_piece in ("floor", "1") else 2
    d_lo, d_hi = PL_D_RANGE[formula]
    if d_ft > d_hi:
        return {"L": l_piece, "D": "refused"}, None
    d_piece = "floor" if d_ft < d_lo else "1"
    d_eff = d_lo if d_piece == "floor" else d_ft
    l_eff = PL_L_PIECES[1][0] if l_piece == "floor" else l_ft
    c, ed, el = (v(q) for q in PL_VERTICAL[formula])
    return {"L": l_piece, "D": d_piece}, c * d_eff**ed * l_eff**el


def vessel(x: Mapping[str, float], opt: Mapping[str, Any]) -> dict[str, Any]:
    orientation = opt["orientation"]
    limit = opt["weight_limit"] if orientation == "vertical" else "1"  # :674
    d_in = F(x["D_m"]) / INCH
    l_in = F(x["L_m"]) / INCH
    t_in = F(x["t_shell_m"]) / INCH
    f_m, rho = (v(c) for c in VESSEL_MATERIAL[opt["material"]])
    w = PI * (d_in + t_in) * (l_in + v(VESSEL_W_LENGTH) * d_in) * t_in * rho
    regime, _ = size_regime(w, *VESSEL_W_RANGE[limit], parallel=False)
    if regime == "refused":
        return {"regime": {"size": regime}, "C_P": None}
    w_eff = VESSEL_W_RANGE[limit][0] if regime == "floor" else w
    a1, a2, a3 = (v(c) for c in VESSEL_ALPHA[(orientation, limit)])
    c_v = mpmath.exp(a1 + a2 * mpmath.log(w_eff) + a3 * mpmath.log(w_eff) ** 2)
    d_ft = F(x["D_m"]) / FT
    l_ft = F(x["L_m"]) / FT
    regimes: dict[str, str] = {"size": regime}
    c_pl: Num = F(0)
    if opt["platforms_ladders"]:
        if orientation == "horizontal":
            c, e = (v(q) for q in PL_HORIZONTAL)
            c_pl = c * d_ft**e
        else:
            pieces, value = platforms_vertical(d_ft, l_ft)
            regimes.update({f"platforms.{k}": p for k, p in pieces.items()})
            if value is None:
                return {"regime": regimes, "C_P": None}
            c_pl = value
    c_p1 = f_m * c_v + c_pl
    return {
        "regime": regimes,
        "quantities": {"W_lb": w, "C_v": c_v, "C_PL": c_pl, "F_M": f_m, "D_ft": d_ft, "L_ft": l_ft},
        "C_P1": c_p1,
        "C_P": c_p1,
    }


def tray_count_factor(n_act: int) -> Num:
    c, b = (v(q) for q in TRAY_NT)
    return max(F(1), c / b**n_act)  # departure 2: exact max


def trays(x: Mapping[str, Any], opt: Mapping[str, str]) -> dict[str, Any]:
    d_ft = F(x["D_m"]) / FT
    regime, _ = size_regime(d_ft, *TRAY_D_RANGE, parallel=False)
    if regime == "refused":
        return {"regime": {"size": regime}, "C_P": None}
    d_eff = TRAY_D_RANGE[0] if regime == "floor" else d_ft
    a1, a2 = (v(c) for c in TRAY_MATERIAL[opt["tray_material"]])
    f_tm = a1 + a2 * d_eff
    c0, c1 = (v(c) for c in TRAY_COST)
    c_t = c0 * mpmath.exp(c1 * d_eff)
    n_act = int(x["N_act"])
    f_nt = tray_count_factor(n_act)
    f_tt = v(TRAY_TYPE[opt["tray_type"]])
    c_p1 = n_act * f_nt * f_tt * f_tm * c_t
    return {
        "regime": {"size": regime},
        "quantities": {"D_ft": d_ft, "F_TM": f_tm, "C_t": c_t, "F_NT": f_nt, "F_TT": f_tt},
        "C_P1": c_p1,
        "C_P": c_p1,
    }


def pump(x: Mapping[str, float], opt: Mapping[str, str]) -> dict[str, Any]:
    kind = opt["pump_type"]
    q_total = F(x["vol_flow_m3s"]) * KAPPA_Q  # gpm
    h_ft = F(x["head_m"]) / FT  # = dP/rho in lbf ft/lb with g = 9.80665
    w_total = F(x["power_W"]) * KAPPA_W  # hp

    def size_of(units: int) -> Num:
        if kind == "Centrifugal":
            return (q_total / units) * h_ft ** v(PUMP_HEAD_EXPONENT)
        return (q_total if kind == "ExternalGear" else w_total) / units

    regime, units = size_regime(size_of(1), *PUMP_SIZE_RANGE[kind], parallel=True)
    s = PUMP_SIZE_RANGE[kind][0] if regime == "floor" else size_of(units)
    a0, a1, a2 = (v(c) for c in PUMP_BASE[kind])
    c_b = mpmath.exp(a0 + a1 * mpmath.log(s) + a2 * mpmath.log(s) ** 2)
    table = "Reciprocating" if kind == "Reciprocating" else "nonreciprocating"
    f_m = v(PUMP_MATERIAL[table][opt["material"]])
    f_t = (
        v(PUMP_TYPE_FACTOR[opt["pump_type_factor"]])
        if kind == "Centrifugal"
        else v(PUMP_OTHER_TYPE_FACTOR)
    )
    c_p1 = f_t * f_m * c_b * CE_RATIO
    return {
        "regime": {"size": regime},
        "quantities": {
            "size": size_of(units),
            "Q_gpm_per_unit": q_total / units,
            "H_ft": h_ft,
            "C_B_CE394": c_b,
            "F_M": f_m,
            "F_T": f_t,
        },
        "C_P1": c_p1,
        "C_P": units * c_p1,
    }


def motor_efficiency(w_hp: Num) -> Num:
    e0, e1, e2 = (v(c) for c in MOTOR_ETA)
    return e0 + e1 * mpmath.log(w_hp) + e2 * mpmath.log(w_hp) ** 2


def motor(x: Mapping[str, Any], opt: Mapping[str, str]) -> dict[str, Any]:
    units = int(x.get("N", 1))
    w_hp = F(x["shaft_power_W"]) / units * KAPPA_W
    eta = motor_efficiency(w_hp)
    w_m = w_hp / eta
    lo, hi = MOTOR_RANGE
    if w_m > hi:
        return {"regime": {"size": "refused"}, "C_P": None}
    regime = "floor" if w_m < lo else f"units:{units}"
    lam = mpmath.log(lo if regime == "floor" else w_m)
    b = [v(c) for c in MOTOR_BASE]
    c_b = mpmath.exp(b[0] + b[1] * lam + b[2] * lam**2 + b[3] * lam**3 + b[4] * lam**4)
    f_mt = v(MOTOR_TYPE[opt["motor_type"]])
    c_p1 = f_mt * c_b * CE_RATIO
    return {
        "regime": {"size": regime},
        "quantities": {
            "W_hp_per_unit": w_hp,
            "eta_m": eta,
            "W_m_hp": w_m,
            "C_B_CE394": c_b,
            "F_MT": f_mt,
            "electricity_W": F(x["shaft_power_W"]) / eta,
        },
        "C_P1": c_p1,
        "C_P": units * c_p1,
    }


def compressor(x: Mapping[str, float], opt: Mapping[str, str]) -> dict[str, Any]:
    kind = opt["compressor_type"]
    w_total = F(x["power_W"]) * KAPPA_W
    regime, units = size_regime(w_total, *COMPRESSOR_RANGE[kind], parallel=True)
    w_hp = COMPRESSOR_RANGE[kind][0] if regime == "floor" else w_total / units
    a1, a2 = (v(c) for c in COMPRESSOR_ALPHA[kind])
    c_b = mpmath.exp(a1 + a2 * mpmath.log(w_hp))
    f_d = v(COMPRESSOR_DRIVE[opt["drive_type"]])
    f_m = v(COMPRESSOR_MATERIAL[opt["material"]])
    c_p1 = f_d * f_m * c_b
    return {
        "regime": {"size": regime},
        "quantities": {"W_hp_per_unit": w_total / units, "C_B": c_b, "F_D": f_d, "F_M": f_m},
        "C_P1": c_p1,
        "C_P": units * c_p1,
    }


def turbine(x: Mapping[str, float], opt: Mapping[str, str]) -> dict[str, Any]:
    w_hp = -F(x["power_W"]) * KAPPA_W  # the turbine's W < 0 (SSLW.py:1374)
    c, e = (v(q) for q in TURBINE)
    c_p1 = c * w_hp**e
    return {"regime": {}, "quantities": {"W_hp": w_hp}, "C_P1": c_p1, "C_P": c_p1}


FORMS: dict[str, tuple[str, Callable[..., dict[str, Any]]]] = {
    "exchanger.shell_tube": ("sslw-exchanger-v1", exchanger),
    "vessel.vertical": ("sslw-vessel-v1", vessel),
    "vessel.horizontal": ("sslw-vessel-v1", vessel),
    "column.trays": ("sslw-trays-v1", trays),
    "pump": ("sslw-pump-v1", pump),
    "motor.electric": ("sslw-motor-v1", motor),
    "compressor": ("sslw-compressor-v1", compressor),
    "turbine": ("sslw-turbine-v1", turbine),
}


# -- Case construction: float inputs whose recomputed size is the target ---------------------------
def fl(x: Num) -> float:
    return float(x)


def max_target(hi: Num) -> Num:
    return hi * (1 - F("1e-14"))


def size_targets(lo: Num, hi: Num, parallel: bool) -> list[tuple[str, Num]]:
    points = [
        ("S_min", lo),
        ("floor_bound_inside", lo * (1 + F("1e-6"))),
        ("geometric_mean", mpmath.sqrt(lo * hi)),
        ("S_max", max_target(hi)),
        ("below_floor", lo / 2),
    ]
    if parallel:
        points.append(("above_S_max", hi * F("2.5")))
    return points


def vessel_geometry(w_target: Num, rho: Num, t_in: Num, ld: int = 3) -> tuple[float, float]:
    """(D, L) in m, L = ld*D, whose weight is w_target (D rounded to binary64)."""

    def weight(d_in: Num) -> Num:
        return PI * (d_in + t_in) * (ld * d_in + v(VESSEL_W_LENGTH) * d_in) * t_in * rho

    d_in = mpmath.findroot(lambda d: weight(d) - w_target, mpmath.sqrt(w_target / 4))
    d_m = fl(d_in * INCH)
    return d_m, fl(ld * F(d_m))


def motor_shaft_for(w_m_target: Num) -> float:
    w_hp = mpmath.findroot(lambda w: w / motor_efficiency(w) - w_m_target, w_m_target * F("0.85"))
    return fl(w_hp / KAPPA_W)


def registered_cases() -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    hx_p = 3.0e6  # Pa, inside 100..2000 psig
    out["exchanger.shell_tube"] = [
        {
            "label": f"area {label}",
            "options": HX_DEFAULTS,
            "inputs": {"area_m2": fl(s / KAPPA_A), "P_Pa": hx_p},
        }
        for label, s in size_targets(*HX_AREA_RANGE, parallel=True)
    ]
    a_mid = fl(mpmath.sqrt(HX_AREA_RANGE[0] * HX_AREA_RANGE[1]) / KAPPA_A)
    for label, p in [
        ("pressure floor bound (100 psig)", F(100)),
        ("pressure floor bound inside", F(100) * (1 + F("1e-6"))),
        ("pressure below floor (full vacuum)", -ATM / PSI),
        ("pressure max (2000 psig)", max_target(F(2000))),
        ("pressure above max (refused)", F(2000) * (1 + F("1e-9"))),
    ]:
        out["exchanger.shell_tube"].append(
            {
                "label": label,
                "options": HX_DEFAULTS,
                "inputs": {"area_m2": a_mid, "P_Pa": fl(ATM + p * PSI)},
            }
        )
    out["exchanger.shell_tube"].append(
        {
            "label": "CarbonSteelCarbonSteel (F_M = 1)",
            "options": {**HX_DEFAULTS, "material": "CarbonSteelCarbonSteel"},
            "inputs": {"area_m2": a_mid, "P_Pa": hx_p},
        }
    )

    t_m = fl(v(VESSEL_T_SHELL_IN) * INCH)
    rho_cs = v(VESSEL_MATERIAL["CarbonSteel"][1])
    t_in = F(t_m) / INCH
    for entry, orientation, limits, platforms in [
        ("vessel.vertical", "vertical", ("1", "2"), False),
        ("vessel.horizontal", "horizontal", ("1",), True),
    ]:
        cases = []
        for limit in limits:
            opt = {
                **VESSEL_DEFAULTS,
                "orientation": orientation,
                "weight_limit": limit,
                "platforms_ladders": platforms,
            }
            if orientation == "horizontal":
                del opt["weight_limit"]  # vertical only (SSLW.py:584-587)
            for label, w in size_targets(*VESSEL_W_RANGE[limit], parallel=False):
                d_m, l_m = vessel_geometry(w, rho_cs, t_in)
                cases.append(
                    {
                        "label": f"weight_limit {limit} W {label}",
                        "options": opt,
                        "inputs": {"D_m": d_m, "L_m": l_m, "t_shell_m": t_m},
                    }
                )
        out[entry] = cases
    opt_pl = {**VESSEL_DEFAULTS, "orientation": "vertical"}
    eps = F("1e-12")
    for label, d_ft, l_ft in [
        ("platforms L and D at their floor bounds", F(3), F(12)),
        ("platforms floor bounds inside", F(3) * (1 + F("1e-6")), F(12) * (1 + F("1e-6"))),
        ("platforms L and D floored", F(2), F(8)),
        ("platforms piece 1", F(10), F(30)),
        ("platforms piece 1 at its L end", F(10), F(40) * (1 - eps)),
        ("platforms piece 2 at its L start", F(10), F(40) * (1 + eps)),
        ("platforms piece 1 at D max", F(21) * (1 - eps), F(30)),
        ("platforms piece 2 at D and L max", F(24) * (1 - eps), F(170) * (1 - eps)),
        ("platforms L above max (refused)", F(10), F(170) * (1 + F("1e-9"))),
    ]:
        out["vessel.vertical"].append(
            {
                "label": label,
                "options": opt_pl,
                "inputs": {"D_m": fl(d_ft * FT), "L_m": fl(l_ft * FT), "t_shell_m": t_m},
            }
        )
    out["vessel.vertical"].append(
        {
            "label": "design note A44 hand case (D 1 m, L 3 m)",
            "options": opt_pl,
            "inputs": {"D_m": 1.0, "L_m": 3.0, "t_shell_m": t_m},
        }
    )

    out["column.trays"] = [
        {
            "label": f"D_ft {label}",
            "options": TRAY_DEFAULTS,
            "inputs": {"D_m": fl(d * FT), "N_act": 8},
        }
        for label, d in size_targets(*TRAY_D_RANGE, parallel=False)
    ]

    head_m = fl(100 * FT)
    h_ft = F(head_m) / FT
    pump_cases = []
    for kind in ("Centrifugal", "ExternalGear", "Reciprocating"):
        opt = {**PUMP_DEFAULTS, "pump_type": kind}
        if kind != "Centrifugal":
            del opt["pump_type_factor"]  # unused: F_T = 1 for the other types (SSLW.py:1570-1571)
        for label, s in size_targets(*PUMP_SIZE_RANGE[kind], parallel=True):
            # The quantities a type does not use are fixed: Q 10 gpm, W 1000 W.
            if kind == "Centrifugal":
                q, w = s / h_ft ** v(PUMP_HEAD_EXPONENT), F(1000)
            elif kind == "ExternalGear":
                q, w = s, F(1000)
            else:
                q, w = F(10), s / KAPPA_W
            inputs = {"vol_flow_m3s": fl(q / KAPPA_Q), "head_m": head_m, "power_W": fl(w)}
            pump_cases.append({"label": f"{kind} {label}", "options": opt, "inputs": inputs})
    out["pump"] = pump_cases

    out["motor.electric"] = [
        {
            "label": f"W_m {label}",
            "options": MOTOR_DEFAULTS,
            "inputs": {"shaft_power_W": motor_shaft_for(w), "N": 1},
        }
        for label, w in size_targets(*MOTOR_RANGE, parallel=False)
    ] + [
        {
            "label": "W_hp 10 hp (design note eta_m)",
            "options": MOTOR_DEFAULTS,
            "inputs": {"shaft_power_W": fl(10 / KAPPA_W), "N": 1},
        },
    ]

    comp = []
    for kind in ("Centrifugal", "Reciprocating", "Screw"):
        opt = {**COMPRESSOR_DEFAULTS, "compressor_type": kind}
        for label, w in size_targets(*COMPRESSOR_RANGE[kind], parallel=True):
            comp.append(
                {
                    "label": f"{kind} W_hp {label}",
                    "options": opt,
                    "inputs": {"power_W": fl(w / KAPPA_W)},
                }
            )
    out["compressor"] = comp

    out["turbine"] = [
        {"label": f"W_hp {w} hp", "options": {}, "inputs": {"power_W": fl(-F(w) / KAPPA_W)}}
        for w in (10, 100, 1000)
    ]
    return out


# -- P1 and P3 sizes (the committed report fixtures) -----------------------------------------------
#: tests/fixtures/schemas/assessment_report/valid/<name>.json: (state_sha256, items). Sizes and
#: design pressures as the fixtures record them; options are IDAES's defaults (as recorded).
P_SIZES: dict[str, tuple[str, list[tuple[str, str, dict[str, Any], dict[str, Any]]]]] = {
    "p1_th_c1": (
        "a23b2407ff55ea7c4056d39f87be504592e4759ea13fdc04f4273eb304ef5c3d",
        [
            (
                "P",
                "pump",
                PUMP_DEFAULTS,
                {
                    "vol_flow_m3s": 1.8194061658708818e-05,
                    "head_m": 307.9210987223914,
                    "power_W": 72.48740658841477,
                },
            ),
            (
                "P.drive",
                "motor.electric",
                MOTOR_DEFAULTS,
                {"shaft_power_W": 72.48740658841477, "N": 1},
            ),
            (
                "B",
                "exchanger.shell_tube",
                HX_DEFAULTS,
                {"area_m2": 0.33254401500796366, "P_Pa": 3000000.0},
            ),
            ("T", "turbine", {}, {"power_W": -15905.094362301697}),
            (
                "C",
                "exchanger.shell_tube",
                HX_DEFAULTS,
                {"area_m2": 3.809791412245464, "P_Pa": 10000.0},
            ),
        ],
    ),
    "p1_th_r1": (
        "9cdbdcc20bac4c61bbb29d42328268e558997cf6630a5b62e0107415fafb105d",
        [
            (
                "H",
                "exchanger.shell_tube",
                HX_DEFAULTS,
                {"area_m2": 0.23013894935410378, "P_Pa": 500000.0},
            ),
            (
                "D.drum",
                "vessel.vertical",
                {**VESSEL_DEFAULTS, "orientation": "vertical"},
                {"D_m": 0.17464743031492239, "L_m": 0.5239422909447672, "t_shell_m": 0.03175},
            ),
            (
                "P",
                "pump",
                PUMP_DEFAULTS,
                {
                    "vol_flow_m3s": 2.0919268093386196e-05,
                    "head_m": 32.442760203582424,
                    "power_W": 8.367131010182973,
                },
            ),
            (
                "P.drive",
                "motor.electric",
                MOTOR_DEFAULTS,
                {"shaft_power_W": 8.367131010182973, "N": 1},
            ),
        ],
    ),
    "p3_m1": (
        "e496390f7e41cff7c2e3e315f7a1d8867c0c00d80aa7811f724b0dc446e2894e",
        [
            (
                "S02.shell",
                "vessel.vertical",
                {**VESSEL_DEFAULTS, "orientation": "vertical"},
                {"D_m": 0.19200006751115933, "L_m": 8.5344, "t_shell_m": 0.03175},
            ),
            ("S02.trays", "column.trays", TRAY_DEFAULTS, {"D_m": 0.19200006751115933, "N_act": 8}),
            (
                "S02.condenser",
                "exchanger.shell_tube",
                HX_DEFAULTS,
                {"area_m2": 1.0382592694262653, "P_Pa": 106000.0},
            ),
            (
                "S02.reboiler",
                "exchanger.shell_tube",
                HX_DEFAULTS,
                {"area_m2": 0.2598826710142376, "P_Pa": 106000.0},
            ),
        ],
    ),
}


# -- Escalation, chain, CRF (§4.6, §4.7) -----------------------------------------------------------
#: BLS PPI WPU11 monthly values (BLS API v2 responses retrieved 2026-10-27 by track A, raw files
#: sha256 a1ec04c4…1727 (2006) and 62bfea28…f522 (2016-2025)); the annual averages the package's
#: series carries are FRED's, to 3 decimals. The means below are recomputed from the months.
BLS_WPU11_MONTHLY = {
    2006: (
        "124.0",
        "124.2",
        "125.3",
        "125.7",
        "125.8",
        "126.1",
        "126.5",
        "127.0",
        "127.4",
        "127.3",
        "127.3",
        "127.4",
    ),
    2023: (
        "171.875",
        "172.326",
        "173.000",
        "173.658",
        "173.780",
        "173.993",
        "174.587",
        "174.935",
        "175.238",
        "175.485",
        "175.669",
        "175.760",
    ),
}
WPU11_ANNUAL = {2006: F("126.167"), 2023: F("174.192")}
#: P1 (TH-C1) basis and the F_BM test inputs of its document (tests/test_e01_a_report.py P1_DOC:
#: exchanger 3.17, pump 3.3, motor 1.5, turbine 3.5; E01A_DECISIONS "F_BM values ... test inputs").
P1_F_BM = {"P": F("3.3"), "P.drive": F("1.5"), "B": F("3.17"), "T": F("3.5"), "C": F("3.17")}
P1_OPEX_TOTAL = "34373.962267160525"  # the fixture's opex.total (an input here, not recomputed)
EBTF = (F("1.10"), F("1.14"), F("1.30"), F("1.07"))  # §4.7.1, PrISMa SI §6.3.3


def crf(i: Num, years: Num) -> Num:
    g = (1 + i) ** years
    return i * g / (g - 1)


# -- Sizing hand cases (§4.4.1, §4.4.4, §4.4.6, §9.4) ----------------------------------------------
R_GAS = F("1.380649e-23") * F("6.02214076e23")  # SI 2019 exact: k N_A = 8.31446261815324


def underwood(dt1: Num, dt2: Num) -> Num:
    return ((mpmath.cbrt(dt1) + mpmath.cbrt(dt2)) / 2) ** 3


def lmtd(dt1: Num, dt2: Num) -> Num:
    return (dt1 - dt2) / mpmath.log(dt1 / dt2)


def a10() -> dict[str, Num]:
    q, u, f_t = F("1.0e6"), F(500), F(1)
    t_steam, t_in, t_out = F("433.15"), F(300), F(400)
    dt1, dt2 = t_steam - t_out, t_steam - t_in  # heating, isothermal utility
    dtlm = underwood(dt1, dt2)
    exact = lmtd(dt1, dt2)
    return {
        "dT1": dt1,
        "dT2": dt2,
        "dT_lm": dtlm,
        "area_m2": q / (u * f_t * dtlm),
        "lmtd_exact": exact,
        "underwood_over_lmtd_minus_1": dtlm / exact - 1,
    }


def load_states() -> dict[str, Any]:
    path = HERE / "recorded_states.yaml"
    if not path.exists():
        return {}
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data


def a11(rec: Mapping[str, Any]) -> dict[str, Any]:
    """§4.4.4 vertical drum on the recorded V_L, V_V, rho_L, rho_V (defaults tau 300 s,
    phi_fill 0.5, LD 3, K_SB 0.07 m/s)."""
    vl, vv = F(rec["vdot_L_m3s"]), F(rec["vdot_V_m3s"])
    rho_l, rho_v = F(rec["rho_L_kgm3"]), F(rec["rho_V_kgm3"])
    tau, phi, ld, k_sb = F(300), F("0.5"), F(3), F("0.07")
    vol = tau * vl / phi
    d2_l = (4 * vol / (PI * ld)) ** (F(2) / 3)
    u_v = k_sb * mpmath.sqrt((rho_l - rho_v) / rho_v)
    d2_v = 4 * vv / (PI * u_v)
    controlling = "L" if d2_l >= d2_v else "V"
    d = mpmath.sqrt(max(d2_l, d2_v))
    return {
        "V_m3": vol,
        "D2_L": d2_l,
        "u_V": u_v,
        "D2_V": d2_v,
        "controlling": controlling,
        "D_m": d,
        "L_m": ld * d,
    }


def a12(rec: Mapping[str, Any]) -> dict[str, Any]:
    """§4.4.6 on the recorded stage states, with §9.4's identity volumes: v^V = RT/P,
    v^L = sum_c x_c v_c (v_c declared or V_MOLAR); M = sum_c x_c M_c."""
    m = {c: F(x) for c, x in rec["molar_mass_kg_mol"].items()}
    v_c = {c: F(x) for c, x in rec["liquid_molar_volume_m3_mol"].items()}
    c_sb, f_flood, phi_a = F("0.09"), F("0.80"), F("0.85")
    s_tray, e_o, h_top, h_bottom = F("0.6096"), F("0.70"), F("1.2192"), F("3.048")
    per_stage: dict[str, dict[str, Num]] = {}
    for j, st in sorted(rec["stages"].items(), key=lambda kv: int(kv[0])):
        t, p = F(st["T_K"]), F(st["P_Pa"])
        nv = {c: F(x) for c, x in st["vapor_mol_s"].items()}
        nl = {c: F(x) for c, x in st["liquid_mol_s"].items()}
        v_tot, l_tot = mpmath.fsum(nv.values()), mpmath.fsum(nl.values())
        v_v = R_GAS * t / p
        vdot_v = v_tot * v_v
        m_v = mpmath.fsum(nv[c] * m[c] for c in nv) / v_tot
        v_l = mpmath.fsum(nl[c] * v_c[c] for c in nl) / l_tot
        m_l = mpmath.fsum(nl[c] * m[c] for c in nl) / l_tot
        rho_v, rho_l = m_v / v_v, m_l / v_l
        u_f = c_sb * mpmath.sqrt((rho_l - rho_v) / rho_v)
        d2 = 4 * vdot_v / (PI * f_flood * phi_a * u_f)
        per_stage[str(j)] = {
            "vdot_V_m3s": vdot_v,
            "rho_V": rho_v,
            "rho_L": rho_l,
            "u_f": u_f,
            "D2_m2": d2,
        }
    j_star = max(per_stage, key=lambda j: (per_stage[j]["D2_m2"], -int(j)))
    n_tr = len(per_stage)
    n_act = int(mpmath.ceil(F(n_tr) / e_o))
    return {
        "stages": per_stage,
        "j_star": int(j_star),
        "D_m": mpmath.sqrt(per_stage[j_star]["D2_m2"]),
        "N_tr": n_tr,
        "N_act": n_act,
        "H_m": (n_act - 1) * s_tray + h_top + h_bottom,
    }


# -- Output ----------------------------------------------------------------------------------------
def s30(x: Num) -> str:
    return str(mpmath.nstr(x, 30, min_fixed=-mpmath.inf, max_fixed=mpmath.inf))


def number(x: Num) -> dict[str, Any]:
    return {"value": float(x), "mp30": s30(x)}


def render(result: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"regime": result["regime"]}
    if result["C_P"] is None:
        out["refused"] = True
        return out
    out["quantities"] = {k: number(q) for k, q in result["quantities"].items()}
    out["C_P1"] = number(result["C_P1"])
    out["C_P"] = number(result["C_P"])
    return out


def evaluate(entry: str, options: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any]:
    return FORMS[entry][1](inputs, options)


def build() -> dict[str, Any]:
    forms_out: dict[str, Any] = {}
    for entry, cases in registered_cases().items():
        forms_out[entry] = {
            "form": FORMS[entry][0],
            "cases": [
                {
                    "label": c["label"],
                    "options": dict(c["options"]),
                    "inputs": dict(c["inputs"]),
                    **render(evaluate(entry, c["options"], c["inputs"])),
                }
                for c in cases
            ],
        }

    p_out: dict[str, Any] = {}
    escalation = WPU11_ANNUAL[2023] / WPU11_ANNUAL[2006]
    p1_cp: dict[str, Num] = {}
    for name, (sha, items) in P_SIZES.items():
        rows = []
        for item, entry, opt, inputs in items:
            result = evaluate(entry, opt, inputs)
            row = {
                "item": item,
                "entry": entry,
                "options": dict(opt),
                "inputs": dict(inputs),
                **render(result),
            }
            row["purchased_at_basis"] = number(result["C_P"] * escalation)
            rows.append(row)
            if name == "p1_th_c1":
                p1_cp[item] = result["C_P"]
        p_out[name] = {"state_sha256": sha, "items": rows}

    for year, months in BLS_WPU11_MONTHLY.items():
        mean = mpmath.fsum(F(m) for m in months) / 12
        assert abs(mean - WPU11_ANNUAL[year]) <= F("0.0005"), year
    purchased = {k: p1_cp[k] * escalation for k in P1_F_BM}
    bare = {k: P1_F_BM[k] * purchased[k] for k in P1_F_BM}
    tdc = mpmath.fsum(bare.values())
    epc = EBTF[0] * EBTF[1] * EBTF[2] * tdc
    capex = EBTF[3] * epc
    i_rate, years = F("0.08"), F(20)
    factor = crf(i_rate, years)
    opex = F(P1_OPEX_TOTAL)
    chain = {
        "escalation": {
            "series": "bls-ppi-wpu11-annual-v1 (FRED annual average, 3 decimals)",
            "base": [2006, float(WPU11_ANNUAL[2006])],
            "target": [2023, float(WPU11_ANNUAL[2023])],
            "bls_monthly_means": {
                str(y): number(mpmath.fsum(F(m) for m in ms) / 12)
                for y, ms in BLS_WPU11_MONTHLY.items()
            },
            "factor": number(escalation),
            "same_basis_factor": number(WPU11_ANNUAL[2023] / WPU11_ANNUAL[2023]),
        },
        "p1_th_c1": {
            "F_BM_test_inputs": {k: float(f) for k, f in P1_F_BM.items()},
            "purchased": {k: number(x) for k, x in purchased.items()},
            "bare_module": {k: number(x) for k, x in bare.items()},
            "capex.sum_purchased": number(mpmath.fsum(purchased.values())),
            "capex.TDC": number(tdc),
            "capex.EPC": number(epc),
            "capex.CAPEX": number(capex),
            "ebtf_capex_over_tdc": number(capex / tdc),
            "CRF": number(factor),
            "opex.total_input": P1_OPEX_TOTAL,
            "annual.capital_charge": number(factor * capex),
            "tac": number(factor * capex + opex),
        },
        "crf_0.08_20": number(factor),
    }

    note_a10 = a10()
    w_case = evaluate(
        "vessel.vertical",
        {**VESSEL_DEFAULTS, "orientation": "vertical"},
        {"D_m": 1.0, "L_m": 3.0, "t_shell_m": fl(v(VESSEL_T_SHELL_IN) * INCH)},
    )
    design_note = {
        "A10": {k: number(x) for k, x in note_a10.items()},
        "A21_crf_0.08_20": number(factor),
        "A20_ebtf_ratio": number(EBTF[0] * EBTF[1] * EBTF[2] * EBTF[3]),
        "A44": {
            "F_NT": {str(k): number(tray_count_factor(k)) for k in (10, 19, 20, 21)},
            "vessel_hand_case": {
                k: number(w_case["quantities"][k]) for k in ("W_lb", "C_v", "C_PL")
            }
            | {"C_P1": number(w_case["C_P1"])},
            "eta_m_1hp": number(motor_efficiency(F(1))),
            "eta_m_10hp": number(motor_efficiency(F(10))),
            "ce_ratio": number(CE_RATIO),
            "F_P_at_100_psig": number(HX_PRESSURE[0][0] + HX_PRESSURE[1][0] + HX_PRESSURE[2][0]),
        },
    }
    # The note's stated values (design §6.1 A10, A21; §9.6 A44): agreement is part of the check.
    stated = [
        (note_a10["dT_lm"], "71.95947205233731", "1e-15"),
        (note_a10["area_m2"], "27.79342236620868", "1e-15"),
        (note_a10["lmtd_exact"], "71.92001136510889", "1e-15"),
        # The note's F_NT values are binary64 evaluations: 1.0414 rounded to binary64 (rel 4e-17)
        # and raised to N moves the result by ~N*4e-17 from the decimal value used here.
        (tray_count_factor(10), "1.4997082643358985", "2e-15"),
        (tray_count_factor(19), "1.0409949546984238", "2e-15"),
        (w_case["quantities"]["W_lb"], "6777.48970680199", "1e-13"),
        (w_case["quantities"]["C_v"], "33222.512431689356", "1e-14"),
        (w_case["quantities"]["C_PL"], "5045.446066094272", "1e-14"),
        (w_case["C_P1"], "38267.95849778363", "1e-14"),
        (motor_efficiency(F(10)), "0.8638030099054395", "1e-15"),
        (CE_RATIO, "1.2690355329949239", "1e-16"),
    ]
    for got, want, rel in stated:
        assert abs(got / F(want) - 1) <= F(rel), (s30(got), want)
    # A21 states the binary64 value within 2 ulp (CRF is evaluated on floats by the package).
    assert abs(factor - F("0.10185220882315059")) <= 2 * F(math.ulp(0.10185220882315059))
    assert abs(note_a10["underwood_over_lmtd_minus_1"] - F("5.4867e-4")) < F("5e-8")

    states = load_states()
    sizing: dict[str, Any] = {}
    if states:
        drum = a11(states["a11_th_r1_drum"])
        sizing["A11"] = {
            "host": "S11 TH-R1, flash D (item D.drum)",
            "state_sha256": states["a11_th_r1_drum"]["state_sha256"],
            **{k: (x if isinstance(x, str) else number(x)) for k, x in drum.items()},
        }
        col = a12(states["a12_m1_column"])
        sizing["A12"] = {
            "host": "S11 M1, column S02 (P3)",
            "state_sha256": states["a12_m1_column"]["state_sha256"],
            "R": number(R_GAS),
            "stages": {j: {k: number(x) for k, x in st.items()} for j, st in col["stages"].items()},
            "j_star": col["j_star"],
            "N_tr": col["N_tr"],
            "N_act": col["N_act"],
            "D_m": number(col["D_m"]),
            "H_m": number(col["H_m"]),
        }

    return {
        "id": "e01-cost-hand-v1",
        "script": "benchmarks/e01/cost_hand/cost_hand.py",
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "mpmath_dps": 30,
        "transcribed_from": SOURCE,
        "units": {
            "kappa_A_ft2_per_m2": number(KAPPA_A),
            "kappa_Q_gpm_per_m3s": number(KAPPA_Q),
            "kappa_W_hp_per_W": number(KAPPA_W),
            "psi_Pa": number(PSI),
            "ce394_to_ce500": number(CE_RATIO),
        },
        "basis": "C_P in USD at CEPCI 500 (pump and motor converted from CE 394 by 500/394.0)",
        "forms": forms_out,
        "p_sizes": p_out,
        "design_note": design_note,
        "sizing": sizing,
        "chain": chain,
    }


def text() -> str:
    return yaml.safe_dump(build(), sort_keys=False, allow_unicode=True, width=100)


def main() -> int:
    target = HERE / "cost_hand.yaml"
    if sys.argv[1:] == ["--print"]:
        sys.stdout.write(text())
        return 0
    if sys.argv[1:] == ["--check"]:
        current = target.read_text(encoding="utf-8") if target.exists() else ""
        if current != text():
            print("cost_hand.yaml is not current: run benchmarks/e01/cost_hand/cost_hand.py")
            return 1
        print("cost_hand.yaml current")
        return 0
    if sys.argv[1:]:
        raise SystemExit("usage: cost_hand.py [--print | --check]")
    target.write_text(text(), encoding="utf-8")
    return 0


if __name__ == "__main__":
    assert math.isclose(float(HP), 745.6998715822702, rel_tol=1e-16)
    sys.exit(main())
