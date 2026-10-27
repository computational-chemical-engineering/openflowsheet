"""The offline Brightway adapter (E01 design §4.8.4; ADR 0052 D7; optional extra `lca`).

Brightway computes the frozen tables the LCA contributor reads; it never runs inside a solve, an
optimization or a replay. Only `bw2data` and `bw2calc` are used, at the pins of the `lca` extra
(bw2data 4.7, bw2calc 2.5.0; not bw2io, not pypardiso: bw2calc falls back to SciPy's sparse LU),
with bw2calc's own pinned dependency `bw_processing` 1.6 for the float64 datapackages.
They are imported inside each call: without them every call returns
`UNSUPPORTED(LCA_ENGINE_UNAVAILABLE)` and nothing else in `assessment` imports Brightway.

The adapter never downloads a database. The user prepares the project (ecoinvent through their own
credentials, USLCI through the Federal LCA Commons import). Brightway keeps its projects under
`BRIGHTWAY2_DIR` when that is set before the first import, else under the user data directory.

- `build_unit_score_table` computes `q_{m,k}`, the LCIA score of one unit of each activity, with
  one LCI factorization per category reused across the activity demands, and records the engine
  versions and the background databases' metadata hashes. bw2calc solves on float64 matrices that
  the adapter assembles from the project's stored rows (`_inventory_datapackage`,
  `_method_datapackage`): bw2data's own processed files hold every amount as float32
  (bw_processing 1.6), which would put ~1e-8 relative error into every frozen score (ESC-B1).
  The result is a `unit-score-table-v1` document with its `sha256` set (`tables.table_sha256`).
- `build_direct_factor_table` takes a method's characterisation factors for declared biosphere
  flows (`direct-factor-table-v1`).
- `foreground_check` is the independent check of A25: it copies the project to a scratch project,
  writes one foreground activity with the given exchange amounts, scores it with bw2calc (one
  solve of the whole system, on the same float64 path), and deletes the scratch project.
"""

from __future__ import annotations

import datetime
import hashlib
import itertools
import json
import uuid
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any, Final

from openflowsheet.assessment.lca.tables import (
    DIRECT_FACTOR_FORMAT,
    UNIT_SCORE_FORMAT,
    table_sha256,
)
from openflowsheet.assessment.program import Refusal

__all__ = [
    "SI_PER_UNIT",
    "available",
    "build_direct_factor_table",
    "build_unit_score_table",
    "foreground_check",
    "write_description",
]

#: Brightway unit names with an exact SI factor (§4.5.6); any other unit needs `si_per_unit`.
SI_PER_UNIT: Final[Mapping[str, float]] = {
    "joule": 1.0,
    "kilojoule": 1e3,
    "megajoule": 1e6,
    "gigajoule": 1e9,
    "kilowatt hour": 3.6e6,
    "megawatt hour": 3.6e9,
    "kilogram": 1.0,
    "ton": 1e3,
    "tonne": 1e3,
    "mole": 1.0,
    "kilomole": 1e3,
    "cubic meter": 1.0,
}


def _unavailable(detail: str) -> Refusal:
    return Refusal("LCA_ENGINE_UNAVAILABLE", "lca", detail, kind="unsupported")


def _engine() -> tuple[Any, Any] | Refusal:
    try:
        import bw2calc  # noqa: PLC0415
        import bw2data  # noqa: PLC0415
    except ImportError as error:
        return _unavailable(f"the optional extra `lca` is not installed: {error}")
    return bw2data, bw2calc


def available() -> bool:
    """Whether `bw2data` and `bw2calc` import (no project is touched)."""
    return not isinstance(_engine(), Refusal)


@contextmanager
def _current(bd: Any, project: str) -> Iterator[None]:
    previous = bd.projects.current
    bd.projects.set_current(project)
    try:
        yield
    finally:
        bd.projects.set_current(previous)


