"""RRC WO-5b: every pre-registered candidate of `cases.yaml` under the three policies (G9), with
G10's timers. Design note `docs/design/RRC-revision-region-continuation.md` §8.1, §8.2; ADR 0072.

**What it runs.** `cases.yaml` exactly as committed before the first run (WO-5a): the candidate
ids, edits, policies and selection rules are read from it, never restated here.

- Each source is solved under `T06-revision-v2` and verified (`verify_revision`); it is eligible
  iff `CONVERGED` and `VERIFIED`. The candidate is read off that run and its certificate, as WO-3's
  tests build it (`tests/test_rrc_edge3.py::candidate`).
- Each target is solved **in-process** under the control (`RRC-revision-v1` with
  `eo_recovery = "none"`, not offered), `T06-revision-v2`, and `RRC-revision-v1` given the
  candidate (no candidate when the source is ineligible: R4 records `absent(not_supplied)`).
- `RRC-revision-v1` is also run **in the store** (`LocalApplication`, inline executor): the source
  committed and solved under `T06-revision-v2`, the target committed as its child and solved
  under `RRC-revision-v1`, so the application's own selection and assembly (find_source, A1–A3)
  supply the source. The store run's outcome, member and state digest are reported beside the
  in-process run's; a difference is reported, never reconciled.
- Family F forces edge 3 after a `CONVERGED` item 0 (`executor.eo_recovery_due` patched to return
  `True`, S01 A17's precedent) on every target run; its store leg is not run (the patch is
  in-process only).

**G10 (no numerics change).** Two pass-through shims, restored whatever happens:
`executor._revision_continuation` is wrapped to time the edge-3 action and read the property meter
before and after; `executor.compile_problem` is wrapped to time each compile made inside it (the
λ = 1 recompile of `_region` and each λ < 1 level). Both call through with the same arguments.

**Usage** (from the repository root, `OMP_NUM_THREADS=1`, at most 4 at a time):
`python benchmarks/rrc/run_candidates.py run <ID> --out <dir>` writes `<dir>/<ID>.json`;
`python benchmarks/rrc/run_candidates.py table --out <dir> --machine ref-x86-64` assembles
`benchmarks/rrc/results-<machine>.json` and `.md` and applies §8.1's selection rules. It judges
the gates' criteria and prints them; it never edits `cases.yaml`.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import platform
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

import yaml

HERE: Final = Path(__file__).resolve().parent
ROOT: Final = HERE.parents[1]
sys.path[:0] = [str(ROOT / "src")]

from openflowsheet.application.local import LocalApplication  # noqa: E402
from openflowsheet.application.policies import RRC_REVISION_V1, T06_REVISION_V2  # noqa: E402
from openflowsheet.application.revision_binding import (  # noqa: E402
    RevisionBinding,
    bind_revision_flowsheet,
)
from openflowsheet.application.types import Change, Edit, JobRequest, SolveBody  # noqa: E402
from openflowsheet.canonical import state_sha256  # noqa: E402
from openflowsheet.models import flow_id  # noqa: E402
from openflowsheet.models.syn001 import FLOW_TOLERANCE  # noqa: E402
from openflowsheet.numerics.scaling import Scaling  # noqa: E402
from openflowsheet.orchestrator import executor, revision  # noqa: E402
from openflowsheet.orchestrator.execution import ExecutionPlan  # noqa: E402
from openflowsheet.orchestrator.executor import PlanResult, StepResult, execute_plan  # noqa: E402
from openflowsheet.orchestrator.recovery import eo_recovery_due, solver_outcomes  # noqa: E402
from openflowsheet.orchestrator.revision_continuation import (  # noqa: E402
    RevisionContinuationCandidate,
)
from openflowsheet.orchestrator.trace import SolvePolicy  # noqa: E402
from openflowsheet.verify.certificate import SolutionCertificate, verify_revision  # noqa: E402
from openflowsheet.verify.checks import VerifierError  # noqa: E402

CASES: Final[dict[str, Any]] = yaml.safe_load((HERE / "cases.yaml").read_text("utf-8"))
#: §8.1: `RRC-revision-v1` with `eo_recovery = "none"`, built here and not offered.
CONTROL: Final[SolvePolicy] = replace(
    RRC_REVISION_V1,
    globalization=replace(RRC_REVISION_V1.globalization, eo_recovery="none"),
)
POLICIES: Final[Mapping[str, SolvePolicy]] = {
    "control": CONTROL,
    "T06-revision-v2": T06_REVISION_V2,
    "RRC-revision-v1": RRC_REVISION_V1,
}
NET02: Final = "SYN-001-T06-NET02"
RECYCLE_CASE: Final = "M1-recycle"
S11_FLOWSHEETS: Final = ROOT / "benchmarks" / "s11" / "flowsheets"
T06_CASES: Final = ROOT / "benchmarks" / "t06" / "cases"
#: `ref.closed_form.corpus_cases` (T06 spec §4.3), the twin roots of the T06 corpus flowsheets.
CORPUS: Final[dict[str, Any]] = yaml.safe_load(
    (ROOT / "benchmarks" / "t06" / "reference_values.yaml").read_text("utf-8")
)["closed_form"]["corpus_cases"]
#: T02 §6.4's allowances by column suffix, as `tests/t06_support.py::ALLOWANCE` (held equal by
#: `tests/test_rrc_candidates.py`).
ALLOWANCE: Final[Mapping[str, float]] = {
    "n": 3.1e-7,
    "T": 1e-5,
    "P": 0.1,
    "Q": 1e-2,
    "W": 1e-2,
    "xi": 3.1e-7,
}
#: S02 §10's state tolerance for flows (S01's R-514), as `tests/test_s02_column_wo2.py`:
#: rel 1e-6 + 10·τ_flow.
FLOW_REL: Final = 1e-6
FLOW_ABS: Final = 10 * FLOW_TOLERANCE
#: §8.2 G4, F1, F2: two roots of one problem agree to this, scaled by the region's `Scaling`.
SAME_ROOT: Final = 1e-8
_PATH = re.compile(r"^(instances|specifications)\[([^\]]+)\]\.(.+)$")


# -------------------------------------------------------------------------------- documents


def _base(case: str) -> dict[str, Any]:
    if case == RECYCLE_CASE:
        document: dict[str, Any] = json.loads((S11_FLOWSHEETS / f"{case}.json").read_bytes())
    else:
        document = yaml.safe_load((T06_CASES / f"{case}.yaml").read_text("utf-8"))
    return document


def _edited(document: dict[str, Any], edits: Mapping[str, Any] | None) -> dict[str, Any]:
    """`document` with each `cases.yaml` edit written at its path (`instances[<id>].<a>.<b>…`)."""
    out = copy.deepcopy(document)
    for path, value in (edits or {}).items():
        match = _PATH.match(path)
        assert match is not None, path
        kind, item_id, rest = match.groups()
        (node,) = [item for item in out[kind] if item["id"] == item_id]
        *parents, leaf = rest.split(".")
        for key in parents:
            node = node[key]
        assert leaf in node, path
        node[leaf] = value
    return out


def _committable(document: Mapping[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(dict(document))
    for key in ("revision_id", "parent_revision"):
        out.pop(key, None)
    return out


# -------------------------------------------------------------------------------- G10 shims


@dataclass
class Cost:
    recovery_wall_s: float | None = None
    property_calls: int | None = None
    compiles: list[dict[str, Any]] | None = None


@contextmanager
def _metered(cost: Cost, watch: tuple[str, ...]) -> Iterator[None]:
    """Pass-through timers on edge 3's revision continuation and on the compiles inside it."""
    original_action = getattr(executor, "_revision_continuation")  # noqa: B009
    original_compile = getattr(executor, "compile_problem")  # noqa: B009
    inside = {"on": False}

    def compile_problem(spec: Any, *args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        compiled = original_compile(spec, *args, **kwargs)
        if inside["on"]:
            assert cost.compiles is not None
            cost.compiles.append(
                {
                    "seconds": time.perf_counter() - start,
                    "values": {
                        pid: spec.parameters[pid] for pid in watch if pid in spec.parameters
                    },
                }
            )
        return compiled

    def action(*args: Any, **kwargs: Any) -> Any:
        flowsheet = args[2]
        before = flowsheet.provider.calls
        cost.compiles = []
        inside["on"] = True
        start = time.perf_counter()
        try:
            return original_action(*args, **kwargs)
        finally:
            cost.recovery_wall_s = time.perf_counter() - start
            inside["on"] = False
            cost.property_calls = flowsheet.provider.calls - before

    setattr(executor, "_revision_continuation", action)  # noqa: B010
    setattr(executor, "compile_problem", compile_problem)  # noqa: B010
    try:
        yield
    finally:
        setattr(executor, "_revision_continuation", original_action)  # noqa: B010
        setattr(executor, "compile_problem", original_compile)  # noqa: B010


@contextmanager
def _forced(on: bool) -> Iterator[None]:
    """§8.1 F: edge 3 due after any outcome (S01 A17's precedent)."""
    original = getattr(executor, "eo_recovery_due")  # noqa: B009
    if on:
        setattr(executor, "eo_recovery_due", lambda outcome, budget, *, attempts: True)  # noqa: B010
    try:
        yield
    finally:
        setattr(executor, "eo_recovery_due", original)  # noqa: B010


# -------------------------------------------------------------------------------- in-process


@dataclass(frozen=True)
class Solved:
    document: dict[str, Any]
    binding: RevisionBinding
    plan: ExecutionPlan
    run: PlanResult
    seconds: float

    @property
    def step(self) -> StepResult | None:
        steps = [step for step in self.run.steps if step.kind == "solve_eo"]
        return steps[-1] if steps else None

    def certificate(self) -> SolutionCertificate | None:
        try:
            return verify_revision(
                self.binding, self.document, self.run, solve_plan=self.plan.steps[-1].solve_plan
            )
        except VerifierError:
            return None


def solve(document: dict[str, Any], policy: SolvePolicy, **keywords: Any) -> Solved:
    binding = bind_revision_flowsheet(document)
    assert isinstance(binding, RevisionBinding), binding
    plan, _ = revision.plan_revision(binding, policy)
    assert isinstance(plan, ExecutionPlan), plan
    start = time.perf_counter()
    run = execute_plan(
        plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=policy, **keywords
    )
    return Solved(document, binding, plan, run, time.perf_counter() - start)


def candidate(source: Solved, certificate: SolutionCertificate) -> RevisionContinuationCandidate:
    """§5.3's candidate from a `VERIFIED` solve of the ancestor (WO-3's construction)."""
    fingerprint = certificate.root_fingerprint
    assert fingerprint is not None and source.run.state is not None
    return RevisionContinuationCandidate(
        job_id="job-source",
        revision_id=str(source.document.get("revision_id")),
        model_version=fingerprint["model_version"],
        constants_sha256=fingerprint["constants_sha256"],
        full_state_sha256=fingerprint["full_state_sha256"],
        signature=tuple(
            (str(unit), str(regime))
            for unit, regime in certificate.branch_provenance[-1]["signature"]
        ),
        state=dict(source.run.state),
        parameters=dict(source.binding.spec.parameters),
    )


def state_digest(state: Mapping[str, float] | None) -> str | None:
    if state is None:
        return None
    text = json.dumps({k: float(v) for k, v in state.items()}, sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()


def scaled_distance(
    binding: RevisionBinding, x: Mapping[str, float], y: Mapping[str, float]
) -> float:
    """‖x − y‖∞ in the region's column scales (`Scaling.from_spec`, as `solve_region` scales)."""
    scaling = Scaling.from_spec(binding.spec)
    return max(abs(x[name] - y[name]) / scaling.column[name] for name in binding.spec.variable_ids)


def report(solved: Solved) -> dict[str, Any]:
    """Everything §8.1 reports for one run, whatever it is."""
    run, step = solved.run, solved.step
    certificate = solved.certificate() if run.outcome == "CONVERGED" else None
    out: dict[str, Any] = {
        "outcome": run.outcome,
        "verification_status": None if certificate is None else certificate.verification_status,
        "message": run.message[:300],
        "seconds": round(solved.seconds, 3),
        "state_sha256": state_digest(run.state),
    }
    if certificate is not None and certificate.root_fingerprint is not None:
        out["full_state_sha256"] = certificate.root_fingerprint["full_state_sha256"]
    if step is None:
        return out
    detail = step.detail
    record = step.revision_continuation
    out.update(
        {
            "step_outcome": step.outcome,
            "iterations": step.iterations,
            "eo_recovery": step.eo_recovery,
            "eo_recovery_unsupported": step.eo_recovery_unsupported,
            "record_status": None if record is None else record.status,
            "record_reason": None if record is None else record.reason,
            "continued": None
            if record is None or not record.parameter_ids
            else {
                "parameter_ids": list(record.parameter_ids),
                "start_values": [repr(v) for v in record.start_values],
            },
            "attempts": len(getattr(detail, "attempts", ()) or ()),
        }
    )
    failed = step.recovered_from if step.recovered_from is not None else detail
    if failed is not None and hasattr(failed, "attempts"):
        out["item0"] = {
            "outcome": failed.outcome,
            "iterations": failed.iterations,
            "in_trigger_set": eo_recovery_due(
                failed.outcome, failed.budget, attempts=solver_outcomes(failed.attempts)
            ),
        }
    homotopy = getattr(detail, "homotopy", None)
    if homotopy is not None:
        out["homotopy"] = {
            "type": homotopy.continuation.type,
            "trials": len(homotopy.trials),
            "accepted": sum(1 for trial in homotopy.trials if trial.accepted),
            "rejected": homotopy.rejected_trials,
            "lambda_levels": [str(level) for level in homotopy.lambda_levels],
            "lambda_reached": str(homotopy.lambda_reached),
            "stalled_at": homotopy.stalled_at,
        }
    provenance = getattr(detail, "branch_provenance", None) or []
    out["branch_items"] = [
        {
            "attempt": item.get("attempt"),
            "initializer_source": item.get("initializer_source"),
            "core": item.get("core"),
            "opening_state_sha256": item.get("opening_state_sha256"),
        }
        for item in provenance
    ]
    out["initializer_rejected"] = [
        event.message for event in run.trace.of_kind("initializer_rejected")
    ]
    return out


# -------------------------------------------------------------------------------- the store


def _store_commit(app: LocalApplication, document: Mapping[str, Any]) -> str:
    edits = tuple(Edit("set", (key,), value) for key, value in _committable(document).items())
    with app.store.reading() as connection:
        head = app.store.head(connection)
    result = app.commit_change(
        Change(edits=edits, new_revision_id=None), head, f"commit-{time.monotonic_ns()}"
    )
    assert result.status == "committed", result
    assert result.revision_id is not None
    return result.revision_id


def _store_solve(app: LocalApplication, revision_id: str, policy_id: str) -> dict[str, Any]:
    count = len(app.list_jobs(limit=200).items)
    request = JobRequest(
        "solve",
        f"rrc-{revision_id}-{policy_id}-{count}",
        SolveBody(revision_id, policy_id=policy_id),
    )
    job = app.submit_job(request).job
    out: dict[str, Any] = {"job_status": job.status, "job_id": job.job_id}
    if job.status != "completed":
        out["error"] = str(job.error)[:300]
        return out
    result = app.get_job_result(job.job_id).run_result
    assert result is not None
    bundle = app.files_root / "jobs" / job.job_id / "bundle" / "artifacts"
    artifacts = {path.name: json.loads(path.read_bytes()) for path in sorted(bundle.iterdir())}
    member = artifacts["solve-path.json"].get("revision_continuation")
    state = artifacts.get("solution-state.json")
    out.update(
        {
            "outcome": result.outcome,
            "verification_status": result.verification_status,
            "member_status": None if member is None else member["status"],
            "member_reason": None if member is None else member["reason"],
            "member_continued": None if member is None else member["continued"],
            "member_source_revision_id": None if member is None else member["source_revision_id"],
            "state_sha256": None if state is None else state_digest(state["variables"]),
            "artifact_names": sorted(artifacts),
        }
    )
    return out


def store_leg(source: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="rrc-wo5-") as root:
        with LocalApplication.create(Path(root) / "p", project_id="rrc-wo5") as app:
            source_id = _store_commit(app, source)
            ancestor = _store_solve(app, source_id, "T06-revision-v2")
            target_id = _store_commit(app, target)
            continued = _store_solve(app, target_id, "RRC-revision-v1")
            continued["source_revision_id"] = source_id
            return {"source": ancestor, "target": continued}


# -------------------------------------------------------------------------------- one candidate


def _find(cid: str) -> tuple[str, dict[str, Any], dict[str, Any], bool]:
    """(family, source document, target document, forced) for one candidate id."""
    families = CASES["families"]
    n = families["N"]
    for entry in n["sources"]:
        if entry["id"] == cid:
            source = _edited(_base(n["target"]["case"]), {n["edit_path"]: entry["split_fraction"]})
            return "N", source, _base(n["target"]["case"]), False
    c = families["C"]
    for entry in c["targets"]:
        if entry["id"] == cid:
            source = _base(c["source"]["case"])
            return "C", source, _edited(source, entry["edits"]), False
    for entry in families["F"]["cases"]:
        if entry["id"] == cid:
            source = _edited(_base(entry["source"]["case"]), entry["source"].get("edits"))
            target = _edited(_base(entry["target"]["case"]), entry["target"].get("edits"))
            return "F", source, target, True
    raise KeyError(cid)


def _eligible(solved: Solved) -> tuple[bool, SolutionCertificate | None]:
    certificate = solved.certificate() if solved.run.outcome == "CONVERGED" else None
    ok = certificate is not None and certificate.verification_status == "VERIFIED"
    return ok, certificate


def feed_flows(document: Mapping[str, Any]) -> tuple[tuple[str, float], ...]:
    """The column flowsheet's feed flows by component, from its pinning specifications
    (`SPEC-S-IN1-n-<c>`): the revision's declared values, not the solver's."""
    values = {item["id"]: item["value"] for item in document["specifications"]}
    return tuple((c, float(values[f"SPEC-S-IN1-n-{c}"])) for c in "ABC")


def closure(document: Mapping[str, Any], state: Mapping[str, float]) -> dict[str, Any]:
    """S11.A29's per-component closure: feed = distillate + purge, within the flow tolerance."""
    worst = 0.0
    for c, n in feed_flows(document):
        out = state[flow_id("S-DISTILLATE", c)] + state[flow_id("S-PURGE", c)]
        worst = max(worst, abs(out - n) / (FLOW_REL * n + FLOW_ABS))
    return {"worst_ratio": worst, "met": worst <= 1.0}


def registered_root(entry: Mapping[str, Any]) -> dict[str, tuple[Decimal, float]]:
    """A twin root's registered coordinates, `column -> (value, allowance)`, as
    `tests/t06_support.py::registered_root` reads them (held equal by the gate tests)."""
    out: dict[str, tuple[Decimal, float]] = {}
    for stream, state in entry["streams"].items():
        for component, value in zip("ABC", state["n_mol_per_s"], strict=True):
            out[f"{stream}.n.{component}"] = (Decimal(value), ALLOWANCE["n"])
        out[f"{stream}.T"] = (Decimal(state["T_K"]), ALLOWANCE["T"])
        out[f"{stream}.P"] = (Decimal(state["P_Pa"]), ALLOWANCE["P"])
        for phase, keys in (
            ("vap", ("vapor_mol_per_s", "vapor_n_mol_per_s")),
            ("liq", ("liquid_mol_per_s", "liquid_n_mol_per_s")),
        ):
            for key in (key for key in keys if key in state):
                for component, value in zip("ABC", state[key], strict=True):
                    out[f"{stream}.{phase}.{component}"] = (Decimal(value), ALLOWANCE["n"])
    for field, suffix in (("duty_W", "Q"), ("work_W", "W"), ("extent_mol_per_s", "xi")):
        for unit, value in (entry.get(field) or {}).items():
            out[f"{unit}.{suffix}"] = (Decimal(value), ALLOWANCE[suffix])
    return out


def worst_ratio(
    state: Mapping[str, float], expected: Mapping[str, tuple[Decimal, float]]
) -> tuple[float, str]:
    """The largest `|x - x_ref| / allowance` over the registered coordinates, and where."""
    return max(
        (float(abs(Decimal(state[column]) - value) / Decimal(allowance)), column)
        for column, (value, allowance) in expected.items()
    )


def run_case(cid: str) -> dict[str, Any]:
    family, source_doc, target_doc, forced = _find(cid)
    entry: dict[str, Any] = {"id": cid, "family": family, "forced_edge": forced}
    source = solve(source_doc, T06_REVISION_V2)
    eligible, certificate = _eligible(source)
    if family == "F" and not eligible:
        # §8.1 F2: the 2 K source when the 5 K source is not VERIFIED.
        (spec,) = [e for e in CASES["families"]["F"]["cases"] if e["id"] == cid]
        fallback = spec["source"].get("fallback_edits")
        if fallback:
            entry["source_first_try"] = report(source)
            source_doc = _edited(_base(spec["source"]["case"]), fallback)
            source = solve(source_doc, T06_REVISION_V2)
            eligible, certificate = _eligible(source)
            entry["source_fallback_used"] = True
    entry["source"] = report(source)
    entry["source_eligible"] = eligible
    ancestor = candidate(source, certificate) if eligible and certificate is not None else None
    target_spec = bind_revision_flowsheet(target_doc)
    assert isinstance(target_spec, RevisionBinding), target_spec
    # The parameters the source and the target disagree on: G10 labels each compile by them.
    watch = tuple(
        pid
        for pid, value in target_spec.spec.parameters.items()
        if source.binding.spec.parameters.get(pid) != value
    )
    entry["differing_parameters"] = list(watch)
    runs: dict[str, Any] = {}
    solved_by: dict[str, Solved] = {}
    for name, policy in POLICIES.items():
        keywords = {"revision_continuation": ancestor} if name == "RRC-revision-v1" else {}
        cost = Cost()
        with _forced(forced), _metered(cost, watch):
            solved = solve(target_doc, policy, **keywords)
        runs[name] = report(solved)
        solved_by[name] = solved
        if cost.compiles is not None:
            runs[name]["g10"] = {
                "recovery_wall_s": round(cost.recovery_wall_s or 0.0, 3),
                "property_calls": cost.property_calls,
                "levels_compiled": len(cost.compiles),
                "compile_seconds": [round(c["seconds"], 3) for c in cost.compiles],
                "compile_values": [
                    {pid: repr(v) for pid, v in c["values"].items()} for c in cost.compiles
                ],
            }
    rrc = solved_by["RRC-revision-v1"]
    checks: dict[str, Any] = {}
    if ancestor is not None:
        items = runs["RRC-revision-v1"].get("branch_items", [])
        recovery = [i for i in items if i["initializer_source"] == "revision_continuation_source"]
        # G2 (f) as amended (review S1): the opening hash is the source root over the recovery
        # attempt 0's free columns, in the region's order. It equals the source's
        # `full_state_sha256` (the special case, kept) exactly when no column is pinned.
        checks["g2f_opening_equals_source_full_state"] = (
            None
            if not recovery
            else recovery[0]["opening_state_sha256"] == ancestor.full_state_sha256
        )
        opened = (
            []
            if rrc.step is None
            else [
                c for c in rrc.step.detail.contexts if c.core == "homotopy" and c.attempt_index == 0
            ]
        )
        checks["g2f_opening_equals_source_over_free_columns"] = (
            None
            if not recovery or len(opened) != 1
            else recovery[0]["opening_state_sha256"]
            == state_sha256(ancestor.state, tuple(opened[0].column_scales))
        )
        checks["source_signature"] = [list(pair) for pair in ancestor.signature]
    if rrc.run.outcome == "CONVERGED" and rrc.run.state is not None:
        restart = solved_by["T06-revision-v2"]
        if restart.run.outcome == "CONVERGED" and restart.run.state is not None:
            checks["scaled_distance_to_t06_root"] = scaled_distance(
                rrc.binding, rrc.run.state, restart.run.state
            )
        step = rrc.step
        if forced and step is not None and step.recovered_from is not None:
            item0 = step.recovered_from.state
            if item0 is not None:
                checks["scaled_distance_to_item0_root"] = scaled_distance(
                    rrc.binding, rrc.run.state, item0
                )
        if family == "N":
            ratio, column = worst_ratio(rrc.run.state, registered_root(CORPUS[NET02]))
            checks["net02_closed_form_worst_ratio"] = [ratio, column]
        if family in ("C",) or cid == "F1":
            checks["a29_closure"] = closure(target_doc, rrc.run.state)
    entry["runs"] = runs
    entry["checks"] = checks
    if not forced:
        entry["store"] = store_leg(source_doc, target_doc)
    return entry


# -------------------------------------------------------------------------------- the table


def _qualifies(entry: dict[str, Any], criteria: Mapping[str, Any]) -> bool:
    rrc = entry["runs"]["RRC-revision-v1"]
    want = criteria["RRC-revision-v1"]
    store = entry.get("store", {}).get("target", {})
    ok = (
        entry["source_eligible"]
        and rrc["outcome"] == want["outcome"]
        and rrc["verification_status"] == want["verification_status"]
        and rrc.get("eo_recovery") == want["eo_recovery"]
        and rrc.get("record_status") == want["member_status"]
        and store.get("member_status") == want["member_status"]
    )
    if "control" in criteria:
        control = entry["runs"]["control"]
        ok = ok and (control.get("item0") or {}).get("in_trigger_set") is True
    return bool(ok)


def _md_row(entry: dict[str, Any]) -> str:
    cells = [entry["id"], f"{entry['source']['outcome']}/{entry['source']['verification_status']}"]
    for name in POLICIES:
        r = entry["runs"][name]
        h = r.get("homotopy") or {}
        trials = f"{h.get('accepted', '-')}/{h.get('rejected', '-')}" if h else "-"
        edge = r.get("eo_recovery_unsupported") or r.get("record_status") or ""
        reason = "" if r.get("record_reason") is None else f"({r['record_reason']})"
        cells.append(
            f"{r['outcome']}/{r['verification_status']} it={r.get('iterations')} "
            f"edge={r.get('eo_recovery')}:{edge}{reason} λ acc/rej={trials}"
        )
    store = entry.get("store", {}).get("target", {})
    member = f"member={store.get('member_status')}"
    cells.append(
        f"{store.get('outcome')}/{store.get('verification_status')} {member}" if store else "-"
    )
    return "| " + " | ".join(cells) + " |"


def table(out: Path, machine: str) -> int:
    ids = [e["id"] for e in CASES["families"]["N"]["sources"]]
    ids += [e["id"] for e in CASES["families"]["C"]["targets"]]
    ids += [e["id"] for e in CASES["families"]["F"]["cases"]]
    entries = {cid: json.loads((out / f"{cid}.json").read_text("utf-8")) for cid in ids}
    families = CASES["families"]
    selected_n = next(
        (
            e["id"]
            for e in families["N"]["sources"]
            if _qualifies(entries[e["id"]], families["N"]["selection_criteria"])
        ),
        None,
    )
    selected_c = next(
        (
            e["id"]
            for e in families["C"]["targets"]
            if _qualifies(entries[e["id"]], families["C"]["selection_criteria"])
        ),
        None,
    )
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT, check=True
    ).stdout.strip()
    document = {
        "schema": "rrc-candidate-results-v1",
        "cases": "benchmarks/rrc/cases.yaml",
        "commit": commit,
        "machine": machine,
        "platform": platform.platform(),
        "selected": {"N": selected_n, "C": selected_c},
        "candidates": [entries[cid] for cid in ids],
    }
    (HERE / f"results-{machine}.json").write_text(
        json.dumps(document, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        f"# RRC WO-5b candidate table ({machine}, commit {commit[:10]})",
        "",
        "Generated by `benchmarks/rrc/run_candidates.py table`; every candidate of `cases.yaml`,",
        "every policy (G9). Cell: outcome/verification, iterations, edge 3 (`eo_recovery`: the",
        "unsupported reason or the revision-continuation record's status (reason)), accepted/",
        "rejected λ-trials.",
        "",
        f"Selected: Family N → **{selected_n}**; Family C → **{selected_c}**.",
        "",
        "| id | source (T06-revision-v2) | control | T06-revision-v2 | RRC-revision-v1 "
        "| store RRC |",
        "| --- | --- | --- | --- | --- | --- |",
        *[_md_row(entries[cid]) for cid in ids],
        "",
    ]
    (HERE / f"results-{machine}.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"selected N={selected_n} C={selected_c}; {len(ids)} candidates tabled")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=("run", "table"))
    parser.add_argument("case", nargs="?")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--machine", default="ref-x86-64")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    if args.action == "table":
        return table(args.out, args.machine)
    start = time.perf_counter()
    entry = run_case(args.case)
    entry["case_seconds"] = round(time.perf_counter() - start, 3)
    (args.out / f"{args.case}.json").write_text(
        json.dumps(entry, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    rrc, runs = entry["runs"]["RRC-revision-v1"], entry["runs"]
    print(
        f"{args.case}: source {entry['source']['outcome']}/{entry['source']['verification_status']}"
        f" control {runs['control']['outcome']} t06 {runs['T06-revision-v2']['outcome']}"
        f" rrc {rrc['outcome']}/{rrc['verification_status']} {rrc.get('record_status')}"
        f" {rrc.get('record_reason')} ({entry['case_seconds']} s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
