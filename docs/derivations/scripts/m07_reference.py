#!/usr/bin/env python3
"""M07 reference generator: ``benchmarks/m07/registration.json`` (M07 spec §12).

Usage (standard library only; no ``openflowsheet`` import, no network)::

    python3 -I docs/derivations/scripts/m07_reference.py          # write the registration
    python3 -I docs/derivations/scripts/m07_reference.py --check  # regenerate, compare bytes

Every claim the specification makes about its own registered numbers is a self-claim here
(GC-*): the script refuses to emit, and ``--check`` fails, when one stops being true. The
journey's rules (spec §4.4: rung decision, indifference set, fidelity effect, truth check TC-1,
bound activity) are implemented here independently of the build lane's
``scripts/m07_journey.py``. Their fixtures use dyadic numbers, so every boundary is exact in
binary64, and carry the expected labels that the build lane's tests compare against. The
measured facts the specification quotes (§3) are re-read from the committed records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

ROOT: Final = Path(__file__).resolve().parents[3]
OUT: Final = ROOT / "benchmarks" / "m07" / "registration.json"
SPEC: Final = ROOT / "docs" / "derivations" / "M07-spec.md"
LOOP_REAL: Final = ROOT / "benchmarks" / "m02" / "c1-loop-real.json"
LOOP_STANDIN: Final = ROOT / "benchmarks" / "m02" / "c1-loop-standin.json"
G12_CENTRE: Final = ROOT / "benchmarks" / "m02" / "g12-real-loop-v3.json"
G12_EDGES: Final = ROOT / "benchmarks" / "m02" / "g12-real-loop-v3-edges.json"
M04_MANIFEST: Final = ROOT / "benchmarks" / "m04" / "wo11-b2-it1-v3" / "manifest.json"

# -- the journey (spec §4) -------------------------------------------------------------------------
BOX: Final = ("653.15", "693.15")  # K; R-313/R-315 (v3 = rung V5); M05 REAL box; M04 box v2 k = 1
GRID: Final = tuple(str(Decimal(BOX[0]) + 5 * k) for k in range(9))  # decimal literals, 5 K apart
T_NOMINAL: Final = "673.15"  # SPEC-S3-T of C1-LOOP-M02-v1 (M02 §8.1); M05's u0
DELTA_T: Final = 0.5  # K; M05 N-F2 decision tolerance
HALF_WIDTH: Final = 20.0  # K; (hi - lo) / 2, M04/M05 scaling of T_in
BOUND_TOL_SCALED: Final = DELTA_T / HALF_WIDTH  # R-452: within δ_T of a bound is at the bound
R0_TOL: Final = 1e-12  # relative flatness tolerance of a rung's J over the grid (spec §4.4.1)
# Amendment 1 A1.5: X_pass = 0.25 exactly for the stand-in (xi = 0.25 n_N2,in); measured on
# wp/M07 94819ea, all nine points: X_pass - 0.25 = -2**-54 (one ulp of 0.25).
R0_X_PASS: Final = 0.25
R0_X_PASS_TOL_ABS: Final = 2.5e-13
R0_X_PASS_DEV_MEASURED: Final = 2.0**-54
# Spec §3 F2: measured on wp/M07 e35b16d, all nine grid points, inner solve at w* = (0.25, 0 K).
R0_J_MEASURED: Final = 0.46705958492513017  # mol/s; a regression value, not a validation value
R0_SPREAD_MEASURED: Final = 1.1885239704513566e-16  # (max - min) / max over the nine points
R0_J_GUARD_LO: Final = 0.40  # accidental-zero guard (spec §11 A06); not a derived bound
REGRESSION_TOL_REL: Final = 1e-12
VARIANTS: Final = {
    "real": {
        "model_id": "c1.reactor",
        "variant_id": "pymrm-6089593-g2-nz800-s123-v3",
        "sha256": "8b92540adc772a454e212b7054a98da4f7995899955a43a54d07669a70aa203c",
    },
    "standin": {
        "model_id": "c1.reactor_standin",
        "variant_id": "standin-x025-v1",
        "sha256": "f993dfc924794c72563164e28560b12224eddf5781f43fad21b80c52625f01c1",
    },
}
BUDGET: Final = {  # M07-budget-v1 (spec §4.5)
    "id": "M07-budget-v1",
    "R0": {"cold_experiments": 0, "wall_s": 600},
    "R1": {"cold_experiments": 60, "wall_s": 5400},
    "R2": {"cold_experiments": 0, "wall_s": 1200},
    "R3": {"cold_experiments": 400, "wall_s": 14400, "source": "M05-budget-v1 REAL"},
}
BUDGET_MARGIN: Final = (
    1.5  # R1's budget is at least this multiple of the measured worst case (GC-COST-1)
)

RUNG_OUTCOMES: Final = ("INDIFFERENT", "DECIDED", "INCOMPLETE")
FE_CLASSES: Final = (
    "FE_WORSE",
    "FE_UNCHANGED",
    "FE_CHANGED",
    "FE_WITHIN_RESOLUTION",
    "FE_NOT_DETERMINED",
)
TC1_OUTCOMES: Final = ("TC1_HOLDS", "TC1_CONTRADICTED", "TC1_NO_GRID", "TC1_NOT_APPLICABLE")
BOUNDS: Final = ("BOUND_LOWER", "BOUND_UPPER", "INTERIOR")
STUDY_HONEST: Final = ("DECISION_STABLE", "ITERATION_LIMIT", "BUDGET_EXHAUSTED")  # M05 §7.4
R2_OUTCOMES: Final = (
    "SURROGATE_NOT_PROMOTABLE",
    "INDIFFERENT",
    "DECIDED",
    "INCOMPLETE",
)  # spec §4.2
JOURNEY_DECISION_LABELS: Final = ("refined", "grid_only", "INSUFFICIENT_EVIDENCE")  # spec §4.4.7
UNSUPPORTED_REASONS: Final = (
    "reactor_environment_unavailable",
    "m05_study_unavailable",
    "surrogate_loop_unavailable",  # spec §4.6, Amendment 1 A1.3
)  # spec §4.6
# spec §4.6: byte-equal between M05's run commit and J, and between J and C
CARRY_JOURNEY: Final = (
    "src/openflowsheet/**",
    "benchmarks/m02/**",
    "benchmarks/m04/**",
    "benchmarks/m05/**",
    "requirements.lock",
    "the reactor environment lock (M02)",
)


def _best(points: list[dict[str, Any]]) -> dict[str, Any]:
    """Highest J; an exact tie goes to the lowest T (spec §4.4.1)."""
    return max(points, key=lambda p: (p["J"], -p["T"]))


def rung_decision(points: list[dict[str, Any]], t_nominal: float, n_grid: int) -> dict[str, Any]:
    """Spec §4.4.1. `points`: a rung's grid evaluations, each {T, J, verified}."""
    ok = [p for p in points if p["verified"]]
    if len(ok) < n_grid:
        return {"outcome": "INCOMPLETE", "decision": _best(ok)["T"] if ok else None}
    js = [p["J"] for p in ok]
    if max(js) - min(js) <= R0_TOL * max(abs(j) for j in js):
        return {"outcome": "INDIFFERENT", "decision": t_nominal}
    return {"outcome": "DECIDED", "decision": _best(ok)["T"]}


