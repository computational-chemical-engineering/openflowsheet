"""T06 representability probe for DWSIM: can each plan §6.4 fixture be built from user constants?

For every fixture of plan §6.4 (mixer, splitter, heater, ideal flash, valve, liquid pump,
conversion reactor, recycle) this script builds a small DWSIM flowsheet headless, on three
user-defined compounds carrying the SYN-001 constants (`docs/derivations/SYN-001.md` §1) and
DWSIM's "Raoult's Law" property package, runs DWSIM's solver, and records whether every object
calculated. The question it answers is *expressibility*; it does **not** compare any number
with this project, choose a tolerance, or tune either side. The values it prints are the tool's
raw output, not reference values (that is T06's `verdict`/`specifier` work).

How the SYN-001 set maps onto a DWSIM user compound (`OriginalDB = "User"`), DWSIM 9.0.5,
source `DWSIM.Thermodynamics/PropertyPackages/PropertyPackage.vb` and `Ideal.vb` at tag v9.0.5:

* Vapor pressure, equation 10 (``exp(A - B/(T + C))``, Pa) with ``A = ln P_r + L_i/(R T_b,i)``,
  ``B = L_i/R``, ``C = 0``: exactly ``P_r exp[(L_i/R)(1/T_b,i - 1/T)]``.
* Ideal-gas c_p, equation 1 (constant, J/(kmol K)): ``100 000``.
* Enthalpy of vaporization, equation 1 (constant, J/kmol): ``1000 L_i``. DWSIM returns 0 at
  ``T >= T_c``, so ``T_c`` must exceed the SYN-001 domain (440 K).
* Liquid density, equation 1 (constant; kg/m3 for a "User" compound): ``M_i / v_i = 1000``.
* Raoult's Law K-value is ``Psat_i(T)/P`` (``Ideal.vb`` ``DW_CalcFugCoeff``): no Poynting
  factor, whatever ``LiquidFugacity_UsePoyntingCorrectionFactor`` says.
* Raoult's Law enthalpy in its default "Ideal" mode (``Ideal.vb`` ``DW_CalcEnthalpy``), per
  mass: vapor ``∫_{298.15}^{T} c_p,ig dT``; liquid the same ``- ΔH_vap(T) + P/ρ_L``. The liquid
  term is ``P v``, not SYN-001's ``(P - P_r) v``, and the datum is 298.15 K, not 300 K.
  Stream enthalpies carry no formation term.
* Liquid density is incompressible only with ``LiquidDensity_CorrectExpDataForPressure``
  switched off (DWSIM's default is on); the probe switches it off (`PP_OPTIONS`).
* A conversion reactor adds a heat of reaction computed once, when the reaction is created, from
  ideal-gas formation enthalpies at 298.15 K (`FlowsheetBase.vb`, `CalcReactionStoichiometry`).

Critical constants, acentric factor and normal boiling point are required fields of a DWSIM
compound; SYN-001 defines none. The probe fills them with the values in `PLACEHOLDERS` and
records that; `--placeholders alt` reruns with different values so their influence can be seen.

Run from the repository root after `scripts/build-reference-envs.sh`:

    .venv-dwsim/bin/python spikes/references/dwsim_representability.py [--json out.json]

Not part of `scripts/check.sh`.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

import dwsim_runtime

# SYN-001 constants, verbatim from docs/derivations/SYN-001.md §1 (plan §3.1).
T_BOIL = {"A": 320.0, "B": 360.0, "C": 400.0}  # K
L_VAP = {"A": 25_000.0, "B": 30_000.0, "C": 35_000.0}  # J/mol
CP = 100.0  # J/(mol K), both phases
V_LIQ = 1.0e-4  # m3/mol
MW = 0.100  # kg/mol
P_REF = 100_000.0  # Pa
R_GAS = 8.31446261815324  # J/(mol K)
COMPONENTS = ("A", "B", "C")

# Fields DWSIM requires and SYN-001 does not define. "base" is used by default; "alt" exists
# only to show whether a result moves when they do.
PLACEHOLDERS = {
    "base": {"Tc": 1000.0, "Pc": 1.0e7, "omega": 0.0},
    "alt": {"Tc": 2500.0, "Pc": 5.0e7, "omega": 0.3},
}

EQUIMOLAR = {"A": 1.0, "B": 1.0, "C": 1.0}

# Raoult's Law package options changed from DWSIM's defaults (see Sheet.__init__).
PP_OPTIONS = {"LiquidDensity_CorrectExpDataForPressure": False}


def compound_name(c: str) -> str:
    return f"SYN001-{c}"


def make_compound(c: str, placeholders: dict[str, float]) -> Any:
    from DWSIM.Thermodynamics.BaseClasses import ConstantProperties

    cp = ConstantProperties()
    cp.Name = compound_name(c)
    cp.ID = 900_000 + COMPONENTS.index(c)
    cp.Formula = c
    cp.CAS_Number = f"syn001-{c.lower()}"
    cp.OriginalDB = "User"
    cp.CurrentDB = "User"
    cp.Molar_Weight = MW * 1000.0  # kg/kmol
    cp.Normal_Boiling_Point = T_BOIL[c]  # SYN-001's T_b is at P_r = 1e5 Pa, not 101 325 Pa
    cp.NBP = T_BOIL[c]
    cp.Critical_Temperature = placeholders["Tc"]
    cp.Critical_Pressure = placeholders["Pc"]
    cp.Acentric_Factor = placeholders["omega"]
    cp.IsHYPO = False
    cp.IsPF = False

    cp.VaporPressureEquation = "10"  # exp(A - B/(T + C)), Pa
    cp.Vapor_Pressure_Constant_A = math.log(P_REF) + L_VAP[c] / (R_GAS * T_BOIL[c])
    cp.Vapor_Pressure_Constant_B = L_VAP[c] / R_GAS
    cp.Vapor_Pressure_Constant_C = 0.0
    cp.Vapor_Pressure_Constant_D = 0.0
    cp.Vapor_Pressure_Constant_E = 0.0

    cp.IdealgasCpEquation = "1"  # constant, J/(kmol K)
    cp.Ideal_Gas_Heat_Capacity_Const_A = CP * 1000.0
    # Used only by the "experimental liquid" enthalpy mode, but AUX_HVAPi reads the
    # vaporization-enthalpy equation only when this field is not "0".
    cp.LiquidHeatCapacityEquation = "1"
    cp.Liquid_Heat_Capacity_Const_A = CP * 1000.0

    cp.VaporizationEnthalpyEquation = "1"  # constant, J/kmol
    cp.HVap_A = L_VAP[c] * 1000.0

    cp.LiquidDensityEquation = "1"  # constant, kg/m3 for a "User" compound
    cp.Liquid_Density_Const_A = MW / V_LIQ

    # Ideal-gas formation enthalpy at 298.15 K, kJ/kg; read only by reactions, which must be
    # created after it is set. SYN-001 has no formation data; its datum puts every liquid at 0
    # and every vapor at +L_i at T_r. Entering L_i here reproduces that datum for a reaction
    # between liquids (the ideal-gas heat of reaction L_B - L_A is cancelled by the liquid
    # streams sitting ΔH_vap below the ideal gas). A synthetic choice for the conversion-reactor
    # fixture only; it has no effect on any non-reacting fixture.
    cp.IG_Enthalpy_of_Formation_25C = L_VAP[c] / (MW * 1000.0)
    cp.IG_Gibbs_Energy_of_Formation_25C = 0.0
    return cp


class Sheet:
    """One DWSIM flowsheet with the SYN-001 compounds and the Raoult's Law package."""

    def __init__(self, automation: Any, placeholders: dict[str, float]) -> None:
        self.automation = automation
        self.fs = automation.CreateFlowsheet()
        self.compounds = {c: make_compound(c, placeholders) for c in COMPONENTS}
        for cp in self.compounds.values():
            self.fs.AvailableCompounds[cp.Name] = cp
            self.fs.AddCompound(cp.Name)
        self.pp = self.fs.CreateAndAddPropertyPackage("Raoult's Law").__implementation__
        # DWSIM's default multiplies "experimental" liquid densities by a compressed-liquid
        # correction built from T_c, P_c, omega and Psat (PropertyPackage.vb, AUX_LIQDENS).
        # SYN-001's liquid is incompressible, so the SYN-001-consistent setting is off. With it
        # on, pump power and valve outlet temperature move with the placeholder constants.
        self.pp.LiquidDensity_CorrectExpDataForPressure = PP_OPTIONS[
            "LiquidDensity_CorrectExpDataForPressure"
        ]
        self._x = 0

    def add(self, kind: str, tag: str) -> Any:
        from DWSIM.Interfaces.Enums.GraphicObjects import ObjectType

        self._x += 60
        obj = self.fs.AddObject(getattr(ObjectType, kind), self._x, 50, tag)
        # AddObject is declared to return the ISimulationObject interface; pythonnet then wraps
        # the interface only, so unwrap to the concrete unit/stream class.
        return obj.__implementation__

    def material(self, tag: str) -> Any:
        return self.add("MaterialStream", tag)

    def feed(self, tag: str, flows: dict[str, float], temperature: float, pressure: float) -> Any:
        ms = self.material(tag)
        ms.SetTemperature(temperature)
        ms.SetPressure(pressure)
        ms.SetMolarFlow(sum(flows.values()))
        for c in COMPONENTS:
            ms.SetOverallCompoundMolarFlow(compound_name(c), flows[c])
        return ms

    def solve(self) -> dict[str, Any]:
        errors = self.automation.CalculateFlowsheet4(self.fs)
        messages = [str(e.Message) for e in errors] if errors is not None else []
        calculated = {
            str(o.GraphicObject.Tag): bool(o.Calculated) for o in self.fs.SimulationObjects.Values
        }
        return {"solver_errors": messages, "calculated": calculated}


