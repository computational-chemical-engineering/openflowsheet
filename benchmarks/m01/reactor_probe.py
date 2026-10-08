"""M01 reactor probe: the pinned 1D ammonia reactor (no membrane) at M01's nominal point, five species.

Specification: ``docs/derivations/M01-spec.md`` section 8 (the boundary, the start strategy, the solver profile)
and section 10 (the refinement evidence). This is a *measurement* of the group's model: nothing here is an
expectation for this repository's code, and nothing in ``openflowsheet`` imports it. Its record,
``benchmarks/m01/reactor-probe.json``, is a regression record for M02 (status ``measured``, ``judged: false``).

**Environment.** A separate virtual environment outside this repository with ``pymrm==2.5.0`` and a FRESH
clone of github.com/computational-chemical-engineering/ammonia_synthesis_reactor at
6089593464fc9bc2c0a0cb58e30ad5433ece6332 installed by ``pip install -e "<clone>[test]"``. Run it from a
``git archive`` export of the pinned commit (the model reads data relative to the project root, and nothing is
then written into the clone), with this file outside the export::

    git -C <clone> archive 6089593464fc9bc2c0a0cb58e30ad5433ece6332 | tar -x -C <export>
    cd <export> && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \\
        <venv>/bin/python <repo>/benchmarks/m01/reactor_probe.py --clone <clone> --export <export> \\
        --overlay <repo>/benchmarks/m01/reactor-overlay.json --out <repo>/benchmarks/m01/reactor-probe.json

**What it runs.** The base configuration of spec section 8.5 (the geometry, catalyst and coolant of the group's
case ``G2 — GHSV sweep_1000``, every permeance pre-factor zero, five species with M01's overlay rows), the inlet
of spec section 8.4 per tube, the start strategy of section 8.7 (S1 cold at the trace inlet, S2 warm at the true
inlet, S3 polish under M01's solver profile) and its acceptance; then a grid sequence, and at the pinned grid:
an alternative start (path independence), repeats (bitwise), the backflow override's inertness, the
inert-transport surrogate's sensitivity, and two neighbouring inlet temperatures.
"""

from __future__ import annotations

import argparse
import copy
import importlib.metadata
import json
import math
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

PIN = "6089593464fc9bc2c0a0cb58e30ad5433ece6332"
SPECIES = ["H2", "N2", "NH3", "Ar", "CH4"]
Y_IN = [0.70, 0.235, 0.03, 0.015, 0.02]
T_IN = 673.15
P_IN = 1.0e7
GHSV = 1000.0
GEOMETRY_CASE = "G2 — GHSV sweep_1000"
TRACE_NH3 = 1e-9  # the group's settings.TRACE_NH3
GRIDS = (100, 200, 400, 800, 1600, 3200)
#: M01's solver profile for the polish stage S3 (spec section 8.7).
PROFILE = {"newton_rtol": 1e-12, "newton_atol": 1e-7, "steady_state_atol": 1e-6, "dt_init": 1.0, "num_timesteps": 400}
EPS_P = 1e-3  # zero-pressure-drop convention's admissibility bound on dP / P_in (ADR 0027 D2)
FLOOR_GRIDS = (100, 400)
FLOOR_STEPS = 40


def merged_database(clone_db: Path, overlay_path: Path, variant: str = "N2") -> dict[str, Any]:
    """The pinned database plus M01's overlay rows; variant 'H2' swaps the transport surrogate (sensitivity only)."""
    db = json.loads(clone_db.read_text(encoding="utf-8"))
    ov = json.loads(overlay_path.read_text(encoding="utf-8"))
    sp = db["species_properties"]["data"]
    for name, row in ov["species_properties"].items():
        new = {k: v for k, v in row.items() if k != "copy_from"}
        src = row["copy_from"]["row"] if variant == "N2" else variant
        for col in row["copy_from"]["columns"]:
            new[col] = sp[src][col]
        sp[name] = new
    bp = db["binary_properties"]["data"]
    for pair, row in ov["binary_properties"].items():
        src = row["copy_from"]
        if variant != "N2":
            a, b = pair.split("/")
            other = a if b in ("Ar", "CH4") else b
            src = "H2/NH3" if other in ("NH3",) else ("H2/N2" if other in ("N2", "Ar", "CH4") else "H2/N2")
        bp[pair] = dict(bp[src])
    return db


