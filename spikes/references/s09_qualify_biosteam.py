"""S09 WO-S09-2: blind qualification of the column cases in BioSTEAM 2.54.0.

Authority: `docs/derivations/S09-spec.md` §2.3 (order), §2.4 (structural questions Q-X1..Q-X10),
§4 (the SYN-001 mapping, in `s09_biosteam_syn001`), §5 (solve path, ladder, L2(c) outer loop,
accuracy rerun, units), §6 (rule values computed from the tool's own record) and §10 (record
fields), with S03 §7.1's rules 2, 2c and 2d as S09 extends them.

For one case of `s09_cases.json -> pairs` per process (§5.7) this script sets the tool's global
thermo once (SYN-001, or PC-LB's latent-heat variant), runs §4.3's readback, then walks §2.3's
order: L1 (the native `MultiStageEquilibrium` with native stage specifications), then L2(c) only
where L1's inspection recorded a registered specification as structurally inexpressible. At an
attempted level it runs all four rungs of §5.3, each through §5.2's two-pass path (and §5.4's
outer loop at L2(c)); a rung that passes rules 2, 2c and 2d's specification residual is repeated at
§5.5's looser tolerance. The selected rung is the first in §5.3's order that passes rules 2-2d,
at a level where §6.4's path dependence does not fire. Every rung, evaluation and pass is recorded.

Blind (§2.3 step 2, §9.2): the only input files of this project are `s03_cases.json` and
`s09_cases.json`; the only modules of this project imported are `t06_fixtures` (pinned) and
`s09_biosteam_syn001`. No value of this project's solver, of the generator or of a classifier output
is read. The tolerances used for the rerun movement and the path spread take the tool's own value
for v (S03 §6's formula; the script reads no other).

    .venv-biosteam/bin/python spikes/references/s09_qualify_biosteam.py --case RC1 --out DIR
    .venv-biosteam/bin/python spikes/references/s09_qualify_biosteam.py --assemble DIR \
        [--repeat DIR2]

`s09_qualify.sh` runs every case, twice, and assembles (A17). Not part of `scripts/check.sh`: the
gate never runs a tool.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import subprocess
import sys
import time
import traceback
import warnings
from pathlib import Path
from typing import Any

warnings.filterwarnings("ignore")

import biosteam as bst  # noqa: E402
import flexsolve as flx  # noqa: E402
import s09_biosteam_syn001 as syn  # noqa: E402
import t06_fixtures as fx  # noqa: E402

CASES3_PATH = fx.REPO_ROOT / "docs" / "derivations" / "scripts" / "s03_cases.json"
CASES9_PATH = fx.REPO_ROOT / "docs" / "derivations" / "scripts" / "s09_cases.json"
SCRIPT_PATHS = (
    "spikes/references/s09_qualify_biosteam.py",
    "spikes/references/s09_biosteam_syn001.py",
    "spikes/references/s09_qualify.sh",
)

# `docs/reference-environments.md` §9 (WO-S09-1): the pip-freeze SHA-256 of `.venv-biosteam`,
# measured on two consecutive builds. Rule 1's fingerprint.
EXPECTED_PIP_FREEZE_SHA256 = "0edea300bbf188030642265ca811425c270d5508bf119fa86431572c06c69a95"
VERSION_DISTRIBUTIONS = (
    "biosteam",
    "thermosteam",
    "thermo",
    "chemicals",
    "flexsolve",
    "numba",
    "numpy",
    "scipy",
)

KMOLH_PER_MOLS = 3.6  # 1 mol/s = 3.6 kmol/h; 1 W = 3.6 kJ/h (§5.6, claim C8)
COMPONENTS = ("A", "B", "C")
PHASE = {"LIQUID": "l", "VAPOR": "g"}

# S03 §6: allowances a_k and the relative term of the tolerance a_k + 1e-6 |v|.
ALLOWANCE = {"T": 1e-5, "flow": 3.1e-7, "duty": 1e-2}
RELATIVE = 1e-6
# S03 rule 2c (unchanged) and its §17.4 specification thresholds.
RULE2C_PRESSURE_PA = 1e-3
RULE2C_INTERMEDIATE_DUTY_W = 1e-3
RULE2C_SPEC_RELATIVE = 1e-4
RULE2D_SPEC = {
    "reflux_ratio": ("relative", 1e-8),
    "boilup_ratio": ("relative", 1e-8),
    "distillate_rate": ("relative", 1e-8),
    "bottoms_rate": ("relative", 1e-8),
    "duty": ("relative", 1e-8),
    "purity": ("absolute", 1e-8),
    "recovery": ("absolute", 1e-9),
    "temperature": ("relative", 1e-9),
}
RULE2D_FRACTION = 0.1  # rerun movement and path spread, in tolerances (§5.5, §6.4)
RUNG_NAMES = ("R1", "R2", "R3", "R4")

# §5.2 P3: the stage attribute each native specification is stored in, and the stored value.
STORED = {
    "Reflux": ("B", lambda v: math.inf if v == 0 else (0.0 if math.isinf(v) else 1.0 / v)),
    "Boilup": ("B", lambda v: v),
    "Duty": ("Q", lambda v: v),
    "Flow": ("F", lambda v: v),
    "Temperature": ("T", lambda v: v),
}
SPECIFIED_VARIABLE = {"Reflux": "B", "Boilup": "B", "Duty": "Q", "Flow": "F", "Temperature": "T"}


def load_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    cases3 = json.loads(CASES3_PATH.read_text(encoding="utf-8"))
    cases9 = json.loads(CASES9_PATH.read_text(encoding="utf-8"))
    pins = cases9["s03_pins"]
    got = hashlib.sha256(CASES3_PATH.read_bytes()).hexdigest()
    rel = "docs/derivations/scripts/s03_cases.json"
    if got != pins[rel]:
        raise RuntimeError(f"{rel} SHA-256 {got} is not the pinned {pins[rel]}")
    return cases3, cases9


def settings9(cases9: dict[str, Any]) -> dict[str, Any]:
    return cases9["tool_settings"]["BioSTEAM"]


def rungs(cases9: dict[str, Any]) -> list[tuple[str, str]]:
    return [(a, m) for a, m in settings9(cases9)["rungs"]]


def quantity_tolerance(kind: str, value: float) -> float:
    """S03 §6's tolerance with the tool's own value standing in for v."""
    return ALLOWANCE[kind] + RELATIVE * abs(value)


# ---- realization at each level (§2.2, §2.5, §5.6) --------------------------------------------


def inlet_total_mol_per_s(case: dict[str, Any]) -> float:
    return math.fsum(float(v) for inlet in case["inlets"] for v in inlet["n_mol_per_s"])


def native_end(case: dict[str, Any], end: str) -> dict[str, Any]:
    """Q-X6 at L1 for one end: the native specification and its conversion, or why there is none."""
    n = int(case["stage_count"])
    spec = case["specifications"].get(end)
    kind_of_end = case["condenser"] if end == "condenser" else case["reboiler"]
    stage = 0 if end == "condenser" else n - 1
    if kind_of_end == "none":
        return {
            "end": end,
            "stage": stage,
            "native": None,
            "expressible": True,
            "realization": f"no {end}: stage {stage} carries no specification",
        }
    if spec is None:
        raise ValueError(f"{end} present without a registered specification")
    kind, value = spec["kind"], float(spec["value"])
    out: dict[str, Any] = {"end": end, "stage": stage, "registered": spec}
    if end == "condenser" and kind == "reflux_ratio" and case["condenser"] == "partial":
        out.update(
            native=("Reflux", value),
            expressible=True,
            conversion="partial condenser RR -> ('Reflux', RR)",
        )
    elif end == "condenser" and kind == "reflux_ratio" and case["condenser"] == "total":
        out.update(
            native=("Reflux", math.inf),
            side_draw=1.0 / (1.0 + value),
            expressible=True,
            conversion="total condenser RR -> ('Reflux', inf) with bottom_side_draws={0: 1/(1+RR)}",
        )
    elif end == "reboiler" and kind == "boilup_ratio":
        out.update(native=("Boilup", value), expressible=True, conversion="BR -> ('Boilup', BR)")
    elif end == "reboiler" and kind == "bottoms_rate":
        f_tot = inlet_total_mol_per_s(case)
        out.update(
            native=("Flow", value / f_tot),
            expressible=True,
            conversion=f"B -> ('Flow', B/F), F = {f_tot!r} mol/s (sum of the registered "
            "inlet flows)",
        )
    elif kind == "duty":
        out.update(
            native=("Duty", KMOLH_PER_MOLS * value),
            expressible=True,
            conversion="Q -> ('Duty', 3.6 Q) in kJ/h",
        )
    elif kind == "temperature" and int(spec["stage"]) - 1 == stage:
        out.update(
            native=("Temperature", value),
            expressible=True,
            conversion="end-stage temperature -> ('Temperature', T)",
        )
    else:
        where = (
            f" on our stage {spec['stage']}, not the end stage {stage + 1}"
            if kind == "temperature"
            else ""
        )
        out.update(
            native=None,
            expressible=False,
            reason=f"no native option with S03 §5.1 row 9's definition: {kind}{where}"
            f" ({settings9_not_native_note(kind)})",
        )
    return out


def settings9_not_native_note(kind: str) -> str:
    return {
        "distillate_rate": "BioSTEAM's stage specifications are Reflux, Boilup, Duty, Flow and "
        "Temperature; Flow is a bottoms flow over the bulk feed",
        "purity": "no composition specification among the stage specifications",
        "recovery": "no recovery specification among the stage specifications",
        "temperature": "a Temperature specification replaces that stage's energy balance, so "
        "the stage would carry the duty and the end would be adiabatic",
    }.get(kind, "not a native stage specification")


def l1_realization(case: dict[str, Any]) -> dict[str, Any]:
    ends = {e: native_end(case, e) for e in ("condenser", "reboiler")}
    bad = [e for e, v in ends.items() if not v["expressible"]]
    real: dict[str, Any] = {"level": "L1", "ends": ends, "expressible": not bad}
    if bad:
        real["reason"] = "; ".join(f"{e}: {ends[e]['reason']}" for e in bad)
    return real


def l2c_realization(case: dict[str, Any], l1: dict[str, Any]) -> dict[str, Any]:
    """§2.2 L2(c): exactly one registered specification without a native option, realized by
    §5.4's loop on the native specification of the same end (C2)."""
    bad = [e for e, v in l1["ends"].items() if not v["expressible"]]
    real: dict[str, Any] = {"level": "L2(c)"}
    if len(bad) != 1:
        real.update(
            expressible=False,
            reason=f"{len(bad)} specifications without a native option; L2(c) admits one",
        )
        return real
    end = bad[0]
    n = int(case["stage_count"])
    adjusted = ("Reflux", 0) if end == "condenser" else ("Boilup", n - 1)
    spec = case["specifications"][end]
    kind = spec["kind"]
    basis = "absolute" if kind in ("purity", "recovery") else "relative"
    real.update(
        expressible=True,
        ends=l1["ends"],
        outer_end=end,
        adjusted={"name": adjusted[0], "stage": adjusted[1]},
        registered=spec,
        residual_basis=basis,
        equation=("g(x) = (s(x) - s*)/|s*|" if basis == "relative" else "g(x) = s(x) - s*")
        + f", s = {kind} by S03 §5.1 row 9 and §17.4 on the tool's record, s* = {spec['value']}",
    )
    return real


