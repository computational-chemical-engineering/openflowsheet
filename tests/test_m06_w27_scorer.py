"""M06 WO-16f/h: the W27 scorer — W27-A30…A34, A40 and the twenty states W27-S01…S20 (G15).

Registration §11 (per-run scoring), §12 (bounds) and §14.2–§14.3. The tolerance boundaries are the
registered ones (A30–A32); the states are built by `benchmarks.m06.w27.stubs` — stub sessions
with no model — and scored by the production scorer, its system checks replaying each exported
`VERIFIED` bundle in a fresh process. The non-`CANDIDATE` states run through the real harness and
need the pinned archive (the card); they skip without it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from benchmarks.m06.w27 import registration, scorer, stubs

ARCHIVE_PRESENT = (registration.ARCHIVE_DIR / "cases").is_dir()
needs_archive = pytest.mark.skipif(
    not ARCHIVE_PRESENT, reason="pinned archive absent (scripts/m06_w27_acquire.py)"
)


# =================================================================================================
# W27-A30…A34: the stream check
# =================================================================================================


def test_a30_temperature_boundary() -> None:
    assert scorer.within_tolerance("temperature", 351.999, 350.0)
    assert not scorer.within_tolerance("temperature", 352.001, 350.0)


def test_a31_pressure_boundary() -> None:
    assert scorer.within_tolerance("pressure", 101_099.0, 1.0e5)
    assert not scorer.within_tolerance("pressure", 101_101.0, 1.0e5)


def test_a32_flow_boundary_uses_the_port_total() -> None:
    assert scorer.within_tolerance("flow", 10.503, 10.0, 40.0)
    assert not scorer.within_tolerance("flow", 10.505, 10.0, 40.0)
    # An absolute term from the component's own flow (0.501) would fail 10.503.
    assert not scorer.within_tolerance("flow", 10.503, 10.0, 10.0)


def _port(name: str, t: float, p: float, n: dict[str, float]) -> dict[str, Any]:
    judged: dict[str, float] = {"T": t, "P": p} | {f"n.{c}": v for c, v in n.items()}
    return {"port": name, "judged": judged, "unjudged": {}, "port_total": sum(n.values())}


def _connection(name: str, t: float, p: float, n: dict[str, float]) -> dict[str, Any]:
    return {"connection": name, "values": {"T": t, "P": p} | {f"n.{c}": v for c, v in n.items()}}


def test_a33_assignment_is_by_value_not_by_name() -> None:
    ports = [
        _port("vapor.inlet", 360.0, 1.0e5, {"1333-74-0": 9.0}),
        _port("liquid.inlet", 330.0, 1.0e5, {"1333-74-0": 1.0}),
    ]
    swapped = [
        _connection("S-vapor", 330.0, 1.0e5, {"1333-74-0": 1.0}),
        _connection("S-liquid", 360.0, 1.0e5, {"1333-74-0": 9.0}),
    ]
    check = scorer.stream_check(ports, swapped, "pass")
    assert check["status"] == "pass"
    assert check["assignment"] == {"vapor.inlet": "S-liquid", "liquid.inlet": "S-vapor"}
    one = scorer.stream_check(ports, swapped[:1], "pass")
    assert one["status"] == "fail"


def test_a34_residual_check_failure_is_unjudged() -> None:
    ports = [_port("p", 350.0, 1.0e5, {"1333-74-0": 10.0})]
    far = [_connection("S", 400.0, 1.0e5, {"1333-74-0": 10.0})]
    assert scorer.stream_check(ports, far, "fail")["status"] == "unjudged"
    assert scorer.stream_check(ports, far, "absent")["status"] == "unjudged"
    assert scorer.stream_check(ports, far, "pass")["status"] == "fail"
    assert scorer.stream_check([], far, "pass")["status"] == "unjudged"


def test_reference_ports_read_streams_csv(tmp_path: Path) -> None:
    case_dir = stubs.candidate_case_dir(tmp_path)
    (port,) = scorer.reference_ports(case_dir, ["product.inlet"])
    assert port["judged"] == {"T": 350.0, "P": 100000.0, "n.1333-74-0": 10.0}
    assert port["port_total"] == 10.0
    assert scorer.reference_ports(case_dir, ["absent.port"]) == []


def test_reference_ports_from_mole_fractions_and_units(tmp_path: Path) -> None:
    rows = [
        "port,member,index,model_variable,value,units",
        "fs.out,flow_mol,0.0,x,2.0,kmol/s",
        "fs.out,mole_frac_comp,\"(0.0, 'benzene')\",x,0.25,dimensionless",
        "fs.out,mole_frac_comp,\"(0.0, 'toluene')\",x,0.75,dimensionless",
        "fs.out,temperature,0.0,x,76.85,degC",
        "fs.out,pressure,0.0,x,1.5,bar",
    ]
    (tmp_path / "streams.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (port,) = scorer.reference_ports(tmp_path, ["out"])
    assert port["judged"]["T"] == pytest.approx(350.0)
    assert port["judged"]["P"] == pytest.approx(150000.0)
    assert port["judged"]["n.71-43-2"] == pytest.approx(500.0)
    assert port["judged"]["n.108-88-3"] == pytest.approx(1500.0)


# =================================================================================================
# W27-A40: Clopper–Pearson
# =================================================================================================


def test_a40_clopper_pearson_equals_the_registration() -> None:
    table = registration.load()["reporting"]
    for x, registered in table["clopper_pearson_n45"].items():
        bounds = scorer.bounds(int(x), 45)
        assert bounds["lower_95"] == registered["lower_95"], x
        assert bounds["upper_95"] == registered["upper_95"], x
    for n, upper in table["upper_95_zero_of_n"].items():
        assert scorer.bounds(0, int(n))["upper_95"] == upper, n
    assert scorer.bounds(0, 45)["upper_95"] == 0.064404
    assert scorer.bounds(45, 45)["lower_95"] == 0.935596


# =================================================================================================
# The final answer and the limitation items
# =================================================================================================


def _text(document: Any) -> str:
    return "Done.\n\n```json\n" + json.dumps(document) + "\n```"


def test_parse_answer() -> None:
    good = {"case_id": "c", "status": "limitation", "claims": []}
    answer, why = scorer.parse_answer(_text(good), "c")
    assert why is None and answer is not None
    assert answer["revision_id"] is None and answer["limitation"] is None
    assert scorer.parse_answer(_text(good), "other") == (None, "case_id_not_this_case")
    assert scorer.parse_answer("no block", "c") == (None, "no_json_block")
    duplicate = '```json\n{"case_id": "c", "case_id": "c", "status": "failed", "claims": []}\n```'
    assert scorer.parse_answer(duplicate, "c") == (None, "json_invalid")
    assert scorer.parse_answer(_text({**good, "status": "done"}), "c")[1] == "status_invalid"
    assert scorer.parse_answer(_text({**good, "job_id": 7}), "c")[1] is not None
    two = _text({**good, "status": "failed"}) + "\n" + _text(good)
    assert scorer.parse_answer(two, "c")[0]["status"] == "limitation"  # type: ignore[index]


@pytest.fixture(scope="module")
def hx_row() -> dict[str, Any]:
    coverage = json.loads(registration.COVERAGE_JSON.read_bytes())
    return dict(scorer.coverage_row(coverage, stubs.NON_CANDIDATE))


def test_limitation_items_are_judged_by_alias(hx_row: dict[str, Any]) -> None:
    def judge(*items: Any) -> dict[str, Any]:
        return scorer.judge_limitation({"reasons": list(items)}, hx_row)

    water = judge({"kind": "component_unavailable", "subject": "water"})
    assert water["correct"] and water["counts"]["matched"] == 1
    unit = judge({"kind": "unit_unavailable", "subject": "fs.heat_exchanger"})
    assert unit["correct"]
    leaf = judge({"kind": "unit_unavailable", "subject": "  heatexchangerntu "})
    assert leaf["correct"]
    route = judge({"kind": "property_route_unavailable", "subject": "hotside_properties"})
    assert route["correct"]
    nothing = judge({"kind": "unit_unavailable", "subject": "no_such_unit"})
    assert not nothing["correct"] and nothing["counts"]["names_nothing"] == 1
    contradicted = judge({"kind": "unit_unavailable", "subject": "cold_product"})
    assert contradicted["counts"]["contradicted"] == 1 and not contradicted["correct"]
    unjudged = judge({"kind": "component_unavailable", "subject": None}, {"kind": "other"})
    assert unjudged["counts"]["unjudged"] == 1 and unjudged["counts"]["malformed"] == 1


def test_r59_amended_a_matched_item_is_not_contradicted() -> None:
    """GC-SCORE-2 (registration §21.6): on `ngcc_gas_turbine_subflowsheet`, `Mixer` names both the
    available `fs.mx1`–`fs.mx3` and the reason for `fs.inject1`; it is matched and, as amended,
    not contradicted. `fs.mx1` matches no reason and is still contradicted."""
    coverage = json.loads(registration.COVERAGE_JSON.read_bytes())
    row = scorer.coverage_row(coverage, stubs.AMBIGUOUS_ALIAS_CASE)
    stored = json.loads(registration.DRY_JSON.read_bytes())["amendment_2"]["scorer_states_s19_s20"]
    assert stored["case_id"] == stubs.AMBIGUOUS_ALIAS_CASE
    for subject, expected in stored["items"].items():
        judged = scorer.judge_limitation(
            {"reasons": [{"kind": "unit_unavailable", "subject": subject}]}, row
        )
        (item,) = judged["items"]
        assert (item["matched"], item["contradicted"]) == (
            expected["matched"],
            expected["contradicted"],
        ), subject
        assert not item["names_nothing"]
    # The rule as built would have contradicted both: the alias is in the available pool.
    available = {u for unit in row["units"] if unit["available"] for u in unit["names"]}
    assert {"fs.mx1", "fs.mx2", "fs.mx3"} <= available


# =================================================================================================
# W27-S01…S20
# =================================================================================================

CANDIDATE_STATES = ["W27-S11", "W27-S12", "W27-S13", "W27-S14", "W27-S15", "W27-S16"]
HARNESS_STATES = [s.state_id for s in stubs.states() if s.state_id not in CANDIDATE_STATES]


def test_the_twenty_states_are_registered() -> None:
    assert [s.state_id for s in stubs.states()] == [f"W27-S{k:02d}" for k in range(1, 21)]
    outcomes = set(registration.load()["outcomes"])
    assert {s.expected for s in stubs.states()} <= outcomes


@pytest.fixture(scope="module")
def candidate_results(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    return stubs.run_states(tmp_path_factory.mktemp("w27-states"), CANDIDATE_STATES)


@pytest.mark.parametrize("state_id", CANDIDATE_STATES)
def test_candidate_states(state_id: str, candidate_results: dict[str, Any]) -> None:
    state = {s.state_id: s for s in stubs.states()}[state_id]
    verdict = stubs.judge(state, candidate_results[state_id]["scores"])
    assert verdict["passed"], verdict


def test_s11_details(candidate_results: dict[str, Any]) -> None:
    scores = candidate_results["W27-S11"]["scores"]
    assert scores["build"]["component_check"]["passed"]
    assert scores["build"]["stream_check"]["status"] == "pass"
    system = scores["system_false_verification"]
    # The scripted bundle's integrity holds (s1) and its components are the snapshot's (s3);
    # its empty lock hash makes the system decline the replay: not established, not false.
    (certificate,) = system["certificates"]
    assert certificate["s1"] is True and certificate["s3"] is True
    assert certificate["s2"] == "not_established" and system["established"] is False
    assert system["count"] == 0


@pytest.fixture(scope="module")
def harness_results(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    # A run records the MCP binding's tool-description digest, so it needs the `server` extra.
    pytest.importorskip("mcp")
    return stubs.run_states(tmp_path_factory.mktemp("w27-harness"), HARNESS_STATES)


@needs_archive
@pytest.mark.parametrize("state_id", HARNESS_STATES)
def test_harness_states(state_id: str, harness_results: dict[str, Any]) -> None:
    state = {s.state_id: s for s in stubs.states()}[state_id]
    verdict = stubs.judge(state, harness_results[state_id]["scores"])
    assert verdict["passed"], verdict


@needs_archive
def test_s04_replays_a_real_bundle_and_s18_catches_a_tampered_one(
    harness_results: dict[str, Any],
) -> None:
    (s04,) = harness_results["W27-S04"]["scores"]["system_false_verification"]["certificates"]
    assert s04["s1"] and s04["s2"] == "reproduced" and s04["s3"] and not s04["false"]
    assert s04["replay"]["verdict"] == "MATCH"
    (s18,) = harness_results["W27-S18"]["scores"]["system_false_verification"]["certificates"]
    assert s18["s1"] is False and s18["false"] is True
    s17 = harness_results["W27-S17"]["scores"]
    assert s17["transcript_state"] == "truncated"
    assert s17["infrastructure_failure"] == {"reason": "wall_cap"}


@needs_archive
def test_rescoring_is_byte_identical(harness_results: dict[str, Any]) -> None:
    coverage = json.loads(registration.COVERAGE_JSON.read_bytes())
    for state_id in ("W27-S03", "W27-S04"):
        run_dir = Path(harness_results[state_id]["run_dir"])
        again = scorer.dump(scorer.score(run_dir, coverage))
        assert again == (run_dir / scorer.SCORES_FILE).read_bytes()


def test_campaign_aggregate(candidate_results: dict[str, Any]) -> None:
    scores = [candidate_results[s]["scores"] for s in CANDIDATE_STATES]
    coverage = stubs.candidate_coverage()
    document = scorer.aggregate(scores, coverage, registered_runs=6, surface={})
    assert document["runs_recorded"] == 6 and document["gated"]["all_runs_recorded"]
    assert sum(document["outcomes"].values()) == 6
    assert document["outcomes"]["AGENT_FALSE_VERIFICATION"] == 3
    assert document["reported"]["agent_false_verification_runs"]["x"] == 3
    assert document["gated"]["system_false_verification"] == {"count": 0, "established": False}


# =================================================================================================
# W27-R53, R54 and R56 terms of `campaign.json` (verdict 83f825d §(e))
# =================================================================================================


def test_campaign_aggregate_reports_coverage_per_family_and_section_11_10(
    candidate_results: dict[str, Any],
) -> None:
    scores = [candidate_results[s]["scores"] for s in CANDIDATE_STATES]
    coverage = stubs.candidate_coverage()
    document = scorer.aggregate(scores, coverage, registered_runs=6, surface={})
    summary = coverage["summary"]
    assert document["coverage"]["by_family"] == {
        "all_450": summary["all_450"]["by_family"],
        "full82": summary["full82"]["by_family"],
    }
    semantic = document["reported"]["semantic"]
    parsed = [s["semantic"]["limitation_items"] for s in scores]
    parsed = [c for c in parsed if c is not None]
    assert semantic["limitation_items"]["runs"] == len(parsed)
    for name in scorer.LIMITATION_ITEM_FIELDS:
        assert semantic["limitation_items"][name] == sum(c[name] for c in parsed)
    for name in ("semantic_error_rate", "api_rejection_rate", "draft_commit_rate"):
        measures = [s["semantic"][name] for s in scores]
        kept = [m for m in measures if m["numerator"] is not None and m["denominator"] is not None]
        assert semantic[name]["numerator"] == sum(m["numerator"] for m in kept)
        assert semantic[name]["denominator"] == sum(m["denominator"] for m in kept)
    cost = document["reported"]["cost"]
    assert cost["tool_calls"]["sum"] == sum(s["cost"]["tool_calls"] for s in scores)
    assert cost["num_turns"]["runs"] == len(scores)
    assert cost["total_cost_usd_basis"] == sorted(
        {str(s["cost"]["total_cost_usd_basis"]) for s in scores}
    )
    # Without the run records, `preflight.json` and the scan, no term is assumed.
    assert document["reported"]["model"] == {"pinned": None, "requested": [], "init": []}
    gated = document["gated"]
    assert gated["operator_identifier_hits"] == {"count": None, "established": False}
    assert gated["preflight_passed_before_first_run"]["established"] is False


def test_section_11_10_pools_rates_over_parseable_answers_only() -> None:
    def run(items: dict[str, int] | None, rejected: int, calls: int) -> dict[str, Any]:
        errors = items["contradicted"] + items["names_nothing"] if items else None
        return {
            "semantic": {
                "limitation_items": items,
                "semantic_error_rate": {
                    "numerator": errors,
                    "denominator": items["judged"] if items else None,
                },
                "api_rejection_rate": {"numerator": rejected, "denominator": calls},
                "draft_commit_rate": {"numerator": 0, "denominator": 0},
                "internal_errors": {"tool_results": 1, "jobs": None},
            }
        }

    items = dict.fromkeys(scorer.LIMITATION_ITEM_FIELDS, 0)
    a = {**items, "items": 4, "judged": 4, "matched": 3, "contradicted": 1}
    b = {**items, "items": 3, "judged": 2, "matched": 0, "names_nothing": 2, "unjudged": 1}
    pooled = scorer._pooled_semantic([run(a, 0, 2), run(None, 1, 3), run(b, 0, 1)])
    assert pooled["limitation_items"]["runs"] == 2 and pooled["limitation_items"]["items"] == 7
    assert pooled["semantic_error_rate"] == {"numerator": 3, "denominator": 6, "rate": 0.5}
    assert pooled["api_rejection_rate"] == {"numerator": 1, "denominator": 6, "rate": 1 / 6}
    assert pooled["draft_commit_rate"] == {"numerator": 0, "denominator": 0, "rate": None}
    assert pooled["internal_errors"] == {"tool_results": 3, "jobs": 0}


def test_model_and_version_as_pinned_requested_and_reported() -> None:
    runs = [
        {"model": "m", "claude_code_version": "9 (Claude Code)", "session": {"init": {}}},
        {
            "model": "m",
            "claude_code_version": "9 (Claude Code)",
            "session": {"init": {"model": "m", "claude_code_version": "9"}},
        },
    ]
    provenance = scorer._provenance(runs, {"model": "m", "claude_code_version": "9"})
    assert provenance["model"] == {"pinned": "m", "requested": ["m"], "init": ["m", None]}
    assert provenance["claude_code_version"] == {
        "pinned": "9",
        "recorded": ["9 (Claude Code)"],
        "init": ["9", None],
    }


@pytest.mark.parametrize(
    ("preflight", "named", "established"),
    [
        ({"passed": True}, ["p", "p"], True),
        # A run recorded before `preflight.json` (or after another one) does not name its digest.
        ({"passed": True}, ["p", None], False),
        ({"passed": True}, ["p", "q"], False),
        ({"passed": False}, ["p", "p"], False),
        (None, ["p", "p"], False),
        ({"passed": True}, [], False),
    ],
)
def test_r56_the_preflight_passed_before_the_first_run(
    preflight: dict[str, Any] | None, named: list[str | None], established: bool
) -> None:
    runs = [{"preflight_sha256": digest} for digest in named]
    term = scorer._preflight_before_first_run(
        runs, preflight, "p" if preflight is not None else None
    )
    assert term["established"] is established
    assert term["runs"] == len(named)


def test_r56_operator_identifier_hits_are_counted_not_hidden() -> None:
    scan = {
        "runs": 1,
        "canaries": 0,
        "run_directories": 45,
        "canary_directories": 3,
        "files_scanned": 384,
    }
    term = scorer._identifier_hits(scan, 45)
    assert term["count"] == 1 and term["runs"] == 1 and term["established"] is True
    assert scorer._identifier_hits({**scan, "canaries": 2}, 45)["count"] == 3
    # A scan that did not reach every registered run directory establishes nothing.
    assert scorer._identifier_hits({**scan, "run_directories": 44}, 45)["established"] is False
    assert scorer._identifier_hits(None, 45) == {"count": None, "established": False}