def indifference_set(points: list[dict[str, Any]]) -> list[float]:
    """Spec §4.4.2: verified grid T with J_k >= J_best - (e_k + e_best), ascending."""
    ok = [p for p in points if p["verified"]]
    if not ok:
        return []
    best = _best(ok)
    return sorted(p["T"] for p in ok if p["J"] >= best["J"] - (p["e"] + best["e"]))


def fe_class(f: dict[str, Any]) -> str:
    """Spec §4.4.4, in this precedence."""
    if f["t_after"] is None:
        return "FE_NOT_DETERMINED"
    dj = f["j_after"] - f["j_before"]
    eps = f["e_before"] + f["e_after"]
    if dj < -eps:
        return "FE_WORSE"
    if abs(f["t_after"] - f["t_before"]) <= DELTA_T:
        return "FE_UNCHANGED"
    if dj > eps:
        return "FE_CHANGED"
    return "FE_WITHIN_RESOLUTION"


def tc1(f: dict[str, Any]) -> dict[str, Any]:
    """Spec §4.4.5: the after-decision against the verified parent grid."""
    if f["t_after"] is None or f["j_after"] is None or f["e_after"] is None:
        return {"outcome": "TC1_NOT_APPLICABLE", "best_grid_T": None}
    grid = [p for p in f["grid"] if p["verified"]]
    if not grid:
        return {"outcome": "TC1_NO_GRID", "best_grid_T": None}
    best = _best(grid)
    if best["e"] is None:  # Amendment 1 A1.1: B's floor is missing; B is never replaced
        return {"outcome": "TC1_NOT_APPLICABLE", "best_grid_T": best["T"]}
    holds = f["j_after"] >= best["J"] - (f["e_after"] + best["e"])
    return {"outcome": "TC1_HOLDS" if holds else "TC1_CONTRADICTED", "best_grid_T": best["T"]}


def bound_activity(t: float) -> str:
    """Spec §4.4.6."""
    lo, hi = float(BOX[0]), float(BOX[1])
    if abs(t - lo) / HALF_WIDTH <= BOUND_TOL_SCALED:
        return "BOUND_LOWER"
    if abs(t - hi) / HALF_WIDTH <= BOUND_TOL_SCALED:
        return "BOUND_UPPER"
    return "INTERIOR"


