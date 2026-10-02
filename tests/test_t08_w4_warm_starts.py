"""T08 W4: compatible warm starts (ADR 0024; T08 build-first spec Part B, assertions B40–B49).

The registered states are §B5's:

- **source** — `SYN-001-nominal` (the T06/T07 corpus), committed and solved under `default`;
- **target** — a child of the source that changes only the splitter's recycle fraction, 0.5 →
  0.95 (both places it is declared: the instance parameter and `SPEC-splitter-r`), P01's
  high-recycle state; solved under `T08-warm-v1` and under `default` (it certifies cold on the
  revision path, measured: `CONVERGED`, `VERIFIED`);
- **incompatible** — a later child that renames the flash instance, so the ids change;
- **tampered** — the selected source's stored `solution-state.json` with one value altered;
- **evaluation** and **projection** — constructed candidates passed to `execute_plan` (B45, B46).

Everything runs through `LocalApplication` under the inline executor except B45 and B46, as §B5
says; B41's reference opening also runs through `execute_plan`, in the same process. B41, B42 and
B46 are the build-first spec's Amendment 1 rows (§Am1.C; Q-W4-1 §Am1.4, Q-W4-2 §Am1.5, R-127): a
warm opening is T05b §6.2's projection of the candidate, compared with a `user_start` opening of
the same values; plans are compared modulo the policy (normalization N).
"""

from __future__ import annotations

import copy
import dataclasses
import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml
from t06_support import ALLOWANCE, worst_ratio
from t07_corpus import CORPUS
from t07_jobs_support import commit

from openflowsheet.application.local import LocalApplication
from openflowsheet.application.policies import (
    APPLICATION_POLICIES,
    T06_REVISION_V2,
    T08_WARM_V1,
)
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.application.store import ProjectStore
from openflowsheet.application.types import JobRequest, ReplayPolicy, SolveBody
from openflowsheet.orchestrator import region as region_module
from openflowsheet.orchestrator import revision
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import PlanResult, execute_plan
from openflowsheet.orchestrator.phase_contract import (
    OpeningRefusal,
    OpeningRequirement,
    OpeningState,
)
from openflowsheet.orchestrator.region import RegionResult
from openflowsheet.orchestrator.splits import lifted_splits
from openflowsheet.orchestrator.warm_start import WarmStartCandidate
from openflowsheet.run import solution_state
from openflowsheet.run.bundle import MANIFEST_NAME
from openflowsheet.run.identity import r0_projection
from openflowsheet.run.manifest import policy_sha256
from openflowsheet.verify.checks import KIND_TOLERANCE

#: The members `run_revision_session` writes under `artifacts/`.
Artifacts = dict[str, Any]
WARM = "T08-warm-v1"


# -- the registered states (§B5) ------------------------------------------------------------------


def _child(recycle: float) -> dict[str, Any]:
    """The source with only the recycle fraction changed, in both places it is declared."""
    document = CORPUS["SYN-001-nominal"]()
    document.pop("revision_id", None)
    (splitter,) = [item for item in document["instances"] if item["id"] == "splitter"]
    splitter["parameters"]["split_fraction"]["value"] = recycle
    (spec,) = [item for item in document["specifications"] if item["id"] == "SPEC-splitter-r"]
    spec["value"] = recycle
    return document


def _renamed(document: dict[str, Any], old: str, new: str) -> dict[str, Any]:
    """`document` with the instance `old` renamed `new` wherever an id refers to it (its `id`,
    a port's `instance`, a specification's `object_id`); its `semantic_role` is unchanged."""
    renamed = copy.deepcopy(document)

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key in ("instance", "object_id"):
                if node.get(key) == old:
                    node[key] = new
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for instance in renamed["instances"]:
        if instance["id"] == old:
            instance["id"] = new
    walk(renamed)
    return renamed


