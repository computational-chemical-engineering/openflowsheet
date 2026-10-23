"""S07 measurement 9 (spec §20, R-627): A31's per-state allowances evaluated on x86-64.

For every fluid of `s07_reference.json`, with the provider `coolprop-heos-v1` (CoolProp 8.0.0):
- the class-N rows of spec §20.3 (state temperature within 1 % of T_c);
- each class-N row's sensitivity sigma (§20.5: a central difference in the state's pressure,
  one-sided at a box edge, step H) and its allowance, relative to max(|x|, s_f);
- the checks of A31c-A31d: every sensitivity evaluation answers `ok`, r = max(|Z-1|, delta)/Z <= 20
  at every class-N TP-type state, (rho_L - rho_V)/rho_c >= 0.04 at every T_sigma_max;
- for comparison with reference tolerances: the slope allowance at T_sigma_max, the summed h
  allowances against |h_V - h_L| (tier A), the largest |h|/RT and |s|/R among stored TP and
  saturation rows, and the pressure sensitivity of the a10 rows at T_lo and T_mid.

A measurement, not an expectation: no test reads its output. Writes argv[2] (JSON) and prints one
summary line. Run from the repository root, in an environment holding the pinned CoolProp:
    PYTHONPATH=<coolprop>:src python \
        docs/derivations/scripts/s07_measurements/m9_a31_allowances.py \
        docs/derivations/scripts/s07_reference.json m9.json
"""

import json
import sys

from openflowsheet.compiled import EvaluationContext
from openflowsheet.thermo import PropertyRequest, StreamState
from openflowsheet.thermo import _coolprop_heos_fluids as table
from openflowsheet.thermo import coolprop_heos as cph

H = 2.5e-7  # §20.5: eps_sigma / 4
B_T, C_N = 1e-10, 2e-10
CONTEXT = EvaluationContext(model_version="s07-provider", constants_sha256="0" * 64)


def scale(x: str, r: float, t: float) -> float:
    """A17's s_f, as `scripts/s07_platform_digest.py`."""
    if x == "h":
        return r * t
    if x in ("s", "cp"):
        return r
    if x == "Z" or x.startswith("lnphi"):
        return 1.0
    return 0.0


