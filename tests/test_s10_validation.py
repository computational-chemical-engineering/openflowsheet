"""S10.A50-A53: the empirical validation of `wilson-ig-v1` (spec §9.6; WO-S10-6).

Validation, not verification: a result outside its band is reported "not validated within band"
(R-708). These tests do not require a band to be met; they require the committed report to be the
script's output, the bands to be §9.6's, and every verdict to follow from the raw numbers. VAL-2's
assertions are S10.A51.1-A51.10 and S10.A53.1-A53.2 of spec §19 A6-8; its independent closed form
(binary64 sum_i x_i gamma_i P_i^sat from the records files by (3.3) and (3.8)) is written here,
with no import from `thermo/wilson_ig.py`.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import math
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT

SCRIPT = REPO_ROOT / "scripts" / "s10_validation.py"
REPORT = REPO_ROOT / "benchmarks" / "s10" / "validation" / "report.json"
FIT_REPORT = REPO_ROOT / "benchmarks" / "s10" / "fit-report.json"
S10 = REPO_ROOT / "benchmarks" / "s10"
REAL_RECORDS = S10 / "records.yaml"
SYNTHETIC_RECORDS = S10 / "verification-records.yaml"
VAL2_FILES = [S10 / "vle" / f"kurihara1995_binaries{s}.csv" for s in ("", ".A", ".B")]
VAL2_SHA256 = "e129027986fa9c15ebf8e00d5fa040497708cb0c7a9d483263eefe2ba98090bb"  # §19 A6-1
VAL2_BLOCK_SIZES = [14, 20, 18, 37, 34, 36]  # §19 A6-1, in file order
VAL2_MD = REPO_ROOT / "docs" / "s10-validation-report.md"
#: The report's system names to the alcohol's slot in (CH3OH, C2H5OH, H2O); written here (A51.10).
SYSTEM_SLOT = {"methanol+water": 0, "ethanol+water": 1}
VERDICTS = ("within band", "not validated within band")

#: §19 A6-8's registered states. Each binary is (i, j) in the records' order; x_1 goes to slot i
#: and 1 - x_1 to slot j (A6-3 step 2). None is a data point.
X1_SET = (0.02, 0.1, 0.25, 0.5, 0.75, 0.9, 0.98)
STATE_SETS = {
    "S": {
        "records": SYNTHETIC_RECORDS,
        "binaries": ((0, 2), (1, 2), (0, 1)),
        "T": (300.0, 323.15, 333.15, 350.0, 380.0, 420.0),
        "P_eval": (5e4, 1e5, 101325.0, 3e5),
    },
    "R": {
        "records": REAL_RECORDS,
        "binaries": ((0, 2), (1, 2)),
        "T": (300.0, 350.0, 400.0),
        "P_eval": (3e4, 1e5, 101325.0, 2e5),
    },
}


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
    assert script.P_EVAL_VAL2 == 101325.0
    assert script.VAL2_SHA256 == VAL2_SHA256


def _embed(pair: tuple[int, int], x1: float) -> tuple[float, float, float]:
    n = [0.0, 0.0, 0.0]
    n[pair[0]], n[pair[1]] = x1, 1.0 - x1
    return (n[0], n[1], n[2])


def _closed_form(
    doc: dict[str, Any],
    n: tuple[float, ...],
    t: float,
    swap: tuple[int, int] | None = None,
) -> tuple[float, list[float]]:
    """binary64 P = sum_i x_i gamma_i P_i^sat and y_i = x_i gamma_i P_i^sat / P, from the records
    document by (3.3) and (3.8); with `swap`, that pair's Lambda_ij and Lambda_ji are exchanged."""
    ids = [c["id"] for c in doc["components"]]
    theta = t / 1000.0
    psat = []
    for c in doc["components"]:
        a, b, cc, d = (c["parameters"][f"vapour_pressure_{k}"]["value"] for k in "abcd")
        psat.append(math.exp(a + b / theta + cc * math.log(theta) + d * theta**2))
    lam = [[1.0] * 3 for _ in range(3)]
    for e in doc["wilson_lambda"]:
        lam[ids.index(e["i"])][ids.index(e["j"])] = float(e["value"])
    if swap is not None:
        i, j = swap
        lam[i][j], lam[j][i] = lam[j][i], lam[i][j]
    s = [sum(n[j] * lam[i][j] for j in range(3)) for i in range(3)]
    lng = [1.0 - math.log(s[i]) - sum(n[k] * lam[k][i] / s[k] for k in range(3)) for i in range(3)]
    terms = [n[i] * math.exp(lng[i]) * psat[i] for i in range(3)]
    p = sum(terms)
    return p, [v / p for v in terms]


