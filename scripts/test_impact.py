"""S16: per-test coverage and test-impact selection, an inner-loop aid (docs/test-impact.md).

    test_impact.py build  [--base SHA] [--out DIR] [--workers N]
    test_impact.py select --base SHA [--map DIR]
    test_impact.py select --lines PATH:START-END [--base SHA] [--map DIR]
    test_impact.py run    --base SHA [--map DIR] [--log FILE] [--workers N] [-- PYTEST-ARGS...]

`build` runs the default-marker suite at a clean worktree of the base commit under coverage, in the
test-map venv (requirements-testmap.lock), and writes a map: for every test, the lines of `src/`,
`scripts/`, `benchmarks/` and `tests/` it executes (its subprocesses included) and the repository
files it opens for reading (scripts/test_impact_runtime.py). `select` maps the diff from the base
to the working tree onto node ids; `run` runs them. Whenever the selection cannot be sure it falls
back to the full default-marker suite and says why (exit code 3 from `select`).

CI on both architectures stays the merge gate; selection never replaces it (R-1040).
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import sysconfig
import tempfile
import time
import tokenize
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path.home() / ".cache" / "openflowsheet" / "testmap"
SOURCE_DIRS = ("src", "scripts", "benchmarks", "tests")
EXIT_FULL = 3
COLLECTION = ""
MAP_FORMAT = 1
RUNTIME = "ofs_testmap_runtime"
#: Test files whose node ids differ between processes (a parameter's repr holds an object address),
#: so pytest-xdist refuses the session ("Different tests were collected"). A build with workers
#: runs them in a second, serial pytest call (docs/S16_DECISIONS.md, B-4).
XDIST_SERIAL = ("tests/test_t07_w2d_noncanonical.py",)


class FallbackError(Exception):
    """The selection cannot be sure: run the full default-marker suite, for this reason."""


# -- git -------------------------------------------------------------------------------------------


def git(*args: str, cwd: Path = ROOT, check: bool = True) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and done.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {done.stderr.strip()}")
    return done.stdout


def resolve(base: str, cwd: Path = ROOT) -> str:
    return git("rev-parse", "--verify", f"{base}^{{commit}}", cwd=cwd).strip()


def tree_of(base: str, cwd: Path = ROOT) -> str:
    return git("rev-parse", f"{base}^{{tree}}", cwd=cwd).strip()


# -- the map (SQLite; written by `build` and by the tests' synthetic maps) -------------------------

SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE tests (id INTEGER PRIMARY KEY, nodeid TEXT UNIQUE NOT NULL, outcome TEXT NOT NULL);
CREATE TABLE contexts (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
CREATE TABLE test_fixtures (test_id INTEGER NOT NULL, context_id INTEGER NOT NULL);
CREATE TABLE files (id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL);
CREATE TABLE blobs (id INTEGER PRIMARY KEY, bits BLOB NOT NULL);
CREATE TABLE lines (
    file_id INTEGER NOT NULL, context_id INTEGER NOT NULL, blob_id INTEGER NOT NULL
);
CREATE TABLE opens (file_id INTEGER NOT NULL, context_id INTEGER NOT NULL);
"""
INDEXES = """
CREATE INDEX lines_file ON lines (file_id);
CREATE INDEX opens_file ON opens (file_id);
CREATE INDEX fixtures_context ON test_fixtures (context_id);
"""


