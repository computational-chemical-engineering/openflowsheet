"""Canonical encoding for the identity hashes of the `CompiledProblem` boundary.

Two hashes identify a compiled evaluation, and this module is the single place either is computed
in production code:

* **`state_sha256`** covers exactly the dense `x` as passed, in `variable_ids` order, after
  signed-zero normalization, and nothing else (ADR 0008 D2).
* **`constants_sha256`** covers the complete pinned-input vector of a compiled-problem instance —
  physical constants, model parameters and specification values — in `parameter_ids` order
  (ADR 0008 D4.1).

They are the *same* operation over different named vectors, and are written that way on purpose:
`hash_named_doubles` is the primitive, and the two public names are its two uses. Drift between
them would be drift between what identifies a state and what identifies the problem it is a state
of, which is the failure ADR 0008 D2.4's pairing fields exist to make detectable.

## The encoding, and why it is not the one P02 used

The digest is SHA-256 over the **big-endian IEEE-754 binary64 bytes** of the ordered values, with
signed zero normalized. Eight bytes per value, no text.

K01 first promoted the P02 composition specification's §10.4 text encoding — `%.17g`, comma-joined
— because it was already fixed and had two independent implementations agreeing. The Fable review
of K01 argued against ratifying it, Frank agreed on 2026-09-18, and the reasons are worth keeping
where the next reader will find them:

* **It puts an implementation-defined formatter inside replay identity.** `%g` is C's, and its
  trailing-zero stripping, exponent-digit count and infinity and NaN spellings are not fixed across
  languages — Rust, JavaScript and Fortran have no `%g` at all. A replay bundle whose identity
  depends on how a particular C library prints a double is portable only by luck. The byte form is
  the value itself.
* **It is slow enough to matter.** The hash runs twice per Newton iteration; the text form measured
  47 ms at n = 1e5 against 1.1 ms for bytes. That is not the deciding argument — the release
  horizon's flowsheets are tens to low hundreds of variables, and ADR 0003 D2.2's own reasoning
  warns against extrapolating to scales not in view — but it points the same way.

The identity *semantics* are unchanged: both encodings are injective over finite doubles, both
normalize signed zero, both make order and length participate, and neither quantizes. So this
changed the digests and nothing else, at the cheapest possible moment — nothing is released, so
fixtures were regenerated rather than hashes migrated. That window closes at K04/K05, when replay
bundles start storing hashes.

`p02_10_4_text` below is kept, not for production use, but because the two independent
implementations of it — `spikes/p02/common/export.py` and `benchmarks/p02/judge.py`, the latter
written separately so a harness could not certify its own hash — are evidence about the P02
artifacts, and that evidence should not be discarded to make a refactor tidy.

**One difference worth stating plainly.** The text form printed every NaN as `nan`, so all NaN
payloads collided; the byte form distinguishes them. This is not load-bearing: a state containing a
NaN is `invalid_trial_state` and is never reported `ok`, so its identity is never compared against
anything. It is recorded here rather than discovered later.

## What the digest does *not* cover

The digest is of the **anonymous ordered vector of values**. The names in `order` choose *which*
values participate and in what sequence, but no name is hashed. So `constants_sha256` identifies a
pinned-input vector only in combination with a `model_version` that pins `parameter_ids`, and
`state_sha256` likewise with `variable_ids`. Nothing in this module can enforce that; it is an
obligation on whatever assigns `model_version`, and ADR 0002 must state it.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

import numpy as np
import numpy.typing as npt

#: Identifies the encoding these hashes are computed under, so a future change can tell digests
#: apart rather than silently comparing across schemes. `p02-10.4` was K01's first promotion and is
#: what every artifact under `spikes/p02/results/` was hashed with.
ENCODING_ID = "ieee754-be-v1"

#: The encoding the P02 composition specification §10.4 fixed, retained for comparison only.
LEGACY_ENCODING_ID = "p02-10.4"

_LEGACY_FORMAT = "%.17g"
_LEGACY_SEPARATOR = ","

#: Big-endian binary64. Big-endian so the bytes do not depend on the host's byte order, which would
#: make replay identity a property of the machine rather than of the numbers.
_DTYPE = np.dtype(">f8")


def normalize_zero(value: float) -> float:
    """Return `+0.0` for either signed zero, and `value` otherwise (ADR 0001 D1.5).

    `-0.0 == 0.0` is true in IEEE-754, so the two are the same state and must hash alike — but
    their bit patterns differ in the sign bit, so without this they would not.
    """
    return 0.0 if value == 0.0 else value


def encode_doubles(values: Iterable[float] | npt.NDArray[np.float64]) -> bytes:
    """The canonical bytes of a sequence of doubles: big-endian binary64, zeros normalized.

    Exposed because the bytes — not just the digest — are what a cross-implementation comparison
    and any future migration need to look at. A non-finite value is encoded as whatever IEEE-754
    says it is rather than rejected: the boundary may legitimately be handed an invalid trial state,
    and reporting that through `EvaluationStatus` is the evaluator's job, not the hash's.
    """
    if isinstance(values, np.ndarray):
        # The hot path: the boundary hashes a dense `x` twice per Newton iteration. `+ 0.0`
        # normalizes every signed zero elementwise — `-0.0 + 0.0` is `+0.0` in IEEE-754 — so the
        # whole encoding is two vectorized operations and no Python-level loop.
        array = np.asarray(values, dtype=np.float64) + 0.0
    else:
        array = np.fromiter((normalize_zero(float(value)) for value in values), dtype=np.float64)
    return array.astype(_DTYPE).tobytes()


def p02_10_4_text(values: Iterable[float]) -> str:
    """The P02 specification §10.4 text encoding. **Not production**; see the module docstring.

    Retained so the agreement with the two independent implementations that hashed the P02
    artifacts stays testable. Nothing in `openflowsheet` calls it.
    """
    return _LEGACY_SEPARATOR.join(_LEGACY_FORMAT % normalize_zero(float(value)) for value in values)


def legacy_p02_hash(values: Mapping[str, float] | Sequence[float], order: Sequence[str]) -> str:
    """The digest the P02 artifacts carry, under `LEGACY_ENCODING_ID`."""
    return hashlib.sha256(p02_10_4_text(_select(values, order)).encode("utf-8")).hexdigest()


def _select(values: Mapping[str, float] | Sequence[float], order: Sequence[str]) -> list[float]:
    """The ordered values `order` names, from either a mapping or an already-ordered sequence.

    Only the names in `order` participate. A mapping may hold more — a key outside `order` is
    ignored by construction, which is how ADR 0008 D2.2 excludes time, pseudo-time and every other
    non-state quantity from the state hash: not by filtering them out, but by never reading them.
    """
    if isinstance(values, Mapping):
        return [float(values[name]) for name in order]
    if len(values) != len(order):
        raise ValueError(
            f"dense vector of length {len(values)} does not match {len(order)} ordered names; "
            "a hash over a mismatched pair would identify a state that does not exist"
        )
    return [float(value) for value in values]


def hash_named_doubles(values: Mapping[str, float] | Sequence[float], order: Sequence[str]) -> str:
    """SHA-256 of the doubles `order` names, in that order, under the canonical encoding.

    `values` is either a mapping keyed by name, or a dense sequence already in `order`. The two
    forms exist because the boundary passes a dense `x` while manifests and fixtures carry
    mappings; they are required to agree, and `tests/test_canonical.py` asserts they do.
    """
    return hashlib.sha256(encode_doubles(_select(values, order))).hexdigest()


def state_sha256(
    x: Mapping[str, float] | npt.NDArray[np.float64] | Sequence[float],
    order: Sequence[str],
) -> str:
    """Hash of exactly the dense state `x`, in `order`, and nothing else (ADR 0008 D2).

    The parameter names are `x` and `order` because
    `tests/test_adr_0008_transient_readiness.py` H6 pins them: ADR 0008 D2.1 says the hash is a
    pure function of the state and its order, and a third parameter would be a third thing in scope.
    """
    if isinstance(x, np.ndarray):
        if x.shape != (len(order),):
            raise ValueError(
                f"dense vector of shape {x.shape} does not match {len(order)} ordered names; "
                "a hash over a mismatched pair would identify a state that does not exist"
            )
        return hashlib.sha256(encode_doubles(x)).hexdigest()
    return hash_named_doubles(x, order)


def constants_sha256(
    values: Mapping[str, float] | Sequence[float],
    parameter_ids: Sequence[str],
) -> str:
    """Hash of the complete pinned-input vector, in `parameter_ids` order (ADR 0008 D4.1).

    "Complete" is the operative word: physical constants, model parameters *and* specification
    values. Two instances compiled from the same equation structure with different fresh-feed
    values share a `model_version` and must differ here, because they are different problems.
    """
    return hash_named_doubles(values, parameter_ids)


# ================================================================================================
# Document identity (ADR 0002 D3): RFC 8785, the JSON Canonicalization Scheme.
#
# `json.dumps` is not an implementation of this, with any options, for two measured reasons:
# its `sort_keys` orders by code point while JCS orders by UTF-16 code unit (they differ on any
# key outside the Basic Multilingual Plane), and its number spelling is Python's, not ECMA-262's
# (`1.0` where JCS writes `1`, `1e+16` where JCS writes `10000000000000000`). Hence this.
# ================================================================================================

#: Names the document canonicalization these digests are computed under (ADR 0002 D3.1).
DOCUMENT_ENCODING_ID = "jcs-rfc8785-v1"

#: Names the directory-hash method and, critically, its ordering (ADR 0002 D5).
DIRECTORY_HASH_ID = "dirhash-v1"

#: Up to this every integer is its own binary64 and is spelled by its own digits. Beyond it an
#: integer is canonical only when its digits are the canonical spelling of its nearest binary64,
#: which is exactly one integer per binary64; any other is refused, never rounded (ADR 0002 D3.3,
#: Amendment 1). `integer_binary64` is the one implementation of that rule.
_MAX_EXACT_INTEGER = 2**53

#: From here on every binary64 is spelled with an exponent (D3.3 layouts (d) and (e)), so no
#: integer is the spelling of one. An integer this large is never converted, nor formatted.
_EXPONENT_FORM_INTEGER = 10**21

#: A code point with no UTF-8 form. RFC 8785 constrains its input to I-JSON (RFC 7493 §2.1), which
#: excludes surrogates from names and strings; `json.loads` joins a valid pair into one code point,
#: so every one a `str` holds is a lone surrogate (T07 design note §12.5, ruling round 4).
_SURROGATE = re.compile("[\ud800-\udfff]")

_ESCAPES = {
    '"': '\\"',
    "\\": "\\\\",
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


class CanonicalizationError(ValueError):
    """A value has no canonical JSON form (ADR 0002 D3.3, D3.4, D3.6)."""


def integer_binary64(n: int) -> float | None:
    """The binary64 an integer is the canonical spelling of, or `None` when it spells none
    (ADR 0002 D3.3, Amendment 1).

    `n` is canonical exactly when its decimal digits are the canonical spelling of the binary64
    nearest to it: every `n` with `|n| ≤ 2⁵³`; exactly one per binary64 for `2⁵³ < |n| < 10²¹`,
    the one D3.3 spells (so `2⁵³ + 2` and `592612204108959000`, but not `2⁵³ + 1` nor `2⁵⁵`,
    which is exact but spelled `36028797018963970`); none from `10²¹`. The verdict is on the
    digits alone, so an in-process `int` and every JSON or YAML parser's `int` agree. This is the
    one implementation: `_canonical_number` and `units.read_number` both ask it.
    """
    if isinstance(n, bool):  # bool is an int subclass; it is not an integer here (D3.6)
        raise TypeError("a boolean is not an integer")
    if abs(n) <= _MAX_EXACT_INTEGER:
        return float(n)
    if abs(n) >= _EXPONENT_FORM_INTEGER:
        return None  # not `float(n)`: it overflows from about 1.8e308
    value = float(n)
    return value if _canonical_number(value) == str(n) else None


def _canonical_number(value: float | int) -> str:
    """The ECMA-262 `Number::toString` spelling of a binary64 (ADR 0002 D3.3).

    The *digits* come from `repr`, which is the shortest round-trip decimal and closest-on-ties —
    exactly what ECMA-262 asks for. Only the **layout** differs between the two, and the layout is
    the five cases below. Doing it this way keeps the delicate part (digit selection) in CPython's
    tested implementation rather than in this file.
    """
    if isinstance(value, bool):  # bool is an int subclass; JCS keeps them distinct (D3.6)
        raise CanonicalizationError("a boolean is not a number")
    if isinstance(value, int):
        reading = integer_binary64(value)
        if reading is None:
            if abs(value) >= _EXPONENT_FORM_INTEGER:
                # Never formatted: CPython refuses `str` of an `int` of more than 4300 digits.
                raise CanonicalizationError(
                    "an integer of magnitude 10^21 or more is not the canonical spelling of a "
                    "binary64: every binary64 there is spelled with an exponent (ADR 0002 D3.3)"
                )
            raise CanonicalizationError(
                f"integer {value} is not the canonical spelling of a binary64: its nearest "
                f"binary64 is spelled {_canonical_number(float(value))}, so canonicalizing it "
                "would silently change its value (ADR 0002 D3.3)"
            )
        value = reading
    if not math.isfinite(value):
        raise CanonicalizationError(
            f"{value!r} has no canonical JSON spelling; a non-finite number never reaches a "
            "document digest (ADR 0002 D3.4, ADR 0001 D1.5)"
        )
    if value == 0.0:
        return "0"  # covers -0.0, which is the canonical-form half of ADR 0001 D1.5

    sign = "-" if value < 0.0 else ""
    text = repr(abs(value))

    mantissa, _, exponent = text.partition("e")
    exponent_value = int(exponent) if exponent else 0
    integral, _, fractional = mantissa.partition(".")
    digits = integral + fractional
    n = len(integral) + exponent_value

    stripped = digits.lstrip("0")
    n -= len(digits) - len(stripped)
    digits = stripped.rstrip("0") or "0"
    k = len(digits)

    if k <= n <= 21:
        return sign + digits + "0" * (n - k)
    if 0 < n <= 21:
        return sign + digits[:n] + "." + digits[n:]
    if -6 < n <= 0:
        return sign + "0." + "0" * (-n) + digits
    exponent_text = f"e{'+' if n - 1 >= 0 else '-'}{abs(n - 1)}"
    if k == 1:
        return sign + digits + exponent_text
    return sign + digits[0] + "." + digits[1:] + exponent_text


def _canonical_string(value: str) -> str:
    """UTF-8 of the code points, escaping exactly what ADR 0002 D3.5 lists and nothing else.

    Not escaped, deliberately: `/`, U+007F, U+2028 and U+2029, and every non-ASCII character. No
    Unicode normalization is applied, so `e` + U+0301 and U+00E9 stay different strings.
    """
    out = ['"']
    for character in value:
        if character in _ESCAPES:
            out.append(_ESCAPES[character])
        elif character < " ":
            out.append(f"\\u{ord(character):04x}")
        else:
            out.append(character)
    out.append('"')
    return "".join(out)


def _canonical(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return _canonical_string(value)
    if isinstance(value, int | float):
        return _canonical_number(value)
    if isinstance(value, list | tuple):
        # Arrays are never reordered: array order is semantic unless a schema says otherwise, and
        # none does — `component_set.components` order *is* the component order (ADR 0001 D2.1).
        return "[" + ",".join(_canonical(item) for item in value) + "]"
    if isinstance(value, Mapping):
        keys = list(value)
        non_string = [key for key in keys if not isinstance(key, str)]
        if non_string:
            raise CanonicalizationError(f"object keys must be strings; got {non_string!r}")
        if len(set(keys)) != len(keys):
            raise CanonicalizationError("object has duplicate keys")
        # RFC 8785 §3.2.3 sorts by UTF-16 code units, not code points. The two orders differ only
        # when a key contains a character outside the BMP — and they *do* differ there, which is
        # why `sort_keys=True` is not an implementation of this rule.
        ordered = sorted(keys, key=lambda key: key.encode("utf-16-be"))
        members = (f"{_canonical_string(key)}:{_canonical(value[key])}" for key in ordered)
        return "{" + ",".join(members) + "}"
    raise CanonicalizationError(
        f"{type(value).__name__} is outside the JSON data model (ADR 0002 D3.6); a date, "
        "timestamp, set or binary node is written as a string before canonicalization"
    )


def canonical_json(document: object) -> bytes:
    """The canonical JSON bytes of a document (ADR 0002 D3): UTF-8, no BOM, no whitespace.

    A string or key holding a lone surrogate has no UTF-8 form and is refused typed
    (`CanonicalizationError`), as the other nodes without a canonical form are.
    """
    try:
        return _canonical(document).encode("utf-8")
    except UnicodeEncodeError as error:  # the key sort (UTF-16) or the final encode
        raise CanonicalizationError(
            f"a string holds the lone surrogate U+{ord(error.object[error.start]):04X}, which has "
            "no UTF-8 form (ADR 0002 D3 through RFC 8785 and I-JSON)"
        ) from None


def document_sha256(document: object) -> str:
    """SHA-256, lowercase hex, of a document's canonical JSON bytes."""
    return hashlib.sha256(canonical_json(document)).hexdigest()


