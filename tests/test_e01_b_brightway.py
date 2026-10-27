"""E01 WO-B1: the Brightway adapter against the synthetic background (design §4.8.4, §4.8.5; A24).

Runs only where the optional extra `lca` is installed (`scripts/build-lca-env.sh`, `.venv-lca`):
elsewhere the module is skipped, which is `not run` for gate G5, never a pass. Brightway keeps its
projects in a temporary `BRIGHTWAY2_DIR`, set before bw2data is first imported.

The expectation is the design's exact hand solution `q = (16.965625, 5.8625, 27.9578125)/31`
(§4.8.5), independent of the shipped table and of Brightway.
"""

from __future__ import annotations

import os
import tempfile
import warnings
from collections.abc import Iterator
from fractions import Fraction

import pytest

if "bw2data" not in __import__("sys").modules:
    os.environ.setdefault("BRIGHTWAY2_DIR", tempfile.mkdtemp(prefix="ofs-bw-"))
pytest.importorskip("bw2data")
pytest.importorskip("bw2calc")

from openflowsheet.assessment.lca import brightway, tables  # noqa: E402

PROJECT = "ofs-e01-test-background"
HAND_Q = {
    "tb.electricity": Fraction("16.965625") / 31,
    "tb.heat": Fraction("5.8625") / 31,
    "tb.chemical_x": Fraction("27.9578125") / 31,
}


@pytest.fixture(scope="module")
def background() -> Iterator[tables.UnitScoreTable]:
    table = tables.load_shipped("test-background-v1")
    assert isinstance(table, tables.UnitScoreTable)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert brightway.write_description(PROJECT, table.document["brightway"]) is None
    yield table


def test_a24_the_adapter_reproduces_the_hand_unit_scores(background: tables.UnitScoreTable) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        document = brightway.build_unit_score_table(
            PROJECT,
            [(a.activity_id, a.key) for a in background.activities],
            [(c.category_id, c.method) for c in background.categories],
            dict(background.document["rights"]),
            table_id="test-background-v1-bw",
        )
    assert isinstance(document, dict), document
    table = tables.parse_table(document)
    assert table.document["producer"]["versions"] == {"bw2data": "4.7", "bw2calc": "2.5.0"}
    assert [a.si_per_unit for a in table.activities] == [3.6e6, 1e6, 1.0]
    for activity, q in HAND_Q.items():
        got = table.value("climate_change_test", activity)
        assert got is not None
        assert abs(Fraction(got) - q) <= Fraction(1, 10**12) * q, (activity, got, float(q))
