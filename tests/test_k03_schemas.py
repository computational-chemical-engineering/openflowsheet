"""K03 M6: the five interfaces joining the plan §2.2 freeze, and their round-trip fixtures.

`SolvePolicy`, `SolvePlan`, `SolveEvent`, `AttemptContext` and `Checkpoint` metadata. From here
a field added is a migration, so the shapes are pinned against real documents and the documents
are **generated from a real solve** rather than written by hand — the same rule P01 applied to
the `ProcessRevision` fixtures, and for the same reason: a fixture written to match a schema
tests the author's reading of the schema, and a fixture emitted by the code tests the code.

Round trip means: load, validate, dump to JSON, reload, validate again, and require the two
decoded documents to be equal.
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

from openflowsheet.run.compare import differences, pinned_digests

SCHEMA_DIR = REPO_ROOT / "schemas"
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "schemas"

K03_SCHEMAS = {
    "solve_policy": "solve-policy.schema.json",
    "solve_plan": "solve-plan.schema.json",
    "solve_event": "solve-event.schema.json",
    "attempt_context": "attempt-context.schema.json",
    "checkpoint": "checkpoint.schema.json",
}


def _registry() -> Registry:
    resources = []
    for path in sorted(SCHEMA_DIR.glob("*.schema.json")):
        document = load_json(path)
        resources.append((document["$id"], Resource(contents=document, specification=DRAFT202012)))
    return Registry().with_resources(resources)


REGISTRY = _registry()


def validator_for(name: str) -> Draft202012Validator:
    return Draft202012Validator(load_json(SCHEMA_DIR / K03_SCHEMAS[name]), registry=REGISTRY)


def errors_for(name: str, document: Any) -> list[str]:
    validator = validator_for(name)
    return [
        f"{list(error.absolute_path)}: {error.message}"
        for error in sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))
    ]


def fixtures(name: str) -> list[Path]:
    return sorted((FIXTURE_DIR / name / "valid").glob("*.json"))


@pytest.mark.parametrize("name", sorted(K03_SCHEMAS))
def test_the_schema_is_itself_valid(name: str) -> None:
    Draft202012Validator.check_schema(load_json(SCHEMA_DIR / K03_SCHEMAS[name]))


@pytest.mark.parametrize("name", sorted(K03_SCHEMAS))
def test_every_interface_has_at_least_one_fixture(name: str) -> None:
    """A schema with no document is a shape nothing has ever had to satisfy."""
    assert fixtures(name), f"no round-trip fixture for {name}"


@pytest.mark.parametrize(
    ("name", "path"),
    [(name, path) for name in sorted(K03_SCHEMAS) for path in fixtures(name)],
    ids=lambda value: value.stem if isinstance(value, Path) else str(value),
)
def test_the_fixtures_validate_and_round_trip(name: str, path: Path) -> None:
    document = load_json(path)
    payload = document if isinstance(document, list) else [document]
    for entry in payload:
        assert errors_for(name, entry) == [], f"{path.name}: {errors_for(name, entry)}"
    reloaded = json.loads(json.dumps(document))
    assert reloaded == document
    for entry in reloaded if isinstance(reloaded, list) else [reloaded]:
        assert errors_for(name, entry) == []


def test_the_fixtures_are_what_the_code_emits_today() -> None:
    """Generated, not written: a hand-made fixture tests the author's reading of the schema.

    Every one of the six documents is compared against a live solve, not two of them — the
    first version of this test regenerated only the policy and the plan, and the three frozen
    files it left alone included an attempt context that was internally impossible: it named
    the *converged* `TWO_PHASE` checkpoint as the thing the restart attempt opened from, when
    a restart by construction opens from the `partial` checkpoint of the regime it is leaving.
    Nothing could have caught that except regenerating it.

    Comparing against a live solve also makes the fixtures a regression test on the whole
    stack: a changed scale, a renamed row or a different elimination all show up here.

    **Not byte-exactly, though, and it used to be.** Two `ubuntu-latest` runners disagreed on
    the converged state's last bits and then an aarch64 runner disagreed with both; the
    comparison rule and the measurements behind it are in `tests/reproducibility.py`. The
    byte-exact version also pinned 39 digest values, which ADR 0008 D2.1 forbids outright.
    """
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from k03_schema_fixtures import documents
    from t04_schema_fixtures import FIXTURE_NAMES as T04_FIXTURES

    emitted = documents()
    # T04's fixtures share these schema directories and are regenerated and compared by T04's
    # own generator and test (`tests/test_t04_schemas.py`); every other file must be this one's.
    assert set(emitted) | {name for name in T04_FIXTURES if name.split("/")[0] in K03_SCHEMAS} == {
        str(path.relative_to(FIXTURE_DIR)) for name in K03_SCHEMAS for path in fixtures(name)
    }, "a fixture exists that nothing regenerates, or vice versa"
    for name, document in emitted.items():
        found = differences(
            document, load_json(FIXTURE_DIR / name), policy_id="K04-numerical-policy-v1"
        )
        assert not found, (
            f"{name} is not what the code emits:\n  "
            + "\n  ".join(found)
            + "\nIf this is an intended change, regenerate with "
            "`python scripts/k03_schema_fixtures.py --write`."
        )


def test_the_restart_context_opens_from_the_regime_it_is_leaving() -> None:
    """§9.3, and what the hand-written fixture got wrong.

    The restart point is a *rejected trial* inside the new regime, but the checkpoint it is
    opened from is the last accepted state of the old one — `partial`, never `candidate_root`,
    because an attempt that had converged would not be restarting.
    """
    document = load_json(FIXTURE_DIR / "attempt_context" / "valid" / "syn001_restart.json")
    assert document["opened_reason"] == "phase_update"
    assert document["attempt_index"] == 1
    opened_from = document["opened_from"]
    assert opened_from["attempt_index"] == document["attempt_index"] - 1
    assert opened_from["label"] == "partial"
    assert opened_from["signature"] == [["U-FLASH", "LIQUID"]]
    assert document["signature"] == [["U-FLASH", "TWO_PHASE"]]
    assert opened_from["residual_inf_unscaled"] > 0.0


def test_the_solve_keeps_the_context_each_attempt_ran_under() -> None:
    """§12.4 and [A01]: the attempt's authority for scales and signature, not a derived record.

    K05 replays an attempt, and an attempt whose context was discarded cannot be replayed.
    """
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from k03_schema_fixtures import OFF_B, POLICY, flowsheet

    from openflowsheet.orchestrator.tear import solve_tear

    result, _ = solve_tear(flowsheet(), policy=POLICY, initial_recycle=OFF_B)
    assert len(result.contexts) == result.attempts == 2
    assert [context.attempt_index for context in result.contexts] == [0, 1]
    assert [context.signature for context in result.contexts] == list(result.signatures)
    assert [context.opened_reason for context in result.contexts] == ["initial", "phase_update"]
    assert result.contexts[0].opened_from is None
    for context in result.contexts:
        assert errors_for("attempt_context", context.as_document()) == []


def test_every_emitted_document_validates_against_its_schema() -> None:
    """The fixtures validate; so must whatever the code emits, before it is ever committed."""
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from k03_schema_fixtures import documents

    for name, document in documents().items():
        schema = name.split("/")[0]
        for entry in document if isinstance(document, list) else [document]:
            assert errors_for(schema, entry) == [], f"{name}: {errors_for(schema, entry)}"


# ------------------------------------------------------- what a JSON Schema cannot express


def test_a_plan_whose_inner_block_is_not_square_is_refused() -> None:
    """`UNSUPPORTED_RANK_STRUCTURE`. A schema can count neither block nor compare the two."""
    from openflowsheet.orchestrator.trace import SolvePlan

    common: dict[str, Any] = {
        "plan_id": "p",
        "model_version": "m@" + "0" * 64,
        "constants_sha256": "0" * 64,
        "policy_id": "q",
        "tear_variable_ids": ("t",),
        "tear_row_ids": ("R",),
        "eliminated_rows": (),
        "column_scales": {},
        "row_scales": {},
        "scale_provenance": "registered nominals",
        "bounds": {},
        "signature_units": (),
        "initializer_chain": (),
        "estimates": {},
    }
    SolvePlan(inner_variable_ids=("a", "b"), inner_row_ids=("x", "y"), **common)
    with pytest.raises(ValueError, match="UNSUPPORTED_RANK_STRUCTURE"):
        SolvePlan(inner_variable_ids=("a", "b"), inner_row_ids=("x",), **common)
    with pytest.raises(ValueError, match="tear rows"):
        SolvePlan(
            inner_variable_ids=("a",),
            inner_row_ids=("x",),
            **{**common, "tear_row_ids": ("R", "S")},
        )


def test_a_trace_never_serializes_a_non_finite_number() -> None:
    """ADR 0002 D3's canonical JSON refuses one, and a 0.0 standing in would be a false reading.

    `plan_built` has no residual and no merit — it precedes every evaluation — so both are
    `null` rather than zero.
    """
    trace = load_json(FIXTURE_DIR / "solve_event" / "valid" / "syn001_nominal_trace.json")
    assert trace[0]["kind"] == "plan_built"
    assert trace[0]["residual_inf_unscaled"] is None
    assert trace[0]["merit"] is None
    raw = (FIXTURE_DIR / "solve_event" / "valid" / "syn001_nominal_trace.json").read_text()
    for spelling in ("NaN", "Infinity", "-Infinity"):
        assert spelling not in raw


def test_the_trace_sequence_is_dense_and_strictly_increasing() -> None:
    for name in ("syn001_nominal_trace.json", "syn001_off_b_restart_trace.json"):
        trace = load_json(FIXTURE_DIR / "solve_event" / "valid" / name)
        assert [event["sequence"] for event in trace] == list(range(len(trace))), name
        assert trace[0]["kind"] == "plan_built", name
        assert trace[-1]["kind"] == "solve_closed", name


def test_the_restart_trace_shows_two_attempts_and_no_repeated_signature() -> None:
    """The document a reader would actually inspect after a phase restart."""
    trace = load_json(FIXTURE_DIR / "solve_event" / "valid" / "syn001_off_b_restart_trace.json")
    opened = [event for event in trace if event["kind"] == "attempt_opened"]
    assert [event["signature"][0][1] for event in opened] == ["LIQUID", "TWO_PHASE"]
    assert opened[1]["message"] == "phase_update(phase_wall(patience, U-FLASH:LIQUID->TWO_PHASE))"
    closed = [event for event in trace if event["kind"] == "attempt_closed"]
    assert [event["outcome"] for event in closed] == ["PHASE_UPDATE_REQUIRED", "CONVERGED"]
    assert trace[-1]["outcome"] == "CONVERGED"


def test_a_checkpoint_never_claims_more_than_unverified() -> None:
    """K03 issues no certificate. A solver that verified its own answer is §8.2's warning."""
    document = load_json(FIXTURE_DIR / "checkpoint" / "valid" / "syn001_candidate_root.json")
    assert document["verification_scope"] == "unverified"
    assert document["label"] in ("partial", "candidate_root")

    broken = {**document, "verification_scope": "verified"}
    assert errors_for("checkpoint", broken) != []


