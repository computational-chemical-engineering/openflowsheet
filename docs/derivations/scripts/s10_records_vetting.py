"""T08.A32's vetting of the S10 real records (S10 spec section 18, A5-1; R-722).

Normative text: ``docs/derivations/S10-spec.md`` section 18 A5-1. Output:
``benchmarks/s10/records-vetting.json``, the file T08.A32 (iv) reads for
``benchmarks/s10/records.yaml`` (``tests/test_t08_w2_inventory.py``, ``_s10_vetted``).

For each of the three records (CH3OH, C2H5OH, H2O) it evaluates twelve equalities, each against a
closed form of the committed inputs or a constant registered in A5-1, never against the generator
(``s10_records.py`` is not imported):

* ``name``, ``elemental_composition``, ``source_species``: the identity the record carries (no CAS
  RN, R-706) equals the registered one, the composition parsed from the NASA species name, and the
  species and fluid names under which the inputs were retrieved;
* ``no_identifiers``: the record carries no ``identifiers`` key (R-706; S10 spec section 9.1);
* ``parameter_keys_units``: exactly the ten registered parameters, each with its registered unit;
* ``molar_mass_ciaaw2021``: the molar mass equals sum(n_e A_e)/1000 with CIAAW 2021's conventional
  atomic weights, rounded once;
* ``nasa7_low_range_decimal``, ``nasa7_range_200_1000``, ``nasa7_note_quoted``: b_k equals
  a_(k+1) 1000^k, exactly in decimal and rounded once, from ``nasa7-low.json``; the range is
  NASA's low range and covers the records' domain; the provenance quotes the species and its note;
* ``formation_enthalpy_h298``: Delta_f H equals R (a1 T0 + ... + a5 T0^5/5 + a6), exactly in
  rationals and rounded once;
* ``vapour_pressure_within_claim``, ``vapour_pressure_source_quoted``: the stored a..d reproduce
  every committed CoolProp point within the fit claim |Delta ln P| <= 2e-3 (40-digit decimal
  arithmetic, so the result is the same on every machine); the provenance quotes the CoolProp
  version, the grid and the EOS key of that component.

``nasa7_retrieval`` re-reads Cantera 3.2.0's ``nasa_gas.yaml`` (as text, SHA-256 checked) and
compares every literal ``nasa7-low.json`` took from it. The generator also runs one negative
control per equality (section 18 A5-1's table) and refuses to emit unless each control turns
exactly its own equality false.

Run from the repository root::

    python docs/derivations/scripts/s10_records_vetting.py --check [--nasa-yaml PATH]
    python docs/derivations/scripts/s10_records_vetting.py --emit --nasa-yaml PATH

``--check`` exits 0 when the whole file is recomputed and equal, 1 when anything differs, and 2
when the part that needs no tool is equal but Cantera 3.2.0's ``nasa_gas.yaml`` is not available,
so ``nasa7_retrieval`` was not re-checked (never 0 without it; rule 5). ``--emit`` needs that file.
Dependencies: Python 3.11+ and PyYAML.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import re
import sys
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
S10 = ROOT / "benchmarks" / "s10"
RECORDS = S10 / "records.yaml"
NASA_JSON = S10 / "nasa7-low.json"
SAT_JSON = S10 / "saturation-points.json"
OUT_JSON = S10 / "records-vetting.json"

#: Cantera 3.2.0's nasa_gas.yaml, as recorded in rights row S10-RC-01.
NASA_SHA256 = "4de6199d65d2d3db782e30573720c723130953707336add59713b02d8667e4db"
#: R (exact in the 2019 SI) and T0, as in S10 spec section 3.1.
R_TEXT = "8.31446261815324"
R = Fraction(R_TEXT)
T0 = Fraction("298.15")
#: CIAAW 2021 conventional atomic weights, g/mol (S10 Q-N6 default; rights row S10-RC-08).
ATOMIC_WEIGHT = {"H": Decimal("1.008"), "C": Decimal("12.011"), "O": Decimal("15.999")}
#: The fit claim of S10 spec section 9.3 (assertion S10.A32), in ln P.
CLAIM = Decimal("2e-3")
#: The registered identities (S10 spec section 18 A5-1): id -> (name, composition, NASA species,
#: CoolProp fluid).
IDENTITY: dict[str, tuple[str, dict[str, int], str, str]] = {
    "CH3OH": ("methanol", {"C": 1, "H": 4, "O": 1}, "CH3OH", "Methanol"),
    "C2H5OH": ("ethanol", {"C": 2, "H": 6, "O": 1}, "C2H5OH", "Ethanol"),
    "H2O": ("water", {"H": 2, "O": 1}, "H2O", "Water"),
}
B_KEYS = tuple(f"ideal_gas_cp_b{k}" for k in range(5))
VP_KEYS = tuple(f"vapour_pressure_{c}" for c in "abcd")
#: The ten registered parameters and their units.
UNITS = {**dict.fromkeys(B_KEYS, "1"), "standard_formation_enthalpy": "J/mol"}
UNITS |= dict.fromkeys(VP_KEYS, "1")
FLAGS = (
    "name",
    "elemental_composition",
    "source_species",
    "no_identifiers",
    "parameter_keys_units",
    "molar_mass_ciaaw2021",
    "nasa7_low_range_decimal",
    "nasa7_range_200_1000",
    "nasa7_note_quoted",
    "formation_enthalpy_h298",
    "vapour_pressure_within_claim",
    "vapour_pressure_source_quoted",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def formula(name: str) -> dict[str, int]:
    """Element counts of a Hill-free formula string such as ``C2H5OH``."""
    counts: dict[str, int] = {}
    for element, n in re.findall(r"([A-Z][a-z]?)(\d*)", name):
        counts[element] = counts.get(element, 0) + (int(n) if n else 1)
    return counts


def worst_dlnp(params: dict[str, Any], points: list[list[float]]) -> Decimal:
    """max |ln P_fit(T) - ln P| over the points, theta = T/1000 K, in 40-digit decimal."""
    with localcontext() as ctx:
        ctx.prec = 40
        a, b, c, d = (Decimal(params[k]["value"]) for k in VP_KEYS)
        worst = Decimal(0)
        for t, p in points:
            theta = Decimal(t) / 1000
            fit = a + b / theta + c * theta.ln() + d * theta * theta
            worst = max(worst, abs(fit - Decimal(p).ln()))
        return worst


def vet_one(
    record: dict[str, Any], nasa: dict[str, Any], sat: dict[str, Any], domain_t: list[float]
) -> tuple[dict[str, bool], Decimal]:
    cid = record["id"]
    name, composition, nasa_name, fluid = IDENTITY[cid]
    entry = next(s for s in nasa["species"] if s["id"] == cid)
    comp = next(c for c in sat["components"] if c["id"] == cid)
    params = record["parameters"]
    a = entry["low_range_a1_a7"]
    if not set(UNITS) <= set(params):
        return dict.fromkeys(FLAGS, False), Decimal(0)  # a missing parameter fails every equality
    worst = worst_dlnp(params, comp["points_T_K_P_Pa"])
    mw = float(sum(ATOMIC_WEIGHT[e] * n for e, n in composition.items()) / 1000)
    h298 = R * (
        Fraction(a[0]) * T0
        + Fraction(a[1]) * T0**2 / 2
        + Fraction(a[2]) * T0**3 / 3
        + Fraction(a[3]) * T0**4 / 4
        + Fraction(a[4]) * T0**5 / 5
        + Fraction(a[5])
    )
    note = f"{entry['nasa_species']} low range (note {entry['note']})"
    grid = sat["grid_T_K"]
    vp_quote = (
        f"CoolProp {sat['coolprop']['version']} saturation pressures, {grid['first']}-"
        f"{grid['last']} K, {grid['count']} points; EOS {comp['eos_bibtex_key']}"
    )
    flags = {
        "name": record["name"] == name,
        "elemental_composition": record["elemental_composition"] == composition
        and formula(entry["nasa_species"]) == composition,
        "source_species": entry["nasa_species"] == nasa_name and comp["coolprop_fluid"] == fluid,
        "no_identifiers": "identifiers" not in record,
        "parameter_keys_units": set(params) == set(UNITS)
        and all(params[k]["unit"] == u for k, u in UNITS.items()),
        "molar_mass_ciaaw2021": record["molecular_weight"]["value"] == mw
        and record["molecular_weight"]["unit"] == "kg/mol",
        "nasa7_low_range_decimal": all(
            params[key]["value"] == float(Decimal(a[k]) * Decimal(1000) ** k)
            for k, key in enumerate(B_KEYS)
        ),
        "nasa7_range_200_1000": entry["temperature_ranges_K"] == ["200.0", "1000.0", "6000.0"]
        and 200.0 <= domain_t[0] < domain_t[1] <= 1000.0,
        "nasa7_note_quoted": all(
            "NASA TM-4513" in params[k]["provenance"] and note in params[k]["provenance"]
            for k in (*B_KEYS, "standard_formation_enthalpy")
        ),
        "formation_enthalpy_h298": params["standard_formation_enthalpy"]["value"] == float(h298),
        "vapour_pressure_within_claim": worst <= CLAIM,
        "vapour_pressure_source_quoted": all(vp_quote in params[k]["provenance"] for k in VP_KEYS),
    }
    return flags, worst


def vet(records: dict[str, Any], nasa: dict[str, Any], sat: dict[str, Any]) -> dict[str, Any]:
    """The tool-free part: one equality block per record, in the records' order."""
    out: dict[str, Any] = {}
    for record in records["components"]:
        flags, worst = vet_one(record, nasa, sat, records["domain"]["T"])
        out[record["id"]] = {"equal": flags, "worst_abs_dlnP": float(format(worst, ".4g"))}
    return out


