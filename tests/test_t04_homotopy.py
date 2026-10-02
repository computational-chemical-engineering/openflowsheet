"""T04 W2: the typed homotopy as the core of one region attempt (T04 §4; ADR 0010 D2, D6, D7).

A02 (endpoint identity), A03 (λ < 1 is never target-verified), A12 (records), A28 (the λ-trial
budget), and the homotopy half of A04–A08: every λ-trial of HOM-01…05 against
`benchmarks/t04/reference_values.yaml` — the design lane's 40-digit twin, never this code's output.

The core is exercised here **directly**: the failed contract solve, then a recovery region solve
from its item-0 opening (`RecoveryStart`), with no plan executor in between, so a failure points
at the homotopy and not at edge 3's wiring (that is `test_t04_edge3.py`). Tolerances are T04 §12's:
λ values, verdicts, outcomes and counts exact; temperatures on the path 1e-9 relative; final states
T02 A28's per-kind allowances.

What is observed and not on the trace — which compiled instance each residual and Jacobian call
went to, under which context, and which declaration each λ-level was compiled from — is recorded by
wrappers that delegate every call unchanged.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import re
from dataclasses import dataclass, field, replace
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml
from jsonschema import Draft202012Validator

from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.compiled import EvaluationContext
from openflowsheet.orchestrator.homotopy import (
    HomotopyRecord,
    continuation_parameter,
    level_values,
    rebind,
)
from openflowsheet.orchestrator.region import (
    RecoveryStart,
    RegionResult,
    solve_region,
    syn001_lifted_splits,
)
from openflowsheet.orchestrator.tear import solve_tear
from openflowsheet.orchestrator.trace import (
    Checkpoint,
    GlobalizationPolicy,
    HomotopyPolicy,
    SolvePolicy,
    Trace,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CASES = REPO_ROOT / "benchmarks" / "syn001" / "cases"
#: Every A02 case differs from this revision only in its guess and its flash duty (T02 §7.3).
BASE = "SYN-001-A02-355-dew-guess"
CONTINUED = "SPEC:SPEC-flash-duty"
RELATIVE = 1e-9
TEMPERATURE, DUTY, FLOW = 1e-5, 1e-2, 3.1e-7
FRACTION = re.compile(r"^(0|[1-9][0-9]*)(/[1-9][0-9]*)?$")
HOM = ("HOM-01", "HOM-02", "HOM-03", "HOM-04", "HOM-05")


@pytest.fixture(scope="module")
def ref() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(
        (REPO_ROOT / "benchmarks" / "t04" / "reference_values.yaml").read_text()
    )
    return loaded


def registered(case_id: str) -> dict[str, Any]:
    reference = yaml.safe_load(
        (REPO_ROOT / "benchmarks" / "t04" / "reference_values.yaml").read_text()
    )
    case: dict[str, Any] = reference["policy_simulation"]["homotopy_cases"][case_id]
    return case


def revision_document(case_id: str) -> dict[str, Any]:
    """The case's revision: the A02 base with the registered guess and flash duty.

    HOM-02 and HOM-03 are new revisions (T04 §13.1, registered by W10) and HOM-04/HOM-05 are
    policy overrides of existing ones; each is fully defined by the YAML's `guess_S3_T_K` and
    `Q_flash_spec_W`, so all five are built the same way from one base."""
    case = registered(case_id)
    document: dict[str, Any] = copy.deepcopy(yaml.safe_load((CASES / f"{BASE}.yaml").read_text()))
    document["revision_id"] = f"{case['registry_id']}-t04-test"
    for entry in document["specifications"]:
        if entry["id"] == "GUESS-heater-outlet-T":
            entry["value"] = float(case["guess_S3_T_K"])
        elif entry["id"] == "SPEC-flash-duty":
            entry["value"] = float(case["Q_flash_spec_W"])
    return document


def case_policy(case_id: str, **globalization: Any) -> SolvePolicy:
    overrides = registered(case_id)["policy_overrides"] or {}
    return SolvePolicy(
        policy_id=f"T04-{case_id}",
        residual_tolerances={},
        scales={},
        globalization=GlobalizationPolicy(**globalization),
        **overrides,
    )


class Spied:
    """A compiled problem that records every residual and Jacobian call — the instance, the λ-trial
    open on the trace at the time, and the context — and delegates it unchanged."""

    def __init__(self, inner: Any, label: str, calls: list[tuple[Any, ...]], trace: Trace) -> None:
        self._inner, self.label, self._calls, self._trace = inner, label, calls, trace
        self.metadata = inner.metadata

    def residual(self, x: Any, context: EvaluationContext) -> Any:
        self._calls.append((self.label, self._trace._level, "residual", context))
        return self._inner.residual(x, context)

    def jacobian(self, x: Any, context: EvaluationContext) -> Any:
        self._calls.append((self.label, self._trace._level, "jacobian", context))
        return self._inner.jacobian(x, context)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


@dataclass
class Direct:
    case_id: str
    spec: ProblemSpec
    target: Any
    failed: RegionResult
    recovery: RegionResult
    trace: Trace
    #: (label, λ-trial index or None, "residual" | "jacobian", context), in call order
    calls: list[tuple[Any, ...]] = field(default_factory=list)
    #: every declaration a λ-level was compiled from, in order
    levels: list[ProblemSpec] = field(default_factory=list)

    @property
    def record(self) -> HomotopyRecord:
        assert self.recovery.homotopy is not None
        return self.recovery.homotopy

    def temperature(self, x: Any) -> float:
        return float(x[self.record.variable_ids.index("S3.T")])


def direct(
    case_id: str,
    policy: SolvePolicy | None = None,
    *,
    from_end_state: bool = False,
) -> Direct:
    """The contract's region solve, then edge 3's recovery solve by hand (T04 §5.3)."""
    from test_t02_a02 import structure, the_region

    item = structure(revision_document(case_id))
    flowsheet = item.binding.flowsheet
    spec = item.binding.spec
    policy = policy or case_policy(case_id)
    pre, _ = solve_tear(flowsheet, policy=policy)
    assert pre.final_state is not None
    region = the_region(item)
    splits = syn001_lifted_splits(flowsheet.components)
    target = compile_problem(spec)
    failed = solve_region(
        compiled=target,
        spec=spec,
        region=region,
        state=dict(pre.final_state),
        splits=splits,
        provider=flowsheet.provider,
        policy=policy,
        initializer_source="user_guess",
    )
    continuation = continuation_parameter(
        specification_rows=region.specification_rows,
        target_variables=region.target_variables,
        spec=spec,
        structural_pattern=target.structural_pattern(),
    )
    assert continuation is not None and failed.opening is not None
    state, regimes = failed.opening
    if from_end_state:
        state = failed.state
    trace = Trace()
    seen = Direct(case_id, spec, target, failed, None, trace)  # type: ignore[arg-type]

    def compile_level(level_spec: ProblemSpec) -> Any:
        seen.levels.append(level_spec)
        return Spied(compile_problem(level_spec), f"level-{len(seen.levels)}", seen.calls, trace)

    seen.recovery = solve_region(
        compiled=Spied(target, "target", seen.calls, trace),  # type: ignore[arg-type]
        spec=spec,
        region=region,
        state=dict(state),
        splits=splits,
        provider=flowsheet.provider,
        policy=policy,
        trace=trace,
        initializer_source=None,
        recovery=RecoveryStart(state, regimes, continuation, "user_guess"),
        compile_level=compile_level,
    )
    return seen


_RUNS: dict[str, Direct] = {}


def run(case_id: str) -> Direct:
    """One run per registered case per session; the tests below only read it."""
    if case_id not in _RUNS:
        _RUNS[case_id] = direct(case_id)
    return _RUNS[case_id]


def close(value: float, expected: Any, relative: float = RELATIVE) -> bool:
    target = float(expected)
    return abs(value - target) <= relative * max(1.0, abs(target))


# ------------------------------------------------------------------ the registered paths


@pytest.mark.parametrize("case_id", HOM)
def test_the_lambda_path_is_the_registered_one(case_id: str) -> None:
    """Every λ-trial of `ref.hom.<case>.homotopy.steps`: λ, Δλ, the corrector's outcome and
    iteration count, the verdict, and the corrector's end temperature (the discarded one, on a
    rejection) — then the outcome, λ reached and the reported state."""
    seen = run(case_id)
    expected = registered(case_id)["homotopy"]
    record = seen.record
    assert seen.recovery.outcome == expected["outcome"] == registered(case_id)["outcome"]
    assert len(record.trials) - 1 == expected["lambda_trials"]
    assert len(record.trials) == len(expected["steps"])
    for trial, step in zip(record.trials, expected["steps"], strict=True):
        result = trial.corrector.result
        where = (case_id, trial.index)
        assert str(trial.lambda_value) == str(step["lambda"]), where
        assert str(trial.delta_lambda) == str(step["delta_lambda"]), where
        assert result.outcome == step["corrector_outcome"], where
        assert result.iterations == step["corrector_iterations"], where
        assert trial.accepted is step["accepted"], where
        assert close(seen.temperature(result.x), step["S3_T_K"]), where
        for landing in step.get("landings") or ():
            # T03 §4.6 inside a corrector: the step is accepted at `α_max`, the variable lands
            # on `+0.0`, and the corrector carries on past it.
            events = [
                e
                for e in seen.trace.of_kind("step_accepted")
                if e.homotopy_level == trial.index and e.iteration == landing["iteration"]
            ]
            assert len(events) == 1, where
            assert close(float(events[0].alpha), landing["alpha_max"]), where
            assert result.iterations > landing["iteration"], where
        if step.get("blocked_by"):
            assert list(result.blocked_by) == step["blocked_by"], where
    assert str(record.lambda_reached) == str(expected["lambda_reached"])
    # The reported state is the last accepted level's root (rollback), never a corrector's end.
    assert close(seen.recovery.state["S3.T"], expected["end_S3_T_K"])
    assert abs(seen.recovery.state["S3.V"] - float(expected["end_S3_V_mol_per_s"])) <= FLOW


@pytest.mark.parametrize("case_id", HOM)
def test_the_contract_before_the_edge_is_the_registered_one(case_id: str) -> None:
    """The failed solve the recovery starts from: `ref.hom.<case>.contract`, attempt by attempt."""
    seen = run(case_id)
    contract = registered(case_id)["contract"]
    assert seen.failed.outcome == contract["outcome"]
    items = seen.failed.branch_provenance
    assert len(items) == len(contract["attempts"])
    for item, attempt in zip(items, contract["attempts"], strict=True):
        signature = ",".join(f"{unit}:{regime}" for unit, regime in item["signature"])
        assert signature == attempt["signature"]
        assert item["opening_source"] == attempt["opening_source"]
        assert item["core"] == attempt["core"] == "newton"
        assert item["core_outcome"] == attempt["core_outcome"]
        assert item["iterations"] == attempt["iterations"]
        assert item["decision"] == attempt["decision"]
        if attempt["decision"] == "terminal":
            # ADR 0005 D7: a terminal item's cause is the closing message, which no specification
            # gives a grammar for; `ref` registers null and the item carries the solve's own
            # (T04 §17 F11).
            assert attempt["cause"] is None
            assert item["cause"] == seen.failed.message
        else:
            # T03 §4.10's grammar in full, byte for byte (T04 §17 F11).
            assert item["cause"] == attempt["cause"]


def test_hom_01_ends_at_t02s_355_k_row_and_the_root_newton_finds(ref: dict[str, Any]) -> None:
    """A04's final state: T02's 355 K sweep row within T02 A28's allowances, and `same_root`
    with `SYN-001-A02-355` solved by Newton from 358 K (T03 §8.3)."""
    from test_t02_a02 import solve

    from openflowsheet.numerics.scaling import Scaling
    from openflowsheet.orchestrator.roots import same_root

    t02 = yaml.safe_load((REPO_ROOT / "benchmarks" / "t02" / "reference_values.yaml").read_text())
    row = t02["syn001"]["a02_sweep"]["T_heater=355K"]
    state = run("HOM-01").recovery.state
    assert abs(state["S3.T"] - 355.0) <= TEMPERATURE
    assert abs(state["U-HEAT.Q"] - float(row["Q_heater_W"])) <= DUTY
    assert abs(state["U-FLASH.Q"] - float(row["Q_flash_W"])) <= DUTY
    for index, component in enumerate(("A", "B", "C")):
        assert abs(state[f"S3.vap.{component}"] - float(row["S3_vapor_mol_per_s"][index])) <= FLOW
        assert abs(state[f"S3.liq.{component}"] - float(row["S3_liquid_mol_per_s"][index])) <= FLOW

    newton = solve("SYN-001-A02-355")
    assert newton.outcome == "CONVERGED" and newton.root_fingerprint is not None
    fingerprint = run("HOM-01").recovery.root_fingerprint
    assert fingerprint is not None
    spec = run("HOM-01").spec
    verdict = same_root(
        fingerprint,
        state,
        newton.root_fingerprint,
        newton.state,
        Scaling.from_spec(spec).column,
        spec.variable_ids,
    )
    assert verdict == "SAME"


def test_hom_05_ends_at_t02s_360_k_row() -> None:
    t02 = yaml.safe_load((REPO_ROOT / "benchmarks" / "t02" / "reference_values.yaml").read_text())
    row = t02["syn001"]["a02_sweep"]["T_heater=360K"]
    state = run("HOM-05").recovery.state
    assert abs(state["S3.T"] - 360.0) <= TEMPERATURE
    assert abs(state["U-HEAT.Q"] - float(row["Q_heater_W"])) <= DUTY
    assert abs(state["U-FLASH.Q"] - float(row["Q_flash_W"])) <= DUTY


@pytest.mark.parametrize("case_id", ["HOM-03", "HOM-04"])
def test_a06_a07_a_stall_brackets_its_phase_boundary(case_id: str, ref: dict[str, Any]) -> None:
    """§4.6: every accepted λ below the boundary on the path, every rejected λ above it, and
    `λ_reached < λ_boundary < λ_reached + 2⁻⁹`, with the boundary's closed form from the YAML;
    the hypothesis is `phase_boundary_on_path(U-HEAT)`."""
    record = run(case_id).record
    key = "HOM-03_lambda_dew_vapor_branch" if case_id == "HOM-03" else "HOM-04_lambda_bubble"
    boundary = Fraction(ref["closed_form"]["a02"][key])
    assert record.stalled_at == "resolution"
    assert record.inferred_cause == "phase_boundary_on_path(U-HEAT)"
    assert all(t.lambda_value < boundary for t in record.trials if t.accepted)
    assert all(t.lambda_value > boundary for t in record.trials if not t.accepted)
    assert record.lambda_reached < boundary < record.lambda_reached + Fraction(1, 512)
    if case_id == "HOM-03":
        assert all(
            t.corrector.result.outcome == "PHASE_UPDATE_REQUIRED"
            for t in record.trials
            if not t.accepted
        )
    else:
        rejected = [t for t in record.trials if not t.accepted]
        assert all(t.corrector.result.outcome == "BOUND_BLOCKED" for t in rejected)
        assert all("S3.vap.C" in t.corrector.result.blocked_by for t in rejected)


# ------------------------------------------------------------------ A02: endpoint identity


@pytest.mark.parametrize("case_id", HOM)
def test_a02_every_call_carries_its_levels_identity(case_id: str) -> None:
    """The λ = 1 corrector calls the target instance under the target's identity; every λ < 1
    corrector calls a level instance with the target's `model_version` and another
    `constants_sha256`, under a context equal to the attempt's but for that field."""
    seen = run(case_id)
    identity = (seen.target.metadata.model_version, seen.target.metadata.constants_sha256)
    lambdas = {trial.index: trial.lambda_value for trial in seen.record.trials}
    corrector_calls = [call for call in seen.calls if call[1] is not None]
    assert corrector_calls
    (attempt_context,) = [c.evaluation_context for c in seen.recovery.contexts[:1]]
    for label, level, _, context in corrector_calls:
        if lambdas[level] == 1:
            assert label == "target"
            assert (context.model_version, context.constants_sha256) == identity
        else:
            assert label != "target"
            assert context.model_version == identity[0]
            assert context.constants_sha256 != identity[1]
        others = {
            f.name: getattr(context, f.name)
            for f in dataclasses.fields(context)
            if f.name != "constants_sha256"
        }
        assert others == {
            f.name: getattr(attempt_context, f.name)
            for f in dataclasses.fields(attempt_context)
            if f.name != "constants_sha256"
        }
    # Calls outside a corrector are the contract's (kernel verdicts go to the provider, not here).
    assert all(call[0] == "target" for call in seen.calls if call[1] is None)


