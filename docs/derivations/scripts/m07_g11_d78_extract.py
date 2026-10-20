#!/usr/bin/env python3
"""M07 Amendment 7 (spec §24.3, R-480): the registered D78 extract for G11 at C′.

Usage (standard library and git only; no ``openflowsheet`` import, no network)::

    python3 -I docs/derivations/scripts/m07_g11_d78_extract.py          # write the extract
    python3 -I docs/derivations/scripts/m07_g11_d78_extract.py --check  # regenerate, compare bytes

``benchmarks/m02/g11_coverage_v3.py`` requires ``--d78``, the record of M02's uncommitted D78
experiment (``g11-exp.json``, sha256 ``afa7325a…``). That file is lost (M07 build log J64). The
script reads three things from it, and nothing else: ``variant``; each point's ``label`` and
``stage``; and ``stage_steps.S1`` of the points that ended ``S1``
(``g11_coverage_v3.py``: ``summarise``, the ``then`` map). Every value it read is written back into
four committed records, each of which names the lost file's sha256:

- ``summary["G11v3-3"]["corners"][label]["d78_stage"]``;
- ``summary["G11v3-5"]["S1_as_D78"]["points"][label]["d78_S1_steps"]`` (those points' stage is
  ``S1``);
- ``summary["G11v3-8"]["points"][label]["d78_stage"]``;
- ``d78["variant"]``.

This script rebuilds exactly those values into a file of the shape ``--d78`` reads. The self-claims
(E1-E5) make the extraction executable. The script refuses to emit, and ``--check`` fails, when one
of them stops being true.

- **E1.** Each source names ``d78.sha256`` = ``D78_SHA256`` and the same ``d78.variant``.
- **E2.** The four sources give the same extract (label -> stage, S1 steps), and inside one source a
  label that two maps name has one stage.
- **E3.** The extract has the counts that ``g11_coverage_v3.py``'s clauses need: 25 labels; 16 old
  corners; the G11v3-5 predicate selects exactly the 10 ``S1`` labels; 3 ``corner-T773.15…``
  labels end ``nonpositive_flow`` (G11v3-3), and 6 of the 8 G11v3-8 labels do (G11v3-8 (a)).
- **E4.** ``--previous-runs`` (``0656f617…``, also lost) may be omitted. Without it,
  ``inertness`` reads the step counts from ``--previous``'s ``points`` (D100's fallback). At each of
  the three alpha RCs, every run's ``stage_steps`` equal those ``points``' ``stage_steps`` at every
  label G11v3-11 compares. So the fallback gives the verdict the raw runs gave (0 differences)
  there. ``--previous`` is ``git show bd446ab:benchmarks/m02/g11-coverage-v3.json``
  (sha256 ``PREVIOUS_SHA256``). A checkout without that commit makes the script refuse.
- **E5.** ``--check`` regenerates and compares bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Final

ROOT: Final = Path(__file__).resolve().parents[3]
OUT: Final = ROOT / "docs" / "derivations" / "scripts" / "m07_g11_d78_extract.json"

D78_SHA256: Final = "afa7325ac72124156e7750ddfb9e553a15e860386c05ba2d55c7a652fb85b2ce"
D78_PATH: Final = "evidence/M02/wo12a-experiment/artifacts/g11-exp.json"
PREVIOUS_RUNS_SHA256: Final = "0656f617241dbb770f4818b7674df52288eb02fe8da18d7bee13b8dbcb6a76c6"
PREVIOUS_SHA256: Final = "fa1b02544f00a1ce02a203dc8cccc9d7bc5e35122a79cfe1506e355bb9729a90"
PREVIOUS_GIT: Final = "bd446ab:benchmarks/m02/g11-coverage-v3.json"

#: WO-12a″'s committed record, then the step-12 records of the three alpha RCs (C_α⁰, C_α¹, C_α²).
SOURCES: Final = (
    "benchmarks/m02/g11-coverage-v3.json",
    "evidence/M07a/e0e198e4632224612671db5b07445639d272d6da/rc/step12/g11-coverage-v3.json",
    "evidence/M07a/cc73219a77f6a54579c8acb151ed6fae228c8a4c/rc/step12/g11-coverage-v3.json",
    "evidence/M07a/6fec82232e1c47308a5e1d67338058f352992800/rc/step12/g11-coverage-v3.json",
)
#: The sources whose raw runs are committed beside them (E4).
ALPHA_SOURCES: Final = SOURCES[1:]

#: g11_coverage_v3.py's G11v3-5 predicate (`summarise`, `s1_labels`) and its M05_S1_LABEL.
S1_PREFIXES: Final = ("corner-T573.15", "B2-corner-T653.15-P1.5e+07")
M05_S1_LABEL: Final = "B1-m05-T643.15"

EXPECTED_LABELS: Final = 25
EXPECTED_CORNERS: Final = 16
EXPECTED_S1: Final = 10
EXPECTED_NONPOSITIVE_773: Final = 3
EXPECTED_G8: Final = 8
EXPECTED_G8_NONPOSITIVE: Final = 6
EXPECTED_G11V3_11_LABELS: Final = 87


class RefusalError(Exception):
    """A self-claim is false; nothing is written."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load(relative: str) -> tuple[Any, str]:
    data = (ROOT / relative).read_bytes()
    return json.loads(data), _sha256_bytes(data)


