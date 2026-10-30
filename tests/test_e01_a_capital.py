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


# -- operating-cost pieces (§4.5.6, §4.6, §4.7.2) and the uncertainty pass (§4.9; A23 part) -----

from openflowsheet.assessment.cost.index import TargetBasis, load_rates, load_series  # noqa: E402
from openflowsheet.assessment.cost.operating import PER_SI, annual, price_on_basis  # noqa: E402
from openflowsheet.assessment.cost.uncertainty import (  # noqa: E402
    AACE_RANGES,
    estimate_class,
    rss,
    worst_case,
)
from openflowsheet.assessment.program import Refusal  # noqa: E402

WPU11 = "bls-ppi-wpu11-annual-v1"
TARGET = TargetBasis("USD", 2024, {"USD": WPU11})


def test_price_on_the_basis_is_divided_by_its_exact_factor() -> None:
    series, rates = {WPU11: load_series(WPU11)}, load_rates()
    for per, factor in (("GJ", 1e9), ("kWh", 3.6e6), ("t", 1e3), ("kmol", 1e3), ("kg", 1.0)):
        assert PER_SI[per] == factor
        found = price_on_basis("p", {"value": 20.0, "per": per}, TARGET, series, rates)
        assert not isinstance(found, Refusal)
        assert found.value == 20.0 / factor and found.escalation == 1.0
    stated = {"value": 20.0, "per": "GJ", "currency": "USD", "year": 2020}
    refused = price_on_basis("U1", stated, TARGET, series, rates)
    assert isinstance(refused, Refusal) and refused.code == "PRICE_BASIS_MISMATCH"
    assert refused.target == "U1"
    escalated = price_on_basis("U1", {**stated, "escalation_series": WPU11}, TARGET, series, rates)
    assert not isinstance(escalated, Refusal)
    ratio = series[WPU11].values[2024] / series[WPU11].values[2020]
    assert escalated.escalation == ratio * 1.0 * 1.0
    assert escalated.value == (20.0 / 1e9) * escalated.escalation
    assert annual(2.0, 8000.0) == 2.0 * 3600.0 * 8000.0


def test_a23_aace_table_and_class() -> None:
    assert AACE_RANGES == {
        5: ((-0.20, -0.50), (0.30, 1.00)),
        4: ((-0.15, -0.30), (0.20, 0.50)),
        3: ((-0.10, -0.20), (0.10, 0.30)),
        2: ((-0.05, -0.15), (0.05, 0.20)),
        1: ((-0.03, -0.10), (0.03, 0.15)),
    }
    assert estimate_class([3, 4, 2], extrapolated=False) == 4
    assert estimate_class([3, 4, 2], extrapolated=True) is None


def test_first_order_propagation_by_hand() -> None:
    g, ranges = [2.0, -3.0], [(-0.3, 0.5), (-0.1, 0.2)]
    low, high = worst_case(10.0, g, ranges)
    assert low == 10.0 + (2.0 * -0.3) + (-3.0 * 0.2)
    assert high == 10.0 + (2.0 * 0.5) + (-3.0 * -0.1)
    expected = math.sqrt(4.0 * 0.8 * 0.8 / 12.0 + 9.0 * 0.3 * 0.3 / 12.0)
    assert rss(g, ranges) == pytest.approx(expected, rel=1e-15)