@pytest.mark.parametrize("case_id", HOM)
def test_a02_each_level_moves_the_continued_input_and_nothing_else(case_id: str) -> None:
    """The re-binding spy: every compiled level's declaration differs from the target's only at
    `SPEC:SPEC-flash-duty` (by id), by exactly §4.2's correctly rounded `p(λ)`; λ = 1 is never
    re-bound, so `p(1) = p*` bitwise (it is the target's own parameter)."""
    seen = run(case_id)
    target = seen.spec.parameters
    opening_state, _ = seen.failed.opening  # type: ignore[misc]
    start = Fraction(opening_state["U-FLASH.Q"])
    star = Fraction(target[CONTINUED])
    compiled_lambdas = sorted({t.lambda_value for t in seen.record.trials if t.lambda_value != 1})
    assert len(seen.levels) == len(compiled_lambdas), "one compile per distinct λ < 1"
    values = sorted(level.parameters[CONTINUED] for level in seen.levels)
    for level in seen.levels:
        assert level.parameter_ids == seen.spec.parameter_ids
        changed = {k for k in target if level.parameters[k] != target[k]}
        assert changed <= {CONTINUED}
        assert level.equations == seen.spec.equations and level.blocks == seen.spec.blocks
    expected = sorted(float(star + (1 - lam) * (start - star)) for lam in compiled_lambdas)
    assert values == expected
    assert Fraction(0) in compiled_lambdas and values.count(float(start)) >= 1
    if any(t.lambda_value == 1 for t in seen.record.trials):
        assert all(level.parameters[CONTINUED] != target[CONTINUED] for level in seen.levels)


