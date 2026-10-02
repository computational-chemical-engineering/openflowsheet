"""K04's three schemas (plan §2.2 row K04/K05), their fixtures, and ADR 0007 D2 made executable.

The fixtures are emitted by real verifier runs through `scripts/k04_schema_fixtures.py`, per
register R-015. That rule was written after K03 shipped six fixtures of which four were
hand-assembled, and regenerating them found one internally impossible.

The most valuable document here is the *rejected* one. A certificate that says `VERIFIED` is
easy to produce and proves little; the trivial-root certificate is a `FAILED` with
`false_success_detected` on a state that satisfies all 49 assembled rows, and it is the
document a reader would actually study.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT, load_json
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from openflowsheet.run.compare import differences

SCHEMA_DIR = REPO_ROOT / "schemas"
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "schemas"

K04_SCHEMAS = {
    "solution_certificate": "solution-certificate.schema.json",
    "regularity_evidence": "regularity-evidence.schema.json",
    "failure_bundle": "failure-bundle.schema.json",
}


def _registry() -> Registry:
    resources = []
    for path in sorted(SCHEMA_DIR.glob("*.schema.json")):
        document = load_json(path)
        resources.append((document["$id"], Resource(contents=document, specification=DRAFT202012)))
    return Registry().with_resources(resources)


REGISTRY = _registry()


def errors_for(name: str, document: Any) -> list[str]:
    validator = Draft202012Validator(load_json(SCHEMA_DIR / K04_SCHEMAS[name]), registry=REGISTRY)
    return [
        f"{list(error.absolute_path)}: {error.message}"
        for error in sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))
    ]


def fixtures(name: str) -> list[Path]:
    return sorted((FIXTURE_DIR / name / "valid").glob("*.json"))


@pytest.mark.parametrize("name", sorted(K04_SCHEMAS))
def test_the_schema_is_itself_valid(name: str) -> None:
    Draft202012Validator.check_schema(load_json(SCHEMA_DIR / K04_SCHEMAS[name]))


@pytest.mark.parametrize(
    ("name", "path"),
    [(name, path) for name in sorted(K04_SCHEMAS) for path in fixtures(name)],
    ids=lambda value: value.stem if isinstance(value, Path) else str(value),
)
def test_a31_the_fixtures_validate_and_round_trip(name: str, path: Path) -> None:
    document = load_json(path)
    assert errors_for(name, document) == [], f"{path.name}: {errors_for(name, document)}"
    reloaded = json.loads(json.dumps(document))
    assert reloaded == document
    assert errors_for(name, reloaded) == []


def test_a31_the_fixtures_are_what_the_verifier_emits_today() -> None:
    """Generated, not written (R-015), and compared under ADR 0007 D2's rule."""
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from k04_schema_fixtures import documents
    from t04_schema_fixtures import FIXTURE_NAMES as T04_FIXTURES

    emitted = documents()
    # T04's fixtures share these schema directories and are regenerated and compared by T04's
    # own generator and test (`tests/test_t04_schemas.py`); every other file must be this one's.
    assert set(emitted) | {name for name in T04_FIXTURES if name.split("/")[0] in K04_SCHEMAS} == {
        str(path.relative_to(FIXTURE_DIR)) for name in K04_SCHEMAS for path in fixtures(name)
    }, "a fixture exists that nothing regenerates, or vice versa"
    for name, document in emitted.items():
        found = differences(
            document, load_json(FIXTURE_DIR / name), policy_id="K04-numerical-policy-v1"
        )
        assert not found, (
            f"{name} is not what the verifier emits:\n  "
            + "\n  ".join(found)
            + "\nIf intended, regenerate with `python scripts/k04_schema_fixtures.py --write`."
        )


def test_the_rejected_certificate_is_the_document_a_reader_would_study() -> None:
    """The trivial root, serialized. A `VERIFIED` proves little; this is the interesting one."""
    document = load_json(
        FIXTURE_DIR / "solution_certificate" / "valid" / "syn001_trivial_root_failed.json"
    )
    assert document["verification_status"] == "FAILED"
    assert document["false_success_detected"] is True

    failing = {check["id"] for check in document["checks"] if check["result"] == "fail"}
    assert "energy_balance.heater" in failing
    assert "energy_balance.flash" in failing
    assert "phase_admissibility.S3.bubble" in failing
    assert any(check.startswith("independent_split.S3") for check in failing)

    # And the passing half, which is what makes it a false success rather than a bad answer.
    residuals = [check for check in document["checks"] if check["category"] == "residual"]
    assert len(residuals) == 49
    assert all(check["result"] == "pass" for check in residuals)
    assert document["regularity"]["status"] == "NO_RANK_LOSS_DETECTED"
    envelope = next(c for c in document["checks"] if c["id"] == "energy_balance.envelope")
    assert envelope["result"] == "pass", "the registered blind spot, serialized"


