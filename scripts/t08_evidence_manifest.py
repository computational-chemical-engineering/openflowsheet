"""Generate `evidence/T08/<C>/manifest.json` at the release candidate `C`, by measuring, not by
transcribing. T08 release spec §15 W5.3 and §8.1 item 5; brief `docs/briefs/T08-close.md`.

The manifest carries one check per assertion of the release spec's §9 catalogue (`T08.Axx`) and of
the build-first spec's catalogue (`T08.Bxx`, as amended), read from the two documents themselves so
that an assertion cannot be left out: an id without a check here, or a check without an id there,
stops the script. Each check is decided from the evidence that measured it, and its `value` names
that evidence:

1. **Tests, run here.** Every T08 test module, T04's PTC modules (B25: T04 A19–A22) and T07's
   offered-policies module (B27) are run once (`pytest --junitxml`) at the checked-out commit,
   whose distribution trees (ADR 0021 D2.4: `src/`, `schemas/`, `benchmarks/`, the lock,
   `pyproject.toml`, `MANIFEST.in`, `README.md`, `LICENSE`, `NOTICE`) must equal `C`'s, so the
   code under test is `C`'s; the script refuses to run otherwise. A check names its tests by
   module or `module::prefix*`; a failed node fails it, a skipped one leaves it `unsupported`, a
   selector that ran no node fails it. The one skip expected here is A02's "once the manifest
   exists" clause, which cannot run before this manifest is written: the script measures that
   clause itself (the ledger lists this manifest under V18–V20) and `check.sh` runs the nodes once
   it is committed.
2. **The RC records** (§8.1 item 4, Amendment R7 1): the committed copies under
   `evidence/T08/<C>/rc/`, each re-hashed against `rc/records.json` and read for its own verdict
   (`passed` and every check `pass`, `commit` = `C`, `tree_clean`, the lock; the A30 summaries'
   `verdict.pass`; the CI `check` logs' `check.sh: PASSED`; the `identity` log's G05 line).
3. **CI**, read only from the runs named on the command line (`--ci-run ID`, through `gh run view`,
   or `--ci-json FILE`, that command's saved output): a run counts only if its head is `C`. The RC
   dispatch run supplies the jobs; A41 also needs a `push` run at `C` that succeeded.
4. **The design lane's verdicts**, read from `docs/reviews/T08-verdicts.md` (the gate table through
   `scripts/v0_1_gate.py`, and the clause rows of the gate sections) and
   `docs/reviews/T08-verdict-V14b.md` (B20–B23). A FAIL is recorded `fail`; it is **accepted**
   only if its clause is one ADR 0021 D3 lists with Frank's dated acceptance.
5. **Direct measurements**: the lock's hash against T07's manifest (A40), the git order of PTC-R1's
   registration (B20, with the §A4.6 attestation), the envelope's B27 facts, the ledger (A02), and
   the gate script's own run at `C` (A50).

Status is `tested` only if every check is `pass` or a `fail` whose clause is accepted; otherwise
`implemented`. `reviewed` is never set, and both review fields stay `pending`.

Usage:
    PYTHONPATH=src:. .venv/bin/python scripts/t08_evidence_manifest.py --commit C \\
        --ci-run 37008077757 --ci-run 37008077056 [--out PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ElementTree
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import v0_1_gate  # noqa: E402

SPEC = ROOT / "docs" / "derivations" / "T08-release-spec.md"
BUILD_FIRST = ROOT / "docs" / "derivations" / "T08-build-first-spec.md"
VERDICTS = ROOT / "docs" / "reviews" / "T08-verdicts.md"
V14B = ROOT / "docs" / "reviews" / "T08-verdict-V14b.md"
RC_RECORD = ROOT / "docs" / "t08-rc-record.md"
ADR_0021 = ROOT / "docs" / "adr" / "0021-v0.1-release-policy.md"
ENVELOPE = ROOT / "benchmarks" / "t08" / "support_envelope.yaml"
LEDGER = ROOT / "docs" / "requirements.yaml"
SCHEMA = ROOT / "schemas" / "evidence-manifest.schema.json"
T07_MANIFEST = (
    ROOT / "evidence" / "T07" / "5f3d3ea25e8349b83c8f8382df3c793532971ca4" / "manifest.json"
)
PTC_R1 = ROOT / "benchmarks" / "t08" / "ptc_r1"
#: §15 W5.3: the requirements T08's manifest supplies evidence for.
REQUIREMENTS = ("D04", "A10", "D17", "D20")
RESULTS = ("pass", "fail", "unsupported", "not_applicable")
#: Build-first spec §A4.6 and Amendment 1: PTC-R1's registration commits, in order.
PTC_R1_ORDER = (
    ("C_reg", "9f5f29d"),
    ("C_A1", "30243f9"),
    ("C_case", "c337fa1"),
    ("C_res", "b11d7b3"),
)
#: A02's clause that runs only once a T08 manifest exists (`tests/test_t08_w1_ledger.py`).
MANIFEST_PENDING_SKIP = "no evidence/T08 manifest yet (W5.3)"
#: That test's V19 parametrization, which A02's T08 clause does not name: a skip by design.
NOT_A_CLAUSE_SKIP = "not in A02"


def _test_modules() -> list[str]:
    t08 = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "tests").glob("test_t08_*.py"))
    extra = [
        "tests/test_t04_ptc.py",
        "tests/test_t04_ptc_region.py",
        "tests/test_t07_b3_policies.py",
    ]
    return [*t08, *extra]


# ----------------------------------------------------------------------------- the catalogue


@dataclass(frozen=True)
class Spec:
    """One assertion's evidence; its result is the worst of the parts."""

    id: str
    tests: tuple[str, ...] = ()
    records: tuple[str, ...] = ()
    jobs: tuple[str, ...] = ()
    verdict: str | None = None
    measure: str | None = None


