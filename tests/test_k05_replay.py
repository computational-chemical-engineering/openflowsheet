"""K05: the run manifest, the replay bundle, and gate G05's two clauses.

The acceptance items (plan §4.2 K05) are clean-environment replay, a changed dependency
failing exact replay, timing excluded from structural identity, and two CI platforms. Three of
those are here; the fourth is the CI matrix, which has been running since 2026-09-22.

The rule that carries the most weight is ADR 0007 D4's ordering: **the mode is decided before
anything runs**. That is what makes "a changed dependency fails exact replay" structural rather
than hopeful — a changed lock file cannot produce a passing exact replay, because the mode was
already `inspected_archived_results` before the first residual was evaluated. The test for it
therefore checks the decision function directly as well as the end-to-end path.
"""

from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT

from openflowsheet.run.bundle import (
    ARTIFACT_DIR,
    MANIFEST_NAME,
    read_artifact,
    read_manifest,
    verify_bundle,
    write_bundle,
)
from openflowsheet.run.manifest import NON_STRUCTURAL, THREAD_VARIABLES, environment
from openflowsheet.run.replay import REGISTERED_PLATFORMS, Rerun, decide_mode, replay
from openflowsheet.run.session import run_session


def flowsheet() -> Any:
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from k03_schema_fixtures import flowsheet as build

    return build()


def policy() -> Any:
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from k03_schema_fixtures import POLICY

    return POLICY


@pytest.fixture(autouse=True)
def pinned_threads(monkeypatch: pytest.MonkeyPatch) -> None:
    """F4, answered by Frank on 2026-09-22: unset is unknown, and unknown is never exact.

    A developer's machine has these unset, so `exact_replay` is unreachable there — which is
    the point of the ruling, and which means the tests must pin them exactly as CI does. A
    test that silently relied on unset-equals-unset would be testing the behaviour the ruling
    removed.
    """
    for variable in THREAD_VARIABLES:
        monkeypatch.setenv(variable, "1")


@pytest.fixture
def bundle(tmp_path: Path) -> tuple[Path, Any]:
    manifest = run_session(flowsheet(), tmp_path, policy=policy(), run_id="run-under-test")
    return tmp_path, manifest


def test_a_run_writes_the_artifacts_a_reader_needs(bundle: tuple[Path, Any]) -> None:
    """A converged run: the plan, the trace, the certificate and the structural report.

    The structural report joined the set with T01 increment 2 (its open question Q4): it is
    integers, ids and booleans, and gate G05 compares it between the two CI architectures.
    """
    directory, manifest = bundle
    assert set(manifest.artifacts) == {
        "solve-plan.json",
        "solve-events.json",
        "solution-certificate.json",
        "structural-report.json",
    }
    assert manifest.outcome == "CONVERGED"
    assert manifest.verification_status == "VERIFIED"
    assert verify_bundle(directory).ok

    # Never both a certificate and a failure bundle, and never neither.
    assert "failure-bundle.json" not in manifest.artifacts


def test_a_failed_run_carries_a_bundle_and_no_certificate(tmp_path: Path) -> None:
    from openflowsheet.orchestrator.trace import SolvePolicy

    capped = SolvePolicy(
        policy_id="SYN-001-capped", residual_tolerances={}, scales={}, max_property_calls=20
    )
    manifest = run_session(flowsheet(), tmp_path, policy=capped, run_id="failed")
    assert manifest.outcome == "BUDGET_EXHAUSTED"
    assert manifest.verification_status is None
    assert "failure-bundle.json" in manifest.artifacts
    assert "solution-certificate.json" not in manifest.artifacts


