"""T02 §3–§4: the execution plan, the solver-choice rule, and NEST-1's tear set.

The plan is structural (T02 design invariant 2): a function of the declaration, the parameters, the
unit manifests and the policy. So these tests build it with every evaluator made to raise, and
compare it with `ref.syn001.plans`, which Fable's generator registers from the specification's rule.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from openflowsheet.application.binding import structural_inputs
from openflowsheet.compiled import EvaluationContext
from openflowsheet.graph.analysis import analyse
from openflowsheet.graph.process import Connection, ProcessGraph
from openflowsheet.graph.tear import Candidate
from openflowsheet.graph.trace import trace_declaration
from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
from openflowsheet.orchestrator.execution import (
    ExecutionPlan,
    build_execution_plan,
    condensation_order,
    declaration_identity,
    eo_capability,
    iterated_tear_set,
)
from openflowsheet.orchestrator.trace import RecyclePolicy, SolvePolicy
from openflowsheet.thermo.syn001 import Syn001Provider

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "schemas"
BASE = "https://github.com/frankp/process-runtime/schemas/"


@pytest.fixture(scope="module")
def ref() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(
        (REPO_ROOT / "benchmarks" / "t02" / "reference_values.yaml").read_text()
    )
    return loaded


@pytest.fixture(scope="module")
def validators() -> dict[str, Draft202012Validator]:
    documents = [json.loads(path.read_text()) for path in SCHEMA_DIR.glob("*.schema.json")]
    registry = Registry().with_resources(
        (document["$id"], Resource.from_contents(document)) for document in documents
    )
    by_id = {document["$id"]: document for document in documents}
    return {
        name: Draft202012Validator(by_id[BASE + name], registry=registry)
        for name in ("execution-plan.schema.json", "solve-plan.schema.json")
    }


def variants() -> dict[str, Mapping[str, Any]]:
    return {
        entry["case_id"]: entry
        for entry in yaml.safe_load(
            (REPO_ROOT / "benchmarks" / "syn001" / "reference_values.yaml").read_text()
        )["variants"]
    }


def plan_for(
    case_id: str,
    method: str = "auto",
    manifests: Mapping[str, Mapping[str, Any]] | None = None,
) -> ExecutionPlan:
    entry = variants()[case_id]
    flowsheet = Syn001Flowsheet(
        provider=Syn001Provider(),
        context=EvaluationContext(
            model_version="t02", constants_sha256="0" * 64, phase_signature=None
        ),
        split_fraction=float(entry["r"]),
        flash_temperature=float(entry["T_flash_K"]),
        heater_temperature=float(entry["T_heater_K"]),
        pressure=float(entry["P_Pa"]),
    )
    spec, graph, row_units = structural_inputs(flowsheet)
    model_version, constants = declaration_identity(spec)
    declaration = trace_declaration(
        spec, row_units=row_units, model_version=model_version, constants_sha256=constants
    )
    report = analyse(
        spec, graph, row_units=row_units, model_version=model_version, constants_sha256=constants
    )
    policy = SolvePolicy(
        policy_id="T02",
        residual_tolerances={},
        scales={},
        recycle=RecyclePolicy(method=method),  # type: ignore[arg-type]
    )
    return build_execution_plan(
        spec=spec,
        declaration=declaration,
        graph=graph,
        report=report,
        manifests=manifests
        if manifests is not None
        else {unit.unit_id: unit.manifest() for unit in flowsheet.units()},
        policy=policy,
    )


def summary(plan: ExecutionPlan) -> list[dict[str, Any]]:
    """The plan in the registered summary shape of `ref.syn001.plans`."""
    out: list[dict[str, Any]] = []
    for step in plan.steps:
        if step.kind == "evaluate":
            out.append({"kind": "evaluate", "unit": step.units[0]})
        elif step.kind == "converge":
            assert step.solve_plan is not None
            out.append(
                {
                    "kind": "converge",
                    "loop": list(step.units),
                    "tear_stream": step.tear_streams[0] if len(step.tear_streams) == 1 else None,
                    "tear_variable_ids": list(step.solve_plan.tear_variable_ids),
                    "tear_row_ids": list(step.solve_plan.tear_row_ids),
                    "method": step.method,
                    "signature_units": list(step.solve_plan.signature_units),
                }
            )
        else:
            assert step.region is not None
            out.append(
                {
                    "kind": "solve_eo",
                    "region_units": list(step.units),
                    "specification_rows": list(step.region.specification_rows),
                    "square": len(step.region.variable_ids),
                    "signature_units": list(step.region.signature_units),
                }
            )
    return out


def strip(registered: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: value for key, value in step.items() if key != "note"} for step in registered]


# --------------------------------------------------------------------------- A01: plan shape


@pytest.mark.parametrize(
    "case_id",
    [
        "SYN-001-nominal",
        "SYN-001-once-through",
        "SYN-001-high-recycle",
        "SYN-001-all-liquid-310K",
        "SYN-001-all-vapor-420K",
    ],
)
def test_a01_the_plan_equals_the_registered_plan(
    ref: dict[str, Any], validators: dict[str, Draft202012Validator], case_id: str
) -> None:
    """`[evaluate U-FEED, converge {U-MIX, U-HEAT, U-FLASH, U-SPLIT} tear S6]` at every variant —
    the once-through one included, because the declared pattern does not fold at r = 0 (T01)."""
    plan = plan_for(case_id)
    assert summary(plan) == strip(ref["syn001"]["plans"]["SYN-001-nominal (tear)"])
    errors = list(validators["execution-plan.schema.json"].iter_errors(plan.as_document()))
    assert errors == [], [error.message for error in errors[:3]]
    for step in plan.steps:
        if step.solve_plan is not None:
            assert not list(
                validators["solve-plan.schema.json"].iter_errors(step.solve_plan.as_document())
            )


def test_a01_the_eo_override_promotes_the_loop_to_one_region(
    ref: dict[str, Any], validators: dict[str, Draft202012Validator]
) -> None:
    """T02 §6.1: 44 rows minus 2 certified over 47 − 5 columns — a 42 × 42 region whose
    signature holds both lifted units, because in a region every lifted block is solved."""
    plan = plan_for("SYN-001-nominal", method="eo")
    assert summary(plan) == strip(ref["syn001"]["plans"]["SYN-001-nominal (eo override)"])
    step = plan.steps[1]
    assert step.solve_plan is not None and step.region is not None
    assert step.solve_plan.tear_variable_ids == () == step.solve_plan.tear_row_ids
    assert len(step.region.row_ids) == len(step.region.variable_ids) == 42
    assert [record.row_id for record in step.solve_plan.eliminated_rows] == [
        "U-FLASH:FLASH-P:inlet",
        "U-SPLIT:SPLIT-P:recycle",
    ]
    assert not list(validators["execution-plan.schema.json"].iter_errors(plan.as_document()))


def test_a01_building_the_plan_evaluates_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """No residual, Jacobian or property call; and the structural analysis is read, not rerun.

    K03's own `build_plan` evaluates a Jacobian to estimate its non-zeros, which is why the plan
    builds its `SolvePlan`s from the declaration instead.
    """
    import openflowsheet.compile.casadi_backend as backend
    import openflowsheet.graph.analysis as analysis
    import openflowsheet.orchestrator.execution as execution
    from openflowsheet.thermo.syn001 import Syn001Provider as Provider

    entry = variants()["SYN-001-nominal"]
    flowsheet = Syn001Flowsheet(
        provider=Syn001Provider(),
        context=EvaluationContext(
            model_version="t02", constants_sha256="0" * 64, phase_signature=None
        ),
        split_fraction=float(entry["r"]),
    )
    spec, graph, row_units = structural_inputs(flowsheet)
    model_version, constants = declaration_identity(spec)
    declaration = trace_declaration(
        spec, row_units=row_units, model_version=model_version, constants_sha256=constants
    )
    report = analyse(
        spec, graph, row_units=row_units, model_version=model_version, constants_sha256=constants
    )

    def refuse(*arguments: object, **keywords: object) -> Any:
        raise AssertionError("the plan builder evaluated or re-analysed something")

    monkeypatch.setattr(backend, "compile_problem", refuse)
    monkeypatch.setattr(Provider, "flash", refuse)
    monkeypatch.setattr(Provider, "evaluate_phase", refuse)
    monkeypatch.setattr(analysis, "analyse", refuse)
    monkeypatch.setattr(analysis, "analyse_declaration", refuse)
    assert not hasattr(execution, "analyse"), "the builder imports no analysis to rerun"

    plan = build_execution_plan(
        spec=spec,
        declaration=declaration,
        graph=graph,
        report=report,
        manifests={unit.unit_id: unit.manifest() for unit in flowsheet.units()},
        policy=SolvePolicy(policy_id="T02", residual_tolerances={}, scales={}),
    )
    assert [step.kind for step in plan.steps] == ["evaluate", "converge"]


# --------------------------------------------------------------------- A03: solver choice


def test_a03_auto_resolves_from_the_manifests() -> None:
    """Every SYN-001 unit with rows declares `residuals / free_variables / ad`, so `auto` is
    Newton on the tear; one unit declaring `unavailable` turns it to Anderson, and the merge edge
    then has nothing to merge into (T02 §4.2, §4.4)."""
    plan = plan_for("SYN-001-nominal")
    loop = plan.steps[1]
    assert loop.method == "newton_tear"
    assert loop.region_on_merge is not None and loop.merge_unsupported is None

    entry = variants()["SYN-001-nominal"]
    flowsheet = Syn001Flowsheet(
        provider=Syn001Provider(),
        context=EvaluationContext(
            model_version="t02", constants_sha256="0" * 64, phase_signature=None
        ),
        split_fraction=float(entry["r"]),
    )
    manifests = {unit.unit_id: dict(unit.manifest()) for unit in flowsheet.units()}
    manifests["U-HEAT"]["derivatives"] = [
        {**item, "method": "unavailable"} if item["output"] == "residuals" else item
        for item in manifests["U-HEAT"]["derivatives"]
    ]
    assert eo_capability(manifests["U-HEAT"]) == (False, "unavailable")

    doubled = plan_for("SYN-001-nominal", manifests=manifests).steps[1]
    assert doubled.method == "anderson"
    assert doubled.region_on_merge is None
    assert doubled.merge_unsupported == ("U-HEAT", "unavailable")
    assert doubled.as_document()["merge_unsupported"] == {"unit": "U-HEAT", "method": "unavailable"}


def test_a03_explicit_methods_are_honoured_and_never_recorded_as_auto() -> None:
    assert plan_for("SYN-001-nominal", method="anderson").steps[1].method == "anderson"
    assert plan_for("SYN-001-nominal", method="newton_tear").steps[1].method == "newton_tear"
    assert "auto" not in json.dumps(plan_for("SYN-001-nominal").as_document()["steps"])


def test_a03_tear_rows_and_columns_have_equal_scales() -> None:
    """The recycle iterates `x̂ = t / S_t` and `f̂ = R / S_t` (T02 §5.1), which is only the scaled
    residual if each tear row's scale equals its tear variable's — asserted, not assumed."""
    plan = plan_for("SYN-001-nominal")
    solve_plan = plan.steps[1].solve_plan
    assert solve_plan is not None
    for variable, row in zip(solve_plan.tear_variable_ids, solve_plan.tear_row_ids, strict=True):
        assert solve_plan.column_scales[variable] == solve_plan.row_scales[row]


# ------------------------------------------------------------------ NEST-1: the tear set


def nest_graph() -> ProcessGraph:
    connections = (
        Connection("s0", "FEED", "A", ("s0.x",)),
        Connection("s1", "A", "B", ("s1.x",)),
        Connection("s2", "B", "C", ("s2.x",)),
        Connection("s3", "C", "PRODUCT", ("s3.x",)),
        Connection("s4", "B", "A", ("s4.x",)),
        Connection("s5", "C", "B", ("s5.x",)),
    )
    return ProcessGraph(
        units=("FEED", "A", "B", "C", "PRODUCT"), connections=connections, instance_ids={}
    )


def test_a18_nest_1_is_torn_by_iterating_t01s_rule(ref: dict[str, Any]) -> None:
    """A loop no single edge breaks: round 1 takes s4 (least boundary distance), what is left is
    the {B, C} loop, round 2 takes s5. One simultaneous tear vector, never a loop inside a loop."""
    from openflowsheet.graph.tear import _boundary_distances

    registered = ref["cases_auxiliary"]["NEST-1"]["tear"]
    graph = nest_graph()
    distances = _boundary_distances(graph)
    candidates = [
        Candidate(
            stream_id=connection.stream_id,
            producer=connection.producer,
            consumer=connection.consumer,
            breaks_loop=False,
            torn_variables=connection.state_columns,
            not_torn=(),
            consumer_boundary_distance=distances[connection.consumer],
        )
        for connection in graph.connections
        if connection.stream_id in {"s1", "s2", "s4", "s5"}
    ]
    assert condensation_order(graph) == (("FEED",), ("A", "B", "C"), ("PRODUCT",))
    streams, rounds = iterated_tear_set(graph, ("A", "B", "C"), candidates)
    assert list(streams) == registered["tear_streams"] == ["s4", "s5"]
    assert [round_.chosen for round_ in rounds] == [
        entry["chosen"] for entry in registered["rounds"]
    ]
    assert [list(round_.cycle_edges) for round_ in rounds] == [
        entry["cycle_edges"] for entry in registered["rounds"]
    ]
    assert {
        stream: distances[consumer]
        for stream, consumer in (("s1", "B"), ("s2", "C"), ("s4", "A"), ("s5", "B"))
    } == {"s1": 2, "s2": 3, "s4": 1, "s5": 2}


# ------------------------------------------ NEST-1 through the plan builder; review M2


def nest_structure() -> tuple[Any, ProcessGraph, Any, Any]:
    """NEST-1 as a declaration: the linear scalar flowsheet of `ref.cases_auxiliary.NEST-1.units`
    (feed 1, split 0.5, recycle 0.8), one row per stream a unit produces. Written by the T02
    manifest generator's author, who found the builder could not plan it (tear rows were
    collected against every torn variable, so `B:s2`, which reads the torn `s5.x`, was one)."""
    from dataclasses import replace

    from openflowsheet.compile.spec import EquationSpec, ProblemSpec

    # Each stream's state belongs to its producer (the ownership SYN-001's binding declares).
    graph = replace(
        nest_graph(),
        column_owners={
            column: connection.producer
            for connection in nest_graph().connections
            for column in connection.state_columns
        },
    )

    def row(equation_id: str, residual: Any) -> EquationSpec:
        return EquationSpec(
            equation_id, lambda v, b, p, a: residual({**v, **p}), "algebraic", origin="NEST-1"
        )

    equations = (
        row("FEED:s0", lambda v: v["s0.x"] - v["FEED.f"]),
        row("A:s1", lambda v: v["s1.x"] - v["s0.x"] - v["s4.x"]),
        row("B:s4", lambda v: v["s4.x"] - 0.5 * (v["s1.x"] + v["s5.x"])),
        row("B:s2", lambda v: v["s2.x"] - 0.5 * (v["s1.x"] + v["s5.x"])),
        row("C:s5", lambda v: v["s5.x"] - 0.8 * v["s2.x"]),
        row("C:s3", lambda v: v["s3.x"] - 0.2 * v["s2.x"]),
    )
    columns = ("s0.x", "s1.x", "s2.x", "s3.x", "s4.x", "s5.x")
    spec = ProblemSpec(
        label="NEST-1",
        variable_ids=columns,
        equations=equations,
        parameter_ids=("FEED.f",),
        parameters={"FEED.f": 1.0},
        variable_kinds=dict.fromkeys(columns, "molar_flow"),
        row_kinds={equation.equation_id: "molar_flow" for equation in equations},
    )
    row_units = {equation.equation_id: equation.equation_id.split(":")[0] for equation in equations}
    model_version, constants = declaration_identity(spec)
    identity: dict[str, Any] = {
        "row_units": row_units,
        "model_version": model_version,
        "constants_sha256": constants,
    }
    return spec, graph, trace_declaration(spec, **identity), analyse(spec, graph, **identity)


CAPABLE = {
    "derivatives": [{"output": "residuals", "with_respect_to": ["free_variables"], "method": "ad"}]
}


def nest_plan(
    method: str = "auto",
    tear_streams: tuple[str, ...] | None = None,
    manifests: Mapping[str, Any] | None = None,
) -> ExecutionPlan:
    spec, graph, declaration, report = nest_structure()
    return build_execution_plan(
        spec=spec,
        declaration=declaration,
        graph=graph,
        report=report,
        manifests=manifests if manifests is not None else dict.fromkeys(graph.units, CAPABLE),
        policy=SolvePolicy(
            policy_id="T02",
            residual_tolerances={},
            scales={},
            recycle=RecyclePolicy(method=method, tear_streams=tear_streams),  # type: ignore[arg-type]
        ),
    )


def test_a01_nest_1_plans_one_simultaneous_tear_vector(ref: dict[str, Any]) -> None:
    """`[evaluate FEED, converge {A, B, C} tear [s4, s5]]`: one tear row per torn stream, each its
    producer's row defining it — never `B:s2`, which only reads `s5.x`."""
    plan = nest_plan()
    assert [step.kind for step in plan.steps] == ["evaluate", "converge"]
    converge = plan.steps[1]
    assert set(converge.units) == {"A", "B", "C"}
    assert converge.tear_streams == tuple(ref["cases_auxiliary"]["NEST-1"]["tear"]["tear_streams"])
    assert converge.solve_plan is not None
    assert converge.solve_plan.tear_variable_ids == ("s4.x", "s5.x")
    assert converge.solve_plan.tear_row_ids == ("B:s4", "C:s5")
    assert len(converge.solve_plan.inner_row_ids) == len(converge.solve_plan.inner_variable_ids)


