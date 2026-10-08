"""W27's preflight: the campaign's preconditions P1–P8 (M06 WO-16e).

Normative text: registration §18 WO-16e and W27-R56 ("the preflight of §18 WO-16e passed before the
first run" is gated, G16), after V17's `benchmarks/t07/v17/preflight.py`. Each check returns a
verdict `{passed, …detail}`; `require` raises unless all eight pass.

- **P1** Frank's spend approval is recorded: a line starting `APPROVAL_LINE` in `APPROVAL_FILE`
  (registration §17 Q3/Q5, design note F1). Nothing in the build lane can make it pass.
- **P2** `registration.json`, the registration document and its generator are as registered
  (`REGISTERED_SHA256`; an amendment changes these pins in the commit that records it); the
  generator's `--check` passes; its `facts --check` passes against the archive, whose size and
  SHA-256 equal `provenance.json`'s (a mismatch stops the campaign: design note R5).
- **P3** the campaign's `coverage.json` was made at this commit from this build (its snapshot is
  rebuilt equal), re-classifies to the same rows, passes G14, and its snapshot is not refused.
- **P4** `sample.json` is the byte-identical re-draw from that `coverage.json` (W27-A20).
- **P5** §7: every sampled `CANDIDATE` has its committed scripted reference build and a record
  showing `VERIFIED` with every stream floor ≤ 1/`floor_margin`; or the sample has none.
- **P6** three canaries are recorded under `<campaign>/canary/` and each passed
  (`harness.canary_verdict`).
- **P7** the model id and Claude Code version the campaign pins are what all three canaries'
  `init` messages showed.
- **P8** the checkout is a clean commit, and the campaign directory holds no run yet.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from benchmarks.m06.w27 import coverage as classifier
from benchmarks.m06.w27 import facts, harness, registration, sample, snapshot

Verdict = dict[str, Any]

#: P1: where Frank's answer to F1 is recorded, and the line that records it.
APPROVAL_FILE: Final[Path] = registration.ROOT / "docs" / "V02_DECISIONS.md"
APPROVAL_LINE: Final[str] = "- **W27 Tier 1 approved**"
#: P2: the registered files' SHA-256 at registration (WO-15, `5ceb32c`). An amendment of the
#: registration changes these pins in the commit that records it.
REGISTERED_SHA256: Final[Mapping[Path, str]] = {
    registration.REGISTRATION_JSON: (
        "ce59200a0bdaf26bbf6c830fb56e69d187d6dba81a0cb348a713d638e4544f7a"
    ),
    registration.DOCUMENT: "71884fcd306480157791c137793a15d0aeae51654485ea0a7fc03649bbe42a13",
    registration.GENERATOR: "98425556530bde87f07a1340e3217a36919862d802de1199204f550c38420f23",
}
#: P5: the scripted reference builds of §7.
CONFIRMATION: Final[Path] = registration.RECORDS / "confirmation"


class PreflightError(harness.HarnessError):
    """A precondition of the campaign does not hold; nothing was launched."""


@dataclass(frozen=True)
class Campaign:
    """What the preflight judges: the campaign directory and its pins."""

    name: str
    runs_root: Path
    coverage_path: Path
    sample_path: Path
    model: str
    claude_code_version: str
    approval_file: Path = APPROVAL_FILE

    @property
    def directory(self) -> Path:
        return self.runs_root / self.name


def _git(*arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(registration.ROOT), *arguments],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def p1(campaign: Campaign) -> Verdict:
    path = campaign.approval_file
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    found = [k + 1 for k, line in enumerate(lines) if line.startswith(APPROVAL_LINE)]
    return {
        "passed": bool(found),
        "file": path.name,
        "lines": found,
        "reason": None if found else f"no line starting {APPROVAL_LINE!r} (Frank's F1 answer)",
    }


def _archive() -> Verdict:
    provenance = json.loads(registration.PROVENANCE_JSON.read_bytes())["archive"]
    path = registration.ARCHIVE_FILE
    if not path.is_file():
        return {"present": False}
    return {
        "present": True,
        "size_matches": path.stat().st_size == provenance["size_bytes"],
        "sha256_matches": registration.sha256_file(path) == provenance["sha256"],
    }


def p2(campaign: Campaign) -> Verdict:
    del campaign
    digests = {p.name: registration.sha256_file(p) for p in REGISTERED_SHA256}
    pinned = all(registration.sha256_file(p) == sha for p, sha in REGISTERED_SHA256.items())
    archive = _archive()
    check = subprocess.run(
        [sys.executable, str(registration.GENERATOR), "--check"],
        capture_output=True,
        text=True,
        check=False,
        env={"PYTHONPATH": str(registration.ROOT / "src"), "PATH": "/usr/bin:/bin"},
    )
    facts_check = subprocess.run(
        [sys.executable, "-I", str(registration.GENERATOR), "facts", "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    archive_ok = archive.get("size_matches") is True and archive.get("sha256_matches") is True
    return {
        "passed": pinned and archive_ok and check.returncode == 0 and facts_check.returncode == 0,
        "sha256": digests,
        "sha256_as_registered": pinned,
        "archive": archive,
        "generator_check_exit": check.returncode,
        "generator_check_tail": check.stdout.strip().splitlines()[-1:],
        "facts_check_exit": facts_check.returncode,
        "facts_check_tail": facts_check.stdout.strip().splitlines()[-1:],
    }


def p3(campaign: Campaign) -> Verdict:
    document = json.loads(campaign.coverage_path.read_bytes())
    head = _git("rev-parse", "HEAD")
    try:
        live = snapshot.build_snapshot()
        again = classifier.coverage_document(facts.load_facts(), document["snapshot"])
    except (classifier.RefusalError, snapshot.SnapshotUnsupportedError) as refusal:
        return {"passed": False, "refused": str(refusal)}
    made_here = document["snapshot"].get("git_commit") == head
    same_build = live == {**document["snapshot"], "git_commit": live["git_commit"]}
    same_rows = again["rows"] == document["rows"] and again["summary"] == document["summary"]
    verdict = classifier.g14(document)
    return {
        "passed": made_here and same_build and same_rows and verdict["passed"],
        "made_at_this_commit": made_here,
        "snapshot_rebuilt_equal": same_build,
        "reclassifies_equal": same_rows,
        "g14": verdict["passed"],
        "snapshot_sha256": document["snapshot_sha256"],
    }


def p4(campaign: Campaign) -> Verdict:
    data = campaign.coverage_path.read_bytes()
    redrawn = registration.dump(sample.sample_document(json.loads(data), data))
    recorded = campaign.sample_path.read_bytes()
    return {"passed": redrawn == recorded, "sample_sha256": registration.sha256_bytes(recorded)}


def p5(campaign: Campaign) -> Verdict:
    drawn = json.loads(campaign.sample_path.read_bytes())
    rows = {r["case_id"]: r for r in json.loads(campaign.coverage_path.read_bytes())["rows"]}
    candidates = [c for c in drawn["cases"] if rows[c]["class"] == "CANDIDATE"]
    if not candidates:
        return {"passed": True, "candidates": 0, "record": "C is empty: §7 has nothing to confirm"}
    margin = float(registration.load()["scoring"]["stream_tolerance"]["floor_margin"])
    missing = []
    for case_id in candidates:
        script = CONFIRMATION / f"{case_id}.py"
        record_path = CONFIRMATION / f"{case_id}.json"
        record = json.loads(record_path.read_bytes()) if record_path.is_file() else {}
        floors = record.get("floors") or {}
        ok = (
            script.is_file()
            and record.get("verification_status") == "VERIFIED"
            and bool(floors)
            and all(isinstance(v, int | float) and v <= 1.0 / margin for v in floors.values())
        )
        if not ok:
            missing.append(case_id)
    return {"passed": not missing, "candidates": len(candidates), "not_confirmed": missing}


def _canary_dirs(campaign: Campaign) -> list[Path]:
    root = campaign.directory / harness.CANARY_DIR
    return sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []


def p6(campaign: Campaign) -> Verdict:
    verdicts = {p.name: harness.canary_verdict(p) for p in _canary_dirs(campaign)}
    return {
        "passed": len(verdicts) == 3 and all(v["passed"] for v in verdicts.values()),
        "canaries": verdicts,
    }


def p7(campaign: Campaign) -> Verdict:
    seen = [harness.canary_verdict(p) for p in _canary_dirs(campaign)]
    models = sorted({str(v["init_model"]) for v in seen})
    versions = sorted({str(v["init_claude_code_version"]) for v in seen})
    return {
        "passed": len(seen) == 3
        and models == [campaign.model]
        and versions == [campaign.claude_code_version],
        "pinned": {"model": campaign.model, "claude_code_version": campaign.claude_code_version},
        "canary_models": models,
        "canary_claude_code_versions": versions,
    }


def p8(campaign: Campaign) -> Verdict:
    clean = harness.git_state(campaign.runs_root)["tree_clean"] is True
    directory = campaign.directory
    runs = (
        sorted(
            p.name
            for p in directory.iterdir()
            if p.name != harness.CANARY_DIR and (p.is_dir() or p.name == "campaign.json")
        )
        if directory.is_dir()
        else []
    )
    return {"passed": clean and not runs, "tree_clean": clean, "runs_present": runs}


CHECKS: Final[Mapping[str, Callable[[Campaign], Verdict]]] = {
    "P1": p1,
    "P2": p2,
    "P3": p3,
    "P4": p4,
    "P5": p5,
    "P6": p6,
    "P7": p7,
    "P8": p8,
}


def run_all(campaign: Campaign) -> dict[str, Verdict]:
    results: dict[str, Verdict] = {}
    for name, check in CHECKS.items():
        try:
            results[name] = check(campaign)
        except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
            results[name] = {"passed": False, "error": f"{type(error).__name__}: {error}"}
    return results


def require(campaign: Campaign) -> None:
    results = run_all(campaign)
    failed = sorted(name for name, verdict in results.items() if not verdict["passed"])
    if failed:
        raise PreflightError(f"preflight failed: {failed}")
