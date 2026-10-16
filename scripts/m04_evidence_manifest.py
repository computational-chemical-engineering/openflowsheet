"""Generate `evidence/M04/<C>/manifest.json` by measuring, not by transcribing. M04 WO-12.

Specification `docs/derivations/M04-spec.md` §12 (assertions A01–A35), §13 (WO-12), §15 (the W23
gate table), §18 (Amendment 1: A36–A42), §19 (Amendment 2: A43–A47, the W23 rows they join,
WO-11 on `b2-it1` and v3) and §20 (Amendment 3: A48–A50, the review's rulings R-360…R-369).
The manifest carries one check per assertion, read from the specification itself, so that an
assertion cannot be left out. Each check is decided from what
this script ran or read at `C`:

1. **The M04 tests**, run once here (`pytest --junitxml` over `tests/test_m04_*.py`, the default
   gate's selection). A test named `test_aNN…` belongs to M04.ANN; every other node is a
   supporting test (`M04.supporting`). A failed or skipped node fails its check; a default-gate
   assertion that no node names fails its check.
2. **The gate**: the stdout of `scripts/gate.sh` at `C`, required to be `GATE PASS <C short>`.
3. **WO-11's record** (`benchmarks/m04/wo11-b2-it1-v3/`, build decision E30), read, never re-run
   here: A31, A32 and A41 are decided from it, its manifest and evidence by their SHA-256; the
   real verdict is copied whatever it is (N6). A33 runs only on a PROMOTABLE A31 (§19 A2.13):
   on any other verdict it is `not_applicable`, never `pass`.
4. **The W23 table**: §15's rows parsed from the specification, plus the amendments' additions
   (§18, §19 A2.13, whose sentences must be present verbatim); one check per row, `pass` when
   every assertion of the row is `pass` or `not_applicable`.
5. **Register pointers**: the `docs/decision-register.md` entries decided by M04, and the ADRs
   they name.

`--harvest-from MANIFEST...` classifies the named manifests' limitations and non-pass checks in
`benchmarks/t08/support_envelope.yaml#harvest` (T08.A21), replacing every `evidence/M04/` entry,
and regenerates `docs/support-matrix.md`; the manifests are not touched. The classes are R-365's
(spec §20 A3.5): the real verdict E (envelope row L43), A33 and Q-A2.1 B, the rest P; the
`a9566a6` manifest's E33 limitation is S, closed by A49 (`HARVEST_BY_COMMIT`).

Status is `tested` when every check is `pass` (A33 may be `not_applicable`) and every command
exited 0; otherwise `implemented`. Per N6, M04 is `tested` whatever the real verdict. `reviewed`
is never set, and both review fields stay `pending`.

Usage:
    PYTHONPATH=src .venv/bin/python scripts/m04_evidence_manifest.py --commit C \\
        --gate-log GATE_STDOUT
    PYTHONPATH=src .venv/bin/python scripts/m04_evidence_manifest.py \\
        --harvest-from evidence/M04/a9566a6…/manifest.json evidence/M04/C/manifest.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ElementTree
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
ENVELOPE = ROOT / "benchmarks" / "t08" / "support_envelope.yaml"
SPEC = ROOT / "docs" / "derivations" / "M04-spec.md"
REGISTER = ROOT / "docs" / "decision-register.md"
M04 = ROOT / "benchmarks" / "m04"
WO11 = M04 / "wo11-b2-it1-v3"
REQUIREMENTS = ("A07", "D12")
#: The opt-in real assertions, decided from WO-11's record (none has a default-gate test).
RECORDED = ("A31", "A32", "A41")
#: Conditional on A31's verdict being PROMOTABLE (§12, §19 A2.13).
CONDITIONAL = ("A33",)
#: §18 and §19 A2.13's additions to §15's rows, with the sentence each is read from.
AMENDMENTS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("Frozen splits/transforms", ("A36", "A40"), 'A36 and A40 under "Frozen splits/transforms"'),
    ("Insufficient-data outcome", ("A39",), 'A39 under "Insufficient-data outcome"'),
    ("Default UQ", ("A37", "A38", "A42"), 'A38 and A42 under "Default UQ"'),
    ("Frozen splits/transforms", ("A43", "A47"), 'under "Frozen splits/transforms": A43 and A47'),
    ("Domain", ("A44",), 'under "Domain": A44'),
    ("Promotion and rollback", ("A45", "A46"), 'under "Promotion and rollback": A45 and A46'),
)
#: Amendment 3's assertions (§20), stated in prose rather than as `**M04.Ann**` lines: each id with
#: the statement read from the specification, which must be present (whitespace-normalised).
ADDED: tuple[tuple[str, str], ...] = (
    (
        "A48",
        "a change whose new revision binds a surrogate-backed instance with no checked replacement "
        "is rejected if that surrogate's re-derived verdict (`derived_verdict`) is not PROMOTABLE. "
        "This covers an added instance, a renamed one, and the first revision.",
    ),
    (
        "A49",
        "The fit runs in two subprocesses with `OPENBLAS_NUM_THREADS=OMP_NUM_THREADS` at 1 and at "
        "8, at a size where it fails without the fix. Its coefficients are bitwise equal.",
    ),
    (
        "A50",
        "A study whose training has N_ok < 36 records IE = [`training_unidentifiable`] (plus "
        "`plan_incomplete` if it applies) and NP = [].",
    ),
)
#: §15's numerical-verification condition: these `tested` in the default gate, A31–A32 recorded.
W23_CONDITION = tuple(f"A{n:02d}" for n in (*range(1, 31), 34, 35)) + ("A31", "A32")

LIMITATIONS: tuple[str, ...] = (
    "A33 (the real surrogate in `C1-LOOP-M02-v1`, rollback, one promoted commit) was not run: "
    "it is conditional on a PROMOTABLE A31. Q-A2.1 (does the surrogate-backed loop's reactor "
    "inlet lie in box v2?) stays open without A33's record.",
    "The real-reactor records (A31, A32, A41) are opt-in: the pinned reactor environment, Linux, "
    "one machine, read here and not re-run. A32's bitwise manifest equality holds on that "
    "platform at any thread setting: the fit runs under one BLAS thread (R-362, A49; build "
    "decision E36), and WO-11's study re-submitted from cache gave `d65bb022…` at one and at 48 "
    "threads; across platforms §18 A1.3's classes govern.",
    "The W23 rows here are numerical verification of §15's items; W23's verdict is the `verdict` "
    "lane's, not this manifest's. Self-generated outputs (the A19 fixtures, the WO-11 record) are "
    "regression evidence; the correctness assertions rest on the specification's closed forms and "
    "the generator's independent reference values (A34).",
)

ARTIFACTS: tuple[tuple[str, str], ...] = (
    ("docs/derivations/M04-spec.md", "The specification (assertions, W23 table, amendments 1-3)."),
    ("docs/reviews/M04-review.md", "The design-lane review (MF1, MF2, SF1, SF2; rulings)."),
    ("docs/design/M04-build-decisions.md", "The build log (E-entries with the measured values)."),
    ("benchmarks/m04/reference_values.json", "The generator's reference values (A34)."),
    ("benchmarks/m04/numerical_policy_surrogate.yaml", "M04's numerical-policy addendum."),
    ("benchmarks/m04/plan-b2-it1.json", "The registered plan WO-11 ran (box v2, iteration 1)."),
    ("benchmarks/m04/wo11-b2-it1-v3/record.json", "WO-11's record: A31, A32, A41, failures."),
    ("benchmarks/m04/wo11-b2-it1-v3/manifest.json", "WO-11's surrogate manifest (NOT_PROMOTABLE)."),
    ("benchmarks/m04/wo11-b2-it1-v3/evidence.json", "WO-11's model evidence naming the manifest."),
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


# ----------------------------------------------------------------------------- the specification


def catalogue() -> dict[str, str]:
    """Every M04 assertion, `Ann` → its first line (first statement only; a later amendment's
    rebinding is not a new assertion)."""
    text = SPEC.read_text(encoding="utf-8")
    found: dict[str, str] = {}
    pattern = r"^(?:- )?\*\*M04\.(A\d\d)\*?\*? *(?:\*\([^)]*\)\* )?(?:—|\*\* —)? *(.*)$"
    for match in re.finditer(pattern, text, re.MULTILINE):
        found.setdefault(match[1], match[2].replace("**", "").strip(" *—"))
    flat = " ".join(text.split())
    for aid, statement in ADDED:
        if " ".join(statement.split()) not in flat:
            raise SystemExit(f"{aid}'s statement is not in {SPEC.name}: {statement!r}")
        found.setdefault(aid, statement)
    numbers = sorted(int(a[1:]) for a in found)
    if numbers != list(range(1, numbers[-1] + 1)):
        raise SystemExit(f"assertion numbers are not contiguous: {numbers}")
    return {f"A{n:02d}": found[f"A{n:02d}"] for n in numbers}


def _expand(cell: str) -> list[str]:
    out: list[str] = []
    for part in (p.strip() for p in cell.split(",")):
        span = re.fullmatch(r"A(\d\d)–A(\d\d)", part)
        if span:
            out += [f"A{n:02d}" for n in range(int(span[1]), int(span[2]) + 1)]
        elif re.fullmatch(r"A\d\d", part):
            out.append(part)
        else:
            raise SystemExit(f"unreadable W23 assertion cell {cell!r}")
    return out


def w23_rows() -> dict[str, list[str]]:
    """§15's rows, then the amendments' additions (each sentence must be in the specification)."""
    text = SPEC.read_text(encoding="utf-8")
    section = text[text.index("## 15. The W23 gate table") : text.index("## 16.")]
    rows: dict[str, list[str]] = {}
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 3 and re.match(r"A\d\d", cells[2]):
            rows[cells[0].split(" (")[0]] = _expand(cells[2])
    for row, added, sentence in AMENDMENTS:
        if sentence not in text:
            raise SystemExit(f"the amendment sentence {sentence!r} is not in {SPEC.name}")
        if row not in rows:
            raise SystemExit(f"the amendment names a W23 row {row!r} that §15 lacks")
        rows[row] += [a for a in added if a not in rows[row]]
    return rows


def register() -> dict[str, Any]:
    """The register entries decided by M04 and the ADRs their normative text names."""
    text = REGISTER.read_text(encoding="utf-8")
    entries, adrs = [], set()
    for block in re.split(r"(?m)^## ", text):
        head = re.match(r"(R-\d+) — (.*)", block)
        decided = re.search(r"^\| Decided by \|([^\n]*)", block, re.MULTILINE)
        if head and decided and "M04" in decided[1]:
            entries.append({"id": head[1], "title": head[2].strip()})
            adrs.update(re.findall(r"(?:docs/adr/|ADR )(\d{4})\b", block))
    files = {a: sorted((ROOT / "docs" / "adr").glob(f"{a}-*.md")) for a in sorted(adrs)}
    return {
        "register": "docs/decision-register.md",
        "entries": entries,
        "adrs": [f.relative_to(ROOT).as_posix() for found in files.values() for f in found],
        "adrs_missing": [f"ADR {a}" for a, found in files.items() if not found],
    }


# ----------------------------------------------------------------------------- the tests


def _nodeid(classname: str, name: str) -> str:
    parts = classname.split(".")
    for index, part in enumerate(parts):
        if part.startswith("test_"):
            return "::".join(["/".join(parts[: index + 1]) + ".py", *parts[index + 1 :], name])
    return f"collection::{classname}::{name}"


def run_tests(artifacts: Path) -> tuple[dict[str, str], dict[str, Any]]:
    modules = sorted(path.relative_to(ROOT).as_posix() for path in ROOT.glob("tests/test_m04_*.py"))
    junit, stdout = artifacts / "m04-tests.junit.xml", artifacts / "m04-tests.stdout.txt"
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={junit}"]
        + modules,
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
        "cmd": "PYTHONPATH=src .venv/bin/python -m pytest -q -p no:cacheprovider "
        "--junitxml=ARTIFACTS/m04-tests.junit.xml tests/test_m04_*.py",
        "cwd": ".",
        "exit_code": completed.returncode,
        "stdout_sha256": _sha256(stdout),
    }
    return nodes, command


def by_assertion(nodes: Mapping[str, str]) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    named: dict[str, dict[str, str]] = {}
    supporting: dict[str, str] = {}
    for node, outcome in nodes.items():
        match = re.match(r"test_a(\d\d)[a-z]?_", node.partition("::")[2])
        if match:
            named.setdefault(f"A{match[1]}", {})[node] = outcome
        else:
            supporting[node] = outcome
    return named, supporting


def _tests_value(picked: Mapping[str, str]) -> tuple[dict[str, Any], bool]:
    counts = {o: sum(v == o for v in picked.values()) for o in ("passed", "failed", "skipped")}
    modules = sorted({n.partition("::")[0] for n in picked})
    value = {"modules": modules, **counts}
    return value, bool(picked) and counts["failed"] == counts["skipped"] == 0


def read_gate(log: Path, commit: str) -> dict[str, Any]:
    text = log.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.startswith("GATE ")]
    last = lines[-1] if lines else ""
    return {
        "passed": last.startswith(f"GATE PASS {commit[:7]}"),
        "summary": re.sub(r" \(log [^)]*\)$", "", last) or None,
        "stdout_sha256": _sha256(log),
    }


# ----------------------------------------------------------------------------- WO-11's record


def wo11() -> dict[str, tuple[dict[str, Any], str]]:
    """A31, A32, A41 and A33 decided from WO-11's committed record."""
    record = json.loads((WO11 / "record.json").read_text(encoding="utf-8"))
    manifest = json.loads((WO11 / "manifest.json").read_text(encoding="utf-8"))
    a31, a32, a41 = record["a31"], record["a32"], record["a41"]
    source = {
        "record": (WO11 / "record.json").relative_to(ROOT).as_posix(),
        "record_sha256": _sha256(WO11 / "record.json"),
        "code_commit": record["code_commit"],
        "judged": False,
    }
    manifest_sha, evidence_sha = _sha256(WO11 / "manifest.json"), _sha256(WO11 / "evidence.json")
    splits = {
        name: {"count": split["count"], "failed": len(split["failed"])}
        for name, split in a31["splits"].items()
    }
    promotion = a31["promotion"]
    a31_ok = (
        a31["executed_requests"] == a31["plan_requests"] == a31["plan_requests_distinct"]
        and a31["plan_requests_executed"] == a31["plan_requests"]
        and a31["executed_not_in_plan"] == 0
        and a31["manifest_schema_errors"] == a31["evidence_schema_errors"] == []
        and a31["evidence_names_manifest"] is True
        and a31["checker_failures"] == []
        and a31["derived_verdict_equal"] is True
        and manifest_sha == record["manifest_sha256"]
        and evidence_sha == record["evidence_sha256"]
        and manifest["promotion"] == promotion
    )
    a31_value = {
        **source,
        "plan_id": record["plan_id"],
        "parent": record["parent"],
        "manifest_sha256": manifest_sha,
        "evidence_sha256": evidence_sha,
        "plan_requests": a31["plan_requests"],
        "executed_requests": a31["executed_requests"],
        "executed_not_in_plan": a31["executed_not_in_plan"],
        "schemas_valid": a31["manifest_schema_errors"] == a31["evidence_schema_errors"] == [],
        "evidence_names_manifest": a31["evidence_names_manifest"],
        "checker_failures": a31["checker_failures"],
        "derived_verdict_equal": a31["derived_verdict_equal"],
        "verdict": promotion["verdict"],
        "not_promotable": promotion["not_promotable"],
        "insufficient": promotion["insufficient"],
        "certificate_refusals": len(record["failures"]),
        "failure_codes": sorted({f["code"] for f in record["failures"]}),
        "splits": splits,
        "n": a31["n"],
        "k": a31["k"],
        "m": a31["m"],
        "q_hat": a31["q_hat"],
        "h_min": a31["h_min"],
        "test_scores_le_1": a31["test_scores_le_1"],
        "fraction_within_width": a31["fraction_within_width"],
        "errors_max": {name: e["max"] for name, e in a31["errors"].items()},
        "gradient_max_e": a31["gradient_max_e"],
        "rho_g": a31["rho_g"],
        "parent_extrapolated": a31["domain"]["parent_extrapolated"],
        "inadmissible_predictions": a31["domain"]["inadmissible_predictions"],
        "note": "Recorded, not judged: the verdict is copied whatever it is (N6).",
    }
    a32_ok = (
        a32["cold_experiments"] == 0
        and a32["cache_hits"] == a31["plan_requests"]
        and a32["cache_misses"] == 0
        and a32["manifest_bitwise_equal"] is True
        and a32["manifest_sha256"] == record["manifest_sha256"]
        and a32["new_attempts"] == 0
    )
    a32_value = {
        **source,
        **a32,
        "note": "Bitwise at WO-11's thread environment (single-threaded BLAS); multi-threaded "
        "BLAS moves the fit's last bits (build decision E33).",
    }
    labels = [r["label"] for r in a41]
    a41_ok = labels == [f"test[{i}]" for i in range(8)] and all(
        r["repeat_bitwise_equal"] is True for r in a41
    )
    a41_value = {
        **source,
        "repeats": len(a41),
        "repeat_bitwise_equal": sum(r["repeat_bitwise_equal"] is True for r in a41),
    }
    promotable = promotion["verdict"] == "PROMOTABLE"
    a33_value = {
        "run": False,
        "condition": "A31 PROMOTABLE (§12 A33, §19 A2.13)",
        "a31_verdict": promotion["verdict"],
        "open_question": "Q-A2.1 stays open without A33's record (§19 A2.15).",
    }
    return {
        "A31": (a31_value, "pass" if a31_ok else "fail"),
        "A32": (a32_value, "pass" if a32_ok else "fail"),
        "A41": (a41_value, "pass" if a41_ok else "fail"),
        # A PROMOTABLE A31 needs A33's record, which this script does not have: `fail` then.
        "A33": (a33_value, "fail" if promotable else "not_applicable"),
    }


