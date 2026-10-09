"""M05 WO-3: the TRF runner on TR-E1 — gates G2 (the pin) and G3 (TR-E1 against Pyomo's native
example), the subproblem options, and the probe findings P2′, P3, P6, P7, P8, P9 and P10 as tests
(design note §4, §5.1, §6.3, §6.7, §13; ADR 0038 D1, D4, D5, D8).

The native example is Pyomo's own `contrib/trustregion/examples/example1.py`, run in the same
process with the same subproblem solver alias, so the comparison isolates the projection and the
holders. Every test here is marked `nlp`: Pyomo and the Ipopt executable exist only in the audited
environment (`scripts/m03_nlp_check.sh`). Nothing at module level imports Pyomo.
"""

from __future__ import annotations

import contextlib
import io
import logging
import math
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from m05_support import PROBE_P1, TR_E1_DECISIONS, SineBlock, tr_e1_projection

from openflowsheet.compile.spec import DomainError
from openflowsheet.studies.trust_region.holders import (
    TRF_PMP_VALUE,
    TRF_START_VALUE,
    TRF_TRIAL_VALUE,
    ColdBudget,
)
from openflowsheet.studies.trust_region.trf_state import (
    EXIT_OPTIMAL,
    TRF_PACKAGE,
    TRSP_OPTIONS,
    TRSP_SOLVER_ALIAS,
    IterationRecord,
    TrfLogHandler,
    framework_readiness,
    reconstruct_filter,
    trsp_executable,
)

pytestmark = pytest.mark.nlp

TR_E1_CONFIG = {"solver": TRSP_SOLVER_ALIAS}
#: Probe P2′'s request sequence for TR-E1: F a cold value, f a memo hit, g a gradient.
PROBE_SEQUENCE = "FFfffgfFfffgFfffgFfffgF"
#: The same through `run_trf`: R-276's pre-flight makes the cold start request, so TRF's own first
#: request — `EFReplacement`'s start value — is a memo hit, and every other request is unchanged.
RUN_SEQUENCE = "Ff" + PROBE_SEQUENCE[1:]
VALUE_TOLERANCE = 1e-10


def run(block: SineBlock | None = None, **options: Any) -> tuple[Any, Any]:
    from openflowsheet.studies.trust_region.trf import run_trf

    projection = tr_e1_projection(block)
    return projection, run_trf(projection, options.pop("config", TR_E1_CONFIG), **options)


def native(model: Any = None, **config: Any) -> tuple[Any, tuple[IterationRecord, ...], list[str]]:
    """Pyomo's example 1 (or `model`) solved by TRF directly, with its log parsed and its `EXIT:`
    lines captured exactly as `run_trf` does."""
    import pyomo.environ as pyo
    from pyomo.contrib.trustregion.examples import example1

    model = example1.create_model() if model is None else model
    handler = TrfLogHandler()
    logger = logging.getLogger(TRF_PACKAGE)
    saved = (logger.level, logger.propagate)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(handler)
    captured = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured):
            returned = pyo.SolverFactory("trustregion").solve(
                model, [model.z[0], model.z[1], model.z[2]], **{**TR_E1_CONFIG, **config}
            )
    finally:
        logger.removeHandler(handler)
        logger.setLevel(saved[0])
        logger.propagate = saved[1]
    exits = [line for line in captured.getvalue().splitlines() if line.startswith("EXIT:")]
    return returned, handler.iterations(), exits


def sequence(holder: Any) -> str:
    return "".join(
        ("F" if entry.served == "cold" else "f") if entry.call == "value" else "g"
        for entry in holder.ledger
    )


# -- G2: the pin ----------------------------------------------------------------------------------


def test_g2_the_audited_environment_is_the_pinned_framework() -> None:
    readiness = framework_readiness()
    assert readiness.status == "READY", readiness.as_document()


def test_g2_a_patched_version_string_is_unpinned_and_nothing_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pyomo.version

    from openflowsheet.studies.trust_region.trf import TrustRegionUnsupportedError, run_trf

    monkeypatch.setattr(pyomo.version, "version", "6.10.2")
    readiness = framework_readiness()
    assert (readiness.status, readiness.codes) == (
        "UNSUPPORTED",
        ("TRUST_REGION_FRAMEWORK_UNPINNED",),
    )
    projection = tr_e1_projection()
    with pytest.raises(TrustRegionUnsupportedError, match="TRUST_REGION_FRAMEWORK_UNPINNED"):
        run_trf(projection, TR_E1_CONFIG)
    assert all(holder.ledger == () for holder in projection.holders)