def test_a02_the_level_values_are_exact_and_refuse_lambda_one() -> None:
    from openflowsheet.orchestrator.homotopy import Continuation

    continuation = Continuation("specification_continuation", (CONTINUED,), ("U-FLASH.Q",))
    target, opening = {CONTINUED: 24681.106068625242}, {"U-FLASH.Q": -90142.27103988026}
    assert level_values(continuation, target, opening, Fraction(0)) == {
        CONTINUED: opening["U-FLASH.Q"]
    }
    quarter = level_values(continuation, target, opening, Fraction(1, 4))[CONTINUED]
    exact = Fraction(target[CONTINUED]) + Fraction(3, 4) * (
        Fraction(opening["U-FLASH.Q"]) - Fraction(target[CONTINUED])
    )
    assert quarter == float(exact)
    with pytest.raises(ValueError, match="never re-bound"):
        level_values(continuation, target, opening, Fraction(1))
    spec = run("HOM-05").spec
    with pytest.raises(ValueError, match="does not have"):
        rebind(spec, {"S3.T": 1.0})


@pytest.mark.parametrize("case_id", ["HOM-01", "HOM-02", "HOM-05"])
def test_a02_the_endpoint_residual_is_the_targets_bit_for_bit(case_id: str) -> None:
    """At the final state the λ = 1 corrector's residual equals a freshly compiled target's."""
    seen = run(case_id)
    final = seen.record.trials[-1].corrector.result
    assert seen.record.trials[-1].lambda_value == 1 and final.converged
    fresh = compile_problem(seen.spec)
    context = EvaluationContext(
        model_version=fresh.metadata.model_version,
        constants_sha256=fresh.metadata.constants_sha256,
    )
    vector = np.array([seen.recovery.state[name] for name in seen.spec.variable_ids])
    evaluated = fresh.residual(vector, context)
    assert evaluated.status == "ok" and evaluated.values is not None
    rows = list(seen.recovery.contexts[0].row_scales)
    at = {name: index for index, name in enumerate(seen.spec.equation_ids)}
    fresh_values = [evaluated.values[at[row]] for row in rows]
    assert [float(v).hex() for v in final.residual] == [float(v).hex() for v in fresh_values]


