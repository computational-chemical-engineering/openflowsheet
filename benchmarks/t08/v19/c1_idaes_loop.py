"""T08 W3.3 (T08.A62, A63, Q7): Peng-Robinson flashes and the ammonia loop skeleton in IDAES 2.13.

Release spec `docs/derivations/T08-release-spec.md` §7.1 items 6-7, §7.3 (C1), §9 T08.A62-A63,
§12 Q7; brief `docs/briefs/T08-phase3-v19.md` item 2. IDAES is not a dependency of this project:
run this with the Python of a separate environment built from
`spikes/references/idaes-requirements.lock` (idaes-pse 2.13.0) plus the IDAES binary extensions
3.4.2 (`idaes get-extensions --release 3.4.2 --distro ubuntu2204`), exactly as
`scripts/build-reference-envs.sh` builds `.venv-idaes`, but outside this repository::

    IDAES_DATA=<venv>/idaes-data <venv>/bin/python benchmarks/t08/v19/c1_idaes_loop.py \\
        --group-repo /home/frankp/Codes/ammonia_synthesis_reactor \\
        --out benchmarks/t08/v19/c1-idaes.json

Nothing here is imported by `openflowsheet` or by the default test run;
`tests/test_t08_w3_v19_records.py` checks the record's form.

**What it is.** A smoke of the *route* -- does IDAES's modular cubic EoS represent the C1 loop's
nonideal phase split, and can the loop skeleton be built headless and solved -- not a reference.
No number here is compared with anything and none is a registered value (T08.A62: "no comparison
claimed").

**Property data (every value from a file, none typed in from memory).**

* H2, N2, NH3: ``Mw``, ``Tc``, ``Pc``, ``omega``, the five DIPPR-107 ideal-gas heat-capacity
  coefficients and ``dH_f`` from the group repository's
  ``src/reactor/data/properties_database.json`` at the pinned commit (read with ``git show``, so
  the checkout is not touched). The heat capacity is the group's own form
  (``gas_mixture_correlations.py``: ``1e-3 (C1 + C2 ((C3/T)/sinh(C3/T))^2 +
  C4 ((C5/T)/cosh(C5/T))^2)`` J/mol/K), implemented below as a user pure-component method with
  its closed-form integral.
* Ar, CH4 (the inerts §7.3 says a meaningful purge needs): IDAES 2.13's own example parameter sets
  ``modular_properties/examples/ASU_PR.py`` (argon) and ``HC_PR.py`` (methane), read from the
  installed package, with the RPP4 heat-capacity method they use.
* Binary interaction parameters: ``k_ij = 0`` for every pair (no source for the N-H-Ar-CH4 pairs in
  either repository; a stated limitation, not a fit).

**States.** At 100 bar, the top of the pressure range of the kinetics' data (Rossetti et al.,
50-100 bar; see `c1-provenance.json`): a reactor-inlet state at 673.15 K (400 degC, inside the
data's 370-460 degC) that must be single-phase vapour, and a separator state at 268.15 K that must
split into vapour and an NH3-rich liquid. The compositions are illustrative loop compositions chosen
here, not registered states.

**Loop skeleton.** Fresh feed (H2:N2 = 3 with 1 % inerts) -> mixer (with recycle) -> heater to
673.15 K -> StoichiometricReactor (N2 + 3 H2 -> 2 NH3, per-pass N2 conversion fixed) -> cooler to
268.15 K -> adiabatic flash -> liquid NH3 product; vapour -> splitter (purge fraction fixed) ->
recycle. Zero-pressure-drop loop (no compressor; the mixer's outlet pressure is fixed and every unit
has dP = 0). Initialized unit by unit from a guessed recycle, then solved simultaneously by Ipopt.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

PINNED_COMMIT = "a6ee9efc85aee199b51e849467845b59bd5b1800"
GROUP_DB = "src/reactor/data/properties_database.json"
COMPONENTS = ("H2", "N2", "NH3", "Ar", "CH4")
IDAES_EXAMPLE = {"Ar": ("ASU_PR", "argon"), "CH4": ("HC_PR", "methane")}
ELEMENTS = {
    "H2": {"H": 2},
    "N2": {"N": 2},
    "NH3": {"N": 1, "H": 3},
    "Ar": {"Ar": 1},
    "CH4": {"C": 1, "H": 4},
}
PRESSURE = 100.0e5  # Pa
T_REACTOR_IN = 673.15  # K
T_SEPARATOR = 268.15  # K
STATES: dict[str, dict[str, Any]] = {
    "reactor_inlet": {
        "expect": "single-phase vapour",
        "T_K": T_REACTOR_IN,
        "P_Pa": PRESSURE,
        "z": {"H2": 0.70, "N2": 0.235, "NH3": 0.03, "Ar": 0.015, "CH4": 0.02},
    },
    "separator": {
        "expect": "two-phase (vapour + NH3-rich liquid)",
        "T_K": T_SEPARATOR,
        "P_Pa": PRESSURE,
        "z": {"H2": 0.60, "N2": 0.20, "NH3": 0.165, "Ar": 0.015, "CH4": 0.02},
    },
}
FEED: dict[str, Any] = {
    "flow_mol": 1.0,
    "z": {"H2": 0.7425, "N2": 0.2475, "NH3": 1e-4, "Ar": 0.005, "CH4": 0.0049},
}
N2_CONVERSION_PER_PASS = 0.25
PURGE_FRACTION = 0.10
LOCK = "spikes/references/idaes-requirements.lock"


def _group_db(repo: Path, commit: str) -> dict[str, Any]:
    text = subprocess.run(
        ["git", "-C", str(repo), "show", f"{commit}:{GROUP_DB}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    data: dict[str, Any] = json.loads(text)["species_properties"]["data"]
    return data


def _idaes_example(module: str, name: str) -> dict[str, Any]:
    mod: Any = importlib.import_module(
        f"idaes.models.properties.modular_properties.examples.{module}"
    )
    comp: dict[str, Any] = mod.configuration["components"][name]
    return comp


def _dippr107() -> Any:
    """User pure-component method: the group's DIPPR-107 ideal-gas heat capacity (J/kmol/K)."""
    pyo: Any = importlib.import_module("pyomo.environ")
    misc: Any = importlib.import_module("idaes.core.util.misc")
    u = pyo.units

    def params(cobj: Any) -> None:
        if hasattr(cobj, "dippr107_C1"):
            return
        for i in range(1, 6):
            unit = u.J / u.kmol / u.K if i in (1, 2, 4) else u.K
            setattr(cobj, f"dippr107_C{i}", pyo.Var(units=unit, doc=f"DIPPR-107 C{i}"))
            misc.set_param_from_config(cobj, param="dippr107", index=f"C{i}")

    def antiderivative(cobj: Any, temp: Any) -> Any:
        # Integral of C1 + C2 (x/sinh x)^2 + C4 (y/cosh y)^2, x = C3/T, y = C5/T, over T:
        # C1 T + C2 C3 coth(C3/T) - C4 C5 tanh(C5/T)  (J/kmol).
        x = cobj.dippr107_C3 / temp
        y = cobj.dippr107_C5 / temp
        return (
            cobj.dippr107_C1 * temp
            + cobj.dippr107_C2 * cobj.dippr107_C3 * pyo.cosh(x) / pyo.sinh(x)
            - cobj.dippr107_C4 * cobj.dippr107_C5 * pyo.tanh(y)
        )

    class Dippr107:
        class cp_mol_ig_comp:  # noqa: N801 - IDAES's method-name protocol
            @staticmethod
            def build_parameters(cobj: Any) -> None:
                params(cobj)

            @staticmethod
            def return_expression(b: Any, cobj: Any, T: Any) -> Any:  # noqa: N803
                temp = u.convert(T, to_units=u.K)
                x = cobj.dippr107_C3 / temp
                y = cobj.dippr107_C5 / temp
                cp = (
                    cobj.dippr107_C1
                    + cobj.dippr107_C2 * (x / pyo.sinh(x)) ** 2
                    + cobj.dippr107_C4 * (y / pyo.cosh(y)) ** 2
                )
                return u.convert(cp, b.params.get_metadata().derived_units.HEAT_CAPACITY_MOLE)

        class enth_mol_ig_comp:  # noqa: N801
            @staticmethod
            def build_parameters(cobj: Any) -> None:
                params(cobj)
                units = cobj.parent_block().get_metadata().derived_units
                cobj.enth_mol_form_vap_comp_ref = pyo.Var(units=units.ENERGY_MOLE)
                misc.set_param_from_config(cobj, param="enth_mol_form_vap_comp_ref")

            @staticmethod
            def return_expression(b: Any, cobj: Any, T: Any) -> Any:  # noqa: N803
                temp = u.convert(T, to_units=u.K)
                tref = u.convert(b.params.temperature_ref, to_units=u.K)
                units = b.params.get_metadata().derived_units
                dh = u.convert(
                    antiderivative(cobj, temp) - antiderivative(cobj, tref), units.ENERGY_MOLE
                )
                return dh + cobj.enth_mol_form_vap_comp_ref

    return Dippr107


