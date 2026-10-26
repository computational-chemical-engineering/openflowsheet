"""S09 WO-S09-3: BioSTEAM's column reference comparison, recomputed from the committed JSON alone.

Authority: `docs/derivations/S09-spec.md` §6–§8 and §10, as amended by §18. Reads BioSTEAM's records
`benchmarks/s09/references/results/biosteam-<case>.json` (WO-S09-2's blind qualification), S03's
committed our-side records `benchmarks/s03/references/results/ours-<case>.json` (PC-LB is RC1's
record, §3), `docs/derivations/scripts/s03_cases.json`, `docs/derivations/scripts/s09_cases.json`,
the twin `docs/derivations/scripts/s03_reference.json` and S03's `comparison.json` (IDAES's and
DWSIM's classes, read at the pinned hash and never re-classified, §8.1). It classifies each of the
19 registered (case, BioSTEAM) pairs by S03 §7.1's rules in order (§6.5):

0. BioSTEAM is not available for the case (§2.3 step 4) → `NOT_COMPARABLE(capability: <reason>)`;
1. the record's pip-freeze fingerprint differs from `docs/reference-environments.md` §9's, or its
   versions from §2.1's → `NOT_COMPARABLE(access: <what>)`;
2. B1–B5 (§6.2; B2 per rung as §18.3 restates it) on the selected run →
   `NOT_COMPARABLE(reference_accuracy: <check>(<value>))`;
2c. S03's rule 2c (stage count and map, inlet stages, pressures, intermediate duties, the
   specification by S03 §5.1 row 9 within 1e-4) and §6.3's additions (total-condenser vapour,
   specification read-back, property readback) → `NOT_COMPARABLE(semantics: <check>(<value>))`;
2d. the specification residual per kind (S03 §17.4), the accuracy rerun (§18.4(b): rules 2 and 2c,
   and no registered quantity moved by more than 0.1 tolerance) and path dependence across the
   passing rungs of the level (§6.4), each with the twin's tolerance →
   `NOT_COMPARABLE(reference_accuracy: <check>(<value>))`;
3. ours is not `CONVERGED`, or a registered quantity is more than 0.1 tolerance from the twin →
   `NOT_COMPARABLE(ours_not_verified)`;
4. every registered quantity within `a_k + 1e-6 |v|` (S03 §6, `v` the twin's 25-digit value,
   unrounded) → `AGREE`, otherwise `DISAGREE`, with the full table.

Every rule value is recomputed here from the record's raw fields (§10): the tool script's summaries
(its check blocks, pass flags, margin ratios and quantities) are not read. The control rule (§7,
S03 §17.3 with §19.4's reading) follows; then §18.4(c)'s margin rows and the thin-margin list (a
disclosure: it moves no classification), §8's three-tool X31 table and clause, the controls'
tool-model distances and S03 §7.4's perturbation response table with a BioSTEAM column.

It imports S03's classifier for the tolerance, the specification definitions, the quantity reader,
the movement and rule 4 (§12 WO-S09-3) and never changes it or anything it writes (A02). It is
mechanical: no tolerance, setting, mapping or case is chosen here, and the verdict is the `verdict`
agent's (WO-S09-4). The gate never runs a tool: `tests/test_s09_references.py` recomputes the
document from the committed records and requires it to equal `comparison.json` (A13).

Usage (repository root, project environment, `PYTHONPATH=src:.`):
    python scripts/s09_reference_comparison.py --write     # (re)write comparison.json, SHA256SUMS
    python scripts/s09_reference_comparison.py --check     # exit 1 unless both recompute
    python scripts/s09_reference_comparison.py --markdown  # the table, for the verdict
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s03_reference_comparison as s03  # noqa: E402  (S03's classifier, imported, never changed)

ROOT = s03.ROOT
REFERENCES = ROOT / "benchmarks" / "s09" / "references"
RESULTS = REFERENCES / "results"
QUALIFICATION = REFERENCES / "qualification"
TABLE = REFERENCES / "comparison.json"
SUMS = REFERENCES / "SHA256SUMS"
CASES9_PATH = ROOT / "docs" / "derivations" / "scripts" / "s09_cases.json"
CASES3_PATH = s03.CASES_PATH
TWIN_PATH = s03.TWIN_PATH
CMP3_PATH = s03.TABLE
OURS_RESULTS = s03.RESULTS
ENVIRONMENTS = ROOT / "docs" / "reference-environments.md"

SCHEMA = "s09-reference-comparison-v1"
TOOL = "BioSTEAM"
S03_TOOLS = ("DWSIM", "IDAES")
ALL_TOOLS = (TOOL, *S03_TOOLS)
RUNG_NAMES = ("R1", "R2", "R3", "R4")
#: §8.1: the counted cases and the inverse kinds reported beside them (S03 §17.5).
X31_CASES = s03.X31_CASES
INVERSE_KINDS = s03.INVERSE_KINDS
NUMBER_WORDS = {2: "two", 3: "three"}
#: kmol/h and kJ/h per mol/s and W, exactly (§5.6, claim C8).
PER_SECOND = Decimal("3.6")
PRECISION = s03.PRECISION
_exact = s03._exact
dec = s03.dec
TENTH = s03.TENTH


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def settings(cases9: dict[str, Any]) -> dict[str, Any]:
    return dict(cases9["tool_settings"][TOOL])


def thresholds(cases9: dict[str, Any]) -> dict[str, Decimal]:
    """The registered thresholds BioSTEAM adds (§6.2, §6.3), read from `s09_cases.json`."""
    ts = settings(cases9)
    return {
        "B3": Decimal(ts["rule2"]["stage_component_mol_per_s"]),
        "B4": Decimal(ts["rule2"]["equilibrium"]),
        "B5_component": Decimal(ts["rule2"]["overall_component_mol_per_s"]),
        "B5_energy": Decimal(ts["rule2"]["overall_energy_W"]),
        "total_condenser_vapour": Decimal(ts["rule2c_added"]["total_condenser_vapour_mol_per_s"]),
        "thin_level": Decimal(ts["margin"]["thin_level"]),
    }


def documented_fingerprint() -> str:
    """`docs/reference-environments.md` §9's pip-freeze SHA-256 (§6.5): one value, however often
    the section quotes it."""
    text = ENVIRONMENTS.read_text(encoding="utf-8")
    section = text.split("## 9. ", 1)[1].split("\n## ", 1)[0]
    found = set(re.findall(r"pip freeze sha256: ([0-9a-f]{64})", section))
    if len(found) != 1:
        raise ValueError(f"docs/reference-environments.md §9 has {len(found)} fingerprints")
    return found.pop()


def verify_s03_pins(cases9: dict[str, Any]) -> dict[str, str]:
    """§0: S09 reads S03's three files at their pinned SHA-256 and refuses otherwise (A02)."""
    out = {}
    for path, pinned in cases9["s03_pins"].items():
        got = sha256(ROOT / path)
        if got != pinned:
            raise ValueError(f"{path} has SHA-256 {got}, not S09 §0's pin {pinned}")
        out[path] = got
    return out


# ---- the registered side ------------------------------------------------------------------------


def inputs_case(case_id: str, cases9: dict[str, Any]) -> str:
    """The S03 case whose inputs a pair runs: PC-LB runs RC1's (§7)."""
    return str(cases9["ours_aliases"].get(case_id, case_id))


def twin_case(case_id: str, cases9: dict[str, Any]) -> str:
    """The twin a pair is judged against: our side's case (PC-LB is RC1's record, §3)."""
    return inputs_case(case_id, cases9)