def test_an_attempt_context_never_serializes_its_workspace() -> None:
    """ADR 0008 D1.4: `workspace` is inert, so a document carrying it would claim otherwise."""
    document = load_json(FIXTURE_DIR / "attempt_context" / "valid" / "syn001_restart.json")
    for key in ("evaluation_context", "flowsheet_context"):
        assert "workspace" not in document[key]
        assert set(document[key]) == {
            "model_version",
            "constants_sha256",
            "phase_signature",
            "accuracy_policy",
        }
    assert document["evaluation_context"]["phase_signature"] is None, (
        "the lifted function has no phase switch; pinning one would claim it does"
    )
    assert document["scale_segment"] == 0


def test_a_policy_cannot_declare_an_unregistered_merit_or_rank_policy() -> None:
    """Single-valued literals: a second policy must be a new value a reader can see."""
    document = load_json(FIXTURE_DIR / "solve_policy" / "valid" / "syn001_k03.json")
    assert errors_for("solve_policy", document) == []
    for field, value in (
        ("merit", "sum_of_squares"),
        ("redundant_row_policy", "least_squares"),
        ("cycle_rule", "allow_repeats"),
        ("derivative_path", "guess"),
        ("phase_contract", "T02-interim"),
    ):
        assert errors_for("solve_policy", {**document, field: value}) != [], field
    # T03 A01: the rule set is required, not defaulted — a policy that omits it is refused.
    without = {key: value for key, value in document.items() if key != "phase_contract"}
    assert errors_for("solve_policy", without) != []


