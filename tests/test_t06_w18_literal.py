"""T06 W18 (a): ADR 0018's one additive enum widening, approved by Frank on 2026-09-26
(`docs/T06_DECISIONS.md`).

`solve-policy`'s `globalization.eo_core` gains `newton_refined` (D1), and the Python `Literal`
(`GlobalizationPolicy.eo_core`) widens with it. The default stays `newton`, and no committed
fixture spells the new value, so no registered policy document moves (C2). The fixtures'
byte-for-byte regeneration is `test_k03_schemas.py`'s, `test_t04_schemas.py`'s and
`test_t05b_literal.py`'s, whose generators run unchanged.
"""

from __future__ import annotations

import typing
from pathlib import Path

import pytest
from conftest import load_json
from test_k03_schemas import SCHEMA_DIR, errors_for

from openflowsheet.orchestrator.trace import GlobalizationPolicy, SolvePolicy

REPO_ROOT = Path(__file__).resolve().parents[1]
REFINED = "newton_refined"


def _policy(eo_core: str) -> SolvePolicy:
    return SolvePolicy(
        policy_id="T06-W18",
        residual_tolerances={},
        scales={},
        globalization=GlobalizationPolicy(eo_core=eo_core),  # type: ignore[arg-type]
    )


def test_w18_the_literal_is_the_schema_enum() -> None:
    schema = load_json(SCHEMA_DIR / "solve-policy.schema.json")
    enum = schema["properties"]["globalization"]["properties"]["eo_core"]["enum"]
    hints = typing.get_type_hints(GlobalizationPolicy)
    assert typing.get_args(hints["eo_core"]) == tuple(enum) == ("newton", "ptc", REFINED)


def test_w18_the_default_is_unchanged() -> None:
    assert GlobalizationPolicy().eo_core == "newton"
    assert GlobalizationPolicy().as_document()["eo_core"] == "newton"


@pytest.mark.parametrize("value", ["newton", "ptc", REFINED])
def test_w18_the_policy_schema_accepts_each_value(value: str) -> None:
    document = _policy(value).as_document()
    assert document["globalization"]["eo_core"] == value
    assert errors_for("solve_policy", document) == []


@pytest.mark.parametrize("value", ["refined", "newton-refined", "anderson", "", None])
def test_w18_the_policy_schema_refuses_every_other_value(value: object) -> None:
    document = _policy("newton").as_document()
    document["globalization"] = {**document["globalization"], "eo_core": value}
    assert errors_for("solve_policy", document) != [], value


def test_w18_no_committed_fixture_names_the_new_value() -> None:
    """C2: no registered fixture or case document carries the value; the policies that select it
    are built in code (`openflowsheet.application.policies`) and named by id and hash."""
    documents = [
        path.relative_to(REPO_ROOT)
        for root in ("tests/fixtures", "benchmarks")
        for pattern in ("*.json", "*.yaml")
        for path in (REPO_ROOT / root).rglob(pattern)
        if REFINED in path.read_text(encoding="utf-8")
    ]
    assert documents == []