# -- fixtures (dyadic, so every boundary is exact; GC-*-EXACT prove it) ----------------------------
_E: Final = 2.0**-21  # each point's noise floor; eps = e_before + e_after = 2**-20
_FE_FIXTURES: Final = (
    # id, t_before, t_after, j_before, j_after, expected   (e_before = e_after = _E)
    ("fe-01-moved-gain", 673.0, 653.0, 0.5, 0.5 + 2.0**-19, "FE_CHANGED"),
    ("fe-02-moved-gain-eq-eps", 673.0, 653.0, 0.5, 0.5 + 2.0**-20, "FE_WITHIN_RESOLUTION"),
    ("fe-03-moved-no-gain", 673.0, 653.0, 0.5, 0.5, "FE_WITHIN_RESOLUTION"),
    ("fe-04-moved-loss-eq-eps", 673.0, 653.0, 0.5, 0.5 - 2.0**-20, "FE_WITHIN_RESOLUTION"),
    ("fe-05-moved-loss", 673.0, 653.0, 0.5, 0.5 - 2.0**-19, "FE_WORSE"),
    ("fe-06-dt-eq-delta-gain", 673.0, 673.5, 0.5, 0.5 + 2.0**-19, "FE_UNCHANGED"),
    ("fe-07-dt-above-delta-gain", 673.0, 673.5 + 2.0**-20, 0.5, 0.5 + 2.0**-19, "FE_CHANGED"),
    ("fe-08-dt-eq-delta-loss", 673.0, 672.5, 0.5, 0.5 - 2.0**-19, "FE_WORSE"),
    ("fe-09-same-point", 673.0, 673.0, 0.5, 0.5, "FE_UNCHANGED"),
    ("fe-10-no-after", 673.0, None, 0.5, None, "FE_NOT_DETERMINED"),
)
_GRID_FIX: Final = (
    {"T": 653.0, "J": 0.5, "e": _E, "verified": True},
    {"T": 663.0, "J": 0.5 + 2.0**-18, "e": _E, "verified": True},
    {"T": 673.0, "J": 0.5 + 2.0**-17, "e": _E, "verified": False},  # unverified: never the best
)
_TC1_FIXTURES: Final = (
    # id, t_after, j_after, e_after, grid, expected outcome, expected best_grid_T
    ("tc1-01-dominates", 660.0, 0.5 + 2.0**-17, _E, list(_GRID_FIX), "TC1_HOLDS", 663.0),
    (
        "tc1-02-on-boundary",
        660.0,
        0.5 + 2.0**-18 - 2.0**-20,
        _E,
        list(_GRID_FIX),
        "TC1_HOLDS",
        663.0,
    ),
    (
        "tc1-03-beaten",
        660.0,
        0.5 + 2.0**-18 - 2.0**-19,
        _E,
        list(_GRID_FIX),
        "TC1_CONTRADICTED",
        663.0,
    ),
    ("tc1-04-at-grid-point", 663.0, 0.5 + 2.0**-18, _E, list(_GRID_FIX), "TC1_HOLDS", 663.0),
    (
        "tc1-05-tie-lowest-T",
        660.0,
        0.5,
        _E,
        [dict(_GRID_FIX[0]), {**_GRID_FIX[0], "T": 693.0}],
        "TC1_HOLDS",
        653.0,
    ),
    ("tc1-06-no-verified-grid", 660.0, 0.5, _E, [dict(_GRID_FIX[2])], "TC1_NO_GRID", None),
    ("tc1-07-no-after", None, None, None, list(_GRID_FIX), "TC1_NOT_APPLICABLE", None),
    (
        "tc1-08-no-floor-at-best",
        660.0,
        0.5 + 2.0**-18 - 2.0**-19,
        _E,
        [dict(_GRID_FIX[0]), {**_GRID_FIX[1], "e": None}, dict(_GRID_FIX[2])],
        "TC1_NOT_APPLICABLE",
        663.0,
    ),
    (
        "tc1-09-no-floor-after",
        660.0,
        0.5 + 2.0**-17,
        None,
        list(_GRID_FIX),
        "TC1_NOT_APPLICABLE",
        None,
    ),
)
_IS_FIXTURES: Final = (
    # id, points (T, J, e, verified), expected set
    (
        "is-01-single",
        [
            (653.0, 0.5, _E, True),
            (663.0, 0.5 + 2.0**-18, _E, True),
            (673.0, 0.5 + 2.0**-17, _E, True),
        ],
        [673.0],
    ),
    (
        "is-02-on-boundary",
        [
            (653.0, 0.5, _E, True),
            (663.0, 0.5 + 2.0**-17 - 2.0**-20, _E, True),
            (673.0, 0.5 + 2.0**-17, _E, True),
        ],
        [663.0, 673.0],
    ),
    (
        "is-03-unverified-ignored",
        [
            (653.0, 0.5, _E, True),
            (663.0, 0.5 + 2.0**-16, _E, False),
            (673.0, 0.5 + 2.0**-21, _E, True),
        ],
        [653.0, 673.0],
    ),
    (
        "is-04-unequal-floors",
        [(653.0, 0.5, 2.0**-17, True), (663.0, 0.5 + 2.0**-17, _E, True)],
        [653.0, 663.0],
    ),
)
_BOUND_FIXTURES: Final = (
    ("b-01", BOX[0], 0.0, "BOUND_LOWER"),
    ("b-02", BOX[0], 0.475, "BOUND_LOWER"),
    ("b-03", BOX[0], 0.525, "INTERIOR"),
    ("b-04", BOX[1], 0.0, "BOUND_UPPER"),
    ("b-05", BOX[1], -0.475, "BOUND_UPPER"),
    ("b-06", BOX[1], -0.525, "INTERIOR"),
    ("b-07", T_NOMINAL, 0.0, "INTERIOR"),
    ("b-08", BOX[0], 3.5e-5, "BOUND_LOWER"),
)


def _rung_fixtures() -> list[dict[str, Any]]:
    grid = [float(t) for t in GRID]
    flat = [{"T": t, "J": R0_J_MEASURED, "verified": True} for t in grid]
    tilt = [
        {"T": t, "J": R0_J_MEASURED * (1.0 + 1e-11 * k), "verified": True}
        for k, t in enumerate(grid)
    ]
    gap = [dict(p) for p in flat]
    gap[3]["verified"] = False
    return [
        {
            "id": "r-01-flat",
            "points": flat,
            "expected": {"outcome": "INDIFFERENT", "decision": float(T_NOMINAL)},
        },
        {
            "id": "r-02-tilted",
            "points": tilt,
            "expected": {"outcome": "DECIDED", "decision": grid[-1]},
        },
        {
            "id": "r-03-one-unverified",
            "points": gap,
            "expected": {"outcome": "INCOMPLETE", "decision": grid[0]},
        },
    ]


