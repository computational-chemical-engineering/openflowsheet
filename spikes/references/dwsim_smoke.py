"""T06 environment check for the DWSIM reference: one of DWSIM's own samples, run headless.

Loads `samples/Cavett's Problem.dwxmz`, shipped in the DWSIM 9.0.5 Linux package (a classic
recycle benchmark: flash vessels, mixers, valves, compressors and three recycle blocks), solves
it through the GUI-less `Automation3` API with no display, and reports whether every object
calculated. It proves only that `.venv-dwsim` starts .NET, loads DWSIM, reads a flowsheet file
and runs DWSIM's sequential-modular solver on this host. Nothing is compared with this project;
the numbers printed are an environment check, not reference values.

Run from the repository root, after `scripts/build-reference-envs.sh`:

    .venv-dwsim/bin/python spikes/references/dwsim_smoke.py

Not part of `scripts/check.sh`: the gate must not depend on external tools.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import dwsim_runtime

SAMPLE = "Cavett's Problem.dwxmz"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env", type=Path, default=dwsim_runtime.DEFAULT_ENV)
    args = parser.parse_args()
    env_dir = args.env.resolve()

    t0 = time.perf_counter()
    automation = dwsim_runtime.start(env_dir)
    t_start = time.perf_counter() - t0

    sample = env_dir / "dwsim" / "samples" / SAMPLE
    t1 = time.perf_counter()
    flowsheet = automation.LoadFlowsheet(str(sample))
    t_load = time.perf_counter() - t1
    t2 = time.perf_counter()
    errors = automation.CalculateFlowsheet4(flowsheet)
    t_calc = time.perf_counter() - t2

    objects = {}
    for obj in flowsheet.SimulationObjects.Values:
        objects[str(obj.GraphicObject.Tag)] = {
            "type": obj.GetType().Name,
            "calculated": bool(obj.Calculated),
        }
    by_type: dict[str, int] = {}
    for rec in objects.values():
        by_type[rec["type"]] = by_type.get(rec["type"], 0) + 1
    error_messages = [str(e.Message) for e in errors] if errors is not None else []
    all_calculated = all(rec["calculated"] for rec in objects.values())

    report = {
        "check": "dwsim-sample-cavett",
        "dwsim_version": str(automation.GetVersion()),
        "sample": SAMPLE,
        "display": os.environ.get("DISPLAY"),
        "object_counts": dict(sorted(by_type.items())),
        "all_objects_calculated": all_calculated,
        "solver_errors": error_messages,
        "seconds": {
            "start_runtime": round(t_start, 2),
            "load": round(t_load, 2),
            "calculate": round(t_calc, 2),
        },
    }
    print(json.dumps(report, indent=2))
    ok = all_calculated and not error_messages
    print("SMOKE", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
