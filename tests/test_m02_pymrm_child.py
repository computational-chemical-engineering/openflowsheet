"""M02 WO-5 in the default gate (design note §2.2-§2.4, §3.1; ADR 0033 D1, D2): the reactor child,
the environment builder, the lock and the registered real variant — without PyMRM.

- **The child is isolated by construction.** It imports nothing outside the standard library,
  numpy, scipy, pymrm and the pinned `reactor` package (its `import` statements and its
  `import_module` strings alike); no module of `openflowsheet` imports it; its protocol literals
  are the protocol's, its environment layout is the builder's, its cheap fingerprint is the
  backend's; the evidence-only switches are named nowhere else in the package.
- **Every exit is `os._exit`.** No `sys.exit`, `exit`, `quit` or `SystemExit` in the child, and
  SIGINT keeps its default action (so no `KeyboardInterrupt` reaches a normal exit); run by this
  project's interpreter, an environment it cannot find exits 72 with its reason, an exception
  raised while the lifeline thread is blocked in stdin exits 1, and a SIGINT ends it by the
  signal — never SIGABRT (log D11).
- **The builder agrees with the child and the probe.** The export tree hash of `env` (ADR 0002
  canonical JSON) equals the child's (stdlib JSON) on a tree with nested and non-ASCII paths; the
  merged database is `reactor_probe.merged_database(..., "N2")`'s; both parse the lock alike.
- **The lock** pins every distribution by hash, holds the probe's five recorded versions, and is
  the variant's `lock_sha256`; the variant's `env_id` is §2.4's.
- **The real variant (R-232, D15)**: its per-tube flow bound is exactly [0.5, 2] x the probe's
  pinned F_ret_in; its profile and configuration are the child's; its rights block says the code is
  used by reference; its execution and accuracy blocks are the note's numbers.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT, load_json

from benchmarks.m01 import reactor_probe
from openflowsheet.adapters import variants
from openflowsheet.adapters.experiments import backends
from openflowsheet.adapters.external import launcher, protocol
from openflowsheet.adapters.pymrm import env
from openflowsheet.canonical import file_sha256

PACKAGE = REPO_ROOT / "src" / "openflowsheet"
CHILD = PACKAGE / "adapters" / "pymrm" / "child.py"
REAL_ID = "pymrm-6089593-g2-nz800-s123-v1"
PROBE: dict[str, Any] = load_json(REPO_ROOT / "benchmarks" / "m01" / "reactor-probe.json")
F_NOM: float = PROBE["pinned"]["F_ret_in_mol_s"]
#: R-232, design note §3.1: [0.5, 2] x F_nom, as registered in the note.
FLOW_BOUND = [0.003573480649651052, 0.014293922598604208]
ALLOWED_IMPORTS = frozenset({"numpy", "scipy", "pymrm", "reactor"})


def _child_module() -> Any:
    """The child's module namespace, loaded from its file (it imports the standard library only
    at import time)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("ofs_reactor_child", CHILD)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHILD_MODULE = _child_module()


# -- isolation -------------------------------------------------------------------------------------


def test_the_child_imports_only_the_stdlib_numpy_scipy_pymrm_and_reactor() -> None:
    tree = ast.parse(CHILD.read_text(encoding="utf-8"))
    roots: set[str] = set()
    dynamic: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "the child is a script: no relative import"
            roots.add((node.module or "").split(".")[0])
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "import_module"
        ):
            (argument,) = node.args
            assert isinstance(argument, ast.Constant) and isinstance(argument.value, str)
            dynamic.add(argument.value.split(".")[0])
    outside = {name for name in roots if name not in sys.stdlib_module_names}
    assert outside <= ALLOWED_IMPORTS and not outside, outside  # statically: stdlib only
    assert dynamic <= ALLOWED_IMPORTS - {"scipy", "pymrm"} | {"reactor", "numpy"}, dynamic
    assert "openflowsheet" not in roots | dynamic


def test_no_module_of_the_package_imports_the_child() -> None:
    offending = []
    for path in sorted(PACKAGE.rglob("*.py")):
        if path == CHILD:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = [module, *(f"{module}.{alias.name}" for alias in node.names)]
                if node.level and (module == "child" or "child" in {a.name for a in node.names}):
                    names.append("child")
            if any(name == "child" or name.endswith("pymrm.child") for name in names):
                offending.append(str(path.relative_to(PACKAGE)))
    assert offending == []


