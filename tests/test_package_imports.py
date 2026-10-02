"""P00 baseline: the package and its nine declared layers import cleanly.

Guards the src layout, the provisional import name, and the blueprint §3 layer set. It asserts
structure only; none of these modules has behavior yet.
"""

from __future__ import annotations

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
