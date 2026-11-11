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

WO-7 (a) (ruling §11.3, S6R-27): an attempt's log digest (`.execution.logs.stdout_sha256`,
`.stderr_sha256`) is compared exactly and never enters the map, so a moved log is other, a uniform
move of every log included. WO-R1 (`docs/reviews/REL040-review.md` S-1): a value digest
(`.inner.state_sha256`, `.inner.constants_sha256`, `.requests[<n>].inputs_sha256`) is held the
same way, a one-to-one move of every inner state included.
"""

from __future__ import annotations

import copy
import hashlib
import importlib
import importlib.util
import json
import math
import platform
import re
import shutil
import sys
from collections.abc import Callable, Iterator
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
    # S6R-27 (4): the summary line printed before WO-7 (`d7258775`).
    assert lines[0] == (
        "RETAKE-DIGEST-ONLY PASS trust-region-study-real: changed-digests=0 digest=0 timing=0 "
        "path=0 version=0 platform=0 other=0 environment=equal"
    )


# A made-up platform, different from whatever kernel the committed REAL record was taken on.
P_RETAKE = "Linux-0.0.0-s6r10-retake-x86_64-with-glibc0.0"


def test_s6r10_the_committed_real_stem_retaken_on_another_kernel_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Q-S6d: the committed record's platform is read from the record, not pinned, so a J that
    # commits the re-take (on whatever kernel) keeps this test meaningful.
    monkeypatch.setattr(platform, "platform", lambda: P_RETAKE)
    new = tmp_path / "new" / REAL.name
    _copy_real(new)
    couplings = sorted(new.with_suffix(".coupling").glob("*.json"))
    assert len(couplings) == 4
    committed = {
        json.loads(path.read_text(encoding="utf-8"))["frozen"]["reactor"]["fingerprint"]["platform"]
        for path in couplings
    }
    assert len(committed) == 1
    (p_old,) = committed
    assert p_old != P_RETAKE
    old_fingerprint = {}
    for path in couplings:
        document = json.loads(path.read_text(encoding="utf-8"))
        reactor = document["frozen"]["reactor"]
        old_fingerprint = copy.deepcopy(reactor["fingerprint"])
        reactor["fingerprint"]["platform"] = P_RETAKE
        path.write_text(json.dumps(document), encoding="utf-8")
    old_digest = document_sha256(old_fingerprint)
    new_digest = document_sha256({**old_fingerprint, "platform": P_RETAKE})
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

    passed, lines = RETAKE.digest_only(REAL, new, None, p_old)
    assert passed, lines[:20]
    assert lines[0].startswith("RETAKE-DIGEST-ONLY PASS trust-region-study-real: ")
    # Each of the 48 cold attempts names its store directory twice, in the archive and in its
    # coupling record's iteration: 96 + 32 log paths.
    assert "path=128 version=0 platform=4 other=0 environment=equal" in lines[0]
    # S6R-27 (4): the summary line printed before WO-7 (`d7258775`).
    assert lines[0] == (
        "RETAKE-DIGEST-ONLY PASS trust-region-study-real: changed-digests=50 digest=431 "
        "timing=0 path=128 version=0 platform=4 other=0 environment=equal"
    )


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


# -- S6R-27 (WO-7 (a), ruling §11.3): a log digest is compared exactly, not relabelled ------------

#: The empty file's SHA-256, every committed REAL log's digest (ruling §11.0 G2).
EMPTY = hashlib.sha256(b"").hexdigest()


def _log_digests(documents: dict[str, Any], keys: tuple[str, str]) -> dict[str, Any]:
    """`_with_logs`, each log's digest the empty file's; the stems' only `EMPTY` leaves."""
    documents = _with_logs(documents, keys)
    archive = documents[".experiments.json"]
    for key in keys:
        name = f"{key[:2]}/{key}/attempts/1.json"
        attempt = json.loads(archive[name])
        attempt["execution"]["logs"] |= {"stderr_sha256": EMPTY, "stdout_sha256": EMPTY}
        archive[name] = json.dumps(attempt)
    for name in COUPLINGS:
        logs = documents[f".coupling/{name}.json"]["attempts"][0]["execution"]["logs"]
        logs |= {"stderr_sha256": EMPTY, "stdout_sha256": EMPTY}
    return documents


