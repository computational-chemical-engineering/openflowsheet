"""M05 G10 (§13, §19.4; R-435, design note §21.6): the five in-process records replayed in the
`nlp` tier — TR-E2, TR-E2-FAR, TR-E2-FD, LOOP-R and LOOP-S, each re-run from a fresh store by
`scripts/m05_wo8_runs.py`'s `run_case` and compared with the committed files by its `compare`
(the environment fingerprint exactly, the record by `m05_replay.replay_differences` without
`provenance`, the ledger and the store index bytewise, every persisted coupling record by integrity
and content), with G7's store bijection on the fresh run.

The numbers depend on the OpenMP thread count (build log S59), so the test refuses — fails, never
skips — unless `OMP_NUM_THREADS=1`. An environment-fingerprint mismatch is a difference like any
other: it fails and is named in the message, never a pass. REAL's replay stays the script
(`scripts/m05_wo9_real.py --replay`): it needs the reactor environment and takes about 25 min.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from conftest import REPO_ROOT

pytestmark = pytest.mark.nlp

CASES = ("TR-E2", "TR-E2-FAR", "TR-E2-FD", "LOOP-R", "LOOP-S")


@pytest.mark.parametrize("name", CASES)
def test_g10_in_process_replay(name: str, tmp_path: Path) -> None:
    """G10: the fresh run equals the committed record and its sidecars (0 differences), and its
    store bijection holds."""
    if os.environ.get("OMP_NUM_THREADS") != "1":
        pytest.fail(
            "G10 refuses: the replays need OMP_NUM_THREADS=1 (build log S59), "
            f"got {os.environ.get('OMP_NUM_THREADS')!r}"
        )
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import m05_wo8_runs as wo8

    case = wo8.CASES[name]
    run = wo8.run_case(case, tmp_path)
    found = wo8.compare(case, run)
    assert not found, f"G10 {name}: {len(found)} differences:\n" + "\n".join(found[:40])
    assert not run.bijection, f"G7 {name}: " + "\n".join(run.bijection[:40])
