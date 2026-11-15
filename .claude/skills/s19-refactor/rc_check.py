# ruff: noqa: E501
"""RC checks for a `closures-to-class` step (S19 G1 plan section 3; playbook rule 6; R-W3-G1N-1).

usage: rc_check.py BASE_FILE HEAD_FILE FUNC CLASS RUNVAR [--rename OLD=NEW ...] [--state A,B,...]
                   [--count PAT=N | --count BASEPAT->HEADPAT=N ...]

  BASE_FILE, HEAD_FILE  the module at the last accepted commit and at the step (`git show <sha>:<path> > f`)
  FUNC, CLASS, RUNVAR   the function, its run class and the name it binds the instance to (`run`)
  --rename              a closure renamed as a method (RC3's one declared rename), e.g. record=close
  --state               the state fields (RC2 b); every other field is frame and is never assigned
                        after construction. Default: the fields assigned through `self.`/RUNVAR.
  --count               an RC5 site count: lines containing PAT over FUNC plus CLASS (when present),
                        at base and at head, `def` lines included; equal at both and to N. A
                        pattern `re:<regex>` counts lines matching the regex instead.

Checks (each prints its findings; the last line is `RESULT OK` or `RESULT CHECK`):
  (i)   every closure of FUNC at base equals the method of CLASS at head, by `ast.dump`, after
        removing `self.` prefixes, `nonlocal` statements and the `self` parameter (body, arguments
        and return annotation). Skipped when FUNC has no closures at base (a later step). The
        function itself (closures removed, RUNVAR. prefixes removed) is diffed by statement and
        the differing statements are listed for reading: the constructor call always differs.
  (ii)  below the constructor call `RUNVAR = CLASS(...)`, no bare read of a state field (a stale
        local read; frame fields never change, so a local alias of one is allowed, RC6); in every
        method, no bare read of a field name that is neither a parameter nor a local of that method
        (a global read).
  (iii) in every method, no `self.<name>` where <name> is a parameter or a local of that method
        (`self.values` for the parameter `values` of `finish`).
  (iv)  below the constructor call, no bare store of a field name in FUNC; in every method, no
        bare store of a field name (a local shadowing a field: a missed `self.`).
  RC2a  no frame field is assigned through `self.` or RUNVAR. anywhere.
  RC5   the --count site counts.
"""

import argparse
import ast
import copy
import difflib
import re


class _Strip(ast.NodeTransformer):
    """Replace `<prefix>.<attr>` by the bare name `<attr>`, recording each hit."""

    def __init__(self, prefixes: set[str]) -> None:
        self.prefixes = prefixes
        self.hits: list[tuple[str, int, str]] = []

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        self.generic_visit(node)
        if isinstance(node.value, ast.Name) and node.value.id in self.prefixes:
            self.hits.append((node.attr, node.lineno, type(node.ctx).__name__))
            return ast.copy_location(ast.Name(id=node.attr, ctx=node.ctx), node)
        return node


def _rename(nodes: list[ast.AST], rename: dict[str, str]) -> None:
    for node in nodes:
        for w in ast.walk(node):
            if isinstance(w, ast.Name) and w.id in rename:
                w.id = rename[w.id]


def _top(module: ast.Module, kind: type, name: str) -> ast.AST | None:
    return next((n for n in module.body if isinstance(n, kind) and n.name == name), None)


def _params(fn: ast.FunctionDef) -> set[str]:
    a = fn.args
    names = {x.arg for x in a.posonlyargs + a.args + a.kwonlyargs}
    names |= {x.arg for x in (a.vararg, a.kwarg) if x is not None}
    return names


def _locals(fn: ast.FunctionDef) -> set[str]:
    out = set()
    for w in ast.walk(fn):
        if isinstance(w, ast.Name) and isinstance(w.ctx, ast.Store):
            out.add(w.id)
        elif isinstance(w, ast.ExceptHandler) and w.name:
            out.add(w.name)
    return out


