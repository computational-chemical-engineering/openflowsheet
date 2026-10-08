"""Generate `evidence/M03/<C>/manifest.json` by running, not by transcribing. M03 WO-10.

M03 spec §11 (A01-A48) and §12 WO-10, on M01's pattern (`scripts/m01_evidence_manifest.py`). The
manifest carries one check per assertion `M03.A01`…`A48`, read from the spec's §11, so an
assertion cannot be left out: an id the spec lists and this script cannot judge stops it. Each
check is decided from what this script ran at `C`:

1. **The default-gate M03 tests**, run here once (`pytest --junitxml` over `tests/test_m03_*.py`
   and A48's `tests/test_t08_w4_package_data.py`). An assertion names its nodes by the prefix
   `test_aNN_`; A41's committed half is the audit tests of `test_m03_nlp_isolation.py`. A failed or
   skipped node fails the check, and so does a selector that ran no node.
2. **The `nlp` gate**, `scripts/m03_nlp_check.sh` in the audited environment, with its inventory
   `--check` (A35-A41), run here with `--junitxml`. Its environment fingerprint is recorded: the
   audited ASL's SHA-256, the lock and inventory hashes, and the `solver.environment` the solved
   fixtures record (M03 review F2).
3. **The measurements.** A test that judges a value against a tolerance records it
   (`m03_support.record_measurement`, a junit property), so the value in the manifest is the one
   the gate judged. Per quantity the worst over the nodes is kept, with its tolerance and margin,
   and a check passes only if its nodes pass *and* every recorded value is within its bound.
4. **The generator**, `m03_reference.py --check` (A42: 264 claims, the JSON byte-identical).
5. **The gate**: the stdout of `scripts/check.sh` at `C`, which must end `check.sh: PASSED`.

Two release conditions are recorded as checks of their own, because a check is what the status
rule reads. **M03.N1** is Frank's licence answer, which A35-A40 rest on (`NLP_LICENCES_ACCEPTED`
is provisionally True; review F4). **M03.ci_both_runners** is the default gate green on both
registered CI runners (review F1's acceptance). Each is `pass` only when stated on the command
line (`--n1 accepted`, `--ci-both-runners green`), and is otherwise `unsupported`, with the reason.
`--n1 declined` marks A35-A40 `unsupported` (the review's "record A35-A40 as BLOCKED"; a check's
vocabulary has no BLOCKED).

The status is `tested` only if every check is `pass` and every command exited 0. Otherwise it is
`implemented`. `reviewed` is never set, and both review fields stay `pending`.

Usage:
    PYTHONPATH=src .venv/bin/python scripts/m03_evidence_manifest.py --commit C \\
        --gate-log GATE_STDOUT --nlp-env PREFIX --nlp-cache CACHE \\
        [--n1 pending|accepted|declined] [--ci-both-runners unconfirmed|green] [--out PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ElementTree
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "docs" / "derivations" / "M03-studies-spec.md"
M03 = ROOT / "benchmarks" / "m03"
REFERENCE = M03 / "reference_values.json"
INVENTORY = M03 / "ipopt-inventory-x86_64.json"
NLP_LOCKS = (
    "nlp-conda-explicit.txt",
    "nlp-build-conda-explicit.txt",
    "nlp-pip.lock",
    "nlp-test.lock",
)
SOLVED_FIXTURES = (
    "tests/fixtures/schemas/optimization_report/valid/nlp_1_solved.json",
    "tests/fixtures/schemas/optimization_report/valid/nlp_inf_solved.json",
)
REQUIREMENTS = ("A06", "D16")
RESULTS = ("pass", "fail", "unsupported", "not_applicable")
MEASUREMENT_PREFIX = "M03.measured."
#: A41's committed half: the audit document and its inventory (spec §9; G1-G8).
A41_NODES = (
    "tests/test_m03_nlp_isolation.py::test_the_audit_records_every_gate_item_and_a_verdict",
    "tests/test_m03_nlp_isolation.py::test_the_inventory_was_taken_from_the_committed_locks",
    "tests/test_m03_nlp_isolation.py::test_the_inventory_was_taken_on_nlp_1",
    "tests/test_m03_nlp_isolation.py::test_the_adapter_requires_the_audited_pynumero_asl_build",
)
#: The assertions only the audited environment can run (spec §11's "NLP with Ipopt").
NLP_ASSERTIONS = ("A35", "A36", "A37", "A38", "A39", "A40")
REFERENCE_CLAIMS = 264


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def catalogue() -> list[str]:
    """`A01`…: every assertion of spec §11, in order (`- **Axx**` bullets)."""
    text = SPEC.read_text(encoding="utf-8")
    section = text[text.index("## 11. Numbered assertions") : text.index("## 12. Work orders")]
    found = re.findall(r"^- \*\*(A\d\d)\*\*", section, re.MULTILINE)
    if len(found) != len(set(found)):
        raise SystemExit(f"duplicate assertion ids in {SPEC.name}")
    return found


def _description(aid: str) -> str:
    """The assertion's text from the spec, as its description."""
    text = SPEC.read_text(encoding="utf-8")
    match = re.search(rf"^- \*\*{aid}\*\* (.+?)(?:\n(?=- \*\*|\n|\*\*)|\Z)", text, re.M | re.S)
    if match is None:
        raise SystemExit(f"M03.{aid}: no bullet in {SPEC.name}")
    # The manifest test rejects any `<…>` (a template placeholder is never evidence); the spec's
    # comparisons stay readable with the full-width signs.
    body = " ".join(match[1].split()).replace("<", "＜").replace(">", "＞")
    return f"M03 spec §11, {aid}: {body[:700]}{'…' if len(body) > 700 else ''}"