def _wilson_psat(scale: float) -> Any:
    """User ``pressure_sat_comp``: Wilson's estimate ``Pc exp[5.373 (1 + omega)(1 - Tc/T)]``.

    IDAES's generic package calls ``pressure_sat_comp`` only to *estimate* bubble and dew
    temperatures when it initializes a state block (``base/utility.py``); with the cubic EoS and the
    log-fugacity form the phase-equilibrium equations themselves contain fugacities, not Psat.
    The estimate uses only ``Tc``, ``Pc`` and ``omega`` already in the parameter set. ``scale``
    multiplies it, so a run at another scale shows that the converged answer does not depend on
    it.
    """
    pyo: Any = importlib.import_module("pyomo.environ")
    u = pyo.units

    class WilsonPsat:
        class pressure_sat_comp:  # noqa: N801 - IDAES's method-name protocol
            @staticmethod
            def build_parameters(cobj: Any) -> None:
                return None

            @staticmethod
            def return_expression(b: Any, cobj: Any, T: Any, dT: bool = False) -> Any:  # noqa: N803
                temp = u.convert(T, to_units=u.K)
                a = 5.373 * (1 + cobj.omega)
                psat = scale * cobj.pressure_crit * pyo.exp(a * (1 - cobj.temperature_crit / temp))
                if dT:
                    return psat * a * cobj.temperature_crit / temp**2
                return psat

    return WilsonPsat


