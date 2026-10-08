"""M03 WO-6: the [A10] audit of the optional NLP path's Ipopt distribution (specification §9).

Two kinds of test, both in the default gate and neither needing the audited environment:

- **G6, the default install is unchanged:** importing `openflowsheet` and every module the default
  gate imports loads neither Pyomo nor cyipopt, and `pyproject.toml` names them only in an `nlp`
  extra. The adapter module of WO-8 (`openflowsheet.studies.nlp.greybox`) is the one module allowed
  to import them, and is the one module not walked here; its tests are marked `nlp` and deselected.
- **A41's committed half:** the audit document and its inventory exist, record every gate item,
  and the inventory was taken from exactly the committed locks. That the inventory reproduces is
  `scripts/m03_ipopt_inventory.py --check`, run in the audited environment.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tomllib

from conftest import REPO_ROOT

NLP_LIBRARIES = ("pyomo", "cyipopt", "ipopt_wrapper")
NLP_ADAPTER_MODULES = (
    "openflowsheet.studies.nlp.greybox",
    # M05 (ADR 0038 D2, D4): the trust-region projection and runner, the two other modules
    # allowed to import Pyomo; tests/test_m05_isolation.py checks the allow-list itself.
    "openflowsheet.studies.trust_region.projection",
    "openflowsheet.studies.trust_region.trf",
)
#: The binding modules that need the `server` extra. Where that extra is absent (the CI
#: `default-install` job) exactly these are skipped; any other import failure fails the test, and
#: where the extra is installed they are walked like every other module.
SERVER_BINDINGS = tuple(
    f"openflowsheet.application.bindings.{name}" for name in ("http", "mcp", "web")
)
AUDIT = REPO_ROOT / "docs" / "m03-ipopt-audit.md"
INVENTORY = REPO_ROOT / "benchmarks" / "m03" / "ipopt-inventory-x86_64.json"
MEASUREMENTS = REPO_ROOT / "benchmarks" / "m03" / "nlp-measurements.json"
LOCKS = {
    "conda": REPO_ROOT / "benchmarks" / "m03" / "nlp-conda-explicit.txt",
    "pip": REPO_ROOT / "benchmarks" / "m03" / "nlp-pip.lock",
    "build": REPO_ROOT / "benchmarks" / "m03" / "nlp-build-conda-explicit.txt",
}


def test_the_default_modules_import_no_nlp_library() -> None:
    """G6: every `openflowsheet` module but the NLP adapter imports, in a fresh interpreter,
    without loading Pyomo or cyipopt."""
    probe = (
        "import importlib, json, pkgutil, sys\n"
        "import openflowsheet\n"
        f"skip = {NLP_ADAPTER_MODULES!r}\n"
        "import importlib.util\n"
        "server_absent = importlib.util.find_spec('starlette') is None\n"
        f"server_bindings = {SERVER_BINDINGS!r}\n"
        "walked = []\n"
        "for module in pkgutil.walk_packages(\n"
        "    openflowsheet.__path__, 'openflowsheet.', onerror=lambda name: None\n"
        "):\n"
        "    if module.name.startswith(skip):\n"
        "        continue\n"
        "    if server_absent and module.name in server_bindings:\n"
        "        continue\n"
        "    importlib.import_module(module.name)\n"
        "    walked.append(module.name)\n"
        f"loaded = sorted(m for m in sys.modules if m.split('.')[0] in {NLP_LIBRARIES!r})\n"
        "print(json.dumps({'walked': len(walked), 'loaded': loaded}))"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True, cwd=REPO_ROOT
    )
    outcome = json.loads(result.stdout.strip().splitlines()[-1])
    assert outcome["walked"] > 50
    assert outcome["loaded"] == []


def test_pyomo_and_cyipopt_are_named_only_in_an_nlp_extra() -> None:
    """G6: the default requirements and every other extra name neither library."""
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        project = tomllib.load(handle)["project"]
    groups = {"dependencies": project["dependencies"]} | {
        f"extra {name}": texts for name, texts in project["optional-dependencies"].items()
    }
    naming = {
        group: [text for text in texts if re.match(r"\s*(pyomo|cyipopt)\b", text, re.I)]
        for group, texts in groups.items()
    }
    assert {group for group, texts in naming.items() if texts} <= {"extra nlp"}


def test_the_audit_records_every_gate_item_and_a_verdict() -> None:
    """A41: G1-G8 each with an outcome, and the verdict PASS or FAIL."""
    text = AUDIT.read_text(encoding="utf-8")
    for item in range(1, 9):
        assert re.search(rf"^\| G{item} \|.*\*\*(PASS|FAIL|BLOCKED)\*\*", text, re.M), f"G{item}"
    assert re.search(r"^\*\*Verdict: (PASS|FAIL)\*\*", text, re.M)


def test_the_inventory_was_taken_from_the_committed_locks() -> None:
    """A41/G7: the committed inventory names the hashes of exactly the committed lock files, and
    records G1-G6 as measured."""
    record = json.loads(INVENTORY.read_text(encoding="utf-8"))
    assert record["format"] == "m03-ipopt-inventory-v1"
    assert record["locks"] == {
        name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in LOCKS.items()
    }
    assert set(record["gates"]) == {"G1", "G2", "G3", "G4", "G5", "G6"}
    assert all(isinstance(gate["pass"], bool) for gate in record["gates"].values())


# -- WO-8: what the default gate can check of the audited path ----------------------------------


def test_the_adapter_requires_the_audited_pynumero_asl_build() -> None:
    """Audit §9 item 2: the SHA-256 the adapter checks before any solve is the inventory's."""
    from openflowsheet.studies.nlp.closure import AUDITED_PYNUMERO_ASL_SHA256

    record = json.loads(INVENTORY.read_text(encoding="utf-8"))
    (row,) = [o for o in record["objects"] if o["path"].endswith("/libpynumero_ASL.so")]
    assert row["sha256"] == record["pynumero_asl_build"]["sha256"] == AUDITED_PYNUMERO_ASL_SHA256