def test_a02_no_evaluation_context_field_carries_lambda() -> None:
    """ADR 0008 D1: λ never reaches the evaluation boundary — the context's field set is the
    pinned one, and a level context differs from the attempt's in `constants_sha256` alone."""
    names = {f.name for f in dataclasses.fields(EvaluationContext)}
    assert names == {
        "model_version",
        "constants_sha256",
        "phase_signature",
        "accuracy_policy",
        "workspace",
    }
    seen = run("HOM-04")
    contexts = {id(call[3]): call[3] for call in seen.calls}
    assert all(not context.workspace for context in contexts.values())


# ------------------------------------------------------------------ A03: λ < 1 not verified


@pytest.mark.parametrize(("case_id", "level"), [("HOM-03", "23/256"), ("HOM-04", "909/1024")])
def test_a03_a_stall_leaves_a_partial_checkpoint_at_its_level_and_no_certificate(
    case_id: str, level: str
) -> None:
    from test_t02_a02 import structure

    from openflowsheet.verify.certificate import verify
    from openflowsheet.verify.checks import VerifierError

    recovery = run(case_id).recovery
    assert recovery.outcome == "HOMOTOPY_STALLED"
    checkpoint = recovery.checkpoint
    assert checkpoint is not None
    assert checkpoint.continuation_lambda == level
    assert (checkpoint.label, checkpoint.verification_scope) == ("partial", "unverified")
    assert recovery.root_fingerprint is None
    flowsheet = structure(revision_document(case_id)).binding.flowsheet
    with pytest.raises(VerifierError):
        verify(flowsheet, recovery)