def dippr107_H(row: dict[str, float], T: float) -> float:
    """Antiderivative of the group's DIPPR-107 c_p (J/kmol/K): C1 T + C2 C3 coth(C3/T) - C4 C5 tanh(C5/T)."""
    c1, c2, c3, c4, c5 = (row[f"c_p_C{k}"] for k in range(1, 6))
    return c1 * T + c2 * c3 / math.tanh(c3 / T) - c4 * c5 * math.tanh(c5 / T)


def h_group(db: dict[str, Any], sp: str, T: float) -> float:
    row = db["species_properties"]["data"][sp]
    return row["dH_f"] + (dippr107_H(row, T) - dippr107_H(row, 298.15)) / 1000.0


def build(num_z: int, y_in: list[float], T_in: float, p_out: float, db_path: Path) -> tuple[Any, dict[str, float]]:
    from reactor import DEFAULTS, ReactorConfig
    from reactor.paper import case_setup, cases, settings

    t = cases.load_case_table()
    row = t[t["Case_ID"] == GEOMETRY_CASE].iloc[0]
    r_min, r_max = DEFAULTS["r_min"], float(row["r_max_m"])
    L_mem, L_seal = float(row["L_m"]), DEFAULTS["Lsealing"]
    fl = case_setup.calculate_flows(
        GHSV=GHSV, eps=DEFAULTS["eps"], Dcat=float(row["Dcat"]), rho_c=DEFAULTS["rho_c"], L_membrane=L_mem,
        Lsealing=L_seal, r_max=r_max, r_min=r_min, Nm=int(row["N_mem"]), sweep_ratio=float(row["Sweep_Ratio"]),
        H2_N2_ratio=3.0,
    )
    y_perm = [0.0, 1.0, 0.0, 0.0, 0.0]
    cfg = ReactorConfig.from_defaults(
        L=L_mem + L_seal, Lsealing=L_seal, r_min=r_min, r_max=r_max, p_ret_out=p_out,
        p_perm_out=float(row["p_perm_bar"]) * 1e5, T_ret_in=T_in, T_perm_in=T_in, T_ret_init=T_in, T_perm_init=T_in,
        F_ret_in=fl[0], F_perm_in=fl[1], y_ret_in=list(y_in), y_ret_init=list(y_in), y_perm_in=y_perm,
        y_perm_init=y_perm, Nm=int(row["N_mem"]), Dcat=float(row["Dcat"]),
        is_counter_current=bool(row["Is_Counter_Current"]), factor_react=1.0, factor_p=1.0, factor_T=1e-1,
        num_z=num_z, is_isothermal=False, species=list(SPECIES), database=str(db_path), **settings.SOLVER_1D,
    )
    for sp in SPECIES:
        setattr(cfg, f"P0_{sp}", 0.0)
        if not hasattr(cfg, f"EA_{sp}"):
            setattr(cfg, f"EA_{sp}", 0.0)
    return cfg, {"W_cat": fl[4], "A_membrane_m2": 1.0, "F_ret_in": fl[0], "F_perm_in": fl[1]}


def reactor_class(backflow: list[float]) -> Any:
    """The pinned 1D class with one instance attribute set for five species (finding F-R1, spec section 8.5)."""
    import numpy as np
    from reactor.paper import runner, settings

    base = runner._one_d_class(settings.MODEL_1D)

    class FiveSpecies1D(base):  # type: ignore[misc, valid-type]
        def _init_derived(self) -> None:
            super()._init_derived()
            bf = np.asarray(backflow, dtype=float).reshape((1, 1, self.num_c))
            self.inflow_conc_ret_backflow = self.p_ret_out / (self.Rg * self.T_ret_in) * bf

    return FiveSpecies1D


