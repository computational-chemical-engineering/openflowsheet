"""S03 reference generator: twin values, case inputs and control discriminations for the two
independent column references (``docs/derivations/S03-spec.md``).

Evaluated with mpmath at 50 significant digits. It imports nothing from ``openflowsheet``. It reuses
the S02 and S06 generators (``s02_reference.py``, ``s06_reference.py``, both independent of
``src/``): SYN-001's closed forms, the generators' column formulation (8 unknowns per equilibrium
stage, quotient equilibrium and specification rows), S02 §6's initializer, S02 §18.2's bubble-point
endpoint and the straight specification path in 16 equal steps. What it adds (spec §3-§6):

* the reference cases RC1-RC4 (S02's M1-M4 with every stage and inlet pressure at P_r, where both
  tools' K = Psat/P equals SYN-001's) and RC5 (S06's J1 on RC1), and the ten perturbed cases;
* the registered comparison quantities and their tolerances ``a_k + 1e-6 |v|`` (T06 §9.4);
* the positive controls: PC-P (RC1's column at 1.5e5 Pa: SYN-001 against SYN-001 without the
  Poynting factor, both tools' K there) and PC-L (RC1 with DWSIM's latent heat unmapped,
  h^V - h^L smaller by P_r v_i), each solved in the tool's model by Newton from the SYN-001 root;
* the discrimination claims: every perturbation moves some registered quantity by at least 100
  tolerances, each positive control by at least 10, a feed one stage up (E1) by at least 100.

Amendment 1 (spec §17) adds, without changing any earlier value:

* RC6 (S06's J8 at P_r: RC2's column, RR 1.5, reboiler recovery of C 0.99) and RC7 (S06's J3 at
  P_r: RC1's column, RR 2, the reboiler slot taken by stage 6's temperature, 368 K);
* the inverse-partner claim: RC5, RC6 and RC7 each move their ratio-partner base case (RC1, RC2,
  RC1) by at least 100 tolerances, so a harness that dropped the inverse specification and kept
  the base case's would disagree;
* the specification-accuracy claim behind rule 2d's thresholds: for every compared case and every
  specified end, re-solving with that specification moved by exactly its threshold (1e-8 relative
  for a ratio, rate or duty; 1e-8 absolute on a purity; 1e-9 absolute on a recovery; 1e-9 relative
  on a temperature) moves every registered quantity by at most 0.05 tolerance;
* the definition-mismatch claim behind rule 2c's 1e-4 threshold for the inverse kinds: each
  registered wrong reading of a purity, recovery or temperature specification differs from the
  registered value by more than 1e-3 relative (ten times the threshold);
* DWSIM's amended column-solver ladder and the specification definitions, as new keys of
  ``tool_settings`` (the superseded key is kept so that the earlier records' settings still read).

Amendment 2 (spec §18) adds, without changing any earlier value:

* PC-LI, IDAES's second positive control: RC1 with IDAES's h_form,ig,i = L_i + P_r v_i (DWSIM's
  mapped value entered in IDAES), so h^V - h^L is larger by P_r v_i; solved in that tool model by
  Newton from the SYN-001 root, like PC-L, whose mirror it is. Our side is RC1's record;
* the claim that PC-LI's registered IDAES input equals L_i + P_r v_i exactly, and that its tool
  model's vapour enthalpy exceeds SYN-001's by exactly P_r v_i;
* IDAES's path ladder (P0, P1, P2) and PC-LI's input, as one new top-level key of ``tool_settings``
  (``IDAES_amendment_2``); ``tool_settings.IDAES`` is unchanged.

It writes two files. ``s03_cases.json`` holds inputs only (cases, quantity names, tool
settings): the tool scripts read it and nothing else of this project (spec §8, blindness).
``s03_reference.json`` holds the twin values and the claims; it records the SHA-256 of the cases
file.

    python docs/derivations/scripts/s03_reference.py --check
    python docs/derivations/scripts/s03_reference.py --emit

``--check`` re-derives every claim (worker processes; a few minutes), refuses to continue when one
fails, and byte-compares both committed files. ``--emit`` runs the same claims and writes both files
only when all of them hold.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from multiprocessing import Pool
from pathlib import Path
from typing import Any

from mpmath import mp, mpf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s02_reference as s2  # noqa: E402  (SYN-001, the S02 column formulation)
import s06_reference as s6  # noqa: E402  (inverse slots, S02 §18.2's endpoint and path)

HERE = Path(__file__).resolve().parent
REF_OUT = HERE / "s03_reference.json"
CASES_OUT = HERE / "s03_cases.json"
DIGITS = 25  # emitted digits (S02's)
WIDE = 45  # digits passed between processes for post-processing
NC = s2.NC
NAMES = ("A", "B", "C")
P_R = s2.P_REF
P_PC = mpf(150000)  # PC-P: T06's PC-2 pressure
# spec §5: tolerance a_k + REL |v| (T06 §9.4, T02 §6.4's allowances)
ALLOWANCE = {"flow": mpf("3.1e-7"), "T": mpf("1e-5"), "duty": mpf("1e-2")}
REL = mpf("1e-6")
RESOLVE_MIN = mpf(100)  # spec §6: a perturbation moves some quantity by >= 100 tolerances
CONTROL_MIN = mpf(10)  # spec §5.3: a positive control misses by >= 10 tolerances
STAGE_MIN = mpf(100)  # spec §5.3: E1 (feed one stage up) moves some quantity by >= 100 tolerances
MARGIN_MIN = mpf("0.02")  # S01: a declared single-phase inlet is admissible with this margin
SIGMA_REGULAR = mpf("1e-4")
NEWTON_FROM_SYN = 2  # the tool-model root is found by Newton from the SYN-001 root
# Amendment 1 (spec §17.4): rule 2d's specification threshold, its claimed effect, rule 2c's margin
# rule 2d's specification threshold per kind: (basis, value). Ratio, rate and duty: 1e-8 relative
# (spec §6). Purity: 1e-8 absolute on the fraction (spec §6). Recovery and temperature: 1e-9, set by
# the response claim below (measured 0.30 and 0.23 tolerance at 1e-8; spec §17.4).
SPEC_ACCURACY: dict[str, tuple[str, Any]] = {
    "purity": ("absolute", mpf("1e-8")),
    "recovery": ("absolute", mpf("1e-9")),
    "temperature": ("relative", mpf("1e-9")),
}
SPEC_ACCURACY_DIRECT = ("relative", mpf("1e-8"))
SPEC_RESPONSE_MAX = mpf("0.05")  # a threshold-sized specification error moves <= 0.05 tolerance
SEMANTICS_THRESHOLD = mpf("1e-4")  # rule 2c, relative
SEMANTICS_MARGIN = 10  # each registered wrong reading misses by > 10 x rule 2c's threshold
FRACTION_KINDS = ("purity", "recovery")

CLAIMS: list[str] = []


def claim(condition: bool, text: str) -> None:
    if not condition:
        raise SystemExit(f"claim failed: {text}")
    CLAIMS.append(text)


def s(x: Any) -> str:
    return s2.s(x)


def wide(x: Any) -> str:
    return mp.nstr(mpf(x), WIDE, min_fixed=-mp.inf, max_fixed=mp.inf) if x != 0 else "0"


# -- registered cases (spec §3) -------------------------------------------------------------------
def uniform(base: str, pressure: Any) -> dict[str, Any]:
    """S02's case `base` with every stage pressure and every inlet pressure set to `pressure`."""
    case = copy.deepcopy(s2.CASES[base])
    case["P"] = [mpf(pressure)] * case["N"]
    for f in case["inlets"]:
        f["P"] = mpf(pressure)
    return case


