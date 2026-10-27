"""S11 WO-A4: W27 registration version 3 (S11.A30–A33).

Normative text: `docs/derivations/W27-registration-v3.md`, transcribed from the S11 design note
§4.10 (ADR 0050 D9, R-808). Version 3 is version 2 with S11's provider, method and model rows, and
a route identified by its key `(provider_id, record_source, components)`. The registered states
come from `registration_v3.json` (its generator is run only through `--check`, never imported).
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from benchmarks.m06.w27 import coverage, facts, registration, snapshot

ROOT = registration.ROOT
GENERATOR_V3 = ROOT / "docs" / "derivations" / "scripts" / "w27_registration_v3.py"
SPLIT_JSON = registration.RECORDS / "split.json"


@functools.cache
def v3() -> dict[str, Any]:
    return dict(registration.load_v3())


def _states() -> list[dict[str, Any]]:
    return list(json.loads(registration.REGISTRATION_V3_JSON.read_bytes())["states"])


def provider_table(version: int) -> dict[str, str]:
    """The state's version's provider table, with `#/test_provider_methods` (W27-A02)."""
    return {**registration.provider_methods(version), **v3()["test_provider_methods"]}


def triples(row: dict[str, Any]) -> list[list[Any]]:
    return [[r["kind"], r["subject"], r["detail"]] for r in row["reasons"]]


# =================================================================================================
# The registered states, through the production classifier
# =================================================================================================


@pytest.mark.parametrize("state", _states(), ids=[s["id"] for s in _states()])
def test_registered_state(state: dict[str, Any]) -> None:
    snap = v3()["snapshots"][state["snapshot"]]
    case = v3()["cases"][state["case"]]
    version = state["registration_version"]
    table = provider_table(version)
    expected = state["expected"]
    try:
        coverage.check_snapshot(snap, {"cases": [case]}, table, registration_version=version)
    except coverage.RefusalError as refusal:
        assert "refusal" in expected, f"{state['id']}: unexpected refusal {refusal}"
        assert str(refusal) == expected["refusal"]
        return
    assert "refusal" not in expected, f"{state['id']}: expected a refusal"
    row = coverage.classify_case(case, snap, table, registration_version=version)
    assert row["class"] == expected["class"]
    assert row["units_judged_on"] == expected["units_judged_on"]
    assert triples(row) == expected["reasons"]
    assert [[u["key"], u["models"]] for u in row["units"]] == expected["units"]


def test_the_states_are_the_registered_eight() -> None:
    assert [s["id"] for s in _states()] == [f"W27v3-A{n:02d}" for n in range(1, 9)]


def test_r07_the_tie_goes_to_the_smaller_key_not_the_first_route() -> None:
    """W27v3-R07: T lists record source `b` before `a`; the units are judged on `a`'s models."""
    sources = [r["record_source"] for r in v3()["snapshots"]["T"]["routes"][1:]]
    assert sources == ["benchmarks/zz-test/b.yaml", "benchmarks/zz-test/a.yaml"]
    case = v3()["cases"]["H2O"]
    for name in ("T", "Tr"):
        row = coverage.classify_case(
            case, v3()["snapshots"][name], provider_table(3), registration_version=3
        )
        heater = next(u for u in row["units"] if u["key"] == "idaes:Heater")
        assert heater["models"] == ["c1.tp_heater", "syn001.tp_heater"]


def test_version_3_tables_are_read_from_registration_v3() -> None:
    tables = v3()["tables"]
    assert registration.provider_methods(3) == tables["provider_methods"]
    assert registration.provider_methods(3) == {
        **registration.provider_methods(2),
        "coolprop-heos-v1": "pure_helmholtz",
        "iapws95-v1": "iapws95",
        "wilson-ig-v1": "activity_coefficient",
    }
    assert registration.model_functions(3)["syn001.column"] == {
        "function": None,
        "offers": [],
        "why_none": "column_function_unregistered",
    }
    assert registration.model_functions(1) == registration.model_functions(2)
    assert "syn001.column" not in registration.model_functions(2)
    with pytest.raises(ValueError, match="not 1, 2 or 3"):
        registration.model_functions(4)


def test_a_v2_snapshot_without_record_sources_is_refused_by_v3() -> None:
    """W27v3-R06: a route with no `record_source` has no key."""
    s1 = registration.load_v2()["snapshots"]["S1"]
    case = registration.load_v2()["cases"]["H2"]
    with pytest.raises(coverage.RefusalError, match=r"routes with no record_source \['pr-c1-v1'\]"):
        coverage.check_snapshot(s1, {"cases": [case]}, registration_version=3)


# =================================================================================================
# S11.A30: the v1 and v2 outputs on every registered state are byte-identical to the base
# =================================================================================================

