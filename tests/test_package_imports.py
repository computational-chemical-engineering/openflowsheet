"""P00 baseline: the package and its nine declared layers import cleanly.

Guards the src layout, the provisional import name, and the blueprint §3 layer set. It asserts
structure only; none of these modules has behavior yet.
"""

from __future__ import annotations

import ast
import importlib
import tomllib
from pathlib import Path

import pytest

LAYERS = [
    "ir",
    "units",
    "models",
    "thermo",
    "compile",
    "graph",
    "numerics",
    "orchestrator",
    # K04's verifier. A top-level layer because blueprint §8.1's "the verifier shares nothing
    # with the solver" is easier to keep true when it is not a subpackage of the solver.
    "verify",
    # K05's runs, manifests and replay. Above both, because a run is a solve *and* its
    # verification and must not be a subpackage of either.
    "run",
    # M02's external-model adapters and experiment records (blueprint §15): below `application`,
    # which runs them, and above `models`, whose boundary they evaluate.
    "adapters",
    "application",
]


def package_dir() -> Path:
    module = importlib.import_module("openflowsheet")
    assert module.__file__ is not None
    return Path(module.__file__).parent


def test_root_package_exposes_version() -> None:
    """The version is declared twice, `pyproject.toml` and `__version__`, and the two agree (T08
    W4.1; `scripts/t08_dist.py` also checks the built metadata against both)."""
    module = importlib.import_module("openflowsheet")
    project = tomllib.loads((Path(__file__).resolve().parent.parent / "pyproject.toml").read_text())
    assert module.__version__ == project["project"]["version"]


def test_package_ships_py_typed() -> None:
    assert (package_dir() / "py.typed").is_file()


@pytest.mark.parametrize("layer", LAYERS)
def test_layer_imports_and_is_documented(layer: str) -> None:
    module = importlib.import_module(f"openflowsheet.{layer}")
    assert module.__doc__ is not None, f"{layer} has no docstring"
    assert "introduced by package" in module.__doc__, (
        f"{layer} docstring must name the work package that introduces it"
    )


def test_no_unexpected_layers() -> None:
    """`studies`, `adapters`, clients and the web shell are not created before their packages."""
    present = sorted(
        entry.name
        for entry in package_dir().iterdir()
        if entry.is_dir() and (entry / "__init__.py").is_file()
    )
    assert present == sorted(LAYERS)


def _imported_modules(source: str, package: str) -> set[str]:
    """Every module `source` (a module of `package`) imports, anywhere — module level, function
    bodies (lazy imports) and `TYPE_CHECKING` blocks alike — with relative imports resolved."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".")
                stem = ".".join(parts[: len(parts) - node.level + 1])
                base = f"{stem}.{node.module}" if node.module else stem
            else:
                base = node.module or ""
            found.add(base)
            found.update(f"{base}.{alias.name}" for alias in node.names)
    return found


def _upward(names: set[str]) -> list[str]:
    application = "openflowsheet.application"
    return sorted(n for n in names if n == application or n.startswith(f"{application}."))


def test_adapters_never_import_application() -> None:
    """R-237 (M02 design note §14 B4): `adapters` sits below `application`; no module of it
    imports `openflowsheet.application`, lazily or not."""
    root = package_dir()
    offending = {}
    for path in sorted((root / "adapters").rglob("*.py")):
        package = ".".join(("openflowsheet", *path.relative_to(root).parts[:-1]))
        found = _upward(_imported_modules(path.read_text(encoding="utf-8"), package))
        if found:
            offending[str(path.relative_to(root))] = found
    assert offending == {}


def test_the_import_scan_sees_lazy_relative_and_type_checking_imports() -> None:
    source = (
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n    from openflowsheet.application.store import ProjectStore\n"
        "def f():\n    from ...application import store\n    import openflowsheet.application.cli\n"
        "from .. import variants\n"
    )
    found = _imported_modules(source, "openflowsheet.adapters.experiments")
    assert _upward(found) == [
        "openflowsheet.application",
        "openflowsheet.application.cli",
        "openflowsheet.application.store",
        "openflowsheet.application.store.ProjectStore",
    ]
    assert "openflowsheet.adapters.variants" in found
