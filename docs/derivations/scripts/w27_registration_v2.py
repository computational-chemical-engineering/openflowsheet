"""W27 registration version 2 (the next release): tables, registered states and self-claims.

Normative text: `docs/derivations/W27-registration-v2.md` (C9). Version 1 is v0.2's registration
(`docs/derivations/M06-W27-registration.md` with Amendments 1-4); this script never writes any of
its files and refuses (GC-V2-1) when one of them is not byte-identical to its v0.2 pin.

Inputs: committed files only (no archive, no network). The C2 split, W27's `case_facts.json` and
`coverage.json` (its `snapshot` member and the rows of development ids only), `registration.json`,
the C1 and L01 record files. Held-out protection (C2 SPLIT-R08...R11): every all-case file is
filtered to the development ids before anything is classified, counted or printed.

The reference functions below implement the v2 deltas (serving rule, refusals) on top of v1's
tested pieces. They are not the production classifier: the build lane implements v2 in
`benchmarks/m06/w27/coverage.py` (work order WO-C9-1) and its tests compare that code with the
registered states this script emits. The states' expected outcomes are written by hand (doc §5) and
this script refuses to emit unless its reference reproduces them and every registered mutant fails.

Run (repository root, PYTHONPATH=src):
    python docs/derivations/scripts/w27_registration_v2.py --emit
    python docs/derivations/scripts/w27_registration_v2.py --check
`--emit` writes the JSON and the generated blocks of the document. `--check` regenerates both in
memory and compares byte for byte. A failed self-claim exits 2 and writes nothing.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from benchmarks.m06.w27 import coverage, registration  # noqa: E402

DATA = ROOT / "benchmarks/m06/openidaes450"
OUT = DATA / "registration_v2.json"
DOC = ROOT / "docs/derivations/W27-registration-v2.md"
C1_RECORDS = ROOT / "benchmarks/m01/components.yaml"
LIB_RECORDS = ROOT / "benchmarks/l01/components.yaml"
SCHEMA = "w27-registration-v2"

#: GC-V2-1: v0.2's registered files (preflight P2, `benchmarks/m06/w27/preflight.py:57-65`).
BASE_PINS = {
    "benchmarks/m06/openidaes450/registration.json": (
        "ee099a60f9da6900325f54127f92e9eee926d2015f97b527843db482d6f0e52e"
    ),
    "docs/derivations/M06-W27-registration.md": (
        "bf48a5212cb0f17675567a8194e61d1f5b6665a082c0c3916a341d7d93260c70"
    ),
    "docs/derivations/scripts/m06_w27_registration.py": (
        "3d7429a258fca0bc92af4a3e4113af7f4ef62cd2b1cd8e4999e9c8f6eb9241eb"
    ),
}

#: W27v2-R02: the provider rows v2 adds to W27-R19's table.
PROVIDER_ADD = {"pr-lib-v1": "cubic_pr"}
#: W27v2-R03: the snapshot line for the added provider (W27-R63's per-provider lines).
PROVIDER_LINES = {
    "pr-lib-v1": {
        "records": "benchmarks/l01/components.yaml (openflowsheet.thermo.pr_lib.RECORDS_PATH)",
        "phases": "vapor for every component",
    }
}
#: W27v2-R08: reviewed case-only spellings, each distinct from the listed registry CAS RNs.
CASE_DISTINCT = {
    "Co": {
        "distinct_from": ["630-08-0"],
        "reading": "cobalt (element symbol; the PrOMMIS nanofiltration solute declared beside Li "
        "and Cl), not carbon monoxide (CO, 630-08-0)",
        "evidence": [
            "blind_synthesized_prommis_membrane_cascade_flowsheet",
            "blind_synthesized_prommis_nanofiltration_membrane_schematic",
        ],
    }
}
CO_RECORD = {
    "cas": "630-08-0",
    "formula": "CO",
    "id": "CO",
    "name": "carbon monoxide",
    "phases": ["vapor"],
    "synthetic": False,
}
C1_MODELS = sorted(m for m in registration.load()["units"]["model_functions"] if m[:3] == "c1.")
C1_TWO_PHASE = {"NH3"}  # pr_c1.LIGHT = (0, 1, 3, 4): every C1 record but NH3 is vapour-only
TEST_PROVIDER = "zz-test-pr"
MUTANTS = (
    "first_serving",
    "smallest_id",
    "all_routes",
    "detail_last",
    "shared_method_refused",
    "no_duplicate_refusal",
    "spelling_v1",
    "spelling_formula_case_sensitive",
)


class SelfClaimError(Exception):
    """A registered claim of the document does not hold; nothing is written."""


def claim(ok: bool, text: str) -> None:
    if not ok:
        raise SelfClaimError(text)


def cas_valid(cas: str) -> bool:
    body, check = cas.rsplit("-", 1)
    digits = body.replace("-", "")
    return sum(int(d) * i for i, d in enumerate(reversed(digits), start=1)) % 10 == int(check)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# =================================================================================================
# Snapshots and cases of the registered states (doc §5.1)
# =================================================================================================


def record_rows(path: Path, two_phase: set[str]) -> list[dict[str, Any]]:
    rows = []
    for r in yaml.safe_load(path.read_bytes())["components"]:
        rows.append(
            {
                "cas": r["identifiers"]["cas"],
                "formula": r["identifiers"]["formula"],
                "id": r["id"],
                "name": r["name"],
                "phases": ["liquid", "vapor"] if r["id"] in two_phase else ["vapor"],
                "synthetic": False,
            }
        )
    return rows


def snapshots() -> dict[str, dict[str, Any]]:
    c1 = {
        "provider_id": "pr-c1-v1",
        "model_ids": C1_MODELS,
        "components": record_rows(C1_RECORDS, C1_TWO_PHASE),
    }
    lib = {
        "provider_id": "pr-lib-v1",
        "model_ids": [],
        "components": record_rows(LIB_RECORDS, set()),
    }
    h2, h2o = (next(r for r in lib["components"] if r["id"] == k) for k in ("H2", "H2O"))
    test = {
        "provider_id": TEST_PROVIDER,
        "model_ids": ["c1.feed_source", "c1.product_sink", "c1.tp_heater"],
        "components": [h2, h2o],
    }

    def snap(*routes: dict[str, Any], rpr: int = 1) -> dict[str, Any]:
        return {
            "schema": "w27-registry-snapshot-v1",
            "package_version": "c9-registered-state",
            "git_commit": None,
            "list_models_sha256": "0" * 64,
            "models": [{"model_id": m} for m in C1_MODELS],
            "routes": [copy.deepcopy(r) for r in routes],
            "routes_per_revision": rpr,
            "basis": "C9 registered state (W27-registration-v2 §5.1)",
        }

    c1_co = copy.deepcopy(c1)
    c1_co["components"].append(dict(CO_RECORD))
    lib_co = copy.deepcopy(lib)
    lib_co["components"].append(dict(CO_RECORD))
    lib_bad = copy.deepcopy(lib)
    lib_bad["model_ids"] = ["x.test"]
    return {
        "S1": snap(c1),
        "S1co": snap(c1_co),
        "S2": snap(c1, lib),
        "S2r": snap(lib, c1),
        "S2co": snap(c1, lib_co),
        "S2dup": snap(c1, lib, lib),
        "S2rpr": snap(c1, lib, rpr=2),
        "S2x": snap(c1, lib_bad),
        "S3": snap(test, lib, c1),
    }


def base_case() -> dict[str, Any]:
    """W27-A13's base row (`dry_illustration.json#/adversarial_states/0/case`), GC-V2-3."""
    return {
        "case_id": "synthetic-w27",
        "expected_dof": 0,
        "family": "synthetic",
        "files_missing": [],
        "in_full82": False,
        "listed_components": ["H2"],
        "model_type": "native_IDAES",
        "objective_declared": False,
        "package_source": "property_packages.json",
        "packages": [
            {
                "classes": ["GenericParameterBlock"],
                "components": ["H2"],
                "key": "generic[Vap:VaporPhase:Cubic(type=PR)]",
                "name": "fs.props",
                "phases": ["vapor"],
            }
        ],
        "parse_errors": [],
        "residual_check": "pass",
        "solve_dynamic": False,
        "steady_state": True,
        "topology_entry_ids": [],
        "topology_kinds": ["Feed", "Heater", "Product"],
        "topology_package_names": [],
        "unit_source": "units.json",
        "units": [
            {"class_leaf": "_ScalarFeed", "key": "idaes:Feed", "names": ["fs.feed"]},
            {"class_leaf": "_ScalarHeater", "key": "idaes:Heater", "names": ["fs.heater"]},
            {"class_leaf": "_ScalarProduct", "key": "idaes:Product", "names": ["fs.product"]},
        ],
    }


