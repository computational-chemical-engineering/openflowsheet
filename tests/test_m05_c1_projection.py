"""M05 WO-5: the C1 study's formulation `c1-trf-study-v1` and its projection, gate G4's C1 part
(design note §6.1, §7.1, §13 G4, §16.1, §16.5; ADR 0039 D1, D2; R-267, R-274, R-278).

- The formulation is generated from the bound revision and variant: the heater feeding the
  reactor as the decision, the flash's liquid NH₃ as the objective, the hard domain and A(s) as
  constraints.
- The projection of the coupled route's inner problem (the loop at S0's certified state for
  TR-E2: T_in = 673.15 K, w the reference's coupled w) passes R-278's shape check
  (`PROJECTION_IMPLICIT_EF_INPUT` is not raised: C1 is forward by construction) and omits exactly
  the rows R-274's elimination computes — the zero-ΔP loop's two pressure alias rows — and
  eliminates the five flows exactly 0.0 at x₀ with their pins (R-296, §17.1 (a), (b)): the
  shape check's matching goes from 73 × 73 to 68 × 68, with DOF = 1.
- TRF on TR-E2 gets past iteration 1 with no `TRF_TRUTH_REFUSED`, and every request any holder
  serves has +0.0, bitwise, at an eliminated flow's position (§17.1 (d)).
- G4 (a)-(e) at that state and at that state with every variable perturbed by a seeded relative
  1e-3: residuals ≤ 1e-12 scaled, x-Jacobian ≤ 1e-10, decision columns ≤ 1e-7 against CasADi's
  central difference, a bijective source map with DOF = n_d = 1, no nonsmooth node.

Marked `nlp`: the projection needs Pyomo. Nothing at module level imports it.
"""

from __future__ import annotations

import json
import sys
import tempfile
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from conftest import REPO_ROOT
from test_m02_wo9_reactor import LOOP_PATH, REAL
from test_m05_projection import equivalence, structure

from openflowsheet.adapters.experiments.runner import ExperimentRunner
from openflowsheet.adapters.experiments.store import ExperimentStore
from openflowsheet.application.revision_binding import (
    RevisionBinding,
    bind_revision_flowsheet,
    with_coupling,
)
from openflowsheet.compiled import EvaluationContext
from openflowsheet.thermo.pr_c1 import PrC1Provider

sys.path.insert(0, str(REPO_ROOT / "tests" / "support"))
import m05_reference as reference  # noqa: E402
import m05_synthetic as synthetic  # noqa: E402

pytestmark = pytest.mark.nlp

#: §7.2: S0's nominal decision, K.
NOMINAL = 673.15
#: G4: the perturbation's seed and relative size.
SEED = 20261009
PERTURBATION = 1e-3


def loop() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(LOOP_PATH.read_text(encoding="utf-8"))
    return document


@cache
def s0() -> tuple[RevisionBinding, dict[str, float], Any]:
    """S0 for TR-E2: the loop at 673.15 K coupled to the synthetic truth (the reference's Newton),
    its inner solve certified, as (binding at that w, state, certificate)."""
    from openflowsheet.orchestrator.executor import execute_plan
    from openflowsheet.orchestrator.revision import plan_revision
    from openflowsheet.verify.certificate import verify_revision

    document = reference.with_inlet_temperature(loop(), NOMINAL)
    point = reference.coupled(loop(), NOMINAL)
    binding = bind_revision_flowsheet(document)
    assert isinstance(binding, RevisionBinding), binding
    pinned = with_coupling(binding, "reactor", *point.w)
    plan, _ = plan_revision(pinned, reference.POLICY)
    run = execute_plan(
        plan=plan, flowsheet=pinned.flowsheet, spec=pinned.spec, policy=reference.POLICY
    )
    assert run.outcome == "CONVERGED" and run.state is not None, run.message
    certificate = verify_revision(pinned, document, run, solve_plan=plan.steps[-1].solve_plan)
    return pinned, dict(run.state), certificate


def truth_for(variant: Any) -> Any:
    runner = ExperimentRunner(
        ExperimentStore(Path(tempfile.mkdtemp(prefix="m05-g4-"))),
        PrC1Provider(),
        EvaluationContext(model_version="m05-g4", constants_sha256="0" * 64),
        backend_for=synthetic.backend_for,
    )
    return synthetic.SyntheticTruth(runner, variant, 1000.0)


def tr_e2() -> tuple[Any, Any, dict[str, float]]:
    from openflowsheet.studies.trust_region.study import TR_E2_BOX, c1_formulation, project_c1

    binding, state, _ = s0()
    variant = synthetic.synthetic_variant()
    formulation = c1_formulation(binding, variant, truth_for(variant), TR_E2_BOX)
    return formulation, project_c1(binding, state, formulation), state


