"""V03 WO-1…WO-4 (manifest id S13a): run the assertions testable before K3 and write the manifest.

Spec P3 (`docs/derivations/V03-release-spec.md` §4) merges WO-1…WO-4 into `main` before the cut K3,
while S13's manifest is written only at C (WO-6). `CLAUDE.md` merges into `main` only with a
`tested` manifest, so this sub-manifest, S13a, carries the assertions WO-1…WO-4 own (§10's table:
A01–A08, A10–A16, A18, A28–A31), as E01b's S12b did (`docs/V03_DECISIONS.md`). S13 at C may cite it.

Each assertion's gate column is read from §7. An assertion whose gate includes D (the default
gate) is judged here: its test nodes run in their own pytest process and it passes only if that
process exits 0 with at least one test passed and none skipped. An assertion whose gate is R only
is judged on the records at C: its check is `unsupported`, which is not a pass, and says so.

    PYTHONPATH=$PWD/src:$PWD python scripts/s13a_evidence_manifest.py --gate-log LOG

`--gate-log` is the full gate's log at this commit (`scripts/gate.sh`, run once before the merge);
the generator reads its summary line and does not re-run it. The manifest goes to
`evidence/S13a/<commit>/manifest.json`, the outputs under `artifacts/` (ignored). Status `tested`
iff every D check passes; `review` stays `pending`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "derivations" / "V03-release-spec.md"
REVIEW = ROOT / "docs" / "reviews" / "V03-review.md"
GATE_TESTS = "tests/test_v03_v0_3_gate.py"
ROLES_TESTS = "tests/test_v03_semantic_roles.py"
SHIP_TESTS = "tests/test_v03_wilson_ship.py"

#: (assertion, WO, pytest arguments). The arguments select the assertion's nodes by file and `-k`.
ITEMS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("A01", "WO-1", (GATE_TESTS, "-k", "a01_ or otherwise_passing_fixture")),
    ("A02", "WO-1", (GATE_TESTS, "-k", "a02_")),
    (
        "A03",
        "WO-1",
        (
            GATE_TESTS,
            "tests/test_m07a_v0_2_gate.py",
            "tests/test_m07_v0_2_gate.py",
            "-k",
            "a03_ or test_m07a_v0_2_gate or test_m07_v0_2_gate",
        ),
    ),
    ("A04", "WO-1", (GATE_TESTS, "-k", "a04_")),
    ("A05", "WO-1", (GATE_TESTS, "-k", "a05_")),
    ("A06", "WO-1", (GATE_TESTS, "-k", "a06_")),
    ("A07", "WO-1", (GATE_TESTS, "-k", "a07_")),
    ("A08", "WO-1", (GATE_TESTS, "-k", "a08_")),
    ("A10", "WO-3", ("tests/test_e01_a48_tripwire.py",)),
    ("A11", "WO-3", ("tests/test_m07_mr12_extras_v02.py",)),
    (
        "A12",
        "WO-2",
        (
            SHIP_TESTS,
            "tests/test_s11_wilson_v2.py::test_a75_v1_is_not_edited",
            "-k",
            "a12_ or test_a75_v1_is_not_edited",
        ),
    ),
    ("A13", "WO-2", (SHIP_TESTS, "-k", "a13_")),
    ("A14", "WO-2", (SHIP_TESTS, "-k", "a14_")),
    ("A15", "WO-3", ("tests/test_v03_rc_coolprop.py",)),
    ("A16", "WO-1", (GATE_TESTS, "-k", "a16_")),
    ("A18", "WO-4", ()),
    ("A28", "WO-3", (ROLES_TESTS, "-k", "a28_")),
    ("A29", "WO-3", (ROLES_TESTS, "-k", "a29_ or nine_cases_and_its_floor")),
    ("A30", "WO-3", (ROLES_TESTS, "-k", "a30_")),
    ("A31", "WO-3", (ROLES_TESTS, "-k", "a31_")),
)

#: The design-lane review pass over WO-1…WO-4 and the commits that closed its findings.
REVIEW_FIXES = {
    "F-V1": "1a2388cf",
    "F-V2": "030226c4",
    "F-V3, F-V4": "b0d71e2f",
}

LIMITATIONS = (
    "Package id: this manifest is filed as S13a, a sub-manifest of V03's S13 for WO-1…WO-4 "
    "(orchestrator's decision, docs/V03_DECISIONS.md; E01b's S12b is the precedent): spec P3 "
    "merges WO-1…WO-4 into main before K3, and S13's manifest is written only at C (WO-6). Check "
    "ids are S13a.*; each description names its assertion V03.A#.",
    "requirements is empty: V03's claims (X31 and the carried rows) are judged by the verdict "
    "document at C (spec §3, A26), and the frozen schema admits only D/A requirement ids.",
    "V03.A18 (CHANGELOG.md `## v0.3.0` holds §8's 17 phrases) has gate R: it is judged at C, in "
    "S13. S13a.A18 is unsupported, which is not a pass; it records the draft's count at this "
    "commit.",
    "V03.A08's gate is D and R: S13a.A08 is its D part; the RC record's step 18 output at C is "
    "S13's.",
    "The assertions WO-1…WO-4 do not own, or that exist only at K3 or C (A09, A17, A19–A27), are "
    "not in this manifest: S13 at C carries them. A25 (WO-4's ADR flips) is judged at C.",
    "The full gate (scripts/gate.sh) was run once at this commit before the merge and is "
    "recorded from its log (S13a.gate), not re-run by this generator. CI on x86-64 and aarch64 "
    "is checked on the push before the merge into main, not recorded here.",
    "Review: the design lane's single reviewer pass over wp/V03 (docs/reviews/V03-review.md) "
    "found one must-fix (F-V1), one should-fix (F-V2) and two notes (F-V3, F-V4); S13a.review "
    "lists the commits that closed them. The manifest's review field stays pending.",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def gates() -> dict[str, str]:
    """§7's gate column, by assertion id."""
    text = SPEC.read_text(encoding="utf-8")
    section = text[text.index("## 7. Assertions") : text.index("## 8. ")]
    rows = re.findall(r"^\| V03\.(A\d\d) \|.*\| ([^|]+) \|$", section, flags=re.MULTILINE)
    return {assertion: gate.strip() for assertion, gate in rows}


