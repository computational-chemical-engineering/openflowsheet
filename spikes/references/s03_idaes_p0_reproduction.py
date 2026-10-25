"""S03 WO-S03-2b step 5: does each new P0 attempt reproduce the IDAES record at 6d9486a0 exactly?

Authority: `docs/derivations/S03-spec.md` §18.8 step 5 (Amendment 2). For every case the standing
IDAES records ran, and every level such a record attempted, the new P0 attempt at that level must
reproduce the old attempt exactly: termination, iteration count and every rule value; for an attempt
that converged, the registered quantities and the accuracy rerun bit for bit. Compared here, by
exact equality of the JSON values: the attempt summary (wall times excepted), the final solve's
Ipopt record, termination, degrees of freedom and initialization events, the rule values, the raw
output (every Pyomo variable, every SmoothVLE eps and every constraint residual), the registered
quantities, and the rerun's convergence, Ipopt record, quantities and movement.

A level the old record attempted but the new run did not reach (an earlier level passed under the
ladder, so §18.1's search stopped there) has no new P0 attempt. With `--run-unreached` the P0
attempt at that level is run here, by the tool script's own `position_attempt`, for this check only:
it is not an attempt of the qualification, is written to no tool record, and cannot change a
selection (B2b-6). That mode needs IDAES's environment.

It reads IDAES records only: the old ones with `git show 6d9486a0:...`, the new ones from DIR. With
`--write` it stores the outcome as `p0_reproduction` in DIR/qualification/idaes.json. Prints one
line per difference and one summary line; exits 1 on any difference.

    .venv-idaes/bin/python spikes/references/s03_idaes_p0_reproduction.py [DIR] [--write]
        [--run-unreached]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
OLD_COMMIT = "6d9486a0"
RECORDS = "benchmarks/s03/references"


def old_record(cid: str) -> dict[str, Any]:
    text = subprocess.run(
        ["git", "show", f"{OLD_COMMIT}:{RECORDS}/results/idaes-{cid}.json"],
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return json.loads(text)


def old_case_ids() -> list[str]:
    text = subprocess.run(
        ["git", "show", f"{OLD_COMMIT}:{RECORDS}/qualification/idaes.json"],
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    cases = json.loads(text)["cases"]
    return [cid for cid, c in cases.items() if "not_applicable" not in c]


def attempts_by_level(rec: dict[str, Any]) -> dict[str, tuple[dict[str, Any], Any]]:
    """level -> (summary, full record or None) of the attempt to compare (P0 in a new record)."""
    out: dict[str, tuple[dict[str, Any], Any]] = {}
    levels = rec.get("levels") or rec.get("levels_before") or {}
    for summ in rec["attempts"]:
        level = summ["level"]
        if summ.get("position", "P0") != "P0":
            continue
        entry = levels.get(level, {})
        if "positions" in entry:  # the WO-S03-2b layout
            pos = entry["positions"]["P0"]
            full = pos.get("full")
            if isinstance(full, str):  # the selected attempt, held at the record's top level
                full = {
                    "record": rec["solve"],
                    "raw": rec["raw_output"],
                    "rules": rec["rule_values"],
                    "quantities": rec["registered_quantities"],
                    "rerun": rec["accuracy_rerun"],
                }
            out[level] = (pos["summary"], full)
        elif rec.get("available") and rec.get("level") == level:  # the 6d9486a0 layout
            out[level] = (
                summ,
                {
                    "record": rec["solve"],
                    "raw": rec["raw_output"],
                    "rules": rec["rule_values"],
                    "quantities": rec["registered_quantities"],
                    "rerun": rec["accuracy_rerun"],
                },
            )
        else:
            out[level] = (summ, entry.get("failed_full_record"))
    return out


def fingerprint(summ: dict[str, Any], full: Any) -> dict[str, Any]:
    fp: dict[str, Any] = {
        "summary": {
            k: v
            for k, v in summ.items()
            if not k.startswith("wall_time") and k not in ("traceback", "position", "solves", "run")
        }
    }
    if full:
        r = full["record"]
        fp.update(
            termination=r.get("termination"),
            converged=r.get("converged"),
            ipopt=r.get("ipopt"),
            degrees_of_freedom=r.get("degrees_of_freedom"),
            initialization_events=r.get("initialization_events"),
            rules=full.get("rules"),
            raw=full.get("raw"),
            quantities=full.get("quantities"),
        )
        if "rerun" in full:
            rr = full["rerun"]
            fp["rerun"] = {
                k: rr.get(k)
                for k in ("converged", "termination", "ipopt", "quantities", "movement", "passes")
            }
    return fp


def diff_keys(a: Any, b: Any, path: str = "") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{path}/{k} (only in {'old' if k in a else 'new'})")
            else:
                out.extend(diff_keys(a[k], b[k], f"{path}/{k}"))
        return out
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [
            d
            for i, (x, y) in enumerate(zip(a, b, strict=True))
            for d in diff_keys(x, y, f"{path}[{i}]")
        ]
    return [] if a == b and type(a) is type(b) else [path or "/"]


def run_unreached_p0(cid: str, level: str, log_dir: Path) -> tuple[dict[str, Any], Any]:
    """The P0 attempt at a level the new run did not reach, by the tool script's own code."""
    import logging
    import os

    os.environ.setdefault("IDAES_DATA", str(REPO / ".venv-idaes" / "idaes-data"))
    import idaes
    import s03_qualify_idaes as q
    import t06_fixtures as fx

    logging.getLogger("idaes").setLevel(logging.WARNING)
    idaes.cfg.ipopt.options.linear_solver = fx.IDAES_SOLVER_OPTIONS["linear_solver"]
    data = q.load_cases()
    case = data["cases"][cid]
    lad = q.ladder(data, {}, {})  # P0 uses no warm-start option
    log_dir.mkdir(parents=True, exist_ok=True)
    return q.position_attempt(data, cid, case, q.realization(case, level), lad, "P0", log_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dir", nargs="?", type=Path, default=REPO / RECORDS)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--run-unreached", action="store_true")
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=REPO / "evidence" / "S03" / "artifacts" / "s03-qualification" / "idaes-p0-check",
    )
    args = parser.parse_args()
    results: dict[str, Any] = {}
    n_attempts = n_equal = 0
    for cid in old_case_ids():
        old = attempts_by_level(old_record(cid))
        new_path = args.dir / "results" / f"idaes-{cid}.json"
        new = attempts_by_level(json.loads(new_path.read_text(encoding="utf-8")))
        results[cid] = {}
        for level, (osumm, ofull) in old.items():
            n_attempts += 1
            source = "the new record's P0 attempt"
            if level in new:
                diffs = diff_keys(fingerprint(osumm, ofull), fingerprint(*new[level]))
            elif args.run_unreached:
                source = (
                    "run by this script for the check only: the new run did not reach this "
                    "level (an earlier level passed); not an attempt of the qualification"
                )
                diffs = diff_keys(
                    fingerprint(osumm, ofull),
                    fingerprint(*run_unreached_p0(cid, level, args.log_dir)),
                )
            else:
                diffs = ["no new P0 attempt at this level (not reached; see --run-unreached)"]
            n_equal += not diffs
            results[cid][level] = {
                "reproduced": not diffs,
                "differences": diffs[:50],
                "new_side": source,
                "old_termination": osumm.get("termination"),
                "old_iterations": osumm.get("ipopt_iterations"),
                "converged_with_quantities": bool(ofull and "quantities" in ofull),
            }
            for d in diffs[:10]:
                print(f"p0 {cid} {level}: differs at {d}")
    ok = n_equal == n_attempts
    if args.write:
        qpath = args.dir / "qualification" / "idaes.json"
        qual = json.loads(qpath.read_text(encoding="utf-8"))
        qual["p0_reproduction"] = {
            "spec": "docs/derivations/S03-spec.md §18.8 step 5",
            "old_records": f"{OLD_COMMIT}:{RECORDS}",
            "script": "spikes/references/s03_idaes_p0_reproduction.py",
            "compared": "attempt summary (wall times excepted), final solve's Ipopt record, "
            "termination, degrees of freedom, initialization events, rule values, raw "
            "output, registered quantities, accuracy rerun (convergence, Ipopt record, "
            "quantities, movement); exact equality of the JSON values",
            "attempts_compared": n_attempts,
            "attempts_reproduced": n_equal,
            "all_reproduced": ok,
            "cases": results,
        }
        qpath.write_text(json.dumps(qual, indent=1) + "\n", encoding="utf-8")
    print(
        f"p0 SUMMARY: {n_equal}/{n_attempts} old attempts reproduced exactly "
        f"({'PASS' if ok else 'FAIL'})"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
