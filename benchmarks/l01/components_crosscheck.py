"""L01 retrieval and cross-check: the library records against their retrieval sources and CoolProp.

Specification: ``docs/derivations/L01-spec.md`` section 4.1 (records, sources, cross-check) and
assertion L01.A12. Runs in a separate environment outside this repository (never the project
``.venv``), with exactly::

    chemicals==1.5.2 thermo==0.6.1 CoolProp==8.0.0 cantera==3.2.0 pyyaml==6.0.2

and writes ``benchmarks/l01/components-crosscheck.json``. ``--check`` recomputes and compares
byte for byte. It reads ``benchmarks/l01/components.yaml`` and the literature table of
``docs/derivations/scripts/l01_projection.json`` and imports nothing from ``openflowsheet``. The
installed packages' data files are read as data (YAML, BibTeX, tables); nothing in them is run.

Without the pinned packages ``--check`` does not pass: it prints ``SKIPPED:`` with the missing or
mismatched distributions and exits 3 (CI does not carry them; ``tests/test_l01_records.py`` runs
the real check when ``OFS_L01_SOURCES_PYTHON`` names an interpreter that has them).

Three parts, for all nine records (the four copied from C1 are re-derived too):

1. **Retrieval** (gates; any failure exits 1 on ``--emit``). Every recorded T_c, P_c, omega and
   formation enthalpy equals the value chemicals 1.5.2 returns for the method named in its
   provenance (exact float equality); every b_k equals a_(k+1) * 1000^k of Cantera 3.2.0's
   ``nasa_gas.yaml`` low range exactly in decimal, the range is 200-1000 K and the species note is
   the one the provenance quotes; the molar mass equals sum n_e A_e / 1000 exactly in decimal with
   chemicals' tabulated atomic weights; CAS, InChI, InChIKey, formula and elemental composition
   equal chemicals'; the ATcT uncertainty the provenance quotes is the table's; the reference
   EOS's DOI the provenance quotes is the one CoolProp 8.0.0's bibliography gives for its EOS.
2. **Cross-check** (stated deviations, not gates): CoolProp 8.0.0's critical point, its acentric
   factor (as stated and by definition, -log10(P_sat(0.7 T_c)/P_c) - 1); the ideal-gas c_p against
   CoolProp's reference-EOS ideal part at 298.15, 300, 600 and 900 K (L01.A12 bounds 300/600/900 K
   at 0.5 %) and against JANAF (thermo method JANAF); formation enthalpies against JANAF.
3. **Literature** (spec section 10 Q-5): each dagger value of the literature table beside the
   record and the independent machine-readable values above. This corroborates the transcriptions;
   it does not replace the printed sources Q-5 names.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import math
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
COMPONENTS = HERE / "components.yaml"
PROJECTION = ROOT / "docs" / "derivations" / "scripts" / "l01_projection.json"
OUT = HERE / "components-crosscheck.json"
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
    "Ar": "Argon",
    "CH4": "Methane",
    "H2O": "Water",
    "CO2": "CarbonDioxide",
    "O2": "Oxygen",
    "C2H6": "Ethane",
    "C3H8": "n-Propane",
}
NEW = ("H2O", "CO2", "O2", "C2H6", "C3H8")
CP_TEMPERATURES = (298.15, 300.0, 600.0, 900.0)
#: L01.A12: |c_p - c_p,CoolProp| / c_p at these temperatures, each <= 0.5 %.
A12_TEMPERATURES = ("300.0", "600.0", "900.0")
A12_BOUND = 0.005
R_GAS = 8.31446261815324
SKIPPED = 3


def _missing_pins() -> dict[str, str | None]:
    """Distributions absent or at another version than the pins (read without importing them)."""
    found: dict[str, str | None] = {}
    for name, pin in PINS.items():
        try:
            version: str | None = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            version = None
        if version != pin:
            found[name] = version
    return found


def _bib_doi(bib_text: str, key: str) -> str | None:
    """The ``Doi`` field of entry ``key`` in CoolProp's BibTeX library (read as text)."""
    start = bib_text.find("{" + key + ",")
    if start < 0:
        return None
    end = bib_text.find("\n}", start)
    match = re.search(r"(?im)^\s*doi\s*=\s*\{([^}]*)\}", bib_text[start:end])
    return match.group(1).strip() if match else None