def input_mapping_readback(sheet: Sheet) -> dict[str, Any]:
    """What the Raoult's Law package itself evaluates from the constants just entered.

    These are the routines `DW_CalcFugCoeff` and `DW_CalcEnthalpy` call (`AUX_PVAPi`,
    `AUX_CPi`, `AUX_HVAPi`, `AUX_LIQDENSi`), in DWSIM's units, read back to confirm the unit
    conversions of the mapping. `ConstantProperties.GetEnthalpyOfVaporization` is *not* used:
    it takes a different code path (a Watson scaling of `HVap_A`) from the one the property
    package uses for a "User" compound, and reports a different value.
    """
    stream = sheet.feed("READBACK", EQUIMOLAR, 360.0, P_REF)
    sheet.pp.CurrentMaterialStream = stream
    out: dict[str, Any] = {}
    for c, cp in sheet.compounds.items():
        name = compound_name(c)
        out[c] = {
            "AUX_PVAPi_at_T_boil_Pa": float(sheet.pp.AUX_PVAPi(name, T_BOIL[c])),
            "AUX_CPi_at_360K_kJ_per_kg_K": float(sheet.pp.AUX_CPi(name, 360.0)),
            "AUX_HVAPi_at_360K_kJ_per_kg": float(sheet.pp.AUX_HVAPi(name, 360.0)),
            "AUX_LIQDENSi_at_360K_kg_per_m3": float(sheet.pp.AUX_LIQDENSi(cp, 360.0)),
        }
    return out