# The bases are registered in S02's case table so that S06's `build_case` can copy them; this runs
# at import, in every worker process.
for _name, _base in (("RC1", "M1"), ("RC2", "M2"), ("RC3", "M3"), ("RC4", "M4")):
    s2.CASES[_name] = uniform(_base, P_R)
s2.CASES["PC-P"] = uniform("M1", P_PC)

BASE_SPEC: dict[str, dict[str, tuple[str, Any, str]]] = {
    "RC1": {"condenser": ("reflux_ratio", None, "2"), "reboiler": ("boilup_ratio", None, "1.5")},
    "RC2": {"condenser": ("reflux_ratio", None, "1.5"), "reboiler": ("bottoms_rate", None, "0.55")},
    "RC3": {"reboiler": ("duty", None, "30000")},
    "RC4": {"condenser": ("distillate_rate", None, "0.5")},
}
FEED_PERTURBED = ("0.28", "0.4", "0.32")
# name: (base column, end specifications, feed override or None, feed stage override or None)
CASES: dict[str, tuple[str, dict[str, tuple[str, Any, str]], Any, Any]] = {
    "RC1": ("RC1", BASE_SPEC["RC1"], None, None),
    "RC2": ("RC2", BASE_SPEC["RC2"], None, None),
    "RC3": ("RC3", BASE_SPEC["RC3"], None, None),
    "RC4": ("RC4", BASE_SPEC["RC4"], None, None),
    "RC5": (
        "RC1",
        {"condenser": ("purity", 0, "0.85"), "reboiler": ("boilup_ratio", None, "1.5")},
        None,
        None,
    ),
    # Amendment 1 (spec §17.1): S06's J8 and J3 at P_r, each with its ratio partner
    "RC6": (
        "RC2",
        {"condenser": ("reflux_ratio", None, "1.5"), "reboiler": ("recovery", 2, "0.99")},
        None,
        None,
    ),
    "RC7": (
        "RC1",
        {"condenser": ("reflux_ratio", None, "2"), "reboiler": ("temperature", 6, "368")},
        None,
        None,
    ),
}
# Amendment 1: the case whose specifications an inverse case shares except for its inverse end
INVERSE_PARTNER = {"RC5": "RC1", "RC6": "RC2", "RC7": "RC1"}
PERTURBED: dict[str, tuple[str, dict[str, tuple[str, Any, str]], Any, Any]] = {
    "RC1-RR": (
        "RC1",
        {"condenser": ("reflux_ratio", None, "2.04"), "reboiler": ("boilup_ratio", None, "1.5")},
        None,
        None,
    ),
    "RC1-BR": (
        "RC1",
        {"condenser": ("reflux_ratio", None, "2"), "reboiler": ("boilup_ratio", None, "1.53")},
        None,
        None,
    ),
    "RC1-z": ("RC1", BASE_SPEC["RC1"], FEED_PERTURBED, None),
    "RC2-RR": (
        "RC2",
        {"condenser": ("reflux_ratio", None, "1.53"), "reboiler": ("bottoms_rate", None, "0.55")},
        None,
        None,
    ),
    "RC2-B": (
        "RC2",
        {"condenser": ("reflux_ratio", None, "1.5"), "reboiler": ("bottoms_rate", None, "0.561")},
        None,
        None,
    ),
    "RC2-z": ("RC2", BASE_SPEC["RC2"], FEED_PERTURBED, None),
    "RC3-Q": ("RC3", {"reboiler": ("duty", None, "30600")}, None, None),
    "RC3-z": ("RC3", BASE_SPEC["RC3"], FEED_PERTURBED, None),
    "RC4-D": ("RC4", {"condenser": ("distillate_rate", None, "0.51")}, None, None),
    "RC4-z": ("RC4", BASE_SPEC["RC4"], FEED_PERTURBED, None),
}
PERTURBED_BASE = {name: name.split("-")[0] for name in PERTURBED}
CONTROLS: dict[str, tuple[str, dict[str, tuple[str, Any, str]], Any, Any]] = {
    "PC-P": ("PC-P", BASE_SPEC["RC1"], None, None),
    "PC-L": ("RC1", BASE_SPEC["RC1"], None, None),
    # Amendment 2 (spec §18.3): IDAES's second control, PC-L's mirror on RC1
    "PC-LI": ("RC1", BASE_SPEC["RC1"], None, None),
}
SENSITIVITY: dict[str, tuple[str, dict[str, tuple[str, Any, str]], Any, Any]] = {
    "E1": ("RC1", BASE_SPEC["RC1"], None, 3),
}


