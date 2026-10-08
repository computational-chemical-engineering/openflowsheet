"""Generate `evidence/M06/<C>/manifest.json` by measuring, not by transcribing. M06 WO-13.

Design note `docs/design/M06-web-shell.md` §11 (gates G1–G16) and the design-lane review
`docs/reviews/M06-review.md` (F1, F2, F6, F7). The manifest carries one check per gate, read from
§11's table itself, so that a gate cannot be left out: a gate without a rule here, or a rule
without a gate there, stops the script. Each check is decided from what this script ran or read
at `C`:

1. **The M06 tests**, run once here (`pytest --junitxml` over `tests/test_m06_*.py`) with
   `OPENFLOWSHEET_REQUIRE_BROWSER=1`, so the browser module runs or fails, never skips. Every
   node is assigned to at least one gate by `SELECTORS` (an unassigned node stops the script); a
   failed or skipped node fails its gates, and a selector that matches no node fails its gate.
2. **The Node tests** (`node --test` over `tests/web/*.test.mjs`), run here (G7).
3. **The gate**: the stdout of `scripts/check.sh` at `C`, required to end `check.sh: PASSED`
   and to show the Node step ran (G12's local half).
4. **The default install**: the stdout of `python -m pytest -q` in an environment with the
   project and its `dev` extra only, at the lock's versions, as CI's `default-install` job (G12;
   review F2b, F2c). It must report no failure.
5. **G10**: the directory a local `dist` → `clean-install` → "M06 G10" run wrote (the wheel built
   from `C` by `scripts/t08_dist.py`, installed in a clean environment with the server extra at
   the lock, `scripts/m06_web_serve_check.py` from outside the tree; review F1).
6. **G15**: the W27 dry run's `summary.json` at `C` (`python -m benchmarks.m06.w27.dryrun`):
   preflight P1–P8, the scorer states, W27-A23 (review F7).
7. **CI** (`--ci-run`, repeatable): `gh run view` of runs at `C` or at a descendant of `C` that
   changes only this manifest's files. G3's identity job and G12's two `check` legs and
   `default-install` are CI's; without a recorded green run those halves are unmet and G3 and
   G12 fail with that reason. A run that holds the `clean-install` jobs adds CI's G10 record.
   With `--add-ci`, the runs are recorded in the manifest already written for `C`, from such a
   descendant, without re-running anything.

G16 is the W27 campaign, M07's (WO-17): `not_applicable` here. Status is `tested` only if every
other check is `pass` and every command exited 0; otherwise `implemented`. `reviewed` is never
set, and both review fields stay `pending`.

`--harvest` also rewrites the M06 entries of `benchmarks/t08/support_envelope.yaml#harvest`
(T08.A21: every limitation and every non-`pass` check classified) and regenerates
`docs/support-matrix.md` with `t08_support_matrix.py --emit`.

Usage:
    PYTHONPATH=src .venv/bin/python scripts/m06_evidence_manifest.py --commit C \\
        --gate-log GATE_STDOUT --default-install-log LOG --g10-dir DIR --g10-log LOG \\
        --dryrun DIR [--ci-run ID ...] [--harvest]
    PYTHONPATH=src .venv/bin/python scripts/m06_evidence_manifest.py --commit C --add-ci \\
        --ci-run ID [--ci-run ID ...] [--harvest]
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ElementTree
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
NOTE = ROOT / "docs" / "design" / "M06-web-shell.md"
ENVELOPE = ROOT / "benchmarks" / "t08" / "support_envelope.yaml"
MATRIX = ROOT / "docs" / "support-matrix.md"
RESULTS = ("pass", "fail", "unsupported", "not_applicable")
#: The CI jobs G12 needs green, and the job that holds G3's cross-platform identity.
CI_CHECK_JOBS = ("check (ubuntu-latest)", "check (ubuntu-24.04-arm)", "default-install")
CI_IDENTITY_JOB = "identity"
CI_CLEAN_INSTALL = ("clean-install (ubuntu-latest)", "clean-install (ubuntu-24.04-arm)")

#: Each gate's test nodes: `module::function-pattern` (fnmatch on the function name, parameters
#: stripped). Every node of `tests/test_m06_*.py` must fall under at least one gate.
SELECTORS: Mapping[str, tuple[str, ...]] = {
    "G1": ("test_m06_static_scan.py::*", "test_m06_browser_smoke.py::test_g1_*"),
    "G2": ("test_m06_http_contract.py::*", "test_m06_fixtures_valid.py::*"),
    "G3": (
        "test_m06_wo1_structure_index.py::test_g3_*",
        "test_m06_wo1_structure_index.py::test_the_snapshots_cover_the_corpus",
    ),
    "G4": ("test_m06_wo1_structure_index.py::*",),
    "G5": ("test_m06_wo2_diff_elements.py::*",),
    "G6": ("test_m06_wo3_list_audit.py::*",),
    "G7": ("test_m06_wo6_expander_fixture.py::*",),
    "G8": ("test_m06_wo4_serving.py::*", "test_m06_browser_smoke.py::test_g8_*"),
    "G9": ("test_m06_contrast.py::*",),
    "G10": ("test_m06_wo4_serving.py::test_a_real_server_serves_the_shell",),
    "G11": ("test_m06_browser_smoke.py::*",),
    "G13": ("test_m06_wo14_w27_provenance.py::*",),
    "G14": ("test_m06_w27_coverage.py::*", "test_m06_w27_registration.py::*"),
    "G15": ("test_m06_w27_harness.py::*", "test_m06_w27_scorer.py::*"),
}
#: The M06 manifest's limitations: the envelope's L-WEB rows verbatim, U14 restated, and the two
#: statements the manifest schema asks of a package with no D/A requirement. With each, its
#: T08.A21 classification (class, pointers, note).
WEB_ROWS = ("L-WEB-1", "L-WEB-2", "L-WEB-3", "L-WEB-4")
EXTRA_LIMITATIONS: tuple[tuple[str, str, list[str], str], ...] = (
    (
        "W27's campaign (G16) is not run in M06: it is M07's (WO-17), after Frank's recorded spend "
        "approval and three real canaries; M06 commits the adaptation records only (provenance, "
        "access report, registration, coverage; R-175 to R-179), and no comparison with CRAFTS or "
        "OpenIDAES-450's reported results is made.",
        "E",
        ["U14"],
        "W27 campaign is M07's",
    ),
    (
        "W26 and W27 are v0.2 requirement ids the manifest schema's `requirements` pattern "
        "([DA]nn) cannot carry, and M06 maps to no D/A requirement (plan v1.2 §4.4, rows W26 and "
        "W27), so `requirements` is empty; the verdicts on W26 and W27 are the `verdict` lane's, "
        "not this manifest's.",
        "P",
        [],
        "requirement ids outside the manifest pattern",
    ),
    (
        "Evidence class: software verification at C (tests, the gate, a local wheel install, the "
        "W27 dry run with stub sessions, and CI where recorded); nothing here is empirical "
        "validation or a usability study. Human numerical and process-modeling review remain "
        "`pending`; `reviewed` is never self-set.",
        "P",
        [],
        "evidence class; review pending",
    ),
)

sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import yaml  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def catalogue() -> dict[str, str]:
    """`{G1: invariant, …}`: §11's table rows, in order."""
    text = NOTE.read_text(encoding="utf-8")
    section = text[text.index("## 11. Verification gates") : text.index("## 12.")]
    rows = re.findall(r"^\| \*\*(G\d+)\*\* ([^|]+?) \| ([^|]+?) \|", section, re.MULTILINE)
    gates = {gate: f"{name.strip()}: {invariant.strip()}" for gate, name, invariant in rows}
    if list(gates) != [f"G{n}" for n in range(1, 17)]:
        raise SystemExit(f"§11's gates are {list(gates)}, not G1-G16")
    return gates


