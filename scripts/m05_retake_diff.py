"""M05 WO-10a: a re-take of a committed study record against the record it replaces (R-432,
design note §21.3; build log S70), with `noise_ratio` and `provenance` masked.

- **The record** by G10's comparator (`m05_replay.replay_differences`: every leaf bitwise by
  `float.hex`, except the registered `excluded` timings — the solves' `wall_s`, positive on both
  sides — and the coupling-record digests, compared by shape). Each raw differing leaf is also
  counted by class (timing, digest, other); any "other" leaf is a difference, except
  `artifacts.experiment_store` when the experiments archive differs only in timings (below).
- **The coupling records** by `m05_replay.content_differences` (M02's `excluded` attempt timings
  removed), plus the reactor's own diagnostic timings (`execution.diagnostics.**.wall_s`), which a
  cold re-run measures again; the re-take's coupling files by `persisted_violations`.
- **The sidecars**: ledger, store index and environment bytewise; REAL's experiments archive
  (`<stem>.experiments.json`) file by file, request and result files bytewise, attempt records
  leaf by leaf with their timings (`execution.timing.*`, `execution.diagnostics.**.wall_s`)
  removed.

The committed side is read from a directory holding the replaced files, for example
`git archive <rev> benchmarks/m05/records | tar -x -C <dir>`. Prints one summary line, then each
noise ratio (old, new, and new/old, which is η·s_k/√2) and each difference; exit 0 iff none.

    python scripts/m05_retake_diff.py <committed-stem> <retake-stem>
"""

from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tests" / "support"))
import m05_replay as replay  # noqa: E402

#: A cold re-run measures these again: M02's attempt timings and the reactor's diagnostic timings.
TIMING = re.compile(r"(.*\.execution\.timing\.[a-z_]+|.*\.execution\.diagnostics\..*\.wall_s)")


def _masked(path: Path) -> tuple[dict[str, Any], list[tuple[str, str, Any]]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    document.pop("provenance", None)
    ratios = []
    for run in document["runs"]:
        links = (run.get("basis") or {}).get("links") or {}
        for name, link in links.items():
            ratios.append((run["run_id"], name, link.get("noise_ratio")))
            link["noise_ratio"] = "<masked>"
    return document, ratios


def _leaves(a: Any, b: Any, path: str = "") -> list[str]:
    """Paths whose leaves differ (floats by hex), timings removed."""
    return [
        where
        for where, x, y in replay._walk_pair(a, b, path)
        if not replay._same_leaf(x, y) and not TIMING.fullmatch(where)
    ]


def _experiments(old: Path, new: Path) -> tuple[list[str], int]:
    """REAL's experiments archive: (differences, attempt files that differ only in timings)."""
    a = json.loads(old.read_text(encoding="utf-8"))
    b = json.loads(new.read_text(encoding="utf-8"))
    if list(a) != list(b):
        return ["experiments: the file sets differ"], 0
    found: list[str] = []
    timing_only = 0
    for name in a:
        if a[name] == b[name]:
            continue
        if "/attempts/" not in name:
            found.append(f"experiments {name}: bytes differ")
            continue
        lines = _leaves(json.loads(a[name]), json.loads(b[name]), "")
        found += [f"experiments {name}{line}" for line in lines]
        timing_only += not lines
    return found, timing_only


def main(argv: list[str]) -> int:
    old, new = Path(argv[0]), Path(argv[1])
    found: list[str] = []
    a, old_ratios = _masked(old.with_suffix(".json"))
    b, new_ratios = _masked(new.with_suffix(".json"))
    found += [f"record {line}" for line in replay.replay_differences(a, b)]
    classes: collections.Counter[str] = collections.Counter()
    other: list[str] = []
    for path, x, y in replay._walk_pair(a, b, ""):
        if replay._same_leaf(x, y):
            continue
        if any(pattern.fullmatch(path) for pattern in replay.DIGEST_PATHS):
            classes["digest"] += 1
        elif isinstance(x, float) and any(p.fullmatch(path) for p in replay.m05_excluded()):
            classes["timing"] += 1
        else:
            classes["other"] += 1
            other.append(path)
    archive_timing_only = 0
    archive = old.with_suffix(".experiments.json")
    if archive.exists() or new.with_suffix(".experiments.json").exists():
        lines, archive_timing_only = _experiments(archive, new.with_suffix(".experiments.json"))
        found += lines
        if not lines and other == [".artifacts.experiment_store"]:
            found = [line for line in found if ".artifacts.experiment_store" not in line]
            other = []
    found += [f"record raw {path}" for path in other]
    directory = new.with_suffix(".coupling")
    found += [f"re-take integrity {line}" for line in replay.persisted_violations(b, directory)]
    old_files = sorted(p.name for p in old.with_suffix(".coupling").glob("*.json"))
    new_files = sorted(p.name for p in directory.glob("*.json"))
    if old_files != new_files:
        found.append(f"coupling files {old_files} vs {new_files}")
    for name in sorted(set(old_files) & set(new_files)):
        x = json.loads((old.with_suffix(".coupling") / name).read_bytes())
        y = json.loads((directory / name).read_bytes())
        found += [
            f"coupling {name}{line}"
            for line in replay.content_differences(x, y)
            if not TIMING.fullmatch(line.split(":", 1)[0])
        ]
    for suffix in (".ledger.json", ".store.json", ".environment.json"):
        if old.with_suffix(suffix).read_bytes() != new.with_suffix(suffix).read_bytes():
            found.append(f"{suffix}: bytes differ")
    print(
        f"RETAKE-DIFF {'PASS' if not found else 'FAIL'} {old.name}: differences={len(found)} "
        f"record-raw-leaves={dict(classes)} coupling-files={len(new_files)} "
        f"experiments-attempts-timing-only={archive_timing_only}"
    )
    for (run, name, x), (_, _, y) in zip(old_ratios, new_ratios, strict=True):
        factors = None if not (x and y) else [q / p for p, q in zip(x, y, strict=True) if p and q]
        print(f"  noise_ratio {run} {name}: {x} -> {y} (new/old {factors})")
    for line in found:
        print(f"  {line}")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