def first_noncanonical(document: object) -> str | None:
    """The RFC 6901 pointer of the first node, in document order, that has no canonical JSON
    form, or `None` when there is none (R-088 Q29, T07 design note §12.5).

    The offending nodes are exactly the ones `canonical_json` refuses, so `None` here and a
    `canonical_json` that does not raise are the same statement: a non-finite float, an integer
    that is not the canonical spelling of a binary64 (`integer_binary64`; ADR 0002 D3.3,
    Amendment 1, D3.4), a non-string or repeated object key, a node outside the JSON data model
    (D3.6), and a string value or key holding a lone surrogate (U+D800–U+DFFF, which has no UTF-8
    form; ruling round 4). A float is judged as `_canonical_number` judges it — every finite one
    is canonical, an integral one beyond 2⁵³ included. The number rules are
    `_canonical_number`'s own, called here, so the two cannot drift.

    Callers that must refuse a non-canonical input typed — `validate()` and both revision
    binders — ask this first, rather than letting a digest deep inside raise an untyped
    `CanonicalizationError` from a field nothing reads. "Document order" is a mapping's own
    iteration order (a parsed document's textual order), not the canonical sorted order. A bad
    key names its member, `<object>/<str(key)>`, so the pointer is never empty below the root;
    each lone surrogate of a key is U+FFFD in the pointer, so the pointer itself is canonical.
    """
    return _first_noncanonical(document, "")


