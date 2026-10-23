"""Generate `evidence/S07/<commit>/manifest.json` by running, not by transcribing. S07.

Spec `docs/derivations/S07-spec.md` §13 (as extended by §16.15, §17 and §19) is the check list and
§9, §16.10, §17.5 and §19.7 the assertion tables (A01-A50). Everything recorded is produced here,
at the checked-out commit (the script refuses to run when `HEAD` is not `--commit` or when a
tracked source, test, script, schema or derivation file differs from it; S01's rule). Run it with
the CoolProp scratch venv (`requirements-coolprop.lock`, `--no-deps --require-hashes`; it also
needs mpmath for the reference generator) and `OPENFLOWSHEET_REQUIRE_COOLPROP=1`:

1. **The S07 tests** (`tests/test_s07_*.py` and `tests/test_m07_mr12_extras_v02.py` for A44; one
   `pytest --junitxml` run). A test cites the assertions its function name carries (`_aNN`), the
   near-critical tests by `_nN` (N1..N6 are A45..A50), the refusal probes by their parameter and
   A44's two git-backed nodes by `CITED_BY_NAME`. `S07.Axx` passes only if at least one node cites
   it and every node citing it passed: a failure, an error or a skip leaves it `fail`. A29's built
   sdist and wheel run with `OFS_S07_BUILD_PYTHON`, a scratch venv holding T08.A43's pinned
   setuptools that this script builds. `S07.tests` also requires that no node of the run skipped.
2. **The reference generator's `--check`** (all claims, both outputs byte-identical), at the
   default `--jobs` and at `--jobs 1` (§16.15: the byte-identity check), with their wall times.
3. **The licence inventory** (`t07_licence_inventory.py --extra coolprop`), judged against the
   committed record and the lock's two wheel hashes.
4. **The measured worsts** (A17 floors of tier A and tier B; tier B's A03, A05 worsts), the fluid
   count, tiers, bounds, the exclusions and the number of fluids reporting `published-check`.
5. **A31**: the digest's own `--check` and `--report` on this machine, and CI's lines on both
   architectures (`--ci-run <id>`: the run must be of this commit; absent: `S07.ci` fails).
6. **The S05 section** (docs/S07_DECISIONS.md, "S05 A33 evidence carried in S07's manifest"): the
   S05 suites, `s05_reference.py --check`, and the registered record digests G7(b) (S05) and G2
   (S07) of `s07_measurements/recplug.py`.
7. **`ruff check`, `ruff format --check`** on S07's files and **`mypy`** (the project's own
   configuration).

`scripts/gate.sh` is not run here (it runs once before merge): its check is `unsupported`.
`status` is computed, never written: `tested` iff every assertion A01-A50 and every required
check passes; otherwise `implemented`. Both review fields stay `pending`.

Usage:
    OPENFLOWSHEET_REQUIRE_COOLPROP=1 PYTHONPATH=src $VENV/bin/python \\
        scripts/s07_evidence_manifest.py \\
        --ci-run <run id> [--commit SHA] [--out PATH]
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parent))
from s01_evidence_manifest import (  # noqa: E402  (S01's generic helpers, unchanged)
    LOCK,
    ROOT,
    SCHEMA,
    Node,
    check,
    command,
    nodes,
    refuse_unless_measuring,
    run,
    sha256_file,
    shown,
    text,
)

SPEC = ROOT / "docs" / "derivations" / "S07-spec.md"
SCRIPTS = ROOT / "docs" / "derivations" / "scripts"
MEASUREMENTS = SCRIPTS / "s07_measurements"
REFERENCE = SCRIPTS / "s07_reference.json"
GENERATOR = SCRIPTS / "s07_reference.py"
S05_GENERATOR = SCRIPTS / "s05_reference.py"
DIGEST = ROOT / "benchmarks" / "s07" / "platform_digest.json"
PUBLISHED = ROOT / "benchmarks" / "s07" / "published_checks.yaml"
MODULE = ROOT / "src" / "openflowsheet" / "thermo" / "coolprop_heos.py"
TABLE = ROOT / "src" / "openflowsheet" / "thermo" / "_coolprop_heos_fluids.py"
LICENCES = ROOT / "docs" / "s07-coolprop-licences.json"
COOLPROP_LOCK = ROOT / "requirements-coolprop.lock"
DECISIONS = ROOT / "docs" / "S07_DECISIONS.md"
NEAR_CRITICAL_NOTE = ROOT / "docs" / "design" / "S07-near-critical-saturation.md"
SOURCES = (
    "src/openflowsheet/thermo/coolprop_heos.py",
    "src/openflowsheet/thermo/_coolprop_heos_fluids.py",
)
SCRIPT_FILES = (
    "scripts/s07_evidence_manifest.py",
    "scripts/s07_platform_digest.py",
)
ASSERTIONS = tuple(f"A{index:02d}" for index in range(1, 51))
REQUIRED_CHECKS = (
    "S07.tests",
    "S07.generator",
    "S07.generator_jobs1",
    "S07.licences",
    "S07.measured",
    "S07.digest",
    "S07.ci",
    "S07.G2",
    "S07.S05.suites",
    "S07.S05.generator",
    "S07.S05.G7b",
    "S07.ruff",
    "S07.format",
    "S07.mypy",
)
#: An assertion id in a test function's name: `_aNN`, then `_` or the end.
CITED = re.compile(r"(?:^|_)a(\d{2})(?=_|$)")
#: The near-critical tests (spec §19.7): N1..N6 are A45..A50.
N_TESTS = re.compile(r"(?:^|_)n(\d)(?=_|$)")
#: The refusal probes are one parametrized function; the tag is in the parameter id.
PARAMETER = re.compile(r"(?:^|[-\[])A(\d{2})(?=[-\]]|$)")
#: Nodes that cite an assertion without `_aNN` in their name.
CITED_BY_NAME = {
    "tests/test_m07_mr12_extras_v02.py::test_the_git_backed_measure_at_head": ("A44",),
    "tests/test_m07_mr12_extras_v02.py::test_the_git_backed_measure_at_the_v0_2_0_commit": ("A44",),
}
#: The record digests of `s07_measurements/recplug.py` (docs/S07_DECISIONS.md "Review fixes").
G2_DIGEST = "2d95732312c94945c91527854c97f9f7c1f4056bf7b3068a69d7ad944779ceb3"
G2_KEYS = 35890
G7B_DIGEST = "2bd5e0edc2f1dd001b89d51a313c4fd728481086a2f75493bacd151fccfd7b8e"
G7B_KEYS = 22782
G2_FILES = ("tests/test_s07_broad.py", "tests/test_s07_coolprop.py", "tests/test_s07_packaging.py")
G7B_FILES = (
    "tests/test_s05_envelope.py",
    "tests/test_s05_iapws95.py",
    "tests/test_s05_review_adversarial.py",
)
#: The check jobs' steps whose conclusions are read on each architecture (ci.yml).
CI_STEPS = ("S07 tests (spec §13)", "S07 A31 line (spec §9, Q-1)")
ARCHITECTURES = {"ubuntu-latest": "x86_64", "ubuntu-24.04-arm": "aarch64"}

#: The U02 limitation; T08 C3 requires its harvest note to name the id and library-only.
LIBRARY_ONLY = (
    "`coolprop-heos-v1` is library-only (R-568, R-569, R-621): it is not in "
    "revision_binding.SELECTABLE_BASES, so no revision can select it and no development case "
    "becomes runnable (U02); it is registered in the T08 envelope's LIBRARY_ONLY_PROVIDERS and its "
    "scanned_providers (spec §3.4, A30). Coverage counts are unchanged."
)


# -- the specification ---------------------------------------------------------------------------


def assertion_table(document: str) -> dict[str, tuple[str, str]]:
    """id -> (assertion, expectation) from every table row `| Axx (Nn)? | ... |`, the first
    definition winning (§9's, then §16.10's new rows, §17.5's and §19.7's)."""
    rows: dict[str, tuple[str, str]] = {}
    for line in document.splitlines():
        match = re.match(r"^\| (A\d{2})(?: \(N\d\))? \| (.*) \|$", line)
        if match is None:
            continue
        cells = [cell.strip() for cell in match.group(2).split(" | ")]
        rows.setdefault(match.group(1), (cells[0], cells[1] if len(cells) > 1 else ""))
    if tuple(sorted(rows)) != ASSERTIONS:
        raise SystemExit(f"the assertion ids of the spec are {sorted(rows)}, not A01-A50")
    return {identifier: rows[identifier] for identifier in ASSERTIONS}


# -- the tests -----------------------------------------------------------------------------------


def cited(node: str) -> tuple[str, ...]:
    """The assertion ids a test node cites (see the module docstring)."""
    if node in CITED_BY_NAME:
        return CITED_BY_NAME[node]
    name, _, parameters = node.rsplit("::", 1)[-1].partition("[")
    found = [f"A{number}" for number in CITED.findall(name)]
    found += [f"A{44 + int(number)}" for number in N_TESTS.findall(name)]
    if name == "test_refusal_probes":
        found += [f"A{number}" for number in PARAMETER.findall(parameters.rstrip("]"))]
    return tuple(found)


def verdict(citing: Sequence[Node]) -> tuple[str, dict[str, Any]]:
    not_passed = [
        {"node": text(item.node), "outcome": item.outcome, "message": text(item.message[:600])}
        for item in citing
        if item.outcome != "passed"
    ]
    value = {
        "judged_by": "tests",
        "nodes": len(citing),
        "outcomes": dict(sorted(Counter(item.outcome for item in citing).items())),
        "not_passed": not_passed,
    }
    return ("pass" if citing and not not_passed else "fail"), value


def assertion_checks(
    rows: Mapping[str, tuple[str, str]],
    tests: Sequence[Node],
    extra: Mapping[str, tuple[bool, dict[str, Any]]],
) -> list[dict[str, Any]]:
    """One check per assertion; `extra` adds a measured half that must also pass."""
    entries: list[dict[str, Any]] = []
    for identifier in ASSERTIONS:
        result, value = verdict([item for item in tests if identifier in cited(item.node)])
        if identifier in extra:
            passed, measured = extra[identifier]
            value = {**value, "measured": measured}
            result = "pass" if result == "pass" and passed else "fail"
        assertion, expected = rows[identifier]
        entries.append(check(f"S07.{identifier}", assertion, result, value, text(expected) or None))
    return entries


# -- environments and subprocesses ---------------------------------------------------------------


def build_python(work: Path) -> tuple[str, str]:
    """A scratch venv with T08.A43's setuptools pin, for A29's sdist and wheel (network: PyPI)."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import t08_dist

    python, version = t08_dist.build_environment(work / "build-venv", t08_dist.SETUPTOOLS)
    return str(python), version


