"""RRC WO-2 (ADR 0072; design note `docs/design/RRC-revision-region-continuation.md` §5.6): the
edge's pure checks, one test per reason, on hand-built candidates over NET-02's binding.

The target is NET-02 as registered (`benchmarks/t06/cases/SYN-001-T06-NET02.yaml`). The source is
the same document with the splitter's `split_fraction` at 0.5 and the heater's outlet temperature
at 355 K, so `D` has two entries. A candidate is what §5.3's assembly would produce from a verified
solve of the source: its identity is the source declaration's, and its signature covers the region's
units. Nothing here solves; the checks read identities, ids and the signature only.
"""

from __future__ import annotations

import copy
import math
from fractions import Fraction
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT
from t05_w12_support import bind, planned_step

from openflowsheet.application.revision_binding import RevisionBinding
from openflowsheet.orchestrator import revision_continuation as module
from openflowsheet.orchestrator.execution import Region, declaration_identity
from openflowsheet.orchestrator.homotopy import Continuation, level_values, rebind
from openflowsheet.orchestrator.revision_continuation import (
    REFUSAL_HEAD,
    RevisionContinuationCandidate,
    RevisionContinuationRefusal,
    continued_parameters,
    refusal_message,
    revision_continuation,
)

NET02 = REPO_ROOT / "benchmarks" / "t06" / "cases" / "SYN-001-T06-NET02.yaml"
SPLIT = "U-SPLIT.split_fraction"
HEATER_T = "U-HEAT.T_spec"
#: A full-state digest's shape; the pure checks never read it (the region solve's opening does).
DIGEST = "0" * 64


def _document(*, split: float | None = None, heater_t: float | None = None) -> dict[str, Any]:
    document: dict[str, Any] = yaml.safe_load(NET02.read_text(encoding="utf-8"))
    if split is not None:
        (splitter,) = [item for item in document["instances"] if item["id"] == "U-SPLIT"]
        splitter["parameters"]["split_fraction"]["value"] = split
    if heater_t is not None:
        (row,) = [
            item for item in document["specifications"] if item["id"] == "SPEC-heater-outlet-T"
        ]
        row["value"] = heater_t
    return document


@pytest.fixture(scope="module")
def target() -> RevisionBinding:
    return bind(_document())


@pytest.fixture(scope="module")
def source() -> RevisionBinding:
    return bind(_document(split=0.5, heater_t=355.0))


@pytest.fixture(scope="module")
def region(target: RevisionBinding) -> Region:
    step = planned_step(target)
    assert step.region is not None
    return step.region


def _candidate(
    binding: RevisionBinding, region: Region, **changes: Any
) -> RevisionContinuationCandidate:
    model_version, constants = declaration_identity(binding.spec)
    fields: dict[str, Any] = {
        "job_id": "job-source",
        "revision_id": "SYN-001-T06-NET02-r0",
        "model_version": model_version,
        "constants_sha256": constants,
        "full_state_sha256": DIGEST,
        "signature": tuple((unit, "TWO_PHASE") for unit in region.signature_units),
        "state": {},
        "parameters": dict(binding.spec.parameters),
    }
    fields.update(changes)
    return RevisionContinuationCandidate(**fields)


def _rejected(reason: str) -> RevisionContinuationRefusal:
    return RevisionContinuationRefusal("rejected", reason)


# -- the passing case ---------------------------------------------------------------------------


def test_the_continuation_is_d_with_the_ancestors_values(
    target: RevisionBinding, source: RevisionBinding, region: Region
) -> None:
    found = revision_continuation(_candidate(source, region), target.spec, region)
    assert isinstance(found, Continuation)
    # `D` in the target's parameter order; the source's values, bitwise.
    expected = tuple(pid for pid in target.spec.parameter_ids if pid in {SPLIT, HEATER_T})
    assert set(expected) == {SPLIT, HEATER_T}
    assert found == Continuation(
        type="revision_continuation",
        parameter_ids=expected,
        variable_ids=(),
        start_values=tuple(source.spec.parameters[pid] for pid in expected),
    )
    assert dict(zip(found.parameter_ids, found.start_values, strict=True)) == {
        SPLIT: 0.5,
        HEATER_T: 355.0,
    }
    assert found.as_context() == {"type": "revision_continuation", "parameter_ids": list(expected)}
    # The λ = 0 level is the source declaration, bit for bit (§5.1; G2 (a) at the unit level).
    opening = rebind(target.spec, level_values(found, target.spec.parameters, {}, Fraction(0)))
    assert declaration_identity(opening) == declaration_identity(source.spec)


def test_d_compares_under_the_constants_encoding(target: RevisionBinding) -> None:
    """`-0.0` and `+0.0` are one constant (`canonical.encode_doubles` normalizes zeros); any other
    bit difference is a difference."""
    assert continued_parameters(target.spec.parameters, target.spec) == ()
    zeroed = rebind(target.spec, {SPLIT: 0.0})
    assert continued_parameters({**zeroed.parameters, SPLIT: -0.0}, zeroed) == ()
    nudged = {**target.spec.parameters, SPLIT: float.fromhex(target.spec.parameters[SPLIT].hex())}
    assert continued_parameters(nudged, target.spec) == ()
    nudged[SPLIT] = math.nextafter(target.spec.parameters[SPLIT], 1.0)
    assert continued_parameters(nudged, target.spec) == (SPLIT,)