def test_s6r27_relabelled_stems_with_equal_log_digests_pass(tmp_path: Path) -> None:
    committed = _log_digests(_real(K1, K2), (K1, K2))
    passed, lines = _run_real(tmp_path, _log_digests(_real(K4, K3), (K4, K3)), None, committed)
    assert passed, lines
    assert "path=8 version=0 platform=0 other=0" in lines[0]


def test_s6r27_an_archived_attempts_stderr_digest_moving_fails_naming_it(tmp_path: Path) -> None:
    committed = _log_digests(_real(K1, K2), (K1, K2))
    retake = _log_digests(_real(K4, K3), (K4, K3))
    name = f"{K4[:2]}/{K4}/attempts/1.json"
    attempt = json.loads(retake[".experiments.json"][name])
    attempt["execution"]["logs"]["stderr_sha256"] = K5
    retake[".experiments.json"][name] = json.dumps(attempt)
    passed, lines = _run_real(tmp_path, retake, None, committed)
    assert not passed
    assert "other=1 " in lines[0]
    leaf = f"experiments {K1[:2]}/{K1}/attempts/1.json.execution.logs.stderr_sha256"
    assert f"  {leaf}: {EMPTY!r} vs {K5!r} (a log digest is compared exactly)" in lines


def test_s6r27_a_coupling_iterations_stderr_digest_moving_fails_naming_it(tmp_path: Path) -> None:
    committed = _log_digests(_real(K1, K2), (K1, K2))
    retake = _log_digests(_real(K4, K3), (K4, K3))
    retake[".coupling/S0.json"]["attempts"][0]["execution"]["logs"]["stderr_sha256"] = K5
    passed, lines = _run_real(tmp_path, retake, None, committed)
    assert not passed
    assert "other=1 " in lines[0]
    leaf = "coupling S0.json.attempts[0].execution.logs.stderr_sha256"
    assert f"  {leaf}: {EMPTY!r} vs {K5!r} (a log digest is compared exactly)" in lines


def test_s6r27_every_log_digest_moving_to_one_common_value_fails(tmp_path: Path) -> None:
    # A uniform move is a bijection EMPTY -> K5: as a digest it would pass (the tool at `0282e4d6`
    # does), so this case discriminates. 2 attempts and 2 coupling iterations, 2 logs each.
    committed = _log_digests(_real(K1, K2), (K1, K2))
    retake = _log_digests(_real(K4, K3), (K4, K3))
    archive = retake[".experiments.json"]
    for key in (K4, K3):
        name = f"{key[:2]}/{key}/attempts/1.json"
        attempt = json.loads(archive[name])
        attempt["execution"]["logs"] |= {"stderr_sha256": K5, "stdout_sha256": K5}
        archive[name] = json.dumps(attempt)
    for name in COUPLINGS:
        logs = retake[f".coupling/{name}.json"]["attempts"][0]["execution"]["logs"]
        logs |= {"stderr_sha256": K5, "stdout_sha256": K5}
    passed, lines = _run_real(tmp_path, retake, None, committed)
    assert not passed
    assert "other=8 " in lines[0]
    assert sum("(a log digest is compared exactly)" in line for line in lines) == 8


# -- WO-R1 (REL040 review S-1): a value digest is compared exactly, not relabelled ---------------


def _value(kind: str, index: int) -> str:
    return hashlib.sha256(f"{kind} {index}".encode()).hexdigest()


#: Two coupling iterations per coupling record, so four inner states across `COUPLINGS`.
ITERATIONS = 2


