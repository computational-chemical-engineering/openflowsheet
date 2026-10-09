"""Shared helpers for the M05 tests (design note `docs/design/M05-trust-region.md`).

TR-E1 (§5.1) is Eason & Biegler's example 1 — Pyomo's `contrib/trustregion/examples/example1.py`
— written as a `ProblemSpec`: variables `x0`, `x1`; pinned inputs `z0`, `z1`, `z2`, which are the
decisions (unbounded, so the scaled decision is the parameter); one `PropertyBlock` `bb` with the
example's black box `s = sin(x0 − x1)` and its Jacobian `(cos, −cos)`; the rows `c1` and `c2`; the
example's objective as an `ObjectiveSpec`. Nothing here imports Pyomo; `run_native_example1` and
the projection helpers import it inside the call, for the `nlp`-marked tests only.

The SYN-001 configuration of G4 (`syn001_*`) projects M03's registered states (P1-P3, B1-B3;
M03 spec §4.2, §4.6) with M03's five registered pinned inputs as decisions in a box that contains
every one of those states, NLP-1's objective and NLP-1's inequality (M03 spec §8.1). The box is
a test configuration of the equivalence gate, not a study registration.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any, Final

from openflowsheet.compile.spec import EquationSpec, Expr, ProblemSpec

# -- TR-E1 ----------------------------------------------------------------------------------------

TR_E1_LABEL: Final = "M05-TR-E1-eason-example-1"
TR_E1_START: Final[Mapping[str, float]] = {"x0": 2.0, "x1": 1.0}
TR_E1_DECISIONS: Final = ("z0", "z1", "z2")
#: Design note §4 P1: the native example under Pyomo's defaults with the `ipopt` executable on
#: `PATH` (a probe, not evidence; G3 compares against the native example run in the same process).
PROBE_P1: Final[Mapping[str, float]] = {
    "z0": 1.286931683273266,
    "z1": 1.4802348006326804,
    "z2": 1.3794547317539292,
    "x0": 1.3219485331078022,
    "x1": 0.628718497180208,
    "objective": 0.27704478876374156,
}


class SineBlock:
    """Example 1's black box, `s = sin(a − b)`, as a `PropertyBlock`."""

    block_id = "bb"
    input_ids = ("a", "b")
    output_ids = ("s",)

    def __init__(self) -> None:
        self.value_calls = 0
        self.jacobian_calls = 0

    def jacobian_pattern(self) -> tuple[tuple[int, int], ...]:
        return ((0, 0), (0, 1))

    def values(self, inputs: Sequence[float]) -> Sequence[float]:
        self.value_calls += 1
        a, b = inputs
        return [math.sin(a - b)]

    def jacobian(self, inputs: Sequence[float]) -> Sequence[tuple[int, int, float]]:
        self.jacobian_calls += 1
        a, b = inputs
        return [(0, 0, math.cos(a - b)), (0, 1, -math.cos(a - b))]


def _c1(v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], algebra: Any) -> Expr:
    return v["x0"] * p["z0"] ** 2 + b["bb.s"] - 2.0 * math.sqrt(2.0)


def _c2(v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], algebra: Any) -> Expr:
    return p["z2"] ** 4 * p["z1"] ** 2 + p["z1"] - (8.0 + math.sqrt(2.0))


def tr_e1_objective_build(
    v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], algebra: Any
) -> Expr:
    """Example 1's objective, term for term."""
    return (
        (p["z0"] - 1.0) ** 2
        + (p["z0"] - p["z1"]) ** 2
        + (p["z2"] - 1.0) ** 2
        + (v["x0"] - 1.0) ** 4
        + (v["x1"] - 1.0) ** 6
    )


