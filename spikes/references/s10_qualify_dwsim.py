"""S10 WO-S10-5: the DWSIM 9.0.5 qualification of `wilson-ig-v1` (spec §8.2, §15 A2-3).

Authority: `docs/derivations/S10-spec.md` §8.2. Through `Automation3`, headless (T06's route),
this script builds, per I-state, a DWSIM flowsheet with the `WilsonPropertyPackage` on three user
compounds carrying the S10 real records, with §8.2's mapping:

* P^sat by DWSIM eq. 101 with A' = a - c ln 1000, B' = 1000 b, C' = c, D' = d 1e-6, E' = 2;
* the ideal-gas c_p polynomial (eq. 100, J/(kmol K)), coefficient k = 1000 R b_k / 1000^k;
* Delta H_vap as eq. 100, Delta h(T) = -1000 R b + R c T + 2 R d T^3 / 1e6, in J/kmol (fixed by
  readback); the liquid-c_p equation set only for AUX_HVAPi (T06 quirk 4);
* the liquid-density pressure correction off (T06 quirk 6);
* Wilson per state: DWSIM's Lambda_ij = V_j / V_i exp(-A_ij / (1.9872 T)) (`WilsonModel.vb` at
  v9.0.5), so A_ij = -1.9872 T ln(Lambda_ij V_i / V_j) with DWSIM's own V (`GetArguments`);

and the settings `inputs.json` lists for what §8.2 does not name (liquid density, Poynting
factor, enthalpy mode, flash type, fail-safe; S10_DECISIONS B-50, B-52).

Then, per state:

1. **Readbacks, before any flash**: DWSIM's GetArguments (CAS ids, volumes), the BIPs as
   `WilsonModel.GetBIPs` returns them, and at the state's (T, P), for x = z and the two RB
   compositions: gamma (`CalcActivityCoefficients`, the routine `DW_CalcFugCoeff` calls), the
   liquid and vapour fugacity coefficients, the phase enthalpies (`DW_CalcEnthalpy` +
   `AUX_HFm25`); per component AUX_PVAPi, AUX_HVAPi, AUX_CPi, AUX_INT_CPDTi(298.15 K, T),
   AUX_LIQDENSi.
2. **The ladder** (spec §8.2): PTFlash external = internal loop tolerance in (1e-10, 1e-8); for
   each rung a fresh flowsheet, the stream at the registered (n, T, P) calculated by
   CalculateFlowsheet4, and the property package's flash called directly with the same inputs.
   Every attempt is recorded.

Inputs: `benchmarks/s10/dwsim/inputs.json` only (written by `scripts/s10_dwsim_comparison.py
--write-inputs`). No expected value is read, and nothing of `openflowsheet` is imported. The
comparison is `scripts/s10_dwsim_comparison.py`'s. Output:
`benchmarks/s10/dwsim/qualification.json`.

    .venv-dwsim/bin/python spikes/references/s10_qualify_dwsim.py [--out FILE]

Not part of `scripts/check.sh`: the gate never runs a tool.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import dwsim_runtime
import t06_fixtures as fx  # REPO_ROOT, the environment fingerprint, finite()

ENV_DIR = fx.REPO_ROOT / ".venv-dwsim"
INPUTS = fx.REPO_ROOT / "benchmarks" / "s10" / "dwsim" / "inputs.json"
DEFAULT_OUT = fx.REPO_ROOT / "benchmarks" / "s10" / "dwsim" / "qualification.json"


def cas(cid: str) -> str:
    return f"s10-{cid.lower()}"


def make_compound(c: dict[str, Any], k: int, rec: dict[str, Any], st: dict[str, Any]) -> Any:
    from DWSIM.Thermodynamics.BaseClasses import ConstantProperties

    r = rec["R_J_per_mol_K"]
    ph = st["placeholders"]
    a, b, cc, d = c["vapour_pressure_abcd"]
    bk = c["ideal_gas_cp_b"]
    mw = c["molecular_weight_kg_per_mol"] * 1000.0  # kg/kmol
    cp = ConstantProperties()
    cp.Name = f"S10-{c['id']}"
    cp.ID = 910_000 + k
    cp.Formula = c["id"]
    cp.CAS_Number = cas(c["id"])
    cp.OriginalDB = "User"
    cp.CurrentDB = "User"
    cp.Molar_Weight = mw
    cp.Normal_Boiling_Point = ph["NBP_K"]
    cp.NBP = ph["NBP_K"]
    cp.Critical_Temperature = ph["T_c_K"]
    cp.Critical_Pressure = ph["P_c_Pa"]
    cp.Acentric_Factor = ph["omega"]
    cp.IsHYPO = False
    cp.IsPF = False

    cp.VaporPressureEquation = "101"
    cp.Vapor_Pressure_Constant_A = a - cc * math.log(1000.0)
    cp.Vapor_Pressure_Constant_B = 1000.0 * b
    cp.Vapor_Pressure_Constant_C = cc
    cp.Vapor_Pressure_Constant_D = d * 1.0e-6
    cp.Vapor_Pressure_Constant_E = 2.0

    cp.IdealgasCpEquation = "100"
    cp.Ideal_Gas_Heat_Capacity_Const_A = 1000.0 * r * bk[0]
    cp.Ideal_Gas_Heat_Capacity_Const_B = 1000.0 * r * bk[1] / 1.0e3
    cp.Ideal_Gas_Heat_Capacity_Const_C = 1000.0 * r * bk[2] / 1.0e6
    cp.Ideal_Gas_Heat_Capacity_Const_D = 1000.0 * r * bk[3] / 1.0e9
    cp.Ideal_Gas_Heat_Capacity_Const_E = 1000.0 * r * bk[4] / 1.0e12

    cp.LiquidHeatCapacityEquation = "1"  # quirk 4 only; unused by the Ideal enthalpy mode
    cp.Liquid_Heat_Capacity_Const_A = 1000.0 * r * bk[0]

    cp.VaporizationEnthalpyEquation = "100"  # J/kmol
    cp.HVap_A = -1000.0 * r * b * 1000.0
    cp.HVap_B = r * cc * 1000.0
    cp.HVap_C = 0.0
    cp.HVap_D = 2.0 * r * d * 1.0e-6 * 1000.0
    cp.HVap_E = 0.0

    cp.LiquidDensityEquation = st["liquid_density"]["equation"]
    cp.Liquid_Density_Const_A = st["liquid_density"]["value_kg_per_m3"]

    cp.IG_Enthalpy_of_Formation_25C = c["standard_formation_enthalpy_J_per_mol"] / mw  # kJ/kg
    cp.IG_Gibbs_Energy_of_Formation_25C = 0.0
    return cp


def compound_record(cp: Any) -> dict[str, Any]:
    fields = (
        "Molar_Weight",
        "Critical_Temperature",
        "Critical_Pressure",
        "Acentric_Factor",
        "NBP",
        "Vapor_Pressure_Constant_A",
        "Vapor_Pressure_Constant_B",
        "Vapor_Pressure_Constant_C",
        "Vapor_Pressure_Constant_D",
        "Vapor_Pressure_Constant_E",
        "Ideal_Gas_Heat_Capacity_Const_A",
        "Ideal_Gas_Heat_Capacity_Const_B",
        "Ideal_Gas_Heat_Capacity_Const_C",
        "Ideal_Gas_Heat_Capacity_Const_D",
        "Ideal_Gas_Heat_Capacity_Const_E",
        "HVap_A",
        "HVap_B",
        "HVap_C",
        "HVap_D",
        "HVap_E",
        "Liquid_Heat_Capacity_Const_A",
        "Liquid_Density_Const_A",
        "IG_Enthalpy_of_Formation_25C",
    )
    out: dict[str, Any] = {f: float(getattr(cp, f)) for f in fields}
    for f in (
        "CAS_Number",
        "OriginalDB",
        "VaporPressureEquation",
        "IdealgasCpEquation",
        "VaporizationEnthalpyEquation",
        "LiquidHeatCapacityEquation",
        "LiquidDensityEquation",
    ):
        out[f] = str(getattr(cp, f))
    return out


class Sheet:
    """One flowsheet: the three compounds, the Wilson package with the inputs' settings, and the
    stream at the state; the BIPs are applied from DWSIM's own volumes."""

    def __init__(self, automation: Any, inp: dict[str, Any], state: dict[str, Any]) -> None:
        from DWSIM.Interfaces.Enums import FlashSetting
        from DWSIM.Interfaces.Enums.GraphicObjects import ObjectType

        rec, st = inp["records"], inp["settings"]
        self.automation = automation
        self.comps = rec["components"]
        self.fs = automation.CreateFlowsheet()
        self.cps = [make_compound(c, k, rec, st) for k, c in enumerate(self.comps)]
        for cp in self.cps:
            self.fs.AvailableCompounds[cp.Name] = cp
            self.fs.AddCompound(cp.Name)
        pp = self.fs.CreateAndAddPropertyPackage(st["property_package"]).__implementation__
        opts = st["property_package_options"]
        # Before any stream exists: with it on, setting a stream runs DWSIM's UNIFAC estimation
        # of "missing" pairs (RunPostMaterialStreamSetRoutine), which needs Ipopt.
        pp.AutoEstimateMissingNRTLUNIQUACParameters = opts[
            "AutoEstimateMissingNRTLUNIQUACParameters"
        ]
        pp.LiquidDensity_CorrectExpDataForPressure = opts["LiquidDensity_CorrectExpDataForPressure"]
        pp.LiquidFugacity_UsePoyntingCorrectionFactor = opts[
            "LiquidFugacity_UsePoyntingCorrectionFactor"
        ]
        pp.EnthalpyEntropyCpCvCalculationMode = getattr(
            type(pp.EnthalpyEntropyCpCvCalculationMode), opts["EnthalpyEntropyCpCvCalculationMode"]
        )
        pp.VaporPhaseFugacityCalculationMode = getattr(
            type(pp.VaporPhaseFugacityCalculationMode), opts["VaporPhaseFugacityCalculationMode"]
        )
        for key, value in st["flash"]["flash_settings_fixed"].items():
            pp.FlashSettings[getattr(FlashSetting, key)] = value
        self.pp = pp
        self.state = state
        ms = self.fs.AddObject(ObjectType.MaterialStream, 50, 50, "FEED").__implementation__
        ms.SetTemperature(state["T"])
        ms.SetPressure(state["P"])
        ms.SetMolarFlow(sum(state["n"]))
        for cp, ni in zip(self.cps, state["n"], strict=True):
            ms.SetOverallCompoundMolarFlow(cp.Name, ni)
        self.ms = ms
        pp.CurrentMaterialStream = ms
        self.applied = self.apply_bips(inp)

    def apply_bips(self, inp: dict[str, Any]) -> list[list[float]]:
        from System import Array, Double, String
        from System.Collections.Generic import Dictionary

        r = inp["settings"]["wilson"]["R_cal_per_mol_K"]
        t = self.state["T"]
        ids = [c["id"] for c in self.comps]
        lam = {(e["i"], e["j"]): e["value"] for e in inp["records"]["wilson_lambda"]}
        v = [float(x) for x in self.pp.GetArguments()[1]]
        a = [[0.0] * 3 for _ in range(3)]
        for i in range(3):
            for j in range(3):
                if i != j:
                    a[i][j] = -r * t * math.log(lam[(ids[i], ids[j])] * v[i] / v[j])
        bips = self.pp.WilsonM.BIPs
        for i in range(3):
            inner = Dictionary[String, Array[Double]]()
            for j in range(i + 1, 3):
                inner[cas(ids[j])] = Array[Double]([a[i][j], a[j][i]])
            if inner.Count:
                bips[cas(ids[i])] = inner
        return a

    def settings_readback(self) -> dict[str, Any]:
        pp = self.pp
        return {
            "property_package": str(pp.ComponentName),
            "flash_algorithm": pp.FlashBase.GetType().FullName,
            "flash_settings": {str(kv.Key): str(kv.Value) for kv in pp.FlashSettings},
            "options": {
                k: str(getattr(pp, k))
                for k in (
                    "LiquidDensity_CorrectExpDataForPressure",
                    "LiquidFugacity_UsePoyntingCorrectionFactor",
                    "EnthalpyEntropyCpCvCalculationMode",
                    "VaporPhaseFugacityCalculationMode",
                    "AutoEstimateMissingNRTLUNIQUACParameters",
                    "ActivityCoefficientModels_IgnoreMissingInteractionParameters",
                    "UseHenryConstants",
                    "LiquidDensityCalculationMode_Subcritical",
                )
            },
            "compounds": {
                c["id"]: compound_record(cp) for c, cp in zip(self.comps, self.cps, strict=True)
            },
            "RET_VNAMES": [str(s) for s in pp.RET_VNAMES()],
        }

    def point(self, x: list[float]) -> dict[str, Any]:
        from DWSIM.Thermodynamics.PropertyPackages import State
        from System import Array, Double

        pp, t, p = self.pp, self.state["T"], self.state["P"]
        vx = Array[Double](x)
        gamma = pp.WilsonM.CalcActivityCoefficients(t, vx, pp.GetArguments())
        mmm = float(pp.AUX_MMM(vx))
        hf = float(pp.AUX_HFm25(vx))
        hl = float(pp.DW_CalcEnthalpy(vx, t, p, State.Liquid))
        hv = float(pp.DW_CalcEnthalpy(vx, t, p, State.Vapor))
        return {
            "x": x,
            "gamma": [float(g) for g in gamma],
            "phi_L": [float(f) for f in pp.DW_CalcFugCoeff(vx, t, p, State.Liquid)],
            "phi_V": [float(f) for f in pp.DW_CalcFugCoeff(vx, t, p, State.Vapor)],
            "AUX_MMM_kg_per_kmol": mmm,
            "AUX_HFm25_kJ_per_kg": hf,
            "DW_CalcEnthalpy_L_kJ_per_kg": hl,
            "DW_CalcEnthalpy_V_kJ_per_kg": hv,
            "AUX_LIQDENS_kg_per_m3": float(pp.AUX_LIQDENS(t, vx, p)),
            "h_L_J_per_mol": (hl + hf) * mmm,
            "h_V_J_per_mol": (hv + hf) * mmm,
        }

    def readback(self, xs: list[list[float]]) -> dict[str, Any]:
        pp, t = self.pp, self.state["T"]
        args = pp.GetArguments()
        ids = [str(s) for s in args[0]]
        pure = {}
        for k, (c, cp) in enumerate(zip(self.comps, self.cps, strict=True)):
            pure[c["id"]] = {
                "AUX_PVAPi_Pa": float(pp.AUX_PVAPi(cp.Name, t)),
                "AUX_HVAPi_kJ_per_kg": float(pp.AUX_HVAPi(cp.Name, t)),
                "AUX_CPi_kJ_per_kg_K": float(pp.AUX_CPi(cp.Name, t)),
                "AUX_INT_CPDTi_298_15_kJ_per_kg": float(pp.AUX_INT_CPDTi(298.15, t, cp.Name)),
                "AUX_LIQDENSi_kg_per_m3": float(pp.AUX_LIQDENSi(k, t)),
                "IG_Enthalpy_of_Formation_25C": float(cp.IG_Enthalpy_of_Formation_25C),
            }
        return {
            "cas_ids": ids,
            "molar_volumes_m3_per_kmol": [float(v) for v in args[1]],
            "bips_cal_per_mol": [[float(pp.WilsonM.GetBIPs(i, j)) for j in ids] for i in ids],
            "pure": pure,
            "points": [self.point(x) for x in xs],
        }

    def flash(self) -> dict[str, Any]:
        """The stream's TP flash by DWSIM's solver, then the package's flash called directly."""
        from System import Array, Double

        out: dict[str, Any] = {}
        errors = self.automation.CalculateFlowsheet4(self.fs)
        out["solver_errors"] = [str(e.Message) for e in errors] if errors is not None else []
        out["stream_calculated"] = bool(self.ms.Calculated)
        ms, pp = self.ms, self.pp
        # The solver leaves the package without a current stream; the readback routines need one.
        pp.CurrentMaterialStream = ms
        out["exception"] = None
        try:
            z = [v / sum(self.state["n"]) for v in self.state["n"]]
            r = pp.FlashBase.Flash_PT(Array[Double](z), self.state["P"], self.state["T"], pp)
            out["direct_flash"] = {
                "L": float(r[0]),
                "V": float(r[1]),
                "x": [float(v) for v in r[2]],
                "y": [float(v) for v in r[3]],
                "ecount": int(r[4]),
                "K": [float(v) for v in r[9]],
            }
        except Exception as exc:  # noqa: BLE001  (the record keeps DWSIM's message)
            out["exception"] = f"{type(exc).__name__}: {exc}"
            out["direct_flash"] = None
        out["converged"] = (
            out["exception"] is None and not out["solver_errors"] and out["stream_calculated"]
        )
        if not out["stream_calculated"]:
            return out

        def comp(phase: int) -> list[float | None]:
            return [
                None
                if (v := ms.Phases[phase].Compounds[cp.Name].MoleFraction) is None
                else float(v)
                for cp in self.cps
            ]

        from DWSIM.Thermodynamics.PropertyPackages import State

        t, p = self.state["T"], self.state["P"]
        x, y = comp(1), comp(2)
        vf, lf = ms.Phases[2].Properties.molarfraction, ms.Phases[1].Properties.molarfraction
        q: dict[str, Any] = {
            "vapor_molarfraction": None if vf is None else float(vf),
            "liquid_molarfraction": None if lf is None else float(lf),
            "x": x,
            "y": y,
            "stream_molar_enthalpy_kJ_per_kmol": {
                name: None if (h := ms.Phases[i].Properties.molar_enthalpy) is None else float(h)
                for name, i in (("mixture", 0), ("liquid", 1), ("vapor", 2))
            },
        }
        for name, comp_, stt in (("h_L", x, State.Liquid), ("h_V", y, State.Vapor)):
            if any(v is None for v in comp_):
                q[f"{name}_J_per_mol"] = None
                continue
            vx = Array[Double]([float(v) for v in comp_])  # type: ignore[arg-type]
            mmm, hf = float(pp.AUX_MMM(vx)), float(pp.AUX_HFm25(vx))
            h = float(pp.DW_CalcEnthalpy(vx, t, p, stt))
            q[f"{name}_DW_CalcEnthalpy_kJ_per_kg"] = h
            q[f"{name}_AUX_HFm25_kJ_per_kg"] = hf
            q[f"{name}_AUX_MMM_kg_per_kmol"] = mmm
            q[f"{name}_J_per_mol"] = (h + hf) * mmm
        out["quantities"] = q
        return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--inputs", type=Path, default=INPUTS, help="for harness smoke tests only")
    args = parser.parse_args()
    inputs_path = args.inputs.resolve()
    out_path = args.out.resolve()  # absolute: dwsim_runtime.start changes the working directory
    env_dir = ENV_DIR.resolve()
    inp = json.loads(inputs_path.read_text(encoding="utf-8"))

    fingerprint = fx.fingerprint("dwsim", env_dir)
    t0 = time.perf_counter()
    automation = dwsim_runtime.start(env_dir)
    t_runtime = time.perf_counter() - t0
    import System

    doc: dict[str, Any] = {
        "tool": "DWSIM",
        "authority": inp["authority"],
        "written_by": "spikes/references/s10_qualify_dwsim.py",
        "inputs_sha256": fx.file_sha256(inputs_path),
        "inputs_echo": inp["records"],
        "versions": {
            "dwsim": str(automation.GetVersion()),
            "pythonnet": importlib.metadata.version("pythonnet"),
            "dotnet_runtime": str(System.Environment.Version),
            "python": sys.version.split()[0],
        },
        "environment_fingerprint": fingerprint,
        "settings": inp["settings"],
        "ladder_settings": inp["ladder"],
        "wall_time_runtime_start_s": t_runtime,
        "states": {},
        "attempts": [],
    }
    status = 0
    xs_fixed = inp["readback_compositions"]["x"]
    for sid, state in inp["i_states"]["states"].items():
        z = [v / sum(state["n"]) for v in state["n"]]
        t1 = time.perf_counter()
        try:
            sh = Sheet(automation, inp, state)
            if "settings_readback" not in doc:
                doc["settings_readback"] = sh.settings_readback()
            doc["states"][sid] = {
                "state": state,
                "applied_bips_cal_per_mol": sh.applied,
                "readback": sh.readback([z, *xs_fixed]),
                "wall_time_s": time.perf_counter() - t1,
            }
        except Exception as exc:  # noqa: BLE001
            doc["states"][sid] = {
                "state": state,
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
            }
            status = 1
            continue
        for tol in inp["ladder"]["tolerances"]:
            t1 = time.perf_counter()
            rec: dict[str, Any] = {"state": sid, "tolerance": tol}
            try:
                sh = Sheet(automation, inp, state)
                from DWSIM.Interfaces.Enums import FlashSetting

                for key in inp["ladder"]["settings_per_rung"]:
                    sh.pp.FlashSettings[getattr(FlashSetting, key)] = f"{tol:.0E}"
                rec["flash_settings_readback"] = {
                    str(kv.Key): str(kv.Value) for kv in sh.pp.FlashSettings
                }
                rec.update(sh.flash())
            except Exception as exc:  # noqa: BLE001
                rec.update(
                    {
                        "converged": False,
                        "exception": f"{type(exc).__name__}: {exc}",
                        "traceback": traceback.format_exc(),
                    }
                )
            rec["wall_time_s"] = time.perf_counter() - t1
            doc["attempts"].append(rec)
            print(
                f"{sid} tol={tol:g}: converged={rec.get('converged')} "
                f"vf={rec.get('quantities', {}).get('vapor_molarfraction')}",
                file=sys.stderr,
            )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(fx.finite(doc), indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    return status


if __name__ == "__main__":
    sys.exit(main())