def _states(name: str) -> list[tuple[tuple[int, int], tuple[float, float, float], float]]:
    st = STATE_SETS[name]
    return [
        (pair, _embed(pair, x1), t) for pair in st["binaries"] for t in st["T"] for x1 in X1_SET
    ]


def _sum_nk(provider: Any, n: tuple[float, ...], t: float, p: float) -> float:
    from openflowsheet.thermo import PropertyRequest, StreamState

    ids = provider.describe().components
    res = provider.evaluate_phase(
        PropertyRequest(
            state=StreamState(n=n, temperature=t, pressure=p),
            phase="LIQUID",
            properties=tuple(f"lnphi_{c}" for c in ids),
        ),
        None,
    )
    assert res.status == "ok", res
    return sum(ni * math.exp(res.values[f"lnphi_{c}"]) for ni, c in zip(n, ids, strict=True))


def test_a51_val2_transcription_is_double_entered() -> None:
    """S10.A51.1: the three files are byte-identical, hash to A6-1's SHA-256, and satisfy C2-C4."""
    raw = [f.read_bytes() for f in VAL2_FILES]
    assert raw[0] == raw[1] == raw[2]
    assert hashlib.sha256(raw[0]).hexdigest() == VAL2_SHA256
    lines = raw[0].decode("utf-8").split("\n")
    assert lines[0] == "system,table,row,T_K,P_kPa,x1,y1" and lines[-1] == ""
    rows = list(csv.reader(lines[1:-1]))
    assert all(len(r) == 7 for r in rows)
    blocks: list[tuple[str, str, str]] = []
    sizes: list[int] = []
    for system, table, row, t_k, p_kpa, x1, y1 in rows:
        if not blocks or blocks[-1] != (system, table, t_k):
            blocks.append((system, table, t_k))
            sizes.append(0)
        sizes[-1] += 1
        assert row == str(sizes[-1])
        assert re.fullmatch(r"[0-9]+\.[0-9]{3}", p_kpa)
        assert re.fullmatch(r"0\.[0-9]{4}", x1) and re.fullmatch(r"0\.[0-9]{4}", y1)
        assert 0.0 < float(x1) < 1.0 and 0.0 < float(y1) < 1.0
    assert blocks == [
        (system, table, t_k)
        for system, table in (("methanol+water", "2"), ("ethanol+water", "3"))
        for t_k in ("323.15", "328.15", "333.15")
    ]
    assert sizes == VAL2_BLOCK_SIZES and sum(sizes) == len(rows) == 159


