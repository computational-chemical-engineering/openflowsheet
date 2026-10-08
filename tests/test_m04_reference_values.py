"""M04.A34: the design lane's generator re-derives every claim and both committed files (spec §12).

`docs/derivations/scripts/m04_reference.py --check` imports nothing from `openflowsheet`, re-checks
every claim the specification makes about its own numbers at 50 digits, and compares
`benchmarks/m04/reference_values.json` and `benchmarks/m04/plan-it1.json` with its output byte for
byte. It runs in about half a minute, so it is in the default gate.
"""

from __future__ import annotations

import re
import subprocess
import sys

from conftest import REPO_ROOT, load_json

GENERATOR = REPO_ROOT / "docs" / "derivations" / "scripts" / "m04_reference.py"
#: The generator's claim count at the specification's commit (spec header: 5269 claims).
CLAIMS = 5269


def test_a34_the_generator_rederives_every_claim_and_the_committed_bytes() -> None:
    completed = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    output = completed.stdout + completed.stderr
    assert completed.returncode == 0, output
    assert re.search(rf"^{CLAIMS} claims passed$", completed.stdout, re.MULTILINE), output
    for name in ("reference_values.json", "plan-it1.json"):
        assert re.search(
            rf"^benchmarks/m04/{re.escape(name)} is byte-identical to the generator's output$",
            completed.stdout,
            re.MULTILINE,
        ), output
    assert "differs" not in output


def test_a34_the_committed_claim_list_is_the_generators() -> None:
    claims = load_json(REPO_ROOT / "benchmarks" / "m04" / "reference_values.json")["claims"]
    assert claims["count"] == CLAIMS
    assert len(claims["distinct_statements"]) == len(set(claims["distinct_statements"]))
