"""T07 W3a: revision runs through the contract — routes, policies, bundles, rerun (gate G8).

Design note `docs/design/T07-jobs-and-bindings.md` §12.1–§12.3 and ruling round 1 R2 (R2.1–R2.5),
§13 Q26 (ii), §16 G8; ADR 0020 D4. There is no job layer yet (W4), so G8 runs the plain functions
the job runner will call: `select_route` → `resolve_policy("default", route)` →
`run_revision_session` → `verify_bundle` → `reproduce_bundle(rerun=True)`, on W0.2's 50 revisions.

Expectations are stated here, not read back from the code under test: the routes from W0.2's
binder table, the policy hashes from `benchmarks/registry.yaml`, the R0 records from
`scripts/t06_identity.py` (the `t06` key's own builder), the roots from the P01 and T02 reference
values at T02 §6.4's allowances, and the legacy plan's documents from the benchmark's pre-move
`_legacy_plan` (measured at `b2c160b`, before it moved; `docs/t07-measurements.md` W3a).

**Two corpus revisions end at an initializer's refusal:** `SYN-001-UL-C3X` on `revision_eo` and
`SYN-001-A02-360-no-guess` on `legacy_eo` both end `INITIALIZATION_FAILED` at a `solve_eo` step that
holds no `RegionResult`. Ruling round 3, Q1 bundles that step through `initializer_bundle`, so every
eligible revision now ends with a bundle (the W3 report had them `failure_bundle_unmapped`); their
documents are pinned in `test_t07_w3f_initializer_bundle.py`.
"""

from __future__ import annotations

import copy
import hashlib
import sys
from collections.abc import Mapping
from dataclasses import replace
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT
from t06_ensemble_support import _a02_sweep, _p01_variant
from t06_support import worst_ratio
from t07_corpus import A02_FILES, CORPUS
from test_t06_w4_registry import BY_ID, CONSTRUCTED, REGISTRY

import benchmarks.t06.ensemble as ensemble
from openflowsheet.application.binding import Binding, bind_revision_or_reason
from openflowsheet.application.policies import (
    APPLICATION_POLICIES,
    DEFAULT_POLICY_ID,
    ROUTE_DEFAULT_POLICY,
    T04_W12,
    T06_REVISION_V2,
    resolve_policy,
)
from openflowsheet.application.revision_run import (
    NoRoute,
    Route,
    RunUnsupportedError,
    legacy_plan,
    reproduce_bundle,
    run_revision_session,
    select_route,
    solve_route,
)
from openflowsheet.canonical import canonical_json
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.trace import RecyclePolicy, SolvePolicy
from openflowsheet.run.bundle import read_artifact, read_manifest, verify_bundle, write_bundle
from openflowsheet.run.identity import execution_plan_r0, floats_in, r0_projection, r0_sha256
from openflowsheet.run.manifest import policy_sha256
from openflowsheet.run.session import run_session
from openflowsheet.verify.certificate import CheckPolicy

sys.path.insert(0, str(REPO_ROOT / "scripts"))

#: W0.2: the revisions only the legacy binder binds and `legacy_eo` solves: the 11 A02 files
#: (ruling round 6, B1: `legacy_answers` holds for their `role: free` refusal).
LEGACY_ONLY = A02_FILES
#: W0.2: neither binder binds (STR-02, STR-06); and, since ruling round 6, B1, the conflicting
#: spec, which only the legacy binder binds and whose refusal (`specification_unconsumed`) does not
#: admit `legacy_eo` (G-R6-1). `validate()` finds it `INVALID` before and after (W0.4); the legacy
#: plan builder refuses its over-specified declaration with a `ValueError` (W3a.3).
NO_ROUTE = ("SYN-001-T06-STR02", "SYN-001-T06-STR06", "SYN-001-conflicting-heater-spec")
#: Routed, but `validate()` finds them not ready, so admission never solves them (§5.3 step 2).
#: None since ruling round 6, B1.
NOT_ELIGIBLE: tuple[str, ...] = ()
#: Ruling round 3, Q1: `INITIALIZATION_FAILED` with no `RegionResult` at the failed `solve_eo`
#: step, bundled by `initializer_bundle` with the source its message names.
INITIALIZER_REFUSALS = {
    "SYN-001-UL-C3X": ("initializer_failed(U-HX): temperature_cross(cold_end)", "U-HX"),
    "SYN-001-A02-360-no-guess": ("missing_initial_guess(S3.T)", "S3.T"),
}
#: The P01 variants (SYN-001 revisions the reference values register a full state for).
P01_VARIANTS = (
    "SYN-001-nominal",
    "SYN-001-once-through",
    "SYN-001-high-recycle",
    "SYN-001-all-liquid-310K",
    "SYN-001-all-vapor-420K",
)
#: T02's A02 sweep points the three unsuffixed A02 files register (T_heater, K).
A02_SWEEP = {"SYN-001-A02-355": "355K", "SYN-001-A02-360": "360K", "SYN-001-A02-365": "365K"}
ROUTED = tuple(name for name in CORPUS if name not in NO_ROUTE)
ELIGIBLE = tuple(name for name in ROUTED if name not in NOT_ELIGIBLE)
#: The eligible revisions that end with a bundle: every one since ruling round 3, Q1.
BUNDLED = ELIGIBLE


def expected_route(name: str) -> str | None:
    if name in NO_ROUTE:
        return None
    return "legacy_eo" if name in LEGACY_ONLY else "revision_eo"


# -- policies (§12.2, R2.3) ---------------------------------------------------------------------