def stage_specifications(
    case: dict[str, Any], real: dict[str, Any], x: float | None
) -> tuple[dict[int, tuple[str, float]], dict[int, float]]:
    """The constructor's `stage_specifications` and `bottom_side_draws` for the realization (with
    the adjusted value x at L2(c))."""
    specs: dict[int, tuple[str, float]] = {}
    draws: dict[int, float] = {}
    for end in ("condenser", "reboiler"):
        e = real["ends"][end]
        if e.get("native") is not None:
            specs[e["stage"]] = (e["native"][0], e["native"][1])
            if "side_draw" in e:
                draws[0] = e["side_draw"]
    if real["level"] == "L2(c)":
        adj = real["adjusted"]
        specs[adj["stage"]] = (adj["name"], x)
    return specs, draws


# ---- build, solve, read (§5.1, §5.2) ---------------------------------------------------------


def build(
    case: dict[str, Any],
    cases9: dict[str, Any],
    rung: tuple[str, str],
    tol: float,
    specs: dict[int, tuple[str, float]],
    draws: dict[int, float],
) -> Any:
    """§5.2 P1: the inlets and the column, then the rung's algorithm, method and tolerances."""
    n = int(case["stage_count"])
    common = settings9(cases9)["common"]
    inlets = []
    for inlet in case["inlets"]:
        flows = {
            c: KMOLH_PER_MOLS * float(v)
            for c, v in zip(COMPONENTS, inlet["n_mol_per_s"], strict=True)
        }
        inlets.append(
            bst.Stream(
                None,
                **flows,
                T=float(inlet["T_K"]),
                P=float(inlet["P_Pa"]),
                phase=PHASE[inlet["phase"]],
                units="kmol/hr",
            )
        )
    outs = ["", ""] + ([""] if draws else [])
    kw: dict[str, Any] = {"bottom_side_draws": dict(draws)} if draws else {}
    col = bst.MultiStageEquilibrium(
        None,
        ins=inlets,
        outs=outs,
        N_stages=n,
        feed_stages=[int(inlet["stage"]) - 1 for inlet in case["inlets"]],
        P=[float(p) for p in case["stage_pressures_Pa"]],
        phases=tuple(common["phases"]),
        stage_specifications=dict(specs),
        maxiter=int(common["maxiter"]),
        max_attempts=int(common["max_attempts"]),
        use_cache=bool(common["use_cache"]),
        specifications_by_weight=bool(settings9(cases9)["mapping"]["specifications_by_weight"]),
        **kw,
    )
    col.algorithms = (rung[0],)
    col.methods = (rung[1],)
    col.early_termination = bool(common["early_termination"])
    col.tolerance = tol
    col.relative_tolerance = tol
    return col


def applied_settings(col: Any) -> dict[str, Any]:
    """Every solver attribute as applied (§5.1: the tool's defaults recorded per run)."""
    return {
        "algorithms": list(col.algorithms),
        "methods": list(col.methods),
        "early_termination": bool(col.early_termination),
        "tolerance": col.tolerance,
        "relative_tolerance": col.relative_tolerance,
        "maxiter": col.maxiter,
        "max_attempts": col.max_attempts,
        "use_cache": bool(col.use_cache),
        "specifications_by_weight": bool(col.specifications_by_weight),
        "phases": list(col.phases),
        "optimize_result": bool(col.optimize_result),
        "damping": col.damping,
        "homotopy_continuation": bool(col.homotopy_continuation),
        "vle_decomposition_before": col.vle_decomposition,
        "inside_loop_algorithm": col.inside_loop_algorithm,
        "line_search": bool(col._line_search),
        "minimum_residual_reduction": col.minimum_residual_reduction,
        "iteration_memory": col.iteration_memory,
        "partition_data": dict(col.partition_data),
    }


_ABSENT = object()


def simulate_pass(col: Any) -> dict[str, Any]:
    t0 = time.perf_counter()
    rec: dict[str, Any] = {"exception": None}
    # §18.3: fsolve ran in this pass iff the tool assigned a new info list in it (stage.py:3044).
    info_before = getattr(col, "_simultaneous_correction_info", _ABSENT)
    try:
        col.simulate()
    except Exception as exc:  # B1: recorded, never hidden
        rec["exception"] = f"{type(exc).__name__}: {exc}"
        rec["traceback"] = traceback.format_exc(limit=3)
    rec["iter"] = getattr(col, "iter", None)
    rec["maxiter"] = col.maxiter
    rec["attempt"] = getattr(col, "attempt", None)
    # The tool's internal residual is not used by any rule (§6.1); it is recorded as raw output.
    rec["tool_mean_residual_not_used"] = repr(getattr(col, "_mean_residual", None))
    info = getattr(col, "_simultaneous_correction_info", _ABSENT)
    ran = info is not _ABSENT and info is not info_before
    # nfev is B2's counter on R3 (§18.3); ier and mesg are recorded and used by no rule (§6.1).
    rec["fsolve"] = {
        "ran": ran,
        "nfev": int(info[0]["nfev"]) if ran else None,
        "ier": int(info[1]) if ran else None,
        "mesg": str(info[2]) if ran else None,
    }
    rec["vle_decomposition_after"] = col.vle_decomposition
    rec["wall_time_s"] = time.perf_counter() - t0
    return rec


