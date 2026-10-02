"""T05 W1.d: the verifier's table for revision-built flowsheets, and `verify_revision`.

Design note `docs/design/T05-generalization.md` §4 and §7 (W1.d), register R-046. SYN-001 keeps
its legacy check set; a revision-built flowsheet is judged by `verify.table`, which shares ids and
the revision's values with the solver and nothing else (R-016). The two sets are held together by
**cross-validation** on the SYN-001-shaped revision (`t05_syn001_shaped`): each legacy check value
equals its general counterpart **bitwise**, at the converged root and at the traversal start `x⁰`,
a non-root where the recycle's balances are nonzero — so an operation order that departs from the
legacy one shows as a differing bit, not as a tolerance that happens to hold.

**At one state** (K04-F9 spec §10.7, X22). Since ADR 0013 D1 the certificate judges its fresh-flash
categories (`energy_balance`, `phase_admissibility`, `independent_split`) at the verifier's
projection `x̃` and everything else at `x_final`, while `run_checks` — the legacy primitive, never
projected — evaluates one point. The pairing is unchanged; the harness compares like with like:
the legacy set at `x_final` with its fresh-flash categories taken from the legacy set at the
certificate's `x̃`, against the certificate — and, separately, both engines at `x_final` and both
at `x̃`, every pair bitwise.
"""

from __future__ import annotations

import struct
from collections.abc import Mapping
from typing import Any

import pytest
from t05_syn001_shaped import shaped_revision

from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.revision_flowsheet import parse_revision
from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import PlanResult, execute_plan
from openflowsheet.orchestrator.revision import InitialStateFailure, initial_state, plan_revision
from openflowsheet.orchestrator.splits import lifted_splits
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.thermo.syn001 import Syn001Provider
from openflowsheet.verify import CheckResult
from openflowsheet.verify.certificate import (
    CheckPolicy,
    SolutionCertificate,
    VerifierError,
    run_checks,
    verify,
    verify_revision,
)
from openflowsheet.verify.projection import PROJECTED_CATEGORIES
from openflowsheet.verify.table import MODEL_CHECKS, Unit, revision_checks

POLICY = SolvePolicy(policy_id="T05-W1d", residual_tolerances={}, scales={})
CONTEXT = EvaluationContext(
    model_version="t05-w1d", constants_sha256="0" * 64, phase_signature=None
)
#: K04 §9.2's registered offset (`benchmarks/k04/reference_values.yaml`), as `test_k04_checks`.
TRIVIAL_ROOT_OFFSET = 8237.8503930694530451

