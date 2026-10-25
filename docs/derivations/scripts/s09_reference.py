"""S09 reference generator: the registered inputs of BioSTEAM as the third column reference.

``docs/derivations/S09-spec.md`` is the authority. This script emits ``s09_cases.json``: inputs
only (the pairs, the controls, BioSTEAM's registered SYN-001 definition, solve path, ladder, outer
loop, thresholds, the three-tool X31 table and the blindness lists), and the claims that make S09's
statements about its own numbers executable. It imports nothing from ``openflowsheet`` and runs no
tool. It reads three S03 files and pins each by SHA-256: ``s03_cases.json`` (S03's inputs),
``s03_reference.json`` (S03's twin, for PC-LI's tool model and the twin temperatures) and
``benchmarks/s03/references/comparison.json`` (S03's committed classifications, for the three-tool
X31 table's reduction claim). Closed forms are evaluated with mpmath at 50 significant digits.

Usage::

    python docs/derivations/scripts/s09_reference.py --emit    # write s09_cases.json
    python docs/derivations/scripts/s09_reference.py --check   # re-derive; refuse; byte-compare

``--check`` refuses when any claim fails, then byte-compares ``s09_cases.json``. The output is
byte-reproducible: no time stamp, no machine data, ``json.dumps(indent=1, ensure_ascii=False)``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Any

import mpmath as mp

mp.mp.dps = 50
getcontext().prec = 50

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
S03_CASES = HERE / "s03_cases.json"
S03_REF = HERE / "s03_reference.json"
S03_COMPARISON = ROOT / "benchmarks" / "s03" / "references" / "comparison.json"
OUT = HERE / "s09_cases.json"

# Pins (S09 §0): the S03 files as merged at main 390e0af5. A different hash stops the generator.
PINS = {
    "docs/derivations/scripts/s03_cases.json": (
        "c901d6c90f4b700b92ff98e2a01ae7e8f1d5557b80dd647e3b14e089d3703f39"
    ),
    "docs/derivations/scripts/s03_reference.json": (
        "95ef9bd2551267e37c225764b5ed159d9f14911c2bb8b05a5905b8b65cec0c67"
    ),
    "benchmarks/s03/references/comparison.json": (
        "5c7d139c0547f17bfa318f33b106cdb5749b9eaacbccb07cf1dedd570593585d"
    ),
}

# SYN-001 constants (docs/derivations/SYN-001.md §1), as Decimal strings. The BioSTEAM harness
# imports the
# same constants from spikes/references/t06_fixtures.py (S09 §4.2); claim C4 below checks that
# file's values.
T_B = {"A": "320", "B": "360", "C": "400"}
L_VAP = {"A": "25000", "B": "30000", "C": "35000"}
CP = "100"
V_LIQ = "1e-4"
T_R = "300"
P_R = "1e5"
R_GAS = "8.31446261815324"
TOOL_T_REF = "298.15"  # thermosteam's default Chemical.T_ref (S09 §4.2)

READBACK_T = ("310", "347", "385", "430")
RUNGS = (
    ("inside out", "fixed-point"),
    ("phenomena", "fixed-point"),
    ("simultaneous correction", "hybr"),
    ("sequential modular", "fixed-point"),
)
COMPARED = (
    "RC1",
    "RC2",
    "RC3",
    "RC4",
    "RC5",
    "RC6",
    "RC7",
    "RC1-RR",
    "RC1-BR",
    "RC1-z",
    "RC2-RR",
    "RC2-B",
    "RC2-z",
    "RC3-Q",
    "RC3-z",
    "RC4-D",
    "RC4-z",
)
COUNTED = ("RC1", "RC2", "RC3", "RC4")
INVERSE = {"RC5": "purity", "RC6": "recovery", "RC7": "temperature"}
BIOSTEAM_CLASSES = ("AGREE", "DISAGREE", "absent", "unusable", "access", "ours")

claims: list[str] = []


class ClaimError(RuntimeError):
    pass


def claim(condition: bool, text: str) -> None:
    if not condition:
        raise ClaimError(f"claim failed: {text}")
    claims.append(text)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def s25(x: Any) -> str:
    return mp.nstr(mp.mpf(x), 25, min_fixed=-5, max_fixed=30)


# ---- §8: the three-tool X31 table (rows 1-4 are S03 §17.5's; rows 5-7 count AGREEs)
# -------------------------


def pair_class(row: dict[str, Any]) -> str:
    """S03 §17.5's class of a committed S03 pair row (as S03's classifier's `pair_class`)."""
    if row["classification"] in ("AGREE", "DISAGREE"):
        return "comparable"
    return {0: "absent", "17.3(b)": "unusable", 1: "access", 3: "ours"}.get(
        row["rule"], f"unclassified({row['rule']})"
    )


