"""S09 WO-S09-2: SYN-001 in BioSTEAM (`docs/derivations/S09-spec.md` §4.2) and its readback (§4.3).

§4.2's registered definition: three blank thermosteam chemicals whose pure-component data are
SYN-001's closed forms, entered through the tool's documented `add_method` hooks, with the tool's
default enthalpy datum (`Chemical.T_ref` = 298.15 K, no subclass) and an `IdealThermo` with an
explicit `IdealMixture` (without it `IdealThermo(chemicals)` raises `AttributeError` in thermosteam
0.54.2, a tool defect that is recorded, not patched). The constants are imported from T06's pinned
`t06_fixtures.py` (S03 §5.1 row 1, generator claim C4b), never re-entered.

§4.3's readback runs in each case's process, before any solve, on the thermo object that case uses.
A failed item is rule 2c `semantics: property_mapping(<item>)`.

Runs only under `.venv-biosteam/bin/python` (it imports thermosteam). Reads no file of this project
but `s09_cases.json` (through the caller) and imports nothing of it but `t06_fixtures`.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any

import t06_fixtures as fx
import thermosteam as tmo

# The pin of `t06_fixtures.py` (s09_cases.json -> blindness.exempt_modules_sha256; S03 §17.6).
T06_FIXTURES_SHA256 = "c6320cc81ea4bf08c36f7d7b5aca19180c2109fd66e4e23c84476d35286ba61f"
COMPONENTS = ("A", "B", "C")
PSAT_TMIN_K = 200.0
PSAT_TMAX_K = 600.0
MW_G_PER_MOL = 1000.0  # thermosteam's MW is g/mol; T06's MW is kg/mol


def check_fixture_pin() -> str:
    """The SHA-256 of the imported `t06_fixtures.py`; raises if it is not the pinned file."""
    got = hashlib.sha256(open(fx.__file__, "rb").read()).hexdigest()
    if got != T06_FIXTURES_SHA256:
        raise RuntimeError(f"t06_fixtures.py SHA-256 {got} is not the pinned {T06_FIXTURES_SHA256}")
    return got


def _chemical(cid: str, hvap_j_per_mol: float) -> Any:
    """§4.2's rows Chemical, Psat, Hvap, heat capacity, liquid volume and finish, for one ID."""
    t_b = fx.T_BOIL[cid]
    lat = fx.L_VAP[cid]
    chem = tmo.Chemical.blank(cid, phase_ref="l", MW=MW_G_PER_MOL * fx.MW, Tb=t_b)
    chem.Psat.add_method(
        f=lambda t, t_b=t_b, lat=lat: fx.P_REF * math.exp((lat / fx.R_GAS) * (1.0 / t_b - 1.0 / t)),
        Tmin=PSAT_TMIN_K,
        Tmax=PSAT_TMAX_K,
    )
    chem.Hvap.add_method(f=lambda t, h=hvap_j_per_mol: h, Tmin=PSAT_TMIN_K, Tmax=PSAT_TMAX_K)
    chem.Cn.l.add_method(fx.CP)
    chem.Cn.g.add_method(fx.CP)
    chem.V.l.add_method(fx.V_LIQ)
    chem.reset_free_energies()
    return chem


def hvap_values(variant: str, cases9: dict[str, Any]) -> dict[str, float]:
    """The constant latent heat entered as `Hvap` per component: SYN-001's L_i, or PC-LB's (§7)."""
    if variant == "SYN-001":
        return {c: fx.L_VAP[c] for c in COMPONENTS}
    if variant == "PC-LB":
        vals = cases9["controls"]["PC-LB"]["Hvap_J_per_mol_PC-LB"]
        return {c: float(v) for c, v in zip(COMPONENTS, vals, strict=True)}
    raise ValueError(f"unknown property variant {variant!r}")


def build_thermo(hvaps: dict[str, float]) -> tuple[Any, Any]:
    """§4.2's Chemicals and IdealThermo with the given latent heats: (chemicals, thermo)."""
    chems = tmo.Chemicals([_chemical(c, hvaps[c]) for c in COMPONENTS])
    chems.compile(skip_checks=True)
    thermo = tmo.IdealThermo(
        chems, mixture=tmo.IdealMixture.from_chemicals(chems), skip_checks=True
    )
    return chems, thermo


