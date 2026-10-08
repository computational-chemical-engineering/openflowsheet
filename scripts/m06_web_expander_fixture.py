"""M06 WO-6 (design note §5.4): the server's views of one document, for the shell's expander test.

`api.readWhole` reassembles a projected document from the views the server gives. Its Node test
(`tests/web/api.test.mjs`) runs it against a fake transport answering from this fixture, which
holds, for a document built to reach every branch of the expander, the response of every view
`readWhole` can ask for — at every container pointer of the document, depth 12, limit 200, and
every cursor of an array target — computed by the server's own functions
(`projection.project`, then `projection.bound_document`, as `operations.dispatch` answers), and
the document a correct reassembly yields (`bound_document` of the original: strings and keys
arrive bounded, §10.4). The branches: objects and arrays elided below depth 12; nested arrays cut
at 20 items; an array target paged by cursor past 200 items; views over 65 536 bytes re-rendered
shallower (`truncated`), down to a depth-1 view that is complete though still over the cap;
RFC 6901 escaping of `/` and `~`; literal content shaped exactly like a marker of its own
pointer, as an object and as an array's last item; a forbidden code point.

Usage: `python scripts/m06_web_expander_fixture.py --write` rewrites
`tests/web/fixtures/expander.json`; `--check` exits 1 when the committed file differs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Final

from openflowsheet.application.projection import (
    MAX_DEPTH,
    MAX_PAGE,
    bound_document,
    encode_offset,
    escape_token,
    project,
)
from openflowsheet.canonical import canonical_json

ROOT: Final[Path] = Path(__file__).resolve().parents[1]
TARGET: Final[Path] = ROOT / "tests" / "web" / "fixtures" / "expander.json"
SUBJECT: Final[str] = "m06-expander-fixture"


def document() -> dict[str, Any]:
    long = "x" * 1900
    deep: dict[str, Any] = {"level": 15}
    for level in range(14, -1, -1):
        deep = {"level": level, "next": deep}
    return {
        "title": "readWhole fixture ‮evil",
        "escaped keys": {"a/b": 1, "m~n": 2, "~1": 3, "": 4, "ünï": 5},
        "deep": deep,
        "long_array": [{"i": i, "pair": [i, i + 0.5]} for i in range(230)],
        "nested_arrays": [list(range(25)), list(range(21)), list(range(20))],
        "literal_marker": {"$elided": {"pointer": "/literal_marker", "members": 2}},
        "literal_tail": [1, 2, {"$elided": {"pointer": "/literal_tail", "items": 3}}],
        # One key needs RFC 6901 escaping in the pointer the expander asks for: `~1` and `~0`.
        "wide": {("a/b~c" if i == 0 else f"k{i:02d}"): {"text": long, "i": i} for i in range(36)},
        "flat_wide": {f"s{i:02d}": long for i in range(40)},
        "numbers": [0, 1e-300, 31487.641739605908, 2**53, -1.5, 0.1],
        "empty": {},
        "empty_list": [],
        "nothing": None,
        "flag": True,
    }


def _containers(node: Any, pointer: str = "") -> Iterator[tuple[str, Any]]:
    if isinstance(node, dict):
        yield pointer, node
        for key, value in node.items():
            yield from _containers(value, f"{pointer}/{escape_token(key)}")
    elif isinstance(node, list):
        yield pointer, node
        for index, value in enumerate(node):
            yield from _containers(value, f"{pointer}/{index}")


def build() -> dict[str, Any]:
    source = document()
    sha = hashlib.sha256(canonical_json(source)).hexdigest()
    responses: dict[str, Any] = {}
    for pointer, node in _containers(source):
        cursors: list[str | None] = [None]
        if isinstance(node, list):
            cursors += [encode_offset(k) for k in range(MAX_PAGE, len(node), MAX_PAGE)]
        for cursor in cursors:
            view = project(
                source,
                subject_id=SUBJECT,
                sha256=sha,
                pointer=pointer,
                depth=MAX_DEPTH,
                cursor=cursor,
                limit=MAX_PAGE,
            )
            responses[f"{pointer}\n{cursor or ''}"] = bound_document(view.as_document())
    return {
        "generator": "scripts/m06_web_expander_fixture.py",
        "depth": MAX_DEPTH,
        "limit": MAX_PAGE,
        "sha256": sha,
        "expected": bound_document(source),
        "responses": responses,
    }


def render() -> str:
    return json.dumps(build(), sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    arguments = parser.parse_args(argv)
    text = render()
    if arguments.write:
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        TARGET.write_text(text, encoding="utf-8")
        print(f"wrote {TARGET.relative_to(ROOT)} ({len(text)} bytes)")
        return 0
    if not TARGET.is_file() or TARGET.read_text(encoding="utf-8") != text:
        print(f"{TARGET.relative_to(ROOT)} is stale: run {Path(__file__).name} --write")
        return 1
    print(f"{TARGET.relative_to(ROOT)} matches the server's projection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
