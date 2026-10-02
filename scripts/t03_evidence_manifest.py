"""Generate `evidence/T03/<commit>/manifest.json` by measuring, not by transcribing. T03.

Every value recorded here is produced by running the code in this process and comparing it with
an independent expectation: `benchmarks/t03/reference_values.yaml` (the design lane's 40-digit twin
of the phase-attempt contract, emitted by `docs/derivations/scripts/t03_reference.py`),
`benchmarks/t02/reference_values.yaml` (T02's closed-form A02 sweep and REC-05),
`benchmarks/syn001/reference_values.yaml` (P01's 20-digit values), or a closed form stated in the
check itself. Nothing is copied from the specification's prose: a manifest that quoted the
document it is evidence for would be evidence of nothing.

The registered assertions are `docs/derivations/T03-phase-controller-spec.md` §11's `A00`…`A26`,
one check each. The case builders — the A02 revisions and their pre-solve, the nominal EO region,
OFF-B, the synthetic tear seeds, K03's constructed seeds, REC-05 through the merge edge — are
imported from the package's tests so that the manifest and the gate run the same fixtures; the
observation (which call each attempt received, what the screen asked, what the decision function
returned) and the comparison with the registered values are stated here. Every observer records
and returns what the solver computed; none alters a value.

One half cannot be measured on one machine: A23's cross-platform equality, which CI's `identity`
job establishes. Pass `--identities DIR` (the two downloaded `structural-identity-*` artifacts,
each holding `identity.json` and `t02-floats.json`) and this script applies the comparison the CI
job applies; without it that half is `unsupported`, never `pass`. `--ci-run URL` names the
workflow run and is recorded in `commands`.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/t03_evidence_manifest.py <gate-stdout> --commit <sha> \
        [--identities DIR] [--ci-run URL] [--out PATH]
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import json
import math
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import scipy.sparse as sp
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

# The registered fixtures, shared with the gate (see the module note).
import test_k03_attempts as k03_fixtures  # noqa: E402
import test_t02_a02 as a02_fixtures  # noqa: E402
import test_t02_executor as executor_fixtures  # noqa: E402
import test_t02_merge as merge_fixtures  # noqa: E402
import test_t02_region as region_fixtures  # noqa: E402
import test_t03_contract as contract_fixtures  # noqa: E402
import test_t03_roots as roots_fixtures  # noqa: E402

import openflowsheet.orchestrator.attempts as attempts_module  # noqa: E402
import openflowsheet.orchestrator.region as region_module  # noqa: E402
import openflowsheet.orchestrator.tear as tear_module  # noqa: E402
from openflowsheet.canonical import file_sha256, state_sha256  # noqa: E402
from openflowsheet.compile.casadi_backend import (  # noqa: E402
    CasadiCompiledProblem,
    compile_problem,
)
from openflowsheet.compiled import EvaluationContext  # noqa: E402
from openflowsheet.numerics.anderson import RecyclePolicy  # noqa: E402
from openflowsheet.orchestrator.attempts import solve_with_attempts  # noqa: E402
from openflowsheet.orchestrator.region import solve_region, syn001_lifted_splits  # noqa: E402
from openflowsheet.orchestrator.tear import Syn001TearProblem, solve_tear  # noqa: E402
from openflowsheet.orchestrator.trace import SolvePolicy, Trace  # noqa: E402

REFERENCE = ROOT / "benchmarks" / "t03" / "reference_values.yaml"
T02_REFERENCE = ROOT / "benchmarks" / "t02" / "reference_values.yaml"
P01 = ROOT / "benchmarks" / "syn001" / "reference_values.yaml"
SPEC = ROOT / "docs" / "derivations" / "T03-phase-controller-spec.md"
GENERATOR = ROOT / "docs" / "derivations" / "scripts" / "t03_reference.py"
CASES = ROOT / "benchmarks" / "syn001" / "cases"
REGISTRY = ROOT / "benchmarks" / "registry.yaml"
ORCHESTRATOR = ROOT / "src" / "openflowsheet" / "orchestrator"

#: The registered phase cases of spec §6.2, by their registered ids.
PHS = {
    "PHS-01": "SYN-001-A02-355-liquid-guess",
    "PHS-02": "SYN-001-A02-360-liquid-guess",
    "PHS-03": "SYN-001-A02-360-vapor-guess",
    "PHS-04": "SYN-001-A02-340-two-phase-guess",
    "PHS-05": "SYN-001-A02-355-dew-guess",
}
#: T02's A28/A29 cases (guess 358 K) and their key in `ref.t02_successes_under_the_contract`.
T02_SUCCESSES = {
    "SYN-001-A02-355": "SYN-001-A02-355 (guess 358 K)",
    "SYN-001-A02-360": "SYN-001-A02-360 (guess 358 K)",
    "SYN-001-A02-365": "SYN-001-A02-365 (guess 358 K)",
}
NO_GUESS = "SYN-001-A02-360-no-guess"
#: The policy the T03 tests solve the A02 region under (registered constants, spec §4.9).
POLICY = SolvePolicy(policy_id="T03", residual_tolerances={}, scales={})
#: OFF-B's policy, as `scripts/t03_identity.py` states it.
TEAR_POLICY = SolvePolicy(policy_id="SYN-001-K03", residual_tolerances={}, scales={})
PHASE_CONTRACT = "T03-phase-contract-v1"
#: §11 conventions: trial temperatures, restart points, β and `α_max` 1e-9 relative (on
#: `max(1, |x|)`, the tests' rule); final states by T02 A28's per-kind allowances.
RELATIVE = 1e-9
TEMPERATURE, DUTY, FLOW = 1e-5, 1e-2, 3.1e-7
COMPONENTS = ("A", "B", "C")
#: The assertion ids of spec §11, `A00`…`A26`.
ASSERTIONS = tuple(f"A{index:02d}" for index in range(27))

#: §4.10's grammar as amended by the review (S4), written out here from the specification (not
#: borrowed from the tests). R0 strings carry no measured number: `inadmissible(<stream>,
#: <branch>)`, `checkpoint_incompatible(<check>, <variable or field>)`; the subject is an id,
#: which starts with a letter, so no float can stand in for it.
_UNIT = r"[A-Z][\w-]*"
_REGIME = r"(LIQUID|TWO_PHASE|VAPOR)"
_SUBJECT = r"[A-Za-z_][\w.-]*"
_CAUSE = (
    rf"(phase_wall\((patience|stall), {_UNIT}:{_REGIME}->{_REGIME}"
    rf"(, {_UNIT}:{_REGIME}->{_REGIME})*\)"
    rf"|phase_disappeared\({_UNIT}, (vapor|liquid), [\w.]+\)"
    rf"|inadmissible\([\w-]+, (all_liquid|all_vapor)\)"
    rf"|kernel_disagrees\({_UNIT}, {_REGIME}\))"
)
OPENED = re.compile(rf"^(initial|phase_update\({_CAUSE}\))$")
TERMINAL = re.compile(
    rf"^(active_set_cycling\({_UNIT}:{_REGIME}(,{_UNIT}:{_REGIME})*; {_CAUSE}\)"
    rf"|checkpoint_incompatible\((identity|step|scale_segment|coverage|active_set|bounds), "
    rf"{_SUBJECT}\))$"
)
#: A float as `repr` writes one: no R0 string may carry one (review S4).
FLOAT = re.compile(r"\d\.\d|\de[-+]?\d|\binf\b|\bnan\b")


def check(
    identifier: str, description: str, result: str, value: Any, expected: Any
) -> dict[str, Any]:
    return {
        "id": identifier,
        "description": description,
        "result": result,
        "value": value,
        "expected": expected,
    }


def verdict(condition: bool) -> str:
    return "pass" if condition else "fail"


def measured(
    identifier: str,
    description: str,
    measure: Callable[[], tuple[bool, Any, Any]],
) -> dict[str, Any]:
    """Run one assertion's measurement. An exception is a failed measurement, recorded as such:
    a check that could not run did not pass, and hiding the error would hide the finding."""
    try:
        condition, value, expected = measure()
    except Exception as error:  # noqa: BLE001 - every failure is recorded, none is swallowed
        return check(
            identifier,
            description,
            "fail",
            {"error": f"{type(error).__name__}: {error}"},
            "the measurement runs to completion",
        )
    return check(identifier, description, verdict(condition), value, expected)


def number(value: Any) -> float:
    return float(value)


def plain(value: Any) -> Any:
    """A JSON-safe copy: numpy scalars and arrays as Python numbers, non-finite as strings."""
    if isinstance(value, dict):
        return {str(key): plain(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        items = sorted(value) if isinstance(value, set | frozenset) else value
        return [plain(item) for item in items]
    if isinstance(value, np.ndarray):
        return [plain(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return plain(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    return value


def close(value: float | None, expected: Any, relative: float = RELATIVE) -> bool:
    """§11's comparison: `|x − x_ref| ≤ 1e-9 · max(1, |x_ref|)`; `None` only against `None`."""
    if expected is None or value is None:
        return expected is None and value is None
    target = float(expected)
    return abs(float(value) - target) <= relative * max(1.0, abs(target))


def off(value: float | None, expected: Any) -> float | None:
    """The departure `close` judges, in its own units, for the record."""
    if expected is None or value is None:
        return None
    target = float(expected)
    return abs(float(value) - target) / max(1.0, abs(target))


def signature_text(signature: Any) -> str:
    return ",".join(f"{unit}:{regime}" for unit, regime in signature)


def positive_zero(value: float) -> bool:
    return value == 0.0 and math.copysign(1.0, value) == 1.0


# ------------------------------------------------------------------------------ observation


@dataclass
class Observed:
    """One region solve and everything observed about it, per attempt (index = attempt)."""

    label: str
    policy: SolvePolicy
    structure: tuple[tuple[str, str], ...]
    spec: Any = None
    result: Any = None
    trace: Trace = field(default_factory=Trace)
    #: the free and row ids `_region_problem` built each attempt's problem over
    free: list[tuple[str, ...]] = field(default_factory=list)
    rows: list[tuple[str, ...]] = field(default_factory=list)
    #: `id` of the evaluation context each attempt's problem (and every compiled call) received
    context_ids: list[int] = field(default_factory=list)
    #: every residual call's free vector and evaluation; the first is the opening state
    calls: list[list[tuple[np.ndarray, Any]]] = field(default_factory=list)
    #: the same attempt's residual without the screen (the frozen formulation)
    plain: list[Callable[[np.ndarray], Any]] = field(default_factory=list)
    #: every Jacobian's shape and stored positions
    jacobians: list[list[tuple[tuple[int, int], frozenset[tuple[int, int]]]]] = field(
        default_factory=list
    )
    #: every call of the admissibility check: attempt, from the screen or not, unit, verdict
    admissible: list[dict[str, Any]] = field(default_factory=list)
    #: every screen invocation: attempt and the trial's `S3.T`
    screened: list[dict[str, Any]] = field(default_factory=list)
    #: kernel flashes the screen asked for, per attempt
    flashes: dict[int, int] = field(default_factory=dict)
    #: every call of the decision function: the core's result and the decision
    decisions: list[dict[str, Any]] = field(default_factory=list)
    #: every opening check's outcome (`None` = the six checks hold, else an `OpeningRefusal`)
    openings: list[Any] = field(default_factory=list)
    #: every call the compiled problem received from inside an attempt's residual or Jacobian:
    #: attempt, `id` of the context passed, and the full vector it evaluated (review M3: read
    #: what the evaluator was given, not what the region wrote afterwards)
    compiled_calls: list[tuple[int, int, np.ndarray]] = field(default_factory=list)


def _observe_region(
    observed: Observed,
    solve: Callable[[Trace], Any],
    *,
    corrupt_opening: Callable[[Any], Any] | None = None,
    corrupt_blocked: Callable[[Any], Any] | None = None,
) -> Observed:
    """Run `solve` with the region's problem, screen, admissibility check, opening check,
    decision function and compiled boundary observed. `corrupt_*` are A16's constructed bites
    (spec §5.1: "Registered bites are constructed"); nothing else changes what the solver
    computes."""
    real_problem = region_module._region_problem
    real_screen = region_module._screen
    real_admissible = region_module._admissible
    real_check = region_module.check_opening
    real_decide = region_module.decide
    real_blocked = region_module._LiftedOps.blocked
    real_compiled = {
        name: getattr(CasadiCompiledProblem, name) for name in ("residual", "jacobian")
    }
    in_screen = [False]
    #: > 0 while an attempt's own residual or Jacobian is on the stack
    in_attempt_call = [0]

    def attempt() -> int:
        return len(observed.free) - 1

    def compiled_spy(name: str) -> Callable[..., Any]:
        real = real_compiled[name]

        def spy(self: Any, x: Any, context: Any) -> Any:
            if in_attempt_call[0]:
                observed.compiled_calls.append(
                    (attempt(), id(context), np.array(x, dtype=np.float64))
                )
            return real(self, x, context)

        return spy

    def problem(
        compiled: Any,
        context: Any,
        spec: Any,
        scaling: Any,
        base: Any,
        free: Sequence[str],
        rows: Sequence[str],
        screen: Any = None,
        opening: Any = None,
    ) -> Any:
        observed.free.append(tuple(free))
        observed.rows.append(tuple(rows))
        observed.context_ids.append(id(context))
        calls: list[tuple[np.ndarray, Any]] = []
        jacobians: list[tuple[tuple[int, int], frozenset[tuple[int, int]]]] = []
        observed.calls.append(calls)
        observed.jacobians.append(jacobians)
        observed.plain.append(
            real_problem(compiled, context, spec, scaling, base, free, rows).residual
        )
        built = real_problem(compiled, context, spec, scaling, base, free, rows, screen, opening)
        residual, jacobian = built.residual, built.jacobian

        def observed_residual(x: np.ndarray) -> Any:
            in_attempt_call[0] += 1
            try:
                out = residual(x)
            finally:
                in_attempt_call[0] -= 1
            calls.append((np.array(x, dtype=np.float64), out))
            return out

        def observed_jacobian(x: np.ndarray) -> Any:
            in_attempt_call[0] += 1
            try:
                matrix = sp.csc_matrix(jacobian(x))
            finally:
                in_attempt_call[0] -= 1
            coo = matrix.tocoo()
            jacobians.append(
                (
                    (int(matrix.shape[0]), int(matrix.shape[1])),
                    frozenset(zip(coo.row.tolist(), coo.col.tolist(), strict=True)),
                )
            )
            return matrix

        return replace(built, residual=observed_residual, jacobian=observed_jacobian)

    def screen_factory(**keywords: Any) -> Any:
        provider = keywords["provider"]

        class Counting:
            """The provider, with the screen's own kernel flashes counted."""

            def __getattr__(self, name: str) -> Any:
                return getattr(provider, name)

            def flash(self, request: Any, context: Any) -> Any:
                observed.flashes[attempt()] = observed.flashes.get(attempt(), 0) + 1
                return provider.flash(request, context)

        inner = real_screen(**{**keywords, "provider": Counting()})

        def screen(state: dict[str, float]) -> Any:
            observed.screened.append({"attempt": attempt(), "S3.T": state.get("S3.T")})
            in_screen[0] = True
            try:
                return inner(state)
            finally:
                in_screen[0] = False

        return screen

    def admissible(
        provider: Any, context: Any, split: Any, regime: str, state: Any, epsilon: float
    ) -> tuple[bool, float]:
        ok, value = real_admissible(provider, context, split, regime, state, epsilon)
        observed.admissible.append(
            {
                "attempt": attempt(),
                "in_screen": in_screen[0],
                "unit": split.unit,
                "regime": regime,
                "epsilon": epsilon,
                "ok": ok,
                "value": value,
                "T": state.get(split.temperature),
            }
        )
        return ok, value

    def opening_check(state: Any, requirement: Any) -> Any:
        if corrupt_opening is not None:
            state = corrupt_opening(state)
        outcome = real_check(state, requirement)
        observed.openings.append(outcome)
        return outcome

    def decide(result: Any, **keywords: Any) -> Any:
        decision = real_decide(result, **keywords)
        observed.decisions.append(
            {
                "attempt": keywords["attempt_index"],
                "core_outcome": result.outcome,
                "iterations": result.iterations,
                "blocked_by": tuple(result.blocked_by or ()),
                "kind": decision.kind,
                "outcome": decision.outcome,
                "message": decision.message,
                "policy": keywords["policy"],
                "residual_calls": sum(len(calls) for calls in observed.calls),
                "jacobian_calls": sum(len(jacobians) for jacobians in observed.jacobians),
            }
        )
        return decision

    def blocked(self: Any, result: Any) -> Any:
        conversion = real_blocked(self, result)
        if corrupt_blocked is None or conversion is None:
            return conversion
        return corrupt_blocked(conversion)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(region_module, "_region_problem", problem)
        patch.setattr(region_module, "_screen", screen_factory)
        patch.setattr(region_module, "_admissible", admissible)
        patch.setattr(region_module, "check_opening", opening_check)
        patch.setattr(region_module, "decide", decide)
        patch.setattr(region_module._LiftedOps, "blocked", blocked)
        for name in real_compiled:
            patch.setattr(CasadiCompiledProblem, name, compiled_spy(name))
        observed.result = solve(observed.trace)
    return observed


def _a02_revision(
    case_id: str,
    policy: SolvePolicy = POLICY,
    **corruptions: Callable[[Any], Any] | None,
) -> Observed:
    """An A02 revision's region solve from its pre-solve (T02 §7.5), exactly as the T03 tests
    run it (`test_t03_contract.observe`), observed. The pre-solve runs before any observer."""
    item = a02_fixtures.structure(a02_fixtures.revision(case_id))
    flowsheet = item.binding.flowsheet
    pre, _ = solve_tear(flowsheet)
    if pre.final_state is None:
        raise RuntimeError(f"{case_id}: the pre-solve produced no state")
    compiled = compile_problem(item.binding.spec)
    region = a02_fixtures.the_region(item)
    start = dict(pre.final_state)

    def solve(trace: Trace) -> Any:
        return solve_region(
            compiled=compiled,
            spec=item.binding.spec,
            region=region,
            state=start,
            splits=syn001_lifted_splits(flowsheet.components),
            provider=flowsheet.provider,
            policy=policy,
            trace=trace,
            # T03 §8.1 as amended (review S2): the freed coordinate's user value seeds the
            # region, through the pre-solve — the tests' source for these regions.
            initializer_source="user_guess",
        )

    observed = Observed(case_id, policy, tuple(compiled.structural_pattern()), item.binding.spec)
    return _observe_region(observed, solve, **corruptions)


def _nominal_eo() -> Observed:
    """T02 A21: SYN-001 nominal under `eo`, the region from `x(t⁰)` (`test_t02_region`)."""
    item = region_fixtures.case("SYN-001-nominal")
    start = region_fixtures.initializer(item)

    def solve(trace: Trace) -> Any:
        return region_fixtures.solve(item, start, trace)

    observed = Observed(
        "SYN-001-nominal eo", region_fixtures.POLICY, tuple(item.compiled.structural_pattern())
    )
    observed.spec = item.spec
    return _observe_region(observed, solve)


@dataclass
class TearObserved:
    """OFF-B on the tear path, observed at the controller's and the tear problem's boundaries."""

    result: Any = None
    trace: Any = None
    policy: Any = None
    flowsheet: Any = None
    variable_ids: tuple[str, ...] = ()
    x0: tuple[float, ...] = ()
    attempt_contexts: list[Any] = field(default_factory=list)
    #: per attempt, at the tear problem's boundary: the flowsheet context of every residual
    #: call; the evaluation context and flowsheet context of every Jacobian call (`None`: the
    #: call named none and fell back to the problem's own)
    residual_contexts: dict[int, list[int | None]] = field(default_factory=dict)
    jacobian_contexts: dict[int, list[int | None]] = field(default_factory=dict)
    jacobian_flowsheet_contexts: dict[int, list[int | None]] = field(default_factory=dict)
    #: inside an open attempt (between its `attempt_opened` and `attempt_closed`), the review's
    #: M3 probe: every compiled residual/Jacobian call's context (`id`); every provider call the
    #: tear code makes itself (`id`); every provider call made by the compiled problem's
    #: property blocks (the context object itself, compared field by field)
    compiled_calls: list[tuple[int, int]] = field(default_factory=list)
    tear_provider_calls: list[tuple[int, int]] = field(default_factory=list)
    block_provider_calls: list[tuple[int, Any]] = field(default_factory=list)
    #: the exact property cache's size at every `attempt_opened`
    cache_sizes: list[int] = field(default_factory=list)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    openings: list[str | None] = field(default_factory=list)