@dataclass(frozen=True)
class Solved:
    """One solve job's result and its bundle's artifacts, read back from disk."""

    job_id: str
    outcome: str | None
    verdict: str | None
    directory: Path
    artifacts: Artifacts

    @property
    def warm_start(self) -> dict[str, Any] | None:
        member: dict[str, Any] | None = self.artifacts["solve-path.json"].get("warm_start")
        return member

    @property
    def events(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = self.artifacts["solve-events.json"]
        return events

    def messages(self, kind: str) -> list[str]:
        return [event["message"] for event in self.events if event["kind"] == kind]


def _read(directory: Path) -> Artifacts:
    return {
        path.name: json.loads(path.read_bytes())
        for path in sorted((directory / "artifacts").iterdir())
    }


def _solve(app: LocalApplication, revision_id: str, policy_id: str, **body: Any) -> Solved:
    request = JobRequest(
        "solve",
        f"t08-w4-{revision_id}-{policy_id}-{len(app.list_jobs(limit=200).items)}",
        SolveBody(revision_id, policy_id=policy_id, **body),
    )
    job = app.submit_job(request).job
    assert job.status == "completed", (job.status, job.error)
    result = app.get_job_result(job.job_id).run_result
    assert result is not None
    directory = app.files_root / "jobs" / job.job_id / "bundle"
    return Solved(
        job.job_id, result.outcome, result.verification_status, directory, _read(directory)
    )


@dataclass(frozen=True)
class Project:
    app: LocalApplication
    source_revision: str
    target_revision: str
    incompatible_revision: str
    source: Solved
    warm: Solved
    cold: Solved
    incompatible: Solved
    incompatible_default: Solved


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Project]:
    with LocalApplication.create(
        tmp_path_factory.mktemp("t08w4") / "p", project_id="t08-w4"
    ) as app:
        source_revision = commit(app, CORPUS["SYN-001-nominal"]())
        source = _solve(app, source_revision, "default")
        target_revision = commit(app, _child(0.95))
        warm = _solve(app, target_revision, WARM)
        cold = _solve(app, target_revision, "default")
        incompatible_revision = commit(app, _renamed(_child(0.95), "flash", "flash_b"))
        incompatible = _solve(app, incompatible_revision, WARM)
        incompatible_default = _solve(app, incompatible_revision, "default")
        yield Project(
            app,
            source_revision,
            target_revision,
            incompatible_revision,
            source,
            warm,
            cold,
            incompatible,
            incompatible_default,
        )


# -- the policy (ADR 0024 D1) ---------------------------------------------------------------------


def test_t08_warm_v1_is_t06_revision_v2_with_only_the_chain_changed() -> None:
    assert APPLICATION_POLICIES[WARM] is T08_WARM_V1
    assert T08_WARM_V1.initializer_chain == ("compatible_warm_start", "traversal-G0-v1")
    document, registered = T08_WARM_V1.as_document(), T06_REVISION_V2.as_document()
    assert {key for key in document if document[key] != registered[key]} == {
        "policy_id",
        "initializer_chain",
    }
    # Every other policy the contract offers keeps an empty chain (B49).
    assert [p for p in APPLICATION_POLICIES.values() if p.initializer_chain] == [T08_WARM_V1]
    # A regression pin of the new policy's hash, measured at this commit.
    assert policy_sha256(T08_WARM_V1) == T08_WARM_V1_SHA256


T08_WARM_V1_SHA256 = "32f484a150f61e2f62357e62c7daa4b4c1c450788abce1967da938fe7ad55795"


# -- B40: absent ----------------------------------------------------------------------------------


def test_b40_absent_in_a_fresh_project(tmp_path: Path) -> None:
    with LocalApplication.create(tmp_path / "fresh", project_id="t08-w4-b40") as app:
        revision_id = commit(app, CORPUS["SYN-001-nominal"]())
        warm = _solve(app, revision_id, WARM)
        cold = _solve(app, revision_id, "default")
    assert warm.warm_start is not None and warm.warm_start["status"] == "absent"
    assert warm.warm_start == {
        "record": "warm-start-v1",
        "selection": "store-latest-verified-lineage-v1",
        "status": "absent",
        "reason": None,
        "source_job_id": None,
        "source_revision_id": None,
        "candidate": None,
        "projections": [],
    }
    assert warm.messages("initializer_candidate") == ["compatible_warm_start(absent)"]
    assert warm.messages("initializer_accepted") == []
    assert warm.messages("initializer_rejected") == []
    # The final state bitwise equal to the same process's default run; same verdict and checks.
    assert warm.artifacts["solution-state.json"] == cold.artifacts["solution-state.json"]
    assert (warm.outcome, warm.verdict) == (cold.outcome, cold.verdict) == ("CONVERGED", "VERIFIED")
    assert _check_ids(warm) == _check_ids(cold)
    assert cold.warm_start is None