def tr_e1_spec(block: SineBlock | None = None) -> ProblemSpec:
    sine = block if block is not None else SineBlock()
    return ProblemSpec(
        label=TR_E1_LABEL,
        variable_ids=("x0", "x1"),
        equations=(
            EquationSpec("c1", _c1, "algebraic", "TR-E1 c1"),
            EquationSpec("c2", _c2, "algebraic", "TR-E1 c2"),
        ),
        parameter_ids=TR_E1_DECISIONS,
        parameters={"z0": 2.0, "z1": 2.0, "z2": 2.0},
        blocks=(sine,),
        block_inputs={"bb": ("x0", "x1")},
    )


def tr_e1_projection(block: SineBlock | None = None) -> Any:
    from openflowsheet.studies.trust_region.projection import (
        DecisionSpec,
        ObjectiveSpec,
        project,
    )

    return project(
        tr_e1_spec(block),
        TR_E1_START,
        decisions=[DecisionSpec(name, None, None) for name in TR_E1_DECISIONS],
        objective=ObjectiveSpec("tr-e1-objective", "minimize", tr_e1_objective_build, 1.0),
        domain={},
        shape_check="exempt_oracle",
    )


# -- SYN-001 (G4) ---------------------------------------------------------------------------------

#: M03's registered states with a certified solution (spec §4.2, §4.6).
SYN001_STATES: Final = ("P1", "P2", "P3", "B1", "B2", "B3")
#: The G4 decision box: M03's registered pinned inputs, each box containing every state above.
SYN001_DECISION_BOX: Final[Mapping[str, tuple[float, float]]] = {
    "U-SPLIT.split_fraction": (0.25, 0.97),
    "U-FLASH.T_spec": (340.0, 370.0),
    "U-HEAT.T_spec": (330.0, 370.0),
    "U-FEED.T_spec": (290.0, 310.0),
    "U-FEED.n_spec.A": (0.5, 1.5),
}
#: M03 spec §8.1's NLP-1 recovery coefficient.
NLP1_RECOVERY: Final = 0.75


def nlp1_objective_build(
    v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], algebra: Any
) -> Expr:
    """M03 spec §8.1: φ = (Q_h + Q_f)/1e5 + 100 (Q_h/1e5)²."""
    return (v["U-HEAT.Q"] + v["U-FLASH.Q"]) / 1e5 + 100.0 * (v["U-HEAT.Q"] / 1e5) ** 2


def nlp1_recovery_build(
    v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], algebra: Any
) -> Expr:
    """M03 spec §8.1: g = (S4.n.A − 0.75 · S1.n.A)/3 ≥ 0."""
    return (v["S4.n.A"] - NLP1_RECOVERY * v["S1.n.A"]) / 3.0


# -- AT: a pressure alias toy (R-274) -------------------------------------------------------------

#: Three pressure rows over two pressures — `Pa = p_spec`, `Pb = Pa`, `Pb = p_spec2` — of which the
#: third is implied by the first two whenever p_spec2 = p_spec; `T = 300 z`; and `Q = y(T)` through
#: a block, `y = T²/1000`. The decision is `z`, and optionally `p_spec`. The objective
#: (Q − 96.1)²/100 has its minimum at T = 310 K, z = 31/30.
AT_LABEL: Final = "M05-AT-pressure-alias-toy"
AT_START: Final[Mapping[str, float]] = {"Pa": 1.0e5, "Pb": 1.0e5, "T": 300.0, "Q": 90.0}
AT_PARAMETERS: Final[Mapping[str, float]] = {"p_spec": 1.0e5, "p_spec2": 1.0e5, "z": 1.0}
AT_DOMAIN: Final[Mapping[str, tuple[float, float]]] = {
    "pressure": (5.0e4, 2.0e5),
    "temperature": (200.0, 1000.0),
}


class SquareBlock:
    """`y = T²/1000` as a `PropertyBlock`."""

    block_id = "sq"
    input_ids = ("T",)
    output_ids = ("y",)

    def jacobian_pattern(self) -> tuple[tuple[int, int], ...]:
        return ((0, 0),)

    def values(self, inputs: Sequence[float]) -> Sequence[float]:
        (t,) = inputs
        return [t * t / 1000.0]

    def jacobian(self, inputs: Sequence[float]) -> Sequence[tuple[int, int, float]]:
        (t,) = inputs
        return [(0, 0, 2.0 * t / 1000.0)]