def test_timing_is_recorded_and_never_hashed(bundle: tuple[Path, Any]) -> None:
    """Plan §4.2 K05 and blueprint D20, checked on the real document rather than asserted.

    The structural document is built by *removing* the excluded fields rather than by listing
    the included ones, so a field added to the manifest is hashed by default. This walks the
    actual document to confirm the exclusion list is the only thing missing.
    """
    _, manifest = bundle
    assert manifest.elapsed_seconds is not None and manifest.elapsed_seconds > 0.0
    assert manifest.started_at

    structural = manifest.structural_document
    full = {
        k: v
        for k, v in manifest.as_document().items()
        # The two self-hashes are derived from the document, not part of it.
        if k not in ("structural_sha256", "manifest_sha256")
    }
    assert set(full) - set(structural) == NON_STRUCTURAL
    for excluded in NON_STRUCTURAL:
        assert excluded not in structural, excluded

    # And the hash is genuinely blind to them: change every excluded field, same hash.
    moved = replace(
        manifest,
        run_id="a-different-name",
        started_at="2000-01-01T00:00:00.000000+00:00",
        elapsed_seconds=(manifest.elapsed_seconds or 0.0) * 99.0,
        hostname="somewhere-else",
        parent_run_id="an-ancestor",
    )
    assert moved.structural_sha256 == manifest.structural_sha256

    # While anything structural changes it.
    assert replace(manifest, policy_id="other").structural_sha256 != manifest.structural_sha256


def test_g05_a_changed_dependency_cannot_produce_an_exact_replay(
    bundle: tuple[Path, Any],
) -> None:
    """G05's first clause, and ADR 0007 D4's ordering.

    The mode is decided from the environment before anything is re-run, so there is no path on
    which a changed lock file reaches a comparison at all. Checked twice: at the decision
    function, and end to end with a rerun supplied that would otherwise have matched.
    """
    directory, manifest = bundle
    recorded = manifest.environment
    changed = replace(recorded, lock_sha256="0" * 64)

    mode, reasons = decide_mode(recorded, changed)
    assert mode == "inspected_archived_results"
    assert any("lock file differs" in reason for reason in reasons)

    fresh = {name: read_artifact(directory, name) for name in manifest.artifacts}
    report = replay(directory, Rerun(fresh), current=changed)
    assert report.mode == "inspected_archived_results"
    assert report.verdict == "NOT_RUN", (
        "a rerun that would have matched must still not be reported as a match: the "
        "environment it ran in is not the environment the archive describes"
    )
    assert report.integrity.ok, "the archive itself is fine; it is the environment that moved"


def test_d4_the_mode_table_in_full(bundle: tuple[Path, Any]) -> None:
    """ADR 0007 D4's three rows, plus D6's thread clause."""
    _, manifest = bundle
    recorded = manifest.environment

    assert decide_mode(recorded, recorded)[0] == "exact_replay"

    other_platform = replace(
        recorded,
        architecture="aarch64" if recorded.architecture != "aarch64" else "x86_64",
    )
    assert decide_mode(recorded, other_platform)[0] == "compatible_reproduction"

    unregistered = replace(recorded, architecture="s390x")
    assert decide_mode(recorded, unregistered)[0] == "inspected_archived_results"
    assert (recorded.architecture, recorded.os_name) in REGISTERED_PLATFORMS

    # D6: a differing thread count is a differing environment.
    threaded = replace(recorded, threads={name: "4" for name in THREAD_VARIABLES})
    mode, reasons = decide_mode(recorded, threaded)
    assert mode == "compatible_reproduction"
    assert any("thread pins differ" in reason for reason in reasons)


def test_a_tampered_artifact_is_reported_and_never_re_run(bundle: tuple[Path, Any]) -> None:
    """Re-running a tampered archive and matching on what survived is a false success.

    So integrity is checked first and unconditionally, and a failure stops the rerun rather
    than being noted beside it.
    """
    directory, manifest = bundle
    target = directory / ARTIFACT_DIR / "solve-events.json"
    document = json.loads(target.read_text())
    document[-1]["message"] = "edited after the fact"
    target.write_text(json.dumps(document))

    integrity = verify_bundle(directory)
    assert not integrity.ok
    assert "solve-events.json" in integrity.tampered

    fresh = {name: read_artifact(directory, name) for name in manifest.artifacts}
    report = replay(directory, Rerun(fresh))
    assert report.mode == "inspected_archived_results"
    assert report.verdict == "NOT_RUN"
    assert any("integrity" in reason for reason in report.reasons)


