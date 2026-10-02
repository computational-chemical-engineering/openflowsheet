"""T08 W4.3–W4.4: the release-candidate job of release spec §8.2, one subcommand per step.

The RC job runs at the release candidate `C` (§8.1). Each subcommand measures one step, writes a
JSON record carrying `commit`, `tree_clean`, the lock's sha256 and the machine class (T08.A16),
prints a verdict line per check, and exits 0 iff every check passed. Nothing here judges a gate:
the records are evidence for the design lane's verdicts (T08 Phase 5).

Steps (§8.2), the subcommand or job that measures each, and its assertions:

1. `check.sh` on both architectures — CI job `check` (every push and dispatch) — T08.A41.
2. Identity and the trial version `0.1.0` — `identity` on each runner; CI job `identity`
   compares the two architectures — T08.A42.
3. sdist and wheel built twice — `scripts/t08_dist.py` — T08.A43.
4. Clean install on both architectures — `install-check`, run by the clean environment's
   interpreter outside the checkout — T08.A44; the lock lookup and the installed package's
   bundle replay — `lock-check --state installed` and `--state checkout`, the same interpreter
   — T08.A19.
5. The RC bundle set — `bundles-write` (CI x86-64), `bundles-replay` (fresh x86-64 and aarch64
   runners) — T08.A45; each replay records the policy its bundle names, every bundle must name
   `T08-numerical-policy-v2`, and ADR 0025 A14's three controls run on both runners.
6. The registered ensemble and T06 A34's same-class replay of it — `ensemble` (`ref-x86-64`
   locally, `ci-aarch64` in CI) — T08.A46 and A47's S3 clause.
7. Adversarial, invalid-structure and reference subsets — `corpus` — T08.A47, A48.
8. Agent surface and G16-b — `surface` — T08.A49.
9. The [A10] inventory — `scripts/p03_binary_inventory.py --a30` — T08.A30.
10. Certificate audit over steps 4–7's outputs — `certificates` — T08.A34.
11. The gate report — `scripts/v0_1_gate.py` — T08.A50.

**Registered values** are restated below with their sources, and `tests/test_t08_w4_rc.py`
holds each equal to its source.

**Readings recorded rather than chosen** (each in the T08 Phase 4 report):

- *A45's two sets* (confirmed by release spec Amendment R3 1). "K05's registered SYN-001 runs"
  are the registered variants of `benchmarks/syn001/reference_values.yaml`, written by the CLI's
  `solve <case>` (the K05/K06 tear path; a K05 bundle reruns when its `run_id` is a registered
  case). "T07 G8's revision bundles" are `tests/test_t07_w3a_revision_runs.py`'s `ELIGIBLE`
  revisions under `default`, as its `runs` fixture writes them. Both are enumerated at `C`, not
  hard-coded, and counted per set. T06 A34 is not in A45 (it writes no bundle, and per-start
  outcomes are not promised across architectures, L07): T08.A46 carries it in its registered
  form — `ensemble` replays the RC run's first start of every case and every retained failure on
  the same machine class (`scripts/t06_ensemble.py replay`), `MATCH` on every field.
- *A49's digest.* The row names `v17-c2`'s `6d13e13d…`; R-133 moved the served digest to
  `171dd768…` and registered it beside the old one. The record states both comparisons, and that
  serving `v17-c2`'s two texts reproduces `6d13e13d…` — which, because the digest covers every
  tool's `inputSchema` and `outputSchema`, is the request/response-schema clause against
  `c7bbc98` (`v17-c2`'s commit). The check passes on R-133's reading and records the literal one.

    PYTHONPATH=src:. python scripts/t08_rc.py <subcommand> --out <path> [...]
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final

ROOT: Final = Path(__file__).resolve().parent.parent
FORMAT: Final = "t08-rc-v1"
THREAD_VARIABLES: Final = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")

#: `requirements.lock`, T08.A40 (release spec §3.2).
LOCK_SHA256: Final = "ead4edf1ea3577287a7576d56a9e5db550e5a5be459dd634b10806fdc655b9c4"
#: The K05 identity document minus `t07`, as re-registered for ADR 0025 D1.2's recording switch
#: (R-148) and the rename to `openflowsheet` (R-149; `tests/test_t07_identity.py`,
#: `K05_MINUS_T07_SHA256_R149`).
K05_MINUS_T07_SHA256: Final = "24af004ab5718e559bd3d40716d66e21d9b19043a26777a39a0da84c6fbdcb8e"
#: The `t07` key after §6.2's approved substitution (F4; D1's STR-05 extension), R-148's and
#: R-149's: `tests/test_t08_w1_identity_substitution.py`, `T07_KEY_SHA256_R149`.
T07_KEY_SHA256: Final = "887a2e622676dbfaff0a8ebfc309414f0e74150ace8327887b4a9ec15e498a38"
#: The trial version string of T08.A42.
TRIAL_VERSION: Final = "0.1.0"
#: `v17-c2`'s served tool-list digest (release spec §3.2; `benchmarks/t08/reference_values.yaml`).
V17_C2_DESCRIPTIONS_SHA256: Final = (
    "6d13e13d660521c1a39dc245d5237c974a4273b0c3eeadb02d44538ba2669a4d"
)
#: The served digest R-133 registered (`tests/test_t08_w2_surface_digest.py`).
R133_DESCRIPTIONS_SHA256: Final = "171dd768efcfb24f65d79d83a4f157dcfd1436935bf5106a247b84f3040e4d14"
#: The registered K04 certificate of SYN-001-nominal (`scripts/k04_schema_fixtures.py`).
NOMINAL_CERTIFICATE: Final = Path(
    "tests/fixtures/schemas/solution_certificate/valid/syn001_nominal_verified.json"
)
#: T08.A44's audited CasADi files: x86-64 per file (P03) and, per architecture, the A30 digest.
P03_CASADI_INVENTORY: Final = Path("spikes/p03/results/casadi-inventory.json")
A30_SUMMARIES: Final = {
    "x86_64": Path("docs/t08-a30/t08-a30-x86_64.json"),
    "aarch64": Path("docs/t08-a30/t08-a30-aarch64.json"),
}
#: T08.A47 and A48: the T06 assertions re-run at `C`, and the T06 manifest naming their tests.
T06_MANIFEST: Final = Path("evidence/T06/ebec629d63e32fb1984b56ad31372c960cd0ae2f/manifest.json")
A47_ASSERTIONS: Final = (
    "T06.A02",
    "T06.A03",
    "T06.A04",
    "T06.A05",
    "T06.A06",
    "T06.A07",
    "T06.A08",
    "T06.A16",
    "T06.A19",
    "T06.A20",
)
A48_ASSERTIONS: Final = ("T06.A47", "T06.A50")
#: A45's sets (Amendment R3 1): K05's registered variants and T07 G8's eligible revisions.
A45_SETS: Final = ("k05", "g8")
#: ADR 0025 A14's controls: (set, bundle) each mutates, re-seals and replays.
A14_CONTROL_BUNDLES: Final = {
    "c1": ("g8", "SYN-001-nominal"),
    "c2": ("g8", "SYN-001-nominal"),
    "c3": ("k05", "SYN-001-high-recycle"),
}

#: Characters `actions/upload-artifact` refuses in a path (RC run 36904782855 failed on the revision
#: id `T05b:DZ-3`). A bundle directory percent-encodes them; the index keeps the revision's name.
_UNPORTABLE: Final = '":<>|*?\r\n'


def _portable(name: str) -> str:
    """`name` with every artifact-unsafe character (and `%`) percent-encoded; injective."""
    return "".join(f"%{ord(c):02X}" if c in _UNPORTABLE or c == "%" else c for c in name)


# -- records -----------------------------------------------------------------------------------


def git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def provenance() -> dict[str, Any]:
    """T08.A16's fields, read from the checkout the script lives in (stdlib only, so that the
    clean-install step can call it without importing the checkout's package)."""
    lock = ROOT / "requirements.lock"
    return {
        "commit": git("rev-parse", "HEAD").strip(),
        "tree_clean": git("status", "--porcelain").strip() == "",
        "environment_lock_sha256": sha256_bytes(lock.read_bytes()),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "github_actions": os.environ.get("GITHUB_ACTIONS") == "true",
        "threads": {name: os.environ.get(name) for name in THREAD_VARIABLES},
    }


