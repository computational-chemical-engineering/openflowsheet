"""RRC G8 (ADR 0072; design note `docs/design/RRC-revision-region-continuation.md` §8.2): R0 is
reproducible. Each registered pair (G4's N1, NET-02; G5's C3, the column pair) is solved in a store
twice, each time in a fresh process: the source under `T06-revision-v2`, then the target under
`RRC-revision-v1`, whose revision continuation is `taken`. The two target bundles' manifests carry
equal `artifact_r0_sha256` (the R0 projection: λ sequence, `D`, outcomes, counts), and that digest
is the one measured on x86-64 (`docs/RRC_DECISIONS.md` D-44), so the CI `check` leg on aarch64
holds the cross-architecture half of the gate against the same value.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
REFERENCE: dict[str, Any] = yaml.safe_load(
    (ROOT / "benchmarks" / "rrc" / "reference_values.yaml").read_text(encoding="utf-8")
)
PAIRS: dict[str, Any] = REFERENCE["pairs"]

#: D-44: the target bundle's `artifact_r0_sha256`, measured on x86-64 at the merge prep (G4's
#: equals WO-4's NET-02 store-pair measurement, `aa47dabf…`, "WO-4 gate runs").
R0: dict[str, str] = {
    "G4": "aa47dabf12e4000a1635c10d950cca3ef4d9db6d1cb5d022c5a82b9dc4aada73",
    "G5": "f835da24214f7f015e28a398d895c7b37cf1096b863fd58b3493aa04dd009d9e",
}

PROGRAM = """
import sys, tempfile
from pathlib import Path
sys.path.insert(0, {root!r})
from benchmarks.rrc import run_candidates as harness
from openflowsheet.application.local import LocalApplication
from openflowsheet.run.bundle import read_manifest

_, source_doc, target_doc, _ = harness._find({candidate!r})
with tempfile.TemporaryDirectory() as tmp:
    with LocalApplication.create(Path(tmp) / "p", project_id="rrc-g8") as app:
        source_id = harness._store_commit(app, source_doc)
        source = harness._store_solve(app, source_id, "T06-revision-v2")
        assert (source["outcome"], source["verification_status"]) == ("CONVERGED", "VERIFIED")
        target_id = harness._store_commit(app, target_doc)
        target = harness._store_solve(app, target_id, "RRC-revision-v1")
        assert target["member_status"] == "taken", target
        manifest, _ = read_manifest(app.files_root / "jobs" / target["job_id"] / "bundle")
        print(manifest.artifact_r0_sha256)
"""


def _r0_in_a_fresh_process(candidate: str) -> str:
    completed = subprocess.run(
        [sys.executable, "-c", PROGRAM.format(root=str(ROOT), candidate=candidate)],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )
    assert completed.returncode == 0, completed.stderr[-2000:]
    return completed.stdout.strip().splitlines()[-1]


@pytest.mark.parametrize("gate", ["G4", "G5"])
def test_g8_r0_is_reproducible_in_fresh_processes_and_across_architectures(gate: str) -> None:
    candidate = PAIRS[gate]["candidate"]
    first, second = (_r0_in_a_fresh_process(candidate) for _ in range(2))
    assert first == second, (gate, candidate, first, second)
    assert first == R0[gate], (gate, candidate, first)
