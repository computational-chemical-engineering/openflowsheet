"""Release automation: the gate check, the public snapshot, and the publish job's tag check.

Frank's decision of 2026-10-03 (`docs/RELEASING.md`): releases are made by two GitHub workflows.
The private repository `openflowsheet-dev` holds the full history; its dispatch-only
`.github/workflows/cut-release.yml` runs `check` and `build` and pushes. The public repository
`openflowsheet` receives one squashed commit per release, with no development history; its
tag-triggered `.github/workflows/release.yml` runs `verify-tag` before it builds and publishes.
Every refusal is exit status 1 with a `refused:` line on stderr; the workflows stop on it.

**`check`** — may this commit be released as this version? The gate script of the version's
minor line (`scripts/v<major>_<minor>_gate.py`) reads the working tree, so the checkout's `HEAD`
must be the commit and its tracked files unmodified. Refused unless: the version is `X.Y.Z`;
`pyproject.toml` at the commit declares it; a tag `vX.Y.Z` that already exists points at the
commit; and the gate, run as `<gate> --rc <C> --candidate <commit>`, exits 0 *and* prints the
line `vX.Y.Z tag may be proposed: YES`.

**`build`** — the snapshot. In a bare clone of the public repository (possibly empty), one commit
on `main` whose tree is exactly the tagged commit's tree minus the paths matched by the tagged
commit's `release/public-exclude.txt` (a subset of gitignore syntax, see `parse_exclusions`), whose
only parent is the previous release snapshot (none for the first), with the fixed author and
committer `RELEASE_IDENTITY`, both dated with the tagged commit's committer date, and the message
`OpenFlowsheet vX.Y.Z` plus a line naming the development commit; and the annotated tag `vX.Y.Z`
on it, by the same identity at the same date. The same inputs give the same commit and tag ids.
Only the snapshot's blobs are copied from the private repository; `git fast-import` writes its
commit and trees anew, so no private commit can enter the public one. Every commit on public
`main` must already be a release snapshot, or one listed in the tagged commit's
`release/public-history.txt` (made by hand before this automation), or the build is refused.
Also refused: a version not newer than the last release; a public tag `vX.Y.Z` that exists; a
tree with a submodule; a version that `pyproject.toml` at the commit does not declare; and, with
`--expect-commit`, a snapshot whose id differs (the workflow's release job rebuilds what its
dry-run job built and must get the same id). Re-running
a build whose snapshot is already the tip of public `main` is a no-op that reports it (and
re-creates its tag if the tag was deleted). Only refs of the public clone change (`main`, the
tag); nothing is pushed. `--exclude-list FILE` replaces the commit's own list (a local dry run
of a commit that predates it).

**`verify-tag`** — the publish job's first step: the pushed tag must be `v` + `pyproject.toml`'s
version.

    python scripts/release_snapshot.py check --version 0.1.0 --rc <C>
    python scripts/release_snapshot.py build --version 0.1.0 --commit v0.1.0 \\
        --public "$RUNNER_TEMP/public.git" --out "$RUNNER_TEMP/snapshot"
    python scripts/release_snapshot.py verify-tag --tag "$GITHUB_REF_NAME"
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parent.parent
#: The author, committer and tagger of every public release snapshot.
RELEASE_NAME: Final = "OpenFlowsheet release"
RELEASE_EMAIL: Final = "e.a.j.f.peters@tue.nl"
RELEASE_IDENTITY: Final = f"{RELEASE_NAME} <{RELEASE_EMAIL}>"
#: The tagged commit's list of paths the public snapshot omits.
EXCLUDE_LIST: Final = "release/public-exclude.txt"
#: The tagged commit's list of public commits made before this automation that count as release
#: snapshots: `<commit id> <version>` per line.
PUBLIC_HISTORY: Final = "release/public-history.txt"
BRANCH: Final = "main"
VERSION: Final = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")
SUBJECT: Final = re.compile(r"OpenFlowsheet v((?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*))")
#: The ref `git fast-import` writes the candidate snapshot to before it is checked; removed after.
SCRATCH_REF: Final = "refs/openflowsheet-release/candidate"
ZERO: Final = "0" * 40
GITLINK: Final = "160000"


class RefusalError(Exception):
    """The release may not proceed; the message says why."""


def git(repo: Path, *arguments: str, data: bytes | None = None) -> bytes:
    completed = subprocess.run(
        ["git", *arguments], cwd=repo, input=data, capture_output=True, check=False
    )
    if completed.returncode != 0:
        raise RefusalError(
            f"git {' '.join(arguments)} failed in {repo}: "
            + completed.stderr.decode("utf-8", "replace").strip()
        )
    return completed.stdout


def text(repo: Path, *arguments: str) -> str:
    return git(repo, *arguments).decode("utf-8").strip()


def resolve(repo: Path, name: str) -> str | None:
    """The object `name` names, or None."""
    completed = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", name], cwd=repo, capture_output=True
    )
    return completed.stdout.decode().strip() if completed.returncode == 0 else None


def commit_of(repo: Path, name: str) -> str:
    found = resolve(repo, f"{name}^{{commit}}")
    if found is None:
        raise RefusalError(f"{name!r} is not a commit in {repo}")
    return found


def require_version(version: str) -> tuple[int, int, int]:
    match = VERSION.fullmatch(version)
    if match is None:
        raise RefusalError(f"version {version!r} is not of the form X.Y.Z")
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


def version_at(repo: Path, commit: str) -> str:
    document = tomllib.loads(text(repo, "show", f"{commit}:pyproject.toml"))
    return str(document["project"]["version"])


def require_declared(repo: Path, commit: str, version: str) -> None:
    declared = version_at(repo, commit)
    if declared != version:
        raise RefusalError(
            f"pyproject.toml at {commit[:12]} declares version {declared!r}, not {version!r}"
        )


# -- check ------------------------------------------------------------------------------------


def gate_script(repo: Path, version: str) -> Path:
    major, minor, _ = require_version(version)
    return repo / "scripts" / f"v{major}_{minor}_gate.py"


def check(repo: Path, version: str, rc: str, commit: str = "HEAD") -> str:
    """Refuse unless `commit` may be released as `version`; return the gate's output."""
    require_version(version)
    target = commit_of(repo, commit)
    head = commit_of(repo, "HEAD")
    if head != target:
        raise RefusalError(
            f"the gate reads the working tree, whose HEAD is {head[:12]}: "
            f"check out {target[:12]} first"
        )
    if text(repo, "status", "--porcelain", "--untracked-files=no"):
        raise RefusalError("the working tree has modified tracked files; the gate would read them")
    rc_commit = commit_of(repo, rc)
    require_declared(repo, target, version)
    tag = f"refs/tags/v{version}"
    if resolve(repo, tag) is not None and commit_of(repo, tag) != target:
        raise RefusalError(f"tag v{version} exists and points at {commit_of(repo, tag)[:12]}")
    gate = gate_script(repo, version)
    if not gate.is_file():
        raise RefusalError(f"no gate script {gate.relative_to(repo)} for version {version}")
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in ("src", environment.get("PYTHONPATH", "")) if part
    )
    completed = subprocess.run(
        [sys.executable, str(gate), "--rc", rc_commit, "--candidate", target],
        cwd=repo,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    output = completed.stdout + completed.stderr
    expected = f"v{version} tag may be proposed: YES"
    if completed.returncode != 0:
        raise RefusalError(f"the gate exited {completed.returncode}:\n{output}")
    if expected not in completed.stdout.splitlines():
        raise RefusalError(f"the gate exited 0 but did not print {expected!r}:\n{output}")
    return output


# -- the exclusion list -----------------------------------------------------------------------


@dataclass(frozen=True)
class Pattern:
    """One line of the exclusion list. `anchored`: matched against the path from the root (the
    pattern has a `/` before its end); otherwise against each path component's name."""

    text: str
    regex: re.Pattern[str]
    anchored: bool
    directory_only: bool


def translate(glob: str) -> str:
    """A gitignore glob as a regular expression: `*` and `?` stop at `/`; `**/` at the start or
    after `/` matches any number of directories; a trailing `/**` everything inside; `[...]` a
    class (`[!...]` negated); a backslash quotes the next character."""
    out: list[str] = []
    i = 0
    while i < len(glob):
        if glob.startswith("**/", i) and (i == 0 or glob[i - 1] == "/"):
            out.append("(?:.*/)?")
            i += 3
        elif glob[i:] == "/**":
            out.append("/.*")
            i += 3
        elif glob[i] == "*":
            while i < len(glob) and glob[i] == "*":
                i += 1
            out.append("[^/]*")
        elif glob[i] == "?":
            out.append("[^/]")
            i += 1
        elif glob[i] == "[":
            # A `]` right after `[` or `[!` is a member, not the end of the class.
            start = i + 2 if glob.startswith("[!", i) else i + 1
            end = glob.find("]", start + 1 if glob.startswith("]", start) else start)
            if end == -1:
                out.append(re.escape("["))
                i += 1
                continue
            body = glob[i + 1 : end]
            if body.startswith("!"):
                body = "^" + body[1:]
            out.append("[" + body.replace("\\", "\\\\") + "]")
            i = end + 1
        elif glob[i] == "\\" and i + 1 < len(glob):
            out.append(re.escape(glob[i + 1]))
            i += 2
        else:
            out.append(re.escape(glob[i]))
            i += 1
    return "".join(out)


def parse_exclusions(listing: str) -> list[Pattern]:
    """The exclusion list: one gitignore pattern per line; blank lines and `#` comments skipped;
    a trailing `/` matches directories only; a leading `/` anchors. Negation (`!`) is refused
    rather than half-supported."""
    patterns: list[Pattern] = []
    for number, raw in enumerate(listing.splitlines(), 1):
        line = raw.rstrip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("!"):
            raise RefusalError(f"{EXCLUDE_LIST}:{number}: negation ({line!r}) is not supported")
        directory_only = line.endswith("/")
        glob = line.rstrip("/")
        anchored = "/" in glob
        glob = glob.lstrip("/")
        if not glob:
            raise RefusalError(f"{EXCLUDE_LIST}:{number}: {raw!r} matches everything")
        patterns.append(Pattern(line, re.compile(translate(glob)), anchored, directory_only))
    return patterns


def excluded_by(path: str, patterns: Sequence[Pattern]) -> Pattern | None:
    """The first pattern that excludes `path` (a file) or one of its leading directories."""
    parts = path.split("/")
    for depth in range(1, len(parts) + 1):
        is_directory = depth < len(parts)
        prefix = "/".join(parts[:depth])
        for pattern in patterns:
            if pattern.directory_only and not is_directory:
                continue
            subject = prefix if pattern.anchored else parts[depth - 1]
            if pattern.regex.fullmatch(subject):
                return pattern
    return None


# -- build ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Entry:
    mode: str
    blob: str
    path: str


@dataclass(frozen=True)
class Release:
    """One commit of public `main`, which must be a release snapshot."""

    commit: str
    parent: str | None
    version: str


@dataclass(frozen=True)
class Snapshot:
    version: str
    development_commit: str
    public_commit: str
    public_tag: str
    parent: str | None
    date: str
    files: tuple[str, ...]
    excluded: tuple[str, ...]
    patterns: tuple[str, ...]
    already_published: bool

    def record(self) -> dict[str, object]:
        return {
            "version": self.version,
            "tag": f"v{self.version}",
            "development_commit": self.development_commit,
            "public_commit": self.public_commit,
            "public_tag_object": self.public_tag,
            "parent": self.parent,
            "date": self.date,
            "identity": RELEASE_IDENTITY,
            "file_count": len(self.files),
            "excluded": list(self.excluded),
            "exclusion_patterns": list(self.patterns),
            "already_published": self.already_published,
        }


def tree_entries(repo: Path, commit: str) -> list[Entry]:
    listing = git(repo, "ls-tree", "-r", "-z", "--full-tree", commit)
    entries: list[Entry] = []
    for item in listing.split(b"\0"):
        if not item:
            continue
        meta, path = item.split(b"\t", 1)
        mode, _, blob = meta.decode().split()
        entries.append(Entry(mode, blob, path.decode("utf-8", "surrogateescape")))
    return entries


def parse_history(listing: str) -> dict[str, str]:
    """`PUBLIC_HISTORY`: commit id to version, for public commits made by hand before this
    automation; blank lines and `#` comments skipped."""
    accepted: dict[str, str] = {}
    for number, raw in enumerate(listing.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if (
            len(fields) != 2
            or re.fullmatch(r"[0-9a-f]{40}", fields[0]) is None
            or VERSION.fullmatch(fields[1]) is None
        ):
            raise RefusalError(f"{PUBLIC_HISTORY}:{number}: expected `<commit id> X.Y.Z`: {raw!r}")
        accepted[fields[0]] = fields[1]
    return accepted


def history(public: Path, tip: str | None, accepted: dict[str, str] | None = None) -> list[Release]:
    """Public `main`, newest first; refused unless every commit is a release snapshot (the fixed
    identity, the subject `OpenFlowsheet vX.Y.Z`, at most one parent, versions increasing) or one
    of the `accepted` earlier commits (`PUBLIC_HISTORY`), whose version the list gives."""
    if tip is None:
        return []
    accepted = accepted or {}
    log = git(public, "log", "-z", "--format=%H%n%P%n%an <%ae>%n%cn <%ce>%n%s", tip)
    releases: list[Release] = []
    for record in log.decode("utf-8", "replace").split("\0"):
        if not record.strip():
            continue
        commit, parents, author, committer, subject = record.strip("\n").split("\n", 4)
        match = SUBJECT.fullmatch(subject)
        if commit in accepted and len(parents.split()) <= 1:
            releases.append(Release(commit, parents or None, accepted[commit]))
            continue
        if (
            len(parents.split()) > 1
            or author != RELEASE_IDENTITY
            or committer != RELEASE_IDENTITY
            or match is None
        ):
            raise RefusalError(
                f"public {BRANCH} holds {commit[:12]} ({subject!r} by {author}), which is not a "
                "release snapshot; the public repository must hold release snapshots only"
            )
        releases.append(Release(commit, parents or None, match.group(1)))
    for newer, older in zip(releases, releases[1:], strict=False):
        if require_version(newer.version) <= require_version(older.version):
            raise RefusalError(f"public {BRANCH}'s versions do not increase at {newer.commit[:12]}")
    return releases


def quote(path: str) -> bytes:
    """A path as `git fast-import` reads it: C-quoted when it would otherwise be ambiguous."""
    raw = path.encode("utf-8", "surrogateescape")
    if raw.startswith(b'"') or b"\n" in raw:
        return (
            b'"' + raw.replace(b"\\", b"\\\\").replace(b'"', b'\\"').replace(b"\n", b"\\n") + b'"'
        )
    return raw


def import_snapshot(
    repo: Path, public: Path, entries: Sequence[Entry], parent: str | None, stamp: str, message: str
) -> str:
    """Write the snapshot commit into `public` with `git fast-import` (to `SCRATCH_REF`), copying
    each blob from `repo`; return its id. Only blobs cross: the commit and its trees are new."""
    body = message.encode("utf-8")
    header = (
        f"reset {SCRATCH_REF}\ncommit {SCRATCH_REF}\n"
        f"author {RELEASE_IDENTITY} {stamp}\ncommitter {RELEASE_IDENTITY} {stamp}\n"
        f"data {len(body)}\n"
    ).encode()
    with (
        subprocess.Popen(
            ["git", "cat-file", "--batch"], cwd=repo, stdin=subprocess.PIPE, stdout=subprocess.PIPE
        ) as reader,
        subprocess.Popen(
            ["git", "fast-import", "--quiet", "--done", "--force", "--date-format=raw"],
            cwd=public,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ) as writer,
    ):
        assert reader.stdin and reader.stdout and writer.stdin
        try:
            writer.stdin.write(header + body + b"\n")
            if parent is not None:
                writer.stdin.write(f"from {parent}\n".encode())
            writer.stdin.write(b"deleteall\n")
            for entry in entries:
                reader.stdin.write(f"{entry.blob}\n".encode())
                reader.stdin.flush()
                answer = reader.stdout.readline().split()
                if len(answer) != 3 or answer[:2] != [entry.blob.encode(), b"blob"]:
                    raise RefusalError(f"{entry.path}: blob {entry.blob} not readable: {answer!r}")
                content = reader.stdout.read(int(answer[2]))
                reader.stdout.read(1)
                path = quote(entry.path)
                writer.stdin.write(b"M " + entry.mode.encode() + b" inline " + path + b"\n")
                writer.stdin.write(f"data {len(content)}\n".encode() + content + b"\n")
            writer.stdin.write(b"done\n")
        except BaseException:
            reader.kill()
            writer.kill()
            raise
        reader.stdin.close()
        _, errors = writer.communicate()
    if writer.returncode != 0:
        raise RefusalError("git fast-import failed: " + errors.decode("utf-8", "replace"))
    return commit_of(public, SCRATCH_REF)


def make_tag(public: Path, commit: str, version: str, stamp: str) -> str:
    """The annotated tag object `vX.Y.Z` on `commit`, written with `git mktag` (deterministic)."""
    body = (
        f"object {commit}\ntype commit\ntag v{version}\ntagger {RELEASE_IDENTITY} {stamp}\n\n"
        f"OpenFlowsheet v{version}\n"
    )
    return git(public, "mktag", data=body.encode()).decode().strip()


def verify_snapshot(
    public: Path, commit: str, entries: Sequence[Entry], parent: str | None
) -> None:
    """The written commit's tree is exactly `entries` and its only parent is `parent`."""
    written = {(e.mode, e.blob, e.path) for e in tree_entries(public, commit)}
    wanted = {(e.mode, e.blob, e.path) for e in entries}
    if written != wanted:
        raise RefusalError(
            f"the snapshot's tree differs from the tagged tree minus exclusions in "
            f"{len(written ^ wanted)} entries"
        )
    parents = text(public, "log", "-1", "--format=%P", commit).split()
    if parents != ([parent] if parent else []):
        raise RefusalError(f"the snapshot's parents are {parents}, not {parent}")


def build(
    repo: Path,
    version: str,
    commit: str,
    public: Path,
    expect_commit: str | None = None,
    exclude_list: str | None = None,
) -> Snapshot:
    """Write the public snapshot of `commit` as `version` into the bare clone `public`. The
    exclusion list is the commit's own unless `exclude_list` (its text) replaces it."""
    require_version(version)
    target = commit_of(repo, commit)
    if not public.is_dir() or text(public, "rev-parse", "--is-bare-repository") != "true":
        raise RefusalError(f"{public} is not a bare repository (clone it with `git clone --bare`)")
    require_declared(repo, target, version)
    if exclude_list is None:
        listing = resolve(repo, f"{target}:{EXCLUDE_LIST}")
        if listing is None:
            raise RefusalError(f"{EXCLUDE_LIST} is missing at {target[:12]}")
        exclude_list = git(repo, "cat-file", "blob", listing).decode("utf-8")
    patterns = parse_exclusions(exclude_list)
    included: list[Entry] = []
    excluded: list[str] = []
    for entry in tree_entries(repo, target):
        if excluded_by(entry.path, patterns) is not None:
            excluded.append(entry.path)
        elif entry.mode == GITLINK:
            raise RefusalError(f"{entry.path} is a submodule; a snapshot cannot carry one")
        else:
            included.append(entry)
    stamp = text(repo, "log", "-1", "--format=%cd", "--date=raw", target)
    message = f"OpenFlowsheet v{version}\n\nDevelopment commit: {target}\n"
    tag_ref = f"refs/tags/v{version}"
    tip = resolve(public, f"refs/heads/{BRANCH}")
    known = resolve(repo, f"{target}:{PUBLIC_HISTORY}")
    accepted = {} if known is None else parse_history(text(repo, "cat-file", "blob", known))
    releases = history(public, tip, accepted)
    existing_tag = resolve(public, tag_ref)
    rerun = bool(releases) and releases[0].version == version
    if rerun:
        parent = releases[0].parent
    else:
        if existing_tag is not None:
            raise RefusalError(f"the public repository already has tag v{version}")
        if releases and require_version(version) <= require_version(releases[0].version):
            raise RefusalError(
                f"v{version} is not newer than the last public release v{releases[0].version}"
            )
        parent = tip
    try:
        candidate = import_snapshot(repo, public, included, parent, stamp, message)
        verify_snapshot(public, candidate, included, parent)
    finally:
        subprocess.run(["git", "update-ref", "-d", SCRATCH_REF], cwd=public, capture_output=True)
    if expect_commit is not None and candidate != expect_commit:
        raise RefusalError(f"the snapshot is {candidate}, not the expected {expect_commit}")
    tag = make_tag(public, candidate, version, stamp)
    if rerun:
        if candidate != tip:
            raise RefusalError(
                f"public {BRANCH} already holds v{version} as {releases[0].commit[:12]}, "
                f"which differs from this snapshot {candidate[:12]}"
            )
        if existing_tag is None:  # the tag was deleted (docs/RELEASING.md, rolling back)
            git(public, "update-ref", tag_ref, tag, ZERO)
        elif existing_tag != tag:
            raise RefusalError(f"the public tag v{version} is {existing_tag}, not {tag}")
    else:
        git(public, "update-ref", f"refs/heads/{BRANCH}", candidate, tip or ZERO)
        git(public, "update-ref", tag_ref, tag, ZERO)
    return Snapshot(
        version=version,
        development_commit=target,
        public_commit=candidate,
        public_tag=tag,
        parent=parent,
        date=stamp,
        files=tuple(entry.path for entry in included),
        excluded=tuple(excluded),
        patterns=tuple(pattern.text for pattern in patterns),
        already_published=rerun,
    )


def write_record(snapshot: Snapshot, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "files.txt").write_text("".join(f"{path}\n" for path in snapshot.files), "utf-8")
    (out / "excluded.txt").write_text("".join(f"{path}\n" for path in snapshot.excluded), "utf-8")
    (out / "snapshot.json").write_text(
        json.dumps(snapshot.record(), indent=1, sort_keys=True) + "\n", "utf-8"
    )


# -- verify-tag -------------------------------------------------------------------------------


def verify_tag(repo: Path, tag: str) -> str:
    """Refuse unless `tag` is `v` + the version `pyproject.toml` at `HEAD` declares."""
    declared = version_at(repo, "HEAD")
    require_version(declared)
    if tag != f"v{declared}":
        raise RefusalError(f"tag {tag!r} does not name pyproject.toml's version {declared!r}")
    return declared


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, default=ROOT, help="the checkout (default: this one)")
    commands = parser.add_subparsers(dest="command", required=True)
    checking = commands.add_parser("check", help="the release gate at the checked-out commit")
    checking.add_argument("--version", required=True)
    checking.add_argument("--rc", required=True, help="the release candidate C")
    checking.add_argument("--commit", default="HEAD")
    building = commands.add_parser("build", help="the public snapshot of a tagged commit")
    building.add_argument("--version", required=True)
    building.add_argument("--commit", required=True, help="the tagged development commit")
    building.add_argument("--public", type=Path, required=True, help="a bare public clone")
    building.add_argument("--out", type=Path, default=None, help="where to write the record")
    building.add_argument("--expect-commit", default=None)
    building.add_argument(
        "--exclude-list",
        type=Path,
        default=None,
        help=f"replaces the commit's own {EXCLUDE_LIST} (a local dry run of an older commit)",
    )
    tagging = commands.add_parser("verify-tag", help="the tag names the package version")
    tagging.add_argument("--tag", required=True)
    arguments = parser.parse_args(argv)

    repo: Path = arguments.repo.resolve()
    try:
        if arguments.command == "check":
            print(check(repo, arguments.version, arguments.rc, arguments.commit), end="")
            print(f"check: v{arguments.version} may be released from {arguments.commit}")
        elif arguments.command == "build":
            snapshot = build(
                repo,
                arguments.version,
                arguments.commit,
                arguments.public.resolve(),
                arguments.expect_commit,
                None
                if arguments.exclude_list is None
                else arguments.exclude_list.read_text(encoding="utf-8"),
            )
            if arguments.out is not None:
                write_record(snapshot, arguments.out)
            state = "already published" if snapshot.already_published else "written"
            print(
                f"snapshot v{snapshot.version} {state}: commit {snapshot.public_commit}, "
                f"tag object {snapshot.public_tag}, parent {snapshot.parent or 'none'}, "
                f"{len(snapshot.files)} files, {len(snapshot.excluded)} excluded "
                f"({', '.join(snapshot.excluded) or 'none'})"
            )
        else:
            print(f"tag {arguments.tag} names version {verify_tag(repo, arguments.tag)}")
    except RefusalError as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
