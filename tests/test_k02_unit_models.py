"""K02 unit models: the declaration, the rows, and the causal evaluator.

Three things are checked here and they are deliberately independent of one another.

**The declaration.** P01 wrote six `ModelManifest` documents stating what each model would do;
K02 re-states them in Python and implements them. The two transcriptions are compared field by
field, so neither can drift. This only has teeth because they *are* two transcriptions: the code
does not load the YAML, and the YAML is not generated from the code.

**The rows.** ADR 0008 D4.3 names K02's obligation and fixes two values exactly. A row is
evaluated directly on floats through `compile.reference` — going through a compile, a dense
assembly and a CSC extraction to check `+0.5` would be testing the compiler instead. The rows are
*also* compiled and the two routes compared, which checks the adapter's wiring and nothing about
the equations, since both call the same `build`.

**The evaluator.** Zero flow, exactness, and the malformed problems that must be refused at
construction rather than travel as a status.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from conftest import REPO_ROOT, load_yaml, sha256_of
from test_schemas_p01 import schema_errors

from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compile.reference import row_values, row_vector, state_vector
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import (
    SpecificationError,
    UnitEvaluation,
    Wiring,
    assemble,
    flow_id,
    origin,
    pressure_id,
    row_id,
    stream_variables,
    temperature_id,
)
from openflowsheet.models.syn001 import COMPONENTS
from openflowsheet.models.syn001.feed import FeedSource
from openflowsheet.models.syn001.flash import TPFlash
from openflowsheet.models.syn001.heater import TPHeater
from openflowsheet.models.syn001.mixer import AdiabaticMixer
from openflowsheet.models.syn001.sink import ProductSink
from openflowsheet.models.syn001.splitter import StreamSplitter
from openflowsheet.thermo import StreamState
from openflowsheet.thermo.syn001 import Syn001Provider

DECLARED_DIR = REPO_ROOT / "tests" / "fixtures" / "schemas" / "model_manifest" / "valid"

FEED = FeedSource(unit_id="U-FEED", flows=(1.0, 1.0, 1.0), temperature=300.0, pressure=100_000.0)
SPLITTER = StreamSplitter(unit_id="U-SPLIT", split_fraction=0.5)
SINK = ProductSink(unit_id="U-PURGE")

#: A provider-free unit ignores its context; it is still required, so a caller never has to know
#: which units hold a provider. The pins are the ones a unit evaluator has no compiled problem to
#: take them from.
CONTEXT = EvaluationContext(
    model_version="K02-unit-evaluator@" + "0" * 64, constants_sha256="0" * 64
)

HEATER = TPHeater(
    unit_id="U-HEAT", provider=Syn001Provider(), outlet_temperature=350.0, context=CONTEXT
)
MIXER = AdiabaticMixer(unit_id="U-MIX", provider=Syn001Provider(), context=CONTEXT)
FLASH = TPFlash(
    unit_id="U-FLASH",
    provider=Syn001Provider(),
    temperature=360.0,
    pressure=100_000.0,
    context=CONTEXT,
)

#: Every model implemented so far, paired with the P01 document that declared it.
IMPLEMENTED: tuple[tuple[Any, str], ...] = (
    (FEED, "feed.yaml"),
    (SPLITTER, "splitter.yaml"),
    (SINK, "sink.yaml"),
    (HEATER, "heater.yaml"),
    (FLASH, "flash.yaml"),
    (MIXER, "mixer.yaml"),
)

UNIT_IDS = [unit.model_id for unit, _ in IMPLEMENTED]


def declared_manifest(filename: str) -> dict[str, Any]:
    loaded = load_yaml(DECLARED_DIR / filename)
    assert isinstance(loaded, dict)
    return loaded


def by_id(unit_model: object) -> str:
    return str(unit_model.model_id)  # type: ignore[attr-defined]


# ------------------------------------------------------------------------------- declaration


@pytest.mark.parametrize(("unit", "filename"), IMPLEMENTED, ids=UNIT_IDS)
def test_implemented_manifest_validates_against_the_frozen_schema(unit: Any, filename: str) -> None:
    assert schema_errors("model_manifest", dict(unit.manifest())) == []


@pytest.mark.parametrize(("unit", "filename"), IMPLEMENTED, ids=UNIT_IDS)
def test_ports_match_the_p01_declaration_exactly(unit: Any, filename: str) -> None:
    """A port set is the model's interface; an added or renamed port is a different model."""
    assert dict(unit.manifest())["ports"] == declared_manifest(filename)["ports"]