def readback(
    chems: Any, thermo: Any, hvaps: dict[str, float], cases9: dict[str, Any]
) -> dict[str, Any]:
    """§4.3's checks on the thermo object the case uses (set as the tool's global thermo)."""
    rb = cases9["tool_settings"]["BioSTEAM"]["readback"]
    temps = [float(t) for t in rb["temperatures_K"]]
    psat_rel = float(rb["Psat_relative"])
    lat_rel = float(rb["latent_relative"])
    cp_abs = float(rb["cp_J_per_mol"])
    offset = float(rb["datum_offset_J_per_mol"])
    offset_abs = float(rb["datum_offset_abs_J_per_mol"])
    items: dict[str, Any] = {}

    psat: dict[str, Any] = {}
    for c in COMPONENTS:
        rows = []
        for t, ref in zip(temps, rb["Psat_Pa"][c], strict=True):
            got = float(chems[c].Psat(t))
            refv = float(ref)
            rows.append({"T_K": t, "tool": got, "registered": ref, "rel": abs(got - refv) / refv})
        psat[c] = rows
    worst = max(r["rel"] for rows in psat.values() for r in rows)
    items["Psat"] = {
        "values": psat,
        "max": worst,
        "threshold": psat_rel,
        "passes": worst <= psat_rel,
    }

    lat: dict[str, Any] = {}
    for c in COMPONENTS:
        rows = []
        for t in temps:
            d = chems[c].H("g", t) - chems[c].H("l", t) - hvaps[c]
            rows.append({"T_K": t, "hV_minus_hL_minus_Hvap": d, "rel": abs(d) / hvaps[c]})
        lat[c] = rows
    worst = max(r["rel"] for rows in lat.values() for r in rows)
    items["latent"] = {
        "Hvap_J_per_mol": hvaps,
        "values": lat,
        "max": worst,
        "threshold": lat_rel,
        "passes": worst <= lat_rel,
    }

    cps: dict[str, Any] = {}
    for c in COMPONENTS:
        rows = []
        for t1, t2 in zip(temps[:-1], temps[1:], strict=True):
            d = (chems[c].H("l", t2) - chems[c].H("l", t1)) - fx.CP * (t2 - t1)
            rows.append({"T1_K": t1, "T2_K": t2, "residual_J_per_mol": d})
        cps[c] = rows
    worst = max(abs(r["residual_J_per_mol"]) for rows in cps.values() for r in rows)
    items["cp"] = {"values": cps, "max": worst, "threshold": cp_abs, "passes": worst <= cp_abs}

    dat: dict[str, Any] = {}
    for c in COMPONENTS:
        dat[c] = [
            {"T_K": t, "hL_minus_cp_T_minus_T_r": chems[c].H("l", t) - fx.CP * (t - fx.T_REF)}
            for t in temps
        ]
    worst = max(abs(r["hL_minus_cp_T_minus_T_r"] - offset) for rows in dat.values() for r in rows)
    items["datum"] = {
        "values": dat,
        "T_r_K": fx.T_REF,
        "T_ref_tool_K": tmo.Chemical.T_ref,
        "expected_offset_J_per_mol": offset,
        "max_abs_deviation": worst,
        "threshold": offset_abs,
        "passes": worst <= offset_abs,
    }

    stream = tmo.Stream(
        None, A=1.0, B=1.0, C=1.0, units="kmol/hr", T=temps[1], P=fx.P_REF, phase="l", thermo=thermo
    )
    h1 = stream.H
    stream.P = 1.5 * fx.P_REF
    h2 = stream.H
    items["liquid_pressure_dependence"] = {
        "stream": "liquid A = B = C = 1 kmol/h",
        "T_K": temps[1],
        "H_at_1.5P_r_minus_H_at_P_r_kJ_per_h": h2 - h1,
        "passes": h2 - h1 == 0.0,
    }

    methods = {
        c: {
            prop: {
                "method": getattr(chems[c], prop).method,
                "all_methods": sorted(getattr(chems[c], prop).all_methods),
            }
            for prop in ("Psat", "Hvap")
        }
        for c in COMPONENTS
    }
    items["methods"] = {
        "values": methods,
        "passes": all(
            m["method"] == "USER_METHOD" and m["all_methods"] == ["USER_METHOD"]
            for per in methods.values()
            for m in per.values()
        ),
    }

    expected = rb["thermo_classes"]
    got_classes = {
        "Gamma": type(thermo.Gamma).__name__
        if not isinstance(thermo.Gamma, type)
        else thermo.Gamma.__name__,
        "Phi": type(thermo.Phi).__name__
        if not isinstance(thermo.Phi, type)
        else thermo.Phi.__name__,
        "PCF": type(thermo.PCF).__name__
        if not isinstance(thermo.PCF, type)
        else thermo.PCF.__name__,
        "mixture": type(thermo.mixture).__name__,
        "include_excess_energies": bool(thermo.mixture.include_excess_energies),
    }
    items["thermo_classes"] = {
        "values": got_classes,
        "expected": expected,
        "passes": got_classes == expected,
    }
    failed = [k for k, v in items.items() if not v["passes"]]
    return {"items": items, "failed": failed, "passes": not failed}


def property_package(chems: Any, thermo: Any) -> dict[str, Any]:
    """Q-X1: the thermo classes and each chemical's active methods, read from the objects."""
    per = {}
    for c in COMPONENTS:
        chem = chems[c]
        per[c] = {
            "MW_g_per_mol": chem.MW,
            "Tb_K": chem.Tb,
            "phase_ref": chem.phase_ref,
            "Psat_method": chem.Psat.method,
            "Hvap_method": chem.Hvap.method,
            "Cn_l_method": str(chem.Cn.l.method),
            "Cn_g_method": str(chem.Cn.g.method),
            "V_l_method": str(chem.V.l.method),
        }
    return {
        "thermo_class": type(thermo).__name__,
        "chemicals": per,
        "Chemical_T_ref_K": tmo.Chemical.T_ref,
        "t06_fixtures_sha256": check_fixture_pin(),
        "constants": {
            "T_BOIL_K": fx.T_BOIL,
            "L_VAP_J_per_mol": fx.L_VAP,
            "CP_J_per_mol_K": fx.CP,
            "V_LIQ_m3_per_mol": fx.V_LIQ,
            "MW_kg_per_mol": fx.MW,
            "P_REF_Pa": fx.P_REF,
            "R_GAS_J_per_mol_K": fx.R_GAS,
        },
    }