def _check_ids(solved: Solved) -> list[str]:
    return [check["id"] for check in solved.artifacts["solution-certificate.json"]["checks"]]


# -- B41: accepted --------------------------------------------------------------------------------


def test_b41_the_target_opens_from_the_source(project: Project) -> None:
    warm = project.warm
    assert warm.warm_start is not None
    assert (warm.warm_start["status"], warm.warm_start["reason"]) == ("accepted", None)
    assert warm.warm_start["source_job_id"] == project.source.job_id
    assert warm.warm_start["source_revision_id"] == project.source_revision
    assert warm.warm_start["candidate"] == project.source.artifacts["solution-state.json"]
    assert warm.warm_start["projections"] == []
    initializer = [e for e in warm.events if e["kind"].startswith("initializer_")]
    assert [(e["kind"], e["message"]) for e in initializer] == [
        ("initializer_candidate", "compatible_warm_start(present)"),
        ("initializer_accepted", "compatible_warm_start"),
    ]
    kinds = [event["kind"] for event in warm.events]
    assert kinds.index("initializer_accepted") < kinds.index("attempt_opened")
    certificate = warm.artifacts["solution-certificate.json"]
    assert certificate["branch_provenance"][0]["initializer_source"] == "compatible_warm_start"
    assert (warm.outcome, warm.verdict) == ("CONVERGED", "VERIFIED")


def test_b41_the_first_opening_is_a_user_start_opening_of_the_candidate(project: Project) -> None:
    """§Am1.C B41 (Q-W4-1): the warm start enters where `user_start` enters, so its opening is
    T05b §6.2's projection of the candidate. The first `attempt_opened` digest equals that of the
    same target region under `T08-warm-v1` opened by `execute_plan(user_start=<the candidate's
    values>)` in this process; §6.2 recorded no projection (its own threshold, 1e-12)."""
    warm = project.warm
    opened = next(event for event in warm.events if event["kind"] == "attempt_opened")
    values = project.source.artifacts["solution-state.json"]["variables"]
    binding = _binding(warm.artifacts["revision.json"])
    plan, _ = revision.plan_revision(binding, T08_WARM_V1)
    assert isinstance(plan, ExecutionPlan)
    user = execute_plan(
        plan=plan,
        flowsheet=binding.flowsheet,
        spec=binding.spec,
        policy=T08_WARM_V1,
        user_start={name: values[name] for name in binding.spec.variable_ids},
    )
    region = user.steps[-1].detail
    assert isinstance(region, RegionResult)
    assert region.branch_provenance[0]["initializer_source"] == "user_guess"
    user_opened = next(e for e in user.trace.events if e.kind == "attempt_opened")
    assert opened["state_sha256"] == user_opened.state_sha256
    assert opened["signature"] == [list(entry) for entry in user_opened.signature]
    assert not [m for m in warm.messages("initializer_candidate") if m.startswith("projected(")]
    assert (warm.outcome, warm.verdict) == ("CONVERGED", "VERIFIED")
    assert warm.warm_start is not None
    assert warm.warm_start["source_job_id"] == project.source.job_id


# -- B42: never changes the problem ---------------------------------------------------------------


def _manifest(solved: Solved) -> dict[str, Any]:
    manifest: dict[str, Any] = json.loads((solved.directory / MANIFEST_NAME).read_bytes())
    return manifest


def test_b42_the_warm_start_changes_the_start_and_not_the_problem(project: Project) -> None:
    warm, cold = project.warm, project.cold
    assert warm.artifacts["revision.json"] == cold.artifacts["revision.json"]
    warm_manifest, cold_manifest = _manifest(warm), _manifest(cold)
    for key in ("constants_sha256", "model_version", "check_policy_sha256"):
        assert warm_manifest[key] == cold_manifest[key], key
    assert _check_ids(warm) == _check_ids(cold)
    assert (warm.verdict, cold.verdict) == ("VERIFIED", "VERIFIED")
    warm_state = warm.artifacts["solution-state.json"]["variables"]
    cold_state = cold.artifacts["solution-state.json"]["variables"]
    assert set(warm_state) == set(cold_state)
    # ADR 0007 D2: 1e-9 relative (floor 1e-300 absolute at an exact zero).
    for name, value in cold_state.items():
        assert abs(warm_state[name] - value) <= 1e-9 * max(abs(value), 1e-300), name
    # Both within T02 §6.4's allowance of P01's high-recycle root (SYN-001 §5).
    expected = _p01_high_recycle()
    for state in (warm_state, cold_state):
        ratio, where = worst_ratio(state, expected)
        assert ratio <= 1.0, (where, ratio)


