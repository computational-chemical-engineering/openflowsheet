"""R-458 (AM-22): `scripts/m05_retake_diff.py --digest-only` on synthetic records.

A re-take passes iff every non-digest leaf is equal (timings excepted), the old->new digest map over
every digest leaf is a function and injective, and the environment files are byte-equal or differ
only in a `distributions_sha256` that the old version reproduces. Each case writes a committed and
a re-taken set of the five documents into `tmp_path` and changes one thing.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import math
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "m05_retake_diff", ROOT / "scripts" / "m05_retake_diff.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RETAKE = _script()

K1, K2, K3, K4, K5 = (format(n, "x") * 64 for n in (1, 2, 3, 4, 5))
ENVIRONMENT = {"omp_num_threads": "1", "distributions": 17, "distributions_sha256": K5}


def _documents(first: str, second: str) -> dict[str, Any]:
    """A record, ledger, store index, environment and one coupling record whose experiment keys are
    `first` and `second`."""
    return {
        ".json": {
            "runs": [{"run_id": "C1", "value": 0.1, "experiment_key": first}],
            "start": {"coupling_record_sha256": second},
            "provenance": {"run_commit": "x", "wall_s": 1.0},
        },
        ".ledger.json": [{"experiment_key": first, "seq": 0}, {"experiment_key": second, "seq": 1}],
        ".store.json": sorted(
            [{"experiment_key": first, "attempt": 1}, {"experiment_key": second, "attempt": 1}],
            key=lambda entry: (entry["experiment_key"], entry["attempt"]),
        ),
        ".environment.json": ENVIRONMENT,
        ".coupling/S0.json": {"request": {"experiment_key": first}, "residual": [1.5, -2.0]},
    }


def _write(stem: Path, documents: dict[str, Any]) -> None:
    for suffix, document in documents.items():
        path = Path(f"{stem}{suffix}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, indent=1), encoding="utf-8")


def _run(
    tmp_path: Path, change: Callable[[dict[str, Any]], None] | None = None, *, new: tuple[str, str]
) -> tuple[bool, list[str]]:
    old_stem, new_stem = tmp_path / "old" / "case", tmp_path / "new" / "case"
    _write(old_stem, _documents(K1, K2))
    retake = copy.deepcopy(_documents(*new))
    if change is not None:
        change(retake)
    _write(new_stem, retake)
    passed, lines = RETAKE.digest_only(old_stem, new_stem)
    return passed, lines


def test_a_consistent_relabelling_of_two_digests_passes(tmp_path: Path) -> None:
    # K3 and K4 sort in the other order than K1 and K2 would map to, so the store is reordered.
    passed, lines = _run(tmp_path, new=(K4, K3))
    assert passed, lines
    assert lines[0].startswith("RETAKE-DIGEST-ONLY PASS case: changed-digests=2 ")
    assert "other=0 environment=equal" in lines[0]


def test_one_float_moved_by_one_ulp_fails_naming_the_leaf(tmp_path: Path) -> None:
    def nudge(documents: dict[str, Any]) -> None:
        residual = documents[".coupling/S0.json"]["residual"]
        residual[0] = math.nextafter(residual[0], math.inf)

    passed, lines = _run(tmp_path, nudge, new=(K3, K4))
    assert not passed
    assert lines[0].startswith("RETAKE-DIGEST-ONLY FAIL case: ")
    assert "other=1" in lines[0]
    assert [line for line in lines[1:] if "coupling S0.json.residual[0]: 1.5 vs" in line]


def test_two_old_digests_mapped_to_one_new_digest_fail(tmp_path: Path) -> None:
    passed, lines = _run(tmp_path, new=(K3, K3))
    assert not passed
    assert f"  map: {K3} is the image of two digests" in lines


def test_one_old_digest_mapped_to_two_new_digests_fails(tmp_path: Path) -> None:
    def split(documents: dict[str, Any]) -> None:
        documents[".coupling/S0.json"]["request"]["experiment_key"] = K4

    passed, lines = _run(tmp_path, split, new=(K3, K2))
    assert not passed
    assert f"  map: {K1} has two images {sorted([K3, K4])}" in lines


def test_an_environment_difference_outside_distributions_sha256_fails(tmp_path: Path) -> None:
    def other_threads(documents: dict[str, Any]) -> None:
        documents[".environment.json"] = {**ENVIRONMENT, "omp_num_threads": "2"}

    passed, lines = _run(tmp_path, other_threads, new=(K3, K4))
    assert not passed
    assert "environment=differs" in lines[0]
    assert any(
        "differs outside distributions_sha256 (['omp_num_threads'])" in line for line in lines
    )


def test_a_distributions_difference_needs_the_old_version(tmp_path: Path) -> None:
    def other_distributions(documents: dict[str, Any]) -> None:
        documents[".environment.json"] = {**ENVIRONMENT, "distributions_sha256": "6" * 64}

    passed, lines = _run(tmp_path, other_distributions, new=(K3, K4))
    assert not passed
    assert "environment=distributions" in lines[0]
    assert any("--old-version is required" in line for line in lines)
