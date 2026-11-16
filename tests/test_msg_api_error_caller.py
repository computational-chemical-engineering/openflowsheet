"""MSG-G3's caller attribution of `api_error` (ADR 0076 I-9 acceptance evidence).

`api_error` records the module of its caller (`sys._getframe(1)`) as the producer of a code the
catalogue lacks. The auditor accepts any `openflowsheet.` module (messages/audit.py), so the suite's
audit cannot see a frame added between a caller and `api_error`: the wrapper's module would be
recorded instead, and it is an `openflowsheet.` module too. These tests pin the frame: a call from
this test module (not an `openflowsheet.` module) records nothing, and the same call executed with
globals `{"__name__": "openflowsheet.probe"}` records exactly that module. They pass before and
after I-9 moves `api_error` to `application.errors`.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from openflowsheet.application.contract import ApplicationError, api_error
from openflowsheet.messages import audit
from openflowsheet.messages.catalogue import CATALOGUE

#: A code with no catalogue entry, so that an attributed call records a miss.
PROBE_CODE = "s19_i9_probe_code_without_entry"


@pytest.fixture
def auditor() -> Iterator[audit.Auditor]:
    """A fresh auditor for the test, so the probe's miss never reaches the session's."""
    saved = audit.auditor
    audit.auditor = audit.Auditor()
    try:
        yield audit.auditor
    finally:
        audit.auditor = saved


def test_the_probe_code_has_no_catalogue_entry() -> None:
    assert PROBE_CODE not in CATALOGUE


def test_a_call_from_a_test_module_records_no_miss(auditor: audit.Auditor) -> None:
    error = api_error(PROBE_CODE, "probe")  # type: ignore[arg-type]
    assert isinstance(error, ApplicationError)
    assert auditor.misses == {}


def test_the_callers_module_is_the_frame_that_calls_api_error(auditor: audit.Auditor) -> None:
    namespace: dict[str, Any] = {
        "__name__": "openflowsheet.probe",
        "api_error": api_error,
        "code": PROBE_CODE,
    }
    exec(compile("error = api_error(code, 'probe')", "<probe>", "exec"), namespace)  # noqa: S102
    assert isinstance(namespace["error"], ApplicationError)
    assert auditor.misses == {PROBE_CODE: "openflowsheet.probe"}