def nullable(value: Any) -> float | None:
    """pythonnet maps a .NET Nullable<double> to a float or None."""
    return None if value is None else float(value)


def molar_flow(ms: Any) -> float:
    return float(ms.GetMolarFlow())


def fixture_mixer(sheet: Sheet) -> dict[str, Any]:
    s1 = sheet.feed("S1", EQUIMOLAR, 300.0, P_REF)
    s6 = sheet.feed("S6", {"A": 0.2, "B": 0.6, "C": 0.8}, 360.0, P_REF)
    s2 = sheet.material("S2")
    mx = sheet.add("NodeIn", "MIX")
    mx.ConnectFeedMaterialStream(s1, 0)
    mx.ConnectFeedMaterialStream(s6, 1)
    mx.ConnectProductMaterialStream(s2, 0)
    out = sheet.solve()
    out["unit_settings"] = {"PressureCalculation": str(mx.PressureCalculation)}
    out["tool_outlet_T_K"] = float(s2.GetTemperature())
    return out


def fixture_splitter(sheet: Sheet) -> dict[str, Any]:
    s5 = sheet.feed("S5", {"A": 0.2, "B": 0.6, "C": 0.8}, 360.0, P_REF)
    s6 = sheet.material("S6")
    s7 = sheet.material("S7")
    sp = sheet.add("NodeOut", "SPLIT")
    sp.ConnectFeedMaterialStream(s5, 0)
    sp.ConnectProductMaterialStream(s6, 0)
    sp.ConnectProductMaterialStream(s7, 1)
    # Splitter.vb keeps three ratios and, with two outlets, sets Ratios(1) = 1 - Ratios(0).
    # It splits the mass flow; at equal composition that is the molar split r.
    sp.Ratios[0] = 0.5
    out = sheet.solve()
    out["tool_recycle_flow"] = molar_flow(s6)
    return out