def test_a_scale_of_zero_is_refused_by_the_schema() -> None:
    """A scale divides. Zero or negative is a division by zero or a silent sign flip."""
    document = load_json(FIXTURE_DIR / "solve_plan" / "valid" / "syn001_nominal.json")
    assert errors_for("solve_plan", document) == []
    broken = {**document, "row_scales": {**document["row_scales"], "U-FEED:FEED-P": 0.0}}
    assert errors_for("solve_plan", broken) != []


def test_no_fixture_pins_a_digest_of_floating_point_state() -> None:
    """ADR 0008 D2.1: "no test may pin a digest value". Nothing enforced it until now.

    The rule is not pedantry. A `state_sha256` covers exactly the dense state vector at full
    double precision (D2.1's coverage rule), so pinning one asserts bit-exact floating point —
    which blueprint §8.3 explicitly declines to promise across platforms, and which two
    `ubuntu-latest` runners were measured disagreeing about on 2026-09-21.

    The fixtures still *carry* digests, because they are documents a real solve emitted and the
    schema requires the field. What is forbidden is comparing the value, so the check here is
    behavioural: perturb every digest in the document and the comparison must stay silent.
    """
    compared: list[str] = []
    for name in sorted(K03_SCHEMAS):
        for path in fixtures(name):
            document = load_json(path)
            carried = pinned_digests(document)
            if not carried:
                continue
            # A *different but well formed* digest. Prepending a character instead would
            # test the shape rule and prove nothing about the value rule.
            poisoned = json.loads(
                re.sub(
                    r'"state_sha256": "[0-9a-f]{64}"',
                    f'"state_sha256": "{"a" * 64}"',
                    json.dumps(document),
                )
            )
            if differences(poisoned, document, policy_id="K04-numerical-policy-v1") != []:
                compared.append(f"{path.name}: {carried}")
    assert not compared, (
        "these fixtures carry digest values that the comparison actually compares, against "
        "ADR 0008 D2.1:\n  " + "\n  ".join(compared)
    )
    assert any(
        pinned_digests(load_json(path)) for name in K03_SCHEMAS for path in fixtures(name)
    ), "no fixture carries a digest at all, so the check above proved nothing"


