"""S07 measurement 7 (Amendment 1): m4 extended to every non-pseudo-pure CoolProp 8.0.0 fluid and
all term types.

30-digit mpmath closed forms of EOS[0] (the EOS HEOS uses), differentiated numerically, against
CoolProp's twenty partials at five (T/T_red, delta) points. Writes argv[1] (JSON) and prints one
line per fluid. Scratch venv only.
"""

import json
import sys
from multiprocessing import Pool

import CoolProp.CoolProp
import mpmath as mp

CP = CoolProp.CoolProp

mp.mp.dps = 30
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
ORD = [(0, 0), (1, 0), (2, 0), (0, 1), (0, 2), (1, 1), (3, 0), (2, 1), (1, 2), (0, 3)]
POINTS = [(1.5, 0.3), (0.8, 2.4), (0.95, 0.02), (2.5, 1.1), (1.1, 1.6)]


def mpf(x):
    return mp.mpf(repr(x)) if isinstance(x, float) else mp.mpf(x)


def cp0_integral(f_cp, f_int_cp, f_int_cp_over_t, temp, t_zero):
    """alpha contribution of a cp0/R term: (1/T) int_T0^T cp dT - int_T0^T cp/T dT (closed-form
    antiderivatives)."""
    return (f_int_cp(temp) - f_int_cp(t_zero)) / temp - (
        f_int_cp_over_t(temp) - f_int_cp_over_t(t_zero)
    )


def alpha0(terms, tau, delta, t_red):
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
        elif k == "IdealGasHelmholtzPlanckEinsteinGeneralized":
            s += sum(
                mpf(n) * mp.log(mpf(c) + mpf(d) * mp.exp(mpf(th) * tau))
                for n, th, c, d in zip(t["n"], t["t"], t["c"], t["d"], strict=False)
            )
        elif k == "IdealGasHelmholtzPower":
            s += sum(mpf(n) * tau ** mpf(e) for n, e in zip(t["n"], t["t"], strict=False))
        elif k in (
            "IdealGasHelmholtzCP0PolyT",
            "IdealGasHelmholtzCP0Constant",
            "IdealGasHelmholtzCP0AlyLee",
        ):
            t_crit, t_zero = mpf(t["Tc"]), mpf(t["T0"])
            temp = t_crit / tau
            if k == "IdealGasHelmholtzCP0Constant":
                pairs = [(mpf(t["cp_over_R"]), mp.mpf(0))]
            elif k == "IdealGasHelmholtzCP0PolyT":
                pairs = [(mpf(c), mpf(e)) for c, e in zip(t["c"], t["t"], strict=False)]
            else:
                pairs = [(mpf(t["c"][0]), mp.mpf(0))]
            for c, e in pairs:
                if e == 0:
                    s += cp0_integral(
                        None, lambda x, c=c: c * x, lambda x, c=c: c * mp.log(x), temp, t_zero
                    )
                elif e == -1:
                    s += cp0_integral(
                        None, lambda x, c=c: c * mp.log(x), lambda x, c=c: -c / x, temp, t_zero
                    )
                else:
                    s += cp0_integral(
                        None,
                        lambda x, c=c, e=e: c * x ** (e + 1) / (e + 1),
                        lambda x, c=c, e=e: c * x**e / e,
                        temp,
                        t_zero,
                    )
            if k == "IdealGasHelmholtzCP0AlyLee":
                c = [mpf(x) for x in t["c"]]
                # c1 (u/sinh u)^2, u = c2/T:  int cp dT = c1 c2 coth(c2/T);
                # int cp/T dT = c1 (u coth u - ln sinh u)
                s += cp0_integral(
                    None,
                    lambda x, c=c: c[1] * c[2] * mp.coth(c[2] / x),
                    lambda x, c=c: c[1]
                    * ((c[2] / x) * mp.coth(c[2] / x) - mp.log(mp.sinh(c[2] / x))),
                    temp,
                    t_zero,
                )
                # c3 (u/cosh u)^2, u = c4/T:  int cp dT = -c3 c4 tanh(c4/T);
                # int cp/T dT = -c3 (u tanh u - ln cosh u)
                s += cp0_integral(
                    None,
                    lambda x, c=c: -c[3] * c[4] * mp.tanh(c[4] / x),
                    lambda x, c=c: -c[3]
                    * ((c[4] / x) * mp.tanh(c[4] / x) - mp.log(mp.cosh(c[4] / x))),
                    temp,
                    t_zero,
                )
        else:
            raise RuntimeError("unhandled alpha0 " + k)
    return s