def cases() -> dict[str, dict[str, Any]]:
    def variant(components: list[str], **changes: Any) -> dict[str, Any]:
        case = base_case()
        case["listed_components"] = list(components)
        case["packages"][0]["components"] = list(components)
        case.update(changes)
        return case

    vl = variant(["H2"])
    vl["packages"][0]["key"] = (
        "generic[Liq:LiquidPhase:Cubic(type=PR);Vap:VaporPhase:Cubic(type=PR)]"
    )
    vl["packages"][0]["phases"] = ["liquid", "vapor"]
    two = variant(["H2"])
    two["packages"].append(
        {
            "classes": ["GenericParameterBlock"],
            "components": ["H2"],
            "key": "generic[Vap:VaporPhase:Ideal]",
            "name": "fs.props2",
            "phases": ["vapor"],
        }
    )
    return {
        "H2": variant(["H2"]),
        "H2O": variant(["H2O"]),
        "H2-VL": vl,
        "H2-2M": two,
        "CO-Co": variant(["CO", "Co"]),
        "co": variant(["co"]),
    }


# =================================================================================================
# The v2 reference (doc §4) and its registered mutants (doc §6, GC-V2-5)
# =================================================================================================


def provider_methods(version: str) -> dict[str, str]:
    v1 = registration.provider_methods()
    table = {"v1": v1, "v2": {**v1, **PROVIDER_ADD}, "v1+lib": {**v1, **PROVIDER_ADD}}[version]
    return {**table, TEST_PROVIDER: "cubic_pr"}