#: The certificate's check ids for the SYN-001-shaped solve, in order (§4.2, §4.3): the 49
#: residual rows, the two certified aliases, then the table's categories — material, energy,
#: specification, bounds, admissibility and independent split — and the derivative witness.
PINNED_IDS: tuple[str, ...] = (
    "residual.U-FEED:FEED-n:A",
    "residual.U-FEED:FEED-n:B",
    "residual.U-FEED:FEED-n:C",
    "residual.U-FEED:FEED-T",
    "residual.U-FEED:FEED-P",
    "residual.U-MIX:MIX-mole:A",
    "residual.U-MIX:MIX-mole:B",
    "residual.U-MIX:MIX-mole:C",
    "residual.U-MIX:MIX-energy",
    "residual.U-MIX:MIX-pressure:0",
    "residual.U-MIX:MIX-pressure:1",
    "residual.U-HEAT:HEAT-mole:A",
    "residual.U-HEAT:HEAT-mole:B",
    "residual.U-HEAT:HEAT-mole:C",
    "residual.U-HEAT:HEAT-T",
    "residual.U-HEAT:HEAT-pressure",
    "residual.U-HEAT:HEAT-duty",
    "residual.U-HEAT:HEAT-equilibrium:A",
    "residual.U-HEAT:split:A",
    "residual.U-HEAT:HEAT-equilibrium:B",
    "residual.U-HEAT:split:B",
    "residual.U-HEAT:HEAT-equilibrium:C",
    "residual.U-HEAT:split:C",
    "residual.U-HEAT:Vdef",
    "residual.U-HEAT:Ldef",
    "residual.U-FLASH:FLASH-mole:A",
    "residual.U-FLASH:FLASH-equilibrium:A",
    "residual.U-FLASH:FLASH-mole:B",
    "residual.U-FLASH:FLASH-equilibrium:B",
    "residual.U-FLASH:FLASH-mole:C",
    "residual.U-FLASH:FLASH-equilibrium:C",
    "residual.U-FLASH:FLASH-T:vapor",
    "residual.U-FLASH:FLASH-T:liquid",
    "residual.U-FLASH:FLASH-P:vapor",
    "residual.U-FLASH:FLASH-P:liquid",
    "residual.U-FLASH:FLASH-P:inlet",
    "residual.U-FLASH:FLASH-duty",
    "residual.U-FLASH:Ndef:vapor",
    "residual.U-FLASH:Ndef:liquid",
    "residual.U-SPLIT:SPLIT-recycle:A",
    "residual.U-SPLIT:SPLIT-purge:A",
    "residual.U-SPLIT:SPLIT-recycle:B",
    "residual.U-SPLIT:SPLIT-purge:B",
    "residual.U-SPLIT:SPLIT-recycle:C",
    "residual.U-SPLIT:SPLIT-purge:C",
    "residual.U-SPLIT:SPLIT-T:recycle",
    "residual.U-SPLIT:SPLIT-T:purge",
    "residual.U-SPLIT:SPLIT-P:recycle",
    "residual.U-SPLIT:SPLIT-P:purge",
    "alias_certificate.identity.U-FLASH:FLASH-P:inlet",
    "alias_certificate.satisfied.U-FLASH:FLASH-P:inlet",
    "alias_certificate.identity.U-SPLIT:SPLIT-P:recycle",
    "alias_certificate.satisfied.U-SPLIT:SPLIT-P:recycle",
    "material_balance.U-MIX.A",
    "material_balance.U-MIX.B",
    "material_balance.U-MIX.C",
    "material_balance.U-HEAT.A",
    "material_balance.U-HEAT.B",
    "material_balance.U-HEAT.C",
    "material_balance.U-HEAT.lifted_split.A",
    "material_balance.U-HEAT.lifted_split.B",
    "material_balance.U-HEAT.lifted_split.C",
    "material_balance.U-HEAT.total.V",
    "material_balance.U-HEAT.total.L",
    "material_balance.U-FLASH.A",
    "material_balance.U-FLASH.B",
    "material_balance.U-FLASH.C",
    "material_balance.U-FLASH.total.vapor",
    "material_balance.U-FLASH.total.liquid",
    "material_balance.U-SPLIT.A",
    "material_balance.U-SPLIT.B",
    "material_balance.U-SPLIT.C",
    "material_balance.envelope.A",
    "material_balance.envelope.B",
    "material_balance.envelope.C",
    "energy_balance.U-MIX",
    "energy_balance.U-HEAT",
    "energy_balance.U-FLASH",
    "energy_balance.U-SPLIT",
    "energy_balance.envelope",
    "specification.U-FEED.n.A",
    "specification.U-FEED.n.B",
    "specification.U-FEED.n.C",
    "specification.U-FEED.T",
    "specification.U-FEED.P",
    "specification.U-HEAT.T",
    "specification.U-FLASH.temperature.vapor",
    "specification.U-FLASH.temperature.liquid",
    "specification.U-FLASH.pressure.vapor",
    "specification.U-FLASH.pressure.liquid",
    "specification.U-SPLIT.ratio.A",
    "specification.U-SPLIT.ratio.B",
    "specification.U-SPLIT.ratio.C",
    "bounds_and_domain.nonnegative.S1.n.A",
    "bounds_and_domain.nonnegative.S1.n.B",
    "bounds_and_domain.nonnegative.S1.n.C",
    "bounds_and_domain.nonnegative.S2.n.A",
    "bounds_and_domain.nonnegative.S2.n.B",
    "bounds_and_domain.nonnegative.S2.n.C",
    "bounds_and_domain.nonnegative.S3.L",
    "bounds_and_domain.nonnegative.S3.V",
    "bounds_and_domain.nonnegative.S3.liq.A",
    "bounds_and_domain.nonnegative.S3.liq.B",
    "bounds_and_domain.nonnegative.S3.liq.C",
    "bounds_and_domain.nonnegative.S3.n.A",
    "bounds_and_domain.nonnegative.S3.n.B",
    "bounds_and_domain.nonnegative.S3.n.C",
    "bounds_and_domain.nonnegative.S3.vap.A",
    "bounds_and_domain.nonnegative.S3.vap.B",
    "bounds_and_domain.nonnegative.S3.vap.C",
    "bounds_and_domain.nonnegative.S4.N",
    "bounds_and_domain.nonnegative.S4.n.A",
    "bounds_and_domain.nonnegative.S4.n.B",
    "bounds_and_domain.nonnegative.S4.n.C",
    "bounds_and_domain.nonnegative.S5.N",
    "bounds_and_domain.nonnegative.S5.n.A",
    "bounds_and_domain.nonnegative.S5.n.B",
    "bounds_and_domain.nonnegative.S5.n.C",
    "bounds_and_domain.nonnegative.S6.n.A",
    "bounds_and_domain.nonnegative.S6.n.B",
    "bounds_and_domain.nonnegative.S6.n.C",
    "bounds_and_domain.nonnegative.S7.n.A",
    "bounds_and_domain.nonnegative.S7.n.B",
    "bounds_and_domain.nonnegative.S7.n.C",
    "bounds_and_domain.domain.S1",
    "bounds_and_domain.domain.S2",
    "bounds_and_domain.domain.S3",
    "bounds_and_domain.domain.S4",
    "bounds_and_domain.domain.S5",
    "bounds_and_domain.domain.S6",
    "bounds_and_domain.domain.S7",
    "phase_admissibility.U-HEAT.S3.bubble",
    "independent_split.U-HEAT.S3.total",
    "independent_split.U-HEAT.S3.A",
    "independent_split.U-HEAT.S3.B",
    "independent_split.U-HEAT.S3.C",
    "phase_admissibility.U-FLASH.S3.closure",
    "independent_split.U-FLASH.S3.total",
    "independent_split.U-FLASH.S3.A",
    "independent_split.U-FLASH.S3.B",
    "independent_split.U-FLASH.S3.C",
    "phase_admissibility.U-MIX.inlet.S1",
    "phase_admissibility.U-MIX.inlet.S6",
    "phase_admissibility.U-MIX.outlet",
    "phase_admissibility.U-HEAT.inlet",
    "derivative_witness.on_pattern",
    "derivative_witness.off_pattern",
)

