"""R-458 (AM-22): `scripts/m05_retake_diff.py --digest-only` on synthetic records.

A re-take passes iff every non-digest leaf is equal (timings excepted), the old->new digest map over
every digest leaf is a function and injective, and the environment files are byte-equal or differ
only in a `distributions_sha256` that the old version reproduces. R-458 A1 (E5a): the coupling
record's clear `frozen.reactor.fingerprint.openflowsheet_version` is admitted as `version` when it
is `--old-version` on the committed side and the running version on the re-take side, and each
frozen unit's `fingerprint_sha256` is bound to its `fingerprint`. Each case writes a committed and a
re-taken set of the five documents into `tmp_path` and changes one thing.

R-1008 (`docs/reviews/REL040-s6-ruling.md` §8 WO-1, S6R-01 to S6R-10): the reactor fingerprint's
clear `platform` is admitted as `platform` when it is `--old-platform` on the committed side and the
running `platform.platform()` on the re-take side, every other leaf of that fingerprint is pinned,
and REAL's experiments archive is walked under the digest map.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import platform
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

import openflowsheet
from openflowsheet.canonical import canonical_json, document_sha256

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
    assert "version=0 platform=0 other=0 environment=equal" in lines[0]


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
    assert "version=1 platform=0 other=0" in lines[0]


def test_the_version_leaf_without_old_version_fails_naming_it(
    tmp_path: Path, running_v1: None
) -> None:
    passed, lines = _run(tmp_path, new=(K3, K4), version=V1)
    assert not passed
    assert "version=0 platform=0 other=1" in lines[0]
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
    assert "version=1 platform=0 other=1" in lines[0]
    assert f"  {leaf}: {V0!r} vs {V1!r}" in lines


# -- R-1008 (S6R-01 to S6R-10): the `platform` class and REAL's experiments archive ---------------

P0 = "Linux-6.12.111+deb13-amd64-x86_64-with-glibc2.41"
P1 = "Linux-6.12.113+deb13-amd64-x86_64-with-glibc2.41"
COUPLINGS = ("S0", "cand-C1-P1")


@pytest.fixture
def running_p1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(platform, "platform", lambda: P1)


def _reactor(host: str, **pins: str) -> dict[str, Any]:
    """A frozen out-of-process reactor on `host`, its fingerprint digest bound; `pins` override
    the fingerprint's other leaves."""
    fingerprint = {
        "export_tree_sha256": "c" * 64,
        "lock_sha256": "b" * 64,
        "machine": "x86_64",
        "platform": host,
        "python": "3.13.5",
        **pins,
    }
    return {
        "reactor": {"fingerprint": fingerprint, "fingerprint_sha256": document_sha256(fingerprint)}
    }


def _archive(keys: tuple[str, ...], fingerprint_sha256: str) -> dict[str, str]:
    """REAL's experiments archive: a request, a result and an attempt per key, as exact text."""
    files: dict[str, str] = {}
    for index, key in enumerate(keys):
        files[f"{key[:2]}/{key}/attempts/1.json"] = json.dumps(
            {"attempt": 1, "execution": {"timing": {"wall_s": 2.5}}, "experiment_key": key}
        )
        files[f"{key[:2]}/{key}/request.json"] = json.dumps(
            {"environment_fingerprint_sha256": fingerprint_sha256, "experiment_key": key}
        )
        files[f"{key[:2]}/{key}/result.json"] = json.dumps({"value": 0.25 + index})
    return dict(sorted(files.items()))


def _real(first: str, second: str, host: str = P0, **pins: str) -> dict[str, Any]:
    """`_documents` with REAL's shape: a frozen reactor on `host` in two coupling records and the
    experiments archive."""
    documents = _documents(first, second)
    del documents[".coupling/S0.json"]
    frozen = _reactor(host, **pins)
    digest = frozen["reactor"]["fingerprint_sha256"]
    for name, key in zip(COUPLINGS, (first, second), strict=True):
        documents[f".coupling/{name}.json"] = {
            "frozen": copy.deepcopy(frozen),
            "request": {"experiment_key": key, "environment_fingerprint_sha256": digest},
            "residual": [1.5, -2.0],
        }
    documents[".experiments.json"] = _archive((first, second), digest)
    return documents