def respecify(col: Any, specs: dict[int, tuple[str, float]]) -> list[dict[str, Any]]:
    """§5.2 P3: re-store every registered native value through the stage's attribute setter."""
    out = []
    for idx, (name, value) in sorted(specs.items()):
        attr, conv = STORED[name]
        stage = col.stages[idx]
        before = getattr(stage, attr)
        setattr(stage, attr, conv(value))
        out.append(
            {
                "stage": idx,
                "specification": name,
                "attribute": attr,
                "stored_after_pass1": before,
                "set_to": getattr(stage, attr),
            }
        )
    return out


def solve(
    case: dict[str, Any],
    cases9: dict[str, Any],
    rung: tuple[str, str],
    tol: float,
    specs: dict[int, tuple[str, float]],
    draws: dict[int, float],
) -> tuple[Any, dict]:
    """§5.2 P1-P4. The record is pass 2; pass 1 is recorded and never selected."""
    col = build(case, cases9, rung, tol, specs, draws)
    path: dict[str, Any] = {
        "applied": applied_settings(col),
        "stage_specifications": {str(k): [v[0], v[1]] for k, v in specs.items()},
        "bottom_side_draws": {str(k): v for k, v in draws.items()},
    }
    path["pass1"] = simulate_pass(col)
    path["respecification"] = {"route": "attribute_setter", "set": respecify(col, specs)}
    path["pass2"] = simulate_pass(col)
    return col, path


def stream_mol_per_s(s: Any) -> dict[str, float]:
    return {c: float(s.imol[c]) / KMOLH_PER_MOLS for c in COMPONENTS}


def stream_record(s: Any) -> dict[str, Any]:
    return {
        "phase": s.phase,
        "T_K": float(s.T),
        "P_Pa": float(s.P),
        "mol_per_s": stream_mol_per_s(s),
        "F_mol_per_s": float(s.F_mol) / KMOLH_PER_MOLS,
        "H_kJ_per_h": float(s.H),
        "H_W": float(s.H) / KMOLH_PER_MOLS,
    }


def live(streams: Any) -> list[Any]:
    return [s for s in streams if s is not None]


def read_profile(col: Any) -> dict[str, Any]:
    """Per stage T, P, L, V, x, y, duty (§5.6), from the tool's own objects."""
    stages = []
    for j, st in enumerate(col.stages):
        vap, liq = st.partition.outs
        h_in = sum(float(s.H) for s in live(st.ins))
        h_out = sum(float(s.H) for s in live(st.outs))
        lf, vf = float(liq.F_mol), float(vap.F_mol)
        stages.append(
            {
                "index": j,
                "T_K": float(st.T) if st.T is not None else None,
                "P_Pa": float(st.P),
                "L_mol_per_s": lf / KMOLH_PER_MOLS,
                "V_mol_per_s": vf / KMOLH_PER_MOLS,
                "x": {c: float(liq.imol[c]) / lf if lf > 0 else None for c in COMPONENTS},
                "y": {c: float(vap.imol[c]) / vf if vf > 0 else None for c in COMPONENTS},
                "liquid_T_K": float(liq.T),
                "vapour_T_K": float(vap.T),
                "duty_W": (h_out - h_in) / KMOLH_PER_MOLS,
                "duty_definition": "(sum of the stage's outlet H - sum of its inlet H)/3.6, the "
                "tool's "
                "enthalpy, positive into the stage",
                "stored_Q_kJ_per_h": st.Q,
                "specified_variable": st.specified_variable,
                "in_mol_per_s": [stream_mol_per_s(s) for s in live(st.ins)],
                "out_mol_per_s": [stream_mol_per_s(s) for s in live(st.outs)],
                "liquid_side_draw_mol_per_s": (
                    stream_mol_per_s(st.outs[-1]) if st.bottom_split else None
                ),
            }
        )
    return {
        "stages": stages,
        "inlets": [stream_record(s) for s in col.ins],
        "products": [stream_record(s) for s in col.outs],
        "products_order": "outs[0] vapour of stage 0, outs[1] liquid of stage N-1"
        + (", outs[2] the liquid side draw of stage 0" if len(col.outs) > 2 else ""),
    }


# ---- registered quantities and specification values (S03 §4, §5.1 row 9, §17.4) -----------


def top_product(case: dict[str, Any], prof: dict[str, Any]) -> dict[str, Any]:
    """The condenser end's product: v_1 (partial or no condenser) or the side draw d (total)."""
    return prof["products"][2] if case["condenser"] == "total" else prof["products"][0]


def quantities(case: dict[str, Any], prof: dict[str, Any]) -> dict[str, float]:
    st = prof["stages"]
    n = len(st)
    out: dict[str, float] = {}
    for name, _kind in case["quantities"]:
        if name.startswith(("T[", "L[", "V[")):
            j = int(name[2:-1])
            key = {"T": "T_K", "L": "L_mol_per_s", "V": "V_mol_per_s"}[name[0]]
            out[name] = st[j - 1][key]
        elif name == "reflux":
            out[name] = st[0]["L_mol_per_s"] - prof["products"][2]["F_mol_per_s"]
        elif name.startswith("top["):
            out[name] = top_product(case, prof)["mol_per_s"][name[4:-1]]
        elif name.startswith("bottom["):
            out[name] = prof["products"][1]["mol_per_s"][name[7:-1]]
        elif name == "Q_condenser":
            out[name] = st[0]["duty_W"]
        elif name == "Q_reboiler":
            out[name] = st[n - 1]["duty_W"]
        else:
            raise KeyError(f"no BioSTEAM value for registered quantity {name}")
    return out


def ratio(a: float, b: float) -> float:
    """a / b, or NaN for b == 0 (an empty stream): a check that reads it fails as non-finite."""
    return a / b if b != 0 else math.nan


def spec_value(case: dict[str, Any], prof: dict[str, Any], end: str) -> tuple[float, str]:
    """S03 §5.1 row 9 with §17.4 (s03_cases.json specification_definitions_amendment_1)."""
    spec = case["specifications"][end]
    kind = spec["kind"]
    st = prof["stages"]
    n = len(st)
    total = case["condenser"] == "total"
    if kind == "reflux_ratio":
        if total:
            d = prof["products"][2]["F_mol_per_s"]
            return ratio(
                st[0]["L_mol_per_s"] - d, d
            ), "reflux (stage 0 liquid less the side draw) / D"
        return ratio(st[0]["L_mol_per_s"], st[0]["V_mol_per_s"]), "L_1 / V_1"
    if kind == "boilup_ratio":
        return ratio(st[n - 1]["V_mol_per_s"], st[n - 1]["L_mol_per_s"]), "V_N / L_N"
    if kind == "distillate_rate":
        if total:
            return prof["products"][2]["F_mol_per_s"], "D (the side draw)"
        return st[0]["V_mol_per_s"], "V_1"
    if kind == "bottoms_rate":
        return st[n - 1]["L_mol_per_s"], "L_N"
    if kind == "duty":
        stage = 0 if end == "condenser" else n - 1
        return st[stage]["duty_W"], f"computed duty of stage index {stage}, W, into the stage"
    if kind == "purity":
        c = spec["component"]
        prod = top_product(case, prof) if end == "condenser" else prof["products"][1]
        return ratio(
            prod["mol_per_s"][c], prod["F_mol_per_s"]
        ), f"mole fraction of {c} in the {end} product"
    if kind == "recovery":
        c = spec["component"]
        prod = top_product(case, prof) if end == "condenser" else prof["products"][1]
        fed = math.fsum(s["mol_per_s"][c] for s in prof["inlets"])
        return ratio(
            prod["mol_per_s"][c], fed
        ), f"{end} product flow of {c} / the inlets' flow of {c}"
    if kind == "temperature":
        s = int(spec["stage"])
        return st[s - 1]["T_K"], f"T of our stage {s} (BioSTEAM index {s - 1})"
    raise ValueError(kind)