@pytest.mark.parametrize(("unit", "filename"), IMPLEMENTED, ids=UNIT_IDS)
def test_equations_match_the_p01_declaration_exactly(unit: Any, filename: str) -> None:
    """Id, statement, dependencies, conditional class, dimension and accumulation, in order.

    ADR 0008 D3.5's table is normative, so a changed accumulation kind here is not a refactor.
    """
    implemented = dict(unit.manifest())["mathematics"]["equations"]
    declared = declared_manifest(filename)["mathematics"]["equations"]
    assert implemented == declared


@pytest.mark.parametrize(("unit", "filename"), IMPLEMENTED, ids=UNIT_IDS)
def test_identity_domain_and_execution_class_are_unchanged(unit: Any, filename: str) -> None:
    implemented = dict(unit.manifest())
    declared = declared_manifest(filename)
    assert implemented["id"] == declared["id"]
    assert implemented["title"] == declared["title"]
    assert implemented["description"] == declared["description"]
    assert implemented["introduced_by_package"] == declared["introduced_by_package"]
    assert implemented["validity"]["domain"] == declared["validity"]["domain"]
    for key in ("execution_class", "property_provider", "reference_convention"):
        assert implemented["execution_requirements"][key] == declared["execution_requirements"][key]
    assert implemented["initialization"]["strategy"] == declared["initialization"]["strategy"]
    assert (
        implemented["initialization"]["registered_initializer"]
        == declared["initialization"]["registered_initializer"]
    )


@pytest.mark.parametrize(("unit", "filename"), IMPLEMENTED, ids=UNIT_IDS)
def test_declared_limitations_survive_implementation(unit: Any, filename: str) -> None:
    """An implementation may discover a further limitation. It may not quietly drop one."""
    implemented = set(dict(unit.manifest())["validity"]["limitations"])
    declared = set(declared_manifest(filename)["validity"]["limitations"])
    assert declared <= implemented


@pytest.mark.parametrize(("unit", "filename"), IMPLEMENTED, ids=UNIT_IDS)
def test_declared_derivatives_are_not_silently_upgraded(unit: Any, filename: str) -> None:
    """Every P01 `(output, wrt, method)` triple is still there with the same method.

    P01 declared everything `unavailable`. K02 implements the models but still exposes no
    sensitivity interface, so those entries stay `unavailable`; upgrading one to `analytic`
    because the arithmetic happens to be simple would be a capability claim nothing can honour.
    """
    implemented = {
        (entry["output"], tuple(entry["with_respect_to"]), entry["method"])
        for entry in dict(unit.manifest())["derivatives"]
    }
    declared = {
        (entry["output"], tuple(entry["with_respect_to"]), entry["method"])
        for entry in declared_manifest(filename)["derivatives"]
    }
    assert declared <= implemented


@pytest.mark.parametrize(("unit", "filename"), IMPLEMENTED, ids=UNIT_IDS)
def test_status_and_artifact_record_that_code_now_exists(unit: Any, filename: str) -> None:
    declared = declared_manifest(filename)
    assert declared["status"] == "declared"
    assert declared["implementation_artifact"]["state"] == "not_implemented"

    implemented = dict(unit.manifest())
    # `tested`, not `reviewed`: the gate exercises every one of these against Fable's
    # independent 20-digit references at every registered variant, and human sign-off is
    # recorded separately and is not an agent's to claim.
    assert implemented["status"] == "tested"
    artifact = implemented["implementation_artifact"]
    assert artifact["state"] == "source"
    assert artifact["module"] is not None


@pytest.mark.parametrize(("unit", "filename"), IMPLEMENTED, ids=UNIT_IDS)
def test_artifact_hash_is_the_named_module(unit: Any, filename: str) -> None:
    """The document's claim about which code it describes is recomputed, not trusted."""
    artifact = dict(unit.manifest())["implementation_artifact"]
    module_path = Path(*artifact["module"].split(".")).with_suffix(".py")
    on_disk = REPO_ROOT / "src" / module_path
    assert on_disk.is_file(), on_disk
    assert artifact["artifact_hash"] == sha256_of(on_disk)