#: Legacy id -> general id (§7, W1.d): every pair must agree to the bit.
PAIRS: dict[str, str] = {
    **{
        f"material_balance.{legacy}.{c}": f"material_balance.{general}.{c}"
        for legacy, general in (
            ("mixer", "U-MIX"),
            ("heater", "U-HEAT"),
            ("flash", "U-FLASH"),
            ("splitter", "U-SPLIT"),
            ("lifted_split", "U-HEAT.lifted_split"),
        )
        for c in "ABC"
    },
    **{f"material_balance.ratio.{c}": f"specification.U-SPLIT.ratio.{c}" for c in "ABC"},
    **{f"material_balance.envelope.{c}": f"material_balance.envelope.{c}" for c in "ABC"},
    "material_balance.total.S3.V": "material_balance.U-HEAT.total.V",
    "material_balance.total.S3.L": "material_balance.U-HEAT.total.L",
    "material_balance.total.S4.N": "material_balance.U-FLASH.total.vapor",
    "material_balance.total.S5.N": "material_balance.U-FLASH.total.liquid",
    "energy_balance.mixer": "energy_balance.U-MIX",
    "energy_balance.heater": "energy_balance.U-HEAT",
    "energy_balance.flash": "energy_balance.U-FLASH",
    # Ruling round Q-R3 (note §4.3's splitter row): K04's splitter balance, the only independent
    # check of the splitter's temperature copies, now has its general counterpart.
    "energy_balance.splitter": "energy_balance.U-SPLIT",
    "energy_balance.envelope": "energy_balance.envelope",
    "specification.S1.T": "specification.U-FEED.T",
    "specification.S1.P": "specification.U-FEED.P",
    **{f"specification.S1.n.{c}": f"specification.U-FEED.n.{c}" for c in "ABC"},
    "specification.S3.T": "specification.U-HEAT.T",
    "specification.S4.T": "specification.U-FLASH.temperature.vapor",
    "specification.S5.T": "specification.U-FLASH.temperature.liquid",
    **{f"independent_split.S3.{x}": f"independent_split.U-HEAT.S3.{x}" for x in ("total", *"ABC")},
}


def _bits(value: float | None) -> bytes:
    assert value is not None
    return struct.pack("<d", value)


def _legacy(**overrides: float) -> Syn001Flowsheet:
    return Syn001Flowsheet(provider=Syn001Provider(), context=CONTEXT, **overrides)  # type: ignore[arg-type]