def test_a_certificate_carries_its_three_statements() -> None:
    """§8.2: the promise and its two disclaimers travel with the document, as text."""
    document = load_json(
        FIXTURE_DIR / "solution_certificate" / "valid" / "syn001_nominal_verified.json"
    )
    statements = " ".join(document["statements"]).lower()
    assert "certifies the residuals at the registered tolerances" in statements
    assert "not an experimental validation" in statements
    assert "no finite test suite" in statements
    assert document["solution_error_bound_scaled"] is not None, (
        "the bound is recorded on a VERIFIED certificate; that is the disclosure it is for"
    )


#: ADR 0007 D2's four classes, made explicit. Every float in every K04 fixture must fall into
#: one of them, or `test_a32` fails naming it. Floats compared **exactly**, because they are
#: policy constants or structure rather than measurements:
EXACT_FLOATS = frozenset(
    {
        # T03 §8.2 (ADR 0005 D7): the root fingerprint's registered δ_root.
        "delta_scaled_inf",
        "tolerance",
        "reference",
        "tau_ill",
        "svd_dimension_cap",
        "cap",
        "applied",
        "registered",
        "threshold",
        "inverse_one_norm_threshold",
        "diag_pivot_thresh",
        "relax",
        "panel_size",
        "constant_mismatch",
    }
)

#: Subtrees keyed by *variable or row id* rather than by field name, so the leaf key is an id
#: and classifying by name is meaningless. Every float in them is a registered scale or a
#: certificate constant, all exact.
EXACT_SUBTREES = (
    ".transformations.scales",
    ".column_scales",
    ".row_scales",
)

#: Floats that are **measurements**, compared within the declared numerical policy.
MEASURED_FLOATS = frozenset(
    {
        "value",
        "one_norm",
        "rcond_1",
        "u_diagonal_ratio",
        "inverse_one_norm_estimate",
        "solution_error_bound_scaled",
        "witness_max_diff",
        "sigma_min",
        "sigma_max",
        "residual_inf_unscaled",
        "merit",
        "vapor",
        "liquid",
        "vapor_total",
        "liquid_total",
    }
)


@pytest.mark.parametrize("policy_id", ["K04-numerical-policy-v1", "T08-numerical-policy-v2"])
def test_a32_every_float_in_every_schema_is_classified(policy_id: str) -> None:
    """ADR 0007 D2 made executable: a schema float with no classification fails this test.

    The classes are the registered floors, the exact-comparison fields, the measurements, the
    counts that are measurably not reproducible, and the digests. A float outside all of them
    would be compared by a rule nobody chose — which is precisely how the byte-exact fixture
    comparison came to assert machine-specific values in the first place.

    It found three on its first run: `witness_max_diff` and the two `phase_branch` split
    vectors, all measurements, none of which anyone had thought about.

    Parameterized over both policies (ADR 0025 A2): v1 exactly as before; v2 by its own rows,
    extended to `solution-state.json`'s `variables` (`_a32_v2`).
    """
    if policy_id == "T08-numerical-policy-v2":
        _a32_v2()
        return
    from openflowsheet.run.compare import DIGEST_FIELDS, REGISTERED_FLOOR, UNREPRODUCIBLE_COUNTS

    known = (
        EXACT_FLOATS
        | MEASURED_FLOATS
        | frozenset(REGISTERED_FLOOR)
        | UNREPRODUCIBLE_COUNTS
        | DIGEST_FIELDS
    )
    unclassified: list[str] = []
    for name in sorted(K04_SCHEMAS):
        for path in fixtures(name):
            _walk(load_json(path), "", unclassified, known)
    assert not unclassified, (
        "these schema floats have no ADR 0007 D2 classification:\n  "
        + "\n  ".join(sorted(set(unclassified)))
    )
    assert EXACT_FLOATS.isdisjoint(MEASURED_FLOATS), "a float cannot be both exact and measured"

    # And the part that stops this recurring. A *measured* float that lives near zero needs an
    # absolute floor at its registered threshold, or it falls back to 1e-24 and a cross-machine
    # comparison of two roundoff values fails. Three of these reached CI before the rule below
    # existed: `checks[].value`, `witness_max_diff` and `solution_error_bound_scaled`.
    from openflowsheet.run.compare import SELF_FLOORED

    near_zero = {
        "value",
        "witness_max_diff",
        "solution_error_bound_scaled",
        "residual_inf_unscaled",
        "merit",
        "sigma_min",
    }
    assert near_zero <= MEASURED_FLOATS, "a near-zero float must first be a measured one"
    unfloored = sorted(
        name for name in near_zero if name not in REGISTERED_FLOOR and name not in SELF_FLOORED
    )
    assert not unfloored, (
        "these quantities live near zero and have no absolute floor, so comparing two "
        f"roundoff values of them across machines will fail: {unfloored}. Register the "
        "threshold each one already has, or floor it against a tolerance in its own object."
    )


