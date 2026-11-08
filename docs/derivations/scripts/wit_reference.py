"""Reference values for the derivative-witness amendment (K04 spec §4.8.1-§4.8.9, ADR 0073).

Normative text: ``docs/derivations/K04-certificate-spec.md`` §4.8.1-§4.8.9 (amendment WIT,
2026-11-08). Output: ``docs/derivations/scripts/wit_reference.json``.

Two kinds of expectation, both independent of OpenFlowsheet (nothing here imports it):

* **W0-W3, analytic cases** for the escalation of §4.8.3. Each is a closed-form residual with a
  closed-form Jacobian; every finite difference is evaluated at 50 digits, so the truncation error
  of each stencil is exact and the selection index ``k*`` follows from the rule alone. W3 is a
  noisy residual; its differences are evaluated in binary64 exactly as the rule's arithmetic
  states them, because noise is the point of the case.
* **G1-G2, closed forms at GP-C3's registered single-phase states** (S11.A71's flowsheet with the
  heater at 345 K and 385 K) from the ``wilson-ig-v2`` record file ``benchmarks/s10/records.yaml``:
  the dormant vapour side's equilibrium-row entries (§4.8.4, A1) and, on the dormant liquid side,
  the AD entry (the K-block's probe convention) against the one-sided derivative along the column
  (§4.8.5, A2), which differ: no derivative exists there.

Every claim the specification makes about these numbers is checked here, and the script refuses
to emit when one fails (rule 4).

    python3 -I docs/derivations/scripts/wit_reference.py          # write the JSON
    python3 -I docs/derivations/scripts/wit_reference.py --check  # byte-compare; 1 on drift

Dependencies: Python 3.11+, mpmath, PyYAML.
"""

from __future__ import annotations

import json
import math
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import yaml
from mpmath import mp, mpf

mp.dps = 50
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = HERE / "wit_reference.json"
RECORDS = ROOT / "benchmarks" / "s10" / "records.yaml"
GP_C3 = ROOT / "benchmarks" / "s11" / "gp" / "GP-C3.json"
DIGITS = 20

# -- the registered constants (K04 §4.8, §4.8.3), transcribed -------------------------------------
FD_RELATIVE_STEP = 1e-5
TOL = mpf("1e-7")  # DERIVATIVE_TOLERANCE
EPS_RES = TOL / 10  # §4.8.3 (c): the resolution bound
K_MAX = 8  # §4.8.3 (b): levels k = 0..K_MAX
#: §4.8.3 (b): the central fourth-order stencil, offsets in units of h_k, and its weights / 12.
C4 = ((2, -1), (1, 8), (-1, -8), (-2, 1))
#: §4.8 (registered): the central second-order stencil, offsets and weights / 2.
C2 = ((1, 1), (-1, -1))
U = mpf(2) ** -53  # binary64 unit roundoff

CLAIMS: list[str] = []


def claim(condition: bool, text: str) -> None:
    if not condition:
        raise SystemExit(f"claim failed, nothing emitted: {text}")
    CLAIMS.append(text)


def s(x: Any) -> str:
    return mp.nstr(mpf(x), DIGITS, strip_zeros=False)


# == W0, W1, W2: smooth small-flow residuals (§4.8.3, class 5) ===================================
#
# Columns S1.n.A, S1.n.B (component columns, scale 3 mol/s) and S1.T (scale 100 K); rows
#   R1 = theta * n_A / (n_A + n_B)        kind temperature, scale 1 K
#   R2 = n_A + n_B - N0                   kind molar_flow,  scale 3 mol/s
#   R3 = T - T0                           kind temperature, scale 1 K
# A trial point with a negative flow is refused (status invalid_trial_state, ADR 0001 D2).