def _heater(sheet: Sheet, inlet: Any, outlet: Any, t_out: float) -> Any:
    from DWSIM.UnitOperations.UnitOperations import Heater

    q = sheet.add("EnergyStream", "Q-HEAT")
    ht = sheet.add("Heater", "HEAT")
    ht.ConnectFeedMaterialStream(inlet, 0)
    ht.ConnectProductMaterialStream(outlet, 0)
    ht.ConnectFeedEnergyStream(q, 1)
    ht.CalcMode = Heater.CalculationMode.OutletTemperature
    ht.OutletTemperature = t_out
    ht.DeltaP = 0.0
    return ht


def fixture_heater(sheet: Sheet) -> dict[str, Any]:
    s2 = sheet.feed("S2", EQUIMOLAR, 321.2, P_REF)
    s3 = sheet.material("S3")
    ht = _heater(sheet, s2, s3, 350.0)
    out = sheet.solve()
    out["tool_heat_duty_kW"] = nullable(ht.DeltaQ)
    return out


def _flash(sheet: Sheet, inlet: Any, vap: Any, liq: Any, t_flash: float) -> Any:
    q = sheet.add("EnergyStream", "Q-FLASH")
    fl = sheet.add("Vessel", "FLASH")
    fl.ConnectFeedMaterialStream(inlet, 0)
    fl.ConnectProductMaterialStream(vap, 0)
    fl.ConnectProductMaterialStream(liq, 1)
    fl.ConnectFeedEnergyStream(q, 6)
    # Isothermal flash at the vessel pressure; the duty is computed (Vessel.vb, Legacy mode).
    fl.OverrideT = True
    fl.FlashTemperature = t_flash
    return fl


def fixture_flash(sheet: Sheet) -> dict[str, Any]:
    s3 = sheet.feed("S3", EQUIMOLAR, 350.0, P_REF)
    s4 = sheet.material("S4")
    s5 = sheet.material("S5")
    fl = _flash(sheet, s3, s4, s5, 360.0)
    out = sheet.solve()
    out["tool_vap_flow"] = molar_flow(s4)
    out["tool_heat_duty_kW"] = nullable(fl.DeltaQ)
    return out


def fixture_valve(sheet: Sheet) -> dict[str, Any]:
    from DWSIM.UnitOperations.UnitOperations import Valve

    s_in = sheet.feed("IN", EQUIMOLAR, 300.0, 2.0e5)
    s_out = sheet.material("OUT")
    vv = sheet.add("Valve", "VALVE")
    vv.ConnectFeedMaterialStream(s_in, 0)
    vv.ConnectProductMaterialStream(s_out, 0)
    vv.CalcMode = Valve.CalculationMode.OutletPressure
    vv.OutletPressure = P_REF
    out = sheet.solve()
    out["tool_outlet_T_K"] = float(s_out.GetTemperature())
    return out