def test_an_edited_manifest_disagrees_with_its_own_hash(bundle: tuple[Path, Any]) -> None:
    """The index is hashed too, so a manifest edited after writing is caught by itself."""
    directory, _ = bundle
    path = directory / MANIFEST_NAME
    document = json.loads(path.read_text())
    document["policy_id"] = "something-else"
    path.write_text(json.dumps(document))

    integrity = verify_bundle(directory)
    assert not integrity.ok
    assert MANIFEST_NAME in integrity.tampered


def test_an_unexpected_artifact_is_reported(bundle: tuple[Path, Any]) -> None:
    """A file nobody indexed is a bundle that does not describe itself."""
    directory, _ = bundle
    (directory / ARTIFACT_DIR / "smuggled.json").write_text("{}")
    integrity = verify_bundle(directory)
    assert not integrity.ok
    assert integrity.unexpected == ("smuggled.json",)


def test_a_clean_replay_of_a_second_solve_matches(bundle: tuple[Path, Any]) -> None:
    """The acceptance item, and it must be a **second solve**.

    Handing back the archived documents measures `differences(x, x)` — true of any two
    identical objects, and evidence about nothing. The Fable review of K05 found that version
    here, in the fixture generator and in the evidence script at once. Solving again and
    getting the same bytes is the observation ADR 0007 D3.2 wants recorded; it is also the
    thing that would actually break if the solver became nondeterministic.
    """
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from k05_schema_fixtures import resolved_artifacts

    directory, manifest = bundle
    fresh = resolved_artifacts(directory)
    assert set(fresh) == set(manifest.artifacts)
    report = replay(directory, Rerun(fresh))
    assert report.mode == "exact_replay"
    assert report.verdict == "MATCH"
    assert report.bitwise_floats is True
    assert report.differences == ()


def test_a_rerun_that_actually_differs_is_a_mismatch(bundle: tuple[Path, Any]) -> None:
    """MATCH must be falsifiable, or the previous test proves nothing."""
    directory, manifest = bundle
    fresh = {name: read_artifact(directory, name) for name in manifest.artifacts}
    fresh["solve-plan.json"] = {
        **fresh["solve-plan.json"],
        "inner_row_ids": fresh["solve-plan.json"]["inner_row_ids"][:-1],
    }
    report = replay(directory, Rerun(fresh))
    assert report.verdict == "MISMATCH"
    assert report.differences


def test_a_structural_difference_is_a_mismatch_whatever_the_floats_do(
    bundle: tuple[Path, Any],
) -> None:
    """D4: "any R0 difference is MISMATCH whatever the floats do"."""
    directory, manifest = bundle
    fresh = {name: read_artifact(directory, name) for name in manifest.artifacts}
    certificate = dict(fresh["solution-certificate.json"])
    certificate["constants_sha256"] = "f" * 64
    fresh["solution-certificate.json"] = certificate

    report = replay(directory, Rerun(fresh))
    assert report.verdict == "MISMATCH"
    assert any("constants_sha256" in entry for entry in report.differences)


def test_replay_without_a_rerun_inspects_rather_than_guessing(
    bundle: tuple[Path, Any],
) -> None:
    directory, _ = bundle
    report = replay(directory)
    assert report.verdict == "NOT_RUN"
    assert any("no rerun" in reason for reason in report.reasons)


def test_the_bundle_index_is_built_from_the_bytes_written(tmp_path: Path) -> None:
    """A hash supplied alongside the content it describes is a hash of an intention."""
    from openflowsheet.run.manifest import RunManifest

    manifest = RunManifest(
        run_id="r",
        model_version="m@" + "0" * 64,
        constants_sha256="0" * 64,
        policy_id="p",
        plan_id="q",
        check_policy_sha256="0" * 64,
        policy_sha256="0" * 64,
        artifact_r0_sha256="0" * 64,
        numerical_policy_id="K04-numerical-policy-v1",
        environment=environment(),
        artifacts={"a-lie.json": "deadbeef"},
        outcome="CONVERGED",
    )
    written = write_bundle(tmp_path, manifest, {"real.json": {"x": 1}})
    assert set(written.artifacts) == {"real.json"}
    assert written.artifacts["real.json"] != "deadbeef"
    assert verify_bundle(tmp_path).ok

    reread, _ = read_manifest(tmp_path)
    assert reread.structural_sha256 == written.structural_sha256


