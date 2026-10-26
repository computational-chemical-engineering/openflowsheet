"""S09 Amendment 1 design probe (NOT evidence): the registered identifier strings against the tool.

Written by the design lane (`specifier`) for docs/derivations/S09-spec.md §18.1. It runs no column
and no S03 case. It builds the registered thermo through the harness's own module
(spikes/references/s09_biosteam_syn001.py, which imports SYN-001's constants from t06_fixtures.py)
and compares every identifier string that a per-run check compares exactly (§4.3's
`thermo_classes` and `methods`, Q-X10's ladder, §5.4's solver signature) with the tool's objects.
For each registered class name it also says whether thermosteam.equilibrium has a class of that
spelling, and it evaluates the three equilibrium classes once at an arbitrary state.

Run with the BioSTEAM environment's interpreter, from this directory:
<venv>/bin/python -I class_probe.py > class_probe.log
"""

import inspect
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "spikes" / "references"))

import biosteam as bst  # noqa: E402
import flexsolve as flx  # noqa: E402
import numpy as np  # noqa: E402
import s09_biosteam_syn001 as syn  # noqa: E402
import t06_fixtures as fx  # noqa: E402
import thermosteam as tmo  # noqa: E402
import thermosteam.equilibrium as eq  # noqa: E402

CASES9 = json.loads((ROOT / "docs/derivations/scripts/s09_cases.json").read_text())
S9 = CASES9["tool_settings"]["BioSTEAM"]


def name_of(obj):
    return obj.__name__ if isinstance(obj, type) else type(obj).__name__


def main():
    chems, thermo = syn.build_thermo({c: float(fx.L_VAP[c]) for c in "ABC"})
    reg = S9["readback"]["thermo_classes"]
    ok = True
    for key in ("Gamma", "Phi", "PCF"):
        tool = name_of(getattr(thermo, key))
        same = tool == reg[key]
        ok &= same
        print(
            f"{key}: tool {tool!r}; registered {reg[key]!r}; equal {same}; "
            f"thermosteam.equilibrium has the registered spelling: {hasattr(eq, reg[key])}"
        )
    mix = thermo.mixture
    same = type(mix).__name__ == reg["mixture"] and type(mix) is tmo.IdealMixture
    ok &= same
    print(f"mixture: tool {type(mix).__name__!r}; registered {reg['mixture']!r}; equal {same}")
    same = bool(mix.include_excess_energies) is reg["include_excess_energies"]
    ok &= same
    print(f"include_excess_energies: tool {mix.include_excess_energies!r}; equal {same}")
    for c in chems:
        for prop in ("Psat", "Hvap"):
            model = getattr(c, prop)
            same = model.method == "USER_METHOD" and sorted(model.all_methods) == ["USER_METHOD"]
            ok &= same
            print(f"{c.ID} {prop}: method {model.method!r}, all {sorted(model.all_methods)}")
    alg = bst.MultiStageEquilibrium.default_algorithms
    meth = bst.MultiStageEquilibrium.default_methods
    tool_rungs = [[a, meth[a]] for a in alg]
    same = tool_rungs == S9["rungs"]
    ok &= same
    print(f"Q-X10 ladder: tool {tool_rungs}; equal to the registered rungs {same}")
    params = list(inspect.signature(flx.IQ_interpolation).parameters)
    expected = [
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
    ]
    same = params == expected
    ok &= same
    print(f"IQ_interpolation positional parameters: {params}; as §5.4 reads them {same}")
    x = np.array([0.2, 0.3, 0.5])
    print(
        "at T = 351 K, P = 1e5 Pa, x = (0.2, 0.3, 0.5): Gamma",
        thermo.Gamma(chems)(x, 351.0),
        "Phi",
        thermo.Phi(chems, "g")(x, 351.0, 1e5),
        "PCF",
        thermo.PCF(chems)(351.0, 1e5),
    )
    print("every registered identifier equals the tool's:", ok)


if __name__ == "__main__":
    main()
