"""OPT's cost and LCA benchmark cases (OPT design §6 G19, G20; WO-7): the requests and their
independent expectations.

Both cases optimise S11's TH-C1 (`benchmarks/s11/thermal/TH-C1.json`: 1 mol/s of water at
318.15 K and 1e4 Pa → pump `P` → boiler `B` → turbine `T` → condenser `C`; IAPWS-95) with one
continuous decision, and both expectations come from **certified production re-solves** — the
`revision_eo` route's binder and `solve_route`, the plain simulation path, with a `VERIFIED`
certificate required at every point — and from E01's **hand models**, never from the optimiser
or the assessment code under test:

- the cost at a state is `benchmarks/e01/cost_hand/cost_hand.py`'s purchased-cost forms (track
  B's transcription of IDAES SSLW, mpmath at 30 digits) on sizes and an operating cost computed
  here from the state by E01 design §4.4.1, §4.4.5, §4.7 and §9.2.7 (`tac_hand`);
- the climate impact at a state is `benchmarks/e01/lca_hand/lca_hand.py`'s unit scores on
  `test-background-v1` (`climate_change_test`, the IPCC AR6 GWP100 factors E01 ships for CO2 and
  CH4) times the inventory of its stated convention, computed here from the state (`gwp_hand`).

Cases (requests in `requests/`):
- **OPT-C** (G19): TH-C1 under E01's TAC program (P1's assessment document, `P1_DOC`); decision
  the pump's outlet pressure `P.P_spec` in [8.5e5, 1.6e6] Pa (scale 1e6 Pa); min TAC/1e5. In this
  box every TH-C1 item but the boiler sits on its size floor and the boiler on pressure piece
  "1", so TAC is smooth and its minimum interior (the trade between the boiler's pressure factor
  and the turbine's netted electricity). Expectation: a **golden-section search** on that box
  over certified re-solves with `tac_hand` at each state (`GOLDEN_WIDTH`), its `d_gs`.
- **OPT-L** (G20): TH-C1 under P4's assessment document (`P4_DOC`: P1 plus an LCA section on
  `test-background-v1`); decision the boiler's outlet temperature `B.T_spec` in [640, 720] K
  (scale 100 K), started at the revision's 673.15 K and at 650 K; min GWP100 rate/0.01 s.t. net
  shaft power −W_T − W_P ≥ `W_MIN` (declared scaled by 1e4 W). The impact rises with T and so
  does the power, so the constraint is active. Expectation: **bisection** on
  W(T) = W_MIN over certified re-solves (`BISECTION_WIDTH`), its `d_root`; `gwp_hand` there, and
  the impact's slope recorded to show the constraint binds.

The box ends and the regimes are checked here, not assumed: every evaluated state has its
pump, drive, turbine and condenser regimes as recorded and the boiler's pressure piece "1".

Usage: `python benchmarks/opt/cost_lca.py [--write | --check | --at SPEC VALUE]` (default
`--check`; `--at` prints the hand TAC and GWP rate at one certified re-solve as JSON): writes or
checks `requests/OPT-C.json`, `requests/OPT-L.json` and `cost_lca.json`. `--check` re-runs the
searches: the requests must be byte-identical, the numbers within `CHECK_RELATIVE` (another
machine's re-solves may differ in the last bits).
"""

from __future__ import annotations

import copy
import importlib.util
import json
import math
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from types import ModuleType
from typing import Any

import mpmath  # type: ignore[import-untyped]

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
F = mpmath.mpf


def _module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COST = _module("e01_cost_hand", REPO / "benchmarks/e01/cost_hand/cost_hand.py")
LCA = _module("e01_lca_hand", REPO / "benchmarks/e01/lca_hand/lca_hand.py")
mpmath.mp.dps = 30

