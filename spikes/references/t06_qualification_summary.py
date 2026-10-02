"""T06 M6: summarize the blind qualification records — flags, self-checks and hashes only.

Reads the `<tool>-<fixture>.json` records written by `t06_qualify_idaes.py` and
`t06_qualify_dwsim.py` and prints, per (tool, fixture): accepted, converged, rule 2's worst
component residual and verdict, IDAES's rule 2b (the SmoothVLE shift of the equilibrium
temperature, a tool-internal quantity), the further tool-internal self-checks, wall time,
adjustments, the
SHA-256 of the record file, and the SHA-256 of its canonical content without the wall times (the
part a rerun must reproduce exactly). It prints **no** quantity a comparison would use (no flow,
temperature, duty or work), so reading its output keeps the qualification blind (spec §9.6).

    python spikes/references/t06_qualification_summary.py <dir> [--markdown]

Stdlib only. Not part of `scripts/check.sh`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import t06_fixtures as fx

TOOLS = ("dwsim", "idaes")


def fmt(x: Any) -> str:
    if isinstance(x, float):
        return f"{x:.1e}"
    return str(x)


def without_wall_times(x: Any) -> Any:
    """The record with every ``wall_time*`` key removed: what a rerun must reproduce exactly."""
    if isinstance(x, dict):
        return {k: without_wall_times(v) for k, v in x.items() if not k.startswith("wall_time")}
    if isinstance(x, list):
        return [without_wall_times(v) for v in x]
    return x


def content_sha256(rec: dict[str, Any]) -> str:
    canonical = json.dumps(without_wall_times(rec), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def row(tool: str, rec: dict[str, Any], sha: str) -> dict[str, str]:
    if "not_applicable" in rec:
        return {
            "tool": tool,
            "fixture": rec["fixture"],
            "other": "not applicable",
            "sha": sha,
            "content_sha": content_sha256(rec),
        }
    sc = rec.get("self_check", {})
    r2 = sc.get("rule2_component_balance", {})
    extra = []
    if "rule2b_smooth_vle" in sc:
        r2b = sc["rule2b_smooth_vle"]
        extra.append(
            f"rule 2b SmoothVLE shift {fmt(r2b['max_shift_K'])} K, eps as registered "
            f"{r2b['eps_as_registered_on_every_block']} {'PASS' if r2b['passes'] else 'FAIL'}"
        )
    if "constraint_residuals" in sc:
        extra.append(
            f"max constraint violation {fmt(sc['constraint_residuals']['max_abs_violation'])}"
        )
    if "energy_balance" in sc:
        extra.append(
            f"energy residual/largest term {fmt(sc['energy_balance']['relative_to_largest_term'])}"
        )
    if sc.get("phase_equilibrium_relative"):
        worst = max(sc["phase_equilibrium_relative"].values())
        extra.append(f"max VLE residual/P {fmt(worst)}")
    if "ipopt" in rec:
        ip = rec["ipopt"]
        extra.append(
            f"Ipopt {ip.get('exit')}, {ip.get('iterations')} it, {ip.get('linear_solver')}"
        )
    rec_unit = rec.get("raw_output", {}).get("units", {}).get("REC")
    if rec_unit:
        extra.append(
            f"Recycle converged={rec_unit['Converged']} in {rec_unit['IterationsTaken']} it"
        )
    return {
        "tool": tool,
        "fixture": rec["fixture"],
        "fingerprint": str(rec["environment_fingerprint"]["matches"]),
        "accepted": str(rec.get("accepted")),
        "converged": str(rec.get("converged")),
        "rule2": f"{fmt(r2.get('max_abs_mol_per_s'))} {'PASS' if r2.get('passes') else 'FAIL'}",
        "other": "; ".join(extra),
        "time": f"{rec.get('wall_time_total_s', float('nan')):.2f}",
        "adjusted": "yes" if rec.get("adjustments") else "no",
        "error": rec.get("error", ""),
        "sha": sha,
        "content_sha": content_sha256(rec),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dir", type=Path)
    parser.add_argument("--markdown", action="store_true")
    args = parser.parse_args()
    rows = []
    missing = []
    for tool in TOOLS:
        for fid in fx.FIXTURES:
            path = args.dir / f"{tool}-{fid}.json"
            if not path.is_file():
                missing.append(path.name)
                continue
            data = path.read_bytes()
            rows.append(row(tool, json.loads(data), hashlib.sha256(data).hexdigest()))
    cols = ["tool", "fixture", "fingerprint", "accepted", "converged", "rule2", "time", "adjusted"]
    cols += ["other", "error"]
    if args.markdown:
        print("| " + " | ".join(cols) + " |")
        print("|" + " --- |" * len(cols))
        for r in rows:
            print("| " + " | ".join(r.get(c, "") for c in cols) + " |")
        print()
        print("| record | SHA-256 of the file | SHA-256 of its content without wall times |")
        print("| --- | --- | --- |")
        for r in rows:
            name = f"{r['tool']}-{r['fixture']}.json"
            print(f"| `{name}` | `{r['sha']}` | `{r['content_sha']}` |")
    else:
        for r in rows:
            print("  ".join(f"{c}={r.get(c, '')}" for c in cols if r.get(c, "") != ""))
    for name in missing:
        print(f"MISSING {name}", file=sys.stderr)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
