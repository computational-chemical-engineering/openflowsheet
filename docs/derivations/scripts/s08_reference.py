"""S08 reference generator: the block roots ``V^a 2P^b L^c`` of four SYN-001 columns (WO-G).

Derived from ``docs/derivations/S08-design.md`` §5.2 and §6.2 and evaluated with mpmath at 50
significant digits. It imports nothing from ``openflowsheet``. It reuses the S02 generator
(``s02_reference.py``, itself independent of ``src/``) for SYN-001's closed forms, the
generator's column formulation (8 unknowns per equilibrium stage; quotient equilibrium rows on a
``TWO_PHASE`` stage; pinned rows ``v = 0`` on a ``LIQUID`` and ``l = 0`` on a ``VAPOR`` stage),
S02 §6's initializer, its damped Newton with complex-step derivatives and its scaled
``sigma_min``. From the S06 generator it reads only the case table, for the candidate lists of
J5, U1 and U2.

**How a root is reached (the decoupling).** At a block root the L-block sends no vapour up and the
V-block sends no liquid down, so the core ``2P^b`` is an S02 column of its own: its stages, their
inlets, the condenser when the core holds stage 1 and the reboiler when it holds stage N. The
generator solves that core column as S02's generator does (S02 §6's initializer, the pre-solve, the
straight 16-step path to the target slots), then completes the column by the explicit passes of the
blocks -- liquid top-down, vapour bottom-up, each stage's temperature from its energy row at its
specified duty, which is linear in ``T`` for SYN-001's constant ``C_P`` and so solved exactly. The
claim that the assembled state is a root of the *full* column's rows below 1e-40 is what makes the
decoupling a checked fact rather than an assumption. With no core (P2, and P1 as a cross-check) the
root is the passes alone, a closed form.

**Candidates.** §5.2's source analysis is transcribed here independently of the implementation
(``candidates``) and its output is claimed equal to §5.2's table for all thirteen specifications it
lists. The first candidate's signature is claimed equal to §6.2's expected signature.

**What this does not establish.** Which path the implementation takes to a root (Stage A or B,
iteration counts, records); that the implementation's endpoint (§5.3) converges to these roots;
uniqueness beyond local uniqueness (``sigma_min``); and anything about other cases, other
property methods, or the near-trivial split itself (F4), of which only F1's stage-4 subcooling
at the root is claimed.

    python docs/derivations/scripts/s08_reference.py --check
    python docs/derivations/scripts/s08_reference.py \
        --emit docs/derivations/scripts/s08_reference.json

``--check`` re-derives every claim, refuses to continue when one fails, and compares the result with
the committed file byte for byte. ``--emit`` runs the same claims and writes the file only when all
of them hold.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from mpmath import mp, mpf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s02_reference as s2  # noqa: E402  (SYN-001, the S02 column formulation, Newton, sigma_min)
import s06_reference as s6  # noqa: E402  (the S06 case table: J5, U1, U2)

mp.dps = 50
DEFAULT_OUT = Path(__file__).with_name("s08_reference.json")
S02_JSON = Path(__file__).with_name("s02_reference.json")
NC = s2.NC
s, sv = s2.s, s2.sv

SIGMA_REGULAR = mpf("1e-4")  # S08-design §6.2: regular above this, with S02's scaling (S02 §9)
FLOW_MIN = mpf("1e-3")  # S08-design §6.2: every core stage has L, V > 1e-3 mol/s
ROOT_TOL = s2.NEWTON_TOL  # 1e-40: the generator's rows at a registered root
IMPL_ROWS_TOL = mpf("1e-38")  # S02's bound on the implementation's division-free rows at the root
# Block-stage admissibility, as a temperature margin: T_bub(l_j) - T_j on a LIQUID stage, T_j -
# T_dew(v_j) on a VAPOR stage. 0.1 K is 1000x S02's state tolerance in T (1e-4 K, S02 §10), so an
# implementation root within state tolerance of this one stays strictly single-phase; the smallest
# margins are set by pressure alone (F1 stage 4 and D1 stage 2, about 0.37 K).
ADMISSIBLE_MARGIN = mpf("0.1")
# S08-design §6.2, F1: item 6 rests on stage 4's subcooling being at least this.
F1_SUBCOOLING = mpf("0.3")
# A genuine two-phase stage has T = T_bub(l) = T_dew(v) (S08-design §5.5); at a 50-digit root the
# saturation error is the Newton residual's image, far below this.
SATURATION_ZERO = mpf("1e-30")
# §6.2's float sanity values are quoted to 4 decimals in K and 6 significant digits in mol/s.
PROTOTYPE_T, PROTOTYPE_V = mpf("1e-4"), mpf("1e-5")
# A closed-form relation, evaluated in 50 digits: exact up to roundoff on O(400 K) quantities.
EXACT = mpf("1e-45")
# S02's 25-digit registered P1 temperatures (~300 K) resolve 1e-22 K.
P1_AGREE = mpf("1e-20")

CLAIMS: list[str] = []


def claim(condition: bool, text: str) -> None:
    if not condition:
        raise SystemExit(f"claim failed: {text}")
    CLAIMS.append(text)


def adopt_s02_claims(label: str) -> None:
    """Claims raised inside the reused S02 functions (its initializer) count as this file's."""
    CLAIMS.extend(f"[{label}] {c}" for c in s2.CLAIMS)
    s2.CLAIMS.clear()


