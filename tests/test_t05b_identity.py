"""T05b W8: B22, T05b's part of the K05 identity document (`scripts/t05b_identity.py`).

Spec `docs/derivations/T05b-limitations-spec.md` B22: the R0 projections of SC-1…SC-4,
NP-1…NP-3, DZ-1…DZ-10 and DZ-12 (as `scripts/t05_identity.py` builds them: the plan's R0
projection, the outcome, `r0_projection` of the events, the structural report and the
certificate, the root fingerprint through T03's projection, the typed message's first line), the
outcomes and messages of DZ-11 and DZ-2C, and NP-G's outcome only — under `T05b-v2`,
floats-free, digests only of declared inputs, and the same twice on one machine. CI compares the
document key by key across x86-64 and aarch64 (`.github/workflows/ci.yml`, job `identity`); the
document minus `t05b` is unchanged (`docs/t05b-measurements.md`, "W8").

B30 (d), for the T05b cases: no certificate gains or loses a check id against the baseline
`tests/fixtures/t05b/check_ids.json`, emitted from this key at W8 (a self-generated regression
baseline — a change is reported to the design lane, never re-pinned). T05's registered cases are
covered by the `t05` key, SYN-001's by the rest of the document.
"""

from __future__ import annotations

import json
import re
import sys
from functools import cache
from typing import Any

from conftest import REPO_ROOT
from t05b_support import REF

from openflowsheet.run.identity import floats_in

FULL = [
    "SC-1",
    "SC-2",
    "SC-3",
    "SC-4",
    "NP-1",
    "NP-2",
    "NP-3",
    "DZ-1",
    "DZ-2",
    "DZ-3",
    "DZ-4",
    "DZ-5",
    "DZ-6",
    "DZ-7",
    "DZ-8",
    "DZ-9",
    "DZ-10",
    "DZ-12",
]
COMMON = {
    "plan",
    "outcome",
    "events",
    "solver_counters",
    "structural",
    "root_fingerprint",
    "message",
    "certificate",
}
#: The digests an R0 document may carry: identities of declared inputs (the constants, the
#: model version's structure hash, the variable ids), never of a computed state.
DECLARED_DIGESTS = {"constants_sha256", "model_version", "variable_ids_sha256"}
HEX64 = re.compile(r"[0-9a-f]{64}")
#: Spec B20 (c): no R0 string carries a digit sequence computed from a state.
FLOAT = re.compile(r"\d\.\d|\d[eE][-+]?\d")


def _digest_keys(node: Any, key: str = "") -> set[str]:
    if isinstance(node, dict):
        return set().union(*(_digest_keys(value, name) for name, value in node.items()))
    if isinstance(node, list):
        return set().union(*(_digest_keys(value, key) for value in node))
    return {key} if isinstance(node, str) and HEX64.search(node) else set()


def _identity() -> dict[str, Any]:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from t05b_identity import identity

    return identity()


@cache
def _document() -> dict[str, Any]:
    return _identity()


def test_b22_the_identity_document_carries_t05bs_r0_fields() -> None:
    document = _document()
    assert list(document) == [*FULL, "DZ-11", "DZ-2C", "NP-G"]
    for case in FULL:
        entry = document[case]
        assert set(entry) == COMMON, case
        assert entry["outcome"] == "CONVERGED", case
        assert entry["certificate"]["verification_status"] == "VERIFIED", case
        assert entry["certificate"]["regularity_status"] == "NO_RANK_LOSS_DETECTED", case
        assert entry["plan"]["policy_id"] == "T05b-v2", case
        assert entry["root_fingerprint"] is not None, case
        assert entry["message"] == "", case
    for case in ("DZ-11", "DZ-2C"):
        expected = REF["zero_flow_conflicts"][case]["expected"]
        assert document[case] == {
            "outcome": "SPECIFICATION_CONFLICT",
            "message": expected["message"],
        }
    # B22: NP-G's verdict can sit in ADR 0007 D2.4's band, so only its outcome is R0 here.
    assert document["NP-G"] == {"outcome": "CONVERGED"}

    assert floats_in(document) == []
    assert _digest_keys(document) <= DECLARED_DIGESTS
    for case in FULL:
        fingerprint = document[case]["root_fingerprint"]
        assert "opening_state_sha256" not in fingerprint
        assert "full_state_sha256" not in fingerprint
    for entry in document.values():
        assert not FLOAT.search(entry.get("message", "")), entry["message"]
    assert _identity() == document, "the same twice on one machine"


def test_b30d_no_t05b_certificate_gains_or_loses_a_check_id() -> None:
    baseline = json.loads(
        (REPO_ROOT / "tests" / "fixtures" / "t05b" / "check_ids.json").read_text()
    )["check_ids"]
    document = _document()
    assert list(baseline) == FULL
    for case in FULL:
        assert document[case]["certificate"]["check_ids"] == baseline[case], case