def test_the_comparison_still_catches_what_it_is_for() -> None:
    """Loosening bit-exactness must not loosen the regression test underneath it.

    A changed scale, a renamed row, a different elimination, a lost event, a changed count or
    a changed outcome must all still fail. Only last-ulp float motion and digests are forgiven.
    """
    trace = load_json(FIXTURE_DIR / "solve_event" / "valid" / "syn001_nominal_trace.json")
    plan = load_json(FIXTURE_DIR / "solve_plan" / "valid" / "syn001_nominal.json")

    assert differences(trace, trace, policy_id="K04-numerical-policy-v1") == []
    assert differences(trace[:-1], trace, policy_id="K04-numerical-policy-v1") != [], "a lost event"

    renamed = json.loads(json.dumps(plan).replace("S6.n.A", "S6.n.Z"))
    assert differences(renamed, plan, policy_id="K04-numerical-policy-v1") != [], (
        "a renamed row or variable"
    )

    rescaled = json.loads(json.dumps(plan))
    key = next(iter(rescaled["column_scales"]))
    rescaled["column_scales"][key] *= 1.01
    assert differences(rescaled, plan, policy_id="K04-numerical-policy-v1") != [], "a changed scale"

    fewer = json.loads(json.dumps(plan))
    fewer["eliminated_rows"] = fewer["eliminated_rows"][:1]
    assert differences(fewer, plan, policy_id="K04-numerical-policy-v1") != [], (
        "a different elimination"
    )

    miscounted = json.loads(json.dumps(trace))
    miscounted[-1]["counters"]["factorizations"] += 1
    assert differences(miscounted, trace, policy_id="K04-numerical-policy-v1") != [], (
        "a changed solver counter"
    )

    # The three property counters are the deliberate exception: they are measurably not
    # reproducible (the test below), so they are checked for being counts and not for value.
    property_moved = json.loads(json.dumps(trace))
    property_moved[-1]["counters"]["property_calls"] += 130
    assert differences(property_moved, trace, policy_id="K04-numerical-policy-v1") == [], (
        "a property counter must be forgiven"
    )
    not_a_count = json.loads(json.dumps(trace))
    not_a_count[-1]["counters"]["property_calls"] = -1
    assert differences(not_a_count, trace, policy_id="K04-numerical-policy-v1") != [], (
        "but it must still be a count"
    )

    outcome = json.loads(json.dumps(trace))
    outcome[-1]["outcome"] = "STAGNATION"
    assert differences(outcome, trace, policy_id="K04-numerical-policy-v1") != [], (
        "a changed outcome"
    )

    # And what it must forgive: the measured cross-architecture motion, reproduced.
    nudged = json.loads(json.dumps(trace))
    for event in nudged:
        if isinstance(event.get("merit"), float):
            event["merit"] *= 1.0 + 2.2e-14
    assert differences(nudged, trace, policy_id="K04-numerical-policy-v1") == [], (
        "last-ulp float motion must be forgiven"
    )


