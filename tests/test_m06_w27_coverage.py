"""M06 WO-16a–c: the W27 coverage classifier, the registry snapshot and the sampler.

Registration `docs/derivations/M06-W27-registration.md` §14.2: W27-A01…A15 and A20. Expected values
come from the registration document and the generator's committed output
(`dry_illustration.json`), which this code does not import. Tests that read the pinned archive
(the extraction equals `case_facts.json`; W27-A21's cards) skip when it is absent: it is
git-ignored and acquired by `scripts/m06_w27_acquire.py`; the preflight (P2) requires it.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from benchmarks.m06.w27 import coverage, facts, registration, sample, snapshot

DRY: dict[str, Any] = json.loads(registration.DRY_JSON.read_bytes())
TODAY: dict[str, Any] = DRY["snapshots"]["today"]["snapshot"]
FACTS: dict[str, Any] = facts.load_facts()
BY_ID: dict[str, dict[str, Any]] = {c["case_id"]: c for c in FACTS["cases"]}
TEST_PROVIDER = "test-pr"
TEST_METHODS = {**registration.provider_methods(), TEST_PROVIDER: "cubic_pr"}
ARCHIVE_PRESENT = (registration.ARCHIVE_DIR / "cases").is_dir()
needs_archive = pytest.mark.skipif(
    not ARCHIVE_PRESENT, reason="pinned archive absent (scripts/m06_w27_acquire.py)"
)


def with_route(components: list[dict[str, Any]], provider: str = TEST_PROVIDER) -> dict[str, Any]:
    route = {"provider_id": provider, "components": components, "model_ids": []}
    return {**TODAY, "routes": [*TODAY["routes"], route]}


def h2(phases: list[str]) -> dict[str, Any]:
    return {
        "id": "H2",
        "name": "hydrogen",
        "formula": "H2",
        "cas": "1333-74-0",
        "synthetic": False,
        "phases": phases,
    }


def triples(row: dict[str, Any]) -> list[tuple[str, Any, str]]:
    return [(x["kind"], x["subject"], x["detail"]) for x in row["reasons"]]


def kinds(row: dict[str, Any]) -> list[str]:
    return sorted({x["kind"] for x in row["reasons"]})


@pytest.fixture(scope="module")
def today_rows() -> dict[str, dict[str, Any]]:
    return {r["case_id"]: r for r in coverage.classify(FACTS, TODAY)["rows"]}


# =================================================================================================
# The registered rows (A01, A02) and the named cases (A03–A08)
# =================================================================================================


def test_a01_every_row_reproduces_the_dry_illustration(
    today_rows: dict[str, dict[str, Any]],
) -> None:
    registered = DRY["snapshots"]["today"]["rows"]
    assert len(registered) == 450
    equal = 0
    for row in registered:
        mine = today_rows[row["case_id"]]

        def multiset(reasons: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
            return sorted((x["kind"], str(x["subject"]), x["detail"]) for x in reasons)

        equal += mine["class"] == row["class"] and multiset(mine["reasons"]) == multiset(
            row["reasons"]
        )
    assert equal == 450
    assert coverage.summarise(list(today_rows.values())) == DRY["snapshots"]["today"]["summary"]


def test_a02_hypothetical_v02_summaries() -> None:
    stored = DRY["snapshots"]["hypothetical_v02"]
    methods = {**registration.provider_methods(), "hypothetical-pr-c1": "cubic_pr"}
    classified = coverage.classify(FACTS, stored["snapshot"], methods)
    assert classified["summary"] == stored["summary"]


def test_a03_watertap_metab(today_rows: dict[str, dict[str, Any]]) -> None:
    row = today_rows["watertap_metab"]
    assert row["class"] == "ARTIFACT_INCOMPLETE"
    reasons = triples(row)
    assert [k for k, _, _ in reasons] == [
        "ARTIFACT_INCOMPLETE",
        "NOT_STEADY_STATE_SIMULATION",
        "UNIT_UNAVAILABLE",
        "COMPONENT_UNAVAILABLE",
        "PROPERTY_ROUTE_UNAVAILABLE",
    ]
    artifact, nss, unit, component, route = reasons
    assert len(artifact[2].removeprefix("missing:").split(",")) == 6
    assert nss[2].startswith("n1:")
    assert unit[1] == "AnaerobicReactor"
    assert component == ("COMPONENT_UNAVAILABLE", None, "components_not_declared")
    assert route == ("PROPERTY_ROUTE_UNAVAILABLE", None, "no_property_package_declared")


def test_a04_gtep_three_stage(today_rows: dict[str, dict[str, Any]]) -> None:
    row = today_rows["official_gtep_5bus_three_stage"]
    assert row["class"] == "NOT_STEADY_STATE_SIMULATION"
    (detail,) = [d for k, _, d in triples(row) if k == "NOT_STEADY_STATE_SIMULATION"]
    rules = {part.split(":")[0] for part in detail.split(";")}
    assert {"n1", "n3", "n5"} <= rules


def test_a05_hx_ntu(today_rows: dict[str, dict[str, Any]]) -> None:
    row = today_rows["variant_idaes_hx_ntu_e60_a80"]
    assert row["class"] == "UNIT_UNAVAILABLE"
    units = [(s, d) for k, s, d in triples(row) if k == "UNIT_UNAVAILABLE"]
    assert len(units) == 1 and units[0][0] == "HeatExchangerNTU"
    assert units[0][1].startswith("partial:heat_exchanger:missing=ntu_relation ")
    components = {s: d for k, s, d in triples(row) if k == "COMPONENT_UNAVAILABLE"}
    assert sorted(components) == ["CO2", "H2O", "HCO3_-", "MEA", "MEACOO_-", "MEA_+"]
    assert sum(d.startswith("chemical:") for d in components.values()) == 3
    assert sum(d == "ion" for d in components.values()) == 3
    routes = sorted((s, d) for k, s, d in triples(row) if k == "PROPERTY_ROUTE_UNAVAILABLE")
    assert routes == [
        ("fs.coldside_properties", "no_route:aqueous_apparent_species"),
        ("fs.hotside_properties", "no_route:aqueous_apparent_species"),
    ]


def test_a06_feed_flash(today_rows: dict[str, dict[str, Any]]) -> None:
    row = today_rows["idaes_feed_flash"]
    assert row["class"] == "UNIT_UNAVAILABLE"
    units = {s: d for k, s, d in triples(row) if k == "UNIT_UNAVAILABLE"}
    assert "missing=two_phase_feed" in units["FeedFlash"]
    assert sorted(s for k, s, _ in triples(row) if k == "COMPONENT_UNAVAILABLE") == [
        "benzene",
        "toluene",
    ]
    assert [(s, d) for k, s, d in triples(row) if k == "PROPERTY_ROUTE_UNAVAILABLE"] == [
        ("fs.properties", "no_route:ideal_vle")
    ]


def test_a07_iapws_pump(today_rows: dict[str, dict[str, Any]]) -> None:
    row = today_rows["variant_idaes_iapws_pump_dp200k_eff75"]
    assert row["class"] == "COMPONENT_UNAVAILABLE"
    assert not [r for r in row["reasons"] if r["kind"] == "UNIT_UNAVAILABLE"]
    assert all(u["available"] for u in row["units"])
    assert [s for k, s, _ in triples(row) if k == "COMPONENT_UNAVAILABLE"] == ["H2O"]
    # H2O is also intrinsic to IAPWS-95 (W27-R05), whether or not the topology lists it.
    unlisted = {**BY_ID[row["case_id"]], "listed_components": []}
    assert coverage.declared_components(unlisted) == ["H2O"]
    assert [(s, d) for k, s, d in triples(row) if k == "PROPERTY_ROUTE_UNAVAILABLE"] == [
        ("fs.properties", "no_route:iapws95")
    ]


def test_a08_hda_flash(today_rows: dict[str, dict[str, Any]]) -> None:
    row = today_rows["blind_synthesized_hda_flash"]
    assert row["class"] == "UNIT_UNAVAILABLE"
    units = [(s, d) for k, s, d in triples(row) if k == "UNIT_UNAVAILABLE"]
    assert len(units) == 1 and units[0][0] == "PressureChanger"
    assert units[0][1].startswith("no_function:defining_relation_absent ")
    names = [n for u in BY_ID[row["case_id"]]["units"] for n in u["names"]]
    assert "fs.F101" in names and "fs.F101.split" not in names
    reaction = [p["name"] for p in row["packages"] if p["method"] == "reaction"]
    assert reaction and not [x for x in row["reasons"] if x["subject"] in reaction]


# =================================================================================================
# Refusals (A09–A11) and the adversarial states (A12–A15)
# =================================================================================================


@pytest.mark.parametrize(
    ("snap", "needle"),
    [
        ({**TODAY, "models": [*TODAY["models"], {"model_id": "x.test"}]}, "x.test"),
        (with_route([], provider="x-provider"), "x-provider"),
        (
            with_route(
                [
                    {
                        "id": "TDS",
                        "name": "TDS",
                        "formula": None,
                        "cas": "7647-14-5",
                        "synthetic": False,
                        "phases": ["liquid"],
                    }
                ]
            ),
            "TDS->7647-14-5",
        ),
    ],
    ids=["A09-model", "A10-provider", "A11-chemical"],
)
def test_a09_a11_refusals(snap: dict[str, Any], needle: str, tmp_path: Path) -> None:
    with pytest.raises(coverage.RefusalError, match=needle.replace(".", r"\.")):
        coverage.classify(FACTS, snap, TEST_METHODS)
    # No coverage.json is written (W27-R24): the CLI exits 2 before writing. A10/A11 refuse
    # under the registered table too (it maps neither `x-provider` nor `test-pr`).
    snap_file = tmp_path / "snapshot.json"
    snap_file.write_bytes(registration.dump(snap))
    out = tmp_path / "coverage.json"
    assert coverage.main(["--snapshot", str(snap_file), "--out", str(out)]) == 2
    assert not out.exists()


def test_a12_iapws_pump_with_water_in_a_pr_route() -> None:
    water = {
        "id": "H2O",
        "name": "water",
        "formula": "H2O",
        "cas": "7732-18-5",
        "synthetic": False,
        "phases": ["liquid", "vapor"],
    }
    snap = with_route([water])
    coverage.check_snapshot(snap, FACTS, TEST_METHODS)
    row = coverage.classify_case(BY_ID["variant_idaes_iapws_pump_dp200k_eff75"], snap, TEST_METHODS)
    assert row["class"] == "PROPERTY_ROUTE_UNAVAILABLE"
    assert triples(row) == [("PROPERTY_ROUTE_UNAVAILABLE", "fs.properties", "no_route:iapws95")]


def synthetic(**changes: Any) -> dict[str, Any]:
    """W27-A13's synthetic row, as stored in `dry_illustration.json#/adversarial_states`."""
    (base,) = [s["case"] for s in DRY["adversarial_states"] if s["state"] == "A13-a base row"]
    case = copy.deepcopy(base)
    case.update(changes)
    return dict(case)