def summary(output: str) -> tuple[str, dict[str, int]]:
    """Pytest's last summary line and its counts."""
    lines = [line for line in output.strip().splitlines() if re.search(r"\d+ \w+ in ", line)]
    last = lines[-1].strip("= ") if lines else ""
    counts = {kind: int(n) for n, kind in re.findall(r"(\d+) (\w+)", last.split(" in ")[0])}
    return last, counts


def changelog_draft() -> dict[str, Any]:
    """A18 measured on the draft: §8's phrases present in `## v0.3.0` (gate R; judged at C)."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import changelog_section

    text = SPEC.read_text(encoding="utf-8")
    heading = '## 8. Release notes: `CHANGELOG.md` `## v0.3.0`, "What it is not"'
    section = text[text.index(heading) : text.index("\n## 9.")]
    phrases = re.findall(r"^\d+\. `([^`]+)`$", section, flags=re.MULTILINE)
    body = changelog_section.section((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), "v0.3.0")
    present = [phrase for phrase in phrases if phrase in body]
    return {"phrases": len(phrases), "present_in_draft": len(present)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gate-log", type=Path, required=True, help="scripts/gate.sh's log")
    arguments = parser.parse_args(argv)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    out = ROOT / "evidence" / "S13a" / commit
    artifacts_dir = out / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    python = sys.executable
    environment = {**os.environ, "PYTHONPATH": f"{ROOT / 'src'}{os.pathsep}{ROOT}"}
    gate_of = gates()
    commands: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []

    def artifact(path: Path, description: str) -> None:
        artifacts.append(
            {
                "path": str(path.relative_to(ROOT)),
                "sha256": sha256(path.read_bytes()),
                "description": description,
            }
        )

    for assertion, order, selection in ITEMS:
        check_id = f"S13a.{assertion}"
        gate = gate_of[assertion]
        if "D" not in [part.strip() for part in gate.split(",")]:
            checks.append(
                {
                    "id": check_id,
                    "description": f"V03.{assertion} ({order}; §7 gate {gate}): judged at C (S13)",
                    "result": "unsupported",
                    "value": {"planned": "at C (records)", "draft_at_commit": changelog_draft()},
                }
            )
            continue
        junit = artifacts_dir / f"{check_id}.junit.xml"
        command = [
            python,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            f"--junitxml={junit}",
            *selection,
        ]
        completed = subprocess.run(
            command, cwd=ROOT, env=environment, capture_output=True, check=False
        )
        log = artifacts_dir / f"{check_id}.log"
        log.write_bytes(completed.stdout + completed.stderr)
        last, counts = summary(completed.stdout.decode(errors="replace"))
        passed = (
            completed.returncode == 0
            and counts.get("passed", 0) > 0
            and not counts.get("skipped")
            and not counts.get("failed")
            and not counts.get("error", counts.get("errors"))
        )
        commands.append(
            {
                "cmd": " ".join(command).replace(str(ROOT) + "/", ""),
                "cwd": ".",
                "exit_code": completed.returncode,
                "stdout_sha256": sha256(completed.stdout),
            }
        )
        checks.append(
            {
                "id": check_id,
                "description": f"V03.{assertion} ({order}; §7 gate {gate}): its test nodes pass",
                "result": "pass" if passed else "fail",
                "value": last,
            }
        )
        artifact(log, f"output of {check_id}")
        if junit.is_file():
            artifact(junit, f"JUnit report of {check_id}")

    # V03.A12 (c): the S10/S11 identity tests are unchanged (S11's gate G1, three families).
    # Its shards run in parallel, so they must not share one `--basetemp` from `PYTEST_ADDOPTS`.
    command = [python, "scripts/s11_identity.py"]
    sharded = {key: value for key, value in environment.items() if key != "PYTEST_ADDOPTS"}
    completed = subprocess.run(command, cwd=ROOT, env=sharded, capture_output=True, check=False)
    log = artifacts_dir / "S13a.A12c.log"
    log.write_bytes(completed.stdout + completed.stderr)
    last = (completed.stdout.decode(errors="replace").strip().splitlines() or [""])[-1]
    commands.append(
        {
            "cmd": " ".join(command),
            "cwd": ".",
            "exit_code": completed.returncode,
            "stdout_sha256": sha256(completed.stdout),
        }
    )
    checks.append(
        {
            "id": "S13a.A12c",
            "description": "V03.A12 (c) (WO-2; §7 gate D): the S10/S11 identity is unchanged "
            "(scripts/s11_identity.py, S11 gate G1)",
            "result": "pass"
            if completed.returncode == 0 and last.startswith("S11-IDENTITY PASS")
            else "fail",
            "value": last[:300],
        }
    )
    artifact(log, "output of S13a.A12c")

    log_bytes = arguments.gate_log.read_bytes()
    log_text = log_bytes.decode(errors="replace")
    gate_last, gate_counts = summary(log_text)
    gate_ok = (
        "=== check.sh: PASSED ===" in log_text
        and gate_counts.get("passed", 0) > 0
        and not gate_counts.get("failed")
    )
    commands.append(
        {
            "cmd": f"scripts/gate.sh > {arguments.gate_log} 2>&1",
            "cwd": ".",
            "exit_code": 0 if gate_ok else 1,
            "stdout_sha256": sha256(log_bytes),
        }
    )
    checks.append(
        {
            "id": "S13a.gate",
            "description": "the full gate (scripts/gate.sh) at this commit, read from its log",
            "result": "pass" if gate_ok else "fail",
            "value": f"{gate_last}; {'=== check.sh: PASSED ===' if gate_ok else 'not passed'}",
        }
    )

    fixes: dict[str, str] = {}
    review_ok = REVIEW.is_file()
    for finding, short in REVIEW_FIXES.items():
        full = subprocess.run(
            ["git", "rev-parse", "--verify", f"{short}^{{commit}}"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        ancestor = (
            bool(full)
            and subprocess.run(
                ["git", "merge-base", "--is-ancestor", full, commit], cwd=ROOT, check=False
            ).returncode
            == 0
        )
        review_ok = review_ok and ancestor
        fixes[finding] = full
    checks.append(
        {
            "id": "S13a.review",
            "description": "the design-lane reviewer pass over WO-1…WO-4 is recorded, and the "
            "commits that closed its findings are in this commit's history",
            "result": "pass" if review_ok else "fail",
            "value": {
                "record": str(REVIEW.relative_to(ROOT)),
                "record_sha256": sha256(REVIEW.read_bytes()) if REVIEW.is_file() else None,
                "fix_commits": fixes,
            },
        }
    )

    judged = [check for check in checks if check["result"] != "unsupported"]
    passed = all(check["result"] == "pass" for check in judged)
    manifest = {
        "work_package": "S13a",
        "commit": commit,
        "requirements": [],
        "status": "tested" if passed else "implemented",
        "inputs": {
            "case_id": "V03 WO-1…WO-4 (manifest id S13a): docs/derivations/V03-release-spec.md §7 "
            "(V03.A01–A08, A10–A16, A18, A28–A31; §10's work-order table) and the reviewer pass "
            "docs/reviews/V03-review.md",
            "case_hash": sha256(SPEC.read_bytes()),
            "environment_lock_hash": sha256((ROOT / "requirements.lock").read_bytes()),
        },
        "commands": commands,
        "checks": checks,
        "artifacts": artifacts,
        "limitations": list(LIMITATIONS),
        "review": {"numerical": "pending", "process_model": "pending"},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(
        f"S13a {'PASS' if passed else 'FAIL'} {commit} "
        + " ".join(f"{c['id'].removeprefix('S13a.')}={c['result']}" for c in checks)
    )
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
