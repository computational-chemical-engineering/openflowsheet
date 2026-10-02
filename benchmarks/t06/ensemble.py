"""T06's ensemble harness: the runner, the scorer, the reports and the replay (W6).

Spec `docs/derivations/T06-corpus-spec.md` §6.6 (the run), §7 (scoring, the gate, the reports) and
§10 (controlled numerical replay), as amended by Amendments 1 and 2. The starts are the published
file's (`benchmarks/t06/ensemble/starts-nominal-v1.json`, written by `generator`); nothing here
draws or regenerates one.

**One start, cold (§6.6).** A fresh binding, provider, compiled problem and plan per start; no
warm-start cache. Each path enters where its registered initializer's output enters: the revision
path through `execute_plan(user_start=…)` (recorded `user_guess`, so edge 3's restart runs after a
failed first solve, ADR 0015), the tear path through `solve_tear(initial_recycle=…)`, NET-05 as the
value of its freed guess in its revision. Every start that converges is certified with the
default check policy. The harness calls existing entry points only; the one thing it adds to them
is timing: for the four wall times it wraps, for the duration of a run, `compile_problem` (compile)
and the initializers `traversal_start`, `restart_start`, `Syn001Flowsheet.initial_recycle` and the
executor's pre-solve `solve_tear` (init) in timing shims that call through unchanged (the M2
attribution of `docs/t06-measurements.md`). *compile* also holds the binding and the plan.

**Scoring (§7.1–§7.2)** is a pure function of the record: `F-GEN`, `F-CRASH`, `F-TIME`,
`F-BUDGET` (K04's `budget/cancellation outcomes`), `F-TYPED(<outcome>)`,
`F-FALSE-SUCCESS-CAUGHT`, `F-UNVERIFIED(<reason>)`, `F-OTHER-ROOT`, first match wins; otherwise a
success, **rescued** iff its trace has `eo_recovery: taken` and a provenance item whose
`initializer_source` is `traversal-G0-pass8-v1` (A66).

**Replay (§10).** A start re-run from the committed file gives a record compared with the recorded
one by `run.compare.differences` under `K04-numerical-policy-v1`, the wall times excluded
(volatile).

**Run records (§6.6 (A5), §7.5 (A5); R-090).** A run document is format `t06-ensemble-results-v2`:
its run id, commit, clean-tree flag, lock hash and the registry's `cache_condition`, and a host
block whose `machine_class` is `machine_class()`'s, decided from the host (never `generator.py`'s
literal). Per start, `refinements` parses ADR 0018 D5's closing message off every `attempt_closed`
event of the start's trace; the harness only reads the trace. The report counts them (A90 (A5)),
and `a98` compares run 2r with run 2's same-class file (A98). v1 files (runs 1 and 2) are read, and
never rewritten: their refinements are "not recorded".
"""

from __future__ import annotations

import copy
import hashlib
import math
import os
import platform
import re
import subprocess
import time
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Any, Final

import numpy as np
import scipy.sparse as sp
import yaml
from scipy.stats import beta

import openflowsheet.orchestrator.executor as executor_module
import openflowsheet.orchestrator.tear as tear_module
import openflowsheet.verify.certificate as certificate_module
import openflowsheet.verify.regularity as regularity_module
from benchmarks.t06 import generator
from openflowsheet.application.binding import Binding, bind_revision
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.application.revision_run import legacy_plan
from openflowsheet.models import flow_id
from openflowsheet.models.revision_flowsheet import pin_specifications
from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
from openflowsheet.numerics.scaling import Scaling
from openflowsheet.orchestrator import revision
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import PlanResult, execute_plan
from openflowsheet.orchestrator.region import RegionResult
from openflowsheet.orchestrator.roots import same_root
from openflowsheet.orchestrator.tear import TEAR_STREAM, solve_tear
from openflowsheet.orchestrator.trace import SolveEvent, SolvePolicy
from openflowsheet.run.compare import differences
from openflowsheet.run.manifest import policy_sha256
from openflowsheet.verify import CheckResult
from openflowsheet.verify.certificate import (
    SolutionCertificate,
    statements_for,
    verify,
    verify_bound,
    verify_revision,
)
from openflowsheet.verify.failure import TAXONOMY

__all__ = [
    "A33_PREFIXES",
    "A90_EXPECTED_REF_X86_64",
    "ACYCLIC_STATEMENT",
    "ACYCLIC_TEXT_COUNT",
    "CEILING_S",
    "DESIGNS_STATEMENT",
    "HOLDOUT_HEADER",
    "HOLDOUT_INDICES",
    "HOLDOUT_RUN_ID",
    "N",
    "REFERENCE_CLASS",
    "REFINEMENT_GRAMMAR",
    "RESCUE_STATEMENT",
    "RESULTS_FORMAT",
    "RESULTS_FORMAT_V1",
    "S_MIN",
    "EnsembleCase",
    "RefinementGrammarError",
    "a33_expected",
    "a98_discrepancies",
    "allowance",
    "captured_screens",
    "classify",
    "clopper_pearson_lower",
    "exact_norm_check",
    "facts",
    "generation_failure_record",
    "host",
    "machine_class",
    "policies",
    "provenance",
    "refinements",
    "registered",
    "render",
    "replay_differences",
    "replayable",
    "report",
    "rescued",
    "run_start",
    "setup",
]

#: §7.5: the time ceiling per start, every machine class.
CEILING_S: Final = 60.0
#: §7.3: the gate.
N: Final = 440
S_MIN: Final = 418
#: §7.4: the one-sided confidence level of the Clopper–Pearson bound.
CP_ALPHA: Final = 0.05
#: §7.4 (A2): the report's wording, verbatim.
RESCUE_STATEMENT: Final = (
    "A rescued start's outcome does not depend on its perturbation: the restart discards it, so "
    "the restart's result is the same for every rescued start of a case, and on an acyclic case "
    "the restart starts at the causal answer. `p_c^first = s_c^first/20` is the evidence about "
    "Newton's basin; `p_c` is the evidence about the solver with its registered fallbacks."
)
ACYCLIC_STATEMENT: Final = (
    "On the {n} acyclic cases ({ids}) the restart starts at the causal answer — the registered "
    "initializer's own start — so every start of these cases that fails from its perturbation "
    "with an edge-3 trigger is rescued by a solve that does not depend on the perturbation; for "
    "these cases `p_c` says nothing about Newton's basin, and `p_c^first` says all of it."
)
DESIGNS_STATEMENT: Final = (
    "No statement is made about other process designs: 440 starts are not 440 designs (plan §6.2)."
)
#: §6.2, §7.4 and §15 (A3) say ten acyclic cases (THM-09 the tenth; the pre-A3 text said nine);
#: A84 checks the count against the plans and prints a finding if they ever count otherwise.
ACYCLIC_TEXT_COUNT: Final = 10
#: T02 §6.4's allowances (S3), by column suffix; every other column is a flow.
ALLOWANCE: Final[Mapping[str, float]] = {"T": 1e-5, "P": 0.1, "Q": 1e-2, "W": 1e-2}
FLOW_ALLOWANCE: Final = 3.1e-7


