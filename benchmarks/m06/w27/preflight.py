"""W27's preflight: the campaign's preconditions P1–P8 (M06 WO-16e).

Normative text: registration §18 WO-16e and W27-R56 ("the preflight of §18 WO-16e passed before the
first run" is gated, G16), after V17's `benchmarks/t07/v17/preflight.py`; P5–P8 as registration
§23.3–§23.5 (Amendment 4) restate them. Each check returns a verdict `{passed, …detail}`;
`require` raises unless all eight pass and returns the verdicts, which the `campaign` command
records in `preflight.json` (W27-R67). The standalone `preflight` command writes nothing.

- **P1** Frank's spend approval is recorded: a line starting `APPROVAL_LINE` in `APPROVAL_FILE`
  (registration §17 Q3/Q5, design note F1). Nothing in the build lane can make it pass.
- **P2** `registration.json`, the registration document and its generator are as registered
  (`REGISTERED_SHA256`; an amendment changes these pins in the commit that records it); the
  generator's `--check` passes; its `facts --check` passes against the archive, whose size and
  SHA-256 equal `provenance.json`'s (a mismatch stops the campaign: design note R5).
- **P3** the campaign's `coverage.json` was made at this commit from this build (its snapshot is
  rebuilt equal), re-classifies to the same rows, passes G14, and its snapshot is not refused.
- **P4** `sample.json` is the byte-identical re-draw from that `coverage.json` (W27-A20).
- **P5** `confirmation/confirmation.json` (W27-R66) has exactly the registered members, names
  this campaign and HEAD, both digests equal the files', its candidates are the recomputed ones,
  and C is empty (a non-empty C fails with `non_empty_candidates`).
- **P6** the canary attempts `canary/<NN>-<case_id>/` are numbered 01…N contiguously, N ≤ 6, each
  on a canary case, none repeating a case that passed at its commit; each canary case's latest
  (counted) attempt passed (`harness.canary_verdict`) at HEAD with a clean tree (W27-R68).
- **P7** a pinning attempt exists; the pin equals its `init` model and is not `claude-sonnet-5`;
  it and the attempts before it requested no model, every later one the pin; every counted
  attempt's `init` shows the pin and the pinned Claude Code version (registration §23.5).
- **P8** the checkout is a clean commit, and the campaign directory holds no run directory, no
  `campaign.json` and no `preflight.json` (`canary/`, `confirmation/`, `coverage.json` and
  `sample.json` are expected there).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from benchmarks.m06.w27 import coverage as classifier
from benchmarks.m06.w27 import facts, harness, registration, sample, snapshot
from benchmarks.m06.w27 import scorer as w27_scorer

Verdict = dict[str, Any]

#: P1: where Frank's answer to F1 is recorded, and the line that records it.
APPROVAL_FILE: Final[Path] = registration.ROOT / "docs" / "V02_DECISIONS.md"
APPROVAL_LINE: Final[str] = "- **W27 Tier 1 approved**"
#: P2: the registered files' SHA-256 at registration (WO-15, `5ceb32c`), as amended by the
#: document's §20 (Amendment 1, M06 review F5), §21 (Amendment 2: the C1 rows, W27-R62/R63),
#: §22 (Amendment 3: `c1.reactor_surrogate`) and §23 (Amendment 4: the campaign's records, order,
#: re-canaries and model pin). An amendment of the registration changes these pins in the commit
#: that records it.
REGISTERED_SHA256: Final[Mapping[Path, str]] = {
    registration.REGISTRATION_JSON: (
        "ee099a60f9da6900325f54127f92e9eee926d2015f97b527843db482d6f0e52e"
    ),
    registration.DOCUMENT: "bf48a5212cb0f17675567a8194e61d1f5b6665a082c0c3916a341d7d93260c70",
    registration.GENERATOR: "3d7429a258fca0bc92af4a3e4113af7f4ef62cd2b1cd8e4999e9c8f6eb9241eb",
}


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
    path = campaign.directory / harness.CONFIRMATION_FILE
    coverage_bytes = campaign.coverage_path.read_bytes()
    sample_bytes = campaign.sample_path.read_bytes()
    candidates = harness.sampled_candidates(json.loads(coverage_bytes), json.loads(sample_bytes))
    reason = "non_empty_candidates" if candidates else None
    if not path.is_file():
        return {"passed": False, "candidates": candidates, "failed": ["file"], "reason": reason}
    record = json.loads(path.read_bytes())
    table = harness.campaign_records()["confirmation"]
    checks = {
        "members": sorted(record) == sorted(table["members"])
        and record.get("schema") == table["schema"],
        "campaign": record.get("campaign") == campaign.name,
        "commit": record.get("commit") == _git("rev-parse", "HEAD"),
        "coverage_sha256": record.get("coverage_sha256")
        == registration.sha256_bytes(coverage_bytes),
        "sample_sha256": record.get("sample_sha256") == registration.sha256_bytes(sample_bytes),
        "candidates": record.get("candidates") == candidates,
        "empty": record.get("empty") is True,
    }
    failed = [name for name, held in checks.items() if not held]
    return {"passed": not failed, "candidates": candidates, "failed": failed, "reason": reason}


def _canaries(campaign: Campaign) -> list[str]:
    canaries: list[str] = json.loads(campaign.sample_path.read_bytes())["canaries"]
    return canaries


def p6(campaign: Campaign) -> Verdict:
    records = harness.campaign_records()
    attempts = harness.canary_attempts(campaign.directory)
    canaries = _canaries(campaign)
    head = _git("rev-parse", "HEAD")
    pattern = re.compile(str(records["canary_attempt_pattern"]))
    problems: list[str] = []
    numbered = [a.n for a in attempts] == list(range(1, len(attempts) + 1))
    if (
        not numbered
        or len(attempts) > int(records["canary_attempts_max"])
        or not all(pattern.match(a.name) for a in attempts)
    ):
        problems.append(f"numbering: {[a.name for a in attempts]}")
    strangers = [a.name for a in attempts if a.case_id not in canaries]
    if strangers:
        problems.append(f"not_a_canary: {strangers}")
    rerolled = [
        a.name
        for k, a in enumerate(attempts)
        if any(b.case_id == a.case_id and b.commit == a.commit and b.passed for b in attempts[:k])
    ]
    if rerolled:
        problems.append(f"passed_case_attempted_again: {rerolled}")
    counted = harness.counted_attempts(attempts, canaries)
    for case_id, attempt in counted.items():
        if attempt is None:
            problems.append(f"never_attempted: {case_id}")
        elif not attempt.passed:
            problems.append(f"counted_attempt_failed: {attempt.name}")
        elif attempt.commit != head or attempt.tree_clean is not True:
            problems.append(f"counted_attempt_not_at_head_clean: {attempt.name}")
    return {
        "passed": not problems,
        "problems": problems,
        "attempts": [a.name for a in attempts],
        "counted": {c: a.name if a is not None else None for c, a in counted.items()},
    }


def p7(campaign: Campaign) -> Verdict:
    attempts = harness.canary_attempts(campaign.directory)
    pinning = harness.pinning_attempt(attempts)
    pin = campaign.model
    problems: list[str] = []
    if pinning is None:
        problems.append("no_pinning_attempt")
    else:
        if pin != pinning.init_model:
            problems.append(f"pin_is_not_{pinning.name}_init_model: {pinning.init_model!r}")
        if pin == harness.NOT_THE_MODEL:
            problems.append(f"pin_is_{harness.NOT_THE_MODEL}")
        k = attempts.index(pinning)
        early = [a.name for a in attempts[: k + 1] if a.model is not None]
        late = [a.name for a in attempts[k + 1 :] if a.model != pinning.init_model]
        if early:
            problems.append(f"model_requested_before_the_pin: {early}")
        if late:
            problems.append(f"pin_not_requested_after_it: {late}")
    for attempt in harness.counted_attempts(attempts, _canaries(campaign)).values():
        if attempt is None:
            continue
        if attempt.init_model != pin:
            problems.append(f"counted_init_model_not_the_pin: {attempt.name}")
        if attempt.init_claude_code_version != campaign.claude_code_version:
            problems.append(f"counted_init_version_not_pinned: {attempt.name}")
    return {
        "passed": not problems,
        "problems": problems,
        "pinned": {"model": pin, "claude_code_version": campaign.claude_code_version},
        "pinning_attempt": pinning.name if pinning is not None else None,
    }


def p8(campaign: Campaign) -> Verdict:
    clean = harness.git_state(campaign.runs_root)["tree_clean"] is True
    directory = campaign.directory
    pattern = re.compile(str(harness.campaign_records()["run_dir_pattern"]))
    files = {harness.PREFLIGHT_FILE, w27_scorer.CAMPAIGN_FILE}
    present = (
        sorted(
            p.name
            for p in directory.iterdir()
            if (p.is_dir() and pattern.match(p.name)) or (p.is_file() and p.name in files)
        )
        if directory.is_dir()
        else []
    )
    return {"passed": clean and not present, "tree_clean": clean, "runs_present": present}


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


def run_all(
    campaign: Campaign, checks: Mapping[str, Callable[[Campaign], Verdict]] = CHECKS
) -> dict[str, Verdict]:
    results: dict[str, Verdict] = {}
    for name, check in checks.items():
        try:
            results[name] = check(campaign)
        except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
            results[name] = {"passed": False, "error": f"{type(error).__name__}: {error}"}
    return results


def require(
    campaign: Campaign, checks: Mapping[str, Callable[[Campaign], Verdict]] = CHECKS
) -> dict[str, Verdict]:
    """P1–P8's verdicts, which `preflight.json` records; raises unless all pass."""
    results = run_all(campaign, checks)
    failed = sorted(name for name, verdict in results.items() if not verdict["passed"])
    if failed:
        raise PreflightError(f"preflight failed: {failed}")
    return results
