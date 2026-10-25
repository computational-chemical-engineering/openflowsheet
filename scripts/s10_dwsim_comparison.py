"""S10 WO-S10-5: the DWSIM reference comparison, recomputed from the committed records alone.

Authority: `docs/derivations/S10-spec.md` §8.2 (the DWSIM mapping, the gamma readback to 1e-9
relative before any flash, the flash-tolerance ladder (1e-10, 1e-8), §8.1's comparison tolerances,
and the pre-registered outcome), with §15 A2-3's I-states. Two documents, both under
`benchmarks/s10/dwsim/`:

* `inputs.json` (`--write-inputs`): the only input of the tool script
  `spikes/references/s10_qualify_dwsim.py`, which runs in the DWSIM environment (no YAML reader,
  no `openflowsheet`). It carries the record values of `benchmarks/s10/records.yaml` verbatim,
  the I-state definitions (`n`, `T`, `P` only) of `reference_values_real.yaml`, the readback
  compositions, the DWSIM settings and the ladder. No expected value of any kind is written to it.
* `comparison.json` (`--write`): from the tool's `qualification.json`, the generator's real
  section and the generator's closed forms (`docs/derivations/scripts/s10_reference.py`, 50
  digits): the Wilson mapping check, the readback table (the gamma gate of §8.2 and the
  informative pure-component and enthalpy rows), the ladder, and A45's per-state table. It is
  mechanical: no tolerance, setting, mapping or state is chosen here, and the verdict per state is
  the `verdict` agent's.

    python scripts/s10_dwsim_comparison.py --write-inputs | --write | --check

`--check` recomputes both documents and compares them byte for byte with the committed files.
The gate never runs a tool.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml
from mpmath import mp, mpf  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parents[1]
S10 = ROOT / "benchmarks" / "s10"
OUT = S10 / "dwsim"
INPUTS = OUT / "inputs.json"
QUALIFICATION = OUT / "qualification.json"
COMPARISON = OUT / "comparison.json"
RECORDS = S10 / "records.yaml"
REAL = S10 / "reference_values_real.yaml"
GENERATOR = ROOT / "docs" / "derivations" / "scripts" / "s10_reference.py"

IDS = ("CH3OH", "C2H5OH", "H2O")
#: §8.2: "The readback of gamma at the state's (T, x) must match ours to 1e-9 relative before the
#: flash." x: the state's feed z and §8.1's two RB compositions (B-51), order (CH3OH, C2H5OH, H2O).
READBACK_X = ((0.2, 0.3, 0.5), (0.6, 0.2, 0.2))
GAMMA_RELATIVE = 1e-9
#: DWSIM 9.0.5 `WilsonModel.vb`, `CalcActivityCoefficients`: Lambda_ij = V_j / V_i *
#: exp(-A_ij / (1.9872 T)), A_ij in cal/mol, V from `WilsonPropertyPackage.GetArguments`
#: (MW / rho_L(298.15 K)). Read from the source at tag v9.0.5; the gamma readback confirms it.
DWSIM_WILSON_R = 1.9872
#: §8.2's mapping and the settings the model needs that §8.2 does not name (B-50, ESC-50).
SETTINGS = {
    "property_package": "Wilson",
    "compounds": "user compounds (OriginalDB = CurrentDB = 'User'), CAS 's10-<id>' so that "
    "DWSIM's embedded wilson_bips.csv supplies nothing; Molar_Weight = records.yaml "
    "molecular_weight in kg/kmol",
    "vapour_pressure": "VaporPressureEquation '101' (exp(A + B/T + C ln T + D T^E), Pa) with "
    "A = a - c ln 1000, B = 1000 b, C = c, D = d 1e-6, E = 2 (spec 8.2)",
    "ideal_gas_cp": "IdealgasCpEquation '100' (A + B T + C T^2 + D T^3 + E T^4, J/(kmol K)) with "
    "coefficient k = 1000 R b_k / 1000^k (spec 8.2: the ideal-gas c_p polynomial)",
    "vaporization_enthalpy": "VaporizationEnthalpyEquation '100' (J/kmol) with A = -1000 R b "
    "1000, B = R c 1000, C = 0, D = 2 R d 1e-6 1000, E = 0: Delta h(T) = -1000 R b + R c T + "
    "2 R d T^3 / 1e6 (spec 8.2, eq. 100; the J/kmol unit is fixed by readback)",
    "liquid_heat_capacity": "LiquidHeatCapacityEquation '1', constant 1000 R b_0 J/(kmol K): "
    "unused by the Ideal enthalpy mode, set only because AUX_HVAPi reads the vaporization "
    "equation only when this field is not '0' (docs/reference-environments.md section 6 quirk 4)",
    "ideal_gas_formation_enthalpy": "IG_Enthalpy_of_Formation_25C = Delta_fH / MW (kJ/kg); "
    "DWSIM's stream enthalpies carry no formation term, so the tool adds DWSIM's own "
    "AUX_HFm25 to DW_CalcEnthalpy",
    "liquid_density": {
        "equation": "1",
        "value_kg_per_m3": 1.0e12,
        "why": "the model's liquid molar volume is zero (spec 3.3, 3.7): DWSIM's Ideal-mode "
        "liquid enthalpy adds P / rho_L and its liquid fugacity a Poynting factor; at 1e12 kg/m3 "
        "P v <= 1e-8 J/mol and v (P - P_sat) / (R T) <= 1e-13 (B-50, ESC-50)",
    },
    "property_package_options": {
        "LiquidDensity_CorrectExpDataForPressure": False,
        "LiquidFugacity_UsePoyntingCorrectionFactor": False,
        "EnthalpyEntropyCpCvCalculationMode": "Ideal",
        "VaporPhaseFugacityCalculationMode": "Ideal",
        "AutoEstimateMissingNRTLUNIQUACParameters": False,
    },
    "placeholders": {
        "T_c_K": 1000.0,
        "P_c_Pa": 1.0e7,
        "omega": 0.0,
        "NBP_K": 350.0,
        "why": "required fields of a DWSIM compound that wilson-ig-v1 does not define; T_c > "
        "T / 0.98 keeps every state on the activity-coefficient branch of DW_CalcFugCoeff and "
        "AUX_HVAPi below T_c (T06's placeholders)",
    },
    "wilson": {
        "R_cal_per_mol_K": DWSIM_WILSON_R,
        "rule": "per state (spec 8.2): A_ij = -1.9872 T ln(Lambda_ij V_i / V_j) cal/mol with V "
        "from DWSIM's GetArguments, stored as BIPs[cas_i][cas_j] = (A_ij, A_ji) for i < j "
        "(WilsonModel.GetBIPs returns A_ij for (i, j) and A_ji for (j, i))",
    },
    "flash": {
        "route": "one material stream at the registered (n, T, P), TP-flashed by "
        "CalculateFlowsheet4; the property package's flash (UniversalFlash) is also called "
        "directly with the same inputs for its raw arrays and iteration count",
        "flash_settings_fixed": {
            "ForceEquilibriumCalculationType": "VLE",
            "FailSafeCalculationMode": "3",
            "PTFlash_Maximum_Number_Of_External_Iterations": "1000",
            "PTFlash_Maximum_Number_Of_Internal_Iterations": "1000",
        },
        "why": "VLE: the Wilson liquid is strictly convex in composition (spec 4.1), so no "
        "liquid split exists for the heuristic to look for; FailSafeCalculationMode 3 ('None'): "
        "a failed flash raises instead of being replaced by DWSIM's Raoult's-law flash (mode 1, "
        "the default); 1000 iterations: T06's value (B-52)",
    },
}
#: §8.2: "flash tolerances ladder (1e-10, 1e-8)"; the selection rule is §8.1's (B-53).
LADDER = {
    "tolerances": [1e-10, 1e-8],
    "settings_per_rung": [
        "PTFlash_External_Loop_Tolerance",
        "PTFlash_Internal_Loop_Tolerance",
    ],
    "selection": "the first rung at which every I-state converges is used for all of them; a "
    "state converged at no rung is NOT_COMPARABLE (spec 8.1's rule, B-53)",
    "converged": "no exception from the direct flash call and no solver error from "
    "CalculateFlowsheet4, with the stream calculated",
}
#: §8.1's tolerances (S10.A41), applied by §8.2.
TOL_ABS_BETA_X_Y = 1e-7
TOL_REL_K = 1e-7
TOL_ABS_H = 0.05  # J/mol


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dumps(doc: Any) -> str:
    return json.dumps(doc, indent=1, sort_keys=True) + "\n"


def generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("s10_reference", GENERATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["s10_reference"] = module
    spec.loader.exec_module(module)
    return module


# ============================================================================================
# 1. inputs.json: the tool's only input
# ============================================================================================


def inputs() -> dict[str, Any]:
    rec = yaml.safe_load(RECORDS.read_bytes())
    real = yaml.safe_load(REAL.read_bytes())
    comps = []
    for c in rec["components"]:
        p = c["parameters"]
        comps.append(
            {
                "id": c["id"],
                "ideal_gas_cp_b": [float(p[f"ideal_gas_cp_b{k}"]["value"]) for k in range(5)],
                "standard_formation_enthalpy_J_per_mol": float(
                    p["standard_formation_enthalpy"]["value"]
                ),
                "vapour_pressure_abcd": [float(p[f"vapour_pressure_{s}"]["value"]) for s in "abcd"],
                "molecular_weight_kg_per_mol": float(c["molecular_weight"]["value"]),
            }
        )
    states = {
        sid: {k: entry["state"][k] for k in ("n", "T", "P")}
        for sid, entry in real["closed_form"]["i_states"].items()
    }
    return {
        "authority": "docs/derivations/S10-spec.md section 8.2 with the I-states of section 15 "
        "A2-3",
        "written_by": "scripts/s10_dwsim_comparison.py --write-inputs",
        "records": {
            "path": "benchmarks/s10/records.yaml",
            "sha256": sha256(RECORDS),
            "reference_convention": rec["reference_convention"],
            "forms": "c_p^ig/R = sum_k b_k theta^k; ln(P_sat/Pa) = a + b/theta + c ln theta + "
            "d theta^2; theta = T / 1000 K; h^ig(298.15 K) = Delta_fH; Wilson Lambda_ij constant",
            "R_J_per_mol_K": 8.31446261815324,
            "theta_unit_K": 1000.0,
            "T0_K": 298.15,
            "components": comps,
            "wilson_lambda": [
                {"i": e["i"], "j": e["j"], "value": float(e["value"])} for e in rec["wilson_lambda"]
            ],
        },
        "i_states": {
            "path": "benchmarks/s10/reference_values_real.yaml",
            "sha256": sha256(REAL),
            "fields": "closed_form.i_states.<id>.state (n, T, P) only",
            "states": states,
        },
        "readback_compositions": {
            "rule": "at each state's (T, P): the feed z, then these (B-51)",
            "x": [list(x) for x in READBACK_X],
        },
        "settings": SETTINGS,
        "ladder": LADDER,
    }


# ============================================================================================
# 2. comparison.json
# ============================================================================================


def _rel(a: float, b: Any) -> float:
    return float(abs(mpf(a) - b) / abs(b))


def wilson_mapping_check(q: dict[str, Any], model: Any) -> dict[str, Any]:
    """DWSIM's effective Lambda, recomputed here from the BIPs and volumes the tool read back
    and DWSIM's own form, against records.yaml's Lambda; and the A the tool applied against the
    rule recomputed from the same volumes."""
    worst_lam, worst_a = 0.0, 0.0
    rows = {}
    for sid, st in q["states"].items():
        rb = st["readback"]
        t, v = st["state"]["T"], rb["molar_volumes_m3_per_kmol"]
        lam_d, a_rule = [], []
        for i in range(3):
            for j in range(3):
                a_ij = rb["bips_cal_per_mol"][i][j]
                lam = v[j] / v[i] * math.exp(-a_ij / (DWSIM_WILSON_R * t))
                lam_d.append(lam)
                worst_lam = max(worst_lam, _rel(lam, model.lam[i][j]))
                if i != j:
                    rule = -DWSIM_WILSON_R * t * math.log(float(model.lam[i][j]) * v[i] / v[j])
                    a_rule.append(rule)
                    worst_a = max(worst_a, abs(st["applied_bips_cal_per_mol"][i][j] - rule))
        rows[sid] = {"effective_lambda": lam_d}
    return {
        "form": "Lambda_ij = V_j / V_i exp(-A_ij / (1.9872 T)) (DWSIM 9.0.5 WilsonModel.vb)",
        "max_relative_effective_lambda_vs_records": worst_lam,
        "max_abs_applied_A_vs_rule_cal_per_mol": worst_a,
        "per_state": rows,
    }


def readbacks(q: dict[str, Any], model: Any) -> dict[str, Any]:
    """The gamma gate (spec 8.2) and, informative, the pure-component and phase-enthalpy rows."""
    gamma_rows, info_rows = [], []
    for sid, st in q["states"].items():
        rb = st["readback"]
        t = mpf(st["state"]["T"])
        mw = [c["molecular_weight_kg_per_mol"] * 1000.0 for c in q["inputs_echo"]["components"]]
        for pt in rb["points"]:
            x = [mpf(v) for v in pt["x"]]
            lg = model.lngamma(x)
            for i, c in enumerate(IDS):
                g = mp.exp(lg[i])
                gamma_rows.append(
                    {
                        "state": sid,
                        "x": pt["x"],
                        "component": c,
                        "dwsim": pt["gamma"][i],
                        "generator": float(g),
                        "relative": _rel(pt["gamma"][i], g),
                    }
                )
                # phi^L = gamma P_sat / P (Poynting off, vapour ideal): DWSIM's DW_CalcFugCoeff.
                phi = g * mp.exp(model.lnpsat(i, t)) / mpf(st["state"]["P"])
                info_rows.append(
                    {
                        "state": sid,
                        "quantity": "phi_L",
                        "x": pt["x"],
                        "component": c,
                        "dwsim": pt["phi_L"][i],
                        "generator": float(phi),
                        "relative": _rel(pt["phi_L"][i], phi),
                    }
                )
            hmix = {
                "h_L": sum(x[i] * model.h0l(i, t) for i in range(3)),
                "h_V": sum(x[i] * model.h_ig(i, t) for i in range(3)),
            }
            for name, v in hmix.items():
                got = pt[f"{name}_J_per_mol"]
                info_rows.append(
                    {
                        "state": sid,
                        "quantity": name,
                        "x": pt["x"],
                        "component": None,
                        "dwsim": got,
                        "generator": float(v),
                        "absolute_J_per_mol": float(abs(mpf(got) - v)),
                        "relative": _rel(got, v),
                    }
                )
        for i, c in enumerate(IDS):
            pc = rb["pure"][c]
            pure = {
                "P_sat_Pa": (pc["AUX_PVAPi_Pa"], mp.exp(model.lnpsat(i, t))),
                "dh_vap_J_per_mol": (pc["AUX_HVAPi_kJ_per_kg"] * mw[i], model.dhvap(i, t)),
                "cp_ig_J_per_mol_K": (pc["AUX_CPi_kJ_per_kg_K"] * mw[i], model.cp_ig(i, t)),
                "h_ig_J_per_mol": (
                    (pc["AUX_INT_CPDTi_298_15_kJ_per_kg"] + pc["IG_Enthalpy_of_Formation_25C"])
                    * mw[i],
                    model.h_ig(i, t),
                ),
            }
            for name, (got, v) in pure.items():
                info_rows.append(
                    {
                        "state": sid,
                        "quantity": name,
                        "x": None,
                        "component": c,
                        "dwsim": got,
                        "generator": float(v),
                        "absolute": float(abs(mpf(got) - v)),
                        "relative": _rel(got, v),
                    }
                )
    worst = max(gamma_rows, key=lambda r: r["relative"])
    worst_info: dict[str, Any] = {}
    for r in info_rows:
        k = r["quantity"]
        if k not in worst_info or r["relative"] > worst_info[k]["relative"]:
            worst_info[k] = {
                "relative": r["relative"],
                "absolute": r.get("absolute", r.get("absolute_J_per_mol")),
                "at": f"{r['state']} {r['component']} {r['x']}",
            }
    return {
        "gamma_gate": {
            "rule": "spec 8.2: gamma at the state's (T, x) matches ours to 1e-9 relative before "
            "the flash; x = the feed z and the two RB compositions (B-51)",
            "tolerance_relative": GAMMA_RELATIVE,
            "expected": "exp(ln gamma) of s10_reference.Model on records.yaml (50 digits)",
            "rows": gamma_rows,
            "max_relative": worst["relative"],
            "argmax": f"{worst['state']} {worst['component']} {worst['x']}",
            "all_within": all(r["relative"] <= GAMMA_RELATIVE for r in gamma_rows),
        },
        "informative": {
            "note": "no tolerance is registered for these rows (spec 8.2 gates gamma only); "
            "they show what DWSIM evaluates from the mapping, the units fixed by readback, and "
            "DWSIM's own numerics (its ideal-gas enthalpy is a midpoint-rule integral of c_p, "
            "PropertyPackage.vb AUX_INT_CPDTi)",
            "worst_per_quantity": worst_info,
            "rows": info_rows,
        },
    }


def phase_identity(beta: float) -> str:
    if abs(beta) <= TOL_ABS_BETA_X_Y:
        return "LIQUID"
    if abs(beta - 1.0) <= TOL_ABS_BETA_X_Y:
        return "VAPOR"
    return "TWO_PHASE"


def beta(qty: dict[str, Any]) -> float:
    """The stream's vapour fraction; DWSIM reports none when the vapour phase is absent, and then
    the vapour fraction is 1 - the liquid fraction it reports."""
    vf = qty["vapor_molarfraction"]
    return float(vf) if vf is not None else 1.0 - float(qty["liquid_molarfraction"])


def state_rows(qty: dict[str, Any], cf: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        {
            "quantity": "beta",
            "dwsim": beta(qty),
            "ours": cf["beta"],
            "basis": "absolute",
            "tolerance": TOL_ABS_BETA_X_Y,
        }
    ]
    for i, c in enumerate(IDS):
        for name in ("x", "y"):
            rows.append(
                {
                    "quantity": f"{name}_{c}",
                    "dwsim": qty[name][i],
                    "ours": cf[name][i],
                    "basis": "absolute",
                    "tolerance": TOL_ABS_BETA_X_Y,
                }
            )
    for i, c in enumerate(IDS):
        if cf["K"][i] is not None:
            rows.append(
                {
                    "quantity": f"K_{c}",
                    "dwsim": qty["y"][i] / qty["x"][i],
                    "ours": cf["K"][i],
                    "basis": "relative",
                    "tolerance": TOL_REL_K,
                }
            )
    for name in ("h_L", "h_V"):
        rows.append(
            {
                "quantity": name,
                "dwsim": qty[f"{name}_J_per_mol"],
                "ours": cf[name],
                "basis": "absolute",
                "tolerance": TOL_ABS_H,
            }
        )
    for r in rows:
        d = abs(r["dwsim"] - r["ours"])
        r["delta"] = d / abs(r["ours"]) if r["basis"] == "relative" else d
        r["ratio"] = r["delta"] / r["tolerance"]
        r["within"] = r["delta"] <= r["tolerance"]
    return rows


def ladder(q: dict[str, Any]) -> dict[str, Any]:
    """The selection rule, recomputed from the attempts' own convergence flags."""
    conv: dict[str, list[float]] = {sid: [] for sid in q["states"]}
    for a in q["attempts"]:
        if a["converged"]:
            conv[a["state"]].append(a["tolerance"])
    selected = next(
        (tol for tol in LADDER["tolerances"] if all(tol in v for v in conv.values())), None
    )
    return {
        "converged_rungs_per_state": conv,
        "selected_tolerance": selected,
        "not_comparable": sorted(sid for sid, v in conv.items() if not v),
        "attempts": [
            {k: a.get(k) for k in ("state", "tolerance", "converged", "solver_errors", "exception")}
            | {"iterations": (a.get("direct_flash") or {}).get("ecount")}
            for a in q["attempts"]
        ],
    }


