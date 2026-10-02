"""T06 environment check for the IDAES reference: one of IDAES's own examples, run headless.

This is the Flash example of the IDAES unit-model documentation (benzene-toluene with the
bundled BTX property package in its ideal mode), solved with the Ipopt that `idaes
get-extensions` installs. It proves only that `.venv-idaes` imports, builds, initializes and
solves a flowsheet and that the solver binary runs on this host. Nothing here is compared with
this project, and the numbers it prints are an environment check, not reference values.

Run it from the repository root, after `scripts/build-reference-envs.sh`:

    .venv-idaes/bin/python spikes/references/idaes_smoke.py

`IDAES_DATA` defaults to `.venv-idaes/idaes-data`, where the build script put the extensions.

Not part of `scripts/check.sh`: the gate must not depend on external tools.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    # IDAES reads its data directory (binary extensions) at import time.
    os.environ.setdefault("IDAES_DATA", str(REPO_ROOT / ".venv-idaes" / "idaes-data"))
    t0 = time.perf_counter()
    import idaes
    import pyomo
    import pyomo.environ as pyo
    from idaes.core import FlowsheetBlock
    from idaes.core.util.model_statistics import degrees_of_freedom
    from idaes.models.properties.activity_coeff_models.BTX_activity_coeff_VLE import (
        BTXParameterBlock,
    )
    from idaes.models.unit_models import Flash

    m = pyo.ConcreteModel()
    m.fs = FlowsheetBlock(dynamic=False)
    m.fs.properties = BTXParameterBlock(
        valid_phase=("Liq", "Vap"), activity_coeff_model="Ideal", state_vars="FTPz"
    )
    m.fs.flash = Flash(property_package=m.fs.properties)

    m.fs.flash.inlet.flow_mol.fix(1)
    m.fs.flash.inlet.temperature.fix(368)
    m.fs.flash.inlet.pressure.fix(101325)
    m.fs.flash.inlet.mole_frac_comp[0, "benzene"].fix(0.5)
    m.fs.flash.inlet.mole_frac_comp[0, "toluene"].fix(0.5)
    m.fs.flash.heat_duty.fix(0)
    m.fs.flash.deltaP.fix(0)

    dof = degrees_of_freedom(m)
    m.fs.flash.initialize()
    solver = pyo.SolverFactory("ipopt")
    result = solver.solve(m)

    # Which linear solvers the bundled Ipopt links: records whether the HSL codes named in the
    # extension licence file are present (a licence fact, not a performance choice).
    linear_solvers = {}
    for name in ("mumps", "ma27", "ma57", "ma97"):
        probe = pyo.SolverFactory("ipopt", options={"linear_solver": name})
        try:
            status = probe.solve(m, load_solutions=False).solver.termination_condition
            linear_solvers[name] = str(status)
        except Exception as exc:  # a missing solver is the recorded outcome
            linear_solvers[name] = f"error: {type(exc).__name__}"

    report = {
        "check": "idaes-flash-btx-ideal",
        "idaes_version": idaes.__version__,
        "pyomo_version": pyomo.__version__,
        "ipopt_available": bool(solver.available()),
        "ipopt_version": ".".join(str(v) for v in solver.version()),
        "ipopt_path": shutil.which("ipopt"),
        "ipopt_linear_solvers": linear_solvers,
        "degrees_of_freedom": dof,
        "termination_condition": str(result.solver.termination_condition),
        "vap_flow_mol": pyo.value(m.fs.flash.vap_outlet.flow_mol[0]),
        "liq_flow_mol": pyo.value(m.fs.flash.liq_outlet.flow_mol[0]),
        "outlet_temperature_K": pyo.value(m.fs.flash.vap_outlet.temperature[0]),
        "wall_seconds": round(time.perf_counter() - t0, 2),
    }
    print(json.dumps(report, indent=2))
    ok = dof == 0 and report["termination_condition"] == "optimal"
    print("SMOKE", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