def allowance(column: str) -> float:
    return ALLOWANCE.get(column.rsplit(".", 1)[1], FLOW_ALLOWANCE)


@dataclass(frozen=True)
class EnsembleCase:
    """A registered eligible case as the ensemble runs it: its ids, path and policy, a factory
    for a fresh copy of its revision, and its registered root, `column -> (value, allowance)`."""

    case: str
    fixture: str
    path: generator.SolvePath
    policy: SolvePolicy
    document: Callable[[], dict[str, Any]]
    root: Mapping[str, tuple[Decimal, float]]


# -- setup (the generator's) and the case's facts ------------------------------------------------


def setup(case: EnsembleCase) -> generator.CaseSetup:
    """The generator's setup for the case, from a fresh binding of its revision."""
    document = case.document()
    if case.path == "revision_eo":
        binding = bind_revision_flowsheet(document)
        if not isinstance(binding, RevisionBinding):
            raise ValueError(f"{case.case}: unbound: {binding}")
        pinned = tuple(pin_specifications(document))
        return generator.revision_setup(case.case, case.fixture, binding, case.policy, pinned)
    bound = bind_revision(document)
    if not isinstance(bound, Binding):
        raise ValueError(f"{case.case}: unbound: {bound}")
    if case.path == "tear":
        return generator.tear_setup(case.case, case.fixture, bound, case.policy)
    return generator.legacy_setup(case.case, case.fixture, document, bound)


#: The registered SYN-001 binding's plan (T02 §7.5), moved verbatim into the application as
#: `legacy_eo`'s plan builder (T07 design note ruling round 1 R2.2); the ensemble runs that one
#: function, which the `t06` identity key proves inert.
_legacy_plan = legacy_plan


def facts(case: EnsembleCase) -> dict[str, Any]:
    """What the report needs of the case beyond its records: `acyclic` — §7.4 (A2): the case's
    plan has no torn stream, i.e. T01's structural report, which the plan is built on, finds no
    loop; computed from the plan, never typed from a list — and the registered column scales
    (`Scaling.from_spec`) the branch census compares roots in."""
    document = case.document()
    if case.path == "revision_eo":
        binding = bind_revision_flowsheet(document)
        assert isinstance(binding, RevisionBinding)
        _, report = revision.plan_revision(binding, case.policy)
        spec = binding.spec
    else:
        bound = bind_revision(document)
        assert isinstance(bound, Binding)
        _, report = _legacy_plan(bound, case.policy)
        spec = bound.spec
    return {
        "path": case.path,
        "policy": case.policy.policy_id,
        "acyclic": report.tear is None or not report.tear.loops,
        "column_scales": dict(Scaling.from_spec(spec).column),
    }


# -- timing ----------------------------------------------------------------------------------


class _Clock:
    """Wall time by phase; a nested phase's time is subtracted from the enclosing one."""

    def __init__(self) -> None:
        self.stack: list[list[Any]] = []
        self.buckets: dict[str, float] = {"compile": 0.0, "init": 0.0, "solve": 0.0, "verify": 0.0}

    def phase(self, name: str, function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        self.stack.append([name, time.perf_counter(), 0.0])
        try:
            return function(*args, **kwargs)
        finally:
            _, began, child = self.stack.pop()
            elapsed = time.perf_counter() - began
            self.buckets[name] += elapsed - child
            if self.stack:
                self.stack[-1][2] += elapsed

    def wrap(self, name: str, function: Callable[..., Any]) -> Callable[..., Any]:
        def timed(*args: Any, **kwargs: Any) -> Any:
            return self.phase(name, function, *args, **kwargs)

        return timed


@contextmanager
def _instrumented(clock: _Clock) -> Iterator[None]:
    """Install the timing shims for one run and restore every original, whatever happens."""
    targets: list[tuple[Any, str, str]] = [
        (executor_module, "compile_problem", "compile"),
        (tear_module, "compile_problem", "compile"),
        (certificate_module, "compile_problem", "compile"),
        (revision, "traversal_start", "init"),
        (revision, "restart_start", "init"),
        (Syn001Flowsheet, "initial_recycle", "init"),
        (executor_module, "solve_tear", "init"),
    ]
    saved = [(owner, name, owner.__dict__[name]) for owner, name, _ in targets]
    try:
        for owner, name, phase in targets:
            setattr(owner, name, clock.wrap(phase, getattr(owner, name)))
        yield
    finally:
        for owner, name, original in saved:
            setattr(owner, name, original)


@contextmanager
def captured_screens(captured: list[tuple[sp.csc_matrix, Any]]) -> Iterator[None]:
    """Capture every matrix the certificate's regularity screen judges, with its evidence, for
    §8.3's exact-norm check (A32). Calls through unchanged."""
    original = regularity_module.screen

    def capturing(matrix: Any, *args: Any, **kwargs: Any) -> Any:
        evidence = original(matrix, *args, **kwargs)
        captured.append((sp.csc_matrix(matrix), evidence))
        return evidence

    regularity_module.screen = capturing
    try:
        yield
    finally:
        regularity_module.screen = original


# -- run records and the machine class (§6.6 (A5), §7.5 (A5); R-090) ---------------------------

#: §6.6 (A5): the run document's format. Run 1's and run 2's files are v1, read and never
#: rewritten.
RESULTS_FORMAT: Final = "t06-ensemble-results-v2"
RESULTS_FORMAT_V1: Final = "t06-ensemble-results-v1"
#: §7.5: the reference machine class, the only one `generate` writes on (§6.5, §7.6 (A5)).
REFERENCE_CLASS: Final = "ref-x86-64"
REGISTRY_FILE: Final = Path(__file__).resolve().parents[1] / "registry.yaml"
#: ADR 0018 D5's closing message, as §6.6 (A5) registers its grammar.
REFINEMENT_GRAMMAR: Final = re.compile(
    r"^terminal_refinement\((accepted|reverted|abandoned): (.*)\): chord (\S+) at (\S+)$"
)
#: A90 (A5): the verdicts' §2.4 reconstruction of run 2's refinements on `ref-x86-64`, out of the
#: run 1 → run 2 differences and independent of the instrumentation — 17 fired, 17 kept, each in
#: its start's last attempt. A98 (c) compares run 2r's `ref-x86-64` records with it exactly.
A90_EXPECTED_REF_X86_64: Final[tuple[tuple[str, int], ...]] = (
    ("NET-03", 8),
    ("NET-03", 19),
    ("NET-10", 0),
    ("NET-10", 4),
    ("NET-10", 8),
    ("NET-10", 11),
    ("NET-11", 12),
    ("STR-01", 5),
    ("THM-07", 0),
    ("THM-07", 5),
    ("THM-09", 1),
    ("THM-09", 2),
    ("THM-09", 5),
    ("THM-09", 6),
    ("THM-09", 10),
    ("THM-09", 19),
    ("THM-10", 7),
)
#: §7.6 (A5): the holdout — its run id, its start indices (reserved to it; a later draw under
#: this law takes 40 and up) and its report's header, which carries no gate line.
HOLDOUT_RUN_ID: Final = "holdout1"
HOLDOUT_INDICES: Final = range(20, 40)
HOLDOUT_HEADER: Final = "HOLDOUT {run_id} — reported, never gated (T06 spec §7.6 (A5))"
#: ADR 0018 D5′: the meter's own message on a step that ended `BUDGET_EXHAUSTED(property_calls)`.
PROPERTY_BUDGET_MESSAGE: Final = "the property-call budget of "


class RefinementGrammarError(RuntimeError):
    """§6.6 (A5): a closing message that begins `terminal_refinement(` and does not match D5's
    grammar. A harness defect: the run stops, and it is never a start's outcome."""


@cache
def registered() -> Mapping[str, Any]:
    """The registry's `ensemble` section, read once per process."""
    with REGISTRY_FILE.open(encoding="utf-8") as handle:
        section: Mapping[str, Any] = yaml.safe_load(handle)["ensemble"]
    return section


def machine_class() -> str:
    """§7.5 (A5): the machine class, decided from the host, never written as a literal. The first
    registered class (`ensemble.machine_classes`) whose `github_actions` flag equals whether
    `GITHUB_ACTIONS` is `true`, whose `architecture` is `platform.machine()`, and whose
    `cpu_model`, where it registers one, is the host's (read as `generator._cpu_model` reads
    it); otherwise `unregistered(<machine>)`, reported and never gated."""
    machine = platform.machine()
    on_ci = os.environ.get("GITHUB_ACTIONS") == "true"
    for name, entry in registered()["machine_classes"].items():
        if bool(entry["github_actions"]) != on_ci or entry["architecture"] != machine:
            continue
        if "cpu_model" in entry and entry["cpu_model"] != generator._cpu_model():
            continue
        return str(name)
    return f"unregistered({machine})"


def host() -> dict[str, str]:
    """§6.6 (A5): the generator's host block with `machine_class` replaced by `machine_class()`.
    On `ref-x86-64` it equals `generator.host()`, which the published starts record."""
    return {**generator.host(), "machine_class": machine_class()}


def _git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=root, check=True, capture_output=True, text=True
    ).stdout