def test_the_childs_literals_are_the_protocols_the_builders_and_the_backends() -> None:
    for name in (
        "PROTOCOL_VERSION",
        "EXIT_LIFELINE_LOST",
        "EXIT_SELF_DEADLINE",
        "EXIT_ENVIRONMENT_MISMATCH",
        "RESULT_FILE",
        "RESULT_TEMPORARY",
        "HANDSHAKE_ARGUMENT",
        "OUTCOME_OUTLET",
        "OUTCOME_NOT_ACCEPTED",
        "OUTCOME_HANDSHAKE",
        "SELF_DEADLINE_MARGIN_S",
        "DEADLINE_MARGIN_VARIABLE",
    ):
        assert getattr(CHILD_MODULE, name) == getattr(protocol, name), name
    for name in ("EXPORT_DIR", "EXPORT_TREE_FILE", "DATABASE_FILE", "LOCK_FILE", "MANIFEST_FILE"):
        assert getattr(CHILD_MODULE, name) == getattr(env, name), name
    assert CHILD_MODULE.CHEAP == backends.CHEAP_FINGERPRINT_FIELDS
    scrubbed = launcher.scrubbed_environment(Path("/a"), Path("/r"))
    assert all(scrubbed[name] == "1" for name in CHILD_MODULE.THREAD_VARIABLES)
    assert Path(scrubbed["NUMBA_CACHE_DIR"]).parent == Path("/r")  # the child's environment root


def test_the_evidence_switches_are_named_only_in_the_child() -> None:
    names = (CHILD_MODULE.S2_DT_INIT_VARIABLE, CHILD_MODULE.BACKFLOW_ALT_VARIABLE)
    assert all(name.startswith("OFS_EVIDENCE_") for name in names)
    mentions = [
        str(path.relative_to(PACKAGE))
        for path in sorted(PACKAGE.rglob("*"))
        if path.is_file() and path != CHILD and path.suffix in (".py", ".json", ".lock", ".md")
        if "OFS_EVIDENCE_" in path.read_text(encoding="utf-8")
    ]
    assert mentions == []
    scrubbed = launcher.scrubbed_environment(Path("/a"), Path("/r"))
    assert not any(name.startswith("OFS_EVIDENCE_") for name in scrubbed)


# -- exits -----------------------------------------------------------------------------------------


