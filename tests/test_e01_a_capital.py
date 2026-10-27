"""E01 WO-A4: the capital chain and annualisation (E01 design §4.7.1, §4.7.3).

A20 (the `ebtf-prisma-v1` ratio) and A21 (the CRF and its domain), on floats and on the CasADi
algebra. Expectations are the note's own numbers, never the program's.
"""

from __future__ import annotations

import math

import casadi
import pytest

from openflowsheet.assessment.cost.capital import (
    ChainError,
    chain_from,
    crf,
    discount_rate_domain,
    load_chain,
)


def _ulps(value: float, expected: float) -> float:
    return abs(value - expected) / math.ulp(expected)


def _run(chain_id: str, bases: dict[str, float]) -> dict[str, float]:
    chain = load_chain(chain_id)
    values: dict[str, float] = dict(bases)
    for step in chain.steps:
        values[step.name] = step.value(values)
    values["total"] = values[chain.capital_total]
    values["fci"] = values[chain.fci]
    return values


def test_a20_ebtf_prisma_ratio() -> None:
    for tdc in (1.0, 1234.5678, 3.7e7):
        values = _run("ebtf-prisma-v1", {"sum_bare_module": tdc, "sum_purchased": 0.5 * tdc})
        assert values["TDC"] == tdc
        assert _ulps(values["total"] / values["TDC"], 1.744314) <= 4.0
        assert values["fci"] == values["total"]
    assert load_chain("ebtf-prisma-v1").bases == frozenset({"sum_bare_module"})


def test_bare_module_total_is_the_sum() -> None:
    values = _run("bare-module-total", {"sum_bare_module": 4.25e6, "sum_purchased": 1.0})
    assert values["total"] == values["fci"] == 4.25e6


def test_a21_crf_and_its_domain() -> None:
    assert _ulps(crf(0.08, 20.0), 0.10185220882315059) <= 2.0
    i, n = casadi.SX.sym("i"), casadi.SX.sym("n")
    symbolic = float(casadi.Function("crf", [i, n], [crf(i, n)])(0.08, 20.0))
    assert _ulps(symbolic, 0.10185220882315059) <= 2.0
    assert discount_rate_domain(0.08, 20) is None
    assert discount_rate_domain(0.001, 1) is None
    assert discount_rate_domain(0.0009, 20) is not None
    assert discount_rate_domain(0.08, 0) is not None


def test_a_document_chain_is_checked() -> None:
    chain = chain_from(
        [
            {"name": "ISBL", "terms": [{"of": "sum_purchased", "factor": 4.0}]},
            {
                "name": "FCI",
                "terms": [{"of": "ISBL"}, {"of": "ISBL", "factor_product": [0.3, 0.5]}],
            },
        ],
        "FCI",
        "ISBL",
    )
    values: dict[str, float] = {"sum_purchased": 10.0}
    for step in chain.steps:
        values[step.name] = step.value(values)
    assert values["FCI"] == 40.0 + (0.3 * 0.5) * 40.0
    for steps, total in (
        ([{"name": "A", "terms": [{"of": "B"}]}], "A"),  # `of` not earlier
        ([{"name": "total", "terms": [{"of": "sum_purchased"}]}], "total"),  # reserved
        ([{"name": "A", "terms": [{"of": "sum_purchased"}]}], "Z"),  # total names no step
        (
            [
                {
                    "name": "A",
                    "terms": [{"of": "sum_purchased", "factor": 1.0, "factor_product": [1.0]}],
                }
            ],
            "A",
        ),
    ):
        with pytest.raises(ChainError):
            chain_from(steps, total, total)
    with pytest.raises(ChainError):
        load_chain("no-such-chain")