def _off_b(policy: SolvePolicy = TEAR_POLICY) -> TearObserved:
    from openflowsheet.thermo.cache import ExactPropertyCache

    reference = yaml.safe_load(P01.read_text(encoding="utf-8"))
    flowsheet = k03_fixtures.flowsheet_for(k03_fixtures.variants(reference)["SYN-001-nominal"])
    seen = TearObserved(flowsheet=flowsheet)
    real_run = tear_module.solve_with_attempts
    real_problem = Syn001TearProblem.as_newton_problem
    real_residual = Syn001TearProblem.residual
    real_jacobian = Syn001TearProblem.jacobian
    real_cache = ExactPropertyCache.__init__
    real_record = Trace.record
    real_decide = attempts_module.decide
    real_check = attempts_module.check_opening
    real_compiled = {
        name: getattr(CasadiCompiledProblem, name) for name in ("residual", "jacobian")
    }
    real_provider = {
        name: getattr(ExactPropertyCache, name) for name in ("flash", "evaluate_phase")
    }
    caches: list[Any] = []
    active = [False]
    #: the attempt between its `attempt_opened` and `attempt_closed`, else `None`
    open_attempt: list[int | None] = [None]
    in_compiled = [0]

    def run(**keywords: Any) -> Any:
        seen.variable_ids = tuple(keywords["variable_ids"])
        seen.x0 = tuple(float(value) for value in keywords["x0"])
        seen.policy = keywords["policy"]
        active[0] = True
        try:
            return real_run(**keywords)
        finally:
            active[0] = False

    def as_problem(self: Any, attempt: Any = None) -> Any:
        if attempt is not None:
            seen.attempt_contexts.append(attempt)
        return real_problem(self, attempt)

    def residual(self: Any, t: np.ndarray, flowsheet: Any = None) -> Any:
        if active[0]:
            seen.residual_contexts.setdefault(len(seen.attempt_contexts) - 1, []).append(
                id(flowsheet.context) if flowsheet is not None else None
            )
        return real_residual(self, t, flowsheet)

    def jacobian(self: Any, t: np.ndarray, context: Any = None, flowsheet: Any = None) -> Any:
        if active[0]:
            k = len(seen.attempt_contexts) - 1
            seen.jacobian_contexts.setdefault(k, []).append(
                id(context) if context is not None else None
            )
            seen.jacobian_flowsheet_contexts.setdefault(k, []).append(
                id(flowsheet.context) if flowsheet is not None else None
            )
        return real_jacobian(self, t, context, flowsheet)

    def compiled_spy(name: str) -> Callable[..., Any]:
        real = real_compiled[name]

        def spy(self: Any, x: Any, context: Any) -> Any:
            if open_attempt[0] is not None:
                seen.compiled_calls.append((open_attempt[0], id(context)))
            in_compiled[0] += 1
            try:
                return real(self, x, context)
            finally:
                in_compiled[0] -= 1

        return spy

    def provider_spy(name: str) -> Callable[..., Any]:
        real = real_provider[name]

        def spy(self: Any, request: Any, context: Any) -> Any:
            if open_attempt[0] is not None:
                if in_compiled[0]:
                    seen.block_provider_calls.append((open_attempt[0], context))
                else:
                    seen.tear_provider_calls.append((open_attempt[0], id(context)))
            return real(self, request, context)

        return spy

    def cache(self: Any, *arguments: Any, **keywords: Any) -> None:
        real_cache(self, *arguments, **keywords)
        caches.append(self)

    def record(self: Any, **fields: Any) -> Any:
        if fields.get("kind") == "attempt_opened":
            if caches:
                seen.cache_sizes.append(len(caches[-1]._entries))
            open_attempt[0] = fields["attempt"]
        elif fields.get("kind") == "attempt_closed":
            open_attempt[0] = None
        return real_record(self, **fields)

    def decide(result: Any, **keywords: Any) -> Any:
        decision = real_decide(result, **keywords)
        seen.decisions.append(
            {
                "attempt": keywords["attempt_index"],
                "core_outcome": result.outcome,
                "iterations": result.iterations,
                "kind": decision.kind,
                "outcome": decision.outcome,
                "message": decision.message,
                "policy": keywords["policy"],
            }
        )
        return decision

    def opening_check(state: Any, requirement: Any) -> Any:
        outcome = real_check(state, requirement)
        seen.openings.append(outcome)
        return outcome

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(tear_module, "solve_with_attempts", run)
        patch.setattr(Syn001TearProblem, "as_newton_problem", as_problem)
        patch.setattr(Syn001TearProblem, "residual", residual)
        patch.setattr(Syn001TearProblem, "jacobian", jacobian)
        patch.setattr(ExactPropertyCache, "__init__", cache)
        patch.setattr(Trace, "record", record)
        patch.setattr(attempts_module, "decide", decide)
        patch.setattr(attempts_module, "check_opening", opening_check)
        for name in real_compiled:
            patch.setattr(CasadiCompiledProblem, name, compiled_spy(name))
        for name in real_provider:
            patch.setattr(ExactPropertyCache, name, provider_spy(name))
        seen.result, seen.trace = solve_tear(
            flowsheet, initial_recycle=k03_fixtures.OFF_B, policy=policy
        )
    return seen


@dataclass
class Seed:
    """A bare-controller run (no compiled problem): the trace, the decisions, the points."""

    label: str
    result: Any
    trace: Trace
    policy: SolvePolicy
    decisions: list[dict[str, Any]]
    evaluated: list[float] = field(default_factory=list)


@contextlib.contextmanager
def _decisions() -> Iterator[list[dict[str, Any]]]:
    """Every call of the decision function on the tear path while inside."""
    real = attempts_module.decide
    log: list[dict[str, Any]] = []

    def decide(result: Any, **keywords: Any) -> Any:
        decision = real(result, **keywords)
        log.append(
            {
                "attempt": keywords["attempt_index"],
                "core_outcome": result.outcome,
                "kind": decision.kind,
                "outcome": decision.outcome,
                "message": decision.message,
                "policy": keywords["policy"],
            }
        )
        return decision

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(attempts_module, "decide", decide)
        yield log


def _synthetic_seed(name: str, bounds: tuple[float, float]) -> Seed:
    """PHS-SYN-1/2 (spec §6.6) through the bare controller, as `test_t03_contract` builds them."""
    problem, signature_of, evaluated = contract_fixtures.synthetic(*bounds)
    context = EvaluationContext(
        model_version="syn", constants_sha256="0" * 64, phase_signature=None
    )
    trace = Trace()
    with _decisions() as log:
        result = solve_with_attempts(
            problem_for=lambda attempt: problem,
            x0=[0.0],
            signature_of=signature_of,
            policy=POLICY,
            trace=trace,
            evaluation_context=context,
            flowsheet_context=context,
            column_scales={"x": 1.0},
            row_scales={"r": 1.0},
            variable_ids=("x",),
        )
    return Seed(name, result, trace, POLICY, log, evaluated)


def _k03_seed(name: str, *, root_in_b: float = 0.0, **policy_fields: Any) -> Seed:
    """K03's constructed two-regime seed (`test_k03_attempts.two_regime_problem`)."""
    problem, signature_of = k03_fixtures.two_regime_problem(root_in_b=root_in_b)
    with _decisions() as log:
        result, trace = k03_fixtures.run_controller(problem, signature_of, [0.0], **policy_fields)
    policy = (
        log[-1]["policy"]
        if log
        else SolvePolicy(
            policy_id="constructed", residual_tolerances={}, scales={}, **policy_fields
        )
    )
    return Seed(name, result, trace, policy, log)


class Runs:
    """Every solve this manifest measures, run once and shared by the checks that read it."""

    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}

    def _once(self, key: str, build: Callable[[], Any]) -> Any:
        if key not in self._cache:
            self._cache[key] = build()
        return self._cache[key]

    def region(self, case_id: str) -> Observed:
        return self._once(f"region {case_id}", lambda: _a02_revision(case_id))

    def nominal_eo(self) -> Observed:
        return self._once("nominal eo", _nominal_eo)

    def off_b(self) -> TearObserved:
        return self._once("OFF-B", _off_b)

    def synthetic(self, name: str) -> Seed:
        bounds = {"PHS-SYN-1": (1.0, 2.0), "PHS-SYN-2": (1.0, 1.01)}[name]
        return self._once(name, lambda: _synthetic_seed(name, bounds))

    def k03_cycling(self) -> Seed:
        return self._once("K03 cycling", lambda: _k03_seed("K03 two-regime seed"))

    def k03_budget(self) -> Seed:
        return self._once(
            "K03 budget",
            lambda: _k03_seed("K03 budget seed", root_in_b=-2.0, max_attempts=2),
        )

    def rec_05(self, route: str) -> Any:
        def build() -> Any:
            t02 = yaml.safe_load(T02_REFERENCE.read_text(encoding="utf-8"))
            if route == "MR-C":
                return roots_fixtures.rec_05_run(t02, "1.1 t*", RecyclePolicy(depth_max=0))
            return roots_fixtures.rec_05_run(t02, {"MR-A": "1.1 t*", "MR-B": "t*"}[route])

        return self._once(route, build)

    def refused(self, check_name: str) -> Observed:
        """A16's constructed bites (spec §5.1), one per refused check."""

        def build() -> Observed:
            if check_name == "active_set":
                return _a02_revision(
                    PHS["PHS-04"],
                    corrupt_blocked=lambda conversion: replace(
                        conversion,
                        opening=(
                            {**conversion.opening[0], "S3.vap.A": 1e-3},
                            conversion.opening[1],
                        ),
                    ),
                )
            corrupt = {
                "scale_segment": lambda state: replace(state, scale_segment=1),
                "identity": lambda state: replace(state, model_version="another@model"),
                "bounds": lambda state: replace(state, values={**state.values, "S3.liq.B": -1e-9}),
            }[check_name]
            return _a02_revision(PHS["PHS-01"], corrupt_opening=corrupt)

        return self._once(f"refused {check_name}", build)

    def observed(self) -> list[Observed]:
        return [value for value in self._cache.values() if isinstance(value, Observed)]

    def all_policies(self) -> list[Any]:
        """Every policy that reached the decision function in any run measured so far."""
        found: list[Any] = []
        for value in self._cache.values():
            for decision in getattr(value, "decisions", ()):
                found.append(decision["policy"])
        return found


# ------------------------------------------------------------------------------ per attempt


def _heater(split_unit: str = "U-HEAT") -> Any:
    return next(split for split in syn001_lifted_splits(COMPONENTS) if split.unit == split_unit)


def _line_search(observed: Observed, k: int) -> list[Any]:
    """Attempt `k`'s trial and accepted-step events, in order, iterations ≥ 0."""
    return [
        event
        for event in observed.trace.events
        if event.attempt == k and event.kind in ("trial", "step_accepted") and event.iteration >= 0
    ]


def _attempt(observed: Observed, k: int) -> dict[str, Any]:
    """Attempt `k` as measured, in the registered record's terms (`ref.cases.X.attempts[k]`)."""
    result = observed.result
    item = result.branch_provenance[k]
    attempt = result.attempts[k]
    free = observed.free[k]
    where = free.index("S3.T")
    x0 = observed.calls[k][0][0]
    opening = dict(zip(free, (float(value) for value in x0), strict=True))
    vapour = opening.get("S3.V", attempt.end_state["S3.V"])
    liquid = opening.get("S3.L", attempt.end_state["S3.L"])
    (opened,) = [e for e in observed.trace.events if e.kind == "attempt_opened" and e.attempt == k]
    decision = next(entry for entry in observed.decisions if entry["attempt"] == k)

    events = _line_search(observed, k)
    temperatures = [float(x[where]) for x, _ in observed.calls[k][1:]]
    trials: list[dict[str, Any]] = []
    halving: dict[int, int] = {}
    for event, temperature in zip(events, temperatures, strict=False):
        index = halving.get(event.iteration, 0)
        halving[event.iteration] = index + 1
        verdict_ = "accepted" if event.kind == "step_accepted" else event.rejection_reason
        trials.append(
            {
                "iteration": event.iteration,
                "halving": index,
                "verdict": verdict_,
                "alpha": float(event.alpha),
                "S3_T_K": temperature,
                "reported_heater_regime": dict(event.signature)["U-HEAT"]
                if verdict_ == "phase_update_required"
                else None,
            }
        )
    # The screen's values, in trial order, for the trials it read (not a domain-refused one).
    screen_values = [
        entry["value"]
        for entry in observed.admissible
        if entry["attempt"] == k and entry["in_screen"] and entry["unit"] == "U-HEAT"
    ]
    return {
        "signature": signature_text(attempt.signature),
        "opening_source": item["opening_source"],
        "opening_trial": item["opening_trial"],
        "opening_alpha": opened.alpha,
        "opening_S3_T_K": float(x0[where]),
        "opening_beta": vapour / (vapour + liquid),
        "opening_message": opened.message,
        "core_outcome": item["core_outcome"],
        "core_iterations": item["iterations"],
        "decision": item["decision"],
        "cause": item["cause"],
        "blocked_by": list(decision["blocked_by"]),
        "end_S3_T_K": float(attempt.end_state["S3.T"]),
        "trials": trials,
        "events_matched_to_calls": len(events) == len(temperatures),
        "phase_rejections": sum(1 for t in trials if t["verdict"] == "phase_update_required"),
        "invalid_trials": sum(1 for t in trials if t["verdict"] == "invalid_trial"),
        "screen_values": screen_values,
    }


def _compare_attempt(
    observed: Observed, k: int, found: Mapping[str, Any], registered: Mapping[str, Any]
) -> dict[str, Any]:
    """Attempt `k` against its registered record: §11's conventions, every departure named."""
    mismatches: list[str] = []
    for key in ("opening_source", "opening_trial", "core_outcome", "decision", "cause"):
        if found[key] != registered[key]:
            mismatches.append(f"{key}: {found[key]!r} != {registered[key]!r}")
    if found["signature"] != registered["signature"]:
        mismatches.append(f"signature: {found['signature']} != {registered['signature']}")
    if found["core_iterations"] != registered["core_iterations"]:
        mismatches.append(
            f"core_iterations: {found['core_iterations']} != {registered['core_iterations']}"
        )
    for key in ("phase_rejections", "invalid_trials"):
        if found[key] != registered[key]:
            mismatches.append(f"{key}: {found[key]} != {registered[key]}")
    if "blocked_by" in registered and found["blocked_by"] != list(registered["blocked_by"]):
        mismatches.append(f"blocked_by: {found['blocked_by']} != {registered['blocked_by']}")
    for key in ("opening_alpha", "opening_S3_T_K", "opening_beta", "end_S3_T_K"):
        if not close(found[key], registered[key]):
            mismatches.append(f"{key}: {found[key]!r} against {registered[key]!r}")
    if not found["events_matched_to_calls"]:
        mismatches.append("the trace's trials and the observed residual calls differ in number")

    worst_trial = 0.0
    registered_trials = registered.get("trials") or []
    if len(found["trials"]) != len(registered_trials):
        mismatches.append(f"trials: {len(found['trials'])} != {len(registered_trials)}")
    for trial, expected in zip(found["trials"], registered_trials, strict=False):
        where = f"trial ({trial['iteration']}, {trial['halving']})"
        if (trial["iteration"], trial["halving"], trial["verdict"]) != (
            expected["iteration"],
            expected["halving"],
            expected["verdict"],
        ):
            mismatches.append(
                f"{where}: {trial['verdict']} against ({expected['iteration']}, "
                f"{expected['halving']}) {expected['verdict']}"
            )
        if not close(trial["alpha"], expected["alpha"]):
            mismatches.append(f"{where}: alpha {trial['alpha']!r} against {expected['alpha']}")
        if not close(trial["S3_T_K"], expected["S3_T_K"]):
            mismatches.append(f"{where}: S3.T {trial['S3_T_K']!r} against {expected['S3_T_K']}")
        worst_trial = max(worst_trial, off(trial["S3_T_K"], expected["S3_T_K"]) or 0.0)
        if expected["verdict"] == "phase_update_required" and (
            trial["reported_heater_regime"] != expected["reported_heater_regime"]
        ):
            mismatches.append(
                f"{where}: reported {trial['reported_heater_regime']} against "
                f"{expected['reported_heater_regime']}"
            )

    landings: list[dict[str, Any]] = []
    for landing in registered.get("landings") or ():
        accepted = [
            (index, trial)
            for index, trial in enumerate(found["trials"])
            if trial["verdict"] == "accepted" and trial["iteration"] == landing["iteration"]
        ]
        if len(accepted) != 1:
            mismatches.append(f"landing at iteration {landing['iteration']}: no accepted step")
            continue
        index, trial = accepted[0]
        x = observed.calls[k][1 + index][0]
        free = observed.free[k]
        on_bound = {name: float(x[free.index(name)]) for name in landing["variables"]}
        record = {
            "iteration": landing["iteration"],
            "alpha": trial["alpha"],
            "alpha_max_registered": number(landing["alpha_max"]),
            "alpha_relative_off": off(trial["alpha"], landing["alpha_max"]),
            "variables": on_bound,
            "on_positive_zero": all(positive_zero(value) for value in on_bound.values()),
            "attempt_continued": found["core_iterations"] >= landing["iteration"] + 1,
        }
        landings.append(record)
        if not (
            close(trial["alpha"], landing["alpha_max"])
            and record["on_positive_zero"]
            and record["attempt_continued"]
        ):
            mismatches.append(f"landing {record}")

    # Recorded, not judged: §11 registers screen values only for A05's opening value.
    screen_off = None
    expected_screen = [
        trial["screen_value"]
        for trial in registered_trials
        if trial.get("screen_value") is not None and trial["verdict"] != "invalid_trial"
    ]
    if expected_screen and len(expected_screen) == len(found["screen_values"]):
        screen_off = max(
            abs(value - number(ref)) / abs(number(ref))
            for value, ref in zip(found["screen_values"], expected_screen, strict=True)
        )
    return {
        "signature": found["signature"],
        "opening": {
            "source": found["opening_source"],
            "trial": found["opening_trial"],
            "alpha": found["opening_alpha"],
            "S3_T_K": found["opening_S3_T_K"],
            "beta": found["opening_beta"],
            "message": found["opening_message"],
        },
        "core": {
            "outcome": found["core_outcome"],
            "iterations": found["core_iterations"],
            "blocked_by": found["blocked_by"],
        },
        "decision": found["decision"],
        "cause": found["cause"],
        "end_S3_T_K": found["end_S3_T_K"],
        "trials": len(found["trials"]),
        "phase_rejections": found["phase_rejections"],
        "invalid_trials": found["invalid_trials"],
        "worst_trial_S3_T_relative_off": worst_trial,
        "landings": landings,
        "screen_values_worst_relative_off (recorded, not judged)": screen_off,
        "mismatches": mismatches,
    }


def _registered_attempt(registered: Mapping[str, Any]) -> dict[str, Any]:
    """The registered record, in the shape `_compare_attempt` reports."""
    return {
        "signature": registered["signature"],
        "opening": {
            "source": registered["opening_source"],
            "trial": registered["opening_trial"],
            "alpha": registered["opening_alpha"],
            "S3_T_K": registered["opening_S3_T_K"],
            "beta": registered["opening_beta"],
        },
        "core": {
            "outcome": registered["core_outcome"],
            "iterations": registered["core_iterations"],
            "blocked_by": registered.get("blocked_by", []),
        },
        "decision": registered["decision"],
        "cause": registered["cause"],
        "end_S3_T_K": registered["end_S3_T_K"],
        "trials": len(registered.get("trials") or []),
        "phase_rejections": registered["phase_rejections"],
        "invalid_trials": registered["invalid_trials"],
        "landings": [
            {"iteration": landing["iteration"], "alpha_max": landing["alpha_max"]}
            for landing in registered.get("landings") or ()
        ],
        "mismatches": [],
        "tolerance": "temperatures, alpha, beta 1e-9 relative on max(1, |x|); the rest exact",
    }