def _extract_one(record: dict[str, Any], name: str) -> dict[str, dict[str, Any]]:
    """Label -> {"stage": …, "S1": n (S1 points only)} from one record's summary (E2's inner
    consistency)."""
    summary = record["summary"]
    extract: dict[str, dict[str, Any]] = {}

    def put(label: str, stage: Any) -> None:
        if label in extract and extract[label]["stage"] != stage:
            was = extract[label]["stage"]
            raise RefusalError(f"E2: {name}: {label} has stages {was!r} and {stage!r}")
        extract.setdefault(label, {})["stage"] = stage

    for label, entry in summary["G11v3-3"]["corners"].items():
        put(label, entry["d78_stage"])
    for label, entry in summary["G11v3-5"]["S1_as_D78"]["points"].items():
        put(label, "S1")
        steps = entry["d78_S1_steps"]
        if not isinstance(steps, int) or isinstance(steps, bool):
            raise RefusalError(f"E2: {name}: {label} has no integer D78 S1 step count ({steps!r})")
        extract[label]["S1"] = steps
    for label, entry in summary["G11v3-8"]["points"].items():
        put(label, entry["d78_stage"])
    return extract


def _s1_labels(points: list[dict[str, Any]]) -> list[str]:
    return [
        p["label"]
        for p in points
        if p.get("stage") == "S1"
        and (p["label"].startswith(S1_PREFIXES) or p["label"] == M05_S1_LABEL)
    ]


def _check_counts(points: list[dict[str, Any]], corners: set[str], g8: set[str]) -> dict[str, Any]:
    """E3."""
    by_label = {p["label"]: p for p in points}
    s1 = _s1_labels(points)
    nonpositive_773 = sorted(
        label
        for label in corners
        if label.startswith("corner-T773.15") and by_label[label]["stage"] == "nonpositive_flow"
    )
    g8_nonpositive = sorted(label for label in g8 if by_label[label]["stage"] == "nonpositive_flow")
    found = {
        "labels": len(points),
        "old_corners": len(corners),
        "S1": len(s1),
        "nonpositive_flow_773": len(nonpositive_773),
        "G11v3-8": len(g8),
        "G11v3-8_nonpositive_flow": len(g8_nonpositive),
    }
    expected = {
        "labels": EXPECTED_LABELS,
        "old_corners": EXPECTED_CORNERS,
        "S1": EXPECTED_S1,
        "nonpositive_flow_773": EXPECTED_NONPOSITIVE_773,
        "G11v3-8": EXPECTED_G8,
        "G11v3-8_nonpositive_flow": EXPECTED_G8_NONPOSITIVE,
    }
    if found != expected:
        raise RefusalError(f"E3: counts {found} differ from {expected}")
    if any("stage_steps" not in by_label[label] for label in s1):
        raise RefusalError("E3: an S1 label has no stage_steps")
    if any("stage_steps" in p for p in points if p["label"] not in s1):
        raise RefusalError("E3: a label outside the S1 set carries stage_steps")
    steps = sorted({by_label[label]["stage_steps"]["S1"] for label in s1})
    return {"counts": found, "S1_labels": s1, "S1_steps": steps}


def _previous() -> dict[str, Any]:
    completed = subprocess.run(
        ["git", "show", PREVIOUS_GIT], cwd=ROOT, capture_output=True, check=False
    )
    if completed.returncode != 0:
        raise RefusalError(f"E4: `git show {PREVIOUS_GIT}` failed; this checkout lacks bd446ab")
    if _sha256_bytes(completed.stdout) != PREVIOUS_SHA256:
        raise RefusalError(f"E4: {PREVIOUS_GIT} is not sha256 {PREVIOUS_SHA256}")
    previous: dict[str, Any] = json.loads(completed.stdout)
    return previous


