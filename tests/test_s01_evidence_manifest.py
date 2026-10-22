"""S01 WO-3: the evidence generator's pure parts (`scripts/s01_evidence_manifest.py`) — which §10
ids a test cites, the status rule, §14 read verbatim, and the placeholder guard."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import s01_evidence_manifest as generator  # noqa: E402


def test_a_test_cites_the_ids_its_function_name_carries() -> None:
    cited = generator.cited
    assert cited("tests/x.py::test_a04_a06_the_state_tolerance[C4-presolve]") == ("A04", "A06")
    assert cited("tests/x.py::test_a10_the_fd_floor_at_the_c2_root_is_below_1e_8") == ("A10",)
    assert cited("tests/x.py::test_the_policy_is_t05b_v2_with_newton_refined") == ()
    assert cited("tests/x.py::test_data_a1_is_not_an_id") == ()


def test_status_is_tested_only_when_every_required_check_passes() -> None:
    passing = [
        {"id": f"S01.{identifier}", "result": "pass"} for identifier in generator.ASSERTIONS
    ] + [{"id": name, "result": "pass"} for name in generator.TOOL_CHECKS]
    assert generator.status(passing) == "tested"
    extra = [*passing, {"id": "S01.gate", "result": "unsupported"}]
    assert generator.status(extra) == "tested"
    one_xfail = [dict(entry) for entry in passing]
    one_xfail[4]["result"] = "fail"
    assert generator.status(one_xfail) == "implemented"
    lint = [dict(entry) for entry in passing]
    lint[-1]["result"] = "fail"
    assert generator.status(lint) == "implemented"


def test_section_14_is_read_verbatim_and_section_10_is_complete() -> None:
    document = generator.SPEC.read_text(encoding="utf-8")
    items = generator.section_14(document)
    assert items[0].startswith("**Synthetic data only.** No real-chemistry or column validation")
    assert items[-1] == (
        "**The generator's agreement validates the transcription of SYN-001**, not the property "
        "model."
    )
    assert len(items) == 8
    for item in items:
        assert item in " ".join(document.split())
    assert sorted(generator.section_10(document)) == list(generator.ASSERTIONS)


def test_no_angle_bracket_text_reaches_the_manifest() -> None:
    assert generator.text("zero_flow_conflict(<cascade>:stage:2:energy)") == (
        "zero_flow_conflict(‹cascade›:stage:2:energy)"
    )
    assert generator.text("a <= b and c >= d") == "a ≤ b and c ≥ d"
    assert not generator.ANGLE.search(generator.text("x < y > z"))