def spec_values(case: dict[str, Any], prof: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out = {}
    for end, spec in case["specifications"].items():
        kind, reg = spec["kind"], float(spec["value"])
        got, definition = spec_value(case, prof, end)
        absolute = got - reg
        relative = absolute / abs(reg)
        basis, threshold = RULE2D_SPEC[kind]
        measure = abs(absolute) if basis == "absolute" else abs(relative)
        out[end] = {
            "kind": kind,
            "definition": definition,
            "registered": reg,
            "tool": got,
            "relative_difference": relative,
            "absolute_difference": absolute,
            "rule2c_threshold": RULE2C_SPEC_RELATIVE,
            "rule2c_passes": bool(
                math.isfinite(relative) and abs(relative) <= RULE2C_SPEC_RELATIVE
            ),
            "rule2d_basis": basis,
            "rule2d_threshold": threshold,
            "rule2d_measure": measure,
            "rule2d_passes": bool(math.isfinite(measure) and measure <= threshold),
        }
    return out


# ---- rule values (§6.2, §6.3, §6.4) ----------------------------------------------------------


def b2_count(rung_name: str, pass_rec: dict[str, Any]) -> int | None:
    """§18.3: B2's counter of one pass. R3 (fsolve): its nfev, or None when fsolve did not run
    in that pass; the fixed-point rungs: the tool's iter."""
    if rung_name == "R3":
        fs = pass_rec["fsolve"]
        return fs["nfev"] if fs["ran"] else None
    return pass_rec["iter"]


def rule2(
    case: dict[str, Any],
    cases9: dict[str, Any],
    rung: tuple[str, str],
    col: Any,
    path: dict[str, Any],
    prof: dict[str, Any],
) -> dict[str, Any]:
    """B1-B5, from the tool's own record."""
    r2 = settings9(cases9)["rule2"]
    t_stage = float(r2["stage_component_mol_per_s"])
    t_eq = float(r2["equilibrium"])
    t_comp = float(r2["overall_component_mol_per_s"])
    t_energy = float(r2["overall_energy_W"])
    b1 = {"pass1": path["pass1"]["exception"], "pass2": path["pass2"]["exception"]}
    b1["passes"] = b1["pass1"] is None and b1["pass2"] is None
    rung_name = RUNG_NAMES[rungs(cases9).index(rung)]
    b2 = {
        "rung": rung_name,
        "counter": "fsolve nfev" if rung_name == "R3" else "iter",
        "pass1_count": b2_count(rung_name, path["pass1"]),
        "pass2_count": b2_count(rung_name, path["pass2"]),
        "maxiter": col.maxiter,
    }
    b2["passes"] = all(
        n is not None and n < col.maxiter for n in (b2["pass1_count"], b2["pass2_count"])
    )
    b3_rows = []
    for st in prof["stages"]:
        res = {
            c: math.fsum([s[c] for s in st["in_mol_per_s"]] + [-s[c] for s in st["out_mol_per_s"]])
            for c in COMPONENTS
        }
        b3_rows.append(res)
    b3_max = max(abs(v) for row in b3_rows for v in row.values())
    b3 = {
        "per_stage_mol_per_s": b3_rows,
        "max": b3_max,
        "threshold": t_stage,
        "passes": bool(math.isfinite(b3_max) and b3_max <= t_stage),
    }
    b4_rows: list[Any] = []
    one_phase = []
    chems = col.chemicals
    for j, st in enumerate(prof["stages"]):
        t, p = st["T_K"], st["P_Pa"]
        k = {c: (float(chems[c].Psat(t)) / p if t is not None else math.nan) for c in COMPONENTS}
        total_cond = case["condenser"] == "total" and j == 0
        if total_cond and st["L_mol_per_s"] > 0:
            val = abs(math.fsum(k[c] * st["x"][c] for c in COMPONENTS) - 1.0)
            b4_rows.append(
                {"stage": j, "form": "bubble |sum K x - 1| (total condenser)", "K": k, "max": val}
            )
        elif st["L_mol_per_s"] > 0 and st["V_mol_per_s"] > 0:
            per = {c: abs(st["y"][c] - k[c] * st["x"][c]) for c in COMPONENTS}
            b4_rows.append(
                {
                    "stage": j,
                    "form": "|y_c - K_c x_c|",
                    "K": k,
                    "per_component": per,
                    "max": max(per.values()),
                }
            )
        else:
            one_phase.append(j)
            b4_rows.append({"stage": j, "form": "skipped: one phase empty", "K": k, "max": None})
    vals = [r["max"] for r in b4_rows if r["max"] is not None]
    b4_max = max(vals) if vals else math.nan
    b4 = {
        "per_stage": b4_rows,
        "max": b4_max,
        "threshold": t_eq,
        "one_phase_stages": one_phase,
        "passes": bool(math.isfinite(b4_max) and b4_max <= t_eq),
    }
    comp = fx.component_balance(
        [s["mol_per_s"] for s in prof["inlets"]], [s["mol_per_s"] for s in prof["products"]]
    )
    duties = [st["duty_W"] for st in prof["stages"]]
    energy = (
        math.fsum(s["H_W"] for s in prof["inlets"])
        + math.fsum(duties)
        - math.fsum(s["H_W"] for s in prof["products"])
    )
    b5 = {
        "component": comp,
        "energy_W": energy,
        "energy_threshold_W": t_energy,
        "component_threshold_mol_per_s": t_comp,
        "energy_terms": {
            "inlets_W": [s["H_W"] for s in prof["inlets"]],
            "products_W": [s["H_W"] for s in prof["products"]],
            "duties_W": duties,
        },
        "passes": bool(
            comp["max_abs_mol_per_s"] <= t_comp
            and math.isfinite(energy)
            and abs(energy) <= t_energy
        ),
    }
    checks = {"B1": b1, "B2": b2, "B3": b3, "B4": b4, "B5": b5}
    failed = [k for k, v in checks.items() if not v["passes"]]
    return {"checks": checks, "failed": failed, "passes": not failed}


def readback_specs(
    col: Any, specs: dict[int, tuple[str, float]], draws: dict[int, float]
) -> dict[str, Any]:
    """§6.3: each specified stage's specified_variable and stored value after pass 2, exactly."""
    rows = []
    for idx, (name, value) in sorted(specs.items()):
        attr, conv = STORED[name]
        st = col.stages[idx]
        stored = getattr(st, attr)
        expected = conv(value)
        rows.append(
            {
                "stage": idx,
                "specification": name,
                "registered_value": value,
                "expected_variable": SPECIFIED_VARIABLE[name],
                "specified_variable": st.specified_variable,
                "attribute": attr,
                "expected_stored": expected,
                "stored": stored,
                "passes": st.specified_variable == SPECIFIED_VARIABLE[name] and stored == expected,
            }
        )
    for idx, split in sorted(draws.items()):
        st = col.stages[idx]
        rows.append(
            {
                "stage": idx,
                "specification": "bottom_side_draw",
                "expected_stored": split,
                "stored": st.bottom_split,
                "passes": st.bottom_split == split,
            }
        )
    return {"rows": rows, "passes": all(r["passes"] for r in rows)}


def pressure_check(case: dict[str, Any], prof: dict[str, Any]) -> dict[str, Any]:
    reg = [float(p) for p in case["stage_pressures_Pa"]]
    devs = [abs(st["P_Pa"] - r) for st, r in zip(prof["stages"], reg, strict=True)]
    devs += [abs(prof["products"][0]["P_Pa"] - reg[0]), abs(prof["products"][1]["P_Pa"] - reg[-1])]
    if len(prof["products"]) > 2:
        devs.append(abs(prof["products"][2]["P_Pa"] - reg[0]))
    worst = max(devs)
    return {"value": worst, "threshold": RULE2C_PRESSURE_PA, "passes": worst <= RULE2C_PRESSURE_PA}


def end_stages(case: dict[str, Any]) -> set[int]:
    n = int(case["stage_count"])
    ends = set()
    if case["condenser"] != "none":
        ends.add(0)
    if case["reboiler"] != "none":
        ends.add(n - 1)
    return ends


def rule2c(
    case: dict[str, Any],
    cases9: dict[str, Any],
    col: Any,
    prof: dict[str, Any],
    specs: dict[int, tuple[str, float]],
    draws: dict[int, float],
    prop_rb: dict[str, Any],
) -> dict[str, Any]:
    n = int(case["stage_count"])
    ends = end_stages(case)
    inter = [abs(st["duty_W"]) for j, st in enumerate(prof["stages"]) if j not in ends]
    inter_max = max(inter) if inter else 0.0
    feed_ok = [
        int(inlet["stage"]) - 1 == fs
        for inlet, fs in zip(case["inlets"], col.feed_stages, strict=True)
    ]
    checks: dict[str, Any] = {
        "stage_count": {"value": len(col.stages), "registered": n, "passes": len(col.stages) == n},
        "feed_stage": {"value": list(col.feed_stages), "passes": all(feed_ok)},
        "pressure_max_abs_dev_Pa": pressure_check(case, prof),
        "intermediate_duty_max_abs_W": {
            "value": inter_max,
            "threshold": RULE2C_INTERMEDIATE_DUTY_W,
            "passes": inter_max <= RULE2C_INTERMEDIATE_DUTY_W,
        },
        "specification_readback": readback_specs(col, specs, draws),
        "property_readback": {"failed": prop_rb["failed"], "passes": prop_rb["passes"]},
    }
    if case["condenser"] == "total":
        vap = prof["products"][0]["F_mol_per_s"]
        lim = float(settings9(cases9)["rule2c_added"]["total_condenser_vapour_mol_per_s"])
        checks["total_condenser_vapour_mol_per_s"] = {
            "value": vap,
            "threshold": lim,
            "passes": abs(vap) <= lim,
        }
    specv = spec_values(case, prof)
    checks["specification"] = {
        "value": specv,
        "passes": all(s["rule2c_passes"] for s in specv.values()),
    }
    failed = [k for k, v in checks.items() if not v["passes"]]
    return {"checks": checks, "failed": failed, "passes": not failed, "specification_values": specv}


def evaluate(
    case: dict[str, Any],
    cases9: dict[str, Any],
    rung: tuple[str, str],
    tol: float,
    real: dict[str, Any],
    x: float | None,
    prop_rb: dict[str, Any],
) -> dict[str, Any]:
    """One complete native solve (fresh build, P1-P4) and every rule value from its record."""
    specs, draws = stage_specifications(case, real, x)
    run: dict[str, Any] = {"x": x}
    try:
        col, path = solve(case, cases9, rung, tol, specs, draws)
        run["path"] = path
        prof = read_profile(col)
        run["profile"] = prof
        run["rule2"] = rule2(case, cases9, rung, col, path, prof)
        run["rule2c"] = rule2c(case, cases9, col, prof, specs, draws, prop_rb)
        specv = run["rule2c"]["specification_values"]
        run["rule2d_specification"] = {
            "passes": all(s["rule2d_passes"] for s in specv.values()),
            "max_measure": max(s["rule2d_measure"] for s in specv.values()),
        }
        run["quantities"] = quantities(case, prof)
        run["harness_error"] = None
    except Exception as exc:  # a harness-side failure to read a record is recorded, not hidden
        run["harness_error"] = f"{type(exc).__name__}: {exc}"
        run["traceback"] = traceback.format_exc(limit=4)
    return run


def run_failed_rule(run: dict[str, Any]) -> tuple[str | None, str]:
    if run.get("harness_error"):
        return "2", f"record not readable: {run['harness_error']}"
    if not run["rule2"]["passes"]:
        return "2", f"rule 2 {run['rule2']['failed']}"
    if not run["rule2c"]["passes"]:
        return "2c", f"semantics: {run['rule2c']['failed']}"
    if not run["rule2d_specification"]["passes"]:
        return "2d", "specification residual"
    return None, "passes rules 2, 2c and 2d's specification residual"


# ---- the L2(c) outer loop (§5.4) -------------------------------------------------------------


class InnerFailedError(RuntimeError):
    pass


def outer_loop(
    case: dict[str, Any],
    cases9: dict[str, Any],
    rung: tuple[str, str],
    tol: float,
    real: dict[str, Any],
    prop_rb: dict[str, Any],
) -> dict[str, Any]:
    """Starts 1 and 2, factor-2 expansion, flexsolve.IQ_interpolation, one final evaluation."""
    ol = settings9(cases9)["outer_loop"]
    kind = real["registered"]["kind"]
    ytol_str, basis = ol["ytol"][kind]
    ytol = float(ytol_str)
    s_star = float(real["registered"]["value"])
    end = real["outer_end"]
    evals: list[dict[str, Any]] = []
    loop: dict[str, Any] = {
        "kind": kind,
        "basis": basis,
        "ytol": ytol,
        "s_star": s_star,
        "starts": [float(v) for v in ol["starts"]],
        "evaluations": evals,
    }

    def g_of(x: float, role: str) -> tuple[float, dict[str, Any]]:
        run = evaluate(case, cases9, rung, tol, real, x, prop_rb)
        ev: dict[str, Any] = {"x": x, "role": role}
        if run.get("harness_error"):
            ev.update(g=None, failed=f"inner_failed({x!r}, record: {run['harness_error']})")
        else:
            b2 = run["rule2"]["checks"]["B2"]
            ev["B2_counter"] = b2["counter"]
            ev["pass1_count"] = b2["pass1_count"]
            ev["pass2_count"] = b2["pass2_count"]
            ev["exceptions"] = [
                run["path"]["pass1"]["exception"],
                run["path"]["pass2"]["exception"],
            ]
            c2 = run["rule2"]["checks"]
            ev["rule2"] = {
                "failed": run["rule2"]["failed"],
                "B3_max": c2["B3"]["max"],
                "B4_max": c2["B4"]["max"],
                "B5_component_max": c2["B5"]["component"]["max_abs_mol_per_s"],
                "B5_energy_W": c2["B5"]["energy_W"],
            }
            c2c = run["rule2c"]["checks"]
            ev["rule2c_inner"] = {
                k: c2c[k]["passes"] for k in ("pressure_max_abs_dev_Pa", "specification_readback")
            }
            s = run["rule2c"]["specification_values"][end]["tool"]
            g = (s - s_star) / abs(s_star) if basis == "relative" else s - s_star
            ev.update(s=s, g=g)
            bad = list(run["rule2"]["failed"]) + [
                k for k, ok in ev["rule2c_inner"].items() if not ok
            ]
            ev["failed"] = f"inner_failed({x!r}, {bad})" if bad else None
        evals.append(ev)
        return (ev["g"] if ev["failed"] is None else math.nan), run

    def g_strict(x: float) -> float:
        g, _ = g_of(x, "solver")
        if not math.isfinite(g):
            raise InnerFailedError(evals[-1]["failed"])
        return g

    try:
        x1, x2 = loop["starts"]
        g1, _ = g_of(x1, "start")
        if not math.isfinite(g1):
            raise InnerFailedError(evals[-1]["failed"])
        g2, _ = g_of(x2, "start")
        if not math.isfinite(g2):
            raise InnerFailedError(evals[-1]["failed"])
        root = None
        if abs(g1) <= ytol:
            root = x1
        elif abs(g2) <= ytol:
            root = x2
        bracket = None
        if root is None:
            if g1 * g2 < 0:
                bracket = (x1, g1, x2, g2)
            else:
                up = abs(g2) <= abs(g1)
                prev_x, prev_g = (x2, g2) if up else (x1, g1)
                loop["expansion"] = "up" if up else "down"
                for _ in range(4):
                    x = prev_x * 2.0 if up else prev_x / 2.0
                    gx, _ = g_of(x, "expansion")
                    if not math.isfinite(gx):
                        raise InnerFailedError(evals[-1]["failed"])
                    if gx * prev_g < 0:
                        bracket = (prev_x, prev_g, x, gx)
                        break
                    prev_x, prev_g = x, gx
                if bracket is None:
                    loop.update(passes=False, failure="no_bracket([1/16, 32])")
                    return loop
            a, ga, b, gb = bracket
            loop["bracket"] = {"a": a, "g_a": ga, "b": b, "g_b": gb}
            loop["solver_call"] = {
                "function": "flexsolve.IQ_interpolation",
                "positional": ["g", a, b, ga, gb, None, 0.0, ytol, [], 50, False, True, True],
                "names": [
                    "f",
                    "x0",
                    "x1",
                    "y0",
                    "y1",
                    "x",
                    "xtol",
                    "ytol",
                    "args",
                    "maxiter",
                    "checkroot",
                    "checkiter",
                    "checkbounds",
                ],
            }
            root = flx.IQ_interpolation(
                g_strict, a, b, ga, gb, None, 0.0, ytol, (), 50, False, True, True
            )
        loop["returned_x"] = float(root)
        gfin, run = g_of(float(root), "final")
        loop["final"] = run
        if not math.isfinite(gfin):
            loop.update(passes=False, failure=evals[-1]["failed"])
        elif not abs(gfin) <= ytol:
            loop.update(passes=False, failure=f"final_residual({gfin!r} > {ytol!r})")
        else:
            loop.update(passes=True, failure=None, final_g=gfin)
    except Exception as exc:  # the attempt fails with the message (§5.4)
        loop.update(passes=False, failure=f"{type(exc).__name__}: {exc}")
    loop["n_evaluations"] = len(evals)
    return loop


# ---- one rung at one level, with its accuracy rerun ------------------------------------------


def rerun_movement(
    case: dict[str, Any], base: dict[str, float], rerun: dict[str, float]
) -> dict[str, Any]:
    kinds = dict(case["quantities"])
    ratios = {k: abs(rerun[k] - base[k]) / quantity_tolerance(kinds[k], base[k]) for k in base}
    worst = max(ratios, key=lambda k: ratios[k])
    return {
        "ratio_to_tolerance": ratios,
        "max_ratio": ratios[worst],
        "max_quantity": worst,
        "threshold": RULE2D_FRACTION,
        "tolerance_value_used": "the tool's own value (the script reads no other)",
        "passes": bool(math.isfinite(ratios[worst]) and ratios[worst] <= RULE2D_FRACTION),
    }


def one_solve(
    case: dict[str, Any],
    cases9: dict[str, Any],
    rung: tuple[str, str],
    tol: float,
    real: dict[str, Any],
    prop_rb: dict[str, Any],
) -> dict[str, Any]:
    """The rung's run: L1's single solve, or L2(c)'s loop and final evaluation."""
    if real["level"] == "L1":
        run = evaluate(case, cases9, rung, tol, real, None, prop_rb)
        return {"run": run, "outer": None}
    loop = outer_loop(case, cases9, rung, tol, real, prop_rb)
    run = loop.pop("final", None)
    return {"run": run, "outer": loop}


def attempt(
    case: dict[str, Any],
    cases9: dict[str, Any],
    k: int,
    rung: tuple[str, str],
    real: dict[str, Any],
    prop_rb: dict[str, Any],
) -> dict[str, Any]:
    s9 = settings9(cases9)
    tol = float(s9["common"]["tolerance"])
    entry: dict[str, Any] = {
        "rung": RUNG_NAMES[k],
        "rung_index": k,
        "algorithm": rung[0],
        "method": rung[1],
        "tolerance": tol,
        "level": real["level"],
    }
    t0 = time.perf_counter()
    res = one_solve(case, cases9, rung, tol, real, prop_rb)
    entry["outer"] = res["outer"]
    run = res["run"]
    entry["run"] = run
    if res["outer"] is not None and not res["outer"]["passes"]:
        entry.update(
            passes=False,
            passes_through_2d_specification=False,
            failed_rule="2",
            reason=f"outer loop: {res['outer']['failure']}",
        )
    else:
        failed, reason = run_failed_rule(run)
        entry["passes_through_2d_specification"] = failed is None
        if failed is not None:
            entry.update(passes=False, failed_rule=failed, reason=reason)
    if entry["passes_through_2d_specification"]:
        fr = s9["floor_rerun"]
        tol2 = float(fr["tolerance"])
        if float(fr["relative_tolerance"]) != tol2:
            raise ValueError("floor_rerun: tolerance and relative_tolerance differ")
        rerun: dict[str, Any] = {"tolerance": tol2}
        if real["level"] == "L1":
            rerun["form"] = "L1: the full path with the registered native specifications"
            run2 = evaluate(case, cases9, rung, tol2, real, None, prop_rb)
        else:
            # §18.4(b): one evaluation at the rung's final x (the same binary64 value), no loop.
            rerun["form"] = f"L2(c): {fr['L2(c)']}"
            run2 = evaluate(case, cases9, rung, tol2, real, run["x"], prop_rb)
        rerun.update(outer=None, run=run2)
        if run2.get("harness_error"):
            rerun.update(passes=False, reason="record not readable")
        elif not run2["rule2"]["passes"] or not run2["rule2c"]["passes"]:
            rerun.update(
                passes=False,
                reason=f"rule 2 {run2['rule2']['failed']}, rule 2c {run2['rule2c']['failed']}",
            )
        else:
            rerun["movement"] = rerun_movement(case, run["quantities"], run2["quantities"])
            rerun["passes"] = rerun["movement"]["passes"]
            rerun["reason"] = "passes" if rerun["passes"] else "movement above 0.1 tolerance"
        entry["accuracy_rerun"] = rerun
        if rerun["passes"]:
            entry.update(passes=True, failed_rule=None, reason="passes rules 2-2d")
        else:
            entry.update(
                passes=False, failed_rule="2d", reason=f"accuracy rerun: {rerun['reason']}"
            )
    entry["wall_time_s"] = time.perf_counter() - t0
    return entry


def path_dependence(case: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, Any]:
    """§6.4: rungs at the level whose runs pass rules 2-2c and the specification residual; the
    largest difference on a registered quantity, in tolerances evaluated at the earlier rung's
    tool value (§5.3 order)."""
    kinds = dict(case["quantities"])
    ok = [e for e in entries if e.get("passes_through_2d_specification")]
    best: dict[str, Any] = {
        "rungs_compared": [e["rung"] for e in ok],
        "max_ratio": None,
        "pair": None,
        "quantity": None,
    }
    worst = -1.0
    for i, a in enumerate(ok):
        for b in ok[i + 1 :]:
            qa, qb = a["run"]["quantities"], b["run"]["quantities"]
            for name in qa:
                r = abs(qb[name] - qa[name]) / quantity_tolerance(kinds[name], qa[name])
                if r > worst:
                    worst = r
                    best.update(max_ratio=r, pair=[a["rung"], b["rung"]], quantity=name)
    best["threshold"] = RULE2D_FRACTION
    best["tolerance_value_used"] = "the earlier rung's tool value"
    best["fires"] = bool(best["max_ratio"] is not None and not best["max_ratio"] <= RULE2D_FRACTION)
    return best


# ---- structural inspection (§2.4) ------------------------------------------------------------


def inspection(
    case: dict[str, Any],
    cases9: dict[str, Any],
    real: dict[str, Any],
    prop: dict[str, Any],
    rung0: tuple[str, str],
) -> dict[str, Any]:
    """Q-X1..Q-X10 read from the built model before it is solved (L2(c): built at x = 1)."""
    n = int(case["stage_count"])
    x = 1.0 if real["level"] == "L2(c)" else None
    specs, draws = stage_specifications(case, real, x)
    col = build(case, cases9, rung0, float(settings9(cases9)["common"]["tolerance"]), specs, draws)
    stages = col.stages

    def spec_of(j: int) -> dict[str, Any]:
        st = stages[j]
        return {
            "specified_variable": st.specified_variable,
            "B": st.B,
            "Q": st.Q,
            "F": st.F,
            "T": st.T,
            "bottom_split": st.bottom_split,
            "top_split": st.top_split,
        }

    feeds_at = {int(fs) for fs in col.feed_stages}
    cond = case["condenser"]
    if cond == "partial":
        cr = {
            "type": "partial",
            "stage": 0,
            "built": spec_of(0),
            "statement": "stage 0 is an equilibrium stage whose vapour is the top product, "
            "with no side draw",
        }
        cr["as_expected"] = stages[0].bottom_split == 0 and stages[0].top_split == 0
    elif cond == "total":
        cr = {
            "type": "total",
            "stage": 0,
            "built": spec_of(0),
            "statement": "stage 0 specified ('Reflux', inf) with bottom_side_draws={0: 1/(1+RR*)}",
        }
        cr["as_expected"] = (
            stages[0].specified_variable == "B"
            and stages[0].B == 0
            and stages[0].bottom_split == real["ends"]["condenser"]["side_draw"]
        )
    else:
        cr = {
            "type": "none",
            "stage": 0,
            "built": spec_of(0),
            "statement": "stage 0 carries no specification and receives the top inlet",
        }
        cr["as_expected"] = (
            stages[0].specified_variable == "Q" and stages[0].Q == 0 and 0 in feeds_at
        )
    reb = case["reboiler"]
    if reb == "partial":
        rr = {
            "type": "kettle",
            "stage": n - 1,
            "built": spec_of(n - 1),
            "statement": "stage N-1 carries the reboiler end's specification",
        }
        rr["as_expected"] = stages[n - 1].specified_variable in ("B", "F", "Q", "T") and (
            real["level"] == "L2(c)"
            or stages[n - 1].specified_variable
            == SPECIFIED_VARIABLE[real["ends"]["reboiler"]["native"][0]]
        )
    else:
        rr = {
            "type": "none",
            "stage": n - 1,
            "built": spec_of(n - 1),
            "statement": "stage N-1 carries no specification and receives the bottom inlet",
        }
        rr["as_expected"] = (
            stages[n - 1].specified_variable == "Q" and stages[n - 1].Q == 0 and (n - 1) in feeds_at
        )
    specs_q: dict[str, Any] = {}
    for end, e in real["ends"].items():
        if e.get("native") is not None:
            specs_q[end] = {
                "native": [e["native"][0], e["native"][1]],
                "conversion": e.get("conversion"),
                "stage": e["stage"],
                "stored": spec_of(e["stage"]),
            }
        elif "reason" in e:
            specs_q[end] = {"native": None, "reason": e["reason"]}
            if real["level"] == "L2(c)":
                specs_q[end].update(adjusted=real["adjusted"], equation=real["equation"])
        else:
            specs_q[end] = {"native": None, "realization": e.get("realization")}
    ends = end_stages(case)
    if real["level"] == "L2(c)":
        ends.add(real["adjusted"]["stage"])
    inter = []
    for j, st in enumerate(stages):
        if j in ends:
            continue
        inter.append(
            {
                "stage": j,
                "specified_variable": st.specified_variable,
                "Q": st.Q,
                "side_draw": bool(st.bottom_split or st.top_split),
                "reaction": st.reaction is not None,
                "as_expected": st.specified_variable == "Q"
                and st.Q == 0
                and not st.bottom_split
                and not st.top_split
                and st.reaction is None
                and not col.partition_data,
            }
        )
    default_methods = [type(col).default_methods[a] for a in type(col).default_algorithms]
    ladder = {
        "default_algorithms": list(type(col).default_algorithms),
        "default_methods": default_methods,
        "registered_rungs": [list(r) for r in rungs(cases9)],
    }
    ladder["matches"] = [
        list(r) for r in zip(ladder["default_algorithms"], default_methods, strict=True)
    ] == ladder["registered_rungs"]
    return {
        "property_package": prop,
        "stage_map": {
            "len_stages": len(stages),
            "registered": n,
            "map": {str(j): j - 1 for j in range(1, n + 1)},
            "statement": "our stage j -> BioSTEAM stage j - 1 (stage 0 is the top)",
        },
        "feed_stages": {
            "tool": list(col.feed_stages),
            "registered": [int(i["stage"]) - 1 for i in case["inlets"]],
            "statement": "each inlet enters whole at stage `stage - 1`",
        },
        "condenser_realization": cr,
        "reboiler_realization": rr,
        "specifications": specs_q,
        "pressures": [float(st.P) for st in stages],
        "intermediate_stages": inter,
        "initialization": {
            "statement": "BioSTEAM's own initializer (hot_start); no initial point "
            "from this project",
            "use_cache": bool(col.use_cache),
        },
        "ladder_source": ladder,
    }


# ---- one case (§2.3) -------------------------------------------------------------------------


def fingerprint() -> dict[str, Any]:
    got = fx.pip_freeze_sha256()
    versions = {d: importlib.metadata.version(d) for d in VERSION_DISTRIBUTIONS}
    versions["python"] = sys.version.split()[0]
    return {
        "pip_freeze_sha256": got,
        "expected_docs_reference_environments_s9": EXPECTED_PIP_FREEZE_SHA256,
        "versions": versions,
        "matches": got == EXPECTED_PIP_FREEZE_SHA256,
    }


def harness_commit() -> dict[str, Any]:
    root = fx.REPO_ROOT
    head = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain", "--", *SCRIPT_PATHS],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return {"head": head, "scripts": list(SCRIPT_PATHS), "scripts_clean_at_head": not dirty}


def run_case(cid: str, cases3: dict[str, Any], cases9: dict[str, Any]) -> dict[str, Any]:
    alias = {"PC-LB": "RC1"}  # PC-LB runs RC1's inputs (s09_cases.json controls.PC-LB.inputs)
    case = cases3["cases"][alias.get(cid, cid)]
    variant = "PC-LB" if cid == "PC-LB" else "SYN-001"
    t0 = time.perf_counter()
    hvaps = syn.hvap_values(variant, cases9)
    chems, thermo = syn.build_thermo(hvaps)
    bst.settings.set_thermo(thermo)
    prop_rb = syn.readback(chems, thermo, hvaps, cases9)
    prop = {**syn.property_package(chems, thermo), "variant": variant, "readback": prop_rb}
    rs = rungs(cases9)
    l1 = l1_realization(case)
    l2c = l2c_realization(case, l1)
    levels: dict[str, Any] = {
        "L1": {"realization": l1},
        "L2(a)": {
            "applicable": False,
            "reason": "S09 §2.2: no BioSTEAM realization adds anything L1 lacks; never attempted",
        },
        "L2(c)": {"realization": l2c},
        "L2(b)": {
            "admissible": False,
            "reason": "S03 restricts L2(b) to an equation-oriented tool",
        },
        "L3": {
            "admissible": False,
            "reason": "S03 §2.2's reason for DWSIM applies (a cascade of "
            "StageEquilibrium units would be the harness's column)",
        },
    }
    selected = None
    for name, real in (("L1", l1), ("L2(c)", l2c)):
        lev = levels[name]
        if name == "L2(c)" and l1["expressible"]:
            lev["attempted"] = False
            lev["reason"] = "not attempted: L1's inspection recorded every specification as native"
            continue
        if not real["expressible"]:
            lev["attempted"] = False
            lev["reason"] = f"structurally inexpressible: {real['reason']}"
            continue
        lev["attempted"] = True
        lev["inspection"] = inspection(case, cases9, real, prop, rs[0])
        if not lev["inspection"]["ladder_source"]["matches"]:
            raise RuntimeError("Q-X10: the tool's default chain is not §5.3's ladder")
        entries = [attempt(case, cases9, k, r, real, prop_rb) for k, r in enumerate(rs)]
        lev["rungs"] = entries
        pdep = path_dependence(case, entries)
        lev["path_dependence"] = pdep
        first = next((e for e in entries if e["passes"]), None)
        if first is not None and not pdep["fires"]:
            lev["passes"] = True
            lev["selected_rung"] = first["rung"]
            selected = (name, first)
        else:
            lev["passes"] = False
        print(
            f"biosteam {cid} {name}: "
            + ", ".join(
                f"{e['rung']} {'PASS' if e['passes'] else 'fail ' + str(e.get('failed_rule'))}"
                for e in entries
            )
            + f"; path ratio {pdep['max_ratio']}",
            file=sys.stderr,
            flush=True,
        )
        if selected is not None:
            break
    rec: dict[str, Any] = {
        "tool": "BioSTEAM",
        "case": cid,
        "inputs_case": alias.get(cid, cid),
        "case_definition": case,
        "property_variant": variant,
        "environment_fingerprint": fingerprint(),
        "input_files": cases9["blindness"]["input_files"],
        "settings": {
            "registered": settings9(cases9),
            "quantity_tolerance": {
                "allowance": ALLOWANCE,
                "relative": RELATIVE,
                "source": "S03 §6",
            },
        },
        "property_package": prop,
        "levels": levels,
    }
    if selected is None:
        rec.update(
            available=False,
            level=None,
            selected_rung=None,
            not_available_reason=not_available_reason(levels),
        )
    else:
        name, e = selected
        insp = levels[name]["inspection"]
        rec.update(
            available=True,
            level=name,
            selected_rung=e["rung"],
            stage_map=insp["stage_map"],
            feed_stages=insp["feed_stages"],
            condenser_realization=insp["condenser_realization"],
            reboiler_realization=insp["reboiler_realization"],
            specifications=insp["specifications"],
            pressures=insp["pressures"],
            intermediate_stages=insp["intermediate_stages"],
            initialization=insp["initialization"],
            ladder_source=insp["ladder_source"],
            registered_quantities=e["run"]["quantities"],
            accuracy_rerun_quantities=e["accuracy_rerun"]["run"]["quantities"],
            path_dependence=levels[name]["path_dependence"],
            outer_evaluations=(e["outer"]["n_evaluations"] if e["outer"] else 0),
            margin=margin(e, levels[name]["path_dependence"], cases9),
        )
    rec["wall_time_s"] = time.perf_counter() - t0
    return rec


# §18.4(c), in the order of s09_cases.json tool_settings.BioSTEAM.margin.rows; the closed list.
MARGIN_ROWS = (
    "B3_stage_component",
    "B4_equilibrium",
    "B5_component",
    "B5_energy",
    "rule2c_adiabatic_duty",
    "rule2c_total_condenser_vapour",
    "rule2d_specification",
    "rule2d_rerun_movement",
    "rule2d_path_spread",
)


def margin(e: dict[str, Any], pdep: dict[str, Any], cases9: dict[str, Any]) -> dict[str, Any]:
    """§6.6 with §18.4(c): the selected record's ratio on each margin row of the closed list, and
    the largest. Above the thin level (0.1) the record is a thin margin: a disclosure that moves
    no classification. The outer loop's |g|/ytol is not a row."""
    run = e["run"]
    c2 = run["rule2"]["checks"]
    c2c = run["rule2c"]["checks"]
    s9 = settings9(cases9)
    r2 = s9["rule2"]
    specv = run["rule2c"]["specification_values"].values()
    ratios = {
        "B3_stage_component": c2["B3"]["max"] / float(r2["stage_component_mol_per_s"]),
        "B4_equilibrium": c2["B4"]["max"] / float(r2["equilibrium"]),
        "B5_component": c2["B5"]["component"]["max_abs_mol_per_s"]
        / float(r2["overall_component_mol_per_s"]),
        "B5_energy": abs(c2["B5"]["energy_W"]) / float(r2["overall_energy_W"]),
        "rule2c_adiabatic_duty": c2c["intermediate_duty_max_abs_W"]["value"]
        / RULE2C_INTERMEDIATE_DUTY_W,
    }
    if "total_condenser_vapour_mol_per_s" in c2c:
        tc = c2c["total_condenser_vapour_mol_per_s"]
        ratios["rule2c_total_condenser_vapour"] = abs(tc["value"]) / tc["threshold"]
    # Each specification against its own kind's threshold θ_k.
    ratios["rule2d_specification"] = max(s["rule2d_measure"] / s["rule2d_threshold"] for s in specv)
    ratios["rule2d_rerun_movement"] = e["accuracy_rerun"]["movement"]["max_ratio"] / RULE2D_FRACTION
    if pdep["max_ratio"] is not None:  # two or more rungs pass at the level
        ratios["rule2d_path_spread"] = pdep["max_ratio"] / RULE2D_FRACTION
    if len(MARGIN_ROWS) != len(s9["margin"]["rows"]) or not set(ratios) <= set(MARGIN_ROWS):
        raise ValueError("margin rows differ from s09_cases.json tool_settings.BioSTEAM.margin")
    worst = max(ratios, key=lambda k: ratios[k])
    thin_level = float(s9["margin"]["thin_level"])
    return {
        "ratios": ratios,
        "max_ratio": ratios[worst],
        "max_row": worst,
        "thin_level": thin_level,
        "thin": ratios[worst] > thin_level,
        "effect": s9["margin"]["effect"],
    }


def not_available_reason(levels: dict[str, Any]) -> str:
    parts = []
    for name in ("L1", "L2(c)"):
        lev = levels[name]
        if not lev.get("attempted"):
            if lev.get("reason", "").startswith("structurally"):
                parts.append(f"{name}: {lev['reason']}")
            continue
        if lev.get("rungs") and any(e["passes"] for e in lev["rungs"]):
            pd = lev["path_dependence"]
            parts.append(f"{name}: reference_accuracy: path_dependence({pd['max_ratio']!r})")
            continue
        fails = "; ".join(f"{e['rung']} {e['failed_rule']}: {e['reason']}" for e in lev["rungs"])
        parts.append(f"{name}: capability: no rung passed rules 2-2d ({fails})")
    return " | ".join(parts)


# ---- assembly and the repeat run (A17) -------------------------------------------------------


def strip_wall(x: Any) -> Any:
    if isinstance(x, dict):
        return {k: strip_wall(v) for k, v in x.items() if not k.startswith("wall_time")}
    if isinstance(x, list):
        return [strip_wall(v) for v in x]
    return x


def canonical(x: Any) -> bytes:
    return (json.dumps(strip_wall(x), indent=1) + "\n").encode()


def assemble(out: Path, repeat: Path | None, cases9: dict[str, Any]) -> int:
    ids = list(cases9["pairs"])
    cases: dict[str, Any] = {}
    rep: dict[str, Any] = {}
    common = None
    for cid in ids:
        path = out / "results" / f"biosteam-{cid}.json"
        rec = json.loads(path.read_text(encoding="utf-8"))
        common = common or {
            k: rec[k] for k in ("tool", "environment_fingerprint", "input_files", "settings")
        }
        levels = {}
        for name, lev in rec["levels"].items():
            row = {k: v for k, v in lev.items() if k not in ("rungs", "inspection", "realization")}
            if "realization" in lev:
                row["expressible"] = lev["realization"].get("expressible")
            if "rungs" in lev:
                row["rungs"] = [
                    {
                        k: e.get(k)
                        for k in ("rung", "algorithm", "method", "passes", "failed_rule", "reason")
                    }
                    | {"outer_evaluations": (e["outer"] or {}).get("n_evaluations")}
                    for e in lev["rungs"]
                ]
            levels[name] = row
        cases[cid] = {
            "available": rec["available"],
            "level": rec["level"],
            "selected_rung": rec["selected_rung"],
            "levels": levels,
            "not_available_reason": rec.get("not_available_reason"),
            "outer_evaluations": rec.get("outer_evaluations"),
            "margin": rec.get("margin"),
            "record_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        if repeat is not None:
            a = canonical(rec)
            b = canonical(
                json.loads(
                    (repeat / "results" / f"biosteam-{cid}.json").read_text(encoding="utf-8")
                )
            )
            rep[cid] = {
                "identical": a == b,
                "sha256_run1": hashlib.sha256(a).hexdigest(),
                "sha256_run2": hashlib.sha256(b).hexdigest(),
            }
    qual = {
        **(common or {}),
        "harness": harness_commit(),
        "pairs": ids,
        "not_applicable": cases9["not_applicable"],
        "cases": cases,
    }
    if repeat is not None:
        qual["repeat_run"] = {
            "statement": "the whole qualification run twice, one process per case; each record "
            "compared byte for byte after removing the wall_time* fields",
            "per_case": rep,
            "all_identical": all(v["identical"] for v in rep.values()),
        }
    (out / "qualification").mkdir(parents=True, exist_ok=True)
    (out / "qualification" / "biosteam.json").write_text(
        json.dumps(fx.finite(qual), indent=1) + "\n", encoding="utf-8"
    )
    n_ok = sum(1 for c in cases.values() if c["available"])
    same = qual.get("repeat_run", {}).get("all_identical")
    print(
        f"biosteam SUMMARY: {n_ok}/{len(ids)} available; repeat identical {same}; "
        f"fingerprint matches {common and common['environment_fingerprint']['matches']}"
    )
    return 0 if (repeat is None or same) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path)
    parser.add_argument("--case")
    parser.add_argument("--assemble", type=Path)
    parser.add_argument("--repeat", type=Path)
    args = parser.parse_args()
    cases3, cases9 = load_inputs()
    if args.assemble:
        return assemble(args.assemble.resolve(), args.repeat and args.repeat.resolve(), cases9)
    if args.case not in cases9["pairs"]:
        raise SystemExit(f"{args.case!r} is not a registered pair")
    out = args.out.resolve()
    (out / "results").mkdir(parents=True, exist_ok=True)
    rec = run_case(args.case, cases3, cases9)
    path = out / "results" / f"biosteam-{args.case}.json"
    path.write_text(json.dumps(fx.finite(rec), indent=1) + "\n", encoding="utf-8")
    print(
        f"biosteam {args.case}: available={rec['available']} level={rec['level']} "
        f"rung={rec['selected_rung']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
