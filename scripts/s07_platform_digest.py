"""`benchmarks/s07/platform_digest.json`: the S07 provider's A03-A13 answers, `float.hex` per fluid.

Spec §9 A31 and §12.3 item 2. The digest is a regression fixture, not validation: it records what
`coolprop-heos-v1` answers on the machine that wrote it (x86-64), so that CI can recompute the
answers on `ubuntu-24.04-arm` and compare them (spec §20: bitwise, or within each row's class).

The inputs are the states of `s07_reference.json` (`phi_states`, `tp_states`, `saturation`,
`tsat`, `band`); no reference *value* is read. Per fluid, in a fixed order (tier B stops where
§16.10 stops):

- A03/A04: the 20 slots of (alpha°, alphar) at each `phi_states` entry;
- A05 (and A06 for tier A): h, s, v, Z, cp, lnphi at each `tp_states` entry, and for tier A their
  T and P derivatives;
- A08/A09: Psat and its T derivative at each `saturation` entry (tier A: every one; tier B:
  `sat_mid`), and Tsat at `tsat_mid`;
- A10/A11: both saturated phases' h, s, v, lnphi at {T_lo, T_mid, T_sigma_max}, Psat and dPsat/dT;
- A12 (H2O): u and s of the saturated liquid at 273.16 K and 450 K;
- A13: the six values at each answered phase of each `band` probe.

A refusal is recorded as the string `status:code`. The file holds the values only, in
`answers(cid)`'s order (its keys are regenerated; the test also compares their count).
`answers(cid)` returns (key, value, scale) rows; `scale` is A17's FD scale s_f (`R*T` for h, `R`
for s and cp, 1 for Z, lnphi and the jet slots, 0 for v and the saturation quantities; a
derivative takes its quantity's scale over T or P), the floor of A31's `max(|x|, s_f)`.

`compare()` is A31 under spec §20 (R-627; it replaces §11 Q-1's rule). It recomputes every answer
and compares it with the digest. Outcome (a) is bitwise equality, and on x86-64, the digest's own
machine, it is required (§20.6). Otherwise every row is judged by its class (§20.3): a refusal
string (S) exactly; an ordinary row (T) by |d| <= 1e-10 * max(|x|, s_f) (§20.4); a near-critical
row (N: family `tp`, `sat` or `a10` with |1 - T/T_c| < 1e-2) by |d| <= 1e-10 * |x| for Psat and
otherwise by 1e-10 * max(|x|, s_f) + 2e-10 * sigma, where sigma = P*|dq/dP|_T is the row's own
pressure sensitivity, recomputed on the running machine by a central difference with step 2.5e-7
(§20.5). A31c's rule inputs and A31d's evaluability are checked on every machine. Beyond an
allowance the comparison fails: nothing is loosened here. `--report` prints §20.9's verdict line
and summaries and writes the JSON report.

Usage (CoolProp 8.0.0 environment, from the repository root):
    PYTHONPATH=src python scripts/s07_platform_digest.py [--check | --report [--out PATH]]
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "docs" / "derivations" / "scripts" / "s07_reference.json"
DIGEST = ROOT / "benchmarks" / "s07" / "platform_digest.json"
SAT_TEMPERATURES = ("T_lo", "T_mid", "T_sigma_max")
Row = tuple[str, "float | str", float]


def _modules() -> tuple[Any, Any, Any]:
    from openflowsheet.compiled import EvaluationContext
    from openflowsheet.thermo import _coolprop_heos_fluids as table
    from openflowsheet.thermo import coolprop_heos as cph

    return EvaluationContext, table, cph


def _scale(quantity: str, r: float, t: float) -> float:
    if quantity == "h":
        return r * t
    if quantity in ("s", "cp"):
        return r
    if quantity == "Z" or quantity.startswith("lnphi_"):
        return 1.0
    return 0.0


def answers(cid: str, reference: dict[str, Any] | None = None) -> list[Row]:
    """The fluid's rows (key, value or refusal string, scale), in the digest's fixed order."""
    from openflowsheet.thermo import PropertyRequest, StreamState

    evaluation_context, table, cph = _modules()
    reference = reference or json.loads(REFERENCE.read_text("utf-8"))
    fluid = reference["fluids"][cid]
    tier = next(row["tier"] for row in table.FLUIDS if row["id"] == cid)
    constants = fluid["constants"]
    r = float(constants["R"])
    provider = cph.CoolPropHeosProvider(cid)
    context = evaluation_context(model_version="s07-provider", constants_sha256="0" * 64)
    properties = ("h", "s", "v", "Z", "cp", f"lnphi_{cid}")
    rows: list[Row] = []

    def evaluate(
        t: float, p: float, phase: str, names: tuple[str, ...], derivatives: tuple[str, ...]
    ) -> Any:
        state = StreamState(n=(1.0,), temperature=t, pressure=p)
        return provider.evaluate_phase(
            PropertyRequest(state, phase, names, derivatives),  # type: ignore[arg-type]
            context,
        )

    def record(tag: str, result: Any, names: tuple[str, ...], t: float, p: float, d: bool) -> None:
        if result.status != "ok":
            rows.append((f"{tag}.status", f"{result.status}:{result.message.split(':')[0]}", 0.0))
            return
        for x in names:
            scale = _scale(x, r, t)
            rows.append((f"{tag}.{x}", float(result.values[x]), scale))
            if d:
                for wrt, divisor in (("T", t), ("P", p)):
                    value = float(result.derivatives[x][wrt])
                    rows.append((f"{tag}.d{wrt}.{x}", value, scale / divisor))

    for key in sorted(fluid["phi_states"]):
        state = fluid["phi_states"][key]
        ideal, residual = cph.helmholtz_jet(cid, state["T"], state["rho"])
        for slot, value in enumerate([*ideal, *residual]):
            rows.append((f"phi.{key}.{slot}", float(value), 1.0))
    for key in sorted(fluid["tp_states"]):
        state = fluid["tp_states"][key]
        t, p = float(state["values"][0]), float(state["values"][1])
        phase = "LIQUID" if state["phase"] == "LIQUID" else "VAPOR"
        derivatives = ("T", "P", f"n_{cid}") if tier == "A" else ()
        result = evaluate(t, p, phase, properties, derivatives)
        record(f"tp.{key}", result, properties, t, p, tier == "A")

    def saturation(t: float) -> Any:
        return evaluate(t, 1.0e5, "LIQUID", ("Psat",), ("T", "P", f"n_{cid}"))

    for key in sorted(fluid["saturation"]):
        if tier == "B" and key != "sat_mid":
            continue
        t = float(fluid["saturation"][key]["T"])
        sat = saturation(t)
        if sat.status != "ok":
            rows.append((f"sat.{key}.status", f"{sat.status}:{sat.message.split(':')[0]}", 0.0))
            continue
        rows.append((f"sat.{key}.Psat", float(sat.values["Psat"]), 0.0))
        rows.append((f"sat.{key}.dT", float(sat.derivatives["Psat"]["T"]), 0.0))
    band_t = float(fluid["band"]["T"])
    tsat = evaluate(
        band_t, float(fluid["tsat"]["tsat_mid"]["P"]), "VAPOR", ("Tsat",), ("T", "P", f"n_{cid}")
    )
    if tsat.status == "ok":
        rows.append(("tsat.Tsat", float(tsat.values["Tsat"]), 0.0))
        rows.append(("tsat.dP", float(tsat.derivatives["Tsat"]["P"]), 0.0))
    else:
        rows.append(("tsat.status", f"{tsat.status}:{tsat.message.split(':')[0]}", 0.0))

    def phases_at(t: float) -> tuple[Any, dict[str, dict[str, float]]]:
        """Psat at T and both saturated phases; below P_lo through the provider's own saturation
        state (B-18, as `tests/test_s07_coolprop.py`'s `saturated_phases`)."""
        sat = saturation(t)
        if sat.status != "ok":
            return sat, {}
        p = float(sat.values["Psat"])
        if p >= provider._fluid.p_lo:
            pair = {phase: evaluate(t, p, phase, properties, ()) for phase in ("LIQUID", "VAPOR")}
            return sat, {
                phase: {x: float(result.values[x]) for x in properties}
                for phase, result in pair.items()
                if result.status == "ok"
            }
        root = provider._saturation(t)
        values = {}
        for phase, rho in (("LIQUID", root.rho_l), ("VAPOR", root.rho_v)):
            at = provider._at(t, rho, p)
            values[phase] = {x: float(at[x][0]) for x in properties}
        return sat, values

    for key in SAT_TEMPERATURES:
        t = float(fluid["saturation"]["sat_mid"]["T"]) if key == "T_mid" else float(constants[key])
        sat, values = phases_at(t)
        if sat.status != "ok":
            rows.append((f"a10.{key}.status", f"{sat.status}:{sat.message.split(':')[0]}", 0.0))
            continue
        rows.append((f"a10.{key}.Psat", float(sat.values["Psat"]), 0.0))
        rows.append((f"a10.{key}.dT", float(sat.derivatives["Psat"]["T"]), 0.0))
        for phase in ("LIQUID", "VAPOR"):
            for x in properties:
                if phase in values:
                    rows.append((f"a10.{key}.{phase}.{x}", values[phase][x], _scale(x, r, t)))
    if cid == "H2O":
        for t in (273.16, 450.0):
            sat, values = phases_at(t)
            liquid = values["LIQUID"]
            rows.append(
                (f"a12.{t}.u", liquid["h"] - float(sat.values["Psat"]) * liquid["v"], r * t)
            )
            rows.append((f"a12.{t}.s", liquid["s"], r))
    for key in sorted(fluid["band"]["probes"]):
        probe = fluid["band"]["probes"][key]
        for phase in sorted(probe["answered"]):
            result = evaluate(band_t, float(probe["P"]), phase, properties, ())
            record(f"band.{key}.{phase}", result, properties, band_t, float(probe["P"]), False)
    return rows


# -- A31's rule (spec §20, R-627) ------------------------------------------------------------------

B_T = 1e-10  # §20.4: class T, |d| <= B_T * max(|x|, s_f), both tiers
B_P = 1e-10  # §20.5: class-N Psat rows, |d| <= B_P * |x| (G3's near p_sigma bound, §19.2)
C_N = 2e-10  # §20.5: every other class-N row, |d| <= B_T * max(|x|, s_f) + C_N * sigma
H = 2.5e-7  # §20.5: the sensitivity's relative pressure step, eps_sigma / 4
THETA_N = 1e-2  # §20.3: class N where |1 - T/T_c| < THETA_N
R_MAX = 20.0  # A31c(3): r = max(|Z - 1|, delta)/Z
DRHO_MIN = 0.04  # A31c(4): (rho_L - rho_V)/rho_c at T_sigma_max
#: §20.3: the six fluids whose clamped supercritical TP states lie within 1 % above T_c.
CLAMPED_NEAR_CRITICAL = (
    "MD4M",
    "PropyleneGlycol",
    "R236FA",
    "R245ca",
    "n-Nonane",
    "n-Perfluorohexane",
)
REPORT_DIR = ROOT / "evidence" / "S07" / "artifacts"


def expected_class_n(tiers: dict[str, str]) -> set[tuple[str, str]]:
    """§20.3's 168 (fluid, state) pairs at this head (A31c(1))."""
    pairs = {(cid, "a10.T_sigma_max") for cid in tiers}
    for cid, tier in tiers.items():
        if tier == "A":
            pairs |= {(cid, "sat.sat_hi"), (cid, "tp.NC_V"), (cid, "tp.NC_L")}
    for cid in CLAMPED_NEAR_CRITICAL:
        pairs |= {(cid, f"tp.{key}") for key in ("S_dense", "V_sup", "V_corner")}
    return pairs


def state_temperature(key: str, fluid: dict[str, Any]) -> float | None:
    """§20.3's state temperature of a row; `phi` rows have none."""
    parts = key.split(".")
    family = parts[0]
    if family == "phi":
        return None
    if family == "tp":
        return float(fluid["tp_states"][parts[1]]["values"][0])
    if family == "sat":
        return float(fluid["saturation"][parts[1]]["T"])
    if family == "a10":
        if parts[1] == "T_mid":
            return float(fluid["saturation"]["sat_mid"]["T"])
        return float(fluid["constants"][parts[1]])
    if family in ("tsat", "band"):
        return float(fluid["band"]["T"])
    if family == "a12":
        return float(".".join(parts[1:-1]))
    raise ValueError(f"no §20.3 state temperature for {key}")


def row_class(key: str, value: float | str, fluid: dict[str, Any]) -> str:
    """§20.3: `S` (a refusal string), `N` (near-critical: a `tp`, `sat` or `a10` row whose state
    temperature has |theta| < 1e-2) or `T`. A near-critical `tsat`, `band` or `a12` row has no
    class: ValueError."""
    if isinstance(value, str):
        return "S"
    t = state_temperature(key, fluid)
    if t is None:
        return "T"
    theta = 1.0 - t / float(fluid["constants"]["T_c"])
    if not abs(theta) < THETA_N:
        return "T"
    if key.split(".")[0] in ("tp", "sat", "a10"):
        return "N"
    raise ValueError(f"§20 defines no class-N sensitivity for {key}")


def _is_psat(key: str) -> bool:
    parts = key.split(".")
    return parts[0] in ("sat", "a10") and parts[-1] == "Psat"


def _evaluate(provider: Any, t: float, p: float, phase: str, names: tuple[str, ...], d: Any) -> Any:
    from openflowsheet.thermo import PropertyRequest, StreamState

    evaluation_context, _, _ = _modules()
    context = evaluation_context(model_version="s07-provider", constants_sha256="0" * 64)
    state = StreamState(n=(1.0,), temperature=t, pressure=p)
    request = PropertyRequest(state, phase, names, d)  # type: ignore[arg-type]
    return provider.evaluate_phase(request, context)


def sensitivities(
    cid: str, rows: list[Row], fluid: dict[str, Any], tier: str
) -> tuple[dict[str, str], dict[str, float], list[str]]:
    """§20.3 and §20.5 for one fluid, on the running machine: each row's class, sigma for every
    class-N row other than Psat, and the failures (an unclassifiable row; a sensitivity that is not
    evaluable, A31d). sigma = |q(P(1 + H)) - q(P(1 - H))|/(2H), one-sided at the box's edges."""
    _, _, cph = _modules()
    constants = fluid["constants"]
    p_lo, p_hi = float(constants["P_lo"]), float(constants["P_hi"])
    properties = ("h", "s", "v", "Z", "cp", f"lnphi_{cid}")
    values = dict((key, value) for key, value, _ in rows)
    classes: dict[str, str] = {}
    failures: list[str] = []
    states: dict[str, list[str]] = {}
    for key, value, _ in rows:
        try:
            classes[key] = row_class(key, value, fluid)
        except ValueError as error:
            classes[key] = "T"
            failures.append(f"{cid}: {error}")
            continue
        if classes[key] == "N" and not _is_psat(key):
            states.setdefault(".".join(key.split(".")[:2]), []).append(key)
    provider = cph.CoolPropHeosProvider(cid)

    def answer(t: float, p: float, phase: str, d: tuple[str, ...]) -> Any:
        result = _evaluate(provider, t, p, phase, properties, d)
        return result if result.status == "ok" else None

    def tp_q(state: str, t: float, phase: str, d: tuple[str, ...]) -> Any:
        def q(p: float) -> dict[str, float] | None:
            result = answer(t, p, phase, d)
            if result is None:
                return None
            out = {f"{state}.{x}": float(result.values[x]) for x in properties}
            if d:
                for x in properties:
                    for wrt in ("T", "P"):
                        out[f"{state}.d{wrt}.{x}"] = float(result.derivatives[x][wrt])
            return out

        return q

    def saturated_q(state: str, t: float) -> Any:
        def q(p: float) -> dict[str, float] | None:
            pair = {phase: answer(t, p, phase, ()) for phase in ("LIQUID", "VAPOR")}
            if None in pair.values():
                return None
            out = {
                f"{state}.{phase}.{x}": float(result.values[x])
                for phase, result in pair.items()
                for x in properties
            }
            liquid, vapour = pair["LIQUID"].values, pair["VAPOR"].values
            out[f"{state}.dT"] = (float(vapour["s"]) - float(liquid["s"])) / (
                float(vapour["v"]) - float(liquid["v"])
            )
            return out

        return q

    sigma: dict[str, float] = {}
    for state, keys in states.items():
        family, name = state.split(".")
        t = state_temperature(keys[0], fluid)
        assert t is not None
        if family == "tp":
            entry = fluid["tp_states"][name]
            p = float(entry["values"][1])
            phase = "LIQUID" if entry["phase"] == "LIQUID" else "VAPOR"
            d = ("T", "P", f"n_{cid}") if tier == "A" else ()
            q = tp_q(state, t, phase, d)
        else:
            psat = values.get(f"{state}.Psat")
            p = psat if isinstance(psat, float) else float("nan")
            q = saturated_q(state, t)
        up, down = p * (1.0 + H), p * (1.0 - H)
        if up > p_hi:
            points, step = (p, down), H
        elif down < p_lo:
            points, step = (up, p), H
        else:
            points, step = (up, down), 2.0 * H
        a, b = (q(point) if math.isfinite(point) else None for point in points)
        for key in keys:
            s = abs(a[key] - b[key]) / step if a and b and key in a and key in b else math.nan
            if not math.isfinite(s):  # refused, missing or not finite: never skipped, never 0
                failures.append(f"{cid}: §20 sensitivity not evaluable at {key}")
                continue
            sigma[key] = s
    return classes, sigma, failures


def rule_inputs(
    cid: str, rows: list[Row], classes: dict[str, str], fluid: dict[str, Any]
) -> tuple[set[str], dict[str, Any], list[str]]:
    """A31c (2)-(5) for one fluid, from ref's constants and the running machine's rows: the
    class-N states, the measured inputs and the failures (each with its item number)."""
    constants = fluid["constants"]
    values = {key: value for key, value, _ in rows}
    numeric = {key: value for key, value in values.items() if isinstance(value, float)}
    rho_red, rho_c = float(constants["rho_red"]), float(constants["rho_c"])
    failures: list[str] = []
    states = {".".join(key.split(".")[:2]) for key, c in classes.items() if c == "N"}
    measured: dict[str, Any] = {"r": {}, "drho": None, "psat_over_p_lo": {}}
    if not 2.0 * H <= float(constants["eps_sigma"]):
        failures.append(f"A31c(2) {cid}: 2H = {2.0 * H!r} > eps_sigma {constants['eps_sigma']!r}")
    prefixes = [f"{state}." + phase for state in sorted(states) for phase in ("LIQUID", "VAPOR")]
    prefixes = [s for s in prefixes if s.startswith("a10.")]
    prefixes += [state for state in sorted(states) if state.startswith("tp.")]
    for prefix in prefixes:
        v, z = numeric.get(f"{prefix}.v"), numeric.get(f"{prefix}.Z")
        if v is None or z is None:
            continue
        r = max(abs(z - 1.0), 1.0 / (v * rho_red)) / z
        measured["r"][prefix] = r
        if not r <= R_MAX:
            failures.append(f"A31c(3) {cid} {prefix}: r = {r:.4g} > {R_MAX:g}")
    v_l = numeric.get("a10.T_sigma_max.LIQUID.v")
    v_v = numeric.get("a10.T_sigma_max.VAPOR.v")
    drho = (1.0 / v_l - 1.0 / v_v) / rho_c if v_l and v_v else float("nan")
    measured["drho"] = drho
    if not drho >= DRHO_MIN:
        failures.append(f"A31c(4) {cid}: (rho_L - rho_V)/rho_c = {drho:.4g} < {DRHO_MIN:g}")
    for state in sorted(s for s in states if s.startswith("a10.")):
        psat = numeric.get(f"{state}.Psat", float("nan"))
        measured["psat_over_p_lo"][state] = psat / float(constants["P_lo"])
        if not psat >= float(constants["P_lo"]):
            failures.append(f"A31c(5) {cid} {state}: Psat {psat!r} < P_lo {constants['P_lo']!r}")
    return states, measured, failures


def measure(reference: dict[str, Any] | None = None) -> dict[str, Any]:
    """Everything A31 recomputes on the running machine, per fluid: the rows, their classes, the
    class-N sensitivities and A31c's inputs; and the failures of A31c and A31d."""
    _, table, _ = _modules()
    reference = reference or json.loads(REFERENCE.read_text("utf-8"))
    tiers = {row["id"]: row["tier"] for row in table.FLUIDS}
    fluids: dict[str, Any] = {}
    failures: list[str] = []
    pairs: set[tuple[str, str]] = set()
    for cid, tier in tiers.items():
        fluid = reference["fluids"][cid]
        rows = answers(cid, reference)
        classes, sigma, sigma_failures = sensitivities(cid, rows, fluid, tier)
        states, inputs, input_failures = rule_inputs(cid, rows, classes, fluid)
        pairs |= {(cid, state) for state in states}
        failures += sigma_failures + input_failures
        fluids[cid] = {"rows": rows, "classes": classes, "sigma": sigma, "inputs": inputs}
    expected = expected_class_n(tiers)
    if pairs != expected:
        failures.append(
            f"A31c(1): class-N pairs {len(pairs)}, §20.3 lists {len(expected)}; "
            f"extra {sorted(pairs - expected)[:5]}, missing {sorted(expected - pairs)[:5]}"
        )
    return {"fluids": fluids, "class_n_pairs": sorted(pairs), "failures": failures}


def allowance(key: str, x: float, scale: float, row: str, sigma: float | None) -> float:
    """A31's allowance A for a numeric row of class `row` (§20.4, §20.5); NaN where a class-N
    row's sigma is missing (A31d has then failed, and a difference there fails)."""
    if row == "T":
        return B_T * max(abs(x), scale)
    if _is_psat(key):
        return B_P * abs(x)
    if sigma is None:
        return float("nan")
    return B_T * max(abs(x), scale) + C_N * sigma


def quantity(key: str) -> str:
    """The key without its state name (§20.9): the quantity a worst is reported for. The a10
    temperature stays; `lnphi_<id>` reads `lnphi`."""
    parts = key.split(".")
    if parts[-1].startswith("lnphi_"):
        parts[-1] = "lnphi"
    family = parts[0]
    if family == "phi":
        return "phi.slot"
    if family in ("band", "sat", "a12"):
        return f"{family}.{parts[-1]}"
    if family == "tp":
        return ".".join([family, *parts[2:]])
    return ".".join(parts)


def _hex(value: float | str) -> str:
    return value.hex() if isinstance(value, float) else value


def compare(
    digest: dict[str, Any] | None = None,
    measured: dict[str, Any] | None = None,
    machine: str | None = None,
) -> dict[str, Any]:
    """A31 (spec §20.8): compare the running machine's answers with the digest. Returns the
    outcome, every differing row (§20.9's fields), the worst ratio per `<class>:<quantity>` group,
    the per-class counts and worst utilization, the rows over their allowance (`flagged`), every
    failure, and the verdict line."""
    machine = machine or platform.machine()
    digest = digest or json.loads(DIGEST.read_text("utf-8"))
    measured = measured or measure()
    failures: list[str] = list(measured["failures"])
    rows_out: list[dict[str, Any]] = []
    flagged: list[tuple[str, str]] = []
    groups: dict[str, tuple[float, str, str]] = {}
    classes: dict[str, dict[str, Any]] = {
        c: {"compared": 0, "differing": 0, "failing": 0, "worst_u": None} for c in "TNS"
    }
    psat_worst: tuple[float, str, str] | None = None
    bitwise = True

    def worse(old: Any, new: tuple[float, str, str]) -> Any:
        return new if old is None or new[0] > old[0] else old

    for cid, entry in measured["fluids"].items():
        stored = digest["fluids"][cid]
        rows = entry["rows"]
        if len(rows) != len(stored):
            failures.append(f"{cid}: {len(rows)} answers, the digest holds {len(stored)}")
            bitwise = False
            continue
        for (key, value, scale), hexed in zip(rows, stored, strict=True):
            kind = "S" if isinstance(value, str) or ":" in hexed else entry["classes"][key]
            summary = classes[kind]
            summary["compared"] += 1
            if kind == "S":
                if value == hexed:
                    continue
                bitwise = False
                row = {"fluid": cid, "key": key, "class": "S", "x": hexed, "y": _hex(value)}
                row |= {"delta": None, "allowance": None, "u": math.inf, "ratio": None}
            else:
                assert isinstance(value, float)
                x = float.fromhex(hexed)
                if value == x:
                    continue
                bitwise = False
                delta = abs(value - x)
                a = allowance(key, x, scale, kind, entry["sigma"].get(key))
                u = math.inf if not a > 0.0 else delta / a
                denominator = max(abs(x), scale)
                ratio = delta / denominator if denominator > 0.0 else math.inf
                row = {"fluid": cid, "key": key, "class": kind, "x": hexed, "y": value.hex()}
                row |= {"delta": delta, "allowance": a, "u": u, "ratio": ratio}
                group = f"{kind}:{quantity(key)}"
                groups[group] = worse(groups.get(group), (ratio, cid, key))
                if kind == "N" and _is_psat(key):
                    psat_worst = worse(psat_worst, (ratio, cid, key))
            row["fails"] = not row["u"] <= 1.0
            summary["differing"] += 1
            summary["worst_u"] = worse(summary["worst_u"], (row["u"], cid, key))
            if row["fails"]:
                summary["failing"] += 1
                flagged.append((cid, key))
                failures.append(
                    f"{cid} {key} [{kind}]: {row['y']} vs {row['x']}"
                    + ("" if kind == "S" else f", |d| {row['delta']:.3e}, A {row['allowance']:.3e}")
                )
            rows_out.append(row)
    rows_out.sort(key=lambda row: (not row["fails"], -row["u"]))
    result = {
        "machine": machine,
        "outcome": "a" if bitwise else "b",
        "bitwise": bitwise,
        "rows": rows_out,
        "groups": groups,
        "classes": classes,
        "psat_worst": psat_worst,
        "flagged": flagged,
        "failures": failures,
        "class_n_pairs": len(measured["class_n_pairs"]),
    }
    result["verdict"] = verdict(result)
    return result


def verdict(result: dict[str, Any]) -> str:
    """§20.9's verdict line for the machine A31 ran on."""
    head = f"S07 A31 ({result['machine']}): "
    classes = result["classes"]
    n_fail = sum(summary["failing"] for summary in classes.values())
    other = len(result["failures"]) - n_fail
    if result["bitwise"] and not result["failures"]:
        return head + "bit-identical"
    if result["machine"] == "x86_64" and not result["bitwise"]:
        return head + (
            "not bit-identical, FAILS: the digest's own architecture must be bit-identical "
            "(spec §20.6)"
        )
    if result["failures"]:
        worst = max(
            (s["worst_u"] for s in classes.values() if s["failing"]),
            key=lambda entry: entry[0],
            default=None,
        )
        text = head + ("bit-identical" if result["bitwise"] else "not bit-identical")
        text += f", FAILS spec §20: {n_fail} rows over their allowance; worst "
        text += f"{worst[0]:.3g} ({worst[1]} {worst[2]})" if worst else "-"
        if other:
            text += f"; {other} other failures, first: {result['failures'][0]}"
        return text

    def at(entry: Any, digits: str) -> str:
        return f"{entry[0]:{digits}} ({entry[1]} {entry[2]})" if entry else "0 (-)"

    t_worst = max(
        (entry for group, entry in result["groups"].items() if group.startswith("T:")),
        key=lambda entry: entry[0],
        default=None,
    )
    p_worst = result["psat_worst"]
    p_text = format(p_worst[0], ".3e") if p_worst else "0"
    n_diff = sum(summary["differing"] for summary in classes.values())
    n_rows = sum(summary["compared"] for summary in classes.values())
    return head + (
        f"not bit-identical; within spec §20: class T worst ratio {at(t_worst, '.3e')} of 1e-10; "
        f"class N worst {at(classes['N']['worst_u'], '.3g')} of its allowance; "
        f"class-N Psat worst {p_text} of 1e-10; {n_diff} of {n_rows} rows differ"
    )


def _plain(value: Any) -> Any:
    """JSON without NaN or Infinity: a non-finite number is written as its string."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(item) for item in value]
    return value


def write_report(result: dict[str, Any], out: Path | None = None) -> Path:
    """§20.9: every differing row and the summaries, as JSON, at `out` or
    `evidence/S07/artifacts/a31_report_<machine>.json`."""
    path = out or REPORT_DIR / f"a31_report_{result['machine']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "schema": "s07-a31-report-v1",
        "spec": "docs/derivations/S07-spec.md §20 (R-627)",
        "constants": {"B_T": B_T, "B_P": B_P, "C_N": C_N, "H": H},
        **{key: result[key] for key in ("machine", "verdict", "outcome", "bitwise")},
        "passed": not result["failures"],
        "classes": result["classes"],
        "groups": result["groups"],
        "psat_worst": result["psat_worst"],
        "class_n_pairs": result["class_n_pairs"],
        "failures": result["failures"],
        "rows": result["rows"],
    }
    path.write_text(json.dumps(_plain(document), indent=1, allow_nan=False) + "\n", "utf-8")
    return path


def report_lines(result: dict[str, Any]) -> list[str]:
    """§20.9's printout: the verdict line, one line per class, the 20 rows with the largest
    utilization (failures first), then every failure that is not a row over its allowance."""
    lines = [result["verdict"]]
    for name, summary in result["classes"].items():
        worst = summary["worst_u"]
        lines.append(
            f"  class {name}: {summary['compared']} compared, {summary['differing']} differ, "
            f"{summary['failing']} fail; worst u "
            + (f"{worst[0]:.3g} ({worst[1]} {worst[2]})" if worst else "-")
        )
    for row in result["rows"][:20]:
        numbers = (
            ""
            if row["class"] == "S"
            else f" ratio {row['ratio']:.3e} |d| {row['delta']:.3e} A {row['allowance']:.3e}"
        )
        mark = "FAIL " if row["fails"] else ""
        lines.append(
            f"  {mark}{row['fluid']} {row['key']} [{row['class']}] u {row['u']:.3g}{numbers}"
        )
    flagged = {f"{cid} {key} " for cid, key in result["flagged"]}
    lines += [
        f"  {line}" for line in result["failures"] if not any(line.startswith(f) for f in flagged)
    ]
    return lines


def build() -> dict[str, Any]:
    _, table, cph = _modules()
    reference = json.loads(REFERENCE.read_text("utf-8"))
    return {
        "schema": "s07-platform-digest-v1",
        "note": "A31 regression fixture (x86-64): float.hex of every A03-A13 answer, in "
        "scripts/s07_platform_digest.py's answers() order; not validation",
        "coolprop_version": cph.PINNED_COOLPROP_VERSION,
        "fluids": {
            row["id"]: [
                value.hex() if isinstance(value, float) else value
                for _, value, _ in answers(row["id"], reference)
            ]
            for row in table.FLUIDS
        },
    }


def render(digest: dict[str, Any]) -> str:
    """One line per fluid: compact, stable, and diffable."""
    lines = [
        f"{json.dumps(cid)}: {json.dumps(rows, separators=(',', ':'))}"
        for cid, rows in digest["fluids"].items()
    ]
    head = {key: value for key, value in digest.items() if key != "fluids"}
    return json.dumps(head, indent=1)[:-2] + ',\n "fluids": {\n' + ",\n".join(lines) + "\n }\n}\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--check", action="store_true", help="regenerate and compare with the file")
    parser.add_argument("--report", action="store_true", help="A31 (spec §20): compare and report")
    parser.add_argument(
        "--out", type=Path, help="--report's JSON (default: evidence/S07/artifacts)"
    )
    arguments = parser.parse_args()
    sys.path.insert(0, str(ROOT / "src"))
    if arguments.report:
        result = compare()
        path = write_report(result, arguments.out)
        print("\n".join(report_lines(result)))
        print(f"  report: {path}")
        return 1 if result["failures"] else 0
    text = render(build())
    json.loads(text)
    if arguments.check:
        same = DIGEST.read_text("utf-8") == text
        print(f"{DIGEST.relative_to(ROOT)}: {'OK (byte-identical)' if same else 'DIFFERS'}")
        return 0 if same else 1
    DIGEST.write_text(text, encoding="utf-8")
    print(f"{DIGEST.relative_to(ROOT)}: written, {len(text)} bytes, {len(text.splitlines())} lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
