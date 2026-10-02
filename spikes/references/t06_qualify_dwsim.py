"""T06 M6: blind reference qualification in DWSIM — accept, converge, and rule 2's self-check.

For each fixture of `t06_fixtures.FIXTURES` (spec §9.2's REF-01 ... REF-08, §9.4's PC-1 and
PC-2) this script builds a DWSIM flowsheet headless on SYN-001's constants as user compounds
(`dwsim_representability.make_compound`, i.e. `docs/reference-environments.md` §5.0) with the
Raoult's Law package, applies spec §9.3's settings and input mappings, calculates it, and writes
one JSON per fixture with:

* ``accepted`` — every object was created, connected and configured without an exception;
* ``converged`` — DWSIM calculated every object and reported no solver error (and, for REF-08,
  its Recycle block reports convergence within its iteration limit);
* ``self_check`` — rule 2 (§9.5): DWSIM's own overall component balance, from its own streams;
  and, as further tool-internal evidence, the energy balance over the fixture boundary from its
  own stream enthalpies and energy streams, and the phase-equilibrium residual of its own
  two-phase results against its own vapour pressures;
* DWSIM's raw output (every stream and energy stream, unit results), versions, the environment
  fingerprint, the settings as read back from DWSIM, every adjustment made, and wall times;
* ``compared_quantities`` — spec §9.2's compared quantities of the fixture, named by
  `t06_fixtures.COMPARED` and computed from the raw output alone by
  `t06_fixtures.dwsim_compared_quantities` (T06 W8), so that they recompute from the record.

§9.3's mappings: ΔH_vap,i := L_i + P_r v_i (PC-1: L_i, unmapped), ideal-gas formation enthalpy
ΔH_f,ig,i := L_i + P_r v_i, liquid-density pressure correction off, placeholders T_c 1000 K,
P_c 1e7 Pa, ω 0, NBP = T_b,i.

It is blind (spec §9.6): nothing of this project, and not the twin, is read. It prints only the
flags. Run from the repository root after `scripts/build-reference-envs.sh`:

    .venv-dwsim/bin/python spikes/references/t06_qualify_dwsim.py --out <dir>

Not part of `scripts/check.sh`.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import sys
import time
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

import dwsim_representability as probe
import dwsim_runtime
import t06_fixtures as fx

ENV_DIR = fx.REPO_ROOT / ".venv-dwsim"

# Every change to a §9.3 setting made to get a model accepted or converged, per fixture. Judged on
# self-consistency alone and brought to the design lane (spec §17 M6). Empty = none was needed.
ADJUSTMENTS: dict[str, list[str]] = {}

APPLICATION_NOTES = [
    "Mixer: DWSIM NodeIn, outlet pressure 'Minimum' of the inlets (its default; both at P_r).",
    "Splitter: DWSIM NodeOut, SplitRatios[0] = split fraction to S2 (mass split = molar split "
    "at equal composition).",
    "Heater: CalcMode OutletTemperature, DeltaP 0, energy stream as feed.",
    "Flash: Vessel with OverrideT (isothermal TP flash at the inlet pressure), energy stream as "
    "feed.",
    "Valve: CalcMode OutletPressure (isenthalpic PH flash).",
    "Pump: CalcMode OutletPressure, Eficiencia = 100 * efficiency (percent).",
    "Conversion reactor: RCT_Conversion, conversion reaction in the liquid phase with base "
    "component = key, conversion expression = 100 * X (percent), OperationMode "
    "OutletTemperature, DeltaP 0; rule 2 uses extent = X_key(tool) n_key,in / |nu_key| with "
    "X_key read back from the reactor's ComponentConversions.",
    "Recycle (REF-08): SYN-001 loop torn on S6 by an OT_Recycle block whose outlet is initialized "
    "with t06_fixtures.RECYCLE_TEAR_GUESS; sequential modular.",
]


def compound_flows(ms: Any, phase: int = 0) -> dict[str, float]:
    return {
        c: probe.nullable(ms.Phases[phase].Compounds[probe.compound_name(c)].MolarFlow) or 0.0
        for c in fx.COMPONENTS
    }


def mole_fractions(ms: Any, phase: int) -> dict[str, float | None]:
    return {
        c: probe.nullable(ms.Phases[phase].Compounds[probe.compound_name(c)].MoleFraction)
        for c in fx.COMPONENTS
    }


def stream_record(ms: Any) -> dict[str, Any]:
    """Every quantity of a material stream DWSIM reports that the self-checks may need."""
    p0 = ms.Phases[0].Properties
    return {
        "T_K": float(ms.GetTemperature()),
        "P_Pa": float(ms.GetPressure()),
        "molar_flow_mol_per_s": float(ms.GetMolarFlow()),
        "mass_flow_kg_per_s": probe.nullable(p0.massflow),
        "mass_enthalpy_kJ_per_kg": probe.nullable(p0.enthalpy),
        "vapor_molar_fraction": probe.nullable(ms.Phases[2].Properties.molarfraction),
        "overall_mol_per_s": compound_flows(ms, 0),
        "vapor_mol_per_s": compound_flows(ms, 2),
        "liquid_mol_per_s": compound_flows(ms, 1),
        "vapor_mole_fractions": mole_fractions(ms, 2),
        "liquid_mole_fractions": mole_fractions(ms, 1),
        "calculated": bool(ms.Calculated),
    }


def make_compound(c: str, mapped_latent: bool) -> Any:
    cp = probe.make_compound(
        c, {"Tc": fx.PLACEHOLDER_TC, "Pc": fx.PLACEHOLDER_PC, "omega": fx.PLACEHOLDER_OMEGA}
    )
    cp.HVap_A = fx.dwsim_hvap_j_per_mol(c, mapped_latent) * 1000.0  # J/kmol
    cp.IG_Enthalpy_of_Formation_25C = fx.dwsim_hform_ig_j_per_mol(c) / (fx.MW * 1000.0)  # kJ/kg
    return cp


class Sheet(probe.Sheet):
    """A probe flowsheet with the §9.3 mappings and flash settings applied."""

    def __init__(self, automation: Any, mapped_latent: bool) -> None:  # noqa: D107
        from DWSIM.Interfaces.Enums import FlashSetting

        self.automation = automation
        self.fs = automation.CreateFlowsheet()
        self.compounds = {c: make_compound(c, mapped_latent) for c in fx.COMPONENTS}
        for cp in self.compounds.values():
            self.fs.AvailableCompounds[cp.Name] = cp
            self.fs.AddCompound(cp.Name)
        self.pp = self.fs.CreateAndAddPropertyPackage("Raoult's Law").__implementation__
        self.pp.LiquidDensity_CorrectExpDataForPressure = fx.DWSIM_PP_OPTIONS[
            "LiquidDensity_CorrectExpDataForPressure"
        ]
        for key, value in fx.DWSIM_FLASH_SETTINGS.items():
            self.pp.FlashSettings[getattr(FlashSetting, key)] = value
        self._x = 0
        self.streams: dict[str, Any] = {}
        self.energy: dict[str, Any] = {}

    def feed_from(self, tag: str, feed: dict[str, Any]) -> Any:
        ms = self.feed(tag, feed["flows"], feed["T"], feed["P"])
        self.streams[tag] = ms
        return ms

    def product(self, tag: str) -> Any:
        ms = self.material(tag)
        self.streams[tag] = ms
        return ms

    def energy_stream(self, tag: str) -> Any:
        es = self.add("EnergyStream", tag)
        self.energy[tag] = es
        return es

    def readback(self) -> dict[str, Any]:
        return {
            "flash_algorithm": self.pp.FlashBase.GetType().FullName,
            "flash_settings": {str(kv.Key): str(kv.Value) for kv in self.pp.FlashSettings},
            "LiquidDensity_CorrectExpDataForPressure": bool(
                self.pp.LiquidDensity_CorrectExpDataForPressure
            ),
            "compounds": {
                c: {
                    "HVap_A_J_per_kmol": float(cp.HVap_A),
                    "IG_Enthalpy_of_Formation_25C_kJ_per_kg": float(
                        cp.IG_Enthalpy_of_Formation_25C
                    ),
                    "Critical_Temperature": float(cp.Critical_Temperature),
                    "Critical_Pressure": float(cp.Critical_Pressure),
                    "Acentric_Factor": float(cp.Acentric_Factor),
                    "NBP": float(cp.NBP),
                }
                for c, cp in self.compounds.items()
            },
        }


# A builder returns (units by tag, the rule-2 boundary: inlet tags, outlet tags, energy tags).
Boundary = tuple[list[str], list[str], list[str]]


def build_mixer(sh: Sheet, f: dict[str, Any]) -> tuple[dict[str, Any], Boundary]:
    s1 = sh.feed_from("S1", f["feeds"]["S1"])
    s2 = sh.feed_from("S2", f["feeds"]["S2"])
    s3 = sh.product("S3")
    mx = sh.add("NodeIn", "U-MIX")
    mx.ConnectFeedMaterialStream(s1, 0)
    mx.ConnectFeedMaterialStream(s2, 1)
    mx.ConnectProductMaterialStream(s3, 0)
    return {"U-MIX": mx}, (["S1", "S2"], ["S3"], [])


def build_splitter(sh: Sheet, f: dict[str, Any]) -> tuple[dict[str, Any], Boundary]:
    s1 = sh.feed_from("S1", f["feeds"]["S1"])
    s2 = sh.product("S2")
    s3 = sh.product("S3")
    sp = sh.add("NodeOut", "U-SPLIT")
    sp.ConnectFeedMaterialStream(s1, 0)
    sp.ConnectProductMaterialStream(s2, 0)
    sp.ConnectProductMaterialStream(s3, 1)
    sp.Ratios[0] = f["split_fraction_S2"]
    return {"U-SPLIT": sp}, (["S1"], ["S2", "S3"], [])


def build_heater(sh: Sheet, f: dict[str, Any]) -> tuple[dict[str, Any], Boundary]:
    s1 = sh.feed_from("S1", f["feeds"]["S1"])
    s2 = sh.product("S2")
    ht = build_heater_on(sh, s1, s2, f["outlet_T"])
    return {"U-HEAT": ht}, (["S1"], ["S2"], ["Q-HEAT"])


def build_flash(sh: Sheet, f: dict[str, Any]) -> tuple[dict[str, Any], Boundary]:
    feed = f["feeds"]["S1"]
    if feed["P"] != f["flash_P"]:
        raise ValueError("the flash fixtures have no pressure change: feed P must equal flash P")
    s1 = sh.feed_from("S1", feed)
    s2 = sh.product("S2")  # vapour
    s3 = sh.product("S3")  # liquid
    fl = build_flash_on(sh, s1, s2, s3, f["flash_T"])
    return {"U-FLASH": fl}, (["S1"], ["S2", "S3"], ["Q-FLASH"])


def build_valve(sh: Sheet, f: dict[str, Any]) -> tuple[dict[str, Any], Boundary]:
    from DWSIM.UnitOperations.UnitOperations import Valve

    s1 = sh.feed_from("S1", f["feeds"]["S1"])
    s2 = sh.product("S2")
    vv = sh.add("Valve", "U-VLV")
    vv.ConnectFeedMaterialStream(s1, 0)
    vv.ConnectProductMaterialStream(s2, 0)
    vv.CalcMode = Valve.CalculationMode.OutletPressure
    vv.OutletPressure = f["outlet_P"]
    return {"U-VLV": vv}, (["S1"], ["S2"], [])


def build_pump(sh: Sheet, f: dict[str, Any]) -> tuple[dict[str, Any], Boundary]:
    from DWSIM.UnitOperations.UnitOperations import Pump

    s1 = sh.feed_from("S1", f["feeds"]["S1"])
    s2 = sh.product("S2")
    w = sh.energy_stream("W-PUMP")
    pu = sh.add("Pump", "U-PUMP")
    pu.ConnectFeedMaterialStream(s1, 0)
    pu.ConnectProductMaterialStream(s2, 0)
    pu.ConnectFeedEnergyStream(w, 1)
    pu.CalcMode = Pump.CalculationMode.OutletPressure
    pu.Pout = f["outlet_P"]
    pu.Eficiencia = 100.0 * f["efficiency"]
    return {"U-PUMP": pu}, (["S1"], ["S2"], ["W-PUMP"])


def build_reactor(sh: Sheet, f: dict[str, Any]) -> tuple[dict[str, Any], Boundary]:
    from DWSIM.UnitOperations.Reactors import OperationMode
    from System import Double, String
    from System.Collections.Generic import Dictionary

    if f["phase"] != "liquid":
        raise ValueError("only the liquid-phase reaction of REF-07 is defined")
    stoich = Dictionary[String, Double]()
    for c, nu in f["nu"].items():
        stoich[probe.compound_name(c)] = nu
    rxn = sh.fs.CreateConversionReaction(
        "R1",
        "REF-07",
        stoich,
        probe.compound_name(f["key"]),
        "Liquid",
        repr(100.0 * f["conversion"]),
    )
    sh.fs.AddReaction(rxn)
    sh.fs.AddReactionToSet(rxn.ID, "DefaultSet", True, 0)
    s1 = sh.feed_from("S1", f["feeds"]["S1"])
    s2v = sh.product("S2-V")
    s2l = sh.product("S2-L")
    q = sh.energy_stream("Q-RX")
    rc = sh.add("RCT_Conversion", "U-RX")
    rc.ConnectFeedMaterialStream(s1, 0)
    rc.ConnectProductMaterialStream(s2v, 0)
    rc.ConnectProductMaterialStream(s2l, 1)
    rc.ConnectFeedEnergyStream(q, 1)
    rc.ReactorOperationMode = OperationMode.OutletTemperature
    rc.OutletTemperature = f["outlet_T"]
    rc.DeltaP = 0.0
    return {"U-RX": rc}, (["S1"], ["S2-V", "S2-L"], ["Q-RX"])


def build_recycle(sh: Sheet, f: dict[str, Any]) -> tuple[dict[str, Any], Boundary]:
    import System

    s1 = sh.feed_from("S1", f["feeds"]["S1"])
    s2 = sh.product("S2")
    s3 = sh.product("S3")
    s4 = sh.product("S4")
    s5 = sh.product("S5")
    s6_split = sh.product("S6-split")
    s6 = sh.feed_from("S6", f["tear_guess"])  # the Recycle block's outlet, initialized
    s7 = sh.product("S7")
    mx = sh.add("NodeIn", "U-MIX")
    mx.ConnectFeedMaterialStream(s1, 0)
    mx.ConnectFeedMaterialStream(s6, 1)
    mx.ConnectProductMaterialStream(s2, 0)
    heat = build_heater_on(sh, s2, s3, f["heater_T"])
    flash = build_flash_on(sh, s3, s4, s5, f["flash_T"])
    sp = sh.add("NodeOut", "U-SPLIT")
    sp.ConnectFeedMaterialStream(s5, 0)
    sp.ConnectProductMaterialStream(s6_split, 0)
    sp.ConnectProductMaterialStream(s7, 1)
    sp.Ratios[0] = f["split_fraction_recycle"]
    rec = sh.add("OT_Recycle", "REC")
    rec.ConnectFeedMaterialStream(s6_split, 0)
    rec.ConnectProductMaterialStream(s6, 0)
    conv = rec.ConvergenceParameters
    conv.VazaoMassica = fx.DWSIM_RECYCLE["mass_flow_kg_per_s"]
    conv.Temperatura = fx.DWSIM_RECYCLE["temperature_K"]
    conv.Pressao = fx.DWSIM_RECYCLE["pressure_Pa"]
    rec.MaximumIterations = fx.DWSIM_RECYCLE["maximum_iterations"]
    accel_type = rec.GetType().GetProperty("AccelerationMethod").PropertyType
    rec.AccelerationMethod = System.Enum.Parse(accel_type, fx.DWSIM_RECYCLE["acceleration"])
    units = {"U-MIX": mx, "U-HEAT": heat, "U-FLASH": flash, "U-SPLIT": sp, "REC": rec}
    return units, (["S1"], ["S4", "S7"], ["Q-HEAT", "Q-FLASH"])


def build_heater_on(sh: Sheet, inlet: Any, outlet: Any, t_out: float) -> Any:
    from DWSIM.UnitOperations.UnitOperations import Heater

    q = sh.energy_stream("Q-HEAT")
    ht = sh.add("Heater", "U-HEAT")
    ht.ConnectFeedMaterialStream(inlet, 0)
    ht.ConnectProductMaterialStream(outlet, 0)
    ht.ConnectFeedEnergyStream(q, 1)
    ht.CalcMode = Heater.CalculationMode.OutletTemperature
    ht.OutletTemperature = t_out
    ht.DeltaP = 0.0
    return ht


def build_flash_on(sh: Sheet, inlet: Any, vap: Any, liq: Any, t_flash: float) -> Any:
    q = sh.energy_stream("Q-FLASH")
    fl = sh.add("Vessel", "U-FLASH")
    fl.ConnectFeedMaterialStream(inlet, 0)
    fl.ConnectProductMaterialStream(vap, 0)
    fl.ConnectProductMaterialStream(liq, 1)
    fl.ConnectFeedEnergyStream(q, 6)
    fl.OverrideT = True
    fl.FlashTemperature = t_flash
    return fl


BUILDERS: dict[str, Callable[[Sheet, dict[str, Any]], tuple[dict[str, Any], Boundary]]] = {
    "mixer": build_mixer,
    "splitter": build_splitter,
    "heater": build_heater,
    "flash": build_flash,
    "valve": build_valve,
    "pump": build_pump,
    "conversion_reactor": build_reactor,
    "recycle": build_recycle,
}


def unit_record(tag: str, u: Any) -> dict[str, Any]:
    out: dict[str, Any] = {
        "class": u.GetType().FullName,
        "calculated": bool(u.Calculated),
        "error_message": str(u.ErrorMessage) if u.ErrorMessage else "",
    }
    for name in ("DeltaQ", "DeltaP", "DeltaT", "OutletTemperature", "FlashTemperature"):
        prop = u.GetType().GetProperty(name)
        if prop is not None:
            try:
                out[name] = probe.nullable(getattr(u, name))
            except Exception as exc:  # recorded, not hidden
                out[name] = f"unreadable: {type(exc).__name__}"
    if tag == "U-RX":
        out["ComponentConversions"] = {str(k.Key): float(k.Value) for k in u.ComponentConversions}
    if tag == "REC":
        conv = u.ConvergenceParameters
        out.update(
            {
                "Converged": bool(u.Converged),
                "IterationsTaken": int(u.IterationsTaken),
                "MaximumIterations": int(u.MaximumIterations),
                "AccelerationMethod": str(u.AccelerationMethod),
                "LegacyMode": bool(u.LegacyMode),
                "tolerances_used": {
                    "mass_flow_kg_per_s": float(conv.VazaoMassica),
                    "temperature_K": float(conv.Temperatura),
                    "pressure_Pa": float(conv.Pressao),
                },
            }
        )
    return out


def energy_balance_w(
    streams: dict[str, dict[str, Any]],
    energy: dict[str, float | None],
    b: Boundary,
    reaction_w: float = 0.0,
) -> dict[str, Any]:
    """DWSIM's own boundary energy balance, in W.

    ``Σ ṁh(in) + Σ E(energy streams) - Σ ṁh(out) - ξ Σ_i ν_i ΔH_f,ig,i``. DWSIM's stream
    enthalpies carry no formation term (datum: ideal gas at 298.15 K), so a reactor's balance
    needs the heat of reaction from the formation enthalpies DWSIM holds (``reaction_w``).
    """

    def mh(tag: str) -> float:
        s = streams[tag]
        return float(s["mass_flow_kg_per_s"]) * float(s["mass_enthalpy_kJ_per_kg"]) * 1000.0

    inlets, outlets, es = b
    e_in = sum(float(energy[t] or 0.0) * 1000.0 for t in es)
    residual = sum(mh(t) for t in inlets) + e_in - sum(mh(t) for t in outlets) - reaction_w
    scale = max([abs(mh(t)) for t in inlets + outlets] + [abs(e_in), abs(reaction_w), 1.0])
    return {
        "residual_W": residual,
        "relative_to_largest_term": residual / scale,
        "energy_streams_counted_as_inlets_W": {t: float(energy[t] or 0.0) * 1000.0 for t in es},
        "reaction_term_W": reaction_w,
    }


def equilibrium_residuals(sh: Sheet, units: dict[str, Any]) -> dict[str, Any]:
    """max_i |y_i P - x_i Psat_i(T)| / P on DWSIM's own two-phase results, with its own Psat."""
    out: dict[str, Any] = {}

    def resid(ms: Any, y: dict[str, float | None], x: dict[str, float | None]) -> float:
        t, p = float(ms.GetTemperature()), float(ms.GetPressure())
        sh.pp.CurrentMaterialStream = ms
        return max(
            abs(
                float(y[c] or 0.0) * p
                - float(x[c] or 0.0) * float(sh.pp.AUX_PVAPi(probe.compound_name(c), t))
            )
            / p
            for c in fx.COMPONENTS
        )

    if "U-FLASH" in units:
        vap, liq = (
            sh.streams["S4" if "S4" in sh.streams else "S2"],
            sh.streams["S5" if "S5" in sh.streams else "S3"],
        )
        if float(vap.GetMolarFlow()) > 0 and float(liq.GetMolarFlow()) > 0:
            out["flash_vapour_vs_liquid_outlet"] = resid(
                vap, mole_fractions(vap, 0), mole_fractions(liq, 0)
            )
    for tag, ms in sh.streams.items():
        vf = probe.nullable(ms.Phases[2].Properties.molarfraction)
        if vf is not None and 0.0 < vf < 1.0:
            out[f"{tag}_internal_phases"] = resid(ms, mole_fractions(ms, 2), mole_fractions(ms, 1))
    return out


