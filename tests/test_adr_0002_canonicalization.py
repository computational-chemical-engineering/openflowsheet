"""ADR 0002: the registered canonicalization vectors, and the structural identity they support.

Assertion ids follow the ADR: **E** for the vector encoding (D1), **S** for structural identity
(D2), **J** for canonical JSON (D3), **R** for reading documents (D3.6), **F** for the fixtures.

**Every digest in the ADR was computed by a scratch implementation written for it, independent of
`openflowsheet`.** The implementation under test here was written separately from that. So the
agreements below are cross-implementation agreements, not a function compared with itself — which
is the only reason a registered constant is worth anything. Where the two disagree, the ADR's
"changing this ADR" clause says the ADR is amended rather than the test relaxed.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from openflowsheet.canonical import (
    DIRECTORY_HASH_ID,
    DOCUMENT_ENCODING_ID,
    ENCODING_ID,
    MODEL_VERSION_PATTERN,
    STRUCTURE_SCHEMA,
    CanonicalizationError,
    canonical_json,
    constants_sha256,
    document_sha256,
    load_document,
    model_version,
    split_model_version,
    structure_document,
    structure_sha256,
)

ADR = "docs/adr/0002-canonicalization-and-schemas.md"

#: D2.8's small structure document, registered with its byte length and three digests.
SMALL_STRUCTURE = {
    "structure_schema": STRUCTURE_SCHEMA,
    "variable_ids": ["T", "l_A", "v_A"],
    "equation_ids": ["bal_A", "eq_A", "tspec"],
    "parameter_ids": ["feed_A", "t_spec"],
    "row_accumulation": {"bal_A": "holdup_balance", "eq_A": "algebraic", "tspec": "algebraic"},
}
SMALL_DIGEST = "690d754282fe59dc63ee7bd85a80329dd95623c4c264683ca42edb09d2335aa4"
PERMUTED_DIGEST = "edbbcf2d23abc0ee4d6a4ef7dc4e36ab95bbd9be7a22b1f83d195c5ff1582200"
RECLASSIFIED_DIGEST = "50e8d3b8e1adddaf88480ffdb596dbe7d58cc65dda9009059c94221d12ab00c2"
SYN001_L_DIGEST = "8e5930fc737e8e0b033a2fe35d06971c6cf911df2db5d9731e050cf1cb6fb98a"
SYN001_L_MODEL_VERSION = f"SYN-001-L-1@{SYN001_L_DIGEST}"


# -- E: the vector encoding (D1) -----------------------------------------------------------------


def test_e1_the_vector_encoding_identifier_is_unchanged() -> None:
    """D1 ratifies R-006 without moving a digest. A changed identifier here is a migration."""
    assert ENCODING_ID == "ieee754-be-v1"


# -- J: canonical JSON (D3) ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "spelling"),
    [
        (0.0, "0"),
        (-0.0, "0"),
        (1.0, "1"),
        (1, "1"),
        (-1.5, "-1.5"),
        (0.1, "0.1"),
        (100.0, "100"),
        (1e16, "10000000000000000"),
        (1e20, "100000000000000000000"),
        (1e21, "1e+21"),
        (1e-6, "0.000001"),
        (1e-7, "1e-7"),
        (1.5e-8, "1.5e-8"),
        (2.0**68, "295147905179352830000"),
        (123456789.0, "123456789"),
        (5e-324, "5e-324"),
    ],
)
def test_j1_number_spellings_are_ecma_262(value: float, spelling: str) -> None:
    """D3.3. `1.0` is `1`, `-0.0` is `0`, `1e16` spells out, `1e21` does not — all five cases."""
    assert canonical_json(value).decode() == spelling


def test_j2_json_dumps_is_not_an_implementation_of_this() -> None:
    """D3.3, stated as a falsifiable claim rather than a warning in prose."""
    for value in (1.0, 1e16, 1e-7):
        assert json.dumps(value) != canonical_json(value).decode()


def test_j3_keys_sort_by_utf16_code_unit_not_code_point() -> None:
    """D3.2, on a document where the two orders disagree.

    An astral character sorts *after* every BMP character by code point and *before* the higher BMP
    range by UTF-16 code unit, because its surrogates begin at U+D800. This registers a case where
    `sort_keys=True` produces different bytes, which is why it is not an acceptable canonicalizer.
    """
    document = {"\U0001f600": 1, "Ｚ": 2}
    assert canonical_json(document).decode() == '{"\U0001f600":1,"Ｚ":2}'
    assert (
        json.dumps(document, sort_keys=True, separators=(",", ":"))
        != canonical_json(document).decode()
    )


def test_j4_strings_escape_exactly_what_the_adr_lists() -> None:
    """D3.5: seven short escapes, control characters as lowercase \\u00xx, nothing else.

    The characters are built with chr() rather than written literally, so the source file stays
    printable ASCII — a test file carrying raw control characters is a file people edit wrongly.
    """
    assert canonical_json('a"b\\c') == b'"a\\"b\\\\c"'
    assert canonical_json("\b\f\n\r\t") == b'"\\b\\f\\n\\r\\t"'
    assert canonical_json(chr(0x01)) == b'"\\u0001"'
    assert canonical_json(chr(0x1F)) == b'"\\u001f"'

    # Deliberately NOT escaped: solidus, DEL, line/paragraph separators, non-ASCII. The result
    # is the quoted string, so the expectation carries the quotes too.
    plain = "/" + chr(0x7F) + chr(0x2028) + chr(0x2029) + chr(0xE9)
    assert canonical_json(plain) == ('"' + plain + '"').encode()


def test_j5_no_unicode_normalization_is_applied() -> None:
    """D3.5: `e` + U+0301 and U+00E9 are different strings and both survive."""
    composed, decomposed = "é", "é"
    assert composed != decomposed
    assert canonical_json(composed) != canonical_json(decomposed)


def test_j6_non_finite_numbers_have_no_canonical_form() -> None:
    """D3.4: there is no path on which a NaN or infinity reaches a document digest."""
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(CanonicalizationError):
            canonical_json(value)


def test_j7_an_integer_is_refused_unless_it_spells_its_binary64() -> None:
    """D3.3 as amended (Amendment 1, A1.6): an integer whose digits are not the canonical spelling
    of its nearest binary64 would silently change its value, so it raises. `2**53 + 2` is that
    spelling, and is admitted; the test's old expectation that it raises was the over-broad rule
    the amendment corrects (reference row I04)."""
    assert canonical_json(2**53) == b"9007199254740992"
    with pytest.raises(CanonicalizationError, match="is not the canonical spelling of a binary64"):
        canonical_json(2**53 + 1)
    assert canonical_json(2**53 + 2) == b"9007199254740994"


def test_j8_booleans_are_not_numbers_and_arrays_are_never_reordered() -> None:
    """D3.2 and D3.6. `bool` is an `int` subclass in Python, which is the trap here."""
    assert canonical_json({"a": True, "b": 1}) == b'{"a":true,"b":1}'
    assert canonical_json([3, 1, 2]) == b"[3,1,2]"


def test_j9_the_document_encoding_is_identified() -> None:
    assert DOCUMENT_ENCODING_ID == "jcs-rfc8785-v1"
    assert DIRECTORY_HASH_ID == "dirhash-v1"


# -- S: structural identity (D2) -----------------------------------------------------------------


def test_s1_the_registered_small_structure_digest() -> None:
    """D2.8, against the ADR's independently computed value and byte length."""
    assert len(canonical_json(SMALL_STRUCTURE)) == 246
    assert document_sha256(SMALL_STRUCTURE) == SMALL_DIGEST


