"""F0: the corpus identity gate (roadmap 0.4, ADR 0057 D3; target architecture §3 F0).

`--check` recomputes every measure over the registered corpus (`benchmarks/f0/corpus.json`),
compares it with the registered values, prints **one** summary line and writes the full log.
Exit 0 only when every measure is judged and equal. A measure that is not implemented is
reported `NOT IMPLEMENTED` and makes the gate FAIL; it is never counted as passing.

| Measure | What is compared | Corpus |
| --- | --- | --- |
| M1 | `content_hash` of each repository revision | T07's revision corpus (`tests/t07_corpus.py`) |
| M2 | `model_version`, `constants_sha256` of each compiled problem | the RC bundle set (below) |
| M3 | `artifact_r0_sha256` of each registered run | the RC bundle set |
| M4 | every `state_sha256` in the artifacts, bitwise (reference platform) | the RC bundle set |
| M5 | outcome, verification status and every check's (id, result) | the RC bundle set |
| M6 | exact-cache keys of a committed request sample; run key trails (ref.) | `m6-requests.json` |
| M7 | replay verdict, mode and integrity of each 0.3.0 bundle | the RC set written at v0.3.0 |
| M8 | outcome of each schema round-trip test node | `M8_FUNCTIONS` (below) |
| M9 | SHA-256 of each file feeding an `implementation_sha256` or `artifact_hash` | AST scan |

The RC bundle set is RC step 4's (`scripts/t08_rc.py bundles-write`): the K05 SYN-001 variants
solved through the CLI and T07 W3a's eligible revisions under the default policy. F0 wraps those
enumerations; it does not keep its own copy of them. M7 replays the same set as RC step 5 does
(`bundles-replay`), from the bundles written at tag v0.3.0 (`tests/fixtures/f0/v0.3.0-bundles`).
M8 runs the schema round-trip tests in a subprocess, as RC step 7 runs its corpus, and registers
every node id, so a removed case is a diff.

    PYTHONPATH=src .venv/bin/python scripts/corpus_identity.py --check [--log PATH]
    PYTHONPATH=src .venv/bin/python scripts/corpus_identity.py --record   # writes the registry
"""

from __future__ import annotations

import os

# Before numpy is imported anywhere: the runs are recorded single-threaded (RC step 4).
for _name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_name] = "1"

import argparse  # noqa: E402
import ast  # noqa: E402
import contextlib  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
from collections.abc import Callable, Iterator, Mapping, Sequence  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Final  # noqa: E402

