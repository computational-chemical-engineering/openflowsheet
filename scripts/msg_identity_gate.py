"""MSG-G0, the identity gate of package MSG (`docs/design/MSG-messages.md` §5, §7, WO-0).

MSG renders human text on read and stores none of it (I2), adds no bundle member and changes no
byte of any member (I3). This script measures that, against a baseline recorded at the branch
point before any MSG code:

- **(a)** SHA-256 of the canonical JSON of `scripts/t07_identity.py`'s `identity()` document (the
  K05/`t07` identity key: validation check messages, G10 refusal codes, R0 projections).
- **(b)** SHA-256 of every file of every bundle written by the RC set (`scripts/t08_rc.py
  bundles-write`: K05's registered SYN-001 runs and T07 G8's revision bundles) and by the
  beginner-mistake cases C01 and C02 (the README Rankine change set with the boiler at 973.15 K;
  C02 with S4 declared vapour), keyed by `<set>/<case>/<member path>`. C03 (reading
  `solution-state.json` from C01's bundle) writes no bundle; its refusal's machine `code` and
  `message` are recorded instead (I1: `detail` may gain members, these two may not move).
- **(c)** `reproduce_bundle(rerun=True)` of each bundle of the 0.3.0 RC set (written once by
  `write-v030` in a detached worktree at tag `v0.3.0`, design note §8 Q12) and of each committed
  replay fixture under `tests/`: `mode`, `verdict` and `bitwise_floats`.
- **(d)** zero occurrences of the key `"explanation"` in the stores a full test-suite run leaves:
  `jobs` (`worker_result`, `error`, `ending`), `events.document`, `ledger.result` and every text
  column of `audit`, in every `project.sqlite3` under the run's pytest base directory.

The baseline also records, for MSG-G10 later, the served MCP tool-list digest and the SHA-256 of
every `OPERATIONS` row's request and response schema (the R4-G3 snapshots). They are reported by
`--check` but do not decide MSG-G0.

**After F0** (review Q3, M3): F0's `scripts/corpus_identity.py --check` replaces (a) and (c), so the
default `--parts` is `bd`; record F0's line beside this one. `--parts abcd` still measures all four
against the same baseline.

Subprocesses pin the thread variables to 1 (`run/manifest.py` records them in every bundle).
Prints one summary line; the full log goes to `--log`.

    python scripts/msg_identity_gate.py write-v030 --out DIR
    python scripts/msg_identity_gate.py --record FILE --v030 DIR [--stores DIR | --suite]
    python scripts/msg_identity_gate.py --check FILE [--stores DIR | --suite] [--log FILE]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
FORMAT = "msg-identity-gate-v1"
THREAD_VARIABLES = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")
RELEASE_TAG = "v0.3.0"
#: Committed replay bundles: each `run-manifest.json` directory under `tests/`, found at run time.
FIXTURE_ROOT = ROOT / "tests"
#: The store tables and columns (d) scans, `application/store.py` `_TABLES`.
STORE_COLUMNS: Mapping[str, tuple[str, ...]] = {
    "jobs": ("worker_result", "error", "ending"),
    "events": ("document",),
    "ledger": ("result",),
    "audit": ("operation", "outcome", "code", "effect"),
}
PARTS = ("a", "b", "c", "d")
#: The run manifest's members that differ between two runs of one commit (measured: C01 written
#: twice at one commit differs in exactly these). `manifest_sha256` covers the other two.
VOLATILE_MANIFEST_KEYS = ("started_at", "elapsed_seconds", "manifest_sha256")


#: Review Q3 (M3): F0 replaces (a) and (c); MSG-G0 measures (b) and (d).
DEFAULT_PARTS = "bd"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def environment(src: Path, extra: Iterable[Path] = ()) -> dict[str, str]:
    env = dict(os.environ)
    env.update({name: "1" for name in THREAD_VARIABLES})
    env["PYTHONPATH"] = os.pathsep.join(str(p) for p in (src, *extra))
    env["PYTHONHASHSEED"] = "0"
    return env


def run(command: Sequence[str], *, cwd: Path, env: Mapping[str, str], log: Any) -> None:
    log.write(f"$ {' '.join(command)}  (cwd {cwd})\n")
    log.flush()
    completed = subprocess.run(
        list(command), cwd=cwd, env=dict(env), stdout=log, stderr=subprocess.STDOUT, check=False
    )
    if completed.returncode != 0:
        raise RuntimeError(f"{command[1:3]} exited {completed.returncode}")


def tree_digests(root: Path) -> dict[str, str]:
    """`{relative path: sha256}` of every file under `root`."""
    return {
        path.relative_to(root).as_posix(): sha256(path.read_bytes())
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def bundle_digests(root: Path) -> dict[str, str]:
    """`tree_digests` of a bundle, except that `run-manifest.json` is digested without its
    wall-clock members (`VOLATILE_MANIFEST_KEYS`), keyed `run-manifest.json#stable`. Every other
    manifest member — the artifact digests, `artifact_r0_sha256`, `structural_sha256`,
    `model_version`, `constants_sha256`, the environment — is compared byte for byte."""
    digests = tree_digests(root)
    manifest = root / "run-manifest.json"
    if manifest.is_file():
        del digests["run-manifest.json"]
        document = json.loads(manifest.read_text("utf-8"))
        stable = {k: v for k, v in document.items() if k not in VOLATILE_MANIFEST_KEYS}
        canonical = json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()
        digests["run-manifest.json#stable"] = sha256(canonical)
    return digests


def bundle_directories(root: Path) -> list[Path]:
    return sorted(path.parent for path in root.rglob("run-manifest.json"))


# -- the in-process steps, each run in a subprocess -------------------------------------------


def step_t07(out: Path) -> int:
    sys.path.insert(0, str(ROOT / "scripts"))
    import t07_identity

    from openflowsheet.canonical import canonical_json

    document = json.loads(json.dumps(t07_identity.identity()))
    out.write_text(json.dumps({"sha256": sha256(canonical_json(document))}) + "\n")
    return 0


def step_corpus(out: Path) -> int:
    """C01 and C02 write their bundles under `out/<case>/`; C03's machine refusal goes to
    `out/c03.json`."""
    from openflowsheet.application.contract import ApplicationError
    from openflowsheet.application.local import LocalApplication
    from openflowsheet.application.types import Change

    base = json.loads((ROOT / "examples" / "rankine-cycle.changeset.json").read_text("utf-8"))

    def variant(s4_phase: str | None) -> dict[str, Any]:
        document: dict[str, Any] = json.loads(json.dumps(base))
        for edit in document["edits"]:
            if edit["path"] == ["specifications"]:
                (spec,) = [s for s in edit["value"] if s["id"] == "boiler-T"]
                spec["value"] = 973.15
            if s4_phase is not None and edit["path"] == ["connections"]:
                (s4,) = [c for c in edit["value"] if c["id"] == "S4"]
                s4["phase_capability"] = s4_phase
        return document

    refusal: dict[str, Any] = {}
    for case, s4_phase in (("C01", None), ("C02", "vapor")):
        project = out / case
        with LocalApplication.create(project, project_id=f"msg-{case}") as app:
            change, expected, key = Change.from_change_set(variant(s4_phase))
            committed = app.commit_change(change, expected, key)
            assert committed.revision_id is not None, committed
            result = app.solve(committed.revision_id, "default")
            print(case, result.outcome, result.verification_status)
            if case == "C01":
                bundle = next(o.artifact_id for o in result.outputs if o.kind == "replay_bundle")
                try:
                    app.artifact_bytes(f"{bundle}/solution-state.json")
                except ApplicationError as error:
                    refusal = {"code": error.error.code, "message": error.error.message}
    (out / "c03.json").write_text(json.dumps(refusal, sort_keys=True) + "\n")
    return 0 if refusal else 1


def step_replay(bundles: Path, out: Path) -> int:
    from openflowsheet.application.revision_run import reproduce_bundle

    rows: dict[str, Any] = {}
    with tempfile.TemporaryDirectory() as scratch:
        for index, (key, directory) in enumerate(json.loads(bundles.read_text("utf-8")).items()):
            report = reproduce_bundle(
                Path(directory),
                rerun=True,
                rerun_directory=Path(scratch) / str(index),
                run_id="msg-g0",
            ).report
            rows[key] = {
                "mode": report.mode,
                "verdict": report.verdict,
                "bitwise_floats": report.bitwise_floats,
            }
    out.write_text(json.dumps(rows, indent=1, sort_keys=True) + "\n")
    return 0


def step_surface(out: Path) -> int:
    from openflowsheet.application.operations import OPERATIONS
    from openflowsheet.canonical import canonical_json

    sys.path.insert(0, str(ROOT))
    snapshots = {
        name: {
            "request": sha256(canonical_json(op.request_schema)),
            "response": None
            if op.response_schema is None
            else sha256(canonical_json(op.response_schema)),
        }
        for name, op in sorted(OPERATIONS.items())
    }
    try:
        from benchmarks.t07.v17 import harness

        digest: str | None = harness.tool_descriptions_sha256()
    except ImportError:  # the `mcp` extra is absent
        digest = None
    schemas = {
        path.name: sha256(path.read_bytes()) for path in sorted((ROOT / "schemas").glob("*.json"))
    }
    out.write_text(
        json.dumps(
            {"mcp_tools_sha256": digest, "operations": snapshots, "schema_files": schemas},
            indent=1,
            sort_keys=True,
        )
        + "\n"
    )
    return 0


# -- the measurements ---------------------------------------------------------------------------


def measure_a(work: Path, log: Any) -> dict[str, Any]:
    out = work / "a.json"
    run(
        [sys.executable, __file__, "_t07", str(out)],
        cwd=ROOT,
        env=environment(ROOT / "src"),
        log=log,
    )
    return {"t07_identity_sha256": json.loads(out.read_text("utf-8"))["sha256"]}


def measure_b(work: Path, log: Any) -> dict[str, Any]:
    env = environment(ROOT / "src", (ROOT,))
    rc = work / "rc"
    run(
        [sys.executable, "scripts/t08_rc.py", "bundles-write", "--out", str(rc)],
        cwd=ROOT,
        env=env,
        log=log,
    )
    corpus = work / "corpus"
    corpus.mkdir()
    run([sys.executable, __file__, "_corpus", str(corpus)], cwd=ROOT, env=env, log=log)
    members: dict[str, str] = {}
    for root, prefix in ((rc, "rc"), (corpus, "corpus")):
        for directory in bundle_directories(root):
            name = directory.relative_to(root).as_posix()
            for member, digest in bundle_digests(directory).items():
                members[f"{prefix}/{name}/{member}"] = digest
    return {
        "n_bundles": len({key.rsplit("/", 1)[0] for key in members}),
        "members": members,
        "c03": json.loads((corpus / "c03.json").read_text("utf-8")),
    }


def replay_inputs(v030: Path) -> dict[str, str]:
    inputs = {f"v030/{d.relative_to(v030).as_posix()}": str(d) for d in bundle_directories(v030)}
    for directory in bundle_directories(FIXTURE_ROOT):
        inputs[f"fixture/{directory.relative_to(ROOT).as_posix()}"] = str(directory)
    return inputs


def measure_c(work: Path, v030: Path, log: Any) -> dict[str, Any]:
    inputs = replay_inputs(v030)
    listing = work / "c-inputs.json"
    listing.write_text(json.dumps(inputs, sort_keys=True))
    out = work / "c.json"
    run(
        [sys.executable, __file__, "_replay", str(listing), str(out)],
        cwd=ROOT,
        env=environment(ROOT / "src", (ROOT,)),
        log=log,
    )
    return {
        "v030_input_sha256": {
            key: sha256(json.dumps(tree_digests(Path(path)), sort_keys=True).encode())
            for key, path in inputs.items()
            if key.startswith("v030/")
        },
        "replays": json.loads(out.read_text("utf-8")),
    }


def measure_d(stores: Path) -> dict[str, Any]:
    databases = sorted(stores.rglob("project.sqlite3"))
    hits: list[str] = []
    for database in databases:
        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        try:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
            for table, columns in STORE_COLUMNS.items():
                if table not in tables:
                    continue
                for column in columns:
                    query = (
                        f"SELECT COUNT(*) FROM {table} "  # noqa: S608 (fixed identifiers)
                        f"WHERE CAST({column} AS TEXT) LIKE '%\"explanation\"%'"
                    )
                    (count,) = connection.execute(query).fetchone()
                    if count:
                        hits.append(f"{database}:{table}.{column}={count}")
        finally:
            connection.close()
    return {"n_stores": len(databases), "explanation_hits": hits}


def measure_surface(work: Path, log: Any) -> dict[str, Any]:
    out = work / "surface.json"
    run(
        [sys.executable, __file__, "_surface", str(out)],
        cwd=ROOT,
        env=environment(ROOT / "src"),
        log=log,
    )
    result: dict[str, Any] = json.loads(out.read_text("utf-8"))
    return result


def suite_stores(work: Path, log: Any) -> Path:
    basetemp = work / "suite"
    log.write("$ pytest (full default suite) for (d)\n")
    log.flush()
    subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--basetemp={basetemp}"],
        cwd=ROOT,
        env=environment(ROOT / "src"),
        stdout=log,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return basetemp


def measure(arguments: argparse.Namespace, work: Path, log: Any) -> dict[str, Any]:
    parts = arguments.parts
    stores = None
    if "d" in parts:
        stores = arguments.stores or (suite_stores(work, log) if arguments.suite else None)
    return {
        "format": FORMAT,
        "commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip(),
        "a": measure_a(work, log) if "a" in parts else None,
        "b": measure_b(work, log) if "b" in parts else None,
        "c": measure_c(work, arguments.v030, log) if "c" in parts else None,
        "d": None if stores is None else measure_d(stores),
        "surface": measure_surface(work, log),
    }


def differences(
    baseline: Mapping[str, Any], current: Mapping[str, Any], parts: str = "abcd"
) -> dict[str, list[str]]:
    """Per measured part, the keys whose values differ (a key on one side only counts)."""
    out: dict[str, list[str]] = {}
    for part in "abc":
        if part not in parts:
            continue
        old, new = flatten(baseline[part]), flatten(current[part])
        out[part] = sorted(k for k in old.keys() | new.keys() if old.get(k) != new.get(k))
    if "d" not in parts:
        return out
    d = current["d"]
    out["d"] = ["not measured"] if d is None else list(d["explanation_hits"])
    if d is not None and d["n_stores"] == 0:
        out["d"].append("no store found")
    return out


def flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, Mapping):
        flat: dict[str, Any] = {}
        for key, item in value.items():
            flat.update(flatten(item, f"{prefix}{key}/"))
        return flat
    return {prefix.rstrip("/"): value}


def write_v030(out: Path, log: Any) -> int:
    """The 0.3.0 RC bundle set, written by the tag's own code (design note §8 Q12)."""
    with tempfile.TemporaryDirectory() as scratch:
        tree = Path(scratch) / "v030"
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(tree), RELEASE_TAG],
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
        )
        try:
            run(
                [sys.executable, "scripts/t08_rc.py", "bundles-write", "--out", str(out)],
                cwd=tree,
                env=environment(tree / "src", (tree,)),
                log=log,
            )
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(tree)], cwd=ROOT, check=True
            )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    internal = {"_t07": step_t07, "_corpus": step_corpus, "_surface": step_surface}
    if argv and argv[0] in internal:
        return internal[argv[0]](Path(argv[1]))
    if argv and argv[0] == "_replay":
        return step_replay(Path(argv[1]), Path(argv[2]))
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("command", nargs="?", choices=("write-v030",))
    parser.add_argument("--out", type=Path, help="write-v030: where to write the bundles")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--record", type=Path, help="write the baseline here")
    mode.add_argument("--check", type=Path, help="compare against this baseline")
    parser.add_argument("--v030", type=Path, help="the 0.3.0 RC set (default: the baseline's)")
    stores = parser.add_mutually_exclusive_group()
    stores.add_argument("--stores", type=Path, help="(d): a pytest base directory to scan")
    stores.add_argument("--suite", action="store_true", help="(d): run the full suite first")
    parser.add_argument(
        "--parts",
        default=DEFAULT_PARTS,
        help="the parts to measure and judge (default: bd; F0 covers a and c, review Q3)",
    )
    parser.add_argument("--log", type=Path, default=None)
    arguments = parser.parse_args(argv)
    log_path = arguments.log or Path(tempfile.gettempdir()) / "msg-identity-gate.log"
    with log_path.open("w", encoding="utf-8") as log, tempfile.TemporaryDirectory() as scratch:
        if arguments.command == "write-v030":
            if arguments.out is None:
                parser.error("write-v030 needs --out")
            code = write_v030(arguments.out.resolve(), log)
            n = len(bundle_directories(arguments.out))
            print(f"MSG-G0 write-v030: {n} bundles (log {log_path})")
            return code
        if arguments.record is None and arguments.check is None:
            parser.error("--record or --check is required")
        baseline: dict[str, Any] | None = None
        if arguments.check is not None:
            baseline = json.loads(arguments.check.read_text("utf-8"))
            assert baseline is not None and baseline["format"] == FORMAT
            arguments.v030 = arguments.v030 or Path(baseline["v030"])
        if arguments.v030 is None:
            parser.error("--record needs --v030")
        current = measure(arguments, Path(scratch), log)
        current["v030"] = str(arguments.v030)
        if arguments.record is not None:
            arguments.record.parent.mkdir(parents=True, exist_ok=True)
            arguments.record.write_text(json.dumps(current, indent=1, sort_keys=True) + "\n")
            baseline = current
        assert baseline is not None
        found = differences(baseline, current, arguments.parts)
        json.dump(found, log, indent=1)
        moved = sorted(
            k
            for k in flatten(baseline["surface"]).keys() | flatten(current["surface"]).keys()
            if flatten(baseline["surface"]).get(k) != flatten(current["surface"]).get(k)
        )
        log.write(f"\nsurface moved: {moved}\n")
        passed = not any(found.values())
        summary = []
        if "a" in found:
            summary.append(f"a {len(found['a'])} diff")
        if "b" in found:
            summary.append(
                f"b {len(found['b'])}/{len(flatten(current['b']))} diff "
                f"({current['b']['n_bundles']} bundles)"
            )
        if "c" in found:
            summary.append(f"c {len(found['c'])}/{len(current['c']['replays'])} diff")
        if "d" in found:
            where = "" if current["d"] is None else f" in {current['d']['n_stores']} stores"
            summary.append(f"d {len(found['d'])} hit(s){where}")
        summary.append(f"surface {'moved: ' + ', '.join(moved[:4]) if moved else 'same'}")
        counts = "; ".join(summary)
        if arguments.parts == DEFAULT_PARTS:
            counts = f"{counts}; a, c: F0 (corpus_identity.py --check)"
        elif arguments.parts != "abcd":
            counts = f"parts {arguments.parts} only: {counts}"
        print(f"MSG-G0 {'PASS' if passed else 'FAIL'}: {counts} (log {log_path})")
        if not passed:
            for part, keys in found.items():
                for key in keys[:5]:
                    print(f"  ({part}) {key}")
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
