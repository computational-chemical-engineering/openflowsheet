"""T06 F4 WO6 (the code half): `T06-revision-v1` is `T05b-v2` with only
`globalization.eo_recovery` changed (design note `docs/design/T06-F4-recovery.md` §5.6, §6.1;
ADR 0015). The spec and registry amendments of WO6 are the design lane's.
"""

from __future__ import annotations

import dataclasses

from t05b_support import POLICY_V2
from t06_support import T06_REVISION_POLICY_V1 as T06_REVISION_POLICY
from test_k03_schemas import errors_for

from openflowsheet.orchestrator.trace import GlobalizationPolicy, SolvePolicy


def _differing(a: object, b: object, kind: type) -> list[str]:
    return [f.name for f in dataclasses.fields(kind) if getattr(a, f.name) != getattr(b, f.name)]


def test_wo6_the_revision_policy_differs_from_t05b_v2_in_exactly_two_fields() -> None:
    policy = T06_REVISION_POLICY
    assert _differing(policy, POLICY_V2, SolvePolicy) == ["policy_id", "globalization"]
    assert _differing(policy.globalization, POLICY_V2.globalization, GlobalizationPolicy) == [
        "eo_recovery"
    ]
    assert policy.policy_id == "T06-revision-v1"
    assert policy.globalization.eo_recovery == "homotopy_or_sequential_restart"
    assert POLICY_V2.globalization.eo_recovery == "homotopy"


def test_wo6_the_revision_policy_document_is_schema_valid_and_differs_in_two_values() -> None:
    document = T06_REVISION_POLICY.as_document()
    assert errors_for("solve_policy", document) == []
    registered = POLICY_V2.as_document()
    assert {key for key in document if document[key] != registered[key]} == {
        "policy_id",
        "globalization",
    }
    assert {
        key
        for key in document["globalization"]
        if document["globalization"][key] != registered["globalization"][key]
    } == {"eo_recovery"}
