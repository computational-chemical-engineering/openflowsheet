"""S07 measurement 5 ("m-melt"): CoolProp 8.0.0 melting lines and PropsSI's own refusal below
T_melt(p)."""

import CoolProp.CoolProp

CP = CoolProp.CoolProp

for f in [
    "Water",
    "CarbonDioxide",
    "Nitrogen",
    "Oxygen",
    "Argon",
    "Methane",
    "Ethane",
    "n-Propane",
    "Hydrogen",
]:
    a = CP.AbstractState("HEOS", f)
    p_hi = min(a.pmax(), 1.0e8)
    try:
        t_m = f"{a.melting_line(CP.iT, CP.iP, p_hi):.2f}"
    except Exception as e:  # noqa: BLE001 - the message is the measurement
        t_m = "raises: " + str(e)[:70]
    try:
        CP.PropsSI("D", "T", a.Ttriple() * 1.1, "P", 1e8, f)
        props = "ok"
    except Exception as e:  # noqa: BLE001
        props = "raises: " + str(e)[:60]
    print(f, "P_hi", p_hi, "T_m(P_hi)", t_m, "| PropsSI(1.1 T_t, 100 MPa)", props)