BACKFLOW_DEFAULT = [0.0, 1.0 - 1e-4, 1e-4, 0.0, 0.0]  # the pinned code's three-species value, padded with zeros


def outlet(r: Any, db: dict[str, Any], meta: dict[str, float], T_in: float) -> dict[str, Any]:
    import numpy as np

    fr, _, fp, _ = r.compute_flows()
    n_in, n_out = fr[0, :].astype(float), fr[-1, :].astype(float)
    E = {"H": [2, 0, 3, 0, 4], "N": [0, 2, 1, 0, 0], "C": [0, 0, 0, 0, 1], "Ar": [0, 0, 0, 1, 0]}
    elem = {e: float((np.dot(w, n_out) - np.dot(w, n_in)) / np.dot(w, n_in)) for e, w in E.items()}
    T_out = float(r.cpT[-1, 1, -1])
    Tp_in, Tp_out = T_in, float(r.cpT[-1, 0, -1])
    F_perm = float(np.sum(fp[0, :]))
    q_cool = F_perm * (h_group(db, "N2", Tp_out) - h_group(db, "N2", Tp_in))
    dH_ret = sum(float(n_out[i]) * h_group(db, s, T_out) - float(n_in[i]) * h_group(db, s, T_in) for i, s in enumerate(SPECIES))
    p_first = float(r.cpT[0, 1, -2])
    return {
        "inlet_face_n_mol_s": [float(v) for v in n_in],
        "outlet_n_mol_s": [float(v) for v in n_out],
        "T_out_K": T_out,
        "T_max_K": float(np.max(r.cpT[:, 1, -1])),
        "p_first_cell_Pa": p_first,
        "dP_over_P": (p_first - r.p_ret_out) / r.p_ret_out,
        "coolant_out_T_K": Tp_out,
        "coolant_flow_mol_s": F_perm,
        "coolant_heat_uptake_W": q_cool,
        "reactor_energy_defect_rel": (dH_ret + q_cool) / q_cool if q_cool != 0 else None,
        "element_defect_rel": elem,
        "permeate_composition_change": float(np.max(np.abs(fp[-1, :] - fp[0, :]))),
        "u_ret_min": float(np.min(r.u_ret_ax)),
        "min_axial_flow_mol_s": float(np.min(fr)),
    }