#: `_a30_corpus()`'s SHA-256 at the identity base `8c34ecb0` (measured there, S11A_DECISIONS).
A30_BASE_SHA256 = "e141bab01c6343677132d438d19040ea01237f114c7ff0f7a270354254c53291"


def _a30_corpus() -> bytes:
    """Versions 1 and 2 on their registered states: v1 over every case at the committed and the
    dry-illustration (`today`) snapshots; v2 over the development half at both; and every v2
    registered snapshot × case × version × provider table, each a whole row or a refusal."""
    out: list[Any] = []

    def run(label: str, thunk: Any) -> None:
        try:
            value = thunk()
        except coverage.RefusalError as refusal:
            value = {"refusal": str(refusal)}
        out.append([label, value])

    every = facts.load_facts()
    development = set(json.loads(SPLIT_JSON.read_bytes())["development"]["case_ids"])
    dev = {**every, "cases": [c for c in every["cases"] if c["case_id"] in development]}
    committed = json.loads(registration.COVERAGE_JSON.read_bytes())["snapshot"]
    today = json.loads(registration.DRY_JSON.read_bytes())["snapshots"]["today"]["snapshot"]
    for name, snap in (("committed", committed), ("today", today)):
        run(f"v1:{name}", lambda s=snap: coverage.coverage_document(every, s))
        run(f"v2:dev:{name}", lambda s=snap: coverage.classify(dev, s, registration_version=2))
    v2 = registration.load_v2()
    test = dict(v2["test_provider_methods"])
    v1_table = registration.provider_methods(1)
    tables = {
        "v1": {**v1_table, **test},
        "v2": {**registration.provider_methods(2), **test},
        "v1+lib": {**v1_table, "pr-lib-v1": "cubic_pr", **test},
    }
    for snap_id, snap in sorted(v2["snapshots"].items()):
        for case_id, case in sorted(v2["cases"].items()):
            for version in (1, 2):
                for table_id, table in sorted(tables.items()):

                    def one(s: Any = snap, c: Any = case, t: Any = table, v: int = version) -> Any:
                        coverage.check_snapshot(s, {"cases": [c]}, t, registration_version=v)
                        return coverage.classify_case(c, s, t, registration_version=v)

                    run(f"{version}:{table_id}:{snap_id}:{case_id}", one)
    return registration.dump(out)


def test_a30_v1_and_v2_outputs_are_byte_identical_to_the_base() -> None:
    assert hashlib.sha256(_a30_corpus()).hexdigest() == A30_BASE_SHA256


def test_a30_v1_reproduces_the_committed_coverage_json() -> None:
    committed = registration.COVERAGE_JSON.read_bytes()
    snap = json.loads(committed)["snapshot"]
    document = coverage.coverage_document(facts.load_facts(), snap)
    assert registration.dump(document) == committed


# =================================================================================================
# S11.A31 / A33: the S11 build's version 3 snapshot
# =================================================================================================


@functools.cache
def _build_v3() -> dict[str, Any]:
    return snapshot.build_snapshot(registration_version=3)


def test_a31_the_s11_build_reads_under_v3_with_distinct_keys() -> None:
    """W27v3-R05/R06: every selectable basis has a line; 127 routes, 123 of them CoolProp, each
    with a distinct key; the snapshot passes version 3's refusals for a case spelling only H2."""
    built = _build_v3()
    assert built["schema"] == "w27-registry-snapshot-v3"
    routes = built["routes"]
    assert len(routes) == 127
    cool = [r for r in routes if r["provider_id"] == "coolprop-heos-v1"]
    assert len(cool) == 123
    assert len({coverage.route_key(r) for r in routes}) == 127
    assert {r["record_source"] for r in cool} == {"benchmarks/s07/components.yaml"}
    case = v3()["cases"]["H2"]
    coverage.check_snapshot(built, {"cases": [case]}, registration_version=3)
    row = coverage.classify_case(case, built, registration_version=3)
    assert (row["class"], row["units_judged_on"]) == ("CANDIDATE", "pr-c1-v1")


def test_a31_v3_refuses_the_build_with_one_route_listed_twice() -> None:
    built = json.loads(json.dumps(_build_v3()))
    co2 = next(r for r in built["routes"] if r["components"][0]["id"] == "CO2")
    built["routes"].append(co2)
    case = v3()["cases"]["H2"]
    with pytest.raises(coverage.RefusalError) as refusal:
        coverage.check_snapshot(built, {"cases": [case]}, registration_version=3)
    assert str(refusal.value) == (
        "duplicate route keys [('coolprop-heos-v1', 'benchmarks/s07/components.yaml', 'CO2')]"
    )


def test_a33_the_iapws95_route_reads_water_from_the_s05_records() -> None:
    (route,) = [r for r in _build_v3()["routes"] if r["provider_id"] == "iapws95-v1"]
    assert route["record_source"] == "benchmarks/s05/components.yaml"
    assert route["components"] == [
        {
            "id": "H2O",
            "name": "water",
            "formula": "H2O",
            "cas": "7732-18-5",
            "synthetic": False,
            "phases": ["liquid", "vapor"],
        }
    ]


