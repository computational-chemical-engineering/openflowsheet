"""Flag test patches of `module.name` where `module` only imports/re-exports `name` and never uses it."""
import ast, pathlib, sys, collections
root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
src = root / "src"
def modpath(mod):
    p = src / pathlib.Path(*mod.split("."))
    for c in (p.with_suffix(".py"), p / "__init__.py"):
        if c.is_file(): return c
def usage(mod, name):
    p = modpath(mod)
    if not p: return None
    t = ast.parse(p.read_text())
    defined = imported = False; uses = 0
    for n in t.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == name: defined = True
        elif isinstance(n, (ast.Assign, ast.AnnAssign)):
            tg = n.targets if isinstance(n, ast.Assign) else [n.target]
            if any(isinstance(x, ast.Name) and x.id == name for x in tg): defined = True
        elif isinstance(n, (ast.Import, ast.ImportFrom)) and any((a.asname or a.name.split('.')[0]) == name for a in n.names): imported = True
    for n in ast.walk(t):
        if isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Load): uses += 1
    return defined, imported, uses
flags = []; total = 0
for tf in sorted((root / "tests").rglob("*.py")):
    try: t = ast.parse(tf.read_text())
    except SyntaxError: continue
    alias = {}
    for n in ast.walk(t):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name.startswith("openflowsheet"): alias[a.asname or a.name] = a.name
        elif isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("openflowsheet"):
            for a in n.names:
                full = n.module + "." + a.name
                if modpath(full): alias[a.asname or a.name] = full
    for n in ast.walk(t):
        if not isinstance(n, ast.Call): continue
        f = n.func; fname = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
        target = None
        if fname in ("setattr", "object") and len(n.args) >= 2 and isinstance(n.args[1], ast.Constant) and isinstance(n.args[1].value, str):
            o = n.args[0]; dotted = ast.unparse(o)
            mod = alias.get(dotted) or (dotted if dotted.startswith("openflowsheet") else None)
            if mod: target = (mod, n.args[1].value)
        elif fname in ("setattr", "patch") and n.args and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str) and n.args[0].value.startswith("openflowsheet."):
            mod, _, name = n.args[0].value.rpartition("."); target = (mod, name)
        if not target: continue
        total += 1
        u = usage(*target)
        if u is None: continue
        defined, imported, uses = u
        if not defined and uses == 0:
            flags.append(f"{tf.relative_to(root)}:{n.lineno} patches {target[0]}.{target[1]} (imported={imported}, used 0 times there)")
print(f"{total} module-attribute patches; {len(flags)} where the module neither defines nor uses the name:")
print("\n".join(flags))