def test_the_structural_identity_document_contains_no_floats() -> None:
    """G05 compares R0 artifacts across platforms, and R0 is a promise about *structure*.

    Blueprint §8.3 excludes adaptive floating-point decisions from any cross-platform bitwise
    promise, and two `ubuntu-latest` runners were measured disagreeing on a converged state's
    last bits on 2026-09-21. A cross-platform comparison that included a float would fail for
    a reason that is not a defect — and the entire value of this gate is that a failure is one.
    """
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from k05_structural_identity import identity

    document = identity()
    floats: list[str] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")
        elif isinstance(node, float):
            floats.append(path)

    walk(document, "")
    assert not floats, (
        "the G05 comparison document carries floats, which cannot be promised equal across "
        f"platforms: {floats}"
    )

    # And it must carry enough to be worth comparing.
    assert document["structural_sha256"]
    assert len(document["events"]) >= 4
    assert len(document["certificate"]["check_ids"]) > 100
    assert document["certificate"]["verification_status"] == "VERIFIED"
    assert set(document["solver_counters"]) == {
        "residual_calls",
        "jacobian_calls",
        "factorizations",
    }, "ADR 0007 D5.3: the solver counters, never the three property counters"


def test_the_ci_workflow_pins_threads_and_compares_two_platforms() -> None:
    """ADR 0007 D6 and G05, asserted against the workflow rather than assumed.

    The pins matter because a differing thread count is a differing environment; the
    comparison job matters because no single runner can perform it, so it cannot live in the
    test suite.
    """
    import yaml

    workflow = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text())
    check = workflow["jobs"]["check"]
    for variable in THREAD_VARIABLES:
        assert check["env"][variable] == "1", variable

    runners = check["strategy"]["matrix"]["runner"]
    assert len(runners) >= 2, "G05 needs two platforms"

    # S8: assert the registered constant *is* the matrix, rather than that an arm runner
    # exists somewhere. The constant is what `decide_mode` promises reproduction on, and a
    # matrix that drifted from it would promise something CI has never measured.
    architectures = {
        ("aarch64", "Linux") if "arm" in runner else ("x86_64", "Linux") for runner in runners
    }
    assert architectures == REGISTERED_PLATFORMS, (
        f"the CI matrix runs {sorted(architectures)} and `decide_mode` promises reproduction "
        f"on {sorted(REGISTERED_PLATFORMS)}"
    )
    assert "identity" in workflow["jobs"], "the cross-platform comparison job"
    assert workflow["jobs"]["identity"]["needs"] == "check"


def test_the_structural_identity_is_the_same_on_any_platform(bundle: tuple[Path, Any]) -> None:
    """The correction CI forced, pinned so it cannot quietly regress.

    The first version of `structural_sha256` hashed the environment and the artifact index.
    CI produced two different hashes across x86-64 and aarch64 while *every other R0 field was
    identical* — the model version, the plan, the event sequence, the certificate's check
    results, the solver counters. The hash was the only thing that moved, which meant it was
    measuring the wrong thing.

    Blueprint §8.3 R0 is "identical structural artifacts **on supported platforms**", so a
    structural identity that changes with the platform cannot be it. The environment is
    provenance (ADR 0007 D6, for attribution) and the artifact index hashes documents
    containing floats, which §8.3 excludes from any cross-platform promise.
    """
    _, manifest = bundle
    structural = manifest.structural_document

    assert "environment" not in structural
    assert "artifacts" not in structural
    for value in structural.values():
        assert not isinstance(value, float), structural

    # Pretend to be the other architecture, with different BLAS and a different artifact index.
    elsewhere = replace(
        manifest,
        environment=replace(
            manifest.environment,
            architecture="aarch64",
            os_release="6.8.0-aws",
            blas={"name": "scipy-openblas", "version": "0.3.99"},
        ),
        artifacts={name: "f" * 64 for name in manifest.artifacts},
    )
    assert elsewhere.structural_sha256 == manifest.structural_sha256, (
        "R0 promises structural artifacts identical across supported platforms; a hash that "
        "moved with the platform would be promising something else"
    )

    # A changed dependency is still caught, and earlier: by the mode decision, before any rerun.
    changed = replace(manifest.environment, lock_sha256="0" * 64)
    assert decide_mode(manifest.environment, changed)[0] == "inspected_archived_results"


