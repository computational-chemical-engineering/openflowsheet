"""T05b W5, B06: the phase-contract literal widens to two values (spec §6.6; ADR 0012 D4 (d), C1).

The frozen-schema change Frank approved on 2026-09-25 (`docs/T05_DECISIONS.md`):
`solve-policy.phase_contract` from `const "T03-phase-contract-v1"` to `enum` of it and
`"T05b-phase-contract-v2"`; `SolvePolicy.phase_contract` a two-value `Literal`, default v1.
B06: the schema accepts the two and refuses T03 A01's list (`T02-interim`,
`T03-phase-contract-v2`) and absence; `_policy()` defaults to v1; every committed policy
fixture and every registered policy in the code is v1; the round-trip fixtures regenerate
identically (R-015) — the policy fixtures byte for byte here, the rest by
`test_k03_schemas.py` and `test_t04_schemas.py`, whose generators run unchanged.

v2's rules are W6's (§6.2–§6.5) and W7's (§7); the T05b cases run them under the policy
`T05b-v2` (`t05b_support.POLICY_V2`, spec §6.6), the one registered construction of v2 outside
this file — in `openflowsheet.application.policies.T05B_V2` since T07 W3a moved it into `src`
(W0 flag E6).
"""

from __future__ import annotations

import ast
import sys
import typing
from pathlib import Path

import pytest
from conftest import load_json
from test_k03_schemas import FIXTURE_DIR, errors_for

from openflowsheet.orchestrator.trace import PhaseContract, SolvePolicy

REPO_ROOT = Path(__file__).resolve().parents[1]
V1, V2 = "T03-phase-contract-v1", "T05b-phase-contract-v2"
POLICY_FIXTURES = sorted((FIXTURE_DIR / "solve_policy" / "valid").glob("*.json"))


def _policy(**overrides: object) -> SolvePolicy:
    """A policy with every field at its default but the three a policy must name."""
    return SolvePolicy(policy_id="T05b-B06", residual_tolerances={}, scales={}, **overrides)  # type: ignore[arg-type]


def test_b06_the_type_has_exactly_the_two_literals_and_defaults_to_v1() -> None:
    assert typing.get_args(PhaseContract) == (V1, V2)
    assert _policy().phase_contract == V1
    assert _policy().as_document()["phase_contract"] == V1


@pytest.mark.parametrize("value", [V1, V2])
def test_b06_the_schema_accepts_both_literals(value: str) -> None:
    document = _policy(phase_contract=value).as_document()  # type: ignore[arg-type]
    assert document["phase_contract"] == value
    assert errors_for("solve_policy", document) == []


@pytest.mark.parametrize("value", ["T03-phase-contract-v2", "T02-interim", "", None, 1])
def test_b06_the_schema_refuses_every_other_value(value: object) -> None:
    document = {**_policy().as_document(), "phase_contract": value}
    assert errors_for("solve_policy", document) != [], value


def test_b06_the_schema_refuses_a_policy_without_the_literal() -> None:
    document = _policy().as_document()
    del document["phase_contract"]
    assert errors_for("solve_policy", document) != []


def test_b06_every_committed_policy_fixture_is_v1() -> None:
    assert [path.name for path in POLICY_FIXTURES] == ["syn001_k03.json", "t04_ptc.json"]
    for path in POLICY_FIXTURES:
        assert load_json(path)["phase_contract"] == V1, path.name


def test_b06_the_policy_fixtures_regenerate_byte_for_byte() -> None:
    """R-015: the committed generators' policies, serialized as they write them, are the files."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import k03_schema_fixtures as k03
    import t04_schema_fixtures as t04

    from openflowsheet.orchestrator.trace import GlobalizationPolicy, RecyclePolicy

    ptc = t04.policy(
        "ptc",
        recycle=RecyclePolicy(method="eo"),
        globalization=GlobalizationPolicy(eo_core="ptc", eo_recovery="none"),
    )
    for name, policy, serialize in (
        ("syn001_k03.json", k03.POLICY, k03.serialize),
        ("t04_ptc.json", ptc, t04.serialize),
    ):
        path = FIXTURE_DIR / "solve_policy" / "valid" / name
        assert serialize(policy.as_document()) == path.read_text(encoding="utf-8"), name


def _sources() -> list[Path]:
    roots = ("src", "scripts", "benchmarks", "tests")
    return sorted(path for root in roots for path in (REPO_ROOT / root).rglob("*.py"))


#: Spec §6.6: the T05b cases' policy `T05b-v2` is constructed in exactly one place — the
#: application's policy registry since T07 W3a (design note §12.2, W0 flag E6).
T05B_V2_SOURCE = REPO_ROOT / "src" / "openflowsheet" / "application" / "policies.py"


def test_b06_no_registered_policy_names_v2() -> None:
    """No code constructs or replaces a policy with a `phase_contract` other than the default,
    and no committed document outside this package's evidence spells v2: every registered
    policy — SYN-001's, T02–T04's fixtures and tests, T05's `T05-W13` — stays v1 (spec §6.6).
    Two exemptions: this file, which constructs v2 to show the schema accepts it, and the T05b
    cases' own policy `T05b-v2` (`t05b_support.POLICY_V2`), constructed once in
    `T05B_V2_SOURCE`."""
    offenders: list[str] = []
    for path in _sources():
        if path.name == Path(__file__).name or path == T05B_V2_SOURCE:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == "phase_contract":
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.value.lineno}")
    assert offenders == []
    constructed = [
        node
        for node in ast.walk(ast.parse(T05B_V2_SOURCE.read_text(encoding="utf-8")))
        if isinstance(node, ast.keyword) and node.arg == "phase_contract"
    ]
    assert len(constructed) == 1
    from t05b_support import POLICY_V2

    assert (POLICY_V2.policy_id, POLICY_V2.phase_contract) == ("T05b-v2", V2)
    documents = [
        path
        for root in ("tests/fixtures", "benchmarks")
        for pattern in ("*.json", "*.yaml")
        for path in (REPO_ROOT / root).rglob(pattern)
        if V2 in path.read_text(encoding="utf-8")
    ]
    assert documents == []