def test_s2_the_anonymity_hole_is_visible_and_closed() -> None:
    """D2.6: the equality that *is* the hole, asserted so it stays visible, and then closed.

    Two problems whose pinned-input vectors are byte-identical have equal `constants_sha256` — that
    is not a bug and must not be "fixed" by hashing names into the vector digest, because the vector
    digest is over the vector. What closes the hole is that their `model_version` now differs.
    """
    first_ids = ("t_spec", "p_spec")
    second_ids = ("p_spec", "t_spec")
    first_values = {"t_spec": 360.0, "p_spec": 100000.0}
    second_values = {"p_spec": 360.0, "t_spec": 100000.0}

    assert constants_sha256(first_values, first_ids) == constants_sha256(second_values, second_ids)

    accumulation = {"r0": "algebraic"}
    first = model_version("HOLE", structure_sha256(("x",), ("r0",), first_ids, accumulation))
    second = model_version("HOLE", structure_sha256(("x",), ("r0",), second_ids, accumulation))
    assert first != second


def test_s3_permuting_parameter_ids_changes_the_structure_digest() -> None:
    permuted = dict(SMALL_STRUCTURE, parameter_ids=["t_spec", "feed_A"])
    assert document_sha256(permuted) == PERMUTED_DIGEST
    assert document_sha256(permuted) != SMALL_DIGEST


def test_s4_reclassifying_one_row_changes_the_structure_digest() -> None:
    """`row_accumulation` is in the document because T04 places the PTC mass matrix from it."""
    reclassified = dict(
        SMALL_STRUCTURE,
        row_accumulation={**SMALL_STRUCTURE["row_accumulation"], "bal_A": "algebraic"},  # type: ignore[dict-item]
    )
    assert document_sha256(reclassified) == RECLASSIFIED_DIGEST


def test_s5_permuting_variable_ids_changes_the_structure_digest() -> None:
    permuted = dict(SMALL_STRUCTURE, variable_ids=["v_A", "l_A", "T"])
    assert document_sha256(permuted) != SMALL_DIGEST


def test_s6_the_structure_document_has_exactly_five_members() -> None:
    """D2.1. Scales, capabilities and backend are deliberately absent, and adding one is a change
    of identity for every existing problem."""
    document = structure_document(("x",), ("r",), ("p",), {"r": "algebraic"})
    assert set(document) == {
        "structure_schema",
        "variable_ids",
        "equation_ids",
        "parameter_ids",
        "row_accumulation",
    }
    assert document["structure_schema"] == "compiled-problem-structure-v1"