def _at_r1(v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], a: Any) -> Expr:
    return v["Pa"] - p["p_spec"]


def _at_r2(v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], a: Any) -> Expr:
    return v["Pb"] - v["Pa"]


def _at_r3(v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], a: Any) -> Expr:
    return v["Pb"] - p["p_spec2"]


def _at_r4(v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], a: Any) -> Expr:
    return v["T"] - 300.0 * p["z"]


def _at_r5(v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], a: Any) -> Expr:
    return v["Q"] - b["sq.y"]


def at_objective_build(
    v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], algebra: Any
) -> Expr:
    return (v["Q"] - 96.1) ** 2 / 100.0


def at_spec(**parameters: float) -> ProblemSpec:
    return ProblemSpec(
        label=AT_LABEL,
        variable_ids=("Pa", "Pb", "T", "Q"),
        equations=(
            EquationSpec("r1", _at_r1, "algebraic", "AT r1"),
            EquationSpec("r2", _at_r2, "algebraic", "AT r2"),
            EquationSpec("r3", _at_r3, "algebraic", "AT r3"),
            EquationSpec("r4", _at_r4, "algebraic", "AT r4"),
            EquationSpec("r5", _at_r5, "algebraic", "AT r5"),
        ),
        parameter_ids=("p_spec", "p_spec2", "z"),
        parameters={**AT_PARAMETERS, **parameters},
        blocks=(SquareBlock(),),
        block_inputs={"sq": ("T",)},
        variable_kinds={"Pa": "pressure", "Pb": "pressure", "T": "temperature", "Q": "heat_rate"},
        row_kinds={
            "r1": "pressure",
            "r2": "pressure",
            "r3": "pressure",
            "r4": "temperature",
            "r5": "heat_rate",
        },
    )


def at_projection(
    *,
    start: Mapping[str, float] = AT_START,
    decisions: Mapping[str, tuple[float, float]] | None = None,
    domain: Mapping[str, tuple[float, float]] = AT_DOMAIN,
    omitted_rows: Sequence[str] | None = None,
    **parameters: float,
) -> Any:
    from openflowsheet.studies.trust_region.projection import DecisionSpec, ObjectiveSpec, project

    boxes = {"z": (0.5, 1.5)} if decisions is None else decisions
    return project(
        at_spec(**parameters),
        start,
        decisions=[DecisionSpec(name, *box) for name, box in boxes.items()],
        objective=ObjectiveSpec("at-objective", "minimize", at_objective_build, 1.0),
        domain=domain,
        omitted_rows=omitted_rows,
    )


# -- R-278: the shape-check toys ------------------------------------------------------------------

#: An external link `R` on seven inlet variables, with an energy balance `T_out = T_in + ΔT̂`. In
#: the forward shape a heater row fixes `T_in = 680 z`, so the glass box determines the link's
#: inlet and the link determines ΔT̂. In the implicit shape (probe P14's `y − 90 z`) a row pins the
#: link output by the decision alone, `ΔT̂ − 90 z = 0`: ΔT̂ is over-determined, and `T_in` — a
#: link-EF input — is fixed only by inverting the link.
LINK_TOY_FLOWS: Final = ("n_H2", "n_N2", "n_NH3", "n_Ar", "n_CH4")
LINK_TOY_FEED: Final[Mapping[str, float]] = {
    "n_H2": 3.0,
    "n_N2": 1.0,
    "n_NH3": 0.1,
    "n_Ar": 0.05,
    "n_CH4": 0.05,
}
LINK_TOY_PRESSURE: Final = 1.5e7
LINK_TOY_INLET: Final = (*LINK_TOY_FLOWS, "T_in", "P")