def _value_digests(documents: dict[str, Any], states: Callable[[int], str]) -> dict[str, Any]:
    """Each coupling record gains `ITERATIONS` iterations, iteration `i` of record `r` holding the
    inner state `states(r * ITERATIONS + i)` and one constants digest; each ledger entry gains a
    request with its own inputs digest."""
    for r, name in enumerate(COUPLINGS):
        documents[f".coupling/{name}.json"]["iterations"] = [
            {
                "inner": {
                    "constants_sha256": _value("constants", 0),
                    "state_sha256": states(r * ITERATIONS + i),
                }
            }
            for i in range(ITERATIONS)
        ]
    for index, entry in enumerate(documents[".ledger.json"]):
        entry["requests"] = [{"inputs_sha256": _value("inputs", index)}]
    return documents


def _states(index: int) -> str:
    return _value("state", index)


def test_wo_r1_relabelled_stems_with_equal_value_digests_pass(tmp_path: Path) -> None:
    committed = _value_digests(_real(K1, K2), _states)
    passed, lines = _run_real(tmp_path, _value_digests(_real(K4, K3), _states), None, committed)
    assert passed, lines
    assert lines[0].startswith("RETAKE-DIGEST-ONLY PASS case: changed-digests=2 ")


def _move_state(documents: dict[str, Any]) -> tuple[str, str]:
    inner = documents[".coupling/S0.json"]["iterations"][1]["inner"]
    inner["state_sha256"] = K5
    return "coupling S0.json.iterations[1].inner.state_sha256", _states(1)


def _move_constants(documents: dict[str, Any]) -> tuple[str, str]:
    inner = documents[".coupling/cand-C1-P1.json"]["iterations"][0]["inner"]
    inner["constants_sha256"] = K5
    return "coupling cand-C1-P1.json.iterations[0].inner.constants_sha256", _value("constants", 0)


def _move_inputs(documents: dict[str, Any]) -> tuple[str, str]:
    documents[".ledger.json"][1]["requests"][0]["inputs_sha256"] = K5
    return "ledger[1].requests[0].inputs_sha256", _value("inputs", 1)


@pytest.mark.parametrize("move", [_move_state, _move_constants, _move_inputs])
def test_wo_r1_one_value_digest_moving_fails_naming_it(
    tmp_path: Path, move: Callable[[dict[str, Any]], tuple[str, str]]
) -> None:
    committed = _value_digests(_real(K1, K2), _states)
    retake = _value_digests(_real(K4, K3), _states)
    leaf, old = move(retake)
    passed, lines = _run_real(tmp_path, retake, None, committed)
    assert not passed
    assert "other=1 " in lines[0]
    assert f"  {leaf}: {old!r} vs {K5!r} (a value digest is compared exactly)" in lines


def test_wo_r1_every_inner_state_moving_one_to_one_fails(tmp_path: Path) -> None:
    # The review's demonstration (S-1): every inner state moves to a new, distinct value. As digests
    # the moves are a bijection and would pass (the tool at `5d0c4121` does), so this discriminates.
    committed = _value_digests(_real(K1, K2), _states)
    retake = _value_digests(_real(K4, K3), lambda index: _value("moved state", index))
    passed, lines = _run_real(tmp_path, retake, None, committed)
    assert not passed
    n = len(COUPLINGS) * ITERATIONS
    assert f"other={n} " in lines[0]
    assert sum("inner.state_sha256" in line and "compared exactly" in line for line in lines) == n


# -- REL040 review N-3: `--old-version` is refused beside a pinned platform ----------------------


def test_n3_old_version_with_a_platform_pinned_pair_fails(tmp_path: Path, running_p1: None) -> None:
    # A-11 requires `environment=equal`; with `--old-version` the tool could print
    # `PASS ... environment=distributions` for REAL. Passes at `5d0c4121`.
    old_stem, new_stem = tmp_path / "old" / "case", tmp_path / "new" / "case"
    _write(old_stem, _real(K1, K2))
    _write(new_stem, _real(K4, K3, host=P1))
    passed, lines = RETAKE.digest_only(old_stem, new_stem, V0, P0)
    assert not passed
    assert f"platform=2 other={len(COUPLINGS)} " in lines[0]
    for name in COUPLINGS:
        assert f"  coupling {name}.json: --old-version is refused beside the platform" in lines


