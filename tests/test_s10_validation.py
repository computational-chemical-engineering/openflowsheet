"""S10.A50-A53: the empirical validation of `wilson-ig-v1` (spec §9.6; WO-S10-6).

Validation, not verification: a result outside its band is reported "not validated within band"
(R-708). These tests do not require a band to be met; they require the committed report to be the
script's output, the bands to be §9.6's, and every verdict to follow from the raw numbers. VAL-2's
data are not yet supplied, so its assertions are skipped, never passed.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from conftest import REPO_ROOT

SCRIPT = REPO_ROOT / "scripts" / "s10_validation.py"
REPORT = REPO_ROOT / "benchmarks" / "s10" / "validation" / "report.json"
FIT_REPORT = REPO_ROOT / "benchmarks" / "s10" / "fit-report.json"


@pytest.fixture(scope="module")
def script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("s10_validation", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["s10_validation"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def report() -> dict[str, Any]:
    doc: dict[str, Any] = json.loads(Path(REPORT).read_text(encoding="utf-8"))
    return doc


def test_bands_are_the_registered_ones(script: ModuleType) -> None:
    assert script.BANDS == {
        "VAL-1": {"aad_T_K": 1.0, "aad_y": 0.015, "max_abs_dy": 0.05},
        "VAL-2": {"aad_dP_over_P": 0.03, "aad_y": 0.015},
        "VAL-3": {"dh_relative": 0.05, "cp_relative": 0.25},
    }
    assert script.P_TABLE_V == 101300.0 and script.P_REGISTERED == 101325.0


def test_report_is_the_scripts_output(script: ModuleType) -> None:
    sys.argv = ["s10_validation.py", "--check"]
    assert script.main() == 0


def test_a50_val1_numbers_follow_from_the_rows(report: dict[str, Any]) -> None:
    v = report["VAL-1"]
    rows = v["per_row"]
    assert v["rows"] == len(rows) == 38
    aad_t = sum(abs(r["dT_K"]) for r in rows) / len(rows)
    assert aad_t == pytest.approx(v["aad_T_K"], rel=1e-8)
    for i, c in enumerate(("CH3OH", "C2H5OH", "H2O")):
        assert sum(abs(r["dy"][i]) for r in rows) / len(rows) == pytest.approx(
            v["aad_y_by_component"][c], rel=1e-8
        )
        assert max(abs(r["dy"][i]) for r in rows) == pytest.approx(
            v["max_abs_dy_by_component"][c], rel=1e-8
        )
    for r in rows:
        assert sum(r["y_calc"]) == pytest.approx(1.0, abs=1e-8)
        assert r["dT_K"] == pytest.approx(r["T_calc_K"] - r["T_exp_K"], abs=1e-6)
    band = v["band"]
    judged = (
        v["aad_T_K"] <= band["aad_T_K"]
        and max(v["aad_y_by_component"][c] for c in ("CH3OH", "C2H5OH")) <= band["aad_y"]
        and max(v["max_abs_dy_by_component"][c] for c in ("CH3OH", "C2H5OH")) <= band["max_abs_dy"]
    )
    assert v["verdict"] == ("within band" if judged else "not validated within band")


def test_a50_bubble_point_is_a_bubble_point(script: ModuleType) -> None:
    provider = script._provider()
    x = (0.3, 0.3, 0.4)
    t, y = script.bubble(provider, x, script.P_TABLE_V)
    ks = script._k(provider, x, t, script.P_TABLE_V)
    assert sum(xi * ki for xi, ki in zip(x, ks, strict=True)) == pytest.approx(1.0, abs=1e-10)
    assert sum(y) == pytest.approx(1.0, abs=1e-12)
    assert 330.0 < t < 380.0


@pytest.mark.skip(reason="VAL-2 data not yet supplied")
def test_a51_val2_isothermal_binaries() -> None:
    raise AssertionError("pending")


def test_a52_val3_verdicts_follow_from_the_points(report: dict[str, Any]) -> None:
    v = report["VAL-3"]
    band = v["band"]
    assert [c["id"] for c in v["components"]] == ["CH3OH", "C2H5OH", "H2O"]
    all_ok = True
    for c in v["components"]:
        pts = c["points"]
        assert len(pts) == 11 and pts[0]["T_K"] == 300.0
        assert pts[-1]["T_K"] == pytest.approx(c["T_range_K"][1], rel=1e-9)
        for p in pts:
            assert p["dh_relative"] == pytest.approx(
                p["dh_model_J_mol"] / p["dHvap_eos_J_mol"] - 1.0, abs=1e-8
            )
            assert p["cp_relative"] == pytest.approx(
                p["cp_model_J_mol_K"] / p["cpL_eos_J_mol_K"] - 1.0, abs=1e-8
            )
        dh = max(abs(p["dh_relative"]) for p in pts)
        cp = max(abs(p["cp_relative"]) for p in pts)
        assert dh == pytest.approx(c["max_abs_dh_relative"], rel=1e-8)
        assert cp == pytest.approx(c["max_abs_cp_relative"], rel=1e-8)
        ok = dh <= band["dh_relative"] and cp <= band["cp_relative"]
        assert c["verdict"] == ("within band" if ok else "not validated within band")
        all_ok = all_ok and ok
    assert v["verdict"] == ("within band" if all_ok else "not validated within band")


def test_a52_eos_file_provenance() -> None:
    eos = json.loads((REPO_ROOT / "benchmarks/s10/validation/val3-eos.json").read_text("utf-8"))
    assert eos["coolprop_version"] == "8.0.0"
    assert [c["eos_bibtex_key"] for c in eos["components"]] == [
        "deReuck-BOOK-1993",
        "Schroeder-JPCRD-2014",
        "Wagner-JPCRD-2002",
    ]


def test_a53_fit_quality_is_reported_apart_from_validation(report: dict[str, Any]) -> None:
    fit = json.loads(FIT_REPORT.read_text(encoding="utf-8"))
    for f in fit["wilson"]:
        assert "aad_bubble_T_K" in f and "aad_bubble_y1" in f
    assert "VAL-2" in report and report["VAL-2"]["verdict"].startswith("PENDING")
    assert "validation, not verification" in report["convention"]


@pytest.mark.skip(reason="VAL-2 data not yet supplied")
def test_a53_val2_is_in_the_report() -> None:
    raise AssertionError("pending")
