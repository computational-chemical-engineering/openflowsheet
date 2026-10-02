"""T06 phase M (measure first): M1, M2 and M3 of `docs/derivations/T06-corpus-spec.md` §17.

Measurement only: nothing here is a gate, and nothing in `src/` is changed. The numbers each
command printed are recorded, with the commit, in `docs/t06-measurements.md`.

- `m1`: every flowsheet revision under `benchmarks/t06/cases/` (the ten new corpus cases of §4.3
  and REF-01…REF-07 of §9.2) bound, planned, solved from its registered initializer
  (`traversal-G0-v1`) under `T05b-v2` and `T05-W13`, and certified; the certified state against
  the twin — `ref.closed_form.corpus_cases` at T02 §6.4's allowances (flows 3.1e-7 mol/s, `T`
  1e-5 K, `P` 0.1 Pa, duty and work 1e-2 W), `ref.closed_form.reference_fixtures` at §9.4's
  tolerance.
- `m1-detail`: the digits §2 quotes; NET-02's trace; NET-11 certified under a domain-safe alias
  shift (a monkeypatch of the verifier, as §2's probe: measurement only, never a fix).
- `m2`: the 22 ensemble-eligible cases (§3.2, §6.1) solved from their registered initializers
  under their ensemble policies (§6.6), cold, `--repeats` times, with the four wall times.
- `m3`: today's STR-02, STR-06, STA-03 (kg/s, degC) and STA-04 (§0 F1, F2, F5).

Usage (from the repository root):
    PYTHONPATH=src:. .venv/bin/python scripts/t06_phase_m.py m1
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from collections.abc import Callable, Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))

import t05b_support as t05b  # noqa: E402
from test_t05_coupled import POLICY as POLICY_V1  # noqa: E402

import openflowsheet.orchestrator.executor as executor_module  # noqa: E402
import openflowsheet.orchestrator.revision as revision_module  # noqa: E402
import openflowsheet.orchestrator.tear as tear_module  # noqa: E402
import openflowsheet.verify.certificate as certificate_module  # noqa: E402
from openflowsheet.application.binding import Binding, bind_revision  # noqa: E402
from openflowsheet.application.revision_binding import (  # noqa: E402
    RevisionBinding,
    bind_revision_flowsheet,
)
from openflowsheet.application.validation import validate  # noqa: E402
from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet  # noqa: E402
from openflowsheet.orchestrator.execution import ExecutionPlan  # noqa: E402
from openflowsheet.orchestrator.rank import eliminate_alias_rows  # noqa: E402
from openflowsheet.orchestrator.trace import SolvePolicy  # noqa: E402

POLICY_V2 = t05b.POLICY_V2
TEAR_POLICY = SolvePolicy(policy_id="SYN-001-K03", residual_tolerances={}, scales={})
A02_POLICY = SolvePolicy(policy_id="T04-W12", residual_tolerances={}, scales={})
T06_CASES = ROOT / "benchmarks" / "t06" / "cases"
T05_CASES = ROOT / "benchmarks" / "t05" / "cases"
SYN_CASES = ROOT / "benchmarks" / "syn001" / "cases"
REF = yaml.safe_load((ROOT / "benchmarks" / "t06" / "reference_values.yaml").read_text())
CORPUS = REF["closed_form"]["corpus_cases"]
FIXTURES = REF["closed_form"]["reference_fixtures"]
ALLOW = {"n": 3.1e-7, "T": 1e-5, "P": 0.1, "Q": 1e-2, "W": 1e-2, "xi": 3.1e-7}

Document = dict[str, Any]


def load(path: Path) -> Document:
    loaded: Document = yaml.safe_load(path.read_text())
    return loaded


def first_line(text: str | None) -> str:
    return (text or "").splitlines()[0][:140] if text else ""


# -- M1 ---------------------------------------------------------------------------------------


def registered(entry: Mapping[str, Any]) -> dict[str, tuple[str, float]]:
    """Every registered coordinate of a corpus case: column -> (20-digit value, allowance)."""
    out: dict[str, tuple[str, float]] = {}
    for stream, state in entry["streams"].items():
        for c, v in zip("ABC", state["n_mol_per_s"], strict=True):
            out[f"{stream}.n.{c}"] = (v, ALLOW["n"])
        out[f"{stream}.T"] = (state["T_K"], ALLOW["T"])
        out[f"{stream}.P"] = (state["P_Pa"], ALLOW["P"])
        for key, phase in (("vapor_mol_per_s", "vap"), ("liquid_mol_per_s", "liq")):
            for c, v in zip("ABC", state.get(key) or (), strict=False):
                out[f"{stream}.{phase}.{c}"] = (v, ALLOW["n"])
    for field, suffix in (("duty_W", "Q"), ("work_W", "W"), ("extent_mol_per_s", "xi")):
        for unit, v in (entry.get(field) or {}).items():
            out[f"{unit}.{suffix}"] = (v, ALLOW[suffix])
    return out


def worst(state: Mapping[str, float], expected: Mapping[str, tuple[str, float]]) -> str:
    missing = [k for k in expected if k not in state]
    ratio, where = max(
        (float(abs(Decimal(state[k]) - Decimal(v)) / Decimal(a)), k)
        for k, (v, a) in expected.items()
        if k in state
    )
    return f"worst {ratio:.2e} @ {where}; missing {missing}"


def solve_revision_case(doc: Document, policy: SolvePolicy) -> dict[str, Any]:
    binding = bind_revision_flowsheet(doc)
    if not isinstance(binding, RevisionBinding):
        return {"outcome": f"UNBOUND {binding}"}
    plan, _ = revision_module.plan_revision(binding, policy)
    if not isinstance(plan, ExecutionPlan):
        return {"outcome": f"PLAN_REFUSED {plan}"}
    run = executor_module.execute_plan(
        plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=policy
    )
    out: dict[str, Any] = {"outcome": run.outcome, "message": first_line(run.message)}
    if run.outcome != "CONVERGED":
        events = [e.as_document() for e in run.trace.events]
        out["recovery"] = sorted(
            {
                f"{k}={d[k]}"
                for d in events
                for k in ("eo_recovery", "eo_recovery_unsupported")
                if d.get(k)
            }
        )
        return out
    out["state"] = run.steps[-1].detail.state
    try:
        certificate = certificate_module.verify_revision(
            binding, doc, run, solve_plan=plan.steps[-1].solve_plan
        )
        out["verdict"] = certificate.verification_status
        out["fails"] = [
            c.id for c in certificate.checks if c.result not in ("pass", "not_applicable")
        ]
    except Exception as error:  # recorded, not handled: §0 F3 is a raise on a converged state
        out["verdict"] = f"{type(error).__name__}: {str(error)[:120]}"
    return out


def m1(_: argparse.Namespace) -> None:
    for path in sorted(T06_CASES.glob("*.yaml")):
        case = path.stem
        fixture = f"REF-{case[-2:]}" if "REF" in case else None
        if case not in CORPUS and fixture is None:
            continue  # a diagnosis fixture: M3
        doc = load(path)
        for name, policy in (("v2", POLICY_V2), ("v1", POLICY_V1)):
            out = solve_revision_case(doc, policy)
            line = f"{case} {name} {out['outcome']} {out.get('verdict')} {out.get('fails', '')}"
            if "state" in out:
                state = out["state"]
                if fixture is None:
                    line += " | allowances: " + worst(state, registered(CORPUS[case]))
                else:
                    quantities = FIXTURES[fixture]["quantities"]
                    expected = {
                        k: (q["value"], float(q["tolerance"])) for k, q in quantities.items()
                    }
                    line += " | §9.4 tolerance: " + worst(state, expected)
            else:
                line += f" | {out.get('message')} {out.get('recovery')}"
            print(line, flush=True)


def _shift_reversed_where_out_of_domain(self: Any, state: Mapping[str, float]) -> Any:
    """`BoundDeclaration._aliases` with the upward shift reversed where it leaves the provider's
    declared pressure domain (§0 F3's probe; measurement only)."""
    p_max = 2.0e5
    jacobian = self.compiled.jacobian(
        np.array(certificate_module.state_vector(self.spec, state)), self.context
    )
    coefficients: dict[str, dict[str, float]] = {name: {} for name in jacobian.row_ids}
    for column, name in enumerate(jacobian.col_ids):
        for offset in range(jacobian.indptr[column], jacobian.indptr[column + 1]):
            row = jacobian.row_ids[jacobian.indices[offset]]
            coefficients[row][name] = float(jacobian.data[offset])
    shifted = dict(state)
    for index, name in enumerate(self.spec.variable_ids):
        if self.spec.variable_kinds.get(name) == "pressure":
            step = self.PRESSURE_SHIFT * (index + 1)
            up = state[name] + step
            shifted[name] = up if up <= p_max else state[name] - step
            if up > p_max:
                print(f"   reversed shift at {name} (index {index}): {state[name]} + {step}")
    return eliminate_alias_rows(
        row_ids=self.spec.equation_ids,
        coefficients=coefficients,
        column_kinds=self.spec.variable_kinds,
        residuals=[self._rows(state), self._rows(shifted)],
    )


def m1_detail(_: argparse.Namespace) -> None:
    watch = {
        "SYN-001-T06-THM02": ["S2.T"],
        "SYN-001-T06-THM10": ["S2.T"],
        "SYN-001-T06-NET03": ["S5.T", "S7.n.A", "S10.n.A"],
        "SYN-001-T06-NET09": ["S6.n.A", "S6.n.B", "S6.n.C"],
    }
    for case, columns in watch.items():
        out = solve_revision_case(load(T06_CASES / f"{case}.yaml"), POLICY_V2)
        print(case, " ".join(f"{k}={out['state'][k]!r}" for k in columns))

    doc = load(T06_CASES / "SYN-001-T06-NET02.yaml")
    binding = bind_revision_flowsheet(doc)
    assert isinstance(binding, RevisionBinding)
    plan, _ = revision_module.plan_revision(binding, POLICY_V2)
    assert isinstance(plan, ExecutionPlan)
    run = executor_module.execute_plan(
        plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=POLICY_V2
    )
    print("SYN-001-T06-NET02", run.outcome)
    for event in run.trace.events:
        d = event.as_document()
        keys = ("kind", "outcome", "iteration", "attempt", "eo_recovery", "eo_recovery_unsupported")
        print("  ", {k: d[k] for k in keys if d.get(k) not in (None, "", [])})
    state = run.steps[-1].detail.state
    print(
        "   flow columns at exactly 0.0:",
        sorted(k for k, v in state.items() if ".n." in k and v == 0.0),
    )

    original = certificate_module.BoundDeclaration._aliases
    certificate_module.BoundDeclaration._aliases = _shift_reversed_where_out_of_domain  # type: ignore[method-assign]
    try:
        out = solve_revision_case(load(T06_CASES / "SYN-001-T06-NET11.yaml"), POLICY_V2)
    finally:
        certificate_module.BoundDeclaration._aliases = original  # type: ignore[method-assign]
    shown = {k: out["state"][k] for k in ("S8.n.A", "S5.T", "S6.T")}
    print("SYN-001-T06-NET11 (probe)", out["outcome"], out["verdict"], out["fails"], shown)


# -- M2 ---------------------------------------------------------------------------------------


class Clock:
    """Wall time by phase; a nested phase's time is subtracted from the enclosing one."""

    def __init__(self) -> None:
        self.stack: list[list[Any]] = []
        self.buckets: dict[str, float] = {}

    def phase(self, name: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        self.stack.append([name, time.perf_counter(), 0.0])
        try:
            return fn(*args, **kwargs)
        finally:
            _, start, child = self.stack.pop()
            elapsed = time.perf_counter() - start
            self.buckets[name] = self.buckets.get(name, 0.0) + elapsed - child
            if self.stack:
                self.stack[-1][2] += elapsed

    def wrap(self, name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            return self.phase(name, fn, *args, **kwargs)

        return wrapped


CLOCK = Clock()


def _instrument() -> None:
    """compile: every `compile_problem`; init: the registered initializer (revision path
    `traversal_start`; tear path `Syn001Flowsheet.initial_recycle`; A02 the executor's
    sequential pre-solve). Timing wrappers only."""
    for module in (executor_module, tear_module, certificate_module):
        module.compile_problem = CLOCK.wrap("compile", module.compile_problem)  # type: ignore[attr-defined]
    revision_module.traversal_start = CLOCK.wrap("init", revision_module.traversal_start)  # type: ignore[assignment]
    Syn001Flowsheet.initial_recycle = CLOCK.wrap("init", Syn001Flowsheet.initial_recycle)  # type: ignore[method-assign]
    executor_module.solve_tear = CLOCK.wrap("init", executor_module.solve_tear)  # type: ignore[attr-defined]


def _revision(case: str) -> Callable[[], Document]:
    return lambda: load(T06_CASES / f"{case}.yaml")


ELIGIBLE_REVISION: dict[str, Callable[[], Document]] = {
    "STR-01": lambda: load(T05_CASES / "SYN-001-UL-C1.yaml"),
    "STA-01": t05b.dz3,
    "STA-02": _revision("SYN-001-T06-STA02"),
    "STA-05": t05b.dz7,
    "NUM-03": lambda: t05b.near_pure("NP-1"),
    "THM-01": _revision("SYN-001-T06-THM01"),
    "THM-02": _revision("SYN-001-T06-THM02"),
    "THM-07": t05b.sc2,
    "THM-08": t05b.sc1,
    "THM-09": t05b.sc3,
    "THM-10": _revision("SYN-001-T06-THM10"),
    "NET-02": _revision("SYN-001-T06-NET02"),
    "NET-03": _revision("SYN-001-T06-NET03"),
    "NET-06": _revision("SYN-001-T06-NET06"),
    "NET-07": lambda: load(T05_CASES / "SYN-001-UL-C3.yaml"),
    "NET-08": lambda: load(T05_CASES / "SYN-001-UL-C2.yaml"),
    "NET-09": _revision("SYN-001-T06-NET09"),
    "NET-10": _revision("SYN-001-T06-NET10"),
    "NET-11": _revision("SYN-001-T06-NET11"),
}
ELIGIBLE_TEAR = {"THM-03": "SYN-001-all-liquid-310K", "NET-01": "SYN-001-nominal"}
ELIGIBLE_LEGACY_EO = {"NET-05": "SYN-001-A02-360"}


def _count(value: Any) -> Any:
    if value is None or isinstance(value, int):
        return value
    try:
        return len(value)
    except TypeError:
        return str(value)


def _timed_revision(doc: Document) -> tuple[str, Any, Any, Any, str]:
    binding = CLOCK.phase("compile", bind_revision_flowsheet, doc)
    assert isinstance(binding, RevisionBinding), binding
    plan, _ = CLOCK.phase("compile", revision_module.plan_revision, binding, POLICY_V2)
    run = CLOCK.phase(
        "solve",
        executor_module.execute_plan,
        plan=plan,
        flowsheet=binding.flowsheet,
        spec=binding.spec,
        policy=POLICY_V2,
    )
    verdict, note = None, ""
    if run.outcome == "CONVERGED":
        try:
            verdict = CLOCK.phase(
                "verify",
                certificate_module.verify_revision,
                binding,
                doc,
                run,
                solve_plan=plan.steps[-1].solve_plan,
            ).verification_status
        except Exception as error:  # recorded: §0 F3
            verdict, note = type(error).__name__, str(error)[:100]
    else:
        note = first_line(run.message)[:100]
    detail = run.steps[-1].detail
    attempts = getattr(detail, "attempts", None)
    return run.outcome, verdict, attempts, getattr(detail, "iterations", None), note


def _timed_tear(case_id: str) -> tuple[str, Any, Any, Any, str]:
    doc = load(SYN_CASES / f"{case_id}.yaml")
    binding = CLOCK.phase("compile", bind_revision, doc)
    assert isinstance(binding, Binding), binding
    result, _ = CLOCK.phase("solve", tear_module.solve_tear, binding.flowsheet, policy=TEAR_POLICY)
    verdict = None
    if result.outcome == "CONVERGED":
        verdict = CLOCK.phase(
            "verify", certificate_module.verify, binding.flowsheet, result
        ).verification_status
    return (
        result.outcome,
        verdict,
        getattr(result, "attempts", None),
        getattr(result, "iterations", None),
        "",
    )


def _timed_legacy_eo(case_id: str) -> tuple[str, Any, Any, Any, str]:
    import test_t02_executor

    doc = load(SYN_CASES / f"{case_id}.yaml")
    binding = CLOCK.phase("compile", bind_revision, doc)
    assert isinstance(binding, Binding), binding
    original = test_t02_executor.execute_plan

    def timed(**kwargs: Any) -> Any:
        return CLOCK.phase("solve", original, **kwargs)

    test_t02_executor.execute_plan = timed  # type: ignore[assignment]
    try:
        run = CLOCK.phase(
            "compile",  # trace, analyse, the specification region and the plan
            test_t02_executor.run_flowsheet,
            binding.flowsheet,
            binding.spec,
            binding.graph,
            binding.row_units,
            A02_POLICY,
            specification_ids=binding.specification_ids,
            freed=binding.freed,
            promoted=binding.promoted,
            missing_guesses=binding.missing_guesses,
        )
    finally:
        test_t02_executor.execute_plan = original  # type: ignore[assignment]
    (step,) = [s for s in run.result.steps if s.kind == "solve_eo"]
    (planned,) = [s for s in run.plan.steps if s.kind == "solve_eo"]
    verdict = None
    if step.outcome == "CONVERGED":
        verdict = CLOCK.phase(
            "verify",
            certificate_module.verify_bound,
            binding,
            doc,
            step.detail,
            solve_plan=planned.solve_plan,
        ).verification_status
    detail = step.detail
    return step.outcome, verdict, detail.attempts, detail.iterations, ""


def m2(arguments: argparse.Namespace) -> None:
    _instrument()
    jobs: list[tuple[str, str, Callable[[], tuple[str, Any, Any, Any, str]]]] = []
    for case, build in ELIGIBLE_REVISION.items():
        jobs.append((case, "revision_eo", lambda build=build: _timed_revision(build())))
    for case, case_id in ELIGIBLE_TEAR.items():
        jobs.append((case, "tear", lambda case_id=case_id: _timed_tear(case_id)))
    for case, case_id in ELIGIBLE_LEGACY_EO.items():
        jobs.append((case, "legacy_eo", lambda case_id=case_id: _timed_legacy_eo(case_id)))
    jobs.sort()
    _timed_revision(ELIGIBLE_REVISION["STR-01"]())  # imports and CasADi warm-up, not measured
    repeats = arguments.repeats
    print(
        f"{'case':7} {'path':11} {'outcome':14} {'verdict':14} att it   compile     init    "
        f"solve   verify    total (median of {repeats}) max-total"
    )
    for case, path, job in jobs:
        rows, outcomes = [], set()
        for _ in range(repeats):
            CLOCK.stack, CLOCK.buckets = [], {}
            start = time.perf_counter()
            outcome, verdict, attempts, iterations, note = job()
            total = time.perf_counter() - start
            b = CLOCK.buckets
            rows.append(
                (
                    b.get("compile", 0.0),
                    b.get("init", 0.0),
                    b.get("solve", 0.0),
                    b.get("verify", 0.0),
                    total,
                )
            )
            outcomes.add((outcome, verdict, _count(attempts), _count(iterations), note))
        medians = [statistics.median(column) for column in zip(*rows, strict=True)]
        o = sorted(outcomes, key=str)[0]
        flag = "" if len(outcomes) == 1 else f" DIFFERS ACROSS REPEATS {outcomes}"
        print(
            f"{case:7} {path:11} {o[0]:14} {o[1]!s:14} {o[2]!s:3} {o[3]!s:3} "
            + " ".join(f"{v:8.4f}" for v in medians)
            + f" {max(r[4] for r in rows):9.4f} {o[4]}{flag}",
            flush=True,
        )


# -- M3 ---------------------------------------------------------------------------------------

DIAGNOSIS = (
    "SYN-001-T06-STR02",
    "SYN-001-T06-STR06",
    "SYN-001-T06-STA03-kgs",
    "SYN-001-T06-STA03-degC",
    "SYN-001-T06-STA04",
)


def m3(_: argparse.Namespace) -> None:
    for case in DIAGNOSIS:
        doc = load(T06_CASES / f"{case}.yaml")
        report = validate(doc)
        print(f"== {case}: validate -> {report.status}")
        for check in report.checks:
            print(
                f"   {check.id:9} {check.result:8} {check.message[:110]!r} "
                f"{list(check.implicated_objects)}"
            )
        legacy = bind_revision(doc)
        if isinstance(legacy, Binding):
            feeds = [
                (u.unit_id, u.flows, u.temperature, u.pressure)
                for u in legacy.flowsheet.units()
                if type(u).__name__ == "FeedSource"
            ]
            print(f"   bind_revision -> Binding; feeds (unit, flows, T, P): {feeds}")
            try:
                result, _ = tear_module.solve_tear(legacy.flowsheet, policy=TEAR_POLICY)
                line = f"   solve_tear -> {result.outcome}"
                if result.outcome == "CONVERGED":
                    certificate = certificate_module.verify(legacy.flowsheet, result)
                    state = result.final_state
                    line += (
                        f"; certificate {certificate.verification_status}; S4.n = "
                        f"{[state[f'S4.n.{c}'] for c in 'ABC']}; S6.n = "
                        f"{[state[f'S6.n.{c}'] for c in 'ABC']}"
                    )
                else:
                    line += f"; {first_line(result.message)}"
                print(line)
            except Exception as error:  # recorded: what today's code does
                print(f"   solve_tear raised {type(error).__name__}: {str(error)[:160]}")
        else:
            print(f"   bind_revision -> {legacy!r}")
        general = bind_revision_flowsheet(doc)
        shown = "RevisionBinding" if isinstance(general, RevisionBinding) else repr(general)
        print(f"   bind_revision_flowsheet -> {shown}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("m1").set_defaults(run=m1)
    sub.add_parser("m1-detail").set_defaults(run=m1_detail)
    timing = sub.add_parser("m2")
    timing.add_argument("--repeats", type=int, default=5)
    timing.set_defaults(run=m2)
    sub.add_parser("m3").set_defaults(run=m3)
    arguments = parser.parse_args()
    arguments.run(arguments)


if __name__ == "__main__":
    main()