@dataclasses.dataclass
class Timed:
    cmd: str
    exit_code: int
    stdout: str
    seconds: float


def start(argv: Sequence[str], environment: Mapping[str, str] | None = None) -> Any:
    merged = {**os.environ, "PYTHONPATH": str(ROOT / "src"), **(environment or {})}
    process = subprocess.Popen(
        list(argv),
        cwd=ROOT,
        env=merged,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    process.started = time.monotonic()  # type: ignore[attr-defined]
    process.argv = list(argv)  # type: ignore[attr-defined]
    return process


def finish(process: Any, label: str | None = None) -> Timed:
    out, _ = process.communicate()
    seconds = time.monotonic() - process.started
    cmd = "PYTHONPATH=src " + " ".join(
        shown(part) if os.path.isabs(part) else part for part in process.argv
    )
    return Timed(label or cmd, process.returncode, out, seconds)


def entry(timed: Timed) -> Any:
    from s01_evidence_manifest import Run

    return Run(timed.cmd, timed.exit_code, timed.stdout)


# -- the measured halves -------------------------------------------------------------------------


def licence_check(artifacts: Path) -> tuple[bool, dict[str, Any], Any]:
    out = artifacts / "s07-coolprop-licences.json"
    ran = run(
        [
            sys.executable,
            str(ROOT / "scripts" / "t07_licence_inventory.py"),
            "--extra",
            "coolprop",
            "--out",
            str(out),
        ],
        pythonpath=True,
    )
    produced = json.loads(out.read_text("utf-8")) if out.is_file() else {}
    committed = json.loads(LICENCES.read_text("utf-8"))

    def bare(record: Mapping[str, Any]) -> Any:
        rows = [{k: v for k, v in row.items() if k != "wheels"} for row in record["distributions"]]
        return {**record, "distributions": rows}

    lock = COOLPROP_LOCK.read_text("utf-8")
    wheels = {
        arch: info["sha256"] for arch, info in committed["distributions"][0]["wheels"].items()
    }
    hashes_in_lock = sorted(re.findall(r"--hash=sha256:([0-9a-f]{64})", lock))
    parts = {
        "exit_code_0": ran.exit_code == 0,
        "equals_the_committed_record_apart_from_the_wheels": bare(produced) == bare(committed),
        "both_wheel_hashes_are_the_locks": sorted(wheels.values()) == hashes_in_lock
        and len(wheels) == 2,
        "no_failures": committed["failures"] == [],
    }
    measured = {
        "cmd": ran.cmd,
        "exit_code": ran.exit_code,
        "parts": parts,
        "wheel_sha256": wheels,
        "record_sha256": sha256_file(LICENCES),
    }
    return all(parts.values()), measured, ran


def a17_floors() -> dict[str, Any]:
    """The A17 floors (max FD ratio) per fluid, tier A over the test's own cases and tier B over
    its six TP states; imports the test modules (`PYTHONPATH=src`, CoolProp)."""
    sys.path[:0] = [str(ROOT / "tests"), str(ROOT)]
    import test_s07_broad as broad
    import test_s07_coolprop as tier_a

    floors: dict[str, float] = {}
    for cid in tier_a.TIER_A:
        worst = 0.0
        for t, p, phase, wrt, kind, _ in tier_a.fd_cases(cid):
            ratios = tier_a.fd_ratios(tier_a.PROVIDERS[cid], cid, t, p, phase, wrt, kind)
            worst = max(worst, *ratios.values())
        floors[cid] = worst
    for cid in broad.TIER_B:
        floors[cid] = max(broad.a17_worst(cid).values())
    tier_a_worst = max((floors[c], c) for c in tier_a.TIER_A)
    tier_b_worst = max((floors[c], c) for c in broad.TIER_B)
    return {
        "tier_a_worst": list(tier_a_worst),
        "tier_b_worst": list(tier_b_worst),
        "tier_b_above_1e-11": sorted(c for c in broad.TIER_B if floors[c] > 1e-11),
        "per_fluid": floors,
    }


def measured_records(artifacts: Path) -> tuple[bool, dict[str, Any], Any]:
    """The fluid count, tiers, bounds, exclusions, published checks, A17 floors and tier B's
    A03/A05 worsts (`wo2b_worsts.py`)."""
    from openflowsheet.thermo import _coolprop_heos_fluids as table
    from openflowsheet.thermo import coolprop_heos as cph

    reference = json.loads(REFERENCE.read_text("utf-8"))
    rows = table.FLUIDS
    tiers = Counter(row["tier"] for row in rows)
    published = [
        row["id"]
        for row in rows
        if cph.CoolPropHeosProvider(row["id"])
        .describe()
        .uncertainty.startswith("verification: published-check")
    ]
    worsts_json = artifacts / "s07-wo2b-worsts.json"
    worsts = run(
        [sys.executable, str(MEASUREMENTS / "wo2b_worsts.py"), str(worsts_json)],
        pythonpath=True,
    )
    worst_lines = [line for line in worsts.stdout.splitlines() if line.startswith(("A0", "A1"))]
    floors = a17_floors()
    parts = {
        "count_123": len(rows) == 123 and len(reference["fluids"]) == 123,
        "tiers_9_and_114": dict(tiers) == {"A": 9, "B": 114},
        "excluded_13_with_reasons": len(reference["excluded"]) == 13
        and all(isinstance(reason, str) and reason for _, reason in reference["excluded"]),
        "published_checks_0": published == [] and reference["published_checks"]["rows"] == {},
        "worsts_ran": worsts.exit_code == 0,
        "tier_a_a17_below_1e-11": floors["tier_a_worst"][0] <= 1e-11,
    }
    measured = {
        "fluids": len(rows),
        "tiers": dict(tiers),
        "bounds": dict(Counter(f"{row['tier']}/{row['bound']}" for row in rows)),
        "per_fluid_tier_and_bound": {row["id"]: f"{row['tier']}/{row['bound']}" for row in rows},
        "excluded": [list(pair) for pair in reference["excluded"]],
        "published_check_fluids": len(published),
        "a17": {k: v for k, v in floors.items() if k != "per_fluid"},
        "a17_per_fluid": floors["per_fluid"],
        "tier_b_worsts": worst_lines,
        "worsts_json_sha256": sha256_file(worsts_json) if worsts_json.is_file() else None,
        "parts": parts,
    }
    return all(parts.values()), measured, worsts


def digest_checks() -> tuple[bool, dict[str, Any], list[Any]]:
    """A31 here: the digest file is the script's output, and the comparison is bitwise."""
    checked = run(
        [sys.executable, str(ROOT / "scripts" / "s07_platform_digest.py"), "--check"],
        pythonpath=True,
    )
    reported = run(
        [sys.executable, str(ROOT / "scripts" / "s07_platform_digest.py"), "--report"],
        pythonpath=True,
    )
    line = reported.stdout.strip().splitlines()[0] if reported.stdout.strip() else ""
    measured = {
        "digest_sha256": sha256_file(DIGEST),
        "check": [text(x) for x in checked.stdout.strip().splitlines()[-1:]],
        "report": text(line),
    }
    passed = checked.exit_code == 0 and reported.exit_code == 0 and "bit-identical" in line
    return passed, measured, [checked, reported]


def ci_evidence(run_id: str | None, commit: str) -> tuple[bool, dict[str, Any], list[Any]]:
    """Both architectures' check jobs of the CI run of this commit: the S07 steps and their A31
    lines (Q-1's measurement). `gh` is read-only here."""
    if not run_id:
        return False, {"error": "--ci-run <id> was not given: aarch64 is not measured"}, []
    listing = run(["gh", "run", "view", run_id, "--json", "headSha,conclusion,status,url,jobs"])
    if listing.exit_code != 0:
        return False, {"error": text(listing.stdout[-400:])}, [listing]
    data = json.loads(listing.stdout)
    ran = [listing]
    per_arch: dict[str, Any] = {}
    for job in data["jobs"]:
        name = str(job["name"])
        match = re.fullmatch(r"check \((.+)\)", name)
        if match is None or match.group(1) not in ARCHITECTURES:
            continue
        steps = {step["name"]: step["conclusion"] for step in job["steps"]}
        log = run(["gh", "run", "view", run_id, "--job", str(job["databaseId"]), "--log"])
        ran.append(log)
        lines = sorted(
            {
                re.sub(r"^.*?(S07 A31 \()", r"\1", line)
                for line in log.stdout.splitlines()
                if "S07 A31 (" in line
            }
        )
        per_arch[ARCHITECTURES[match.group(1)]] = {
            "job": name,
            "job_conclusion": job["conclusion"],
            "steps": {step: steps.get(step) for step in CI_STEPS},
            "a31_lines": [text(line) for line in lines],
        }
    parts = {
        "run_is_of_this_commit": data["headSha"] == commit,
        "both_architectures": sorted(per_arch) == ["aarch64", "x86_64"],
        "s07_steps_succeeded": bool(per_arch)
        and all(
            info["steps"][step] == "success" for info in per_arch.values() for step in CI_STEPS
        ),
        "a31_line_per_architecture_without_failure": bool(per_arch)
        and all(
            len(info["a31_lines"]) == 1 and "FAILS" not in info["a31_lines"][0]
            for info in per_arch.values()
        ),
    }
    measured = {
        "run": run_id,
        "url": data["url"],
        "head_sha": data["headSha"],
        "status": data["status"],
        "conclusion": data["conclusion"],
        "architectures": per_arch,
        "parts": parts,
    }
    return all(parts.values()), measured, ran


def record_digest(files: Sequence[str], path: Path, extra: str = "") -> Timed:
    """pytest over `files` with `recplug`, writing `path`."""
    environment = {
        "PYTHONPATH": f"{ROOT / 'src'}:{ROOT}:{MEASUREMENTS}",
        "REC_OUT": str(path),
        "OPENFLOWSHEET_REQUIRE_COOLPROP": "1",
    }
    process = start(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "recplug", *files],
        environment,
    )
    timed = finish(process)
    return Timed(
        "REC_OUT=<record> " + timed.cmd.replace(f"{MEASUREMENTS}", "s07_measurements") + extra,
        timed.exit_code,
        timed.stdout,
        timed.seconds,
    )


