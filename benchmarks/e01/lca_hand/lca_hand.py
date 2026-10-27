"""E01 WO-A5 (design §4.8, §5.1 R-861): the LCA hand expectations, written by track A for track B's
LCA contributor. Imports nothing from `openflowsheet`; mpmath at 30 digits.

1. `test-background-v1` (§4.8.5) solved by hand: unit scores `q_k = c·B·s_k` with `A s_k = e_k`, for
   the three activities, compared with the design's rationals (A24).
2. P4's inventory: P1 (S11 TH-C1, the report fixture `p1_th_c1.json`) with an LCA section on
   `test-background-v1`. The boundary quantities φ are the fixture's recorded values (below), not
   recomputed. Exchanges (document fragment `P4_LCA`):
   - electricity (`utilities[EL].lca`): `tb.electricity`, 1.0 kWh per kWh, on the net electricity
     consumption − generation (the pump's W/η_m minus the turbine's −W·η_gen; generation negative,
     §4.8.1);
   - heating (`utilities[HPS].lca`): `tb.heat`, 1.0 MJ per MJ of the boiler duty |Q_B|;
   - the raw material S1 (`materials[S1].lca`): `tb.chemical_x`, 1.0 kg per kg of ṁ_S1.
   Convention (stated, for B2 to match or escalate): `a_k = amount · φ_k / SI(per)`, in the
   activity's unit per second; `impact.<m>.rate = Σ_k q_{m,k} a_k` (no allocation, no direct
   emissions: TH-C1 has no emission stream); `.annual = rate·3600·h_op`; `.per_fu = rate / ṁ_FU`
   with the FU S5's mass.
3. Superposition: one solve `A s = Σ_k a_k e_k` gives the same rate as `Σ_k q_k a_k`.

Usage: `python benchmarks/e01/lca_hand/lca_hand.py` writes `lca_hand.yaml` beside it;
`--print` writes the YAML to stdout instead.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import mpmath
import yaml

mpmath.mp.dps = 30
HERE = Path(__file__).resolve().parent
F = mpmath.mpf

# -- §4.8.5: test-background-v1 ------------------------------------------------------------------
ACTIVITIES = ("tb.electricity", "tb.heat", "tb.chemical_x")  # kWh, MJ, kg
#: Technosphere matrix (rows: products electricity, heat, chemical_x; columns: activities).
A = mpmath.matrix(
    [
        [F(1), F("-0.125"), F("-0.5")],
        [F("-0.25"), F(1), F(-2)],
        [F(0), F(0), F(1)],
    ]
)
#: Biosphere per unit activity (rows: CO2 fossil, CH4 fossil), kg.
B = mpmath.matrix([[F("0.5"), F("0.0625"), F("0.25")], [F(0), F("0.001953125"), F(0)]])
#: `climate_change_test`: CO2 fossil 1.0, CH4 fossil 29.8 (kg CO2-eq per kg).
C = mpmath.matrix([[F(1), F("29.8")]])
#: The design's hand values (§4.8.5), as rationals.
DESIGN_Q = {
    "tb.electricity": F("16.965625") / 31,
    "tb.heat": F("5.8625") / 31,
    "tb.chemical_x": F("27.9578125") / 31,
}

# -- P1's recorded boundary quantities -----------------------------------------------------------
# From tests/fixtures/schemas/assessment_report/valid/p1_th_c1.json,
# state_sha256 a23b2407ff55ea7c4056d39f87be504592e4759ea13fdc04f4273eb304ef5c3d.
RECORDED = {
    "w_consumed_W": ("items[P.drive].size.power", "101.2739580708677"),
    "w_turbine_W": ("items[T].size.power", "15905.094362301697"),
    "eta_gen": ("items[T].inputs.eta_gen (default generator_efficiency)", "0.95"),
    "q_boiler_W": ("items[B].inputs.Q", "54752.49787667207"),
    "m_s1_kg_s": (
        "S1: 1.0 mol/s H2O x M 0.018015268 kg/mol (benchmarks/s05/components.yaml)",
        "0.018015268",
    ),
    "m_fu_kg_s": ("S5: 1.0 mol/s H2O (sat.L 1.0, sat.V 0.0) x M", "0.018015268"),
    "hours_per_year": ("operation.hours_per_year", "8000"),
}
P4_LCA = {
    "utilities.EL.lca": [
        {"table": "test-background-v1", "activity": "tb.electricity", "amount": 1.0, "per": "kWh"}
    ],
    "utilities.HPS.lca": [
        {"table": "test-background-v1", "activity": "tb.heat", "amount": 1.0, "per": "MJ"}
    ],
    "materials.S1.lca": [
        {"table": "test-background-v1", "activity": "tb.chemical_x", "amount": 1.0, "per": "kg"}
    ],
    "lca.functional_unit": {"connection": "S5", "basis": "mass_total"},
    "lca.categories": ["climate_change_test"],
}
SI = {"kWh": F("3.6e6"), "MJ": F("1e6"), "kg": F(1)}


def unit_scores() -> dict[str, mpmath.mpf]:
    scores = {}
    for k, activity in enumerate(ACTIVITIES):
        e = mpmath.matrix([1 if i == k else 0 for i in range(3)])
        s = mpmath.lu_solve(A, e)
        scores[activity] = (C * (B * s))[0, 0]
    return scores


def inventory() -> dict[str, mpmath.mpf]:
    r = {name: F(value) for name, (_, value) in RECORDED.items()}
    net = r["w_consumed_W"] - r["w_turbine_W"] * r["eta_gen"]
    return {
        "tb.electricity": F(1) * net / SI["kWh"],
        "tb.heat": F(1) * r["q_boiler_W"] / SI["MJ"],
        "tb.chemical_x": F(1) * r["m_s1_kg_s"] / SI["kg"],
    }


def s30(x: mpmath.mpf) -> str:
    return mpmath.nstr(x, 30, min_fixed=-mpmath.inf, max_fixed=mpmath.inf)


def build() -> dict[str, object]:
    q = unit_scores()
    a = inventory()
    for activity in ACTIVITIES:
        assert abs(q[activity] - DESIGN_Q[activity]) < F("1e-27"), activity
    contributions = {k: q[k] * a[k] for k in ACTIVITIES}
    rate = (
        contributions["tb.electricity"] + contributions["tb.heat"] + contributions["tb.chemical_x"]
    )
    s = mpmath.lu_solve(A, mpmath.matrix([a[k] for k in ACTIVITIES]))
    rate_superposed = (C * (B * s))[0, 0]
    assert abs(rate - rate_superposed) <= F("1e-27") * abs(rate)
    hours = F(RECORDED["hours_per_year"][1])
    fu = F(RECORDED["m_fu_kg_s"][1])

    def number(x: mpmath.mpf) -> dict[str, object]:
        return {"value": float(x), "mp30": s30(x)}

    return {
        "id": "e01-lca-hand-v1",
        "script": "benchmarks/e01/lca_hand/lca_hand.py",
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "mpmath_dps": 30,
        "background": {
            "table": "test-background-v1",
            "category": "climate_change_test",
            "unit": "kg CO2-eq per activity unit",
            "unit_scores": {k: number(q[k]) for k in ACTIVITIES},
            "a24_design_values_agree_to": "1e-27",
        },
        "p4": {
            "host": "S11 TH-C1 (P1 fixture p1_th_c1.json)",
            "recorded_inputs": {k: {"source": src, "value": v} for k, (src, v) in RECORDED.items()},
            "document_fragment": P4_LCA,
            "convention": "a_k = amount * phi_k / SI(per); rate = sum_k q_k a_k; no allocation; "
            "no direct emissions",
            "exchange_amounts_per_s": {k: number(a[k]) for k in ACTIVITIES},
            "contributions_kg_co2eq_per_s": {k: number(contributions[k]) for k in ACTIVITIES},
            "impact.climate_change_test.rate": number(rate),
            "impact.climate_change_test.annual": number(rate * 3600 * hours),
            "impact.climate_change_test.per_fu": number(rate / fu),
            "superposition_agrees_to": "1e-27 relative",
        },
    }


def main() -> None:
    text = yaml.safe_dump(build(), sort_keys=False, allow_unicode=True, width=100)
    if sys.argv[1:] == ["--print"]:
        sys.stdout.write(text)
    else:
        (HERE / "lca_hand.yaml").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
