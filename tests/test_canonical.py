"""K01: the canonical identity encoding, its properties, and the legacy one it replaced.

Production hashes big-endian IEEE-754 binary64 bytes. K01 first promoted the P02 composition
specification's §10.4 text encoding (`%.17g`, comma-joined); the Fable review of K01 argued against
ratifying that, and Frank agreed on 2026-09-18. `src/openflowsheet/canonical.py` carries the
reasons.

**Both encodings are tested here, for different reasons.**

The *production* encoding is tested on its own properties, because that is what identity now rests
on: injective over finite doubles, signed zero normalized, order and length participating, no
quantization, and the array and mapping forms agreeing.

The *legacy* encoding is tested for agreement with two independent implementations —
`spikes/p02/common/export.py`, which hashed the artifacts under `spikes/p02/results/`, and
`benchmarks/p02/judge.py`, written separately so that a harness could not certify its own hash.
Those artifacts still carry §10.4 digests, so that agreement is live evidence about them and is not
discarded merely because production moved on. Collapsing the three into one function would destroy
the property that makes them evidence.

What is *not* claimed is that the two encodings agree with each other. They do not, and are not
meant to: the digests changed, the identity semantics did not.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from benchmarks.p02.judge import _state_sha256 as judge_state_sha256
from openflowsheet.canonical import (
    ENCODING_ID,
    LEGACY_ENCODING_ID,
    constants_sha256,
    encode_doubles,
    hash_named_doubles,
    legacy_p02_hash,
    normalize_zero,
    p02_10_4_text,
    state_sha256,
)
from spikes.p02.common.export import CONSTANTS
from spikes.p02.common.export import constants_sha256 as spike_constants_sha256
from spikes.p02.common.export import state_sha256 as spike_state_sha256

#: Vectors chosen to break a careless encoding: signed zero, subnormals, values eleven decades
#: apart, exact halves, a value whose shortest repr is shorter than its 17-digit form, and
#: negatives. `0.1 + 0.2` is included because its 17-digit text differs from `0.3`'s while a
#: 15-digit one would not.
AWKWARD: list[tuple[str, ...]] = [
    ("a", "b", "c", "d", "e"),
]
VECTORS: list[dict[str, float]] = [
    {"a": 1.5, "b": -2.25, "c": 0.0, "d": 3.0e-7, "e": 1.0e5},
    {"a": -0.0, "b": 0.0, "c": 5e-324, "d": 1.7976931348623157e308, "e": 2.2250738585072014e-308},
    {"a": 0.1 + 0.2, "b": 0.3, "c": 1.0, "d": -1.0, "e": 1e-15},
    {"a": math.pi, "b": math.e, "c": math.sqrt(2.0), "d": 1.0 / 3.0, "e": 6.02214076e23},
]


@pytest.mark.parametrize("values", VECTORS)
def test_the_legacy_encoding_still_agrees_with_the_judge(values: dict[str, float]) -> None:
    """The judge is an independent witness about the P02 artifacts, and stays one."""
    order = AWKWARD[0]
    assert legacy_p02_hash(values, order) == judge_state_sha256(values, order)


@pytest.mark.parametrize("values", VECTORS)
def test_the_legacy_encoding_still_agrees_with_the_spike(values: dict[str, float]) -> None:
    """The artifacts under `spikes/p02/results/` carry digests from the spike's implementation."""
    order = AWKWARD[0]
    assert legacy_p02_hash(values, order) == spike_state_sha256(values, order)


@pytest.mark.parametrize("values", VECTORS)
def test_production_and_legacy_encodings_are_different(values: dict[str, float]) -> None:
    """Stated rather than left implicit: the digests changed, so a mix-up must be visible.

    If these ever coincided it would mean production had silently reverted, and every stored digest
    would be ambiguous about which scheme produced it.
    """
    order = AWKWARD[0]
    assert state_sha256(values, order) != legacy_p02_hash(values, order)


def test_the_legacy_entry_point_reproduces_the_recorded_p02_constants_hash() -> None:
    """P02's fixed constants still hash to their recorded digest through the named entry point.

    The spike hashes a hard-coded tuple with no names; the generalized form hashes named values in
    `parameter_ids` order. They must coincide on P02's own vector, or the artifacts P02 recorded
    could no longer be checked against anything.
    """
    parameter_ids = tuple(f"c{index}" for index in range(len(CONSTANTS)))
    values = dict(zip(parameter_ids, CONSTANTS, strict=True))
    assert legacy_p02_hash(values, parameter_ids) == spike_constants_sha256()


@pytest.mark.parametrize("values", VECTORS)
def test_dense_and_mapping_forms_agree(values: dict[str, float]) -> None:
    """The boundary passes a dense `x`; manifests carry mappings. They must hash alike."""
    order = AWKWARD[0]
    dense = np.array([values[name] for name in order], dtype=np.float64)
    assert state_sha256(dense, order) == state_sha256(values, order)
    assert hash_named_doubles([values[name] for name in order], order) == state_sha256(
        values, order
    )