# -- the cases (S08-design §6.2; normative inputs) ------------------------------------------------
FEED = s2.FEED  # (0.3, 0.4, 0.3) mol/s
SMALL = ("0.03", "0.04", "0.03")
HALF = ("0.15", "0.2", "0.15")


def p_profile() -> list[Any]:
    return s2.profile(5, "100000", "1000")  # P_j* = 1.00 + 0.01 (j - 1) bar


CASES: dict[str, dict[str, Any]] = {
    "P2": {
        "N": 5,
        "condenser": "partial",
        "reboiler": "none",
        "P": p_profile(),
        "Q": {},
        "inlets": [s2.inlet("bottom", FEED, "420", "104000", "VAPOR", 5)],
        "spec": {"condenser": ("duty", "-3000")},
    },
    "P3": {
        "N": 5,
        "condenser": "partial",
        "reboiler": "partial",
        "P": p_profile(),
        "Q": {},
        "inlets": [
            s2.inlet("feed", FEED, "385", "102000", "VAPOR", 3),
            s2.inlet("cold", HALF, "300", "103000", "LIQUID", 4),
        ],
        "spec": {"condenser": ("distillate_rate", "0.5"), "reboiler": ("duty", "1000")},
    },
    "F1": {
        "N": 5,
        "condenser": "partial",
        "reboiler": "none",
        "P": p_profile(),
        "Q": {},
        "inlets": [
            s2.inlet("bottom", SMALL, "330", "104000", "LIQUID", 5),
            s2.inlet("feed", FEED, "385", "102000", "VAPOR", 3),
        ],
        "spec": {"condenser": ("distillate_rate", "0.5")},
    },
    "D1": {
        "N": 5,
        "condenser": "none",
        "reboiler": "partial",
        "P": p_profile(),
        "Q": {},
        "inlets": [
            s2.inlet("top", SMALL, "400", "100000", "VAPOR", 1),
            s2.inlet("feed", FEED, "340", "102000", "LIQUID", 3),
        ],
        "spec": {"reboiler": ("duty", "30000")},
    },
}
ROLES = {
    "P2": "P1's mirror: all vapour, reached through Stage B",
    "P3": "partly one-phase: the weak reboiler is quenched by the cold feed; Stage B with a core",
    "F1": "flooded bottom: a dead section below a vapour feed; Stage A is rejected by item 6",
    "D1": "dry top: a dead section above a liquid feed; reached through Stage A",
}
# S08-design §6.2's "Expected" signatures, over the equilibrium stages, top to bottom.
EXPECTED_SIGNATURE = {
    "P2": ["VAPOR"] * 5,
    "P3": ["TWO_PHASE"] * 3 + ["LIQUID"] * 2,
    "F1": ["TWO_PHASE"] * 3 + ["LIQUID"] * 2,
    "D1": ["VAPOR"] * 2 + ["TWO_PHASE"] * 3,
}
# S08-design §6.2's float sanity values (prototype), K and mol/s.
PROTOTYPE = {
    "P2": {"T": ("390", "420", "420", "420", "420")},
    "P3": {
        "T": ("350.9491", "362.4433", "370.0147", "335.0069", "345.0059"),
        "V": ("0.5", "1.08077", "1.04935", "0", "0"),
    },
    "F1": {"T": ("350.9491", "362.4433", "370.0147", "370.0137", "363.3439")},
    "D1": {"T": ("372.9262", "369.9392", "369.9392", "386.5229", "395.475")},
}


