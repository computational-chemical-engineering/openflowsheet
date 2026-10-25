"""S10 DWSIM reference comparison (spec §8.2, §15 A2-3; assertion S10.A45).

The gate never runs a tool: these tests read the committed tool record
`benchmarks/s10/dwsim/qualification.json` (written by `spikes/references/s10_qualify_dwsim.py` in
the DWSIM environment) and recompute from its raw fields, independently of the summaries in
`comparison.json`:

* the mapping: every DWSIM compound constant against §8.2's rule recomputed from `records.yaml`,
  the applied Wilson A_ij against DWSIM's form with DWSIM's own volumes, and the BIPs DWSIM reads
  back;
* the gamma readback (§8.2, 1e-9 relative before the flash) against the generator's closed forms
  (`s10_reference.Model` on `records.yaml`, 50 digits), and the pure-component readbacks; DWSIM's
  ideal-gas enthalpy is reproduced exactly as the midpoint-rule integral it is;
* the ladder's registered settings, the completeness of the attempt record and the selection
  rule, and `comparison.json` recomputing byte for byte. The verdict per state is the `verdict`
  agent's, not a test's.
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from types import ModuleType
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT
from mpmath import mp, mpf  # type: ignore[import-untyped]

S10 = REPO_ROOT / "benchmarks" / "s10"
DWSIM = S10 / "dwsim"
IDS = ("CH3OH", "C2H5OH", "H2O")
R = 8.31446261815324
R_CAL = 1.9872  # DWSIM 9.0.5 WilsonModel.vb
RB_X = ([0.2, 0.3, 0.5], [0.6, 0.2, 0.2])


def _module(name: str, path: Any) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def qual() -> dict[str, Any]:
    # The records are the work order's deliverable: their absence fails, it does not skip.
    doc: dict[str, Any] = json.loads((DWSIM / "qualification.json").read_text(encoding="utf-8"))
    return doc


@pytest.fixture(scope="module")
def rec() -> dict[str, Any]:
    doc: dict[str, Any] = yaml.safe_load((S10 / "records.yaml").read_bytes())
    return doc


@pytest.fixture(scope="module")
def real() -> dict[str, Any]:
    doc: dict[str, Any] = yaml.safe_load((S10 / "reference_values_real.yaml").read_bytes())
    return doc


@pytest.fixture(scope="module")
def gen() -> ModuleType:
    return _module(
        "s10_reference", REPO_ROOT / "docs" / "derivations" / "scripts" / "s10_reference.py"
    )


@pytest.fixture(scope="module")
def model(gen: ModuleType) -> Any:
    return gen.Model(gen.load_records(S10 / "records.yaml"))


def _lam(rec: dict[str, Any]) -> list[list[float]]:
    lam = [[1.0] * 3 for _ in range(3)]
    for e in rec["wilson_lambda"]:
        lam[IDS.index(e["i"])][IDS.index(e["j"])] = float(e["value"])
    return lam


# ---------------------------------------------------------------------------- the record


def test_a45_environment_and_blindness(qual: dict[str, Any], real: dict[str, Any]) -> None:
    assert qual["environment_fingerprint"]["matches"]
    assert qual["versions"]["dwsim"].startswith("DWSIM version 9.0.5.0")
    assert qual["versions"]["dotnet_runtime"].startswith("8.0.")
    assert sorted(qual["states"]) == sorted(real["closed_form"]["i_states"])
    for sid, st in qual["states"].items():
        assert st["state"] == {
            k: real["closed_form"]["i_states"][sid]["state"][k] for k in ("n", "T", "P")
        }
        assert "error" not in st
    # The tool reads inputs.json only and imports nothing of this project (S03's form).
    src = (REPO_ROOT / "spikes" / "references" / "s10_qualify_dwsim.py").read_text("utf-8")
    assert "import openflowsheet" not in src and "from openflowsheet" not in src
    assert "reference_values" not in src
    inputs = (DWSIM / "inputs.json").read_text("utf-8")
    assert "closed_form" not in json.loads(inputs)["i_states"]["states"]["I1"]


def test_a45_settings_read_back(qual: dict[str, Any]) -> None:
    sb, st = qual["settings_readback"], qual["settings"]
    assert sb["property_package"] == "Wilson"
    for k, v in st["property_package_options"].items():
        assert sb["options"][k] == str(v)
    for k, v in st["flash"]["flash_settings_fixed"].items():
        assert sb["flash_settings"][k] == v
    assert sb["RET_VNAMES"] == [f"S10-{c}" for c in IDS]


def test_a45_compound_mapping(qual: dict[str, Any], rec: dict[str, Any]) -> None:
    """Spec 8.2's mapping, recomputed here from records.yaml."""
    comps = qual["settings_readback"]["compounds"]
    for c in rec["components"]:
        p = {k: float(v["value"]) for k, v in c["parameters"].items()}
        mw = float(c["molecular_weight"]["value"]) * 1000.0
        a, b, cc, d = (p[f"vapour_pressure_{s}"] for s in "abcd")
        bk = [p[f"ideal_gas_cp_b{k}"] for k in range(5)]
        want = {
            "Vapor_Pressure_Constant_A": a - cc * math.log(1000.0),
            "Vapor_Pressure_Constant_B": 1000.0 * b,
            "Vapor_Pressure_Constant_C": cc,
            "Vapor_Pressure_Constant_D": d * 1e-6,
            "Vapor_Pressure_Constant_E": 2.0,
            "HVap_A": -1000.0 * R * b * 1000.0,
            "HVap_B": R * cc * 1000.0,
            "HVap_C": 0.0,
            "HVap_D": 2.0 * R * d * 1e-6 * 1000.0,
            "HVap_E": 0.0,
            "IG_Enthalpy_of_Formation_25C": p["standard_formation_enthalpy"] / mw,
            "Molar_Weight": mw,
            "Liquid_Density_Const_A": 1.0e12,
        }
        want.update(
            {
                f"Ideal_Gas_Heat_Capacity_Const_{'ABCDE'[k]}": 1000.0 * R * bk[k] / 1000.0**k
                for k in range(5)
            }
        )
        got = comps[c["id"]]
        for k, v in want.items():
            assert got[k] == pytest.approx(v, rel=1e-15, abs=0.0), (c["id"], k)
        assert got["VaporPressureEquation"] == "101"
        assert got["IdealgasCpEquation"] == "100"
        assert got["VaporizationEnthalpyEquation"] == "100"
        assert got["LiquidHeatCapacityEquation"] != "0"  # T06 quirk 4
        assert got["OriginalDB"] == "User"
        assert got["CAS_Number"] == f"s10-{c['id'].lower()}"