# -- one test per reason, in §5.6's order --------------------------------------------------------


def test_r5_another_model_version_is_rejected(
    target: RevisionBinding, source: RevisionBinding, region: Region
) -> None:
    candidate = _candidate(source, region, model_version="syn001-other@" + "f" * 64)
    assert revision_continuation(candidate, target.spec, region) == _rejected("model_version")


def test_r5_equal_model_version_with_other_parameter_ids_is_a_defect(
    target: RevisionBinding, source: RevisionBinding, region: Region
) -> None:
    parameters = dict(source.spec.parameters)
    del parameters[SPLIT]
    candidate = _candidate(source, region, parameters=parameters)
    with pytest.raises(ValueError, match="exactly the target's inputs"):
        revision_continuation(candidate, target.spec, region)


def test_r6_an_unchanged_declaration_has_no_path(target: RevisionBinding, region: Region) -> None:
    candidate = _candidate(target, region)
    assert revision_continuation(candidate, target.spec, region) == _rejected(
        "no_changed_specification"
    )


def test_r8_a_candidate_whose_constants_are_not_its_declarations_is_rejected(
    target: RevisionBinding, source: RevisionBinding, region: Region
) -> None:
    _, constants = declaration_identity(target.spec)
    candidate = _candidate(source, region, constants_sha256=constants)
    assert revision_continuation(candidate, target.spec, region) == _rejected("level_identity")


def test_r8_passes_iff_d_is_complete(
    target: RevisionBinding,
    source: RevisionBinding,
    region: Region,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With one id dropped from `D`, the λ = 0 level keeps the target's value there and is not the
    ancestor's problem: R8 says so. With `D` whole, it passes (the passing case above)."""
    complete = continued_parameters(source.spec.parameters, target.spec)
    assert len(complete) == 2
    for dropped in complete:
        monkeypatch.setattr(
            module,
            "continued_parameters",
            lambda values, spec, dropped=dropped: tuple(
                pid for pid in continued_parameters(values, spec) if pid != dropped
            ),
        )
        assert revision_continuation(_candidate(source, region), target.spec, region) == _rejected(
            "level_identity"
        )
    monkeypatch.undo()
    assert isinstance(
        revision_continuation(_candidate(source, region), target.spec, region), Continuation
    )


def test_r9a_a_signature_missing_a_region_unit_is_rejected_naming_the_first(
    target: RevisionBinding, source: RevisionBinding, region: Region
) -> None:
    assert len(region.signature_units) >= 2
    for missing in (region.signature_units[:1], region.signature_units):
        signature = tuple(
            (unit, "TWO_PHASE") for unit in region.signature_units if unit not in missing
        )
        candidate = _candidate(source, region, signature=signature)
        assert revision_continuation(candidate, target.spec, region) == _rejected(
            f"opening(coverage:{missing[0]})"
        )
    # Extra units in the source signature are not this check's business (R9b's, in the region).
    extra = (*_candidate(source, region).signature, ("U-ELSEWHERE", "LIQUID"))
    assert isinstance(
        revision_continuation(_candidate(source, region, signature=extra), target.spec, region),
        Continuation,
    )


def test_the_first_failure_decides(
    target: RevisionBinding, source: RevisionBinding, region: Region
) -> None:
    _, constants = declaration_identity(target.spec)
    both = _candidate(source, region, constants_sha256=constants, signature=())
    assert revision_continuation(both, target.spec, region) == _rejected("level_identity")
    unchanged = _candidate(target, region, signature=())
    assert revision_continuation(unchanged, target.spec, region) == _rejected(
        "no_changed_specification"
    )
    other = _candidate(source, region, model_version="x@" + "0" * 64, signature=())
    assert revision_continuation(other, target.spec, region) == _rejected("model_version")


def test_the_refusal_message_is_r0() -> None:
    assert REFUSAL_HEAD == "revision_continuation"
    assert refusal_message(_rejected("opening(coverage:U-HEAT)")) == (
        "revision_continuation_rejected: opening(coverage:U-HEAT)"
    )
    assert refusal_message(RevisionContinuationRefusal("absent", "not_supplied")) == (
        "revision_continuation_absent: not_supplied"
    )


def test_the_checks_do_not_mutate_their_inputs(
    target: RevisionBinding, source: RevisionBinding, region: Region
) -> None:
    before = copy.deepcopy(dict(target.spec.parameters))
    candidate = _candidate(source, region)
    parameters = copy.deepcopy(dict(candidate.parameters))
    revision_continuation(candidate, target.spec, region)
    assert dict(target.spec.parameters) == before
    assert dict(candidate.parameters) == parameters
