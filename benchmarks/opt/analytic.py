"""OPT's analytic benchmark cases: the requests and their independent expectations (OPT design §6
G7, G8, G9; WO-4).

The expectations are computed with mpmath (30 digits) from the SYN-001 coefficient table
(`docs/derivations/SYN-001.md` §1, transcribed below), **independently of the provider code**:
the ideal liquid enthalpy `h_i^L = c_p (T − T_r) + v_i (P − P_r)` and
`K_i = (P_r/P) exp[(L_i/R)(1/T_b,i − 1/T) + v_i (P − P_r)/(RT)]` (§2, §3 there).

Cases (flowsheets in `flowsheets/`, generated once from the T05 case templates; every pressure
drop is zero, so P = 1e5 Pa throughout):
- **OPT-A1** (G7): feed (A, B, C liquid, 1 mol/s each, 300 K) → PH heater `U-PHF` (decision Q) →
  sinks; min Q/Q_s s.t. `S3.T ≥ T_min`. Q* = Σ n_i c_p (T_min − T_in); the multiplier of the
  constraint as written is λ* = Σ n_i c_p / Q_s (objective units per kelvin).
- **OPT-A2** (G8): feed → splitter (decision r) → PH heater (decision Q) → sinks; purge → sink;
  min Q/Q_s + c (r n_F − n*)²/n_s² s.t. `S3.T ≥ T_min`. r* = n*/n_F − Δh n_s²/(2 c Q_s n_F),
  Q* = r* n_F Δh, Δh = Σ z_i c_p (T_min − T_in) per mole of feed.
- **OPT-A2b** (G8): A2 with a TP heater whose outlet-T specification is the decision; the
  objective names the heater duty `U-HEAT.Q` (a state variable). Same r*, Q*; T* = T_min.
- **OPT-N1** (G9): A1 with T_min above the bubble point, started liquid: before WO-5
  `NOT_VERIFIED` with `PHASE_REGIME_CHANGED(U-PHF)`.

Constants are chosen so that interior decisions sit ≥ 10 % of the box from either end and every
start's single-phase state is ≥ 10 K below its bubble point (checked here, not assumed).

Usage: `python benchmarks/opt/analytic.py [--write | --check]` (default `--check`): writes or
checks `requests/OPT-*.json` and `expected.json` (canonical JSON, numbers as decimal strings of
30 significant digits where they are expectations).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import mpmath as mp

mp.mp.dps = 30
HERE = Path(__file__).resolve().parent

# -- SYN-001 coefficient table (docs/derivations/SYN-001.md §1) ---------------------------------
COMPONENTS = ("A", "B", "C")
T_B = {"A": mp.mpf(320), "B": mp.mpf(360), "C": mp.mpf(400)}
L = {"A": mp.mpf(25000), "B": mp.mpf(30000), "C": mp.mpf(35000)}
CP = {"A": mp.mpf(100), "B": mp.mpf(100), "C": mp.mpf(100)}
V = {"A": mp.mpf("1.0e-4"), "B": mp.mpf("1.0e-4"), "C": mp.mpf("1.0e-4")}
T_R, P_R = mp.mpf(300), mp.mpf(100000)
R = mp.mpf("8.31446261815324")

# -- the cases' constants -----------------------------------------------------------------------
FEED = {"A": mp.mpf(1), "B": mp.mpf(1), "C": mp.mpf(1)}  # mol/s
T_IN, P = mp.mpf(300), mp.mpf(100000)
T_MIN = mp.mpf(330)
T_MIN_N1 = mp.mpf(355)
Q_S = mp.mpf(10000)
C, N_STAR, N_S = mp.mpf("0.25"), mp.mpf("1.5"), mp.mpf(1)
BOX = {
    "A1": {"Q": (1000.0, 11000.0)},
    "A2": {"r": (0.05, 0.95), "Q": (500.0, 6000.0)},
    "A2b": {"r": (0.05, 0.95), "T": (305.0, 336.0)},
    "N1": {"Q": (1000.0, 20000.0)},
}
#: OPT-C0 (WO-4b, D-32): OPT-A1 with the heater's heating-utility cost as the objective, through
#: E01's cost program. Its one operating line is `opex = price · hours · 3600 s/h · Q`, so
#: `ALPHA` (USD/yr per W) is by hand; the objective's scale `ALPHA · Q_S` makes it A1's `Q/Q_S`.
PRICE_PER_GJ, HOURS = mp.mpf(8), mp.mpf(8000)
ALPHA = PRICE_PER_GJ * mp.mpf("1e-9") * HOURS * 3600
ASSESSMENT_C0 = {
    "schema_version": "assessment-v1",
    "assessment_id": "opt-c0-heater-utility",
    "basis": {"currency": "USD", "year": 2020},
    "operation": {"hours_per_year": float(HOURS), "lifetime_years": 20, "discount_rate": 0.08},
    "correlation_set": "sslw-idaes-v1",
    "defaults": {"U_by_service": {"heating": 800.0}},
    "utilities": [
        {
            "utility_id": "LPS",
            "kind": "heating",
            "T_supply": 433.15,
            "dT_min": 10.0,
            "price": {"value": float(PRICE_PER_GJ), "per": "GJ"},
        }
    ],
}


def h_liquid(component: str, temperature: Any, pressure: Any) -> Any:
    return CP[component] * (temperature - T_R) + V[component] * (pressure - P_R)


def k_value(component: str, temperature: Any, pressure: Any) -> Any:
    exponent = (L[component] / R) * (1 / T_B[component] - 1 / temperature)
    return (P_R / pressure) * mp.exp(exponent + V[component] * (pressure - P_R) / (R * temperature))


def bubble_point(pressure: Any) -> Any:
    """Σ z_i K_i(T, P) = 1 for the feed composition."""
    total = sum(FEED.values())
    return mp.findroot(
        lambda t: sum(FEED[i] / total * k_value(i, t, pressure) for i in COMPONENTS) - 1, 345
    )


def duty(flow_fraction: Any, temperature: Any) -> Any:
    """The heater duty bringing `flow_fraction` of the feed from T_in to `temperature`."""
    return sum(
        flow_fraction * FEED[i] * (h_liquid(i, temperature, P) - h_liquid(i, T_IN, P))
        for i in COMPONENTS
    )


def outlet_temperature(flow_fraction: Any, q: Any) -> Any:
    return T_IN + q / (flow_fraction * sum(FEED[i] * CP[i] for i in COMPONENTS))


# -- the requests -------------------------------------------------------------------------------


def _linear(text: str, linear: dict[str, float], **extra: Any) -> dict[str, Any]:
    return {
        "text": text,
        "constant": extra.get("constant", 0),
        "linear": linear,
        "quadratic": extra.get("quadratic", []),
    }


def _t_min(value: Any) -> dict[str, Any]:
    return {
        "id": "T-min",
        "expression": _linear("S3.T", {"S3.T": 1}),
        "lower": float(value),
        "upper": None,
    }


def _decision(spec: str, box: tuple[float, float], scale: float, unit: str) -> dict[str, Any]:
    return {
        "specification_id": spec,
        "lower": box[0],
        "upper": box[1],
        "scale": scale,
        "unit": unit,
    }


def _a2_objective(duty_name: str) -> dict[str, Any]:
    """Q/Q_s + c (r n_F − n*)²/n_s², expanded: c n_F²/n_s² r² − 2 c n_F n*/n_s² r + c n*²/n_s²."""
    n_f = sum(FEED.values())
    return {
        "sense": "minimize",
        "expression": _linear(
            "Q/Q_s + c*(r*n_F - n_star)^2/n_s^2",
            {duty_name: float(1 / Q_S), "decision:SPEC-r": float(-2 * C * n_f * N_STAR / N_S**2)},
            constant=float(C * N_STAR**2 / N_S**2),
            quadratic=[
                {
                    "a": "decision:SPEC-r",
                    "b": "decision:SPEC-r",
                    "coefficient": float(C * n_f**2 / N_S**2),
                }
            ],
        ),
    }


def requests() -> dict[str, dict[str, Any]]:
    a1 = {
        "request_format": "openflowsheet-optimization-request-v1",
        "problem_id": "OPT-A1",
        "decisions": [_decision("SPEC-Q", BOX["A1"]["Q"], 10000.0, "W")],
        "objective": {
            "sense": "minimize",
            "expression": _linear("Q", {"decision:SPEC-Q": 1}),
            "scale": float(Q_S),
        },
        "constraints": [_t_min(T_MIN)],
        "starts": {"include_revision": True},
    }
    n1 = dict(
        a1,
        problem_id="OPT-N1",
        decisions=[_decision("SPEC-Q", BOX["N1"]["Q"], 10000.0, "W")],
        constraints=[_t_min(T_MIN_N1)],
    )
    a2 = {
        "request_format": "openflowsheet-optimization-request-v1",
        "problem_id": "OPT-A2",
        "decisions": [
            _decision("SPEC-r", BOX["A2"]["r"], 1.0, "1"),
            _decision("SPEC-Q", BOX["A2"]["Q"], 10000.0, "W"),
        ],
        "objective": _a2_objective("decision:SPEC-Q"),
        "constraints": [_t_min(T_MIN)],
        "starts": {"include_revision": True, "explicit": [[0.7, 5500.0]], "halton": 1},
    }
    a2b = dict(
        a2,
        problem_id="OPT-A2b",
        decisions=[
            _decision("SPEC-r", BOX["A2b"]["r"], 1.0, "1"),
            _decision("SPEC-T", BOX["A2b"]["T"], 10.0, "K"),
        ],
        objective=_a2_objective("U-HEAT.Q"),
        starts={"include_revision": True, "explicit": [[0.7, 325.0]], "halton": 1},
    )
    c0 = dict(
        a1,
        problem_id="OPT-C0",
        objective={
            "sense": "minimize",
            "expression": _linear("opex/opex_s", {"assessment:opex.total": 1}),
            "scale": float(ALPHA * Q_S),
        },
        assessment=ASSESSMENT_C0,
    )
    return {"OPT-A1": a1, "OPT-A2": a2, "OPT-A2b": a2b, "OPT-C0": c0, "OPT-N1": n1}


#: Each case's flowsheet and its revision values (start 0) of the decisions, in request order.
FLOWSHEET = {
    "OPT-A1": "OPT-A1",
    "OPT-N1": "OPT-A1",
    "OPT-A2": "OPT-A2",
    "OPT-A2b": "OPT-A2b",
    "OPT-C0": "OPT-A1",
}
REVISION_START = {
    "OPT-A1": (10500.0,),
    "OPT-C0": (10500.0,),
    "OPT-N1": (10500.0,),
    "OPT-A2": (0.5, 5000.0),
    "OPT-A2b": (0.5, 320.0),
}


# -- the expectations ---------------------------------------------------------------------------


def _interior(value: Any, box: tuple[float, float]) -> Any:
    low, high = (mp.mpf(box[0]), mp.mpf(box[1]))
    return min(value - low, high - value) / (high - low)


def expectations() -> dict[str, Any]:
    t_b = bubble_point(P)
    n_f = sum(FEED.values())
    flow_cp = sum(FEED[i] * CP[i] for i in COMPONENTS)
    q_a1 = duty(1, T_MIN)
    delta_h = duty(1, T_MIN) / n_f
    r_star = N_STAR / n_f - delta_h * N_S**2 / (2 * C * Q_S * n_f)
    q_a2 = r_star * n_f * delta_h
    f_a2 = q_a2 / Q_S + C * (r_star * n_f - N_STAR) ** 2 / N_S**2
    # Every start's single-phase state must be >= 10 K below the bubble point.
    halton = {
        "OPT-A2": (0.05 + 0.9 * mp.mpf(1) / 2, 500 + 5500 * mp.mpf(1) / 3),
        "OPT-A2b": (0.05 + 0.9 * mp.mpf(1) / 2, 305 + 31 * mp.mpf(1) / 3),
    }
    margins = {
        "OPT-A1/0": t_b - outlet_temperature(1, mp.mpf(10500)),
        "OPT-A2/0": t_b - outlet_temperature(mp.mpf("0.5"), mp.mpf(5000)),
        "OPT-A2/1": t_b - outlet_temperature(mp.mpf("0.7"), mp.mpf(5500)),
        "OPT-A2/2": t_b - outlet_temperature(*halton["OPT-A2"]),
        "OPT-A2b/0": t_b - mp.mpf(320),
        "OPT-A2b/1": t_b - mp.mpf(325),
        "OPT-A2b/2": t_b - halton["OPT-A2b"][1],
        "OPT-A2b/box-upper": t_b - mp.mpf(336),
    }
    assert all(m >= 10 for m in margins.values()), margins
    interior = {
        "OPT-A1/Q": _interior(q_a1, BOX["A1"]["Q"]),
        "OPT-A2/r": _interior(r_star, BOX["A2"]["r"]),
        "OPT-A2/Q": _interior(q_a2, BOX["A2"]["Q"]),
        "OPT-A2b/r": _interior(r_star, BOX["A2b"]["r"]),
        "OPT-A2b/T": _interior(T_MIN, BOX["A2b"]["T"]),
    }
    assert all(v >= mp.mpf("0.1") for v in interior.values()), interior
    q_n1 = duty(1, T_MIN_N1)
    assert T_MIN_N1 > t_b and _interior(q_n1, BOX["N1"]["Q"]) >= mp.mpf("0.1")

    def s(value: Any) -> str:
        return mp.nstr(value, 30, min_fixed=-30, max_fixed=30)

    return {
        "source": "benchmarks/opt/analytic.py (mpmath dps 30, SYN-001 coefficient table)",
        "bubble_point_K": s(t_b),
        "OPT-A1": {
            "Q": s(q_a1),
            "multiplier": s(flow_cp / Q_S),
            "objective": s(q_a1 / Q_S),
            "T_out": s(T_MIN),
        },
        "OPT-A2": {"r": s(r_star), "Q": s(q_a2), "objective": s(f_a2), "T_out": s(T_MIN)},
        "OPT-A2b": {"r": s(r_star), "Q": s(q_a2), "T": s(T_MIN), "objective": s(f_a2)},
        "OPT-C0": {
            "Q": s(q_a1),
            "opex": s(ALPHA * q_a1),
            "objective": s(q_a1 / Q_S),
            "multiplier": s(flow_cp / Q_S),
        },
        "OPT-N1": {
            "T_min": s(T_MIN_N1),
            "liquid_held_Q": s(q_n1),
            "status": "NOT_VERIFIED",
            "reason": "PHASE_REGIME_CHANGED(U-PHF)",
        },
        "margins_K": {k: s(v) for k, v in margins.items()},
        "interior_fraction": {k: s(v) for k, v in interior.items()},
        "revision_starts": {k: list(v) for k, v in REVISION_START.items()},
        "flowsheets": FLOWSHEET,
    }


def _bytes(document: Any) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()


def main(argv: list[str]) -> int:
    write = "--write" in argv
    files = {HERE / "expected.json": _bytes(expectations())}
    for name, request in requests().items():
        files[HERE / "requests" / f"{name}.json"] = _bytes(request)
    stale = []
    for path, payload in files.items():
        if write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        elif not path.exists() or path.read_bytes() != payload:
            stale.append(str(path.relative_to(HERE)))
    if stale:
        print(f"OPT analytic: stale {stale}; run with --write")
        return 1
    print(f"OPT analytic: {'written' if write else 'current'} ({len(files)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