def latent_heats(case_id: str, cases9: dict[str, Any]) -> dict[str, Decimal]:
    """§4.2: `Hvap_i` = `L_VAP[i]`, PC-LB's §7 values for PC-LB."""
    control = cases9["controls"].get(case_id, {})
    if "Hvap_J_per_mol_PC-LB" in control:
        values = control["Hvap_J_per_mol_PC-LB"]
        return {c: Decimal(v) for c, v in zip(s03.fx.COMPONENTS, values, strict=True)}
    return {c: dec(s03.fx.L_VAP[c]) for c in s03.fx.COMPONENTS}


# ---- a run's raw fields, in our stage numbering -------------------------------------------------


@_exact
def view(run: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    """The raw fields every rule and quantity is computed from, in S03's normalized form.

    `profile.stages` (our stage j is index j − 1), `profile.products` (outs[0] the vapour of stage
    0, outs[1] the liquid of stage N − 1, outs[2] the side draw of a total condenser) and
    `profile.inlets`. §5.6: for a total condenser the top product is the side draw and the reflux
    (S03's `L[1]` slot) is stage 0's liquid less the side draw; the stage duty is the record's
    computed duty (positive into the stage).
    """
    prof = run["profile"]
    st = prof["stages"]
    n = int(case["stage_count"])
    total = case["condenser"] == "total"
    reg_p = [dec(p) for p in case["stage_pressures_Pa"]]
    products = prof["products"]
    top = products[2] if total else products[0]
    bottom = products[1]

    def comp(s: dict[str, Any]) -> dict[str, Decimal]:
        return {c: dec(x) for c, x in s["mol_per_s"].items()}

    v: dict[str, Any] = {"n": n, "stage_count_raw": len(st)}
    v["T"] = [s["T_K"] for s in st]
    v["L"] = [s["L_mol_per_s"] for s in st]
    v["V"] = [s["V_mol_per_s"] for s in st]
    if total:
        if "L[1]" in dict(case["quantities"]):
            raise ValueError("a total-condenser case registers L[1] beside the reflux")
        # binary64 subtraction of the two recorded doubles (exact, then rounded once)
        v["L"][0] = float(st[0]["L_mol_per_s"]) - float(top["F_mol_per_s"])
    v["top"] = {"flow": dec(top["F_mol_per_s"]), "comp": comp(top)}
    v["bottom"] = {"flow": dec(bottom["F_mol_per_s"]), "comp": comp(bottom)}
    v["inlet_comps"] = [comp(s) for s in prof["inlets"]]
    v["product_comps"] = [comp(s) for s in products]
    v["inlet_enthalpy_W"] = [dec(s["H_kJ_per_h"]) / PER_SECOND for s in prof["inlets"]]
    v["product_enthalpy_W"] = [dec(s["H_kJ_per_h"]) / PER_SECOND for s in products]
    ends: dict[str, int] = {}
    if case["condenser"] != "none":
        ends["Q_condenser"] = 0
    if case["reboiler"] != "none":
        ends["Q_reboiler"] = n - 1
    v["duties"] = {q: dec(st[i]["duty_W"]) for q, i in ends.items()}
    v["duty_floats"] = {
        q: (st[ends[q]]["duty_W"] if q in ends else None) for q in ("Q_condenser", "Q_reboiler")
    }
    v["stage_duties_W"] = [dec(s["duty_W"]) for s in st]
    v["intermediate_duties_W"] = [
        dec(s["duty_W"]) for i, s in enumerate(st) if i not in ends.values()
    ]
    v["vapour_product_mol_per_s"] = sum(
        (dec(x) for x in products[0]["mol_per_s"].values()), Decimal(0)
    )
    pressures = [(f"stage {i + 1}", dec(s["P_Pa"]), reg_p[min(i, n - 1)]) for i, s in enumerate(st)]
    names = ("vapour of stage 1", f"liquid of stage {n}", "side draw of stage 1")
    at = (0, n - 1, 0)
    for k, s in enumerate(products):
        pressures.append((f"product {names[k]}", dec(s["P_Pa"]), reg_p[at[k]]))
    v["pressures"] = pressures
    return v


def _finite(x: Any) -> Decimal:
    """A recorded number as an exact decimal; NaN for a missing or non-finite one (a check that
    reads it then fails, never passes)."""
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return Decimal("NaN")
    return dec(x)


def _passes(value: Decimal, threshold: Decimal) -> bool:
    return not value.is_nan() and value <= threshold


def _fmt(value: Decimal) -> str:
    return "nan" if value.is_nan() else f"{float(value):.4g}"


# ---- rule 1 -------------------------------------------------------------------------------------


def rule1(record: dict[str, Any], cases9: dict[str, Any]) -> str | None:
    """§6.5: the pip-freeze fingerprint of `docs/reference-environments.md` §9
    and §2.1's versions."""
    fp = record.get("environment_fingerprint") or {}
    expected = documented_fingerprint()
    if fp.get("pip_freeze_sha256") != expected:
        return (
            "environment fingerprint differs from docs/reference-environments.md §9: "
            f"{fp.get('pip_freeze_sha256')}"
        )
    registered = {k: v for k, v in settings(cases9)["environment"].items() if k != "lock"}
    versions = fp.get("versions") or {}
    differing = sorted(k for k in registered if versions.get(k) != registered[k])
    if differing:
        return f"versions differ from S09 §2.1: {differing}"
    return None


# ---- rule 2 (§6.2, B2 per §18.3) ----------------------------------------------------------------


def fsolve_rung(rung_index: int, cases9: dict[str, Any]) -> bool:
    """§18.3 (claim C12): R3 (`simultaneous correction`, `hybr`) is the rung that runs fsolve."""
    algorithm, method = settings(cases9)["rungs"][rung_index]
    return bool(algorithm == "simultaneous correction" and method == "hybr")


@_exact
def psat_ratio(component: str, t: Decimal, p: Decimal) -> Decimal:
    """K_c = Psat_c(T)/P from SYN-001's closed form at T06's pinned constants (§4.2), which §4.3's
    readback ties to the tool's `Psat` within 1e-14 relative."""
    fx = s03.fx
    exponent = (dec(fx.L_VAP[component]) / dec(fx.R_GAS)) * (1 / dec(fx.T_BOIL[component]) - 1 / t)
    return dec(fx.P_REF) * exponent.exp() / p


@_exact
def rule2(
    run: dict[str, Any], rung_index: int, case: dict[str, Any], cases9: dict[str, Any]
) -> tuple[str | None, dict[str, Any]]:
    """B1–B5 from the run's raw fields: both passes' exceptions and counters, each stage's inlet
    and outlet flows, T, P, x and y, the inlets' and products' flows and enthalpies, the stage
    duties."""
    th = thresholds(cases9)
    maxiter = int(settings(cases9)["common"]["maxiter"])
    path, prof = run["path"], run["profile"]
    passes = (path["pass1"], path["pass2"])
    failed: list[str] = []
    detail: dict[str, Any] = {}

    exceptions = [p.get("exception") for p in passes]
    detail["B1_exceptions"] = exceptions
    if any(e is not None for e in exceptions):
        failed.append(f"B1({exceptions[0] or exceptions[1]})")

    fsolve = fsolve_rung(rung_index, cases9)
    counts: list[int | None] = []
    ok2 = True
    for p in passes:
        if fsolve:
            f = p.get("fsolve") or {}
            count = f.get("nfev") if f.get("ran") is True else None
        else:
            count = p.get("iter")
        counts.append(None if count is None else int(count))
        ok2 = ok2 and count is not None and int(count) < maxiter
    detail["B2"] = {"counter": "fsolve nfev" if fsolve else "iter", "counts": counts}
    if not ok2:
        failed.append(f"B2({detail['B2']['counter']} {counts} of {maxiter})")

    b3 = Decimal(0)
    for st in prof["stages"]:
        for c in s03.fx.COMPONENTS:
            r = sum((_finite(s[c]) for s in st["in_mol_per_s"]), Decimal(0)) - sum(
                (_finite(s[c]) for s in st["out_mol_per_s"]), Decimal(0)
            )
            b3 = r.copy_abs() if r.is_nan() or b3.is_nan() else max(b3, abs(r))
    detail["B3_max_mol_per_s"] = float(b3)
    if not _passes(b3, th["B3"]):
        failed.append(f"B3({_fmt(b3)} mol/s)")

    total = case["condenser"] == "total"
    b4, one_phase = Decimal(0), []
    for j, st in enumerate(prof["stages"]):
        liquid, vapour = _finite(st["L_mol_per_s"]), _finite(st["V_mol_per_s"])
        t, p = _finite(st["T_K"]), _finite(st["P_Pa"])
        if t.is_nan() or p.is_nan():
            b4 = Decimal("NaN")
            continue
        k = {c: psat_ratio(c, t, p) for c in s03.fx.COMPONENTS}
        if total and j == 0 and liquid > 0:
            r = abs(sum((k[c] * _finite(st["x"][c]) for c in k), Decimal(0)) - 1)
        elif liquid > 0 and vapour > 0:
            r = max(abs(_finite(st["y"][c]) - k[c] * _finite(st["x"][c])) for c in k)
        else:
            one_phase.append(j)
            continue
        b4 = Decimal("NaN") if r.is_nan() or b4.is_nan() else max(b4, r)
    detail["B4_max"] = float(b4)
    detail["B4_one_phase_stages"] = one_phase
    if not _passes(b4, th["B4"]):
        failed.append(f"B4({_fmt(b4)})")

    comp = {
        c: sum((_finite(s["mol_per_s"][c]) for s in prof["inlets"]), Decimal(0))
        - sum((_finite(s["mol_per_s"][c]) for s in prof["products"]), Decimal(0))
        for c in s03.fx.COMPONENTS
    }
    b5c = max(abs(r) for r in comp.values())
    energy = (
        sum((_finite(s["H_kJ_per_h"]) / PER_SECOND for s in prof["inlets"]), Decimal(0))
        + sum((_finite(s["duty_W"]) for s in prof["stages"]), Decimal(0))
        - sum((_finite(s["H_kJ_per_h"]) / PER_SECOND for s in prof["products"]), Decimal(0))
    )
    detail["B5_component_max_mol_per_s"] = float(b5c)
    detail["B5_energy_W"] = float(energy)
    if not _passes(b5c, th["B5_component"]):
        failed.append(f"B5_component({_fmt(b5c)} mol/s)")
    if not _passes(abs(energy), th["B5_energy"]):
        failed.append(f"B5_energy({_fmt(energy)} W)")
    detail["failed"] = failed
    return ("; ".join(failed) or None), detail


# ---- rule 2c (S03's, unchanged, with §6.3's additions) ------------------------------------------


def native(case: dict[str, Any], end: str) -> bool:
    """§2.2 / `s09_cases.json → native_specifications`: whether an end's registered specification
    has a native stage specification with S03 §5.1 row 9's definition."""
    spec = case["specifications"][end]
    kind, n = spec["kind"], int(case["stage_count"])
    if end == "condenser" and kind == "reflux_ratio":
        return True
    if end == "reboiler" and kind in ("boilup_ratio", "bottoms_rate"):
        return True
    if kind == "duty":
        return True
    if kind == "temperature":
        return int(spec["stage"]) == (1 if end == "condenser" else n)
    return False


def expected_specifications(
    case: dict[str, Any], level: str, x: float | None
) -> list[tuple[int, str, str | None, float]]:
    """§6.3 / §5.6 / §5.2 P3: each stored native value after the exact conversion, in binary64, as
    `(stage, specification, specified_variable, stored)`. At L2(c) the adjusted end stores the run's
    final x (condenser: `Reflux` x, so B = 1/x; reboiler: `Boilup` x)."""
    n = int(case["stage_count"])
    total = case["condenser"] == "total"
    fed = sum((Decimal(f) for i in case["inlets"] for f in i["n_mol_per_s"]), Decimal(0))
    out: list[tuple[int, str, str | None, float]] = []
    for end, spec in case["specifications"].items():
        stage = 0 if end == "condenser" else n - 1
        kind, value = spec["kind"], float(spec["value"])
        if not native(case, end):
            if level != "L2(c)" or x is None:
                raise ValueError(f"{end} {kind} has no native option at {level}")
            if end == "condenser" and total:
                raise ValueError("an adjusted Reflux on a total condenser is not registered")
            if end == "condenser":
                out.append((stage, "Reflux", "B", 1.0 / x))
            else:
                out.append((stage, "Boilup", "B", x))
        elif kind == "reflux_ratio" and total:
            out.append((stage, "Reflux", "B", 0.0))
            out.append((stage, "bottom_side_draw", None, 1.0 / (1.0 + value)))
        elif kind == "reflux_ratio":
            out.append((stage, "Reflux", "B", math.inf if value == 0 else 1.0 / value))
        elif kind == "boilup_ratio":
            out.append((stage, "Boilup", "B", value))
        elif kind == "bottoms_rate":
            out.append((stage, "Flow", "F", value / float(fed)))
        elif kind == "duty":
            out.append((stage, "Duty", "Q", float(PER_SECOND) * value))
        elif kind == "temperature":
            out.append((stage, "Temperature", "T", value))
    return out


def specification_readback(
    run: dict[str, Any], case: dict[str, Any], level: str, x: float | None
) -> str | None:
    """§6.3: after pass 2, each specified stage's `specified_variable` and stored value equal the
    registered ones exactly in binary64; at L2(c) the run is at the final x."""
    if level == "L2(c)" and run.get("x") != x:
        return f"x({run.get('x')!r} against {x!r})"
    rows = run["rule2c"]["checks"]["specification_readback"]["rows"]
    got = {(int(r["stage"]), r["specification"]): r for r in rows}
    expected = expected_specifications(case, level, x)
    if sorted(got) != sorted((s, name) for s, name, _, _ in expected):
        return f"rows({sorted(got)})"
    for stage, name, variable, stored in expected:
        r = got[stage, name]
        if variable is not None and r.get("specified_variable") != variable:
            return f"{stage}, {r.get('specified_variable')}"
        value = r.get("stored")
        if not isinstance(value, int | float) or float(value) != stored:
            return f"{stage}, {value!r}"
    return None


def property_readback(record: dict[str, Any], case_id: str, cases9: dict[str, Any]) -> str | None:
    """§4.3's checks from the readback's raw values against `s09_cases.json → readback`. Returns
    the first failing item's name."""
    reg = settings(cases9)["readback"]
    items = record["property_package"]["readback"]["items"]
    comps = s03.fx.COMPONENTS
    temps = [Decimal(t) for t in reg["temperatures_K"]]

    def at_temps(rows: list[dict[str, Any]], key: str = "T_K") -> bool:
        return [dec(r[key]) for r in rows] == temps

    try:
        psat = items["Psat"]["values"]
        worst = Decimal(0)
        for c in comps:
            if not at_temps(psat[c]):
                return "Psat"
            for row, value in zip(psat[c], reg["Psat_Pa"][c], strict=True):
                r = abs(_finite(row["tool"]) - Decimal(value)) / Decimal(value)
                worst = r if r.is_nan() else max(worst, r)
        if not _passes(worst, Decimal(reg["Psat_relative"])):
            return "Psat"
        latent = items["latent"]
        hvap = latent_heats(case_id, cases9)
        if any(dec(latent["Hvap_J_per_mol"][c]) != hvap[c] for c in comps):
            return "latent"
        for c in comps:
            if not at_temps(latent["values"][c]):
                return "latent"
            for row in latent["values"][c]:
                r = abs(_finite(row["hV_minus_hL_minus_Hvap"])) / hvap[c]
                if not _passes(r, Decimal(reg["latent_relative"])):
                    return "latent"
        pairs = list(zip(temps, temps[1:], strict=False))
        for c in comps:
            rows = items["cp"]["values"][c]
            if [(dec(r["T1_K"]), dec(r["T2_K"])) for r in rows] != pairs:
                return "cp"
            for row in rows:
                if not _passes(
                    abs(_finite(row["residual_J_per_mol"])), Decimal(reg["cp_J_per_mol"])
                ):
                    return "cp"
        offset = Decimal(reg["datum_offset_J_per_mol"])
        for c in comps:
            rows = items["datum"]["values"][c]
            if not at_temps(rows):
                return "datum"
            for row in rows:
                dev = abs(_finite(row["hL_minus_cp_T_minus_T_r"]) - offset)
                if not _passes(dev, Decimal(reg["datum_offset_abs_J_per_mol"])):
                    return "datum"
        if items["liquid_pressure_dependence"]["H_at_1.5P_r_minus_H_at_P_r_kJ_per_h"] != 0:
            return "liquid_pressure_dependence"
        for c in comps:
            for prop in ("Psat", "Hvap"):
                m = items["methods"]["values"][c][prop]
                if m["method"] != "USER_METHOD" or m["all_methods"] != ["USER_METHOD"]:
                    return "methods"
        if items["thermo_classes"]["values"] != reg["thermo_classes"]:
            return "thermo_classes"
    except (KeyError, TypeError, ValueError):
        return "readback_record"
    return None


@_exact
def rule2c(
    record: dict[str, Any],
    run: dict[str, Any],
    case_id: str,
    case: dict[str, Any],
    v: dict[str, Any],
    specs: dict[str, dict[str, Any]],
    cases9: dict[str, Any],
    x: float | None,
) -> tuple[str | None, dict[str, Any]]:
    """S03 §7.1 rule 2c unchanged (stage count and map, inlet stages, pressures within 1e-3 Pa,
    intermediate duties within 1e-3 W from §5.6's computed duty, the specification by S03 §5.1
    row 9 within 1e-4), then §6.3's total-condenser vapour, specification read-back and property
    readback. The adiabatic-stage duty is the intermediate-duty check (§6.2)."""
    th = thresholds(cases9)
    level = record["level"]
    inspection = record["levels"][level]["inspection"]
    n = v["n"]
    smap = inspection["stage_map"]
    counts = (int(smap["len_stages"]), int(v["stage_count_raw"]), len(smap["map"]))
    detail: dict[str, Any] = {"stage_counts": list(counts)}
    if any(c != n for c in counts):
        return f"stage_count({list(counts)} against {n})", detail
    bad = [j for j, i in smap["map"].items() if int(i) != int(j) - 1]
    if sorted(int(j) for j in smap["map"]) != list(range(1, n + 1)) or bad:
        return f"stage_map({bad})", detail
    registered = [int(i["stage"]) for i in case["inlets"]]
    entered = [int(s) + 1 for s in inspection["feed_stages"]["tool"]]
    detail["feed_stages"] = entered
    if entered != registered:
        return f"feed_stage({entered} against {registered})", detail
    worst_p, where_p = Decimal(0), None
    for where, value, reg in v["pressures"]:
        dev = abs(value - reg)
        if dev.is_nan() or dev > worst_p:
            worst_p, where_p = dev, where
        if dev.is_nan():
            break
    detail["pressure_max_abs_dev_Pa"] = float(worst_p)
    if worst_p.is_nan() or worst_p > s03.RULE2C_PRESSURE_PA:
        return f"pressure({float(worst_p):.4g} Pa at {where_p})", detail
    inter = max((abs(q) for q in v["intermediate_duties_W"]), default=Decimal(0))
    detail["intermediate_duty_max_abs_W"] = float(inter)
    if not _passes(inter, s03.RULE2C_INTERMEDIATE_DUTY_W):
        return f"intermediate_duty({_fmt(inter)} W)", detail
    if case["condenser"] == "total":
        vapour = abs(v["vapour_product_mol_per_s"])
        detail["total_condenser_vapour_mol_per_s"] = float(vapour)
        if not _passes(vapour, th["total_condenser_vapour"]):
            return f"total_condenser_vapour({_fmt(vapour)})", detail
    readback = specification_readback(run, case, level, x)
    if readback is not None:
        return f"specification_readback({readback})", detail
    item = property_readback(record, case_id, cases9)
    if item is not None:
        return f"property_mapping({item})", detail
    for end, s in specs.items():
        if not s["rule2c_passes"]:
            return f"specification_{end}_{s['kind']}({s['relative_difference']:.4g})", detail
    return None, detail


# ---- one run through rules 2–2d's specification residual ----------------------------------------


def final_x(rung: dict[str, Any], level: str) -> float | None:
    """The adjusted specification's value at L2(c): the outer loop's returned x (§5.4)."""
    if level != "L2(c)":
        return None
    outer = rung.get("outer") or {}
    x = outer.get("returned_x")
    return None if x is None else float(x)


def assess_run(
    record: dict[str, Any],
    run: dict[str, Any] | None,
    rung_index: int,
    case_id: str,
    case: dict[str, Any],
    cases9: dict[str, Any],
    x: float | None,
) -> dict[str, Any]:
    """Rules 2, 2c and 2d's specification residual on one run, recomputed from its raw fields."""
    if run is None or run.get("harness_error") or "profile" not in run:
        why = "no run" if run is None else f"record not readable: {run.get('harness_error')}"
        return {"rule": 2, "problem": why, "category": "reference_accuracy"}
    v = view(run, case)
    problem, d2 = rule2(run, rung_index, case, cases9)
    out: dict[str, Any] = {"view": v, "rule2": d2}
    if problem is not None:
        return {**out, "rule": 2, "problem": problem, "category": "reference_accuracy"}
    specs = s03.specification_values(v, case)
    out["specs"] = specs
    problem, out["rule2c"] = rule2c(record, run, case_id, case, v, specs, cases9, x)
    if problem is not None:
        return {**out, "rule": "2c", "problem": problem, "category": "semantics"}
    for end, s in specs.items():
        if not s["rule2d_passes"]:
            problem = f"specification_residual_{end}_{s['kind']}({s['rule2d_measure']:.4g})"
            return {**out, "rule": "2d", "problem": problem, "category": "reference_accuracy"}
    out["quantities"] = s03.tool_quantities(v, case)
    return {**out, "rule": None, "problem": None}


def rerun_check(
    record: dict[str, Any],
    rung: dict[str, Any],
    base: dict[str, Any],
    case_id: str,
    case: dict[str, Any],
    twin: dict[str, dict[str, str]],
    cases9: dict[str, Any],
) -> tuple[str | None, dict[str, Any]]:
    """§18.4(b): a fresh build at 1e-9 (both tolerances), at L2(c) one evaluation at the run's final
    x; rules 2 and 2c; no registered quantity moved by more than 0.1 tolerance (the twin's)."""
    floor = settings(cases9)["floor_rerun"]
    rerun = (rung.get("accuracy_rerun") or {}).get("run")
    level = record["level"]
    x = final_x(rung, level)
    if rerun is None or rerun.get("harness_error") or "profile" not in rerun:
        return "rerun_not_run", {}
    applied = rerun["path"]["applied"]
    wanted = (float(floor["tolerance"]), float(floor["relative_tolerance"]))
    if (applied.get("tolerance"), applied.get("relative_tolerance")) != wanted:
        return (
            f"rerun_settings({applied.get('tolerance')}, {applied.get('relative_tolerance')})",
            {},
        )
    got = assess_run(record, rerun, int(rung["rung_index"]), case_id, case, cases9, x)
    if got["rule"] in (2, "2c"):
        return f"rerun_rule{got['rule']}({got['problem']})", {}
    quantities = s03.tool_quantities(got["view"], case)
    moved = s03.movement(case, twin, base, quantities)
    detail = {"max_ratio": moved["max_ratio"], "max_quantity": moved["max_quantity"]}
    if moved["_exceeds"]:
        return f"rerun_movement({moved['max_ratio']:.4g} at {moved['max_quantity']})", detail
    return None, detail


@_exact
def level_assessment(
    record: dict[str, Any],
    case_id: str,
    case: dict[str, Any],
    twin: dict[str, dict[str, str]],
    cases9: dict[str, Any],
) -> dict[str, Any]:
    """Every rung of the selected level, recomputed: which pass rules 2–2c and the specification
    residual (the set §6.4's path dependence compares), which also pass the rerun (§2.3 step 1's
    selection, recomputed), and the largest pairwise movement in the twin's tolerance."""
    level = record["level"]
    rungs = record["levels"][level]["rungs"]
    by_name = {r["rung"]: r for r in rungs}
    if sorted(by_name) != list(RUNG_NAMES):
        raise ValueError(f"({case_id}, {TOOL}) {level} records rungs {sorted(by_name)}")
    assessed: dict[str, dict[str, Any]] = {}
    for name in RUNG_NAMES:
        rung = by_name[name]
        x = final_x(rung, level)
        got = assess_run(record, rung.get("run"), int(rung["rung_index"]), case_id, case, cases9, x)
        if got["problem"] is None:
            got["rerun_problem"], got["rerun"] = rerun_check(
                record, rung, got["quantities"], case_id, case, twin, cases9
            )
        assessed[name] = got
    through = [n for n in RUNG_NAMES if assessed[n]["problem"] is None]
    selected = next((n for n in through if assessed[n]["rerun_problem"] is None), None)
    worst: dict[str, Any] = {"max_ratio": 0.0, "max_quantity": None, "pair": None}
    exceeds = False
    for i, a in enumerate(through):
        for b in through[i + 1 :]:
            m = s03.movement(case, twin, assessed[a]["quantities"], assessed[b]["quantities"])
            exceeds = exceeds or m["_exceeds"]
            if m["max_ratio"] > worst["max_ratio"] or worst["pair"] is None:
                worst = {"max_ratio": m["max_ratio"], "max_quantity": m["max_quantity"]}
                worst["pair"] = f"{a}-{b}"
    return {
        "assessed": assessed,
        "through_specification": through,
        "selected_recomputed": selected,
        "path_dependence": {
            "compared_rungs": through,
            "max_ratio": worst["max_ratio"] if len(through) > 1 else None,
            "max_quantity": worst["max_quantity"],
            "pair": worst["pair"],
            "tolerance_value_used": "the twin's (S09 §6.4)",
            "fires": exceeds,
        },
    }


# ---- one pair -----------------------------------------------------------------------------------


def outer_summary(
    rung: dict[str, Any], level: str, specs: dict[str, dict[str, Any]], cases9: dict[str, Any]
) -> dict[str, Any] | None:
    """A18 / §18.4(c): the outer evaluations' count and the final |g|/ytol, recomputed from the
    selected run's specification value (recorded and reported, never a margin row)."""
    if level != "L2(c)":
        return None
    outer = rung.get("outer") or {}
    evaluations = outer.get("evaluations") or []
    case_end = [e for e, s in specs.items() if s["kind"] == outer.get("kind")]
    ytol_value, basis = settings(cases9)["outer_loop"]["ytol"][outer["kind"]]
    s = specs[case_end[0]]
    g = s["_relative"] if basis == "relative" else s["_accuracy"]
    return {
        "kind": outer["kind"],
        "end": case_end[0],
        "evaluations": len(evaluations),
        "evaluations_passed_inner_checks": sum(1 for e in evaluations if e.get("failed") is None),
        "returned_x": outer.get("returned_x"),
        "final_abs_g": float(abs(g)),
        "ytol": ytol_value,
        "final_abs_g_over_ytol": s03.ratio(abs(g), Decimal(ytol_value)),
    }


@_exact
def margin(
    case: dict[str, Any],
    got: dict[str, Any],
    rerun: dict[str, Any],
    path: dict[str, Any],
    cases9: dict[str, Any],
) -> dict[str, Any]:
    """§18.4(c): the closed list of margin rows of the selected record, recomputed, each as a
    ratio to its threshold; the largest and its row; thin above 0.1 (a disclosure only)."""
    th = thresholds(cases9)
    d2, d2c, specs = got["rule2"], got["rule2c"], got["specs"]
    r = {
        "B3_stage_component": s03.ratio(dec(d2["B3_max_mol_per_s"]), th["B3"]),
        "B4_equilibrium": s03.ratio(dec(d2["B4_max"]), th["B4"]),
        "B5_component": s03.ratio(dec(d2["B5_component_max_mol_per_s"]), th["B5_component"]),
        "B5_energy": s03.ratio(abs(dec(d2["B5_energy_W"])), th["B5_energy"]),
        "rule2c_adiabatic_duty": s03.ratio(
            dec(d2c["intermediate_duty_max_abs_W"]), s03.RULE2C_INTERMEDIATE_DUTY_W
        ),
    }
    if case["condenser"] == "total":
        r["rule2c_total_condenser_vapour"] = s03.ratio(
            dec(d2c["total_condenser_vapour_mol_per_s"]), th["total_condenser_vapour"]
        )
    r["rule2d_specification"] = max(
        s03.ratio(s["_accuracy"], Decimal(s["rule2d_threshold"])) for s in specs.values()
    )
    r["rule2d_rerun_movement"] = s03.ratio(dec(rerun["max_ratio"]), TENTH)
    if path["max_ratio"] is not None:
        r["rule2d_path_spread"] = s03.ratio(dec(path["max_ratio"]), TENTH)
    row = max(r, key=lambda k: (r[k], k))
    return {
        "ratios": r,
        "max_ratio": r[row],
        "max_row": row,
        "thin": r[row] > float(th["thin_level"]),
    }


def _label(classification: str, category: str | None, reason: str) -> str:
    return s03._label(classification, category, reason)


@_exact
def classify(
    case_id: str,
    record: dict[str, Any] | None,
    ours: dict[str, Any] | None,
    cases3: dict[str, Any],
    cases9: dict[str, Any],
    ref: dict[str, Any],
) -> dict[str, Any]:
    """S03 §7.1's rules 0–4 in order (§6.5) on one (case, BioSTEAM) pair (no control rule)."""
    row: dict[str, Any] = {"case": case_id, "tool": TOOL}

    def result(classification: str, category: str | None, reason: str, rule: Any) -> dict:
        return {
            **row,
            "classification": classification,
            "category": category,
            "reason": reason,
            "label": _label(classification, category, reason),
            "rule": rule,
        }

    if case_id in cases9["not_applicable"]:
        if record is not None:
            raise ValueError(f"({case_id}, {TOOL}) is registered not_applicable but has a record")
        reason = (
            f"a registered absence with no record (S09 §3): {cases9['not_applicable'][case_id]}"
        )
        return {
            **result("not_applicable", None, reason, "registered_absence"),
            "label": "not_applicable",
        }
    if record is None:
        return result("NOT_COMPARABLE", "access", "no record", 1)
    if record.get("case") != case_id or record.get("tool") != TOOL:
        raise ValueError(f"the record for ({case_id}, {TOOL}) names {record.get('case')}")
    if not record.get("available"):
        reason = str(record.get("not_available_reason") or "not available")
        return result("NOT_COMPARABLE", "capability", reason, 0)
    case = cases3["cases"][inputs_case(case_id, cases9)]
    level = record["level"]
    row["level"] = level
    row["rung"] = record["selected_rung"]
    access = rule1(record, cases9)
    if access is not None:
        return result("NOT_COMPARABLE", "access", access, 1)
    twin = s03.twin_quantities(ref, twin_case(case_id, cases9))
    lv = level_assessment(record, case_id, case, twin, cases9)
    row["selection"] = {
        "recorded": record["selected_rung"],
        "recomputed": lv["selected_recomputed"],
    }
    rung = next(r for r in record["levels"][level]["rungs"] if r["rung"] == row["rung"])
    got = lv["assessed"][row["rung"]]
    if "rule2" in got:
        row["rule2"] = got["rule2"]
    if got["rule"] in (2, "2c"):
        if "rule2c" in got:
            row["rule2c"] = got["rule2c"]
        return result("NOT_COMPARABLE", got["category"], got["problem"], got["rule"])
    row["rule2c"] = got["rule2c"]
    specs = got["specs"]
    row["rule2d"] = {
        "specification": {
            e: {k: s[k] for k in s if not k.startswith("_")} for e, s in specs.items()
        },
        "path_dependence": lv["path_dependence"],
    }
    row["outer"] = outer_summary(rung, level, specs, cases9)
    if got["rule"] == "2d":
        return result("NOT_COMPARABLE", got["category"], got["problem"], "2d")
    if got["rerun_problem"] is not None:
        return result("NOT_COMPARABLE", "reference_accuracy", got["rerun_problem"], "2d")
    row["rule2d"]["rerun"] = got["rerun"]
    path = lv["path_dependence"]
    if path["fires"]:
        reason = f"path_dependence({path['max_ratio']:.4g} {path['pair']})"
        return result("NOT_COMPARABLE", "reference_accuracy", reason, "2d")
    row["margin"] = margin(case, got, got["rerun"], path, cases9)
    values = got["quantities"]

    kinds = dict(case["quantities"])
    if ours is None or ours.get("outcome") != "CONVERGED":
        status = None if ours is None else ours.get("outcome")
        return result("NOT_COMPARABLE", "ours_not_verified", f"ours: {status}", 3)
    ours_far = []
    for q in values:
        tol = s03.tolerance(kinds[q], Decimal(twin[q]["value"]))
        if abs(dec(ours["quantities"][q]) - Decimal(twin[q]["value"])) > TENTH * tol:
            ours_far.append(q)
    if ours_far:
        reason = f"ours more than 0.1 tolerance from the twin on {ours_far}"
        return result("NOT_COMPARABLE", "ours_not_verified", reason, 3)
    word, extra = s03.rule4(values, ours["quantities"], twin, kinds)
    return {**result(word, None, extra.pop("reason"), 4), **extra}


# ---- §7 controls, §8 three-tool X31, §7.3 distances, S03 §7.4 responses -------------------------


def apply_controls(rows: list[dict[str, Any]], cases9: dict[str, Any]) -> dict[str, Any]:
    """§7 (S03 §17.3 with §19.4's reading): BioSTEAM's pairs count iff PC-LB or PC-P classifies
    `DISAGREE`; a control `AGREE` stops the comparison; without a `DISAGREE` control every pair that
    reached rule 2 (other than the controls and rule 3's) becomes `control_not_comparable`."""
    by = {r["case"]: r for r in rows}
    controls = list(cases9["controls"])
    labels = {c: by[c]["label"] for c in controls}
    working = [c for c in controls if by[c]["classification"] == "DISAGREE"]
    agree = [c for c in controls if by[c]["classification"] == "AGREE"]
    summary = {
        "stopped": bool(agree),
        "per_tool": {
            TOOL: {
                "controls": labels,
                "disagree": working,
                "agree": agree,
                "pairs_count": bool(working) and not agree,
            }
        },
        "not_applicable": dict(cases9["not_applicable"]),
    }
    if working:
        return summary
    reason = "; ".join(f"{c} {labels[c]}" for c in controls)
    for r in rows:
        if r["case"] in controls or r["rule"] in (0, 1, 3, "registered_absence"):
            continue
        r["before_control_rule"] = {
            k: r[k] for k in ("classification", "category", "reason", "label", "rule")
        }
        r.update(
            classification="NOT_COMPARABLE",
            category="control_not_comparable",
            reason=reason,
            rule="17.3(b)",
        )
        r["label"] = _label("NOT_COMPARABLE", "control_not_comparable", reason)
    return summary


def case_outcome(pairs: dict[str, dict[str, Any]]) -> tuple[int, str]:
    """§8.1's table: the first matching row decides. Rows 1–4 are S03 §17.5's; 5–7 count AGREEs."""
    classes = {t: p["class"] for t, p in pairs.items()}
    words = {t: p["classification"] for t, p in pairs.items()}
    if any(c == "ours" for c in classes.values()):
        return 1, "not met: a column finding (S02 or S06)"
    if any(w == "DISAGREE" for w in words.values()):
        return 2, "not met: a disagreement finding, until the design lane resolves it"
    if any(c == "access" for c in classes.values()):
        return 3, "blocked"
    if any(c == "unusable" for c in classes.values()):
        return 4, "not met: an available reference could not be shown to see a known difference"
    agree = sorted(t for t, w in words.items() if w == "AGREE")
    absent = sorted(t for t, c in classes.items() if c == "absent")
    if len(agree) >= 2 and len(agree) + len(absent) == len(pairs):
        return 5, f"{NUMBER_WORDS[len(agree)]} references ({', '.join(agree)})"
    if len(agree) == 1 and len(absent) == len(pairs) - 1:
        return 6, f"one reference ({agree[0]}), absent: {', '.join(absent)}"
    if len(absent) == len(pairs):
        return 7, "no reference: not met"
    return 0, f"no row of S09 §8.1 matches: {classes}"


def clause(rows_hit: list[int], stopped: bool) -> str:
    """§8.2."""
    if stopped:
        return "stopped: a control classified AGREE (S03 §17.3(a)); no clause outcome is recorded"
    if any(r == 0 for r in rows_hit):
        return "undetermined: a pair outside §8.1's classes (a design-lane question)"
    if any(r in (1, 2, 4, 7) for r in rows_hit):
        return "not met"
    if any(r == 3 for r in rows_hit):
        return "blocked"
    if all(r == 5 for r in rows_hit):
        return "met with two references"
    return "met where available"


def x31_three_tool(
    rows: list[dict[str, Any]],
    cmp3: dict[str, Any],
    stopped: bool,
    tools: tuple[str, ...] = ALL_TOOLS,
) -> dict[str, Any]:
    """§8: per counted case and per inverse kind, IDAES's and DWSIM's classes read from S03's
    committed `comparison.json` (never re-classified) beside BioSTEAM's, the row and outcome; the
    clause. `tools` without BioSTEAM gives the reduction to S03's two tools (claim C9, A15)."""
    by = {r["case"]: r for r in rows}
    s03_rows = {(r["case"], r["tool"]): r for r in cmp3["rows"]}
    s03_x31 = {
        **cmp3["x31"]["cases"],
        **{v["case"]: v for v in cmp3["x31"]["inverse_kinds"].values()},
    }

    def entry(case_id: str) -> dict[str, Any]:
        pairs: dict[str, dict[str, Any]] = {}
        for tool in tools:
            if tool == TOOL:
                r = by[case_id]
                pairs[tool] = {"class": s03.pair_class(r), "source": "S09"}
            else:
                r = s03_rows[case_id, tool]
                pairs[tool] = {
                    "class": s03_x31[case_id]["pairs"][tool]["class"],
                    "source": "S03 comparison.json (pinned)",
                }
            pairs[tool].update(
                classification=r["classification"], label=r["label"], reason=r["reason"]
            )
        number, outcome = case_outcome(pairs)
        out: dict[str, Any] = {
            "pairs": {
                t: {k: p[k] for k in ("class", "classification", "label", "source")}
                for t, p in pairs.items()
            },
            "row": number,
            "outcome": outcome,
        }
        if number == 6:
            out["absent_reasons"] = {
                t: p["reason"] for t, p in pairs.items() if p["class"] == "absent"
            }
        return out

    cases = {c: entry(c) for c in X31_CASES}
    rows_hit = [cases[c]["row"] for c in X31_CASES]
    return {
        "tools": list(tools),
        "counted_cases": list(X31_CASES),
        "cases": cases,
        "clause": clause(rows_hit, stopped),
        "cases_row_5": [c for c in X31_CASES if cases[c]["row"] == 5],
        "count_row_5": sum(1 for r in rows_hit if r == 5),
        "cases_row_6": [c for c in X31_CASES if cases[c]["row"] == 6],
        "target": 4,
        "inverse_kinds": {k: {"case": c, **entry(c)} for c, k in INVERSE_KINDS.items()},
    }


def reduction(rows: list[dict[str, Any]], cmp3: dict[str, Any], stopped: bool) -> dict[str, Any]:
    """Claim C9 / A15: the table on S03's two tools alone reproduces S03's rows and clause."""
    two = x31_three_tool(rows, cmp3, stopped, tools=S03_TOOLS)
    got = {c: two["cases"][c]["row"] for c in X31_CASES}
    got |= {v["case"]: v["row"] for v in two["inverse_kinds"].values()}
    s03_rows = {c: cmp3["x31"]["cases"][c]["row"] for c in X31_CASES}
    s03_rows |= {v["case"]: v["row"] for v in cmp3["x31"]["inverse_kinds"].values()}
    return {
        "rows": got,
        "clause": two["clause"],
        "s03_rows": s03_rows,
        "s03_clause": cmp3["x31"]["clause"],
        "equal": got == s03_rows and two["clause"] == cmp3["x31"]["clause"],
    }


@_exact
def control_distances(
    rows: list[dict[str, Any]],
    values: dict[str, dict[str, float]],
    ref: dict[str, Any],
    cases3: dict[str, Any],
    cases9: dict[str, Any],
) -> dict[str, Any]:
    """§7: PC-LB's tool distance to `ref.controls.PC-LI.tool_model` over the tool-model value's own
    tolerance (S03 §7.3); PC-P's is `not_applicable(tool_model_differs)`."""
    by = {r["case"]: r for r in rows}
    out: dict[str, Any] = {}
    for cid, control in cases9["controls"].items():
        key = f"{cid}/{TOOL}"
        if cid == "PC-P":
            out[key] = {
                "classification": by[cid]["label"],
                "max_ratio": None,
                "reason": "not_applicable(tool_model_differs)",
                "statement": control["tool_model_distance"],
            }
            continue
        model = ref["controls"]["PC-LI"]
        if cid not in values:
            out[key] = {
                "classification": by[cid]["label"],
                "max_ratio": None,
                "reason": "no tool values (not available)",
            }
            continue
        ratios = {}
        for q, value in values[cid].items():
            entry = model["tool_model"][q]
            tm = Decimal(entry["value"])
            ratios[q] = s03.ratio(abs(dec(value) - tm), s03.tolerance(entry["kind"], tm))
        worst = max(ratios, key=lambda q: (ratios[q], q))
        out[key] = {
            "classification": by[cid]["label"],
            "tool_model": "s03_reference.json controls.PC-LI.tool_model (S09 §7, claim C4)",
            "max_ratio": ratios[worst],
            "argmax": worst,
            "registered_discrimination": model["max_ratio"],
        }
    return out


@_exact
def response_table(
    rows: list[dict[str, Any]],
    values: dict[str, dict[str, float]],
    ours: dict[str, dict[str, Any] | None],
    ref: dict[str, Any],
    cases3: dict[str, Any],
    cmp3: dict[str, Any],
) -> dict[str, Any]:
    """S03 §7.4 with a BioSTEAM column: Δy = y_pert − y_base per quantity for ours, each tool and
    the twin, with the bound tol(y_pert) + tol(y_base). IDAES's and DWSIM's columns and their
    `both_agree` are S03's committed values."""
    by = {r["case"]: r for r in rows}
    out = {}
    for pert, entry in ref["perturbations"].items():
        base = entry["base"]
        case_p, case_b = cases3["cases"][pert], cases3["cases"][base]
        s3 = cmp3["perturbation_response"][pert]
        s3_lines = {line["quantity"]: line for line in s3["quantities"]}
        bio = None
        if pert in values and base in values:
            bio = {q: values[pert][q] - values[base][q] for q in values[pert]}
        op, ob = ours.get(pert), ours.get(base)
        ours_ok = all(o is not None and o.get("outcome") == "CONVERGED" for o in (op, ob))
        lines = []
        for q, kind in case_p["quantities"]:
            tp = Decimal(ref["twin"][pert]["quantities"][q]["value"])
            tb = Decimal(ref["twin"][base]["quantities"][q]["value"])
            line = {
                "quantity": q,
                "twin": float(tp - tb),
                "ours": op["quantities"][q] - ob["quantities"][q] if ours_ok else None,
                "bound": float(s03.tolerance(kind, tp) + s03.tolerance(kind, tb)),
                TOOL: None if bio is None else bio[q],
            }
            for tool in S03_TOOLS:
                line[tool] = s3_lines[q][tool]
            lines.append(line)
        if dict(case_b["quantities"]) != dict(case_p["quantities"]):
            raise ValueError(f"{pert} and {base} register different quantities")
        both = {
            TOOL: by[pert]["classification"] == "AGREE" and by[base]["classification"] == "AGREE"
        }
        both |= {t: s3["both_agree"][t] for t in S03_TOOLS}
        out[pert] = {"base": base, "both_agree": both, "quantities": lines}
    return out


# ---- the document -------------------------------------------------------------------------------


def load_records(cases9: dict[str, Any], results: Path = RESULTS) -> dict[str, Any]:
    out: dict[str, dict[str, Any] | None] = {}
    for cid in [*cases9["pairs"], *cases9["not_applicable"]]:
        path = results / f"biosteam-{cid}.json"
        out[cid] = load_json(path) if path.exists() else None
    return out


def ours_path(case_id: str, cases9: dict[str, Any]) -> Path:
    return OURS_RESULTS / f"ours-{inputs_case(case_id, cases9)}.json"


def load_ours(cases9: dict[str, Any], cases3: dict[str, Any]) -> dict[str, Any]:
    """Our side: S03's committed records (§3), for the pairs and the perturbations' bases."""
    out: dict[str, dict[str, Any] | None] = {}
    for cid in [*cases9["pairs"], *cases3["cases"]]:
        path = ours_path(cid, cases9)
        out[cid] = load_json(path) if path.exists() else None
    return out


def selected_values(
    records: dict[str, Any], cases3: dict[str, Any], cases9: dict[str, Any]
) -> dict[str, dict[str, float]]:
    """Each available pair's registered quantities from its selected run's raw fields."""
    out = {}
    for cid in cases9["pairs"]:
        record = records.get(cid)
        if record is None or not record.get("available"):
            continue
        case = cases3["cases"][inputs_case(cid, cases9)]
        rung = next(
            r
            for r in record["levels"][record["level"]]["rungs"]
            if r["rung"] == record["selected_rung"]
        )
        if rung.get("run") is None or "profile" not in rung["run"]:
            continue
        out[cid] = s03.tool_quantities(view(rung["run"], case), case)
    return out


@_exact
def compute(
    records: dict[str, Any] | None = None,
    ours: dict[str, Any] | None = None,
    cases3: dict[str, Any] | None = None,
    cases9: dict[str, Any] | None = None,
    ref: dict[str, Any] | None = None,
    cmp3: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The whole comparison document. Every argument defaults to the committed file; the gate
    passes a live solve of our side (A13) or mutated copies (A09–A12, A18)."""
    cases9 = cases9 or load_json(CASES9_PATH)
    pins = verify_s03_pins(cases9)
    cases3 = cases3 or load_json(CASES3_PATH)
    ref = ref or load_json(TWIN_PATH)
    cmp3 = cmp3 or load_json(CMP3_PATH)
    records = load_records(cases9) if records is None else records
    ours = load_ours(cases9, cases3) if ours is None else ours
    ids = [*cases9["pairs"], *cases9["not_applicable"]]
    rows = [classify(cid, records.get(cid), ours.get(cid), cases3, cases9, ref) for cid in ids]
    controls = apply_controls(rows, cases9)
    values = selected_values(records, cases3, cases9)
    by = {r["case"]: r for r in rows}
    margin_rows = {
        cid: {"level": by[cid].get("level"), "rung": by[cid].get("rung"), **by[cid]["margin"]}
        for cid in cases9["pairs"]
        if by[cid].get("margin") is not None
    }
    thin = [
        {"case": cid, "row": m["max_row"], "ratio": m["max_ratio"]}
        for cid, m in margin_rows.items()
        if m["thin"]
    ]
    pairs = {
        cid: {
            "level": by[cid].get("level"),
            "rung": by[cid].get("rung"),
            "outer_evaluations": (by[cid].get("outer") or {}).get("evaluations", 0),
            "classification": by[cid]["classification"],
            "label": by[cid]["label"],
        }
        for cid in cases9["pairs"]
    }
    inputs = {rel(p): sha256(p) for p in sorted(QUALIFICATION.glob("*.json"))}
    inputs |= {rel(p): sha256(p) for p in sorted(RESULTS.glob("*.json"))}
    for path in sorted({ours_path(cid, cases9) for cid in ours if ours_path(cid, cases9).exists()}):
        inputs[rel(path)] = sha256(path)
    for path in (CASES9_PATH, CASES3_PATH, TWIN_PATH, CMP3_PATH):
        inputs[rel(path)] = sha256(path)
    ts = settings(cases9)
    return {
        "schema": SCHEMA,
        "authority": "docs/derivations/S09-spec.md §6-§8, §10, §18; A05, A09-A15, A18",
        "classification_is_mechanical": "the recorded verdict is the verdict agent's, on this "
        "document (S09 WO-S09-4)",
        "tolerance_rule": "|ours - tool| <= a_k + 1e-6 |v_twin|, v the twin's 25-digit value "
        "evaluated unrounded (S03 §6), no per-case or per-tool factor",
        "allowances": {k: str(a) for k, a in s03.ALLOWANCE.items()},
        "thresholds": {
            "rule2": dict(ts["rule2"]),
            "rule2c_s03": {
                "pressure_Pa": str(s03.RULE2C_PRESSURE_PA),
                "intermediate_duty_W": str(s03.RULE2C_INTERMEDIATE_DUTY_W),
                "specification_relative": str(s03.RULE2C_SPEC_RELATIVE),
            },
            "rule2c_added": dict(ts["rule2c_added"]),
            "rule2d_specification": {k: [str(t), b] for k, (t, b) in s03.RULE2D_SPEC.items()},
            "rule2d_rerun_and_path_fraction_of_tolerance": str(TENTH),
            "rule3_fraction_of_tolerance": str(TENTH),
        },
        "environment_fingerprint": {
            "pip_freeze_sha256": documented_fingerprint(),
            "source": "docs/reference-environments.md §9",
        },
        "s03_pins": pins,
        "inputs_sha256": inputs,
        "rows": rows,
        "pairs": pairs,
        "controls": controls,
        "comparison_stopped": controls["stopped"],
        "control_tool_model_distance": control_distances(rows, values, ref, cases3, cases9),
        "margin": {
            "rows": list(ts["margin"]["rows"]),
            "thin_level": ts["margin"]["thin_level"],
            "effect": ts["margin"]["effect"],
            "per_pair": margin_rows,
            "thin_margin": thin,
        },
        "not_comparable_and_disagree": [
            {"case": r["case"], "label": r["label"], "rule": r["rule"]}
            for r in rows
            if r["classification"] in ("NOT_COMPARABLE", "DISAGREE")
        ],
        "x31_three_tool": x31_three_tool(rows, cmp3, controls["stopped"]),
        "x31_reduction_to_s03": reduction(rows, cmp3, controls["stopped"]),
        "perturbation_response": response_table(rows, values, ours, ref, cases3, cmp3),
    }


def dumps(document: dict[str, Any]) -> str:
    return json.dumps(document, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def sums_text() -> str:
    """SHA256SUMS over the qualification record, every tool record and comparison.json (paths
    relative to `benchmarks/s09/references/`)."""
    paths = sorted(QUALIFICATION.glob("*.json")) + sorted(RESULTS.glob("*.json")) + [TABLE]
    return "".join(f"{sha256(p)}  {p.relative_to(REFERENCES)}\n" for p in paths)


def markdown(document: dict[str, Any]) -> str:
    lines = [
        "| Case | Classification | Level | Rung | Outer | Worst | Ratio | Margin |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in document["rows"]:
        worst = f"{r['worst_ratio']:.4g}" if "worst_ratio" in r else "—"
        m = r.get("margin")
        lines.append(
            f"| {r['case']} | {r['label'][:160]} | {r.get('level', '—')} | {r.get('rung', '—')} | "
            f"{(r.get('outer') or {}).get('evaluations', '—')} | {r.get('worst_quantity', '—')} | "
            f"{worst} | {'—' if m is None else f'{m["max_ratio"]:.3g} {m["max_row"]}'} |"
        )
    x = document["x31_three_tool"]
    lines += ["", f"Three-tool X31 clause: {x['clause']}; row 5 in {x['count_row_5']} of 4."]
    for c, v in x["cases"].items():
        lines.append(f"- {c}: row {v['row']}, {v['outcome']}")
    for k, v in x["inverse_kinds"].items():
        lines.append(f"- {k} ({v['case']}): row {v['row']}, {v['outcome']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--markdown", action="store_true")
    args = parser.parse_args()
    document = compute()
    if args.write:
        TABLE.write_text(dumps(document), encoding="utf-8")
        SUMS.write_text(sums_text(), encoding="utf-8")
        print(f"wrote {TABLE.relative_to(ROOT)} and {SUMS.relative_to(ROOT)}")
    elif args.check:
        same = TABLE.exists() and TABLE.read_text(encoding="utf-8") == dumps(document)
        same_sums = SUMS.exists() and SUMS.read_text(encoding="utf-8") == sums_text()
        print(
            f"comparison.json {'recomputes identically' if same else 'differs'}; "
            f"SHA256SUMS {'matches' if same_sums else 'differs'}"
        )
        return 0 if same and same_sums else 1
    else:
        print(markdown(document), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