def test_a_malformed_digest_is_still_refused() -> None:
    """Not compared is not unchecked: the shape is a claim the document still makes."""
    document = load_json(FIXTURE_DIR / "checkpoint" / "valid" / "syn001_candidate_root.json")
    assert differences(document, document, policy_id="K04-numerical-policy-v1") == []
    for bad in ("not-a-digest", "ABCDEF" + "0" * 58, "0" * 63, 17):
        assert (
            differences(
                {**document, "state_sha256": bad}, document, policy_id="K04-numerical-policy-v1"
            )
            != []
        ), repr(bad)


def test_the_property_counters_are_measurably_not_reproducible() -> None:
    """Why `UNREPRODUCIBLE_COUNTERS` exists, held as a measurement rather than an opinion.

    Perturbing the OFF-B start by one ulp and re-solving moves the three property counters by
    over a tenth while every structural quantity stays put. Excluding them from the document
    comparison is therefore what the measurement says, not a concession to a red gate — and
    this test is here so that a later session cannot quietly re-assert their portability
    without first making this measurement come out differently.

    It also pins the other half, which matters more: the three *solver* counters and the whole
    outer control flow are bit-stable under the same perturbation, and they stay compared
    exactly.
    """
    import math
    import sys

    from openflowsheet.orchestrator.tear import solve_tear
    from openflowsheet.run.compare import UNREPRODUCIBLE_COUNTS

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from k03_schema_fixtures import OFF_B, POLICY, flowsheet

    chaotic: dict[str, set[int]] = {
        name: set()
        for name in UNREPRODUCIBLE_COUNTS
        if name.startswith(("property", "requested", "cache"))
    }
    stable: dict[str, set[int]] = {
        name: set() for name in ("residual_calls", "jacobian_calls", "factorizations")
    }
    structure: set[tuple[Any, ...]] = set()
    fill: set[tuple[int, ...]] = set()

    for step in (-2, -1, 0, 1, 2):
        start = list(OFF_B)
        value = start[2]
        for _ in range(abs(step)):
            value = math.nextafter(value, math.inf if step > 0 else -math.inf)
        start[2] = value

        result, trace = solve_tear(flowsheet(), policy=POLICY, initial_recycle=tuple(start))
        fill.add(
            tuple(
                event.linear.nnz_l
                for event in trace.of_kind("linear_solve")
                if event.linear is not None
            )
        )
        for name in chaotic:
            chaotic[name].add(getattr(result.counters, name))
        for name in stable:
            stable[name].add(getattr(result.counters, name))
        structure.add(
            (
                result.outcome,
                result.attempts,
                result.iterations,
                tuple(signature[0][1] for signature in result.signatures),
                len(trace),
            )
        )

    assert len(structure) == 1, f"the outer solve is not ulp-stable after all: {structure}"
    for name, values in stable.items():
        assert len(values) == 1, f"{name} was believed stable and varies over {sorted(values)}"
    assert len(fill) > 1, (
        "nnz(L) no longer varies under a one-ulp perturbation, so filing the fill counts as "
        "pivot-determined is no longer justified by measurement — re-derive the rule or "
        "delete it"
    )
    varying = [name for name, values in chaotic.items() if len(values) > 1]
    assert varying, (
        "no property counter varied under a one-ulp perturbation, so excluding them from the "
        "comparison is no longer justified by measurement — re-derive the rule or delete it"
    )