def provenance(root: Path) -> dict[str, Any]:
    """§6.6 (A5): `commit` (the 40-hex `HEAD`), `tree_clean` (`git status --porcelain` is empty),
    `environment_lock_sha256` (`requirements.lock`'s bytes) and the registry's `cache_condition`.
    Taken before the run starts, so the run's own output cannot dirty it."""
    return {
        "commit": _git(root, "rev-parse", "HEAD").strip(),
        "tree_clean": _git(root, "status", "--porcelain") == "",
        "environment_lock_sha256": hashlib.sha256(
            (root / "requirements.lock").read_bytes()
        ).hexdigest(),
        "cache_condition": dict(registered()["cache_condition"]),
    }


def refinements(events: Sequence[SolveEvent]) -> list[dict[str, Any]]:
    """§6.6 (A5): one entry per `attempt_closed` event, in trace order, across every region solve
    the start ran (the restart's included). `fired` iff the first line of the event's message
    matches D5's grammar; then `result`, `reason`, `rho` and `column` are its groups, otherwise
    `null`. `last` marks the start's final `attempt_closed`. Raises `RefinementGrammarError` on a
    first line that begins `terminal_refinement(` and does not match."""
    closed = [event for event in events if event.kind == "attempt_closed"]
    entries: list[dict[str, Any]] = []
    for position, event in enumerate(closed):
        line = _first_line(event.message)
        match = REFINEMENT_GRAMMAR.match(line)
        if match is None and line.startswith("terminal_refinement("):
            raise RefinementGrammarError(
                f"attempt {event.attempt} (step {event.step_index}): {line!r} does not match "
                "ADR 0018 D5's grammar (spec §6.6 (A5)): a harness defect, the run stops"
            )
        entries.append(
            {
                "step": event.step_index,
                "attempt": event.attempt,
                "attempt_outcome": event.outcome,
                "last": position == len(closed) - 1,
                "fired": match is not None,
                "result": None if match is None else match[1],
                "reason": None if match is None else match[2],
                "rho": None if match is None else float(match[3]),
                "column": None if match is None else match[4],
            }
        )
    return entries


# -- one start --------------------------------------------------------------------------------


def _first_line(text: str | None) -> str:
    return (text or "").splitlines()[0] if text else ""


def _events(events: Sequence[SolveEvent]) -> list[list[Any]]:
    """The R0 projection §10 replays exactly: each event's kind and outcome, in order."""
    return [[event.kind, event.outcome] for event in events]


def _branch(rcond: float | None, estimate: float, limit: float | None) -> str:
    """§8.3: the decision the screen takes on its numbers — `τ_ill`'s relative test (escalate),
    K04 §7.4's absolute limit, or neither."""
    if rcond is None or not math.isfinite(rcond) or rcond < regularity_module.TAU_ILL:
        return "relative"
    if limit is not None and estimate > limit:
        return "absolute"
    return "none"


def exact_norm_check(matrix: sp.csc_matrix, evidence: Any) -> dict[str, Any]:
    """§8.3 (A32): the exact `‖Ĵ⁻¹‖₁` by the dense inverse, `estimate/exact`, and whether the
    decision taken with the exact norm equals the recorded one."""
    estimate = float(evidence.inverse_one_norm_estimate)
    dense = matrix.toarray()
    try:
        exact = float(np.linalg.norm(np.linalg.inv(dense), 1))
    except np.linalg.LinAlgError:
        return {
            "exact": None,
            "estimate": estimate,
            "ratio": None,
            "agree": not math.isfinite(estimate),
        }
    one_norm = float(np.linalg.norm(dense, 1))
    rcond_exact = 1.0 / (one_norm * exact) if exact > 0.0 else None
    recorded = _branch(evidence.rcond_1, estimate, evidence.inverse_one_norm_threshold)
    decided = _branch(rcond_exact, exact, evidence.inverse_one_norm_threshold)
    return {
        "exact": exact,
        "estimate": estimate,
        "ratio": estimate / exact if exact > 0.0 else None,
        "lower": estimate <= exact * (1.0 + 1e-12),
        "branch_recorded": recorded,
        "branch_exact": decided,
        "agree": recorded == decided,
    }


#: A33: the check-id prefixes whose checks consult the shared provider.
A33_PREFIXES = ("energy_balance.", "phase_admissibility.", "independent_split.")