def _normalized(document: Any, warm_policy: str, cold_policy: str) -> Any:
    """§Am1.5's N: every string with the warm run's policy id replaced by the cold run's, and every
    member named `initializer_chain` removed."""
    if isinstance(document, dict):
        return {
            key: _normalized(value, warm_policy, cold_policy)
            for key, value in document.items()
            if key != "initializer_chain"
        }
    if isinstance(document, list):
        return [_normalized(item, warm_policy, cold_policy) for item in document]
    if isinstance(document, str):
        return document.replace(warm_policy, cold_policy)
    return document


def test_b42_the_plans_are_equal_modulo_the_policy(project: Project) -> None:
    """§Am1.C B42 (Q-W4-2): the bundles' `execution-plan.json` are equal under N, exactly, and
    each run's `plan_id` — the execution plan's, which its manifest records — ends
    `-<its policy_id>-execution` (`execution.py:776`). The solve plans inside carry their own
    ids (`…-<policy_id>-region<k>`); N covers them."""
    warm_policy, cold_policy = (
        _manifest(project.warm)["policy_id"],
        _manifest(project.cold)["policy_id"],
    )
    assert (warm_policy, cold_policy) == (WARM, "T06-revision-v2")
    warm_plan = project.warm.artifacts["execution-plan.json"]
    cold_plan = project.cold.artifacts["execution-plan.json"]
    assert warm_plan != cold_plan
    assert _normalized(warm_plan, warm_policy, cold_policy) == _normalized(
        cold_plan, warm_policy, cold_policy
    )
    for solved, plan, policy_id in (
        (project.warm, warm_plan, warm_policy),
        (project.cold, cold_plan, cold_policy),
    ):
        assert plan["plan_id"] == _manifest(solved)["plan_id"]
        assert plan["plan_id"].endswith(f"-{policy_id}-execution"), plan["plan_id"]


def _p01_high_recycle() -> dict[str, tuple[Decimal, float]]:
    """P01's high-recycle root (`benchmarks/syn001/reference_values.yaml`) on the revision's
    columns: S1 fresh feed, S2 mixer outlet, S3 heater outlet, S4 vapour product, S5 flash
    liquid, S6 recycle, S7 purge; duties; the flash split's totals."""
    (case,) = [
        entry
        for entry in load_yaml(REPO_ROOT / "benchmarks" / "syn001" / "reference_values.yaml")[
            "variants"
        ]
        if entry["case_id"] == "SYN-001-high-recycle"
    ]
    streams = {
        "S2": (case["mixed_feed_mol_per_s"], case["T_mix_K"]),
        "S3": (case["mixed_feed_mol_per_s"], case["T_heater_K"]),
        "S4": (case["vapor_product_mol_per_s"], case["T_flash_K"]),
        "S6": (case["recycle_mol_per_s"], case["T_flash_K"]),
        "S7": (case["purge_mol_per_s"], case["T_flash_K"]),
    }
    out: dict[str, tuple[Decimal, float]] = {}
    for stream, (flows, temperature) in streams.items():
        for component, value in zip("ABC", flows, strict=True):
            out[f"{stream}.n.{component}"] = (Decimal(value), ALLOWANCE["n"])
        out[f"{stream}.T"] = (Decimal(temperature), ALLOWANCE["T"])
        out[f"{stream}.P"] = (Decimal(case["P_Pa"]), ALLOWANCE["P"])
    out["heater.Q"] = (Decimal(case["Q_heater_W"]), ALLOWANCE["Q"])
    out["flash.Q"] = (Decimal(case["Q_flash_W"]), ALLOWANCE["Q"])
    out["S4.N"] = (Decimal(case["V_mol_per_s"]), ALLOWANCE["n"])
    out["S5.N"] = (Decimal(case["L_mol_per_s"]), ALLOWANCE["n"])
    return out


# -- B43: incompatible ----------------------------------------------------------------------------


