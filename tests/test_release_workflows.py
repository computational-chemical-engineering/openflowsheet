"""The release workflow's guards and pins (docs/RELEASING.md; R-150).

`actionlint` (with `shellcheck`) checks the workflow's syntax, expressions and scripts when it is
available (it is not part of the project environment); these tests hold what the release depends
on and a linter does not know: the workflow runs only in the public repository, by hand, as a dry
run by default; nothing is tagged, uploaded or published on a dry run; only `tag` and
`github-release` may write to the repository, and only `pypi`, behind the `pypi` environment,
holds an OIDC token and uploads, by trusted publishing; every action is pinned by commit id. The
`gate` job's two scripts are run here on a scratch repository: they refuse a version that is not
`pyproject.toml`'s or not `X.Y.Z`, a tag on another commit, and a gate that does not exit 0 *and*
print the version's YES line.

V02 alpha release spec §9.1 (M07a.A20–A24): the version step accepts canonical PEP 440 releases and
pre-releases, `X.Y.Z{a|b|rc}N` with N ≥ 1, exactly as Table T2 states; `0.2.0a1` resolves the gate
`scripts/v0_2_gate.py`, whose YES line must name the version; `github-release` marks a version with
an `a`, `b` or `rc` segment `--prerelease`; and the dispatch defaults are unchanged (a dry run, and
the v0.1 candidate as `rc`). Table T2 is read from `benchmarks/m07a/reference_values.yaml`, which
`v02a_reference.py --check` re-derives from the specification (M07a.A00).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT

WORKFLOWS = REPO_ROOT / ".github" / "workflows"
RELEASE = "release.yml"
CI = "ci.yml"
#: DOC (S14): the documentation site's build and Pages deployment.
SITE = "site.yml"
PUBLIC = "computational-chemical-engineering/openflowsheet"
GUARD = f"github.repository == '{PUBLIC}'"
C = "67c66d98587f23bd7dfe8da28a8facccc92da21e"
PINNED = re.compile(r"^\s*(?:-\s*)?uses:\s*([^@\s]+)@([0-9a-f]{40}) # v\d+(?:\.\d+)*\s*$")


def load() -> dict[str, Any]:
    document: dict[Any, Any] = yaml.safe_load((WORKFLOWS / RELEASE).read_text(encoding="utf-8"))
    # YAML 1.1 reads the key `on` as the boolean true.
    document["on"] = document.pop(True)
    return document


def step(job: str, name: str) -> dict[str, Any]:
    (found,) = [s for s in load()["jobs"][job]["steps"] if s.get("name") == name]
    return found


def test_one_release_workflow_and_no_other() -> None:
    assert not (WORKFLOWS / "cut-release.yml").exists()
    assert sorted(path.name for path in WORKFLOWS.glob("*.yml")) == ["ci.yml", RELEASE, SITE]
    for gone in ("scripts/release_snapshot.py", "release/public-exclude.txt"):
        assert not (REPO_ROOT / gone).exists()


def test_every_action_is_pinned_by_commit_id() -> None:
    lines = (WORKFLOWS / RELEASE).read_text(encoding="utf-8").splitlines()
    uses = [line for line in lines if re.match(r"^\s*(?:-\s*)?uses:", line)]
    assert uses
    for line in uses:
        assert PINNED.match(line), f"not pinned by commit id: {line.strip()}"


def test_ci_every_action_is_pinned_by_commit_id() -> None:
    lines = (WORKFLOWS / CI).read_text(encoding="utf-8").splitlines()
    uses = [line for line in lines if re.match(r"^\s*(?:-\s*)?uses:", line)]
    assert uses
    for line in uses:
        assert PINNED.match(line), f"not pinned by commit id: {line.strip()}"


def test_site_every_action_is_pinned_by_commit_id() -> None:
    lines = (WORKFLOWS / SITE).read_text(encoding="utf-8").splitlines()
    uses = [line for line in lines if re.match(r"^\s*(?:-\s*)?uses:", line)]
    assert uses
    for line in uses:
        assert PINNED.match(line), f"not pinned by commit id: {line.strip()}"


def test_site_deploys_only_from_main_in_the_public_repository() -> None:
    """DOC (S14): every push and pull request builds the site; only a push to `main` in the public
    repository uploads and deploys it, and only the deploy job may write to Pages."""
    document: dict[Any, Any] = yaml.safe_load((WORKFLOWS / SITE).read_text(encoding="utf-8"))
    assert document["permissions"] == {"contents": "read"}
    jobs = document["jobs"]
    assert list(jobs) == ["build", "deploy"]
    main = "github.event_name == 'push' && github.ref == 'refs/heads/main'"
    (upload,) = [s for s in jobs["build"]["steps"] if s.get("name") == "Upload Pages artifact"]
    assert upload["if"] == main
    deploy = jobs["deploy"]
    assert deploy["needs"] == "build" and deploy["if"].startswith(main) and GUARD in deploy["if"]
    assert deploy["permissions"] == {"pages": "write", "id-token": "write"}
    assert deploy["environment"]["name"] == "github-pages"
    assert "permissions" not in jobs["build"]
    build = " ".join(str(s.get("run", "")) for s in jobs["build"]["steps"])
    assert "mkdocs build --strict --site-dir site" in build
    assert "--require-hashes -r requirements-docs.txt" in build


def test_dispatch_only_a_dry_run_by_default_and_c_by_default() -> None:
    workflow = load()
    assert list(workflow["on"]) == ["workflow_dispatch"]
    inputs = workflow["on"]["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"version", "rc", "dry_run"}
    assert inputs["version"]["required"] is True
    assert inputs["rc"]["default"] == C
    assert inputs["dry_run"]["type"] == "boolean" and inputs["dry_run"]["default"] is True
    assert workflow["permissions"] == {}
    assert workflow["env"] == {"VERSION": "${{ inputs.version }}", "RC": "${{ inputs.rc }}"}


def test_every_job_runs_only_in_the_public_repository() -> None:
    jobs = load()["jobs"]
    assert list(jobs) == ["gate", "tag", "build", "pypi", "github-release"]
    for name, job in jobs.items():
        assert GUARD in job["if"], name


def test_the_order_and_what_a_dry_run_skips() -> None:
    jobs = load()["jobs"]
    assert jobs["tag"]["needs"] == "gate"
    assert jobs["build"]["needs"] == ["gate", "tag"]
    assert jobs["pypi"]["needs"] == "build"
    assert jobs["github-release"]["needs"] == ["build", "pypi"]
    for name in ("tag", "pypi", "github-release"):
        assert jobs[name]["if"] == f"{GUARD} && !inputs.dry_run", name
    # `build` runs on a dry run (tag skipped) and after a tag that succeeded, never otherwise.
    build = " ".join(jobs["build"]["if"].split())
    assert build.startswith("!cancelled() && ")
    assert "needs.gate.result == 'success'" in build
    assert (
        "(needs.tag.result == 'success' || (inputs.dry_run && needs.tag.result == 'skipped'))"
        in build
    )


def test_permissions_tokens_and_secrets() -> None:
    jobs = load()["jobs"]
    assert jobs["gate"]["permissions"] == {"contents": "read"}
    assert jobs["build"]["permissions"] == {"contents": "read"}
    assert jobs["tag"]["permissions"] == {"contents": "write"}
    assert jobs["github-release"]["permissions"] == {"contents": "write"}
    pypi = jobs["pypi"]
    assert pypi["permissions"] == {"id-token": "write"}
    assert pypi["environment"]["name"] == "pypi"
    assert pypi["steps"][-1]["uses"].startswith("pypa/gh-action-pypi-publish@")
    assert "password" not in yaml.safe_dump(pypi)  # no API token: trusted publishing
    for name, job in jobs.items():
        if name != "pypi":
            assert "environment" not in job and "id-token" not in job["permissions"], name
    text = (WORKFLOWS / RELEASE).read_text(encoding="utf-8")
    assert "secrets." not in text
    pushes = [
        name
        for name, job in jobs.items()
        if any("git push" in s.get("run", "") for s in job["steps"])
    ]
    assert pushes == ["tag"]
    # Only `tag` keeps the checkout's credentials (to push the tag with GITHUB_TOKEN).
    for name in ("gate", "build"):
        checkout = jobs[name]["steps"][0]
        assert checkout["uses"].startswith("actions/checkout@")
        assert checkout["with"]["persist-credentials"] is False, name


def test_the_gate_job_checks_before_anything_is_built() -> None:
    gate = load()["jobs"]["gate"]
    assert gate["steps"][0]["with"]["fetch-depth"] == 0  # tags, and C where it is present
    runs = [s.get("run", "") for s in gate["steps"]]
    order = [
        next(n for n, run in enumerate(runs) if needle in run)
        for needle in ("pip install -r requirements.lock", "pyproject.toml", "changelog_section.py")
    ]
    assert order == sorted(order)
    gate_run = step("gate", "The release gate")["run"]
    assert '--rc "$RC"' in gate_run
    assert 'grep -qxF "v$VERSION tag may be proposed: YES"' in gate_run
    assert gate["outputs"]["commit"] == "${{ steps.gate.outputs.commit }}"
    for job in ("tag", "build"):
        checkouts = [s for s in load()["jobs"][job]["steps"] if "checkout" in s.get("uses", "")]
        assert checkouts[0]["with"]["ref"] == "${{ needs.gate.outputs.commit }}", job
    for script in ("changelog_section.py", "t08_dist.py", "v0_1_gate.py", "v0_2_gate.py"):
        assert (REPO_ROOT / "scripts" / script).is_file()


# -- the gate job's scripts, on a scratch repository -------------------------------------------

FAKE_GATE = """import os, sys
print(os.environ["FAKE_GATE_OUT"])
sys.exit(int(os.environ["FAKE_GATE_EXIT"]))
"""


def _git(repo: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *arguments],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def scratch(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "pyproject.toml").write_text('[project]\nname = "p"\nversion = "0.1.1"\n', "utf-8")
    (repo / "scripts" / "v0_1_gate.py").write_text(FAKE_GATE, "utf-8")
    _git(tmp_path, "init", "-q", str(repo))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "one")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "two")
    (tmp_path / "runner").mkdir()
    (tmp_path / "runner" / "record").mkdir()
    return repo


def _run(
    repo: Path, name: str, version: str, *, job: str = "gate", **env: str
) -> subprocess.CompletedProcess[str]:
    script = step(job, name)["run"]
    environment = {
        **os.environ,
        "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}",
        "VERSION": version,
        "RC": C,
        "RUNNER_TEMP": str(repo.parent / "runner"),
        "GITHUB_OUTPUT": str(repo.parent / "runner" / "output"),
        **env,
    }
    return subprocess.run(
        ["bash", "-e", "-c", script], cwd=repo, env=environment, capture_output=True, text=True
    )


VERSION_STEP = "The version is pyproject.toml's, and its tag is free or on this commit"


def test_the_version_step(scratch: Path) -> None:
    assert _run(scratch, VERSION_STEP, "0.1.1").returncode == 0
    for version, why in (
        ("0.1.2", "declares version '0.1.1', not '0.1.2'"),
        ("v0.1.1", "not of the form X.Y.Z"),
        ("0.1", "not of the form X.Y.Z"),
        ("0.1.1; true", "not of the form X.Y.Z"),
    ):
        refused = _run(scratch, VERSION_STEP, version)
        assert refused.returncode == 1 and "refused: " in refused.stderr, version
        assert why in refused.stderr, version
    _git(scratch, "tag", "v0.1.1", "HEAD")
    assert _run(scratch, VERSION_STEP, "0.1.1").returncode == 0
    _git(scratch, "tag", "-f", "v0.1.1", "HEAD~1")
    refused = _run(scratch, VERSION_STEP, "0.1.1")
    assert refused.returncode == 1 and "tag v0.1.1 exists on another commit" in refused.stderr


def test_the_gate_step(scratch: Path) -> None:
    output = scratch.parent / "runner" / "output"
    passed = _run(
        scratch,
        "The release gate",
        "0.1.1",
        FAKE_GATE_OUT="...\nv0.1.1 tag may be proposed: YES",
        FAKE_GATE_EXIT="0",
    )
    assert passed.returncode == 0, passed.stderr
    assert output.read_text("utf-8") == f"commit={_git(scratch, 'rev-parse', 'HEAD')}\n"
    record = (scratch.parent / "runner" / "record" / "gate.txt").read_text("utf-8")
    assert record.endswith("v0.1.1 tag may be proposed: YES\n")
    for out, code, version, why in (
        ("v0.1.1 tag may be proposed: YES", "1", "0.1.1", "exited 1"),
        ("v0.1.1 tag may be proposed: NO (2 reasons)", "0", "0.1.1", "did not print"),
        ("v0.1.0 tag may be proposed: YES", "0", "0.1.1", "did not print"),
        ("v0.1.1 tag may be proposed: YES (sic)", "0", "0.1.1", "did not print"),
        ("v0.2.0 tag may be proposed: YES", "0", "0.2.0", "no release gate"),
    ):
        output.unlink(missing_ok=True)
        refused = _run(scratch, "The release gate", version, FAKE_GATE_OUT=out, FAKE_GATE_EXIT=code)
        assert refused.returncode == 1 and why in refused.stderr, (out, code, version)
        assert not output.exists()


# -- R-922 (V03-post1): a post-release X.Y.Z.postN of a tagged X.Y.Z ----------------------------


def test_r922_the_version_step_admits_a_post_release_of_a_tagged_release(scratch: Path) -> None:
    (scratch / "pyproject.toml").write_text(
        '[project]\nname = "p"\nversion = "0.1.1.post1"\n', "utf-8"
    )
    _git(scratch, "commit", "-qam", "post")
    refused = _run(scratch, VERSION_STEP, "0.1.1.post1")
    assert refused.returncode == 1, refused.stderr
    assert "post-release 0.1.1.post1 of 0.1.1, which has no tag v0.1.1 (R-922)" in refused.stderr
    _git(scratch, "tag", "v0.1.1", "HEAD~1")
    assert _run(scratch, VERSION_STEP, "0.1.1.post1").returncode == 0


@pytest.mark.parametrize(
    "version",
    [
        "0.1.1.post0",
        "0.1.1.post01",
        "0.1.1rc1.post1",
        "0.1.1.post1.dev0",
        "0.1.1-post1",
        "0.1.1post1",
    ],
)
def test_r922_the_version_step_refuses_other_post_forms(scratch: Path, version: str) -> None:
    (scratch / "pyproject.toml").write_text(
        f'[project]\nname = "p"\nversion = "{version}"\n', "utf-8"
    )
    _git(scratch, "tag", "v0.1.1", "HEAD")
    refused = _run(scratch, VERSION_STEP, version)
    assert refused.returncode == 1 and "not of the form" in refused.stderr, version


def test_r922_a_post_release_resolves_its_line_s_gate(scratch: Path) -> None:
    passed = _run(
        scratch,
        "The release gate",
        "0.1.1.post1",
        FAKE_GATE_OUT="...\nv0.1.1.post1 tag may be proposed: YES",
        FAKE_GATE_EXIT="0",
    )
    assert passed.returncode == 0, passed.stderr
    refused = _run(
        scratch,
        "The release gate",
        "0.1.1.post1",
        FAKE_GATE_OUT="...\nv0.1.1 tag may be proposed: YES",
        FAKE_GATE_EXIT="0",
    )
    assert refused.returncode == 1 and "did not print" in refused.stderr


# -- M07a.A20–A23: PEP 440 pre-releases (V02 alpha release spec §9.1) --------------------------

M07A = yaml.safe_load(
    (REPO_ROOT / "benchmarks" / "m07a" / "reference_values.yaml").read_text(encoding="utf-8")
)


@pytest.mark.parametrize(
    ("version", "accepted"), M07A["truth_tables"]["T2_workflow_version"].items()
)
def test_m07a_a20_the_version_step_is_table_t2(scratch: Path, version: str, accepted: bool) -> None:
    (scratch / "pyproject.toml").write_text(
        f'[project]\nname = "p"\nversion = "{version}"\n', "utf-8"
    )
    result = _run(scratch, VERSION_STEP, version)
    if accepted:
        assert result.returncode == 0, result.stderr
    else:
        assert result.returncode == 1 and "refused: " in result.stderr
        assert "not of the form" in result.stderr


def test_m07a_a20_the_step_s_pattern_is_the_registered_one() -> None:
    pattern = M07A["targets"]["workflow_version_pattern"]
    assert f'[[ "$VERSION" =~ {pattern} ]]' in step("gate", VERSION_STEP)["run"]


def test_m07a_a21_a_pre_release_resolves_the_0_2_gate(scratch: Path) -> None:
    (scratch / "scripts" / "v0_2_gate.py").write_text(FAKE_GATE, "utf-8")
    output = scratch.parent / "runner" / "output"
    passed = _run(
        scratch,
        "The release gate",
        "0.2.0a1",
        FAKE_GATE_OUT="...\nv0.2.0a1 tag may be proposed: YES",
        FAKE_GATE_EXIT="0",
    )
    assert passed.returncode == 0, passed.stderr
    assert output.read_text("utf-8") == f"commit={_git(scratch, 'rev-parse', 'HEAD')}\n"
    for out, code, why in (
        ("v0.2.0a2 tag may be proposed: YES", "0", "did not print"),
        ("v0.2.0 tag may be proposed: YES", "0", "did not print"),
        ("v0.2.0a1 tag may be proposed: YES", "1", "v0_2_gate.py exited 1"),
    ):
        output.unlink(missing_ok=True)
        refused = _run(
            scratch, "The release gate", "0.2.0a1", FAKE_GATE_OUT=out, FAKE_GATE_EXIT=code
        )
        assert refused.returncode == 1 and why in refused.stderr, (out, code)
        assert not output.exists()


FAKE_GH = """#!/usr/bin/env bash
printf '%s\\n' "$@" > "$FAKE_GH_ARGS"
"""


@pytest.mark.parametrize(
    ("version", "prerelease"),
    [("0.2.0a1", True), ("0.2.0rc1", True), ("0.2.0", False), ("0.3.0.post1", False)],
)
def test_m07a_a23_github_release_marks_pre_releases(
    tmp_path: Path, version: str, prerelease: bool
) -> None:
    work = tmp_path / "work"
    (work / "dist").mkdir(parents=True)
    (work / "record").mkdir()
    (work / "dist" / f"openflowsheet-{version}.tar.gz").write_text("sdist", "utf-8")
    (work / "record" / "notes.md").write_text("notes", "utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "gh").write_text(FAKE_GH, "utf-8")
    (bin_dir / "gh").chmod(0o755)
    arguments = tmp_path / "gh-arguments"
    result = subprocess.run(
        ["bash", "-e", "-c", step("github-release", "Create the GitHub release")["run"]],
        cwd=work,
        env={
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "VERSION": version,
            "GITHUB_REPOSITORY": PUBLIC,
            "GH_TOKEN": "unused",
            "FAKE_GH_ARGS": str(arguments),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    passed = arguments.read_text("utf-8").splitlines()
    assert passed[:3] == ["release", "create", f"v{version}"]
    assert ("--prerelease" in passed) is prerelease
    assert passed[-1] == f"dist/openflowsheet-{version}.tar.gz"