def test_the_application_policies_are_the_registered_ones() -> None:
    """R2.3: two policies, each its route's registered one, each hash its registry entry's; and
    T08's offered `T08-warm-v1` (ADR 0024 D1) and `T08-ptc-v1` (ADR 0023), which are not registry
    policies and are checked by construction in `test_t08_w4_warm_starts` and
    `test_t08_ptc_r1_case`."""
    assert sorted(APPLICATION_POLICIES) == [
        "T04-W12",
        "T06-revision-v2",
        "T08-ptc-v1",
        "T08-warm-v1",
    ]
    for policy_id in ("T04-W12", "T06-revision-v2"):
        policy = APPLICATION_POLICIES[policy_id]
        entry = REGISTRY["policies"][policy_id]
        assert policy.policy_id == entry["policy_id"] == policy_id
        assert policy_sha256(policy) == entry["sha256"]
        # One object: the T06 ensemble's registered construction is this one (W0 flag E6).
        assert CONSTRUCTED[policy_id] is policy
    assert policy_sha256(T06_REVISION_V2) == (
        "c03d7205fb445b4e3c0d2c5d712c04fc60fbb6bde1f8ff753c7cedffd61c66ab"
    )
    assert T06_REVISION_V2.globalization.eo_core == "newton_refined"
    assert T06_REVISION_V2.globalization.eo_recovery == "homotopy_or_sequential_restart"
    # The registry's per-path policies, the tear path (unreachable through `solve`) excepted.
    registered = dict(REGISTRY["ensemble"]["policies"])
    assert registered.pop("tear") == "SYN-001-K03"
    assert dict(ROUTE_DEFAULT_POLICY) == registered


def test_default_resolves_per_route_and_a_named_policy_on_either() -> None:
    assert DEFAULT_POLICY_ID == "default"
    assert resolve_policy("default", "revision_eo") is T06_REVISION_V2
    assert resolve_policy("default", "legacy_eo") is T04_W12
    for path in ("revision_eo", "legacy_eo"):
        assert resolve_policy("T04-W12", path) is T04_W12  # type: ignore[arg-type]
        assert resolve_policy("T06-revision-v2", path) is T06_REVISION_V2  # type: ignore[arg-type]
        assert resolve_policy("T05b-v2", path) is None  # type: ignore[arg-type]
        assert resolve_policy("SYN-001-K03", path) is None  # type: ignore[arg-type]


# -- SolvePolicy.from_document (§12.3) ------------------------------------------------------------


def _policies() -> list[SolvePolicy]:
    tear = SolvePolicy(
        policy_id="round-trip",
        residual_tolerances={"mole_flow": {"absolute": 1e-9, "relative": 1e-12}},
        scales={"S1.n.A": 2.5},
        initializer_chain=("traversal-G0-v1",),
        max_attempts=3,
        recycle=RecyclePolicy(method="eo", tear_streams=("S6",)),
    )
    return [*CONSTRUCTED.values(), tear]


@pytest.mark.parametrize("policy", _policies(), ids=lambda p: p.policy_id)
def test_solve_policy_document_round_trips_byte_identically(policy: SolvePolicy) -> None:
    """document → object → document, byte-identical under ADR 0002, also through JSON."""
    import json

    document = policy.as_document()
    rebuilt = SolvePolicy.from_document(json.loads(canonical_json(document)))
    assert canonical_json(rebuilt.as_document()) == canonical_json(document)
    assert rebuilt == policy
    assert policy_sha256(rebuilt) == policy_sha256(policy)


@pytest.mark.parametrize("where", ["", "globalization", "globalization.homotopy", "recycle"])
def test_solve_policy_from_document_refuses_unknown_and_missing_members(where: str) -> None:
    document = T06_REVISION_V2.as_document()
    node = document
    for key in filter(None, where.split(".")):
        node = node[key]
    node["unknown_member"] = 1
    with pytest.raises(ValueError, match="unknown members"):
        SolvePolicy.from_document(document)
    del node["unknown_member"]
    node.pop(sorted(k for k in node if k != "tear_streams")[0])
    with pytest.raises(ValueError, match="missing members"):
        SolvePolicy.from_document(document)


# -- routing (R2.1) and the legacy plan (R2.2) ----------------------------------------------------


def test_the_corpus_is_w02s_fifty() -> None:
    assert len(CORPUS) == 50
    assert len(A02_FILES) == 11
    assert len([name for name in CORPUS if expected_route(name) == "revision_eo"]) == 36
    # G-R6-1: 36 `revision_eo`, 11 `legacy_eo`, 3 with no route.
    assert len([name for name in CORPUS if expected_route(name) == "legacy_eo"]) == 11
    assert len([name for name in CORPUS if expected_route(name) is None]) == 3


@pytest.mark.parametrize("name", sorted(CORPUS))
def test_select_route_is_w02s_binder_table(name: str) -> None:
    document = CORPUS[name]()
    route = select_route(document)
    expected = expected_route(name)
    if expected is None:
        assert isinstance(route, NoRoute)
        assert route.reason == (
            f"{route.revision.kind}({route.revision.detail}); "
            f"{route.legacy.kind}({route.legacy.detail})"
        )
        if name == "SYN-001-conflicting-heater-spec":
            # Ruling round 6, B1: the legacy binder binds; the refusal does not admit `legacy_eo`.
            assert route.reason == (
                "unsupported(specification_unconsumed(SPEC-heater-duty)); "
                "unsupported(legacy_route_not_admitted(specification_unconsumed))"
            )
        return
    assert isinstance(route, Route)
    assert route.solve_path == expected
    if expected == "revision_eo":
        assert route.reason is None
    else:
        assert name in A02_FILES
        assert route.reason == "unsupported(specification_role_unsupported(GUESS-heater-outlet-T))"
    # A pure function of the document: the document is not mutated.
    assert canonical_json(document) == canonical_json(CORPUS[name]())


def test_the_benchmark_runs_the_moved_legacy_plan() -> None:
    """R2.2: `ensemble._legacy_plan` moved verbatim; the benchmark delegates to the one function."""
    assert ensemble._legacy_plan is legacy_plan


def _digest(document: Any) -> str:
    return hashlib.sha256(canonical_json(document)).hexdigest()


