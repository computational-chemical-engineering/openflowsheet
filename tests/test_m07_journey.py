"""M07.A00–A08, A10–A15: the journey script's rules, record, check, render and refusal paths, R0
live on the stand-in, and R2's reading of M04's verdict (M07 spec §4–§6, §11; WO-1, WO-2).

The rules are compared with the registered fixtures of `benchmarks/m07/registration.json`, whose
expectations come from the reference generator's independent implementation
(`docs/derivations/scripts/m07_reference.py`). R0's J is a regression value (spec §3 F2); its
indifference in T_in is the closed-form expectation. The dry-run record (R1 played by the stand-in,
a synthetic noise floor) is a fixture for `check` and `render` only and never W25 evidence.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import m07_journey as m07  # noqa: E402

REG: Mapping[str, Any] = m07.REG
FIXTURES: Mapping[str, Any] = REG["fixtures"]
R0_FACTS: Mapping[str, Any] = REG["journey"]["r0"]
GENERATOR = REPO_ROOT / "docs" / "derivations" / "scripts" / "m07_reference.py"
#: The dry run's synthetic noise floor at every point (a dyadic number; never a measurement).
SYNTHETIC_E = 2.0**-21
COMMIT = "0" * 40
ENVIRONMENT = {
    "lock_sha256": "1" * 64,
    "reactor_lock_sha256": "2" * 64,
    "platform": "fixture",
    "tree_clean": True,
}


def synthetic_extras(t: float, entry: Mapping[str, Any]) -> tuple[float | None, Any]:
    return SYNTHETIC_E, []


@pytest.fixture(scope="module")
def r0(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("m07-r0")
    return m07.run_r0(root, m07.standin_runner(root / "store"))


@pytest.fixture(scope="module")
def dry(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("m07-dry")
    return m07.run_journey(
        root, dry_run=True, extras=synthetic_extras, commit=COMMIT, environment=ENVIRONMENT
    )


def rederived(record: Mapping[str, Any], edit: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    """`record` with its rungs edited by `edit` and every derived member re-derived."""
    changed = copy.deepcopy(dict(record))
    edit(changed["rungs"])
    return m07.derive(changed)


def accepted(record: Mapping[str, Any]) -> list[str]:
    return m07.check(record, m07.render(record))


def r3_study(status: str, candidate: dict[str, Any] | None) -> dict[str, Any]:
    """An R3 rung as `r3_rung` writes it, for a synthetic M05 record."""
    budget = m07.budget_for("R3")
    decision = None if candidate is None else candidate["T"]
    return {
        "outcome": status,
        "study_status": status,
        "m05_record": {"path": "fixture", "sha256": "3" * 64, "carried_from": "rerun"},
        "candidate": candidate,
        "decision": decision,
        "bound_activity": m07.bound_activity(decision),
        "budget": budget.as_document(),
    }


def candidate(t: float, j: float, status: str = m07.PARENT_LOCAL_EVIDENCE) -> dict[str, Any]:
    return {
        "T": t,
        "status": status,
        "J": j,
        "e": SYNTHETIC_E,
        "half_width": None,
        "verified": True,
        "check_id": "fixture-candidate",
        "coupling_record_sha256": "4" * 64,
        "constraints": {"n": 0},
    }


def tilt(rungs: dict[str, Any]) -> None:
    """R1's J rising by 1e-9 mol/s per grid step: DECIDED at the upper bound."""
    for k, point in enumerate(rungs["R1"]["grid"]):
        point["J"] = point["J"] + k * 1e-9
    rungs["R1"].update(outcome="DECIDED", decision=693.15, bound_activity="BOUND_UPPER")


# -- A00, A01, A02 ---------------------------------------------------------------------------------


