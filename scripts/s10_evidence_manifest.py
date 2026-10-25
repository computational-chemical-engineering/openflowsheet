"""Generate `evidence/S10/<commit>/manifest.json` by running, not by transcribing. S10 (WO-S10-7).

Spec `docs/derivations/S10-spec.md` §7.5 (amended by §16 A3-7 and §17 A4-2 item 4) is the check
list, and §17 A4-4 rules how S10 closes. Everything recorded is produced here, at the checked-out
commit (the script refuses to run when `HEAD` is not `--commit` or when a tracked source, test,
script, schema, derivation or S10 benchmark file differs from it; S01's rule):

1. **The S10 tests** (`tests/test_s10_*.py`, one `pytest --junitxml` run). A test cites the
   assertions its function name carries (`test_a33_…` cites A33). `S10.Axx` passes only if at
   least one node cites it and every node citing it passed. The verification assertions are
   A01–A08, A10–A28, A30–A34, A40–A45 and A54–A58 (A09 is reserved). `S10.tests` records the
   count; it passes only if every test passed and none was skipped (§19 A6-10).
2. **The generators' `--check`**: `s10_reference.py` (113 claims, A25), `s10_reference.py --real`
   (160 claims), `s10_records.py` (25 claims, A31).
3. **The comparisons' and the validation report's `--check`**: both `inputs.json` and both
   `comparison.json` recompute identically; `docs/s10-validation-report.md` is the script's output.
4. **`ruff check`, `ruff format --check`** on S10's files.
5. **The reference record**: each tool's per-state status, the provenance hashes, the hash the
   qualification record cites for its `inputs.json` (rebuilt from HEAD by
   `records-lineage.json`, spec §17 A4-3), and the `verdict` agent's document.

**Validation is not verification** (spec §9.6, §17 A4-4). A50–A53 are not in `status`. The
validation block §19 A6-9 gives is recorded verbatim as the value of the check `S10.validation`
(`not_applicable`: the frozen manifest schema has no top-level field for it, B-81), beside the
outcomes of the tests that check each verdict follows from the raw points (B-74). The block is
refused unless `benchmarks/s10/validation/report.json` carries the verdicts and the values it
states.

`scripts/gate.sh` and CI on both architectures are not run here (they run once before merge):
their checks are `unsupported`. `status` is computed, never written: `tested` iff every
verification assertion, the test count and every tool check pass; otherwise `implemented`. Both
review fields stay `pending`; `reviewed` is the `reviewer`'s. The limitations are §0's items, the
"does not establish" lists of A2-6, A3-9, A4-5, A5-7 and A6-13, then what this run found.

Usage:
    PYTHONPATH=src .venv/bin/python scripts/s10_evidence_manifest.py [--commit SHA] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parent))
from s01_evidence_manifest import (  # noqa: E402  (S01's generic helpers, unchanged)
    CLEAN_PATHS,
    LOCK,
    ROOT,
    SCHEMA,
    Node,
    check,
    command,
    nodes,
    run,
    sha256_file,
    shown,
    text,
)
from s02_evidence_manifest import _verdict, bullets, cited  # noqa: E402

SPEC = ROOT / "docs" / "derivations" / "S10-spec.md"
BENCH = ROOT / "benchmarks" / "s10"
RECORDS = BENCH / "records.yaml"
LINEAGE = BENCH / "records-lineage.json"
REAL = BENCH / "reference_values_real.yaml"
REPORT = BENCH / "validation" / "report.json"
VERDICTS = ROOT / "docs" / "reviews" / "S10-reference-verdicts.md"
VALIDATION_VERDICTS = (
    ROOT / "docs" / "reviews" / "S10-validation-verdicts.md",
    ROOT / "docs" / "reviews" / "S10-validation-verdict-val2.md",
)
TRANSCRIPTION = BENCH / "vle" / "kurihara1995_binaries.csv"
DERIVATIONS = ROOT / "docs" / "derivations" / "scripts"
GENERATORS = (
    DERIVATIONS / "s10_reference.py",
    DERIVATIONS / "s10_records.py",
    DERIVATIONS / "s10_saturation_points.py",
)
#: The source files S10 added or changed (WO-S10-1, WO-S10-2).
SOURCES = (
    "src/openflowsheet/thermo/wilson_ig.py",
    "src/openflowsheet/thermo/stability.py",
)
SCRIPTS = (
    "scripts/s10_idaes_comparison.py",
    "scripts/s10_dwsim_comparison.py",
    "scripts/s10_validation.py",
    "scripts/s10_evidence_manifest.py",
)
TOOLS = ("idaes", "dwsim")
#: §7.5's verification ids (A09 is reserved; A50–A53 are validation, §17 A4-4; A54–A58, §18).
VERIFICATION = (
    *(f"A{index:02d}" for index in range(1, 9)),
    *(f"A{index:02d}" for index in range(10, 29)),
    *(f"A{index:02d}" for index in range(30, 35)),
    *(f"A{index:02d}" for index in range(40, 46)),
    *(f"A{index:02d}" for index in range(54, 59)),
)
VALIDATION_IDS = ("A50", "A51", "A52", "A53")
#: A tool check's expected `--check` line, when it carries a claim count.
CLAIMS = {
    "S10.generator": r"^113 claims hold; reference_values\.yaml matches$",
    "S10.generator_real": r"^160 claims hold; reference_values_real\.yaml matches$",
    "S10.records": r"^25 claims hold; records\.yaml and fit-report\.json match$",
}
#: VAL-2's verdicts, pinned from the `verdict` agent's document (spec §19 A6-4, A6-10 step 3).
VAL2_VERDICTS = {
    "VAL-2": "within band",
    "methanol+water": "within band",
    "ethanol+water": "within band",
}
#: The values the block below states, as A6-9 formats them from `report.json`'s "VAL-2".
VAL2_VALUES = {
    "methanol+water": ("1.09", "0.0048"),
    "ethanol+water": ("0.29", "0.0041"),
}
#: Spec §19 A6-9, verbatim with its slots filled from `report.json`.
VALIDATION = {
    "kind": "empirical validation (S10 spec §9.6), reported apart from numerical verification",
    "S10.A50 (VAL-1)": "within band",
    "S10.A51 (VAL-2)": "within band: methanol-water within band (AAD(dP/P) 1.09 %, AAD(y1) "
    "0.0048); ethanol-water within band (AAD(dP/P) 0.29 %, AAD(y1) 0.0041); 159 points at "
    "323.15-333.15 K, judged per binary (S10 spec §19 A6-4)",
    "S10.A52 (VAL-3)": "not validated within band: CH3OH latent heat +5.72 % against 5 % "
    "(ideal-gas vapour); the other five cells within band",
    "S10.A53": "met for the fit-quality report; VAL-2's data entered no fit",
    "not_established": "constant-Lambda extrapolation outside 323.15-333.15 K (VAL-2) and the "
    "101.3 kPa isobar (VAL-1), and for methanol-ethanol off the isobar; the records' P domain "
    "below 30 kPa (not extended by VAL-2); individual methanol-ethanol Lambda (S10 spec §17 "
    "A4-2)",
}
REQUIRED_CHECKS = (
    "S10.tests",
    *CLAIMS,
    "S10.idaes_comparison",
    "S10.dwsim_comparison",
    "S10.validation_report",
    "S10.ruff",
    "S10.format",
)


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def refuse_unless_measuring(commit: str) -> None:
    head = git("rev-parse", "HEAD")
    if head != commit:
        raise SystemExit(f"HEAD is {head}, not {commit}: check the commit out to measure it")
    dirty = git(
        "status", "--porcelain", "--untracked-files=no", "--", *CLEAN_PATHS, "benchmarks/s10"
    )
    if dirty:
        raise SystemExit(f"tracked files differ from {commit}:\n{dirty}")


# -- the specification ---------------------------------------------------------------------------


def section(document: str, heading: str) -> str:
    """The body under the heading that starts with `heading` (`## 0.`, `### A4-2.`); S03's."""
    level = heading.split(" ", 1)[0]
    match = re.search(
        rf"^{re.escape(heading)} .*?$(.*?)(?=^#{{2,{len(level)}}} |\Z)", document, re.M | re.S
    )
    if match is None:
        raise SystemExit(f"{SPEC.name} has no {heading}")
    return match.group(1)