# ------------------------------------------- the four routes the Fable review of K05 measured


def test_m1_the_identity_hash_is_not_the_integrity_check(bundle: tuple[Path, Any]) -> None:
    """The second half of the correction CI forced, which nobody saw at the time.

    Removing the environment and the artifact index from `structural_sha256` was right — it
    was measuring the platform rather than the model. It also removed the only thing detecting
    an edit to either, because that hash *was* the manifest's self-check. Two measured routes
    to a clean verification of a doctored archive:

    1. edit `environment.lock_sha256` in the written manifest;
    2. tamper an artifact and re-index its hash in `artifacts`.

    Identity and integrity are two questions and now have two hashes.
    """

    directory, _ = bundle
    assert verify_bundle(directory).ok

    path = directory / MANIFEST_NAME
    document = json.loads(path.read_text())
    document["environment"]["lock_sha256"] = "0" * 64
    path.write_text(json.dumps(document))
    integrity = verify_bundle(directory)
    assert not integrity.ok, "an edited environment must not verify clean"
    assert MANIFEST_NAME in integrity.tampered


def test_m1_a_re_indexed_tampered_artifact_is_still_caught(tmp_path: Path) -> None:
    """The subtler of the two: edit the artifact *and* update its recorded hash."""
    from openflowsheet.canonical import file_sha256

    manifest = run_session(flowsheet(), tmp_path, policy=policy(), run_id="reindexed")
    target = tmp_path / ARTIFACT_DIR / "solve-events.json"
    events = json.loads(target.read_text())
    events[-1]["message"] = "edited after the fact"
    target.write_text(json.dumps(events))

    document = json.loads((tmp_path / MANIFEST_NAME).read_text())
    document["artifacts"]["solve-events.json"] = file_sha256(target)
    (tmp_path / MANIFEST_NAME).write_text(json.dumps(document))

    integrity = verify_bundle(tmp_path)
    assert not integrity.ok, (
        "the per-artifact hashes now agree with the bytes; only a hash over the whole manifest "
        "notices that the index itself moved"
    )
    assert MANIFEST_NAME in integrity.tampered
    del manifest


def test_m2_a_verdict_change_without_a_near_threshold_flag_is_a_mismatch(
    bundle: tuple[Path, Any],
) -> None:
    """D2.4 forgives a verdict that drifted *near a threshold*, and nothing else.

    The suppression was unconditional: a certificate whose `verification_status` flipped to
    `FAILED` with no flag anywhere still reported `MATCH`. That is precisely the failure D4
    exists to prevent.
    """
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from k05_schema_fixtures import resolved_artifacts

    directory, _ = bundle
    fresh = resolved_artifacts(directory)
    certificate = dict(fresh["solution-certificate.json"])
    assert not any(check["near_threshold"] for check in certificate["checks"]), (
        "the nominal certificate has nothing near a threshold, which is what makes this a test"
    )
    certificate["verification_status"] = "FAILED"
    fresh["solution-certificate.json"] = certificate

    report = replay(directory, Rerun(fresh))
    assert report.verdict == "MISMATCH"
    assert report.verdict_changed_near_threshold == ()


