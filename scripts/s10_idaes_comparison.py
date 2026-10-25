"""S10 WO-S10-4: the IDAES reference comparison, recomputed from the committed records alone.

Authority: `docs/derivations/S10-spec.md` §8.1 (the mapping, the readbacks S10.A40, the
pre-registered ladder, the tolerances S10.A41, the smoothing claim S10.A42), as amended by §15
A2-3 (the I-states). Two documents, both under `benchmarks/s10/idaes/`:

* `inputs.json` (`--write-inputs`): the only input of the tool script
  `spikes/references/s10_qualify_idaes.py`, which runs in the IDAES environment (no YAML reader,
  no `openflowsheet`). It carries the record values of `benchmarks/s10/records.yaml` verbatim,
  the I-state definitions (`n`, `T`, `P` only) of `reference_values_real.yaml`, §8.1's readback
  points and its ladder. No expected value of any kind is written to it.
* `comparison.json` (`--write`): from the tool's `qualification.json`, the generator's real
  section and the generator's closed forms (`docs/derivations/scripts/s10_reference.py`, 50
  digits): the τ mapping check, A40's readback table, A41's per-state table and A42's smoothing
  table. It is mechanical: no tolerance, setting, mapping or state is chosen here, and the
  verdict per state is the `verdict` agent's (§8.1).

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


def selected_attempt(q: dict[str, Any], sid: str, eps: float | None) -> dict[str, Any] | None:
    for a in q["ladder"]["attempts"]:
        if a["state"] == sid and a["eps_K"] == eps and a["converged"]:
            return dict(a)
    return None


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
    eps = q["ladder"]["selected_rung_eps_K"]
    states: dict[str, Any] = {}
    for sid, entry in real["closed_form"]["i_states"].items():
        tried = [summary(t) for t in q["ladder"]["attempts"] if t["state"] == sid]
        if sid in q["ladder"]["not_comparable"]:
            states[sid] = {
                "status": "NOT_COMPARABLE",
                "reason": "optimal at no rung (spec 8.1)",
                "ladder_record": tried,
            }
            continue
        a = selected_attempt(q, sid, eps) if eps is not None else None
        if a is None:
            # Spec 8.1 selects the first rung at which every I-state ends optimal; when there is
            # none, it does not say which rung the others are compared at (escalated, B-37).
            states[sid] = {
                "status": "NO_SELECTED_RUNG",
                "optimal_rungs": q["ladder"]["optimal_rungs_per_state"][sid],
                "reason": "no rung at which every I-state ends optimal; the rung for "
                "this state is a design-lane ruling (S10_DECISIONS B-37); no "
                "difference to our values is computed before it",
                "ladder_record": tried,
            }
            continue
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
                    "else TWO_PHASE (B-36)",
                    "all_within": got == entry["phase"],
                }
            )
        states[sid] = rec
    return {
        "assertion": "S10.A41",
        "selected_rung_eps_K": eps,
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
    """The claim from the generator's prediction at every rung, and, from the tool's own record
    alone, IDAES's envelope and its smoothing shift at every optimal two-phase attempt."""
    predicted = {}
    tool = {}
    for sid, entry in real["closed_form"]["i_states"].items():
        if entry["phase"] != "TWO_PHASE":
            continue
        predicted[sid] = {
            RUNG_KEY[e]: real["measured"]["smoothing_predicted"][sid][RUNG_KEY[e]]
            for e in LADDER["eps_K"]
        }
        t, dq = entry["state"]["T"], entry["max_abs_dq_dT"]
        for a in q["ladder"]["attempts"]:
            if a["state"] != sid or not a["converged"]:
                continue
            qty, eps = a["quantities"], a["eps_K"]
            db, dd = t - qty["temperature_bubble"], qty["temperature_dew"] - t
            tool[f"{sid}@{RUNG_KEY[eps]}"] = {
                "idaes_d_b_K": db,
                "idaes_d_d_K": dd,
                "generator_d_d_gamma_at_z_K": entry["idaes_dew_T_gamma_at_z"] - t,
                "idaes_T_dew_minus_generator_T_dew_gamma_at_z_K": qty["temperature_dew"]
                - entry["idaes_dew_T_gamma_at_z"],
                "predicted_with_idaes_envelope": (eps**2 / (4 * db) + eps**2 / (4 * dd)) * dq,
                "T_eq_minus_T_K": qty["temperature_equilibrium"] - t,
                "abs_T_eq_minus_T_times_dq_dT": abs(qty["temperature_equilibrium"] - t) * dq,
            }
    eps = q["ladder"]["selected_rung_eps_K"]
    worst = {e: max(v[RUNG_KEY[e]] for v in predicted.values()) for e in LADDER["eps_K"]}
    return {
        "assertion": "S10.A42",
        "bound": TAU_A42,
        "rule": "(eps^2/(4 d_b) + eps^2/(4 d_d)) |dq/dT| <= tau/10 at the chosen rung, with d_b to "
        "the true bubble, d_d to the dew with gamma(z) (B-31) and |dq/dT| = max_abs_dq_dT "
        "(reference_values_real.yaml measured.smoothing_predicted)",
        "selected_rung_eps_K": eps,
        "predicted_generator": predicted,
        "worst_predicted_per_rung": {RUNG_KEY[e]: w for e, w in worst.items()},
        "within_per_rung": {RUNG_KEY[e]: w <= TAU_A42 for e, w in worst.items()},
        "tool_envelope_at_optimal_attempts": tool,
    }


def comparison() -> dict[str, Any]:
    g = generator()
    q = json.loads(QUALIFICATION.read_text(encoding="utf-8"))
    real = yaml.safe_load(REAL.read_bytes())
    rec = g.load_records(RECORDS)
    model, model_t = g.Model(rec), g.Model(rec, g.Mut(lam_transposed=True))
    insp = q["inspection"]
    return {
        "authority": "docs/derivations/S10-spec.md section 8.1 (as amended by section 15 A2-3)",
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
            "dew_equation": insp["psat_sites_CH3OH_and_dew_equation"]["eq_temperature_dew"],
        },
        "tau_mapping_check": tau_mapping_check(q, real, g, model, model_t),
        "readbacks": readbacks(q, model),
        "ladder": {
            "optimal_rungs_per_state": q["ladder"]["optimal_rungs_per_state"],
            "selected_rung_eps_K": q["ladder"]["selected_rung_eps_K"],
            "not_comparable": q["ladder"]["not_comparable"],
            "attempts": [
                {"state": a["state"], **summary(a), "converged": a["converged"]}
                for a in q["ladder"]["attempts"]
            ],
        },
        "comparison": a41(q, real),
        "smoothing": a42(q, real),
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
