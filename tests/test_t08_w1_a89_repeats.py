"""T08.A15 (W1.6): T06 A89's case repeated — the committed records (T08 release spec §6.1, §9).

`scripts/t08_a89_repeats.py` runs THM-09 start 2 under `T06-revision-v2` in a fresh interpreter
per repetition and records outcome, verification, S3's worst ratio and the refinement count:
`benchmarks/t08/a89/ref-x86-64.json` once on `ref-x86-64` (local), and
`benchmarks/t08/a89/ci-aarch64.json` 20 times on the aarch64 class (CI job `a89-repeats`, dispatch
input `a89_repeats`). The aarch64 half skips — never passes — until its record is committed.

The criterion is A89's registered outcome on every repetition — `CONVERGED`, `VERIFIED`, S3's worst
ratio ≤ 0.1 — with the refinement count recorded, not asserted: whether A89 keeps "exactly one
refinement" is the design lane's amendment to make from these counts.
"""

from __future__ import annotations

from typing import Any

import pytest
from conftest import REPO_ROOT, load_json

RECORDS = REPO_ROOT / "benchmarks" / "t08" / "a89"
CLASSES = {"ref-x86-64": ("x86_64", 1), "ci-aarch64": ("aarch64", 20)}


def _record(label: str) -> dict[str, Any]:
    path = RECORDS / f"{label}.json"
    if not path.is_file():
        pytest.skip(
            f"T08.A15's {label} half is pending: dispatch the CI input `a89_repeats` and commit "
            f"the uploaded record as {path.relative_to(REPO_ROOT)}"
        )
    loaded = load_json(path)
    assert isinstance(loaded, dict)
    return loaded


@pytest.mark.parametrize("label", sorted(CLASSES))
def test_a15_every_repetition_ends_with_a89s_registered_outcome(label: str) -> None:
    record = _record(label)
    machine, repetitions = CLASSES[label]
    assert record["format"] == "t08-a89-repeats-v1"
    assert (record["case"], record["start"], record["policy"]) == ("THM-09", 2, "T06-revision-v2")
    assert record["ratio_bound"] == 0.1
    assert (record["label"], record["host"]["machine"]) == (label, machine)
    assert record["host"]["threads"] == {
        "MKL_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
    }
    rows = record["repetitions"]
    assert [row["repetition"] for row in rows] == list(range(1, repetitions + 1))
    for row in rows:
        assert row["crash"] is None, row
        assert row["outcome"] == "CONVERGED", row
        assert row["verification"] == "VERIFIED", row
        assert row["s3_worst_ratio"] <= 0.1, row
        assert row["meets_a89_outcome"] is True
        # Recorded, not judged: the count A89's amendment will be written from.
        assert row["refinement_count"] == len(row["refinements"])
    counts: dict[str, int] = {}
    for row in rows:
        counts[str(row["refinement_count"])] = counts.get(str(row["refinement_count"]), 0) + 1
    assert record["refinement_counts"] == dict(sorted(counts.items()))
    assert record["all_meet_a89_outcome"] is True
