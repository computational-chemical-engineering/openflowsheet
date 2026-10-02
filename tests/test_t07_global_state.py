"""T07 gate G20: how "no other process-global mutable state" is established (design note §9.5).

(1) **The static audit.** Every line of `src/openflowsheet/**/*.py` is scanned for §9.5's eleven
patterns, verbatim, over its *code*: comments and string literals (docstrings included) are
blanked first with `tokenize`, W0.5's proposal (`docs/t07-measurements.md` §W0.5), which removes
its six prose hits of `\\bglobal\\s+\\w` without widening any pattern. Every hit must be listed in
`tests/data/t07_global_state_allowlist.json` with its file, its line text, the patterns it hits,
how many lines of the file carry that text, and a justification; a hit not on the list, or an
entry with no hit, fails. The W2 `except BaseException` sites are not in the scan: no §9.5 pattern
covers them (W4b's no-broad-except lint, `tests/test_t07_interrupt.py`, holds them instead).

(3) **Benchmark monkeypatching is out of the import graph:** no module of `openflowsheet`
imports `benchmarks` (the T06 harness patches module attributes).

(2), the dynamic A-then-B test, is `tests/test_t07_w4c_process_executor.py`'s.
"""

from __future__ import annotations

import ast
import io
import json
import re
import tokenize
from collections import Counter

from conftest import REPO_ROOT

SOURCE = REPO_ROOT / "src" / "openflowsheet"
ALLOWLIST = REPO_ROOT / "tests" / "data" / "t07_global_state_allowlist.json"
#: §9.5 (1), verbatim.
PATTERNS: dict[str, re.Pattern[str]] = {
    name: re.compile(pattern)
    for name, pattern in {
        "np.random": r"np\.random\.(seed|set_state|get_state|rand|randn|randint|random|normal"
        r"|uniform|choice|shuffle|permutation)",
        "random": r"^\s*import random\b|\brandom\.(seed|random|randint|choice|shuffle)",
        "global": r"\bglobal\s+\w",
        "environ": r"os\.environ\[[^]]+\]\s*=|os\.environ\.(update|setdefault|pop)|os\.putenv",
        "np.seterr": r"np\.seterr\(|np\.set_printoptions\(",
        "warnings": r"warnings\.(simplefilter|filterwarnings)",
        "recursion": r"sys\.setrecursionlimit",
        "cache": r"@(functools\.)?(lru_cache|cache)\b",
        "GlobalOptions": r"GlobalOptions",
        "threading.local": r"threading\.local\(",
        "ContextVar": r"ContextVar\(",
    }.items()
}
#: What `tokenize` calls prose: comments, and every piece of a string literal but an f-string's
#: replacement fields.
PROSE = {
    tokenize.COMMENT,
    tokenize.STRING,
    tokenize.FSTRING_START,
    tokenize.FSTRING_MIDDLE,
    tokenize.FSTRING_END,
}


def code_lines(text: str) -> list[str]:
    """`text`'s lines with every comment and string literal blanked (same line count)."""
    lines = [list(line) for line in text.splitlines()]
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type not in PROSE:
            continue
        (first, start), (last, end) = token.start, token.end
        for row in range(first, last + 1):
            line = lines[row - 1]
            begin = start if row == first else 0
            stop = end if row == last else len(line)
            line[begin:stop] = " " * (stop - begin)
    return ["".join(line) for line in lines]


def scan() -> dict[tuple[str, str], tuple[tuple[str, ...], int]]:
    """`{(file, stripped line text): (patterns hit, occurrences)}` over the package's code."""
    found: dict[tuple[str, str], tuple[tuple[str, ...], int]] = {}
    for path in sorted(SOURCE.rglob("*.py")):
        text = path.read_text("utf-8")
        relative = path.relative_to(SOURCE).as_posix()
        for code, line in zip(code_lines(text), text.splitlines(), strict=True):
            hits = tuple(name for name, pattern in PATTERNS.items() if pattern.search(code))
            if hits:
                key = (relative, line.strip())
                previous = found.get(key)
                if previous is not None:
                    assert previous[0] == hits, key
                found[key] = (hits, 1 if previous is None else previous[1] + 1)
    return found


def test_the_scan_blanks_prose_and_keeps_code() -> None:
    source = (
        '"""global state, a docstring"""\n'
        "x = 1  # the global generator\n"
        "def f():\n"
        "    global counter\n"
        "    return f'global {np.random.seed(1)} text'\n"
    )
    code = code_lines(source)
    assert [bool(PATTERNS["global"].search(line)) for line in code] == [
        False,
        False,
        False,
        True,
        False,
    ]
    # An f-string's replacement field is code.
    assert PATTERNS["np.random"].search(code[4])


def test_g20_every_hit_is_allowlisted_and_every_entry_is_hit() -> None:
    entries = json.loads(ALLOWLIST.read_text("utf-8"))["entries"]
    listed = {
        (entry["file"], entry["line"]): (tuple(entry["patterns"]), entry["occurrences"])
        for entry in entries
    }
    assert len(listed) == len(entries), "one entry per file and line text"
    assert all(entry["justification"].strip() for entry in entries)
    found = scan()
    unlisted = {key: value for key, value in found.items() if listed.get(key) != value}
    stale = {key: value for key, value in listed.items() if found.get(key) != value}
    assert unlisted == {}, f"hits not on the allowlist (decide and list them): {unlisted}"
    assert stale == {}, f"allowlist entries with no such hit: {stale}"
    # By line: W0.5's 16 code hits (3 + 1 on regularity.py's three lines, 12 `_artifact_hash`),
    # W1's 4 schema `@cache`s, W3e's solution-state validator, W4b's INTERRUPT_CHECK, W6b's
    # `published_schemas` and MCP tool list; T08 W2's kinetic CSTR `_artifact_hash` (13th model).
    per_line = Counter(hit for hits, count in found.values() for hit in hits for _ in range(count))
    assert per_line == Counter({"cache": 20, "np.random": 3, "random": 1, "ContextVar": 1})


def test_openflowsheet_never_imports_benchmarks() -> None:
    offenders = []
    for path in sorted(SOURCE.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text("utf-8"))):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            offenders.extend(
                f"{path.relative_to(SOURCE)}:{node.lineno} {name}"
                for name in names
                if name == "benchmarks" or name.startswith("benchmarks.")
            )
    assert offenders == []
