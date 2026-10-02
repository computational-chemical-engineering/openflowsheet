"""T06 W8: the reference comparison table, recomputed from the committed JSON alone (spec §9.5).

Reads `benchmarks/t06/references/results/` (the tool records `<tool>-<fixture>.json` and our records
`ours-<fixture>.json`) and the twin `benchmarks/t06/reference_values.yaml`, and classifies every
(fixture, tool) pair by spec §9.5's rules, in order:

1. the tool's environment fingerprint differs from `docs/reference-environments.md` §3, or the
   tool did not run → `NOT_COMPARABLE(access: <what>)` (a registered absence — (PC-1, IDAES),
   §9.4 as amended — is `not_applicable` instead, outside V16's counts);
2. the tool reports non-convergence (IDAES: Ipopt's final solve did not end "Optimal Solution
   Found"; DWSIM: an object not calculated, a solver error, or REF-08's `Recycle` not converged
   within its limit), or its own overall component balance misses by more than 3.1e-8 mol/s on
   any component → `NOT_COMPARABLE(reference_accuracy: <value>)`; if this fires on PC-1 (DWSIM),
   DWSIM's REF-04 is not comparable either (§9.5);
2b. (A2) IDAES only: the SmoothVLE shift recomputed from the record's own variables,
   `max |T_eq − min(max(T, T_bub), T_dew)|` over every SmoothVLE state block, exceeds 1e-7 K, or
   the record does not carry the registered `eps_1 = eps_2 = 1e-8 K` on every such block →
   `NOT_COMPARABLE(semantics: smooth_vle_shift(<shift> K))`;
3. our solve is not `CONVERGED` and `VERIFIED` → `NOT_COMPARABLE(ours_not_verified)`;
4. every registered quantity within §9.4's tolerance `a_k + 1e-6 |v|` (the twin's registered
   tolerance; for PC-2, which registers none, the same formula on the twin's value) → `AGREE`,
   otherwise `DISAGREE` — with the full table (ours, tool, twin, tolerance, `|ours − tool|` and
   its ratio to the tolerance).

W8's IDAES records, run at IDAES's default smoothing, are retained as
`results/idaes-default-eps-<fixture>.json` and classified in the document's `superseded_default_eps`
section by the same rules — rule 2b fires on each — beside the table rules 3 and 4 produced from
them without rule 2b (W8's `DISAGREE`s; spec §9.5 rule 2b, A83). They count nowhere.

It is mechanical: no tolerance, setting or mapping is chosen here, and the verdict is the
`verdict` agent's, on this table. The gate never runs a tool: `tests/test_t06_w8_references.py`
recomputes the table with `compute()` and requires it to equal the committed
`benchmarks/t06/references/comparison.json` (A50).

Usage (from the repository root, project environment):
    python scripts/t06_reference_comparison.py --write     # (re)write comparison.json
    python scripts/t06_reference_comparison.py --check     # exit 1 unless it recomputes identically
    python scripts/t06_reference_comparison.py --markdown  # the table, for the dossier
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "spikes" / "references"))

import t06_fixtures as fx  # noqa: E402

REFERENCES = ROOT / "benchmarks" / "t06" / "references"
RESULTS = REFERENCES / "results"
TABLE = REFERENCES / "comparison.json"
TWIN = ROOT / "benchmarks" / "t06" / "reference_values.yaml"

SCHEMA = "t06-reference-comparison-v2"
TOOLS = ("DWSIM", "IDAES")
REF_FIXTURES = tuple(f"REF-0{k}" for k in range(1, 9))
FIXTURES = (*REF_FIXTURES, "PC-1", "PC-2")
POSITIVE_CONTROLS = ("PC-1", "PC-2")
#: Our record per fixture: PC-1 is REF-04 with DWSIM's unmapped latent heat (spec §9.4).
OURS_OF = {**{f: f for f in FIXTURES}, "PC-1": "REF-04"}
#: Where rule 2 firing on a positive control makes the same tool's fixture not comparable (§9.5).
CONTROL_FIXTURE = {"PC-1": "REF-04"}
#: W8's IDAES records at IDAES's default SmoothVLE smoothing, retained (spec §9.5 rule 2b, A83).
DEFAULT_EPS_PREFIX = "idaes-default-eps-"

#: T02 §6.4's allowances `a_k` by quantity kind (spec §9.4); work is a `heat_rate`.
ALLOWANCE = {
    "molar_flow": Decimal("3.1e-7"),
    "temperature": Decimal("1e-5"),
    "heat_rate": Decimal("1e-2"),
}
RELATIVE = Decimal("1e-6")
#: §9.5 rule 2.
RULE2_TOLERANCE = Decimal("3.1e-8")
IPOPT_OPTIMAL = "Optimal Solution Found."


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tolerance(kind: str, value: Decimal) -> Decimal:
    """Spec §9.4: `a_k + 1e-6 |v|`, exact in decimal."""
    return ALLOWANCE[kind] + RELATIVE * abs(value)


def registered(twin: dict[str, Any], fixture: str) -> dict[str, dict[str, str]]:
    """The registered quantities of a fixture: quantity -> {kind, value, tolerance} (strings)."""
    closed = twin["closed_form"]
    if fixture in REF_FIXTURES:
        return {
            q: {"kind": e["kind"], "value": e["value"], "tolerance": e["tolerance"]}
            for q, e in closed["reference_fixtures"][fixture]["quantities"].items()
        }
    if fixture == "PC-1":
        control = closed["positive_controls"]["PC-1"]
        entry = closed["reference_fixtures"]["REF-04"]["quantities"][control["quantity"]]
        if Decimal(entry["tolerance"]) != Decimal(control["tolerance_W"]):
            raise ValueError("PC-1's registered tolerance is not REF-04's duty tolerance")
        return {
            control["quantity"]: {
                "kind": entry["kind"],
                "value": entry["value"],
                "tolerance": entry["tolerance"],
            }
        }
    control = closed["positive_controls"]["PC-2"]
    out: dict[str, dict[str, str]] = {}
    for c, value in zip(fx.COMPONENTS, control["ours_vapor_mol_per_s"], strict=True):
        out[f"S2.n.{c}"] = {
            "kind": "molar_flow",
            "value": value,
            "tolerance": str(tolerance("molar_flow", Decimal(value))),
        }
    return out


def registered_absence(twin: dict[str, Any], fixture: str, tool: str) -> bool:
    settings = twin["closed_form"]["reference_tool_settings"]
    return bool(settings.get(fixture, {}).get(tool) == "not_applicable")


# ---- rules 1 and 2 on a tool record -------------------------------------------------------------


def rule1(record: dict[str, Any] | None, tool: str) -> str | None:
    """The access problem, if any (spec §9.5 rule 1)."""
    if record is None:
        return "no record"
    if "not_applicable" in record:
        return f"not run: {record['not_applicable']}"
    measured = record.get("environment_fingerprint", {}).get("measured")
    expected = fx.EXPECTED_FINGERPRINT[tool.lower()]
    if measured != expected:
        differing = sorted(k for k in expected if (measured or {}).get(k) != expected[k])
        return (
            f"environment fingerprint differs from docs/reference-environments.md §3: {differing}"
        )
    if "error" in record:
        return f"tool did not run: {record['error']}"
    if not record.get("accepted"):
        return "tool did not accept the model"
    return None


def converged(record: dict[str, Any], tool: str) -> tuple[bool, str]:
    """Convergence as spec §9.5 rule 2 defines it (A1), recomputed from the record."""
    if tool == "IDAES":
        exit_line = record.get("ipopt", {}).get("exit")
        return exit_line == IPOPT_OPTIMAL, f"Ipopt: {exit_line}"
    errors = record.get("solver_errors") or []
    uncalculated = sorted(tag for tag, done in record.get("calculated", {}).items() if not done)
    ok = not errors and not uncalculated and bool(record.get("calculated"))
    what = f"solver errors {errors}, not calculated {uncalculated}"
    recycle = record.get("raw_output", {}).get("units", {}).get("REC")
    if recycle is not None:
        ok = (
            ok
            and recycle["Converged"]
            and recycle["IterationsTaken"] < recycle["MaximumIterations"]
        )
        what += (
            f", Recycle converged {recycle['Converged']} in {recycle['IterationsTaken']} of "
            f"{recycle['MaximumIterations']}"
        )
    return ok, what


def rule2(record: dict[str, Any], tool: str) -> str | None:
    """The reference-accuracy problem, if any (spec §9.5 rule 2)."""
    ok, what = converged(record, tool)
    if not ok:
        return f"not converged ({what})"
    balance = record.get("self_check", {}).get("rule2_component_balance")
    if not balance:
        return "no component balance recorded"
    residuals = [float(v) for v in balance["residual_mol_per_s"].values()]
    if not all(math.isfinite(v) for v in residuals):
        return f"component balance not finite: {residuals}"
    worst = max(abs(Decimal(repr(v))) for v in residuals)
    if not worst <= RULE2_TOLERANCE:
        return f"component balance misses by {float(worst):.3g} mol/s"
    return None


def smooth_vle_settings(twin: dict[str, Any]) -> tuple[dict[str, Decimal], Decimal]:
    """The registered SmoothVLE `eps` (by parameter) and rule 2b's bound, from the twin."""
    closed = twin["closed_form"]
    registered = closed["reference_tool_settings"]["IDAES"]["smooth_vle"]
    eps = {which: Decimal(str(registered[f"{which}_K"])) for which in ("eps_1", "eps_2")}
    return eps, Decimal(str(closed["smooth_vle"]["self_check_bound_K"]))


