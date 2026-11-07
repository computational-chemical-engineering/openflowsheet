"""X02 WO-5: the warm reactor child `adapters/pymrm/child_warm.py` (design note §5.6; ADR 0070 D4,
D7, D10), on what needs no reactor environment. The reactor itself is measured by the workstation
campaign G5 (`benchmarks/x02/g5_warm_reactor.py`).

- **The pin.** `BASE_CHILD_SHA256` is `child.py`'s hash and v3's `runner_sha256`; a base that
  does not hash to it exits 72 as a script and raises when imported.
- **The profile and the variant.** `PROFILE_W` is the base profile renamed plus the start; the
  provisional variant is v3's document with exactly §5.6's four changes, and `pinned_program`
  selects `child_warm.py` for it.
- **Isolation, exits, literals.** The base child's AST and literal checks, widened to this file:
  the standard library plus the one by-path load, every exit `os._exit`, the protocol's names.
- **The start and the export.** `tube-profile-v1` round-trips bit for bit; every malformed start
  is `MismatchError`.
- **The chain.** `evaluate_w` over stub windows: cold passes through, a warm outlet answers with
  `used`, any refusal or covered exception of the warm chain answers through the cold chain with
  `fallback_from`, an uncovered exception propagates.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from conftest import REPO_ROOT, load_json

from openflowsheet.adapters import variants
from openflowsheet.adapters.experiments import backends
from openflowsheet.adapters.external import protocol

PYMRM = REPO_ROOT / "src" / "openflowsheet" / "adapters" / "pymrm"
CHILD = PYMRM / "child.py"
WARM = PYMRM / "child_warm.py"
V3_ID = "pymrm-6089593-g2-nz800-s123-v3"
PROVISIONAL = REPO_ROOT / "benchmarks" / "x02" / "variant-s123w-provisional.json"
SYNTHETIC_WARM = REPO_ROOT / "tests" / "support" / "synthetic_warm_child.py"


def _load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


WARM_MODULE = _load(WARM, "ofs_pymrm_child_warm_test")
BASE = WARM_MODULE.base


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# -- the pin ---------------------------------------------------------------------------------------


def test_the_base_hash_literal_is_child_py_and_v3s_runner_hash() -> None:
    v3 = variants.registered_variant(V3_ID)
    assert WARM_MODULE.BASE_CHILD_SHA256 == _sha256(CHILD) == v3.evaluation["runner_sha256"]
    assert WARM_MODULE.BASE_CHILD == CHILD
    assert BASE.__name__ == "ofs_pymrm_child_base"


def _copied(tmp_path: Path, edit: bool) -> Path:
    shutil.copy(WARM, tmp_path / "child_warm.py")
    text = CHILD.read_text(encoding="utf-8")
    (tmp_path / "child.py").write_text(text + ("\n# edited\n" if edit else ""), encoding="utf-8")
    return tmp_path / "child_warm.py"


def test_an_edited_base_exits_72_as_a_script(tmp_path: Path) -> None:
    script = _copied(tmp_path, edit=True)
    done = subprocess.run(
        [sys.executable, "-I", str(script)], input=b"", capture_output=True, timeout=60, check=False
    )
    assert done.returncode == protocol.EXIT_ENVIRONMENT_MISMATCH == 72
    assert done.stderr.decode().startswith("environment_mismatch: child.py hashes to ")


def test_the_unedited_base_loads_past_the_pin(tmp_path: Path) -> None:
    """Control: the same copy with the base unchanged gets past the pin (and stops later, at the
    environment, since none is set up here)."""
    script = _copied(tmp_path, edit=False)
    request = json.dumps({"protocol": 1, "deadline_s": 30, "request_sha256": "0" * 64})
    process = subprocess.Popen(
        [sys.executable, "-I", str(script)],
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={"PATH": "/usr/bin:/bin"},
    )
    assert process.stdin is not None and process.stderr is not None
    process.stdin.write((request + "\n").encode())
    process.stdin.flush()  # stdin stays open: the lifeline holds
    code = process.wait(timeout=60)
    stderr = process.stderr.read()
    process.stdin.close()
    process.stderr.close()
    assert code == 72
    assert b"hashes to" not in stderr and b"NUMBA_CACHE_DIR" in stderr


def test_an_edited_base_raises_when_imported(tmp_path: Path) -> None:
    script = _copied(tmp_path, edit=True)
    with pytest.raises(Exception, match="hashes to") as raised:
        _load(script, "ofs_pymrm_child_warm_edited")
    assert type(raised.value).__name__ == "BaseMismatchError"


# -- the profile and the variant ---------------------------------------------------------------


def test_profile_w_is_the_base_profile_renamed_plus_the_start() -> None:
    profile = dict(WARM_MODULE.PROFILE_W)
    start = profile.pop("start")
    assert profile.pop("id") == "M01-S123W-v1"
    base = dict(BASE.PROFILE)
    assert base.pop("id") == "M01-S123-v2"
    assert profile == base
    assert start == {
        "kind": "profile",
        "format": "tube-profile-v1",
        "file": "start.json",
        "replaces": ["S1"],
        "S2": "built at the true inlet from the start's c, p, T; dt_init and acceptance as S2",
        "fallback": "the S1-S3 chain of M01-S123-v2, in the same attempt, on any refusal or "
        "model_exception of the warm chain",
        "export": "profile.json after every outlet answer",
    }


def test_the_provisional_variant_is_v3s_with_the_four_changes() -> None:
    document = load_json(PROVISIONAL)
    v3 = json.loads((PYMRM.parent / "variants" / f"{V3_ID}.json").read_text(encoding="utf-8"))
    assert document["variant_id"] == "pymrm-6089593-g2-nz800-s123w-v1"
    assert document["evaluation"]["profile"] == WARM_MODULE.PROFILE_W
    assert document["evaluation"]["runner_sha256"] == _sha256(WARM)
    measured = document["accuracy"]["measured_path_independence_rel"]
    assert measured < document["accuracy"]["precision_floor_rel"] / 10
    for name in ("variant_id",):
        v3[name] = document[name]
    v3["evaluation"]["profile"] = document["evaluation"]["profile"]
    v3["evaluation"]["runner_sha256"] = document["evaluation"]["runner_sha256"]
    v3["accuracy"]["measured_path_independence_rel"] = measured
    assert document == v3
    variant = variants.variant_from_document(document)
    assert backends.start_capable(variant)
    assert backends.pinned_program(variant).script.name == "child_warm.py"


def _configuration(profile: Any) -> dict[str, Any]:
    v3 = variants.registered_variant(V3_ID)
    return {"configuration": {**v3.evaluation["configuration"], "profile": profile}}


def test_the_configuration_check_compares_against_profile_w() -> None:
    checked = WARM_MODULE._configuration_w(_configuration(WARM_MODULE.PROFILE_W))
    assert checked == BASE._configuration(_configuration(BASE.PROFILE))
    with pytest.raises(BASE.MismatchError):
        WARM_MODULE._configuration_w(_configuration(BASE.PROFILE))
    with pytest.raises(BASE.MismatchError):
        BASE._configuration(_configuration(WARM_MODULE.PROFILE_W))


# -- isolation, exits, literals ------------------------------------------------------------------


def test_the_warm_child_imports_only_the_stdlib_and_loads_only_its_base_by_path() -> None:
    tree = ast.parse(WARM.read_text(encoding="utf-8"))
    roots: set[str] = set()
    loads: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            roots.add((node.module or "").split(".")[0])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr != "import_module", "the warm child imports nothing dynamically"
            if node.func.attr == "spec_from_file_location":
                loads.append(ast.unparse(node))
    assert {name for name in roots if name not in sys.stdlib_module_names} == set()
    assert loads == ["importlib.util.spec_from_file_location(BASE_MODULE, BASE_CHILD)"]
    assert "exec(" not in WARM.read_text(encoding="utf-8")


def test_no_module_of_the_package_imports_the_warm_child() -> None:
    package = REPO_ROOT / "src" / "openflowsheet"
    for path in sorted(package.rglob("*.py")):
        if path == WARM:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import | ast.ImportFrom):
                names = [alias.name for alias in node.names]
                module = node.module if isinstance(node, ast.ImportFrom) else None
                assert "child_warm" not in names and not (module or "").endswith("child_warm")


def test_every_exit_of_the_warm_child_is_os_exit() -> None:
    tree = ast.parse(WARM.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            function = node.func
            name = (
                function.attr
                if isinstance(function, ast.Attribute)
                else getattr(function, "id", "")
            )
            owner = getattr(getattr(function, "value", None), "id", None)
            assert not (owner == "sys" and name == "exit")
            assert name not in ("exit", "quit") or owner == "os" or name == "_exit"
        if isinstance(node, ast.Raise) and node.exc is not None:
            raised = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
            assert getattr(raised, "id", None) != "SystemExit"
    guard = tree.body[-1]
    assert isinstance(guard, ast.If) and "__main__" in ast.unparse(guard.test)
    source = ast.unparse(guard)
    assert "signal.signal(signal.SIGINT, signal.SIG_DFL)" in source
    (handler,) = [node for node in ast.walk(guard) if isinstance(node, ast.ExceptHandler)]
    assert handler.type is not None and ast.unparse(handler.type) == "Exception"
    assert "os._exit(1)" in ast.unparse(handler)


def test_the_warm_childs_literals_are_the_protocols_and_the_backends() -> None:
    assert WARM_MODULE.EXIT_BASE_MISMATCH == protocol.EXIT_ENVIRONMENT_MISMATCH
    assert WARM_MODULE.START_FILE == backends.START_FILE
    assert WARM_MODULE.PROFILE_FILE == backends.PROFILE_FILE
    assert WARM_MODULE.START_MEMBER in Path(backends.__file__).read_text(encoding="utf-8")
    synthetic = _load(SYNTHETIC_WARM, "ofs_synthetic_warm_child_test")
    assert WARM_MODULE.PROFILE_FORMAT == synthetic.FORMAT
    assert (WARM_MODULE.SIDES, WARM_MODULE.FIELDS) == (2, len(BASE.SPECIES) + 2)
    assert "child_warm.py" in backends.CHILD_SCRIPTS


# -- the start and the export ----------------------------------------------------------------------

NUM_Z = 800
TRICKY = [5e-324, -0.0, 0.1 + 0.2, 1e300, 2.0**-1074 * 3, 1 / 3, 101325.0, 673.15]


def _fields() -> Any:
    values = np.linspace(0.0, 1.0, NUM_Z * 14)
    values[: len(TRICKY)] = TRICKY
    return values.reshape((NUM_Z, 2, 7))


def _hex(values: Any) -> list[str]:
    return [float(value).hex() for value in values]


def test_a_profile_round_trips_bit_for_bit(tmp_path: Path) -> None:
    fields = _fields()
    sha256 = WARM_MODULE.export_profile(fields, tmp_path)
    data = (tmp_path / "profile.json").read_bytes()
    assert (
        hashlib.sha256(data).hexdigest()
        == sha256
        == hashlib.sha256(WARM_MODULE.profile_bytes(fields)).hexdigest()
    )
    document = json.loads(data)
    assert document["format"] == "tube-profile-v1" and document["shape"] == [NUM_Z, 2, 7]
    assert data == json.dumps(document, sort_keys=True, separators=(",", ":")).encode("ascii")
    (tmp_path / "start.json").write_bytes(data)
    values = WARM_MODULE.read_start(tmp_path, sha256, NUM_Z)
    assert _hex(values) == _hex(fields.reshape(-1))
    assert not (tmp_path / "profile.json.tmp").exists()


def _start(tmp_path: Path, document: Any, raw: bytes | None = None) -> str:
    data = raw if raw is not None else json.dumps(document).encode()
    (tmp_path / "start.json").write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _valid() -> dict[str, Any]:
    return {"format": "tube-profile-v1", "shape": [NUM_Z, 2, 7], "cpT": [1.0] * (NUM_Z * 14)}


@pytest.mark.parametrize(
    "case",
    ["missing", "hash", "json", "format", "shape", "length", "nan", "bool", "string", "sha_type"],
)
def test_a_malformed_start_is_a_mismatch(tmp_path: Path, case: str) -> None:
    document = _valid()
    raw = None
    if case == "format":
        document["format"] = "tube-profile-v2"
    elif case == "shape":
        document["shape"] = [NUM_Z, 1, 14]
    elif case == "length":
        document["cpT"] = document["cpT"][:-1]
    elif case == "bool":
        document["cpT"][5] = True
    elif case == "string":
        document["cpT"][5] = "1.0"
    elif case == "json":
        raw = b"{not json"
    elif case == "nan":
        raw = json.dumps(document).replace("1.0", "NaN", 1).encode()
    sha256: Any = _start(tmp_path, document, raw)
    if case == "missing":
        (tmp_path / "start.json").unlink()
    elif case == "hash":
        sha256 = "0" * 64
    elif case == "sha_type":
        sha256 = None
    with pytest.raises(BASE.MismatchError):
        WARM_MODULE.read_start(tmp_path, sha256, NUM_Z)
    sha256 = _start(tmp_path, _valid())  # control: the valid document reads
    assert len(WARM_MODULE.read_start(tmp_path, sha256, NUM_Z)) == NUM_Z * 14


# -- the chain (evaluate_w over stub windows) ----------------------------------------------------


TUBE = {"composition": [0.7, 0.23, 0.03, 0.02, 0.02]}
GOOD = {"kpi_drift_ok": True}


def _outlet(model: str, *, u_ret_min: float = 1.0, temperature: float = 700.0) -> dict[str, Any]:
    return {
        "tube_outlet": {"flows": [1.0] * 5, "temperature": temperature, "model": model},
        "diagnostics": {"u_ret_min": u_ret_min, "min_axial_flow_mol_s": 1.0},
    }


class Stub:
    """A `WarmReactor` without `__init__`, whose two windows are stubs: `cold` and `warm` are the
    answers (a stage, an exception, or an outlet) and `seen` records each window's call."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, cold: Any, warm: Any) -> None:
        reactor = object.__new__(WARM_MODULE.WarmReactor)
        reactor.configuration = {"num_z": 2}
        reactor.np = np
        reactor.remembered = None
        reactor._start = None
        self.reactor = reactor
        self.seen: list[tuple[str, Any]] = []

        def window(answer: Any, name: str, diagnostics: dict[str, Any]) -> Any:
            diagnostics["stages"][f"{name}-stage"] = {"accepted": True}
            if isinstance(answer, BaseException):
                raise answer
            if isinstance(answer, str):
                return answer
            reactor.remembered = name
            return GOOD, answer

        def cold_window(self_: Any, tube: Any, y_in: Any, y_trace: Any, *rest: Any) -> Any:
            self.seen.append(("cold", None))
            return window(cold, "cold", rest[-1])

        def warm_window(tube: Any, y_in: Any, s2: Any, backflow: Any, diagnostics: Any) -> Any:
            self.seen.append(("warm", reactor._start.shape))
            return window(warm, "warm", diagnostics)

        monkeypatch.setattr(BASE.Reactor, "_window", cold_window)
        reactor._warm_window = warm_window

    def run(self, start: Any) -> dict[str, Any]:
        result: dict[str, Any] = self.reactor.evaluate_w(TUBE, None, [0.0] * 5, start)
        assert self.reactor._start is None
        return result


