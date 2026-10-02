"""T06 representability probe for IDAES: can each plan §6.4 fixture be built from user constants?

For every fixture of plan §6.4 (mixer, splitter, heater, ideal flash, valve, liquid pump,
conversion reactor, recycle) this script builds a small IDAES flowsheet on a user-defined
three-component set carrying the SYN-001 constants (`docs/derivations/SYN-001.md` §1), counts
degrees of freedom, initializes and solves it, and records the outcome. The question it answers
is *expressibility* — does IDAES accept these constants and this unit with the stated
specification — and which of IDAES's own equations are then in force. It does **not** compare
any number with this project, choose a tolerance, or tune either side; the values it prints are
the tool's raw output and are not reference values (that is T06's `verdict`/`specifier` work).

How the SYN-001 set maps onto IDAES's modular property framework (IDAES 2.13.0):

* Ideal EoS in both phases (`eos/ideal.py`). Liquid molar enthalpy there is
  ``enth_mol_liq_comp(T) + (P - pressure_ref)/dens_mol_liq``; with ``Constant`` liquid
  properties, ``pressure_ref = P_r`` and ``temperature_ref = T_r`` this is SYN-001's
  ``c_p (T - T_r) + v_i (P - P_r)``. Vapor molar enthalpy is ``c_p (T - T_r) + h_form,ig``,
  with ``h_form,ig = L_i``: SYN-001's ``c_p (T - T_r) + L_i``.
* Vapor pressure is a user-written pure-component method (`SynPsat` below):
  ``P_r exp[(L_i/R)(1/T_b,i - 1/T)]``.
* Liquid fugacity in the Ideal EoS is ``x_i Psat_i(T)`` (Raoult), so the K-value IDAES solves
  with is ``Psat_i/P``. SYN-001's K carries a further Poynting factor
  ``exp[v_i (P - P_r)/(RT)]``, which is 1 at ``P = P_r`` and not 1 elsewhere. That difference is
  reported, not patched: adding it would need a user-written EoS or phase-equilibrium form.
* Phase equilibrium uses IDAES's ``SmoothVLE`` formulation (smooth max complementarity for
  phase existence); in a two-phase solution it reduces to ``y_i P = x_i Psat_i``.

Run from the repository root after `scripts/build-reference-envs.sh`:

    .venv-idaes/bin/python spikes/references/idaes_representability.py [--json out.json]

`IDAES_DATA` defaults to `.venv-idaes/idaes-data`, where the build script put the extensions.

Not part of `scripts/check.sh`.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

# SYN-001 constants, verbatim from docs/derivations/SYN-001.md §1 (plan §3.1).
T_BOIL = {"A": 320.0, "B": 360.0, "C": 400.0}  # K
L_VAP = {"A": 25_000.0, "B": 30_000.0, "C": 35_000.0}  # J/mol
CP = 100.0  # J/(mol K), both phases
V_LIQ = 1.0e-4  # m3/mol
MW = 0.100  # kg/mol
T_REF = 300.0  # K
P_REF = 100_000.0  # Pa
COMPONENTS = ("A", "B", "C")
REPO_ROOT = Path(__file__).resolve().parents[2]
CRIT_T = 1000.0  # K, inert placeholder (see build_property_package)
CRIT_P = 1.0e7  # Pa, inert placeholder


def build_property_package(m: Any) -> None:
    """Attach a GenericParameterBlock carrying the SYN-001 constants to ``m.fs.props``."""
    import pyomo.environ as pyo
    from idaes.core import Component, LiquidPhase, VaporPhase
    from idaes.core.util.misc import set_param_from_config
    from idaes.models.properties.modular_properties.base.generic_property import (
        GenericParameterBlock,
    )
    from idaes.models.properties.modular_properties.eos.ideal import Ideal
    from idaes.models.properties.modular_properties.phase_equil import SmoothVLE
    from idaes.models.properties.modular_properties.phase_equil.bubble_dew import (
        IdealBubbleDew,
    )
    from idaes.models.properties.modular_properties.phase_equil.forms import fugacity
    from idaes.models.properties.modular_properties.pure.ConstantProperties import Constant
    from idaes.models.properties.modular_properties.state_definitions import FTPx
    from pyomo.environ import units as u

    class SynPsat:
        """User pure-component method: P_r exp[(L_i/R)(1/T_b,i - 1/T)] (SYN-001 §3)."""

        @staticmethod
        def build_parameters(cobj: Any) -> None:
            cobj.syn_t_boil = pyo.Var(units=u.K, doc="SYN-001 T_b,i")
            set_param_from_config(cobj, param="syn_t_boil")
            cobj.syn_l_vap = pyo.Var(units=u.J / u.mol, doc="SYN-001 L_i")
            set_param_from_config(cobj, param="syn_l_vap")

        @staticmethod
        def return_expression(b: Any, cobj: Any, T: Any, dT: bool = False) -> Any:  # noqa: N803
            r_gas = 8.31446261815324 * u.J / u.mol / u.K
            psat = b.params.pressure_ref * pyo.exp(
                cobj.syn_l_vap / r_gas * (1 / cobj.syn_t_boil - 1 / T)
            )
            if dT:
                return psat * cobj.syn_l_vap / (r_gas * T**2)
            return psat

    def component(name: str) -> dict[str, Any]:
        return {
            "type": Component,
            "valid_phase_types": None,
            "pressure_sat_comp": SynPsat,
            "enth_mol_ig_comp": Constant,
            "enth_mol_liq_comp": Constant,
            "dens_mol_liq_comp": Constant,
            "phase_equilibrium_form": {("Vap", "Liq"): fugacity},
            "parameter_data": {
                "mw": (MW, u.kg / u.mol),
                "syn_t_boil": (T_BOIL[name], u.K),
                "syn_l_vap": (L_VAP[name], u.J / u.mol),
                "cp_mol_ig_comp_coeff": (CP, u.J / u.mol / u.K),
                "cp_mol_liq_comp_coeff": (CP, u.J / u.mol / u.K),
                "enth_mol_form_ig_comp_ref": (L_VAP[name], u.J / u.mol),
                "enth_mol_form_liq_comp_ref": (0.0, u.J / u.mol),
                "dens_mol_liq_comp_coeff": (1.0 / V_LIQ, u.mol / u.m**3),
                # SYN-001 has no critical point. IDAES's state-block initializer builds the
                # mixture critical-point estimate whenever these exist on the parameter block and
                # fails without them, although no Ideal-EoS equation used here reads them. Values
                # far outside the declared domain. They are not bit-inert: they add decoupled
                # critical-point rows to the same NLP, and changing them moved the results by at
                # most 6e-16 relative (docs/reference-environments.md §5.1).
                "temperature_crit": (CRIT_T, u.K),
                "pressure_crit": (CRIT_P, u.Pa),
            },
        }

    config = {
        "components": {c: component(c) for c in COMPONENTS},
        "phases": {
            "Liq": {"type": LiquidPhase, "equation_of_state": Ideal},
            "Vap": {"type": VaporPhase, "equation_of_state": Ideal},
        },
        "base_units": {
            "time": u.s,
            "length": u.m,
            "mass": u.kg,
            "amount": u.mol,
            "temperature": u.K,
        },
        "state_definition": FTPx,
        # SYN-001's declared domain (§1): 280-440 K, 5e4-2e5 Pa.
        "state_bounds": {
            "flow_mol": (0, 1, 1000, u.mol / u.s),
            "temperature": (280, 330, 440, u.K),
            "pressure": (5e4, 1e5, 2e5, u.Pa),
        },
        "pressure_ref": (P_REF, u.Pa),
        "temperature_ref": (T_REF, u.K),
        "phases_in_equilibrium": [("Vap", "Liq")],
        "phase_equilibrium_state": {("Vap", "Liq"): SmoothVLE},
        "bubble_dew_method": IdealBubbleDew,
    }
    m.fs.props = GenericParameterBlock(**config)


def new_flowsheet() -> Any:
    import pyomo.environ as pyo
    from idaes.core import FlowsheetBlock

    m = pyo.ConcreteModel()
    m.fs = FlowsheetBlock(dynamic=False)
    build_property_package(m)
    return m


def fix_port(port: Any, flows: dict[str, float], temperature: float, pressure: float) -> None:
    total = sum(flows.values())
    port.flow_mol.fix(total)
    port.temperature.fix(temperature)
    port.pressure.fix(pressure)
    for c in COMPONENTS:
        port.mole_frac_comp[0, c].fix(flows[c] / total)


def solve(m: Any) -> dict[str, Any]:
    import pyomo.environ as pyo
    from idaes.core.util.model_statistics import degrees_of_freedom

    dof = degrees_of_freedom(m)
    result = pyo.SolverFactory("ipopt").solve(m)
    return {
        "degrees_of_freedom": dof,
        "termination_condition": str(result.solver.termination_condition),
    }


EQUIMOLAR = {"A": 1.0, "B": 1.0, "C": 1.0}


def fixture_mixer() -> dict[str, Any]:
    import pyomo.environ as pyo
    from idaes.models.unit_models import Mixer, MomentumMixingType

    m = new_flowsheet()
    # MomentumMixingType.none plus an outlet-pressure specification: 'equality' writes one
    # P_out = P_in row per inlet (redundant for two fixed equal inlets, and structurally
    # redundant in a closed loop), 'minimize' is a smoothed min(). Recorded in the doc.
    m.fs.unit = Mixer(
        property_package=m.fs.props,
        inlet_list=["feed", "recycle"],
        momentum_mixing_type=MomentumMixingType.none,
    )
    fix_port(m.fs.unit.feed, EQUIMOLAR, 300.0, P_REF)
    fix_port(m.fs.unit.recycle, {"A": 0.2, "B": 0.6, "C": 0.8}, 360.0, P_REF)
    m.fs.unit.mixed_state[0].pressure.fix(P_REF)
    m.fs.unit.initialize()
    out = solve(m)
    out["tool_outlet_T_K"] = pyo.value(m.fs.unit.mixed_state[0].temperature)
    return out


def fixture_splitter() -> dict[str, Any]:
    import pyomo.environ as pyo
    from idaes.models.unit_models import Separator
    from idaes.models.unit_models.separator import EnergySplittingType, SplittingType

    m = new_flowsheet()
    m.fs.unit = Separator(
        property_package=m.fs.props,
        outlet_list=["recycle", "purge"],
        split_basis=SplittingType.totalFlow,
        energy_split_basis=EnergySplittingType.equal_temperature,
    )
    fix_port(m.fs.unit.inlet, {"A": 0.2, "B": 0.6, "C": 0.8}, 360.0, P_REF)
    m.fs.unit.split_fraction[0, "recycle"].fix(0.5)
    m.fs.unit.initialize()
    out = solve(m)
    out["tool_recycle_flow"] = pyo.value(m.fs.unit.recycle.flow_mol[0])
    return out


def fixture_heater() -> dict[str, Any]:
    import pyomo.environ as pyo
    from idaes.models.unit_models import Heater

    m = new_flowsheet()
    m.fs.unit = Heater(property_package=m.fs.props, has_pressure_change=False)
    fix_port(m.fs.unit.inlet, EQUIMOLAR, 321.2, P_REF)
    m.fs.unit.outlet.temperature.fix(350.0)
    m.fs.unit.initialize()
    out = solve(m)
    out["tool_heat_duty_W"] = pyo.value(m.fs.unit.heat_duty[0])
    return out


def fixture_flash() -> dict[str, Any]:
    import pyomo.environ as pyo
    from idaes.models.unit_models import Flash

    m = new_flowsheet()
    m.fs.unit = Flash(property_package=m.fs.props)
    fix_port(m.fs.unit.inlet, EQUIMOLAR, 350.0, P_REF)
    m.fs.unit.deltaP.fix(0)
    # Isothermal flash: the duty is computed, the outlet temperature is specified.
    m.fs.unit.control_volume.properties_out[0].temperature.fix(360.0)
    m.fs.unit.initialize()
    out = solve(m)
    out["tool_vap_flow"] = pyo.value(m.fs.unit.vap_outlet.flow_mol[0])
    out["tool_heat_duty_W"] = pyo.value(m.fs.unit.heat_duty[0])
    return out


def fixture_valve() -> dict[str, Any]:
    import pyomo.environ as pyo
    from idaes.models.unit_models import PressureChanger
    from idaes.models.unit_models.pressure_changer import ThermodynamicAssumption

    m = new_flowsheet()
    # Isenthalpic pressure letdown with a specified outlet pressure. (IDAES's separate `Valve`
    # model adds a flow-coefficient pressure-flow relation on top of the same balance.)
    m.fs.unit = PressureChanger(
        property_package=m.fs.props,
        thermodynamic_assumption=ThermodynamicAssumption.adiabatic,
        compressor=False,
    )
    fix_port(m.fs.unit.inlet, EQUIMOLAR, 300.0, 2.0e5)
    m.fs.unit.outlet.pressure.fix(P_REF)
    m.fs.unit.initialize()
    out = solve(m)
    out["tool_outlet_T_K"] = pyo.value(m.fs.unit.outlet.temperature[0])
    return out


def fixture_pump() -> dict[str, Any]:
    import pyomo.environ as pyo
    from idaes.models.unit_models import PressureChanger
    from idaes.models.unit_models.pressure_changer import ThermodynamicAssumption

    m = new_flowsheet()
    # IDAES pump: work_fluid = (P_out - P_in) * flow_vol_out, work_mechanical = work_fluid / eta,
    # and the energy balance takes work_mechanical.
    m.fs.unit = PressureChanger(
        property_package=m.fs.props,
        thermodynamic_assumption=ThermodynamicAssumption.pump,
        compressor=True,
    )
    fix_port(m.fs.unit.inlet, EQUIMOLAR, 300.0, P_REF)
    m.fs.unit.outlet.pressure.fix(2.0e5)
    m.fs.unit.efficiency_pump.fix(0.75)
    m.fs.unit.initialize()
    out = solve(m)
    out["tool_work_mechanical_W"] = pyo.value(m.fs.unit.work_mechanical[0])
    out["tool_outlet_T_K"] = pyo.value(m.fs.unit.outlet.temperature[0])
    return out


def fixture_conversion_reactor() -> dict[str, Any]:
    import pyomo.environ as pyo
    from idaes.core import MaterialBalanceType
    from idaes.models.properties.modular_properties.base.generic_reaction import (
        GenericReactionParameterBlock,
    )
    from idaes.models.unit_models import StoichiometricReactor

    m = new_flowsheet()
    # A synthetic liquid-phase reaction A -> B; SYN-001 itself has no reaction. Heat of reaction
    # comes from the component enthalpies (formation terms included), so no separate
    # heat_of_reaction method is declared.
    m.fs.rxn = GenericReactionParameterBlock(
        property_package=m.fs.props,
        rate_reactions={"R1": {"stoichiometry": {("Liq", "A"): -1, ("Liq", "B"): 1}}},
        base_units={
            "time": pyo.units.s,
            "length": pyo.units.m,
            "mass": pyo.units.kg,
            "amount": pyo.units.mol,
            "temperature": pyo.units.K,
        },
    )
    m.fs.unit = StoichiometricReactor(
        property_package=m.fs.props,
        reaction_package=m.fs.rxn,
        material_balance_type=MaterialBalanceType.componentTotal,
        has_heat_of_reaction=False,
        has_heat_transfer=True,
        has_pressure_change=False,
    )
    fix_port(m.fs.unit.inlet, EQUIMOLAR, 300.0, P_REF)
    # Conversion of the key reactant A as a specification on the extent.
    conversion = 0.6
    m.fs.unit.conversion_spec = pyo.Constraint(
        expr=m.fs.unit.rate_reaction_extent[0, "R1"]
        == conversion * m.fs.unit.inlet.flow_mol[0] * m.fs.unit.inlet.mole_frac_comp[0, "A"]
    )
    m.fs.unit.outlet.temperature.fix(300.0)  # isothermal: duty computed
    m.fs.unit.rate_reaction_extent[0, "R1"].value = 0.6
    m.fs.unit.initialize()
    out = solve(m)
    out["tool_heat_duty_W"] = pyo.value(m.fs.unit.heat_duty[0])
    return out


def fixture_recycle() -> dict[str, Any]:
    """The SYN-001 loop: feed -> mixer -> heater -> flash -> splitter -> (recycle) mixer."""
    import pyomo.environ as pyo
    from idaes.core.util.initialization import propagate_state
    from idaes.models.unit_models import Flash, Heater, Mixer, MomentumMixingType, Separator
    from idaes.models.unit_models.separator import EnergySplittingType, SplittingType
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

    fix_port(fs.mix.feed, EQUIMOLAR, 300.0, P_REF)
    fs.mix.mixed_state[0].pressure.fix(P_REF)
    fs.heat.outlet.temperature.fix(350.0)
    fs.flash.deltaP.fix(0)
    fs.flash.control_volume.properties_out[0].temperature.fix(360.0)
    fs.split.split_fraction[0, "recycle"].fix(0.5)

    # Sequential initialization with a torn S6 guess, then one simultaneous (EO) solve.
    guess = {"A": 0.2, "B": 0.6, "C": 0.8}
    fix_port(fs.mix.recycle, guess, 360.0, P_REF)
    fs.mix.initialize()
    for c in COMPONENTS:
        fs.mix.recycle.mole_frac_comp[0, c].unfix()
    fs.mix.recycle.flow_mol.unfix()
    fs.mix.recycle.temperature.unfix()
    fs.mix.recycle.pressure.unfix()
    propagate_state(fs.s2)
    fs.heat.initialize()
    propagate_state(fs.s3)
    fs.flash.initialize()
    propagate_state(fs.s5)
    fs.split.initialize()
    out = solve(m)

    def comp(port: Any, c: str) -> float:
        return float(pyo.value(port.flow_mol[0] * port.mole_frac_comp[0, c]))

    # Tool-internal consistency of the converged loop: fresh = vapor product + purge.
    out["overall_component_balance_max_abs_mol_per_s"] = max(
        abs(comp(fs.mix.feed, c) - comp(fs.flash.vap_outlet, c) - comp(fs.split.purge, c))
        for c in COMPONENTS
    )
    out["tool_vap_flow"] = pyo.value(fs.flash.vap_outlet.flow_mol[0])
    out["tool_liq_flow"] = pyo.value(fs.flash.liq_outlet.flow_mol[0])
    return out


FIXTURES: dict[str, Callable[[], dict[str, Any]]] = {
    "mixer": fixture_mixer,
    "splitter": fixture_splitter,
    "heater": fixture_heater,
    "ideal_flash": fixture_flash,
    "valve": fixture_valve,
    "liquid_pump": fixture_pump,
    "conversion_reactor": fixture_conversion_reactor,
    "recycle": fixture_recycle,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", help="write the records to this file as well")
    args = parser.parse_args()

    # IDAES reads its data directory (binary extensions) at import time.
    os.environ.setdefault("IDAES_DATA", str(REPO_ROOT / ".venv-idaes" / "idaes-data"))
    import idaes
    import pyomo

    records: dict[str, Any] = {
        "tool": "idaes-pse",
        "idaes_version": idaes.__version__,
        "pyomo_version": pyomo.__version__,
        "component_set": "SYN-001 constants as user parameters (A, B, C)",
        "fixtures": {},
    }
    failures = 0
    for name, build in FIXTURES.items():
        try:
            rec = build()
            rec["built"] = True
            ok = rec["degrees_of_freedom"] == 0 and rec["termination_condition"] == "optimal"
        except Exception as exc:  # every failure is recorded, none is hidden
            rec = {
                "built": False,
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(limit=4),
            }
            ok = False
        rec["status"] = "RAN" if ok else "FAILED"
        failures += 0 if ok else 1
        records["fixtures"][name] = rec
        print(f"{name:20s} {rec['status']}", file=sys.stderr)

    text = json.dumps(records, indent=2, default=lambda x: None if math.isnan(x) else x)
    print(text)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