def digest_part(files: Sequence[str], keys: int, expected: str, label: str, artifacts: Path):
    record = artifacts / f"{label}.rec"
    timed = record_digest(files, record)
    got = hashlib.sha256(record.read_bytes()).hexdigest() if record.is_file() else ""
    lines = record.read_text("utf-8").splitlines() if record.is_file() else []
    measured = {
        "cmd": timed.cmd,
        "exit_code": timed.exit_code,
        "sha256": got,
        "expected_sha256": expected,
        "calls": len(lines),
        "distinct_calls": len(set(lines)),
        "expected_keys": keys,
        "tests_tail": [text(x) for x in timed.stdout.strip().splitlines()[-1:]],
        "seconds": round(timed.seconds, 1),
    }
    passed = timed.exit_code == 0 and got == expected and len(set(lines)) == keys
    return passed, measured, timed


# -- the manifest --------------------------------------------------------------------------------


def status(entries: Sequence[Mapping[str, Any]]) -> str:
    """`tested` iff every registered assertion and every required check passes."""
    required = {f"S07.{identifier}" for identifier in ASSERTIONS} | set(REQUIRED_CHECKS)
    results = {entry["id"]: entry["result"] for entry in entries}
    missing = required - set(results)
    if missing:
        raise SystemExit(f"checks missing: {sorted(missing)}")
    return "tested" if all(results[name] == "pass" for name in required) else "implemented"


