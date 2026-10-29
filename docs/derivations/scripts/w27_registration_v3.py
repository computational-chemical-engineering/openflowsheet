"""W27 registration version 3 (S11): tables, registered states and self-claims.

Normative text: `docs/derivations/W27-registration-v3.md`, transcribed from the S11 design note
§4.10 (ADR 0050 D9, R-808). Version 3 is version 2 (`docs/derivations/W27-registration-v2.md`)
with S11's provider, method and model rows added, and with a route identified by its key
`(provider_id, record_source, components)` instead of its provider id. This script writes none of
version 1's or version 2's files, and refuses (GC-V3-1) when one of them is not byte-identical to
its pin.

Inputs: committed files only (no archive, no network): version 1's and version 2's registrations
and generator, W27's `case_facts.json` and `coverage.json` (development rows only, after the C2
split's filter), and the record files the registered snapshots' routes read.

The reference functions below implement the version 3 deltas (route key, key order, refusals) on
top of version 2's reference (`w27_registration_v2.py`) and version 1's tested pieces. They are not
the production classifier (`benchmarks/m06/w27/coverage.py`, WO-A4), whose tests compare it with
the registered states this script emits. The states' expected outcomes are written by hand (doc
§5); this script refuses to emit unless its reference reproduces them and every registered mutant
changes the outcome of a state that lists it.

Run (repository root, PYTHONPATH=src:.):
    python docs/derivations/scripts/w27_registration_v3.py --emit
    python docs/derivations/scripts/w27_registration_v3.py --check
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
sys.path.insert(0, str(Path(__file__).resolve().parent))

import w27_registration_v2 as v2  # noqa: E402

from benchmarks.m06.w27 import coverage, registration  # noqa: E402

DATA = ROOT / "benchmarks/m06/openidaes450"
OUT = DATA / "registration_v3.json"
DOC = ROOT / "docs/derivations/W27-registration-v3.md"
SCHEMA = "w27-registration-v3"
SNAPSHOT_SCHEMA = "w27-registry-snapshot-v3"

#: GC-V3-1: version 1's pins (GC-V2-1) and version 2's files as C9 registered them.
BASE_PINS = {
    **v2.BASE_PINS,
    "benchmarks/m06/openidaes450/registration_v2.json": (
        "c7dab28a00886e7a6643ce38079c998c235c7e694c8f4afaf0c62ab2c45f04b0"
    ),
    "docs/derivations/W27-registration-v2.md": (
        "39bbf047b90c04b5c3baa98abc112d77071250af1f1dd639b733a63bb7027641"
    ),
    "docs/derivations/scripts/w27_registration_v2.py": (
        "0963c445f5b6842f6bc83ac1e782bca33e9aab545d8ccbb118b2033453195708"
    ),
}

#: W27v3-R02: the provider rows version 3 adds to version 2's table, with S11 WO-D5's
#: `wilson-ig-v2 → activity_coefficient` (units design §5.4 item 2; v1's row kept, as version 2
#: keeps `pr-lib-v1`'s).
PROVIDER_ADD = {
    "coolprop-heos-v1": "pure_helmholtz",
    "iapws95-v1": "iapws95",
    "wilson-ig-v1": "activity_coefficient",
    "wilson-ig-v2": "activity_coefficient",
}
#: W27v3-R03.
METHODS_ADD = {
    "pure_helmholtz": "a pure-fluid multiparameter Helmholtz EOS other than IAPWS-95 (CoolProp "
    "HEOS); matches no case method"
}
#: W27v3-R04, with the meaning of its `why_none` (as `#/units/model_none_reasons` gives each),
#: and S11 units design §4.10's seven thermal rows, each onto an existing function.
MODEL_FUNCTIONS_ADD = {
    "syn001.column": {"function": None, "offers": [], "why_none": "column_function_unregistered"},
    "thermal.heater": {"function": "heater", "offers": []},
    "thermal.valve": {"function": "valve", "offers": []},
    "thermal.mixer": {"function": "mixer", "offers": []},
    "thermal.flash": {"function": "flash", "offers": []},
    "thermal.pump": {"function": "pump", "offers": []},
    "thermal.compressor": {"function": "compressor", "offers": []},
    "thermal.turbine": {"function": "expander", "offers": []},
}
MODEL_NONE_REASONS_ADD = {
    "column_function_unregistered": "no W27 function is registered for the counter-current "
    "column against the OpenIDAES-450 archive (S11 §7 Q6: a workstation follow-on), so it "
    "serves no case unit"
}
#: W27v3-R05: each provider's snapshot line.
GENERIC_LINE = (
    "the records at ROOT / basis.record_source ({id, name, formula, cas, synthetic} from each "
    "record's identifiers); every phase of describe().phases for every component"
)
PROVIDER_LINES = {
    "coolprop-heos-v1": GENERIC_LINE,
    "iapws95-v1": GENERIC_LINE,
    "pr-c1-v1": "version 2's line (pr_c1.RECORDS_PATH; vapor for pr_c1.LIGHT, every phase else)",
    "pr-lib-v1": "version 2's line (pr_lib.RECORDS_PATH; vapor for every component)",
    "syn001": GENERIC_LINE,
    "wilson-ig-v1": GENERIC_LINE,
    "wilson-ig-v2": GENERIC_LINE,
}
#: S11 §4.1: the `record_source` each provider's basis carries (`zz-test-pr` holds library rows).
RECORD_SOURCES = {
    "coolprop-heos-v1": "benchmarks/s07/components.yaml",
    "iapws95-v1": "benchmarks/s05/components.yaml",
    "pr-c1-v1": "benchmarks/m01/components.yaml",
    "pr-lib-v1": "benchmarks/l01/components.yaml",
    "syn001": "benchmarks/syn001/components.yaml",
    "wilson-ig-v1": "benchmarks/s10/records.yaml",
    "wilson-ig-v2": "benchmarks/s10/records.yaml",
    v2.TEST_PROVIDER: "benchmarks/l01/components.yaml",
}
#: S11 A2: the routing models every S11 basis admits.
ROUTING = ["syn001.feed_source", "syn001.product_sink", "syn001.stream_splitter"]
COOLPROP_FLUIDS = 123
MUTANTS = (
    "provider_table_v2",
    "column_unregistered",
    "duplicate_provider_refusal",
    "no_key_refusal",
    "record_source_ignored",
    "first_serving",
    "cas_less_refused",
    "spelling_rule_off",
)


class SelfClaimError(Exception):
    """A registered claim of the document does not hold; nothing is written."""


def claim(ok: bool, text: str) -> None:
    if not ok:
        raise SelfClaimError(text)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# =================================================================================================
# Snapshots and cases of the registered states (doc §5.1)
# =================================================================================================


def generic_rows(record_source: str) -> list[dict[str, Any]]:
    """W27v3-R05's generic line, read independently of `snapshot.py`: every record of the file,
    in file order, in liquid and vapour (the S11 bases' `describe().phases`)."""
    rows = []
    for r in yaml.safe_load((ROOT / record_source).read_bytes())["components"]:
        identifiers = r.get("identifiers") or {}
        rows.append(
            {
                "cas": identifiers.get("cas"),
                "formula": identifiers.get("formula"),
                "id": r["id"],
                "name": r.get("name"),
                "phases": ["liquid", "vapor"],
                "synthetic": bool(r.get("synthetic")),
            }
        )
    return rows


def route(provider: str, components: list[dict[str, Any]], models: list[str]) -> dict[str, Any]:
    return {
        "provider_id": provider,
        "record_source": RECORD_SOURCES[provider],
        "components": copy.deepcopy(components),
        "model_ids": list(models),
    }


def snap(models: list[str], *routes: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": SNAPSHOT_SCHEMA,
        "package_version": "s11-registered-state",
        "git_commit": None,
        "list_models_sha256": "0" * 64,
        "models": [{"model_id": m} for m in sorted(models)],
        "routes": [copy.deepcopy(r) for r in routes],
        "routes_per_revision": 1,
        "basis": "S11 registered state (W27-registration-v3 §5.1)",
    }


def snapshots() -> dict[str, dict[str, Any]]:
    c1 = route("pr-c1-v1", v2.snapshots()["S1"]["routes"][0]["components"], v2.C1_MODELS)
    iapws = route("iapws95-v1", generic_rows(RECORD_SOURCES["iapws95-v1"]), ROUTING)
    wilson = route(
        "wilson-ig-v1", generic_rows(RECORD_SOURCES["wilson-ig-v1"]), [*ROUTING, "syn001.column"]
    )
    coolprop = [
        route("coolprop-heos-v1", [row], ROUTING)
        for row in generic_rows(RECORD_SOURCES["coolprop-heos-v1"])
    ]
    models = [*v2.C1_MODELS, *ROUTING, "syn001.column"]
    build = snap(models, c1, iapws, wilson, *coolprop)
    duplicate = copy.deepcopy(build)
    duplicate["routes"].append(
        copy.deepcopy(next(r for r in coolprop if r["components"][0]["id"] == "CO2"))
    )
    unkeyed = copy.deepcopy(build)
    del unkeyed["routes"][1]["record_source"]
    lib = {r["id"]: r for r in v2.record_rows(v2.LIB_RECORDS, set())}
    pair = [lib["H2"], lib["H2O"]]
    tie_b = route(v2.TEST_PROVIDER, pair, ["c1.feed_source", "c1.product_sink", "c1.tp_heater"])
    tie_b["record_source"] = "benchmarks/zz-test/b.yaml"
    tie_a = route(
        v2.TEST_PROVIDER,
        pair,
        ["c1.feed_source", "c1.product_sink", "c1.tp_heater", "syn001.tp_heater"],
    )
    tie_a["record_source"] = "benchmarks/zz-test/a.yaml"
    tie_models = [*v2.C1_MODELS, "syn001.tp_heater"]
    no_wilson = snap([*v2.C1_MODELS, *ROUTING], c1, iapws, *coolprop)
    return {
        "B": build,
        "Bi": no_wilson,
        "Bdup": duplicate,
        "Bsrc": unkeyed,
        "T": snap(tie_models, c1, tie_b, tie_a),
        "Tr": snap(tie_models, c1, tie_a, tie_b),
        "S1co": with_sources(v2.snapshots()["S1co"]),
    }


def cases() -> dict[str, dict[str, Any]]:
    table = v2.cases()
    water = v2.base_case()
    water["listed_components"] = ["H2O"]
    water["packages"] = [
        {
            "classes": ["Iapws95ParameterBlock"],
            "components": ["H2O"],
            "key": "idaes.models.properties.iapws95.Iapws95ParameterBlock",
            "name": "fs.props",
            "phases": ["liquid", "vapor"],
        }
    ]
    return {"H2": table["H2"], "H2O": table["H2O"], "H2O-iapws": water, "co": table["co"]}


# =================================================================================================
# The v3 reference (doc §4) and its registered mutants (doc §6, GC-V3-5)
# =================================================================================================


def provider_methods(table: str, mutant: str | None = None) -> dict[str, str]:
    """`v2` is version 2's table, `v3` version 2's plus `PROVIDER_ADD`; each with the test
    provider (W27-A02)."""
    base = registration.provider_methods(2)
    if table == "v3" and mutant != "provider_table_v2":
        base = {**base, **PROVIDER_ADD}
    return {**base, v2.TEST_PROVIDER: "cubic_pr"}


def model_functions(mutant: str | None = None) -> dict[str, Any]:
    table = dict(registration.load()["units"]["model_functions"])
    if mutant != "column_unregistered":
        table.update(MODEL_FUNCTIONS_ADD)
    return table


def key(r: dict[str, Any], mutant: str | None = None) -> tuple[str, ...]:
    """W27v3-R06/R07: the route key, compared in code-point order."""
    ids = ",".join(c["id"] for c in r["components"])
    if mutant == "record_source_ignored":
        return (r["provider_id"], ids)
    return (r["provider_id"], r["record_source"], ids)


def spelling_problems_v3(
    snapshot: dict[str, Any], names: set[str], mutant: str | None
) -> list[str]:
    """W27v3-R09: W27v2-R08 over the records that have a CAS RN; a non-synthetic record with no
    CAS RN (`cas` absent, null or empty) can match no case component (W27-R15) and takes no part.
    """
    if mutant == "spelling_rule_off":
        return []
    keyed = copy.deepcopy(snapshot)
    if mutant != "cas_less_refused":
        for r in keyed["routes"]:
            r["components"] = [c for c in r["components"] if c["synthetic"] or c.get("cas")]
    return v2.spelling_problems(keyed, names, None)


def refusal_v3(
    snapshot: dict[str, Any], names: set[str], methods: dict[str, str], mutant: str | None
) -> str | None:
    """W27v2-R07 with version 3's tables, W27v3-R09's spelling rule for (c) and W27v3-R06's (d),
    against the archive spellings `names`."""
    functions = model_functions(mutant)
    problems = []
    unknown_models = sorted(
        m["model_id"] for m in snapshot["models"] if m["model_id"] not in functions
    )
    unknown_providers = sorted(
        r["provider_id"] for r in snapshot["routes"] if r["provider_id"] not in methods
    )
    unaliased = spelling_problems_v3(snapshot, names, mutant)
    if unknown_models:
        problems.append(f"unregistered model ids {unknown_models}")
    if unknown_providers:
        problems.append(f"unregistered provider ids {unknown_providers}")
    if unaliased:
        problems.append(f"archive spellings of registry chemicals not aliased {unaliased}")
    if snapshot["routes_per_revision"] != 1:
        problems.append(f"routes_per_revision {snapshot['routes_per_revision']} is not 1")
    unkeyed = sorted({r["provider_id"] for r in snapshot["routes"] if not r.get("record_source")})
    if mutant == "duplicate_provider_refusal":
        ids = Counter(r["provider_id"] for r in snapshot["routes"])
        duplicates: list[Any] = sorted(p for p, n in ids.items() if n > 1)
        if duplicates:
            problems.append(f"duplicate provider ids {duplicates}")
    elif unkeyed:
        problems.append(f"routes with no record_source {unkeyed}")
    elif mutant != "no_key_refusal":
        keys = Counter(key(r, mutant) for r in snapshot["routes"])
        duplicates = sorted(k for k, n in keys.items() if n > 1)
        if duplicates:
            problems.append(f"duplicate route keys {duplicates}")
    listed = {m["model_id"] for m in snapshot["models"]}
    on_routes = {m for r in snapshot["routes"] for m in r["model_ids"]}
    if on_routes - listed:
        problems.append(f"route model ids not among the models {sorted(on_routes - listed)}")
    if listed - on_routes:
        problems.append(f"models on no route {sorted(listed - on_routes)}")
    return "; ".join(problems) or None


def classify_v3(
    case: dict[str, Any], snapshot: dict[str, Any], methods: dict[str, str], mutant: str | None
) -> dict[str, Any]:
    """W27v2-R04…R06 with routes named and ordered by key (W27v3-R07); every other part is
    version 1's (`coverage.classify_case`)."""
    package_methods = registration.load()["routes"]["package_methods"]
    functions = model_functions(mutant)
    reasons: list[dict[str, Any]] = []
    if case["files_missing"] or case["parse_errors"]:
        missing = ",".join(case["files_missing"] + case["parse_errors"])
        reasons.append(
            {"kind": "ARTIFACT_INCOMPLETE", "subject": None, "detail": "missing:" + missing}
        )
    fired = coverage._not_steady_rules(case)
    if fired:
        reasons.append(
            {"kind": "NOT_STEADY_STATE_SIMULATION", "subject": None, "detail": ";".join(fired)}
        )
    component_rows, component_reasons = coverage._component_reasons(case, snapshot)
    available = sorted({c["cas"] for c in component_rows if c["available"]})
    groups: dict[str, list[dict[str, Any]]] = {}
    for package in case["packages"]:
        method = package_methods[package["key"]]
        if method != "reaction":
            groups.setdefault(method, []).append(package)
    route_reasons: list[dict[str, Any]] = []
    serving: list[dict[str, Any]] = []
    for method in sorted(groups):
        members = groups[method]
        phases = sorted({p for package in members for p in package["phases"]})
        detail: str | None
        if len(groups) > 1:
            detail = "multiple_routes_per_revision:" + ",".join(sorted(groups))
        else:
            of_method = [r for r in snapshot["routes"] if methods[r["provider_id"]] == method]
            if mutant != "first_serving":
                of_method.sort(key=key)
            mismatches = [(r, v2.mismatch(r, phases, available)) for r in of_method]
            serving = [r for r, m in mismatches if m is None]
            if not of_method:
                detail = f"no_route:{method}"
            elif serving:
                detail = None
            else:
                detail = ";".join(str(m) for _, m in mismatches)
        if detail is not None:
            route_reasons += [
                {"kind": "PROPERTY_ROUTE_UNAVAILABLE", "subject": p["name"], "detail": detail}
                for p in members
            ]
    if not groups:
        route_reasons.append(
            {
                "kind": "PROPERTY_ROUTE_UNAVAILABLE",
                "subject": None,
                "detail": "no_property_package_declared",
            }
        )
    judged_on: str | None = None
    if serving:
        judged = [
            (coverage._unit_reasons(case, sorted(r["model_ids"]), functions), r) for r in serving
        ]
        if mutant == "first_serving":
            (unit_rows, unit_reasons), chosen = judged[0]
        else:
            (unit_rows, unit_reasons), chosen = min(
                judged,
                key=lambda j: (
                    sum(1 for x in j[0][1] if x["kind"] == "UNIT_UNAVAILABLE"),
                    key(j[1]),
                ),
            )
        judged_on = chosen["provider_id"]
    else:
        every = sorted(m["model_id"] for m in snapshot["models"])
        unit_rows, unit_reasons = coverage._unit_reasons(case, every, functions)
    reasons += unit_reasons + component_reasons + route_reasons
    kinds = {r["kind"] for r in reasons}
    order = registration.classes()
    return {
        "class": next((c for c in order[:-1] if c in kinds), order[-1]),
        "units_judged_on": judged_on,
        "reasons": [[r["kind"], r["subject"], r["detail"]] for r in reasons],
        "units": [[u["key"], u["models"]] for u in unit_rows],
    }


def outcome(
    version: int, snapshot: dict[str, Any], case: dict[str, Any], mutant: str | None = None
) -> dict[str, Any]:
    """A state's outcome: version 2 through its reference, version 3 through this one."""
    if version == 2:
        methods = provider_methods("v2")
        text = v2.refusal_v2(snapshot, [case], methods)
        if text is not None:
            return {"refusal": text}
        r = v2.classify_v2(case, snapshot, methods)
        return {
            "class": r["class"],
            "units_judged_on": r["units_judged_on"],
            "reasons": [[x["kind"], x["subject"], x["detail"]] for x in r["reasons"]],
            "units": [[u["key"], u["models"]] for u in r["units"]],
        }
    methods = provider_methods("v3", mutant)
    text = refusal_v3(snapshot, set(coverage.declared_components(case)), methods, mutant)
    if text is not None:
        return {"refusal": text}
    return classify_v3(case, snapshot, methods, mutant)


# =================================================================================================
# Registered states (doc §5.2): expectations written by hand, never derived from the reference
# =================================================================================================

FEED = ["idaes:Feed", ["syn001.feed_source"]]
PRODUCT = ["idaes:Product", ["syn001.product_sink"]]
C1_UNITS = [
    ["idaes:Feed", ["c1.feed_source"]],
    ["idaes:Heater", ["c1.tp_heater"]],
    ["idaes:Product", ["c1.product_sink"]],
]
CO2_KEY = "('coolprop-heos-v1', 'benchmarks/s07/components.yaml', 'CO2')"


def judged(
    on: str | None, klass: str, reasons: list[list[Any]], units: list[Any]
) -> dict[str, Any]:
    return {"class": klass, "units_judged_on": on, "reasons": reasons, "units": units}


STATES: list[tuple[str, int, str, str, dict[str, Any], list[str], str]] = [
    (
        "W27v3-A01",
        3,
        "B",
        "H2",
        judged("pr-c1-v1", "CANDIDATE", [], C1_UNITS),
        ["provider_table_v2", "column_unregistered", "duplicate_provider_refusal"],
        "the S11 bases beside C1: 123 CoolProp routes with distinct keys and the column are "
        "admitted, and pr-c1-v1 still judges a cubic_pr case",
    ),
    (
        "W27v3-A02",
        3,
        "Bdup",
        "H2",
        {"refusal": f"duplicate route keys [{CO2_KEY}]"},
        ["no_key_refusal"],
        "two routes with one key are refused (W27v3-R06)",
    ),
    (
        "W27v3-A03",
        3,
        "Bsrc",
        "H2",
        {"refusal": "routes with no record_source ['iapws95-v1']"},
        [],
        "a route with no record_source has no key",
    ),
    (
        "W27v3-A04",
        3,
        "Bi",
        "H2O-iapws",
        judged(
            "iapws95-v1",
            "UNIT_UNAVAILABLE",
            [["UNIT_UNAVAILABLE", "Heater", "no_model:heater units=fs.heater"]],
            [FEED, ["idaes:Heater", []], PRODUCT],
        ),
        ["provider_table_v2"],
        "IAPWS-95's route serves an iapws95 case's property side; its routing models judge the "
        "units",
    ),
    (
        "W27v3-A05",
        3,
        "T",
        "H2O",
        judged(
            v2.TEST_PROVIDER,
            "CANDIDATE",
            [],
            [
                ["idaes:Feed", ["c1.feed_source"]],
                ["idaes:Heater", ["c1.tp_heater", "syn001.tp_heater"]],
                ["idaes:Product", ["c1.product_sink"]],
            ],
        ),
        ["first_serving", "record_source_ignored"],
        "two routes of one provider differ only by record_source; a tie goes to the smaller key "
        "(benchmarks/zz-test/a.yaml), not the first route",
    ),
    (
        "W27v3-A06",
        3,
        "Tr",
        "H2O",
        judged(
            v2.TEST_PROVIDER,
            "CANDIDATE",
            [],
            [
                ["idaes:Feed", ["c1.feed_source"]],
                ["idaes:Heater", ["c1.tp_heater", "syn001.tp_heater"]],
                ["idaes:Product", ["c1.product_sink"]],
            ],
        ),
        ["record_source_ignored"],
        "the same build with the two routes reversed: the order does not decide",
    ),
    (
        "W27v3-A07",
        2,
        "T",
        "H2O",
        {"refusal": "duplicate provider ids ['zz-test-pr']"},
        [],
        "version 2 is unchanged: it refuses two routes of one provider id",
    ),
    (
        "W27v3-A08",
        3,
        "B",
        "H2O-iapws",
        judged(
            "iapws95-v1",
            "UNIT_UNAVAILABLE",
            [["UNIT_UNAVAILABLE", "Heater", "no_model:heater units=fs.heater"]],
            [FEED, ["idaes:Heater", []], PRODUCT],
        ),
        ["cas_less_refused"],
        "A04's outcome, now on B: the Wilson records carry no CAS RN, so W27v3-R09 skips them "
        "(R-832)",
    ),
    (
        "W27v3-A09",
        3,
        "S1co",
        "co",
        {"refusal": "archive spellings of registry chemicals not aliased ['co->630-08-0']"},
        ["spelling_rule_off"],
        "W27v2-A16's refusal under version 3: records with a CAS RN keep W27v2-R08 (R-832)",
    ),
]


# =================================================================================================
# Build, self-claims, rendering
# =================================================================================================


def with_sources(snapshot: dict[str, Any]) -> dict[str, Any]:
    """A version 2 snapshot in version 3's form: each route with its provider's record source."""
    out = copy.deepcopy(snapshot)
    out["schema"] = SNAPSHOT_SCHEMA
    for r in out["routes"]:
        r["record_source"] = RECORD_SOURCES[r["provider_id"]]
    return out


def build() -> dict[str, Any]:
    # GC-V3-1: versions 1 and 2 are byte-identical to their pins.
    for rel, pin in BASE_PINS.items():
        claim(sha256(ROOT / rel) == pin, f"GC-V3-1: {rel} moved from its pin")
    reg = registration.load()
    # GC-V3-2: the table is version 2's plus exactly PROVIDER_ADD, onto registered methods.
    v2_table = registration.provider_methods(2)
    claim(not set(v2_table) & set(PROVIDER_ADD), "GC-V3-2: an added provider is already in v2")
    methods = set(reg["routes"]["methods"])
    claim(not set(METHODS_ADD) & methods, "GC-V3-2: an added method is already in v1")
    claim(set(PROVIDER_ADD.values()) <= methods | set(METHODS_ADD), "GC-V3-2: unknown method")
    claim(
        not set(METHODS_ADD) & set(reg["routes"]["package_methods"].values()),
        "GC-V3-2: an added method matches a case package",
    )
    claim(set(PROVIDER_LINES) == set(v2_table) | set(PROVIDER_ADD), "GC-V3-2: provider lines")
    # GC-V3-3: the column row is new, its reason is registered, and the records are as S11 says.
    claim(
        not set(MODEL_FUNCTIONS_ADD) & set(reg["units"]["model_functions"]),
        "GC-V3-3: an added model id is already a v1 model",
    )
    claim(
        {e["why_none"] for e in MODEL_FUNCTIONS_ADD.values() if e["function"] is None}
        == set(MODEL_NONE_REASONS_ADD)
        and not set(MODEL_NONE_REASONS_ADD) & set(reg["units"]["model_none_reasons"]),
        "GC-V3-3: why_none is not a new registered reason",
    )
    claim(
        all(
            e["offers"] == [] and (e["function"] is None) == ("why_none" in e)
            for e in MODEL_FUNCTIONS_ADD.values()
        )
        and {e["function"] for e in MODEL_FUNCTIONS_ADD.values()} - {None}
        <= set(reg["units"]["functions"]),
        "GC-V3-3: an added model row is not onto an existing function",
    )
    cool = generic_rows(RECORD_SOURCES["coolprop-heos-v1"])
    claim(
        len(cool) == COOLPROP_FLUIDS == len({r["id"] for r in cool}),
        f"GC-V3-3: {len(cool)} CoolProp records, not {COOLPROP_FLUIDS} distinct ids",
    )
    water = generic_rows(RECORD_SOURCES["iapws95-v1"])
    claim(
        [(r["id"], r["cas"]) for r in water] == [("H2O", "7732-18-5")],
        "GC-V3-3: the IAPWS-95 records are not H2O with CAS 7732-18-5",
    )
    snaps, case_table = snapshots(), cases()
    claim(len(snaps["B"]["routes"]) == 3 + COOLPROP_FLUIDS, "GC-V3-3: B is not 126 routes")
    # GC-V3-4: every registered state's hand-written expectation is reproduced, and every listed
    # mutant changes that state's outcome; every mutant is caught by some state.
    states = []
    for sid, version, snap_id, case_id, expected, mutants, why in STATES:
        got = outcome(version, snaps[snap_id], case_table[case_id])
        claim(got == expected, f"GC-V3-4: {sid} gives {got}")
        for mutant in mutants:
            claim(
                outcome(version, snaps[snap_id], case_table[case_id], mutant) != got,
                f"GC-V3-4: mutant {mutant} does not change {sid}",
            )
        states.append(
            {
                "id": sid,
                "registration_version": version,
                "snapshot": snap_id,
                "case": case_id,
                "expected": expected,
                "discriminates": mutants,
                "why": why,
            }
        )
    claim(
        sorted({m for s in STATES for m in s[5]}) == sorted(MUTANTS),
        "GC-V3-4: a registered mutant is caught by no state",
    )
    # GC-V3-5: version 3 equals version 2 wherever version 2 accepts, on version 2's registered
    # snapshots and on the development half at the committed snapshot (record sources added).
    v2_snaps, v2_cases = v2.snapshots(), v2.cases()
    compared = 0
    for snap_id, snapshot in sorted(v2_snaps.items()):
        for case_id, case in sorted(v2_cases.items()):
            before = outcome(2, snapshot, case)
            if "refusal" in before:
                continue
            claim(
                outcome(3, with_sources(snapshot), case) == before,
                f"GC-V3-5: v3 differs from v2 at {snap_id}/{case_id}",
            )
            compared += 1
    _, dev_facts, committed, committed_snap = v2.development()
    keyed = with_sources(committed_snap)
    names = {n for c in dev_facts for n in coverage.declared_components(c)}
    claim(
        refusal_v3(keyed, names, provider_methods("v3"), None) is None,
        "GC-V3-5: v3 refuses the committed snapshot",
    )
    equal = sum(
        outcome(3, keyed, c)
        == {
            "class": committed[c["case_id"]]["class"],
            "units_judged_on": committed[c["case_id"]]["units_judged_on"],
            "reasons": [
                [x["kind"], x["subject"], x["detail"]] for x in committed[c["case_id"]]["reasons"]
            ],
            "units": [[u["key"], u["models"]] for u in committed[c["case_id"]]["units"]],
        }
        for c in dev_facts
    )
    claim(len(dev_facts) == 225 and equal == 225, f"GC-V3-5: {225 - equal} development rows differ")
    return {
        "schema": SCHEMA,
        "registration_version": 3,
        "document": str(DOC.relative_to(ROOT)),
        "generator": str(Path(__file__).resolve().relative_to(ROOT)),
        "base": {"registration_version": 2, "sha256": BASE_PINS},
        "tables": {
            "provider_methods": dict(sorted({**v2_table, **PROVIDER_ADD}.items())),
            "provider_methods_added": PROVIDER_ADD,
            "methods_added": METHODS_ADD,
            "model_functions_added": MODEL_FUNCTIONS_ADD,
            "model_none_reasons_added": MODEL_NONE_REASONS_ADD,
            "provider_lines": PROVIDER_LINES,
        },
        "rules": {
            "route_key": ["provider_id", "record_source", "components"],
            "route_key_components_join": ",",
            "serving_route_order": ["unit_reason_count", "route_key"],
            "units_judged_on": "provider_id",
            "refusals": [
                "a",
                "b",
                "c:case_distinct",
                "c:no_cas_skipped",
                "d:routes_per_revision",
                "d:no_record_source",
                "d:duplicate_route_keys",
                "e",
            ],
            "snapshot_schema": SNAPSHOT_SCHEMA,
        },
        "snapshots": snaps,
        "cases": case_table,
        "test_provider_methods": {v2.TEST_PROVIDER: "cubic_pr"},
        "states": states,
        "mutants": list(MUTANTS),
        "equivalence": {
            "v2_states_compared": compared,
            "development_rows_equal_at_committed_snapshot": equal,
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
            heater = next(m for k, m in e["units"] if k == "idaes:Heater")
            text = f"`{e['class']}`, judged on {on}; reasons: {reasons}; Heater models: " + (
                ", ".join(f"`{m}`" for m in heater) or "none"
            )
        mutants = ", ".join(f"`{m}`" for m in s["discriminates"]) or "—"
        lines.append(
            f"| {s['id']} | {s['registration_version']} | {s['snapshot']} | {s['case']} | "
            f"{text} | {mutants} | {s['why']} |"
        )
    added = document["tables"]["provider_methods_added"]
    provider = ["| Provider id | Method | Line (W27v3-R05) |", "| --- | --- | --- |"] + [
        f"| `{p}` | `{m}`{' (added)' if p in added else ''} | "
        f"{document['tables']['provider_lines'][p]} |"
        for p, m in document["tables"]["provider_methods"].items()
    ]
    return {"states": "\n".join(lines), "providers": "\n".join(provider)}


def dump(document: dict[str, Any]) -> bytes:
    text = json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
    return (text + "\n").encode("utf-8")


def with_blocks(doc_text: str, blocks: dict[str, str]) -> str:
    for name, body in blocks.items():
        pattern = re.compile(rf"(<!-- s11:begin:{name} -->\n).*?(\n<!-- s11:end:{name} -->)", re.S)
        claim(len(pattern.findall(doc_text)) == 1, f"GC-V3-6: block {name} not found once")
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
        same_doc = new_doc == doc_text  # GC-V3-6: the document's generated blocks are current
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
