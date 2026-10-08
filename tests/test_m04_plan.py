"""M04.A01–A03: the registered sampler, plan and plan guard (M04 spec §5, ADR 0036 D2).

The expectations are the design lane's generator output (`benchmarks/m04/reference_values.json`,
`benchmarks/m04/plan-it1.json`), which imports nothing from `openflowsheet`. Identity is exact
(ADR 0033), so every float is compared bit for bit (`float.hex`), never within a tolerance.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from typing import Any

import pytest
from conftest import REPO_ROOT, load_json

from openflowsheet.models.c1.boundary import data_domain_violations, hard_domain_violations
from openflowsheet.studies.surrogate import plan as sp
from openflowsheet.thermo import StreamState

REFERENCE: Mapping[str, Any] = load_json(REPO_ROOT / "benchmarks" / "m04" / "reference_values.json")
PLAN_IT1: Mapping[str, Any] = load_json(REPO_ROOT / "benchmarks" / "m04" / "plan-it1.json")
#: The real variant's per-tube flow bound [0.5, 2] × F₀ (ADR 0034 D10, spec §5.1), which the plan
#: must satisfy although M01's hard domain on `main` has no flow bound.
F0 = float(REFERENCE["constants"]["nominal_tube_flow_mol_s"])


def _hex(values: Sequence[float]) -> list[str]:
    return [float(x).hex() for x in values]


def _request_hex(request: StreamState) -> list[str]:
    return _hex([*request.n, request.temperature, request.pressure])


def _expected_request_hex(document: Mapping[str, Any]) -> list[str]:
    return _hex([*document["n"], document["T"], document["P"]])


def parent_domain(request: StreamState) -> list[str]:
    """The real parent's hard domain with its flow bound, and the kinetics' data domain."""
    found = list(hard_domain_violations(request))
    flow = request.total_flow / sp.PLAN_N_TUBES
    if not 0.5 * F0 <= flow <= 2.0 * F0:
        found.append(f"F_ret_in {flow!r} mol/s outside [0.5, 2] x F0")
    found.extend(f"data domain: {name}" for name in data_domain_violations(request))
    return found


# -- constants ------------------------------------------------------------------------------------


def test_the_box_and_the_counts_are_the_registered_ones() -> None:
    box = REFERENCE["constants"]["box"]
    assert [b.name for b in sp.BOX] == [row["coordinate"] for row in box]
    for coordinate, row in zip(sp.BOX, box, strict=True):
        assert coordinate.unit == row["unit"]
        for attribute in ("lo", "hi", "centre", "half_width"):
            assert getattr(coordinate, attribute).hex() == float(row[attribute]).hex(), attribute
    assert sp.BOX[4].half_width == 0.009999999999999998  # the binary64 half-width of spec §3.1
    constants = REFERENCE["constants"]
    assert dict(sp.COUNTS) == constants["counts"] == PLAN_IT1["counts"]
    assert dict(sp.PREFIX_COUNTS) == constants["prefix_counts"]
    assert sp.GRADIENT_INNER == constants["gradient_inner_box"]
    assert sp.GRADIENT_STEP_Z == constants["gradient_step_z"]
    assert {split: sp.seed(1, split) for split in sp.SPLITS} == constants["seeds"]
    assert PLAN_IT1["seeds"] == constants["seeds"] and PLAN_IT1["n_tubes"] == sp.PLAN_N_TUBES


# -- A01 ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("split", sp.SPLITS)
def test_a01_splitmix64_first_words(split: sp.Split) -> None:
    expected = [int(word) for word in REFERENCE["splitmix64_first_words"][split]]
    assert list(sp.splitmix64(sp.seed(1, split), 3)) == expected


def test_a01_the_sampler_is_a_pure_function_of_its_seed() -> None:
    first = sp.splitmix64(20261008011, 10)
    assert sp.splitmix64(20261008011, 10) == first
    assert sp.splitmix64(20261008011, 3) == first[:3]
    assert all(0 <= word < 2**64 for word in first)
    assert sp.unit_uniform(0) == 0.0 and sp.unit_uniform(2**64 - 1) == 1.0 - 2.0**-53


# -- A02 ------------------------------------------------------------------------------------------

FULL = sp.registered_plan("it1", synthetic_parent=False)


@pytest.mark.parametrize("split", ["training", "calibration", "test"])
def test_a02_every_draw_and_request_bitwise(split: str) -> None:
    rows = getattr(FULL, split)
    expected = PLAN_IT1[split]
    assert len(rows) == len(expected) == sp.COUNTS[split]
    for row, document in zip(rows, expected, strict=True):
        assert row.index == document["index"]
        assert _hex(row.u) == _hex(document["u"]), f"{split}[{row.index}].u"
        assert _request_hex(row.request) == _expected_request_hex(document["request"]), (
            f"{split}[{row.index}].request"
        )


def test_a02_every_gradient_centre_and_stencil_bitwise() -> None:
    assert len(FULL.gradient) == len(PLAN_IT1["gradient"]) == 5
    stencils = 0
    for centre, document in zip(FULL.gradient, PLAN_IT1["gradient"], strict=True):
        assert centre.index == document["index"]
        assert _hex(centre.u) == _hex(document["u"])
        assert _request_hex(centre.request) == _expected_request_hex(document["request"])
        assert len(centre.stencil) == len(document["stencil"]) == 14
        for point, expected in zip(centre.stencil, document["stencil"], strict=True):
            assert (point.coordinate, point.sign) == (expected["coordinate"], expected["sign"])
            assert _hex(point.u) == _hex(expected["u"])
            assert _request_hex(point.request) == _expected_request_hex(expected["request"])
            stencils += 1
    assert stencils == 70


def test_a02_the_632_experiments_are_distinct_and_in_plan_order() -> None:
    requests = FULL.requests()
    assert len(requests) == 632 == REFERENCE["plan_summary"]["experiments"]
    assert len({label for label, _ in requests}) == 632
    assert len({tuple(_request_hex(request)) for _, request in requests}) == 632
    assert requests[0][0] == "training[0]" and requests[144][0] == "calibration[0]"
    assert requests[262][0] == "test[0]" and requests[562][0] == "gradient[0].T+"
    assert requests[-1][0] == "gradient[4].F_tube-"


def test_a02_the_prefix_plan_is_the_prefix_of_iteration_1() -> None:
    prefix = sp.registered_plan("it1-prefix", synthetic_parent=True)
    assert prefix.counts == dict(sp.PREFIX_COUNTS)
    assert len(prefix.requests()) == 72 + 39 + 60 + 2 * 14 == 199
    for split in ("training", "calibration", "test", "gradient"):
        rows = getattr(prefix, split)
        assert rows == getattr(FULL, split)[: len(rows)], split
    assert prefix.seeds == FULL.seeds and prefix.iteration == FULL.iteration == 1


def test_a02_the_input_map_inverts_the_request_map_on_the_plan() -> None:
    """u(request(u)) returns T and P exactly and the other five within a few ulps: the box test
    the guard makes on recomputed coordinates is the surrogate's own (spec §3.1)."""
    worst = 0.0
    for _, request in FULL.requests():
        u = sp.coordinates(request, sp.PLAN_N_TUBES)
        assert u is not None
        z = sp.scaled(u)
        worst = max(worst, max(abs(x) for x in z))
    # Every request is inside the box with a registered margin (generator: at least 1.6e-6).
    assert worst <= 1.0 - 1.0e-6


