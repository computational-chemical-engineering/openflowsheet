"""S10 WO-S10-4: the IDAES 2.13 qualification of `wilson-ig-v1` (spec §8.1, §15 A2-3).

Authority: `docs/derivations/S10-spec.md` §8.1. This script builds IDAES's ideal-gas + Wilson
package (`idaes/models/properties/activity_coeff_models/activity_coeff_prop_pack.py`,
`activity_coeff_model="Wilson"`, `state_vars="FTPz"`, `valid_phase=("Vap", "Liq")`) on the S10
real records with §8.1's mapping:

* `vol_mol_comp[i] = 1` and `tau[j, i] = -ln Lambda_ij` (i != j): IDAES's G_ji plays our Lambda_ij;
* P^sat: the three Wagner sites (the constraint `eq_P_vap` at the equilibrium temperature, the
  Expressions `_p_sat_bubbleT` and `_p_sat_dewT`) replaced by ln(P^sat/Pa) = a + b/theta +
  c ln theta + d theta^2 at the same temperature variable (the T06 precedent of a user
  vapour-pressure method); the package's Wagner parameters are placeholders that the inspection
  shows no active constraint references;
* `temperature_reference` = 298.15 K; vapour c_p A..E = R b_k / 1000^k with `dh_form["Vap", i]`
  = Delta_fH_i; liquid A = R (b_0 - c), B = R b_1/10^3, C = R (b_2 - 6 d)/10^6, D = R b_3/10^9,
  E = R b_4/10^12 with `dh_form["Liq", i]` = h_i^0L(298.15 K) from spec (3.5)-(3.6). The liquid
  coefficients are declared in J/kmol (the package's `pyunits.convert` to J/mol, as in its BTX
  example), so their values are 1000 times the J/mol values; the readbacks fix the factor.

Then, in this order:

1. **Readbacks (S10.A40), before any flash**: at §8.1's four RB points, IDAES's own constraints
   are solved one variable at a time (`calculate_variable_from_constraint`) for `Gij_coeff`, `A`,
   `B`, `activity_coeff_comp`, `pressure_sat_comp`, `enth_mol_phase_comp` and `enth_mol_phase`,
   with both phase compositions and every temperature variable fixed at the point. The bubble and
   dew P^sat Expressions and the bubble/dew activity Expressions are read at the same point.
2. **The ladder** (pre-registered, §8.1): eps_1 = eps_2 in (1e-4, 1e-5, 1e-6) K; for each rung
   and I-state a fresh model, the package's `initialize()` from the registered state, then Ipopt
   (the bundled 3.13.2) with tol = constr_viol_tol = 1e-10 and max_iter = 3000, linear solver
   MA27, then MUMPS if MA27 did not end optimal. Every attempt is recorded. The first rung at
   which every I-state ends "Optimal Solution Found" is the selected rung.

Inputs: `benchmarks/s10/idaes/inputs.json` only (written by `scripts/s10_idaes_comparison.py
--write-inputs`: record values, I-state definitions n, T, P, the RB points, the ladder). No
expected value is read, and nothing of `openflowsheet` is imported. The comparison is
`scripts/s10_idaes_comparison.py`'s. Output: `benchmarks/s10/idaes/qualification.json`; Ipopt
logs go to `--log-dir` (not committed; their SHA-256 is recorded).

    .venv-idaes/bin/python spikes/references/s10_qualify_idaes.py [--out FILE] [--log-dir DIR]

Not part of `scripts/check.sh`: the gate never runs a tool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any

# Single-threaded linear algebra: deterministic, and no oversubscription of a shared host.
for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import t06_fixtures as fx  # noqa: E402  (REPO_ROOT, the environment fingerprint, finite())
import t06_qualify_idaes as t06i  # noqa: E402  (parse_ipopt_log, constraint_residuals)

ENV_DIR = fx.REPO_ROOT / ".venv-idaes"
INPUTS = fx.REPO_ROOT / "benchmarks" / "s10" / "idaes" / "inputs.json"
DEFAULT_OUT = fx.REPO_ROOT / "benchmarks" / "s10" / "idaes" / "qualification.json"
DEFAULT_LOGS = fx.REPO_ROOT / "evidence" / "S10" / "artifacts" / "idaes-logs"
IDS = ("CH3OH", "C2H5OH", "H2O")
#: The package's Wagner parameters, needed only so that its bubble and dew Expressions construct
#: before their P^sat is replaced; `inspect` shows that no active constraint references them.
WAGNER_PLACEHOLDER = {
    "pressure_critical_Pa": 1.0e7,
    "temperature_critical_K": 1000.0,
    "pressure_sat_coeff": 0.0,
}
APPLICATION_NOTES = [
    "Standalone state block (FlowsheetBlock, steady state; build_state_block([0], "
    "defined_state=True, has_phase_equilibrium=True)): the TP flash at the registered (z, T, P) "
    "with flow_mol = 1 mol/s; enth_mol_phase, temperature_bubble, temperature_dew, "
    "pressure_sat_comp and fug_phase_comp are constructed before eps is set and before the "
    "initializer runs.",
    "eps_1 = eps_2 = the rung is set on the state block before the initializer runs, so that the "
    "initializer and the final solve see the same equations (T06 precedent).",
    "The initializer is the package's ActivityCoeffStateBlock.initialize() with no arguments; "
    "its Ipopt comes from idaes.core.solvers.get_solver(), with idaes.cfg.ipopt.options."
    "linear_solver set to the attempt's linear solver and its other options IDAES defaults.",
    "ipopt_log_sha256 is the hash of the log file as written; it names Pyomo's temporary .nl "
    "file and carries timings, so it differs from run to run while every value does not.",
    "Converged = Pyomo optimal termination and Ipopt's 'EXIT: Optimal Solution Found.' (Solved "
    "To Acceptable Level is not counted).",
    "The I-state composition is z = n / sum(n), in the order (CH3OH, C2H5OH, H2O); a zero "
    "component stays in the model with z_i = 0 (the registered state).",
]


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ============================================================================================
# 1. The mapping (spec §8.1), from the record values of inputs.json
# ============================================================================================


def mapping(rec: dict[str, Any]) -> dict[str, Any]:
    r, unit, t0 = rec["R_J_per_mol_K"], rec["theta_unit_K"], rec["T0_K"]
    th0 = t0 / unit
    lam = {(e["i"], e["j"]): e["value"] for e in rec["wilson_lambda"]}
    tau = {f"{j},{i}": -math.log(lam[(i, j)]) for (i, j) in lam}  # tau[j, i] = -ln Lambda_ij
    comps: dict[str, Any] = {}
    for c in rec["components"]:
        b, dhf = c["ideal_gas_cp_b"], c["standard_formation_enthalpy_J_per_mol"]
        _, bb, cc, dd = c["vapour_pressure_abcd"]
        vap = [r * b[k] / unit**k for k in range(5)]
        liq_j_per_mol = [
            r * (b[0] - cc),
            r * b[1] / unit,
            r * (b[2] - 6 * dd) / unit**2,
            r * b[3] / unit**3,
            r * b[4] / unit**4,
        ]
        # spec (3.5)-(3.6) at T0: h^0L(T0) = Delta_fH - R (1000 K) (-b + c theta0 + 2 d theta0^3)
        h0l = dhf - r * unit * (-bb + cc * th0 + 2 * dd * th0**3)
        comps[c["id"]] = {
            "cp_mol_vap_comp_coeff_A_E_J_per_mol": vap,
            "dh_form_Vap_J_per_mol": dhf,
            "cp_mol_liq_comp_coeff_A_E_J_per_mol": liq_j_per_mol,
            "cp_mol_liq_comp_coeff_A_E_as_declared_J_per_kmol": [1000.0 * v for v in liq_j_per_mol],
            "dh_form_Liq_J_per_mol": h0l,
            "s10_pressure_sat_abcd": list(c["vapour_pressure_abcd"]),
        }
    return {
        "vol_mol_comp_m3_per_mol": dict.fromkeys(IDS, 1.0),
        "tau": tau,
        "temperature_reference_K": t0,
        "pressure_reference_Pa": 101325.0,
        "components": comps,
        "liquid_coefficient_units": "J/kmol/K^(k+1), converted by the package to J/mol",
        "wagner_placeholders": WAGNER_PLACEHOLDER,
    }


# ============================================================================================
# 2. The property package: IDAES's activity-coefficient package with the S10 P^sat
# ============================================================================================


def define_package(mp: dict[str, Any]) -> Any:
    from idaes.core import Component, declare_process_block_class
    from idaes.models.properties.activity_coeff_models.activity_coeff_prop_pack import (
        ActivityCoeffParameterData,
        ActivityCoeffStateBlockData,
        _ActivityCoeffStateBlock,
    )
    from pyomo.environ import Constraint, Param, Set, Var, exp, log
    from pyomo.environ import units as pyunits

    comps = mp["components"]

    def s10_psat(b: Any, j: str, temperature: Any) -> Any:
        """ln(P^sat/Pa) = a + b/theta + c ln theta + d theta^2, theta = T / 1000 K (spec (3.3))."""
        th = temperature / (1000.0 * pyunits.K)
        pa, pb, pc, pd = (b.params.s10_psat_coeff[j, k] for k in "abcd")
        return pa + pb / th + pc * log(th) + pd * th**2

    @declare_process_block_class("S10StateBlock", block_class=_ActivityCoeffStateBlock)
    class S10StateBlockData(ActivityCoeffStateBlockData):
        def _pressure_sat_comp(self) -> None:
            # Replaces the Wagner constraint eq_P_vap: same variable, same temperature (T_eq).
            self.pressure_sat_comp = Var(
                self.params.component_list,
                initialize=101325,
                doc="vapor pressure",
                units=pyunits.Pa,
            )

            def rule_p_vap(b: Any, j: str) -> Any:
                return log(b.pressure_sat_comp[j] / pyunits.Pa) == s10_psat(
                    b, j, b._temperature_equilibrium
                )

            self.eq_P_vap = Constraint(self.params.component_list, rule=rule_p_vap)

        def _temperature_bubble(self) -> None:
            super()._temperature_bubble()
            for j in self.params.component_list:  # replaces the Wagner Expression at T_bubble
                self._p_sat_bubbleT[j].set_value(
                    exp(s10_psat(self, j, self.temperature_bubble)) * pyunits.Pa
                )

        def _temperature_dew(self) -> None:
            super()._temperature_dew()
            for j in self.params.component_list:  # replaces the Wagner Expression at T_dew
                self._p_sat_dewT[j].set_value(
                    exp(s10_psat(self, j, self.temperature_dew)) * pyunits.Pa
                )

    @declare_process_block_class("S10WilsonParameterBlock")
    class S10WilsonParameterData(ActivityCoeffParameterData):
        def build(self) -> None:
            self.component_list_master = Set(initialize=list(IDS))
            for c in IDS:
                self.add_component(c, Component())
            super().build()
            self._state_block_class = S10StateBlock  # noqa: F821  (declared above)
            self.pressure_reference = Param(
                mutable=True, default=mp["pressure_reference_Pa"], units=pyunits.Pa
            )
            self.temperature_reference = Param(
                mutable=True, default=mp["temperature_reference_K"], units=pyunits.K
            )
            self.pressure_critical = Param(
                self.component_list,
                mutable=True,
                units=pyunits.Pa,
                initialize=WAGNER_PLACEHOLDER["pressure_critical_Pa"],
            )
            self.temperature_critical = Param(
                self.component_list,
                mutable=True,
                units=pyunits.K,
                initialize=WAGNER_PLACEHOLDER["temperature_critical_K"],
            )
            self.pressure_sat_coeff = Param(
                self.component_list,
                ["A", "B", "C", "D"],
                mutable=True,
                initialize=WAGNER_PLACEHOLDER["pressure_sat_coeff"],
            )
            self.s10_psat_coeff = Param(
                self.component_list,
                ["a", "b", "c", "d"],
                mutable=False,
                initialize={
                    (c, k): comps[c]["s10_pressure_sat_abcd"][n]
                    for c in IDS
                    for n, k in enumerate("abcd")
                },
                doc="S10 ln(P_sat/Pa) = a + b/theta + c ln theta + d theta^2",
            )
            vap_units = [pyunits.J / pyunits.mol / pyunits.K ** (k + 1) for k in range(5)]
            liq_units = [pyunits.J / pyunits.kmol / pyunits.K ** (k + 1) for k in range(5)]
            for k, letter in enumerate("ABCDE"):
                self.add_component(
                    f"cp_mol_vap_comp_coeff_{letter}",
                    Param(
                        self.component_list,
                        units=vap_units[k],
                        initialize={
                            c: comps[c]["cp_mol_vap_comp_coeff_A_E_J_per_mol"][k] for c in IDS
                        },
                    ),
                )
                self.add_component(
                    f"cp_mol_liq_comp_coeff_{letter}",
                    Param(
                        self.component_list,
                        units=liq_units[k],
                        initialize={
                            c: comps[c]["cp_mol_liq_comp_coeff_A_E_as_declared_J_per_kmol"][k]
                            for c in IDS
                        },
                    ),
                )
            self.dh_form = Param(
                self.phase_list,
                self.component_list,
                mutable=True,
                units=pyunits.J / pyunits.mol,
                initialize={
                    **{("Vap", c): comps[c]["dh_form_Vap_J_per_mol"] for c in IDS},
                    **{("Liq", c): comps[c]["dh_form_Liq_J_per_mol"] for c in IDS},
                },
            )

    return S10WilsonParameterBlock  # noqa: F821  (declared by the decorator above)


def build(package: Any, mp: dict[str, Any]) -> tuple[Any, Any]:
    import pyomo.environ as pyo
    from idaes.core import FlowsheetBlock

    m = pyo.ConcreteModel()
    m.fs = FlowsheetBlock(dynamic=False)
    m.fs.props = package(
        activity_coeff_model="Wilson", state_vars="FTPz", valid_phase=("Vap", "Liq")
    )
    for key, value in mp["tau"].items():
        j, i = key.split(",")
        m.fs.props.tau[j, i].fix(value)
    for c in IDS:
        m.fs.props.tau[c, c].fix(0.0)  # unused: G_ii is fixed at 1 by the package
        m.fs.props.vol_mol_comp[c].fix(mp["vol_mol_comp_m3_per_mol"][c])
    m.fs.state = m.fs.props.build_state_block([0], defined_state=True, has_phase_equilibrium=True)
    sb = m.fs.state[0]
    for name in (
        "enth_mol_phase",
        "temperature_bubble",
        "temperature_dew",
        "pressure_sat_comp",
        "fug_phase_comp",
    ):
        getattr(sb, name)  # build on demand, before eps or the initializer
    return m, sb


def inspect(m: Any, sb: Any) -> dict[str, Any]:
    """Structural facts of the built model, before any solve (S03 precedent)."""
    import pyomo.environ as pyo
    from idaes.core.util.model_statistics import degrees_of_freedom
    from pyomo.core.expr.visitor import identify_mutable_parameters

    wagner = {"pressure_critical", "temperature_critical", "pressure_sat_coeff"}
    refs = []
    active = []
    for c in m.component_data_objects(pyo.Constraint, active=True, descend_into=True):
        active.append(c.name)
        for p in identify_mutable_parameters(c.body):
            parent = getattr(p, "parent_component", None)  # units are not Params
            if parent is not None and parent().local_name in wagner:
                refs.append(f"{c.name}: {p.name}")
    psat_sites = {
        "eq_P_vap": str(sb.eq_P_vap["CH3OH"].expr),
        "_p_sat_bubbleT": str(sb._p_sat_bubbleT["CH3OH"].expr),
        "_p_sat_dewT": str(sb._p_sat_dewT["CH3OH"].expr),
        "eq_temperature_dew": str(sb.eq_temperature_dew.expr),
    }
    return {
        "degrees_of_freedom": int(degrees_of_freedom(m)),
        "active_constraints": len(active),
        "active_constraint_names": sorted(active),
        "wagner_parameter_references_in_active_constraints": refs,
        "psat_sites_CH3OH_and_dew_equation": psat_sites,
    }


# ============================================================================================
# 3. Readbacks (S10.A40)
# ============================================================================================


def readback(package: Any, mp: dict[str, Any], point: dict[str, Any]) -> dict[str, Any]:
    import pyomo.environ as pyo
    from pyomo.util.calc_var_value import calculate_variable_from_constraint as calc

    m, sb = build(package, mp)
    t, x = point["T"], dict(zip(IDS, point["x"], strict=True))
    sb.flow_mol.fix(1.0)
    sb.temperature.fix(t)
    sb.pressure.fix(point["P"])
    for c in IDS:
        sb.mole_frac_comp[c].fix(x[c])
        for p in ("Liq", "Vap"):
            sb.mole_frac_phase_comp[p, c].fix(x[c])
    for v in (sb._temperature_equilibrium, sb.temperature_bubble, sb.temperature_dew):
        v.fix(t)
    eps = 1e-15
    for i in IDS:
        for j in IDS:
            if i != j:
                calc(sb.Gij_coeff[i, j], sb.eq_Gij_coeff[i, j], eps=eps)
    for i in IDS:
        calc(sb.A[i], sb.eq_A[i], eps=eps)
        calc(sb.B[i], sb.eq_B[i], eps=eps)
    for i in IDS:
        sb.activity_coeff_comp[i].set_value(1.0)
        calc(sb.activity_coeff_comp[i], sb.eq_activity_coeff[i], eps=eps)
        sb.pressure_sat_comp[i].set_value(1e5)
        calc(sb.pressure_sat_comp[i], sb.eq_P_vap[i], eps=eps)
        for p in ("Liq", "Vap"):
            calc(sb.enth_mol_phase_comp[p, i], sb.eq_enth_mol_phase_comp[p, i], eps=eps)
    for p in ("Liq", "Vap"):
        calc(sb.enth_mol_phase[p], sb.eq_enth_mol_phase[p], eps=eps)
    residual = max(
        abs(pyo.value(c.body) - pyo.value(c.upper))
        for name in (
            "eq_Gij_coeff",
            "eq_A",
            "eq_B",
            "eq_activity_coeff",
            "eq_P_vap",
            "eq_enth_mol_phase_comp",
            "eq_enth_mol_phase",
        )
        for c in sb.component(name).values()
    )
    return {
        **point,
        "method": "calculate_variable_from_constraint on each property constraint, phase "
        "compositions = x, temperature = _temperature_equilibrium = temperature_bubble = "
        "temperature_dew = T (fixed)",
        "pressure_sat_comp": {c: pyo.value(sb.pressure_sat_comp[c]) for c in IDS},
        "p_sat_bubbleT": {c: pyo.value(sb._p_sat_bubbleT[c]) for c in IDS},
        "p_sat_dewT": {c: pyo.value(sb._p_sat_dewT[c]) for c in IDS},
        "activity_coeff_comp": {c: pyo.value(sb.activity_coeff_comp[c]) for c in IDS},
        "activity_coeff_comp_bubble": {c: pyo.value(sb.activity_coeff_comp_bubble[c]) for c in IDS},
        "activity_coeff_comp_dew": {c: pyo.value(sb.activity_coeff_comp_dew[c]) for c in IDS},
        "enth_mol_phase_comp": {
            f"{p},{c}": pyo.value(sb.enth_mol_phase_comp[p, c]) for p in ("Liq", "Vap") for c in IDS
        },
        "enth_mol_phase": {p: pyo.value(sb.enth_mol_phase[p]) for p in ("Liq", "Vap")},
        "max_abs_residual_of_solved_constraints": residual,
    }


# ============================================================================================
# 4. The ladder (spec §8.1)
# ============================================================================================


def quantities(sb: Any) -> dict[str, Any]:
    import pyomo.environ as pyo

    v = pyo.value
    x = {c: v(sb.mole_frac_phase_comp["Liq", c]) for c in IDS}
    y = {c: v(sb.mole_frac_phase_comp["Vap", c]) for c in IDS}
    return {
        "beta": v(sb.flow_mol_phase["Vap"]) / v(sb.flow_mol),
        "flow_mol_phase": {p: v(sb.flow_mol_phase[p]) for p in ("Liq", "Vap")},
        "x": x,
        "y": y,
        "K": {c: (y[c] / x[c] if x[c] != 0 else None) for c in IDS},
        "h_L": v(sb.enth_mol_phase["Liq"]),
        "h_V": v(sb.enth_mol_phase["Vap"]),
        "temperature": v(sb.temperature),
        "temperature_equilibrium": v(sb._temperature_equilibrium),
        "t1": v(sb._t1),
        "temperature_bubble": v(sb.temperature_bubble),
        "temperature_dew": v(sb.temperature_dew),
        "activity_coeff_comp": {c: v(sb.activity_coeff_comp[c]) for c in IDS},
        "pressure_sat_comp": {c: v(sb.pressure_sat_comp[c]) for c in IDS},
        "eps_1": v(sb.eps_1),
        "eps_2": v(sb.eps_2),
    }


def attempt(
    package: Any,
    mp: dict[str, Any],
    sid: str,
    state: dict[str, Any],
    eps: float,
    linear_solver: str,
    ipopt_options: dict[str, Any],
    log_dir: Path,
) -> dict[str, Any]:
    import idaes
    import pyomo.environ as pyo
    from pyomo.opt import SolverStatus

    n = state["n"]
    z = dict(zip(IDS, (v / sum(n) for v in n), strict=True))
    rec: dict[str, Any] = {
        "state": sid,
        "eps_K": eps,
        "linear_solver": linear_solver,
        "z": z,
        "stage_reached": "build",
        "converged": False,
    }
    t0 = time.perf_counter()
    try:
        m, sb = build(package, mp)
        sb.flow_mol.fix(1.0)
        sb.temperature.fix(state["T"])
        sb.pressure.fix(state["P"])
        for c in IDS:
            sb.mole_frac_comp[c].fix(z[c])
        sb.eps_1.set_value(eps)
        sb.eps_2.set_value(eps)
        rec["stage_reached"] = "initialize"
        idaes.cfg.ipopt.options.linear_solver = linear_solver
        rec["initializer_ipopt_options"] = dict(idaes.cfg.ipopt.options)
        t1 = time.perf_counter()
        try:
            m.fs.state.initialize()
            rec["initializer"] = "completed"
        except Exception as exc:  # recorded; the final solve still runs from where it stopped
            rec["initializer"] = f"{type(exc).__name__}: {exc}"
        rec["wall_time_initialize_s"] = time.perf_counter() - t1
        rec["stage_reached"] = "solve"
        solver = pyo.SolverFactory("ipopt")
        options = {**ipopt_options, "linear_solver": linear_solver}
        for k, val in options.items():
            solver.options[k] = val
        rec["final_solve_ipopt_options"] = options
        log = log_dir / f"{sid}-eps{eps:g}-{linear_solver}.ipopt.log"
        t2 = time.perf_counter()
        result = solver.solve(m, tee=False, logfile=str(log), load_solutions=False)
        rec["wall_time_solve_s"] = time.perf_counter() - t2
        text = log.read_text(encoding="utf-8", errors="replace")
        rec["ipopt_log_sha256"] = hashlib.sha256(text.encode()).hexdigest()
        rec["solver_status"] = str(result.solver.status)
        rec["termination_condition"] = str(result.solver.termination_condition)
        rec["ipopt"] = t06i.parse_ipopt_log(text)
        rec["converged"] = bool(pyo.check_optimal_termination(result)) and (
            rec["ipopt"].get("exit") == "Optimal Solution Found."
        )
        rec["stage_reached"] = "solved" if rec["converged"] else "solve_not_converged"
        if not rec["converged"]:
            result.solver.status = SolverStatus.warning
        try:
            m.solutions.load_from(result)
        except ValueError as exc:  # Pyomo refuses an iterate Ipopt reports as an error
            rec["last_iterate"] = f"not loadable: {exc}"
            return rec
        if not rec["converged"]:
            rec["last_iterate"] = "loaded although not converged"
        rec["quantities"] = quantities(sb)
        rec["constraint_residuals"] = t06i.constraint_residuals(m)
        rec["raw_variables"] = t06i.all_variables(m.fs.state)
    except Exception as exc:  # every failure is recorded, none is hidden
        rec["error"] = f"{type(exc).__name__}: {exc}"
        rec["traceback"] = traceback.format_exc(limit=6)
    finally:
        rec["wall_time_total_s"] = time.perf_counter() - t0
    return rec


def run_ladder(
    package: Any, mp: dict[str, Any], states: dict[str, Any], ladder: dict[str, Any], log_dir: Path
) -> dict[str, Any]:
    attempts = []
    optimal: dict[str, list[float]] = {sid: [] for sid in states}
    for eps in ladder["eps_K"]:
        for sid, state in states.items():
            for ls in ladder["linear_solvers"]:
                rec = attempt(package, mp, sid, state, eps, ls, ladder["ipopt_options"], log_dir)
                attempts.append(rec)
                print(
                    f"idaes S10 {sid} eps={eps:g} {ls}: "
                    f"{rec.get('ipopt', {}).get('exit', rec.get('error', '?'))}",
                    file=sys.stderr,
                )
                if rec["converged"]:
                    optimal[sid].append(eps)
                    break  # MUMPS only if MA27 did not end optimal (spec §8.1)
                if "error" in rec and "not available" in rec.get("error", "").lower():
                    break
    selected = next((e for e in ladder["eps_K"] if all(e in optimal[s] for s in states)), None)
    return {
        "attempts": attempts,
        "optimal_rungs_per_state": optimal,
        "selected_rung_eps_K": selected,
        "not_comparable": [s for s in states if not optimal[s]],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOGS)
    args = parser.parse_args()
    args.log_dir.mkdir(parents=True, exist_ok=True)
    inputs = json.loads(INPUTS.read_text(encoding="utf-8"))

    os.environ.setdefault("IDAES_DATA", str(ENV_DIR / "idaes-data"))
    t_import = time.perf_counter()
    import idaes
    import pyomo

    t_import = time.perf_counter() - t_import
    mp = mapping(inputs["records"])
    package = define_package(mp)
    _, sb = build(package, mp)
    sb.flow_mol.fix(1.0)
    sb.temperature.fix(350.0)
    sb.pressure.fix(101325.0)
    for c in IDS:
        sb.mole_frac_comp[c].fix(1.0 / 3.0)
    structure = inspect(sb.model(), sb)
    readbacks = [readback(package, mp, p) for p in inputs["readback_points"]]
    ladder = run_ladder(package, mp, inputs["i_states"]["states"], inputs["ladder"], args.log_dir)
    doc = {
        "tool": "IDAES",
        "authority": "docs/derivations/S10-spec.md section 8.1 (as amended by section 15 A2-3); "
        "S10.A40-A42",
        "script": "spikes/references/s10_qualify_idaes.py",
        "inputs": {"path": "benchmarks/s10/idaes/inputs.json", "sha256": file_sha256(INPUTS)},
        "versions": {
            "idaes_pse": idaes.__version__,
            "pyomo": pyomo.__version__,
            "python": sys.version.split()[0],
        },
        "environment_fingerprint": fx.fingerprint("idaes", ENV_DIR),
        "property_package": "idaes.models.properties.activity_coeff_models."
        "activity_coeff_prop_pack (ActivityCoeffParameterData / ActivityCoeffStateBlockData "
        "subclassed for the components, the parameters and the S10 P^sat at its three sites)",
        "package_sha256": file_sha256(
            Path(idaes.__file__).parent
            / "models"
            / "properties"
            / "activity_coeff_models"
            / "activity_coeff_prop_pack.py"
        ),
        "mapping": mp,
        "application_notes": APPLICATION_NOTES,
        "inspection": structure,
        "readbacks": readbacks,
        "ladder": {"registered": inputs["ladder"], **ladder},
        "wall_time_import_s": t_import,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(fx.finite(doc), indent=1) + "\n", encoding="utf-8")
    per = ladder["optimal_rungs_per_state"]
    n_opt = sum(1 for s in per.values() if s)
    print(
        f"idaes S10: dof={structure['degrees_of_freedom']} wagner_refs="
        f"{len(structure['wagner_parameter_references_in_active_constraints'])} "
        f"readbacks={len(readbacks)} optimal_somewhere={n_opt}/{len(per)} "
        f"selected_rung={ladder['selected_rung_eps_K']} "
        f"not_comparable={ladder['not_comparable']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