def test_b43_an_incompatible_candidate_is_rejected_to_the_traversal(project: Project) -> None:
    run, default = project.incompatible, project.incompatible_default
    assert run.warm_start is not None
    assert (run.warm_start["status"], run.warm_start["reason"]) == ("rejected", "compatibility")
    # The latest VERIFIED state of the lineage is the target's cold run.
    assert run.warm_start["source_job_id"] == project.cold.job_id
    initializer = [(e["kind"], e["message"]) for e in run.events if e["kind"].startswith("init")]
    assert initializer == [
        ("initializer_candidate", "compatible_warm_start(present)"),
        ("initializer_rejected", "warm_start_rejected(compatibility)"),
    ]
    certificate = run.artifacts["solution-certificate.json"]
    assert certificate["branch_provenance"][0]["initializer_source"] == "traversal-G0-v1"
    # Equal to the same revision's default run but for policy id, events and the member.
    assert set(run.artifacts) == set(default.artifacts)
    for name in sorted(run.artifacts):
        if name in ("solve-events.json", "solve-policy.json"):
            continue
        ours, theirs = (
            _without_policy(run.artifacts[name]),
            _without_policy(default.artifacts[name]),
        )
        if name == "solve-path.json":
            ours.pop("warm_start")
            ours.pop("policy_requested")
            theirs.pop("policy_requested")
        assert ours == theirs, name
    assert _kinds(run.events, drop_initializer=True) == _kinds(default.events)


def _without_policy(document: Any) -> Any:
    """`document` with the policy id spelled as a placeholder wherever it appears in a string —
    the plan id embeds it (`execution.py:776`)."""
    text = json.dumps(document).replace(WARM, "<policy>").replace("T06-revision-v2", "<policy>")
    return json.loads(text)


def _kinds(events: list[dict[str, Any]], *, drop_initializer: bool = False) -> list[str]:
    return [
        event["kind"]
        for event in events
        if not (drop_initializer and event["kind"].startswith("initializer_"))
    ]


# -- B44: integrity -------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def tampered(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[Solved, Solved]]:
    """A source whose stored `solution-state.json` has one value altered (its digest left), and
    the target solved under `T08-warm-v1` after it."""
    with LocalApplication.create(
        tmp_path_factory.mktemp("t08w4-b44") / "p", project_id="t08-w4-b44"
    ) as app:
        source = _solve(app, commit(app, CORPUS["SYN-001-nominal"]()), "default")
        path = source.directory / "artifacts" / solution_state.NAME
        document = json.loads(path.read_bytes())
        document["variables"]["S2.T"] = document["variables"]["S2.T"] + 1.0
        path.write_text(json.dumps(document), encoding="utf-8")
        run = _solve(app, commit(app, _child(0.95)), WARM)
        yield source, run


def test_b44_a_tampered_candidate_is_rejected_for_integrity(
    tampered: tuple[Solved, Solved],
) -> None:
    source, run = tampered
    assert run.warm_start is not None
    assert (run.warm_start["status"], run.warm_start["reason"]) == ("rejected", "integrity")
    assert run.warm_start["source_job_id"] == source.job_id
    assert run.messages("initializer_rejected") == ["warm_start_rejected(integrity)"]
    certificate = run.artifacts["solution-certificate.json"]
    assert certificate["branch_provenance"][0]["initializer_source"] == "traversal-G0-v1"
    # Not failed by it.
    assert (run.outcome, run.verdict) == ("CONVERGED", "VERIFIED")


# -- B45, B46: constructed candidates through `execute_plan` ---------------------------------------


def _binding(document: dict[str, Any]) -> RevisionBinding:
    binding = bind_revision_flowsheet(document)
    assert isinstance(binding, RevisionBinding)
    return binding


def _source_state() -> dict[str, float]:
    binding = _binding(CORPUS["SYN-001-nominal"]())
    run = _plan_run(binding, T06_REVISION_V2)
    assert run.outcome == "CONVERGED" and run.state is not None
    return dict(run.state)


def _plan_run(
    binding: RevisionBinding, policy: Any, warm_start: WarmStartCandidate | None = None
) -> PlanResult:
    plan, _ = revision.plan_revision(binding, policy)
    assert isinstance(plan, ExecutionPlan)
    return execute_plan(
        plan=plan,
        flowsheet=binding.flowsheet,
        spec=binding.spec,
        policy=policy,
        warm_start=warm_start,
    )