def _segment_lines(src: list[str], nodes: list[ast.AST]) -> list[str]:
    out: list[str] = []
    for n in nodes:
        start = min([n.lineno] + [d.lineno for d in getattr(n, "decorator_list", [])])
        out += src[start - 1 : n.end_lineno]
    return out


def _count(src: str, module: ast.Module, func: str, cls: str, pat: str) -> int:
    nodes = [n for n in (_top(module, ast.FunctionDef, func), _top(module, ast.ClassDef, cls)) if n]
    lines = _segment_lines(src.splitlines(), nodes)
    if pat.startswith("re:"):
        return sum(re.search(pat[3:], line) is not None for line in lines)
    return sum(pat in line for line in lines)


def main() -> None:
    ap = argparse.ArgumentParser(usage=__doc__.split("\n\n")[1])
    ap.add_argument("base_file")
    ap.add_argument("head_file")
    ap.add_argument("func")
    ap.add_argument("cls")
    ap.add_argument("runvar")
    ap.add_argument("--rename", action="append", default=[])
    ap.add_argument("--state", default="")
    ap.add_argument("--count", action="append", default=[])
    o = ap.parse_args()
    rename = dict(r.split("=", 1) for r in o.rename)
    bsrc, hsrc = open(o.base_file).read(), open(o.head_file).read()
    bm, hm = ast.parse(bsrc), ast.parse(hsrc)
    bf = _top(bm, ast.FunctionDef, o.func)
    hf = _top(hm, ast.FunctionDef, o.func)
    hc = _top(hm, ast.ClassDef, o.cls)
    assert bf is not None and hf is not None and hc is not None, "FUNC or CLASS not found"
    fields = {n.target.id for n in hc.body if isinstance(n, ast.AnnAssign)}
    methods = {n.name: n for n in hc.body if isinstance(n, ast.FunctionDef)}
    ok = True

    # Stores through self. (all methods) and RUNVAR. (FUNC).
    stored: set[str] = set()
    for m in methods.values():
        for w in ast.walk(m):
            if (
                isinstance(w, ast.Attribute)
                and isinstance(w.ctx, ast.Store)
                and isinstance(w.value, ast.Name)
                and w.value.id == "self"
            ):
                stored.add(w.attr)
    for w in ast.walk(hf):
        if (
            isinstance(w, ast.Attribute)
            and isinstance(w.ctx, ast.Store)
            and isinstance(w.value, ast.Name)
            and w.value.id == o.runvar
        ):
            stored.add(w.attr)
    state = set(o.state.split(",")) - {""} if o.state else set(stored)
    frame = fields - state
    print(f"fields: {len(fields)}; state {sorted(state)}; frame {sorted(frame)}")
    bad = sorted(stored & frame)
    unknown = sorted(state - fields)
    print(
        f"RC2a frame fields assigned after construction: {bad or 'none'}"
        + (f"; declared state not a field: {unknown}" if unknown else "")
    )
    ok &= not bad and not unknown

    # (i)
    closures = [n for n in bf.body if isinstance(n, ast.FunctionDef)]
    if not closures:
        print("(i) n/a: FUNC has no closures at base")
    for c in closures:
        mname = rename.get(c.name, c.name)
        m = methods.get(mname)
        if m is None:
            print(f"(i) {c.name}: no method {mname}")
            ok = False
            continue
        m2 = copy.deepcopy(m)
        _Strip({"self"}).visit(m2)
        args = m2.args
        assert args.args and args.args[0].arg == "self", f"{mname}: first parameter is not self"
        args.args = args.args[1:]
        body = [n for n in copy.deepcopy(c.body) if not isinstance(n, ast.Nonlocal)]
        _rename(body, rename)
        same_body = [ast.dump(n) for n in body] == [ast.dump(n) for n in m2.body]
        same_sig = ast.dump(c.args) == ast.dump(args) and (
            (c.returns is None and m2.returns is None)
            or (
                c.returns is not None
                and m2.returns is not None
                and ast.dump(c.returns) == ast.dump(m2.returns)
            )
        )
        print(
            f"(i) {c.name} -> {mname}: body {'equal' if same_body else 'DIFFERENT'}, "
            f"signature {'equal' if same_sig else 'DIFFERENT'}"
        )
        ok &= same_body and same_sig
    if closures:
        hb = copy.deepcopy(hf.body)
        s = _Strip({o.runvar})
        hb = [s.visit(n) for n in hb]
        bb = [n for n in copy.deepcopy(bf.body) if not isinstance(n, ast.FunctionDef)]
        _rename(bb, rename)
        sm = difflib.SequenceMatcher(
            a=[ast.dump(n) for n in bb], b=[ast.dump(n) for n in hb], autojunk=False
        )
        diffs = [
            (
                op,
                [(n.lineno, n.end_lineno) for n in bb[a0:a1]],
                [(n.lineno, n.end_lineno) for n in hf.body[b0:b1]],
            )
            for op, a0, a1, b0, b1 in sm.get_opcodes()
            if op != "equal"
        ]
        print(
            f"(i) FUNC statements differing (base lines -> head lines), to read: {diffs or 'none'}"
        )

    ctor = next(
        (
            n
            for n in hf.body
            if isinstance(n, ast.Assign)
            and isinstance(n.value, ast.Call)
            and isinstance(n.value.func, ast.Name)
            and n.value.func.id == o.cls
        ),
        None,
    )
    assert ctor is not None, "no constructor call RUNVAR = CLASS(...) in FUNC"
    below = ctor.end_lineno

    # (ii)
    watched = state
    stale = sorted(
        {
            (w.id, w.lineno)
            for w in ast.walk(hf)
            if isinstance(w, ast.Name)
            and isinstance(w.ctx, ast.Load)
            and w.id in watched
            and w.lineno > below
        }
    )
    print(f"(ii) bare reads in FUNC below the constructor (line {below}): {stale or 'none'}")
    glob = []
    for name, m in methods.items():
        own = _params(m) | _locals(m)
        glob += [
            (name, w.id, w.lineno)
            for w in ast.walk(m)
            if isinstance(w, ast.Name)
            and isinstance(w.ctx, ast.Load)
            and w.id in fields
            and w.id not in own
        ]
    print(
        f"(ii) bare reads of a field name in a method, neither parameter nor local: {glob or 'none'}"
    )
    ok &= not stale and not glob

    # (iii)
    shadow = []
    for name, m in methods.items():
        own = (_params(m) - {"self"}) | _locals(m)
        shadow += [
            (name, w.attr, w.lineno)
            for w in ast.walk(m)
            if isinstance(w, ast.Attribute)
            and isinstance(w.value, ast.Name)
            and w.value.id == "self"
            and w.attr in own
        ]
    print(f"(iii) self.<name> with <name> a parameter or local of the method: {shadow or 'none'}")
    ok &= not shadow

    # (iv)
    fstores = sorted(
        {
            (w.id, w.lineno)
            for w in ast.walk(hf)
            if isinstance(w, ast.Name)
            and isinstance(w.ctx, ast.Store)
            and w.id in fields
            and w.lineno > below
        }
    )
    mstores = sorted(
        {
            (name, w.id, w.lineno)
            for name, m in methods.items()
            for w in ast.walk(m)
            if isinstance(w, ast.Name) and isinstance(w.ctx, ast.Store) and w.id in fields
        }
    )
    print(
        f"(iv) bare stores of a field name in FUNC below the constructor: {fstores or 'none'}; "
        f"in methods: {mstores or 'none'}"
    )
    ok &= not fstores and not mstores

    # RC5
    for spec in o.count:
        pats, n = spec.rsplit("=", 1)
        bpat, hpat = pats.split("->", 1) if "->" in pats else (pats, pats)
        cb = _count(bsrc, bm, o.func, o.cls, bpat)
        ch = _count(hsrc, hm, o.func, o.cls, hpat)
        good = cb == ch == int(n)
        print(
            f"RC5 {bpat!r} {cb} at base, {hpat!r} {ch} at head (plan {n}): {'OK' if good else 'MISMATCH'}"
        )
        ok &= good
    print("RESULT", "OK" if ok else "CHECK")


main()
