"""M05 WO-8b: `SurrogateTruth` and the promoted link basis (design note §6.4, §6.6, §20.5, §20.7;
R-407, R-408), with WO-4's acceptance (§12): the basis expression agrees with M04's
`QuadraticSurrogate.predict` at M04's J1-J3 within 1e-14 relative, and the truth keeps §16.4's
`meta` contract.

The surrogate is M04.A19's committed PROMOTABLE manifest of `m04-synthetic-smooth-v1` (F-22). J1-J3
are M04's registered Jacobian states (`benchmarks/m04/reference_values.json` → `jacobian_states`,
each with its own N_tubes).

Default gate, except the one test marked `nlp` that builds the expression on Pyomo variables.
"""

from __future__ import annotations

import copy
import json
import math
import sys
from collections.abc import Mapping, Sequence
from types import SimpleNamespace
from typing import Any

import pytest
from conftest import REPO_ROOT

from openflowsheet.studies.surrogate.plan import coordinates, scaled
from openflowsheet.studies.surrogate.quadratic import inlet_sensitivity
from openflowsheet.studies.surrogate.reactor import surrogate_of
from openflowsheet.studies.trust_region.basis import (
    surrogate_expression,
    surrogate_link_basis,
)
from openflowsheet.studies.trust_region.holders import TruthBox
from openflowsheet.studies.trust_region.truths import (
    SURROGATE,
    SurrogateTruth,
    in_process_meta,
)
from openflowsheet.thermo import StreamState

sys.path.insert(0, str(REPO_ROOT / "tests" / "support"))
import m04_synthetic_parents as parents  # noqa: E402

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "schemas" / "surrogate_manifest" / "valid"
A19_PATH = FIXTURES / "a19_smooth_prefix.json"
A19: Mapping[str, Any] = json.loads(A19_PATH.read_text(encoding="utf-8"))
SMOOTH = parents.synthetic_variant(parents.SMOOTH_ID)
ROUGH = parents.synthetic_variant(parents.ROUGH_ID)
STATES = {
    state["id"]: state
    for state in json.loads(
        (REPO_ROOT / "benchmarks" / "m04" / "reference_values.json").read_text(encoding="utf-8")
    )["jacobian_states"]
    if state["id"] in ("J1", "J2", "J3")
}
#: WO-4's acceptance (§6.6): the compiled quadratic against `predict`, relative.
AGREEMENT = 1e-14


def inlet(state_id: str) -> tuple[float, ...]:
    item = STATES[state_id]["inlet"]
    return (*(float(n) for n in item["n"]), float(item["T"]), float(item["P"]))


def n_tubes(state_id: str) -> float:
    return float(STATES[state_id]["n_tubes"])


def stream(w: Sequence[float]) -> StreamState:
    return StreamState(n=tuple(w[:5]), temperature=w[5], pressure=w[6])


def predicted(w: Sequence[float], tubes: float) -> tuple[float, float]:
    """M04's own prediction at w: `predict(z(s))` on the manifest's scaling."""
    surrogate = surrogate_of(A19)
    u = coordinates(stream(w), tubes)
    assert u is not None
    return surrogate.predict(scaled(u, surrogate.scaling))


def relative(got: float, exact: float) -> float:
    return abs(got - exact) / abs(exact)


@pytest.mark.parametrize("state_id", sorted(STATES))
def test_the_truth_is_m04s_prediction_and_sensitivity_with_the_in_process_meta(
    state_id: str,
) -> None:
    """§6.4: values `predict(z(s))`, gradient M04's `inlet_sensitivity`, both bitwise (the same
    calls); §16.4's `meta` of a truth that is not a parent experiment."""
    truth = SurrogateTruth(A19, SMOOTH, n_tubes(state_id))
    w = inlet(state_id)
    x, dt, meta = truth.evaluate(w)
    assert (x, dt) == predicted(w, n_tubes(state_id))
    assert dict(meta) == in_process_meta()
    found = inlet_sensitivity(truth.surrogate, stream(w), n_tubes(state_id))
    assert found is not None
    assert tuple(map(tuple, truth.gradient(w))) == (found.dx_ds, found.ddt_ds)


def test_the_truth_describes_itself_and_never_counts_as_a_parent_experiment() -> None:
    truth = SurrogateTruth(A19, SMOOTH, 1000.0)
    identity = dict(truth.describe())
    assert identity == {
        "kind": SURROGATE,
        "id": A19["surrogate_id"],
        "sha256": truth.sha256,
        "synthetic": True,
        "gradient": "analytic",
    }
    box = TruthBox(truth)
    assert box.parent is False and box.finite_difference is None


def test_only_a_promoted_surrogate_of_the_bound_parent_is_a_truth() -> None:
    with pytest.raises(ValueError, match="not of the bound parent"):
        SurrogateTruth(A19, ROUGH, 1000.0)
    demoted = copy.deepcopy(dict(A19))
    demoted["promotion"]["verdict"] = "NOT_PROMOTABLE"
    with pytest.raises(ValueError, match="NOT_PROMOTABLE, not promoted"):
        SurrogateTruth(demoted, SMOOTH, 1000.0)


