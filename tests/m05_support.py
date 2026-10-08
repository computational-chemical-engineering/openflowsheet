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