def _solve(document: Mapping[str, Any]) -> tuple[RevisionBinding, ExecutionPlan, PlanResult]:
    binding = bind_revision_flowsheet(document)
    assert isinstance(binding, RevisionBinding), binding
    plan, _ = plan_revision(binding, POLICY)
    assert isinstance(plan, ExecutionPlan), plan
    run = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=POLICY)
    assert run.outcome == "CONVERGED", run.message
    return binding, plan, run


@pytest.fixture(scope="module")
def solved() -> tuple[dict[str, Any], RevisionBinding, ExecutionPlan, PlanResult]:
    document = shaped_revision()
    return (document, *_solve(document))


@pytest.fixture(scope="module")
def certificate(
    solved: tuple[dict[str, Any], RevisionBinding, ExecutionPlan, PlanResult],
) -> SolutionCertificate:
    document, binding, plan, run = solved
    return verify_revision(binding, document, run, solve_plan=plan.steps[-1].solve_plan)


def _general_at(document: Mapping[str, Any], state: Mapping[str, float]) -> list[CheckResult]:
    view = parse_revision(document)
    splits = lifted_splits(
        [(i.unit_id, i.model_id, i.wiring) for i in view.instances], view.components
    )
    return revision_checks(
        view,
        splits,
        state,
        provider=Syn001Provider(),
        context=CONTEXT,
        tolerances=CheckPolicy().tolerances,
    )


def _projection(
    binding: RevisionBinding, document: Mapping[str, Any], state: Mapping[str, float]
) -> tuple[str, Mapping[str, float]]:
    """`verify_revision`'s projection at `state` (ADR 0013 D1): `(judged_at, x̃)`, rebuilt from the
    certificate path's own pieces — its declaration, screen, rows and zero-flow forms."""
    from openflowsheet.compile.casadi_backend import compile_problem
    from openflowsheet.verify.certificate import BoundDeclaration, _project, _screen
    from openflowsheet.verify.checks import label_checks, residual_checks
    from openflowsheet.verify.zero_flow import dormant_outlets, zero_flow_splits

    view = parse_revision(document)
    splits = lifted_splits(
        [(i.unit_id, i.model_id, i.wiring) for i in view.instances], view.components
    )
    target = BoundDeclaration(binding.spec, compile_problem(binding.spec), state)
    tolerances = CheckPolicy().tolerances
    zero_flow = (*zero_flow_splits(view, splits, state), *dormant_outlets(view, state))
    rows, _ = residual_checks(
        target.compiled, target.spec, state, target.context, target.spec.row_kinds, tolerances
    )
    projection = _project(
        target,
        state,
        [*rows, *label_checks(zero_flow, state, tolerances)],
        _screen(target, state, zero_flow),
        zero_flow=zero_flow,
        streams=view.streams,
        provider=Syn001Provider(),
        policy=CheckPolicy(),
    )
    return projection.judged_at, projection.state


def _at_one_state(
    at_final: list[CheckResult], at_projection: list[CheckResult]
) -> list[CheckResult]:
    """One engine's checks as the certificate judges them: the fresh-flash categories from
    `at_projection`, everything else from `at_final` — same ids, same order."""
    assert [c.id for c in at_final] == [c.id for c in at_projection]
    return [
        judged if check.category in PROJECTED_CATEGORIES else check
        for check, judged in zip(at_final, at_projection, strict=True)
    ]


# -- the certificate ---------------------------------------------------------------------------


def test_the_shaped_solve_is_verified_with_the_pinned_check_ids(
    certificate: SolutionCertificate,
) -> None:
    assert certificate.verification_status == "VERIFIED", certificate.limitations
    assert not certificate.false_success_detected
    assert [check.id for check in certificate.checks] == list(PINNED_IDS)
    assert len(PINNED_IDS) == 147
    # §4.3: the energy and phase checks share the provider and say so; the balances do not.
    for check in certificate.checks:
        shares = check.category in ("energy_balance", "phase_admissibility", "independent_split")
        assert (check.independence_qualification is not None) == shares, check.id
    assert certificate.phase_branch["U-HEAT:S3"]["vapor_total"] == 0.0
    assert set(certificate.phase_branch) == {
        *(f"S{k}" for k in range(1, 8)),
        "U-HEAT:S3",
        "U-FLASH:S3",
    }


