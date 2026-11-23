"""`README.md` is the PyPI project page, and it stays current (V03-post1; Frank, 2026-10-31).

PyPI renders `README.md` as the long description and resolves no relative link, so every link and
image in it is absolute (`https://`). Its status names the release the version belongs to: at a
release version (`X.Y.Z`, `X.Y.Z{a|b|rc}N`) that version, at a post-release `X.Y.Z.postN` its
release `X.Y.Z` and the post-release itself (R-922), and at a `.devN` version between releases the
newest released version (`RELEASED`, `tests/test_v02_main_version.py`). The status table's
first row is `Released in <that release>` (a post-release's base) and the quickstart downloads
from its tag (REL051). The cut commit of every release updates the whole section
(`docs/RELEASING.md`). `[project.urls]`, the links in PyPI's sidebar, has the six keys
below, every one an `https://` URL. Each check has a negative control.

MSG-G9 (FB-01): the Python quickstart runs twice in one directory, with the change set copied
there — both runs print `CONVERGED VERIFIED`, and the second opens the project the first made.
"""

from __future__ import annotations

import contextlib
import io
import re
import shutil
import tomllib
from collections.abc import Iterable, Mapping
from pathlib import Path

import pytest
from conftest import REPO_ROOT
from packaging.version import Version
from test_v02_main_version import RELEASED

README = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
PROJECT = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
VERSION = str(PROJECT["version"])
#: `[project.urls]`'s keys, in PyPI's well-known labels.
URL_KEYS = ("Homepage", "Documentation", "Repository", "Issues", "Changelog", "Release notes")

#: Inline links and images `[text](target)`, `![alt](target)`; reference definitions
#: `[label]: target`; HTML `href`/`src`. Autolinks `<https://…>` are absolute by construction.
_INLINE = re.compile(r"!?\[(?:[^\[\]]|\[[^\]]*\])*\]\(\s*<?([^)\s>]*)")
_REFERENCE = re.compile(r"^ {0,3}\[[^\]]+\]:\s*<?(\S+?)>?(?:\s|$)", re.MULTILINE)
_HTML = re.compile(r"""(?:href|src)\s*=\s*["']([^"']*)["']""", re.IGNORECASE)
_FENCE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)


def relative_links(text: str) -> list[str]:
    """Every link or image target in `text`, outside code fences, that is not `https://`."""
    prose = _FENCE.sub("", text)
    targets = [
        *_INLINE.findall(prose),
        *_REFERENCE.findall(prose),
        *_HTML.findall(prose),
    ]
    return [target for target in targets if not target.startswith("https://")]


def named_release(version: str, released: Iterable[str]) -> tuple[str, ...]:
    """The strings the status must carry at `version`."""
    parsed = Version(version)
    if parsed.is_devrelease:
        newest = max(released, key=Version)
        if Version(newest).is_postrelease:
            return named_release(newest, released)
        return (f"Version {newest} is released",)
    if parsed.is_postrelease:
        return (f"Version {parsed.base_version} is released", f"`{version}`")
    return (f"Version {version} is released",)


def status_problems(text: str, version: str, released: Iterable[str]) -> list[str]:
    match = re.search(r"^## Status\n(.*?)(?=^## )", text, re.MULTILINE | re.DOTALL)
    if match is None:
        return ["README.md has no `## Status` section"]
    return [
        f"README.md's status does not name {phrase!r}"
        for phrase in named_release(version, released)
        if phrase not in match[1]
    ]


def page_release(version: str, released: Iterable[str]) -> str:
    """The release the page describes at `version`.

    A release version itself, a post-release's base, a `.devN`'s newest release.
    """
    parsed = Version(version)
    if parsed.is_devrelease:
        return page_release(max(released, key=Version), released)
    if parsed.is_postrelease:
        return parsed.base_version
    return version


#: The quickstart's raw download URLs, one per tag they name.
_RAW_TAG = re.compile(
    r"https://raw\.githubusercontent\.com/computational-chemical-engineering/openflowsheet/([^/\s]+)/"
)


def release_row_problems(text: str, version: str, released: Iterable[str]) -> list[str]:
    """The status table's first row names the release; every quickstart download, its tag."""
    release = page_release(version, released)
    problems = []
    match = re.search(r"^## Status\n(.*?)(?=^## )", text, re.MULTILINE | re.DOTALL)
    rows = re.findall(r"^\| ([^|]+?) \|", match[1] if match else "", re.MULTILINE)
    rows = [row for row in rows if row.strip() and set(row.strip()) != {"-"}]
    if not rows or rows[0] != f"Released in {release}":
        problems.append(f"the status table's first row is not 'Released in {release}': {rows[:1]}")
    tags = _RAW_TAG.findall(text)
    if not tags:
        problems.append("the quickstart downloads nothing from a tag")
    problems += [
        f"the quickstart downloads from {tag!r}, not 'v{release}'"
        for tag in tags
        if tag != f"v{release}"
    ]
    return problems


def url_problems(urls: Mapping[str, str] | None) -> list[str]:
    if not urls:
        return ["pyproject.toml has no [project.urls]"]
    problems = [f"[project.urls] lacks {key!r}" for key in URL_KEYS if key not in urls]
    problems += [
        f"[project.urls] {k!r} is not https: {v!r}"
        for k, v in urls.items()
        if not str(v).startswith("https://")
    ]
    return problems


def test_readme_has_no_relative_link_or_image() -> None:
    assert relative_links(README) == []