# -- The assessment documents (transcribed from tests/test_e01_a_contributor.py C2_DOC,
#    tests/test_e01_a_contributor_c1.py C1_DOC, tests/test_e01_a_report.py P1_DOC and
#    tests/test_e01_b_lca.py's P4; tests/test_opt_cost_lca.py checks the transcription) ----------
YEAR = 2023
P1_DOC: dict[str, Any] = {
    "schema_version": "assessment-v1",
    "assessment_id": "e01-a5-p1-th-c1",
    "basis": {"currency": "USD", "year": YEAR},
    "operation": {"hours_per_year": 8000.0, "lifetime_years": 20, "discount_rate": 0.08},
    "correlation_set": "sslw-idaes-v1",
    "defaults": {"U_by_service": {"heating": 800.0, "cooling": 500.0}},
    "items": {
        "P": {"F_BM": 3.3},
        "P.drive": {"F_BM": 1.5},
        "B": {"F_BM": 3.17},
        "T": {"F_BM": 3.5},
        "C": {"F_BM": 3.17},
    },
    "utilities": [
        {
            "utility_id": "HPS",
            "kind": "heating",
            "T_supply": 750.0,
            "dT_min": 10.0,
            "price": {"value": 12.0, "per": "GJ"},
        },
        {
            "utility_id": "LPS",
            "kind": "heating",
            "T_supply": 433.15,
            "dT_min": 10.0,
            "price": {"value": 8.0, "per": "GJ"},
        },
        {
            "utility_id": "CW",
            "kind": "cooling",
            "T_supply": 293.15,
            "T_return": 303.15,
            "dT_min": 5.0,
            "price": {"value": 0.5, "per": "GJ"},
        },
        {"utility_id": "EL", "kind": "electricity", "price": {"value": 0.1, "per": "kWh"}},
    ],
    "capital": {"chain": "ebtf-prisma-v1"},
    "fixed_opex": [{"line": "maintenance", "fraction_of": {"of": "fci", "fraction": 0.03}}],
    "materials": [
        {
            "connection": "S1",
            "role": "raw_material",
            "basis": "mass_total",
            "price": {"value": 0.002, "per": "kg"},
        }
    ],
    "lca": {"functional_unit": {"connection": "S5", "basis": "mass_total"}},
    "derived": [
        {
            "id": "capex_per_opex",
            "unit": "yr",
            "numerator": {"terms": {"capex.total": 1.0}},
            "denominator": {"terms": {"opex.total": 1.0}},
        }
    ],
    "uncertainty": {"asm:utility.EL.price": {"relative_range": [-0.2, 0.2]}},
}


def p4_document() -> dict[str, Any]:
    """P4 = P1 with the LCA fragment of `lca_hand.py` (`P4_LCA`), as tests/test_e01_b_lca.py."""
    document = copy.deepcopy(P1_DOC)
    document["assessment_id"] = "e01-b2-p4"
    fragment = LCA.P4_LCA
    for utility in document["utilities"]:
        key = f"utilities.{utility['utility_id']}.lca"
        if key in fragment:
            utility["lca"] = copy.deepcopy(fragment[key])
    document["materials"][0]["lca"] = copy.deepcopy(fragment["materials.S1.lca"])
    document["lca"] = {
        "tables": ["test-background-v1"],
        "direct_factors": ["gwp100-ipcc-ar6-v1"],
        "categories": list(fragment["lca.categories"]),
        "functional_unit": dict(fragment["lca.functional_unit"]),
    }
    return document


P4_DOC = p4_document()

# -- The cases -----------------------------------------------------------------------------------
C_BOX = (8.5e5, 1.6e6)
C_SCALE = 1.0e6
C_OBJECTIVE_SCALE = 1.0e5
L_BOX = (640.0, 720.0)
L_SCALE = 100.0
L_OBJECTIVE_SCALE = 0.01
W_MIN = 15600.0
W_SCALE = 1.0e4
#: Golden section stops when the bracket is this wide (Pa): 1e-1 of G19's 1e-5·scale. Below
#: ~0.2 Pa the search is limited by TAC's binary64 noise (curvature ~7e-10 USD/yr/Pa² against an
#: ulp of 1.5e-11 USD/yr; measured), so a narrower bracket would not be more accurate.
GOLDEN_WIDTH = 1.0
#: Bisection stops when the bracket is this wide (K): 1e-3 of G20's 1e-6·scale.
BISECTION_WIDTH = 1e-7
#: `--check`: every number within this relative distance, the two decisions within 1e-2 of
#: their gate's tolerance (another machine's last bits may move a search's final bracket).
CHECK_RELATIVE = 1e-9
#: The regimes every evaluated state must hold (cost_hand's own regime words).
C_REGIMES = {
    "P": "floor",
    "P.drive": "floor",
    "B": "floor",
    "B.pressure": "1",
    "T": "floor",
    "C": "floor",
}
L_REGIMES = {**C_REGIMES, "T": "units:1"}


