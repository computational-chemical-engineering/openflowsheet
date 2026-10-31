"""`README.md` is the PyPI project page, and it stays current (V03-post1; Frank, 2026-10-31).

PyPI renders `README.md` as the long description and resolves no relative link, so every link and
image in it is absolute (`https://`). Its status names the release the version belongs to: at a
release version (`X.Y.Z`, `X.Y.Z{a|b|rc}N`) that version, at a post-release `X.Y.Z.postN` its
release `X.Y.Z` and the post-release itself (R-922), and at a `.devN` version between releases the
newest released version (`RELEASED`, `tests/test_v02_main_version.py`). The cut commit of every
release updates it (`docs/RELEASING.md`). `[project.urls]`, the links in PyPI's sidebar, has the
six keys below, every one an `https://` URL. Each check has a negative control.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Iterable, Mapping

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
        return (f"Version {max(released, key=Version)} is released",)
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