# -- the 0.2 gate sets (spec §7, §8) ---------------------------------------------------------------
GATES17: Final = tuple(f"V{n}" for n in range(11, 21)) + tuple(f"W{n}" for n in range(21, 28))
ALPHA_CLAUSE: Final = (
    r"\b(?:V(?:1[1-9]|20)|W2[12]) \([a-z0-9]+\)"  # scripts/v0_2_gate.py CLAUSE @ 758a902
)
V02_CLAUSE: Final = r"\b(?:V(?:1[1-9]|20)|W2[1-7]) \([a-z0-9]+\)"
GATE_SETS: Final = {
    # restated from wp/V02-alpha-gate scripts/v0_2_gate.py @ 758a902; unchanged
    "v0.2-alpha-gate-v1": {
        "covers": r"0\.2\.0a[1-9][0-9]*",
        "claimed": list(GATES17[:12]),
        "not_claimed": list(GATES17[12:]),
        "clause": ALPHA_CLAUSE,
        "policy_adr": "docs/adr/0028-v0.2-pre-release-policy.md",
        "verdict_document": "docs/reviews/V02-alpha-verdicts.md",
        "rc_record": "docs/v02-alpha-rc-record.md",
        "rc_steps": list(range(1, 13)),
        "rc_last_step": 13,
        "evidence_package": "M07a",
        "packages": ["M01", "M02"],
        "envelope_id": "v0.2-alpha-envelope-1",
        "required_adrs": ["0022", "0026", "0027", "0028", "0033", "0034", "0035"],
        "frank_items": ["N3", "V17 carry", "M02 N1"],
        "rejudge_waits": [["V13", "V17 carry"], ["V17", "V17 carry"], ["W21", "M02 N1"]],
    },
    "v0.2-gate-v1": {
        "covers": r"0\.2\.0(?:(?:b|rc)[1-9][0-9]*)?",
        "claimed": list(GATES17),
        "not_claimed": [],
        "clause": V02_CLAUSE,
        "policy_adr": "docs/adr/0042-v0.2.0-release-policy.md",
        "verdict_document": "docs/reviews/V02-verdicts.md",
        "rc_record": "docs/v02-rc-record.md",
        "rc_steps": list(range(1, 18)),
        "rc_last_step": 18,
        "evidence_package": "M07",
        "packages": ["M01", "M02", "M03", "M04", "M05", "M06"],
        "envelope_id": "v0.2-envelope-1",
        "required_adrs": [
            "0022",
            "0026",
            "0027",
            "0030",
            "0031",
            "0032",
            "0033",
            "0034",
            "0035",
            "0036",
            "0037",
            "0038",
            "0039",
            "0041",
            "0042",
        ],
        "frank_items": ["Claim set", "V17 carry", "M02 N1", "M03 N1"],
        "rejudge_waits": [
            ["V13", "V17 carry"],
            ["V17", "V17 carry"],
            ["W21", "M02 N1"],
            ["W24", "M03 N1"],
        ],
    },
}
# Table T-V (spec §8.2): the expectation is written by hand; GC-VER-1 compares it with the patterns.
VERSIONS: Final = (
    ("0.2.0", "v0.2-gate-v1"),
    ("0.2.0b1", "v0.2-gate-v1"),
    ("0.2.0b2", "v0.2-gate-v1"),
    ("0.2.0b10", "v0.2-gate-v1"),
    ("0.2.0rc1", "v0.2-gate-v1"),
    ("0.2.0rc12", "v0.2-gate-v1"),
    ("0.2.0a1", "v0.2-alpha-gate-v1"),
    ("0.2.0a10", "v0.2-alpha-gate-v1"),
    ("0.2.0b0", None),
    ("0.2.0rc0", None),
    ("0.2.0b01", None),
    ("0.2.0rc01", None),
    ("0.2.0c1", None),
    ("0.2.0RC1", None),
    ("0.2.0-rc1", None),
    ("0.2.0.rc1", None),
    ("0.2.0pre1", None),
    ("0.2.0rc1.dev1", None),
    ("0.2.0rc1.post1", None),
    ("0.2.0b1.dev0", None),
    ("0.2.0.post1", None),
    ("0.2.0.dev0", None),
    ("0.2.1", None),
    ("0.2.1rc1", None),
    ("0.2", None),
    ("0.2.0.0", None),
    ("0.2.0a0", None),
    ("0.1.1", None),
    ("1.2.0", None),
)
# W23-W27 clause labels of the 0.2 verdict document (spec §7.2). W21, W22: V02 alpha spec §6,
# unchanged.
W_CLAUSES: Final = {
    "W23": ("a", "b", "c", "d", "e", "f", "g"),
    "W24": ("a", "b", "c", "d", "e", "f", "g"),
    "W25": ("a", "b", "c", "d", "e", "f", "g", "h"),
    "W26": ("a", "b"),
    "W27": ("a", "b", "c", "d", "e", "f", "g", "h"),
}
RC_STEPS: Final = tuple(
    [(k, f"V02 alpha spec §8.2 step {k}, at C", f"M07a.A{29 + k}") for k in range(1, 13)]
    + [
        (
            13,
            "W23: M04's committed records re-checked at C (generator --check, manifest and "
            "evidence validation)",
            "M07.A60",
        ),
        (
            14,
            "W24: M03 nlp-tier A35-A42 and M05 G1-G10, G12, G13 at C in the audited environment",
            "M07.A60",
        ),
        (
            15,
            "W25: the journey carried to C by identity (spec §4.6) or re-run at C; check and "
            "replay at C",
            "M07.A61",
        ),
        (16, "W26: M06 design note G1-G15 at C; the browser test on CI x86-64", "M07.A60"),
        (
            17,
            "W27: coverage at C; the campaign's carry from C_W to C (spec §9); campaign.json "
            "recomputed",
            "M07.A53",
        ),
        (18, "scripts/v0_2_gate.py --rc C (not required in the record)", "M07.A36"),
    ]
)
NOT_ESTABLISHED: Final = (  # spec §6.3: the journey report's section 11, verbatim and in this order
    "No empirical validation: no number in this journey is compared with plant or experimental "
    "data.",
    "Not a plant design: C1-LOOP-M02-v1 is a registered test configuration.",
    "No global optimality.",
    "Nothing is claimed for reactor inlet temperatures outside 653.15-693.15 K, the reactor "
    "model's registered domain.",
    "Relative to the parent at its design grid (num_z = 800), whose NH3 output is estimated "
    "1.0-1.4 % high (M01 §10.5); an estimate, not a bound.",
    "The simple rung is synthetic (fixed per-pass N2 conversion 0.25, no temperature rise) and "
    "certifies nothing about the reactor.",
    "Reactor results flagged extrapolated (R-169) are counted, not excluded.",
    "No surrogate coverage claim at any operating point; the band-containment counts are not a "
    "coverage estimate.",
    "The K_NH3 enthalpy term rests on Frank's decision (R-152); its check against Rossetti et "
    "al. 2006 was not made.",
    "No reproduction of the reactor results on another architecture.",
    "No pressure-drop or selectivity comparison: zero pressure drop by convention (ADR 0022 D2), "
    "one reaction.",
    "No equilibrium-reactor rung: this journey does not show what an equilibrium model would "
    "decide.",
    "No sensitivities of the decision: the coupled route refuses them (ADR 0031 C3); the poll's "
    "curvature is reported only.",
)
BOUND_PHRASE: Final = (
    "The decision lies at the {side} bound of the reactor model's registered domain "
    "({value} K, R-315). The objective may improve beyond it; no model in this journey "
    "is registered there, and nothing is claimed about it."
)
REPORT_SECTIONS: Final = (
    "1. Summary",
    "2. Case and decision",
    "3. Rungs and their decisions",
    "4. The grid comparison",
    "5. Surrogate discrepancy",
    "6. Refinement",
    "7. Truth checks",
    "8. Uncertainty",
    "9. Compute cost",
    "10. Verification, validation and optimality, kept apart",
    "11. What this journey does not establish",
    "12. Provenance and replay",
)
FORBIDDEN_TOKENS: Final = (
    "optimal",
    "optimum",
    "validated",
    "guarantee",
    "guaranteed",
    "proves",
)  # whole words
WHAT_IT_IS_NOT: Final = (  # spec §7.5: CHANGELOG ## v0.2.0, "What it is not"
    "not a sandbox",
    "Linux only",
    "reactor results reproduce from records (R3)",
    "T_in 653.15-693.15 K, P 9-11 MPa, H2/N2 2.5-3.5, inerts 0.035-0.2, per-tube flow 0.5-2 x "
    "nominal",
    "no empirical validation of the C1 loop",
    "no global optimality",
    "the optimization routes need the optional nlp extra",
    "the stand-in reactor is synthetic",
    "no external benchmark score",
    "no CFD or Peclet refinement",
    "no equilibrium-stage subsystem",
)
CARRY_W27: Final = ("served_tool_list_sha256", "list_models", "coverage_rows")  # spec §10.3
CATALOGUE: Final = (  # spec §11; GC-CAT-2 compares it with the spec's table
    [
        f"M07.A{n:02d}"
        for n in (*range(0, 9), *range(10, 16), *range(20, 27), *range(30, 39), *range(40, 44))
    ]
    + [f"M07.A{n:02d}" for n in (50, 51, 60, 61, 62)]
)


