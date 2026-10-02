"""T07 W6d: the optional `server` extra — its pins, its lock lines, its licences (gate G19), and
that the default install does not need it.

Design note §11.1 and D-Q5. The committed record is `docs/t07-server-licences.json`, written by
`scripts/t07_licence_inventory.py` from the installed closure and the downloaded wheels of both CI
architectures. Two kinds of test live here:

- tests of the **committed record and the repository's pins**, which run in every environment;
- tests of the **installed extra**, which skip cleanly when `mcp` is absent (the default install).
  `test_the_mcp_sdk_speaks_2025_06_18` is the marker W6's binding tests follow: they
  `pytest.importorskip("mcp")` the same way.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tomllib
from types import ModuleType
from typing import Any

import pytest
from conftest import REPO_ROOT
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

RECORD = REPO_ROOT / "docs" / "t07-server-licences.json"
DIRECT = {"mcp", "starlette", "uvicorn"}
# W0.6 measured four compiled distributions in the closure, each with an aarch64 wheel.
COMPILED = {"cffi", "cryptography", "pydantic-core", "rpds-py"}


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "t07_licence_inventory", REPO_ROOT / "scripts" / "t07_licence_inventory.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCRIPT = _script()


@pytest.fixture(scope="module")
def record() -> dict[str, Any]:
    loaded = json.loads(RECORD.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _server_extra() -> list[Requirement]:
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        project = tomllib.load(handle)["project"]
    return [Requirement(text) for text in project["optional-dependencies"]["server"]]


def _lock() -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in (REPO_ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            name, version = line.split("==")
            pins[canonicalize_name(name)] = version
    return pins


def test_the_server_extra_pins_its_three_libraries_exactly() -> None:
    """§11.1: `mcp`, starlette and uvicorn, each `==`; nothing else is a direct requirement."""
    requirements = _server_extra()
    assert {canonicalize_name(requirement.name) for requirement in requirements} == DIRECT
    for requirement in requirements:
        (specifier,) = requirement.specifier
        assert specifier.operator == "==", requirement
        assert requirement.marker is None and not requirement.extras, requirement


def test_the_server_extra_is_not_a_base_dependency() -> None:
    """§11.1: the default install is unchanged."""
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        base = tomllib.load(handle)["project"]["dependencies"]
    assert not DIRECT & {canonicalize_name(Requirement(text).name) for text in base}


def test_the_record_is_of_the_current_pins(record: dict[str, Any]) -> None:
    assert record["format"] == SCRIPT.FORMAT
    assert record["requirements"] == [str(requirement) for requirement in _server_extra()]
    versions = {row["name"]: row["version"] for row in record["distributions"]}
    for requirement in _server_extra():
        assert requirement.specifier.contains(versions[canonicalize_name(requirement.name)])


def test_the_lock_carries_the_whole_server_closure(record: dict[str, Any]) -> None:
    """§11.1: the transitive pins are in `requirements.lock`, at the versions inventoried."""
    lock = _lock()
    for row in record["distributions"]:
        assert lock.get(row["name"]) == row["version"], row["name"]


def test_g19_the_recorded_closure_has_no_gpl_family_or_unresolved_licence(
    record: dict[str, Any],
) -> None:
    """G19 and D-Q5, re-judged from the record's own fields rather than trusted from its verdict."""
    assert record["failures"] == []
    for row in record["distributions"]:
        assert SCRIPT.verdict_of(row) == row["verdict"] == "ok", row["name"]
        declared = row["license_expression"] or row["license"]
        assert declared in SCRIPT.ALLOWED, row["name"]
        assert row["license_files"], f"{row['name']} ships no licence file"


def test_every_compiled_distribution_has_a_wheel_for_both_ci_architectures(
    record: dict[str, Any],
) -> None:
    """Both CI runners (x86-64, aarch64) install from wheels; an aarch64 gap stops W6d."""
    compiled = {row["name"] for row in record["distributions"] if row["compiled"]}
    assert compiled == COMPILED
    for row in record["distributions"]:
        expected = {"x86_64", "aarch64"} if row["compiled"] else {"any"}
        assert set(row["wheels"]) == expected, row["name"]
        for wheel in row["wheels"].values():
            assert len(wheel["sha256"]) == 64 and wheel["file"].endswith(".whl")


def test_the_installed_closure_is_the_recorded_one(record: dict[str, Any]) -> None:
    """With the extra installed, the inventory re-read from this environment equals the record in
    every field an installed environment can show (the wheel hashes are of the downloads)."""
    pytest.importorskip("mcp")
    fresh = SCRIPT.inventory(REPO_ROOT / "pyproject.toml", None)
    assert fresh["failures"] == []
    strip = [{k: v for k, v in row.items() if k != "wheels"} for row in record["distributions"]]
    assert [{k: v for k, v in row.items() if k != "wheels"} for row in fresh["distributions"]] == (
        strip
    )


def test_the_mcp_sdk_speaks_2025_06_18() -> None:
    """The marker for W6's binding tests: skips without the extra, and pins what §11.1 relies on —
    protocol 2025-06-18, `structuredContent` and `outputSchema`, the low-level server over stdio,
    Starlette and uvicorn."""
    types = pytest.importorskip("mcp.types")
    from mcp.server.lowlevel import Server  # noqa: F401
    from mcp.server.stdio import stdio_server  # noqa: F401
    from mcp.shared.version import SUPPORTED_PROTOCOL_VERSIONS
    from starlette.applications import Starlette  # noqa: F401
    from uvicorn import Config  # noqa: F401

    assert "2025-06-18" in SUPPORTED_PROTOCOL_VERSIONS
    assert "structuredContent" in types.CallToolResult.model_fields
    assert "outputSchema" in types.Tool.model_fields


def test_the_core_imports_without_the_server_libraries() -> None:
    """The default install: importing the package and its application layer loads none of the
    server extra's libraries, so it works whether or not the extra is installed."""
    probe = (
        "import sys\n"
        "import openflowsheet\n"
        "import openflowsheet.application.cli, openflowsheet.application.local\n"
        "server = {'mcp', 'starlette', 'uvicorn'}\n"
        "print(sorted(m for m in sys.modules if m.split('.')[0] in server))"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True, cwd=REPO_ROOT
    )
    assert result.stdout.strip() == "[]"