def a33_expected(checks: Sequence[CheckResult]) -> set[str]:
    """A33 (A4) (spec §8.4 (A4), R-080): the ids the certificate must qualify — the prefixed
    checks whose `result` is `pass` or `fail`. A `not_applicable` check (`ZERO_FLOW`,
    `temperature_degenerate`, `fresh_flash_unresolved`) or an `unsupported` one consulted no
    provider, so an entry for it would say it did."""
    return {
        check.id
        for check in checks
        if check.id.startswith(A33_PREFIXES) and check.result in ("pass", "fail")
    }


def _a33(certificate: SolutionCertificate, provider: Any) -> dict[str, Any]:
    """A33 (A4) at one certificate: the qualified check ids are exactly `a33_expected`'s; each
    entry names the binding provider; the statements are K04's and the shared-provider
    sentence."""
    described = provider.describe()
    expected = a33_expected(certificate.checks)
    qualified = [dict(entry) for entry in certificate.independence_qualifications]
    problems = []
    if {entry["check_id"] for entry in qualified} != expected:
        problems.append("qualified_check_ids")
    for entry in qualified:
        if (
            entry["provider_id"],
            entry["implementation_sha256"],
            entry["data_sha256"],
            entry["reference_convention"],
        ) != (
            described.provider_id,
            described.implementation_sha256,
            described.data_sha256,
            described.reference_convention,
        ):
            problems.append(f"provider({entry['check_id']})")
            break
    # K04's three sentences and the shared-provider sentence, which `statements_for` returns.
    if tuple(certificate.statements) != statements_for(provider):
        problems.append("statements")
    return {"ok": not problems, "problems": problems}


def _certificate(certificate: SolutionCertificate) -> dict[str, Any]:
    regularity = certificate.regularity
    return {
        "verdict": certificate.verification_status,
        "false_success_detected": certificate.false_success_detected,
        "not_passed": sorted(
            check.id
            for check in certificate.checks
            if check.result not in ("pass", "not_applicable")
        ),
        "near_threshold": sorted(check.id for check in certificate.checks if check.near_threshold),
        "regularity_status": None if regularity is None else regularity.status,
        "rcond_1": None if regularity is None else regularity.rcond_1,
        "b": certificate.solution_error_bound_scaled,
        "root_fingerprint": (
            None if certificate.root_fingerprint is None else dict(certificate.root_fingerprint)
        ),
        "limitations": sorted(item.as_document()["kind"] for item in certificate.limitations),
    }


def _worst(state: Mapping[str, float], root: Mapping[str, tuple[Decimal, float]]) -> list[Any]:
    """S3: the largest `|x − x_ref| / allowance` over the registered coordinates, and where."""
    ratio, where = max(
        (float(abs(Decimal(state[column]) - value) / Decimal(bound)), column)
        for column, (value, bound) in root.items()
    )
    return [ratio, where]


def _run_revision(
    case: EnsembleCase, vector: Mapping[str, float], clock: _Clock, out: dict[str, Any]
) -> None:
    document = case.document()
    binding = clock.phase("compile", bind_revision_flowsheet, document)
    assert isinstance(binding, RevisionBinding), binding
    plan, _ = clock.phase("compile", revision.plan_revision, binding, case.policy)
    assert isinstance(plan, ExecutionPlan), plan
    run: PlanResult = clock.phase(
        "solve",
        execute_plan,
        plan=plan,
        flowsheet=binding.flowsheet,
        spec=binding.spec,
        policy=case.policy,
        user_start=vector,
    )
    (step,) = [step for step in run.steps if step.kind == "solve_eo"]
    detail = step.detail
    provenance = (
        [str(item["initializer_source"]) for item in detail.branch_provenance]
        if isinstance(detail, RegionResult)
        else []
    )
    out.update(
        outcome=run.outcome,
        message=_first_line(run.message),
        attempts=len(detail.attempts) if isinstance(detail, RegionResult) else 0,
        iterations=step.iterations,
        counters=asdict(run.counters),
        events=_events(run.trace.events),
        eo_recovery=step.eo_recovery,
        eo_recovery_unsupported=step.eo_recovery_unsupported,
        first_outcome=None if step.recovered_from is None else step.recovered_from.outcome,
        sources=provenance,
        refinements=refinements(run.trace.events),
    )
    if run.outcome != "CONVERGED" or run.state is None:
        return
    out["state"] = [[name, run.state[name]] for name in binding.spec.variable_ids]
    captured: list[tuple[sp.csc_matrix, Any]] = []
    with captured_screens(captured):
        certificate = clock.phase(
            "verify",
            verify_revision,
            binding,
            document,
            run,
            solve_plan=plan.steps[-1].solve_plan,
        )
    _certified(out, certificate, captured, binding.flowsheet.provider, run.state, case.root)


def _run_tear(
    case: EnsembleCase, vector: Mapping[str, float], clock: _Clock, out: dict[str, Any]
) -> None:
    document = case.document()
    binding = clock.phase("compile", bind_revision, document)
    assert isinstance(binding, Binding), binding
    flowsheet = binding.flowsheet
    recycle = [vector[flow_id(TEAR_STREAM, component)] for component in flowsheet.components]
    result, trace = clock.phase(
        "solve", solve_tear, flowsheet, initial_recycle=recycle, policy=case.policy
    )
    out.update(
        outcome=result.outcome,
        message=_first_line(result.message),
        attempts=result.attempts,
        iterations=result.iterations,
        counters=asdict(result.counters),
        events=_events(trace.events),
        eo_recovery=None,
        eo_recovery_unsupported=None,
        first_outcome=None,
        sources=[],
        refinements=refinements(trace.events),
    )
    if result.outcome != "CONVERGED" or result.final_state is None:
        return
    state = result.final_state
    out["state"] = [[name, state[name]] for name in binding.spec.variable_ids]
    captured: list[tuple[sp.csc_matrix, Any]] = []
    with captured_screens(captured):
        certificate = clock.phase("verify", verify, flowsheet, result)
    _certified(out, certificate, captured, flowsheet.provider, state, case.root)