def test_g2_one_changed_module_byte_is_unpinned(tmp_path: Path) -> None:
    import importlib.util

    spec = importlib.util.find_spec(TRF_PACKAGE)
    assert spec is not None and spec.submodule_search_locations
    copy = tmp_path / "trustregion"
    shutil.copytree(next(iter(spec.submodule_search_locations)), copy)
    assert framework_readiness(module_dir=copy).status == "READY"
    module = copy / "TRF.py"
    data = bytearray(module.read_bytes())
    data[len(data) // 2] ^= 0x01
    module.write_bytes(bytes(data))
    readiness = framework_readiness(module_dir=copy)
    assert readiness.codes == ("TRUST_REGION_FRAMEWORK_UNPINNED",)
    assert len(readiness.reasons) == 1 and "TRF.py" in readiness.reasons[0].detail


# -- G3: TR-E1 against the native example ---------------------------------------------------------


def test_g3_tr_e1_reproduces_the_native_example(record_property: Any) -> None:
    import pyomo.environ as pyo

    reference, native_iterations, native_exits = native()
    projection, result = run()

    assert result.outcome == "TRF_CONVERGED", result.error
    assert result.exit_lines == (EXIT_OPTIMAL,) and native_exits == [EXIT_OPTIMAL]
    assert len(result.iterations) == len(native_iterations) == 5
    assert [r.step_type for r in result.iterations] == [r.step_type for r in native_iterations]
    assert [r.step_type for r in result.iterations] == [None, "theta", "theta", "theta", "theta"]

    model = result.model
    ours = {
        **{f"z{j}": pyo.value(model.d[j]) for j in range(3)},
        "x0": pyo.value(model.x[0]),
        "x1": pyo.value(model.x[1]),
        "objective": pyo.value(model.obj),
    }
    theirs = {
        **{f"z{j}": pyo.value(reference.z[j]) for j in range(3)},
        "x0": pyo.value(reference.x[0]),
        "x1": pyo.value(reference.x[1]),
        "objective": pyo.value(reference.obj),
    }
    worst = max(abs(ours[name] - theirs[name]) for name in theirs)
    record_property("M05.G3.max_abs_difference", worst)
    record_property("M05.G3.bitwise", all(ours[name] == theirs[name] for name in theirs))
    assert worst <= VALUE_TOLERANCE
    assert result.final.decisions == {name: ours[name] for name in TR_E1_DECISIONS}
    assert result.final.objective == result.iterations[-1].objective
    logged = max(
        abs(getattr(a, field) - getattr(b, field))
        for a, b in zip(result.iterations, native_iterations, strict=True)
        for field in ("theta", "objective", "radius", "step_norm")
    )
    record_property("M05.G3.max_logged_difference", logged)
    assert logged <= VALUE_TOLERANCE
    # Design note §4 P1 (plain `ipopt`, Ipopt's defaults) agrees at the subproblem tolerance.
    assert max(abs(ours[name] - PROBE_P1[name]) for name in PROBE_P1) <= 1e-8

    # The original holder saw TRF's calls (P2′): 6 distinct cold points, 4 gradient points.
    (holder,) = projection.holders
    summary = holder.summary()
    cold = [e for e in holder.ledger if e.call == "value" and e.served == "cold"]
    assert summary["value_cold"] == len({e.inputs_sha256 for e in cold}) == 6
    assert summary["jacobian_cold"] == 4
    assert sequence(holder) == RUN_SEQUENCE

    # §8.3's request identity, with an analytic gradient: start 1, PMP 1, trials K, gradients
    # 1 + A − [the final logged iteration was accepted].
    purposes = Counter(e.purpose for e in holder.ledger if e.purpose is not None)
    k = len(result.iterations) - 1
    accepted = sum(1 for r in result.iterations[1:] if r.step_type in ("f", "theta"))
    final_accepted = result.iterations[-1].step_type != "rejected"
    assert purposes == {TRF_START_VALUE: 1, TRF_PMP_VALUE: 1, TRF_TRIAL_VALUE: k}
    assert summary["jacobian_cold"] == 1 + accepted - int(final_accepted)
    assert [e.trf_iteration for e in cold] == [0, 0, 1, 2, 3, 4]

    # The source map's `trf` part: one holder variable for the one EF.
    assert result.trf_map == ({"holder": "trf_data.ef_outputs[1]", "ef": "ef_0"},)
    assert result.source_map(projection)["trf"] == [dict(result.trf_map[0])]
    assert result.filter == reconstruct_filter(result.iterations, 0.01, 0.01)
    native_filter = reconstruct_filter(native_iterations, 0.01, 0.01)
    assert len(result.filter) == len(native_filter) == 4
    for (f, theta), (native_f, native_theta) in zip(result.filter, native_filter, strict=True):
        assert abs(f - native_f) <= VALUE_TOLERANCE and abs(theta - native_theta) <= VALUE_TOLERANCE


def test_g3_every_trsp_option_is_echoed(tmp_path: Path) -> None:
    """`M05-trsp-ipopt-v1` reaches Ipopt: with `print_user_options` the executable lists every
    option it was given, with its value, and the banner names the audited build."""
    import pyomo.environ as pyo

    import openflowsheet.studies.trust_region.trf  # noqa: F401 - registers the alias

    model = pyo.ConcreteModel()
    model.a = pyo.Var(initialize=0.0, bounds=(-5.0, 5.0))
    model.b = pyo.Var(initialize=0.0)
    model.sum = pyo.Constraint(expr=model.a + model.b == 1.0)
    model.obj = pyo.Objective(expr=(model.a - 1.0) ** 2 + (model.b - 2.0) ** 2)
    model.scaling_factor = pyo.Suffix(direction=pyo.Suffix.EXPORT)
    solver = pyo.SolverFactory(TRSP_SOLVER_ALIAS)
    assert Path(solver.executable()) == trsp_executable()
    output = tmp_path / "trsp.out"
    solver.options.update(
        {"output_file": str(output), "file_print_level": 5, "print_user_options": "yes"}
    )
    results = solver.solve(model)
    assert pyo.check_optimal_termination(results)
    text = output.read_text(encoding="utf-8")
    assert "This is Ipopt version 3.14.20, running with linear solver MUMPS 5.8.2." in text
    listed = text.split("List of user-set options:")[1].split("*****")[0]
    echoed = {}
    for line in listed.splitlines():
        parts = line.split()
        if len(parts) == 4 and parts[1] == "=":
            assert parts[3] == "yes", line  # Ipopt used the option
            echoed[parts[0]] = parts[2]
    for name, value in TRSP_OPTIONS.items():
        assert name in echoed, name
        if isinstance(value, str):
            assert echoed[name] == value, (name, echoed[name])
        else:
            assert float(echoed[name]) == float(value), (name, echoed[name])


def test_p10_the_alias_runs_without_ipopt_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "/nonexistent")
    assert shutil.which("ipopt") is None
    _, result = run()
    assert result.outcome == "TRF_CONVERGED"


