"""Frozen LCA tables: loading, hashing, checking and rights (E01 design §4.8.2, §4.8.5, §4.8.6;
ADR 0052 D7, D8).

Two formats, each a JSON document carrying its own `format`:

- `unit-score-table-v1`: `{table_id, producer {engine, versions…, created}, background [{database,
  declared_version, system_model, metadata_sha256}], categories [{category_id, method, unit}],
  activities [{activity_id, key, name, location, unit, si_per_unit}], scores [[q_{m,k}]]
  (categories × activities), rights {class, licence, redistribution, notice}, sha256}`;
- `direct-factor-table-v1`: `{table_id, categories, flows [{flow_id, name, compartment, unit}],
  factors [[c_{m,e}]] (categories × flows), source, rights, sha256}`.

`sha256` is the canonical hash (`canonical.document_sha256`) of the document without `sha256` and
without `producer.created`; a table whose stored hash disagrees is refused
`LCA_TABLE_HASH_MISMATCH`, and so is one whose hash disagrees with the `{id, sha256}` an assessment
names it by. A shipped table is read by id from `openflowsheet/_data/assessment/lca/`; a user's
table from the `path` of its `data.tables` entry.

Rights (§4.8.6): a table with `redistribution: forbidden` is named by `{id, sha256}` only in
reports, exports, fixtures and evidence (`reference`, `exportable`); its scores never leave the
user's project directory. Nothing derived from ecoinvent ships, and a table that ships carries its
licence text and notice in the file.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any, Final, Literal

from openflowsheet.assessment.program import Refusal
from openflowsheet.canonical import document_sha256

__all__ = [
    "DIRECT_FACTOR_FORMAT",
    "SHIPPED_TABLES",
    "UNIT_SCORE_FORMAT",
    "Activity",
    "Category",
    "DirectFactorTable",
    "Flow",
    "LcaTable",
    "LcaTableError",
    "Rights",
    "UnitScoreTable",
    "exportable",
    "load_shipped",
    "parse_table",
    "reference",
    "resolve_tables",
    "table_sha256",
]

UNIT_SCORE_FORMAT: Final = "unit-score-table-v1"
DIRECT_FACTOR_FORMAT: Final = "direct-factor-table-v1"
#: The tables `openflowsheet/_data/assessment/lca/` carries (§4.8.5). No USLCI table ships (WO-B1:
#: no CC0 or US public-domain licence recorded for a release; docs/E01B_DECISIONS.md).
SHIPPED_TABLES: Final[tuple[str, ...]] = ("gwp100-ipcc-ar6-v1", "test-background-v1")


class LcaTableError(ValueError):
    """A table document that is not a well-formed table of its format, or whose hash disagrees.

    `code` is `LCA_TABLE_HASH_MISMATCH` for a hash disagreement and `LCA_TABLE_INVALID` otherwise;
    the contributor turns either into a typed refusal of the exchanges that name the table."""

    def __init__(self, table_id: str, errors: Sequence[str], code: str = "LCA_TABLE_INVALID"):
        self.table_id = table_id
        self.errors = list(errors)
        self.code = code
        super().__init__(f"LCA table {table_id!r}: " + "; ".join(self.errors))


@dataclass(frozen=True)
class Category:
    category_id: str
    method: tuple[str, ...]
    unit: str


@dataclass(frozen=True)
class Activity:
    """One background activity: `si_per_unit` is its unit in SI (kWh → 3.6e6 J)."""

    activity_id: str
    key: tuple[str, ...]
    name: str
    location: str
    unit: str
    si_per_unit: float


@dataclass(frozen=True)
class Flow:
    flow_id: str
    name: str
    compartment: tuple[str, ...]
    unit: str


@dataclass(frozen=True)
class Rights:
    rights_class: Literal["open", "user-licensed"]
    licence: str
    redistribution: Literal["allowed", "forbidden"]
    notice: str

    @property
    def forbidden(self) -> bool:
        return self.redistribution == "forbidden"

    @property
    def label(self) -> str:
        """The report's one-string rights statement (`assessment-report` `lca.tables[].rights`)."""
        return f"{self.rights_class}; redistribution {self.redistribution}; {self.licence}"


