"""X02 WO-4: the external start's plumbing (ADR 0070 D4–D10; design note
`docs/design/X02-warm-starts.md` §5.5, §5.7, §5.8; gate G4) on the synthetic warm child
(`tests/support/synthetic_warm_child.py`) and the stand-in loop pinned to its variant.

The child's model is a damped fixed-point iteration on a 16-vector from zeros (cold) or from the
start's vector (warm), so a warm and a cold answer at one inlet differ only below 1e-11, and its
outlet is checked here against the stand-in's closed form computed independently.

- **G4 (a)** in a coupled run k = 0 carries no `start`, and every later request carries the
  previous `ok` result's `profile_sha256`; the k = 0 key equals a cold request's built here.
- **(b)** warm and cold outlets each match the analytic value within 1e-11.
- **(c)** a cold and a warm request at one inlet have different keys: each is a miss, then a hit.
- **(d)** the forced refusal (`OFS_TEST_WARM_REFUSE`) answers through the cold chain: `used`
  false, `fallback_from` set, the outlet bitwise the cold one's.
- **(e)** replay gives `MATCH`; a bundle whose second request's start was edited (its key
  recomputed) diverges (`MISMATCH`).
- **(f)** the certificate's `external_model` detail carries `start` iff the final request did.
- **The job source.** A declared job's last profiles are the k = 0 starts: the `external`
  sub-record, its R0, its statuses (`absent`/`rejected` cases), and its replay.
- **The store, the program, the protocol.** The profile store is content-addressed and
  write-once; `pinned_program` selects by `runner_sha256` (v1–v3 → `child.py`); a
  start-capable outlet without its profile is a `protocol_error`.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT
from m02_variant_support import register_variants

from openflowsheet.adapters import variants
from openflowsheet.adapters.experiments.backends import (
    InProcessBackend,
    OutOfProcessBackend,
    pinned_program,
    start_capable,
)
from openflowsheet.adapters.experiments.request import build_request, experiment_key
from openflowsheet.adapters.experiments.runner import ExperimentRunner
from openflowsheet.adapters.experiments.store import ExperimentStore, ListArtifactSink
from openflowsheet.adapters.external.launcher import ChildProgram
from openflowsheet.application.coupled_run import (
    CoupledStart,
    LiveExperiments,
    external_starts,
    job_coupling_start,
)
from openflowsheet.application.policies import T06_REVISION_V2
from openflowsheet.application.revision_run import (
    Route,
    reproduce_bundle,
    run_revision_session,
    select_route,
)
from openflowsheet.compiled import EvaluationContext
from openflowsheet.run.bundle import read_artifact, read_manifest, write_bundle
from openflowsheet.run.identity import r0_projection
from openflowsheet.thermo import StreamState
from openflowsheet.thermo.pr_c1 import COMPONENTS, PrC1Provider
from openflowsheet.verify.certificate import CheckPolicy

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from m02_schema_fixtures import (  # noqa: E402
    N_TUBES,
    SYNTHETIC_CHILD,
    nominal_inlet,
    synthetic_variant,
)

WARM_CHILD = REPO_ROOT / "tests" / "support" / "synthetic_warm_child.py"
LOOP_PATH = REPO_ROOT / "benchmarks" / "m02" / "c1-loop-standin.json"
REAL = variants.registered_variant("pymrm-6089593-g2-nz800-s123-v2")
NU = (-3, -1, 2, 0, 0)
START = {"kind": "profile", "format": "tube-profile-v1", "file": "start.json"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def warm_variant(name: str, child: Path = WARM_CHILD) -> variants.Variant:
    """A test-only start-capable out-of-process variant (never registered outside the test)."""
    document = copy.deepcopy(synthetic_variant(name, ["ok"]).document)
    document["synthetic"] = False
    document["accuracy"] = REAL.document["accuracy"]
    document["evaluation"]["runner_sha256"] = _sha256(child)
    document["evaluation"]["profile"] = {"id": "synthetic-warm", "start": START}
    return variants.variant_from_document(document)


def backend_for(root: Path, *, refuse: bool = False, child: Path = WARM_CHILD) -> Any:
    root.mkdir(parents=True, exist_ok=True)
    program = ChildProgram(Path(sys.executable), child, root)

    def build(variant: variants.Variant) -> Any:
        if variant.kind == "in_process":
            return InProcessBackend(variant)
        return OutOfProcessBackend(
            variant,
            program,
            expected={"runner_sha256": _sha256(child)},
            test_environment={"OFS_TEST_WARM_REFUSE": "1"} if refuse else None,
        )

    return build


def runner_in(records: Path, environment: Path, **options: Any) -> ExperimentRunner:
    return ExperimentRunner(
        ExperimentStore(records, ListArtifactSink()),
        PrC1Provider(),
        EvaluationContext(model_version="x02-wo4", constants_sha256="0" * 64),
        backend_for=backend_for(environment, **options),
    )


def pinned(variant: variants.Variant) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(LOOP_PATH.read_text(encoding="utf-8"))
    for item in document["instances"]:
        if item["id"] == "reactor":
            item["model"] = {
                "id": variant.model_id,
                "version": variant.variant_id,
                "artifact_ref": variant.sha256,
            }
    return document


def solve(
    document: Mapping[str, Any],
    directory: Path,
    runner: ExperimentRunner,
    coupled_start: CoupledStart | None = None,
) -> dict[str, Any]:
    route = select_route(document)
    assert isinstance(route, Route) and route.solve_path == "revision_coupled"
    manifest = run_revision_session(
        route,
        document,
        directory,
        run_id="run-x02-wo4",
        policy=T06_REVISION_V2,
        check_policy=CheckPolicy(),
        policy_requested="default",
        experiments=LiveExperiments(runner),
        coupled_start=coupled_start,
    )
    return {name: read_artifact(directory, name) for name in manifest.artifacts}


def analytic(tube: Mapping[str, Any]) -> tuple[list[float], float]:
    """The stand-in's closed form per tube (M01 spec §8.13), computed here, not by the child."""
    feed = [tube["flow"] * y for y in tube["composition"]]
    xi = 0.25 * feed[1]
    return [feed[i] + NU[i] * xi for i in range(5)], float(tube["temperature"])