def test_the_inventory_was_taken_on_nlp_1() -> None:
    """Audit §9 item 1: G1 re-measured with NLP-1 solved by the adapter, in both import orders."""
    record = json.loads(INVENTORY.read_text(encoding="utf-8"))
    for run in record["workload"].values():
        assert run["workload"] == "nlp-1"
        assert run["termination"] == "KKT_POINT_VERIFIED"
        assert run["nlpsol_calls"] == []
    assert record["pass_g1_to_g6"] is True


def test_the_q_f2_measurements_keep_a_tenfold_margin() -> None:
    """Spec §14 Q-F2, as recorded by `scripts/m03_nlp_measurements.py` in the audited environment
    (whose `nlp` test checks that the record reproduces): no measured value of NLP-1 within 10x of
    the tolerance A35/A36 register for it."""
    record = json.loads(MEASUREMENTS.read_text(encoding="utf-8"))
    assert record["format"] == "m03-nlp-measurements-v1"
    assert record["environment"]["omp_num_threads"] == "1"
    q_f2 = record["q_f2"]
    assert len(q_f2["starts"]) == 3
    assert q_f2["within_margin_factor"] == []
    assert q_f2["closest"]["ratio"] >= q_f2["margin_factor"] == 10.0
    for start in q_f2["starts"]:
        assert start["ipopt_status"] == 0
        for name, item in start["measured"].items():
            assert item["ratio"] is None or item["ratio"] >= 10.0, name


def test_the_nlp_tests_are_deselected_not_skipped_in_the_default_gate() -> None:
    """ADR 0032 C2: collected, every test of the adapter module is marked `nlp` and the default
    configuration deselects all of them; none is skipped."""
    module = "tests/test_m03_nlp_greybox.py"

    def collect(*options: str) -> str:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"]
            + list(options)
            + [module],
            capture_output=True,
            text=True,
            check=False,
            cwd=REPO_ROOT,
        )
        return result.stdout

    marked = collect("-m", "nlp")
    selected = [line for line in marked.splitlines() if line.startswith(module + "::")]
    assert len(selected) >= 17
    assert f"no tests collected ({len(selected)} deselected)" in collect()
    assert "skipped" not in marked


# -- M05 WO-1: the Ipopt executable's record (audit section 11) ---------------------------------

TRSP_INVENTORY = REPO_ROOT / "benchmarks" / "m05" / "trsp-inventory-x86_64.json"
#: The two objects the executable adds to M03's inventory; both are conda-forge ipopt-3.14.20 files.
TRSP_NEW_OBJECTS = {"$ENV/bin/ipopt", "$ENV/lib/libipoptamplinterface.so.3.14.20"}


def test_the_trsp_inventory_was_taken_from_the_committed_locks_and_passes_g1_to_g6() -> None:
    """M05 WO-1 / G1: the executable's record names the committed locks' hashes, carries G1-G6 as
    measured, and passes all six."""
    record = json.loads(TRSP_INVENTORY.read_text(encoding="utf-8"))
    assert record["format"] == "m05-trsp-inventory-v1"
    assert record["locks"] == {
        name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in LOCKS.items()
    }
    assert set(record["gates"]) == {"G1", "G2", "G3", "G4", "G5", "G6"}
    assert all(gate["pass"] is True for gate in record["gates"].values())
    assert record["pass_g1_to_g6"] is True