# ----------------------------------------------------------------------------- the test runs


@dataclass
class TestRun:
    """Node id → outcome, and node id → the measurements its test recorded."""

    nodes: dict[str, str] = field(default_factory=dict)
    measured: dict[str, list[tuple[str, dict[str, Any]]]] = field(default_factory=dict)

    __test__ = False  # not a pytest class

    def merge(self, other: TestRun) -> None:
        self.nodes.update(other.nodes)
        for node, records in other.measured.items():
            self.measured.setdefault(node, []).extend(records)

    def select(self, prefix: str) -> dict[str, str]:
        return {
            node: outcome
            for node, outcome in self.nodes.items()
            if node.partition("::")[2].split("[", 1)[0].startswith(prefix)
        }


def _nodeid(classname: str, name: str) -> str:
    parts = classname.split(".")
    for index, part in enumerate(parts):
        if part.startswith("test_"):
            return "::".join(["/".join(parts[: index + 1]) + ".py", *parts[index + 1 :], name])
    return f"collection::{classname}::{name}"


def parse_junit(path: Path) -> TestRun:
    run = TestRun()
    for case in ElementTree.parse(path).getroot().iter("testcase"):
        node = _nodeid(case.get("classname", ""), case.get("name", ""))
        tags = {child.tag for child in case}
        if tags & {"failure", "error"} or run.nodes.get(node) == "failed":
            run.nodes[node] = "failed"
        else:
            run.nodes[node] = "skipped" if "skipped" in tags else "passed"
        for prop in case.iter("property"):
            name = prop.get("name", "")
            if name.startswith(MEASUREMENT_PREFIX):
                aid = name.removeprefix(MEASUREMENT_PREFIX)
                run.measured.setdefault(node, []).append((aid, json.loads(prop.get("value", ""))))
    return run


def _command(cmd: str, exit_code: int, log: Path) -> dict[str, Any]:
    return {"cmd": cmd, "cwd": ".", "exit_code": exit_code, "stdout_sha256": _sha256(log)}


def _run(
    argv: Sequence[str], log: Path, env: Mapping[str, str]
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        list(argv), cwd=ROOT, capture_output=True, text=True, check=False, env=dict(env)
    )
    log.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    return completed


