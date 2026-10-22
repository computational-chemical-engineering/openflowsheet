"""Generate `evidence/S04/<commit>/manifest.json` by running, not by transcribing. S04.

S04 is the package L01 (component-library gaps, `pr-lib-v1`) under its manifest id (D1, R-565):
check ids are `S04.<label>` for the L01 spec's `L01.<label>`; `T08.A32` keeps its id. File,
module and generator names keep `L01`. The checks are those of the WO-L01-R draft
(`docs/briefs/L01-WOR-manifest-draft.json`), re-taken at the checked-out commit, with L01.A22 as
amended (L01 spec §13.2, R-566) and the support-envelope checks S04's C2 changed (T08 release
spec §5.7 Amendment S04, R-568). Everything recorded is produced here, at the checked-out commit
(the script refuses to run when `HEAD` is not `--commit` or when a tracked source, test, script,
schema or derivation file differs from it; S01's rule):

1. **One pytest run** (`--junitxml`) of the L01 tests, T08's inventory and package-data tests,
   the M01 tests, ADR 0008's transient-readiness test, the W27 coverage pin test (§13.2 (c)) and
   the support-envelope tests, with `OFS_L01_SOURCES_PYTHON` set so that A12's retrieval re-run
   is executed, not skipped. A check judged by tests passes only if at least one node cites it
   and every node citing it passed (a skip or an expected failure is not a pass).
2. **`l01_reference.py --check`** (46 claims) and **`components_crosscheck.py --check`** under
   the pinned source interpreter.
3. **`t08_support_matrix.py --check`** (0 problems).
4. **`ruff check`, `ruff format --check`** on S04's files and **`mypy`** (no arguments).

`scripts/gate.sh` is not run here (it runs once before merge): its check is `unsupported`.
`status` is computed, never written: `tested` iff every check other than `S04.gate` passes;
otherwise `implemented`. Both review fields stay `pending`.

Usage:
    PYTHONPATH=src .venv/bin/python scripts/s04_evidence_manifest.py [--commit SHA] [--out PATH]
        [--sources-python PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parent))
from s01_evidence_manifest import (  # noqa: E402  (S01's generic helpers, unchanged)
    LOCK,
    ROOT,
    SCHEMA,
    Node,
    Run,
    check,
    command,
    nodes,
    refuse_unless_measuring,
    sha256_file,
    shown,
    text,
)

SPEC = ROOT / "docs" / "derivations" / "L01-spec.md"
REFERENCE = ROOT / "benchmarks" / "l01" / "reference_values.yaml"
RECORDS = ROOT / "benchmarks" / "l01" / "components.yaml"
CROSSCHECK = ROOT / "benchmarks" / "l01" / "components-crosscheck.json"
CROSSCHECK_SCRIPT = ROOT / "benchmarks" / "l01" / "components_crosscheck.py"
GENERATOR = ROOT / "docs" / "derivations" / "scripts" / "l01_reference.py"
MATRIX = ROOT / "scripts" / "t08_support_matrix.py"
#: The interpreter with the pinned source distributions (L01 spec §4.1), the draft's.
SOURCES_PYTHON = Path("/home/user/venv-l01-sources/bin/python")
#: The test battery (the draft's, with the W27 pin node and the envelope tests added).
BATTERY = (
    "tests/test_l01_*.py",
    "tests/test_t08_w2_inventory.py",
    "tests/test_t08_w4_package_data.py",
    "tests/test_m01_*.py",
    "tests/test_adr_0008_transient_readiness.py",
    "tests/test_t08_w2_support_envelope.py",
)
W27_PIN = (
    "tests/test_m06_w27_coverage.py::"
    "test_committed_coverage_json_is_g14_and_this_builds_classification"
)
#: The paths ruff checks (the draft's, with this script and C2's files).
LINT = (
    "src",
    "tests",
    "benchmarks/l01",
    "docs/derivations/scripts/l01_reference.py",
    "scripts/s04_evidence_manifest.py",
    "scripts/t08_support_matrix.py",
)
#: `l01_reference.py --check`'s verdict line (`tests/test_l01_provider.py`, CLAIM_COUNT 46).
CLAIMS = re.compile(r"^46 claims hold; reference_values\.yaml matches$", re.M)
#: An assertion id in a test function's name: `_aNN` followed by `_` or the end.
CITED = re.compile(r"(?:^|_)a(\d{2})(?=_|$)")
#: The provider's `vapour_unstable` message: the component and its tm.
REFUSAL = re.compile(r"^vapour_unstable: pure-(\S+) trial phase tm = (\S+) < 0 ")


def run(argv: Sequence[str], *, env: Mapping[str, str] | None = None) -> Run:
    """S01's `run` with `PYTHONPATH=src` and extra environment, both shown in `cmd`."""
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "src"), **(env or {})}
    completed = subprocess.run(
        list(argv), cwd=ROOT, env=environment, capture_output=True, text=True, check=False
    )
    prefix = "".join(f"{key}={value} " for key, value in (env or {}).items())
    cmd = (
        prefix
        + "PYTHONPATH=src "
        + " ".join(shown(part) if os.path.isabs(part) else part for part in argv)
    )
    return Run(cmd, completed.returncode, completed.stdout + completed.stderr)


