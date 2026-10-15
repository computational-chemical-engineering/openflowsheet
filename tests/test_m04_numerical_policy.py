"""M04.A37 (WO-14): `M04-numerical-policy-surrogate-v1` classifies every float of M04's records.

ADR 0036 Amendment 1 D8 and spec §18 A1.3 (R-291): no new class. A float of a SurrogateManifest or
a ModelEvidence is `exact` (a registered constant or a verbatim copy) or `r1_r2` (computed from the
experiment records, with the floor of the §11 tolerance that checks it); the one ratio of counts is
`r0_conditional`. Every integer, status and the verdict are R0 only when no decision they depend on
is near threshold — a gap below 10⁻⁸ in the decision's own units — and every gap is computable from
stored members of the manifest (`domain.admissibility_margin` included).

- Every float of every emitted fixture (`tests/fixtures/schemas/<def>/valid/`) matches a rule of
  the addendum (M02's `test_m02_schemas` pattern: dotted paths, full-match regular expressions).
- The decision gaps of A19's manifest, from its stored members, are all ≥ 10⁻⁸ and equal the
  generator's 50-digit margins (`pipeline.smooth_prefix.margins`, six significant digits) — the
  fixture's R0 promise holds; a constructed near case is flagged.
- `scripts/t08_numerical_policy.py --check` passes: the `sha256` partition follows the schemas.
"""

from __future__ import annotations

import copy
import re
import sys
from collections.abc import Iterator, Mapping
from typing import Any

import pytest
from conftest import REPO_ROOT, load_json, load_yaml

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import m04_schema_fixtures  # noqa: E402
import t08_numerical_policy  # noqa: E402

POLICY: dict[str, Any] = load_yaml(
    REPO_ROOT / "benchmarks" / "m04" / "numerical_policy_surrogate.yaml"
)["numerical_policy_surrogate"]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "schemas"
REFERENCE = load_json(REPO_ROOT / "benchmarks" / "m04" / "reference_values.json")
CLASSES = {"exact", "r1_r2", "r0_conditional"}
A19 = FIXTURES / "surrogate_manifest" / "valid" / "a19_smooth_prefix.json"


def test_the_policy_keeps_its_id_and_declares_its_three_classes() -> None:
    assert POLICY["id"] == "M04-numerical-policy-surrogate-v1"
    assert set(POLICY["classes"]) == CLASSES
    assert set(POLICY["rules"]) == set(m04_schema_fixtures.REFERENCES)
    for rules in POLICY["rules"].values():
        for rule in rules:
            assert rule["class"] in CLASSES, rule
            re.compile(rule["path"])
            # An r1_r2 float has a floor with its unit and provenance (ADR 0007 D2.2); no other
            # class has one.
            floored = {"floor", "floor_unit", "source"} & set(rule)
            if rule["class"] == "r1_r2":
                assert floored == {"floor", "floor_unit", "source"}, rule
                assert isinstance(rule["floor"], float) and rule["floor"] > 0.0, rule
            else:
                assert not floored, rule
    assert POLICY["conditional_r0"]["gap"] == 1.0e-8


