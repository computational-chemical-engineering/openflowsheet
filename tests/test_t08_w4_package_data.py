"""T08 W4.2 (release spec §12 Q1, FD5): the runtime data travels in the package, unchanged.

The schemas, the registered YAML files the package reads at run time and the web shell (`_data/web`
→ `apps/web/`, M06) are package data (`openflowsheet.resources`), reached through
`importlib.resources` via `_data/` links to the one repository copy of each. These tests hold the
source-tree half: the links point at the registered files, every packaged file reads the
repository's bytes, the package-data patterns cover exactly what is packaged, and no module goes
back to walking up from `__file__` to the repository. The built half — the sdist's and the wheel's
bytes equal the commit's, file by file — is T08.A43's `scripts/t08_dist.py`, and an installed wheel
solving outside the tree is T08.A44's CI job.
"""

from __future__ import annotations

import hashlib
import re
import sys
import tomllib
from pathlib import Path

import pytest
from conftest import REPO_ROOT

from openflowsheet.application.types import published_schemas
from openflowsheet.resources import DIRECTORIES, PACKAGED, packaged, repository_path

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import t08_dist  # noqa: E402

DATA = REPO_ROOT / "src" / "openflowsheet" / "_data"
#: Which files below each packaged directory travel: the published schemas only (not the
#: directory's README or unit table), but every file of the web shell (M06, gate G10).
DIRECTORY_FILES = {"schemas": "*.schema.json", "web": "**/*"}


def _repository_files() -> dict[str, bytes]:
    """Every file the package carries, by its path below `_data/`, read from its single
    repository copy (`repository_path`: `web` is `apps/web`)."""
    found: dict[str, bytes] = {}
    for relative in PACKAGED:
        source = REPO_ROOT / repository_path(relative)
        if relative in DIRECTORIES:
            for path in sorted(source.glob(DIRECTORY_FILES[relative])):
                if path.is_file():
                    found[f"{relative}/{path.relative_to(source).as_posix()}"] = path.read_bytes()
        else:
            found[relative] = source.read_bytes()
    return found


@pytest.mark.parametrize("relative", PACKAGED)
def test_each_packaged_path_is_a_link_to_the_single_repository_copy(relative: str) -> None:
    link = DATA / relative
    assert link.is_symlink(), f"{link} must be a link, not a copy (one copy, no rumour)"
    assert link.resolve() == (REPO_ROOT / repository_path(relative)).resolve()


def test_only_the_web_shell_sits_at_another_repository_path() -> None:
    assert set(DIRECTORY_FILES) == set(DIRECTORIES)
    assert {r: repository_path(r) for r in PACKAGED if repository_path(r) != r} == {
        "web": "apps/web"
    }
    with pytest.raises(KeyError):
        repository_path("schemas/job.schema.json")


def test_the_web_shell_holds_no_link_and_nothing_outside_the_packaged_globs() -> None:
    """`serve-http --ui` serves the resolved directory without following links, and the wheel
    carries bytes: a link inside `apps/web/` would serve in a checkout and not from a wheel."""
    shell = REPO_ROOT / "apps" / "web"
    assert [p for p in shell.rglob("*") if p.is_symlink()] == []
    assert "web/index.html" in _repository_files()


def test_every_packaged_file_reads_the_repository_bytes() -> None:
    expected = _repository_files()
    assert sum(1 for r in expected if r.startswith("schemas/")) == 32
    assert sum(1 for r in expected if r in PACKAGED) == 4
    for relative, data in expected.items():
        assert packaged(relative).read_bytes() == data, relative
    assert sorted(
        entry.name for entry in packaged("schemas").iterdir() if entry.name.endswith(".schema.json")
    ) == sorted(Path(relative).name for relative in expected if relative.startswith("schemas/"))