def numbits(lines: Iterable[int]) -> bytes:
    """Coverage's numbits form: bit `n % 8` of byte `n // 8` is line `n`."""
    numbers = list(lines)
    data = bytearray(max(numbers, default=-1) // 8 + 1)
    for number in numbers:
        data[number // 8] |= 1 << (number % 8)
    return bytes(data)


def numbits_union(left: bytes, right: bytes) -> bytes:
    if len(left) < len(right):
        left, right = right, left
    return bytes(a | b for a, b in zip(left, right.ljust(len(left), b"\0"), strict=True))


def has_any(bits: bytes, lines: Iterable[int]) -> bool:
    return any(n // 8 < len(bits) and bits[n // 8] >> (n % 8) & 1 for n in lines)


@dataclass
class MapData:
    """The map in memory, before it is written."""

    meta: dict[str, str] = field(default_factory=dict)
    tests: dict[str, str] = field(default_factory=dict)  # node id -> outcome
    fixtures: dict[str, set[str]] = field(default_factory=dict)  # node id -> fixture contexts
    lines: dict[tuple[str, str], bytes] = field(default_factory=dict)  # (path, context) -> numbits
    opens: set[tuple[str, str]] = field(default_factory=set)  # (path, context)

    def add_lines(self, path: str, context: str, bits: bytes) -> None:
        key = (path, context)
        self.lines[key] = numbits_union(self.lines[key], bits) if key in self.lines else bits

    def write(self, target: Path) -> None:
        target.unlink(missing_ok=True)
        with sqlite3.connect(target) as db:
            db.executescript(SCHEMA)
            ids: dict[str, dict[str, int]] = {"files": {}, "contexts": {}, "blobs": {}}

            def ident(table: str, value: str) -> int:
                known = ids[table]
                if value not in known:
                    column = "name" if table == "contexts" else "path"
                    known[value] = (
                        db.execute(f"INSERT INTO {table} ({column}) VALUES (?)", (value,)).lastrowid
                        or 0
                    )
                return known[value]

            blob_ids: dict[bytes, int] = {}
            db.executemany("INSERT INTO meta VALUES (?, ?)", sorted(self.meta.items()))
            for nodeid, outcome in sorted(self.tests.items()):
                test_id = db.execute(
                    "INSERT INTO tests (nodeid, outcome) VALUES (?, ?)", (nodeid, outcome)
                ).lastrowid
                for fixture in sorted(self.fixtures.get(nodeid, ())):
                    db.execute(
                        "INSERT INTO test_fixtures VALUES (?, ?)",
                        (test_id, ident("contexts", fixture)),
                    )
            for (path, context), bits in sorted(self.lines.items()):
                if bits not in blob_ids:
                    blob_ids[bits] = (
                        db.execute("INSERT INTO blobs (bits) VALUES (?)", (bits,)).lastrowid or 0
                    )
                db.execute(
                    "INSERT INTO lines VALUES (?, ?, ?)",
                    (ident("files", path), ident("contexts", context), blob_ids[bits]),
                )
            for path, context in sorted(self.opens):
                db.execute(
                    "INSERT INTO opens VALUES (?, ?)",
                    (ident("files", path), ident("contexts", context)),
                )
            db.executescript(INDEXES)


class TestMap:
    """A written map, read-only."""

    def __init__(self, directory: Path) -> None:
        path = directory / "map.sqlite"
        if not path.is_file():
            raise FallbackError(f"no map at {directory} (build one: scripts/test_impact.py build)")
        self.db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        self.meta = dict(self.db.execute("SELECT key, value FROM meta"))
        self.nodeids = {nodeid for (nodeid,) in self.db.execute("SELECT nodeid FROM tests")}

    def _file_id(self, path: str) -> int | None:
        row = self.db.execute("SELECT id FROM files WHERE path = ?", (path,)).fetchone()
        return None if row is None else int(row[0])

    def has_lines(self, path: str) -> bool:
        file_id = self._file_id(path)
        query = "SELECT 1 FROM lines WHERE file_id = ? LIMIT 1"
        return file_id is not None and self.db.execute(query, (file_id,)).fetchone() is not None

    def line_contexts(self, path: str, lines: Iterable[int]) -> set[str]:
        """The contexts that executed any of `lines` of `path`."""
        wanted = sorted(set(lines))
        file_id = self._file_id(path)
        if file_id is None or not wanted:
            return set()
        rows = self.db.execute(
            "SELECT contexts.name, blobs.bits FROM lines JOIN contexts ON contexts.id = context_id"
            " JOIN blobs ON blobs.id = blob_id WHERE file_id = ?",
            (file_id,),
        )
        return {name for name, bits in rows if has_any(bits, wanted)}

    def open_contexts(self, path: str) -> set[str]:
        file_id = self._file_id(path)
        if file_id is None:
            return set()
        rows = self.db.execute(
            "SELECT contexts.name FROM opens JOIN contexts ON contexts.id = context_id"
            " WHERE file_id = ?",
            (file_id,),
        )
        return {name for (name,) in rows}

    def tests_of(self, contexts: set[str], where: str) -> set[str]:
        """Node ids for contexts: a test's own, or every test that uses a shared fixture."""
        if COLLECTION in contexts:
            raise FallbackError(f"{where} runs at import or collection time in the pytest process")
        selected: set[str] = set()
        for context in contexts:
            if context in self.nodeids:
                selected.add(context)
            elif context.startswith("fixture:"):
                selected |= {
                    nodeid
                    for (nodeid,) in self.db.execute(
                        "SELECT nodeid FROM tests JOIN test_fixtures ON test_id = tests.id"
                        " JOIN contexts ON contexts.id = context_id WHERE contexts.name = ?",
                        (context,),
                    )
                }
            else:
                raise FallbackError(f"{where} ran under an unattributed context {context!r}")
        return selected


# -- the diff --------------------------------------------------------------------------------------


@dataclass
class Change:
    path: str
    status: str  # A, D, M, T (git's letters; untracked files are A)
    hunks: list[tuple[int, int, int, int]] = field(
        default_factory=list
    )  # old start, count, new ...


HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def parse_diff(text: str) -> dict[str, list[tuple[int, int, int, int]]]:
    """Hunks per path of a `git diff -U0 --no-renames` output (paths as on the new side)."""
    hunks: dict[str, list[tuple[int, int, int, int]]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("diff --git "):
            current = None
        elif line.startswith("--- ") and current is None:
            old = line[4:]
            current = None if old == "/dev/null" else old.removeprefix("a/")
        elif line.startswith("+++ "):
            new = line[4:]
            if new != "/dev/null":
                current = new.removeprefix("b/")
            if current is not None:
                hunks.setdefault(current, [])
        elif current is not None and (match := HUNK.match(line)):
            old_start, old_count, new_start, new_count = match.groups()
            hunks[current].append(
                (
                    int(old_start),
                    1 if old_count is None else int(old_count),
                    int(new_start),
                    1 if new_count is None else int(new_count),
                )
            )
    return hunks


def changes_since(base: str, cwd: Path = ROOT) -> list[Change]:
    """The working tree against `base`: staged, unstaged and untracked (not ignored) files."""
    changes: dict[str, Change] = {}
    for line in git("diff", "--no-renames", "--name-status", base, cwd=cwd).splitlines():
        status, path = line.split("\t", 1)
        changes[path] = Change(path, status[0])
    for path, hunks in parse_diff(
        git("diff", "--no-renames", "--no-color", "--no-ext-diff", "-U0", base, cwd=cwd)
    ).items():
        if path in changes:
            changes[path].hunks = hunks
    for path in git("ls-files", "--others", "--exclude-standard", cwd=cwd).splitlines():
        changes[path] = Change(path, "A")
    return [changes[path] for path in sorted(changes)]


# -- Python sources --------------------------------------------------------------------------------

Scope = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef


def _start(node: ast.stmt) -> int:
    decorators = getattr(node, "decorator_list", ())
    return min([node.lineno, *(d.lineno for d in decorators)])


def _end(node: ast.stmt) -> int:
    return node.end_lineno or node.lineno


def _children(node: ast.AST) -> Iterator[ast.stmt]:
    for name in ("body", "orelse", "finalbody", "handlers", "cases"):
        for child in getattr(node, name, ()):
            if isinstance(child, ast.stmt):
                yield child
            else:  # an except handler or a match case: its body holds the statements
                yield from (s for s in getattr(child, "body", ()) if isinstance(s, ast.stmt))


class Source:
    """A Python file's statements and scopes, by line."""

    def __init__(self, text: str, where: str) -> None:
        try:
            self.tree = ast.parse(text)
        except SyntaxError as error:
            raise FallbackError(
                f"{where} does not parse ({error.msg}, line {error.lineno})"
            ) from None
        self.lines = text.splitlines()
        self.code_lines = _code_lines(text)
        self.qualnames: dict[str, list[Scope]] = {}
        self._index(self.tree, "")

    def _index(self, node: ast.AST, prefix: str) -> None:
        for child in _children(node):
            if isinstance(child, Scope):
                name = f"{prefix}{child.name}"
                self.qualnames.setdefault(name, []).append(child)
                self._index(child, f"{name}.")
            else:
                self._index(child, prefix)

    def path_to(self, line: int) -> list[ast.stmt]:
        """The statements containing `line`, outermost first."""
        chain: list[ast.stmt] = []
        nodes: Iterable[ast.stmt] = self.tree.body
        while True:
            for node in nodes:
                if _start(node) <= line <= _end(node):
                    chain.append(node)
                    nodes = list(_children(node))
                    break
            else:
                return chain

    def is_code(self, line: int) -> bool:
        """False for a blank or comment-only line (it changes line numbers, not behaviour)."""
        return line in self.code_lines

    def function_of(self, line: int) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
        """The innermost function whose body (after the header) holds `line`."""
        for node in reversed(self.path_to(line)):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and line > _header_end(
                node
            ):
                return node
        return None

    def qualname(self, scope: Scope) -> str:
        for name, scopes in self.qualnames.items():
            if any(s is scope for s in scopes):
                return name
        raise KeyError(scope)

    def statement_lines(self, line: int) -> set[int]:
        """The lines whose coverage decides whether the statement at `line` ran."""
        chain = self.path_to(line)
        if not chain:
            return set()
        node = chain[-1]
        body = list(_children(node))
        if not body:
            return set(range(_start(node), _end(node) + 1))
        header_end = _header_end(node)
        if line <= header_end:
            return set(range(_start(node), header_end + 1))
        return set(range(_start(node), _end(node) + 1))


def _header_end(node: ast.stmt) -> int:
    body = list(_children(node))
    return (min(_start(child) for child in body) - 1) if body else _end(node)


def _body_lines(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[int]:
    return set(range(_header_end(node) + 1, _end(node) + 1))


def _code_lines(text: str) -> set[int]:
    """Lines holding a token other than a comment or a line break (multi-line strings too)."""
    lines: set[int] = set()
    skip = {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT}
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type not in skip and token.type != tokenize.ENDMARKER:
                lines.update(range(token.start[0], token.end[0] + 1))
    except (tokenize.TokenError, SyntaxError):
        lines.update(range(1, text.count("\n") + 2))
    return lines


def _mentioned_at(base: str, cwd: Path, name: str) -> bool:
    """Whether any file of the base's tree holds `name` as a whole word (an error counts as yes)."""
    found = subprocess.run(
        ["git", "grep", "-q", "-w", "-F", "-e", name, base, "--"], cwd=cwd, capture_output=True
    )
    return found.returncode != 1


def _fresh_definition(
    node: ast.stmt, new: Source, added: set[int], mentioned: Callable[[str], bool]
) -> bool:
    """A new, undecorated def whose name the base never mentions: only changed code reaches it.

    The name must occur nowhere in the base's tree, as a whole word (`mentioned`): then it binds,
    shadows or overrides nothing the base binds in any scope (an import, an assignment, a loop or
    `with` target, a `global`, a sibling base's method in a mixin's MRO), and no base code reaches
    it by a literal `getattr`/`hasattr` (docs/S16_DECISIONS.md, B-13)."""
    import builtins

    if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) or node.decorator_list:
        return False
    if not set(range(_start(node), _end(node) + 1)) <= added:
        return False
    if node.name in dir(builtins) or node.name.startswith("__") or mentioned(node.name):
        return False
    owner = new.qualname(node).rpartition(".")[0]
    if owner:  # a method: only of a class with no bases, so it overrides nothing
        classes = new.qualnames.get(owner, [])
        return all(isinstance(c, ast.ClassDef) and not (c.bases or c.keywords) for c in classes)
    return True


# -- selection -------------------------------------------------------------------------------------


@dataclass
class Selection:
    nodes: set[str] = field(default_factory=set)
    fallback: str | None = None

    def whole_files(self) -> Selection:
        """Every selected node id widened to its whole test file (docs/S16_DECISIONS.md B-11).

        Per-test coverage records a line only for the test that ran it. A module-scoped fixture or
        a module-level cache runs in the first test that needs it, so the file's later tests depend
        on the line without recording it (recall: 46 misses in test_t07_g12_no_weakening.py), and
        a file whose tests use an earlier test's state fails when run in part
        (test_m06_browser_smoke.py). A whole file runs in its own order with its own fixtures.
        """
        return Selection({node.split("::", 1)[0] for node in self.nodes}, self.fallback)


def is_test_module(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return path.startswith("tests/") and name.endswith(".py") and name.startswith("test_")


def _pytest_section(text: str) -> str:
    match = re.search(r"^\[tool\.pytest[^\]]*\]\n(.*?)(?=^\[|\Z)", text, re.M | re.S)
    return match.group(0) if match else ""


def _fallback_rule(change: Change, base: str, cwd: Path) -> str | None:
    """The path rules that need no map (docs/test-impact.md, "Fallbacks")."""
    path = change.path
    name = path.rsplit("/", 1)[-1]
    if change.status in ("A", "D"):
        return None if path.startswith("docs/") else f"{path}: new or deleted file"
    if change.status != "M":
        return f"{path}: changed type or mode ({change.status})"
    if name == "conftest.py":
        return f"{path}: a conftest.py changed"
    if name in ("pytest.ini", "tox.ini", "setup.cfg"):
        return f"{path}: pytest configuration may have changed"
    if path == "pyproject.toml":
        old = git("show", f"{base}:{path}", cwd=cwd)
        if _pytest_section(old) != _pytest_section((cwd / path).read_text(encoding="utf-8")):
            return f"{path}: its pytest section changed"
    if path.startswith("tests/"):
        if name.endswith("_support.py") or path.startswith("tests/support/"):
            return f"{path}: a shared test support module changed"
        if not is_test_module(path):
            return f"{path}: a file under tests/ that is not a test module changed"
    return None


def _open_rule(test_map: TestMap, path: str, *, required: bool) -> set[str]:
    contexts = test_map.open_contexts(path)
    if not contexts and required:
        raise FallbackError(f"{path}: the map has never seen this file opened")
    return test_map.tests_of(contexts, f"{path} (opened)")


def _python_rule(test_map: TestMap, change: Change, base: str, cwd: Path) -> set[str]:
    path = change.path
    if not test_map.has_lines(path):
        return _open_rule(test_map, path, required=True)
    old = Source(git("show", f"{base}:{path}", cwd=cwd), f"{path} (base)")
    new = Source((cwd / path).read_text(encoding="utf-8"), path)
    selected = _open_rule(test_map, path, required=False)
    for old_start, old_count, new_start, new_count in change.hunks:
        added = set(range(new_start, new_start + new_count))
        for line in range(old_start, old_start + old_count):
            if not old.is_code(line):
                continue
            if old.function_of(line) is None:
                raise FallbackError(f"{path}:{line} (base): import-time code changed")
            where = f"{path}:{line} (base)"
            selected |= test_map.tests_of(
                test_map.line_contexts(path, old.statement_lines(line)), where
            )
        for line in sorted(added):
            if not new.is_code(line):
                continue
            selected |= _new_line(
                test_map, path, line, old, new, added, lambda name: _mentioned_at(base, cwd, name)
            )
    return selected


def _new_line(
    test_map: TestMap,
    path: str,
    line: int,
    old: Source,
    new: Source,
    added: set[int],
    mentioned: Callable[[str], bool],
) -> set[str]:
    """An added or rewritten line: the tests of the innermost enclosing function the base has
    (of every base function with its qualified name)."""
    chain = new.path_to(line)
    functions = [
        node
        for node in chain
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and line > _header_end(node)
    ]
    for function in reversed(functions):
        name = new.qualname(function)
        # Every base function of that name: `if`/`else` twins, property setters, overloads (B-14).
        bodies = [
            _body_lines(each)
            for each in old.qualnames.get(name, [])
            if isinstance(each, ast.FunctionDef | ast.AsyncFunctionDef)
        ]
        if bodies:
            where = f"{path}:{line} (in {name})"
            return test_map.tests_of(test_map.line_contexts(path, set().union(*bodies)), where)
    outer = next((n for n in chain if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)), None)
    if outer is not None and _fresh_definition(outer, new, added, mentioned):
        return set()
    raise FallbackError(f"{path}:{line}: import-time code changed")


def select(base: str, map_dir: Path | None = None, cwd: Path = ROOT) -> Selection:
    """The node ids the change from `base` to the working tree can affect, or a fallback."""
    try:
        sha = resolve(base, cwd)
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", sha, "HEAD"], cwd=cwd, capture_output=True
        )
        if ancestor.returncode != 0:
            raise FallbackError(f"base {sha[:12]} is not an ancestor of HEAD")
        test_map = TestMap(map_dir or CACHE / sha)
        if test_map.meta.get("base") != sha or test_map.meta.get("tree") != tree_of(sha, cwd):
            raise FallbackError(f"the map at {map_dir or CACHE / sha} is not of base {sha[:12]}")
        if test_map.meta.get("pytest_args"):
            raise FallbackError(f"the map is of a partial run ({test_map.meta['pytest_args']})")
        selected: set[str] = set()
        for change in changes_since(sha, cwd):
            reason = _fallback_rule(change, sha, cwd)
            if reason is not None:
                raise FallbackError(reason)
            path = change.path
            if path.startswith("docs/"):
                if change.status == "M":
                    selected |= _open_rule(test_map, path, required=False)
            elif path.endswith(".py"):
                if is_test_module(path):
                    selected.add(path)
                selected |= _python_rule(test_map, change, sha, cwd)
            else:
                selected |= _open_rule(test_map, path, required=True)
        return Selection(_collapse(selected))
    except FallbackError as reason:
        return Selection(fallback=str(reason))


def _collapse(nodes: set[str]) -> set[str]:
    """Drop node ids a selected test file already includes."""
    files = {node for node in nodes if "::" not in node}
    return {node for node in nodes if "::" not in node or node.split("::", 1)[0] not in files}


def select_lines(spec: str, base: str, map_dir: Path | None, cwd: Path = ROOT) -> Selection:
    """The tests that execute `path:start-end` at the map's base."""
    match = re.fullmatch(r"(.+):(\d+)(?:-(\d+))?", spec)
    if match is None:
        raise SystemExit(f"--lines wants PATH:START-END, got {spec!r}")
    path, start, end = match.group(1), int(match.group(2)), int(match.group(3) or match.group(2))
    try:
        sha = resolve(base, cwd)
        test_map = TestMap(map_dir or CACHE / sha)
        contexts = test_map.line_contexts(path, range(start, end + 1))
        return Selection(test_map.tests_of(contexts, spec))
    except FallbackError as reason:
        return Selection(fallback=str(reason))


# -- build -----------------------------------------------------------------------------------------


def _install_runtime() -> Path:
    """Put the runtime and its .pth into this (test-map) venv's site-packages; never the repo's."""
    if sys.prefix == sys.base_prefix:
        raise SystemExit(
            "build runs in the test-map venv (docs/test-impact.md), not a system Python"
        )
    try:
        import coverage  # noqa: F401
    except ImportError:
        raise SystemExit("coverage is missing: install requirements-testmap.lock") from None
    site = Path(sysconfig.get_paths()["purelib"])
    runtime = (ROOT / "scripts" / "test_impact_runtime.py").read_bytes()
    target = site / f"{RUNTIME}.py"
    if not target.exists() or target.read_bytes() != runtime:
        target.write_bytes(runtime)
    (site / "ofs_testmap.pth").write_text(f"import {RUNTIME}\n")
    return site / "ofs_testmap_active.json"


def _fold(run: Path, root: Path, data: MapData) -> None:
    """Read the run's coverage files, open records and test records into `data`."""
    prefix = str(root) + "/"
    for path in sorted((run / "cov").glob(".coverage*")):
        with sqlite3.connect(path) as db:
            (version,) = db.execute("SELECT version FROM coverage_schema").fetchone()
            if int(version) != 7:
                raise SystemExit(f"{path}: coverage schema {version}, this tool reads 7")
            contexts = dict(db.execute("SELECT id, context FROM context"))
            files = dict(db.execute("SELECT id, path FROM file"))
            for file_id, context_id, bits in db.execute(
                "SELECT file_id, context_id, numbits FROM line_bits"
            ):
                name = files[file_id]
                if name.startswith(prefix):
                    data.add_lines(name[len(prefix) :], contexts[context_id], bytes(bits))
    for path in sorted((run / "opens").glob("*.json")):
        data.opens |= {(name, context) for context, name in json.loads(path.read_text())}
    for path in sorted((run / "tests").glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            data.tests[record["nodeid"]] = record["outcome"]
            data.fixtures[record["nodeid"]] = set(record["fixtures"])


def build(base: str, out: Path | None, workers: int, extra: list[str]) -> int:
    sha = resolve(base)
    out = out or CACHE / sha
    out.mkdir(parents=True, exist_ok=True)
    pointer = _install_runtime()
    if pointer.exists():
        raise SystemExit(f"another build is active ({pointer}); remove it if it is stale")
    scratch = Path(tempfile.mkdtemp(prefix="testmap-", dir=out))
    tree, run = scratch / "tree", scratch / "run"
    for sub in ("cov", "opens", "tests", "ctx"):
        (run / sub).mkdir(parents=True)
    git("worktree", "add", "--detach", str(tree), sha)
    log = out / "build.log"
    try:
        pointer.write_text(
            json.dumps(
                {
                    "root_pid": os.getpid(),
                    "run": str(run),
                    "root": str(tree),
                    "source": [str(tree / name) for name in SOURCE_DIRS],
                }
            )
        )
        environment = dict(os.environ, PYTHONPATH="src")
        environment.update(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
        command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", RUNTIME]
        commands = [command + extra]
        if workers > 0:
            ignored = [f"--ignore={name}" for name in XDIST_SERIAL]
            commands = [command + ["-n", str(workers), *ignored, *extra]]
            if not extra:
                commands.append(command + list(XDIST_SERIAL))
        started = time.monotonic()
        exit_code = 0
        with log.open("w") as stream:
            for each in commands:
                stream.write(f"$ {' '.join(each)}\n")
                stream.flush()
                exit_code = max(
                    exit_code,
                    subprocess.call(
                        each, cwd=tree, env=environment, stdout=stream, stderr=subprocess.STDOUT
                    ),
                )
        wall = time.monotonic() - started
    finally:
        pointer.unlink(missing_ok=True)
    data = MapData()
    _fold(run, tree, data)
    data.meta = {
        "format": str(MAP_FORMAT),
        "base": sha,
        "tree": tree_of(sha),
        "pytest_exit": str(exit_code),
        "wall_seconds": f"{wall:.0f}",
        "workers": str(workers),
        "tests": str(len(data.tests)),
        "pytest_args": " ".join(extra),
    }
    data.write(out / "map.sqlite")
    (out / "meta.json").write_text(json.dumps(data.meta, indent=2) + "\n")
    git("worktree", "remove", "--force", str(tree))
    shutil.rmtree(scratch)
    outcomes: dict[str, int] = {}
    for outcome in data.tests.values():
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
    size = (out / "map.sqlite").stat().st_size
    print(
        f"TESTMAP {sha[:12]}: {len(data.tests)} tests {outcomes}, pytest exit {exit_code}, "
        f"wall {wall:.0f}s, map {size / 1e6:.1f} MB (log {log})"
    )
    return 0


# -- run -------------------------------------------------------------------------------------------

SUMMARY = re.compile(r"^=*\s*(\d+ (?:passed|failed|error|skipped|deselected).*?) in [\d.]+s")
COUNT = re.compile(r"(\d+) (\w+)")
NO_TESTS = 5  # pytest's exit code when it collected nothing


def _runs(selection: Selection, workers: int) -> list[tuple[list[str], list[str]]]:
    """The pytest calls of a run as (arguments, node ids): one call, or with workers an xdist call
    and a serial one.

    `XDIST_SERIAL` files abort an xdist session (B-4), so with workers they run in a second, serial
    call, on a fallback and whenever the selection holds them (docs/S16_DECISIONS.md, B-12)."""
    if selection.fallback is not None:
        if workers <= 0:
            return [([], [])]
        ignored = [f"--ignore={name}" for name in XDIST_SERIAL]
        return [(["-n", str(workers), *ignored], []), (list(XDIST_SERIAL), [])]
    nodes = sorted(selection.nodes)
    if workers <= 0:
        return [([], nodes)]
    serial = [node for node in nodes if node.split("::", 1)[0] in XDIST_SERIAL]
    parallel = [node for node in nodes if node.split("::", 1)[0] not in XDIST_SERIAL]
    calls = [(["-n", str(workers)], parallel)] if parallel else []
    return calls + ([([], serial)] if serial else [])


def _counts(text: str) -> dict[str, int]:
    """pytest's closing counts (`3 passed, 1 skipped`) of one run's output, by kind."""
    match = next((m for m in map(SUMMARY.match, reversed(text.splitlines())) if m), None)
    counts: dict[str, int] = {}
    for number, kind in COUNT.findall(match.group(1) if match else ""):
        kind = "error" if kind == "errors" else kind
        counts[kind] = counts.get(kind, 0) + int(number)
    return counts


def run(
    base: str,
    map_dir: Path | None,
    log: Path | None,
    extra: list[str],
    repo: Path,
    workers: int = 0,
) -> int:
    if any(
        arg in ("-n", "--numprocesses") or arg.startswith(("-n", "--numprocesses="))
        for arg in extra
    ):
        raise SystemExit("run takes workers as --workers N, which keeps XDIST_SERIAL serial (B-12)")
    selection = select(base, map_dir, repo).whole_files()
    sha = git("rev-parse", "--short", "HEAD", cwd=repo).strip()
    log = log or Path(os.environ.get("TMPDIR", "/tmp")) / f"test-impact-{sha}.log"
    command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rs", *extra]
    if selection.fallback is not None:
        print(f"full suite: {selection.fallback}", file=sys.stderr)
    elif not selection.nodes:
        print(f"TEST-IMPACT PASS {sha}: selected 0, fallback no, nothing to run")
        return 0
    started = time.monotonic()
    environment = dict(os.environ, PYTHONPATH="src")
    codes: list[int] = []
    counts: dict[str, int] = {}
    with log.open("w") as stream:
        for index, (arguments, nodes) in enumerate(_runs(selection, workers)):
            each = command + arguments
            if nodes:  # through an @file, without shell splitting
                listing = log.with_suffix(f".{index}.args")
                listing.write_text("".join(f"{node}\n" for node in nodes))
                each.append(f"@{listing}")
            stream.write(f"$ {' '.join(each)}\n")
            stream.flush()
            start = stream.tell()
            codes.append(
                subprocess.call(
                    each, cwd=repo, env=environment, stdout=stream, stderr=subprocess.STDOUT
                )
            )
            stream.flush()
            with log.open() as reader:
                reader.seek(start)
                for kind, number in _counts(reader.read()).items():
                    counts[kind] = counts.get(kind, 0) + number
    wall = time.monotonic() - started
    # A part that collected nothing (an extra -k, say) is not a failure while another part ran.
    ran = [code for code in codes if code != NO_TESTS] or codes
    exit_code = max(ran)
    summary = (
        ", ".join(f"{number} {kind}" for kind, number in counts.items()) or "no pytest summary"
    )
    verdict = "PASS" if exit_code == 0 else f"FAIL (exit {exit_code})"
    selected = "all" if selection.fallback else str(len(selection.nodes))
    fallback = "yes" if selection.fallback else "no"
    print(
        f"TEST-IMPACT {verdict} {sha}: selected {selected}, fallback {fallback}, {summary}, "
        f"pytest calls {len(codes)}, wall {wall:.0f}s (log {log})"
    )
    return exit_code


# -- the command line ------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--repo", type=Path, default=None, help="the checkout to select in (default: this one)"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    build_parser = commands.add_parser("build", help="build the map at a base commit")
    build_parser.add_argument("--base", default="HEAD")
    build_parser.add_argument("--out", type=Path)
    build_parser.add_argument("--workers", type=int, default=0, help="pytest-xdist workers")
    build_parser.add_argument(
        "pytest_args", nargs="*", help="after --: a partial run (select refuses it)"
    )
    select_parser = commands.add_parser("select", help="print the node ids a change can affect")
    select_parser.add_argument("--base", default="HEAD")
    select_parser.add_argument("--map", type=Path)
    select_parser.add_argument("--lines", help="PATH:START-END: the tests executing those lines")
    select_parser.add_argument(
        "--nodes", action="store_true", help="print node ids, not their whole test files (B-11)"
    )
    run_parser = commands.add_parser("run", help="run the selection (or the full suite)")
    run_parser.add_argument("--base", required=True)
    run_parser.add_argument("--map", type=Path)
    run_parser.add_argument("--log", type=Path)
    run_parser.add_argument(
        "--workers", type=int, default=0, help="pytest-xdist workers (XDIST_SERIAL runs serially)"
    )
    run_parser.add_argument("pytest_args", nargs="*", help="after --: extra pytest arguments")
    args = parser.parse_args(argv)
    if args.command == "build":
        return build(args.base, args.out, args.workers, args.pytest_args)
    if args.command == "run":
        return run(args.base, args.map, args.log, args.pytest_args, args.repo or ROOT, args.workers)
    if args.lines:
        selection = select_lines(args.lines, args.base, args.map, args.repo or ROOT)
    else:
        selection = select(args.base, args.map, args.repo or ROOT)
        if not args.nodes:
            selection = selection.whole_files()
    if selection.fallback is not None:
        print(f"full suite: {selection.fallback}", file=sys.stderr)
        return EXIT_FULL
    for node in sorted(selection.nodes):
        print(node)
    print(f"selected {len(selection.nodes)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