def test_legacy_plan_documents_equal_the_pre_move_benchmarks() -> None:
    """R2.2: for every legacy-bound corpus revision, under both application policies, the plan and
    T01 report documents equal those of the benchmark's `_legacy_plan` before the move (measured
    at `b2c160b`); the over-specified revision raises the same `ValueError` as before."""
    legacy_bound = [
        name for name in CORPUS if isinstance(bind_revision_or_reason(CORPUS[name]()), Binding)
    ]
    assert len(legacy_bound) == 20
    assert sorted({name for name, _ in LEGACY_PLAN}) == sorted(legacy_bound)
    for (name, policy_id), expected in LEGACY_PLAN.items():
        binding = bind_revision_or_reason(CORPUS[name]())
        assert isinstance(binding, Binding)
        policy = APPLICATION_POLICIES[policy_id]
        if expected == ("raised ValueError",):
            with pytest.raises(ValueError, match="structurally closed"):
                legacy_plan(binding, policy)
            continue
        plan, report = legacy_plan(binding, policy)
        assert (_digest(plan.as_document()), _digest(report.as_document())) == expected, name


# -- R0 projection (§12.3, R2.4) ------------------------------------------------------------------


def test_the_new_r0_branches_are_inert_for_a_tear_bundle(tmp_path: Path) -> None:
    """No bundle before T07 has `execution-plan.json` or `solve-path.json` (K05 unchanged)."""
    from openflowsheet.application.revision_run import registered_case, registered_flowsheet

    case = registered_case("SYN-001-nominal")
    assert case is not None
    manifest = run_session(registered_flowsheet(case), tmp_path)
    artifacts = {name: read_artifact(tmp_path, name) for name in manifest.artifacts}
    projection = r0_projection(artifacts)
    assert "execution_plan" not in projection and "solve_path" not in projection
    assert manifest.artifact_r0_sha256 == r0_sha256(projection)


# -- G8: every routed corpus revision, bundled and rerun ------------------------------------------


@cache
def _identity_records() -> dict[str, dict[str, Any]]:
    """The `t06` key's revision records (`cases`, `references`), by corpus name."""
    import t06_identity

    section = REGISTRY["reference_fixtures"]
    fixtures = {fixture["id"]: fixture for fixture in section["fixtures"]}
    by_name: dict[str, dict[str, Any]] = {}
    for case_id, record in t06_identity._cases().items():
        by_name[Path(BY_ID[case_id]["revision"]).stem] = record
    for ref_id, record in t06_identity._references().items():
        by_name[Path(fixtures[ref_id]["revision"]).stem] = record
    return by_name


#: Session-scoped: W3e's tests (`test_t07_w3e_solution_state.py`) read the same bundles.
@pytest.fixture(scope="session")
def runs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """Every eligible revision: its route, the bundle's manifest (or the typed refusal), and the
    rerun's report."""
    root = tmp_path_factory.mktemp("w3a")
    out: dict[str, Any] = {}
    for name in ELIGIBLE:
        document = CORPUS[name]()
        route = select_route(document)
        assert isinstance(route, Route), name
        policy = resolve_policy(DEFAULT_POLICY_ID, route.solve_path)
        assert policy is not None
        directory = root / name
        try:
            manifest = run_revision_session(
                route,
                document,
                directory,
                run_id=f"run-{name}",
                policy=policy,
                check_policy=CheckPolicy(),
                policy_requested=DEFAULT_POLICY_ID,
            )
        except RunUnsupportedError as error:
            out[name] = {"route": route, "unsupported": error.code, "directory": directory}
            continue
        reproduction = reproduce_bundle(
            directory, rerun=True, rerun_directory=root / f"{name}.rerun", run_id="rerun"
        )
        out[name] = {
            "route": route,
            "manifest": manifest,
            "directory": directory,
            "reproduction": reproduction,
        }
    return out


def test_g8_every_eligible_revision_ends_typed_with_one_bundle_document(
    runs: dict[str, Any],
) -> None:
    unsupported = {name: run["unsupported"] for name, run in runs.items() if "unsupported" in run}
    assert unsupported == {}
    # Ruling round 3, Q1 item 6: 47 bundles, 44 `VERIFIED`, 1 `HOMOTOPY_STALLED` and 2
    # `INITIALIZATION_FAILED` (before it, 45 bundles and 2 unmapped runs).
    ends = [(run["manifest"].outcome, run["manifest"].verification_status) for run in runs.values()]
    assert len(ends) == 47
    assert {end: ends.count(end) for end in set(ends)} == {
        ("CONVERGED", "VERIFIED"): 44,
        ("HOMOTOPY_STALLED", None): 1,
        ("INITIALIZATION_FAILED", None): 2,
    }
    for name, (message, source) in INITIALIZER_REFUSALS.items():
        bundle = read_artifact(runs[name]["directory"], "failure-bundle.json")
        observed = (bundle["observations"]["message"], bundle["implicated_sources"])
        assert observed == (message, [source]), name
    for name, run in runs.items():
        manifest = run["manifest"]
        names = set(manifest.artifacts)
        assert ("solution-certificate.json" in names) != ("failure-bundle.json" in names), name
        assert (manifest.verification_status is not None) == ("solution-certificate.json" in names)
        assert {
            "solve-events.json",
            "execution-plan.json",
            "solve-plan.json",
            "structural-report.json",
            "revision.json",
            "solve-policy.json",
            "check-policy.json",
            "solve-path.json",
        } <= names, name


@pytest.mark.parametrize("name", BUNDLED)
def test_g8_bundle_integrity_route_and_policy(runs: dict[str, Any], name: str) -> None:
    run = runs[name]
    directory, manifest = run["directory"], run["manifest"]
    assert verify_bundle(directory).ok
    route = run["route"]
    assert route.solve_path == expected_route(name)
    solve_path = read_artifact(directory, "solve-path.json")
    assert solve_path == {
        "solve_path": route.solve_path,
        "route_reason": route.reason,
        "policy_requested": "default",
    }
    registered = ROUTE_DEFAULT_POLICY[route.solve_path]
    assert manifest.policy_id == registered
    assert manifest.policy_sha256 == REGISTRY["policies"][registered]["sha256"]
    assert manifest.check_policy_sha256 == CheckPolicy().sha256
    assert read_artifact(directory, "check-policy.json") == {
        "policy_id": CheckPolicy().policy_id,
        "tolerances": dict(CheckPolicy().tolerances),
    }
    assert canonical_json(read_artifact(directory, "revision.json")) == canonical_json(
        CORPUS[name]()
    )
    artifacts = {entry: read_artifact(directory, entry) for entry in manifest.artifacts}
    projection = r0_projection(artifacts)
    assert projection["solve_path"] == route.solve_path
    assert floats_in(projection) == []
    assert manifest.artifact_r0_sha256 == r0_sha256(projection)