def test_p9_a_repeat_run_is_bitwise_identical() -> None:
    _, first = run()
    _, second = run()
    assert first.iterations == second.iterations
    assert first.final == second.final
    assert first.filter == second.filter


# -- the probe findings ---------------------------------------------------------------------------


def test_p2_prime_a_bound_method_callback_loses_trfs_calls_to_the_clone() -> None:
    """Why the holder returns itself from `__deepcopy__`: TRF clones the model, and a callback
    bound to an object without that hook is deep-copied with it."""
    import pyomo.environ as pyo
    from pyomo.contrib.trustregion.examples import example1

    class Plain:
        def __init__(self) -> None:
            self.calls = 0

        def value(self, a: float, b: float) -> float:
            self.calls += 1
            return math.sin(a - b)

        def gradient(self, args: list[float], fixed: Any) -> list[float]:
            self.calls += 1
            return [math.cos(args[0] - args[1]), -math.cos(args[0] - args[1])]

    plain = Plain()
    model = example1.create_model()
    model.del_component(model.c1)
    model.del_component(model.ext_fcn)
    model.ext_fcn = pyo.ExternalFunction(plain.value, plain.gradient)
    model.c1 = pyo.Constraint(
        expr=model.x[0] * model.z[0] ** 2 + model.ext_fcn(model.x[0], model.x[1])
        == 2 * math.sqrt(2.0)
    )
    _, iterations, exits = native(model)
    assert exits == [EXIT_OPTIMAL] and len(iterations) == 5
    assert plain.calls == 0