def nasa_retrieval(path: Path, nasa: dict[str, Any]) -> dict[str, Any] | str:
    """Every literal nasa7-low.json took from Cantera 3.2.0's file, re-read; or why not."""
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != NASA_SHA256:
        return f"{path}: SHA-256 {digest} is not the vetted {NASA_SHA256}"
    species = {s["name"]: s for s in yaml.load(raw, Loader=yaml.BaseLoader)["species"]}
    equal = {}
    for entry in nasa["species"]:
        _, composition, nasa_name, _ = IDENTITY[entry["id"]]
        s = species.get(entry["nasa_species"])
        equal[entry["id"]] = bool(
            s is not None
            and entry["nasa_species"] == nasa_name
            and s["thermo"]["model"] == "NASA7"
            and s["thermo"]["temperature-ranges"] == entry["temperature_ranges_K"]
            and s["thermo"]["data"][0] == entry["low_range_a1_a7"]
            and s["thermo"].get("note", "") == entry["note"]
            and {k: int(v) for k, v in s["composition"].items()} == composition
        )
    return {
        "source_file": "cantera/data/nasa_gas.yaml (Cantera 3.2.0)",
        "source_sha256": digest,
        "compared": "low-range a1..a7 literals, temperature ranges, note, composition",
        "equal": equal,
    }


