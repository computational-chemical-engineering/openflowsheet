"""RRC WO-1 (ADR 0072; design note `docs/design/RRC-revision-region-continuation.md` §5.1, §5.2):
the revision continuation's level values, the policy that selects it, and the three additive
schema widenings.

- `level_values` on a `revision_continuation`: λ = 0 returns `start_values` bitwise; λ = 1/2 is
  `p* + ½(p_src − p*)` formed in exact rationals and rounded once; λ = 1 is refused; the opening is
  not read.
- `level_values` on a `specification_continuation` is today's function: on HOM-01's inputs it
  equals, bitwise at every dyadic λ < 1 down to 1/1024, a frozen copy of the pre-RRC body.
- `RRC-revision-v1` is `T06-revision-v2` with only `globalization.eo_recovery` changed.
- A `revision_continuation` attempt context and certificate item validate; the old documents do.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from conftest import load_json
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from openflowsheet.application.policies import RRC_REVISION_V1, T06_REVISION_V2
from openflowsheet.orchestrator.homotopy import Continuation, level_values
from openflowsheet.run.manifest import policy_sha256

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "schemas"
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "schemas"
REGISTRY = Registry().with_resources(
    (document["$id"], Resource(contents=document, specification=DRAFT202012))
    for document in (load_json(path) for path in sorted(SCHEMA_DIR.glob("*.schema.json")))
)
NEW_VALUE = "homotopy_or_revision_continuation_or_sequential_restart"

#: Hand-picked values whose binary64 expansions are long (none is a dyadic), with both signs and
#: a large magnitude ratio, so a second rounding would show.
PARAMETERS = ("U-SPLIT.split_fraction", "U-HEAT.T_out", "U-FLASH.Q")
TARGET = {"U-SPLIT.split_fraction": 0.9, "U-HEAT.T_out": 351.37, "U-FLASH.Q": -90142.27103988026}
SOURCE = (0.2, 357.1, 24681.106068625242)

#: HOM-01's inputs, as `tests/test_t04_homotopy.py`'s A02 level-value test pins them.
HOM01_CONTINUED = "SPEC:SPEC-flash-duty"
HOM01_TARGET = {HOM01_CONTINUED: 24681.106068625242}
HOM01_OPENING = {"U-FLASH.Q": -90142.27103988026}


def revision() -> Continuation:
    return Continuation("revision_continuation", PARAMETERS, (), SOURCE)


def _today(
    continuation: Continuation,
    target: Mapping[str, float],
    opening: Mapping[str, float],
    lam: Fraction,
) -> dict[str, float]:
    """`level_values` as it stood at `e45628fd`, verbatim, for the specification continuation."""
    if lam == 1:
        raise ValueError("the λ = 1 level is the target instance itself; it is never re-bound")
    values: dict[str, float] = {}
    pairs = zip(continuation.parameter_ids, continuation.variable_ids, strict=True)
    for parameter, column in pairs:
        star = Fraction(target[parameter])
        start = Fraction(opening[column])
        values[parameter] = float(star + (1 - lam) * (start - star))
    return values


def _bits(values: Mapping[str, float]) -> dict[str, str]:
    return {key: value.hex() for key, value in values.items()}


# -- level values ----------------------------------------------------------------------------


def test_level_values_lambda_zero_returns_the_start_values_bitwise() -> None:
    values = level_values(revision(), TARGET, {}, Fraction(0))
    assert list(values) == list(PARAMETERS)
    assert _bits(values) == _bits(dict(zip(PARAMETERS, SOURCE, strict=True)))


def test_level_values_lambda_half_is_formed_exactly_and_rounded_once() -> None:
    values = level_values(revision(), TARGET, {}, Fraction(1, 2))
    for parameter, source in zip(PARAMETERS, SOURCE, strict=True):
        star = Fraction(TARGET[parameter])
        expected = float(star + Fraction(1, 2) * (Fraction(source) - star))
        assert values[parameter].hex() == expected.hex()


def test_level_values_lambda_one_is_refused() -> None:
    with pytest.raises(ValueError, match="never re-bound"):
        level_values(revision(), TARGET, {}, Fraction(1))


def test_level_values_revision_continuation_reads_no_opening() -> None:
    """The opening is not read: an empty mapping and one with every id give the same values."""
    for lam in (Fraction(0), Fraction(1, 4), Fraction(3, 4), Fraction(1023, 1024)):
        poisoned = {key: float("nan") for key in (*PARAMETERS, "U-FLASH.Q")}
        assert _bits(level_values(revision(), TARGET, {}, lam)) == _bits(
            level_values(revision(), TARGET, poisoned, lam)
        )


def test_level_values_specification_continuation_is_todays_on_hom_01() -> None:
    continuation = Continuation("specification_continuation", (HOM01_CONTINUED,), ("U-FLASH.Q",))
    assert continuation.start_values == ()
    for denominator in (1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024):
        for numerator in range(denominator):
            lam = Fraction(numerator, denominator)
            assert _bits(level_values(continuation, HOM01_TARGET, HOM01_OPENING, lam)) == _bits(
                _today(continuation, HOM01_TARGET, HOM01_OPENING, lam)
            )


def test_level_values_a_malformed_revision_continuation_is_refused() -> None:
    with pytest.raises(ValueError, match="no columns"):
        Continuation("revision_continuation", PARAMETERS, ("U-FLASH.Q",) * 3, SOURCE)
    with pytest.raises(ValueError, match="one start value per parameter"):
        Continuation("revision_continuation", PARAMETERS, (), SOURCE[:2])


def test_the_attempt_context_member_is_type_and_parameter_ids() -> None:
    assert revision().as_context() == {
        "type": "revision_continuation",
        "parameter_ids": list(PARAMETERS),
    }


# -- the policy --------------------------------------------------------------------------------


def test_rrc_revision_v1_is_t06_revision_v2_with_only_eo_recovery_changed() -> None:
    rrc, base = RRC_REVISION_V1.as_document(), T06_REVISION_V2.as_document()
    assert rrc["policy_id"] == "RRC-revision-v1" and base["policy_id"] == "T06-revision-v2"
    assert rrc["globalization"]["eo_recovery"] == NEW_VALUE
    assert base["globalization"]["eo_recovery"] == "homotopy_or_sequential_restart"
    expected = copy.deepcopy(base)
    expected["policy_id"] = "RRC-revision-v1"
    expected["globalization"]["eo_recovery"] = NEW_VALUE
    assert rrc == expected
    # The base's registered hash (`tests/test_t07_w3a_revision_runs.py`) is untouched.
    assert policy_sha256(T06_REVISION_V2) == (
        "c03d7205fb445b4e3c0d2c5d712c04fc60fbb6bde1f8ff753c7cedffd61c66ab"
    )


# -- the schema widenings (ADR 0072 C1; FQ1) ---------------------------------------------------


def _errors(schema: str, document: Any) -> list[str]:
    validator = Draft202012Validator(load_json(SCHEMA_DIR / schema), registry=REGISTRY)
    return [error.message for error in validator.iter_errors(document)]


def test_the_policy_document_validates() -> None:
    assert _errors("solve-policy.schema.json", RRC_REVISION_V1.as_document()) == []
    bogus = RRC_REVISION_V1.as_document()
    bogus["globalization"]["eo_recovery"] = "revision_continuation"
    assert _errors("solve-policy.schema.json", bogus) != []


def test_a_revision_continuation_attempt_context_validates() -> None:
    document = load_json(FIXTURE_DIR / "attempt_context/valid/t04_hom05_homotopy.json")
    assert document["continuation"]["type"] == "specification_continuation"
    assert _errors("attempt-context.schema.json", document) == []
    document["continuation"] = revision().as_context()
    assert _errors("attempt-context.schema.json", document) == []
    document["continuation"]["type"] = "arclength_continuation"
    assert _errors("attempt-context.schema.json", document) != []


def test_a_revision_continuation_certificate_item_validates() -> None:
    document = load_json(FIXTURE_DIR / "solution_certificate/valid/t04_hom01_bound_verified.json")
    item = document["branch_provenance"][2]["continuation"]
    assert item["type"] == "specification_continuation"
    assert _errors("solution-certificate.schema.json", document) == []
    item["type"] = "revision_continuation"
    assert _errors("solution-certificate.schema.json", document) == []
    item["type"] = "arclength_continuation"
    assert _errors("solution-certificate.schema.json", document) != []