@pytest.mark.parametrize(
    ("edit", "code"),
    [
        ({1: 0.0}, "surrogate_input_undefined"),
        ({5: 780.0}, "surrogate_outside_hard_domain"),
    ],
)
def test_the_truth_refuses_where_m04s_unit_refuses(edit: Mapping[int, float], code: str) -> None:
    """The M04 unit's refusals, `out_of_domain` with its code, NaN values (module docstring)."""
    truth = SurrogateTruth(A19, SMOOTH, 1.0)
    w = list(inlet("J1"))
    for index, value in edit.items():
        w[index] = value
    x, dt, meta = truth.evaluate(w)
    assert math.isnan(x) and math.isnan(dt)
    assert meta["status"] == "out_of_domain" and meta["code"] == code


def test_an_inadmissible_prediction_is_refused() -> None:
    """A(s) (M04 spec §3.2): β_X[0] = 0.96 puts X̃ above 0.95 at J1."""
    shifted = copy.deepcopy(dict(A19))
    shifted["predictor"]["coefficients"]["X"][0] = 0.96
    x, _, meta = SurrogateTruth(shifted, SMOOTH, 1.0).evaluate(inlet("J1"))
    assert math.isnan(x) and meta["code"] == "surrogate_output_inadmissible"


@pytest.mark.parametrize("state_id", sorted(STATES))
def test_the_compiled_quadratic_on_floats_agrees_with_predict(state_id: str) -> None:
    """WO-4 (§6.6): the expression's arithmetic against `predict`'s `math.fsum`, ≤ 1e-14."""
    surrogate = surrogate_of(A19)
    w = inlet(state_id)
    exact = predicted(w, n_tubes(state_id))
    got = (
        surrogate_expression(surrogate.coefficients_x, surrogate, n_tubes(state_id), list(w)),
        surrogate_expression(surrogate.coefficients_dt, surrogate, n_tubes(state_id), list(w)),
    )
    assert max(relative(g, e) for g, e in zip(got, exact, strict=True)) <= AGREEMENT


def _projection(w0: Sequence[float], scales: Sequence[float]) -> Any:
    """The three members of a projection `surrogate_link_basis` reads."""
    ids = [f"S5.{name}" for name in ("n.H2", "n.N2", "n.NH3", "n.Ar", "n.CH4", "T", "P")]
    return SimpleNamespace(
        state_of=lambda: dict(zip(ids, w0, strict=True)),
        holders=[SimpleNamespace(name="link:reactor")],
        source_map={
            "external_links": [
                {
                    "unit_id": "reactor",
                    "ef": f"ef_ext_{k}",
                    "coordinate": coordinate,
                    "input_variable_ids": ids,
                    "output_scale": scale,
                }
                for k, (coordinate, scale) in enumerate(zip(("X", "dT"), scales, strict=True))
            ]
        },
    )


def test_the_link_basis_is_the_quadratic_in_the_efs_scaled_units() -> None:
    """R-408: one `surrogate` basis per link output, X then ΔT, divided by its output scale; it
    asks no holder anything (the fake holder has no request method)."""
    surrogate = surrogate_of(A19)
    w = inlet("J2")
    scales = (0.25, 128.0)
    basis = surrogate_link_basis(_projection(w, scales), surrogate, n_tubes("J2"))
    assert {name: item.kind for name, item in basis.items()} == {
        "ef_ext_0": "surrogate",
        "ef_ext_1": "surrogate",
    }
    exact = predicted(w, n_tubes("J2"))
    for k, name in enumerate(("ef_ext_0", "ef_ext_1")):
        assert relative(basis[name].build(list(w)) * scales[k], exact[k]) <= AGREEMENT


@pytest.mark.nlp
@pytest.mark.parametrize("state_id", sorted(STATES))
def test_the_compiled_quadratic_on_pyomo_variables_agrees_with_predict(state_id: str) -> None:
    """WO-4's acceptance on Pyomo variables, as TRF's clone holds them: the expression's value
    against `predict` within 1e-14 relative, every variable of it one of the arguments, and its
    symbolic gradient against M04's `inlet_sensitivity` (reported bound 1e-12 relative)."""
    import pyomo.environ as pyo
    from pyomo.core.expr.calculus.derivatives import Modes, differentiate
    from pyomo.core.expr.visitor import identify_variables

    surrogate = surrogate_of(A19)
    w = inlet(state_id)
    tubes = n_tubes(state_id)
    model = pyo.ConcreteModel()
    model.w = pyo.Var(range(7), initialize=dict(enumerate(w)))
    args = [model.w[k] for k in range(7)]
    exact = predicted(w, tubes)
    sensitivity = inlet_sensitivity(surrogate, stream(w), tubes)
    assert sensitivity is not None
    for coefficients, value, gradient in (
        (surrogate.coefficients_x, exact[0], sensitivity.dx_ds),
        (surrogate.coefficients_dt, exact[1], sensitivity.ddt_ds),
    ):
        expression = surrogate_expression(coefficients, surrogate, tubes, args)
        assert {id(v) for v in identify_variables(expression)} <= {id(a) for a in args}
        assert relative(pyo.value(expression), value) <= AGREEMENT
        derivative = differentiate(expression, wrt_list=args, mode=Modes.reverse_symbolic)
        scale = max(abs(g) for g in gradient)
        for entry, g in zip(derivative, gradient, strict=True):
            assert abs(pyo.value(entry) - g) <= 1e-12 * scale
