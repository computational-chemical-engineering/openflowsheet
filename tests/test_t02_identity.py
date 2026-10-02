"""T02 A02 and A34: what the CI pair compares, and under which rule.

The comparison itself needs two machines and runs in CI (`.github/workflows/ci.yml`, job
`identity`). What is checked here is everything one machine can check: the floors are registered
where ADR 0007 D2.6 says the policy lives, the ADR's table carries both rows, the R0 document holds
no float the comparison would have to compare for equality — except `beta_substitution`, one of two
registered constants and an exact field — and the document is the same twice on one machine.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def document() -> dict[str, Any]:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from t02_identity import identity

    result: dict[str, Any] = identity()
    return result


def floats_in(value: Any, path: str = "") -> list[str]:
    if isinstance(value, dict):
        return [found for key, item in value.items() for found in floats_in(item, f"{path}.{key}")]
    if isinstance(value, list):
        return [found for index, item in enumerate(value) for found in floats_in(item, path)]
    return [path] if isinstance(value, float) else []


def test_a34_the_window_is_registered_where_the_policy_lives() -> None:
    """ADR 0009 D3 as amended (T02 review M4): no absolute floor on either quantity; both
    compared only inside the comparability window `‖f̂_k‖∞ ≥ 1e-4`."""
    from openflowsheet.run.compare import COMPARABILITY_WINDOW, REGISTERED_FLOOR

    assert REGISTERED_FLOOR["kappa_2"] == 0.0 and REGISTERED_FLOOR["gamma_inf"] == 0.0
    assert COMPARABILITY_WINDOW == {
        "kappa_2": ("residual_inf_scaled", 1e-4),
        "gamma_inf": ("residual_inf_scaled", 1e-4),
    }


def test_a34_adr_0007_d2_2_carries_both_rows_with_the_window() -> None:
    (adr,) = (REPO_ROOT / "docs" / "adr").glob("0007-*.md")
    table = adr.read_text().split("**D2.2", 1)[1].split("**D2.3", 1)[0]
    for name in ("kappa_2", "gamma_inf"):
        (row,) = [line for line in table.splitlines() if line.startswith(f"| `{name}`")]
        assert "0 (relative only)" in row or "comparability window" in row, row
    assert "1e-4" in table


def test_a34_the_window_is_decided_on_the_committed_side() -> None:
    """Inside: a 1e-6 relative difference is reported. Outside (the committed residual below
    1e-4): the same difference is not a value comparison — but a number against null still is a
    shape difference. The selector itself is never value-compared."""
    from openflowsheet.run.compare import differences

    committed = {"kappa_2": 12.0, "gamma_inf": 0.3, "residual_inf_scaled": 2e-4}
    moved = {"kappa_2": 12.0 * (1 + 1e-6), "gamma_inf": 0.3, "residual_inf_scaled": 5e-5}
    assert [
        line
        for line in differences(moved, committed, policy_id="K04-numerical-policy-v1")
        if "kappa_2" in line
    ]
    assert not [
        line
        for line in differences(moved, committed, policy_id="K04-numerical-policy-v1")
        if "residual_inf_scaled" in line
    ]

    below = {**committed, "residual_inf_scaled": 5e-5}
    assert not differences(
        {**moved, "residual_inf_scaled": 5e-5}, below, policy_id="K04-numerical-policy-v1"
    )
    assert differences(
        {**moved, "kappa_2": None, "residual_inf_scaled": 5e-5},
        below,
        policy_id="K04-numerical-policy-v1",
    )


def test_a34_every_accelerated_event_keeps_the_decision_margin(document: dict[str, Any]) -> None:
    """D2.4 applied to the drop decisions (review M4): the R0 decisions are promised only while
    no accelerated event sits within a decade of a threshold — `κ₂ ∉ [1e7, 1e9]` against
    `condition_max = 1e8`, `‖γ‖∞ ∉ [1e3, 1e5]` against `coefficient_max = 1e4`."""
    events = [
        event
        for group in document["floats"].values()
        for runs in group.values()
        for event in runs
        if event["kappa_2"] is not None
    ]
    assert events
    near = [
        event
        for event in events
        if 1e7 <= event["kappa_2"] <= 1e9 or 1e3 <= event["gamma_inf"] <= 1e5
    ]
    assert not near, near[:3]
    inside = [event for event in events if event["residual_inf_scaled"] >= 1e-4]
    assert inside, "the window is not empty on the registered cases"


def test_a34_the_r0_document_compares_no_measured_float(document: dict[str, Any]) -> None:
    """R0 is compared for equality and holds no float at all (K05's rule for the identity
    document). The plans go through `execution_plan_r0`; `beta_substitution`, one of two
    registered constants, is its exact decimal string."""
    leaked = floats_in(document["r0"])
    assert not leaked, sorted(set(leaked))[:10]
    betas = {
        event["beta_substitution"]
        for runs in document["r0"]["recycle"].values()
        for event in runs
        if "beta_substitution" in event
    }
    assert betas <= {"1.0", "0.5"} and betas


def test_a34_the_float_document_holds_only_the_two_r1_r2_floats(document: dict[str, Any]) -> None:
    names = {path.rsplit(".", 1)[-1] for path in floats_in(document["floats"])}
    assert names <= {"kappa_2", "gamma_inf", "residual_inf_scaled"}
    assert names, "the registered cases do take Anderson steps"


def test_a02_every_registered_plan_is_in_the_comparison(document: dict[str, Any]) -> None:
    plans = document["r0"]["plans"]
    assert set(plans) == {
        "SYN-001-nominal auto",
        "SYN-001-nominal eo",
        "SYN-001-nominal anderson",
        "SYN-001-A02-360",
        "SYN-001-A02-355-liquid-guess",
    }
    kinds = [step["kind"] for step in plans["SYN-001-A02-360"]["steps"]]
    assert kinds == ["evaluate", "solve_eo"]


def test_a34_the_document_is_the_same_twice_on_one_machine(document: dict[str, Any]) -> None:
    from t02_identity import identity

    assert identity() == document


def test_s3_the_plan_projection_keeps_its_declared_scales() -> None:
    """Review S3: a changed declared scale is a changed plan in R0."""
    import copy

    from openflowsheet.run.identity import execution_plan_r0

    sys.path.insert(0, str(REPO_ROOT / "tests"))
    from test_t02_plan import plan_for

    document = plan_for("SYN-001-nominal").as_document()
    moved = copy.deepcopy(document)
    step = next(step for step in moved["steps"] if step.get("solve_plan"))
    scales = step["solve_plan"]["column_scales"]
    name = next(iter(scales))
    scales[name] = scales[name] * 1.1
    assert execution_plan_r0(moved) != execution_plan_r0(document)
    assert not floats_in(execution_plan_r0(document))
