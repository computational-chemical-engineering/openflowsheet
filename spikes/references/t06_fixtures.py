"""T06 M6 reference qualification: the fixtures, settings and self-check shared by both tools.

Authority: `docs/derivations/T06-corpus-spec.md` §9.2 (the eight fixtures REF-01 ... REF-08),
§9.3 (matched semantics and the registered solver settings), §9.4 (positive controls PC-1,
PC-2), §9.5 rule 2 (the tool's own overall component balance, 3.1e-8 mol/s) and §9.6 (blindness).

**Blind by construction.** This module and the two tool scripts that import it
(`t06_qualify_idaes.py`, `t06_qualify_dwsim.py`) hold only *inputs*: SYN-001's constants, the
fixture definitions of §9.2, the settings of §9.3, and the environment fingerprint of
`docs/reference-environments.md` §3. They import nothing from `src/`, `benchmarks/` or the design
lane's generator, and they read no result of this project or of the twin. What they decide per
run is only: did the tool accept the model, did it converge, does its own component balance
close (rule 2), and (IDAES) does its SmoothVLE equilibrium temperature sit within rule 2b's bound
of the sharp one. No tool number is compared with anything but the same tool's other numbers.

Stdlib only, so that both reference environments (and the project venv, for the summary) can
import it. Not part of `scripts/check.sh`: the gate never runs a tool.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

# SYN-001 constants, verbatim from docs/derivations/SYN-001.md §1 (plan §3.1).
COMPONENTS = ("A", "B", "C")
T_BOIL = {"A": 320.0, "B": 360.0, "C": 400.0}  # K
L_VAP = {"A": 25_000.0, "B": 30_000.0, "C": 35_000.0}  # J/mol
CP = 100.0  # J/(mol K), both phases
V_LIQ = 1.0e-4  # m3/mol
MW = 0.100  # kg/mol
T_REF = 300.0  # K
P_REF = 100_000.0  # Pa
R_GAS = 8.31446261815324  # J/(mol K)

# Rule 2 (§9.5): the tool's own overall component balance must close to this, per component.
RULE2_TOL_MOL_PER_S = 3.1e-8
# Rule 2b (§9.5 as amended by A2), IDAES only: the SmoothVLE shift of the equilibrium temperature,
# `|T_eq - min(max(T, T_bub), T_dew)|`, must not exceed this on any state block (a_T / 100).
RULE2B_SHIFT_BOUND_K = "1e-7"

# ---- §9.3 settings (registered inputs) -------------------------------------------------------

# Placeholders both tools require and SYN-001 does not define (§9.3 row "Placeholders").
PLACEHOLDER_TC = 1000.0  # K
PLACEHOLDER_PC = 1.0e7  # Pa
PLACEHOLDER_OMEGA = 0.0

# IDAES/Ipopt, final solve of every fixture and control. HSL MA27 (the bundled Ipopt's default) is
# not used (D19 disclosure). `constr_viol_tol` is 1e-9 uniformly (spec §9.3 as amended by A1,
# ruling M6 (a); `ref.closed_form.reference_tool_settings.IDAES.final_solve`): M6 measured 1e-10 at
# the binary64 floor of the Pa rows of REF-04/05/06 and applied 1e-9 there as an adjustment; the
# design lane registered 1e-9 for every fixture, so no per-fixture adjustment remains.
IDAES_SOLVER_OPTIONS: dict[str, Any] = {
    "linear_solver": "mumps",
    "tol": 1e-10,
    "constr_viol_tol": 1e-9,
    "max_iter": 500,
}

# IDAES SmoothVLE smoothing parameters, set on every SmoothVLE state block of every fixture and
# control before initialization (spec §9.3 as amended by A2;
# `ref.closed_form.reference_tool_settings.IDAES.smooth_vle`). IDAES's defaults are eps_1 = 0.01 K
# and eps_2 = 5e-4 K, which shift the equilibrium temperature by up to (eps_1 + eps_2)/2; the
# registered value bounds that shift by 1e-8 K. A registered input: never changed per fixture.
IDAES_SMOOTH_VLE_EPS_K: dict[str, float] = {"eps_1": 1e-8, "eps_2": 1e-8}

# DWSIM flash (Raoult's Law package's FlashSettings), PT and PH, external and internal loops.
DWSIM_FLASH_SETTINGS: dict[str, str] = {
    "PTFlash_External_Loop_Tolerance": "1E-10",
    "PTFlash_Internal_Loop_Tolerance": "1E-10",
    "PHFlash_External_Loop_Tolerance": "1E-10",
    "PHFlash_Internal_Loop_Tolerance": "1E-10",
    "PTFlash_Maximum_Number_Of_External_Iterations": "1000",
    "PTFlash_Maximum_Number_Of_Internal_Iterations": "1000",
    "PHFlash_Maximum_Number_Of_External_Iterations": "1000",
    "PHFlash_Maximum_Number_Of_Internal_Iterations": "1000",
}

# DWSIM Recycle block (REF-08): absolute tolerances, no acceleration.
DWSIM_RECYCLE = {
    "mass_flow_kg_per_s": 1e-12,
    "temperature_K": 1e-8,
    "pressure_Pa": 1e-6,
    "maximum_iterations": 1000,
    "acceleration": "None",
}

# DWSIM liquid density: incompressible (the pressure correction off), §9.3 placeholders row.
DWSIM_PP_OPTIONS = {"LiquidDensity_CorrectExpDataForPressure": False}


def dwsim_hvap_j_per_mol(c: str, mapped: bool) -> float:
    """DWSIM's constant vaporization enthalpy input: ``L_i + P_r v_i`` (§9.3), or ``L_i`` (PC-1)."""
    return L_VAP[c] + (P_REF * V_LIQ if mapped else 0.0)