def test_a13_synthetic_candidate_and_its_one_change_variants() -> None:
    vapour = with_route([h2(["vapor"])])
    base = synthetic()
    assert coverage.classify_case(base, vapour, TEST_METHODS)["reasons"] == []
    assert coverage.classify_case(base, vapour, TEST_METHODS)["class"] == "CANDIDATE"
    no_h2 = coverage.classify_case(base, with_route([]), TEST_METHODS)
    assert no_h2["class"] == "COMPONENT_UNAVAILABLE"
    assert [(k, s) for k, s, _ in triples(no_h2)] == [("COMPONENT_UNAVAILABLE", "H2")]
    units = copy.deepcopy(base["units"])
    units[1]["config"] = {"dynamic": True}
    dynamic = coverage.classify_case(synthetic(units=units), vapour, TEST_METHODS)
    assert dynamic["class"] == "NOT_STEADY_STATE_SIMULATION"
    assert kinds(dynamic) == ["NOT_STEADY_STATE_SIMULATION", "UNIT_UNAVAILABLE"]
    assert any("missing=dynamic" in d for _, _, d in triples(dynamic))
    mixer = {
        "key": "idaes:Mixer",
        "class_leaf": "_ScalarMixer",
        "config": {"momentum_mixing_type": "none"},
        "names": ["fs.mix"],
    }
    mixed = coverage.classify_case(synthetic(units=[*base["units"], mixer]), vapour, TEST_METHODS)
    assert mixed["class"] == "UNIT_UNAVAILABLE"
    assert any(
        s == "Mixer" and "missing=mixer_no_momentum_balance" in d for _, s, d in triples(mixed)
    )
    gap = synthetic(files_missing=["units.json"], steady_state=False)
    artifact = coverage.classify_case(gap, vapour, TEST_METHODS)
    assert artifact["class"] == "ARTIFACT_INCOMPLETE"
    assert kinds(artifact) == ["ARTIFACT_INCOMPLETE", "NOT_STEADY_STATE_SIMULATION"]