@pytest.mark.parametrize(
    "line",
    [
        "See [the docs](docs/index.md).",
        "![logo](images/logo.png)",
        "[spec]: docs/spec.md",
        '<img src="logo.svg">',
        '<a href="#status">status</a>',
        "[anchor](#status)",
        "[insecure](http://example.org/)",
        "[nested [brackets]](CHANGELOG.md)",
    ],
)
def test_relative_links_control(line: str) -> None:
    assert relative_links(f"# T\n\n{line}\n") != []
    assert relative_links(f"# T\n\n```\n{line}\n```\n") == []


def test_absolute_links_pass_the_control() -> None:
    text = "[a](https://x.org/a) ![b](https://x.org/b.png) <https://x.org/>\n[c]: https://x.org/c\n"
    assert relative_links(text) == []


def test_readme_status_names_the_release() -> None:
    assert status_problems(README, VERSION, RELEASED) == []


@pytest.mark.parametrize(
    ("version", "status", "named"),
    [
        ("0.3.0", "Version 0.3.0 is released.", True),
        ("0.3.0", "Version 0.2.0 is released.", False),
        ("0.4.0rc1", "Version 0.4.0rc1 is released.", True),
        ("0.4.0rc1", "Version 0.4.0 is released.", False),
        ("0.3.0.post1", "Version 0.3.0 is released; `0.3.0.post1` updates the page.", True),
        ("0.3.0.post1", "Version 0.3.0 is released.", False),
        ("0.3.0.post1", "Version 0.3.0.post1 is released; `0.3.0.post1`.", False),
        ("0.4.0.dev0", "Version 0.2.0 is released.", True),
        ("0.4.0.dev0", "Version 0.2.0a1 is released.", False),
        ("0.4.0.dev0", "Version 0.4.0.dev0 is released.", False),
    ],
)
def test_status_control(version: str, status: str, named: bool) -> None:
    text = f"# T\n\n## Status\n\n{status}\n\n## Next\n"
    assert (status_problems(text, version, ("0.2.0a1", "0.2.0")) == []) is named
    assert status_problems("# T\n\nVersion 0.3.0 is released.\n", version, RELEASED) != []


def test_readme_table_and_quickstart_name_the_release() -> None:
    assert release_row_problems(README, VERSION, RELEASED) == []


_RAW = "https://raw.githubusercontent.com/computational-chemical-engineering/openflowsheet"


@pytest.mark.parametrize(
    ("version", "row", "tag", "named"),
    [
        ("0.5.1", "Released in 0.5.1", "v0.5.1", True),
        ("0.5.1", "Released in 0.5.0", "v0.5.1", False),
        ("0.5.1", "Released in 0.5.1", "v0.3.0", False),
        ("0.5.1", "Released in 0.5.1", "main", False),
        ("0.3.0.post1", "Released in 0.3.0", "v0.3.0", True),
        ("0.3.0.post1", "Released in 0.3.0.post1", "v0.3.0", False),
        ("0.6.0.dev0", "Released in 0.2.0", "v0.2.0", True),
        ("0.6.0.dev0", "Released in 0.6.0.dev0", "v0.2.0", False),
    ],
)
def test_release_row_control(version: str, row: str, tag: str, named: bool) -> None:
    text = (
        f"# T\n\n## Status\n\n| | |\n| --- | --- |\n| {row} | x |\n| Established | y |\n\n"
        f"## Quickstart\n\n```bash\ncurl -sLO {_RAW}/{tag}/examples/a.json\n```\n"
    )
    assert (release_row_problems(text, version, ("0.2.0a1", "0.2.0")) == []) is named
    elsewhere = text.replace(_RAW, "https://example.org")
    assert release_row_problems(elsewhere, version, ("0.2.0",)) != []


def test_project_urls_are_the_six_https_links() -> None:
    assert url_problems(PROJECT.get("urls")) == []
    assert PROJECT["readme"] == "README.md"


def test_project_urls_control() -> None:
    good = {key: f"https://example.org/{n}" for n, key in enumerate(URL_KEYS)}
    assert url_problems(good) == []
    assert url_problems(None) != []
    assert url_problems({k: v for k, v in good.items() if k != "Issues"}) == [
        "[project.urls] lacks 'Issues'"
    ]
    assert url_problems({**good, "Repository": "http://example.org/r"}) != []
    assert url_problems({**good, "Source": "git@github.com:x/y.git"}) != []


# ======================================================================= MSG-G9: the quickstart

_PYTHON_BLOCK = re.compile(r"^```python\n(.*?)^```", re.MULTILINE | re.DOTALL)
RANKINE = REPO_ROOT / "examples" / "rankine-cycle.changeset.json"


def quickstart() -> str:
    """The README's Python quickstart: its first `python` block."""
    found = _PYTHON_BLOCK.search(README)
    assert found is not None, "README.md has no ```python block"
    return found.group(1)


def test_msg_g9_the_quickstart_runs_twice_in_one_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from openflowsheet.application.local import LocalApplication

    shutil.copy(RANKINE, tmp_path / RANKINE.name)
    monkeypatch.chdir(tmp_path)
    code = compile(quickstart(), "README.md", "exec")
    printed = []
    for _ in range(2):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            exec(code, {"__name__": "__readme__"})
        printed.append(out.getvalue().split("\n"))
        with LocalApplication.open(tmp_path / "plant") as app:
            printed[-1].append(app.project_id)
    first, second = printed
    assert first[0] == second[0] == "READY_FOR_SIMULATION"
    assert first[1] == second[1] == "CONVERGED VERIFIED"
    assert first[-1] == second[-1]  # the second run opened the project the first created
    with LocalApplication.open(tmp_path / "plant") as app:
        assert len(app.list_jobs().items) == 2
