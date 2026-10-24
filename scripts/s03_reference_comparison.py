"""S03 WO-S03-4: the column reference comparison, recomputed from the committed JSON alone.

Authority: `docs/derivations/S03-spec.md` §6–§8, as amended by §17 and §18. Reads the tool records
`benchmarks/s03/references/results/<tool>-<case>.json`, our records `ours-<case>.json` (PC-L and
PC-LI are RC1's record, §3.3, §18.3), `docs/derivations/scripts/s03_cases.json` and the twin
`docs/derivations/scripts/s03_reference.json`, and classifies every registered (case, tool) pair by
§7.1's rules, in order:

0. the tool is not available for the case (§2.3 step 4) → `NOT_COMPARABLE(capability: <reason>)`;
1. the environment fingerprint differs from `docs/reference-environments.md` §3, or the tool did
   not run → `NOT_COMPARABLE(access: <what>)`;
2. not converged (IDAES: the final solve did not end "Optimal Solution Found"; DWSIM: an error, an
   object not calculated or an iteration limit), or the tool's own component balance misses by
   more than 3.1e-8 mol/s, or its own energy balance by more than 1e-3 W →
   `NOT_COMPARABLE(reference_accuracy: <value>)`;
2b. (IDAES) SmoothVLE shift > 1e-7 K, or a block without the registered ε →
   `NOT_COMPARABLE(semantics: smooth_vle_shift(<K>))`;
2c. stage count or map, an inlet's stage, a stage pressure (1e-3 Pa), an intermediate duty
   (1e-3 W), a fixed-zero liquid distillate (3.1e-8 mol/s), or a specification computed by §5.1
   row 9 / §17.4 from the tool's own record more than 1e-4 relative from the registered value →
   `NOT_COMPARABLE(semantics: <check>(<value>))`;
2d. a specification residual above its kind's threshold (§17.4), the accuracy rerun not converged
   or moving a registered quantity by more than 0.1 tolerance, or (IDAES, §18.4) two positions of
   the attempt's level whose final solves ended "Optimal Solution Found" differing by more than
   0.1 tolerance → `NOT_COMPARABLE(reference_accuracy: <check>(<value>))`;
3. ours is not `CONVERGED`, or a registered quantity is more than 0.1 tolerance from the twin →
   `NOT_COMPARABLE(ours_not_verified)`;
4. every registered quantity within `a_k + 1e-6 |v|` (§6, `v` the twin's 25-digit value,
   unrounded) → `AGREE`, otherwise `DISAGREE`, with the full table.

Rules 0–2d read only the tool's record, and the values they decide on are recomputed here from the
record's raw fields (§8): the script's own summaries are not read. A pair whose case registers the
tool as `not_applicable` is a registered absence (§3.3, §18.3). §17.3 (with §18.3) then applies the
control rule: a control classified `AGREE` stops the comparison; a tool none of whose controls
classifies `DISAGREE` has every pair that reached rule 2 made
`NOT_COMPARABLE(control_not_comparable: …)`. §17.5's per-case outcomes and X31's clause, §7.3's
reported values and §7.4's perturbation response table complete the document.

It is mechanical: no tolerance, setting, mapping or case is chosen here, and the verdict is the
`verdict` agent's (§7.5). The gate never runs a tool: `tests/test_s03_references.py` recomputes
the document with `compute()` from the committed records and a live solve of our side and requires
it to equal the committed `comparison.json` (A10).

Usage (repository root, project environment, `PYTHONPATH=src`):
    python scripts/s03_reference_comparison.py --write     # (re)write comparison.json, SHA256SUMS
    python scripts/s03_reference_comparison.py --check     # exit 1 unless both recompute
    python scripts/s03_reference_comparison.py --markdown  # the table, for the verdict
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "spikes" / "references"))

import t06_fixtures as fx  # noqa: E402  (the documented fingerprint and rule 2b's shift, T06's)

REFERENCES = ROOT / "benchmarks" / "s03" / "references"
RESULTS = REFERENCES / "results"
QUALIFICATION = REFERENCES / "qualification"
TABLE = REFERENCES / "comparison.json"
SUMS = REFERENCES / "SHA256SUMS"
CASES_PATH = ROOT / "docs" / "derivations" / "scripts" / "s03_cases.json"
TWIN_PATH = ROOT / "docs" / "derivations" / "scripts" / "s03_reference.json"

SCHEMA = "s03-reference-comparison-v1"
TOOLS = ("DWSIM", "IDAES")
#: Our record per case where the case has none of its own (§3.3 PC-L, §18.3 PC-LI; A02).
OURS_ALIASES = {"PC-L": "RC1", "PC-LI": "RC1"}
#: The qualification commits that hold the standing tool records (§2.3 step 3, §17.8, §18.5):
#: DWSIM's blind run (WO-S03-3) and its top-up (WO-S03-3b); IDAES's re-run (WO-S03-2b).
QUALIFICATION_COMMITS = {
    "DWSIM": (
        "958701409a162efe1c1be9dcad70b26a8cbbf546",
        "5474531f519ef2781fc9563cd3177f5f6684b590",
    ),
    "IDAES": ("2eb71ac05b8ad489ddab525755b0e45415a878fb",),
}
#: X31's count (§2.3 step 5) and the inverse kinds reported beside it (§17.5).
X31_CASES = ("RC1", "RC2", "RC3", "RC4")
INVERSE_KINDS = {"RC5": "purity", "RC6": "recovery", "RC7": "temperature"}

#: §6: T02 §6.4's allowances `a_k` by quantity kind, and the relative term.
ALLOWANCE = {"flow": Decimal("3.1e-7"), "T": Decimal("1e-5"), "duty": Decimal("1e-2")}
RELATIVE = Decimal("1e-6")
#: §6's rule 2 and 2c thresholds; rule 2b's bound (T06 rule 2b unchanged).
RULE2_COMPONENT_MOL_PER_S = Decimal("3.1e-8")
RULE2_ENERGY_W = Decimal("1e-3")
RULE2B_SHIFT_K = Decimal("1e-7")
RULE2C_PRESSURE_PA = Decimal("1e-3")
RULE2C_INTERMEDIATE_DUTY_W = Decimal("1e-3")
RULE2C_ZERO_DISTILLATE_MOL_PER_S = Decimal("3.1e-8")
RULE2C_SPEC_RELATIVE = Decimal("1e-4")  # every kind (§17.4)
#: §17.4's rule 2d thresholds per specification kind: (threshold, basis).
RULE2D_SPEC = {
    "reflux_ratio": (Decimal("1e-8"), "relative"),
    "boilup_ratio": (Decimal("1e-8"), "relative"),
    "distillate_rate": (Decimal("1e-8"), "relative"),
    "bottoms_rate": (Decimal("1e-8"), "relative"),
    "duty": (Decimal("1e-8"), "relative"),
    "purity": (Decimal("1e-8"), "absolute"),
    "recovery": (Decimal("1e-9"), "absolute"),
    "temperature": (Decimal("1e-9"), "relative"),
}
#: Rule 2d's rerun and path-dependence budget, and rule 3's (§7.1, §18.4).
TENTH = Decimal("0.1")
IPOPT_OPTIMAL = "Optimal Solution Found."
PRECISION = 50


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dec(x: Any) -> Decimal:
    """A recorded binary64 (or a registered decimal string) as an exact decimal."""
    if isinstance(x, str):
        return Decimal(x)
    return Decimal(repr(float(x)))


def tolerance(kind: str, value: Decimal) -> Decimal:
    """§6: `a_k + 1e-6 |v|`, exact in decimal (A14)."""
    return ALLOWANCE[kind] + RELATIVE * abs(value)


def ratio(numerator: Decimal, denominator: Decimal) -> float:
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return float(numerator / denominator)


# ---- the registered side ------------------------------------------------------------------------


def twin_quantities(ref: dict[str, Any], case_id: str) -> dict[str, dict[str, str]]:
    """The twin a case is judged against: `ref.twin` for RC and perturbed cases,
    `ref.controls.<PC>.ours` for the controls (§3.3, §18.3; PC-L's and PC-LI's are RC1's)."""
    if case_id in ref["twin"]:
        return ref["twin"][case_id]["quantities"]
    return ref["controls"][case_id]["ours"]


def control_cases(cases: dict[str, Any], tool: str) -> list[str]:
    """The tool's registered controls: role `positive_control`, not `not_applicable` for it."""
    return [
        cid
        for cid, case in cases["cases"].items()
        if case["role"] == "positive_control" and case["tool_variant"][tool] != "not_applicable"
    ]


def registered_absence(case: dict[str, Any], tool: str) -> bool:
    return bool(case["tool_variant"][tool] == "not_applicable")


# ---- a tool record's raw fields, in our stage numbering -----------------------------------------


def _products_and_inlets_dwsim(streams: dict[str, Any]) -> tuple[list[str], list[str]]:
    inlets = sorted(t for t in streams if t.startswith("IN"))
    products = sorted(t for t in streams if not t.startswith("IN"))
    return inlets, products


def view(record: dict[str, Any], case: dict[str, Any], raw: dict[str, Any] | None = None) -> dict:
    """The raw fields every rule and quantity is computed from, normalized across the tools.

    DWSIM: `raw_output.profile` (stage j is index j − 1), `.streams` (inlets `IN*`, products the
    rest), `.energy_streams_kW` with the record's sign conversion (Q > 0 into the stage). IDAES:
    `raw_output.stages` (keyed by our j), `.products`, `.inlets`, `.variables` (every state block's
    pressure). `raw` replaces the record's `raw_output` (another IDAES position's raw fields).
    """
    tool = record["tool"]
    raw = record["raw_output"] if raw is None else raw
    n = int(case["stage_count"])
    reg_p = [dec(p) for p in case["stage_pressures_Pa"]]
    v: dict[str, Any] = {"n": n}
    pressures: list[tuple[str, Decimal, Decimal]] = []
    if tool == "DWSIM":
        prof, streams = raw["profile"], raw["streams"]
        v["T"], v["L"], v["V"] = prof["T_K"], prof["L_mol_per_s"], prof["V_mol_per_s"]
        v["stage_count_raw"] = len(prof["T_K"])
        for j, p in enumerate(prof["P_Pa"], start=1):
            pressures.append((f"stage {j}", dec(p), reg_p[min(j, n) - 1]))
        inlets, products = _products_and_inlets_dwsim(streams)
        for t in products:
            at = n if t == "BOTTOM" else 1
            pressures.append((f"product {t}", dec(streams[t]["P_Pa"]), reg_p[at - 1]))
        energy = raw["energy_streams_kW"]
        duties: dict[str, Decimal] = {}
        if case["condenser"] != "none":
            duties["Q_condenser"] = -1000 * dec(energy["Q-COND"])
        if case["reboiler"] != "none":
            duties["Q_reboiler"] = 1000 * dec(energy["Q-REB"])
        ends = {1} if case["condenser"] != "none" else set()
        ends |= {n} if case["reboiler"] != "none" else set()
        v["intermediate_duties_W"] = [
            1000 * dec(q) for j, q in enumerate(prof["stage_duty_input_kW"], 1) if j not in ends
        ]
        if case["condenser"] == "partial":
            liquid = [abs(dec(prof["LSS_mol_per_s"][0]))]
            liquid += [
                abs(dec(streams[t]["molar_flow_mol_per_s"]))
                for t in products
                if t not in ("TOP", "BOTTOM")
            ]
            v["liquid_distillate"] = max(liquid)

        def comp(t: str) -> dict[str, Decimal]:
            return {c: dec(x) for c, x in streams[t]["overall_mol_per_s"].items()}

        def enthalpy_w(t: str) -> Decimal:
            s = streams[t]
            return dec(s["mass_flow_kg_per_s"]) * dec(s["mass_enthalpy_kJ_per_kg"]) * 1000

        v["top"] = {"flow": dec(streams["TOP"]["molar_flow_mol_per_s"]), "comp": comp("TOP")}
        v["bottom"] = {
            "flow": dec(streams["BOTTOM"]["molar_flow_mol_per_s"]),
            "comp": comp("BOTTOM"),
        }
        v["inlet_comps"] = [comp(t) for t in inlets]
        v["product_comps"] = [comp(t) for t in products]
        v["inlet_enthalpy_W"] = [enthalpy_w(t) for t in inlets]
        v["product_enthalpy_W"] = [enthalpy_w(t) for t in products]
        v["duties"] = duties
        v["duty_floats"] = {
            "Q_condenser": -1000.0 * float(energy["Q-COND"]) if "Q-COND" in energy else None,
            "Q_reboiler": 1000.0 * float(energy["Q-REB"]) if "Q-REB" in energy else None,
        }
    else:
        st = raw["stages"]
        v["stage_count_raw"] = len(st)
        v["T"] = [st[str(j)]["T_K"] for j in range(1, n + 1)]
        v["L"] = [st[str(j)]["L_mol_per_s"] for j in range(1, n + 1)]
        v["V"] = [st[str(j)]["V_mol_per_s"] for j in range(1, n + 1)]
        for j in range(1, n + 1):
            pressures.append((f"stage {j}", dec(st[str(j)]["P_Pa"]), reg_p[j - 1]))
        units = {e["unit"]: int(j) for j, e in record["stage_map"]["map"].items()}
        for name, value in sorted(raw["variables"].items()):
            if not name.endswith(".pressure"):
                continue
            owner = [j for u, j in units.items() if name.startswith(u + ".")]
            at = owner[0] if len(owner) == 1 else None
            registered = reg_p[at - 1] if at is not None else Decimal("NaN")
            pressures.append(
                (name, dec(value) if value is not None else Decimal("NaN"), registered)
            )
        for t, p in raw["products"].items():
            at = n if t == "BOTTOM" else 1
            pressures.append((f"product {t}", dec(p["P_Pa"]), reg_p[at - 1]))
        duties = {}
        if case["condenser"] != "none":
            duties["Q_condenser"] = dec(st["1"]["duty_W"])
        if case["reboiler"] != "none":
            duties["Q_reboiler"] = dec(st[str(n)]["duty_W"])
        kinds = {int(j): e["kind"] for j, e in record["stage_map"]["map"].items()}
        v["intermediate_duties_W"] = [
            dec(st[str(j)]["duty_W"] or 0.0) for j in range(1, n + 1) if kinds.get(j) == "tray"
        ]
        if case["condenser"] == "partial":
            # IDAES has no liquid-distillate stream at L3 (a Flash whose liquid outlet is joined to
            # stage 2 by an Arc, B2-3): any product other than TOP and BOTTOM would be one.
            extra = [
                abs(dec(p["flow_mol_per_s"]))
                for t, p in raw["products"].items()
                if t not in ("TOP", "BOTTOM")
            ]
            v["liquid_distillate"] = max(extra) if extra else Decimal(0)

        def comp_i(p: dict[str, Any]) -> dict[str, Decimal]:
            return {c: dec(x) for c, x in p["component_mol_per_s"].items()}

        products = raw["products"]
        v["top"] = {"flow": dec(products["TOP"]["flow_mol_per_s"]), "comp": comp_i(products["TOP"])}
        v["bottom"] = {
            "flow": dec(products["BOTTOM"]["flow_mol_per_s"]),
            "comp": comp_i(products["BOTTOM"]),
        }
        v["inlet_comps"] = [comp_i(i) for i in raw["inlets"].values()]
        v["product_comps"] = [comp_i(p) for p in products.values()]
        v["inlet_enthalpy_W"] = [
            dec(i["flow_mol_per_s"]) * dec(i["enth_mol_J_per_mol"]) for i in raw["inlets"].values()
        ]
        v["product_enthalpy_W"] = [
            dec(p["flow_mol_per_s"]) * dec(p["enth_mol_J_per_mol"]) for p in products.values()
        ]
        v["duties"] = duties
        v["duty_floats"] = {
            "Q_condenser": st["1"]["duty_W"] if case["condenser"] != "none" else None,
            "Q_reboiler": st[str(n)]["duty_W"] if case["reboiler"] != "none" else None,
        }
        v["variables"], v["smooth_vle_parameters"] = raw["variables"], raw["smooth_vle_parameters"]
    v["pressures"] = pressures
    return v


def tool_quantities(v: dict[str, Any], case: dict[str, Any]) -> dict[str, float]:
    """The case's registered quantities (§4), from the raw fields, as recorded doubles."""
    out: dict[str, float] = {}
    for name, _kind in case["quantities"]:
        if name[:2] in ("T[", "L[", "V["):
            value = v[name[0]][int(name[2:-1]) - 1]
        elif name == "reflux":
            value = v["L"][0]
        elif name.startswith("top["):
            value = float(v["top"]["comp"][name[4:-1]])
        elif name.startswith("bottom["):
            value = float(v["bottom"]["comp"][name[7:-1]])
        elif name in ("Q_condenser", "Q_reboiler"):
            value = v["duty_floats"][name]
        else:
            raise KeyError(f"no tool value for registered quantity {name}")
        if value is None or not math.isfinite(float(value)):
            raise ValueError(f"the record has no finite value for {name}")
        out[name] = float(value)
    return out


def specification_values(v: dict[str, Any], case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """§5.1 row 9 with §17.4, from the tool's own flows, duties and temperatures."""
    n, out = v["n"], {}
    with localcontext() as ctx:
        ctx.prec = PRECISION
        fed = {c: sum((i[c] for i in v["inlet_comps"]), Decimal(0)) for c in v["top"]["comp"]}
        for end, spec in case["specifications"].items():
            kind, registered = spec["kind"], Decimal(spec["value"])
            product = v["top"] if end == "condenser" else v["bottom"]
            if kind == "reflux_ratio":
                below = v["top"]["flow"] if case["condenser"] == "total" else dec(v["V"][0])
                got = dec(v["L"][0]) / below
            elif kind == "boilup_ratio":
                got = dec(v["V"][n - 1]) / dec(v["L"][n - 1])
            elif kind == "distillate_rate":
                got = v["top"]["flow"]
            elif kind == "bottoms_rate":
                got = v["bottom"]["flow"]
            elif kind == "duty":
                got = v["duties"]["Q_reboiler" if end == "reboiler" else "Q_condenser"]
            elif kind == "purity":
                got = product["comp"][spec["component"]] / product["flow"]
            elif kind == "recovery":
                c = spec["component"]
                got = product["comp"][c] / fed[c]
            elif kind == "temperature":
                got = dec(v["T"][int(spec["stage"]) - 1])
            else:
                raise ValueError(f"unregistered specification kind {kind}")
            absolute = got - registered
            relative = absolute / abs(registered)
            threshold, basis = RULE2D_SPEC[kind]
            accuracy = abs(absolute) if basis == "absolute" else abs(relative)
            out[end] = {
                "kind": kind,
                "registered": spec["value"],
                "tool": float(got),
                "relative_difference": float(relative),
                "rule2c_passes": abs(relative) <= RULE2C_SPEC_RELATIVE,
                "rule2d_basis": basis,
                "rule2d_threshold": str(threshold),
                "rule2d_measure": float(accuracy),
                "rule2d_passes": accuracy <= threshold,
                "_relative": relative,
                "_accuracy": accuracy,
            }
    return out


# ---- rules 0–2d on a tool record ----------------------------------------------------------------


def _final_termination(record: dict[str, Any]) -> list[str]:
    solve = record.get("solve", {})
    exits = [solve.get("ipopt", {}).get("exit"), solve.get("termination")]
    exits += [s.get("termination") for s in solve.get("solves", [])[-1:]]
    return [str(e) for e in exits]


def rule1(record: dict[str, Any], tool: str) -> str | None:
    measured = record.get("environment_fingerprint", {}).get("measured")
    expected = fx.EXPECTED_FINGERPRINT[tool.lower()]
    if measured != expected:
        differing = sorted(k for k in expected if (measured or {}).get(k) != expected[k])
        return (
            f"environment fingerprint differs from docs/reference-environments.md §3: {differing}"
        )
    if "raw_output" not in record:
        return "tool did not run: the record has no raw output"
    return None


def rule2(record: dict[str, Any], tool: str, v: dict[str, Any]) -> tuple[str | None, dict]:
    detail: dict[str, Any] = {}
    raw = record["raw_output"]
    if tool == "IDAES":
        exits = _final_termination(record)
        ok = all(e == IPOPT_OPTIMAL for e in exits)
        what = f"Ipopt final solve: {exits[0]}"
    else:
        prof = raw.get("profile", {})
        limit = int(record["settings_used"]["max_iterations"])
        uncalculated = sorted(t for t, done in raw.get("calculated", {}).items() if not done)
        iterations = (
            int(prof.get("internal_iterations", limit)),
            int(prof.get("external_iterations", limit)),
        )
        ok = (
            not raw.get("solver_errors")
            and not raw.get("column_error_message")
            and bool(raw.get("calculated"))
            and not uncalculated
            and max(iterations) < limit
        )
        what = (
            f"errors {raw.get('solver_errors')}, not calculated {uncalculated}, "
            f"iterations {iterations} of {limit}"
        )
    detail["converged"] = ok
    if not ok:
        return f"not_converged({what})", detail
    with localcontext() as ctx:
        ctx.prec = PRECISION
        residual = {
            c: sum((i[c] for i in v["inlet_comps"]), Decimal(0))
            - sum((p[c] for p in v["product_comps"]), Decimal(0))
            for c in v["top"]["comp"]
        }
        worst = max(abs(r) for r in residual.values())
        energy = (
            sum(v["inlet_enthalpy_W"], Decimal(0))
            + sum(v["duties"].values(), Decimal(0))
            - sum(v["product_enthalpy_W"], Decimal(0))
        )
    detail["component_balance_max_mol_per_s"] = float(worst)
    detail["energy_balance_W"] = float(energy)
    if not worst <= RULE2_COMPONENT_MOL_PER_S:
        return f"component_balance({float(worst):.4g} mol/s)", detail
    if not abs(energy) <= RULE2_ENERGY_W:
        return f"energy_balance({float(energy):.4g} W)", detail
    return None, detail


def rule2b(v: dict[str, Any], cases: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    """T06 rule 2b unchanged, recomputed from the record's variables and SmoothVLE parameters."""
    registered = cases["tool_settings"]["IDAES"]["smooth_vle"]
    eps = {which: Decimal(registered[f"{which}_K"]) for which in ("eps_1", "eps_2")}
    shift = fx.smooth_vle_shift(v["variables"], v["smooth_vle_parameters"])
    blocks = shift["blocks"]
    off = sorted(
        b
        for b, e in blocks.items()
        if any(e[f"{w}_K"] is None or dec(e[f"{w}_K"]) != value for w, value in eps.items())
    )
    worst = shift["max_shift_K"]
    detail = {
        "max_shift_K": None if worst is None else float(worst),
        "argmax": shift["argmax"],
        "smooth_vle_blocks": len(blocks),
        "blocks_without_the_registered_eps": off,
    }
    if not blocks:
        return "smooth_vle_shift(no SmoothVLE state block recorded)", detail
    if worst is None:
        return "smooth_vle_shift(not computable)", detail
    if worst > RULE2B_SHIFT_K or off:
        return f"smooth_vle_shift({float(worst):.4g})", detail
    return None, detail


def rule2c(
    record: dict[str, Any],
    case: dict[str, Any],
    v: dict[str, Any],
    specs: dict[str, dict[str, Any]],
) -> tuple[str | None, dict[str, Any]]:
    tool, n = record["tool"], v["n"]
    smap = record["stage_map"]
    count_key = "stage_count_dwsim" if tool == "DWSIM" else "stage_count_idaes"
    counts = (int(smap[count_key]), int(v["stage_count_raw"]), len(smap["map"]))
    detail: dict[str, Any] = {"stage_counts": list(counts)}
    if any(c != n for c in counts):
        return f"stage_count({list(counts)} against {n})", detail
    keys = sorted(int(j) for j in smap["map"])
    if tool == "DWSIM":
        bad = [j for j, e in smap["map"].items() if int(e["dwsim_index"]) != int(j) - 1]
    else:
        units = [e["unit"] for e in smap["map"].values()]
        bad = [] if len(set(units)) == n else ["units not distinct"]
    if keys != list(range(1, n + 1)) or bad:
        return f"stage_map({bad or keys})", detail
    feeds = record["feed_stages"]
    registered = [int(i["stage"]) for i in case["inlets"]]
    entered = []
    for inlet, f in zip(case["inlets"], feeds, strict=False):
        if tool == "DWSIM":
            at = int(f["dwsim_stage_index_0_based"]) + 1
            ok = smap["map"][str(at)]["dwsim_name"] == f["dwsim_associated_stage"]
        else:
            owners = [int(j) for j, e in smap["map"].items() if e["unit"] == f["idaes_unit"]]
            at = owners[0] if len(owners) == 1 else -1
            ok = f["idaes_port"].startswith(f["idaes_unit"] + ".")
        entered.append(at if ok and int(f["registered_stage"]) == int(inlet["stage"]) else -1)
    detail["feed_stages"] = entered
    if len(feeds) != len(case["inlets"]) or entered != registered:
        return f"feed_stage({entered} against {registered})", detail
    worst_p, where_p = Decimal(0), None
    for where, value, reg in v["pressures"]:
        dev = abs(value - reg)
        if dev.is_nan() or dev > worst_p:
            worst_p, where_p = dev, where
        if dev.is_nan():
            break
    detail["pressure_max_abs_dev_Pa"] = float(worst_p)
    if worst_p.is_nan() or worst_p > RULE2C_PRESSURE_PA:
        return f"pressure({float(worst_p):.4g} Pa at {where_p})", detail
    inter = max((abs(q) for q in v["intermediate_duties_W"]), default=Decimal(0))
    detail["intermediate_duty_max_abs_W"] = float(inter)
    if inter > RULE2C_INTERMEDIATE_DUTY_W:
        return f"intermediate_duty({float(inter):.4g} W)", detail
    if "liquid_distillate" in v:
        detail["zero_liquid_distillate_mol_per_s"] = float(v["liquid_distillate"])
        if v["liquid_distillate"] > RULE2C_ZERO_DISTILLATE_MOL_PER_S:
            return f"zero_liquid_distillate({float(v['liquid_distillate']):.4g} mol/s)", detail
    for end, s in specs.items():
        if not s["rule2c_passes"]:
            return f"specification_{end}_{s['kind']}({s['relative_difference']:.4g})", detail
    return None, detail


def movement(
    case: dict[str, Any],
    twin: dict[str, dict[str, str]],
    base: dict[str, float],
    other: dict[str, float],
) -> dict[str, Any]:
    """`|other − base| / tol(twin)` per registered quantity (rule 2d, §18.4)."""
    kinds = dict(case["quantities"])
    ratios = {}
    for q in base:
        tol = tolerance(kinds[q], Decimal(twin[q]["value"]))
        ratios[q] = (abs(dec(other[q]) - dec(base[q])), tol)
    worst = max(ratios, key=lambda q: (ratios[q][0] / ratios[q][1], q))
    num, tol = ratios[worst]
    return {"max_ratio": ratio(num, tol), "max_quantity": worst, "_exceeds": num > TENTH * tol}


def path_positions(record: dict[str, Any], case: dict[str, Any]) -> dict[str, dict[str, float]]:
    """IDAES: the registered quantities of every position at the selected level whose final solve
    ended "Optimal Solution Found", each from its own raw fields (§18.4)."""
    level = record["levels"][record["level"]]
    out = {}
    for name, entry in level.get("positions", {}).items():
        if name == record["position"]:
            if all(e == IPOPT_OPTIMAL for e in _final_termination(record)):
                out[name] = tool_quantities(view(record, case), case)
            continue
        full = entry.get("full")
        if not isinstance(full, dict) or "raw" not in full:
            continue
        rec = full["record"]
        exits = [rec.get("ipopt", {}).get("exit"), rec.get("termination")]
        exits += [s.get("termination") for s in rec.get("solves", [])[-1:]]
        if all(e == IPOPT_OPTIMAL for e in exits):
            out[name] = tool_quantities(view(record, case, raw=full["raw"]), case)
    return dict(sorted(out.items()))


def rule2d(
    record: dict[str, Any],
    case: dict[str, Any],
    twin: dict[str, dict[str, str]],
    specs: dict[str, dict[str, Any]],
    quantities: dict[str, float],
) -> tuple[str | None, dict[str, Any]]:
    detail: dict[str, Any] = {
        "specification": {
            e: {k: s[k] for k in s if not k.startswith("_")} for e, s in specs.items()
        }
    }
    for end, s in specs.items():
        if not s["rule2d_passes"]:
            return f"specification_residual_{end}_{s['kind']}({s['rule2d_measure']:.4g})", detail
    rerun = record.get("accuracy_rerun") or {}
    if record["tool"] == "IDAES":
        exits = [rerun.get("ipopt", {}).get("exit"), rerun.get("termination")]
        exits += [s.get("termination") for s in rerun.get("solves", [])[-1:]]
        rerun_ok = bool(rerun) and all(e == IPOPT_OPTIMAL for e in exits)
    else:
        rerun_ok = bool(rerun.get("converged")) and rerun.get("termination") == (
            "calculated, no error reported"
        )
    if not rerun_ok or "quantities" not in rerun:
        return f"rerun_not_converged({rerun.get('termination')})", detail
    moved = movement(case, twin, quantities, {q: rerun["quantities"][q] for q in quantities})
    detail["rerun_max_ratio"], detail["rerun_max_quantity"] = (
        moved["max_ratio"],
        moved["max_quantity"],
    )
    if moved["_exceeds"]:
        return f"rerun_movement({moved['max_ratio']:.4g} at {moved['max_quantity']})", detail
    if record["tool"] == "IDAES":
        positions = path_positions(record, case)
        worst: dict[str, Any] = {"max_ratio": 0.0, "max_quantity": None, "pair": None}
        exceeds = False
        names = list(positions)
        for i, a in enumerate(names):
            for b in names[i + 1 :]:
                m = movement(case, twin, positions[a], positions[b])
                exceeds = exceeds or m["_exceeds"]
                if m["max_ratio"] > worst["max_ratio"]:
                    worst = {**m, "pair": f"{a}-{b}"}
        detail["path_dependence"] = {
            "converged_positions": names,
            "max_ratio": worst["max_ratio"],
            "max_quantity": worst["max_quantity"],
            "pair": worst["pair"],
        }
        if exceeds:
            return f"path_dependence({worst['max_ratio']:.4g} {worst['pair']})", detail
    return None, detail


# ---- one pair -----------------------------------------------------------------------------------


def _label(classification: str, category: str | None, reason: str) -> str:
    if category is None:
        return classification
    if category == "ours_not_verified":
        return f"{classification}(ours_not_verified)"
    return f"{classification}({category}: {reason})"


def classify(
    case_id: str,
    tool: str,
    record: dict[str, Any] | None,
    ours: dict[str, Any] | None,
    cases: dict[str, Any],
    ref: dict[str, Any],
) -> dict[str, Any]:
    """§7.1's rules 0–4 in order, on one (case, tool) pair (no control rule)."""
    case = cases["cases"][case_id]
    row: dict[str, Any] = {"case": case_id, "tool": tool}

    def result(classification: str, category: str | None, reason: str, rule: Any) -> dict:
        return {
            **row,
            "classification": classification,
            "category": category,
            "reason": reason,
            "label": _label(classification, category, reason),
            "rule": rule,
        }

    if registered_absence(case, tool):
        if record is not None and "not_applicable" not in record:
            raise ValueError(f"({case_id}, {tool}) is registered not_applicable but has a record")
        reason = (record or {}).get(
            "not_applicable", "a registered absence with no record (spec §18.3, A08 (ii))"
        )
        return {
            **result("not_applicable", None, reason, "registered_absence"),
            "label": "not_applicable",
        }
    if record is None:
        return result("NOT_COMPARABLE", "access", "no record", 1)
    if "not_applicable" in record:
        raise ValueError(f"({case_id}, {tool}) says not_applicable but the case registers it")
    if not record.get("available"):
        return result(
            "NOT_COMPARABLE",
            "capability",
            str(record.get("not_available_reason", "not available")),
            0,
        )
    row["level"] = record["level"]
    if tool == "DWSIM":
        used = record["settings_used"]
        row["rung"] = {"tolerance": used["column_tolerance"], "method": used["method"]}
    else:
        row["position"] = record["position"]
    access = rule1(record, tool)
    if access is not None:
        return result("NOT_COMPARABLE", "access", access, 1)
    twin = twin_quantities(ref, case_id)
    v = view(record, case)
    problem, row["rule2"] = rule2(record, tool, v)
    if problem is not None:
        return result("NOT_COMPARABLE", "reference_accuracy", problem, 2)
    if tool == "IDAES":
        problem, row["rule2b"] = rule2b(v, cases)
        if problem is not None:
            return result("NOT_COMPARABLE", "semantics", problem, "2b")
    specs = specification_values(v, case)
    problem, row["rule2c"] = rule2c(record, case, v, specs)
    if problem is not None:
        return result("NOT_COMPARABLE", "semantics", problem, "2c")
    values = tool_quantities(v, case)
    problem, row["rule2d"] = rule2d(record, case, twin, specs, values)
    if problem is not None:
        return result("NOT_COMPARABLE", "reference_accuracy", problem, "2d")

    kinds = dict(case["quantities"])
    if ours is None or ours.get("outcome") != "CONVERGED":
        status = None if ours is None else ours.get("outcome")
        return result("NOT_COMPARABLE", "ours_not_verified", f"ours: {status}", 3)
    ours_far = []
    for q in values:
        tol = tolerance(kinds[q], Decimal(twin[q]["value"]))
        if abs(dec(ours["quantities"][q]) - Decimal(twin[q]["value"])) > TENTH * tol:
            ours_far.append(q)
    if ours_far:
        return result(
            "NOT_COMPARABLE",
            "ours_not_verified",
            f"ours more than 0.1 tolerance from the twin on {ours_far}",
            3,
        )

    word, extra = rule4(values, ours["quantities"], twin, kinds)
    return {**result(word, None, extra.pop("reason"), 4), **extra}


def rule4(
    values: dict[str, float],
    ours_quantities: dict[str, float],
    twin: dict[str, dict[str, str]],
    kinds: dict[str, str],
) -> tuple[str, dict[str, Any]]:
    """Rule 4: every registered quantity within §6's tolerance on the twin's value (A14)."""
    table = []
    for q, tool_value in values.items():
        twin_value = Decimal(twin[q]["value"])
        tol = tolerance(kinds[q], twin_value)
        ours_value = float(ours_quantities[q])
        o, t = dec(ours_value), dec(tool_value)
        table.append(
            {
                "quantity": q,
                "kind": kinds[q],
                "ours": ours_value,
                "tool": tool_value,
                "twin": twin[q]["value"],
                "tolerance": float(tol),
                "within_tolerance": abs(o - t) <= tol,
                "ratio": ratio(abs(o - t), tol),
                "ours_vs_twin_ratio": ratio(abs(o - twin_value), tol),
                "tool_vs_twin_ratio": ratio(abs(t - twin_value), tol),
            }
        )
    worst = max(table, key=lambda r: (r["ratio"], r["quantity"]))
    outside = sum(not r["within_tolerance"] for r in table)
    word = "AGREE" if outside == 0 else "DISAGREE"
    reason = (
        f"every registered quantity within tolerance; worst {worst['quantity']} at "
        f"{worst['ratio']:.4g} of its tolerance"
        if outside == 0
        else f"{outside} of {len(table)} quantities outside tolerance; worst "
        f"{worst['quantity']} at {worst['ratio']:.4g} of its tolerance"
    )
    return word, {
        "reason": reason,
        "worst_quantity": worst["quantity"],
        "worst_ratio": worst["ratio"],
        "quantities_outside": outside,
        "quantities": table,
    }


# ---- §17.3, §17.5, §7.3, §7.4 -------------------------------------------------------------------


def apply_controls(rows: list[dict[str, Any]], cases: dict[str, Any]) -> dict[str, Any]:
    """§17.3 with §18.3. Returns the control summary; rewrites the rows of a tool without a
    `DISAGREE` control (each pair that reached rule 2, other than its controls and rule 3's)."""
    by = {(r["case"], r["tool"]): r for r in rows}
    summary: dict[str, Any] = {"stopped": False, "per_tool": {}}
    for tool in TOOLS:
        controls = control_cases(cases, tool)
        labels = {c: by[c, tool]["label"] for c in controls}
        working = [c for c in controls if by[c, tool]["classification"] == "DISAGREE"]
        agree = [c for c in controls if by[c, tool]["classification"] == "AGREE"]
        summary["per_tool"][tool] = {
            "controls": labels,
            "disagree": working,
            "agree": agree,
            "pairs_count": bool(working) and not agree,
        }
        if agree:
            summary["stopped"] = True
        if working:
            continue
        reason = "; ".join(f"{c} {labels[c]}" for c in controls)
        for r in rows:
            if r["tool"] != tool or r["case"] in controls:
                continue
            if r["rule"] in (0, 1, 3, "registered_absence"):
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


def pair_class(row: dict[str, Any]) -> str:
    """§17.5's class of a pair."""
    if row["classification"] in ("AGREE", "DISAGREE"):
        return "comparable"
    rule = row["rule"]
    if rule == 0:
        return "absent"
    if rule == "17.3(b)":
        return "unusable"
    if rule == 1:
        return "access"
    if rule == 3:
        return "ours"
    if rule == "registered_absence":
        return "not_applicable"
    return f"unclassified(rule {rule})"


def case_outcome(pairs: dict[str, dict[str, Any]]) -> tuple[int, str]:
    """§17.5's table: the first matching row decides."""
    classes = {t: pair_class(r) for t, r in pairs.items()}
    words = {t: r["classification"] for t, r in pairs.items()}
    if any(c == "ours" for c in classes.values()):
        return 1, "not met: a column finding (S02 or S06)"
    if any(w == "DISAGREE" for w in words.values()):
        return 2, "not met: a disagreement finding, until the design lane resolves it"
    if any(c == "access" for c in classes.values()):
        return 3, "blocked"
    if any(c == "unusable" for c in classes.values()):
        return 4, "not met: an available reference could not be shown to see a known difference"
    if all(w == "AGREE" for w in words.values()):
        return 5, "two references"
    agree = [t for t, w in words.items() if w == "AGREE"]
    absent = [t for t, c in classes.items() if c == "absent"]
    if len(agree) == 1 and len(absent) == len(pairs) - 1:
        quoted = "; ".join(f"{t}: {pairs[t]['reason']}" for t in absent)
        return 6, f"one reference ({agree[0]}), absent: {quoted}"
    if len(absent) == len(pairs):
        return 7, "no reference: not met"
    return 0, f"no row of §17.5 matches: {classes}"


def x31(rows: list[dict[str, Any]], stopped: bool) -> dict[str, Any]:
    by = {(r["case"], r["tool"]): r for r in rows}

    def table(case_ids: tuple[str, ...]) -> dict[str, Any]:
        out = {}
        for c in case_ids:
            pairs = {t: by[c, t] for t in TOOLS}
            number, outcome = case_outcome(pairs)
            out[c] = {
                "pairs": {
                    t: {"class": pair_class(r), "label": r["label"]} for t, r in pairs.items()
                },
                "row": number,
                "outcome": outcome,
            }
        return out

    cases = table(X31_CASES)
    rows_hit = [cases[c]["row"] for c in X31_CASES]
    if stopped:
        clause = "stopped: a control classified AGREE (§17.3(a)); no clause outcome is recorded"
    elif any(r == 0 for r in rows_hit):
        clause = "undetermined: a pair outside §17.5's classes (a design-lane question)"
    elif any(r in (1, 2, 4, 7) for r in rows_hit):
        clause = "not met"
    elif any(r == 3 for r in rows_hit):
        clause = "blocked"
    elif all(r == 5 for r in rows_hit):
        clause = "met with two references"
    else:
        clause = "met where available"
    two = [c for c in X31_CASES if cases[c]["row"] == 5]
    comparable_one = [
        c for c in X31_CASES if any(cases[c]["pairs"][t]["class"] == "comparable" for t in TOOLS)
    ]
    return {
        "counted_cases": list(X31_CASES),
        "cases": cases,
        "clause": clause,
        "cases_with_two_references": len(two),
        "cases_with_two_references_list": two,
        "cases_with_a_comparable_pair": comparable_one,
        "target": 4,
        "inverse_kinds": {
            INVERSE_KINDS[c]: {"case": c, **v} for c, v in table(tuple(INVERSE_KINDS)).items()
        },
    }


def control_distances(
    rows: list[dict[str, Any]], records: dict, ref: dict[str, Any], cases: dict[str, Any]
) -> dict[str, Any]:
    """§7.3: each control's tool distance to the tool-model twin, over the tool-model value's own
    §6 tolerance (expected ≤ 1 if the tool computed its own model correctly)."""
    out = {}
    by = {(r["case"], r["tool"]): r for r in rows}
    for cid, control in ref["controls"].items():
        for tool in TOOLS:
            case = cases["cases"][cid]
            if registered_absence(case, tool):
                continue
            record = records.get((tool, cid))
            key = f"{cid}/{tool}"
            if record is None or not record.get("available") or "raw_output" not in record:
                out[key] = {
                    "classification": by[cid, tool]["label"],
                    "max_ratio": None,
                    "reason": "no tool values (not available)",
                }
                continue
            values = tool_quantities(view(record, case), case)
            ratios = {}
            for q, value in values.items():
                entry = control["tool_model"][q]
                tm = Decimal(entry["value"])
                ratios[q] = ratio(abs(dec(value) - tm), tolerance(entry["kind"], tm))
            worst = max(ratios, key=lambda q: (ratios[q], q))
            out[key] = {
                "classification": by[cid, tool]["label"],
                "max_ratio": ratios[worst],
                "argmax": worst,
                "registered_discrimination": control["max_ratio"],
            }
    return out


def response_table(
    rows: list[dict[str, Any]],
    records: dict,
    ours: dict,
    ref: dict[str, Any],
    cases: dict[str, Any],
) -> dict[str, Any]:
    """§7.4: Δy = y_pert − y_base per quantity for ours, each tool and the twin, with the bound
    tol(y_pert) + tol(y_base). A tool's Δy is given where both records carry values."""
    by = {(r["case"], r["tool"]): r for r in rows}
    out = {}
    for pert, entry in ref["perturbations"].items():
        base = entry["base"]
        case_p, case_b = cases["cases"][pert], cases["cases"][base]
        values: dict[str, dict[str, float] | None] = {}
        for tool in TOOLS:
            rp, rb = records.get((tool, pert)), records.get((tool, base))
            ok = all(r is not None and r.get("available") and "raw_output" in r for r in (rp, rb))
            values[tool] = None
            if ok:
                vp = tool_quantities(view(rp, case_p), case_p)
                vb = tool_quantities(view(rb, case_b), case_b)
                values[tool] = {q: vp[q] - vb[q] for q in vp}
        op, ob = ours.get(pert), ours.get(base)
        ours_ok = all(o is not None and o.get("outcome") == "CONVERGED" for o in (op, ob))
        kinds = dict(case_p["quantities"])
        lines = []
        for q, kind in case_p["quantities"]:
            tp, tb = (
                Decimal(ref["twin"][pert]["quantities"][q]["value"]),
                Decimal(ref["twin"][base]["quantities"][q]["value"]),
            )
            line = {
                "quantity": q,
                "twin": float(tp - tb),
                "ours": op["quantities"][q] - ob["quantities"][q] if ours_ok else None,
                "bound": float(tolerance(kinds[q], tp) + tolerance(kind, tb)),
            }
            for tool in TOOLS:
                line[tool] = None if values[tool] is None else values[tool][q]
            lines.append(line)
        out[pert] = {
            "base": base,
            "both_agree": {
                t: by[pert, t]["classification"] == "AGREE"
                and by[base, t]["classification"] == "AGREE"
                for t in TOOLS
            },
            "quantities": lines,
        }
    return out


# ---- the document -------------------------------------------------------------------------------


def load_records(results: Path = RESULTS, cases: dict[str, Any] | None = None) -> dict:
    cases = cases or load_json(CASES_PATH)
    records: dict[tuple[str, str], dict[str, Any] | None] = {}
    for tool in TOOLS:
        for cid in cases["cases"]:
            path = results / f"{tool.lower()}-{cid}.json"
            records[tool, cid] = load_json(path) if path.exists() else None
    return records


def load_ours(results: Path = RESULTS, cases: dict[str, Any] | None = None) -> dict:
    cases = cases or load_json(CASES_PATH)
    ours: dict[str, dict[str, Any] | None] = {}
    for cid in cases["cases"]:
        path = results / f"ours-{OURS_ALIASES.get(cid, cid)}.json"
        ours[cid] = load_json(path) if path.exists() else None
    return ours


def compute(
    records: dict | None = None,
    ours: dict | None = None,
    cases: dict[str, Any] | None = None,
    ref: dict[str, Any] | None = None,
) -> dict:
    """The whole comparison document. `records` and `ours` default to the committed files; the
    gate passes a live solve of our side (A10)."""
    cases = cases or load_json(CASES_PATH)
    ref = ref or load_json(TWIN_PATH)
    records = load_records(cases=cases) if records is None else records
    ours = load_ours(cases=cases) if ours is None else ours
    rows = [
        classify(cid, tool, records[tool, cid], ours[cid], cases, ref)
        for cid in cases["cases"]
        for tool in TOOLS
    ]
    controls = apply_controls(rows, cases)
    idaes_paths = {
        r["case"]: r["rule2d"]["path_dependence"]
        for r in rows
        if r["tool"] == "IDAES" and "path_dependence" in r.get("rule2d", {})
    }
    inputs = {
        f"benchmarks/s03/references/results/{p.name}": sha256(p)
        for p in sorted(RESULTS.glob("*.json"))
    }
    for path in (CASES_PATH, TWIN_PATH):
        inputs[str(path.relative_to(ROOT))] = sha256(path)
    return {
        "schema": SCHEMA,
        "authority": "docs/derivations/S03-spec.md §6-§8, §17, §18; A08-A14",
        "classification_is_mechanical": "the recorded verdict is the verdict agent's, on this "
        "document (§7.5)",
        "tolerance_rule": "|ours - tool| <= a_k + 1e-6 |v_twin|, v the twin's 25-digit value "
        "evaluated unrounded (§6)",
        "allowances": {k: str(a) for k, a in ALLOWANCE.items()},
        "thresholds": {
            "rule2_component_mol_per_s": str(RULE2_COMPONENT_MOL_PER_S),
            "rule2_energy_W": str(RULE2_ENERGY_W),
            "rule2b_shift_K": str(RULE2B_SHIFT_K),
            "rule2c_pressure_Pa": str(RULE2C_PRESSURE_PA),
            "rule2c_intermediate_duty_W": str(RULE2C_INTERMEDIATE_DUTY_W),
            "rule2c_zero_liquid_distillate_mol_per_s": str(RULE2C_ZERO_DISTILLATE_MOL_PER_S),
            "rule2c_specification_relative": str(RULE2C_SPEC_RELATIVE),
            "rule2d_specification": {k: [str(t), b] for k, (t, b) in RULE2D_SPEC.items()},
            "rule2d_rerun_and_path_fraction_of_tolerance": str(TENTH),
            "rule3_fraction_of_tolerance": str(TENTH),
        },
        "inputs_sha256": inputs,
        "rows": rows,
        "controls": controls,
        "comparison_stopped": controls["stopped"],
        "control_tool_model_distance": control_distances(rows, records, ref, cases),
        "idaes_path_dependence": idaes_paths,
        "x31": x31(rows, controls["stopped"]),
        "perturbation_response": response_table(rows, records, ours, ref, cases),
    }


def dumps(document: dict[str, Any]) -> str:
    return json.dumps(document, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def sums_text() -> str:
    """SHA256SUMS over every committed record and comparison.json (paths relative to
    `benchmarks/s03/references/`)."""
    paths = sorted(QUALIFICATION.glob("*.json")) + sorted(RESULTS.glob("*.json")) + [TABLE]
    return "".join(f"{sha256(p)}  {p.relative_to(REFERENCES)}\n" for p in paths)


def markdown(document: dict[str, Any]) -> str:
    lines = [
        "| Case | Tool | Classification | Level | Worst | Ratio |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in document["rows"]:
        level = r.get("level", "—")
        if "rung" in r:
            level += f" ({r['rung']['tolerance']:g}, {r['rung']['method']})"
        if "position" in r:
            level += f" {r['position']}"
        worst = f"{r['worst_ratio']:.4g}" if "worst_ratio" in r else "—"
        lines.append(
            f"| {r['case']} | {r['tool']} | {r['label'][:160]} | {level} | "
            f"{r.get('worst_quantity', '—')} | {worst} |"
        )
    x = document["x31"]
    lines += [
        "",
        f"X31 clause: {x['clause']}; {x['cases_with_two_references']} of 4 cases "
        "with two references.",
    ]
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
