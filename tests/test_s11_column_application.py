"""S11 rulings item 9 (a) (R-838): every A29 case solved through the application.

The served path: each committed case (`benchmarks/s11/flowsheets/*.json`: S02 M1–M4, S06 J1–J8,
the recycle case, the Wilson cases C-MW and C-EW, and the Wilson stripper) is committed to a
`LocalApplication` project and solved by `solve` under the policy id `T06-revision-v2`, the
application's registered revision policy (`S01_DEFAULT_V1` is not a served policy). The run is read
back from its job's outputs only: the bundle's `solution-state.json` and the solution certificate.
Each case reproduces A29 (max |Δ|/tol ≤ 1 against its registered root, ≤ 3 Newton iterations
summed over the certificate's branch provenance) and certifies as A35 says.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from s11_column_support import (
    COLUMN_CASES,
    RECYCLE_CASE,
    WILSON_CASES,
    WILSON_STRIPPER,
    column_case_spec,
    committed_case,
)
from t07_jobs_support import commit
from test_s02_column_wo2 import FLOW_ABS, FLOW_REL
from test_s11_column_solve import (
    NEWTON_BUDGET,
    _equals_library_root,
    _expected,
    _worst,
    _worst_wilson,
)
from test_s11_column_verifier import column_items

from openflowsheet.application.local import LocalApplication
from openflowsheet.application.types import RunResult
from openflowsheet.models import flow_id
from openflowsheet.run.bundle import read_artifact

#: The application's registered revision policy (R-838: the served path).
POLICY_ID = "T06-revision-v2"


@pytest.fixture(scope="module")
def app(tmp_path_factory: pytest.TempPathFactory) -> Iterator[LocalApplication]:
    application = LocalApplication.create(
        tmp_path_factory.mktemp("s11-app") / "p", project_id="s11-column-application"
    )
    try:
        yield application
    finally:
        application.close()


def _solve(app: LocalApplication, name: str) -> tuple[RunResult, dict[str, float], dict[str, Any]]:
    """The case committed and solved under `POLICY_ID`: the run result, the bundle's state and
    the solution certificate, each read from the job's outputs."""
    result = app.solve(commit(app, committed_case(name)), POLICY_ID)
    assert (result.job_status, result.outcome, result.error) == ("completed", "CONVERGED", None)
    assert (result.policy_id, result.solve_path) == (POLICY_ID, "revision_eo")
    outputs = {output.kind: output for output in result.outputs}
    bundle = app.store.artifact(outputs["replay_bundle"].artifact_id)
    assert bundle is not None
    state = read_artifact(app.files_root / bundle.relpath, "solution-state.json")
    certificate = app.store.artifact(outputs["solution_certificate"].artifact_id)
    assert certificate is not None
    document = json.loads(Path(app.files_root / certificate.relpath).read_text(encoding="utf-8"))
    assert document["verification_status"] == result.verification_status
    return result, dict(state["variables"]), document


def _iterations(certificate: Mapping[str, Any]) -> int:
    """Newton iterations summed over every attempt of the certificate's branch provenance."""
    return sum(int(entry["iterations"]) for entry in certificate["branch_provenance"])


def _checks(certificate: Mapping[str, Any]) -> dict[str, SimpleNamespace]:
    return {check["id"]: SimpleNamespace(**check) for check in certificate["checks"]}


@pytest.mark.parametrize("name", [*COLUMN_CASES, RECYCLE_CASE])
def test_a29_a35_a_syn001_case_through_the_application(app: LocalApplication, name: str) -> None:
    """A29 (max |Δ|/tol ≤ 1 against S02's/S06's registered root; the recycle case converges with a
    non-zero recycle and closes per component) in ≤ 3 Newton iterations; A35: the column's
    material, energy, specification and stage rows pass, every stage item at 0.0, VERIFIED."""
    result, state, certificate = _solve(app, name)
    assert _iterations(certificate) <= NEWTON_BUDGET
    spec = column_case_spec(name)
    if name == RECYCLE_CASE:
        (feed,) = spec.inlets()
        for c, n in zip("ABC", feed.state.n, strict=True):
            out = state[flow_id("S-DISTILLATE", c)] + state[flow_id("S-PURGE", c)]
            assert abs(out - n) <= FLOW_REL * n + FLOW_ABS
            assert state[flow_id("S-REC", c)] > 0.0
    else:
        worst = _worst(spec, _expected(name), state)
        assert max(worst.values()) <= 1.0, worst
    items = column_items(spec, _checks(certificate))
    failing = {k: (c.result, c.value, c.reason) for k, c in items.items() if c.result != "pass"}
    assert not failing, failing
    assert all(c.value == 0.0 and c.reason == "" for k, c in items.items() if ".stage." in k)
    assert result.verification_status == "VERIFIED", [
        (c["id"], c["result"], c["reason"]) for c in certificate["checks"] if c["result"] != "pass"
    ]


@pytest.mark.parametrize("name", [*WILSON_CASES, WILSON_STRIPPER])
def test_a29_a35_a_wilson_case_through_the_application(app: LocalApplication, name: str) -> None:
    """A29 on `wilson-ig-v1` (C-MW, C-EW: S10-C's registered root, max |Δ|/tol ≤ 1; every case:
    the standalone `solve_column` root exactly) in ≤ 3 Newton iterations; A35 as restated by R-831:
    every row passes, VERIFIED, no partial derivative witness."""
    result, state, certificate = _solve(app, name)
    assert _iterations(certificate) <= NEWTON_BUDGET
    spec = column_case_spec(name)
    if name in WILSON_CASES:
        largest = _worst_wilson(spec, name, state)
        assert largest[0] <= 1.0, largest
    _equals_library_root(spec, state)
    checks = _checks(certificate)
    column_items(spec, checks)
    failing = {k: (c.result, c.reason) for k, c in checks.items() if c.result != "pass"}
    assert not failing, failing
    assert result.verification_status == "VERIFIED"
    assert not [x for x in certificate["limitations"] if x["kind"] == "derivative_witness_partial"]