def _run_real(
    tmp_path: Path,
    retake: dict[str, Any],
    old_platform: str | None = None,
    committed: dict[str, Any] | None = None,
) -> tuple[bool, list[str]]:
    old_stem, new_stem = tmp_path / "old" / "case", tmp_path / "new" / "case"
    _write(old_stem, _real(K1, K2) if committed is None else committed)
    _write(new_stem, retake)
    return RETAKE.digest_only(old_stem, new_stem, None, old_platform)


def test_s6r01_the_platform_leaf_pinned_and_bound_passes(tmp_path: Path, running_p1: None) -> None:
    passed, lines = _run_real(tmp_path, _real(K3, K4, P1), P0)
    assert passed, lines
    # K1, K2 and the fingerprint digest moved; the archive's attempts are equal (no timing).
    assert lines[0].startswith("RETAKE-DIGEST-ONLY PASS case: changed-digests=3 ")
    assert f"version=0 platform={len(COUPLINGS)} other=0 environment=equal" in lines[0]


def test_s6r02_the_platform_leaf_without_old_platform_fails_naming_it(
    tmp_path: Path, running_p1: None
) -> None:
    passed, lines = _run_real(tmp_path, _real(K3, K4, P1))
    assert not passed
    assert f"platform=0 other={len(COUPLINGS)}" in lines[0]
    assert (
        f"  coupling S0.json{RETAKE.PLATFORM_PATH}: {P0!r} vs {P1!r} (no --old-platform)" in lines
    )


def test_s6r03_an_old_platform_other_than_the_committed_side_fails(
    tmp_path: Path, running_p1: None
) -> None:
    passed, lines = _run_real(tmp_path, _real(K3, K4, P1), "Linux-6.12.110")
    assert not passed
    assert any(f"committed {P0!r} is not --old-platform 'Linux-6.12.110'" in x for x in lines)


def test_s6r04_a_retake_side_other_than_the_running_platform_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(platform, "platform", lambda: "Linux-6.12.114")
    passed, lines = _run_real(tmp_path, _real(K3, K4, P1), P0)
    assert not passed
    assert any(f"re-take {P1!r} is not the running 'Linux-6.12.114'" in x for x in lines)


def test_s6r05_a_platform_move_that_keeps_the_old_fingerprint_digest_fails(
    tmp_path: Path, running_p1: None
) -> None:
    stale = _reactor(P0)["reactor"]["fingerprint_sha256"]
    retake = _real(K3, K4, P1)
    for name in COUPLINGS:
        coupling = retake[f".coupling/{name}.json"]
        coupling["frozen"]["reactor"]["fingerprint_sha256"] = stale
        coupling["request"]["environment_fingerprint_sha256"] = stale
    retake[".experiments.json"] = _archive((K3, K4), stale)
    passed, lines = _run_real(tmp_path, retake, P0)
    assert not passed
    assert any(
        "coupling S0.json (re-take): frozen.reactor.fingerprint_sha256" in line
        and "is not document_sha256 of its fingerprint" in line
        for line in lines
    )


@pytest.mark.parametrize(
    ("leaf", "value"),
    [("lock_sha256", "d" * 64), ("export_tree_sha256", "e" * 64), ("python", "3.13.6")],
)
def test_s6r06_s6r07_another_fingerprint_leaf_moving_with_the_platform_is_other(
    tmp_path: Path, running_p1: None, leaf: str, value: str
) -> None:
    # The binding is recomputed, so only the pinned leaf itself is wrong.
    passed, lines = _run_real(tmp_path, _real(K3, K4, P1, **{leaf: value}), P0)
    assert not passed
    assert f"platform={len(COUPLINGS)} other={len(COUPLINGS)}" in lines[0]
    assert any(
        line.startswith(f"  coupling S0.json.frozen.reactor.fingerprint.{leaf}: ") for line in lines
    )


def _platform_in_record(documents: dict[str, Any], host: str) -> None:
    documents[".json"]["runs"][0]["platform"] = host


def _platform_outside_the_fingerprint(documents: dict[str, Any], host: str) -> None:
    documents[".coupling/S0.json"]["frozen"]["reactor"]["platform"] = host


@pytest.mark.parametrize(
    ("place", "leaf"),
    [
        (_platform_in_record, "record.runs[0].platform"),
        (_platform_outside_the_fingerprint, "coupling S0.json.frozen.reactor.platform"),
    ],
)
def test_s6r08_the_platform_moving_at_another_path_is_other(
    tmp_path: Path,
    running_p1: None,
    place: Callable[[dict[str, Any], str], None],
    leaf: str,
) -> None:
    committed, retake = _real(K1, K2), _real(K3, K4, P1)
    place(committed, P0)
    place(retake, P1)
    passed, lines = _run_real(tmp_path, retake, P0, committed)
    assert not passed
    assert f"platform={len(COUPLINGS)} other=1" in lines[0]
    assert f"  {leaf}: {P0!r} vs {P1!r}" in lines