def test_every_exit_of_the_child_is_os_exit() -> None:
    tree = ast.parse(CHILD.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            function = node.func
            name = (
                function.attr
                if isinstance(function, ast.Attribute)
                else getattr(function, "id", "")
            )
            owner = getattr(getattr(function, "value", None), "id", None)
            assert not (owner == "sys" and name == "exit"), "sys.exit in the child"
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


def _run_child(
    tmp_path: Path, request: dict[str, Any] | str, *, close: bool
) -> subprocess.CompletedProcess[bytes]:
    root = tmp_path / "environment"
    root.mkdir()
    environment = launcher.scrubbed_environment(tmp_path, root)
    line = request if isinstance(request, str) else json.dumps(request)
    process = subprocess.Popen(
        [sys.executable, "-I", str(CHILD)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=tmp_path,
        env=environment,
    )
    assert process.stdin is not None
    process.stdin.write((line + "\n").encode("utf-8"))
    process.stdin.flush()
    if close:
        process.stdin.close()
    stdout, stderr = process.communicate(timeout=30) if close else (b"", b"")
    if not close:
        process.wait(timeout=30)
        assert process.stderr is not None
        stderr = process.stderr.read()
        process.stdin.close()
    return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)


def test_a_missing_environment_exits_72_with_its_reason(tmp_path: Path) -> None:
    request = {"protocol": 1, "deadline_s": 60.0, "expected": {}, "request_sha256": "0" * 64}
    completed = _run_child(tmp_path, request, close=False)
    assert completed.returncode == protocol.EXIT_ENVIRONMENT_MISMATCH
    assert completed.stderr.decode().startswith("environment_mismatch: no env-manifest.json")
    assert not (tmp_path / "result.json").exists()


def test_an_exception_with_the_lifeline_blocked_exits_1_not_sigabrt(tmp_path: Path) -> None:
    """The lifeline thread is blocked in stdin's read (stdin stays open) when the missing
    `deadline_s` raises: the child must leave through `os._exit(1)`, not die of SIGABRT."""
    completed = _run_child(tmp_path, {"protocol": 1}, close=False)
    assert completed.returncode == 1, completed.stderr.decode()[-2000:]
    assert b"KeyError: 'deadline_s'" in completed.stderr


def test_a_sigint_ends_the_child_by_the_signal_not_sigabrt(tmp_path: Path) -> None:
    import signal
    import time

    root = tmp_path / "environment"
    root.mkdir()
    process = subprocess.Popen(
        [sys.executable, "-I", str(CHILD)],
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=tmp_path,
        env=launcher.scrubbed_environment(tmp_path, root),
    )
    time.sleep(1.0)  # blocked reading the request line, the main guard installed
    process.send_signal(signal.SIGINT)
    process.wait(timeout=30)
    assert process.returncode == -signal.SIGINT
    assert process.stdin is not None and process.stderr is not None
    process.stdin.close()
    process.stderr.close()


# -- the builder ---------------------------------------------------------------------------------


def test_the_export_tree_hash_is_the_same_in_the_builder_and_the_child(tmp_path: Path) -> None:
    root = tmp_path / "export"
    (root / "src" / "reactor").mkdir(parents=True)
    (root / "src" / "reactor" / "a.py").write_text("x = 1\n")
    (root / "data" / "inputs").mkdir(parents=True)
    (root / "data" / "inputs" / "G2 — GHSV sweep.json").write_text("{}")
    (root / "LICENSE").write_bytes(b"MIT\n")
    before = env.tree_sha256(root)
    assert before == CHILD_MODULE.tree_sha256(root)
    (root / env.EXPORT_TREE_FILE).write_text(before + "\n")
    assert env.tree_sha256(root) == before  # the marker is outside its own hash
    (root / "LICENSE").write_bytes(b"MIT.\n")
    assert env.tree_sha256(root) != before


def test_the_merged_database_is_the_probes(tmp_path: Path) -> None:
    columns = ("mu_C1", "k_C1", "sigma", "c_p_C1")
    rows = {
        name: {column: float(i + j) for j, column in enumerate(columns)}
        for i, name in enumerate(("H2", "N2", "NH3"))
    }
    database = {
        "species_properties": {"data": rows},
        "binary_properties": {
            "data": {"H2/N2": {"D": 1.5}, "N2/NH3": {"D": 2.5}, "H2/NH3": {"D": 3.5}}
        },
    }
    overlay = {
        "species_properties": {
            "Ar": {"M": 39.948, "copy_from": {"row": "N2", "columns": ["mu_C1", "k_C1"]}},
            "CH4": {"M": 16.04, "copy_from": {"row": "N2", "columns": ["sigma"]}},
        },
        "binary_properties": {"H2/Ar": {"copy_from": "H2/N2"}, "N2/CH4": {"copy_from": "N2/NH3"}},
    }
    clone_db, overlay_path = tmp_path / "db.json", tmp_path / "overlay.json"
    clone_db.write_text(json.dumps(database))
    overlay_path.write_text(json.dumps(overlay))
    assert env.merged_database(clone_db, overlay_path) == reactor_probe.merged_database(
        clone_db, overlay_path, "N2"
    )


def test_the_lock_pins_every_distribution_by_hash_and_holds_the_probes_versions() -> None:
    lock = env.packaged_lock()
    text = lock.read_text(encoding="utf-8")
    pins = env.locked_versions(text)
    assert pins == CHILD_MODULE.locked_versions(lock)
    for name, version in PROBE["environment"]["packages"].items():
        assert pins[name] == version, name
    assert pins["numba"] == "0.68.0"
    assert "ammonia-synthesis-reactor" not in pins  # the reactor is imported from the export
    blocks = [block for block in text.split("\n") if block and not block.startswith((" ", "#"))]
    assert len(blocks) == len(pins)
    requirement = None
    hashed: dict[str, int] = {}
    for line in text.splitlines():
        if line and not line.startswith((" ", "#")):
            requirement = line.split("==")[0]
            hashed[requirement] = 0
        elif "--hash=sha256:" in line:
            assert requirement is not None
            hashed[requirement] += 1
    assert all(count >= 1 for count in hashed.values()), hashed


@pytest.mark.parametrize(
    ("filename", "kept"),
    [
        ("numpy-2.5.3-cp313-cp313-manylinux_2_27_x86_64.whl", True),
        ("numpy-2.5.3-cp312-cp312-manylinux_2_27_x86_64.whl", False),
        ("six-1.17.0-py2.py3-none-any.whl", True),
        ("pyzmq-27.2.0-cp312-abi3-manylinux_2_28_x86_64.whl", True),
        ("numpy-2.5.3.tar.gz", True),
        ("numpy-2.5.3-cp313-cp313t-win_amd64.whl", True),
    ],
)
def test_the_lock_keeps_the_files_cpython_313_can_install(filename: str, kept: bool) -> None:
    assert env._cpython313(filename) is kept


# -- the registered real variant -----------------------------------------------------------------


def test_the_real_variant_is_registered_from_the_files_it_names() -> None:
    variant = variants.registered_variant(REAL_ID)
    evaluation = variant.evaluation
    lock_sha256 = file_sha256(env.packaged_lock())
    assert evaluation["environment"] == {
        "python": PROBE["environment"]["python"],
        "lock_sha256": lock_sha256,
        "env_id": f"pymrm-6089593-{lock_sha256[:12]}",
    }
    assert evaluation["runner_sha256"] == file_sha256(CHILD)
    reactor = evaluation["reactor"]
    assert reactor["commit"] == reactor_probe.PIN == PROBE["reactor_commit"]
    assert reactor["repository"].endswith(
        "computational-chemical-engineering/ammonia_synthesis_reactor"
    )
    assert (reactor["licence"], reactor["used_by_reference"]) == ("MIT", True)
    assert evaluation["profile"] == CHILD_MODULE.PROFILE
    configuration = evaluation["configuration"]
    assert set(configuration) == set(CHILD_MODULE.CONFIGURATION)
    assert configuration["geometry_case"] == reactor_probe.GEOMETRY_CASE
    assert configuration["num_z"] == PROBE["pinned_num_z"] == 800
    assert configuration["backflow"] == reactor_probe.BACKFLOW_DEFAULT
    assert variant.sweep_ratio == 1.0
    assert dict(variant.execution) == {"timeout_s": 120, "max_retries": 1, "kill_grace_s": 2.0}
    accuracy = variant.accuracy
    assert (accuracy["precision_floor_rel"], accuracy["measured_path_independence_rel"]) == (
        1e-6,
        1.56e-8,
    )


def test_qf5_the_real_variants_flow_bound_is_half_and_twice_the_probes_nominal_flow() -> None:
    """R-232 (design note §3.1, D15), now on the registered variant itself."""
    variant = variants.registered_variant(REAL_ID)
    bound = variant.document["boundary"]["hard_domain"]["tube_flow_mol_s"]
    assert bound == FLOW_BOUND == [0.5 * F_NOM, 2.0 * F_NOM]
    assert variants.hard_domain(variant).tube_flow == (0.5 * F_NOM, 2.0 * F_NOM)
    standin = variants.registered_variant("standin-x025-v1").document["boundary"]
    real = dict(variant.document["boundary"])
    real["hard_domain"] = {**real["hard_domain"], "tube_flow_mol_s": None}
    assert real == standin  # the same boundary block but the bound (§3.1)


def test_the_child_resolves_through_the_packaged_files() -> None:
    program = backends.pinned_program(variants.registered_variant(REAL_ID))
    assert program.script.resolve() == CHILD.resolve()
    assert program.environment_root.name == f"pymrm-6089593-{file_sha256(env.packaged_lock())[:12]}"
    assert os.fspath(program.python).endswith("venv/bin/python")


def test_the_builder_needs_a_clean_clone_at_the_pin(tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    clone.mkdir()

    def git(*arguments: str) -> str:
        return subprocess.run(
            ["git", "-C", str(clone), *arguments], capture_output=True, text=True, check=True
        ).stdout.strip()

    git("init", "-q")
    (clone / "LICENSE").write_text("MIT\n")
    git("add", "LICENSE")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "one")
    head = git("rev-parse", "HEAD")
    env._checked_clone(clone, head)
    with pytest.raises(env.EnvironmentBuildError, match="clean clone at"):
        env._checked_clone(clone, "0" * 40)
    (clone / "LICENSE").write_text("MIT, edited\n")
    with pytest.raises(env.EnvironmentBuildError, match="dirty=True"):
        env._checked_clone(clone, head)


def test_the_builder_refuses_a_pin_it_cannot_meet_before_any_work(tmp_path: Path) -> None:
    variant = variants.registered_variant(REAL_ID)
    overlay = tmp_path / "overlay.json"
    overlay.write_text("{}")
    with pytest.raises(env.EnvironmentBuildError, match="overlay_sha256"):
        env.build(variant, overlay=overlay, base=tmp_path / "external")
    assert not (tmp_path / "external").exists()
    existing = env.environment_root(variant, tmp_path / "other")
    existing.mkdir(parents=True)
    with pytest.raises(env.EnvironmentBuildError, match="exists"):
        env.build(variant, base=tmp_path / "other")