# -- A03 ------------------------------------------------------------------------------------------


def test_a03_the_registered_plan_passes_its_guard() -> None:
    assert sp.plan_violations(FULL, parent_domain) == ()
    sp.check_plan(FULL, parent_domain)


def test_a03_a_request_outside_the_box_refuses_the_plan() -> None:
    row = FULL.test[17]
    moved = dataclasses.replace(row, request=dataclasses.replace(row.request, temperature=700.0))
    test = (*FULL.test[:17], moved, *FULL.test[18:])
    mutated = dataclasses.replace(FULL, test=test)
    assert sp.plan_violations(mutated, parent_domain) == (
        "test[17]: outside the reference box in ['T']",
    )
    with pytest.raises(sp.PlanRefusedError) as refused:
        sp.check_plan(mutated, parent_domain)
    assert refused.value.code == "plan_invalid"


def test_a03_the_domain_check_is_the_parents() -> None:
    """A request inside the box that the parent's domain rejects (here a stand-in domain that
    narrows T) refuses the plan: the guard does not assume box ⊂ domain, it checks it."""

    def narrow(request: StreamState) -> list[str]:
        return ["T_in above 690 K"] if request.temperature > 690.0 else []

    found = sp.plan_violations(FULL, narrow)
    assert found and all(reason.endswith("T_in above 690 K") for reason in found)
    with pytest.raises(sp.PlanRefusedError, match="^plan_invalid: "):
        sp.check_plan(FULL, narrow)


def test_a03_a_repeated_request_refuses_the_plan() -> None:
    calibration = (*FULL.calibration[:-1], FULL.training[3])
    mutated = dataclasses.replace(FULL, calibration=calibration)
    assert sp.plan_violations(mutated, parent_domain) == ("calibration[3]: repeats training[3]",)


def test_a03_an_undefined_input_refuses_the_plan() -> None:
    row = FULL.training[0]
    n = (row.request.n[0], 0.0, *row.request.n[2:])
    broken = dataclasses.replace(row, request=dataclasses.replace(row.request, n=n))
    mutated = dataclasses.replace(FULL, training=(broken, *FULL.training[1:]))
    found = sp.plan_violations(mutated, lambda _: [])
    assert found == ("training[0]: the input map is undefined",)


def test_a03_the_prefix_plan_is_refused_for_a_non_synthetic_parent() -> None:
    with pytest.raises(sp.PlanRefusedError) as refused:
        sp.registered_plan("it1-prefix", synthetic_parent=False)
    assert refused.value.code == "plan_not_registered_for_parent"
    with pytest.raises(sp.PlanRefusedError) as unknown:
        sp.registered_plan("it2", synthetic_parent=True)
    assert unknown.value.code == "plan_not_registered"