def spelling_problems(snapshot: dict[str, Any], names: set[str], mutant: str | None) -> list[str]:
    """W27v2-R08 (W27-R24 (c) restated)."""
    aliases: dict[str, str] = registration.load()["components"]["aliases"]
    found = set()
    for route in snapshot["routes"]:
        for comp in route["components"]:
            if comp["synthetic"]:
                continue
            exact = {str(comp[k]) for k in ("id", "name", "formula") if comp.get(k)}
            folded = {s.casefold() for s in exact}
            cas = comp["cas"]
            for name in names:
                if aliases.get(name) == cas:
                    continue
                if mutant == "spelling_v1":
                    hit = name.casefold() in folded
                elif mutant == "spelling_formula_case_sensitive":
                    hit = name in exact or name.casefold() == str(comp.get("name")).casefold()
                else:
                    distinct = CASE_DISTINCT.get(name, {}).get("distinct_from", [])
                    hit = name in exact or (name.casefold() in folded and cas not in distinct)
                if hit:
                    found.add(f"{name}->{cas}")
    return sorted(found)


def refusal_v2(
    snapshot: dict[str, Any],
    facts: list[dict[str, Any]],
    methods: dict[str, str],
    mutant: str | None = None,
) -> str | None:
    """W27v2-R07: (a), (b), (e) as v1; (c) by W27v2-R08; (d) duplicate provider ids."""
    model_functions = registration.load()["units"]["model_functions"]
    problems = []
    unknown_models = sorted(
        m["model_id"] for m in snapshot["models"] if m["model_id"] not in model_functions
    )
    unknown_providers = sorted(
        r["provider_id"] for r in snapshot["routes"] if r["provider_id"] not in methods
    )
    names = {c for case in facts for c in coverage.declared_components(case)}
    unaliased = spelling_problems(snapshot, names, mutant)
    if unknown_models:
        problems.append(f"unregistered model ids {unknown_models}")
    if unknown_providers:
        problems.append(f"unregistered provider ids {unknown_providers}")
    if unaliased:
        problems.append(f"archive spellings of registry chemicals not aliased {unaliased}")
    if snapshot["routes_per_revision"] != 1:
        problems.append(f"routes_per_revision {snapshot['routes_per_revision']} is not 1")
    ids = Counter(r["provider_id"] for r in snapshot["routes"])
    duplicates = sorted(p for p, n in ids.items() if n > 1)
    if duplicates and mutant != "no_duplicate_refusal":
        problems.append(f"duplicate provider ids {duplicates}")
    if mutant == "shared_method_refused":
        per = Counter(
            methods[r["provider_id"]] for r in snapshot["routes"] if r["provider_id"] in methods
        )
        shared = sorted(m for m, n in per.items() if n > 1)
        if shared:
            problems.append(f"routes sharing a method {shared}")
    listed = {m["model_id"] for m in snapshot["models"]}
    on_routes = {m for r in snapshot["routes"] for m in r["model_ids"]}
    if on_routes - listed:
        problems.append(f"route model ids not among the models {sorted(on_routes - listed)}")
    if listed - on_routes:
        problems.append(f"models on no route {sorted(listed - on_routes)}")
    return "; ".join(problems) or None


