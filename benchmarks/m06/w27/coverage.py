"""W27's coverage classifier: every case of the archive, a class and every applicable reason.

Normative text: registration §5 (W27-R08…R25), with R-176 and R-177. Inputs: the case facts
(`facts.py`, or the committed `case_facts.json`), a registry snapshot (`snapshot.py`, W27-R22)
and `registration.json`'s tables. The classifier is deterministic and reads nothing else.

- Units (§5.4): a unit is available iff some snapshot model performs its function **and** offers
  every token it requires; a function match with a missing token is `partial`, and partial is
  unavailable. `junction` needs no model. Which models (W27-R62, Amendment 2): when the case's
  non-reaction packages form one method group and a route serves it, that route's `model_ids`
  only (the row's `units_judged_on` names the route); otherwise every model of the snapshot.
- Components (§5.5): identity by CAS RN through the alias table; available iff a non-synthetic
  record of some snapshot route carries that CAS RN. Ions and unidentified names never are.
- Property routes (§5.6): non-reaction packages grouped by method; with one route per revision
  and more than one group, every package is refused `multiple_routes_per_revision`; otherwise a
  group needs a route of **the same method** admitting every available component in every phase
  kind the group declares.
- Refusals (W27-R24): a snapshot holding a model id, provider id, or registry chemical spelling
  the registration does not map, (d) whose `routes_per_revision` is not 1 or two of whose routes
  share a method, or (e) whose routes list a model id that is not among its models, or leave a
  model on no route, stops classification (`RefusalError`), naming every item; no `coverage.json`
  is written. A gap in the tables is the design lane's amendment, never a local default.

Registration version 2 (`docs/derivations/W27-registration-v2.md`, W27v2-R01): every public
function takes a keyword-only `registration_version`, default 1. Version 1 is the code above and
is unchanged; version 2 dispatches at the top of each function to the `_v2` functions at the end
of this module, which read `registration_v2.json` and reuse version 1's helpers wherever the
rules are version 1's. Version 2 judges several routes of one method (W27v2-R04…R06), restates
the refusals (W27v2-R07, R08) and writes a `w27-coverage-v2` record (W27v2-R09).

Registration version 3 (`docs/derivations/W27-registration-v3.md`, W27v3-R01) is version 2 with
S11's rows added to its tables (`registration_v3.json`: W27v3-R02…R04) and a route identified by
its key `(provider_id, record_source, components)` instead of its provider id: a duplicate key is
refused (W27v3-R06) and serving routes are ordered by key (W27v3-R07). It writes a
`w27-coverage-v3` record under version 2's output-path rules.

Run: `python -m benchmarks.m06.w27.coverage [--out PATH]` writes `coverage.json` (W27-R25) for
the build at hand, or exits 2 naming the refusal. `--registration-version 2` (or `3`) needs an
`--out` other than the committed `coverage.json` (W27v2-R09, C2 SPLIT-R10).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from benchmarks.m06.w27 import facts, registration

SCHEMA: Final[str] = "w27-coverage-v1"
#: W27v2-R09: the version 2 coverage record.
SCHEMA_V2: Final[str] = "w27-coverage-v2"
#: W27v2-R09: version 2's refusal of an output path, before any case is classified.
SPLIT_R10_REFUSAL: Final[str] = (
    "registration version 2 has no default output path and never writes the committed "
    "coverage.json; pass --out to another path (W27v2-R09, C2 SPLIT-R10: a record over every "
    "case holds held-out ids and goes under a heldout/ path)"
)
#: R-580: version 2's refusal of an output path outside a `heldout/` directory.
HELDOUT_PATH_REFUSAL: Final[str] = (
    "registration version 2 writes a record over every case, held-out ids included; --out must "
    "have a directory segment named heldout (C2 SPLIT-R10 (b), SPLIT-R11; R-580)"
)
#: W27v3-R01: the version 3 coverage record, and version 2's two path refusals in its words.
SCHEMA_V3: Final[str] = "w27-coverage-v3"
SPLIT_R10_REFUSAL_V3: Final[str] = SPLIT_R10_REFUSAL.replace("version 2", "version 3", 1)
HELDOUT_PATH_REFUSAL_V3: Final[str] = HELDOUT_PATH_REFUSAL.replace("version 2", "version 3", 1)


class RefusalError(Exception):
    """W27-R24: a snapshot this registration cannot judge. Nothing is classified."""


def _table(*path: str) -> Any:
    node: Any = registration.load()
    for key in path:
        node = node[key]
    return node


# =================================================================================================
# §5.4 units
# =================================================================================================


def unit_aliases(unit: Mapping[str, Any]) -> set[str]:
    """W27-R40: the strings a limitation may name a unit group by."""
    aliases = {str(unit["key"]).split(":", 1)[1]}
    for name in unit["names"]:
        aliases |= {name, name.split(".")[-1]}
    if "class_leaf" in unit:
        aliases.add(unit["class_leaf"])
    if "topology_kind" in unit:
        aliases.add(unit["topology_kind"])
    return aliases


def unit_requirement(unit: Mapping[str, Any]) -> tuple[str | None, list[str], str | None]:
    """W27-R12/R13: `(function, required tokens, why none)` for one case unit group."""
    keys: Mapping[str, Mapping[str, Any]] = _table("units", "keys")
    reviewed: Mapping[str, str] = _table("units", "reviewed_none")
    key = unit["key"]
    config = unit.get("config", {})
    tokens: list[str] = ["dynamic"] if config.get("dynamic") is True else []
    if key not in keys:
        return None, tokens, reviewed.get(key, "no_function")
    entry = keys[key]
    function = entry["function"]
    tokens += list(entry.get("tokens", []))
    rule = entry.get("rule")
    if rule == "mixer":
        if config.get("has_phase_equilibrium") is True:
            tokens.append("mixer_phase_equilibrium")
        if config.get("energy_mixing_type") == "none":
            tokens.append("mixer_no_energy_balance")
        if config.get("momentum_mixing_type") == "none":
            tokens.append("mixer_no_momentum_balance")
    elif rule == "separator":
        basis = config.get("split_basis")
        if basis == "componentFlow":
            function = "component_separator"
        elif basis in ("phaseFlow", "phaseComponentFlow"):
            tokens.append("phase_split_basis")
        outlets = config.get("outlet_list")
        if outlets is None and isinstance(config.get("num_outlets"), int):
            outlets = config["num_outlets"]
        if isinstance(outlets, int) and outlets > 2:
            tokens.append("outlets_gt_2")
        if config.get("ideal_separation") is True:
            tokens.append("ideal_separation")
        if config.get("has_phase_equilibrium") is True:
            tokens.append("separator_phase_equilibrium")
        split = config.get("energy_split_basis")
        if split is not None and split != "equal_temperature":
            tokens.append("energy_split_basis_other")
    elif rule == "pressure_changer":
        assumption = config.get("thermodynamic_assumption")
        compressor = config.get("compressor")
        if assumption == "pump":
            function = "pump"
        elif assumption == "isentropic":
            function = "compressor" if compressor is True else "expander"
        elif assumption == "adiabatic" and compressor is False:
            function = "valve"
        else:
            return None, tokens, "defining_relation_absent"
    return function, sorted(set(tokens)), None


# =================================================================================================
# §5.5 components
# =================================================================================================


def component_identity(name: str) -> tuple[str, str | None]:
    """W27-R15: `chemical` with its CAS RN, an `ion`, or `unidentified`."""
    aliases: Mapping[str, str] = _table("components", "aliases")
    if name in aliases:
        return "chemical", aliases[name]
    if re.search(str(_table("components", "ion_pattern")), name):
        return "ion", None
    return "unidentified", None


def declared_components(case: Mapping[str, Any]) -> list[str]:
    """W27-R05: the components the case lists, plus those its packages define intrinsically."""
    intrinsic: Mapping[str, Sequence[str]] = _table("components", "intrinsic")
    names = set(case["listed_components"])
    for package in case["packages"]:
        names |= set(intrinsic.get(package["key"], []))
    return sorted(names)


# =================================================================================================
# §5.7 refusals
# =================================================================================================


def check_snapshot(
    snapshot: Mapping[str, Any],
    case_facts: Mapping[str, Any],
    provider_methods: Mapping[str, str] | None = None,
    *,
    registration_version: int = 1,
) -> None:
    """W27-R24: refuse what the registration cannot judge, naming every item. Version 2:
    W27v2-R07; version 3: W27v3-R06."""
    if _version(registration_version) == 3:
        _check_snapshot_v3(snapshot, case_facts, provider_methods)
        return
    if registration_version == 2:
        _check_snapshot_v2(snapshot, case_facts, provider_methods)
        return
    methods = registration.provider_methods() if provider_methods is None else provider_methods
    model_functions: Mapping[str, Any] = _table("units", "model_functions")
    aliases: Mapping[str, str] = _table("components", "aliases")
    unknown_models = sorted(
        m["model_id"] for m in snapshot["models"] if m["model_id"] not in model_functions
    )
    unknown_providers = sorted(
        r["provider_id"] for r in snapshot["routes"] if r["provider_id"] not in methods
    )
    unaliased: list[str] = []
    names = {c for case in case_facts["cases"] for c in declared_components(case)}
    for route in snapshot["routes"]:
        for component in route["components"]:
            if component["synthetic"]:
                continue
            spellings = {
                str(component.get(k)).casefold()
                for k in ("id", "name", "formula")
                if component.get(k)
            }
            for name in names:
                if name.casefold() in spellings and aliases.get(name) != component["cas"]:
                    unaliased.append(f"{name}->{component['cas']}")
    problems = []
    if unknown_models:
        problems.append(f"unregistered model ids {unknown_models}")
    if unknown_providers:
        problems.append(f"unregistered provider ids {unknown_providers}")
    if unaliased:
        problems.append(f"archive spellings of registry chemicals not aliased {sorted(unaliased)}")
    # (d), Amendment 2: W27-R62 is registered for one route per revision and one route per method.
    if snapshot["routes_per_revision"] != 1:
        problems.append(f"routes_per_revision {snapshot['routes_per_revision']} is not 1")
    per_method = Counter(
        methods[r["provider_id"]] for r in snapshot["routes"] if r["provider_id"] in methods
    )
    shared = sorted(m for m, n in per_method.items() if n > 1)
    if shared:
        problems.append(f"routes sharing a method {shared}")
    # (e): the routes' model ids are the snapshot's models, and every model is on a route.
    listed = {m["model_id"] for m in snapshot["models"]}
    on_routes = {m for r in snapshot["routes"] for m in r["model_ids"]}
    if on_routes - listed:
        problems.append(f"route model ids not among the models {sorted(on_routes - listed)}")
    if listed - on_routes:
        problems.append(f"models on no route {sorted(listed - on_routes)}")
    if problems:
        raise RefusalError("; ".join(problems))


# =================================================================================================
# §5.1–§5.6 one case
# =================================================================================================


def _not_steady_rules(case: Mapping[str, Any]) -> list[str]:
    """W27-R10: every rule n1…n6 that fires."""
    model_types = set(_table("not_steady_state", "model_types"))
    kinds_table = set(_table("not_steady_state", "topology_kinds"))
    fired = []
    if case["model_type"] in model_types:
        fired.append(f"n1:model_type={case['model_type']}")
    if any(u.get("config", {}).get("dynamic") is True for u in case["units"]):
        fired.append("n2:dynamic_unit")
    if case["steady_state"] is False:
        fired.append("n3:steady_state=false")
    dof = case["expected_dof"]
    if dof is not None and not (isinstance(dof, int) and not isinstance(dof, bool) and dof == 0):
        fired.append("n4:expected_dof_not_0")
    kinds = sorted(set(case["topology_kinds"]) & kinds_table)
    if kinds:
        fired.append("n5:topology_kinds=" + ",".join(kinds))
    if case["objective_declared"] or case["solve_dynamic"]:
        fired.append("n6:objective_or_dynamic_declared")
    return fired


def _judging_models(snapshot: Mapping[str, Any], serving: str | None) -> list[str]:
    """W27-R62: the serving route's `model_ids`, or every model of the snapshot when no route
    serves the case's single method group."""
    if serving is None:
        return sorted(m["model_id"] for m in snapshot["models"])
    (route,) = [r for r in snapshot["routes"] if r["provider_id"] == serving]
    return sorted(route["model_ids"])