def _run_legacy(
    case: EnsembleCase, vector: Mapping[str, float], clock: _Clock, out: dict[str, Any]
) -> None:
    document = copy.deepcopy(case.document())
    (guess,) = [
        entry
        for entry in document["specifications"]
        if entry["id"] == generator.GUESS_SPECIFICATION
    ]
    guess["value"] = vector[generator.GUESS_COORDINATE]
    binding = clock.phase("compile", bind_revision, document)
    assert isinstance(binding, Binding), binding
    plan, _ = clock.phase("compile", _legacy_plan, binding, case.policy)
    run: PlanResult = clock.phase(
        "solve",
        execute_plan,
        plan=plan,
        flowsheet=binding.flowsheet,
        spec=binding.spec,
        policy=case.policy,
    )
    (step,) = [step for step in run.steps if step.kind == "solve_eo"]
    (planned,) = [step for step in plan.steps if step.kind == "solve_eo"]
    detail = step.detail
    out.update(
        outcome=run.outcome,
        message=_first_line(run.message),
        attempts=len(detail.attempts) if isinstance(detail, RegionResult) else 0,
        iterations=step.iterations,
        counters=asdict(run.counters),
        events=_events(run.trace.events),
        eo_recovery=step.eo_recovery,
        eo_recovery_unsupported=step.eo_recovery_unsupported,
        first_outcome=None if step.recovered_from is None else step.recovered_from.outcome,
        sources=(
            [str(item["initializer_source"]) for item in detail.branch_provenance]
            if isinstance(detail, RegionResult)
            else []
        ),
        refinements=refinements(run.trace.events),
    )
    if run.outcome != "CONVERGED" or not isinstance(detail, RegionResult):
        return
    state = dict(detail.state)
    out["state"] = [[name, state[name]] for name in binding.spec.variable_ids]
    captured: list[tuple[sp.csc_matrix, Any]] = []
    with captured_screens(captured):
        certificate = clock.phase(
            "verify", verify_bound, binding, document, detail, solve_plan=planned.solve_plan
        )
    _certified(out, certificate, captured, binding.flowsheet.provider, state, case.root)


def _certified(
    out: dict[str, Any],
    certificate: SolutionCertificate,
    captured: Sequence[tuple[sp.csc_matrix, Any]],
    provider: Any,
    state: Mapping[str, float],
    root: Mapping[str, tuple[Decimal, float]],
) -> None:
    out["certificate"] = _certificate(certificate)
    out["a32"] = [exact_norm_check(matrix, evidence) for matrix, evidence in captured]
    out["a33"] = _a33(certificate, provider)
    out["worst"] = _worst(state, root)


def run_start(case: EnsembleCase, start: Mapping[str, Any]) -> dict[str, Any]:
    """One published start, cold, recorded (§6.6). An exception that is not a typed outcome is
    recorded as a crash with the phase it escaped from; it never propagates — except
    `RefinementGrammarError`, a harness defect that stops the run (§6.6 (A5))."""
    vector = {name: float(value) for name, value in start["vector"].items()}
    out: dict[str, Any] = {
        "case": case.case,
        "fixture": case.fixture,
        "path": case.path,
        "policy": case.policy.policy_id,
        "start": int(start["start"]),
        "generation_failure": None,
        "crash": None,
        "outcome": None,
        "certificate": None,
        "refinements": [],
    }
    clock = _Clock()
    began = time.perf_counter()
    runner = {"revision_eo": _run_revision, "tear": _run_tear, "legacy_eo": _run_legacy}[case.path]
    try:
        with _instrumented(clock):
            runner(case, vector, clock, out)
    except RefinementGrammarError:
        raise
    except Exception as error:  # recorded, never handled: F-CRASH is a defect (§7.2)
        phase = clock.stack[-1][0] if clock.stack else "harness"
        out["crash"] = f"{phase}: {type(error).__name__}: {_first_line(str(error))}"
    total = time.perf_counter() - began
    out["times"] = {**{k: v for k, v in clock.buckets.items()}, "total": total}
    return out


def generation_failure_record(case: EnsembleCase, failure: Mapping[str, Any]) -> dict[str, Any]:
    """`F-GEN` (§6.4): a start the published file records as not generated."""
    return {
        "case": case.case,
        "fixture": case.fixture,
        "path": case.path,
        "policy": case.policy.policy_id,
        "start": int(failure["start"]),
        "generation_failure": str(failure["reason"]),
        "crash": None,
        "outcome": None,
        "certificate": None,
        "refinements": [],
        "times": {"compile": 0.0, "init": 0.0, "solve": 0.0, "verify": 0.0, "total": 0.0},
    }


# -- scoring (§7.1–§7.2) -----------------------------------------------------------------------


def classify(record: Mapping[str, Any], ceiling_s: float = CEILING_S) -> str:
    """§7.2's class of a start, or `SUCCESS` (§7.1); first match wins. A pure function of the
    record (A27)."""
    if record["generation_failure"] is not None:
        return "F-GEN"
    if record["crash"] is not None:
        return "F-CRASH"
    if record["times"]["total"] > ceiling_s:
        return "F-TIME"
    outcome = record["outcome"]
    if outcome != "CONVERGED":
        if TAXONOMY.get(outcome) == "budget/cancellation outcomes":
            return "F-BUDGET"
        return f"F-TYPED({outcome})"
    certificate = record["certificate"]
    if certificate is None:
        raise ValueError(f"{record['case']} start {record['start']}: converged, not certified")
    verdict = certificate["verdict"]
    if verdict == "FAILED":
        return "F-FALSE-SUCCESS-CAUGHT"
    if verdict != "VERIFIED":
        reason = (
            certificate["regularity_status"]
            if certificate["regularity_status"] != "NO_RANK_LOSS_DETECTED"
            else ",".join(certificate["not_passed"][:3]) or verdict
        )
        return f"F-UNVERIFIED({reason})"
    if record["worst"][0] > 1.0:
        return "F-OTHER-ROOT"
    return "SUCCESS"


def rescued(record: Mapping[str, Any]) -> bool:
    """A66: the trace has `eo_recovery: taken` and a provenance item from the restart."""
    return record.get("eo_recovery") == "taken" and revision.RESTART_INITIALIZER_ID in (
        record.get("sources") or []
    )


def clopper_pearson_lower(successes: int, trials: int, alpha: float = CP_ALPHA) -> float:
    """§7.4: the one-sided `1 − α` Clopper–Pearson lower bound on `successes/trials`."""
    if successes == 0:
        return 0.0
    return float(beta.ppf(alpha, successes, trials - successes + 1))


def _distribution(values: Sequence[float | None]) -> dict[str, float | None]:
    """Median, 95th percentile (linear interpolation) and maximum; `None` when empty."""
    finite = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    if not finite:
        return {"median": None, "p95": None, "max": None, "n": 0}
    array = np.array(finite)
    return {
        "median": float(np.median(array)),
        "p95": float(np.percentile(array, 95)),
        "max": float(array.max()),
        "n": len(finite),
    }


def _census(records: Sequence[Mapping[str, Any]], scales: Mapping[str, float]) -> int:
    """§7.4: the distinct root fingerprints among a case's `VERIFIED` runs (T03 §8.3's
    `same_root`; the D11 branch census)."""
    roots: list[tuple[Mapping[str, Any], dict[str, float], list[str]]] = []
    for record in records:
        certificate = record["certificate"]
        if certificate is None or certificate["verdict"] != "VERIFIED":
            continue
        fingerprint = certificate["root_fingerprint"]
        if fingerprint is None:  # ADR 0005 D7: a converged certificate carries one
            continue
        ids = [name for name, _ in record["state"]]
        state = {name: float(value) for name, value in record["state"]}
        if not any(
            same_root(fingerprint, state, other, other_state, scales, ids) == "SAME"
            for other, other_state, _ in roots
        ):
            roots.append((fingerprint, state, ids))
    return len(roots)