_KC = "tests/test_t08_kinetic_cstr.py::test_"
_WS = "tests/test_t08_w4_warm_starts.py::test_"
_ENV = "tests/test_t08_w2_support_envelope.py::test_"
_INV = "tests/test_t08_w2_inventory.py::test_"
_RC = "tests/test_t08_w4_rc.py::test_"
_V19 = "tests/test_t08_w3_v19_records.py::test_"
_GEN = "tests/test_t08_reference_generators.py::test_a00_generator_check_passes"
_IDS = (
    "identity/rc-identity.json",
    "ci/rc-steps-ubuntu-latest/identity/rc-identity.json",
    "ci/rc-steps-ubuntu-24.04-arm/identity/rc-identity.json",
)
_CORPUS = (
    "corpus-ref-x86-64.json",
    "ci/rc-steps-ubuntu-latest/corpus-ubuntu-latest.json",
    "ci/rc-steps-ubuntu-24.04-arm/corpus-ubuntu-24.04-arm.json",
)
_ENSEMBLE = (
    "ensemble/rc-ensemble-ref-x86-64.json",
    "ci/rc-ensemble-ubuntu-24.04-arm/rc-ensemble-ci-aarch64.json",
)
_SURFACE = (
    "surface/rc-surface.json",
    "ci/rc-steps-ubuntu-latest/surface/rc-surface.json",
    "ci/rc-steps-ubuntu-24.04-arm/surface/rc-surface.json",
)
_A30 = (
    "a30/t08-a30-x86_64.json",
    "ci/rc-steps-ubuntu-latest/a30/t08-a30-x86_64.json",
    "ci/rc-steps-ubuntu-24.04-arm/a30/t08-a30-aarch64.json",
)
_CERTIFICATES = (
    "certificates-ref-x86-64.json",
    "ci/rc-steps-ubuntu-latest/certificates-ubuntu-latest.json",
    "ci/rc-steps-ubuntu-24.04-arm/certificates-ubuntu-24.04-arm.json",
    "ci/rc-install-ubuntu-latest/certificates-ubuntu-latest.json",
    "ci/rc-install-ubuntu-24.04-arm/certificates-ubuntu-24.04-arm.json",
    "ci/rc-bundle-set-certificates/rc-certificates.json",
)
_LOCKS = (
    "ci/rc-install-ubuntu-latest/lock-installed-ubuntu-latest.json",
    "ci/rc-install-ubuntu-latest/lock-checkout-ubuntu-latest.json",
    "ci/rc-install-ubuntu-24.04-arm/lock-installed-ubuntu-24.04-arm.json",
    "ci/rc-install-ubuntu-24.04-arm/lock-checkout-ubuntu-24.04-arm.json",
)
_CHECK_JOBS = ("check (ubuntu-latest)", "check (ubuntu-24.04-arm)")
_STEPS = ("rc-steps (ubuntu-latest)", "rc-steps (ubuntu-24.04-arm)")
_INSTALL = ("clean-install (ubuntu-latest)", "clean-install (ubuntu-24.04-arm)")

SPECS: tuple[Spec, ...] = (
    Spec("A00", tests=(f"{_GEN}[t08_reference.py]",)),
    Spec(
        "A01",
        tests=(
            f"{_GEN}[t08_reference.py]",
            "tests/test_t08_w1_ledger.py::test_a02_v_gate_evidence*",
        ),
    ),
    Spec("A02", tests=("tests/test_t08_w1_ledger.py",), measure="ledger"),
    Spec("A03", tests=("tests/test_t08_w4_v0_1_gate.py",), measure="verdict_table"),
    Spec("A10", tests=("tests/test_t08_w1_d1_instance_ids.py",)),
    Spec("A11", tests=("tests/test_t08_w1_d2_replay_identity.py",)),
    Spec("A12", tests=("tests/test_t08_w1_d3_counters.py",)),
    Spec("A13", tests=("tests/test_t08_w1_identity_substitution.py::test_a13*",)),
    Spec("A14", tests=("tests/test_t08_w1_typed_ends.py",)),
    Spec("A15", tests=("tests/test_t08_w1_a89_repeats.py",)),
    Spec(
        "A16",
        tests=("tests/test_t08_w1_records.py", "tests/test_t08_rc_records.py"),
        measure="provenance",
    ),
    Spec("A17", tests=("tests/test_t08_w2_cli_rerun.py",)),
    Spec("A18", tests=("tests/test_t08_w2_description_reviews.py",)),
    Spec("A19", tests=("tests/test_t08_r3_a19_lock_lookup.py",), records=_LOCKS, jobs=_INSTALL),
    Spec("A20", tests=(f"{_ENV}a20*",)),
    Spec("A21", tests=(f"{_ENV}a21*",)),
    Spec("A22", tests=(f"{_ENV}a22*", "tests/test_t08_w2_unsupported.py")),
    Spec("A23", tests=(f"{_ENV}a23*",)),
    Spec("A24", tests=("tests/test_t08_w2_alias_threshold.py",)),
    Spec("A30", tests=(f"{_INV}a30*",), records=_A30, jobs=_STEPS),
    Spec("A31", tests=(f"{_INV}a31*",), records=("ci/rc-dist/t08-a43-dist.json",)),
    Spec("A32", tests=(f"{_INV}a32*",)),
    Spec(
        "A33", tests=("tests/test_t08_w2_recovery_edges.py", "tests/test_t08_w2_edge_identity.py")
    ),
    Spec(
        "A34",
        tests=(f"{_RC}the_audit*",),
        records=(*_CERTIFICATES, *_ENSEMBLE),
        jobs=(*_STEPS, *_INSTALL, "bundle-set", "rc-ensemble"),
    ),
    Spec("A35", tests=("tests/test_t08_w2_v000_probe.py",)),
    Spec("A40", tests=(f"{_GEN}[t08_reference.py]",), measure="lock"),
    Spec(
        "A41",
        records=("ci/job-logs/check-ubuntu-latest.log", "ci/job-logs/check-ubuntu-24.04-arm.log"),
        jobs=_CHECK_JOBS,
        measure="push_run",
    ),
    Spec(
        "A42",
        tests=(
            "tests/test_t08_w1_identity_substitution.py",
            "tests/test_t08_rename_substitution.py",
        ),
        records=(*_IDS, "ci/job-logs/identity.log"),
        jobs=("identity", *_STEPS),
    ),
    Spec(
        "A43",
        tests=("tests/test_t08_w4_package_data.py",),
        records=("ci/rc-dist/t08-a43-dist.json",),
        jobs=("dist",),
    ),
    Spec(
        "A44",
        records=(
            "ci/rc-install-ubuntu-latest/install-ubuntu-latest.json",
            "ci/rc-install-ubuntu-24.04-arm/install-ubuntu-24.04-arm.json",
        ),
        jobs=_INSTALL,
    ),
    Spec(
        "A45",
        tests=("tests/test_t08_adr0025.py", f"{_RC}a45*"),
        records=(
            "ci/rc-bundles/index.json",
            "ci/rc-replay-ubuntu-latest/replay-ubuntu-latest.json",
            "ci/rc-replay-ubuntu-24.04-arm/replay-ubuntu-24.04-arm.json",
        ),
        jobs=("bundle-set", "bundle-replay (ubuntu-latest)", "bundle-replay (ubuntu-24.04-arm)"),
        verdict="A45",
    ),
    Spec("A46", tests=(f"{_RC}a46*",), records=_ENSEMBLE, jobs=("rc-ensemble",)),
    Spec(
        "A47", tests=(f"{_RC}a47*",), records=(*_CORPUS, *_ENSEMBLE), jobs=(*_STEPS, "rc-ensemble")
    ),
    Spec("A48", tests=(f"{_RC}a47*",), records=_CORPUS, jobs=_STEPS),
    Spec("A49", tests=("tests/test_t08_w2_surface_digest.py",), records=_SURFACE, jobs=_STEPS),
    Spec("A50", tests=("tests/test_t08_w4_v0_1_gate.py",), measure="gate"),
    Spec("A60", tests=(f"{_V19}a60*",), verdict="V19 (ii)"),
    Spec("A61", tests=(f"{_V19}a61*",), verdict="V19 (iv)"),
    Spec("A62", tests=(f"{_V19}a62*",), verdict="V19 (iv)"),
    Spec("A63", tests=(f"{_V19}a62_a63*", f"{_V19}a63*"), verdict="V19 (iv)"),
    Spec("A64", tests=(f"{_V19}a64*",), verdict="V19 (v)"),
    Spec("A65", tests=(f"{_GEN}[t08_reference.py]",)),
    Spec("A70", verdict="V14 (b)"),
    Spec("A71", tests=(f"{_WS}b4*",), verdict="V13 (e)"),
    *(Spec(f"B0{n}", tests=(f"{_GEN}[t08_build_first_reference.py]",)) for n in range(10)),
    Spec("B10", tests=(f"{_KC}b10*",)),
    Spec("B11", tests=(f"{_KC}b11*",)),
    Spec("B12", tests=(f"{_KC}b12*",)),
    Spec("B13", tests=(f"{_KC}b13*",)),
    Spec("B14", tests=(f"{_KC}b14*",)),
    Spec("B15", tests=(f"{_KC}b15*",)),
    Spec("B16", tests=(f"{_KC}b16*",)),
    Spec("B17", tests=(f"{_KC}b17*",)),
    Spec("B18", tests=(f"{_KC}b18*",)),
    Spec("B19", tests=(f"{_KC}b19*", f"{_KC}b11_b19*")),
    Spec(
        "B20",
        tests=("tests/test_t08_ptc_r1_case.py::test_b20*",),
        verdict="B20",
        measure="git_order",
    ),
    Spec(
        "B21",
        tests=("tests/test_t08_ptc_r1_case.py::test_b21*",),
        verdict="B21",
        measure="ptc_results",
    ),
    Spec("B22", verdict="B22"),
    Spec("B23", tests=(f"{_KC}b14*",), verdict="B23"),
    Spec("B24", tests=("tests/test_t08_b24_ptc_job.py",)),
    Spec(
        "B25",
        tests=(
            "tests/test_t04_ptc.py::test_a19*",
            "tests/test_t04_ptc.py::test_a20*",
            "tests/test_t04_ptc_region.py::test_a21*",
            "tests/test_t04_ptc_region.py::test_a22*",
        ),
        jobs=_CHECK_JOBS,
    ),
    Spec(
        "B26",
        tests=(
            "tests/test_t08_w1_identity_substitution.py",
            "tests/test_t08_rename_substitution.py",
        ),
        records=_IDS,
    ),
    Spec(
        "B27", tests=(f"{_ENV}a20*", f"{_ENV}a22*", "tests/test_t07_b3_policies.py"), measure="b27"
    ),
    Spec("B28", tests=(f"{_GEN}[t08_build_first_reference.py]",), verdict="B28"),
    *(Spec(f"B4{n}", tests=(f"{_WS}b4{n}*",)) for n in range(10)),
    Spec(
        "B50",
        tests=("tests/test_t08_b50_surface_content.py", "tests/test_t08_w2_surface_digest.py"),
        records=_SURFACE,
    ),
    Spec("B51", verdict="V13 (e)"),
)


