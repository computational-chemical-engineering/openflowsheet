"""R-922 (V03-post1): a post-release `X.Y.Z.postN` of a released `X.Y.Z`, gated as `X.Y.Z`.

The rule (`docs/decision-register.md` R-922, `docs/RELEASING.md` "Post-releases"): against X.Y.Z's
candidate `C`, the D2.4 files of the candidate differ only in `README.md`, in `pyproject.toml`'s
`[project]` keys `version`, `urls` and `readme`, and in the version string of
`src/openflowsheet/__init__.py`; files outside D2.4 are free; and `X.Y.Z` is released (a tag
`vX.Y.Z` on an ancestor of the candidate). The gate set, `C`, the verdicts and the envelope stay
X.Y.Z's. The tests below hold the rule on a scratch repository — passing for a README, links and
version change, failing for each of a source byte, a dependency, the lock, a schema and a missing
tag — and on this repository's own post-release.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from conftest import REPO_ROOT
from packaging.version import Version

import openflowsheet

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import test_m07_v0_2_gate as m07  # noqa: E402
import test_v03_v0_3_gate as v03  # noqa: E402
import v0_1_gate  # noqa: E402
import v0_2_gate  # noqa: E402
import v0_3_gate  # noqa: E402

#: 0.3.0's release candidate (V03 RC record; `v0.3.0` was cut from it).
C_0_3_0 = "a3e508e35fc5451fe56fa7b70941621992d35b50"

PYPROJECT = """[project]
name = "p"
version = "{version}"
readme = "README.md"
dependencies = ["numpy==2.2.4"]
{urls}
[tool.setuptools]
package-dir = {{ "" = "src" }}
"""
URLS = '\n[project.urls]\nHomepage = "https://example.org/"\nIssues = "https://example.org/i"\n'


def _pyproject(version: str, *, urls: str = "", dependency: str = "numpy==2.2.4") -> str:
    return PYPROJECT.format(version=version, urls=urls).replace("numpy==2.2.4", dependency)


@pytest.fixture
def scratch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    m07._git(repo, "init", "-q")
    monkeypatch.setattr(v0_1_gate, "ROOT", repo)
    return repo


def _release(repo: Path) -> str:
    """`C` at 0.3.0 with every kind of D2.4 file, tagged `v0.3.0`."""
    rc = m07._commit(
        repo,
        {
            "pyproject.toml": _pyproject("0.3.0"),
            "src/openflowsheet/__init__.py": '"""The package."""\n__version__ = "0.3.0"\n',
            "requirements.lock": "numpy==2.2.4\n",
            "schemas/a.schema.json": '{"type": "object"}\n',
            "README.md": "Version 0.2.0 is released.\n",
            "docs/notes.md": "notes\n",
        },
        "C",
    )
    m07._git(repo, "tag", "v0.3.0", rc)
    return rc


#: The post-release's own change: README, links, version; and files outside D2.4.
POST = {
    "pyproject.toml": _pyproject("0.3.0.post1", urls=URLS),
    "src/openflowsheet/__init__.py": '"""The package."""\n__version__ = "0.3.0.post1"\n',
    "README.md": "Version 0.3.0 is released.\n",
    "CHANGELOG.md": "## v0.3.0.post1\n\nREADME only.\n",
    "docs/RELEASING.md": "post-releases\n",
    "scripts/tool.py": "print()\n",
    "tests/test_x.py": "def test() -> None: ...\n",
    ".github/workflows/x.yml": "on: push\n",
}


def test_the_post_release_s_own_change_passes(scratch: Path) -> None:
    rc = _release(scratch)
    candidate = m07._commit(scratch, POST, "post")
    assert v0_2_gate.post_release_differences(rc, candidate) == []
    assert v0_2_gate.is_released("0.3.0", candidate)
    # The ordinary D2.4 rule refuses the same change: the allowance is R-922's, not D2.4's.
    assert v0_1_gate.tree_differences(rc, candidate) == ["README.md", "pyproject.toml"]


@pytest.mark.parametrize(
    ("change", "path"),
    [
        (
            {"src/openflowsheet/__init__.py": '"""The package!"""\n__version__ = "0.3.0.post1"\n'},
            "src/openflowsheet/__init__.py",
        ),
        ({"src/openflowsheet/new.py": "x = 1\n"}, "src/openflowsheet/new.py"),
        (
            {"pyproject.toml": _pyproject("0.3.0.post1", urls=URLS, dependency="numpy==2.2.5")},
            "pyproject.toml",
        ),
        (
            {"pyproject.toml": _pyproject("0.3.0.post1", urls=URLS) + "[tool.x]\ny = 1\n"},
            "pyproject.toml",
        ),
        ({"requirements.lock": "numpy==2.2.5\n"}, "requirements.lock"),
        ({"schemas/a.schema.json": '{"type": "array"}\n'}, "schemas/a.schema.json"),
        ({"schemas/b.schema.json": "{}\n"}, "schemas/b.schema.json"),
    ],
)
def test_each_change_outside_the_allowance_fails(
    scratch: Path, change: dict[str, str], path: str
) -> None:
    rc = _release(scratch)
    candidate = m07._commit(scratch, {**POST, **change}, "post")
    assert v0_2_gate.post_release_differences(rc, candidate) == [path]


def test_a_version_string_twice_fails(scratch: Path) -> None:
    rc = _release(scratch)
    twice = '"""The package."""\n__version__ = "0.3.0.post1"\nX = "0.3.0.post1"\n'
    candidate = m07._commit(scratch, {**POST, "src/openflowsheet/__init__.py": twice}, "post")
    assert v0_2_gate.post_release_differences(rc, candidate) == ["src/openflowsheet/__init__.py"]


def test_without_the_release_s_tag_it_is_not_released(scratch: Path) -> None:
    rc = _release(scratch)
    candidate = m07._commit(scratch, POST, "post")
    assert v0_2_gate.is_released("0.3.0", candidate)
    m07._git(scratch, "tag", "-d", "v0.3.0")
    assert not v0_2_gate.is_released("0.3.0", candidate)
    # A tag that is not on an ancestor of the candidate does not count either.
    m07._git(scratch, "checkout", "-q", "--orphan", "elsewhere")
    elsewhere = m07._commit(scratch, {"other.md": "x\n"}, "elsewhere")
    m07._git(scratch, "tag", "v0.3.0", elsewhere)
    assert not v0_2_gate.is_released("0.3.0", candidate)
    assert v0_2_gate.post_release_differences(rc, candidate) == []


def test_c_known_only_by_its_record_is_refused(
    scratch: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rc = _release(scratch)
    candidate = m07._commit(scratch, POST, "post")
    monkeypatch.setattr(v0_2_gate, "has_commit", lambda commit: commit != rc)
    with pytest.raises(ValueError, match=r"R-922\) reads C"):
        v0_2_gate.post_release_differences(rc, candidate)


@pytest.mark.parametrize(
    ("version", "gated"),
    [
        ("0.3.0.post1", "0.3.0"),
        ("0.3.0.post12", "0.3.0"),
        ("0.3.0", "0.3.0"),
        ("0.3.0rc1", "0.3.0rc1"),
        ("0.3.0.post0", "0.3.0.post0"),
        ("0.3.0rc1.post1", "0.3.0rc1.post1"),
        ("0.3.0.post1.dev0", "0.3.0.post1.dev0"),
    ],
)
def test_the_v0_3_line_gates_a_post_release_as_its_release(version: str, gated: str) -> None:
    assert v0_3_gate.gated_version(version) == gated
    covered = v0_3_gate.gate_set_of(gated)
    expected = "v0.3-gate-v1" if gated in ("0.3.0", "0.3.0rc1") else None
    assert (covered.name if covered else None) == expected
    # Table T-V3 is unchanged: the set's pattern does not cover a post-release itself.
    assert v0_3_gate.gate_set_of("0.3.0.post1") is None


def test_the_v0_2_line_admits_no_post_release() -> None:
    assert v0_2_gate.post_release_of("0.2.0.post1") is None
    assert v0_2_gate.gated_version("0.2.0.post1") == "0.2.0.post1"
    assert v0_2_gate.gate_set_of("0.2.0.post1") is None


def _post_release_scratch(repo: Path) -> tuple[str, str]:
    """`v03._build_scratch`'s YES candidate tagged `v0.3.0`, then the post-release's change."""
    rc, candidate, _ = v03._build_scratch(repo)
    m07._git(repo, "tag", "v0.3.0", candidate)
    post = m07._commit(
        repo,
        {
            "pyproject.toml": '[project]\nname = "p"\nversion = "0.3.0.post1"\n' + URLS,
            "src/openflowsheet/__init__.py": '__version__ = "0.3.0.post1"\n',
            "README.md": "Version 0.3.0 is released.\n",
            "CHANGELOG.md": "## v0.3.0.post1\n\nREADME only.\n",
        },
        "post",
    )
    return rc, post


def test_main_proposes_the_post_release_at_the_release_s_c(
    scratch: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc, post = _post_release_scratch(scratch)
    code = v0_3_gate.main(["--rc", rc])
    out = capsys.readouterr().out
    assert code == 0, out
    lines = out.splitlines()
    assert lines[0] == f"v0.3 gates (v0.3-gate-v1) at C = {rc}; candidate {post}"
    assert "tree check (D2.4): equal to C" in lines
    assert "post-release (R-922): of 0.3.0, released (tag v0.3.0)" in lines
    assert lines[-1] == "v0.3.0.post1 tag may be proposed: YES"


def test_main_refuses_a_post_release_without_its_release(
    scratch: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc, _ = _post_release_scratch(scratch)
    m07._git(scratch, "tag", "-d", "v0.3.0")
    code = v0_3_gate.main(["--rc", rc])
    out = capsys.readouterr().out
    assert code == 1
    assert "post-release (R-922): of 0.3.0, not released" in out.splitlines()
    assert out.splitlines()[-1] == "v0.3.0.post1 tag may be proposed: NO (1 reasons)"


def test_main_refuses_a_post_release_with_a_source_change(
    scratch: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc, _ = _post_release_scratch(scratch)
    m07._commit(scratch, {"src/openflowsheet/extra.py": "x = 1\n"}, "source")
    code = v0_3_gate.main(["--rc", rc])
    out = capsys.readouterr().out
    assert code == 1
    assert "tree check (D2.4): differs in 1 paths" in out.splitlines()
    assert out.splitlines()[-1] == "v0.3.0.post1 tag may be proposed: NO (1 reasons)"


def test_main_refuses_a_post_release_whose_envelope_moved(
    scratch: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The envelope stays the release's (`release: 0.3.0`); its file is in D2.4 as well."""
    rc, _ = _post_release_scratch(scratch)
    m07._commit(scratch, {v03.ENVELOPE: v03.envelope(release="0.3.0.post1")}, "envelope")
    code = v0_3_gate.main(["--rc", rc])
    out = capsys.readouterr().out
    assert code == 1
    assert out.splitlines()[-1] == "v0.3.0.post1 tag may be proposed: NO (2 reasons)"