COLUMNS = ("S1.n.A", "S1.n.B", "S1.T")
COLUMN_SCALE = {"S1.n.A": mpf(3), "S1.n.B": mpf(3), "S1.T": mpf(100)}
ROWS = ("R1", "R2", "R3")
ROW_SCALE = {"R1": mpf(1), "R2": mpf(3), "R3": mpf(1)}


def smooth_case(theta: str, n_a: str, n_b: str, t: str) -> dict[str, Any]:
    th = mpf(theta)
    x0 = {"S1.n.A": mpf(n_a), "S1.n.B": mpf(n_b), "S1.T": mpf(t)}
    n0 = x0["S1.n.A"] + x0["S1.n.B"]
    t0 = x0["S1.T"]

    def residual(x: dict[str, Any]) -> dict[str, Any] | None:
        if x["S1.n.A"] < 0 or x["S1.n.B"] < 0:
            return None
        total = x["S1.n.A"] + x["S1.n.B"]
        return {"R1": th * x["S1.n.A"] / total, "R2": total - n0, "R3": x["S1.T"] - t0}

    a, b = x0["S1.n.A"], x0["S1.n.B"]
    total = a + b
    jac = {
        ("R1", "S1.n.A"): th * b / total**2,
        ("R1", "S1.n.B"): -th * a / total**2,
        ("R2", "S1.n.A"): mpf(1),
        ("R2", "S1.n.B"): mpf(1),
        ("R3", "S1.T"): mpf(1),
    }
    return {"x0": x0, "residual": residual, "jacobian": jac, "theta": th}


def scaled_difference(
    residual: Callable[[dict[str, Any]], dict[str, Any] | None],
    x0: dict[str, Any],
    column: str,
    h: Any,
    stencil: Sequence[tuple[int, int]],
    denominator: int,
) -> dict[str, Any] | None:
    """The stencil's scaled column, D_i = (sum_s w_s F_i(x + s h e_j)) / (den h) * S_j / S_i, at
    50 digits; None when a point is refused."""
    acc = dict.fromkeys(ROWS, mpf(0))
    for offset, weight in stencil:
        point = dict(x0)
        point[column] = x0[column] + offset * h
        values = residual(point)
        if values is None:
            return None
        for row in ROWS:
            acc[row] += weight * values[row]
    return {
        row: acc[row] / (denominator * h) * COLUMN_SCALE[column] / ROW_SCALE[row] for row in ROWS
    }


def scaled_exact(case: dict[str, Any], column: str) -> dict[str, Any]:
    return {
        row: case["jacobian"].get((row, column), mpf(0)) * COLUMN_SCALE[column] / ROW_SCALE[row]
        for row in ROWS
    }


def escalation(case: dict[str, Any], column: str) -> dict[str, Any]:
    """§4.8.3 at 50 digits: the registered central difference, then the levels of the central
    fourth-order stencil at h_k = h 2^-k, e_k, and k* (the first k with e_k <= EPS_RES)."""
    x0, residual = case["x0"], case["residual"]
    h0 = mpf(FD_RELATIVE_STEP * float(COLUMN_SCALE[column]))  # the binary64 registered step
    exact = scaled_exact(case, column)
    tier1 = scaled_difference(residual, x0, column, h0, C2, 2)
    tier1_error = None if tier1 is None else max(abs(tier1[r] - exact[r]) for r in ROWS)
    levels: list[dict[str, Any]] = []
    previous = None
    selected = None
    for k in range(K_MAX + 1):
        h = h0 * mpf(2) ** -k
        d = scaled_difference(residual, x0, column, h, C4, 12)
        if d is None:
            levels.append({"k": k, "admissible": False})
            previous = None
            continue
        error = max(abs(d[r] - exact[r]) for r in ROWS)
        e_k = None if previous is None else max(abs(d[r] - previous[r]) for r in ROWS)
        # The binary64 roundoff the stencil adds: u * sum|w| * max|F| / (12 h), scaled.
        f_max = max(
            abs(v)
            for offset, _ in C4
            for v in residual({**x0, column: x0[column] + offset * h}).values()  # type: ignore[union-attr]
        )
        roundoff = U * 18 * f_max / (12 * h) * COLUMN_SCALE[column] / min(ROW_SCALE.values())
        level = {"k": k, "admissible": True, "h": h, "error": error, "e_k": e_k}
        level["roundoff_bound"] = roundoff
        levels.append(level)
        if selected is None and e_k is not None and e_k <= EPS_RES:
            selected = k
            break
        previous = d
    return {"h0": h0, "tier1": tier1, "tier1_error": tier1_error, "levels": levels, "k": selected}