# == the formulation ===============================================================================


def test_s0_is_certified() -> None:
    _, state, certificate = s0()
    assert certificate.verification_status == "VERIFIED", certificate.limitations
    assert state["S3.T"] == NOMINAL


def test_the_formulation_is_generated_from_the_revision_and_the_variant() -> None:
    from openflowsheet.studies.trust_region.study import MARGIN_REL, OBJECTIVE_ID

    formulation, projection, _ = tr_e2()
    assert (formulation.reactor, formulation.heater) == ("reactor", "preheater")
    assert (formulation.inlet_stream, formulation.liquid_stream) == ("S3", "S6")
    (decision,) = formulation.decisions
    assert (decision.parameter_id, decision.lower, decision.upper) == (
        "preheater.T_spec",
        653.15,
        693.15,
    )
    (link,) = formulation.external_links
    assert (link.x_param_id, link.dt_param_id) == ("reactor.coupling.X", "reactor.coupling.dT")
    assert link.inlet_variable_ids == (
        "S3.n.H2",
        "S3.n.N2",
        "S3.n.NH3",
        "S3.n.Ar",
        "S3.n.CH4",
        "S3.T",
        "S3.P",
    )
    assert formulation.objective.objective_id == OBJECTIVE_ID
    assert formulation.objective.sense == "maximize" and formulation.objective.scale == 1.0
    assert formulation.domain == {"temperature": (200.0, 1000.0), "pressure": (1e4, 3e7)}
    # The stand-in's hard domain (the synthetic truth's): T, P bounds; no per-tube flow bound.
    assert formulation.variable_bounds == {"S3.T": (573.15, 773.15), "S3.P": (5e6, 1.5e7)}
    assert [
        (i.inequality_id, i.bound, i.sense, i.margin_rel) for i in formulation.inequalities
    ] == [
        ("hard_domain.h2_n2.lower", 0.0, "<=", MARGIN_REL),
        ("hard_domain.h2_n2.upper", 0.0, "<=", MARGIN_REL),
        ("hard_domain.inert_max", 0.0, "<=", MARGIN_REL),
        ("admissibility.h2_limit", 0.0, "<=", MARGIN_REL),
    ]
    variables = {entry["variable_id"]: entry for entry in projection.source_map["variables"]}
    assert variables["S3.T"]["bounds"] == [573.15, 773.15]
    assert variables["S3.P"]["bounds"] == [5e6, 1.5e7]
    assert variables["S4.T"]["bounds"] == [200.0, 1000.0]


def test_the_real_variant_adds_the_per_tube_flow_bounds() -> None:
    """ADR 0034 D10: the real variant bounds Σn/N_tubes to [0.5, 2] F₀ (two expression
    constraints); REAL's box is the kinetics' inlet span."""
    from openflowsheet.studies.trust_region.study import REAL_BOX, c1_formulation, project_c1

    binding, state, _ = s0()
    formulation = c1_formulation(binding, REAL, truth_for(REAL), REAL_BOX)
    added = [i for i in formulation.inequalities if i.inequality_id.startswith("hard_domain.tube")]
    low, high = REAL.boundary["hard_domain"]["tube_flow_mol_s"]
    assert [(i.inequality_id, i.bound, i.sense) for i in added] == [
        ("hard_domain.tube_flow.lower", low, ">="),
        ("hard_domain.tube_flow.upper", high, "<="),
    ]
    (decision,) = formulation.decisions
    assert (decision.lower, decision.upper) == REAL_BOX == (653.15, 693.15)
    projection = project_c1(binding, state, formulation)
    assert projection.source_map["shape_check"]["status"] == "pass"


# == the projection: R-278, R-274 ================================================================


def test_c1_passes_the_shape_check_and_omits_exactly_the_computed_alias_rows() -> None:
    _, projection, state = tr_e2()
    source = projection.source_map
    shape = source["shape_check"]
    assert (shape["status"], shape["matched"], shape["size"], shape["refusal"]) == (
        "pass",
        68,
        68,
        None,
    )
    omitted = source["omitted_rows"]
    assert [row["equation_id"] for row in omitted] == [
        "flash:C1FL-P:inlet",
        "splitter:C1SPLIT-P:recycle",
    ]
    assert all(row["residual_x0"] == 0.0 for row in omitted)
    assert len(source["rows"]) == len(projection.spec.equation_ids) - 2 - 5 == 57
    assert len(source["external_links"]) == 2 and len(source["decisions"]) == 1