def test_m3_an_unknown_dependency_set_is_never_an_exact_replay() -> None:
    """Two unknowns are not a match.

    An empty lock hash means the file was not found — which is what any non-editable install
    outside the repository records. Compared for equality, two of those looked identical and
    replayed as `exact_replay` with the dependency set unknown on both sides.
    """
    from dataclasses import replace as replace_dataclass

    from openflowsheet.run.manifest import environment as capture

    nowhere = capture(lock_path="/nonexistent/requirements.lock")
    assert nowhere.lock_sha256 == ""
    assert nowhere.threads_known(), "the autouse fixture pins them; this test is about locks"

    mode, reasons = decide_mode(nowhere, nowhere)
    assert mode == "inspected_archived_results"
    assert any("unknown" in reason for reason in reasons)

    known = replace_dataclass(nowhere, lock_sha256="a" * 64)
    assert decide_mode(known, nowhere)[0] == "inspected_archived_results"
    assert decide_mode(nowhere, known)[0] == "inspected_archived_results"
    assert decide_mode(known, known)[0] == "exact_replay"


def test_m5_an_unregistered_platform_is_unknown_on_either_side(
    bundle: tuple[Path, Any],
) -> None:
    """A bundle *recorded* on an unregistered platform is as unknown as a current one.

    Only the current side was checked, so an archive claiming s390x replayed as
    `compatible_reproduction` on x86-64 — asserting a comparability nothing has measured.
    macOS arm64 is also gone from the registered set: plan §4.2 offered it, Frank chose Linux
    aarch64, and an option nobody took is not a registered platform.
    """
    _, manifest = bundle
    recorded = manifest.environment

    assert REGISTERED_PLATFORMS == {("x86_64", "Linux"), ("aarch64", "Linux")}
    assert ("arm64", "Darwin") not in REGISTERED_PLATFORMS

    for side in ("recorded", "current"):
        strange = replace(recorded, architecture="s390x")
        pair = (strange, recorded) if side == "recorded" else (recorded, strange)
        mode, reasons = decide_mode(*pair)
        assert mode == "inspected_archived_results", side
        assert any("not a registered platform" in reason for reason in reasons), side


def test_m4_the_comparison_policy_comes_from_where_it_is_registered() -> None:
    """A policy with two copies is one copy and one rumour.

    `compare.py` carried its own table, labelled interim, and it drifted from the registry:
    `rcond_1` floored at 1e-8 here against 1e-14 there, six decades looser, so any two
    `ILL_CONDITIONED` certificates compared equal. K04's A32 classified against the code's
    table, so the divergence was invisible to the test written to catch exactly this.
    """
    import yaml

    from openflowsheet.run.compare import (
        CURRENT_POLICY_ID,
        NO_FLOOR,
        POLICY_ID,
        REGISTERED_FLOOR,
        RELATIVE_TOLERANCE,
        V1_POLICY_ID,
    )

    registry = yaml.safe_load(
        (REPO_ROOT / "benchmarks" / "k04" / "reference_values.yaml").read_text()
    )["numerical_policy"]

    assert V1_POLICY_ID == registry["id"] == "K04-numerical-policy-v1"
    # ADR 0025 W2: `POLICY_ID` is the alias of the current policy, whose data are registered in
    # `benchmarks/t08/numerical_policy_v2.yaml`; the constants below are v1's, frozen.
    assert POLICY_ID == CURRENT_POLICY_ID == "T08-numerical-policy-v2"
    assert RELATIVE_TOLERANCE == float(registry["relative"])
    for name, entry in registry["floors"].items():
        if "." in name:
            continue
        try:
            expected = float(entry["floor"])
        except ValueError:
            continue
        assert REGISTERED_FLOOR[name] == expected, name

    assert REGISTERED_FLOOR["rcond_1"] == 1e-14
    assert NO_FLOOR == 0.0, (
        "ADR 0007 D2.3 withdrew the invented fallback: an unregistered float compares "
        "relatively and nothing else, because nobody has said what near-zero means for it"
    )


# --------------------------------------------------- the should-fixes the review also measured


