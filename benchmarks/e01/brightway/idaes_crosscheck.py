"""E01 WO-B4 (design §5.3, §9.5; A15): the IDAES evaluation of cost_hand's cases.

A one-off run in a scratch IDAES environment (idaes-pse 2.13.0 from the pinned wheel, its own
dependencies), never in the project's environments; the committed `idaes_crosscheck.yaml` records
the versions, this script's sha256 and every value. It evaluates IDAES's own costing methods
(`SSLWCostingData`, SSLW.py at the pinned sha256) at our *effective* inputs (§9.5):

- floored values in place of the item's (area 150 ft², 100 psig, W_min, D_ft = 2, S_min, ...),
  and N (`number_of_units`) for parallel forms;
- the vessel through `cost_vessel` directly (departure 3), with platforms off, and the platform
  term through `_cost_platforms_ladders` at the floored D and L with the selected formula passed as
  `aspect_ratio_range` (departure 4); a floored weight is fixed at W_min in place of `weight_eq`;
- the trays through `_cost_distillation_trays`, rescaled by max(1, f)/value(number_trays_factor)
  (departure 2: IDAES's smooth_max with eps = 1e-4);
- pump and motor read as `pump_capital_cost` and `motor_capital_cost` (USD_CE500).

The unit model is a stand-in namespace holding the Pyomo variables the methods read (area and the
hot side's inlet pressure; work, deltaP, inlet density and volumetric flow; the config flags).
Every constraint the methods write is `var == expression` in declaration order, so each is
solved for its one free variable in turn (`calculate_variable_from_constraint`).

Usage (scratch env): `<venv-idaes>/bin/python -I benchmarks/e01/brightway/idaes_crosscheck.py`
writes `idaes_crosscheck.yaml` beside it; `--print` writes to stdout.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import math
import platform
import sys
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import idaes  # type: ignore[import-not-found,unused-ignore]
import pyomo.environ as pyo
import pyomo.version
import yaml
from idaes.core.base.costing_base import (  # type: ignore[import-not-found,unused-ignore]
    register_idaes_currency_units,
)
from idaes.models.costing import SSLW  # type: ignore[import-not-found,unused-ignore]
from idaes.models.unit_models.pressure_changer import (  # type: ignore[import-not-found,unused-ignore]
    ThermodynamicAssumption,
)
from pyomo.core.expr.visitor import identify_variables
from pyomo.util.calc_var_value import calculate_variable_from_constraint

HERE = Path(__file__).resolve().parent
HAND = HERE.parent / "cost_hand" / "cost_hand.yaml"
U = pyo.units
FT, INCH = 0.3048, 0.0254
ATM, PSI = 101325.0, 6894.757293168361
KAPPA_A, KAPPA_Q, KAPPA_W = 1 / FT**2, 60 / 3.785411784e-3, 1 / 745.6998715822702
G = 9.80665

#: Effective-input floors (the ranges of §9.2.4; the same numbers as cost_hand.py's).
HX_AREA_MIN, HX_P_MIN = 150.0, 100.0
W_MIN = {"1": 1000.0, "2": 4200.0}
TRAY_D_MIN = 2.0
PUMP_MIN = {"Centrifugal": 400.0, "ExternalGear": 10.0, "Reciprocating": 1.0}
COMPRESSOR_MIN = {"Centrifugal": 200.0, "Reciprocating": 100.0, "Screw": 10.0}
PL_FLOOR = {"L": 12.0, "D": 3.0}


def _var(m: Any, name: str, value: float, units: Any) -> Any:
    var = pyo.Var(initialize=value, units=units)
    m.add_component(name, var)
    var.fix(value)
    return var


def _solve(blk: Any) -> None:
    for con in blk.component_data_objects(pyo.Constraint, active=True, descend_into=True):
        free = [v for v in identify_variables(con.body) if not v.fixed]
        assert len(free) == 1, (con.name, [v.name for v in free])
        calculate_variable_from_constraint(free[0], con)
        free[0].fix()


def _model() -> tuple[Any, Any]:
    m = pyo.ConcreteModel()
    m.costing = pyo.Block()
    return m, m.costing


def _unit(**fields: Any) -> SimpleNamespace:
    return SimpleNamespace(
        name="unit",
        flowsheet=lambda: SimpleNamespace(time=SimpleNamespace(first=lambda: 0)),
        **fields,
    )


def _units(regime: Mapping[str, str]) -> int:
    size = regime.get("size", "units:1")
    return int(size.split(":")[1]) if size.startswith("units:") else 1


def exchanger(case: Mapping[str, Any]) -> dict[str, float]:
    x, opt, regime = case["inputs"], case["options"], case["regime"]
    n = _units(regime)
    area = HX_AREA_MIN / KAPPA_A if regime["size"] == "floor" else x["area_m2"]
    pressure = ATM + HX_P_MIN * PSI if regime["pressure"] == "floor" else x["P_Pa"]
    m, blk = _model()
    blk.unit_model = _unit(
        area=_var(m, "area", area, U.m**2),
        hot_side=SimpleNamespace(
            properties_in={0: SimpleNamespace(pressure=_var(m, "p", pressure, U.Pa))}
        ),
    )
    SSLW.SSLWCostingData.cost_heat_exchanger(
        blk,
        hx_type=SSLW.HXType[opt["hx_type"]],
        material_type=SSLW.HXMaterial[opt["material"]],
        tube_length=SSLW.HXTubeLength[opt["tube_length"]],
    )
    blk.number_of_units.fix(n)
    _solve(blk)
    return {"C_P": pyo.value(blk.capital_cost), "N": n, "area_m2": area, "P_Pa": pressure}


def vessel(case: Mapping[str, Any], entry: str) -> dict[str, float]:
    x, opt, regime = case["inputs"], case["options"], case["regime"]
    vertical = entry == "vessel.vertical"
    limit = int(opt.get("weight_limit", "1"))
    m, blk = _model()
    d = _var(m, "D", x["D_m"], U.m)
    length = _var(m, "L", x["L_m"], U.m)
    SSLW.SSLWCostingData.cost_vessel(
        blk,
        vertical=vertical,
        material_type=SSLW.VesselMaterial[opt["material"]],
        shell_thickness=x["t_shell_m"] / INCH * U.inch,
        weight_limit=limit,
        include_platforms_ladders=False,
        vessel_diameter=d,
        vessel_length=length,
    )
    out: dict[str, float] = {}
    if regime["size"] == "floor":
        blk.weight_eq.deactivate()
        blk.weight.fix(W_MIN[str(limit)])
        out["W_lb"] = W_MIN[str(limit)]
    _solve(blk)
    out.setdefault("W_lb", pyo.value(blk.weight))
    shell = pyo.value(blk.capital_cost)
    platforms = 0.0
    if opt["platforms_ladders"]:
        d_ft, l_ft = x["D_m"] / FT, x["L_m"] / FT
        formula = 1
        if vertical:
            if regime["platforms.L"] == "floor":
                l_ft = PL_FLOOR["L"]
            formula = 2 if regime["platforms.L"] == "2" else 1
            if regime["platforms.D"] == "floor":
                d_ft = PL_FLOOR["D"]
        m2, blk2 = _model()
        SSLW.SSLWCostingData._cost_platforms_ladders(
            blk2,
            vertical=vertical,
            aspect_ratio_range=formula,
            vessel_diameter=_var(m2, "D", d_ft * FT, U.m),
            vessel_length=_var(m2, "L", l_ft * FT, U.m),
        )
        _solve(blk2)
        platforms = pyo.value(blk2.base_cost_platforms_ladders)
        out.update({"platform_D_ft": d_ft, "platform_L_ft": l_ft, "aspect_ratio_range": formula})
    return {"C_P": shell + platforms, "shell": shell, "platforms": platforms, **out}


def trays(case: Mapping[str, Any]) -> dict[str, float]:
    x, opt, regime = case["inputs"], case["options"], case["regime"]
    d_ft = TRAY_D_MIN if regime["size"] == "floor" else x["D_m"] / FT
    n_act = int(x["N_act"])
    m, blk = _model()
    SSLW.SSLWCostingData._cost_distillation_trays(
        blk,
        tray_material=SSLW.TrayMaterial[opt["tray_material"]],
        tray_type=SSLW.TrayType[opt["tray_type"]],
        vessel_diameter=_var(m, "D", d_ft * FT, U.m),
        number_of_trays=n_act,
    )
    _solve(blk)
    smooth = pyo.value(blk.number_trays_factor)
    exact = max(1.0, 2.25 / 1.0414**n_act)
    raw = pyo.value(blk.base_cost_trays)
    return {
        "C_P": raw * exact / smooth,
        "idaes_raw": raw,
        "smooth_max": smooth,
        "max": exact,
        "D_ft": d_ft,
    }


def _pump_block(
    work: float,
    delta_p: float,
    flow: float,
    opt: Mapping[str, str],
    n: int,
    motor_type: str = "Open",
) -> Any:
    m, blk = _model()
    blk.unit_model = _unit(
        config=SimpleNamespace(
            compressor=True, thermodynamic_assumption=ThermodynamicAssumption.pump
        ),
        work_mechanical={0: _var(m, "W", work, U.W)},
        deltaP={0: _var(m, "dP", delta_p, U.Pa)},
        control_volume=SimpleNamespace(
            properties_in={
                0: SimpleNamespace(
                    dens_mass=_var(m, "rho", 1000.0, U.kg / U.m**3),
                    flow_vol=_var(m, "Q", flow, U.m**3 / U.s),
                )
            }
        ),
    )
    SSLW.SSLWCostingData.cost_pump(
        blk,
        pump_type=SSLW.PumpType[opt["pump_type"]],
        material_type=SSLW.PumpMaterial[opt["material"]],
        pump_type_factor=float(opt.get("pump_type_factor", "1.4")),
        motor_type=SSLW.PumpMotorType[motor_type],
    )
    blk.number_of_units.fix(n)
    _solve(blk)
    return blk


def pump(case: Mapping[str, Any]) -> dict[str, float]:
    x, opt, regime = case["inputs"], case["options"], case["regime"]
    kind = opt["pump_type"]
    n = _units(regime)
    flow, work, head = x["vol_flow_m3s"], x["power_W"], x["head_m"]
    if regime["size"] == "floor":
        if kind == "Centrifugal":
            flow = PUMP_MIN[kind] / (head / FT) ** 0.5 / KAPPA_Q
        elif kind == "ExternalGear":
            flow = PUMP_MIN[kind] / KAPPA_Q
        else:
            work = PUMP_MIN[kind] / KAPPA_W
    blk = _pump_block(work, head * G * 1000.0, flow, opt, n)
    return {
        "C_P": pyo.value(blk.pump_capital_cost),
        "N": n,
        "vol_flow_m3s": flow,
        "power_W": work,
        "deltaP_Pa": head * G * 1000.0,
    }


def motor(case: Mapping[str, Any], floor_shaft: float) -> dict[str, float]:
    x, opt, regime = case["inputs"], case["options"], case["regime"]
    n = int(x["N"])
    work = floor_shaft * n if regime["size"] == "floor" else x["shaft_power_W"]
    pump_opt = {"pump_type": "Centrifugal", "material": "StainlessSteel"}
    blk = _pump_block(work, 1.0e5, 1.0e-3, pump_opt, n, motor_type=opt["motor_type"])
    return {"C_P": pyo.value(blk.motor_capital_cost), "N": n, "shaft_power_W": work}


def compressor(case: Mapping[str, Any]) -> dict[str, float]:
    x, opt, regime = case["inputs"], case["options"], case["regime"]
    kind = opt["compressor_type"]
    n = _units(regime)
    work = COMPRESSOR_MIN[kind] / KAPPA_W if regime["size"] == "floor" else x["power_W"]
    m, blk = _model()
    blk.unit_model = _unit(
        config=SimpleNamespace(
            compressor=True, thermodynamic_assumption=ThermodynamicAssumption.isentropic
        ),
        work_mechanical={0: _var(m, "W", work, U.W)},
    )
    SSLW.SSLWCostingData.cost_compressor(
        blk,
        compressor_type=SSLW.CompressorType[kind],
        drive_type=SSLW.CompressorDriveType[opt["drive_type"]],
        material_type=SSLW.CompressorMaterial[opt["material"]],
    )
    blk.number_of_units.fix(n)
    _solve(blk)
    return {"C_P": pyo.value(blk.capital_cost), "N": n, "power_W": work}


def turbine(case: Mapping[str, Any]) -> dict[str, float]:
    m, blk = _model()
    blk.unit_model = _unit(
        config=SimpleNamespace(compressor=False),
        work_mechanical={0: _var(m, "W", case["inputs"]["power_W"], U.W)},
    )
    SSLW.SSLWCostingData.cost_turbine(blk)
    _solve(blk)
    return {"C_P": pyo.value(blk.capital_cost), "power_W": case["inputs"]["power_W"]}


def evaluate(entry: str, case: Mapping[str, Any], floor_shaft: float) -> dict[str, float]:
    if entry == "exchanger.shell_tube":
        return exchanger(case)
    if entry.startswith("vessel."):
        return vessel(case, entry)
    if entry == "column.trays":
        return trays(case)
    if entry == "pump":
        return pump(case)
    if entry == "motor.electric":
        return motor(case, floor_shaft)
    if entry == "compressor":
        return compressor(case)
    if entry == "turbine":
        return turbine(case)
    raise AssertionError(entry)


def build() -> dict[str, Any]:
    register_idaes_currency_units()
    hand = yaml.safe_load(HAND.read_text(encoding="utf-8"))
    floor_shaft = next(
        c["inputs"]["shaft_power_W"]
        for c in hand["forms"]["motor.electric"]["cases"]
        if c["label"] == "W_m S_min"
    )
    forms: dict[str, list[dict[str, Any]]] = {}
    for entry, block in hand["forms"].items():
        forms[entry] = [
            {"label": case["label"], **evaluate(entry, case, floor_shaft)}
            for case in block["cases"]
            if not case.get("refused")
        ]
    p_sizes: dict[str, list[dict[str, Any]]] = {}
    for name, block in hand["p_sizes"].items():
        p_sizes[name] = [
            {"item": row["item"], **evaluate(row["entry"], row, floor_shaft)}
            for row in block["items"]
        ]
    for rows in [*forms.values(), *p_sizes.values()]:
        for row in rows:
            assert math.isfinite(row["C_P"]) and row["C_P"] > 0, row
    sslw = Path(SSLW.__file__).read_bytes()
    return {
        "id": "e01-idaes-crosscheck-v1",
        "script": "benchmarks/e01/brightway/idaes_crosscheck.py",
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "cases_from": "benchmarks/e01/cost_hand/cost_hand.yaml",
        "cases_sha256": hashlib.sha256(HAND.read_bytes()).hexdigest(),
        "environment": {
            "idaes_pse": idaes.__version__,
            "pyomo": pyomo.version.version,
            "pint": importlib.metadata.version("pint"),
            "python": platform.python_version(),
            "machine": platform.machine(),
            "SSLW.py_sha256": hashlib.sha256(sslw).hexdigest(),
        },
        "basis": "C_P in USD_CE500; pump and motor are IDAES's pump_capital_cost and "
        "motor_capital_cost (converted from USD_CE394 by IDAES's units)",
        "forms": forms,
        "p_sizes": p_sizes,
    }


def main() -> int:
    text = yaml.safe_dump(build(), sort_keys=False, allow_unicode=True, width=100)
    if sys.argv[1:] == ["--print"]:
        sys.stdout.write(text)
    elif not sys.argv[1:]:
        (HERE / "idaes_crosscheck.yaml").write_text(text, encoding="utf-8")
    else:
        raise SystemExit("usage: idaes_crosscheck.py [--print]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