def table(body: str) -> dict[str, tuple[str, str, str]]:
    """A four-column assertion table's `S10.Axx` rows: id → (assertion, expected, tolerance)."""
    rows: dict[str, tuple[str, str, str]] = {}
    for line in body.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split(" | ")]
        if len(cells) == 4 and re.fullmatch(r"S10\.A\d{2}", cells[0]):
            rows[cells[0][4:]] = (cells[1], cells[2], cells[3])
    return rows


def assertion_table(document: str) -> dict[str, tuple[str, str, str]]:
    rows = table(section(document, "### 7.5"))
    if rows.pop("A09", None) != ("(Reserved.)", "—", "—"):
        raise SystemExit("§7.5's A09 is not the reserved row")
    if tuple(sorted(rows)) != VERIFICATION:
        raise SystemExit(f"§7.5's ids are {sorted(rows)}, not {list(VERIFICATION)}")
    validation = table(section(document, "### A4-2."))
    if tuple(validation) != VALIDATION_IDS:
        raise SystemExit(f"§17 A4-2's rows are {list(validation)}, not {list(VALIDATION_IDS)}")
    return {**rows, **validation}


def amendments(document: str) -> dict[str, str]:
    """§16 A3-7's amended statements (§7.5's rows stand amended by them)."""
    return {k: v[0] for k, v in table(section(document, "### A3-7.")).items()}


