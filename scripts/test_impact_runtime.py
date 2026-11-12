"""S16: the in-process half of `scripts/test_impact.py build` (docs/test-impact.md).

`build` copies this file into the test-map venv's site-packages as `ofs_testmap_runtime.py`, next to
`ofs_testmap.pth` (one line: `import ofs_testmap_runtime`), so every Python process of that venv
imports it at start-up. It stays inert unless `ofs_testmap_active.json` sits next to it (written by
`build` for the length of one run) and the process descends from the build. Then it:

- starts coverage (line data of the source directories the pointer names) in this process, so a
  CLI subprocess a test spawns is measured too; a pytest process switches the dynamic context per
  test, a subprocess carries the context of the ancestor that spawned it as its static context;
- records every repository file the process opens for reading (a `sys.addaudithook` on "open"),
  keyed by the same context, except imports and pytest's own reads (assertion rewriting, conftest);
- as a pytest plugin (`-p ofs_testmap_runtime`), names the context: the test's node id while a test
  runs; `fixture:<baseid>::<name>` while a fixture of class, module, package or session scope is
  set up (its work is shared by every test that uses it, so the map attributes it to all of them);
  the empty context at collection and outside tests. It also clears every `functools` cache of the
  repository's modules before each test, so a cached function's lines count for each test that
  calls it, not only for the first.

Nothing here runs under the main venv or in CI; the repository's code is unchanged by it.
"""

from __future__ import annotations

import atexit
import json
import os
import sys
import sysconfig
from pathlib import Path
from typing import Any

POINTER = Path(__file__).with_name("ofs_testmap_active.json")
CONTEXT_ENV = "OFS_TESTMAP_CONTEXT"
COLLECTION = ""

_run: Path | None = None
_root = ""
_context = COLLECTION
_opens: set[tuple[str, str]] = set()
_coverage: Any = None
_stdlib = tuple({sysconfig.get_paths()["stdlib"], sysconfig.get_paths()["platstdlib"], "<frozen"})
_internal = ("/_pytest/", "/pluggy/", "/coverage/", "/xdist/", "/execnet/", "ofs_testmap_runtime")


def _ancestors(pid: int) -> list[int]:
    """`pid`'s parent chain (Linux /proc), nearest first."""
    chain: list[int] = []
    while pid > 1 and len(chain) < 64:
        try:
            stat = Path(f"/proc/{pid}/stat").read_text()
        except OSError:
            break
        pid = int(stat.rsplit(")", 1)[1].split()[1])
        chain.append(pid)
    return chain


def _inherited_context(ancestors: list[int]) -> str:
    """The context of the nearest ancestor that names one; the environment's if none does."""
    assert _run is not None
    for pid in ancestors:
        try:
            return (_run / "ctx" / str(pid)).read_text()
        except OSError:
            continue
    return os.environ.get(CONTEXT_ENV, COLLECTION)


def _audit(event: str, args: tuple[Any, ...]) -> None:
    if event != "open":
        return
    try:
        _record_open(*args)
    except Exception:  # an audit hook must never break the open it observes
        pass


def _record_open(path: Any, mode: Any, flags: int) -> None:
    if path is None or isinstance(path, int):
        return
    if isinstance(mode, str):
        if "r" not in mode and "+" not in mode:
            return
    elif flags & os.O_ACCMODE == os.O_WRONLY or flags & os.O_DIRECTORY:
        return
    name = os.fsdecode(path)
    if not os.path.isabs(name):
        name = os.path.join(os.getcwd(), name)
    name = os.path.normpath(name)
    if not name.startswith(_root) or not os.path.isfile(name):
        return  # outside the repository, or relative to a directory descriptor (`dir_fd`)
    relative = name[len(_root) :]
    if relative.startswith(".git/") or relative == ".git":
        return
    frame = sys._getframe(1)
    while frame is not None and frame.f_code.co_filename.startswith(_stdlib):
        if frame.f_code.co_filename.startswith("<frozen importlib"):
            return  # an import: coverage sees the module's lines
        frame = frame.f_back
    if frame is not None and any(part in frame.f_code.co_filename for part in _internal):
        return
    _opens.add((_context, relative))


def _finish() -> None:
    assert _run is not None
    if _coverage is not None:
        _coverage.stop()
        _coverage.save()
    if _opens:
        target = _run / "opens" / f"{os.getpid()}-{os.urandom(4).hex()}.json"
        target.write_text(json.dumps(sorted(_opens)))


def _boot() -> None:
    global _run, _root, _context, _coverage
    try:
        config = json.loads(POINTER.read_text())
    except OSError:
        return
    ancestors = _ancestors(os.getpid())
    if config["root_pid"] not in ancestors:
        return
    _run = Path(config["run"])
    _root = config["root"].rstrip("/") + "/"
    _context = _inherited_context(ancestors)
    import coverage

    _coverage = coverage.Coverage(
        data_file=str(_run / "cov" / ".coverage"),
        data_suffix=True,
        source=config["source"],
        context=_context or None,
        config_file=False,
        branch=False,
    )
    _coverage.set_option("run:sigterm", True)
    _coverage.start()
    sys.addaudithook(_audit)
    atexit.register(_finish)


_boot()


# -- the pytest plugin (`-p ofs_testmap_runtime`; only the pytest processes of a build load it) --


#: Packages imported whole at the end of collection, so their import-time work runs in the
#: collection context, not in whichever test happens to import a module first.
EAGER = ("openflowsheet", "benchmarks")

_stack: list[str] = []
_PACKAGES = ("openflowsheet", "benchmarks")
MappingProxy = type(type.__dict__)
_caches: dict[int, Any] = {}
_modules_seen = 0
_outcomes: dict[str, str] = {}


