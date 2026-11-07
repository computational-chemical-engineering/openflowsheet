"""OPT WO-4: `FullSpaceNlp` over a revision's held system (design §4.4, §4.2.1).

The primal is the held system's free columns (spec order), then the decisions; the equality rows
its rows, then its label rows; held columns are constants at their certified values. SYN-001's
path is unchanged (gate G2, `scripts/opt_m03_dump.py`). Default environment: no Ipopt.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest
from test_opt_revision_host import _certified

from openflowsheet.studies.nlp.formulation import (
    Decision,
    FullSpaceNlp,
    InequalityConstraint,
    NlpFormulation,
    QuadraticExpression,
)
from openflowsheet.studies.nlp.host import HeldSystem


def _formulation(host: Any, point: Any) -> NlpFormulation:
    (parameter,) = host.decisions.parameters.values()
    value = point.parameters[parameter]
    return NlpFormulation(
        problem_id="opt-wo4-full-space",
        decisions=(Decision(parameter, 0.5 * value, 1.5 * value, abs(value)),),
        objective=QuadraticExpression(linear={parameter: 1.0 / abs(value)}),
        constraints=(
            InequalityConstraint("T", QuadraticExpression(linear={"S3.T": 1.0}), 280.0, None),
        ),
        starts=((value,),),
    )


def test_the_primal_is_the_free_columns_then_the_decisions() -> None:
    host, point, _ = _certified("PHF")
    system = host.held_system(point)
    assert system.held, "the LIQUID PH flash holds its vapour side"
    nlp = FullSpaceNlp(host, _formulation(host, point), point, (1000.0,))
    assert set(nlp.variable_ids) == set(system.free)
    assert nlp.variable_ids == tuple(n for n in system.spec.variable_ids if n in set(system.free))
    assert not set(nlp.primal_ids) & set(system.held)
    assert nlp.primal_ids[len(nlp.variable_ids) :] == tuple(host.decisions.parameters.values())
    assert nlp.equality_ids == system.rows
    z = nlp.initial_point()
    x, decisions = nlp.split(z)
    # The full state vector: free columns from z, held columns at their certified values.
    for name, value in zip(system.spec.variable_ids, x, strict=True):
        assert value == point.state[name], name
    assert set(nlp.bounds) == set(nlp.primal_ids)
    residual = nlp.equality_residual(z)
    assert residual.shape == (len(nlp.variable_ids),)
    assert np.max(np.abs(residual * nlp.equality_scaling())) < 1e-8


def test_the_jacobian_is_the_restricted_twin_jacobian() -> None:
    host, point, _ = _certified("PHF")
    nlp = FullSpaceNlp(host, _formulation(host, point), point, (1000.0,))
    z = nlp.initial_point()
    jacobian = nlp.equality_jacobian(z).toarray()
    assert jacobian.shape == (len(nlp.equality_ids), len(nlp.primal_ids))
    scale = 1.0 / nlp.primal_scaling()
    for j in range(len(nlp.primal_ids)):
        h = 1e-6 * scale[j]
        up, down = z.copy(), z.copy()
        up[j] += h
        down[j] -= h
        column = (nlp.equality_residual(up) - nlp.equality_residual(down)) / (2 * h)
        np.testing.assert_allclose(jacobian[:, j], column, rtol=1e-5, atol=1e-6)


def test_label_rows_follow_the_held_rows() -> None:
    """A label row `x[t_out] − x[t_label]` is appended after the rows, its Jacobian `+1`/`−1` at
    the free columns (a held system with one row replaced by a label, square by construction)."""
    host, point, _ = _certified("PHF")
    system = host.held_system(point)
    temperatures = [n for n in system.free if system.spec.variable_kinds[n] == "temperature"]
    out, source = temperatures[-1], temperatures[0]
    labelled = HeldSystem(
        spec=system.spec,
        rows=system.rows[:-1],
        free=system.free,
        held=system.held,
        labels=(("label-test", out, source),),
        eliminated=system.eliminated,
        signature=system.signature,
    )
    original = host.held_system
    host.held_system = lambda _point: labelled  # type: ignore[method-assign]
    try:
        nlp = FullSpaceNlp(host, _formulation(host, point), point, (1000.0,))
    finally:
        host.held_system = original  # type: ignore[method-assign]
    assert nlp.equality_ids == (*system.rows[:-1], "label-test")
    z = nlp.initial_point()
    x, _ = nlp.split(z)
    index = {name: k for k, name in enumerate(system.spec.variable_ids)}
    assert nlp.equality_residual(z)[-1] == x[index[out]] - x[index[source]]
    row = nlp.equality_jacobian(z).toarray()[-1]
    expected = np.zeros(len(nlp.primal_ids))
    expected[nlp.primal_ids.index(out)] = 1.0
    expected[nlp.primal_ids.index(source)] = -1.0
    assert np.array_equal(row, expected)
    assert nlp.equality_scaling()[-1] == 1.0 / 100.0  # K03's temperature nominal


def test_the_bounds_are_the_hosts_over_the_free_columns() -> None:
    host, point, _ = _certified("PHF")
    nlp = FullSpaceNlp(host, _formulation(host, point), point, (1000.0,))
    expected = host.bounds(point)
    for name in nlp.variable_ids:
        assert nlp.bounds[name] == expected[name]
    (parameter,) = host.decisions.parameters.values()
    assert nlp.bounds[parameter].reason == "decision_box"


def test_a_revision_host_needs_the_starts_certified_point() -> None:
    host, point, _ = _certified("PHF")
    with pytest.raises(TypeError):
        FullSpaceNlp(host, _formulation(host, point), dict(point.state), (1000.0,))