def run_default_tests(artifacts: Path) -> tuple[TestRun, dict[str, Any]]:
    modules = sorted(path.relative_to(ROOT).as_posix() for path in ROOT.glob("tests/test_m03_*.py"))
    modules.append("tests/test_t08_w4_package_data.py")
    junit, log = artifacts / "m03-tests.junit.xml", artifacts / "m03-tests.stdout.txt"
    completed = _run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o",
         "junit_family=xunit1", f"--junitxml={junit}", *modules],
        log,
        {**os.environ, "PYTHONPATH": str(ROOT / "src")},
    )  # fmt: skip
    command = _command(
        "PYTHONPATH=src .venv/bin/python -m pytest -q -p no:cacheprovider -o junit_family=xunit1 "
        "--junitxml=ARTIFACTS/m03-tests.junit.xml " + " ".join(modules),
        completed.returncode,
        log,
    )
    return parse_junit(junit), command


def run_nlp_gate(prefix: Path, cache: Path, artifacts: Path) -> tuple[TestRun, dict[str, Any]]:
    junit, log = artifacts / "m03-nlp.junit.xml", artifacts / "m03-nlp.stdout.txt"
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    completed = _run(
        ["scripts/m03_nlp_check.sh", str(prefix), str(cache), "--", "-o", "junit_family=xunit1",
         f"--junitxml={junit}"],
        log,
        env,
    )  # fmt: skip
    command = _command(
        "scripts/m03_nlp_check.sh PREFIX CACHE -- -o junit_family=xunit1 "
        "--junitxml=ARTIFACTS/m03-nlp.junit.xml  (PREFIX: the audited environment of "
        "docs/m03-ipopt-audit.md; the script sets OMP_NUM_THREADS=1, PYTHONNOUSERSITE=1 and "
        "PYOMO_CONFIG_DIR, and runs the inventory --check)",
        completed.returncode,
        log,
    )
    text = completed.stdout
    run = parse_junit(junit) if junit.is_file() else TestRun()
    summary = re.findall(r"^(\d+ passed.*) in [\d.]+s", text, re.MULTILINE)
    gate = {
        "exit_code": completed.returncode,
        "passed": "=== m03_nlp_check.sh: PASSED ===" in text,
        "pytest": summary[-1] if summary else "no summary line",
        "inventory_check_exit_0": "--- inventory --check: exit 0" in text,
    }
    return run, {"command": command, "gate": gate}


# ----------------------------------------------------------------------------- measurements


def _bound(value: float, tolerance: float, sense: str) -> dict[str, Any]:
    if sense == "<=":
        within = value <= tolerance
        margin = tolerance / value if value > 0 else math.inf
    elif sense == "<":
        within = value < tolerance
        margin = tolerance / value if value > 0 else math.inf
    elif sense in (">=", ">"):
        within = value >= tolerance if sense == ">=" else value > tolerance
        margin = value / tolerance if tolerance > 0 else math.nan
    elif sense == "==":
        within, margin = value == tolerance, math.nan
    else:
        raise SystemExit(f"unknown sense {sense!r}")
    record: dict[str, Any] = {
        "value": value,
        "tolerance": tolerance,
        "sense": sense,
        "within": within,
    }
    if math.isinf(margin):
        record["margin"] = "infinite (exactly 0)"
    elif not math.isnan(margin):
        record["margin"] = float(f"{margin:.3g}")
    return record


def measurements(run: TestRun, aid: str) -> dict[str, Any]:
    """Per quantity, the worst value any node recorded for `aid`."""
    worst: dict[str, dict[str, Any]] = {}
    for records in run.measured.values():
        for recorded_aid, record in records:
            if recorded_aid != aid:
                continue
            key = f"{record['quantity']} ({record['sense']} {record['tolerance']:g})"
            previous = worst.get(key)
            value, sense = float(record["value"]), record["sense"]
            if (
                previous is None
                or (sense in ("<=", "<") and value > previous["value"])
                or (sense in (">=", ">") and value < previous["value"])
                or (sense == "==" and value != record["tolerance"])
            ):
                worst[key] = _bound(value, float(record["tolerance"]), sense)
    return dict(sorted(worst.items()))