def build(name: str, entry: tuple[str, dict[str, tuple[str, Any, str]], Any, Any]) -> dict:
    base, spec, feed, stage = entry
    case = s6.build_case(base, spec, name)
    if feed is not None:
        case["inlets"][0]["n"] = [mpf(v) for v in feed]
    if stage is not None:
        case["inlets"][0]["stage"] = stage
    return case


# -- the tools' models (spec §5.3) -----------------------------------------------------------------
def ln_k_without_poynting(t: Any, p: Any, i: int) -> Any:
    """Both tools' K = Psat/P (reference-environments.md §5.0): SYN-001's without the factor."""
    return mp.log(s2.P_REF / p) + (s2.L_VAP[i] / s2.R) * (1 / s2.T_BOIL[i] - 1 / t)


def h_vap_unmapped(t: Any, i: int) -> Any:
    """DWSIM with Delta H_vap,i = L_i: h^V - h^L = L_i - P v_i, i.e. SYN-001's less P_r v_i."""
    return s2.C_P * (t - s2.T_REF) + s2.L_VAP[i] - s2.P_REF * s2.V_MOL[i]


def h_vap_idaes_overmapped(t: Any, i: int) -> Any:
    """IDAES with h_form,ig,i = L_i + P_r v_i (Amendment 2's PC-LI): IDAES's vapour enthalpy is
    c_p (T - T_r) + h_form,ig (idaes_representability.py), so h^V is SYN-001's plus P_r v_i."""
    return s2.C_P * (t - s2.T_REF) + s2.L_VAP[i] + s2.P_REF * s2.V_MOL[i]


PC_LI_H_FORM_IG = ["25010", "30010", "35010"]  # spec §18.3: L_i + P_r v_i, J/mol (claimed below)

TOOL_MODEL: dict[str, tuple[str, Callable[..., Any]]] = {
    "PC-P": ("ln_k", ln_k_without_poynting),
    "PC-L": ("h_vap", h_vap_unmapped),
    "PC-LI": ("h_vap", h_vap_idaes_overmapped),
}


@contextmanager
def patched(attribute: str, function: Callable[..., Any]) -> Iterator[None]:
    original = getattr(s2, attribute)
    setattr(s2, attribute, function)
    try:
        yield
    finally:
        setattr(s2, attribute, original)


# -- registered quantities (spec §4) ---------------------------------------------------------------
def quantities(case: dict[str, Any], st: dict[str, Any]) -> list[tuple[str, str, Any]]:
    """(name, kind, value) in registered order. A duty that is an input is not compared."""
    n_st, out = case["N"], []
    total = s2.is_total(case)
    for j in range(1, n_st + 1):
        out.append((f"T[{j}]", "T", st["Tc"] if (j == 1 and total) else st["T"][j]))
    for j in s2.eq_stages(case):
        out.append((f"L[{j}]", "flow", sum(st["l"][j])))
        out.append((f"V[{j}]", "flow", sum(st["v"][j])))
    if total:
        out.append(("reflux", "flow", st["phi"] * sum(st["v"][2])))
    top = s6.top_flows(case, st)
    for i in range(NC):
        out.append((f"top[{NAMES[i]}]", "flow", top[i]))
    for i in range(NC):
        out.append((f"bottom[{NAMES[i]}]", "flow", st["l"][n_st][i]))
    spec, inverse = case["spec"], case["inverse"]
    if case["condenser"] != "none" and (spec["condenser"][0] != "duty" or 1 in inverse):
        out.append(("Q_condenser", "duty", st["Q"][1]))
    if case["reboiler"] != "none" and (spec["reboiler"][0] != "duty" or n_st in inverse):
        out.append(("Q_reboiler", "duty", st["Q"][n_st]))
    return out


def tolerance(kind: str, value: Any) -> Any:
    return ALLOWANCE[kind] + REL * abs(value)


def admissible_inlets(case: dict[str, Any]) -> None:
    for f in case["inlets"]:
        if f["phase"] == "LIQUID":
            margin = s2.bubble_margin(f["n"], f["T"], f["P"])
        else:
            margin = s2.dew_margin(f["n"], f["T"], f["P"])
        claim(
            margin >= MARGIN_MIN,
            f"{case['name']}: inlet {f['port']} is an admissible {f['phase']} with margin >= 0.02",
        )


