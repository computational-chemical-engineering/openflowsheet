"""S10 real data and records (spec §9.1-§9.5, §9.7 and §15; assertions S10.A30-A34).

The expectations come from the committed inputs (`benchmarks/s10/saturation-points.json`,
`nasa7-low.json`, the transcription in `benchmarks/s10/vle/`) and from independent values stated
here, never from the provider. The records (`benchmarks/s10/records.yaml`,
`fit-report.json`) and the real section (`reference_values_real.yaml`) are committed; their
absence fails A30, A31, A33 and A34 rather than skipping them.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import re
import subprocess
import sys
from decimal import Decimal
from types import ModuleType
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT
from mpmath import mp, mpf  # type: ignore[import-untyped]

S10 = REPO_ROOT / "benchmarks" / "s10"
SCRIPTS = REPO_ROOT / "docs" / "derivations" / "scripts"
SATURATION = S10 / "saturation-points.json"
NASA = S10 / "nasa7-low.json"
TRANSCRIPTION_A = S10 / "vle" / "kurihara1993_binaries.A.csv"
RECORDS = S10 / "records.yaml"
FIT_REPORT = S10 / "fit-report.json"
IDS = ("CH3OH", "C2H5OH", "H2O")


def _script(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def records_script() -> ModuleType:
    return _script("s10_records")


@pytest.fixture(scope="module")
def saturation() -> dict[str, Any]:
    doc: dict[str, Any] = json.loads(SATURATION.read_text(encoding="utf-8"))
    return doc


def _needs_records() -> None:
    # The records are committed (WO-S10-3, spec §15 A2-5): their absence is a failure, not a skip.
    assert RECORDS.exists() and FIT_REPORT.exists()


# ================================================================================ §9.2


def test_saturation_points_cover_the_grid(saturation: dict[str, Any]) -> None:
    assert saturation["coolprop"]["version"] == "8.0.0"
    assert re.fullmatch(r"[0-9a-f]{40}", saturation["coolprop"]["gitrevision"])
    assert [c["id"] for c in saturation["components"]] == list(IDS)
    for c in saturation["components"]:
        points = c["points_T_K_P_Pa"]
        assert [t for t, _ in points] == [290.0 + 2 * k for k in range(61)]
        assert all(p > 0 for _, p in points)
        assert all(a[1] < b[1] for a, b in zip(points, points[1:], strict=False))
        assert c["eos_bibtex_key"]


def test_water_saturation_agrees_with_iapws95_v1(saturation: dict[str, Any]) -> None:
    # Spec §9.2: the deviation is recorded and must be <= 1e-8 relative. Recomputed here from
    # iapws95-v1 itself, against the committed CoolProp values.
    from openflowsheet.thermo.iapws95 import _saturation

    xcheck = saturation["water_crosscheck"]
    assert len(xcheck["points"]) == 5
    for point in xcheck["points"]:
        sat = _saturation(point["T_K"])
        assert sat is not None
        assert sat.pressure == point["P_iapws95_v1_Pa"]
        assert abs(point["P_coolprop_Pa"] / sat.pressure - 1.0) <= 1e-8


def test_saturation_check_never_passes_without_coolprop() -> None:
    script = SCRIPTS / "s10_saturation_points.py"
    run = subprocess.run(
        [sys.executable, str(script), "--check"], capture_output=True, text=True, check=False
    )
    if importlib.util.find_spec("CoolProp") is None:
        assert run.returncode == 2
        assert run.stdout.strip() == "UNAVAILABLE: CoolProp 8.0.0 not importable"
    else:
        assert run.returncode in (0, 2), run.stdout + run.stderr


# ================================================================================ S10.A32


def test_a32_the_vapour_pressure_fit_meets_its_claim(
    records_script: ModuleType, saturation: dict[str, Any]
) -> None:
    fits = records_script.vapour_pressure(saturation)
    for fit, comp in zip(fits, saturation["components"], strict=True):
        assert fit["range"] == (290.0, 410.0), "Q-N4's narrowing was not needed"
        worst = max(
            abs(records_script.ln_psat(fit["stored"], t) - mp.log(mpf(p)))
            for t, p in comp["points_T_K_P_Pa"]
        )
        assert worst <= mpf("2e-3"), (comp["id"], worst)
        # Stored to 12 significant digits (spec §9.3).
        for v in fit["stored"]:
            assert float(f"{v:.12g}") == v


def test_a32_the_fit_catches_a_wrong_coefficient(
    records_script: ModuleType, saturation: dict[str, Any]
) -> None:
    # A b coefficient off by 1e-3 relative (a units or transcription slip) breaks the claim.
    fit = records_script.vapour_pressure(saturation)[0]
    a, b, c, d = fit["stored"]
    points = saturation["components"][0]["points_T_K_P_Pa"]
    worst = max(
        abs(records_script.ln_psat((a, b * 1.001, c, d), t) - mp.log(mpf(p))) for t, p in points
    )
    assert worst > mpf("2e-3")


# ================================================================================ §9.5


def test_ideal_gas_rows_follow_nasa_exactly(records_script: ModuleType) -> None:
    nasa = json.loads(NASA.read_text(encoding="utf-8"))
    assert nasa["source_sha256"] == records_script.NASA_SHA256
    assert [s["id"] for s in nasa["species"]] == list(IDS)
    assert [s["note"] for s in nasa["species"]] == ["L 8/88", "L 8/88", "L 8/89"]
    rows = records_script.ideal_gas(nasa)
    for s, row in zip(nasa["species"], rows, strict=True):
        a = s["low_range_a1_a7"]
        assert row["b"] == [float(Decimal(a[k]) * 1000**k) for k in range(5)]


@pytest.mark.parametrize(
    ("index", "tabulated"),
    # NASA's tabulated standard formation enthalpies at 298.15 K (TM-4513 / thermo.inp), J/mol:
    # independent of the polynomial, which reproduces them to within its fit error.
    [(0, -200940.0), (1, -234950.0), (2, -241826.0)],
)
def test_formation_enthalpy_is_the_polynomials_own_h298(
    records_script: ModuleType, index: int, tabulated: float
) -> None:
    rows = records_script.ideal_gas(json.loads(NASA.read_text(encoding="utf-8")))
    assert abs(rows[index]["dhf"] - tabulated) <= 5.0


# ================================================================================ §9.4


def test_transcription_a_shape() -> None:
    with TRANSCRIPTION_A.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == ["system", "table", "row", "T_K", "x1", "y1"]
        rows = list(reader)
    counts = {
        s: sum(r["system"] == s for r in rows)
        for s in ("methanol+ethanol", "methanol+water", "ethanol+water")
    }
    assert counts == {"methanol+ethanol": 11, "methanol+water": 20, "ethanol+water": 18}
    for system in counts:
        block = [r for r in rows if r["system"] == system]
        assert [int(r["row"]) for r in block] == list(range(1, len(block) + 1))
        assert all(r["table"] == "II" for r in block)
        assert all(re.fullmatch(r"0\.\d{3}", r[k]) for r in block for k in ("x1", "y1"))
        assert all(re.fullmatch(r"3\d\d\.\d\d", r["T_K"]) for r in block)


def _synthetic_binary(records_script: ModuleType, t12: str, t21: str) -> dict[str, Any]:
    """Exact ln gamma data from known theta: the fit must return theta itself."""
    data = []
    for k in range(1, 20):
        x1 = mpf(k) / 20
        lg, _ = records_script.ln_gamma_binary(x1, mpf(t12), mpf(t21))
        data.append({"x1": x1, "lgexp": lg, "used": [True, True]})
    return {"label": "synthetic", "data": data}


def test_wilson_jacobian_matches_a_50_digit_derivative(records_script: ModuleType) -> None:
    x1, t12, t21 = mpf("0.3"), mpf("1.2"), mpf("-0.4")
    _, jac = records_script.ln_gamma_binary(x1, t12, t21)
    for i in range(2):
        d12 = mp.diff(lambda a, i=i: records_script.ln_gamma_binary(x1, a, t21)[0][i], t12)
        d21 = mp.diff(lambda b, i=i: records_script.ln_gamma_binary(x1, t12, b)[0][i], t21)
        assert abs(jac[i][0] - d12) < mpf("1e-40")
        assert abs(jac[i][1] - d21) < mpf("1e-40")


def test_the_gauss_newton_start_is_singular(records_script: ModuleType) -> None:
    # B-26: at theta = 0 both columns of J equal x_j^2, so the step must be the minimum-norm one.
    x1 = mpf("0.3")
    _, jac = records_script.ln_gamma_binary(x1, mpf(0), mpf(0))
    assert jac[0][0] == jac[0][1] and abs(jac[0][0] - (1 - x1) ** 2) < mpf("1e-45")
    assert jac[1][0] == jac[1][1] and abs(jac[1][0] - x1**2) < mpf("1e-45")


def test_gauss_newton_recovers_known_parameters(records_script: ModuleType) -> None:
    b = _synthetic_binary(records_script, "1.8", "0.15")
    fit = records_script.gauss_newton(b)
    assert abs(fit["theta"][0] - mpf("1.8")) < mpf("1e-25")
    assert abs(fit["theta"][1] - mpf("0.15")) < mpf("1e-25")
    assert fit["phi"] < mpf("1e-50")


def test_records_check_refuses_without_the_double_entered_transcription(tmp_path: Any) -> None:
    absent = tmp_path / "absent.csv"
    run = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "s10_records.py"),
            "--check",
            "--vle",
            str(absent),
            "--out-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 2
    assert run.stdout.startswith("UNAVAILABLE: ")


# ================================================================================ S10.A30, A31, A33


def test_a30_records_validate() -> None:
    _needs_records()
    from test_schemas_p01 import validator_for

    from openflowsheet.thermo.wilson_ig import load_records

    raw = RECORDS.read_text(encoding="utf-8")
    doc = yaml.safe_load(raw)
    assert doc["reference_convention"] == "WILSON-IG-ref-v1" and doc["synthetic"] is False
    assert [c["id"] for c in doc["components"]] == list(IDS)
    validator = validator_for("component_record")
    for record in doc["components"]:
        assert not list(validator.iter_errors(record)), record["id"]
        assert "identifiers" not in record
        assert all(p["provenance"] for p in record["parameters"].values())
        assert record["rights"]["source"] and record["rights"]["redistribution"]
    assert all(e["provenance"] for e in doc["wilson_lambda"])
    assert not re.search(r"\b\d{2,7}-\d{2}-\d\b", raw), "no CAS RN"
    load_records(RECORDS)


def test_a31_records_check_reproduces_the_committed_files() -> None:
    _needs_records()
    run = subprocess.run(
        [sys.executable, str(SCRIPTS / "s10_records.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + run.stderr


def test_a33_the_lambda_fit_claims_hold() -> None:
    _needs_records()
    report = json.loads(FIT_REPORT.read_text(encoding="utf-8"))
    assert [f["binary"] for f in report["wilson"]] == [
        "methanol+ethanol",
        "ethanol+water",
        "methanol+water",
    ]
    for fit in report["wilson"]:
        assert fit["gauss_newton_iterations"] <= 200
        assert fit["grid_margin_over_phi_star"] >= -1e-12
        assert len(fit["per_point"]) == fit["points"]
    # Spec §15 A2-1/A2-5: every listed claim is present by id and holds, so a dropped claim fails.
    holds = {c["id"]: c["holds"] for c in report["claims"]}
    binaries = ("methanol+ethanol", "ethanol+water", "methanol+water")
    want = [
        f"LAMBDA{kind}-{b}" for b in binaries for kind in ("-GRID64", "-CONV", "-BOX", "", "-MIN")
    ]
    want += [f"LAMBDA-V1-{b}" for b in ("ethanol+water", "methanol+water")]
    want += ["LAMBDA-CURVE-methanol+ethanol", "WILSON-SINGULAR-CURVE"]
    assert len(want) == 19
    missing = [cid for cid in want if cid not in holds]
    assert not missing, missing
    assert all(holds[cid] is True for cid in want)
    assert len(holds) == 25 and all(v is True for v in holds.values())


def test_a33_the_stored_lambda_are_amendment_2s() -> None:
    # Spec §15 A2-1, "Results": the stored Λ (10 significant digits) and the iteration counts.
    report = json.loads(FIT_REPORT.read_text(encoding="utf-8"))
    want = {
        "methanol+ethanol": ((0.6109248362, 1.49887856), 19),
        "ethanol+water": ((0.1649874985, 0.8615311153), 21),
        "methanol+water": ((0.3674022637, 1.134238098), 28),
    }
    for fit in report["wilson"]:
        lam, iterations = want[fit["binary"]]
        assert tuple(fit["lambda_stored"].values()) == lam, fit["binary"]
        assert fit["gauss_newton_iterations"] == iterations, fit["binary"]
    stored = {
        (e["i"], e["j"]): e["value"] for e in yaml.safe_load(RECORDS.read_text())["wilson_lambda"]
    }
    assert stored == {
        ("CH3OH", "C2H5OH"): 0.6109248362,
        ("C2H5OH", "CH3OH"): 1.49887856,
        ("C2H5OH", "H2O"): 0.1649874985,
        ("H2O", "C2H5OH"): 0.8615311153,
        ("CH3OH", "H2O"): 0.3674022637,
        ("H2O", "CH3OH"): 1.134238098,
    }
    me = report["wilson"][0]
    assert me["start_theta_zero"]["converged"] is False
    assert me["second_local_minimum"]["phi"] > me["phi_star"]


# ================================================================================ S10.A34


REAL_REFERENCE = S10 / "reference_values_real.yaml"
REAL_PROPERTIES = ("h", "lnphi_CH3OH", "lnphi_C2H5OH", "lnphi_H2O")
REAL_INPUTS = ("T", "P", "n_CH3OH", "n_C2H5OH", "n_H2O")


def test_a34_real_e_states_through_the_provider() -> None:
    # The evaluate_phase half of A34 (spec §9.7, tolerances of §7.2).
    from openflowsheet.thermo import PropertyRequest, StreamState
    from openflowsheet.thermo.wilson_ig import WilsonIdealGasProvider

    reference = yaml.safe_load(REAL_REFERENCE.read_text(encoding="utf-8"))
    provider = WilsonIdealGasProvider(None)
    tol = reference["tolerances"]["evaluate_phase_relative"]
    for sid, entry in reference["closed_form"]["evaluate_phase"].items():
        st = entry["state"]
        n_tot, pressure = sum(st["n"]), st["P"]
        for phase in ("LIQUID", "VAPOR"):
            request = PropertyRequest(
                state=StreamState(n=tuple(st["n"]), temperature=st["T"], pressure=pressure),
                phase=phase,
                properties=REAL_PROPERTIES,
                derivatives=REAL_INPUTS,
            )
            result = provider.evaluate_phase(request, None)  # type: ignore[arg-type]
            want = entry[phase]
            for prop in REAL_PROPERTIES:
                w = want["values"][prop]
                s = 1.0e3 if prop == "h" else 1.0
                assert abs(result.values[prop] - w) <= tol * max(abs(w), s), (sid, phase, prop)
                for wrt in REAL_INPUTS:
                    w = want["derivatives"][prop][wrt]
                    if w == 0.0:
                        assert result.derivatives[prop][wrt] == 0.0, (sid, phase, prop, wrt)
                        continue
                    if prop == "h":
                        s = {"T": 10.0, "P": 0.0}.get(wrt, 1.0e3 / n_tot)
                    else:
                        s = {"T": 1.0e-2, "P": 1.0 / pressure}.get(wrt, 1.0 / n_tot)
                    got = result.derivatives[prop][wrt]
                    assert abs(got - w) <= tol * max(abs(w), s), (sid, phase, prop, wrt)


# -- S10.A34, the flash half: I1-I14 (spec §8.1 as amended by §15 A2-3) through the provider's
#    flash, with §7.3's tolerances from the real section (floors re-measured on these states).

TOL_BALANCE = 1.0e-13  # spec §7.3: |n^V_i + n^L_i - n_i| <= 1e-13 n_tot


@pytest.fixture(scope="module")
def real_reference() -> dict[str, Any]:
    reference: dict[str, Any] = yaml.safe_load(REAL_REFERENCE.read_text(encoding="utf-8"))
    return reference


@pytest.fixture(scope="module")
def real_flashes(real_reference: dict[str, Any]) -> dict[str, Any]:
    from openflowsheet.thermo import FlashRequest, StreamState
    from openflowsheet.thermo.wilson_ig import WilsonIdealGasProvider

    provider = WilsonIdealGasProvider(None)
    out = {}
    for sid, entry in real_reference["closed_form"]["flash"].items():
        st = entry["state"]
        state = StreamState(n=tuple(st["n"]), temperature=st["T"], pressure=st["P"])
        out[sid] = (state, provider.flash(FlashRequest(state=state), None))  # type: ignore[arg-type]
    return out


def _real_tm(message: str, key: str) -> float | None:
    match = re.search(rf"{key}: ([^;]+)", message)
    assert match is not None, message
    return None if match.group(1) == "not_evaluated" else float(match.group(1))


def test_a34_the_real_section_is_on_the_committed_records(real_reference: dict[str, Any]) -> None:
    import hashlib

    assert real_reference["records_sha256"] == hashlib.sha256(RECORDS.read_bytes()).hexdigest()
    assert sorted(real_reference["closed_form"]["flash"], key=lambda k: int(k[1:])) == [
        f"I{k}" for k in range(1, 15)
    ]
    assert real_reference["closed_form"]["flash"]["I10"]["state"]["n"] == [0.0, 0.4, 0.6]
    assert all(c["holds"] is True for c in real_reference["generator_claims"])


def test_a34_real_flash_through_the_provider(
    real_reference: dict[str, Any], real_flashes: dict[str, Any]
) -> None:
    tol_tm = real_reference["tolerances"]["tm"]["TOL_TM"]
    per_state = real_reference["tolerances"]["flash"]["per_state"]
    worst = (0.0, "")
    for sid, entry in real_reference["closed_form"]["flash"].items():
        state, result = real_flashes[sid]
        assert result.status == "ok", (sid, result.message)
        assert result.provider_id == "wilson-ig-v1"
        assert result.reference_convention == "WILSON-IG-ref-v1"
        assert result.phase_signature == entry["phase_signature"], sid
        for key in ("tm_vapour_trial", "tm_liquid_trial"):
            got, want = _real_tm(result.message, key), entry["stability"][key]
            if want is None:
                assert got is None, (sid, key)
            else:
                assert got is not None and abs(got - want) <= tol_tm, (sid, key, got, want)
        assert result.vapor is not None and result.liquid is not None
        if entry["phase_signature"] in ("LIQUID", "VAPOR"):
            # §7.3: single-phase outlets bitwise, the other outlet dormant
            liquid = entry["phase_signature"] == "LIQUID"
            named, other = (
                (result.liquid, result.vapor) if liquid else (result.vapor, result.liquid)
            )
            assert named == state and [v.hex() for v in named.n] == [v.hex() for v in state.n]
            assert all(v == 0.0 for v in other.n), sid
            assert (other.temperature, other.pressure) == (state.temperature, state.pressure)
            assert result.vapor_fraction == entry["vapor_fraction"] and result.k_values == {}
            continue
        tolerance = per_state[sid]["per_output"]
        assert result.vapor_fraction is not None
        ratios = {"beta": abs(result.vapor_fraction - entry["vapor_fraction"]) / tolerance["beta"]}
        vapor_total, liquid_total = sum(result.vapor.n), sum(result.liquid.n)
        for i, c in enumerate(IDS):
            if state.n[i] == 0.0:  # an absent component: exact zeros, K at infinite dilution
                assert result.vapor.n[i] == 0.0 and result.liquid.n[i] == 0.0, (sid, c)
            outputs = {
                "nV": (result.vapor.n[i], entry["vapor_n"][c]),
                "nL": (result.liquid.n[i], entry["liquid_n"][c]),
                "y": (result.vapor.n[i] / vapor_total, entry["y"][c]),
                "x": (result.liquid.n[i] / liquid_total, entry["x"][c]),
            }
            for key, (got, want) in outputs.items():
                if f"{key}_{c}" in tolerance:
                    ratios[f"{key}_{c}"] = abs(got - want) / tolerance[f"{key}_{c}"]
            k_tol = tolerance.get(f"k_relative_{c}", tolerance["k_relative"])
            ratios[f"K_{c}"] = abs(result.k_values[c] / entry["k_values"][c] - 1.0) / k_tol
            assert abs(result.vapor.n[i] + result.liquid.n[i] - state.n[i]) <= (
                TOL_BALANCE * state.total_flow
            ), (sid, c)
        key = max(ratios, key=ratios.__getitem__)
        assert ratios[key] <= 1.0, (sid, key, ratios[key])
        worst = max(worst, (ratios[key], f"{sid}.{key}"))
    assert worst[0] <= 1.0, worst