def test_r296_the_five_exact_zero_flows_are_eliminated_with_their_pins() -> None:
    """§17.1 (a): `S1.n.NH3` with the feed's specification row, `S6.n.{H2,N2,Ar,CH4}` with the
    flash's four zero rows (`zero_row`, which sit in the light gases' equilibrium slots), each
    with residual 0.0 and a nonzero pivot at x₀; (b) DOF = n_d = 1 (`structure`)."""
    _, projection, state = tr_e2()
    eliminated = projection.source_map["zero_eliminated"]
    assert [(z["variable_id"], z["row_id"]) for z in eliminated] == [
        ("S1.n.NH3", "makeup:C1FEED-n:NH3"),
        ("S6.n.H2", "flash:C1FL-equilibrium:H2"),
        ("S6.n.N2", "flash:C1FL-equilibrium:N2"),
        ("S6.n.Ar", "flash:C1FL-equilibrium:Ar"),
        ("S6.n.CH4", "flash:C1FL-equilibrium:CH4"),
    ]
    assert all(z["residual_x0"] == 0.0 and abs(z["dr_dx"]) > 0.0 for z in eliminated)
    zero = [
        name
        for name in projection.spec.variable_ids
        if projection.spec.variable_kinds.get(name) == "molar_flow" and state[name] == 0.0
    ]
    assert zero == [z["variable_id"] for z in eliminated]
    structure(projection)


def test_r296_trf_on_tr_e2_passes_iteration_1_with_exact_zero_arguments(
    monkeypatch: pytest.MonkeyPatch, record_property: Any
) -> None:
    """§17.1 (d): before R-296 TRF stopped before iteration 1, `TRF_TRUTH_REFUSED(
    property_domain_error:S1_Hdot_V)` at S1.n.NH3 = −3.4e-27. Every argument tuple any holder
    is asked about holds +0.0, bitwise, at each eliminated flow's position. (The run's outcome
    and optimum are WO-8's acceptance, not this test's.)"""
    import struct

    from openflowsheet.studies.trust_region import holders
    from openflowsheet.studies.trust_region.basis import m05_basis
    from openflowsheet.studies.trust_region.trf import run_trf
    from openflowsheet.studies.trust_region.trf_state import TRF_CONFIG_V1

    seen: dict[str, list[tuple[float, ...]]] = {}
    key = holders.EFHolder._key

    def spy(self: Any, args: Any) -> Any:
        seen.setdefault(self.name, []).append(tuple(float(a) for a in args[: self.n_in]))
        return key(self, args)

    monkeypatch.setattr(holders.EFHolder, "_key", spy)
    _, projection, _ = tr_e2()
    result = run_trf(
        projection,
        {**dict(TRF_CONFIG_V1), "step_size_termination": 0.0125},
        basis=m05_basis(projection),
    )
    record_property("M05.R296.tr_e2.outcome", result.outcome)
    record_property("M05.R296.tr_e2.iterations", len(result.iterations))
    assert not result.outcome.startswith("TRF_TRUTH_REFUSED"), result.outcome
    assert result.refusal is None and max(record.k for record in result.iterations) >= 1
    ids, gone = projection.spec.variable_ids, projection.eliminated_ids
    checked = 0
    for holder, inputs in zip(projection.holders, projection.holder_inputs, strict=True):
        positions = [k for k, i in enumerate(inputs) if ids[i] in gone]
        for arguments in seen.get(holder.name, []) if positions else ():
            for k in positions:
                assert struct.pack(">d", arguments[k]) == bytes(8), (holder.name, k, arguments)
                checked += 1
    record_property("M05.R296.tr_e2.zero_arguments_checked", checked)
    assert checked > 0
    if result.zero_pins_final is not None:
        assert result.zero_pins_final.status == "pass"
        assert result.final_state is not None
        assert all(result.final_state[name] == 0.0 for name in gone)


# == G4 (C1) ====================================================================================


def test_g4_c1_at_s0s_certified_state(record_property: Any) -> None:
    _, projection, state = tr_e2()
    measured = equivalence(projection, state)
    for name, value in measured.items():
        record_property(f"M05.G4.c1.s0.{name}", value)


def test_g4_c1_at_s0_perturbed_by_a_seeded_relative_1e_3(record_property: Any) -> None:
    """The same projection's rows, Jacobian and decision columns at x₀(1 + 10⁻³ ξ), ξ uniform in
    [−1, 1] from a fixed seed (exact zeros stay zero): the projection and CasADi are the same
    functions, not only the same values at a solution."""
    _, projection, state = tr_e2()
    names = projection.spec.variable_ids
    generator = np.random.default_rng(SEED)
    factors = 1.0 + PERTURBATION * generator.uniform(-1.0, 1.0, len(names))
    perturbed = {
        name: state[name] * float(factor) for name, factor in zip(names, factors, strict=True)
    }
    projection.set_state(perturbed)
    structure(projection)
    measured = equivalence(projection, perturbed)
    for name, value in measured.items():
        record_property(f"M05.G4.c1.perturbed.{name}", value)
