"""X10 inventory (ADR 0056 row 9, R-925): the committed unit × basis inventory is what the code
measures today.

`scripts/x10_inventory.py --check` rebinds every pair of `MODEL_BUILDERS` × the selectable
providers, solves each bound `revision_eo` pair once, and compares with
`benchmarks/x10/inventory.json`; it also checks that `docs/X10-inventory.md` is the inventory's
rendering. The full matrix takes about 30 s on the reference host (docs/X10_DECISIONS.md D-5), so
the whole of it is checked, not a subset. The CoolProp column is compared in this environment's
section only (D-3).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

from conftest import REPO_ROOT

SCRIPT = REPO_ROOT / "scripts" / "x10_inventory.py"
INVENTORY = REPO_ROOT / "benchmarks" / "x10" / "inventory.json"


def test_x10_inventory_check_passes() -> None:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr[-2000:]
    assert done.stdout.startswith("X10 inventory: PASS"), done.stdout


def test_x10_inventory_records_both_coolprop_environments() -> None:
    """D-3: the CoolProp column carries a measurement with the extra absent and present."""
    pairs = json.loads(INVENTORY.read_text(encoding="utf-8"))["pairs"]
    coolprop = [pair for pair in pairs.values() if pair["provider"] == "coolprop-heos-v1"]
    assert coolprop
    for pair in coolprop:
        assert set(pair["env"]) == {"coolprop_extra_absent", "coolprop_extra_present"}, pair


def test_x10_inventory_pump_on_wilson_stays_refused() -> None:
    """R-819's refusal, as measured: both pumps are refused at admission on Wilson."""
    pairs = json.loads(INVENTORY.read_text(encoding="utf-8"))["pairs"]
    for model_id in ("syn001.liquid_pump", "thermal.pump"):
        measured = pairs[f"{model_id} x wilson-ig-v2"]["env"]["any"]
        assert measured["class"] == "refused_admission"
        assert measured["reason"] == "no_volume"
