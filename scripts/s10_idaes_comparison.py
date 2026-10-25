"""S10 WO-S10-4 and 4b: the IDAES reference comparison, recomputed from the committed records alone.

Authority: `docs/derivations/S10-spec.md` §8.1 (the mapping, the readbacks S10.A40, the
tolerances S10.A41), as amended by §15 A2-3 (the I-states) and §16 (Amendment 3: the ladder
`amendment_3`, the per-state selection, S10.A42-A44). Two documents, both under
`benchmarks/s10/idaes/`:

* `inputs.json` (`--write-inputs`): the only input of the tool script
  `spikes/references/s10_qualify_idaes.py`, which runs in the IDAES environment (no YAML reader,
  no `openflowsheet`). It carries the record values of `benchmarks/s10/records.yaml` verbatim,
  the I-state definitions (`n`, `T`, `P` only) of `reference_values_real.yaml`, §8.1's readback
  points, both ladders (`registered_8_1` for reproduction, `amendment_3`) and the tolerances
  S10.A43 compares tool attempts at. No expected value of any kind is written to it.
* `comparison.json` (`--write`): from the tool's `qualification.json`, the generator's real
  section and the generator's closed forms (`docs/derivations/scripts/s10_reference.py`, 50
  digits): the tau mapping check, A40's readback table, the reproduction, the selection and A43
  as the tool record holds them, A41's per-state table at each state's selected attempt, A42's
  smoothing tables and A44's envelope-equation patterns. It is mechanical: no tolerance,
  setting, mapping or state is chosen here, and the verdict per state is the `verdict` agent's.

    python scripts/s10_idaes_comparison.py --write-inputs | --write | --check

`--check` recomputes both documents and compares them byte for byte with the committed files.
The gate never runs a tool.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml
from mpmath import mp, mpf  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parents[1]
S10 = ROOT / "benchmarks" / "s10"
OUT = S10 / "idaes"
INPUTS = OUT / "inputs.json"
QUALIFICATION = OUT / "qualification.json"
COMPARISON = OUT / "comparison.json"
RECORDS = S10 / "records.yaml"
REAL = S10 / "reference_values_real.yaml"
GENERATOR = ROOT / "docs" / "derivations" / "scripts" / "s10_reference.py"

#: §8.1, readbacks: T in {340, 360} K x x in {(0.2, 0.3, 0.5), (0.6, 0.2, 0.2)}, order
#: (CH3OH, C2H5OH, H2O). The pressure does not enter P^sat, gamma or h; 101 325 Pa is the I-states'.
RB_T = (340.0, 360.0)
RB_X = ((0.2, 0.3, 0.5), (0.6, 0.2, 0.2))
RB_P = 101325.0
READBACK_RELATIVE = 1e-10  # S10.A40
IDS = ("CH3OH", "C2H5OH", "H2O")
#: The two ladders (spec §16 A3-2, A3-8): `reference_values_real.yaml` `idaes_ladders`, asserted
#: equal by a test. Run R (§8.1's ladder) is rerun for reproduction only; run A3 decides.
LADDER_R = {
    "eps_K": [1e-4, 1e-5, 1e-6],
    "ipopt_options": {"tol": 1e-10, "constr_viol_tol": 1e-10, "max_iter": 3000},
    "linear_solvers": ["ma27", "mumps"],
    "use": "reproduction of the WO-S10-4 record only (spec 16 A3-4); decides nothing",
}
LADDER = {
    "eps_K": [1e-4, 1e-5, 1e-6],
    "ipopt_options": {"tol": 1e-10, "constr_viol_tol": 1e-9, "max_iter": 3000},
    "linear_solvers": ["ma27", "mumps"],
    "mumps": "only when the ma27 attempt at the same state and rung did not end optimal",
    "converged": "Pyomo optimal termination and Ipopt 'EXIT: Optimal Solution Found.'",
    "selection": "per state: the first optimal attempt in the order (eps 1e-4 ma27, mumps; 1e-5 "
    "ma27, mumps; 1e-6 ma27, mumps); none: NOT_COMPARABLE(no_optimal_attempt)",
    "dependence_ratio_max": 0.1,
    "use": "decides (spec 16 A3-2, A3-4)",
}
#: S10.A41.
TOL_ABS_BETA_X_Y = 1e-7
TOL_REL_K = 1e-7
TOL_ABS_H = 0.05  # J/mol
TAU_A42 = 1e-8  # tau/10 with tau = 1e-7 (S10.A42)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dumps(doc: Any) -> str:
    return json.dumps(doc, indent=1, sort_keys=True) + "\n"


def generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("s10_reference", GENERATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["s10_reference"] = module
    spec.loader.exec_module(module)
    return module


# ============================================================================================
# 1. inputs.json: the tool's only input
# ============================================================================================


def inputs() -> dict[str, Any]:
    rec = yaml.safe_load(RECORDS.read_bytes())
    real = yaml.safe_load(REAL.read_bytes())
    comps = []
    for c in rec["components"]:
        p = c["parameters"]
        comps.append(
            {
                "id": c["id"],
                "ideal_gas_cp_b": [float(p[f"ideal_gas_cp_b{k}"]["value"]) for k in range(5)],
                "standard_formation_enthalpy_J_per_mol": float(
                    p["standard_formation_enthalpy"]["value"]
                ),
                "vapour_pressure_abcd": [float(p[f"vapour_pressure_{s}"]["value"]) for s in "abcd"],
            }
        )
    states = {
        sid: {k: entry["state"][k] for k in ("n", "T", "P")}
        for sid, entry in real["closed_form"]["i_states"].items()
    }
    return {
        "authority": "docs/derivations/S10-spec.md section 8.1 as amended by section 15 A2-3 and "
        "section 16",
        "written_by": "scripts/s10_idaes_comparison.py --write-inputs",
        "records": {
            "path": "benchmarks/s10/records.yaml",
            "sha256": sha256(RECORDS),
            "reference_convention": rec["reference_convention"],
            "forms": "c_p^ig/R = sum_k b_k theta^k; ln(P_sat/Pa) = a + b/theta + c ln theta + "
            "d theta^2; theta = T / 1000 K; h^ig(298.15 K) = Delta_fH; Wilson Lambda_ij constant",
            "R_J_per_mol_K": 8.31446261815324,
            "theta_unit_K": 1000.0,
            "T0_K": 298.15,
            "components": comps,
            "wilson_lambda": [
                {"i": e["i"], "j": e["j"], "value": float(e["value"])} for e in rec["wilson_lambda"]
            ],
        },
        "i_states": {
            "path": "benchmarks/s10/reference_values_real.yaml",
            "sha256": sha256(REAL),
            "fields": "closed_form.i_states.<id>.state (n, T, P) only",
            "states": states,
        },
        "readback_points": [
            {"id": f"RB-T{int(t)}-x{k + 1}", "T": t, "P": RB_P, "x": list(x)}
            for t in RB_T
            for k, x in enumerate(RB_X)
        ],
        "ladders": {"registered_8_1": LADDER_R, "amendment_3": LADDER},
        # spec §16 A3-4: what S10.A43 compares, on tool records only (tolerances, not values).
        "a43": {
            "tolerances": {
                "beta_x_y_absolute": TOL_ABS_BETA_X_Y,
                "K_relative": TOL_REL_K,
                "h_absolute_J_per_mol": TOL_ABS_H,
            },
            "compared_by_phase_identity": sorted(
                sid
                for sid, entry in real["closed_form"]["i_states"].items()
                if entry["phase"] != "TWO_PHASE"
            ),
            "ratio_max": LADDER["dependence_ratio_max"],
        },
    }


# ============================================================================================
# 2. comparison.json
# ============================================================================================


def _rel(a: float, b: Any) -> float:
    return float(abs(mpf(a) - b) / abs(b))


def tau_mapping_check(
    q: dict[str, Any], real: dict[str, Any], g: ModuleType, model: Any, model_t: Any
) -> dict[str, Any]:
    """The tool's applied mapping against the generator's independent transcription
    (`idaes_mapping`), and the discrimination of the untransposed tau at the RB points."""
    applied, gen = q["mapping"], real["idaes_mapping"]
    tau_diff = {k: abs(applied["tau"][k] - v) for k, v in gen["tau"].items()}
    coeff_rel: dict[str, float] = {}
    for c, entry in gen["components"].items():
        mine = applied["components"][c]
        pairs = {
            "cp_vap": (
                mine["cp_mol_vap_comp_coeff_A_E_J_per_mol"],
                entry["cp_mol_ig_comp_coeff_A_E"],
            ),
            "cp_liq": (
                mine["cp_mol_liq_comp_coeff_A_E_J_per_mol"],
                entry["cp_mol_liq_comp_coeff_A_E"],
            ),
            "dh_form": (
                [mine["dh_form_Vap_J_per_mol"], mine["dh_form_Liq_J_per_mol"]],
                [entry["dh_form_Vap"], entry["dh_form_Liq"]],
            ),
            "psat": (mine["s10_pressure_sat_abcd"], entry["pressure_sat_a_b_c_d"]),
        }
        for name, (a, b) in pairs.items():
            coeff_rel[f"{c}.{name}"] = max(abs(u - v) / abs(v) for u, v in zip(a, b, strict=True))
    lnk_shift = 0.0
    for pt in q["readbacks"]:
        x = [mpf(v) for v in pt["x"]]
        lg, lg_t = model.lngamma(x), model_t.lngamma(x)
        lnk_shift = max(lnk_shift, max(float(abs(u - v)) for u, v in zip(lg, lg_t, strict=True)))
    return {
        "rule": "tau[j, i] = -ln Lambda_ij (spec 8.1); generator transcription "
        "reference_values_real.yaml idaes_mapping",
        "max_abs_tau_difference": max(tau_diff.values()),
        "tau_difference": tau_diff,
        "max_relative_coefficient_difference": max(coeff_rel.values()),
        "relative_coefficient_difference": coeff_rel,
        "liquid_coefficients_declared_J_per_kmol_factor": [
            v / u
            for c in q["mapping"]["components"].values()
            for u, v in zip(
                c["cp_mol_liq_comp_coeff_A_E_J_per_mol"],
                c["cp_mol_liq_comp_coeff_A_E_as_declared_J_per_kmol"],
                strict=True,
            )
            if u != 0
        ][0],
        "untransposed_tau_max_abs_ln_gamma_shift_at_rb_points": lnk_shift,
    }


def readbacks(q: dict[str, Any], model: Any) -> dict[str, Any]:
    rows = []
    for pt in q["readbacks"]:
        t = mpf(pt["T"])
        x = [mpf(v) for v in pt["x"]]
        lg = model.lngamma(x)
        exp_ = {
            "pressure_sat_comp": [mp.exp(model.lnpsat(i, t)) for i in range(3)],
            "p_sat_bubbleT": [mp.exp(model.lnpsat(i, t)) for i in range(3)],
            "p_sat_dewT": [mp.exp(model.lnpsat(i, t)) for i in range(3)],
            "activity_coeff_comp": [mp.exp(v) for v in lg],
            "activity_coeff_comp_bubble": [mp.exp(v) for v in lg],
        }
        for qty, values in exp_.items():
            for i, c in enumerate(IDS):
                rows.append(
                    {
                        "point": pt["id"],
                        "quantity": qty,
                        "component": c,
                        "idaes": pt[qty][c],
                        "generator": float(values[i]),
                        "relative": _rel(pt[qty][c], values[i]),
                    }
                )
        h = {
            "Liq": sum(x[i] * model.h0l(i, t) for i in range(3)),
            "Vap": sum(x[i] * model.h_ig(i, t) for i in range(3)),
        }
        for p, v in h.items():
            got = pt["enth_mol_phase"][p]
            rows.append(
                {
                    "point": pt["id"],
                    "quantity": f"enth_mol_phase.{p}",
                    "component": None,
                    "idaes": got,
                    "generator": float(v),
                    "relative": _rel(got, v),
                }
            )
    worst = max(rows, key=lambda r: r["relative"])
    return {
        "assertion": "S10.A40",
        "tolerance_relative": READBACK_RELATIVE,
        "expected": "the generator's closed forms (s10_reference.Model on records.yaml, 50 digits) "
        "at the RB points' binary64 inputs",
        "rows": rows,
        "max_relative": worst["relative"],
        "argmax": f"{worst['point']} {worst['quantity']} {worst['component']}",
        "all_within": all(r["relative"] <= READBACK_RELATIVE for r in rows),
    }


def phase_identity(beta: float) -> str:
    if abs(beta) <= TOL_ABS_BETA_X_Y:
        return "LIQUID"
    if abs(beta - 1.0) <= TOL_ABS_BETA_X_Y:
        return "VAPOR"
    return "TWO_PHASE"


def run_attempts(q: dict[str, Any], run: str = "amendment_3") -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = q["ladders"][run]["attempts"]
    return attempts


def selected_attempt(q: dict[str, Any], sid: str) -> dict[str, Any] | None:
    """The state's selected attempt of run A3 (spec §16 A3-2 item 4), or None."""
    sel = q["selection"]["states"][sid]
    if "attempt_index" not in sel:
        return None
    return dict(run_attempts(q)[sel["attempt_index"]])