def test_a03_a_checkpoint_below_lambda_one_cannot_claim_more() -> None:
    base = dict(
        checkpoint_id="c",
        attempt_index=0,
        iteration=1,
        variable_ids=("x",),
        state_sha256="0" * 64,
        signature=(),
        residual_inf_unscaled=0.0,
        merit=0.0,
    )
    with pytest.raises(ValueError, match="modified problem"):
        Checkpoint(**base, label="candidate_root", continuation_lambda="3/4")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="modified problem"):
        Checkpoint(
            **base,  # type: ignore[arg-type]
            label="partial",
            verification_scope="checked_partial",
            continuation_lambda="0",
        )
    Checkpoint(**base, label="candidate_root", continuation_lambda="1")  # type: ignore[arg-type]

    schema = json.loads((REPO_ROOT / "schemas" / "checkpoint.schema.json").read_text())
    validator = Draft202012Validator(schema)
    document = Checkpoint(**base, label="partial", continuation_lambda="3/4").as_document()  # type: ignore[arg-type]
    assert not list(validator.iter_errors(document))
    assert list(validator.iter_errors({**document, "label": "candidate_root"}))
    assert list(validator.iter_errors({**document, "verification_scope": "certified"}))
    assert not list(
        validator.iter_errors({**document, "continuation_lambda": "1", "label": "candidate_root"})
    )
    assert list(validator.iter_errors({**document, "continuation_lambda": 0.75}))


