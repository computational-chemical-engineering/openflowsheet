"""S06 reference generator: column specifications by purity, recovery and stage temperature.

Derived from ``docs/derivations/S06-spec.md`` and evaluated with mpmath at 50 significant digits.
It imports nothing from ``openflowsheet``. It reuses the S02 generator (``s02_reference.py``, itself
independent of ``src/``) for SYN-001's closed forms, the generator's column formulation (8 unknowns
per equilibrium stage, quotient equilibrium rows), S02 §6's initializer and S02 §18.2's
bubble-point endpoint, and adds the inverse slot rows in quotient form (spec §11). The static
refusals of spec §5 are decided here in exact rational arithmetic, by a method of this file.

Usage::

    python docs/derivations/scripts/s06_reference.py --check
    python docs/derivations/scripts/s06_reference.py \
        --emit docs/derivations/scripts/s06_reference.json

``--check`` re-derives every claim (four worker processes; a few minutes) and byte-compares the
committed ``s06_reference.json``; it refuses to emit when a claim fails.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from collections.abc import Sequence
from fractions import Fraction
from multiprocessing import Pool
from pathlib import Path
from typing import Any

from mpmath import mp, mpf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s02_reference as s2  # noqa: E402  (SYN-001, the S02 column formulation and endpoint)

DEFAULT_OUT = Path(__file__).with_name("s06_reference.json")
S02_JSON = Path(__file__).with_name("s02_reference.json")
NC = s2.NC
PATH_STEPS = 16  # spec §7: the straight path the generator follows (S02 §11's)
FINE_STEPS = 64  # spec §9 U1: the same path at a quarter of the step
SIGMA_REGULAR = mpf("1e-4")  # spec §9: registered roots are regular above this (S02's bound)
ZERO = mpf("1e-30")  # a quantity the generator's Newton (tolerance 1e-40) drives to zero
AGREE = mpf("1e-15")  # spec §9 V-sets: matched roots agree with S02's 25-digit registered roots
BAND_MARGIN = mpf(1)  # spec §5 I4: registered probes and targets sit at least 1 K from a band end
END = {"condenser": 0, "reboiler": 1}
DIRECT = {
    "reflux_ratio": "RR",
    "boilup_ratio": "BR",
    "distillate_rate": "D",
    "bottoms_rate": "B",
    "duty": "Q",
}
INVERSE = ("purity", "recovery", "temperature")
CLAIMS: list[str] = []


def claim(condition: bool, text: str) -> None:
    if not condition:
        raise SystemExit(f"claim failed: {text}")
    CLAIMS.append(text)


s = s2.s


# -- spec §4: SYN-001 saturation temperatures and the stage band -------------------------------
def t_sat(i: int, p: Any) -> Any:
    """Root of ln K_i(T, P) = 0 in closed form (spec §4):
    T_sat,i(P) = (L_i - V_i (P - P_ref)) / (L_i / T_b,i + R ln(P_ref / P))."""
    return (s2.L_VAP[i] - s2.V_MOL[i] * (p - s2.P_REF)) / (
        s2.L_VAP[i] / s2.T_BOIL[i] + s2.R * mp.log(s2.P_REF / p)
    )


def band(feed: Sequence[Any], p: Any) -> tuple[Any, Any]:
    present = [t_sat(i, p) for i in range(NC) if feed[i] > 0]
    return min(present), max(present)


# -- the cases (spec §9) ------------------------------------------------------------------------
# end -> (kind, attribute, value): attribute = component index (purity, recovery), stage
# (temperature) or None; value None means "the base case's root value" (the matched sets).
CASES: dict[str, tuple[str, dict[str, tuple[str, Any, Any]]]] = {
    "J1": ("M1", {"condenser": ("purity", 0, "0.85"), "reboiler": ("boilup_ratio", None, "1.5")}),
    "J2": (
        "M2",
        {"condenser": ("recovery", 0, "0.9"), "reboiler": ("bottoms_rate", None, "0.7")},
    ),
    "J3": ("M1", {"condenser": ("reflux_ratio", None, "2"), "reboiler": ("temperature", 6, "368")}),
    "J4": ("M1", {"condenser": ("purity", 0, "0.82"), "reboiler": ("purity", 2, "0.46")}),
    "J5": ("M3", {"reboiler": ("temperature", 5, "395")}),
    "J6": (
        "M2",
        {"condenser": ("temperature", 1, "330"), "reboiler": ("bottoms_rate", None, "0.55")},
    ),
    "J7": ("M4", {"condenser": ("recovery", 0, "0.9")}),
    "J8": ("M2", {"condenser": ("reflux_ratio", None, "1.5"), "reboiler": ("recovery", 2, "0.99")}),
}
MATCHED: dict[str, tuple[str, dict[str, tuple[str, Any, Any]]]] = {
    "V-M1-purity+boilup_ratio": (
        "M1",
        {"condenser": ("purity", 0, None), "reboiler": ("boilup_ratio", None, "1.5")},
    ),
    "V-M1-reflux_ratio+temperature": (
        "M1",
        {"condenser": ("reflux_ratio", None, "2"), "reboiler": ("temperature", 6, None)},
    ),
    "V-M1-purity+purity": (
        "M1",
        {"condenser": ("purity", 0, None), "reboiler": ("purity", 2, None)},
    ),
    "V-M1-recovery+recovery": (
        "M1",
        {"condenser": ("recovery", 0, None), "reboiler": ("recovery", 1, None)},
    ),
}
UNREACHED = {
    "U1": ("M2", {"condenser": ("temperature", 1, None), "reboiler": ("recovery", 2, None)}),
    "U2": ("M2", {"condenser": ("recovery", 0, None), "reboiler": ("bottoms_rate", None, "0.55")}),
}
ILL_CONDITIONED = ("U1",)  # spec §7.2: endpoints measured below SIGMA_REGULAR


def end_stage(case: dict[str, Any], end: str) -> int:
    return 1 if end == "condenser" else case["N"]


def top_flows(case: dict[str, Any], st: dict[str, Any]) -> list[Any]:
    if s2.is_total(case):
        return [(1 - st["phi"]) * st["v"][2][i] for i in range(NC)]
    return list(st["v"][1])


def product(case: dict[str, Any], st: dict[str, Any], end: str) -> list[Any]:
    return top_flows(case, st) if end == "condenser" else list(st["l"][case["N"]])


def quantity(case: dict[str, Any], st: dict[str, Any], end: str, kind: str, attr: Any) -> Any:
    """The specified quantity of an inverse specification (spec §2, quotient form)."""
    if kind == "temperature":
        return st["Tc"] if attr == 1 and s2.is_total(case) else st["T"][attr]
    flows = product(case, st, end)
    if kind == "purity":
        return flows[attr] / sum(flows)
    return flows[attr] / s2.feed_total(case)[0][attr]


def implementation_parameter(
    case: dict[str, Any], st: dict[str, Any], end: str, kind: str, attr: Any
) -> Any:
    """The variable the implementation's slot row pins (spec §2): T_s, n_c, or u = F x_c."""
    if kind == "temperature":
        return quantity(case, st, end, kind, attr)
    flows = product(case, st, end)
    if kind == "recovery":
        return flows[attr]
    return s2.feed_total(case)[1] * flows[attr] / sum(flows)