def test_a14_two_methods_one_route_per_revision() -> None:
    base = synthetic()
    second = {
        "name": "fs.props2",
        "key": "generic[Vap:VaporPhase:Ideal]",
        "classes": ["GenericParameterBlock"],
        "phases": ["vapor"],
        "components": ["H2"],
    }
    row = coverage.classify_case(
        synthetic(packages=[*base["packages"], second]), with_route([h2(["vapor"])]), TEST_METHODS
    )
    assert row["class"] == "PROPERTY_ROUTE_UNAVAILABLE"
    assert sorted(s for _, s, _ in triples(row)) == ["fs.props", "fs.props2"]
    assert all("multiple_routes_per_revision" in d for _, _, d in triples(row))


def test_a15_liquid_phase_with_a_vapour_only_component() -> None:
    base = synthetic()
    vle = [
        {
            **base["packages"][0],
            "key": "generic[Liq:LiquidPhase:Cubic(type=PR);Vap:VaporPhase:Cubic(type=PR)]",
            "phases": ["liquid", "vapor"],
        }
    ]
    row = coverage.classify_case(synthetic(packages=vle), with_route([h2(["vapor"])]), TEST_METHODS)
    assert row["class"] == "PROPERTY_ROUTE_UNAVAILABLE"
    assert len(row["reasons"]) == 1 and "phase=1333-74-0:liquid" in row["reasons"][0]["detail"]


