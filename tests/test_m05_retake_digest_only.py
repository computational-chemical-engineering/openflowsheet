"""R-458 (AM-22): `scripts/m05_retake_diff.py --digest-only` on synthetic records.

A re-take passes iff every non-digest leaf is equal (timings excepted), the old->new digest map over
every digest leaf is a function and injective, and the environment files are byte-equal or differ
only in a `distributions_sha256` that the old version reproduces. R-458 A1 (E5a): the coupling
record's clear `frozen.reactor.fingerprint.openflowsheet_version` is admitted as `version` when it
is `--old-version` on the committed side and the running version on the re-take side, and each
frozen unit's `fingerprint_sha256` is bound to its `fingerprint`. Each case writes a committed and a
re-taken set of the five documents into `tmp_path` and changes one thing.
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

import pytest

import openflowsheet
from openflowsheet.canonical import document_sha256

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


V0, V1 = "0.1.1", "0.2.0a2.dev0"


def _frozen(version: str) -> dict[str, Any]:
    """A coupling record's frozen reactor at `version`, its fingerprint digest bound."""
    fingerprint = {
        "kind": "in_process",
        "module_sha256": "a" * 64,
        "openflowsheet_version": version,
    }
    return {
        "reactor": {"fingerprint": fingerprint, "fingerprint_sha256": document_sha256(fingerprint)}
    }


def _documents(first: str, second: str, version: str = V0) -> dict[str, Any]:
    """A record, ledger, store index, environment and one coupling record whose experiment keys are
    `first` and `second`, its frozen reactor at `version`."""
    frozen = _frozen(version)
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
        ".coupling/S0.json": {
            "frozen": frozen,
            "request": {
                "experiment_key": first,
                "environment_fingerprint_sha256": frozen["reactor"]["fingerprint_sha256"],
            },
            "residual": [1.5, -2.0],
        },
    }


def _write(stem: Path, documents: dict[str, Any]) -> None:
    for suffix, document in documents.items():
        path = Path(f"{stem}{suffix}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, indent=1), encoding="utf-8")


def _run(
    tmp_path: Path,
    change: Callable[[dict[str, Any]], None] | None = None,
    *,
    new: tuple[str, str],
    version: str = V0,
    old_version: str | None = None,
) -> tuple[bool, list[str]]:
    """The committed side at `V0`, the re-take at `version`, compared with `--old-version`."""
    old_stem, new_stem = tmp_path / "old" / "case", tmp_path / "new" / "case"
    _write(old_stem, _documents(K1, K2))
    retake = copy.deepcopy(_documents(*new, version=version))
    if change is not None:
        change(retake)
    _write(new_stem, retake)
    passed, lines = RETAKE.digest_only(old_stem, new_stem, old_version)
    return passed, lines


def test_a_consistent_relabelling_of_two_digests_passes(tmp_path: Path) -> None:
    # K3 and K4 sort in the other order than K1 and K2 would map to, so the store is reordered.
    passed, lines = _run(tmp_path, new=(K4, K3))
    assert passed, lines
    assert lines[0].startswith("RETAKE-DIGEST-ONLY PASS case: changed-digests=2 ")
    assert "version=0 other=0 environment=equal" in lines[0]


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


# -- R-458 A1 (E5a): the `version` class and the fingerprint binding ------------------------------


@pytest.fixture
def running_v1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(openflowsheet, "__version__", V1)


def test_the_version_leaf_pinned_and_bound_passes(tmp_path: Path, running_v1: None) -> None:
    # The fingerprint digest moves with the leaf, in `frozen` and in the request: one more changed.
    passed, lines = _run(tmp_path, new=(K3, K4), version=V1, old_version=V0)
    assert passed, lines
    assert lines[0].startswith("RETAKE-DIGEST-ONLY PASS case: changed-digests=3 ")
    assert "version=1 other=0" in lines[0]


def test_the_version_leaf_without_old_version_fails_naming_it(
    tmp_path: Path, running_v1: None
) -> None:
    passed, lines = _run(tmp_path, new=(K3, K4), version=V1)
    assert not passed
    assert "version=0 other=1" in lines[0]
    assert f"  coupling S0.json{RETAKE.VERSION_PATH}: {V0!r} vs {V1!r} (no --old-version)" in lines


def test_an_old_version_other_than_the_committed_side_fails(
    tmp_path: Path, running_v1: None
) -> None:
    passed, lines = _run(tmp_path, new=(K3, K4), version=V1, old_version="0.1.0")
    assert not passed
    assert any(f"committed {V0!r} is not --old-version '0.1.0'" in line for line in lines)


def test_a_retake_side_other_than_the_running_version_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(openflowsheet, "__version__", "0.2.0a3.dev0")
    passed, lines = _run(tmp_path, new=(K3, K4), version=V1, old_version=V0)
    assert not passed
    assert any(f"re-take {V1!r} is not the running '0.2.0a3.dev0'" in line for line in lines)


def test_a_version_move_that_keeps_the_old_fingerprint_digest_fails(
    tmp_path: Path, running_v1: None
) -> None:
    # Without the binding this passes: an unchanged digest is a valid map entry.
    stale = _frozen(V0)["reactor"]["fingerprint_sha256"]

    def keep_digest(documents: dict[str, Any]) -> None:
        coupling = documents[".coupling/S0.json"]
        coupling["frozen"]["reactor"]["fingerprint_sha256"] = stale
        coupling["request"]["environment_fingerprint_sha256"] = stale

    passed, lines = _run(tmp_path, keep_digest, new=(K3, K4), version=V1, old_version=V0)
    assert not passed
    assert any(
        "coupling S0.json (re-take): frozen.reactor.fingerprint_sha256" in line
        and "is not document_sha256 of its fingerprint" in line
        for line in lines
    )


def _version_elsewhere_in_coupling(documents: dict[str, Any], version: str) -> None:
    documents[".coupling/S0.json"]["frozen"]["reactor"]["openflowsheet_version"] = version


def _version_in_record(documents: dict[str, Any], version: str) -> None:
    documents[".json"]["runs"][0]["openflowsheet_version"] = version


@pytest.mark.parametrize(
    ("place", "leaf"),
    [
        (_version_elsewhere_in_coupling, "coupling S0.json.frozen.reactor.openflowsheet_version"),
        (_version_in_record, "record.runs[0].openflowsheet_version"),
    ],
)
def test_the_version_moving_at_another_path_is_other(
    tmp_path: Path,
    running_v1: None,
    place: Callable[[dict[str, Any], str], None],
    leaf: str,
) -> None:
    old_stem, new_stem = tmp_path / "old" / "case", tmp_path / "new" / "case"
    committed, retake = _documents(K1, K2), _documents(K3, K4, version=V1)
    place(committed, V0)
    place(retake, V1)
    _write(old_stem, committed)
    _write(new_stem, retake)
    passed, lines = RETAKE.digest_only(old_stem, new_stem, V0)
    assert not passed
    assert "version=1 other=1" in lines[0]
    assert f"  {leaf}: {V0!r} vs {V1!r}" in lines
