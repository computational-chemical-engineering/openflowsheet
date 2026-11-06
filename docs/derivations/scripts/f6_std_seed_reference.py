"""Reference values for `docs/derivations/F6-std-seed.md` (the `std.*` equation sheet, SQ-F6-2).

Every expected value of the sheet's registered cases is a closed form of SYN-001's potentials
(`docs/derivations/SYN-001.md` §1-§3) composed on `ELEMENTAL-ref-v1` with Q2.R4/Q2.R9's datum
(anchor `ig`, h = 0 and s = 0 at (T°, P°)), or, for the one IAPWS-95 pump case, S05's 50-digit
forms (`s05_reference.py`, imported unchanged). Nothing here calls OpenFlowsheet code.

The sheet's claims about its own states are checked here and the script refuses to emit when one
fails (rule 4): liquids are below their bubble point, vapours above their dew point, two-phase
states between, every state inside SYN-001's declared domain, the registered states distinguish
what they claim to distinguish.

    python3 -I docs/derivations/scripts/f6_std_seed_reference.py          # write the JSON
    python3 -I docs/derivations/scripts/f6_std_seed_reference.py --check  # byte-compare; 1 on drift
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from mpmath import mp, mpf

mp.dps = 50
HERE = Path(__file__).resolve().parent
OUT = HERE / "f6_std_seed_reference.json"
DIGITS = 25

# -- SYN-001 §1, verbatim; floats as the doubles a composed method holds ------------------------
R = mpf("8.31446261815324")
T_R, P_R = mpf(300), mpf(100000)
T_REF = mpf(float("298.15"))  # T°: the double nearest 298.15 K (ADR 0063 D4)
P_REF = mpf(100000)  # P° = P_r, so every ln(P°/P_r) term is exactly zero
COMPONENTS = ("A", "B", "C")
TB = {"A": mpf(320), "B": mpf(360), "C": mpf(400)}
LAT = {"A": mpf(25000), "B": mpf(30000), "C": mpf(35000)}
CP = mpf(100)
VL = mpf(float("1.0e-4"))
MW = mpf(float("0.100"))
T_DOMAIN, P_DOMAIN = (mpf(280), mpf(440)), (mpf(50000), mpf(200000))

CLAIMS: list[str] = []


def claim(condition: bool, text: str) -> None:
    if not condition:
        raise SystemExit(f"claim failed, nothing emitted: {text}")
    CLAIMS.append(text)


def s(x: Any) -> str:
    return mp.nstr(mpf(x), DIGITS, strip_zeros=False)


# -- shifted per-mole properties on ELEMENTAL-ref-v1 (sheet §2) -----------------------------------
def h_vap(c: str, t: Any) -> Any:  # native c_p (T - T_r) + L_c, shifted by -(c_p (T° - T_r) + L_c)
    return CP * (t - T_REF)


def h_liq(c: str, t: Any, p: Any) -> Any:
    return CP * (t - T_REF) - LAT[c] + VL * (p - P_R)


def s_vap(c: str, t: Any, p: Any, y: Any) -> Any:
    return CP * mp.log(t / T_REF) - R * mp.log(p / P_REF) - (R * mp.log(y) if y > 0 else 0)


def s_liq(c: str, t: Any, x: Any) -> Any:
    return CP * mp.log(t / T_REF) - LAT[c] / TB[c] - (R * mp.log(x) if x > 0 else 0)


def k_value(c: str, t: Any, p: Any) -> Any:
    return (P_R / p) * mp.exp((LAT[c] / R) * (1 / TB[c] - 1 / t) + VL * (p - P_R) / (R * t))


def mass(n: tuple[Any, ...]) -> Any:
    return sum((MW * ni for ni in n), mpf(0))


def bubble_t(z: tuple[Any, ...], p: Any) -> Any:
    return mp.findroot(
        lambda t: sum(zi * k_value(c, t, p) for zi, c in zip(z, COMPONENTS, strict=False)) - 1, 340
    )


def dew_t(z: tuple[Any, ...], p: Any) -> Any:
    return mp.findroot(
        lambda t: sum(zi / k_value(c, t, p) for zi, c in zip(z, COMPONENTS, strict=False)) - 1, 370
    )


def in_domain(t: Any, p: Any) -> bool:
    return T_DOMAIN[0] <= t <= T_DOMAIN[1] and P_DOMAIN[0] <= p <= P_DOMAIN[1]


def liquid(n: tuple[Any, ...], t: Any, p: Any, label: str) -> dict[str, Any]:
    tot = sum(n, mpf(0))
    z = tuple(ni / tot for ni in n)
    claim(in_domain(t, p), f"{label}: ({s(t)} K, {s(p)} Pa) inside SYN-001's domain")
    if sum(1 for ni in n if ni > 0) > 1:
        tb = bubble_t(z, p)
        claim(t < tb, f"{label}: liquid below its bubble point {mp.nstr(tb, 12)} K")
    H = sum((ni * h_liq(c, t, p) for ni, c in zip(n, COMPONENTS, strict=False)), mpf(0))  # noqa: N806
    S = sum((ni * s_liq(c, t, ni / tot) for ni, c in zip(n, COMPONENTS, strict=False)), mpf(0))  # noqa: N806
    return {"H": H, "S": S, "m": mass(n), "h": H / mass(n), "T": t, "P": p}


def vapour(n: tuple[Any, ...], t: Any, p: Any, label: str) -> dict[str, Any]:
    tot = sum(n, mpf(0))
    z = tuple(ni / tot for ni in n)
    claim(in_domain(t, p), f"{label}: ({s(t)} K, {s(p)} Pa) inside SYN-001's domain")
    td = dew_t(z, p)
    claim(t > td, f"{label}: vapour above its dew point {mp.nstr(td, 12)} K")
    H = sum((ni * h_vap(c, t) for ni, c in zip(n, COMPONENTS, strict=False)), mpf(0))  # noqa: N806
    S = sum((ni * s_vap(c, t, p, ni / tot) for ni, c in zip(n, COMPONENTS, strict=False)), mpf(0))  # noqa: N806
    return {"H": H, "S": S, "m": mass(n), "h": H / mass(n), "T": t, "P": p}


def two_phase(n: tuple[Any, ...], t: Any, p: Any, label: str) -> dict[str, Any]:
    tot = sum(n, mpf(0))
    z = tuple(ni / tot for ni in n)
    claim(in_domain(t, p), f"{label}: inside SYN-001's domain")
    claim(bubble_t(z, p) < t < dew_t(z, p), f"{label}: between bubble and dew point")
    k = [k_value(c, t, p) for c in COMPONENTS]
    rr = lambda b: sum(zi * (ki - 1) / (1 + b * (ki - 1)) for zi, ki in zip(z, k, strict=False))  # noqa: E731
    beta = mp.findroot(rr, (mpf("1e-6"), 1 - mpf("1e-6")), solver="anderson")
    x = [zi / (1 + beta * (ki - 1)) for zi, ki in zip(z, k, strict=False)]
    y = [ki * xi for ki, xi in zip(k, x, strict=False)]
    nv = [beta * tot * yi for yi in y]
    nl = [ni - vi for ni, vi in zip(n, nv, strict=False)]
    H = sum(  # noqa: N806 (extensive H, the sheet's notation)
        (
            vi * h_vap(c, t) + li * h_liq(c, t, p)
            for vi, li, c in zip(nv, nl, COMPONENTS, strict=False)
        ),
        mpf(0),
    )
    return {
        "H": H,
        "m": mass(n),
        "h": H / mass(n),
        "T": t,
        "P": p,
        "beta": beta,
        "nV": nv,
        "nL": nl,
    }


def pure_b_two_phase(beta: Any) -> dict[str, Any]:
    """Pure B at P_r: T_sat = T_b,B = 360 K exactly (K_B(360 K, P_r) = 1); the lever rule in h."""
    claim(k_value("B", TB["B"], P_R) == 1, "K_B(360 K, P_r) = 1 exactly")
    hl, hv = h_liq("B", TB["B"], P_R), h_vap("B", TB["B"])
    return {"h": (hl + beta * (hv - hl)) / MW, "T": TB["B"], "beta": beta, "latent": (hv - hl) / MW}


def iapws_pump() -> dict[str, Any]:
    """Water, 300 K, 1e5 Pa -> 1e7 Pa, eta = 1: isentropic and incompressible work per kg (S05)."""
    sys.path.insert(0, str(HERE))
    import s05_reference as s05  # noqa: PLC0415  (50-digit IAPWS-95, imported unchanged)

    t0, p0, p1 = mpf(300), mpf(100000), mpf(10000000)
    inlet = s05.tp_values(t0, p0, mpf(996))
    ts = mp.findroot(lambda t: s05.tp_values(t, p1, mpf(1000), check=False)["s"] - inlet["s"], t0)
    out = s05.tp_values(ts, p1, mpf(1000))
    mw = s05.MOLAR_MASS
    w_isen = (out["h"] - inlet["h"]) / mw
    w_inc = inlet["v"] * (p1 - p0) / mw
    claim(
        w_inc - w_isen > mpf(10),
        "IAPWS-95 pump: incompressible exceeds isentropic work by > 10 J/kg",
    )
    return {"T_s": ts, "w_isentropic": w_isen, "w_incompressible": w_inc, "v_in": inlet["v"] / mw}


def build() -> dict[str, Any]:
    eq = (mpf(1), mpf(1), mpf(1))
    cases: dict[str, Any] = {}

    feed = liquid(eq, mpf(300), P_R, "FEED-1")
    claim(
        abs(feed["h"] + 298150) < mpf("1e-9"),
        "FEED-1 h = -298150 J/kg to 1e-9 J/kg (T°, M and v are doubles)",
    )
    cases["FEED-1"] = {"n": [1, 1, 1], "T": "300", "P": "1e5", "h": s(feed["h"])}

    # heater: T mode to 350 K (two-phase), the duty that gives it, and the liquid PI case
    out350 = two_phase(eq, mpf(350), P_R, "HTR-T outlet")
    q350 = out350["H"] - feed["H"]
    cases["HTR-T"] = {
        "T_spec": "350",
        "Q": s(q350),
        "h_out": s(out350["h"]),
        "beta": s(out350["beta"]),
        "nV": [s(v) for v in out350["nV"]],
        "Q_double": repr(float(q350)),
    }
    claim(
        abs(out350["beta"] - mpf("0.10136872342672776")) < mpf("1e-16"),
        "beta(350 K) = SYN-001 §3.1's",
    )
    for q, tag in ((6000, "HTR-L6000"), (3000, "HTR-L3000"), (0, "HTR-L0")):
        t_out = mpf(300) + mpf(q) / (3 * CP)
        o = liquid(eq, t_out, P_R, tag)
        claim(
            abs(o["h"] - feed["h"] - mpf(q) / feed["m"]) < mpf("1e-35"),
            f"{tag}: h_out = h_in + Q/m",
        )
        cases[tag] = {"Q": str(q), "T_out": s(t_out), "h_out": s(o["h"])}

    # valve: VLV-1 (liquid heats), VLV-2 (flashes), VLV-3 (ideal gas, T unchanged)
    n1 = (mpf("1.2"), mpf("0.9"), mpf("0.3"))
    v_in = liquid(n1, mpf(300), mpf(180000), "VLV-1 inlet")
    t_out = mpf(300) + VL * mpf(80000) / CP
    v_out = liquid(n1, t_out, P_R, "VLV-1 outlet")
    claim(abs(v_out["H"] - v_in["H"]) < mpf("1e-35"), "VLV-1 isenthalpic at T = 300 + v dP/c_p")
    cases["VLV-1"] = {"h": s(v_in["h"]), "T_out": s(t_out)}
    v2_in = liquid(eq, mpf(360), mpf(180000), "VLV-2 inlet")
    t2 = mp.findroot(lambda t: two_phase(eq, t, P_R, "VLV-2 trial")["H"] - v2_in["H"], 348)
    v2 = two_phase(eq, t2, P_R, "VLV-2 outlet")
    claim(
        abs(t2 - mpf("348.4998644192089")) < mpf("1e-12"), "VLV-2 T equals T05's registered value"
    )
    cases["VLV-2"] = {"h": s(v2_in["h"]), "T_out": s(t2), "beta": s(v2["beta"])}
    v3 = vapour(eq, mpf(420), mpf(150000), "VLV-3 inlet")
    vapour(eq, mpf(420), mpf(60000), "VLV-3 outlet")
    cases["VLV-3"] = {"h": s(v3["h"]), "T_out": "420"}

    # mixer: two subcooled liquids at P_r; L cancels component-wise, so T is the mole-weighted mean
    n2 = (mpf("0.2"), mpf("0.3"), mpf("0.5"))
    m_a, m_b = liquid(eq, mpf(300), P_R, "MIX-1 a"), liquid(n2, mpf(340), P_R, "MIX-1 b")
    nsum = tuple(a + b for a, b in zip(eq, n2, strict=False))
    m_o = liquid(nsum, mpf(310), P_R, "MIX-1 outlet")
    claim(
        abs(m_o["H"] - m_a["H"] - m_b["H"]) < mpf("1e-35"), "MIX-1: T = (3*300 + 1*340)/4 = 310 K"
    )
    cases["MIX-1"] = {"h_a": s(m_a["h"]), "h_b": s(m_b["h"]), "h_out": s(m_o["h"]), "T_out": "310"}

    # flash: pure B at P_r (pi = C + 1: T fixed, h decides beta) and the equimolar drum at 350 K
    for beta in (mpf("0.25"), mpf("0.5"), mpf("0.75")):
        pb = pure_b_two_phase(beta)
        cases[f"FLS-B{int(beta * 100)}"] = {"h": s(pb["h"]), "T": "360", "beta": s(beta)}
    claim(
        abs(pure_b_two_phase(mpf("0.25"))["latent"] - 300000) < mpf("1e-9"),
        "pure B: latent 3e5 J/kg at P_r",
    )

    # pump: PUMP-1 (both work models coincide on SYN-001) and IAPWS-95 water (they differ)
    w_s = sum(n1, mpf(0)) * VL * mpf(80000)
    claim(abs(w_s - mpf("19.2")) < mpf("1e-12"), "PMP-1 W_s = 19.2 W (v is a double)")
    cases["PMP-1"] = {
        "W_s": s(w_s),
        "W": s(w_s / mpf("0.75")),
        "T_out": s(mpf(300) + (w_s / mpf("0.75") - w_s) / (sum(n1, mpf(0)) * CP)),
    }
    cases["PMP-W"] = {k: s(v) for k, v in iapws_pump().items()}

    # compressor and turbine: ideal-gas vapour, T_s = T_in (P_out/P_in)^(R/c_p)
    for tag, t_in, p_in, p_out, eta in (
        ("CMP-1", mpf(380), mpf(60000), mpf(150000), mpf("0.8")),
        ("TRB-1", mpf(430), mpf(150000), mpf(60000), mpf("0.85")),
    ):
        inlet = vapour(eq, t_in, p_in, f"{tag} inlet")
        t_s = t_in * (p_out / p_in) ** (R / CP)
        isen = vapour(eq, t_s, p_out, f"{tag} isentropic state")
        claim(abs(isen["S"] - inlet["S"]) < mpf("1e-35"), f"{tag}: isentropic state has S_in")
        dh_s = isen["H"] - inlet["H"]
        w = dh_s / eta if tag == "CMP-1" else dh_s * eta
        t_out = t_in + w / (3 * CP)
        outlet = vapour(eq, t_out, p_out, f"{tag} outlet")
        cases[tag] = {
            "T_s": s(t_s),
            "W": s(w),
            "T_out": s(t_out),
            "h_in": s(inlet["h"]),
            "h_out": s(outlet["h"]),
            "S_in": s(inlet["S"]),
            "S_out": s(outlet["S"]),
        }
    # Q2.A12 (c): with s°(ig) = (200, 250, 300) J/(mol K) the reported S moves by sum n s° = 750 W/K
    cases["Q2.A12"] = {"S_shift_W_per_K": "750"}

    # heat_direction (Q5.A12): (donor in, donor out, receiver in, receiver out) in K, Q in W
    hd = {}
    for tag, (d_in, d_out, r_in) in {
        "HD-a": (340, 320, 300),
        "HD-b": (300, 290, 320),
        "HD-c": (310, 300, 310),
    }.items():
        q = 3 * CP * (d_in - d_out)
        r_out = r_in + q / (3 * CP)
        for t in (d_in, d_out, r_in, r_out):
            liquid(eq, mpf(t), P_R, f"{tag} at {t} K")
        hd[tag] = {
            "Q": s(q),
            "receiver_out": s(r_out),
            "value": s(min(r_in, r_out) - max(d_in, d_out)),
        }
    claim(
        mpf(hd["HD-a"]["value"]) < 0 < mpf(hd["HD-b"]["value"]) and mpf(hd["HD-c"]["value"]) == 0,
        "heat_direction: HD-a passes, HD-b fails, HD-c is the equal contact",
    )
    cases.update(hd)

    # distinctness: the three latent heats differ, so a permuted component index moves each liquid h
    claim(len({LAT[c] for c in COMPONENTS}) == 3, "L_A, L_B, L_C pairwise distinct")
    return {
        "generator": "docs/derivations/scripts/f6_std_seed_reference.py",
        "sheet": "docs/derivations/F6-std-seed.md",
        "units": {"h": "J/kg", "Q,W": "W", "T": "K", "P": "Pa", "S": "W/K", "n": "mol/s"},
        "cases": cases,
        "claims": CLAIMS,
    }


def encode(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode()


def main(argv: list[str]) -> int:
    data = encode(build())
    if "--check" in argv:
        same = OUT.exists() and OUT.read_bytes() == data
        print(f"f6_std_seed_reference: {'PASS' if same else 'FAIL'} ({len(CLAIMS)} claims)")
        return 0 if same else 1
    OUT.write_bytes(data)
    print(f"f6_std_seed_reference: wrote {OUT.name} ({len(CLAIMS)} claims)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
