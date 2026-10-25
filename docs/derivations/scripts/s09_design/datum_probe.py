"""S09 design probe (NOT evidence): SYN-001 pure components in thermosteam with the tool's default
datum (Chemical.T_ref = 298.15 K, no subclass). No column is run.

Run with the BioSTEAM environment's interpreter: <venv>/bin/python -I datum_probe.py
"""

import math
import warnings

warnings.filterwarnings("ignore")
import thermosteam as tmo  # noqa: E402

R = 8.31446261815324
P_R = 1e5
CP = 100.0
COMP = {"A": (320.0, 25000.0), "B": (360.0, 30000.0), "C": (400.0, 35000.0)}


def chem(cid, cls):
    t_b, lat = COMP[cid]
    c = cls.blank(cid, phase_ref="l", MW=100.0, Tb=t_b)
    c.Psat.add_method(
        f=lambda t, t_b=t_b, lat=lat: P_R * math.exp((lat / R) * (1.0 / t_b - 1.0 / t)),
        Tmin=200.0,
        Tmax=600.0,
    )
    c.Hvap.add_method(f=lambda t, lat=lat: lat, Tmin=200.0, Tmax=600.0)
    c.Cn.l.add_method(CP)
    c.Cn.g.add_method(CP)
    c.V.l.add_method(1e-4)
    c.reset_free_energies()
    return c


print("default T_ref", tmo.Chemical.T_ref, "P_ref", getattr(tmo.Chemical, "P_ref", None))
for cid in COMP:
    c = chem(cid, tmo.Chemical)
    for T in (310.0, 347.0, 385.0, 430.0):
        hl, hg = c.H("l", T), c.H("g", T)
        print(
            cid,
            T,
            "hl-cp(T-Tref)=%.3e" % (hl - CP * (T - c.T_ref)),
            "hg-hl-L=%.3e" % (hg - hl - COMP[cid][1]),
            "hl-SYN=%.15g" % (hl - CP * (T - 300.0)),
        )
chems = tmo.Chemicals([chem(i, tmo.Chemical) for i in COMP])
chems.compile(skip_checks=True)
th = tmo.IdealThermo(chems, mixture=tmo.IdealMixture.from_chemicals(chems), skip_checks=True)
tmo.settings.set_thermo(th)
s = tmo.Stream("x", A=1.08, B=1.44, C=1.08, units="kmol/hr", T=350.0, P=P_R, phase="l")
h1 = s.H
s.P = 1.5e5
h2 = s.H
print("liquid stream H(1.5 bar)-H(1 bar) kJ/h:", h2 - h1)