def catalogue() -> dict[str, tuple[str, str]]:
    """`T08.<id>` → (subject, judged by), from §9 of the release spec and the build-first spec's
    catalogue; a row repeated by an amendment replaces the earlier one."""
    found: dict[str, tuple[str, str]] = {}
    for path in (SPEC, BUILD_FIRST):
        for line in path.read_text(encoding="utf-8").splitlines():
            match = re.match(r"^\| T08\.([AB]\d\d) \|", line)
            if match:
                cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
                found[match[1]] = (cells[1], cells[-1])
    return dict(sorted(found.items()))


# ----------------------------------------------------------------------------- the tests


@dataclass
class TestRun:
    """The tests as the subprocess ran them: node id → (outcome, skip message), pytest's exit."""

    nodes: dict[str, tuple[str, str]]
    exit_code: int

    __test__ = False  # not a pytest class

    def select(self, selector: str) -> dict[str, tuple[str, str]]:
        """A module path, `path::function` with its parametrizations, `path::prefix*`, or one
        parametrized node `path::function[id]`."""
        path, _, name = selector.partition("::")
        found: dict[str, tuple[str, str]] = {}
        for nodeid, outcome in self.nodes.items():
            node_path, _, rest = nodeid.partition("::")
            if node_path != path:
                continue
            function = rest.split("[", 1)[0]
            if (
                not name
                or rest == name
                or function == name
                or (name.endswith("*") and function.startswith(name[:-1]))
            ):
                found[nodeid] = outcome
        return found


def _nodeid(classname: str, name: str) -> str:
    parts = classname.split(".")
    for index, part in enumerate(parts):
        if part.startswith("test_"):
            return "::".join(["/".join(parts[: index + 1]) + ".py", *parts[index + 1 :], name])
    return f"collection::{classname}::{name}"


def parse_junit(path: Path, exit_code: int) -> TestRun:
    nodes: dict[str, tuple[str, str]] = {}
    for case in ElementTree.parse(path).getroot().iter("testcase"):
        nodeid = _nodeid(case.get("classname", ""), case.get("name", ""))
        tags = {child.tag: child for child in case}
        if "failure" in tags or "error" in tags or nodes.get(nodeid, ("",))[0] == "failed":
            nodes[nodeid] = ("failed", "")
        elif "skipped" in tags:
            nodes[nodeid] = ("skipped", tags["skipped"].get("message", ""))
        else:
            nodes[nodeid] = ("passed", "")
    return TestRun(nodes, exit_code)


def run_tests(artifacts: Path) -> tuple[TestRun, dict[str, Any]]:
    junit = artifacts / "t08-tests.junit.xml"
    stdout = artifacts / "t08-tests.stdout.txt"
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "src"), str(ROOT)])
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            f"--junitxml={junit}",
            *_test_modules(),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    stdout.write_text(completed.stdout, encoding="utf-8")
    command = {
        "cmd": "PYTHONPATH=src:. .venv/bin/python -m pytest -q -p no:cacheprovider "
        "--junitxml=ARTIFACTS/t08-tests.junit.xml " + " ".join(_test_modules()),
        "cwd": ".",
        "exit_code": completed.returncode,
        "stdout_sha256": _sha256(stdout),
    }
    return parse_junit(junit, completed.returncode), command


# ----------------------------------------------------------------------------- inputs