def requests() -> dict[str, dict[str, Any]]:
    common = {"request_format": "openflowsheet-optimization-request-v1"}
    cost = {
        **common,
        "problem_id": "OPT-C",
        "assessment": P1_DOC,
        "decisions": [
            {
                "specification_id": "SPEC-P-P",
                "unit": "Pa",
                "lower": C_BOX[0],
                "upper": C_BOX[1],
                "scale": C_SCALE,
            }
        ],
        "objective": {
            "sense": "minimize",
            "scale": C_OBJECTIVE_SCALE,
            "expression": {
                "constant": 0,
                "linear": {"assessment:tac": 1},
                "quadratic": [],
                "text": "tac/tac_s",
            },
        },
        "constraints": [],
        # The revision's own 3 MPa lies outside the box (its turbine is no longer on the floor).
        "starts": {"include_revision": False, "explicit": [[1.0e6], [1.4e6]]},
    }
    lca = {
        **common,
        "problem_id": "OPT-L",
        "assessment": P4_DOC,
        "decisions": [
            {
                "specification_id": "SPEC-B-T",
                "unit": "K",
                "lower": L_BOX[0],
                "upper": L_BOX[1],
                "scale": L_SCALE,
            }
        ],
        "objective": {
            "sense": "minimize",
            "scale": L_OBJECTIVE_SCALE,
            "expression": {
                "constant": 0,
                "linear": {"assessment:impact.climate_change_test.rate": 1},
                "quadratic": [],
                "text": "gwp_rate/gwp_s",
            },
        },
        "constraints": [
            {
                "id": "W-net-min",
                # Declared scaled (the request schema's convention): W_net/W_s, W_s = 1e4 W.
                "expression": {
                    "constant": 0,
                    "linear": {"T.W": -1 / W_SCALE, "P.W": -1 / W_SCALE},
                    "quadratic": [],
                    "text": "(-T.W - P.W)/W_s",
                },
                "lower": W_MIN / W_SCALE,
                "upper": None,
            }
        ],
        # D-70, OPT review S3: the revision's start (673.15 K, feasible side), from which Ipopt
        # crawls to max_iter (measured; L-OPT-2, kept as a case), and 650 K on the infeasible side
        # of the power constraint (W(650 K) < W_min), from which it verifies.
        "starts": {"include_revision": True, "explicit": [[650.0]]},
    }
    return {"OPT-C": cost, "OPT-L": lca}


# -- Certified production re-solves ----------------------------------------------------------------
def document_at(spec_id: str, value: float) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((REPO / "benchmarks/s11/thermal/TH-C1.json").read_bytes())
    (spec,) = [item for item in document["specifications"] if item["id"] == spec_id]
    spec["value"] = float(value)
    return document


def certified_state(spec_id: str, value: float) -> dict[str, float]:
    """TH-C1 with `spec_id` at `value`, bound and solved by the `revision_eo` route (the
    simulation path, cold), its certificate `VERIFIED`; else `RuntimeError`."""
    from openflowsheet.application.policies import DEFAULT_POLICY_ID, resolve_policy
    from openflowsheet.application.revision_run import Route, bind_route, solve_route
    from openflowsheet.verify.certificate import CheckPolicy

    policy = resolve_policy(DEFAULT_POLICY_ID, "revision_eo")
    assert policy is not None
    document = document_at(spec_id, value)
    route = bind_route("revision_eo", document)
    if not isinstance(route, Route):
        raise RuntimeError(f"{spec_id}={value!r}: route refused {route}")
    result = solve_route(
        route, document, policy=policy, check_policy=CheckPolicy(), warm_start=None
    )
    certificate = result.certificate
    if (
        result.outcome != "CONVERGED"
        or certificate is None
        or certificate.verification_status != "VERIFIED"
    ):
        raise RuntimeError(f"{spec_id}={value!r}: {result.outcome}, not certified")
    state = result.state
    if state is None and result.run is not None:
        state = result.run.state
    if state is None:
        raise RuntimeError(f"{spec_id}={value!r}: no state")
    return {name: float(x) for name, x in state.items()}


# -- E01's hand models at a state ---------------------------------------------------------------
#: TH-C1's feed (S1) is fixed by its specifications; the pump's volumetric flow and its specific
#: volume are P1's recorded values (cost_hand.P_SIZES, the fixture at 3 MPa: the inlet is the same
#: state whatever the outlet pressure), so `head = ΔP·v/g` (E01 §4.4.5) needs no property call.
M_H2O = F("0.018015268")  # kg/mol (benchmarks/s05/components.yaml; lca_hand's RECORDED)
G = F("9.80665")
HOURS = F(8000)
SECONDS = 3600 * HOURS
ESCALATION = COST.WPU11_ANNUAL[2023] / COST.WPU11_ANNUAL[2006]