def _floats(node: Any, path: str = "") -> Iterator[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _floats(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _floats(value, f"{path}[{index}]")
    elif isinstance(node, float):
        yield path


@pytest.mark.parametrize("directory", sorted(m04_schema_fixtures.REFERENCES))
def test_a37_every_float_of_every_m04_fixture_is_classified(directory: str) -> None:
    """ADR 0007 D2.3 for M04's floats: each one matches a rule of the addendum."""
    rules = [(re.compile(rule["path"]), rule["class"]) for rule in POLICY["rules"][directory]]
    found: dict[str, int] = {}
    for path in sorted((FIXTURES / directory / "valid").glob("*.json")):
        for where in _floats(load_json(path)):
            classes = [cls for pattern, cls in rules if pattern.fullmatch(where)]
            assert classes, f"{path.name}: {where} is unclassified"
            found[classes[0]] = found.get(classes[0], 0) + 1
    if directory in ("surrogate_manifest", "model_evidence"):
        assert {"exact", "r1_r2"} <= set(found), (directory, found)
    else:  # the job's body and answer carry no float
        assert found == {}, (directory, found)
    if directory == "surrogate_manifest":
        assert found.get("r0_conditional") == 1, found  # fraction_within_width


def test_a37_every_rule_of_the_manifest_matches_a_float_of_a19s_manifest() -> None:
    """No dead rule: the table is the fixture's, not a list of hopes."""
    floats = list(_floats(load_json(A19)))
    for rule in POLICY["rules"]["surrogate_manifest"]:
        pattern = re.compile(rule["path"])
        assert any(pattern.fullmatch(where) for where in floats), rule["path"]


# -- the conditional R0 promise ------------------------------------------------------------------


def decision_gaps(manifest: Mapping[str, Any]) -> dict[str, float | None]:
    """The smallest gap of each decision of `conditional_r0` from the manifest's stored members
    (`None` where the decision is not taken: no finite q̂, no gradient error, no predictor)."""
    calibration = manifest["calibration"]
    evaluation = manifest["evaluation"]
    q_hat = calibration["q_hat"]
    k = calibration["k"]
    finite = sorted(float(s) for s in calibration["scores"] if s is not None)
    test = [float(s) for s in evaluation["scores"] if s is not None]
    order = [abs(finite[k - 1] - finite[i]) for i in (k - 2, k) if 0 <= i < len(finite)]
    rho_g = manifest["gradient"]["rho_g"]
    errors = [
        float(centre["errors"][o])
        for centre in manifest["gradient"]["centres"]
        if centre["errors"] is not None
        for o in ("X", "dT_K")
    ]
    return {
        "test_score_vs_q_hat": None
        if q_hat is None or not test
        else min(abs(s - q_hat) for s in test),
        "calibration_order_at_k": min(order) if q_hat is not None and order else None,
        "q_hat_vs_width": None if q_hat is None else abs(q_hat - 1.0),
        "test_score_vs_width": min(abs(s - 1.0) for s in test) if test else None,
        "gradient_error_vs_rho_g": min(abs(e - rho_g) for e in errors) if errors else None,
        "admissibility": manifest["domain"]["admissibility_margin"],
    }


def near_threshold(manifest: Mapping[str, Any]) -> list[str]:
    """The decisions of `manifest` that are near threshold (the R0 promise does not hold)."""
    rule = POLICY["conditional_r0"]
    near = [
        name
        for name, gap in decision_gaps(manifest).items()
        if gap is not None and gap < rule["gap"]
    ]
    (identifiability,) = rule["registered_thresholds"]
    ratio = manifest["predictor"]["fit"]["singular_value_ratio"]
    if ratio is not None and 0.1 <= ratio / identifiability["threshold"] <= 10.0:
        near.append(identifiability["id"])
    return near


def test_the_decisions_are_the_policys() -> None:
    declared = [d["id"] for d in POLICY["conditional_r0"]["decisions"]]
    assert declared == list(decision_gaps(load_json(A19)))


def test_a37_a19s_manifest_is_r0_no_decision_is_near_threshold() -> None:
    manifest = load_json(A19)
    gaps = decision_gaps(manifest)
    assert all(gap is not None for gap in gaps.values()), gaps
    assert near_threshold(manifest) == []
    assert min(g for g in gaps.values() if g is not None) >= 1e-3  # 1.4 × 10⁻³ measured
    # The gaps from stored members are the generator's 50-digit margins (six digits registered).
    margins = REFERENCE["pipeline"]["smooth_prefix"]["margins"]
    for name, registered in (
        ("calibration_order_at_k", "order_statistic_gap"),
        ("test_score_vs_q_hat", "test_to_q_hat"),
        ("q_hat_vs_width", "q_hat_to_width_limit"),
    ):
        assert gaps[name] == pytest.approx(float(margins[registered]), rel=1e-5), name


def test_a37_a_constructed_near_case_is_flagged() -> None:
    manifest = copy.deepcopy(load_json(A19))
    q_hat = manifest["calibration"]["q_hat"]
    first = next(i for i, s in enumerate(manifest["evaluation"]["scores"]) if s is not None)
    manifest["evaluation"]["scores"][first] = q_hat + 5e-9
    manifest["domain"]["admissibility_margin"] = 3e-9
    manifest["predictor"]["fit"]["singular_value_ratio"] = 5e-8
    assert near_threshold(manifest) == ["test_score_vs_q_hat", "admissibility", "identifiability"]


def test_a37_the_sha256_partition_follows_the_schemas() -> None:
    assert t08_numerical_policy.main(["--check"]) == 0