def implementation_inputs(case: dict[str, Any]) -> dict[str, Any]:
    """The case in ``ColumnSpec``'s vocabulary (``models/syn001/column.py``), for WO-4."""
    n_st = case["N"]

    def end_spec(end: str) -> Any:
        if case[end] == "none":
            return None
        kind, value = case["spec"][end]
        return {"kind": kind, "value": value}

    def state(f: dict[str, Any]) -> dict[str, Any]:
        return {"n": sv(f["n"]), "T": s(f["T"]), "P": s(f["P"]), "phase": f["phase"]}

    ends = {1} if case["condenser"] != "none" else set()
    ends |= {n_st} if case["reboiler"] != "none" else set()
    top = [f for f in case["inlets"] if f["port"] == "top"]
    bottom = [f for f in case["inlets"] if f["port"] == "bottom"]
    return {
        "stage_count": n_st,
        "pressures": sv(case["P"]),
        "duties": [
            None if j in ends else s(mpf(case["Q"].get(j, "0"))) for j in range(1, n_st + 1)
        ],
        "condenser": case["condenser"],
        "reboiler": case["reboiler"],
        "condenser_spec": end_spec("condenser"),
        "reboiler_spec": end_spec("reboiler"),
        "top": state(top[0]) if top else None,
        "bottom": state(bottom[0]) if bottom else None,
        "sides": [
            {"port": f["port"], "stage": f["stage"], **state(f)}
            for f in case["inlets"]
            if f["port"] not in ("top", "bottom")
        ],
    }


# -- S08-design §5.2: sources, fixed stages and candidates (independent transcription) -----------
def topology(
    base: dict[str, Any], ends: dict[str, tuple[str, Any]], duties: dict[int, Any] | None = None
) -> dict[str, Any]:
    """What §5.2 reads of a specification: N, the end kinds and their specification kinds (with a
    temperature specification's stage), the present inlets (port, stage, declared phase, flowing?)
    and the intermediate duties. No specification value is read."""
    n_st = base["N"]
    end_stages = ({1} if base["condenser"] != "none" else set()) | (
        {n_st} if base["reboiler"] != "none" else set()
    )
    q = {j: mpf(base["Q"].get(j, "0")) for j in range(1, n_st + 1) if j not in end_stages}
    if duties is not None:
        q.update({j: mpf(v) for j, v in duties.items()})
    return {
        "N": n_st,
        "condenser": base["condenser"],
        "reboiler": base["reboiler"],
        "ends": dict(ends),
        "inlets": [(f["port"], f["stage"], f["phase"], sum(f["n"]) > 0) for f in base["inlets"]],
        "duties": q,
    }


def equilibrium(top: dict[str, Any]) -> list[int]:
    return list(range(2 if top["condenser"] == "total" else 1, top["N"] + 1))


def sources(
    top: dict[str, Any], end_ports_any_phase: bool = False
) -> tuple[set[int], set[int], set[int]]:
    """§5.2's table: liquid-source stages, vapour-source stages, fixed (TWO_PHASE) stages.

    The table names a top inlet only when declared ``LIQUID`` and a bottom inlet only when declared
    ``VAPOR``. ``end_ports_any_phase`` is the other reading (either phase is a source at its
    stage); it exists only so that the claim "no registered list depends on it" is executable."""
    n_st, eqs = top["N"], equilibrium(top)
    liquid: set[int] = set()
    vapour: set[int] = set()
    fixed: set[int] = set()
    if top["condenser"] == "partial":
        liquid.add(1)
    if top["condenser"] == "total":
        liquid.add(2)
        fixed.add(2)
    if top["reboiler"] == "partial":
        vapour.add(n_st)
    for port, stage, phase, flows in top["inlets"]:
        if not flows:
            continue  # a dormant inlet is never a source
        if port == "top" and not end_ports_any_phase:
            if phase == "LIQUID":
                liquid.add(1)
        elif port == "bottom" and not end_ports_any_phase:
            if phase == "VAPOR":
                vapour.add(n_st)
        else:
            (liquid if phase == "LIQUID" else vapour).add(stage)
    for j, q in top["duties"].items():
        if q < 0:
            liquid.add(j)
        elif q > 0:
            vapour.add(j)
    for end, (kind, stage) in top["ends"].items():
        if top[end] == "partial" and kind != "duty":
            fixed.add(1 if end == "condenser" else n_st)
        if kind == "temperature" and stage in eqs:
            fixed.add(stage)
    return liquid, vapour, fixed


def candidates(
    top: dict[str, Any], end_ports_any_phase: bool = False, v3_sides_only: bool = False
) -> list[tuple[int, int]]:
    """§5.2: every valid (a, c), ordered by a + c, then a. (V3)'s "flowing inlet" is any present
    port of that phase; ``v3_sides_only`` (side feeds only) is the reading §5.2's table excludes,
    kept so that the exclusion is a claim."""
    eqs = equilibrium(top)
    n = len(eqs)
    liquid, vapour, fixed = sources(top, end_ports_any_phase)
    phases: dict[int, set[str]] = {}
    for port, stage, phase, flows in top["inlets"]:
        if flows and not (v3_sides_only and port in ("top", "bottom")):
            phases.setdefault(stage, set()).add(phase)
    out = []
    for size in range(1, n + 1):  # (V4): (0, 0) is Stage A's
        for a in range(size + 1):
            c = size - a
            b = n - size
            if not fixed <= set(eqs[a : a + b]):  # (V1)
                continue
            if b >= 1:  # (V2)
                if eqs[a] not in liquid or eqs[a + b - 1] not in vapour:
                    continue
            else:  # (V3)
                if a >= 1 and "VAPOR" not in phases.get(eqs[a - 1], set()):
                    continue
                if c >= 1 and "LIQUID" not in phases.get(eqs[a], set()):
                    continue
            out.append((a, c))
    return out


