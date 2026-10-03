"""Release automation (docs/RELEASING.md): `scripts/release_snapshot.py` and
`scripts/changelog_section.py`.

Every test builds its own scratch repositories: a "private" development repository whose history
holds a file that a later commit deletes (so a leak of history would show), a symbolic link, an
executable, a path with a space and a fake gate script, and an empty bare "public" repository.
The snapshot is judged against what the brief requires of it: one commit per release whose tree
is exactly the tagged tree minus the exclusion list, whose only parent is the previous snapshot,
with no private commit, tree or deleted blob reachable or even present in the public repository,
and the same ids for the same inputs; `check` refuses unless the gate says YES and the version
matches.
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import changelog_section  # noqa: E402
import release_snapshot  # noqa: E402
from release_snapshot import RefusalError  # noqa: E402

#: A gate stand-in: prints `$FAKE_GATE_LINE`, records its arguments and `PYTHONPATH` in
#: `$FAKE_GATE_LOG`, exits `$FAKE_GATE_EXIT`.
FAKE_GATE = """import os, sys
with open(os.environ["FAKE_GATE_LOG"], "w") as log:
    log.write(" ".join(sys.argv[1:]) + "\\n" + os.environ.get("PYTHONPATH", "") + "\\n")
print("V11  PASS  something")
print(os.environ["FAKE_GATE_LINE"])
sys.exit(int(os.environ["FAKE_GATE_EXIT"]))
"""
EXCLUDES = ".github/workflows/cut-release.yml\n"
#: 2026-10-02 23:17:06 +0200, then a day later each.
EPOCH = 1790975826


def run(repo: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture(autouse=True)
def isolated_git(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """No user or system git configuration (signing, hooks, default branch) leaks in."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Developer")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "dev@example.org")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Developer")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "dev@example.org")
    monkeypatch.setenv("FAKE_GATE_LOG", str(tmp_path / "gate.log"))
    monkeypatch.setenv("FAKE_GATE_LINE", "v0.1.0 tag may be proposed: YES")
    monkeypatch.setenv("FAKE_GATE_EXIT", "0")


