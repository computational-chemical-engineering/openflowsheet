"""E01 WO-A4: the `derived` contributor (design §4.7.5) on S11's TH-C2 loop (water).

Hand values are recomputed from the formula `(Σ α y + α_0) / (Σ β y + β_0)` over the program's
own earlier outputs; derivatives by the quotient rule from the earlier outputs' rows.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pytest
from test_e01_a_contributor import C2_DOC, _c2
from test_s11_thermal_binding import registered  # noqa: F401

from openflowsheet.assessment.cost.contributor import CostContributor
from openflowsheet.assessment.cost.derived import DerivedContributor
from openflowsheet.assessment.program import AssessmentProgram, Linearization
from openflowsheet.assessment.spec import load_assessment
from openflowsheet.assessment.views import view_of


def _program(derived: list[dict[str, Any]]) -> tuple[AssessmentProgram, dict[str, float]]:
    binding, host, state = _c2()
    program = AssessmentProgram.build(
        view_of(binding.flowsheet),
        host,
        load_assessment({**C2_DOC, "derived": derived}),
        state,
        contributors=[CostContributor(), DerivedContributor()],
    )
    assert isinstance(program, AssessmentProgram), program
    return program, state


def _dense(lin: Linearization, row: str) -> np.ndarray:
    m = lin.d_dx
    out = np.zeros(len(m.col_ids))
    i = m.row_ids.index(row)
    for j in range(len(m.col_ids)):
        for k in range(m.indptr[j], m.indptr[j + 1]):
            if m.indices[k] == i:
                out[j] = m.data[k]
    return out


RATIO = {
    "id": "r",
    "unit": "1",
    "numerator": {"terms": {"capex.total": 2.0}, "constant": 5.0},
    "denominator": {"terms": {"opex.total": 1.0}, "constant": -1.0},
}


def test_ratio_value_nesting_and_quotient_rule(registered: None) -> None:  # noqa: F811
    nested = {"id": "s", "unit": "1", "numerator": {"terms": {"derived.r": 3.0, "tac": -1e-9}}}
    program, state = _program([RATIO, nested])
    assert not program.refusals and not program.unavailable
    values = program.evaluate(state)
    assert isinstance(values, Mapping)
    c, o = values["capex.total"], values["opex.total"]
    r = (2.0 * c + 5.0) / (1.0 * o + -1.0)
    assert values["derived.r"] == pytest.approx(r, rel=1e-15)
    assert values["derived.s"] == pytest.approx(3.0 * r - 1e-9 * values["tac"], rel=1e-15)
    lin = program.linearize(state, {}, ["derived.r", "capex.total", "opex.total"])
    assert isinstance(lin, Linearization)
    dc, do, dr = (_dense(lin, k) for k in ("capex.total", "opex.total", "derived.r"))
    expected = (2.0 * dc * (o - 1.0) - (2.0 * c + 5.0) * do) / (o - 1.0) ** 2
    scale = np.max(np.abs(expected))
    assert scale > 0.0
    assert np.max(np.abs(dr - expected)) <= 1e-12 * scale


def test_non_positive_denominator_is_metric_undefined(registered: None) -> None:  # noqa: F811
    program, state = _program([{**RATIO, "denominator": {"terms": {"opex.total": -1.0}}}])
    assert [(r.code, r.target) for r in program.refusals] == [("METRIC_UNDEFINED", "derived.r")]
    assert "derived.r" in program.unavailable and "derived.r" not in program.output_ids


def test_references_go_backwards_only(registered: None) -> None:  # noqa: F811
    forward = {"id": "a", "unit": "1", "numerator": {"terms": {"derived.b": 1.0}}}
    later = {"id": "b", "unit": "1", "numerator": {"terms": {"tac": 1.0}}}
    selfref = {"id": "c", "unit": "1", "numerator": {"terms": {"derived.c": 1.0}}}
    unknown = {"id": "d", "unit": "1", "numerator": {"terms": {"capex.nothing": 1.0}}}
    program, _ = _program([forward, later, selfref, unknown])
    assert [(r.code, r.target) for r in program.refusals] == [
        ("ASSESSMENT_OUTPUT_UNKNOWN", "derived.b"),
        ("ASSESSMENT_OUTPUT_UNKNOWN", "derived.c"),
        ("ASSESSMENT_OUTPUT_UNKNOWN", "capex.nothing"),
    ]
    assert "derived.b" in program.output_ids
    assert {"derived.a", "derived.c", "derived.d"} <= set(program.unavailable)


def test_zero_denominator_means_no_ratio_and_unavailable_propagates(registered: None) -> None:  # noqa: F811
    plain = {**RATIO, "denominator": {"terms": {"opex.total": 0.0}, "constant": 0.0}}
    program, state = _program([plain])
    values = program.evaluate(state)
    assert isinstance(values, Mapping)
    assert values["derived.r"] == 2.0 * values["capex.total"] + 5.0
    # A ratio over a withheld total is withheld, not refused (A40).
    document = {**C2_DOC, "operation": {"discount_rate": 0.0009}}
    binding, host, state = _c2()
    withheld = AssessmentProgram.build(
        view_of(binding.flowsheet),
        host,
        load_assessment(
            {**document, "derived": [{"id": "t", "unit": "1", "numerator": {"terms": {"tac": 1}}}]}
        ),
        state,
        contributors=[CostContributor(), DerivedContributor()],
    )
    assert isinstance(withheld, AssessmentProgram)
    assert "derived.t" in withheld.unavailable
    assert "METRIC_UNDEFINED" not in {r.code for r in withheld.refusals}