def target_parameter(case: dict[str, Any], kind: str, attr: Any, value: Any) -> Any:
    """The implementation's pinned slot parameter: T*, nu* = r* F_c, or pi* = x* F (spec §2)."""
    feed, total = s2.feed_total(case)
    if kind == "temperature":
        return value
    return value * feed[attr] if kind == "recovery" else value * total


def build_case(base: str, spec: dict[str, tuple[str, Any, Any]], name: str) -> dict[str, Any]:
    """S02's base case with its end specifications replaced; an inverse end's S02 slot is a duty
    placeholder (it opens the CMO stage ratio in S02 §18.2 step 1 and is overwritten in rows)."""
    case = copy.deepcopy(s2.CASES[base])
    case["name"], case["base"], case["inverse"], case["spec"] = name, base, {}, {}
    for end, (kind, attr, value) in spec.items():
        if kind in INVERSE:
            case["spec"][end] = ("duty", "0")
            case["inverse"][end_stage(case, end)] = (end, kind, attr, mpf(value))
        else:
            case["spec"][end] = (kind, value)
    return case


def slot_row(case: dict[str, Any], j: int) -> int:
    if j == 1 and s2.is_total(case):
        return -1
    return s2.eq_stages(case).index(j) * (2 * NC + 2) + 2 * NC + 1


def residual(
    case: dict[str, Any], x: Sequence[Any], direct: dict, inverse: dict, sig: Sequence[str]
) -> list[Any]:
    """S02's generator rows with every inverse slot row overwritten by its quotient form."""
    rows = s2.residual(case, x, direct, sig)
    st = s2.unpack(case, x)
    for j, (end, kind, attr, value) in inverse.items():
        scale = s2.SCALE_T if kind == "temperature" else mpf(1)
        rows[slot_row(case, j)] = (quantity(case, st, end, kind, attr) - value) / scale
    return rows


