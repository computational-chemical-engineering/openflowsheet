"""W27 case facts and case cards: what the classifier and the prompt read from the archive.

Normative text: registration §4 (W27-R01…R07, the facts) and §9 (W27-R34, the card). The facts
are read from five case JSON files and the access report's row, never from `sources/`, a `.py`
file or a solver output, and nothing from the archive is executed (W27-R01): the archive is
untrusted data, so a caller reading it runs Python with `-I` (registration §2). The tables the
rules use — the eleven unit options, the phase vocabularies, the configuration-keyed packages,
the card's field lists and bounds — are read from `registration.json`.

`extract(archive)` must reproduce the committed `case_facts.json` byte for byte (WO-16a's test),
and `case_card(case_dir)` every registered card SHA-256 (W27-A21).
"""

from __future__ import annotations

import csv
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from benchmarks.m06.w27 import registration

GENERIC: Final[str] = "generic"
#: An IDAES export marks a configuration it could not serialise with this key; the card drops it
#: ("without unset sub-configurations", W27-R34).
UNSET_MARKER: Final[str] = "requires_source_definition"


class _Missing:
    """A file that is absent or does not parse, distinct from a JSON `null`."""


MISSING: Final = _Missing()


def _load(path: Path) -> Any:
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return MISSING
    except (json.JSONDecodeError, UnicodeDecodeError):
        return MISSING


def _option(value: Any) -> Any:
    """W27-R03: IDAES exports an enum option as `{"component": name}`; the rules read the name."""
    if isinstance(value, dict) and set(value) == {"component"}:
        return value["component"]
    return value


def leaf(path: Any) -> str:
    return str(path).split(".")[-1]


def normalise_class(path: str) -> str:
    """W27-R02: the class leaf without a leading `_Scalar`/`_Indexed` and a trailing `Data`."""
    name = leaf(path)
    for prefix in ("_Scalar", "_Indexed"):
        if name.startswith(prefix):
            name = name[len(prefix) :]
    if name.endswith("Data") and len(name) > len("Data"):
        name = name[: -len("Data")]
    return name


def phase_kind_from_name(name: Any) -> str:
    """W27-R06: a topology phase name's kind, `unknown` when unregistered."""
    names: Mapping[str, str] = registration.load()["extraction"]["phase_names"]
    return str(names.get(str(name).casefold(), "unknown"))


def is_sub_block(name: str, names: set[str]) -> bool:
    """W27-R02: a unit block inside another unit block of the case is part of it."""
    return any(
        name != other and (name.startswith(other + ".") or name.startswith(other + "["))
        for other in names
    )


# =================================================================================================
# W27-R02/R03: units
# =================================================================================================


def _unit_facts(units: Any, topology_units: Sequence[Mapping[str, Any]]) -> tuple[str, list[Any]]:
    """The case's units, grouped by everything the rules read, each group with its names."""
    config_keys: Sequence[str] = registration.load()["extraction"]["unit_config_keys"]
    by_id = {str(u.get("id")): u for u in topology_units}
    groups: dict[str, dict[str, Any]] = {}
    if isinstance(units, list) and units:
        source = "units.json"
        names = {str(u.get("name")) for u in units if isinstance(u, dict)}
        for unit in units:
            name = str(unit.get("name"))
            if is_sub_block(name, names):
                continue
            cls = str(unit.get("class"))
            configuration = unit.get("configuration") or {}
            config: dict[str, Any] = {}
            for item in config_keys:
                if item in configuration:
                    value = _option(configuration[item])
                    if item == "outlet_list":
                        value = len(value) if isinstance(value, list) else None
                    if isinstance(value, str | int | float | bool) or value is None:
                        config[item] = value
            fact: dict[str, Any] = {"key": "idaes:" + normalise_class(cls), "class_leaf": leaf(cls)}
            if config:
                fact["config"] = config
            short = name.split(".")[-1]
            if short in by_id:
                fact["topology_kind"] = str(by_id[short].get("kind"))
            slot = json.dumps(fact, sort_keys=True)
            groups.setdefault(slot, {**fact, "names": []})["names"].append(name)
    else:
        source = "topology.json" if topology_units else "none"
        for unit in topology_units:
            fact = {"key": f"topology:{unit.get('kind')}"}
            slot = json.dumps(fact, sort_keys=True)
            groups.setdefault(slot, {**fact, "names": []})["names"].append(str(unit.get("id")))
    return source, [groups[k] for k in sorted(groups)]