def summary(a: dict[str, Any]) -> dict[str, Any]:
    return {
        k: a.get(k)
        for k in (
            "eps_K",
            "linear_solver",
            "initializer",
            "ipopt",
            "termination_condition",
            "constraint_residuals",
        )
    }


def state_rows(qty: dict[str, Any], cf: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        {
            "quantity": "beta",
            "idaes": qty["beta"],
            "ours": cf["beta"],
            "basis": "absolute",
            "tolerance": TOL_ABS_BETA_X_Y,
        }
    ]
    for i, c in enumerate(IDS):
        for name in ("x", "y"):
            rows.append(
                {
                    "quantity": f"{name}_{c}",
                    "idaes": qty[name][c],
                    "ours": cf[name][i],
                    "basis": "absolute",
                    "tolerance": TOL_ABS_BETA_X_Y,
                }
            )
    for i, c in enumerate(IDS):
        if cf["K"][i] is not None:
            rows.append(
                {
                    "quantity": f"K_{c}",
                    "idaes": qty["K"][c],
                    "ours": cf["K"][i],
                    "basis": "relative",
                    "tolerance": TOL_REL_K,
                }
            )
    for name, key in (("h_L", "h_L"), ("h_V", "h_V")):
        rows.append(
            {
                "quantity": name,
                "idaes": qty[key],
                "ours": cf[key],
                "basis": "absolute",
                "tolerance": TOL_ABS_H,
            }
        )
    for r in rows:
        d = abs(r["idaes"] - r["ours"])
        r["delta"] = d / abs(r["ours"]) if r["basis"] == "relative" else d
        r["ratio"] = r["delta"] / r["tolerance"]
        r["within"] = r["delta"] <= r["tolerance"]
    return rows