def _dec(x: float) -> Decimal:
    return Decimal(repr(x))


def _retrieve(
    r: dict[str, Any], mods: dict[str, Any], nasa: dict[str, Any], bib: str
) -> dict[str, Any]:
    critical, acentric, reaction = mods["critical"], mods["acentric"], mods["reaction"]
    elements, identifiers, coolprop = mods["elements"], mods["identifiers"], mods["coolprop"]
    cid, cas, p = r["id"], r["identifiers"]["cas"], r["parameters"]
    chem = identifiers.search_chemical(cas)
    got = {
        "critical_temperature": critical.Tc(cas, method="HEOS"),
        "critical_pressure": critical.Pc(cas, method="HEOS"),
        "acentric_factor": acentric.omega(cas, method="HEOS"),
        "standard_formation_enthalpy": reaction.Hfg(cas, method="ATCT_G"),
    }
    equal: dict[str, bool] = {k: float(p[k]["value"]) == float(v) for k, v in got.items()}
    composition = elements.simple_formula_parser(chem.formula)
    mw = sum(_dec(elements.periodic_table[e].MW) * n for e, n in composition.items()) / 1000
    mw_rec = float(r["molecular_weight"]["value"])
    equal["molar_mass_decimal"] = _dec(mw_rec) == mw
    equal["molar_mass_chemicals_1e-12"] = (
        abs(mw_rec / (elements.molecular_weight(composition) / 1000.0) - 1.0) < 1e-12
    )
    spec = nasa[cid]["thermo"]
    low = spec["data"][0]
    equal["nasa7_low_range_decimal"] = all(
        _dec(float(p[f"ideal_gas_cp_b{k}"]["value"])) == _dec(low[k]) * Decimal(1000) ** k
        for k in range(5)
    )
    ranges = spec["temperature-ranges"]
    # C1's rule (M01's external_crosscheck.py): the low range starts at 200 K and either breaks at
    # 1000 K or is a single fit covering it (Ar: one range, 200-6000 K).
    equal["nasa7_range_200_1000"] = (
        ranges[0] == 200.0
        and (ranges[1] == 1000.0 or (len(ranges) == 2 and ranges[1] >= 1000.0))
        and float(p["ideal_gas_cp_lower_temperature"]["value"]) == 200.0
        and float(p["ideal_gas_cp_upper_temperature"]["value"]) == 1000.0
    )
    note = spec.get("note")
    equal["nasa7_note_quoted"] = all(
        f"species note '{note}'" in p[f"ideal_gas_cp_b{k}"]["provenance"] for k in range(5)
    )
    ids = r["identifiers"]
    equal["identifiers"] = (
        chem.CASs == cas
        and chem.InChI == ids["inchi"].removeprefix("InChI=1S/")
        and chem.InChI_key == ids["inchikey"]
        and chem.formula == ids["formula"]
    )
    equal["elemental_composition"] = dict(composition) == dict(r["elemental_composition"])
    hf_prov = p["standard_formation_enthalpy"]["provenance"]
    table = reaction.Hfg_ATcT_data
    if got["standard_formation_enthalpy"] == 0.0:
        equal["atct_uncertainty_quoted"] = "zero by definition" in hf_prov
    else:
        u = float(table.loc[cas, "uncertainty"]) / 1000.0
        equal["atct_uncertainty_quoted"] = f"uncertainty {u:g} kJ/mol" in hf_prov
    eos_key = coolprop.get_BibTeXKey(COOLPROP_NAME[cid], "EOS").split(",")[0]
    doi = _bib_doi(bib, eos_key)
    equal["eos_doi_quoted"] = doi is not None and all(
        f"doi:{doi}" in p[k]["provenance"]
        for k in ("critical_temperature", "critical_pressure", "acentric_factor")
    )
    return {
        "equal": equal,
        "nasa_note": note,
        "nasa_temperature_ranges": ranges,
        "coolprop_eos_key": eos_key,
        "coolprop_eos_doi": doi,
    }