def _constructed(edit: Callable[[dict[str, float]], None]) -> WarmStartCandidate:
    """The source's state edited, with a consistent digest (`solution_state.document`)."""
    binding = _binding(CORPUS["SYN-001-nominal"]())
    values = _source_state()
    edit(values)
    ids = binding.spec.variable_ids
    document = solution_state.document(ids, [values[name] for name in ids])
    return WarmStartCandidate(document, "constructed", "constructed")


def _initializer(run: PlanResult) -> list[tuple[str, str]]:
    return [
        (event.kind, event.message)
        for event in run.trace.events
        if event.kind.startswith("initializer_")
    ]


def test_b45_a_candidate_outside_the_provider_domain_is_rejected() -> None:
    candidate = _constructed(lambda values: values.__setitem__("S2.T", 450.0))
    run = _plan_run(_binding(_child(0.95)), T08_WARM_V1, candidate)
    assert run.warm_start is not None
    assert (run.warm_start.status, run.warm_start.reason) == ("rejected", "evaluation")
    assert _initializer(run) == [
        ("initializer_candidate", "compatible_warm_start(present)"),
        ("initializer_rejected", "warm_start_rejected(evaluation)"),
    ]
    region = run.steps[-1].detail
    assert isinstance(region, RegionResult)
    assert region.branch_provenance[0]["initializer_source"] == "traversal-G0-v1"
    assert run.outcome == "CONVERGED"


def test_b46_a_negative_flow_is_projected_and_accepted() -> None:
    """§Am1.C B46: `<id>` is a flow column T05b §6.2 does not lift (else the opening coordinate
    would be the kernel's value, not `0.0`)."""
    target = _binding(_child(0.95))
    lifted = {
        name
        for split in lifted_splits(
            revision.instances_of(target.flowsheet), target.flowsheet.components
        )
        for name in (*split.vapor, *split.liquid, split.vapor_total, split.liquid_total)
    }
    assert "S7.n.A" in target.spec.variable_ids and "S7.n.A" not in lifted
    candidate = _constructed(lambda values: values.__setitem__("S7.n.A", -1e-12))
    run = _plan_run(target, T08_WARM_V1, candidate)
    assert run.warm_start is not None
    assert run.warm_start.status == "accepted"
    assert run.warm_start.as_document()["projections"] == [["S7.n.A", -1e-12, 0.0]]
    region = run.steps[-1].detail
    assert isinstance(region, RegionResult)
    assert region.branch_provenance[0]["initializer_source"] == "compatible_warm_start"
    assert region.opening is not None
    opening_value = region.opening[0]["S7.n.A"]
    assert opening_value == 0.0 and str(opening_value) == "0.0"
    assert run.outcome == "CONVERGED"


def _kernel_refused(state: Any) -> RegionResult:
    raise region_module._KernelRefusedError("S3", "error", "refused at the candidate")


def _not_settled(state: Any) -> RegionResult:
    return RegionResult(
        outcome="ACTIVE_SET_CYCLING",
        state=dict(state),
        attempts=(),
        message="opening_not_settled(U-FLASH)",
    )


@pytest.mark.parametrize(
    ("refusal", "outcome"),
    [(_kernel_refused, "EVALUATION_ERROR"), (_not_settled, "ACTIVE_SET_CYCLING")],
)
def test_a_warm_opening_that_ends_before_an_attempt_falls_through(
    monkeypatch: pytest.MonkeyPatch, refusal: Callable[[Any], RegionResult], outcome: str
) -> None:
    """Review S4 (§B2, "the run never fails because of the warm start"): a candidate that passes
    `integrity`, `compatibility` and `evaluation`, but whose region solve ends before any attempt
    other than by the opening check — §6.2's kernel refusal (`region.py`, `_KernelRefusedError`),
    or an opening that does not settle (§7.8 (ii)) — is rejected `opening:<outcome>`, and the
    traversal follows. The refusal is monkeypatched at the warm solve only."""
    original = region_module._solve_region

    def refusing(**kwargs: Any) -> RegionResult:
        if kwargs["warm_start"]:
            return refusal(kwargs["state"])
        result: RegionResult = original(**kwargs)
        return result

    monkeypatch.setattr(region_module, "_solve_region", refusing)
    run = _plan_run(_binding(_child(0.95)), T08_WARM_V1, _constructed(lambda values: None))
    assert run.warm_start is not None
    assert (run.warm_start.status, run.warm_start.reason) == ("rejected", f"opening:{outcome}")
    assert _initializer(run) == [
        ("initializer_candidate", "compatible_warm_start(present)"),
        ("initializer_rejected", f"warm_start_rejected(opening:{outcome})"),
    ]
    region = run.steps[-1].detail
    assert isinstance(region, RegionResult)
    assert region.branch_provenance[0]["initializer_source"] == "traversal-G0-v1"
    assert run.outcome == "CONVERGED"