@pytest.mark.parametrize("case_id", ["HOM-01", "HOM-02", "HOM-05"])
def test_a03_a_converged_homotopy_ends_on_the_target_identity(case_id: str) -> None:
    """λ = 1 is the target problem: the checkpoint is a candidate root at `"1"` and the root
    fingerprint carries the target's `(model_version, constants_sha256)`."""
    seen = run(case_id)
    checkpoint, fingerprint = seen.recovery.checkpoint, seen.recovery.root_fingerprint
    assert checkpoint is not None and fingerprint is not None
    assert (checkpoint.continuation_lambda, checkpoint.label) == ("1", "candidate_root")
    assert fingerprint["model_version"] == seen.target.metadata.model_version
    assert fingerprint["constants_sha256"] == seen.target.metadata.constants_sha256


# ------------------------------------------------------------------ A12: records


@pytest.mark.parametrize("case_id", HOM)
def test_a12_one_homotopy_step_per_lambda_trial(case_id: str) -> None:
    seen = run(case_id)
    steps = seen.trace.of_kind("homotopy_step")
    record = seen.record
    assert len(steps) == len(record.trials)
    for event, trial in zip(steps, record.trials, strict=True):
        result = trial.corrector.result
        assert event.iteration == trial.index and event.attempt == 0
        assert event.lambda_value == str(trial.lambda_value)
        assert event.delta_lambda == str(trial.delta_lambda)
        assert FRACTION.match(event.lambda_value) and FRACTION.match(event.delta_lambda)
        assert event.trial_status == ("accepted" if trial.accepted else "rejected")
        assert event.corrector_outcome == result.outcome
        assert event.corrector_iterations == result.iterations
        assert event.level_constants_sha256 == trial.corrector.level_constants_sha256
        assert re.fullmatch(r"[0-9a-f]{64}", event.level_constants_sha256)
        assert (event.level_constants_sha256 == seen.target.metadata.constants_sha256) == (
            trial.lambda_value == 1
        )
        assert event.homotopy_level is None
    last = steps[-1]
    if seen.recovery.outcome == "HOMOTOPY_STALLED":
        assert last.message == f"homotopy_stalled({last.corrector_outcome})"
        assert seen.recovery.message == last.message
        assert all(e.message == "" for e in steps[:-1])
    else:
        assert all(e.message == "" for e in steps)


@pytest.mark.parametrize("case_id", HOM)
def test_a12_every_corrector_event_carries_its_level(case_id: str) -> None:
    """Between two `homotopy_step`s every event is that trial's corrector's, stamped with its
    index; the homotopy attempt opens and closes once, unstamped."""
    events = run(case_id).trace.events
    trial = 0
    for event in events:
        if event.kind == "homotopy_step":
            assert event.iteration == trial
            trial += 1
        elif event.kind in ("jacobian", "linear_solve", "trial", "step_accepted") or (
            event.kind == "attempt_closed" and event.homotopy_level is not None
        ):
            if event.attempt == 0:
                assert event.homotopy_level == trial, event
    homotopy = [e for e in events if e.attempt == 0 and e.homotopy_level is None]
    assert [e.kind for e in homotopy if e.kind in ("attempt_opened", "attempt_closed")] == [
        "attempt_opened",
        "attempt_closed",
    ]
    (closed,) = [e for e in homotopy if e.kind == "attempt_closed"]
    assert closed.outcome == run(case_id).recovery.attempts[0].solver_outcome


@pytest.mark.parametrize("case_id", HOM)
def test_a12_the_context_and_the_provenance_item(case_id: str) -> None:
    seen = run(case_id)
    expected = registered(case_id)["homotopy"]
    context = seen.recovery.contexts[0]
    assert context.core == "homotopy"
    assert context.continuation == {
        "type": "specification_continuation",
        "parameter_ids": [CONTINUED],
    }
    assert context.as_document()["continuation"] == {
        "type": "specification_continuation",
        "parameter_ids": [CONTINUED],
    }
    item = seen.recovery.branch_provenance[0]
    assert item["core"] == "homotopy"
    assert item["opening_source"] == "eo_recovery_start"
    assert item["initializer_source"] == "user_guess"
    continuation = item["continuation"]
    accepted = [str(s["lambda"]) for s in expected["steps"][1:] if s["accepted"]]
    assert continuation == {
        "type": "specification_continuation",
        "parameter_ids": [CONTINUED],
        "lambda_levels": accepted,
        "lambda_reached": str(expected["lambda_reached"]),
        "rejected_trials": sum(1 for s in expected["steps"] if not s["accepted"]),
    }
    # §4.7 as amended (A12, F16): the item's `iterations` counts every corrector, accepted and
    # rejected — the Newton work done, registered per case (12/12/30/28/9 on HOM-01…05).
    assert item["iterations"] == expected["provenance_item_iterations"]
    assert item["iterations"] == sum(t.corrector.result.iterations for t in seen.record.trials)
    # The opening is the failed solve's item 0, to the bit.
    assert item["opening_state_sha256"] == seen.failed.branch_provenance[0]["opening_state_sha256"]
    # R0: no float anywhere in the item's strings.
    assert all(FRACTION.match(level) for level in continuation["lambda_levels"])
    assert FRACTION.match(continuation["lambda_reached"])