# -- jobs (worker processes) -----------------------------------------------------------------------
def solve_syn(case: dict[str, Any]) -> dict[str, Any]:
    """S06's solve: S02 §18.2's endpoint, the straight path in 16 steps, every S02/S06 check."""
    sol = s6.solve(case)
    return {"x": sol["x"], "st": sol["st"], "out": sol["out"]}


def solve_tool_model(case: dict[str, Any], x_syn: Sequence[Any], key: str) -> dict[str, Any]:
    attribute, function = TOOL_MODEL[key]
    two = ["TWO_PHASE"] * case["N"]
    direct = s2.target_slots(case)
    with patched(attribute, function):
        x = s2.newton(lambda y: s6.residual(case, y, direct, case["inverse"], two), x_syn)
        st = s2.unpack(case, x)
        s2.check_state(f"{key} tool model", case, st, two)
        s2.closures(f"{key} tool model", case, st)
        smin = s6.sigma_min(case, x, direct, case["inverse"])
        claim(smin > SIGMA_REGULAR, f"{key}: the tool-model root is regular, sigma_min > 1e-4")
    return {"x": x, "st": st, "sigma_min": smin}


def record(case: dict[str, Any], st: dict[str, Any]) -> list[list[str]]:
    return [[name, kind, wide(value)] for name, kind, value in quantities(case, st)]


# -- Amendment 1 (spec §17.4): what rules 2c and 2d's specification thresholds rest on -----------
def spec_response(case: dict[str, Any], x_syn: Sequence[Any], st_syn: dict) -> dict[str, Any]:
    """Each specified end's specification moved by exactly rule 2d's threshold, re-solved by Newton
    from the twin root; the largest move of a registered quantity, in tolerances at the twin."""
    n_st, two = case["N"], ["TWO_PHASE"] * case["N"]
    base = {name: (kind, value) for name, kind, value in quantities(case, st_syn)}
    out: dict[str, Any] = {}
    for end, j in (("condenser", 1), ("reboiler", n_st)):
        if case[end] == "none":
            continue
        direct, inverse = dict(s2.target_slots(case)), dict(case["inverse"])
        if j in inverse:
            e, kind, attr, value = inverse[j]
            basis, threshold = SPEC_ACCURACY[kind]
            delta = threshold if basis == "absolute" else threshold * abs(value)
            inverse[j] = (e, kind, attr, value + delta)
        else:
            kind, (basis, threshold) = case["spec"][end][0], SPEC_ACCURACY_DIRECT
            slot, value = direct[j]
            direct[j] = (slot, value + threshold * abs(value))
        x = s2.newton(lambda y, d=direct, i=inverse: s6.residual(case, y, d, i, two), x_syn)
        moved = {name: v for name, _, v in quantities(case, s2.unpack(case, x))}
        ratios = {n: abs(moved[n] - v) / tolerance(k, v) for n, (k, v) in base.items()}
        worst = max(ratios, key=lambda n: ratios[n])
        claim(
            ratios[worst] <= SPEC_RESPONSE_MAX,
            f"{case['name']}: the {end} {kind} specification moved by {s(threshold)} ({basis}) "
            "moves every registered quantity by <= 0.05 tolerance",
        )
        out[end] = {
            "kind": kind,
            "basis": basis,
            "threshold": s(threshold),
            "max_ratio": mp.nstr(ratios[worst], 6),
            "argmax": worst,
        }
    return out


def definition_alternatives(case: dict[str, Any], st: dict[str, Any]) -> dict[str, Any]:
    """Registered wrong readings of each inverse specification, at the twin root; each must miss the
    registered value by more than 10 x rule 2c's 1e-4 relative threshold."""
    feed, total = s2.feed_total(case)
    out: dict[str, Any] = {}
    for j, (end, kind, attr, value) in case["inverse"].items():
        flows = s6.product(case, st, end)
        alternatives: dict[str, Any] = {}
        if kind == "purity":
            liquid = st["l"][j]
            alternatives["liquid_of_the_end_stage"] = liquid[attr] / sum(liquid)
            alternatives["recovery_in_the_product"] = flows[attr] / feed[attr]
        elif kind == "recovery":
            other = s6.product(case, st, "condenser" if end == "reboiler" else "reboiler")
            alternatives["recovery_in_the_other_product"] = other[attr] / feed[attr]
            alternatives["purity_in_the_product"] = flows[attr] / sum(flows)
            alternatives["fraction_of_the_total_feed"] = flows[attr] / total
        else:
            for name, stage in (("stage_above", attr - 1), ("stage_below", attr + 1)):
                alternatives[name] = s6.quantity(case, st, end, kind, stage)
        entry: dict[str, Any] = {"kind": kind, "end": end, "registered": s(value)}
        for name, alt in alternatives.items():
            miss = abs(alt - value) / abs(value)
            claim(
                miss > SEMANTICS_MARGIN * SEMANTICS_THRESHOLD,
                f"{case['name']}: reading the {kind} specification as {name} misses the registered "
                "value by > 1e-3 relative (10 x rule 2c's threshold)",
            )
            entry[name] = {"value": s(alt), "relative_miss": mp.nstr(miss, 6)}
        out[str(j)] = entry
    return out