class LinkToyTruth:
    """A smooth (X, ΔT) of the inlet temperature, for the link toy; the projection reads only its
    identity."""

    def describe(self) -> Mapping[str, Any]:
        return {"kind": "test", "id": "link-toy", "sha256": None, "gradient": "analytic"}

    def evaluate(self, inlet: Sequence[float]) -> tuple[float, float, Mapping[str, Any]]:
        from openflowsheet.studies.trust_region.truths import in_process_meta

        conversion = 0.2 + 1e-4 * (inlet[5] - 680.0)
        return conversion, 350.0 * conversion, in_process_meta()

    def gradient(self, inlet: Sequence[float]) -> Sequence[Sequence[float]]:
        row = [0.0, 0.0, 0.0, 0.0, 0.0, 1e-4, 0.0]
        return [row, [350.0 * value for value in row]]


def _feed_row(name: str) -> EquationSpec:
    def build(v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], a: Any) -> Expr:
        return v[name] - LINK_TOY_FEED[name]

    return EquationSpec(f"feed.{name}", build, "algebraic", f"link toy feed {name}")


def _link_toy_pressure(
    v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], a: Any
) -> Expr:
    return v["P"] - LINK_TOY_PRESSURE


def _link_toy_heater(
    v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], a: Any
) -> Expr:
    return v["T_in"] - 680.0 * p["z"]


def _link_toy_pinned_output(
    v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], a: Any
) -> Expr:
    return p["R.dT"] - 90.0 * p["z"]


def _link_toy_energy(
    v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], a: Any
) -> Expr:
    return v["T_out"] - v["T_in"] - p["R.dT"]


def _link_toy_objective(
    v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], a: Any
) -> Expr:
    return (v["T_out"] - 760.0) ** 2 / 100.0


def link_toy_projection(shape: str, **options: Any) -> Any:
    """The link toy in its `forward` or `implicit` shape, projected with the decision `z`."""
    from openflowsheet.studies.trust_region.projection import (
        DecisionSpec,
        ExternalLinkSpec,
        ObjectiveSpec,
        project,
    )

    rise = 70.0 if shape == "forward" else 90.0
    fix = (
        EquationSpec("heater", _link_toy_heater, "algebraic", "link toy heater")
        if shape == "forward"
        else EquationSpec("pinned", _link_toy_pinned_output, "algebraic", "link toy y - 90 z")
    )
    spec = ProblemSpec(
        label=f"M05-link-shape-toy-{shape}",
        variable_ids=(*LINK_TOY_INLET, "T_out"),
        equations=(
            *(_feed_row(name) for name in LINK_TOY_FLOWS),
            EquationSpec("pressure", _link_toy_pressure, "algebraic", "link toy pressure"),
            fix,
            EquationSpec("energy", _link_toy_energy, "algebraic", "link toy energy balance"),
        ),
        parameter_ids=("z", "R.X", "R.dT"),
        parameters={"z": 1.0, "R.X": 0.2, "R.dT": rise},
    )
    start = {**LINK_TOY_FEED, "P": LINK_TOY_PRESSURE, "T_in": 680.0, "T_out": 680.0 + rise}
    return project(
        spec,
        start,
        decisions=[DecisionSpec("z", 0.9, 1.1)],
        objective=ObjectiveSpec("link-toy-objective", "minimize", _link_toy_objective, 1.0),
        domain={},
        external_links=[ExternalLinkSpec("R", "R.X", "R.dT", LINK_TOY_INLET, LinkToyTruth())],
        **options,
    )


# -- probe P14's toy A: a property-block output pinned by the decision ---------------------------

#: `y = T²/1000` through the block `sq` (the AT toy's), and the row `y − 90 z = 0`: the block's
#: input T enters no other row. With a property block this passes the shape check (R-278: property
#: relations stay functions); the objective is P14's `(y − 96.1)²/100`.
TOY_A_LABEL: Final = "M05-P14-toy-A"