def rule2b(record: dict[str, Any], twin: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    """IDAES's smoothing problem, if any (spec §9.5 rule 2b, A2), and what it was decided on.

    Recomputed from the record's own `raw_output` (its variables and its SmoothVLE parameters);
    the self-check the tool script recorded is not trusted.
    """
    eps, bound = smooth_vle_settings(twin)
    raw = record.get("raw_output", {})
    shift = fx.smooth_vle_shift(raw.get("variables", {}), raw.get("smooth_vle_parameters", {}))
    blocks = shift["blocks"]
    off = sorted(
        block
        for block, entry in blocks.items()
        if any(
            entry[f"{which}_K"] is None or Decimal(repr(float(entry[f"{which}_K"]))) != value
            for which, value in eps.items()
        )
    )
    worst = shift["max_shift_K"]
    detail = {
        "max_shift_K": None if worst is None else float(worst),
        "argmax": shift["argmax"],
        "bound_K": str(bound),
        "smooth_vle_blocks": len(blocks),
        "blocks_without_the_registered_eps": off,
    }
    if not blocks:
        return "smooth_vle_shift(no SmoothVLE state block recorded)", detail
    if worst is None:
        return "smooth_vle_shift(not computable: a temperature missing or not finite)", detail
    if worst > bound or off:
        return f"smooth_vle_shift({float(worst):.3e} K)", detail
    return None, detail


def tool_quantities(record: dict[str, Any], tool: str, fixture: str) -> dict[str, float]:
    """The tool's compared quantities. DWSIM's are recomputed from its raw output and must equal
    what the record reports (a harness defect otherwise); IDAES's are read from the record."""
    reported = {q: float(v) for q, v in record["compared_quantities"].items()}
    if tool == "DWSIM":
        recomputed = fx.dwsim_compared_quantities(fixture, record["raw_output"])
        if recomputed != reported:
            raise ValueError(f"DWSIM {fixture}: compared quantities differ from its raw output")
    return reported


# ---- the table ----------------------------------------------------------------------------------


def _ratio(numerator: Decimal, denominator: Decimal) -> float:
    return float(numerator / denominator)


def classify(
    fixture: str,
    tool: str,
    record: dict[str, Any] | None,
    ours: dict[str, Any] | None,
    quantities: dict[str, dict[str, str]],
    control_problem: str | None,
    absence_registered: bool,
    twin_document: dict[str, Any],
    apply_rule_2b: bool = True,
) -> dict[str, Any]:
    """Spec §9.5's rules in order. `apply_rule_2b=False` only for the table W8's default-ε
    records produced (retained beside their rule 2b classification, never counted)."""
    row: dict[str, Any] = {"fixture": fixture, "tool": tool}

    def result(classification: str, category: str | None, reason: str) -> dict[str, Any]:
        label = classification if category is None else f"{classification}({category}: {reason})"
        if category == "ours_not_verified":
            label = f"{classification}(ours_not_verified)"
        return {
            **row,
            "classification": classification,
            "category": category,
            "reason": reason,
            "label": label,
        }

    if record is not None and "not_applicable" in record and absence_registered:
        return {
            **result("not_applicable", None, record["not_applicable"]),
            "label": "not_applicable",
            "rule": "registered_absence",
        }
    access = rule1(record, tool)
    if access is not None:
        return {**result("NOT_COMPARABLE", "access", access), "rule": 1}
    assert record is not None
    accuracy = rule2(record, tool)
    if accuracy is not None:
        return {**result("NOT_COMPARABLE", "reference_accuracy", accuracy), "rule": 2}
    if control_problem is not None:
        return {**result("NOT_COMPARABLE", "reference_accuracy", control_problem), "rule": 2}
    if tool == "IDAES" and apply_rule_2b:
        smoothing, detail = rule2b(record, twin_document)
        row["smooth_vle"] = detail
        if smoothing is not None:
            return {**result("NOT_COMPARABLE", "semantics", smoothing), "rule": "2b"}
    if (
        ours is None
        or ours.get("outcome") != "CONVERGED"
        or ours.get("verification_status") != "VERIFIED"
    ):
        status = (
            None if ours is None else f"{ours.get('outcome')} {ours.get('verification_status')}"
        )
        return {**result("NOT_COMPARABLE", "ours_not_verified", f"ours: {status}"), "rule": 3}

    values = tool_quantities(record, tool, fixture)
    table = []
    for quantity, entry in quantities.items():
        twin = Decimal(entry["value"])
        tol = Decimal(entry["tolerance"])
        ours_value = float(ours["compared_quantities"][quantity])
        tool_value = values[quantity]
        o, t = Decimal(repr(ours_value)), Decimal(repr(tool_value))
        table.append(
            {
                "quantity": quantity,
                "kind": entry["kind"],
                "ours": ours_value,
                "tool": tool_value,
                "twin": entry["value"],
                "tolerance": entry["tolerance"],
                "abs_ours_minus_tool": float(abs(o - t)),
                # Decided exactly, in decimal, on the doubles as recorded.
                "within_tolerance": abs(o - t) <= tol,
                "ratio": _ratio(abs(o - t), tol),
                "ours_vs_twin_ratio": _ratio(abs(o - twin), tol),
                "tool_vs_twin_ratio": _ratio(abs(t - twin), tol),
            }
        )
    worst = max(table, key=lambda r: (r["ratio"], r["quantity"]))
    outside = sum(not r["within_tolerance"] for r in table)
    word = "AGREE" if outside == 0 else "DISAGREE"
    reason = (
        f"every registered quantity within tolerance; worst {worst['quantity']} at "
        f"{worst['ratio']:.3g} of its tolerance"
        if outside == 0
        else f"{outside} of {len(table)} quantities outside tolerance; worst "
        f"{worst['quantity']} at {worst['ratio']:.4g} of its tolerance"
    )
    return {
        **result(word, None, reason),
        "rule": 4,
        "worst_quantity": worst["quantity"],
        "worst_ratio": worst["ratio"],
        "quantities": table,
    }


def compute(results: Path = RESULTS, twin_path: Path = TWIN) -> dict[str, Any]:
    """The whole comparison document, from the committed files alone."""
    twin = yaml.safe_load(twin_path.read_text(encoding="utf-8"))
    records: dict[tuple[str, str], dict[str, Any] | None] = {}
    for tool in TOOLS:
        for fixture in FIXTURES:
            path = results / f"{tool.lower()}-{fixture}.json"
            records[tool, fixture] = _load_json(path) if path.exists() else None
    ours: dict[str, dict[str, Any] | None] = {}
    for fixture in FIXTURES:
        path = results / f"ours-{OURS_OF[fixture]}.json"
        ours[fixture] = _load_json(path) if path.exists() else None

    rows = []
    for fixture in FIXTURES:
        quantities = registered(twin, fixture)
        for tool in TOOLS:
            control_problem = None
            for control, same in CONTROL_FIXTURE.items():
                if same == fixture:
                    record = records[tool, control]
                    if record is not None and rule1(record, tool) is None:
                        problem = rule2(record, tool)
                        if problem is not None:
                            control_problem = (
                                f"positive control {control} on this fixture: {problem}"
                            )
            rows.append(
                classify(
                    fixture,
                    tool,
                    records[tool, fixture],
                    ours[fixture],
                    quantities,
                    control_problem,
                    registered_absence(twin, fixture, tool),
                    twin,
                )
            )

    # W8's default-ε IDAES records: rule 2b's classification, and the table they produced without
    # it. No positive control maps onto an IDAES fixture (CONTROL_FIXTURE is DWSIM's PC-1 only).
    superseded = []
    for fixture in FIXTURES:
        path = results / f"{DEFAULT_EPS_PREFIX}{fixture}.json"
        if not path.exists():
            continue
        record = _load_json(path)
        args = (fixture, "IDAES", record, ours[fixture], registered(twin, fixture), None, False)
        superseded.append(
            {
                "record": f"references/results/{path.name}",
                **classify(*args, twin),
                "without_rule_2b": classify(*args, twin, apply_rule_2b=False),
            }
        )

    by = {(r["fixture"], r["tool"]): r for r in rows}
    compared = {"AGREE", "DISAGREE"}
    one = [f for f in REF_FIXTURES if any(by[f, t]["classification"] in compared for t in TOOLS)]
    both = [f for f in REF_FIXTURES if all(by[f, t]["classification"] in compared for t in TOOLS)]
    controls = {
        f"{fixture}/{tool}": by[fixture, tool]["label"]
        for fixture in POSITIVE_CONTROLS
        for tool in TOOLS
    }
    control_ok = all(
        by[f, t]["classification"] == "DISAGREE"
        or (
            by[f, t]["classification"] == "NOT_COMPARABLE"
            and by[f, t]["category"] == "reference_accuracy"
        )
        or (by[f, t]["classification"] == "not_applicable" and registered_absence(twin, f, t))
        for f in POSITIVE_CONTROLS
        for t in TOOLS
    )
    # Every file the table was computed from, by the name it has under `benchmarks/t06/`.
    inputs = {f"references/results/{p.name}": _sha256(p) for p in sorted(results.glob("*.json"))}
    inputs[f"{twin_path.name}"] = _sha256(twin_path)
    eps, bound = smooth_vle_settings(twin)
    return {
        "schema": SCHEMA,
        "authority": "docs/derivations/T06-corpus-spec.md §9.2-§9.5 (Amendments 1 and 2); "
        "A47-A54, A83",
        "classification_is_mechanical": "the recorded verdict is the verdict agent's, "
        "on this table",
        "tolerance_rule": "|ours - tool| <= a_k + 1e-6 |v_twin| (spec §9.4)",
        "allowances": {kind: str(a) for kind, a in ALLOWANCE.items()},
        "rule2_tolerance_mol_per_s": str(RULE2_TOLERANCE),
        "rule2b": {
            "registered_eps_K": {k: str(v) for k, v in eps.items()},
            "shift_bound_K": str(bound),
        },
        "inputs_sha256": inputs,
        "rows": rows,
        "superseded_default_eps": {
            "what": "W8's IDAES records at IDAES's default SmoothVLE smoothing (eps_1 = 0.01 K, "
            "eps_2 = 5e-4 K), superseded by the re-run at the registered eps; retained with their "
            "rule 2b classification and, under without_rule_2b, the table they produced "
            "(spec §9.5 rule 2b, A83). Counted nowhere.",
            "rows": superseded,
        },
        "positive_controls": {
            "classifications": controls,
            "all_as_required": control_ok,
            "requirement": "PC-1 (DWSIM) and PC-2 (DWSIM, IDAES) DISAGREE, or "
            "NOT_COMPARABLE(reference_accuracy); (PC-1, IDAES) not_applicable (spec §9.5, A51)",
        },
        "v16_counts": {
            "fixtures_compared_by_at_least_one_tool": len(one),
            "fixtures_compared_by_both_tools": len(both),
            "of": len(REF_FIXTURES),
            "at_least_one": one,
            "both": both,
        },
    }


def dumps(document: dict[str, Any]) -> str:
    return json.dumps(document, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def _shift(r: dict[str, Any]) -> str:
    shift = r.get("smooth_vle", {}).get("max_shift_K")
    return "—" if shift is None else f"{shift:.2g} K"


def markdown(document: dict[str, Any]) -> str:
    lines = [
        "| Fixture | Tool | Classification | Worst quantity | Worst ratio | Rule 2b shift |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in document["rows"]:
        worst = f"{r['worst_ratio']:.4g}" if "worst_ratio" in r else "—"
        quantity = r.get("worst_quantity", "—")
        lines.append(
            f"| {r['fixture']} | {r['tool']} | {r['label']} | {quantity} | {worst} | {_shift(r)} |"
        )
    counts = document["v16_counts"]
    one, both = (
        counts["fixtures_compared_by_at_least_one_tool"],
        counts["fixtures_compared_by_both_tools"],
    )
    lines.append("")
    lines.append(
        f"V16: {one} of {counts['of']} fixtures compared by at least one tool, {both} by both. "
        f"Positive controls as required: {document['positive_controls']['all_as_required']}."
    )
    lines += [
        "",
        "Superseded (W8, IDAES's default smoothing; counted nowhere):",
        "",
        "| Fixture | Tool | Classification | Without rule 2b | Worst quantity | Worst ratio |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in document["superseded_default_eps"]["rows"]:
        before = r["without_rule_2b"]
        worst = f"{before['worst_ratio']:.4g}" if "worst_ratio" in before else "—"
        lines.append(
            f"| {r['fixture']} | {r['tool']} | {r['label']} | {before['label']} | "
            f"{before.get('worst_quantity', '—')} | {worst} |"
        )
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
        print(f"wrote {TABLE.relative_to(ROOT)}")
    elif args.check:
        same = TABLE.exists() and TABLE.read_text(encoding="utf-8") == dumps(document)
        print("comparison.json recomputes identically" if same else "comparison.json differs")
        return 0 if same else 1
    else:
        print(markdown(document), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