def a45(
    q: dict[str, Any], real: dict[str, Any], gate: dict[str, Any], lad: dict[str, Any]
) -> dict[str, Any]:
    states: dict[str, Any] = {}
    tol = lad["selected_tolerance"]
    for sid, entry in real["closed_form"]["i_states"].items():
        if not gate["all_within"]:
            states[sid] = {
                "status": "NOT_COMPARABLE",
                "reason": "the gamma readback differs (spec 8.2's pre-registered outcome: every "
                "DWSIM state NOT_COMPARABLE)",
            }
            continue
        if sid in lad["not_comparable"]:
            states[sid] = {"status": "NOT_COMPARABLE", "reason": "converged at no rung"}
            continue
        if tol is None:
            states[sid] = {
                "status": "NO_SELECTED_RUNG",
                "converged_rungs": lad["converged_rungs_per_state"][sid],
                "reason": "no rung at which every I-state converges; no difference is computed",
            }
            continue
        a = next(
            t
            for t in q["attempts"]
            if t["state"] == sid and t["tolerance"] == tol and t["converged"]
        )
        qty = a["quantities"]
        rec: dict[str, Any] = {
            "status": "compared",
            "tolerance": tol,
            "temperature": entry["state"]["T"],
        }
        if entry["phase"] == "TWO_PHASE":
            rows = state_rows(qty, entry["closed_form"])
            worst = max(rows, key=lambda r: r["ratio"])
            rec.update(
                {
                    "rows": rows,
                    "max_ratio": worst["ratio"],
                    "argmax": worst["quantity"],
                    "all_within": all(r["within"] for r in rows),
                }
            )
        else:
            b = beta(qty)
            got = phase_identity(b)
            rec.update(
                {
                    "phase_ours": entry["phase"],
                    "phase_dwsim": got,
                    "beta_dwsim": b,
                    "phase_rule": "LIQUID if |beta| <= 1e-7, VAPOR if |beta - 1| <= 1e-7, "
                    "else TWO_PHASE (B-36's rule)",
                    "all_within": got == entry["phase"],
                }
            )
        states[sid] = rec
    return {
        "assertion": "S10.A45",
        "selected_tolerance": tol,
        "tolerances": {
            "beta_x_y_absolute": TOL_ABS_BETA_X_Y,
            "K_relative": TOL_REL_K,
            "h_absolute_J_per_mol": TOL_ABS_H,
            "I6_I7": "the phase identity, exact",
        },
        "expected": "reference_values_real.yaml closed_form.i_states (two-phase) and phase "
        "(I6, I7)",
        "states": states,
        "verdict": "the verdict agent's, per state; nothing here classifies",
    }