def test_the_published_schemas_are_the_repository_schemas_by_id() -> None:
    by_id = {
        document["$id"]: hashlib.sha256(
            (REPO_ROOT / "schemas" / document["$id"].rsplit("/", 1)[1]).read_bytes()
        ).hexdigest()
        for document in published_schemas().values()
    }
    assert len(by_id) == 32
    for schema_id, digest in by_id.items():
        name = schema_id.rsplit("/", 1)[1]
        assert hashlib.sha256(packaged(f"schemas/{name}").read_bytes()).hexdigest() == digest


def test_the_package_data_patterns_cover_exactly_what_is_packaged() -> None:
    document = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    patterns = document["tool"]["setuptools"]["package-data"]["openflowsheet"]
    base = REPO_ROOT / "src" / "openflowsheet"
    matched = {
        path.relative_to(DATA).as_posix()
        for pattern in patterns
        if pattern.startswith("_data/")
        for path in base.glob(pattern)
        if path.is_file()
    }
    assert matched == set(_repository_files())


def test_an_unlisted_path_is_refused() -> None:
    with pytest.raises(KeyError):
        packaged("benchmarks/registry.yaml")
    with pytest.raises(KeyError):
        packaged("webx/index.html")
    assert (
        packaged("web/index.html").read_bytes()
        == (REPO_ROOT / "apps" / "web" / "index.html").read_bytes()
    )


def test_no_module_reads_schemas_or_benchmarks_by_walking_up_from_its_file() -> None:
    """The pre-W4.2 idiom, `Path(__file__).resolve().parents[3] / "schemas"` and the walk to a
    parent holding `benchmarks/`, works only in a checkout. (`run/manifest.py`'s walk to
    `requirements.lock` stays: the lock describes a checkout's environment, not the package. So does
    `thermo/pr_c1.py`'s `_checkout_records`, taken only when `PACKAGED` lacks the C1 records, which
    is M01 spec Q-N4 declined: the package then deliberately carries none; M01 review F4.)"""
    idiom = re.compile(r'/\s*"(schemas|benchmarks)"')
    found = [
        f"{path.relative_to(REPO_ROOT)}:{number}"
        for path in sorted((REPO_ROOT / "src").rglob("*.py"))
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if idiom.search(line) and not line.lstrip().startswith("#")
    ]
    assert found == []


# -- scripts/t08_dist.py's classification rules (T08.A43), on constructed members ------------


def test_dist_classifies_members_and_refuses_anything_else() -> None:
    assert t08_dist.classify_sdist("LICENSE") == "licence"
    assert t08_dist.classify_sdist("PKG-INFO") == "metadata"
    assert t08_dist.classify_sdist("src/openflowsheet.egg-info/SOURCES.txt") == "metadata"
    assert t08_dist.classify_sdist("src/openflowsheet/canonical.py") == "package"
    assert t08_dist.classify_sdist("src/openflowsheet/_data/schemas/job.schema.json") == (
        "runtime_data"
    )
    assert t08_dist.classify_sdist("tests/test_canonical.py") is None
    assert t08_dist.classify_sdist("benchmarks/syn001/oracle.py") is None
    info = "openflowsheet-0.1.0rc1.dist-info"
    assert t08_dist.classify_wheel(f"{info}/licenses/NOTICE", info) == "licence"
    assert t08_dist.classify_wheel(f"{info}/METADATA", info) == "metadata"
    assert t08_dist.classify_wheel(f"{info}/INSTALLER", info) is None
    assert t08_dist.classify_wheel("benchmarks/__init__.py", info) is None
    assert t08_dist.is_casadi_or_compiled("casadi/_casadi.so")
    assert t08_dist.is_casadi_or_compiled("openflowsheet/libx.so.3")
    assert not t08_dist.is_casadi_or_compiled("openflowsheet/compile/casadi_backend.py")


def test_dist_expects_the_pyproject_pins_as_requires_dist() -> None:
    document = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    wanted = t08_dist.expected_requires_dist(document["project"])
    assert "casadi==3.8.0" in wanted
    assert 'mcp==1.30.0; extra == "server"' in wanted
    assert len(wanted) == len(document["project"]["dependencies"]) + sum(
        len(extra) for extra in document["project"]["optional-dependencies"].values()
    )
