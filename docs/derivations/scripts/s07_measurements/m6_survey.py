"""S07 measurement 6 (Amendment 1): survey of every CoolProp 8.0.0 fluid (scratch venv only).

Prints one JSON line per fluid with the facts the Amendment 1 selection rule reads, and writes them to argv[1].
"""

import json
import sys

import CoolProp
import CoolProp.CoolProp as CP

names = sorted(CP.get_global_param_string("FluidsList").split(","))
out = {
    "version": CoolProp.__version__,
    "gitrevision": CP.get_global_param_string("gitrevision"),
    "n_fluids": len(names),
    "fluids": {},
}
for f in names:
    d = json.loads(CP.get_fluid_param_string(f, "JSON"))
    d = d[0] if isinstance(d, list) else d
    e = d["EOS"][0]
    a = CP.AbstractState("HEOS", f)
    p_hi = min(a.pmax(), 1.0e8)
    melt = a.has_melting_line()
    rec = dict(
        cas=d["INFO"].get("CAS", ""),
        n_eos=len(d["EOS"]),
        bibtex_all=[x.get("BibTeX_EOS", "") for x in d["EOS"]],
        pseudo_pure=bool(e["pseudo_pure"]),
        alpha0=sorted({t["type"] for t in e["alpha0"]}),
        alphar=sorted({t["type"] for t in e["alphar"]}),
        n_terms_r=sum(len(t.get("n", [])) for t in e["alphar"]),
        R=e["gas_constant"],
        M=e["molar_mass"],
        Tred=e["STATES"]["reducing"]["T"],
        rhored=e["STATES"]["reducing"]["rhomolar"],
        Tc=a.T_critical(),
        pc=a.p_critical(),
        Tt=a.Ttriple(),
        pt=a.trivial_keyed_output(CP.iP_triple),
        Tmin=a.Tmin(),
        Tmax=a.Tmax(),
        pmax=a.pmax(),
        p_hi=p_hi,
        has_melting_line=melt,
        has_superancillary="SUPERANCILLARY" in e,
        json_keys=sorted(d.keys()),
    )
    if melt:
        lim = {}
        for k, key in (
            ("T_min", CP.iT_min),
            ("T_max", CP.iT_max),
            ("p_min", CP.iP_min),
            ("p_max", CP.iP_max),
        ):
            try:
                lim[k] = a.melting_line(key, -1, -1)
            except Exception as ex:  # noqa: BLE001 - the message is the measurement
                lim[k] = "raises: " + str(ex)[:60]
        rec["melt_limits"] = lim
        try:
            rec["Tm_p_hi"] = a.melting_line(CP.iT, CP.iP, p_hi)
        except Exception as ex:  # noqa: BLE001
            rec["Tm_p_hi"] = "raises: " + str(ex)[:80]
    out["fluids"][f] = rec
json.dump(out, open(sys.argv[1], "w"), indent=1, sort_keys=True)
print("version", out["version"], out["gitrevision"], "n", len(names))