def signature_of(top: dict[str, Any], a: int, c: int) -> list[str]:
    n = len(equilibrium(top))
    return ["VAPOR"] * a + ["TWO_PHASE"] * (n - a - c) + ["LIQUID"] * c


def is_block(sig: Sequence[str]) -> bool:
    """S02 §4.3's block rule: V^a 2P^b L^c, top to bottom (no ZERO_FLOW stage here)."""
    rank = {"VAPOR": 0, "TWO_PHASE": 1, "LIQUID": 2}
    return all(g in rank for g in sig) and all(
        rank[sig[k]] <= rank[sig[k + 1]] for k in range(len(sig) - 1)
    )


def candidate_specs() -> dict[str, dict[str, Any]]:
    """The thirteen specifications of §5.2's expected-candidate table, as §5.2 reads them."""

    def direct(case: dict[str, Any]) -> dict[str, tuple[str, Any]]:
        return {end: (kind, None) for end, (kind, _) in case["spec"].items()}

    def s06(entry: tuple[str, dict[str, tuple[str, Any, Any]]]) -> dict[str, Any]:
        base, spec = entry
        ends = {
            end: (kind, attr if kind == "temperature" else None)
            for end, (kind, attr, _) in spec.items()
        }
        return topology(s2.CASES[base], ends)

    claim(
        ("duty", "duty") in s2.VARIANT_SETS["M1"],
        "V-M1 duty+duty is a registered S02 specification set",
    )
    p1 = dict(s2.CASES["M3"], spec={"reboiler": ("duty", "3000")})
    out = {
        "P1": topology(p1, direct(p1)),
        **{name: topology(CASES[name], direct(CASES[name])) for name in ("P2", "P3", "F1", "D1")},
        "M3": topology(s2.CASES["M3"], direct(s2.CASES["M3"])),
        "V-M1 duty+duty": topology(
            s2.CASES["M1"], {"condenser": ("duty", None), "reboiler": ("duty", None)}
        ),
        **{name: topology(s2.CASES[name], direct(s2.CASES[name])) for name in ("M1", "M2", "M4")},
        "J5": s06(s6.CASES["J5"]),
        "U1": s06(s6.UNREACHED["U1"]),
        "U2": s06(s6.UNREACHED["U2"]),
    }
    return out


# S08-design §5.2's "Expected candidate lists" table (A01).
EXPECTED_CANDIDATES: dict[str, list[tuple[int, int]]] = {
    "P1": [(0, 5)],
    "P2": [(5, 0)],
    "P3": [(0, 2)],
    "F1": [(0, 2)],
    "D1": [(2, 0)],
    "M3": [(0, 5)],
    "V-M1 duty+duty": [(3, 0)],
    "M1": [],
    "M2": [],
    "M4": [],
    "J5": [],
    "U1": [],
    "U2": [],
}


def candidate_section() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    specs = candidate_specs()
    out: dict[str, Any] = {}
    for name, top in specs.items():
        found = candidates(top)
        claim(
            found == EXPECTED_CANDIDATES[name],
            f"{name}: the §5.2 candidate list is {EXPECTED_CANDIDATES[name]} (§5.2's table)",
        )
        liquid, vapour, fixed = sources(top)
        out[name] = {
            "liquid_sources": sorted(liquid),
            "vapour_sources": sorted(vapour),
            "fixed_stages": sorted(fixed),
            "candidates": [list(ac) for ac in found],
            "signatures": [signature_of(top, a, c) for a, c in found],
        }
    for name in ("U1", "U2"):
        claim(
            out[name]["fixed_stages"] == [2, 7],
            f"{name}: fixed stages {{2, 7}} (S08-design §5.2 table)",
        )
    claim(
        all(candidates(top, end_ports_any_phase=True) == candidates(top) for top in specs.values()),
        "no list depends on whether a top VAPOR or bottom LIQUID inlet is a source",
    )
    claim(
        candidates(specs["P1"], v3_sides_only=True) == []
        and candidates(specs["P2"], v3_sides_only=True) == [],
        "§5.2's table fixes (V3)'s reading: P1's (0, 5) and P2's (5, 0) need the top and bottom"
        " ports to count as (V3)'s flowing inlet",
    )
    return out, specs