def test_adversarial_states_equal_the_stored_record() -> None:
    """Every stored state (GC-ADV) classified by this code gives the stored reasons."""
    for state in DRY["adversarial_states"]:
        if "expected_class" not in state:
            continue
        case = state["case"] if isinstance(state["case"], dict) else BY_ID[state["case"]]
        added = state["added_route_components"]
        snap = with_route(list(added)) if added is not None else TODAY
        row = coverage.classify_case(case, snap, TEST_METHODS)
        assert row["class"] == state["expected_class"], state["state"]
        assert [{"kind": k, "subject": s, "detail": d} for k, s, d in triples(row)] == state[
            "reasons"
        ], state["state"]


def test_every_subject_is_among_its_aliases(today_rows: dict[str, dict[str, Any]]) -> None:
    for row in today_rows.values():
        for reason in row["reasons"]:
            if reason["subject"] is not None:
                assert reason["subject"] in reason["aliases"]


# =================================================================================================
# The registry snapshot (WO-16b) and coverage.json (W27-R25, G14)
# =================================================================================================


def test_snapshot_of_this_build_is_todays_registry() -> None:
    live = snapshot.build_snapshot()
    assert live["schema"] == "w27-registry-snapshot-v1"
    assert live["package_version"] == "0.1.1"
    assert live["list_models_sha256"] == TODAY["list_models_sha256"]
    assert live["models"] == TODAY["models"] and live["routes"] == TODAY["routes"]
    assert live["routes_per_revision"] == 1
    assert set(live) == {
        "schema",
        "package_version",
        "git_commit",
        "list_models_sha256",
        "models",
        "routes",
        "routes_per_revision",
        "basis",
    }


def test_snapshot_refuses_an_unregistered_binder_reading() -> None:
    with pytest.raises(snapshot.SnapshotUnsupportedError, match="route enumeration"):
        snapshot.build_snapshot(version="0.2.0")


def _revision_over(components: list[str]) -> dict[str, Any]:
    """A registered T05 revision (feed, pump, heater, valve, flash, two sinks) whose component set
    is `components`."""
    from benchmarks.t07.v17 import fixtures  # noqa: PLC0415

    document = copy.deepcopy(fixtures.load_case("benchmarks/t05/cases/SYN-001-UL-C1.yaml"))
    document["component_set"]["components"] = components
    return dict(document)