def test_a01_a_converged_solve_hands_over_the_full_state_and_its_hash() -> None:
    """K04 §3.1 / A01, closing the Fable review of K03's finding S2.

    `Checkpoint.state_sha256` covers exactly the variables the solver iterated on — three, for
    this tear — which is ADR 0008 D2.1's coverage rule and is right. The certificate is about
    the other forty-four as well, so the converged state and its own hash are handed over
    rather than left for the verifier to rebuild: a verifier that reconstructs the state it
    then judges has chosen that state.
    """
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from k03_schema_fixtures import OFF_B, POLICY, flowsheet

    from openflowsheet.compile.reference import state_vector
    from openflowsheet.orchestrator.tear import Syn001TearProblem, solve_tear
    from openflowsheet.orchestrator.trace import SolvePolicy

    result, _ = solve_tear(flowsheet(), policy=POLICY)
    assert result.outcome == "CONVERGED"
    assert result.final_state is not None
    assert result.checkpoint is not None

    tear = Syn001TearProblem(flowsheet())
    assert set(result.final_state) == set(tear.spec.variable_ids)
    assert len(result.final_state) == 47

    # The recorded hash is the compiled residual's own, so a verifier can assert it against its
    # own evaluation instead of trusting a digest computed by another route.
    evaluation = tear.compiled.residual(
        __import__("numpy").array(state_vector(tear.spec, result.final_state)), tear.context
    )
    assert result.checkpoint.full_state_sha256 == evaluation.state_sha256
    assert result.checkpoint.full_state_sha256 != result.checkpoint.state_sha256, (
        "the full state and the tear vector are different states and must hash differently"
    )

    # A failed solve hands over nothing to certify.
    capped = SolvePolicy(
        policy_id="capped", residual_tolerances={}, scales={}, max_property_calls=20
    )
    failed, _ = solve_tear(flowsheet(), policy=capped, initial_recycle=OFF_B)
    assert failed.outcome != "CONVERGED"
    assert failed.final_state is None


def test_the_widened_verification_scope_is_still_unverified_from_k03() -> None:
    """K04 §8.3 widens the literal; K03 must go on writing only the narrowest value.

    The widening exists so the *verifier* can say `checked_partial` and `certified`. A solver
    that wrote either would be the injected-false-success failure §8.2 warns about, so the
    schema admits three values and K03's own output is asserted to use one.
    """
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from k03_schema_fixtures import OFF_B, POLICY, flowsheet

    from openflowsheet.orchestrator.tear import solve_tear

    schema = load_json(SCHEMA_DIR / K03_SCHEMAS["checkpoint"])
    assert schema["properties"]["verification_scope"]["enum"] == [
        "unverified",
        "checked_partial",
        "certified",
    ]

    for start in (None, OFF_B):
        result, _ = solve_tear(flowsheet(), policy=POLICY, initial_recycle=start)
        assert result.checkpoint is not None
        assert result.checkpoint.verification_scope == "unverified"