# -- the root: the core column solved as S02's generator does, then the block passes ------------
def core_case(case: dict[str, Any], core: list[int]) -> dict[str, Any]:
    """The core 2P^b as an S02 column of its own (stages renumbered 1..b)."""
    n_st = case["N"]
    assert case["condenser"] != "total", "no registered S08 case has a total condenser"
    renum = {j: k + 1 for k, j in enumerate(core)}
    sub = {
        "name": f"{case['name']} core",
        "N": len(core),
        "condenser": case["condenser"] if core[0] == 1 else "none",
        "reboiler": case["reboiler"] if core[-1] == n_st else "none",
        "P": [case["P"][j - 1] for j in core],
        "Q": {renum[j]: q for j, q in case["Q"].items() if j in renum},
        "inlets": [
            dict(copy.deepcopy(f), stage=renum[f["stage"]])
            for f in case["inlets"]
            if f["stage"] in renum
        ],
        "spec": {},
    }
    if sub["condenser"] != "none":
        sub["spec"]["condenser"] = case["spec"]["condenser"]
    if sub["reboiler"] != "none":
        sub["spec"]["reboiler"] = case["spec"]["reboiler"]
    return sub


def solve_core(sub: dict[str, Any]) -> dict[str, Any]:
    """S02 §6's initializer, the pre-solve and the straight 16-step path (s02 ``solve_case``)."""
    two = ["TWO_PHASE"] * sub["N"]
    init = s2.initializer(sub)
    adopt_s02_claims(sub["name"])
    pre = s2.presolve_slots(sub, init["profile"])
    x = s2.newton(lambda y: s2.residual(sub, y, pre, two), s2.pack(sub, init["state"]))
    st0 = s2.unpack(sub, x)
    tgt = s2.target_slots(sub)
    cont = {j: tgt[j] for j in tgt if pre[j] != tgt[j]}
    p0 = {j: s2.slot_value(sub, st0, j, kind) for j, (kind, _) in cont.items()}
    for k in range(1, s2.PATH_STEPS + 1):
        lam = mpf(k) / s2.PATH_STEPS
        slots = dict(tgt)
        for j, (kind, value) in cont.items():
            slots[j] = (kind, value + (1 - lam) * (p0[j] - value))
        x = s2.newton(lambda y, sl=slots: s2.residual(sub, y, sl, two), x)
    return s2.unpack(sub, x)


def block_passes(
    case: dict[str, Any], st: dict[str, Any], v_block: list[int], l_block: list[int]
) -> None:
    """S08-design §5.3 steps 5-6 at a root: every inflow of a block stage leaves in its phase, and
    its temperature solves its energy row at the specified duty Q_j* -- linear in T because
    SYN-001's C_P is constant: h_L = C_P (T - T_ref) + V_i (P - P_ref) and
    h_V = C_P (T - T_ref) + L_i."""
    slots = s2.target_slots(case)
    p = case["P"]
    for j in l_block:  # top-down
        kind, q = slots[j]
        assert kind == "Q", (case["name"], j)
        ins = s2.inflows(case, st, j)
        liq = [sum(f[0][i] for f in ins) for i in range(NC)]
        h_in = sum(s2.h_stream(*f) for f in ins) + q
        poynting = sum(liq[i] * s2.V_MOL[i] * (p[j - 1] - s2.P_REF) for i in range(NC))
        st["l"][j], st["v"][j] = liq, [mpf(0)] * NC
        st["T"][j] = s2.T_REF + (h_in - poynting) / (s2.C_P * sum(liq))
        st["Q"][j] = q
    for j in reversed(v_block):  # bottom-up
        kind, q = slots[j]
        assert kind == "Q", (case["name"], j)
        ins = s2.inflows(case, st, j)
        vap = [sum(f[0][i] for f in ins) for i in range(NC)]
        h_in = sum(s2.h_stream(*f) for f in ins) + q
        latent = sum(vap[i] * s2.L_VAP[i] for i in range(NC))
        st["v"][j], st["l"][j] = vap, [mpf(0)] * NC
        st["T"][j] = s2.T_REF + (h_in - latent) / (s2.C_P * sum(vap))
        st["Q"][j] = q