# ----------------------------------------------------------------------------- the checks


def checks(nodes: Mapping[str, str], gate: Mapping[str, Any]) -> list[dict[str, Any]]:
    assertions = catalogue()
    named, supporting = by_assertion(nodes)
    unknown = sorted(set(named) - set(assertions))
    if unknown:
        raise SystemExit(f"tests name assertions the specification lacks: {unknown}")
    recorded = wo11()
    out: list[dict[str, Any]] = []
    for aid, statement in assertions.items():
        if aid in recorded:
            value, result = recorded[aid]
            if aid in named:  # a default-gate test of an opt-in assertion counts too
                tests, ok = _tests_value(named[aid])
                value = {**value, "tests": tests}
                result = result if ok or result == "not_applicable" else "fail"
        else:
            tests, ok = _tests_value(named.get(aid, {}))
            value, result = {"tests": tests}, "pass" if ok else "fail"
        out.append(
            {
                "id": f"M04.{aid}",
                "description": f"M04 spec, {aid}: {statement[:160]}",
                "result": result,
                "value": value,
            }
        )
    tests, ok = _tests_value(supporting)
    out.append(
        {
            "id": "M04.supporting",
            "description": "The M04 tests that name no assertion (wiring, refusals, regressions).",
            "result": "pass" if ok else "fail",
            "value": {"tests": tests},
        }
    )
    out.append(
        {
            "id": "M04.gate",
            "description": "The default gate (`scripts/gate.sh`) at the evidence commit.",
            "result": "pass" if gate["passed"] else "fail",
            "value": gate,
        }
    )
    result_of = {c["id"].removeprefix("M04."): c["result"] for c in out}
    rows = w23_rows()
    placed = {a for row in rows.values() for a in row}
    for row, members in rows.items():
        results = {a: result_of[a] for a in members}
        row_ok = all(r in ("pass", "not_applicable") for r in results.values())
        out.append(
            {
                "id": f"M04.W23.{re.sub(r'[^A-Za-z]+', '_', row).strip('_').lower()}",
                "description": f"W23 (spec §15, as amended by §18 and §19 A2.13): {row}.",
                "result": "pass" if row_ok else "fail",
                "value": {"assertions": results},
            }
        )
    condition = {a: result_of[a] for a in W23_CONDITION}
    out.append(
        {
            "id": "M04.W23",
            "description": "§15's numerical-verification condition: A01–A30, A34, A35 tested in "
            "the default gate, A31–A32 recorded for the real variant. W23's verdict is the "
            "verdict lane's.",
            "result": "pass" if all(r == "pass" for r in condition.values()) else "fail",
            "value": {
                "condition": condition,
                "not_in_a_w23_row": sorted(set(assertions) - placed),
                "real_verdict": recorded["A31"][0]["verdict"],
            },
        }
    )
    pointers = register()
    out.append(
        {
            "id": "M04.register",
            "description": "Register entries decided by M04, and the ADRs they name (all present).",
            "result": "pass" if pointers["entries"] and not pointers["adrs_missing"] else "fail",
            "value": pointers,
        }
    )
    return out


