"""T07 W2d: non-canonical numbers are refused typed (R-088 Q29; gate G10).

Design note `docs/design/T07-jobs-and-bindings.md` §12.5 and §16 G10. `canonical.first_noncanonical`
names the first node, in document order, with no canonical JSON form; `validate()` turns it into
`SCHEMA-01 FAIL` (`document_not_canonical(<pointer>)`, status `INVALID`), and both revision binders
into `Unbound("unsupported", "document_not_canonical(<pointer>)")` at entry. The legacy binding's
non-number values — a string, a bool or null where a number is read — give a typed `Unbound`,
never an exception and never a number coerced out of them.

G10's vector set is every numeric leaf of five registered revisions × {NaN, +∞, −∞, 2⁵³+1,
−(2⁵³+1), `"x"`, `true`, `null`} and, since ruling round 4 (W5a-Q1, R4-G2), the three strings
holding lone surrogates `"\\ud800"`, `"a\\udfffb"` and `"\\ud83d" + "\\ude00"` (two code points),
which are non-canonical. The expectations are stated here, from the note, not read back from the
code under test. `dispatch` (transport 422) and `commit_change` (`rejected`) are tested in
`test_t07_w5a_operations.py` and `test_t07_w5d_surrogates.py`.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Iterator, Mapping
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml

from openflowsheet.application.binding import Binding, Unbound, bind_revision_or_reason
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.application.validation import validate
from openflowsheet.canonical import CanonicalizationError, canonical_json, first_noncanonical
from openflowsheet.orchestrator.execution import declaration_identity

#: Five registered revisions of different shapes: the nominal (both binders bind), a `role: free`
#: guess (only the legacy binder binds), a non-SI unit variant (conversions on both paths), a
#: revision-path network (the legacy binder is `incomplete`) and a T05 unit-library case (the
#: legacy binder is `unsupported`).
REVISIONS = (
    "benchmarks/syn001/cases/SYN-001-nominal.yaml",
    "benchmarks/syn001/cases/SYN-001-A02-360-vapor-guess.yaml",
    "benchmarks/t06/cases/SYN-001-T06-STA03-degC.yaml",
    "benchmarks/t06/cases/SYN-001-T06-NET02.yaml",
    "benchmarks/t05/cases/SYN-001-UL-C1.yaml",
)
CASE_DIRECTORIES = ("benchmarks/syn001/cases", "benchmarks/t05/cases", "benchmarks/t06/cases")

#: The numbers ADR 0002 D3.3/D3.4 give no canonical form.
NONCANONICAL: tuple[float | int, ...] = (math.nan, math.inf, -math.inf, 2**53 + 1, -(2**53 + 1))
#: The values that are canonical JSON but not numbers.
NON_NUMBERS: tuple[object, ...] = ("x", True, None)
#: Ruling round 4 (W5a-Q1): strings holding lone surrogates, which have no UTF-8 form (RFC 8785
#: through I-JSON). The last is a high and a low surrogate as two code points: no `str` that
#: `json.loads` returns holds such a pair, and it is refused like the others.
SURROGATES: tuple[str, ...] = ("\ud800", "a\udfffb", "\ud83d" + "\ude00")


def _pointer(path: tuple[str | int, ...]) -> str:
    """RFC 6901, written out independently of the implementation."""
    return "".join("/" + str(token).replace("~", "~0").replace("/", "~1") for token in path)


def _numeric_leaves(node: object, path: tuple[str | int, ...] = ()) -> Iterator[tuple[Any, ...]]:
    if isinstance(node, bool):
        return
    if isinstance(node, int | float):
        yield path
    elif isinstance(node, Mapping):
        for key, value in node.items():
            yield from _numeric_leaves(value, (*path, key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _numeric_leaves(value, (*path, index))


def _with(document: Any, path: tuple[Any, ...], value: object) -> Any:
    mutated = copy.deepcopy(document)
    node = mutated
    for token in path[:-1]:
        node = node[token]
    node[path[-1]] = value
    return mutated


@cache
def _revision(name: str) -> Any:
    return load_yaml(REPO_ROOT / name)


def _problem(binding: Binding | RevisionBinding) -> tuple[Any, ...]:
    """What a binding binds: the declaration's identity (structure and every pinned input), the
    guesses and the unit conversions. A leaf nothing reads cannot move any of it."""
    if isinstance(binding, Binding):
        return (
            declaration_identity(binding.spec),
            dict(binding.guesses),
            binding.missing_guesses,
            binding.input_mapping,
        )
    return (declaration_identity(binding.spec), binding.input_mapping)


# ------------------------------------------------------------------------------------------------
# first_noncanonical itself
# ------------------------------------------------------------------------------------------------


class _RepeatedKeys(Mapping[str, int]):
    """A mapping that yields one key twice: no `dict` can, but `canonical_json` guards it."""

    def __getitem__(self, key: str) -> int:
        return 1

    def __iter__(self) -> Iterator[str]:
        return iter(("a", "b", "a"))

    def __len__(self) -> int:
        return 3


@pytest.mark.parametrize(
    ("document", "pointer"),
    [
        ({"a": 1, "b": [0.5, -0.0, 2**53, -(2**53), 2.0**60, 1e308, True, None, "s"]}, None),
        ({}, None),
        ([], None),
        (math.nan, ""),
        ({"a": [1, {"b~/c": math.inf}]}, "/a/1/b~0~1c"),
        # Document order is the mapping's own order, not the canonical (sorted) one.
        ({"z": -math.inf, "a": math.nan}, "/z"),
        ({"n": 2**53 + 1}, "/n"),
        ({"n": -(2**53 + 1)}, "/n"),
        ({"t": (1, 2, math.nan)}, "/t/2"),
        ({"a": 1, 2: "x"}, "/2"),
        ({"s": {1, 2}}, "/s"),
        ({"d": Decimal("1")}, "/d"),
        ({"b": b"\x00"}, "/b"),
        (_RepeatedKeys(), "/a"),
        # Ruling round 4: a lone surrogate in a value names the value, in a key its member,
        # with U+FFFD for each surrogate; a surrogate is refused before a later number.
        ({"a": ["ok", "a\udfffb"]}, "/a/1"),
        ({"a": {"\ud83d" + "\ude00~/": 1}}, "/a/\ufffd\ufffd~0~1"),
        ({"s": "\ud800", "n": math.nan}, "/s"),
        ({"\ud800": math.nan}, "/\ufffd"),
        ({"a": "\U0001f600"}, None),
    ],
    ids=lambda value: ascii(value)[:40],
)
def test_first_noncanonical_names_the_first_offending_node(
    document: object, pointer: str | None
) -> None:
    assert first_noncanonical(document) == pointer


@pytest.mark.parametrize(
    "document",
    [
        {"a": 1.5},
        {"a": 2**53},
        {"a": 2.0**70},
        {"a": [math.nan]},
        {"a": 2**53 + 1},
        {1: "a"},
        {"a": {1}},
        _RepeatedKeys(),
        *({"a": value} for value in SURROGATES),
        *({"a": {value: 1}} for value in SURROGATES),
        *({value: 1, "b": 2} for value in SURROGATES),
        {"a": "\U0001f600", "\U0001f600": 1},
    ],
    ids=ascii,
)
def test_first_noncanonical_agrees_with_canonical_json(document: object) -> None:
    """`None` exactly when `canonical_json` succeeds: the two are one rule. The refusal is typed
    (`CanonicalizationError`), never an untyped `UnicodeEncodeError` (ruling round 4)."""
    try:
        canonical_json(document)
    except CanonicalizationError:
        assert first_noncanonical(document) is not None
    else:
        assert first_noncanonical(document) is None


def test_every_registered_revision_is_canonical() -> None:
    """No registered revision enters the new branch, so none of their reports can move."""
    paths = [path for d in CASE_DIRECTORIES for path in sorted((REPO_ROOT / d).glob("*.yaml"))]
    assert len(paths) > 40
    assert [path.name for path in paths if first_noncanonical(load_yaml(path)) is not None] == []


# ------------------------------------------------------------------------------------------------
# G10
# ------------------------------------------------------------------------------------------------


def _cases() -> list[Any]:
    return [
        pytest.param(name, value, noncanonical, id=f"{Path(name).stem}-{value!r}")
        for name in REVISIONS
        for values, noncanonical in (
            (NONCANONICAL, True),
            (NON_NUMBERS, False),
            (SURROGATES, True),
        )
        for value in values
    ]


@pytest.mark.parametrize(("name", "value", "noncanonical"), _cases())
def test_g10_every_numeric_leaf(name: str, value: object, noncanonical: bool) -> None:
    document = _revision(name)
    leaves = list(_numeric_leaves(document))
    assert len(leaves) > 40, name
    base_bindings = (
        bind_revision_or_reason(copy.deepcopy(document)),
        bind_revision_flowsheet(copy.deepcopy(document)),
    )

    failures: list[str] = []
    for path in leaves:
        pointer = _pointer(path)
        mutated = _with(document, path, value)
        try:
            report = validate(copy.deepcopy(mutated))
            bindings = (
                bind_revision_or_reason(copy.deepcopy(mutated)),
                bind_revision_flowsheet(copy.deepcopy(mutated)),
            )
        except Exception as error:  # noqa: BLE001 - "0 untyped exceptions" is the assertion
            failures.append(f"{pointer}: raised {type(error).__name__}: {error}")
            continue

        if noncanonical:
            expected = f"document_not_canonical({pointer})"
            (check,) = report.checks
            if (report.status, check.id, check.result, check.message, check.implicated_objects) != (
                "INVALID",
                "SCHEMA-01",
                "FAIL",
                expected,
                (pointer,),
            ):
                failures.append(f"{pointer}: validate gave {report.status} {report.checks}")
            for binding in bindings:
                if binding != Unbound("unsupported", expected):
                    failures.append(f"{pointer}: a binder gave {binding!r:.200}")
            continue

        # A non-number is canonical JSON: validate reports on it like any other document, and
        # its report is itself canonical (it can be hashed and served).
        if first_noncanonical(report.as_document()) is not None:
            failures.append(f"{pointer}: the validation report is not canonical")
        for binding, base in zip(bindings, base_bindings, strict=True):
            if isinstance(binding, Unbound):
                continue
            # It still binds only where the binder does not read the leaf: the same problem.
            if not isinstance(base, Binding | RevisionBinding) or _problem(binding) != _problem(
                base
            ):
                failures.append(f"{pointer}: bound a different problem from {value!r}")
        # A specification's `value` is read by both binders, and refused by both with the same
        # code; before T07 the legacy binding `float()`-ed it (T06 hand-off, R-088). A revision
        # the legacy binder refuses before reading any value keeps that refusal.
        if path[0] == "specifications" and path[2:] == ("value",):
            spec_id = document["specifications"][path[1]]["id"]
            code = f"specification_value_unreadable({spec_id})"
            legacy, revision = bindings
            if legacy not in (Unbound("unsupported", code, (spec_id,)), base_bindings[0]):
                failures.append(f"{pointer}: legacy binder gave {legacy!r:.200}")
            if not isinstance(revision, Unbound):
                failures.append(f"{pointer}: revision binder bound")

    assert failures == []


def test_a_numeric_string_is_not_a_number() -> None:
    """`"300"` was read as 300.0 by `float()`; it is refused like any other string."""
    document = copy.deepcopy(_revision(REVISIONS[0]))
    spec = document["specifications"][0]
    spec["value"] = str(spec["value"])
    assert bind_revision_or_reason(document) == Unbound(
        "unsupported", f"specification_value_unreadable({spec['id']})", (spec["id"],)
    )


def test_an_absent_value_is_still_a_missing_guess() -> None:
    """Only a *present* non-number is refused: a `role: free` specification without a `value`
    binds with its guess missing, as T02 §7.5 registers (SYN-001-A02-360-no-guess)."""
    document = _revision("benchmarks/syn001/cases/SYN-001-A02-360-no-guess.yaml")
    binding = bind_revision_or_reason(copy.deepcopy(document))
    assert isinstance(binding, Binding)
    assert binding.missing_guesses