def block_root(case: dict[str, Any], a: int, c: int) -> tuple[dict[str, Any], list[str]]:
    eqs = s2.eq_stages(case)
    b = len(eqs) - a - c
    v_block, core, l_block = eqs[:a], eqs[a : a + b], eqs[a + b :]
    zero = [mpf(0)] * NC
    st: dict[str, Any] = {
        "l": {j: list(zero) for j in eqs},
        "v": {j: list(zero) for j in eqs},
        "T": {j: mpf(0) for j in eqs},
        "Q": {j: mpf(0) for j in eqs},
    }
    if core:
        sub = solve_core(core_case(case, core))
        for k, j in enumerate(core, start=1):
            st["l"][j], st["v"][j] = list(sub["l"][k]), list(sub["v"][k])
            st["T"][j], st["Q"][j] = sub["T"][k], sub["Q"][k]
    block_passes(case, st, v_block, l_block)
    sig = ["VAPOR"] * a + ["TWO_PHASE"] * b + ["LIQUID"] * c
    return st, sig


# -- checks on a root -----------------------------------------------------------------------------
def t_bub(n: Sequence[Any], p: Any) -> Any:
    return s2.rr_temperature(n, 0, p)


def t_dew(n: Sequence[Any], p: Any) -> Any:
    return s2.rr_temperature(n, 1, p)


def closure(case: dict[str, Any], st: dict[str, Any]) -> tuple[Any, Any]:
    prod = s2.products(case, st)
    comp = max(
        abs(sum(f["n"][i] for f in case["inlets"]) - prod["top"][0][i] - prod["bottom"][0][i])
        for i in range(NC)
    )
    energy = (
        sum(s2.h_stream(f["n"], f["T"], f["P"], f["phase"]) for f in case["inlets"])
        + sum(st["Q"].values())
        - s2.h_stream(*prod["top"])
        - s2.h_stream(*prod["bottom"])
    )
    return comp, abs(energy)


def solve_case(name: str, cand: list[tuple[int, int]]) -> tuple[dict[str, Any], dict[str, Any]]:
    case = CASES[name]
    case["name"] = name
    a, c = cand[0]
    st, sig = block_root(case, a, c)
    claim(sig == EXPECTED_SIGNATURE[name], f"{name}: the first candidate's signature is §6.2's")
    claim(is_block(sig), f"{name}: the signature conforms to the block rule V^a 2P^b L^c")
    tgt = s2.target_slots(case)
    x = s2.pack(case, st)
    worst = max(abs(r) for r in s2.residual(case, x, tgt, sig))
    claim(
        worst < ROOT_TOL,
        f"{name}: the core root completed by the block passes is a root of the full column's rows"
        " below 1e-40",
    )
    claim(
        s2.implementation_rows_max(case, st, tgt, sig) < IMPL_ROWS_TOL,
        f"{name}: the implementation's division-free rows vanish below 1e-38",
    )
    p, eqs = case["P"], s2.eq_stages(case)
    claim(
        all(s2.T_MIN <= st["T"][j] <= s2.T_MAX for j in eqs),
        f"{name}: every stage temperature lies in SYN-001's domain [280, 440] K",
    )
    smin = s2.sigma_min(case, x, tgt, sig)
    claim(smin >= SIGMA_REGULAR, f"{name}: regular, scaled sigma_min >= 1e-4 (S02's scaling)")
    core = [j for j in eqs if sig[j - 1] == "TWO_PHASE"]
    blocks = [j for j in eqs if sig[j - 1] != "TWO_PHASE"]
    pins = [
        (j, i)
        for j in blocks
        for i in range(NC)
        if (st["v"][j][i] if sig[j - 1] == "LIQUID" else st["l"][j][i]) != 0
    ]
    claim(not pins, f"{name}: every pinned flow on a block stage is exactly zero")
    min_core = min((min(sum(st["l"][j]), sum(st["v"][j])) for j in core), default=None)
    if core:
        claim(
            min_core > FLOW_MIN
            and all(st["l"][j][i] > 0 and st["v"][j][i] > 0 for j in core for i in range(NC)),
            f"{name}: every core stage has L, V > 1e-3 mol/s and every component flow positive",
        )
    sat = {}
    for j in core:
        sat[j] = max(
            abs(st["T"][j] - t_bub(st["l"][j], p[j - 1])),
            abs(st["T"][j] - t_dew(st["v"][j], p[j - 1])),
        )
    if core:
        claim(
            max(sat.values()) < SATURATION_ZERO,
            f"{name}: every core stage lies at its bubble and dew temperature (error < 1e-30 K)",
        )
    admissibility = {}
    for j in blocks:
        t, pj = st["T"][j], p[j - 1]
        if sig[j - 1] == "LIQUID":
            ts = t_bub(st["l"][j], pj)
            margin, frac = ts - t, s2.bubble_margin(st["l"][j], t, pj)
            label = "T_bub"
        else:
            ts = t_dew(st["v"][j], pj)
            margin, frac = t - ts, s2.dew_margin(st["v"][j], t, pj)
            label = "T_dew"
        claim(
            margin >= ADMISSIBLE_MARGIN and frac > 0,
            f"{name}: block stage {j} ({sig[j - 1]}) admissible by >= 0.1 K",
        )
        admissibility[str(j)] = {
            "phase": sig[j - 1],
            label: s(ts),
            "margin_K": mp.nstr(margin, 8),
            "margin_sum": mp.nstr(frac, 8),
        }
    comp, energy = closure(case, st)
    claim(
        comp < mpf("1e-38") and energy < mpf("1e-33"),
        f"{name}: overall component and energy closure",
    )
    proto = PROTOTYPE[name]
    dev_t = max(abs(st["T"][j] - mpf(proto["T"][j - 1])) for j in eqs)
    claim(dev_t <= PROTOTYPE_T, f"{name}: T agrees with §6.2's float sanity values within 1e-4 K")
    if "V" in proto:
        dev_v = max(abs(sum(st["v"][j]) - mpf(proto["V"][j - 1])) for j in eqs)
        claim(dev_v <= PROTOTYPE_V, f"{name}: V agrees with §6.2's float sanity values within 1e-5")
    out = {
        "role": ROLES[name],
        "inputs": implementation_inputs(case),
        "candidate": [a, c],
        "signature": sig,
        "core": core,
        "v_block": [j for j in eqs if sig[j - 1] == "VAPOR"],
        "l_block": [j for j in eqs if sig[j - 1] == "LIQUID"],
        "root": s2.record(case, st),
        "pinned_zero": [f"{'v' if sig[j - 1] == 'LIQUID' else 'l'}_{j}" for j in blocks],
        "sigma_min": mp.nstr(smin, 6),
        "core_min_flow": mp.nstr(min_core, 6) if core else None,
        "core_saturation_error_max_K": mp.nstr(max(sat.values()), 3) if core else None,
        "admissibility": admissibility,
        "prototype_deviation_T_K": mp.nstr(dev_t, 3),
    }
    return out, {"st": st, "sig": sig, "x": x}