def test_each_route_binds_a_revision_with_its_component_set() -> None:
    """WO-16b: each (route, component set) the snapshot lists binds a revision over that set,
    with each of the route's models available to the binder."""
    from openflowsheet.application.binding import Unbound  # noqa: PLC0415
    from openflowsheet.application.revision_binding import (  # noqa: PLC0415
        MODEL_BUILDERS,
        bind_revision_flowsheet,
    )

    live = snapshot.build_snapshot()
    for route in live["routes"]:
        ids = [c["id"] for c in route["components"]]
        bound = bind_revision_flowsheet(_revision_over(ids))
        assert not isinstance(bound, Unbound), bound
        assert set(route["model_ids"]) == set(MODEL_BUILDERS)
        refused = bind_revision_flowsheet(_revision_over([*ids, "H2"]))
        assert isinstance(refused, Unbound) and refused.detail == "components_unsupported"


def test_coverage_document_and_g14() -> None:
    live = snapshot.build_snapshot()
    document = coverage.coverage_document(FACTS, live)
    verdict = coverage.g14(document)
    assert verdict["passed"], verdict
    assert document["case_facts_sha256"] == registration.load()["inputs"]["case_facts_sha256"]
    assert document["snapshot_sha256"] == registration.sha256_bytes(registration.dump(live))
    assert set(document["rows"][0]) == {
        "case_id",
        "family",
        "model_type",
        "in_full82",
        "residual_check",
        "class",
        "reasons",
        "units",
        "components",
        "packages",
    }
    broken = copy.deepcopy(document)
    broken["rows"][0]["reasons"] = []
    assert not coverage.g14(broken)["passed"]


def test_committed_coverage_json_is_g14_and_this_builds_classification() -> None:
    """The committed Tier 0 record: G14 holds, and re-classifying its own snapshot reproduces
    every row (the classification is a function of facts and snapshot)."""
    document = json.loads(registration.COVERAGE_JSON.read_bytes())
    assert coverage.g14(document)["passed"]
    again = coverage.coverage_document(FACTS, document["snapshot"])
    assert again["rows"] == document["rows"] and again["summary"] == document["summary"]
    live = snapshot.build_snapshot()
    assert {k: v for k, v in live.items() if k != "git_commit"} == {
        k: v for k, v in document["snapshot"].items() if k != "git_commit"
    }


# =================================================================================================
# The sample (WO-16c, A20) and the archive-dependent checks
# =================================================================================================


def test_a20_sample_redraws_byte_identically(tmp_path: Path) -> None:
    data = registration.COVERAGE_JSON.read_bytes()
    first = registration.dump(sample.sample_document(json.loads(data), data))
    path = tmp_path / "coverage.json"
    path.write_bytes(data)
    out = tmp_path / "sample.json"
    assert sample.main([str(path), "--out", str(out)]) == 0
    assert out.read_bytes() == first


def test_dry_sample_equals_the_registered_draw(today_rows: dict[str, dict[str, Any]]) -> None:
    drawn = sample.draw(list(today_rows.values()))
    assert drawn == DRY["snapshots"]["today"]["sample"]
    assert len(set(drawn["cases"])) == 45 and sorted(drawn["run_order"]) == drawn["cases"]
    assert len(drawn["canaries"]) == 3 and not set(drawn["canaries"]) & set(drawn["cases"])


def test_allocation_holds_for_every_size(today_rows: dict[str, dict[str, Any]]) -> None:
    frame = [r for r in today_rows.values() if r["class"] != "ARTIFACT_INCOMPLETE"]
    populations: dict[str, int] = {}
    for row in frame:
        populations[row["family"]] = populations.get(row["family"], 0) + 1
    eligible = [f for f, n in populations.items() if n >= 4]
    for slots in range(1, 46):
        alloc = sample.allocate(populations, slots)
        assert sum(alloc.values()) == slots
        assert all(alloc[f] <= populations[f] for f in alloc)
        if len(eligible) <= slots:
            assert all(alloc[f] >= 1 for f in eligible)


@needs_archive
def test_extraction_equals_case_facts_json() -> None:
    fresh = facts.dump_facts(facts.extract(registration.ARCHIVE_DIR))
    assert fresh == registration.CASE_FACTS_JSON.read_bytes()


@needs_archive
def test_a21_every_card_hashes_as_registered() -> None:
    registered = registration.load()["prompt"]["card"]["sha256_by_case"]
    cases = registration.ARCHIVE_DIR / "cases"
    equal = sum(
        registration.sha256_bytes(facts.case_card(cases / case_id).encode("utf-8")) == digest
        for case_id, digest in registered.items()
    )
    assert equal == 450