def real_verdict(checks_: Sequence[Mapping[str, Any]]) -> str:
    """The first limitation, written from A31's check (the record's numbers, not a transcript)."""
    a31 = next(c["value"] for c in checks_ if c["id"] == "M04.A31")
    splits = ", ".join(
        f"{name} {split['failed']}/{split['count']}"
        for name, split in sorted(a31["splits"].items())
    )
    return (
        f"The real surrogate is {a31['verdict']} ({', '.join(a31['not_promotable']) or 'none'}): "
        f"WO-11 on `{a31['plan_id']}` with reactor v3 recorded {a31['certificate_refusals']} of "
        f"{a31['plan_requests']} registered experiments as deterministic "
        f"{' / '.join(a31['failure_codes'])} ({splits}), so k = {a31['k']} of n = {a31['n']} "
        f"tolerates only {a31['n'] - a31['k']} null scores and q̂ = +∞ (recorded as null). This is "
        "a measured property of v3 (§19 A2.13), not a defect of M04; per N6 M04 is `tested` "
        "whatever the real verdict, and M05 proceeds with the parent. The real surrogate claims "
        "nothing beyond its recorded verdict."
    )


def status(checks_: Sequence[Mapping[str, Any]], commands: Sequence[Mapping[str, Any]]) -> str:
    allowed = {f"M04.{a}" for a in CONDITIONAL}
    every = all(
        c["result"] == "pass" or (c["id"] in allowed and c["result"] == "not_applicable")
        for c in checks_
    )
    return "tested" if every and all(c["exit_code"] == 0 for c in commands) else "implemented"


