"""S10-C R-782, note §8 (2026-10-26): G-R7's class-level comparisons of T06 ensemble run records.

Evidence script (design lane). It reads run documents only and classifies each start with T06's own
scoring (`benchmarks.t06.ensemble.classify`, `rescued`); it never writes or edits a record.

    PYTHONPATH=src:. python <this script> classes OLD NEW LABEL
        OLD = the committed same-class record, NEW = the R-782 run of the same starts file.
        Prints the class changes by kind (failure -> SUCCESS, SUCCESS -> failure,
        failure -> failure), S, and the starts whose final state moved in bits.
    PYTHONPATH=src:. python <this script> cross A B LABEL
        A, B = two records of the same starts file on different machine classes. Prints the
        per-start class disagreements, the rescue-status disagreements and S^first on each.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from typing import Any

from benchmarks.t06 import ensemble

Key = tuple[str, int]


def _records(path: str) -> dict[Key, dict[str, Any]]:
    with open(path, encoding="utf-8") as handle:
        return {(r["case"], r["start"]): r for r in json.load(handle)["records"]}


def _name(key: Key) -> str:
    return f"{key[0]}/{key[1]:02d}"


def _bits(record: dict[str, Any]) -> str:
    """The final state's identity: its full JSON (sorted keys), which A98 compares bitwise."""
    return json.dumps(record.get("state"), sort_keys=True)


def classes(old_path: str, new_path: str, label: str) -> int:
    old, new = _records(old_path), _records(new_path)
    if old.keys() != new.keys():
        print(f"{label}: start sets differ")
        return 2
    before = {k: ensemble.classify(r) for k, r in old.items()}
    after = {k: ensemble.classify(r) for k, r in new.items()}
    changes = sorted(k for k in old if before[k] != after[k])
    gained = [k for k in changes if after[k] == "SUCCESS"]
    lost = [k for k in changes if before[k] == "SUCCESS"]
    sideways = [k for k in changes if "SUCCESS" not in (before[k], after[k])]
    moved = sorted(k for k in old if _bits(old[k]) != _bits(new[k]))
    s_old = sum(v == "SUCCESS" for v in before.values())
    s_new = sum(v == "SUCCESS" for v in after.values())
    print(
        f"{label}: n={len(old)} S {s_old}->{s_new} changes={len(changes)} "
        f"fail->SUCCESS={len(gained)} SUCCESS->fail={len(lost)} fail->fail={len(sideways)} "
        f"bits_moved={len(moved)}"
    )
    for k in changes:
        print(
            f"   {_name(k)}: {before[k]} -> {after[k]} "
            f"(property_calls {old[k]['counters']['property_calls']} -> "
            f"{new[k]['counters']['property_calls']})"
        )
    print(
        f"   classes before {dict(Counter(before.values()))} after {dict(Counter(after.values()))}"
    )
    if len(moved) <= 40:
        print("   bits moved: " + " ".join(_name(k) for k in moved))
    return 0


def cross(a_path: str, b_path: str, label: str) -> int:
    a, b = _records(a_path), _records(b_path)
    if a.keys() != b.keys():
        print(f"{label}: start sets differ")
        return 2
    ca = {k: ensemble.classify(r) for k, r in a.items()}
    cb = {k: ensemble.classify(r) for k, r in b.items()}
    ra = {k: ensemble.rescued(r) for k, r in a.items()}
    rb = {k: ensemble.rescued(r) for k, r in b.items()}
    split = sorted(k for k in a if ca[k] != cb[k])
    rescue = sorted(k for k in a if ra[k] != rb[k])
    first_a = sum(ca[k] == "SUCCESS" and not ra[k] for k in a)
    first_b = sum(cb[k] == "SUCCESS" and not rb[k] for k in b)
    print(
        f"{label}: class disagreements={len(split)} rescue disagreements={len(rescue)} "
        f"S^first {first_a}|{first_b}"
    )
    for k in split:
        print(
            f"   class  {_name(k)}: {ca[k]}({a[k]['counters']['property_calls']}) | "
            f"{cb[k]}({b[k]['counters']['property_calls']})"
        )
    for k in rescue:
        print(f"   rescue {_name(k)}: {ra[k]} | {rb[k]}")
    return 0


def main() -> int:
    if len(sys.argv) != 5 or sys.argv[1] not in ("classes", "cross"):
        print(__doc__)
        return 2
    command, first, second, label = sys.argv[1:]
    return (classes if command == "classes" else cross)(first, second, label)


if __name__ == "__main__":
    sys.exit(main())
