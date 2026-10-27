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


def test_the_float64_assembly_is_brightways_own_matrices_unrounded(
    background: tables.UnitScoreTable,
) -> None:
    """ESC-B1: the adapter's float64 matrices, rounded to float32, are exactly the matrices
    bw2calc builds from bw2data's own processed (float32) files: same rows, columns, signs and
    implicit productions; only the precision differs."""
    import bw2calc as bc
    import bw2data as bd
    import numpy as np

    method = tuple(background.categories[0].method)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        bd.projects.set_current(PROJECT)
        node = bd.get_activity(tuple(background.activities[0].key))
        theirs = bc.LCA({node: 1.0}, method=method)
        theirs.lci()
        theirs.lcia()
        ours = bc.LCA(
            {node.id: 1.0},
            data_objs=[
                brightway._inventory_datapackage(bd, brightway._closure(bd, [node["database"]])),
                brightway._method_datapackage(bd, method),
            ],
        )
        ours.lci()
        ours.lcia()
    for matrix in ("technosphere_matrix", "biosphere_matrix", "characterization_matrix"):
        mine, reference = getattr(ours, matrix), getattr(theirs, matrix)
        assert mine.dtype == np.float64, matrix
        assert mine.shape == reference.shape, matrix
        assert (mine.astype(np.float32) != reference.astype(np.float32)).nnz == 0, matrix
    assert ours.dicts.activity == theirs.dicts.activity
    assert ours.dicts.biosphere == theirs.dicts.biosphere


def test_foreground_check_reproduces_the_hand_superposition(
    background: tables.UnitScoreTable,
) -> None:
    """`foreground_check` (A25's engine side) on exchanges whose hand score is
    `Σ a_k q_k + Σ b_j c_j` with §4.8.5's rationals, rel ≤ 1e-12; the scratch project is gone."""
    import bw2data as bd

    keys = {a.activity_id: a.key for a in background.activities}
    exchanges = [
        (keys["tb.electricity"], 2.5),
        (keys["tb.heat"], -0.75),
        (keys["tb.chemical_x"], 0.125),
    ]
    emissions = [
        (("test-biosphere-v1", "co2_fossil_air"), 0.5),
        (("test-biosphere-v1", "ch4_fossil_air"), 0.01),
    ]
    hand = (
        Fraction("2.5") * HAND_Q["tb.electricity"]
        - Fraction("0.75") * HAND_Q["tb.heat"]
        + Fraction("0.125") * HAND_Q["tb.chemical_x"]
        + Fraction("0.5")
        + Fraction(0.01) * Fraction("29.8")
    )
    before = set(bd.projects)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        score = brightway.foreground_check(
            PROJECT, exchanges, emissions, background.categories[0].method
        )
    assert isinstance(score, float), score
    assert abs(Fraction(score) - hand) <= Fraction(1, 10**12) * hand, (score, float(hand))
    assert set(bd.projects) == before