def mismatch(route: dict[str, Any], phases: list[str], available: list[str]) -> str | None:
    """W27-R20's per-route test, in v1's detail form; `None` when the route serves."""
    admitted = {
        c["cas"]: set(c["phases"])
        for c in route["components"]
        if not c["synthetic"] and c.get("cas")
    }
    missing = [cas for cas in available if cas not in admitted]
    bad = [
        f"{cas}:{p}"
        for cas in available
        if cas in admitted
        for p in phases
        if p in ("vapor", "liquid", "solid") and p not in admitted[cas]
    ]
    if not missing and not bad:
        return None
    return (
        f"route_mismatch:{route['provider_id']}:missing="
        + ",".join(missing)
        + ":phase="
        + ",".join(bad)
    )


def classify_v2(
    case: dict[str, Any],
    snapshot: dict[str, Any],
    methods: dict[str, str],
    mutant: str | None = None,
) -> dict[str, Any]:
    """W27v2-R04...R06 for one case; every other part is v1's (`coverage.classify_case`)."""
    package_methods = registration.load()["routes"]["package_methods"]
    reasons: list[dict[str, Any]] = []
    if case["files_missing"] or case["parse_errors"]:
        missing = ",".join(case["files_missing"] + case["parse_errors"])
        reasons.append(
            {
                "kind": "ARTIFACT_INCOMPLETE",
                "subject": None,
                "detail": "missing:" + missing,
                "aliases": [],
            }
        )
    fired = coverage._not_steady_rules(case)
    if fired:
        reasons.append(
            {
                "kind": "NOT_STEADY_STATE_SIMULATION",
                "subject": None,
                "detail": ";".join(fired),
                "aliases": [],
            }
        )
    component_rows, component_reasons = coverage._component_reasons(case, snapshot)
    available = sorted({c["cas"] for c in component_rows if c["available"]})
    rows: list[dict[str, Any]] = []
    groups: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for package in case["packages"]:
        method = package_methods[package["key"]]
        row = {"name": package["name"], "key": package["key"], "method": method}
        rows.append(row)
        if method != "reaction":
            groups.setdefault(method, []).append((package, row))
    route_aliases = set(case["topology_package_names"]) | set(case["topology_entry_ids"])
    route_reasons: list[dict[str, Any]] = []
    serving: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for method in sorted(groups):
        members = groups[method]
        phases = sorted({p for package, _ in members for p in package["phases"]})
        detail: str | None
        if len(groups) > 1:
            detail = "multiple_routes_per_revision:" + ",".join(sorted(groups))
        else:
            of_method = [r for r in snapshot["routes"] if methods[r["provider_id"]] == method]
            details = {r["provider_id"]: mismatch(r, phases, available) for r in of_method}
            serving = [r for r in of_method if details[r["provider_id"]] is None]
            candidates = of_method if mutant == "all_routes" else serving
            if not of_method:
                detail = f"no_route:{method}"
            elif serving:
                detail = None
            elif mutant == "detail_last":
                detail = str(details[of_method[-1]["provider_id"]])
            else:
                detail = ";".join(str(details[p]) for p in sorted(details))
        for _, row in members:
            row["available"] = detail is None
            row["detail"] = detail or "available"
        if detail is None:
            continue
        for package, _ in members:
            aliases = {package["name"], package["name"].split(".")[-1], package["key"]}
            aliases |= set(package["classes"])
            aliases |= {coverage.facts.leaf(c) for c in package["classes"]}
            route_reasons.append(
                {
                    "kind": "PROPERTY_ROUTE_UNAVAILABLE",
                    "subject": package["name"],
                    "detail": detail,
                    "aliases": sorted(aliases | route_aliases),
                }
            )
    for row in rows:
        if row["method"] == "reaction":
            row["available"] = None
            row["detail"] = "reaction_package_not_a_route"
    if not groups:
        route_reasons.append(
            {
                "kind": "PROPERTY_ROUTE_UNAVAILABLE",
                "subject": None,
                "detail": "no_property_package_declared",
                "aliases": [],
            }
        )
    judged_on: str | None = None
    if serving and candidates:
        judged = {
            r["provider_id"]: coverage._unit_reasons(case, sorted(r["model_ids"]))
            for r in candidates
        }
        if mutant == "first_serving":
            judged_on = candidates[0]["provider_id"]
        elif mutant == "smallest_id":
            judged_on = min(judged)
        else:
            judged_on = min(judged, key=lambda p: (len(judged[p][1]), p))
        unit_rows, unit_reasons = judged[judged_on]
    else:
        unit_rows, unit_reasons = coverage._unit_reasons(
            case, sorted(m["model_id"] for m in snapshot["models"])
        )
    reasons += unit_reasons + component_reasons + route_reasons
    kinds = {r["kind"] for r in reasons}
    order = registration.classes()
    return {
        "case_id": case["case_id"],
        "family": case["family"],
        "model_type": case["model_type"],
        "in_full82": case["in_full82"],
        "residual_check": case["residual_check"],
        "class": next((c for c in order[:-1] if c in kinds), order[-1]),
        "reasons": reasons,
        "units_judged_on": judged_on,
        "units": unit_rows,
        "components": component_rows,
        "packages": rows,
    }