class ClaimFailedError(Exception):
    pass


def claim(cond: bool, cid: str, detail: str) -> None:
    if not cond:
        raise ClaimFailedError(f"{cid}: {detail}")


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _strip(doc: dict[str, Any]) -> dict[str, Any]:
    d = json.loads(json.dumps(doc))
    for key in ("description", "title", "provenance"):
        d.pop(key, None)
    for inst in d["instances"]:
        if inst["id"] == "reactor":
            inst.pop("model")
    return d


def _spec_ids() -> list[str]:
    text = SPEC.read_text(encoding="utf-8")
    return re.findall(r"^\| (M07\.A\d{2}) \|", text, flags=re.M)


def _g12_facts() -> dict[str, Any]:
    """Spec §3 F3, re-read from M02's G12 records (GC-G12-*)."""
    centre, edges = _json(G12_CENTRE), _json(G12_EDGES)
    s = centre["summary"]
    states = {
        T_NOMINAL: {
            "verification_status": s["verification_status"],
            "experiments": s["experiments"],
            "solve_wall_s": s["solve_wall_s"],
            "n": s["reactor_inlet"]["n_mol_s"],
            "y_inert": s["reactor_inlet"]["y_inert"],
        }
    }
    for e in edges["edges"]:
        states[f"{e['T_in_spec_K']:.2f}"] = {
            "verification_status": e["verification_status"],
            "experiments": e["experiments"],
            "solve_wall_s": e["solve_wall_s"],
            "n": e["reactor_inlet"]["n_mol_s"],
            "y_inert": e["y_inert_solution"],
        }
    claim(sorted(states) == [BOX[0], T_NOMINAL, BOX[1]], "GC-G12-1", f"states {sorted(states)}")
    claim(
        all(
            v["verification_status"] == "VERIFIED" and v["experiments"] == 4
            for v in states.values()
        ),
        "GC-G12-1",
        "every G12 state VERIFIED with 4 experiments",
    )
    totals = [sum(states[t]["n"]) for t in (BOX[0], T_NOMINAL, BOX[1])]
    claim(
        totals[0] < totals[1] < totals[2],
        "GC-G12-2",
        f"reactor-inlet total not increasing in T_in: {totals}",
    )
    claim(
        all(v["y_inert"] >= 0.036 for v in states.values()),
        "GC-G12-3",
        "inert fraction below box v2's 0.036",
    )
    live = s["live_rerun"]
    claim(
        live["final_state_bitwise_equal"] is True and all(live["repeat_bitwise_equal"]),
        "GC-G12-4",
        "G12's live re-run is not bitwise",
    )
    return {
        "records": {
            "g12-real-loop-v3.json": _sha256(G12_CENTRE),
            "g12-real-loop-v3-edges.json": _sha256(G12_EDGES),
        },
        "reactor_inlet_total_mol_s": dict(zip((BOX[0], T_NOMINAL, BOX[1]), totals, strict=False)),
        "y_inert": {t: states[t]["y_inert"] for t in sorted(states)},
        "solve_wall_s": {t: states[t]["solve_wall_s"] for t in sorted(states)},
        "experiments_per_loop": 4,
        "live_rerun_bitwise_at_nominal": True,
    }