def run_job(key: str) -> tuple[str, dict[str, Any], list[str]]:
    CLAIMS.clear()
    s2.CLAIMS.clear()
    s6.CLAIMS.clear()
    table = {**CASES, **PERTURBED, **CONTROLS, **SENSITIVITY}
    case = build(key, table[key])
    level = case["P"][0]
    claim(
        all(p == level for p in case["P"]) and all(f["P"] == level for f in case["inlets"]),
        f"{key}: every stage and inlet pressure equals {s(level)} Pa",
    )
    admissible_inlets(case)
    out: dict[str, Any] = {}
    if key in ("PC-L", "PC-LI"):
        syn = solve_syn(case)  # RC1 itself; its claims are RC1's job's, so they are dropped here
        s2.CLAIMS.clear()
        s6.CLAIMS.clear()
        CLAIMS.clear()
    else:
        syn = solve_syn(case)
    if key in CASES or key in PERTURBED:
        # spec §5 item 2: at P = P_r both tools' K = Psat/P is SYN-001's K exactly, so each row of
        # the tools' model equals SYN-001's at the twin root (PC-P: the converse at 1.5e5 Pa).
        two = ["TWO_PHASE"] * case["N"]
        direct = s2.target_slots(case)
        rows_syn = s6.residual(case, syn["x"], direct, case["inverse"], two)
        with patched("ln_k", ln_k_without_poynting):
            rows_tool = s6.residual(case, syn["x"], direct, case["inverse"], two)
        claim(
            rows_syn == rows_tool,
            f"{key}: at P_r the tools' K (no Poynting factor) gives SYN-001's rows exactly",
        )
    out["syn"] = record(case, syn["st"])
    out["sigma_min"] = syn["out"]["sigma_min"]
    out["spec_values"] = syn["out"]["spec_values"]
    out["inverse_values"] = syn["out"]["inverse_values"]
    if key in CONTROLS:
        tool = solve_tool_model(case, syn["x"], key)
        out["tool_model"] = record(case, tool["st"])
        out["tool_model_sigma_min"] = mp.nstr(tool["sigma_min"], 6)
    if key == "PC-LI":
        # Amendment 2 (spec §18.3): the registered IDAES input is L_i + P_r v_i exactly, and the
        # tool model's h^V exceeds SYN-001's by exactly P_r v_i at every stage temperature of the
        # tool-model root (so h^V - h^L is larger by P_r v_i; h^L is unchanged)
        claim(
            all(
                abs(mpf(PC_LI_H_FORM_IG[i]) - (s2.L_VAP[i] + s2.P_REF * s2.V_MOL[i])) < mpf("1e-40")
                for i in range(NC)
            ),
            "PC-LI: IDAES's registered h_form,ig equals L_i + P_r v_i = 25010, 30010, 35010 J/mol",
        )
        gap = max(
            abs(h_vap_idaes_overmapped(t, i) - s2.h_vap(t, i) - s2.P_REF * s2.V_MOL[i])
            for t in tool["st"]["T"].values()
            for i in range(NC)
        )
        claim(
            gap < mpf("1e-40"),
            "PC-LI: the tool model's h^V exceeds SYN-001's by P_r v_i = 10 J/mol at every stage",
        )
    # Amendment 1: appended after every earlier claim of the job, so those keep their order
    if key in CASES or key in PERTURBED:
        out["spec_response"] = spec_response(case, syn["x"], syn["st"])
    if case["inverse"] and (key in CASES or key in PERTURBED):
        out["definition_alternatives"] = definition_alternatives(case, syn["st"])
    return key, out, [*s2.CLAIMS, *s6.CLAIMS, *CLAIMS]


def job(key: str) -> tuple[str, dict[str, Any], list[str]]:
    """A failed claim comes back as an error (a SystemExit in a worker would hang the pool)."""
    try:
        return run_job(key)
    except SystemExit as failure:
        return key, {"error": str(failure)}, []


# -- post-processing (parent process) --------------------------------------------------------------
def values(rows: list[list[str]]) -> dict[str, tuple[str, Any]]:
    return {name: (kind, mpf(v)) for name, kind, v in rows}


def emitted(rows: list[list[str]]) -> dict[str, dict[str, str]]:
    return {
        name: {"kind": kind, "value": s(mpf(v)), "tolerance": s(tolerance(kind, mpf(v)))}
        for name, kind, v in rows
    }


def discrimination(
    reference: dict[str, tuple[str, Any]], moved: dict[str, tuple[str, Any]], judged_at: str
) -> dict[str, Any]:
    """Ratios |moved - reference| / tol, the tolerance taken at `judged_at`'s value."""
    ratios = {}
    for name, (kind, ref_value) in reference.items():
        new_value = moved[name][1]
        at = new_value if judged_at == "moved" else ref_value
        ratios[name] = abs(new_value - ref_value) / tolerance(kind, at)
    worst = max(ratios, key=lambda n: ratios[n])
    return {
        "max_ratio": mp.nstr(ratios[worst], 6),
        "argmax": worst,
        "quantities_over_one_tolerance": sum(1 for r in ratios.values() if r > 1),
        "quantities": len(ratios),
        "_max": ratios[worst],
    }