def property_config(
    db: dict[str, Any],
    psat_scale: float = 1.0,
    light_gases_vapour_only: bool = True,
    vle: str = "SmoothVLE",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """The IDAES GenericParameterBlock configuration and a table of where each value came from.

    ``light_gases_vapour_only`` declares H2, N2, Ar and CH4 vapour-only (no liquid solubility), the
    convention IDAES's own ``HC_PR`` example uses for hydrogen and methane; NH3 is then the one
    component in both phases. ``False`` puts all five in both phases (full PR VLE). ``vle`` is the
    IDAES phase-equilibrium formulation (``SmoothVLE`` or ``CubicComplementarityVLE``).
    """
    pyo: Any = importlib.import_module("pyomo.environ")
    core: Any = importlib.import_module("idaes.core")
    ceos: Any = importlib.import_module("idaes.models.properties.modular_properties.eos.ceos")
    pe: Any = importlib.import_module("idaes.models.properties.modular_properties.phase_equil")
    bd: Any = importlib.import_module(
        "idaes.models.properties.modular_properties.phase_equil.bubble_dew"
    )
    forms: Any = importlib.import_module(
        "idaes.models.properties.modular_properties.phase_equil.forms"
    )
    sd: Any = importlib.import_module(
        "idaes.models.properties.modular_properties.state_definitions"
    )
    u = pyo.units
    dippr = _dippr107()
    psat = _wilson_psat(psat_scale)
    components: dict[str, Any] = {}
    sources: dict[str, Any] = {}
    for name in ("H2", "N2", "NH3"):
        row = db[name]
        components[name] = {
            "type": core.Component,
            "elemental_composition": ELEMENTS[name],
            "enth_mol_ig_comp": dippr,
            "cp_mol_ig_comp": dippr,
            "pressure_sat_comp": psat,
            "phase_equilibrium_form": {("Vap", "Liq"): forms.log_fugacity},
            "parameter_data": {
                "mw": (row["Mw"], u.kg / u.mol),
                "pressure_crit": (row["Pc"], u.Pa),
                "temperature_crit": (row["Tc"], u.K),
                "omega": row["omega"],
                "dippr107": {f"C{i}": row[f"c_p_C{i}"] for i in range(1, 6)},
                "enth_mol_form_vap_comp_ref": (row["dH_f"], u.J / u.mol),
            },
        }
        sources[name] = {
            "source": f"group repository {GROUP_DB} at {PINNED_COMMIT[:7]}",
            "values": {k: row[k] for k in ("Mw", "Tc", "Pc", "omega", "dH_f")}
            | {f"c_p_C{i}": row[f"c_p_C{i}"] for i in range(1, 6)},
            "cp_method": "DIPPR-107 (the group's form), user method in this script",
        }
    for name, (module, key) in IDAES_EXAMPLE.items():
        example = _idaes_example(module, key)
        data = example["parameter_data"]
        components[name] = {
            "type": core.Component,
            "elemental_composition": ELEMENTS[name],
            "enth_mol_ig_comp": example["enth_mol_ig_comp"],
            "pressure_sat_comp": psat,
            "phase_equilibrium_form": {("Vap", "Liq"): forms.log_fugacity},
            "parameter_data": {
                k: data[k]
                for k in (
                    "mw",
                    "pressure_crit",
                    "temperature_crit",
                    "omega",
                    "cp_mol_ig_comp_coeff",
                    "enth_mol_form_vap_comp_ref",
                )
            },
        }
        sources[name] = {
            "source": f"idaes-pse 2.13.0 idaes/models/properties/modular_properties/examples/"
            f"{module}.py, component {key!r}",
            "values": {
                "mw": float(data["mw"][0]),
                "pressure_crit": float(data["pressure_crit"][0]),
                "temperature_crit": float(data["temperature_crit"][0]),
                "omega": float(data["omega"]),
                "enth_mol_form_vap_comp_ref": float(data["enth_mol_form_vap_comp_ref"][0]),
                "cp_mol_ig_comp_coeff": {
                    k: float(v[0]) for k, v in data["cp_mol_ig_comp_coeff"].items()
                },
            },
            "cp_method": example["enth_mol_ig_comp"].__name__,
        }
    kappa = {(i, j): 0.0 for i in COMPONENTS for j in COMPONENTS}
    eos = {
        "equation_of_state": ceos.Cubic,
        "equation_of_state_options": {"type": ceos.CubicType.PR},
    }
    config = {
        "components": components,
        "phases": {
            "Liq": {"type": core.LiquidPhase, **eos},
            "Vap": {"type": core.VaporPhase, **eos},
        },
        "base_units": {
            "time": u.s,
            "length": u.m,
            "mass": u.kg,
            "amount": u.mol,
            "temperature": u.K,
        },
        "state_definition": sd.FTPx,
        "state_bounds": {
            "flow_mol": (0, 1, 100, u.mol / u.s),
            "temperature": (10, 300, 1000, u.K),
            "pressure": (5e4, 1e7, 3e7, u.Pa),
        },
        "pressure_ref": (101325, u.Pa),
        "temperature_ref": (298.15, u.K),
        "phases_in_equilibrium": [("Vap", "Liq")],
        "phase_equilibrium_state": {("Vap", "Liq"): getattr(pe, vle)},
        "bubble_dew_method": bd.LogBubbleDew,
        "parameter_data": {"PR_kappa": kappa},
        "include_enthalpy_of_formation": True,
    }
    sources["binary_interaction"] = {"PR_kappa": "0 for every pair (no source; stated limitation)"}
    sources["pressure_sat_comp"] = (
        "Wilson estimate from Tc, Pc, omega, used by IDAES only to initialize bubble/dew "
        "temperatures; see pr_flash.*.psat_independence"
    )
    if light_gases_vapour_only:
        for name in ("H2", "N2", "Ar", "CH4"):
            components[name]["valid_phase_types"] = core.PhaseType.vaporPhase
            del components[name]["phase_equilibrium_form"]
    sources["phase_representation"] = (
        "H2, N2, Ar, CH4 vapour-only; NH3 in both phases"
        if light_gases_vapour_only
        else "all five components in both phases"
    ) + f"; {vle}"
    return config, sources


def _solver() -> Any:
    pyo: Any = importlib.import_module("pyomo.environ")
    solver = pyo.SolverFactory("ipopt")
    solver.options["max_iter"] = 500
    solver.options["tol"] = 1e-8
    return solver


def _status(result: Any) -> dict[str, str]:
    return {
        "solver_status": str(result.solver.status),
        "termination_condition": str(result.solver.termination_condition),
    }


def _phase_split(state: Any) -> dict[str, Any]:
    pyo: Any = importlib.import_module("pyomo.environ")
    v = pyo.value
    in_liquid = [c for c in COMPONENTS if ("Liq", c) in state.mole_frac_phase_comp]
    out: dict[str, Any] = {
        "phase_fraction": {p: v(state.phase_frac[p]) for p in ("Vap", "Liq")},
        "x_liquid": {
            c: (v(state.mole_frac_phase_comp["Liq", c]) if c in in_liquid else 0.0)
            for c in COMPONENTS
        },
        "y_vapour": {c: v(state.mole_frac_phase_comp["Vap", c]) for c in COMPONENTS},
    }
    # K = y/x for the components present in both phases; None for vapour-only components, and
    # None for every component when one phase is absent (its "composition" is then the incipient
    # phase's at the formulation's equilibrium temperature, not a coexisting phase).
    out["single_phase"] = min(out["phase_fraction"].values()) < 1e-8
    out["K_value"] = {
        c: (
            out["y_vapour"][c] / out["x_liquid"][c]
            if c in in_liquid and not out["single_phase"]
            else None
        )
        for c in COMPONENTS
    }
    # The temperature at which IDAES evaluates the phase equilibrium (SmoothVLE and
    # CubicComplementarityVLE both carry one); equal to T when the formulation is exact there.
    teq = getattr(state, "_teq", None)
    out["T_equilibrium_K"] = v(teq["Vap", "Liq"]) if teq is not None else None
    k_two_phase = [k for k in out["K_value"].values() if k is not None]
    out["trivial_solution"] = bool(k_two_phase) and all(abs(k - 1.0) < 1e-3 for k in k_two_phase)
    out["fug_coeff_vapour"] = {c: v(state.fug_coeff_phase_comp["Vap", c]) for c in COMPONENTS}
    out["fug_coeff_liquid"] = {c: v(state.fug_coeff_phase_comp["Liq", c]) for c in in_liquid}
    return out


def flash_at(config: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    """A Flash unit with inlet = outlet temperature and pressure at ``spec``."""
    pyo: Any = importlib.import_module("pyomo.environ")
    core: Any = importlib.import_module("idaes.core")
    gp: Any = importlib.import_module(
        "idaes.models.properties.modular_properties.base.generic_property"
    )
    units: Any = importlib.import_module("idaes.models.unit_models")
    stats: Any = importlib.import_module("idaes.core.util.model_statistics")
    m = pyo.ConcreteModel()
    m.fs = core.FlowsheetBlock(dynamic=False)
    m.fs.props = gp.GenericParameterBlock(**config)
    m.fs.flash = units.Flash(property_package=m.fs.props)
    m.fs.flash.inlet.flow_mol.fix(1.0)
    m.fs.flash.inlet.temperature.fix(spec["T_K"])
    m.fs.flash.inlet.pressure.fix(spec["P_Pa"])
    for c, z in spec["z"].items():
        m.fs.flash.inlet.mole_frac_comp[0, c].fix(z)
    m.fs.flash.control_volume.properties_out[0].temperature.fix(spec["T_K"])
    m.fs.flash.deltaP.fix(0.0)
    dof = stats.degrees_of_freedom(m)
    try:
        m.fs.flash.initialize(outlvl=40)
        init_outcome = "ok"
    except Exception as exc:  # recorded; the solve is still attempted from where it stopped
        init_outcome = f"{type(exc).__name__}: {exc}"
    result = _solver().solve(m)
    return {
        "spec": spec,
        "degrees_of_freedom": dof,
        "initialization": init_outcome,
        **_status(result),
        "heat_duty_W": pyo.value(m.fs.flash.heat_duty[0]),
        **_phase_split(m.fs.flash.control_volume.properties_out[0]),
    }


def loop_skeleton(config: dict[str, Any]) -> dict[str, Any]:
    """Build, initialize and solve the zero-dP loop skeleton once."""
    pyo: Any = importlib.import_module("pyomo.environ")
    network: Any = importlib.import_module("pyomo.network")
    core: Any = importlib.import_module("idaes.core")
    gp: Any = importlib.import_module(
        "idaes.models.properties.modular_properties.base.generic_property"
    )
    gr: Any = importlib.import_module(
        "idaes.models.properties.modular_properties.base.generic_reaction"
    )
    units: Any = importlib.import_module("idaes.models.unit_models")
    mixer_mod: Any = importlib.import_module("idaes.models.unit_models.mixer")
    init: Any = importlib.import_module("idaes.core.util.initialization")
    stats: Any = importlib.import_module("idaes.core.util.model_statistics")
    u = pyo.units
    v = pyo.value

    m = pyo.ConcreteModel()
    m.fs = core.FlowsheetBlock(dynamic=False)
    m.fs.props = gp.GenericParameterBlock(**config)
    m.fs.rxn = gr.GenericReactionParameterBlock(
        property_package=m.fs.props,
        base_units={"time": u.s, "length": u.m, "mass": u.kg, "amount": u.mol, "temperature": u.K},
        rate_reactions={
            "R1": {"stoichiometry": {("Vap", "N2"): -1, ("Vap", "H2"): -3, ("Vap", "NH3"): 2}}
        },
    )
    fs = m.fs
    fs.feed = units.Feed(property_package=fs.props)
    fs.mixer = units.Mixer(
        property_package=fs.props,
        inlet_list=["fresh", "recycle"],
        momentum_mixing_type=mixer_mod.MomentumMixingType.none,
    )
    fs.heater = units.Heater(property_package=fs.props, has_pressure_change=True)
    fs.reactor = units.StoichiometricReactor(
        property_package=fs.props,
        reaction_package=fs.rxn,
        has_heat_transfer=True,
        has_pressure_change=True,
    )
    fs.cooler = units.Heater(property_package=fs.props, has_pressure_change=True)
    fs.flash = units.Flash(property_package=fs.props)
    fs.splitter = units.Separator(
        property_package=fs.props, outlet_list=["purge", "recycle"], num_outlets=2
    )
    fs.product = units.Product(property_package=fs.props)
    fs.purge = units.Product(property_package=fs.props)

    fs.s01 = network.Arc(source=fs.feed.outlet, destination=fs.mixer.fresh)
    fs.s02 = network.Arc(source=fs.mixer.outlet, destination=fs.heater.inlet)
    fs.s03 = network.Arc(source=fs.heater.outlet, destination=fs.reactor.inlet)
    fs.s04 = network.Arc(source=fs.reactor.outlet, destination=fs.cooler.inlet)
    fs.s05 = network.Arc(source=fs.cooler.outlet, destination=fs.flash.inlet)
    fs.s06 = network.Arc(source=fs.flash.liq_outlet, destination=fs.product.inlet)
    fs.s07 = network.Arc(source=fs.flash.vap_outlet, destination=fs.splitter.inlet)
    fs.s08 = network.Arc(source=fs.splitter.purge, destination=fs.purge.inlet)
    fs.s09 = network.Arc(source=fs.splitter.recycle, destination=fs.mixer.recycle)
    pyo.TransformationFactory("network.expand_arcs").apply_to(m)

    fs.feed.flow_mol.fix(FEED["flow_mol"])
    fs.feed.temperature.fix(T_REACTOR_IN)
    fs.feed.pressure.fix(PRESSURE)
    for c, z in FEED["z"].items():
        fs.feed.mole_frac_comp[0, c].fix(z)
    fs.mixer.outlet.pressure.fix(PRESSURE)
    fs.heater.outlet.temperature.fix(T_REACTOR_IN)
    fs.heater.deltaP.fix(0.0)
    inlet = fs.reactor.control_volume.properties_in[0]
    fs.reactor_conversion = pyo.Constraint(
        expr=fs.reactor.rate_reaction_extent[0, "R1"]
        == N2_CONVERSION_PER_PASS * inlet.flow_mol * inlet.mole_frac_comp["N2"]
    )
    fs.reactor.outlet.temperature.fix(T_REACTOR_IN)
    fs.reactor.deltaP.fix(0.0)
    fs.cooler.outlet.temperature.fix(T_SEPARATOR)
    fs.cooler.deltaP.fix(0.0)
    fs.flash.heat_duty.fix(0.0)
    fs.flash.deltaP.fix(0.0)
    fs.splitter.split_fraction[0, "purge"].fix(PURGE_FRACTION)
    dof = stats.degrees_of_freedom(m)

    # Sequential initialization from a guessed recycle (the tear), then one simultaneous solve.
    guess = {"H2": 0.62, "N2": 0.21, "NH3": 0.02, "Ar": 0.07, "CH4": 0.08}
    fs.mixer.recycle.flow_mol.fix(3.0)
    fs.mixer.recycle.temperature.fix(T_SEPARATOR)
    fs.mixer.recycle.pressure.fix(PRESSURE)
    for c, z in guess.items():
        fs.mixer.recycle.mole_frac_comp[0, c].fix(z)
    fs.feed.initialize(outlvl=40)
    init.propagate_state(arc=fs.s01)
    fs.mixer.initialize(outlvl=40)
    for arc, unit in (
        (fs.s02, fs.heater),
        (fs.s03, fs.reactor),
        (fs.s04, fs.cooler),
        (fs.s05, fs.flash),
        (fs.s07, fs.splitter),
    ):
        init.propagate_state(arc=arc)
        unit.initialize(outlvl=40)
    for arc, unit in ((fs.s06, fs.product), (fs.s08, fs.purge)):
        init.propagate_state(arc=arc)
        unit.initialize(outlvl=40)
    fs.mixer.recycle.unfix()
    dof_after_unfix = stats.degrees_of_freedom(m)
    result = _solver().solve(m)

    def stream(state: Any) -> dict[str, Any]:
        return {
            "flow_mol": v(state.flow_mol),
            "T_K": v(state.temperature),
            "P_Pa": v(state.pressure),
            "z": {c: v(state.mole_frac_comp[c]) for c in COMPONENTS},
        }

    def element_flows(state: Any) -> dict[str, float]:
        out: dict[str, float] = {}
        for c in COMPONENTS:
            for el, n in ELEMENTS[c].items():
                out[el] = out.get(el, 0.0) + n * v(state.flow_mol * state.mole_frac_comp[c])
        return out

    feed = fs.feed.properties[0]
    product = fs.product.properties[0]
    purge = fs.purge.properties[0]
    e_in = element_flows(feed)
    e_out = {
        el: element_flows(product).get(el, 0.0) + element_flows(purge).get(el, 0.0) for el in e_in
    }
    return {
        "degrees_of_freedom": {"specified": dof, "after_unfixing_tear_guess": dof_after_unfix},
        **_status(result),
        "specification": {
            "fresh_feed": FEED,
            "pressure_Pa_everywhere": PRESSURE,
            "reactor_inlet_T_K": T_REACTOR_IN,
            "reactor_outlet_T_K": T_REACTOR_IN,
            "reactor": "StoichiometricReactor, extent = "
            f"{N2_CONVERSION_PER_PASS} x N2 inlet flow (per-pass N2 conversion)",
            "cooler_outlet_T_K": T_SEPARATOR,
            "flash": "adiabatic, dP = 0",
            "purge_split_fraction": PURGE_FRACTION,
            "tear_guess": {"flow_mol": 3.0, "T_K": T_SEPARATOR, "z": guess},
        },
        "streams": {
            "fresh_feed": stream(feed),
            "reactor_inlet": stream(fs.reactor.control_volume.properties_in[0]),
            "reactor_outlet": stream(fs.reactor.control_volume.properties_out[0]),
            "liquid_product": stream(product),
            "purge": stream(purge),
            "recycle": stream(fs.splitter.recycle_state[0]),
        },
        "separator_phase_split": _phase_split(fs.flash.control_volume.properties_out[0]),
        "duties_W": {
            "heater": v(fs.heater.heat_duty[0]),
            "reactor": v(fs.reactor.heat_duty[0]),
            "cooler": v(fs.cooler.heat_duty[0]),
        },
        "reaction_extent_mol_s": v(fs.reactor.rate_reaction_extent[0, "R1"]),
        # Isothermal reactor at 673.15 K: duty / extent is the heat of reaction there, from the
        # formation enthalpies and heat capacities of the property route.
        "reactor_duty_per_extent_J_mol": v(fs.reactor.heat_duty[0])
        / v(fs.reactor.rate_reaction_extent[0, "R1"]),
        "element_balance_in_minus_out_mol_s": {el: e_in[el] - e_out[el] for el in e_in},
        "element_flows_in_mol_s": e_in,
    }


#: The group's catalyst-volume conversion, ``rho_b / rho_c = Dcat (1 - eps)`` with ReactorConfig's
#: defaults at the pinned commit (``Dcat = 1/3``, ``eps = 0.4``; ``config.py``), and its unit factor
#: ``1000 / 3600`` (mol h^-1 L_cat^-1 -> mol s^-1 m_cat^-3); ``ammonia_synthesis_kinetics.py:185``.
CATALYST_FRACTION = (1.0 / 3.0) * (1.0 - 0.4)
CSTR_VOLUME_M3 = 1.0e-3


def _rossetti_rate_form() -> Any:
    """User IDAES rate form: the group's ``AmmoniaSynthesisKinetics`` rate law (Q7).

    The expression is transcribed from ``src/reactor/ammonia_synthesis_kinetics.py`` (lines
    185-375 at the pinned commit): ``K_eq``, ``k_f``, ``K_H2``, ``K_NH3`` and the rate with its
    exponents, with activities in bar. One thing differs by construction: the activities are IDAES's
    Peng-Robinson vapour fugacities, not the group's fugacity-coefficient correlations, so no number
    here is the group model's.
    """
    pyo: Any = importlib.import_module("pyomo.environ")
    u = pyo.units
    r_cal = 8.314462618 / 4.184  # the group's Rc = constants.R / constants.calorie

    class RossettiRate:
        @staticmethod
        def build_parameters(rblock: Any, config: Any) -> None:
            return None

        @staticmethod
        def return_expression(b: Any, rblock: Any, r_idx: Any, T: Any) -> Any:  # noqa: N803
            temp = pyo.units.convert(T, to_units=u.K) / u.K
            state = b.state_ref
            act = {
                j: pyo.units.convert(state.fug_phase_comp["Vap", j], to_units=u.bar) / u.bar
                for j in ("H2", "N2", "NH3")
            }
            k_eq = pyo.exp(
                -2.691122 * pyo.log(temp)
                + pyo.log(10.0)
                * ((-5.519265e-5 + 1.848863e-7 * temp) * temp + 2001.6 / temp + 2.6899)
            )
            k_f = 9.02e8 * pyo.exp(-23000.0 / (r_cal * temp))
            k_h2 = pyo.exp(-13.6 / r_cal + 9000.0 / (r_cal * temp))
            k_nh3 = pyo.exp(-8.3 / r_cal + 7000.0 / (r_cal * temp))
            driving = act["N2"] ** 0.5 * act["H2"] ** 0.375 / act["NH3"] ** 0.25 - act[
                "NH3"
            ] ** 0.75 / (k_eq * act["H2"] ** 1.125)
            inhibition = 1.0 + k_h2 * act["H2"] ** 0.3 + k_nh3 * act["NH3"] ** 0.2
            rate = k_f * 1000.0 / 3600.0 * CATALYST_FRACTION * driving / inhibition
            return rate * u.mol / u.m**3 / u.s

    return RossettiRate


def kinetic_cstr(config: dict[str, Any]) -> dict[str, Any]:
    """Q7: an isothermal CSTR on the PR package with the group's rate law as a user rate form."""
    pyo: Any = importlib.import_module("pyomo.environ")
    core: Any = importlib.import_module("idaes.core")
    gp: Any = importlib.import_module(
        "idaes.models.properties.modular_properties.base.generic_property"
    )
    gr: Any = importlib.import_module(
        "idaes.models.properties.modular_properties.base.generic_reaction"
    )
    units: Any = importlib.import_module("idaes.models.unit_models")
    stats: Any = importlib.import_module("idaes.core.util.model_statistics")
    u = pyo.units
    v = pyo.value
    spec = STATES["reactor_inlet"]
    m = pyo.ConcreteModel()
    m.fs = core.FlowsheetBlock(dynamic=False)
    m.fs.props = gp.GenericParameterBlock(**config)
    m.fs.rxn = gr.GenericReactionParameterBlock(
        property_package=m.fs.props,
        base_units={"time": u.s, "length": u.m, "mass": u.kg, "amount": u.mol, "temperature": u.K},
        rate_reactions={
            "R1": {
                "stoichiometry": {("Vap", "N2"): -1, ("Vap", "H2"): -3, ("Vap", "NH3"): 2},
                "rate_form": _rossetti_rate_form(),
            }
        },
    )
    m.fs.cstr = units.CSTR(
        property_package=m.fs.props,
        reaction_package=m.fs.rxn,
        has_heat_transfer=True,
        has_pressure_change=True,
    )
    c = m.fs.cstr
    c.inlet.flow_mol.fix(1.0)
    c.inlet.temperature.fix(spec["T_K"])
    c.inlet.pressure.fix(spec["P_Pa"])
    for j, z in spec["z"].items():
        c.inlet.mole_frac_comp[0, j].fix(z)
    c.volume.fix(CSTR_VOLUME_M3)
    c.outlet.temperature.fix(spec["T_K"])
    c.deltaP.fix(0.0)
    dof = stats.degrees_of_freedom(m)
    try:
        c.initialize(outlvl=40)
        init_outcome = "ok"
    except Exception as exc:  # recorded; the solve is still attempted
        init_outcome = f"{type(exc).__name__}: {exc}"
    result = _solver().solve(m)
    state_in = c.control_volume.properties_in[0]
    state_out = c.control_volume.properties_out[0]
    n2_in = v(state_in.flow_mol * state_in.mole_frac_comp["N2"])
    return {
        "unit": "idaes.models.unit_models.CSTR, isothermal, dP = 0",
        "rate_form": "user class transcribing the group's AmmoniaSynthesisKinetics rate law; "
        "activities = PR vapour fugacities in bar (not the group's correlations)",
        "catalyst_fraction_rho_b_over_rho_c": CATALYST_FRACTION,
        "volume_m3": CSTR_VOLUME_M3,
        "inlet": spec,
        "degrees_of_freedom": dof,
        "initialization": init_outcome,
        **_status(result),
        "extent_mol_s": v(c.control_volume.rate_reaction_extent[0, "R1"]),
        "N2_conversion": v(c.control_volume.rate_reaction_extent[0, "R1"]) / n2_in,
        "outlet_y_NH3": v(state_out.mole_frac_comp["NH3"]),
        "outlet_vapour_fraction": v(state_out.phase_frac["Vap"]),
    }


def _ok(block: dict[str, Any]) -> bool:
    return "error" not in block and block.get("termination_condition") == "optimal"


def representability(record: dict[str, Any]) -> list[dict[str, str]]:
    """T06-form table (unit, method, reaction form, Y/N/not_built, reason) from this run."""
    loop = record["loop_skeleton"]
    flash = record["pr_flash"]
    full = flash["full_vle_all_components_both_phases"]
    light = flash["light_gases_vapour_only"]
    loop_yn = "Y" if _ok(loop) else "N"
    full_ok = all(
        _ok(full[s]) and not full[s]["trivial_solution"] for s in ("reactor_inlet", "separator")
    )
    light_ok = all(_ok(light[s]) for s in ("reactor_inlet", "separator"))
    q7 = record["kinetic_reactor_q7"]
    rows = [
        ("fresh feed", "Feed", "-", loop_yn, "built and solved in loop_skeleton"),
        (
            "recycle mixer",
            "Mixer, MomentumMixingType.none, outlet pressure fixed",
            "-",
            loop_yn,
            "zero-dP loop convention (no compressor); built and solved in loop_skeleton",
        ),
        ("reactor preheater", "Heater, outlet T, dP = 0", "-", loop_yn, "loop_skeleton"),
        (
            "reactor (stoichiometric)",
            "StoichiometricReactor + user constraint extent = X * N2 inlet",
            "N2 + 3 H2 -> 2 NH3, fixed per-pass conversion; heat of reaction from formation "
            "enthalpies",
            loop_yn,
            "loop_skeleton; see reactor_duty_per_extent_J_mol",
        ),
        (
            "reactor (kinetic, the group's rate law)",
            "CSTR + user rate_form class (GenericReactionParameterBlock)",
            "Rossetti-type rate as in the group's AmmoniaSynthesisKinetics; activities = PR "
            "vapour fugacities",
            "Y" if _ok(q7) else "N",
            "kinetic_reactor_q7: built and solved once (CSTR only; a PFR was not built; the "
            "activities are IDAES's PR fugacities, not the group's correlations)",
        ),
        (
            "reactor (equilibrium)",
            "EquilibriumReactor",
            "K_a of the group's kinetics (log10 form)",
            "not_built",
            "not built in this smoke: IDAES's built-in equilibrium-constant forms do not include "
            "this K_a expression, so it would need a user equilibrium_constant class (the same "
            "mechanism as the rate form above)",
        ),
        ("cooler", "Heater, outlet T, dP = 0", "-", loop_yn, "loop_skeleton"),
        (
            "HP separator, PR, light gases vapour-only",
            "Flash, adiabatic, SmoothVLE; H2/N2/Ar/CH4 vapour-only (IDAES HC_PR convention)",
            "-",
            "Y" if light_ok and loop_yn == "Y" else "N",
            "pr_flash.light_gases_vapour_only (both states) and loop_skeleton; no gas "
            "solubility in the liquid",
        ),
        (
            "HP separator, full PR VLE (gases dissolve in liquid NH3)",
            "Flash, SmoothVLE; all five components in both phases",
            "-",
            "Y" if full_ok else "N",
            "pr_flash.full_vle_all_components_both_phases: with IDAES's default initialization "
            "the reactor-inlet state ends on the trivial solution (all K = 1) and the separator "
            "state ends unbounded on the trivial solution; not resolved in this smoke",
        ),
        (
            "purge",
            "Separator, total-flow split, purge fraction fixed",
            "-",
            loop_yn,
            "loop_skeleton",
        ),
        (
            "recycle closure",
            "Arcs, simultaneous (EO) solve after sequential initialization from a tear guess",
            "-",
            loop_yn,
            "loop_skeleton",
        ),
        (
            "recycle compressor",
            "PressureChanger (compressor)",
            "-",
            "not_built",
            "the skeleton uses the zero-dP loop convention; not built here",
        ),
    ]
    keys = ("unit", "idaes_model_and_method", "reaction_form", "representable", "reason")
    return [dict(zip(keys, row, strict=True)) for row in rows]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--group-repo", type=Path, required=True)
    parser.add_argument("--commit", default=PINNED_COMMIT)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[3]

    db = _group_db(args.group_repo.resolve(), args.commit)
    config, sources = property_config(db)
    pyo: Any = importlib.import_module("pyomo.environ")
    ipopt = pyo.SolverFactory("ipopt")
    idaes_data = os.environ.get("IDAES_DATA", "")
    record: dict[str, Any] = {
        "record": "t08-v19-c1-idaes",
        "version": 1,
        "assertions": ["T08.A62", "T08.A63", "Q7"],
        "status": "measured",
        "judged": False,
        "comparison_claimed": False,
        "environment": {
            "kind": "separate venv outside this repository, from "
            f"{LOCK} (--require-hashes), never the project .venv",
            "lock_sha256": hashlib.sha256((repo_root / LOCK).read_bytes()).hexdigest(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": {
                p: importlib.metadata.version(p) for p in ("idaes-pse", "pyomo", "numpy", "scipy")
            },
            "ipopt_version": ".".join(str(x) for x in ipopt.version()),
            "idaes_extensions": "3.4.2 ubuntu2204 (idaes get-extensions)",
            "idaes_extension_sha256": {
                name: hashlib.sha256((Path(idaes_data) / "bin" / name).read_bytes()).hexdigest()
                for name in (
                    "idaes-lib-ubuntu2204-x86_64.tar.gz",
                    "idaes-solvers-ubuntu2204-x86_64.tar.gz",
                )
            }
            if idaes_data
            else None,
        },
        "property_route": {
            "method": "Peng-Robinson cubic EoS in both phases (IDAES modular Cubic, "
            "CubicType.PR), log-fugacity phase equilibrium, SmoothVLE, LogBubbleDew, FTPx",
            "components": list(COMPONENTS),
            "group_repository_commit": args.commit,
            "sources": sources,
        },
    }
    flashes: dict[str, Any] = {}
    routes: dict[str, dict[str, Any]] = {
        "full_vle_all_components_both_phases": {"light_gases_vapour_only": False},
        "light_gases_vapour_only": {"light_gases_vapour_only": True},
        "light_gases_vapour_only_CubicComplementarityVLE": {
            "light_gases_vapour_only": True,
            "vle": "CubicComplementarityVLE",
        },
    }
    for route, options in routes.items():
        route_config, route_sources = property_config(db, **options)
        flashes[route] = {"phase_representation": route_sources["phase_representation"]}
        for name, spec in STATES.items():
            try:
                flashes[route][name] = flash_at(route_config, spec)
            except Exception as exc:  # recorded: the failure is the finding
                flashes[route][name] = {"spec": spec, "error": f"{type(exc).__name__}: {exc}"}
    # The Psat estimate only seeds IDAES's bubble/dew initialization: rerun the primary route with
    # it halved and record how much the converged answer moves.
    config_half, _ = property_config(db, psat_scale=0.5)
    for name, spec in STATES.items():
        base = flashes["light_gases_vapour_only"][name]
        if "error" in base:
            continue
        other = flash_at(config_half, spec)
        base["psat_independence"] = {
            "rerun_with_psat_estimate_scaled_by": 0.5,
            "termination_condition": other["termination_condition"],
            "abs_diff_vapour_fraction": abs(
                other["phase_fraction"]["Vap"] - base["phase_fraction"]["Vap"]
            ),
            "max_abs_diff_y_vapour": max(
                abs(other["y_vapour"][c] - base["y_vapour"][c]) for c in COMPONENTS
            ),
        }
    record["pr_flash"] = flashes
    try:
        record["loop_skeleton"] = loop_skeleton(config)
    except Exception as exc:
        record["loop_skeleton"] = {"error": f"{type(exc).__name__}: {exc}"}
    try:
        record["kinetic_reactor_q7"] = kinetic_cstr(config)
    except Exception as exc:
        record["kinetic_reactor_q7"] = {"error": f"{type(exc).__name__}: {exc}"}
    record["representability"] = representability(record)
    args.out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
