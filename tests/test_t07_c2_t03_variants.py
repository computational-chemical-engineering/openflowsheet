"""The three `v17-c2` T03 certificates the scorer could not judge (unjudged_verified),
checked against independent twin roots (`docs/reviews/T07-verdicts.md`, "Supplementary: the
three unjudged T03 certificates"). The script imports nothing from `openflowsheet` or
`benchmarks`; `--check` re-derives every claim from the committed run records and compares
with the committed output."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "docs" / "derivations" / "scripts" / "t07_c2_t03_variants.py"
EXPECTED = SCRIPT.with_suffix(".json")


def test_the_three_t03_variant_certificates_meet_their_independent_roots() -> None:
    pytest.importorskip("mpmath")
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(ROOT), "--check", str(EXPECTED)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