def test_s8_a_float_beyond_the_policy_is_a_mismatch_and_one_within_it_is_not(
    bundle: tuple[Path, Any],
) -> None:
    """The two cases that *are* the numerical policy, and neither existed.

    Every replay test passed with a comparator that ignored floats entirely, so nothing
    established that the policy was being applied at all. One float moved beyond D2 must be a
    mismatch; one moved within it must be a match with `bitwise_floats` false — the second is
    the more interesting, because it is the whole reason a tolerance exists rather than an
    equality.
    """
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from k05_schema_fixtures import resolved_artifacts

    directory, _ = bundle

    beyond = resolved_artifacts(directory)
    events = [dict(event) for event in beyond["solve-events.json"]]
    moved = next(e for e in events if isinstance(e.get("merit"), float) and e["merit"] > 0)
    moved["merit"] = moved["merit"] * 2.0
    beyond["solve-events.json"] = events
    report = replay(directory, Rerun(beyond))
    assert report.verdict == "MISMATCH"
    assert any("merit" in entry for entry in report.differences)

    within = resolved_artifacts(directory)
    certificate = json.loads(json.dumps(within["solution-certificate.json"]))
    regularity = certificate["regularity"]
    # `one_norm` is a measured quantity with no registered floor, so it compares relatively
    # at 1e-9 — a one-ulp move is nine decades inside that.
    before = regularity["one_norm"]
    regularity["one_norm"] = math.nextafter(before, math.inf)
    assert regularity["one_norm"] != before
    within["solution-certificate.json"] = certificate

    report = replay(directory, Rerun(within))
    assert report.verdict == "MATCH", report.differences
    assert report.bitwise_floats is False, (
        "the documents are not byte-identical and the policy still calls them a match; that "
        "distinction is what `bitwise_floats` is for"
    )


def test_s8_the_manifest_round_trips_through_the_bundle(bundle: tuple[Path, Any]) -> None:
    """`read_manifest` was a whitelist in disguise, which the removal-list design avoids.

    A field added to `RunManifest` and to `_base_document` but forgotten in the reader would
    read back as its default, and every bundle carrying it would then fail integrity — loud,
    but for the wrong reason and at the worst moment. This makes it a test failure instead.
    """
    directory, written = bundle
    reread, document = read_manifest(directory)
    assert reread.as_document() == written.as_document() == document
    assert reread.manifest_sha256 == written.manifest_sha256
    assert reread.structural_sha256 == written.structural_sha256


def test_s4_an_artifact_the_archive_lacks_is_a_difference(bundle: tuple[Path, Any]) -> None:
    """The loop walked the archive's index, so a *surplus* rerun artifact was never seen.

    A rerun producing both a certificate and a failure bundle is exactly the "never both" case
    `run_session` forbids, and it arrived unnoticed.
    """
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from k05_schema_fixtures import resolved_artifacts

    directory, _ = bundle
    fresh = resolved_artifacts(directory)
    fresh["failure-bundle.json"] = {"outcome": "STAGNATION"}

    report = replay(directory, Rerun(fresh))
    assert report.verdict == "MISMATCH"
    assert any("does not have" in entry for entry in report.differences)


def test_s1_the_identity_covers_what_the_run_did(bundle: tuple[Path, Any]) -> None:
    """S1(b): the hash saw ids, policy *names* and two words — not the plan or the events.

    Measured before the fix: a `SolvePolicy` with the same `policy_id` and a different
    iteration cap produced an identical `structural_sha256`. Now the policy's values and a
    digest of the R0 projection are both in it.
    """
    from openflowsheet.orchestrator.trace import SolvePolicy
    from openflowsheet.run.identity import floats_in, r0_projection, r0_sha256
    from openflowsheet.run.manifest import policy_sha256

    _, manifest = bundle
    assert manifest.policy_sha256 and manifest.artifact_r0_sha256
    assert "policy_sha256" in manifest.structural_document
    assert "artifact_r0_sha256" in manifest.structural_document

    a = SolvePolicy(policy_id="p", residual_tolerances={}, scales={})
    b = SolvePolicy(
        policy_id="p",
        residual_tolerances={},
        scales={},
        max_iterations_per_attempt=a.max_iterations_per_attempt + 1,
    )
    assert policy_sha256(a) != policy_sha256(b), (
        "same name, different values: the identity must see the difference"
    )

    directory, _ = bundle
    artifacts = {name: read_artifact(directory, name) for name in manifest.artifacts}
    projection = r0_projection(artifacts)
    assert r0_sha256(projection) == manifest.artifact_r0_sha256
    assert floats_in(projection) == [], "the R0 projection carries no float, at any depth"
    assert "check_near_threshold" in projection["certificate"], "S2: D2.4's condition, carried"