def smooth_entry(name: str, case: dict[str, Any], columns: Sequence[str]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "state": {c: s(v) for c, v in case["x0"].items()},
        "theta_K": s(case["theta"]),
        "jacobian_scaled": {
            f"{r}|{c}": s(v * COLUMN_SCALE[c] / ROW_SCALE[r])
            for (r, c), v in case["jacobian"].items()
        },
        "columns": {},
    }
    for column in columns:
        result = escalation(case, column)
        k = result["k"]
        claim(k is not None, f"{name} {column}: the escalation resolves within K_MAX")
        selected = result["levels"][k]
        before = result["levels"][k - 1]
        # Robust selection: e_k* <= EPS_RES/2 and, when e_(k*-1) exists, e_(k*-1) >= 2 EPS_RES.
        claim(
            selected["e_k"] <= EPS_RES / 2,
            f"{name} {column}: e_k* <= EPS_RES/2 (a 2x margin against the binary64 roundoff)",
        )
        if before.get("e_k") is not None:
            claim(
                before["e_k"] >= 2 * EPS_RES,
                f"{name} {column}: e_(k*-1) >= 2 EPS_RES (k* does not move by roundoff)",
            )
        claim(
            selected["roundoff_bound"] <= EPS_RES / 100,
            f"{name} {column}: the binary64 roundoff bound at k* is <= EPS_RES/100",
        )
        claim(
            selected["error"] + selected["roundoff_bound"] <= TOL / 100,
            f"{name} {column}: the escalated estimate is within TOL/100 of the closed form",
        )
        out["columns"][column] = {
            "registered_step": s(result["h0"]),
            "tier1": "refused" if result["tier1"] is None else "evaluated",
            "tier1_error_scaled": None
            if result["tier1_error"] is None
            else s(result["tier1_error"]),
            "k_star": k,
            "levels": [
                {
                    "k": lv["k"],
                    "admissible": lv["admissible"],
                    **(
                        {
                            "h": s(lv["h"]),
                            "truncation_error_scaled": s(lv["error"]),
                            "e_k": None if lv["e_k"] is None else s(lv["e_k"]),
                            "roundoff_bound_scaled": s(lv["roundoff_bound"]),
                        }
                        if lv["admissible"]
                        else {}
                    ),
                }
                for lv in result["levels"]
            ],
            "escalated_error_bound_scaled": s(selected["error"] + selected["roundoff_bound"]),
        }
    return out


def build_w1() -> dict[str, Any]:
    case = smooth_case(theta="0.3", n_a="2.0e-4", n_b="5.0e-3", t="600")
    entry = smooth_entry("W1", case, ("S1.n.A", "S1.n.B"))
    for column in ("S1.n.A", "S1.n.B"):
        error = mpf(entry["columns"][column]["tier1_error_scaled"])
        claim(
            error >= 10 * TOL, f"W1 {column}: the registered central difference fails by >= 10 TOL"
        )
    claim(
        entry["columns"]["S1.n.A"]["k_star"] != entry["columns"]["S1.n.B"]["k_star"],
        "W1: the two escalated columns resolve at different levels (a shared k* hides a "
        "column-indexing defect)",
    )
    # S1.T passes the registered stencil: R3 is linear, so its central difference is exact.
    t_case = scaled_difference(case["residual"], case["x0"], "S1.T", mpf(1e-5 * 100.0), C2, 2)
    assert t_case is not None
    claim(
        max(abs(t_case[r] - scaled_exact(case, "S1.T")[r]) for r in ROWS) <= mpf("1e-30"),
        "W1 S1.T: the registered central difference is exact (no escalation)",
    )
    # WIT.A03's mutation: +3 TOL on the scaled (R1, S1.n.A) entry is reported within 1e-9 of 3 TOL.
    bound = mpf(entry["columns"]["S1.n.A"]["escalated_error_bound_scaled"])
    claim(bound <= mpf("1e-9") / 5, "W1 mutation: the escalated error is <= 1/5 of A03's window")
    return entry


