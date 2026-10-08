"""M01 external cross-check: the component records against their retrieval sources, and W22's
pure-NH3 comparison.

Specification: ``docs/derivations/M01-spec.md`` sections 3.3 (records) and 9.4 (W22). Runs in a
separate environment outside this repository (never the project ``.venv``), with exactly::

    chemicals==1.5.2 thermo==0.6.1 CoolProp==8.0.0 cantera==3.2.0 pyyaml==6.0.2

and writes ``benchmarks/m01/external-crosscheck.json``. ``--check`` recomputes and compares byte
for byte. It reads ``benchmarks/m01/components.yaml`` and ``benchmarks/m01/reference_values.yaml``
(the generator's 50-digit Peng-Robinson saturation values) and imports nothing from
``openflowsheet``.

Three parts:

1. **Retrieval.** Every recorded T_c, P_c, omega and formation enthalpy equals the value chemicals
   1.5.2 returns for the method named in its provenance (exact float equality), every NASA-7
   coefficient equals Cantera 3.2.0's ``nasa_gas.yaml`` low range scaled by 1000^k (to 1e-15
   relative), the molar mass equals chemicals'.
2. **Cross-check** (stated deviations, not gates): CoolProp 8.0.0's critical point and its
   acentric factor by definition (-log10(P_sat(0.7 T_c)/P_c) - 1); the ideal-gas c_p against
   CoolProp's reference-EOS ideal part and the JANAF tables (thermo HeatCapacityGas method JANAF);
   formation enthalpies against JANAF (chemicals).
3. **W22 validation, pure NH3.** Peng-Robinson's saturation pressure, saturated-liquid volume and
   enthalpy of vaporization against CoolProp's ammonia (Gao et al. 2020, the reference EOS) at the
   registered temperatures.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
import math
import sys
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
COMPONENTS = HERE / "components.yaml"
REFERENCE = HERE / "reference_values.yaml"
OUT = HERE / "external-crosscheck.json"
PINS = {
    "chemicals": "1.5.2",
    "thermo": "0.6.1",
    "CoolProp": "8.0.0",
    "cantera": "3.2.0",
    "PyYAML": "6.0.2",
}
COOLPROP_NAME = {
    "H2": "Hydrogen",
    "N2": "Nitrogen",
    "NH3": "Ammonia",
    "Ar": "Argon",
    "CH4": "Methane",
}
CP_TEMPERATURES = (250.0, 298.15, 500.0, 700.0, 1000.0)


def build() -> dict[str, Any]:
    ct: Any = importlib.import_module("cantera")
    coolprop: Any = importlib.import_module("CoolProp.CoolProp")
    acentric: Any = importlib.import_module("chemicals.acentric")
    critical: Any = importlib.import_module("chemicals.critical")
    elements: Any = importlib.import_module("chemicals.elements")
    identifiers: Any = importlib.import_module("chemicals.identifiers")
    reaction: Any = importlib.import_module("chemicals.reaction")
    thermo: Any = importlib.import_module("thermo")

    recs = yaml.safe_load(COMPONENTS.read_text(encoding="utf-8"))["components"]
    gas_yaml = Path(ct.__file__).parent / "data" / "nasa_gas.yaml"
    nasa = {s["name"]: s for s in yaml.safe_load(gas_yaml.read_text(encoding="utf-8"))["species"]}
    r_gas = 8.31446261815324
    out: dict[str, Any] = {
        "record": "m01-external-crosscheck",
        "version": 1,
        "status": "measured",
        "judged": False,
        "specification": "docs/derivations/M01-spec.md sections 3.3 and 9.4",
        "packages": {p: importlib.metadata.version(p) for p in PINS},
        "retrieval": {},
        "crosscheck": {},
    }
    failures = []
    for r in recs:
        cid = r["id"]
        cas = r["identifiers"]["cas"]
        p = r["parameters"]
        chem = identifiers.search_chemical(cas)
        got = {
            "critical_temperature": critical.Tc(cas, method="HEOS"),
            "critical_pressure": critical.Pc(cas, method="HEOS"),
            "acentric_factor": acentric.omega(cas, method="HEOS"),
            "standard_formation_enthalpy": reaction.Hfg(cas, method="ATCT_G"),
            "molecular_weight_kg_mol": elements.molecular_weight(
                elements.simple_formula_parser(chem.formula)
            )
            / 1000.0,
        }
        rec_vals = {k: float(p[k]["value"]) for k in got if k in p}
        rec_vals["molecular_weight_kg_mol"] = float(r["molecular_weight"]["value"])
        eq = {
            k: (rec_vals[k] == got[k])
            if k != "molecular_weight_kg_mol"
            else abs(rec_vals[k] / got[k] - 1) < 1e-12
            for k in got
        }
        lo = nasa[cid]["thermo"]["data"][0]
        rng = nasa[cid]["thermo"]["temperature-ranges"]
        nasa_ok = all(
            abs(float(p[f"ideal_gas_cp_b{k}"]["value"]) - lo[k] * 1000.0**k)
            <= 1e-15 * max(1.0, abs(lo[k] * 1000.0**k))
            for k in range(5)
        )
        nasa_ok = nasa_ok and rng[0] == 200.0 and (len(rng) == 2 or rng[1] == 1000.0)
        ident_ok = (
            chem.InChI == r["identifiers"]["inchi"].removeprefix("InChI=1S/")
            and chem.InChI_key == r["identifiers"]["inchikey"]
        )
        out["retrieval"][cid] = {
            "equal": eq,
            "nasa7_low_range_equal": nasa_ok,
            "identifiers_equal": ident_ok,
            "nasa_note": nasa[cid]["thermo"].get("note"),
        }
        if not (all(eq.values()) and nasa_ok and ident_ok):
            failures.append(cid)
        # Cross-checks.
        fl = COOLPROP_NAME[cid]
        tc, pc = coolprop.PropsSI("Tcrit", fl), coolprop.PropsSI("pcrit", fl)
        om_def = -math.log10(coolprop.PropsSI("P", "T", 0.7 * tc, "Q", 0, fl) / pc) - 1.0
        bk = [float(p[f"ideal_gas_cp_b{k}"]["value"]) for k in range(5)]
        cp_dev, janaf_dev = {}, {}
        hcg = thermo.HeatCapacityGas(CASRN=cas)
        for temp in CP_TEMPERATURES:
            cp_rec = r_gas * sum(bk[k] * (temp / 1000.0) ** k for k in range(5))
            cp0 = coolprop.PropsSI("CP0MOLAR", "T", temp, "P", 1e3, fl)
            cp_dev[str(temp)] = round(cp_rec / cp0 - 1.0, 7)
            try:
                janaf_dev[str(temp)] = round(cp_rec / hcg.calculate(temp, "JANAF") - 1.0, 7)
            except Exception:  # noqa: BLE001 -- JANAF absent for this species
                janaf_dev[str(temp)] = None
        try:
            hf_janaf = reaction.Hfg(cas, method="JANAF")
        except Exception:  # noqa: BLE001
            hf_janaf = None
        out["crosscheck"][cid] = {
            "coolprop_eos": coolprop.get_fluid_param_string(fl, "BibTeX-EOS"),
            "Tc_rel_dev": round(float(p["critical_temperature"]["value"]) / tc - 1.0, 9),
            "Pc_rel_dev": round(float(p["critical_pressure"]["value"]) / pc - 1.0, 9),
            "omega_record_minus_definition": round(
                float(p["acentric_factor"]["value"]) - om_def, 6
            ),
            "cp_rel_dev_vs_coolprop_ideal_gas": cp_dev,
            "cp_rel_dev_vs_janaf": janaf_dev,
            "dHf_record_minus_janaf_J_mol": None
            if hf_janaf is None
            else round(float(p["standard_formation_enthalpy"]["value"]) - hf_janaf, 3),
        }
    out["retrieval_all_equal"] = not failures
    # W22: pure NH3 saturation.
    ref = yaml.safe_load(REFERENCE.read_text(encoding="utf-8"))["closed_form"]["nh3_saturation_pr"]
    w22 = {}
    for tk, v in ref.items():
        temp = float(tk)
        ps = coolprop.PropsSI("P", "T", temp, "Q", 0, "Ammonia")
        vl = 1.0 / coolprop.PropsSI("Dmolar", "T", temp, "Q", 0, "Ammonia")
        hv = coolprop.PropsSI("Hmolar", "T", temp, "Q", 1, "Ammonia") - coolprop.PropsSI(
            "Hmolar", "T", temp, "Q", 0, "Ammonia"
        )
        w22[tk] = {
            "P_sat_ref_Pa": round(ps, 3),
            "P_sat_rel_dev": round(v["P_sat_Pa"] / ps - 1.0, 6),
            "v_L_rel_dev": round(v["v_L_m3_mol"] / vl - 1.0, 6),
            "h_vap_rel_dev": round(v["h_vap_J_mol"] / hv - 1.0, 6),
        }
    pure = yaml.safe_load(REFERENCE.read_text(encoding="utf-8"))["closed_form"][
        "pure_component_states"
    ]
    pc_out = {}
    for key, v in pure.items():
        cid = key.split("-")[0]
        st = coolprop.AbstractState("HEOS", COOLPROP_NAME[cid])
        st.update(coolprop.PT_INPUTS, float(v["P_Pa"]), float(v["T_K"]))
        lnphi_ref = math.log(st.fugacity_coefficient(0))
        pc_out[key] = {
            "lnphi_ref": round(lnphi_ref, 9),
            "lnphi_pr_minus_ref": round(float(v["lnphi"]) - lnphi_ref, 6),
            "Z_rel_dev": round(float(v["Z"]) / st.compressibility_factor() - 1.0, 6),
            "h_dep_pr_J_mol": round(float(v["h_departure_J_mol"]), 3),
        }
    out["w22_pure_component_fugacity_vs_reference_eos"] = pc_out
    out["w22_pure_nh3_vs_reference_eos"] = {
        "reference": "CoolProp 8.0.0 Ammonia, "
        + coolprop.get_fluid_param_string("Ammonia", "BibTeX-EOS"),
        "by_temperature_K": w22,
    }
    if failures:
        out["retrieval_failures"] = failures
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--emit", action="store_true")
    args = ap.parse_args()
    bad = {
        p: importlib.metadata.version(p) for p in PINS if importlib.metadata.version(p) != PINS[p]
    }
    if bad:
        print(f"package versions differ from the pins: {bad}", file=sys.stderr)
        return 2
    text = json.dumps(build(), indent=1) + "\n"
    if args.emit:
        OUT.write_text(text, encoding="utf-8")
        return 0
    same = OUT.exists() and OUT.read_text(encoding="utf-8") == text
    print("external-crosscheck.json", "matches" if same else "DIFFERS")
    return 0 if same else 1


if __name__ == "__main__":
    raise SystemExit(main())
