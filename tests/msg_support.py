"""MSG WO-3 (design note §3.3, §5): helpers for tests that compare a transported `ApiError`'s
`detail` exactly. Not collected.

A projected error (every transport, and `dispatch`) carries `detail.explanation`, the rendered
explanation; the machine members are unchanged (I1). `machine_detail` is the comparison those
tests make: the detail without the explanation, which must be there.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def machine_detail(document: Mapping[str, Any]) -> dict[str, Any]:
    """`document["detail"]` without `explanation`; asserts the transport attached one for the
    document's own code."""
    detail = dict(document["detail"])
    explanation = detail.pop("explanation", None)
    assert isinstance(explanation, Mapping), f"no detail.explanation on {document['code']}"
    assert explanation["chain"][0] == document["code"], explanation["chain"]
    return detail
