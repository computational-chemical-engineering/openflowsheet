"""T06 W25 (review S5): an integer without a binary64 reading is refused, typed (spec A100,
§8.5 (A5)).

ADR 0016 V0 reads a number as "the binary64 value as read, finite (else refused, reason
`value`)", and ADR 0002 D3.3 gives an integer with `|n| > 2⁵³` no binary64 reading at all. Every
number a reader takes from a specification's `value` or a parameter Quantity's `value`, `bounds`
or `nominal` goes through one function, `units.read_number`, which reads such an integer as the
infinity of its sign — so on every path and field it gets exactly the result that infinity gets:
`specification_value_unsupported(<id>)` or `parameter_quantity_invalid(<instance>.<name>)`, from
both bindings as `Unbound("unsupported", …)` and from `validate()` as `DIM-01` `FAIL`. Before W25,
`10⁴⁰⁰` raised `OverflowError` and `2⁵³ + 1` raised `CanonicalizationError` (both bindings, the
legacy `validate()`) or passed `DIM-01` (revision `validate()`). An integer with `|n| ≤ 2⁵³` is
read exactly, as before: the pair `2⁵³` / `2⁵³ + 1` pins the bound.

**T07 §12.5 (R-088 Q29).** Neither such an integer nor an infinity has a canonical JSON form, so
`validate()` and both bindings now refuse either at entry, naming its node: `SCHEMA-01` `FAIL` and
`Unbound("unsupported", "document_not_canonical(<pointer>)")`, before a reader runs. A100 (a)'s
equivalence — the integer gets exactly its infinity's result — is what this file still asserts;
the field codes above are that result only where a reader is reached (`read_number`, below).
Superseded pending the design lane's ruling (T07 W2d).
"""

from __future__ import annotations

import copy
import math
from collections.abc import Callable
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml

from openflowsheet.application.binding import Unbound, bind_revision_or_reason
from openflowsheet.application.revision_binding import bind_revision_flowsheet
from openflowsheet.application.validation import ValidationReport, validate
from openflowsheet.units import read_number

#: A100's two documents, the instance whose `pressure_drop` Quantity carries the parameter
#: fields, and the binding that reads each.
DOCUMENTS: dict[str, tuple[str, str, Callable[[Any], Any]]] = {
    "legacy": ("benchmarks/syn001/cases/SYN-001-nominal.yaml", "mixer", bind_revision_or_reason),
    "revision": ("benchmarks/t05/cases/SYN-001-UL-C2.yaml", "U-RX", bind_revision_flowsheet),
}
FIELDS = (
    "specification.value",
    "pressure_drop.value",
    "pressure_drop.bounds.upper",
    "pressure_drop.nominal",
)
READERS = ("bind", "validate")

BEYOND = 2**53 + 1
#: A100 (a): each integer, and the infinity whose result it must get.
UNREADABLE = {
    "2^53+1": (BEYOND, math.inf),
    "-(2^53+1)": (-BEYOND, -math.inf),
    "10^400": (10**400, math.inf),
    "-10^400": (-(10**400), -math.inf),
}


def _document(which: str, field: str, value: Any) -> tuple[dict[str, Any], str]:
    """A100's document with `value` written into `field`, and the code a refusal of a
    non-canonical number there names (T07 §12.5: the node's RFC 6901 pointer)."""
    path, instance_id, _ = DOCUMENTS[which]
    document: dict[str, Any] = copy.deepcopy(load_yaml(REPO_ROOT / path))
    if field == "specification.value":
        (index,) = [
            k
            for k, s in enumerate(document["specifications"])
            if s.get("role") == "fixed" and s["target"].get("path") == "state.T"
        ][:1]
        document["specifications"][index]["value"] = value
        return document, f"document_not_canonical(/specifications/{index}/value)"
    (index,) = [k for k, i in enumerate(document["instances"]) if i["id"] == instance_id]
    quantity = document["instances"][index]["parameters"]["pressure_drop"]
    pointer = f"/instances/{index}/parameters/pressure_drop"
    if field == "pressure_drop.value":
        quantity["value"] = value
        pointer += "/value"
    elif field == "pressure_drop.bounds.upper":
        quantity["bounds"] = {**(quantity.get("bounds") or {}), "upper": value}
        pointer += "/bounds/upper"
    else:
        quantity["nominal"] = value
        pointer += "/nominal"
    return document, f"document_not_canonical({pointer})"


def _result(which: str, reader: str, document: dict[str, Any]) -> tuple[Any, ...]:
    """What a reader returns, projected on what A100 compares; an exception is a result too, so
    that a crash fails the comparison rather than the harness."""
    try:
        result = DOCUMENTS[which][2](document) if reader == "bind" else validate(document)
    except Exception as error:  # A100: "no exception" — recorded, and compared
        return ("raised", type(error).__name__, str(error))
    if isinstance(result, Unbound):
        return ("Unbound", result.kind, result.detail, result.implicated)
    if isinstance(result, ValidationReport):
        # `DIM-01` where the dimensions stage runs; a non-canonical document ends at `SCHEMA-01`
        # (T07 §12.5).
        found = {check.id: check for check in result.checks}
        check = found.get("DIM-01", found["SCHEMA-01"])
        return (
            "ValidationReport",
            result.status,
            check.result,
            check.message,
            check.implicated_objects,
        )
    return ("bound", type(result).__name__)


@pytest.mark.parametrize("reader", READERS)
@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("which", sorted(DOCUMENTS))
@pytest.mark.parametrize("label", sorted(UNREADABLE))
def test_a100_a_an_integer_beyond_2_53_gets_its_infinitys_result(
    label: str, which: str, field: str, reader: str
) -> None:
    integer, infinity = UNREADABLE[label]
    document, code = _document(which, field, infinity)
    expected = _result(which, reader, document)
    # The infinity itself is refused, typed, naming its node (T07 §12.5).
    if reader == "bind":
        assert expected[:3] == ("Unbound", "unsupported", code), expected
    else:
        assert expected[1:3] == ("INVALID", "FAIL") and code in expected[3], expected
    assert _result(which, reader, _document(which, field, integer)[0]) == expected


@pytest.mark.parametrize("reader", READERS)
@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("which", sorted(DOCUMENTS))
def test_a100_b_2_53_is_read_as_the_float_2_53(which: str, field: str, reader: str) -> None:
    as_float = _result(which, reader, _document(which, field, 2.0**53)[0])
    assert as_float[0] != "raised", as_float
    assert _result(which, reader, _document(which, field, 2**53)[0]) == as_float


def test_read_number_is_the_one_reading() -> None:
    """The function's own contract: a bool is not a number; `|n| ≤ 2⁵³` exactly; beyond it the
    infinity of its sign; a float as is (V0 judges it)."""
    assert read_number(True) is None and read_number("1") is None and read_number(None) is None
    assert read_number(2**53) == 2.0**53 and read_number(-(2**53)) == -(2.0**53)
    assert read_number(BEYOND) == math.inf and read_number(-BEYOND) == -math.inf
    assert read_number(10**400) == math.inf and read_number(-(10**400)) == -math.inf
    assert read_number(1.5) == 1.5 and read_number(-math.inf) == -math.inf
    nan, zero = read_number(math.nan), read_number(0)
    assert nan is not None and math.isnan(nan)
    assert zero is not None and zero == 0.0 and math.copysign(1.0, zero) == 1.0