def test_a45_wilson_mapping(qual: dict[str, Any], rec: dict[str, Any], gen: ModuleType) -> None:
    lam = _lam(rec)
    worst_lam = 0.0
    for sid, st in qual["states"].items():
        t, rb = st["state"]["T"], st["readback"]
        v, a, bips = (
            rb["molar_volumes_m3_per_kmol"],
            st["applied_bips_cal_per_mol"],
            rb["bips_cal_per_mol"],
        )
        assert rb["cas_ids"] == [f"s10-{c.lower()}" for c in IDS]
        for i in range(3):
            assert a[i][i] == 0.0 and bips[i][i] == 0.0
            for j in range(3):
                if i == j:
                    continue
                assert a[i][j] == -R_CAL * t * math.log(lam[i][j] * v[i] / v[j]), (sid, i, j)
                assert bips[i][j] == a[i][j], (sid, i, j)  # GetBIPs returns what was applied
                eff = v[j] / v[i] * math.exp(-bips[i][j] / (R_CAL * t))
                worst_lam = max(worst_lam, abs(eff - lam[i][j]) / lam[i][j])
    assert worst_lam <= 1e-14, worst_lam


def test_a45_gamma_readback_gate(qual: dict[str, Any], model: Any, gen: ModuleType) -> None:
    """Spec 8.2: gamma at the state's (T, x) to 1e-9 relative, before the flash."""
    transposed = gen.Model(gen.load_records(S10 / "records.yaml"), gen.Mut(lam_transposed=True))
    worst, shift, n = 0.0, 0.0, 0
    for st in qual["states"].values():
        z = [v / sum(st["state"]["n"]) for v in st["state"]["n"]]
        pts = st["readback"]["points"]
        assert [p["x"] for p in pts] == [z, *RB_X]
        for pt in pts:
            x = [mpf(v) for v in pt["x"]]
            lg, lg_t = model.lngamma(x), transposed.lngamma(x)
            for i in range(3):
                g = mp.exp(lg[i])
                worst = max(worst, float(abs(mpf(pt["gamma"][i]) - g) / g))
                shift = max(shift, float(abs(lg[i] - lg_t[i])))
                n += 1
    assert n == 14 * 3 * 3
    assert worst <= 1e-9, worst
    assert shift > 1e-3  # a transposed Lambda would fail the gate by > 1e6x