def test_p3_an_external_function_without_a_gradient_is_refused_by_trf() -> None:
    import pyomo.environ as pyo
    from pyomo.contrib.trustregion.examples import example1

    model = example1.create_model()
    model.del_component(model.c1)
    model.del_component(model.ext_fcn)
    model.ext_fcn = pyo.ExternalFunction(lambda a, b: math.sin(a - b))
    model.c1 = pyo.Constraint(
        expr=model.x[0] * model.z[0] ** 2 + model.ext_fcn(model.x[0], model.x[1])
        == 2 * math.sqrt(2.0)
    )
    with pytest.raises(RuntimeError, match="not defined with a gradient callback"):
        native(model)


class RefusingBlock(SineBlock):
    """Refuses (a `DomainError`) from its `refuse_from`-th value call on; call 1 is the
    projection's start value, which never goes through the holder."""

    def __init__(self, refuse_from: int) -> None:
        super().__init__()
        self.refuse_from = refuse_from

    def values(self, inputs: Any) -> Any:
        self.value_calls += 1
        if self.value_calls >= self.refuse_from:
            raise DomainError("outside the stated domain")
        return [math.sin(inputs[0] - inputs[1])]


def test_p6_a_refusal_aborts_the_run_typed_with_no_candidate() -> None:
    projection, result = run(RefusingBlock(refuse_from=5))
    assert result.outcome == "TRF_TRUTH_REFUSED(property_domain_error:bb)"
    assert (result.model, result.final, result.trf_map) == (None, None, ())
    assert result.refusal is not None and "outside the stated domain" in result.refusal.detail
    assert len(result.iterations) >= 1  # the log up to the refusal is kept
    (holder,) = projection.holders
    assert holder.ledger[-1].status == "property_domain_error:bb"


class OnceRefusingBlock(SineBlock):
    """Refuses (a `DomainError`) on its `refuse_on`-th value call only."""

    def __init__(self, refuse_on: int) -> None:
        super().__init__()
        self.refuse_on = refuse_on

    def values(self, inputs: Any) -> Any:
        self.value_calls += 1
        if self.value_calls == self.refuse_on:
            raise DomainError("outside the stated domain")
        return [math.sin(inputs[0] - inputs[1])]


def test_r276_a_refusal_at_the_start_is_caught_before_trf_runs() -> None:
    """The pre-flight: call 1 is the projection's start value (direct), call 2 the pre-flight's
    request at x₀, which refuses; TRF is never invoked — no log, no `EXIT:` line, one request."""
    block = OnceRefusingBlock(refuse_on=2)
    projection, result = run(block)
    assert result.outcome == "TRF_TRUTH_REFUSED(start:property_domain_error:bb)"
    assert (result.model, result.final, result.trf_map) == (None, None, ())
    assert (result.iterations, result.exit_lines, result.log) == ((), (), ())
    assert result.refusal is not None and result.refusal.code == "property_domain_error:bb"
    assert block.value_calls == 2
    (holder,) = projection.holders
    assert len(holder.ledger) == 1
    assert holder.ledger[0].purpose == TRF_START_VALUE
    assert holder.ledger[0].status == "property_domain_error:bb"