def _a32_v2() -> None:
    """ADR 0025 A2: under `T08-numerical-policy-v2`, every float of the K04 fixtures and of the
    solution-state fixtures is classified by one of §5's rows 2–14.

    The rows that classify by path rather than by name are 9 (a `near_threshold` limitation's
    `value`), 11 (a solution state's `variables.<id>`) and 12 (a phase split's flows); row 3
    takes `u_diagonal_ratio` out of the measurements (D4)."""
    from openflowsheet.run import compare

    by_name = {
        **dict.fromkeys(compare.V2_UNREPRODUCIBLE_COUNTS, 2),
        **dict.fromkeys(compare.V2_COMPARABILITY_WINDOW, 7),
        **dict.fromkeys(compare.V2_WINDOW_SELECTORS, 6),
        **dict.fromkeys(compare.V2_SELF_FLOORED, 10),
        **dict.fromkeys(compare.V2_REGISTERED_FLOOR, 13),
        **dict.fromkeys((EXACT_FLOATS | MEASURED_FLOATS) - compare.POST_PIVOTING_FLOATS, 14),
        **dict.fromkeys(compare.POST_PIVOTING_FLOATS, 3),
    }
    assert "u_diagonal_ratio" in MEASURED_FLOATS and by_name["u_diagonal_ratio"] == 3

    def row(path: str, solution_state: bool) -> int | None:
        if solution_state and path.startswith(".variables."):
            return 11
        if re.fullmatch(r"\.phase_branch\.[^.\[]+\.(liquid|vapor)\[\d+\]", path) or re.fullmatch(
            r"\.phase_branch\.[^.\[]+\.(liquid|vapor)_total", path
        ):
            return 12
        if re.fullmatch(r"\.limitations\[\d+\]\.value", path):
            return 9
        return by_name.get(path.rsplit(".", 1)[-1].split("[")[0])

    def walk(node: Any, path: str, solution_state: bool, found: list[str], rows: set[int]) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}", solution_state, found, rows)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]", solution_state, found, rows)
        elif isinstance(node, float) and not any(path.startswith(p) for p in EXACT_SUBTREES):
            classified = row(path, solution_state)
            if classified is None:
                found.append(path)
            else:
                rows.add(classified)

    unclassified: list[str] = []
    rows: set[int] = set()
    for name in sorted(K04_SCHEMAS):
        for path in fixtures(name):
            walk(load_json(path), "", False, unclassified, rows)
    states = sorted((FIXTURE_DIR / "solution_state" / "valid").glob("*.json"))
    assert states, "no solution-state fixture to extend A32 over"
    for path in states:
        walk(load_json(path), "", True, unclassified, rows)
    assert not unclassified, f"floats no v2 row classifies: {sorted(set(unclassified))}"
    assert {3, 11, 12} <= rows, f"the v2-only rows were never exercised: {sorted(rows)}"

    near_zero = {
        "value",
        "witness_max_diff",
        "solution_error_bound_scaled",
        "residual_inf_unscaled",
        "merit",
        "sigma_min",
    }
    unfloored = sorted(
        name
        for name in near_zero
        if name not in compare.V2_REGISTERED_FLOOR and name not in compare.V2_SELF_FLOORED
    )
    assert not unfloored, f"near-zero quantities without a v2 floor: {unfloored}"


