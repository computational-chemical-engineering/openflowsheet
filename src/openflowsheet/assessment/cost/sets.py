"""Correlation sets: load, check and resolve `cost-set-v1` files (E01 design §4.5.2, §9.2.3).

A set is data only; its arithmetic is `forms`. The loader refuses, with every reason found, a set
that has:

- an unknown `schema` or entry `form`;
- a number taken from the source without its `source_line` (coefficients, choice values, defaults,
  index values), or an option default that is not one of its choices;
- a range without a `source`, a `pinned` source without its `source_line`, or a `primary` source
  without `citation` and a boolean `verified`;
- a `size` range with `max < 2·min` (§4.3.2), an `input` range whose `below` is not `floor` or
  `refuse` or whose `above` is not `refuse`, or pieces that are not contiguous and increasing;
- an `input` range declaring `below: floor` whose form value at `min` is smaller than at
  `min − 1e-6·max(1, |min|)`: a floor must never undercut (checked on floats at load).

`resolve` applies an item's options to an entry: an option the entry does not have, a choice
outside an option's `choices`, or a combination the source refuses (the pump's material against
its type) is `NO_CORRELATION(<item>)` with the reason (§9.2.3). Every option the item leaves out
takes the IDAES default and is listed in `defaulted`.

Shipped sets live in `openflowsheet/_data/assessment/cost/<set_id>.json`.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib.resources import files
from types import MappingProxyType
from typing import Any, Final, TypeGuard

from openflowsheet.assessment.cost.forms import FORMS, GENERIC_FORMS, Range, ResolvedEntry

__all__ = [
    "SCHEMA",
    "CostEntry",
    "CostSet",
    "CostSetError",
    "NoCorrelation",
    "entry_for",
    "load_set",
    "parse_set",
    "resolve",
    "unverified_primary_ranges",
]

SCHEMA: Final = "cost-set-v1"
#: The SSLW forms plus the generic layout (§4.5.2).
KNOWN_FORMS: Final = (*FORMS, "generic-v1")
_SOURCE_KINDS: Final = ("pinned", "primary")


class CostSetError(ValueError):
    """A set file the loader refuses; `reasons` lists every check that failed."""

    def __init__(self, set_id: str, reasons: Sequence[str]) -> None:
        self.set_id = set_id
        self.reasons = tuple(reasons)
        super().__init__(f"cost set {set_id!r} refused: " + "; ".join(self.reasons))


@dataclass(frozen=True)
class NoCorrelation:
    """`NO_CORRELATION(<item>)`: why an item's options do not resolve on an entry."""

    entry_id: str
    detail: str


@dataclass(frozen=True)
class CostEntry:
    """One entry of a set, as parsed (its document kept for the report's provenance)."""

    entry_id: str
    form: str
    family: tuple[str, ...]
    orientation: str | None
    document: Mapping[str, Any]


@dataclass(frozen=True)
class CostSet:
    """A checked set: its id, source, basis, accuracy class and entries in file order."""

    set_id: str
    document: Mapping[str, Any]
    entries: tuple[CostEntry, ...]

    @property
    def index_value(self) -> float:
        return _number(self.document["basis"]["index"]["value"])

    def entry(self, entry_id: str) -> CostEntry:
        for entry in self.entries:
            if entry.entry_id == entry_id:
                return entry
        raise KeyError(f"cost set {self.set_id!r} has no entry {entry_id!r}")


def _number(node: Any) -> float:
    return float(node["value"]) if isinstance(node, Mapping) else float(node)


def _is_number(value: Any) -> TypeGuard[int | float]:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _check_number(node: Any, where: str, reasons: list[str]) -> None:
    """A number from the source: `{value, source_line}` (§9.2.3 "Numbers")."""
    if not isinstance(node, Mapping) or not _is_number(node.get("value")):
        reasons.append(f"{where}: not a number object {{value, source_line}}")
    elif not (isinstance(node.get("source_line"), str) and node["source_line"]):
        reasons.append(f"{where}: missing source_line")


