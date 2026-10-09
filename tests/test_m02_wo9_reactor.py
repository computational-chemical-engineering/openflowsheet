"""M02 WO-9: the embedded C1 reactor, its builders and verifier entries, the C1 loop case
`C1-LOOP-M02-v1`, G7 (f) and G8 (e) (design note §4.1, §8.1, §10.1, §14.3 C1; ADR 0034 D1, D9;
register R-231, R-280).

- §4.1: `c1.reactor` and `c1.reactor_standin` are one embedded unit, extent-fixed at the pinned
  coupling parameters `<U>.coupling.X` and `<U>.coupling.dT`; it never calls the external model.
  The traversal start satisfies its linear rows to the last bit.
- The builders are in `MODEL_BUILDERS` since R-280's join, on the C1 basis only (R-288).
- The verifier's entries: the material rule on its own copy of the C1 reaction, SYN-001's reactor
  energy rule, both ports declared vapour; the reaction envelope and the external duty.
- `C1-LOOP-M02-v1` (`benchmarks/m02/c1-loop-standin.json`, registered here): its inner solve at
  fixed w converges from `traversal-G0-v1` and verifies, at the variant's initial w and at the
  stand-in's fixed point w* = (0.25, 0 K), which is the stand-in loop's solution.
- G7 (f): the scaled Jacobian's `rcond_1` at that solution is ≥ 10 τ_ill (recorded).
- G8 (e): replaces M01.A49's binder clause (R-231; test_m01_reactor_boundary.py); since the join
  the stand-in is in `MODEL_BUILDERS` and the v0.2 envelope lists it as synthetic only.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from conftest import REPO_ROOT
from m02_c1_support import (
    DIMENSIONLESS,
    connection,
    feed_specifications,
    instance,
    revision,
)
from m02_wo8_support import POLICY
from test_schemas_p01 import validator_for

from openflowsheet.adapters import variants
from openflowsheet.adapters.experiments.runner import ExperimentRunner
from openflowsheet.adapters.experiments.store import ExperimentStore, ListArtifactSink
from openflowsheet.application.revision_binding import (
    MODEL_BASES,
    MODEL_BUILDERS,
    MODEL_SIGNATURES,
    RevisionBinding,
    Unbound,
    bind_revision_flowsheet,
)
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.c1 import NU
from openflowsheet.models.c1.reactor import MODEL_IDS, C1Reactor
from openflowsheet.orchestrator.executor import PlanResult, execute_plan
from openflowsheet.orchestrator.revision import INITIALIZER_ID, plan_revision, traversal_start
from openflowsheet.thermo import PropertyRequest, StreamState
from openflowsheet.thermo.pr_c1 import COMPONENTS, PrC1Provider
from openflowsheet.verify import pr_c1
from openflowsheet.verify.certificate import SolutionCertificate, verify_revision
from openflowsheet.verify.regularity import TAU_ILL
from openflowsheet.verify.table import (
    EXTERNAL_DUTY_MODELS,
    MODEL_CHECKS,
    REACTING_MODELS,
    _c1_reactor_material,
    _reactor_energy,
)

LOOP_PATH: Path = REPO_ROOT / "benchmarks" / "m02" / "c1-loop-standin.json"
STANDIN = variants.registered_variant("standin-x025-v1")
REAL = variants.registered_variant("pymrm-6089593-g2-nz800-s123-v2")
#: ADR 0034 D10's nominal per-tube flow: the real variant bounds it to [0.5, 2] × F_nom.
F_NOM = 2.0 * variants.hard_domain(REAL).tube_flow[0]  # type: ignore[index]
PROVIDER = PrC1Provider()
CONTEXT = EvaluationContext(model_version="m02-wo9", constants_sha256="0" * 64)
P = 1.0e7
#: The stand-in's fixed point: its map is constant, F(w) = (0.25, 0 K) (design note §4.3).
W_STAR = (0.25, 0.0)


def loop() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(LOOP_PATH.read_text(encoding="utf-8"))
    return document


def _quantity(value: float) -> dict[str, Any]:
    return {
        "value": value,
        "unit": "1",
        "dimension": list(DIMENSIONLESS),
        "kind": "dimensionless",
        "meaning": "test",
        "role": "fixed",
    }


def _reactor(
    model: str = "c1.reactor_standin", parameters: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    variant = STANDIN if model == "c1.reactor_standin" else REAL
    return instance(
        "R",
        model,
        {"n_tubes": _quantity(1000.0)} if parameters is None else parameters,
        version=variant.variant_id,
        artifact_ref=variant.sha256,
    )


def reactor_revision(
    n: tuple[float, ...], temperature: float = 673.15, **reactor: Any
) -> dict[str, Any]:
    """F → R → K: a feed fully specified at `(n, T, 1e7 Pa)` into the reactor, its outlet a sink."""
    return revision(
        [instance("F", "c1.feed_source"), _reactor(**reactor), instance("K", "c1.product_sink")],
        [
            connection("S1", ("F", "outlet"), ("R", "inlet")),
            connection("S2", ("R", "outlet"), ("K", "inlet")),
        ],
        feed_specifications("S1", n, temperature, P),
    )


def bound(document: Mapping[str, Any]) -> RevisionBinding:
    binding = bind_revision_flowsheet(document)
    assert isinstance(binding, RevisionBinding), binding
    return binding


def at_coupling(binding: RevisionBinding, unit: str, w: tuple[float, float]) -> RevisionBinding:
    """The same binding with `unit`'s coupling parameters at `w` (test support: the coupled
    route's own re-binding is WO-10's)."""
    flowsheet = binding.flowsheet
    units = tuple(
        replace(model, conversion=w[0], temperature_rise=w[1]) if model.unit_id == unit else model
        for model in flowsheet.instances
    )
    rebuilt = replace(flowsheet, instances=units)
    return replace(binding, flowsheet=rebuilt, spec=rebuilt.spec())


def solved(binding: RevisionBinding) -> tuple[Any, PlanResult]:
    plan, report = plan_revision(binding, POLICY)
    run = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=POLICY)
    return plan, run


def certify(
    binding: RevisionBinding, document: Mapping[str, Any], plan: Any, run: PlanResult
) -> SolutionCertificate:
    assert run.outcome == "CONVERGED", run.message
    return verify_revision(binding, document, run, solve_plan=plan.steps[-1].solve_plan)


def unit_of(binding: RevisionBinding, unit: str) -> Any:
    (found,) = (model for model in binding.flowsheet.instances if model.unit_id == unit)
    return found


def _rows(binding: RevisionBinding, state: Mapping[str, float]) -> dict[str, float]:
    compiled = compile_problem(binding.spec)
    context = EvaluationContext(
        model_version=compiled.metadata.model_version,
        constants_sha256=compiled.metadata.constants_sha256,
    )
    x = np.array([state[name] for name in binding.spec.variable_ids], dtype=np.float64)
    result = compiled.residual(x, context)
    assert result.status == "ok" and result.values is not None
    return dict(zip(result.equation_ids, result.values, strict=True))


def _flows(state: Mapping[str, float], stream: str) -> tuple[float, ...]:
    return tuple(state[f"{stream}.n.{c}"] for c in COMPONENTS)


#: M01's nominal reactor inlet composition, at the loop's scale (H2/N2 = 3, inerts 7 %).
NOMINAL = (2.79, 0.93, 0.11, 0.1, 0.15)


# == the case ======================================================================================


def test_the_loop_case_is_registered_as_section_8_1_states_it() -> None:
    document = loop()
    assert [e.message for e in validator_for("process_revision").iter_errors(document)] == []
    assert document["revision_id"] == "C1-LOOP-M02-v1"
    models = {entry["id"]: entry["model"] for entry in document["instances"]}
    assert {unit: model["id"] for unit, model in models.items()} == {
        "makeup": "c1.feed_source",
        "mixer": "c1.adiabatic_mixer",
        "preheater": "c1.tp_heater",
        "reactor": "c1.reactor_standin",
        "flash": "c1.tp_flash",
        "splitter": "c1.stream_splitter",
        "NH3": "c1.product_sink",
        "purge": "c1.product_sink",
    }
    assert models["reactor"]["version"] == "standin-x025-v1"
    assert models["reactor"]["artifact_ref"] == STANDIN.sha256
    parameters = {entry["id"]: entry["parameters"] for entry in document["instances"]}
    assert parameters["reactor"]["n_tubes"]["value"] == 1000.0
    assert parameters["splitter"]["split_fraction"]["value"] == 0.98  # purge fraction 0.02
    pins = {
        (s["target"]["object_id"], s["target"]["path"], s["target"].get("component")): s["value"]
        for s in document["specifications"]
    }
    makeup = tuple(pins[("S1", "state.n", c)] for c in COMPONENTS)
    assert makeup == (0.74625, 0.24875, 0.0, 0.002, 0.003)
    assert sum(makeup) == 1.0 and makeup[0] / makeup[1] == 3.0
    assert (pins[("S1", "state.T", None)], pins[("S1", "state.P", None)]) == (300.0, P)
    assert pins[("S3", "state.T", None)] == 673.15
    for product in ("S5", "S6"):
        assert (pins[(product, "state.T", None)], pins[(product, "state.P", None)]) == (253.15, P)
    assert len(pins) == 12  # nothing else is pinned: zero pressure drop everywhere
    edges = {
        entry["id"]: (entry["from"]["instance"], entry["to"]["instance"])
        for entry in document["connections"]
    }
    assert edges == {
        "S1": ("makeup", "mixer"),
        "S8": ("splitter", "mixer"),
        "S2": ("mixer", "preheater"),
        "S3": ("preheater", "reactor"),
        "S4": ("reactor", "flash"),
        "S5": ("flash", "splitter"),
        "S6": ("flash", "NH3"),
        "S7": ("splitter", "purge"),
    }


# == the unit (§4.1) ===============================================================================


def test_the_embedded_rows_and_pinned_parameters_are_section_4_1s() -> None:
    binding = bound(loop())
    reactor = unit_of(binding, "reactor")
    assert isinstance(reactor, C1Reactor) and reactor.model_id == "c1.reactor_standin"
    contribution = reactor.contribute(binding.flowsheet.wiring["reactor"], COMPONENTS)
    assert contribution.variable_ids == ("reactor.xi", "reactor.Q")
    assert dict(contribution.variable_kinds) == {
        "reactor.xi": "molar_flow",
        "reactor.Q": "heat_rate",
    }
    assert dict(contribution.row_kinds) == {
        **{f"reactor:C1RX-mole:{c}": "molar_flow" for c in COMPONENTS},
        "reactor:C1RX-extent": "molar_flow",
        "reactor:C1RX-temperature": "temperature",
        "reactor:C1RX-pressure": "pressure",
        "reactor:C1RX-duty": "heat_rate",
    }
    initial = STANDIN.coupling["initial"]
    assert dict(contribution.parameters) == {
        **{f"reactor.nu.{c}": float(nu) for c, nu in zip(COMPONENTS, NU, strict=True)},
        "reactor.coupling.X": float(initial["X"]),
        "reactor.coupling.dT": float(initial["dT_K"]),
    }
    # In `constants_sha256` (the compiled problem's parameters); N_tubes is not (no row reads it).
    assert {name: binding.spec.parameters[name] for name in contribution.parameters} == dict(
        contribution.parameters
    )
    assert reactor.n_tubes == 1000.0
    assert not any("n_tubes" in name for name in binding.spec.parameters)
    assert [block.block_id for block in contribution.blocks] == ["S3_Hdot_V", "S4_Hdot_V"]


def test_the_traversal_start_satisfies_the_rows_to_the_last_bit() -> None:
    """§4.1: the causal evaluate is formed in the rows' arithmetic order, so at the traversal
    start every linear row is exactly 0.0; the duty row is its enthalpies' roundoff. The solve
    then converges with no Newton iteration and verifies."""
    for w in ((0.15, 80.0), W_STAR, (0.3, 17.25)):
        binding = at_coupling(bound(reactor_revision(NOMINAL)), "R", w)
        start = traversal_start(binding.flowsheet, binding.spec.variable_ids)
        state = start.values  # type: ignore[union-attr]
        rows = _rows(binding, state)
        for name, value in rows.items():
            if name.startswith("R:") and name != "R:C1RX-duty":
                assert value == 0.0, (w, name, value)
        # Q = Ḣ_out − Ḣ_in, so the row Q + Ḣ_in − Ḣ_out is the roundoff of that difference:
        # measured 0, +0.25 and −0.25 ulp of Ḣ_in (3.0e4 W); asserted within one ulp.
        h_in = (
            sum(NOMINAL)
            * PROVIDER.evaluate_phase(
                PropertyRequest(
                    state=StreamState(n=NOMINAL, temperature=673.15, pressure=P),
                    phase="VAPOR",
                    properties=("h",),
                ),
                CONTEXT,
            ).values["h"]
        )
        assert abs(rows["R:C1RX-duty"]) <= np.spacing(max(abs(h_in), abs(state["R.Q"])))
        assert state["R.xi"] == w[0] * NOMINAL[1] / 1.0
        assert state["S2.T"] == 673.15 + w[1]
        document = reactor_revision(NOMINAL)
        plan, run = solved(binding)
        certificate = certify(binding, document, plan, run)
        assert certificate.verification_status == "VERIFIED", certificate.limitations


def test_a_dormant_inlet_gives_zero_extent_and_zero_duty_exactly() -> None:
    binding = bound(reactor_revision((0.0,) * 5))
    reactor = unit_of(binding, "R")
    feed = StreamState(n=(0.0,) * 5, temperature=673.15, pressure=P)
    answer = reactor.evaluate({"inlet": (feed,)}, CONTEXT)
    assert answer.status == "ok" and answer.phase_signature == "ZERO_FLOW"
    assert (answer.extent, answer.duty) == (0.0, 0.0)
    assert np.copysign(1.0, answer.extent) == 1.0 and np.copysign(1.0, answer.duty) == 1.0
    outlet = answer.outlets["outlet"]
    assert outlet.n == (0.0,) * 5 and outlet.temperature == 673.15 + 80.0
    plan, run = solved(binding)
    certificate = certify(binding, reactor_revision((0.0,) * 5), plan, run)
    assert run.state is not None and run.state["R.Q"] == 0.0 and run.state["R.xi"] == 0.0
    assert certificate.verification_status == "VERIFIED", certificate.limitations


def test_the_evaluate_refuses_a_two_phase_inlet() -> None:
    """§14.2 B16, as for the C1 heater: a flowing inlet that is not VAPOR is refused."""
    reactor = unit_of(bound(reactor_revision(NOMINAL)), "R")
    wet = StreamState(n=(0.6, 0.2, 0.2, 0.015, 0.02), temperature=253.15, pressure=P)
    answer = reactor.evaluate({"inlet": (wet,)}, CONTEXT)
    assert answer.status == "unsupported"
    assert answer.message.startswith("vapour_phase_inadmissible: inlet: liquid NH3 fraction")


@pytest.mark.parametrize("model", MODEL_IDS)
def test_each_manifest_is_valid_and_states_the_embedding(model: str) -> None:
    manifest = unit_of(bound(reactor_revision(NOMINAL, model=model)), "R").manifest()
    assert [e.message for e in validator_for("model_manifest").iter_errors(manifest)] == []
    assert manifest["id"] == model and manifest["introduced_by_package"] == "M02"
    assert manifest["derivatives"] == [
        {
            "output": "residuals",
            "with_respect_to": ["free_variables"],
            "method": "analytic",
            "regime": "all",
            "notes": (
                "the embedded rows at pinned coupling parameters (ADR 0034); exact for those rows"
            ),
        },
        {
            "output": "outlet.state",
            "with_respect_to": ["inlet.state"],
            "method": "unavailable",
            "regime": "all",
            "notes": "the external map; no sensitivity through this unit (ADR 0034 D4)",
        },
    ]
    limitations = manifest["validity"]["limitations"]
    assert any("never call the external model" in text for text in limitations)
    domain = manifest["validity"]["domain"]
    assert (domain["temperature_K"], domain["pressure_Pa"]) == (
        {"min": 573.15, "max": 773.15},
        {"min": 5.0e6, "max": 1.5e7},
    )
    if model == "c1.reactor":
        assert manifest["execution_requirements"]["execution_class"] == "experiment_provider"
        assert manifest["execution_requirements"]["evaluation_cost_class"] == "expensive"
        assert not any("SYNTHETIC" in text for text in (*limitations, manifest["description"]))
        assert any(text.startswith("Discretization at the design grid") for text in limitations)
        assert any("xi high by 1.4-1.9 %" in text for text in limitations)
        assert any(text.startswith("F-R2:") for text in limitations)
        assert any(text.startswith("F-R3:") for text in limitations)
        assert any("extrapolated" in text for text in limitations)
    else:
        assert manifest["execution_requirements"]["execution_class"] == "explicit_reduced"
        assert manifest["execution_requirements"]["evaluation_cost_class"] == "cheap"


# == the builders (R-280's join) ==================================================================


def test_the_two_builders_are_in_the_shared_registry() -> None:
    for model in MODEL_IDS:
        assert model in MODEL_BUILDERS and model in MODEL_SIGNATURES
        assert MODEL_BASES[model] == {"pr-c1-v1"}
        assert MODEL_SIGNATURES[model].required == ("n_tubes",)


def test_the_real_reactor_binds_at_its_variants_initial_coupling() -> None:
    """Binding executes nothing: the embedded unit never calls the external model."""
    reactor = unit_of(bound(reactor_revision(NOMINAL, model="c1.reactor")), "R")
    assert reactor.model_id == "c1.reactor" and not reactor.synthetic
    initial = REAL.coupling["initial"]
    assert (reactor.conversion, reactor.temperature_rise) == (initial["X"], initial["dT_K"])


@pytest.mark.parametrize(
    ("parameters", "expected"),
    [
        ({}, ("incomplete", "parameter_missing(R.n_tubes)")),
        (
            {"n_tubes": _quantity(1000.0), "coupling_initial.X": _quantity(0.2)},
            ("unsupported", "parameter_unsupported(R.coupling_initial.X)"),
        ),
    ],
)
def test_the_builder_reads_n_tubes_and_nothing_else(
    parameters: dict[str, Any], expected: tuple[str, str]
) -> None:
    """R6's parameter rule: `n_tubes` required; an optional `coupling_initial.*` is not admitted
    (build log D46: the frozen signature document has no optional-parameter slot)."""
    refused = bind_revision_flowsheet(reactor_revision(NOMINAL, parameters=parameters))
    assert isinstance(refused, Unbound)
    assert (refused.kind, refused.detail) == expected


def test_a_nonpositive_n_tubes_is_outside_the_models_domain() -> None:
    refused = bind_revision_flowsheet(
        reactor_revision(NOMINAL, parameters={"n_tubes": _quantity(0.0)})
    )
    assert isinstance(refused, Unbound)
    assert refused.kind == "inadmissible" and refused.detail.startswith(
        "value_outside_model_domain"
    )
    assert refused.implicated == ("R",)


# == the verifier's entries =======================================================================


def test_the_verifier_entries_read_the_c1_reaction() -> None:
    for model in MODEL_IDS:
        entry = MODEL_CHECKS[model]
        assert (entry.material, entry.energy, entry.specification, entry.bounds) == (
            _c1_reactor_material,
            _reactor_energy,
            MODEL_CHECKS["c1.product_sink"].specification,
            MODEL_CHECKS["c1.product_sink"].bounds,
        )
        assert entry.declared_ports == (("inlet", False), ("outlet", False))
        assert model in REACTING_MODELS and model in EXTERNAL_DUTY_MODELS
    # The verifier's own copy of N2 + 3 H2 -> 2 NH3 equals the model's, as data.
    assert tuple(pr_c1.REACTION_NU[c] for c in COMPONENTS) == tuple(float(v) for v in NU)
    assert pr_c1.REACTOR_MODELS == frozenset(MODEL_IDS)


# == the loop: WO-9's acceptance and G7 (f) =======================================================


def test_the_loop_at_the_variants_initial_coupling_converges_from_traversal_and_verifies() -> None:
    """WO-9's acceptance at w0 = the stand-in variant's `coupling.initial` (0.15, 80 K): the
    inner solve converges from `traversal-G0-v1` and verifies."""
    document = loop()
    binding = bound(document)
    reactor = unit_of(binding, "reactor")
    assert (reactor.conversion, reactor.temperature_rise) == (0.15, 80.0)
    plan, run = solved(binding)
    certificate = certify(binding, document, plan, run)
    assert certificate.branch_provenance[0]["initializer_source"] == INITIALIZER_ID
    assert INITIALIZER_ID == "traversal-G0-v1"
    assert certificate.verification_status == "VERIFIED", certificate.limitations
    assert run.state is not None and run.state["S4.T"] == 673.15 + 80.0


def test_g7f_the_stand_in_loops_solution_is_well_conditioned() -> None:
    """G7 (f): at the stand-in loop's solution — the inner solve at w* = (0.25, 0 K), the
    stand-in's constant map, so ρ = 0 there — the scaled Jacobian's `rcond_1` ≥ 10 τ_ill.
    Recorded (design note §8.1, §14.3 C3): `rcond_1` 1.424e-4, the flash's L/n_tot 0.128, the
    reactor inlet inside the hard and the data domain, per-tube flow 0.576 F_nom."""
    document = loop()
    binding = at_coupling(bound(document), "reactor", W_STAR)
    plan, run = solved(binding)
    certificate = certify(binding, document, plan, run)
    assert certificate.branch_provenance[0]["initializer_source"] == INITIALIZER_ID
    assert certificate.verification_status == "VERIFIED", certificate.limitations
    # Newton's stop leaves two energy residuals within 10x of their tolerance: disclosed, as
    # ADR 0007 D2.4 says, and nothing else is near threshold.
    near = [
        item.detail["check"] for item in certificate.limitations if item.kind == "near_threshold"
    ]
    assert all(check.startswith("residual.") for check in near), near
    regularity = certificate.regularity
    assert regularity is not None and regularity.status == "NO_RANK_LOSS_DETECTED"
    assert regularity.rcond_1 is not None and regularity.rcond_1 >= 10.0 * TAU_ILL
    assert regularity.rcond_1 == pytest.approx(1.4238e-4, rel=1e-3)
    state = run.state
    assert state is not None
    liquid, vapour_in = sum(_flows(state, "S6")), sum(_flows(state, "S4"))
    assert liquid / vapour_in == pytest.approx(0.12806, rel=1e-3)
    # The reactor inlet (§8.1's feasibility facts): inside the hard and the data domain.
    n = _flows(state, "S3")
    total = sum(n)
    hard, data = STANDIN.boundary["hard_domain"], STANDIN.boundary["data_domain"]
    t, p = state["S3.T"], state["S3.P"]
    assert hard["T_K"][0] <= t <= hard["T_K"][1] and hard["P_Pa"][0] <= p <= hard["P_Pa"][1]
    assert data["T_K"][0] <= t <= data["T_K"][1] and data["P_Pa"][0] <= p <= data["P_Pa"][1]
    assert data["H2_N2"][0] <= n[0] / n[1] <= data["H2_N2"][1]
    assert (n[3] + n[4]) / total <= hard["inert_max"]
    assert (n[3] + n[4]) / total == pytest.approx(0.0607, rel=1e-2)
    assert n[2] / total == pytest.approx(0.0271, rel=1e-2)
    per_tube = total / 1000.0
    assert per_tube / F_NOM == pytest.approx(0.576, rel=1e-2)
    assert variants.hard_domain(REAL).tube_flow is not None
    low, high = variants.hard_domain(REAL).tube_flow  # type: ignore[misc]
    assert low <= per_tube <= high  # Q-F5's bound holds for the real variant too


# == G8 (e) ======================================================================================


def test_g8e_the_stand_in_binds_and_says_synthetic_everywhere(tmp_path: Path) -> None:
    """G8 (e) (design note §10.1; ADR 0034 D9; R-231), replacing M01.A49's binder clause: the
    stand-in binds — through `MODEL_BUILDERS` since R-280's join, the v0.2 envelope listing it as
    synthetic only (`test_m02_join.py`) — its manifest says
    SYNTHETIC where M01.A49 puts the label, and every `ok` result's identity at the loop's
    reactor inlet says synthetic. At w* the experiment agrees with the embedded rows to
    roundoff (|ξ_E − X̂ n_N2,in| / n_tot ≤ 1e-12, T_E − T_in = 0.0): w* is the coupled solution."""
    document = loop()
    binding = at_coupling(bound(document), "reactor", W_STAR)
    reactor = unit_of(binding, "reactor")
    assert reactor.synthetic and reactor.model_id == "c1.reactor_standin"
    assert "c1.reactor_standin" in MODEL_BUILDERS and MODEL_BASES["c1.reactor_standin"] == {
        "pr-c1-v1"
    }
    manifest = reactor.manifest()
    assert "synthetic" in manifest["title"].lower()
    assert manifest["description"].startswith("SYNTHETIC")
    assert manifest["validity"]["limitations"][0].startswith("SYNTHETIC:")
    _, run = solved(binding)
    assert run.state is not None
    n = _flows(run.state, "S3")
    inlet = StreamState(n=n, temperature=run.state["S3.T"], pressure=run.state["S3.P"])
    runner = ExperimentRunner(ExperimentStore(tmp_path, ListArtifactSink()), PROVIDER, CONTEXT)
    outcome = runner.run(STANDIN, inlet, COMPONENTS, reactor.n_tubes)
    assert outcome.result is not None
    envelope = outcome.result["envelope"]
    assert envelope["status"] == "ok"
    assert envelope["identity"]["synthetic"] is True
    assert envelope["identity"]["model_id"] == "c1.reactor_standin"
    assert abs(envelope["xi"] - W_STAR[0] * n[1]) / sum(n) <= 1e-12
    assert envelope["outlet"]["T"] - inlet.temperature == 0.0