def test_a51_val2_bubble_pressure_is_the_closed_form(script: ModuleType) -> None:
    """S10.A51.2-A51.5 on the registered states of sets S and R (spec §19 A6-8)."""
    from openflowsheet.thermo.wilson_ig import WilsonIdealGasProvider

    for name, st in STATE_SETS.items():
        provider = WilsonIdealGasProvider(st["records"])
        doc = yaml.safe_load(Path(st["records"]).read_text(encoding="utf-8"))
        p_lo, p_hi = provider.describe().domain["P"]
        inside: set[tuple[int, int]] = set()
        below: set[tuple[int, int]] = set()
        for pair, n, t in _states(name):
            where = f"{name} {pair} T={t} n={n}"
            p_ref, y_ref = script.bubble_p(provider, n, t, 101325.0)
            # A51.2: independent of P_eval.
            for p_eval in st["P_eval"]:
                p, y = script.bubble_p(provider, n, t, p_eval)
                assert abs(p / p_ref - 1.0) <= 1e-12, where
                assert max(abs(a - b) for a, b in zip(y, y_ref, strict=True)) <= 1e-12, where
            # A51.3: the independent closed form.
            p_cf, y_cf = _closed_form(doc, n, t)
            assert abs(p_ref / p_cf - 1.0) <= 1e-12, where
            assert max(abs(a - b) for a, b in zip(y_ref, y_cf, strict=True)) <= 1e-12, where
            # A51.4: the bubble condition where P_calc is in the domain.
            if p_lo <= p_ref <= p_hi:
                inside.add(pair)
                assert abs(_sum_nk(provider, n, t, p_ref) - 1.0) <= 1e-12, where
            elif p_ref < p_lo:
                below.add(pair)
            # A51.5: a transposed Lambda would show.
            if n[pair[0]] in (0.02, 0.98):
                p_sw, _ = _closed_form(doc, n, t, swap=pair)
                assert abs(p_sw / p_ref - 1.0) > 1e-6, where
        assert inside == below == set(st["binaries"]), name


def _val2_rows() -> list[dict[str, str]]:
    with VAL2_FILES[0].open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _sig(v: float) -> float:
    return float(f"{v:.10g}")


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


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


