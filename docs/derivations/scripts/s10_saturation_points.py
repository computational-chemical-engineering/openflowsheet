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
    python docs/derivations/scripts/s10_saturation_points.py --floor

``--check`` recomputes and fails (exit 1) unless the result equals the committed file: byte for
byte on ``platform.machine() == "x86_64"``, the architecture that wrote it, and elsewhere within
the classes of S10 spec section 18 A5-2 (R-723): every string, integer and temperature exactly,
every pressure within ``B_P`` = 1e-10 relative, each deviation within ``B_D`` = 2.1e-10 absolute.
CoolProp's superancillaries are switched on explicitly, because the committed pressures are their
values (A5-2). ``--floor`` asserts A5-2's floor claims F1-F3 on the running machine and prints
the measured floor. Without CoolProp 8.0.0 every mode prints ``UNAVAILABLE: CoolProp 8.0.0 not
importable`` and exits 2, never 0 (spec section 9.2, rule 5).
"""

from __future__ import annotations

import argparse
import json
import platform
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
#: Off x86-64 (S10 spec section 18 A5-2, R-723): S07's class-T bound (R-627) for every pressure,
#: relative; and for the two deviation leaves, which are (P_coolprop - P_iapws95)/P_iapws95 and its
#: maximum, the sum of their two pressures' bounds rounded up, absolute.
B_P = 1e-10
B_D = 2.1e-10
PRESSURE_KEYS = ("P_coolprop_Pa", "P_iapws95_v1_Pa")
DEVIATION_KEYS = ("relative_deviation", "worst_relative")


def compute() -> dict[str, Any]:
    import CoolProp.CoolProp as CP  # noqa: N817

    from openflowsheet.thermo.iapws95 import _saturation

    # The committed pressures are the superancillary values (S10 spec section 18 A5-2): stated
    # here, not left to CoolProp's default, so that no run takes the iterative solver silently.
    CP.set_config_bool(CP.ENABLE_SUPERANCILLARIES, True)
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


def classed_problems(committed: Any, computed: Any) -> tuple[list[str], float, float]:
    """The S10 spec section 18 A5-2 comparison: (problems, worst pressure ratio, worst deviation).

    Keys (in order), list lengths, strings, integers and every float that is not a pressure or a
    deviation (the temperatures, the grid and the limit) compare exactly. A pressure is the second
    element of a ``points_T_K_P_Pa`` pair or the value of a ``PRESSURE_KEYS`` key:
    |delta| <= B_P |committed|. A deviation is the value of a ``DEVIATION_KEYS`` key:
    |delta| <= B_D.
    """
    problems: list[str] = []
    worst = [0.0, 0.0]

    def walk(a: Any, b: Any, where: str, kind: str) -> None:
        if isinstance(a, dict) and isinstance(b, dict):
            if list(a) != list(b):
                problems.append(f"{where}: keys {list(a)} != {list(b)}")
                return
            for key in a:
                sub = (
                    "pairs"
                    if key == "points_T_K_P_Pa"
                    else "P"
                    if key in PRESSURE_KEYS
                    else "D"
                    if key in DEVIATION_KEYS
                    else "exact"
                )
                walk(a[key], b[key], f"{where}.{key}", sub)
        elif isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                problems.append(f"{where}: length {len(a)} != {len(b)}")
                return
            for i, (x, y) in enumerate(zip(a, b, strict=True)):
                sub = "pair" if kind == "pairs" else ("P" if i == 1 else "exact")
                walk(x, y, f"{where}[{i}]", sub if kind in ("pairs", "pair") else kind)
        elif type(a) is float and type(b) is float and kind == "P":
            ratio = abs(a - b) / abs(a) if a != 0.0 else (0.0 if b == 0.0 else float("inf"))
            worst[0] = max(worst[0], ratio)
            if not ratio <= B_P:
                problems.append(f"{where}: |delta|/|x| = {ratio:.3e} > {B_P:g}")
        elif type(a) is float and type(b) is float and kind == "D":
            delta = abs(a - b)
            worst[1] = max(worst[1], delta)
            if not delta <= B_D:
                problems.append(f"{where}: |delta| = {delta:.3e} > {B_D:g}")
        elif type(a) is not type(b) or a != b:
            problems.append(f"{where}: {a!r} != {b!r}")

    walk(committed, computed, "$", "exact")
    return problems, worst[0], worst[1]


def floor() -> tuple[list[str], list[str]]:
    """S10 spec section 18 A5-2's floor claims F1-F3 on this machine: (report lines, failures).

    F1: with superancillaries on, every grid pressure equals the exact rational evaluation of
    CoolProp's stored Chebyshev series (``SUPERANCILLARY.jexpansions_p``) within the a priori
    bound A = 4(n+1)^2 u sum|c_k|/|P| + |S'(x)| dx/|P| of that point (u = 2^-53).
    F2: twice the largest A is at most B_P/100, so two machines differ by at most 1 % of B_P.
    F3: with superancillaries off, at least one of the 183 points lies beyond B_P of the committed
    value, so the classed comparison tells CoolProp's iterative solver from the series.
    """
    from fractions import Fraction

    import CoolProp.CoolProp as CP  # noqa: N817

    committed = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    u = Fraction(1, 2**53)
    lines, failures = [], []
    worst_a = Fraction(0)
    beyond_all = 0
    for comp in committed["components"]:
        fluid = comp["coolprop_fluid"]
        info = json.loads(CP.get_fluid_param_string(fluid, "JSON"))
        info = info[0] if isinstance(info, list) else info
        pieces = info["EOS"][0]["SUPERANCILLARY"]["jexpansions_p"]
        CP.set_config_bool(CP.ENABLE_SUPERANCILLARIES, True)
        realized_u, bound_max, beyond = Fraction(0), Fraction(0), 0
        for t, _ in comp["points_T_K_P_Pa"]:
            piece = next(e for e in pieces if e["xmin"] <= t <= e["xmax"])
            coef = piece["coef"] if isinstance(piece["coef"], list) else json.loads(piece["coef"])
            lo, hi = Fraction(piece["xmin"]), Fraction(piece["xmax"])
            x = (2 * Fraction(t) - (lo + hi)) / (hi - lo)
            cheb, second = [Fraction(1), x], [Fraction(1), 2 * x]
            while len(cheb) < len(coef):
                cheb.append(2 * x * cheb[-1] - cheb[-2])
                second.append(2 * x * second[-1] - second[-2])
            series = sum(Fraction(c) * cheb[k] for k, c in enumerate(coef))
            slope = sum(Fraction(c) * k * second[k - 1] for k, c in enumerate(coef) if k)
            dx = u * (abs(lo + hi) + abs(2 * Fraction(t) - (lo + hi))) / (hi - lo)
            dx += 2 * u * abs(x) + u
            bound = (4 * len(coef) ** 2 * u * sum(abs(Fraction(c)) for c in coef)) / abs(series)
            bound += abs(slope) * dx / abs(series)
            realized = abs(Fraction(CP.PropsSI("P", "T", t, "Q", 0, fluid)) - series) / abs(series)
            if realized > bound:
                failures.append(
                    f"F1 {comp['id']} {t} K: {float(realized):.3e} > {float(bound):.3e}"
                )
            realized_u = max(realized_u, realized / u)
            bound_max = max(bound_max, bound)
        worst_a = max(worst_a, bound_max)
        CP.set_config_bool(CP.ENABLE_SUPERANCILLARIES, False)
        try:
            for t, p in comp["points_T_K_P_Pa"]:
                beyond += abs(CP.PropsSI("P", "T", t, "Q", 0, fluid) - p) > B_P * abs(p)
        finally:
            CP.set_config_bool(CP.ENABLE_SUPERANCILLARIES, True)
        beyond_all += beyond
        lines.append(
            f"{comp['id']}: realized {float(realized_u):.1f} u of the exact series, a priori "
            f"{float(bound_max):.3e}; without superancillaries {beyond} of "
            f"{len(comp['points_T_K_P_Pa'])} points beyond B_P"
        )
    if beyond_all == 0:
        failures.append("F3: no point beyond B_P without superancillaries")
    if not 2 * worst_a <= Fraction(B_P) / 100:
        failures.append(f"F2: 2 A = {float(2 * worst_a):.3e} > B_P/100")
    lines.append(f"two machines differ by at most {float(2 * worst_a):.3e} = 2 A (B_P {B_P:g})")
    return lines, failures


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--emit", action="store_true")
    g.add_argument("--floor", action="store_true")
    args = ap.parse_args()
    try:
        from CoolProp import __version__ as version
    except ImportError:
        version = None
    if version != COOLPROP_VERSION:
        print(f"UNAVAILABLE: CoolProp {COOLPROP_VERSION} not importable")
        return 2
    if args.floor:
        lines, failures = floor()
        print(f"floor claims F1-F3 {'FAIL' if failures else 'hold'} on {platform.machine()}")
        print("\n".join(lines + failures))
        return 1 if failures else 0
    doc = compute()
    text = dump(doc)
    worst = doc["water_crosscheck"]["worst_relative"]
    if args.emit:
        OUT_JSON.write_text(text, encoding="utf-8")
        print(f"wrote {OUT_JSON.relative_to(ROOT)}; water cross-check worst {worst:.3e}")
        return 0
    if not OUT_JSON.exists():
        print(f"water cross-check worst {worst:.3e}; saturation-points.json is absent: DIFFERS")
        return 1
    machine = platform.machine()
    if machine == "x86_64":
        ok = OUT_JSON.read_text(encoding="utf-8") == text
        print(
            f"water cross-check worst {worst:.3e}; saturation-points.json "
            f"{'matches' if ok else 'DIFFERS'} (bitwise, {machine})"
        )
        return 0 if ok else 1
    committed = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    problems, ratio, delta = classed_problems(committed, json.loads(text))
    print(
        f"water cross-check worst {worst:.3e}; saturation-points.json "
        f"{'DIFFERS' if problems else 'matches'} (classed, {machine}: worst pressure "
        f"|delta|/|x| {ratio:.3e} against {B_P:g}, worst deviation |delta| {delta:.3e} against "
        f"{B_D:g}; S10 spec section 18 A5-2)"
    )
    for problem in problems[:10]:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
