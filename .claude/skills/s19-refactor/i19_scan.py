"""ADR 0076 I-19 re-export inventory: every module-level name in `src/openflowsheet/**` bound by an
import that S17 or S19 added, and every file that takes such a name through that module.

A re-export is a module-level name bound by an import (any depth of if/try/with at module level,
TYPE_CHECKING included) rather than defined there. It is added by S17 or S19 when the module did not
bind the name by import at the S17 base (`--base`, default 1fd6826b; a module absent there counts as
added), or when S17/S19 added its re-export marker (an `X as X` alias or an `__all__` entry). An importer through the old path is a file in src, tests, scripts, benchmarks or examples
that takes the name from the re-exporting module: a from-import at any depth (relative resolved),
`m.N` with `m` bound to the module, a call `f(m, "N", ...)` (setattr, monkeypatch, patch.object,
getattr), a dotted string "openflowsheet.<module>.N", or a factory reference
`{"module": "...", "attribute": "N"}`.

Classes of an added re-export:
  w5            an importer is a frozen M9 module, a registry-hashed file (in a built-in
                descriptor's implementation set: frozen M9 plus assessment/cost, lca) or a
                factory reference, the form of the registry table (scripts/registry_builtin.py and the
                test that mirrors it; ADR 0076 FQ-A; W5 retargets them)
  retarget      importers through the old path outside the exceptions: retarget, then remove
  remove        no importer left, but the module marks it as a re-export (`X as X`, `__all__`, noqa
                F401) or does not use it: remove the binding
  own-use       no importer and no marker, the module reads it: a plain import, nothing to do
A patch (setattr, assignment, dotted string) of a name the module itself reads is a live patch point,
listed but not counted as an importer.
Exempt (ADR 0076 I-8): `assessment.sizing`'s `__all__` names that sizing.core defines.

    python3 .claude/skills/s19-refactor/i19_scan.py [--base REV] [--rows] [--json PATH] [--moved]

Prints one summary line, then (`--rows`) one line per actionable re-export and its importers.
`--moved` (needs cce-code-health, run it with .venv-codehealth/bin/python) also re-runs the tool's
`old_path_importers` (ec5aaea) for every `renamed`/`retargeted` entry of `.codehealth/interface/*.toml`
over the whole tree, exempting only the old module (R-W4-9a note 3). Standard library otherwise.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import tomllib
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PKG = "src/openflowsheet/"
SCAN_DIRS = ("src", "tests", "scripts", "benchmarks", "examples")
S19_BASE = "d90b498f"  # S19's CB: a commit at or before it is S17's
BUILTIN = "src/openflowsheet/registry/builtin"  # descriptors whose implementation sets registry_sha256 hashes
EXEMPT_INIT = "openflowsheet.assessment.sizing"
PATCH_KINDS = ("setattr", "assign", "string")
DOTTED = re.compile(r"^openflowsheet(\.[A-Za-z_]\w*)+$")


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def modname(path: str) -> tuple[str, bool] | None:
    if not path.startswith("src/") or not path.endswith(".py"):
        return None
    parts = path[4:-3].split("/")
    pkg = parts[-1] == "__init__"
    if pkg:
        parts = parts[:-1]
    return (".".join(parts), pkg) if all(p.isidentifier() for p in parts) else None


def resolve(node: ast.ImportFrom, path: str) -> str | None:
    if not node.level:
        return node.module
    m = modname(path)
    if m is None:
        return None
    dotted, is_pkg = m
    pkg = dotted.split(".") if is_pkg else dotted.split(".")[:-1]
    pkg = pkg[: len(pkg) - (node.level - 1)]
    return ".".join(pkg + (node.module.split(".") if node.module else []))


def _type_checking(test: ast.expr) -> bool:
    return ast.unparse(test) in ("TYPE_CHECKING", "typing.TYPE_CHECKING")


def _flat(body: list, tc: bool = False):
    """Module-level statements, descending into if/try/with/for/while but not def/class."""
    for s in body:
        yield s, tc
        if isinstance(s, ast.If):
            yield from _flat(s.body, tc or _type_checking(s.test))
            yield from _flat(s.orelse, tc)
        elif isinstance(s, (ast.Try, getattr(ast, "TryStar", ast.Try))):
            for b in (s.body, s.orelse, s.finalbody, *[h.body for h in s.handlers]):
                yield from _flat(b, tc)
        elif isinstance(s, (ast.With, ast.For, ast.While)):
            yield from _flat(s.body, tc)
            yield from _flat(getattr(s, "orelse", []), tc)


def _names(t: ast.expr) -> list[str]:
    if isinstance(t, ast.Name):
        return [t.id]
    if isinstance(t, (ast.Tuple, ast.List)):
        return [n for e in t.elts for n in _names(e)]
    if isinstance(t, ast.Starred):
        return _names(t.value)
    return []


class Module:
    """Module-level definitions and import bindings of one source file."""

    def __init__(self, path: str, text: str) -> None:
        self.path, self.text = path, text
        self.tree = ast.parse(text)
        self.defined: set[str] = set()
        self.bound: dict[str, dict] = {}  # name -> {src, name, line, alias, tc}
        self.all: list[str] = []
        lines = text.splitlines()
        for s, tc in _flat(self.tree.body):
            if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                self.defined.add(s.name)
            elif isinstance(s, ast.Assign):
                for t in s.targets:
                    self.defined.update(_names(t))
                if any(isinstance(t, ast.Name) and t.id == "__all__" for t in s.targets):
                    try:
                        self.all = [str(v) for v in ast.literal_eval(s.value)]
                    except ValueError:
                        pass
            elif isinstance(s, getattr(ast, "TypeAlias", ())):
                self.defined.add(s.name.id)
            elif isinstance(s, (ast.AnnAssign, ast.AugAssign)):
                self.defined.update(_names(s.target))
            elif isinstance(s, ast.For):
                self.defined.update(_names(s.target))
            elif isinstance(s, ast.With):
                for it in s.items:
                    if it.optional_vars is not None:
                        self.defined.update(_names(it.optional_vars))
            elif isinstance(s, ast.ImportFrom):
                src = resolve(s, path)
                for a in s.names:
                    if a.name == "*":
                        continue
                    noqa = (
                        "noqa: F401" in lines[s.end_lineno - 1]
                        or "noqa: F401" in lines[s.lineno - 1]
                    )
                    self.bound[a.asname or a.name] = {
                        "src": src,
                        "name": a.name,
                        "line": s.lineno,
                        "tc": tc,
                        "alias": a.asname == a.name,
                        "noqa": noqa,
                    }
            elif isinstance(s, ast.Import):
                for a in s.names:
                    key = a.asname or a.name.split(".")[0]
                    self.bound[key] = {
                        "src": None,
                        "name": a.name if a.asname else key,
                        "line": s.lineno,
                        "tc": tc,
                        "alias": a.asname == a.name,
                        "noqa": False,
                        "module": True,
                    }
        for n in self.defined:
            self.bound.pop(n, None)
        self._used: set[str] | None = None

    def uses(self, name: str) -> bool:
        if self._used is None:
            used = {n.id for n in ast.walk(self.tree) if isinstance(n, ast.Name)}
            for n in ast.walk(self.tree):  # string annotations
                if (
                    isinstance(n, ast.Constant)
                    and isinstance(n.value, str)
                    and n.value not in self.all
                ):
                    used.update(re.findall(r"[A-Za-z_]\w*", n.value))
            self._used = used
        return name in self._used


def load(rev: str | None) -> dict[str, Module]:
    if rev is None:
        files = {
            str(p.relative_to(ROOT)): p.read_text(encoding="utf-8")
            for p in (ROOT / PKG).rglob("*.py")
        }
    else:
        paths = [
            p
            for p in git("ls-tree", "-r", "--name-only", rev, "--", PKG).split()
            if p.endswith(".py")
        ]
        out = subprocess.run(
            ["git", "cat-file", "--batch"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            input="".join(f"{rev}:{p}\n" for p in paths).encode(),
        )
        files, buf = {}, out.stdout
        for p in paths:
            head, buf = buf.split(b"\n", 1)
            size = int(head.split()[2])
            files[p], buf = buf[:size].decode(), buf[size + 1 :]
    mods = {}
    for p, t in files.items():
        m = modname(p)
        if m:
            mods[m[0]] = Module(p, t)
    return mods


def home(mods: dict[str, Module], mod: str, name: str, depth: int = 0) -> str:
    m = mods.get(mod)
    if m is None or depth > 20:
        return f"{mod}.{name}"
    if name in m.defined:
        return f"{mod}.{name}"
    b = m.bound.get(name)
    if b is None:
        return f"{mod}.{name}" if f"{mod}.{name}" in mods else f"{mod}.{name}?"
    if b.get("module"):
        return b["name"]
    full = f"{b['src']}.{b['name']}"
    if full in mods or b["src"] not in mods:
        return full
    return home(mods, b["src"], b["name"], depth + 1)


def importers(mods: dict[str, Module]) -> tuple[dict, list]:
    """(mod, name) -> [(file, line, kind)] for names bound by import in mod; plus unbound takes."""
    hits: dict[tuple[str, str], set] = defaultdict(set)
    unbound: list = []

    def take(mod: str, name: str, f: str, line: int, kind: str) -> None:
        m = mods.get(mod)
        if m is None or name == "*" or f"{mod}.{name}" in mods or m.path == f:
            return
        if name in m.bound:
            hits[(mod, name)].add((f, line, kind))
        elif name not in m.defined and kind != "string" and not name.startswith("__"):
            unbound.append((f, line, kind, f"{mod}.{name}"))

    def split(dotted: str) -> tuple[str, str] | None:
        parts = dotted.split(".")
        for i in range(len(parts) - 1, 0, -1):
            if ".".join(parts[:i]) in mods:
                return ".".join(parts[:i]), parts[i]
        return None

    for d in SCAN_DIRS:
        for p in sorted((ROOT / d).rglob("*.py")):
            f = str(p.relative_to(ROOT))
            text = p.read_text(encoding="utf-8")
            if "openflowsheet" not in text and not f.startswith("src/"):
                continue
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            alias: dict[str, str] = {}
            consts: dict[str, str] = {}
            for s in tree.body:
                if (
                    isinstance(s, (ast.Assign, ast.AnnAssign))
                    and isinstance(s.value, ast.Constant)
                    and isinstance(s.value.value, str)
                ):
                    for t in s.targets if isinstance(s, ast.Assign) else [s.target]:
                        if isinstance(t, ast.Name):
                            consts[t.id] = s.value.value
            for n in ast.walk(tree):
                if isinstance(n, ast.ImportFrom):
                    src = resolve(n, f)
                    for a in n.names:
                        if src and f"{src}.{a.name}" in mods:
                            alias[a.asname or a.name] = f"{src}.{a.name}"
                        elif src:
                            take(src, a.name, f, n.lineno, "from")
                elif isinstance(n, ast.Import):
                    for a in n.names:
                        if a.asname:
                            alias[a.asname] = a.name
                        else:
                            alias.setdefault(a.name.split(".")[0], a.name.split(".")[0])

            def dotted_of(e: ast.expr) -> str | None:
                chain = []
                while isinstance(e, ast.Attribute):
                    chain.append(e.attr)
                    e = e.value
                if isinstance(e, ast.Name) and e.id in alias:
                    return ".".join([alias[e.id], *reversed(chain)])
                return None

            for n in ast.walk(tree):
                if isinstance(n, ast.Attribute):
                    d_ = dotted_of(n)
                    if d_ and d_ not in mods:
                        s_ = split(d_)
                        if s_ and d_ == f"{s_[0]}.{s_[1]}":
                            take(
                                *s_,
                                f,
                                n.lineno,
                                "attr" if isinstance(n.ctx, ast.Load) else "assign",
                            )
                elif (
                    isinstance(n, ast.Call)
                    and len(n.args) >= 2
                    and isinstance(n.args[1], ast.Constant)
                    and isinstance(n.args[1].value, str)
                ):
                    d_ = dotted_of(n.args[0])
                    if d_ in mods:
                        take(d_, n.args[1].value, f, n.lineno, "setattr")
                elif (
                    isinstance(n, ast.Constant)
                    and isinstance(n.value, str)
                    and DOTTED.match(n.value)
                ):
                    s_ = split(n.value)
                    if s_:
                        take(*s_, f, n.lineno, "string")
                elif isinstance(n, ast.Dict):
                    kv = {
                        k.value: v for k, v in zip(n.keys, n.values) if isinstance(k, ast.Constant)
                    }
                    if "module" in kv and isinstance(kv.get("attribute"), ast.Constant):
                        mv = kv["module"]
                        mod = (
                            mv.value
                            if isinstance(mv, ast.Constant)
                            else consts.get(getattr(mv, "id", ""))
                        )
                        if isinstance(mod, str):
                            take(mod, kv["attribute"].value, f, n.lineno, "factory")
    return hits, unbound


def added_in(path: str, name: str, base: str) -> str:
    log = (
        git("log", "--format=%h", f"-S{name}", f"{base}..HEAD", "--", path).split()
        or git("log", "--format=%h", f"-G\\b{name}\\b", f"{base}..HEAD", "--", path).split()
        or git("log", "--format=%h", "--diff-filter=A", f"{base}..HEAD", "--", path).split()
    )
    if not log:
        return "?"
    c = log[-1]
    s17 = (
        subprocess.run(["git", "merge-base", "--is-ancestor", c, S19_BASE], cwd=ROOT).returncode
        == 0
    )
    return f"{'S17' if s17 else 'S19'} {c}"


def moved_scan() -> list[str]:
    from cce_code_health import interface  # noqa: PLC0415

    files = {}
    for d in SCAN_DIRS:
        for p in (ROOT / d).rglob("*.py"):
            files[str(p.relative_to(ROOT))] = p.read_text(encoding="utf-8")
    out = []
    for plan_path in sorted((ROOT / ".codehealth/interface").glob("*.toml")):
        plan = tomllib.loads(plan_path.read_text(encoding="utf-8"))
        old = {po.split(":")[0] for po, _ in interface.moved_names(plan)}
        for line in interface.old_path_importers(plan, files, ["src", "."], old):
            out.append(f"{plan_path.stem}: {line}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="1fd6826b")
    ap.add_argument("--rows", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--moved", action="store_true")
    a = ap.parse_args()
    head, base = load(None), load(a.base)
    frozen = set(
        subprocess.run(
            [sys.executable, "scripts/codehealth_frozen.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
    )
    hashed = {
        "src/" + p
        for f in sorted((ROOT / BUILTIN).glob("*.json"))
        for p in re.findall(r'"(openflowsheet/[^"]+\.py)"', f.read_text(encoding="utf-8"))
    }
    hits, unbound = importers(head)
    rows = []
    counts: dict[str, int] = defaultdict(int)
    for mod, m in sorted(head.items()):
        for name, b in sorted(m.bound.items()):
            bm = base.get(mod)
            if (
                bm is not None
                and name in bm.bound
                and not (b["alias"] and not bm.bound[name]["alias"])
                and not (name in m.all and name not in bm.all)
            ):
                continue  # bound by import at the S17 base, no marker added since: not S17/S19's
            if b.get("module") or (b["src"] or "").split(".")[0] == "__future__":
                continue
            allhits = sorted(hits.get((mod, name), ()))
            # a patch (setattr, assignment, dotted string) of a name the module reads is a live patch point
            live = [i for i in allhits if i[2] in PATCH_KINDS and m.uses(name)]
            imp = [i for i in allhits if i not in live]
            exc = [i for i in imp if i[0] in frozen or i[0] in hashed or i[2] == "factory"]
            marker = [
                k
                for k, v in (("alias", b["alias"]), ("__all__", name in m.all), ("noqa", b["noqa"]))
                if v
            ]
            if (
                mod == EXEMPT_INIT
                and name in m.all
                and home(head, mod, name).startswith(EXEMPT_INIT + ".core.")
            ):
                cls = "exempt"
            elif exc:
                cls = "w5"
            elif imp:
                cls = "retarget"
            elif marker or not m.uses(name):
                cls = "remove"
            else:
                cls = "own-use"
            counts[cls] += 1
            if cls != "own-use":
                rows.append(
                    {
                        "module": mod,
                        "name": name,
                        "line": b["line"],
                        "home": home(head, mod, name),
                        "marker": marker,
                        "used": m.uses(name),
                        "class": cls,
                        "importers": [f"{f}:{ln} {k}" for f, ln, k in imp],
                        "live_patches": [f"{f}:{ln} {k}" for f, ln, k in live],
                        "exceptions": [f"{f}:{ln}" for f, ln, _ in exc],
                        "path": m.path,
                    }
                )
    left = sum(len(r["importers"]) for r in rows if r["class"] in ("retarget", "w5"))
    left_exc = sum(len(r["exceptions"]) for r in rows if r["class"] == "w5")
    print(
        f"I19-SCAN re-exports added since {a.base}: {sum(counts.values())} "
        f"({', '.join(f'{k} {v}' for k, v in sorted(counts.items()))}); old-path importers {left} "
        f"(W5 exception users {left_exc}, others {left - left_exc}); unbound takes {len(unbound)}"
    )
    if a.rows:
        for r in rows:
            if r["class"] in ("retarget", "remove", "w5"):
                r["added"] = added_in(r["path"], r["name"], a.base)
            print(
                f"{r['class']:8} {r['module']}.{r['name']} (:{r['line']}; home {r['home']}; "
                f"{'/'.join(r['marker']) or '-'}; {'used' if r['used'] else 'unused'}; {r.get('added', '')})"
            )
            for i in r["importers"]:
                print(f"           <- {i}")
            for i in r["live_patches"]:
                print(f"           live patch {i}")
        for u in unbound:
            print("unbound  ", *u)
    if a.moved:
        mv = moved_scan()
        print(f"MOVED-SCAN old-path importers of renamed/retargeted names: {len(mv)}")
        for line in mv:
            print("  ", line)
    if a.json:
        Path(a.json).write_text(json.dumps({"rows": rows, "unbound": unbound}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