def strategy(num_z: int, y_in: list[float], T_in: float, db: dict[str, Any], db_path: Path,
             s2_dt: float | None = None, backflow: list[float] = BACKFLOW_DEFAULT) -> dict[str, Any]:
    from reactor.paper import kpis as kpi_mod
    from reactor.paper import runner, settings

    cls = reactor_class(backflow)
    s = sum(y_in[:2] + [TRACE_NH3] + y_in[3:])
    y_tr = [v / s for v in (y_in[:2] + [TRACE_NH3] + y_in[3:])]
    stages: dict[str, Any] = {}
    cfg1, meta = build(num_z, y_tr, T_in, P_IN, db_path)
    t0 = time.perf_counter()
    r1 = cls(config=cfg1)
    st1 = r1.solve(dt_init=settings.DT_INIT_1D, return_status=True, verbose=0)
    acc1 = kpi_mod.solver_acceptance(st1, cfg1.steady_state_atol, settings.STEADY_STATE_ACCEPT_FACTOR)
    stages["S1"] = {"accepted": bool(acc1["accepted"]), "steady_state_norm": float(st1.steady_state_norm),
                    "steps": int(st1.num_steps_attempted)}
    cfg2, meta = build(num_z, y_in, T_in, P_IN, db_path)
    nc = len(SPECIES)
    r = cls(config=cfg2, c=r1.cpT[..., :nc].copy(), p=r1.cpT[..., -2].copy(), T=r1.cpT[..., -1].copy())
    st2 = r.solve(dt_init=settings.DT_INIT_1D if s2_dt is None else s2_dt, return_status=True, verbose=0)
    acc2 = kpi_mod.solver_acceptance(st2, cfg2.steady_state_atol, settings.STEADY_STATE_ACCEPT_FACTOR)
    stages["S2"] = {"accepted": bool(acc2["accepted"]), "steady_state_norm": float(st2.steady_state_norm),
                    "steps": int(st2.num_steps_attempted), "outlet_at_group_tolerance": outlet(r, db, meta, T_in)["outlet_n_mol_s"]}
    r.rtol, r.atol = PROFILE["newton_rtol"], PROFILE["newton_atol"]
    st3 = r.solve(num_timesteps=PROFILE["num_timesteps"], dt_init=PROFILE["dt_init"],
                  steady_state_atol=PROFILE["steady_state_atol"], return_status=True, verbose=0)
    wall = time.perf_counter() - t0
    cert = runner.certify_convergence_1d(r, st3, meta)
    out = outlet(r, db, meta, T_in)
    drift = cert.get("kpi_drift_rel") or {}
    accepted = (bool(st3.converged) and cert.get("kpi_drift_ok") is True and out["u_ret_min"] > 0
                and out["min_axial_flow_mol_s"] > 0 and abs(out["dP_over_P"]) <= EPS_P)
    stages["S3"] = {"converged": bool(st3.converged), "steady_state_norm": float(st3.steady_state_norm),
                    "steps": int(st3.num_steps_attempted), "certificate_kpi_drift_ok": cert.get("kpi_drift_ok"),
                    "certificate_kpi_drift_rel_max": max(drift.values()) if drift else None,
                    "certificate_residual": float(cert.get("achieved_residual", float("nan")))}
    return {"num_z": num_z, "T_in_K": T_in, "P_in_Pa": P_IN, "y_in": list(y_in), "F_ret_in_mol_s": meta["F_ret_in"],
            "F_perm_in_mol_s": meta["F_perm_in"], "inlet_n_mol_s": [meta["F_ret_in"] * v for v in y_in],
            "stages": stages, "m01_accepted": accepted, "wall_s": round(wall, 2), **out, "_reactor": r}


def floor(r: Any) -> dict[str, Any]:
    st = r.solve(num_timesteps=FLOOR_STEPS, dt_init=PROFILE["dt_init"], steady_state_atol=1e-14,
                 return_status=True, verbose=0)
    return {"steps": FLOOR_STEPS, "best_steady_state_norm": float(st.best_steady_state_norm or st.steady_state_norm)}