def dwsim_hform_ig_j_per_mol(c: str) -> float:
    """DWSIM's ideal-gas formation enthalpy at 298.15 K: ``L_i + P_r v_i`` (§9.3 reaction datum)."""
    return L_VAP[c] + P_REF * V_LIQ


# ---- §9.2 fixtures and §9.4 positive controls (inputs only) ----------------------------------


def _feed(flows: tuple[float, float, float], t: float, p: float = P_REF) -> dict[str, Any]:
    return {"flows": dict(zip(COMPONENTS, flows, strict=True)), "T": t, "P": p}


EQ = (1.0, 1.0, 1.0)

# The recycle's tear/initialization guess is a harness input, not a §9.3 setting: the stream the
# T06 representability probe used (spikes/references/*_representability.py), chosen there before
# any comparison existed. It is not this project's registered initializer (whose values come from
# the twin and are therefore not read here).
RECYCLE_TEAR_GUESS = _feed((0.2, 0.6, 0.8), 360.0)

FIXTURES: dict[str, dict[str, Any]] = {
    "REF-01": {
        "unit": "mixer",
        "feeds": {"S1": _feed((1.0, 0.5, 0.2), 300.0), "S2": _feed((0.2, 0.5, 1.0), 340.0)},
        "outlet_P": P_REF,
    },
    "REF-02": {
        "unit": "splitter",
        "feeds": {"S1": _feed((1.0, 2.0, 3.0), 330.0)},
        "split_fraction_S2": 0.3,  # to S2 ("recycle"); S3 is "purge"
    },
    "REF-03": {"unit": "heater", "feeds": {"S1": _feed(EQ, 300.0)}, "outlet_T": 350.0},
    "REF-04": {
        "unit": "flash",
        "feeds": {"S1": _feed(EQ, 300.0)},
        "flash_T": 360.0,
        "flash_P": P_REF,
    },
    "REF-05": {"unit": "valve", "feeds": {"S1": _feed(EQ, 360.0, 1.8e5)}, "outlet_P": P_REF},
    "REF-06": {
        "unit": "pump",
        "feeds": {"S1": _feed(EQ, 300.0)},
        "outlet_P": 1.8e5,
        "efficiency": 0.75,
    },
    "REF-07": {
        "unit": "conversion_reactor",
        "feeds": {"S1": _feed((1.2, 0.9, 0.3), 300.0)},
        "nu": {"A": -2.0, "B": -1.0, "C": 3.0},
        "key": "A",
        "conversion": 0.5,
        "outlet_T": 315.0,
        "phase": "liquid",
    },
    "REF-08": {
        "unit": "recycle",
        "feeds": {"S1": _feed(EQ, 300.0)},
        "heater_T": 350.0,
        "flash_T": 360.0,
        "split_fraction_recycle": 0.5,
        "tear_guess": RECYCLE_TEAR_GUESS,
    },
    # PC-1: REF-04 in DWSIM with the unmapped vaporization enthalpy dH_vap = L_i (§9.4).
    "PC-1": {
        "unit": "flash",
        "feeds": {"S1": _feed(EQ, 300.0)},
        "flash_T": 360.0,
        "flash_P": P_REF,
        "dwsim_unmapped_latent": True,
    },
    # PC-2: TP flash of the equimolar feed at 370 K and 1.5e5 Pa (§9.4), where neither tool's
    # K = Psat/P carries SYN-001's Poynting factor. The spec names only the flash (T, P) and the
    # feed composition; the feed is REF-04's (300 K, liquid) at the flash pressure, so that the
    # flash has no pressure change.
    "PC-2": {
        "unit": "flash",
        "feeds": {"S1": _feed(EQ, 300.0, 1.5e5)},
        "flash_T": 370.0,
        "flash_P": 1.5e5,
    },
}

