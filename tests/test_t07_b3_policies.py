"""T07 `v17-c1` B3: V17 spec F3, adopted by the build lane (`docs/T07_DECISIONS.md`) and not
implemented until now (`docs/t07-v17-c1-failure-analysis.md` §B3).

A solve policy that `benchmarks/registry.yaml` registers but the application does not offer (for
example `T06-revision-v1`) is refused `unsupported`, with `detail.policy_id` and a message saying
it is registered but not offered in v0.1. An unknown id stays `not_found` ("no registered solve
policy", now true of every id it is said of). `src/` does not read the registry at run time:
`policies.REGISTERED_POLICY_IDS` is a committed copy, held equal to the registry here.
"""

from __future__ import annotations

import ast
import math
import time
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT
from t07_corpus import CORPUS
from t07_jobs_support import commit

from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.policies import APPLICATION_POLICIES, REGISTERED_POLICY_IDS
from openflowsheet.application.types import JobRequest, schema_errors

REGISTRY = REPO_ROOT / "benchmarks" / "registry.yaml"
#: Registered and not offered: every registered id but the two the contract offers.
NOT_OFFERED = sorted(REGISTERED_POLICY_IDS - set(APPLICATION_POLICIES))


def test_the_registered_ids_are_the_registrys() -> None:
    import yaml

    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["policies"]
    # Review 2, S2: a policy is named by its registry key; `policy_id` is the string its document
    # carries. Both are registered names, 9 strings.
    keys = set(registry)
    policy_ids = {entry["policy_id"] for entry in registry.values()}
    assert REGISTERED_POLICY_IDS == keys | policy_ids
    assert keys <= REGISTERED_POLICY_IDS and policy_ids <= REGISTERED_POLICY_IDS
    assert len(REGISTERED_POLICY_IDS) == 9
    # T08 W4 (ADR 0024 D1) and W3 (ADR 0023): `T08-warm-v1` and `T08-ptc-v1` are offered and are
    # not registry policies — the registry holds exactly the policies its registrations name
    # (`test_t06_w4_registry`), and none names them. Every other offered policy is registered.
    t08 = {"T08-ptc-v1", "T08-warm-v1"}
    assert set(APPLICATION_POLICIES) - t08 < REGISTERED_POLICY_IDS
    assert t08 <= set(APPLICATION_POLICIES) and not t08 & REGISTERED_POLICY_IDS
    assert "T06-revision-v1" in NOT_OFFERED and "T04-HOM-01-edge-off" in NOT_OFFERED
    assert len(NOT_OFFERED) == 7


def _strings(tree: ast.AST) -> list[str]:
    """Every string constant of a module that is not a docstring."""
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


def test_src_does_not_read_the_registry() -> None:
    """No module of `src/` holds the registry's path as a string in code: a path constant has no
    whitespace (a provenance sentence citing the registry, `scaling.SCALE_PROVENANCE`, is not a
    path; docstrings and comments are not code)."""
    readers = [
        path
        for path in sorted((REPO_ROOT / "src").rglob("*.py"))
        if any(
            "registry.yaml" in text and not any(c.isspace() for c in text)
            for text in _strings(ast.parse(path.read_text("utf-8")))
        )
    ]
    assert readers == []


@pytest.fixture(scope="module")
def application(tmp_path_factory: pytest.TempPathFactory) -> Any:
    root = tmp_path_factory.mktemp("b3")
    with LocalApplication.create(root / "p", project_id="t07-b3") as app:
        app.revision_id = commit(app, CORPUS["SYN-001-nominal"]())  # type: ignore[attr-defined]
        yield app


def _submit(application: Any, policy_id: str) -> Any:
    return application.submit_job(
        JobRequest.from_document(
            {
                "operation": "solve",
                "idempotency_key": f"b3-{time.monotonic_ns()}",
                "body": {"revision_id": application.revision_id, "policy_id": policy_id},
            }
        )
    )


def _jobs(application: Any) -> int:
    return len(application.list_jobs(limit=200).items)


@pytest.mark.parametrize("policy_id", NOT_OFFERED)
def test_a_registered_policy_not_offered_is_refused_unsupported(
    application: Any, policy_id: str
) -> None:
    before = _jobs(application)
    with pytest.raises(ApplicationError) as refused:
        _submit(application, policy_id)
    error = refused.value.error
    assert error.code == "unsupported"
    assert error.message == f"solve policy {policy_id!r} is registered but not offered in v0.1"
    assert error.detail == {"policy_id": policy_id, "offered": sorted(APPLICATION_POLICIES)}
    assert error.retryable is False
    assert schema_errors("api-error.schema.json", error.as_document()) == []
    assert _jobs(application) == before


@pytest.mark.parametrize("policy_id", ["no-such-policy", "T06-revision-v3", "t06-revision-v1"])
def test_an_unknown_policy_stays_not_found(application: Any, policy_id: str) -> None:
    with pytest.raises(ApplicationError) as refused:
        _submit(application, policy_id)
    error = refused.value.error
    assert error.code == "not_found"
    assert error.message == f"no registered solve policy {policy_id!r}"
    assert error.detail == {"policy_id": policy_id, "registered": sorted(APPLICATION_POLICIES)}


@pytest.mark.parametrize("policy_id", ["default", *sorted(APPLICATION_POLICIES)])
def test_an_offered_policy_is_admitted(application: Any, policy_id: str) -> None:
    submitted = _submit(application, policy_id)
    job = application.wait_job(submitted.job.job_id, timeout_s=math.inf).job
    assert job.status == "completed"


def test_the_v17_c1_t10_1_request(tmp_path: Path) -> None:
    """The T10-1 agent's request, `T06-revision-v1`, as the transcript records it: now refused
    `unsupported`, where `v17-c1` said `not_found` "no registered solve policy"."""
    with LocalApplication.create(tmp_path / "t10", project_id="t07-b3-t10") as app:
        revision = commit(app, CORPUS["SYN-001-nominal"]())
        with pytest.raises(ApplicationError) as refused:
            app.submit_job(
                JobRequest.from_document(
                    {
                        "operation": "solve",
                        "body": {"revision_id": revision, "policy_id": "T06-revision-v1"},
                        "idempotency_key": "t10-1",
                    }
                )
            )
    assert refused.value.code == "unsupported"
    assert "registered but not offered in v0.1" in refused.value.error.message