def _property_budget(record: Mapping[str, Any]) -> bool:
    """The start ended `BUDGET_EXHAUSTED(property_calls)` (ADR 0018 D5′: the meter's message)."""
    return record.get("outcome") == "BUDGET_EXHAUSTED" and str(
        record.get("message") or ""
    ).startswith(PROPERTY_BUDGET_MESSAGE)


def _refinement_counts(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """A90 (A5): fired, kept (`accepted`), reverted and abandoned, the abandoned by `reason`, and
    *abandoned (budget)* — abandoned in the last attempt of a start that ended
    `BUDGET_EXHAUSTED(property_calls)`."""
    counts: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    for record in records:
        for entry in record["refinements"]:
            if not entry["fired"]:
                continue
            counts["fired"] += 1
            counts[{"accepted": "kept"}.get(entry["result"], entry["result"])] += 1
            if entry["result"] == "abandoned":
                reasons[entry["reason"]] += 1
                counts["abandoned_budget"] += entry["last"] and _property_budget(record)
    keys = ("fired", "kept", "reverted", "abandoned", "abandoned_budget")
    return {
        **{key: counts[key] for key in keys},
        "abandoned_by_reason": dict(sorted(reasons.items())),
    }


def _refinements(records: Sequence[Mapping[str, Any]], ceiling_s: float) -> dict[str, Any] | None:
    """A90 (A5) over a run: the counts; every fired refinement with where it fired; those whose
    attempt was not the start's last (ADR 0018 D4′ (ii)'s route); and S3's worst ratio over the
    `SUCCESS` and `F-OTHER-ROOT` starts whose final attempt kept its refinement, or did not fire
    (reported). `None` when a record carries no `refinements` (a v1 file: not recorded)."""
    if any("refinements" not in record for record in records):
        return None
    fired: list[list[Any]] = []
    worst: dict[str, list[float]] = {"kept": [], "not_fired": []}
    for record in records:
        for entry in record["refinements"]:
            if entry["fired"]:
                fired.append(
                    [
                        record["case"],
                        record["start"],
                        entry["step"],
                        entry["attempt"],
                        entry["result"],
                        entry["reason"],
                        entry["last"],
                    ]
                )
        final = record["refinements"][-1] if record["refinements"] else None
        if final is None or classify(record, ceiling_s) not in ("SUCCESS", "F-OTHER-ROOT"):
            continue
        if not final["fired"]:
            worst["not_fired"].append(float(record["worst"][0]))
        elif final["result"] == "accepted":
            worst["kept"].append(float(record["worst"][0]))
    return {
        **_refinement_counts(records),
        "fired_at": fired,
        "not_last": [entry for entry in fired if not entry[6]],
        "worst_ratio": {key: _distribution(values) for key, values in worst.items()},
    }


def report(
    records: Sequence[Mapping[str, Any]],
    cases: Mapping[str, Mapping[str, Any]],
    starts: Mapping[str, Any],
    ceiling_s: float = CEILING_S,
) -> dict[str, Any]:
    """§7.3–§7.4's reports, recomputed from the records (A31): per case the rates, classes,
    branch census, the numerical and cost distributions; overall the gate, both Clopper–Pearson
    bounds, the acyclic census and the shifted geometric mean of total time (shift 10 ms).
    `cases` maps each case id to `{acyclic, column_scales}`; `starts` is the published file."""
    conditioning = {
        (case["case"], record["start"]): record["conditioning"]
        for case in starts["cases"]
        for record in case["starts"]
    }
    per_case: dict[str, dict[str, Any]] = {}
    classes_all: Counter[str] = Counter()
    order = [entry["case"] for entry in starts["cases"] if entry["case"] in cases]
    for case_id in order:
        mine = [r for r in records if r["case"] == case_id]
        classes = Counter(classify(r, ceiling_s) for r in mine)
        classes_all.update(classes)
        successes = [r for r in mine if classify(r, ceiling_s) == "SUCCESS"]
        s_rescued = sum(1 for r in successes if rescued(r))
        certified = [r for r in mine if r["certificate"] is not None]
        per_case[case_id] = {
            "n": len(mine),
            "s": len(successes),
            "s_first": len(successes) - s_rescued,
            "s_rescued": s_rescued,
            "p": len(successes) / len(mine) if mine else None,
            "p_first": (len(successes) - s_rescued) / len(mine) if mine else None,
            "acyclic": bool(cases[case_id]["acyclic"]),
            "classes": dict(sorted(classes.items())),
            "roots": _census(mine, cases[case_id]["column_scales"]),
            "numerical": {
                "iterations": _distribution([r.get("iterations") for r in mine]),
                "attempts": _distribution([r.get("attempts") for r in mine]),
                "property_calls": _distribution(
                    [(r.get("counters") or {}).get("property_calls") for r in mine]
                ),
                "recovery_edges": _distribution(
                    [1.0 if r.get("eo_recovery") == "taken" else 0.0 for r in mine]
                ),
                "rcond_1": _distribution([r["certificate"]["rcond_1"] for r in certified]),
                "b": _distribution([r["certificate"]["b"] for r in certified]),
                "start_residual_inf_scaled": _distribution(
                    [
                        conditioning[(case_id, r["start"])]["residual_inf_scaled"]
                        for r in mine
                        if (case_id, r["start"]) in conditioning
                    ]
                ),
            },
            "cost": {
                phase: _distribution([r["times"][phase] for r in mine])
                for phase in ("compile", "init", "solve", "verify", "total")
            },
            "refinements": (
                _refinement_counts(mine) if all("refinements" in r for r in mine) else None
            ),
        }
    total = len(records)
    s = sum(case["s"] for case in per_case.values())
    s_first = sum(case["s_first"] for case in per_case.values())
    acyclic_ids = [case_id for case_id, case in per_case.items() if case["acyclic"]]
    totals = [r["times"]["total"] for r in records]
    shift = 0.010
    geometric = (
        math.exp(sum(math.log(t + shift) for t in totals) / len(totals)) - shift if totals else None
    )
    ratios = [
        check["ratio"]
        for r in records
        for check in (r.get("a32") or [])
        if check.get("ratio") is not None
    ]
    return {
        "N": total,
        "S": s,
        "S_first": s_first,
        "S_rescued": s - s_first,
        "cp_lower": clopper_pearson_lower(s, total) if total else None,
        "cp_lower_first": clopper_pearson_lower(s_first, total) if total else None,
        "gate": {
            "S_min": S_MIN,
            "registered_N": N,
            "complete": total == N,
            "pass": total == N
            and s >= S_MIN
            and classes_all.get("F-CRASH", 0) == 0
            and classes_all.get("F-OTHER-ROOT", 0) == 0,
        },
        "classes": dict(sorted(classes_all.items())),
        "cases_p1": sum(1 for c in per_case.values() if c["p"] == 1.0),
        "cases_below_1": sum(1 for c in per_case.values() if c["p"] is not None and c["p"] < 1.0),
        "cases_below_0p8": sum(1 for c in per_case.values() if c["p"] is not None and c["p"] < 0.8),
        "acyclic": acyclic_ids,
        "all_cases": len(order) == len(starts["cases"]),
        "shifted_geometric_mean_total_s": geometric,
        "a32": {
            "matrices": len(ratios),
            "ratio": _distribution(ratios),
            "not_lower": sum(
                1 for r in records for c in (r.get("a32") or []) if c.get("lower") is False
            ),
            "disagreements": sum(
                1 for r in records for c in (r.get("a32") or []) if not c.get("agree", True)
            ),
        },
        "a33_failures": sum(1 for r in records if r.get("a33") and not r["a33"]["ok"]),
        "refinements": _refinements(records, ceiling_s),
        "per_case": per_case,
    }


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}g}"
    return str(value)