# S6R-09: the experiments archive.


def test_s6r09_a_consistent_relabelling_of_the_archive_passes(tmp_path: Path) -> None:
    passed, lines = _run_real(tmp_path, _real(K4, K3))
    assert passed, lines
    assert "changed-digests=2 " in lines[0]
    assert "platform=0 other=0" in lines[0]


def test_s6r09_one_result_leaf_moved_by_one_ulp_fails_naming_it(tmp_path: Path) -> None:
    retake = _real(K3, K4)
    name = f"{K3[:2]}/{K3}/result.json"
    retake[".experiments.json"][name] = json.dumps({"value": math.nextafter(0.25, math.inf)})
    passed, lines = _run_real(tmp_path, retake)
    assert not passed
    assert "other=1" in lines[0]
    assert [x for x in lines if x.startswith(f"  experiments {K1[:2]}/{K1}/result.json.value: ")]


def test_s6r09_one_archive_file_missing_on_the_retake_side_fails(tmp_path: Path) -> None:
    retake = _real(K3, K4)
    del retake[".experiments.json"][f"{K4[:2]}/{K4}/request.json"]
    passed, lines = _run_real(tmp_path, retake)
    assert not passed
    assert any(f"experiments {K2[:2]}/{K2}/request.json: no re-taken file" in x for x in lines)


def test_s6r09_two_committed_keys_mapped_to_one_fail(tmp_path: Path) -> None:
    passed, lines = _run_real(tmp_path, _real(K3, K3))
    assert not passed
    assert f"  map: {K3} is the image of two digests" in lines


def test_s6r09_an_attempt_differing_only_in_its_wall_time_passes_as_timing(
    tmp_path: Path,
) -> None:
    retake = _real(K3, K4)
    name = f"{K3[:2]}/{K3}/attempts/1.json"
    attempt = json.loads(retake[".experiments.json"][name])
    attempt["execution"]["timing"]["wall_s"] = 3.75
    retake[".experiments.json"][name] = json.dumps(attempt)
    passed, lines = _run_real(tmp_path, retake)
    assert passed, lines
    assert "timing=1 " in lines[0]


def test_s6r09_an_archive_on_one_side_only_fails(tmp_path: Path) -> None:
    retake = _real(K3, K4)
    del retake[".experiments.json"]
    passed, lines = _run_real(tmp_path, retake)
    assert not passed
    assert "  experiments: no case.experiments.json on the re-take side" in lines


# S6R-10: the committed REAL stem.

REAL = ROOT / "benchmarks" / "m05" / "records" / "trust-region-study-real"
REAL_SUFFIXES = (".json", ".ledger.json", ".store.json", ".environment.json", ".experiments.json")


def _copy_real(stem: Path) -> None:
    stem.parent.mkdir(parents=True)
    for suffix in REAL_SUFFIXES:
        shutil.copyfile(REAL.with_suffix(suffix), stem.with_suffix(suffix))
    shutil.copytree(REAL.with_suffix(".coupling"), stem.with_suffix(".coupling"))


def test_s6r10_a_byte_copy_of_the_committed_real_stem_passes(tmp_path: Path) -> None:
    new = tmp_path / "new" / REAL.name
    _copy_real(new)
    passed, lines = RETAKE.digest_only(REAL, new)
    assert passed, lines
    assert "changed-digests=0 " in lines[0]
    assert "version=0 platform=0 other=0 environment=equal" in lines[0]