def _switch(context: str) -> None:
    global _context
    assert _run is not None
    _context = context
    os.environ[CONTEXT_ENV] = context
    staging = _run / "ctx" / f".{os.getpid()}"
    staging.write_text(context)
    os.replace(staging, _run / "ctx" / str(os.getpid()))
    if _coverage is not None:
        _coverage.switch_context(context)


def _clear_caches() -> None:
    """Clear every functools cache defined in a module or class of the repository."""
    global _modules_seen
    if len(sys.modules) != _modules_seen:
        _modules_seen = len(sys.modules)
        for module in list(sys.modules.values()):
            if not (getattr(module, "__file__", None) or "").startswith(_root):
                continue
            for value in list(vars(module).values()):
                candidates = [value]
                if isinstance(value, type) and value.__module__ == module.__name__:
                    for member in vars(value).values():
                        candidates.append(getattr(member, "__func__", member))
                        candidates.append(getattr(member, "fget", None))
                for candidate in candidates:
                    if callable(getattr(candidate, "cache_clear", None)):
                        _caches[id(candidate)] = candidate
    for cached in _caches.values():
        cached.cache_clear()
    _restore()


_MISSING = object()
#: (namespace, its values, [(container or instance, its shallow contents)]) per repository module
#: and class, taken at the end of collection.
_snapshot: list[tuple[dict[str, Any], dict[str, Any], list[tuple[Any, Any]]]] = []
_snapshot_names: set[str] = set()


def _state(value: Any) -> Any:
    """A shallow copy of a mutable value's contents, or None for one this does not restore."""
    kind = type(value)
    if kind in (dict, list, set):
        return value.copy()
    if isinstance(value, type) or not (kind.__module__ or "").startswith(_PACKAGES):
        return None
    try:
        return dict(vars(value))
    except TypeError:  # __slots__: no instance dictionary
        return None


def _take_snapshot() -> None:
    """Record every repository module's globals (and its classes' attributes) after collection."""
    for name, module in list(sys.modules.items()):
        if not (getattr(module, "__file__", None) or "").startswith(_root):
            continue
        _snapshot_names.add(name)
        namespaces = [vars(module)]
        namespaces += [
            vars(value)
            for value in vars(module).values()
            if isinstance(value, type) and value.__module__ == module.__name__
        ]
        for namespace in namespaces:
            values = dict(namespace)
            contents = [(value, state) for value in values.values() if (state := _state(value))]
            _snapshot.append((namespace, values, contents))


def _same(current: Any, saved: Any) -> bool:
    if len(current) != len(saved):
        return False
    if isinstance(saved, list):
        return all(a is b for a, b in zip(current, saved, strict=True))
    if isinstance(saved, set):
        return current == saved
    return all(current.get(key, _MISSING) is value for key, value in saved.items())


def _restore() -> None:
    """Put the module state back as collection left it: a test starts as in a fresh process.

    A repository module first imported by an earlier test is dropped from `sys.modules`, so a
    test that needs it imports it afresh."""
    for name, module in list(sys.modules.items()):
        if name not in _snapshot_names and (getattr(module, "__file__", None) or "").startswith(
            _root
        ):
            del sys.modules[name]
    for namespace, values, contents in _snapshot:
        for key, value in values.items():
            if namespace.get(key, _MISSING) is not value and not isinstance(
                namespace, MappingProxy
            ):
                namespace[key] = value
        for owner, saved in contents:
            current = owner if isinstance(saved, type(owner)) else vars(owner)
            if _same(current, saved):
                continue
            if isinstance(current, list):
                current[:] = saved
            else:
                current.clear()
                current.update(saved)


def _fixture_key(fixturedef: Any) -> str:
    return f"fixture:{fixturedef.baseid}::{fixturedef.argname}"


def pytest_configure(config: Any) -> None:
    if _run is None:
        raise RuntimeError("ofs_testmap_runtime: no test-map build is active in this process")


def pytest_collection_finish(session: Any) -> None:
    """Import every module of `EAGER` now, in the collection context; failures are ignored."""
    import importlib
    import pkgutil

    for package_name in EAGER:
        try:
            package = importlib.import_module(package_name)
        except Exception:
            continue
        for info in pkgutil.walk_packages(package.__path__, f"{package_name}.", lambda _: None):
            try:
                importlib.import_module(info.name)
            except Exception:
                continue
    _take_snapshot()


def pytest_runtest_logreport(report: Any) -> None:
    if report.failed:
        _outcomes[report.nodeid] = "failed"
    elif report.when == "call" or (report.when == "setup" and report.skipped):
        _outcomes.setdefault(report.nodeid, report.outcome)


def _wrapper(function: Any) -> Any:
    import pytest

    return pytest.hookimpl(wrapper=True)(function)


@_wrapper
def pytest_runtest_protocol(item: Any, nextitem: Any) -> Any:
    assert _run is not None
    fixtures = sorted(
        {
            _fixture_key(definition)
            for name in item.fixturenames
            for definition in item._fixtureinfo.name2fixturedefs.get(name, ())
            if definition.scope != "function"
        }
    )
    _clear_caches()
    _switch(item.nodeid)
    try:
        return (yield)
    finally:
        _switch(COLLECTION)
        record = {
            "nodeid": item.nodeid,
            "path": item.nodeid.split("::", 1)[0],
            "fixtures": fixtures,
            "outcome": _outcomes.pop(item.nodeid, "unknown"),
        }
        with (_run / "tests" / f"{os.getpid()}.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record) + "\n")


@_wrapper
def pytest_fixture_setup(fixturedef: Any, request: Any) -> Any:
    if fixturedef.scope == "function":
        return (yield)
    _stack.append(_context)
    _switch(_fixture_key(fixturedef))
    try:
        return (yield)
    finally:
        _switch(_stack.pop())
