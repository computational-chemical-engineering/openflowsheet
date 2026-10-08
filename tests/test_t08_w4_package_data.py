"""T08 W4.2 (release spec §12 Q1, FD5): the runtime data travels in the package, unchanged.

The schemas and the two registered YAML files the package reads at run time are package data
(`openflowsheet.resources`), reached through `importlib.resources` via `_data/` links to the one
repository copy of each. These tests hold the source-tree half: the links point at the registered
files, every packaged file reads the repository's bytes, the package-data patterns cover exactly
what is packaged, and no module goes back to walking up from `__file__` to the repository. The
built half — the sdist's and the wheel's bytes equal the commit's, file by file — is T08.A43's
`scripts/t08_dist.py`, and an installed wheel solving outside the tree is T08.A44's CI job.

The schema list is `schemas/registry.json` (R-213; M03 spec §10, A48), not a number here: every
count below is derived from it, so schemas added on separate branches merge as separate lines of
the registry instead of as one literal two branches each bump.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path

import pytest
from conftest import REPO_ROOT

from openflowsheet.application.types import published_schemas
from openflowsheet.resources import PACKAGED, packaged

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import t08_dist  # noqa: E402

DATA = REPO_ROOT / "src" / "openflowsheet" / "_data"
#: R-213: the registered schema list — sorted file names, one per line, not packaged.
REGISTRY = REPO_ROOT / "schemas" / "registry.json"


def _registry() -> list[str]:
    names: list[str] = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return names


def _repository_files() -> dict[str, bytes]:
    """Every file the package carries, by repository path, read from the repository."""
    found = {
        f"schemas/{path.name}": path.read_bytes()
        for path in sorted((REPO_ROOT / "schemas").glob("*.schema.json"))
    }
    for relative in PACKAGED:
        if relative != "schemas":
            found[relative] = (REPO_ROOT / relative).read_bytes()
    return found


@pytest.mark.parametrize("relative", PACKAGED)
def test_each_packaged_path_is_a_link_to_the_single_repository_copy(relative: str) -> None:
    link = DATA / relative
    assert link.is_symlink(), f"{link} must be a link, not a copy (one copy, no rumour)"
    assert link.resolve() == (REPO_ROOT / relative).resolve()


def test_every_packaged_file_reads_the_repository_bytes() -> None:
    expected = _repository_files()
    # Every schema, and every other packaged path (`schemas` itself is the directory).
    assert len(expected) == len(_registry()) + len(PACKAGED) - 1
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
    assert len(by_id) == len(_registry())
    for schema_id, digest in by_id.items():
        name = schema_id.rsplit("/", 1)[1]
        assert hashlib.sha256(packaged(f"schemas/{name}").read_bytes()).hexdigest() == digest


def test_a48_the_registry_is_sorted_and_names_each_schema_once() -> None:
    names = _registry()
    assert names == sorted(names)
    assert len(set(names)) == len(names), sorted({n for n in names if names.count(n) > 1})
    assert all(name.endswith(".schema.json") for name in names)
    # The registry's own text: one name per line, so a branch's addition is its own line.
    lines = REGISTRY.read_text(encoding="utf-8").splitlines()
    assert lines == ["[", *(f'  "{name}",' for name in names[:-1]), f'  "{names[-1]}"', "]"]


def test_a48_the_registry_is_the_schema_directory() -> None:
    on_disk = {path.name for path in (REPO_ROOT / "schemas").glob("*.schema.json")}
    registered = set(_registry())
    assert sorted(on_disk - registered) == [], "schema files without a registry line"
    assert sorted(registered - on_disk) == [], "registry lines without a schema file"


def test_a48_the_registry_is_the_published_and_the_packaged_schemas() -> None:
    registered = set(_registry())
    published = {schema_id.rsplit("/", 1)[1] for schema_id in published_schemas()}
    assert sorted(published ^ registered) == []
    packaged_names = {
        entry.name for entry in packaged("schemas").iterdir() if entry.name.endswith(".schema.json")
    }
    assert sorted(packaged_names ^ registered) == []
    # The registry itself is not packaged (like `units.json`): the package-data patterns, which
    # the next test holds to `_repository_files()`, carry `*.schema.json` only.
    assert f"schemas/{REGISTRY.name}" not in _repository_files()


def test_a48_no_literal_schema_count_is_left_in_this_file() -> None:
    """R-213: a literal count is what two branches each bump and merge to a wrong number."""
    source = Path(__file__).read_text(encoding="utf-8")
    assert re.search(r"len\([^)]*\)\s*==\s*\d", source) is None
    assert re.search(r"==\s*\d+\s*\+\s*\d", source) is None


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


def test_no_module_reads_schemas_or_benchmarks_by_walking_up_from_its_file() -> None:
    """The pre-W4.2 idiom, `Path(__file__).resolve().parents[3] / "schemas"` and the walk to a
    parent holding `benchmarks/`, works only in a checkout. (`run/manifest.py`'s walk to
    `requirements.lock` stays: the lock describes a checkout's environment, not the package.)"""
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