def _crosscheck(r: dict[str, Any], mods: dict[str, Any]) -> dict[str, Any]:
    coolprop, thermo, reaction = mods["coolprop"], mods["thermo"], mods["reaction"]
    cid, cas, p = r["id"], r["identifiers"]["cas"], r["parameters"]
    fl = COOLPROP_NAME[cid]
    tc, pc = coolprop.PropsSI("Tcrit", fl), coolprop.PropsSI("pcrit", fl)
    om_def = -math.log10(coolprop.PropsSI("P", "T", 0.7 * tc, "Q", 0, fl) / pc) - 1.0
    om_stated = coolprop.PropsSI("acentric", fl)
    bk = [float(p[f"ideal_gas_cp_b{k}"]["value"]) for k in range(5)]
    hcg = thermo.HeatCapacityGas(CASRN=cas)
    cp_dev: dict[str, float] = {}
    janaf_dev: dict[str, float | None] = {}
    for temp in CP_TEMPERATURES:
        cp_rec = R_GAS * sum(bk[k] * (temp / 1000.0) ** k for k in range(5))
        cp0 = coolprop.PropsSI("CP0MOLAR", "T", temp, "P", 1e3, fl)
        cp_dev[str(temp)] = round((cp_rec - cp0) / cp_rec, 7)
        try:
            janaf_dev[str(temp)] = round(cp_rec / hcg.calculate(temp, "JANAF") - 1.0, 7)
        except Exception:  # noqa: BLE001 -- JANAF absent for this species
            janaf_dev[str(temp)] = None
    try:
        hf_janaf: float | None = reaction.Hfg(cas, method="JANAF")
    except Exception:  # noqa: BLE001 -- JANAF absent for this species
        hf_janaf = None
    return {
        "coolprop_eos": coolprop.get_fluid_param_string(fl, "BibTeX-EOS"),
        "coolprop_Tc_K": tc,
        "coolprop_Pc_Pa": pc,
        "coolprop_acentric_stated": om_stated,
        "coolprop_acentric_by_definition": round(om_def, 6),
        "Tc_rel_dev": round(float(p["critical_temperature"]["value"]) / tc - 1.0, 9),
        "Pc_rel_dev": round(float(p["critical_pressure"]["value"]) / pc - 1.0, 9),
        "omega_record_minus_stated": round(float(p["acentric_factor"]["value"]) - om_stated, 9),
        "omega_record_minus_definition": round(float(p["acentric_factor"]["value"]) - om_def, 6),
        "cp_rel_dev_vs_coolprop_ideal_gas": cp_dev,
        "cp_rel_dev_vs_janaf": janaf_dev,
        "dHf_janaf_J_mol": hf_janaf,
        "dHf_record_minus_janaf_J_mol": None
        if hf_janaf is None
        else round(float(p["standard_formation_enthalpy"]["value"]) - hf_janaf, 3),
    }


def _literature(
    r: dict[str, Any], lit: dict[str, str], cross: dict[str, Any], mods: dict[str, Any]
) -> dict[str, Any]:
    """Each dagger value beside the record and the independent machine-readable values."""
    coolprop, thermo = mods["coolprop"], mods["thermo"]
    p, cas, fl = r["parameters"], r["identifiers"]["cas"], COOLPROP_NAME[r["id"]]
    bk = [float(p[f"ideal_gas_cp_b{k}"]["value"]) for k in range(5)]
    cp298 = R_GAS * sum(bk[k] * 0.29815**k for k in range(5))
    try:
        cp298_janaf: float | None = thermo.HeatCapacityGas(CASRN=cas).calculate(298.15, "JANAF")
    except Exception:  # noqa: BLE001 -- JANAF absent for this species
        cp298_janaf = None
    cp298_coolprop = coolprop.PropsSI("CP0MOLAR", "T", 298.15, "P", 1e3, fl)

    def row(lit_value: str, record: float, others: dict[str, float | None]) -> dict[str, Any]:
        v = float(lit_value)
        return {
            "lit": lit_value,
            "record": record,
            "record_minus_lit": round(record - v, 9),
            **{f"{k}_minus_lit": None if o is None else round(o - v, 9) for k, o in others.items()},
        }

    return {
        "src": lit["src"],
        "Tc_K": row(
            lit["Tc"],
            float(p["critical_temperature"]["value"]),
            {"coolprop": cross["coolprop_Tc_K"]},
        ),
        "Pc_Pa": row(
            lit["Pc"], float(p["critical_pressure"]["value"]), {"coolprop": cross["coolprop_Pc_Pa"]}
        ),
        "omega": row(
            lit["omega"],
            float(p["acentric_factor"]["value"]),
            {
                "coolprop_stated": cross["coolprop_acentric_stated"],
                "coolprop_definition": cross["coolprop_acentric_by_definition"],
            },
        ),
        "dHf_J_mol": row(
            lit["dHf"],
            float(p["standard_formation_enthalpy"]["value"]),
            {"janaf": cross["dHf_janaf_J_mol"]},
        ),
        "cp298_J_molK": row(
            lit["cp298"],
            round(cp298, 9),
            {"janaf": cp298_janaf, "coolprop_ideal_gas": cp298_coolprop},
        ),
    }