def function(node: str) -> str:
    return node.rsplit("::", 1)[-1].split("[", 1)[0]


def cited(node: str) -> tuple[str, ...]:
    return tuple(f"A{number}" for number in CITED.findall(function(node)))


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
        "selectors": [text(item.node) for item in citing],
        "not_passed": not_passed,
    }
    return ("pass" if citing and not not_passed else "fail"), value


def by_tests(
    identifier: str, description: str, tests: Sequence[Node], select: Callable[[str], bool]
) -> dict[str, Any]:
    result, value = verdict([item for item in tests if select(item.node)])
    return check(identifier, description, result, value, "every citing node passed")


def by_tool(identifier: str, description: str, entry: Run, ok: bool) -> dict[str, Any]:
    return check(
        identifier,
        description,
        "pass" if ok else "fail",
        {"cmd": entry.cmd, "exit_code": entry.exit_code},
        "exit code 0",
    )


def m1_measured() -> dict[str, Any]:
    """M-1's three states: the provider's tm (from its refusal) and the review file's
    independent float transcription's most negative tm."""
    for path in (ROOT / "src", ROOT / "tests"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    import test_l01_review_adversarial as review

    measured: dict[str, Any] = {}
    for sid, state in review.UNSTABLE.items():
        message = review._evaluate(*state).message
        match = REFUSAL.match(message)
        measured[sid] = {
            "provider_message": message,
            "provider_component": match.group(1) if match else None,
            "provider_tm": float(match.group(2)) if match else None,
            "transcription_component": review._worst(*state),
            "transcription_tm": float(review._min_tm(*state)),
        }
    return measured


def limitations(entries: Sequence[Mapping[str, Any]]) -> list[str]:
    items = [
        "Scope: WO-L01-R (docs/reviews/L01-review.md M-1, M-2, M-3, S-1, S-2, N-6) and the S04 "
        "ruling's C1 and C2 (D1 §7, R-566, R-568); numerical verification of `pr-lib-v1` "
        "against independent 50-digit and float transcriptions, not empirical validation. The "
        "review's not-examined items (l01_projection.py, the re-take WO-L01-3, the dagger "
        "literature values Q-5) are untouched.",
        "`pr-lib-v1` is library-only until WO-L01-3 (L01 spec §13.4, R-569): it is not in "
        "revision_binding.SELECTABLE_BASES, so a revision cannot select it; a record_source of "
        "benchmarks/l01/components.yaml selects SYN-001's basis and the library's components "
        "are refused components_unsupported.",
        "vapour_unstable certifies a VAPOR answer of `pr-lib-v1` stable against pure-component "
        "trial phases only; a vapour unstable only towards a mixed liquid is not detected "
        "(L01 spec §12.3, §9 as corrected).",
        "Rights: T08.A32 checks that each `pr-lib-v1` record's rights statements exist; their "
        "correctness and whether the records ship are Frank's (L01-Q4). The records are not "
        "packaged (R-541).",
    ]
    for entry in entries:
        if entry["result"] == "pass" or entry["id"] == "S04.gate":
            continue
        value = entry.get("value")
        detail = (
            "; ".join(f"{item['node']} {item['outcome']}" for item in value["not_passed"])
            if isinstance(value, dict) and value.get("not_passed")
            else "see its value"
        )
        items.append(
            text(f"{entry['id']} is {entry['result']}: {detail} (see docs/L01_DECISIONS.md)")
        )
    return items


def status(entries: Sequence[Mapping[str, Any]]) -> str:
    """`tested` iff every check other than the unsupported gate passes."""
    required = [entry for entry in entries if entry["id"] != "S04.gate"]
    return "tested" if all(entry["result"] == "pass" for entry in required) else "implemented"


def build(commit: str, sources_python: Path) -> dict[str, Any]:
    refuse_unless_measuring(commit)
    artifacts = ROOT / "evidence" / "S04" / commit / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    junit = artifacts / "s04-tests.junit.xml"
    python = sys.executable
    tools = Path(python).parent
    tests = sorted({shown(path) for pattern in BATTERY for path in ROOT.glob(pattern)})
    sources = {"OFS_L01_SOURCES_PYTHON": str(sources_python)}

    runs = {
        "tests": run(
            [
                python,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                f"--junitxml={shown(junit)}",
                *tests,
                W27_PIN,
            ],
            env=sources,
        ),
        "generator": run([python, str(GENERATOR), "--check"]),
        "crosscheck": run([str(sources_python), str(CROSSCHECK_SCRIPT), "--check"]),
        "matrix": run([python, str(MATRIX), "--check"]),
        "ruff": run([str(tools / "ruff"), "check", *LINT]),
        "format": run([str(tools / "ruff"), "format", "--check", *LINT]),
        "mypy": run([str(tools / "mypy")]),
    }
    if not junit.is_file():
        raise SystemExit(f"pytest wrote no report (exit {runs['tests'].exit_code})")
    found = nodes(junit)

    def l01(identifier: str) -> Callable[[str], bool]:
        return lambda node: node.startswith("tests/test_l01_") and identifier in cited(node)

    m1 = m1_measured()
    m1_agree = all(
        entry["provider_component"] == entry["transcription_component"] for entry in m1.values()
    )
    wor1 = by_tests(
        "S04.WOR-1",
        "M-1 / R-540 (L01 spec §12.3): `pr-lib-v1` refuses vapour_unstable at the review's three "
        "states, naming the component with the most negative tm of the independent float "
        "transcription (tests/test_l01_review_adversarial.py); the five registered admitted "
        "mixtures stay ok. The provider's tm and the transcription's are recorded per state.",
        found,
        lambda node: node.startswith("tests/test_l01_review_adversarial.py::test_m1_"),
    )
    wor1["value"]["measured"] = m1
    if not m1_agree:
        wor1["result"] = "fail"

    generator_ok = runs["generator"].exit_code == 0 and bool(
        CLAIMS.search(runs["generator"].stdout)
    )
    wor2_nodes = by_tests(
        "S04.WOR-2",
        "",
        found,
        lambda node: function(node)
        == "test_the_generator_rederives_every_claim_and_the_committed_bytes",
    )
    wor2 = check(
        "S04.WOR-2",
        "l01_reference.py --check: 46 claims hold and reference_values.yaml matches; "
        "tests/test_l01_provider.py's generator node (CLAIM_COUNT 46) passed",
        "pass" if generator_ok and wor2_nodes["result"] == "pass" else "fail",
        {
            "cmd": runs["generator"].cmd,
            "exit_code": runs["generator"].exit_code,
            "verdict_line_found": generator_ok,
            "nodes": wor2_nodes["value"],
        },
        "exit code 0, the verdict line, and the node passed",
    )

    a12_nodes = by_tests("S04.A12", "", found, l01("A12"))
    a12 = check(
        "S04.A12",
        "R-528 (L01 spec §12.1): |c_p − c_p,CoolProp|/c_p ≤ 2 % at 300/600/900 K for all nine "
        "records; components_crosscheck.py --check matches under the pinned sources; every "
        "A12 node passed with OFS_L01_SOURCES_PYTHON set (the retrieval re-run executed, not "
        "skipped)",
        "pass" if runs["crosscheck"].exit_code == 0 and a12_nodes["result"] == "pass" else "fail",
        {
            "cmd": runs["crosscheck"].cmd,
            "exit_code": runs["crosscheck"].exit_code,
            "nodes": a12_nodes["value"],
        },
        "exit code 0 and every A12 node passed",
    )

    a01 = by_tests(
        "S04.A01",
        "L01.A01 with R-541 (L01 spec §12.5): nine records in the registered order; "
        "benchmarks/l01/components.yaml not packaged before WO-L01-3",
        found,
        l01("A01"),
    )
    a22_nodes = by_tests(
        "S04.A22",
        "",
        found,
        lambda node: l01("A22")(node) or node == W27_PIN,
    )
    a22 = {
        **a22_nodes,
        "description": text(
            "L01.A22 as amended (L01 spec §13.2, R-566): the 18 C1/W27 files no registered "
            "procedure rewrites hash as pinned; L01 is absent from W27's committed coverage "
            "(w27_absence_problems, with its two negative controls) and from the live "
            "SELECTABLE_BASES; pr_c1's identity unchanged; the W27 pin test passes unmodified"
        ),
    }
    a32 = by_tests(
        "T08.A32",
        "R-529 (L01 spec §12.4): every component record is synthetic or a vetted real record "
        "of VETTED_RECORD_FILES (M01's five, L01's nine) with identifiers, rights statements, "
        "provenance and its file's retrieval equality; no third-party data in the sdist or "
        "wheel; the envelope's statement",
        found,
        lambda node: node.startswith("tests/test_t08_w2_inventory.py::") and "A32" in cited(node),
    )
    matrix_ok = runs["matrix"].exit_code == 0 and "\n0 problem(s)" in "\n" + runs["matrix"].stdout
    envelope_nodes = by_tests(
        "S04.envelope",
        "",
        found,
        lambda node: node.startswith("tests/test_t08_w2_support_envelope.py::"),
    )
    envelope = check(
        "S04.envelope",
        "T08.A20–A23 at this commit with the providers axis as amended (T08 release spec §5.7 "
        "Amendment S04, R-568): tests/test_t08_w2_support_envelope.py passes and "
        "t08_support_matrix.py --check reports 0 problems",
        "pass" if matrix_ok and envelope_nodes["result"] == "pass" else "fail",
        {
            "cmd": runs["matrix"].cmd,
            "exit_code": runs["matrix"].exit_code,
            "zero_problems": matrix_ok,
            "nodes": envelope_nodes["value"],
        },
        "exit code 0, 0 problem(s), and every node passed",
    )
    battery_result, battery_value = verdict(found)
    del battery_value["selectors"]
    targeted = check(
        "S04.WOR-targeted",
        "The targeted battery (tests/test_l01_*.py, test_t08_w2_inventory.py, "
        "test_t08_w4_package_data.py, test_m01_*.py, test_adr_0008_transient_readiness.py, "
        "test_t08_w2_support_envelope.py and the W27 pin node) with OFS_L01_SOURCES_PYTHON set: "
        "every node passed",
        battery_result if runs["tests"].exit_code == 0 else "fail",
        {**battery_value, "exit_code": runs["tests"].exit_code},
        "every node passed, exit code 0",
    )
    entries = [
        wor1,
        wor2,
        a12,
        a01,
        a22,
        a32,
        envelope,
        targeted,
        by_tool("S04.ruff", "ruff check is clean", runs["ruff"], runs["ruff"].exit_code == 0),
        by_tool(
            "S04.format",
            "ruff format --check is clean",
            runs["format"],
            runs["format"].exit_code == 0,
        ),
        by_tool(
            "S04.mypy",
            "mypy (the project's configuration) is clean",
            runs["mypy"],
            runs["mypy"].exit_code == 0,
        ),
        check(
            "S04.gate",
            "scripts/gate.sh passes before merge",
            "unsupported",
            "not run by this generator; the full gate runs once before merge (CLAUDE.md)",
        ),
    ]

    manifest: dict[str, Any] = {
        "work_package": "S04",
        "commit": commit,
        "requirements": ["D08"],
        "status": status(entries),
        "inputs": {
            "case_id": "S04 (L01) registered states of benchmarks/l01/reference_values.yaml "
            "(V1L, V2L, P1; the A17–A20 guard states incl. A20_P_low; the M-1 states; the S-2 "
            "pair) and the nine records of benchmarks/l01/components.yaml; case_hash is "
            "reference_values.yaml's SHA-256",
            "case_hash": sha256_file(REFERENCE),
            "environment_lock_hash": sha256_file(LOCK),
        },
        "commands": [command(entry) for entry in runs.values()],
        "checks": entries,
        "artifacts": [
            {
                "path": shown(junit),
                "sha256": sha256_file(junit),
                "description": "JUnit report of the S04 test battery (ignored; kept by hash)",
            },
            {
                "path": shown(REFERENCE),
                "sha256": sha256_file(REFERENCE),
                "description": "50-digit reference, 46 claims",
            },
            {
                "path": shown(CROSSCHECK),
                "sha256": sha256_file(CROSSCHECK),
                "description": "retrieval and cross-check record, A12 at 2 % over nine",
            },
            {
                "path": shown(RECORDS),
                "sha256": sha256_file(RECORDS),
                "description": "the nine `pr-lib-v1` records",
            },
            {
                "path": shown(SPEC),
                "sha256": sha256_file(SPEC),
                "description": "the L01 specification (S04's), through Amendment 2 (§13)",
            },
        ],
        "limitations": limitations(entries),
        "review": {"numerical": "pending", "process_model": "pending"},
    }
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = [error.message for error in Draft202012Validator(schema).iter_errors(manifest)]
    if errors:
        raise SystemExit(f"the manifest does not validate: {errors}")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--commit", help="the measured commit (default: HEAD)")
    parser.add_argument("--out", type=Path, help="default: evidence/S04/<commit>/manifest.json")
    parser.add_argument("--sources-python", type=Path, default=SOURCES_PYTHON)
    arguments = parser.parse_args()
    commit = (
        arguments.commit
        or subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    )
    manifest = build(commit, arguments.sources_python)
    out = arguments.out or ROOT / "evidence" / "S04" / commit / "manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    passed = sum(1 for entry in manifest["checks"] if entry["result"] == "pass")
    digest = hashlib.sha256(out.read_bytes()).hexdigest()[:12]
    print(
        f"{shown(out)}: status {manifest['status']}, "
        f"{passed}/{len(manifest['checks'])} checks pass (sha256 {digest}…)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