def _p1_pump() -> Mapping[str, float]:
    (inputs,) = [x for item, _, _, x in COST.P_SIZES["p1_th_c1"][1] if item == "P"]
    return {str(key): float(value) for key, value in inputs.items()}


def underwood(dt1: Any, dt2: Any) -> Any:
    return ((mpmath.cbrt(dt1) + mpmath.cbrt(dt2)) / 2) ** 3


def sizes(state: Mapping[str, float]) -> dict[str, dict[str, Any]]:
    """Each P1 item's cost_hand inputs at `state` (E01 §4.4.1, §4.4.5, §9.2.2 item 7)."""
    s = {name: F(value) for name, value in state.items()}
    assert state["S1.T"] == 318.15 and state["S1.P"] == 1.0e4 and state["S1.n.H2O"] == 1.0
    recorded = _p1_pump()
    v_mass = F(recorded["vol_flow_m3s"]) / (s["S1.n.H2O"] * M_H2O)
    head = (s["S2.P"] - s["S1.P"]) * v_mass / G
    hps = F(750)  # isothermal: T_return = T_supply
    a_b = s["B.Q"] / (800 * underwood(hps - s["S3.T"], hps - s["S2.T"]))
    a_c = -s["C.Q"] / (500 * underwood(s["S4.T"] - F("303.15"), s["S5.T"] - F("293.15")))
    return {
        "P": {"vol_flow_m3s": recorded["vol_flow_m3s"], "head_m": head, "power_W": s["P.W"]},
        "P.drive": {"shaft_power_W": s["P.W"], "N": 1},
        "B": {"area_m2": a_b, "P_Pa": s["S2.P"]},
        "T": {"power_W": s["T.W"]},
        "C": {"area_m2": a_c, "P_Pa": s["S4.P"]},
    }


FORMS: dict[str, tuple[Callable[..., dict[str, Any]], Mapping[str, Any]]] = {
    "P": (COST.pump, COST.PUMP_DEFAULTS),
    "P.drive": (COST.motor, COST.MOTOR_DEFAULTS),
    "B": (COST.exchanger, COST.HX_DEFAULTS),
    "T": (COST.turbine, {}),
    "C": (COST.exchanger, COST.HX_DEFAULTS),
}
F_BM = {item: F(str(entry["F_BM"])) for item, entry in P1_DOC["items"].items()}


def regimes(state: Mapping[str, float]) -> dict[str, str]:
    out = {}
    for item, inputs in sizes(state).items():
        form, options = FORMS[item]
        regime = form(inputs, options)["regime"]
        out[item] = regime["size"]
        if item == "B":
            out["B.pressure"] = regime["pressure"]
    return out


def net_electricity_w(state: Mapping[str, float]) -> Any:
    """Consumed minus generated (E01 §2 signs, §4.4.5, §9.2.7): W_P/η_m(W_P) − η_gen·(−W_T)."""
    w_p, w_t = F(state["P.W"]), F(state["T.W"])
    return w_p / COST.motor_efficiency(w_p * COST.KAPPA_W) - F("0.95") * (-w_t)


def tac_hand(state: Mapping[str, float]) -> dict[str, Any]:
    """TAC (USD/yr) at `state` by E01 §4.7: purchased costs by cost_hand, escalated 2006→2023,
    times F_BM, the `ebtf-prisma-v1` chain, CRF(8 %, 20 yr); utilities, netted electricity, the
    raw material and maintenance (3 % of FCI = CAPEX)."""
    purchased = {}
    for item, inputs in sizes(state).items():
        form, options = FORMS[item]
        purchased[item] = form(inputs, options)["C_P"] * ESCALATION
    tdc = mpmath.fsum(F_BM[item] * purchased[item] for item in F_BM)
    capex = COST.EBTF[3] * COST.EBTF[0] * COST.EBTF[1] * COST.EBTF[2] * tdc
    crf = COST.crf(F("0.08"), F(20))
    s = {name: F(value) for name, value in state.items()}
    opex = {
        "HPS": F(12) / F("1e9") * s["B.Q"] * SECONDS,
        "CW": F("0.5") / F("1e9") * (-s["C.Q"]) * SECONDS,
        "EL": F("0.1") * net_electricity_w(state) / 1000 * HOURS,
        "S1": F("0.002") * s["S1.n.H2O"] * M_H2O * SECONDS,
        "maintenance": F("0.03") * capex,
    }
    opex_total = mpmath.fsum(opex.values())
    return {
        "capex": capex,
        "annual_capital_charge": crf * capex,
        "opex": opex,
        "opex_total": opex_total,
        "tac": crf * capex + opex_total,
    }


