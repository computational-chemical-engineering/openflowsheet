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
| M6 | the exact property cache's key digests of the runs' requests | the RC bundle set |
| M7 | replay verdicts of the 0.3.0 bundles | not implemented yet |
| M8 | schema round-trips | not implemented yet |
| M9 | SHA-256 of each file whose bytes enter an `implementation_sha256` | AST scan of `src/` |

The RC bundle set is RC step 4's (`scripts/t08_rc.py bundles-write`): the K05 SYN-001 variants
solved through the CLI and T07 W3a's eligible revisions under the default policy. F0 wraps those
enumerations; it does not keep its own copy of them.

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
NOT_IMPLEMENTED: Final = {
    "M7": "the 0.3.0 bundles are not in the repository yet (docs/F0_DECISIONS.md D3)",
    "M8": "the schema round-trip wrapper is not written yet (docs/F0_DECISIONS.md D4)",
}
STATE_KEYS: Final = ("state_sha256", "target_state_sha256")

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


def run_corpus() -> list[tuple[str, str]]:
    """`(set, name)` of every registered run, enumerated as RC step 4 enumerates them."""
    from t08_rc import g8_revisions, k05_registered_cases  # noqa: PLC0415

    return [("k05", case) for case in k05_registered_cases()] + [
        ("g8", name) for name in g8_revisions()
    ]


@contextlib.contextmanager
def recorded_cache_keys() -> Iterator[list[str]]:
    """Record every key the exact property cache computes, in order, without changing one."""
    from openflowsheet.thermo.cache import ExactPropertyCache  # noqa: PLC0415

    keys: list[str] = []
    originals = {
        name: getattr(ExactPropertyCache, name) for name in ("_property_key", "_flash_key")
    }

    def recording(original: Callable[..., str]) -> Callable[..., str]:
        def wrapped(*arguments: Any) -> str:
            key = original(*arguments)
            keys.append(key)
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
    from t07_corpus import CORPUS  # noqa: PLC0415

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

    revision = dict(document) if document is not None else CORPUS[name]()
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
) -> dict[str, dict[str, Any]]:
    """M2-M6 per run, keyed `<set>/<name>`. `documents` replaces a g8 run's revision (tests)."""
    result: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory() as scratch:
        for index, (run_set, name) in enumerate(selection or run_corpus()):
            directory = Path(scratch) / f"{index:03d}"
            with recorded_cache_keys() as keys:
                solve(run_set, name, directory, (documents or {}).get(name))
            result[f"{run_set}/{name}"] = run_measures(*artifacts(directory), keys)
    return result


# -- M9: identity-bearing legacy modules ---------------------------------------------------------


def _hashed_files(module: Path, tree: ast.AST) -> set[Path]:
    """Files whose bytes an `implementation_sha256` of `module` reads: the module itself when
    `__file__` is read, and each sibling `*.py` named by a string literal in the same scope."""
    scopes: list[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_implementation_sha256":
            scopes.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Attribute) and target.attr == "_implementation_sha256"
            for target in node.targets
        ):
            scopes.append(node)
    found: set[Path] = set()
    for scope in scopes:
        names = {n.id for n in ast.walk(scope) if isinstance(n, ast.Name)}
        calls = {n.attr for n in ast.walk(scope) if isinstance(n, ast.Attribute)}
        if "__file__" in names or "here" in names:
            if "read_bytes" in calls:
                found.add(module)
        for node in ast.walk(scope):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value.endswith(".py") and (module.parent / node.value).is_file():
                    found.add(module.parent / node.value)
    return found


def identity_bearing_modules() -> list[str]:
    """Every file under `src/` whose bytes enter an `implementation_sha256` (§2.4.4, S1)."""
    found: set[Path] = set()
    for path in sorted((ROOT / "src").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "_implementation_sha256" in text:
            found |= _hashed_files(path, ast.parse(text))
    return sorted(path.relative_to(ROOT).as_posix() for path in found)


def m9() -> dict[str, str]:
    return {name: sha256((ROOT / name).read_bytes()) for name in identity_bearing_modules()}


# -- registry and comparison ---------------------------------------------------------------------


def reference_class() -> str:
    from t08_rc import machine_class  # noqa: PLC0415

    return machine_class()


def measure_all() -> dict[str, Any]:
    per_run = runs()
    return {
        "M1": m1(),
        **{
            measure: {run: values[measure] for run, values in per_run.items()}
            for measure in ("M2", "M3", "M4", "M5", "M6")
        },
        "M9": m9(),
    }


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
        wrong = [key for key in actual if key in expected and expected[key] != actual[key]]
        missing = [] if subset else sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        for key in wrong:
            log.append(f"{measure}: {key}: registered {expected.get(key)!r}, now {actual[key]!r}")
        log.extend(f"{measure}: {key}: registered, not measured" for key in missing)
        log.extend(f"{measure}: {key}: measured, not registered" for key in extra)
        failed = len(wrong) + len(missing) + len(extra)
        results[measure] = {
            "status": "FAIL" if failed else "PASS",
            "n": len(expected),
            "failed": failed,
            "wrong": wrong,
        }
    return results, log


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
            "M9": "AST scan of src/ for what feeds an implementation_sha256",
        },
        "measures": measure_all(),
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
