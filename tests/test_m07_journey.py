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
import math
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
    """An R3 rung as `r3_rung` writes it for a carried synthetic M05 record (A1.6: M05's cold
    copied, no spent wall recorded)."""
    budget = m07.budget_for("R3").as_document()
    budget["spent"] = {"cold": 63, "wall_s": None}
    budget["wall_source"] = None
    decision = None if candidate is None else candidate["T"]
    return {
        "outcome": status,
        "study_status": status,
        "m05_record": {"path": "fixture", "sha256": "3" * 64, "carried_from": "c" * 40},
        "candidate": candidate,
        "decision": decision,
        "bound_activity": m07.bound_activity(decision),
        "budget": budget,
        "store_hits": 0,
        "limitations": ["R3:m05_wall_unrecorded"],
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
    # A1.4 (R-423): the stand-in is in-process by registration, so no point spends a cold reactor
    # experiment; its own executions are `in_process`.
    assert all(p["experiments"]["cold"] == 0 for p in r0["grid"])
    assert all(p["experiments"]["in_process"] > 0 for p in r0["grid"])


def test_a08_r0s_reported_quantities_meet_their_closed_forms(r0: Mapping[str, Any]) -> None:
    """A1.5 (R-424), at each of the nine points: X_pass = 0.25 (the stand-in's xi = 0.25 n_N2,in);
    recycle and purge flows T-independent (F2); the preheater heats and the flash cools, both
    duties strictly monotone in T (c_p > 0 at fixed flows and S2 state)."""
    grid = r0["grid"]
    for point in grid:
        assert abs(point["X_pass"] - R0_FACTS["X_pass"]) <= R0_FACTS["X_pass_tol_abs"]
    tol = REG["journey"]["rung_flatness_tol_rel"]
    for key in ("n_recycle_mol_s", "n_purge_NH3_mol_s"):
        values = [p[key] for p in grid]
        assert max(values) - min(values) <= tol * max(abs(v) for v in values), key
    q_heat = [p["Q_preheater_W"] for p in grid]
    q_flash = [p["Q_flash_W"] for p in grid]
    assert all(q > 0 for q in q_heat) and all(
        b > a for a, b in zip(q_heat[:-1], q_heat[1:], strict=True)
    )
    assert all(q < 0 for q in q_flash) and all(
        b < a for a, b in zip(q_flash[:-1], q_flash[1:], strict=True)
    )
    assert all(p["extrapolated"] == 0 for p in grid)  # the final iterate is within the domain


def _coupling(*statuses: str) -> dict[str, Any]:
    return {
        "frozen": {"reactor": {"fingerprint": {"kind": "in_process"}}},
        "iterations": [
            {"units": {"reactor": {"attempts": [{}], "result": {"envelope": {"domain_status": s}}}}}
            for s in statuses
        ],
    }


def test_a08_extrapolated_counts_only_the_last_coupling_iteration() -> None:
    """A1.5: iterations before the last are the solve's path, not its result."""
    experiments, extrapolated = m07.coupling_attribution(
        _coupling("extrapolated", "within_data_domain")
    )
    assert extrapolated == 0
    assert experiments == {"cold": 0, "store_hit": 0, "in_process": 2}
    assert m07.coupling_attribution(_coupling("within_data_domain", "extrapolated"))[1] == 1
    assert m07.coupling_attribution(None) == ({"cold": 0, "store_hit": 0, "in_process": 0}, 0)


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


def test_a10_a_rungs_spent_cold_is_its_points_sum(dry: Mapping[str, Any]) -> None:
    """A1.4: Σₖ experiments.cold = the rung's budget.spent.cold."""
    changed = copy.deepcopy(dict(dry))
    changed["rungs"]["R0"]["grid"][0]["experiments"]["cold"] = 1
    assert "R0 spent cold 0 is not its points' sum 1" in m07.check(changed, None)


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


def test_a12_the_grid_only_decision_is_r1s_rung_decision(dry: Mapping[str, Any]) -> None:
    """A1.8 (R-427): with nine equal J, R1 is INDIFFERENT and decides 673.15 K; the journey's
    grid-only decision is that, not the best grid point (653.15 K, BOUND_LOWER, by the tie rule)."""

    def flat(rungs: dict[str, Any]) -> None:
        j = rungs["R1"]["grid"][0]["J"]
        for point in rungs["R1"]["grid"]:
            point["J"] = j
        rungs["R3"] = m07.unsupported_rung("R3", m07.M05_UNAVAILABLE)
        rungs["R1"].update(outcome="INDIFFERENT", decision=673.15, bound_activity="INTERIOR")

    record = rederived(dry, flat)
    assert record["rungs"]["R1"]["outcome"] == "INDIFFERENT"
    assert m07.best_point(record["rungs"]["R1"]["grid"])["T"] == 653.15
    assert record["decision"] == {
        "label": "grid_only",
        "T": 673.15,
        "reason": m07.unsupported(m07.M05_UNAVAILABLE),
        "bound_activity": "INTERIOR",
    }
    assert accepted(record) == []


def test_a12_a_constraints_margin_is_positive_when_it_holds(dry: Mapping[str, Any]) -> None:
    """A1.7 (R-426): margin = bound - value for `<=`, value - bound for `>=`; check rejects a
    constraint whose margin is not that."""
    upper = {"constraint_id": "u", "value": 1.0, "bound": 1.5, "sense": "<=", "scale": 1.0}
    lower = {"constraint_id": "l", "value": 1.0, "bound": 1.5, "sense": ">=", "scale": 1.0}
    assert m07.with_margin(upper)["margin"] == 0.5
    assert m07.with_margin(lower)["margin"] == -0.5
    assert m07.with_margin({**lower, "value": 2.0})["margin"] == 0.5
    with pytest.raises(ValueError):
        m07.with_margin({**upper, "sense": "=="})
    changed = copy.deepcopy(dict(dry))
    changed["rungs"]["R1"]["grid"][0]["constraints"] = [{**m07.with_margin(upper), "margin": -0.5}]
    assert "R1 653.15: a constraint's margin is not A1.7's" in m07.check(changed, None)
    changed["rungs"]["R1"]["grid"][0]["constraints"] = [m07.with_margin(upper)]
    assert not [p for p in m07.check(changed, None) if "margin" in p]


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
            experiments={"cold": self.cold, "store_hit": 0, "in_process": 0},
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


def test_a13_check_rederives_where_the_budget_stopped(dry: Mapping[str, Any]) -> None:
    """A1.2 (R-421): `check` re-derives the stop from the recorded costs in grid order and
    rejects a point relabelled NOT_EVALUATED(budget) while budget remains, and a point evaluated
    after the stop."""
    relabelled = copy.deepcopy(dict(dry))
    last = relabelled["rungs"]["R1"]["grid"][8]
    relabelled["rungs"]["R1"]["grid"][8] = {
        **m07.empty_entry(last["T"], last["T_literal"]),
        "outcome": m07.NOT_EVALUATED_BUDGET,
    }
    problems = m07.check(relabelled, None)
    assert "R1 693.15 is NOT_EVALUATED(budget) with budget left" in problems

    budget = m07.RungBudget(10, 1e9, first_estimate=4)
    evaluate = CountingEvaluator(4, 1.0)
    entries, exhausted = m07.run_grid("R1", evaluate, budget)
    rung = m07.grid_rung(entries, exhausted, budget)
    assert m07._check_stop("R1", rung) == []
    late = copy.deepcopy(rung)
    late["grid"][2] = evaluate(late["grid"][2]["T"], late["grid"][2]["T_literal"])
    assert "R1 663.15 was evaluated after the budget stop" in m07._check_stop("R1", late)


def test_a13_a_points_wall_includes_its_parent_extras() -> None:
    """A1.2 item 2: the extras run inside the point's timing."""
    ticks = iter(float(k) for k in range(100))
    budget = m07.RungBudget(60, 1e9, first_estimate=4)
    entries, _ = m07.run_grid(
        "R1", CountingEvaluator(0, 0.5), budget, synthetic_extras, lambda: next(ticks)
    )
    assert [e["wall_s"] for e in entries] == [1.5] * 9
    assert budget.wall_s == 13.5


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


# -- A21 (WO-2 part): R3's input conditions, carry anchor and accounting (Amendment 1 A1.6) --------

T_STAR = 653.1500010581631  # M05's LOOP-R best decision (wp/M05 5961915), a non-grid binary64
C_M = "d" * 40


def m05_study(**edits: Any) -> dict[str, Any]:
    """A synthetic M05 study record with what A1.6 reads: its targeted check solved the journey's
    case document at T*."""
    from openflowsheet.canonical import document_sha256

    revision = document_sha256(m07.document_at(m07.load_loop("real"), T_STAR))
    record: dict[str, Any] = {
        "schema_version": "trust-region-study-v1",
        "study_id": "c1-trf-study-v1",
        "status": "DECISION_STABLE",
        "environment": {},
        "best": {"check_id": "cand-1-P1", "decisions": {"preheater.T_spec": T_STAR}},
        "candidates": [
            {
                "candidate_id": "cand-1",
                "decisions": {"preheater.T_spec": T_STAR},
                "status": m07.PARENT_LOCAL_EVIDENCE,
                "noise_floor": {"e_star": 1.25e-6},
                "indifference_halfwidth": {"preheater.T_spec": None},
                "checks": {"P3": {"pass": True, "values": {"n": 4}}},
                "solves": [
                    {
                        "check_id": "cand-1-P1",
                        "revision_sha256": revision,
                        "outcome": "CONVERGED",
                        "certificate": "VERIFIED",
                        "objective": 0.4940269880217402,
                        "coupling_record_sha256": "7" * 64,
                    }
                ],
            }
        ],
        "accounting": {
            "totals": {"store_hits": 5, "trf_cold": 40, "parent_executions": 23},
            "budgets": {
                "budget_id": "M05-budget-v1",
                "configuration": "REAL",
                "study_wall_s": 3600.0,
                "cold_used": 63,
            },
        },
    }
    for path, value in edits.items():
        *parents, leaf = path.split(".")
        node = record
        for key in parents:
            node = node[key]
        if value is None:
            node.pop(leaf)
        else:
            node[leaf] = value
    return record


@pytest.fixture
def m05_inputs(tmp_path: Path) -> tuple[Path, Path]:
    """A schema demanding `study_id`, and an evidence directory for the manifest anchor."""
    schema = tmp_path / "schema.json"
    schema.write_text(json.dumps({"type": "object", "required": ["study_id"]}), encoding="utf-8")
    return schema, tmp_path / "evidence" / "M05"


def carried(
    tmp_path: Path, inputs: tuple[Path, Path], record: dict[str, Any], *, anchor: bool = True
) -> dict[str, Any]:
    schema, evidence = inputs
    path = tmp_path / "study.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    if anchor:
        (evidence / C_M).mkdir(parents=True, exist_ok=True)
        manifest = {"status": "tested", "artifacts": [{"sha256": m07.sha256_file(path)}]}
        (evidence / C_M / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return m07.r3_rung(
        path,
        schema_path=schema,
        evidence=evidence,
        tracked=lambda p: True,
        identical=lambda a: True,
    )


@pytest.mark.parametrize(
    ("condition", "edits"),
    [
        (1, {"study_id": None}),
        (2, {"study_id": "c1-trf-study-v0"}),
        (3, {"accounting.budgets.configuration": "in_process"}),
        (4, {}),  # the targeted check solved another document (its revision is replaced below)
        (5, {}),
    ],
)
def test_a21_r3_rejects_a_record_failing_an_input_condition(
    tmp_path: Path, m05_inputs: tuple[Path, Path], condition: int, edits: dict[str, Any]
) -> None:
    record = m05_study(**edits)
    if condition == 4:
        record["candidates"][0]["solves"][0]["revision_sha256"] = "a8de3fc5" + "0" * 56
    path = tmp_path / "study.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    schema, evidence = m05_inputs
    r3 = m07.r3_rung(path, schema_path=schema, evidence=evidence, tracked=lambda p: condition != 5)
    assert r3["outcome"] == m07.unsupported(m07.M05_UNAVAILABLE)
    assert r3["limitations"] == [f"R3:record_rejected:{condition}"]
    assert r3["decision"] is None and "candidate" not in r3


def test_a21_r3_is_carried_through_the_manifest_anchor_without_a_wall(
    tmp_path: Path, m05_inputs: tuple[Path, Path], dry: Mapping[str, Any]
) -> None:
    r3 = carried(tmp_path, m05_inputs, m05_study())
    assert r3["outcome"] == "DECISION_STABLE"
    assert r3["m05_record"]["carried_from"] == C_M != m07.RERUN
    assert (r3["decision"], r3["candidate"]["J"], r3["candidate"]["e"]) == (
        T_STAR,
        0.4940269880217402,
        1.25e-6,
    )
    assert r3["budget"]["spent"] == {"cold": 63, "wall_s": None}  # cold_used, never trf + parent
    assert r3["budget"]["wall_source"] is None and r3["store_hits"] == 5
    assert r3["limitations"] == ["R3:m05_wall_unrecorded"]

    def edit(rungs: dict[str, Any]) -> None:
        rungs["R3"] = r3

    record = rederived(dry, edit)
    assert accepted(record) == []
    assert "R3:m05_wall_unrecorded" in [item["code"] for item in record["limitations"]]
    assert record["accounting"]["journey"]["wall_s"] is None
    defaulted = rederived(record, lambda rungs: rungs["R3"]["m05_record"].update(carried_from="x"))
    assert any("carried_from" in p for p in accepted(defaulted))
    zero_wall = copy.deepcopy(record)
    zero_wall["rungs"]["R3"]["budget"]["spent"]["wall_s"] = 0.0
    assert any("m05_wall_unrecorded" in p for p in m07.check(zero_wall, None))


def test_a21_r3_reads_m05s_stated_run_commit_and_wall(
    tmp_path: Path, m05_inputs: tuple[Path, Path]
) -> None:
    """A1.6 items 2.1 and 4: M05's REAL record states `provenance` {run_commit, tree_clean,
    wall_s} (M05 build log S65); that commit is the anchor and that wall R3's, from `m05_record`."""
    stated = {"run_commit": "c" * 40, "tree_clean": True, "wall_s": 1454.5}
    r3 = carried(tmp_path, m05_inputs, m05_study(provenance=stated), anchor=False)
    assert r3["m05_record"]["carried_from"] == "c" * 40
    assert r3["budget"]["spent"] == {"cold": 63, "wall_s": 1454.5}
    assert (r3["budget"]["wall_source"], r3["limitations"]) == ("m05_record", [])
    assert m07._check_r3(r3) == []
    dirty = carried(tmp_path, m05_inputs, m05_study(provenance={**stated, "tree_clean": False}))
    assert dirty["m05_record"]["carried_from"] == C_M  # a dirty run states no commit


def test_a21_r3_without_an_anchor_or_a_cold_count_says_so(
    tmp_path: Path, m05_inputs: tuple[Path, Path]
) -> None:
    unanchored = carried(tmp_path, m05_inputs, m05_study(), anchor=False)
    assert unanchored["outcome"] == m07.unsupported(m07.M05_UNAVAILABLE)
    assert unanchored["limitations"] == ["R3:carry_anchor_missing"]
    uncounted = carried(tmp_path, m05_inputs, m05_study(**{"accounting.budgets.cold_used": None}))
    assert uncounted["budget"]["spent"]["cold"] is None
    assert uncounted["limitations"] == ["R3:m05_cold_unrecorded", "R3:m05_wall_unrecorded"]
    assert m07._check_r3(uncounted) == []


def test_a21_the_carry_identity_is_the_determining_files_at_the_anchor_and_j() -> None:
    """Spec §4.6: `carry.journey_files` as pathspecs; HEAD is identical to itself; a commit git does
    not know is not."""
    assert m07.carry_paths() == (
        "src/openflowsheet",
        "benchmarks/m02",
        "benchmarks/m04",
        "benchmarks/m05",
        "requirements.lock",
        m07.REACTOR_LOCK,
    )
    assert (REPO_ROOT / m07.REACTOR_LOCK).is_file()
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert m07.carry_identical(head) is True
    assert m07.carry_identical("0" * 40) is False


def test_a21_a_record_that_does_not_carry_is_re_run_at_j(
    tmp_path: Path, m05_inputs: tuple[Path, Path]
) -> None:
    """A1.6 items 2.3 and 3: no anchor, or determining files that differ at J, re-run M05's study
    (its record then carried_from `rerun`, its wall the journey's measurement); without a re-run,
    R3 refuses and says which."""
    schema, evidence = m05_inputs
    stated = {"run_commit": "c" * 40, "tree_clean": True, "wall_s": 1454.5}
    path = tmp_path / "study.json"
    path.write_text(json.dumps(m05_study(provenance=stated)), encoding="utf-8")
    rerun_path = tmp_path / "m05" / "rerun.json"
    rerun_path.parent.mkdir()
    rerun_path.write_text(json.dumps(m05_study(**{"accounting.budgets.cold_used": 51})), "utf-8")
    calls: list[int] = []

    def rerun() -> tuple[Path, float]:
        calls.append(1)
        return rerun_path, 1500.25

    def r3(**kw: Any) -> dict[str, Any]:
        return m07.r3_rung(
            path, schema_path=schema, evidence=evidence, tracked=lambda p: True, **kw
        )

    differs = r3(identical=lambda a: False)
    assert differs["outcome"] == m07.unsupported(m07.M05_UNAVAILABLE)
    assert differs["limitations"] == ["R3:carry_identity_differs"]
    rerun_r3 = r3(identical=lambda a: False, rerun=rerun)
    assert calls == [1] and rerun_r3["m05_record"]["carried_from"] == m07.RERUN
    assert rerun_r3["m05_record"]["sha256"] == m07.sha256_file(rerun_path)
    assert rerun_r3["budget"]["spent"] == {"cold": 51, "wall_s": 1500.25}
    assert rerun_r3["budget"]["wall_source"] == "journey_measured"
    assert m07._check_r3(rerun_r3) == []
    assert r3(identical=lambda a: True, rerun=rerun)["m05_record"]["carried_from"] == "c" * 40
    assert calls == [1]  # a carried record is not re-run
    path.write_text(json.dumps(m05_study()), encoding="utf-8")  # no anchor at all
    assert r3(rerun=rerun)["m05_record"]["carried_from"] == m07.RERUN and calls == [1, 1]


# -- A23, A25 (WO-4 part): the T* re-solve (Amendment 1 A1.7) --------------------------------------

J_STAR = 0.4940269880217402  # `m05_study`'s targeted-check objective
P3_VALUES = [
    {"constraint_id": "h2_limit", "value": 0.25, "bound": 0.5, "sense": "<=", "scale": 1.0},
    {"constraint_id": "n_tube", "value": 2.0, "bound": 1.5, "sense": ">=", "scale": 1.0},
]


def mock_resolver(objective: float, cold: int = 0) -> Callable[[float], Any]:
    """A mock parent at T*: certified, `objective`, M05 P3 values, the given cold count."""

    def resolve(t: float) -> tuple[float | None, bool, list[dict[str, Any]] | None, Any]:
        assert t == T_STAR
        experiments = {"cold": cold, "store_hit": 4 - cold, "in_process": 0}
        return objective, True, copy.deepcopy(P3_VALUES), experiments

    return resolve


def resolved_record(
    tmp_path: Path, inputs: tuple[Path, Path], dry: Mapping[str, Any], objective: float, cold: int
) -> dict[str, Any]:
    clock = iter([10.0, 13.5])
    r3 = carried(tmp_path, inputs, m05_study())
    m07.apply_t_star_resolve(r3, mock_resolver(objective, cold), lambda: next(clock))
    return rederived(dry, lambda rungs: rungs.__setitem__("R3", r3))


def test_a23_a_bitwise_equal_t_star_re_solve_gives_r3s_values_and_margins(
    tmp_path: Path, m05_inputs: tuple[Path, Path], dry: Mapping[str, Any]
) -> None:
    record = resolved_record(tmp_path, m05_inputs, dry, J_STAR, cold=1)
    r3 = record["rungs"]["R3"]
    assert r3["t_star_resolve"] == {"cold": 1, "store_hit": 3, "in_process": 0, "wall_s": 3.5}
    assert [c["margin"] for c in r3["candidate"]["constraints"]] == [0.25, 0.5]
    assert "R3:j_star_not_reproduced" not in r3["limitations"]
    assert accepted(record) == []
    assert record["parent_checks"]["R3"]["constraints"] == r3["candidate"]["constraints"]
    totals = record["accounting"]
    assert totals["t_star_resolve"] == r3["t_star_resolve"]
    assert (
        totals["journey"]["reactor_cold"] == sum(totals[n]["reactor_cold"] for n in m07.RUNGS) + 1
    )  # the re-solve counts in the journey's totals, not in M05's spend
    assert totals["R3"]["reactor_cold"] == 63
    wrong = copy.deepcopy(record)
    wrong["rungs"]["R3"]["candidate"]["constraints"][1]["margin"] = -0.5
    assert any("margin" in p for p in m07.check(wrong, None))


def test_a23_an_unequal_t_star_re_solve_gives_null_values_and_the_limitation(
    tmp_path: Path, m05_inputs: tuple[Path, Path], dry: Mapping[str, Any]
) -> None:
    record = resolved_record(tmp_path, m05_inputs, dry, J_STAR + 2.0**-53, cold=0)
    r3 = record["rungs"]["R3"]
    assert r3["candidate"]["constraints"] is None
    assert r3["limitations"][-1] == "R3:j_star_not_reproduced"
    assert (r3["candidate"]["J"], r3["candidate"]["e"]) == (J_STAR, 1.25e-6)  # still serve P13
    assert accepted(record) == []
    unstated = copy.deepcopy(record)
    unstated["rungs"]["R3"]["limitations"].remove("R3:j_star_not_reproduced")
    assert any("j_star_not_reproduced" in p for p in m07.check(unstated, None))


def test_a23_a_real_record_needs_the_t_star_re_solve(
    tmp_path: Path, m05_inputs: tuple[Path, Path], dry: Mapping[str, Any]
) -> None:
    r3 = carried(tmp_path, m05_inputs, m05_study())
    record = rederived(dry, lambda rungs: rungs.__setitem__("R3", r3))
    record["synthetic_dry_run"] = False
    record = m07.derive(record)
    assert "R3's verified candidate has no T* re-solve (A1.7)" in m07.check(record, None)


def test_the_environment_is_taken_before_any_rung_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R3's re-run writes under `--out`; a tree read after it is dirty (build log J26)."""
    order: list[str] = []
    monkeypatch.setattr(
        m07, "environment_block", lambda: order.append("environment") or ENVIRONMENT
    )
    run_r0 = m07.run_r0

    def recorded_r0(*args: Any, **kwargs: Any) -> dict[str, Any]:
        order.append("R0")
        return run_r0(*args, **kwargs)

    monkeypatch.setattr(m07, "run_r0", recorded_r0)
    record = m07.run_journey(tmp_path, dry_run=True, extras=synthetic_extras, commit=COMMIT)
    assert order == ["environment", "R0"]
    assert record["environment"] == ENVIRONMENT


# -- A24: replay (spec §6.4, Amendment 1 A1.7), on a dry run: the mechanics without the reactor --


@pytest.fixture(scope="module")
def dry_run_dir(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """`run --dry-run` through the CLI, under OMP_NUM_THREADS=1: its record and its archive."""
    root = tmp_path_factory.mktemp("m07-dry-cli")
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("OMP_NUM_THREADS", "1")
        code = m07.main(["run", "--dry-run", "--out", str(root / "out"), "--artifacts", str(root)])
    assert code == 3  # R3: no M05 record is passed (A14's exit; the record is written)
    yield root / "out"


def copied(directory: Path, target: Path) -> Path:
    for name in (m07.RECORD_NAME, m07.REPORT_NAME, m07.ARCHIVE_NAME):
        (target / name).write_bytes((directory / name).read_bytes())
    return target


def test_a24_run_writes_the_store_archive(dry_run_dir: Path) -> None:
    archive = json.loads((dry_run_dir / m07.ARCHIVE_NAME).read_bytes())
    record = json.loads((dry_run_dir / m07.RECORD_NAME).read_text(encoding="utf-8"))
    attempts = [key for key in archive if "/attempts/" in key]
    executions = sum(
        e["experiments"]["cold"] + e["experiments"]["in_process"]
        for rung in m07.GRID_RUNGS
        for e in record["rungs"][rung]["grid"]
    )
    assert len(attempts) == executions > 0


def test_a24_replay_reproduces_a_dry_run_bitwise(
    dry_run_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("OMP_NUM_THREADS", "1")
    assert m07.main(["replay", str(dry_run_dir)]) == 0
    assert capsys.readouterr().out.strip().endswith("replay: bitwise")


def test_a24_replay_refuses_on_a_thread_setting_other_than_the_records(
    dry_run_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("OMP_NUM_THREADS", "2")
    assert m07.main(["replay", str(dry_run_dir)]) == 2
    assert "omp_num_threads differs" in capsys.readouterr().out


def test_a24_replay_refuses_without_the_archive(
    dry_run_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OMP_NUM_THREADS", "1")
    directory = copied(dry_run_dir, tmp_path)
    (directory / m07.ARCHIVE_NAME).unlink()
    assert m07.main(["replay", str(directory)]) == 2


def test_a24_replay_reports_a_number_the_record_does_not_reproduce(
    dry_run_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OMP_NUM_THREADS", "1")
    directory = copied(dry_run_dir, tmp_path)
    record = json.loads((directory / m07.RECORD_NAME).read_text(encoding="utf-8"))
    point = record["rungs"]["R1"]["grid"][3]
    point["J"] = math.nextafter(point["J"], math.inf)
    (directory / m07.RECORD_NAME).write_text(m07.dumps(record), encoding="utf-8")
    _, found = m07.replay_journey(directory, tmp_path / "scratch")
    assert any(line.startswith("rungs.R1.grid[3].J: ") for line in found)
    assert m07.main(["replay", str(directory)]) == 1


def test_a24_a_request_the_archive_cannot_serve_is_a_difference_not_an_execution(
    dry_run_dir: Path, tmp_path: Path
) -> None:
    directory = copied(dry_run_dir, tmp_path)
    archive = json.loads((directory / m07.ARCHIVE_NAME).read_bytes())
    dropped = sorted(key for key in archive if key.endswith("/result.json"))[0]
    del archive[dropped]
    (directory / m07.ARCHIVE_NAME).write_text(json.dumps(archive), encoding="utf-8")
    _, found = m07.replay_journey(directory, tmp_path / "scratch")
    assert any(line.startswith("replay diverged: a cold execution") for line in found)


def test_a24_a_replayed_evaluation_counts_store_hits_only() -> None:
    assert m07.replay_experiments({"cold": 4, "store_hit": 1, "in_process": 2}) == {
        "cold": 0,
        "in_process": 0,
        "store_hit": 7,
    }


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