def test_a03_nest_1_solver_choice() -> None:
    assert nest_plan().steps[1].method == "newton_tear"
    _, graph, _, _ = nest_structure()
    manifests = {**dict.fromkeys(graph.units, CAPABLE), "B": {"derivatives": []}}
    assert nest_plan(manifests=manifests).steps[1].method == "anderson"


def test_m2_an_override_is_derived_through_the_candidates() -> None:
    """NEST-1's registered alternate tear `{s1, s5}`: the plan tears exactly those streams."""
    converge = nest_plan(tear_streams=("s1", "s5")).steps[1]
    assert converge.tear_streams == ("s1", "s5")
    assert converge.solve_plan is not None
    assert converge.solve_plan.tear_variable_ids == ("s1.x", "s5.x")
    assert converge.solve_plan.tear_row_ids == ("A:s1", "C:s5")


def test_m2_an_override_that_is_not_a_cycle_edge_or_leaves_a_cycle_is_refused() -> None:
    from openflowsheet.orchestrator.execution import UnsupportedRankStructureError

    with pytest.raises(UnsupportedRankStructureError, match="not cycle edges"):
        nest_plan(tear_streams=("s0",))
    with pytest.raises(UnsupportedRankStructureError, match="cyclic"):
        nest_plan(tear_streams=("s4",))
    with pytest.raises(UnsupportedRankStructureError, match="not cycle edges"):
        plan_for_override(("S1",))