def _selector(aid: str) -> tuple[str, ...]:
    if aid == "A41":
        return A41_NODES
    return (f"test_a{aid[1:]}_",)


@dataclass
class Inputs:
    tests: TestRun
    gate_passed: bool
    gate_summary: str
    nlp: dict[str, Any]
    generator: dict[str, Any]
    n1: str
    ci: str


def check(aid: str, inputs: Inputs) -> dict[str, Any]:
    selectors = _selector(aid)
    if aid == "A41":
        nodes = {node: inputs.tests.nodes.get(node, "missing") for node in selectors}
        shown = list(selectors)
    else:
        nodes = inputs.tests.select(selectors[0])
        shown = [f"tests/test_*.py::{selectors[0]}*"]
    counts = {o: sum(v == o for v in nodes.values()) for o in ("passed", "failed", "skipped")}
    counts["missing"] = sum(v == "missing" for v in nodes.values())
    value: dict[str, Any] = {"tests": {"selector": shown, **counts}}
    ok = bool(nodes) and counts["passed"] == len(nodes)
    measured = measurements(inputs.tests, aid)
    if measured:
        value["measured"] = measured
        ok = ok and all(bound["within"] for bound in measured.values())
    if aid in NLP_ASSERTIONS or aid == "A41":
        value["nlp_gate"] = inputs.nlp["gate"]
        ok = ok and inputs.nlp["gate"]["passed"]
    if aid == "A41":
        ok = ok and inputs.nlp["gate"]["inventory_check_exit_0"]
    if aid == "A35":
        value["q_f2"] = inputs.nlp["q_f2"]
    if aid == "A42":
        value["generator"] = inputs.generator
        ok = (
            ok
            and inputs.generator["exit_code"] == 0
            and inputs.generator["claims"] == REFERENCE_CLAIMS
        )
    entry: dict[str, Any] = {"id": f"M03.{aid}", "description": _description(aid)}
    if aid in NLP_ASSERTIONS and inputs.n1 == "declined":
        entry["result"] = "unsupported"
        entry["description"] += (
            " — N1 declined: the `nlp` extra and the licence acceptance are reverted, and the "
            "capability is withdrawn (M03 review, 'If N1 is declined')."
        )
    else:
        entry["result"] = "pass" if ok else "fail"
    entry["value"] = value
    return entry


def release_checks(n1: str, ci: str) -> list[dict[str, Any]]:
    return [
        {
            "id": "M03.N1",
            "description": "Frank's answer N1 on the licences of the `nlp` extra's stack (audit "
            "§7-§8; ADR 0032 D5's acceptance evidence). A35-A40 rest on it: "
            "`NLP_LICENCES_ACCEPTED` is provisionally True (commit 2b6e350), and declining is "
            "the revert of 2b6e350 and 91537b0 plus a re-taken inventory (M03 review F4).",
            "result": "pass" if n1 == "accepted" else "unsupported",
            "value": {"n1": n1},
        },
        {
            "id": "M03.ci_both_runners",
            "description": "M03 review F1's acceptance: the default gate green on both registered "
            "CI runners, ubuntu-latest (x86-64) and ubuntu-24.04-arm (aarch64), before the "
            "manifest says `tested`. This script runs the gate on one machine; the runners' "
            "verdict is stated on its command line.",
            "result": "pass" if ci == "green" else "unsupported",
            "value": {"ci_both_runners": ci},
        },
    ]