def comparison() -> dict[str, Any]:
    g = generator()
    q = json.loads(QUALIFICATION.read_text(encoding="utf-8"))
    real = yaml.safe_load(REAL.read_bytes())
    model = g.Model(g.load_records(RECORDS))
    rb = readbacks(q, model)
    lad = ladder(q)
    return {
        "authority": "docs/derivations/S10-spec.md section 8.2 (I-states of section 15 A2-3)",
        "written_by": "scripts/s10_dwsim_comparison.py --write",
        "provenance": {
            p.name: sha256(p) for p in (QUALIFICATION, INPUTS, RECORDS, REAL, GENERATOR)
        },
        "environment": {
            "fingerprint_matches": q["environment_fingerprint"]["matches"],
            "versions": q["versions"],
        },
        "settings_readback": q["settings_readback"],
        "wilson_mapping_check": wilson_mapping_check(q, model),
        "readbacks": rb,
        "ladder": lad,
        "comparison": a45(q, real, rb["gamma_gate"], lad),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write-inputs", action="store_true")
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.write_inputs:
        OUT.mkdir(parents=True, exist_ok=True)
        INPUTS.write_text(dumps(inputs()), encoding="utf-8")
        print(f"wrote {INPUTS.relative_to(ROOT)}")
        return 0
    doc = dumps(comparison())
    if args.write:
        COMPARISON.write_text(doc, encoding="utf-8")
        print(f"wrote {COMPARISON.relative_to(ROOT)}")
        return 0
    same_inputs = INPUTS.read_text(encoding="utf-8") == dumps(inputs())
    same = COMPARISON.exists() and COMPARISON.read_text(encoding="utf-8") == doc
    print(
        f"inputs.json {'recomputes identically' if same_inputs else 'differs'}; "
        f"comparison.json {'recomputes identically' if same else 'differs'}"
    )
    return 0 if same and same_inputs else 1


if __name__ == "__main__":
    sys.exit(main())