# -- cross-validation against the legacy check set ---------------------------------------------


def _pairs(legacy: list[CheckResult]) -> dict[str, str]:
    """`PAIRS` plus the one admissibility pair, whose closure (`bubble`, `dew` or `closure`)
    depends on the state."""
    admissibility = [c.id for c in legacy if c.id.startswith("phase_admissibility.S3.")]
    assert len(admissibility) == 1, admissibility
    return {
        **PAIRS,
        admissibility[0]: admissibility[0].replace(
            "phase_admissibility.S3.", "phase_admissibility.U-HEAT.S3."
        ),
    }


def _cross_validate(legacy: list[CheckResult], general: list[CheckResult]) -> list[str]:
    old = {check.id: check.value for check in legacy}
    new = {check.id: check.value for check in general}
    pairs = _pairs(legacy)
    assert len(pairs) == 43
    return [
        f"{legacy_id}={old[legacy_id]!r} vs {general_id}={new[general_id]!r}"
        for legacy_id, general_id in pairs.items()
        if _bits(old[legacy_id]) != _bits(new[general_id])
    ]


def _uncovered(
    legacy: list[CheckResult], general: list[CheckResult], pairs: Mapping[str, str]
) -> list[str]:
    """Note §7 W1.d (d), coverage: every legacy check id is either generic — the same id in the
    general certificate (residual rows, aliases, the generic bounds, `energy_balance.enthalpy.<S>`)
    — or the legacy side of a listed pair. Returns the ids that are neither, and the generic ids
    whose values differ in a bit."""
    new = {check.id: check.value for check in general}
    uncovered = [c.id for c in legacy if c.id not in new and c.id not in pairs]

    def same(a: float | None, b: float | None) -> bool:
        return a is None and b is None or (a is not None and b is not None and _bits(a) == _bits(b))

    differing = [
        f"{c.id}={c.value!r} vs {new[c.id]!r}"
        for c in legacy
        if c.id in new and not same(c.value, new[c.id])
    ]
    return uncovered + differing


def test_every_legacy_value_equals_its_general_counterpart_bitwise_at_the_root(
    solved: tuple[dict[str, Any], RevisionBinding, ExecutionPlan, PlanResult],
    certificate: SolutionCertificate,
) -> None:
    """(a) At the converged shaped state, against the certificate's own checks — the legacy set
    judged where the certificate judges (X22) — and both engines at `x_final` and at `x̃`."""
    document, binding, _, run = solved
    assert run.state is not None
    judged_at, projected = _projection(binding, document, run.state)
    assert judged_at == "projection"  # not vacuous: the certificate did project
    assert certificate.transformations["projection"]["judged_at"] == "projection"
    assert projected != run.state
    at_final, _ = run_checks(_legacy(), run.state)
    at_projection, _ = run_checks(_legacy(), projected)
    legacy = _at_one_state(at_final, at_projection)
    assert _cross_validate(legacy, list(certificate.checks)) == []
    assert _uncovered(legacy, list(certificate.checks), _pairs(legacy)) == []
    # Each engine at one point, every pair — fresh-flash and not — to the bit.
    assert _cross_validate(at_final, _general_at(document, run.state)) == []
    assert _cross_validate(at_projection, _general_at(document, projected)) == []


def test_every_legacy_value_equals_its_general_counterpart_bitwise_at_the_start(
    solved: tuple[dict[str, Any], RevisionBinding, ExecutionPlan, PlanResult],
) -> None:
    """(b) At `x⁰` (`traversal-G0-v1`): a non-root, so the pairs compare nonzero values."""
    document, binding, plan, run = solved
    start = initial_state(binding.flowsheet, binding.spec.variable_ids)
    assert not isinstance(start, InitialStateFailure), start
    legacy, _ = run_checks(_legacy(), start)
    general = _general_at(document, start)
    assert _cross_validate(legacy, general) == []
    # (d) Coverage against the whole general certificate at `x⁰`, generic checks included.
    whole = verify_revision(
        binding, document, run, solve_plan=plan.steps[-1].solve_plan, state=start
    )
    # `x⁰` fails its rows, so the certificate judges every category there (spec §5.1, 1).
    assert whole.transformations["projection"] == {
        "judged_at": "final_state",
        "reason": "residual_not_passed",
        "categories": list(PROJECTED_CATEGORIES),
    }
    assert _uncovered(legacy, list(whole.checks), _pairs(legacy)) == []
    # What `x⁰` exercises: the traversal closes every unit causally, so the heater's and the
    # specifications' pairs are exactly zero; the torn recycle leaves these nonzero.
    nonzero = [name for name in PAIRS if next(c for c in legacy if c.id == name).value != 0.0]
    assert nonzero == [
        *(
            f"material_balance.{item}.{c}"
            for item in ("flash", "splitter", "ratio", "envelope")
            for c in "ABC"
        ),
        "energy_balance.mixer",
        "energy_balance.flash",
        "energy_balance.splitter",
        "energy_balance.envelope",
    ]
    # Q-R3's measured 2 458.79 W: the splitter's temperature copies are not closed at `x⁰`.
    splitter = next(c for c in general if c.id == "energy_balance.U-SPLIT")
    assert splitter.value is not None and round(splitter.value, 2) == 2458.79


