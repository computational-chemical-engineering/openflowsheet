"""S08b design-time measurement M2: the 52 registered column and S01 configurations of
`scripts/s08_identity.py` (S08 G1), with the contract as it is and with the design's item rule
(`s08b_probe`'s `fix` mode), in two subprocesses of this checkout. NOT a gate, NOT a test.

    python docs/derivations/scripts/s08b_design/column_records.py OUT

Per configuration: S08 G1's digest (and `stage_a`'s), and a readable record — outcome, cause,
per attempt (signature, outcome, core outcome, iterations, reason) of every region result it
carries, each result's message, and S08's `reentry` (trigger, Stage A, the candidates, the accepted
index). One line is printed: the count and the configurations whose digest moved; both modes'
records of every configuration go to `OUT/records.json`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent


def _attempts(result: Any) -> Any:
    if result is None:
        return None
    return {
        "outcome": result.outcome,
        "message": result.message,
        "attempts": [
            (
                "".join(regime[0] for _, regime in attempt.signature),
                attempt.outcome,
                attempt.solver_outcome,
                attempt.iterations,
                attempt.reason,
            )
            for attempt in result.attempts
        ],
    }


def _record(answer: Any) -> dict[str, Any]:
    from openflowsheet.models.syn001.cascade_solve import CascadeSolution
    from openflowsheet.models.syn001.column_solve import ColumnSolution

    if isinstance(answer, ColumnSolution):
        record: dict[str, Any] = {
            "outcome": answer.outcome,
            "cause": answer.cause,
            "signature": "".join(regime[0] for regime in answer.signature),
            "result": _attempts(answer.result),
            "recovered_from": _attempts(answer.recovered_from),
        }
        reentry = answer.reentry
        if reentry is not None:
            record["reentry"] = {
                "trigger": reentry.trigger,
                "accepted": reentry.accepted,
                "stage_a": {
                    "outcome": reentry.stage_a.outcome,
                    "cause": reentry.stage_a.cause,
                    "result": _attempts(reentry.stage_a.result),
                    "recovered_from": _attempts(reentry.stage_a.recovered_from),
                },
                "candidates": [
                    (c.a, c.c, "".join(r[0] for r in c.signature), c.outcome, c.cause)
                    for c in reentry.candidates
                ],
            }
        return record
    if isinstance(answer, CascadeSolution):
        return {
            "outcome": answer.outcome,
            "cause": answer.cause,
            "signature": "".join(regime[0] for regime in answer.signature),
            "presolve": _attempts(answer.presolve),
            "result": _attempts(answer.result),
            "recovered_from": _attempts(answer.recovered_from),
        }
    return {"type": type(answer).__name__, "outcome": answer.outcome}


def measure(mode: str, out: Path) -> None:
    if mode == "fix":
        os.environ["S08B_MODE"] = "fix"
        import s08b_probe  # noqa: F401  (patches the contract at import)
    import s08_identity as g1
    from test_s01_cascade_wo1 import CASES, REFERENCE, _spec
    from test_s02_column_wo1 import PROVIDER

    from openflowsheet.models.syn001.cascade_solve import CascadeSolution, solve_cascade
    from openflowsheet.models.syn001.column_solve import ColumnSolution, solve_column

    solves = [(name, spec, solve_column) for name, spec in g1.column_configurations().items()]
    solves += [(f"S01.{case}", _spec(REFERENCE["cases"][case]), solve_cascade) for case in CASES]
    found: dict[str, Any] = {}
    for name, spec, solve in solves:
        try:
            answer = solve(spec, PROVIDER)
        except Exception as error:  # a raise is a recorded outcome
            found[name] = {"digest": g1._hash(("raised", type(error).__name__, str(error)))}
            continue
        entry: dict[str, Any] = {"record": _record(answer)}
        if isinstance(answer, ColumnSolution):
            entry["digest"] = g1._hash(g1.column_fields(answer))
            if answer.reentry is not None:
                entry["stage_a"] = g1._hash(g1.stage_a_fields(spec, PROVIDER, answer))
        elif isinstance(answer, CascadeSolution):
            entry["digest"] = g1._hash(g1.cascade_fields(answer))
        else:
            entry["digest"] = g1._hash((type(answer).__name__, answer.outcome))
        found[name] = entry
    out.write_text(json.dumps(found, indent=1, sort_keys=True, default=repr) + "\n")


def _differences(old: Any, new: Any, path: str = "") -> list[tuple[str, Any, Any]]:
    """Every leaf at which two readable records differ, by its path."""
    if isinstance(old, dict) and isinstance(new, dict):
        found: list[tuple[str, Any, Any]] = []
        for key in sorted(set(old) | set(new)):
            found += _differences(old.get(key), new.get(key), f"{path}/{key}")
        return found
    return [] if old == new else [(path, old, new)]


def main() -> int:
    if len(sys.argv) == 4 and sys.argv[1] == "--measure":
        measure(sys.argv[2], Path(sys.argv[3]))
        return 0
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        str(part) for part in (ROOT / "src", ROOT / "tests", ROOT / "scripts", ROOT, HERE)
    )
    running = {
        mode: subprocess.Popen(
            [sys.executable, __file__, "--measure", mode, str(out / f"{mode}.json")],
            cwd=ROOT,
            env=environment,
            stdout=(out / f"{mode}.log").open("wb"),
            stderr=subprocess.STDOUT,
        )
        for mode in ("baseline", "fix")
    }
    for mode, process in running.items():
        if process.wait() != 0:
            print(f"S08B-RECORDS FAIL the {mode} run exited {process.returncode}")
            return 1
    base, fix = (json.loads((out / f"{mode}.json").read_text()) for mode in ("baseline", "fix"))
    moved = sorted(name for name in base if base[name]["digest"] != fix[name]["digest"])
    stage_a = sorted(name for name in base if base[name].get("stage_a") != fix[name].get("stage_a"))
    both = {name: {"baseline": base[name], "fix": fix[name]} for name in sorted(base)}
    (out / "records.json").write_text(json.dumps(both, indent=1, sort_keys=True) + "\n")
    print(f"S08B-RECORDS n={len(base)} moved={moved} stage_a_moved={stage_a}")
    for name in sorted(base):
        for path, old, new in _differences(base[name].get("record"), fix[name].get("record")):
            print(f"  {name} {path}\n    base: {old}\n    fix:  {new}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