def _first_noncanonical(value: object, pointer: str) -> str | None:
    # The same case order as `_canonical`.
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        return pointer if _SURROGATE.search(value) else None
    if isinstance(value, int | float):
        try:
            _canonical_number(value)
        except CanonicalizationError:
            return pointer
        return None
    if isinstance(value, list | tuple):
        for index, item in enumerate(value):
            found = _first_noncanonical(item, f"{pointer}/{index}")
            if found is not None:
                return found
        return None
    if isinstance(value, Mapping):
        seen: set[str] = set()
        for key in value:
            # RFC 6901 §3: `~` is written `~0` and `/` is written `~1`.
            member = f"{pointer}/{str(key).replace('~', '~0').replace('/', '~1')}"
            if not isinstance(key, str) or key in seen or _SURROGATE.search(key):
                # Each lone surrogate shows as U+FFFD, so the pointer can itself be written.
                return _SURROGATE.sub("\ufffd", member)
            seen.add(key)
            found = _first_noncanonical(value[key], member)
            if found is not None:
                return found
        return None
    return pointer


# ================================================================================================
# Structural identity (ADR 0002 D2): `model_version` is `<label>@<structure_sha256>`.
#
# The hole this closes: the vector digests above are over the *anonymous ordered vector of values*
# — no name is hashed — so two problems whose pinned inputs happen to have equal value vectors have
# equal `constants_sha256`. Identity rests on the pair (`model_version`, `constants_sha256`), and
# before this the first half was a free string that nothing pinned to anything.
# ================================================================================================