def _toy_a_row(v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], a: Any) -> Expr:
    block_output = next(iter(b.values()))
    return block_output - 90.0 * p["z"]


def _toy_a_objective(
    v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], a: Any
) -> Expr:
    block_output = next(iter(b.values()))
    return (block_output - 96.1) ** 2 / 100.0


class ParabolaBlock:
    """Probe P14 (c)'s block, `y = 90 + (T − 300)²/100`: nearly stationary in its input near the
    start, so the affine basis's subproblems move T far for a small change in y."""

    block_id = "pb"
    input_ids = ("T",)
    output_ids = ("y",)

    def jacobian_pattern(self) -> tuple[tuple[int, int], ...]:
        return ((0, 0),)

    def values(self, inputs: Sequence[float]) -> Sequence[float]:
        (t,) = inputs
        return [90.0 + (t - 300.0) ** 2 / 100.0]

    def jacobian(self, inputs: Sequence[float]) -> Sequence[tuple[int, int, float]]:
        (t,) = inputs
        return [(0, 0, 2.0 * (t - 300.0) / 100.0)]


def implicit_block_projection(block: Any, start_t: float, **options: Any) -> Any:
    """P14's implicit shape on a one-input, one-output property `block`, started at T = `start_t`
    with z = y(T)/90, the decision z in [0.5, 1.5] (the probe's d = 2(z − 1) ∈ [−1, 1])."""
    from openflowsheet.studies.trust_region.projection import DecisionSpec, ObjectiveSpec, project

    (y0,) = block.values([start_t])
    spec = ProblemSpec(
        label=TOY_A_LABEL,
        variable_ids=("T",),
        equations=(EquationSpec("r", _toy_a_row, "algebraic", "P14 y - 90 z"),),
        parameter_ids=("z",),
        parameters={"z": y0 / 90.0},
        blocks=(block,),
        block_inputs={block.block_id: ("T",)},
    )
    return project(
        spec,
        {"T": start_t},
        decisions=[DecisionSpec("z", 0.5, 1.5)],
        objective=ObjectiveSpec("p14-objective", "minimize", _toy_a_objective, 1.0),
        domain={},
        **options,
    )


# -- bases for the tests (R-277) ------------------------------------------------------------------


def affine_block_basis(projection: Any) -> dict[str, Any]:
    """An affine Taylor basis at the projection's start for every property-block EF:
    b(w) = (y_k(w₀) + ∇y_k(w₀)ᵀ(w − w₀)) / s_k, from each block's own values and Jacobian at x₀,
    in the EF's scaled units. A test's basis, not M05-basis-v1's (WO-4 builds that)."""
    import pyomo.environ as pyo

    from openflowsheet.studies.trust_region.trf_state import EFBasis

    spec = projection.spec
    start = {
        name: float(pyo.value(projection.model.x[i])) for i, name in enumerate(spec.variable_ids)
    }
    blocks = {block.block_id: block for block in spec.blocks}
    basis = {}
    for entry in projection.source_map["block_outputs"]:
        block = blocks[entry["block_id"]]
        k = list(block.output_ids).index(entry["output_id"])
        w0 = [start[name] for name in entry["input_variable_ids"]]
        value = float(block.values(w0)[k])
        gradient = [0.0] * len(w0)
        for row, column, entry_value in block.jacobian(w0):
            if row == k:
                gradient[column] += float(entry_value)
        scale = float(entry["output_scale"])

        def build(
            args: Sequence[Any],
            value: float = value,
            gradient: Sequence[float] = tuple(gradient),
            w0: Sequence[float] = tuple(w0),
            scale: float = scale,
        ) -> Any:
            terms = zip(gradient, args, w0, strict=True)
            return (value + sum(g * (a - w) for g, a, w in terms)) / scale

        basis[entry["ef"]] = EFBasis("affine_taylor", build)
    return basis
