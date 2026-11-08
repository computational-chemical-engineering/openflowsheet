"""X05 (ADR 0069): the packaged lock, verified against the installed runtime closure.

X05.A01-A12, A18, A19, and the static halves of A20 and A25. Every expectation is read from
`benchmarks/x05/reference_values.json`, which `docs/derivations/scripts/x05_reference.py` renders
from its own statement of ADR 0069 D2 (it imports nothing from `openflowsheet`); the code under
test supplies only the values compared against it. The end-to-end states (A13-A17) are
`tests/test_x05_replay_from_the_wheel.py`'s.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib
import traceback
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT

from openflowsheet.canonical import canonical_json
from openflowsheet.resources import PACKAGED, packaged
from openflowsheet.run import lock
from openflowsheet.run.manifest import Environment, environment
from openflowsheet.run.replay import decide_mode

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import t08_dist  # noqa: E402

REFERENCE = json.loads((REPO_ROOT / "benchmarks/x05/reference_values.json").read_text("utf-8"))
LOCK_FILE = REPO_ROOT / REFERENCE["lock"]["path"]
LOCK_BYTES = LOCK_FILE.read_bytes()
WHERE = REFERENCE["lock"]["packaged_as"]
CLOSURE = {row["name"]: row["locked"] for row in REFERENCE["lock"]["runtime_closure"]}
CASES = {case["id"]: case for case in REFERENCE["cases"]}
TEMPLATES = REFERENCE["templates"]
LOCKED = REFERENCE["lock"]["sha256"]


def _normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _lock_pins() -> dict[str, str]:
    """Every `name==version` line of the committed lock, by PEP 503 name."""
    pins: dict[str, str] = {}
    for line in LOCK_BYTES.decode("utf-8").splitlines():
        body = line.split("#", 1)[0].strip()
        if body:
            name, version = body.split("==")
            pins[_normalise(name)] = version
    return pins


def _apply(edits: list[dict[str, Any]]) -> bytes | None:
    """A registered state's lock: the committed bytes with the state's edits, in order."""
    data: bytes | None = LOCK_BYTES
    for edit in edits:
        if edit["op"] == "missing":
            data = None
        elif edit["op"] == "bytes":
            data = bytes.fromhex(edit["hex"])
        elif edit["op"] == "append":
            assert data is not None
            data += edit["text"].encode("utf-8")
        else:
            assert data is not None
            lines = data.decode("utf-8").split("\n")
            (at,) = [i for i, line in enumerate(lines) if line == edit["line"]]
            lines[at : at + 1] = [] if edit["op"] == "remove_line" else [edit["with"]]
            data = "\n".join(lines).encode("utf-8")
    return data


def _installed(table: dict[str, Any]) -> Callable[[str], str | None]:
    """A registered state's installed-version table as the verifier's `installed` callable."""
    errors: dict[str, type[Exception]] = {"ValueError": ValueError, "TypeError": TypeError}

    def installed(name: str) -> str | None:
        value = table.get(name)
        if isinstance(value, dict):
            raise errors[value["raises"]](name)
        return value

    return installed


def _table(case: dict[str, Any]) -> dict[str, Any]:
    base = dict(CLOSURE) if case["installed"]["base"] == "closure" else _lock_pins()
    for name, value in case["installed"]["overrides"].items():
        if value is None:
            base.pop(name, None)
        else:
            base[name] = value
    return base


# -- X05.A01-A09: every registered state through `verify_lock` ---------------------------------


def test_the_registered_states_are_the_adrs_36() -> None:
    assert sorted(CASES) == [f"V{n:02d}" for n in range(1, 37)]
    assert len(LOCK_BYTES.split(b"\n")) - 1 == REFERENCE["lock"]["lines"]
    assert len(_lock_pins()) == REFERENCE["lock"]["pins"]
    assert hashlib.sha256(LOCK_BYTES).hexdigest() == LOCKED


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_a01_to_a09_each_registered_state(case_id: str) -> None:
    case = CASES[case_id]
    data = _apply(case["lock"]["edits"])
    if data is not None:  # the state's lock is the one the JSON registers
        assert hashlib.sha256(data).hexdigest() == case["lock"]["sha256"]
    found = lock.verify_lock(data, _installed(_table(case)), WHERE)
    assert found == (case["expect"]["sha256"], tuple(case["expect"]["findings"])), case["why"]


def test_a01_the_controls_fail_and_the_matched_states_verify() -> None:
    """A01's control: V04-V29 each record `""`; A04's control V01 verifies."""
    for number in range(4, 30):
        case = CASES[f"V{number:02d}"]
        sha, findings = lock.verify_lock(
            _apply(case["lock"]["edits"]), _installed(_table(case)), WHERE
        )
        assert sha == "" and findings, case["id"]
    for case_id in ("V01", "V02", "V03"):
        assert CASES[case_id]["expect"] == {"findings": [], "sha256": LOCKED}


def test_a06_control_an_edit_outside_the_checked_versions_moves_the_hash() -> None:
    v30 = CASES["V30"]
    sha, findings = lock.verify_lock(_apply(v30["lock"]["edits"]), _installed(CLOSURE), WHERE)
    assert findings == () and sha == v30["expect"]["sha256"] != LOCKED


def test_a09_a_real_dist_info_without_version_is_f6_typeerror_under_w_error(
    tmp_path: Path,
) -> None:
    """X05.A09: a dist-info found first on `sys.path` whose METADATA has no `Version` is F6
    `TypeError` through `installed_version` (not "not installed"), with warnings as errors."""
    info = tmp_path / "numpy-2.2.4.dist-info"
    info.mkdir()
    (info / "METADATA").write_text("Metadata-Version: 2.1\nName: numpy\n", encoding="utf-8")
    script = (
        "import json, sys\n"
        "from openflowsheet.run.lock import installed_version, verify_lock\n"
        "data = open(sys.argv[1], 'rb').read()\n"
        "print(json.dumps(verify_lock(data, installed_version, sys.argv[2])))\n"
    )
    ran = subprocess.run(
        [sys.executable, "-W", "error", "-c", script, str(LOCK_FILE), WHERE],
        env={**os.environ, "PYTHONPATH": f"{tmp_path}{os.pathsep}{REPO_ROOT / 'src'}"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert ran.returncode == 0, ran.stderr[-2000:]
    expected = TEMPLATES["F6"].format(name="numpy", error="TypeError")
    assert json.loads(ran.stdout) == ["", [expected]]


# -- X05.A10: the registered closure is the measured closure ------------------------------------


def _measured_closure(roots: list[str]) -> set[str]:
    """ADR 0069 D3.1: the transitive closure from `roots`, no extras (markers with `extra = ""`),
    by recursion over installed metadata."""
    from importlib import metadata

    from packaging.requirements import Requirement

    seen: set[str] = set()
    todo = [Requirement(text) for text in roots]
    while todo:
        requirement = todo.pop()
        if requirement.marker is not None and not requirement.marker.evaluate({"extra": ""}):
            continue
        name = _normalise(requirement.name)
        if name not in seen:
            seen.add(name)
            todo.extend(Requirement(text) for text in metadata.requires(name) or [])
    return seen


def test_a10_the_registered_closure_is_the_measured_closure() -> None:
    pytest.importorskip("packaging")
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text("utf-8"))["project"]
    assert lock.RUNTIME_CLOSURE == tuple(CLOSURE)
    assert _measured_closure(project["dependencies"]) == set(CLOSURE)
    # Control: the five pre-X05 pins alone reach all nine — the four transitive members are found
    # by recursion over installed metadata, not read back from `pyproject.toml` (which, since
    # ADR 0069 Amendment 1, declares exactly these five).
    pre_x05 = [
        f"{name}=={CLOSURE[name]}" for name in ("casadi", "jsonschema", "numpy", "pyyaml", "scipy")
    ]
    assert _measured_closure(pre_x05) == set(CLOSURE)


# -- X05.A11, A12: the checkout records the packaged lock; the document is unchanged -------------


def test_a11_the_checkout_records_the_packaged_lock(tmp_path: Path) -> None:
    assert packaged("requirements.lock").read_bytes() == LOCK_BYTES
    here = environment()
    assert (here.lock_sha256, here.lock_findings) == (LOCKED, ())
    # Control: the checkout is not exempt — V36's lock (the lock moved, not the environment).
    v36 = CASES["V36"]
    moved = tmp_path / "requirements.lock"
    data = _apply(v36["lock"]["edits"])
    assert data is not None
    moved.write_bytes(data)
    there = environment(lock_path=moved)
    assert (there.lock_sha256, there.lock_findings) == ("", tuple(v36["expect"]["findings"]))


def test_a11_a_missing_lock_path_is_f1_naming_the_path(tmp_path: Path) -> None:
    nowhere = tmp_path / "absent.lock"
    found = environment(lock_path=nowhere)
    assert (found.lock_sha256, found.lock_findings) == (
        "",
        (TEMPLATES["F1"].format(where=os.fspath(nowhere)),),
    )


def test_a12_the_environment_document_keeps_its_eight_keys() -> None:
    schema = json.loads((REPO_ROOT / "schemas/run-manifest.schema.json").read_text("utf-8"))
    keys = schema["properties"]["environment"]["properties"]
    here = environment()
    assert sorted(here.as_document()) == sorted(keys)
    assert len(keys) == 8
    findings = ("numpy is 2.2.5, the lock pins 2.2.4",)
    a, b = replace(here, lock_findings=()), replace(here, lock_findings=findings)
    assert a == b
    assert canonical_json(a.as_document()) == canonical_json(b.as_document())
    # Control: differing in `lock_sha256` is a differing environment.
    assert replace(here, lock_sha256="") != here


# -- X05.A18: decide_mode's reasons --------------------------------------------------------------


def _pinned(lock_sha256: str, findings: tuple[str, ...] = ()) -> Environment:
    return Environment(
        architecture="x86_64",
        os_name="Linux",
        os_release="6",
        python_version="3.13.5",
        lock_sha256=lock_sha256,
        blas={"name": "scipy-openblas", "version": "0.3.28"},
        threads={"OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"},
        lock_findings=findings,
    )


def test_a18_decide_modes_reason_templates() -> None:
    verified, failed = _pinned(LOCKED), _pinned("", ("numpy is 2.2.5, the lock pins 2.2.4", "x"))
    joined = TEMPLATES["JOIN"].join(failed.lock_findings)
    inspected = "inspected_archived_results"
    assert decide_mode(_pinned(""), verified) == (inspected, (TEMPLATES["R_ARCHIVE"],))
    assert decide_mode(verified, failed) == (
        inspected,
        (TEMPLATES["R_THIS"].format(findings=joined),),
    )
    assert decide_mode(verified, _pinned("")) == (
        inspected,
        (TEMPLATES["R_THIS"].format(findings=TEMPLATES["NONE"]),),
    )
    assert decide_mode(_pinned(""), failed) == (
        inspected,
        (TEMPLATES["R_BOTH"].format(findings=joined),),
    )
    # The archive's findings are never recorded, so they never reach a reason.
    assert decide_mode(failed, verified) == (inspected, (TEMPLATES["R_ARCHIVE"],))
    # Control: both verified, all else equal.
    assert decide_mode(verified, verified) == ("exact_replay", ())
    assert decide_mode(verified, _pinned("f" * 64))[0] == inspected


# -- X05.A19: one installed-version read per closure member per process --------------------------

_COUNT_READS = """
import collections, importlib.metadata, json, sys
counts = collections.Counter()
real = importlib.metadata.distribution
def counted(name):
    counts[name] += 1
    return real(name)