def plan_for_override(streams: tuple[str, ...]) -> ExecutionPlan:
    entry = variants()["SYN-001-nominal"]
    flowsheet = Syn001Flowsheet(
        provider=Syn001Provider(),
        context=EvaluationContext(
            model_version="t02", constants_sha256="0" * 64, phase_signature=None
        ),
        split_fraction=float(entry["r"]),
    )
    spec, graph, row_units = structural_inputs(flowsheet)
    model_version, constants = declaration_identity(spec)
    declaration = trace_declaration(
        spec, row_units=row_units, model_version=model_version, constants_sha256=constants
    )
    report = analyse(
        spec, graph, row_units=row_units, model_version=model_version, constants_sha256=constants
    )
    return build_execution_plan(
        spec=spec,
        declaration=declaration,
        graph=graph,
        report=report,
        manifests={unit.unit_id: unit.manifest() for unit in flowsheet.units()},
        policy=SolvePolicy(
            policy_id="T02",
            residual_tolerances={},
            scales={},
            recycle=RecyclePolicy(tear_streams=streams),
        ),
    )


def test_m2_a_syn001_override_that_k03s_form_cannot_take_is_refused_by_name() -> None:
    """`S3` is a cycle edge, but the heater's rows touching `S3.n` outnumber the three torn flows
    (its energy balance and lifted split read them too): a typed refusal at plan time, where
    before the fix the plan said `S3` and tore `S6`."""
    from openflowsheet.orchestrator.execution import UnsupportedRankStructureError

    with pytest.raises(UnsupportedRankStructureError, match=r"tearing \['S3'\]"):
        plan_for_override(("S3",))
    converge = plan_for_override(("S6",)).steps[1]
    assert converge.solve_plan is not None
    assert converge.solve_plan.tear_variable_ids == ("S6.n.A", "S6.n.B", "S6.n.C")


def test_s1_an_eo_loop_region_obeys_the_capability_rule() -> None:
    """Review S1: `method: eo` with the heater's residual derivative `unavailable` is refused at
    plan construction, naming the heater, as a specification region is (§7.4)."""
    from openflowsheet.orchestrator.execution import CapabilityUnavailableError

    flowsheet = Syn001Flowsheet(
        provider=Syn001Provider(),
        context=EvaluationContext(
            model_version="t02", constants_sha256="0" * 64, phase_signature=None
        ),
    )
    manifests = {unit.unit_id: unit.manifest() for unit in flowsheet.units()}
    heater = dict(manifests["U-HEAT"])
    heater["derivatives"] = [
        {**entry, "method": "unavailable"} if entry["output"] == "residuals" else entry
        for entry in heater["derivatives"]
    ]
    manifests["U-HEAT"] = heater
    with pytest.raises(CapabilityUnavailableError) as refused:
        plan_for("SYN-001-nominal", method="eo", manifests=manifests)
    assert refused.value.unit == "U-HEAT" and refused.value.method == "unavailable"