def _final(
    state: Mapping[str, float],
    registered: Mapping[str, Any],
    sweep: Mapping[str, Any] | None,
) -> tuple[bool, dict[str, Any]]:
    """The final state against the twin's final record and, where one exists, T02's closed-form
    A02 sweep row — by T02 A28's per-kind allowances."""
    offs = {
        "S3.T (K)": abs(state["S3.T"] - number(registered["S3_T_K"])),
        "U-HEAT.Q (W)": abs(state["U-HEAT.Q"] - number(registered["U_HEAT_Q_W"])),
        "U-FLASH.Q (W)": abs(state["U-FLASH.Q"] - number(registered["U_FLASH_Q_W"])),
        "S3 split (mol/s)": max(
            max(
                abs(state[f"S3.vap.{c}"] - number(registered["S3_vapor_mol_per_s"][i])),
                abs(state[f"S3.liq.{c}"] - number(registered["S3_liquid_mol_per_s"][i])),
            )
            for i, c in enumerate(COMPONENTS)
        ),
    }
    ok = (
        offs["S3.T (K)"] <= TEMPERATURE
        and offs["U-HEAT.Q (W)"] <= DUTY
        and offs["U-FLASH.Q (W)"] <= DUTY
        and offs["S3 split (mol/s)"] <= FLOW
    )
    value: dict[str, Any] = {"S3.T": state["S3.T"], "against_t03_final": offs}
    if sweep is not None:
        sweep_offs = {
            "U-HEAT.Q (W)": abs(state["U-HEAT.Q"] - number(sweep["Q_heater_W"])),
            "U-FLASH.Q (W)": abs(state["U-FLASH.Q"] - number(sweep["Q_flash_W"])),
            "S3 split (mol/s)": max(
                max(
                    abs(state[f"S3.vap.{c}"] - number(sweep["S3_vapor_mol_per_s"][i])),
                    abs(state[f"S3.liq.{c}"] - number(sweep["S3_liquid_mol_per_s"][i])),
                )
                for i, c in enumerate(COMPONENTS)
            ),
        }
        value["against_t02_sweep"] = sweep_offs
        ok = (
            ok
            and sweep_offs["U-HEAT.Q (W)"] <= DUTY
            and sweep_offs["U-FLASH.Q (W)"] <= DUTY
            and sweep_offs["S3 split (mol/s)"] <= FLOW
        )
    return ok, value


FINAL_EXPECTED = {"S3.T": TEMPERATURE, "duties": DUTY, "S3 split": FLOW}


def _phase_case(
    runs: Runs, ref: Mapping[str, Any], t02: Mapping[str, Any], name: str, sweep: str | None
) -> tuple[bool, dict[str, Any], dict[str, Any], Observed]:
    """A registered phase case's attempts and final state against `ref.cases.<id>`."""
    case_id = PHS[name]
    registered = ref["policy_simulation"]["cases"][case_id]
    observed = runs.region(case_id)
    result = observed.result
    attempts = [
        _compare_attempt(observed, k, _attempt(observed, k), entry)
        for k, entry in enumerate(registered["attempts"])
        if k < len(result.attempts)
    ]
    value: dict[str, Any] = {
        "outcome": result.outcome,
        "attempts": len(result.attempts),
        "per_attempt": attempts,
    }
    expected: dict[str, Any] = {
        "outcome": registered["outcome"],
        "attempts": len(registered["attempts"]),
        "per_attempt": [_registered_attempt(entry) for entry in registered["attempts"]],
    }
    ok = (
        result.outcome == registered["outcome"]
        and len(result.attempts) == len(registered["attempts"])
        and all(not attempt["mismatches"] for attempt in attempts)
    )
    if registered["final"] is not None:
        good, value["final"] = _final(
            result.state,
            registered["final"],
            t02["syn001"]["a02_sweep"][sweep] if sweep else None,
        )
        expected["final"] = {"t03_final": "ref.cases.final", "t02_sweep": sweep, **FINAL_EXPECTED}
        fingerprint = result.root_fingerprint
        closing = [
            entry
            for entry in observed.admissible
            if entry["attempt"] == len(result.attempts) - 1 and not entry["in_screen"]
        ]
        value["admissible_at_closure"] = [
            {"unit": entry["unit"], "branch": entry["regime"], "ok": entry["ok"]}
            for entry in closing
        ]
        value["root_fingerprint_branch_found"] = (
            fingerprint["branch_found"] if fingerprint else None
        )
        expected["admissible_at_closure"] = "every lifted unit admissible, by branch found"
        expected["root_fingerprint_branch_found"] = [
            ["U-HEAT", registered["final"]["branch_found"]],
            ["U-FLASH", "TWO_PHASE"],
        ]
        ok = (
            ok
            and good
            and bool(closing)
            and all(entry["ok"] for entry in closing)
            and value["root_fingerprint_branch_found"] == expected["root_fingerprint_branch_found"]
        )
    return ok, value, expected, observed


# --------------------------------------------------------------------------------- the build


def build(
    commit: str,
    gate_stdout: Path,
    identities: Path | None,
    ci_run: str | None,
) -> dict[str, Any]:
    ref: dict[str, Any] = yaml.safe_load(REFERENCE.read_text(encoding="utf-8"))
    t02: dict[str, Any] = yaml.safe_load(T02_REFERENCE.read_text(encoding="utf-8"))
    gate = _gate(gate_stdout)
    runs = Runs()
    checks: list[dict[str, Any]] = []

    checks.append(
        measured(
            "T03.A00",
            "Generator self-check: `t03_reference.py --check` passes with 107 checks; the "
            "committed YAML's SHA-256 equals the one in the specification header; `--emit` twice "
            "gives identical bytes, equal to the committed file; the generator and the two "
            "sibling closed-form scripts it imports import nothing from `openflowsheet` or "
            "`benchmarks` (every import statement, read from the syntax tree).",
            lambda: _a00(),
        )
    )
    checks.append(
        measured(
            "T03.A02",
            "One contract, one implementation: the decision function `phase_contract.decide` "
            "(spied) is called exactly once per attempt closure on the tear path (OFF-B) and the "
            "lifted path (PHS-01, PHS-04, PHS-05); both controllers construct the one "
            "`WallObserver`, defined in `phase_contract.py` alone; the cycling refusal "
            "`active_set_cycling(` is produced in `phase_contract.py` alone, and neither "
            "`attempts.py` nor `region.py` names `ACTIVE_SET_CYCLING` or `ATTEMPTS_EXHAUSTED`, "
            "tests `in used`, or compares against `max_attempts` (grep of the orchestrator "
            "sources; each attempt loop's `range(policy.max_attempts)` bound is not a rule — "
            "`decide` refuses at the bound and the loop's end is unreachable).",
            lambda: _a02(runs),
        )
    )
    checks.append(
        measured(
            "T03.A03",
            "[A01] on every multi-attempt registered case — OFF-B, T02 A21 (nominal `eo`), "
            "PHS-01…05, PHS-SYN-1/2: every event of attempt k from its `attempt_opened` on, "
            "except a rejected trial, carries σ_k; each attempt's `EvaluationContext` is a "
            "distinct object. Lifted path: every compiled residual and Jacobian call made from "
            "inside attempt k's problem passes attempt k's evaluation context object (spied at "
            "the compiled class); every σ_k-pinned variable is outside the attempt's free "
            "columns and bit-exactly `+0.0` (sign bit clear) in every vector the compiled "
            "problem received inside attempt k, every accepted iterate among them (review M3: "
            "the vectors the evaluator was given, not the end state the region writes); the "
            "attempt's row and column ids equal the keys of its `AttemptContext.row_scales` / "
            "`column_scales`. Tear path (OFF-B, review M3's probe): at the tear problem's "
            "boundary every residual call traverses under attempt k's flowsheet context and "
            "every Jacobian call takes attempt k's evaluation context and flowsheet; between "
            "attempt k's `attempt_opened` and `attempt_closed` every compiled call passes "
            "attempt k's evaluation context object and every provider call the tear code makes "
            "itself passes attempt k's flowsheet context object; provider calls made by the "
            "compiled problem's property blocks carry the context bound at assembly, asserted "
            "field-equal (`attempts._context_document`) to attempt k's — counted per attempt "
            "and category (see `limitations`).",
            lambda: _a03(runs),
        )
    )
    checks.append(
        measured(
            "T03.A04",
            "The evaluator does not choose: at every `ok` trial of every attempt of PHS-01 the "
            "screened residual's values are bit-identical (IEEE bytes) with the same attempt's "
            "residual built without the screen — the frozen formulation's; at iteration 0's "
            "α = 1 trial of attempt 1 the frozen `LIQUID` formulation evaluates and only the "
            "reported signature differs (`U-HEAT:VAPOR`, the unscreened evaluation reports none).",
            lambda: _a04(runs),
        )
    )
    checks.append(
        measured(
            "T03.A05",
            "The screen: every call of K03 §8.2's check `_admissible` (spied), from the screen "
            "and from the closure alike, uses `policy.admissibility_epsilon` (1e-12) — one "
            "callable for both, the closure's calls observed on every converged attempt; no "
            "`TWO_PHASE` unit is screened; on attempt 1 the screen reads exactly the trials the "
            "twin screens (PHS-01 15, PHS-02 14, PHS-03 8 = the registered trials less the "
            "domain-refused ones), flags exactly those whose registered value exceeds 1 + ε, and "
            "the kernel flash is called once per flagged trial and on no other — PHS-01 13, "
            "PHS-02 12, PHS-03 6; the opening state is never screened (every attempt's screen "
            "invocations equal its screened trials), and PHS-04's `LIQUID` attempt, whose "
            "opening the check refuses at `ref…opening_screen_value` 1.075 417 012 292 933 "
            "(1e-9 relative), converges.",
            lambda: _a05(runs, ref),
        )
    )
    checks.append(
        measured(
            "T03.A06",
            "PHS-01 (`SYN-001-A02-355-liquid-guess`) attempt 1 against "
            "`ref.cases…attempts[0]`: every trial's iteration, halving, verdict, α and reported "
            "heater regime exactly, its `S3.T` to 1e-9 relative (the residual call observed per "
            "trial); accepted iterates 351.232 445 119 600 and 351.381 686 520 802 K among "
            "them; `PHASE_UPDATE_REQUIRED` on patience at core iteration 2; 13 phase rejections, "
            "0 invalid trials.",
            lambda: _a06(runs, ref, t02),
        )
    )
    checks.append(
        measured(
            "T03.A07",
            "PHS-01 restart: attempt 2 opens `(U-HEAT:TWO_PHASE, U-FLASH:TWO_PHASE)` from "
            "`phase_rejected_trial` (iteration 1, halving 1), `attempt_opened.alpha = 0.5`, "
            "`S3.T = 370.335 344 473 404 K` and β = 0.664 711 039 122 145 (1e-9 relative), "
            "message `phase_update(phase_wall(patience, U-HEAT:LIQUID->TWO_PHASE))`; the α = 1 "
            "candidate of the same line search reported `VAPOR` and was not chosen.",
            lambda: _a07(runs, ref),
        )
    )
    checks.append(
        measured(
            "T03.A08",
            "PHS-01 attempt 2: iteration 0's accepted step is at `α_max = 0.683 005 540 573 936` "
            "(1e-9 relative) with `S3.vap.C` exactly `+0.0`, and the attempt continues; every "
            "trial as registered; `CONVERGED` at core iteration 5; the solve `CONVERGED` in "
            "exactly 2 attempts; final state = `t02.syn001.a02_sweep[T_heater=355K]` and the "
            "twin's final record by kind (1e-5 K, 1e-2 W, 3.1e-7 mol/s); every lifted unit "
            "admissible at closure; a `root_fingerprint` with `branch_found` all `TWO_PHASE`.",
            lambda: _a08(runs, ref, t02),
        )
    )
    checks.append(
        measured(
            "T03.A09",
            "PHS-02 (`SYN-001-A02-360-liquid-guess`) against `ref.cases`: attempt 1 with the "
            "α = 1 trial (442.639 559 394 732 K) `invalid_trial` in both iterations and not "
            "screened, accepted 350.723 746 557 771 and 351.441 838 845 560 K, patience at 2, 12 "
            "phase rejections, 2 invalid; restart (1, 2), α = 0.25, 373.702 699 767 012 K, "
            "β = 0.807 854 853 272; attempt 2 lands `S3.vap.C` at "
            "`α_max = 0.848 058 504 137 589`, continues, `CONVERGED` at 4; final = the 360 K row.",
            lambda: _a09_a10(runs, ref, t02, "PHS-02"),
        )
    )
    checks.append(
        measured(
            "T03.A10",
            "PHS-03 (`SYN-001-A02-360-vapor-guess`, 400 K) against `ref.cases`: attempt 1 "
            "`VAPOR`, α = 1 and 1/2 `invalid_trial` in both iterations, the far `LIQUID` "
            "candidates at halving 2 skipped; accepted 383.580 026 850 553 and "
            "379.731 595 643 652 K; patience at 2; restart (1, 3), α = 0.125, "
            "352.792 577 195 341 K, β = 0.048 273 238 6; attempt 2 `CONVERGED` at 4 with no "
            "landing (every accepted α = 1); final = the 360 K row.",
            lambda: _a09_a10(runs, ref, t02, "PHS-03"),
        )
    )
    checks.append(
        measured(
            "T03.A11",
            "PHS-04 (`SYN-001-A02-340-two-phase-guess`) against `ref.cases`: attempt 1 lands "
            "`S3.vap.C` at `α_max = 0.611 571 194 452 767` and its core ends `BOUND_BLOCKED` at "
            "iteration 1 with `blocked_by = (S3.vap.C)`; attempt 2 `LIQUID` from "
            "`pinned_iterate`, message `phase_update(phase_disappeared(U-HEAT, vapor, "
            "S3.vap.C))`, opening at 354.208 439 732 282 K with the opening vector equal, bit for "
            "bit, to attempt 1's end state with the vapour pinned (`S3.vap.* = S3.V = +0.0`, "
            "`S3.liq = S3.n`); `CONVERGED` at core iteration 1; `S3.T = 340`, "
            "`U-HEAT.Q = 8 721.618 138 446 303 W` (T02's 340 K row), `S3.V = 0.0` exactly; "
            "admissible at closure with `Σ x K = 0.731 446 283…` (1e-9 relative).",
            lambda: _a11(runs, ref, t02),
        )
    )
    checks.append(
        measured(
            "T03.A12",
            "PHS-05 (`SYN-001-A02-355-dew-guess`, expected failure): attempt 1 lands at "
            "`α_max = 0.642 309 461 269 271` and its core ends `BOUND_BLOCKED` at 1 on "
            "`S3.vap.C` alone; attempt 2 `LIQUID` opens at 365.572 400 509 395 K; its core ends "
            "`LINE_SEARCH_FAILED` at iteration 0 with exactly 21 phase-rejected trials, each as "
            "registered; the solve ends `ACTIVE_SET_CYCLING` with §6.4's message; no "
            "certificate target (no `root_fingerprint`); checkpoint `partial`; the failure "
            "class and action the bundle builder resolves for the outcome "
            "(`TAXONOMY`, `OUTCOME_ACTIONS` over `ACTIONS`) are `homotopy/PTC/active-set "
            "stalls` and `supply_initial_guess`; no `INFEASIBLE`; the registry entry is outside "
            "the success denominator with `handed_to: T04`.",
            lambda: _a12(runs, ref),
        )
    )
    checks.append(
        measured(
            "T03.A13",
            "Regression under the contract. T02 A21 (nominal `eo` from `x(t⁰)`): exactly 2 "
            "attempts; attempt 1's core ends `BOUND_BLOCKED` at iteration 1 with `S3.vap.B` in "
            "`blocked_by`, converted to `phase_disappeared(U-HEAT, vapor, S3.vap.B)`; attempt 2 "
            "opens, bit for bit, from T02's pinned iterate (attempt 1's end state with the heater "
            "vapour pinned); attempt 2 `LIQUID` converges within 5; T02's own A21–A24 "
            "measurements (`scripts/t02_evidence_manifest.py`) still pass. T02 A28/A29's cases "
            "(guess 358 K) converge in 1 attempt with 3, 3, 4 core iterations "
            "(`ref.t02_successes_under_the_contract`) and no landing (every accepted α = 1).",
            lambda: _a13(runs, ref),
        )
    )
    checks.append(
        measured(
            "T03.A14",
            "Adjacency on the tear path: PHS-SYN-1 and PHS-SYN-2 through the bare controller — "
            "every evaluated point (each opening and each trial) exactly the twin's dyadic "
            "rationals, every attempt's signature, `CONVERGED` at x = 3 in 3 and 2 attempts; "
            "OFF-B restarts from the largest-α phase-rejected trial of its last line search, "
            "`TWO_PHASE` (K03's point), and K03's own attempt tests "
            "(`tests/test_k03_attempts.py`, A12/A29 included) pass when rerun here.",
            lambda: _a14(runs, ref),
        )
    )
    checks.append(
        measured(
            "T03.A15",
            "Sparsity rebuild: every region `AttemptContext` carries `jacobian_pattern` with the "
            "shape `ref.closed_form.region_shapes_rows_by_columns` gives its signature (42 × 42 "
            "two-phase, 38 × 38 single-phase heater) and an `nnz` equal to an independent count "
            "here of the compiled structural pattern's entries restricted by id to the "
            "attempt's rows and columns (review S5: not recomputed with the function that "
            "recorded it), fewer than rows × columns; within a solve, one `sha256` per "
            "signature and distinct across signatures; on PHS-01 the 38 × 38 entry set is exactly "
            "the 42 × 42 set restricted to its ids; every factorized Jacobian of every region "
            "attempt has the recorded shape and stores no entry outside the recorded pattern; "
            "OFF-B's two tear attempts record the same non-null pattern; the bare controller's "
            "is null; the exact property cache is never cleared across `attempt_opened` "
            "(its size does not decrease).",
            lambda: _a15(runs, ref),
        )
    )
    checks.append(
        measured(
            "T03.A16",
            "Opening checks: on every opening of every region solve here and of OFF-B's tear "
            "solve (review S5: `attempts.check_opening` spied as well as the region's) the six "
            "checks hold (every `check_opening` call observed returns none), and, recomputed "
            "from the opening vectors each restart's problem and compiled residual received, "
            "coverage (finite), active set "
            "(σ'-pinned variables exactly `+0.0`) and bounds (molar flows ≥ 0) hold. The four "
            "constructed refusals — `scale_segment` (1), `identity` (another `model_version`), "
            "`bounds` (`S3.liq.B = −1e-9`) on PHS-01, `active_set` (`S3.vap.A = 1e-3` under "
            "`LIQUID`) on PHS-04 — each end `CHECKPOINT_INCOMPATIBLE` with exactly the message "
            "naming the check and the variable or field, and no float in it (review S4): "
            "`checkpoint_incompatible(scale_segment, scale_segment)`, `(identity, "
            "model_version)`, `(bounds, S3.liq.B)`, `(active_set, S3.vap.A)`; the offending "
            "value on the attempt's `observations` instead (`{bounds:S3.liq.B: -1e-9}`, "
            "`{active_set:S3.vap.A: 0.001}`, none for the other two), no "
            "`attempt_opened` for the refused attempt, no residual or Jacobian call after the "
            "decision, checkpoint `partial`, no certificate target, failure class "
            "`homotopy/PTC/active-set stalls` and action `report_defect` (an override of the "
            "class's).",
            lambda: _a16(runs),
        )
    )
    checks.append(
        measured(
            "T03.A17",
            "Opening record, on both paths (the region solves PHS-01…05, T02's A02-355/360/365 "
            "and A21; OFF-B on the tear): every `attempt_opened.state_sha256` is non-empty "
            "and equals ADR 0008 D2's hash of the observed opening free vector (region: the "
            "attempt's first residual call; tear: OFF-B's start, then the chosen trial's own "
            "hash) and the provenance item's `opening_state_sha256`; `alpha` is set iff the "
            "source is `phase_rejected_trial` and equals that candidate's `trial.alpha`; every "
            "`attempt_opened` message (`initial` exactly on attempt 0) and every terminal "
            "decision produced here — PHS-05's and K03's two-regime seed's "
            "`ACTIVE_SET_CYCLING`, A16's four constructed `CHECKPOINT_INCOMPATIBLE` — parses "
            "under §4.10's grammar as amended (review S4: no number in `inadmissible(…)` or "
            "`checkpoint_incompatible(…)`), written out in this script; `opened_from` is the "
            "closing attempt's `partial` checkpoint.",
            lambda: _a17(runs),
        )
    )
    checks.append(
        measured(
            "T03.A18",
            "Bounded cycling and budget: PHS-05 ends `ACTIVE_SET_CYCLING` (A12); K03's "
            "constructed two-regime seed ends `ACTIVE_SET_CYCLING` and its budget construction "
            "(`root_in_b = −2`, `max_attempts = 2`) `ATTEMPTS_EXHAUSTED`, each the terminal "
            "decision of the one decision function (spied); PHS-01 with `max_attempts = 1` ends "
            "`ATTEMPTS_EXHAUSTED` after attempt 1's patience closure, checkpoint `partial`; no "
            "solve measured in this manifest ran more attempts than its policy's `max_attempts`.",
            lambda: _a18(runs),
        )
    )
    checks.append(
        measured(
            "T03.A19",
            "REC-05 (γ = 0.1) provenance, against `ref.multiple_roots`: MR-A (`anderson` from "
            "1.1 t*) `CONVERGED` within `δ_root` of `S1` (scaled by 3 mol/s); MR-B `CONVERGED` "
            "at iteration 0 on `t*`; MR-C (`depth_max = 0`) `RECYCLE_STAGNATION` at 20, then a "
            "merge whose Newton converges within 5 iterations (twin 3) within `δ_root` of `S1`; "
            "`same_root(MR-A, MR-B) = DISTINCT`, `same_root(MR-A, MR-C) = SAME` with different "
            "`branch_provenance`; each result's item 0 has `initializer_source = user_guess` and "
            "`opening_state_sha256` equal to the hash of its start; MR-C's list is "
            "`[(anderson, initializer), (newton, merge_best_iterate)]`.",
            lambda: _a19(runs, ref),
        )
    )
    checks.append(
        measured(
            "T03.A20",
            "SYN-001 one root, three histories: SYN-001-A02-360 from 358 K, PHS-02 and PHS-03 "
            "are pairwise `SAME` under `same_root` with the plan's column scales; their "
            "`branch_provenance` lengths are 1, 2, 2 with different opening sources, and their "
            "item-0 `opening_state_sha256` are three different hashes.",
            lambda: _a20(runs),
        )
    )
    checks.append(
        measured(
            "T03.A21",
            "No overclaim: every root fingerprint issued by a solve in this manifest has "
            "`claims` `NOT_ASSESSED` for uniqueness and dynamic stability; every certificate "
            "issued here — OFF-B's, the one converged tear solve this check certifies — "
            "validates against the extended `solution-certificate.schema.json`, lists "
            "`[LIQUID: restart, phase_wall(patience, U-FLASH:LIQUID->TWO_PHASE); TWO_PHASE: "
            "converged]` in §8.1's item shape, one item per attempt, carries a §8.2 fingerprint "
            "whose `branch_found` is `[[U-HEAT, LIQUID], [U-FLASH, TWO_PHASE]]` (read from the "
            "reconstructed state, review M1), and says `unique root` or `stable` nowhere outside "
            "the `dynamic_stability` key. The review's ruling (§8): a non-`CONVERGED` solve is "
            "issued no certificate — `verify()` on OFF-B under `max_attempts = 1` "
            "(`ATTEMPTS_EXHAUSTED`) raises `VerifierError`, and that solve result carries no "
            "`root_fingerprint` and exactly one `branch_provenance` item, `decision: restart` "
            "with the patience cause (the restart the budget refused, R-029).",
            lambda: _a21(runs),
        )
    )
    checks.append(
        measured(
            "T03.A22",
            "`NOT_COMPARABLE`: MR-A's fingerprint against a copy differing only in "
            "`model_version`, and separately only in `variable_ids_sha256`, returns "
            "`NOT_COMPARABLE` — never `SAME` or `DISTINCT` — at the same state (the unchanged "
            "copy, the control, `SAME`). With it, §8.3 as amended (review S3): `same_root` "
            "refuses with `RootComparisonError`, never a verdict, for empty scales, for MR-A's "
            "fingerprint paired with MR-B's state, and for variable ids that are not the "
            "fingerprint's.",
            lambda: _a22(runs),
        )
    )
    checks.append(_a23(identities))
    checks.append(
        measured(
            "T03.A24",
            "`SYN-001-A02-360-no-guess` through the plan executor: the A02 plan is built with "
            "`S3.T` in the `solve_eo` step's `adjusted_variables`; one `initializer_rejected` "
            "with `missing_initial_guess(S3.T)`; outcome `INITIALIZATION_FAILED` with the same "
            "message; no `attempt_opened`, zero Jacobian calls; no `CONVERGED` anywhere in the "
            "trace.",
            lambda: _a24(),
        )
    )
    checks.append(
        measured(
            "T03.A25",
            "Regression gate: the gate's pytest run passed with no failure, error or skip, and "
            "the number it passed equals the number of tests `pytest --collect-only` finds "
            "here, among them K03's, T02's, K04's, K05's and T03's own test files (counted per "
            "family) — every one of them ran green in the gate, with §10's re-registrations "
            "already in the tests. The two-architecture half is A26's `--ci-run`.",
            lambda: _a25(gate),
        )
    )
    # A01 is measured last, over every solve the checks above ran, and filed in its place.
    checks.insert(
        1,
        measured(
            "T03.A01",
            "`SolvePolicy.phase_contract`: every policy that reached the decision function in "
            "any solve of this manifest carries `T03-phase-contract-v1` and its document "
            "validates against `solve-policy.schema.json`; the schema refuses the policy without "
            "the field and with any other value (`T02-interim`, `T03-phase-contract-v2`); the "
            "committed round-trip fixtures of `solve-policy`, `attempt-context`, `solve-event`, "
            "`checkpoint`, `solve-plan` (K03's generator) and `solution-certificate`, "
            "`regularity-evidence`, `failure-bundle` (K04's) are what the generators emit today "
            "under the ADR 0007 comparison and validate against their schemas.",
            lambda: _a01(runs),
        ),
    )

    covered = [entry["id"] for entry in checks]
    registered = [f"T03.{identifier}" for identifier in ASSERTIONS]
    requirements = ["D09", "D11", "A01"]
    ids_ok = covered + ["T03.A26"] == registered
    v15_refused = _schema_refuses_requirement("V15")
    a26_ok = ids_ok and v15_refused
    checks.append(
        check(
            "T03.A26",
            "This manifest carries one `checks[]` entry per assertion of spec §11, "
            "`T03.A00`…`T03.A26`, including every `unsupported`; `requirements` is spec A26's "
            "`[D09, D11, A01, V15]` less `V15`, which the frozen evidence-manifest schema "
            "refuses (items `^[DA][0-9]{2}$`, measured here) — T02's precedent; V15 is carried "
            "by `docs/requirements.yaml` (owner T03) and stated in `limitations`; `limitations` "
            "restates spec §13; `review` is unset (`pending` in both fields — no agent may set "
            "it); `commands` is the gate actually run here plus the named CI run on both "
            "architectures. Without `--ci-run` the two-architecture half of `commands` is absent "
            "and this check is `unsupported`.",
            (verdict(a26_ok) if ci_run else ("unsupported" if a26_ok else "fail")),
            {
                "entries": len(covered) + 1,
                "ids_in_order": ids_ok,
                "requirements": requirements,
                "V15_refused_by_the_frozen_schema": v15_refused,
                "ci_run": ci_run,
            },
            {
                "entries": len(registered),
                "ids_in_order": True,
                "requirements": "D09, D11, A01 (V15 in docs/requirements.yaml and limitations)",
                "V15_refused_by_the_frozen_schema": True,
                "ci_run": "a workflow run URL",
            },
        )
    )

    failed = [entry["id"] for entry in checks if entry["result"] == "fail"]
    a00 = checks[0]["value"]
    commands = [
        {
            "cmd": "PATH=.venv/bin:$PATH ./scripts/check.sh",
            "cwd": ".",
            "exit_code": 0 if gate["passed"] else 1,
            "stdout_sha256": hashlib.sha256(gate_stdout.read_bytes()).hexdigest(),
        },
        {
            "cmd": "PATH=.venv/bin:$PATH .venv/bin/python "
            "docs/derivations/scripts/t03_reference.py --check",
            "cwd": ".",
            "exit_code": int(a00.get("check_exit_code", 1)) if isinstance(a00, dict) else 1,
        },
        {
            "cmd": "PYTHONPATH=. .venv/bin/python scripts/t03_evidence_manifest.py "
            f"GATE_STDOUT --commit {commit}"
            + (f" --identities {identities.name}" if identities else "")
            + (f" --ci-run {ci_run}" if ci_run else ""),
            "cwd": ".",
            "exit_code": 1 if failed else 0,
        },
    ]
    if ci_run:
        # The `commands` schema has no field for a reference (K05's precedent): the run URL goes
        # in the command string, where a reader looking for how the pair was run will find it.
        commands.append(
            {
                "cmd": "GitHub Actions workflow `ci`, jobs `check` (ubuntu-latest, "
                f"ubuntu-24.04-arm) and `identity`: {ci_run}",
                "cwd": ".",
                "exit_code": 0,
            }
        )

    return {
        "work_package": "T03",
        "commit": commit,
        # The frozen schema takes D/A requirement ids only. V15 is a verification item of plan
        # §5, carried in `docs/requirements.yaml` (owner T02, T03), which points back here.
        "requirements": requirements,
        "status": _status(checks),
        "inputs": {
            "case_id": "The five registered phase cases PHS-01..05 (SYN-001-A02-355/360 "
            "liquid-guess, -360-vapor-guess, -340-two-phase-guess, -355-dew-guess), T02's "
            "SYN-001-A02-355/360/365 from 358 K and SYN-001-A02-360-no-guess; SYN-001 nominal "
            "under eo (T02 A21) and OFF-B on the tear path; the synthetic tear seeds PHS-SYN-1/2 "
            "and K03's constructed seeds; REC-05 at gamma 0.1 (MR-A/B/C); judged against "
            f"benchmarks/t03/reference_values.yaml ({file_sha256(REFERENCE)}), "
            f"benchmarks/t02/reference_values.yaml ({file_sha256(T02_REFERENCE)}), "
            f"benchmarks/syn001/reference_values.yaml ({file_sha256(P01)}) and "
            f"docs/derivations/T03-phase-controller-spec.md ({file_sha256(SPEC)})",
            "case_hash": _case_hash(),
            "environment_lock_hash": file_sha256(ROOT / "requirements.lock"),
        },
        "commands": commands,
        "checks": checks,
        "artifacts": [],
        "limitations": _limitations(ci_run is not None, identities is not None),
        "review": {"numerical": "pending", "process_model": "pending"},
    }