def test_a_manifest_cannot_be_written_as_reviewed_or_released() -> None:
    """CLAUDE.md: human sign-off is recorded separately and no agent may claim it."""
    from openflowsheet.models import Initialization, Validity, manifest_document

    for status in ("reviewed", "released"):
        with pytest.raises(ValueError, match="human"):
            manifest_document(
                model_id="syn001.feed_source",
                title="t",
                description="d",
                ports=FEED.ports(),
                equations=FEED.declared_equations(),
                derivatives=(),
                initialization=Initialization(strategy="none", notes="n"),
                validity=Validity(components=COMPONENTS, phases=("liquid",), limitations=()),
                module="m",
                artifact_hash="0" * 64,
                execution_class="native_equation",
                thread_safety="thread_safe",
                evaluation_cost_class="cheap",
                property_provider="syn001",
                reference_convention="SYN-001-ref-v1",
                status=status,  # type: ignore[arg-type]
            )


def test_the_residual_route_is_declared_where_rows_exist() -> None:
    """A model that contributes rows says so; the sink, which contributes none, does not."""
    for unit, _ in IMPLEMENTED:
        methods = {
            (entry["output"], entry["method"]) for entry in dict(unit.manifest())["derivatives"]
        }
        has_rows = bool(unit.declared_equations())
        assert (("residuals", "ad") in methods) is has_rows, unit.model_id


# ------------------------------------------------------------------------------------- wiring

STREAMS = ("S5", "S6", "S7")
WIRING = {
    "U-FEED": Wiring({"outlet": ("S5",)}),
    "U-SPLIT": Wiring({"inlet": ("S5",), "recycle": ("S6",), "purge": ("S7",)}),
    "U-PURGE": Wiring({"inlet": ("S7",)}),
}


def build_spec(splitter: StreamSplitter = SPLITTER) -> Any:
    return assemble(
        label="K02-M1-feed-split-sink",
        units=[FEED, splitter, SINK],
        wiring=WIRING,
        streams=STREAMS,
        components=COMPONENTS,
    )


def test_stream_variable_order_is_flows_then_temperature_then_pressure() -> None:
    """Written out, not derived from the helper under test: a permutation must be visible."""
    assert stream_variables("S5", COMPONENTS) == ("S5.n.A", "S5.n.B", "S5.n.C", "S5.T", "S5.P")


def test_assembled_spec_validates_and_has_the_expected_shape() -> None:
    spec = build_spec()
    spec.validate()
    # Three streams of five variables each; no unit owns a variable of its own here.
    assert spec.variable_ids == (
        "S5.n.A", "S5.n.B", "S5.n.C", "S5.T", "S5.P",
        "S6.n.A", "S6.n.B", "S6.n.C", "S6.T", "S6.P",
        "S7.n.A", "S7.n.B", "S7.n.C", "S7.T", "S7.P",
    )  # fmt: skip
    # feed 3 + 2, splitter 3 + 3 + 2 + 2, sink 0.
    assert len(spec.equations) == 5 + 10


#: The units in `build_spec`. Row integrity is a property of an assembled spec, so it is checked
#: against the units that are actually in one, not against every model that exists.
M1_UNITS = (FEED, SPLITTER, SINK)


def test_every_row_traces_back_to_a_declared_equation() -> None:
    """ADR 0008 D4.4 needs a row to name the manifest equation that authored it."""
    declared = {
        origin(unit.model_id, equation.equation_id)
        for unit in M1_UNITS
        for equation in unit.declared_equations()
    }
    produced = {equation.origin for equation in build_spec().equations}
    assert produced <= declared
    assert produced == declared, "a declared unconditional equation authored no row"


def test_row_accumulation_matches_the_declaration_row_by_row() -> None:
    kinds = {
        origin(unit.model_id, equation.equation_id): equation.accumulation.kind
        for unit in M1_UNITS
        for equation in unit.declared_equations()
    }
    for equation in build_spec().equations:
        assert equation.accumulation == kinds[equation.origin], equation.equation_id


# --------------------------------------------------------------------------------- feed rows


def test_feed_rows_are_the_specification_residual() -> None:
    spec = build_spec()
    state = {name: 0.0 for name in spec.variable_ids}
    state[flow_id("S5", "A")] = 1.0
    state[flow_id("S5", "B")] = 0.25
    state[temperature_id("S5")] = 300.0
    state[pressure_id("S5")] = 100_000.0
    rows = row_values(spec, state)
    assert rows[row_id("U-FEED", "FEED-n", "A")] == 0.0
    assert rows[row_id("U-FEED", "FEED-n", "B")] == -0.75
    assert rows[row_id("U-FEED", "FEED-n", "C")] == -1.0
    assert rows[row_id("U-FEED", "FEED-T")] == 0.0
    assert rows[row_id("U-FEED", "FEED-P")] == 0.0