# -- R-1020 (`docs/reviews/HOSTMOVE-ruling.md` §11, WO-H1, HM-01 to HM-18): the class `host` -------

HOSTMOVE = ROOT / "docs" / "derivations" / "scripts" / "hostmove_host_leaves.py"
#: The committed side's host, set synthetically, and the re-take's: made-up literals (§11.0).
OLD_HOST = {"machine": "host-hm-committed", "cpu": "cpu-hm-committed", "cpu_count": 96}
NEW_HOST = {"machine": "host-hm02", "cpu": "cpu-hm02", "cpu_count": 3}
OLD_FLAGS, NEW_FLAGS = "d" * 64, "e" * 64
OLD_ROOT, NEW_ROOT = "/home/hm-committed/.cache/openflowsheet/external", Path("/home/hm02/external")
ENV_DIR = "pymrm-0000000-hm0000000000"
OLD_PLATFORM, NEW_PLATFORM = "Linux-0.0.0-hm10-committed", "Linux-0.0.0-hm10"
#: An environment sidecar in the writer's key order, on the committed host.
SIDECAR = {
    "omp_num_threads": "1",
    "python": "3.13.5 (hm)",
    "distributions": 17,
    "distributions_sha256": K5,
    "conda_builds": 41,
    "conda_builds_sha256": "9" * 64,
    **OLD_HOST,
}
MOVED = {**SIDECAR, **NEW_HOST}


