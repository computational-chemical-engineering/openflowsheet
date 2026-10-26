"""Q2: pure-component and stream-level check of the SYN-001 mapping against the closed forms."""

import syn001_thermo as s
import thermosteam as tmo

thermo = s.make_thermo()
tmo.settings.set_thermo(thermo)
print(
    "thermo:",
    type(thermo).__name__,
    "Gamma",
    thermo.Gamma.__name__,
    "Phi",
    thermo.Phi.__name__,
    "PCF",
    thermo.PCF.__name__,
    "mixture",
    type(thermo.mixture).__name__,
    "excess",
    thermo.mixture.include_excess_energies,
)
worst = 0.0
for ID in s.COMPONENTS:
    c = thermo.chemicals[ID]
    print(
        ID,
        "Psat methods",
        c.Psat.all_methods,
        "Hvap",
        c.Hvap.all_methods,
        "Tc",
        c.Tc,
        "Pc",
        c.Pc,
        "T_ref",
        c.T_ref,
        "eos",
        type(c._eos).__name__,
    )
    for T in (310.0, 347.0, 385.0, 430.0):
        p = c.Psat(T)
        pe = s.psat_closed(ID, T)
        hl = c.H("l", T)
        hg = c.H("g", T)
        el = abs(hl - s.h_closed(ID, "l", T)) / max(abs(s.h_closed(ID, "l", T)), 1.0)
        eg = abs(hg - s.h_closed(ID, "g", T)) / abs(s.h_closed(ID, "g", T))
        ep = abs(p - pe) / pe
        worst = max(worst, el, eg, ep)
        print(
            f"  T={T}: Psat rel {ep:.2e}  hL {hl:.10f} (rel {el:.2e})  hV {hg:.10f} (rel {eg:.2e})"
        )
# Stream level: mixture enthalpy, K-values from a VLE at P_r, pressure dependence of H.
st = tmo.Stream("x", A=1.08, B=1.44, C=1.08, units="kmol/hr", T=350.0, P=s.P_R)  # 0.3/0.4/0.3 mol/s
for phase in ("l", "g"):
    st.phase = phase
    H_W = st.H / 3.6  # kJ/hr -> W
    H_exp = sum(
        n * s.h_closed(i, phase, 350.0) for i, n in zip("ABC", (0.3, 0.4, 0.3), strict=False)
    )
    st.P = 1.5e5
    H2 = st.H / 3.6
    st.P = s.P_R
    print(
        f"stream {phase}: H {H_W:.10f} W vs {H_exp:.10f} (rel "
        f"{abs(H_W - H_exp) / abs(H_exp):.2e}); "
        f"H at 1.5 bar - H at 1 bar = {H2 - H_W:.3e} W"
    )
st.vle(T=350.0, P=s.P_R)
y = st.imol["g"] / st.imol["g"].sum()
x = st.imol["l"] / st.imol["l"].sum()
Kexp = [s.psat_closed(i, 350.0) / s.P_R for i in "ABC"]
print(
    "VLE at 350 K, P_r: K",
    list(y / x),
    "rel err",
    [abs(a - b) / b for a, b in zip(y / x, Kexp, strict=False)],
    "vapour fraction",
    st.imol["g"].sum() / st.F_mol,
    "(SYN-001: 0.10136872342672776)",
)
print(f"WORST pure rel err {worst:.2e}")
# Independent Rachford-Rice for z = (0.3, 0.4, 0.3) at 350 K (bisection on the closed-form K).
z = (0.3, 0.4, 0.3)


def f(b):
    return sum(zi * (k - 1) / (1 + b * (k - 1)) for zi, k in zip(z, Kexp, strict=False))


lo, hi = 0.0, 1.0
for _ in range(200):
    mid = 0.5 * (lo + hi)
    lo, hi = (mid, hi) if f(mid) > 0 else (lo, mid)
print(f"independent RR beta {lo:.15f}; thermosteam {st.imol['g'].sum() / st.F_mol:.15f}")