def sigma_min(case: dict[str, Any], x: Sequence[Any], direct: dict, inverse: dict) -> Any:
    two = ["TWO_PHASE"] * case["N"]
    jac = s2.jacobian(lambda y: residual(case, y, direct, inverse, two), x)
    scales = s2.col_scales(case)
    for r in range(jac.rows):
        for k in range(jac.cols):
            jac[r, k] *= scales[k]
    with mp.workdps(40):
        return min(mp.svd_r(jac, compute_uv=False))


def dof(case: dict[str, Any]) -> dict[str, int]:
    n_eq, n_in = len(s2.eq_stages(case)), len(case["inlets"])
    total = int(s2.is_total(case))
    purity = sum(1 for (_, kind, _, _) in case["inverse"].values() if kind == "purity")
    cols = 14 * n_eq + (NC + 2) * n_in + (2 * NC + 5) * total + purity
    out = {
        "columns": cols,
        "rows": cols,
        "s02_columns": cols - purity,
        "purity_columns": purity,
        "column_specifications": len(case["spec"]),
    }
    claim(out["columns"] == out["rows"], f"{case['name']}: square ({cols})")
    return out


# -- the path (spec §7) -------------------------------------------------------------------------
def endpoint(case: dict[str, Any]) -> dict[str, Any]:
    """S02 §18.2 unchanged: the inverse end takes the CMO stage ratio (or phi0) like a duty end."""
    init = s2.initializer(case)
    direct = s2.target_slots(case)
    bp = s2.bubble_point(case, init, direct)
    st0 = bp["st"]
    cont = {j: v for j, v in direct.items() if v[0] in ("Q", "D", "B") and j not in case["inverse"]}
    p0 = {j: s2.slot_value(case, st0, j, kind) for j, (kind, _) in cont.items()}
    q0 = {j: quantity(case, st0, *spec[:3]) for j, spec in case["inverse"].items()}
    return {"init": init, "direct": direct, "bp": bp, "st0": st0, "cont": cont, "p0": p0, "q0": q0}


def level(ep: dict[str, Any], case: dict[str, Any], lam: Any) -> tuple[dict, dict]:
    direct = dict(ep["direct"])
    for j, (kind, value) in ep["cont"].items():
        direct[j] = (kind, value + (1 - lam) * (ep["p0"][j] - value))
    inverse = {}
    for j, (end, kind, attr, value) in case["inverse"].items():
        inverse[j] = (end, kind, attr, value + (1 - lam) * (ep["q0"][j] - value))
    return direct, inverse


def follow(
    case: dict[str, Any], ep: dict[str, Any], steps: int
) -> tuple[list[Any] | None, int, str]:
    """Spec §7: the straight path in `steps` equal lambda-steps. Returns (root, steps, "") or
    (None, the failed step, "newton" | "state"): the corrector failed, or its root left the
    domain, the two-phase region or 0 < phi < 1 (S02's state check)."""
    two = ["TWO_PHASE"] * case["N"]
    x = s2.pack(case, ep["st0"])
    for k in range(1, steps + 1):
        direct, inverse = level(ep, case, mpf(k) / steps)
        try:
            x = s2.newton(lambda y, d=direct, v=inverse: residual(case, y, d, v, two), x)
        except SystemExit:
            return None, k, "newton"
        try:
            s2.check_state(f"{case['name']} path step {k}/{steps}", case, s2.unpack(case, x), two)
        except SystemExit:
            return None, k, "state"
    return x, steps, ""