def test_v3_routes_are_the_v2_routes_with_their_record_sources() -> None:
    """W27v3-R05: `pr-c1-v1` keeps its v2 line and SYN-001's generic line reads what `_syn001_line`
    read; only `record_source` is added."""
    from test_m06_w27_coverage import v2_binder  # noqa: PLC0415

    before = snapshot.build_snapshot(binding=v2_binder())["routes"]
    after = {r["provider_id"]: r for r in _build_v3()["routes"]}
    for r in before:
        assert {k: v for k, v in after[r["provider_id"]].items() if k != "record_source"} == r


def test_the_0_1_1_reading_carries_the_syn001_record_source_under_v3() -> None:
    from openflowsheet.application import revision_binding  # noqa: PLC0415

    binder = ModuleType("binder_0_1_1")
    binder.MODEL_BUILDERS = revision_binding.MODEL_BUILDERS  # type: ignore[attr-defined]
    (route,) = snapshot.build_snapshot("0.1.1", binder, registration_version=3)["routes"]
    assert route["record_source"] == "benchmarks/syn001/components.yaml"
    (old,) = snapshot.build_snapshot("0.1.1", binder)["routes"]
    assert "record_source" not in old


def test_build_snapshot_refuses_other_registration_versions() -> None:
    for version in (0, 4, True):
        with pytest.raises(ValueError, match="not 1, 2 or 3"):
            snapshot.build_snapshot(registration_version=version)


# =================================================================================================
# Version 3 equals version 2 wherever version 2 accepts (GC-V3-5, through production)
# =================================================================================================

RECORD_SOURCES = {
    "syn001": "benchmarks/syn001/components.yaml",
    "pr-c1-v1": "benchmarks/m01/components.yaml",
}


def test_v3_development_rows_equal_the_committed_rows() -> None:
    development = set(json.loads(SPLIT_JSON.read_bytes())["development"]["case_ids"])
    every = facts.load_facts()
    dev_facts = {**every, "cases": [c for c in every["cases"] if c["case_id"] in development]}
    committed = json.loads(registration.COVERAGE_JSON.read_bytes())
    committed_rows = {r["case_id"]: r for r in committed["rows"] if r["case_id"] in development}
    snap = committed["snapshot"]
    for r in snap["routes"]:
        r["record_source"] = RECORD_SOURCES[r["provider_id"]]
    rows = coverage.classify(dev_facts, snap, registration_version=3)["rows"]
    assert {r["case_id"] for r in rows} == development
    assert [r["case_id"] for r in rows if r != committed_rows[r["case_id"]]] == []


def test_the_version_3_record() -> None:
    snap = v3()["snapshots"]["B"]
    document = coverage.coverage_document(
        {"cases": [v3()["cases"]["H2"]]}, snap, registration_version=3
    )
    assert document["schema"] == "w27-coverage-v3"
    assert document["registration_version"] == 3
    assert document["registration_v3_sha256"] == registration.sha256_file(
        registration.REGISTRATION_V3_JSON
    )
    assert document["registration_v2_sha256"] == registration.sha256_file(
        registration.REGISTRATION_V2_JSON
    )
    assert document["rows"][0]["units_judged_on"] == "pr-c1-v1"


@pytest.mark.parametrize("out", [None, "committed", "elsewhere"])
def test_cli_v3_keeps_version_2s_output_path_rules(
    out: str | None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    def no_snapshot(**_: Any) -> Any:
        raise AssertionError("a snapshot was built before the path was refused")

    monkeypatch.setattr(snapshot, "build_snapshot", no_snapshot)
    argv = ["--registration-version", "3"]
    if out == "committed":
        argv += ["--out", str(registration.COVERAGE_JSON)]
    elif out == "elsewhere":
        argv += ["--out", str(tmp_path / "v3.json")]
    before = registration.COVERAGE_JSON.read_bytes()
    assert coverage.main(argv) == 2
    message = capsys.readouterr().err
    expected = (
        coverage.HELDOUT_PATH_REFUSAL_V3 if out == "elsewhere" else coverage.SPLIT_R10_REFUSAL_V3
    )
    assert message == f"REFUSED: {expected}\n"
    assert "registration version 3" in message
    assert registration.COVERAGE_JSON.read_bytes() == before


# =================================================================================================
# S11.A32: the generator's check
# =================================================================================================


def test_a32_generator_check() -> None:
    env = {**os.environ, "PYTHONPATH": f"{ROOT / 'src'}{os.pathsep}{ROOT}"}
    result = subprocess.run(
        [sys.executable, str(GENERATOR_V3), "--check"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "identical" in result.stdout and "DIFFER" not in result.stdout