def _walk(node: Any, path: str, found: list[str], known: frozenset[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            _walk(value, f"{path}.{key}", found, known)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            _walk(value, f"{path}[{index}]", found, known)
    elif isinstance(node, float):
        if any(path.startswith(prefix) for prefix in EXACT_SUBTREES):
            return
        key = path.rsplit(".", 1)[-1].split("[")[0]
        if key not in known:
            found.append(f"{key} (at {path})")


def test_a_check_value_is_compared_against_its_own_tolerance() -> None:
    """Why `SELF_FLOORED` exists, and that it has not become a blanket exemption.

    `checks[].value` is a residual of *some* kind and the field name says nothing about which,
    so there is no per-name floor to register. The object carries the tolerance it was judged
    by in the next field along, which is the right floor and is not an invented number.

    Measured across x86-64 and aarch64: the same check values come back as `0.0` against
    `4.4e-16` and `2.2e-16` against `-2.2e-16` — residuals at machine epsilon where the sign
    itself is noise. What must still fail is a value that actually moved.
    """
    from openflowsheet.run.compare import SELF_FLOORED, differences

    assert SELF_FLOORED["value"] == "tolerance"
    assert SELF_FLOORED["sigma_min"] == "tolerance", (
        "a singular value is floored at the SVD rank tolerance in its own escalation object, "
        "because n*eps*sigma_max is state-dependent and no constant would be right"
    )

    flow = {"value": 0.0, "tolerance": 3.1e-8}
    assert (
        differences({**flow, "value": -4.44e-16}, flow, policy_id="K04-numerical-policy-v1") == []
    )
    assert differences({**flow, "value": 5.55e-17}, flow, policy_id="K04-numerical-policy-v1") == []
    # A quantity a thousand times its own tolerance is not noise and must be caught.
    assert differences({**flow, "value": 3.1e-5}, flow, policy_id="K04-numerical-policy-v1") != []
    # And the exemption does not leak: a value with no tolerance beside it falls back.
    assert differences({"value": 1.0}, {"value": 0.0}, policy_id="K04-numerical-policy-v1") != []


def test_every_float_derived_digest_is_recognised_by_its_name() -> None:
    """ADR 0008 D2.1, enforced by a rule rather than by a list that keeps missing one.

    `state_sha256`, `full_state_sha256` and `target_state_sha256` are all digests of the
    floating-point state and none may be compared for value. Naming them individually missed
    `target_state_sha256` and cost a CI round, so the rule is the suffix: any field ending
    `state_sha256` is float-derived.

    Digests of *structure* must stay exactly compared — R0 promises structural artifacts
    bit-identical across platforms, and that promise is holding on two instruction sets.
    """
    from openflowsheet.run.compare import is_float_digest

    for name in ("state_sha256", "full_state_sha256", "target_state_sha256"):
        assert is_float_digest(name), name
    for name in ("constants_sha256", "model_version", "check_policy_sha256", "content_hash"):
        assert not is_float_digest(name), name

    certificate = load_json(
        FIXTURE_DIR / "solution_certificate" / "valid" / "syn001_nominal_verified.json"
    )
    # Substituting a different well-formed digest must be silent; changing a structural one
    # must not be.
    moved = {**certificate, "target_state_sha256": "a" * 64}
    assert differences(moved, certificate, policy_id="K04-numerical-policy-v1") == []
    forked = {**certificate, "constants_sha256": "b" * 64}
    assert differences(forked, certificate, policy_id="K04-numerical-policy-v1") != []


def test_a_target_hash_certificate_id_is_a_float_digest() -> None:
    """K04 §9: with no plan, `certificate_id` is `cert-` + the target hash's first 12 digits — a
    digest of floating-point state. CI caught it (T04's HOM-01 fixture: `cert-8e9706f6fc9b` on
    aarch64 against `cert-2c9f40f6d306`): its value is not compared, its tie to the document's own
    `target_state_sha256` is. With a plan, the id is structural and compared exactly."""
    from openflowsheet.run.compare import differences

    def certificate(digest: str, plan_id: str = "", certificate_id: str | None = None) -> dict:
        return {
            "certificate_id": certificate_id or f"cert-{plan_id or digest[:12]}",
            "plan_id": plan_id,
            "target_state_sha256": digest,
        }

    a, b = "2c9f40f6d306" + "0" * 52, "8e9706f6fc9b" + "1" * 52
    assert differences(certificate(b), certificate(a), policy_id="K04-numerical-policy-v1") == []
    assert differences(
        certificate(b, certificate_id="cert-2c9f40f6d306"),
        certificate(a),
        policy_id="K04-numerical-policy-v1",
    )
    assert (
        differences(certificate(b, "P1"), certificate(a, "P1"), policy_id="K04-numerical-policy-v1")
        == []
    )
    assert differences(
        certificate(b, "P1", "cert-P2"), certificate(a, "P1"), policy_id="K04-numerical-policy-v1"
    )