@dataclass(frozen=True)
class Chained:
    variant: variants.Variant
    records: Path
    environment: Path
    bundle: Path
    artifacts: dict[str, Any]
    root: Path


@pytest.fixture(scope="module")
def chained(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Chained]:
    root = tmp_path_factory.mktemp("x02wo4")
    with pytest.MonkeyPatch.context() as monkeypatch:
        register = register_variants(monkeypatch)
        variant = register(warm_variant("x02-g4"))
        runner = runner_in(root / "records", root / "env")
        artifacts = solve(pinned(variant), root / "bundle", runner)
        yield Chained(variant, root / "records", root / "env", root / "bundle", artifacts, root)


def _entries(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [item["units"]["reactor"] for item in record["iterations"]]


# -- G4 (a), (b): chaining inside a coupled run ----------------------------------------------------


def test_g4a_k0_is_cold_and_each_later_request_starts_from_the_previous_profile(
    chained: Chained,
) -> None:
    record = chained.artifacts["external-coupling.json"]
    assert record["outcome"] == "CONVERGED"
    entries = _entries(record)
    assert len(entries) >= 2
    assert "start" not in entries[0]["request"]
    for previous, entry in zip(entries, entries[1:], strict=False):
        assert entry["request"]["start"] == {
            "kind": "profile",
            "profile_sha256": previous["result"]["profile_sha256"],
        }
    for entry in entries:
        assert entry["request"]["experiment_key"] == experiment_key(entry["request"])
    # The k = 0 key is a cold request's, built independently at the recorded inlet.
    first = entries[0]
    frozen = record["frozen"]["reactor"]["fingerprint_sha256"]
    inputs = first["request"]["inputs"]
    cold = build_request(
        chained.variant,
        PrC1Provider().describe(),
        N_TUBES,
        COMPONENTS,
        StreamState(n=tuple(inputs["n"]), temperature=inputs["T"], pressure=inputs["P"]),
        frozen,
    )
    assert cold["experiment_key"] == first["request"]["experiment_key"]
    assert chained.artifacts["solution-certificate.json"]["verification_status"] == "VERIFIED"


def test_g4b_warm_and_cold_outlets_match_the_analytic_value(chained: Chained) -> None:
    for entry in _entries(chained.artifacts["external-coupling.json"]):
        execution = entry["attempts"][-1]["execution"]
        flows, temperature = analytic(execution["tube_inlet"])
        outlet = execution["tube_outlet"]
        assert max(abs(a - b) for a, b in zip(outlet["flows"], flows, strict=True)) <= 1e-11
        assert abs(outlet["temperature"] - temperature) <= 1e-11
        start = execution["diagnostics"]["start"]
        assert (start is None) == ("start" not in entry["request"])
        if start is not None:
            assert (start["used"], start["fallback_from"]) == (True, None)


def test_g4_every_result_profile_is_in_the_store(chained: Chained) -> None:
    store = ExperimentStore(chained.records)
    for entry in _entries(chained.artifacts["external-coupling.json"]):
        sha = entry["result"]["profile_sha256"]
        data = store.profile(sha)
        assert data is not None and hashlib.sha256(data).hexdigest() == sha
        document = json.loads(data)
        assert (document["format"], document["shape"]) == ("tube-profile-v1", [16, 1, 1])


# -- G4 (c), (d): keys and the fallback -----------------------------------------------------------


def test_g4c_a_warm_and_a_cold_request_at_one_inlet_have_different_keys(
    chained: Chained, tmp_path: Path
) -> None:
    runner = runner_in(tmp_path / "records", tmp_path / "env")
    inlet = nominal_inlet()
    cold = runner.run(chained.variant, inlet, COMPONENTS, N_TUBES)
    assert cold.cache_hit is False and cold.result is not None
    profile = cold.result["profile_sha256"]
    warm = runner.run(chained.variant, inlet, COMPONENTS, N_TUBES, start=profile)
    assert warm.cache_hit is False and warm.key != cold.key
    assert warm.request["start"] == {"kind": "profile", "profile_sha256": profile}
    assert runner.run(chained.variant, inlet, COMPONENTS, N_TUBES).cache_hit is True
    again = runner.run(chained.variant, inlet, COMPONENTS, N_TUBES, start=profile)
    assert again.cache_hit is True and again.key == warm.key


def test_g4d_a_refused_warm_chain_answers_through_the_cold_chain(
    chained: Chained, tmp_path: Path
) -> None:
    normal = runner_in(tmp_path / "records", tmp_path / "env")
    inlet = nominal_inlet()
    source = normal.run(chained.variant, inlet, COMPONENTS, N_TUBES)
    assert source.result is not None
    profile = source.result["profile_sha256"]
    shifted = StreamState(n=inlet.n, temperature=inlet.temperature + 5.0, pressure=inlet.pressure)
    cold = normal.run(chained.variant, shifted, COMPONENTS, N_TUBES)
    refusing = runner_in(tmp_path / "records", tmp_path / "env-refuse", refuse=True)
    fallback = refusing.run(chained.variant, shifted, COMPONENTS, N_TUBES, start=profile)
    assert fallback.cache_hit is False
    execution = fallback.attempts[-1]["execution"]
    start = execution["diagnostics"]["start"]
    assert (start["used"], start["fallback_from"]) == (False, "S2")
    assert execution["tube_outlet"] == cold.attempts[-1]["execution"]["tube_outlet"]
    # The control: without the switch the same warm request is answered warm.
    warm = runner_in(tmp_path / "records-2", tmp_path / "env")
    warm.records.write_profile(ExperimentStore(tmp_path / "records").profile(profile) or b"")
    used = warm.run(chained.variant, shifted, COMPONENTS, N_TUBES, start=profile)
    assert used.attempts[-1]["execution"]["diagnostics"]["start"]["used"] is True


# -- G4 (e): replay -------------------------------------------------------------------------------


def test_g4e_replay_of_the_chained_run_matches(chained: Chained, tmp_path: Path) -> None:
    reproduction = reproduce_bundle(
        chained.bundle, rerun=True, rerun_directory=tmp_path / "rerun", run_id="run-rerun"
    )
    assert reproduction.report.verdict == "MATCH", reproduction.report.differences


def test_g4e_an_edited_start_diverges(chained: Chained, tmp_path: Path) -> None:
    manifest, _ = read_manifest(chained.bundle)
    artifacts = {name: read_artifact(chained.bundle, name) for name in manifest.artifacts}
    request = artifacts["external-coupling.json"]["iterations"][1]["units"]["reactor"]["request"]
    request["start"]["profile_sha256"] = "0" * 64
    request["experiment_key"] = experiment_key(request)
    write_bundle(tmp_path / "forged", manifest, artifacts)
    reproduction = reproduce_bundle(
        tmp_path / "forged", rerun=True, rerun_directory=tmp_path / "rerun", run_id="run-forged"
    )
    report = reproduction.report
    assert report.verdict == "MISMATCH", (report.verdict, report.reasons)
    assert any("start" in entry for entry in (*report.reasons, *report.differences)), report


# -- G4 (f): the certificate's disclosure (D8) -----------------------------------------------------


def test_g4f_the_certificate_discloses_the_final_start(chained: Chained) -> None:
    certificate = chained.artifacts["solution-certificate.json"]
    (external,) = [item for item in certificate["limitations"] if item["kind"] == "external_model"]
    final = _entries(chained.artifacts["external-coupling.json"])[-1]
    assert external["start"] == {"profile_sha256": final["request"]["start"]["profile_sha256"]}
    assert external["path_independence_rel"] == REAL.accuracy["measured_path_independence_rel"]


def test_g4f_a_cold_certificate_carries_no_start(tmp_path: Path) -> None:
    document: dict[str, Any] = json.loads(LOOP_PATH.read_text(encoding="utf-8"))
    runner = runner_in(tmp_path / "records", tmp_path / "env")
    artifacts = solve(document, tmp_path / "bundle", runner)
    certificate = artifacts["solution-certificate.json"]
    (external,) = [item for item in certificate["limitations"] if item["kind"] == "external_model"]
    assert "start" not in external and "path_independence_rel" not in external


# -- the job source: k = 0 child starts and the `external` sub-record ------------------------------


def test_a_job_source_gives_the_k0_start_and_its_record(chained: Chained, tmp_path: Path) -> None:
    source = chained.bundle / "artifacts" / "external-coupling.json"
    with pytest.MonkeyPatch.context() as monkeypatch:
        register_variants(monkeypatch)(chained.variant)
        targets = {"reactor": chained.variant}
        store = ExperimentStore(chained.records)
        start = job_coupling_start(source)
        profiles = external_starts(source, targets, store.profile)
        assert profiles is not None
        from dataclasses import replace

        start = replace(start, profiles=profiles)
        runner = runner_in(chained.records, chained.environment)
        artifacts = solve(pinned(chained.variant), tmp_path / "bundle", runner, start)
        last = _entries(chained.artifacts["external-coupling.json"])[-1]
        record = artifacts["external-coupling.json"]
        first = _entries(record)[0]
        assert first["request"]["start"]["profile_sha256"] == last["result"]["profile_sha256"]
        member = artifacts["solve-path.json"]["warm_start"]
        assert member["external"] == {
            "record": "external-start-v1",
            "units": {
                "reactor": {
                    "status": "accepted",
                    "reason": None,
                    "source_experiment_key": last["request"]["experiment_key"],
                    "profile_sha256": last["result"]["profile_sha256"],
                }
            },
        }
        assert member["coupling"]["status"] == "accepted"
        assert r0_projection(artifacts)["warm_start"]["external"] == {
            "reactor": {"status": "accepted", "reason": None}
        }
        reproduction = reproduce_bundle(
            tmp_path / "bundle", rerun=True, rerun_directory=tmp_path / "rerun", run_id="r"
        )
    assert reproduction.report.verdict == "MATCH", reproduction.report.differences


def test_external_start_statuses(chained: Chained, tmp_path: Path) -> None:
    source = chained.bundle / "artifacts" / "external-coupling.json"
    store = ExperimentStore(chained.records)
    variant = chained.variant

    def status(targets: Mapping[str, Any], stored: Any = store.profile, path: Any = source) -> Any:
        found = external_starts(path, targets, stored)
        return None if found is None else (found["reactor"].status, found["reactor"].reason)

    standin = variants.registered_variant("standin-x025-v1")
    assert status({"reactor": standin}) is None
    assert status({"reactor": variant}) == ("accepted", None)
    assert status({"reactor": variant}, path=None) == ("absent", "no_profile")
    assert status({"reactor": variant}, stored=lambda _: None) == ("absent", "profile_unavailable")
    assert status({"reactor": variant}, stored=lambda _: b"{}") == (
        "rejected",
        "external_integrity",
    )
    other = warm_variant("x02-g4-other")
    assert status({"reactor": other}) == (
        "rejected",
        "external_compatibility",
    )
    garbage = tmp_path / "garbage.json"
    garbage.write_bytes(b"{")
    assert status({"reactor": variant}, path=garbage) == (
        "rejected",
        "external_integrity",
    )
    cold_only = synthetic_variant("x02-g4-cold", ["ok"])
    found = external_starts(source, {"reactor": variant, "second": cold_only}, store.profile)
    assert found is not None
    assert (found["second"].status, found["second"].reason) == ("absent", "variant_cold_only")


# -- the store, the program, the protocol ---------------------------------------------------------


def test_the_profile_store_is_content_addressed_and_write_once(tmp_path: Path) -> None:
    store = ExperimentStore(tmp_path)
    data = b'{"cpT":[1.0],"format":"tube-profile-v1","shape":[1,1,1]}'
    sha = store.write_profile(data)
    assert sha == hashlib.sha256(data).hexdigest()
    assert (
        store.profile_path(sha) == tmp_path / "experiments" / "profiles" / sha[:2] / f"{sha}.json"
    )
    assert store.write_profile(data) == sha
    assert store.profile(sha) == data
    assert store.profile("0" * 64) is None
    store.profile_path(sha).write_bytes(b"damaged")
    with pytest.raises(RuntimeError):
        store.write_profile(data)


def test_pinned_program_selects_the_child_by_runner_hash() -> None:
    for variant_id in (
        "pymrm-6089593-g2-nz800-s123-v1",
        "pymrm-6089593-g2-nz800-s123-v2",
        "pymrm-6089593-g2-nz800-s123-v3",
    ):
        variant = variants.registered_variant(variant_id)
        assert pinned_program(variant).script.name == "child.py"
        assert not start_capable(variant)
    unknown = copy.deepcopy(REAL.document)
    unknown["variant_id"] = "x02-unknown-runner"
    unknown["evaluation"]["runner_sha256"] = "0" * 64
    assert pinned_program(variants.variant_from_document(unknown)).script.name == "child.py"


def test_a_start_capable_outlet_without_its_profile_is_a_protocol_error(tmp_path: Path) -> None:
    variant = warm_variant("x02-g4-noexport", child=SYNTHETIC_CHILD)
    runner = runner_in(tmp_path / "records", tmp_path / "env", child=SYNTHETIC_CHILD)
    outcome = runner.run(variant, nominal_inlet(), COMPONENTS, N_TUBES)
    assert outcome.result is None
    statuses = [attempt["execution"]["status"] for attempt in outcome.attempts]
    assert statuses and set(statuses) == {"protocol_error"}
    assert "profile.json" in outcome.attempts[-1]["execution"]["message"]
