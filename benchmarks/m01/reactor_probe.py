"""M01 reactor probe: grid refinement and repeatability of the pinned 1D ammonia reactor (no membrane).

Specification: `docs/derivations/M01-spec.md` §9.3 (the measurement that sized the pinned grid) and work
order WO-6 (which re-measures it on the final configuration). This is a *measurement* of the group's
model; nothing here is an expectation for this repository's code, and nothing in `openflowsheet`
imports it.

**Environment.** A separate virtual environment outside this repository in which a FRESH clone of
github.com/computational-chemical-engineering/ammonia_synthesis_reactor at
6089593464fc9bc2c0a0cb58e30ad5433ece6332 was installed with ``pip install "pymrm==2.5.0"`` and
``pip install -e "<clone>[test]"``. Run it from a ``git archive`` export of the pinned commit (the
model reads its data relative to the project root, and nothing is then written into the clone), with
the probe file *outside* the clone's parent directory (a directory named ``reactor`` beside the probe
shadows the installed package)::

    git -C <clone> archive 6089593464fc9bc2c0a0cb58e30ad5433ece6332 | tar -x -C <export>
    cd <export> && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \\
        PYTHONDONTWRITEBYTECODE=1 <venv>/bin/python <repo>/benchmarks/m01/reactor_probe.py \\
        --clone <clone> --out <repo>/benchmarks/m01/reactor-probe.json

**What it runs** (three species only; the inert rows of M01 §9.5 do not exist yet):

1. The M01 base configuration (spec §9.2): geometry, catalyst and coolant of the group's case
   ``G2 — GHSV sweep_1000`` (r_max 0.03 m, L 1 m plus the 0.05 m sealing length, Dcat 0.333, one
   impermeable inner tube, co-current N2 coolant at sweep ratio 1 and 1 bar), every permeance
   pre-factor zero, at the M01 nominal operating point inside the kinetics' data domain:
   T_in = 673.15 K, p_ret_out = 1e7 Pa, H2/N2 = 3, y_NH3,in = 0.03, GHSV 1000 1/h, the group's 1D
   solver settings (``settings.SOLVER_1D``) and cold start (``settings.DT_INIT_1D``).
2. A grid sequence ``num_z`` in GRIDS, each a cold solve, with the group's acceptance
   (``solver_acceptance``) and KPI-drift certificate (``certify_convergence_1d``).
3. Three repeats at ``num_z = 1600`` (bitwise repeatability on one machine).
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

PIN = "6089593464fc9bc2c0a0cb58e30ad5433ece6332"
GRIDS = (100, 200, 400, 800, 1600, 3200)
REPEAT_GRID = 1600
REPEATS = 3
NOMINAL = {"T_in_K": 673.15, "p_ret_out_Pa": 1.0e7, "H2_N2_ratio": 3.0, "y_NH3_in": 0.03, "GHSV_h": 1000.0}
GEOMETRY_CASE = "G2 — GHSV sweep_1000"


def _build(num_z: int) -> tuple[Any, dict[str, float]]:
    import numpy as np
    from reactor import DEFAULTS, ReactorConfig
    from reactor.paper import case_setup, cases, settings

    table = cases.load_case_table()
    row = table[table["Case_ID"] == GEOMETRY_CASE].iloc[0]
    r_min, r_max = DEFAULTS["r_min"], float(row["r_max_m"])
    L_mem, L_seal = float(row["L_m"]), DEFAULTS["Lsealing"]
    flows = case_setup.calculate_flows(
        GHSV=NOMINAL["GHSV_h"], eps=DEFAULTS["eps"], Dcat=float(row["Dcat"]), rho_c=DEFAULTS["rho_c"],
        L_membrane=L_mem, Lsealing=L_seal, r_max=r_max, r_min=r_min, Nm=int(row["N_mem"]),
        sweep_ratio=float(row["Sweep_Ratio"]), H2_N2_ratio=NOMINAL["H2_N2_ratio"],
    )
    F_ret_in, F_perm_in = flows[0], flows[1]
    y_nh3 = NOMINAL["y_NH3_in"]
    y_n2 = (1.0 - y_nh3) / (NOMINAL["H2_N2_ratio"] + 1.0)
    y_in = [1.0 - y_nh3 - y_n2, y_n2, y_nh3]
    cfg = ReactorConfig.from_defaults(
        L=L_mem + L_seal, Lsealing=L_seal, r_min=r_min, r_max=r_max,
        p_ret_out=NOMINAL["p_ret_out_Pa"], p_perm_out=float(row["p_perm_bar"]) * 1e5,
        T_ret_in=NOMINAL["T_in_K"], T_perm_in=NOMINAL["T_in_K"],
        T_ret_init=NOMINAL["T_in_K"], T_perm_init=NOMINAL["T_in_K"],
        F_ret_in=F_ret_in, F_perm_in=F_perm_in, y_ret_in=y_in, y_ret_init=y_in,
        Nm=int(row["N_mem"]), Dcat=float(row["Dcat"]), is_counter_current=bool(row["Is_Counter_Current"]),
        factor_react=1.0, factor_p=1.0, factor_T=1e-1, num_z=num_z, is_isothermal=False,
        **settings.SOLVER_1D,
    )
    for key in ("P0_H2", "P0_N2", "P0_NH3"):
        setattr(cfg, key, 0.0)
    del np
    return cfg, {"F_ret_in": F_ret_in, "F_perm_in": F_perm_in, "W_cat": flows[4]}


def _solve(num_z: int) -> dict[str, Any]:
    import numpy as np
    from reactor.paper import kpis as kpi_mod
    from reactor.paper import runner, settings

    cfg, meta = _build(num_z)
    design_meta = {"W_cat": meta["W_cat"], "A_membrane_m2": 1.0}
    reactor = runner._one_d_class(settings.MODEL_1D)(config=cfg)
    t0 = time.perf_counter()
    status = reactor.solve(dt_init=settings.DT_INIT_1D, return_status=True, verbose=0)
    wall = time.perf_counter() - t0
    acceptance = kpi_mod.solver_acceptance(
        status, cfg.steady_state_atol, settings.STEADY_STATE_ACCEPT_FACTOR
    )
    cert = runner.certify_convergence_1d(reactor, status, design_meta)
    fr_ax, _fr_mem, fp_ax, _fp_mem = reactor.compute_flows()
    ret_in, ret_out = fr_ax[0, :], fr_ax[-1, :]
    perm_in, perm_out = fp_ax[0, :], fp_ax[-1, :]
    # Elements over both sides (species order H2, N2, NH3).
    h_in = 2 * (ret_in[0] + perm_in[0]) + 3 * (ret_in[2] + perm_in[2])
    h_out = 2 * (ret_out[0] + perm_out[0]) + 3 * (ret_out[2] + perm_out[2])
    n_in = 2 * (ret_in[1] + perm_in[1]) + (ret_in[2] + perm_in[2])
    n_out = 2 * (ret_out[1] + perm_out[1]) + (ret_out[2] + perm_out[2])
    t_ret = reactor.cpT[:, 1, -1]
    p_ret = reactor.cpT[:, 1, -2]
    drift = cert.get("kpi_drift_rel") or {}
    return {
        "num_z": num_z,
        "solve_wall_s": round(wall, 3),
        "solve_converged": bool(status.converged),
        "solver_accepted": bool(acceptance["accepted"]),
        "steady_state_norm": float(status.steady_state_norm),
        "steps_attempted": int(status.num_steps_attempted),
        "certificate_kpi_drift_ok": cert.get("kpi_drift_ok"),
        "certificate_kpi_drift_rel_max": max(drift.values()) if drift else None,
        "certificate_achieved_residual": float(cert.get("achieved_residual", float("nan"))),
        "retentate_in_mol_s": [float(v) for v in ret_in],
        "retentate_out_mol_s": [float(v) for v in ret_out],
        "permeate_in_mol_s": [float(v) for v in perm_in],
        "permeate_out_mol_s": [float(v) for v in perm_out],
        "T_ret_last_cell_K": float(t_ret[-1]),
        "T_ret_max_K": float(np.max(t_ret)),
        "T_perm_last_cell_K": float(reactor.cpT[-1, 0, -1]),
        "p_ret_first_cell_Pa": float(p_ret[0]),
        "p_ret_out_Pa": float(cfg.p_ret_out),
        "element_H_rel": float((h_out - h_in) / h_in),
        "element_N_rel": float((n_out - n_in) / n_in),
        "F_ret_in_mol_s": float(cfg.F_ret_in),
        "y_ret_in": [float(v) for v in np.asarray(cfg.y_ret_in).ravel()],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clone", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    head = subprocess.run(
        ["git", "-C", str(args.clone), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "-C", str(args.clone), "status", "--porcelain"], capture_output=True, text=True, check=True
    ).stdout.strip()
    if head != PIN or dirty:
        print(f"clone at {head} (dirty={bool(dirty)}), expected clean {PIN}", file=sys.stderr)
        return 2
    if importlib.metadata.version("pymrm") != "2.5.0":
        print("pymrm must be exactly 2.5.0", file=sys.stderr)
        return 2
    grid = [_solve(nz) for nz in GRIDS]
    repeats = [_solve(REPEAT_GRID) for _ in range(REPEATS)]
    keys = ("retentate_out_mol_s", "T_ret_last_cell_K", "p_ret_first_cell_Pa")
    identical = all(all(r[k] == repeats[0][k] for k in keys) for r in repeats[1:])
    record = {
        "record": "m01-reactor-probe",
        "version": 1,
        "status": "measured",
        "judged": False,
        "specification": "docs/derivations/M01-spec.md §9.3",
        "reactor_commit": head,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": {p: importlib.metadata.version(p) for p in ("pymrm", "numpy", "scipy", "pandas")},
            "threads": "OMP/OPENBLAS/MKL_NUM_THREADS=1",
        },
        "configuration": {"geometry_case": GEOMETRY_CASE, "nominal": NOMINAL, "species": ["H2", "N2", "NH3"],
                          "permeance_prefactors": "P0_H2 = P0_N2 = P0_NH3 = 0"},
        "grid": grid,
        "repeats": {"num_z": REPEAT_GRID, "runs": repeats, "bitwise_identical": identical},
    }
    args.out.write_text(json.dumps(record, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