importlib.metadata.distribution = counted
import openflowsheet.run.manifest as manifest
import scipy  # noqa: F401
counts.clear()
for _ in range(3):
    manifest.environment()
print(json.dumps({name: counts[name] for name in sys.argv[1:]}))
"""


def test_a19_one_read_per_closure_member_per_process() -> None:
    environment_ = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    for _fresh in range(2):  # control: a second fresh interpreter counts one each again
        ran = subprocess.run(
            [sys.executable, "-c", _COUNT_READS, *CLOSURE],
            env=environment_,
            capture_output=True,
            text=True,
            check=False,
        )
        assert ran.returncode == 0, ran.stderr[-2000:]
        assert json.loads(ran.stdout) == dict.fromkeys(CLOSURE, 1)


def test_a19_the_memo_holds_the_outcome_not_only_the_version(monkeypatch: Any) -> None:
    calls: list[str] = []

    def failing(name: str) -> Any:
        calls.append(name)
        raise ValueError(name)

    monkeypatch.setattr(lock, "_INSTALLED", {})
    monkeypatch.setattr("importlib.metadata.distribution", failing)
    raised: list[BaseException] = []
    depths: list[int] = []
    for _ in range(3):
        with pytest.raises(ValueError) as excinfo:
            lock.installed_version("numpy")
        raised.append(excinfo.value)
        depths.append(len(traceback.extract_tb(excinfo.value.__traceback__)))
    assert calls == ["numpy"]
    # D-2: the stored instance is re-raised; review S1: its traceback does not grow per call.
    assert all(error is raised[0] for error in raised)
    assert depths[0] == depths[2], depths


# -- X05.A20, A25: the static halves -------------------------------------------------------------


def test_a20_the_packaged_lock_is_a_link_to_the_root_file() -> None:
    link = REPO_ROOT / "src/openflowsheet/_data/requirements.lock"
    assert "requirements.lock" in PACKAGED
    assert link.is_symlink() and os.readlink(link) == "../../../requirements.lock"
    document = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text("utf-8"))
    assert (
        "_data/requirements.lock" in document["tool"]["setuptools"]["package-data"]["openflowsheet"]
    )
    assert lock.PACKAGED_LOCK_WHERE == WHERE
    named = sorted(
        path.relative_to(REPO_ROOT).as_posix()
        for path in (REPO_ROOT / "src").rglob("requirements.lock")
    )
    assert named == ["src/openflowsheet/_data/requirements.lock"]


#: ADR 0069 D3.2 as amended (Amendment 1, Frank's Q-F1 = no): the five direct members stay exact
#: pins in `Requires-Dist`; the four transitive members of the closure float.
DIRECT = ("numpy", "scipy", "pyyaml", "jsonschema", "casadi")
FLOATING = ("attrs", "jsonschema-specifications", "referencing", "rpds-py")


def test_a25_requires_dist_pins_the_direct_five_and_leaves_the_transitive_four_floating() -> None:
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text("utf-8"))["project"]
    declared = {}
    for text in project["dependencies"]:
        name, version = text.split("==")
        declared[_normalise(name)] = version
    assert declared == {name: CLOSURE[name] for name in DIRECT}
    assert set(CLOSURE) == set(DIRECT) | set(FLOATING)
    # Floating: not named at all, so no specifier of any kind constrains them.
    named = {
        _normalise(re.split(r"[\s<>=!~;\[]", text, maxsplit=1)[0])
        for text in project["dependencies"]
    }
    assert not named & set(FLOATING)
    # The wheel's non-extra `Requires-Dist`, as setuptools writes it (T08.A43 holds the built
    # wheel to the same function), is the same five.
    requires = [r for r in t08_dist.expected_requires_dist(project) if "extra ==" not in r]
    assert requires == sorted(project["dependencies"])
    assert all(_lock_pins()[name] == version for name, version in CLOSURE.items())


def test_a25_an_install_off_the_lock_records_empty_and_the_reason_names_the_floating_members() -> (
    None
):
    """The D5 path: the direct five at the lock (their pins), the floating four at whatever an
    unconstrained resolver picked. Every member off the lock is named, in the closure's order, and
    replaying a bundle written with the verified lock names them in the reason."""
    moved = {"attrs": "99.1.0", "referencing": "0.99.0", "rpds-py": "2099.1.1"}
    found = lock.verify_lock(LOCK_BYTES, _installed({**CLOSURE, **moved}), WHERE)
    findings = tuple(
        TEMPLATES["F4"].format(name=name, installed=moved[name], locked=CLOSURE[name])
        for name in CLOSURE
        if name in moved
    )
    assert found == ("", findings)
    assert [f.split(" ", 1)[0] for f in findings] == ["attrs", "referencing", "rpds-py"]
    current = _pinned(*found)
    assert decide_mode(_pinned(LOCKED), current) == (
        "inspected_archived_results",
        (TEMPLATES["R_THIS"].format(findings=TEMPLATES["JOIN"].join(findings)),),
    )
    # A floating member that is not installed at all is F3, and still named.
    missing = lock.verify_lock(LOCK_BYTES, _installed({**CLOSURE, "attrs": None}), WHERE)
    assert missing == ("", (TEMPLATES["F3"].format(name="attrs", locked=CLOSURE["attrs"]),))
    # Control: an unconstrained resolver that happens to pick the lock's versions verifies.
    assert lock.verify_lock(LOCK_BYTES, _installed(dict(CLOSURE)), WHERE) == (LOCKED, ())
