"""Saturation points for the S10 vapour-pressure fit (spec section 9.2).

Normative text: ``docs/derivations/S10-spec.md`` section 9.2. Output:
``benchmarks/s10/saturation-points.json``.

For ``Methanol``, ``Ethanol`` and ``Water`` it records CoolProp 8.0.0's
``PropsSI("P", "T", T, "Q", 0, fluid)`` at T = 290, 292, ..., 410 K (61 points), with the CoolProp
version, its gitrevision and the BibTeX key of each reference equation of state. Water is
cross-checked against ``iapws95-v1`` at five temperatures (Q-N7); the relative deviation is
recorded and must be at most 1e-8.

These are tool output: no equation-of-state coefficient is reproduced (rights row S10-RC-03). The
fit itself (section 9.3) is ``s10_records.py``'s.

Run from the repository root, in an environment with CoolProp 8.0.0 and ``PYTHONPATH=src`` (for
the ``iapws95-v1`` cross-check), for example ``~/.cache/of-rca-6fec822/venv-xcheck``::

    python docs/derivations/scripts/s10_saturation_points.py --check
    python docs/derivations/scripts/s10_saturation_points.py --emit

``--check`` recomputes and fails (exit 1) unless the result equals the committed file. Without
CoolProp 8.0.0 it prints ``UNAVAILABLE: CoolProp 8.0.0 not importable`` and exits 2, never 0
(spec section 9.2, rule 5).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
OUT_JSON = ROOT / "benchmarks" / "s10" / "saturation-points.json"

COOLPROP_VERSION = "8.0.0"
#: (record id, CoolProp fluid name), in the records' component order (spec section 9.5).
FLUIDS = (("CH3OH", "Methanol"), ("C2H5OH", "Ethanol"), ("H2O", "Water"))
#: The fit grid: 290, 292, ..., 410 K (spec section 9.2).
GRID = tuple(float(290 + 2 * k) for k in range(61))
#: The five water cross-check temperatures (Q-N7; build decision B-19): the grid's ends, its
#: middle and the quarter points.
XCHECK_T = (290.0, 320.0, 350.0, 380.0, 410.0)
XCHECK_LIMIT = 1e-8


def compute() -> dict[str, Any]:
    import CoolProp.CoolProp as CP  # noqa: N817

    from openflowsheet.thermo.iapws95 import _saturation

    components = []
    for cid, fluid in FLUIDS:
        points = [[t, CP.PropsSI("P", "T", t, "Q", 0, fluid)] for t in GRID]
        components.append(
            {
                "id": cid,
                "coolprop_fluid": fluid,
                "eos_bibtex_key": CP.get_BibTeXKey(fluid, "EOS"),
                "points_T_K_P_Pa": points,
            }
        )
    xcheck = []
    for t in XCHECK_T:
        sat = _saturation(t)
        if sat is None:
            raise RuntimeError(f"iapws95-v1 saturation did not converge at {t} K")
        p_cp = CP.PropsSI("P", "T", t, "Q", 0, "Water")
        xcheck.append(
            {
                "T_K": t,
                "P_coolprop_Pa": p_cp,
                "P_iapws95_v1_Pa": sat.pressure,
                "relative_deviation": (p_cp - sat.pressure) / sat.pressure,
            }
        )
    worst = max(abs(e["relative_deviation"]) for e in xcheck)
    if not worst <= XCHECK_LIMIT:
        raise RuntimeError(f"water cross-check {worst:.3e} exceeds {XCHECK_LIMIT:g} (spec 9.2)")
    return {
        "schema_version": 1,
        "what": "Saturated-liquid pressures P = PropsSI('P','T',T,'Q',0,fluid) on the S10 "
        "vapour-pressure fit grid (S10 spec section 9.2). Tool output; no EOS coefficient is "
        "reproduced (rights row S10-RC-03).",
        "generator": "docs/derivations/scripts/s10_saturation_points.py",
        "coolprop": {
            "version": CP.get_global_param_string("version"),
            "gitrevision": CP.get_global_param_string("gitrevision"),
            "license": "MIT",
        },
        "grid_T_K": {"first": GRID[0], "last": GRID[-1], "step": 2.0, "count": len(GRID)},
        "components": components,
        "water_crosscheck": {
            "reference": "iapws95-v1 (openflowsheet.thermo.iapws95._saturation(T).pressure, "
            "the Maxwell solve; Q-N7, build decision B-19)",
            "limit_relative": XCHECK_LIMIT,
            "worst_relative": worst,
            "points": xcheck,
        },
    }


def dump(doc: dict[str, Any]) -> str:
    return json.dumps(doc, indent=1) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--emit", action="store_true")
    args = ap.parse_args()
    try:
        from CoolProp import __version__ as version
    except ImportError:
        version = None
    if version != COOLPROP_VERSION:
        print(f"UNAVAILABLE: CoolProp {COOLPROP_VERSION} not importable")
        return 2
    doc = compute()
    text = dump(doc)
    worst = doc["water_crosscheck"]["worst_relative"]
    if args.emit:
        OUT_JSON.write_text(text, encoding="utf-8")
        print(f"wrote {OUT_JSON.relative_to(ROOT)}; water cross-check worst {worst:.3e}")
        return 0
    ok = OUT_JSON.exists() and OUT_JSON.read_text(encoding="utf-8") == text
    print(
        f"water cross-check worst {worst:.3e}; saturation-points.json "
        f"{'matches' if ok else 'DIFFERS'}"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
