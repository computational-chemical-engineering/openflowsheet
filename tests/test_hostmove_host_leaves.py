"""R-1020 (`docs/reviews/HOSTMOVE-ruling.md` §11, WO-H6): the ruling's claims about the 0.4.0
records stay executable. `docs/derivations/scripts/hostmove_host_leaves.py --check` regenerates the
host-leaf inventory from the commit tagged `v0.4.0` and byte-compares it with the committed
`hostmove_host_leaves.json`; it refuses to emit when one of the ruling's claims about those bytes
fails. CI clones with `fetch-depth: 0`, so the pinned commit is present there.
"""

from __future__ import annotations

import subprocess
import sys

from conftest import REPO_ROOT

GENERATOR = REPO_ROOT / "docs" / "derivations" / "scripts" / "hostmove_host_leaves.py"


def test_the_host_leaf_inventory_reproduces_from_the_pinned_records() -> None:
    run = subprocess.run(
        [sys.executable, "-I", str(GENERATOR), "--check"],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    assert run.returncode == 0, run.stdout + run.stderr