@dataclass(frozen=True)
class LcaTable:
    """What both formats share: the columns are activities or flows, in file order."""

    table_id: str
    sha256: str
    categories: tuple[Category, ...]
    columns: tuple[str, ...]
    values: tuple[tuple[float, ...], ...]
    rights: Rights
    document: Mapping[str, Any]

    def category(self, category_id: str) -> Category | None:
        return next((c for c in self.categories if c.category_id == category_id), None)

    def value(self, category_id: str, column_id: str) -> float | None:
        """`q_{m,k}` or `c_{m,e}`; `None` when the table has no such category or column."""
        rows = [i for i, c in enumerate(self.categories) if c.category_id == category_id]
        if not rows or column_id not in self.columns:
            return None
        return self.values[rows[0]][self.columns.index(column_id)]


@dataclass(frozen=True)
class UnitScoreTable(LcaTable):
    activities: tuple[Activity, ...] = ()

    def activity(self, activity_id: str) -> Activity | None:
        return next((a for a in self.activities if a.activity_id == activity_id), None)


@dataclass(frozen=True)
class DirectFactorTable(LcaTable):
    flows: tuple[Flow, ...] = ()
    source: Mapping[str, Any] | None = None


def table_sha256(document: Mapping[str, Any]) -> str:
    """The canonical hash of a table without `sha256` and `producer.created` (§4.8.2)."""
    body = {key: value for key, value in document.items() if key != "sha256"}
    producer = body.get("producer")
    if isinstance(producer, Mapping):
        body["producer"] = {key: value for key, value in producer.items() if key != "created"}
    return document_sha256(body)


def _strings(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) and v for v in value)


def _matrix(
    name: str, value: Any, rows: int, cols: int, errors: list[str]
) -> tuple[tuple[float, ...], ...]:
    if not isinstance(value, list) or len(value) != rows:
        errors.append(f"{name} must be a list of {rows} rows")
        return ()
    out: list[tuple[float, ...]] = []
    for i, row in enumerate(value):
        if not isinstance(row, list) or len(row) != cols:
            errors.append(f"{name}[{i}] must have {cols} entries")
            return ()
        numbers = []
        for j, v in enumerate(row):
            if isinstance(v, bool) or not isinstance(v, int | float) or not math.isfinite(v):
                errors.append(f"{name}[{i}][{j}] is not a finite number")
                return ()
            numbers.append(float(v))
        out.append(tuple(numbers))
    return tuple(out)


def _unique(name: str, ids: Sequence[str], errors: list[str]) -> None:
    if len(set(ids)) != len(ids):
        errors.append(f"{name} ids repeat")


def _rights(value: Any, errors: list[str]) -> Rights:
    if not isinstance(value, Mapping):
        errors.append("rights must be an object")
        return Rights("user-licensed", "", "forbidden", "")
    rights_class = value.get("class")
    redistribution = value.get("redistribution")
    if rights_class not in ("open", "user-licensed"):
        errors.append("rights.class must be open or user-licensed")
    if redistribution not in ("allowed", "forbidden"):
        errors.append("rights.redistribution must be allowed or forbidden")
    if not isinstance(value.get("licence"), str) or not value.get("licence"):
        errors.append("rights.licence must be a non-empty string")
    if not isinstance(value.get("notice", ""), str):
        errors.append("rights.notice must be a string")
    if rights_class == "user-licensed" and redistribution == "allowed" and not value.get("notice"):
        errors.append("a user-licensed table set to redistribution allowed must say why (notice)")
    ok_class: Literal["open", "user-licensed"] = (
        "open" if rights_class == "open" else "user-licensed"
    )
    ok_red: Literal["allowed", "forbidden"] = (
        "allowed" if redistribution == "allowed" else "forbidden"
    )
    return Rights(ok_class, str(value.get("licence", "")), ok_red, str(value.get("notice", "")))


