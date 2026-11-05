"""F0: the corpus identity gate (`scripts/corpus_identity.py`) and its four exit mutations.

Target architecture §3 F0, exit N2. Every mutation is test-only (a monkeypatch or a copy in
`tmp_path`); no committed fixture or module is edited.
"""

from __future__ import annotations

import json
import math
import shutil
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import corpus_identity as gate  # noqa: E402

RUN = ("g8", "SYN-001-nominal")
KEY = "/".join(RUN)


@pytest.fixture(scope="module")
def registered() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(gate.REGISTRY.read_text(encoding="utf-8"))
    return document


@pytest.fixture(scope="module")
def platform() -> str:
    return gate.reference_class()


@pytest.fixture(scope="module")
def full(registered: dict[str, Any], platform: str) -> tuple[dict[str, Any], list[str]]:
    return gate.compare(registered, gate.measure_all(), platform)


def judged(registered: dict[str, Any], measured: dict[str, Any]) -> dict[str, dict[str, Any]]:
    # M4 is judged here whatever the host: the mutations below must move it bitwise, and a
    # state hash that moved on the reference platform moved everywhere it is compared.
    results, _ = gate.compare(registered, measured, registered["reference_platform"], subset=True)
    return results


def test_every_implemented_measure_passes(
    registered: dict[str, Any], full: tuple[dict[str, Any], list[str]], platform: str
) -> None:
    results, log = full
    implemented = {m: r for m, r in results.items() if m not in gate.NOT_IMPLEMENTED}
    assert all(r["status"] in ("PASS", "NOT JUDGED") for r in implemented.values()), log
    assert results["M1"]["n"] == 50 and results["M2"]["n"] == 52 + 9 and results["M9"]["n"] == 35
    assert results["M7"]["n"] == 52 and results["M8"]["n"] == 105
    # M6 counts what carries keys: the 15 runs that key the cache and the 70-entry sample. Off
    # the reference platform the runs' key trails are not judged, so only the sample counts.
    runs = 15 if platform == registered["reference_platform"] else 0
    assert results["M6"]["n"] == runs + 70


def test_the_gate_passes(full: tuple[dict[str, Any], list[str]]) -> None:
    passed, line = gate.summary(full[0])
    assert passed, line


def test_the_runs_cover_every_provider_basis_but_coolprop(registered: dict[str, Any]) -> None:
    """Review finding 2: a run per basis beyond SYN-001 (D20: CoolProp only in M6 and M9)."""
    versions = {v["model_version"] for v in registered["measures"]["M2"].values()}
    bases = {"syn001", "wilson-ig-v2", "iapws95-v1", "pr-c1-v1"}
    assert all(any(f"-{basis}-" in version for version in versions) for basis in bases)
    assert not any("coolprop" in version for version in versions)
    assert [r for s, r in gate.run_corpus() if s in gate.BASIS_CASES] == [
        name for names in gate.BASIS_CASES.values() for name in names
    ]


def test_an_empty_measure_fails_the_gate(registered: dict[str, Any]) -> None:
    """Review note 6: a measure with nothing registered and nothing measured is not 0/0 PASS."""
    empty = {**registered, "measures": {**registered["measures"], "M1": {}}}
    results, log = gate.compare(empty, {"M1": {}}, registered["reference_platform"], subset=True)
    assert results["M1"]["status"] == "FAIL" and results["M1"]["n"] == 0
    assert any("an empty measure fails" in line for line in log)
    assert not gate.summary(results)[0]


def test_record_refuses_off_the_reference_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    """Review note 9: a re-record elsewhere would move where M4 is judged; it is refused before
    anything is measured or written."""
    monkeypatch.setattr(gate, "reference_class", lambda: "elsewhere")
    monkeypatch.setattr(gate, "measure_all", lambda **_: pytest.fail("measured"))
    assert gate.record() == 2


def test_a_not_implemented_measure_fails_the_gate() -> None:
    passed, line = gate.summary(
        {"M1": {"status": "PASS", "n": 1}, "M7": {"status": "NOT IMPLEMENTED"}}
    )
    assert not passed and "M7 NOT IMPLEMENTED" in line


def test_the_registry_holds_no_hollow_entry(registered: dict[str, Any]) -> None:
    """Every registered replay matches with its archive intact (RC step 5's rule), and every
    registered round-trip node passed: a registered failure or skip would be a vacuous identity."""
    replays = registered["measures"]["M7"].values()
    assert all(r["verdict"] == "MATCH" and r["integrity_ok"] for r in replays)
    assert all(r["mode"] in ("exact_replay", "compatible_reproduction") for r in replays)
    assert set(registered["measures"]["M8"].values()) == {"passed"}
    assert not gate.NOT_IMPLEMENTED


