"""The pre-push guard (`scripts/pre_push_guard.py`, installed by `scripts/install-hooks.sh`; R-150).

On scratch repositories: a stand-in public root `R`, a descendant line, a foreign root `F` (the
private history), and a merge of the two. A push to the public repository passes only if every
commit it could send descends from `R` — a merge that drags in `F` is refused though its tip
descends from `R` — and a deletion, the archive `openflowsheet-dev` and any other remote pass. The
installed hook, run by `git push` itself, refuses a push to a path naming the public repository
where the real `PUBLIC_ROOT` is absent, and lets a push to the archive through.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import pre_push_guard  # noqa: E402
from pre_push_guard import RefusalError  # noqa: E402

ZERO = "0" * 40
PUBLIC_URLS = (
    "https://github.com/computational-chemical-engineering/openflowsheet.git",
    "https://github.com/computational-chemical-engineering/openflowsheet",
    "git@github.com:computational-chemical-engineering/openflowsheet.git",
    "ssh://git@github.com/Computational-Chemical-Engineering/OpenFlowsheet.git",
    "/tmp/x/computational-chemical-engineering/openflowsheet.git",
    "https://github.com/computational-chemical-engineering/openflowsheet-docs.git",
)
UNGUARDED_URLS = (
    "https://github.com/computational-chemical-engineering/openflowsheet-dev.git",
    "git@github.com:computational-chemical-engineering/openflowsheet-dev",
    "https://github.com/someone/openflowsheet.git",
    "/tmp/elsewhere.git",
    "DISABLED-no-direct-push",
)


def _git(repo: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *arguments],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit(repo: Path, name: str) -> str:
    (repo / name).write_text(name, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-qm", name)
    return _git(repo, "rev-parse", "HEAD")


class Lines:
    def __init__(self, repo: Path) -> None:
        self.repo = repo
        _git(repo.parent, "init", "-q", "-b", "public", str(repo))
        self.root = _commit(repo, "root")
        self.public = _commit(repo, "public-1")
        _git(repo, "checkout", "-q", "--orphan", "private")
        _git(repo, "rm", "-rqf", ".")
        self.foreign = _commit(repo, "private-1")
        _git(repo, "checkout", "-q", "public")
        _git(repo, "merge", "-q", "--allow-unrelated-histories", "-m", "merge", "private")
        self.merge = _git(repo, "rev-parse", "HEAD")
        _git(repo, "tag", "-a", "-m", "t", "v-public", self.public)

    def check(self, url: str, *objects: str) -> None:
        lines = [f"refs/heads/x {o} refs/heads/x {ZERO}\n" for o in objects]
        pre_push_guard.check(url, lines, root=self.root, cwd=self.repo)


@pytest.fixture
def lines(tmp_path: Path) -> Lines:
    return Lines(tmp_path / "repo")


@pytest.mark.parametrize("url", PUBLIC_URLS)
def test_the_public_repository_is_guarded(url: str) -> None:
    assert pre_push_guard.guarded(url)


@pytest.mark.parametrize("url", UNGUARDED_URLS)
def test_the_archive_and_other_remotes_are_not(url: str) -> None:
    assert not pre_push_guard.guarded(url)


def test_descendants_of_the_root_pass(lines: Lines) -> None:
    url = PUBLIC_URLS[0]
    lines.check(url, lines.root)
    lines.check(url, lines.public)
    lines.check(url, _git(lines.repo, "rev-parse", "v-public"))  # an annotated tag
    lines.check(url)  # nothing pushed
    assert pre_push_guard.foreign_commits([lines.public], lines.root, lines.repo) == []


def test_a_foreign_commit_or_a_merge_of_one_is_refused(lines: Lines) -> None:
    url = PUBLIC_URLS[0]
    for pushed in ((lines.foreign,), (lines.merge,), (lines.public, lines.foreign)):
        with pytest.raises(RefusalError, match=r"1 commits do not descend from v0\.1\.0"):
            lines.check(url, *pushed)
    assert pre_push_guard.foreign_commits([lines.merge], lines.root, lines.repo) == [lines.foreign]


def test_the_archive_and_other_remotes_take_anything(lines: Lines) -> None:
    for url in UNGUARDED_URLS:
        lines.check(url, lines.foreign, lines.merge)


def test_a_deletion_sends_nothing(lines: Lines) -> None:
    deletion = [f"(delete) {ZERO} refs/heads/x {lines.foreign}\n"]
    pre_push_guard.check(PUBLIC_URLS[0], deletion, root=lines.root, cwd=lines.repo)


def test_without_the_root_or_on_a_git_error_the_push_is_refused(lines: Lines) -> None:
    lines_ = [f"refs/heads/x {lines.public} refs/heads/x {ZERO}\n"]
    with pytest.raises(RefusalError, match="cannot show that the push descends"):
        pre_push_guard.check(PUBLIC_URLS[0], lines_, root="e" * 40, cwd=lines.repo)
    with pytest.raises(RefusalError, match="cannot show that the push descends"):
        pre_push_guard.check(PUBLIC_URLS[0], ["refs/heads/x\n"], root=lines.root, cwd=lines.repo)


def test_the_installed_hook_guards_git_push(tmp_path: Path) -> None:
    repo = tmp_path / "dev"
    _git(tmp_path, "init", "-q", "-b", "main", str(repo))
    (repo / "scripts").mkdir()
    for name in ("install-hooks.sh", "pre_push_guard.py"):
        shutil.copy2(REPO_ROOT / "scripts" / name, repo / "scripts" / name)
    _commit(repo, "a")
    installed = subprocess.run(
        ["bash", str(repo / "scripts" / "install-hooks.sh")],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    hook = Path(_git(repo, "rev-parse", "--path-format=absolute", "--git-path", "hooks"))
    assert installed.stdout.strip() == f"installed {hook / 'pre-push'}"
    assert (hook / "pre-push").read_bytes() == (
        REPO_ROOT / "scripts" / "pre_push_guard.py"
    ).read_bytes()
    remotes = tmp_path / "computational-chemical-engineering"
    for name in ("openflowsheet.git", "openflowsheet-dev.git"):
        _git(tmp_path, "init", "-q", "--bare", str(remotes / name))
    public = subprocess.run(
        ["git", "push", str(remotes / "openflowsheet.git"), "HEAD:refs/heads/main"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert public.returncode != 0
    assert "pre-push: refused push to" in public.stderr
    assert _git(remotes / "openflowsheet.git", "for-each-ref") == ""
    _git(repo, "push", "-q", str(remotes / "openflowsheet-dev.git"), "HEAD:refs/heads/main")
    # A second install is a no-op; a different hook is kept unless --force.
    subprocess.run(["bash", str(repo / "scripts" / "install-hooks.sh")], cwd=repo, check=True)
    (hook / "pre-push").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    refused = subprocess.run(
        ["bash", str(repo / "scripts" / "install-hooks.sh")],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert refused.returncode == 1 and "--force" in refused.stderr
    subprocess.run(
        ["bash", str(repo / "scripts" / "install-hooks.sh"), "--force"], cwd=repo, check=True
    )
    assert (hook / "pre-push").read_bytes() == (
        REPO_ROOT / "scripts" / "pre_push_guard.py"
    ).read_bytes()