def case_row(pairs: dict[str, tuple[str, str]]) -> tuple[int, str]:
    """pairs: tool -> (class, classification). The first matching row decides (S09 §8.1)."""
    classes = {t: c for t, (c, _) in pairs.items()}
    words = {t: w for t, (_, w) in pairs.items()}
    if any(c == "ours" for c in classes.values()):
        return 1, "not met: a column finding (S02 or S06)"
    if any(w == "DISAGREE" for w in words.values()):
        return 2, "not met: a disagreement finding, until the design lane resolves it"
    if any(c == "access" for c in classes.values()):
        return 3, "blocked"
    if any(c == "unusable" for c in classes.values()):
        return 4, "not met: an available reference could not be shown to see a known difference"
    agree = sorted(t for t, w in words.items() if w == "AGREE")
    absent = sorted(t for t, c in classes.items() if c == "absent")
    if len(agree) + len(absent) != len(pairs):
        return 0, f"no row matches: {classes}"
    if len(agree) >= 2:
        return 5, f"{['', '', 'two', 'three'][len(agree)]} references ({', '.join(agree)})"
    if len(agree) == 1:
        return 6, f"one reference ({agree[0]}), absent: {', '.join(absent)}"
    return 7, "no reference: not met"


def clause(rows: dict[str, int]) -> str:
    if all(r == 5 for r in rows.values()):
        return "met with two references"
    if any(r in (1, 2, 4, 7, 0) for r in rows.values()):
        return "not met"
    if any(r == 3 for r in rows.values()):
        return "blocked"
    two = sum(1 for r in rows.values() if r == 5)
    return f"met where available, {two} of {len(rows)} with two references"


def biosteam_pair(cls: str) -> tuple[str, str]:
    return {
        "AGREE": ("comparable", "AGREE"),
        "DISAGREE": ("comparable", "DISAGREE"),
        "absent": ("absent", "NOT_COMPARABLE"),
        "unusable": ("unusable", "NOT_COMPARABLE"),
        "access": ("access", "NOT_COMPARABLE"),
        "ours": ("ours", "NOT_COMPARABLE"),
    }[cls]


# ---- the document
# ---------------------------------------------------------------------------------------------