def build_w0() -> dict[str, Any]:
    """W1's residual at plant-scale flows: every registered central difference passes, so nothing
    escalates (WIT.A06 counts the evaluations)."""
    case = smooth_case(theta="0.3", n_a="2.0", n_b="5.0", t="600")
    errors: dict[str, str] = {}
    for column in COLUMNS:
        h0 = mpf(FD_RELATIVE_STEP * float(COLUMN_SCALE[column]))
        tier1 = scaled_difference(case["residual"], case["x0"], column, h0, C2, 2)
        assert tier1 is not None
        error = max(abs(tier1[r] - scaled_exact(case, column)[r]) for r in ROWS)
        claim(error <= TOL / 1000, f"W0 {column}: the registered central difference passes by 1e3")
        errors[column] = s(error)
    return {"state": {c: s(v) for c, v in case["x0"].items()}, "tier1_error_scaled": errors}


def build_w2() -> dict[str, Any]:
    case = smooth_case(theta="0.3", n_a="5.0e-6", n_b="1.0e-3", t="600")
    entry = smooth_entry("W2", case, ("S1.n.A", "S1.n.B"))
    column = entry["columns"]["S1.n.A"]
    claim(column["tier1"] == "refused", "W2 S1.n.A: the registered central difference is refused")
    admissible = [lv["k"] for lv in column["levels"] if lv["admissible"]]
    claim(admissible[0] == 4, "W2 S1.n.A: levels 0-3 are refused (2 h_k > n_A); level 4 is first")
    claim(column["k_star"] == 6, "W2 S1.n.A: k* = 6, after one unresolved pair (e_5 >= 2 EPS_RES)")
    other = entry["columns"]["S1.n.B"]
    claim(
        other["tier1"] == "evaluated" and mpf(other["tier1_error_scaled"]) >= 10 * TOL,
        "W2 S1.n.B: the registered central difference is evaluated and fails by >= 10 TOL",
    )
    claim(other["k_star"] == 4, "W2 S1.n.B: k* = 4 (no refused level)")
    return entry


def stencil_claims() -> None:
    """§4.8.3 (b): the escalation stencil is the central fourth-order one."""
    moment = [sum(w * mpf(o) ** p for o, w in C4) for p in range(6)]
    claim(moment[0] == 0 and moment[2] == 0 and moment[4] == 0, "C4: even moments vanish")
    claim(moment[1] == 12, "C4: sum w s = 12, so the weights / (12 h) differentiate exactly")
    claim(moment[3] == 0, "C4: sum w s^3 = 0, so the stencil is fourth order")
    claim(moment[5] == -48, "C4: sum w s^5 = -48, truncation -h^4 f^(5) / 30")
    claim(EPS_RES == TOL / 10, "EPS_RES = DERIVATIVE_TOLERANCE / 10")


# == W3: a noisy residual, evaluated in binary64 (§4.8.3 (d), unresolved) ==========================
#
# One component column S1.n.A (scale 3 mol/s) at 0.5 mol/s; one row R4 (molar_flow, scale 3 mol/s):
#   R4 = n_A + ETA * saw(n_A * 2^40),  saw(u) = u - floor(u) - 1/2,
# whose AD entry is declared 1 (the noise-free part, as ADV-06's clean Jacobian is).