# --------------------------------------------------------------------------- negative controls


def _nudge(record: dict[str, Any], key: str) -> None:
    value = record["parameters"][key]["value"]
    record["parameters"][key]["value"] = math.nextafter(value, math.inf)


def _controls() -> list[tuple[str, Any]]:
    """One mutation per equality (S10 spec section 18 A5-1); each must turn exactly its flag."""

    def species_note(r: dict[str, Any], n: dict[str, Any], s: dict[str, Any]) -> None:
        p = r["parameters"]["ideal_gas_cp_b0"]
        p["provenance"] = p["provenance"].replace("(note L 8/8", "(note L 9/8")

    def eos_key(r: dict[str, Any], n: dict[str, Any], s: dict[str, Any]) -> None:
        p = r["parameters"]["vapour_pressure_a"]
        p["provenance"] = p["provenance"].replace("; EOS ", "; EOS x")

    def fluid(r: dict[str, Any], n: dict[str, Any], s: dict[str, Any]) -> None:
        next(c for c in s["components"] if c["id"] == r["id"])["coolprop_fluid"] = "Propane"

    def nasa_range(r: dict[str, Any], n: dict[str, Any], s: dict[str, Any]) -> None:
        next(e for e in n["species"] if e["id"] == r["id"])["temperature_ranges_K"][1] = "1500.0"

    def b_coefficient(r: dict[str, Any], n: dict[str, Any], s: dict[str, Any]) -> None:
        _nudge(r, "ideal_gas_cp_b0")

    def formation(r: dict[str, Any], n: dict[str, Any], s: dict[str, Any]) -> None:
        _nudge(r, "standard_formation_enthalpy")

    def molar_mass(r: dict[str, Any], n: dict[str, Any], s: dict[str, Any]) -> None:
        r["molecular_weight"]["value"] = math.nextafter(r["molecular_weight"]["value"], 0.0)

    def identifiers(r: dict[str, Any], n: dict[str, Any], s: dict[str, Any]) -> None:
        r["identifiers"] = {"formula": r["id"]}

    def vp_b(r: dict[str, Any], n: dict[str, Any], s: dict[str, Any]) -> None:
        r["parameters"]["vapour_pressure_b"]["value"] *= 1.001

    def name(r: dict[str, Any], n: dict[str, Any], s: dict[str, Any]) -> None:
        r["name"] = r["name"].upper()

    def composition(r: dict[str, Any], n: dict[str, Any], s: dict[str, Any]) -> None:
        r["elemental_composition"] = {**r["elemental_composition"], "H": 1}

    def extra_parameter(r: dict[str, Any], n: dict[str, Any], s: dict[str, Any]) -> None:
        r["parameters"]["vapour_pressure_e"] = copy.deepcopy(r["parameters"]["vapour_pressure_d"])

    return [
        ("name", name),
        ("elemental_composition", composition),
        ("source_species", fluid),
        ("no_identifiers", identifiers),
        ("parameter_keys_units", extra_parameter),
        ("molar_mass_ciaaw2021", molar_mass),
        ("nasa7_low_range_decimal", b_coefficient),
        ("nasa7_range_200_1000", nasa_range),
        ("nasa7_note_quoted", species_note),
        ("formation_enthalpy_h298", formation),
        ("vapour_pressure_within_claim", vp_b),
        ("vapour_pressure_source_quoted", eos_key),
    ]


