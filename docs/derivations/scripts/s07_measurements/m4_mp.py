"""S07 measurement 4: CoolProp 8.0.0 Helmholtz partials vs a 30-digit mpmath closed form from the
same JSON."""

import json

import CoolProp.CoolProp
import mpmath as mp

CP = CoolProp.CoolProp

mp.mp.dps = 30
FL = [
    "Water",
    "CarbonDioxide",
    "Nitrogen",
    "Oxygen",
    "Argon",
    "Methane",
    "Ethane",
    "n-Propane",
    "Hydrogen",
]
R_ = [
    "alphar",
    "dalphar_dDelta",
    "d2alphar_dDelta2",
    "dalphar_dTau",
    "d2alphar_dTau2",
    "d2alphar_dDelta_dTau",
    "d3alphar_dDelta3",
    "d3alphar_dDelta2_dTau",
    "d3alphar_dDelta_dTau2",
    "d3alphar_dTau3",
]
Z_ = [n.replace("alphar", "alpha0") for n in R_]
ORD = [
    (0, 0),
    (1, 0),
    (2, 0),
    (0, 1),
    (0, 2),
    (1, 1),
    (3, 0),
    (2, 1),
    (1, 2),
    (0, 3),
]  # (k_delta, k_tau)


def mpf(x):
    return mp.mpf(repr(x)) if isinstance(x, float) else mp.mpf(x)


def alpha0(terms, tau, delta):
    s = mp.mpf(0)
    for t in terms:
        k = t["type"]
        if k == "IdealGasHelmholtzLead":
            s += mp.log(delta) + mpf(t["a1"]) + mpf(t["a2"]) * tau
        elif k == "IdealGasHelmholtzEnthalpyEntropyOffset":
            s += mpf(t["a1"]) + mpf(t["a2"]) * tau
        elif k == "IdealGasHelmholtzLogTau":
            s += mpf(t["a"]) * mp.log(tau)
        elif k == "IdealGasHelmholtzPlanckEinstein":
            s += sum(
                mpf(n) * mp.log(1 - mp.exp(-mpf(th) * tau))
                for n, th in zip(t["n"], t["t"], strict=False)
            )
        elif k == "IdealGasHelmholtzPlanckEinsteinFunctionT":
            s += sum(
                mpf(n) * mp.log(1 - mp.exp(-mpf(v) / mpf(t["Tcrit"]) * tau))
                for n, v in zip(t["n"], t["v"], strict=False)
            )
        elif k == "IdealGasHelmholtzPower":
            s += sum(mpf(n) * tau ** mpf(e) for n, e in zip(t["n"], t["t"], strict=False))
        else:
            raise SystemExit("unhandled " + k)
    return s


def alphar(terms, tau, delta):
    s = mp.mpf(0)
    for t in terms:
        k = t["type"]
        if k == "ResidualHelmholtzPower":
            for n, d, e, ell in zip(t["n"], t["d"], t["t"], t["l"], strict=False):
                f = mpf(n) * delta ** mpf(d) * tau ** mpf(e)
                s += f * (mp.exp(-(delta ** mpf(ell))) if ell > 0 else 1)
        elif k == "ResidualHelmholtzGaussian":
            for n, d, e, eta, eps, be, ga in zip(
                t["n"], t["d"], t["t"], t["eta"], t["epsilon"], t["beta"], t["gamma"], strict=False
            ):
                s += (
                    mpf(n)
                    * delta ** mpf(d)
                    * tau ** mpf(e)
                    * mp.exp(-mpf(eta) * (delta - mpf(eps)) ** 2 - mpf(be) * (tau - mpf(ga)) ** 2)
                )
        elif k == "ResidualHelmholtzNonAnalytic":
            for n, a, b, be, a_na, b_na, c_na, d_na in zip(
                *(t[x] for x in ("n", "a", "b", "beta", "A", "B", "C", "D")), strict=False
            ):
                q = (delta - 1) ** 2
                th = (1 - tau) + mpf(a_na) * q ** (1 / (2 * mpf(be)))
                big_delta = th**2 + mpf(b_na) * q ** mpf(a)
                psi = mp.exp(-mpf(c_na) * q - mpf(d_na) * (tau - 1) ** 2)
                s += mpf(n) * big_delta ** mpf(b) * delta * psi
        else:
            raise SystemExit("unhandled " + k)
    return s


summary = {}
for fl in FL:
    d = json.loads(CP.get_fluid_param_string(fl, "JSON"))
    d = d[0] if isinstance(d, list) else d
    e = d["EOS"][0]
    red = e["STATES"]["reducing"]
    Tr, rr = red["T"], red["rhomolar"]
    a = CP.AbstractState("HEOS", fl)
    a.specify_phase(CP.iphase_gas)
    worst = [0.0, 0.0]
    where = [None, None]
    for T_over, dl in [(1.5, 0.3), (0.8, 2.4), (0.95, 0.02), (2.5, 1.1), (1.1, 1.6)]:
        T = T_over * Tr
        a.update(CP.DmolarT_INPUTS, dl * rr, T)
        tau, delta = mpf(a.tau()), mpf(a.delta())
        for part, (fn, terms, names) in enumerate(
            [(alpha0, e["alpha0"], Z_), (alphar, e["alphar"], R_)]
        ):
            for (kd, kt), nm in zip(ORD, names, strict=False):
                ref = mp.diff(
                    lambda dd, tt, fn=fn, terms=terms: fn(terms, tt, dd), (delta, tau), (kd, kt)
                )
                got = getattr(a, nm)()
                err = float(abs(mpf(got) - ref) / max(abs(ref), 1))
                if err > worst[part]:
                    worst[part], where[part] = err, (T_over, dl, nm)
    summary[fl] = worst
    print(fl, f"alpha0 worst {worst[0]:.1e}", where[0], f"| alphar worst {worst[1]:.1e}", where[1])