def _check_numbers(node: Any, where: str, reasons: list[str]) -> None:
    """Every leaf of a coefficient tree is a number object (lists and nested objects allowed)."""
    if isinstance(node, list):
        for index, item in enumerate(node):
            _check_numbers(item, f"{where}[{index}]", reasons)
    elif isinstance(node, Mapping) and "value" not in node:
        for key, item in node.items():
            _check_numbers(item, f"{where}.{key}", reasons)
    else:
        _check_number(node, where, reasons)


def _check_choice(body: Any, where: str, reasons: list[str]) -> None:
    if not isinstance(body, Mapping):
        reasons.append(f"{where}: a choice must be an object")
        return
    for key, value in body.items():
        if key == "ranges":
            _check_ranges(value, f"{where}.ranges", reasons)
        else:
            _check_numbers(value, f"{where}.{key}", reasons)


def _check_option(name: str, option: Any, where: str, reasons: list[str]) -> None:
    if not isinstance(option, Mapping):
        reasons.append(f"{where}: an option must be an object")
        return
    default = option.get("default")
    if not (isinstance(option.get("default_source_line"), str) and option["default_source_line"]):
        reasons.append(f"{where}: default without default_source_line")
    tables: list[tuple[str, Mapping[str, Any]]] = []
    if "choices_by" in option:
        by = option.get("depends_on")
        if not isinstance(by, str):
            reasons.append(f"{where}: choices_by without depends_on")
        for key, table in dict(option["choices_by"]).items():
            tables.append((f"{where}.choices_by.{key}", table))
    else:
        tables.append((f"{where}.choices", option.get("choices", {})))
    for table_where, table in tables:
        if not isinstance(table, Mapping) or not table:
            reasons.append(f"{table_where}: no choices")
            continue
        for key, body in table.items():
            _check_choice(body, f"{table_where}.{key}", reasons)
    if "choices_by" not in option and default not in dict(option.get("choices", {})):
        reasons.append(f"{where}: default {default!r} is not one of its choices")


def _check_source(source: Any, where: str, reasons: list[str]) -> None:
    if not isinstance(source, Mapping):
        reasons.append(f"{where}: range without source")
        return
    kind = source.get("kind")
    if kind not in _SOURCE_KINDS:
        reasons.append(f"{where}: source kind {kind!r} is not one of {list(_SOURCE_KINDS)}")
    elif kind == "pinned" and not (
        isinstance(source.get("source_line"), str) and source["source_line"]
    ):
        reasons.append(f"{where}: pinned source without source_line")
    elif kind == "primary":
        if not (isinstance(source.get("citation"), str) and source["citation"]):
            reasons.append(f"{where}: primary source without citation")
        if not isinstance(source.get("verified"), bool):
            reasons.append(f"{where}: primary source without verified")


def _check_ranges(ranges: Any, where: str, reasons: list[str]) -> None:
    if not isinstance(ranges, Mapping):
        reasons.append(f"{where}: ranges must be an object")
        return
    for name, r in ranges.items():
        at = f"{where}.{name}"
        if not isinstance(r, Mapping):
            reasons.append(f"{at}: a range must be an object")
            continue
        _check_source(r.get("source"), at, reasons)
        role = r.get("role")
        if role == "size":
            low, high = r.get("min"), r.get("max")
            if not (_is_number(low) and _is_number(high) and low > 0):
                reasons.append(f"{at}: size range needs positive numbers min and max")
            elif high < 2.0 * low:
                reasons.append(f"{at}: size range max {high!r} < 2·min {low!r} (§4.3.2)")
            if "below" in r or "above" in r:
                reasons.append(f"{at}: a size range declares no below/above")
        elif role == "input":
            if r.get("below") not in ("floor", "refuse"):
                reasons.append(f"{at}: below must be 'floor' or 'refuse'")
            if r.get("above") != "refuse":
                reasons.append(f"{at}: above must be 'refuse'")
            if "pieces" in r:
                pieces = r["pieces"]
                bounds = [(p.get("min"), p.get("max")) for p in pieces if isinstance(p, Mapping)]
                if (
                    len(bounds) != len(pieces)
                    or not bounds
                    or not all(_is_number(lo) and _is_number(hi) and lo < hi for lo, hi in bounds)
                ):
                    reasons.append(f"{at}: pieces need numbers min < max")
                elif any(bounds[i][1] != bounds[i + 1][0] for i in range(len(bounds) - 1)):
                    reasons.append(f"{at}: pieces are not contiguous: {bounds}")
            else:
                low, high = r.get("min"), r.get("max")
                highs = high if isinstance(high, list) else [high]
                if not (
                    _is_number(low) and highs and all(_is_number(h) and h > low for h in highs)
                ):
                    reasons.append(f"{at}: input range needs numbers min < max")
                if isinstance(high, list) and not isinstance(r.get("pieces_of"), str):
                    reasons.append(f"{at}: a maximum per piece needs pieces_of")
        else:
            reasons.append(f"{at}: role {role!r} is neither 'size' nor 'input'")