@dataclass
class Inputs:
    """What the checks judge. `main` measures it; the tests build it."""

    commit: str
    tests: TestRun
    ci: list[dict[str, Any]] = field(default_factory=list)
    gate: dict[str, Any] | None = None
    manifest_exists: bool = False
    verdicts: Path = VERDICTS
    v14b: Path = V14B
    adr_0021: Path = ADR_0021
    evidence: Path = ROOT / "evidence" / "T08"

    @property
    def rc_dir(self) -> Path:
        return self.evidence / self.commit / "rc"


def _git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def _git_ok(*arguments: str) -> bool:
    return subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True).returncode == 0


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _shown(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else path.name


# ----------------------------------------------------------------------------- evidence readers

Part = tuple[str, dict[str, Any]]


def _tests(selectors: Sequence[str], inputs: Inputs) -> Part:
    nodes: dict[str, tuple[str, str]] = {}
    missing = []
    for selector in selectors:
        found = inputs.tests.select(selector)
        if not found:
            missing.append(selector)
        nodes.update(found)
    failed = sorted(n for n, (o, _) in nodes.items() if o == "failed")
    skipped = sorted(n for n, (o, _) in nodes.items() if o == "skipped")
    pending = [
        n
        for n in skipped
        if (nodes[n][1] == MANIFEST_PENDING_SKIP and not inputs.manifest_exists)
        or nodes[n][1] == NOT_A_CLAUSE_SKIP
    ]
    value = {
        "selectors": list(selectors),
        "nodes": len(nodes),
        "outcomes": dict(sorted(Counter(o for o, _ in nodes.values()).items())),
        "failed": failed,
        "skipped": skipped,
        "missing": missing,
    }
    if pending:
        value["skipped_by_design"] = {n: nodes[n][1] for n in pending}
    if failed or missing:
        return "fail", value
    if set(skipped) - set(pending):
        return "unsupported", value
    return "pass", value


def rc_index(inputs: Inputs) -> dict[str, dict[str, Any]]:
    index = json.loads((inputs.rc_dir / "records.json").read_text(encoding="utf-8"))
    if index.get("commit") != inputs.commit:
        raise ValueError(f"rc/records.json is of {index.get('commit')}, not {inputs.commit}")
    return {entry["path"]: entry for entry in index["files"]}


def _record(path: str, inputs: Inputs, index: Mapping[str, Mapping[str, Any]]) -> tuple[bool, str]:
    """One RC record: committed, hashing to its entry, and saying it passed at `C`."""
    entry = index.get(path)
    file = inputs.rc_dir / path
    if entry is None or not entry.get("committed") or not file.is_file():
        return False, "not a committed record of rc/records.json"
    if _sha256(file) != entry["sha256"]:
        return False, "sha256 differs from rc/records.json"
    if path.endswith(".log"):
        text = file.read_text(encoding="utf-8", errors="replace")
        wanted = (
            "G05: R0 structural identity equal across 2 platforms"
            if "identity" in path
            else "=== check.sh: PASSED ==="
        )
        return wanted in text, f"contains {wanted!r}: {wanted in text}"
    document = json.loads(file.read_text(encoding="utf-8"))
    if document.get("format") == "t08-a30-inventory-v1-summary":
        ok = (
            document["verdict"]["pass"] is True
            and not document["verdict"]["undispositioned_in_required_closure"]
        )
        return ok, f"verdict.pass {document['verdict']['pass']}"
    provenance = document.get("provenance") or document
    commit_ok = provenance.get("commit") == inputs.commit and provenance.get("tree_clean") is True
    if "entries" in document:  # the bundle-set index: no check list (RC record step 5)
        exits = Counter(entry.get("exit") for entry in document["entries"])
        ok = commit_ok and document["n_b"] == len(document["entries"]) == 52 and set(exits) == {0}
        return ok, f"n_b {document['n_b']}, exits {dict(exits)}, at C {commit_ok}"
    checks = Counter(check.get("result") for check in document.get("checks", []))
    ok = commit_ok and document.get("passed") is True and bool(checks) and set(checks) == {"pass"}
    return ok, f"passed {document.get('passed')}, checks {dict(checks)}, at C {commit_ok}"


def _records(paths: Sequence[str], inputs: Inputs) -> Part:
    try:
        index = rc_index(inputs)
    except (OSError, ValueError, KeyError) as error:
        return "fail", {"error": f"{type(error).__name__}: {error}"}
    read = {path: _record(path, inputs, index) for path in paths}
    value = {"rc_records": {path: said for path, (_, said) in read.items()}}
    return ("pass" if all(ok for ok, _ in read.values()) else "fail"), value


def _runs_at_c(inputs: Inputs) -> list[dict[str, Any]]:
    return [run for run in inputs.ci if run.get("headSha") == inputs.commit]


def _jobs(names: Sequence[str], inputs: Inputs) -> Part:
    runs = _runs_at_c(inputs)
    if not runs:
        return "unsupported", {"state": "pending", "reason": "no CI run at C was given"}
    conclusions: dict[str, str] = {}
    for run in runs:
        for job in run.get("jobs", []):
            if job["name"] in names and conclusions.get(job["name"]) != "success":
                conclusions[job["name"]] = str(job.get("conclusion"))
    found = {name: conclusions.get(name, "absent") for name in names}
    value = {"ci_runs": [run.get("databaseId") for run in runs], "jobs": found}
    return ("pass" if all(c == "success" for c in found.values()) else "fail"), value


# -- the verdicts ----------------------------------------------------------------------------


def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    following = text.find("\n## ", start + 1)
    return text[start : following if following != -1 else len(text)]


def _row(section: str, first_cell: str) -> list[str]:
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if line.startswith("|") and v0_1_gate._bare(cells[0]).startswith(first_cell):
            return cells
    raise ValueError(f"no row {first_cell!r}")


def accepted(inputs: Inputs) -> dict[str, str]:
    return v0_1_gate.accepted_clauses(inputs.adr_0021.read_text(encoding="utf-8"))


def _verdict(key: str, inputs: Inputs) -> Part:
    """The design lane's judgement of `key`, as its document records it. A clause judged not met
    is `fail`, with `accepted_fail` saying whether ADR 0021 D3 lists it with Frank's date."""
    text = inputs.verdicts.read_text(encoding="utf-8")
    gates = v0_1_gate.verdict_rows(text)
    if key.startswith("V"):
        gate, clause = key.split(" ", 1)
        cells = _row(_section(text, f"## {gate} —"), clause)
        word = v0_1_gate._bare(cells[1]).lower()
        value: dict[str, Any] = {
            "source": _shown(inputs.verdicts),
            "gate": gate,
            "gate_verdict": gates[gate].verdict,
            "clause": key,
            "judgement": v0_1_gate._bare(cells[1]),
        }
        if word == "met":
            return ("pass" if gates[gate].verdict == "PASS" else "fail"), value
        value["accepted_fail"] = key in accepted(inputs) and key in gates[gate].clauses
        if value["accepted_fail"]:
            value["accepted_in"] = f"ADR 0021 D3: {accepted(inputs)[key]}"
        return "fail", value
    if key == "A45":
        section = _section(text, "## T08.A45 at `C`")
        words = [
            v0_1_gate._bare(_row(section, half)[-1])
            for half in ("write", "fresh x86-64 replay", "aarch64 replay")
        ]
        value = {"source": _shown(inputs.verdicts), "halves": words}
        return ("pass" if words == ["met"] * 3 else "fail"), value
    # B20–B23 and B28: `T08-verdict-V14b.md`'s verdict table (rows `| n | **T08.Bxx** …`).
    v14b = inputs.v14b.read_text(encoding="utf-8")
    if key == "B28":
        heading = re.search(r"^### 3\.\d+ T08\.B28 .*: (\S+)", v14b, flags=re.MULTILINE)
        word = heading[1] if heading else "absent"
        return ("pass" if word == "MET" else "fail"), {
            "source": _shown(inputs.v14b),
            "judgement": word,
        }
    (line,) = [ln for ln in v14b.splitlines() if re.match(rf"^\| \d+ \| \*\*T08\.{key}\*\*", ln)]
    bold = re.search(r"\*\*([^*]+)\*\*", line.strip().strip("|").split("|")[-1])
    judgement = bold[1].strip() if bold else "absent"
    value = {"source": _shown(inputs.v14b), "judgement": judgement}
    if judgement == "MET":
        return "pass", value
    if key == "B20" and judgement == "INSUFFICIENT EVIDENCE":
        # The one outstanding clause is this manifest's §A4.6 attestation (the verdict's
        # "smallest addition that settles B20"), which `git_order` measures and writes.
        value["outstanding_clause"] = "the manifest attests §A4.6's prohibitions up to C_case"
        value["supplied_by"] = "this manifest (B20's value `attestation`, and its limitations)"
        return "pass", value
    value["accepted_fail"] = key == "B23" and "V14 (b)" in accepted(inputs)
    if value["accepted_fail"]:
        value["accepted_in"] = (
            "ADR 0021 D3, as V14 (b) (B23 is its saddle clause): " + accepted(inputs)["V14 (b)"]
        )
    return "fail", value


# -- direct measurements -------------------------------------------------------------------


def _m_ledger(inputs: Inputs) -> Part:
    ledger = yaml.safe_load(LEDGER.read_text(encoding="utf-8"))
    gates = {entry["id"]: entry for entry in ledger["gates"]}
    path = f"evidence/T08/{inputs.commit}/manifest.json"
    listed = {gate: path in gates[gate]["evidence"] for gate in ("V18", "V19", "V20")}
    words = {gate: gates[gate]["verdict"] for gate in v0_1_gate.GATES}
    document = {
        g: r.verdict for g, r in v0_1_gate.verdict_rows(inputs.verdicts.read_text("utf-8")).items()
    }
    ok = all(listed.values()) and words == document
    return ("pass" if ok else "fail"), {
        "manifest_listed": listed,
        "verdicts_equal_document": words == document,
    }


def _m_verdict_table(inputs: Inputs) -> Part:
    try:
        rows = v0_1_gate.verdict_rows(inputs.verdicts.read_text(encoding="utf-8"))
    except ValueError as error:
        return "fail", {"error": str(error)}
    words = {gate: row.verdict for gate, row in rows.items()}
    return ("pass" if set(words) == set(v0_1_gate.GATES) else "fail"), {"verdicts": words}


def _m_provenance(inputs: Inputs) -> Part:
    """T08.A16: every committed `t08-rc-v1` record (and the A43 record) carries `commit` = `C`,
    `tree_clean` true and the lock's sha256."""
    lock = _sha256(ROOT / "requirements.lock")
    bad: list[str] = []
    seen = 0
    for path in sorted(inputs.rc_dir.rglob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("format") not in ("t08-rc-v1", "t08-a43-dist-v1"):
            continue
        seen += 1
        provenance = document.get("provenance") or document
        if (
            provenance.get("commit"),
            provenance.get("tree_clean"),
            provenance.get("environment_lock_sha256"),
        ) != (inputs.commit, True, lock):
            bad.append(str(path.relative_to(inputs.rc_dir)))
    return ("pass" if seen and not bad else "fail"), {"records": seen, "not_attributable": bad}


def _m_lock(inputs: Inputs) -> Part:
    ours = _sha256(ROOT / "requirements.lock")
    t07 = json.loads(T07_MANIFEST.read_text(encoding="utf-8"))["inputs"]["environment_lock_hash"]
    return ("pass" if ours == t07 else "fail"), {
        "lock_sha256": ours,
        "t07_environment_lock_hash": t07,
    }


def _m_push_run(inputs: Inputs) -> Part:
    pushes = [run for run in _runs_at_c(inputs) if run.get("event") == "push"]
    value = {"push_runs": {str(run.get("databaseId")): run.get("conclusion") for run in pushes}}
    if not pushes:
        return "unsupported", {**value, "state": "pending", "reason": "no push run at C was given"}
    return ("pass" if any(run.get("conclusion") == "success" for run in pushes) else "fail"), value


def _m_gate(inputs: Inputs) -> Part:
    """`v0_1_gate.py --rc C` at this commit: no reason but the manifest this run writes."""
    if inputs.gate is None:
        return "unsupported", {"state": "pending", "reason": "the gate script was not run"}
    pending = (
        f"no T08 manifest: evidence/T08/{inputs.commit}/manifest.json does not exist (§8.1 item 5)"
    )
    others = [reason for reason in inputs.gate["reasons"] if reason != pending]
    return ("pass" if not others else "fail"), dict(inputs.gate)


def ptc_r1_order() -> dict[str, Any]:
    """§A4.6's git facts: each registration commit an ancestor of the next, and every commit
    that added a PTC-R1 result file a descendant of `C_case`."""
    full = {name: _git("rev-parse", f"{short}^{{commit}}").strip() for name, short in PTC_R1_ORDER}
    names = [name for name, _ in PTC_R1_ORDER]
    links = {
        f"{a} ⊑ {b}": _git_ok("merge-base", "--is-ancestor", full[a], full[b])
        for a, b in zip(names, names[1:], strict=False)
    }
    added = _git(
        "log", "--all", "--diff-filter=A", "--format=%H", "--", "benchmarks/t08/ptc_r1/results-*"
    ).split()
    # A public release commit made without the development history (the orphan v0.1.0 root of
    # the public repository, R-150) shares no history with the development line; it is a copy,
    # not a commit that produced a result, so §A4.6's ancestry rule is judged on the development
    # history only and the unrelated commits are listed, not dropped silently.
    related = [c for c in added if _git_ok("merge-base", full["C_reg"], c)]
    unrelated = sorted(c[:12] for c in added if c not in related)
    after = {
        commit[:12]: _git_ok("merge-base", "--is-ancestor", full["C_case"], commit)
        for commit in related
    }
    return {
        "commits": full,
        "links": links,
        "result_files_added_by": after,
        "unrelated_history_ignored": unrelated,
    }


def attestation(order: Mapping[str, Any]) -> str:
    descendants = ", ".join(f"`{c}`" for c in order["result_files_added_by"]) or "none"
    return (
        "§A4.6 attestation (build lane, T08 close, from the records): before `C_case` = "
        "`c337fa1` no PTC run was made on the PTC-R1 flowsheet from any start, and no Newton run "
        "from a registered start. Basis: the git order `C_reg` `9f5f29d` → `C_A1` `30243f9` → "
        "`C_case` `c337fa1` → `C_res` `b11d7b3` holds (measured here), and every commit that "
        f"added a `benchmarks/t08/ptc_r1/results-*` file ({descendants}) descends from "
        "`C_case`; build-first Amendment 1's preamble records the only pre-`C_case` evaluations "
        "— W2's rows and Jacobians at the three roots and single steps at the three off-grid "
        "states, and the design lane's single-step directions at the same six states — both "
        "inside §A4.6's allowance; review 1 (`docs/reviews/T08-review.md`, at `C_case`) records "
        "that no PTC-R1 result existed and none was produced there. Disclosed after `C_case`, "
        "none forbidden by §A4.6: (1) the reviewer's LOW-root probe, one run per arm from the "
        "LOW root (not a registered start), both `CONVERGED` at step 0, class LOW "
        "(`docs/reviews/T08-review.md`); (2) the aborted first local `ref-x86-64` invocation at "
        "`8d311b9`, which computed and failed to write (its output directory was missing), was "
        "re-run unchanged, and printed no summary, so there was no choice between runs "
        "(`docs/reviews/T08-verdict-V14b.md` §3.1); (3) the `src/` changes after `C_case` "
        "(`c337fa1..4e92e0d`), found inert on every path the arms execute — nothing under "
        "`numerics/`, `thermo/`, `models/`, `orchestrator/region*`, `revision_binding.py` or "
        "`verify/certificate.py`; `executor.py`'s `_warm_start` runs only without a "
        "`user_start`, which the harness always passes; `policies.py` adds `T08-ptc-v1`, and "
        "both arms' `policy_sha256` recompute; the failure-bundle and STR-naming changes are not "
        "called on a solve (`docs/reviews/T08-verdict-V14b.md` §1)."
    )


def _m_git_order(inputs: Inputs) -> Part:
    order = ptc_r1_order()
    ok = (
        all(order["links"].values())
        and all(order["result_files_added_by"].values())
        and bool(order["result_files_added_by"])
    )
    return ("pass" if ok else "fail"), {**order, "attestation": attestation(order)}


def _m_ptc_results(inputs: Inputs) -> Part:
    names = ("results-ref-x86-64.json", "results-ci-aarch64.json", "results-ci-x86-64.json")
    present = {name: (PTC_R1 / name).is_file() for name in names}
    return ("pass" if all(present.values()) else "fail"), {"committed": present}


def _m_b27(inputs: Inputs) -> Part:
    envelope = yaml.safe_load(ENVELOPE.read_text(encoding="utf-8"))
    axes = {row["id"]: row for row in envelope["axes"]}
    policies = sorted(axes["solve_policies"]["members"])
    models = axes["unit_models"]["members"]
    (u07,) = [row for row in envelope["unsupported"] if row["id"] == "U07"]
    limitation_ids = {row["id"] for row in envelope["limitations"]}
    facts = {
        # T08's thirteen SYN-001 models. The envelope is v0.2's working one (R-193); since M02's
        # join it also lists the eight C1 models (R-280 (c)), which are not T08's (B13's rule).
        "models": len([model for model in models if model.startswith("syn001.")]),
        "offered_policies": policies,
        "u07_names_kinetic_cstr": "kinetic_cstr" in u07["outcome"],
        "l_cstr_rows": sorted(i for i in limitation_ids if i.startswith("L-CSTR")),
    }
    ok = (
        facts["models"] == 13
        and policies == sorted(["T06-revision-v2", "T04-W12", "T08-ptc-v1", "T08-warm-v1"])
        and facts["u07_names_kinetic_cstr"]
        and facts["l_cstr_rows"] == ["L-CSTR-1", "L-CSTR-2", "L-CSTR-3"]
    )
    return ("pass" if ok else "fail"), facts


MEASURES: dict[str, Callable[[Inputs], Part]] = {
    "ledger": _m_ledger,
    "verdict_table": _m_verdict_table,
    "provenance": _m_provenance,
    "lock": _m_lock,
    "push_run": _m_push_run,
    "gate": _m_gate,
    "git_order": _m_git_order,
    "ptc_results": _m_ptc_results,
    "b27": _m_b27,
}


# ----------------------------------------------------------------------------- deciding


def _result(parts: Sequence[str]) -> str:
    if not parts:
        return "unsupported"
    if "fail" in parts:
        return "fail"
    if "unsupported" in parts:
        return "unsupported"
    return "pass"


def decide(spec: Spec, subject: str, judged_by: str, inputs: Inputs) -> dict[str, Any]:
    parts: list[str] = []
    value: dict[str, Any] = {"judged_by": judged_by}
    sources: list[tuple[str, Callable[[], Part]]] = []
    if spec.tests:
        sources.append(("tests", lambda: _tests(spec.tests, inputs)))
    if spec.records:
        sources.append(("records", lambda: _records(spec.records, inputs)))
    if spec.jobs:
        sources.append(("ci", lambda: _jobs(spec.jobs, inputs)))
    if spec.verdict is not None:
        verdict = spec.verdict
        sources.append(("verdict", lambda: _verdict(verdict, inputs)))
    if spec.measure is not None:
        measure = spec.measure
        sources.append(("measured", lambda: MEASURES[measure](inputs)))
    for name, read in sources:
        try:
            result, said = read()
        except Exception as error:  # noqa: BLE001 - evidence that could not be read did not pass
            result, said = "fail", {"error": f"{type(error).__name__}: {error}"}
        parts.append(result)
        value[name] = said
    result = _result(parts)
    if result == "fail" and all(
        (value.get(name) or {}).get("accepted_fail") is True
        for name, part in zip([n for n, _ in sources], parts, strict=True)
        if part == "fail"
    ):
        value["accepted_fail"] = True
    # An angle-bracketed span is a template placeholder in a manifest (A45's `solve <case_id>`).
    description = re.sub(r"<([^<>]*)>", r"{\1}", subject)
    return {"id": f"T08.{spec.id}", "description": description, "result": result, "value": value}


def checks(inputs: Inputs) -> list[dict[str, Any]]:
    listed = catalogue()
    specs = {spec.id: spec for spec in SPECS}
    if set(listed) != set(specs) or len(specs) != len(SPECS):
        raise SystemExit(
            "the catalogue and the checks differ: catalogue only "
            f"{sorted(set(listed) - set(specs))}, "
            f"checks only {sorted(set(specs) - set(listed))}"
        )
    return [decide(specs[i], subject, judged, inputs) for i, (subject, judged) in listed.items()]


def status(entries: Sequence[Mapping[str, Any]]) -> str:
    """`tested` only if every check passes or is a FAIL whose clause Frank accepted (ADR 0021 D3);
    never `reviewed`."""
    if all(
        entry["result"] == "pass"
        or (entry["result"] == "fail" and entry["value"].get("accepted_fail") is True)
        for entry in entries
    ):
        return "tested"
    return "implemented"


# ----------------------------------------------------------------------------- limitations


def limitations(inputs: Inputs, entries: Sequence[Mapping[str, Any]]) -> list[str]:
    envelope = yaml.safe_load(ENVELOPE.read_text(encoding="utf-8"))
    by_id = {entry["id"]: entry for entry in entries}
    order = (by_id["T08.B20"]["value"].get("measured") or {}).get("attestation")
    gates = v0_1_gate.verdict_rows(inputs.verdicts.read_text(encoding="utf-8"))
    tests_changed = _git("diff", "--name-only", inputs.commit, "HEAD", "--", "tests").split()
    stated = [
        "Evidence class: numerical and software verification at the release candidate `C` (tests, "
        "the RC job's records on ref-x86-64, ci-x86-64 and ci-aarch64, CI), and the design lane's "
        "verdicts (`docs/reviews/T08-verdicts.md`, `docs/reviews/T08-verdict-V14b.md`); V19 is a "
        "selection's feasibility, not validation; nothing here is empirical validation of a "
        "process model, and there is no optimality evidence. Status `tested` is the build lane's; "
        "`reviewed` is never set by this generator, and `review.numerical` and "
        "`review.process_model` stay `pending` for Frank.",
        "Gates V11–V20 are not requirement ids the frozen evidence schema accepts; their verdicts "
        "travel in `docs/requirements.yaml` and here: "
        + "; ".join(
            f"{gate} {row.verdict}" + (f" ({', '.join(row.clauses)})" if row.clauses else "")
            for gate, row in gates.items()
        )
        + ".",
        "FAIL: V14 (b) — one PTC family qualified by §7.5 with tested SER — is FAIL on PTC-R1 (the "
        "saddle clause: PTC ends `MID` from 149 of 441 starts on ref-x86-64 and on ci-aarch64; "
        "T08.A70 and T08.B23 `fail`), accepted by Frank on 2026-09-29 in ADR 0021 D3, and printed "
        'FAIL everywhere, never "met with limitations". PTC is experimental (L01).',
        "The tests were run by this generator at the commit that carries it, whose ADR 0021 D2.4 "
        "trees equal `C`'s (checked before anything ran), so the code under test is `C`'s; "
        "`tests/` differs from `C`'s in: "
        + (", ".join(tests_changed) or "nothing")
        + ". Among them `tests/test_t08_b24_ptc_job.py`, T08.B24's test, was written at T08 close: "
        "B24 had no test before (a DECISION recorded in its commit).",
    ]
    if order:
        stated.append(order)
    stated += [
        "T08.A45 is met at `C` under `T08-numerical-policy-v2` (ADR 0025), adopted after A45 "
        "failed at `814e151` under `K04-numerical-policy-v1`; that FAIL stands. Pivot-path "
        "diagnostics are recorded and not compared (control C3 is a deliberate blind spot); on "
        "aarch64 34 of 52 bundles agree within the policy, not bitwise.",
        "V13 (e)'s PASS rests on B50 as amended twice by Frank after it was first found not met "
        "(R-134, the digest; R-144, the package version).",
        "V19's PASS is feasibility: light gases vapour-only (dissolved gases not represented); "
        "K_NH₃ pending Frank's check against Rossetti et al. 2006; `k_ij` = 0 in the smoke runs; "
        "property values to be chosen by M01 from open, cited sources; no experimental VLE data "
        "identified; three group tests not reproduced; the dossier is an unreviewed draft.",
        "`library-only`: V13 clause (b)'s safeguarded Anderson recycle and V14 (c)'s edges E1 and "
        "E2 are tested library capabilities, not application paths.",
        "T08.A34's audit did not separately cover the certificates the replays re-emit.",
        "The RC records: 42 of the 44 the RC record cites are committed under "
        f"`evidence/T08/{inputs.commit}/rc/` (Amendment R7 1); the two ensemble run files "
        "(2.4 MB each) exist on one host (git-ignored) and as CI artifacts with finite retention.",
        "Bitwise reproduction is reported, never promised (ADR 0007 F1); portability beyond Linux "
        "x86-64 and aarch64, Python 3.13 and the one lock is not established.",
    ]
    for row in envelope["limitations"]:
        stated.append(f"{row['id']}: " + " ".join(str(row["text"]).split()))
    for entry in entries:
        if entry["result"] != "pass" and not entry["value"].get("accepted_fail"):
            stated.append(f"{entry['id']} is `{entry['result']}`: its value names every departure.")
    return stated


# ----------------------------------------------------------------------------- the manifest


def _case_hash(inputs: Inputs) -> str:
    digest = hashlib.sha256()
    for path in (
        SPEC,
        BUILD_FIRST,
        inputs.verdicts,
        inputs.v14b,
        RC_RECORD,
        inputs.rc_dir / "records.json",
    ):
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _artifact_rows(inputs: Inputs, artifacts: Path | None) -> list[dict[str, str]]:
    rows = [
        (RC_RECORD, "the RC record at C (§8.1 item 4)"),
        (inputs.rc_dir / "records.json", "the RC records: sha256, size and where each is kept"),
        (inputs.verdicts, "the design lane's verdicts V11–V20 at C"),
        (inputs.v14b, "the design lane's verdict on V14 (b), PTC-R1 (B20–B23, B28)"),
        (ENVELOPE, "the v0.1 support envelope (limitations L-rows, unsupported U-rows)"),
    ]
    found = [
        {"path": _shown(path), "sha256": _sha256(path), "description": description}
        for path, description in rows
    ]
    if artifacts is not None:
        for name, description in (
            ("t08-tests.junit.xml", "the tests run here, per node (not committed)"),
            ("v0_1_gate.json", "the gate script's report at C, run here (not committed)"),
        ):
            path = artifacts / name
            if path.is_file():
                shown = (
                    str(path.relative_to(ROOT))
                    if path.is_relative_to(ROOT)
                    else f"ARTIFACTS/{name}"
                )
                found.append({"path": shown, "sha256": _sha256(path), "description": description})
    return found


def build(
    inputs: Inputs, commands: Sequence[Mapping[str, Any]] = (), artifacts: Path | None = None
) -> dict[str, Any]:
    entries = checks(inputs)
    return {
        "work_package": "T08",
        "commit": inputs.commit,
        "requirements": list(REQUIREMENTS),
        "status": status(entries),
        "inputs": {
            "case_id": "T08's acceptance: plan row T08 (gates V11–V20, the V19 dossier, a "
            "reproducible release candidate) at C; one check per assertion of "
            "docs/derivations/T08-release-spec.md "
            f"§9 ({_sha256(SPEC)}) and docs/derivations/T08-build-first-spec.md's catalogue "
            f"({_sha256(BUILD_FIRST)}), as amended",
            "case_hash": _case_hash(inputs),
            "environment_lock_hash": _sha256(ROOT / "requirements.lock"),
        },
        "commands": [dict(command) for command in commands],
        "checks": entries,
        "artifacts": _artifact_rows(inputs, artifacts),
        "limitations": limitations(inputs, entries),
        "review": {"numerical": "pending", "process_model": "pending"},
    }


def strings(node: Any) -> Iterator[str]:
    if isinstance(node, dict):
        for key, item in node.items():
            yield str(key)
            yield from strings(item)
    elif isinstance(node, list):
        for item in node:
            yield from strings(item)
    elif isinstance(node, str):
        yield node


#: The evidence-manifest rule: an angle-bracketed span is a template placeholder, never evidence.
ANGLE_PLACEHOLDER = re.compile(r"<[^<>]*>")


def problems(manifest: Mapping[str, Any]) -> list[str]:
    from jsonschema import Draft202012Validator

    schema = json.loads(SCHEMA.read_text("utf-8"))
    found = [f"schema: {e.message}" for e in Draft202012Validator(schema).iter_errors(manifest)]
    found += [
        f"placeholder: {text[:80]}" for text in strings(manifest) if ANGLE_PLACEHOLDER.search(text)
    ]
    return found


def fetch_ci(run_id: str, artifacts: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    fields = "databaseId,headSha,conclusion,event,jobs,workflowName,url"
    completed = subprocess.run(
        ["gh", "run", "view", run_id, "--json", fields],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(f"gh run view {run_id}: {completed.stderr.strip()}")
    saved = artifacts / f"ci-run-{run_id}.json"
    saved.write_text(completed.stdout, encoding="utf-8")
    command = {
        "cmd": f"gh run view {run_id} --json {fields}",
        "cwd": ".",
        "exit_code": 0,
        "stdout_sha256": _sha256(saved),
    }
    return json.loads(completed.stdout), command


def run_gate(commit: str, artifacts: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    saved = artifacts / "v0_1_gate.json"
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "v0_1_gate.py"), "--rc", commit, "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    saved.write_text(completed.stdout, encoding="utf-8")
    report = json.loads(completed.stdout)
    gate = {
        "exit_code": completed.returncode,
        "tree_differences": report["tree_differences"],
        "rc_record_problems": report["rc_record_problems"],
        "reasons": report["reasons"],
    }
    command = {
        "cmd": f".venv/bin/python scripts/v0_1_gate.py --rc {commit} --json",
        "cwd": ".",
        "exit_code": completed.returncode,
        "stdout_sha256": _sha256(saved),
    }
    return gate, command


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--commit", required=True, help="the release candidate C")
    parser.add_argument("--ci-run", action="append", default=[], help="a CI run id (repeatable)")
    parser.add_argument(
        "--ci-json",
        action="append",
        type=Path,
        default=[],
        help="saved `gh run view ID --json databaseId,headSha,conclusion,event,"
        "jobs,workflowName,url` output (repeatable)",
    )
    parser.add_argument("--out", type=Path, default=None)
    arguments = parser.parse_args()

    commit = _git("rev-parse", f"{arguments.commit}^{{commit}}").strip()
    differing = v0_1_gate.tree_differences(commit, "HEAD")
    if differing:
        raise SystemExit(f"HEAD's distribution trees differ from C's (D2.4): {differing}")
    dirty = [line for line in _git("status", "--porcelain").splitlines() if "evidence/" not in line]
    if dirty:
        raise SystemExit(f"the tree is not clean: {dirty[:5]}")
    destination = arguments.out or (ROOT / "evidence" / "T08" / commit / "manifest.json")
    artifacts = ROOT / "evidence" / "T08" / commit / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    head = _git("rev-parse", "HEAD").strip()
    commands: list[dict[str, Any]] = []
    ci: list[dict[str, Any]] = []
    for run_id in arguments.ci_run:
        run, command = fetch_ci(run_id, artifacts)
        ci.append(run)
        commands.append(command)
    for path in arguments.ci_json:
        ci.append(json.loads(path.read_text("utf-8")))
        commands.append(
            {
                "cmd": f"gh run view {ci[-1].get('databaseId')} --json "
                "databaseId,headSha,conclusion,event,jobs,workflowName,url (saved output, read)",
                "cwd": ".",
                "exit_code": 0,
                "stdout_sha256": _sha256(path),
            }
        )
    tests, test_command = run_tests(artifacts)
    commands.append(test_command)
    gate, gate_command = run_gate(commit, artifacts)
    commands.append(gate_command)
    inputs = Inputs(commit, tests, ci, gate, manifest_exists=destination.is_file())

    manifest = build(inputs, commands, artifacts)
    manifest["commands"].append(
        {
            "cmd": "PYTHONPATH=src:. .venv/bin/python scripts/t08_evidence_manifest.py "
            f"--commit {commit}"
            + "".join(f" --ci-run {run_id}" for run_id in arguments.ci_run)
            + " (run at "
            + head
            + ")",
            "cwd": ".",
            "exit_code": 0,
        }
    )
    found = problems(manifest)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False, allow_nan=False) + "\n", "utf-8"
    )

    counts = Counter(entry["result"] for entry in manifest["checks"])
    accepted_fails = [e["id"] for e in manifest["checks"] if e["value"].get("accepted_fail")]
    print(
        "wrote "
        f"{destination.relative_to(ROOT) if destination.is_relative_to(ROOT) else destination}"
    )
    print(
        f"tests run here: pytest exit {tests.exit_code}, {len(tests.nodes)} nodes; "
        f"gate exit {gate['exit_code']}"
    )
    print(
        f"checks: {len(manifest['checks'])}: {counts['pass']} pass, {counts['fail']} fail "
        f"({len(accepted_fails)} accepted: {', '.join(accepted_fails) or 'none'}), "
        f"{counts['unsupported']} unsupported; status {manifest['status']}"
    )
    for entry in manifest["checks"]:
        if entry["result"] != "pass":
            print(
                f"  {entry['id']}: {entry['result']}"
                + (" (accepted)" if entry["value"].get("accepted_fail") else "")
            )
    for problem in found:
        print(f"invalid: {problem}")
    return 1 if found or manifest["status"] != "tested" else 0


if __name__ == "__main__":
    raise SystemExit(main())
