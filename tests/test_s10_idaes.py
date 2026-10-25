"""S10 IDAES reference comparison (spec §8.1, §15 A2-3; assertions S10.A40-A42).

The gate never runs a tool: these tests read the committed tool record
`benchmarks/s10/idaes/qualification.json` (written by `spikes/references/s10_qualify_idaes.py` in
the IDAES environment) and recompute from its raw fields, independently of the summaries in
`comparison.json`:

* A40: every readback against the generator's closed forms (`s10_reference.Model` on
  `records.yaml`, 50 digits) to 1e-10 relative; the applied tau against -ln Lambda_ij read from
  `records.yaml`, and the untransposed tau's discrimination at the RB points;
* A41: the ladder's registered settings, the completeness of the attempt record, the selection
  rule recomputed from Ipopt's own exit messages, and `comparison.json` recomputing byte for
  byte. The verdict per state is the `verdict` agent's, not a test's;
* A42: the predicted smoothing error at every rung of the ladder, and the smoothing shift each
  optimal two-phase attempt measured, within tau/10.
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
IDAES = S10 / "idaes"
IDS = ("CH3OH", "C2H5OH", "H2O")
OPTIMAL = "Optimal Solution Found."


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
    doc: dict[str, Any] = json.loads((IDAES / "qualification.json").read_text(encoding="utf-8"))
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


def _converged(attempt: dict[str, Any]) -> bool:
    return attempt.get("ipopt", {}).get("exit") == OPTIMAL


# ---------------------------------------------------------------------------- S10.A40


def test_a40_environment_and_structure(qual: dict[str, Any]) -> None:
    assert qual["environment_fingerprint"]["matches"]
    assert qual["versions"]["idaes_pse"] == "2.13.0"
    insp = qual["inspection"]
    assert insp["degrees_of_freedom"] == 0
    # The Wagner sites are replaced: no active constraint references the package's parameters.
    assert insp["wagner_parameter_references_in_active_constraints"] == []
    for site in ("eq_P_vap", "_p_sat_bubbleT", "_p_sat_dewT"):
        assert "log(1/(1000.0*K)*" in insp["psat_sites_CH3OH_and_dew_equation"][site]


def test_a40_tau_mapping(qual: dict[str, Any], gen: ModuleType, model: Any) -> None:
    rec = yaml.safe_load((S10 / "records.yaml").read_bytes())
    tau = qual["mapping"]["tau"]
    assert len(tau) == 6
    for e in rec["wilson_lambda"]:  # tau[j, i] = -ln Lambda_ij (spec 8.1)
        assert tau[f"{e['j']},{e['i']}"] == -math.log(float(e["value"]))
    # The untransposed mapping moves ln gamma by far more than the readback tolerance.
    transposed = gen.Model(gen.load_records(S10 / "records.yaml"), gen.Mut(lam_transposed=True))
    shift = max(
        float(abs(u - v))
        for pt in qual["readbacks"]
        for u, v in zip(
            model.lngamma([mpf(x) for x in pt["x"]]),
            transposed.lngamma([mpf(x) for x in pt["x"]]),
            strict=True,
        )
    )
    assert shift > 1e-3


def test_a40_readbacks(qual: dict[str, Any], model: Any) -> None:
    rb = qual["readbacks"]
    assert [(p["T"], p["x"]) for p in rb] == [
        (t, x) for t in (340.0, 360.0) for x in ([0.2, 0.3, 0.5], [0.6, 0.2, 0.2])
    ]
    worst = 0.0
    for pt in rb:
        t, x = mpf(pt["T"]), [mpf(v) for v in pt["x"]]
        psat = [mp.exp(model.lnpsat(i, t)) for i in range(3)]
        gamma = [mp.exp(v) for v in model.lngamma(x)]
        expected = {
            "pressure_sat_comp": psat,
            "p_sat_bubbleT": psat,
            "p_sat_dewT": psat,
            "activity_coeff_comp": gamma,
            "activity_coeff_comp_bubble": gamma,
        }
        for qty, values in expected.items():
            for i, c in enumerate(IDS):
                worst = max(worst, float(abs(mpf(pt[qty][c]) - values[i]) / values[i]))
        h_l = sum(x[i] * model.h0l(i, t) for i in range(3))
        h_v = sum(x[i] * model.h_ig(i, t) for i in range(3))
        for got, want in ((pt["enth_mol_phase"]["Liq"], h_l), (pt["enth_mol_phase"]["Vap"], h_v)):
            worst = max(worst, float(abs(mpf(got) - want) / abs(want)))
    assert worst <= 1e-10, worst


# ---------------------------------------------------------------------------- S10.A41


def test_a41_ladder_is_the_registered_one(qual: dict[str, Any], real: dict[str, Any]) -> None:
    reg = qual["ladder"]["registered"]
    assert reg["eps_K"] == [1e-4, 1e-5, 1e-6]
    assert reg["ipopt_options"] == {"tol": 1e-10, "constr_viol_tol": 1e-10, "max_iter": 3000}
    assert reg["linear_solvers"] == ["ma27", "mumps"]
    states = json.loads((IDAES / "inputs.json").read_text(encoding="utf-8"))["i_states"]["states"]
    assert states == {k: v["state"] for k, v in real["closed_form"]["i_states"].items()}
    for a in qual["ladder"]["attempts"]:
        assert a["final_solve_ipopt_options"] == {
            **reg["ipopt_options"],
            "linear_solver": a["linear_solver"],
        }
        assert a["eps_K"] in reg["eps_K"]
        if "quantities" in a:
            assert a["quantities"]["eps_1"] == a["quantities"]["eps_2"] == a["eps_K"]


def test_a41_every_attempt_recorded_and_selection(
    qual: dict[str, Any], real: dict[str, Any]
) -> None:
    attempts = qual["ladder"]["attempts"]
    optimal: dict[str, list[float]] = {}
    for sid in real["closed_form"]["i_states"]:
        optimal[sid] = []
        for eps in (1e-4, 1e-5, 1e-6):
            mine = [a for a in attempts if a["state"] == sid and a["eps_K"] == eps]
            assert mine[0]["linear_solver"] == "ma27"
            # MUMPS runs exactly when MA27 did not end optimal (spec 8.1).
            assert len(mine) == (1 if _converged(mine[0]) else 2)
            if mine[1:]:
                assert mine[1]["linear_solver"] == "mumps"
            assert all(a["converged"] == _converged(a) for a in mine)
            if any(_converged(a) for a in mine):
                optimal[sid].append(eps)
    assert optimal == qual["ladder"]["optimal_rungs_per_state"]
    common = [e for e in (1e-4, 1e-5, 1e-6) if all(e in v for v in optimal.values())]
    assert qual["ladder"]["selected_rung_eps_K"] == (common[0] if common else None)
    assert sorted(qual["ladder"]["not_comparable"]) == sorted(
        s for s, v in optimal.items() if not v
    )


def test_a41_comparison_recomputes(qual: dict[str, Any]) -> None:
    script = _module("s10_idaes_comparison", REPO_ROOT / "scripts" / "s10_idaes_comparison.py")
    assert (IDAES / "inputs.json").read_text(encoding="utf-8") == script.dumps(script.inputs())
    assert (IDAES / "comparison.json").read_text(encoding="utf-8") == script.dumps(
        script.comparison()
    )
    doc = json.loads((IDAES / "comparison.json").read_text(encoding="utf-8"))
    states = doc["comparison"]["states"]
    assert sorted(states) == sorted(qual["ladder"]["optimal_rungs_per_state"])
    for sid, entry in states.items():
        if sid in qual["ladder"]["not_comparable"]:
            assert entry["status"] == "NOT_COMPARABLE"
        elif qual["ladder"]["selected_rung_eps_K"] is None:
            # No rung is selected (escalated): no difference to our values is computed.
            assert entry["status"] == "NO_SELECTED_RUNG" and "rows" not in entry
        else:
            assert entry["status"] == "compared"


# ---------------------------------------------------------------------------- S10.A42


def test_a42_predicted_smoothing_at_every_rung(real: dict[str, Any]) -> None:
    for sid, entry in real["closed_form"]["i_states"].items():
        if entry["phase"] != "TWO_PHASE":
            continue
        for key in ("0.0001", "1.0e-5", "1.0e-6"):
            assert real["measured"]["smoothing_predicted"][sid][key] <= 1e-8, (sid, key)


def test_a42_measured_smoothing_shift(qual: dict[str, Any], real: dict[str, Any]) -> None:
    seen = 0
    for a in qual["ladder"]["attempts"]:
        entry = real["closed_form"]["i_states"][a["state"]]
        if not _converged(a) or entry["phase"] != "TWO_PHASE":
            continue
        qty = a["quantities"]
        shift = abs(qty["temperature_equilibrium"] - entry["state"]["T"])
        assert shift * entry["max_abs_dq_dT"] <= 1e-8, (a["state"], a["eps_K"])
        seen += 1
    assert seen > 0