def _hostmove() -> ModuleType:
    spec = importlib.util.spec_from_file_location("hostmove_host_leaves", HOSTMOVE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _literals_are_made_up() -> None:
    """§11.0: no literal is a committed host value or one the running host measures."""
    real = json.loads(REAL.with_suffix(".environment.json").read_bytes())
    fingerprint = json.loads(next(REAL.with_suffix(".coupling").glob("*.json")).read_bytes())
    fingerprint = fingerprint["frozen"]["reactor"]["fingerprint"]
    known = {str(value) for value in RETAKE._running_host().values()}
    known |= {str(real[key]) for key in RETAKE.SIDECAR_HOST}
    known |= {fingerprint["cpu_model"], fingerprint["cpu_flags_sha256"], fingerprint["platform"]}
    known |= {fingerprint["env_allowlist"]["NUMBA_CACHE_DIR"], platform.platform()}
    literals = [*OLD_HOST.values(), *NEW_HOST.values(), OLD_FLAGS, NEW_FLAGS, OLD_ROOT]
    literals += [NEW_ROOT, OLD_PLATFORM, NEW_PLATFORM]
    assert not {str(literal) for literal in literals} & known


_literals_are_made_up()


def _running(**override: Any) -> dict[str, Any]:
    """`_running_host()` on the re-take's host."""
    values = {**NEW_HOST, "cpu_model": NEW_HOST["cpu"], "cpu_flags_sha256": NEW_FLAGS}
    return {**values, "external_root": NEW_ROOT, **override}


@pytest.fixture
def running_hm(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """The running host is the re-take's; call the fixture's value to override one of its
    values."""

    def patch(**override: Any) -> None:
        monkeypatch.setattr(RETAKE, "_running_host", lambda: _running(**override))

    patch()
    monkeypatch.setattr(platform, "platform", lambda: NEW_PLATFORM)
    return patch


def _writer(document: dict[str, Any]) -> str:
    return json.dumps(document, indent=1) + "\n"


def _run_host(
    tmp_path: Path,
    retake_sidecar: dict[str, Any],
    *,
    old_host: str | None = OLD_HOST["machine"],
    committed_sidecar: dict[str, Any] = SIDECAR,
    committed: dict[str, Any] | None = None,
    retake: dict[str, Any] | None = None,
    old_version: str | None = None,
    old_platform: str | None = None,
    text: Callable[[dict[str, Any]], str] = _writer,
) -> tuple[bool, list[str]]:
    """The in-process pair of `_run` (or `committed` and `retake`), with the writer's sidecars."""
    old_stem, new_stem = tmp_path / "old" / "case", tmp_path / "new" / "case"
    _write(old_stem, _documents(K1, K2) if committed is None else committed)
    _write(new_stem, _documents(K3, K4) if retake is None else retake)
    Path(f"{old_stem}.environment.json").write_text(_writer(committed_sidecar), encoding="utf-8")
    Path(f"{new_stem}.environment.json").write_text(text(retake_sidecar), encoding="utf-8")
    return RETAKE.digest_only(old_stem, new_stem, old_version, old_platform, old_host)


def test_hm01_the_writers_sidecar_keys_and_host_values() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    runs = importlib.import_module("m05_wo8_runs")
    written = runs.environment_fingerprint()
    assert tuple(written) == _hostmove().SIDECAR_KEYS
    host = sys.modules["m05_replay"].host_identity()
    assert list(host) == list(RETAKE.SIDECAR_HOST)
    assert list(written.items())[-3:] == list(host.items())


def test_hm02_the_three_host_keys_moved_to_the_running_host_pass(
    tmp_path: Path, running_hm: Callable[..., None]
) -> None:
    passed, lines = _run_host(tmp_path / "moved", MOVED)
    assert passed, lines
    assert lines[0].endswith(" other=0 environment=host host=3")
    # The same pair without the move: every other count is equal.
    passed, still = _run_host(tmp_path / "still", SIDECAR)
    assert passed, still
    assert still[0].endswith(" other=0 environment=equal host=0")
    assert lines[0].rsplit(" environment=", 1)[0] == still[0].rsplit(" environment=", 1)[0]


def test_hm03_without_old_host_the_move_fails_as_before(
    tmp_path: Path, running_hm: Callable[..., None]
) -> None:
    passed, lines = _run_host(tmp_path, MOVED, old_host=None)
    assert not passed
    # The lines the tool printed at `c57c2ca0` for this pair.
    assert lines == [
        "RETAKE-DIGEST-ONLY FAIL case: changed-digests=2 digest=7 timing=0 path=0 version=0 "
        "platform=0 other=0 environment=differs",
        "  environment: differs outside distributions_sha256 (['cpu', 'cpu_count', 'machine'])",
    ]


@pytest.mark.parametrize("retake_sidecar", [MOVED, SIDECAR], ids=["moved", "byte-equal"])
def test_hm04_an_old_host_other_than_the_committed_machine_fails(
    tmp_path: Path, running_hm: Callable[..., None], retake_sidecar: dict[str, Any]
) -> None:
    passed, lines = _run_host(tmp_path, retake_sidecar, old_host="host-hm04")
    assert not passed
    assert (
        "  environment: the committed machine 'host-hm-committed' is not --old-host 'host-hm04'"
        in lines
    )


@pytest.mark.parametrize(
    ("key", "value"), [("machine", "host-hm05"), ("cpu", "cpu-hm05"), ("cpu_count", 5)]
)
def test_hm05_a_retake_value_other_than_the_running_hosts_fails(
    tmp_path: Path, running_hm: Callable[..., None], key: str, value: Any
) -> None:
    running_hm(**{key: value})
    passed, lines = _run_host(tmp_path, MOVED)
    assert not passed
    assert f"  environment: re-take {key} {NEW_HOST[key]!r} is not the running {value!r}" in lines
    assert " host=0" in lines[0]


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("omp_num_threads", "2"),
        ("python", "3.13.6 (hm06)"),
        ("distributions", 18),
        ("conda_builds", 42),
        ("conda_builds_sha256", "8" * 64),
    ],
)
def test_hm06_one_more_differing_key_fails_naming_it(
    tmp_path: Path, running_hm: Callable[..., None], key: str, value: Any
) -> None:
    passed, lines = _run_host(tmp_path, {**MOVED, key: value})
    assert not passed
    assert "environment=differs host=0" in lines[0]
    assert (
        f"  environment: differs outside distributions_sha256 and the host keys (['{key}'])"
        in lines
    )


