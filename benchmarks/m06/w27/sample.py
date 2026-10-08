"""The W27 sample: 45 cases drawn from `coverage.json` by a rule nobody can steer (§6).

Normative text: registration §6 (W27-R26…R31) and R-178. The frame is every case not
`ARTIFACT_INCOMPLETE`; `CANDIDATE` cases first; the rest by family, largest remainder with a
minimum of one for families of at least four cases; within a family by SHA-256 rank of a fixed
seed. No RNG library is involved, so a re-draw is byte-identical (W27-A20). Size, seed, minimum
and canary count are read from `registration.json#/sample`.

Run: `python -m benchmarks.m06.w27.sample COVERAGE [--out sample.json]`.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from fractions import Fraction
from pathlib import Path
from typing import Any, Final

from benchmarks.m06.w27 import registration

SCHEMA: Final[str] = "w27-sample-v1"


def _parameters() -> tuple[int, int, int]:
    table = registration.load()["sample"]
    return int(table["size"]), int(table["min_family_size_for_one"]), int(table["canaries"])


def allocate(populations: Mapping[str, int], slots: int) -> dict[str, int]:
    """W27-R28: largest remainder over families with the minimum of one, ties by the seeded
    family hash, never beyond a family's size; an excess removed from the smallest remainder
    that keeps its minimum."""
    _, minimum, _ = _parameters()
    total = sum(populations.values())
    if slots <= 0 or total == 0:
        return dict.fromkeys(populations, 0)
    slots = min(slots, total)
    share = {f: Fraction(slots * n, total) for f, n in populations.items()}
    alloc = {f: int(share[f]) for f in populations}
    eligible = [f for f, n in populations.items() if n >= minimum]
    bumped: set[str] = set()
    if len(eligible) <= slots:
        for f in eligible:
            if alloc[f] == 0:
                alloc[f] = 1
                bumped.add(f)

    def rank(f: str) -> tuple[Fraction, str]:
        return (-(share[f] - int(share[f])), registration.hash_rank("family", f))

    deficit = slots - sum(alloc.values())
    while deficit > 0:
        open_ = [f for f in populations if f not in bumped and alloc[f] < populations[f]]
        if not open_:
            open_ = [f for f in populations if alloc[f] < populations[f]]
        for f in sorted(open_, key=rank)[:deficit]:
            alloc[f] += 1
            deficit -= 1
        bumped = set()
    while deficit < 0:
        reducible = [f for f in populations if alloc[f] > (1 if f in eligible else 0)]
        f = sorted(reducible, key=rank)[-1]
        alloc[f] -= 1
        deficit += 1
    return alloc


def bumped_families(populations: Mapping[str, int], slots: int) -> list[str]:
    """The families W27-R28 lifts to one slot by the minimum (recorded)."""
    _, minimum, _ = _parameters()
    total = sum(populations.values())
    if slots <= 0 or total == 0:
        return []
    eligible = [f for f, n in populations.items() if n >= minimum]
    if len(eligible) > slots:
        return []
    return sorted(f for f in eligible if slots * populations[f] < total)


def _family_draw(rows: Sequence[Mapping[str, Any]], slots: int) -> tuple[list[str], dict[str, Any]]:
    """W27-R28/R29 over `rows`: the allocation, then the first `a_f` of each family by rank."""
    by_family: dict[str, list[str]] = {}
    for row in rows:
        by_family.setdefault(row["family"], []).append(row["case_id"])
    populations = {f: len(v) for f, v in sorted(by_family.items())}
    alloc = allocate(populations, slots)
    chosen: list[str] = []
    for family, ids in sorted(by_family.items()):
        ranked = sorted(ids, key=lambda c: registration.hash_rank("case", c))
        chosen += ranked[: alloc[family]]
    return sorted(chosen), {
        "populations": populations,
        "allocation": alloc,
        "bumped_by_minimum": bumped_families(populations, slots),
    }


def draw(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """W27-R26…R31: the frame, candidates first, the stratified rest, the order, the canaries."""
    size, _, canaries = _parameters()
    frame = [r for r in rows if r["class"] != "ARTIFACT_INCOMPLETE"]
    candidates = [r for r in frame if r["class"] == "CANDIDATE"]
    others = [r for r in frame if r["class"] != "CANDIDATE"]
    stages: dict[str, Any]
    if len(candidates) >= size:
        chosen, stage = _family_draw(candidates, size)
        stages = {"candidates": stage, "others": None}
    else:
        rest, stage = _family_draw(others, size - len(candidates))
        chosen = sorted([r["case_id"] for r in candidates] + rest)
        stages = {"candidates": "all", "others": stage}
    order = sorted(chosen, key=lambda c: registration.hash_rank("order", c))
    taken = set(chosen)
    remaining = sorted(
        (r["case_id"] for r in frame if r["case_id"] not in taken),
        key=lambda c: registration.hash_rank("canary", c),
    )
    by_id = {r["case_id"]: r for r in rows}
    return {
        "frame_size": len(frame),
        "excluded": sorted(r["case_id"] for r in rows if r["class"] == "ARTIFACT_INCOMPLETE"),
        "candidate_count": len(candidates),
        "stages": stages,
        "cases": chosen,
        "run_order": order,
        "canaries": remaining[:canaries],
        "composition": {
            "classes": dict(Counter(by_id[c]["class"] for c in chosen)),
            "families": dict(sorted(Counter(by_id[c]["family"] for c in chosen).items())),
            "in_full82": sum(1 for c in chosen if by_id[c]["in_full82"]),
            "residual_check_not_pass": sorted(
                c for c in chosen if by_id[c]["residual_check"] != "pass"
            ),
        },
    }


def sample_document(coverage: Mapping[str, Any], coverage_bytes: bytes) -> dict[str, Any]:
    """`sample.json` (W27-R58): the draw from `coverage`, bound to that file by its SHA-256."""
    return {
        "schema": SCHEMA,
        "coverage_sha256": registration.sha256_bytes(coverage_bytes),
        "seed_text": registration.load()["sample"]["seed_text"],
        **draw(coverage["rows"]),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="W27 sample (registration §6) from coverage")
    parser.add_argument("coverage", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    data = args.coverage.read_bytes()
    document = sample_document(json.loads(data), data)
    args.out.write_bytes(registration.dump(document))
    print(f"wrote {args.out}: {len(document['cases'])} cases, canaries {document['canaries']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