#: The structure-document schema tag. `v2` will add a `sources` member carrying the content hashes
#: of the contributing manifests, so that expression identity stops resting on the label
#: (ADR 0002 D2.7); until then the label carries it and the ADR says so.
STRUCTURE_SCHEMA = "compiled-problem-structure-v1"

#: `^label@64 hex$`. The label names the function *family*; the suffix is the structure digest.
MODEL_VERSION_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}@[0-9a-f]{64}$"

_MODEL_VERSION = re.compile(MODEL_VERSION_PATTERN)


def structure_document(
    variable_ids: Sequence[str],
    equation_ids: Sequence[str],
    parameter_ids: Sequence[str],
    row_accumulation: Mapping[str, str],
) -> dict[str, object]:
    """The five-member structure document of ADR 0002 D2.1, and no other members.

    Scales, capabilities, backend and backend version are deliberately absent: scales are numerical
    policy, and two problems compiled by different backends from the same structure *describe the
    same function* and should share a structure digest, being told apart by the `backend` fields.
    """
    return {
        "structure_schema": STRUCTURE_SCHEMA,
        "variable_ids": list(variable_ids),
        "equation_ids": list(equation_ids),
        "parameter_ids": list(parameter_ids),
        "row_accumulation": dict(row_accumulation),
    }


