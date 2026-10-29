"""E01 review S4: the A48 tripwire (§9.6 A48, §9.7 QA1; the MR-12 / S07 Ruling M pattern).

The shipped SSLW set carries three `primary` size ranges with `verified: false` (the compressors;
QA1.patch verified the other five, E01b C1); they set S_min and S_max, and so the floors and the
parallel-unit splits. `a48_release_check()` is the release
candidate's measure: it fails while any primary range is unverified. This test pins today's count
and the `fail`, so the normal suite passes while a release cannot: the release specification flips
the ranges (after QA1) and this count together.
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

#: The unverified primary ranges after QA1.patch (E01b C1, 2026-10-29); the release specification
#: sets 0.
UNVERIFIED_AT_REVIEW = 3
SET = REPO / "src" / "openflowsheet" / "_data" / "assessment" / "cost" / "sslw-idaes-v1.json"


def test_e01_a48_tripwire() -> None:
    result, value = manifest.a48_release_check()
    assert value["unverified_primary_ranges"] == UNVERIFIED_AT_REVIEW, value
    assert list(value["by_set"]) == ["sslw-idaes-v1"]
    assert result == "fail"


def test_the_release_check_passes_once_every_primary_range_is_verified() -> None:
    document = json.loads(SET.read_text(encoding="utf-8"))
    pointers = unverified_primary_ranges(document)
    assert len(pointers) == UNVERIFIED_AT_REVIEW
    verified = copy.deepcopy(document)
    for pointer in pointers:
        node = verified
        for key in pointer.strip("/").split("/"):
            node = node[int(key)] if isinstance(node, list) else node[key]
        assert node["source"]["kind"] == "primary"
        node["source"]["verified"] = True
    assert unverified_primary_ranges(verified) == ()
