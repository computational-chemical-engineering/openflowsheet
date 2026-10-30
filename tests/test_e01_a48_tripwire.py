"""E01 review S4: the A48 tripwire (§9.6 A48, §9.7 QA1; the MR-12 / S07 Ruling M pattern).

Every `primary` size range of the shipped SSLW set is `verified: true` after C7 (E01b, design note
§10.10.8: the three compressors, the turbine and fit "2", on Frank's approval; QA1.patch verified
the other five). `a48_release_check()` is the release candidate's measure: it fails while any
primary range is unverified. This test pins the count 0 and the `pass`, and its negative case
flips one range back in a copy (design note §10.5 A48, amended).
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import e01_evidence_manifest as manifest  # noqa: E402

from openflowsheet.assessment.cost.sets import unverified_primary_ranges  # noqa: E402

#: The unverified primary ranges after C7 (E01b, design §10.10.6, §10.10.8).
UNVERIFIED_AT_REVIEW = 0
SET = REPO / "src" / "openflowsheet" / "_data" / "assessment" / "cost" / "sslw-idaes-v1.json"


def test_e01_a48_tripwire() -> None:
    result, value = manifest.a48_release_check()
    assert value["unverified_primary_ranges"] == UNVERIFIED_AT_REVIEW, value
    assert value["by_set"] == {}
    assert result == "pass"


def test_the_release_check_finds_one_range_flipped_back() -> None:
    """§10.5 A48's negative case: one primary range set to `false` in a copy is exactly what
    `unverified_primary_ranges` returns."""
    document = json.loads(SET.read_text(encoding="utf-8"))
    assert unverified_primary_ranges(document) == ()
    flipped = copy.deepcopy(document)
    turbine = next(i for i, e in enumerate(flipped["entries"]) if e["entry_id"] == "turbine")
    flipped["entries"][turbine]["ranges"]["power_hp"]["source"]["verified"] = False
    assert unverified_primary_ranges(flipped) == (f"/entries/{turbine}/ranges/power_hp",)