@pytest.mark.parametrize("name", BUNDLED)
def test_g8_rerun_matches_on_the_same_host(runs: dict[str, Any], name: str) -> None:
    run = runs[name]
    report = run["reproduction"].report
    assert report.verdict == "MATCH", (report.reasons, report.differences[:5])
    assert report.mode in ("exact_replay", "compatible_reproduction")
    assert run["reproduction"].rerun_manifest.structural_sha256 == (
        run["manifest"].structural_sha256
    )


def test_g8_r0_equals_the_t06_keys_records(runs: dict[str, Any]) -> None:
    """Wherever the `t06` key records (fixture, `revision_eo`, `T06-revision-v2`, initializer
    start): its §4.3 flowsheets and REF-01…REF-07."""
    records = _identity_records()
    assert len(records) == 17
    for name, record in records.items():
        run = runs[name]
        assert run["route"].solve_path == "revision_eo"
        assert run["manifest"].policy_id == "T06-revision-v2"
        directory = run["directory"]
        artifacts = {entry: read_artifact(directory, entry) for entry in run["manifest"].artifacts}
        projection = r0_projection(artifacts)
        assert run["manifest"].outcome == record["outcome"], name
        for key in ("events", "solver_counters", "structural", "certificate", "failure"):
            assert projection.get(key) == record.get(key), (name, key)
        # The key records the plan's R0 from the in-memory document, where an integral float is
        # `"3.0"`; the bundle holds its canonical bytes, where ADR 0002 writes `3`. So the plan
        # is compared as the key computes it, from the route's own plan, and that plan's
        # canonical bytes are the bundle's `execution-plan.json`.
        result = solve_route(
            run["route"], CORPUS[name](), policy=T06_REVISION_V2, check_policy=CheckPolicy()
        )
        assert isinstance(result.plan, ExecutionPlan)
        assert execution_plan_r0(result.plan.as_document()) == record["plan"], name
        assert canonical_json(result.plan.as_document()) == canonical_json(
            artifacts["execution-plan.json"]
        )


def _root_ratio(name: str, root: Mapping[str, tuple[Decimal, float]]) -> tuple[float, str]:
    document = CORPUS[name]()
    route = select_route(document)
    assert isinstance(route, Route)
    policy = resolve_policy(DEFAULT_POLICY_ID, route.solve_path)
    assert policy is not None
    result = solve_route(route, document, policy=policy, check_policy=CheckPolicy())
    assert result.certificate is not None and result.state is not None
    assert result.certificate.verification_status == "VERIFIED"
    if route.solve_path == "revision_eo":
        # A revision-built flowsheet names a duty by its instance (`heater.Q`), the registered
        # SYN-001 declaration by its unit (`U-HEAT.Q`).
        renamed = {"U-HEAT.Q": "heater.Q", "U-FLASH.Q": "flash.Q"}
        root = {renamed.get(column, column): entry for column, entry in root.items()}
    return worst_ratio(result.state, root)


@pytest.mark.parametrize("name", P01_VARIANTS)
def test_g8_syn001_variants_verify_at_their_reference_state(
    runs: dict[str, Any], name: str
) -> None:
    """The P01 variants on `revision_eo`: `VERIFIED`, every registered coordinate within T02
    §6.4's allowance of the 20-digit reference."""
    assert runs[name]["manifest"].verification_status == "VERIFIED"
    ratio, where = _root_ratio(name, _p01_variant(name))
    assert ratio <= 1.0, (ratio, where)


@pytest.mark.parametrize("name", sorted(A02_SWEEP))
def test_g8_a02_sweep_files_verify_at_t02s_reference(runs: dict[str, Any], name: str) -> None:
    """The three A02 sweep files on `legacy_eo` under `T04-W12`: `VERIFIED` at T02's A02 sweep
    point (the duties, the heater outlet temperature and its phase split)."""
    assert runs[name]["route"].solve_path == "legacy_eo"
    assert runs[name]["manifest"].verification_status == "VERIFIED"
    ratio, where = _root_ratio(name, _a02_sweep(f"T_heater={A02_SWEEP[name]}"))
    assert ratio <= 1.0, (ratio, where)


def test_g8_every_a02_file_ends_typed_and_its_verdict_is_reported(runs: dict[str, Any]) -> None:
    """R2 (W3a tests): NET-05 and every A02 file run on `legacy_eo`; each ends typed. The verdicts
    are recorded in `docs/t07-measurements.md` (W3a); here they are pinned."""
    verdicts = {
        name: (
            runs[name].get("unsupported")
            or (runs[name]["manifest"].outcome, runs[name]["manifest"].verification_status)
        )
        for name in A02_FILES
    }
    assert all(runs[name]["route"].solve_path == "legacy_eo" for name in A02_FILES)
    assert verdicts == {
        "SYN-001-A02-340-two-phase-guess": ("CONVERGED", "VERIFIED"),
        "SYN-001-A02-352-vapor-guess-410": ("HOMOTOPY_STALLED", None),
        "SYN-001-A02-355-dew-guess-377": ("CONVERGED", "VERIFIED"),
        "SYN-001-A02-355-dew-guess": ("CONVERGED", "VERIFIED"),
        "SYN-001-A02-355-liquid-guess": ("CONVERGED", "VERIFIED"),
        "SYN-001-A02-355": ("CONVERGED", "VERIFIED"),
        "SYN-001-A02-360-liquid-guess": ("CONVERGED", "VERIFIED"),
        "SYN-001-A02-360-no-guess": ("INITIALIZATION_FAILED", None),
        "SYN-001-A02-360-vapor-guess": ("CONVERGED", "VERIFIED"),
        "SYN-001-A02-360": ("CONVERGED", "VERIFIED"),
        "SYN-001-A02-365": ("CONVERGED", "VERIFIED"),
    }