def gwp_hand(state: Mapping[str, float]) -> Any:
    """`impact.climate_change_test.rate` (kg CO2-eq/s) at `state` by lca_hand's convention:
    Σ_k q_k a_k with a = (net electricity kWh/s, |Q_B| MJ/s, ṁ_S1 kg/s)."""
    q = LCA.unit_scores()
    a = {
        "tb.electricity": net_electricity_w(state) / LCA.SI["kWh"],
        "tb.heat": F(state["B.Q"]) / LCA.SI["MJ"],
        "tb.chemical_x": F(state["S1.n.H2O"]) * M_H2O / LCA.SI["kg"],
    }
    return mpmath.fsum(q[k] * a[k] for k in LCA.ACTIVITIES)


def net_power(state: Mapping[str, float]) -> float:
    return -state["T.W"] - state["P.W"]


# -- The independent searches -------------------------------------------------------------------
INVGOLD = (math.sqrt(5.0) - 1.0) / 2.0


def golden_section() -> dict[str, Any]:
    """G19: min `tac_hand` over certified re-solves on `C_BOX` by golden section (unimodal on the
    box: checked on a coarse grid first)."""

    def tac(p: float) -> Any:
        state = certified_state("SPEC-P-P", p)
        assert regimes(state) == C_REGIMES, (p, regimes(state))
        return tac_hand(state)["tac"]

    grid = [C_BOX[0] + k * (C_BOX[1] - C_BOX[0]) / 10 for k in range(11)]
    values = [tac(p) for p in grid]
    best = min(range(len(grid)), key=lambda k: values[k])
    assert 0 < best < len(grid) - 1, "the minimum must be interior"
    assert all(values[k] > values[k + 1] for k in range(best))
    assert all(values[k] < values[k + 1] for k in range(best, len(grid) - 1))
    a, b = grid[best - 1], grid[best + 1]
    c, d = b - INVGOLD * (b - a), a + INVGOLD * (b - a)
    fc, fd = tac(c), tac(d)
    evaluations = len(grid) + 2
    while b - a > GOLDEN_WIDTH:
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - INVGOLD * (b - a)
            fc = tac(c)
        else:
            a, c, fc = c, d, fd
            d = a + INVGOLD * (b - a)
            fd = tac(d)
        evaluations += 1
    d_gs = (a + b) / 2
    at = tac_hand(certified_state("SPEC-P-P", d_gs))
    return {
        "decision": "P.P_spec",
        "d_gs": d_gs,
        "bracket": [a, b],
        "evaluations": evaluations + 1,
        "tac_at_d_gs": float(at["tac"]),
        "tolerance_decision": 1e-5 * C_SCALE,
        "grid_tac": [float(x) for x in values],
    }


def bisection() -> dict[str, Any]:
    """G20: W(T) = W_MIN on `L_BOX` by bisection over certified re-solves; GWP's slope there."""

    def power(t: float) -> float:
        state = certified_state("SPEC-B-T", t)
        assert regimes(state) == L_REGIMES, (t, regimes(state))
        return net_power(state) - W_MIN

    lo, hi = L_BOX
    f_lo, f_hi = power(lo), power(hi)
    assert f_lo < 0.0 < f_hi, (f_lo, f_hi)
    evaluations = 2
    while hi - lo > BISECTION_WIDTH:
        mid = (lo + hi) / 2
        if power(mid) < 0.0:
            lo = mid
        else:
            hi = mid
        evaluations += 1
    root = hi  # the feasible end of the final bracket
    state = certified_state("SPEC-B-T", root)
    step = 1e-3 * L_SCALE
    slope = (
        gwp_hand(certified_state("SPEC-B-T", root + step))
        - gwp_hand(certified_state("SPEC-B-T", root - step))
    ) / (2 * step)
    return {
        "decision": "B.T_spec",
        "d_root": root,
        "bracket": [lo, hi],
        "evaluations": evaluations + 3,
        "net_power_at_d_root": net_power(state),
        "gwp_rate_at_d_root": float(gwp_hand(state)),
        "gwp_slope_per_K": float(slope),
        "tolerance_decision": 1e-6 * L_SCALE,
    }