def strip(rec: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in rec.items() if not k.startswith("_")}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--clone", required=True, type=Path)
    ap.add_argument("--export", required=True, type=Path)
    ap.add_argument("--overlay", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--pinned", type=int, default=1600)
    ap.add_argument("--grids", type=str, default=",".join(str(g) for g in GRIDS))
    args = ap.parse_args()
    head = subprocess.run(["git", "-C", str(args.clone), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(args.clone), "status", "--porcelain"], capture_output=True, text=True, check=True).stdout.strip()
    if head != PIN or dirty:
        print(f"clone at {head} (dirty={bool(dirty)}), expected clean {PIN}", file=sys.stderr)
        return 2
    if importlib.metadata.version("pymrm") != "2.5.0":
        print("pymrm must be exactly 2.5.0", file=sys.stderr)
        return 2
    clone_db = args.export / "src" / "reactor" / "data" / "properties_database.json"
    tmp = Path(tempfile.mkdtemp(prefix="m01-db-"))
    db = merged_database(clone_db, args.overlay)
    db_path = tmp / "db5.json"
    db_path.write_text(json.dumps(db), encoding="utf-8")
    dbh = merged_database(clone_db, args.overlay, variant="H2")
    dbh_path = tmp / "db5_h2.json"
    dbh_path.write_text(json.dumps(dbh), encoding="utf-8")

    grids = [int(g) for g in args.grids.split(",")]
    grid = []
    pinned = None
    for nz in grids:
        rec = strategy(nz, Y_IN, T_IN, db, db_path)
        if nz in FLOOR_GRIDS:
            rec["floor"] = floor(rec["_reactor"])
        if nz == args.pinned:
            pinned = rec
        grid.append(strip(rec))
        print(f"num_z={nz} accepted={rec['m01_accepted']} wall={rec['wall_s']} NH3_out={rec['outlet_n_mol_s'][2]:.10e} T_out={rec['T_out_K']:.6f}", flush=True)
    if pinned is None:
        pinned = strategy(args.pinned, Y_IN, T_IN, db, db_path)
    nzp = args.pinned
    alt = strategy(nzp, Y_IN, T_IN, db, db_path, s2_dt=1e-1)
    reps = [strategy(nzp, Y_IN, T_IN, db, db_path) for _ in range(2)]
    bfl = strategy(nzp, Y_IN, T_IN, db, db_path, backflow=[0.0, 0.0, 0.0, 1.0, 0.0])
    h2v = strategy(nzp, Y_IN, T_IN, dbh, dbh_path)
    neighbours = [strip(strategy(nzp, Y_IN, t, db, db_path)) for t in (653.15, 693.15)]
    keys = ("outlet_n_mol_s", "T_out_K", "p_first_cell_Pa")

    def rel(a: dict[str, Any], b: dict[str, Any]) -> float:
        da = max(abs(x - y) / abs(y) for x, y in zip(a["outlet_n_mol_s"], b["outlet_n_mol_s"]))
        return max(da, abs(a["T_out_K"] - b["T_out_K"]) / b["T_out_K"])

    record = {
        "record": "m01-reactor-probe",
        "version": 2,
        "status": "measured",
        "judged": False,
        "specification": "docs/derivations/M01-spec.md sections 8 and 10",
        "reactor_commit": head,
        "overlay": str(args.overlay.name),
        "environment": {
            "python": platform.python_version(), "platform": platform.platform(),
            "packages": {p: importlib.metadata.version(p) for p in ("pymrm", "numpy", "scipy", "pandas")},
            "threads": "OMP/OPENBLAS/MKL_NUM_THREADS=1",
        },
        "configuration": {"geometry_case": GEOMETRY_CASE, "species": SPECIES, "y_in": Y_IN, "T_in_K": T_IN,
                          "P_in_Pa": P_IN, "p_ret_out_Pa": P_IN, "GHSV_h": GHSV, "permeance_prefactors": "all zero",
                          "coolant": "pure N2, co-current, F_perm_in = sweep_ratio (1) x F_ret_in, T_perm_in = T_in, 1 bar",
                          "start": "S1 cold at the trace inlet (y_NH3 := 1e-9, renormalized), group SOLVER_1D and DT_INIT_1D; S2 warm at the true inlet from S1's fields, group settings; S3 polish under PROFILE",
                          "profile": PROFILE, "eps_P": EPS_P, "trace_NH3": TRACE_NH3},
        "grid": grid,
        "pinned_num_z": nzp,
        "pinned": strip(pinned),
        "path_independence": {"alternative": "S2 with dt_init = 1e-1", "max_rel_diff": rel(alt, pinned),
                              "alternative_S2_outlet_at_group_tolerance": alt["stages"]["S2"]["outlet_at_group_tolerance"]},
        "repeats": {"runs": 2, "bitwise_identical": all(all(r[k] == pinned[k] for k in keys) for r in reps)},
        "backflow_override": {"alternative_backflow": [0.0, 0.0, 0.0, 1.0, 0.0],
                              "bitwise_identical": all(bfl[k] == pinned[k] for k in keys)},
        "inert_transport_variant": {"variant": "transport columns and pairs from H2 instead of N2",
                                    "max_rel_diff": rel(h2v, pinned)},
        "neighbouring_inlet_temperatures": neighbours,
    }
    args.out.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