def _categories(value: Any, errors: list[str]) -> tuple[Category, ...]:
    if not isinstance(value, list) or not value:
        errors.append("categories must be a non-empty list")
        return ()
    out = []
    for i, c in enumerate(value):
        if (
            not isinstance(c, Mapping)
            or not isinstance(c.get("category_id"), str)
            or not _strings(c.get("method"))
            or not isinstance(c.get("unit"), str)
        ):
            errors.append(f"categories[{i}] needs category_id, method (strings) and unit")
            continue
        out.append(Category(c["category_id"], tuple(c["method"]), c["unit"]))
    _unique("category", [c.category_id for c in out], errors)
    return tuple(out)


def parse_table(document: Mapping[str, Any]) -> UnitScoreTable | DirectFactorTable:
    """A checked table; raises `LcaTableError` (`LCA_TABLE_HASH_MISMATCH` for a stored hash that
    disagrees with the content)."""
    table_id = str(document.get("table_id", ""))
    errors: list[str] = []
    fmt = document.get("format")
    if fmt not in (UNIT_SCORE_FORMAT, DIRECT_FACTOR_FORMAT):
        raise LcaTableError(table_id, [f"unknown format {fmt!r}"])
    if not table_id:
        errors.append("table_id must be a non-empty string")
    categories = _categories(document.get("categories"), errors)
    rights = _rights(document.get("rights"), errors)
    if fmt == UNIT_SCORE_FORMAT:
        activities = []
        for i, a in enumerate(document.get("activities") or []):
            spu = a.get("si_per_unit") if isinstance(a, Mapping) else None
            if (
                not isinstance(a, Mapping)
                or not isinstance(a.get("activity_id"), str)
                or not _strings(a.get("key"))
                or isinstance(spu, bool)
                or not isinstance(spu, int | float)
                or not spu > 0
            ):
                errors.append(f"activities[{i}] needs activity_id, key and si_per_unit > 0")
                continue
            activities.append(
                Activity(
                    a["activity_id"],
                    tuple(a["key"]),
                    str(a.get("name", "")),
                    str(a.get("location", "")),
                    str(a.get("unit", "")),
                    float(spu),
                )
            )
        if not activities:
            errors.append("activities must be a non-empty list")
        _unique("activity", [a.activity_id for a in activities], errors)
        if not isinstance(document.get("background"), list):
            errors.append("background must be a list")
        if not isinstance(document.get("producer"), Mapping):
            errors.append("producer must be an object")
        values = _matrix("scores", document.get("scores"), len(categories), len(activities), errors)
        columns = tuple(a.activity_id for a in activities)
    else:
        flows = []
        for i, f in enumerate(document.get("flows") or []):
            if (
                not isinstance(f, Mapping)
                or not isinstance(f.get("flow_id"), str)
                or not _strings(f.get("compartment"))
            ):
                errors.append(f"flows[{i}] needs flow_id and compartment")
                continue
            flows.append(
                Flow(
                    f["flow_id"],
                    str(f.get("name", "")),
                    tuple(f["compartment"]),
                    str(f.get("unit", "")),
                )
            )
        if not flows:
            errors.append("flows must be a non-empty list")
        _unique("flow", [f.flow_id for f in flows], errors)
        if not isinstance(document.get("source"), Mapping):
            errors.append("source must be an object")
        values = _matrix("factors", document.get("factors"), len(categories), len(flows), errors)
        columns = tuple(f.flow_id for f in flows)
    if errors:
        raise LcaTableError(table_id, errors)
    stored = document.get("sha256")
    computed = table_sha256(document)
    if stored != computed:
        raise LcaTableError(
            table_id,
            [f"stored sha256 {stored!r} is not the content's {computed}"],
            code="LCA_TABLE_HASH_MISMATCH",
        )
    common = (table_id, computed, categories, columns, values, rights, document)
    if fmt == UNIT_SCORE_FORMAT:
        return UnitScoreTable(*common, activities=tuple(activities))
    return DirectFactorTable(*common, flows=tuple(flows), source=document.get("source"))