def test_a12_every_emitted_document_validates() -> None:
    from referencing import Registry, Resource

    documents = {
        path.stem.removesuffix(".schema"): json.loads(path.read_text())
        for path in (REPO_ROOT / "schemas").glob("*.schema.json")
    }
    registry = Registry().with_resources(
        (document["$id"], Resource.from_contents(document))
        for document in documents.values()
        if "$id" in document
    )
    event = Draft202012Validator(documents["solve-event"], registry=registry)
    context = Draft202012Validator(documents["attempt-context"], registry=registry)
    checkpoint = Draft202012Validator(documents["checkpoint"], registry=registry)
    for case_id in HOM:
        seen = run(case_id)
        for e in seen.trace.events:
            document = e.as_document()
            json.dumps(document, allow_nan=False)
            assert not list(event.iter_errors(document)), (case_id, e.kind)
        for c in seen.recovery.contexts:
            assert not list(context.iter_errors(c.as_document())), case_id
        assert seen.recovery.checkpoint is not None
        assert not list(checkpoint.iter_errors(seen.recovery.checkpoint.as_document()))


# ------------------------------------------------------------------ A28: the λ-trial budget


def test_a28_hom_04_with_four_lambda_trials_exhausts_its_budget() -> None:
    """`max_lambda_trials = 4`: 1/4, 3/4 accepted, 1 rejected, 7/8 accepted — then the budget, with
    the last accepted checkpoint (λ = 7/8), its state, and the provenance kept."""
    policy = case_policy("HOM-04", homotopy=HomotopyPolicy(max_lambda_trials=4))
    seen = direct("HOM-04", policy)
    recovery = seen.recovery
    assert recovery.outcome == "BUDGET_EXHAUSTED" and recovery.budget == "homotopy_steps"
    record = seen.record
    assert len(record.trials) - 1 == 4
    assert [str(t.lambda_value) for t in record.trials] == ["0", "1/4", "3/4", "1", "7/8"]
    assert record.lambda_reached == Fraction(7, 8)
    assert recovery.checkpoint is not None
    assert (recovery.checkpoint.continuation_lambda, recovery.checkpoint.label) == (
        "7/8",
        "partial",
    )
    steps = registered("HOM-04")["homotopy"]["steps"]
    assert close(recovery.state["S3.T"], steps[4]["S3_T_K"])
    assert len(recovery.branch_provenance) == 1
    assert recovery.branch_provenance[0]["continuation"]["lambda_reached"] == "7/8"
    assert recovery.branch_provenance[0]["core_outcome"] == "BUDGET_EXHAUSTED"


# ------------------------------------------------------------------ the homotopy's own ablations


@pytest.mark.parametrize(
    ("name", "case_id", "homotopy"),
    [
        ("no_growth (HOM-01)", "HOM-01", HomotopyPolicy(growth=1)),
        ("no_shrink (HOM-04)", "HOM-04", HomotopyPolicy(shrink=Fraction(0))),
        ("corrector_cap_50 (HOM-01)", "HOM-01", HomotopyPolicy(corrector_max_iterations=50)),
        ("corrector_cap_50 (HOM-04)", "HOM-04", HomotopyPolicy(corrector_max_iterations=50)),
        (
            "delta_lambda_initial_1 (HOM-01, sensitivity)",
            "HOM-01",
            HomotopyPolicy(delta_lambda_initial=Fraction(1)),
        ),
        (
            "delta_lambda_initial_1/2 (HOM-01, sensitivity)",
            "HOM-01",
            HomotopyPolicy(delta_lambda_initial=Fraction(1, 2)),
        ),
        (
            "delta_lambda_initial_1/8 (HOM-01, sensitivity)",
            "HOM-01",
            HomotopyPolicy(delta_lambda_initial=Fraction(1, 8)),
        ),
    ],
)
def test_the_registered_homotopy_ablations(
    name: str, case_id: str, homotopy: HomotopyPolicy, ref: dict[str, Any]
) -> None:
    """T04 §9.9's homotopy rows that a policy value expresses: growth and shrink are load-bearing,
    the corrector cap is inert on the registered paths, and Δλ₀ is not fitted. `shrink = 0` is
    "stall on the first rejection" (Δλ becomes 0 < Δλ_min)."""
    expected = ref["policy_simulation"]["ablations"][name]
    seen = direct(case_id, case_policy(case_id, homotopy=homotopy))
    assert seen.recovery.outcome == expected["outcome"]
    if "lambda_trials" in expected:
        assert len(seen.record.trials) - 1 == expected["lambda_trials"]
    if "lambda_reached" in expected:
        assert str(seen.record.lambda_reached) == str(expected["lambda_reached"])
    if "end_S3_T_K" in expected:
        # The YAML prints these to 1e-9 K.
        assert abs(seen.recovery.state["S3.T"] - float(expected["end_S3_T_K"])) <= 1e-8


