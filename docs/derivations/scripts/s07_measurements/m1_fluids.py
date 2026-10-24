"""S07 measurement 1: CoolProp 8.0.0 fluid facts for the L01 nine (scratch venv only)."""

import hashlib
import json

import CoolProp
import CoolProp.CoolProp

CP = CoolProp.CoolProp

FLUIDS = {
    "H2O": "Water",
    "CO2": "CarbonDioxide",
    "N2": "Nitrogen",
    "O2": "Oxygen",
    "Ar": "Argon",
    "CH4": "Methane",
    "C2H6": "Ethane",
    "C3H8": "n-Propane",
    "H2": "Hydrogen",
}
print("version", CoolProp.__version__, "gitrevision", CP.get_global_param_string("gitrevision"))
print("n_fluids", len(CP.get_global_param_string("FluidsList").split(",")))
out = {}
for cid, name in FLUIDS.items():
    s = CP.get_fluid_param_string(name, "JSON")
    d = json.loads(s)
    if isinstance(d, list):
        d = d[0]
    eos = d["EOS"]
    e0 = eos[0]
    a0 = sorted({t["type"] for t in e0["alpha0"]})
    ar = sorted({t["type"] for t in e0["alphar"]})
    st = e0["STATES"]
    red = st["reducing"]
    AS = CP.AbstractState("HEOS", name)
    facts = dict(
        n_eos=len(eos),
        alpha0=a0,
        alphar=ar,
        nterms_r=sum(len(t.get("n", [])) for t in e0["alphar"]),
        R=e0["gas_constant"],
        M=e0["molar_mass"],
        Tred=red["T"],
        rhored=red["rhomolar"],
        Tc=AS.T_critical(),
        pc=AS.p_critical(),
        rhoc=AS.rhomolar_critical(),
        Tt=AS.Ttriple(),
        Tmin=AS.Tmin(),
        Tmax=AS.Tmax(),
        pmax=AS.pmax(),
        ptriple=AS.trivial_keyed_output(CP.iP_triple),
        json_sha=hashlib.sha256(s.encode()).hexdigest()[:16],
        json_len=len(s),
        bibtex=e0.get("BibTeX_EOS", ""),
        aliases=d["INFO"].get("ALIASES", [])[:3],
    )
    out[cid] = facts
    print(cid, name, json.dumps(facts, sort_keys=True))