def build() -> dict[str, Any]:
    yaml: Any = importlib.import_module("yaml")
    ct: Any = importlib.import_module("cantera")
    coolprop: Any = importlib.import_module("CoolProp.CoolProp")
    mods: dict[str, Any] = {
        "coolprop": coolprop,
        "thermo": importlib.import_module("thermo"),
        **{
            name: importlib.import_module(f"chemicals.{name}")
            for name in ("acentric", "critical", "elements", "identifiers", "reaction")
        },
    }
    data = COMPONENTS.read_bytes()
    recs = yaml.safe_load(data.decode("utf-8"))["components"]
    literature = json.loads(PROJECTION.read_text(encoding="utf-8"))["literature"]
    gas_yaml = Path(ct.__file__).parent / "data" / "nasa_gas.yaml"
    nasa = {s["name"]: s for s in yaml.safe_load(gas_yaml.read_text(encoding="utf-8"))["species"]}
    bib = (Path(coolprop.__file__).parent / "CoolPropBibTeXLibrary.bib").read_text(encoding="utf-8")
    out: dict[str, Any] = {
        "record": "l01-components-crosscheck",
        "version": 1,
        "status": "measured",
        "judged": False,
        "specification": "docs/derivations/L01-spec.md section 4.1, L01.A12, section 10 Q-5",
        "packages": {p: importlib.metadata.version(p) for p in PINS},
        "records_sha256": hashlib.sha256(data).hexdigest(),
        "projection_sha256": hashlib.sha256(PROJECTION.read_bytes()).hexdigest(),
        "retrieval": {},
        "crosscheck": {},
        "a12_cp_within_bound": {},
        "literature": {},
    }
    failures = []
    for r in recs:
        cid = r["id"]
        out["retrieval"][cid] = _retrieve(r, mods, nasa, bib)
        if not all(out["retrieval"][cid]["equal"].values()):
            failures.append(cid)
        out["crosscheck"][cid] = _crosscheck(r, mods)
        if cid in NEW:
            dev = out["crosscheck"][cid]["cp_rel_dev_vs_coolprop_ideal_gas"]
            out["a12_cp_within_bound"][cid] = all(
                abs(dev[t]) <= A12_BOUND for t in A12_TEMPERATURES
            )
            out["literature"][cid] = _literature(r, literature[cid], out["crosscheck"][cid], mods)
    out["retrieval_all_equal"] = not failures
    out["retrieval_failures"] = failures
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--emit", action="store_true")
    args = ap.parse_args()
    missing = _missing_pins()
    if missing:
        print(
            f"SKIPPED: components-crosscheck.json not recomputed: source distributions absent or "
            f"off the pins {missing} (pins {PINS}; L01 spec section 4.1)",
        )
        return SKIPPED
    document = build()
    text = json.dumps(document, indent=1) + "\n"
    if args.emit:
        OUT.write_text(text, encoding="utf-8")
        print(
            "components-crosscheck.json written; retrieval_all_equal",
            document["retrieval_all_equal"],
        )
        return 0 if document["retrieval_all_equal"] else 1
    same = OUT.exists() and OUT.read_text(encoding="utf-8") == text
    print("components-crosscheck.json", "matches" if same else "DIFFERS")
    return 0 if same else 1


if __name__ == "__main__":
    raise SystemExit(main())