def test_the_guards_exempt_only_the_registered_archived_outputs(registered: dict[str, Any]) -> None:
    """Ruling D15 (R-939): exactly 36 files, each the `artifacts/solve-policy.json` of a bundle
    the 0.3.0 index names, registered as `--record` writes them and matching their bytes."""
    from f0_support import N_ARCHIVED_OUTPUTS, archived_outputs, is_archived_output

    exempt = registered["archived_outputs"]
    assert exempt == archived_outputs() == gate.archived_outputs()
    assert len(exempt) == N_ARCHIVED_OUTPUTS == 36
    index = json.loads((gate.V030_BUNDLES / "index.json").read_text(encoding="utf-8"))
    indexed = {
        (gate.V030_BUNDLES / e["directory"] / "artifacts" / "solve-policy.json")
        .relative_to(ROOT)
        .as_posix()
        for e in index["entries"]
    }
    assert set(exempt) <= indexed
    assert all(is_archived_output(ROOT / path) for path in exempt)


def test_an_archived_output_with_one_changed_byte_is_not_exempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import f0_support

    path = next(iter(f0_support.archived_outputs()))
    original = (ROOT / path).read_bytes()
    copy = tmp_path / path
    copy.parent.mkdir(parents=True)
    monkeypatch.setattr(f0_support, "REPO_ROOT", tmp_path)
    copy.write_bytes(original)
    assert f0_support.is_archived_output(copy)
    copy.write_bytes(original[:-1] + bytes([original[-1] ^ 0x01]))
    assert not f0_support.is_archived_output(copy)
    assert not f0_support.is_archived_output(tmp_path / "benchmarks" / "elsewhere.json")


