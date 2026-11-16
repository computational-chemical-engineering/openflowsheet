#!/usr/bin/env python3
"""S19 gate report: is the gate still the bottleneck? One screen, measured, with targets.

Reads what the gates and the queue already write (no model, no test run):
  <git-common-dir>/codehealth/runs/s19-gates/<stamp>-<label>.{json,tiers.log}: tiers, selection
  <git-common-dir>/codehealth/queue/done/<label>.json: enqueued, started, finished
  <git-common-dir>/codehealth/runs/s19.jsonl: steps and debt

  gate_report.py [--hours H] [--append FILE] [--slow N]

Prints the report for the last H hours (default 12) and exits 1 when a target is missed (an ALERT
line says which). --append adds one tab-separated line to FILE (a trend log the user can read).
--slow N lists the N slowest gates of the window with what they ran.

The orchestrator runs it at every wake on a chain result and before every self-reset, quotes the
ALERT lines in docs/S19_DECISIONS.md and acts on them before it starts new work (SKILL.md).

Targets (Frank, 2026-11-16: "not wasting time with unnecessary tests remains a priority"):
  SELECTED_SHARE   step gates that ran a selection, not the full suite
  SELECTED_SECONDS median tests-tier time of a selected gate
  SPEEDUP          median selected tests-tier time over median full-suite time
  WAIT_MINUTES     median time a job waits in the queue before its gate starts
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

SELECTED_SHARE = 0.75
SELECTED_SECONDS = 300.0
SPEEDUP = 0.4
WAIT_MINUTES = 15.0

IMPACT = re.compile(
    r"TEST-IMPACT (PASS|FAIL[^:]*?) \S+: selected (\S+), fallback (yes|no), (.*?), "
    r"pytest calls \d+, wall (\d+)s"
)
FULL = re.compile(r"^full suite: (.*)$", re.M)
STAMP = re.compile(r"^(\d{8}T\d{6})-(.+)$")


def common_dir() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=Path(__file__).resolve().parent,
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(out.stdout.strip())


def reason_kind(reason: str) -> str:
    for needle, kind in (
        ("--full", "merge-check"),
        ("new or deleted file", "new or deleted file"),
        ("import-time code changed", "import-time code"),
        ("import or collection time", "collection-time code"),
        ("not an ancestor", "lane does not contain the map base"),
        ("no map at", "no map"),
        ("is not of base", "map not of base"),
        ("never seen", "file unknown to the map"),
        ("conftest", "conftest or test support"),
        ("support module", "conftest or test support"),
    ):
        if needle in reason:
            return kind
    return reason[-50:]


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def show(value: float | None, unit: str = "s") -> str:
    return "n/a" if value is None else f"{value:.0f} {unit}"


def parse_time(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def gates(directory: Path, since: datetime) -> list[dict]:
    found = []
    for report in sorted(directory.glob("*.json")):
        match = STAMP.match(report.stem)
        if match is None:
            continue
        # gate.sh stamps with local time; the file's mtime is the gate's end
        ended = datetime.fromtimestamp(report.stat().st_mtime, UTC)
        if ended < since:
            continue
        try:
            data = json.loads(report.read_text())
        except ValueError:
            continue
        tiers = {c["name"]: float(c.get("seconds") or 0.0) for c in data.get("checks", [])}
        log = report.with_name(report.stem + ".tiers.log")
        text = log.read_text(errors="replace") if log.is_file() else ""
        impact = IMPACT.search(text)
        full = FULL.search(text)
        found.append(
            {
                "label": match.group(2),
                "ended": ended,
                "ok": all(c.get("ok") for c in data.get("checks", [])),
                "tests": tiers.get("tests"),
                "other": sum(v for k, v in tiers.items() if k != "tests"),
                "selected": None if impact is None else impact.group(2),
                "fallback": None if impact is None else impact.group(3) == "yes",
                "counts": "" if impact is None else impact.group(4),
                "reason": reason_kind(full.group(1)) if full else "",
            }
        )
    return found


def queue_waits(directory: Path, since: datetime) -> tuple[list[float], float]:
    """Minutes each finished job waited, and the gate-minutes the runner spent in the window."""
    waits, busy = [], 0.0
    for path in directory.glob("*.json"):
        try:
            job = json.loads(path.read_text())
            enqueued, started = parse_time(job["enqueued"]), parse_time(job["started"])
            finished = parse_time(job["finished"])
        except (ValueError, KeyError):
            continue
        if finished < since or "gate_rc" not in job:
            continue
        waits.append((started - enqueued).total_seconds() / 60)
        busy += (finished - max(started, since)).total_seconds() / 60
    return waits, busy


def steps(log: Path, since: datetime) -> tuple[Counter, float]:
    results: Counter = Counter()
    debt = 0.0
    if not log.is_file():
        return results, debt
    for line in log.read_text().splitlines():
        try:
            row = json.loads(line)
            when = parse_time(row["time"])
        except (ValueError, KeyError):
            continue
        if when < since:
            continue
        results[row["result"]] += 1
        if row["result"] == "accepted" and row["class"] == "refactor":
            debt += row["debt_before"] - row["debt_after"]
    return results, debt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--hours", type=float, default=12.0)
    parser.add_argument("--append", type=Path)
    parser.add_argument("--slow", type=int, default=0)
    a = parser.parse_args(argv)
    common = common_dir()
    now = datetime.now(UTC)
    since = now - timedelta(hours=a.hours)
    found = gates(common / "codehealth" / "runs" / "s19-gates", since)
    ran = [g for g in found if g["fallback"] is not None and g["tests"]]
    merge = [g for g in ran if g["reason"] == "merge-check"]
    step = [g for g in ran if g["reason"] != "merge-check"]
    selected = [g for g in step if not g["fallback"]]
    full = [g for g in step if g["fallback"]]
    waits, busy = queue_waits(common / "codehealth" / "queue" / "done", since)
    results, debt = steps(common / "codehealth" / "runs" / "s19.jsonl", since)

    share = len(selected) / len(step) if step else None
    sel_s = median([g["tests"] for g in selected])
    full_s = median([g["tests"] for g in full + merge])
    other_s = median([g["other"] for g in ran])
    wait_m = median(waits)
    ratio = sel_s / full_s if sel_s and full_s else None
    attempts = sum(results.values())
    accepted = sum(n for kind, n in results.items() if kind.startswith("accepted"))

    stamp = now.astimezone().strftime("%Y-%m-%d %H:%M")
    print(f"S19 GATE REPORT, last {a.hours:g} h to {stamp}")
    print(
        f"gates {len(ran)}: step {len(step)} (selected {len(selected)}, full suite {len(full)}), "
        f"merge-check {len(merge)}; failed {sum(1 for g in ran if not g['ok'])}"
    )
    reasons = Counter(g["reason"] for g in full)
    if reasons:
        print(
            "full-suite causes: " + "; ".join(f"{n} {kind}" for kind, n in reasons.most_common(5))
        )
    print(
        f"tests tier, median: selected {show(sel_s)}, full suite {show(full_s)}; "
        f"other tiers {show(other_s)}"
    )
    print(
        f"queue: {len(waits)} jobs, wait median {show(wait_m, 'min')}, "
        f"max {show(max(waits) if waits else None, 'min')}; gate time {busy / 60:.1f} h of "
        f"{a.hours:g} h (2 slots: {busy / 60 / a.hours / 2:.0%} busy)"
    )
    print(
        f"steps: {attempts} attempts, {accepted} accepted, debt removed {debt:.1f}; "
        f"{attempts / a.hours:.1f} attempts/h"
    )
    alerts = []
    if share is not None and share < SELECTED_SHARE:
        alerts.append(f"selected share {share:.0%} < {SELECTED_SHARE:.0%} of step gates")
    if sel_s is not None and sel_s > SELECTED_SECONDS:
        alerts.append(f"selected gates take {sel_s:.0f} s > {SELECTED_SECONDS:.0f} s (tests tier)")
    if ratio is not None and ratio > SPEEDUP:
        alerts.append(f"selected/full time ratio {ratio:.2f} > {SPEEDUP}: selection saves little")
    if wait_m is not None and wait_m > WAIT_MINUTES:
        alerts.append(f"queue wait median {wait_m:.0f} min > {WAIT_MINUTES:.0f} min")
    for alert in alerts:
        print(f"ALERT {alert}")
    if not alerts:
        print("OK all targets met" if ran else "no gate in the window")
    if a.slow:
        print(f"slowest {a.slow}:")
        for g in sorted(ran, key=lambda g: -g["tests"])[: a.slow]:
            what = g["reason"] or f"selected {g['selected']} files"
            print(f"  {g['tests']:5.0f} s  {g['label'][:34]:34s} {what}; {g['counts']}")
    if a.append:
        fields = [
            stamp,
            f"{a.hours:g}",
            str(len(step)),
            str(len(selected)),
            "" if sel_s is None else f"{sel_s:.0f}",
            "" if full_s is None else f"{full_s:.0f}",
            "" if wait_m is None else f"{wait_m:.0f}",
            str(attempts),
            str(accepted),
            f"{debt:.1f}",
            str(len(alerts)),
        ]
        new = not a.append.exists()
        with a.append.open("a") as handle:
            if new:
                handle.write(
                    "time\thours\tstep_gates\tselected\tselected_s\tfull_s\twait_min\t"
                    "attempts\taccepted\tdebt_removed\talerts\n"
                )
            handle.write("\t".join(fields) + "\n")
    return 1 if alerts else 0


if __name__ == "__main__":
    sys.exit(main())