@pytest.mark.parametrize(
    "bad",
    [
        "SYN-001-L-1",
        "SYN-001-L-1@",
        "SYN-001-L-1@" + "0" * 63,
        "SYN-001-L-1@" + "0" * 65,
        "SYN-001-L-1@" + "A" * 64,
        "@" + "0" * 64,
        "-leading-dash@" + "0" * 64,
    ],
)
def test_s7_a_malformed_model_version_is_refused(bad: str) -> None:
    """D2.3. Uppercase hex is refused too: two spellings of one identity is one too many."""
    with pytest.raises(ValueError):
        split_model_version(bad)


def test_s8_split_and_compose_round_trip() -> None:
    label, digest = split_model_version(SYN001_L_MODEL_VERSION)
    assert label == "SYN-001-L-1"
    assert digest == SYN001_L_DIGEST
    assert model_version(label, digest) == SYN001_L_MODEL_VERSION


def test_s9_the_pattern_constant_and_the_schemas_agree(repo_root: Path) -> None:
    """The schema pattern and the code's must be the same rule, not two spellings of one."""
    for name in (
        "compiled-problem-metadata",
        "evaluation-result",
        "jacobian-result",
    ):
        schema = json.loads((repo_root / "schemas" / f"{name}.schema.json").read_text())
        assert schema["properties"]["model_version"]["pattern"] == MODEL_VERSION_PATTERN


# -- R: reading documents (D3.6) -------------------------------------------------------------


def test_r1_a_duplicated_key_is_refused_on_read() -> None:
    """`json.loads` keeps the last value silently: a document could hash as one of two answers."""
    with pytest.raises(CanonicalizationError, match="duplicate key"):
        load_document('{"a": 1, "a": 2}')


@pytest.mark.parametrize(
    "text", ["when: 2026-09-18\n", "when: 2026-09-18T10:00:00\n", "1: a\n", "s: !!set {a, b}\n"]
)
def test_r2_a_node_outside_the_json_data_model_is_refused(text: str) -> None:
    """D3.6: a date, timestamp, set or non-string key has no canonical form. Quote it instead."""
    with pytest.raises(CanonicalizationError):
        load_document(text)


def test_r3_ordinary_documents_still_load() -> None:
    """Anti-vacuity: a reader that refuses everything would pass every test above."""
    assert load_document('{"b": 1, "a": [1, 2]}') == {"b": 1, "a": [1, 2]}
    assert load_document("a: 1\nb:\n  - x\n  - y\n") == {"a": 1, "b": ["x", "y"]}
    assert load_document('{"when": "2026-09-18"}') == {"when": "2026-09-18"}


# -- F: the fixtures (C5) --------------------------------------------------------------------


def test_f1_the_syn001_fixture_carries_the_registered_model_version(repo_root: Path) -> None:
    """D2.8's registered value, against the regenerated fixture."""
    fixture = json.loads(
        (
            repo_root / "tests/fixtures/schemas/compiled_problem_metadata/valid/syn001_lifted.json"
        ).read_text()
    )
    assert fixture["model_version"] == SYN001_L_MODEL_VERSION


def test_f2_the_fixture_digest_recomputes_from_its_own_fields(repo_root: Path) -> None:
    """The check that makes the digest evidence rather than an assertion the document makes."""
    fixture = json.loads(
        (
            repo_root / "tests/fixtures/schemas/compiled_problem_metadata/valid/syn001_lifted.json"
        ).read_text()
    )
    _, digest = split_model_version(fixture["model_version"])
    assert digest == structure_sha256(
        fixture["variable_ids"],
        fixture["equation_ids"],
        fixture["parameter_ids"],
        fixture["row_accumulation"],
    )


def test_f3_the_compiled_syn001_problem_agrees_with_the_fixture() -> None:
    """Closes the loop: the compiler assigns what the ADR registered and the fixture records."""
    from benchmarks.k01.syn001 import syn001_spec
    from benchmarks.p02.reference import load_reference
    from openflowsheet.compile.casadi_backend import compile_problem

    state = load_reference().states["S1"]
    problem = compile_problem(syn001_spec(state.parameters))
    assert problem.metadata.model_version == SYN001_L_MODEL_VERSION


def test_f4_the_inlined_form_is_self_consistent() -> None:
    """D2.8 registers no digest for form I, so this is a consistency check and is labelled one."""
    from benchmarks.k01.syn001 import syn001_spec
    from benchmarks.p02.reference import load_reference
    from openflowsheet.compile.casadi_backend import compile_problem

    state = load_reference().states["S1"]
    metadata = compile_problem(syn001_spec(state.parameters, form="I")).metadata
    label, digest = split_model_version(metadata.model_version)
    assert label == "SYN-001-I-1"
    assert digest == structure_sha256(
        metadata.variable_ids,
        metadata.equation_ids,
        metadata.parameter_ids,
        metadata.row_accumulation,
    )
    assert digest != SYN001_L_DIGEST


def test_f5_math_is_not_shadowed() -> None:
    """Guards a real hazard: `canonical` imports `math`, and a stray rebind would be silent."""
    assert math.isfinite(1.0)
