"""T05 W13: A24, T05's part of the K05 identity document (`scripts/t05_identity.py`).

Design note `docs/design/T05-generalization.md` §6: per case C1, C2, C3 and C3X, the execution
plan's R0 projection, the outcome, `r0_projection` of the events, the structural report and (if
converged) the certificate, the root fingerprint through T03's projection, and the run's typed
message's first line (ruling round Q-R5) — only existing projections, floats-free, and the same
twice on one machine. CI compares the document key by key
across x86-64 and aarch64 (`.github/workflows/ci.yml`, job `identity`); the document minus `t05` is
unchanged (`docs/t05-measurements.md`, "W13b").
"""

from __future__ import annotations

import sys
from pathlib import Path

from openflowsheet.run.identity import floats_in

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_a24_the_identity_document_carries_t05s_r0_fields() -> None:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from t05_identity import identity

    document = identity()
    assert list(document) == [
        "SYN-001-UL-C1",
        "SYN-001-UL-C2",
        "SYN-001-UL-C3",
        "SYN-001-UL-C3X",
    ]
    common = {
        "plan",
        "outcome",
        "events",
        "solver_counters",
        "structural",
        "root_fingerprint",
        "message",
    }
    for case in ("SYN-001-UL-C1", "SYN-001-UL-C2", "SYN-001-UL-C3"):
        entry = document[case]
        assert set(entry) == common | {"certificate"}
        assert entry["outcome"] == "CONVERGED"
        assert entry["certificate"]["verification_status"] == "VERIFIED"
        assert entry["certificate"]["limitation_kinds"] == []
        assert entry["root_fingerprint"]["branch_found"]
        assert entry["events"][-1]["kind"] == "solve_closed"
        assert entry["message"] == ""
    c3x = document["SYN-001-UL-C3X"]
    assert set(c3x) == common
    assert c3x["outcome"] == "INITIALIZATION_FAILED"
    assert c3x["root_fingerprint"] is None
    assert "initializer_rejected" in [event["kind"] for event in c3x["events"]]
    # Ruling round Q-R5 (review N4): A20's discriminant is R0, so the CI pair compares it.
    assert c3x["message"] == "initializer_failed(U-HX): temperature_cross(cold_end)"

    assert floats_in(document) == []
    assert identity() == document, "the same twice on one machine"
