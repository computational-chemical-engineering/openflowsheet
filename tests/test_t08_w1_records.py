"""T08.A16 (W1.7): a campaign record carries its commit, clean-tree flag, lock hash, machine class.

T08 release spec §6.1 ("run records lack the lock hash": T07 verdict §7.6, T06 P3), §9 A16. Of the
records the RC job writes (§8.2), the ensemble's run document already carries them (T06 §6.6 (A5):
`ensemble.provenance` and the host block's `machine_class`); G16-b's `run.json` now does too, from
the same sources. The RC bundle set's record is written by the RC job itself (§8.2 step 5), which
does not exist yet. Here the fields are compared with what they claim to record: the repository's
own `HEAD`, its porcelain status, the lock's bytes and the registry's machine classes. That the
tree is clean and the commit is `C` holds only for the RC job's own runs, so it is not asserted.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from conftest import REPO_ROOT

import benchmarks.t06.ensemble as ensemble
from benchmarks.t07.v17 import reference, scorer

#: T08 release spec §3.2 (T08.A40): `requirements.lock` is not edited in T08.
LOCK_SHA256 = "ead4edf1ea3577287a7576d56a9e5db550e5a5be459dd634b10806fdc655b9c4"


def _git(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    )
    return completed.stdout


def _assert_attributable(record: dict[str, Any]) -> None:
    assert record["commit"] == _git("rev-parse", "HEAD").strip()
    assert len(record["commit"]) == 40 and int(record["commit"], 16) >= 0
    assert record["tree_clean"] is (_git("status", "--porcelain") == "")
    lock = hashlib.sha256((REPO_ROOT / "requirements.lock").read_bytes()).hexdigest()
    assert record["environment_lock_sha256"] == lock == LOCK_SHA256
    registered = set(ensemble.registered()["machine_classes"])
    machine = record["machine_class"]
    assert machine in registered or machine.startswith("unregistered("), machine


def test_a16_the_ensemble_record_is_attributable() -> None:
    _assert_attributable({**ensemble.provenance(REPO_ROOT), **ensemble.host()})


def test_a16_a_g16b_run_record_is_attributable(tmp_path: Path) -> None:
    record = reference.run("V17-T01", "python", tmp_path)
    run = json.loads((record.directory / scorer.RUN_FILE).read_bytes())
    _assert_attributable(run["provenance"])
    assert run["provenance"]["machine_class"] == ensemble.machine_class()
    # The scorer reads the record as before.
    assert reference.clean(reference.verdict(record))