def _range(name: str, r: Mapping[str, Any]) -> Range:
    if r["role"] == "size":
        return Range(
            name, "size", float(r["min"]), float(r["max"]), MappingProxyType(dict(r["source"]))
        )
    if "pieces" in r:
        pieces = tuple((float(p["min"]), float(p["max"])) for p in r["pieces"])
        return Range(
            name,
            "input",
            pieces[0][0],
            pieces[-1][1],
            MappingProxyType(dict(r["source"])),
            below=r["below"],
            pieces=pieces,
        )
    high = r["max"]
    by_piece = tuple(float(h) for h in high) if isinstance(high, list) else ()
    return Range(
        name,
        "input",
        float(r["min"]),
        max(by_piece) if by_piece else float(high),
        MappingProxyType(dict(r["source"])),
        below=r["below"],
        max_by_piece=by_piece,
        pieces_of=r.get("pieces_of"),
    )


def _check_floors(
    set_id: str, entry: Mapping[str, Any], reasons: list[str], set_index: float
) -> None:
    """§9.2.3: a floored input's form value at `min` is not smaller than just below it, on the
    entry's default options."""
    form = FORMS[entry["form"]]
    try:
        resolved = _resolve(set_id, entry, {}, set_index)
    except (KeyError, TypeError, ValueError) as error:
        reasons.append(f"{entry.get('entry_id')}: does not resolve on its defaults: {error}")
        return
    if isinstance(resolved, NoCorrelation):
        reasons.append(
            f"{entry.get('entry_id')}: does not resolve on its defaults: {resolved.detail}"
        )
        return
    for r in resolved.ranges.values():
        if r.role != "input" or r.below != "floor":
            continue
        below = r.min - 1e-6 * max(1.0, abs(r.min))
        at_min = form.input_response(resolved, r.name, r.min)
        under = form.input_response(resolved, r.name, below)
        if at_min < under:
            reasons.append(
                f"{entry['entry_id']}.ranges.{r.name}: the floor undercuts: the form is "
                f"{at_min!r} at min {r.min!r} and {under!r} at {below!r}"
            )