def control_problems(
    records: dict[str, Any], nasa: dict[str, Any], sat: dict[str, Any]
) -> list[str]:
    """Empty when every control, applied to every record, turns exactly its own flag false."""
    problems = []
    base = vet(records, nasa, sat)
    controls = _controls()
    if [flag for flag, _ in controls] != list(FLAGS):
        problems.append("the controls do not cover the equalities one to one")
    for flag, mutate in controls:
        for index, record in enumerate(records["components"]):
            r, n, s = copy.deepcopy(records), copy.deepcopy(nasa), copy.deepcopy(sat)
            mutate(r["components"][index], n, s)
            got = vet(r, n, s)
            for cid, block in got.items():
                false = {f for f, ok in block["equal"].items() if not ok}
                want = {f for f, ok in base[cid]["equal"].items() if not ok}
                if cid == record["id"]:
                    want = want | {flag}
                if false != want:
                    got_false = sorted(false)
                    problems.append(f"control {flag} on {record['id']}: {cid} false {got_false}")
    return problems


# --------------------------------------------------------------------------------------- main


def document(retrieval: dict[str, Any]) -> dict[str, Any]:
    records = yaml.safe_load(RECORDS.read_text(encoding="utf-8"))
    nasa = json.loads(NASA_JSON.read_text(encoding="utf-8"))
    sat = json.loads(SAT_JSON.read_text(encoding="utf-8"))
    blocks = vet(records, nasa, sat)
    failures = [f"{cid}.{f}" for cid, b in blocks.items() for f, ok in b["equal"].items() if not ok]
    return {
        "schema_version": 1,
        "what": "T08.A32 (iv) for benchmarks/s10/records.yaml: twelve equalities per record "
        "against closed forms of the committed inputs and constants registered in S10 spec "
        "section 18 A5-1, and the NASA-7 literals re-read from Cantera 3.2.0's file. Vetting of "
        "these bytes; it decides no rights question and no shipping (Q-F3).",
        "generator": "docs/derivations/scripts/s10_records_vetting.py",
        "specification": "docs/derivations/S10-spec.md section 18 A5-1 (R-722)",
        "records_sha256": sha256(RECORDS),
        "inputs_sha256": {
            "benchmarks/s10/nasa7-low.json": sha256(NASA_JSON),
            "benchmarks/s10/saturation-points.json": sha256(SAT_JSON),
        },
        "constants": {
            "R_J_per_mol_K": R_TEXT,
            "T0_K": "298.15",
            "atomic_weights_g_per_mol": {k: str(v) for k, v in ATOMIC_WEIGHT.items()},
            "vapour_pressure_claim_abs_dlnP": str(CLAIM),
        },
        "retrieval": blocks,
        "retrieval_all_equal": not failures,
        "retrieval_failures": failures,
        "nasa7_retrieval": retrieval,
    }