# =================================================================================================
# W27-R04…R06: property packages
# =================================================================================================


def _generic_key(configuration: Mapping[str, Any]) -> tuple[str, list[str]]:
    """W27-R04 (a): a GenericParameterBlock's key is its phases' types, EoS and options."""
    phase_types: Mapping[str, str] = registration.load()["extraction"]["phase_types"]
    parts = []
    kinds = []
    phases = configuration.get("phases") or {}
    for name in sorted(phases):
        phase = phases[name] if isinstance(phases[name], dict) else {}
        ptype = leaf(phase.get("type"))
        eos = leaf(phase.get("equation_of_state"))
        options = phase.get("equation_of_state_options")
        text = f"{name}:{ptype}:{eos}"
        if isinstance(options, dict) and options:
            text += "(" + ",".join(f"{k}={leaf(_option(v))}" for k, v in sorted(options.items()))
            text += ")"
        parts.append(text)
        kinds.append(str(phase_types.get(ptype, phase_kind_from_name(name))))
    return f"{GENERIC}[{';'.join(parts)}]", sorted(set(kinds))


def _native_package(entry: Mapping[str, Any]) -> dict[str, Any]:
    config_keyed: Mapping[str, str] = registration.load()["extraction"]["config_keyed_packages"]
    implementation = entry.get("implementation") or []
    classes = [str(i.get("class")) for i in implementation if isinstance(i, dict)]
    configuration = entry.get("configuration") or {}
    if not classes:
        return {
            "name": str(entry.get("name")),
            "key": "native:no_implementation",
            "classes": [],
            "phases": [],
            "components": [],
        }
    cls = classes[-1]
    phases: list[str] = []
    components: list[str] = []
    if leaf(cls) == "GenericParameterBlock":
        key, phases = _generic_key(configuration)
        listed = configuration.get("components")
        if isinstance(listed, dict):
            components = sorted(str(c) for c in listed)
    elif cls in config_keyed:
        option = config_keyed[cls]
        key = f"{cls}[{option}={leaf(_option(configuration.get(option)))}]"
    else:
        key = cls
    return {
        "name": str(entry.get("name")),
        "key": key,
        "classes": classes,
        "phases": phases,
        "components": components,
    }


def _topology_package(name: str, entry: Mapping[str, Any]) -> dict[str, Any]:
    if entry.get("entry_id"):
        key = f"topology-entry:{entry['entry_id']}"
    elif entry.get("method"):
        key = f"topology-entry:method:{entry['method']}"
    else:
        key = "topology-entry:(none)"
    return {
        "name": name,
        "key": key,
        "classes": [],
        "phases": sorted({phase_kind_from_name(p) for p in entry.get("phases") or []}),
        "components": sorted(str(c) for c in entry.get("components") or []),
    }


# =================================================================================================
# W27-R34: the case card
# =================================================================================================


def _card_table() -> Mapping[str, Any]:
    table: Mapping[str, Any] = registration.load()["prompt"]["card"]
    return table


def _replacements() -> dict[int, str]:
    ranges: Sequence[Sequence[int]] = _card_table()["forbidden_ranges"]
    return {c: "�" for lo, hi in ranges for c in range(lo, hi + 1)}


def _project(value: Any) -> Any:
    """A configuration value as the card shows it: enum names, finite numbers, no dropped
    subtree and no unset sub-configuration."""
    dropped = set(_card_table()["dropped_configuration_keys"])
    value = _option(value)
    if isinstance(value, dict):
        if UNSET_MARKER in value:
            return MISSING
        out = {}
        for key in sorted(value):
            if key in dropped:
                continue
            projected = _project(value[key])
            if projected is not MISSING:
                out[str(key)] = projected
        return out
    if isinstance(value, list):
        return [p for p in (_project(v) for v in value) if p is not MISSING]
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    return value


def bound_text(text: str, limit: int, replace: Mapping[int, str]) -> str:
    """The application's §10.4 bound (`projection.bound_text`), as registration §9 restates it."""
    if len(text) <= limit:
        return text.translate(replace)
    for digits in range(1, len(str(len(text))) + 1):
        keep = limit - 10 - digits
        if keep < 0:
            break
        if len(str(len(text) - keep)) <= digits:
            return f"{text[:keep].translate(replace)}…[+{len(text) - keep} chars]"
    return text[:limit].translate(replace)