def _headline(summary: Mapping[str, Any], holdout: Mapping[str, Any] | None) -> list[str]:
    """The heading and the `N`/`S` line: the nominal report's gate line (§7.3), or the holdout's
    header and `S_holdout − S_run2` for its class, with no gate line (§7.6 (A5))."""
    counts = (
        f"N = {summary['N']}; S = {summary['S']} (S^first = {summary['S_first']}, "
        f"S^rescued = {summary['S_rescued']})"
    )
    if holdout is None:
        return [
            "# T06 robustness ensemble — nominal profile",
            "",
            f"{counts}; gate S >= {summary['gate']['S_min']} of "
            f"{summary['gate']['registered_N']}, no F-CRASH, no unexplained F-OTHER-ROOT: "
            f"{'PASS' if summary['gate']['pass'] else 'FAIL'}"
            + ("" if summary["gate"]["complete"] else " (incomplete run: not a gate evaluation)"),
        ]
    s_run2 = holdout["s_run2"]
    difference = (
        f"S_holdout − S_run2 = {summary['S'] - s_run2:+d} (run 2 on {holdout['machine_class']}: "
        f"S = {s_run2})"
        if s_run2 is not None
        else f"S_holdout − S_run2: run 2 has no registered file on {holdout['machine_class']}"
    )
    return ["# " + HOLDOUT_HEADER.format(run_id=holdout["run_id"]), "", f"{counts}; {difference}."]


def _provenance_line(run: Mapping[str, Any]) -> str:
    """§6.6 (A5): a v2 file's run id, commit, clean-tree flag and machine class."""
    return (
        f"Run {run['run_id']} at {run['commit']} (tree clean: "
        f"{'yes' if run['tree_clean'] else 'NO — never evidence'}), machine class "
        f"{run['machine_class']}, starts {run['starts_sha256']}."
    )