ROOT: Final = Path(__file__).resolve().parent.parent
REGISTRY: Final = ROOT / "benchmarks" / "f0" / "corpus.json"
FORMAT: Final = "f0-corpus-identity-v1"
MEASURES: Final = ("M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "M9")
#: Measures not implemented yet, with the reason; each is reported, and fails the gate.
NOT_IMPLEMENTED: Final[dict[str, str]] = {}
STATE_KEYS: Final = ("state_sha256", "target_state_sha256")
V030_BUNDLES: Final = ROOT / "tests" / "fixtures" / "f0" / "v0.3.0-bundles"
#: Ruling D15 (R-939): the policies whose archived `solve-policy.json` records in the 0.3.0
#: bundles are registered as archived outputs, by path and SHA-256, and so exempt from the three
#: guards that keep this policy's values out of input documents (`tests/f0_support.py`). The other
#: records (`T04-W12`) carry none of those values and are not registered.
ARCHIVED_POLICIES: Final = ("T06-revision-v2",)
#: M6's committed request sample (review finding 1): keys recomputed without solving.
M6_SAMPLE: Final = ROOT / "benchmarks" / "f0" / "m6-requests.json"
M6_FIRST: Final = 3
#: One sample per registered provider basis (`basis_provider`), by id and component order.
M6_PROVIDERS: Final[tuple[tuple[str, tuple[str, ...]], ...]] = (
    ("syn001", ("A", "B", "C")),
    ("pr-c1-v1", ("H2", "N2", "NH3", "Ar", "CH4")),
    ("iapws95-v1", ("H2O",)),
    ("wilson-ig-v2", ("CH3OH", "C2H5OH", "H2O")),
    ("coolprop-heos-v1", ("R134a",)),
)
#: M6's registry keys of the sample start with this; the others are the runs' key trails.
M6_SAMPLE_PREFIX: Final = "sample/"
#: M7's fields judged off the reference platform: the replay mode is decided by the platform
#: identity (`run.replay.decide_mode`), so elsewhere only the verdict and the integrity are.
M7_PORTABLE: Final = ("verdict", "integrity_ok")
#: M8: the test functions that validate a document against its schema and round-trip it
#: (docs/F0_DECISIONS.md D4, D13). Every node they collect is registered.
M8_FUNCTIONS: Final = (
    "tests/test_schemas_p01.py::test_valid_fixture_round_trips_through_json",
    "tests/test_schemas_p01.py::test_component_record_round_trips",
    "tests/test_k01_schemas.py::test_a_valid_fixture_round_trips_through_json_and_through_the_dataclass",
    "tests/test_k03_schemas.py::test_the_fixtures_validate_and_round_trip",
    "tests/test_k04_schemas.py::test_a31_the_fixtures_validate_and_round_trip",
    "tests/test_k05_schemas.py::test_the_fixtures_validate_and_round_trip",
    "tests/test_t04_schemas.py::test_a26_the_t04_fixtures_validate_and_round_trip",
    "tests/test_t07_types.py::test_each_typed_document_round_trips_through_its_schema",
    "tests/test_t07_w1f_followup.py::test_a_job_result_round_trips_through_its_schema",
    "tests/test_t07_w3e_solution_state.py::test_the_fixture_validates_round_trips_and_is_consistent",
)
#: M8's subprocess: RC step 7's recorder (`t08_rc._Recorder`), every node's worst outcome.
M8_DRIVER: Final = """
import json, sys
import pytest
sys.path.insert(0, "scripts")
from t08_rc import _Recorder
recorder = _Recorder()
pytest.main(["-q", "-p", "no:cacheprovider", *sys.argv[2:]], plugins=[recorder])
with open(sys.argv[1], "w", encoding="utf-8") as out:
    json.dump(recorder.outcomes, out, sort_keys=True)
"""

for _entry in (ROOT / "scripts", ROOT / "tests", ROOT):
    if str(_entry) not in sys.path:
        sys.path.insert(0, str(_entry))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(value: Any) -> str:
    """ADR 0002's canonical JSON of `value`, hashed."""
    from openflowsheet.canonical import canonical_json  # noqa: PLC0415

    return sha256(canonical_json(value))


# -- M1: revisions -------------------------------------------------------------------------------


def m1(names: Sequence[str] | None = None) -> dict[str, str]:
    from t07_corpus import CORPUS  # noqa: PLC0415

    from openflowsheet.application.revisions import content_hash  # noqa: PLC0415

    return {name: content_hash(CORPUS[name]()) for name in names or sorted(CORPUS)}


# -- M2-M6: the RC bundle set --------------------------------------------------------------------


#: Review finding 2: registered revisions on the provider bases beyond SYN-001, solved through
#: the g8 path (`solve`): S11's GP cases (Wilson v2), its IAPWS-95 TH cases and M02's C1 flash
#: (pr-c1). TH-C2 (CoolProp R134a) is not run: the reference platform has no `coolprop` extra,
#: so it cannot be recorded there (docs/F0_DECISIONS.md D20); CoolProp enters M6's sample and M9.
BASIS_CASES: Final[dict[str, tuple[str, ...]]] = {
    "s11-gp": ("GP-C1", "GP-C2", "GP-C3", "GP-M1", "GP-M2"),
    "s11-th": ("TH-C1", "TH-R1", "TH-V1"),
    "m02": ("C1-FLASH-F1-M02-v1",),
}


def run_corpus() -> list[tuple[str, str]]:
    """`(set, name)` of every registered run: RC step 4's enumeration, then `BASIS_CASES`."""
    from t08_rc import g8_revisions, k05_registered_cases  # noqa: PLC0415

    return (
        [("k05", case) for case in k05_registered_cases()]
        + [("g8", name) for name in g8_revisions()]
        + [(run_set, name) for run_set, names in BASIS_CASES.items() for name in names]
    )


def revision_document(run_set: str, name: str) -> dict[str, Any]:
    """A fresh copy of a registered revision: T07's corpus (`g8`) or a committed basis case."""
    if run_set == "g8":
        from t07_corpus import CORPUS  # noqa: PLC0415

        return CORPUS[name]()
    if run_set == "m02":
        from m02_c1_corpus import C1_CORPUS  # noqa: PLC0415

        return C1_CORPUS[name]()
    directory = {"s11-gp": "gp", "s11-th": "thermal"}[run_set]
    path = ROOT / "benchmarks" / "s11" / directory / f"{name}.json"
    document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return document


@contextlib.contextmanager
def recorded_cache_keys(
    requests: list[dict[str, Any]] | None = None,
) -> Iterator[list[str]]:
    """Record every key the exact property cache computes, in order, without changing one; and,
    when `requests` is given, each key's inputs as an M6 sample entry (`m6_entry`)."""
    from openflowsheet.thermo.cache import ExactPropertyCache  # noqa: PLC0415

    keys: list[str] = []
    originals = {
        name: getattr(ExactPropertyCache, name) for name in ("_property_key", "_flash_key")
    }

    def recording(original: Callable[..., str]) -> Callable[..., str]:
        def wrapped(*arguments: Any) -> str:
            key = original(*arguments)
            keys.append(key)
            if requests is not None:
                cache, request, context = arguments
                requests.append(m6_entry(cache._capabilities, request, context))
            return key

        return wrapped

    for name, original in originals.items():
        setattr(ExactPropertyCache, name, recording(original))
    try:
        yield keys
    finally:
        for name, original in originals.items():
            setattr(ExactPropertyCache, name, original)


def solve(
    run_set: str, name: str, directory: Path, document: Mapping[str, Any] | None = None
) -> None:
    """One registered run, written as a bundle to `directory`, exactly as RC step 4 writes it."""
    if run_set == "k05":
        from openflowsheet.application.cli import main as cli  # noqa: PLC0415

        assert document is None, "a K05 case is solved by name"
        with contextlib.redirect_stdout(sys.stderr):
            code = cli(["solve", name, "--out", str(directory)])
        if code != 0:
            raise RuntimeError(f"k05 {name}: solve exited {code}")
        return
    from openflowsheet.application.policies import (  # noqa: PLC0415
        DEFAULT_POLICY_ID,
        resolve_policy,
    )
    from openflowsheet.application.revision_run import (  # noqa: PLC0415
        Route,
        run_revision_session,
        select_route,
    )
    from openflowsheet.verify.certificate import CheckPolicy  # noqa: PLC0415

    revision = dict(document) if document is not None else revision_document(run_set, name)
    route = select_route(revision)
    assert isinstance(route, Route), name
    policy = resolve_policy(DEFAULT_POLICY_ID, route.solve_path)
    assert policy is not None, name
    run_revision_session(
        route,
        revision,
        directory,
        run_id=f"run-{name}",
        policy=policy,
        check_policy=CheckPolicy(),
        policy_requested=DEFAULT_POLICY_ID,
    )


def artifacts(directory: Path) -> tuple[Any, dict[str, Any]]:
    from openflowsheet.run.bundle import read_artifact, read_manifest  # noqa: PLC0415

    manifest, _ = read_manifest(directory)
    return manifest, {name: read_artifact(directory, name) for name in sorted(manifest.artifacts)}


def state_hashes(node: Any) -> Iterator[str]:
    """Every state hash in a document, in sorted-key, list order."""
    if isinstance(node, Mapping):
        for key in sorted(node):
            value = node[key]
            if key in STATE_KEYS and isinstance(value, str):
                yield value
            else:
                yield from state_hashes(value)
    elif isinstance(node, list):
        for value in node:
            yield from state_hashes(value)


def run_measures(
    manifest: Any, documents: Mapping[str, Any], keys: Sequence[str]
) -> dict[str, Any]:
    trail = {name: list(state_hashes(document)) for name, document in documents.items()}
    certificate = documents.get("solution-certificate.json")
    checks = (
        [[check["id"], check["result"]] for check in certificate["checks"]]
        if isinstance(certificate, Mapping)
        else []
    )
    return {
        "M2": {
            "model_version": manifest.model_version,
            "constants_sha256": manifest.constants_sha256,
        },
        "M3": {"artifact_r0_sha256": manifest.artifact_r0_sha256},
        "M4": {
            "target_state_sha256": (
                certificate.get("target_state_sha256") if isinstance(certificate, Mapping) else None
            ),
            "n_state_hashes": sum(len(values) for values in trail.values()),
            "state_trail_sha256": digest(trail),
        },
        "M5": {
            "outcome": manifest.outcome,
            "verification_status": manifest.verification_status,
            "n_checks": len(checks),
            "checks_sha256": digest(checks),
        },
        "M6": {"n_keys": len(keys), "keys_sha256": digest(list(keys))},
    }


def runs(
    selection: Sequence[tuple[str, str]] | None = None,
    documents: Mapping[str, Mapping[str, Any]] | None = None,
    requests: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, dict[str, Any]]:
    """M2-M6 per run, keyed `<set>/<name>`. `documents` replaces a g8 run's revision (tests);
    `requests`, when given, receives each run's cache-key inputs, in order (`--record`)."""
    result: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory() as scratch:
        for index, (run_set, name) in enumerate(selection or run_corpus()):
            directory = Path(scratch) / f"{index:03d}"
            captured: list[dict[str, Any]] | None = None if requests is None else []
            with recorded_cache_keys(captured) as keys:
                solve(run_set, name, directory, (documents or {}).get(name))
            result[f"{run_set}/{name}"] = run_measures(*artifacts(directory), keys)
            if requests is not None and captured:
                requests[f"{run_set}/{name}"] = captured
    return result


# -- M6: the cache keys of a committed request sample ---------------------------------------------


def m6_entry(capabilities: Any, request: Any, context: Any) -> dict[str, Any]:
    """One cache-key input set as a document: the provider by id and component order, the
    request (state at full precision: JSON floats round-trip exactly) and the context fields."""
    from openflowsheet.thermo import FlashRequest  # noqa: PLC0415

    state = request.state
    document: dict[str, Any] = {
        "provider_id": capabilities.provider_id,
        "components": list(capabilities.components),
        "state": {"n": list(state.n), "temperature": state.temperature, "pressure": state.pressure},
        "derivatives": list(request.derivatives),
        "context": {
            "model_version": context.model_version,
            "constants_sha256": context.constants_sha256,
            "phase_signature": context.phase_signature,
            "accuracy_policy": context.accuracy_policy,
        },
    }
    if isinstance(request, FlashRequest):
        document |= {"kind": "flash", "specification": request.specification}
    else:
        document |= {
            "kind": "evaluate_phase",
            "phase": request.phase,
            "properties": list(request.properties),
        }
    return document


def m6_sample_provider(provider_id: str, components: Sequence[str]) -> Any:
    """A fresh provider of a registered basis, by id (`basis_provider`); its component order must
    be the recorded one."""
    from openflowsheet.application.revision_binding import basis_provider  # noqa: PLC0415
    from openflowsheet.models.revision_flowsheet import (  # noqa: PLC0415
        SYN001_BASIS,
        ComponentBasis,
    )

    basis = (
        SYN001_BASIS
        if provider_id == SYN001_BASIS.provider_id
        else ComponentBasis(provider_id, tuple(components), {}, record_source="")
    )
    provider = basis_provider(basis)
    if list(provider.describe().components) != list(components):
        raise ValueError(f"M6 sample: {provider_id} components {list(components)} differ")
    return provider


def m6_sample(sample: Path = M6_SAMPLE) -> dict[str, str]:
    """`sample/<id>` -> the exact cache's key of each committed entry, recomputed without solving
    (review finding 1): a function of the entry, the provider's `describe()` and the key code, so
    it is judged on every platform."""
    from openflowsheet.compiled import EvaluationContext  # noqa: PLC0415
    from openflowsheet.thermo import FlashRequest, PropertyRequest, StreamState  # noqa: PLC0415
    from openflowsheet.thermo.cache import ExactPropertyCache  # noqa: PLC0415

    entries: dict[str, dict[str, Any]] = json.loads(sample.read_text(encoding="utf-8"))["entries"]
    caches: dict[tuple[str, ...], Any] = {}
    keys: dict[str, str] = {}
    for name, entry in entries.items():
        identity = (entry["provider_id"], *entry["components"])
        if identity not in caches:
            caches[identity] = ExactPropertyCache(
                m6_sample_provider(entry["provider_id"], entry["components"])
            )
        cache = caches[identity]
        state = StreamState(
            n=tuple(entry["state"]["n"]),
            temperature=entry["state"]["temperature"],
            pressure=entry["state"]["pressure"],
        )
        context = EvaluationContext(**entry["context"])
        derivatives = tuple(entry["derivatives"])
        if entry["kind"] == "flash":
            flash = FlashRequest(state, entry["specification"], derivatives)
            keys[M6_SAMPLE_PREFIX + name] = cache._flash_key(flash, context)
        else:
            phase = PropertyRequest(state, entry["phase"], tuple(entry["properties"]), derivatives)
            keys[M6_SAMPLE_PREFIX + name] = cache._property_key(phase, context)
    return keys


def m6_sample_entries(requests: Mapping[str, Sequence[dict[str, Any]]]) -> dict[str, Any]:
    """The committed sample (`--record`): from each run that keys the cache, its first
    `M6_FIRST` requests and its last, by position; and, for each registered provider basis, one
    `evaluate_phase` and one `flash` request at a fixed state, so every basis' identity enters a
    key whether or not a corpus run caches it."""
    entries: dict[str, Any] = {}
    for run, captured in sorted(requests.items()):
        for position in sorted({*range(min(M6_FIRST, len(captured))), len(captured) - 1}):
            entries[f"{run}#{position}"] = captured[position]
    for provider_id, components in M6_PROVIDERS:
        provider = m6_sample_provider(provider_id, components)
        described = provider.describe()
        state = {"n": [1.0] * len(components), "temperature": 300.0, "pressure": 101325.0}
        common = {
            "provider_id": described.provider_id,
            "components": list(described.components),
            "state": state,
            "derivatives": [],
            "context": {
                "model_version": f"F0-M6-sample@{provider_id}",
                "constants_sha256": "0" * 64,
                "phase_signature": None,
                "accuracy_policy": "exact-double",
            },
        }
        entries[f"provider/{provider_id}/evaluate_phase"] = {
            **common,
            "kind": "evaluate_phase",
            "phase": "LIQUID",
            "properties": ["h"],
        }
        entries[f"provider/{provider_id}/flash"] = {
            **common,
            "kind": "flash",
            "specification": "TP",
        }
    return {
        "format": "f0-m6-request-sample-v1",
        "provenance": "corpus_identity.py --record on the reference platform (review finding 1)",
        "entries": entries,
    }


# -- M7: the 0.3.0 bundles, replayed ------------------------------------------------------------


def m7(bundles: Path = V030_BUNDLES) -> dict[str, dict[str, Any]]:
    """Each bundle re-run and compared as RC step 5 (`bundles-replay`) does, keyed `<set>/<name>`.
    A directory the index does not name, or an entry with no directory, is its own key."""
    from openflowsheet.application.revision_run import reproduce_bundle  # noqa: PLC0415

    index = json.loads((bundles / "index.json").read_text(encoding="utf-8"))
    entries = {entry["directory"]: f"{entry['set']}/{entry['name']}" for entry in index["entries"]}
    found = {
        f"{run_set.name}/{run.name}"
        for run_set in bundles.iterdir()
        if run_set.is_dir()
        for run in run_set.iterdir()
    }
    result: dict[str, dict[str, Any]] = {
        f"unindexed/{directory}": {"verdict": None} for directory in sorted(found - set(entries))
    }
    with tempfile.TemporaryDirectory() as scratch:
        for directory, key in entries.items():
            if directory not in found:
                result[key] = {"verdict": None, "missing": directory}
                continue
            with contextlib.redirect_stdout(sys.stderr):
                report = reproduce_bundle(
                    bundles / directory,
                    rerun=True,
                    rerun_directory=Path(scratch) / directory,
                    run_id="rc-replay",
                ).report
            result[key] = {
                "verdict": report.verdict,
                "mode": report.mode,
                "integrity_ok": report.integrity.ok,
            }
    return result


def archived_outputs(bundles: Path = V030_BUNDLES) -> dict[str, str]:
    """Path -> SHA-256 of each indexed bundle's `artifacts/solve-policy.json` whose policy is one
    of `ARCHIVED_POLICIES`: the guards' registered exemption (R-939)."""
    index = json.loads((bundles / "index.json").read_text(encoding="utf-8"))
    found: dict[str, str] = {}
    for entry in index["entries"]:
        path = bundles / entry["directory"] / "artifacts" / "solve-policy.json"
        if path.is_file():
            data = path.read_bytes()
            if json.loads(data).get("policy_id") in ARCHIVED_POLICIES:
                found[path.relative_to(ROOT).as_posix()] = sha256(data)
    return dict(sorted(found.items()))


# -- M8: schema round-trips ----------------------------------------------------------------------


def m8(functions: Sequence[str] = M8_FUNCTIONS) -> dict[str, str]:
    """Each collected node of `functions` and its worst outcome, from a fresh interpreter."""
    import subprocess  # noqa: PLC0415

    with tempfile.TemporaryDirectory() as scratch:
        out = Path(scratch) / "outcomes.json"
        subprocess.run(  # noqa: S603
            [sys.executable, "-c", M8_DRIVER, str(out), *functions],
            cwd=ROOT,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if not out.is_file():
            return {"driver": "no outcomes written"}
        outcomes: dict[str, str] = json.loads(out.read_text(encoding="utf-8"))
    return outcomes


# -- M9: identity-bearing legacy modules ---------------------------------------------------------


def _imported_modules(module: Path, tree: ast.AST) -> dict[str, Path]:
    """Local name -> file of every `openflowsheet` module `module` imports from (absolute or
    relative), for the names it binds; a package resolves to its `__init__.py`."""
    package = ROOT / "src"
    found: dict[str, Path] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                base = module.parent
                for _ in range(node.level - 1):
                    base = base.parent
                parts = node.module.split(".") if node.module else []
                target = base.joinpath(*parts)
            elif node.module and node.module.split(".")[0] == "openflowsheet":
                target = package.joinpath(*node.module.split("."))
            else:
                continue
            for alias in node.names:
                as_module = target / alias.name
                for candidate in (as_module.with_suffix(".py"), as_module / "__init__.py"):
                    if candidate.is_file():
                        found[alias.asname or alias.name] = candidate
                        break
                else:
                    for candidate in (target.with_suffix(".py"), target / "__init__.py"):
                        if candidate.is_file():
                            found[alias.asname or alias.name] = candidate
                            break
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] != "openflowsheet":
                    continue
                target = package.joinpath(*alias.name.split("."))
                for candidate in (target.with_suffix(".py"), target / "__init__.py"):
                    if candidate.is_file() and alias.asname:
                        found[alias.asname] = candidate
    return found


def _is_hash_site(path: Path) -> bool:
    return "_implementation_sha256" in path.read_text(encoding="utf-8")


def _hashed_files(module: Path, tree: ast.AST) -> set[Path]:
    """Files whose bytes an `implementation_sha256` of `module` reads: the module itself when
    `__file__` is read, each sibling `*.py` named by a string literal in the same scope, the file
    of an imported module whose `__file__` is read, and, when the scope reads another provider's
    `implementation_sha256` (a composed identity, §2.4.4's "imported into such a hash set"),
    every hash-site module `module` imports. A scope that resolves to no file, by any idiom, or a
    composition that resolves to none, raises: the scan never narrows silently."""
    scopes: list[ast.FunctionDef | ast.Assign] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_implementation_sha256":
            scopes.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Attribute) and target.attr == "_implementation_sha256"
            for target in node.targets
        ):
            scopes.append(node)
    imported = _imported_modules(module, tree)
    found: set[Path] = set()
    for scope in scopes:
        files: set[Path] = set()
        names = {n.id for n in ast.walk(scope) if isinstance(n, ast.Name)}
        calls = {n.attr for n in ast.walk(scope) if isinstance(n, ast.Attribute)}
        if "__file__" in names or "here" in names:
            if "read_bytes" in calls:
                files.add(module)
        for node in ast.walk(scope):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value.endswith(".py") and (module.parent / node.value).is_file():
                    files.add(module.parent / node.value)
            elif (
                isinstance(node, ast.Attribute)
                and node.attr == "__file__"
                and isinstance(node.value, ast.Name)
            ):
                if node.value.id not in imported:
                    raise ValueError(f"{module}: {node.value.id}.__file__ is not resolved")
                files.add(imported[node.value.id])
        if "implementation_sha256" in calls:
            composed = {path for path in imported.values() if _is_hash_site(path)}
            if not composed:
                raise ValueError(f"{module}: a composed implementation_sha256 is not resolved")
            files |= composed
        if not files:
            raise ValueError(f"{module}:{scope.lineno}: a hash scope resolves to no file")
        found |= files
    return found


