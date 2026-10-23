"""S07 spec §17 (Erratum 1, R-624), assertions A36-A43: the `coolprop` extra's lock, its licence
record, and the CI wiring. A44 (MR-12) lives in `test_m07_mr12_extras_v02.py`.

Every value is compared for equality: hashes, names, versions and strings. Tests that read the
installed extra call `require_coolprop()` (§17.4); the rest run in every environment.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tomllib
from types import ModuleType
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from s07_coolprop_support import ABSENT_REASON, require_coolprop

LOCK = REPO_ROOT / "requirements.lock"
COOLPROP_LOCK = REPO_ROOT / "requirements-coolprop.lock"
RECORD = REPO_ROOT / "docs" / "s07-coolprop-licences.json"
SERVER_RECORD = REPO_ROOT / "docs" / "t07-server-licences.json"
A30 = [REPO_ROOT / "docs" / "t08-a30" / f"t08-a30-{arch}.json" for arch in ("x86_64", "aarch64")]
CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"

LOCK_SHA256 = "ead4edf1ea3577287a7576d56a9e5db550e5a5be459dd634b10806fdc655b9c4"
SERVER_RECORD_SHA256 = "3052fb332fff417bd861107f71fedbacf813dd3e28ea5c5b40385c4e749dac7b"
WHEEL_SHA256 = {
    "x86_64": "8ca1aefd1873b14f3e7e9122a08a32fe8c62ac03a1fc4496512a31a3bba8f611",
    "aarch64": "113fc0e97f2b64617141d453ddc0439987b32aa3f6f4a45b928b2030c68292fa",
}
X86_WHEEL = "coolprop-8.0.0-cp312-abi3-manylinux2014_x86_64.manylinux_2_17_x86_64.whl"
AARCH64_WHEEL = "coolprop-8.0.0-cp312-abi3-manylinux2014_aarch64.manylinux_2_17_aarch64.whl"
LICENCE_SHA256 = "9bf835333ef602af4cb19338b9f9d43671e174fa029b00280e9bdba6ea4719b2"
EXPECTED_RECORD: dict[str, Any] = {
    "format": "s07-coolprop-licences-v1",
    "extra": "coolprop",
    "requirements": ["CoolProp==8.0.0"],
    "distributions": [
        {
            "name": "coolprop",
            "version": "8.0.0",
            "license_expression": None,
            "license": "MIT",
            "license_classifiers": ["OSI Approved :: MIT License"],
            "license_files": {"licenses/LICENSE": LICENCE_SHA256},
            "compiled": True,
            "wheels": {
                "x86_64": {
                    "file": X86_WHEEL,
                    "sha256": WHEEL_SHA256["x86_64"],
                },
                "aarch64": {
                    "file": AARCH64_WHEEL,
                    "sha256": WHEEL_SHA256["aarch64"],
                },
            },
            "verdict": "ok",
        }
    ],
    "base_members": [{"name": "numpy", "version": "2.2.4"}],
    "failures": [],
}
ALLOWED_KEYS = {
    "MIT",
    "MIT-0",
    "BSD-3-Clause",
    "Apache-2.0",
    "Apache-2.0 OR BSD-3-Clause",
    "PSF-2.0",
    "MPL-2.0",
}


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "t07_licence_inventory", REPO_ROOT / "scripts" / "t07_licence_inventory.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256(path: Any) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pyproject() -> dict[str, Any]:
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["project"]


def _record() -> dict[str, Any]:
    return json.loads(RECORD.read_text(encoding="utf-8"))


def test_a36_the_base_lock_is_byte_unchanged_and_has_no_coolprop() -> None:
    assert _sha256(LOCK) == LOCK_SHA256
    names = [
        canonicalize_name(line.split("==", 1)[0])
        for line in LOCK.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#") and "==" in line
    ]
    assert names and "coolprop" not in names


def test_a37_the_pin_agrees_across_extra_lock_and_record() -> None:
    text = COOLPROP_LOCK.read_text(encoding="utf-8")
    body = [line for line in text.splitlines() if line.strip() and not line.startswith("#")]
    assert len(body) == 1
    requirement = body[0].split(" --hash", 1)[0]
    assert requirement == "CoolProp==8.0.0"
    assert [str(Requirement(requirement))] == _pyproject()["optional-dependencies"]["coolprop"]
    assert _pyproject()["optional-dependencies"]["coolprop"] == ["CoolProp==8.0.0"]
    hashes = set(re.findall(r"--hash=sha256:([0-9a-f]{64})", body[0]))
    assert hashes == set(WHEEL_SHA256.values())
    wheels = _record()["distributions"][0]["wheels"]
    assert {wheel["sha256"] for wheel in wheels.values()} == hashes


def test_a38_the_extra_adds_only_coolprop_to_the_base_closure() -> None:
    require_coolprop()
    script = _script()
    pyproject = REPO_ROOT / "pyproject.toml"
    extra = set(script.closure(script.extra_requirements(pyproject, "coolprop")))
    base = script.closure(script.base_requirements(pyproject))
    assert extra - set(base) == {"coolprop"}
    pins = script.lock_pins(LOCK)
    for name in extra & set(base):
        assert base[name].version == pins[name]


def test_a39_the_committed_record_is_the_expected_one() -> None:
    script = _script()
    record = _record()
    # `python` is the recording venv's patch level, which CI's may differ from.
    assert {key: value for key, value in record.items() if key != "python"} == EXPECTED_RECORD
    row = record["distributions"][0]
    assert script.verdict_of(row) == "ok"
    assert (row["license_expression"] or row["license"]) in script.ALLOWED
    assert row["license_files"]


def test_a39_the_installed_extra_reads_back_as_the_record() -> None:
    require_coolprop()
    committed = _record()
    reread = _script().inventory(REPO_ROOT / "pyproject.toml", None, "coolprop")
    assert reread["failures"] == []

    def without_wheels(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{key: value for key, value in row.items() if key != "wheels"} for row in rows]

    assert without_wheels(reread["distributions"]) == without_wheels(committed["distributions"])
    assert reread["base_members"] == committed["base_members"]


def test_a40_the_base_members_are_in_both_a30_records() -> None:
    members = _record()["base_members"]
    for path in A30:
        document = json.loads(path.read_text(encoding="utf-8"))
        assert document["lock_sha256"] == LOCK_SHA256
        assert document["verdict"]["pass"] is True
        rows = {row["name"]: row["version"] for row in document["distributions"]}
        for member in members:
            assert rows.get(member["name"]) == member["version"], path.name


def test_a41_the_server_path_is_unchanged() -> None:
    assert set(_script().ALLOWED) == ALLOWED_KEYS
    assert _sha256(SERVER_RECORD) == SERVER_RECORD_SHA256
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "tests/test_t07_server_extra.py",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout[-2000:]


def test_a42_without_the_partition_numpy_reaches_the_judge_and_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    require_coolprop()
    script = _script()
    assert script.inventory(REPO_ROOT / "pyproject.toml", None, "coolprop")["failures"] == []
    real = script.closure
    # An empty base closure makes the partition empty: every row goes through `verdict_of`.
    monkeypatch.setattr(
        script,
        "closure",
        lambda roots: {}
        if roots == script.base_requirements(REPO_ROOT / "pyproject.toml")
        else real(roots),
    )
    unpartitioned = script.inventory(REPO_ROOT / "pyproject.toml", None, "coolprop")
    assert unpartitioned["failures"] == ["numpy: not-allowed"]


def _helper_outcome(require: bool) -> tuple[str, str]:
    """Run the helper in a subprocess where `import CoolProp` fails; return (outcome, message)."""
    code = (
        "import sys, json\n"
        f"sys.path.insert(0, {str(REPO_ROOT / 'tests')!r})\n"
        "sys.modules['CoolProp'] = None\n"
        "import pytest\n"
        "from s07_coolprop_support import require_coolprop\n"
        "try:\n"
        "    require_coolprop()\n"
        "    out = ['returned', '']\n"
        "except pytest.skip.Exception as error:\n"
        "    out = ['skipped', str(error)]\n"
        "except pytest.fail.Exception as error:\n"
        "    out = ['failed', str(error)]\n"
        "print(json.dumps(out))\n"
    )
    env = {
        key: value for key, value in os.environ.items() if key != "OPENFLOWSHEET_REQUIRE_COOLPROP"
    }
    if require:
        env["OPENFLOWSHEET_REQUIRE_COOLPROP"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    outcome, message = json.loads(result.stdout.strip().splitlines()[-1])
    return outcome, message


def test_a43_an_absent_coolprop_skips_and_fails_under_the_flag() -> None:
    assert _helper_outcome(False) == ("skipped", ABSENT_REASON)
    assert _helper_outcome(True) == ("failed", ABSENT_REASON)
    assert ABSENT_REASON == (
        "CoolProp 8.0.0 is not installed: "
        "python -m pip install --no-deps --require-hashes -r requirements-coolprop.lock"
    )


def test_a43_ci_installs_the_lock_and_requires_coolprop() -> None:
    steps = yaml.safe_load(CI.read_text(encoding="utf-8"))["jobs"]["check"]["steps"]
    job_env = yaml.safe_load(CI.read_text(encoding="utf-8"))["jobs"]["check"].get("env", {})
    runs = [step.get("run", "") for step in steps]
    checks = next(i for i, run in enumerate(runs) if "./scripts/check.sh" in run)
    flag = {**job_env, **steps[checks].get("env", {})}.get("OPENFLOWSHEET_REQUIRE_COOLPROP")
    assert flag == "1"
    install = "--no-deps --require-hashes -r requirements-coolprop.lock"
    assert any(install in run for run in runs[:checks])
    assert any("t07_licence_inventory.py --extra coolprop" in run for run in runs)