def _refinement_lines(summary: Mapping[str, Any]) -> list[str]:
    """A90 (A5): the counts, overall and per case, the fired refinements outside a start's last
    attempt, where each refinement fired, and S3's worst ratio by the final attempt's refinement
    (reported)."""
    counted = summary["refinements"]
    if counted is None:
        return ["", "Refinements (ADR 0018; A90 (A5)): not recorded."]
    worst = counted["worst_ratio"]
    lines = [
        "",
        f"Refinements (ADR 0018; A90 (A5)): fired {counted['fired']}, kept {counted['kept']}, "
        f"reverted {counted['reverted']}, abandoned {counted['abandoned']} (by reason "
        f"{counted['abandoned_by_reason']}; abandoned (budget) {counted['abandoned_budget']}).",
        f"Fired outside a start's last attempt (ADR 0018 D4′ (ii)): {len(counted['not_last'])}"
        + "".join(
            f"; {case} {start:02d} step {step} attempt {attempt} {result}"
            for case, start, step, attempt, result, _, _ in counted["not_last"]
        )
        + ".",
        "Fired at: "
        + (
            ", ".join(
                f"{case}/{start:02d} {result}{'' if last else ' (not last)'}"
                for case, start, _, _, result, _, last in counted["fired_at"]
            )
            or "none"
        )
        + ".",
        f"S3's worst ratio over SUCCESS and F-OTHER-ROOT (reported): final attempt kept its "
        f"refinement, max {_fmt(worst['kept']['max'])} over {worst['kept']['n']}; did not fire, "
        f"max {_fmt(worst['not_fired']['max'])} over {worst['not_fired']['n']}.",
        "",
        "| case | fired | kept | reverted | abandoned | abandoned (budget) |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for case_id, case in summary["per_case"].items():
        counts = case["refinements"]
        lines.append(
            f"| {case_id} | {counts['fired']} | {counts['kept']} | {counts['reverted']} | "
            f"{counts['abandoned']} | {counts['abandoned_budget']} |"
        )
    return lines


def render(
    summary: Mapping[str, Any],
    *,
    run: Mapping[str, Any] | None = None,
    holdout: Mapping[str, Any] | None = None,
) -> str:
    """The report as text (§7.4 (A2)'s wording verbatim). `run` is a v2 file's provenance
    (`run_id`, `commit`, `tree_clean`, `machine_class`, `starts_sha256`; §6.6 (A5)). `holdout`,
    for the holdout (§7.6 (A5)), is `{run_id, machine_class, s_run2}`: its header replaces the
    nominal one and `S_holdout − S_run2` replaces the gate line."""
    per_case = summary["per_case"]
    acyclic_ids = summary["acyclic"]
    lines = [
        *_headline(summary, holdout),
        *([_provenance_line(run)] if run is not None else []),
        f"One-sided 95 % Clopper–Pearson lower bound: on S {_fmt(summary['cp_lower'], 6)}; "
        f"on S^first {_fmt(summary['cp_lower_first'], 6)} (reported, never gated).",
        f"Classes: {summary['classes']}",
        f"Cases with p_c = 1: {summary['cases_p1']}; p_c < 1: {summary['cases_below_1']}; "
        f"p_c < 0.8: {summary['cases_below_0p8']}.",
        "",
        DESIGNS_STATEMENT,
        "",
        RESCUE_STATEMENT,
        "",
        ACYCLIC_STATEMENT.format(n=len(acyclic_ids), ids=", ".join(acyclic_ids)),
    ]
    if summary["all_cases"] and len(acyclic_ids) != ACYCLIC_TEXT_COUNT:
        lines += [
            "",
            f"The specification's text (§6.2, §15) says {ACYCLIC_TEXT_COUNT} acyclic cases; the "
            f"plans count {len(acyclic_ids)}. This is a finding against the text (A84), not a "
            "reason to change the flag.",
        ]
    lines += [
        "",
        "| case | acyclic | s_c/20 | s_c^first/20 | s_c^rescued | classes | roots |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for case_id, case in per_case.items():
        lines.append(
            f"| {case_id} | {'yes' if case['acyclic'] else 'no'} | {case['s']}/{case['n']} | "
            f"{case['s_first']}/{case['n']} | {case['s_rescued']} | "
            f"{', '.join(f'{k} {v}' for k, v in case['classes'].items())} | {case['roots']} |"
        )
    lines += [
        "",
        "Numerical report (median / p95 / max):",
        "",
        "| case | iterations | attempts | property calls | edges | rcond_1 | b | start ‖F̂‖∞ |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for case_id, case in per_case.items():
        numbers = case["numerical"]
        cells = [
            " / ".join(_fmt(numbers[key][q]) for q in ("median", "p95", "max"))
            for key in (
                "iterations",
                "attempts",
                "property_calls",
                "recovery_edges",
                "rcond_1",
                "b",
                "start_residual_inf_scaled",
            )
        ]
        lines.append(f"| {case_id} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "Cost report, seconds (median / p95 / max):",
        "",
        "| case | compile | init | solve | verify | total |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for case_id, case in per_case.items():
        cells = [
            " / ".join(_fmt(case["cost"][phase][q]) for q in ("median", "p95", "max"))
            for phase in ("compile", "init", "solve", "verify", "total")
        ]
        lines.append(f"| {case_id} | " + " | ".join(cells) + " |")
    a32 = summary["a32"]
    lines += [
        "",
        f"Shifted geometric mean of total time (shift 10 ms): "
        f"{_fmt(summary['shifted_geometric_mean_total_s'], 4)} s. No cross-simulator cost "
        "comparison is made.",
        f"§8.3 (A32): {a32['matrices']} matrices; estimate/exact median "
        f"{_fmt(a32['ratio']['median'], 6)}, max {_fmt(a32['ratio']['max'], 6)}; "
        f"estimates above the exact norm: {a32['not_lower']}; status disagreements: "
        f"{a32['disagreements']}. A33 failures: {summary['a33_failures']}.",
        *_refinement_lines(summary),
    ]
    return "\n".join(lines) + "\n"


# -- replay (§10) ------------------------------------------------------------------------------


def replayable(record: Mapping[str, Any]) -> dict[str, Any]:
    """The record without its wall times (volatile)."""
    return {key: value for key, value in record.items() if key != "times"}


def replay_differences(recorded: Mapping[str, Any], emitted: Mapping[str, Any]) -> list[str]:
    """§10: R0 fields exactly, floats under `K04-numerical-policy-v1`. A v1 record carries no
    `refinements` (not recorded, §6.6 (A5)), so the replay's are not compared with it."""
    replayed = replayable(emitted)
    if "refinements" not in recorded:
        replayed.pop("refinements", None)
    return differences(replayed, replayable(recorded), policy_id="K04-numerical-policy-v1")


# -- run 2r against run 2 (A98) ----------------------------------------------------------------


def _bits(state: Sequence[Sequence[Any]] | None) -> list[tuple[str, str]] | None:
    return None if state is None else [(str(n), float(v).hex()) for n, v in state]


def a98_discrepancies(
    rerun: Mapping[str, Any],
    run2: Mapping[str, Any],
    expected: Sequence[tuple[str, int]] | None = None,
) -> dict[str, Any]:
    """A98 (b)–(c): run 2r (a v2 document) against run 2's same-class file. A **discrepancy** is a
    start whose class differs, a different `S` or `S^first`, a different starts file or policy
    hash, a record missing on either side, a dirty tree, or — where `expected` is given (A90 (A5)'s
    `ref-x86-64` reconstruction) — refinements other than exactly one fired and kept, in the
    start's last attempt, at each expected start and nowhere else. Final states that differ
    bitwise are counted and listed, and reported only."""
    problems: list[str] = []
    if rerun.get("format") != RESULTS_FORMAT:
        problems.append(f"format {rerun.get('format')!r}: A98 needs a v2 record")
    if rerun.get("tree_clean") is not True:
        problems.append("tree_clean is not true: a dirty-tree record is never evidence")
    for field in ("starts_sha256", "policies"):
        if rerun[field] != run2[field]:
            problems.append(f"{field}: {rerun[field]} vs run 2's {run2[field]}")
    ours = {(r["case"], r["start"]): r for r in rerun["records"]}
    theirs = {(r["case"], r["start"]): r for r in run2["records"]}
    for key in sorted(set(ours) ^ set(theirs)):
        problems.append(
            f"{key[0]} {key[1]:02d}: recorded in {'run 2r' if key in ours else 'run 2'} only"
        )
    common = sorted(set(ours) & set(theirs))
    states: list[str] = []
    for key in common:
        mine, judged = classify(ours[key]), classify(theirs[key])
        if mine != judged:
            problems.append(f"{key[0]} {key[1]:02d}: class {mine}, run 2 {judged}")
        if _bits(ours[key].get("state")) != _bits(theirs[key].get("state")):
            states.append(f"{key[0]} {key[1]:02d}")

    def headline(records: Mapping[tuple[str, int], Mapping[str, Any]]) -> tuple[int, int]:
        successes = [r for r in records.values() if classify(r) == "SUCCESS"]
        return len(successes), sum(1 for r in successes if not rescued(r))

    (s, s_first), (s_run2, s_first_run2) = headline(ours), headline(theirs)
    if (s, s_first) != (s_run2, s_first_run2):
        problems.append(f"S = {s} (S^first {s_first}), run 2 S = {s_run2} (S^first {s_first_run2})")
    fired = {
        key: [entry for entry in record.get("refinements", []) if entry["fired"]]
        for key, record in ours.items()
    }
    counts = _refinement_counts(list(ours.values()))
    if expected is not None:
        for key in sorted(set(expected) | {key for key, entries in fired.items() if entries}):
            entries = fired.get(key, [])
            wanted = key in expected
            if not wanted or [(e["result"], e["last"]) for e in entries] != [("accepted", True)]:
                problems.append(
                    f"{key[0]} {key[1]:02d}: refinements "
                    f"{[(e['result'], e['reason'], e['last']) for e in entries]}, expected "
                    f"{'one kept in the last attempt' if wanted else 'none'} (A90 (A5))"
                )
    return {
        "discrepancies": problems,
        "S": [s, s_run2],
        "S_first": [s_first, s_first_run2],
        "starts": len(common),
        "state_bitwise_differences": states,
        "refinements": counts,
    }


def policies(cases: Sequence[EnsembleCase]) -> dict[str, str]:
    """Each policy the campaign runs, by id, with its canonical document hash (§6.6)."""
    return {case.policy.policy_id: policy_sha256(case.policy) for case in cases}