START = ("a" * 64, [1.0] * 28)


def test_a_cold_request_runs_the_base_window_only(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = Stub(monkeypatch, _outlet("cold"), AssertionError("no warm chain"))
    result = stub.run(None)
    assert stub.seen == [("cold", None)]
    assert result["outcome"] == "outlet" and result["diagnostics"]["start"] is None


def test_a_warm_outlet_answers_with_used(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = Stub(monkeypatch, AssertionError("no cold chain"), _outlet("warm"))
    result = stub.run(START)
    assert stub.seen == [("warm", (2, 2, 7))]
    assert result["outcome"] == "outlet" and result["tube_outlet"]["model"] == "warm"
    assert result["diagnostics"]["start"] == {
        "profile_sha256": "a" * 64,
        "used": True,
        "fallback_from": None,
        "warm_stages": {"warm-stage": {"accepted": True}},
    }
    assert stub.reactor.remembered == "warm"


@pytest.mark.parametrize(
    ("warm", "stage"),
    [
        ("S2", "S2"),
        ("S3", "S3"),
        (_outlet("warm", u_ret_min=0.0), "backflow"),
        (_outlet("warm", temperature=math.nan), "nonfinite"),
        (ValueError("singular"), "model_exception"),
    ],
)
def test_a_refused_warm_chain_answers_through_the_cold_chain(
    monkeypatch: pytest.MonkeyPatch, warm: Any, stage: str
) -> None:
    stub = Stub(monkeypatch, _outlet("cold"), warm)
    result = stub.run(START)
    assert stub.seen == [("warm", (2, 2, 7)), ("cold", None)]
    assert result["outcome"] == "outlet" and result["tube_outlet"]["model"] == "cold"
    start = result["diagnostics"]["start"]
    assert (start["used"], start["fallback_from"]) == (False, stage)
    assert "warm-stage" in start["warm_stages"]
    assert ("model_exception" in start["warm_stages"]) == (stage == "model_exception")
    assert "model_exception" not in result["diagnostics"]
    assert stub.reactor.remembered == "cold"


def test_a_cold_fallback_that_refuses_is_the_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = Stub(monkeypatch, "S1", "S2")
    result = stub.run(START)
    assert (result["outcome"], result["stage"]) == ("not_accepted", "S1")
    assert result["diagnostics"]["start"]["fallback_from"] == "S2"
    assert stub.reactor.remembered is None


def test_an_uncovered_exception_of_the_warm_chain_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = Stub(monkeypatch, AssertionError("no cold chain"), MemoryError())
    with pytest.raises(MemoryError):
        stub.run(START)
    assert stub.reactor._start is None