def _metadata_sha256(meta: Mapping[str, Any]) -> str:
    text = json.dumps(dict(meta), sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _closure(bd: Any, names: Sequence[str]) -> list[str]:
    """The databases `names` and everything they depend on, sorted."""
    seen: list[str] = []
    queue = list(names)
    while queue:
        name = queue.pop(0)
        if name in seen or name not in bd.databases:
            continue
        seen.append(name)
        queue.extend(bd.databases[name].get("depends", ()))
    return sorted(seen)


def _backgrounds(bd: Any, names: Sequence[str]) -> list[dict[str, Any]]:
    """The databases `names` and everything they depend on, each with its metadata hash."""
    return [
        {
            "database": name,
            "declared_version": str(bd.databases[name].get("version", "")),
            "system_model": str(bd.databases[name].get("system model", "")),
            "metadata_sha256": _metadata_sha256(bd.databases[name]),
        }
        for name in _closure(bd, names)
    ]


def _producer(bd: Any, bc: Any) -> dict[str, Any]:
    return {
        "engine": "brightway",
        "versions": {"bw2data": str(bd.__version__), "bw2calc": str(bc.__version__)},
        "created": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
    }


def _vector(dp: Any, matrix: str, name: str, rows: Iterable[Mapping[str, Any]]) -> None:
    """Add `rows` (`row`, `col`, `amount`, optional `flip`) to `dp` as one float64 vector."""
    import numpy as np  # noqa: PLC0415
    from bw_processing import INDICES_DTYPE  # noqa: PLC0415

    listed = list(rows)
    if not listed:
        return
    dp.add_persistent_vector(
        matrix=matrix,
        name=name,
        indices_array=np.array([(r["row"], r["col"]) for r in listed], dtype=INDICES_DTYPE),
        data_array=np.array([float(r["amount"]) for r in listed], dtype=np.float64),
        flip_array=np.array([bool(r.get("flip", False)) for r in listed], dtype=bool),
    )


def _inventory_datapackage(bd: Any, databases: Sequence[str]) -> Any:
    """The technosphere and biosphere matrices of `databases` as a float64 datapackage.

    The same stored rows, by the same rules, as bw2data 4.7's `SQLiteBackend.process` (one vector
    per database and matrix; technosphere-negative edges flipped; an implicit unit production for
    a process node without a production edge; duplicates within a vector summed), keeping the
    stored float64 amounts where `process` writes float32 (ESC-B1). Uses bw2data's own query
    functions, so it is tied to the pinned version, like the rest of the adapter."""
    from bw2data.backends.base import (  # noqa: PLC0415
        get_biosphere_qs,
        get_technosphere_negative_qs,
        get_technosphere_positive_qs,
    )
    from bw2data.backends.schema import ActivityDataset, ExchangeDataset, get_id  # noqa: PLC0415
    from bw2data.configuration import labels  # noqa: PLC0415
    from bw_processing import create_datapackage  # noqa: PLC0415

    dp = create_datapackage(sum_intra_duplicates=True, sum_inter_duplicates=False)
    for index, name in enumerate(databases):
        backend = bd.Database(name)
        dependents: set[str] = set()
        _vector(
            dp,
            "biosphere_matrix",
            f"biosphere-{index}",
            backend.exchange_data_iterator(get_biosphere_qs, dependents),
        )
        implicit = (
            {"row": get_id((name, code)), "col": get_id((name, code)), "amount": 1.0}
            for (code,) in ActivityDataset.select(ActivityDataset.code)
            .where(
                ActivityDataset.database == name,
                ActivityDataset.type << labels.implicit_production_allowed_node_types,
                ~(
                    ActivityDataset.code
                    << ExchangeDataset.select(ExchangeDataset.output_code).where(
                        ExchangeDataset.output_database == name,
                        ExchangeDataset.type << labels.technosphere_positive_edge_types,
                    )
                ),
            )
            .tuples()
        )
        _vector(
            dp,
            "technosphere_matrix",
            f"technosphere-{index}",
            itertools.chain(
                backend.exchange_data_iterator(get_technosphere_negative_qs, dependents, flip=True),
                backend.exchange_data_iterator(get_technosphere_positive_qs, dependents),
                implicit,
            ),
        )
    return dp


def _method_datapackage(bd: Any, method: Sequence[str]) -> Any:
    """`method`'s characterisation factors at the global location as a float64 datapackage.

    bw2calc's static LCA reads only the global-location column of a method (`custom_filter` on
    `global_index`); the rows are those of bw2data's `Method.process_row`, the amounts the stored
    float64 values."""
    from bw_processing import create_datapackage  # noqa: PLC0415

    bw_method = bd.Method(tuple(method))
    global_index = bd.geomapping[bd.config.global_location]
    rows = [bw_method.process_row(row) for row in bw_method.load()]
    dp = create_datapackage(sum_intra_duplicates=True, sum_inter_duplicates=False)
    _vector(dp, "characterization_matrix", "cfs", [r for r in rows if r["col"] == global_index])
    return dp


def build_unit_score_table(
    project: str,
    activities: Sequence[tuple[str, Sequence[str]]],
    categories: Sequence[tuple[str, Sequence[str]]],
    rights: Mapping[str, str],
    *,
    table_id: str,
    si_per_unit: Mapping[str, float] | None = None,
) -> dict[str, Any] | Refusal:
    """A `unit-score-table-v1` of `q_{m,k}` for `activities` `[(activity_id, key)]` and
    `categories` `[(category_id, method)]` in `project` (§4.8.4).

    `si_per_unit` gives an activity's unit in SI where `SI_PER_UNIT` does not know its unit. A
    key or a method the project lacks is refused `LCA_ACTIVITY_UNKNOWN` (never raised)."""
    engine = _engine()
    if isinstance(engine, Refusal):
        return engine
    bd, bc = engine
    overrides = dict(si_per_unit or {})
    with _current(bd, project):
        nodes = []
        for activity_id, key in activities:
            try:
                nodes.append(bd.get_activity(tuple(key)))
            except Exception as error:  # noqa: BLE001 (bw2data raises its own UnknownObject)
                return Refusal("LCA_ACTIVITY_UNKNOWN", activity_id, f"{tuple(key)}: {error}")
        rows: list[dict[str, Any]] = []
        for (activity_id, key), node in zip(activities, nodes, strict=True):
            unit = str(node.get("unit", ""))
            factor = overrides.get(activity_id, SI_PER_UNIT.get(unit))
            if factor is None:
                return Refusal(
                    "LCA_ACTIVITY_UNKNOWN", activity_id, f"unit {unit!r} has no SI factor"
                )
            rows.append(
                {
                    "activity_id": activity_id,
                    "key": list(key),
                    "name": str(node.get("name", "")),
                    "location": str(node.get("location", "")),
                    "unit": unit,
                    "si_per_unit": float(factor),
                }
            )
        unknown = [cid for cid, method in categories if tuple(method) not in bd.methods]
        if unknown:
            return Refusal("LCA_ACTIVITY_UNKNOWN", ",".join(unknown), "method not in the project")
        scores: list[list[float]] = []
        units: list[str] = []
        demand = {node.id: 1.0 for node in nodes}
        databases = _closure(bd, sorted({str(key[0]) for _, key in activities}))
        inventory = _inventory_datapackage(bd, databases)
        for _, method in categories:
            lca = bc.LCA(demand, data_objs=[inventory, _method_datapackage(bd, method)])
            lca.lci(factorize=True)
            row = []
            for node in nodes:
                lca.lcia(demand={node.id: 1.0})
                row.append(float(lca.score))
            scores.append(row)
            units.append(str(bd.Method(tuple(method)).metadata.get("unit", "")))
        document: dict[str, Any] = {
            "format": UNIT_SCORE_FORMAT,
            "table_id": table_id,
            "producer": _producer(bd, bc),
            "background": _backgrounds(bd, sorted({str(key[0]) for _, key in activities})),
            "categories": [
                {"category_id": cid, "method": list(method), "unit": unit}
                for (cid, method), unit in zip(categories, units, strict=True)
            ],
            "activities": rows,
            "scores": scores,
            "rights": dict(rights),
        }
    document["sha256"] = table_sha256(document)
    return document


def build_direct_factor_table(
    project: str,
    method: tuple[str, Sequence[str]],
    flows: Sequence[tuple[str, Sequence[str]]],
    rights: Mapping[str, str],
    *,
    table_id: str,
    source: Mapping[str, Any] | None = None,
) -> dict[str, Any] | Refusal:
    """A `direct-factor-table-v1` of `method` `(category_id, method)`'s characterisation factors
    for `flows` `[(flow_id, biosphere key)]`; a flow the method does not characterise gets 0.0."""
    engine = _engine()
    if isinstance(engine, Refusal):
        return engine
    bd, bc = engine
    category_id, name = method
    with _current(bd, project):
        if tuple(name) not in bd.methods:
            return Refusal("LCA_FLOW_UNKNOWN", category_id, "method not in the project")
        bw_method = bd.Method(tuple(name))
        by_id: dict[int, float] = {}
        for key_or_id, value, *_ in bw_method.load():
            node = (
                bd.get_node(id=key_or_id)
                if isinstance(key_or_id, int)
                else bd.get_node(database=key_or_id[0], code=key_or_id[1])
            )
            amount = value["amount"] if isinstance(value, Mapping) else value
            by_id[node.id] = float(amount)
        rows = []
        factors = []
        for flow_id, key in flows:
            try:
                node = bd.get_node(database=key[0], code=key[1])
            except Exception as error:  # noqa: BLE001
                return Refusal("LCA_FLOW_UNKNOWN", flow_id, f"{tuple(key)}: {error}")
            rows.append(
                {
                    "flow_id": flow_id,
                    "name": str(node.get("name", "")),
                    "compartment": [str(c) for c in node.get("categories", ())],
                    "unit": str(node.get("unit", "")),
                }
            )
            factors.append(by_id.get(node.id, 0.0))
        document: dict[str, Any] = {
            "format": DIRECT_FACTOR_FORMAT,
            "table_id": table_id,
            "categories": [
                {
                    "category_id": category_id,
                    "method": list(name),
                    "unit": str(bw_method.metadata.get("unit", "")),
                }
            ],
            "flows": rows,
            "factors": [factors],
            "source": dict(source or {"engine": _producer(bd, bc)}),
            "rights": dict(rights),
        }
    document["sha256"] = table_sha256(document)
    return document


def write_description(project: str, description: Mapping[str, Any]) -> None | Refusal:
    """Create `project` (if new) holding a background described as in `test-background-v1`'s
    `brightway` member: a biosphere database, a technosphere database and its methods. For the
    synthetic background and tests only; a user's real background is prepared by the user."""
    engine = _engine()
    if isinstance(engine, Refusal):
        return engine
    bd, _ = engine
    with _current(bd, project):
        biosphere = str(description["biosphere_database"])
        bd.Database(biosphere).write(
            {(biosphere, code): dict(body) for code, body in description["biosphere"].items()}
        )
        technosphere = str(description["technosphere_database"])
        bd.Database(technosphere).write(
            {
                (technosphere, code): {
                    **{k: v for k, v in body.items() if k != "exchanges"},
                    "exchanges": [
                        {**exchange, "input": tuple(exchange["input"])}
                        for exchange in body["exchanges"]
                    ],
                }
                for code, body in description["activities"].items()
            }
        )
        for method in description["methods"]:
            bw_method = bd.Method(tuple(method["method"]))
            bw_method.register(unit=str(method["unit"]))
            bw_method.write([(tuple(key), float(cf)) for key, cf in method["cfs"]])
    return None


def foreground_check(
    project: str,
    exchanges: Sequence[tuple[Sequence[str], float]],
    emissions: Sequence[tuple[Sequence[str], float]],
    method: Sequence[str],
) -> float | Refusal:
    """Brightway's score of one foreground activity that consumes `exchanges` `[(key, a_k)]`
    (activity units; negative for generation or substitution) and emits `emissions`
    `[(biosphere key, kg)]`, characterised by `method` (A25). Runs in a scratch copy of `project`,
    which is deleted afterwards."""
    engine = _engine()
    if isinstance(engine, Refusal):
        return engine
    bd, bc = engine
    previous = bd.projects.current
    scratch = f"{project}-ofs-check-{uuid.uuid4().hex[:12]}"
    bd.projects.set_current(project)
    bd.projects.copy_project(scratch, switch=True)
    try:
        name = "ofs_foreground"
        code = (name, "foreground")
        rows: list[dict[str, Any]] = [{"input": code, "amount": 1.0, "type": "production"}]
        rows += [
            {"input": tuple(key), "amount": float(a), "type": "technosphere"}
            for key, a in exchanges
        ]
        rows += [
            {"input": tuple(key), "amount": float(b), "type": "biosphere"} for key, b in emissions
        ]
        database = bd.Database(name)
        database.write(
            {code: {"name": "foreground", "unit": "unit", "location": "GLO", "exchanges": rows}}
        )
        foreground = database.get("foreground")
        lca = bc.LCA(
            {foreground.id: 1.0},
            data_objs=[
                _inventory_datapackage(bd, _closure(bd, [name])),
                _method_datapackage(bd, method),
            ],
        )
        lca.lci()
        lca.lcia()
        score = float(lca.score)
    finally:
        bd.projects.set_current(previous)
        bd.projects.delete_project(scratch, delete_dir=True)
    return score
