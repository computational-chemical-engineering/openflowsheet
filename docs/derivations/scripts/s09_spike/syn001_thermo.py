"""SYN-001 (docs/derivations/SYN-001.md §1-3) as thermosteam user chemicals, no database.

At P = P_r the SYN-001 closed forms are
    K_i   = exp[(L_i/R)(1/T_b,i - 1/T)]           (Poynting term vanishes)
    h_i^L = c_p (T - T_r)
    h_i^V = c_p (T - T_r) + L_i
Here Psat_i(T) = P_r exp[(L_i/R)(1/T_b,i - 1/T)], so K = gamma*Psat*PCF/(phi*P) = Psat/P
under IdealThermo (ideal gamma, ideal phi, mock Poynting). Enthalpy: phase_ref 'l', T_ref = 300 K,
constant Cn = c_p in both phases, Hvap(T) = L_i constant, Tb = T_b,i, so thermosteam's
EnthalpyRefLiquid gives H_g(T) = c_p (T_b - T_r) + L_i + c_p (T - T_b) = c_p (T - T_r) + L_i.

"""

import math

import thermosteam as tmo

R = 8.31446261815324
T_R = 300.0
P_R = 1.0e5
CP = 100.0
V_L = 1.0e-4
MW_G_PER_MOL = 100.0  # 0.100 kg/mol
COMPONENTS = {"A": (320.0, 25000.0), "B": (360.0, 30000.0), "C": (400.0, 35000.0)}


def psat_closed(chem_id, temp):
    t_b, lat = COMPONENTS[chem_id]
    return P_R * math.exp((lat / R) * (1.0 / t_b - 1.0 / temp))


def h_closed(chem_id, phase, temp):
    _, lat = COMPONENTS[chem_id]
    return CP * (temp - T_R) + (lat if phase == "g" else 0.0)


class SynChemical(tmo.Chemical):
    """Chemical with SYN-001's reference temperature.

    (thermosteam's T_ref is a read-only class attribute.)
    """

    __slots__ = ()
    T_ref = T_R
    P_ref = P_R


def make_chemical(chem_id):
    t_b, lat = COMPONENTS[chem_id]
    chem = SynChemical.blank(chem_id, phase_ref="l", MW=MW_G_PER_MOL, Tb=t_b)
    chem.Psat.add_method(
        f=lambda t, t_b=t_b, lat=lat: P_R * math.exp((lat / R) * (1.0 / t_b - 1.0 / t)),
        Tmin=200.0,
        Tmax=600.0,
    )
    chem.Hvap.add_method(f=lambda t, lat=lat: lat, Tmin=200.0, Tmax=600.0)
    chem.Cn.l.add_method(CP)
    chem.Cn.g.add_method(CP)
    chem.V.l.add_method(V_L)
    chem.reset_free_energies()
    return chem


def make_thermo():
    chems = tmo.Chemicals([make_chemical(i) for i in COMPONENTS])
    # tmo.IdealThermo(chems) without a mixture calls Mixture.from_chemicals, which does not exist in
    # thermosteam 0.54.2 (AttributeError); the IdealMixture is passed explicitly instead.
    chems.compile(skip_checks=True)
    mixture = tmo.IdealMixture.from_chemicals(chems)
    thermo = tmo.IdealThermo(chems, mixture=mixture, skip_checks=True)
    return thermo