def test_build_refuses_a_post_release_whose_release_was_not_checked() -> None:
    report = v0_3_gate.build(
        files=v03.files(),
        rc=v03.RC,
        rc_version="0.3.0",
        rc_in_repository=True,
        candidate=v03.CANDIDATE,
        version="0.3.0.post1",
        differences=[],
        is_ancestor=lambda commit: True,
    )
    assert report["post_release"] == {"of": "0.3.0", "released": None}
    assert report["reasons"] == [
        "0.3.0.post1 is a post-release of 0.3.0, which is not released: no tag v0.3.0 on an "
        "ancestor of the candidate (R-922)"
    ]
    released = v0_3_gate.build(
        files=v03.files(),
        rc=v03.RC,
        rc_version="0.3.0",
        rc_in_repository=True,
        candidate=v03.CANDIDATE,
        version="0.3.0.post1",
        differences=[],
        is_ancestor=lambda commit: True,
        released=True,
    )
    assert released["tag_may_be_proposed"] is True
    assert "post_release" not in v0_3_gate.build(
        files=v03.files(),
        rc=v03.RC,
        rc_version="0.3.0",
        rc_in_repository=True,
        candidate=v03.CANDIDATE,
        version="0.3.0",
        differences=[],
        is_ancestor=lambda commit: True,
    )