def fixture_pump(sheet: Sheet) -> dict[str, Any]:
    from DWSIM.UnitOperations.UnitOperations import Pump

    s_in = sheet.feed("IN", EQUIMOLAR, 300.0, P_REF)
    s_out = sheet.material("OUT")
    w = sheet.add("EnergyStream", "W-PUMP")
    pu = sheet.add("Pump", "PUMP")
    pu.ConnectFeedMaterialStream(s_in, 0)
    pu.ConnectProductMaterialStream(s_out, 0)
    pu.ConnectFeedEnergyStream(w, 1)
    pu.CalcMode = Pump.CalculationMode.OutletPressure
    pu.Pout = 2.0e5
    pu.Eficiencia = 75.0  # percent
    out = sheet.solve()
    out["tool_power_kW"] = nullable(pu.DeltaQ)
    out["tool_outlet_T_K"] = float(s_out.GetTemperature())
    return out


def fixture_conversion_reactor(sheet: Sheet) -> dict[str, Any]:
    from System import Double, String
    from System.Collections.Generic import Dictionary

    stoich = Dictionary[String, Double]()
    stoich[compound_name("A")] = -1.0
    stoich[compound_name("B")] = 1.0
    rxn = sheet.fs.CreateConversionReaction(
        "R1", "synthetic A -> B", stoich, compound_name("A"), "Liquid", "60"
    )
    sheet.fs.AddReaction(rxn)
    sheet.fs.AddReactionToSet(rxn.ID, "DefaultSet", True, 0)

    from DWSIM.UnitOperations.Reactors import OperationMode

    s_in = sheet.feed("IN", EQUIMOLAR, 300.0, P_REF)
    s_vap = sheet.material("OUT-V")
    s_liq = sheet.material("OUT-L")
    q = sheet.add("EnergyStream", "Q-RCT")
    rc = sheet.add("RCT_Conversion", "RCT")
    rc.ConnectFeedMaterialStream(s_in, 0)
    rc.ConnectProductMaterialStream(s_vap, 0)
    rc.ConnectProductMaterialStream(s_liq, 1)
    rc.ConnectFeedEnergyStream(q, 1)
    rc.ReactorOperationMode = OperationMode.Isothermic
    rc.DeltaP = 0.0
    out = sheet.solve()
    out["tool_heat_duty_kW"] = nullable(rc.DeltaQ)
    out["tool_conversions"] = {str(k.Key): float(k.Value) for k in rc.ComponentConversions}
    return out


def compound_flows(ms: Any) -> dict[str, float]:
    return {c: float(ms.Phases[0].Compounds[compound_name(c)].MolarFlow) for c in COMPONENTS}


def _recycle(sheet: Sheet, tight: bool) -> dict[str, Any]:
    """The SYN-001 loop, torn on S6 by a DWSIM Recycle block (sequential modular)."""
    s1 = sheet.feed("S1", EQUIMOLAR, 300.0, P_REF)
    s2 = sheet.material("S2")
    s3 = sheet.material("S3")
    s4 = sheet.material("S4")
    s5 = sheet.material("S5")
    s6_out = sheet.material("S6-split")
    s6 = sheet.feed("S6", {"A": 0.2, "B": 0.6, "C": 0.8}, 360.0, P_REF)  # tear guess
    s7 = sheet.material("S7")
    mx = sheet.add("NodeIn", "MIX")
    mx.ConnectFeedMaterialStream(s1, 0)
    mx.ConnectFeedMaterialStream(s6, 1)
    mx.ConnectProductMaterialStream(s2, 0)
    _heater(sheet, s2, s3, 350.0)
    _flash(sheet, s3, s4, s5, 360.0)
    sp = sheet.add("NodeOut", "SPLIT")
    sp.ConnectFeedMaterialStream(s5, 0)
    sp.ConnectProductMaterialStream(s6_out, 0)
    sp.ConnectProductMaterialStream(s7, 1)
    sp.Ratios[0] = 0.5
    rec = sheet.add("OT_Recycle", "REC")
    rec.ConnectFeedMaterialStream(s6_out, 0)
    rec.ConnectProductMaterialStream(s6, 0)
    conv = rec.ConvergenceParameters
    defaults = {
        "mass_flow_kg_per_s": float(conv.VazaoMassica),
        "temperature_K": float(conv.Temperatura),
        "pressure_Pa": float(conv.Pressao),
        "maximum_iterations": int(rec.MaximumIterations),
    }
    if tight:
        # A probe setting to show that the loop can be closed tightly, not a registered choice:
        # DWSIM's default mass-flow tolerance (0.01 kg/s, absolute) is ~6 % of this recycle.
        conv.VazaoMassica = 1.0e-10
        conv.Temperatura = 1.0e-6
        conv.Pressao = 1.0e-3
        rec.MaximumIterations = 500
    out = sheet.solve()
    fresh, vapor, purge = compound_flows(s1), compound_flows(s4), compound_flows(s7)
    out["recycle_tolerances_default"] = defaults
    out["recycle_tolerances_used"] = {
        "mass_flow_kg_per_s": float(conv.VazaoMassica),
        "temperature_K": float(conv.Temperatura),
        "pressure_Pa": float(conv.Pressao),
        "maximum_iterations": int(rec.MaximumIterations),
    }
    out["recycle_converged_flag"] = bool(rec.Converged)
    out["recycle_iterations_taken"] = int(rec.IterationsTaken)
    out["recycle_acceleration"] = str(rec.AccelerationMethod)
    # Tool-internal consistency of the converged loop: the overall component balance
    # fresh = vapor product + purge, which holds only when the tear has actually closed. (The
    # tear streams themselves agree exactly after convergence: DWSIM copies one onto the other.)
    out["overall_component_balance_max_abs_mol_per_s"] = max(
        abs(fresh[c] - vapor[c] - purge[c]) for c in COMPONENTS
    )
    out["tool_vap_flow"] = molar_flow(s4)
    out["tool_liq_flow"] = molar_flow(s5)
    return out