def test_an_unpaired_legacy_id_is_reported(
    solved: tuple[dict[str, Any], RevisionBinding, ExecutionPlan, PlanResult],
    certificate: SolutionCertificate,
) -> None:
    """(d)'s failing control: with the splitter's pair withdrawn, coverage names the legacy id
    instead of passing it silently."""
    document, binding, _, run = solved
    assert run.state is not None
    _, projected = _projection(binding, document, run.state)
    legacy = _at_one_state(run_checks(_legacy(), run.state)[0], run_checks(_legacy(), projected)[0])
    pairs = _pairs(legacy)
    del pairs["energy_balance.splitter"]
    assert _uncovered(legacy, list(certificate.checks), pairs) == ["energy_balance.splitter"]


# -- refusals ----------------------------------------------------------------------------------


def test_another_revision_is_refused(
    solved: tuple[dict[str, Any], RevisionBinding, ExecutionPlan, PlanResult],
) -> None:
    document, binding, plan, run = solved
    other = shaped_revision()
    (entry,) = (s for s in other["specifications"] if s["id"] == "SPEC-flash-T")
    entry["value"] = 361.0
    with pytest.raises(VerifierError, match=r"^declaration_mismatch\(revision\)$"):
        verify_revision(binding, other, run, solve_plan=plan.steps[-1].solve_plan)


def test_verify_is_syn001s_only(
    solved: tuple[dict[str, Any], RevisionBinding, ExecutionPlan, PlanResult],
) -> None:
    _, binding, _, run = solved
    with pytest.raises(VerifierError, match=r"^syn001_only\(verify\)$"):
        verify(binding.flowsheet, run)  # type: ignore[arg-type]


# -- the false success it exists to reject -----------------------------------------------------