def _m04_facts() -> dict[str, Any]:
    """Spec §3 F1, re-read from M04's committed real iteration (GC-M04-1)."""
    m = _json(M04_MANIFEST)
    p = m["promotion"]
    claim(
        p["verdict"] == "NOT_PROMOTABLE"
        and p["not_promotable"] == ["band_not_finite"]
        and not p["insufficient"],
        "GC-M04-1",
        f"M04 verdict {p}",
    )
    claim(
        m["parent"]["boundary"]["hard_domain"]["T_K"] == [float(BOX[0]), float(BOX[1])],
        "GC-M04-1",
        "the surrogate's parent hard domain is not the journey's box",
    )
    claim(
        VARIANTS["real"]["variant_id"] in m["surrogate_id"]
        and m["model_id"] == "c1.reactor_surrogate",
        "GC-M04-1",
        f"surrogate {m['model_id']} {m['surrogate_id']} is not of the bound parent",
    )
    return {
        "record": str(M04_MANIFEST.relative_to(ROOT)),
        "sha256": _sha256(M04_MANIFEST),
        "surrogate_id": m["surrogate_id"],
        "verdict": p["verdict"],
        "reasons": p["not_promotable"],
        "expected_r2_outcome": "SURROGATE_NOT_PROMOTABLE",
        "expected_r2_evaluations": 0,
    }