def continued_record(case: dict[str, Any], ep: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for j, (kind, value) in sorted(ep["cont"].items()):
        out[str(j)] = {"kind": kind, "p0": s(ep["p0"][j]), "target": s(value)}
    for j, (end, kind, attr, value) in sorted(case["inverse"].items()):
        out[str(j)] = {
            "kind": kind,
            "end": end,
            "attribute": attr,
            "q0": s(ep["q0"][j]),
            "target": s(value),
            "p0": s(implementation_parameter(case, ep["st0"], end, kind, attr)),
            "parameter": s(target_parameter(case, kind, attr, value)),
        }
    return out


def identity_at_endpoint(case: dict[str, Any], ep: dict[str, Any]) -> Any:
    """Every row at x0 with the continued slots at their p0 and the inverse slots at q0 (S02 §18.2's
    identity, extended): the worst row."""
    direct, inverse = level(ep, case, mpf(0))
    return max(
        abs(r)
        for r in residual(
            case, s2.pack(case, ep["st0"]), direct, inverse, ["TWO_PHASE"] * case["N"]
        )
    )


def solve(case: dict[str, Any]) -> dict[str, Any]:
    name, two = case["name"], ["TWO_PHASE"] * case["N"]
    ep = endpoint(case)
    s2.check_state(f"{name} bubble_point", case, ep["st0"], two)
    claim(identity_at_endpoint(case, ep) < ZERO, f"{name}: x0 is a root of H(., 0) below 1e-30")
    x, _, _ = follow(case, ep, PATH_STEPS)
    claim(x is not None, f"{name}: the straight path reaches lambda = 1 in {PATH_STEPS} steps")
    assert x is not None
    st = s2.unpack(case, x)
    s2.check_state(f"{name} target", case, st, two)
    s2.closures(name, case, st)
    smin = sigma_min(case, x, ep["direct"], case["inverse"])
    claim(smin > SIGMA_REGULAR, f"{name}: target regular, sigma_min > 1e-4")
    placeholders = dict(ep["direct"])
    for j in case["inverse"]:
        placeholders[j] = ("Q", st["Q"][j])
    claim(
        s2.implementation_rows_max(case, st, placeholders, two) < mpf("1e-38"),
        f"{name}: S02's division-free rows vanish below 1e-38 at the target",
    )
    values = {}
    for _j, (end, kind, attr, value) in sorted(case["inverse"].items()):
        got = quantity(case, st, end, kind, attr)
        impl = implementation_parameter(case, st, end, kind, attr)
        claim(
            abs(got - value) < ZERO
            and abs(impl - target_parameter(case, kind, attr, value)) < ZERO,
            f"{name}: the {end} {kind} and its implementation row hold at the target",
        )
        values[end] = {"kind": kind, "value": s(got), "parameter": s(impl)}
    bp_rec = s2.record(case, ep["st0"])
    bp_rec["rho"] = {str(j): s(r) for j, r in sorted(ep["bp"]["rho"].items())}
    bp_rec["sweeps_to_1e-9_K"] = ep["bp"]["sweeps_impl"]
    return {
        "x": x,
        "st": st,
        "ep": ep,
        "out": {
            "base": case["base"],
            "dof": dof(case),
            "bubble_point": bp_rec,
            "continued": continued_record(case, ep),
            "target": s2.record(case, st),
            "signature": s2.CASES[case["base"]]["signature"],
            "spec_values": s2.spec_values(case, st),
            "inverse_values": values,
            "sigma_min": mp.nstr(smin, 6),
        },
    }


# -- matched and unreached sets (spec §9) --------------------------------------------------------
def s02_root(base: str) -> dict[str, Any]:
    """S02's registered target, rebuilt as a generator state from s02_reference.json."""
    case = s2.CASES[base]
    rec = json.loads(S02_JSON.read_text())["cases"][base]["target"]
    st: dict[str, Any] = {"l": {}, "v": {}, "T": {}, "Q": {}}
    for stage in rec["stages"]:
        j = stage["stage"]
        st["Q"][j] = mpf(stage["Q"])
        if stage.get("kind") == "total_condenser":
            st["phi"], st["Tc"] = mpf(stage["phi"]), mpf(stage["T"])
            continue
        st["l"][j], st["v"][j] = [mpf(v) for v in stage["l"]], [mpf(v) for v in stage["v"]]
        st["T"][j] = mpf(stage["T"])
    st["x"] = s2.pack(case, st)
    return st


def matched_spec(
    base: str, spec: dict[str, tuple[str, Any, Any]]
) -> dict[str, tuple[str, Any, Any]]:
    """A value None becomes the base root's value of that quantity, as a 25-digit decimal string."""
    case, root, out = build_case(base, {}, base), s02_root(base), {}
    for end, (kind, attr, value) in spec.items():
        if value is None:
            value = s(quantity(case, root, end, kind, attr))
        out[end] = (kind, attr, value)
    return out


def deviation(case: dict[str, Any], x: Sequence[Any], ref: Sequence[Any]) -> Any:
    scales = s2.col_scales(case)
    return max(abs(a - b) / sc for a, b, sc in zip(x, ref, scales, strict=True))


def job(key: str) -> tuple[str, dict[str, Any], list[str], list[str]]:
    """One registered set, run in a worker process; returns its record and its claims in order. A
    failed claim comes back as an error (a SystemExit in a worker would hang the pool)."""
    try:
        return run_job(key)
    except SystemExit as failure:
        return key, {"error": str(failure)}, [], []


def run_job(key: str) -> tuple[str, dict[str, Any], list[str], list[str]]:
    CLAIMS.clear()
    s2.CLAIMS.clear()
    if key in CASES:
        base, spec = CASES[key]
        out = solve(build_case(base, spec, key))["out"]
    elif key in MATCHED:
        base, spec = MATCHED[key]
        spec = matched_spec(base, spec)
        case = build_case(base, spec, key)
        root = s02_root(base)
        sol = solve(case)
        dev = deviation(case, sol["x"], root["x"])
        claim(
            dev < AGREE, f"{key}: the inverse set returns {base}'s registered root (scaled 1e-15)"
        )
        out = {
            "base": base,
            "spec": {e: [k, a, v] for e, (k, a, v) in spec.items()},
            "dof": sol["out"]["dof"],
            "continued": sol["out"]["continued"],
            "sigma_min": sol["out"]["sigma_min"],
            "deviation_from_s02_root": mp.nstr(dev, 3),
        }
    else:
        base, spec = UNREACHED[key]
        spec = matched_spec(base, spec)
        case = build_case(base, spec, key)
        root = s02_root(base)
        ep = endpoint(case)
        s2.check_state(f"{key} bubble_point", case, ep["st0"], ["TWO_PHASE"] * case["N"])
        at_root = sigma_min(case, root["x"], ep["direct"], case["inverse"])
        claim(at_root > SIGMA_REGULAR, f"{key}: {base}'s root is a regular root of this set")
        at_x0 = sigma_min(case, s2.pack(case, ep["st0"]), *level(ep, case, mpf(0)))
        if key in ILL_CONDITIONED:
            claim(
                at_x0 < SIGMA_REGULAR, f"{key}: the endpoint is ill-conditioned, sigma_min < 1e-4"
            )
        fails = {}
        for steps in (PATH_STEPS, FINE_STEPS):
            x, k, reason = follow(case, ep, steps)
            claim(x is None, f"{key}: the straight path in {steps} steps does not reach lambda = 1")
            fails[str(steps)] = {"step": k, "reason": reason}
        out = {
            "base": base,
            "spec": {e: [k, a, v] for e, (k, a, v) in spec.items()},
            "continued": continued_record(case, ep),
            "sigma_min_at_root": mp.nstr(at_root, 6),
            "sigma_min_at_endpoint": mp.nstr(at_x0, 6),
            "path_fails": fails,
        }
    return key, out, list(s2.CLAIMS), list(CLAIMS)


# -- static refusals (spec §5, I1-I6), decided exactly ------------------------------------------
def frac(value: Any) -> Fraction:
    return Fraction(str(value))


def null_space(rows: list[list[Fraction]], rhs: list[Fraction], n: int) -> tuple[Any, Any]:
    """Exact Gauss-Jordan: (t0, basis) with A (t0 + basis s) = b; (None, None) if inconsistent."""
    a = [row[:] + [b] for row, b in zip(rows, rhs, strict=True)]
    pivots, r = [], 0
    for c in range(n):
        pr = next((k for k in range(r, len(a)) if a[k][c] != 0), None)
        if pr is None:
            continue
        a[r], a[pr] = a[pr], a[r]
        a[r] = [v / a[r][c] for v in a[r]]
        for k in range(len(a)):
            if k != r and a[k][c] != 0:
                a[k] = [vk - a[k][c] * vr for vk, vr in zip(a[k], a[r], strict=True)]
        pivots.append(c)
        r += 1
    if any(all(v == 0 for v in row[:n]) and row[n] != 0 for row in a):
        return None, None
    free = [c for c in range(n) if c not in pivots]
    t0 = [Fraction(0)] * n
    for k, c in enumerate(pivots):
        t0[c] = a[k][n]
    basis = []
    for f in free:
        vec = [Fraction(0)] * n
        vec[f] = Fraction(1)
        for k, c in enumerate(pivots):
            vec[c] = -a[k][f]
        basis.append(vec)
    return t0, basis


def split_feasible(feed: list[Fraction], rows: list[list[Fraction]], rhs: list[Fraction]) -> bool:
    """Spec §5 I6: is there a top-product split t with 0 < t_i < F_i (present i) meeting rows?"""
    present = [i for i in range(NC) if feed[i] > 0]
    sub = [[row[i] for i in present] for row in rows]
    t0, basis = null_space(sub, rhs, len(present))
    if t0 is None:
        return False
    box = [feed[i] for i in present]
    if not basis:
        return all(0 < t0[k] < box[k] for k in range(len(present)))
    if len(basis) == 1:
        lo, hi = -math.inf, math.inf
        for k in range(len(present)):
            d = basis[0][k]
            if d == 0:
                if not 0 < t0[k] < box[k]:
                    return False
                continue
            a_, b_ = (-t0[k]) / d, (box[k] - t0[k]) / d
            lo, hi = max(lo, min(a_, b_)), min(hi, max(a_, b_))
        return lo < hi
    if len(sub) == 1:  # one row in three unknowns: the open box's image of the row is an interval
        row = sub[0]
        low = sum(min(Fraction(0), row[k] * box[k]) for k in range(len(present)))
        high = sum(max(Fraction(0), row[k] * box[k]) for k in range(len(present)))
        return low < rhs[0] < high
    return True  # no row linear in the split


def linear_rows(feed: list[Fraction], specs: dict[str, tuple[str, Any, Any]]) -> tuple[list, list]:
    """Spec §5 I5-I6: the end specifications that are linear in the top split t (F - t is the
    bottom), as rows a.t = b."""
    total = sum(feed)
    rows, rhs = [], []
    for end, (kind, attr, value) in specs.items():
        v = frac(value)
        one = [Fraction(1)] * NC
        unit = [Fraction(int(i == attr)) for i in range(NC)]
        if kind == "distillate_rate":
            row, b = one, v
        elif kind == "bottoms_rate":
            row, b = one, total - v
        elif kind == "purity" and end == "condenser":
            row, b = [unit[i] - v for i in range(NC)], Fraction(0)
        elif kind == "purity":
            row, b = [v - unit[i] for i in range(NC)], v * total - feed[attr]
        elif kind == "recovery":
            row, b = unit, (v if end == "condenser" else 1 - v) * feed[attr]
        else:
            continue
        rows.append(row)
        rhs.append(b)
    return rows, rhs


def rank(rows: list[list[Fraction]]) -> int:
    t0, basis = null_space(rows, [Fraction(0)] * len(rows), NC)
    assert basis is not None
    return NC - len(basis)


def refusal(
    n_stages: int, pressures: Sequence[Any], feed: list[Fraction], specs: dict[str, Any]
) -> str | None:
    """Spec §5's I1-I6 in order, on a specification that passed S02's S1-S10 (inverse kinds only
    where the check names them)."""
    for end, (kind, attr, value) in specs.items():
        if kind not in INVERSE:
            continue
        if (kind == "temperature" and attr not in range(1, n_stages + 1)) or (
            kind != "temperature" and attr not in range(NC)
        ):
            return f"invalid_spec({kind}:{end})"  # I1
        number = float(value)
        if not math.isfinite(number) or (kind != "temperature" and not 0 < frac(value) < 1):
            return f"invalid_spec({kind}:{end})"  # I2
    for end, (kind, attr, _) in specs.items():
        if kind in ("purity", "recovery") and feed[attr] == 0:
            return f"infeasible_spec(absent_component:{end})"  # I3
    for _end, (kind, attr, value) in specs.items():
        if kind == "temperature":
            lo, hi = band([mpf(f.numerator) / f.denominator for f in feed], pressures[attr - 1])
            if not lo < mpf(value) < hi:
                return f"infeasible_spec(temperature_outside_band:{attr})"  # I4
    kinds = list(specs.values())
    temps = [a for (k, a, _) in kinds if k == "temperature"]
    rows, rhs = linear_rows(feed, specs)
    if len(temps) != len(set(temps)) or (rows and rank(rows) < len(rows)):
        return "invalid_spec(redundant_specification)"  # I5
    if not split_feasible(feed, rows, rhs):
        return "infeasible_spec(mass_balance)"  # I6
    return None


DYADIC = ("0.25", "0.5", "0.25")
PROBES: list[tuple[str, str, tuple[str, ...], dict[str, tuple[str, Any, Any]], str | None]] = [
    (
        "I1-component",
        "M1",
        s2.FEED,
        {"condenser": ("purity", 3, "0.8"), "reboiler": ("boilup_ratio", None, "1.5")},
        "invalid_spec(purity:condenser)",
    ),
    (
        "I1-stage",
        "M1",
        s2.FEED,
        {"condenser": ("reflux_ratio", None, "2"), "reboiler": ("temperature", 8, "360")},
        "invalid_spec(temperature:reboiler)",
    ),
    (
        "I2-purity-one",
        "M1",
        s2.FEED,
        {"condenser": ("purity", 0, "1"), "reboiler": ("boilup_ratio", None, "1.5")},
        "invalid_spec(purity:condenser)",
    ),
    (
        "I2-recovery-zero",
        "M1",
        s2.FEED,
        {"condenser": ("reflux_ratio", None, "2"), "reboiler": ("recovery", 2, "0")},
        "invalid_spec(recovery:reboiler)",
    ),
    (
        "I2-temperature-nan",
        "M1",
        s2.FEED,
        {"condenser": ("reflux_ratio", None, "2"), "reboiler": ("temperature", 6, "nan")},
        "invalid_spec(temperature:reboiler)",
    ),
    (
        "I3-absent",
        "M1",
        ("0", "0.5", "0.5"),
        {"condenser": ("reflux_ratio", None, "2"), "reboiler": ("recovery", 0, "0.9")},
        "infeasible_spec(absent_component:reboiler)",
    ),
    (
        "I4-above",
        "M1",
        s2.FEED,
        {"condenser": ("reflux_ratio", None, "2"), "reboiler": ("temperature", 6, "405")},
        "infeasible_spec(temperature_outside_band:6)",
    ),
    (
        "I4-below",
        "M1",
        s2.FEED,
        {"condenser": ("temperature", 1, "315"), "reboiler": ("boilup_ratio", None, "1.5")},
        "infeasible_spec(temperature_outside_band:1)",
    ),
    (
        "I5-recovery",
        "M1",
        s2.FEED,
        {"condenser": ("recovery", 0, "0.9"), "reboiler": ("recovery", 0, "0.05")},
        "invalid_spec(redundant_specification)",
    ),
    (
        "I5-temperature",
        "M1",
        s2.FEED,
        {"condenser": ("temperature", 4, "355"), "reboiler": ("temperature", 4, "356")},
        "invalid_spec(redundant_specification)",
    ),
    (
        "I5-purity",
        "M1",
        s2.FEED,
        {"condenser": ("purity", 1, "0.4"), "reboiler": ("purity", 1, "0.4")},
        "invalid_spec(redundant_specification)",
    ),
    (
        "I6-purity-purity",
        "M1",
        s2.FEED,
        {"condenser": ("purity", 0, "0.85"), "reboiler": ("purity", 2, "0.5")},
        "infeasible_spec(mass_balance)",
    ),
    (
        "I6-purity-recovery",
        "M1",
        s2.FEED,
        {"condenser": ("purity", 0, "0.9"), "reboiler": ("recovery", 1, "0.1")},
        "infeasible_spec(mass_balance)",
    ),
    (
        "I6-boundary",
        "M1",
        DYADIC,
        {"condenser": ("distillate_rate", None, "0.125"), "reboiler": ("recovery", 0, "0.5")},
        "infeasible_spec(mass_balance)",
    ),
    (
        "I6-inside",
        "M1",
        DYADIC,
        {
            "condenser": ("distillate_rate", None, "0.125"),
            "reboiler": ("recovery", 0, "0.50000095367431640625"),
        },
        None,
    ),
]


def refusal_section() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, base, feed, spec, expected in PROBES:
        case = s2.CASES[base]
        got = refusal(case["N"], case["P"], [frac(f) for f in feed], spec)
        claim(got == expected, f"refusal probe {name}: {expected}")
        out[name] = {
            "base": base,
            "feed": list(feed),
            "spec": {e: [k, a, v] for e, (k, a, v) in spec.items()},
            "expected": expected,
        }
    for key, (base, spec) in {**CASES, **MATCHED, **UNREACHED}.items():
        case = s2.CASES[base]
        full = matched_spec(base, spec) if key not in CASES else spec
        got = refusal(case["N"], case["P"], [frac(f) for f in s2.FEED], full)
        claim(got is None, f"{key} passes I1-I6")
    p6 = s2.CASES["M1"]["P"][5]
    lo, hi = band([mpf(f) for f in s2.FEED], p6)
    claim(hi + BAND_MARGIN < 405 and lo - BAND_MARGIN > 315, "I4 probes lie > 1 K outside the band")
    return out


def band_section() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for p in [mpf(100000) + 1000 * k for k in range(7)]:
        sats = [t_sat(i, p) for i in range(NC)]
        claim(
            all(abs(s2.ln_k(sats[i], p, i)) < ZERO for i in range(NC))
            and sats[0] < sats[1] < sats[2],
            f"T_sat at {int(p)} Pa: ln K_i(T_sat,i) = 0 and T_sat,A < T_sat,B < T_sat,C",
        )
        out[str(int(p))] = [s(t) for t in sats]
    claim(
        all(abs(t_sat(i, s2.P_REF) - s2.T_BOIL[i]) < ZERO for i in range(NC)),
        "T_sat,i(P_ref) = T_b,i",
    )
    corners = [(t, p) for t in (s2.T_MIN, s2.T_MAX) for p in (s2.P_MIN, s2.P_MAX)]
    claim(
        all(s2.ln_k(t, p, 0) > s2.ln_k(t, p, 1) > s2.ln_k(t, p, 2) for t, p in corners),
        "K_A > K_B > K_C at the domain's corners (spec §4 shows it on the whole domain)",
    )
    for key, (base, spec) in CASES.items():
        for end, (kind, attr, value) in spec.items():
            if kind == "temperature":
                lo, hi = band([mpf(f) for f in s2.FEED], s2.CASES[base]["P"][attr - 1])
                claim(
                    lo + BAND_MARGIN < mpf(value) < hi - BAND_MARGIN,
                    f"{key} {end}: inside band by > 1 K",
                )
    return out


# -- spec §10 A04: the implementation's rows at a dyadic trial state ------------------------------
def trial_rows() -> dict[str, Any]:
    """Exact values of the implementation's inverse rows at a dyadic state (feed DYADIC, F = 1)."""
    feed = [frac(f) for f in DYADIC]
    total = sum(feed)
    v1 = [Fraction(1, 8), Fraction(1, 16), Fraction(1, 32)]
    l7 = [Fraction(1, 128), Fraction(1, 4), Fraction(3, 16)]
    u, x_star, r_star = Fraction(1, 2), Fraction(3, 4), Fraction(1, 2)
    t6, t_star, t5 = Fraction(1445, 4), Fraction(721, 2), Fraction(355)
    defs = [total * v1[c] - u * sum(v1) for c in range(NC)]
    recs = [l7[c] - r_star * feed[2] for c in range(NC)]
    out = {
        "state": {
            "v_1": [str(v) for v in v1],
            "V_1": str(sum(v1)),
            "l_7": [str(v) for v in l7],
            "u": str(u),
            "T_5": str(t5),
            "T_6": str(t6),
        },
        "spec": {
            "purity": ["condenser", 1, str(x_star)],
            "recovery": ["reboiler", 2, str(r_star)],
            "temperature": ["reboiler", 6, str(t_star)],
        },
        "purity_definition": str(defs[1]),
        "purity_definition_other_components": [str(defs[0]), str(defs[2])],
        "purity_slot": str(u - x_star * total),
        "recovery_slot": str(recs[2]),
        "recovery_slot_other_components": [str(recs[0]), str(recs[1])],
        "temperature_slot": str(t6 - t_star),
        "temperature_slot_other_stage": str(t5 - t_star),
    }
    values = defs + recs + [u - x_star * total, t6 - t_star, t5 - t_star]
    claim(
        len(set(defs)) == NC and len(set(recs)) == NC and all(v != 0 for v in values),
        "A04: the trial rows are nonzero and pairwise distinct across components",
    )
    claim(
        all(
            abs(v.numerator).bit_length() <= 24 and v.denominator.bit_length() <= 12 for v in values
        ),
        "A04: every trial value is a short dyadic, exact in binary64",
    )
    return out


def build() -> dict[str, Any]:
    doc: dict[str, Any] = {
        "generator": "docs/derivations/scripts/s06_reference.py",
        "spec": "docs/derivations/S06-spec.md",
        "precision_digits": mp.dps,
        "band": band_section(),
        "refusals": refusal_section(),
        "trial_rows": trial_rows(),
    }
    keys = [*CASES, *MATCHED, *UNREACHED]
    with Pool(4) as pool:
        results = pool.map(job, keys)
    doc["cases"], doc["matched"], doc["unreached"] = {}, {}, {}
    errors = [f"{key}: {out['error']}" for key, out, _, _ in results if "error" in out]
    if errors:
        raise SystemExit("; ".join(errors))
    for key, out, s02_claims, own in results:
        CLAIMS.extend(f"[{key}] {c}" for c in s02_claims + own)
        section = "cases" if key in CASES else "matched" if key in MATCHED else "unreached"
        doc[section][key] = out
    doc["claims"] = list(CLAIMS)
    doc["claim_count"] = len(CLAIMS)
    return doc


def encode(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="re-derive and compare")
    parser.add_argument("--emit", metavar="PATH", help="write the reference JSON")
    args = parser.parse_args(argv)
    if not (args.check or args.emit):
        parser.error("choose --check and/or --emit PATH")
    payload = encode(build())
    if args.check:
        print(f"{len(CLAIMS)} claims passed")
        committed = DEFAULT_OUT.read_bytes() if DEFAULT_OUT.exists() else b""
        if committed != payload:
            print(f"{DEFAULT_OUT} differs from the generator's output", file=sys.stderr)
            return 1
        print(f"{DEFAULT_OUT} is byte-identical to the generator's output")
    if args.emit:
        Path(args.emit).parent.mkdir(parents=True, exist_ok=True)
        Path(args.emit).write_bytes(payload)
        print("wrote", args.emit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