def identity_bearing_modules() -> list[str]:
    """Every file under `src/` whose bytes enter an `implementation_sha256` (§2.4.4, S1)."""
    found: set[Path] = set()
    for path in sorted((ROOT / "src").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "_implementation_sha256" in text:
            found |= _hashed_files(path, ast.parse(text, filename=str(path)))
    return sorted(path.relative_to(ROOT).as_posix() for path in found)


def _reads_file(node: ast.AST) -> bool:
    return any(isinstance(n, ast.Name) and n.id == "__file__" for n in ast.walk(node))


def legacy_unit_modules() -> list[str]:
    """Ruling D9 (R-940): every file under `src/openflowsheet/models/` whose bytes enter a model
    manifest's `implementation_artifact.artifact_hash`, by the two idioms in use:

    - a module's zero-argument `_artifact_hash()` that hashes its own `__file__`;
    - a forwarding `_artifact_hash(path)` (`models/thermal/common.py`): each module that passes
      its own `__file__` to a function it imports from the forwarding module.

    Any other idiom raises: an `artifact_hash=` that is not a call of the module's own
    `_artifact_hash`, a zero-argument one that reads no `__file__`, or a forwarder no module calls
    with its `__file__`. `studies/surrogate` and `adapters/*` are not legacy unit families."""
    models = ROOT / "src" / "openflowsheet" / "models"
    trees = {
        path: ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for path in sorted(models.rglob("*.py"))
    }
    found: set[Path] = set()
    forwarders: set[Path] = set()
    for path, tree in trees.items():
        sites = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_artifact_hash"
        ]
        for keyword in (n for n in ast.walk(tree) if isinstance(n, ast.keyword)):
            if keyword.arg == "artifact_hash" and not (
                sites
                and isinstance(keyword.value, ast.Call)
                and isinstance(keyword.value.func, ast.Name)
                and keyword.value.func.id == "_artifact_hash"
            ):
                raise ValueError(f"{path}:{keyword.value.lineno}: artifact_hash is not resolved")
        for site in sites:
            if site.args.args:
                forwarders.add(path)
            elif _reads_file(site):
                found.add(path)
            else:
                raise ValueError(f"{path}:{site.lineno}: _artifact_hash reads no __file__")
    for forwarder in sorted(forwarders):
        callers = {
            path
            for path, tree in trees.items()
            for names in [{n for n, f in _imported_modules(path, tree).items() if f == forwarder}]
            for call in ast.walk(tree)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id in names
            and any(_reads_file(a) for a in [*call.args, *(k.value for k in call.keywords)])
        }
        if not callers:
            raise ValueError(f"{forwarder}: a forwarding _artifact_hash has no caller")
        found |= callers
    return sorted(path.relative_to(ROOT).as_posix() for path in found)


