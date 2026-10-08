"""M01 WO-5 (M01.A37): IDAES 2.13 conformance of the C1 Peng-Robinson method on M01's records.

Specification: ``docs/derivations/M01-spec.md`` §9.8 (M01.A37), §13 (the evidence catalogue's
"IDAES conformance" row) and §14 WO-5. IDAES is not a dependency of this project: run this with
the Python of the environment ``scripts/build-reference-envs.sh idaes`` builds (``.venv-idaes``:
idaes-pse 2.13.0 from ``spikes/references/idaes-requirements.lock``, ``--require-hashes``, plus
the IDAES binary extensions 3.4.2 with their bundled Ipopt), never the project ``.venv``::

    .venv-idaes/bin/python -I benchmarks/m01/idaes_conformance.py

``IDAES_DATA`` defaults to ``<venv>/idaes-data``. The script writes
``benchmarks/m01/idaes-conformance.json`` (``--out`` to write elsewhere). It imports nothing from
``openflowsheet`` and compares nothing: the record holds IDAES's numbers and the environment's
hashes, and ``tests/test_m01_idaes_conformance.py`` compares them with the provider ``pr-c1-v1``
in the default gate at A37's tolerances.

**Property block.** T08's vapour-only block (``benchmarks/t08/v19/c1_idaes_loop.py``,
``property_config(light_gases_vapour_only=True)``) rebuilt on M01's records: IDAES's modular cubic
EoS (``Cubic``, ``CubicType.PR``) in both phases, H2, N2, Ar and CH4 vapour-only, NH3 in both,
log-fugacity phase equilibrium, ``SmoothVLE``, ``LogBubbleDew``, FTPx, ``k_ij = 0`` for every
pair (ADR 0026 D3). Every component parameter comes from ``benchmarks/m01/components.yaml``:
``T_c``, ``P_c``, ``omega``, the molar mass, the standard formation enthalpy and the NASA-7
low-range ``b_0..b_4`` of ``c_p^ig/R = sum_k b_k (T/1000 K)^k``, implemented below as a user
pure-component method with its closed-form integral. ``pressure_sat_comp`` is T08's Wilson
estimate, which IDAES uses only to initialize bubble and dew temperatures.

**States** (``benchmarks/m01/reference_values.yaml``, ``closed_form``; transcribed below, the gate
test checks the transcription bit for bit):

* V1, V2 (VAPOR) and L1 (LIQUID, pure NH3): one IDAES state block on a one-phase variant of the
  block (the same components, records and EoS; only the phase of the request; L1's block holds
  NH3 alone, the composition of a LIQUID request under the convention). The state variables are
  fixed at (T, P, z = n / sum n) and ``mole_frac_phase_comp`` is set to z, the value the one-phase
  FTPx constraints give; Z, ln phi and h are then IDAES's own expressions (its ``cubic_roots``
  external function for Z), evaluated, not solved.
* F1, F11: T08's flash (``Flash``, outlet T = inlet T, dP = 0, inlet flow 1 mol/s) on the
  two-phase block, initialized by IDAES and solved by Ipopt with T08's options (``tol = 1e-8``).

The reader of ``components.yaml`` is a narrow line reader for the file's block layout (the IDAES
lock carries no YAML parser); it fails on any layout it does not expect, and the record echoes
every value it read, which the gate test compares with the project's own loader exactly.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
import platform
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
RECORDS = HERE / "components.yaml"
REFERENCE = HERE / "reference_values.yaml"
OUT = HERE / "idaes-conformance.json"
LOCK = "spikes/references/idaes-requirements.lock"
EXTENSIONS = {"release": "3.4.2", "distro": "ubuntu2204"}
EXTENSION_TARBALLS = (
    "idaes-lib-ubuntu2204-x86_64.tar.gz",
    "idaes-solvers-ubuntu2204-x86_64.tar.gz",
)
PACKAGES = ("idaes-pse", "pyomo", "numpy", "scipy")
COMPONENTS = ("H2", "N2", "NH3", "Ar", "CH4")
LIGHT_GASES = ("H2", "N2", "Ar", "CH4")
#: The records' gas constant (exact SI; the header of components.yaml), used for c_p^ig = R sum b_k
#: tau^k. IDAES's EoS uses its own ``Constants.gas_constant``, recorded in the output.
R_RECORDS = 8.31446261815324
T_REF = 298.15
PARAMETERS = (
    "critical_temperature",
    "critical_pressure",
    "acentric_factor",
    "standard_formation_enthalpy",
    *(f"ideal_gas_cp_b{k}" for k in range(5)),
    "ideal_gas_cp_lower_temperature",
    "ideal_gas_cp_upper_temperature",
)
#: The registered states of M01.A37, transcribed from reference_values.yaml ``closed_form``.
PHASE_STATES: dict[str, dict[str, Any]] = {
    "V1": {
        "phase": "VAPOR",
        "T_K": 673.15,
        "P_Pa": 10000000.0,
        "n_mol_s": [0.7, 0.235, 0.03, 0.015, 0.02],
    },
    "V2": {
        "phase": "VAPOR",
        "T_K": 268.15,
        "P_Pa": 10000000.0,
        "n_mol_s": [
            0.6743819512868283,
            0.22479398376227613,
            0.061485117792505664,
            0.01685954878217071,
            0.022479398376227616,
        ],
    },
    "L1": {
        "phase": "LIQUID",
        "T_K": 268.15,
        "P_Pa": 10000000.0,
        "n_mol_s": [0.0, 0.0, 1.0, 0.0, 0.0],
    },
}
FLASH_STATES: dict[str, dict[str, Any]] = {
    "F1": {"T_K": 268.15, "P_Pa": 10000000.0, "n_mol_s": [0.6, 0.2, 0.165, 0.015, 0.02]},
    "F11": {"T_K": 250.0, "P_Pa": 25000000.0, "n_mol_s": [0.6, 0.2, 0.165, 0.015, 0.02]},
}
SOLVER_OPTIONS = {"max_iter": 500, "tol": 1e-8}


# -- the records ---------------------------------------------------------------------------------

_ID = re.compile(r"^  - id: (\S+)$")
_KEY4 = re.compile(r"^    (\w+):\s*$")
_KEY6 = re.compile(r"^      (\w+):\s*$")
_VALUE6 = re.compile(r"^      value: (\S+)$")
_VALUE8 = re.compile(r"^        value: (\S+)$")


def read_records(path: Path) -> dict[str, dict[str, float]]:
    """``{id: {"molar_mass": ..., <PARAMETERS>: ...}}`` in file order, from components.yaml's lines.

    Reads ``components[*].molecular_weight.value`` and ``components[*].parameters.<name>.value``
    at the indentation components.yaml uses; raises on a duplicate, a missing value, an unexpected
    parameter or a component order other than ``COMPONENTS``.
    """
    records: dict[str, dict[str, float]] = {}
    current: dict[str, float] | None = None
    key4 = key6 = None
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if line.startswith("#") or not line.strip():
            continue
        if not line.startswith("  "):
            current = None  # a top-level key ends the components list
            continue
        if match := _ID.match(line):
            cid = match.group(1)
            if cid in records:
                raise ValueError(f"line {number}: duplicate component {cid}")
            current = records[cid] = {}
            key4 = key6 = None
            continue
        if current is None:
            continue
        if match := _KEY4.match(line):
            key4, key6 = match.group(1), None
        elif match := _KEY6.match(line):
            key6 = match.group(1)
        elif (match := _VALUE6.match(line)) and key4 == "molecular_weight":
            _store(current, "molar_mass", match.group(1), number)
        elif (match := _VALUE8.match(line)) and key4 == "parameters":
            if key6 not in PARAMETERS:
                raise ValueError(f"line {number}: unexpected parameter {key6!r}")
            _store(current, str(key6), match.group(1), number)
    if tuple(records) != COMPONENTS:
        raise ValueError(f"component order {list(records)} is not {list(COMPONENTS)}")
    for cid, values in records.items():
        missing = {"molar_mass", *PARAMETERS} - set(values)
        if missing:
            raise ValueError(f"{cid}: missing {sorted(missing)}")
    return records


def _store(values: dict[str, float], name: str, text: str, number: int) -> None:
    if name in values:
        raise ValueError(f"line {number}: duplicate value for {name}")
    value = float(text)
    if not math.isfinite(value):
        raise ValueError(f"line {number}: {name} = {text!r} is not a finite number")
    values[name] = value


# -- the IDAES property block --------------------------------------------------------------------


def _nasa_cp() -> Any:
    """User pure-component method: c_p^ig = R sum_k b_k tau^k, tau = T / 1000 K (the records' form).

    h^ig = Delta_f H + 1000 R sum_k b_k (tau^(k+1) - tau_ref^(k+1)) / (k+1), the closed-form
    integral from T_ref = 298.15 K (the PR-C1-ref-v1 datum), the formation enthalpy included as
    IDAES's own RPP4 method includes it (``include_enthalpy_of_formation``).
    """
    pyo: Any = importlib.import_module("pyomo.environ")
    misc: Any = importlib.import_module("idaes.core.util.misc")
    u = pyo.units

    def params(cobj: Any) -> None:
        if hasattr(cobj, "nasa_cp_b0"):
            return
        for k in range(5):
            setattr(cobj, f"nasa_cp_b{k}", pyo.Var(units=u.dimensionless, doc=f"b_{k}"))
            misc.set_param_from_config(cobj, param="nasa_cp", index=f"b{k}")

    def tau(temperature: Any) -> Any:
        return u.convert(temperature, to_units=u.K) / (1000.0 * u.K)

    class NasaCp:
        class cp_mol_ig_comp:  # noqa: N801 - IDAES's method-name protocol
            @staticmethod
            def build_parameters(cobj: Any) -> None:
                params(cobj)

            @staticmethod
            def return_expression(b: Any, cobj: Any, T: Any) -> Any:  # noqa: N803
                t = tau(T)
                coeff = [getattr(cobj, f"nasa_cp_b{k}") for k in range(5)]
                cp = R_RECORDS * u.J / u.mol / u.K * sum(coeff[k] * t**k for k in range(5))
                return u.convert(cp, b.params.get_metadata().derived_units.HEAT_CAPACITY_MOLE)

        class enth_mol_ig_comp:  # noqa: N801
            @staticmethod
            def build_parameters(cobj: Any) -> None:
                params(cobj)
                if cobj.parent_block().config.include_enthalpy_of_formation:
                    units = cobj.parent_block().get_metadata().derived_units
                    cobj.enth_mol_form_vap_comp_ref = pyo.Var(units=units.ENERGY_MOLE)
                    misc.set_param_from_config(cobj, param="enth_mol_form_vap_comp_ref")

            @staticmethod
            def return_expression(b: Any, cobj: Any, T: Any) -> Any:  # noqa: N803
                units = b.params.get_metadata().derived_units
                t, t0 = tau(T), tau(b.params.temperature_ref)
                coeff = [getattr(cobj, f"nasa_cp_b{k}") for k in range(5)]
                integral = sum(
                    coeff[k] * (t ** (k + 1) - t0 ** (k + 1)) / (k + 1) for k in range(5)
                )
                dh = u.convert(1000.0 * R_RECORDS * u.J / u.mol * integral, units.ENERGY_MOLE)
                if b.params.config.include_enthalpy_of_formation:
                    return dh + cobj.enth_mol_form_vap_comp_ref
                return dh

    return NasaCp


def _wilson_psat() -> Any:
    """T08's user ``pressure_sat_comp``: Wilson's ``P_c exp[5.373 (1 + omega)(1 - T_c/T)]``.

    IDAES's generic package calls it only to estimate bubble and dew temperatures when it
    initializes a state block; the phase-equilibrium equations contain fugacities, not P_sat.
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
                psat = cobj.pressure_crit * pyo.exp(a * (1 - cobj.temperature_crit / temp))
                if dT:
                    return psat * a * cobj.temperature_crit / temp**2
                return psat

    return WilsonPsat


def property_config(
    records: dict[str, dict[str, float]], phase: str | None = None
) -> dict[str, Any]:
    """The GenericParameterBlock configuration.

    ``phase=None``: T08's two-phase vapour-only block. ``"VAPOR"``: the vapour phase alone, all five
    components. ``"LIQUID"``: the liquid phase alone, NH3 alone.
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
    nasa = _nasa_cp()
    psat = _wilson_psat()
    names = ("NH3",) if phase == "LIQUID" else COMPONENTS
    components: dict[str, Any] = {}
    for name in names:
        row = records[name]
        entry: dict[str, Any] = {
            "type": core.Component,
            "enth_mol_ig_comp": nasa,
            "cp_mol_ig_comp": nasa,
            "parameter_data": {
                "mw": (row["molar_mass"], u.kg / u.mol),
                "pressure_crit": (row["critical_pressure"], u.Pa),
                "temperature_crit": (row["critical_temperature"], u.K),
                "omega": row["acentric_factor"],
                "nasa_cp": {f"b{k}": row[f"ideal_gas_cp_b{k}"] for k in range(5)},
                "enth_mol_form_vap_comp_ref": (row["standard_formation_enthalpy"], u.J / u.mol),
            },
        }
        if phase is None:
            entry["pressure_sat_comp"] = psat
            if name in LIGHT_GASES:
                entry["valid_phase_types"] = core.PhaseType.vaporPhase
            else:
                entry["phase_equilibrium_form"] = {("Vap", "Liq"): forms.log_fugacity}
        components[name] = entry
    eos = {
        "equation_of_state": ceos.Cubic,
        "equation_of_state_options": {"type": ceos.CubicType.PR},
    }
    phases = {
        "Liq": {"type": core.LiquidPhase, **eos},
        "Vap": {"type": core.VaporPhase, **eos},
    }
    if phase == "VAPOR":
        del phases["Liq"]
    elif phase == "LIQUID":
        del phases["Vap"]
    config: dict[str, Any] = {
        "components": components,
        "phases": phases,
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
        "temperature_ref": (T_REF, u.K),
        "parameter_data": {"PR_kappa": {(i, j): 0.0 for i in names for j in names}},
        "include_enthalpy_of_formation": True,
    }
    if phase is None:
        config["phases_in_equilibrium"] = [("Vap", "Liq")]
        config["phase_equilibrium_state"] = {("Vap", "Liq"): pe.SmoothVLE}
        config["bubble_dew_method"] = bd.LogBubbleDew
    return config


# -- the evaluations -----------------------------------------------------------------------------


def _fractions(n: Sequence[float]) -> list[float]:
    total = sum(n)
    return [value / total for value in n]


def evaluate_phase(records: dict[str, dict[str, float]], spec: dict[str, Any]) -> dict[str, Any]:
    """Z, ln phi and h of one phase at (T, P, z): IDAES's expressions at the fixed state."""
    pyo: Any = importlib.import_module("pyomo.environ")
    gp: Any = importlib.import_module(
        "idaes.models.properties.modular_properties.base.generic_property"
    )
    stats: Any = importlib.import_module("idaes.core.util.model_statistics")
    v = pyo.value
    phase = spec["phase"]
    p = "Vap" if phase == "VAPOR" else "Liq"
    z = dict(zip(COMPONENTS, _fractions(spec["n_mol_s"]), strict=True))
    present = ("NH3",) if phase == "LIQUID" else COMPONENTS
    if phase == "LIQUID" and any(z[c] != 0.0 for c in LIGHT_GASES):
        raise ValueError("a LIQUID request carries light gas")
    m = pyo.ConcreteModel()
    m.props = gp.GenericParameterBlock(**property_config(records, phase))
    m.state = m.props.build_state_block([0], defined_state=True)
    s = m.state[0]
    s.flow_mol.fix(1.0)
    s.temperature.fix(spec["T_K"])
    s.pressure.fix(spec["P_Pa"])
    for c in present:
        s.mole_frac_comp[c].fix(z[c])
        s.mole_frac_phase_comp[p, c].set_value(z[c])
    s.flow_mol_phase[p].set_value(1.0)
    s.phase_frac[p].set_value(1.0)
    dof = stats.degrees_of_freedom(m)
    residual = max(
        abs(v(con.body) - v(con.upper))
        for con in m.component_data_objects(pyo.Constraint, active=True)
    )
    values: dict[str, float] = {"Z": v(s.compress_fact_phase[p])}
    for c in present:
        values[f"lnphi_{c}"] = math.log(v(s.fug_coeff_phase_comp[p, c]))
    values["h"] = v(s.enth_mol_phase[p])
    return {
        "spec": spec,
        "idaes_phase": p,
        "components_in_block": list(present),
        "degrees_of_freedom": dof,
        "max_constraint_residual": residual,
        "values": values,
    }


def flash(records: dict[str, dict[str, float]], spec: dict[str, Any]) -> dict[str, Any]:
    """T08's isothermal flash on the two-phase block: beta, y and the phases' properties."""
    pyo: Any = importlib.import_module("pyomo.environ")
    core: Any = importlib.import_module("idaes.core")
    gp: Any = importlib.import_module(
        "idaes.models.properties.modular_properties.base.generic_property"
    )
    units: Any = importlib.import_module("idaes.models.unit_models")
    stats: Any = importlib.import_module("idaes.core.util.model_statistics")
    v = pyo.value
    z = _fractions(spec["n_mol_s"])
    m = pyo.ConcreteModel()
    m.fs = core.FlowsheetBlock(dynamic=False)
    m.fs.props = gp.GenericParameterBlock(**property_config(records))
    m.fs.flash = units.Flash(property_package=m.fs.props)
    m.fs.flash.inlet.flow_mol.fix(1.0)
    m.fs.flash.inlet.temperature.fix(spec["T_K"])
    m.fs.flash.inlet.pressure.fix(spec["P_Pa"])
    for c, zc in zip(COMPONENTS, z, strict=True):
        m.fs.flash.inlet.mole_frac_comp[0, c].fix(zc)
    out = m.fs.flash.control_volume.properties_out[0]
    out.temperature.fix(spec["T_K"])
    m.fs.flash.deltaP.fix(0.0)
    dof = stats.degrees_of_freedom(m)
    try:
        m.fs.flash.initialize(outlvl=40)
        init_outcome = "ok"
    except Exception as exc:  # recorded; the solve is still attempted from where it stopped
        init_outcome = f"{type(exc).__name__}: {exc}"
    solver = pyo.SolverFactory("ipopt")
    for key, value in SOLVER_OPTIONS.items():
        solver.options[key] = value
    result = solver.solve(m)
    y = {c: v(out.mole_frac_phase_comp["Vap", c]) for c in COMPONENTS}
    vapour: dict[str, float] = {"Z": v(out.compress_fact_phase["Vap"])}
    vapour |= {f"lnphi_{c}": math.log(v(out.fug_coeff_phase_comp["Vap", c])) for c in COMPONENTS}
    vapour["h"] = v(out.enth_mol_phase["Vap"])
    liquid = {
        "x_NH3": v(out.mole_frac_phase_comp["Liq", "NH3"]),
        "Z": v(out.compress_fact_phase["Liq"]),
        "lnphi_NH3": math.log(v(out.fug_coeff_phase_comp["Liq", "NH3"])),
        "h": v(out.enth_mol_phase["Liq"]),
    }
    return {
        "spec": spec,
        "degrees_of_freedom": dof,
        "initialization": init_outcome,
        "solver_status": str(result.solver.status),
        "termination_condition": str(result.solver.termination_condition),
        "solver_options": SOLVER_OPTIONS,
        "vapor_fraction": v(out.phase_frac["Vap"]),
        "y_star": y["NH3"],
        "y_vapour": y,
        "T_equilibrium_minus_T_K": v(out._teq["Vap", "Liq"]) - spec["T_K"],
        "vapour": vapour,
        "liquid": liquid,
    }


# -- the environment -----------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_sha256(root: Path) -> str:
    """``scripts/build-reference-envs.sh``'s ``tree_hash``: sha256sum's lines over sorted files."""
    files = sorted(
        (f"./{p.relative_to(root).as_posix()}" for p in root.rglob("*") if p.is_file()),
        key=lambda s: s.encode(),
    )
    lines = "".join(f"{_sha256(root / f[2:])}  {f}\n" for f in files)
    return hashlib.sha256(lines.encode()).hexdigest()


def environment(idaes_data: Path) -> dict[str, Any]:
    pyo: Any = importlib.import_module("pyomo.environ")
    ceos_common: Any = importlib.import_module(
        "idaes.models.properties.modular_properties.eos.ceos_common"
    )
    constants: Any = importlib.import_module("idaes.core.util.constants")
    freeze = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"], check=True, capture_output=True, text=True
    ).stdout
    freeze_sorted = "".join(sorted(freeze.splitlines(keepends=True), key=lambda s: s.encode()))
    bin_dir = idaes_data / "bin"
    pr = ceos_common.EoS_param[ceos_common.CubicType.PR]
    return {
        "kind": f"separate venv from {LOCK} (--require-hashes) and the IDAES binary extensions "
        f"{EXTENSIONS['release']} {EXTENSIONS['distro']}, built by "
        "scripts/build-reference-envs.sh idaes; never the project .venv",
        "lock_sha256": _sha256(REPO_ROOT / LOCK),
        "pip_freeze_sha256": hashlib.sha256(freeze_sorted.encode()).hexdigest(),
        "idaes_data_bin_tree_sha256": _tree_sha256(bin_dir),
        "ipopt_sha256": _sha256(bin_dir / "ipopt"),
        "cubic_roots_sha256": _sha256(bin_dir / "cubic_roots.so"),
        "idaes_extension_sha256": {name: _sha256(bin_dir / name) for name in EXTENSION_TARBALLS},
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": {p: importlib.metadata.version(p) for p in PACKAGES},
        "ipopt_version": ".".join(str(x) for x in pyo.SolverFactory("ipopt").version()),
        "idaes_pr_constants": {
            "omegaA": pr["omegaA"],
            "coeff_b": pr["coeff_b"],
            "u": pr["u"],
            "w": pr["w"],
            "kappa": "0.37464 + 1.54226 omega - 0.26992 omega^2 (IDAES ceos.cubic_kappa_PR)",
            "gas_constant_J_per_mol_K": pyo.value(constants.Constants.gas_constant),
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)
    idaes_data = Path(os.environ.setdefault("IDAES_DATA", str(Path(sys.prefix) / "idaes-data")))
    records = read_records(RECORDS)
    record: dict[str, Any] = {
        "record": "m01-idaes-conformance",
        "version": 1,
        "assertion": "M01.A37",
        "specification": "docs/derivations/M01-spec.md §9.8 M01.A37, §14 WO-5",
        "script": "benchmarks/m01/idaes_conformance.py",
        "status": "measured",
        "judged": False,
        "comparison": "none here: tests/test_m01_idaes_conformance.py compares this record with "
        "pr-c1-v1 at A37's tolerances",
        "environment": environment(idaes_data),
        "inputs": {
            "components_yaml_sha256": _sha256(RECORDS),
            "reference_values_yaml_sha256": _sha256(REFERENCE),
            "records": records,
            "k_ij": "0 for every pair (ADR 0026 D3)",
            "cp_gas_constant_J_per_mol_K": R_RECORDS,
            "T_ref_K": T_REF,
        },
        "property_block": {
            "method": "IDAES modular Cubic, CubicType.PR; FTPx; light gases vapour-only (H2, N2, "
            "Ar, CH4), NH3 in both phases; log-fugacity equilibrium, SmoothVLE, LogBubbleDew; "
            "c_p^ig: NASA-7 low range from the records (user method); P_sat: Wilson estimate "
            "(initialization only)",
            "phase_states": "one-phase variant of the block (VAPOR: Vap only, five components; "
            "LIQUID: Liq only, NH3 alone); state fixed, mole_frac_phase_comp = z, IDAES's "
            "expressions evaluated (no solve)",
            "flash_states": "Flash, outlet T = inlet T, dP = 0, inlet 1 mol/s; IDAES initialize, "
            "then Ipopt",
        },
        "phase_states": {sid: evaluate_phase(records, spec) for sid, spec in PHASE_STATES.items()},
        "flash_states": {sid: flash(records, spec) for sid, spec in FLASH_STATES.items()},
    }
    args.out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