def test_s5_the_provenance_rule_is_anchored_to_the_document_root() -> None:
    """A bare-key rule would shape-compare a nested `environment` in any future artifact.

    That is the silent-escape shape the `state_sha256` suffix rule exists to avoid, running in
    the other direction. The failure bundle, which carries `replay_identity` and
    `observations`, is the likely first collision.
    """
    from openflowsheet.run.compare import differences

    at_root = {"environment": {"architecture": "x86_64"}}
    elsewhere = {"environment": {"architecture": "aarch64"}}
    assert differences(at_root, elsewhere, policy_id="K04-numerical-policy-v1") == [], (
        "root-level provenance is not compared"
    )

    nested = {"observations": {"environment": {"architecture": "x86_64"}}}
    moved = {"observations": {"environment": {"architecture": "aarch64"}}}
    assert differences(nested, moved, policy_id="K04-numerical-policy-v1") != [], (
        "a nested key of the same name is ordinary content and must be compared"
    )


def test_f4_an_unpinned_machine_cannot_claim_an_exact_replay(
    bundle: tuple[Path, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Frank's ruling of 2026-09-22, option A. Unset is unknown; unknown is never exact."""
    from openflowsheet.run.manifest import environment as capture

    _, manifest = bundle
    for variable in THREAD_VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    unpinned = capture()

    assert not unpinned.threads_known()
    mode, reasons = decide_mode(unpinned, unpinned)
    assert mode == "compatible_reproduction", (
        "two unpinned machines with different core counts looked identical and replayed as "
        "exact_replay, with the effective thread count unknown on both sides"
    )
    assert any("unset" in reason for reason in reasons)
    assert decide_mode(manifest.environment, manifest.environment)[0] == "exact_replay"


def test_s3_the_blas_identity_decides_the_mode(bundle: tuple[Path, Any]) -> None:
    """ADR 0007 D3.3 lists the BLAS vendor as part of the platform identity; it was ignored.

    And the *version* is the one thing a lock hash cannot see — a wheel rebuilt under an
    unchanged lock. The measured non-portability enters at the factorization, which is the
    code a BLAS build feeds.
    """
    _, manifest = bundle
    recorded = manifest.environment
    assert recorded.blas["name"] in recorded.identity()

    other_vendor = replace(recorded, blas={**recorded.blas, "name": "mkl"})
    assert decide_mode(recorded, other_vendor)[0] == "compatible_reproduction"

    newer = replace(recorded, blas={**recorded.blas, "version": "99.0.0"})
    mode, reasons = decide_mode(recorded, newer)
    assert mode == "compatible_reproduction"
    assert any("BLAS version" in reason for reason in reasons)


def test_s6_the_model_identity_survives_a_failure_before_the_plan(tmp_path: Path) -> None:
    """§8.2 requires a failure bundle to carry its replay identity.

    `model_version` and `constants_sha256` were read from the plan, so a solve that failed
    before a plan existed recorded empty strings for both — and two different models that both
    failed at planning shared a structural identity.
    """
    from openflowsheet.orchestrator.trace import SolvePolicy

    capped = SolvePolicy(
        policy_id="SYN-001-capped", residual_tolerances={}, scales={}, max_property_calls=20
    )
    manifest = run_session(flowsheet(), tmp_path, policy=capped, run_id="early-failure")
    assert manifest.outcome == "BUDGET_EXHAUSTED"
    assert manifest.plan_id == "", "no plan was built"
    assert manifest.model_version.endswith("@" + "0" * 0) or "@" in manifest.model_version
    assert manifest.model_version and manifest.constants_sha256, (
        "the model identity comes from the compiled problem, not from a plan that never existed"
    )
    assert manifest.reproducibility_class == "R1"