def structure_sha256(
    variable_ids: Sequence[str],
    equation_ids: Sequence[str],
    parameter_ids: Sequence[str],
    row_accumulation: Mapping[str, str],
) -> str:
    """SHA-256 of the canonical JSON of the structure document (ADR 0002 D2.2)."""
    return document_sha256(
        structure_document(variable_ids, equation_ids, parameter_ids, row_accumulation)
    )


def model_version(label: str, structure_digest: str) -> str:
    """Compose `<label>@<structure_sha256>`, refusing a label that cannot appear in one.

    The compiler calls this; a `ProblemSpec` supplies only the label and is never trusted to supply
    the digest (ADR 0002 D2.5).
    """
    composed = f"{label}@{structure_digest}"
    if not _MODEL_VERSION.match(composed):
        raise ValueError(
            f"{composed!r} is not a well-formed model_version. The label must match "
            "[A-Za-z0-9][A-Za-z0-9._-]{0,63} and the digest must be 64 lowercase hex characters "
            "(ADR 0002 D2.3)."
        )
    return composed


def split_model_version(value: str) -> tuple[str, str]:
    """Split `<label>@<structure_sha256>` into its two parts, refusing a malformed one."""
    if not _MODEL_VERSION.match(value):
        raise ValueError(f"{value!r} is not a well-formed model_version (ADR 0002 D2.3)")
    label, _, digest = value.rpartition("@")
    return label, digest