def _bound(value: Any, replace: Mapping[int, str]) -> Any:
    table = _card_table()
    text_limit, key_limit = int(table["text_limit"]), int(table["key_limit"])
    if isinstance(value, str):
        return bound_text(value, text_limit, replace)
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key in sorted(value):
            bounded = bound_text(str(key), key_limit, replace)
            name = bounded
            n = 2
            while name in out:
                suffix = f"~{n}"
                name = bounded[: key_limit - len(suffix)] + suffix
                n += 1
            out[name] = _bound(value[key], replace)
        return out
    if isinstance(value, list):
        return [_bound(v, replace) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    return value


def _scalar(value: Any) -> bool:
    if isinstance(value, list):
        return all(_scalar(v) for v in value)
    return value is None or isinstance(value, str | int | float | bool)


def _scalar_options(configuration: Any) -> dict[str, Any]:
    options = set(_card_table()["unit_options"])
    if not isinstance(configuration, dict):
        return {}
    out = {}
    for key in sorted(configuration):
        if key not in options:
            continue
        value = _project(configuration[key])
        if value is not MISSING and _scalar(value):
            out[str(key)] = value
    return out


def _pick(entry: Any, fields: Sequence[str]) -> dict[str, Any]:
    if not isinstance(entry, dict):
        return {}
    return {
        f: _project(entry[f]) for f in fields if f in entry and _project(entry[f]) is not MISSING
    }


def case_card(case_dir: Path) -> str:
    """W27-R34: the card's text, a pure function of the case's five JSON files."""
    table = _card_table()
    case = _load(case_dir / "case.json")
    spec = _load(case_dir / "specification.json")
    topo = _load(case_dir / "topology.json")
    units = _load(case_dir / "units.json")
    packages = _load(case_dir / "property_packages.json")
    case = case if isinstance(case, dict) else {}
    spec = spec if isinstance(spec, dict) else {}
    topo = topo if isinstance(topo, dict) else {}
    units = units if isinstance(units, list) else []
    packages = [packages] if isinstance(packages, dict) else packages
    packages = packages if isinstance(packages, list) else []
    card: dict[str, Any] = {
        "case_id": case.get("case_id"),
        "family": case.get("family"),
        "label": case.get("label"),
        "model_type": case.get("model_type"),
        "request": case.get("request"),
        "specification": {
            "solve": _pick(spec.get("solve"), table["solve_fields"]),
            "specs": [_pick(s, table["spec_fields"]) for s in spec.get("specs") or []],
            "terminal_feed_ports": _project(spec.get("terminal_feed_ports")),
            "terminal_product_ports": _project(spec.get("terminal_product_ports")),
        },
        "topology": {
            "arcs": [_pick(a, table["topology_arc_fields"]) for a in topo.get("arcs") or []],
            "components": _project(topo.get("components")),
            "process_type": topo.get("process_type"),
            "property_packages": {
                str(name): _pick(entry, table["topology_package_fields"])
                for name, entry in sorted((topo.get("property_packages") or {}).items())
            },
            "units": [_pick(u, table["topology_unit_fields"]) for u in topo.get("units") or []],
        },
        "idaes_units": [
            {
                "class": u.get("class"),
                "configuration": _scalar_options(u.get("configuration")),
                "name": u.get("name"),
            }
            for u in units
            if isinstance(u, dict)
        ],
        "idaes_property_packages": [
            {
                "classes": [i.get("class") for i in p.get("implementation") or []],
                "configuration": _project(p.get("configuration") or {}),
                "name": p.get("name"),
            }
            for p in packages
            if isinstance(p, dict)
        ],
    }
    return json.dumps(_bound(card, _replacements()), sort_keys=True, ensure_ascii=False)


def envelope_stem() -> str:
    """The marker stem no card may contain (GC-CARD-2): the begin marker before ` BEGIN`."""
    return str(registration.load()["prompt"]["envelope_begin"]).split(" BEGIN", 1)[0]


# =================================================================================================
# W27-R01…R07: the facts of one case and of the archive
# =================================================================================================


def _ports_found(path: Path, ports: Sequence[str]) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8", newline="") as handle:
        present = {row.get("port") for row in csv.DictReader(handle)}
    return sum(1 for p in ports if p in present or f"fs.{p}" in present)


def _stream_rows(path: Path) -> int:
    if not path.exists():
        return -1
    with path.open(encoding="utf-8", newline="") as handle:
        return max(sum(1 for _ in csv.reader(handle)) - 1, 0)


def case_facts(directory: Path, row: Mapping[str, Any]) -> dict[str, Any]:
    """One case's facts (W27-R01…R07) from its directory and its access-report row."""
    case = _load(directory / "case.json")
    spec = _load(directory / "specification.json")
    topo = _load(directory / "topology.json")
    units = _load(directory / "units.json")
    packages = _load(directory / "property_packages.json")
    case = case if isinstance(case, dict) else {}
    spec = spec if isinstance(spec, dict) else {}
    topo = topo if isinstance(topo, dict) else {}
    topology_units = [u for u in topo.get("units") or [] if isinstance(u, dict)]
    unit_source, unit_facts = _unit_facts(units, topology_units)
    if isinstance(packages, dict):
        packages = [packages] if "name" in packages else []
    topo_packages = {
        str(k): v for k, v in (topo.get("property_packages") or {}).items() if isinstance(v, dict)
    }
    if isinstance(packages, list) and packages:
        package_source = "property_packages.json"
        package_facts = [_native_package(p) for p in packages if isinstance(p, dict)]
    else:
        package_source = "topology.json" if topo_packages else "none"
        package_facts = [_topology_package(k, v) for k, v in sorted(topo_packages.items())]
    declared: set[str] = set()
    for entry in topo_packages.values():
        declared |= {str(c) for c in entry.get("components") or []}
    for package in package_facts:
        declared |= set(package["components"])
    solve = spec.get("solve") if isinstance(spec.get("solve"), dict) else {}
    card = case_card(directory)
    ports = [str(p) for p in spec.get("terminal_product_ports") or []]
    return {
        "case_id": directory.name,
        "family": row["family"],
        "model_type": row["model_type"],
        "in_full82": row["in_full82"],
        "residual_check": row["residual_check"],
        "files_missing": row["files_missing"],
        "parse_errors": row["parse_errors"],
        "unit_source": unit_source,
        "units": unit_facts,
        "topology_kinds": sorted({str(u.get("kind")) for u in topology_units}),
        "package_source": package_source,
        "packages": package_facts,
        "topology_package_names": sorted(topo_packages),
        "topology_entry_ids": sorted(
            {str(v["entry_id"]) for v in topo_packages.values() if v.get("entry_id")}
        ),
        "listed_components": sorted(declared),
        "steady_state": solve.get("steady_state"),
        "expected_dof": solve.get("expected_dof"),
        "solve_dynamic": bool(solve.get("dynamic")),
        "objective_declared": "objective" in solve,
        "terminal_product_ports": ports,
        "stream_rows": _stream_rows(directory / "streams.csv"),
        "product_ports_in_streams": _ports_found(directory / "streams.csv", ports),
        "card_chars": len(card),
        "card_sha256": registration.sha256_bytes(card.encode("utf-8")),
        "card_has_envelope_stem": envelope_stem() in card,
        "case_json_case_id": case.get("case_id"),
    }


def extract(archive: Path) -> dict[str, Any]:
    """The `case_facts.json` document from the extracted archive and the access report."""
    access = json.loads(registration.ACCESS_JSON.read_bytes())
    rows = {row["case_id"]: row for row in access["rows"]}
    case_root = archive / "cases"
    names = sorted(p.name for p in case_root.iterdir() if p.is_dir())
    if names != sorted(rows):
        raise ValueError("the archive's case directories are not the access report's 450")
    provenance = json.loads(registration.PROVENANCE_JSON.read_bytes())
    return {
        "schema": "w27-case-facts-v1",
        "source": {
            "archive_sha256": provenance["archive"]["sha256"],
            "access_report_sha256": registration.sha256_file(registration.ACCESS_JSON),
            "generator": "docs/derivations/scripts/m06_w27_registration.py",
        },
        "cases": [case_facts(case_root / name, rows[name]) for name in names],
    }


def dump_facts(document: Mapping[str, Any]) -> bytes:
    """`case_facts.json`'s committed form: one case per line."""
    head = {k: v for k, v in document.items() if k != "cases"}
    lines = [
        json.dumps(c, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        for c in document["cases"]
    ]
    text = json.dumps(head, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return (text[:-1] + ', "cases": [\n' + ",\n".join(lines) + "\n]}\n").encode("utf-8")


def load_facts() -> dict[str, Any]:
    """The committed `case_facts.json` (the classifier's input when the archive is absent)."""
    document: dict[str, Any] = json.loads(registration.CASE_FACTS_JSON.read_bytes())
    return document
