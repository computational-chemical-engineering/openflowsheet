"""S10-C R-782, note §8.1 (2026-10-26): one T06 ensemble start on a given source tree, with the
WO-R1 detector (`scripts/s10c_release_detector.py`, observation-only) installed. Prints one line:
OpenBLAS kernel, class, outcome, property calls, attempts, worst ratio, the attempts' closing
outcomes, the event count, and the detector's acting iterations and `_released` calls.

Evidence script (design lane). TREE is an exported tree (`git archive <commit> | tar -x -C TREE`),
for example `f9122cc7` (pre-change, with the detector) and `03ef9e2e` (R-782). HOLDOUT=1 selects
the holdout starts file. Run with the repository's virtual environment:

    OPENBLAS_NUM_THREADS=1 [OPENBLAS_CORETYPE=<kernel>] [HOLDOUT=1] \
        python -I docs/derivations/scripts/s10c_r782_one_start.py TREE THM-09 3
"""

import json
import os
import sys

tree, case_id, start_no = sys.argv[1], sys.argv[2], int(sys.argv[3])
sys.path[:0] = [f"{tree}/src", tree, f"{tree}/scripts", f"{tree}/tests"]
os.chdir(tree)

import s10c_release_detector as detector  # noqa: E402

detector.install()

from t06_ensemble_support import HOLDOUT_FILE, STARTS_FILE, ensemble_cases  # noqa: E402

from benchmarks.t06 import ensemble  # noqa: E402

holdout = os.environ.get("HOLDOUT") == "1"
published = json.loads((HOLDOUT_FILE if holdout else STARTS_FILE).read_bytes())
entry = {e["case"]: e for e in published["cases"]}[case_id]
start = [s for s in entry["starts"] if s["start"] == start_no][0]
case = [c for c in ensemble_cases() if c.case == case_id][0]
record = ensemble.run_start(case, start)
closings = [e[1] for e in record["events"] if e[0] == "attempt_closed"]
print(
    f"{os.environ.get('OPENBLAS_CORETYPE', 'default'):12s} {ensemble.classify(record):24s} "
    f"{record['outcome']:18s} calls={record['counters']['property_calls']:5d} "
    f"att={record['attempts']} worst={record.get('worst')} attempts={closings} "
    f"events={len(record['events'])} acting_iters={detector._counts['acting_iterations']} "
    f"released_calls={detector._counts['released_calls']}"
)