def test_m7_one_byte_in_a_0_3_0_bundle_fails_m7(registered: dict[str, Any], tmp_path: Path) -> None:
    source = gate.V030_BUNDLES
    index = json.loads((source / "index.json").read_text(encoding="utf-8"))
    entry = next(e for e in index["entries"] if (e["set"], e["name"]) == RUN)
    shutil.copytree(source / entry["directory"], tmp_path / entry["directory"])
    (tmp_path / "index.json").write_text(json.dumps({**index, "entries": [entry]}))
    target = tmp_path / entry["directory"] / "artifacts" / "solution-certificate.json"
    data = bytearray(target.read_bytes())
    at = next(i for i in range(len(data) // 2, len(data)) if chr(data[i]).isdigit())
    data[at] = ord("1") if data[at] != ord("1") else ord("2")  # one digit: still valid JSON
    target.write_bytes(bytes(data))
    measured = gate.m7(tmp_path)
    assert list(measured) == [KEY] and measured[KEY]["integrity_ok"] is False
    assert judged(registered, {"M7": measured})["M7"]["wrong"] == [KEY]


def test_m7_judges_the_mode_only_on_the_reference_platform(registered: dict[str, Any]) -> None:
    measured = json.loads(json.dumps(registered["measures"]))
    measured["M7"][KEY]["mode"] = "compatible_reproduction"
    elsewhere, log = gate.compare(registered, measured, "elsewhere")
    assert elsewhere["M7"]["status"] == "PASS" and any("mode not judged" in x for x in log)
    here, _ = gate.compare(registered, measured, registered["reference_platform"])
    assert here["M7"]["status"] == "FAIL" and here["M7"]["wrong"] == [KEY]
    measured["M7"][KEY]["verdict"] = "MISMATCH"
    assert gate.compare(registered, measured, "elsewhere")[0]["M7"]["wrong"] == [KEY]


def test_m8_a_removed_round_trip_node_fails_m8_by_name(registered: dict[str, Any]) -> None:
    measured = json.loads(json.dumps(registered["measures"]))
    node = sorted(measured["M8"])[0]
    del measured["M8"][node]
    results, log = gate.compare(registered, measured, registered["reference_platform"])
    assert results["M8"]["status"] == "FAIL" and f"M8: {node}: registered, not measured" in log
    assert all(r["status"] == "PASS" for m, r in results.items() if m != "M8")


def test_m8_runs_the_registered_nodes_in_a_fresh_interpreter(registered: dict[str, Any]) -> None:
    function = "tests/test_k05_schemas.py::test_the_fixtures_validate_and_round_trip"
    measured = gate.m8([function])
    assert measured and all(node.startswith(function + "[") for node in measured)
    assert judged(registered, {"M8": measured})["M8"]["status"] == "PASS"


def _mappings(node: Any) -> Iterator[dict[str, Any]]:
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _mappings(value)
    elif isinstance(node, list):
        for value in node:
            yield from _mappings(value)


def _one_ulp_split_fraction(document: dict[str, Any]) -> float:
    """SYN-001's split fraction r, one ulp up, in the instance and in the fixed specification
    that pins it (SPEC-splitter-r); moving one without the other is a specification conflict."""
    pinned = [
        m
        for m in _mappings(document)
        if isinstance(m.get("target"), dict)
        and m["target"].get("object_id") == "splitter"
        and m["target"].get("path") == "parameters.split_fraction"
    ]
    splitter = next(m for m in _mappings(document) if m.get("id") == "splitter")
    parameter = splitter["parameters"]["split_fraction"]
    assert len(pinned) == 1 and pinned[0]["value"] == parameter["value"] == 0.5
    moved = math.nextafter(parameter["value"], math.inf)
    parameter["value"] = pinned[0]["value"] = moved
    return moved


def test_m6_the_request_sample_recomputes_without_solving(registered: dict[str, Any]) -> None:
    """Review finding 1: the sample's keys are a function of committed inputs, the providers'
    `describe()` and the key code, so they are recomputed and judged on every platform."""
    sample = gate.m6_sample()
    assert len(sample) == 70 and all(k.startswith(gate.M6_SAMPLE_PREFIX) for k in sample)
    providers = {k.split("/")[2] for k in sample if k.startswith("sample/provider/")}
    assert providers == {p for p, _ in gate.M6_PROVIDERS} and len(providers) == 5
    assert judged(registered, {"M6": sample})["M6"]["status"] == "PASS"


def test_m6_judges_the_run_trails_only_on_the_reference_platform(
    registered: dict[str, Any], tmp_path: Path
) -> None:
    measured = json.loads(json.dumps(registered["measures"]))
    trail = "k05/SYN-001-nominal"
    measured["M6"][trail]["keys_sha256"] = "0" * 64
    elsewhere, log = gate.compare(registered, measured, "elsewhere")
    assert elsewhere["M6"]["status"] == "PASS" and elsewhere["M6"]["n"] == 70
    assert any("key trails (iterate states) are not judged" in line for line in log)
    here, _ = gate.compare(registered, measured, registered["reference_platform"])
    assert here["M6"]["status"] == "FAIL" and here["M6"]["wrong"] == [trail]
    # One ulp in one committed sample state moves its key, and that fails on every platform.
    document = json.loads(gate.M6_SAMPLE.read_text(encoding="utf-8"))
    name = sorted(document["entries"])[0]
    state = document["entries"][name]["state"]
    state["temperature"] = math.nextafter(state["temperature"], math.inf)
    copy = tmp_path / "m6-requests.json"
    copy.write_text(json.dumps(document), encoding="utf-8")
    moved = gate.m6_sample(copy)
    elsewhere, _ = gate.compare(registered, {**measured, "M6": moved}, "elsewhere")
    assert elsewhere["M6"]["wrong"] == [gate.M6_SAMPLE_PREFIX + name]


def test_exit_2_one_ulp_in_a_registered_parameter_moves_m2_m3_m4(
    registered: dict[str, Any], platform: str
) -> None:
    """With an unmutated control (review note 7): the run as registered passes M2, M3 (and M4 on
    the reference platform); one ulp fails M2 and M3 everywhere, fails M4 on the reference
    platform, and moves the state trail against the control on any platform."""
    from t07_corpus import CORPUS

    def statuses(measured: dict[str, Any]) -> dict[str, str]:
        results, _ = gate.compare(
            registered, {m: {KEY: measured[m]} for m in ("M2", "M3", "M4")}, platform, subset=True
        )
        return {m: r["status"] for m, r in results.items()}

    reference = platform == registered["reference_platform"]
    control = gate.runs([RUN])[KEY]
    assert statuses(control) == {
        "M2": "PASS",
        "M3": "PASS",
        "M4": "PASS" if reference else "NOT JUDGED",
    }
    document = CORPUS[RUN[1]]()
    assert _one_ulp_split_fraction(document) == 0.5 + 2.0**-53
    measured = gate.runs([RUN], {RUN[1]: document})[KEY]
    assert statuses(measured) == {
        "M2": "FAIL",
        "M3": "FAIL",
        "M4": "FAIL" if reference else "NOT JUDGED",
    }
    assert measured["M4"]["state_trail_sha256"] != control["M4"]["state_trail_sha256"]
    expected = registered["measures"]["M2"][KEY]
    assert measured["M2"]["model_version"] == expected["model_version"]
    assert measured["M2"]["constants_sha256"] != expected["constants_sha256"]


def test_exit_3_one_flipped_check_result_fails_m5(
    registered: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    read = gate.artifacts

    def flipped(directory: Path) -> tuple[Any, dict[str, Any]]:
        manifest, documents = read(directory)
        check = documents["solution-certificate.json"]["checks"][0]
        check["result"] = "fail" if check["result"] == "pass" else "pass"
        return manifest, documents

    unmutated = gate.runs([RUN])[KEY]
    assert judged(registered, {"M5": {KEY: unmutated["M5"]}})["M5"]["status"] == "PASS"
    monkeypatch.setattr(gate, "artifacts", flipped)
    measured = gate.runs([RUN])[KEY]
    assert judged(registered, {"M5": {KEY: measured["M5"]}})["M5"]["status"] == "FAIL"


@pytest.mark.parametrize("family", ["src/openflowsheet/models/", "src/openflowsheet/thermo/"])
def test_exit_4_one_byte_in_a_frozen_module_fails_m9_by_name(
    registered: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, family: str
) -> None:
    """One byte of the module docstring (the file stays valid Python), in the first registered
    legacy unit module and the first registered provider module."""
    shutil.copytree(ROOT / "src", tmp_path / "src", symlinks=True)
    name = next(n for n in sorted(registered["measures"]["M9"]) if n.startswith(family))
    target = tmp_path / name
    data = bytearray(target.read_bytes())
    at = next(i for i in range(3, len(data)) if chr(data[i]).isalpha())
    data[at] ^= 0x20  # the letter's case
    target.write_bytes(bytes(data))
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    results, log = gate.compare(registered, {"M9": gate.m9()}, "", subset=True)
    assert results["M9"]["status"] == "FAIL" and results["M9"]["wrong"] == [name]
    assert any(line.startswith(f"M9: {name}:") for line in log)


def test_m9_enumerates_from_the_hash_sites_not_by_hand() -> None:
    modules = gate.identity_bearing_modules()
    assert "src/openflowsheet/thermo/wilson_ig.py" in modules
    assert "src/openflowsheet/thermo/_coolprop_heos_fluids.py" in modules


def test_m9_follows_a_composed_identity_into_the_imported_module() -> None:
    """§2.4.4 "or one imported into such a hash set": wilson_ig_v2 hashes its own bytes and v1's
    `implementation_sha256`, so wilson_ig.py enters M9 through v2's site, not only its own."""
    import ast

    module = gate.ROOT / "src/openflowsheet/thermo/wilson_ig_v2.py"
    hashed = gate._hashed_files(module, ast.parse(module.read_text(encoding="utf-8")))
    assert hashed == {module, module.parent / "wilson_ig.py"}


def test_m9_a_composition_it_cannot_resolve_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = tmp_path / "src" / "openflowsheet" / "thermo"
    package.mkdir(parents=True)
    (package / "base.py").write_text(
        "import hashlib\nfrom pathlib import Path\n\n\n"
        "def _implementation_sha256() -> str:\n"
        "    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()\n"
    )
    (package / "plain.py").write_text("X = 1\n")
    composed = (
        "import hashlib\nfrom pathlib import Path\nfrom openflowsheet.thermo.{} import {}\n\n\n"
        "class P:\n    def __init__(self, v1):\n"
        "        self._implementation_sha256 = hashlib.sha256(\n"
        "            Path(__file__).read_bytes() + v1.describe().implementation_sha256.encode()\n"
        "        ).hexdigest()\n"
    )
    (package / "composed.py").write_text(composed.format("base", "_implementation_sha256"))
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    assert gate.identity_bearing_modules() == [
        "src/openflowsheet/thermo/base.py",
        "src/openflowsheet/thermo/composed.py",
    ]
    (package / "composed.py").write_text(composed.format("plain", "X"))
    with pytest.raises(ValueError, match="composed implementation_sha256 is not resolved"):
        gate.identity_bearing_modules()


def test_m9_a_hash_scope_read_by_an_unknown_idiom_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review finding 3: a scope that reads its bytes by an idiom the scan does not know adds no
    file; it raises instead of narrowing the set silently."""
    package = tmp_path / "src" / "openflowsheet" / "thermo"
    package.mkdir(parents=True)
    (package / "odd.py").write_text(
        "import hashlib\n\n\n"
        "def _implementation_sha256() -> str:\n"
        "    with open(__spec__.origin, 'rb') as handle:\n"
        "        return hashlib.sha256(handle.read()).hexdigest()\n"
    )
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="a hash scope resolves to no file"):
        gate.identity_bearing_modules()


def _manifest_modules() -> set[str]:
    """The distinct `module=` values of the model manifests under `models/`: `__name__` is the
    calling module, a string literal names one; a pass-through parameter adds none."""
    import ast

    modules: set[str] = set()
    for path in sorted((gate.ROOT / "src" / "openflowsheet" / "models").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.keyword) and node.arg == "module":
                if isinstance(node.value, ast.Name) and node.value.id == "__name__":
                    modules.add(path.relative_to(gate.ROOT).as_posix())
                elif isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    dotted = node.value.value.split(".")
                    modules.add(Path("src", *dotted).with_suffix(".py").as_posix())
    return modules


def test_m9_holds_every_legacy_unit_module_d9() -> None:
    """Ruling D9 (R-940), the AST fallback's cross-checks: the legacy set is the set of distinct
    manifest modules; each declares a `MODEL_BUILDERS` id and every bindable id but M04's
    surrogate is declared by one; a zero-argument `_artifact_hash()` is its own file's SHA-256."""
    import importlib
    import inspect

    from openflowsheet.application.revision_binding import MODEL_BUILDERS

    legacy = gate.legacy_unit_modules()
    assert len(legacy) == 27 and set(legacy) == _manifest_modules()
    assert set(legacy) <= set(gate.frozen_modules()) and len(gate.frozen_modules()) == 35
    declared: set[str] = set()
    for name in legacy:
        module = importlib.import_module(
            Path(name).with_suffix("").as_posix()[4:].replace("/", ".")
        )
        ids = {getattr(module, "MODEL_ID", None), *getattr(module, "MODEL_IDS", ())} - {None}
        assert ids & set(MODEL_BUILDERS), name
        declared |= ids
        hasher = inspect.unwrap(getattr(module, "_artifact_hash", lambda path: path))
        if not inspect.signature(hasher).parameters:
            assert hasher() == gate.sha256((gate.ROOT / name).read_bytes()), name
    assert set(MODEL_BUILDERS) - declared == {"c1.reactor_surrogate"}


def test_m9_an_unknown_artifact_hash_idiom_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    models = tmp_path / "src" / "openflowsheet" / "models" / "family"
    models.mkdir(parents=True)
    (models / "unit.py").write_text("M = dict(artifact_hash='0' * 64)\n")
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="artifact_hash is not resolved"):
        gate.legacy_unit_modules()
    (models / "unit.py").write_text(
        "def _artifact_hash(path):\n    return path\n\n\n"
        "M = dict(artifact_hash=_artifact_hash('x'))\n"
    )
    with pytest.raises(ValueError, match="a forwarding _artifact_hash has no caller"):
        gate.legacy_unit_modules()
    (models / "other.py").write_text(
        "from openflowsheet.models.family.unit import build\n\n\nX = build(path=__file__)\n"
    )
    assert gate.legacy_unit_modules() == ["src/openflowsheet/models/family/other.py"]


def test_importing_the_gate_leaves_the_thread_variables_alone() -> None:
    """Review finding 5: only `main()` pins the BLAS/OpenMP threads, never the import."""
    import os
    import subprocess

    environment = {k: v for k, v in os.environ.items() if k not in gate.THREAD_VARIABLES} | {
        "PYTHONPATH": os.pathsep.join([str(ROOT / "src"), str(ROOT / "scripts")])
    }
    probe = (
        "import os, corpus_identity as g; print([os.environ.get(n) for n in g.THREAD_VARIABLES])"
    )
    shown = subprocess.run(
        [sys.executable, "-c", probe], env=environment, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert shown == "[None, None, None]"
    before = [os.environ.get(n) for n in gate.THREAD_VARIABLES]
    with gate.pinned_threads():
        assert [os.environ[n] for n in gate.THREAD_VARIABLES] == ["1", "1", "1"]
    assert [os.environ.get(n) for n in gate.THREAD_VARIABLES] == before