@pytest.mark.parametrize("reproduced", [True, False])
def test_hm07_host_keys_and_distributions_sha256(
    tmp_path: Path,
    running_hm: Callable[..., None],
    running_v1: None,
    monkeypatch: pytest.MonkeyPatch,
    reproduced: bool,
) -> None:
    recomputed = K5 if reproduced else "7" * 64
    monkeypatch.setattr(RETAKE, "_distributions_sha256", lambda version: recomputed)
    passed, lines = _run_host(
        tmp_path,
        {**MOVED, "distributions_sha256": "6" * 64},
        retake=_documents(K3, K4, version=V1),
        old_version=V0,
    )
    assert "environment=distributions+host host=3" in lines[0]
    assert passed is reproduced, lines
    if not reproduced:
        assert f"  environment: openflowsheet=={V0} gives {recomputed}, not the committed {K5}" in (
            lines
        )


def _swapped(document: dict[str, Any]) -> str:
    keys = list(document)
    keys[-3], keys[-2] = keys[-2], keys[-3]
    return _writer({key: document[key] for key in keys})


@pytest.mark.parametrize(
    "text", [lambda d: json.dumps(d, indent=2) + "\n", _swapped], ids=["indent-2", "swapped"]
)
def test_hm08_retake_bytes_that_are_not_the_writers_fail(
    tmp_path: Path, running_hm: Callable[..., None], text: Callable[[dict[str, Any]], str]
) -> None:
    passed, lines = _run_host(tmp_path, MOVED, text=text)
    assert not passed
    assert " host=0" in lines[0]


def test_hm09_byte_equal_sidecars_with_the_committed_machine_pass(
    tmp_path: Path, running_hm: Callable[..., None]
) -> None:
    passed, lines = _run_host(tmp_path, SIDECAR)
    assert passed, lines
    assert lines[0].endswith(" other=0 environment=equal host=0")


# HM-10 to HM-17: a REAL-like pair on S6R-01's synthetic reactor, its host leaves moving.

#: R-1020's host-identity paths, restated here so that the count below is the test's own.
HOST_PATH = re.compile(
    r"\.frozen\.reactor\.fingerprint\.(cpu_model|cpu_flags_sha256|env_allowlist\.NUMBA_CACHE_DIR)"
    r"|.*\.execution\.fingerprint\.cpu_model"
)


