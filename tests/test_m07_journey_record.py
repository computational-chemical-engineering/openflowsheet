"""M07.A20–A26 on the committed real journey (M07 spec §5, §6, §13 WO-4; Amendment 1 A1.6, A1.7).

The record `benchmarks/m07/journey/<J>/journey.json` was produced by `scripts/m07_journey.py run` at
J with the real PyMRM v3 reactor. Its numbers are measurements; these tests check what the record
must satisfy whatever the measurements are: the rules' labels against the reference generator's
independent implementation (`docs/derivations/scripts/m07_reference.py`), M05's record and its
input conditions, the accounting against the committed store archive, and the parent evaluation
every decision names. They read committed files only and run in the default gate. The replay
(A24) re-runs the journey's solves from the archive with a backend that refuses to execute; it
needs the pinned reactor environment for the handshake and is opt-in (`-m pymrm`).
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import m07_journey as m07  # noqa: E402

GENERATOR = REPO_ROOT / "docs" / "derivations" / "scripts" / "m07_reference.py"
JOURNEYS = sorted((REPO_ROOT / "benchmarks" / "m07" / "journey").glob("*/journey.json"))
SHA256 = re.compile(r"[0-9a-f]{64}")
#: M05's vocabulary (its study and candidate statuses: `study.py`, `checks.py`).
M05_STUDY_STATUSES = ("DECISION_STABLE", "ITERATION_LIMIT", "BUDGET_EXHAUSTED")
M05_CANDIDATE_STATUSES = (
    "PARENT_LOCAL_EVIDENCE",
    "PARENT_CHECK_FAILED",
    "REGIME_CHANGED",
    "PARENT_CONSTRAINT_VIOLATED",
    "PROJECTION_DISAGREES",
    "NOT_STATIONARY_AT_DELTA",
    "NOT_CHECKED",
)


def reference() -> Any:
    """The reference generator as a module (its rules, independent of the journey's)."""
    if "m07_reference" not in sys.modules:
        spec = importlib.util.spec_from_file_location("m07_reference", GENERATOR)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules["m07_reference"] = module
        spec.loader.exec_module(module)
    return sys.modules["m07_reference"]


@pytest.fixture(scope="module", params=JOURNEYS, ids=lambda p: p.parent.name[:7])
def journey(request: pytest.FixtureRequest) -> tuple[Path, dict[str, Any]]:
    path: Path = request.param
    return path.parent, json.loads(path.read_text(encoding="utf-8"))


def test_wo4_the_real_journey_is_committed() -> None:
    real = [
        p for p in JOURNEYS if not json.loads(p.read_text(encoding="utf-8"))["synthetic_dry_run"]
    ]
    assert real, "WO-4 commits the real journey record under benchmarks/m07/journey/<J>/"


def test_the_record_names_its_commit_and_a_clean_single_threaded_run(
    journey: tuple[Path, dict[str, Any]],
) -> None:
    directory, record = journey
    assert directory.name == record["commit"]
    assert record["synthetic_dry_run"] is False
    assert record["environment"]["tree_clean"] is True
    assert record["environment"]["omp_num_threads"] == "1"
    assert m07.tracked_unmodified(directory / m07.RECORD_NAME)
    assert m07.tracked_unmodified(directory / m07.ARCHIVE_NAME)


def test_a10_a11_check_accepts_the_record_and_render_gives_its_report(
    journey: tuple[Path, dict[str, Any]],
) -> None:
    directory, record = journey
    report = (directory / m07.REPORT_NAME).read_text(encoding="utf-8")
    assert m07.check(record, report) == []
    assert m07.render(record) == report


# -- A20: R1 real ----------------------------------------------------------------------------------


def test_a20_r1_has_nine_grid_records_with_j_e_and_the_reported_quantities(
    journey: tuple[Path, dict[str, Any]],
) -> None:
    _, record = journey
    r1 = record["rungs"]["R1"]
    assert [p["T_literal"] for p in r1["grid"]] == list(m07.GRID_LITERALS)
    for point in r1["grid"]:
        assert set(m07.GRID_ENTRY_KEYS) <= set(point)
        if point["outcome"] == m07.NOT_EVALUATED_BUDGET:
            assert r1["outcome"] == "BUDGET_EXHAUSTED"
            continue
        assert point["wall_s"] > 0 and set(point["experiments"]) == {
            "cold",
            "store_hit",
            "in_process",
        }
        if point["verified"]:
            for name in ("J", "e", "X_pass", "Q_preheater_W", "Q_flash_W", "n_recycle_mol_s"):
                assert isinstance(point[name], float), (point["T_literal"], name)
            assert isinstance(point["n_purge_NH3_mol_s"], float)


def test_a20_r1_is_within_its_budget_or_says_it_ran_out(
    journey: tuple[Path, dict[str, Any]],
) -> None:
    _, record = journey
    budget = record["rungs"]["R1"]["budget"]
    within = (
        budget["spent"]["cold"] <= budget["cold"] and budget["spent"]["wall_s"] <= budget["wall_s"]
    )
    assert within or record["rungs"]["R1"]["outcome"] == "BUDGET_EXHAUSTED"


# -- A21: R3 from M05's REAL record ----------------------------------------------------------------


def test_a21_r3s_m05_record_is_tracked_with_the_recorded_sha256_and_meets_conditions_1_to_5(
    journey: tuple[Path, dict[str, Any]],
) -> None:
    directory, record = journey
    r3 = record["rungs"]["R3"]
    path = REPO_ROOT / r3["m05_record"]["path"]
    assert m07.sha256_file(path) == r3["m05_record"]["sha256"]
    failed, m05, chosen = m07._r3_condition(path, m07.M05_SCHEMA, m07.tracked_unmodified)
    assert failed is None and m05 is not None and chosen is not None
    carried_from = r3["m05_record"]["carried_from"]
    if carried_from == m07.RERUN:
        assert path.parent == directory / m07.M05_RERUN_DIR
        assert r3["budget"]["wall_source"] == "journey_measured"
    else:
        assert re.fullmatch(r"[0-9a-f]{40}", carried_from)
        assert r3["budget"]["wall_source"] == "m05_record"


def test_a21_r3s_statuses_are_m05s_verbatim(journey: tuple[Path, dict[str, Any]]) -> None:
    _, record = journey
    r3 = record["rungs"]["R3"]
    m05 = json.loads((REPO_ROOT / r3["m05_record"]["path"]).read_text(encoding="utf-8"))
    assert r3["study_status"] == r3["outcome"] == m05["status"]
    assert r3["study_status"] in M05_STUDY_STATUSES
    (chosen,) = [
        c for c in m05["candidates"] if c["solves"][0]["check_id"] == m05["best"]["check_id"]
    ]
    assert r3["candidate"]["status"] == chosen["status"] in M05_CANDIDATE_STATUSES
    assert r3["candidate"]["T"] == float(next(iter(chosen["decisions"].values())))
    assert r3["budget"]["spent"]["cold"] == m05["accounting"]["budgets"]["cold_used"]


# -- A22, A23: the labels against the reference generator ------------------------------------------


@pytest.mark.parametrize("name", ["P01", "P13"])
def test_a22_the_fe_class_equals_the_reference_function_on_the_records_numbers(
    journey: tuple[Path, dict[str, Any]], name: str
) -> None:
    _, record = journey
    pair = record["pairs"][name]
    assert pair["missing"] == []
    assert pair["fe_class"] == reference().fe_class(pair)


def test_a23_tc1_equals_the_reference_function(journey: tuple[Path, dict[str, Any]]) -> None:
    _, record = journey
    candidate = record["rungs"]["R3"]["candidate"]
    expected = reference().tc1(
        {
            "t_after": candidate["T"],
            "j_after": candidate["J"] if candidate["verified"] else None,
            "e_after": candidate["e"],
            "grid": record["rungs"]["R1"]["grid"],
        }
    )
    assert {k: record["tc1"][k] for k in expected} == expected


def test_a23_every_bound_activity_equals_the_reference_function(
    journey: tuple[Path, dict[str, Any]],
) -> None:
    _, record = journey
    decisions = [(name, record["rungs"][name]) for name in m07.RUNGS]
    decisions.append(("journey", record["decision"]))
    for name, decided in decisions:
        t = decided.get("decision", decided.get("T"))
        expected = None if t is None else reference().bound_activity(t)
        assert decided["bound_activity"] == expected, name


def test_a23_every_decision_has_p3s_values_and_margins(
    journey: tuple[Path, dict[str, Any]],
) -> None:
    _, record = journey
    for name in ("R0", "R1", "R3", "journey"):
        check = record["parent_checks"][name]
        assert check is not None and check["constraints"], name
        for item in check["constraints"]:
            assert isinstance(item["value"], float | int) and isinstance(
                item["margin"], float | int
            )
            assert (item["margin"] >= 0) == item["holds"], (name, item["constraint_id"])


# -- A25: accounting against the store archive -----------------------------------------------------


def test_a25_the_rung_totals_are_their_points_sums_and_the_archive_holds_every_execution(
    journey: tuple[Path, dict[str, Any]],
) -> None:
    directory, record = journey
    accounting = record["accounting"]
    for name in m07.GRID_RUNGS:
        grid = record["rungs"][name]["grid"]
        for kind in ("cold", "store_hit", "in_process"):
            assert accounting[name]["experiments"][kind] == sum(
                p["experiments"][kind] for p in grid
            )
    resolve = record["rungs"]["R3"]["t_star_resolve"]
    assert accounting["t_star_resolve"] == resolve
    assert accounting["journey"]["reactor_cold"] == (
        accounting["R1"]["reactor_cold"] + accounting["R3"]["reactor_cold"] + resolve["cold"]
    )
    archive = json.loads((directory / m07.ARCHIVE_NAME).read_bytes())
    kinds = [
        json.loads(text)["execution"]["kind"]
        for key, text in archive.items()
        if "/attempts/" in key
    ]
    assert kinds.count("out_of_process") == (
        sum(accounting[name]["experiments"]["cold"] for name in m07.GRID_RUNGS) + resolve["cold"]
    )
    assert kinds.count("in_process") == (
        sum(accounting[name]["experiments"]["in_process"] for name in m07.GRID_RUNGS)
        + resolve["in_process"]
    )


def test_a25_every_budget_is_respected_or_exhausted(journey: tuple[Path, dict[str, Any]]) -> None:
    _, record = journey
    for name in m07.RUNGS:
        rung = record["rungs"][name]
        spent, budget = rung["budget"]["spent"], rung["budget"]
        assert (spent["cold"] <= budget["cold"] and spent["wall_s"] <= budget["wall_s"]) or rung[
            "outcome"
        ] == "BUDGET_EXHAUSTED", name


# -- A26: every decision names a parent evaluation -------------------------------------------------


def test_a26_every_decision_names_a_parent_evaluation(journey: tuple[Path, dict[str, Any]]) -> None:
    directory, record = journey
    grid = {p["T"]: p for p in record["rungs"]["R1"]["grid"]}
    rungs = record["rungs"]
    decisions = {
        "R0": rungs["R0"]["decision"],
        "R1": rungs["R1"]["decision"],
        "R3": rungs["R3"]["decision"],
        "journey": record["decision"]["T"],
    }
    for name, check in record["parent_checks"].items():
        assert check is not None and SHA256.fullmatch(check["run_sha256"]), name
        if check["kind"] == "grid_point":
            assert check["run_sha256"] == grid[decisions[name]]["run_sha256"], name
        else:
            assert check["kind"] == "targeted_check"
            assert decisions[name] == rungs["R3"]["candidate"]["T"], name
            assert check["run_sha256"] == rungs["R3"]["candidate"]["coupling_record_sha256"]


def test_a26_a_re_run_targeted_check_is_the_committed_coupling_record(
    journey: tuple[Path, dict[str, Any]],
) -> None:
    from openflowsheet.canonical import document_sha256

    directory, record = journey
    r3 = record["rungs"]["R3"]
    if r3["m05_record"]["carried_from"] != m07.RERUN:
        pytest.skip("a carried M05 record's coupling records are M05's (its own G10 evidence)")
    stem = (REPO_ROOT / r3["m05_record"]["path"]).with_suffix("")
    coupling = stem.with_suffix(".coupling") / f"{r3['candidate']['check_id']}.json"
    sha = document_sha256(json.loads(coupling.read_text(encoding="utf-8")))
    assert sha == record["parent_checks"]["R3"]["run_sha256"]


# -- A24: replay, opt-in (the reactor environment's handshake; nothing executes) ------------------


@pytest.mark.pymrm
def test_a24_replay_reproduces_the_record_bitwise(
    journey: tuple[Path, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    directory, record = journey
    monkeypatch.setenv("OMP_NUM_THREADS", record["environment"]["omp_num_threads"])
    assert m07.main(["replay", str(directory)]) == 0