# Fixtures a tool has no run for, with the reason (recorded, not silently skipped).
NOT_APPLICABLE = {
    "IDAES": {
        "PC-1": (
            "PC-1 is defined on DWSIM's vaporization-enthalpy input (spec §9.4: 'DWSIM with "
            "dH_vap = L_i on REF-04'); IDAES's SYN-001 mapping has no such input (its enthalpies "
            "are SYN-001's exactly, docs/reference-environments.md §5.0), so there is no "
            "unmapped IDAES variant to run; registered not_applicable by spec §9.4 as amended "
            "(A1, ruling M6 (b))"
        )
    },
    "DWSIM": {},
}


# ---- the quantities each tool reports (names only) -------------------------------------------

_N = ("A", "B", "C")


def _flows(stream: str, part: str = "n") -> tuple[str, ...]:
    return tuple(f"{stream}.{part}.{c}" for c in _N)


# Spec §9.2's "Compared" column, per fixture, in this project's stream and unit ids — which the
# tool scripts use as their own tags, so a tool reports the quantity of the stream or unit that
# carries the same name. These are *names*: which quantities a fixture compares is a registration
# input (spec §9.2; `ref.closed_form.reference_fixtures`, `.positive_controls`), and no value of
# this project or of the twin is read. PC-1 is REF-04 with DWSIM's unmapped latent heat, so a tool
# reports REF-04's quantities for it; PC-2 compares `S2.n` only (§9.2's PC-2 row).
_REF04 = ("U-FLASH.Q", *_flows("S2"), *_flows("S3"))
COMPARED: dict[str, tuple[str, ...]] = {
    "REF-01": (*_flows("S3"), "S3.T"),
    "REF-02": (*_flows("S2"), *_flows("S3"), "S2.T", "S3.T"),
    "REF-03": ("U-HEAT.Q", *_flows("S2", "vap")),
    "REF-04": _REF04,
    "REF-05": ("S2.T", *_flows("S2", "vap")),
    "REF-06": ("U-PUMP.W", "S2.T"),
    "REF-07": (*_flows("S2"), "U-RX.Q"),
    "REF-08": (
        *_flows("S4"),
        *_flows("S6"),
        *_flows("S7"),
        "U-HEAT.Q",
        "U-FLASH.Q",
        "S2.T",
    ),
    "PC-1": _REF04,
    "PC-2": _flows("S2"),
}

# DWSIM's tags where they differ from this project's stream ids: REF-07's reactor product is two
# DWSIM streams (its vapour and liquid outlets; S2 is their sum), REF-08's recycle S6 is the
# splitter's product `S6-split` (the stream DWSIM calculates; `S6` is the Recycle block's outlet,
# equal to it within the Recycle tolerances), and every duty or work is an energy stream, counted
# as flowing into its unit exactly as the energy self-check counts it.
DWSIM_STREAM_PARTS: dict[str, dict[str, tuple[str, ...]]] = {
    "REF-07": {"S2": ("S2-V", "S2-L")},
    "REF-08": {"S6": ("S6-split",)},
}
DWSIM_ENERGY_STREAM = {
    "U-HEAT.Q": "Q-HEAT",
    "U-FLASH.Q": "Q-FLASH",
    "U-RX.Q": "Q-RX",
    "U-PUMP.W": "W-PUMP",
}