def test_the_trsp_workload_ran_the_executable_and_the_loader_agrees_with_ldd() -> None:
    """The record is of the executable, not of the Python process: Ipopt's banner names MUMPS, the
    loader's log equals ldd's closure, every spawned process maps one set, and neither CasADi nor
    cyipopt was loaded."""
    record = json.loads(TRSP_INVENTORY.read_text(encoding="utf-8"))
    run = record["workload"]["executable"]
    assert run["direct"]["termination"] == "optimal"
    assert run["executable_pinned"] == run["executable_resolved_on_path"] == "$ENV/bin/ipopt"
    assert run["casadi_imported"] is False
    assert run["cyipopt_imported"] is False
    assert run["nlpsol_calls"] == []
    assert run["processes"] >= 2
    assert run["each_process_maps_the_same_objects"] is True
    assert run["loader_equals_ldd_closure"] is True
    assert run["loader_minus_ldd"] == run["ldd_minus_loader"] == []
    for banner in (run["direct"]["banner"], run["trf_example1"]["banner"]):
        assert len(banner) == 1
        assert "running with linear solver MUMPS" in banner[0]
    assert run["dlopen_attempts"].keys() <= {"libarcher.so", "libmemkind.so"}
    assert set(run["trf_modules"]) == {
        "TRF.py",
        "interface.py",
        "filter.py",
        "funnel.py",
        "util.py",
    }
    assert all(re.fullmatch(r"[0-9a-f]{64}", digest) for digest in run["trf_modules"].values())


def test_the_trsp_objects_are_m03s_plus_two_and_none_is_unresolved_or_forbidden() -> None:
    """The executable adds exactly `bin/ipopt` and `libipoptamplinterface` to M03's inventory (the
    rest are the same paths with the same SHA-256), each with owner and licence; `libgomp.so.1` is
    the LLVM OpenMP object already inventoried; no CasADi METIS-closure, HSL or unresolved
    object."""
    record = json.loads(TRSP_INVENTORY.read_text(encoding="utf-8"))
    m03 = {o["path"]: o for o in json.loads(INVENTORY.read_text(encoding="utf-8"))["objects"]}
    objects = {o["path"]: o for o in record["objects"]}
    assert set(objects) - set(m03) == TRSP_NEW_OBJECTS
    for path in set(objects) & set(m03):
        assert objects[path]["sha256"] == m03[path]["sha256"], path
    for path in TRSP_NEW_OBJECTS:
        row = objects[path]
        assert re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) and row["bytes"] > 0
        assert row["origin"] == "conda-forge: ipopt-3.14.20-hec1326d_0"
        assert row["licence"]["category"] == "identified"
        assert row["licence"]["notices"]
    run = record["workload"]["executable"]
    assert run["loaded_through_a_symlink"]["libgomp.so.1"] == ["$ENV/lib/libomp.so"]
    assert objects["$ENV/lib/libomp.so"]["licence"]["declared"] == "Apache-2.0 WITH LLVM-exception"
    assert not any(o["licence"]["category"] == "unresolved" for o in objects.values())
    assert not any("/casadi/" in path or "hsl" in path.lower() for path in objects)
    assert record["gates"]["G2"]["casadi_metis_closure_mapped"] == []
    assert record["gates"]["G4"]["hsl_symbol_exporters"] == []
    assert [c["conclusion"] for c in record["gates"]["G3"]["carriers"]] == ["METIS 5.x"]


def test_the_audit_has_a_section_for_the_executable_with_every_gate() -> None:
    """Audit section 11: G1-G8 each with an outcome for the executable, and a verdict."""
    text = AUDIT.read_text(encoding="utf-8")
    assert "## 11. The Ipopt executable (M05 WO-1)" in text
    section = text.split("## 11. The Ipopt executable (M05 WO-1)", 1)[1]
    for item in range(1, 9):
        assert re.search(rf"^\| G{item} \|.*\*\*(PASS|FAIL|BLOCKED)\*\*", section, re.M), f"G{item}"
    assert re.search(r"^\*\*Verdict: (PASS|FAIL)\*\* ", section, re.M)
    record = json.loads(TRSP_INVENTORY.read_text(encoding="utf-8"))
    run = record["workload"]["executable"]
    assert run["executable"] in section
    for digest in run["trf_modules"].values():
        assert digest[:8] in section