def test_a_dense_vector_of_the_wrong_length_is_refused() -> None:
    """Silently hashing a mismatched pair would identify a state that does not exist."""
    order = AWKWARD[0]
    with pytest.raises(ValueError, match="does not match"):
        hash_named_doubles([1.0, 2.0], order)


def test_keys_outside_the_ordering_are_never_read() -> None:
    """ADR 0008 D2.2 excludes time by construction, not by filtering."""
    order = AWKWARD[0]
    base = dict(VECTORS[0])
    polluted = dict(base) | {"t": 1.0, "tau": 2.0, "time": 3.0, "workspace": 4.0}
    assert state_sha256(polluted, order) == state_sha256(base, order)


def test_signed_zero_normalization_is_part_of_the_encoding() -> None:
    assert normalize_zero(-0.0) == 0.0
    assert math.copysign(1.0, normalize_zero(-0.0)) == 1.0
    assert encode_doubles([-0.0]) == encode_doubles([0.0])
    assert encode_doubles([-1.0]) != encode_doubles([1.0])


def test_the_encoding_round_trips_every_double_it_writes() -> None:
    """Eight bytes of binary64 lose nothing; this is that being true rather than assumed."""
    for values in VECTORS:
        for value in values.values():
            decoded = np.frombuffer(encode_doubles([value]), dtype=">f8")
            assert decoded.tolist() == [normalize_zero(value)]


def test_the_encoding_is_eight_big_endian_bytes_per_value() -> None:
    """Big-endian so the digest is a property of the numbers, not of the host's byte order."""
    assert len(encode_doubles([1.0, 2.0, 3.0])) == 24
    assert encode_doubles([1.0]) == b"\x3f\xf0\x00\x00\x00\x00\x00\x00"


def test_the_legacy_text_encoding_is_still_what_it_was() -> None:
    """It is retained as evidence about the P02 artifacts, so it must not drift either."""
    assert p02_10_4_text([1.5, -0.0, 1e5]) == "1.5,0,100000"


def test_one_ulp_changes_survive_the_encoding() -> None:
    """ADR 0008 D2.6: a quantized hash is forbidden on the exact path."""
    for values in VECTORS:
        for name, value in values.items():
            if not math.isfinite(value):
                continue
            stepped = dict(values)
            stepped[name] = math.nextafter(value, math.inf)
            if stepped[name] == value:
                continue
            assert state_sha256(stepped, AWKWARD[0]) != state_sha256(values, AWKWARD[0]), name


def test_non_finite_values_encode_rather_than_raise() -> None:
    """An invalid trial state is reported through EvaluationStatus, not by the hash exploding."""
    assert len(encode_doubles([float("nan")])) == 8
    decoded = np.frombuffer(encode_doubles([float("inf"), float("-inf")]), dtype=">f8")
    assert decoded.tolist() == [float("inf"), float("-inf")]


def test_the_encodings_are_identified_so_digests_cannot_be_compared_across_schemes() -> None:
    assert ENCODING_ID == "ieee754-be-v1"
    assert LEGACY_ENCODING_ID == "p02-10.4"
    assert ENCODING_ID != LEGACY_ENCODING_ID


def test_variable_order_participates() -> None:
    """ADR 0008 D2.1 (H2), asserted against the production implementation, not only the judge.

    The agreement tests above tie production to the judge on four vectors, and the judge's own
    H1-H6 pin the rules; but an implication that holds "on the vectors we happened to try" is a
    weaker statement than the property itself. D2's rules are cheap to assert directly, so they are.
    """
    order = AWKWARD[0]
    base = dict(VECTORS[0])
    swapped = dict(base)
    swapped["a"], swapped["b"] = base["b"], base["a"]
    assert state_sha256(swapped, order) != state_sha256(base, order)


def test_state_length_participates() -> None:
    """ADR 0008 D2.1 (H5): a shorter ordering is a different state, not a prefix of the same one."""
    base = dict(VECTORS[0])
    assert state_sha256(base, AWKWARD[0][:-1]) != state_sha256(base, AWKWARD[0])


def test_constants_sha256_is_the_same_primitive_over_a_different_named_vector() -> None:
    """ADR 0008 D4.1's entry point, under the production encoding.

    `state_sha256` and `constants_sha256` must stay two *uses* of one operation rather than two
    implementations of it: drift between them would be drift between what identifies a state and
    what identifies the problem it is a state of.
    """
    values = {"feed_A": 1.0, "h_feed": 0.0, "t_spec": 360.0}
    order = ("feed_A", "h_feed", "t_spec")
    assert constants_sha256(values, order) == hash_named_doubles(values, order)
    assert constants_sha256(values, order) == state_sha256(values, order)

    # And the declared order is load-bearing, not incidental.
    assert constants_sha256(values, ("h_feed", "feed_A", "t_spec")) != constants_sha256(
        values, order
    )
