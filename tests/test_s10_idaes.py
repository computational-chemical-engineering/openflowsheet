"""S10 IDAES reference comparison (spec §8.1, §15 A2-3, §16; assertions S10.A40-A44).

The gate never runs a tool: these tests read the committed tool record
`benchmarks/s10/idaes/qualification.json` (written by `spikes/references/s10_qualify_idaes.py` in
the IDAES environment) and recompute from its raw fields, independently of the summaries in
`comparison.json`:

* A40: every readback against the generator's closed forms (`s10_reference.Model` on
  `records.yaml`, 50 digits) to 1e-10 relative; the applied tau against -ln Lambda_ij read from
  `records.yaml`, and the untransposed tau's discrimination at the RB points;
* A41: both ladders equal to `reference_values_real.yaml` `idaes_ladders`, the completeness and
  order of every attempt, run R's reproduction of the WO-S10-4 record, the per-state selection
  recomputed from Ipopt's own exit messages (spec §16 A3-2), the statuses and the differences
  recomputed, and `comparison.json` recomputing byte for byte. The verdict per state is the
  `verdict` agent's, not a test's;
* A42: (a) the predicted smoothing error at every rung and at each selected rung; (b) the
  smoothing shift each selected two-phase attempt measured, within 0.1 of each tolerance;
* A43: rung and setting dependence recomputed from the tool's attempts (spec §16 A3-4);
* A44: the four patterns on IDAES's envelope equations as built.
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

LADDER_ORDER = (1e-4, 1e-5, 1e-6)
RUNS = ("registered_8_1", "amendment_3")
#: SHA-256 of `benchmarks/s10/idaes/qualification.json` at e63f98c2 (the WO-S10-4 record).
WO_S10_4_RECORD_SHA256 = "a77c10fe48e52716c2126886bce59ec558e42f31380207d7b3ccd60824af7bd7"
TOL = {"bxy": 1e-7, "K": 1e-7, "h": 0.05}


@pytest.fixture(scope="module")
def script() -> ModuleType:
    return _module("s10_idaes_comparison", REPO_ROOT / "scripts" / "s10_idaes_comparison.py")


def _attempts(qual: dict[str, Any], run: str = "amendment_3") -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = qual["ladders"][run]["attempts"]
    return attempts


def test_a41_ladders_are_the_registered_ones(
    qual: dict[str, Any], real: dict[str, Any], script: ModuleType
) -> None:
    # LADDER is reference_values_real.yaml idaes_ladders.amendment_3 (spec §16 A3-8 item 1).
    assert script.LADDER == real["idaes_ladders"]["amendment_3"]
    assert script.LADDER_R == real["idaes_ladders"]["registered_8_1"]
    assert script.LADDER["ipopt_options"] == {
        "tol": 1e-10,
        "constr_viol_tol": 1e-9,
        "max_iter": 3000,
    }
    inputs = json.loads((IDAES / "inputs.json").read_text(encoding="utf-8"))
    assert inputs["ladders"] == {
        "registered_8_1": script.LADDER_R,
        "amendment_3": script.LADDER,
    }
    assert inputs["i_states"]["states"] == {
        k: v["state"] for k, v in real["closed_form"]["i_states"].items()
    }
    for run in RUNS:
        reg = qual["ladders"][run]["registered"]
        assert reg == inputs["ladders"][run]
        assert reg["eps_K"] == list(LADDER_ORDER)
        assert reg["linear_solvers"] == ["ma27", "mumps"]
        for a in _attempts(qual, run):
            assert a["final_solve_ipopt_options"] == {
                **reg["ipopt_options"],
                "linear_solver": a["linear_solver"],
            }
            assert "error" not in a  # the WO-S10-4 harness defects are gone (spec §16 A3-8)
            if "quantities" in a:
                assert a["quantities"]["eps_1"] == a["quantities"]["eps_2"] == a["eps_K"]
                assert "raw_variables" in a


def test_a41_reproduction_of_the_wo_s10_4_record(qual: dict[str, Any]) -> None:
    rep = qual["reproduction"]
    assert rep["source_sha256"] == WO_S10_4_RECORD_SHA256
    assert rep["identical"] is True and rep["differences"] == []
    assert rep["attempts_source"] == rep["attempts_run_r"] == rep["attempts_compared"] == 67
    assert len(_attempts(qual, "registered_8_1")) == 67
    assert rep["attempts_with_quantities_compared"] == 53
    assert rep["fields"] == [
        "initializer",
        "stage_reached",
        "solver_status",
        "termination_condition",
        "converged",
        "ipopt.iterations",
        "ipopt.exit",
        "ipopt.final_constraint_violation_unscaled",
        "ipopt.final_overall_nlp_error_scaled",
    ]


def _first_converged(qual: dict[str, Any], sid: str) -> int | None:
    for i, a in enumerate(_attempts(qual)):
        if a["state"] == sid and _converged(a):
            return i
    return None


def test_a41_every_attempt_recorded_and_selection(
    qual: dict[str, Any], real: dict[str, Any]
) -> None:
    sids = list(real["closed_form"]["i_states"])
    # within a rung the tool takes the states in inputs.json's (sorted-key) order; the order
    # does not matter to a per-state selection, but every state is attempted at every rung
    order = list(
        json.loads((IDAES / "inputs.json").read_text(encoding="utf-8"))["i_states"]["states"]
    )
    assert sorted(order) == sorted(sids)
    for run in RUNS:
        attempts = _attempts(qual, run)
        # rung-major order, every state at every rung (spec §16 A3-2 item 1)
        keys = [(a["eps_K"], a["state"]) for a in attempts]
        assert keys == sorted(keys, key=lambda k: (LADDER_ORDER.index(k[0]), order.index(k[1])))
        optimal: dict[str, list[float]] = {sid: [] for sid in sids}
        for sid in sids:
            for eps in LADDER_ORDER:
                mine = [a for a in attempts if a["state"] == sid and a["eps_K"] == eps]
                assert mine[0]["linear_solver"] == "ma27"
                # MUMPS runs exactly when MA27 did not end optimal.
                assert len(mine) == (1 if _converged(mine[0]) else 2)
                if mine[1:]:
                    assert mine[1]["linear_solver"] == "mumps"
                for a in mine:
                    assert a["converged"] == (
                        _converged(a) and a["termination_condition"] == "optimal"
                    )
                if any(_converged(a) for a in mine):
                    optimal[sid].append(eps)
        assert optimal == qual["ladders"][run]["optimal_rungs_per_state"]
    sel = qual["selection"]["states"]
    assert sorted(sel) == sorted(sids)
    for sid in sids:
        i = _first_converged(qual, sid)
        if i is None:
            assert sel[sid] == {"status": "NOT_COMPARABLE", "reason": "no_optimal_attempt"}
        else:
            a = _attempts(qual)[i]
            assert sel[sid]["attempt_index"] == i
            assert (sel[sid]["eps_K"], sel[sid]["linear_solver"]) == (
                a["eps_K"],
                a["linear_solver"],
            )
            assert sel[sid]["status"] in ("selected", "NOT_COMPARABLE")
            if sel[sid]["status"] == "NOT_COMPARABLE":
                assert sel[sid]["reason"].startswith("reference_accuracy: ")


def _rows(qty: dict[str, Any], cf: dict[str, Any]) -> list[float]:
    """|delta| / tolerance for every S10.A41 quantity of a two-phase state."""
    out = [abs(qty["beta"] - cf["beta"]) / TOL["bxy"]]
    for i, c in enumerate(IDS):
        out += [abs(qty[n][c] - cf[n][i]) / TOL["bxy"] for n in ("x", "y")]
        if cf["K"][i] is not None:
            out.append(abs(qty["K"][c] - cf["K"][i]) / abs(cf["K"][i]) / TOL["K"])
    out += [abs(qty[n] - cf[n]) / TOL["h"] for n in ("h_L", "h_V")]
    return out


def _phase(beta: float) -> str:
    return "LIQUID" if abs(beta) <= 1e-7 else "VAPOR" if abs(beta - 1) <= 1e-7 else "TWO_PHASE"


def test_a41_comparison_statuses_and_recomputes(
    qual: dict[str, Any], real: dict[str, Any], script: ModuleType
) -> None:
    assert (IDAES / "inputs.json").read_text(encoding="utf-8") == script.dumps(script.inputs())
    text = (IDAES / "comparison.json").read_text(encoding="utf-8")
    assert text == script.dumps(script.comparison())
    assert "NO_SELECTED_RUNG" not in text  # retired by spec §16 A3-5
    states = json.loads(text)["comparison"]["states"]
    sel = qual["selection"]["states"]
    assert sorted(states) == sorted(real["closed_form"]["i_states"])
    for sid, entry in real["closed_form"]["i_states"].items():
        got = states[sid]
        if sel[sid]["status"] != "selected":
            assert got["status"] == "NOT_COMPARABLE" and "rows" not in got
            assert got["reason"] == sel[sid]["reason"]
            continue
        assert got["status"] == "compared"
        a = _attempts(qual)[sel[sid]["attempt_index"]]
        assert (got["attempt"]["eps_K"], got["attempt"]["linear_solver"]) == (
            a["eps_K"],
            a["linear_solver"],
        )
        if entry["phase"] == "TWO_PHASE":
            ratios = _rows(a["quantities"], entry["closed_form"])
            assert len(got["rows"]) == len(ratios)
            assert got["max_ratio"] == max(ratios)
        else:
            assert got["phase_idaes"] == _phase(a["quantities"]["beta"])
            assert got["phase_ours"] == entry["phase"]


# ---------------------------------------------------------------------------- S10.A42


def test_a42_a_predicted_smoothing_at_every_rung(
    qual: dict[str, Any], real: dict[str, Any]
) -> None:
    meas = real["measured"]
    for sid, entry in real["closed_form"]["i_states"].items():
        if entry["phase"] != "TWO_PHASE":
            continue
        kh = meas["smoothing_predicted_K_h_at_1e-4"][sid]
        # the prediction scales as eps^2: 1e-4 is the coarsest rung, so the worst
        assert kh["K_relative_over_tau_K"] <= 0.1 and kh["h_over_tau_h"] <= 0.1, sid
        for key in ("0.0001", "1.0e-5", "1.0e-6"):
            assert meas["smoothing_predicted"][sid][key] <= 1e-8, (sid, key)
    doc = json.loads((IDAES / "comparison.json").read_text(encoding="utf-8"))["smoothing"]
    assert doc["a_all_within_at_selected_rung"] is True
    selected = {
        sid
        for sid, v in qual["selection"]["states"].items()
        if "attempt_index" in v and real["closed_form"]["i_states"][sid]["phase"] == "TWO_PHASE"
    }
    assert set(doc["a_at_selected_rung"]) == selected


def test_a42_b_measured_smoothing_shift(qual: dict[str, Any], real: dict[str, Any]) -> None:
    seen = 0
    for sid, sel in qual["selection"]["states"].items():
        entry = real["closed_form"]["i_states"][sid]
        if "attempt_index" not in sel or entry["phase"] != "TWO_PHASE":
            continue
        qty = _attempts(qual)[sel["attempt_index"]]["quantities"]
        shift = abs(qty["temperature_equilibrium"] - entry["state"]["T"])
        assert shift * entry["max_abs_dq_dT"] <= 0.1 * TOL["bxy"], sid
        assert shift * entry["max_abs_dlnK_dT"] <= 0.1 * TOL["K"], sid
        assert shift * entry["max_abs_dh_dT"] <= 0.1 * TOL["h"], sid
        seen += 1
    assert seen == 11  # every selected two-phase state (I3 has no optimal attempt)


# ---------------------------------------------------------------------------- S10.A43


def _dependence(a: dict[str, Any], ref: dict[str, Any], single_phase: bool) -> float | None:
    """Largest |delta| / tolerance of `a` against `ref` on the A41 quantities; None at I6/I7,
    where the phase identity alone is compared (and must be equal)."""
    qa, qr = a["quantities"], ref["quantities"]
    if single_phase:
        assert _phase(qa["beta"]) == _phase(qr["beta"]), (a["state"], a["eps_K"])
        return None
    out = [abs(qa["beta"] - qr["beta"]) / TOL["bxy"]]
    for c in IDS:
        out += [abs(qa[n][c] - qr[n][c]) / TOL["bxy"] for n in ("x", "y")]
        if a["z"][c] != 0:  # A41 compares no K of a component absent from the feed
            out.append(abs(qa["K"][c] - qr["K"][c]) / abs(qr["K"][c]) / TOL["K"])
    out += [abs(qa[n] - qr[n]) / TOL["h"] for n in ("h_L", "h_V")]
    return max(out)


def test_a43_rung_and_setting_dependence(qual: dict[str, Any], real: dict[str, Any]) -> None:
    rec = qual["a43"]
    assert rec["spec"]["ratio_max"] == 0.1
    assert rec["spec"]["compared_by_phase_identity"] == ["I6", "I7"]
    run_r = {
        (a["state"], a["eps_K"], a["linear_solver"]): a
        for a in _attempts(qual, "registered_8_1")
        if _converged(a)
    }
    worst = 0.0
    n_rung = n_setting = 0
    for sid, sel in qual["selection"]["states"].items():
        if "attempt_index" not in sel:
            assert sid not in rec["rung_dependence"]
            continue
        single = real["closed_form"]["i_states"][sid]["phase"] != "TWO_PHASE"
        ref = _attempts(qual)[sel["attempt_index"]]
        conv = [a for a in _attempts(qual) if a["state"] == sid and _converged(a)]
        assert conv[0] is ref or conv[0] == ref
        others = rec["rung_dependence"][sid]["others"]
        assert len(others) == len(conv) - 1
        for o, a in zip(others, conv[1:], strict=True):
            r = _dependence(a, ref, single)
            assert o["max_ratio"] == r
            if r is not None:
                assert r <= 0.1, (sid, a["eps_K"])
                worst = max(worst, r)
            n_rung += 1
        pairs = [a for a in conv if (a["state"], a["eps_K"], a["linear_solver"]) in run_r]
        assert len(rec["setting_dependence"][sid]) == len(pairs)
        for o, a in zip(rec["setting_dependence"][sid], pairs, strict=True):
            r = _dependence(run_r[(a["state"], a["eps_K"], a["linear_solver"])], a, single)
            assert o["max_ratio"] == r
            assert r is None or r <= 0.1, (sid, a["eps_K"])
            n_setting += 1
        assert sel["status"] == "selected"  # no state fails A43 in this record
    assert n_rung > 0 and n_setting == 18  # the 18 attempts optimal under section 8.1
    assert worst <= 0.1


# ---------------------------------------------------------------------------- S10.A44


def test_a44_envelope_equations_as_read(qual: dict[str, Any]) -> None:
    eqs = qual["inspection"]["envelope_equations"]
    bubble, dew = eqs["eq_temperature_bubble"], eqs["eq_temperature_dew"]
    assert "activity_coeff_comp_bubble[" in bubble
    assert "activity_coeff_comp[" not in bubble
    assert "activity_coeff_comp[" in dew
    assert "activity_coeff_comp_dew[" not in dew
    # the plain rendering of the dew equation is the one WO-S10-4 recorded
    assert (
        eqs["plain_str"]["eq_temperature_dew"]
        == qual["inspection"]["psat_sites_CH3OH_and_dew_equation"]["eq_temperature_dew"]
    )
    doc = json.loads((IDAES / "comparison.json").read_text(encoding="utf-8"))
    assert doc["envelope_equations"]["all_hold"] is True


#: The tool script and the project modules it imports (S10 spec §8, blindness).
HELPERS = ("s10_qualify_idaes.py", "t06_qualify_idaes.py", "t06_fixtures.py")


def test_blindness_inputs_hold_only_the_states_and_the_tool_reads_nothing_else() -> None:
    """Blindness (final review S-3): every I-state the tool is given holds exactly (n, T, P), and
    the tool script and the helpers it imports import nothing of this project and name neither
    the expectation (`reference_values`) nor the comparison record (`comparison.json`)."""
    inputs = json.loads((IDAES / "inputs.json").read_text("utf-8"))
    states = inputs["i_states"]["states"]
    assert len(states) == 14  # I1-I14 (spec §15 A2-3)
    for sid, state in states.items():
        assert set(state) == {"n", "T", "P"}, sid
    spikes = REPO_ROOT / "spikes" / "references"
    for name in HELPERS:
        src = (spikes / name).read_text("utf-8")
        assert "import openflowsheet" not in src and "from openflowsheet" not in src, name
        assert "reference_values" not in src, name
        assert "comparison.json" not in src, name