RUNG_KEY = {1e-4: "0.0001", 1e-5: "1.0e-5", 1e-6: "1.0e-6"}  # the real section's keys


def a41(q: dict[str, Any], real: dict[str, Any]) -> dict[str, Any]:
    states: dict[str, Any] = {}
    for sid, entry in real["closed_form"]["i_states"].items():
        sel = q["selection"]["states"][sid]
        if sel["status"] != "selected":
            # no_optimal_attempt, or a failed A43 check (spec §16 A3-2 items 5-6)
            states[sid] = {
                "status": "NOT_COMPARABLE",
                "reason": sel["reason"],
                "ladder_record": [summary(t) for t in run_attempts(q) if t["state"] == sid],
            }
            continue
        a = selected_attempt(q, sid)
        assert a is not None
        qty = a["quantities"]
        rec: dict[str, Any] = {
            "status": "compared",
            "attempt": summary(a),
            "temperature": entry["state"]["T"],
        }
        if entry["phase"] == "TWO_PHASE":
            rows = state_rows(qty, entry["closed_form"])
            worst = max(rows, key=lambda r: r["ratio"])
            rec.update(
                {
                    "rows": rows,
                    "max_ratio": worst["ratio"],
                    "argmax": worst["quantity"],
                    "all_within": all(r["within"] for r in rows),
                }
            )
        else:
            got = phase_identity(qty["beta"])
            rec.update(
                {
                    "phase_ours": entry["phase"],
                    "phase_idaes": got,
                    "beta_idaes": qty["beta"],
                    "phase_rule": "LIQUID if |beta| <= 1e-7, VAPOR if |beta - 1| <= 1e-7, "
                    "else TWO_PHASE (B-36, ratified by spec 16 A3-5)",
                    "all_within": got == entry["phase"],
                }
            )
        states[sid] = rec
    return {
        "assertion": "S10.A41",
        "selection": "per state, the selected attempt of run amendment_3 (qualification.json "
        "selection; spec 16 A3-2)",
        "tolerances": {
            "beta_x_y_absolute": TOL_ABS_BETA_X_Y,
            "K_relative": TOL_REL_K,
            "h_absolute_J_per_mol": TOL_ABS_H,
            "I6_I7": "the phase identity, exact",
        },
        "expected": "reference_values_real.yaml closed_form.i_states (two-phase) and phase "
        "(I6, I7)",
        "states": states,
        "verdict": "the verdict agent's, per state (spec 8.1); nothing here classifies",
    }