def parse_set(document: Mapping[str, Any]) -> CostSet:
    """Check a set document (§9.2.3) and return it; `CostSetError` lists every failed check."""
    set_id = str(document.get("set_id", "<no set_id>"))
    reasons: list[str] = []
    if document.get("schema") != SCHEMA:
        reasons.append(f"schema {document.get('schema')!r} is not {SCHEMA!r}")
    basis = document.get("basis")
    if not isinstance(basis, Mapping) or not isinstance(basis.get("index"), Mapping):
        reasons.append("basis.index missing")
        set_index = 1.0
    else:
        _check_number(basis["index"].get("value"), "basis.index.value", reasons)
        set_index = (
            _number(basis["index"]["value"])
            if _is_number(dict(basis["index"].get("value") or {}).get("value"))
            else 1.0
        )
    entries: list[CostEntry] = []
    seen: set[str] = set()
    for position, entry in enumerate(document.get("entries", [])):
        at = str(entry.get("entry_id", f"entries[{position}]"))
        if at in seen:
            reasons.append(f"{at}: repeated entry_id")
        seen.add(at)
        form = entry.get("form")
        if form not in KNOWN_FORMS:
            reasons.append(f"{at}: unknown form {form!r}")
            continue
        if form == "generic-v1":
            _check_generic(entry, at, reasons)
        else:
            for name, option in dict(entry.get("options", {})).items():
                _check_option(name, option, f"{at}.options.{name}", reasons)
            _check_numbers(entry.get("coefficients", {}), f"{at}.coefficients", reasons)
            for name, theta in dict(entry.get("continuous", {})).items():
                _check_number(theta.get("default"), f"{at}.continuous.{name}.default", reasons)
            if "index_basis" in entry:
                _check_number(entry["index_basis"].get("value"), f"{at}.index_basis.value", reasons)
            _check_ranges(entry.get("ranges", {}), f"{at}.ranges", reasons)
        entries.append(
            CostEntry(
                at, str(form), tuple(entry.get("family", ())), entry.get("orientation"), entry
            )
        )
    if not reasons:
        for entry in document.get("entries", []):
            if entry["form"] != "generic-v1":
                _check_floors(set_id, entry, reasons, set_index)
    if reasons:
        raise CostSetError(set_id, reasons)
    return CostSet(set_id, MappingProxyType(dict(document)), tuple(entries))


def _check_generic(entry: Mapping[str, Any], at: str, reasons: list[str]) -> None:
    """§4.5.2's layout: `size`, `base` (a generic form with its `source_line`), `factors`."""
    size = entry.get("size")
    if not isinstance(size, Mapping) or not all(
        _is_number(size.get(k)) for k in ("unit_factor", "min", "max")
    ):
        reasons.append(f"{at}: size needs unit_factor, min, max")
    elif size["max"] < 2.0 * size["min"]:
        reasons.append(f"{at}: size range max {size['max']!r} < 2·min {size['min']!r} (§4.3.2)")
    base = entry.get("base")
    if not isinstance(base, Mapping) or base.get("form") not in GENERIC_FORMS:
        reasons.append(f"{at}: base form must be one of {list(GENERIC_FORMS)}")
    elif not (isinstance(base.get("source_line"), str) and base["source_line"]):
        reasons.append(f"{at}.base: missing source_line")
    for index, factor in enumerate(entry.get("factors", [])):
        if not (isinstance(factor.get("source_line"), str) and factor["source_line"]):
            reasons.append(f"{at}.factors[{index}]: missing source_line")


def _plain(node: Any) -> Any:
    """A coefficient tree with its number objects replaced by floats (lists become tuples)."""
    if isinstance(node, list):
        return tuple(_plain(item) for item in node)
    if isinstance(node, Mapping) and "value" in node:
        return float(node["value"])
    if isinstance(node, Mapping):
        return MappingProxyType({k: _plain(v) for k, v in node.items()})
    return node