def limitations(entries: Sequence[Mapping[str, Any]], measured: Mapping[str, Any]) -> list[str]:
    reference = json.loads(REFERENCE.read_text("utf-8"))
    ci = next(item for item in entries if item["id"] == "S07.ci")["value"]
    lines = {
        arch: info["a31_lines"][0]
        for arch, info in (ci.get("architectures") or {}).items()
        if info["a31_lines"]
    }
    a17 = measured["a17"]
    items = [
        LIBRARY_ONLY,
        f"The provider serves {measured['fluids']} fluids (tier A {measured['tiers']['A']}, tier B "
        f"{measured['tiers']['B']}) and refuses {len(reference['excluded'])} by name with a reason "
        "(spec §16.1); the full excluded list, each fluid's tier and its bound kind (E, M or T) "
        "are in the S07.measured check. Tier B is self-consistent against CoolProp's own EOS, "
        "not independent of it: this is numerical verification of an implementation against "
        "a formulation, not empirical validation (spec §15).",
        f"{measured['published_check_fluids']} fluids report `published-check` (spec §16.5.2, "
        "A35): no published check values are transcribed (WO-S07-4 is optional and does not "
        "gate `tested`).",
        "The melting lines bound the domain from below only through a run-time estimate "
        "T_lo = T_t(1 + 1e-8/Pa P_hi) for the E fluids: no melting line exists in CoolProp "
        "8.0.0 for them, and solid states inside the box are not refused (§16.8, §15); the "
        "cryogenic liquids below T_lo are S07b's.",
        "The near-critical box of each fluid is refused near_critical, and the saturation of "
        "the (T_sigma_max, T_c) strip is answered by the second-stage fallback of "
        "docs/design/S07-near-critical-saturation.md (A45-A50, R-626); metastable states beyond "
        "eps_sigma = 1e-6 are refused phase_not_stable (spec §4, §19).",
        f"A17's floors: tier A at most {a17['tier_a_worst'][0]:.2e} ({a17['tier_a_worst'][1]}), "
        f"tier B at most {a17['tier_b_worst'][0]:.2e} ({a17['tier_b_worst'][1]}); tier B fluids "
        f"above 1e-11: {', '.join(a17['tier_b_above_1e-11']) or 'none'}. R22 (value noise in "
        "`L_corner` h and s) and PropyleneGlycol (cp in `S_dense`, truncation) were accepted "
        "by the reviewer (docs/S07_DECISIONS.md F-6, §19.6). Tier B's A03, A05, A08-A11 "
        "worsts are in the S07.measured check (spec §16.11).",
        "Q-3 (spec §5.2, A26(c)): the reference-state guard G4 runs once per instance for all "
        "nine tier-A fluids; no §5.2 amendment (docs/S07_DECISIONS.md, WO-S07-2a).",
        "Q-1 (cross-architecture): "
        + (
            f"x86-64: {lines.get('x86_64', 'not read')}; "
            f"aarch64: {lines.get('aarch64', 'not read')}"
            if lines
            else "not read (no CI run was given); status cannot be `tested`"
        )
        + ". The spec's pre-registered rule, if not bitwise, is |d| <= 1e-12 max(|x|, s_f) (tier B "
        "and NC: 1e-10); ADR 0046's status line states the measured agreement.",
        "CoolProp is the `coolprop` extra (`CoolProp==8.0.0`, MIT, compiled; the wheels' SHA-256s "
        "are recorded in docs/s07-coolprop-licences.json and the lock); it is not bundled, "
        "its fluid data are not redistributed (A29), and `requirements.lock` is byte-unchanged "
        "(A36). Distribution of a bundle containing CoolProp is a separate decision (ADR 0046).",
        "Requirements: D08 only (R-614 pattern): `coolprop-heos-v1` is a real provider on the "
        "property contract; no unit-model basis selects it (the binding package is a follow-on).",
        "S05 section (docs/S07_DECISIONS.md, 'S05 A33 evidence carried in S07's manifest'): the "
        "S05 suites, `s05_reference.py --check` and the record digest G7(b) after `8cab0e15` "
        "(S05's saturation fallback) are checks S07.S05.* of this manifest; S05's merged "
        "manifest keeps its own scope and no new S05 manifest is made.",
        "scripts/gate.sh was not run by this generator (it runs once before merge into main); "
        "S07.gate is unsupported here.",
        "Review: the design lane's reviewer pass (docs/reviews/S07-review.md, R-626) was applied "
        "by "
        "the review fixes and WO-S07-NC4; the human numerical and process-model review is "
        "pending, and this manifest claims neither `reviewed` nor `released`.",
    ]
    for item in entries:
        if item["result"] == "pass" or item["id"] == "S07.gate":
            continue
        value = item.get("value")
        detail = (
            "; ".join(f"{n['node']} {n['outcome']}" for n in value["not_passed"])
            if isinstance(value, dict) and value.get("not_passed")
            else "see its value"
        )
        items.append(text(f"{item['id']} is {item['result']}: {detail}"))
    return items