ETA = 1e-10
W3_X = 0.5


def _r4(n_a: float) -> float:
    u = n_a * 2.0**40
    return n_a + ETA * (u - math.floor(u) - 0.5)


def _binary64_c4(h: float) -> float:
    points = [_r4(W3_X + float(offset) * h) for offset, _ in C4]
    weights = [float(w) for _, w in C4]
    acc = 0.0
    for weight, value in zip(weights, points, strict=True):
        acc += weight * value
    return acc / (12.0 * h) * 3.0 / 3.0


def build_w3() -> dict[str, Any]:
    h0 = FD_RELATIVE_STEP * 3.0
    tier1 = (_r4(W3_X + h0) - _r4(W3_X - h0)) / (2.0 * h0) * 3.0 / 3.0
    tier1_error = abs(tier1 - 1.0)
    claim(
        tier1_error >= 10 * float(TOL), "W3: the registered central difference fails by >= 10 TOL"
    )
    estimates = [_binary64_c4(h0 * 2.0**-k) for k in range(K_MAX + 1)]
    e = [abs(estimates[k] - estimates[k - 1]) for k in range(1, K_MAX + 1)]
    claim(
        min(e) >= 100 * float(EPS_RES), "W3: every e_k >= 100 EPS_RES, so the column is unresolved"
    )
    return {
        "state": {"S1.n.A": W3_X},
        "eta_mol_per_s": ETA,
        "saw_period_mol_per_s": "2^-40",
        "tier1_error_scaled": float(f"{tier1_error:.6e}"),
        "min_e_k": float(f"{min(e):.6e}"),
        "outcome": "unresolved: the registered result (fail) and its value stand",
    }


# == G1, G2: GP-C3's single-phase states on wilson-ig-v2 (§4.8.4, §4.8.5) =========================

THETA_UNIT = mpf(1000)


def load_records() -> dict[str, Any]:
    doc = yaml.safe_load(RECORDS.read_bytes())
    ids = [c["id"] for c in doc["components"]]
    psat = [
        tuple(mpf(float(c["parameters"][f"vapour_pressure_{k}"]["value"])) for k in "abcd")
        for c in doc["components"]
    ]
    lam = [[mpf(1) if i == j else None for j in range(len(ids))] for i in range(len(ids))]
    for e in doc["wilson_lambda"]:
        lam[ids.index(e["i"])][ids.index(e["j"])] = mpf(float(e["value"]))
    return {"ids": ids, "psat": psat, "lam": lam}


def ln_psat(rec: dict[str, Any], i: int, t: Any) -> Any:
    a, b, c, d = rec["psat"][i]
    theta = t / THETA_UNIT
    return a + b / theta + c * mp.log(theta) + d * theta**2


def ln_gamma(rec: dict[str, Any], x: Sequence[Any]) -> list[Any]:
    lam, n = rec["lam"], len(x)
    sums = [sum(x[j] * lam[i][j] for j in range(n)) for i in range(n)]
    return [
        1 - mp.log(sums[i]) - sum(x[k] * lam[k][i] / sums[k] for k in range(n)) for i in range(n)
    ]


def k_value(rec: dict[str, Any], i: int, t: Any, p: Any, x: Sequence[Any]) -> Any:
    return mp.exp(ln_gamma(rec, x)[i] + ln_psat(rec, i, t) - mp.log(p))


def gp_c3_totals() -> tuple[dict[str, Any], Any]:
    """The heater's outlet flows from GP-C3's pinned feeds (S1 + S2), and the pressure."""
    doc = json.loads(GP_C3.read_text(encoding="utf-8"))
    flows: dict[str, Any] = {}
    pressure = None
    for spec in doc["specifications"]:
        target = spec["target"]
        if target.get("path") == "state.n":
            flows[target["component"]] = flows.get(target["component"], mpf(0)) + mpf(
                str(spec["value"])
            )
        if target.get("path") == "state.P" and target["object_id"] == "S1":
            pressure = mpf(str(spec["value"]))
    return flows, pressure