def case_inputs(name: str, entry: tuple[str, dict[str, tuple[str, Any, str]], Any, Any]) -> dict:
    case = build(name, entry)
    inlets = [
        {
            "port": f["port"],
            "stage": f["stage"],
            "phase": f["phase"],
            "n_mol_per_s": [s(v) for v in f["n"]],
            "T_K": s(f["T"]),
            "P_Pa": s(f["P"]),
        }
        for f in case["inlets"]
    ]
    specs = {}
    for end, (kind, attr, value) in entry[1].items():
        item: dict[str, Any] = {"kind": kind, "value": value}
        if kind in FRACTION_KINDS:
            item["component"] = NAMES[attr]
        if kind == "temperature":
            item["stage"] = attr  # our numbering (S02 §1.1)
        specs[end] = item
    variant = {
        "PC-P": {"IDAES": "registered settings", "DWSIM": "registered settings"},
        "PC-L": {"IDAES": "not_applicable", "DWSIM": "dH_vap_J_per_mol_PC-L in place of dH_vap"},
        "PC-LI": {
            "IDAES": "IDAES_amendment_2.h_form_ig_J_per_mol_PC-LI in place of h_form_ig_J_per_mol",
            "DWSIM": "not_applicable",
        },
    }.get(name, {"IDAES": "registered settings", "DWSIM": "registered settings"})
    return {
        "role": "positive_control" if name in CONTROLS else "comparison",
        "tool_variant": variant,
        "stage_count": case["N"],
        "condenser": case["condenser"],
        "reboiler": case["reboiler"],
        "stage_pressures_Pa": [s(p) for p in case["P"]],
        "intermediate_duties_W": "0 on every stage that carries no end specification",
        "inlets": inlets,
        "specifications": specs,
        "quantities": [[n, k] for n, k, _ in quantities(case, _placeholder_state(case))],
    }


def _placeholder_state(case: dict[str, Any]) -> dict[str, Any]:
    """A state with unit flows and temperatures, used only to list quantity names and kinds."""
    st: dict[str, Any] = {"l": {}, "v": {}, "T": {}, "Q": {}, "phi": mpf("0.5"), "Tc": mpf(1)}
    for j in range(1, case["N"] + 1):
        st["l"][j], st["v"][j], st["T"][j], st["Q"][j] = [mpf(1)] * NC, [mpf(1)] * NC, mpf(1), 1
    return st


TOOL_SETTINGS: dict[str, Any] = {
    "SYN-001_mapping": "T06 §9.3 unchanged (ref.closed_form.dwsim_input_mapping, "
    "ref.closed_form.reference_tool_settings in t06_reference.json)",
    "IDAES": {
        "version": "idaes-pse 2.13.0, extensions 3.4.2",
        "linear_solver": "mumps",
        "tol": "1e-10",
        "constr_viol_tol": "1e-9",
        "max_iter": 500,
        "initializers": "linear_solver = mumps; IDAES's other defaults",
        "smooth_vle": {"eps_1_K": "1e-8", "eps_2_K": "1e-8"},
        "floor_rerun": {"tol": "1e-9", "constr_viol_tol": "1e-8"},
        "h_form_liq_J_per_mol": ["0", "0", "0"],
        "h_form_ig_J_per_mol": ["25000", "30000", "35000"],
        "placeholders": {"temperature_crit_K": "1000", "pressure_crit_Pa": "1e7"},
    },
    "DWSIM": {
        "version": "9.0.5 via pythonnet 3.1.0",
        "property_package": "Raoult's Law, user compounds (docs/reference-environments.md §5.0)",
        "dH_vap_J_per_mol": ["25010", "30010", "35010"],
        "dH_vap_J_per_mol_PC-L": ["25000", "30000", "35000"],
        "dH_f_ig_J_per_mol": "equal to dH_vap (T06 §9.3)",
        "liquid_density_pressure_correction": False,
        "placeholders": {
            "T_c_K": "1000",
            "P_c_Pa": "1e7",
            "omega": "0",
            "NBP_K": ["320", "360", "400"],
        },
        "flash_loop_tolerances": "1e-10 (PT and PH, external and internal), 1000 iterations",
        "column_method_order": [
            "Napthali-Sandholm",
            "Russell inside-out",
            "Wang-Henke / Burningham-Otto",
        ],
        "column_tolerance_ladder": ["1e-10", "1e-9", "1e-8", "1e-7", "1e-6"],
        "column_max_iterations": 1000,
        "floor_rerun": "the selected column tolerance times 10, everything else unchanged",
        "column_method_order_amendment_1": {
            "supersedes": "column_method_order",
            "methods": ["Napthali-Sandholm", "Wang-Henke"],
            "applies_to": "every case and control",
            "order": "levels L1 then L2; within a level, tolerances tightest first; within a "
            "tolerance, the methods in this order",
            "reason": "Russell inside-out does not exist in DWSIM 9.0.5; Burningham-Otto runs "
            "only in AbsorptionColumn, which has no condenser and no reboiler (spec §17.2)",
        },
    },
    "tool_initial_guess": "the tool's own initializer or estimator; if it needs a temperature "
    "profile: linear from 320 K (stage 1) to 400 K (stage N), from SYN-001's T_b alone",
    "specification_definitions_amendment_1": {
        "note": "spec §5.1 row 9 with §17.4; molar; our stage numbering; the condenser end's "
        "product is v_1 (partial) or d (total), the reboiler end's product is l_N",
        "reflux_ratio": "L_1/V_1 (partial condenser); sum(r)/D (total condenser)",
        "boilup_ratio": "V_N/L_N",
        "distillate_rate": "V_1 (partial condenser); D (total condenser)",
        "bottoms_rate": "L_N",
        "duty": "the end stage's duty, positive into the stage",
        "purity": "n_c/P: the component's mole fraction in the end's product",
        "recovery": "n_c/F_c: the end's product flow of c over the inlets' total flow of c",
        "temperature": "T_s of the named stage s (s = 1 with a total condenser means T_c)",
        "semantics_threshold": "1e-4 relative (rule 2c)",
        "accuracy_threshold": "rule 2d: 1e-8 relative for a ratio, rate or duty; 1e-8 absolute for "
        "purity; 1e-9 absolute for recovery; 1e-9 relative for temperature",
    },
    # Amendment 2 (spec §18.1, §18.3): a new top-level key, so tool_settings.IDAES and every
    # earlier key stay byte-identical (spec §17.8's earlier-cases-file rule)
    "IDAES_amendment_2": {
        "spec": "docs/derivations/S03-spec.md §18",
        "registered_unchanged": "tool_settings.IDAES: linear_solver, tol, constr_viol_tol, "
        "max_iter and smooth_vle for every solve that decides (the final solve and its accuracy "
        "rerun); converged iff 'Optimal Solution Found'",
        "common_start": [
            "S1 initial guesses: every tray inlet that is not a case inlet at the registered "
            "linear profile (320 K at stage 1 to 400 K at stage N; a liquid inlet at the profile "
            "temperature of the stage above, a vapour inlet at that of the stage below), 1 mol/s, "
            "the first inlet's composition, the registered pressure",
            "S2 initializers: L1/L2 TrayColumn.initialize(); L3 IDAES's unit initializers in "
            "TrayColumn.initialize's order (trays holding a case inlet, then the end units from "
            "the nearest of them, then every other tray from its nearest initialized neighbours)",
            "S3 one full model solve with IDAES's initializer solver (get_solver(), MUMPS, IDAES's "
            "other defaults); its final iterate is the start of the position's solves whatever "
            "its termination",
            "S4 S1-S3 run at IDAES's default SmoothVLE eps (eps_1 = 0.01 K, eps_2 = 5e-4 K)",
            "S5 an L2(b) equation on another stage's variables is deactivated during S2, with "
            "the native variable it replaces fixed at IDAES's own initial value, and restored "
            "before S3",
            "S6 an initializer exception is recorded and does not end the attempt",
        ],
        "warm_start_options": {
            "mu_init": "1e-9",
            "bound_push": "1e-9",
            "bound_frac": "1e-9",
            "bound_mult_init_method": "mu-based",
        },
        "path_positions": [
            {
                "id": "P0",
                "eps_schedule_K": [],
                "warm_start": False,
                "note": "B2-4 as recorded: eps_1 = eps_2 = 1e-8 K on every SmoothVLE block, then "
                "the final solve with the registered options and Ipopt's defaults otherwise",
            },
            {
                "id": "P1",
                "eps_schedule_K": [],
                "warm_start": True,
                "note": "eps 1e-8 K on every block, then the final solve with the registered "
                "options plus warm_start_options",
            },
            {
                "id": "P2",
                "eps_schedule_K": ["1e-4", "1e-6"],
                "warm_start": True,
                "note": "eps_1 = eps_2 = 1e-4 K, solve; 1e-6 K, solve; 1e-8 K, the final solve; "
                "each solve with the registered options plus warm_start_options, from the previous "
                "solve's final iterate whatever its termination",
            },
        ],
        "order": "levels L1, L2, L3 (each only if structurally expressible); within a level every "
        "position P0, P1, P2 is run before the level is judged, and every position whose final "
        "solve ends 'Optimal Solution Found' also gets its accuracy rerun; the search stops at the "
        "first level that passes",
        "selection": "the first position, in P0, P1, P2 order, of the first level that shows no "
        "path dependence and has a position passing rules 2-2d",
        "path_dependence": "rule 2d (IDAES): two positions of one level whose final solves ended "
        "'Optimal Solution Found' differ on a registered quantity by more than 0.1 tolerance",
        "accuracy_rerun": "the attempt repeated from S1 with floor_rerun's tol and constr_viol_tol "
        "in place of the registered ones in every solve after S3",
        "contingency": "if Ipopt rejects bound_mult_init_method, P1 and P2 run without it and the "
        "record says so; no other option is substituted",
        "h_form_ig_J_per_mol_PC-LI": PC_LI_H_FORM_IG,
    },
}