def case_specific(doc: dict[str, Any], sols: dict[str, dict[str, Any]]) -> None:
    """The per-case closed forms and the claims §6.2 names."""
    # P2: v_j = bottom inlet, T_j = 420 K for j >= 2, T_1 = 420 + Q_c*/(F C_P) = 390 K, bottoms 0.
    st, p = sols["P2"]["st"], CASES["P2"]["P"]
    feed = CASES["P2"]["inlets"][0]["n"]
    claim(
        all(st["v"][j] == feed and st["l"][j] == [0] * NC for j in range(1, 6))
        and all(abs(st["T"][j] - 420) < EXACT for j in range(2, 6))
        and abs(st["T"][1] - 390) < EXACT,
        "P2: the closed form v_j = bottom inlet, T_j = 420 K (j >= 2), T_1 = 390 K, bottoms 0",
    )
    dew1 = t_dew(st["v"][1], p[0])
    claim(
        abs(dew1 - mpf("373.128")) < mpf("5e-4")
        and abs(st["T"][1] - dew1 - mpf("16.9")) < mpf("0.05"),
        "P2: stage 1's dew temperature is 373.128 K at 1 bar, a 16.9 K margin (§6.2)",
    )
    doc["cases"]["P2"]["closed_form"] = {
        "T": "T_1 = 420 + Q_c*/(F C_P) = 390 K; T_j = 420 K for j >= 2",
        "v": "v_j = bottom inlet for every j",
        "bottoms": "+0.0",
        "T_dew_stage_1": s(dew1),
    }
    # F1: stage 4 is stage 3's liquid 1 kPa down: T_4 = T_3 - V_mol dP / C_P = T_3 - 1e-3 K exactly,
    # and subcooled by >= 0.3 K (item 6 rests on this, §6.2).
    st, p = sols["F1"]["st"], CASES["F1"]["P"]
    claim(
        st["l"][4] == st["l"][3] and abs(st["T"][4] - st["T"][3] + mpf("0.001")) < EXACT,
        "F1: stage 4 passes stage 3's liquid adiabatically 1 kPa down: T_4 = T_3 - 1e-3 K exactly",
    )
    sub4 = t_bub(st["l"][4], p[3]) - st["T"][4]
    claim(
        sub4 >= F1_SUBCOOLING,
        "F1: T_bub(l_4, P_4) exceeds the root's T_4 by >= 0.3 K (item 6 rests on this)",
    )
    claim(
        abs(sub4 - mpf("0.375")) < mpf("5e-4"),
        "F1: stage 4's subcooling is 0.375 K, by pressure alone (§6.2)",
    )
    doc["cases"]["F1"]["stage_4_subcooling_K"] = s(sub4)
    # D1: stage 2 passes stage 3's vapour adiabatically up: vapour enthalpy is P-independent in
    # SYN-001, so T_2 = T_3 exactly.
    st = sols["D1"]["st"]
    claim(
        st["v"][2] == st["v"][3] and abs(st["T"][2] - st["T"][3]) < EXACT,
        "D1: stage 2 passes stage 3's vapour adiabatically 1 kPa up: T_2 = T_3 exactly",
    )
    # Core decoupling (§6.2, A11): P3 and F1 share their core column and so their stages 1-3.
    p3, f1 = sols["P3"]["st"], sols["F1"]["st"]
    claim(
        core_case(CASES["P3"], [1, 2, 3]) | {"name": ""}
        == core_case(CASES["F1"], [1, 2, 3]) | {"name": ""},
        "P3, F1: their core columns (stages 1-3, inlets, condenser, specification) are identical",
    )
    diff = max(
        [abs(p3["T"][j] - f1["T"][j]) for j in (1, 2, 3)]
        + [abs(p3[k][j][i] - f1[k][j][i]) for k in ("l", "v") for j in (1, 2, 3) for i in range(NC)]
        + [abs(p3["Q"][1] - f1["Q"][1])]
    )
    claim(diff < ROOT_TOL, "P3, F1: stages 1-3 (T, l, v, Q_1) are equal below 1e-40")
    doc["core_decoupling"] = {
        "cases": ["P3", "F1"],
        "stages": [1, 2, 3],
        "max_abs_difference": mp.nstr(diff, 3),
    }