def _unit_reasons(
    case: Mapping[str, Any],
    model_ids: Sequence[str],
    model_functions: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """W27-R12/R13 for every unit group, against the models `model_ids` (W27-R62), with version
    1's model table unless another is given (version 3: W27v3-R04's)."""
    if model_functions is None:
        model_functions = _table("units", "model_functions")
    by_function: dict[str | None, list[tuple[str, set[str]]]] = {}
    for model_id in model_ids:
        entry = model_functions[model_id]
        by_function.setdefault(entry["function"], []).append((model_id, set(entry["offers"])))
    rows: list[dict[str, Any]] = []
    unavailable: dict[str, dict[str, Any]] = {}
    for unit in case["units"]:
        function, tokens, why_none = unit_requirement(unit)
        models: list[str] = []
        if function == "junction":
            available, detail = True, "junction"
        elif function is None:
            available, detail = False, f"no_function:{why_none}"
        else:
            candidates = by_function.get(function, [])
            models = sorted(model for model, offers in candidates if set(tokens) <= offers)
            available = bool(models)
            if available:
                detail = "available"
            elif candidates:
                detail = f"partial:{function}:missing=" + ",".join(tokens)
            else:
                detail = f"no_model:{function}"
        rows.append(
            {
                "names": unit["names"],
                "key": unit["key"],
                "function": function,
                "tokens": tokens,
                "available": available,
                "models": models,
                "detail": detail,
            }
        )
        if not available:
            slot = unavailable.setdefault(
                unit["key"], {"details": set(), "aliases": set(), "units": []}
            )
            slot["details"].add(detail)
            slot["aliases"] |= unit_aliases(unit)
            slot["units"] += unit["names"]
    reasons = []
    for key in sorted(unavailable):
        slot = unavailable[key]
        subject = key.split(":", 1)[1]
        reasons.append(
            {
                "kind": "UNIT_UNAVAILABLE",
                "subject": subject,
                "detail": ";".join(sorted(slot["details"])) + " units=" + ",".join(slot["units"]),
                "aliases": sorted(slot["aliases"] | {subject}),
            }
        )
    return rows, reasons


def _component_reasons(
    case: Mapping[str, Any], snapshot: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    registry_cas: set[str] = {
        component["cas"]
        for route in snapshot["routes"]
        for component in route["components"]
        if not component["synthetic"] and component.get("cas")
    }
    rows: list[dict[str, Any]] = []
    reasons: list[dict[str, Any]] = []
    declared = declared_components(case)
    if not declared:
        reasons.append(
            {
                "kind": "COMPONENT_UNAVAILABLE",
                "subject": None,
                "detail": "components_not_declared",
                "aliases": [],
            }
        )
    for name in declared:
        kind, cas = component_identity(name)
        available = kind == "chemical" and cas in registry_cas
        rows.append({"name": name, "class": kind, "cas": cas, "available": available})
        if not available:
            reasons.append(
                {
                    "kind": "COMPONENT_UNAVAILABLE",
                    "subject": name,
                    "detail": kind + (f":{cas}:not_in_registry" if cas else ""),
                    "aliases": [name],
                }
            )
    return rows, reasons


def _route_detail(
    method: str,
    phases: Sequence[str],
    available_cas: Sequence[str],
    snapshot: Mapping[str, Any],
    methods: Mapping[str, str],
) -> tuple[str | None, str | None]:
    """W27-R20 for one group: `(the serving route's provider id, None)` when a route serves it,
    else `(None, why none does)`."""
    routes = [r for r in snapshot["routes"] if methods[r["provider_id"]] == method]
    if not routes:
        return None, f"no_route:{method}"
    detail: str | None = None
    for route in routes:
        admitted = {
            c["cas"]: set(c["phases"])
            for c in route["components"]
            if not c["synthetic"] and c.get("cas")
        }
        missing = [cas for cas in available_cas if cas not in admitted]
        bad_phase = [
            f"{cas}:{p}"
            for cas in available_cas
            if cas in admitted
            for p in phases
            if p in ("vapor", "liquid", "solid") and p not in admitted[cas]
        ]
        if not missing and not bad_phase:
            return str(route["provider_id"]), None
        detail = (
            f"route_mismatch:{route['provider_id']}:missing="
            + ",".join(missing)
            + ":phase="
            + ",".join(bad_phase)
        )
    return None, detail


def _route_reasons(
    case: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    component_rows: Sequence[Mapping[str, Any]],
    methods: Mapping[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str | None]:
    """W27-R19/R20: package rows, route reasons, and the provider id of the route serving the
    case's one method group (`None` for no package, several groups, or no serving route)."""
    package_methods: Mapping[str, str] = _table("routes", "package_methods")
    available_cas = sorted({c["cas"] for c in component_rows if c["available"]})
    rows: list[dict[str, Any]] = []
    groups: dict[str, list[tuple[Mapping[str, Any], dict[str, Any]]]] = {}
    for package in case["packages"]:
        method = package_methods[package["key"]]
        row: dict[str, Any] = {"name": package["name"], "key": package["key"], "method": method}
        rows.append(row)
        if method != "reaction":
            groups.setdefault(method, []).append((package, row))
    route_aliases = set(case["topology_package_names"]) | set(case["topology_entry_ids"])
    multiple = len(groups) > 1 and snapshot["routes_per_revision"] == 1
    reasons: list[dict[str, Any]] = []
    serving: str | None = None
    for method in sorted(groups):
        members = groups[method]
        phases = sorted({p for package, _ in members for p in package["phases"]})
        if multiple:
            detail: str | None = "multiple_routes_per_revision:" + ",".join(sorted(groups))
        else:
            route, detail = _route_detail(method, phases, available_cas, snapshot, methods)
            if len(groups) == 1:
                serving = route
        for _, row in members:
            row["available"] = detail is None
            row["detail"] = detail or "available"
        if detail is None:
            continue
        for package, _ in members:
            aliases = {package["name"], package["name"].split(".")[-1], package["key"]}
            aliases |= set(package["classes"]) | {facts.leaf(c) for c in package["classes"]}
            aliases |= route_aliases
            reasons.append(
                {
                    "kind": "PROPERTY_ROUTE_UNAVAILABLE",
                    "subject": package["name"],
                    "detail": detail,
                    "aliases": sorted(aliases),
                }
            )
    for row in rows:
        if row["method"] == "reaction":
            row["available"] = None
            row["detail"] = "reaction_package_not_a_route"
    if not groups:
        reasons.append(
            {
                "kind": "PROPERTY_ROUTE_UNAVAILABLE",
                "subject": None,
                "detail": "no_property_package_declared",
                "aliases": [],
            }
        )
    return rows, reasons, serving


def classify_case(
    case: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    provider_methods: Mapping[str, str] | None = None,
    *,
    registration_version: int = 1,
) -> dict[str, Any]:
    """W27-R08: every applicable reason, then the class by precedence. The snapshot must have
    passed `check_snapshot` (of the same registration version)."""
    if _version(registration_version) in (2, 3):
        return _classify_case_v2(case, snapshot, provider_methods, version=registration_version)
    methods = registration.provider_methods() if provider_methods is None else provider_methods
    reasons: list[dict[str, Any]] = []
    if case["files_missing"] or case["parse_errors"]:
        reasons.append(
            {
                "kind": "ARTIFACT_INCOMPLETE",
                "subject": None,
                "detail": "missing:" + ",".join(case["files_missing"] + case["parse_errors"]),
                "aliases": [],
            }
        )
    fired = _not_steady_rules(case)
    if fired:
        reasons.append(
            {
                "kind": "NOT_STEADY_STATE_SIMULATION",
                "subject": None,
                "detail": ";".join(fired),
                "aliases": [],
            }
        )
    component_rows, component_reasons = _component_reasons(case, snapshot)
    package_rows, route_reasons, serving = _route_reasons(case, snapshot, component_rows, methods)
    unit_rows, unit_reasons = _unit_reasons(case, _judging_models(snapshot, serving))
    reasons += unit_reasons + component_reasons + route_reasons
    kinds = {r["kind"] for r in reasons}
    order = registration.classes()
    klass = next((c for c in order[:-1] if c in kinds), order[-1])
    return {
        "case_id": case["case_id"],
        "family": case["family"],
        "model_type": case["model_type"],
        "in_full82": case["in_full82"],
        "residual_check": case["residual_check"],
        "class": klass,
        "reasons": reasons,
        "units_judged_on": serving,
        "units": unit_rows,
        "components": component_rows,
        "packages": package_rows,
    }


# =================================================================================================
# §5.8 the coverage record
# =================================================================================================


def summarise(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """W27-R25's summaries: class counts, cases carrying each reason kind, per family."""
    order = registration.classes()

    def table(selected: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        counted = Counter(r["class"] for r in selected)
        carried = Counter(k for r in selected for k in sorted({x["kind"] for x in r["reasons"]}))
        families: dict[str, dict[str, int]] = {}
        for r in selected:
            families.setdefault(r["family"], dict.fromkeys(order, 0))[r["class"]] += 1
        return {
            "total": len(selected),
            "classes": {c: counted.get(c, 0) for c in order},
            "cases_with_reason": {c: carried.get(c, 0) for c in order[:-1]},
            "by_family": dict(sorted(families.items())),
        }

    return {"all_450": table(rows), "full82": table([r for r in rows if r["in_full82"]])}


def classify(
    case_facts: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    provider_methods: Mapping[str, str] | None = None,
    *,
    registration_version: int = 1,
) -> dict[str, Any]:
    """Every case of `case_facts` against `snapshot`: `{rows, summary}`. Refuses (W27-R24;
    version 2: W27v2-R07; version 3: W27v3-R06)."""
    if _version(registration_version) in (2, 3):
        return _classify_v2(case_facts, snapshot, provider_methods, version=registration_version)
    check_snapshot(snapshot, case_facts, provider_methods)
    rows = [classify_case(case, snapshot, provider_methods) for case in case_facts["cases"]]
    return {"rows": rows, "summary": summarise(rows)}


def coverage_document(
    case_facts: Mapping[str, Any], snapshot: Mapping[str, Any], *, registration_version: int = 1
) -> dict[str, Any]:
    """W27-R25's `coverage.json`, with the input digests. Refuses (W27-R24). Version 2:
    W27v2-R09's record, which has no default path; version 3 likewise, as `w27-coverage-v3`."""
    if _version(registration_version) == 3:
        return _coverage_document_v3(case_facts, snapshot)
    if registration_version == 2:
        return _coverage_document_v2(case_facts, snapshot)
    classified = classify(case_facts, snapshot)
    return {
        "schema": SCHEMA,
        "snapshot": snapshot,
        "snapshot_sha256": registration.sha256_bytes(registration.dump(snapshot)),
        "list_models_sha256": snapshot["list_models_sha256"],
        "registration_sha256": registration.sha256_file(registration.REGISTRATION_JSON),
        "case_facts_sha256": registration.sha256_bytes(facts.dump_facts(case_facts)),
        "rows": classified["rows"],
        "summary": classified["summary"],
    }


def g14(coverage: Mapping[str, Any]) -> dict[str, Any]:
    """W27-R25 / G14: 450/450 rows with a class, every non-`CANDIDATE` row a reason of its class,
    the summaries summing to 450 and 82, both SHA-256 values recorded."""
    order = registration.classes()
    rows = coverage["rows"]
    summary = coverage["summary"]
    with_class = sum(1 for r in rows if r["class"] in order)
    with_reason = sum(
        1
        for r in rows
        if r["class"] == order[-1] or any(x["kind"] == r["class"] for x in r["reasons"])
    )
    recount = summarise(rows)
    sums = {
        "all_450": sum(summary["all_450"]["classes"].values()),
        "full82": sum(summary["full82"]["classes"].values()),
    }
    digests = {
        "list_models_sha256": coverage.get("list_models_sha256"),
        "snapshot_sha256": coverage.get("snapshot_sha256"),
    }
    recorded = all(isinstance(v, str) and len(v) == 64 for v in digests.values())
    snapshot_ok = coverage.get("snapshot_sha256") == registration.sha256_bytes(
        registration.dump(coverage["snapshot"])
    )
    passed = (
        len(rows) == 450
        and with_class == 450
        and with_reason == 450
        and sums == {"all_450": 450, "full82": 82}
        and recount == summary
        and recorded
        and snapshot_ok
    )
    return {
        "passed": passed,
        "rows": len(rows),
        "rows_with_class": with_class,
        "rows_with_reason_of_their_class": with_reason,
        "summary_sums": sums,
        "summary_recounts": recount == summary,
        "digests": digests,
        "snapshot_sha256_matches_snapshot": snapshot_ok,
    }


# =================================================================================================
# Registration version 2 (W27-registration-v2.md: W27v2-R01, R04…R09)
# =================================================================================================


def _version(registration_version: int) -> int:
    """W27v2-R01, W27v3-R01: the registration version is 1, 2 or 3; nothing else is selected
    implicitly."""
    if isinstance(registration_version, bool) or registration_version not in (1, 2, 3):
        raise ValueError(f"registration version {registration_version!r} is not 1, 2 or 3")
    return registration_version


def _check_snapshot_v2(
    snapshot: Mapping[str, Any],
    case_facts: Mapping[str, Any],
    provider_methods: Mapping[str, str] | None,
) -> None:
    """W27v2-R07 (a)–(e), with W27v2-R08's spelling rule for (c), in version 1's message forms."""
    methods = registration.provider_methods(2) if provider_methods is None else provider_methods
    model_functions: Mapping[str, Any] = _table("units", "model_functions")
    unknown_models = sorted(
        m["model_id"] for m in snapshot["models"] if m["model_id"] not in model_functions
    )
    unknown_providers = sorted(
        r["provider_id"] for r in snapshot["routes"] if r["provider_id"] not in methods
    )
    unaliased = _unaliased_v2(snapshot, case_facts)
    problems = []
    if unknown_models:
        problems.append(f"unregistered model ids {unknown_models}")
    if unknown_providers:
        problems.append(f"unregistered provider ids {unknown_providers}")
    if unaliased:
        problems.append(f"archive spellings of registry chemicals not aliased {sorted(unaliased)}")
    # (d): one route per revision stands; W27v2-R05's tie-break key, the provider id, is unique.
    if snapshot["routes_per_revision"] != 1:
        problems.append(f"routes_per_revision {snapshot['routes_per_revision']} is not 1")
    per_provider = Counter(r["provider_id"] for r in snapshot["routes"])
    duplicate = sorted(p for p, n in per_provider.items() if n > 1)
    if duplicate:
        problems.append(f"duplicate provider ids {duplicate}")
    problems += _models_on_routes(snapshot)
    if problems:
        raise RefusalError("; ".join(problems))


def _unaliased_v2(snapshot: Mapping[str, Any], case_facts: Mapping[str, Any]) -> set[str]:
    """W27v2-R08's (c): every `<archive spelling>-><CAS RN>` that collides with a registry
    record's spelling without an alias to its CAS RN."""
    aliases: Mapping[str, str] = _table("components", "aliases")
    distinct = registration.case_distinct()
    unaliased: set[str] = set()
    names = {c for case in case_facts["cases"] for c in declared_components(case)}
    for route in snapshot["routes"]:
        for component in route["components"]:
            if component["synthetic"]:
                continue
            cas = component["cas"]
            spellings = {
                str(component.get(k)) for k in ("id", "name", "formula") if component.get(k)
            }
            folded = {spelling.casefold() for spelling in spellings}
            for name in names:
                if aliases.get(name) == cas:
                    continue
                # W27v2-R08: an exact spelling is refused; a case-only one unless reviewed distinct.
                if name in spellings or (
                    name.casefold() in folded and cas not in distinct.get(name, frozenset())
                ):
                    unaliased.add(f"{name}->{cas}")
    return unaliased


def _models_on_routes(snapshot: Mapping[str, Any]) -> list[str]:
    """(e), unchanged from version 1: the routes' model ids are the snapshot's models, and every
    model is on a route."""
    problems = []
    listed = {m["model_id"] for m in snapshot["models"]}
    on_routes = {m for r in snapshot["routes"] for m in r["model_ids"]}
    if on_routes - listed:
        problems.append(f"route model ids not among the models {sorted(on_routes - listed)}")
    if listed - on_routes:
        problems.append(f"models on no route {sorted(listed - on_routes)}")
    return problems


def _serving_routes_v2(
    method: str,
    phases: Sequence[str],
    available_cas: Sequence[str],
    snapshot: Mapping[str, Any],
    methods: Mapping[str, str],
) -> tuple[list[str], str | None]:
    """W27v2-R04/R06 for one group: `(the serving routes' provider ids, None)` when at least one
    route of `method` serves it, else `([], why none does)`. The per-route test and its detail
    are version 1's `_route_detail`, applied to one route at a time."""
    routes = sorted(
        (r for r in snapshot["routes"] if methods[r["provider_id"]] == method),
        key=lambda r: str(r["provider_id"]),
    )
    if not routes:
        return [], f"no_route:{method}"
    serving: list[str] = []
    details: list[str] = []
    for route in routes:
        provider, detail = _route_detail(
            method, phases, available_cas, {"routes": [route]}, methods
        )
        if provider is not None:
            serving.append(provider)
        elif detail is not None:
            details.append(detail)
    if serving:
        return serving, None
    return [], ";".join(details)


def _route_reasons_v2(
    case: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    component_rows: Sequence[Mapping[str, Any]],
    methods: Mapping[str, str],
    serving_routes: Callable[..., tuple[list[Any], str | None]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[Any]]:
    """`_route_reasons` under W27v2-R04/R06: package rows, route reasons, and the provider ids of
    every route serving the case's one method group (empty for no package, several groups, or no
    serving route). Version 3 passes `_serving_routes_v3`, and gets route keys."""
    if serving_routes is None:
        serving_routes = _serving_routes_v2
    package_methods: Mapping[str, str] = _table("routes", "package_methods")
    available_cas = sorted({c["cas"] for c in component_rows if c["available"]})
    rows: list[dict[str, Any]] = []
    groups: dict[str, list[tuple[Mapping[str, Any], dict[str, Any]]]] = {}
    for package in case["packages"]:
        method = package_methods[package["key"]]
        row: dict[str, Any] = {"name": package["name"], "key": package["key"], "method": method}
        rows.append(row)
        if method != "reaction":
            groups.setdefault(method, []).append((package, row))
    route_aliases = set(case["topology_package_names"]) | set(case["topology_entry_ids"])
    multiple = len(groups) > 1 and snapshot["routes_per_revision"] == 1
    reasons: list[dict[str, Any]] = []
    serving: list[Any] = []
    for method in sorted(groups):
        members = groups[method]
        phases = sorted({p for package, _ in members for p in package["phases"]})
        if multiple:
            detail: str | None = "multiple_routes_per_revision:" + ",".join(sorted(groups))
        else:
            routes, detail = serving_routes(method, phases, available_cas, snapshot, methods)
            if len(groups) == 1:
                serving = routes
        for _, row in members:
            row["available"] = detail is None
            row["detail"] = detail or "available"
        if detail is None:
            continue
        for package, _ in members:
            aliases = {package["name"], package["name"].split(".")[-1], package["key"]}
            aliases |= set(package["classes"]) | {facts.leaf(c) for c in package["classes"]}
            aliases |= route_aliases
            reasons.append(
                {
                    "kind": "PROPERTY_ROUTE_UNAVAILABLE",
                    "subject": package["name"],
                    "detail": detail,
                    "aliases": sorted(aliases),
                }
            )
    for row in rows:
        if row["method"] == "reaction":
            row["available"] = None
            row["detail"] = "reaction_package_not_a_route"
    if not groups:
        reasons.append(
            {
                "kind": "PROPERTY_ROUTE_UNAVAILABLE",
                "subject": None,
                "detail": "no_property_package_declared",
                "aliases": [],
            }
        )
    return rows, reasons, serving


def _units_v2(
    case: Mapping[str, Any], snapshot: Mapping[str, Any], serving: Sequence[str]
) -> tuple[str | None, list[dict[str, Any]], list[dict[str, Any]]]:
    """W27v2-R05: `(units_judged_on, unit rows, unit reasons)`. The units are judged on the
    serving route with the fewest `UNIT_UNAVAILABLE` reasons, ties to the smallest provider id;
    with no serving route, on every model of the snapshot and `units_judged_on` null."""
    if not serving:
        rows, reasons = _unit_reasons(case, _judging_models(snapshot, None))
        return None, rows, reasons
    judged = []
    for provider in serving:
        rows, reasons = _unit_reasons(case, _judging_models(snapshot, provider))
        count = sum(1 for r in reasons if r["kind"] == "UNIT_UNAVAILABLE")
        judged.append((count, provider, rows, reasons))
    _, provider, rows, reasons = min(judged, key=lambda j: (j[0], j[1]))
    return provider, rows, reasons


def _classify_case_v2(
    case: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    provider_methods: Mapping[str, str] | None,
    *,
    version: int = 2,
) -> dict[str, Any]:
    """`classify_case` under W27v2-R04…R06. Every other step, and the row's form, is version
    1's; W27v2-R10 (A20) pins that the two agree wherever version 1 classifies. `version=3`
    identifies the serving routes by key (W27v3-R07) and reads version 3's tables."""
    methods = (
        registration.provider_methods(version) if provider_methods is None else provider_methods
    )
    reasons: list[dict[str, Any]] = []
    if case["files_missing"] or case["parse_errors"]:
        reasons.append(
            {
                "kind": "ARTIFACT_INCOMPLETE",
                "subject": None,
                "detail": "missing:" + ",".join(case["files_missing"] + case["parse_errors"]),
                "aliases": [],
            }
        )
    fired = _not_steady_rules(case)
    if fired:
        reasons.append(
            {
                "kind": "NOT_STEADY_STATE_SIMULATION",
                "subject": None,
                "detail": ";".join(fired),
                "aliases": [],
            }
        )
    component_rows, component_reasons = _component_reasons(case, snapshot)
    if version == 3:
        package_rows, route_reasons, serving = _route_reasons_v2(
            case, snapshot, component_rows, methods, _serving_routes_v3
        )
        judged_on, unit_rows, unit_reasons = _units_v3(case, snapshot, serving)
    else:
        package_rows, route_reasons, serving = _route_reasons_v2(
            case, snapshot, component_rows, methods
        )
        judged_on, unit_rows, unit_reasons = _units_v2(case, snapshot, serving)
    reasons += unit_reasons + component_reasons + route_reasons
    kinds = {r["kind"] for r in reasons}
    order = registration.classes()
    klass = next((c for c in order[:-1] if c in kinds), order[-1])
    return {
        "case_id": case["case_id"],
        "family": case["family"],
        "model_type": case["model_type"],
        "in_full82": case["in_full82"],
        "residual_check": case["residual_check"],
        "class": klass,
        "reasons": reasons,
        "units_judged_on": judged_on,
        "units": unit_rows,
        "components": component_rows,
        "packages": package_rows,
    }


def _classify_v2(
    case_facts: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    provider_methods: Mapping[str, str] | None,
    *,
    version: int = 2,
) -> dict[str, Any]:
    """`classify` under version 2 (or 3): refuses (W27v2-R07; W27v3-R06), else
    `{rows, summary}`."""
    if version == 3:
        _check_snapshot_v3(snapshot, case_facts, provider_methods)
    else:
        _check_snapshot_v2(snapshot, case_facts, provider_methods)
    rows = [
        _classify_case_v2(case, snapshot, provider_methods, version=version)
        for case in case_facts["cases"]
    ]
    return {"rows": rows, "summary": summarise(rows)}


def _coverage_document_v2(
    case_facts: Mapping[str, Any], snapshot: Mapping[str, Any]
) -> dict[str, Any]:
    """W27v2-R09: version 1's members with their version 1 meanings, plus the version and the
    SHA-256 of `registration_v2.json`, under schema `w27-coverage-v2`."""
    classified = _classify_v2(case_facts, snapshot, None)
    return {
        "schema": SCHEMA_V2,
        "registration_version": 2,
        "snapshot": snapshot,
        "snapshot_sha256": registration.sha256_bytes(registration.dump(snapshot)),
        "list_models_sha256": snapshot["list_models_sha256"],
        "registration_sha256": registration.sha256_file(registration.REGISTRATION_JSON),
        "registration_v2_sha256": registration.sha256_file(registration.REGISTRATION_V2_JSON),
        "case_facts_sha256": registration.sha256_bytes(facts.dump_facts(case_facts)),
        "rows": classified["rows"],
        "summary": classified["summary"],
    }


# =================================================================================================
# Registration version 3 (W27-registration-v3.md: W27v3-R01, R04, R06, R07)
# =================================================================================================


def route_key(route: Mapping[str, Any]) -> tuple[str, str, str]:
    """W27v3-R06/R07: a route's key, `(provider_id, record_source, the component ids joined by
    ',')`, compared in code-point order."""
    return (
        str(route["provider_id"]),
        str(route["record_source"]),
        ",".join(str(c["id"]) for c in route["components"]),
    )


def _check_snapshot_v3(
    snapshot: Mapping[str, Any],
    case_facts: Mapping[str, Any],
    provider_methods: Mapping[str, str] | None,
) -> None:
    """W27v2-R07 with version 3's tables (W27v3-R02, R04), W27v3-R09's spelling rule for (c) and
    W27v3-R06's (d): two routes with one key are refused, in place of two routes with one
    provider id. A route with no `record_source` has no key and is refused."""
    methods = registration.provider_methods(3) if provider_methods is None else provider_methods
    model_functions = registration.model_functions(3)
    unknown_models = sorted(
        m["model_id"] for m in snapshot["models"] if m["model_id"] not in model_functions
    )
    unknown_providers = sorted(
        r["provider_id"] for r in snapshot["routes"] if r["provider_id"] not in methods
    )
    # W27v3-R09: a non-synthetic record with no CAS RN can match no case component (W27-R15), so
    # it takes no part in W27v2-R08; records with a CAS RN keep W27v2-R08 unchanged.
    keyed = {
        "routes": [
            {"components": [c for c in r["components"] if c["synthetic"] or c.get("cas")]}
            for r in snapshot["routes"]
        ]
    }
    unaliased = _unaliased_v2(keyed, case_facts)
    problems = []
    if unknown_models:
        problems.append(f"unregistered model ids {unknown_models}")
    if unknown_providers:
        problems.append(f"unregistered provider ids {unknown_providers}")
    if unaliased:
        problems.append(f"archive spellings of registry chemicals not aliased {sorted(unaliased)}")
    if snapshot["routes_per_revision"] != 1:
        problems.append(f"routes_per_revision {snapshot['routes_per_revision']} is not 1")
    unkeyed = sorted(
        {str(r["provider_id"]) for r in snapshot["routes"] if not r.get("record_source")}
    )
    if unkeyed:
        problems.append(f"routes with no record_source {unkeyed}")
    else:
        per_key = Counter(route_key(r) for r in snapshot["routes"])
        duplicate = sorted(k for k, n in per_key.items() if n > 1)
        if duplicate:
            problems.append(f"duplicate route keys {duplicate}")
    problems += _models_on_routes(snapshot)
    if problems:
        raise RefusalError("; ".join(problems))


def _serving_routes_v3(
    method: str,
    phases: Sequence[str],
    available_cas: Sequence[str],
    snapshot: Mapping[str, Any],
    methods: Mapping[str, str],
) -> tuple[list[tuple[str, str, str]], str | None]:
    """`_serving_routes_v2` with routes ordered and named by key (W27v3-R07): `(the serving
    routes' keys, None)`, else `([], every route's mismatch, in key order)`."""
    routes = sorted(
        (r for r in snapshot["routes"] if methods[r["provider_id"]] == method), key=route_key
    )
    if not routes:
        return [], f"no_route:{method}"
    serving: list[tuple[str, str, str]] = []
    details: list[str] = []
    for route in routes:
        provider, detail = _route_detail(
            method, phases, available_cas, {"routes": [route]}, methods
        )
        if provider is not None:
            serving.append(route_key(route))
        elif detail is not None:
            details.append(detail)
    if serving:
        return serving, None
    return [], ";".join(details)


def _units_v3(
    case: Mapping[str, Any], snapshot: Mapping[str, Any], serving: Sequence[tuple[str, str, str]]
) -> tuple[str | None, list[dict[str, Any]], list[dict[str, Any]]]:
    """W27v2-R05 with W27v3-R07's tie-break: the units are judged on the serving route with the
    fewest `UNIT_UNAVAILABLE` reasons, ties to the smallest route key, against version 3's model
    table. `units_judged_on` is that route's provider id (the row's form is version 2's)."""
    model_functions = registration.model_functions(3)
    if not serving:
        rows, reasons = _unit_reasons(case, _judging_models(snapshot, None), model_functions)
        return None, rows, reasons
    by_key = {route_key(r): r for r in snapshot["routes"]}
    judged = []
    for key in serving:
        rows, reasons = _unit_reasons(case, sorted(by_key[key]["model_ids"]), model_functions)
        count = sum(1 for r in reasons if r["kind"] == "UNIT_UNAVAILABLE")
        judged.append((count, key, rows, reasons))
    _, key, rows, reasons = min(judged, key=lambda j: (j[0], j[1]))
    return key[0], rows, reasons


def _coverage_document_v3(
    case_facts: Mapping[str, Any], snapshot: Mapping[str, Any]
) -> dict[str, Any]:
    """W27v3-R01: version 2's record, under schema `w27-coverage-v3`, with the version and the
    SHA-256 of `registration_v3.json` added."""
    classified = _classify_v2(case_facts, snapshot, None, version=3)
    return {
        "schema": SCHEMA_V3,
        "registration_version": 3,
        "snapshot": snapshot,
        "snapshot_sha256": registration.sha256_bytes(registration.dump(snapshot)),
        "list_models_sha256": snapshot["list_models_sha256"],
        "registration_sha256": registration.sha256_file(registration.REGISTRATION_JSON),
        "registration_v2_sha256": registration.sha256_file(registration.REGISTRATION_V2_JSON),
        "registration_v3_sha256": registration.sha256_file(registration.REGISTRATION_V3_JSON),
        "case_facts_sha256": registration.sha256_bytes(facts.dump_facts(case_facts)),
        "rows": classified["rows"],
        "summary": classified["summary"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    from benchmarks.m06.w27 import snapshot as snapshots  # noqa: PLC0415

    parser = argparse.ArgumentParser(description="W27 coverage (Tier 0 item 3) for this build")
    parser.add_argument("--out", type=Path, default=None, help="default: coverage.json (v1)")
    parser.add_argument("--snapshot", type=Path, help="classify against this snapshot JSON")
    parser.add_argument(
        "--registration-version",
        type=int,
        choices=(1, 2, 3),
        default=1,
        help="W27v2-R01, W27v3-R01",
    )
    args = parser.parse_args(argv)
    version = args.registration_version
    split_refusal = SPLIT_R10_REFUSAL_V3 if version == 3 else SPLIT_R10_REFUSAL
    heldout_refusal = HELDOUT_PATH_REFUSAL_V3 if version == 3 else HELDOUT_PATH_REFUSAL
    if version >= 2 and (
        args.out is None or args.out.resolve() == registration.COVERAGE_JSON.resolve()
    ):
        # W27v2-R09: refused before any snapshot is built or case classified.
        print(f"REFUSED: {split_refusal}", file=sys.stderr)
        return 2
    if version >= 2 and args.out is not None and "heldout" not in args.out.resolve().parent.parts:
        # R-580: also before any snapshot is built or case classified.
        print(f"REFUSED: {heldout_refusal}", file=sys.stderr)
        return 2
    out: Path = registration.COVERAGE_JSON if args.out is None else args.out
    try:
        snap = (
            json.loads(args.snapshot.read_bytes())
            if args.snapshot
            else snapshots.build_snapshot(registration_version=3 if version == 3 else 1)
        )
        document = coverage_document(facts.load_facts(), snap, registration_version=version)
    except (RefusalError, snapshots.SnapshotUnsupportedError) as refusal:
        print(f"REFUSED: {refusal}", file=sys.stderr)
        return 2
    verdict = g14(document)
    out.write_bytes(registration.dump(document))
    print(f"wrote {out}: snapshot {document['snapshot_sha256']}")
    if version >= 2:
        # R-580: no class counts over all 450 or the full 82 (SPLIT-R08).
        print(f"  G14 {'PASS' if verdict['passed'] else 'FAIL'}")
        return 0 if verdict["passed"] else 1
    classes = document["summary"]["all_450"]["classes"]
    full82 = document["summary"]["full82"]["classes"]
    print(f"  all 450: {classes}")
    print(f"  full 82: {full82}")
    print(f"  G14 {'PASS' if verdict['passed'] else 'FAIL'}: {verdict}")
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