def build_documents() -> tuple[bytes, bytes, int]:
    CLAIMS.clear()
    keys = [*CASES, *PERTURBED, *CONTROLS, *SENSITIVITY]
    with Pool(min(16, len(keys))) as pool:
        results = pool.map(job, keys)
    errors = [f"{key}: {out['error']}" for key, out, _ in results if "error" in out]
    if errors:
        raise SystemExit("; ".join(errors))
    claims: list[str] = []
    by_key: dict[str, dict[str, Any]] = {}
    for key, out, own in results:
        claims.extend(f"[{key}] {c}" for c in own)
        by_key[key] = out

    def post(condition: bool, text: str) -> None:
        if not condition:
            raise SystemExit(f"claim failed: {text}")
        claims.append(f"[post] {text}")

    twin: dict[str, Any] = {}
    for key in [*CASES, *PERTURBED]:
        twin[key] = {
            "sigma_min": by_key[key]["sigma_min"],
            "spec_values": by_key[key]["spec_values"],
            "inverse_values": by_key[key]["inverse_values"],
            "quantities": emitted(by_key[key]["syn"]),
        }
    perturbations: dict[str, Any] = {}
    for key, base in PERTURBED_BASE.items():
        d = discrimination(values(by_key[base]["syn"]), values(by_key[key]["syn"]), "moved")
        post(
            d.pop("_max") >= RESOLVE_MIN,
            f"{key}: moves some registered quantity of {base} by >= 100 tolerances",
        )
        perturbations[key] = {"base": base, **d}
    controls: dict[str, Any] = {}
    for key in CONTROLS:
        ours = values(by_key[key]["syn"])
        tool = values(by_key[key]["tool_model"])
        d = discrimination(ours, tool, "reference")
        post(d.pop("_max") >= CONTROL_MIN, f"{key}: the tool model misses ours by >= 10 tolerances")
        controls[key] = {
            "ours": emitted(by_key[key]["syn"]),
            "ours_sigma_min": by_key[key]["sigma_min"],
            "tool_model": emitted(by_key[key]["tool_model"]),
            "tool_model_sigma_min": by_key[key]["tool_model_sigma_min"],
            **d,
        }
    sensitivity: dict[str, Any] = {}
    for key in SENSITIVITY:
        d = discrimination(values(by_key["RC1"]["syn"]), values(by_key[key]["syn"]), "reference")
        post(
            d.pop("_max") >= STAGE_MIN, f"{key}: a feed one stage up moves RC1 by >= 100 tolerances"
        )
        sensitivity[key] = {
            "base": "RC1",
            "feed_stage": 3,
            "sigma_min": by_key[key]["sigma_min"],
            **d,
        }
    # Within a family (T[*], L[*], V[*], top[*], bottom[*]) the registered quantities of every
    # compared case differ pairwise by more than the sum of their tolerances, so a permuted stage or
    # component index in a harness changes the classification (spec §4).
    for key in [*CASES, *PERTURBED]:
        rows = list(values(by_key[key]["syn"]).items())
        close = [
            (na, nb)
            for a, (na, (ka, va)) in enumerate(rows)
            for nb, (kb, vb) in rows[a + 1 :]
            if na.split("[")[0] == nb.split("[")[0]
            and abs(va - vb) <= tolerance(ka, va) + tolerance(kb, vb)
        ]
        if close:
            raise SystemExit(f"claim failed: {key}: quantities within a tolerance: {close}")
        post(True, f"{key}: within each family the registered quantities differ pairwise")
    # Amendment 1 (spec §17.1, §17.4)
    inverse_partner: dict[str, Any] = {}
    for key, partner in INVERSE_PARTNER.items():
        d = discrimination(values(by_key[partner]["syn"]), values(by_key[key]["syn"]), "moved")
        post(
            d.pop("_max") >= RESOLVE_MIN,
            f"{key}: moves its ratio-partner base case {partner} by >= 100 tolerances",
        )
        inverse_partner[key] = {"partner": partner, **d}
    spec_responses = {key: by_key[key]["spec_response"] for key in [*CASES, *PERTURBED]}
    worst_key, worst_end = max(
        ((k, e) for k, ends in spec_responses.items() for e in ends),
        key=lambda ke: mpf(spec_responses[ke[0]][ke[1]]["max_ratio"]),
    )
    alternatives = {
        key: by_key[key]["definition_alternatives"]
        for key in [*CASES, *PERTURBED]
        if "definition_alternatives" in by_key[key]
    }
    post(
        sorted(alternatives) == sorted(INVERSE_PARTNER),
        "the inverse cases with registered wrong readings are exactly RC5, RC6 and RC7",
    )

    cases_doc = {
        "generator": "docs/derivations/scripts/s03_reference.py",
        "spec": "docs/derivations/S03-spec.md",
        "note": "Inputs only. Tool scripts read this file and nothing else of this project.",
        "components": list(NAMES),
        "cases": {k: case_inputs(k, e) for k, e in {**CASES, **PERTURBED, **CONTROLS}.items()},
        "tool_settings": TOOL_SETTINGS,
    }
    cases_bytes = encode(cases_doc)
    ref_doc = {
        "generator": "docs/derivations/scripts/s03_reference.py",
        "spec": "docs/derivations/S03-spec.md",
        "precision_digits": mp.dps,
        "cases_sha256": hashlib.sha256(cases_bytes).hexdigest(),
        "tolerance": (
            "a_k + 1e-6 |v|; a_flow 3.1e-7 mol/s, a_T 1e-5 K, a_duty 1e-2 W; v the twin value"
        ),
        "twin": twin,
        "perturbations": perturbations,
        "controls": controls,
        "sensitivity": sensitivity,
        "amendment_1": {
            "spec": "docs/derivations/S03-spec.md §17",
            "inverse_partner": inverse_partner,
            "spec_response": {
                "threshold": "rule 2d: 1e-8 relative (ratio, rate, duty), 1e-8 absolute (purity), "
                "1e-9 absolute (recovery), 1e-9 relative (temperature)",
                "claimed_max_ratio": s(SPEC_RESPONSE_MAX),
                "worst": {"case": worst_key, "end": worst_end},
                "cases": spec_responses,
            },
            "definition_alternatives": alternatives,
        },
        "claims": claims,
        "claim_count": len(claims),
    }
    return cases_bytes, encode(ref_doc), len(claims)


def encode(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="re-derive and compare both files")
    parser.add_argument("--emit", action="store_true", help="write both files")
    parser.add_argument("--out-dir", type=Path, default=HERE, help="where --emit writes")
    args = parser.parse_args(argv)
    if not (args.check or args.emit):
        parser.error("choose --check and/or --emit")
    cases_bytes, ref_bytes, count = build_documents()
    print(f"{count} claims passed")
    if args.check:
        status = 0
        for path, payload in ((CASES_OUT, cases_bytes), (REF_OUT, ref_bytes)):
            committed = path.read_bytes() if path.exists() else b""
            if committed != payload:
                print(f"{path} differs from the generator's output", file=sys.stderr)
                status = 1
            else:
                print(f"{path} is byte-identical to the generator's output")
        if status:
            return status
    if args.emit:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        for name, payload in ((CASES_OUT.name, cases_bytes), (REF_OUT.name, ref_bytes)):
            (args.out_dir / name).write_bytes(payload)
            print("wrote", args.out_dir / name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