class Private:
    """A scratch development repository."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.mkdir()
        run(path, "init", "-q", "-b", "main")
        self.commits = 0

    def commit(self, files: dict[str, str | None], version: str = "0.1.0") -> str:
        files = {"pyproject.toml": f'[project]\nname = "x"\nversion = "{version}"\n', **files}
        for name, content in files.items():
            target = self.path / name
            if content is None:
                target.unlink()
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        run(self.path, "add", "-A")
        stamp = f"{EPOCH + 86400 * self.commits} +0200"
        self.commits += 1
        subprocess.run(
            ["git", "commit", "-q", "-m", f"work {self.commits}"],
            cwd=self.path,
            env={**os.environ, "GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp},
            check=True,
        )
        return run(self.path, "rev-parse", "HEAD")

    def tag(self, version: str) -> None:
        run(self.path, "tag", "-a", f"v{version}", "-m", f"v{version}")


def public_repository(path: Path) -> Path:
    run(path.parent, "init", "-q", "--bare", "-b", "main", str(path))
    return path


@pytest.fixture
def private(tmp_path: Path) -> Private:
    repository = Private(tmp_path / "private")
    repository.commit({"secret-draft.txt": "pre-redaction transcript\n", "src/a.py": "a = 1\n"})
    repository.commit(
        {
            "secret-draft.txt": None,
            "release/public-exclude.txt": EXCLUDES,
            ".github/workflows/cut-release.yml": "name: cut-release\n",
            ".github/workflows/release.yml": "name: release\n",
            "scripts/v0_1_gate.py": FAKE_GATE,
            "docs/with space.md": "spaced\n",
            "bin/tool": "#!/bin/sh\necho tool\n",
        }
    )
    tool = repository.path / "bin" / "tool"
    tool.chmod(tool.stat().st_mode | stat.S_IXUSR)
    (repository.path / "src" / "link").symlink_to("a.py")
    run(repository.path, "add", "-A")
    run(repository.path, "commit", "-q", "-m", "mode and link")
    repository.tag("0.1.0")
    return repository


def tree(repo: Path, commit: str) -> dict[str, tuple[str, str]]:
    return {e.path: (e.mode, e.blob) for e in release_snapshot.tree_entries(repo, commit)}


# -- build ------------------------------------------------------------------------------------


def test_first_release_is_an_orphan_with_the_tagged_tree_minus_exclusions(
    private: Private, tmp_path: Path
) -> None:
    public = public_repository(tmp_path / "public.git")
    snapshot = release_snapshot.build(private.path, "0.1.0", "v0.1.0", public)
    development = run(private.path, "rev-parse", "v0.1.0^{commit}")

    assert run(public, "rev-parse", "main") == snapshot.public_commit
    assert run(public, "log", "--format=%P", "-1", "main") == ""  # no parent
    expected = tree(private.path, development)
    del expected[".github/workflows/cut-release.yml"]
    assert tree(public, "main") == expected
    assert expected["bin/tool"][0] == "100755"
    assert expected["src/link"][0] == "120000"
    assert "docs/with space.md" in expected
    assert snapshot.excluded == (".github/workflows/cut-release.yml",)
    assert ".github/workflows/release.yml" in snapshot.files

    fields = run(public, "log", "-1", "--format=%an <%ae>|%cn <%ce>|%ad|%cd", "--date=raw", "main")
    stamp = run(private.path, "log", "-1", "--format=%cd", "--date=raw", development)
    identity = "OpenFlowsheet release <e.a.j.f.peters@tue.nl>"
    assert fields == f"{identity}|{identity}|{stamp}|{stamp}"
    message = run(public, "log", "-1", "--format=%B", "main")
    assert message == f"OpenFlowsheet v0.1.0\n\nDevelopment commit: {development}"

    assert run(public, "cat-file", "-t", "v0.1.0") == "tag"  # annotated
    assert run(public, "rev-parse", "v0.1.0^{commit}") == snapshot.public_commit
    tag = run(public, "cat-file", "-p", "v0.1.0")
    assert f"tagger {identity} {stamp}" in tag
    assert tag.endswith("OpenFlowsheet v0.1.0")


def test_second_release_has_the_first_as_parent_and_replaces_the_tree(
    private: Private, tmp_path: Path
) -> None:
    public = public_repository(tmp_path / "public.git")
    first = release_snapshot.build(private.path, "0.1.0", "v0.1.0", public)
    private.commit({"src/a.py": "a = 2\n", "src/b.py": "b = 1\n", "docs/with space.md": None})
    run(private.path, "rm", "-q", "src/link")
    run(private.path, "commit", "-q", "-m", "drop link")
    private.commit({}, version="0.2.0")
    private.tag("0.2.0")

    second = release_snapshot.build(private.path, "0.2.0", "v0.2.0", public)

    assert second.parent == first.public_commit
    assert run(public, "log", "--format=%P", "-1", "main") == first.public_commit
    assert run(public, "rev-list", "main").split() == [second.public_commit, first.public_commit]
    expected = tree(private.path, run(private.path, "rev-parse", "v0.2.0^{commit}"))
    del expected[".github/workflows/cut-release.yml"]
    published = tree(public, "main")
    assert published == expected
    assert "docs/with space.md" not in published and "src/link" not in published
    assert "docs/with space.md" in tree(public, "v0.1.0")  # the first release keeps it
    assert run(public, "rev-parse", "v0.1.0^{commit}") == first.public_commit


def test_no_private_commit_or_deleted_file_enters_the_public_repository(
    private: Private, tmp_path: Path
) -> None:
    public = public_repository(tmp_path / "public.git")
    snapshot = release_snapshot.build(private.path, "0.1.0", "v0.1.0", public)

    assert run(public, "rev-list", "--all").split() == [snapshot.public_commit]
    # Every object in the public store belongs to the snapshot: its commit, trees, blobs and tag.
    stored = run(public, "cat-file", "--batch-all-objects", "--batch-check=%(objectname)")
    reachable = run(public, "rev-list", "--all", "--objects").splitlines()
    assert set(stored.split()) == {line.split()[0] for line in reachable} | {snapshot.public_tag}
    for commit in run(private.path, "rev-list", "--all").split():
        present = subprocess.run(["git", "cat-file", "-e", commit], cwd=public, check=False)
        assert present.returncode != 0, f"private commit {commit} is in the public store"
    secret = run(private.path, "rev-parse", "HEAD~2:secret-draft.txt")
    assert subprocess.run(["git", "cat-file", "-e", secret], cwd=public).returncode != 0
    assert run(public, "for-each-ref", "--format=%(refname)").split() == [
        "refs/heads/main",
        "refs/tags/v0.1.0",
    ]


def test_the_same_inputs_give_the_same_commit_and_tag(private: Private, tmp_path: Path) -> None:
    one = release_snapshot.build(
        private.path, "0.1.0", "v0.1.0", public_repository(tmp_path / "one.git")
    )
    two = release_snapshot.build(
        private.path, "0.1.0", "v0.1.0", public_repository(tmp_path / "two.git")
    )
    assert (one.public_commit, one.public_tag) == (two.public_commit, two.public_tag)
    three = release_snapshot.build(
        private.path,
        "0.1.0",
        "v0.1.0",
        public_repository(tmp_path / "three.git"),
        expect_commit=one.public_commit,
    )
    assert three.public_commit == one.public_commit


def test_a_rerun_of_a_published_release_is_a_no_op(private: Private, tmp_path: Path) -> None:
    public = public_repository(tmp_path / "public.git")
    first = release_snapshot.build(private.path, "0.1.0", "v0.1.0", public)
    again = release_snapshot.build(private.path, "0.1.0", "v0.1.0", public)
    assert again.already_published and not first.already_published
    assert (again.public_commit, again.public_tag) == (first.public_commit, first.public_tag)
    assert run(public, "rev-list", "--all").split() == [first.public_commit]
    run(public, "tag", "-d", "v0.1.0")  # rolled back: the tag deleted, main kept
    restored = release_snapshot.build(private.path, "0.1.0", "v0.1.0", public)
    assert run(public, "rev-parse", "v0.1.0") == first.public_tag == restored.public_tag
    run(public, "tag", "-f", "v0.1.0", first.public_commit)  # a lightweight tag instead
    with pytest.raises(RefusalError, match="the public tag v0.1.0 is"):
        release_snapshot.build(private.path, "0.1.0", "v0.1.0", public)


def test_build_refusals(private: Private, tmp_path: Path) -> None:
    public = public_repository(tmp_path / "public.git")
    with pytest.raises(RefusalError, match="declares version '0.1.0', not '0.2.0'"):
        release_snapshot.build(private.path, "0.2.0", "v0.1.0", public)
    with pytest.raises(RefusalError, match="not the expected"):
        release_snapshot.build(private.path, "0.1.0", "v0.1.0", public, expect_commit="0" * 40)
    assert run(public, "for-each-ref") == ""  # a refused build leaves no ref behind
    with pytest.raises(RefusalError, match="not of the form"):
        release_snapshot.build(private.path, "0.1", "v0.1.0", public)
    non_bare = tmp_path / "work"
    run(tmp_path, "init", "-q", str(non_bare))
    with pytest.raises(RefusalError, match="not a bare repository"):
        release_snapshot.build(private.path, "0.1.0", "v0.1.0", non_bare)

    release_snapshot.build(private.path, "0.1.0", "v0.1.0", public)
    private.commit({"src/a.py": "a = 3\n"}, version="0.1.1")
    private.commit({"src/a.py": "a = 4\n"}, version="0.0.9")
    with pytest.raises(RefusalError, match="not newer than the last public release v0.1.0"):
        release_snapshot.build(private.path, "0.0.9", "HEAD", public)
    with pytest.raises(RefusalError, match="differs from this snapshot"):
        release_snapshot.build(private.path, "0.1.0", "HEAD~3", public)  # 0.1.0, not the tag
    with pytest.raises(RefusalError, match="missing"):
        release_snapshot.build(private.path, "0.1.0", "HEAD~4", public)  # before the list


def test_build_refuses_a_public_main_with_foreign_history(private: Private, tmp_path: Path) -> None:
    public = public_repository(tmp_path / "public.git")
    seed = Private(tmp_path / "seed")
    seed.commit({"README.md": "initial commit made on GitHub\n"})
    run(seed.path, "push", "-q", str(public), "main")
    with pytest.raises(RefusalError, match="not a release snapshot"):
        release_snapshot.build(private.path, "0.1.0", "v0.1.0", public)


def test_build_accepts_listed_hand_made_public_commits(private: Private, tmp_path: Path) -> None:
    """A public commit made by hand before the automation (v0.1.0's) counts as a release when the
    tagged commit lists it in `release/public-history.txt`; the next snapshot builds on it."""
    public = public_repository(tmp_path / "public.git")
    hand = Private(tmp_path / "hand")
    hand.commit({"README.md": "the hand-made v0.1.0\n"})
    run(hand.path, "commit", "-q", "--amend", "-m", "OpenFlowsheet v0.1.0 — initial public release")
    initial = run(hand.path, "rev-parse", "HEAD")
    run(hand.path, "push", "-q", str(public), "main")
    private.commit({}, version="0.2.0")
    with pytest.raises(RefusalError, match="not a release snapshot"):
        release_snapshot.build(private.path, "0.2.0", "HEAD", public)

    private.commit({"release/public-history.txt": f"# by hand\n{initial} 0.1.0\n"}, "0.2.0")
    second = release_snapshot.build(private.path, "0.2.0", "HEAD", public)
    assert second.parent == initial
    assert run(public, "rev-list", "main").split() == [second.public_commit, initial]
    private.commit({}, version="0.1.0")
    with pytest.raises(RefusalError, match="not newer than the last public release v0.2.0"):
        release_snapshot.build(private.path, "0.1.0", "HEAD", public)


@pytest.mark.parametrize("line", ["5a35019 0.1.0", f"{'a' * 40} v0.1.0", f"{'a' * 40}", "x y z"])
def test_a_malformed_public_history_is_refused(line: str) -> None:
    with pytest.raises(RefusalError, match="expected"):
        release_snapshot.parse_history(line)


def test_the_repository_public_history_names_the_hand_made_v0_1_0() -> None:
    listing = (REPO_ROOT / release_snapshot.PUBLIC_HISTORY).read_text(encoding="utf-8")
    assert release_snapshot.parse_history(listing) == {
        "5a350199f1334e52cfd789109a0e1dc944ef328c": "0.1.0"
    }


def test_build_refuses_an_existing_public_tag(private: Private, tmp_path: Path) -> None:
    public = public_repository(tmp_path / "public.git")
    first = release_snapshot.build(private.path, "0.1.0", "v0.1.0", public)
    run(public, "tag", "v0.2.0", first.public_commit)
    private.commit({}, version="0.2.0")
    with pytest.raises(RefusalError, match="already has tag v0.2.0"):
        release_snapshot.build(private.path, "0.2.0", "HEAD", public)


def test_build_refuses_a_submodule(private: Private, tmp_path: Path) -> None:
    commit = run(private.path, "rev-parse", "HEAD")
    run(private.path, "update-index", "--add", "--cacheinfo", f"160000,{commit},vendor/sub")
    run(private.path, "commit", "-q", "-m", "submodule")
    public = public_repository(tmp_path / "public.git")
    with pytest.raises(RefusalError, match="submodule"):
        release_snapshot.build(private.path, "0.1.0", "HEAD", public)


def test_the_cli_writes_the_record(private: Private, tmp_path: Path) -> None:
    public = public_repository(tmp_path / "public.git")
    out = tmp_path / "record"
    arguments = ["--repo", str(private.path), "build", "--version", "0.1.0", "--commit", "v0.1.0"]
    assert release_snapshot.main([*arguments, "--public", str(public), "--out", str(out)]) == 0
    files = (out / "files.txt").read_text(encoding="utf-8").splitlines()
    assert files == sorted(tree(public, "main"))
    excluded = (out / "excluded.txt").read_text(encoding="utf-8")
    assert excluded == ".github/workflows/cut-release.yml\n"
    assert release_snapshot.main([*arguments, "--public", str(tmp_path / "absent")]) == 1


# -- the exclusion list -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("patterns", "path", "excluded"),
    [
        (".github/workflows/cut-release.yml", ".github/workflows/cut-release.yml", True),
        (".github/workflows/cut-release.yml", ".github/workflows/release.yml", False),
        (".github/workflows/cut-release.yml", "x/.github/workflows/cut-release.yml", False),
        ("/notes.md", "notes.md", True),
        ("/notes.md", "docs/notes.md", False),
        ("notes.md", "docs/notes.md", True),
        ("private/", "private/a/b.txt", True),
        ("private/", "docs/private/b.txt", True),
        ("private/", "private", False),  # a file named `private`: directories only
        ("/private/", "docs/private/b.txt", False),
        ("*.secret", "a/b/key.secret", True),
        ("*.secret", "a/b/key.secret.txt", False),
        ("docs/*.md", "docs/a.md", True),
        ("docs/*.md", "docs/sub/a.md", False),
        ("docs/**/*.md", "docs/sub/deep/a.md", True),
        ("docs/**/*.md", "docs/a.md", True),
        ("**/transcripts", "a/b/transcripts/x.txt", True),
        ("**/transcripts", "transcripts", True),
        ("evidence/**", "evidence/a/b", True),
        ("evidence/**", "evidence", False),
        ("v1[0-9].txt", "v17.txt", True),
        ("v1[!0-9].txt", "v17.txt", False),
        ("a?c", "abc", True),
        ("a?c", "a/c", False),
        ("# comment\n\nx.txt", "x.txt", True),
    ],
)
def test_exclusion_patterns(patterns: str, path: str, excluded: bool) -> None:
    parsed = release_snapshot.parse_exclusions(patterns)
    assert (release_snapshot.excluded_by(path, parsed) is not None) == excluded


def test_negation_is_refused() -> None:
    with pytest.raises(RefusalError, match="negation"):
        release_snapshot.parse_exclusions("docs/\n!docs/keep.md\n")


def test_the_repository_list_excludes_exactly_the_private_workflow() -> None:
    """At the repository's own tree, the list removes `cut-release.yml` and nothing else; the
    public workflow `release.yml` stays."""
    listing = (REPO_ROOT / release_snapshot.EXCLUDE_LIST).read_text(encoding="utf-8")
    patterns = release_snapshot.parse_exclusions(listing)
    tracked = run(REPO_ROOT, "ls-files").splitlines() + [".github/workflows/cut-release.yml"]
    hits = sorted({p for p in tracked if release_snapshot.excluded_by(p, patterns) is not None})
    assert hits == [".github/workflows/cut-release.yml"]


# -- check ------------------------------------------------------------------------------------


def test_check_passes_when_the_gate_says_yes(private: Private, tmp_path: Path) -> None:
    rc = run(private.path, "rev-parse", "HEAD~1")
    output = release_snapshot.check(private.path, "0.1.0", rc)
    assert "v0.1.0 tag may be proposed: YES" in output
    arguments, pythonpath = (tmp_path / "gate.log").read_text().splitlines()
    assert arguments == f"--rc {rc} --candidate {run(private.path, 'rev-parse', 'HEAD')}"
    assert pythonpath.split(os.pathsep)[0] == "src"


@pytest.mark.parametrize(
    ("line", "status", "reason"),
    [
        ("v0.1.0 tag may be proposed: NO (2 reasons)", "1", "exited 1"),
        ("v0.1.0 tag may be proposed: NO (2 reasons)", "0", "did not print"),
        ("v0.1.0 tag may be proposed: YES", "2", "exited 2"),
        ("tag may be proposed: YES", "0", "did not print"),
    ],
)
def test_check_refuses_unless_the_gate_exits_0_and_says_yes(
    private: Private, monkeypatch: pytest.MonkeyPatch, line: str, status: str, reason: str
) -> None:
    monkeypatch.setenv("FAKE_GATE_LINE", line)
    monkeypatch.setenv("FAKE_GATE_EXIT", status)
    with pytest.raises(RefusalError, match=reason):
        release_snapshot.check(private.path, "0.1.0", "HEAD~1")


def test_check_refusals(private: Private, monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(RefusalError, match="declares version '0.1.0', not '0.1.1'"):
        release_snapshot.check(private.path, "0.1.1", "HEAD~1")
    with pytest.raises(RefusalError, match="not of the form"):
        release_snapshot.check(private.path, "v0.1.0", "HEAD~1")
    with pytest.raises(RefusalError, match="not a commit"):
        release_snapshot.check(private.path, "0.1.0", "no-such-commit")
    with pytest.raises(RefusalError, match="check out"):
        release_snapshot.check(private.path, "0.1.0", "HEAD~1", commit="HEAD~1")
    (private.path / "src" / "a.py").write_text("a = 99\n", encoding="utf-8")
    with pytest.raises(RefusalError, match="modified tracked files"):
        release_snapshot.check(private.path, "0.1.0", "HEAD~1")
    run(private.path, "checkout", "-q", "--", "src/a.py")
    # The gate's version line names the version asked for: 0.1.1 with a gate printing v0.1.0.
    private.commit({}, version="0.1.1")
    with pytest.raises(RefusalError, match="did not print 'v0.1.1 tag may be proposed: YES'"):
        release_snapshot.check(private.path, "0.1.1", "HEAD~1")
    # A tag that exists must point at the commit.
    private.commit({"src/a.py": "a = 5\n"}, version="0.1.0")
    with pytest.raises(RefusalError, match="tag v0.1.0 exists"):
        release_snapshot.check(private.path, "0.1.0", "HEAD~1")


def test_check_refuses_without_a_gate_for_the_minor_line(private: Private) -> None:
    private.commit({}, version="0.2.0")
    with pytest.raises(RefusalError, match="no gate script scripts/v0_2_gate.py"):
        release_snapshot.check(private.path, "0.2.0", "HEAD~1")


def test_check_cli_exit_status(private: Private, monkeypatch: pytest.MonkeyPatch) -> None:
    arguments = ["--repo", str(private.path), "check", "--version", "0.1.0", "--rc", "HEAD~1"]
    assert release_snapshot.main(arguments) == 0
    monkeypatch.setenv("FAKE_GATE_EXIT", "1")
    assert release_snapshot.main(arguments) == 1


# -- verify-tag -------------------------------------------------------------------------------


def test_verify_tag(private: Private) -> None:
    assert release_snapshot.verify_tag(private.path, "v0.1.0") == "0.1.0"
    for wrong in ("v0.1.1", "0.1.0", "v0.1.0-rc1"):
        with pytest.raises(RefusalError, match="does not name"):
            release_snapshot.verify_tag(private.path, wrong)


def test_verify_tag_at_the_repository() -> None:
    version = release_snapshot.version_at(REPO_ROOT, "HEAD")
    assert release_snapshot.verify_tag(REPO_ROOT, f"v{version}") == version


# -- changelog_section ------------------------------------------------------------------------

CHANGELOG = """# Changelog

## v0.2.0 — 2027-01-01

Second.

### Details

More.

## v0.1.0rc1 — a candidate

Candidate.

## v0.1.0 — the first

First.

## v0.0.9

"""


def test_changelog_section_is_the_body_up_to_the_next_level_2_heading() -> None:
    assert changelog_section.section(CHANGELOG, "v0.2.0") == "Second.\n\n### Details\n\nMore.\n"
    assert changelog_section.section(CHANGELOG, "v0.1.0") == "First.\n"


def test_changelog_section_refusals() -> None:
    with pytest.raises(changelog_section.MissingSectionError, match="0 sections"):
        changelog_section.section(CHANGELOG, "v0.3.0")
    with pytest.raises(changelog_section.MissingSectionError, match="empty"):
        changelog_section.section(CHANGELOG, "v0.0.9")
    with pytest.raises(changelog_section.MissingSectionError, match="2 sections"):
        changelog_section.section(CHANGELOG + "## v0.1.0\n\nAgain.\n", "v0.1.0")
    with pytest.raises(ValueError, match="vX.Y.Z"):
        changelog_section.section(CHANGELOG, "0.1.0")


def test_changelog_section_of_the_repository() -> None:
    """The v0.1.0 notes are the repository changelog's own section, starting with ADR 0021 D4's
    italic preamble and stopping before v0.0.0."""
    text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    notes = changelog_section.section(text, "v0.1.0")
    assert notes.startswith("*ADR 0021 D4.")
    assert "## v0.0.0" not in notes and "## v0.1.0" not in notes
    assert notes.strip() in text
