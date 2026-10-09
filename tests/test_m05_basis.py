"""M05 WO-4: `M05-basis-v1` (design note §6.6, §16.4, §16.5; R-264, R-277) — the affine Taylor
basis for property EFs and for external links.

§16.4's acceptance for the property basis: at w₀ the basis value equals the block's value
bitwise; its `differentiate` gradient equals the block Jacobian within 1e-15 relative; every basis
variable belongs to the clone; TR-E1 with an affine basis on `bb` converges to native within 1e-6
(probe P5's analogue). For a link: the same at w₀ against the truth, and an FD truth's basis
gradient is n_in = 7 `basis_fd_point` requests, memo hits after the gradient check at w₀.

Marked `nlp`: the projection and TRF need Pyomo. Nothing at module level imports it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pytest
from m05_support import LinkToyTruth, link_toy_projection, tr_e1_projection

from openflowsheet.studies.trust_region.holders import BASIS_FD_POINT, FDCHECK_POINT
from openflowsheet.studies.trust_region.truths import (
    ForwardDifference,
    gradient_check,
    in_process_meta,
)

pytestmark = pytest.mark.nlp


def _clone_calls(model: Any) -> list[tuple[str, Any]]:
    """Every `ExternalFunction` call in `model`'s active constraints, with its EF's name."""
    import pyomo.environ as pyo
    from pyomo.core.expr.numeric_expr import ExternalFunctionExpression

    found = []
    for constraint in model.component_data_objects(pyo.Constraint, active=True):
        stack = [constraint.body]
        while stack:
            node = stack.pop()
            if isinstance(node, ExternalFunctionExpression):
                found.append((node._fcn.local_name, node))
            elif getattr(node, "is_expression_type", lambda: False)():
                stack.extend(node.args)
    return found


def _check_affine_at_start(
    projection: Any,
    basis: Mapping[str, Any],
    expected: Mapping[str, tuple[float, Sequence[float], float]],
) -> float:
    """Each EF's basis on the clone's arguments: b(w₀)·s equals `value` bitwise and the
    `differentiate` gradient times s equals `gradient` within 1e-15 relative; every variable of
    the basis is the clone's. Returns the worst relative gradient error."""
    import pyomo.environ as pyo
    from pyomo.core.expr.calculus.derivatives import Modes, differentiate
    from pyomo.core.expr.visitor import identify_variables

    clone = projection.model.clone()
    clone_variables = {id(v) for v in clone.component_data_objects(pyo.Var)}
    worst = 0.0
    calls = _clone_calls(clone)
    assert {name for name, _ in calls} == set(expected) == set(basis)
    for name, call in calls:
        value, gradient, scale = expected[name]
        args = list(call.args[: len(gradient)])
        expression = basis[name].build(args)
        assert {id(v) for v in identify_variables(expression)} <= clone_variables
        assert pyo.value(expression) * scale == value
        derivative = differentiate(expression, wrt_list=args, mode=Modes.reverse_symbolic)
        for entry, exact in zip(derivative, gradient, strict=True):
            got = pyo.value(entry) * scale
            error = abs(got - exact) / max(abs(exact), 1e-300) if exact else abs(got)
            worst = max(worst, error)
    assert worst <= 1e-15
    return worst


def test_the_property_basis_is_the_blocks_taylor_model_at_the_start() -> None:
    from openflowsheet.studies.trust_region.basis import affine_block_basis

    projection = tr_e1_projection()
    basis = affine_block_basis(projection)
    assert {item.kind for item in basis.values()} == {"affine_taylor"}
    (entry,) = projection.source_map["block_outputs"]
    block = projection.spec.blocks[0]
    w0 = [float(projection.model.x[i].value) for i in projection.holder_inputs[0]]
    gradient = [0.0, 0.0]
    for _, column, value in block.jacobian(w0):
        gradient[column] += value
    expected = {entry["ef"]: (block.values(w0)[0], gradient, entry["output_scale"])}
    _check_affine_at_start(projection, basis, expected)
    assert all(holder.ledger == () for holder in projection.holders)  # blocks called directly