def run_fixture(automation: Any, fid: str, f: dict[str, Any]) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "fixture": fid,
        "definition": f,
        "adjustments": ADJUSTMENTS.get(fid, []),
        "accepted": False,
        "converged": False,
        "stage_reached": "build",
    }
    t0 = time.perf_counter()
    try:
        sh = Sheet(automation, mapped_latent=not f.get("dwsim_unmapped_latent", False))
        units, boundary = BUILDERS[f["unit"]](sh, f)
        rec["settings_readback"] = sh.readback()
        rec["accepted"] = True
        rec["stage_reached"] = "calculate"
        t1 = time.perf_counter()
        errors = automation.CalculateFlowsheet4(sh.fs)
        rec["wall_time_calculate_s"] = time.perf_counter() - t1
        messages = [str(e.Message) for e in errors] if errors is not None else []
        rec["solver_errors"] = messages
        calculated = {
            str(o.GraphicObject.Tag): bool(o.Calculated) for o in sh.fs.SimulationObjects.Values
        }
        rec["calculated"] = calculated
        streams = {t: stream_record(ms) for t, ms in sh.streams.items()}
        energy = {t: probe.nullable(es.EnergyFlow) for t, es in sh.energy.items()}
        unit_out = {t: unit_record(t, u) for t, u in units.items()}
        rec["raw_output"] = {"streams": streams, "energy_streams_kW": energy, "units": unit_out}
        converged = not messages and all(calculated.values())
        if "REC" in unit_out:
            r = unit_out["REC"]
            converged = (
                converged and r["Converged"] and r["IterationsTaken"] < r["MaximumIterations"]
            )
        rec["converged"] = bool(converged)
        rec["stage_reached"] = "calculated"

        inlets, outlets, _ = boundary
        generation = None
        reaction_w = 0.0
        if f["unit"] == "conversion_reactor":
            key = f["key"]
            x_key = unit_out["U-RX"]["ComponentConversions"][probe.compound_name(key)]
            xi = x_key * streams["S1"]["overall_mol_per_s"][key] / abs(f["nu"][key])
            generation = {c: f["nu"][c] * xi for c in fx.COMPONENTS}
            hform = rec["settings_readback"]["compounds"]
            reaction_w = xi * sum(
                f["nu"][c] * hform[c]["IG_Enthalpy_of_Formation_25C_kJ_per_kg"] * fx.MW * 1000.0
                for c in fx.COMPONENTS
            )
        rule2 = fx.component_balance(
            [streams[t]["overall_mol_per_s"] for t in inlets],
            [streams[t]["overall_mol_per_s"] for t in outlets],
            generation,
        )
        if generation is not None:
            rule2["extent_used_mol_per_s"] = generation[f["key"]] / f["nu"][f["key"]]
        rec["self_check"] = {
            "rule2_component_balance": rule2,
            "energy_balance": energy_balance_w(streams, energy, boundary, reaction_w),
            "phase_equilibrium_relative": equilibrium_residuals(sh, units),
        }
        # Spec §9.2's compared quantities, from the raw output alone (names: t06_fixtures.COMPARED).
        rec["compared_quantities"] = fx.dwsim_compared_quantities(fid, rec["raw_output"])
    except Exception as exc:  # every failure is recorded, none is hidden
        rec["error"] = f"{type(exc).__name__}: {exc}"
        rec["traceback"] = traceback.format_exc(limit=6)
    finally:
        rec["wall_time_total_s"] = time.perf_counter() - t0
    return rec


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True, help="directory for the JSON records")
    parser.add_argument("--only", nargs="*", help="fixture ids (default: all)")
    args = parser.parse_args()
    out_dir = args.out.resolve()  # absolute: dwsim_runtime.start changes the working directory
    out_dir.mkdir(parents=True, exist_ok=True)
    env_dir = ENV_DIR.resolve()

    fingerprint = fx.fingerprint("dwsim", env_dir)
    t_start = time.perf_counter()
    automation = dwsim_runtime.start(env_dir)
    t_start = time.perf_counter() - t_start
    import System

    common = {
        "tool": "DWSIM",
        "versions": {
            "dwsim": str(automation.GetVersion()),
            "pythonnet": importlib.metadata.version("pythonnet"),
            "dotnet_runtime": str(System.Environment.Version),
            "python": sys.version.split()[0],
        },
        "environment_fingerprint": fingerprint,
        "settings": {
            "flash_settings": fx.DWSIM_FLASH_SETTINGS,
            "recycle": fx.DWSIM_RECYCLE,
            "property_package": "Raoult's Law",
            "property_package_options": fx.DWSIM_PP_OPTIONS,
            "placeholders": {
                "T_c_K": fx.PLACEHOLDER_TC,
                "P_c_Pa": fx.PLACEHOLDER_PC,
                "omega": fx.PLACEHOLDER_OMEGA,
                "NBP": "T_b,i",
            },
        },
        "application_notes": APPLICATION_NOTES,
        "wall_time_runtime_start_s": t_start,
    }
    status = 0
    for fid in args.only or list(fx.FIXTURES):
        if fid in fx.NOT_APPLICABLE["DWSIM"]:
            rec = {"fixture": fid, "not_applicable": fx.NOT_APPLICABLE["DWSIM"][fid]}
        else:
            rec = run_fixture(automation, fid, fx.FIXTURES[fid])
            rule2 = rec.get("self_check", {}).get("rule2_component_balance", {})
            ok = rec["accepted"] and rec["converged"] and rule2.get("passes") and "error" not in rec
            status |= 0 if ok else 1
        rec = {**common, **rec}
        path = out_dir / f"dwsim-{fid}.json"
        path.write_text(json.dumps(fx.finite(rec), indent=1) + "\n", encoding="utf-8")
        print(
            f"dwsim {fid}: accepted={rec.get('accepted')} converged={rec.get('converged')} "
            f"rule2={rec.get('self_check', {}).get('rule2_component_balance', {}).get('passes')}"
            + (f" ERROR {rec['error']}" if "error" in rec else ""),
            file=sys.stderr,
        )
    return status


if __name__ == "__main__":
    sys.exit(main())