def test_r276_the_backstop_refuses_a_run_trf_called_optimal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The backstop, with the pre-flight bypassed: the same one-off refusal reaches Pyomo 6.10.1's
    `EFReplacement.exitNode`, whose bare `except:` swallows it and sets the holder variable to 0.
    TRF carries on and prints "EXIT: Optimal solution found." — and the run is still
    `TRF_TRUTH_REFUSED`, with no candidate."""
    from openflowsheet.studies.trust_region import trf

    monkeypatch.setattr(trf, "_preflight", lambda projection: None)
    projection, result = run(OnceRefusingBlock(refuse_on=2))
    assert result.exit_lines == (EXIT_OPTIMAL,)  # TRF's own account: optimal
    assert result.iterations  # TRF ran
    assert result.outcome == "TRF_TRUTH_REFUSED(property_domain_error:bb)"
    assert (result.model, result.final, result.trf_map) == (None, None, ())
    (holder,) = projection.holders
    assert holder.ledger[0].purpose == TRF_START_VALUE
    assert holder.ledger[0].status == "property_domain_error:bb"


class NanBlock(SineBlock):
    def __init__(self, poison_call: int) -> None:
        super().__init__()
        self.poison_call = poison_call

    def values(self, inputs: Any) -> Any:
        self.value_calls += 1
        return [
            math.nan if self.value_calls == self.poison_call else math.sin(inputs[0] - inputs[1])
        ]


def test_p7_a_nan_never_reaches_trf() -> None:
    projection, result = run(NanBlock(poison_call=4))
    assert result.outcome == "TRF_TRUTH_REFUSED(non_finite_output:block:bb)"
    assert result.model is None


def test_p7_native_trf_accepts_a_nan_silently() -> None:
    """The hazard the non-finite guard exists for, pinned: with a plain callback that returns NaN
    once, Pyomo 6.10.1's TRF neither raises nor refuses."""
    import pyomo.environ as pyo
    from pyomo.contrib.trustregion.examples import example1

    calls = {"n": 0}

    def value(a: float, b: float) -> float:
        calls["n"] += 1
        return math.nan if calls["n"] == 4 else math.sin(a - b)

    def gradient(args: list[float], fixed: Any) -> list[float]:
        return [math.cos(args[0] - args[1]), -math.cos(args[0] - args[1])]

    model = example1.create_model()
    model.del_component(model.c1)
    model.del_component(model.ext_fcn)
    model.ext_fcn = pyo.ExternalFunction(value, gradient)
    model.c1 = pyo.Constraint(
        expr=model.x[0] * model.z[0] ** 2 + model.ext_fcn(model.x[0], model.x[1])
        == 2 * math.sqrt(2.0)
    )
    returned, _, exits = native(model)
    assert returned is not None and exits == [EXIT_OPTIMAL]


def test_p8_cyipopt_cannot_be_the_subproblem_solver() -> None:
    _, result = run(config={"solver": "cyipopt"})
    assert result.outcome == "TRF_ERROR(ValueError)"
    assert "keepfiles" in result.error


def test_g7_mechanism_a_budget_is_never_exceeded_through_a_run() -> None:
    cap = ColdBudget("run", 3)
    projection, result = run(budgets={"block:bb": [cap]})
    assert result.outcome == "TRF_TRUTH_REFUSED(budget:budget_exhausted)"
    (holder,) = projection.holders
    assert holder.summary()["value_cold"] == cap.used == 3
    assert [r.code for r in holder.refusals] == ["budget:budget_exhausted"]


def test_the_omitted_rows_are_recorded_at_trf_s_final_state() -> None:
    """R-274's fact 4, wired: a run that returns a model records the omitted rows there."""
    from m05_support import at_projection

    from openflowsheet.studies.trust_region.trf import run_trf

    projection = at_projection()
    result = run_trf(projection, TR_E1_CONFIG)
    assert result.outcome == "TRF_CONVERGED", result.error
    assert result.final is not None and abs(result.final.decisions["z"] - 31.0 / 30.0) <= 1e-6
    check = result.omitted_rows_final
    assert check is not None and check.status == "pass"
    assert list(check.residuals) == ["r3"] and abs(check.residuals["r3"]) <= 1e-2


def test_one_trf_run_per_process() -> None:
    from openflowsheet.studies.trust_region import trf

    with trf._RUN_LOCK, pytest.raises(RuntimeError, match="one TRF run per process"):
        trf.run_trf(tr_e1_projection(), TR_E1_CONFIG)


def test_the_logger_is_restored_after_a_run() -> None:
    logger = logging.getLogger(TRF_PACKAGE)
    before = (logger.level, logger.propagate, list(logger.handlers))
    run()
    assert (logger.level, logger.propagate, list(logger.handlers)) == before
    assert sys.stdout is sys.__stdout__ or not isinstance(sys.stdout, io.StringIO)