# -- rerun rules (§12.3, R2.5) and the forged bundle (Q26 (ii)) -----------------------------------


def _rewrite(directory: Path, target: Path, *, intact: bool = True, **changes: Any) -> Path:
    """A copy of a bundle with artifacts replaced (`name=document`, `None` drops one) and the
    index, `artifact_r0_sha256` and the manifest's hashes recomputed: consistent, but forged.
    `intact=False` for a forgery a cross-check inside `verify_bundle` is expected to catch."""
    manifest, _ = read_manifest(directory)
    artifacts = {name: read_artifact(directory, name) for name in manifest.artifacts}
    overrides = changes.pop("manifest", {})
    for name, document in changes.items():
        key = name.replace("_", "-") + ".json"
        if document is None:
            artifacts.pop(key, None)
        else:
            artifacts[key] = document
    forged = replace(manifest, artifact_r0_sha256=r0_sha256(r0_projection(artifacts)), **overrides)
    written = write_bundle(target, forged, artifacts)
    assert verify_bundle(target).ok is intact
    assert set(written.artifacts) == set(artifacts)
    return target


def _reproduce(directory: Path, tmp_path: Path, *, rerun: bool = True) -> Any:
    return reproduce_bundle(directory, rerun=rerun, rerun_directory=tmp_path / "r", run_id="r")


def test_rerun_false_inspects_and_never_matches(runs: dict[str, Any], tmp_path: Path) -> None:
    result = _reproduce(runs["SYN-001-T06-NET03"]["directory"], tmp_path, rerun=False)
    assert (result.report.mode, result.report.verdict) == ("inspected_archived_results", "NOT_RUN")
    assert result.rerun_manifest is None


def test_rerun_without_solve_path_is_unsupported(runs: dict[str, Any], tmp_path: Path) -> None:
    bundle = _rewrite(runs["SYN-001-T06-NET03"]["directory"], tmp_path / "b", solve_path=None)
    result = _reproduce(bundle, tmp_path)
    assert (result.report.mode, result.report.verdict) == ("inspected_archived_results", "NOT_RUN")
    assert result.report.reasons[-1] == "rerun_unsupported(no_solve_path)"
    assert result.rerun_manifest is None


def test_rerun_refuses_a_policy_document_that_is_not_the_manifests(
    runs: dict[str, Any], tmp_path: Path
) -> None:
    source = runs["SYN-001-T06-NET03"]["directory"]
    policy = read_artifact(source, "solve-policy.json")
    policy["max_attempts"] = policy["max_attempts"] + 1
    bundle = _rewrite(source, tmp_path / "b", solve_policy=policy)
    result = _reproduce(bundle, tmp_path)
    assert result.report.verdict == "NOT_RUN"
    assert result.report.reasons[-1] == "policy_document_mismatch"
    check = read_artifact(source, "check-policy.json")
    check["tolerances"] = {kind: value / 2 for kind, value in check["tolerances"].items()}
    bundle = _rewrite(source, tmp_path / "c", check_policy=check)
    assert _reproduce(bundle, tmp_path).report.reasons[-1] == "policy_document_mismatch"


def test_rerun_follows_the_recorded_route_and_never_reroutes(
    runs: dict[str, Any], tmp_path: Path
) -> None:
    """R2.5: a forged `solve-path.json` never produces a false `MATCH`. On this corpus a switched
    route either has no binder (`route_unbound`) or no registered certificate on the other route
    (`RunUnsupportedError`); a forged `route_reason` is a `MISMATCH`. Each switched route names
    the manifest's policy by its registered id, which resolves alike on either route, so that the
    forgery passes W3-Q4's integrity cross-check and reaches the rerun."""
    a02 = runs["SYN-001-A02-360"]["directory"]
    switched = dict(
        read_artifact(a02, "solve-path.json"), solve_path="revision_eo", policy_requested="T04-W12"
    )
    result = _reproduce(_rewrite(a02, tmp_path / "a", solve_path=switched), tmp_path)
    assert result.report.verdict == "NOT_RUN"
    assert result.report.reasons[-1] == "rerun_unsupported(route_unbound(revision_eo))"

    net09 = runs["SYN-001-T06-NET09"]["directory"]
    switched = dict(
        read_artifact(net09, "solve-path.json"),
        solve_path="legacy_eo",
        policy_requested="T06-revision-v2",
    )
    with pytest.raises(RunUnsupportedError, match=r"certificate_unmapped\(legacy_eo"):
        _reproduce(_rewrite(net09, tmp_path / "b", solve_path=switched), tmp_path / "x")

    # A route no registry knows is caught before any rerun (W3-Q4): not rerun, `tampered`.
    unknown = dict(read_artifact(net09, "solve-path.json"), solve_path="tear")
    forged = _rewrite(net09, tmp_path / "c", intact=False, solve_path=unknown)
    assert verify_bundle(forged).tampered == ("solve-path.json",)
    result = _reproduce(forged, tmp_path / "y")
    assert (result.report.verdict, result.rerun_manifest) == ("NOT_RUN", None)

    # The route's reason is recomputed from the revision, never copied from the archive.
    edited = dict(read_artifact(net09, "solve-path.json"), route_reason="forged")
    result = _reproduce(_rewrite(net09, tmp_path / "d", solve_path=edited), tmp_path / "z")
    assert result.report.verdict == "MISMATCH"
    assert any(entry.startswith("solve-path.json") for entry in result.report.differences)


