"""L01: component dispositions and the development-half coverage projection (L01 spec §3, §6, §7).

Normative text: `docs/derivations/L01-spec.md`. Inputs are committed files only (no archive, no
network): the C2 split, W27's `case_facts.json`, `coverage.json` (its `snapshot` member and the
rows of development ids only) and `registration.json`, and the C1 records (molar-mass anchors).

Held-out protection (C2 SPLIT-R08…R11): every all-case file is filtered to the development ids
*before* anything is counted, classified or printed. No held-out id, count or name is read into
the output, and no message prints one. W27's committed records are read, never written.

Run (repository root):
    PYTHONPATH=src python docs/derivations/scripts/l01_projection.py --emit
    PYTHONPATH=src python docs/derivations/scripts/l01_projection.py --check

`--check` regenerates in memory and compares byte for byte with the committed record. A failed
self-claim (L01 spec §7.1, SC-1…SC-12) refuses: exit 2, nothing written.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from benchmarks.m06.w27 import coverage, registration  # noqa: E402

OUT = Path(__file__).with_suffix(".json")
DATA = ROOT / "benchmarks/m06/openidaes450"
C1_RECORDS = ROOT / "benchmarks/m01/components.yaml"
SCHEMA = "l01-projection-v1"

#: chemicals 1.5.2's standard atomic weights (IUPAC as tabulated there). SC-4 shows H, C, N and
#: Ar reproduce the C1 records' molar masses exactly; O is the same table's value.
ATOMIC_WEIGHTS = {
    "H": Decimal("1.00794"),
    "C": Decimal("12.0107"),
    "N": Decimal("14.0067"),
    "O": Decimal("15.9994"),
    "Ar": Decimal("39.948"),
}
C1_ELEMENTS = {
    "H2": {"H": 2},
    "N2": {"N": 2},
    "NH3": {"N": 1, "H": 3},
    "Ar": {"Ar": 1},
    "CH4": {"C": 1, "H": 4},
}

#: The library's new records (spec §4.1): id, name, Hill formula, CAS RN, elements. All vapour.
NEW = (
    ("H2O", "water", "H2O", "7732-18-5", {"H": 2, "O": 1}),
    ("CO2", "carbon dioxide", "CO2", "124-38-9", {"C": 1, "O": 2}),
    ("O2", "oxygen", "O2", "7782-44-7", {"O": 2}),
    ("C2H6", "ethane", "C2H6", "74-84-0", {"C": 2, "H": 6}),
    ("C3H8", "propane", "C3H8", "74-98-6", {"C": 3, "H": 8}),
)
#: Servable by rule R-A but stopped (spec §3.2): the record cannot enter any snapshot W27 judges.
BLOCKED = {
    "630-08-0": (
        "CO",
        "carbon monoxide",
        "CO",
        "W27-R24 (c): the archive spelling 'Co' (cobalt) casefolds to the record's 'CO'",
    ),
}
#: The C1 records the library copies verbatim (vapour-only in C1 too); NH3 is not copied.
COPIED = ("H2", "N2", "Ar", "CH4")

#: Literature expectations (spec §5.2), each with its citation. T_c / K, P_c / Pa, omega,
#: dHf / (J/mol) ideal gas 298.15 K, cp / (J/(mol K)) ideal gas 298.15 K.
LITERATURE = {
    "H2O": {
        "Tc": "647.096",
        "Pc": "22064000",
        "omega": "0.3443",
        "dHf": "-241826",
        "cp298": "33.59",
        "src": "IAPWS-95 (Wagner and Pruss, JPCRD 31 (2002) 387) critical point; CODATA key "
        "values (Cox, Wagman, Medvedev 1989) dHf; JANAF 4th ed. (Chase 1998) cp",
    },
    "CO2": {
        "Tc": "304.1282",
        "Pc": "7377300",
        "omega": "0.22394",
        "dHf": "-393510",
        "cp298": "37.129",
        "src": "Span and Wagner, JPCRD 25 (1996) 1509 critical point; CODATA key values dHf; "
        "JANAF 4th ed. cp",
    },
    "O2": {
        "Tc": "154.581",
        "Pc": "5043000",
        "omega": "0.0222",
        "dHf": "0",
        "cp298": "29.376",
        "src": "Schmidt and Wagner, Fluid Phase Equilib. 19 (1985) 175 critical point; element "
        "in its reference state (dHf = 0 by definition); JANAF 4th ed. cp",
    },
    "C2H6": {
        "Tc": "305.322",
        "Pc": "4872200",
        "omega": "0.0995",
        "dHf": "-83800",
        "cp298": "52.49",
        "src": "Buecker and Wagner, JPCRD 35 (2006) 205 critical point; Pittam and Pilcher "
        "(1972) dHf; Chao, Wilhoit and Hall (1973) cp",
    },
    "C3H8": {
        "Tc": "369.89",
        "Pc": "4251200",
        "omega": "0.1521",
        "dHf": "-104700",
        "cp298": "73.60",
        "src": "Lemmon, McLinden and Wagner, J. Chem. Eng. Data 54 (2009) 3141 critical "
        "point; Prosen and Rossini (1945) dHf; Chao, Wilhoit and Hall (1973) cp",
    },
}
#: Tolerances of L01.A07-A11 (spec §5.2 gives each one's floor and catch argument).
TOLERANCE = {
    "Tc_K": "0.01",
    "Pc_rel": "0.001",
    "omega_abs": "0.003",
    "dHf_inorganic_J": "250",
    "dHf_hydrocarbon_J": "600",
    "cp_inorganic_rel": "0.005",
    "cp_hydrocarbon_rel": "0.01",
}

LIBRARY_PROVIDER = "pr-lib-v1"
C1_PROVIDER = "pr-c1-v1"


class SelfClaimError(Exception):
    """A self-claim of spec §7.1 failed; nothing is emitted."""


def claim(ok: bool, text: str) -> None:
    if not ok:
        raise SelfClaimError(text)


def cas_valid(cas: str) -> bool:
    """CAS RN check digit: sum of digit_i * i over the body read right to left, mod 10."""
    body, check = cas.rsplit("-", 1)
    digits = body.replace("-", "")
    total = sum(int(d) * i for i, d in enumerate(reversed(digits), start=1))
    return total % 10 == int(check)


def molar_mass(elements: dict[str, int]) -> Decimal:
    """kg/mol, exact in decimal from `ATOMIC_WEIGHTS` (g/mol) / 1000."""
    return sum(ATOMIC_WEIGHTS[e] * n for e, n in elements.items()) / 1000


def load_inputs() -> tuple[list[str], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    dev = list(json.loads((DATA / "split.json").read_bytes())["development"]["case_ids"])
    keep = set(dev)
    cases = [
        c
        for c in json.loads((DATA / "case_facts.json").read_bytes())["cases"]
        if c["case_id"] in keep
    ]
    cov = json.loads((DATA / "coverage.json").read_bytes())
    committed = {r["case_id"]: r for r in cov["rows"] if r["case_id"] in keep}
    return dev, cases, committed, cov["snapshot"]


def library_rows() -> list[dict[str, Any]]:
    return [
        {
            "cas": cas,
            "formula": formula,
            "id": cid,
            "name": name,
            "phases": ["vapor"],
            "synthetic": False,
        }
        for cid, name, formula, cas, _ in NEW
    ]


def route(snapshot: dict[str, Any], provider: str) -> dict[str, Any]:
    (found,) = [r for r in snapshot["routes"] if r["provider_id"] == provider]
    return found


def classify_all(
    cases: list[dict[str, Any]], snapshot: dict[str, Any], methods: dict[str, str]
) -> dict[str, dict[str, Any]]:
    coverage.check_snapshot(snapshot, {"cases": cases}, methods)
    return {c["case_id"]: coverage.classify_case(c, snapshot, methods) for c in cases}


def tally(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    order = registration.classes()
    classes = Counter(r["class"] for r in rows.values())
    comps: Counter[str] = Counter()
    for r in rows.values():
        for x in r["reasons"]:
            if x["kind"] == "COMPONENT_UNAVAILABLE":
                comps[str(x["subject"])] += 1
    kinds = Counter(x["kind"] for r in rows.values() for x in r["reasons"])
    return {
        "classes": {k: classes.get(k, 0) for k in order},
        "reason_kinds": dict(sorted(kinds.items())),
        "component_reasons_by_subject": dict(sorted(comps.items())),
    }


def dispositions(
    cases: list[dict[str, Any]], rows: dict[str, dict[str, Any]], admitted: set[str]
) -> list[dict[str, Any]]:
    """Spec §3: per unavailable chemical (by CAS), development cases, method groups, and the
    admission rule R-A (some case whose non-reaction packages are all `cubic_pr`, every one
    declaring phases within {vapor}, lists it)."""
    facts = {c["case_id"]: c for c in cases}
    per: dict[str, dict[str, Any]] = {}
    for cid, row in sorted(rows.items()):
        pkgs = [p for p in row["packages"] if p["method"] != "reaction"]
        group = tuple(sorted({p["method"] for p in pkgs}))
        phases = {p["name"]: set(p["phases"]) for p in facts[cid]["packages"]}
        vapour_pr = group == ("cubic_pr",) and all(phases[p["name"]] <= {"vapor"} for p in pkgs)
        seen: set[str] = set()
        for comp in row["components"]:
            if comp["class"] != "chemical" or comp["available"] or comp["cas"] in seen:
                continue
            seen.add(comp["cas"])
            entry = per.setdefault(
                comp["cas"],
                {
                    "cas": comp["cas"],
                    "names": set(),
                    "cases": 0,
                    "groups": Counter(),
                    "vapour_pr_cases": [],
                },
            )
            entry["cases"] += 1
            entry["groups"]["+".join(group) or "none"] += 1
            if vapour_pr:
                entry["vapour_pr_cases"].append(cid)
        for comp in row["components"]:
            if comp["class"] == "chemical" and not comp["available"]:
                per[comp["cas"]]["names"].add(comp["name"])
    out = []
    for e in sorted(per.values(), key=lambda e: (-e["cases"], e["cas"])):
        methods = sorted({m for g in e["groups"] for m in g.split("+")} - {"none"})
        served = bool(e["vapour_pr_cases"])
        blocked = BLOCKED.get(e["cas"])
        out.append(
            {
                "cas": e["cas"],
                "names": sorted(e["names"]),
                "development_cases": e["cases"],
                "method_groups": dict(sorted(e["groups"].items())),
                "methods": methods,
                "vapour_pr_cases": e["vapour_pr_cases"],
                "disposition": (
                    "stopped: " + blocked[3]
                    if blocked
                    else "admit: cubic_pr vapour (pr-lib-v1)"
                    if served
                    else "needs new method: "
                    + ", ".join(m for m in methods if m != "cubic_pr")
                    + ("; cubic_pr only beside other methods" if "cubic_pr" in methods else "")
                ),
            }
        )
        claim(
            served == (e["cas"] in admitted or blocked is not None),
            f"SC-6: admission rule and the registered library disagree on {e['cas']}",
        )
    return out


def build() -> dict[str, Any]:
    dev, cases, committed, snapshot = load_inputs()
    # SC-1: the development half is the registered 225, every id has facts and a committed row.
    claim(len(dev) == 225 == len(set(dev)), "SC-1: development ids are not 225 distinct")
    claim(
        {c["case_id"] for c in cases} == set(dev) == set(committed),
        "SC-1: a development id lacks facts or a committed coverage row",
    )
    methods = registration.provider_methods()
    before = classify_all(cases, snapshot, methods)
    # SC-2: W27's classifier at the committed snapshot reproduces the committed development rows.
    claim(
        all(before[k] == committed[k] for k in committed),
        "SC-2: re-classification differs from committed development rows",
    )
    t_before = tally(before)
    # SC-3: the brief's development tally (UNIT 184, NOT_STEADY 32, COMPONENT 9).
    claim(
        t_before["classes"]
        == {
            "ARTIFACT_INCOMPLETE": 0,
            "NOT_STEADY_STATE_SIMULATION": 32,
            "UNIT_UNAVAILABLE": 184,
            "COMPONENT_UNAVAILABLE": 9,
            "PROPERTY_ROUTE_UNAVAILABLE": 0,
            "CANDIDATE": 0,
        },
        f"SC-3: development tally {t_before['classes']}",
    )
    # SC-4: CAS check digits; molar masses; the atomic weights reproduce the C1 records.
    c1 = {r["id"]: r for r in yaml.safe_load(C1_RECORDS.read_bytes())["components"]}
    for cid, elements in C1_ELEMENTS.items():
        claim(
            Decimal(str(c1[cid]["molecular_weight"]["value"])) == molar_mass(elements),
            f"SC-4: atomic weights do not reproduce C1 {cid}",
        )
    claim(
        all(cas_valid(cas) for *_, cas, _ in NEW)
        and all(cas_valid(c1[c]["identifiers"]["cas"]) for c in COPIED),
        "SC-4: a CAS check digit fails",
    )
    # SC-5: a corrupted CAS fails the check (the check is not vacuous).
    claim(not cas_valid("7732-18-6") and not cas_valid("124-38-8"), "SC-5: vacuous CAS check")
    aliases = registration.load()["components"]["aliases"]
    claim(
        all(aliases.get(cid) == cas for cid, _, _, cas, _ in NEW),
        "SC-7: a library id is not W27-aliased to its CAS",
    )
    # Dispositions (§3), admission rule R-A (SC-6 inside).
    admitted = {cas for *_, cas, _ in NEW}
    disp = dispositions(cases, before, admitted)
    # The projection snapshot: the one cubic_pr route admits the new records vapour-only.
    after_snap = copy.deepcopy(snapshot)
    route(after_snap, C1_PROVIDER)["components"].extend(library_rows())
    after = classify_all(cases, after_snap, methods)  # SC-7: spellings pass W27-R24 (c)
    t_after = tally(after)
    order = registration.classes()
    transitions = []
    for cid in sorted(dev):
        b, a = before[cid], after[cid]
        # SC-8: precedence never worsens; no reason other than a COMPONENT one disappears.
        claim(order.index(a["class"]) >= order.index(b["class"]), f"SC-8: {cid} worsens")
        gone = [x for x in b["reasons"] if x not in a["reasons"]]
        new = [x for x in a["reasons"] if x not in b["reasons"]]
        claim(all(x["kind"] == "COMPONENT_UNAVAILABLE" for x in gone), f"SC-8: {cid}")
        if gone or new or a["class"] != b["class"]:
            transitions.append(
                {
                    "case_id": cid,
                    "class_before": b["class"],
                    "class_after": a["class"],
                    "component_reasons_removed": sorted(str(x["subject"]) for x in gone),
                    "reasons_added": sorted(
                        f"{x['kind']}:{x['subject']}:{x['detail']}" for x in new
                    ),
                }
            )
    # SC-9: no development case becomes CANDIDATE; every case whose cubic_pr package is served
    # with a library component keeps a UNIT reason (so its class does not depend on which
    # route's models judge its units, W27-R62).
    claim(t_after["classes"]["CANDIDATE"] == 0, "SC-9: a development case becomes CANDIDATE")
    lib_cas = {cas for *_, cas, _ in NEW}
    for cid, a in after.items():
        served = any(p["method"] == "cubic_pr" and p["available"] for p in a["packages"])
        uses_lib = any(c["cas"] in lib_cas for c in a["components"])
        if served and uses_lib:
            claim(
                any(x["kind"] == "UNIT_UNAVAILABLE" for x in a["reasons"]),
                f"SC-9: {cid} has no UNIT reason",
            )
    # SC-10: the registered projected tally (spec §6.3).
    claim(
        t_after["classes"]
        == {
            "ARTIFACT_INCOMPLETE": 0,
            "NOT_STEADY_STATE_SIMULATION": 32,
            "UNIT_UNAVAILABLE": 184,
            "COMPONENT_UNAVAILABLE": 6,
            "PROPERTY_ROUTE_UNAVAILABLE": 3,
            "CANDIDATE": 0,
        },
        f"SC-10: projected tally {t_after['classes']}",
    )
    # SC-11: the real two-route build is refused by W27 as registered (W27-R24 (a), (d)).
    two = copy.deepcopy(snapshot)
    c1_rows = [r for r in route(two, C1_PROVIDER)["components"] if r["id"] in COPIED]
    two["routes"].append(
        {
            "provider_id": LIBRARY_PROVIDER,
            "model_ids": [],
            "components": [*c1_rows, *library_rows()],
        }
    )
    refusals = []
    for table in (methods, {**methods, LIBRARY_PROVIDER: "cubic_pr"}):
        try:
            coverage.check_snapshot(two, {"cases": cases}, table)
            refusals.append(None)
        except coverage.RefusalError as refusal:
            refusals.append(str(refusal))
    claim(
        refusals[0] is not None
        and f"unregistered provider ids ['{LIBRARY_PROVIDER}']" in refusals[0],
        f"SC-11: unregistered provider not refused: {refusals[0]}",
    )
    claim(
        refusals[1] is not None and "routes sharing a method ['cubic_pr']" in refusals[1],
        f"SC-11: shared method not refused: {refusals[1]}",
    )
    # SC-13: the stopped records are refused by W27-R24 (c) exactly as registered in BLOCKED.
    for cas, (cid, name, formula, _why) in sorted(BLOCKED.items()):
        trial = copy.deepcopy(after_snap)
        route(trial, C1_PROVIDER)["components"].append(
            {
                "cas": cas,
                "formula": formula,
                "id": cid,
                "name": name,
                "phases": ["vapor"],
                "synthetic": False,
            }
        )
        try:
            coverage.check_snapshot(trial, {"cases": cases}, methods)
            refused = ""
        except coverage.RefusalError as refusal:
            refused = str(refusal)
        claim(f"not aliased ['Co->{cas}']" in refused, f"SC-13: {cid} not refused as registered")
    # SC-12: the literature table covers exactly the new records.
    claim(set(LITERATURE) == {cid for cid, *_ in NEW}, "SC-12: literature table incomplete")
    return {
        "schema": SCHEMA,
        "scope": "development half only (C2 split, 225 ids); no held-out row is read",
        "inputs": {
            p: registration.sha256_file(DATA / p)
            for p in ("split.json", "case_facts.json", "coverage.json", "registration.json")
        }
        | {"benchmarks/m01/components.yaml": registration.sha256_file(C1_RECORDS)},
        "library": {
            "provider_id": LIBRARY_PROVIDER,
            "copied_from_c1": list(COPIED),
            "new": [
                {
                    "id": cid,
                    "name": name,
                    "formula": f,
                    "cas": cas,
                    "elements": el,
                    "molar_mass_kg_per_mol": str(molar_mass(el)),
                    "phases": ["vapor"],
                }
                for cid, name, f, cas, el in NEW
            ],
            "stopped": {cas: v[3] for cas, v in BLOCKED.items()},
            "atomic_weights_g_per_mol": {k: str(v) for k, v in ATOMIC_WEIGHTS.items()},
        },
        "literature": LITERATURE,
        "tolerance": TOLERANCE,
        "dispositions": disp,
        "before": t_before,
        "projection": {
            "reading": "hypothetical: the new records admitted vapour-only by the one cubic_pr "
            "route (pr-c1-v1's route in the 0.2.0 snapshot); W27-R62 unit reasons of "
            "served cases are not projected",
            "after": t_after,
            "transitions": transitions,
        },
        "two_route_refusals": refusals,
    }


def render(document: dict[str, Any]) -> bytes:
    return registration.dump(document)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--emit", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        data = render(build())
    except (SelfClaimError, coverage.RefusalError) as refusal:
        print(f"REFUSED: {refusal}", file=sys.stderr)
        return 2
    if args.emit:
        OUT.write_bytes(data)
        print(f"wrote {OUT.relative_to(ROOT)}")
        return 0
    if OUT.read_bytes() != data:
        print(f"MISMATCH: {OUT.relative_to(ROOT)} differs from regeneration", file=sys.stderr)
        return 1
    print(f"OK: {OUT.relative_to(ROOT)} reproduces byte for byte")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