def build() -> dict[str, Any]:
    grid = [float(t) for t in GRID]
    # GC-GRID-*: nine decimal literals spanning the box 5 K apart; the nominal is the centre point.
    claim(len(GRID) == 9 and GRID[0] == BOX[0] and GRID[-1] == BOX[1], "GC-GRID-1", f"grid {GRID}")
    claim(
        GRID[4] == T_NOMINAL and all(a < b for a, b in zip(grid, grid[1:], strict=False)),
        "GC-GRID-2",
        "nominal / order",
    )
    claim(
        all(Decimal(b) - Decimal(a) == 5 for a, b in zip(GRID, GRID[1:], strict=False)),
        "GC-GRID-3",
        "spacing",
    )
    claim((grid[-1] - grid[0]) / 2 == HALF_WIDTH, "GC-GRID-4", "half-width")
    claim(
        all(bound_activity(t) == "INTERIOR" for t in grid[1:-1]),
        "GC-GRID-5",
        "inner grid points interior",
    )
    # GC-LOOP-*: both loop files pin T_in at the nominal and differ only in the reactor's model pin.
    real, standin = _json(LOOP_REAL), _json(LOOP_STANDIN)
    for name, doc in (("real", real), ("standin", standin)):
        spec = [s for s in doc["specifications"] if s["id"] == "SPEC-S3-T"]
        claim(
            len(spec) == 1 and spec[0]["value"] == float(T_NOMINAL),
            "GC-LOOP-1",
            f"{name} SPEC-S3-T",
        )
        pin = [i["model"] for i in doc["instances"] if i["id"] == "reactor"][0]
        want = VARIANTS[name]
        claim(
            pin
            == {
                "id": want["model_id"],
                "version": want["variant_id"],
                "artifact_ref": want["sha256"],
            },
            "GC-LOOP-3",
            f"{name} reactor pin {pin}",
        )
    claim(_strip(real) == _strip(standin), "GC-LOOP-2", "the twins differ beyond the reactor pin")
    n2 = [s["value"] for s in real["specifications"] if s["id"] == "SPEC-S1-n-N2"]
    claim(len(n2) == 1, "GC-LOOP-4", "makeup N2 specification")
    j_max_n_balance = 2.0 * n2[0]  # steady-state N balance: NH3 product <= 2 n_N2,makeup
    # GC-R0-*: tolerance placement and the registered regression value.
    claim(
        R0_TOL >= 1e3 * R0_SPREAD_MEASURED and R0_TOL <= 1e-8, "GC-R0-1", "R0 tolerance placement"
    )
    claim(R0_J_GUARD_LO < R0_J_MEASURED <= j_max_n_balance, "GC-R0-2", "R0 J outside its bounds")
    claim(
        REGRESSION_TOL_REL >= 1e3 * R0_SPREAD_MEASURED,
        "GC-R0-3",
        "regression tolerance above the floor",
    )
    claim(
        R0_X_PASS_TOL_ABS >= 1e3 * R0_X_PASS_DEV_MEASURED and R0_X_PASS_TOL_ABS <= 1e-8 * R0_X_PASS,
        "GC-R0-4",
        "R0 X_pass tolerance placement",
    )
    rungs = _rung_fixtures()
    for fx in rungs:
        got = rung_decision(fx["points"], float(T_NOMINAL), len(GRID))
        claim(got == fx["expected"], "GC-RUNG-1", f"{fx['id']}: {got}")
    claim(
        {fx["expected"]["outcome"] for fx in rungs} == set(RUNG_OUTCOMES),
        "GC-RUNG-2",
        "outcomes covered",
    )
    # r-02's tilt (1e-11 relative per step, 8e-11 overall) must exceed R0_TOL, else it would read
    # INDIFFERENT.
    claim(8e-11 > 10 * R0_TOL, "GC-RUNG-3", "tilt fixture too close to the tolerance")
    iss = []
    for iid, pts, want in _IS_FIXTURES:
        points = [{"T": t, "J": j, "e": e, "verified": v} for t, j, e, v in pts]
        got = indifference_set(points)
        claim(got == want, "GC-IS-1", f"{iid}: {got} != {want}")
        iss.append({"id": iid, "points": points, "expected": want})
    claim(
        (0.5 + 2.0**-17 - 2.0**-20) == (0.5 + 2.0**-17) - 2 * _E,
        "GC-IS-EXACT",
        "is-02 boundary inexact",
    )
    fe = []
    for fid, tb, ta, jb, ja, want in _FE_FIXTURES:
        f = {
            "t_before": tb,
            "t_after": ta,
            "j_before": jb,
            "j_after": ja,
            "e_before": _E,
            "e_after": _E,
        }
        got = fe_class(f)
        claim(got == want, "GC-FE-1", f"{fid}: {got} != {want}")
        fe.append({"id": fid, **f, "expected": want})
    claim({x["expected"] for x in fe} == set(FE_CLASSES), "GC-FE-2", "classes covered")
    claim(
        abs(673.5 - 673.0) == DELTA_T and abs(672.5 - 673.0) == DELTA_T,
        "GC-FE-EXACT",
        "dT boundary inexact",
    )
    claim(
        (0.5 + 2.0**-20) - 0.5 == 2 * _E and (0.5 - 2.0**-20) - 0.5 == -2 * _E,
        "GC-FE-EXACT",
        "dJ boundary",
    )
    tcs = []
    for tid, ta, ja, ea, grid_pts, want, best in _TC1_FIXTURES:
        f = {"t_after": ta, "j_after": ja, "e_after": ea, "grid": grid_pts}
        got = tc1(f)
        claim(got == {"outcome": want, "best_grid_T": best}, "GC-TC1-1", f"{tid}: {got}")
        tcs.append({"id": tid, **f, "expected": got})
    claim(
        {x["expected"]["outcome"] for x in tcs} == set(TC1_OUTCOMES), "GC-TC1-2", "outcomes covered"
    )
    claim(
        (0.5 + 2.0**-18 - 2.0**-20) == (0.5 + 2.0**-18) - 2 * _E,
        "GC-TC1-EXACT",
        "tc1-02 boundary inexact",
    )
    f8 = {"t_after": 660.0, "j_after": 0.5 + 2.0**-18 - 2.0**-19, "e_after": _E}
    claim(
        tc1({**f8, "grid": [dict(_GRID_FIX[0]), {**_GRID_FIX[1], "e": 0.0}]})["outcome"]
        == "TC1_CONTRADICTED"
        and tc1({**f8, "grid": [dict(_GRID_FIX[0])]})
        == {"outcome": "TC1_HOLDS", "best_grid_T": 653.0}
        and tc1(
            {"t_after": 660.0, "j_after": 0.5 + 2.0**-17, "e_after": 0.0, "grid": list(_GRID_FIX)}
        )["outcome"]
        == "TC1_HOLDS",
        "GC-TC1-NULL",
        "tc1-08/09 would not catch a missing floor read as 0 or a skipped B",
    )
    bounds = []
    for bid, base, offset, want in _BOUND_FIXTURES:
        t = float(base) + offset
        got = bound_activity(t)
        claim(got == want, "GC-BOUND-1", f"{bid}: {t!r} -> {got}")
        bounds.append({"id": bid, "T": t, "expected": want})
    claim({b["expected"] for b in bounds} == set(BOUNDS), "GC-BOUND-2", "labels covered")
    # GC-G12-* and GC-COST-1: the measured real-loop facts, and R1's budget against them.
    g12 = _g12_facts()
    m04 = _m04_facts()
    worst_wall = max(g12["solve_wall_s"].values())
    r1 = BUDGET["R1"]
    claim(
        r1["wall_s"] >= BUDGET_MARGIN * len(GRID) * worst_wall
        and r1["cold_experiments"] >= BUDGET_MARGIN * len(GRID) * g12["experiments_per_loop"],
        "GC-COST-1",
        f"R1 budget below {BUDGET_MARGIN} x the measured worst case",
    )
    # GC-VER-*: the hand-written table equals the patterns; no version is covered twice.
    pats = {n: re.compile(s["covers"]) for n, s in GATE_SETS.items()}
    rows = []
    for v, want in VERSIONS:
        hits = [n for n, p in pats.items() if p.fullmatch(v)]
        claim(len(hits) <= 1, "GC-VER-2", f"{v} covered by {hits}")
        claim((hits[0] if hits else None) == want, "GC-VER-1", f"{v}: {hits} != {want}")
        rows.append({"version": v, "gate_set": want})
    claim(
        {r["gate_set"] for r in rows} == {None, *GATE_SETS} and len(rows) == 29,
        "GC-VER-3",
        "every set and none reached; 29 rows (spec §7.2)",
    )
    claim(
        all(
            dict(map(tuple, s["rejudge_waits"])).keys() <= set(s["claimed"])
            and {w for _, w in s["rejudge_waits"]} <= set(s["frank_items"])
            for s in GATE_SETS.values()
        ),
        "GC-SET-2",
        "a re-judgement waits on a gate not claimed or an answer not among the Frank items",
    )
    g = GATE_SETS["v0.2-gate-v1"]
    claim(
        tuple(g["claimed"]) == GATES17 and not g["not_claimed"],
        "GC-SET-1",
        "v0.2-gate-v1 claims 17",
    )
    alpha = GATE_SETS["v0.2-alpha-gate-v1"]
    claim(
        set(alpha["claimed"]) | set(alpha["not_claimed"]) == set(GATES17),
        "GC-SET-1",
        "alpha partitions 17",
    )
    v02, a = re.compile(V02_CLAUSE), re.compile(ALPHA_CLAUSE)
    labels = [f"{w} ({x})" for w, xs in W_CLAUSES.items() for x in xs]
    claim(
        all(v02.fullmatch(lab) for lab in labels) and not any(a.fullmatch(lab) for lab in labels),
        "GC-CLAUSE-1",
        "W23-W27 labels: v0.2 grammar only",
    )
    claim(
        all(v02.fullmatch(f"{x} (a)") and a.fullmatch(f"{x} (a)") for x in GATES17[:12]),
        "GC-CLAUSE-2",
        "V11-W22 labels read by both grammars",
    )
    claim(not v02.search("W28 (a)") and not v02.search("V10 (a)"), "GC-CLAUSE-3", "grammar bounds")
    claim(len(W_CLAUSES["W25"]) == 8, "GC-CLAUSE-4", "W25 has clauses (a)-(h), spec §5")
    claim(
        [s[0] for s in RC_STEPS] == list(range(1, 19))
        and g["rc_steps"] == list(range(1, 18))
        and g["rc_last_step"] == 18,
        "GC-RC-1",
        "RC steps dense; 1-17 required",
    )
    claim(
        len(set(NOT_ESTABLISHED)) == len(NOT_ESTABLISHED) == 13
        and len(set(WHAT_IT_IS_NOT)) == 11
        and len(REPORT_SECTIONS) == 12,
        "GC-PHRASE-1",
        "phrase counts",
    )
    forbidden = re.compile(r"\b(?:" + "|".join(FORBIDDEN_TOKENS) + r")\b", flags=re.I)
    claim(
        not any(forbidden.search(p) for p in (*REPORT_SECTIONS, BOUND_PHRASE)),
        "GC-PHRASE-2",
        "a report heading or the bound phrase holds a forbidden word",
    )
    claim(
        all(forbidden.search(t) for t in ("an optimal T", "the Optimum", "validated", "guaranteed"))
        and not forbidden.search("optimality, validation, unvalidated-ish"),
        "GC-PHRASE-4",
        "word matching",
    )
    claim(
        all(
            BOUND_PHRASE.format(side=s, value=v).count("R-315") == 1
            for s, v in (("lower", BOX[0]), ("upper", BOX[1]))
        ),
        "GC-PHRASE-3",
        "bound phrase",
    )
    total_cold = sum(BUDGET[r]["cold_experiments"] for r in ("R0", "R1", "R2", "R3"))
    total_wall = sum(BUDGET[r]["wall_s"] for r in ("R0", "R1", "R2", "R3"))
    claim(
        total_cold == 460 and total_wall == 21600,
        "GC-BUDGET-1",
        f"journey {total_cold} / {total_wall}",
    )
    ids = _spec_ids()
    claim(
        ids == sorted(ids) and len(set(ids)) == len(ids), "GC-CAT-1", "spec ids sorted and unique"
    )
    claim(
        ids == CATALOGUE, "GC-CAT-2", f"spec ids != catalogue: {sorted(set(ids) ^ set(CATALOGUE))}"
    )
    return {
        "schema": "m07-registration-v1",
        "specification": "docs/derivations/M07-spec.md",
        "journey": {
            "case": "C1-LOOP-M02-v1",
            "loops": {
                "real": "benchmarks/m02/c1-loop-real.json",
                "standin": "benchmarks/m02/c1-loop-standin.json",
            },
            "decision": {
                "spec_id": "SPEC-S3-T",
                "box_K": [float(x) for x in BOX],
                "grid_K": grid,
                "grid_literals": list(GRID),
                "t_nominal_K": float(T_NOMINAL),
                "delta_T_K": DELTA_T,
                "half_width_K": HALF_WIDTH,
                "bound_tol_scaled": BOUND_TOL_SCALED,
            },
            "objective": "c1-obj-nh3-liquid-v1",
            "study": "c1-trf-study-v1",
            "variants": VARIANTS,
            "rung_flatness_tol_rel": R0_TOL,
            "r0": {
                "J_mol_s": R0_J_MEASURED,
                "spread_rel_measured": R0_SPREAD_MEASURED,
                "regression_tol_rel": REGRESSION_TOL_REL,
                "J_guard_lo": R0_J_GUARD_LO,
                "J_max_n_balance": j_max_n_balance,
                "expected_outcome": "INDIFFERENT",
                "X_pass": R0_X_PASS,
                "X_pass_tol_abs": R0_X_PASS_TOL_ABS,
                "X_pass_dev_measured": R0_X_PASS_DEV_MEASURED,
                "provenance": "regression value measured at wp/M07 e35b16d; not a validation value",
            },
            "study_honest_statuses": list(STUDY_HONEST),
            "r2_outcomes": list(R2_OUTCOMES),
            "decision_labels": list(JOURNEY_DECISION_LABELS),
            "unsupported_reasons": list(UNSUPPORTED_REASONS),
            "m04_facts": m04,
            "budget": BUDGET,
            "g12_facts": g12,
        },
        "fixtures": {"rung": rungs, "indifference": iss, "fe": fe, "tc1": tcs, "bound": bounds},
        "report": {
            "sections": list(REPORT_SECTIONS),
            "not_established": list(NOT_ESTABLISHED),
            "bound_phrase": BOUND_PHRASE,
            "forbidden_tokens": list(FORBIDDEN_TOKENS),
        },
        "gate": {
            "gate_sets": GATE_SETS,
            "versions": rows,
            "w_clauses": {k: list(v) for k, v in W_CLAUSES.items()},
            "rc_steps": [{"step": s, "what": w, "assertion": x} for s, w, x in RC_STEPS],
            "changelog_what_it_is_not": list(WHAT_IT_IS_NOT),
            "w27_carry": list(CARRY_W27),
        },
        "carry": {"journey_files": list(CARRY_JOURNEY), "w27": list(CARRY_W27)},
        "catalogue": CATALOGUE,
    }


def render(doc: dict[str, Any]) -> str:
    return json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        text = render(build())
    except ClaimFailedError as exc:
        print(f"refused: self-claim failed: {exc}", file=sys.stderr)
        return 1
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print(
                f"FAIL: {OUT.relative_to(ROOT)} differs from the regenerated bytes", file=sys.stderr
            )
            return 1
        print("m07_reference --check: PASS")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
