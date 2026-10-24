"""S03 WO-S03-3b: merge DWSIM's top-up qualification into the standing records (spec §17.8, §17.10).

The tool script runs the eight re-qualified and new cases into a separate directory (`--out`), so it
never rewrites a standing record. This script then
- checks that the eleven standing `results/dwsim-<case>.json` files are byte-identical to their
  versions at the earlier qualification commit (read with `git show`);
- copies the eight top-up records into `results/`;
- rewrites `qualification/dwsim.json`: the eleven standing per-case entries verbatim, each with
  `"from_commit"`, the eight top-up entries, and the selection summary recomputed over all cases.

It reads only DWSIM's own records (the earlier qualification file at that commit and the top-up
output) and the case list of `s03_cases.json`; no value of another tool or of this project's solver.

    python spikes/references/s03_dwsim_topup_merge.py TOPUP_DIR [--out benchmarks/s03/references]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
EARLIER_COMMIT = "95870140"
REL = "benchmarks/s03/references"
# §17.8: the records that stand, and the cases the top-up qualifies.
STANDING = ("RC1", "RC1-RR", "RC1-z", "PC-L", "RC2", "RC2-RR", "RC2-B", "RC2-z", "RC5", "RC1-BR",
            "PC-P")
TOP_UP = ("RC3", "RC3-Q", "RC3-z", "RC4", "RC4-D", "RC4-z", "RC6", "RC7")


def git_show(path: str) -> bytes:
    try:
        return subprocess.run(["git", "show", f"{EARLIER_COMMIT}:{path}"], cwd=REPO, check=True,
                              capture_output=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"refused: needs the git history of {EARLIER_COMMIT} ({exc})") from exc


def passing_pairs(entry: dict[str, Any]) -> set[tuple[float, str]]:
    return {(float(a["tolerance"]), a["method"]) for a in entry["attempts"] if a.get("passes")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("topup", type=Path)
    parser.add_argument("--out", type=Path, default=REPO / REL)
    args = parser.parse_args()
    out, topup = args.out.resolve(), args.topup.resolve()

    earlier = json.loads(git_show(f"{REL}/qualification/dwsim.json"))
    new = json.loads((topup / "qualification" / "dwsim.json").read_text(encoding="utf-8"))
    assert set(new["cases"]) == set(TOP_UP), sorted(new["cases"])
    assert set(STANDING) <= set(earlier["cases"]), sorted(earlier["cases"])
    for cid in STANDING:
        path = out / "results" / f"dwsim-{cid}.json"
        if path.read_bytes() != git_show(f"{REL}/results/dwsim-{cid}.json"):
            raise SystemExit(f"standing record changed: {path}")
    for cid in TOP_UP:
        shutil.copyfile(topup / "results" / f"dwsim-{cid}.json",
                        out / "results" / f"dwsim-{cid}.json")

    order = list(json.loads((REPO / "docs/derivations/scripts/s03_cases.json").read_text(
        encoding="utf-8"))["cases"])
    assert set(order) == set(STANDING) | set(TOP_UP), order
    cases: dict[str, Any] = {}
    per_case: dict[str, Any] = {}
    for cid in order:
        if cid in STANDING:
            cases[cid] = {**earlier["cases"][cid], "from_commit": EARLIER_COMMIT,
                          "run": "WO-S03-3", "ladder": "column_method_order"}
            sel = earlier["selection"]["per_case"][cid]
            per_case[cid] = sel and {**sel, "ladder": "column_method_order",
                                     "from_commit": EARLIER_COMMIT}
        else:
            cases[cid] = {**new["cases"][cid], "run": "WO-S03-3b (top-up)"}
            sel = new["selection"]["per_case"][cid]
            per_case[cid] = sel and {**sel, "ladder": "column_method_order_amendment_1"}
    # §5.2's uniform setting over every case: a (tolerance, method) pair that passed for all.
    common = set.intersection(*(passing_pairs(cases[cid]) for cid in order))
    uniform = sorted(common)[0] if common else None
    not_available = [cid for cid in order if per_case[cid] is None]
    selection = {
        "uniform_pair": uniform and {"tolerance": uniform[0], "method": uniform[1]},
        "uniform_note": ("no (tolerance, method) pair passes rules 2-2d for every case; cases "
                         f"passing at no position: {', '.join(not_available)}; each case takes its "
                         "own first passing position (spec §5.2, §17.2)") if uniform is None
        else "a pair passes for every case",
        "rung_index_note": ("rung_index counts positions within a level of the case's ladder: "
                            "column_method_order (3 methods per tolerance) for the standing "
                            "entries, column_method_order_amendment_1 (2 per tolerance) for the "
                            "top-up entries"),
        "per_case": per_case,
    }
    keep = ("tool", "versions", "environment_fingerprint", "input_file", "settings",
            "sign_conversion", "wall_time_total_s")
    merged = {
        **{k: new[k] for k in keep},
        "qualification_runs": {
            "WO-S03-3": {"commit": EARLIER_COMMIT, "cases": list(STANDING),
                         **{k: earlier[k] for k in keep}},
            "WO-S03-3b (top-up)": {"commit": "5474531f",  # the commit that added the records
                                   "cases": list(TOP_UP)},
        },
        "selection": selection,
        "cases": cases,
    }
    path = out / "qualification" / "dwsim.json"
    path.write_text(json.dumps(merged, indent=1) + "\n", encoding="utf-8")
    n_ok = sum(1 for cid in order if per_case[cid] is not None)
    print(f"merged: {n_ok}/{len(order)} cases available; uniform pair {uniform}; "
          f"not available: {', '.join(not_available)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