def dwsim_compared_quantities(fixture: str, raw_output: dict[str, Any]) -> dict[str, float]:
    """``COMPARED[fixture]`` from a DWSIM record's raw output alone (streams and energy streams).

    Pure and stdlib-only, so that the comparison can recompute it from the committed record.
    Flows in mol/s (DWSIM's compound molar flows), ``T`` in K, duty and work in W (DWSIM's energy
    streams are in kW)."""
    streams = raw_output["streams"]
    energy_kw = raw_output["energy_streams_kW"]
    parts = DWSIM_STREAM_PARTS.get(fixture, {})
    out: dict[str, float] = {}
    for quantity in COMPARED[fixture]:
        if quantity in DWSIM_ENERGY_STREAM:
            out[quantity] = float(energy_kw[DWSIM_ENERGY_STREAM[quantity]]) * 1000.0
            continue
        stream, _, rest = quantity.partition(".")
        tags = parts.get(stream, (stream,))
        if rest == "T":
            (tag,) = tags
            out[quantity] = float(streams[tag]["T_K"])
        else:
            part, _, c = rest.partition(".")
            key = {"n": "overall_mol_per_s", "vap": "vapor_mol_per_s"}[part]
            out[quantity] = math.fsum(float(streams[tag][key][c]) for tag in tags)
    return out


# ---- rule 2 ----------------------------------------------------------------------------------


def component_balance(
    inlets: list[dict[str, float]],
    outlets: list[dict[str, float]],
    generation: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Rule 2 on the tool's own numbers: ``inlets + generation - outlets`` per component."""
    gen = generation or dict.fromkeys(COMPONENTS, 0.0)
    residual = {
        c: sum(s[c] for s in inlets) + gen[c] - sum(s[c] for s in outlets) for c in COMPONENTS
    }
    worst = max(abs(v) for v in residual.values())
    return {
        "residual_mol_per_s": residual,
        "max_abs_mol_per_s": worst,
        "tolerance_mol_per_s": RULE2_TOL_MOL_PER_S,
        "passes": bool(math.isfinite(worst) and worst <= RULE2_TOL_MOL_PER_S),
    }


# ---- rule 2b (IDAES) -------------------------------------------------------------------------

_TEQ = re.compile(r"^(?P<block>.+)\._teq\[(?P<pair>[^\]]+)\]$")


def smooth_vle_shift(
    variables: dict[str, float | None], parameters: dict[str, float]
) -> dict[str, Any]:
    """Rule 2b on an IDAES record's own numbers (spec §9.5 as amended by A2).

    ``variables`` is the record's ``raw_output.variables`` (every Pyomo variable by name) and
    ``parameters`` its ``raw_output.smooth_vle_parameters`` (every SmoothVLE ``eps_1_*``/``eps_2_*``
    by name). A SmoothVLE state block is one with an ``_teq[<pair>]`` variable; for each, the shift
    ``|T_eq - min(max(T, T_bub), T_dew)|`` is computed exactly (in decimal, on the recorded
    doubles), and the ``eps_1``/``eps_2`` the block carries are collected (``None`` if absent).
    Nothing but the record is read.
    """
    blocks: dict[str, dict[str, Any]] = {}
    for name in sorted(variables):
        mt = _TEQ.match(name)
        if mt is None:
            continue
        block, pair = mt.group("block"), mt.group("pair")
        suffix = "_" + "_".join(p.strip() for p in pair.split(","))
        values = [
            variables[name],
            variables.get(f"{block}.temperature"),
            variables.get(f"{block}.temperature_bubble[{pair}]"),
            variables.get(f"{block}.temperature_dew[{pair}]"),
        ]
        entry: dict[str, Any] = {
            "eps_1_K": parameters.get(f"{block}.eps_1{suffix}"),
            "eps_2_K": parameters.get(f"{block}.eps_2{suffix}"),
        }
        finite_values = [float(v) for v in values if v is not None and math.isfinite(v)]
        if len(finite_values) < len(values):
            entry["shift_K"] = None
        else:
            t_eq, t, t_bub, t_dew = (Decimal(repr(v)) for v in finite_values)
            entry["shift_K"] = abs(t_eq - min(max(t, t_bub), t_dew))
        blocks[f"{block}[{pair}]"] = entry
    shifts = [e["shift_K"] for e in blocks.values()]
    worst = None if not shifts or None in shifts else max(shifts)
    argmax = None if worst is None else next(b for b, e in blocks.items() if e["shift_K"] == worst)
    return {"blocks": blocks, "max_shift_K": worst, "argmax": argmax}


def smooth_vle_self_check(
    variables: dict[str, float | None], parameters: dict[str, float]
) -> dict[str, Any]:
    """The tool-side record of rule 2b: the shift against the bound, and the eps it ran with."""
    shift = smooth_vle_shift(variables, parameters)
    worst = shift["max_shift_K"]
    registered = all(
        e["eps_1_K"] == IDAES_SMOOTH_VLE_EPS_K["eps_1"]
        and e["eps_2_K"] == IDAES_SMOOTH_VLE_EPS_K["eps_2"]
        for e in shift["blocks"].values()
    )
    bound = Decimal(RULE2B_SHIFT_BOUND_K)
    return {
        "shift_bound_K": float(bound),
        "max_shift_K": None if worst is None else float(worst),
        "argmax": shift["argmax"],
        "blocks": {
            b: {**e, "shift_K": None if e["shift_K"] is None else float(e["shift_K"])}
            for b, e in shift["blocks"].items()
        },
        "eps_as_registered_on_every_block": bool(shift["blocks"]) and registered,
        "passes": bool(shift["blocks"]) and registered and worst is not None and worst <= bound,
    }


# ---- environment fingerprint (docs/reference-environments.md §3) -----------------------------

EXPECTED_FINGERPRINT = {
    "idaes": {
        "pip_freeze_sha256": "dfeec96faebeb6bedab5eb1c069df7344282d0002fe92fb191f2c55c73af82c6",
        "idaes_data_bin_tree": "370a694825da3be3d7b0e68742bf2e704918260b05fa0f6c54d4d61458d1144d",
        "ipopt_sha256": "8f8711b709b5f265ff7cb8b352c037bb999d88628384be8390f26530f08de94e",
    },
    "dwsim": {
        "pip_freeze_sha256": "d0a428cc7c06a7605bcfdaeb1e62ac3e9630b02c04224dea8e5928bc2e02635a",
        "dotnet_tree": "f03ce7f0101336009c4bd090fd3006d187ba419b03bf86c84d0b56367b6e1058",
        "dwsim_tree": "b8de32e026197858b552b7b310c621a9e919952288900a66c73ac2a0353ea87e",
        "automation_dll_sha256": "ce32c2a422e20c553769a355fdf6fc0cf94eac85ae6ba37d4df045cd2208aa31",
    },
}


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def tree_hash(root: Path) -> str:
    """The build script's `tree_hash`: sha256 of `find . -type f | sort | xargs sha256sum`."""
    entries: list[bytes] = []
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            full = Path(dirpath) / name
            if full.is_symlink() or not full.is_file():
                continue
            rel = "./" + full.relative_to(root).as_posix()
            entries.append(rel.encode())
    entries.sort()
    listing = b"".join(
        file_sha256(root / e.decode()[2:]).encode() + b"  " + e + b"\n" for e in entries
    )
    return hashlib.sha256(listing).hexdigest()


def pip_freeze_sha256() -> str:
    out = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"], check=True, capture_output=True
    ).stdout
    lines = sorted(out.splitlines(keepends=True))
    return hashlib.sha256(b"".join(lines)).hexdigest()


