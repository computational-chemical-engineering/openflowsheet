"""E01 WO-B1: the frozen LCA tables, their rights, the adapter's import guard and the D04 inventory
(design §4.8.2, §4.8.4–§4.8.6; ADR 0052 D7, D8; A27 table part, A29 adapter part, A42).

Independent expectations: the IPCC values are the ones read from AR6 WG1 Table 7.15 (WO-B1, typed
here from the chapter, not from the shipped file); the test background's scores are the design's
rationals (§4.8.5) and track A's mpmath expectation (`benchmarks/e01/lca_hand/lca_hand.yaml`).
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
import yaml

from openflowsheet.assessment.lca import brightway, tables
from openflowsheet.assessment.lca.tables import LcaTableError, parse_table, table_sha256

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import e01_d04_inventory as d04  # noqa: E402

# AR6 WG1 ch. 7, Table 7.15, GWP-100 column (read 2026-10-27 from the chapter PDF, sha256
# 470d2662…febfa9), plus the stated biogenic convention for non-fossil CO2.
AR6_GWP100 = {
    "co2_fossil_air": 1.0,
    "co2_non_fossil_air": 0.0,
    "ch4_fossil_air": 29.8,
    "ch4_non_fossil_air": 27.0,
    "n2o_air": 273.0,
}
DESIGN_Q = {
    "tb.electricity": Fraction("16.965625") / 31,
    "tb.heat": Fraction("5.8625") / 31,
    "tb.chemical_x": Fraction("27.9578125") / 31,
}


def _shipped(table_id: str) -> dict[str, Any]:
    return copy.deepcopy(dict(tables.load_shipped(table_id).document))


def test_the_shipped_tables_are_what_the_generator_writes() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "e01_lca_data.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_shipped_tables_load_and_their_hashes_hold() -> None:
    assert tables.SHIPPED_TABLES == ("gwp100-ipcc-ar6-v1", "test-background-v1")
    for table_id in tables.SHIPPED_TABLES:
        table = tables.load_shipped(table_id)
        assert table.table_id == table_id
        assert table.sha256 == table_sha256(table.document) == table.document["sha256"]
        assert not table.rights.forbidden
        assert table.rights.licence and table.rights.notice


def test_the_ipcc_factors_are_table_7_15() -> None:
    table = tables.load_shipped("gwp100-ipcc-ar6-v1")
    assert isinstance(table, tables.DirectFactorTable)
    assert [c.category_id for c in table.categories] == ["climate_change_gwp100_ar6"]
    assert table.categories[0].unit == "kg CO2-eq"
    assert {f: table.value("climate_change_gwp100_ar6", f) for f in table.columns} == AR6_GWP100
    # A27, table part: 1 kg CH4 fossil is exactly 29.8 kg CO2-eq.
    assert 1.0 * table.value("climate_change_gwp100_ar6", "ch4_fossil_air") == 29.8
    assert "Table 7.15" in table.document["source"]["citation"]


def test_the_test_background_scores_are_the_hand_solution() -> None:
    table = tables.load_shipped("test-background-v1")
    assert isinstance(table, tables.UnitScoreTable)
    hand = yaml.safe_load((ROOT / "benchmarks/e01/lca_hand/lca_hand.yaml").read_text("utf-8"))
    for activity, q in DESIGN_Q.items():
        value = table.value("climate_change_test", activity)
        assert value == float(q)
        assert value == hand["background"]["unit_scores"][activity]["value"]
    units = {a.activity_id: (a.unit, a.si_per_unit) for a in table.activities}
    assert units == {
        "tb.electricity": ("kWh", 3.6e6),
        "tb.heat": ("MJ", 1e6),
        "tb.chemical_x": ("kg", 1.0),
    }
    # The Brightway description is the §4.8.5 background, exchange by exchange.
    description = table.document["brightway"]
    amounts = {
        (k, tuple(e["input"])[1]): e["amount"]
        for k, body in description["activities"].items()
        for e in body["exchanges"]
        if e["type"] != "production"
    }
    assert amounts == {
        ("tb.electricity", "tb.heat"): 0.25,
        ("tb.electricity", "co2_fossil_air"): 0.5,
        ("tb.heat", "tb.electricity"): 0.125,
        ("tb.heat", "co2_fossil_air"): 0.0625,
        ("tb.heat", "ch4_fossil_air"): 0.001953125,
        ("tb.chemical_x", "tb.electricity"): 0.5,
        ("tb.chemical_x", "tb.heat"): 2.0,
        ("tb.chemical_x", "co2_fossil_air"): 0.25,
    }
    assert description["methods"][0]["cfs"] == [
        [["test-biosphere-v1", "co2_fossil_air"], 1.0],
        [["test-biosphere-v1", "ch4_fossil_air"], 29.8],
    ]


def test_the_hash_excludes_created_and_covers_everything_else() -> None:
    document = _shipped("test-background-v1")
    document["producer"]["created"] = "2030-01-01"
    assert parse_table(document).sha256 == tables.load_shipped("test-background-v1").sha256
    document["scores"][0][0] = 0.5
    with pytest.raises(LcaTableError) as error:
        parse_table(document)
    assert error.value.code == "LCA_TABLE_HASH_MISMATCH"
    document = _shipped("gwp100-ipcc-ar6-v1")
    document["rights"]["redistribution"] = "forbidden"
    with pytest.raises(LcaTableError) as error:
        parse_table(document)
    assert error.value.code == "LCA_TABLE_HASH_MISMATCH"


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda d: d.update(format="unit-score-table-v2"), "unknown format"),
        (lambda d: d["scores"].append([1.0, 1.0, 1.0]), "scores must be a list of 1 rows"),
        (lambda d: d["scores"][0].pop(), "scores[0] must have 3 entries"),
        (lambda d: d["activities"][0].update(si_per_unit=0), "si_per_unit > 0"),
        (lambda d: d["rights"].update(redistribution="maybe"), "rights.redistribution"),
        (lambda d: d["activities"][1].update(activity_id="tb.electricity"), "activity ids repeat"),
    ],
)
def test_a_malformed_table_is_refused(edit: Any, message: str) -> None:
    document = _shipped("test-background-v1")
    edit(document)
    document["sha256"] = table_sha256(document)
    with pytest.raises(LcaTableError) as error:
        parse_table(document)
    assert error.value.code == "LCA_TABLE_INVALID"
    assert message in str(error.value)


def _user_table(tmp_path: Path, redistribution: str = "forbidden") -> tuple[Path, dict[str, Any]]:
    document = _shipped("test-background-v1")
    document.pop("brightway")
    document["table_id"] = "user-ecoinvent-like"
    document["scores"] = [[0.123456789012345, 0.234567890123456, 0.345678901234567]]
    document["rights"] = {
        "class": "user-licensed",
        "licence": "ecoinvent EULA (user's own licence)",
        "redistribution": redistribution,
        "notice": "derived from a licensed database" if redistribution == "allowed" else "",
    }
    document["sha256"] = table_sha256(document)
    path = tmp_path / "user.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path, document


def test_resolve_reads_shipped_and_user_tables_and_checks_the_named_hash(tmp_path: Path) -> None:
    path, document = _user_table(tmp_path)
    good = {
        "lca": {
            "tables": ["test-background-v1", "user-ecoinvent-like"],
            "direct_factors": ["gwp100-ipcc-ar6-v1"],
        },
        "data": {
            "tables": [
                {"id": "user-ecoinvent-like", "sha256": document["sha256"], "path": str(path)}
            ]
        },
    }
    found, refused = tables.resolve_tables(good)
    assert refused == {}
    assert list(found) == ["test-background-v1", "user-ecoinvent-like", "gwp100-ipcc-ar6-v1"]
    bad = copy.deepcopy(good)
    bad["data"]["tables"][0]["sha256"] = "0" * 64
    bad["data"]["tables"].append({"id": "test-background-v1", "sha256": "1" * 64})
    bad["lca"]["tables"].append("no-such-table")
    bad["lca"]["direct_factors"].append("test-background-v1")
    found, refused = tables.resolve_tables(bad)
    assert list(found) == ["gwp100-ipcc-ar6-v1"]
    assert {k: r.code for k, r in refused.items()} == {
        "user-ecoinvent-like": "LCA_TABLE_HASH_MISMATCH",
        "test-background-v1": "LCA_ACTIVITY_UNKNOWN",  # the later, wrong-format listing wins
        "no-such-table": "LCA_ACTIVITY_UNKNOWN",
    }


def test_a_forbidden_table_exports_its_id_and_hash_only(tmp_path: Path) -> None:
    _, document = _user_table(tmp_path)
    table = parse_table(document)
    assert table.rights.forbidden
    reference = tables.reference(table)
    exported = json.dumps([reference, tables.exportable(table)])
    assert reference == {
        "id": "user-ecoinvent-like",
        "sha256": document["sha256"],
        "rights": "user-licensed; redistribution forbidden; ecoinvent EULA (user's own licence)",
    }
    for score in document["scores"][0]:
        assert repr(score) not in exported and str(score)[:10] not in exported
    assert document["sha256"] in exported
    _, allowed = _user_table(tmp_path, "allowed")
    assert tables.exportable(parse_table(allowed)) == allowed


def test_a29_every_adapter_call_is_unsupported_without_brightway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "bw2data", None)
    monkeypatch.setitem(sys.modules, "bw2calc", None)
    assert not brightway.available()
    calls = [
        brightway.build_unit_score_table(
            "p", [("a", ("db", "a"))], [("m", ("x",))], {}, table_id="t"
        ),
        brightway.build_direct_factor_table(
            "p", ("m", ("x",)), [("f", ("bio", "f"))], {}, table_id="t"
        ),
        brightway.foreground_check("p", [(("db", "a"), 1.0)], [], ("x",)),
        brightway.write_description("p", {}),
    ]
    for result in calls:
        assert isinstance(result, tables.Refusal)
        assert (result.kind, result.code) == ("unsupported", "LCA_ENGINE_UNAVAILABLE")


def test_the_core_lca_path_imports_no_brightway() -> None:
    code = (
        "import sys; import openflowsheet.assessment.lca.tables, "
        "openflowsheet.assessment.lca.brightway; "
        "print(sorted(m for m in sys.modules "
        "if m.split('.')[0] in ('bw2data', 'bw2calc', 'bw_processing')))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "[]"


def test_a42_the_d04_inventory_covers_every_data_file_and_dependency() -> None:
    assert d04.check() == []
    record = json.loads(d04.PACKAGES_RECORD.read_text("utf-8"))
    assert record["requirements"] == ["bw2data==4.7", "bw2calc==2.5.0"]
    names = {row["name"] for row in record["distributions"]}
    assert {"bw2data", "bw2calc"} <= names and not names & {"bw2io", "pypardiso", "mkl"}
    rows = {row["name"]: row for row in record["distributions"]}
    assert rows["bw2data"]["license_files"] == {
        "licenses/LICENSE": "966d484abb7c9601d38b3797695be4ccd24199e95b3c43346fc668204ad622d5"
    }
    assert rows["bw2calc"]["license_files"] == {
        "licenses/LICENSE": "e3e590114822c8f110f6b0333ef0649494287680c2cb950d333f977e85bee2c8"
    }


def test_a42_the_checker_fails_on_an_unlisted_or_changed_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = tmp_path / "assessment"
    for path in d04.DATA.rglob("*.json"):
        target = data / path.relative_to(d04.DATA)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    monkeypatch.setattr(d04, "DATA", data)
    assert d04.check() == []
    (data / "lca" / "extra.json").write_text("{}", encoding="utf-8")
    (data / "cost" / "chains.json").write_text("{}", encoding="utf-8")
    problems = d04.check()
    assert any("lca/extra.json: no D04 entry" in p for p in problems)
    assert any("cost/chains.json: sha256 differs" in p for p in problems)
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "e01_d04_inventory.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0 and result.stdout.startswith("A42 PASS")