def main() -> int:
    reference = json.loads(open(sys.argv[1], encoding="utf-8").read())
    tiers = {row["id"]: row["tier"] for row in table.FLUIDS}
    out: dict = {
        "refused": [],
        "class_n_tp": [],
        "rel_allowance": {},
        "a10_far_sigma": {},
        "a10_far_sigma_over_6_2": [],
        "sigma_rel_t_sigma_max": {},
    }
    worst_r, min_drho, slope, dh = (0.0, ""), (9.0, ""), {}, {}

    def keep(group: str, name: str, value: float, where: str, largest: bool = True) -> None:
        book = out[group]
        old = book.get(name)
        if old is None or (value > old[0] if largest else value < old[0]):
            book[name] = (value, where)

    for cid, fluid in reference["fluids"].items():
        c = fluid["constants"]
        r, t_c = float(c["R"]), float(c["T_c"])
        p_lo, p_hi, rho_red, rho_c = (float(c[k]) for k in ("P_lo", "P_hi", "rho_red", "rho_c"))
        provider = cph.CoolPropHeosProvider(cid)
        names = ("h", "s", "v", "Z", "cp", f"lnphi_{cid}")

        def evaluate(t, p, phase, ders=(), props=names, prov=provider):
            state = StreamState(n=(1.0,), temperature=t, pressure=p)
            return prov.evaluate_phase(PropertyRequest(state, phase, props, ders), CONTEXT)

        def sigma(t, p, phase, ders, getter, where, lo=p_lo, hi=p_hi):
            up, down = p * (1 + H), p * (1 - H)
            points, step = (
                ((p, down), H) if up > hi else ((up, p), H) if down < lo else ((up, down), 2 * H)
            )
            values = []
            for q in points:
                result = evaluate(t, q, phase, ders)
                if result.status != "ok":
                    out["refused"].append(f"{where} {phase} at P={q!r}: {result.status}")
                    return None
                values.append(getter(result))
            return [abs(a - b) / step for a, b in zip(*values, strict=True)], values

        def ratio(v: float, z: float, rho_red: float = rho_red) -> float:
            return max(abs(z - 1.0), 1.0 / (v * rho_red)) / z

        # a10 at T_sigma_max (every fluid) and, for comparison, at T_lo and T_mid
        for key, t in (
            ("T_sigma_max", float(c["T_sigma_max"])),
            ("T_lo", float(c["T_lo"])),
            ("T_mid", float(fluid["saturation"]["sat_mid"]["T"])),
        ):
            sat = evaluate(t, 1.0e5, "LIQUID", ("T", "P", f"n_{cid}"), ("Psat",))
            p_s = float(sat.values["Psat"])
            if p_s < p_lo:
                continue
            base, plus_minus = {}, {}
            for phase in ("LIQUID", "VAPOR"):
                base[phase] = evaluate(t, p_s, phase).values
                got = sigma(t, p_s, phase, (), lambda res, n=names: [res.values[x] for x in n], cid)
                if got is None:
                    continue
                sig, plus_minus[phase] = got
                for x, s in zip(names, sig, strict=True):
                    m = max(abs(base[phase][x]), scale(x, r, t))
                    q = f"{key}.{phase}.{'lnphi' if x.startswith('lnphi') else x}"
                    if key == "T_sigma_max":
                        out["sigma_rel_t_sigma_max"].setdefault(cid, {})[q] = s / m
                        keep("rel_allowance", f"a10.{q}", (B_T * m + C_N * s) / m, cid)
                        keep("rel_allowance", f"a10.{q}.min", (B_T * m + C_N * s) / m, cid, False)
                        if x == "h":
                            dh.setdefault(cid, 0.0)
                            dh[cid] += B_T * m + C_N * s
                    else:
                        keep("a10_far_sigma", q, s / m, cid)
                        if s / m > 6.2:  # 1e-10 / 1.61e-11: spec §20.11 Q-20.1
                            out["a10_far_sigma_over_6_2"].append(
                                f"{cid} {tiers[cid]} {q} {s / m:.1f}"
                            )
                if key == "T_sigma_max":
                    rr = ratio(base[phase]["v"], base[phase]["Z"])
                    worst_r = max(worst_r, (rr, f"{cid} a10.T_sigma_max.{phase}"))
            if key != "T_sigma_max" or len(plus_minus) < 2:
                continue
            drho = (1 / base["LIQUID"]["v"] - 1 / base["VAPOR"]["v"]) / rho_c
            min_drho = min(min_drho, (drho, cid))
            i_s, i_v = names.index("s"), names.index("v")
            cc = [
                (plus_minus["VAPOR"][j][i_s] - plus_minus["LIQUID"][j][i_s])
                / (plus_minus["VAPOR"][j][i_v] - plus_minus["LIQUID"][j][i_v])
                for j in (0, 1)
            ]
            d_t = float(sat.derivatives["Psat"]["T"])
            rel = abs(cc[0] - cc[1]) / (2 * H) / abs(d_t)
            slope[cid] = (B_T + C_N * rel, rel)
            out["sigma_rel_t_sigma_max"][cid]["slope"] = rel
            if tiers[cid] == "A":
                ref_dh = float(fluid["saturation"]["sat_hi"]["dh_vap"])
                dh[cid] = dh[cid] / abs(ref_dh)
            else:
                dh.pop(cid, None)

        # tp rows with |theta| < 1e-2
        for key, state in sorted(fluid["tp_states"].items()):
            t, p = float(state["values"][0]), float(state["values"][1])
            if abs(1.0 - t / t_c) >= 1e-2:
                continue
            out["class_n_tp"].append(f"{cid}.{key}")
            phase = "LIQUID" if state["phase"] == "LIQUID" else "VAPOR"
            tier_a = tiers[cid] == "A"
            ders = ("T", "P", f"n_{cid}") if tier_a else ()

            def getter(res, tier_a=tier_a, names=names):
                values = [res.values[x] for x in names]
                if tier_a:
                    values += [res.derivatives[x][w] for x in names for w in ("T", "P")]
                return values

            result = evaluate(t, p, phase, ders)
            base_values = getter(result)
            got = sigma(t, p, phase, ders, getter, f"{cid}.{key}")
            if got is None:
                continue
            labels = list(names) + (
                [f"d{w}.{x}" for x in names for w in ("T", "P")] if tier_a else []
            )
            for label, value, s in zip(labels, base_values, got[0], strict=True):
                x = label.split(".")[-1]
                s_f = scale(x, r, t) / (
                    (t if label[1] == "T" else p) if label.startswith("d") else 1.0
                )
                m = max(abs(value), s_f)
                q = label.replace(f"lnphi_{cid}", "lnphi")
                keep(
                    "rel_allowance", f"tp.{tiers[cid]}.{q}", (B_T * m + C_N * s) / m, f"{cid}.{key}"
                )
            worst_r = max(worst_r, (ratio(base_values[2], base_values[3]), f"{cid}.{key}"))

    # stored rows: the largest |h|/RT and |s|/R (class-T allowance against A05's absolute bounds)
    big_h, big_s = (0.0, ""), (0.0, "")
    for cid, fluid in reference["fluids"].items():
        r = float(fluid["constants"]["R"])
        rows = [(k, s["values"]) for k, s in fluid["tp_states"].items()]
        rows += [
            (k + ph, s[ph]) for k, s in fluid["saturation"].items() for ph in ("L", "V") if ph in s
        ]
        for key, values in rows:
            t, h, s = values[0], values[2], values[3]
            big_h = max(big_h, (abs(h) / (r * t), f"{cid}.{key}"))
            big_s = max(big_s, (abs(s) / r, f"{cid}.{key}"))

    out.update(
        r_max=worst_r,
        drho_min=min_drho,
        slope_rel_allowance=slope,
        dh_sum_over_abs_dh_tier_a=dh,
        max_h_over_rt=big_h,
        max_s_over_r=big_s,
    )
    with open(sys.argv[2], "w", encoding="utf-8") as handle:
        json.dump(out, handle, indent=1, sort_keys=True)
    slopes = [v[1] for v in slope.values()]
    print(
        f"m9: refused {len(out['refused'])}; class-N tp states {len(out['class_n_tp'])}; "
        f"r_max {worst_r[0]:.3f} ({worst_r[1]}); drho_min {min_drho[0]:.4f} ({min_drho[1]}); "
        f"sigma_dT/|dT| {min(slopes):.1f}..{max(slopes):.1f}; "
        f"max |h|/RT {big_h[0]:.1f} ({big_h[1]}); max |s|/R {big_s[0]:.1f} ({big_s[1]})"
    )
    return 1 if out["refused"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