def test_a00_the_generator_check_passes() -> None:
    completed = subprocess.run(
        [sys.executable, "-I", str(GENERATOR), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_a01_the_journey_grid_is_the_registrations() -> None:
    decision = REG["journey"]["decision"]
    assert m07.GRID_LITERALS == tuple(decision["grid_literals"])
    assert [float(x) for x in m07.GRID_LITERALS] == decision["grid_K"]
    assert len(m07.GRID_LITERALS) == 9
    assert m07.GRID_LITERALS[4] == "673.15" and float(m07.GRID_LITERALS[4]) == m07.T_NOMINAL
    activities = [m07.bound_activity(float(x)) for x in m07.GRID_LITERALS]
    assert activities == ["BOUND_LOWER", *["INTERIOR"] * 7, "BOUND_UPPER"]


def test_a02_the_case_twins_differ_only_in_the_reactor_pin() -> None:
    real, standin = m07.load_loop("real"), m07.load_loop("standin")

    def unpinned(document: dict[str, Any]) -> dict[str, Any]:
        stripped = copy.deepcopy(document)
        for item in stripped["instances"]:
            if item["id"] == "reactor":
                item.pop("model")
        for key in ("revision_id", "title", "description", "provenance", "parent_revision"):
            stripped.pop(key, None)
        return stripped

    assert unpinned(real) == unpinned(standin)
    pins = {
        name: next(i["model"] for i in doc["instances"] if i["id"] == "reactor")
        for name, doc in (("real", real), ("standin", standin))
    }
    for name, pin in pins.items():
        variant = REG["journey"]["variants"][name]
        assert (pin["id"], pin["version"], pin["artifact_ref"]) == (
            variant["model_id"],
            variant["variant_id"],
            variant["sha256"],
        )
    for document in (real, standin):
        (spec,) = [s for s in document["specifications"] if s["id"] == m07.SPEC_ID]
        assert spec["value"] == 673.15


# -- A03–A07: the rules on the registered fixtures ------------------------------------------------


@pytest.mark.parametrize("fixture", FIXTURES["rung"], ids=lambda f: f["id"])
def test_a03_rung_decision(fixture: Mapping[str, Any]) -> None:
    assert len(fixture["points"]) == 9
    assert m07.rung_decision(fixture["points"]) == fixture["expected"]


def test_a03_the_rung_fixtures_cover_the_three_outcomes() -> None:
    outcomes = {f["expected"]["outcome"] for f in FIXTURES["rung"]}
    assert outcomes == {"INDIFFERENT", "DECIDED", "INCOMPLETE"}


@pytest.mark.parametrize("fixture", FIXTURES["indifference"], ids=lambda f: f["id"])
def test_a04_indifference_set(fixture: Mapping[str, Any]) -> None:
    assert m07.indifference_set(fixture["points"]) == fixture["expected"]


@pytest.mark.parametrize("fixture", FIXTURES["fe"], ids=lambda f: f["id"])
def test_a05_fidelity_effect_class(fixture: Mapping[str, Any]) -> None:
    assert m07.fe_class(fixture) == fixture["expected"]


def test_a05_the_fe_fixtures_cover_the_five_classes() -> None:
    assert len(FIXTURES["fe"]) == 10
    assert {f["expected"] for f in FIXTURES["fe"]} == {
        "FE_WORSE",
        "FE_UNCHANGED",
        "FE_CHANGED",
        "FE_WITHIN_RESOLUTION",
        "FE_NOT_DETERMINED",
    }


def reference() -> Any:
    """The reference generator as a module (its rules, independent of the journey's)."""
    if "m07_reference" not in sys.modules:
        spec = importlib.util.spec_from_file_location("m07_reference", GENERATOR)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules["m07_reference"] = module
        spec.loader.exec_module(module)
    return sys.modules["m07_reference"]


@pytest.mark.parametrize("side", ["e_before", "e_after"])
def test_a05_a_null_noise_floor_makes_the_pair_not_determined(side: str) -> None:
    """Amendment 1 A1.1 (R-420) on fe-01's numbers: a null floor on either side nulls t_after and
    names the field; read as 0 the same pair would be FE_CHANGED."""
    floors: dict[str, float | None] = {"e_before": SYNTHETIC_E, "e_after": SYNTHETIC_E, side: None}
    grid = [{"T": 673.0, "J": 0.5, "e": floors["e_before"], "verified": True}]
    made = m07.pair("P13", 673.0, (653.0, 0.5 + 2.0**-19, floors["e_after"], True), grid)
    assert made["t_after"] is None
    assert made["missing"] == [side]
    assert made["fe_class"] == "FE_NOT_DETERMINED"
    as_zero = {"t_before": 673.0, "t_after": 653.0, "j_before": 0.5, "j_after": 0.5 + 2.0**-19}
    as_zero.update({**floors, side: 0.0})
    assert reference().fe_class(as_zero) == m07.fe_class(as_zero) == "FE_CHANGED"


@pytest.mark.parametrize("fixture", FIXTURES["tc1"], ids=lambda f: f["id"])
def test_a06_truth_check(fixture: Mapping[str, Any]) -> None:
    assert (
        m07.tc1(fixture["t_after"], fixture["j_after"], fixture["e_after"], fixture["grid"])
        == (fixture["expected"])
    )


def test_a06_the_tc1_fixtures_cover_the_four_outcomes() -> None:
    assert len(FIXTURES["tc1"]) == 9
    assert {f["expected"]["outcome"] for f in FIXTURES["tc1"]} == {
        "TC1_HOLDS",
        "TC1_CONTRADICTED",
        "TC1_NO_GRID",
        "TC1_NOT_APPLICABLE",
    }


def test_a06_tc1_names_what_is_missing_and_reads_r3s_candidate(dry: Mapping[str, Any]) -> None:
    """A1.1: `tc1.missing` names the absent value; TC-1 is judged on R3's candidate, not on P13's
    t_after, which a missing floor at R1's decision nulls."""
    by_id = {f["id"]: f for f in FIXTURES["tc1"]}
    args = ("t_after", "j_after", "e_after", "grid")
    assert m07.tc1_missing(*(by_id["tc1-08-no-floor-at-best"][a] for a in args)) == ["e_B"]
    assert m07.tc1_missing(*(by_id["tc1-09-no-floor-after"][a] for a in args)) == ["e_after"]
    assert m07.tc1_missing(*(by_id["tc1-01-dominates"][a] for a in args)) == []

    def floorless_decision(rungs: dict[str, Any]) -> None:
        j = rungs["R1"]["grid"][0]["J"]
        for point in rungs["R1"]["grid"]:
            point["J"] = j
        rungs["R1"]["grid"][4]["e"] = None  # R1 decides 673.15 (INDIFFERENT); B is 653.15
        rungs["R1"].update(outcome="INDIFFERENT", decision=673.15, bound_activity="INTERIOR")
        rungs["R3"] = r3_study("DECISION_STABLE", candidate(670.0, j + 1e-9))

    record = rederived(dry, floorless_decision)
    assert record["pairs"]["P13"]["missing"] == ["e_before"]
    assert record["pairs"]["P13"]["t_after"] is None
    assert record["tc1"] == {"outcome": "TC1_HOLDS", "best_grid_T": 653.15, "missing": []}
    assert record["decision"]["label"] == "refined"
    assert accepted(record) == []


@pytest.mark.parametrize("fixture", FIXTURES["bound"], ids=lambda f: f["id"])
def test_a07_bound_activity(fixture: Mapping[str, Any]) -> None:
    assert m07.bound_activity(fixture["T"]) == fixture["expected"]


# -- A08: R0 live ----------------------------------------------------------------------------------


def test_a08_r0_is_verified_and_indifferent_at_the_nine_points(r0: Mapping[str, Any]) -> None:
    grid = r0["grid"]
    assert [p["T_literal"] for p in grid] == list(m07.GRID_LITERALS)
    assert all(p["verified"] for p in grid), [(p["T_literal"], p["outcome"]) for p in grid]
    values = [p["J"] for p in grid]
    assert max(values) - min(values) <= 1e-12 * max(values)
    assert (r0["outcome"], r0["decision"]) == (R0_FACTS["expected_outcome"], 673.15)
    assert r0["bound_activity"] == "INTERIOR"
    for value in values:
        assert (
            abs(value - R0_FACTS["J_mol_s"]) <= R0_FACTS["regression_tol_rel"] * R0_FACTS["J_mol_s"]
        )
        assert R0_FACTS["J_guard_lo"] < value <= R0_FACTS["J_max_n_balance"]


def test_a08_r0_spends_no_reactor_experiment_within_its_wall_budget(r0: Mapping[str, Any]) -> None:
    spent = r0["budget"]["spent"]
    assert spent["cold"] == 0
    assert spent["wall_s"] <= REG["journey"]["budget"]["R0"]["wall_s"]
    assert all(p["experiments"]["cold"] > 0 for p in r0["grid"])  # the stand-in's own executions
    assert all(p["X_pass"] == pytest.approx(0.25, rel=1e-12) for p in r0["grid"])


# -- A10, A11: check and render on the dry-run record ---------------------------------------------


def test_a10_check_accepts_the_dry_run_record(dry: Mapping[str, Any]) -> None:
    assert dry["synthetic_dry_run"] is True
    assert dry["rungs"]["R1"]["outcome"] in ("INDIFFERENT", "DECIDED")
    assert accepted(dry) == []


def test_a10_each_mutation_is_rejected(dry: Mapping[str, Any]) -> None:
    report = m07.render(dry)
    dropped = report.replace("## 5. Surrogate discrepancy\n", "")
    assert any("headings" in p for p in m07.check(dry, dropped))
    changed = copy.deepcopy(dict(dry))
    changed["rungs"]["R0"]["grid"][3]["J"] = changed["rungs"]["R0"]["grid"][3]["J"] * (1 + 1e-9)
    problems = m07.check(changed, report)
    assert "R0 outcome INDIFFERENT is not the rule's DECIDED" in problems
    assert "the report is not the rendering of the record" in problems
    seventh = f"7. {REG['report']['not_established'][6]}\n"
    assert seventh in report
    assert any("section 11" in p for p in m07.check(dry, report.replace(seventh, "")))
    heading = "## 12. Provenance and replay\n"
    added = report.replace(heading, heading + "\nAn optimal decision.\n")
    assert "forbidden words in the report: ['optimal']" in m07.check(dry, added)


def test_a11_render_is_deterministic_with_the_registered_sections(dry: Mapping[str, Any]) -> None:
    first, second = m07.render(dry), m07.render(copy.deepcopy(dict(dry)))
    assert first.encode() == second.encode()
    headings = [line[3:] for line in first.splitlines() if line.startswith("## ")]
    assert headings == REG["report"]["sections"]
    eleven = m07._section(first, REG["report"]["sections"][10])
    assert [line for line in eleven if line] == [
        f"{i}. {s}" for i, s in enumerate(REG["report"]["not_established"], start=1)
    ]


def test_a11_the_bound_phrase_appears_iff_a_decision_is_bound_active(
    dry: Mapping[str, Any],
) -> None:
    head = REG["report"]["bound_phrase"].split("{side}")[0]
    flat = rederived(dry, lambda r: None)
    flat_active = any(a not in (None, "INTERIOR") for _, a in m07.decision_activities(flat))
    assert (head in m07.render(flat)) == flat_active
    bound = rederived(dry, tilt)
    assert bound["decision"]["bound_activity"] == "BOUND_UPPER"
    text = m07.render(bound)
    assert m07.bound_phrase("BOUND_UPPER") in text
    assert accepted(bound) == []


# -- A12: honest outcomes are accepted when stated, rejected when not ------------------------------


def _incomplete(rungs: dict[str, Any]) -> None:
    point = rungs["R1"]["grid"][2]
    point.update(verified=False, outcome="NOT_CONVERGED", certificate=None, J=None, e=None)
    decided = m07.rung_decision(rungs["R1"]["grid"])
    rungs["R1"].update(
        outcome="INCOMPLETE",
        decision=decided["decision"],
        bound_activity=m07.bound_activity(decided["decision"]),
    )


def _budget_exhausted(rungs: dict[str, Any]) -> None:
    rungs["R3"] = r3_study("BUDGET_EXHAUSTED", None)


def _contradicted(rungs: dict[str, Any]) -> None:
    rungs["R3"] = r3_study("DECISION_STABLE", candidate(670.0, 0.25))


HONEST = {
    "R1:INCOMPLETE": (_incomplete, "INCOMPLETE"),
    "R3:BUDGET_EXHAUSTED": (_budget_exhausted, "BUDGET_EXHAUSTED"),
    "R2:SURROGATE_NOT_PROMOTABLE": (lambda r: None, "SURROGATE_NOT_PROMOTABLE"),
    "bound:journey": (tilt, "bound of the reactor model's registered domain"),
    "TC1_CONTRADICTED": (_contradicted, "TC1_CONTRADICTED"),
}


@pytest.mark.parametrize("code", sorted(HONEST))
def test_a12_an_honest_outcome_is_accepted_and_stated(dry: Mapping[str, Any], code: str) -> None:
    edit, words = HONEST[code]
    record = rederived(dry, edit)
    assert code in [item["code"] for item in record["limitations"]]
    assert accepted(record) == []
    assert words in m07.render(record)
    if code == "TC1_CONTRADICTED":
        assert record["tc1"]["outcome"] == "TC1_CONTRADICTED"
        assert record["decision"]["label"] == "grid_only"
        assert record["decision"]["reason"] == "TC1_CONTRADICTED"


@pytest.mark.parametrize("code", sorted(HONEST))
def test_a12_the_same_record_without_its_statement_is_rejected(
    dry: Mapping[str, Any], code: str
) -> None:
    edit, _ = HONEST[code]
    record = rederived(dry, edit)
    record["limitations"] = [item for item in record["limitations"] if item["code"] != code]
    problems = accepted(record)
    assert "limitations differs from its re-derivation" in problems


# -- A13: the budget is checked before each evaluation ---------------------------------------------


class CountingEvaluator:
    def __init__(self, cold: int, wall_s: float) -> None:
        self.calls = 0
        self.cold, self.wall_s = cold, wall_s

    def __call__(self, t: float, literal: str) -> dict[str, Any]:
        self.calls += 1
        entry = m07.empty_entry(t, literal)
        entry.update(
            verified=True,
            outcome="CONVERGED",
            certificate="VERIFIED",
            J=0.5,
            run_sha256="5" * 64,
            reactor_cold=self.cold,
            wall_s=self.wall_s,
        )
        return entry


@pytest.mark.parametrize(
    ("budget", "cost", "calls"),
    [
        (m07.RungBudget(10, 1e9, first_estimate=4), (4, 1.0), 2),
        (m07.RungBudget(3, 1e9, first_estimate=4), (4, 1.0), 0),
        (m07.RungBudget(60, 25.0, first_estimate=4), (4, 10.0), 2),
    ],
    ids=["cold", "first-estimate", "wall"],
)
def test_a13_a_rung_stops_before_the_call_that_would_exceed(
    budget: m07.RungBudget, cost: tuple[int, float], calls: int
) -> None:
    evaluate = CountingEvaluator(*cost)
    entries, exhausted = m07.run_grid("R1", evaluate, budget)
    assert evaluate.calls == calls
    assert exhausted and not budget.overrun
    assert [e["outcome"] for e in entries[calls:]] == ["NOT_EVALUATED(budget)"] * (9 - calls)
    rung = m07.grid_rung(entries, exhausted, budget)
    assert rung["outcome"] == "BUDGET_EXHAUSTED"
    assert m07._check_grid_rung("R1", rung) == []


def test_a13_r1_starts_from_g12s_four_experiments_per_loop() -> None:
    assert (
        m07.budget_for("R1").first_estimate == REG["journey"]["g12_facts"]["experiments_per_loop"]
    )
    assert m07.budget_for("R1").cold_cap == REG["journey"]["budget"]["R1"]["cold_experiments"]


# -- A14: no reactor environment -------------------------------------------------------------------


def test_a14_without_the_reactor_r1_and_r3_refuse_and_the_record_is_written(
    tmp_path: Path,
) -> None:
    out = tmp_path / "journey"
    code = m07.main(
        [
            "run",
            "--out",
            str(out),
            "--artifacts",
            str(tmp_path / "artifacts"),
            "--env-base",
            str(tmp_path / "no-environment"),
        ]
    )
    assert code == 3
    record = json.loads((out / m07.RECORD_NAME).read_text(encoding="utf-8"))
    refusal = m07.unsupported(m07.REACTOR_UNAVAILABLE)
    assert record["rungs"]["R1"]["outcome"] == refusal
    assert record["rungs"]["R3"]["outcome"] == refusal
    assert record["rungs"]["R0"]["outcome"] == "INDIFFERENT"
    assert record["decision"] == {
        "label": "INSUFFICIENT_EVIDENCE",
        "T": None,
        "reason": refusal,
        "bound_activity": None,
    }
    report = (out / m07.REPORT_NAME).read_text(encoding="utf-8")
    assert "The journey reports no decision" in report
    assert "The journey's decision" not in report
    assert m07.main(["check", str(out)]) == 0


def test_replay_refuses_until_wo4(tmp_path: Path) -> None:
    assert m07.main(["replay", str(tmp_path)]) == 2


# -- A15: R2 reads M04's committed verdict ---------------------------------------------------------


def test_a15_r2_is_not_promotable_with_m04s_reasons_and_no_evaluation() -> None:
    facts = REG["journey"]["m04_facts"]
    r2 = m07.r2_rung(REPO_ROOT / facts["record"])
    assert r2["outcome"] == facts["expected_r2_outcome"] == "SURROGATE_NOT_PROMOTABLE"
    assert "band_not_finite" in r2["m04_reasons"]
    assert r2["evaluations"] == facts["expected_r2_evaluations"] == 0
    assert r2["m04_record"] == {"path": facts["record"], "sha256": facts["sha256"]}
    assert m07._check_r2(r2) == []


@pytest.fixture
def promotable(tmp_path: Path) -> Iterator[Path]:
    manifest = json.loads((REPO_ROOT / REG["journey"]["m04_facts"]["record"]).read_text())
    manifest["promotion"] = {**manifest["promotion"], "verdict": "PROMOTABLE", "not_promotable": []}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    yield path


def test_a15_a_promotable_verdict_requires_nine_surrogate_evaluations(promotable: Path) -> None:
    evaluate = CountingEvaluator(0, 0.0)
    r2 = m07.r2_rung(promotable, evaluate=evaluate)
    assert evaluate.calls == 9 and r2["evaluations"] == 9
    assert r2["outcome"] == "INDIFFERENT"
    assert m07._check_r2(r2) == []
    assert m07._check_r2({**r2, "evaluations": 0}) != []
    refused = m07.r2_rung(promotable)
    assert refused["outcome"] == m07.unsupported(m07.SURROGATE_LOOP_UNAVAILABLE)
    assert refused["evaluations"] == 0


def test_a15_a_promotable_verdict_without_a_loop_is_a_registered_refusal(
    dry: Mapping[str, Any], promotable: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Amendment 1 A1.3 (R-422): PROMOTABLE with no surrogate-backed loop is
    `UNSUPPORTED(surrogate_loop_unavailable)`, zero evaluations; the record is accepted, the
    journey exits 3 (`main` returns 3 iff a rung is UNSUPPORTED) and the report states it."""
    assert m07.SURROGATE_LOOP_UNAVAILABLE in REG["journey"]["unsupported_reasons"]
    monkeypatch.setitem(m07.JOURNEY["m04_facts"], "record", str(promotable))
    refused = m07.r2_rung(promotable)
    assert (refused["outcome"], refused["evaluations"]) == (
        m07.unsupported(m07.SURROGATE_LOOP_UNAVAILABLE),
        0,
    )
    assert m07._check_r2(refused) == []
    assert m07._check_r2({**refused, "evaluations": 1}) != []

    def edit(rungs: dict[str, Any]) -> None:
        rungs["R2"] = refused
        rungs["R3"] = r3_study("DECISION_STABLE", None)

    record = rederived(dry, edit)
    assert m07.any_unsupported(record)
    assert [
        r for r in m07.RUNGS if str(record["rungs"][r]["outcome"]).startswith("UNSUPPORTED")
    ] == ["R2"]
    assert accepted(record) == []
    assert "R2 is UNSUPPORTED(surrogate_loop_unavailable)" in m07.render(record)