def test_w3q4_policy_requested_must_resolve_to_the_manifests_policy(
    runs: dict[str, Any], tmp_path: Path
) -> None:
    """W3-Q4 (decision log): `verify_bundle` resolves `solve-path.json`'s `policy_requested` on
    its recorded route and requires the manifest's `policy_sha256`; a forged request is
    `tampered` and never rerun. The registered id and the alias both resolve on either route; a
    §8.3 tightening of `max_property_calls` recorded in `solve-policy.json` is admitted."""
    for name, other in (("SYN-001-T06-NET03", "T04-W12"), ("SYN-001-A02-360", "T06-revision-v2")):
        directory = runs[name]["directory"]
        recorded = read_artifact(directory, "solve-path.json")
        assert recorded["policy_requested"] == "default"
        assert verify_bundle(directory).ok
        registered = read_manifest(directory)[0].policy_id
        same = dict(recorded, policy_requested=registered)
        assert verify_bundle(_rewrite(directory, tmp_path / name / "same", solve_path=same)).ok
        for index, forged_request in enumerate((other, "no-such-policy", 7, None)):
            forged = dict(recorded, policy_requested=forged_request)
            bundle = _rewrite(
                directory, tmp_path / name / str(index), intact=False, solve_path=forged
            )
            assert verify_bundle(bundle).tampered == ("solve-path.json",), forged_request
            result = _reproduce(bundle, tmp_path / name / f"r{index}")
            assert (result.report.verdict, result.rerun_manifest) == ("NOT_RUN", None)
        # A file that is not an object at all is judged, not raised.
        bundle = _rewrite(directory, tmp_path / name / "list", intact=False, solve_path=[1])
        assert verify_bundle(bundle).tampered == ("solve-path.json",)

    # A tightened policy (§8.3): the manifest hashes the effective policy, which is the resolved
    # one with `max_property_calls` lowered, and `solve-policy.json` records that value.
    net03 = runs["SYN-001-T06-NET03"]
    policy = read_artifact(net03["directory"], "solve-policy.json")
    tightened = dict(policy, max_property_calls=policy["max_property_calls"] - 1)
    rebuilt = SolvePolicy.from_document(tightened)
    bundle = _rewrite(
        net03["directory"],
        tmp_path / "tight",
        solve_policy=tightened,
        manifest={"policy_sha256": policy_sha256(rebuilt)},
    )
    assert verify_bundle(bundle).ok
    # Loosened instead: no admitted request gives that policy.
    loosened = dict(policy, max_property_calls=policy["max_property_calls"] + 1)
    bundle = _rewrite(
        net03["directory"],
        tmp_path / "loose",
        intact=False,
        solve_policy=loosened,
        manifest={"policy_sha256": policy_sha256(SolvePolicy.from_document(loosened))},
    )
    assert verify_bundle(bundle).tampered == ("solve-path.json",)


def test_rerun_of_a_legacy_eo_bundle_matches(runs: dict[str, Any]) -> None:
    """R2 (W3a tests): one `legacy_eo` bundle reruns to `MATCH` (every A02 file does, above)."""
    report = runs["SYN-001-A02-360"]["reproduction"].report
    assert report.verdict == "MATCH"


def test_q26_a_forged_verified_bundle_never_matches(runs: dict[str, Any], tmp_path: Path) -> None:
    """Q26 (ii): a bundle of a run that did not converge, forged to carry a `VERIFIED`
    certificate with a consistent index and recomputed manifest hashes. `rerun=True` re-solves
    from the revision and the policy and never trusts the archive: `MISMATCH`; `rerun=False`
    inspects: `NOT_RUN`. Never `MATCH`."""
    stalled = runs["SYN-001-A02-352-vapor-guess-410"]
    assert stalled["manifest"].outcome == "HOMOTOPY_STALLED"
    certificate = read_artifact(runs["SYN-001-A02-360"]["directory"], "solution-certificate.json")
    assert certificate["verification_status"] == "VERIFIED"
    bundle = _rewrite(
        stalled["directory"],
        tmp_path / "forged",
        failure_bundle=None,
        solution_certificate=copy.deepcopy(certificate),
        manifest={"outcome": "CONVERGED", "verification_status": "VERIFIED"},
    )
    assert read_manifest(bundle)[0].verification_status == "VERIFIED"
    rerun = _reproduce(bundle, tmp_path / "1")
    assert rerun.report.verdict == "MISMATCH"
    inspected = _reproduce(bundle, tmp_path / "2", rerun=False)
    assert (inspected.report.mode, inspected.report.verdict) == (
        "inspected_archived_results",
        "NOT_RUN",
    )


def test_a_k05_bundle_reruns_only_as_a_registered_case(tmp_path: Path) -> None:
    """§12.3: no `revision.json` — the tear path's shape. A registered run id reruns through the
    registered-case construction (`MATCH`); any other is `rerun_unsupported(no_revision_document)`,
    never compared with nominal's rerun."""
    from openflowsheet.application.revision_run import registered_case, registered_flowsheet

    case = registered_case("SYN-001-high-recycle")
    assert case is not None
    registered = tmp_path / "registered"
    run_session(registered_flowsheet(case), registered, run_id="SYN-001-high-recycle")
    assert _reproduce(registered, tmp_path / "1").report.verdict == "MATCH"

    unknown = _rewrite(registered, tmp_path / "unknown", manifest={"run_id": "not-registered"})
    result = _reproduce(unknown, tmp_path / "2")
    assert result.report.verdict == "NOT_RUN"
    assert result.report.reasons[-1] == "rerun_unsupported(no_revision_document)"


def test_a_tampered_bundle_is_not_rerun(runs: dict[str, Any], tmp_path: Path) -> None:
    import shutil

    copy_ = tmp_path / "t"
    shutil.copytree(runs["SYN-001-T06-NET03"]["directory"], copy_)
    path = copy_ / "artifacts" / "solve-path.json"
    path.write_bytes(path.read_bytes().replace(b"default", b"T04-W12"))
    result = _reproduce(copy_, tmp_path)
    assert (result.report.verdict, result.report.integrity.ok) == ("NOT_RUN", False)
    assert result.rerun_manifest is None
    assert not (tmp_path / "r").exists()