_SHIPPED: dict[str, UnitScoreTable | DirectFactorTable] = {}


def load_shipped(table_id: str) -> UnitScoreTable | DirectFactorTable:
    """The shipped table `table_id`, read once through `importlib.resources` and checked."""
    if table_id not in _SHIPPED:
        if table_id not in SHIPPED_TABLES:
            raise KeyError(f"no shipped LCA table {table_id!r}")
        path = files("openflowsheet").joinpath("_data", "assessment", "lca", f"{table_id}.json")
        table = parse_table(json.loads(path.read_text(encoding="utf-8")))
        if table.table_id != table_id:
            raise LcaTableError(table_id, [f"file declares table_id {table.table_id!r}"])
        _SHIPPED[table_id] = table
    return _SHIPPED[table_id]


def resolve_tables(
    document: Mapping[str, Any],
) -> tuple[dict[str, UnitScoreTable | DirectFactorTable], dict[str, Refusal]]:
    """The tables an assessment document's `lca` section names (`tables`, `direct_factors`), by
    id, and a refusal per table that cannot be used (absent, malformed, wrong format, or a hash
    that disagrees with the table's content or with its `data.tables` entry)."""
    lca = dict(document.get("lca", {}))
    refs = {str(r["id"]): r for r in dict(document.get("data", {})).get("tables", ())}
    wanted = [(str(t), UNIT_SCORE_FORMAT) for t in lca.get("tables", ())]
    wanted += [(str(t), DIRECT_FACTOR_FORMAT) for t in lca.get("direct_factors", ())]
    tables: dict[str, UnitScoreTable | DirectFactorTable] = {}
    refused: dict[str, Refusal] = {}
    for table_id, fmt in wanted:
        ref = refs.get(table_id)
        try:
            if ref is not None and "path" in ref:
                table = parse_table(json.loads(Path(ref["path"]).read_text(encoding="utf-8")))
            else:
                table = load_shipped(table_id)
        except (KeyError, OSError, json.JSONDecodeError) as error:
            refused[table_id] = Refusal(
                "LCA_ACTIVITY_UNKNOWN", table_id, f"table not found: {error}"
            )
            continue
        except LcaTableError as error:
            refused[table_id] = Refusal(error.code, table_id, "; ".join(error.errors))
            continue
        if table.table_id != table_id:
            refused[table_id] = Refusal(
                "LCA_ACTIVITY_UNKNOWN", table_id, f"the file declares table_id {table.table_id!r}"
            )
        elif table.document["format"] != fmt:
            refused[table_id] = Refusal(
                "LCA_ACTIVITY_UNKNOWN", table_id, f"listed as {fmt}, is {table.document['format']}"
            )
        elif ref is not None and ref["sha256"] != table.sha256:
            refused[table_id] = Refusal(
                "LCA_TABLE_HASH_MISMATCH",
                table_id,
                f"data.tables names {ref['sha256']}, the table is {table.sha256}",
            )
        else:
            tables[table_id] = table
    return tables, refused


def reference(table: LcaTable) -> dict[str, str]:
    """The report's entry for a table (`lca.tables[]`): its id, hash and rights, never a score."""
    return {"id": table.table_id, "sha256": table.sha256, "rights": table.rights.label}


def exportable(table: LcaTable) -> dict[str, Any]:
    """What an export (a bundle, a fixture, evidence) may carry of `table` (§4.8.6): the whole
    document when its rights allow redistribution, else `{table_id, sha256, rights}` only."""
    if not table.rights.forbidden:
        return dict(table.document)
    return {
        "table_id": table.table_id,
        "sha256": table.sha256,
        "rights": {
            "class": table.rights.rights_class,
            "licence": table.rights.licence,
            "redistribution": table.rights.redistribution,
            "notice": table.rights.notice,
        },
    }