# =================================================================================================
# Registered states (doc §5.2): expectations written by hand, never derived from the reference
# =================================================================================================

U3 = [
    ["UNIT_UNAVAILABLE", "Feed", "no_model:feed units=fs.feed"],
    ["UNIT_UNAVAILABLE", "Heater", "no_model:heater units=fs.heater"],
    ["UNIT_UNAVAILABLE", "Product", "no_model:product units=fs.product"],
]
CO_NOT = ["COMPONENT_UNAVAILABLE", "Co", "unidentified"]
LIQ = "route_mismatch:{}:missing=:phase=1333-74-0:liquid"
MULTI = "multiple_routes_per_revision:cubic_pr,ideal_gas"


def row(klass: str, on: str | None, reasons: list[list[Any]]) -> dict[str, Any]:
    return {"class": klass, "units_judged_on": on, "reasons": reasons}


def refused(text: str) -> dict[str, Any]:
    return {"refusal": text}


SPELL = "archive spellings of registry chemicals not aliased "
#: (id, version, table, snapshot, case, expected, mutants that must change the outcome, why)
STATES: list[tuple[str, int, str, str, str, dict[str, Any], list[str], str]] = [
    (
        "W27v2-A01",
        2,
        "v2",
        "S1",
        "H2",
        row("CANDIDATE", "pr-c1-v1", []),
        [],
        "one route per method: v2's row equals v1's (W27v2-R10)",
    ),
    (
        "W27v2-A02",
        2,
        "v2",
        "S2",
        "H2",
        row("CANDIDATE", "pr-c1-v1", []),
        ["shared_method_refused"],
        "two cubic_pr routes serve; the one with models judges",
    ),
    (
        "W27v2-A03",
        2,
        "v2",
        "S2r",
        "H2",
        row("CANDIDATE", "pr-c1-v1", []),
        ["first_serving"],
        "snapshot order does not choose the route",
    ),
    (
        "W27v2-A04",
        2,
        "v2",
        "S2",
        "H2O",
        row("UNIT_UNAVAILABLE", "pr-lib-v1", U3),
        ["all_routes"],
        "only the library route serves H2O; units are judged on its (empty) model list",
    ),
    (
        "W27v2-A05",
        2,
        "v2",
        "S3",
        "H2O",
        row("CANDIDATE", TEST_PROVIDER, []),
        ["smallest_id"],
        "fewest unit reasons beats the smaller provider id",
    ),
    (
        "W27v2-A06",
        2,
        "v2",
        "S3",
        "H2",
        row("CANDIDATE", "pr-c1-v1", []),
        ["first_serving"],
        "a tie on unit reasons goes to the smaller provider id, not the first route",
    ),
    (
        "W27v2-A07",
        2,
        "v2",
        "S2",
        "H2-VL",
        row(
            "PROPERTY_ROUTE_UNAVAILABLE",
            None,
            [
                [
                    "PROPERTY_ROUTE_UNAVAILABLE",
                    "fs.props",
                    LIQ.format("pr-c1-v1") + ";" + LIQ.format("pr-lib-v1"),
                ]
            ],
        ),
        ["detail_last"],
        "no route serves: every route's mismatch, by provider id",
    ),
    (
        "W27v2-A08",
        2,
        "v2",
        "S2",
        "H2-2M",
        row(
            "PROPERTY_ROUTE_UNAVAILABLE",
            None,
            [
                ["PROPERTY_ROUTE_UNAVAILABLE", "fs.props", MULTI],
                ["PROPERTY_ROUTE_UNAVAILABLE", "fs.props2", MULTI],
            ],
        ),
        [],
        "one basis per revision stands (W27-R20's first sentence)",
    ),
    (
        "W27v2-A09",
        1,
        "v1",
        "S2",
        "H2",
        refused("unregistered provider ids ['pr-lib-v1']"),
        [],
        "v1 is unchanged: pr-lib-v1 is not in v0.2's table",
    ),
    (
        "W27v2-A10",
        1,
        "v1+lib",
        "S2",
        "H2",
        refused("routes sharing a method ['cubic_pr']"),
        [],
        "v1 is unchanged: W27-R24 (d) still refuses two routes of one method",
    ),
    (
        "W27v2-A11",
        2,
        "v2",
        "S2dup",
        "H2",
        refused("duplicate provider ids ['pr-lib-v1']"),
        ["no_duplicate_refusal"],
        "the tie-break key must be unique",
    ),
    (
        "W27v2-A12",
        2,
        "v2",
        "S2rpr",
        "H2",
        refused("routes_per_revision 2 is not 1"),
        [],
        "one route per revision stands",
    ),
    (
        "W27v2-A13",
        2,
        "v2",
        "S2x",
        "H2",
        refused("route model ids not among the models ['x.test']"),
        [],
        "(e) stands",
    ),
    (
        "W27v2-A14",
        1,
        "v1",
        "S1co",
        "CO-Co",
        refused(SPELL + "['Co->630-08-0']"),
        [],
        "v1 is unchanged: the casefold check refuses CO against Co (L01 F-2)",
    ),
    (
        "W27v2-A15",
        2,
        "v2",
        "S1co",
        "CO-Co",
        row("COMPONENT_UNAVAILABLE", "pr-c1-v1", [CO_NOT]),
        ["spelling_v1"],
        "v2 accepts CO beside the reviewed Co; Co stays unidentified",
    ),
    (
        "W27v2-A16",
        2,
        "v2",
        "S1co",
        "co",
        refused(SPELL + "['co->630-08-0']"),
        ["spelling_formula_case_sensitive"],
        "an unreviewed case variant is still refused",
    ),
    (
        "W27v2-A17",
        2,
        "v2",
        "S2co",
        "CO-Co",
        row("UNIT_UNAVAILABLE", "pr-lib-v1", [*U3, CO_NOT]),
        ["spelling_v1"],
        "both fixes together: CO on the library route",
    ),
]