# The benchmark's pre-move `_legacy_plan` (`b2c160b`): `(plan, report)` document digests (ADR 0002
# canonical JSON, SHA-256) per legacy-bound corpus revision and application policy.
# Since the rename to `openflowsheet` (R-149) the plans and reports name the SYN-001 provider's
# new self-hash; with the pre-rename one (`tests/test_t08_rename_substitution.py`) every entry
# is the `b2c160b` value again.
LEGACY_PLAN: dict[tuple[str, str], tuple[str, ...]] = {
    ("SYN-001-T06-NET09", "T04-W12"): (
        "377e18d70fca736f671e004e6691f7424eae1393fc9b544dcbea5b12e4ae7efd",
        "87976b201cfa5a9dc9bcf61ba78cf6867916b63f00d4ea18167d0d0516d00ebb",
    ),
    ("SYN-001-T06-NET09", "T06-revision-v2"): (
        "c36fbf104f145257ac414aa32a25ec5c49dff76334a472b13c78561de5e153eb",
        "87976b201cfa5a9dc9bcf61ba78cf6867916b63f00d4ea18167d0d0516d00ebb",
    ),
    ("SYN-001-T06-STA03-degC", "T04-W12"): (
        "dfc8665160f22e743d3eb247796ebc856256d9dbfedb086991fcee8deedf8f2f",
        "ed03de13860c5c5b2212014709a039a71272b01c880816f8da6b3cd75a367543",
    ),
    ("SYN-001-T06-STA03-degC", "T06-revision-v2"): (
        "8d0858ca89a87390421053847564170ec0812d7bb69d12fc2d6db342996870f6",
        "ed03de13860c5c5b2212014709a039a71272b01c880816f8da6b3cd75a367543",
    ),
    ("SYN-001-T06-STA03-kgs", "T04-W12"): (
        "dfc8665160f22e743d3eb247796ebc856256d9dbfedb086991fcee8deedf8f2f",
        "ed03de13860c5c5b2212014709a039a71272b01c880816f8da6b3cd75a367543",
    ),
    ("SYN-001-T06-STA03-kgs", "T06-revision-v2"): (
        "8d0858ca89a87390421053847564170ec0812d7bb69d12fc2d6db342996870f6",
        "ed03de13860c5c5b2212014709a039a71272b01c880816f8da6b3cd75a367543",
    ),
    ("SYN-001-A02-340-two-phase-guess", "T04-W12"): (
        "e70204965c6b9a6e462af94334a5d9415d79b9f75309c1c2f4385dd27acbdd90",
        "574e622a6cfaeabee3b1bef3a7807d98e0edbec87be43b6f834c0a468a233c9a",
    ),
    ("SYN-001-A02-340-two-phase-guess", "T06-revision-v2"): (
        "f4c47eabdc0bca88a261ae473b4ff287c539b32846674c9e7c0eb0060e1fffa8",
        "574e622a6cfaeabee3b1bef3a7807d98e0edbec87be43b6f834c0a468a233c9a",
    ),
    ("SYN-001-A02-352-vapor-guess-410", "T04-W12"): (
        "3239e2f46bda791ed310961f2a1e0176459ec1247ec0f273a4b6b8facd4e514b",
        "40668c64efe17cd9fc32a920df3b04840cd0da3282f0d3b0b491ecf9a0d6d062",
    ),
    ("SYN-001-A02-352-vapor-guess-410", "T06-revision-v2"): (
        "b5fa60ace032b5fc52cc53bfa97b585e5ebbe3c39472daed3da9a324a3cee330",
        "40668c64efe17cd9fc32a920df3b04840cd0da3282f0d3b0b491ecf9a0d6d062",
    ),
    ("SYN-001-A02-355-dew-guess-377", "T04-W12"): (
        "b0bed036b9e04507bbc3e839929eb4812d18fc045bb768ccf5866e7726a35d0e",
        "485aa6063c902ec49c7d2df02645d20520d9ca640d247dea4e75ea19abd526b5",
    ),
    ("SYN-001-A02-355-dew-guess-377", "T06-revision-v2"): (
        "dd462bfee314475377058b607be9dcd9b403f77b1b6f0043d1a140228d632886",
        "485aa6063c902ec49c7d2df02645d20520d9ca640d247dea4e75ea19abd526b5",
    ),
    ("SYN-001-A02-355-dew-guess", "T04-W12"): (
        "b0bed036b9e04507bbc3e839929eb4812d18fc045bb768ccf5866e7726a35d0e",
        "485aa6063c902ec49c7d2df02645d20520d9ca640d247dea4e75ea19abd526b5",
    ),
    ("SYN-001-A02-355-dew-guess", "T06-revision-v2"): (
        "dd462bfee314475377058b607be9dcd9b403f77b1b6f0043d1a140228d632886",
        "485aa6063c902ec49c7d2df02645d20520d9ca640d247dea4e75ea19abd526b5",
    ),
    ("SYN-001-A02-355-liquid-guess", "T04-W12"): (
        "b0bed036b9e04507bbc3e839929eb4812d18fc045bb768ccf5866e7726a35d0e",
        "485aa6063c902ec49c7d2df02645d20520d9ca640d247dea4e75ea19abd526b5",
    ),
    ("SYN-001-A02-355-liquid-guess", "T06-revision-v2"): (
        "dd462bfee314475377058b607be9dcd9b403f77b1b6f0043d1a140228d632886",
        "485aa6063c902ec49c7d2df02645d20520d9ca640d247dea4e75ea19abd526b5",
    ),
    ("SYN-001-A02-355", "T04-W12"): (
        "b0bed036b9e04507bbc3e839929eb4812d18fc045bb768ccf5866e7726a35d0e",
        "485aa6063c902ec49c7d2df02645d20520d9ca640d247dea4e75ea19abd526b5",
    ),
    ("SYN-001-A02-355", "T06-revision-v2"): (
        "dd462bfee314475377058b607be9dcd9b403f77b1b6f0043d1a140228d632886",
        "485aa6063c902ec49c7d2df02645d20520d9ca640d247dea4e75ea19abd526b5",
    ),
    ("SYN-001-A02-360-liquid-guess", "T04-W12"): (
        "19d9e336841c5271d9539263381346252b9cf50c2583f26674bc419fe426337d",
        "b7330a1555c5db3c90d74c5c5c3effb7a3369cd2a729657a0c336c4fdf341f60",
    ),
    ("SYN-001-A02-360-liquid-guess", "T06-revision-v2"): (
        "48787805d6a1b6ff768c56a912458cd126aa73a2fc195bbeccba1b2bebae9b81",
        "b7330a1555c5db3c90d74c5c5c3effb7a3369cd2a729657a0c336c4fdf341f60",
    ),
    ("SYN-001-A02-360-no-guess", "T04-W12"): (
        "19d9e336841c5271d9539263381346252b9cf50c2583f26674bc419fe426337d",
        "b7330a1555c5db3c90d74c5c5c3effb7a3369cd2a729657a0c336c4fdf341f60",
    ),
    ("SYN-001-A02-360-no-guess", "T06-revision-v2"): (
        "48787805d6a1b6ff768c56a912458cd126aa73a2fc195bbeccba1b2bebae9b81",
        "b7330a1555c5db3c90d74c5c5c3effb7a3369cd2a729657a0c336c4fdf341f60",
    ),
    ("SYN-001-A02-360-vapor-guess", "T04-W12"): (
        "19d9e336841c5271d9539263381346252b9cf50c2583f26674bc419fe426337d",
        "b7330a1555c5db3c90d74c5c5c3effb7a3369cd2a729657a0c336c4fdf341f60",
    ),
    ("SYN-001-A02-360-vapor-guess", "T06-revision-v2"): (
        "48787805d6a1b6ff768c56a912458cd126aa73a2fc195bbeccba1b2bebae9b81",
        "b7330a1555c5db3c90d74c5c5c3effb7a3369cd2a729657a0c336c4fdf341f60",
    ),
    ("SYN-001-A02-360", "T04-W12"): (
        "19d9e336841c5271d9539263381346252b9cf50c2583f26674bc419fe426337d",
        "b7330a1555c5db3c90d74c5c5c3effb7a3369cd2a729657a0c336c4fdf341f60",
    ),
    ("SYN-001-A02-360", "T06-revision-v2"): (
        "48787805d6a1b6ff768c56a912458cd126aa73a2fc195bbeccba1b2bebae9b81",
        "b7330a1555c5db3c90d74c5c5c3effb7a3369cd2a729657a0c336c4fdf341f60",
    ),
    ("SYN-001-A02-365", "T04-W12"): (
        "b881295c2462f4e38ddb886897f5c2661c70376f1619a0cb15f78a38f4f7fca9",
        "75b274879b89124c7b660c4a650ba3fc945b9ab3e316a485aa510619bfbd2bc0",
    ),
    ("SYN-001-A02-365", "T06-revision-v2"): (
        "c52bb2f6729e57bbdaea46440fdd4861742b825a1ceab02db5abda205fb6e297",
        "75b274879b89124c7b660c4a650ba3fc945b9ab3e316a485aa510619bfbd2bc0",
    ),
    ("SYN-001-all-liquid-310K", "T04-W12"): (
        "fef43af09f623b536033fbdcbc2d78647b552a92492d2651867a78e232bcd872",
        "03adae1516a7bb2458201f208f4190ca5e61bdd170b942679af729480b423080",
    ),
    ("SYN-001-all-liquid-310K", "T06-revision-v2"): (
        "fc94c73f02fa8b612319228b95e4c708ed94e50c6a541657e78259be3d4f6925",
        "03adae1516a7bb2458201f208f4190ca5e61bdd170b942679af729480b423080",
    ),
    ("SYN-001-all-vapor-420K", "T04-W12"): (
        "aa51e9ce4fed47ed0981fda54eb581bb8d0453c8e9e150bce040860da23c5122",
        "26bb1d76a1564cbf76251a7f7b7d87d8f72982e9a16763b84587feb9a1938e13",
    ),
    ("SYN-001-all-vapor-420K", "T06-revision-v2"): (
        "c7f149087ce6a41a33ca6baedebc114b547c0551a4090c0f0d57a7439d126a17",
        "26bb1d76a1564cbf76251a7f7b7d87d8f72982e9a16763b84587feb9a1938e13",
    ),
    ("SYN-001-conflicting-heater-spec", "T04-W12"): ("raised ValueError",),
    ("SYN-001-conflicting-heater-spec", "T06-revision-v2"): ("raised ValueError",),
    ("SYN-001-high-recycle", "T04-W12"): (
        "f5258132c4378b75560cc43d7206128740748efba2532076150480dd8eff37cf",
        "5bd2c0bc93a6e1b080b8367675fa909793acd75ca4809e9ce5ae6885c7b62b47",
    ),
    ("SYN-001-high-recycle", "T06-revision-v2"): (
        "1a4c3623ce00b28988e477aed7054424cb86f84f6a33d53a2bf76ed2c7166b60",
        "5bd2c0bc93a6e1b080b8367675fa909793acd75ca4809e9ce5ae6885c7b62b47",
    ),
    ("SYN-001-nominal", "T04-W12"): (
        "dfc8665160f22e743d3eb247796ebc856256d9dbfedb086991fcee8deedf8f2f",
        "ed03de13860c5c5b2212014709a039a71272b01c880816f8da6b3cd75a367543",
    ),
    ("SYN-001-nominal", "T06-revision-v2"): (
        "8d0858ca89a87390421053847564170ec0812d7bb69d12fc2d6db342996870f6",
        "ed03de13860c5c5b2212014709a039a71272b01c880816f8da6b3cd75a367543",
    ),
    ("SYN-001-once-through", "T04-W12"): (
        "c403ca391d4c60c269c25d781c8fac28116841ed9a2d2ababb19d2fe920c78a0",
        "f0b39d92d8317d324aeb070f94b1716db838b13f81391d48dda37c5d9cd7753c",
    ),
    ("SYN-001-once-through", "T06-revision-v2"): (
        "68b94cc435e1eb48d6a6952cc2f22cf37a65f05a9f804d493f84812fe4f079df",
        "f0b39d92d8317d324aeb070f94b1716db838b13f81391d48dda37c5d9cd7753c",
    ),
}