def nlp_fingerprint(prefix: Path) -> dict[str, Any]:
    """What the `nlp` evidence was produced in (ADR 0007 D6; review F2 and ruling Q2)."""
    solved = json.loads((ROOT / SOLVED_FIXTURES[0]).read_text(encoding="utf-8"))
    environment = dict(solved["solver"]["environment"])
    environment["pynumero_asl"] = {"sha256": environment["pynumero_asl"]["sha256"]}
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    return {
        "interpreter": "PREFIX/bin/python, the audited environment (docs/m03-ipopt-audit.md)",
        "prefix_name": prefix.name,
        "locks_sha256": {name: _sha256(M03 / name) for name in NLP_LOCKS},
        "inventory_sha256": _sha256(INVENTORY),
        "inventory_host": inventory.get("host"),
        "inventory_pass_g1_to_g6": inventory.get("pass_g1_to_g6"),
        "solver": {
            key: solved["solver"][key] for key in ("ipopt", "cyipopt", "pyomo", "linear_solver")
        },
        "recorded_environment": environment,
    }


def q_f2(measurements_path: Path) -> dict[str, Any]:
    record = json.loads(measurements_path.read_text(encoding="utf-8"))["q_f2"]
    return {
        "source": "benchmarks/m03/nlp-measurements.json (reproduced by the nlp gate's "
        "test_the_q_f2_and_q_f4_measurements_reproduce_and_keep_their_margin)",
        "closest": record["closest"],
        "margin_factor": record["margin_factor"],
        "within_margin_factor": record["within_margin_factor"],
    }


# ----------------------------------------------------------------------------- main


def _artifact(path: str, description: str) -> dict[str, str]:
    return {"path": path, "sha256": _sha256(ROOT / path), "description": description}


def build(
    commit: str,
    checks: list[dict[str, Any]],
    commands: list[dict[str, Any]],
    verdict: str,
) -> dict[str, Any]:
    return {
        "work_package": "M03",
        "commit": commit,
        "requirements": list(REQUIREMENTS),
        "status": verdict,
        "inputs": {
            "case_id": "M03 registered states (P1-P3, B1-B3, the sweep, FIT-I, FIT-U, NLP-1, "
            "NLP-INF) and the toy problems of spec §5, from benchmarks/m03/reference_values.json",
            "case_hash": _sha256(REFERENCE),
            "environment_lock_hash": _sha256(ROOT / "requirements.lock"),
        },
        "commands": commands,
        "checks": checks,
        "artifacts": [
            _artifact(
                "docs/derivations/M03-studies-spec.md",
                "The specification, Amendments 1 and 2 included.",
            ),
            _artifact(
                "benchmarks/m03/reference_values.json", "The generator's 60-digit expectations."
            ),
            _artifact(
                "docs/adr/0031-m03-parametric-sensitivities-and-studies.md",
                "ADR 0031 (sensitivities, sweeps, estimation).",
            ),
            _artifact("docs/adr/0032-m03-general-nlp-adapter.md", "ADR 0032 (the NLP adapter)."),
            _artifact("docs/m03-ipopt-audit.md", "The [A10] audit of the Ipopt route (A41)."),
            _artifact(
                "benchmarks/m03/ipopt-inventory-x86_64.json", "The audited inventory (A41, G1-G8)."
            ),
            _artifact(
                "benchmarks/m03/nlp-measurements.json", "The Q-F2 and Q-F4 measurements (A35-A36)."
            ),
            _artifact("docs/reviews/M03-review.md", "The design-lane review this build answers."),
            _artifact(
                "tests/m03_fixture_compare.py",
                "The fixture comparison under the numerical policy (review F1).",
            ),
            _artifact("schemas/study.schema.json", "The study schema (spec §10)."),
            _artifact("schemas/optimization-report.schema.json", "The optimization-report schema."),
        ],
        "limitations": LIMITATIONS,
        "review": {"numerical": "pending", "process_model": "pending"},
    }