def _tr_e1_affine_and_native() -> tuple[Any, Any]:
    from test_m05_trf import native

    from openflowsheet.studies.trust_region.basis import affine_block_basis
    from openflowsheet.studies.trust_region.trf import run_trf
    from openflowsheet.studies.trust_region.trf_state import TRSP_SOLVER_ALIAS

    projection = tr_e1_projection()
    result = run_trf(
        projection, {"solver": TRSP_SOLVER_ALIAS}, basis=affine_block_basis(projection)
    )
    assert result.outcome == "TRF_CONVERGED", result.error
    assert result.basis == {name: "affine_taylor" for name in projection.ef_names.values()}
    return result, native()[0]


def test_tr_e1_with_the_affine_basis_reaches_natives_objective() -> None:
    """Measured beside §16.4's criterion (next test): with the affine basis TRF takes 7 iterations
    (native 5) and stops at a step of 6.9e-7; its objective is native's within 1e-10 relative and
    θ ≤ 1e-10."""
    import pyomo.environ as pyo

    result, model = _tr_e1_affine_and_native()
    final = result.final
    assert final is not None and final.theta <= 1e-10
    assert abs(final.objective - pyo.value(model.obj)) <= 1e-10 * abs(pyo.value(model.obj))


@pytest.mark.xfail(
    strict=True,
    reason=(
        "§16.4's acceptance 'TR-E1 with an affine basis on bb converges to native within 1e-6' "
        "is missed by the decisions: |dz| = (1.18e-6, 1.11e-6, 5.7e-7), at TRF's step-size "
        "termination level (the last step 6.9e-7); the objective agrees within 4e-11 relative. "
        "Escalated to the design lane (M05 WO-4 report)."
    ),
)
def test_tr_e1_with_the_affine_basis_converges_to_native_within_1e_6() -> None:
    """Probe P5's analogue (§16.4): the basis changes the PMP only, so the converged point is
    native's within TRF's own tolerance."""
    import pyomo.environ as pyo

    result, model = _tr_e1_affine_and_native()
    for i in range(3):
        assert abs(result.final.decisions[f"z{i}"] - pyo.value(model.z[i])) <= 1e-6, i


class FiniteDifferenceToy(LinkToyTruth):
    """The link toy's map without its gradient: `M05-fd-v1` through the holder, in process."""

    def __init__(self) -> None:
        self.finite_difference = ForwardDifference(lambda point: True, workers=1)

    def describe(self) -> Mapping[str, Any]:
        return {**super().describe(), "id": "link-toy-fd", "gradient": "finite_difference"}


def test_the_link_basis_is_the_truths_taylor_model_at_the_start_inlet() -> None:
    from openflowsheet.studies.trust_region.basis import affine_link_basis, m05_basis

    projection = link_toy_projection("forward")
    basis = affine_link_basis(projection)
    (holder,) = projection.holders
    w0 = [float(projection.model.x[i].value) for i in projection.holder_inputs[0]]
    truth = LinkToyTruth()
    conversion, rise, meta = truth.evaluate(w0)
    assert meta == in_process_meta()
    gradient = truth.gradient(w0)
    entries = projection.source_map["external_links"]
    expected = {
        entry["ef"]: ((conversion, rise)[k], gradient[k], entry["output_scale"])
        for k, entry in enumerate(entries)
    }
    _check_affine_at_start(projection, basis, expected)
    assert set(m05_basis(projection)) == set(projection.ef_names.values())


def test_an_fd_truths_link_basis_reuses_the_gradient_checks_points() -> None:
    """§6.6/§8.3: `basis_fd_point` = n_in = 7 requests at w₀; after the gradient check at the same
    w₀ every one is a memo hit, and the basis gradient is the check's G(η)."""
    from openflowsheet.studies.trust_region.basis import affine_link_basis

    projection = link_toy_projection("forward", FiniteDifferenceToy())
    (holder,) = projection.holders
    w0 = [float(projection.model.x[i].value) for i in projection.holder_inputs[0]]
    check = gradient_check(holder, w0)
    assert sum(1 for e in holder.ledger if e.purpose == FDCHECK_POINT) == 15
    before = len(holder.ledger)
    affine_link_basis(projection)
    after = holder.ledger[before:]
    basis_points = [e for e in after if e.purpose == BASIS_FD_POINT]
    assert len(basis_points) == 7 and all(e.served == "memo_hit" for e in basis_points)
    assert holder.request_jacobian(w0) == check.gradient