def test_a45_pure_component_readbacks(qual: dict[str, Any], model: Any) -> None:
    """P_sat, Delta h_vap (whose J/kmol unit this fixes) and c_p^ig to 1e-12 relative; DWSIM's
    h^ig is its own midpoint-rule integral of c_p (PropertyPackage.vb AUX_INT_CPDTi: 10 steps
    below 100 K), reproduced here to 1e-9 J/mol, which accounts for its difference from (3.2)."""
    mw = {
        c["id"]: c["molecular_weight_kg_per_mol"] * 1000.0
        for c in qual["inputs_echo"]["components"]
    }
    worst, worst_mid, worst_exact = 0.0, 0.0, 0.0
    for st in qual["states"].values():
        t = mpf(st["state"]["T"])
        for i, c in enumerate(IDS):
            pc = st["readback"]["pure"][c]
            for got, want in (
                (pc["AUX_PVAPi_Pa"], mp.exp(model.lnpsat(i, t))),
                (pc["AUX_HVAPi_kJ_per_kg"] * mw[c], model.dhvap(i, t)),
                (pc["AUX_CPi_kJ_per_kg_K"] * mw[c], model.cp_ig(i, t)),
            ):
                worst = max(worst, float(abs(mpf(got) - want) / abs(want)))
            t0 = mpf("298.15")
            assert abs(t - t0) < 100  # DWSIM's step rule: 10 midpoints
            h = (t - t0) / 10
            mid = sum(model.cp_ig(i, t0 + h / 2 + k * h) for k in range(10)) * h
            got_int = mpf(pc["AUX_INT_CPDTi_298_15_kJ_per_kg"]) * mw[c]
            worst_mid = max(worst_mid, float(abs(got_int - mid)))
            exact = model.h_ig(i, t) - model.dhf[i]
            worst_exact = max(worst_exact, float(abs(got_int - exact)))
    assert worst <= 1e-12, worst
    assert worst_mid <= 1e-9, worst_mid
    # The quadrature error itself is a tool floor, recorded (0.026 J/mol), not hidden.
    assert 1e-3 < worst_exact < 0.05, worst_exact


# ---------------------------------------------------------------------------- the ladder


def test_a45_ladder_is_the_registered_one(qual: dict[str, Any]) -> None:
    lad = qual["ladder_settings"]
    assert lad["tolerances"] == [1e-10, 1e-8]  # spec 8.2
    assert lad["settings_per_rung"] == [
        "PTFlash_External_Loop_Tolerance",
        "PTFlash_Internal_Loop_Tolerance",
    ]
    tried = [(a["state"], a["tolerance"]) for a in qual["attempts"]]
    assert sorted(tried) == sorted((s, t) for s in qual["states"] for t in lad["tolerances"])
    for a in qual["attempts"]:
        fs = a["flash_settings_readback"]
        for key in lad["settings_per_rung"]:
            assert float(fs[key]) == a["tolerance"]
        for k, v in qual["settings"]["flash"]["flash_settings_fixed"].items():
            assert fs[k] == v
        assert a["converged"] == (
            a["exception"] is None and not a["solver_errors"] and a["stream_calculated"]
        )


def test_a45_comparison_recomputes(qual: dict[str, Any], real: dict[str, Any]) -> None:
    script = _module("s10_dwsim_comparison", REPO_ROOT / "scripts" / "s10_dwsim_comparison.py")
    assert (DWSIM / "inputs.json").read_text(encoding="utf-8") == script.dumps(script.inputs())
    assert (DWSIM / "comparison.json").read_text(encoding="utf-8") == script.dumps(
        script.comparison()
    )
    doc = json.loads((DWSIM / "comparison.json").read_text(encoding="utf-8"))
    conv = {
        s: [a["tolerance"] for a in qual["attempts"] if a["state"] == s and a["converged"]]
        for s in qual["states"]
    }
    selected = next((t for t in (1e-10, 1e-8) if all(t in v for v in conv.values())), None)
    assert doc["ladder"]["selected_tolerance"] == selected
    gate = doc["readbacks"]["gamma_gate"]["all_within"]
    for sid, entry in doc["comparison"]["states"].items():
        if not gate or not conv[sid]:
            assert entry["status"] == "NOT_COMPARABLE" and "rows" not in entry
        elif selected is None:
            assert entry["status"] == "NO_SELECTED_RUNG" and "rows" not in entry
        else:
            assert entry["status"] == "compared"
            if real["closed_form"]["i_states"][sid]["phase"] == "TWO_PHASE":
                assert len(entry["rows"]) >= 9


def test_a45_single_phase_states_raw(qual: dict[str, Any]) -> None:
    """I6 and I7: the phase comparison.json records is the one the raw stream fractions give.
    Whether it matches ours is the verdict's reading, not a test's."""
    doc = json.loads((DWSIM / "comparison.json").read_text(encoding="utf-8"))
    for sid in ("I6", "I7"):
        a = next(a for a in qual["attempts"] if a["state"] == sid and a["tolerance"] == 1e-10)
        q = a["quantities"]
        vf = q["vapor_molarfraction"]
        beta = vf if vf is not None else 1.0 - q["liquid_molarfraction"]
        assert beta in (0.0, 1.0), (sid, beta)
        assert doc["comparison"]["states"][sid]["beta_dwsim"] == beta