def numbered(body: str) -> list[str]:
    """`1. ` items verbatim, continuation lines joined by one space."""
    items: list[str] = []
    for line in body.splitlines():
        if re.match(r"^\d+\. ", line):
            items.append(line.split(" ", 1)[1].strip())
        elif line.startswith("   ") and items and line.strip():
            items[-1] += " " + line.strip()
    return items


def limitations_of_the_spec(document: str) -> list[str]:
    scope = section(document, "## 0.").split("**What this document does NOT establish.**", 1)[1]
    items = [f"§0: {item}" for item in numbered(scope)]
    for heading, name in (
        ("### A2-6.", "§15 A2-6 (as written at Amendment 2)"),
        ("### A3-9.", "§16 A3-9 (as written at Amendment 3)"),
        ("### A4-5.", "§17 A4-5"),
        ("### A5-7.", "§18 A5-7"),
        ("### A6-13.", "§19 A6-13"),
    ):
        found = bullets(section(document, heading))
        if not found:
            raise SystemExit(f"{heading} lists no item")
        items += [f"{name}: {item}" for item in found]
    if len(items) < 8:
        raise SystemExit("§0 lists fewer than eight items")
    return [text(item) for item in items]


# -- the tests -----------------------------------------------------------------------------------


def assertion_checks(
    rows: Mapping[str, tuple[str, str, str]], amended: Mapping[str, str], tests: Sequence[Node]
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for identifier in VERIFICATION:
        result, value = _verdict([item for item in tests if identifier in cited(item.node)])
        assertion, expected, tolerance = rows[identifier]
        if identifier in amended:
            assertion = f"{assertion} [amended by §16 A3-7: {amended[identifier]}]"
        entries.append(
            check(f"S10.{identifier}", assertion, result, value, text(expected), text(tolerance))
        )
    return entries


def test_count(tests: Sequence[Node]) -> dict[str, Any]:
    outcomes = Counter(item.outcome for item in tests)
    skipped = [item for item in tests if item.outcome == "skipped"]
    ok = set(outcomes) == {"passed"} and outcomes["passed"] > 0
    summary = f"{outcomes['passed']} passed, {outcomes['skipped']} skipped"
    return check(
        "S10.tests",
        "§19 A6-10: every S10 test passed and none was skipped",
        "pass" if ok else "fail",
        {
            "summary": summary,
            "outcomes": dict(sorted(outcomes.items())),
            "skipped": [item.node for item in skipped],
        },
        "every test passed; no failure, error or skip",
    )


def validation_check(rows: Mapping[str, tuple[str, str, str]], tests: Sequence[Node]) -> Any:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    states = {
        "VAL-1": "within band",
        "VAL-3": "not validated within band",
    }
    for name, verdict in states.items():
        if report[name]["verdict"] != verdict:
            found = report[name]["verdict"]
            raise SystemExit(f"report.json's {name} is {found!r}, not {verdict!r}")
    val2 = report["VAL-2"]
    found_val2 = {"VAL-2": val2["verdict"]}
    found_val2.update((binary["system"], binary["verdict"]) for binary in val2["binaries"])
    if found_val2 != VAL2_VERDICTS:
        raise SystemExit(f"report.json's VAL-2 verdicts are {found_val2}, not {VAL2_VERDICTS}")
    values = {
        binary["system"]: (
            f"{100 * binary['aad_dP_over_P']:.2f}",
            f"{binary['aad_y1']:.4f}",
        )
        for binary in val2["binaries"]
    }
    if values != VAL2_VALUES:
        raise SystemExit(f"report.json's VAL-2 values are {values}, not {VAL2_VALUES}")
    by_id = {}
    for identifier in VALIDATION_IDS:
        citing = [item for item in tests if identifier in cited(item.node)]
        by_id[f"S10.{identifier}"] = {
            "statement": text(rows[identifier][0]),
            "band": text(rows[identifier][2]),
            "nodes": {item.node: item.outcome for item in citing},
        }
    return check(
        "S10.validation",
        VALIDATION["kind"] + "; not a verification check and not counted in status (§17 A4-4)",
        "not_applicable",
        {
            "validation": VALIDATION,
            "tests": {
                "what_they_check": "the report is the script's output, the bands are §9.6's and "
                "each verdict follows from the raw points; not that a band is met (B-74)",
                "per_assertion": by_id,
            },
            "report": {"path": shown(REPORT), "sha256": sha256_file(REPORT)},
            "verdict_documents": [
                {"path": shown(path), "sha256": sha256_file(path)} for path in VALIDATION_VERDICTS
            ],
        },
    )


# -- the reference record ------------------------------------------------------------------------


def reference_record() -> dict[str, Any]:
    lineage = json.loads(LINEAGE.read_text(encoding="utf-8"))
    out: dict[str, Any] = {
        "records_sha256": sha256_file(RECORDS),
        "records_lineage": {
            "path": shown(LINEAGE),
            "sha256": sha256_file(LINEAGE),
            "steps": [
                {k: step[k] for k in ("from_sha256", "to_sha256", "key", "authority", "commit")}
                for step in lineage["steps"]
            ],
        },
        "verdict_document": {
            "path": shown(VERDICTS),
            "present": VERDICTS.is_file(),
            "sha256": sha256_file(VERDICTS) if VERDICTS.is_file() else None,
        },
        "tools": {},
    }
    for tool in TOOLS:
        comparison = json.loads((BENCH / tool / "comparison.json").read_text(encoding="utf-8"))
        qualification = json.loads((BENCH / tool / "qualification.json").read_text("utf-8"))
        cited_inputs = (
            qualification["inputs"]["sha256"] if tool == "idaes" else qualification["inputs_sha256"]
        )
        states = comparison["comparison"]["states"]
        out["tools"][tool] = {
            "environment_versions": comparison["environment"]["versions"],
            "fingerprint_matches": comparison["environment"]["fingerprint_matches"],
            "provenance": comparison["provenance"],
            "qualification_cites_inputs_sha256": cited_inputs,
            "inputs_sha256_at_head": sha256_file(BENCH / tool / "inputs.json"),
            "cited_hash_rebuilt_by": "tests/test_s10_records.py::"
            "test_records_lineage_reconstructs_the_cited_hashes (spec §17 A4-3)",
            "statuses": dict(sorted(Counter(s["status"] for s in states.values()).items())),
            "states": {
                sid: {
                    k: s[k]
                    for k in ("status", "reason", "max_ratio", "all_within", "attempt")
                    if k in s
                }
                for sid, s in sorted(states.items(), key=lambda kv: int(kv[0][1:]))
            },
        }
    return out


# -- the manifest --------------------------------------------------------------------------------


def status(entries: Sequence[Mapping[str, Any]]) -> str:
    required = {f"S10.{identifier}" for identifier in VERIFICATION} | set(REQUIRED_CHECKS)
    results = {entry["id"]: entry["result"] for entry in entries}
    missing = required - set(results)
    if missing:
        raise SystemExit(f"checks missing: {sorted(missing)}")
    return "tested" if all(results[name] == "pass" for name in required) else "implemented"


def found_limitations(entries: Sequence[Mapping[str, Any]], record: Mapping[str, Any]) -> list[str]:
    lost = [
        f"{tool} {sid}: {s['status']}" + (f" ({s['reason']})" if "reason" in s else "")
        for tool, data in record["tools"].items()
        for sid, s in data["states"].items()
        if s["status"] != "compared"
    ]
    items = [
        "Validation is reported apart from verification (spec §9.6, §17 A4-4, §19) in the check "
        "S10.validation: VAL-1 within band; VAL-2 within band (methanol-water within band, "
        "ethanol-water within band; judged per binary); VAL-3 not validated within band for the "
        "CH3OH latent heat (+5.72 % against 5 %). `tested` attests numerical verification only.",
        "Every IDAES and DWSIM state not compared, with its reason: " + "; ".join(lost),
        "requirements lists D08 and D19; §8's comparisons are D19's matched-model evidence for "
        "the property method (S10 spec §18 A5-3)",
        "Rights (docs/s10-rights-check.md): RC-05 and RC-06 (the 1993 paper's Tables II and V) "
        "and RC-08 (atomic weights) are unresolved; no S10 file is in a PACKAGED path (A28) and "
        "`wilson-ig-v1` is library-only (A27). Shipping is Frank's decision (Q-F3).",
        "The qualification records cite inputs.json hashes from before spec §17 A4-3 "
        "(IDAES 92aa171f..., DWSIM 28676a25...); records-lineage.json and its test rebuild both "
        "from HEAD, so the tool records are not re-run.",
        "scripts/gate.sh and CI on both architectures were not run by this generator (they run "
        "once before merge into main); S10.gate and S10.ci are unsupported here.",
        "Review: the design lane's final review (docs/reviews/S10-review-final.md, R-720, R-721) "
        "was applied by WO-S10-7 (S-1 to S-3); the human numerical and process-model review is "
        "pending, and this manifest claims neither `reviewed` nor `released`.",
    ]
    for entry in entries:
        if entry["result"] in ("pass", "not_applicable") or entry["id"] in ("S10.gate", "S10.ci"):
            continue
        value = entry.get("value")
        detail = (
            "; ".join(f"{item['node']} {item['outcome']}" for item in value["not_passed"])
            if isinstance(value, dict) and value.get("not_passed")
            else "see its value"
        )
        items.append(text(f"{entry['id']} is {entry['result']}: {detail}"))
    return items


def build(commit: str) -> dict[str, Any]:
    refuse_unless_measuring(commit)
    document_text = SPEC.read_text(encoding="utf-8")
    rows = assertion_table(document_text)
    amended = amendments(document_text)
    artifacts = ROOT / "evidence" / "S10" / commit / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    junit = artifacts / "s10-tests.junit.xml"
    python = sys.executable
    tools = Path(python).parent
    tests = sorted(shown(path) for path in (ROOT / "tests").glob("test_s10_*.py"))
    lint = [*SOURCES, *SCRIPTS, *tests, *(shown(path) for path in GENERATORS)]

    reference, records = shown(GENERATORS[0]), shown(GENERATORS[1])
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
            ],
            pythonpath=True,
        ),
        "S10.generator": run([python, reference, "--check"]),
        "S10.generator_real": run([python, reference, "--real", "--check"]),
        "S10.records": run([python, records, "--check"]),
        "S10.idaes_comparison": run(
            [python, "scripts/s10_idaes_comparison.py", "--check"], pythonpath=True
        ),
        "S10.dwsim_comparison": run(
            [python, "scripts/s10_dwsim_comparison.py", "--check"], pythonpath=True
        ),
        "S10.validation_report": run(
            [python, "scripts/s10_validation.py", "--check"], pythonpath=True
        ),
        "S10.ruff": run([str(tools / "ruff"), "check", *lint]),
        "S10.format": run([str(tools / "ruff"), "format", "--check", *lint]),
    }
    if not junit.is_file():
        raise SystemExit(f"pytest wrote no report (exit {runs['tests'].exit_code})")
    found = nodes(junit)

    entries = assertion_checks(rows, amended, found)
    entries.append(test_count(found))
    descriptions = {
        "S10.generator": "§7.4, A25: s10_reference.py --check re-derives the 113 claims and "
        "byte-compares reference_values.yaml",
        "S10.generator_real": "§9.7, §16: s10_reference.py --real --check re-derives the 160 "
        "claims and byte-compares reference_values_real.yaml",
        "S10.records": "§9.3-9.5, A31: s10_records.py --check re-fits and byte-compares "
        "records.yaml and fit-report.json (25 claims)",
        "S10.idaes_comparison": "§8.1: inputs.json and comparison.json recompute identically",
        "S10.dwsim_comparison": "§8.2: inputs.json and comparison.json recompute identically",
        "S10.validation_report": "§9.6: docs/s10-validation-report.md is the script's output",
        "S10.ruff": "ruff check is clean on S10's files",
        "S10.format": "ruff format --check is clean on S10's files",
    }
    for name, description in descriptions.items():
        ok = runs[name].exit_code == 0
        if name in CLAIMS:
            ok = ok and bool(re.search(CLAIMS[name], runs[name].stdout, re.M))
        entries.append(
            check(
                name,
                description,
                "pass" if ok else "fail",
                {"cmd": runs[name].cmd, "exit_code": runs[name].exit_code},
                "exit code 0" + (f", output matching {CLAIMS[name]}" if name in CLAIMS else ""),
            )
        )
    record = reference_record()
    entries.append(
        check(
            "S10.reference_record",
            "§8: each tool's environment, provenance hashes, per-state status (the verdicts are "
            "the verdict agent's document), and the qualification's cited inputs hash",
            "pass" if record["verdict_document"]["present"] else "fail",
            record,
        )
    )
    entries.append(validation_check(rows, found))
    entries.append(
        check(
            "S10.gate",
            "scripts/gate.sh passes before the merge",
            "unsupported",
            "not run by this generator; it runs once before merge",
        )
    )
    entries.append(
        check(
            "S10.ci",
            "CI is green on both architectures",
            "unsupported",
            "not measured by this generator; checked before merge",
        )
    )

    manifest: dict[str, Any] = {
        "work_package": "S10",
        "commit": commit,
        "requirements": ["D08", "D19"],
        "status": status(entries),
        "inputs": {
            "case_id": "S10 acceptance: docs/derivations/S10-spec.md §7.5 (A01–A45, amended by "
            "§14, §16 A3-7 and §17), against benchmarks/s10/reference_values.yaml, "
            "reference_values_real.yaml and the committed tool records; validation (A50–A53, "
            "§9.6) reported apart (§17 A4-4)",
            "case_hash": sha256_file(REAL),
            "environment_lock_hash": sha256_file(LOCK),
        },
        "commands": [command(entry) for entry in runs.values()],
        "checks": entries,
        "artifacts": [
            {
                "path": shown(junit),
                "sha256": sha256_file(junit),
                "description": "JUnit report of the S10 test run (ignored; kept by hash)",
            },
            *(
                {
                    "path": shown(path),
                    "sha256": sha256_file(path),
                    "description": description,
                }
                for path, description in (
                    (RECORDS, "the real records of wilson-ig-v1 (spec §9.3-9.5, §17 A4-3)"),
                    (LINEAGE, "the records' change steps (spec §17 A4-3)"),
                    (BENCH / "fit-report.json", "the fit claims and fit quality (not validation)"),
                    (BENCH / "reference_values.yaml", "the synthetic verification expectation"),
                    (REAL, "the real section: E-, F- and I-state expectations (spec §9.7, §16)"),
                    (BENCH / "idaes" / "qualification.json", "the IDAES tool record (§8.1)"),
                    (BENCH / "idaes" / "comparison.json", "the IDAES comparison (§8.1)"),
                    (BENCH / "dwsim" / "qualification.json", "the DWSIM tool record (§8.2)"),
                    (BENCH / "dwsim" / "comparison.json", "the DWSIM comparison (§8.2)"),
                    (REPORT, "the empirical validation numbers (§9.6)"),
                    (
                        TRANSCRIPTION,
                        "VAL-2's held-out data: Kurihara et al. 1995 Tables 2-3, double-entered "
                        "(spec §19 A6-1, A6-6)",
                    ),
                    (SPEC, "the S10 specification the checks are read from (§0, §7.5, §14-§19)"),
                )
            ),
        ],
        "limitations": [
            *limitations_of_the_spec(document_text),
            *found_limitations(entries, record),
        ],
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
    parser.add_argument("--out", type=Path, help="default: evidence/S10/<commit>/manifest.json")
    arguments = parser.parse_args()
    commit = arguments.commit or git("rev-parse", "HEAD")
    manifest = build(commit)
    out = arguments.out or ROOT / "evidence" / "S10" / commit / "manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    passed = sum(1 for entry in manifest["checks"] if entry["result"] == "pass")
    tests = next(e for e in manifest["checks"] if e["id"] == "S10.tests")["value"]["summary"]
    print(
        f"{shown(out)}: status {manifest['status']}, {passed}/{len(manifest['checks'])} checks "
        f"pass; tests {tests}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
