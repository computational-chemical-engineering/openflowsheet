"""M05 WO-2b, WO-2c: rule `M05-zero-flow-v2` — the flows exactly 0.0 at x₀ are eliminated as
constants together with the rows that pin them, alone or as a certified square block (design note
§17.1, §18.1; R-296, R-326).

On toys with declared kinds (so R-275's scales apply and the `molar_flow` kind is known):
- a pinned zero flow and a chain behind it (a row whose only other unknown is an eliminated flow,
  visited before that flow's pin, so a second pass is needed) are eliminated; the pins are not
  rows, the flows are no `x`, the source map records both, DOF and G4 (a)-(e) hold on the rest;
- the three refusals of §17.1 step 3 — `unpinned` (the only pin depends on the decision),
  `redundant_row` (a second row on the eliminated flow alone) and `link_input` (an eliminated
  flow among an external link's inlet arguments) — with the acceptance's toy fixtures (§17.1 (e));
- the inverse map, the final-state pin check, `set_state` and `variable_bounds` (R-300 E5);
- R-326's joint stage: a 2 × 2 block certified (one of its rows reads a third unknown whose
  partial is 0.0 at x₀), and §18.1 (f)'s three toy refusals `joint_not_square`, `joint_singular`
  and `joint_not_persistent`.

Marked `nlp`: the projection needs Pyomo. Nothing at module level imports it.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from m05_support import (
    LINK_TOY_FEED,
    LINK_TOY_FLOWS,
    LINK_TOY_INLET,
    LINK_TOY_PRESSURE,
    LinkToyTruth,
)
from test_m05_projection import equivalence

from openflowsheet.compile.spec import EquationSpec, Expr, ProblemSpec

pytestmark = pytest.mark.nlp

#: The toy's start: `a` = z, `n0` = 0, `n1` = n0 (both exactly zero), `m` = a + n0 + n1.
START: Mapping[str, float] = {"a": 1.0, "n0": 0.0, "n1": 0.0, "m": 1.0}


def _row(name: str, build: Any) -> EquationSpec:
    return EquationSpec(name, build, "algebraic", f"zero-flow toy {name}")


def _objective(v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], a: Any) -> Expr:
    return (v["m"] - 1.2) ** 2


def toy_spec(
    pin: Any = None, extra: tuple[EquationSpec, ...] = (), copy: Any = None
) -> ProblemSpec:
    """`copy`: n1 − n0 (before n0's pin, so n1 pairs on the second pass; `copy` replaces it);
    `feed.n0`: n0's pin (`pin`, by default n0 − 0.0); `feed.a`: a − z; `mix`: m − a − n0 − n1;
    then `extra`."""
    rows = (
        _row("copy", copy or (lambda v, b, p, a: v["n1"] - v["n0"])),
        _row("feed.n0", pin or (lambda v, b, p, a: v["n0"] - 0.0)),
        _row("feed.a", lambda v, b, p, a: v["a"] - p["z"]),
        _row("mix", lambda v, b, p, a: v["m"] - v["a"] - v["n0"] - v["n1"]),
        *extra,
    )
    return ProblemSpec(
        label="M05-zero-flow-toy",
        variable_ids=tuple(START),
        equations=rows,
        parameter_ids=("z",),
        parameters={"z": 1.0},
        variable_kinds=dict.fromkeys(START, "molar_flow"),
        row_kinds={row.equation_id: "molar_flow" for row in rows},
    )


def toy_projection(spec: ProblemSpec | None = None, **options: Any) -> Any:
    from openflowsheet.studies.trust_region.projection import DecisionSpec, ObjectiveSpec, project

    return project(
        toy_spec() if spec is None else spec,
        START,
        decisions=[DecisionSpec("z", 0.5, 1.5)],
        objective=ObjectiveSpec("zero-flow-toy-objective", "minimize", _objective, 1.0),
        domain={},
        **options,
    )


def refusal(spec: ProblemSpec) -> str:
    from openflowsheet.studies.trust_region.projection import ProjectionRefusedError

    with pytest.raises(ProjectionRefusedError) as refused:
        toy_projection(spec)
    return refused.value.reason


def test_a_pinned_zero_flow_and_its_chain_are_eliminated_with_their_pins() -> None:
    projection = toy_projection()
    assert [
        (z["variable_id"], z["row_id"], z["residual_x0"], z["dr_dx"])
        for z in projection.source_map["zero_eliminated"]
    ] == [("n0", "feed.n0", 0.0, 1.0), ("n1", "copy", 0.0, 1.0)]
    assert projection.row_ids == ("feed.a", "mix")
    assert projection.variable_indices == (0, 3)
    assert sorted(projection.model.x) == [0, 3]
    shape = projection.source_map["shape_check"]
    assert (shape["matched"], shape["size"], shape["refusal"]) == (2, 2, None)
    measured = equivalence(projection, START)  # G4 (a)-(e), DOF included, on the projected part
    assert measured["residual_bitwise"] == 1.0 and measured["pin"] <= 1.0


def test_the_inverse_map_writes_plus_zero_and_the_pins_hold_at_a_state() -> None:
    import math

    import pyomo.environ as pyo

    projection = toy_projection()
    state = projection.state_of()
    assert state == {"a": 1.0, "n0": 0.0, "n1": 0.0, "m": 1.0}
    assert all(math.copysign(1.0, state[name]) == 1.0 for name in ("n0", "n1"))
    projection.model.x[0].set_value(1.1)
    projection.model.x[3].set_value(1.1)
    check = projection.zero_pins_at(projection.model)
    assert (check.status, dict(check.residuals)) == ("pass", {"copy": 0.0, "feed.n0": 0.0})
    assert pyo.value(projection.model.x[3]) == 1.1


def test_set_state_keeps_an_eliminated_flow_at_zero() -> None:
    projection = toy_projection()
    projection.set_state({"a": 1.1, "n0": 0.0, "n1": -0.0, "m": 1.1})
    assert projection.state_of() == {"a": 1.1, "n0": 0.0, "n1": 0.0, "m": 1.1}
    with pytest.raises(ValueError, match="eliminated zero flows"):
        projection.set_state({"a": 1.1, "n0": 1e-27, "n1": 0.0, "m": 1.1})


def test_a_bound_on_an_eliminated_flow_is_a_value_error() -> None:
    """R-300 E5: `variable_bounds` may not name an eliminated zero flow."""
    with pytest.raises(ValueError, match="eliminated zero flows"):
        toy_projection(variable_bounds={"n1": (0.0, 1.0)})


def decision_pin(
    v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], a: Any
) -> Expr:
    """§17.1 (e): n0's pin, with a nonzero decision tangent at x₀ (criterion iii)."""
    return v["n0"] - 0.5 * (p["z"] - 1.0)


def test_a_zero_flow_pinned_by_a_decision_dependent_row_is_unpinned() -> None:
    """§17.1 (e), with n1's only row also reading m (∂/∂m = 1 at x₀), so no row is a joint
    candidate either (§18.1): n0 and n1 stay unpaired, and the first is named."""
    spec = toy_spec(pin=decision_pin, copy=lambda v, b, p, a: v["n1"] - v["n0"] + (v["m"] - v["a"]))
    assert refusal(spec) == "PROJECTION_ZERO_FLOW(n0:unpinned)"


def test_a_decision_dependent_pin_leaves_a_non_square_joint_block() -> None:
    """§17.1 (e)'s original fixture under `M05-zero-flow-v2` (M05 build log S27): with n0's pin
    decision-dependent, `copy` (n1 − n0) is a joint candidate on {n0, n1} alone, a 1 × 2 block,
    refused by §18.1 step 3 (a)."""
    assert refusal(toy_spec(pin=decision_pin)) == "PROJECTION_ZERO_FLOW(n0:joint_not_square)"


def test_a_second_row_on_an_eliminated_flow_alone_is_redundant() -> None:
    """§17.1 (e): `dup` reads only n0, which `feed.n0` already pins."""
    spec = toy_spec(extra=(_row("dup", lambda v, b, p, a: 2.0 * v["n0"]),))
    assert refusal(spec) == "PROJECTION_ZERO_FLOW(dup:redundant_row)"


def test_an_eliminated_flow_among_a_links_inlet_is_refused() -> None:
    """§17.1 (e): the link toy with declared kinds and its NH₃ feed exactly 0.0: the feed row
    pins it, and it is an inlet argument of the external link."""
    from m05_support import _link_toy_energy, _link_toy_heater, _link_toy_objective

    from openflowsheet.studies.trust_region.projection import (
        DecisionSpec,
        ExternalLinkSpec,
        ObjectiveSpec,
        ProjectionRefusedError,
        project,
    )

    feed = {**LINK_TOY_FEED, "n_NH3": 0.0}

    def feed_row(name: str) -> EquationSpec:
        return _row(f"feed.{name}", lambda v, b, p, a: v[name] - feed[name])

    rows = (
        *(feed_row(name) for name in LINK_TOY_FLOWS),
        _row("pressure", lambda v, b, p, a: v["P"] - LINK_TOY_PRESSURE),
        EquationSpec("heater", _link_toy_heater, "algebraic", "link toy heater"),
        EquationSpec("energy", _link_toy_energy, "algebraic", "link toy energy balance"),
    )
    kinds = {
        **dict.fromkeys(LINK_TOY_FLOWS, "molar_flow"),
        "T_in": "temperature",
        "T_out": "temperature",
        "P": "pressure",
    }
    spec = ProblemSpec(
        label="M05-zero-flow-link-toy",
        variable_ids=(*LINK_TOY_INLET, "T_out"),
        equations=rows,
        parameter_ids=("z", "R.X", "R.dT"),
        parameters={"z": 1.0, "R.X": 0.2, "R.dT": 70.0},
        variable_kinds=kinds,
        row_kinds={
            **{f"feed.{name}": "molar_flow" for name in LINK_TOY_FLOWS},
            "pressure": "pressure",
            "heater": "temperature",
            "energy": "temperature",
        },
    )
    start = {**feed, "P": LINK_TOY_PRESSURE, "T_in": 680.0, "T_out": 750.0}
    with pytest.raises(ProjectionRefusedError) as refused:
        project(
            spec,
            start,
            decisions=[DecisionSpec("z", 0.9, 1.1)],
            objective=ObjectiveSpec("link-toy-objective", "minimize", _link_toy_objective, 1.0),
            domain={"temperature": (200.0, 1000.0), "pressure": (1e4, 3e7)},
            external_links=[ExternalLinkSpec("R", "R.X", "R.dT", LINK_TOY_INLET, LinkToyTruth())],
        )
    assert refused.value.reason == "PROJECTION_ZERO_FLOW(n_NH3:link_input)"


def test_the_affine_basis_has_no_term_for_a_constant_argument() -> None:
    """§17.1 step 4: the affine basis builds terms only for variable arguments; a constant must
    equal its start value (it is the eliminated flow's +0.0)."""
    import pyomo.environ as pyo

    from openflowsheet.studies.trust_region.basis import affine

    model = pyo.ConcreteModel()
    model.v = pyo.Var(initialize=2.0)
    basis = affine(1.0, [3.0, -5.0], [2.0, 0.0], 4.0)
    expression = basis.build([model.v, 0.0])
    assert [v.name for v in pyo.expr.identify_variables(expression)] == ["v"]
    assert pyo.value(expression) == 0.25
    with pytest.raises(ValueError, match="differs from its start value"):
        basis.build([model.v, 1e-27])


# -- R-326: the joint stage (§18.1) ---------------------------------------------------------------

#: The joint toy's start: the toy's, two more flows exactly zero, and `y` = 2a.
JOINT_START: Mapping[str, float] = {**START, "z1": 0.0, "z2": 0.0, "y": 2.0}


def joint_spec(*joint: EquationSpec) -> ProblemSpec:
    """The toy's rows, `ydef`: y − 2a, then `joint`, the rows on z1 and z2."""
    rows = (
        *toy_spec().equations,
        _row("ydef", lambda v, b, p, a: v["y"] - 2.0 * v["a"]),
        *joint,
    )
    return ProblemSpec(
        label="M05-zero-flow-joint-toy",
        variable_ids=tuple(JOINT_START),
        equations=rows,
        parameter_ids=("z",),
        parameters={"z": 1.0},
        variable_kinds=dict.fromkeys(JOINT_START, "molar_flow"),
        row_kinds={row.equation_id: "molar_flow" for row in rows},
    )


def joint_projection(*joint: EquationSpec) -> Any:
    from openflowsheet.studies.trust_region.projection import DecisionSpec, ObjectiveSpec, project

    return project(
        joint_spec(*joint),
        JOINT_START,
        decisions=[DecisionSpec("z", 0.5, 1.5)],
        objective=ObjectiveSpec("zero-flow-toy-objective", "minimize", _objective, 1.0),
        domain={},
    )


#: §18.1 (f): one fixture per joint refusal, each naming the block's first variable, z1.
JOINT_REFUSALS: Mapping[str, tuple[EquationSpec, ...]] = {
    "joint_not_square": (_row("tie", lambda v, b, p, a: v["z1"] - v["z2"]),),
    "joint_singular": (
        _row("j1", lambda v, b, p, a: v["z1"] + v["z2"]),
        _row("j2", lambda v, b, p, a: 2.0 * v["z1"] + 2.0 * v["z2"]),
    ),
    # Every criterion but (c) holds at x₀: ∂j2/∂y = 2(y − y₀) = 0.0 there, so N_e = {z1, z2}.
    "joint_not_persistent": (
        _row("j1", lambda v, b, p, a: v["z1"] - v["z2"]),
        _row("j2", lambda v, b, p, a: v["z1"] + v["z2"] + (v["y"] - 2.0) ** 2),
    ),
}


def test_a_certified_joint_block_is_eliminated_with_its_rows() -> None:
    """j1: z1 − z2 and j2: z1 + z2·y pin z1 and z2 only jointly; j2 also reads y, whose partial
    z2 is 0.0 at x₀. One 2 × 2 block, certified; DOF, matching and G4 hold on the rest, and the
    block's rows are checked at a final state with the pins."""
    from openflowsheet.studies.trust_region.projection import ZERO_FLOW_RULE

    assert ZERO_FLOW_RULE == "M05-zero-flow-v2"
    projection = joint_projection(
        _row("j1", lambda v, b, p, a: v["z1"] - v["z2"]),
        _row("j2", lambda v, b, p, a: v["z1"] + v["z2"] * v["y"]),
    )
    source = projection.source_map
    assert [(z["variable_id"], z["row_id"], z.get("block")) for z in source["zero_eliminated"]] == [
        ("n0", "feed.n0", None),
        ("n1", "copy", None),
        ("z1", None, 0),
        ("z2", None, 0),
    ]
    (block,) = source["zero_blocks"]
    assert {key: block[key] for key in ("block", "variables", "rows", "residuals_x0")} == {
        "block": 0,
        "variables": ["z1", "z2"],
        "rows": ["j1", "j2"],
        "residuals_x0": [0.0, 0.0],
    }
    # Scaled by the unit molar_flow nominals, J_B = [[1, -1], [1, 2]]: σ_min/σ_max is exact here.
    assert block["persistence_max_abs"] == 0.0 and block["rcond"] >= 0.3
    assert projection.row_ids == ("feed.a", "mix", "ydef")
    shape = source["shape_check"]
    assert (shape["matched"], shape["size"], shape["refusal"]) == (3, 3, None)
    measured = equivalence(projection, JOINT_START)
    assert measured["residual_bitwise"] == 1.0 and measured["joint"] <= 1.0
    check = projection.zero_pins_at(projection.model)
    assert check.status == "pass"
    assert dict(check.residuals) == {"copy": 0.0, "feed.n0": 0.0, "j1": 0.0, "j2": 0.0}


def test_a_toy_without_a_joint_block_keeps_its_source_map_bytes() -> None:
    """§18.1 step 7: `zero_blocks` is written only when a block exists."""
    assert "zero_blocks" not in toy_projection().source_map


@pytest.mark.parametrize("reason", sorted(JOINT_REFUSALS))
def test_each_joint_refusal_names_the_block_s_first_variable(reason: str) -> None:
    from openflowsheet.studies.trust_region.projection import ProjectionRefusedError

    with pytest.raises(ProjectionRefusedError) as refused:
        joint_projection(*JOINT_REFUSALS[reason])
    assert refused.value.reason == f"PROJECTION_ZERO_FLOW(z1:{reason})"