def test_feed_specification_reaches_the_pinned_inputs_not_the_rows() -> None:
    """The specified values are pinned inputs (ADR 0008 D1.3), hashed by `constants_sha256`."""
    spec = build_spec()
    assert spec.parameters["U-FEED.n_spec.A"] == 1.0
    assert spec.parameters["U-FEED.T_spec"] == 300.0
    assert set(spec.parameter_ids) == set(spec.parameters)


# ----------------------------------------------------------------------------- splitter rows


def test_split_rows_are_exact_at_the_registered_fractions() -> None:
    spec = build_spec()
    state = {name: 0.0 for name in spec.variable_ids}
    state[flow_id("S5", "A")] = 4.0
    state[flow_id("S6", "A")] = 2.0
    state[flow_id("S7", "A")] = 2.0
    rows = row_values(spec, state)
    assert rows[row_id("U-SPLIT", "SPLIT-recycle", "A")] == 0.0
    assert rows[row_id("U-SPLIT", "SPLIT-purge", "A")] == 0.0


def test_split_row_signs_follow_the_declared_statement() -> None:
    """`n_rec - r n_in`: too much in the recycle is positive, not negative."""
    spec = build_spec()
    state = {name: 0.0 for name in spec.variable_ids}
    state[flow_id("S5", "A")] = 4.0
    state[flow_id("S6", "A")] = 3.0
    rows = row_values(spec, state)
    assert rows[row_id("U-SPLIT", "SPLIT-recycle", "A")] == pytest.approx(1.0, abs=0.0)


def test_temperature_and_pressure_rows_exist_for_both_outlets() -> None:
    spec = build_spec()
    state = {name: 0.0 for name in spec.variable_ids}
    state[temperature_id("S5")] = 360.0
    state[temperature_id("S6")] = 360.0
    state[temperature_id("S7")] = 350.0
    rows = row_values(spec, state)
    assert rows[row_id("U-SPLIT", "SPLIT-T", "recycle")] == 0.0
    assert rows[row_id("U-SPLIT", "SPLIT-T", "purge")] == -10.0
    assert row_id("U-SPLIT", "SPLIT-P", "recycle") in rows
    assert row_id("U-SPLIT", "SPLIT-P", "purge") in rows


# --------------------------------------------------------------------- compiled vs reference


def test_compiled_rows_agree_with_the_float_route() -> None:
    """Checks the adapter's wiring. Both routes call the same `build`, so it checks nothing else."""
    spec = build_spec()
    problem = compile_problem(spec)
    metadata = problem.metadata
    context = EvaluationContext(
        model_version=metadata.model_version, constants_sha256=metadata.constants_sha256
    )
    rng = np.random.default_rng(20260919)
    for _ in range(4):
        state = {
            name: float(value)
            for name, value in zip(spec.variable_ids, rng.uniform(0.5, 400.0, 15), strict=True)
        }
        result = problem.residual(np.array(state_vector(spec, state)), context)
        assert result.status == "ok"
        assert result.values is not None
        assert result.equation_ids == spec.equation_ids
        expected = row_vector(spec, state)
        rows = zip(result.equation_ids, result.values, expected, strict=True)
        for equation_id, got, want in rows:
            assert got == pytest.approx(want, rel=0.0, abs=1e-12), equation_id


def test_compiled_jacobian_of_a_split_row_is_the_declared_fraction() -> None:
    """dSPLIT-recycle:A/dS5.n.A = -r exactly. Written out by hand, not read from the code."""
    spec = build_spec()
    problem = compile_problem(spec)
    metadata = problem.metadata
    context = EvaluationContext(
        model_version=metadata.model_version, constants_sha256=metadata.constants_sha256
    )
    state = np.full(len(spec.variable_ids), 1.0)
    result = problem.jacobian(state, context)
    entries: dict[tuple[str, str], float] = {}
    for column, col_id in enumerate(result.col_ids):
        for offset in range(result.indptr[column], result.indptr[column + 1]):
            entries[(result.row_ids[result.indices[offset]], col_id)] = result.data[offset]
    assert entries[(row_id("U-SPLIT", "SPLIT-recycle", "A"), flow_id("S5", "A"))] == -0.5
    assert entries[(row_id("U-SPLIT", "SPLIT-recycle", "A"), flow_id("S6", "A"))] == 1.0
    assert entries[(row_id("U-SPLIT", "SPLIT-purge", "A"), flow_id("S5", "A"))] == -0.5


# ------------------------------------------------------------------------------- evaluators