def a42(q: dict[str, Any], real: dict[str, Any]) -> dict[str, Any]:
    """Spec §16 A3-7: (a) the generator's prediction (with IDAES's dew d_d^I) at each state's
    selected rung and at every rung; (b) at each selected two-phase attempt, the tool's own
    smoothing shift |T_eq - T| times each sensitivity, against 0.1 of the tolerance."""
    meas = real["measured"]
    kh = meas["smoothing_predicted_K_h_at_1e-4"]
    predicted: dict[str, Any] = {}
    at_selected: dict[str, Any] = {}
    shift: dict[str, Any] = {}
    for sid, entry in real["closed_form"]["i_states"].items():
        if entry["phase"] != "TWO_PHASE":
            continue
        # The prediction is (eps^2/(4 d_b) + eps^2/(4 d_d^I)) |dq/dT|: K and h scale from 1e-4 by
        # (eps / 1e-4)^2, as beta, x and y do in measured.smoothing_predicted (B-45).
        predicted[sid] = {
            RUNG_KEY[e]: {
                "beta_x_y": meas["smoothing_predicted"][sid][RUNG_KEY[e]],
                "K_relative_over_tau_K": kh[sid]["K_relative_over_tau_K"] * (e / 1e-4) ** 2,
                "h_over_tau_h": kh[sid]["h_over_tau_h"] * (e / 1e-4) ** 2,
            }
            for e in LADDER["eps_K"]
        }
        a = selected_attempt(q, sid)
        if a is None:
            continue
        eps, t, qty = a["eps_K"], entry["state"]["T"], a["quantities"]
        p = predicted[sid][RUNG_KEY[eps]]
        at_selected[sid] = {
            "eps_K": eps,
            **p,
            "within": p["beta_x_y"] <= TAU_A42
            and p["K_relative_over_tau_K"] <= 0.1
            and p["h_over_tau_h"] <= 0.1,
        }
        d_t = abs(qty["temperature_equilibrium"] - t)
        rows = {
            "beta_x_y_over_tau": d_t * entry["max_abs_dq_dT"] / TOL_ABS_BETA_X_Y,
            "K_relative_over_tau_K": d_t * entry["max_abs_dlnK_dT"] / TOL_REL_K,
            "h_over_tau_h": d_t * entry["max_abs_dh_dT"] / TOL_ABS_H,
        }
        shift[sid] = {
            "eps_K": eps,
            "linear_solver": a["linear_solver"],
            "T_eq_minus_T_K": qty["temperature_equilibrium"] - t,
            **rows,
            "within": all(v <= 0.1 for v in rows.values()),
            "diagnostic_envelope": {
                "idaes_d_b_K": t - qty["temperature_bubble"],
                "idaes_d_d_K": qty["temperature_dew"] - t,
                "generator_d_d_I_K": entry["idaes_dew_T"] - t,
                "generator_d_d_gamma_at_z_K": entry["dew_T_gamma_at_z"] - t,
            },
        }
    worst = {
        RUNG_KEY[e]: {
            k: max(v[RUNG_KEY[e]][k] for v in predicted.values())
            for k in ("beta_x_y", "K_relative_over_tau_K", "h_over_tau_h")
        }
        for e in LADDER["eps_K"]
    }
    return {
        "assertion": "S10.A42",
        "bound": {"beta_x_y": TAU_A42, "K_relative_over_tau_K": 0.1, "h_over_tau_h": 0.1},
        "rule": "(a) (eps^2/(4 d_b) + eps^2/(4 d_d^I)) |dq/dT| <= tau/10 for beta, x, y and <= 0.1 "
        "of the tolerance for K and h (reference_values_real.yaml measured.smoothing_predicted, "
        "smoothing_predicted_K_h_at_1e-4); (b) |T_eq - T| x max_abs_dq_dT, max_abs_dlnK_dT, "
        "max_abs_dh_dT <= 0.1 of the tolerance at each selected two-phase attempt (spec 16 A3-7)",
        "a_predicted_per_rung": predicted,
        "a_worst_predicted_per_rung": worst,
        "a_at_selected_rung": at_selected,
        "a_all_within_at_selected_rung": all(v["within"] for v in at_selected.values()),
        "b_shift_at_selected_attempt": shift,
        "b_all_within": all(v["within"] for v in shift.values()),
        "b_max_ratio": max(
            max(v[k] for k in ("beta_x_y_over_tau", "K_relative_over_tau_K", "h_over_tau_h"))
            for v in shift.values()
        ),
    }