def _identity_refused(state: OpeningState, requirement: OpeningRequirement) -> OpeningState:
    return dataclasses.replace(state, model_version=f"not-{requirement.model_version}")


def _bounds_refused(state: OpeningState, requirement: OpeningRequirement) -> OpeningState:
    name = next(iter(requirement.lower_bounds))
    return dataclasses.replace(state, values={**state.values, name: -1.0})


@pytest.mark.parametrize(
    ("tamper", "check"), [(_identity_refused, "identity"), (_bounds_refused, "bounds")]
)
def test_a_warm_opening_refused_by_the_opening_check_falls_through(
    monkeypatch: pytest.MonkeyPatch,
    tamper: Callable[[OpeningState, OpeningRequirement], OpeningState],
    check: str,
) -> None:
    """V13 (e) (`docs/reviews/T08-verdict-V13e.md`): T03 §5.1's opening check itself refuses a warm
    candidate. The candidate is the source's state, which passes `integrity`, `compatibility` and
    `evaluation`; at the warm solve's attempt-0 opening the real `check_opening` is handed a copy
    of the opening state made to fail one of its six checks (identity, or a free molar flow below
    its bound). Nothing the solve computes is changed — only what the check reads, and only inside
    the warm region solve. The run records `warm_start_rejected(opening:<check>)`, records no
    `initializer_accepted`, and the traversal follows to the state a run without a candidate
    reaches, bit for bit."""
    real_check, real_solve = region_module.check_opening, region_module._solve_region
    warm: list[bool] = []
    refusals: list[OpeningRefusal | None] = []

    def solving(**kwargs: Any) -> RegionResult:
        warm.append(bool(kwargs["warm_start"]))
        try:
            result: RegionResult = real_solve(**kwargs)
        finally:
            warm.pop()
        return result

    def checking(state: OpeningState, requirement: OpeningRequirement) -> OpeningRefusal | None:
        if not (warm and warm[-1]):
            return real_check(state, requirement)
        refused = real_check(tamper(state, requirement), requirement)
        refusals.append(refused)
        return refused

    monkeypatch.setattr(region_module, "_solve_region", solving)
    monkeypatch.setattr(region_module, "check_opening", checking)
    target = _binding(_child(0.95))
    run = _plan_run(target, T08_WARM_V1, _constructed(lambda values: None))
    assert [refused.check if refused else None for refused in refusals] == [check]
    assert run.warm_start is not None
    assert (run.warm_start.status, run.warm_start.reason) == ("rejected", f"opening:{check}")
    assert _initializer(run) == [
        ("initializer_candidate", "compatible_warm_start(present)"),
        ("initializer_rejected", f"warm_start_rejected(opening:{check})"),
    ]
    region = run.steps[-1].detail
    assert isinstance(region, RegionResult)
    assert region.branch_provenance[0]["initializer_source"] == "traversal-G0-v1"
    assert run.outcome == "CONVERGED"
    monkeypatch.undo()
    cold = _plan_run(target, T08_WARM_V1)
    assert cold.warm_start is not None and cold.warm_start.status == "absent"
    assert cold.outcome == "CONVERGED" and cold.state is not None and run.state is not None
    assert [run.state[name] for name in target.spec.variable_ids] == [
        cold.state[name] for name in target.spec.variable_ids
    ]


# -- B47: replay from the bundle alone -------------------------------------------------------------