def build() -> dict[str, Any]:
    claims.clear()
    # C1: pins.
    for rel, pinned in PINS.items():
        claim(sha256(ROOT / rel) == pinned, f"C1 {rel} has the pinned SHA-256 {pinned[:12]}")
    cases = json.loads(S03_CASES.read_text())
    ref = json.loads(S03_REF.read_text())
    comparison = json.loads(S03_COMPARISON.read_text())

    # C2: the registered pairs are S03's compared cases and PC-P, plus PC-LB; PC-L and PC-LI are not
    # BioSTEAM's.
    s03_ids = list(cases["cases"])
    for cid in COMPARED + ("PC-P",):
        claim(cid in s03_ids, f"C2 {cid} is a case of s03_cases.json")
    claim(
        set(s03_ids) - set(COMPARED) - {"PC-P"} == {"PC-L", "PC-LI"},
        "C2 every S03 case other than PC-L and PC-LI is a BioSTEAM pair",
    )
    for cid in COMPARED:
        claim(cases["cases"][cid]["role"] == "comparison", f"C2 {cid} has role comparison in S03")

    # C3: PC-LB is RC1's inputs with BioSTEAM's Hvap = L_i + P_r v_i, the value of S03's PC-LI
    # input.
    rc1, pcli = cases["cases"]["RC1"], cases["cases"]["PC-LI"]
    for key in (
        "stage_count",
        "condenser",
        "reboiler",
        "stage_pressures_Pa",
        "intermediate_duties_W",
        "inlets",
        "specifications",
        "quantities",
    ):
        claim(
            rc1[key] == pcli[key],
            f"C3 PC-LI's {key} equals RC1's, so PC-LI's tool-model root is on RC1's inputs",
        )
    hvap_pclb = {}
    pcli_hform = cases["tool_settings"]["IDAES_amendment_2"]["h_form_ig_J_per_mol_PC-LI"]
    for k, c in enumerate("ABC"):
        v = Decimal(L_VAP[c]) + Decimal(P_R) * Decimal(V_LIQ)
        hvap_pclb[c] = format(v.normalize(), "f")
        claim(
            v == Decimal(pcli_hform[k]),
            f"C3 Hvap_PC-LB[{c}] = L + P_r v = {v} J/mol = S03's PC-LI h_form,ig[{c}]",
        )
        claim(
            v - Decimal(L_VAP[c]) == Decimal(10),
            f"C3 PC-LB shifts h^V - h^L of {c} by exactly P_r v = 10 J/mol",
        )

    # C4: PC-LB's tool model is PC-LI's. At P = P_r both have K_i = Psat_i/P and h^V_i - h^L_i = L_i
    # + P_r v_i at
    # every T; their h^L differ by a constant per component that is the same for A, B and C, so it
    # cancels in every
    # balance (S03 §4). Checked at the readback temperatures; the offset is c_p (T_r - 298.15) = 185
    # J/mol.
    offset = Decimal(CP) * (Decimal(T_R) - Decimal(TOOL_T_REF))
    claim(
        offset == Decimal(185),
        "C4 the default-datum offset c_p (T_r - 298.15 K) is exactly 185 J/mol",
    )
    for c in "ABC":
        for t in READBACK_T:
            tt = Decimal(t)
            bio_l = Decimal(CP) * (tt - Decimal(TOOL_T_REF))
            bio_v = bio_l + Decimal(hvap_pclb[c])
            idaes_l = Decimal(CP) * (tt - Decimal(T_R))  # + v (P - P_r) = 0 at P_r
            idaes_v = Decimal(CP) * (tt - Decimal(T_R)) + Decimal(pcli_hform["ABC".index(c)])
            claim(
                bio_v - bio_l == idaes_v - idaes_l,
                f"C4 {c} at {t} K: PC-LB's h^V - h^L equals PC-LI's",
            )
            claim(
                bio_l - idaes_l == offset,
                f"C4 {c} at {t} K: h^L offset to PC-LI's model is the common 185 J/mol",
            )
    # C4b: the harness takes SYN-001's constants from t06_fixtures.py (pinned); they equal the ones
    # used here.
    fixtures = ROOT / "spikes" / "references" / "t06_fixtures.py"
    claim(
        sha256(fixtures) == "c6320cc81ea4bf08c36f7d7b5aca19180c2109fd66e4e23c84476d35286ba61f",
        "C4b spikes/references/t06_fixtures.py has S03 §17.6's pinned SHA-256",
    )
    ns: dict[str, Any] = {}
    src = fixtures.read_text()
    exec(
        compile(
            src.split("REPO_ROOT =")[0]
            + "\n"
            + src[src.index("# SYN-001 constants") : src.index("PLACEHOLDER_TC")],
            str(fixtures),
            "exec",
        ),
        ns,
    )
    for c in "ABC":
        claim(
            Decimal(repr(ns["T_BOIL"][c])) == Decimal(T_B[c]),
            f"C4b t06_fixtures T_BOIL[{c}] = {T_B[c]} K",
        )
        claim(
            Decimal(repr(ns["L_VAP"][c])) == Decimal(L_VAP[c]),
            f"C4b t06_fixtures L_VAP[{c}] = {L_VAP[c]} J/mol",
        )
    for name, value in (
        ("CP", CP),
        ("V_LIQ", V_LIQ),
        ("T_REF", T_R),
        ("P_REF", P_R),
        ("R_GAS", R_GAS),
    ):
        claim(Decimal(repr(ns[name])) == Decimal(value), f"C4b t06_fixtures {name} = {value}")
    pc = ref["controls"]["PC-LI"]
    claim(
        float(pc["max_ratio"]) >= 100.0 and pc["argmax"] == "Q_reboiler",
        f"C4 the reused PC-LI tool-model discrimination is {pc['max_ratio']} tolerances "
        f"({pc['argmax']}) >= 100",
    )

    # C5: readback expectations, closed forms at 50 digits, two algebraically equal forms agreeing
    # to 1e-40.
    psat: dict[str, list[str]] = {}
    for c in "ABC":
        row = []
        for t in READBACK_T:
            a = mp.mpf(P_R) * mp.exp(
                mp.mpf(L_VAP[c]) / mp.mpf(R_GAS) * (1 / mp.mpf(T_B[c]) - 1 / mp.mpf(t))
            )
            antoine_a = mp.log(mp.mpf(P_R)) + mp.mpf(L_VAP[c]) / (mp.mpf(R_GAS) * mp.mpf(T_B[c]))
            b = mp.exp(antoine_a - (mp.mpf(L_VAP[c]) / mp.mpf(R_GAS)) / mp.mpf(t))
            claim(
                abs(a - b) / a < mp.mpf("1e-40"),
                f"C5 Psat_{c}({t} K) closed form, two forms agree to 1e-40",
            )
            row.append(s25(a))
        psat[c] = row

    # C6: the equilibrium threshold's temperature equivalent. At an equilibrium stage sum_c K_c x_c
    # = 1, so the
    # component with the largest K_c x_c has K_c x_c >= 1/3 and d(K_c x_c)/dT = K_c x_c L_c/(R T^2)
    # >=
    # L_min/(3 R T^2). A residual r on that component therefore bounds a pure temperature error by
    # dT <= 3 R T^2 r / L_min. Evaluated at the hottest registered twin stage; claimed <= 0.01
    # tolerance.
    t_max = max(
        mp.mpf(q["value"])
        for cid in COMPARED
        for name, q in ref["twin"][cid]["quantities"].items()
        if name.startswith("T[")
    )
    r_eq = mp.mpf("1e-8")
    d_t = 3 * mp.mpf(R_GAS) * t_max**2 * r_eq / mp.mpf(min(L_VAP.values(), key=float))
    tol_t = mp.mpf("1e-5") + mp.mpf("1e-6") * t_max
    claim(
        d_t / tol_t <= mp.mpf("0.01"),
        f"C6 an equilibrium residual of 1e-8 bounds a temperature-only error by {mp.nstr(d_t, 4)} "
        "K "
        f"= {mp.nstr(d_t / tol_t, 3)} tolerance at T_max {mp.nstr(t_max, 8)} K",
    )

    # C7: the outer loop's termination is one tenth of rule 2d's threshold for each kind (S03
    # §17.4).
    s03_thr = comparison["thresholds"]["rule2d_specification"]
    ytol = {}
    for kind, (thr, basis) in sorted(s03_thr.items()):
        ytol[kind] = [format(Decimal(thr) / 10, "E"), basis]
        claim(
            Decimal(ytol[kind][0]) * 10 == Decimal(thr),
            f"C7 outer ytol for {kind} is rule 2d's {thr} / 10",
        )

    # C8: the expansion reaches [1/16, 32] from the starts 1 and 2 in four steps each way; units are
    # exact.
    claim(
        Decimal(2) * Decimal(2) ** 4 == 32 and Decimal(1) / Decimal(2) ** 4 == Decimal("0.0625"),
        "C8 the bracket search covers [1/16, 32]",
    )
    claim(
        Decimal(3600) / Decimal(1000) == Decimal("3.6"),
        "C8 1 mol/s = 3.6 kmol/h and 1 W = 3.6 kJ/h exactly",
    )

    # C9: the three-tool table reduces to S03 §17.5 on S03's committed two-tool rows.
    rows = {(r["case"], r["tool"]): r for r in comparison["rows"]}
    s03_x = comparison["x31"]
    s03_rows: dict[str, int] = {}
    for cid in COUNTED:
        pairs = {
            t: (pair_class(rows[(cid, t)]), rows[(cid, t)]["classification"])
            for t in ("DWSIM", "IDAES")
        }
        row, _ = case_row(pairs)
        s03_rows[cid] = row
        claim(
            row == s03_x["cases"][cid]["row"],
            f"C9 {cid}: the three-tool table gives S03's committed row {row}",
        )
    claim(
        clause(s03_rows) == s03_x["clause"],
        f"C9 on S03's two tools the clause is S03's committed '{s03_x['clause']}'",
    )
    for cid, kind in INVERSE.items():
        pairs = {
            t: (pair_class(rows[(cid, t)]), rows[(cid, t)]["classification"])
            for t in ("DWSIM", "IDAES")
        }
        claim(
            case_row(pairs)[0] == s03_x["inverse_kinds"][kind]["row"],
            f"C9 {kind} ({cid}): S03's committed row",
        )

    # C10: the pre-registered outcomes (S09 §8.3), per counted case and BioSTEAM class, from S03's
    # committed rows.
    pre: dict[str, dict[str, Any]] = {}
    for cid in COUNTED + tuple(INVERSE):
        pre[cid] = {
            "S03": {
                t: [pair_class(rows[(cid, t)]), rows[(cid, t)]["classification"]]
                for t in ("DWSIM", "IDAES")
            }
        }
        for cls in BIOSTEAM_CLASSES:
            pairs = {
                t: (pair_class(rows[(cid, t)]), rows[(cid, t)]["classification"])
                for t in ("DWSIM", "IDAES")
            }
            pairs["BioSTEAM"] = biosteam_pair(cls)
            row, text = case_row(pairs)
            claim(row != 0, f"C10 {cid} with BioSTEAM {cls} matches a row")
            pre[cid][cls] = [row, text]
    best = {cid: pre[cid]["AGREE"][0] for cid in COUNTED}
    claim(
        clause(best) == "met where available, 3 of 4 with two references",
        "C10 every counted BioSTEAM pair AGREE gives 'met where available, 3 of 4'; 'two "
        "references' is unreachable",
    )
    rc4_absent = dict(best, RC4=pre["RC4"]["absent"][0])
    claim(clause(rc4_absent) == "not met", "C10 BioSTEAM absent on RC4 leaves the clause not met")

    # C11: no S03 record or classification is touched: S03's comparison is read, not rewritten (pins
    # above).
    claim(
        comparison["schema"] == "s03-reference-comparison-v1",
        "C11 S03's comparison schema is unchanged",
    )

    document: dict[str, Any] = {
        "generator": "docs/derivations/scripts/s09_reference.py",
        "spec": "docs/derivations/S09-spec.md",
        "note": (
            "Inputs only. No tool value, no value of ours and no twin value enters a BioSTEAM run "
            "through this "
            "file; the readback expectations are SYN-001's closed forms (S09 §4.3)."
        ),
        "s03_pins": PINS,
        "tool": "BioSTEAM",
        "pairs": list(COMPARED) + ["PC-P", "PC-LB"],
        "not_applicable": {
            "PC-L": "DWSIM's mapping input (S03 §3.3)",
            "PC-LI": "IDAES's mapping input (S03 §18.3)",
        },
        "ours_aliases": {"PC-LB": "RC1"},
        "controls": {
            "PC-P": {
                "inputs": "s03_cases.json cases.PC-P",
                "expected": "DISAGREE",
                "tool_model_distance": (
                    "not_applicable: BioSTEAM's model at 1.5e5 Pa also lacks v (P - P_r) in "
                    "h^L, which S03's PC-P tool model keeps (S09 §7)"
                ),
            },
            "PC-LB": {
                "inputs": "s03_cases.json cases.RC1",
                "role": "positive_control",
                "expected": "DISAGREE",
                "tool_variant": "Hvap_J_per_mol_PC-LB in place of L_i",
                "Hvap_J_per_mol_PC-LB": [hvap_pclb[c] for c in "ABC"],
                "tool_model": "s03_reference.json controls.PC-LI.tool_model (claim C4)",
            },
        },
        "tool_settings": {
            "BioSTEAM": {
                "environment": {
                    "python": "3.13.5",
                    "biosteam": "2.54.0",
                    "thermosteam": "0.54.2",
                    "thermo": "0.6.1",
                    "chemicals": "1.5.2",
                    "flexsolve": "0.5.10",
                    "numba": "0.68.0",
                    "numpy": "2.5.4",
                    "scipy": "1.18.1",
                    "lock": "spikes/references/biosteam-requirements.lock",
                },
                "mapping": {
                    "constants": (
                        "spikes/references/t06_fixtures.py (T_BOIL, L_VAP, CP, V_LIQ, MW, P_REF, "
                        "R_GAS)"
                    ),
                    "chemical": (
                        "thermosteam.Chemical.blank(ID, phase_ref='l', MW=1000*MW, Tb=T_BOIL[ID])"
                    ),
                    "Psat": (
                        "Psat.add_method(f=P_REF*exp((L/R_GAS)*(1/T_b - 1/T)), Tmin=200.0, "
                        "Tmax=600.0)"
                    ),
                    "Hvap": (
                        "Hvap.add_method(f=L (constant), Tmin=200.0, Tmax=600.0); PC-LB: "
                        "Hvap_J_per_mol_PC-LB"
                    ),
                    "Cn": "Cn.l.add_method(CP); Cn.g.add_method(CP)",
                    "V": "V.l.add_method(V_LIQ)",
                    "finish": "reset_free_energies(); Chemicals([...]).compile(skip_checks=True)",
                    "thermo": (
                        "IdealThermo(chemicals, mixture=IdealMixture.from_chemicals(chemicals), "
                        "skip_checks=True)"
                    ),
                    "datum": (
                        "the tool's default (Chemical.T_ref = 298.15 K); no subclass; offset 185 "
                        "J/mol (C4)"
                    ),
                    "specifications_by_weight": False,
                },
                "readback": {
                    "temperatures_K": list(READBACK_T),
                    "Psat_Pa": psat,
                    "Psat_relative": "1e-14",
                    "latent_relative": "1e-12",
                    "cp_J_per_mol": "1e-9",
                    "datum_offset_J_per_mol": "185",
                    "datum_offset_abs_J_per_mol": "1e-9",
                    "liquid_pressure_dependence": (
                        "H(T, 1.5 P_r) - H(T, P_r) == 0 exactly for a liquid stream"
                    ),
                    "methods": "Psat and Hvap: exactly {'USER_METHOD'}",
                    "thermo_classes": {
                        "Gamma": "IdealActivityCoefficients",
                        "Phi": "IdealFugacityCoefficients",
                        "PCF": "MockPoyntingCorrectionFactors",
                        "mixture": "IdealMixture",
                        "include_excess_energies": False,
                    },
                },
                "common": {
                    "early_termination": False,
                    "tolerance": "1e-10",
                    "relative_tolerance": "1e-10",
                    "maxiter": 500,
                    "max_attempts": 1,
                    "use_cache": True,
                    "phases": ["g", "l"],
                    "other_attributes": "the tool's defaults, recorded per run",
                },
                "rungs": [list(r) for r in RUNGS],
                "rungs_source": "MultiStageEquilibrium.default_algorithms and default_methods "
                "(biosteam/units/stage.py:2185-2200), one algorithm per rung, in that order",
                "solve_path": [
                    "P1 build: MultiStageEquilibrium(ins=inlets, outs=['vapor', 'liquid'] (+ "
                    "['distillate'] for a "
                    "total condenser), N_stages=N, feed_stages=[s-1], P=[P]*N, phases=('g','l'), "
                    "stage_specifications={...}, [bottom_side_draws={0: 1/(1+RR)}], maxiter=500, "
                    "max_attempts=1, "
                    "use_cache=True); then algorithms=(rung,), methods=(method,), "
                    "early_termination=False, "
                    "tolerance=relative_tolerance=1e-10",
                    "P2 simulate()  (pass 1)",
                    "P3 re-store every registered native specification through the stage's "
                    "attribute setter "
                    "(Reflux r: stage.B = 1/r, or inf for r = 0, or 0 for r = inf; Boilup b: "
                    "stage.B = b; Duty q: "
                    "stage.Q = 3.6 q; Flow f: stage.F = f; Temperature t: stage.T = t); never "
                    "specify_variables",
                    "P4 simulate()  (pass 2); the record is pass 2",
                ],
                "native_specifications": {
                    "reflux_ratio_partial": "stage 0: ('Reflux', RR)",
                    "reflux_ratio_total": (
                        "stage 0: ('Reflux', inf) with bottom_side_draws={0: 1/(1+RR)}"
                    ),
                    "boilup_ratio": "stage N-1: ('Boilup', BR)",
                    "bottoms_rate": "stage N-1: ('Flow', B / sum of the registered inlet flows)",
                    "duty": "the end stage: ('Duty', 3.6 Q) in kJ/h",
                    "temperature_end_stage": (
                        "the end stage that carries the slot: ('Temperature', T)"
                    ),
                    "not_native": [
                        "distillate_rate",
                        "purity",
                        "recovery",
                        "temperature on a stage other than the end stage that carries the slot",
                    ],
                },
                "outer_loop": {
                    "level": "L2(c)",
                    "adjusted": {
                        "condenser": ["Reflux", "stage 0"],
                        "reboiler": ["Boilup", "stage N-1"],
                    },
                    "residual": (
                        "g(x) = (s(x) - s*)/|s*| for a relative kind, s(x) - s* for an absolute "
                        "kind, with "
                        "s computed from the tool's record by S03 §5.1 row 9 and §17.4"
                    ),
                    "starts": ["1", "2"],
                    "expansion": (
                        "if g(1) g(2) > 0: x = 4, 8, 16, 32 when |g(2)| <= |g(1)|, else 0.5, "
                        "0.25, 0.125, "
                        "0.0625; the first sign change against the previous point gives the bracket"
                    ),
                    "solver": (
                        "flexsolve.IQ_interpolation(g, a, b, g(a), g(b), None, 0.0, ytol, (), 50, "
                        "False, "
                        "True, True)"
                    ),
                    "ytol": ytol,
                    "evaluation": (
                        "every g(x) is a fresh build and the full solve path P1-P4 at the rung's "
                        "settings, "
                        "and its state must pass rule 2 (BioSTEAM) and rule 2c's pressure and "
                        "read-back "
                        "checks, or the attempt fails"
                    ),
                    "record": (
                        "one final fresh evaluation at the returned x; |g| <= ytol or the attempt "
                        "fails"
                    ),
                },
                "floor_rerun": {
                    "tolerance": "1e-9",
                    "relative_tolerance": "1e-9",
                    "ytol_factor": "10",
                },
                "rule2": {
                    "stage_component_mol_per_s": "3.1e-8",
                    "equilibrium": "1e-8",
                    "overall_component_mol_per_s": "3.1e-8",
                    "overall_energy_W": "1e-3",
                    "iteration_cap": "no pass's iteration counter reaches maxiter",
                    "exception": "no pass raised",
                },
                "rule2c_added": {
                    "specification_readback": "exact",
                    "total_condenser_vapour_mol_per_s": "3.1e-8",
                    "property_readback": "readback block",
                },
                "units": {"flow": "kmol/h = 3.6 mol/s", "duty": "kJ/h = 3.6 W"},
            }
        },
        "x31_three_tool": {
            "rows": {
                "1": "any pair ours: not met (a column finding)",
                "2": "any genuine DISAGREE: not met (a disagreement finding)",
                "3": "any pair access: blocked",
                "4": "any pair unusable: not met",
                "5": "two or more pairs AGREE, the others absent: two (or three) references",
                "6": "exactly one pair AGREE, the others absent: one reference",
                "7": "every pair absent: no reference, not met",
            },
            "clause": {
                "met with two references": "every counted case is row 5",
                "met where available": (
                    "every counted case is row 5 or row 6 (report the count of row 5)"
                ),
                "not met": "any counted case is row 1, 2, 4 or 7",
                "blocked": "no case is not met and some case is row 3",
            },
            "counted": list(COUNTED),
            "pre_registered": pre,
        },
        "blindness": {
            "forbidden_strings": [
                "s03_reference",
                "s02_reference",
                "s06_reference",
                "openflowsheet",
                "ours-",
                "comparison",
                "twin",
                "s09_spike",
                "compare_ours",
                "1.2341901",
            ],
            "exempt_modules_sha256": {
                "spikes/references/t06_fixtures.py": (
                    "c6320cc81ea4bf08c36f7d7b5aca19180c2109fd66e4e23c84476d35286ba61f"
                ),
            },
            "exempt_strings": ["twin", "comparison"],
            "input_files": [
                "docs/derivations/scripts/s03_cases.json",
                "docs/derivations/scripts/s09_cases.json",
            ],
        },
    }
    document["claim_count"] = len(claims)
    document["claims"] = list(claims)
    return document


def dumps(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument(
        "--check", action="store_true", help="re-derive and byte-compare s09_cases.json"
    )
    parser.add_argument("--emit", action="store_true", help="write s09_cases.json")
    args = parser.parse_args(argv)
    if not (args.check or args.emit):
        parser.error("choose --check and/or --emit")
    try:
        data = dumps(build())
    except ClaimError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    if args.emit:
        OUT.write_bytes(data)
        print(
            f"wrote {OUT.relative_to(ROOT)}: {len(claims)} claims, sha256 "
            f"{hashlib.sha256(data).hexdigest()}"
        )
    if args.check:
        if not OUT.exists() or OUT.read_bytes() != data:
            print(f"FAIL: {OUT.relative_to(ROOT)} differs from a fresh derivation", file=sys.stderr)
            return 1
        print(
            f"PASS: {len(claims)} claims; {OUT.relative_to(ROOT)} byte-identical "
            f"(sha256 {hashlib.sha256(data).hexdigest()})"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
