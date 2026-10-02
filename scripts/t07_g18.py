"""T07 G18's job-overhead leg and G5's two timed legs under the process executor. T07 W8b.

The measured body is `docs/t07-measurements.md` Appendix J (`w4c_g18.py`, W4c.2 and W4c.3),
unchanged: SYN-001-nominal, `max_workers = 1`, `grace_s = 0.5`, one warm-up job not counted; then

- 20 jobs one after another: overhead = (`ended_at` − the wall clock before `submit_job`) − the
  run manifest's `elapsed_seconds` (G18: median ≤ 1.0 s);
- 5 frozen `Application.solve` round trips (recorded, not gated);
- 5 cooperative cancels at the pause hook (stage `solve`): `cancel_job` return → ended
  (G5: ≤ 2 s each);
- 5 forced cancels under the block hook: `cancel_job` return → ended (G5: ≤ `grace_s` + 1 s each).

It prints one JSON document on stdout. Only `openflowsheet` is imported at module level, as a
server's entry point does: a spawned worker re-imports the main module, so the test helpers and the
corpus are imported inside `main`.

Usage:
    OMP_NUM_THREADS=1 PYTHONPATH=src:. python scripts/t07_g18.py SCRATCH_DIR
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from openflowsheet.application.jobs.executor import ProcessExecutor
from openflowsheet.application.jobs.worker import BLOCK_VARIABLE, PAUSE_AT_STAGE_VARIABLE
from openflowsheet.application.local import LocalApplication

ROOT = Path(__file__).resolve().parent.parent
#: Appendix J's counts and settings.
JOBS = 20
ROUND_TRIPS = 5
CANCELS = 5
GRACE_S = 0.5


def _summary(values: list[float]) -> dict[str, Any]:
    return {
        "n": len(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def _ending(job: Any) -> list[Any]:
    """`[status, reason, interruption]` of an ended job (§5.5 `job_ending`)."""
    ending = job.ending
    if ending is None:
        return [job.status, None, None]
    return [ending.status, ending.reason, ending.interruption]


def measure(scratch: Path) -> dict[str, Any]:
    sys.path.insert(0, str(ROOT / "tests"))
    from t07_corpus import CORPUS
    from t07_jobs_support import commit
    from t07_process_support import (
        paused_pid,
        set_executor,
        solve_request,
        wait_ended,
        wait_until,
    )

    root = Path(tempfile.mkdtemp(dir=scratch))
    LocalApplication.create(root / "p").close()
    set_executor(root / "p", max_workers=1, grace_s=GRACE_S)
    app = LocalApplication.open(root / "p", executor=ProcessExecutor(test_hooks=True))
    try:
        revision_id = commit(app, CORPUS["SYN-001-nominal"]())
        # One warm-up job (the page cache, the resource tracker), not counted.
        wait_ended(app, app.submit_job(solve_request("warm", revision_id)).job.job_id)
        overheads: list[float] = []
        totals: list[float] = []
        solves: list[float] = []
        statuses: list[str] = []
        for index in range(JOBS):
            before = time.time()
            job_id = app.submit_job(solve_request(f"g18-{index}", revision_id)).job.job_id
            job = wait_ended(app, job_id)
            statuses.append(job.status)
            assert job.ended_at is not None
            ended = datetime.fromisoformat(job.ended_at.replace("Z", "+00:00")).timestamp()
            (bundle,) = [o for o in job.outputs if o.kind == "replay_bundle"]
            row = app.store.artifact(bundle.artifact_id)
            assert row is not None
            manifest = json.loads((app.files_root / row.relpath / "run-manifest.json").read_bytes())
            solves.append(manifest["elapsed_seconds"])
            totals.append(ended - before)
            overheads.append(ended - before - manifest["elapsed_seconds"])
        rounds: list[float] = []
        for _ in range(ROUND_TRIPS):
            before = time.perf_counter()
            app.solve(revision_id, "default")
            rounds.append(time.perf_counter() - before)
        cooperative: list[float] = []
        cooperative_endings: list[list[Any]] = []
        os.environ[PAUSE_AT_STAGE_VARIABLE] = "solve"
        try:
            for index in range(CANCELS):
                job = app.submit_job(solve_request(f"coop-{index}", revision_id)).job
                paused_pid(app, job.job_id)
                app.cancel_job(job.job_id)
                start = time.monotonic()
                job = wait_ended(app, job.job_id)
                cooperative.append(time.monotonic() - start)
                cooperative_endings.append(_ending(job))
        finally:
            del os.environ[PAUSE_AT_STAGE_VARIABLE]
        forced: list[float] = []
        forced_endings: list[list[Any]] = []
        os.environ[BLOCK_VARIABLE] = "1"
        try:
            for index in range(CANCELS):
                job = app.submit_job(solve_request(f"forced-{index}", revision_id)).job
                job_id = job.job_id
                wait_until(
                    lambda: app.get_job(job_id).status == "running",  # noqa: B023 - read now
                    "running",
                )
                app.cancel_job(job_id)
                start = time.monotonic()
                job = wait_ended(app, job_id)
                forced.append(time.monotonic() - start)
                forced_endings.append(_ending(job))
        finally:
            del os.environ[BLOCK_VARIABLE]
    finally:
        app.close()
    return {
        "method": "docs/t07-measurements.md Appendix J (w4c_g18.py), unchanged",
        "case": "SYN-001-nominal",
        "max_workers": 1,
        "grace_s": GRACE_S,
        "omp_num_threads": os.environ.get("OMP_NUM_THREADS"),
        "g18_job_overhead_s": _summary(overheads),
        "submit_to_ended_s": _summary(totals),
        "solve_elapsed_s": _summary(solves),
        "job_statuses": sorted(set(statuses)),
        "application_solve_round_trip_s": _summary(rounds),
        "g5_cooperative_cancel_to_ended_s": {**_summary(cooperative), "values": cooperative},
        "g5_cooperative_endings": cooperative_endings,
        "g5_forced_cancel_to_ended_s": {**_summary(forced), "values": forced},
        "g5_forced_endings": forced_endings,
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    scratch = Path(sys.argv[1])
    scratch.mkdir(parents=True, exist_ok=True)
    print(json.dumps(measure(scratch), indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