def frozen_modules() -> list[str]:
    """M9's set: the provider files of `implementation_sha256` and the legacy unit modules."""
    return sorted({*identity_bearing_modules(), *legacy_unit_modules()})


def m9() -> dict[str, str]:
    return {name: sha256((ROOT / name).read_bytes()) for name in frozen_modules()}


# -- registry and comparison ---------------------------------------------------------------------


def reference_class() -> str:
    from t08_rc import machine_class  # noqa: PLC0415

    return machine_class()


def measure_all(requests: dict[str, list[dict[str, Any]]] | None = None) -> dict[str, Any]:
    """Every measure. `requests` (`--record`) receives the runs' cache-key inputs, and the M6
    sample is written from them before it is measured."""
    per_run = runs(requests=requests)
    if requests is not None:
        M6_SAMPLE.write_text(
            json.dumps(m6_sample_entries(requests), indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    measured = {
        measure: {run: values[measure] for run, values in per_run.items()}
        for measure in ("M2", "M3", "M4", "M5", "M6")
    }
    return {
        "M1": m1(),
        **measured,
        "M6": {**measured["M6"], **m6_sample()},
        "M7": m7(),
        "M8": m8(),
        "M9": m9(),
    }


def _fields(value: Any, names: Sequence[str]) -> Any:
    return {n: value.get(n) for n in names} if isinstance(value, Mapping) else value


def compare(
    registered: Mapping[str, Any],
    measured: Mapping[str, Any],
    platform: str,
    *,
    subset: bool = False,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Per measure: `status` (PASS, FAIL, NOT JUDGED, NOT IMPLEMENTED) and counts; and the log.
    `subset` (tests only) judges the measured keys alone and skips unmeasured measures."""
    results: dict[str, dict[str, Any]] = {}
    log: list[str] = []
    for measure in MEASURES:
        if subset and measure not in measured:
            continue
        if measure in NOT_IMPLEMENTED:
            results[measure] = {"status": "NOT IMPLEMENTED"}
            log.append(f"{measure}: NOT IMPLEMENTED — {NOT_IMPLEMENTED[measure]}")
            continue
        expected: Mapping[str, Any] = registered["measures"][measure]
        actual: Mapping[str, Any] = measured[measure]
        if measure == "M4" and platform != registered["reference_platform"]:
            results[measure] = {"status": "NOT JUDGED", "n": len(actual)}
            log.append(
                f"M4: NOT JUDGED on {platform} (reference {registered['reference_platform']})"
            )
            continue
        if measure == "M6" and platform != registered["reference_platform"]:
            expected = {k: v for k, v in expected.items() if k.startswith(M6_SAMPLE_PREFIX)}
            actual = {k: v for k, v in actual.items() if k.startswith(M6_SAMPLE_PREFIX)}
            log.append(
                f"M6: the runs' key trails (iterate states) are not judged on {platform}; "
                "the committed request sample is"
            )
        if measure == "M7" and platform != registered["reference_platform"]:
            expected = {k: _fields(v, M7_PORTABLE) for k, v in expected.items()}
            actual = {k: _fields(v, M7_PORTABLE) for k, v in actual.items()}
            log.append(f"M7: mode not judged on {platform}; {', '.join(M7_PORTABLE)} are")
        wrong = [key for key in actual if key in expected and expected[key] != actual[key]]
        missing = [] if subset else sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        for key in wrong:
            log.append(f"{measure}: {key}: registered {expected.get(key)!r}, now {actual[key]!r}")
        log.extend(f"{measure}: {key}: registered, not measured" for key in missing)
        log.extend(f"{measure}: {key}: measured, not registered" for key in extra)
        failed = len(wrong) + len(missing) + len(extra)
        n = _coverage(measure, expected)
        results[measure] = {
            "status": "FAIL" if failed else "PASS",
            "n": n,
            "failed": failed,
            "wrong": wrong,
        }
    return results, log


def _coverage(measure: str, expected: Mapping[str, Any]) -> int:
    """The judged entries that carry a value: M6 counts the sample and the runs that key the
    cache, not the runs with an empty trail (review finding 1); the others count every entry."""
    if measure != "M6":
        return len(expected)
    return sum(
        1
        for key, value in expected.items()
        if key.startswith(M6_SAMPLE_PREFIX) or (isinstance(value, Mapping) and value["n_keys"])
    )


def summary(results: Mapping[str, Mapping[str, Any]]) -> tuple[bool, str]:
    passed = all(result["status"] in ("PASS", "NOT JUDGED") for result in results.values())
    parts = []
    for measure, result in results.items():
        if result["status"] == "PASS":
            parts.append(f"{measure} {result['n']}/{result['n']}")
        elif result["status"] == "FAIL":
            parts.append(f"{measure} FAIL {result['failed']}/{result['n']}")
        else:
            parts.append(f"{measure} {result['status']}")
    return passed, f"F0 {'PASS' if passed else 'FAIL'}: " + ", ".join(parts)


def record() -> int:
    document = {
        "format": FORMAT,
        "reference_platform": reference_class(),
        "corpus": {
            "M1": "tests/t07_corpus.py CORPUS (T07 W0.2's revisions)",
            "M2-M6": "scripts/t08_rc.py bundles-write: K05 variants (CLI) + T07 W3a ELIGIBLE",
            "M7": "tests/fixtures/f0/v0.3.0-bundles: bundles-write at tag v0.3.0, replayed",
            "M8": "M8_FUNCTIONS: the schema round-trip tests, every collected node",
            "M9": "AST scan of src/ for what feeds an implementation_sha256",
        },
        "measures": measure_all(requests={}),
        "archived_outputs": archived_outputs(),
    }
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"recorded {REGISTRY.relative_to(ROOT)}")
    return 0


def check(log_path: Path) -> int:
    registered = json.loads(REGISTRY.read_text(encoding="utf-8"))
    platform = reference_class()
    results, log = compare(registered, measure_all(), platform)
    passed, line = summary(results)
    log_path.write_text(
        "\n".join([line, f"platform {platform}", *log, json.dumps(results, indent=1)]) + "\n",
        encoding="utf-8",
    )
    print(f"{line} (log {log_path})")
    return 0 if passed else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--record", action="store_true")
    parser.add_argument(
        "--log", type=Path, default=Path(tempfile.gettempdir()) / "corpus-identity.log"
    )
    arguments = parser.parse_args(argv)
    return record() if arguments.record else check(arguments.log)


if __name__ == "__main__":
    raise SystemExit(main())