#: spec §16 A3-4 (S10.A44): exact substrings of the envelope equations' text.
A44_PATTERNS = (
    ("eq_temperature_bubble", "activity_coeff_comp_bubble[", True),
    ("eq_temperature_bubble", "activity_coeff_comp[", False),
    ("eq_temperature_dew", "activity_coeff_comp[", True),
    ("eq_temperature_dew", "activity_coeff_comp_dew[", False),
)


def a44(q: dict[str, Any]) -> dict[str, Any]:
    eqs = q["inspection"]["envelope_equations"]
    checks = [
        {
            "equation": eq,
            "pattern": pat,
            "must_contain": want,
            "contains": pat in eqs[eq],
            "holds": (pat in eqs[eq]) == want,
        }
        for eq, pat, want in A44_PATTERNS
    ]
    return {
        "assertion": "S10.A44",
        "rendering": eqs["rendering"],
        "checks": checks,
        "all_hold": all(c["holds"] for c in checks),
    }


def comparison() -> dict[str, Any]:
    g = generator()
    q = json.loads(QUALIFICATION.read_text(encoding="utf-8"))
    real = yaml.safe_load(REAL.read_bytes())
    rec = g.load_records(RECORDS)
    model, model_t = g.Model(rec), g.Model(rec, g.Mut(lam_transposed=True))
    insp = q["inspection"]
    return {
        "authority": "docs/derivations/S10-spec.md section 8.1 (as amended by section 15 A2-3 "
        "and section 16)",
        "written_by": "scripts/s10_idaes_comparison.py --write",
        "provenance": {
            p.name: sha256(p) for p in (QUALIFICATION, INPUTS, RECORDS, REAL, GENERATOR)
        },
        "environment": {
            "fingerprint_matches": q["environment_fingerprint"]["matches"],
            "versions": q["versions"],
            "package_sha256": q["package_sha256"],
        },
        "inspection": {
            "degrees_of_freedom": insp["degrees_of_freedom"],
            "wagner_parameter_references_in_active_constraints": insp[
                "wagner_parameter_references_in_active_constraints"
            ],
        },
        "tau_mapping_check": tau_mapping_check(q, real, g, model, model_t),
        "readbacks": readbacks(q, model),
        "ladders": {
            name: {
                "registered": run["registered"],
                "optimal_rungs_per_state": run["optimal_rungs_per_state"],
                "attempts": [
                    {"state": a["state"], **summary(a), "converged": a["converged"]}
                    for a in run["attempts"]
                ],
            }
            for name, run in q["ladders"].items()
        },
        "reproduction": q["reproduction"],
        "selection": q["selection"],
        "rung_and_setting_dependence": q["a43"],
        "comparison": a41(q, real),
        "smoothing": a42(q, real),
        "envelope_equations": a44(q),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write-inputs", action="store_true")
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.write_inputs:
        OUT.mkdir(parents=True, exist_ok=True)
        INPUTS.write_text(dumps(inputs()), encoding="utf-8")
        print(f"wrote {INPUTS.relative_to(ROOT)}")
        return 0
    doc = dumps(comparison())
    if args.write:
        COMPARISON.write_text(doc, encoding="utf-8")
        print(f"wrote {COMPARISON.relative_to(ROOT)}")
        return 0
    same_inputs = INPUTS.read_text(encoding="utf-8") == dumps(inputs())
    same = COMPARISON.exists() and COMPARISON.read_text(encoding="utf-8") == doc
    print(
        f"inputs.json {'recomputes identically' if same_inputs else 'differs'}; "
        f"comparison.json {'recomputes identically' if same else 'differs'}"
    )
    return 0 if same and same_inputs else 1


if __name__ == "__main__":
    sys.exit(main())