def fingerprint(tool: str, env_dir: Path) -> dict[str, Any]:
    """This run's environment fingerprint and whether it equals §3's (spec §9.5 rule 1)."""
    if tool == "idaes":
        got = {
            "pip_freeze_sha256": pip_freeze_sha256(),
            "idaes_data_bin_tree": tree_hash(env_dir / "idaes-data" / "bin"),
            "ipopt_sha256": file_sha256(env_dir / "idaes-data" / "bin" / "ipopt"),
        }
    else:
        got = {
            "pip_freeze_sha256": pip_freeze_sha256(),
            "dotnet_tree": tree_hash(env_dir / "dotnet"),
            "dwsim_tree": tree_hash(env_dir / "dwsim"),
            "automation_dll_sha256": file_sha256(env_dir / "dwsim" / "DWSIM.Automation.dll"),
        }
    expected = EXPECTED_FINGERPRINT[tool]
    return {
        "measured": got,
        "expected_docs_reference_environments_s3": expected,
        "matches": got == expected,
    }


def finite(x: Any) -> Any:
    """JSON-safe: non-finite floats become strings, recursively."""
    if isinstance(x, float) and not math.isfinite(x):
        return repr(x)
    if isinstance(x, dict):
        return {str(k): finite(v) for k, v in x.items()}
    if isinstance(x, list | tuple):
        return [finite(v) for v in x]
    return x