def test_b47_warm_bundles_rerun_to_match_without_a_lookup(
    project: Project,
    tampered: tuple[Solved, Solved],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    lookup = ProjectStore.latest_verified_solution

    def spy(*args: Any, **kwargs: Any) -> Any:
        calls.append("lookup")
        return lookup(*args, **kwargs)

    monkeypatch.setattr(ProjectStore, "latest_verified_solution", staticmethod(spy))
    with LocalApplication.create(tmp_path / "fresh", project_id="t08-w4-b47") as app:
        for solved in (project.warm, project.incompatible, tampered[1]):
            report = app.reproduce(solved.directory, ReplayPolicy(rerun=True))
            # ADR 0007 D4 decides the mode from the environment (unpinned threads locally give
            # `compatible_reproduction`, CI's pins `exact_replay`); either way it is a rerun.
            assert report.mode in ("exact_replay", "compatible_reproduction"), report.reasons
            assert report.verdict == "MATCH", (solved.job_id, report.reasons)
            job_id = app.list_jobs(limit=200).items[-1].job_id
            rerun = _read(app.files_root / "jobs" / job_id / "rerun")
            assert rerun["solve-path.json"]["warm_start"] == solved.warm_start
            assert r0_projection(rerun) == r0_projection(solved.artifacts)
    assert calls == []
    # The spy is live: a warm solve in that project does look up.
    with LocalApplication.create(tmp_path / "spied", project_id="t08-w4-b47s") as app:
        _solve(app, commit(app, CORPUS["SYN-001-nominal"]()), WARM)
    assert calls == ["lookup"]


# -- B48: selection -------------------------------------------------------------------------------


def test_b48_the_latest_verified_state_of_the_lineage_is_selected(tmp_path: Path) -> None:
    tightened = {kind: value * 1e-12 for kind, value in KIND_TOLERANCE.items()}
    with LocalApplication.create(tmp_path / "b48", project_id="t08-w4-b48") as app:
        base = commit(app, CORPUS["SYN-001-nominal"]())
        earlier = _solve(app, base, "default")
        target = commit(app, _child(0.95))
        later = _solve(app, target, "default")
        failed = _solve(app, target, "default", check_tolerances=tightened)
        outside = _solve(app, commit(app, _child(0.9)), "default")
        run = _solve(app, target, WARM)
    assert (earlier.verdict, later.verdict, failed.verdict, outside.verdict) == (
        "VERIFIED",
        "VERIFIED",
        "FAILED",
        "VERIFIED",
    )
    # The FAILED run and the out-of-lineage run carry a solution state and are later still.
    assert solution_state.NAME in failed.artifacts and solution_state.NAME in outside.artifacts
    assert run.warm_start is not None
    assert run.warm_start["status"] == "accepted"
    assert run.warm_start["source_job_id"] == later.job_id
    assert run.warm_start["source_revision_id"] == target


def test_b48_an_ancestor_is_in_the_lineage(tmp_path: Path) -> None:
    with LocalApplication.create(tmp_path / "b48a", project_id="t08-w4-b48a") as app:
        base = commit(app, CORPUS["SYN-001-nominal"]())
        source = _solve(app, base, "default")
        run = _solve(app, commit(app, _child(0.95)), WARM)
    assert run.warm_start is not None
    assert (run.warm_start["source_job_id"], run.warm_start["source_revision_id"]) == (
        source.job_id,
        base,
    )


# -- B49: byte identity for every existing policy -------------------------------------------------


def test_b49_no_other_policy_writes_the_member(project: Project) -> None:
    for solved in (project.source, project.cold, project.incompatible_default):
        assert "warm_start" not in solved.artifacts["solve-path.json"]
        assert "warm_start" not in r0_projection(solved.artifacts)
        assert solved.messages("initializer_candidate") == []


def test_b49_the_r0_branch_is_inert_without_the_member(project: Project) -> None:
    warm = copy.deepcopy(project.warm.artifacts)
    projected = r0_projection(warm)
    assert projected["warm_start"] == {
        "status": "accepted",
        "reason": None,
        "selection": "store-latest-verified-lineage-v1",
        "candidate_variable_ids": sorted(
            project.source.artifacts["solution-state.json"]["variable_ids"]
        ),
        "projected_ids": [],
    }
    del warm["solve-path.json"]["warm_start"]
    stripped = r0_projection(warm)
    assert "warm_start" not in stripped
    assert {key: value for key, value in projected.items() if key != "warm_start"} == stripped
