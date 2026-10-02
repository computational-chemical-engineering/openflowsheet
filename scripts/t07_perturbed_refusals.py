"""G-R6-5 (iii) and G-R7-6: every binder refusal and every reported refusal over the perturbed set.

T07 design note, ruling round 7, gate G-R7-6 (review 2, N1). The set is G-R6-5 (iii)'s, as rf3a
measured it at W3 and W6: W0.2's 50 revisions and G-R6-3's V17 documents, each as it is and with
one specification removed, its `kind` or `unit` changed, its target path or component changed, or
one connection's `phase_capability` changed — 5485 documents. For each it records:

- the legacy binder's refusal and the revision binder's (G-R6-5 (iii)), `[kind, detail,
  implicated]` or `null`;
- the refusal `validate()`'s structural stage reports (`structural_refusal`), likewise;
- `select_route`'s answer: the route's `solve_path`, or `NoRoute`'s two refusals.

The digest of that mapping (`canonical_json`) is committed as `PERTURBED_REFUSALS_SHA256` in
`tests/test_t07_r6_routes.py`. `--out` writes the mapping, so that two trees can be compared
document by document; `--moves OLD.json` writes, to `--moves-out`, every document whose record
differs from OLD's, with its old and new reported refusal and route (G-R7-6's list,
`docs/t07-g-r7-6-moves.json`).

usage: PYTHONPATH=src:. python scripts/t07_perturbed_refusals.py [--out refusals.json]
           [--moves old.json --moves-out moves.json]
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))

Document = dict[str, Any]


def documents() -> Iterator[tuple[str, Document]]:
    """G-R6-5 (iii)'s perturbed documents, by name, in rf3a's order."""
    from t07_corpus import CORPUS
    from t07_v17_c1_documents import g_r6_3_documents

    bases = {name: CORPUS[name]() for name in sorted(CORPUS)}
    bases.update({f"v17:{key}": value for key, value in g_r6_3_documents().items()})
    for name, document in bases.items():
        yield name, document
        for index, specification in enumerate(document.get("specifications") or []):
            removed = copy.deepcopy(document)
            del removed["specifications"][index]
            yield f"{name}/-{specification['id']}", removed
            for label, change in (("kind", {"kind": "power"}), ("unit", {"unit": "degR"})):
                changed = copy.deepcopy(document)
                changed["specifications"][index].update(change)
                yield f"{name}/{specification['id']}:{label}", changed
            for path in ("x", "state.x", "duty.Q", "outlet.T", "outlet.P", "state.n"):
                changed = copy.deepcopy(document)
                changed["specifications"][index]["target"]["path"] = path
                yield f"{name}/{specification['id']}:path={path}", changed
            changed = copy.deepcopy(document)
            changed["specifications"][index]["target"]["component"] = "D"
            yield f"{name}/{specification['id']}:component=D", changed
        for position, connection in enumerate(document.get("connections") or []):
            for capability in ("liquid", "vapor", "vapor_liquid"):
                if connection.get("phase_capability") != capability:
                    changed = copy.deepcopy(document)
                    changed["connections"][position]["phase_capability"] = capability
                    yield f"{name}/{connection['id']}:phase={capability}", changed


def _refusal(result: Any) -> list[Any] | None:
    from openflowsheet.application.binding import Unbound

    if isinstance(result, Unbound):
        return [result.kind, result.detail, list(result.implicated)]
    return None


def record(document: Document) -> list[Any]:
    """`[legacy refusal, revision refusal, reported refusal, route]` for one document."""
    from openflowsheet.application.binding import bind_revision_or_reason
    from openflowsheet.application.revision_binding import bind_revision_flowsheet
    from openflowsheet.application.revision_run import Route, select_route
    from openflowsheet.application.validation import structural_refusal

    route = select_route(copy.deepcopy(document))
    return [
        _refusal(bind_revision_or_reason(copy.deepcopy(document))),
        _refusal(bind_revision_flowsheet(copy.deepcopy(document))),
        _refusal(structural_refusal(copy.deepcopy(document))),
        route.solve_path
        if isinstance(route, Route)
        else [_refusal(route.revision), _refusal(route.legacy)],
    ]


def perturbed_refusals() -> dict[str, list[Any]]:
    return {name: record(document) for name, document in documents()}


def digest(refusals: dict[str, list[Any]]) -> str:
    from openflowsheet.canonical import canonical_json

    return hashlib.sha256(canonical_json(refusals)).hexdigest()


def _tokens(entry: list[Any]) -> dict[str, str | None]:
    """A record's reported refusal and route, as `kind(detail)` tokens."""
    reported, route = entry[2], entry[3]
    return {
        "reported": None if reported is None else f"{reported[0]}({reported[1]})",
        "route": route
        if isinstance(route, str)
        else "; ".join(f"{part[0]}({part[1]})" for part in route),
    }


def moves(old: dict[str, list[Any]], new: dict[str, list[Any]]) -> list[str]:
    """Every document whose record moved, as JSON lines `"<name>": {"new": …, "old": …}`."""
    if set(old) != set(new):
        raise SystemExit("the two mappings are not over the same documents")
    return [
        f"  {json.dumps(name)}: "
        + json.dumps({"new": _tokens(new[name]), "old": _tokens(old[name])}, sort_keys=True)
        for name in sorted(new)
        if new[name] != old[name]
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, help="write the mapping here, as sorted JSON")
    parser.add_argument("--moves", type=Path, help="another tree's --out, to compare against")
    parser.add_argument("--moves-out", type=Path, help="where --moves writes the moved documents")
    arguments = parser.parse_args()
    if arguments.moves is not None and arguments.moves_out is None:
        parser.error("--moves needs --moves-out")
    refusals = perturbed_refusals()
    if arguments.out is not None:
        arguments.out.write_text(json.dumps(refusals, sort_keys=True), encoding="utf-8")
    print(f"documents = {len(refusals)}")
    print(f"perturbed_refusals_sha256 = {digest(refusals)}")
    if arguments.moves is not None:
        lines = moves(json.loads(arguments.moves.read_text(encoding="utf-8")), refusals)
        arguments.moves_out.write_text("{\n" + ",\n".join(lines) + "\n}\n", encoding="utf-8")
        print(f"moved = {len(lines)}")


if __name__ == "__main__":
    main()