def test_feed_emits_the_specification_and_claims_no_phase() -> None:
    result = FEED.evaluate({}, CONTEXT)
    assert result.status == "ok"
    outlet = result.outlets["outlet"]
    assert outlet.n == (1.0, 1.0, 1.0)
    assert outlet.temperature == 300.0
    assert outlet.pressure == 100_000.0
    assert result.duty is None
    assert result.phase_signature is None, (
        "the manifest says this model does not verify the liquid claim, so it may not report it"
    )


def test_a_dormant_feed_is_zero_flow_without_any_thermodynamics() -> None:
    dormant = FeedSource(
        unit_id="U-ZERO", flows=(0.0, 0.0, 0.0), temperature=360.0, pressure=100_000.0
    )
    result = dormant.evaluate({}, CONTEXT)
    assert result.phase_signature == "ZERO_FLOW"
    assert result.outlets["outlet"].is_dormant


def test_splitter_is_exact_at_r_zero_and_at_a_dormant_inlet() -> None:
    feed = StreamState(n=(1.0, 2.0, 3.0), temperature=360.0, pressure=100_000.0)
    once_through = StreamSplitter(unit_id="U-SPLIT", split_fraction=0.0)
    result = once_through.evaluate({"inlet": (feed,)}, CONTEXT)
    assert result.outlets["recycle"].n == (0.0, 0.0, 0.0)
    assert result.outlets["recycle"].is_dormant
    assert result.outlets["purge"].n == (1.0, 2.0, 3.0)

    dormant = StreamState(n=(0.0, 0.0, 0.0), temperature=360.0, pressure=100_000.0)
    both = SPLITTER.evaluate({"inlet": (dormant,)}, CONTEXT)
    assert both.phase_signature == "ZERO_FLOW"
    assert both.outlets["recycle"].is_dormant
    assert both.outlets["purge"].is_dormant


def test_splitter_carries_temperature_and_pressure_through_unchanged() -> None:
    feed = StreamState(n=(1.0, 2.0, 3.0), temperature=347.44118198144020, pressure=123_456.0)
    result = SPLITTER.evaluate({"inlet": (feed,)}, CONTEXT)
    for outlet in result.outlets.values():
        assert outlet.temperature == feed.temperature
        assert outlet.pressure == feed.pressure


@pytest.mark.parametrize("fraction", [0.0, 0.5, 0.95])
def test_split_closure_is_exact_at_every_registered_recycle_ratio(fraction: float) -> None:
    """r = 0, 0.5 and 0.95 are the registered variants and all three close to the last bit."""
    feed = StreamState(n=(1.0, 1.0, 1.0), temperature=360.0, pressure=100_000.0)
    result = StreamSplitter(unit_id="U-SPLIT", split_fraction=fraction).evaluate(
        {"inlet": (feed,)}, CONTEXT
    )
    assert result.outlets["recycle"].n[0] + result.outlets["purge"].n[0] == 1.0


def test_split_closure_rounds_where_the_complement_is_not_representable() -> None:
    """Documented, not hidden: the evaluator uses `(1 - r)` because `SPLIT-purge` does.

    Rewriting the purge as `n_in - n_rec` would close this to the last bit at every r and would
    make the evaluator a different function from the row. The measured witness is r = 0.3 at
    3 mol/s; the registered variants above are exact by luck, not by construction.
    """
    feed = StreamState(n=(3.0, 3.0, 3.0), temperature=360.0, pressure=100_000.0)
    result = StreamSplitter(unit_id="U-SPLIT", split_fraction=0.3).evaluate(
        {"inlet": (feed,)}, CONTEXT
    )
    total = result.outlets["recycle"].n[0] + result.outlets["purge"].n[0]
    assert total == 2.9999999999999996
    assert total != 3.0
    # Comfortably inside the registered component-balance tolerance (ADR 0001 D6).
    assert abs(total - 3.0) < 1e-9 + 1e-8 * 3.0


def test_splitter_normalizes_a_negative_zero_it_is_handed() -> None:
    """ADR 0001 D1.5. `-0.0 * 0.5` is `-0.0`, and a stored `-0.0` would make two physically
    identical states hash differently."""
    feed = StreamState(n=(-0.0, 1.0, 1.0), temperature=360.0, pressure=100_000.0)
    result = SPLITTER.evaluate({"inlet": (feed,)}, CONTEXT)
    for outlet in result.outlets.values():
        assert math.copysign(1.0, outlet.n[0]) == 1.0