def machine_class() -> str:
    """T06 §7.5 (A5)'s class (`benchmarks.t06.ensemble.machine_class`)."""
    sys.path.insert(0, str(ROOT))
    from benchmarks.t06 import ensemble  # noqa: PLC0415

    return str(ensemble.machine_class())


def check(checks: list[dict[str, Any]], check_id: str, passed: bool, **value: Any) -> None:
    checks.append({"id": check_id, "result": "pass" if passed else "fail", **value})


def finish(out: Path, step: str, checks: list[dict[str, Any]], **body: Any) -> int:
    record = {
        "format": FORMAT,
        "step": step,
        "provenance": body.pop("provenance", None) or provenance(),
        **body,
        "checks": checks,
        "passed": bool(checks) and all(entry["result"] == "pass" for entry in checks),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    for entry in checks:
        print(f"{entry['result'].upper():4} {entry['id']}")
    print(f"{step}: {'PASS' if record['passed'] else 'FAIL'} ({out})")
    return 0 if record["passed"] else 1


def pinned_environment(**extra: str) -> dict[str, str]:
    environment = {**os.environ, **{name: "1" for name in THREAD_VARIABLES}, **extra}
    return environment


# -- step 2: identity (T08.A42) ----------------------------------------------------------------

_RUN_WITH_VERSION = (
    "import runpy, sys\n"
    "import openflowsheet\n"
    "version = sys.argv[1]\n"
    "if version: openflowsheet.__version__ = version\n"
    "sys.argv = sys.argv[2:]\n"
    "runpy.run_path(sys.argv[0], run_name='__main__')\n"
)


def _emit_identity(directory: Path, version: str) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    k05, floats = directory / "identity.json", directory / "t02-floats.json"
    environment = pinned_environment(PYTHONPATH=os.pathsep.join([str(ROOT / "src"), str(ROOT)]))
    for script, arguments in (
        ("scripts/k05_structural_identity.py", ["--out", str(k05)]),
        ("scripts/t02_identity.py", ["--floats-out", str(floats)]),
    ):
        subprocess.run(
            [sys.executable, "-c", _RUN_WITH_VERSION, version, str(ROOT / script), *arguments],
            cwd=ROOT,
            env=environment,
            check=True,
        )
    return k05, floats


def identity_digests(document_bytes: bytes) -> dict[str, str]:
    """`scripts/t07_evidence_manifest.py`'s §W0.1 convention for the whole document, the
    document minus `t07`, and the `t07` key."""
    document = json.loads(document_bytes)
    rest = {key: value for key, value in document.items() if key != "t07"}
    return {
        "whole": sha256_bytes(document_bytes),
        "minus_t07": sha256_bytes((json.dumps(rest, indent=1, sort_keys=True) + "\n").encode()),
        "t07_key": sha256_bytes(json.dumps(document["t07"], sort_keys=True).encode()),
        "structural_sha256": str(document["structural_sha256"]),
    }


def step_identity(arguments: argparse.Namespace) -> int:
    out: Path = arguments.out
    k05, floats = _emit_identity(out / "as-built", "")
    trial_k05, trial_floats = _emit_identity(out / f"version-{TRIAL_VERSION}", TRIAL_VERSION)
    digests = identity_digests(k05.read_bytes())
    checks: list[dict[str, Any]] = []
    check(
        checks,
        "a42.minus_t07_registered",
        digests["minus_t07"] == K05_MINUS_T07_SHA256,
        found=digests["minus_t07"],
        expected=K05_MINUS_T07_SHA256,
    )
    check(
        checks,
        "a42.t07_key_substituted",
        digests["t07_key"] == T07_KEY_SHA256,
        found=digests["t07_key"],
        expected=T07_KEY_SHA256,
    )
    check(
        checks,
        "a42.unchanged_under_trial_version",
        k05.read_bytes() == trial_k05.read_bytes()
        and floats.read_bytes() == trial_floats.read_bytes(),
        trial_version=TRIAL_VERSION,
    )
    return finish(
        out / "rc-identity.json",
        "identity",
        checks,
        machine_class=machine_class(),
        digests=digests,
        t02_floats_sha256=sha256_bytes(floats.read_bytes()),
        note="equality across the two architectures is the CI job `identity` (G05's comparison)",
    )


# -- step 4: clean install (T08.A44) -----------------------------------------------------------


def _lock_versions() -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in (ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if "==" in line:
            name, version = line.split("==", 1)
            pins[_normalise(name)] = version.strip()
    return pins


def _normalise(name: str) -> str:
    return name.lower().replace("_", "-").replace(".", "-")


def _installed_casadi_files() -> dict[str, str]:
    """The installed CasADi package's files, by path inside `casadi/`, with their sha256."""
    import casadi  # noqa: PLC0415

    package = Path(casadi.__file__).resolve().parent
    return {
        path.relative_to(package).as_posix(): sha256_bytes(path.read_bytes())
        for path in sorted(package.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }


def step_install_check(arguments: argparse.Namespace) -> int:
    """Run with the clean environment's interpreter, from a directory outside the checkout."""
    import importlib.metadata as metadata  # noqa: PLC0415

    checks: list[dict[str, Any]] = []
    sys.path[:] = [
        entry for entry in sys.path if not Path(entry or ".").resolve().is_relative_to(ROOT)
    ]
    import openflowsheet  # noqa: PLC0415

    location = Path(openflowsheet.__file__).resolve()
    check(
        checks,
        "a44.outside_the_tree",
        not location.is_relative_to(ROOT) and not Path.cwd().resolve().is_relative_to(ROOT),
        package=str(location),
        cwd=str(Path.cwd()),
    )
    distribution = metadata.distribution("openflowsheet")
    check(
        checks,
        "a44.wheel_version",
        distribution.version == openflowsheet.__version__,
        version=distribution.version,
    )

    lock = _lock_versions()
    installed = {
        _normalise(d.metadata["Name"]): d.version
        for d in metadata.distributions()
        if _normalise(d.metadata["Name"]) not in ("pip", "openflowsheet")
    }
    off_lock = sorted(f"{n}=={v}" for n, v in installed.items() if lock.get(n) != v)
    check(
        checks,
        "a44.versions_are_the_locks",
        not off_lock and bool(installed),
        installed=len(installed),
        off_lock=off_lock,
    )
    pip_check = subprocess.run(
        [sys.executable, "-m", "pip", "check"], capture_output=True, text=True, check=False
    )
    check(checks, "a44.pip_check", pip_check.returncode == 0, output=pip_check.stdout.strip())

    sys.path.insert(0, str(ROOT / "scripts"))
    from p03_binary_inventory import _files_digest  # noqa: PLC0415

    machine = platform.machine()
    summary = json.loads((ROOT / A30_SUMMARIES[machine]).read_text(encoding="utf-8"))
    (audited,) = [d for d in summary["distributions"] if d["name"] == "casadi"]
    digest = _files_digest(metadata.distribution("casadi"))
    check(
        checks,
        "a44.casadi_files_equal_a30",
        digest == audited["files_digest"],
        found=digest,
        expected=audited["files_digest"],
        summary=str(A30_SUMMARIES[machine]),
    )
    if machine == "x86_64":
        p03 = json.loads((ROOT / P03_CASADI_INVENTORY).read_text(encoding="utf-8"))
        files = _installed_casadi_files()
        audited_files = {
            e["path"]: e["sha256"] for e in p03["files"] if not e["path"].endswith(".pyc")
        }
        differing = sorted(p for p, h in audited_files.items() if files.get(p) != h)
        check(
            checks,
            "a44.casadi_files_equal_p03",
            not differing,
            audited=len(audited_files),
            differing=differing[:20],
        )

    console = Path(sys.executable).parent / "openflowsheet"
    with tempfile.TemporaryDirectory() as scratch:
        bundle = Path(scratch) / "bundle"
        solved = subprocess.run(
            [str(console), "solve", "SYN-001-nominal", "--out", str(bundle)],
            cwd=scratch,
            env=pinned_environment(),
            capture_output=True,
            text=True,
            check=False,
        )
        check(
            checks,
            "a44.cli_solve_exit",
            solved.returncode == 0,
            stdout=solved.stdout[-2000:],
            stderr=solved.stderr[-2000:],
        )
        if solved.returncode == 0:
            from openflowsheet.run.compare import differences  # noqa: PLC0415

            manifest = json.loads((bundle / "run-manifest.json").read_text(encoding="utf-8"))
            certificate = json.loads(
                (bundle / "artifacts" / "solution-certificate.json").read_text(encoding="utf-8")
            )
            registered = json.loads((ROOT / NOMINAL_CERTIFICATE).read_text(encoding="utf-8"))
            check(
                checks,
                "a44.converged_verified",
                (manifest["outcome"], certificate["verification_status"])
                == ("CONVERGED", "VERIFIED"),
                outcome=manifest["outcome"],
                verdict=certificate["verification_status"],
            )
            ids = sorted((c["id"], c["result"]) for c in certificate["checks"])
            expected = sorted((c["id"], c["result"]) for c in registered["checks"])
            check(checks, "a44.registered_checks", ids == expected, n=len(ids))
            found = differences(
                registered, certificate, "certificate", policy_id="K04-numerical-policy-v1"
            )
            check(
                checks,
                "a44.certificate_within_policy",
                not found,
                differences=list(found)[:20],
                registered=str(NOMINAL_CERTIFICATE),
            )
            if arguments.keep:
                import shutil  # noqa: PLC0415

                shutil.copytree(bundle, arguments.keep / "SYN-001-nominal", dirs_exist_ok=True)
    return finish(arguments.out, "install-check", checks, machine=machine)


# -- step 4: the lock lookup (T08.A19) ---------------------------------------------------------

#: T08.A19 (c): the replay reason's side, by the state that replays (`run/replay.py` D4).
A19_UNKNOWN_SIDE: Final = {"installed": "both sides", "checkout": "the archive's side"}


def step_lock_check(arguments: argparse.Namespace) -> int:
    """T08.A19 (release spec Amendment R3 5). Run with the clean environment's interpreter from
    outside the checkout. `installed` imports the installed package (every checkout entry is
    dropped from `sys.path`), whose environment must contain an unrelated `requirements.lock` in
    a directory above the package; `checkout` imports this checkout's `src/`. `--bundle` is a
    `SYN-001-nominal` bundle written by the installed package's CLI, replayed here."""
    state: str = arguments.state
    checks: list[dict[str, Any]] = []
    if state == "installed":
        # The checkout's entries go; the running environment's own stay (a test's virtual
        # environment may live inside the checkout; CI's clean one never does).
        prefix = Path(sys.prefix).resolve()
        sys.path[:] = [
            entry
            for entry in sys.path
            if not Path(entry or ".").resolve().is_relative_to(ROOT)
            or Path(entry).resolve().is_relative_to(prefix)
        ]
    else:
        sys.path.insert(0, str(ROOT / "src"))
    import openflowsheet  # noqa: PLC0415
    from openflowsheet.application.revision_run import reproduce_bundle  # noqa: PLC0415
    from openflowsheet.run.bundle import read_manifest  # noqa: PLC0415
    from openflowsheet.run.manifest import environment  # noqa: PLC0415

    location = Path(openflowsheet.__file__).resolve().parent
    here = environment()
    if state == "installed":
        strays = [
            str(d / "requirements.lock")
            for d in location.parents
            if (d / "requirements.lock").is_file()
        ]
        check(
            checks,
            "a19.b_installed_outside_the_tree_beneath_a_stray_lock",
            not location.is_relative_to(ROOT) and bool(strays),
            package=str(location),
            strays=strays,
        )
        check(checks, "a19.b_lock_sha256_empty", here.lock_sha256 == "", found=here.lock_sha256)
    else:
        check(
            checks,
            "a19.a_the_checkouts_package",
            location == (ROOT / "src" / "openflowsheet").resolve(),
            package=str(location),
        )
        check(
            checks,
            "a19.a_lock_sha256_registered",
            here.lock_sha256 == LOCK_SHA256,
            found=here.lock_sha256,
            expected=LOCK_SHA256,
        )
    bundle: Path = arguments.bundle
    recorded, _ = read_manifest(bundle)
    check(
        checks,
        "a19.c_bundle_written_without_a_lock",
        recorded.environment.lock_sha256 == "",
        found=recorded.environment.lock_sha256,
    )
    side = A19_UNKNOWN_SIDE[state]
    try:
        with tempfile.TemporaryDirectory() as scratch:
            report = reproduce_bundle(
                bundle, rerun=True, rerun_directory=Path(scratch) / "rerun", run_id="rc-a19"
            ).report
        check(
            checks,
            f"a19.c_replay_by_{state}",
            report.mode == "inspected_archived_results"
            and report.verdict == "NOT_RUN"
            and any(
                r.startswith(f"the dependency set is unknown on {side}") for r in report.reasons
            ),
            mode=report.mode,
            verdict=report.verdict,
            reasons=list(report.reasons),
            expected_side=side,
        )
    except Exception as failure:  # noqa: BLE001 - T08.A19 (c): "no exception" is the assertion
        check(checks, f"a19.c_replay_by_{state}", False, exception=repr(failure))
    return finish(arguments.out, "lock-check", checks, state=state, bundle=str(bundle))


# -- step 5: the RC bundle set (T08.A45) -------------------------------------------------------


def _tests_on_path() -> None:
    for entry in (ROOT / "tests", ROOT):
        if str(entry) not in sys.path:
            sys.path.insert(0, str(entry))


def k05_registered_cases() -> list[str]:
    import yaml  # noqa: PLC0415

    document = yaml.safe_load(
        (ROOT / "benchmarks" / "syn001" / "reference_values.yaml").read_text(encoding="utf-8")
    )
    return [str(entry["case_id"]) for entry in document["variants"]]


def g8_revisions() -> list[str]:
    _tests_on_path()
    import test_t07_w3a_revision_runs as g8  # noqa: PLC0415

    return list(g8.ELIGIBLE)


def step_bundles_write(arguments: argparse.Namespace) -> int:
    _tests_on_path()
    from t07_corpus import CORPUS  # noqa: PLC0415

    from openflowsheet.application.cli import main as cli  # noqa: PLC0415
    from openflowsheet.application.policies import (  # noqa: PLC0415
        DEFAULT_POLICY_ID,
        resolve_policy,
    )
    from openflowsheet.application.revision_run import (  # noqa: PLC0415
        Route,
        run_revision_session,
        select_route,
    )
    from openflowsheet.run.bundle import read_manifest  # noqa: PLC0415
    from openflowsheet.verify.certificate import CheckPolicy  # noqa: PLC0415

    os.environ.update({name: "1" for name in THREAD_VARIABLES})
    out: Path = arguments.out
    entries: list[dict[str, Any]] = []
    for case in k05_registered_cases():
        directory = out / "k05" / _portable(case)
        with contextlib.redirect_stdout(sys.stderr):
            code = cli(["solve", case, "--out", str(directory)])
        manifest, _ = read_manifest(directory)
        entries.append(
            {
                "set": "k05",
                "name": case,
                "directory": f"k05/{_portable(case)}",
                "exit": code,
                "outcome": manifest.outcome,
                "verification_status": manifest.verification_status,
            }
        )
    for name in g8_revisions():
        document = CORPUS[name]()
        route = select_route(document)
        assert isinstance(route, Route), name
        policy = resolve_policy(DEFAULT_POLICY_ID, route.solve_path)
        assert policy is not None, name
        manifest = run_revision_session(
            route,
            document,
            out / "g8" / _portable(name),
            run_id=f"run-{name}",
            policy=policy,
            check_policy=CheckPolicy(),
            policy_requested=DEFAULT_POLICY_ID,
        )
        entries.append(
            {
                "set": "g8",
                "name": name,
                "directory": f"g8/{_portable(name)}",
                "exit": 0,
                "outcome": manifest.outcome,
                "verification_status": manifest.verification_status,
            }
        )
    counts = Counter(entry["set"] for entry in entries)
    index = {
        "format": FORMAT,
        "step": "bundles-write",
        "provenance": {**provenance(), "machine_class": machine_class()},
        "sets": {
            "k05": {
                "enumerated_by": "benchmarks/syn001/reference_values.yaml variants, CLI solve",
                "n": counts["k05"],
            },
            "g8": {
                "enumerated_by": "tests/test_t07_w3a_revision_runs.py ELIGIBLE, default policy",
                "n": counts["g8"],
            },
        },
        "n_b": len(entries),
        "entries": entries,
    }
    (out / "index.json").write_text(json.dumps(index, indent=1, sort_keys=True) + "\n")
    written = (
        all(entry["exit"] == 0 for entry in entries) and counts["k05"] > 0 and counts["g8"] > 0
    )
    print(
        f"bundles-write: {len(entries)} bundles (k05 {counts['k05']}, g8 {counts['g8']}); "
        f"{'ok' if written else 'a write failed'} ({out / 'index.json'})"
    )
    return 0 if written else 1


# -- ADR 0025 A14: the controls --------------------------------------------------------------


def reseal(source: Path, target: Path, mutate: Callable[[dict[str, Any]], str]) -> str:
    """A copy of `source`'s bundle with `mutate` applied to its documents, written again by the
    project's own writer so that its integrity holds (A14). Returns what `mutate` returns: the
    path the comparison is expected to name. The manifest keeps every field but the two that
    describe the documents: `artifact_r0_sha256` and `verification_status`."""
    from dataclasses import replace  # noqa: PLC0415

    from openflowsheet.canonical import canonical_json  # noqa: PLC0415
    from openflowsheet.run.bundle import (  # noqa: PLC0415
        read_artifact,
        read_manifest,
        write_bundle,
    )
    from openflowsheet.run.identity import r0_projection, r0_sha256  # noqa: PLC0415

    manifest, _ = read_manifest(source)
    documents = {name: read_artifact(source, name) for name in manifest.artifacts}
    expected = mutate(documents)
    certificate = documents.get("solution-certificate.json")
    write_bundle(
        target,
        replace(
            manifest,
            artifact_r0_sha256=r0_sha256(r0_projection(json.loads(canonical_json(documents)))),
            verification_status=(
                certificate["verification_status"]
                if isinstance(certificate, dict)
                else manifest.verification_status
            ),
        ),
        documents,
    )
    return expected


def c1_move_heat_rate(documents: dict[str, Any]) -> str:
    """C1: the first `heat_rate` variable of `solution-state.json` (in `variable_ids` order) moved
    by 10× its v2 tolerance; the state's digest, and the certificate's target and digest-form id,
    follow it (the bundle's own consistency check, `run.bundle`)."""
    from openflowsheet.application.revision_run import bind_route, declared_kinds  # noqa: PLC0415
    from openflowsheet.run import compare, solution_state  # noqa: PLC0415

    route = bind_route(documents["solve-path.json"]["solve_path"], documents["revision.json"])
    kinds = declared_kinds(route.binding.spec)  # type: ignore[union-attr]
    state = documents[solution_state.NAME]
    ids = state["variable_ids"]
    name = next(variable for variable in ids if kinds.get(variable) == "heat_rate")
    value = float(state["variables"][name])
    tolerance = max(compare.V2_RELATIVE_TOLERANCE * abs(value), compare.KIND_FLOOR["heat_rate"])
    moved = {**state["variables"], name: value + 10.0 * tolerance}
    documents[solution_state.NAME] = solution_state.document(ids, [moved[i] for i in ids])
    certificate = documents["solution-certificate.json"]
    digest = documents[solution_state.NAME]["state_sha256"]
    if certificate["certificate_id"] == f"cert-{certificate['target_state_sha256'][:12]}":
        certificate["certificate_id"] = f"cert-{digest[:12]}"
    certificate["target_state_sha256"] = digest
    return f"{solution_state.NAME}<root>.variables.{name}"


def c2_fail_the_verdict(documents: dict[str, Any]) -> str:
    """C2: the certificate's `verification_status` set to `FAILED`. Its precondition, that no
    near-threshold flag is present (ADR 0007 D2.4 would forgive the flip) and the verdict is not
    already `FAILED`, raises when it does not hold, also under `python -O` (T08 review 3, N6)."""
    certificate = documents["solution-certificate.json"]
    if any(entry["kind"] == "near_threshold" for entry in certificate["limitations"]):
        raise ValueError("C2's precondition: the certificate carries a near_threshold limitation")
    if any(check.get("near_threshold") for check in certificate["checks"]):
        raise ValueError("C2's precondition: a check of the certificate is near its threshold")
    if certificate["verification_status"] == "FAILED":
        raise ValueError("C2's precondition: the certificate's verdict is already FAILED")
    certificate["verification_status"] = "FAILED"
    return "solution-certificate.json<root>.verification_status"


def c3_move_a_pivot(documents: dict[str, Any]) -> str:
    """C3: one event's archived `u_diag_min_abs` × 0.6 — D4's deliberate, visible blind spot."""
    for index, event in enumerate(documents["solve-events.json"]):
        linear = event.get("linear")
        if isinstance(linear, dict) and linear.get("u_diag_min_abs"):
            linear["u_diag_min_abs"] = linear["u_diag_min_abs"] * 0.6
            return f"solve-events.json<root>[{index}].linear.u_diag_min_abs"
    raise AssertionError("no event carries a u_diag_min_abs")


A14_MUTATIONS: Final = {"c1": c1_move_heat_rate, "c2": c2_fail_the_verdict, "c3": c3_move_a_pivot}
#: The verdict each control must produce (ADR 0025 A14).
A14_EXPECTED: Final = {"c1": "MISMATCH", "c2": "MISMATCH", "c3": "MATCH"}
#: The `bitwise_floats` a control must report where it is fixed: C3's `MATCH` must come from the
#: moved pivot being read and forgiven, not from `solve-events.json` going unread (review 3, N6).
A14_BITWISE_FLOATS: Final = {"c3": False}


def run_control(control: str, source: Path, scratch: Path) -> dict[str, Any]:
    """One A14 control: mutate and re-seal a copy of `source`, check its integrity first, then
    replay it against a fresh rerun. Passes iff the verdict is A14's, for a `MISMATCH` the
    expected path is named, and `bitwise_floats` is what `A14_BITWISE_FLOATS` fixes, if anything."""
    from openflowsheet.application.revision_run import reproduce_bundle  # noqa: PLC0415
    from openflowsheet.run.bundle import read_manifest, verify_bundle  # noqa: PLC0415

    target = scratch / "controls" / control
    expected_path = reseal(source, target, A14_MUTATIONS[control])
    row: dict[str, Any] = {
        "control": control,
        "source": str(source.relative_to(source.parent.parent)),
        "numerical_policy_id": read_manifest(target)[0].numerical_policy_id,
        "mutated": expected_path,
        "expected": A14_EXPECTED[control],
        "integrity_ok": verify_bundle(target).ok,
    }
    if not row["integrity_ok"]:
        return {**row, "passed": False, "why": "the control fails integrity; it tests nothing"}
    report = reproduce_bundle(
        target, rerun=True, rerun_directory=scratch / "controls-rerun" / control, run_id="rc-a14"
    ).report
    named = any(entry.startswith(f"{expected_path}:") for entry in report.differences)
    passed = report.verdict == A14_EXPECTED[control] and (report.verdict == "MATCH" or named)
    if control in A14_BITWISE_FLOATS:
        passed = passed and report.bitwise_floats is A14_BITWISE_FLOATS[control]
    return {
        **row,
        "mode": report.mode,
        "verdict": report.verdict,
        "bitwise_floats": report.bitwise_floats,
        "differences": list(report.differences)[:10],
        "passed": passed,
    }


def step_bundles_replay(arguments: argparse.Namespace) -> int:
    from openflowsheet.application.revision_run import reproduce_bundle  # noqa: PLC0415
    from openflowsheet.run.bundle import read_manifest  # noqa: PLC0415
    from openflowsheet.run.compare import CURRENT_POLICY_ID  # noqa: PLC0415

    os.environ.update({name: "1" for name in THREAD_VARIABLES})
    bundles: Path = arguments.bundles
    index = json.loads((bundles / "index.json").read_text(encoding="utf-8"))
    here = provenance()
    checks: list[dict[str, Any]] = []
    check(
        checks,
        "a45.same_commit",
        index["provenance"]["commit"] == here["commit"],
        written_at=index["provenance"]["commit"],
        replayed_at=here["commit"],
    )
    found_dirs = sorted(
        f"{s.name}/{d.name}" for s in bundles.iterdir() if s.is_dir() for d in s.iterdir()
    )
    enumerated = sorted(entry["directory"] for entry in index["entries"])
    check(
        checks,
        "a45.n_b_equals_the_enumeration",
        found_dirs == enumerated and len(enumerated) > 0,
        n_b=len(enumerated),
        found=len(found_dirs),
    )
    rows = []
    with tempfile.TemporaryDirectory() as scratch:
        for entry in index["entries"]:
            reproduction = reproduce_bundle(
                bundles / entry["directory"],
                rerun=True,
                rerun_directory=Path(scratch) / entry["directory"],
                run_id="rc-replay",
            )
            report = reproduction.report
            rows.append(
                {
                    "directory": entry["directory"],
                    "numerical_policy_id": read_manifest(bundles / entry["directory"])[
                        0
                    ].numerical_policy_id,
                    "mode": report.mode,
                    "verdict": report.verdict,
                    "integrity_ok": report.integrity.ok,
                    "reasons": list(report.reasons),
                    "differences": list(report.differences)[:10],
                    "near_threshold": list(report.verdict_changed_near_threshold),
                    "bitwise_floats": report.bitwise_floats,
                }
            )
        directories = {
            (entry["set"], entry["name"]): entry["directory"] for entry in index["entries"]
        }
        controls = [
            run_control(control, bundles / directories[source], Path(scratch))
            for control, source in A14_CONTROL_BUNDLES.items()
        ]
    bad = [
        row["directory"]
        for row in rows
        if row["verdict"] != "MATCH"
        or row["mode"] not in ("exact_replay", "compatible_reproduction")
        or not row["integrity_ok"]
    ]
    check(
        checks,
        "a45.every_bundle_matches",
        not bad,
        failing=bad,
        modes=dict(Counter(row["mode"] for row in rows)),
        near_threshold=[r["directory"] for r in rows if r["near_threshold"]],
    )
    # ADR 0025 D1.2: a v0.1 record names T08-numerical-policy-v2, and is compared under it.
    other_policies = [r["directory"] for r in rows if r["numerical_policy_id"] != CURRENT_POLICY_ID]
    check(
        checks,
        "a45.every_bundle_records_the_current_policy",
        not other_policies,
        policy=CURRENT_POLICY_ID,
        policies=dict(Counter(row["numerical_policy_id"] for row in rows)),
        other=other_policies,
    )
    for control in controls:
        check(
            checks,
            f"a14.{control['control']}",
            control["passed"],
            expected=control["expected"],
            verdict=control.get("verdict"),
            bitwise_floats=control.get("bitwise_floats"),
            integrity_ok=control["integrity_ok"],
            mutated=control["mutated"],
        )
    per_set = Counter(entry["set"] for entry in index["entries"])
    recorded = {name: value.get("n") for name, value in index["sets"].items()}
    check(
        checks,
        "a45.every_set_enumerated",
        sorted(index["sets"]) == sorted(A45_SETS)
        and all(recorded[name] == per_set[name] > 0 for name in A45_SETS),
        sets=list(A45_SETS),
        recorded=recorded,
        counted=dict(per_set),
    )
    return finish(
        arguments.out,
        "bundles-replay",
        checks,
        provenance={**here, "machine_class": machine_class()},
        sets={name: per_set[name] for name in A45_SETS},
        n_b=len(index["entries"]),
        replays=rows,
        controls=controls,
    )


# -- step 6: the registered ensemble (T08.A46, the S3 part of A47) ------------------------------


def a34_replay_set(record: Mapping[str, Any], classify: Callable[[Any], str]) -> list[list[Any]]:
    """T06 A34's replay set of a results record: each case's first recorded start and every
    recorded start that is not `SUCCESS` (`scripts/t06_ensemble.py replay`'s default)."""
    first: dict[str, int] = {}
    for entry in record["records"]:
        first.setdefault(entry["case"], entry["start"])
    return [
        [entry["case"], entry["start"]]
        for entry in record["records"]
        if entry["start"] == first[entry["case"]] or classify(entry) != "SUCCESS"
    ]


def parse_replay(stdout: str) -> dict[str, list[list[Any]]]:
    """`scripts/t06_ensemble.py replay`'s verdict lines (`<case> <start> MATCH|DIFFER`; the
    differences follow indented) and the starts it reports not generated (F-GEN)."""
    parsed: dict[str, list[list[Any]]] = {"MATCH": [], "DIFFER": [], "not_generated": []}
    for line in stdout.splitlines():
        parts = line.split()
        if line[:1].isspace() or not parts:
            continue
        if len(parts) == 3 and parts[2] in ("MATCH", "DIFFER") and parts[1].isdigit():
            parsed[parts[2]].append([parts[0], int(parts[1])])
        elif line.endswith("not generated (F-GEN); nothing to replay"):
            parsed["not_generated"].append([line.split(":", 1)[0]])
    return parsed


def step_ensemble(arguments: argparse.Namespace) -> int:
    out: Path = arguments.out
    out.mkdir(parents=True, exist_ok=True)
    label = machine_class()
    results, report = out / f"rc-{label}.json", out / f"rc-{label}.report.txt"
    environment = pinned_environment(PYTHONPATH=str(ROOT))
    script = str(ROOT / "scripts" / "t06_ensemble.py")
    before = git("status", "--porcelain", "--", "benchmarks/t06")
    ran = subprocess.run(
        [sys.executable, script, "run", "--run-id", "rc", "--out", str(results)],
        cwd=ROOT,
        env=environment,
        check=False,
    )
    reported = subprocess.run(
        [sys.executable, script, "report", str(results), "--out", str(report)],
        cwd=ROOT,
        env=environment,
        check=False,
    )
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "scripts"))
    import t06_ensemble  # noqa: PLC0415

    from benchmarks.t06 import ensemble  # noqa: PLC0415

    record = json.loads(results.read_text(encoding="utf-8")) if results.is_file() else None
    if record is None:
        checks0: list[dict[str, Any]] = []
        check(checks0, "a46.run_and_report", False, run_exit=ran.returncode)
        return finish(out / f"rc-ensemble-{label}.json", "ensemble", checks0)
    _, summary, _ = t06_ensemble.render(record)
    classes = Counter(ensemble.classify(r) for r in record["records"])
    verified_outside_s3 = [
        (r["case"], r["start"]) for r in record["records"] if ensemble.classify(r) == "F-OTHER-ROOT"
    ]
    worst = max(
        (float(r["worst"][0]) for r in record["records"] if ensemble.classify(r) == "SUCCESS"),
        default=None,
    )
    checks: list[dict[str, Any]] = []
    label = str(record["host"]["machine_class"])
    check(
        checks, "a46.registered_class", not label.startswith("unregistered("), machine_class=label
    )
    check(
        checks,
        "a46.run_and_report",
        ran.returncode == 0 and reported.returncode == 0,
        run_exit=ran.returncode,
        report_exit=reported.returncode,
    )
    check(
        checks,
        "a46.gate",
        bool(summary and summary["gate"]["pass"]),
        gate=summary["gate"] if summary else None,
        classes=dict(classes),
    )
    check(
        checks,
        "a47.no_verified_outside_s3",
        not verified_outside_s3,
        found=verified_outside_s3,
        worst_ratio_success=worst,
    )
    check(
        checks,
        "a34.ensemble_certificates",
        bool(summary) and summary.get("a33_failures") == 0,
        a33_failures=summary.get("a33_failures") if summary else None,
        rule="T06 A33 (A4) on every certificate of the run, as the harness records it",
    )
    # T06 A34 in its registered form (Amendment R3 1): the run's first start of every case and
    # every retained failure, rerun on this same machine class and compared on every field.
    replayed = subprocess.run(
        [sys.executable, script, "replay", str(results)],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    (out / f"rc-{label}.replay.txt").write_text(replayed.stdout + replayed.stderr, "utf-8")
    parsed = parse_replay(replayed.stdout)
    expected = a34_replay_set(record, ensemble.classify)
    replay_class = machine_class()
    check(
        checks,
        "a46.t06_a34_same_class_replay",
        replayed.returncode == 0
        and replay_class == label
        and not parsed["DIFFER"]
        and len(parsed["MATCH"]) > 0
        and len(parsed["MATCH"]) + len(parsed["not_generated"]) == len(expected),
        replay_exit=replayed.returncode,
        run_class=label,
        replay_class=replay_class,
        replay_set=len(expected),
        match=len(parsed["MATCH"]),
        differ=parsed["DIFFER"],
        not_generated=len(parsed["not_generated"]),
        rule="T06 A34: same machine class, MATCH on every field (K04-numerical-policy-v1)",
    )
    check(
        checks,
        "a46.registered_runs_untouched",
        git("status", "--porcelain", "--", "benchmarks/t06") == before == "",
    )
    return finish(
        out / f"rc-ensemble-{label}.json",
        "ensemble",
        checks,
        provenance={k: record.get(k) for k in ("commit", "tree_clean", "environment_lock_sha256")}
        | {"machine_class": label},
        results=str(results),
        replay=str(out / f"rc-{label}.replay.txt"),
    )


# -- step 7: the corpus and the references (T08.A47, A48) ----------------------------------------


class _Recorder:
    """Every node's worst outcome over setup, call and teardown; a collection error fails."""

    RANK: Final = {"passed": 0, "xfailed": 1, "skipped": 2, "xpassed": 3, "failed": 4}

    def __init__(self) -> None:
        self.outcomes: dict[str, str] = {}

    def pytest_runtest_logreport(self, report: Any) -> None:
        outcome = (
            ("xfailed" if report.skipped else "xpassed")
            if hasattr(report, "wasxfail")
            else str(report.outcome)
        )
        if self.RANK[outcome] >= self.RANK[self.outcomes.get(report.nodeid, "passed")]:
            self.outcomes[report.nodeid] = outcome

    def pytest_collectreport(self, report: Any) -> None:
        if report.failed:
            self.outcomes[report.nodeid or "collection"] = "failed"


def registered_functions(identifiers: Iterable[str]) -> dict[str, list[str]]:
    """The test functions the T06 manifest names for each assertion (`value.tests.functions`)."""
    manifest = json.loads((ROOT / T06_MANIFEST).read_text(encoding="utf-8"))
    by_id = {entry["id"]: entry for entry in manifest["checks"]}
    return {i: list(by_id[i]["value"]["tests"]["functions"]) for i in identifiers}


def judge(functions: Sequence[str], outcomes: Mapping[str, str]) -> dict[str, Any]:
    nodes = {n: o for n, o in outcomes.items() if n.split("[", 1)[0] in functions}
    ran = {n.split("[", 1)[0] for n in nodes}
    return {
        "nodes": len(nodes),
        "outcomes": dict(Counter(nodes.values())),
        "missing": [f for f in functions if f not in ran],
        "failed": sorted(n for n, o in nodes.items() if o in ("failed", "xpassed")),
        "skipped": sorted(n for n, o in nodes.items() if o == "skipped"),
    }


def step_corpus(arguments: argparse.Namespace) -> int:
    import pytest  # noqa: PLC0415

    os.environ.update({name: "1" for name in THREAD_VARIABLES})
    named = registered_functions((*A47_ASSERTIONS, *A48_ASSERTIONS))
    functions = sorted({f for fs in named.values() for f in fs})
    recorder = _Recorder()
    with contextlib.chdir(ROOT):
        exit_code = int(
            pytest.main(["-q", "-p", "no:cacheprovider", *functions], plugins=[recorder])
        )
    checks: list[dict[str, Any]] = []
    for identifier, fs in named.items():
        value = judge(fs, recorder.outcomes)
        group = "a47" if identifier in A47_ASSERTIONS else "a48"
        check(
            checks,
            f"{group}.{identifier}",
            not (value["missing"] or value["failed"] or value["skipped"]) and value["nodes"] > 0,
            **value,
        )
    return finish(
        arguments.out,
        "corpus",
        checks,
        pytest_exit=exit_code,
        provenance={**provenance(), "machine_class": machine_class()},
    )


# -- step 8: the agent surface (T08.A49) --------------------------------------------------------


def surface_digests() -> dict[str, str]:
    _tests_on_path()
    from benchmarks.t07.v17 import harness  # noqa: PLC0415
    from openflowsheet.application.bindings import mcp  # noqa: PLC0415

    texts = ROOT / "tests" / "fixtures" / "t08" / "v17_c2_descriptions"
    served = mcp.description
    mcp.tools.cache_clear()
    now = harness.tool_descriptions_sha256()

    def restored(operation: Any) -> str:
        kept = texts / f"{operation.name}.md"
        return kept.read_text("utf-8") if kept.is_file() else str(served(operation))

    mcp.description = restored
    mcp.tools.cache_clear()
    try:
        v17_c2 = harness.tool_descriptions_sha256()
    finally:
        mcp.description = served
        mcp.tools.cache_clear()
    return {"served": now, "with_v17_c2_texts": v17_c2}


def step_surface(arguments: argparse.Namespace) -> int:
    _tests_on_path()
    from benchmarks.t07.v17 import reference  # noqa: PLC0415

    os.environ.update({name: "1" for name in THREAD_VARIABLES})
    out: Path = arguments.out
    digests = surface_digests()
    checks: list[dict[str, Any]] = []
    check(
        checks,
        "a49.descriptions_digest_r133",
        digests["served"] == R133_DESCRIPTIONS_SHA256,
        served=digests["served"],
        r133=R133_DESCRIPTIONS_SHA256,
        equals_v17_c2_as_written=digests["served"] == V17_C2_DESCRIPTIONS_SHA256,
    )
    check(
        checks,
        "a49.schemas_and_other_texts_are_v17_c2s",
        digests["with_v17_c2_texts"] == V17_C2_DESCRIPTIONS_SHA256,
        found=digests["with_v17_c2_texts"],
        v17_c2=V17_C2_DESCRIPTIONS_SHA256,
    )
    runs: list[dict[str, Any]] = []
    expected_class = machine_class()
    for task in reference.TASKS:
        for transport in reference.TRANSPORTS:
            record = reference.run(task, transport, out / "g16b" / task / transport)
            numbers = reference.verdict(record)
            run = json.loads((record.directory / "run.json").read_bytes())
            conditions = record.scores["completion"]["conditions"]
            runs.append(
                {
                    "task": task,
                    "transport": transport,
                    "clean": bool(reference.clean(numbers))
                    and all(conditions.values())
                    and record.scores["infrastructure_failure"] is None,
                    "attributable": run["provenance"].get("machine_class") == expected_class
                    and run["provenance"].get("tree_clean") is not None,
                }
            )
    clean = sum(run["clean"] for run in runs)
    check(
        checks,
        "a49.g16b_clean",
        clean == len(runs) == 40,
        clean=clean,
        runs=len(runs),
        not_clean=[(r["task"], r["transport"]) for r in runs if not r["clean"]],
    )
    check(checks, "a16.g16b_records_attributable", all(r["attributable"] for r in runs))
    return finish(
        out / "rc-surface.json",
        "surface",
        checks,
        digests=digests,
        runs=runs,
        provenance={**provenance(), "machine_class": expected_class},
    )


# -- step 10: the certificate audit (T08.A34) ---------------------------------------------------


def _schema_validator() -> Any:
    from jsonschema import Draft202012Validator  # noqa: PLC0415
    from referencing import Registry, Resource  # noqa: PLC0415
    from referencing.jsonschema import DRAFT202012  # noqa: PLC0415

    documents = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((ROOT / "schemas").glob("*.schema.json"))
    ]
    registry = Registry().with_resources(
        (d["$id"], Resource(contents=d, specification=DRAFT202012)) for d in documents
    )
    (certificate,) = [
        d for d in documents if d["$id"].endswith("/solution-certificate.schema.json")
    ]
    return Draft202012Validator(certificate, registry=registry)


A33_PREFIXES: Final = ("energy_balance.", "phase_admissibility.", "independent_split.")
SHARED_PROVIDER: Final = "shares the property provider with the solver: "


def audit_certificate(document: Mapping[str, Any], validator: Any) -> list[str]:
    """[A08] and [A09] on one certificate document: schema-valid (the regularity evidence is
    required and is of the Jacobian evaluated at the final state); the qualified check ids are
    exactly the prefixed checks whose result is `pass` or `fail` (T06 A33 (A4)); each entry
    names the provider the shared-provider statement names."""
    problems = [f"schema: {error.message}" for error in validator.iter_errors(document)][:3]
    expected = {
        c["id"]
        for c in document.get("checks", [])
        if c["id"].startswith(A33_PREFIXES) and c["result"] in ("pass", "fail")
    }
    qualified = document.get("independence_qualifications", [])
    if {q["check_id"] for q in qualified} != expected:
        problems.append("a09.qualified_check_ids")
    statements = [s for s in document.get("statements", []) if s.startswith(SHARED_PROVIDER)]
    if expected and len(statements) != 1:
        problems.append("a09.shared_provider_statement")
    elif statements:
        named = dict(
            part.split("=", 1)
            for part in statements[0][len(SHARED_PROVIDER) :].split(";", 1)[0].split(", ")
        )
        for entry in qualified:
            if any(
                str(entry[k]) != named.get(k)
                for k in (
                    "provider_id",
                    "implementation_sha256",
                    "data_sha256",
                    "reference_convention",
                )
            ):
                problems.append(f"a09.provider({entry['check_id']})")
                break
    return problems


def step_certificates(arguments: argparse.Namespace) -> int:
    validator = _schema_validator()
    audited: dict[str, list[str]] = {}
    for root in arguments.inputs:
        for path in sorted(Path(root).rglob("solution-certificate.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            audited[str(path)] = audit_certificate(document, validator)
    violations = {path: problems for path, problems in audited.items() if problems}
    checks: list[dict[str, Any]] = []
    check(checks, "a34.certificates_audited", len(audited) > 0, certificates=len(audited))
    check(
        checks,
        "a34.violations",
        not violations,
        violations=len(violations),
        first=dict(list(violations.items())[:10]),
    )
    return finish(arguments.out, "certificates", checks, inputs=[str(p) for p in arguments.inputs])


# -- the command line -------------------------------------------------------------------------

STEPS: Final[dict[str, Callable[[argparse.Namespace], int]]] = {
    "identity": step_identity,
    "install-check": step_install_check,
    "lock-check": step_lock_check,
    "bundles-write": step_bundles_write,
    "bundles-replay": step_bundles_replay,
    "ensemble": step_ensemble,
    "corpus": step_corpus,
    "surface": step_surface,
    "certificates": step_certificates,
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="step", required=True)
    for name in ("identity", "bundles-write", "ensemble", "surface"):
        commands.add_parser(name).add_argument("--out", type=Path, required=True)
    for name in ("corpus",):
        commands.add_parser(name).add_argument("--out", type=Path, required=True)
    install = commands.add_parser("install-check")
    install.add_argument("--out", type=Path, required=True)
    install.add_argument("--keep", type=Path, default=None, help="copy the smoke bundle here")
    lock = commands.add_parser("lock-check")
    lock.add_argument("--state", choices=sorted(A19_UNKNOWN_SIDE), required=True)
    lock.add_argument("--bundle", type=Path, required=True, help="a bundle the installed CLI wrote")
    lock.add_argument("--out", type=Path, required=True)
    replay = commands.add_parser("bundles-replay")
    replay.add_argument("--bundles", type=Path, required=True)
    replay.add_argument("--out", type=Path, required=True)
    certificates = commands.add_parser("certificates")
    certificates.add_argument("--out", type=Path, required=True)
    certificates.add_argument("inputs", type=Path, nargs="+")
    arguments = parser.parse_args(argv)
    arguments.out = arguments.out.resolve()
    return STEPS[arguments.step](arguments)


if __name__ == "__main__":
    sys.exit(main())