# ----------------------------------------------------------------------------- the tests


@dataclass
class TestRun:
    """Node id → outcome (`passed`, `failed`, `skipped`) as `pytest --junitxml` recorded it."""

    nodes: dict[str, str]
    exit_code: int

    __test__ = False  # not a pytest class

    def select(self, patterns: Sequence[str]) -> dict[str, str]:
        found: dict[str, str] = {}
        for node, outcome in self.nodes.items():
            module, _, function = node.partition("::")
            name = f"{Path(module).name}::{function.split('[', 1)[0]}"
            if any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns):
                found[node] = outcome
        return found


def _nodeid(classname: str, name: str) -> str:
    parts = classname.split(".")
    for index, part in enumerate(parts):
        if part.startswith("test_"):
            return "::".join(["/".join(parts[: index + 1]) + ".py", *parts[index + 1 :], name])
    return f"collection::{classname}::{name}"


def run_tests(artifacts: Path) -> tuple[TestRun, dict[str, Any]]:
    modules = sorted(path.relative_to(ROOT).as_posix() for path in ROOT.glob("tests/test_m06_*.py"))
    junit, stdout = artifacts / "m06-tests.junit.xml", artifacts / "m06-tests.stdout.txt"
    env = {
        **os.environ,
        "PYTHONPATH": f"{ROOT / 'src'}:{ROOT}",
        "OPENFLOWSHEET_REQUIRE_BROWSER": "1",
    }
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-rs", "-p", "no:cacheprovider"]
        + [f"--junitxml={junit}", *modules],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    stdout.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    nodes: dict[str, str] = {}
    for case in ElementTree.parse(junit).getroot().iter("testcase"):
        node = _nodeid(case.get("classname", ""), case.get("name", ""))
        tags = {child.tag for child in case}
        if tags & {"failure", "error"} or nodes.get(node) == "failed":
            nodes[node] = "failed"
        else:
            nodes[node] = "skipped" if "skipped" in tags else "passed"
    command = {
        "cmd": "OPENFLOWSHEET_REQUIRE_BROWSER=1 PYTHONPATH=src:. .venv/bin/python -m pytest -q -rs "
        "-p no:cacheprovider --junitxml=ARTIFACTS/m06-tests.junit.xml " + " ".join(modules),
        "cwd": ".",
        "exit_code": completed.returncode,
        "stdout_sha256": _sha256(stdout),
    }
    return TestRun(nodes, completed.returncode), command