def test_a51_val2_isothermal_binaries(script: ModuleType, report: dict[str, Any]) -> None:
    """S10.A51.6-A51.10 on the committed report (spec §19 A6-8)."""
    v = report["VAL-2"]
    csv_rows, per = _val2_rows(), v["per_row"]
    # A51.6: shape, order and echo of the data.
    assert v["rows"] == len(per) == len(csv_rows) == 159
    assert v["transcription_sha256"] == VAL2_SHA256 and v["P_eval_Pa"] == 101325.0
    domain = script._provider().describe().domain["P"]
    assert v["records_P_domain_Pa"] == [domain[0], domain[1]]
    assert [(b["system"], b["table"], b["rows"]) for b in v["binaries"]] == [
        ("methanol+water", 2, 52),
        ("ethanol+water", 3, 107),
    ]
    assert [[(i["T_K"], i["rows"]) for i in b["isotherms"]] for b in v["binaries"]] == [
        [(323.15, 14), (328.15, 20), (333.15, 18)],
        [(323.15, 37), (328.15, 34), (333.15, 36)],
    ]
    for r, c in zip(per, csv_rows, strict=True):
        assert (r["system"], r["T_K"], r["row"], r["x1"], r["y1_exp"]) == (
            c["system"],
            float(c["T_K"]),
            int(c["row"]),
            float(c["x1"]),
            float(c["y1"]),
        )
        assert r["P_exp_Pa"] == _sig(1000.0 * float(c["P_kPa"]))
    # A51.7: the per-row identities and flags.
    bound = v["records_P_domain_Pa"][0]
    for r in per:
        assert r["dP_over_P"] == pytest.approx(
            (r["P_calc_Pa"] - r["P_exp_Pa"]) / r["P_exp_Pa"], rel=0, abs=1e-8
        )
        assert r["dy1"] == pytest.approx(r["y1_calc"] - r["y1_exp"], rel=0, abs=1e-8)
        assert r["y1_calc"] + r["y_water_calc"] == pytest.approx(1.0, rel=0, abs=1e-8)
        assert r["P_exp_below_domain"] == (r["P_exp_Pa"] < bound)
        assert r["P_calc_below_domain"] == (r["P_calc_Pa"] < bound)

    # A51.8: every aggregate follows from the rows.
    def close(a: float, b: float) -> bool:
        return abs(a - b) <= 1e-8

    for b in v["binaries"]:
        mine = [r for r in per if r["system"] == b["system"]]
        dp, dy = [r["dP_over_P"] for r in mine], [r["dy1"] for r in mine]
        dyw = [r["y_water_calc"] - (1.0 - r["y1_exp"]) for r in mine]
        assert close(b["aad_dP_over_P"], _mean([abs(x) for x in dp]))
        assert close(b["aad_y1"], _mean([abs(x) for x in dy]))
        assert close(b["max_abs_dP_over_P"], max(abs(x) for x in dp))
        assert close(b["max_abs_dy1"], max(abs(x) for x in dy))
        assert close(b["mean_dP_over_P"], _mean(dp)) and close(b["mean_dy1"], _mean(dy))
        assert close(b["aad_y_water"], _mean([abs(x) for x in dyw]))
        assert close(b["aad_y_water"], b["aad_y1"])
        assert b["n_P_exp_below_domain"] == sum(r["P_exp_below_domain"] for r in mine)
        assert b["n_P_calc_below_domain"] == sum(r["P_calc_below_domain"] for r in mine)
        for iso in b["isotherms"]:
            blk = [r for r in mine if r["T_K"] == iso["T_K"]]
            assert iso["rows"] == len(blk)
            assert close(iso["aad_dP_over_P"], _mean([abs(r["dP_over_P"]) for r in blk]))
            assert close(iso["aad_y1"], _mean([abs(r["dy1"]) for r in blk]))
            assert close(iso["mean_dP_over_P"], _mean([r["dP_over_P"] for r in blk]))
            assert close(iso["mean_dy1"], _mean([r["dy1"] for r in blk]))
    pooled = v["pooled_not_judged"]
    assert pooled["rows"] == 159
    assert close(pooled["aad_dP_over_P"], _mean([abs(r["dP_over_P"]) for r in per]))
    assert close(pooled["aad_y1"], _mean([abs(r["dy1"]) for r in per]))
    # A51.9: the verdicts follow from the stored aggregates and §9.6's band.
    assert v["band"] == script.BANDS["VAL-2"] == {"aad_dP_over_P": 0.03, "aad_y": 0.015}
    for b in v["binaries"]:
        within = {
            "aad_dP_over_P": b["aad_dP_over_P"] <= 0.03,
            "aad_y": b["aad_y1"] <= 0.015,
        }
        assert b["within_band"] == within
        assert b["verdict"] == VERDICTS[0 if all(within.values()) else 1]
    both = all(b["verdict"] == "within band" for b in v["binaries"])
    assert v["verdict"] == VERDICTS[0 if both else 1]
    # A51.10: every stored model value is the independent closed form at the row's (T, x_1).
    doc = yaml.safe_load(REAL_RECORDS.read_text(encoding="utf-8"))
    for r in per:
        slot = SYSTEM_SLOT[r["system"]]
        p_cf, y_cf = _closed_form(doc, _embed((slot, 2), r["x1"]), r["T_K"])
        assert abs(r["P_calc_Pa"] / p_cf - 1.0) <= 1e-9, r
        assert abs(r["y1_calc"] - y_cf[slot]) <= 1e-9, r


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
    assert "validation, not verification" in report["convention"]


def _strings(node: Any) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for k, val in node.items() for s in (*_strings(k), *_strings(val))]
    if isinstance(node, list):
        return [s for val in node for s in _strings(val)]
    return []


def test_a53_val2_is_in_the_report(report: dict[str, Any]) -> None:
    """S10.A53.1: VAL-2 is reported with a verdict; S10.A53.2: its data entered no fit."""
    v = report["VAL-2"]
    assert v["verdict"] in VERDICTS
    assert all(b["verdict"] in VERDICTS for b in v["binaries"])
    assert not any(s.startswith("PENDING") for s in _strings(v))
    md = VAL2_MD.read_text(encoding="utf-8").splitlines()
    assert any(line.startswith("## VAL-2: isothermal binaries, ") for line in md)
    assert f"VAL-2 verdict: **{v['verdict']}**." in md
    fit = FIT_REPORT.read_text(encoding="utf-8")
    assert "1995" not in fit and "kurihara1995" not in fit
    records = yaml.safe_load(REAL_RECORDS.read_text(encoding="utf-8"))
    provenances = [e["provenance"] for e in records["wilson_lambda"]]
    assert provenances and all("38 (1993)" in p and "40 (1995)" not in p for p in provenances)