LIMITATIONS = [
    "N1 is pending. The `nlp` extra (91537b0) and the licence acceptance NLP_LICENCES_ACCEPTED "
    "(2b6e350) are provisional, and A35-A40 rest on them; the M03.N1 check says so. Declining "
    "is the revert of both commits and a re-taken inventory, after which A35-A40 are recorded "
    "unsupported (the review's BLOCKED) and optimize() reports UNSUPPORTED everywhere.",
    "The default gate was run on one x86-64 machine. M03 review F1's acceptance, both registered "
    "CI runners green, is not established here; the M03.ci_both_runners check says so. The "
    "fixture comparison was shown to tolerate cross-platform noise by regenerating every "
    "fixture with each linear back-solve perturbed by 1-64 ulps, not on aarch64.",
    "The NLP evidence (A35-A41) is valid only in the audited environment on its host and under "
    "OMP_NUM_THREADS=1 (review ruling Q2): each report records its thread configuration and the "
    "loaded ASL (review F2), and the adapter enforces nothing. Whether single-threading is a "
    "product requirement is open for Frank (ADR 0007 D6).",
    "W24 is a gate id that the manifest schema's `requirements` pattern ([DA]nn) cannot carry. "
    "This evidence bears on W24's M03 part (fixed-topology optimization); M05 supplies the "
    "trust-region half, and the gate's verdict is the verdict lane's.",
    "Synthetic only: SYN-001 is a synthetic flowsheet, and the estimation data are generated from "
    "the model itself, so FIT-I and FIT-U are numerical verification of the estimation "
    "machinery, not empirical validation.",
    "Local stationarity is not global optimality. NLP-1's candidate is a verified KKT point from "
    "three starts; second-order conditions are not assessed (limited-memory Hessian, spec §8.3).",
    "The fixture comparison's rules for values T08-numerical-policy-v2 has no row for (the "
    "scaled-sensitivity floor tau_abs = 1e-11 among them) live in tests/m03_fixture_compare.py, "
    "not in the registered policy data; the design lane registers them (review F1).",
    "Review notes left open: F6 (one CasADi Function for [F_x F_p]; caching the twin, for M05), "
    "F8.2 (the formulation record states the first verified start's regimes), F8.3 (Q0 is "
    "structurally vacuous in syn001_sensitivity) and F8.4 (tp_margin assumes ideal, "
    "composition-independent K; a non-ideal host needs a new margin).",
    "Human numerical and process-modeling review remain `pending`; `reviewed` is never self-set.",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--commit", required=True)
    parser.add_argument("--gate-log", required=True, type=Path)
    parser.add_argument("--nlp-env", required=True, type=Path)
    parser.add_argument("--nlp-cache", required=True, type=Path)
    parser.add_argument("--n1", choices=("pending", "accepted", "declined"), default="pending")
    parser.add_argument(
        "--ci-both-runners", choices=("unconfirmed", "green"), default="unconfirmed"
    )
    parser.add_argument("--out", type=Path, default=None)
    arguments = parser.parse_args()

    commit = arguments.commit
    if _git("rev-parse", "HEAD").strip() != commit or _git(
        "status", "--porcelain", "--", "src", "tests", "benchmarks", "docs/derivations", "scripts",
        "schemas",
    ):  # fmt: skip
        raise SystemExit(f"run at a clean checkout of {commit}: the code under test must be C's")
    ids = catalogue()
    if ids != [f"A{n:02d}" for n in range(1, 49)]:
        raise SystemExit(f"spec §11's assertions are {ids}, not A01-A48")

    destination = arguments.out or (ROOT / "evidence" / "M03" / commit / "manifest.json")
    artifacts = destination.parent / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    gate_text = arguments.gate_log.read_text(encoding="utf-8")
    verdicts = [line for line in gate_text.splitlines() if line.startswith("=== check.sh: ")]
    gate_passed = verdicts[-1:] == ["=== check.sh: PASSED ==="]
    summary = re.findall(r"^(\d+ passed.*) in [\d.]+s", gate_text, re.MULTILINE)
    gate_summary = f"check.sh {'PASSED' if gate_passed else 'FAILED'}; pytest: "
    gate_summary += summary[-1] if summary else "no summary line"

    tests, test_command = run_default_tests(artifacts)
    nlp_run, nlp = run_nlp_gate(arguments.nlp_env, arguments.nlp_cache, artifacts)
    tests.merge(nlp_run)
    nlp["fingerprint"] = nlp_fingerprint(arguments.nlp_env)
    nlp["q_f2"] = q_f2(M03 / "nlp-measurements.json")
    log = artifacts / "m03-reference-check.stdout.txt"
    completed = _run(
        [sys.executable, "docs/derivations/scripts/m03_reference.py", "--check"],
        log,
        {**os.environ, "PYTHONPATH": str(ROOT / "src")},
    )
    claims = re.search(r"(\d+) claims", completed.stdout)
    generator = {
        "exit_code": completed.returncode,
        "claims": int(claims[1]) if claims else None,
        "last_line": completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else "",
    }
    generator_command = _command(
        "PYTHONPATH=src .venv/bin/python docs/derivations/scripts/m03_reference.py --check",
        completed.returncode,
        log,
    )

    inputs = Inputs(
        tests=tests,
        gate_passed=gate_passed,
        gate_summary=gate_summary,
        nlp=nlp,
        generator=generator,
        n1=arguments.n1,
        ci=arguments.ci_both_runners,
    )
    checks = [check(aid, inputs) for aid in ids]
    checks.append(
        {
            "id": "M03.gate",
            "description": "`./scripts/check.sh` green at C: ruff, ruff format, mypy and the "
            "default pytest gate, which holds every M03 assertion but A35-A40.",
            "result": "pass" if gate_passed else "fail",
            "value": gate_summary,
        }
    )
    checks.append(
        {
            "id": "M03.nlp_gate",
            "description": "`scripts/m03_nlp_check.sh` green at C in the audited environment: "
            "the `nlp`-marked tests (A35-A40, the F2 thread record, the NLP fixtures and the "
            "Q-F2/Q-F4 measurements under the numerical policy) and the inventory --check (A41).",
            "result": "pass" if nlp["gate"]["passed"] else "fail",
            "value": {"gate": nlp["gate"], "environment": nlp["fingerprint"]},
        }
    )
    checks += release_checks(arguments.n1, arguments.ci_both_runners)
    commands = [
        {
            "cmd": "PYTHONPATH=src PATH=.venv/bin:$PATH ./scripts/check.sh",
            "cwd": ".",
            "exit_code": 0 if gate_passed else 1,
            "stdout_sha256": _sha256(arguments.gate_log),
        },
        test_command,
        nlp["command"],
        generator_command,
    ]
    every = all(entry["result"] == "pass" for entry in checks)
    verdict = "tested" if every and all(c["exit_code"] == 0 for c in commands) else "implemented"
    manifest = build(commit, checks, commands, verdict)
    destination.write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    counts = {r: sum(c["result"] == r for c in checks) for r in RESULTS}
    print(f"wrote {destination}: status {manifest['status']}")
    print(", ".join(f"{n} {r}" for r, n in counts.items()))
    for entry in checks:
        if entry["result"] != "pass":
            print(f"{entry['result'].upper()}: {entry['id']}")
    tight = list(_tight(checks))
    if tight:
        print("within 10x of the bound:\n  " + "\n  ".join(tight))
    return 1 if counts["fail"] else 0


def _tight(checks: Iterable[Mapping[str, Any]]) -> Iterable[str]:
    for entry in checks:
        value = entry.get("value")
        if not isinstance(value, Mapping):
            continue
        for name, bound in (value.get("measured") or {}).items():
            margin = bound.get("margin")
            if isinstance(margin, float) and margin < 10.0:
                yield f"{entry['id']} {name}: {bound['value']:.3g}, margin {margin}"


if __name__ == "__main__":
    raise SystemExit(main())