def test_the_edge_from_the_failed_end_state_stalls_at_the_easy_endpoint(
    ref: dict[str, Any],
) -> None:
    """Register R-031's ablation: from PHS-05's end state — a pinned iterate inside the two-phase
    band, not a root of any level — the λ = 0 corrector fails and nothing is accepted."""
    expected = ref["policy_simulation"]["ablations"]["edge3_from_failed_end_state (HOM-01)"]
    seen = direct("HOM-01", from_end_state=True)
    assert seen.recovery.outcome == expected["outcome"] == "HOMOTOPY_STALLED"
    assert str(seen.record.lambda_reached) == str(expected["lambda_reached"])
    assert seen.record.stalled_at == "easy_endpoint"
    assert len(seen.record.trials) == 1 and not seen.record.trials[0].accepted
    assert seen.recovery.checkpoint is None


def test_the_opening_is_a_root_of_the_easy_endpoint_on_every_case() -> None:
    """§4.2: at λ = 0 the promoted row vanishes at x⁰ by construction and the rest is the
    pre-solve's root, so the λ = 0 corrector converges at iteration 0 with no Jacobian."""
    for case_id in HOM:
        seen = run(case_id)
        easy = seen.record.trials[0].corrector.result
        assert (easy.outcome, easy.iterations) == ("CONVERGED", 0)
        assert not [e for e in seen.trace.events if e.kind == "jacobian" and e.homotopy_level == 0]


def test_the_region_without_a_promoted_row_has_no_continuation_parameter() -> None:
    """§4.1: SYN-001 under `eo` promotes a loop, not a specification — no parameter to move."""
    from test_t02_region import case

    item = case("SYN-001-nominal")
    compiled = compile_problem(item.spec)
    assert (
        continuation_parameter(
            specification_rows=(),
            target_variables=(),
            spec=item.spec,
            structural_pattern=compiled.structural_pattern(),
        )
        is None
    )
    # A promoted row whose parameter the binding did not name after it is not `v − p`.
    spec = run("HOM-05").spec
    target = run("HOM-05").target
    assert (
        continuation_parameter(
            specification_rows=("SPEC:SPEC-flash-duty",),
            target_variables=("S3.T",),
            spec=spec,
            structural_pattern=target.structural_pattern(),
        )
        is None
    )
    assert (
        continuation_parameter(
            specification_rows=("SPEC:SPEC-flash-duty",),
            target_variables=("U-FLASH.Q",),
            spec=replace(
                spec, parameters={k: v for k, v in spec.parameters.items() if k != CONTINUED}
            ),
            structural_pattern=target.structural_pattern(),
        )
        is None
    )


def test_a_bundle_lists_the_homotopy_attempt_once_not_its_correctors() -> None:
    """HOM-04's recovery trace has eighteen corrector closures inside its one attempt; the failure
    bundle's attempt tree (K04 §10) reads the attempt's own closure only."""
    from types import SimpleNamespace

    from openflowsheet.verify.failure import bundle_for

    seen = run("HOM-04")
    closures = seen.trace.of_kind("attempt_closed")
    assert sum(1 for e in closures if e.homotopy_level is not None) == len(seen.record.trials)
    result = SimpleNamespace(
        outcome=seen.recovery.outcome,
        counters=seen.recovery.counters,
        checkpoint=seen.recovery.checkpoint,
        message=seen.recovery.message,
        attempts=len(seen.recovery.attempts),
        iterations=seen.recovery.iterations,
        residual_inf=float("nan"),
    )
    bundle = bundle_for(result, seen.trace, inferred=[{"cause": seen.record.inferred_cause}])
    assert [entry["outcome"] for entry in bundle.attempt_tree] == ["HOMOTOPY_STALLED"]
    assert bundle.taxonomy == "homotopy/PTC/active-set stalls"
    assert bundle.suggested_actions[0].action == "supply_initial_guess"
    assert bundle.best_checkpoint is not None
    assert bundle.best_checkpoint["continuation_lambda"] == "909/1024"