def _host_real(
    first: str,
    second: str,
    *,
    moved: bool,
    change: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """`_real` with REAL's host leaves: the reactor fingerprint's CPU model, CPU flags and
    environment directory, and a CPU model in each attempt's cheap fingerprint, in a coupling
    iteration and in the archive; on the re-take's host if `moved`, else on the committed one.
    `change` edits the fingerprint before it is bound."""
    host, flags, root, on = (
        (NEW_HOST, NEW_FLAGS, str(NEW_ROOT), NEW_PLATFORM)
        if moved
        else (OLD_HOST, OLD_FLAGS, OLD_ROOT, OLD_PLATFORM)
    )
    fingerprint = _reactor(on)["reactor"]["fingerprint"]
    fingerprint |= {
        "cpu_flags_sha256": flags,
        "cpu_model": host["cpu"],
        "env_allowlist": {"NUMBA_CACHE_DIR": f"{root}/{ENV_DIR}/numba-cache", "PATH": "/usr/bin"},
        "packages": {"numpy": "2.2.4", "pymrm": "2.5.0"},
        "thread_env": {"OMP_NUM_THREADS": "1"},
    }
    if change is not None:
        change(fingerprint)
    digest = document_sha256(fingerprint)
    documents = _real(first, second, on)
    for name, key in zip(COUPLINGS, (first, second), strict=True):
        coupling = documents[f".coupling/{name}.json"]
        coupling["frozen"]["reactor"] = {
            "fingerprint": copy.deepcopy(fingerprint),
            "fingerprint_sha256": digest,
        }
        coupling["request"]["environment_fingerprint_sha256"] = digest
        execution = {"fingerprint": {"cpu_model": host["cpu"]}}
        attempt = {"attempt": 1, "execution": execution, "experiment_key": key}
        coupling["iterations"] = [{"units": {"reactor": {"attempts": [attempt]}}}]
    archive = _archive((first, second), digest)
    for name in [name for name in archive if "/attempts/" in name]:
        attempt = json.loads(archive[name])
        attempt["execution"]["fingerprint"] = {"cpu_model": host["cpu"]}
        archive[name] = json.dumps(attempt)
    documents[".experiments.json"] = archive
    return documents


def _host_leaf_count(documents: dict[str, Any]) -> int:
    """The test's own count of the re-take's host leaves: the paths of `HOST_PATH` in the coupling
    records and the archived attempts, and the sidecar's three keys."""

    def paths(node: Any, path: str) -> Iterator[str]:
        if isinstance(node, dict):
            for key, value in node.items():
                yield from paths(value, f"{path}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                yield from paths(value, f"{path}[{index}]")
        else:
            yield path

    found = 0
    for suffix, document in documents.items():
        if suffix.startswith(".coupling/"):
            found += sum(1 for path in paths(document, "") if HOST_PATH.fullmatch(path))
    for text in documents[".experiments.json"].values():
        found += sum(1 for path in paths(json.loads(text), "") if HOST_PATH.fullmatch(path))
    return found + len(NEW_HOST)


def _run_host_real(
    tmp_path: Path,
    retake: dict[str, Any],
    *,
    committed: dict[str, Any] | None = None,
    old_host: str | None = OLD_HOST["machine"],
) -> tuple[bool, list[str]]:
    committed = _host_real(K1, K2, moved=False) if committed is None else committed
    return _run_host(
        tmp_path,
        MOVED,
        committed=committed,
        retake=retake,
        old_host=old_host,
        old_platform=OLD_PLATFORM,
    )


def test_hm10_a_real_like_pair_moved_to_the_running_host_passes(
    tmp_path: Path, running_hm: Callable[..., None]
) -> None:
    retake = _host_real(K3, K4, moved=True)
    passed, lines = _run_host_real(tmp_path, retake)
    assert passed, lines
    # Four leaves per coupling record (three in the fingerprint, one attempt), one per archived
    # attempt, and the sidecar's three.
    count = _host_leaf_count(retake)
    assert count == 4 * len(COUPLINGS) + 2 + 3
    assert lines[0].endswith(f" platform={len(COUPLINGS)} other=0 environment=host host={count}"), (
        lines[0]
    )


def test_hm11_without_old_host_the_real_like_pair_fails_naming_the_leaves(
    tmp_path: Path, running_hm: Callable[..., None]
) -> None:
    passed, lines = _run_host_real(tmp_path, _host_real(K3, K4, moved=True), old_host=None)
    assert not passed
    assert "environment=differs" in lines[0] and " host=" not in lines[0]
    assert int(lines[0].split(" other=")[1].split()[0]) > 0
    for leaf in ("cpu_model", "cpu_flags_sha256", "env_allowlist.NUMBA_CACHE_DIR"):
        assert any(f".frozen.reactor.fingerprint.{leaf}: " in line for line in lines), leaf


def test_hm12_another_environment_directory_fails(
    tmp_path: Path, running_hm: Callable[..., None]
) -> None:
    def other_lock(fingerprint: dict[str, Any]) -> None:
        directory = f"{NEW_ROOT}/pymrm-0000000-hm1200000000/numba-cache"
        fingerprint["env_allowlist"]["NUMBA_CACHE_DIR"] = directory

    passed, lines = _run_host_real(tmp_path, _host_real(K3, K4, moved=True, change=other_lock))
    assert not passed
    assert any("NUMBA_CACHE_DIR" in x and "not the same environment directory" in x for x in lines)


def _one_archived_attempt(documents: dict[str, Any], key: str, cpu: str) -> None:
    name = f"{key[:2]}/{key}/attempts/1.json"
    attempt = json.loads(documents[".experiments.json"][name])
    attempt["execution"]["fingerprint"]["cpu_model"] = cpu
    documents[".experiments.json"][name] = json.dumps(attempt)


def test_hm13_an_archived_attempt_on_another_cpu_fails(
    tmp_path: Path, running_hm: Callable[..., None]
) -> None:
    retake = _host_real(K3, K4, moved=True)
    _one_archived_attempt(retake, K3, "cpu-hm13")
    passed, lines = _run_host_real(tmp_path / "retake", retake)
    assert not passed
    attempt = f"  experiments {K1[:2]}/{K1}/attempts/1.json.execution.fingerprint.cpu_model: "
    assert f"{attempt}re-take 'cpu-hm13' is not the running 'cpu-hm02'" in lines

    committed = _host_real(K1, K2, moved=False)
    _one_archived_attempt(committed, K2, "cpu-hm13")
    passed, lines = _run_host_real(tmp_path / "committed", retake, committed=committed)
    assert not passed
    attempt = f"  experiments {K2[:2]}/{K2}/attempts/1.json.execution.fingerprint.cpu_model: "
    assert f"{attempt}committed 'cpu-hm13' is not the committed reactor cpu_model" in lines


def _set(path: str, value: Any) -> Callable[[dict[str, Any]], None]:
    def change(fingerprint: dict[str, Any]) -> None:
        *parents, leaf = path.split(".")
        node = fingerprint
        for parent in parents:
            node = node[parent]
        node[leaf] = value

    return change


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("lock_sha256", "7" * 64),
        ("python", "3.13.6"),
        ("packages.numpy", "2.2.5"),
        ("thread_env.OMP_NUM_THREADS", "2"),
    ],
)
def test_hm14_another_fingerprint_leaf_moving_with_the_host_is_other(
    tmp_path: Path, running_hm: Callable[..., None], path: str, value: Any
) -> None:
    retake = _host_real(K3, K4, moved=True, change=_set(path, value))
    passed, lines = _run_host_real(tmp_path, retake)
    assert not passed
    assert f" other={len(COUPLINGS)} " in lines[0]
    assert all(
        any(f"coupling {name}.json.frozen.reactor.fingerprint.{path}: " in x for x in lines)
        for name in COUPLINGS
    )