def _check_fallback(previous: dict[str, Any]) -> list[dict[str, Any]]:
    """E4: at each alpha RC, every run's stage_steps equal `--previous`'s `points` stage_steps at
    every label G11v3-11 compares, and G11v3-11 itself read the raw runs with 0 differences."""
    before = {p["label"]: p for p in previous["points"]}
    out = []
    for relative in ALPHA_SOURCES:
        record, _ = _load(relative)
        prior = record["previous"]
        g11 = record["summary"]["G11v3-11"]
        if prior["sha256"] != PREVIOUS_SHA256 or prior["runs_sha256"] != PREVIOUS_RUNS_SHA256:
            raise RefusalError(f"E4: {relative} names another --previous or --previous-runs")
        if g11["stage_steps_from"] != "raw runs" or g11["differences"] or not g11["met"]:
            raise RefusalError(
                f"E4: {relative}'s G11v3-11 did not read the raw runs with 0 differences"
            )
        labels = [label for label in before if label not in set(g11["excluded"])]
        if len(labels) != EXPECTED_G11V3_11_LABELS or g11["labels"] != len(labels):
            raise RefusalError(
                f"E4: {relative}: {len(labels)} labels, the record says {g11['labels']}"
            )
        runs, _ = _load(relative.replace(".json", ".runs.json"))
        unequal = [
            (k + 1, label)
            for k, run in enumerate(runs)
            for label, point in ((p["label"], p) for p in run)
            if label in labels and point.get("stage_steps") != before[label].get("stage_steps")
        ]
        seen = [sum(1 for p in run if p["label"] in labels) for run in runs]
        if unequal or len(runs) != 2 or seen != [len(labels)] * 2:
            raise RefusalError(f"E4: {relative}: fallback differs ({unequal[:3]}, runs {seen})")
        out.append({"record": relative, "runs": len(runs), "labels": len(labels), "differences": 0})
    return out


def build() -> str:
    extracts = []
    variants = []
    sources = []
    corners: set[str] = set()
    g8: set[str] = set()
    for relative in SOURCES:
        record, sha = _load(relative)
        if record["d78"]["sha256"] != D78_SHA256:
            raise RefusalError(f"E1: {relative} names d78 {record['d78']['sha256']}")
        variants.append(record["d78"]["variant"])
        extracts.append(_extract_one(record, relative))
        corners |= set(record["summary"]["G11v3-3"]["corners"])
        g8 |= set(record["summary"]["G11v3-8"]["points"])
        sources.append({"path": relative, "sha256": sha})
    if any(v != variants[0] for v in variants):
        raise RefusalError("E1: the sources name different D78 variants")
    if any(e != extracts[0] for e in extracts):
        raise RefusalError("E2: the sources give different extracts")
    points = []
    for label in sorted(extracts[0]):
        entry = extracts[0][label]
        point: dict[str, Any] = {"label": label, "stage": entry["stage"]}
        if "S1" in entry:
            point["stage_steps"] = {"S1": entry["S1"]}
        points.append(point)
    claims = _check_counts(points, corners, g8)
    fallback = _check_fallback(_previous())
    doc = {
        "format": "m07-g11-d78-extract-v1",
        "specification": "docs/derivations/M07-spec.md §24.3 (R-480)",
        "generator": "docs/derivations/scripts/m07_g11_d78_extract.py",
        "original": {
            "path": D78_PATH,
            "sha256": D78_SHA256,
            "state": "lost (M07 build log J64); not reproducible (uncommitted experiment patch)",
        },
        "reads": (
            "g11_coverage_v3.py reads `variant`, and each point's `label`, `stage` and "
            "`stage_steps.S1`; the other members of this file are provenance"
        ),
        "derived_from": sources,
        "self_claims": {
            "E3": claims,
            "E4": {
                "previous": {"git": PREVIOUS_GIT, "sha256": PREVIOUS_SHA256},
                "previous_runs_lost_sha256": PREVIOUS_RUNS_SHA256,
                "fallback_equal_at": fallback,
            },
        },
        "variant": variants[0],
        "points": points,
    }
    return json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    try:
        text = build()
    except RefusalError as refusal:
        print(f"m07_g11_d78_extract: REFUSED: {refusal}", file=sys.stderr)
        return 1
    if arguments.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print("m07_g11_d78_extract --check: FAIL (the committed file differs)", file=sys.stderr)
            return 1
        print("m07_g11_d78_extract --check: PASS")
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} (sha256 {_sha256_bytes(text.encode('utf-8'))})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