def test_s6r10_the_committed_real_stem_retaken_on_another_kernel_passes(
    tmp_path: Path, running_p1: None
) -> None:
    new = tmp_path / "new" / REAL.name
    _copy_real(new)
    couplings = sorted(new.with_suffix(".coupling").glob("*.json"))
    assert len(couplings) == 4
    old_fingerprint = {}
    for path in couplings:
        document = json.loads(path.read_text(encoding="utf-8"))
        reactor = document["frozen"]["reactor"]
        assert reactor["fingerprint"]["platform"] == P0
        old_fingerprint = copy.deepcopy(reactor["fingerprint"])
        reactor["fingerprint"]["platform"] = P1
        path.write_text(json.dumps(document), encoding="utf-8")
    old_digest = document_sha256(old_fingerprint)
    new_digest = document_sha256({**old_fingerprint, "platform": P1})
    keys = {e["experiment_key"] for e in json.loads(REAL.with_suffix(".store.json").read_bytes())}
    relabel = {old_digest: new_digest}
    relabel |= {k: hashlib.sha256((k + new_digest).encode()).hexdigest() for k in keys}

    def rewrite(text: str) -> str:
        # A store directory `<k[:2]>/<k>` (an attempt's log paths) follows its key, as a name does.
        for old, image in relabel.items():
            text = text.replace(f"{old[:2]}/{old}", f"{image[:2]}/{image}").replace(old, image)
        return text

    for path in [*couplings, *(new.with_suffix(s) for s in REAL_SUFFIXES[:3])]:
        path.write_text(rewrite(path.read_text(encoding="utf-8")), encoding="utf-8")
    archive = json.loads(REAL.with_suffix(".experiments.json").read_bytes())
    renamed = {}
    for name, text in archive.items():
        key = name.split("/")[1]
        image = relabel[key]
        renamed[f"{image[:2]}/{image}/{name.split('/', 2)[2]}"] = rewrite(text)
    stored = canonical_json(dict(sorted(renamed.items())))
    new.with_suffix(".experiments.json").write_bytes(stored)
    record = json.loads(new.with_suffix(".json").read_bytes())
    record["artifacts"]["experiment_store"] = hashlib.sha256(stored).hexdigest()
    new.with_suffix(".json").write_text(json.dumps(record), encoding="utf-8")

    passed, lines = RETAKE.digest_only(REAL, new, None, P0)
    assert passed, lines[:20]
    assert lines[0].startswith("RETAKE-DIGEST-ONLY PASS trust-region-study-real: ")
    # Each of the 48 cold attempts names its store directory twice, in the archive and in its
    # coupling record's iteration: 96 + 32 log paths.
    assert "path=128 version=0 platform=4 other=0 environment=equal" in lines[0]


# The class `path`: an attempt's log path names its experiment key's store directory.


def _logs(key: str) -> dict[str, Any]:
    return {
        "relpaths": {
            name: f"experiments/{key[:2]}/{key}/attempts/1/child.{name}"
            for name in ("stderr", "stdout")
        }
    }


def _with_logs(documents: dict[str, Any], keys: tuple[str, str]) -> dict[str, Any]:
    """Each archived attempt, and each coupling record's request, gains its log paths."""
    archive = documents[".experiments.json"]
    for key in keys:
        name = f"{key[:2]}/{key}/attempts/1.json"
        attempt = json.loads(archive[name])
        attempt["execution"]["logs"] = _logs(key)
        archive[name] = json.dumps(attempt)
    for name, key in zip(COUPLINGS, keys, strict=True):
        documents[f".coupling/{name}.json"]["attempts"] = [{"execution": {"logs": _logs(key)}}]
    return documents


def test_log_paths_relabelled_with_their_keys_pass_as_path(tmp_path: Path) -> None:
    committed = _with_logs(_real(K1, K2), (K1, K2))
    passed, lines = _run_real(tmp_path, _with_logs(_real(K4, K3), (K4, K3)), None, committed)
    assert passed, lines
    assert "path=8 version=0 platform=0 other=0" in lines[0]


@pytest.mark.parametrize(
    ("bend", "why"),
    [
        (lambda text: text.replace(f"{K4[:2]}/", f"{K1[:2]}/"), "the directory kept"),
        (lambda text: text.replace("child.", "kid."), "the text moved"),
        (lambda text: text.replace(K4, K5), "a key that is not the image"),
    ],
)
def test_a_log_path_that_is_not_its_relabelled_path_is_other(
    tmp_path: Path, bend: Callable[[str], str], why: str
) -> None:
    committed = _with_logs(_real(K1, K2), (K1, K2))
    retake = _with_logs(_real(K4, K3), (K4, K3))
    relpaths = retake[".coupling/S0.json"]["attempts"][0]["execution"]["logs"]["relpaths"]
    relpaths["stderr"] = bend(relpaths["stderr"])
    passed, lines = _run_real(tmp_path, retake, None, committed)
    assert not passed, why
    assert "path=7 " in lines[0] and "other=1" in lines[0], why
    assert any(
        "coupling S0.json.attempts[0].execution.logs.relpaths.stderr: " in line
        and "(not its relabelled path)" in line
        for line in lines
    )