def alphar(terms, tau, delta):
    s = mp.mpf(0)
    for t in terms:
        k = t["type"]
        if k == "ResidualHelmholtzPower":
            for n, d, e, ell in zip(t["n"], t["d"], t["t"], t["l"], strict=False):
                f = mpf(n) * delta ** mpf(d) * tau ** mpf(e)
                s += f * (mp.exp(-(delta ** mpf(ell))) if ell > 0 else 1)
        elif k == "ResidualHelmholtzExponential":
            for n, d, e, g, ell in zip(t["n"], t["d"], t["t"], t["g"], t["l"], strict=False):
                s += mpf(n) * delta ** mpf(d) * tau ** mpf(e) * mp.exp(-mpf(g) * delta ** mpf(ell))
        elif k == "ResidualHelmholtzLemmon2005":
            for n, d, e, ell, m in zip(t["n"], t["d"], t["t"], t["l"], t["m"], strict=False):
                f = mpf(n) * delta ** mpf(d) * tau ** mpf(e)
                f *= mp.exp(-(delta ** mpf(ell))) if ell > 0 else 1
                f *= mp.exp(-(tau ** mpf(m))) if m > 0 else 1
                s += f
        elif k == "ResidualHelmholtzDoubleExponential":
            for n, d, e, gd, ld, gt, lt in zip(
                *(t[x] for x in ("n", "d", "t", "gd", "ld", "gt", "lt")), strict=False
            ):
                s += (
                    mpf(n)
                    * delta ** mpf(d)
                    * tau ** mpf(e)
                    * mp.exp(-mpf(gd) * delta ** mpf(ld) - mpf(gt) * tau ** mpf(lt))
                )
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
        elif k == "ResidualHelmholtzGaoB":
            for n, d, e, eta, eps, be, ga, b in zip(
                *(t[x] for x in ("n", "d", "t", "eta", "epsilon", "beta", "gamma", "b")),
                strict=False,
            ):
                s += (
                    mpf(n)
                    * delta ** mpf(d)
                    * tau ** mpf(e)
                    * mp.exp(
                        mpf(eta) * (delta - mpf(eps)) ** 2
                        + 1 / (mpf(be) * (tau - mpf(ga)) ** 2 + mpf(b))
                    )
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
            raise RuntimeError("unhandled alphar " + k)
    return s


def one(fl):
    d = json.loads(CP.get_fluid_param_string(fl, "JSON"))
    d = d[0] if isinstance(d, list) else d
    e = d["EOS"][0]
    if e["pseudo_pure"]:
        return fl, None
    red = e["STATES"]["reducing"]
    t_red, rr = red["T"], red["rhomolar"]
    a = CP.AbstractState("HEOS", fl)
    a.specify_phase(CP.iphase_gas)
    worst = [0.0, 0.0]
    where = [None, None]
    by_order = {"a0_le2": 0.0, "a0_3": 0.0, "ar_le2": 0.0, "ar_3": 0.0}
    for t_over, dl in POINTS:
        a.update(CP.DmolarT_INPUTS, dl * rr, t_over * t_red)
        tau, delta = mpf(a.tau()), mpf(a.delta())
        for part, (fn, names) in enumerate(
            [
                (lambda dd, tt: alpha0(e["alpha0"], tt, dd, t_red), Z_),
                (lambda dd, tt: alphar(e["alphar"], tt, dd), R_),
            ]
        ):
            for (kd, kt), nm in zip(ORD, names, strict=False):
                ref = mp.diff(fn, (delta, tau), (kd, kt))
                got = getattr(a, nm)()
                err = float(abs(mpf(got) - ref) / max(abs(ref), 1))
                key = ("a0_" if part == 0 else "ar_") + ("3" if kd + kt == 3 else "le2")
                by_order[key] = max(by_order[key], err)
                if err > worst[part]:
                    worst[part], where[part] = err, [t_over, dl, nm]
    return fl, {
        "alpha0": worst[0],
        "alpha0_at": where[0],
        "alphar": worst[1],
        "alphar_at": where[1],
        **by_order,
    }


if __name__ == "__main__":
    names = sorted(CP.get_global_param_string("FluidsList").split(","))
    with Pool(40) as p:
        res = dict(p.map(one, names, chunksize=1))
    res = {k: v for k, v in res.items() if v is not None}
    json.dump(res, open(sys.argv[1], "w"), indent=1, sort_keys=True)
    for k, v in sorted(res.items(), key=lambda kv: -max(kv[1]["alpha0"], kv[1]["alphar"])):
        print(
            f"{k:20s} a0 {v['alpha0']:.1e} {v['alpha0_at']}  ar {v['alphar']:.1e} {v['alphar_at']}"
        )
