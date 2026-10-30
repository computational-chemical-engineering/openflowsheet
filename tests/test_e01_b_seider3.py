"""E01b A49 (design §10.10.5.7, §10.10.6): the shipped SSLW set against Seider's 3rd edition.

`benchmarks/e01/cost_hand/seider3.yaml` holds the 3rd-edition numbers the set's numbers correspond
to, typed from the book's pages (individual numbers with page and equation). This test checks
every relation it states against the set file as shipped, and that the YAML is complete: every
number object of the set (each `{value, source_line}`, the entry bases and the set's own basis
included) and every range is covered by exactly one record or a `not_in_book` line, every amended
number has an `amended` or `basis` record, and no record names a path the set lacks (R-895…R-899).
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Iterator, Mapping
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[1]
SET = REPO / "src" / "openflowsheet" / "_data" / "assessment" / "cost" / "sslw-idaes-v1.json"
SEIDER3 = REPO / "benchmarks" / "e01" / "cost_hand" / "seider3.yaml"
RELATIONS = ("same", "shift", "amended", "basis", "not_in_book")
#: The set's own `basis` is addressed as this entry id.
SET_ENTRY = "set"
#: The one number with two records (§10.10.5.7): its `shift` and Example 22.10's `same`.
TWICE = ("exchanger.shell_tube", "options.hx_type.choices.floating_head.alpha1")
#: A path step: a quoted key (a key containing a dot), a plain key, or a list index.
_STEP = re.compile(r'"([^"]+)"|([^.\[\]"]+)|\[(\d+)\]')


@cache
def _set() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(SET.read_text(encoding="utf-8"))
    return document


@cache
def _book() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(SEIDER3.read_text(encoding="utf-8"))
    return data


def _entry(entry_id: str) -> Mapping[str, Any]:
    if entry_id == SET_ENTRY:
        return {"basis": _set()["basis"]}
    return next(e for e in _set()["entries"] if e["entry_id"] == entry_id)


def _at(entry_id: str, path: str) -> Any:
    node: Any = _entry(entry_id)
    for quoted, key, index in _STEP.findall(path):
        node = node[int(index)] if index else node[quoted or key]
    return node


def _key(path: str, key: str) -> str:
    step = f'"{key}"' if "." in key else key
    return f"{path}.{step}" if path else step


def _walk(node: Any, path: str) -> Iterator[tuple[str, Mapping[str, Any]]]:
    if isinstance(node, list):
        for index, item in enumerate(node):
            yield from _walk(item, f"{path}[{index}]")
    elif isinstance(node, Mapping):
        yield path, node
        for key, item in node.items():
            yield from _walk(item, _key(path, key))


def _shipped(predicate: Any) -> set[tuple[str, str]]:
    """(entry id, path) of every node of the set that satisfies `predicate`."""
    bodies = [(SET_ENTRY, {"basis": _set()["basis"]})]
    for entry in _set()["entries"]:
        skip = ("entry_id", "form", "family", "method_lines")
        bodies.append((entry["entry_id"], {k: v for k, v in entry.items() if k not in skip}))
    found: set[tuple[str, str]] = set()
    for entry_id, body in bodies:
        for path, node in _walk(body, ""):
            if predicate(node):
                found.add((entry_id, path))
    return found


def _is_number(node: Mapping[str, Any]) -> bool:
    return "value" in node and "source_line" in node


def _is_range(node: Mapping[str, Any]) -> bool:
    return "min" in node and "max" in node


def _pages(page: str) -> str:
    return f"pp. {page}" if "-" in page else f"p. {page}"


def test_a49_every_relation_holds() -> None:
    shift = Decimal(_book()["shift"])
    counts: Counter[str] = Counter()
    for record in _book()["records"]:
        entry, path, relation = record["entry"], record["path"], record["relation"]
        where = f"{entry}:{path} ({relation})"
        assert relation in RELATIONS, where
        counts[relation] += 1
        node = _at(entry, path)
        assert _is_number(node), where
        if relation == "not_in_book":
            assert record["reason"] and "book" not in record, where
            assert "amended" not in node, where
            continue
        book = record["book"]
        assert isinstance(book, str) and isinstance(record["page"], str), where
        value = Decimal(repr(node["value"]))
        sign = int(record.get("sign", 1))
        if relation == "same":
            assert value * sign == Decimal(book), (where, node["value"], book)
            assert "amended" not in node, where
        elif relation == "shift":
            assert value - Decimal(book) == shift, (where, node["value"], book)
            assert "amended" not in node, where
        elif relation == "amended":
            assert value * sign == Decimal(book), (where, node["value"], book)
            amended = node["amended"]
            assert Decimal(repr(amended["replaces"])) == Decimal(record["replaces"]), where
            assert "index_basis" not in amended and "scale" not in amended, where
            assert _pages(record["page"]) in amended["citation"], where
        else:  # basis: the entry's index_basis, at the book's stated CE
            assert path == "index_basis.value", where
            assert value == Decimal(book) == Decimal(repr(_book()["book_index"])), where
            amended = node["amended"]
            assert Decimal(repr(amended["replaces"])) == Decimal(record["replaces"]), where
            assert record["page"] in amended["citation"], where
    assert counts["shift"] == 4 and counts["amended"] == 2 and counts["basis"] == 2, counts


def test_a49_ranges_match_the_printed_bounds() -> None:
    for record in _book()["ranges"]:
        entry, path = record["entry"], record["path"]
        r = _at(entry, path)
        where = f"{entry}:{path} ({_pages(record['page'])})"
        book_max = record["max"]
        if isinstance(book_max, list):  # one max per piece of the range it is `pieces_of`
            assert r["max"] == [float(m) for m in book_max], where
        else:
            assert r["max"] == float(book_max), where
        if record.get("min_is_switch"):
            previous = _at(entry, re.sub(r"\[(\d+)\]$", lambda m: f"[{int(m[1]) - 1}]", path))
            assert float(record["min"]) <= r["min"] == previous["max"], where
        else:
            assert r["min"] == float(record["min"]), where
        source = r.get("source", {})
        if source.get("kind") == "primary":
            assert r["role"] == "size", where
            third = source["citation"].split("3rd ed.", 1)[1]
            assert f"{_pages(record['page'])}," in third, where


def test_a49_the_expectation_is_complete() -> None:
    """Every number object and every range of the set has its record, exactly once; every
    amended number has an `amended` or `basis` record; no record names a path the set lacks."""
    numbers = _shipped(_is_number)
    ranges = _shipped(_is_range)
    records = Counter((r["entry"], r["path"]) for r in _book()["records"])
    range_records = Counter((r["entry"], r["path"]) for r in _book()["ranges"])
    assert set(records) == numbers, (sorted(numbers - set(records)), sorted(set(records) - numbers))
    assert {k: n for k, n in records.items() if n != 1} == {TWICE: 2}
    relations = {r["relation"] for r in _book()["records"] if (r["entry"], r["path"]) == TWICE}
    assert relations == {"shift", "same"}
    assert set(range_records) == ranges, (sorted(ranges - set(range_records)),)
    assert set(range_records.values()) == {1}
    amended = _shipped(lambda n: _is_number(n) and "amended" in n)
    named = {
        (r["entry"], r["path"]) for r in _book()["records"] if r["relation"] in ("amended", "basis")
    }
    assert named == amended, (sorted(amended ^ named),)
    assert len(amended) == 4
    primary = _shipped(lambda n: _is_range(n) and n.get("source", {}).get("kind") == "primary")
    assert len(primary) == 10, sorted(primary)
