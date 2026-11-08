"""OPT WO-6 (design §4.10, ADR 0071): the `optimize` job operation, default environment.

G11's job half: without an audited NLP solver `submit_job(optimize)` is refused `unsupported`,
`detail.code = nlp_solver_unavailable`, pointer `/operation`, before any job exists, and neither
Pyomo nor cyipopt is imported. The request round-trips through `JobRequest` (the Amendment-16
branch). G12 (job ≡ library) and G14 (cancellation, budget) need Ipopt: audited environment.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from test_opt_request import UNAVAILABLE, _fixture, _th_r1

from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.types import JobRequest, OptimizeBody
from openflowsheet.studies.nlp import closure


def _request(revision_id: str) -> dict[str, object]:
    return {
        "operation": "optimize",
        "idempotency_key": "opt-wo6",
        "body": {"revision_id": revision_id, "request": _fixture("valid", "th_r1_minimal")},
    }


def test_the_optimize_request_round_trips() -> None:
    request = JobRequest.from_document(_request("rev-1"))
    assert isinstance(request.body, OptimizeBody)
    assert request.body.solve_body().revision_id == "rev-1"
    normalized = request.as_document()
    assert normalized["body"]["policy_id"] == "default"
    assert normalized["body"]["check_tolerances"] == {}
    assert JobRequest.from_document(normalized).request_sha256 == request.request_sha256


def test_g11_submit_job_without_a_solver_is_unsupported_and_creates_no_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from openflowsheet.application.types import Change, Edit

    with LocalApplication.create(tmp_path / "project", project_id="opt-wo6") as app:
        edits = tuple(Edit("set", (key,), value) for key, value in _th_r1().items())
        revision_id = app.commit_change(Change(edits=edits), None, "seed").revision_id
        assert revision_id is not None
        monkeypatch.setattr(closure, "audited_solver", lambda: UNAVAILABLE)
        with pytest.raises(ApplicationError) as refused:
            app.submit_job(JobRequest.from_document(_request(revision_id)))
        assert refused.value.error.as_document() == {
            "code": "unsupported",
            "message": "nlp_solver_unavailable",
            "detail": {"code": "nlp_solver_unavailable", "pointer": "/operation"},
            "retryable": False,
        }
        rows = [row for row in app.store.audit_rows() if row["outcome"] == "refused"]
        assert [(row["operation"], row["code"]) for row in rows] == [("submit_job", "unsupported")]
    assert "pyomo" not in sys.modules or "pyomo" in _preloaded
    assert "cyipopt" not in sys.modules or "cyipopt" in _preloaded


#: Modules another test in the same process may already have loaded (the audited env).
_preloaded = frozenset(name for name in ("pyomo", "cyipopt") if name in sys.modules)
