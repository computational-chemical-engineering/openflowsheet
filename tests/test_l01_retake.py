"""L01.A23–A27 as amended by L01 spec §14.4, and W27v2-A23: the development-half coverage re-take
on the measurement-only binding (WO-L01-3a, `benchmarks/l01/retake.py`).

The expectations are independent of the re-take: the projection's registered classes and
transitions (`docs/derivations/scripts/l01_projection.json`, §6.3), the registered expected route
(`registration_v2.json#/snapshots/S2/routes/1`), W27 v1's registered refusal text (W27v2-A09), and
the installed build's own tables (A27).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT
from test_t08_w2_support_envelope import LIBRARY_ONLY_PROVIDERS

from benchmarks.l01 import retake
from benchmarks.m06.w27 import registration, snapshot
from openflowsheet import resources
from openflowsheet.application import revision_binding

PROJECTION: dict[str, Any] = json.loads(
    (REPO_ROOT / "docs" / "derivations" / "scripts" / "l01_projection.json").read_bytes()
)
S2_LIBRARY_ROUTE: dict[str, Any] = json.loads(registration.REGISTRATION_V2_JSON.read_bytes())[
    "snapshots"
]["S2"]["routes"][1]


@pytest.fixture(scope="module")
def run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """One version 2 re-take through the CLI, into a temporary path; the committed coverage.json's
    bytes before and after it (A26)."""
    out = tmp_path_factory.mktemp("l01") / "retake.json"
    before = registration.COVERAGE_JSON.read_bytes()
    code = retake.main(["--out", str(out)])
    after = registration.COVERAGE_JSON.read_bytes()
    return {
        "code": code,
        "record": json.loads(out.read_bytes()),
        "coverage_unchanged": before == after,
    }


# -- A23 ------------------------------------------------------------------------------------------


def test_a23_the_projection_generator_check_passes() -> None:
    script = REPO_ROOT / "docs" / "derivations" / "scripts" / "l01_projection.py"
    done = subprocess.run(
        [sys.executable, str(script), "--check"], capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, done.stderr


# -- A24: the registration-version-1 control -----------------------------------------------------


def test_a24_version_1_refuses_the_two_route_snapshot(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "retake.json"
    code = retake.main(["--registration-version", "1", "--out", str(out)])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.err.startswith("REFUSED:")
    assert "unregistered provider ids ['pr-lib-v1']" in captured.err
    assert captured.out == ""  # no count
    assert not out.exists()


# -- A25: the measurement -------------------------------------------------------------------------


def test_a25_development_classes_equal_the_projection(run: dict[str, Any]) -> None:
    assert run["code"] == 0
    record = run["record"]
    assert record["before"] == PROJECTION["before"]
    assert record["after"]["classes"] == PROJECTION["projection"]["after"]["classes"]


def test_a25_removed_component_reasons_equal_the_projected_transitions(
    run: dict[str, Any],
) -> None:
    projected = {
        t["case_id"]: t["component_reasons_removed"]
        for t in PROJECTION["projection"]["transitions"]
    }
    measured = {
        t["case_id"]: t["component_reasons_removed"]
        for t in run["record"]["transitions"]
        if t["component_reasons_removed"]
    }
    assert measured == {cid: removed for cid, removed in projected.items() if removed}
    classes = {t["case_id"]: t["class_after"] for t in run["record"]["transitions"]}
    assert classes == {
        t["case_id"]: t["class_after"] for t in PROJECTION["projection"]["transitions"]
    }


def test_a25_unit_reason_differences_are_listed_with_their_w27_r62_cause(
    run: dict[str, Any],
) -> None:
    record = run["record"]
    listed = {u["case_id"]: u for u in record["unit_reason_differences"]}
    for t in record["transitions"]:
        # Beyond the projection's removed component reasons, only unit reasons may move (SC-8).
        assert t["other_reasons_removed"] == [], t["case_id"]
        added_units = [r for r in t["reasons_added"] if r.startswith("UNIT_UNAVAILABLE:")]
        assert added_units == t["reasons_added"], t["case_id"]
        if added_units:
            assert listed[t["case_id"]]["unit_reasons_added"] == added_units
    for cid, u in listed.items():
        assert u["cause"].startswith("W27-R62:"), cid
        # The cause holds: the serving route moved, to the library route that carries no models.
        assert u["units_judged_on_before"] != u["units_judged_on_after"] == "pr-lib-v1", cid


# -- A26 ------------------------------------------------------------------------------------------


def test_a26_development_ids_only_and_coverage_json_untouched(run: dict[str, Any]) -> None:
    dev = set(json.loads(retake.SPLIT_JSON.read_bytes())["development"]["case_ids"])
    record = run["record"]
    named = {t["case_id"] for t in record["transitions"]}
    named |= {u["case_id"] for u in record["unit_reason_differences"]}
    assert named and named <= dev
    assert run["coverage_unchanged"]
    with pytest.raises(RuntimeError, match="L01.A26"):
        retake.development_only({**record, "transitions": [{"case_id": "not-dev"}]}, sorted(dev))


# -- W27v2-A23 ------------------------------------------------------------------------------------


def test_w27v2_a23_the_library_route_is_the_registered_one(run: dict[str, Any]) -> None:
    (route,) = [r for r in run["record"]["snapshot"]["routes"] if r["provider_id"] == "pr-lib-v1"]
    assert route["components"] == S2_LIBRARY_ROUTE["components"]
    assert route["model_ids"] == S2_LIBRARY_ROUTE["model_ids"] == []
    assert run["record"]["snapshot_sha256"] == registration.sha256_bytes(
        registration.dump(run["record"]["snapshot"])
    )


# -- A27: the measurement does not expose ---------------------------------------------------------


def test_a27_1_the_installed_binder_has_no_library_basis() -> None:
    assert all(b.provider_id != "pr-lib-v1" for b in revision_binding.SELECTABLE_BASES)


def test_a27_2_the_default_snapshot_has_no_library_route() -> None:
    # S11 (ADR 0050 D9): the installed binder is read under W27 v1/v2 through `v2_binder`.
    from test_m06_w27_coverage import v2_binder  # noqa: PLC0415

    routes = snapshot.build_snapshot(binding=v2_binder())["routes"]
    assert all(r["provider_id"] != "pr-lib-v1" for r in routes)


def test_a27_3_nothing_under_benchmarks_l01_is_packaged() -> None:
    assert not [p for p in resources.PACKAGED if p.startswith("benchmarks/l01/")]


def test_a27_4_pr_lib_v1_stays_library_only_under_s04() -> None:
    assert LIBRARY_ONLY_PROVIDERS["pr-lib-v1"] == "S04"


def test_a27_5_the_record_says_measurement_only_under_version_2(run: dict[str, Any]) -> None:
    records = [run["record"]] + [
        json.loads(p.read_bytes()) for p in sorted(retake.EVIDENCE.glob("*/retake.json"))
    ]
    for record in records:
        assert record["selectable_in_build"] is False
        assert record["registration_version"] == 2
        assert record["binding"] == retake.BINDING_TEXT
        assert record["schema"] == retake.SCHEMA
