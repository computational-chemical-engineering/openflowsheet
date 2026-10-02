"""Emit the R0 structural artifacts of a reference run, for cross-platform comparison. K05, G05.

Gate G05's second clause is "two-platform structural equality". This produces, on whatever
platform it runs on, the things blueprint §8.3 R0 promises identical across supported
platforms: the model and constants identity, the plan's structure, the event sequence with its
kinds and outcomes, the solver counters, and the manifest's `structural_sha256`.

**It deliberately does not emit floats.** R0 is a promise about structure; §8.3 excludes
adaptive floating-point decisions from any cross-platform bitwise promise, and two
`ubuntu-latest` runners were measured disagreeing on the last bits of a converged state on
2026-09-21. A comparison that included them would fail for a reason that is not a defect, and
the point of this file is that a failure *is* one.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/k05_structural_identity.py --out identity.json
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from k03_schema_fixtures import POLICY, flowsheet  # noqa: E402
from t02_identity import identity as t02_identity  # noqa: E402
from t03_identity import identity as t03_identity  # noqa: E402
from t04_identity import identity as t04_identity  # noqa: E402
from t05_identity import identity as t05_identity  # noqa: E402
from t05b_identity import identity as t05b_identity  # noqa: E402
from t06_identity import identity as t06_identity  # noqa: E402
from t07_identity import identity as t07_identity  # noqa: E402

from openflowsheet.run.bundle import read_artifact  # noqa: E402
from openflowsheet.run.identity import r0_projection  # noqa: E402
from openflowsheet.run.session import run_session  # noqa: E402


def identity() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as scratch:
        directory = Path(scratch)
        manifest = run_session(flowsheet(), directory, policy=POLICY, run_id="g05-structural")

        # S1(b): the projection is production code now (`run/identity.py`), because the
        # manifest's identity covers its digest. Two copies of this shape would be one copy
        # and one rumour — which is the drift M4 found between the comparator and the policy.
        projection = r0_projection(
            {name: read_artifact(directory, name) for name in manifest.artifacts}
        )
        return {
            "structural_sha256": manifest.structural_sha256,
            "artifact_r0_sha256": manifest.artifact_r0_sha256,
            "policy_sha256": manifest.policy_sha256,
            "model_version": manifest.model_version,
            "constants_sha256": manifest.constants_sha256,
            "plan_id": manifest.plan_id,
            "outcome": manifest.outcome,
            "verification_status": manifest.verification_status,
            "check_policy_sha256": manifest.check_policy_sha256,
            **projection,
            # T02 A02/A34: the plans and the recycle decisions are R0 and compared for equality.
            # Their two R1/R2 floats are not here — `scripts/t02_identity.py --floats-out` writes
            # them to their own artifact, compared under ADR 0007 D2.
            "t02": t02_identity()["r0"],
            # T03 A23: ADR 0005's R0 fields (policy literal, patterns, messages, provenance,
            # fingerprints) for OFF-B, PHS-01, PHS-04, PHS-05 and MR-A; floats-free.
            "t03": t03_identity(),
            # T04 A26: ADR 0010 D7's R0 fields (the globalization policy, `homotopy_step` with λ as
            # `p/q`, levels, `eo_recovery`, contexts' `core`/`continuation`, provenance
            # `continuation`, `continuation_lambda`, the PTC trials' verdicts and counts) for
            # HOM-01, HOM-03, HOM-04, HOM-U, PTC-S1, PTC-S5, OFF-B and PHS-05 under PTC;
            # floats-free.
            "t04": t04_identity(),
            # T05 A24 (design note §6): per coupled case C1, C2, C3 and C3X, the execution plan's
            # R0 projection, the outcome, `r0_projection` of the events, the structural report
            # and (when converged) the certificate, and the root fingerprint through T03's
            # projection; floats-free.
            "t05": t05_identity(),
            # T05b B22: under `T05b-v2`, the same projections as `t05` of SC-1…SC-4, NP-1…NP-3,
            # DZ-1…DZ-10 and DZ-12, the outcomes and typed messages of DZ-11 and DZ-2C, and
            # NP-G's outcome only (its verdict can sit in ADR 0007 D2.4's band); floats-free.
            "t05b": t05b_identity(),
            # T06 §10 (A45): under each case's registered policy, the R0 records of §4.3's new
            # flowsheets, REF-01…REF-07 and ADV-06 L/M/H, NET-02's `T05b-v2` control, STR-02's and
            # STR-06's validation, STA-03's conversions and tear records (A69's two spellings
            # too), STA-04's declared order and record, §8.7's typed initializer failures, and
            # the ensemble's definition (cases, coordinates, per-path policy ids and hashes, the
            # law's ids, the KATs' `k53`); floats-free, no per-start outcome.
            "t06": t06_identity(),
            # T07 §15 W8 (G1): through the application contract, inline, under each route's
            # registered policy: `RunResult`'s R0 members, the job-event projection, F5's
            # validation (provenance excluded) and the bundle's R0 as written (W3-Q3) of
            # SYN-001-nominal, C2, NET-02, STA-04, SYN-001-A02-360 (`legacy_eo`) and SYN-001-UL-C3X
            # (the initializer's failure bundle); G10's Q29 refusal codes; ADR 0002 A1's 22
            # integers' commit outcomes; floats-free, nothing volatile.
            "t07": t07_identity(),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args()

    document = identity()
    arguments.out.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")
    print(f"structural_sha256 = {document['structural_sha256']}")
    print(
        f"events = {len(document['events'])}, checks = {len(document['certificate']['check_ids'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