def p1_check() -> dict[str, Any]:
    """The hand model on P1's own state (3 MPa, 673.15 K) against cost_hand's P1 chain and the
    P1 fixture's sizes and operating cost (`cost_hand.yaml` chain.p1_th_c1)."""
    state = certified_state("SPEC-P-P", 3.0e6)
    out = tac_hand(state)
    recorded = {item: x for item, _, _, x in COST.P_SIZES["p1_th_c1"][1]}
    mine = sizes(state)
    worst = 0.0
    for item, inputs in recorded.items():
        for key, value in inputs.items():
            if key == "N":
                continue
            worst = max(worst, float(abs(F(mine[item][key]) / F(value) - 1)))
    opex_rel = float(abs(out["opex_total"] / F(COST.P1_OPEX_TOTAL) - 1))
    return {
        "sizes_worst_relative": worst,
        "opex_total_relative": opex_rel,
        "tac": float(out["tac"]),
    }


def expectations() -> dict[str, Any]:
    return {
        "id": "opt-cost-lca-v1",
        "script": "benchmarks/opt/cost_lca.py",
        "hand_models": [
            "benchmarks/e01/cost_hand/cost_hand.py",
            "benchmarks/e01/lca_hand/lca_hand.py",
        ],
        "p1_check": p1_check(),
        "OPT-C": golden_section(),
        "OPT-L": bisection(),
    }


def _bytes(document: Any) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _close(new: Any, old: Any, where: str, found: list[str]) -> None:
    if isinstance(new, dict) and isinstance(old, dict) and sorted(new) == sorted(old):
        for key in new:
            _close(new[key], old[key], f"{where}/{key}", found)
    elif isinstance(new, list) and isinstance(old, list) and len(new) == len(old):
        for k, (a, b) in enumerate(zip(new, old, strict=True)):
            _close(a, b, f"{where}/{k}", found)
    elif isinstance(new, float) and isinstance(old, float):
        if where.endswith(("_relative", "bracket/0", "bracket/1")):
            return  # rounding-level records, not expectations
        absolute = 0.0
        if where.endswith(("/d_gs", "/d_root")):
            absolute = 1e-2 * (1e-5 * C_SCALE if where.endswith("d_gs") else 1e-6 * L_SCALE)
        if not math.isclose(new, old, rel_tol=CHECK_RELATIVE, abs_tol=absolute):
            found.append(f"{where}: {new!r} against {old!r}")
    elif new != old:
        found.append(f"{where}: {new!r} against {old!r}")


def main(argv: list[str]) -> int:
    if argv[:1] == ["--at"]:
        # `--at SPEC VALUE`: the hand models at one certified re-solve, as JSON (the audited
        # environment's G19/G20 tests call this in an interpreter that has mpmath).
        state = certified_state(argv[1], float(argv[2]))
        print(json.dumps({"tac": float(tac_hand(state)["tac"]), "gwp": float(gwp_hand(state))}))
        return 0
    write = "--write" in argv
    files = {HERE / "requests" / f"{name}.json": _bytes(r) for name, r in requests().items()}
    numbers = expectations()
    target = HERE / "cost_lca.json"
    stale = []
    for path, payload in files.items():
        if write:
            path.write_bytes(payload)
        elif not path.exists() or path.read_bytes() != payload:
            stale.append(str(path.relative_to(HERE)))
    if write:
        target.write_bytes(_bytes(numbers))
    elif not target.exists():
        stale.append("cost_lca.json")
    else:
        found: list[str] = []
        _close(numbers, json.loads(target.read_bytes()), "", found)
        stale += [f"cost_lca.json{entry}" for entry in found]
    if stale:
        print(f"OPT cost/LCA: stale {stale}; run with --write")
        return 1
    c, lca = numbers["OPT-C"], numbers["OPT-L"]
    print(
        f"OPT cost/LCA: {'written' if write else 'current'}; d_gs {c['d_gs']!r} Pa, "
        f"TAC {c['tac_at_d_gs']!r}; d_root {lca['d_root']!r} K, GWP {lca['gwp_rate_at_d_root']!r}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