def build(commit: str, ci_run: str | None) -> dict[str, Any]:
    refuse_unless_measuring(commit)
    os.environ["OPENFLOWSHEET_REQUIRE_COOLPROP"] = "1"
    document = SPEC.read_text(encoding="utf-8")
    rows = assertion_table(document)
    artifacts = ROOT / "evidence" / "S07" / commit / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    junit = artifacts / "s07-tests.junit.xml"
    python = sys.executable
    tools = Path(python).parent
    tests = sorted(shown(path) for path in (ROOT / "tests").glob("test_s07_*.py"))
    measured_tests = [*tests, "tests/test_m07_mr12_extras_v02.py"]
    lint = [*SOURCES, *tests, *SCRIPT_FILES, shown(GENERATOR), shown(MEASUREMENTS / "recplug.py")]

    # the long measurements run beside the tests (compute is free; reading their output is not)
    background = {
        "S07.generator": start([python, str(GENERATOR), "--check"]),
        "S07.generator_jobs1": start([python, str(GENERATOR), "--check", "--jobs", "1"]),
        "S07.S05.generator": start([python, str(S05_GENERATOR), "--check"]),
    }

    with tempfile.TemporaryDirectory(prefix="s07-build-") as work:
        builder, setuptools = build_python(Path(work))
        os.environ["OFS_S07_BUILD_PYTHON"] = builder
        try:
            runs: dict[str, Any] = {
                "tests": run(
                    [
                        python,
                        "-m",
                        "pytest",
                        "-q",
                        "-p",
                        "no:cacheprovider",
                        f"--junitxml={shown(junit)}",
                        *measured_tests,
                    ],
                    pythonpath=True,
                ),
            }
        finally:
            del os.environ["OFS_S07_BUILD_PYTHON"]
    if not junit.is_file():
        raise SystemExit(f"pytest wrote no report (exit {runs['tests'].exit_code})")
    runs["tests"] = dataclasses.replace(
        runs["tests"],
        cmd=f"OPENFLOWSHEET_REQUIRE_COOLPROP=1 OFS_S07_BUILD_PYTHON=build-venv/bin/python "
        f"{runs['tests'].cmd} (build-venv: a scratch venv with setuptools {setuptools})",
    )
    s05_files = sorted(shown(path) for path in (ROOT / "tests").glob("test_s05_*.py"))
    s05_junit = artifacts / "s05-tests.junit.xml"
    runs["S07.S05.suites"] = run(
        [
            python,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            f"--junitxml={shown(s05_junit)}",
            *s05_files,
        ],
        pythonpath=True,
    )
    licences_ok, licences, runs["S07.licences"] = licence_check(artifacts)
    measured_ok, measured, runs["S07.measured"] = measured_records(artifacts)
    digest_ok, digest, digest_runs = digest_checks()
    ci_ok, ci, ci_runs = ci_evidence(ci_run, commit)
    g2_ok, g2, runs["S07.G2"] = digest_part(G2_FILES, G2_KEYS, G2_DIGEST, "s07-g2", artifacts)
    g7_ok, g7, runs["S07.S05.G7b"] = digest_part(
        G7B_FILES, G7B_KEYS, G7B_DIGEST, "s05-g7b", artifacts
    )
    runs["S07.ruff"] = run([str(tools / "ruff"), "check", *lint])
    runs["S07.format"] = run([str(tools / "ruff"), "format", "--check", *lint])
    runs["S07.mypy"] = run([str(tools / "mypy")], pythonpath=True)
    waited = {name: finish(process) for name, process in background.items()}
    for name, timed in waited.items():
        runs[name] = entry(timed)

    all_nodes = nodes(junit)
    skipped = [item.node for item in all_nodes if item.outcome == "skipped"]
    not_passed = [item for item in all_nodes if item.outcome not in ("passed",)]
    s05_nodes = nodes(s05_junit)
    s05_bad = [item for item in s05_nodes if item.outcome not in ("passed", "skipped")]
    generated = {
        name: {
            "cmd": runs[name].cmd,
            "exit_code": runs[name].exit_code,
            "seconds": round(waited[name].seconds, 1),
            "output": [text(x) for x in runs[name].stdout.strip().splitlines()[-2:]],
        }
        for name in ("S07.generator", "S07.generator_jobs1", "S07.S05.generator")
    }
    extra = {
        "A29": (True, {"sdist_and_wheel_built_with_setuptools": setuptools}),
        "A31": (
            digest_ok and ci_ok,
            {"this_machine": digest, "ci": ci},
        ),
    }
    entries = assertion_checks(rows, all_nodes, extra)
    entries += [
        check(
            "S07.tests",
            "§13: the S07 tests pass and none skips (CoolProp present, flag set)",
            "pass" if not not_passed and len(all_nodes) > 0 else "fail",
            {
                "nodes": len(all_nodes),
                "outcomes": dict(sorted(Counter(i.outcome for i in all_nodes).items())),
                "skipped": skipped[:20],
                "not_passed": [text(f"{i.node} {i.outcome}") for i in not_passed[:20]],
            },
            "every node passed",
        ),
        check(
            "S07.generator",
            "§13: s07_reference.py --check re-derives every claim and byte-compares both outputs",
            "pass" if runs["S07.generator"].exit_code == 0 else "fail",
            {**generated["S07.generator"], "coolprop": _coolprop(), "claims": _claims()},
            "exit code 0",
        ),
        check(
            "S07.generator_jobs1",
            "§16.15: the same --check at --jobs 1 (the outputs are byte-identical to --jobs N)",
            "pass" if runs["S07.generator_jobs1"].exit_code == 0 else "fail",
            generated["S07.generator_jobs1"],
            "exit code 0",
        ),
        check(
            "S07.licences",
            "§13, §17.3: the licence inventory for the coolprop extra is OK with both wheel hashes",
            "pass" if licences_ok else "fail",
            licences,
        ),
        check(
            "S07.measured",
            "§13, §16.15: fluid count, tiers and bounds, exclusions, published checks and the "
            "measured A17 floors and tier-B worsts",
            "pass" if measured_ok else "fail",
            measured,
        ),
        check(
            "S07.digest",
            "§9 A31: the platform digest is the script's x86-64 output and this machine's "
            "answers equal it",
            "pass" if digest_ok else "fail",
            digest,
        ),
        check(
            "S07.ci",
            "§13: the S07 tests and A31's line, on both CI architectures, for this commit",
            "pass" if ci_ok else "fail",
            ci,
        ),
        check(
            "S07.G2",
            "§19.7 A46 (G2): the S07 record digest after the near-critical change equals the "
            "registered one",
            "pass" if g2_ok else "fail",
            g2,
            G2_DIGEST,
        ),
        check(
            "S07.S05.suites",
            "S05 section: the S05 suites pass (S05 A33 evidence carried, 8cab0e15)",
            "pass" if runs["S07.S05.suites"].exit_code == 0 and not s05_bad else "fail",
            {
                "nodes": len(s05_nodes),
                "outcomes": dict(sorted(Counter(i.outcome for i in s05_nodes).items())),
                "cmd": runs["S07.S05.suites"].cmd,
            },
            "every node passed or skipped with its reason",
        ),
        check(
            "S07.S05.generator",
            "S05 section: s05_reference.py --check is byte-identical",
            "pass" if runs["S07.S05.generator"].exit_code == 0 else "fail",
            generated["S07.S05.generator"],
            "exit code 0",
        ),
        check(
            "S07.S05.G7b",
            "S05 section (G7(b)): the S05 record digest equals the one before 8cab0e15",
            "pass" if g7_ok else "fail",
            g7,
            G7B_DIGEST,
        ),
    ]
    tool_text = {
        "S07.ruff": "ruff check is clean on S07's files",
        "S07.format": "ruff format --check is clean on S07's files",
        "S07.mypy": "mypy (the project's configuration) is clean",
    }
    for name, description in tool_text.items():
        entries.append(
            check(
                name,
                description,
                "pass" if runs[name].exit_code == 0 else "fail",
                {"cmd": runs[name].cmd, "exit_code": runs[name].exit_code},
                "exit code 0",
            )
        )
    entries.append(
        check(
            "S07.gate",
            "§13: scripts/gate.sh passes before merge",
            "unsupported",
            "not run by this generator; the full gate runs once before merge (CLAUDE.md)",
        )
    )

    commands = [command(item) for item in runs.values()]
    commands += [command(item) for item in [*digest_runs, *ci_runs]]
    manifest: dict[str, Any] = {
        "work_package": "S07",
        "commit": commit,
        "requirements": ["D08"],
        "status": status(entries),
        "inputs": {
            "case_id": "S07 acceptance: docs/derivations/S07-spec.md §9, §16.10, §17.5, §19.7 "
            "(A01-A50) against docs/derivations/scripts/s07_reference.json, check list §13",
            "case_hash": sha256_file(REFERENCE),
            "environment_lock_hash": sha256_file(LOCK),
        },
        "commands": commands,
        "checks": entries,
        "artifacts": [
            {
                "path": shown(junit),
                "sha256": sha256_file(junit),
                "description": "JUnit report of the S07 test run (ignored; kept by hash)",
            },
            {
                "path": shown(s05_junit),
                "sha256": sha256_file(s05_junit),
                "description": "JUnit report of the S05 suites (ignored; kept by hash)",
            },
            {
                "path": shown(REFERENCE),
                "sha256": sha256_file(REFERENCE),
                "description": "the design lane's 50-digit reference values (ref)",
            },
            {
                "path": shown(TABLE),
                "sha256": sha256_file(TABLE),
                "description": "the generated fluid table (FLUID_DATA_SHA256's recipe, A28)",
            },
            {
                "path": shown(MODULE),
                "sha256": sha256_file(MODULE),
                "description": "the coolprop-heos-v1 provider module (implementation_sha256)",
            },
            {
                "path": shown(DIGEST),
                "sha256": sha256_file(DIGEST),
                "description": "A31's x86-64 digest (a regression fixture, not validation)",
            },
            {
                "path": shown(LICENCES),
                "sha256": sha256_file(LICENCES),
                "description": "the coolprop extra's licence record with both wheel SHA-256s",
            },
            {
                "path": shown(COOLPROP_LOCK),
                "sha256": sha256_file(COOLPROP_LOCK),
                "description": "the coolprop extra's hash-pinned lock",
            },
            {
                "path": shown(PUBLISHED),
                "sha256": sha256_file(PUBLISHED),
                "description": "published check values (zero rows; A35)",
            },
            {
                "path": shown(SPEC),
                "sha256": sha256_file(SPEC),
                "description": "the S07 specification the checks are read from",
            },
            {
                "path": shown(artifacts / "s07-g2.rec"),
                "sha256": sha256_file(artifacts / "s07-g2.rec"),
                "description": "the S07 provider-answer record behind G2 (ignored; kept by hash)",
            },
            {
                "path": shown(artifacts / "s05-g7b.rec"),
                "sha256": sha256_file(artifacts / "s05-g7b.rec"),
                "description": "the S05 provider-answer record behind G7(b) (ignored; by hash)",
            },
        ],
        "limitations": limitations(entries, measured),
        "review": {"numerical": "pending", "process_model": "pending"},
    }
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = [error.message for error in Draft202012Validator(schema).iter_errors(manifest)]
    if errors:
        raise SystemExit(f"the manifest does not validate: {errors}")
    return manifest


def _coolprop() -> dict[str, str]:
    import CoolProp

    return {"version": CoolProp.__version__, "gitrevision": CoolProp.__gitrevision__}


def _claims() -> int:
    return int(json.loads(REFERENCE.read_text("utf-8"))["claims"]["count"])


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--commit", help="the measured commit (default: HEAD)")
    parser.add_argument("--ci-run", help="the GitHub Actions run id of this commit (both arches)")
    parser.add_argument("--out", type=Path, help="default: evidence/S07/<commit>/manifest.json")
    arguments = parser.parse_args()
    commit = (
        arguments.commit
        or subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    )
    manifest = build(commit, arguments.ci_run)
    out = arguments.out or ROOT / "evidence" / "S07" / commit / "manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    passed = sum(1 for item in manifest["checks"] if item["result"] == "pass")
    print(
        f"{shown(out)}: status {manifest['status']}, {passed}/{len(manifest['checks'])} checks pass"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