def _resolve(
    set_id: str, entry: Mapping[str, Any], options: Mapping[str, str], set_index: float
) -> ResolvedEntry | NoCorrelation:
    entry_id = str(entry["entry_id"])
    declared = dict(entry.get("options", {}))
    unknown = sorted(set(options) - set(declared))
    if unknown:
        return NoCorrelation(entry_id, f"options {unknown} are not options of {entry_id}")
    chosen: dict[str, str] = {}
    defaulted: list[str] = []
    numbers: dict[str, Any] = {}
    sources: dict[str, str] = {}
    ranges: dict[str, Range] = {}

    def take(prefix: str, body: Mapping[str, Any]) -> NoCorrelation | None:
        for key, value in body.items():
            if key == "ranges":
                for name, r in value.items():
                    ranges[name] = _range(name, r)
                continue
            if key in numbers:
                return NoCorrelation(entry_id, f"{prefix}.{key} repeats a coefficient")
            numbers[key] = _plain(value)
            if isinstance(value, Mapping) and "source_line" in value:
                sources[key] = value["source_line"]
        return None

    for name, option in declared.items():
        applies = dict(option.get("applies_when", {}))
        if any(chosen.get(k) != v for k, v in applies.items()):
            if name in options:
                return NoCorrelation(
                    entry_id, f"option {name} applies only when {applies} (chosen: {chosen})"
                )
            continue
        if name in options:
            key = str(options[name])
        else:
            key = str(option["default"])
            defaulted.append(name)
        if "choices_by" in option:
            table = dict(option["choices_by"]).get(chosen.get(option["depends_on"], ""), {})
        else:
            table = dict(option["choices"])
        if key not in table:
            return NoCorrelation(
                entry_id,
                f"{name} = {key!r} is not one of {sorted(table)}"
                + (
                    f" for {option['depends_on']} = {chosen.get(option['depends_on'])!r}"
                    if "choices_by" in option
                    else ""
                ),
            )
        chosen[name] = key
        refused = take(f"{name}.{key}", table[key])
        if refused is not None:
            return refused
    refused = take("coefficients", dict(entry.get("coefficients", {})))
    if refused is not None:
        return refused
    for name, r in dict(entry.get("ranges", {})).items():
        ranges.setdefault(name, _range(name, r))
    continuous = {
        name: float(theta["default"]["value"])
        for name, theta in dict(entry.get("continuous", {})).items()
    }
    index = entry.get("index_basis")
    ratio = 1.0 if index is None else set_index / _number(index["value"])
    return ResolvedEntry(
        set_id=set_id,
        entry_id=entry_id,
        form=str(entry["form"]),
        options=chosen,
        defaulted=tuple(defaulted),
        numbers=numbers,
        ranges=ranges,
        sources=sources,
        continuous=continuous,
        ratio=ratio,
        includes_drive=bool(entry.get("includes_drive", False)),
    )


def resolve(
    cost_set: CostSet, entry_id: str, options: Mapping[str, str] | None = None
) -> ResolvedEntry | NoCorrelation:
    """Entry `entry_id` with the item's `options` applied (§9.2.3 "Options")."""
    entry = cost_set.entry(entry_id)
    if entry.form == "generic-v1":
        raise NotImplementedError("generic-v1 entries are resolved by the cost contributor (WO-A4)")
    return _resolve(cost_set.set_id, entry.document, dict(options or {}), cost_set.index_value)


def entry_for(cost_set: CostSet, family: str, orientation: str | None = None) -> CostEntry | None:
    """§4.5.3: the set's first entry whose `family` contains `family` (and `orientation`, when
    declared); `None` is `NO_CORRELATION(<item>)`."""
    for entry in cost_set.entries:
        if family in entry.family and (
            orientation is None or entry.orientation in (None, orientation)
        ):
            return entry
    return None


_SETS: dict[str, CostSet] = {}


def unverified_primary_ranges(document: Mapping[str, Any]) -> tuple[str, ...]:
    """The JSON pointers of every range in a set document whose source is `primary` with
    `verified: false` (§9.6 A48: a release candidate ships none; §9.7 QA1 verifies them)."""
    found: list[str] = []

    def walk(node: Any, pointer: str) -> None:
        if isinstance(node, Mapping):
            source = node.get("source")
            if (
                isinstance(source, Mapping)
                and source.get("kind") == "primary"
                and source.get("verified") is False
            ):
                found.append(pointer)
            for key, value in node.items():
                walk(value, f"{pointer}/{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{pointer}/{index}")

    walk(document, "")
    return tuple(found)


def load_set(set_id: str) -> CostSet:
    """The shipped set `set_id`, read once through `importlib.resources` and checked."""
    if set_id not in _SETS:
        path = files("openflowsheet").joinpath("_data", "assessment", "cost", f"{set_id}.json")
        if not path.is_file():
            raise KeyError(f"no shipped cost set {set_id!r}")
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("set_id") != set_id:
            raise CostSetError(set_id, [f"file declares set_id {document.get('set_id')!r}"])
        _SETS[set_id] = parse_set(document)
    return _SETS[set_id]