def p1_crosscheck() -> dict[str, Any]:
    """P1 stays in s02_reference.json; the block passes reproduce its registered closed form."""
    ref = json.loads(S02_JSON.read_text())["phase_case"]["P1"]
    case = dict(
        copy.deepcopy(s2.CASES["M3"]), name="P1", spec={"reboiler": ("duty", ref["Q_reboiler"])}
    )
    st, sig = block_root(case, 0, 5)
    dev = max(abs(st["T"][j] - mpf(ref["T"][j - 1])) for j in range(1, 6))
    claim(
        sig == ref["signature"]
        and dev < P1_AGREE
        and all(st["l"][j] == case["inlets"][0]["n"] for j in range(1, 6)),
        "P1: the L-block pass reproduces s02_reference.json's closed form (T within 1e-20 K)",
    )
    return {"source": "s02_reference.json phase_case.P1", "max_abs_T_deviation_K": mp.nstr(dev, 3)}


def build() -> dict[str, Any]:
    doc: dict[str, Any] = {
        "generator": "docs/derivations/scripts/s08_reference.py",
        "spec": "docs/derivations/S08-design.md",
        "precision_digits": mp.dps,
        "conventions": {
            "units": "mol/s, K, Pa, W",
            "signature": "regimes over the equilibrium stages, top to bottom",
            "root": "s02_reference.py's record(): per stage T, Q, l, v, L, V; top and bottom"
            " products",
            "pinned_zero": "exact zeros; the implementation's pins are +0.0 with the sign bit"
            " checked",
            "admissibility": "margin_K = T_bub(l) - T (LIQUID) or T - T_dew(v) (VAPOR);"
            " margin_sum = 1 - sum K x (LIQUID) or 1 - sum y/K (VAPOR)",
            "candidate_reading": "a bottom inlet declared LIQUID and a top inlet declared VAPOR"
            " are not sources (§5.2's table; no registered list depends on it); (V3)'s 'flowing"
            " inlet' is any present port of that phase (§5.2's table forces it: P1, P2)",
        },
    }
    doc["inputs_changed"] = {
        "cases": [],
        "note": "S08-design §10 Q2: §6.2's inputs are used as registered; every claim held",
    }
    doc["does_not_establish"] = [
        "the implementation's path to a root: Stage A or B, iteration counts, attempt records",
        "that the implementation's block endpoint (§5.3) converges to these roots",
        "uniqueness beyond local uniqueness at a regular root (sigma_min >= 1e-4)",
        "the near-trivial split (F4) itself; only F1's stage-4 subcooling at the root is claimed",
        "anything for other cases, other property methods, or SYN-001's K beyond its definition",
    ]
    doc["candidate_lists"], specs = candidate_section()
    doc["cases"] = {}
    sols = {}
    for name in CASES:
        doc["cases"][name], sols[name] = solve_case(name, candidates(specs[name]))
    case_specific(doc, sols)
    doc["p1_crosscheck"] = p1_crosscheck()
    doc["claims"] = list(CLAIMS)
    doc["claim_count"] = len(CLAIMS)
    return doc


def encode(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="re-derive every claim and compare with the committed file",
    )
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