def test_assembly_refuses_two_units_binding_one_pinned_input_differently() -> None:
    clashing = FeedSource(
        unit_id="U-FEED", flows=(2.0, 2.0, 2.0), temperature=300.0, pressure=100_000.0
    )
    with pytest.raises(SpecificationError, match="different values"):
        assemble(
            label="clash",
            units=[FEED, clashing],
            wiring={"U-FEED": Wiring({"outlet": ("S5",)})},
            streams=STREAMS,
            components=COMPONENTS,
        )


def test_sink_contributes_nothing_and_still_reports_a_dormant_inlet() -> None:
    dormant = StreamState(n=(0.0, 0.0, 0.0), temperature=360.0, pressure=100_000.0)
    result = SINK.evaluate({"inlet": (dormant,)}, CONTEXT)
    assert result.status == "ok"
    assert result.outlets == {}
    assert result.duty is None
    assert result.phase_signature == "ZERO_FLOW"
    assert SINK.contribute(WIRING["U-PURGE"], COMPONENTS).equations == ()


# ---------------------------------------------------------------- malformed, not a bad status


def test_split_fraction_one_is_rejected_at_construction() -> None:
    with pytest.raises(SpecificationError, match="steady state"):
        StreamSplitter(unit_id="U-SPLIT", split_fraction=1.0)


@pytest.mark.parametrize("fraction", [-0.1, 1.5, float("nan"), float("inf")])
def test_split_fraction_outside_the_admissible_range_is_rejected(fraction: float) -> None:
    with pytest.raises(SpecificationError):
        StreamSplitter(unit_id="U-SPLIT", split_fraction=fraction)


def test_a_negative_feed_specification_is_rejected() -> None:
    with pytest.raises(SpecificationError, match="negative"):
        FeedSource(unit_id="U-BAD", flows=(1.0, -1.0, 1.0), temperature=300.0, pressure=100_000.0)


def test_a_splitter_wired_to_two_inlets_is_refused() -> None:
    with pytest.raises(SpecificationError, match="exactly one stream"):
        SPLITTER.contribute(
            Wiring({"inlet": ("S5", "S4"), "recycle": ("S6",), "purge": ("S7",)}), COMPONENTS
        )


def test_a_failed_evaluation_may_not_carry_an_answer() -> None:
    with pytest.raises(ValueError, match="failed evaluation"):
        UnitEvaluation(
            status="not_converged",
            outlets={"outlet": StreamState(n=(1.0,), temperature=300.0, pressure=1e5)},
        )


def test_assembly_refuses_a_unit_with_no_wiring() -> None:
    with pytest.raises(SpecificationError, match="no wiring"):
        assemble(
            label="broken",
            units=[FEED],
            wiring={},
            streams=STREAMS,
            components=COMPONENTS,
        )


# ------------------------------------------------------------------ one place for a row shape


UNIT_MODULES = sorted(
    path
    for path in (REPO_ROOT / "src" / "openflowsheet" / "models" / "syn001").glob("*.py")
    if path.name not in ("__init__.py",)
)


def test_no_unit_module_defines_a_row_builder_of_its_own() -> None:
    """Every row shape lives in `models/rows.py`, and nowhere else.

    The Fable review of K02 found a heater equilibrium row that was never evaluated at a state
    where it could fail, while its near-identical twin in the flash was — so a reader comparing
    the two saw agreement and moved on. Six builders were duplicated across two to three modules
    at the time. They are consolidated now, and this keeps them that way: a builder is a function
    returning a `RowBuilder`, and there is one place to look for one and one place to test it.
    """
    import ast

    offenders: list[str] = []
    for path in UNIT_MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            # A row builder is a module-level function whose body returns an inner `build`.
            returns_build = any(
                isinstance(inner, ast.Return)
                and isinstance(inner.value, ast.Name)
                and inner.value.id == "build"
                for inner in node.body
            )
            if returns_build:
                offenders.append(f"{path.name}:{node.name}")
    assert offenders == [], (
        f"row builders outside models/rows.py: {offenders}. A shape defined twice is a shape "
        "with two places to test and one of them will be missed."
    )


def test_every_shared_row_shape_is_actually_used() -> None:
    """A builder nothing calls is a shape nothing tests. Guards the other direction."""
    import ast

    from openflowsheet.models import rows

    exported = set(rows.__all__)
    used: set[str] = set()
    for path in (*UNIT_MODULES, REPO_ROOT / "src/openflowsheet/models/rows.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                used.add(node.func.id)
    assert exported <= used, f"unused row shapes: {sorted(exported - used)}"
