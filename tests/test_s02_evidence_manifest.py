"""S02 WO-3: the evidence generator's pure parts (`scripts/s02_evidence_manifest.py`) — which
assertion ids a test cites, the registered table read from §10, §17 and §18.6, the A16 rule,
the status rule, and §14/§18.9 read verbatim."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import s02_evidence_manifest as generator  # noqa: E402
from s01_evidence_manifest import Node  # noqa: E402


def test_a_test_cites_the_ids_its_function_name_carries() -> None:
    cited = generator.cited
    assert cited("tests/x.py::test_a06b_m1_recovers_after[M1]") == ("A06b",)
    assert cited("tests/x.py::test_a13b_forced_edge_3_from_the_profile_endpoint[M2]") == ("A13b",)
    assert cited("tests/x.py::test_a04_a06_the_state_tolerance") == ("A04", "A06")
    assert cited("tests/x.py::test_a06bis_is_not_an_id") == ()
    assert cited("tests/x.py::test_data_a1_is_not_an_id") == ()


def test_the_registered_table_is_complete_and_amendment_2_replaces_section_10() -> None:
    document = generator.SPEC.read_text(encoding="utf-8")
    rows = generator.assertion_table(document)
    assert tuple(rows) == generator.ASSERTIONS and len(rows) == 24
    assert rows["A14"][0].startswith("M1 from four perturbed endpoints: sweep start")
    assert rows["A05"][1].startswith("`ref.cases.*.bubble_point`")
    assert rows["A11"][0].startswith("§4.3's circulation vector")


def test_section_14_and_18_9_are_read_verbatim() -> None:
    document = generator.SPEC.read_text(encoding="utf-8")
    items = generator.limitations_of_the_spec(document)
    assert len(items) == 8
    assert items[0].startswith("**Synthetic data only.** SYN-001 is an ideal")
    assert items[-1].startswith("The sweeps' convergence is measured on the ten registered")
    assert items[-1].endswith("now with §18.1 item 3's counterexample.")


def _node(name: str, outcome: str = "passed") -> Node:
    return Node(name, outcome, "")


def test_the_s01_suite_rule_reads_the_s01_nodes_only() -> None:
    s01 = [_node(f"tests/test_s01_x.py::test_a{index:02d}_x") for index in range(1, 21)]
    s02 = [_node("tests/test_s02_x.py::test_a16_is_not_cited_here", "failed")]
    assert generator.s01_suite([*s01, *s02])[0] == "pass"
    assert generator.s01_suite(s01[:-1])[0] == "fail"  # S01's A20 uncited
    xfailed = [*s01, _node("tests/test_s01_y.py::test_helper", "xfailed")]
    assert generator.s01_suite(xfailed)[0] == "fail"


def test_status_is_tested_only_when_every_required_check_passes() -> None:
    passing = [
        {"id": f"S02.{identifier}", "result": "pass"} for identifier in generator.ASSERTIONS
    ] + [{"id": name, "result": "pass"} for name in generator.REQUIRED_CHECKS]
    assert generator.status(passing) == "tested"
    unsupported_gate = [*passing, {"id": "S02.gate", "result": "unsupported"}]
    assert generator.status(unsupported_gate) == "tested"
    for index in range(len(passing)):
        one_fail = [dict(entry) for entry in passing]
        one_fail[index]["result"] = "fail"
        assert generator.status(one_fail) == "implemented"


def test_s02_nodes_cite_and_s01_nodes_do_not() -> None:
    rows = {identifier: ("a", "e", "t") for identifier in generator.ASSERTIONS}
    tests = [
        _node("tests/test_s01_x.py::test_a11_an_s01_id"),
        _node("tests/test_s02_x.py::test_a12_p1", "xfailed"),
    ]
    found = {entry["id"]: entry for entry in generator.assertion_checks(rows, tests)}
    assert found["S02.A11"]["result"] == "fail" and found["S02.A11"]["value"]["nodes"] == 0
    assert found["S02.A12"]["result"] == "fail"
    assert found["S02.A12"]["value"]["not_passed"][0]["outcome"] == "xfailed"