def test_the_trivial_root_is_a_detected_false_success() -> None:
    """(c) K04 §9.2 through the general path: the once-through shaped revision's root with S3's
    split forced all-liquid and both duties closed. The legacy set's three detections appear under
    their general ids, with the legacy values to the bit — the legacy set judged where the
    certificate judges (X22): the state passes every row, so the fresh-flash categories are
    judged at its projection, which is the state itself to roundoff (spec §5.6, 2)."""
    document = shaped_revision()
    (splitter,) = (i for i in document["instances"] if i["id"] == "U-SPLIT")
    splitter["parameters"]["split_fraction"]["value"] = 0.0
    (ratio,) = (s for s in document["specifications"] if s["id"] == "SPEC-splitter-r")
    ratio["value"] = 0.0
    binding, plan, run = _solve(document)
    assert run.state is not None
    state = dict(run.state)
    for component in "ABC":
        state[f"S3.liq.{component}"] = state[f"S3.n.{component}"]
        state[f"S3.vap.{component}"] = 0.0
    state["S3.L"] = sum(state[f"S3.n.{c}"] for c in "ABC")
    state["S3.V"] = 0.0
    state["U-HEAT.Q"] -= TRIVIAL_ROOT_OFFSET
    state["U-FLASH.Q"] += TRIVIAL_ROOT_OFFSET

    certificate = verify_revision(
        binding, document, run, state=state, solve_plan=plan.steps[-1].solve_plan
    )
    assert certificate.verification_status == "FAILED"
    assert certificate.false_success_detected
    by_id = {check.id: check for check in certificate.checks}
    failing = sorted(c.id for c in certificate.checks if c.result == "fail")
    assert failing == [
        "energy_balance.U-FLASH",
        "energy_balance.U-HEAT",
        "independent_split.U-HEAT.S3.A",
        "independent_split.U-HEAT.S3.B",
        "independent_split.U-HEAT.S3.C",
        "independent_split.U-HEAT.S3.total",
        "phase_admissibility.U-HEAT.S3.bubble",
    ]
    assert by_id["energy_balance.envelope"].result == "pass"
    assert by_id["energy_balance.enthalpy.S6"].result == "not_applicable"

    judged_at, projected = _projection(binding, document, state)
    assert judged_at == "projection"
    assert certificate.transformations["projection"]["judged_at"] == "projection"
    legacy = _at_one_state(
        run_checks(_legacy(split_fraction=0.0), state)[0],
        run_checks(_legacy(split_fraction=0.0), projected)[0],
    )
    old = {check.id: check.value for check in legacy}
    for legacy_id, general_id in (
        ("energy_balance.heater", "energy_balance.U-HEAT"),
        ("energy_balance.flash", "energy_balance.U-FLASH"),
        ("phase_admissibility.S3.bubble", "phase_admissibility.U-HEAT.S3.bubble"),
        ("independent_split.S3.total", "independent_split.U-HEAT.S3.total"),
    ):
        assert _bits(by_id[general_id].value) == _bits(old[legacy_id]), general_id
    assert by_id["energy_balance.U-HEAT"].value == pytest.approx(-TRIVIAL_ROOT_OFFSET, abs=1e-6)
    assert by_id["energy_balance.U-FLASH"].value == pytest.approx(TRIVIAL_ROOT_OFFSET, abs=1e-6)
    assert by_id["phase_admissibility.U-HEAT.S3.bubble"].value == pytest.approx(
        1.0703142190807741552 - 1.0, rel=1e-12
    )
    assert abs(by_id["independent_split.U-HEAT.S3.total"].value or 0.0) == pytest.approx(
        0.30410617028018327955, rel=1e-12
    )


# -- the table's generic machinery -------------------------------------------------------------


def test_a_model_without_an_entry_caps_the_verdict(
    solved: tuple[dict[str, Any], RevisionBinding, ExecutionPlan, PlanResult],
) -> None:
    """§4.3: one `unsupported` check, never a silent pass."""
    document, _, _, run = solved
    assert run.state is not None
    other = shaped_revision()
    (splitter,) = (i for i in other["instances"] if i["id"] == "U-SPLIT")
    splitter["model"]["id"] = "test.unknown"
    checks = _general_at(other, run.state)
    unsupported = [c for c in checks if c.result == "unsupported"]
    assert [(c.id, c.reason) for c in unsupported] == [
        ("material_balance.U-SPLIT.all", "model_unsupported(test.unknown)")
    ]
    assert not [c.id for c in checks if c.id.startswith("specification.U-SPLIT.")]
    assert "test.unknown" not in MODEL_CHECKS


def test_a_one_sided_check_is_judged_on_one_side_and_dormant_with_its_inlet(
    solved: tuple[dict[str, Any], RevisionBinding, ExecutionPlan, PlanResult],
) -> None:
    """§4.3: `value <= τ` passes however negative; near threshold on `τ/10 < value <= 10τ`."""
    document, _, _, run = solved
    assert run.state is not None
    (heater,) = (i for i in parse_revision(document).instances if i.unit_id == "U-HEAT")
    tolerances = CheckPolicy().tolerances
    unit = Unit(heater, run.state, {}, tolerances, energy_note="")
    tau = tolerances["heat_rate"]
    far_below = unit.one_sided("probe", -1e6, "heat_rate")
    assert (far_below.id, far_below.category) == (
        "bounds_and_domain.U-HEAT.probe",
        "bounds_and_domain",
    )
    assert (far_below.result, far_below.near_threshold) == ("pass", False)
    near = unit.one_sided("probe", 0.5 * tau, "heat_rate")
    assert (near.result, near.near_threshold) == ("pass", True)
    above = unit.one_sided("probe", 2.0 * tau, "heat_rate")
    assert (above.result, above.near_threshold) == ("fail", True)
    dormant_inlet = {**run.state, **{f"S2.n.{c}": 0.0 for c in "ABC"}}
    skipped = Unit(heater, dormant_inlet, {}, tolerances, energy_note="").one_sided(
        "probe", 1e6, "heat_rate"
    )
    assert (skipped.result, skipped.reason) == ("not_applicable", "ZERO_FLOW")
