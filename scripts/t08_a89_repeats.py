"""T08.A15 (W1.6): T06 A89's case — THM-09 start 2 under `T06-revision-v2` — repeated.

T08 release spec §6.1: A89's exact refinement count failed once on aarch64 and passed on re-run
(`d1c4ee5`, CI 36440983702). §9 T08.A15 asks for the case repeated 20 times on the aarch64 class
and once on `ref-x86-64`, each repetition recording its outcome, whether it is `VERIFIED`, S3's
worst ratio and the refinement count; the design lane then amends A89 (or escalates a defect).

Each repetition runs in a **fresh interpreter**, because the flake was seen between CI runs (that
is, between processes), not inside one. A repetition does exactly what
`tests/test_t06_w18_policy.py::test_a89_thm09_ends_within_a_tenth_of_s3s_allowance` does for start
2: `ensemble.run_start` on the published start, and the refinement count read off the solve trace
as the number of `terminal_refinement(` closing messages. Nothing here judges; the record states
whether each repetition meets A89's registered outcome (`CONVERGED`, `VERIFIED`, ratio ≤ 0.1),
and the count is reported beside it.

    python scripts/t08_a89_repeats.py --label ref-x86-64 --repetitions 1 \
        --out benchmarks/t08/a89/ref-x86-64.json
    python scripts/t08_a89_repeats.py --label ci-aarch64 --repetitions 20 --out <file>   # CI

Exit status 0 iff every repetition meets the registered outcome.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
FORMAT = "t08-a89-repeats-v1"
CASE, START, POLICY = "THM-09", 2, "T06-revision-v2"
#: A89's registered bound on S3's worst ratio: ADR 0018's first-order promise (allowance / 10).
RATIO_BOUND = 0.1
#: The thread variables ADR 0007 D4 pins for an exact run; the CI jobs set them to 1.
THREAD_VARIABLES = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")


def one_repetition() -> dict[str, Any]:
    """Run the case once in this interpreter and return its row."""
    sys.path.insert(0, str(ROOT / "tests"))
    sys.path.insert(0, str(ROOT))
    from t06_ensemble_support import STARTS_FILE, ensemble_cases  # noqa: PLC0415

    from benchmarks.t06 import ensemble  # noqa: PLC0415

    (case,) = [c for c in ensemble_cases() if c.case == CASE]
    assert case.policy.policy_id == POLICY, case.policy.policy_id
    published = json.loads(STARTS_FILE.read_bytes())
    (starts,) = [e for e in published["cases"] if e["case"] == CASE]
    (start,) = [s for s in starts["starts"] if s["start"] == START]

    runs: list[Any] = []
    real = ensemble.execute_plan

    def keeping(**kwargs: Any) -> Any:
        runs.append(real(**kwargs))
        return runs[-1]

    ensemble.execute_plan = keeping  # the same capture the A89 test makes with monkeypatch
    try:
        record = ensemble.run_start(case, start)
    finally:
        ensemble.execute_plan = real
    messages = [
        event.message
        for run in runs
        for event in run.trace.events
        if event.message.startswith("terminal_refinement(")
    ]
    worst = record.get("worst")
    ratio, where = (worst[0], worst[1]) if worst else (None, None)
    certificate = record.get("certificate") or {}
    row = {
        "crash": record["crash"],
        "outcome": record["outcome"],
        "verification": certificate.get("verdict"),
        "s3_worst_ratio": ratio,
        "worst_at": where,
        "refinement_count": len(messages),
        "refinements": messages,
        "classification": ensemble.classify(record),
        "solves": len(runs),
    }
    row["meets_a89_outcome"] = (
        row["crash"] is None
        and row["outcome"] == "CONVERGED"
        and row["verification"] == "VERIFIED"
        and ratio is not None
        and ratio <= RATIO_BOUND
    )
    return row


def _cpu_model() -> str | None:
    try:
        text = Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for key in ("model name", "CPU part"):
        for line in text.splitlines():
            if line.startswith(key):
                return f"{key}: {line.split(':', 1)[1].strip()}"
    return None


def _commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    return completed.stdout.strip() or "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--one", action="store_true", help="one repetition; print its row")
    parser.add_argument("--repetitions", type=int, default=20)
    parser.add_argument("--label", help="the machine class, e.g. ref-x86-64 or ci-aarch64")
    parser.add_argument("--out", type=Path)
    arguments = parser.parse_args()
    if arguments.one:
        print("A89-ROW " + json.dumps(one_repetition(), sort_keys=True))
        return 0
    if not arguments.label or arguments.out is None or arguments.repetitions < 1:
        parser.error("--label, --out and a positive --repetitions are required")

    rows = []
    for repetition in range(1, arguments.repetitions + 1):
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--one"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        lines = [line for line in completed.stdout.splitlines() if line.startswith("A89-ROW ")]
        if completed.returncode != 0 or len(lines) != 1:
            row = {
                "crash": f"exit {completed.returncode}: {completed.stderr.strip()[-500:]}",
                "meets_a89_outcome": False,
            }
        else:
            row = json.loads(lines[0].removeprefix("A89-ROW "))
        row["repetition"] = repetition
        rows.append(row)
        print(
            f"{repetition:2d}: {row.get('outcome')} {row.get('verification')} "
            f"ratio {row.get('s3_worst_ratio')} refinements {row.get('refinement_count')} "
            f"meets {row['meets_a89_outcome']}",
            flush=True,
        )

    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get("refinement_count"))
        counts[key] = counts.get(key, 0) + 1
    record = {
        "format": FORMAT,
        "assertion": "T08.A15",
        "case": CASE,
        "start": START,
        "policy": POLICY,
        "ratio_bound": RATIO_BOUND,
        "label": arguments.label,
        "commit": _commit(),
        "host": {
            "machine": platform.machine(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu": _cpu_model(),
            "threads": {name: os.environ.get(name) for name in THREAD_VARIABLES},
        },
        "repetitions": rows,
        "refinement_counts": dict(sorted(counts.items())),
        "all_meet_a89_outcome": all(row["meets_a89_outcome"] for row in rows),
    }
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    arguments.out.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {arguments.out}: all meet = {record['all_meet_a89_outcome']}, counts {counts}")
    return 0 if record["all_meet_a89_outcome"] else 1


if __name__ == "__main__":
    sys.exit(main())