def run_node(artifacts: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    log = artifacts / "m06-node.stdout.txt"
    completed = subprocess.run(
        ["node", "--test", "--test-reporter=spec", "tests/web/*.test.mjs"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    log.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    counts = {
        key: int(value)
        for key, value in re.findall(
            r"^ℹ (tests|pass|fail|cancelled|skipped|todo) (\d+)$", completed.stdout, re.MULTILINE
        )
    }
    version = subprocess.run(["node", "--version"], capture_output=True, text=True, check=False)
    record = {"node": version.stdout.strip(), "exit_code": completed.returncode, **counts}
    command = {
        "cmd": 'node --test --test-reporter=spec "tests/web/*.test.mjs"',
        "cwd": ".",
        "exit_code": completed.returncode,
        "stdout_sha256": _sha256(log),
    }
    return record, command


# ----------------------------------------------------------------------------- the inputs


def read_gate(log: Path) -> dict[str, Any]:
    text = log.read_text(encoding="utf-8")
    verdicts = [line for line in text.splitlines() if line.startswith("=== check.sh: ")]
    summary = re.findall(r"^(\d+ passed.*) in [\d.]+s", text, re.MULTILINE)
    node = re.search(r"^--- node --test: exit (\d+)$", text, re.MULTILINE)
    node_pass = re.findall(r"^ℹ pass (\d+)$", text, re.MULTILINE)
    return {
        "passed": verdicts[-1:] == ["=== check.sh: PASSED ==="],
        "pytest": summary[-1] if summary else None,
        "node_step_ran": node is not None and node[1] == "0" and "SKIPPED (explicit)" not in text,
        "node_pass": int(node_pass[-1]) if node_pass else None,
        "stdout_sha256": _sha256(log),
    }


def read_default_install(log: Path) -> dict[str, Any]:
    text = log.read_text(encoding="utf-8")
    absent = re.search(r"^server extra absent: (\[.*\])$", text, re.MULTILINE)
    summary = re.findall(r"^((?:\d+ \w+(?:, )?)+) in [\d.]+s", text, re.MULTILINE)
    last = summary[-1] if summary else ""
    failed = re.search(r"(\d+) (failed|error)", last)
    return {
        "summary": last or None,
        "extra_absent": absent is not None and absent[1] == "[]",
        "passed": bool(last) and failed is None and absent is not None and absent[1] == "[]",
        "stdout_sha256": _sha256(log),
    }


def read_g10(directory: Path, log: Path) -> dict[str, Any]:
    dist = json.loads((directory / "rc-dist" / "t08-a43-dist.json").read_text(encoding="utf-8"))
    served_text = (directory / "web.txt").read_text(encoding="utf-8")
    text = log.read_text(encoding="utf-8")
    commit = re.search(r"^commit ([0-9a-f]{40})$", text, re.MULTILINE)
    wheel = re.search(r"^wheel \S+/([^/\s]+\.whl) ([0-9a-f]{64})$", text, re.MULTILINE)
    imported = re.search(r"^imported from (\S+)$", text, re.MULTILINE)
    failing = sorted(c["id"] for c in dist["checks"] if c["result"] != "pass")
    if dist["passed"] is not True and not failing:
        failing = ["record: passed is not true"]
    (equal,) = [c for c in dist["checks"] if c["id"] == "a43.bytes_equal_commit"]
    web = sorted(k for k in equal["runtime_data"] if k.startswith("openflowsheet/_data/web/"))
    tracked = _git("ls-files", "apps/web").split()
    lines = [line for line in served_text.splitlines() if line.startswith(("PASS ", "FAIL "))]
    served = served_text.strip().splitlines()[-1] if served_text.strip() else ""
    served = re.sub(r"\(\S*/", "(.../", served)
    return {
        "built_from": commit[1] if commit else None,
        "wheel": wheel[1] if wheel else None,
        "wheel_sha256": wheel[2] if wheel else None,
        "installed_package": re.sub(r"^.*/(site-packages/)", r".../\1", imported[1])
        if imported
        else None,
        "dist_record_sha256": _sha256(directory / "rc-dist" / "t08-a43-dist.json"),
        "dist_checks_failing": failing,
        # Every tracked `apps/web` file is runtime data of the wheel and the sdist with the
        # commit's bytes (`a43.bytes_equal_commit`; the two builds equal, `a43.two_builds`).
        "web_files_in_wheel_equal_bytes": len(web),
        "web_files_tracked": len(tracked),
        "serve_checks": lines,
        "serve_verdict": served,
        "exit_line": "EXIT 0" in text.splitlines()[-1:],
    }


def read_dryrun(directory: Path) -> dict[str, Any]:
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    preflight = {name: bool(v["passed"]) for name, v in summary["preflight"].items()}
    p7 = summary["preflight"].get("P7", {})
    return {
        "commit": summary["commit"],
        "summary_sha256": _sha256(directory / "summary.json"),
        "preflight": preflight,
        "canaries": "stub sessions: model "
        f"{p7.get('canary_models')}, Claude Code {p7.get('canary_claude_code_versions')} — P6 "
        "and P7 are met by stub canaries; the real campaign's P7 pins a real model and version",
        "g14_passed": summary["g14"]["passed"],
        "g15_states_passed": summary["g15_states"]["passed"],
        "a23_passed": summary["a23_passed"],
    }


def read_ci(run_ids: Sequence[str], commit: str, own_paths: Sequence[str]) -> dict[str, Any]:
    """Each run's jobs, and whether its head is `C` or a descendant that touches only
    `own_paths` (this manifest's directory, the envelope and the matrix)."""
    runs: list[dict[str, Any]] = []
    for run_id in run_ids:
        view = json.loads(
            subprocess.run(
                ["gh", "run", "view", run_id, "--json", "databaseId,headSha,conclusion,event,jobs"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
            ).stdout
        )
        head = view["headSha"]
        descends = (
            subprocess.run(
                ["git", "merge-base", "--is-ancestor", commit, head], cwd=ROOT, check=False
            ).returncode
            == 0
        )
        touched = _git("diff", "--name-only", commit, head).split() if descends else []
        foreign = [p for p in touched if not any(p.startswith(own) for own in own_paths)]
        jobs = {job["name"]: job["conclusion"] for job in view["jobs"]}
        steps = {
            job["name"]: {step["name"]: step["conclusion"] for step in job.get("steps", [])}
            for job in view["jobs"]
        }
        runs.append(
            {
                "run": view["databaseId"],
                "head": head,
                "event": view["event"],
                "conclusion": view["conclusion"],
                "at_or_after_c": descends and not foreign,
                "changes_since_c": touched,
                "jobs": jobs,
                "g10_steps": {
                    name: steps[name].get("M06 G10 — the installed wheel serves the web shell")
                    for name in CI_CLEAN_INSTALL
                    if name in steps
                },
            }
        )
    usable = [run for run in runs if run["at_or_after_c"]]

    def green(job: str) -> bool:
        return any(run["jobs"].get(job) == "success" for run in usable)

    return {
        "runs": runs,
        "checks_green": all(green(job) for job in CI_CHECK_JOBS),
        "identity_green": green(CI_IDENTITY_JOB),
        "g10_green": any(
            len(run["g10_steps"]) == 2 and set(run["g10_steps"].values()) == {"success"}
            for run in usable
        ),
    }


# ----------------------------------------------------------------------------- the checks


@dataclass
class Inputs:
    commit: str
    tests: TestRun
    node: dict[str, Any]
    gate: dict[str, Any]
    default_install: dict[str, Any]
    g10: dict[str, Any]
    dryrun: dict[str, Any]
    ci: dict[str, Any] | None
    gates: dict[str, str] = field(default_factory=dict)


def _tests(gate: str, inputs: Inputs) -> tuple[bool, dict[str, Any]]:
    patterns = SELECTORS.get(gate, ())
    if not patterns:
        return True, {}
    nodes = inputs.tests.select(patterns)
    counts = {o: sum(v == o for v in nodes.values()) for o in ("passed", "failed", "skipped")}
    bad = sorted(node for node, outcome in nodes.items() if outcome != "passed")
    ok = bool(nodes) and not bad
    return ok, {"selectors": [f"tests/{p}" for p in patterns], **counts, "not_passed": bad}


def check(gate: str, inputs: Inputs) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": f"M06.{gate}",
        "description": f"§11 {gate}, {inputs.gates[gate]}",
    }
    if gate == "G16":
        entry["result"] = "not_applicable"
        entry["description"] += (
            " — Not run in M06: the W27 campaign is M07's (WO-17), after Frank's spend approval "
            "(recorded, P1) and three real canaries (design note §11: M06 reaches tested on "
            "G1-G15)."
        )
        entry["value"] = {"status": "planned at M07"}
        return entry
    ok, tests = _tests(gate, inputs)
    value: dict[str, Any] = {"tests": tests} if tests else {}
    if gate == "G3":
        ok = ok and inputs.gate["passed"]
    if gate == "G7":
        value["node"] = inputs.node
        ok = (
            ok
            and inputs.node["exit_code"] == 0
            and inputs.node.get("fail") == 0
            and inputs.node.get("skipped") == 0
            and inputs.node.get("pass", 0) > 0
        )
    if gate == "G10":
        value["local"] = inputs.g10
        ok = (
            ok
            and inputs.g10["built_from"] == inputs.commit
            and inputs.g10["dist_checks_failing"] == []
            and inputs.g10["web_files_in_wheel_equal_bytes"] == inputs.g10["web_files_tracked"] > 0
            and inputs.g10["serve_verdict"].startswith("m06_web_serve_check: PASSED")
            and not any(line.startswith("FAIL ") for line in inputs.g10["serve_checks"])
            and inputs.g10["exit_line"]
            and "/site-packages/" in str(inputs.g10["installed_package"])
        )
    if gate == "G12":
        value["gate"] = inputs.gate
        value["default_install_local"] = inputs.default_install
        ok = (
            inputs.gate["passed"]
            and inputs.gate["node_step_ran"]
            and inputs.default_install["passed"]
        )
    if gate == "G15":
        value["dry_run"] = inputs.dryrun
        ok = (
            ok
            and inputs.dryrun["commit"] == inputs.commit
            and all(inputs.dryrun["preflight"].values())
            and sorted(inputs.dryrun["preflight"]) == [f"P{n}" for n in range(1, 9)]
            and inputs.dryrun["g15_states_passed"]
            and inputs.dryrun["a23_passed"]
        )
    if gate == "G14":
        value["dry_run_g14"] = inputs.dryrun["g14_passed"]
        ok = ok and inputs.dryrun["g14_passed"]
    entry["result"] = "pass" if ok else "fail"
    entry["value"] = value
    if gate in CI_GATES:
        value["local_passed"] = ok
        apply_ci(entry, inputs.ci)
    return entry


#: The gates with a CI half: G3's identity job and G12's legs are required; G10's clean-install
#: steps are recorded when a run holds them (the local wheel install is G10's measurement).
CI_GATES = ("G3", "G10", "G12")
NOT_RECORDED = "not recorded: the session dispatches CI and records it with --add-ci"


def apply_ci(entry: dict[str, Any], ci: Mapping[str, Any] | None) -> None:
    """Decide a CI gate from its local half (`value.local_passed`) and the CI runs."""
    gate, value = entry["id"].removeprefix("M06."), entry["value"]
    ok = bool(value["local_passed"])
    if gate == "G3":
        value["ci_identity_job"] = (
            ("green" if ci["identity_green"] else "not green") if ci else NOT_RECORDED
        )
        ok = ok and bool(ci and ci["identity_green"])
    elif gate == "G10":
        if ci:
            value["ci_clean_install_g10_steps"] = "green" if ci["g10_green"] else "not recorded"
    elif gate == "G12":
        value["ci"] = (
            {
                "checks_and_default_install": "green" if ci["checks_green"] else "not green",
                "runs": ci["runs"],
                "browser_module": "check (ubuntu-latest) sets OPENFLOWSHEET_REQUIRE_BROWSER=1, "
                "so its success means the browser module ran and passed there",
            }
            if ci
            else NOT_RECORDED
        )
        ok = ok and bool(ci and ci["checks_green"])
    entry["result"] = "pass" if ok else "fail"


def status(checks: Sequence[Mapping[str, Any]], commands: Sequence[Mapping[str, Any]]) -> str:
    allowed = {"M06.G16": "not_applicable"}
    every = all(c["result"] == allowed.get(c["id"], "pass") for c in checks)
    return "tested" if every and all(c["exit_code"] == 0 for c in commands) else "implemented"


# ----------------------------------------------------------------------------- limitations


def limitations() -> list[tuple[str, str, list[str], str]]:
    envelope = yaml.safe_load(ENVELOPE.read_text(encoding="utf-8"))
    rows = {row["id"]: row for row in envelope["limitations"]}
    web = [(" ".join(rows[r]["text"].split()), "E", [r], f"{r}, verbatim") for r in WEB_ROWS]
    return [*web, *EXTRA_LIMITATIONS]


def harvest_entries(path: str, manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The manifest's T08.A21 classification: its limitations by the table above; G16 as U14's;
    G3 and G12 without a CI run as pending in the manifest (P). Any other non-pass check stops
    the script: the generator does not classify a failure it did not expect."""
    from t08_support_matrix import text_sha256

    entries: list[dict[str, Any]] = []
    table = {text: (kind, to, note) for text, kind, to, note in limitations()}
    for index, text in enumerate(manifest["limitations"]):
        kind, to, note = table[text]
        entries.append(
            {
                "manifest": path,
                "item": f"limitations[{index}]",
                "sha256": text_sha256(text),
                "class": kind,
                "to": to,
                "note": note,
            }
        )
    for index, entry in enumerate(manifest["checks"]):
        if entry["result"] == "pass":
            continue
        if entry["id"] == "M06.G16":
            kind, to, note = "E", ["U14"], "W27 campaign is M07's (G16)"
        elif (
            entry["id"] in ("M06.G3", "M06.G12")
            and entry["value"].get("local_passed") is True
            and NOT_RECORDED in json.dumps(entry["value"])
        ):
            # Its local half passed; only the CI half is missing (review F2).
            kind, to, note = "P", [], "pending the green CI run (review F2); recorded with --add-ci"
        else:
            raise SystemExit(f"{entry['id']} is {entry['result']}: not classified; fix it first")
        entries.append(
            {
                "manifest": path,
                "item": f"checks[{index}]",
                "check_id": entry["id"],
                "sha256": text_sha256(entry),
                "class": kind,
                "to": to,
                "note": note,
            }
        )
    return entries


def _yaml_entry(entry: Mapping[str, Any]) -> str:
    lines = [f"- manifest: {entry['manifest']}", f"  item: {entry['item']}"]
    if "check_id" in entry:
        lines.append(f"  check_id: {entry['check_id']}")
    lines += [f"  sha256: {entry['sha256']}", f"  class: {entry['class']}"]
    lines += ["  to: []"] if not entry["to"] else ["  to:", *[f"  - {p}" for p in entry["to"]]]
    lines.append(f"  note: {entry['note']}")
    return "\n".join(lines) + "\n"


def write_harvest(entries: Sequence[Mapping[str, Any]]) -> None:
    """Replace the envelope's `evidence/M06/` harvest entries with `entries`, at the end of the
    list (the file's last section), leaving every other byte as it is."""
    text = ENVELOPE.read_text(encoding="utf-8")
    head, marker, body = text.partition("\nharvest:\n")
    if not marker:
        raise SystemExit("support_envelope.yaml has no harvest section")
    blocks = re.split(r"(?m)^(?=- manifest: )", body)
    kept = [b for b in blocks if b and not b.startswith("- manifest: evidence/M06/")]
    if any(not b.startswith("- manifest: ") for b in kept):
        raise SystemExit("support_envelope.yaml: unexpected text in the harvest section")
    ENVELOPE.write_text(
        head + marker + "".join(kept) + "".join(_yaml_entry(e) for e in entries), encoding="utf-8"
    )
    loaded = yaml.safe_load(ENVELOPE.read_text(encoding="utf-8"))["harvest"]
    written = [e for e in loaded if str(e.get("manifest", "")).startswith("evidence/M06/")]
    if written != [dict(e) for e in entries]:
        raise SystemExit("support_envelope.yaml: the harvest entries did not round-trip")


# ----------------------------------------------------------------------------- main


def _artifact(path: str, description: str) -> dict[str, str]:
    return {"path": path, "sha256": _sha256(ROOT / path), "description": description}


def build(
    commit: str, checks: list[dict[str, Any]], commands: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "work_package": "M06",
        "commit": commit,
        "requirements": [],
        "status": status(checks, commands),
        "inputs": {
            "case_id": "M06's acceptance: design note docs/design/M06-web-shell.md §11 gates "
            "G1-G16 at C (the W26 fixture project of §8, NET-02 and A02-352; the 50-revision "
            "T07 corpus; the pinned OpenIDAES-450 archive and the W27 registration as amended)",
            "case_hash": _sha256(NOTE),
            "environment_lock_hash": _sha256(ROOT / "requirements.lock"),
        },
        "commands": commands,
        "checks": checks,
        "artifacts": [
            _artifact("docs/design/M06-web-shell.md", "The design note, §14 as built."),
            _artifact("docs/adr/0030-diagnostic-web-shell.md", "ADR 0030."),
            _artifact("docs/adr/0019-application-contract-v1.md", "ADR 0019, Amendment 3."),
            _artifact("docs/reviews/M06-review.md", "The design-lane review (WO-13)."),
            _artifact("apps/web/js/routes.js", "The generated route table (G1)."),
            _artifact(
                "tests/web/fixtures/w26/exchanges.json", "The W26 fixture exchanges (G2, G7)."
            ),
            _artifact(
                "docs/derivations/M06-W27-registration.md", "The W27 registration, Amendment 1."
            ),
            _artifact("benchmarks/m06/openidaes450/registration.json", "The registration data."),
            _artifact("benchmarks/m06/openidaes450/coverage.json", "W27 coverage (G14)."),
            _artifact("benchmarks/m06/openidaes450/access_report.json", "W27 access (G13)."),
        ],
        "limitations": [text for text, _, _, _ in limitations()],
        "review": {"numerical": "pending", "process_model": "pending"},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--commit", required=True)
    parser.add_argument("--gate-log", type=Path)
    parser.add_argument("--default-install-log", type=Path)
    parser.add_argument("--g10-dir", type=Path)
    parser.add_argument("--g10-log", type=Path)
    parser.add_argument("--dryrun", type=Path)
    parser.add_argument("--ci-run", action="append", default=[])
    parser.add_argument(
        "--add-ci",
        action="store_true",
        help="record --ci-run runs in the existing manifest of --commit (G3, G10, G12)",
    )
    parser.add_argument("--harvest", action="store_true")
    arguments = parser.parse_args()
    commit = arguments.commit
    destination = ROOT / "evidence" / "M06" / commit / "manifest.json"
    if arguments.add_ci:
        manifest = add_ci(commit, destination, arguments.ci_run)
    else:
        local = ("gate_log", "default_install_log", "g10_dir", "g10_log", "dryrun")
        missing = [f"--{n.replace('_', '-')}" for n in local if getattr(arguments, n) is None]
        if missing:
            parser.error(f"a full run needs {', '.join(missing)}")
        manifest = generate(commit, destination, arguments)
    return finish(destination, manifest, arguments.harvest)


def own_paths(commit: str) -> list[str]:
    """What may change between `C` and a CI run's head: this manifest's files."""
    return [
        f"evidence/M06/{commit}/",
        "benchmarks/t08/support_envelope.yaml",
        "docs/support-matrix.md",
    ]


def add_ci(commit: str, destination: Path, run_ids: Sequence[str]) -> dict[str, Any]:
    """The manifest of `C` with CI's halves of G3, G10 and G12 decided from `run_ids`. Runs at
    `C` or at a descendant of `C` that changes only `own_paths`; the local halves stand as
    measured at `C` (nothing is re-run)."""
    if not run_ids:
        raise SystemExit("--add-ci needs at least one --ci-run")
    head = _git("rev-parse", "HEAD").strip()
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, head], cwd=ROOT, check=False
    )
    changed = _git("diff", "--name-only", commit, head).split() if ancestor.returncode == 0 else []
    foreign = [p for p in changed if not any(p.startswith(o) for o in own_paths(commit))]
    if ancestor.returncode != 0 or foreign:
        raise SystemExit(f"HEAD must be C or C plus this manifest's files only: {foreign}")
    manifest: dict[str, Any] = json.loads(destination.read_text(encoding="utf-8"))
    ci = read_ci(run_ids, commit, own_paths(commit))
    for entry in manifest["checks"]:
        if entry["id"].removeprefix("M06.") in CI_GATES:
            apply_ci(entry, ci)
    manifest["commands"] = [
        c for c in manifest["commands"] if not c["cmd"].startswith("gh run view")
    ] + _ci_commands(ci)
    manifest["status"] = status(manifest["checks"], manifest["commands"])
    return manifest


def _ci_commands(ci: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    return [
        {
            "cmd": f"gh run view {run['run']} --json databaseId,headSha,conclusion,event,jobs",
            "cwd": ".",
            "exit_code": 0,
        }
        for run in (ci or {}).get("runs", [])
    ]


def generate(commit: str, destination: Path, arguments: argparse.Namespace) -> dict[str, Any]:
    if _git("rev-parse", "HEAD").strip() != commit or _git(
        "status",
        "--porcelain",
        "--",
        "src",
        "tests",
        "benchmarks",
        "apps",
        "scripts",
        "docs/derivations",
        "docs/design",
    ):
        raise SystemExit(f"run at a clean checkout of {commit}: the code under test must be C's")
    gates = catalogue()
    if set(SELECTORS) - set(gates):
        raise SystemExit(f"selectors without a gate: {set(SELECTORS) - set(gates)}")

    artifacts = destination.parent / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    tests, test_command = run_tests(artifacts)
    assigned = tests.select([p for patterns in SELECTORS.values() for p in patterns])
    if set(tests.nodes) - set(assigned):
        raise SystemExit(f"M06 nodes under no gate: {sorted(set(tests.nodes) - set(assigned))}")
    node, node_command = run_node(artifacts)
    inputs = Inputs(
        commit=commit,
        tests=tests,
        node=node,
        gate=read_gate(arguments.gate_log),
        default_install=read_default_install(arguments.default_install_log),
        g10=read_g10(arguments.g10_dir, arguments.g10_log),
        dryrun=read_dryrun(arguments.dryrun),
        ci=read_ci(arguments.ci_run, commit, own_paths(commit)) if arguments.ci_run else None,
        gates=gates,
    )
    checks = [check(gate, inputs) for gate in gates]
    commands = [
        {
            "cmd": "OPENFLOWSHEET_REQUIRE_BROWSER=1 PYTHONPATH=src PATH=.venv/bin:$PATH "
            "./scripts/check.sh",
            "cwd": ".",
            "exit_code": 0 if inputs.gate["passed"] else 1,
            "stdout_sha256": inputs.gate["stdout_sha256"],
        },
        {
            "cmd": "python3.13 -m venv VENV && VENV/bin/python -m pip install -c requirements.lock "
            "-e '.[dev]' && VENV/bin/python -m pytest -q  (CI's default-install job, locally; "
            "the server extra absent)",
            "cwd": ".",
            "exit_code": 0 if inputs.default_install["passed"] else 1,
            "stdout_sha256": inputs.default_install["stdout_sha256"],
        },
        {
            "cmd": "python3.13 scripts/t08_dist.py --out W/rc-dist; a clean venv with the wheel's "
            "requirements at the lock and the wheel --no-deps, then the server extra at the lock; "
            "from W/outside-ui: VENV/bin/python scripts/m06_web_serve_check.py W/outside-ui  "
            "(CI's dist -> clean-install -> 'M06 G10' steps, locally)",
            "cwd": ".",
            "exit_code": 0 if inputs.g10["exit_line"] else 1,
            "stdout_sha256": _sha256(arguments.g10_log),
        },
        {
            "cmd": "PYTHONPATH=src:. .venv/bin/python -m benchmarks.m06.w27.dryrun --out "
            f"evidence/M06/W27/artifacts/dry-run/{commit[:7]}",
            "cwd": ".",
            "exit_code": 0 if inputs.dryrun["commit"] == commit else 1,
            "stdout_sha256": inputs.dryrun["summary_sha256"],
        },
        test_command,
        node_command,
        *_ci_commands(inputs.ci),
    ]
    return build(commit, checks, commands)


def finish(destination: Path, manifest: Mapping[str, Any], harvest: bool) -> int:
    """Write the manifest, report it, and with `harvest` classify it in the envelope."""
    destination.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", "utf-8")
    checks = manifest["checks"]
    counts = {r: sum(c["result"] == r for c in checks) for r in RESULTS}
    print(f"wrote {destination.relative_to(ROOT)}: status {manifest['status']}")
    print(", ".join(f"{n} {r}" for r, n in counts.items()))
    for entry in checks:
        print(f"  {entry['id']}: {entry['result']}")
    if harvest:
        path = destination.relative_to(ROOT).as_posix()
        write_harvest(harvest_entries(path, manifest))
        emitted = subprocess.run(
            [sys.executable, "scripts/t08_support_matrix.py", "--emit"],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            check=False,
        )
        if emitted.returncode != 0:
            return emitted.returncode
        print(f"harvest: {ENVELOPE.relative_to(ROOT)} and {MATRIX.relative_to(ROOT)} rewritten")
    return 0 if manifest["status"] == "tested" else 1


if __name__ == "__main__":
    raise SystemExit(main())