def build_gp() -> dict[str, Any]:
    rec = load_records()
    flows, pressure = gp_c3_totals()
    ids = rec["ids"]
    claim(list(flows) == ids or sorted(flows) == sorted(ids), "GP-C3's components are the records'")
    total = sum(flows.values())
    s_flow, s_eq = mpf(3), mpf(9)  # molar_flow scale (mol/s), molar_flow_squared scale ((mol/s)^2)
    claim(total == mpf("1.5"), "GP-C3: the heater's outlet carries 1.5 mol/s")
    # G1 (345 K, vapour side dormant, A1): row H:HEAT-equilibrium:<c> is v_c L - K_c(x) l_c V,
    # affine in v_c with slope L; scaled L S_flow / S_eq.
    g1 = {
        "temperature_K": 345,
        "L_mol_per_s": s(total),
        "equilibrium_row_vapour_entry_scaled": s(total * s_flow / s_eq),
    }
    claim(total * s_flow / s_eq == mpf("0.5"), "G1: the dormant vapour entry is 0.5, not zero")
    # G2 (385 K, liquid side dormant, A2): the AD entry reads K at the probe x = (1/3, 1/3, 1/3);
    # the one-sided derivative along +e_c reads K at x = e_c (gamma_c = 1).
    t = mpf(385)
    probe = [mpf(1) / 3] * len(ids)
    g2: dict[str, Any] = {"temperature_K": 385, "V_mol_per_s": s(total), "components": {}}
    for i, c in enumerate(ids):
        pure = [mpf(1) if j == i else mpf(0) for j in range(len(ids))]
        k_probe = k_value(rec, i, t, pressure, probe)
        k_pure = k_value(rec, i, t, pressure, pure)
        ad = -k_probe * total * s_flow / s_eq
        one_sided = -k_pure * total * s_flow / s_eq
        gap = abs(ad - one_sided)
        claim(abs(ln_gamma(rec, pure)[i]) < mpf("1e-45"), f"G2 {c}: gamma_c(e_c) = 1")
        claim(
            gap >= 1000 * TOL,
            f"G2 {c}: the AD entry and the one-sided derivative differ by >= 1e3 TOL",
        )
        g2["components"][c] = {
            "psat_Pa": s(mp.exp(ln_psat(rec, i, t))),
            "K_at_probe": s(k_probe),
            "K_pure": s(k_pure),
            "ad_entry_scaled": s(ad),
            "one_sided_derivative_scaled": s(one_sided),
            "gap_scaled": s(gap),
        }
    return {"pressure_Pa": s(pressure), "G1": g1, "G2": g2}


def build() -> dict[str, Any]:
    stencil_claims()
    document = {
        "format": "wit-reference-v1",
        "spec": "docs/derivations/K04-certificate-spec.md §4.8.1-§4.8.9",
        "constants": {
            "FD_RELATIVE_STEP": FD_RELATIVE_STEP,
            "DERIVATIVE_TOLERANCE": float(TOL),
            "EPS_RES": float(EPS_RES),
            "K_MAX": K_MAX,
            "c4_offsets_weights_over_12": [list(p) for p in C4],
        },
        "W0": build_w0(),
        "W1": build_w1(),
        "W2": build_w2(),
        "W3": build_w3(),
        "GP_C3": build_gp(),
    }
    document["claims"] = list(CLAIMS)
    return document


def render(document: dict[str, Any]) -> str:
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def main() -> int:
    text = render(build())
    if "--check" in sys.argv[1:]:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print(f"DRIFT: {OUT.name} differs from the generator")
            return 1
        print(f"OK: {OUT.name} reproduced byte-for-byte ({len(CLAIMS)} claims hold)")
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.name} ({len(CLAIMS)} claims hold)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
