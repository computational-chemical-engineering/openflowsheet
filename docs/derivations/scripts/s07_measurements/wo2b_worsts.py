"""WO-S07-2b record: per tier-B fluid, the measured worsts of A03, A04, A05, A08, A09, A10, A11 and
the A17 floor, with the provider's saturation at {T_lo, T_mid, T_sigma_max} (spec §16.11, §16.15,
Q-A1-5).

A record, not a gate: `tests/test_s07_broad.py` is the gate. Run from the repository root with
CoolProp 8.0.0 and `PYTHONPATH=src:.`; writes argv[1] (JSON) and prints the worsts.
"""

import json
import sys
from typing import Any

sys.path.insert(0, "tests")

import test_s07_broad as b  # noqa: E402
from test_s07_coolprop import value_bound  # noqa: E402

from openflowsheet.thermo import coolprop_heos as cph  # noqa: E402


def jet_worst(cid: str, slots: range) -> float:
    worst = 0.0
    for state in b.FLUIDS[cid]["phi_states"].values():
        ideal, residual = cph.helmholtz_jet(cid, state["T"], state["rho"])
        got = list(ideal) + list(residual)
        for k in [*slots, *(10 + s for s in slots)]:
            expected = state["jet"][k]
            worst = max(worst, abs(got[k] - expected) / max(abs(expected), 1.0))
    return worst


def a05_worst(cid: str) -> tuple[float, str]:
    """max |Δ|/bound over the six TP states and six properties (A05's bound = 1)."""
    provider, r = b.PROVIDERS[cid], b.FLUIDS[cid]["constants"]["R"]
    worst, where = 0.0, ""
    for name, state in b.FLUIDS[cid]["tp_states"].items():
        t, p, phase = b.tp(cid, name)
        result = b.ev(provider, t, p, phase, b.six(cid), ())
        if result.status != "ok":
            return float("inf"), f"{name}: {result.message}"
        for i, x in enumerate(b.six(cid)):
            expected = state["values"][2 + i]
            q = abs(result.values[x] - expected) / value_bound(name, x, t, expected, r)
            if q > worst:
                worst, where = q, f"{name}/{x.split('_')[0]}"
    return worst, where


def saturation(cid: str, key: str) -> dict[str, Any]:
    provider, fluid = b.PROVIDERS[cid], b.PROVIDERS[cid]._fluid
    t = b.sat_temperature(cid, key)
    try:
        sat, liquid, vapour = b.saturated_phases(provider, t)
    except AssertionError as error:
        return {"T": t, "refused": str(error).splitlines()[0]}
    root = provider._saturation(t)
    assert root is not None
    lnphi = f"lnphi_{cid}"
    ratio = (vapour["s"] - liquid["s"]) / (vapour["v"] - liquid["v"])
    return {
        "T": t,
        "Tr": t / fluid.t_c,
        "Psat": sat.values["Psat"],
        "Z_L": sat.values["Psat"] / (root.rho_l * fluid.r * t),
        "iterations": root.iterations,
        "A10": abs(liquid[lnphi] - vapour[lnphi]),
        "A11": abs(sat.derivatives["Psat"]["T"] / ratio - 1.0),
    }


def measure(cid: str) -> dict[str, Any]:
    provider = b.PROVIDERS[cid]
    row: dict[str, Any] = {
        "A03": jet_worst(cid, b.LOW_ORDER),
        "A04": jet_worst(cid, b.THIRD_ORDER),
    }
    row["A05"], row["A05_at"] = a05_worst(cid)
    mid = b.FLUIDS[cid]["saturation"]["sat_mid"]
    result = b.psat(provider, mid["T"])
    row["A08"] = abs(result.values["Psat"] / mid["Psat"] - 1.0) if result.status == "ok" else None
    entry = b.FLUIDS[cid]["tsat"]["tsat_mid"]
    result = b.ev(provider, b.band_t(cid), entry["P"], "VAPOR", ("Tsat",))
    row["A09"] = abs(result.values["Tsat"] / entry["Tsat"] - 1.0) if result.status == "ok" else None
    for key in b.SAT_TEMPERATURES:
        row[key] = saturation(cid, key)
    try:
        row["A17"] = max(b.a17_worst(cid).values())
    except AssertionError as error:
        row["A17"] = str(error).splitlines()[0]
    return row


def main() -> None:
    out = {cid: measure(cid) for cid in b.TIER_B}
    with open(sys.argv[1], "w", encoding="utf-8") as handle:
        json.dump(out, handle, indent=1, sort_keys=True)
    for key in ("A03", "A04", "A05", "A08", "A09", "A17"):
        values = [(r[key], c) for c, r in out.items() if isinstance(r[key], float)]
        print(key, "worst", max(values), "of", len(values))
    for key in b.SAT_TEMPERATURES:
        rows = {c: r[key] for c, r in out.items()}
        served = {c: r for c, r in rows.items() if "A10" in r}
        print(
            key,
            "A10 worst",
            max((r["A10"], c) for c, r in served.items()),
            "A11 worst",
            max((r["A11"], c) for c, r in served.items()),
            "refused",
            sorted(c for c, r in rows.items() if "refused" in r),
        )


if __name__ == "__main__":
    main()