def directory_hash(root: Path) -> str:
    """SHA-256 over every file under `root`, as `path\\0sha256\\n` (ADR 0002 D5.2).

    **The ordering is the UTF-8 byte order of the relative POSIX path**, which is not what sorting
    `Path` objects gives: `Path` compares component-wise, so it orders `a/b, a/c, a-c, a.c, ab`
    where byte order gives `a-c, a.c, a/b, a/c, ab` (measured). Both are deterministic, but only one
    is stated, and a hash whose ordering depends on a library's comparison rules is a hash whose
    value depends on the library.
    """
    digest = hashlib.sha256()
    entries = sorted(
        (str(path.relative_to(root).as_posix()), path) for path in root.rglob("*") if path.is_file()
    )
    for relative, path in sorted(entries, key=lambda item: item[0].encode("utf-8")):
        digest.update(relative.encode("utf-8") + b"\0")
        digest.update(file_sha256(path).encode("utf-8") + b"\n")
    return digest.hexdigest()


def file_sha256(path: Path) -> str:
    """SHA-256 of a file's exact bytes as stored (ADR 0002 D5.1)."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_document(text: str, *, source: str = "<document>") -> object:
    """Parse JSON or YAML into the JSON data model, refusing what ADR 0002 D3.6 refuses.

    Two things a default parser does silently and this does not. `json.loads` keeps the **last** of
    duplicated keys, so a document can carry two contradictory values for one field and hash as
    whichever the parser happened to keep. And `yaml.safe_load` returns dates, timestamps, sets and
    non-string keys, none of which is in the JSON data model or has a canonical form; a timestamp
    belongs in a document as a quoted string, which every P01 fixture already does.
    """
    import yaml

    def _no_duplicate_keys(pairs: Sequence[tuple[str, object]]) -> dict[str, object]:
        seen: set[str] = set()
        for key, _ in pairs:
            if key in seen:
                raise CanonicalizationError(
                    f"{source}: duplicate key {key!r}. A parser that keeps the last value lets a "
                    "document carry two answers and hash as one (ADR 0002 D3.6)."
                )
            seen.add(key)
        return dict(pairs)

    stripped = text.lstrip()
    if stripped.startswith(("{", "[")):
        document = json.loads(text, object_pairs_hook=_no_duplicate_keys)
    else:
        document = yaml.safe_load(text)
    _check_json_model(document, source, "$")
    return document


def _check_json_model(node: object, source: str, path: str) -> None:
    """Every node must be `null`, bool, number, string, array or object with string keys."""
    if node is None or isinstance(node, bool | int | float | str):
        return
    if isinstance(node, list | tuple):
        for index, item in enumerate(node):
            _check_json_model(item, source, f"{path}[{index}]")
        return
    if isinstance(node, Mapping):
        for key, value in node.items():
            if not isinstance(key, str):
                raise CanonicalizationError(
                    f"{source}: non-string key {key!r} at {path} is outside the JSON data model "
                    "(ADR 0002 D3.6)"
                )
            _check_json_model(value, source, f"{path}.{key}")
        return
    raise CanonicalizationError(
        f"{source}: {type(node).__name__} at {path} is outside the JSON data model. A date, "
        "timestamp, set or binary node is written as a quoted string (ADR 0002 D3.6)."
    )