# ----------------------------------------------------------------------------- harvest

#: A harvest classification: (class, pointers, note) (T08 spec §5.7).
Classified = tuple[str, tuple[str, ...], str]

#: Each limitation's classification, in the manifest's order (the first is the real verdict), by
#: R-365 (spec §20 A3.5). B points to T08 §6.3's B10, the handed-on follow-ups (build decision
#: E37: §6.3 has no M04 id).
NOTES: tuple[Classified, ...] = (
    ("E", ("L43",), "real surrogate NOT_PROMOTABLE (band_not_finite) on v3; L43 (R-365)"),
    ("B", ("B10",), "A33 not run (A31 not PROMOTABLE); Q-A2.1 open until A33's record (R-366)"),
    ("P", (), "real-reactor records opt-in, one machine; A32 bitwise per platform (R-362)"),
    ("P", (), "W23 verdict is the verdict lane's; self-generated records are regression fixtures"),
)
CHECK_NOTES: Mapping[str, Classified] = {
    "M04.A33": (
        "B",
        ("B10",),
        "A33 is conditional on a PROMOTABLE A31 (spec §12, §19 A2.13); not run (R-365)",
    ),
}
#: A manifest written before a limitation's text changed keeps its own classification: the
#: `a9566a6` manifest's E33 limitation is closed by R-362's pin, A49 (R-365: B, then S).
HARVEST_BY_COMMIT: Mapping[str, Mapping[int, Classified]] = {
    "a9566a6b3805938e8d4d386cc1820a551530f771": {
        2: (
            "S",
            ("check:M04.A49",),
            "E33 closed by the one-thread fit (R-362, A49; build decision E36)",
        ),
    },
}


