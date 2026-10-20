"""T08.A30's measured workload and its registered `nlp`-extra modules (M07 spec §24.1, R-478).

The workload imports every module of the package, except the `nlp` extra's: each of those must fail
to import on one of the extra's own names (MR-12 gives their closure to `docs/m03-ipopt-audit.md`
and R-450). S9.5 runs the child on a synthetic package in `tmp_path` and checks each refusal and the
passing control; S9.6 pins the registered list to `src/openflowsheet` in both directions.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "p03_binary_inventory.py"
PACKAGE = "a30synthetic"


@pytest.fixture(scope="module")
def p03() -> ModuleType:
    spec = importlib.util.spec_from_file_location("p03_binary_inventory", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _package(root: Path, modules: dict[str, str]) -> None:
    """A synthetic package `a30synthetic` under `root`, one file per `{name: source}`."""
    package = root / PACKAGE
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    for name, source in modules.items():
        (package / f"{name}.py").write_text(source, encoding="utf-8")


def _run(
    p03: ModuleType, root: Path, registered: tuple[str, ...]
) -> subprocess.CompletedProcess[str]:
    argument = p03.workload_argument(
        PACKAGE,
        tuple(f"{PACKAGE}.{name}" for name in registered),
        p03.NLP_EXTRA_IMPORTS,
        solve=False,
    )
    environment = {**os.environ, "PYTHONPATH": str(root)}
    return subprocess.run(
        [sys.executable, "-c", p03._WORKLOAD, argument],
        capture_output=True,
        text=True,
        check=False,
        cwd=root,
        env=environment,
    )


# The control and (b) need the default install, where the `nlp` extra is absent.
needs_default_install = pytest.mark.skipif(
    importlib.util.find_spec("pyomo") is not None,
    reason="pyomo is importable: this is not the default install (M07 spec §24.1)",
)


@needs_default_install
def test_s9_5_control_a_registered_module_failing_on_pyomo_is_recorded(
    p03: ModuleType, tmp_path: Path
) -> None:
    _package(tmp_path, {"plain": "VALUE = 1\n", "solver": "import pyomo.environ\n"})
    completed = _run(p03, tmp_path, ("solver",))
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout.strip().splitlines()[-1])
    assert result["nlp_extra_modules"] == {f"{PACKAGE}.solver": "pyomo"}
    assert result["modules_walked"] == 2
    assert result["modules_imported"] == 1
    assert result["solve_exit"] is None


def test_s9_5a_a_registered_module_that_imports_fails(p03: ModuleType, tmp_path: Path) -> None:
    _package(tmp_path, {"solver": "VALUE = 1\n"})
    completed = _run(p03, tmp_path, ("solver",))
    assert completed.returncode != 0
    assert "the nlp extra is importable in the A30 environment" in completed.stderr


@needs_default_install
def test_s9_5b_an_unregistered_module_not_found_fails(p03: ModuleType, tmp_path: Path) -> None:
    _package(tmp_path, {"solver": "import pyomo.environ\n"})
    completed = _run(p03, tmp_path, ())
    assert completed.returncode != 0
    assert "ModuleNotFoundError: No module named 'pyomo'" in completed.stderr


def test_s9_5c_a_registered_module_failing_outside_the_extra_fails(
    p03: ModuleType, tmp_path: Path
) -> None:
    _package(tmp_path, {"solver": "import a30_no_such_distribution\n"})
    completed = _run(p03, tmp_path, ("solver",))
    assert completed.returncode != 0
    assert "ModuleNotFoundError: No module named 'a30_no_such_distribution'" in completed.stderr


def test_s9_5d_a_registered_module_that_is_not_walked_fails(
    p03: ModuleType, tmp_path: Path
) -> None:
    _package(tmp_path, {"plain": "VALUE = 1\n"})
    completed = _run(p03, tmp_path, ("absent",))
    assert completed.returncode != 0
    assert f"registered nlp-extra module {PACKAGE}.absent is not an openflowsheet module" in (
        completed.stderr
    )


def _module_level_imports(tree: ast.Module) -> set[str]:
    """Top-level names imported where the module body runs (not inside a function)."""
    names: set[str] = set()
    pending: list[ast.AST] = list(tree.body)
    while pending:
        node = pending.pop()
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
            continue
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
        pending.extend(ast.iter_child_nodes(node))
    return names


def test_s9_6_the_registered_modules_are_exactly_those_importing_the_extra(
    p03: ModuleType,
) -> None:
    source = ROOT / "src"
    importing: set[str] = set()
    for path in sorted((source / "openflowsheet").rglob("*.py")):
        parts = path.relative_to(source).with_suffix("").parts
        name = ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if _module_level_imports(tree) & set(p03.NLP_EXTRA_IMPORTS):
            importing.add(name)
    assert importing == set(p03.NLP_EXTRA_MODULES)
