"""S06 WO-2: the evidence generator's pure parts (`scripts/s06_evidence_manifest.py`) — the
registered table read from §10, §14 read verbatim, the A16 rule and the status rule."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import s06_evidence_manifest as generator  # noqa: E402
from s01_evidence_manifest import ASSERTIONS as S01_ASSERTIONS  # noqa: E402
from s01_evidence_manifest import Node  # noqa: E402
from s02_evidence_manifest import ASSERTIONS as S02_ASSERTIONS  # noqa: E402


def _node(name: str, outcome: str = "passed") -> Node:
    return Node(name, outcome, "")


def test_the_registered_table_is_section_10s() -> None:
    document = generator.SPEC.read_text(encoding="utf-8")
    rows = generator.assertion_table(document)
    assert tuple(rows) == generator.ASSERTIONS and len(rows) == 16
    assert rows["A01"][0].startswith("Columns = rows for J1–J8 and the V-sets")
    assert rows["A16"][0].startswith("S02's A01–A22")


def test_section_14_is_read_verbatim() -> None:
    items = generator.limitations_of_the_spec(generator.SPEC.read_text(encoding="utf-8"))
    assert len(items) == 8
    assert items[0].startswith("**Synthetic data only.** SYN-001 is ideal, three-component")
    assert items[-1].startswith("**No rate-based, inside-out or sensitivity results**")


def _lower() -> list[Node]:
    s01 = [_node(f"tests/test_s01_x.py::test_a{n[1:]}_x") for n in S01_ASSERTIONS]
    s02 = [_node(f"tests/test_s02_x.py::test_{n.lower()}_x") for n in S02_ASSERTIONS if n != "A16"]
    return [*s01, *s02]


def test_a16_reads_the_s02_and_s01_nodes() -> None:
    lower = _lower()
    assert generator.lower_suites(lower)[0] == "pass"
    assert generator.lower_suites(lower[1:])[0] == "fail"  # S01's A01 uncited
    assert generator.lower_suites(lower[:-1])[0] == "fail"  # S02's last id uncited
    xfailed = [*lower, _node("tests/test_s02_y.py::test_helper", "xfailed")]
    assert generator.lower_suites(xfailed)[0] == "fail"
    s06 = [*lower, _node("tests/test_s06_y.py::test_a16_is_not_judged_here", "failed")]
    assert generator.lower_suites(s06)[0] == "pass"


def test_s06_nodes_cite_and_lower_nodes_do_not() -> None:
    rows = {identifier: ("a", "e", "t") for identifier in generator.ASSERTIONS}
    tests = [
        *_lower(),
        _node("tests/test_s06_x.py::test_a05_x"),
        _node("tests/test_s06_x.py::test_a02_x", "xfailed"),
    ]
    found = {entry["id"]: entry for entry in generator.assertion_checks(rows, tests)}
    assert found["S06.A05"]["result"] == "pass" and found["S06.A05"]["value"]["nodes"] == 1
    assert found["S06.A02"]["result"] == "fail"
    assert found["S06.A01"]["result"] == "fail" and found["S06.A01"]["value"]["nodes"] == 0
    assert found["S06.A16"]["result"] == "pass"


def test_status_is_tested_only_when_every_required_check_passes() -> None:
    passing = [
        {"id": f"S06.{identifier}", "result": "pass"} for identifier in generator.ASSERTIONS
    ] + [{"id": name, "result": "pass"} for name in generator.REQUIRED_CHECKS]
    assert generator.status(passing) == "tested"
    assert generator.status([*passing, {"id": "S06.gate", "result": "unsupported"}]) == "tested"
    for index in range(len(passing)):
        one_fail = [dict(entry) for entry in passing]
        one_fail[index]["result"] = "fail"
        assert generator.status(one_fail) == "implemented"