def harvest_entries(path: str, manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    sys.path.insert(0, str(ROOT / "scripts"))
    from t08_support_matrix import text_sha256

    if len(manifest["limitations"]) != len(NOTES):
        raise SystemExit("the manifest's limitations and NOTES differ in number")
    own = HARVEST_BY_COMMIT.get(manifest["commit"], {})
    entries: list[dict[str, Any]] = []
    for index, text in enumerate(manifest["limitations"]):
        kind, pointers, note = own.get(index, NOTES[index])
        entries.append(
            {
                "manifest": path,
                "item": f"limitations[{index}]",
                "sha256": text_sha256(text),
                "class": kind,
                "to": list(pointers),
                "note": note,
            }
        )
    for index, check in enumerate(manifest["checks"]):
        if check["result"] == "pass":
            continue
        if check["id"] not in CHECK_NOTES or check["result"] != "not_applicable":
            raise SystemExit(f"{check['id']} is {check['result']}: not classified; fix it first")
        kind, pointers, note = CHECK_NOTES[check["id"]]
        entries.append(
            {
                "manifest": path,
                "item": f"checks[{index}]",
                "check_id": check["id"],
                "sha256": text_sha256(check),
                "class": kind,
                "to": list(pointers),
                "note": note,
            }
        )
    return entries


def _yaml_entry(entry: Mapping[str, Any]) -> str:
    lines = [f"- manifest: {entry['manifest']}", f"  item: {entry['item']}"]
    if "check_id" in entry:
        lines.append(f"  check_id: {entry['check_id']}")
    lines += [f"  sha256: {entry['sha256']}", f"  class: {entry['class']}"]
    lines += [f"  to:{'' if entry['to'] else ' []'}", *(f"  - {p}" for p in entry["to"])]
    lines.append(f"  note: {entry['note']}")
    return "\n".join(lines) + "\n"


def write_harvest(entries: Sequence[Mapping[str, Any]]) -> None:
    """Replace the envelope's `evidence/M04/` harvest entries with `entries`, at the end of the
    list (the file's last section), leaving every other byte as it is."""
    text = ENVELOPE.read_text(encoding="utf-8")
    head, marker, body = text.partition("\nharvest:\n")
    if not marker:
        raise SystemExit("support_envelope.yaml has no harvest section")
    blocks = re.split(r"(?m)^(?=- manifest: )", body)
    kept = [b for b in blocks if b and not b.startswith("- manifest: evidence/M04/")]
    if any(not b.startswith("- manifest: ") for b in kept):
        raise SystemExit("support_envelope.yaml: unexpected text in the harvest section")
    ENVELOPE.write_text(
        head + marker + "".join(kept) + "".join(_yaml_entry(e) for e in entries), encoding="utf-8"
    )
    loaded = yaml.safe_load(ENVELOPE.read_text(encoding="utf-8"))["harvest"]
    written = [e for e in loaded if str(e.get("manifest", "")).startswith("evidence/M04/")]
    if written != [dict(e) for e in entries]:
        raise SystemExit("support_envelope.yaml: the harvest entries did not round-trip")


def harvest(manifest_paths: Sequence[Path]) -> int:
    entries: list[dict[str, Any]] = []
    for manifest_path in manifest_paths:
        path = manifest_path.resolve().relative_to(ROOT).as_posix()
        manifest = json.loads((ROOT / path).read_text(encoding="utf-8"))
        entries += harvest_entries(path, manifest)
    write_harvest(entries)
    subprocess.run(
        [sys.executable, "scripts/t08_support_matrix.py", "--emit"], cwd=ROOT, check=True
    )
    print(f"harvest: {len(entries)} entries for {len(manifest_paths)} manifests")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--commit")
    parser.add_argument("--gate-log", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--harvest-from", type=Path, nargs="+")
    args = parser.parse_args(argv)
    if args.harvest_from is not None:
        return harvest(args.harvest_from)
    if args.commit is None or args.gate_log is None:
        parser.error("--commit and --gate-log are required to generate a manifest")
    commit = _git("rev-parse", args.commit).strip()
    if _git("rev-parse", "HEAD").strip() != commit:
        raise SystemExit(f"HEAD is not {commit}: check it out first")
    if _git("status", "--porcelain", "--untracked-files=no").strip():
        raise SystemExit("the working tree has changes: the manifest must describe C")
    out = args.out or ROOT / "evidence" / "M04" / commit / "manifest.json"
    gate = read_gate(args.gate_log, commit)
    with tempfile.TemporaryDirectory(prefix="m04-evidence-") as scratch:
        nodes, test_command = run_tests(Path(scratch))
    commands = [
        {
            "cmd": "PYTHONPATH=src PATH=.venv/bin:$PATH ./scripts/gate.sh",
            "cwd": ".",
            "exit_code": 0 if gate["passed"] else 1,
            "stdout_sha256": gate["stdout_sha256"],
        },
        test_command,
    ]
    result = checks(nodes, gate)
    manifest = {
        "work_package": "M04",
        "commit": commit,
        "requirements": list(REQUIREMENTS),
        "status": status(result, commands),
        "inputs": {
            "case_id": "plan b2-it1 on pymrm-6089593-g2-nz800-s123-v3 (WO-11, opt-in record); "
            "the synthetic parents, the stand-in and the v1 plans (default gate)",
            "case_hash": _sha256(M04 / "plan-b2-it1.json"),
            "environment_lock_hash": _sha256(ROOT / "requirements.lock"),
        },
        "commands": commands,
        "checks": result,
        "artifacts": [
            {"path": path, "sha256": _sha256(ROOT / path), "description": text}
            for path, text in ARTIFACTS
        ],
        "limitations": [real_verdict(result), *LIMITATIONS],
        "review": {"numerical": "pending", "process_model": "pending"},
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    failed = [c["id"] for c in result if c["result"] not in ("pass", "not_applicable")]
    na = [c["id"] for c in result if c["result"] == "not_applicable"]
    print(
        f"{manifest['status']}: {len(result) - len(failed) - len(na)}/{len(result)} pass, "
        f"not_applicable {na}, failed {failed or '[]'}"
    )
    return 0 if manifest["status"] == "tested" else 1


if __name__ == "__main__":
    raise SystemExit(main())
