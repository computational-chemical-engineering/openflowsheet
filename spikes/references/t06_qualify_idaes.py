"""T06 M6: blind reference qualification in IDAES — accept, converge, and rule 2's self-check.

For each fixture of `t06_fixtures.FIXTURES` (spec §9.2's REF-01 ... REF-08 and §9.4's PC-2;
PC-1 is DWSIM-only) this script builds the IDAES model on SYN-001's constants (the property
package of `idaes_representability.py`, i.e. `docs/reference-environments.md` §5.0), applies
spec §9.3's settings, initializes, solves, and writes one JSON per fixture with:

* ``accepted`` — the model built and has zero degrees of freedom;
* ``converged`` — initialization raised nothing and the final Ipopt solve ended optimal;
* ``self_check`` — rule 2 (§9.5): the tool's own overall component balance, from its own ports;
  rule 2b (§9.5 as amended by A2): the SmoothVLE shift of every state block's equilibrium
  temperature, with the ``eps_1``/``eps_2`` each block carries; and, as further tool-internal
  evidence, the largest residual of any active constraint;
* the tool's raw output (every variable of the solved model, and every SmoothVLE ``eps`` parameter
  as the model holds it after the solve), versions, the environment
  fingerprint, the settings, every adjustment made, the Ipopt log, and wall times;
* ``compared_quantities`` — spec §9.2's compared quantities of the fixture, named by
  `t06_fixtures.COMPARED`, read from the solved model's ports and unit variables, with each one's
  Pyomo source in ``compared_quantity_sources`` (T06 W8).

It is blind (spec §9.6): nothing of this project, and not the twin, is read. It prints only the
flags. Run from the repository root after `scripts/build-reference-envs.sh`:

    .venv-idaes/bin/python spikes/references/t06_qualify_idaes.py --out <dir>

Not part of `scripts/check.sh`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

import t06_fixtures as fx

ENV_DIR = fx.REPO_ROOT / ".venv-idaes"

# Every change to a §9.3 setting made to get a model accepted or converged, per fixture. Judged on
# self-consistency alone and brought to the design lane (spec §17 M6). Empty = none was needed.
# M6's three (constr_viol_tol 1e-10 -> 1e-9 on REF-04, REF-05, REF-06, where 1e-10 sat at the
# binary64 floor of a Pa row) became the registered setting for every fixture (spec §9.3 as
# amended by A1, ruling M6 (a); t06_fixtures.IDAES_SOLVER_OPTIONS), so none remains.
ADJUSTMENTS: dict[str, list[str]] = {}
# The Ipopt option overrides those adjustments consist of, per fixture.
IPOPT_OPTION_ADJUSTMENTS: dict[str, dict[str, Any]] = {}

# How §9.3 is applied beyond the final solve (recorded with every run; not adjustments).
APPLICATION_NOTES = [
    "IDAES unit initializers call idaes.core.solvers.get_solver(), whose Ipopt would use the "
    "bundled default linear solver HSL MA27; idaes.cfg.ipopt.options.linear_solver is set to "
    "'mumps' before any model is built so that MA27 is used nowhere (spec §9.3 D19 disclosure). "
    "The initializers' other options stay IDAES defaults (tol 1e-6, max_iter 200, "
    "gradient-based scaling); the final solve uses spec §9.3's options.",
    "Mixer: MomentumMixingType.none with the outlet pressure fixed at P_r (spec §9.3).",
    "Conversion reactor: StoichiometricReactor, extent = X n_key,in / |nu_key| written as a "
    "constraint; h_form,liq = 0 and h_form,ig = L_i (spec §9.3 IDAES reaction datum).",
    "SmoothVLE: eps_1 = eps_2 = 1e-8 K is set on every state block that carries SmoothVLE's "
    "equilibrium temperature (_teq), after the model is built and before any initializer runs, "
    "so that initializers and the final solve see the same equations (spec §9.3 as amended by "
    "A2; IDAES's defaults are 0.01 K and 5e-4 K).",
]


def set_smooth_vle_eps(m: Any) -> list[str]:
    """Spec §9.3 (A2): the registered ``eps_1``, ``eps_2`` on every SmoothVLE state block.

    A SmoothVLE state block is one that owns ``_teq``; for each of its phase pairs both smoothing
    parameters must exist (SYN-001 has no liquid-only or vapour-only component, so IDAES builds
    both), and a block without them is an error, not a skip. Returns the blocks set.
    """
    import pyomo.environ as pyo

    done = []
    for b in m.component_data_objects(pyo.Block, descend_into=True):
        teq = b.component("_teq")  # component(), not getattr: no build-on-demand side effect
        if teq is None:
            continue
        for pair in teq:
            suffix = "_" + "_".join(pair)
            for which, eps in fx.IDAES_SMOOTH_VLE_EPS_K.items():
                param = b.component(which + suffix)
                if param is None:
                    raise ValueError(f"{b.name}: SmoothVLE block without {which}{suffix}")
                param.set_value(eps)
            done.append(f"{b.name}[{','.join(pair)}]")
    if not done:
        raise ValueError("no SmoothVLE state block found")
    return done


def smooth_vle_parameters(m: Any) -> dict[str, float]:
    """Every SmoothVLE ``eps_1_*``/``eps_2_*`` parameter by name, as the model holds it."""
    import pyomo.environ as pyo

    return {
        p.name: float(pyo.value(p))
        for p in m.component_data_objects(pyo.Param, descend_into=True)
        if p.parent_component().local_name.startswith(("eps_1_", "eps_2_"))
    }


def comp_flows(port: Any) -> dict[str, float]:
    import pyomo.environ as pyo

    return {
        c: float(pyo.value(port.flow_mol[0] * port.mole_frac_comp[0, c])) for c in fx.COMPONENTS
    }


def fix_feed(port: Any, feed: dict[str, Any]) -> None:
    from idaes_representability import fix_port

    fix_port(port, feed["flows"], feed["T"], feed["P"])


def build_mixer(f: dict[str, Any]) -> tuple[Any, Callable[[Any], dict[str, Any]]]:
    from idaes.models.unit_models import Mixer, MomentumMixingType
    from idaes_representability import new_flowsheet

    m = new_flowsheet()
    m.fs.unit = Mixer(
        property_package=m.fs.props,
        inlet_list=["S1", "S2"],
        momentum_mixing_type=MomentumMixingType.none,
    )
    fix_feed(m.fs.unit.S1, f["feeds"]["S1"])
    fix_feed(m.fs.unit.S2, f["feeds"]["S2"])
    m.fs.unit.mixed_state[0].pressure.fix(f["outlet_P"])

    def check(m: Any) -> dict[str, Any]:
        u = m.fs.unit
        return fx.component_balance([comp_flows(u.S1), comp_flows(u.S2)], [comp_flows(u.outlet)])

    return m, check


def build_splitter(f: dict[str, Any]) -> tuple[Any, Callable[[Any], dict[str, Any]]]:
    from idaes.models.unit_models import Separator
    from idaes.models.unit_models.separator import EnergySplittingType, SplittingType
    from idaes_representability import new_flowsheet

    m = new_flowsheet()
    m.fs.unit = Separator(
        property_package=m.fs.props,
        outlet_list=["S2", "S3"],
        split_basis=SplittingType.totalFlow,
        energy_split_basis=EnergySplittingType.equal_temperature,
    )
    fix_feed(m.fs.unit.inlet, f["feeds"]["S1"])
    m.fs.unit.split_fraction[0, "S2"].fix(f["split_fraction_S2"])

    def check(m: Any) -> dict[str, Any]:
        u = m.fs.unit
        return fx.component_balance([comp_flows(u.inlet)], [comp_flows(u.S2), comp_flows(u.S3)])

    return m, check


def build_heater(f: dict[str, Any]) -> tuple[Any, Callable[[Any], dict[str, Any]]]:
    from idaes.models.unit_models import Heater
    from idaes_representability import new_flowsheet

    m = new_flowsheet()
    m.fs.unit = Heater(property_package=m.fs.props, has_pressure_change=False)
    fix_feed(m.fs.unit.inlet, f["feeds"]["S1"])
    m.fs.unit.outlet.temperature.fix(f["outlet_T"])
    return m, _in_out_check


def _in_out_check(m: Any) -> dict[str, Any]:
    u = m.fs.unit
    return fx.component_balance([comp_flows(u.inlet)], [comp_flows(u.outlet)])


def build_flash(f: dict[str, Any]) -> tuple[Any, Callable[[Any], dict[str, Any]]]:
    from idaes.models.unit_models import Flash
    from idaes_representability import new_flowsheet

    feed = f["feeds"]["S1"]
    if feed["P"] != f["flash_P"]:
        raise ValueError("the flash fixtures have no pressure change: feed P must equal flash P")
    m = new_flowsheet()
    m.fs.unit = Flash(property_package=m.fs.props)
    fix_feed(m.fs.unit.inlet, feed)
    m.fs.unit.deltaP.fix(0)
    m.fs.unit.control_volume.properties_out[0].temperature.fix(f["flash_T"])

    def check(m: Any) -> dict[str, Any]:
        u = m.fs.unit
        return fx.component_balance(
            [comp_flows(u.inlet)], [comp_flows(u.vap_outlet), comp_flows(u.liq_outlet)]
        )

    return m, check


def build_valve(f: dict[str, Any]) -> tuple[Any, Callable[[Any], dict[str, Any]]]:
    from idaes.models.unit_models import PressureChanger
    from idaes.models.unit_models.pressure_changer import ThermodynamicAssumption
    from idaes_representability import new_flowsheet

    m = new_flowsheet()
    m.fs.unit = PressureChanger(
        property_package=m.fs.props,
        thermodynamic_assumption=ThermodynamicAssumption.adiabatic,
        compressor=False,
    )
    fix_feed(m.fs.unit.inlet, f["feeds"]["S1"])
    m.fs.unit.outlet.pressure.fix(f["outlet_P"])
    return m, _in_out_check


def build_pump(f: dict[str, Any]) -> tuple[Any, Callable[[Any], dict[str, Any]]]:
    from idaes.models.unit_models import PressureChanger
    from idaes.models.unit_models.pressure_changer import ThermodynamicAssumption
    from idaes_representability import new_flowsheet

    m = new_flowsheet()
    m.fs.unit = PressureChanger(
        property_package=m.fs.props,
        thermodynamic_assumption=ThermodynamicAssumption.pump,
        compressor=True,
    )
    fix_feed(m.fs.unit.inlet, f["feeds"]["S1"])
    m.fs.unit.outlet.pressure.fix(f["outlet_P"])
    m.fs.unit.efficiency_pump.fix(f["efficiency"])
    return m, _in_out_check


def build_reactor(f: dict[str, Any]) -> tuple[Any, Callable[[Any], dict[str, Any]]]:
    import pyomo.environ as pyo
    from idaes.core import MaterialBalanceType
    from idaes.models.properties.modular_properties.base.generic_reaction import (
        GenericReactionParameterBlock,
    )
    from idaes.models.unit_models import StoichiometricReactor
    from idaes_representability import new_flowsheet

    if f["phase"] != "liquid":
        raise ValueError("only the liquid-phase reaction of REF-07 is defined")
    m = new_flowsheet()
    u = pyo.units
    m.fs.rxn = GenericReactionParameterBlock(
        property_package=m.fs.props,
        rate_reactions={
            "R1": {"stoichiometry": {("Liq", c): nu for c, nu in f["nu"].items()}},
        },
        base_units={"time": u.s, "length": u.m, "mass": u.kg, "amount": u.mol, "temperature": u.K},
    )
    m.fs.unit = StoichiometricReactor(
        property_package=m.fs.props,
        reaction_package=m.fs.rxn,
        material_balance_type=MaterialBalanceType.componentTotal,
        has_heat_of_reaction=False,  # enthalpies carry the formation terms (§9.3)
        has_heat_transfer=True,
        has_pressure_change=False,
    )
    feed = f["feeds"]["S1"]
    fix_feed(m.fs.unit.inlet, feed)
    key, x_key = f["key"], f["conversion"]
    m.fs.unit.conversion_spec = pyo.Constraint(
        expr=m.fs.unit.rate_reaction_extent[0, "R1"] * abs(f["nu"][key])
        == x_key * m.fs.unit.inlet.flow_mol[0] * m.fs.unit.inlet.mole_frac_comp[0, key]
    )
    m.fs.unit.outlet.temperature.fix(f["outlet_T"])
    m.fs.unit.rate_reaction_extent[0, "R1"].value = x_key * feed["flows"][key] / abs(f["nu"][key])

    def check(m: Any) -> dict[str, Any]:
        un = m.fs.unit
        xi = float(pyo.value(un.rate_reaction_extent[0, "R1"]))
        rec = fx.component_balance(
            [comp_flows(un.inlet)],
            [comp_flows(un.outlet)],
            generation={c: f["nu"][c] * xi for c in fx.COMPONENTS},
        )
        rec["extent_used_mol_per_s"] = xi
        return rec

    return m, check


def build_recycle(f: dict[str, Any]) -> tuple[Any, Callable[[Any], dict[str, Any]]]:
    import pyomo.environ as pyo
    from idaes.models.unit_models import Flash, Heater, Mixer, MomentumMixingType, Separator
    from idaes.models.unit_models.separator import EnergySplittingType, SplittingType
    from idaes_representability import new_flowsheet
    from pyomo.network import Arc

    m = new_flowsheet()
    fs = m.fs
    fs.mix = Mixer(
        property_package=fs.props,
        inlet_list=["feed", "recycle"],
        momentum_mixing_type=MomentumMixingType.none,
    )
    fs.heat = Heater(property_package=fs.props, has_pressure_change=False)
    fs.flash = Flash(property_package=fs.props)
    fs.split = Separator(
        property_package=fs.props,
        outlet_list=["recycle", "purge"],
        split_basis=SplittingType.totalFlow,
        energy_split_basis=EnergySplittingType.equal_temperature,
    )
    fs.s2 = Arc(source=fs.mix.outlet, destination=fs.heat.inlet)
    fs.s3 = Arc(source=fs.heat.outlet, destination=fs.flash.inlet)
    fs.s5 = Arc(source=fs.flash.liq_outlet, destination=fs.split.inlet)
    fs.s6 = Arc(source=fs.split.recycle, destination=fs.mix.recycle)
    pyo.TransformationFactory("network.expand_arcs").apply_to(m)

    fix_feed(fs.mix.feed, f["feeds"]["S1"])
    fs.mix.mixed_state[0].pressure.fix(fx.P_REF)
    fs.heat.outlet.temperature.fix(f["heater_T"])
    fs.flash.deltaP.fix(0)
    fs.flash.control_volume.properties_out[0].temperature.fix(f["flash_T"])
    fs.split.split_fraction[0, "recycle"].fix(f["split_fraction_recycle"])
    # The tear guess is fixed on the mixer's recycle inlet only while the sequential
    # initialization runs (initialize_recycle); DOF is counted with the loop closed.

    def check(m: Any) -> dict[str, Any]:
        return fx.component_balance(
            [comp_flows(m.fs.mix.feed)],
            [comp_flows(m.fs.flash.vap_outlet), comp_flows(m.fs.split.purge)],
        )

    return m, check


def initialize_recycle(m: Any, f: dict[str, Any]) -> None:
    """Sequential initialization on the torn S6 guess, as the representability probe does."""
    from idaes.core.util.initialization import propagate_state

    fs = m.fs
    port = fs.mix.recycle
    fix_feed(port, f["tear_guess"])
    fs.mix.initialize()
    for c in fx.COMPONENTS:
        port.mole_frac_comp[0, c].unfix()
    port.flow_mol.unfix()
    port.temperature.unfix()
    port.pressure.unfix()
    propagate_state(fs.s2)
    fs.heat.initialize()
    propagate_state(fs.s3)
    fs.flash.initialize()
    propagate_state(fs.s5)
    fs.split.initialize()


BUILDERS: dict[str, Callable[[dict[str, Any]], tuple[Any, Callable[[Any], dict[str, Any]]]]] = {
    "mixer": build_mixer,
    "splitter": build_splitter,
    "heater": build_heater,
    "flash": build_flash,
    "valve": build_valve,
    "pump": build_pump,
    "conversion_reactor": build_reactor,
    "recycle": build_recycle,
}


def compared_quantities(fid: str, f: dict[str, Any], m: Any) -> dict[str, dict[str, Any]]:
    """Spec §9.2's compared quantities (names: `t06_fixtures.COMPARED`) from the solved model.

    Each is read from the port, state block or unit variable that carries the named stream or
    unit, and recorded with that component's Pyomo name. Flows in mol/s, ``T`` in K, duty and
    work in W, IDAES's sign (heat and work into the unit positive).
    """
    import pyomo.environ as pyo

    fs = m.fs
    out: dict[str, dict[str, Any]] = {}

    def flows(stream: str, port: Any) -> None:
        for c, v in comp_flows(port).items():
            out[f"{stream}.n.{c}"] = {"value": v, "source": f"{port.name} flow_mol*mole_frac_comp"}

    def vapour(stream: str, sb: Any) -> None:
        for c in fx.COMPONENTS:
            v = float(pyo.value(sb.flow_mol_phase["Vap"] * sb.mole_frac_phase_comp["Vap", c]))
            out[f"{stream}.vap.{c}"] = {
                "value": v,
                "source": f"{sb.name} flow_mol_phase[Vap]*mole_frac_phase_comp[Vap,{c}]",
            }

    def scalar(quantity: str, var: Any) -> None:
        out[quantity] = {"value": float(pyo.value(var)), "source": var.name}

    unit = f["unit"]
    if unit == "recycle":
        flows("S4", fs.flash.vap_outlet)
        flows("S6", fs.split.recycle)
        flows("S7", fs.split.purge)
        scalar("U-HEAT.Q", fs.heat.heat_duty[0])
        scalar("U-FLASH.Q", fs.flash.heat_duty[0])
        scalar("S2.T", fs.mix.outlet.temperature[0])
    else:
        u = fs.unit
        if unit == "mixer":
            flows("S3", u.outlet)
            scalar("S3.T", u.outlet.temperature[0])
        elif unit == "splitter":
            for s in ("S2", "S3"):
                flows(s, getattr(u, s))
                scalar(f"{s}.T", getattr(u, s).temperature[0])
        elif unit == "heater":
            scalar("U-HEAT.Q", u.heat_duty[0])
            vapour("S2", u.control_volume.properties_out[0])
        elif unit == "flash":
            scalar("U-FLASH.Q", u.heat_duty[0])
            flows("S2", u.vap_outlet)
            flows("S3", u.liq_outlet)
        elif unit == "valve":
            scalar("S2.T", u.outlet.temperature[0])
            vapour("S2", u.control_volume.properties_out[0])
        elif unit == "pump":
            scalar("U-PUMP.W", u.work_mechanical[0])
            scalar("S2.T", u.outlet.temperature[0])
        elif unit == "conversion_reactor":
            flows("S2", u.outlet)
            scalar("U-RX.Q", u.heat_duty[0])
    wanted = fx.COMPARED[fid]
    if missing := [q for q in wanted if q not in out]:
        raise ValueError(f"{fid}: no reading for the registered quantities {missing}")
    return {q: out[q] for q in wanted}


def constraint_residuals(m: Any) -> dict[str, Any]:
    """Largest violation over all active constraints (unscaled, the model's own units)."""
    import pyomo.environ as pyo

    worst, worst_name, count = 0.0, None, 0
    for c in m.component_data_objects(pyo.Constraint, active=True, descend_into=True):
        body = pyo.value(c.body, exception=False)
        if body is None:
            continue
        lo = pyo.value(c.lower) if c.has_lb() else None
        up = pyo.value(c.upper) if c.has_ub() else None
        viol = max(
            0.0, (lo - body) if lo is not None else 0.0, (body - up) if up is not None else 0.0
        )
        if viol > 1e-8:
            count += 1
        if viol > worst:
            worst, worst_name = viol, c.name
    return {
        "max_abs_violation": worst,
        "argmax": worst_name,
        "count_above_1e-8": count,
    }


def all_variables(m: Any) -> dict[str, Any]:
    import pyomo.environ as pyo

    return {
        v.name: (None if v.value is None else float(v.value))
        for v in m.component_data_objects(pyo.Var, descend_into=True)
    }


def parse_ipopt_log(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if mt := re.search(r"running with linear solver (\w+)", text):
        out["linear_solver"] = mt.group(1)
    if mt := re.search(r"Number of Iterations\.+:\s*(\d+)", text):
        out["iterations"] = int(mt.group(1))
    if mt := re.search(r"EXIT: (.*)", text):
        out["exit"] = mt.group(1).strip()
    if mt := re.search(r"This is Ipopt version ([\w.]+)", text):
        out["ipopt_version"] = mt.group(1)
    for key, pat in {
        "final_constraint_violation_unscaled": r"Constraint violation\.+:\s*\S+\s+(\S+)",
        "final_overall_nlp_error_scaled": r"Overall NLP error\.+:\s*(\S+)",
    }.items():
        if mt := re.search(pat, text):
            out[key] = float(mt.group(1))
    return out


def run_fixture(fid: str, f: dict[str, Any], log_dir: Path) -> dict[str, Any]:
    import pyomo.environ as pyo
    from idaes.core.util.model_statistics import degrees_of_freedom

    rec: dict[str, Any] = {
        "fixture": fid,
        "definition": f,
        "adjustments": ADJUSTMENTS.get(fid, []),
        "accepted": False,
        "converged": False,
        "stage_reached": "build",
    }
    t0 = time.perf_counter()
    try:
        m, check = BUILDERS[f["unit"]](f)
        rec["smooth_vle_eps_set_on"] = set_smooth_vle_eps(m)
        rec["degrees_of_freedom"] = int(degrees_of_freedom(m))
        rec["accepted"] = rec["degrees_of_freedom"] == 0
        if not rec["accepted"]:
            return rec
        rec["stage_reached"] = "initialize"
        t1 = time.perf_counter()
        if f["unit"] == "recycle":
            initialize_recycle(m, f)
        else:
            m.fs.unit.initialize()
        rec["wall_time_initialize_s"] = time.perf_counter() - t1
        rec["stage_reached"] = "solve"
        solver = pyo.SolverFactory("ipopt")
        options = {**fx.IDAES_SOLVER_OPTIONS, **IPOPT_OPTION_ADJUSTMENTS.get(fid, {})}
        for k, v in options.items():
            solver.options[k] = v
        rec["final_solve_ipopt_options_used"] = options
        log = log_dir / f"idaes-{fid}.ipopt.log"
        t2 = time.perf_counter()
        result = solver.solve(m, tee=False, logfile=str(log), load_solutions=False)
        rec["wall_time_solve_s"] = time.perf_counter() - t2
        rec["solver_status"] = str(result.solver.status)
        rec["termination_condition"] = str(result.solver.termination_condition)
        rec["ipopt"] = parse_ipopt_log(log.read_text(encoding="utf-8", errors="replace"))
        # Converged means Ipopt met the requested tolerances. Pyomo also reports "Solved To
        # Acceptable Level" (Ipopt's looser acceptable_* criteria) as optimal; that is not counted.
        rec["converged"] = bool(pyo.check_optimal_termination(result)) and (
            rec["ipopt"].get("exit") == "Optimal Solution Found."
        )
        if not rec["converged"]:
            # Keep the solver's last iterate so that the self-check below describes it; Pyomo
            # refuses to load a non-optimal result unless its status is downgraded to warning.
            from pyomo.opt import SolverStatus

            result.solver.status = SolverStatus.warning
            rec["last_iterate_loaded_although_not_converged"] = True
        m.solutions.load_from(result)
        rec["stage_reached"] = "solved" if rec["converged"] else "solve_not_converged"
        variables, eps = all_variables(m), smooth_vle_parameters(m)
        rec["self_check"] = {
            "rule2_component_balance": check(m),
            "rule2b_smooth_vle": fx.smooth_vle_self_check(variables, eps),
            "constraint_residuals": constraint_residuals(m),
        }
        rec["raw_output"] = {"variables": variables, "smooth_vle_parameters": eps}
        reported = compared_quantities(fid, f, m)
        rec["compared_quantities"] = {q: r["value"] for q, r in reported.items()}
        rec["compared_quantity_sources"] = {q: r["source"] for q, r in reported.items()}
    except Exception as exc:  # every failure is recorded, none is hidden
        rec["error"] = f"{type(exc).__name__}: {exc}"
        rec["traceback"] = traceback.format_exc(limit=6)
    finally:
        rec["wall_time_total_s"] = time.perf_counter() - t0
    return rec


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True, help="directory for the JSON records")
    parser.add_argument("--only", nargs="*", help="fixture ids (default: all)")
    args = parser.parse_args()
    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # IDAES reads its data directory (binary extensions) at import time.
    os.environ.setdefault("IDAES_DATA", str(ENV_DIR / "idaes-data"))
    t_import = time.perf_counter()
    import idaes
    import idaes_representability as probe
    import pyomo

    idaes.cfg.ipopt.options.linear_solver = fx.IDAES_SOLVER_OPTIONS["linear_solver"]
    t_import = time.perf_counter() - t_import
    if (probe.CRIT_T, probe.CRIT_P) != (fx.PLACEHOLDER_TC, fx.PLACEHOLDER_PC):
        raise SystemExit("placeholder constants differ from spec §9.3")

    common = {
        "tool": "IDAES",
        "versions": {
            "idaes_pse": idaes.__version__,
            "pyomo": pyomo.__version__,
            "python": sys.version.split()[0],
        },
        "environment_fingerprint": fx.fingerprint("idaes", ENV_DIR),
        "settings": {
            "final_solve_ipopt_options": fx.IDAES_SOLVER_OPTIONS,
            "smooth_vle_eps_K": fx.IDAES_SMOOTH_VLE_EPS_K,
            "initializer_ipopt_options": dict(idaes.cfg.ipopt.options),
            "placeholders": {"T_c_K": probe.CRIT_T, "P_c_Pa": probe.CRIT_P},
            "property_package": "idaes_representability.build_property_package (SYN-001, "
            "Ideal EoS, SmoothVLE, h_form_ig = L_i, h_form_liq = 0)",
        },
        "application_notes": APPLICATION_NOTES,
        "wall_time_import_s": t_import,
    }
    status = 0
    ids = args.only or list(fx.FIXTURES)
    for fid in ids:
        if fid in fx.NOT_APPLICABLE["IDAES"]:
            rec = {"fixture": fid, "not_applicable": fx.NOT_APPLICABLE["IDAES"][fid]}
        else:
            rec = run_fixture(fid, fx.FIXTURES[fid], out_dir)
            rule2 = rec.get("self_check", {}).get("rule2_component_balance", {})
            rule2b = rec.get("self_check", {}).get("rule2b_smooth_vle", {})
            ok = (
                rec["accepted"]
                and rec["converged"]
                and rule2.get("passes")
                and rule2b.get("passes")
                and "error" not in rec
            )
            status |= 0 if ok else 1
        rec = {**common, **rec}
        path = out_dir / f"idaes-{fid}.json"
        path.write_text(json.dumps(fx.finite(rec), indent=1) + "\n", encoding="utf-8")
        print(
            f"idaes {fid}: accepted={rec.get('accepted')} converged={rec.get('converged')} "
            f"rule2={rec.get('self_check', {}).get('rule2_component_balance', {}).get('passes')} "
            f"rule2b={rec.get('self_check', {}).get('rule2b_smooth_vle', {}).get('passes')}"
            + (f" ERROR {rec['error']}" if "error" in rec else ""),
            file=sys.stderr,
        )
    return status


if __name__ == "__main__":
    sys.exit(main())
