"""S08b design-time report over `s08b_probe`'s `observe` records. NOT a gate, NOT a test.

    python docs/derivations/scripts/s08b_design/scan_report.py OBSERVE_DIR > report.txt

M1: where the `"."` heuristic and the explicit item rule disagree, and whether the restart
selection or the `phase_wall` change list differs. S1: every accepted lifted `TWO_PHASE` split,
grouped by kind (`.stage.` in the unit id: a column or cascade stage; otherwise a flash-type
split) and provider, with its saturation errors, its minority flow and the raw kernel's verdict at
its `(T, P)`. S2: near-trivial `TWO_PHASE` answers of the raw providers, by test file.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _records(directory: Path) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for path in sorted(directory.glob("observe-*.jsonl")):
        with path.open() as source:
            found.extend(json.loads(line) for line in source)
    return found


def _file(test: str) -> str:
    return test.split("::", 1)[0]


def _numeric(value: Any) -> float | None:
    return value if isinstance(value, float) and math.isfinite(value) else None


def m1(records: list[dict[str, Any]]) -> None:
    print("## M1 item/unit classification")
    print(f"records {len(records)}; tests {len({r['test'] for r in records})}")
    undotted = sorted({k for r in records for k in r["sample"] if "." not in k})
    print(f"undotted keys the explicit rule calls items: {undotted[:5]}")
    other = sorted({k for r in records for k in r["sample"] if ".stage." not in k})
    print(f"disagreeing keys outside `.stage.` ids: {other[:5]}")
    print(f"by outcome: {dict(Counter(r['outcome'] for r in records))}")
    consulted = [r for r in records if r["consulted"]]
    moved = [r for r in consulted if r["old_index"] != r["new_index"]]
    print(
        f"consulted the restart selection: {len(consulted)}; chose a different candidate: "
        f"{len(moved)}"
    )
    for record in moved[:20]:
        print(
            f"  MOVED {record['test']} frozen={record['frozen']} "
            f"old={record['old_index']} new={record['new_index']} {record['candidates']}"
        )
    changes = Counter((r["old_changes"], r["new_changes"]) for r in consulted)
    for (old, new), count in sorted(changes.items(), key=lambda item: -item[1])[:20]:
        print(f"  {count:6d}  old={old!r} new={new!r}")
    files = Counter(_file(r["test"]) for r in consulted)
    print(f"consulting test files: {dict(sorted(files.items()))}")


def s1(records: list[dict[str, Any]]) -> None:
    print("\n## S1 accepted lifted TWO_PHASE splits")
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        kind = "stage" if ".stage." in record["unit"] else "flash"
        groups[(kind, record["provider"])].append(record)
    for (kind, provider), group in sorted(groups.items()):
        errors = [
            max(abs(b), abs(d))
            for r in group
            if (b := _numeric(r.get("bubble_error"))) is not None
            and (d := _numeric(r.get("dew_error"))) is not None
        ]
        refused = sum(
            1
            for r in group
            if _numeric(r.get("bubble_error")) is None or _numeric(r.get("dew_error")) is None
        )
        kernel = Counter(str(r.get("kernel", ("n/a", "n/a"))[1]) for r in group)
        minority = min(min(r["V"], r["L"]) / r["n"] for r in group if r["n"] > 0)
        product = min(r["V"] * r["L"] for r in group)
        print(
            f"{kind}/{provider}: n={len(group)} tests={len({r['test'] for r in group})} "
            f"max_sat_error={max(errors) if errors else None!r} K non_numeric={refused} "
            f"min_minority_fraction={minority:.3e} min_LV={product:.3e} kernel={dict(kernel)}"
        )
        worst = sorted(
            group,
            key=lambda r: -max(
                abs(_numeric(r.get("bubble_error")) or 0.0),
                abs(_numeric(r.get("dew_error")) or 0.0),
            ),
        )
        for r in worst[:8]:
            print(
                f"  {r['test']} {r['unit']} V={r['V']:.4g} L={r['L']:.4g} n={r['n']:.4g} "
                f"T={r['T']:.6f} bub={r.get('bubble_error')} dew={r.get('dew_error')} "
                f"kernel={r.get('kernel')}"
            )
        small = sorted(group, key=lambda r: min(r["V"], r["L"]) / max(r["n"], 1e-300))
        for r in small[:6]:
            print(
                f"  SMALLEST {r['test']} {r['unit']} V={r['V']:.4g} L={r['L']:.4g} "
                f"bub={r.get('bubble_error')} dew={r.get('dew_error')} kernel={r.get('kernel')}"
            )
        disagree = [r for r in group if str(r.get("kernel", ("", ""))[1]) in ("LIQUID", "VAPOR")]
        for r in disagree[:6]:
            print(
                f"  KERNEL-SINGLE {r['test']} {r['unit']} V={r['V']:.4g} L={r['L']:.4g} "
                f"bub={r.get('bubble_error')} dew={r.get('dew_error')} kernel={r.get('kernel')}"
            )


def s2(records: list[dict[str, Any]]) -> None:
    print("\n## S2 near-trivial TWO_PHASE provider answers (minority fraction < 1e-6)")
    files = Counter(_file(r["test"]) for r in records)
    print(f"records {len(records)}; by file: {dict(sorted(files.items()))}")
    smallest = sorted(records, key=lambda r: min(r["vapor_fraction"], 1 - r["vapor_fraction"]))
    for r in smallest[:6]:
        print(f"  {r['test']} {r['provider']} beta={r['vapor_fraction']!r} T={r['T']}")


def _error(record: dict[str, Any]) -> float | None:
    bubble, dew = _numeric(record.get("bubble_error")), _numeric(record.get("dew_error"))
    return None if bubble is None or dew is None else max(abs(bubble), abs(dew))


def s1_breakdown(records: list[dict[str, Any]]) -> None:
    """Stages by unit prefix and test file; flash-type SYN-001 splits by minority fraction."""
    print("\n## S1 stages by unit and test file")
    stages: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        if ".stage." in r["unit"]:
            stages[(r["unit"].split(".stage.")[0], _file(r["test"]))].append(r)
    for (unit, test_file), group in sorted(stages.items()):
        errors = [e for r in group if (e := _error(r)) is not None]
        print(
            f"{unit} {test_file}: n={len(group)} max_sat_error={max(errors):.3g} K "
            f"min_LV={min(r['V'] * r['L'] for r in group):.3g} "
            f"min_V_or_L={min(min(r['V'], r['L']) for r in group):.3g}"
        )
    print("\n## S1 flash-type SYN-001 splits by minority fraction min(V, L)/n")
    flashes = [
        r for r in records if ".stage." not in r["unit"] and r["provider"] == "Syn001Provider"
    ]
    for low, high in ((1e-3, 2.0), (1e-6, 1e-3), (1e-10, 1e-6), (0.0, 1e-10)):
        group = [r for r in flashes if low <= min(r["V"], r["L"]) / r["n"] < high]
        errors = [e for r in group if (e := _error(r)) is not None]
        kernel = dict(Counter(str(r["kernel"][1]) for r in group))
        print(
            f"[{low:g}, {high:g}): n={len(group)} tests={len({r['test'] for r in group})} "
            f"max_sat_error={max(errors) if errors else None!r} "
            f"over_1e-4={sum(1 for e in errors if e > 1e-4)} kernel={kernel}"
        )
    distinct: Counter[tuple[str, ...]] = Counter()
    for r in flashes:
        error = _error(r)
        if min(r["V"], r["L"]) / r["n"] < 1e-6 or (error is not None and error > 1e-4):
            distinct[
                (
                    _file(r["test"]),
                    r["unit"],
                    f"V={r['V']:.4g}",
                    f"L={r['L']:.4g}",
                    f"bub={r['bubble_error']:.3g}",
                    f"dew={r['dew_error']:.3g}",
                    f"kernel={r['kernel'][1]}:{r['kernel'][2]!r}",
                )
            ] += 1
    for key, count in distinct.items():
        print(f"  {count} x {' '.join(key)}")


def main() -> int:
    records = _records(Path(sys.argv[1]))
    kinds: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        kinds[record["kind"]].append(record)
    m1(kinds["M1"])
    s1(kinds["S1"])
    s1_breakdown(kinds["S1"])
    s2(kinds["S2"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
