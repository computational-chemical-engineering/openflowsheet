"""S03 WO-S03-1: this project's side of the column reference comparisons (S03 spec §3, §4, §8).

Maps each case of `docs/derivations/scripts/s03_cases.json` (inputs only) to a `ColumnSpec`,
solves it with `solve_column` and the SYN-001 provider, and writes one record per case to
`benchmarks/s03/references/results/ours-<case>.json`. A record carries only what the comparison
reads (§8): the case, the input file's SHA-256, the outcome, the final signature, and the
registered quantities of `cases.cases.<case>.quantities` by name, in SI units and in our stage
numbering (§4). The comparison (WO-S03-4) reads these records, never this module; the gate test
solves again live and checks that the committed record is what a solve produces today (A07).

Which cases have a record (§3, §12 WO-S03-1): RC1–RC5, the ten perturbed cases and PC-P. PC-L is
RC1 with DWSIM's unmapped latent heat, so its "ours" is RC1's record (§3.3; no file), as T06's
PC-1 is REF-04's.

The mapping (§3, §5.1 rows 2, 4, 8, 10): one pressure per stage and per inlet exactly as
registered; an inlet on port `top` enters stage 1, one on `bottom` stage N, any other port is a
side feed at its registered stage, each whole and in its declared phase; every stage that carries
no end specification is adiabatic (`Q_j* = 0`). Nothing is read from `s03_reference.json`.

Usage (from the repository root):
    PYTHONPATH=src:. .venv/bin/python scripts/s03_references_ours.py [--out DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from openflowsheet.models.syn001.cascade import (
    BOTTOM,
    TOP,
    CascadeFailure,
    DormantAnswer,
    InletState,
    SideFeed,
    liquid_total_id,
    stage_duty_id,
    stage_temperature_id,
    vapor_total_id,
)
from openflowsheet.models.syn001.column import (
    CONDENSER,
    REBOILER,
    ColumnSpec,
    EndSpecification,
    product_flow_id,
    reflux_fraction_id,
)
from openflowsheet.models.syn001.column_solve import S02_TARGET_POLICY, solve_column
from openflowsheet.thermo.syn001 import Syn001Provider

ROOT = Path(__file__).resolve().parent.parent
CASES_PATH = ROOT / "docs" / "derivations" / "scripts" / "s03_cases.json"
RESULTS = ROOT / "benchmarks" / "s03" / "references" / "results"

#: The column's unit id in every record's state ids (a CasADi token; `cascade._TOKEN`).
UNIT = "S03"

#: The cases with a record of their own, in `s03_cases.json`'s order (§12 WO-S03-1).
OURS_CASES: tuple[str, ...] = (
    "RC1",
    "RC2",
    "RC3",
    "RC4",
    "RC5",
    "RC1-RR",
    "RC1-BR",
    "RC1-z",
    "RC2-RR",
    "RC2-B",
    "RC2-z",
    "RC3-Q",
    "RC3-z",
    "RC4-D",
    "RC4-z",
    "PC-P",
)

#: Registered cases whose "ours" is another case's record (§3.3).
OURS_ALIASES: Mapping[str, str] = {"PC-L": "RC1"}

_STAGE_QUANTITY = re.compile(r"^(T|L|V)\[([1-9][0-9]*)\]$")
_PRODUCT_QUANTITY = re.compile(r"^(top|bottom)\[([A-Za-z0-9_]+)\]$")


def load_cases() -> dict[str, Any]:
    cases: dict[str, Any] = json.loads(CASES_PATH.read_bytes())
    return cases


def cases_sha256() -> str:
    return hashlib.sha256(CASES_PATH.read_bytes()).hexdigest()


def _end_specification(entry: Mapping[str, Any]) -> EndSpecification:
    extra = set(entry) - {"kind", "value", "component", "stage"}
    if extra:
        raise ValueError(f"unregistered specification fields {sorted(extra)}")
    stage = entry.get("stage")
    return EndSpecification(
        kind=entry["kind"],
        value=float(entry["value"]),
        component=entry.get("component"),
        stage=None if stage is None else int(stage),
    )


def column_spec(case: Mapping[str, Any], components: tuple[str, ...]) -> ColumnSpec:
    """`case` (one entry of `s03_cases.json`'s `cases`) as a `ColumnSpec` (§3, §5.1)."""
    count = int(case["stage_count"])
    condenser, reboiler = case["condenser"], case["reboiler"]
    specifications = case["specifications"]
    if set(specifications) - {CONDENSER, REBOILER}:
        raise ValueError(f"unregistered ends {sorted(specifications)}")
    pressures = tuple(float(p) for p in case["stage_pressures_Pa"])
    slot_stages = {1} if condenser != "none" else set()
    if reboiler != "none":
        slot_stages.add(count)
    duties = tuple(None if j in slot_stages else 0.0 for j in range(1, count + 1))
    top: InletState | None = None
    bottom: InletState | None = None
    sides: list[SideFeed] = []
    for inlet in case["inlets"]:
        state = InletState(
            n=tuple(float(a) for a in inlet["n_mol_per_s"]),
            temperature=float(inlet["T_K"]),
            pressure=float(inlet["P_Pa"]),
            phase=inlet["phase"],
        )
        port, stage = inlet["port"], int(inlet["stage"])
        if port == TOP:
            if stage != 1:
                raise ValueError(f"inlet {port} registered at stage {stage}, not 1")
            top = state
        elif port == BOTTOM:
            if stage != count:
                raise ValueError(f"inlet {port} registered at stage {stage}, not {count}")
            bottom = state
        else:
            sides.append(SideFeed(port, stage, state))
    condenser_entry = specifications.get(CONDENSER)
    reboiler_entry = specifications.get(REBOILER)
    return ColumnSpec(
        unit_id=UNIT,
        stage_count=count,
        pressures=pressures,
        duties=duties,
        condenser=condenser,
        reboiler=reboiler,
        condenser_spec=None if condenser_entry is None else _end_specification(condenser_entry),
        reboiler_spec=None if reboiler_entry is None else _end_specification(reboiler_entry),
        top=top,
        bottom=bottom,
        sides=tuple(sides),
        components=components,
    )


def quantity(spec: ColumnSpec, state: Mapping[str, float], name: str) -> float:
    """The registered quantity `name` (§4) at `state`, in SI units and our stage numbering."""
    unit, count = spec.unit_id, spec.stage_count
    found = _STAGE_QUANTITY.match(name)
    if found is not None:
        what, stage = found.group(1), int(found.group(2))
        if not 1 <= stage <= count:
            raise ValueError(f"{name}: stage outside 1..{count}")
        if what == "T":
            return float(state[stage_temperature_id(unit, stage)])
        if stage not in spec.equilibrium_stages():
            raise ValueError(f"{name}: stage {stage} is not an equilibrium stage")
        column = liquid_total_id if what == "L" else vapor_total_id
        return float(state[column(unit, stage)])
    found = _PRODUCT_QUANTITY.match(name)
    if found is not None:
        end, component = found.group(1), found.group(2)
        if component not in spec.components:
            raise ValueError(f"{name}: no component {component!r}")
        product = product_flow_id(spec, CONDENSER if end == "top" else REBOILER, component)
        return float(state[product])
    if name == "reflux":
        if not spec.total_condenser:
            raise ValueError("reflux: registered for a total condenser only")
        return float(state[reflux_fraction_id(unit)]) * float(state[vapor_total_id(unit, 2)])
    if name in ("Q_condenser", "Q_reboiler"):
        end = CONDENSER if name == "Q_condenser" else REBOILER
        if spec.end_kind(end) == "none":
            raise ValueError(f"{name}: the column has no {end}")
        return float(state[stage_duty_id(unit, spec.end_stage(end))])
    raise ValueError(f"{name}: not a registered quantity (§4)")


def solve(case_id: str, cases: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Our record for `case_id` (one of `OURS_CASES`): solve, then read the registered
    quantities. A refusal or a non-`CONVERGED` answer is a record too (rule 2: a failed run is a
    result), with its outcome and cause and no quantities."""
    if case_id not in OURS_CASES:
        raise ValueError(f"{case_id}: not one of {OURS_CASES}")
    document = load_cases() if cases is None else cases
    case = document["cases"][case_id]
    spec = column_spec(case, tuple(document["components"]))
    record: dict[str, Any] = {
        "case": case_id,
        "side": "ours",
        "cases_file": CASES_PATH.relative_to(ROOT).as_posix(),
        "cases_sha256": cases_sha256(),
        "unit_id": UNIT,
        "provider_id": Syn001Provider().describe().provider_id,
        "policy_id": S02_TARGET_POLICY.policy_id,
    }
    answer = solve_column(spec, Syn001Provider())
    if isinstance(answer, CascadeFailure):
        return {**record, "outcome": answer.outcome, "cause": answer.cause}
    if isinstance(answer, DormantAnswer):
        return {**record, "outcome": "DORMANT", "cause": ""}
    record["outcome"] = answer.outcome
    record["cause"] = answer.cause
    record["signature"] = list(answer.signature)
    if answer.outcome == "CONVERGED":
        record["quantities"] = {
            name: quantity(spec, answer.state, name) for name, _ in case["quantities"]
        }
    return record


def write(record: Mapping[str, Any], out: Path) -> Path:
    path = out / f"ours-{record['case']}.json"
    path.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=RESULTS)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    cases = load_cases()
    status = 0
    for case_id in OURS_CASES:
        record = solve(case_id, cases)
        path = write(record, args.out)
        status |= 0 if record["outcome"] == "CONVERGED" else 1
        print(f"ours {case_id}: {record['outcome']} -> {path.name}")
    return status


if __name__ == "__main__":
    sys.exit(main())