def fixture_recycle(sheet: Sheet) -> dict[str, Any]:
    return _recycle(sheet, tight=False)


def fixture_recycle_tight(sheet: Sheet) -> dict[str, Any]:
    return _recycle(sheet, tight=True)


FIXTURES: dict[str, Callable[[Sheet], dict[str, Any]]] = {
    "mixer": fixture_mixer,
    "splitter": fixture_splitter,
    "heater": fixture_heater,
    "ideal_flash": fixture_flash,
    "valve": fixture_valve,
    "liquid_pump": fixture_pump,
    "conversion_reactor": fixture_conversion_reactor,
    "recycle": fixture_recycle,
    "recycle_tight": fixture_recycle_tight,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env", type=Path, default=dwsim_runtime.DEFAULT_ENV)
    parser.add_argument("--placeholders", choices=sorted(PLACEHOLDERS), default="base")
    parser.add_argument("--json", type=Path, help="write the records to this file as well")
    args = parser.parse_args()
    json_path = args.json.resolve() if args.json else None
    placeholders = PLACEHOLDERS[args.placeholders]

    automation = dwsim_runtime.start(args.env.resolve())
    probe = Sheet(automation, placeholders)
    records: dict[str, Any] = {
        "tool": "DWSIM",
        "dwsim_version": str(automation.GetVersion()),
        "property_package": "Raoult's Law",
        "component_set": "SYN-001 constants as DWSIM user compounds (A, B, C)",
        "placeholders": {"set": args.placeholders, **placeholders},
        "property_package_options": PP_OPTIONS,
        "input_mapping_readback": input_mapping_readback(probe),
        "flash_algorithm": probe.pp.FlashBase.GetType().FullName,
        "flash_settings": {str(kv.Key): str(kv.Value) for kv in probe.pp.FlashSettings},
        "fixtures": {},
    }
    failures = 0
    for name, build in FIXTURES.items():
        try:
            rec = build(Sheet(automation, placeholders))
            rec["built"] = True
            ok = not rec["solver_errors"] and all(rec["calculated"].values())
        except Exception as exc:  # every failure is recorded, none is hidden
            rec = {
                "built": False,
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(limit=4),
            }
            ok = False
        rec["status"] = "RAN" if ok else "FAILED"
        failures += 0 if ok else 1
        records["fixtures"][name] = rec
        print(f"{name:20s} {rec['status']}", file=sys.stderr)

    text = json.dumps(records, indent=2)
    print(text)
    if json_path is not None:
        json_path.write_text(text + "\n", encoding="utf-8")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