def test_hm15_cpu_flags_moved_with_the_fingerprint_digest_kept_fails(
    tmp_path: Path, running_hm: Callable[..., None]
) -> None:
    retake = _host_real(K3, K4, moved=True, change=_set("cpu_flags_sha256", OLD_FLAGS))
    for name in COUPLINGS:
        retake[f".coupling/{name}.json"]["frozen"]["reactor"]["fingerprint"]["cpu_flags_sha256"] = (
            NEW_FLAGS
        )
    passed, lines = _run_host_real(tmp_path, retake)
    assert not passed
    assert any(
        "frozen.reactor.fingerprint_sha256" in x and "is not document_sha256" in x for x in lines
    )


def test_hm16_one_archived_result_moved_by_one_ulp_fails_naming_it(
    tmp_path: Path, running_hm: Callable[..., None]
) -> None:
    retake = _host_real(K3, K4, moved=True)
    name = f"{K3[:2]}/{K3}/result.json"
    retake[".experiments.json"][name] = json.dumps({"value": math.nextafter(0.25, math.inf)})
    passed, lines = _run_host_real(tmp_path, retake)
    assert not passed
    assert "other=1 " in lines[0]
    assert [x for x in lines if x.startswith(f"  experiments {K1[:2]}/{K1}/result.json.value: ")]


def test_hm17_the_cpu_model_outside_the_registered_leaves_is_other(
    tmp_path: Path, running_hm: Callable[..., None]
) -> None:
    committed, retake = _host_real(K1, K2, moved=False), _host_real(K3, K4, moved=True)
    committed[".json"]["runs"][0]["cpu"] = OLD_HOST["cpu"]
    retake[".json"]["runs"][0]["cpu"] = NEW_HOST["cpu"]
    passed, lines = _run_host_real(tmp_path, retake, committed=committed)
    assert not passed
    assert "other=1 " in lines[0]
    assert "  record.runs[0].cpu: 'cpu-hm-committed' vs 'cpu-hm02'" in lines
