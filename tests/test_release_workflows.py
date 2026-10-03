"""The release workflows' guards and pins (docs/RELEASING.md).

`actionlint` checks the workflows' syntax and expressions when it is available (it is not part of
the project environment); these tests hold what the release depends on and a linter does not
know: each workflow runs only in its own repository, the private one is dispatch-only and a dry
run by default, only the job behind the `release` environment sees the deploy key or pushes, the
public one starts only on a `v*` tag and uploads to PyPI by trusted publishing from the job behind
the PyPI environment, and every third-party action is pinned by commit id.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT

WORKFLOWS = REPO_ROOT / ".github" / "workflows"
PRIVATE = "computational-chemical-engineering/openflowsheet-dev"
PUBLIC = "computational-chemical-engineering/openflowsheet"
PINNED = re.compile(r"^\s*(?:-\s*)?uses:\s*([^@\s]+)@([0-9a-f]{40}) # v\d+(?:\.\d+)*\s*$")


def load(name: str) -> dict[str, Any]:
    document: dict[Any, Any] = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    # YAML 1.1 reads the key `on` as the boolean true.
    document["on"] = document.pop(True)
    return document


def guard(repository: str) -> str:
    return f"github.repository == '{repository}'"


@pytest.mark.parametrize("name", ["cut-release.yml", "release.yml"])
def test_every_action_is_pinned_by_commit_id(name: str) -> None:
    lines = (WORKFLOWS / name).read_text(encoding="utf-8").splitlines()
    uses = [line for line in lines if re.match(r"^\s*(?:-\s*)?uses:", line)]
    assert uses
    for line in uses:
        assert PINNED.match(line), f"{name}: not pinned by commit id: {line.strip()}"


def test_cut_release_is_dispatch_only_and_a_dry_run_by_default() -> None:
    workflow = load("cut-release.yml")
    assert list(workflow["on"]) == ["workflow_dispatch"]
    inputs = workflow["on"]["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"version", "rc_commit", "ref", "dry_run"}
    assert inputs["version"]["required"] and inputs["rc_commit"]["required"]
    assert inputs["ref"]["default"] == "main"
    assert inputs["dry_run"]["type"] == "boolean" and inputs["dry_run"]["default"] is True
    assert workflow["permissions"] == {}


def test_cut_release_runs_only_in_the_private_repository() -> None:
    jobs = load("cut-release.yml")["jobs"]
    for name, job in jobs.items():
        assert job["if"].startswith(guard(PRIVATE)), name


def test_only_the_approved_job_pushes_or_sees_the_deploy_key() -> None:
    jobs = load("cut-release.yml")["jobs"]
    publish, snapshot = jobs["publish"], jobs["snapshot"]
    assert publish["environment"] == "release"
    assert publish["needs"] == "snapshot"
    assert publish["if"] == f"{guard(PRIVATE)} && !inputs.dry_run"
    assert publish["permissions"] == {"contents": "write"}
    assert "environment" not in snapshot
    assert snapshot["permissions"] == {"contents": "read"}
    snapshot_text = yaml.safe_dump(snapshot)
    assert "secrets." not in snapshot_text and "git push" not in snapshot_text
    runs = [step.get("run", "") for step in publish["steps"]]
    assert any("--expect-commit" in run for run in runs)
    assert any("push --atomic" in run for run in runs)
    secrets = [step for step in publish["steps"] if "secrets." in yaml.safe_dump(step)]
    assert [step["env"] for step in secrets] == [
        {"DEPLOY_KEY": "${{ secrets.PUBLIC_REPO_DEPLOY_KEY }}"}
    ]


def test_release_runs_only_on_a_version_tag_in_the_public_repository() -> None:
    workflow = load("release.yml")
    assert workflow["on"] == {"push": {"tags": ["v*"]}}
    assert workflow["permissions"] == {}
    for name, job in workflow["jobs"].items():
        assert job["if"] == guard(PUBLIC), name


def test_release_publishes_from_the_pypi_environment_by_trusted_publishing() -> None:
    workflow = load("release.yml")
    jobs = workflow["jobs"]
    assert workflow["env"]["PYPI_ENVIRONMENT"] == "pypi"
    assert jobs["build"]["outputs"]["pypi_environment"] == "${{ env.PYPI_ENVIRONMENT }}"
    pypi = jobs["pypi"]
    assert pypi["environment"]["name"] == "${{ needs.build.outputs.pypi_environment }}"
    assert pypi["permissions"] == {"id-token": "write"}
    assert pypi["needs"] == "build"
    assert pypi["steps"][-1]["uses"].startswith("pypa/gh-action-pypi-publish@")
    assert "password" not in yaml.safe_dump(pypi)  # no API token: trusted publishing
    for name, job in jobs.items():
        if name != "pypi":
            assert "id-token" not in job.get("permissions", {}), name
    assert jobs["github-release"]["needs"] == ["build", "pypi"]


def test_release_checks_the_tag_and_the_notes_before_building() -> None:
    steps = load("release.yml")["jobs"]["build"]["steps"]
    runs = [step.get("run", "") for step in steps]
    order = [
        next(n for n, run in enumerate(runs) if needle in run)
        for needle in ("release_snapshot.py verify-tag", "changelog_section.py", "t08_dist.py")
    ]
    assert order == sorted(order)
    for script in ("release_snapshot.py", "changelog_section.py", "t08_dist.py"):
        assert (REPO_ROOT / "scripts" / script).is_file()


def test_the_private_workflow_is_excluded_from_the_public_snapshot() -> None:
    listing = (REPO_ROOT / "release" / "public-exclude.txt").read_text(encoding="utf-8")
    entries = [line for line in listing.splitlines() if line and not line.startswith("#")]
    assert entries == [".github/workflows/cut-release.yml"]
    assert Path(WORKFLOWS / "cut-release.yml").is_file()