def outcome(
    version: int, table: str, snap: dict[str, Any], case: dict[str, Any], mutant: str | None = None
) -> dict[str, Any]:
    methods = provider_methods(table)
    if version == 1:
        try:
            coverage.check_snapshot(snap, {"cases": [case]}, methods)
        except coverage.RefusalError as refusal:
            return refused(str(refusal))
        r = coverage.classify_case(case, snap, methods)
    else:
        text = refusal_v2(snap, [case], methods, mutant)
        if text is not None:
            return refused(text)
        r = classify_v2(case, snap, methods, mutant)
    return row(
        r["class"],
        r["units_judged_on"],
        [[x["kind"], x["subject"], x["detail"]] for x in r["reasons"]],
    )


# =================================================================================================
# Build, self-claims, rendering
# =================================================================================================


def development() -> tuple[set[str], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    dev = set(json.loads((DATA / "split.json").read_bytes())["development"]["case_ids"])
    facts = [
        c
        for c in json.loads((DATA / "case_facts.json").read_bytes())["cases"]
        if c["case_id"] in dev
    ]
    cov = json.loads((DATA / "coverage.json").read_bytes())
    rows = {r["case_id"]: r for r in cov["rows"] if r["case_id"] in dev}
    return dev, facts, rows, cov["snapshot"]


def build() -> dict[str, Any]:
    # GC-V2-1: v0.2's registration, document and generator are byte-identical to their pins.
    for rel, pin in BASE_PINS.items():
        claim(sha256(ROOT / rel) == pin, f"GC-V2-1: {rel} moved from its v0.2 pin")
    reg = registration.load()
    # GC-V2-2: the v2 provider table is v1's plus exactly PROVIDER_ADD, onto registered methods.
    v1 = registration.provider_methods()
    claim(not set(v1) & set(PROVIDER_ADD), "GC-V2-2: an added provider is already in v1")
    claim(set(PROVIDER_ADD.values()) <= set(reg["routes"]["methods"]), "GC-V2-2: unknown method")
    claim(set(PROVIDER_LINES) == set(PROVIDER_ADD), "GC-V2-2: provider line missing")
    snaps, case_table = snapshots(), cases()
    dev, facts, committed, committed_snap = development()
    # GC-V2-3: the registered rows are what they claim to be.
    claim(len(C1_MODELS) == 9, "GC-V2-3: the C1 model rows are not nine")
    lib_ids = [c["id"] for c in snaps["S2"]["routes"][1]["components"]]
    claim(
        lib_ids == ["H2", "N2", "Ar", "CH4", "H2O", "CO2", "O2", "C2H6", "C3H8"],
        f"GC-V2-3: library identity order {lib_ids}",
    )
    committed_c1 = [r for r in committed_snap["routes"] if r["provider_id"] == "pr-c1-v1"]
    claim(
        len(committed_c1) == 1
        and committed_c1[0]["components"] == snaps["S1"]["routes"][0]["components"]
        and committed_c1[0]["model_ids"] == C1_MODELS,
        "GC-V2-3: the C1 route differs from the committed snapshot's",
    )
    dry = json.loads(registration.DRY_JSON.read_bytes())["adversarial_states"][0]
    claim(
        dry["state"] == "A13-a base row" and dry["case"] == base_case(),
        "GC-V2-3: the base case is not W27-A13's base row",
    )
    # GC-V2-4: case_distinct entries are real, reviewed, development-evidenced collisions.
    aliases: dict[str, str] = reg["components"]["aliases"]
    for name, entry in CASE_DISTINCT.items():
        claim(name not in aliases, f"GC-V2-4: {name} is aliased; an alias decides it already")
        for cas in entry["distinct_from"]:
            claim(cas_valid(cas), f"GC-V2-4: CAS check digit {cas}")
            claim(
                any(
                    a != name and a.casefold() == name.casefold() and c == cas
                    for a, c in aliases.items()
                ),
                f"GC-V2-4: {name} vs {cas} is no collision",
            )
        declaring = sorted(c["case_id"] for c in facts if name in coverage.declared_components(c))
        claim(declaring == entry["evidence"], f"GC-V2-4: development evidence for {name}")
    # GC-V2-5: every registered state's hand-written expectation is reproduced, and every listed
    # mutant changes that state's outcome (no state is satisfiable by a dropped rule).
    states = []
    for sid, version, table, snap_id, case_id, expected, mutants, why in STATES:
        got = outcome(version, table, snaps[snap_id], case_table[case_id])
        claim(got == expected, f"GC-V2-5: {sid} gives {got}")
        for mutant in mutants:
            claim(
                outcome(version, table, snaps[snap_id], case_table[case_id], mutant) != got,
                f"GC-V2-5: mutant {mutant} does not change {sid}",
            )
        states.append(
            {
                "id": sid,
                "registration_version": version,
                "provider_table": table,
                "snapshot": snap_id,
                "case": case_id,
                "expected": expected,
                "discriminates": mutants,
                "why": why,
            }
        )
    claim(
        sorted({m for s in STATES for m in s[6]}) == sorted(MUTANTS),
        "GC-V2-5: a registered mutant is caught by no state",
    )
    # GC-V2-6: v2 equals v1 wherever v1 classifies (W27v2-R10): every state v1 accepts, and the
    # development half at the committed snapshot (rows compared whole, every member).
    for sid, _, table, snap_id, case_id, _, _, _ in STATES:
        try:
            coverage.check_snapshot(
                snaps[snap_id], {"cases": [case_table[case_id]]}, provider_methods(table)
            )
        except coverage.RefusalError:
            continue
        case, snap, methods = case_table[case_id], snaps[snap_id], provider_methods(table)
        claim(refusal_v2(snap, [case], methods) is None, f"GC-V2-6: v2 refuses {sid}")
        claim(
            classify_v2(case, snap, methods) == coverage.classify_case(case, snap, methods),
            f"GC-V2-6: v2 row differs from v1 at {sid}",
        )
    claim(len(facts) == 225 == len(committed), "GC-V2-6: development half is not 225")
    claim(
        refusal_v2(committed_snap, facts, provider_methods("v2")) is None,
        "GC-V2-6: v2 refuses the committed snapshot",
    )
    equal = sum(
        classify_v2(c, committed_snap, provider_methods("v2")) == committed[c["case_id"]]
        for c in facts
    )
    claim(equal == 225, f"GC-V2-6: {225 - equal} development rows differ under v2")
    # GC-V2-7: on development spellings, the CO record is refused by v1 for Co alone and accepted
    # by v2, on one route and beside the library route.
    try:
        coverage.check_snapshot(snaps["S1co"], {"cases": facts}, provider_methods("v1"))
        v1_text = ""
    except coverage.RefusalError as refusal:
        v1_text = str(refusal)
    claim(v1_text == SPELL + "['Co->630-08-0']", f"GC-V2-7: v1 on development: {v1_text}")
    for snap_id in ("S1co", "S2co"):
        claim(
            refusal_v2(snaps[snap_id], facts, provider_methods("v2")) is None,
            f"GC-V2-7: v2 refuses {snap_id} on development spellings",
        )
    return {
        "schema": SCHEMA,
        "registration_version": 2,
        "document": str(DOC.relative_to(ROOT)),
        "generator": str(Path(__file__).resolve().relative_to(ROOT)),
        "base": {"registration_version": 1, "sha256": BASE_PINS},
        "tables": {
            "provider_methods": dict(sorted({**v1, **PROVIDER_ADD}.items())),
            "provider_lines_added": PROVIDER_LINES,
            "case_distinct": CASE_DISTINCT,
        },
        "rules": {
            "serving_route_order": ["unit_reason_count", "provider_id"],
            "route_detail_join": ";",
            "refusals": [
                "a",
                "b",
                "c:case_distinct",
                "d:routes_per_revision",
                "d:duplicate_ids",
                "e",
            ],
        },
        "snapshots": snaps,
        "cases": case_table,
        "test_provider_methods": {TEST_PROVIDER: "cubic_pr"},
        "states": states,
        "mutants": list(MUTANTS),
        "development": {
            "cases": 225,
            "rows_equal_v1_at_committed_snapshot": equal,
            "scope": "development half only (C2 split); no held-out row is read",
        },
    }


def render_blocks(document: dict[str, Any]) -> dict[str, str]:
    lines = [
        "| Assertion | Version | Snapshot | Case | Expected | Mutants that must fail | Why |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for s in document["states"]:
        e = s["expected"]
        if "refusal" in e:
            text = f"refused: `{e['refusal']}`"
        else:
            on = f"`{e['units_judged_on']}`" if e["units_judged_on"] else "null"
            reasons = "; ".join(f"`{k}` `{sub}` `{d}`" for k, sub, d in e["reasons"]) or "none"
            text = f"`{e['class']}`, judged on {on}; reasons: {reasons}"
        table = "" if s["provider_table"] in ("v1", "v2") else f" ({s['provider_table']})"
        mutants = ", ".join(f"`{m}`" for m in s["discriminates"]) or "—"
        lines.append(
            f"| {s['id']} | {s['registration_version']}{table} | {s['snapshot']} | "
            f"{s['case']} | {text} | {mutants} | {s['why']} |"
        )
    provider = ["| Provider id | Method |", "| --- | --- |"] + [
        f"| `{p}` | `{m}` |" for p, m in document["tables"]["provider_methods"].items()
    ]
    distinct = [
        "| Spelling | Distinct from | Reading | Development evidence |",
        "| --- | --- | --- | --- |",
    ] + [
        f"| `{n}` | {', '.join(e['distinct_from'])} | {e['reading']} | "
        + ", ".join(f"`{x}`" for x in e["evidence"])
        + " |"
        for n, e in document["tables"]["case_distinct"].items()
    ]
    return {
        "states": "\n".join(lines),
        "providers": "\n".join(provider),
        "case_distinct": "\n".join(distinct),
    }


def dump(document: dict[str, Any]) -> bytes:
    text = json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
    return (text + "\n").encode("utf-8")


def with_blocks(doc_text: str, blocks: dict[str, str]) -> str:
    for name, body in blocks.items():
        pattern = re.compile(rf"(<!-- c9:begin:{name} -->\n).*?(\n<!-- c9:end:{name} -->)", re.S)
        claim(len(pattern.findall(doc_text)) == 1, f"GC-V2-8: block {name} not found once")
        doc_text = pattern.sub(lambda m, b=body: m.group(1) + b + m.group(2), doc_text)
    return doc_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--emit", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        document = build()
        data = dump(document)
        doc_text = DOC.read_text(encoding="utf-8")
        new_doc = with_blocks(doc_text, render_blocks(document))
    except SelfClaimError as failure:
        print(f"REFUSED (self-claim): {failure}", file=sys.stderr)
        return 2
    if args.check:
        same_json = OUT.exists() and OUT.read_bytes() == data
        same_doc = new_doc == doc_text  # GC-V2-8: the document's generated blocks are current
        print(
            f"{OUT.relative_to(ROOT)}: {'identical' if same_json else 'DIFFERS'}; "
            f"{DOC.relative_to(ROOT)} blocks: {'identical' if same_doc else 'DIFFER'}"
        )
        return 0 if same_json and same_doc else 1
    OUT.write_bytes(data)
    DOC.write_text(new_doc, encoding="utf-8")
    print(
        f"wrote {OUT.relative_to(ROOT)} ({len(document['states'])} states) and "
        f"{DOC.relative_to(ROOT)} blocks"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