# -- this repository's post-release ---------------------------------------------------------------


def _this_post_release() -> str | None:
    """The commit that carries 0.3.0's post-release: `HEAD` while it declares one, else the newest
    tag `v0.3.0.postN`, else `None` (before the post-release, or in a clone without tags)."""
    if (
        v0_3_gate.gated_version(openflowsheet.__version__) == "0.3.0"
        and Version(openflowsheet.__version__).is_postrelease
    ):
        return "HEAD"
    tags = v0_1_gate.git("tag", "--list", "v0.3.0.post*").decode().split()
    tags = [tag for tag in tags if v0_2_gate.POST_RELEASE.fullmatch(tag[1:])]
    return max(tags, key=lambda tag: Version(tag[1:])) if tags else None


def test_this_repository_s_post_release_is_admitted() -> None:
    """The rule passes on 0.3.0.post1's own diff against 0.3.0's C."""
    at = _this_post_release()
    if at is None:
        pytest.skip("no 0.3.0 post-release at HEAD or among the tags")
    assert v0_1_gate.has_commit(C_0_3_0)
    assert v0_2_gate.post_release_differences(C_0_3_0, at) == []
    assert v0_2_gate.is_released("0.3.0", at)
    # Negative control: the ordinary D2.4 rule sees the README and the links.
    assert "README.md" in v0_1_gate.tree_differences(C_0_3_0, at)