def _status(checks: Sequence[Mapping[str, Any]]) -> str:
    """`tested` when nothing failed. An `unsupported` check carries its reason in its own
    description (the CI halves without their artifacts), which is T01's, K05's and T02's rule;
    a `fail` anywhere leaves the package `implemented`, never `tested`."""
    return "implemented" if any(entry["result"] == "fail" for entry in checks) else "tested"


def _case_hash() -> str:
    """One digest over every registered revision this package ran, in name order."""
    digest = hashlib.sha256()
    for name in sorted((*PHS.values(), *T02_SUCCESSES, NO_GUESS)):
        digest.update((CASES / f"{name}.yaml").read_bytes())
    return digest.hexdigest()


def _gate(gate_stdout: Path) -> dict[str, Any]:
    text = gate_stdout.read_text(encoding="utf-8")
    counts = _pytest_counts(text)
    return {
        "passed": "=== check.sh: PASSED ===" in text,
        "pytest_passed": counts.get("passed", 0),
        "pytest_counts": counts,
        "pytest_failed_or_errors": bool(
            counts.get("failed", 0) + counts.get("error", 0) + counts.get("errors", 0)
        ),
    }


def _pytest_counts(text: str) -> dict[str, int]:
    """The last pytest summary line (`3 failed, 1511 passed in 27.1s`), as counts by word."""
    lines = re.findall(r"^((?:\d+ [a-z]+(?:, )?)+) in [\d.]+s", text, flags=re.MULTILINE)
    if not lines:
        return {}
    return {word: int(count) for count, word in re.findall(r"(\d+) ([a-z]+)", lines[-1])}


def _schema_refuses_requirement(identifier: str) -> bool:
    from jsonschema import Draft202012Validator

    schema = json.loads(
        (ROOT / "schemas" / "evidence-manifest.schema.json").read_text(encoding="utf-8")
    )
    items = schema["properties"]["requirements"]
    return bool(list(Draft202012Validator(items).iter_errors([identifier])))


# ----------------------------------------------------------------------------------- A00