def dump(doc: dict[str, Any]) -> str:
    return json.dumps(doc, indent=1) + "\n"


def nasa_path(given: Path | None) -> Path | None:
    if given is not None:
        return given
    spec = importlib.util.find_spec("cantera")
    if spec is None or spec.origin is None:
        return None
    path = Path(spec.origin).parent / "data" / "nasa_gas.yaml"
    return path if path.is_file() else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--emit", action="store_true")
    ap.add_argument("--nasa-yaml", type=Path, default=None)
    args = ap.parse_args()
    records = yaml.safe_load(RECORDS.read_text(encoding="utf-8"))
    nasa = json.loads(NASA_JSON.read_text(encoding="utf-8"))
    sat = json.loads(SAT_JSON.read_text(encoding="utf-8"))
    problems = control_problems(records, nasa, sat)
    if problems:
        print("refused: a negative control does not turn exactly its equality false")
        print("\n".join(problems[:10]))
        return 1
    path = nasa_path(args.nasa_yaml)
    retrieval: dict[str, Any] | str = "Cantera 3.2.0's nasa_gas.yaml is not available"
    if path is not None:
        retrieval = nasa_retrieval(path, nasa)
    if args.emit:
        if isinstance(retrieval, str):
            print(f"UNAVAILABLE: {retrieval}; pass --nasa-yaml")
            return 2
        doc = document(retrieval)
        OUT_JSON.write_text(dump(doc), encoding="utf-8")
        print(
            f"wrote {OUT_JSON.relative_to(ROOT)}; retrieval_all_equal "
            f"{doc['retrieval_all_equal']}; {len(FLAGS)} controls hold"
        )
        return 0
    if not OUT_JSON.exists():
        print(f"DIFFERS: {OUT_JSON.relative_to(ROOT)} is absent")
        return 1
    committed = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    if isinstance(retrieval, str):
        doc = document(committed.get("nasa7_retrieval", {}))
        if dump(doc) != OUT_JSON.read_text(encoding="utf-8"):
            print("DIFFERS: records-vetting.json's tool-free part does not reproduce")
            return 1
        print(
            "PARTIAL: records-vetting.json's tool-free part matches; nasa7_retrieval not "
            f"re-checked ({retrieval})"
        )
        return 2
    ok = dump(document(retrieval)) == OUT_JSON.read_text(encoding="utf-8")
    print(f"{len(FLAGS)} controls hold; records-vetting.json {'matches' if ok else 'DIFFERS'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