def _a00() -> tuple[bool, Any, Any]:
    completed = subprocess.run(  # noqa: S603
        [sys.executable, str(GENERATOR), "--check"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    counted = re.findall(r"^(\d+) checks passed", completed.stdout, flags=re.MULTILINE)
    digest = file_sha256(REFERENCE)
    header = SPEC.read_text(encoding="utf-8").split("\n---\n", 1)[0]
    with tempfile.TemporaryDirectory() as scratch:
        first, second = Path(scratch) / "a.yaml", Path(scratch) / "b.yaml"
        for destination in (first, second):
            subprocess.run(  # noqa: S603
                [sys.executable, str(GENERATOR), "--emit", str(destination)],
                capture_output=True,
                cwd=ROOT,
                check=True,
            )
        twice = first.read_bytes() == second.read_bytes()
        committed = first.read_bytes() == REFERENCE.read_bytes()
    forbidden: list[str] = []
    for script in ("t03_reference.py", "t02_reference.py", "syn001_reference.py"):
        tree = ast.parse((GENERATOR.parent / script).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            forbidden += [
                f"{script}: {name}"
                for name in names
                if name.split(".")[0] in {"openflowsheet", "benchmarks"}
            ]
    value = {
        "check_exit_code": completed.returncode,
        "checks_passed": int(counted[-1]) if counted else None,
        "reference_sha256": digest,
        "digest_in_spec_header": digest in header,
        "emit_twice_identical": twice,
        "emit_equals_committed": committed,
        "forbidden_imports": forbidden,
    }
    expected = {
        "check_exit_code": 0,
        "checks_passed": 107,
        "digest_in_spec_header": True,
        "emit_twice_identical": True,
        "emit_equals_committed": True,
        "forbidden_imports": [],
    }
    return all(value[key] == expected[key] for key in expected), value, expected


# ------------------------------------------------------------------------------ A01–A05


def _validator(name: str) -> Any:
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource

    documents = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (ROOT / "schemas").glob("*.schema.json")
    ]
    registry = Registry().with_resources(
        (document["$id"], Resource.from_contents(document))
        for document in documents
        if "$id" in document
    )
    (schema,) = [
        document for document in documents if str(document.get("$id", "")).endswith("/" + name)
    ]
    return Draft202012Validator(schema, registry=registry)


def _a01(runs: Runs) -> tuple[bool, Any, Any]:
    from k03_schema_fixtures import documents as k03_documents
    from k04_schema_fixtures import documents as k04_documents

    from openflowsheet.run.compare import differences

    policy_validator = _validator("solve-policy.schema.json")
    policies = runs.all_policies()
    distinct = {id(policy): policy for policy in policies}.values()
    per_policy = sorted(
        {
            (
                policy.policy_id,
                policy.phase_contract,
                policy.as_document().get("phase_contract"),
                len(list(policy_validator.iter_errors(policy.as_document()))),
            )
            for policy in distinct
        }
    )
    document = TEAR_POLICY.as_document()
    refusals = {
        "without": bool(
            list(
                policy_validator.iter_errors(
                    {key: item for key, item in document.items() if key != "phase_contract"}
                )
            )
        ),
        "T02-interim": bool(
            list(policy_validator.iter_errors({**document, "phase_contract": "T02-interim"}))
        ),
        "T03-phase-contract-v2": bool(
            list(
                policy_validator.iter_errors(
                    {**document, "phase_contract": "T03-phase-contract-v2"}
                )
            )
        ),
    }

    fixture_root = ROOT / "tests" / "fixtures" / "schemas"
    fixtures: dict[str, Any] = {}
    for emitted in (k03_documents(), k04_documents()):
        for name, emitted_document in emitted.items():
            committed = json.loads((fixture_root / name).read_text(encoding="utf-8"))
            schema = name.split("/", 1)[0].replace("_", "-") + ".schema.json"
            validator = _validator(schema)
            payload = committed if isinstance(committed, list) else [committed]
            fixtures[name] = {
                "differences_from_emitted": differences(
                    emitted_document, committed, policy_id="K04-numerical-policy-v1"
                )[:5],
                "schema_errors": sum(len(list(validator.iter_errors(entry))) for entry in payload),
            }
    policy_fixture = json.loads(
        (fixture_root / "solve_policy" / "valid" / "syn001_k03.json").read_text(encoding="utf-8")
    )
    value = {
        "policies_reaching_decide": len(policies),
        "distinct_policies": [
            {"policy_id": i, "phase_contract": c, "document": d, "schema_errors": e}
            for i, c, d, e in per_policy
        ],
        "schema_refuses": refusals,
        "policy_fixture_phase_contract": policy_fixture.get("phase_contract"),
        "fixtures": fixtures,
    }
    expected = {
        "distinct_policies": "every one: phase_contract and document T03-phase-contract-v1, "
        "0 schema errors",
        "schema_refuses": dict.fromkeys(refusals, True),
        "policy_fixture_phase_contract": PHASE_CONTRACT,
        "fixtures": "every one: no difference from what its generator emits, 0 schema errors",
    }
    ok = (
        bool(policies)
        and all(c == PHASE_CONTRACT and d == PHASE_CONTRACT and e == 0 for _, c, d, e in per_policy)
        and all(refusals.values())
        and policy_fixture.get("phase_contract") == PHASE_CONTRACT
        and bool(fixtures)
        and all(
            not entry["differences_from_emitted"] and entry["schema_errors"] == 0
            for entry in fixtures.values()
        )
    )
    return ok, value, expected


def _a02(runs: Runs) -> tuple[bool, Any, Any]:
    tear = runs.off_b()
    per_run = {
        "OFF-B (tear)": {
            "decide_calls": len(tear.decisions),
            "attempt_closures": tear.result.attempts,
        }
    }
    for name in ("PHS-01", "PHS-04", "PHS-05"):
        observed = runs.region(PHS[name])
        per_run[f"{name} (region)"] = {
            "decide_calls": len(observed.decisions),
            "attempt_closures": len(observed.result.attempts),
        }
    sources = {path.name: path.read_text(encoding="utf-8") for path in ORCHESTRATOR.glob("*.py")}
    producing = sorted(name for name, text in sources.items() if "active_set_cycling(" in text)
    defining_wall = sorted(name for name, text in sources.items() if "class WallObserver" in text)
    # A cycle or budget rule of its own: either refusal outcome named, a used-signature test, or
    # a comparison against `max_attempts` (the attempt loop's `range(policy.max_attempts)` bound
    # is not one: the refusal at the bound is `decide`'s, and the loop's end is unreachable).
    budget_comparison = re.compile(r"[<>]=?\s*[\w.]*max_attempts|max_attempts\s*[<>]")
    own_rules = {
        name: [
            token
            for token in ("ACTIVE_SET_CYCLING", "ATTEMPTS_EXHAUSTED", " in used")
            if token in sources[name]
        ]
        + budget_comparison.findall(sources[name])
        for name in ("attempts.py", "region.py")
    }
    constructs_wall = {
        name: "WallObserver(policy)" in sources[name] for name in ("attempts.py", "region.py")
    }
    value = {
        "per_run": per_run,
        "cycling_refusal_produced_in": producing,
        "WallObserver_defined_in": defining_wall,
        "WallObserver_constructed_by": constructs_wall,
        "own_cycle_or_budget_rule": own_rules,
    }
    expected = {
        "per_run": "decide_calls == attempt_closures on every run (2, 2, 2, 2)",
        "cycling_refusal_produced_in": ["phase_contract.py"],
        "WallObserver_defined_in": ["phase_contract.py"],
        "WallObserver_constructed_by": {"attempts.py": True, "region.py": True},
        "own_cycle_or_budget_rule": {"attempts.py": [], "region.py": []},
    }
    ok = (
        all(row["decide_calls"] == row["attempt_closures"] > 0 for row in per_run.values())
        and producing == ["phase_contract.py"]
        and defining_wall == ["phase_contract.py"]
        and all(constructs_wall.values())
        and not any(own_rules.values())
    )
    return ok, value, expected


def _signature_violations(trace: Any, signatures: Sequence[Any]) -> list[str]:
    """Events of attempt k, from its `attempt_opened` on, not carrying σ_k — rejected trials
    excepted (a rejected trial records the signature it found)."""
    opened = {e.attempt: e.sequence for e in trace.events if e.kind == "attempt_opened"}
    found: list[str] = []
    for event in trace.events:
        if event.kind in ("plan_built", "solve_closed") or event.attempt not in opened:
            continue
        if event.sequence < opened[event.attempt]:
            continue
        if event.kind == "trial" and event.trial_status == "rejected":
            continue
        if tuple(event.signature) != tuple(signatures[event.attempt]):
            found.append(f"{event.sequence} {event.kind} attempt {event.attempt}")
    return found


def _a03(runs: Runs) -> tuple[bool, Any, Any]:
    value: dict[str, Any] = {}
    ok = True
    region_runs = [(name, runs.region(case_id)) for name, case_id in PHS.items()]
    region_runs.append(("T02 A21", runs.nominal_eo()))
    for name, observed in region_runs:
        result = observed.result
        contexts = result.contexts
        signatures = [attempt.signature for attempt in result.attempts]
        order = {variable: index for index, variable in enumerate(observed.spec.variable_ids)}
        pinned_off: list[str] = []
        scales_off: list[int] = []
        foreign_context: list[str] = []
        compiled_per_attempt: dict[int, int] = {}
        for k, context in enumerate(contexts):
            if set(context.column_scales) != set(observed.free[k]) or set(
                context.row_scales
            ) != set(observed.rows[k]):
                scales_off.append(k)
            regimes = dict(result.attempts[k].signature)
            pinned = [
                variable
                for split in syn001_lifted_splits(COMPONENTS)
                if split.unit in regimes
                for variable in split.pinned(regimes[split.unit])
            ]
            pinned_off += [
                f"attempt {k}: {variable} is a free column"
                for variable in pinned
                if variable in observed.free[k]
            ]
            own = id(context.evaluation_context)
            received = [(ctx, x) for at, ctx, x in observed.compiled_calls if at == k]
            compiled_per_attempt[k] = len(received)
            foreign = sum(1 for ctx, _ in received if ctx != own)
            if foreign:
                foreign_context.append(f"attempt {k}: {foreign} of {len(received)} calls")
            # Review M3: the pinned positions of every vector the compiled problem received
            # inside attempt k — every accepted iterate among them — bit-exactly `+0.0`.
            for index, (_, x) in enumerate(received):
                pinned_off += [
                    f"attempt {k} call {index}: {variable} = {float(x[order[variable]])!r}"
                    for variable in pinned
                    if not positive_zero(float(x[order[variable]]))
                ]
        row = {
            "attempts": len(contexts),
            "distinct_context_objects": len({id(c.evaluation_context) for c in contexts})
            == len(contexts),
            "problem_built_under_own_context": observed.context_ids
            == [id(c.evaluation_context) for c in contexts],
            "compiled_calls_per_attempt": compiled_per_attempt,
            "compiled_calls_under_another_context": foreign_context,
            "scales_keys_equal_ids": not scales_off,
            "pinned_violations": pinned_off[:10],
            "events_off_signature": _signature_violations(observed.trace, signatures),
        }
        value[name] = row
        ok = ok and (
            row["attempts"] >= 2
            and row["distinct_context_objects"]
            and row["problem_built_under_own_context"]
            and all(count > 0 for count in compiled_per_attempt.values())
            and not foreign_context
            and row["scales_keys_equal_ids"]
            and not pinned_off
            and not row["events_off_signature"]
        )

    tear = runs.off_b()
    contexts = tear.result.contexts
    ids = [(id(c.flowsheet_context), id(c.evaluation_context)) for c in contexts]

    def all_own(calls: Mapping[int, list[int | None]], which: int) -> bool:
        return sorted(calls) == list(range(len(contexts))) and all(
            entries and all(entry == ids[k][which] for entry in entries)
            for k, entries in calls.items()
        )

    def per_attempt(pairs: Sequence[tuple[int, Any]], own: Callable[[int, Any], bool]) -> Any:
        return {
            k: {
                "calls": sum(1 for at, _ in pairs if at == k),
                "own": sum(1 for at, item in pairs if at == k and own(k, item)),
            }
            for k in range(len(contexts))
        }

    compiled = per_attempt(tear.compiled_calls, lambda k, item: item == ids[k][1])
    by_tear = per_attempt(tear.tear_provider_calls, lambda k, item: item == ids[k][0])
    by_blocks = per_attempt(
        tear.block_provider_calls,
        lambda k, item: attempts_module._context_document(item)
        == attempts_module._context_document(contexts[k].flowsheet_context),
    )
    blocks_same_object = sum(
        1 for at, item in tear.block_provider_calls if item is contexts[at].flowsheet_context
    )
    row = {
        "attempts": len(contexts),
        "distinct_context_objects": len({i for pair in ids for i in pair}) == 2 * len(contexts),
        "at_the_tear_problem_boundary": {
            "residual_calls": {k: len(v) for k, v in tear.residual_contexts.items()},
            "residual_under_own_flowsheet_context": all_own(tear.residual_contexts, 0),
            "jacobian_calls": {k: len(v) for k, v in tear.jacobian_contexts.items()},
            "jacobian_under_own_evaluation_context": all_own(tear.jacobian_contexts, 1),
            "jacobian_under_own_flowsheet_context": all_own(tear.jacobian_flowsheet_contexts, 0),
        },
        "inside_an_open_attempt": {
            "compiled_calls (own = the attempt's evaluation_context object)": compiled,
            "provider_calls_by_the_tear_code (own = the attempt's flowsheet_context object)": (
                by_tear
            ),
            "provider_calls_by_compiled_property_blocks (own = field-equal to the attempt's "
            "flowsheet_context; the context bound at assembly)": by_blocks,
            "block_calls_carrying_the_attempts_own_object": blocks_same_object,
        },
        "events_off_signature": _signature_violations(tear.trace, tear.result.signatures),
    }
    value["OFF-B"] = row
    boundary = row["at_the_tear_problem_boundary"]
    ok = ok and (
        row["attempts"] == 2
        and row["distinct_context_objects"]
        and boundary["residual_under_own_flowsheet_context"]
        and boundary["jacobian_under_own_evaluation_context"]
        and boundary["jacobian_under_own_flowsheet_context"]
        and all(
            entry["calls"] > 0 and entry["own"] == entry["calls"]
            for category in (compiled, by_tear, by_blocks)
            for entry in category.values()
        )
        and not row["events_off_signature"]
    )

    for name in ("PHS-SYN-1", "PHS-SYN-2"):
        seed = runs.synthetic(name)
        contexts = seed.result.contexts
        row = {
            "attempts": len(contexts),
            "distinct_context_objects": len({id(c.evaluation_context) for c in contexts})
            == len(contexts),
            "events_off_signature": _signature_violations(seed.trace, seed.result.signatures),
        }
        value[name] = row
        ok = ok and (
            row["attempts"] >= 2
            and row["distinct_context_objects"]
            and not row["events_off_signature"]
        )
    expected = {
        "every region run": {
            "attempts": "at least 2",
            "distinct_context_objects": True,
            "problem_built_under_own_context": True,
            "compiled_calls_per_attempt": "at least 1 per attempt",
            "compiled_calls_under_another_context": [],
            "scales_keys_equal_ids": True,
            "pinned_violations": [],
            "events_off_signature": [],
        },
        "OFF-B": {
            "attempts": 2,
            "distinct_context_objects": True,
            "at_the_tear_problem_boundary": "every residual and Jacobian call of attempt k "
            "under attempt k's context objects",
            "inside_an_open_attempt": "per attempt and category: at least 1 call, own == calls",
            "events_off_signature": [],
        },
        "bare controller (PHS-SYN-1/2)": {
            "attempts": "at least 2",
            "distinct_context_objects": True,
            "events_off_signature": [],
        },
    }
    return ok, value, expected


def _a04(runs: Runs) -> tuple[bool, Any, Any]:
    observed = runs.region(PHS["PHS-01"])
    checked, differing = 0, []
    for k, calls in enumerate(observed.calls):
        for index, (x, evaluation) in enumerate(calls):
            frozen = observed.plain[k](x)
            if frozen.status != evaluation.status:
                differing.append(f"attempt {k} call {index}: status")
            elif evaluation.status == "ok":
                checked += 1
                if (
                    np.asarray(frozen.values, dtype=np.float64).tobytes()
                    != np.asarray(evaluation.values, dtype=np.float64).tobytes()
                ):
                    differing.append(f"attempt {k} call {index}: values")
    x, first = observed.calls[0][1]
    frozen = observed.plain[0](x)
    value = {
        "ok_evaluations_compared": checked,
        "differing": differing,
        "first_trial": {
            "S3.T": float(x[observed.free[0].index("S3.T")]),
            "frozen_regime": dict(observed.result.attempts[0].signature)["U-HEAT"],
            "reported": signature_text(first.signature or ()),
            "unscreened_reports": signature_text(frozen.signature or ()),
            "values_bit_identical": np.asarray(frozen.values).tobytes()
            == np.asarray(first.values).tobytes(),
        },
    }
    expected = {
        "ok_evaluations_compared": "every one (more than 20)",
        "differing": [],
        "first_trial": {
            "frozen_regime": "LIQUID",
            "reported": "U-HEAT:VAPOR,U-FLASH:TWO_PHASE",
            "unscreened_reports": "",
            "values_bit_identical": True,
        },
    }
    ok = (
        checked > 20
        and not differing
        and value["first_trial"]["frozen_regime"] == "LIQUID"
        and value["first_trial"]["reported"] == "U-HEAT:VAPOR,U-FLASH:TWO_PHASE"
        and value["first_trial"]["unscreened_reports"] == ""
        and value["first_trial"]["values_bit_identical"]
    )
    return ok, value, expected


def _screened_trials(observed: Observed, k: int) -> int:
    """Trials of attempt k whose evaluation reached the screen (a domain refusal returns first)."""
    return sum(1 for _, evaluation in observed.calls[k][1:] if evaluation.status == "ok") + sum(
        1
        for _, evaluation in observed.calls[k][1:]
        if evaluation.status != "ok" and "kernel refused" in (evaluation.message or "")
    )


def _a05(runs: Runs, ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    epsilon = POLICY.admissibility_epsilon
    value: dict[str, Any] = {"admissibility_epsilon": epsilon}
    ok = epsilon == float(ref["constants"]["admissibility_epsilon"])
    for name in ("PHS-01", "PHS-02", "PHS-03"):
        observed = runs.region(PHS[name])
        registered = ref["policy_simulation"]["cases"][PHS[name]]["attempts"][0]
        trials = registered["trials"]
        registered_screened = len(trials) - registered["invalid_trials"]
        registered_flagged = sum(
            1
            for trial in trials
            if trial.get("screen_value") is not None
            and number(trial["screen_value"]) > 1.0 + epsilon
        )
        in_screen = [e for e in observed.admissible if e["attempt"] == 0 and e["in_screen"]]
        row = {
            "screened": len(in_screen),
            "flagged": sum(1 for entry in in_screen if not entry["ok"]),
            "kernel_flashes": observed.flashes.get(0, 0),
            "screened_units": sorted({entry["unit"] for entry in in_screen}),
            "registered_screened": registered_screened,
            "registered_flagged": registered_flagged,
        }
        value[name] = row
        ok = ok and (
            row["screened"] == registered_screened
            and row["flagged"] == row["kernel_flashes"] == registered_flagged
            and row["screened_units"] == ["U-HEAT"]
        )

    # Across every region solve measured here: one ε, no TWO_PHASE unit screened, the closure's
    # calls through the same callable, and the opening never screened.
    epsilons: set[float] = set()
    screened_two_phase: list[str] = []
    openings_screened: list[str] = []
    closure_calls = 0
    for observed in runs.observed():
        epsilons |= {entry["epsilon"] for entry in observed.admissible}
        screened_two_phase += [
            f"{observed.label} attempt {entry['attempt']}"
            for entry in observed.admissible
            if entry["in_screen"] and entry["regime"] == "TWO_PHASE"
        ]
        for k, attempt in enumerate(observed.result.attempts):
            if attempt.solver_outcome == "CONVERGED":
                closure_calls += sum(
                    1
                    for entry in observed.admissible
                    if entry["attempt"] == k and not entry["in_screen"]
                )
            if all(regime == "TWO_PHASE" for _, regime in attempt.signature):
                continue
            invocations = sum(1 for entry in observed.screened if entry["attempt"] == k)
            if invocations != _screened_trials(observed, k):
                openings_screened.append(
                    f"{observed.label} attempt {k}: {invocations} screen calls, "
                    f"{_screened_trials(observed, k)} screened trials"
                )
    value["every_region_solve"] = {
        "epsilons_used": sorted(epsilons),
        "two_phase_units_screened": screened_two_phase,
        "closure_calls_through_the_same_callable": closure_calls,
        "attempts_whose_opening_was_screened": openings_screened,
    }
    ok = ok and (
        epsilons == {epsilon}
        and not screened_two_phase
        and closure_calls > 0
        and not openings_screened
    )

    # PHS-04's LIQUID opening: the check refuses it, the attempt converges.
    observed = runs.region(PHS["PHS-04"])
    registered = ref["policy_simulation"]["cases"][PHS["PHS-04"]]["attempts"][1]
    opening = dict(observed.result.attempts[0].end_state)
    heater = _heater()
    region_module._pin(opening, heater, "LIQUID")
    context = EvaluationContext(
        model_version="t03", constants_sha256="0" * 64, phase_signature=None
    )
    provider = a02_fixtures.structure(
        a02_fixtures.revision(PHS["PHS-04"])
    ).binding.flowsheet.provider
    admissible, screen_value = region_module._admissible(
        provider, context, heater, "LIQUID", opening, epsilon
    )
    value["PHS-04 opening"] = {
        "admissible": admissible,
        "screen_value": screen_value,
        "relative_off": off(screen_value, registered["opening_screen_value"]),
        "attempt_2_outcome": observed.result.attempts[1].solver_outcome,
    }
    ok = ok and (
        not admissible
        and close(screen_value, registered["opening_screen_value"])
        and observed.result.attempts[1].solver_outcome == "CONVERGED"
    )
    expected = {
        "admissibility_epsilon": number(ref["constants"]["admissibility_epsilon"]),
        "PHS-01": {"screened": 15, "flagged": 13, "kernel_flashes": 13},
        "PHS-02": {"screened": 14, "flagged": 12, "kernel_flashes": 12},
        "PHS-03": {"screened": 8, "flagged": 6, "kernel_flashes": 6},
        "screened_units": ["U-HEAT"],
        "every_region_solve": {
            "epsilons_used": [epsilon],
            "two_phase_units_screened": [],
            "closure_calls_through_the_same_callable": "at least 1",
            "attempts_whose_opening_was_screened": [],
        },
        "PHS-04 opening": {
            "admissible": False,
            "screen_value": number(registered["opening_screen_value"]),
            "attempt_2_outcome": "CONVERGED",
        },
    }
    return ok, value, expected


# ------------------------------------------------------------------------------ A06–A13


def _a06(runs: Runs, ref: Mapping[str, Any], t02: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    registered = ref["policy_simulation"]["cases"][PHS["PHS-01"]]["attempts"][0]
    observed = runs.region(PHS["PHS-01"])
    found = _compare_attempt(observed, 0, _attempt(observed, 0), registered)
    accepted = [
        trial["S3_T_K"]
        for trial in _attempt(observed, 0)["trials"]
        if trial["verdict"] == "accepted"
    ]
    value = {"attempt_1": found, "accepted_S3_T_K": accepted}
    expected = {
        "attempt_1": _registered_attempt(registered),
        "accepted_S3_T_K": [
            number(t["S3_T_K"]) for t in registered["trials"] if t["verdict"] == "accepted"
        ],
    }
    ok = not found["mismatches"] and len(accepted) == 2
    return ok, value, expected


def _a07(runs: Runs, ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    registered = ref["policy_simulation"]["cases"][PHS["PHS-01"]]["attempts"][1]
    observed = runs.region(PHS["PHS-01"])
    found = _attempt(observed, 1)
    first = _attempt(observed, 0)["trials"]
    candidate_one = next((t for t in first if (t["iteration"], t["halving"]) == (1, 0)), None)
    value = {
        "signature": found["signature"],
        "opening_source": found["opening_source"],
        "opening_trial": found["opening_trial"],
        "attempt_opened_alpha": found["opening_alpha"],
        "S3_T_K": found["opening_S3_T_K"],
        "S3_T_relative_off": off(found["opening_S3_T_K"], registered["opening_S3_T_K"]),
        "beta": found["opening_beta"],
        "beta_relative_off": off(found["opening_beta"], registered["opening_beta"]),
        "message": found["opening_message"],
        "alpha_1_candidate": candidate_one,
    }
    expected = {
        "signature": registered["signature"],
        "opening_source": registered["opening_source"],
        "opening_trial": registered["opening_trial"],
        "attempt_opened_alpha": number(registered["opening_alpha"]),
        "S3_T_K": number(registered["opening_S3_T_K"]),
        "beta": number(registered["opening_beta"]),
        "message": "phase_update(phase_wall(patience, U-HEAT:LIQUID->TWO_PHASE))",
        "alpha_1_candidate": "iteration 1, halving 0, phase_update_required, VAPOR (not chosen)",
    }
    ok = (
        found["signature"] == registered["signature"]
        and found["opening_source"] == registered["opening_source"]
        and found["opening_trial"] == registered["opening_trial"]
        and close(found["opening_alpha"], registered["opening_alpha"])
        and close(found["opening_S3_T_K"], registered["opening_S3_T_K"])
        and close(found["opening_beta"], registered["opening_beta"])
        and found["opening_message"] == expected["message"]
        and candidate_one is not None
        and candidate_one["verdict"] == "phase_update_required"
        and candidate_one["reported_heater_regime"] == "VAPOR"
        and found["opening_trial"] != {"iteration": 1, "halving": 0}
    )
    return ok, value, expected


def _a08(runs: Runs, ref: Mapping[str, Any], t02: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    ok, value, expected, observed = _phase_case(runs, ref, t02, "PHS-01", "T_heater=355K")
    second = value["per_attempt"][1] if len(value["per_attempt"]) > 1 else {}
    # §6.3, recorded: the direction at the landed variable after the landing points inward.
    trials = _attempt(observed, 1)["trials"]
    accepted = [i for i, t in enumerate(trials) if t["verdict"] == "accepted"]
    after = None
    if len(accepted) > 1:
        x = observed.calls[1][1 + accepted[1]][0]
        after = float(x[observed.free[1].index("S3.vap.C")])
    value["S3.vap.C after the next accepted step (recorded)"] = after
    value["summary"] = {
        "attempt_2_core": second.get("core"),
        "landing": second.get("landings"),
    }
    return ok, value, expected


def _a09_a10(
    runs: Runs, ref: Mapping[str, Any], t02: Mapping[str, Any], name: str
) -> tuple[bool, Any, Any]:
    ok, value, expected, observed = _phase_case(runs, ref, t02, name, "T_heater=360K")
    if name == "PHS-03":
        alphas = [float(e.alpha) for e in _line_search(observed, 1) if e.kind == "step_accepted"]
        value["attempt_2_accepted_alphas"] = alphas
        expected["attempt_2_accepted_alphas"] = "every one 1.0 (no landing)"
        ok = ok and bool(alphas) and all(alpha == 1.0 for alpha in alphas)
    return ok, value, expected


def _a11(runs: Runs, ref: Mapping[str, Any], t02: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    ok, value, expected, observed = _phase_case(runs, ref, t02, "PHS-04", "T_heater=340K")
    registered = ref["policy_simulation"]["cases"][PHS["PHS-04"]]
    result = observed.result
    first, second = result.attempts[:2]
    pinned = dict(first.end_state)
    region_module._pin(pinned, _heater(), "LIQUID")
    free = observed.free[1]
    x0 = observed.calls[1][0][0]
    target = np.array([pinned[name] for name in free], dtype=np.float64)
    heater_vapour = ("S3.vap.A", "S3.vap.B", "S3.vap.C", "S3.V")
    closure = [
        entry
        for entry in observed.admissible
        if entry["attempt"] == 1 and not entry["in_screen"] and entry["unit"] == "U-HEAT"
    ]
    registered_value = registered["attempts"][1]["trials"][0]["screen_value"]
    detail = {
        "opening_equals_pinned_end_state_bitwise": x0.tobytes() == target.tobytes(),
        "opening_vapour_pinned_positive_zero": {
            name: positive_zero(second.end_state[name]) and name not in free
            for name in heater_vapour
        },
        "opening_liquid_equals_feed": all(
            x0[free.index(f"S3.liq.{c}")] == x0[free.index(f"S3.n.{c}")] for c in COMPONENTS
        ),
        "final_S3.V": result.state["S3.V"],
        "final_S3.V_is_positive_zero": positive_zero(result.state["S3.V"]),
        "closure_sum_xK": closure[-1]["value"] if closure else None,
        "closure_sum_xK_relative_off": off(closure[-1]["value"], registered_value)
        if closure
        else None,
    }
    value["pinned_restart"] = detail
    expected["pinned_restart"] = {
        "opening_equals_pinned_end_state_bitwise": True,
        "opening_vapour_pinned_positive_zero": dict.fromkeys(heater_vapour, True),
        "opening_liquid_equals_feed": True,
        "final_S3.V": 0.0,
        "closure_sum_xK": number(registered_value),
    }
    ok = (
        ok
        and detail["opening_equals_pinned_end_state_bitwise"]
        and all(detail["opening_vapour_pinned_positive_zero"].values())
        and detail["opening_liquid_equals_feed"]
        and result.state["S3.V"] == 0.0
        and bool(closure)
        and close(closure[-1]["value"], registered_value)
    )
    return ok, value, expected


def _a12(runs: Runs, ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    from openflowsheet.verify.failure import ACTIONS, OUTCOME_ACTIONS, TAXONOMY

    ok, value, expected, observed = _phase_case(runs, ref, {}, "PHS-05", None)
    result = observed.result
    registered = ref["policy_simulation"]["cases"][PHS["PHS-05"]]
    message = (
        "active_set_cycling(U-HEAT:TWO_PHASE,U-FLASH:TWO_PHASE; "
        "phase_wall(stall, U-HEAT:LIQUID->TWO_PHASE))"
    )
    taxonomy = TAXONOMY.get(result.outcome)
    entry = next(
        item
        for item in yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["cases"]
        if item["case_id"] == PHS["PHS-05"]
    )
    value["solve"] = {
        "message": result.message,
        "refused_signature_and_cause_registered": registered["refused"],
        "root_fingerprint": result.root_fingerprint,
        "checkpoint_label": result.checkpoint.label if result.checkpoint else None,
        "failure_class": taxonomy,
        "failure_action": OUTCOME_ACTIONS.get(result.outcome, ACTIONS[taxonomy])
        if taxonomy
        else None,
        "INFEASIBLE": "INFEASIBLE" in f"{result.outcome} {result.message}".upper(),
        "registry": {
            "code": entry["expected"].get("code"),
            "in_success_denominator": entry["expected"].get("in_success_denominator"),
            "handed_to": entry["expected"].get("handed_to"),
        },
    }
    expected["solve"] = {
        "message": message,
        "root_fingerprint": None,
        "checkpoint_label": "partial",
        "failure_class": "homotopy/PTC/active-set stalls",
        "failure_action": "supply_initial_guess",
        "INFEASIBLE": False,
        "registry": {
            "code": "ACTIVE_SET_CYCLING",
            "in_success_denominator": False,
            "handed_to": "T04",
        },
    }
    solve = value["solve"]
    ok = (
        ok
        and result.message == message == f"active_set_cycling({registered['refused']})"
        and solve["root_fingerprint"] is None
        and solve["checkpoint_label"] == "partial"
        and solve["failure_class"] == expected["solve"]["failure_class"]
        and solve["failure_action"] == "supply_initial_guess"
        and not solve["INFEASIBLE"]
        and solve["registry"] == expected["solve"]["registry"]
    )
    return ok, value, expected


def _a13(runs: Runs, ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    import t02_evidence_manifest as t02_manifest

    observed = runs.nominal_eo()
    result = observed.result
    decision = next(entry for entry in observed.decisions if entry["attempt"] == 0)
    value: dict[str, Any] = {"outcome": result.outcome, "attempts": len(result.attempts)}
    ok = result.outcome == "CONVERGED" and len(result.attempts) == 2
    if len(result.attempts) >= 2:
        first, second = result.attempts[:2]
        pinned = dict(first.end_state)
        region_module._pin(pinned, _heater(), "LIQUID")
        free = observed.free[1]
        x0 = observed.calls[1][0][0]
        opening_equal = (
            x0.tobytes() == np.array([pinned[n] for n in free], dtype=np.float64).tobytes()
        )
        value["A21"] = {
            "attempt_1_core": decision["core_outcome"],
            "attempt_1_core_iterations": decision["iterations"],
            "attempt_1_blocked_by": list(decision["blocked_by"]),
            "attempt_1_cause": result.branch_provenance[0]["cause"],
            "attempt_2_opening_source": result.branch_provenance[1]["opening_source"],
            "attempt_2_opening_equals_pinned_iterate_bitwise": opening_equal,
            "attempt_2_signature": signature_text(second.signature),
            "attempt_2_outcome": second.solver_outcome,
            "attempt_2_iterations": second.iterations,
        }
        ok = ok and (
            decision["core_outcome"] == "BOUND_BLOCKED"
            and decision["iterations"] == 1
            and "S3.vap.B" in decision["blocked_by"]
            and result.branch_provenance[0]["cause"] == "phase_disappeared(U-HEAT, vapor, S3.vap.B)"
            and result.branch_provenance[1]["opening_source"] == "pinned_iterate"
            and opening_equal
            and signature_text(second.signature) == "U-HEAT:LIQUID,U-FLASH:TWO_PHASE"
            and second.solver_outcome == "CONVERGED"
            and second.iterations <= 5
        )

    t02_checks = {}
    for name, measure in (
        ("A21", t02_manifest._a21),
        ("A22", t02_manifest._a22),
        ("A23", t02_manifest._a23),
        ("A24", t02_manifest._a24),
    ):
        try:
            passed, _, _ = measure()
            t02_checks[name] = "pass" if passed else "fail"
        except Exception as error:  # noqa: BLE001 - recorded
            t02_checks[name] = f"error: {type(error).__name__}: {error}"
    value["t02_manifest_measurements"] = t02_checks
    ok = ok and all(result_ == "pass" for result_ in t02_checks.values())

    successes: dict[str, Any] = {}
    registered = ref["t02_successes_under_the_contract"]
    for case_id, key in T02_SUCCESSES.items():
        case = runs.region(case_id)
        alphas = [float(e.alpha) for e in case.trace.events if e.kind == "step_accepted"]
        successes[case_id] = {
            "outcome": case.result.outcome,
            "attempts": len(case.result.attempts),
            "core_iterations": case.result.attempts[0].iterations,
            "every_accepted_alpha_1": bool(alphas) and all(alpha == 1.0 for alpha in alphas),
        }
        ok = ok and successes[case_id] == {
            "outcome": registered[key]["outcome"],
            "attempts": registered[key]["attempts"],
            "core_iterations": registered[key]["core_iterations"],
            "every_accepted_alpha_1": registered[key]["landings"] == 0,
        }
    value["t02_successes"] = successes
    expected = {
        "outcome": "CONVERGED",
        "attempts": 2,
        "A21": {
            "attempt_1_core": "BOUND_BLOCKED",
            "attempt_1_core_iterations": 1,
            "attempt_1_blocked_by": "contains S3.vap.B",
            "attempt_1_cause": "phase_disappeared(U-HEAT, vapor, S3.vap.B)",
            "attempt_2_opening_source": "pinned_iterate",
            "attempt_2_opening_equals_pinned_iterate_bitwise": True,
            "attempt_2_signature": "U-HEAT:LIQUID,U-FLASH:TWO_PHASE",
            "attempt_2_outcome": "CONVERGED",
            "attempt_2_iterations": "at most 5",
        },
        "t02_manifest_measurements": dict.fromkeys(("A21", "A22", "A23", "A24"), "pass"),
        "t02_successes": {
            case_id: {
                "outcome": registered[key]["outcome"],
                "attempts": registered[key]["attempts"],
                "core_iterations": registered[key]["core_iterations"],
                "every_accepted_alpha_1": registered[key]["landings"] == 0,
            }
            for case_id, key in T02_SUCCESSES.items()
        },
    }
    return ok, value, expected


# ------------------------------------------------------------------------------ A14–A18


def _a14(runs: Runs, ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    value: dict[str, Any] = {}
    expected: dict[str, Any] = {}
    ok = True
    for name in ("PHS-SYN-1", "PHS-SYN-2"):
        registered = ref["policy_simulation"]["synthetic_tear_seeds"][name]
        seed = runs.synthetic(name)
        points: list[float] = []
        for attempt in registered["attempts"]:
            points.append(number(attempt["opening_x"]))
            for iteration in attempt["iterations"]:
                points.extend(number(trial["x"]) for trial in iteration)
        signatures = [dict(item["signature"])["U-SYN"] for item in seed.result.branch_provenance]
        value[name] = {
            "outcome": seed.result.outcome,
            "x": float(seed.result.x[0]),
            "attempts": len(seed.result.branch_provenance),
            "signatures": signatures,
            "evaluated_points": len(seed.evaluated),
            "points_equal_exactly": seed.evaluated == points,
        }
        expected[name] = {
            "outcome": registered["outcome"],
            "x": number(registered["x"]),
            "attempts": len(registered["attempts"]),
            "signatures": [attempt["signature"] for attempt in registered["attempts"]],
            "evaluated_points": len(points),
            "points_equal_exactly": True,
        }
        ok = ok and value[name] == expected[name]

    tear = runs.off_b()
    item = tear.result.branch_provenance[1]
    trial = item["opening_trial"]
    rejected = [
        e
        for e in tear.trace.events
        if e.kind == "trial"
        and e.attempt == 0
        and e.rejection_reason == "phase_update_required"
        and e.iteration == trial["iteration"]
    ]
    last_wall = max(
        e.iteration
        for e in tear.trace.events
        if e.kind == "trial" and e.attempt == 0 and e.rejection_reason == "phase_update_required"
    )
    line = [
        e
        for e in tear.trace.events
        if e.attempt == 0
        and e.iteration == trial["iteration"]
        and e.kind in ("trial", "step_accepted")
    ]
    chosen = line[trial["halving"]]
    value["OFF-B"] = {
        "outcome": tear.result.outcome,
        "attempts": tear.result.attempts,
        "opening_source": item["opening_source"],
        "opening_trial": trial,
        "last_iteration_with_a_phase_rejection": last_wall,
        "chosen_alpha": chosen.alpha,
        "largest_rejected_alpha_there": max(e.alpha for e in rejected) if rejected else None,
        "new_signature": signature_text(tear.result.signatures[1]),
    }
    expected["OFF-B"] = {
        "outcome": "CONVERGED",
        "attempts": 2,
        "opening_source": "phase_rejected_trial",
        "opening_trial": "in the last iteration with a phase rejection",
        "chosen_alpha": "the largest phase-rejected alpha of that line search",
        "new_signature": "U-FLASH:TWO_PHASE",
    }
    ok = ok and (
        tear.result.outcome == "CONVERGED"
        and tear.result.attempts == 2
        and item["opening_source"] == "phase_rejected_trial"
        and trial["iteration"] == last_wall
        and chosen.kind == "trial"
        and chosen.rejection_reason == "phase_update_required"
        and bool(rejected)
        and chosen.alpha == max(e.alpha for e in rejected)
        and value["OFF-B"]["new_signature"] == "U-FLASH:TWO_PHASE"
    )

    completed = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "tests/test_k03_attempts.py",
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    rerun = _pytest_counts(completed.stdout)
    value["k03_attempt_tests"] = {"exit_code": completed.returncode, "counts": rerun}
    expected["k03_attempt_tests"] = {"exit_code": 0, "counts": "passed only"}
    ok = ok and (
        completed.returncode == 0 and rerun.get("passed", 0) > 0 and set(rerun) == {"passed"}
    )
    return ok, value, expected


def _a15(runs: Runs, ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    shapes = ref["closed_form"]["region_shapes_rows_by_columns"]
    value: dict[str, Any] = {}
    ok = True
    region_runs = [runs.region(case_id) for case_id in (*PHS.values(), *T02_SUCCESSES)]
    region_runs.append(runs.nominal_eo())
    for observed in region_runs:
        rows_out: list[dict[str, Any]] = []
        for k, context in enumerate(observed.result.contexts):
            pattern = context.jacobian_pattern
            free, rows = observed.free[k], observed.rows[k]
            allowed = {
                (rows.index(r), free.index(c))
                for r, c in observed.structure
                if r in rows and c in free
            }
            outside = sum(len(entries - allowed) for _, entries in observed.jacobians[k])
            wrong_shape = sum(
                1
                for shape, _ in observed.jacobians[k]
                if pattern is None or shape != (pattern["rows"], pattern["columns"])
            )
            key = signature_text(context.signature)
            rows_out.append(
                {
                    "signature": key,
                    "shape": [pattern["rows"], pattern["columns"]] if pattern else None,
                    "registered_shape": shapes.get(key),
                    # Review S5: not recomputed with the function that produced it — the
                    # declared entries restricted by id, counted here.
                    "nnz": pattern["nnz"] if pattern else None,
                    "declared_entries_restricted_by_id": len(allowed),
                    "sha256": pattern["sha256"] if pattern else None,
                    "jacobians": len(observed.jacobians[k]),
                    "wrong_shape": wrong_shape,
                    "entries_outside_pattern": outside,
                }
            )
        # One pattern per signature: a rebuild under another signature is another pattern.
        by_signature = {row["signature"]: row["sha256"] for row in rows_out}
        digests_ok = len(set(by_signature.values())) == len(by_signature) and all(
            row["sha256"] == by_signature[row["signature"]] for row in rows_out
        )
        value[observed.label] = {"attempts": rows_out, "one_digest_per_signature": digests_ok}
        ok = ok and digests_ok
        ok = ok and all(
            row["shape"] is not None
            and row["shape"] == row["registered_shape"]
            and row["nnz"] == row["declared_entries_restricted_by_id"]
            and row["nnz"] < row["shape"][0] * row["shape"][1]
            and row["jacobians"] > 0
            and row["wrong_shape"] == 0
            and row["entries_outside_pattern"] == 0
            for row in rows_out
        )

    # PHS-01: the 38 × 38 set is the 42 × 42 set restricted to its ids.
    observed = runs.region(PHS["PHS-01"])

    def id_entries(k: int) -> set[tuple[str, str]]:
        return {
            (r, c) for r, c in observed.structure if r in observed.rows[k] and c in observed.free[k]
        }

    single, double = id_entries(0), id_entries(1)
    restricted = {(r, c) for r, c in double if r in observed.rows[0] and c in observed.free[0]}
    value["PHS-01 restriction"] = {
        "38x38_entries": len(single),
        "42x42_entries": len(double),
        "equal_to_restriction": single == restricted,
        "pinned_columns": sorted(set(observed.free[1]) - set(observed.free[0])),
        "dropped_rows": sorted(set(observed.rows[1]) - set(observed.rows[0])),
    }
    ok = ok and single == restricted and len(value["PHS-01 restriction"]["pinned_columns"]) == 4

    tear = runs.off_b()
    patterns = [context.jacobian_pattern for context in tear.result.contexts]
    value["OFF-B"] = {
        "patterns": len(patterns),
        "same_across_attempts": len(patterns) == 2 and patterns[0] == patterns[1],
        "non_null": all(pattern is not None for pattern in patterns),
        "cache_sizes_at_attempt_opened": tear.cache_sizes,
    }
    ok = ok and (
        value["OFF-B"]["same_across_attempts"]
        and value["OFF-B"]["non_null"]
        and bool(tear.cache_sizes)
        and tear.cache_sizes == sorted(tear.cache_sizes)
        and tear.cache_sizes[-1] > 0
    )
    bare = [
        context.jacobian_pattern
        for name in ("PHS-SYN-1", "PHS-SYN-2")
        for context in runs.synthetic(name).result.contexts
    ]
    value["bare_controller_patterns_null"] = all(pattern is None for pattern in bare)
    ok = ok and value["bare_controller_patterns_null"]
    expected = {
        "every region attempt": {
            "shape": "ref.closed_form.region_shapes_rows_by_columns[signature]",
            "nnz": "declared_entries_restricted_by_id, fewer than rows × columns",
            "wrong_shape": 0,
            "entries_outside_pattern": 0,
        },
        "every region run": {"one_digest_per_signature": True},
        "PHS-01 restriction": {"equal_to_restriction": True, "pinned_columns": 4},
        "OFF-B": {
            "same_across_attempts": True,
            "non_null": True,
            "cache_sizes_at_attempt_opened": "non-decreasing, last > 0",
        },
        "bare_controller_patterns_null": True,
    }
    return ok, value, expected


#: A16's constructed refusals: the check, the variable or field it names (review S4's R0 form),
#: and the offending value the attempt records instead (`None`: no number is involved).
REFUSALS: dict[str, tuple[str, float | None]] = {
    "scale_segment": ("scale_segment", None),
    "identity": ("model_version", None),
    "bounds": ("S3.liq.B", -1e-9),
    "active_set": ("S3.vap.A", 1e-3),
}


def _refusal(observed: Observed, check_name: str) -> dict[str, Any]:
    from openflowsheet.verify.failure import ACTIONS, OUTCOME_ACTIONS, TAXONOMY

    result = observed.result
    events = observed.trace.events
    opened = [e for e in events if e.kind == "attempt_opened"]
    closed_at = max(e.sequence for e in events if e.kind == "attempt_closed")
    after = [e.kind for e in events if e.sequence > closed_at]
    final = observed.decisions[-1] if observed.decisions else {}
    taxonomy = TAXONOMY.get(result.outcome)
    return {
        "outcome": result.outcome,
        "message": result.message,
        "message_carries_a_float": bool(FLOAT.search(result.message)),
        "observations": dict(result.attempts[-1].observations) if result.attempts else None,
        "attempt_opened": len(opened),
        "attempts": len(result.attempts),
        "events_after_the_last_closure": after,
        "residual_calls_after_the_decision": sum(len(c) for c in observed.calls)
        - final.get("residual_calls", -1),
        "jacobian_calls_after_the_decision": sum(len(j) for j in observed.jacobians)
        - final.get("jacobian_calls", -1),
        "checkpoint_label": result.checkpoint.label if result.checkpoint else None,
        "root_fingerprint": result.root_fingerprint,
        "failure_class": taxonomy,
        "failure_action": OUTCOME_ACTIONS.get(result.outcome, ACTIONS[taxonomy])
        if taxonomy
        else None,
        "class_action_overridden": bool(taxonomy)
        and ACTIONS[taxonomy] != OUTCOME_ACTIONS.get(result.outcome),
    }


def _a16(runs: Runs) -> tuple[bool, Any, Any]:
    # Every registered opening: the six checks as observed, then three recomputed.
    observed_runs = [runs.region(case_id) for case_id in (*PHS.values(), *T02_SUCCESSES)]
    observed_runs.append(runs.nominal_eo())
    outcomes = [outcome for observed in observed_runs for outcome in observed.openings]
    tear = runs.off_b()
    outcomes += tear.openings
    recomputed: list[str] = []
    openings = 0
    for observed in observed_runs:
        for k in range(1, len(observed.result.attempts)):
            openings += 1
            free = observed.free[k]
            x0 = observed.calls[k][0][0]
            if not np.all(np.isfinite(x0)):
                recomputed.append(f"{observed.label} {k}: coverage")
            regimes = dict(observed.result.attempts[k].signature)
            # The opening as the compiled problem received it (attempt k's first call, the
            # evaluation of its opening vector) — not the end state the region writes later.
            order = {name: index for index, name in enumerate(observed.spec.variable_ids)}
            opened = next(x for at, _, x in observed.compiled_calls if at == k)
            for split in syn001_lifted_splits(COMPONENTS):
                if split.unit in regimes:
                    for name in split.pinned(regimes[split.unit]):
                        if not positive_zero(float(opened[order[name]])):
                            recomputed.append(f"{observed.label} {k}: active_set {name}")
            kinds = observed.spec.variable_kinds
            for index, name in enumerate(free):
                if kinds.get(name) == "molar_flow" and x0[index] < 0.0:
                    recomputed.append(f"{observed.label} {k}: bounds {name}")
    value: dict[str, Any] = {
        "opening_checks_observed": {
            "region": len(outcomes) - len(tear.openings),
            "tear (OFF-B)": len(tear.openings),
        },
        "refused": [outcome.detail for outcome in outcomes if outcome is not None],
        "region_restart_openings_recomputed": openings,
        "recomputed_violations": recomputed,
    }
    ok = (
        len(outcomes) > len(tear.openings) > 0
        and not value["refused"]
        and openings > 0
        and not recomputed
    )

    refusals = {name: _refusal(runs.refused(name), name) for name in REFUSALS}
    value["constructed_refusals"] = refusals
    for name, row in refusals.items():
        subject, number_ = REFUSALS[name]
        ok = ok and (
            row["outcome"] == "CHECKPOINT_INCOMPATIBLE"
            and row["message"] == f"checkpoint_incompatible({name}, {subject})"
            and not row["message_carries_a_float"]
            and row["observations"] == ({} if number_ is None else {f"{name}:{subject}": number_})
            and row["attempt_opened"] == row["attempts"] == 1
            and not {"trial", "step_accepted", "jacobian"}
            & set(row["events_after_the_last_closure"])
            and row["residual_calls_after_the_decision"] == 0
            and row["jacobian_calls_after_the_decision"] == 0
            and row["checkpoint_label"] == "partial"
            and row["root_fingerprint"] is None
            and row["failure_class"] == "homotopy/PTC/active-set stalls"
            and row["failure_action"] == "report_defect"
            and row["class_action_overridden"]
        )
    expected = {
        "opening_checks_observed": "at least one region opening and OFF-B's tear openings",
        "refused": [],
        "recomputed_violations": [],
        "constructed_refusals": {
            name: {
                "message": f"checkpoint_incompatible({name}, {subject})",
                "observations": {} if number_ is None else {f"{name}:{subject}": number_},
            }
            for name, (subject, number_) in REFUSALS.items()
        },
        "each constructed refusal": {
            "outcome": "CHECKPOINT_INCOMPATIBLE",
            "message_carries_a_float": False,
            "attempt_opened": 1,
            "attempts": 1,
            "events_after_the_last_closure": "no trial, step_accepted or jacobian",
            "residual_calls_after_the_decision": 0,
            "jacobian_calls_after_the_decision": 0,
            "checkpoint_label": "partial",
            "root_fingerprint": None,
            "failure_class": "homotopy/PTC/active-set stalls",
            "failure_action": "report_defect",
            "class_action_overridden": True,
        },
    }
    return ok, value, expected


def _a17(runs: Runs) -> tuple[bool, Any, Any]:
    problems: list[str] = []
    openings = 0
    region_runs = [runs.region(case_id) for case_id in (*PHS.values(), *T02_SUCCESSES)]
    region_runs.append(runs.nominal_eo())
    for observed in region_runs:
        events = observed.trace.events
        for k, item in enumerate(observed.result.branch_provenance):
            openings += 1
            (opened,) = [e for e in events if e.kind == "attempt_opened" and e.attempt == k]
            digest = state_sha256(observed.calls[k][0][0], observed.free[k])
            where = f"{observed.label} attempt {k}"
            if not opened.state_sha256 or opened.state_sha256 != digest:
                problems.append(f"{where}: state_sha256")
            if item["opening_state_sha256"] != opened.state_sha256:
                problems.append(f"{where}: provenance hash")
            if not OPENED.match(opened.message) or (opened.message == "initial") != (k == 0):
                problems.append(f"{where}: message {opened.message!r}")
            if item["opening_source"] == "phase_rejected_trial":
                trial = item["opening_trial"]
                line = [
                    e for e in _line_search(observed, k - 1) if e.iteration == trial["iteration"]
                ]
                if opened.alpha is None or opened.alpha != line[trial["halving"]].alpha:
                    problems.append(f"{where}: alpha")
            elif opened.alpha is not None:
                problems.append(f"{where}: alpha set for {item['opening_source']}")
            if k > 0:
                source = observed.result.contexts[k].opened_from
                if source is None or (
                    source.checkpoint_id,
                    source.attempt_index,
                    source.label,
                    source.signature,
                ) != (
                    f"region-attempt-{k - 1}",
                    k - 1,
                    "partial",
                    observed.result.attempts[k - 1].signature,
                ):
                    problems.append(f"{where}: opened_from {source}")

    tear = runs.off_b()
    events = tear.trace.events
    opened_events = [e for e in events if e.kind == "attempt_opened"]
    first_hash = state_sha256(np.array(tear.x0, dtype=np.float64), tear.variable_ids)
    item = tear.result.branch_provenance[1]
    line = [
        e
        for e in events
        if e.attempt == 0
        and e.iteration == item["opening_trial"]["iteration"]
        and e.kind in ("trial", "step_accepted")
    ]
    chosen = line[item["opening_trial"]["halving"]]
    source = tear.result.contexts[1].opened_from
    tear_row = {
        "attempt_0_hash_is_the_start": opened_events[0].state_sha256 == first_hash,
        "attempt_1_hash_is_the_chosen_trial": opened_events[1].state_sha256 == chosen.state_sha256,
        "provenance_hashes": [i["opening_state_sha256"] for i in tear.result.branch_provenance]
        == [e.state_sha256 for e in opened_events],
        "alpha": [e.alpha for e in opened_events],
        "chosen_trial_alpha": chosen.alpha,
        "messages": [e.message for e in opened_events],
        "opened_from": (source.checkpoint_id, source.label) if source else None,
    }
    openings += len(opened_events)
    if not (
        tear_row["attempt_0_hash_is_the_start"]
        and tear_row["attempt_1_hash_is_the_chosen_trial"]
        and tear_row["provenance_hashes"]
        and opened_events[0].alpha is None
        and opened_events[1].alpha == chosen.alpha
        and all(OPENED.match(message) for message in tear_row["messages"])
        and tear_row["messages"][0] == "initial"
        and tear_row["opened_from"] == ("attempt-0", "partial")
    ):
        problems.append(f"OFF-B: {tear_row}")

    # Terminal decisions of §4.10's two kinds, wherever a solve here produced one.
    terminal = [runs.region(PHS["PHS-05"]).result.message]
    terminal += [
        e.message
        for e in runs.k03_cycling().trace.events
        if e.kind == "solve_closed" and e.outcome == "ACTIVE_SET_CYCLING"
    ]
    terminal += [runs.refused(name).result.message for name in REFUSALS]
    unparsed = [message for message in terminal if not TERMINAL.match(message)]
    value = {
        "openings_checked": openings,
        "problems": problems,
        "OFF-B": tear_row,
        "terminal_messages": terminal,
        "terminal_unparsed": unparsed,
    }
    expected = {
        "problems": [],
        "OFF-B": {
            "attempt_0_hash_is_the_start": True,
            "attempt_1_hash_is_the_chosen_trial": True,
            "provenance_hashes": True,
            "alpha": [None, "the chosen trial's alpha"],
            "opened_from": ["attempt-0", "partial"],
        },
        "terminal_unparsed": [],
    }
    ok = openings > 0 and not problems and len(terminal) == 2 + len(REFUSALS) and not unparsed
    return ok, value, expected


def _a18(runs: Runs) -> tuple[bool, Any, Any]:
    cycling, budget = runs.k03_cycling(), runs.k03_budget()
    capped = _a02_revision(PHS["PHS-01"], replace(POLICY, max_attempts=1))
    phs05 = runs.region(PHS["PHS-05"])

    def last(decisions: Sequence[Mapping[str, Any]]) -> Any:
        return decisions[-1]["outcome"] if decisions else None

    value: dict[str, Any] = {
        "PHS-05": {"outcome": phs05.result.outcome, "decided": last(phs05.decisions)},
        "K03 two-regime seed": {
            "outcome": cycling.result.outcome,
            "decided": last(cycling.decisions),
            "message": cycling.result.message,
        },
        "K03 budget seed": {
            "outcome": budget.result.outcome,
            "decided": last(budget.decisions),
            "attempts": budget.result.attempts,
        },
        "PHS-01 max_attempts=1": {
            "outcome": capped.result.outcome,
            "decided": last(capped.decisions),
            "attempts": len(capped.result.attempts),
            "attempt_1_core": capped.decisions[0]["core_outcome"] if capped.decisions else None,
            "checkpoint_label": capped.result.checkpoint.label
            if capped.result.checkpoint
            else None,
        },
    }
    over: list[str] = []
    counted = 0
    for observed in [*runs.observed(), capped]:
        counted += 1
        if len(observed.result.attempts) > observed.policy.max_attempts:
            over.append(observed.label)
    for seed in (cycling, budget, runs.synthetic("PHS-SYN-1"), runs.synthetic("PHS-SYN-2")):
        counted += 1
        if seed.result.attempts > seed.policy.max_attempts:
            over.append(seed.label)
    tear = runs.off_b()
    counted += 1
    if tear.result.attempts > tear.policy.max_attempts:
        over.append("OFF-B")
    value["solves_counted"] = counted
    value["over_max_attempts"] = over
    expected = {
        "PHS-05": {"outcome": "ACTIVE_SET_CYCLING", "decided": "ACTIVE_SET_CYCLING"},
        "K03 two-regime seed": {"outcome": "ACTIVE_SET_CYCLING", "decided": "ACTIVE_SET_CYCLING"},
        "K03 budget seed": {
            "outcome": "ATTEMPTS_EXHAUSTED",
            "decided": "ATTEMPTS_EXHAUSTED",
            "attempts": 2,
        },
        "PHS-01 max_attempts=1": {
            "outcome": "ATTEMPTS_EXHAUSTED",
            "decided": "ATTEMPTS_EXHAUSTED",
            "attempts": 1,
            "attempt_1_core": "PHASE_UPDATE_REQUIRED",
            "checkpoint_label": "partial",
        },
        "over_max_attempts": [],
    }
    ok = (
        value["PHS-05"] == expected["PHS-05"]
        and {k: value["K03 two-regime seed"][k] for k in ("outcome", "decided")}
        == expected["K03 two-regime seed"]
        and value["K03 budget seed"] == expected["K03 budget seed"]
        and value["PHS-01 max_attempts=1"] == expected["PHS-01 max_attempts=1"]
        and not over
    )
    return ok, value, expected


# ------------------------------------------------------------------------------ A19–A22


def _start_hash(start: str) -> str:
    t02 = yaml.safe_load(T02_REFERENCE.read_text(encoding="utf-8"))
    loop, t_110 = merge_fixtures.rec_05(t02, 0.1)
    point = {"1.1 t*": np.asarray(t_110, dtype=np.float64), "t*": np.array([1.0, 2.0, 3.0])}
    return state_sha256(point[start], loop.problem.variable_ids)


def _a19(runs: Runs, ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    from openflowsheet.orchestrator.roots import DELTA_ROOT, same_root

    roots = ref["multiple_roots"]["REC-05 gamma=0.1"]
    mr_a, mr_b, mr_c = runs.rec_05("MR-A"), runs.rec_05("MR-B"), runs.rec_05("MR-C")

    def scaled(result: Any, point: Sequence[Any]) -> float:
        return max(abs(float(v) - number(p)) / 3.0 for v, p in zip(result.x, point, strict=True))

    starts = {"MR-A": "1.1 t*", "MR-B": "t*", "MR-C": "1.1 t*"}
    items = {
        name: result.branch_provenance[0]
        for name, result in (("MR-A", mr_a), ("MR-B", mr_b), ("MR-C", mr_c))
    }
    fingerprints = (mr_a.root_fingerprint, mr_b.root_fingerprint, mr_c.root_fingerprint)
    value: dict[str, Any] = {
        "delta_root": DELTA_ROOT,
        "MR-A": {
            "outcome": mr_a.outcome,
            "iterations": mr_a.recycle.iterations,
            "scaled_distance_to_S1": scaled(mr_a, roots["S1"]),
        },
        "MR-B": {
            "outcome": mr_b.outcome,
            "iterations": mr_b.recycle.iterations,
            "scaled_distance_to_t_star": scaled(mr_b, roots["t_star"]),
        },
        "MR-C": {
            "loop_outcome": mr_c.recycle.outcome,
            "loop_iterations": mr_c.recycle.iterations,
            "outcome": mr_c.outcome,
            "merge_newton_iterations": mr_c.merged.iterations if mr_c.merged else None,
            "scaled_distance_to_S1": scaled(mr_c, roots["S1"]),
            "provenance": [(i["core"], i["opening_source"]) for i in mr_c.branch_provenance],
        },
        "item_0": {
            name: {
                "initializer_source": item["initializer_source"],
                "opening_state_sha256_is_the_start": item["opening_state_sha256"]
                == _start_hash(starts[name]),
            }
            for name, item in items.items()
        },
        "fingerprints_issued": all(fingerprint is not None for fingerprint in fingerprints),
    }
    if value["fingerprints_issued"]:
        value["same_root(MR-A, MR-B)"] = same_root(
            mr_a.root_fingerprint,
            roots_fixtures.as_state(mr_a),
            mr_b.root_fingerprint,
            roots_fixtures.as_state(mr_b),
            roots_fixtures.SCALES,
            roots_fixtures.IDS,
        )
        value["same_root(MR-A, MR-C)"] = same_root(
            mr_a.root_fingerprint,
            roots_fixtures.as_state(mr_a),
            mr_c.root_fingerprint,
            roots_fixtures.as_state(mr_c),
            roots_fixtures.SCALES,
            roots_fixtures.IDS,
        )
        value["provenance_differs(MR-A, MR-C)"] = mr_a.branch_provenance != mr_c.branch_provenance
    expected = {
        "delta_root": number(ref["constants"]["delta_root_scaled_inf"]),
        "MR-A": {
            "outcome": roots["MR-A"]["outcome"],
            "iterations (twin, recorded)": roots["MR-A"]["iterations"],
            "scaled_distance_to_S1": f"at most {DELTA_ROOT}",
        },
        "MR-B": {
            "outcome": "CONVERGED",
            "iterations": 0,
            "scaled_distance_to_t_star": "at most δ_root",
        },
        "MR-C": {
            "loop_outcome": roots["MR-C"]["loop_outcome"],
            "loop_iterations": roots["MR-C"]["loop_iterations"],
            "outcome": roots["MR-C"]["merge_outcome"],
            "merge_newton_iterations": "at most 5 (twin "
            f"{roots['MR-C']['merge_newton_iterations']})",
            "scaled_distance_to_S1": "at most δ_root",
            "provenance": [["anderson", "initializer"], ["newton", "merge_best_iterate"]],
        },
        "item_0": dict.fromkeys(
            starts,
            {"initializer_source": "user_guess", "opening_state_sha256_is_the_start": True},
        ),
        "same_root(MR-A, MR-B)": "DISTINCT",
        "same_root(MR-A, MR-C)": "SAME",
        "provenance_differs(MR-A, MR-C)": True,
    }
    ok = (
        DELTA_ROOT == number(ref["constants"]["delta_root_scaled_inf"])
        and mr_a.outcome == roots["MR-A"]["outcome"] == "CONVERGED"
        and value["MR-A"]["scaled_distance_to_S1"] <= DELTA_ROOT
        and mr_b.outcome == "CONVERGED"
        and mr_b.recycle.iterations == roots["MR-B"]["iterations"] == 0
        and value["MR-B"]["scaled_distance_to_t_star"] <= DELTA_ROOT
        and mr_c.recycle.outcome == roots["MR-C"]["loop_outcome"]
        and mr_c.recycle.iterations == roots["MR-C"]["loop_iterations"]
        and mr_c.outcome == roots["MR-C"]["merge_outcome"]
        and value["MR-C"]["merge_newton_iterations"] is not None
        and value["MR-C"]["merge_newton_iterations"] <= 5
        and value["MR-C"]["scaled_distance_to_S1"] <= DELTA_ROOT
        and value["MR-C"]["provenance"]
        == [("anderson", "initializer"), ("newton", "merge_best_iterate")]
        and all(
            row == {"initializer_source": "user_guess", "opening_state_sha256_is_the_start": True}
            for row in value["item_0"].values()
        )
        and value["fingerprints_issued"]
        and value.get("same_root(MR-A, MR-B)") == "DISTINCT"
        and value.get("same_root(MR-A, MR-C)") == "SAME"
        and value.get("provenance_differs(MR-A, MR-C)") is True
    )
    return ok, value, expected


def _a20(runs: Runs) -> tuple[bool, Any, Any]:
    from openflowsheet.numerics.scaling import Scaling
    from openflowsheet.orchestrator.roots import same_root

    names = ("SYN-001-A02-360", PHS["PHS-02"], PHS["PHS-03"])
    results = [runs.region(case_id).result for case_id in names]
    spec = runs.region(names[0]).spec
    scales = Scaling.from_spec(spec).column
    pairs: dict[str, str] = {}
    for a in range(3):
        for b in range(a + 1, 3):
            fa, fb = results[a].root_fingerprint, results[b].root_fingerprint
            # §8.3 as amended (review S3): told which states, by the declaration's ids.
            pairs[f"{names[a]} / {names[b]}"] = (
                same_root(fa, results[a].state, fb, results[b].state, scales, spec.variable_ids)
                if fa is not None and fb is not None
                else "no fingerprint"
            )
    value = {
        "same_root": pairs,
        "provenance_lengths": [len(result.branch_provenance) for result in results],
        "opening_sources": [
            [item["opening_source"] for item in result.branch_provenance] for result in results
        ],
        "distinct_item_0_hashes": len(
            {result.branch_provenance[0]["opening_state_sha256"] for result in results}
        ),
    }
    expected = {
        "same_root": dict.fromkeys(pairs, "SAME"),
        "provenance_lengths": [1, 2, 2],
        "opening_sources": "three different lists",
        "distinct_item_0_hashes": 3,
    }
    sources = [tuple(row) for row in value["opening_sources"]]
    ok = (
        all(result == "SAME" for result in pairs.values())
        and value["provenance_lengths"] == [1, 2, 2]
        and len(set(sources)) >= 2
        and value["distinct_item_0_hashes"] == 3
    )
    return ok, value, expected


def _a21(runs: Runs) -> tuple[bool, Any, Any]:
    from openflowsheet.verify.certificate import verify
    from openflowsheet.verify.checks import VerifierError

    tear = runs.off_b()
    certificate = verify(tear.flowsheet, tear.result).as_document()
    capped, _ = solve_tear(
        tear.flowsheet,
        initial_recycle=k03_fixtures.OFF_B,
        policy=replace(TEAR_POLICY, max_attempts=1),
    )
    # The review's ruling (§8): a non-`CONVERGED` solve receives no certificate — `verify()`
    # refuses it — and its provenance lives on the solve result.
    try:
        verify(tear.flowsheet, capped)
        refused, refusal_message = "returned a certificate", None
    except VerifierError as error:
        refused, refusal_message = "VerifierError", str(error)
    validator = _validator("solution-certificate.schema.json")

    fingerprints: list[Any] = [
        observed.result.root_fingerprint
        for observed in runs.observed()
        if observed.result.root_fingerprint is not None
    ]
    fingerprints += [
        runs.rec_05(route).root_fingerprint
        for route in ("MR-A", "MR-B", "MR-C")
        if runs.rec_05(route).root_fingerprint is not None
    ]
    fingerprints += [f for f in (tear.result.root_fingerprint,) if f is not None]
    claims = sorted(
        {json.dumps(fingerprint.get("claims"), sort_keys=True) for fingerprint in fingerprints}
    )

    def overclaims(document: Any) -> list[str]:
        text = json.dumps(document).lower()
        return [
            word
            for word in ("unique root", "stable")
            if word in text.replace("dynamic_stability", "")
        ]

    history = [
        [dict(item["signature"])["U-FLASH"], item["decision"], item["cause"]]
        for item in certificate["branch_provenance"]
    ]

    def schema_errors(document: Any) -> list[str]:
        return [
            f"{list(error.absolute_path)}: {error.message}"
            for error in validator.iter_errors(document)
        ][:3]

    value = {
        "fingerprints_measured": len(fingerprints),
        "claims_seen": claims,
        "certificates_issued_here": 1,
        "OFF-B": {
            "schema_errors": schema_errors(certificate),
            "history": history,
            "provenance_items_per_attempt": [
                len(certificate["branch_provenance"]),
                tear.result.attempts,
            ],
            "item_keys": sorted(certificate["branch_provenance"][0]) if history else [],
            "fingerprint_claims": (certificate.get("root_fingerprint") or {}).get("claims"),
            "fingerprint_branch_found": (certificate.get("root_fingerprint") or {}).get(
                "branch_found"
            ),
            "overclaims": overclaims(certificate),
        },
        "OFF-B max_attempts=1": {
            "solve_outcome": capped.outcome,
            "attempts": capped.attempts,
            "verify": refused,
            "verify_message": refusal_message,
            "solve_root_fingerprint": capped.root_fingerprint,
            "solve_branch_provenance": [
                {"decision": item["decision"], "cause": item["cause"]}
                for item in capped.branch_provenance
            ],
        },
    }
    item_keys = [
        "attempt",
        "core",
        "core_outcome",
        "cause",
        "decision",
        "initializer_source",
        "iterations",
        "opening_source",
        "opening_state_sha256",
        "opening_trial",
        "signature",
    ]
    not_assessed = {"uniqueness": "NOT_ASSESSED", "dynamic_stability": "NOT_ASSESSED"}
    patience = "phase_wall(patience, U-FLASH:LIQUID->TWO_PHASE)"
    expected = {
        "claims_seen": [json.dumps(not_assessed, sort_keys=True)],
        "OFF-B": {
            "schema_errors": [],
            "history": [
                ["LIQUID", "restart", patience],
                ["TWO_PHASE", "converged", ""],
            ],
            "provenance_items_per_attempt": [2, 2],
            "item_keys": sorted(item_keys),
            "fingerprint_claims": not_assessed,
            # §8.2 as amended (review M1): from the reconstructed state, every lifted split.
            "fingerprint_branch_found": [["U-HEAT", "LIQUID"], ["U-FLASH", "TWO_PHASE"]],
            "overclaims": [],
        },
        "OFF-B max_attempts=1": {
            "solve_outcome": "ATTEMPTS_EXHAUSTED",
            "attempts": 1,
            "verify": "VerifierError",
            "solve_root_fingerprint": None,
            # R-029 (review Q1): the closure proposed a restart; the budget refused it.
            "solve_branch_provenance": [{"decision": "restart", "cause": patience}],
        },
    }
    capped_row = {k: v for k, v in value["OFF-B max_attempts=1"].items() if k != "verify_message"}
    ok = (
        len(fingerprints) > 0
        and claims == expected["claims_seen"]
        and value["OFF-B"] == expected["OFF-B"]
        and capped_row == expected["OFF-B max_attempts=1"]
    )
    return ok, value, expected


def _a22(runs: Runs) -> tuple[bool, Any, Any]:
    from openflowsheet.orchestrator.roots import RootComparisonError, same_root

    mr_a, mr_b = runs.rec_05("MR-A"), runs.rec_05("MR-B")
    fingerprint = mr_a.root_fingerprint
    if fingerprint is None or mr_b.root_fingerprint is None:
        return False, {"MR-A/MR-B": "no fingerprint"}, "a fingerprint on each"
    state, other = roots_fixtures.as_state(mr_a), roots_fixtures.as_state(mr_b)
    scales, ids = roots_fixtures.SCALES, roots_fixtures.IDS
    value: dict[str, Any] = {
        key: same_root(fingerprint, state, {**fingerprint, key: changed}, state, scales, ids)
        for key, changed in (("model_version", "another@model"), ("variable_ids_sha256", "f" * 64))
    }
    value["unchanged (control)"] = same_root(
        fingerprint, state, dict(fingerprint), state, scales, ids
    )

    # §8.3 as amended (review S3): inputs `same_root` cannot vouch for are refused with a typed
    # error — never one of the three verdicts. Recorded beside A22's verdicts, same function.
    def refusal(call: Callable[[], Any]) -> str:
        try:
            return f"returned {call()}"
        except RootComparisonError:
            return "RootComparisonError"

    b_fingerprint = mr_b.root_fingerprint
    value["typed refusals (§8.3 as amended)"] = {
        "empty scales": refusal(
            lambda: same_root(fingerprint, state, b_fingerprint, other, {}, ids)
        ),
        "MR-A's fingerprint with MR-B's state": refusal(
            lambda: same_root(fingerprint, other, b_fingerprint, other, scales, ids)
        ),
        "variable ids not the fingerprint's": refusal(
            lambda: same_root(fingerprint, state, b_fingerprint, other, scales, ids[::-1])
        ),
    }
    expected = {
        "model_version": "NOT_COMPARABLE",
        "variable_ids_sha256": "NOT_COMPARABLE",
        "unchanged (control)": "SAME",
        "typed refusals (§8.3 as amended)": {
            "empty scales": "RootComparisonError",
            "MR-A's fingerprint with MR-B's state": "RootComparisonError",
            "variable ids not the fingerprint's": "RootComparisonError",
        },
    }
    return value == expected, value, expected


# ------------------------------------------------------------------------------ A23–A25


def _a23(identities: Path | None) -> dict[str, Any]:
    description = (
        "R0 on the CI pair. Locally: `scripts/t03_identity.py` covers exactly OFF-B, PHS-01, "
        "PHS-04, PHS-05 and MR-A, carries `phase_contract` `T03-phase-contract-v1` and a "
        "non-empty `jacobian_pattern.sha256` for every attempt of the four phase-contract "
        "solves, the `attempt_opened` messages and PHS-05's terminal `active_set_cycling(…)`, "
        "the R0 fields of `branch_provenance` and `root_fingerprint`; holds no float; is "
        "identical twice on one machine; and `scripts/k05_structural_identity.py`'s document "
        "carries it under `t03`, equal to the one built here. From the two CI artifacts: the "
        "x86-64 and aarch64 `identity.json` are equal key for key and the T02 floats agree — "
        "the `identity` job's own comparison in `.github/workflows/ci.yml` — with `t03` equal. "
        "Without `--identities` the cross-platform half is not measured and the check is "
        "`unsupported`."
    )
    try:
        local, value = _a23_local()
    except Exception as error:  # noqa: BLE001
        return check(
            "T03.A23", description, "fail", {"error": f"{type(error).__name__}: {error}"}, ""
        )
    expected: dict[str, Any] = {
        "cases": ["MR-A", "OFF-B", "PHS-01", "PHS-04", "PHS-05"],
        "phase_contract": dict.fromkeys(("OFF-B", "PHS-01", "PHS-04", "PHS-05"), PHASE_CONTRACT),
        "every_pattern_hashed": True,
        "PHS-05_terminal_is_cycling": True,
        "floats": [],
        "same_twice": True,
        "k05_carries_t03": True,
        "ci": {
            "platforms": 2,
            "identity_differences": [],
            "float_differences": [],
            "t03_equal": True,
        },
    }
    if identities is None:
        value["ci"] = "not measured: no --identities directory given"
        return check("T03.A23", description, "unsupported" if local else "fail", value, expected)
    ci = _ci_comparison(identities)
    value["ci"] = {
        "platforms": len(ci["platforms"]),
        "identity_differences": ci["identity_differences"],
        "float_differences": ci["float_differences"],
        "t03_equal": ci["t03_equal"],
    }
    return check(
        "T03.A23",
        description,
        verdict(local and value["ci"] == expected["ci"]),
        value,
        expected,
    )


def _floats_in(value: Any, path: str = "") -> list[str]:
    if isinstance(value, dict):
        return [found for key, item in value.items() for found in _floats_in(item, f"{path}.{key}")]
    if isinstance(value, list):
        return [found for item in value for found in _floats_in(item, path)]
    return [path] if isinstance(value, float) else []


def _a23_local() -> tuple[bool, dict[str, Any]]:
    from k05_structural_identity import identity as k05_identity
    from t03_identity import identity

    first, second = identity(), identity()
    phase_cases = ("OFF-B", "PHS-01", "PHS-04", "PHS-05")
    value: dict[str, Any] = {
        "cases": sorted(first),
        "phase_contract": {name: first[name].get("phase_contract") for name in phase_cases},
        "every_pattern_hashed": all(
            first[name]["jacobian_patterns"]
            and all(pattern.get("sha256") for pattern in first[name]["jacobian_patterns"])
            for name in phase_cases
        ),
        "attempt_opened_messages": {
            name: [m[2] for m in first[name]["messages"] if m[0] == "attempt_opened"]
            for name in phase_cases
        },
        "PHS-05_terminal_is_cycling": str(first["PHS-05"].get("terminal_message", "")).startswith(
            "active_set_cycling("
        ),
        "floats": sorted(set(_floats_in(first)))[:10],
        "same_twice": first == second,
        "k05_carries_t03": k05_identity().get("t03") == json.loads(json.dumps(first)),
    }
    local = (
        value["cases"] == ["MR-A", "OFF-B", "PHS-01", "PHS-04", "PHS-05"]
        and all(item == PHASE_CONTRACT for item in value["phase_contract"].values())
        and value["every_pattern_hashed"]
        and value["PHS-05_terminal_is_cycling"]
        and not value["floats"]
        and value["same_twice"]
        and value["k05_carries_t03"]
    )
    return local, value


def _ci_comparison(directory: Path) -> dict[str, Any]:
    """The CI `identity` job's comparison, applied to its two downloaded artifacts."""
    from openflowsheet.run.compare import differences

    found = sorted(directory.rglob("identity.json"))
    documents = {path.parent.name: json.loads(path.read_text(encoding="utf-8")) for path in found}
    floats = {
        path.parent.name: json.loads(path.read_text(encoding="utf-8"))
        for path in directory.rglob("t02-floats.json")
    }
    names = sorted(documents)
    identity_differences: list[str] = []
    float_differences: list[str] = []
    if sorted(floats) != names:
        float_differences.append(f"t02-floats.json from {sorted(floats)}, identities from {names}")
    if len(names) < 2:
        identity_differences.append(f"two platforms needed; found {len(names)}")
    first = documents[names[0]] if names else {}
    for name in names[1:]:
        other = documents[name]
        identity_differences += [
            f"{key}: {names[0]} != {name}"
            for key in sorted(set(first) | set(other))
            if first.get(key) != other.get(key)
        ]
        if name in floats and names[0] in floats:
            float_differences += [
                f"{entry} ({names[0]} vs {name})"
                for entry in differences(
                    floats[name],
                    floats[names[0]],
                    "t02_floats",
                    policy_id="K04-numerical-policy-v1",
                )
            ]
    t03 = [document.get("t03") for document in documents.values()]
    return {
        "platforms": names,
        "identity_differences": identity_differences,
        "float_differences": float_differences,
        "t03_equal": len(t03) >= 2 and bool(t03[0]) and all(item == t03[0] for item in t03),
    }


def _a24() -> tuple[bool, Any, Any]:
    run = executor_fixtures.revision_run(NO_GUESS)
    regions = [step for step in run.plan.steps if step.kind == "solve_eo"]
    result = run.result
    events = result.trace.events
    rejected = [event.message for event in events if event.kind == "initializer_rejected"]
    value = {
        "solve_eo_steps": len(regions),
        "S3.T_adjusted": bool(regions)
        and regions[0].region is not None
        and "S3.T" in regions[0].region.adjusted_variables,
        "initializer_rejected": rejected,
        "outcome": result.outcome,
        "message": result.message,
        "attempt_opened": sum(1 for event in events if event.kind == "attempt_opened"),
        "jacobian_calls": result.counters.jacobian_calls,
        "CONVERGED_in_trace": any(event.outcome == "CONVERGED" for event in events),
    }
    expected = {
        "solve_eo_steps": 1,
        "S3.T_adjusted": True,
        "initializer_rejected": ["missing_initial_guess(S3.T)"],
        "outcome": "INITIALIZATION_FAILED",
        "message": "missing_initial_guess(S3.T)",
        "attempt_opened": 0,
        "jacobian_calls": 0,
        "CONVERGED_in_trace": False,
    }
    return value == expected, value, expected


def _a25(gate: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    collected = [line for line in completed.stdout.splitlines() if "::" in line]
    families = {
        family: sum(1 for line in collected if line.startswith(f"tests/test_{family}_"))
        for family in ("k03", "t02", "k04", "k05", "t03")
    }
    value = {
        "gate": dict(gate),
        "collected": len(collected),
        "collected_by_family": families,
    }
    expected = {
        "gate": {"passed": True, "pytest_failed_or_errors": False, "pytest_counts": "passed only"},
        "collected": "equal to the gate's passed count",
        "collected_by_family": "every family at least 1",
    }
    ok = (
        gate["passed"]
        and not gate["pytest_failed_or_errors"]
        and set(gate["pytest_counts"]) == {"passed"}
        and completed.returncode == 0
        and len(collected) == gate["pytest_passed"] > 0
        and all(count > 0 for count in families.values())
    )
    return ok, value, expected


# ------------------------------------------------------------------------------ limitations


def _limitations(ci_run: bool, identities: bool) -> list[str]:
    stated = [
        # Spec §13, restated item by item.
        "Spec §13: correctness of any solver is not established. The specification registers "
        "what a correct implementation of the contract must produce; the twin is the contract "
        "simulated a second time on an exact reduction of the region. This manifest measures "
        "the implementation against those registrations — numerical verification, not "
        "empirical validation.",
        "Spec §13: that the contract converges wherever a root exists is not established. "
        "PHS-05 (A12) is a registered counterexample on an ordinary guess, and the A02 scan "
        "found one more (377 K). The bound-driven disappearance premise holds at roots, not at "
        "Newton iterates far from them; the persistent-block rule filters a one-step overshoot "
        "(PHS-01/02), not a two-step one (PHS-05). Handed to T04 (spec F1).",
        "Spec §13: recurrence of a signature is not permitted (`no_repeated_signature`); §7 "
        "says why and what would reopen it.",
        "Spec §13: phase changes of more than one lifted unit at once, or of the flash on the "
        "lifted path, are stated rules that no registered case exercises.",
        "Spec §13: a single-phase unit whose component vanishes from the stream, a provider "
        "whose K-values vanish or diverge, a saturated lifted stream, and a narrow-band mixture "
        "where even the adjacent candidate is absent (only PHS-SYN-2's synthetic) are stated, "
        "not exercised on physics.",
        "Spec §13: root completeness, uniqueness, thermodynamic stability beyond K03 §8.2 and "
        "dynamic stability are not assessed (`claims` say NOT_ASSESSED; no root search runs). "
        "Two roots within delta_root = 1e-4 scaled are reported SAME; a fingerprint cannot "
        "separate nearly degenerate steady states, and REC-05's basin boundaries are finer "
        "than double precision resolves.",
        "Spec §13: warm starts across runs and continuation history do not exist in v0.1; the "
        "opening checks are ready for an external checkpoint and exercised here only by "
        "constructed bites (A16).",
        "Spec §13: the cost of the screen at size is not measured; counts are registered on "
        "SYN-001 only.",
        "Spec §13: nothing is empirically validated (SYN-001 and REC-05 are synthetic), and "
        "human numerical and process-modeling review are `pending`; no agent sets them.",
        # The implementation review's rulings (docs/reviews/T03-review.md §5) on the choices the
        # build lane made and recorded for it — accepted, and stated here as settled.
        "Review ruling Q1 / brief decision 3 (register R-029): `branch_provenance.decision` "
        "records what the attempt's closure proposed; an attempt whose restart the restart gate "
        "refused (budget, cycling, opening check) is `restart` with that restart's cause, the "
        "refusal being the solve's outcome and terminal message. Spec §8.1 amended; PHS-05's "
        "attempt 2, A16's refused openings and OFF-B under `max_attempts = 1` read `restart`.",
        "Review ruling Q2 / brief decision 1: a removed row's parameter that no remaining row "
        "reads is dropped from the declaration's identity (sound: an initial guess is not a "
        "constant of the problem); every A02 revision's `constants_sha256` changed as the "
        "correction of an identity that was wrong. Accepted with the review's N2 hardening "
        "note (parameter reads other than `__getitem__` are not yet recorded).",
        "Review ruling Q3: spec §14 Q2–Q5's defaults are confirmed — no far-restart refusal, "
        "the registry class `phase-controller case` outside the success denominator (Frank's "
        "to overrule, review §6), `delta_root = 1e-4`, `alpha` on `attempt_opened`.",
        "Review ruling, brief decision 4: `root_fingerprint.delta_scaled_inf` is a registered "
        "constant (`1e-4`), compared exactly as an ADR 0007 D1 field — accepted; spec §10 "
        "amended from 'no float is added' to 'no *measured* float is added'.",
        "Review ruling, brief decision 5: the cycling `solve_closed` message follows §4.10's "
        "grammar, which re-registers K03's `test_restarting_into_a_used_signature_is_reported_"
        "as_cycling` — accepted; spec §10 amended to list it.",
        "Review ruling, brief decision 6: a bare region solve records no `solve_closed`; the "
        "plan executor's `solve_closed` carries the region's message (measured by the review "
        "on PHS-05) — accepted; spec §4.10 amended to say where it lives.",
        "PHS-05 (`SYN-001-A02-355-dew-guess`) is an expected failure handed to T04 (spec F1); "
        "A12 asserts the failure, and the registry keeps it outside the success denominator.",
        # Defects and scope handed on by the review, not closed in T03.
        "K04 defect handed on (review §8): a `CONVERGED` result without `x_final` still "
        "yields a certificate its schema refuses (`regularity: null`). It is unreachable on "
        "every registered path (K04 A01 made every `CONVERGED` result carry `x_final`) and is "
        "not a phase-attempt question; a K04 follow-up decides between refusing that input "
        "too and a nullable `regularity` (a schema change, its own ADR).",
        "Review S1's tear-path twin is not folded in: a `BudgetExhaustedError` on the tear "
        "path still returns `attempts = 0`, `x = start` and no provenance (K03's registered "
        "capped-budget shape). Handed to T04/K05 (review §7); the region path's refusal now "
        "closes the attempt with its end state, `partial` checkpoint and provenance.",
        "A03's scope on the tear path (review M3): property calls made inside the compiled "
        "problem by its property blocks carry the provider context bound at assembly (K01/K02: "
        "one compiled problem serves every attempt; `casadi_backend.residual` states that "
        "nothing in `context` reaches the evaluated function). That context is field-equal to "
        "the attempt's flowsheet context (`attempts._context_document`), not the attempt's "
        "object; A03 counts these calls in their own category and asserts field equality. "
        "Routing the attempt's object into the CasADi callbacks is a compiled-boundary change "
        "for the design lane.",
        # What the measurements here do and do not reach.
        "A12's and A16's failure-bundle class and action are the ones `bundle_for` resolves "
        "from the verifier's tables (`TAXONOMY`, then `OUTCOME_ACTIONS` over `ACTIONS`) for the "
        "solve's outcome; no bundle document is built from a region result here (the region "
        "returns no K03-shaped result for `bundle_for`).",
        "Spec A26 lists V15 among `requirements`; the frozen evidence-manifest schema takes "
        "D/A ids only (measured: it refuses `V15`), so this manifest names D09, D11 and A01 and "
        "V15 is carried by `docs/requirements.yaml` (owner packages T02, T03) — T02's "
        "precedent for V13/V15.",
    ]
    if not identities:
        stated.append(
            "The cross-platform half of A23 was not measured by this run: no `--identities` "
            "directory was given, so the check is `unsupported`, not `pass`."
        )
    if not ci_run:
        stated.append(
            "No CI run was named (`--ci-run`), so `commands` records the local gate only and "
            "A26's two-architecture half is `unsupported`."
        )
    return stated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("gate_stdout", type=Path)
    parser.add_argument("--commit", required=True)
    parser.add_argument(
        "--identities",
        type=Path,
        default=None,
        help="directory holding the two downloaded structural-identity-* CI artifacts",
    )
    parser.add_argument("--ci-run", default=None, help="the workflow run that compared platforms")
    parser.add_argument("--out", type=Path, default=None)
    arguments = parser.parse_args()

    manifest = plain(
        build(arguments.commit, arguments.gate_stdout, arguments.identities, arguments.ci_run)
    )
    destination = arguments.out or (ROOT / "evidence" / "T03" / arguments.commit / "manifest.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=1, allow_nan=False) + "\n", encoding="utf-8")

    counts = {
        name: sum(entry["result"] == name for entry in manifest["checks"])
        for name in ("pass", "fail", "unsupported", "not_applicable")
    }
    print(f"wrote {destination}")
    print(
        f"checks: {counts['pass']} pass, {counts['fail']} fail, "
        f"{counts['unsupported']} unsupported, {counts['not_applicable']} not applicable; "
        f"status {manifest['status']}"
    )
    for entry in manifest["checks"]:
        if entry["result"] != "pass":
            print(f"  {entry['id']}: {entry['result']}")
    return 1 if counts["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
