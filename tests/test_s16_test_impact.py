"""S16: test-impact selection (scripts/test_impact.py, docs/test-impact.md).

Every rule runs on a synthetic repository and a synthetic map, so these tests need neither coverage
nor a built map: they run in the main venv and in CI. The map build itself needs the test-map venv
(requirements-testmap.lock) and is exercised by the recall check (docs/S16_DECISIONS.md).
"""

from __future__ import annotations

import ast
import contextlib
import importlib.util
import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses look their module up there
    spec.loader.exec_module(module)
    return module


ti = _load("test_impact")

MODULE = '''\
"""A module."""

LIMIT = 3


def f(x):
    y = x + 1
    if y > LIMIT:
        return y
    return 0


def g(x):
    total = 0
    for i in range(x):
        total += i
    return total


def counter():
    """Count."""
    count = 0

    def bump():
        nonlocal count
        count += 1
        return count

    return bump()


def h():
    return "fixture work"


class Plain:
    def method(self):
        return 1


class Child(Plain):
    def other(self):
        return 2


def boot():
    return "import time"


BOOTED = boot()
'''

TEST_MODULE = """\
import pytest

CONSTANT = 1


def test_one():
    assert CONSTANT == 1


def test_two():
    assert True
"""

PYPROJECT = """\
[project]
name = "x"

[tool.pytest.ini_options]
testpaths = ["tests"]
"""

TWINS = """\
import os

if os.name == "nt":

    def render():
        return "first"

else:

    def render():
        return "second"
"""

FILES = {
    "src/pkg/mod.py": MODULE,
    "src/pkg/twins.py": TWINS,
    "src/pkg/unseen.py": "def u():\n    return 1\n",
    "tests/test_a.py": TEST_MODULE,
    "tests/conftest.py": "",
    "tests/a_support.py": "X = 1\n",
    "tests/support/helper.py": "Y = 1\n",
    "tests/data.json": "{}\n",
    "docs/guide.md": "guide\n",
    "docs/other.md": "other\n",
    "docs/tool.py": "def run():\n    return 1\n",
    "data/table.yaml": "a: 1\n",
    "data/boot.json": "{}\n",
    "data/unseen.txt": "x\n",
    "pyproject.toml": PYPROJECT,
    ".codehealth/config.toml": "scope = 1\n",
    ".claude/skills/s/SKILL.md": "skill\n",
}

T1 = "tests/test_a.py::test_one"
T2 = "tests/test_a.py::test_two"
T3 = "tests/test_b.py::test_three"
T4 = "tests/test_b.py::test_four[1]"


def _git(repo: Path, *args: str) -> str:
    environment = dict(
        os.environ,
        GIT_AUTHOR_NAME="t",
        GIT_AUTHOR_EMAIL="t@example.invalid",
        GIT_COMMITTER_NAME="t",
        GIT_COMMITTER_EMAIL="t@example.invalid",
    )
    return subprocess.run(
        ["git", *args], cwd=repo, env=environment, capture_output=True, text=True, check=True
    ).stdout


def _lines(text: str, *needles: str) -> list[int]:
    lines = text.splitlines()
    return [lines.index(needle) + 1 for needle in needles]


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, str, Path]:
    """A committed synthetic repository, its base commit and a map of it."""
    repo = tmp_path / "repo"
    for name, text in FILES.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD").strip()
    data = ti.MapData()
    data.meta = {"format": "1", "base": base, "tree": ti.tree_of(base, repo)}
    data.tests = {T1: "passed", T2: "passed", T3: "passed", T4: "passed"}
    data.fixtures = {T3: {"fixture:tests::shared"}, T4: {"fixture:tests::shared"}}
    f_body = _lines(MODULE, "    y = x + 1", "    if y > LIMIT:", "        return y")
    data.add_lines("src/pkg/mod.py", T1, ti.numbits(f_body))
    data.add_lines("src/pkg/mod.py", T2, ti.numbits(_lines(MODULE, "    total = 0")))
    data.add_lines("src/pkg/mod.py", T2, ti.numbits(_lines(MODULE, "    return total")))
    data.add_lines(
        "src/pkg/mod.py",
        "fixture:tests::shared",
        ti.numbits(_lines(MODULE, '    return "fixture work"')),
    )
    data.add_lines("src/pkg/mod.py", T3, ti.numbits(_lines(MODULE, "        return 1")))
    data.add_lines("src/pkg/mod.py", T4, ti.numbits(_lines(MODULE, "        return 2")))
    data.add_lines("src/pkg/mod.py", T1, ti.numbits(_lines(MODULE, "        count += 1")))
    data.add_lines("src/pkg/mod.py", T2, ti.numbits(_lines(MODULE, "    count = 0")))
    data.add_lines("src/pkg/twins.py", T1, ti.numbits(_lines(TWINS, '        return "first"')))
    data.add_lines("src/pkg/twins.py", T2, ti.numbits(_lines(TWINS, '        return "second"')))
    module_level = _lines(
        MODULE, "LIMIT = 3", "def f(x):", "BOOTED = boot()", '    return "import time"'
    )
    data.add_lines("src/pkg/mod.py", ti.COLLECTION, ti.numbits(module_level))
    data.add_lines(
        "tests/test_a.py", T1, ti.numbits(_lines(TEST_MODULE, "    assert CONSTANT == 1"))
    )
    data.add_lines("tests/test_a.py", T2, ti.numbits(_lines(TEST_MODULE, "    assert True")))
    data.opens = {
        ("data/table.yaml", T2),
        ("docs/guide.md", T1),
        ("pyproject.toml", T3),
        ("data/boot.json", ti.COLLECTION),
    }
    map_dir = tmp_path / "map"
    map_dir.mkdir()
    data.write(map_dir / "map.sqlite")
    return repo, base, map_dir


def _edit(repo: Path, name: str, old: str, new: str) -> None:
    path = repo / name
    text = path.read_text()
    assert old in text, old
    path.write_text(text.replace(old, new, 1))


def _select(repo_fixture: tuple[Path, str, Path]) -> object:
    repo, base, map_dir = repo_fixture
    return ti.select(base, map_dir, cwd=repo)


# -- the pieces ------------------------------------------------------------------------------------


def test_parse_diff_reads_counts_insertions_and_deletions() -> None:
    diff = (
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n"
        "@@ -3 +3 @@\n-a\n+b\n@@ -10,0 +11,2 @@\n+c\n+d\n@@ -20,2 +22,0 @@\n-e\n-f\n"
        "diff --git a/gone.txt b/gone.txt\n--- a/gone.txt\n+++ /dev/null\n@@ -1 +0,0 @@\n-x\n"
        "diff --git a/new.txt b/new.txt\n--- /dev/null\n+++ b/new.txt\n@@ -0,0 +1 @@\n+y\n"
    )
    assert ti.parse_diff(diff) == {
        "x.py": [(3, 1, 3, 1), (10, 0, 11, 2), (20, 2, 22, 0)],
        "gone.txt": [(1, 1, 0, 0)],
        "new.txt": [(0, 0, 1, 1)],
    }


def test_numbits_match_coverage_form() -> None:
    bits = ti.numbits([1, 8, 17])
    assert bits == bytes([0b10, 0b1, 0b10])
    assert ti.has_any(bits, [8]) and not ti.has_any(bits, [2, 100])
    assert ti.numbits_union(ti.numbits([1]), ti.numbits([17])) == ti.numbits([1, 17])


def test_runtime_is_inert_without_an_active_build() -> None:
    runtime = _load("test_impact_runtime")
    assert runtime._run is None and runtime._coverage is None
    with pytest.raises(RuntimeError, match="no test-map build"):
        runtime.pytest_configure(None)


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="X07a platform limit: the test-map runtime matches an opened path by its POSIX prefix "
    "(`root + '/'`); the map is built in the Linux test-map venv only (docs/test-impact.md)",
)
def test_runtime_open_record_walks_library_frames_and_drops_imports(
    tmp_path: Path, monkeypatch
) -> None:
    """B-18: the audit hook walks past the standard library, installed packages and itself to the
    opener; an open reached from an import frame is dropped, any other read is recorded."""
    import sysconfig

    runtime = _load("test_impact_runtime")
    (tmp_path / "data.txt").write_text("x")
    (tmp_path / "folder").mkdir()
    monkeypatch.setattr(runtime, "_root", f"{tmp_path}/")
    monkeypatch.setattr(runtime, "_context", "ctx")
    monkeypatch.setattr(runtime, "_opens", set())

    def caller(filename: str, inner: object = None) -> object:
        namespace: dict[str, object] = {}
        exec(compile("def call(f, *a):\n    return f(*a)\n", filename, "exec"), namespace)
        call = namespace["call"]
        return call if inner is None else (lambda f, *a: call(inner, f, *a))

    library = sysconfig.get_paths()["purelib"] + "/somelib/io.py"
    frozen = "<frozen importlib._bootstrap_external>"
    path = str(tmp_path / "data.txt")

    def recorded(via: object, name: str = path, mode: object = "r", flags: int = 0) -> bool:
        runtime._opens.clear()
        via(runtime._audit, "open", (name, mode, flags))  # type: ignore[operator]
        assert runtime._opens <= {("ctx", "data.txt")}
        return bool(runtime._opens)

    direct = lambda f, *a: f(*a)  # noqa: E731
    assert recorded(direct)  # from a repository frame
    assert recorded(direct, mode=None, flags=os.O_RDONLY)  # os.open
    assert recorded(caller(library))  # through an installed package
    assert not recorded(caller(frozen))  # an import
    assert not recorded(caller(library, caller(frozen)))  # an import, deeper
    assert not recorded(direct, mode="w")
    assert not recorded(direct, mode=None, flags=os.O_WRONLY)
    assert not recorded(direct, name=str(tmp_path / "folder"))  # a directory
    assert not recorded(direct, name="/etc/hostname")  # outside the repository
    monkeypatch.chdir(tmp_path)
    assert recorded(direct, name="data.txt")  # relative to the working directory


# -- line coverage ---------------------------------------------------------------------------------


def test_a_changed_line_selects_the_tests_that_ran_it(repo) -> None:
    _edit(repo[0], "src/pkg/mod.py", "    y = x + 1", "    y = x + 2")
    assert _select(repo).nodes == {T1} and _select(repo).fallback is None


def test_a_rewritten_line_also_selects_the_enclosing_function(repo) -> None:
    _edit(repo[0], "src/pkg/mod.py", "    for i in range(x):", "    for i in range(x + 1):")
    # No test ran g's loop header in the synthetic map, but the new side's line lies in g.
    assert _select(repo).nodes == {T2}


def test_a_deleted_line_selects_the_tests_that_ran_it(repo) -> None:
    _edit(repo[0], "src/pkg/mod.py", "    total = 0\n", "")
    assert _select(repo).nodes == {T2}
    _edit(repo[0], "src/pkg/mod.py", "    for i in range(x):\n        total += i\n", "")
    assert _select(repo).nodes == {T2}


def test_an_added_line_selects_the_enclosing_function(repo) -> None:
    _edit(repo[0], "src/pkg/mod.py", "    total = 0\n", "    total = 0\n    total -= 1\n")
    assert _select(repo).nodes == {T2}


def test_shared_fixture_work_selects_every_test_using_the_fixture(repo) -> None:
    _edit(repo[0], "src/pkg/mod.py", '"fixture work"', '"other work"')
    assert _select(repo).nodes == {T3, T4}


def test_a_comment_only_change_selects_nothing(repo) -> None:
    _edit(repo[0], "src/pkg/mod.py", "LIMIT = 3\n", "# a comment\nLIMIT = 3\n")
    assert _select(repo).nodes == set() and _select(repo).fallback is None


def test_an_extracted_function_selects_the_caller_only(repo) -> None:
    _edit(
        repo[0],
        "src/pkg/mod.py",
        "    y = x + 1\n",
        "    y = _plus_one(x)\n",
    )
    _edit(
        repo[0], "src/pkg/mod.py", "def g(x):", "def _plus_one(x):\n    return x + 1\n\n\ndef g(x):"
    )
    assert _select(repo).nodes == {T1}


def test_a_new_method_of_a_plain_class_selects_nothing_more(repo) -> None:
    _edit(
        repo[0],
        "src/pkg/mod.py",
        "        return 1\n",
        "        return 1\n\n    def helper(self):\n        return 3\n",
    )
    assert _select(repo).nodes == set() and _select(repo).fallback is None


@pytest.mark.parametrize("name", ["LIMIT", "total", "CONSTANT", "method"])
def test_a_new_def_that_shadows_a_name_the_base_mentions_falls_back(repo, name: str) -> None:
    """B-13: an assignment (LIMIT), a local (total), another file's name (CONSTANT), a sibling
    class's method (method): the new def may rebind or override what base code reaches."""
    _edit(
        repo[0],
        "src/pkg/mod.py",
        "BOOTED = boot()\n",
        f"BOOTED = boot()\n\n\ndef {name}():\n    return 1\n",
    )
    assert "import-time code changed" in (_select(repo).fallback or "")
    _edit(repo[0], "src/pkg/mod.py", f"def {name}():", "def _fresh_name():")
    assert _select(repo).nodes == set() and _select(repo).fallback is None


def test_a_line_added_to_one_of_two_same_named_functions_selects_both(repo) -> None:
    """B-14: the base has two `render`s (if/else); the new side cannot say which one it edits."""
    _edit(
        repo[0],
        "src/pkg/twins.py",
        '        return "second"',
        '        x = 1\n        return "second"',
    )
    assert _select(repo).nodes == {T1, T2}


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ("        nonlocal count\n", "", {T1}),
        ('    """Count."""\n', "", {T1, T2}),
        ("        nonlocal count\n", "        # nonlocal count\n", {T1}),
    ],
    ids=["nonlocal", "docstring", "commented-out"],
)
def test_deleting_a_statement_without_a_line_event_selects_its_function(
    repo, old: str, new: str, expected: set[str]
) -> None:
    """B-15: coverage never records `nonlocal` or a docstring, so their deletion maps to the tests
    of the enclosing function's body (the nested `bump` or the whole `counter`)."""
    _edit(repo[0], "src/pkg/mod.py", old, new)
    assert _select(repo).nodes == expected


def test_deleting_a_module_level_statement_falls_back(repo) -> None:
    _edit(repo[0], "src/pkg/mod.py", '"""A module."""\n', "")
    assert "import-time code changed" in (_select(repo).fallback or "")


def _with_map_rows(map_dir: Path, *statements: tuple[str, tuple[object, ...]]) -> None:
    with contextlib.closing(sqlite3.connect(map_dir / "map.sqlite")) as db, db:
        for statement, values in statements:
            db.execute(statement, values)


def test_a_test_that_failed_in_the_build_is_always_selected(repo) -> None:
    """B-17: its line set stops where it failed, so no change can be shown not to reach it."""
    root, base, map_dir = repo
    _with_map_rows(map_dir, ("UPDATE tests SET outcome = 'failed' WHERE nodeid = ?", (T4,)))
    _edit(root, "src/pkg/mod.py", "    y = x + 1", "    y = x + 2")
    assert _select(repo).nodes == {T1, T4}


def test_an_unsure_test_the_run_deselects_selects_nothing(repo, monkeypatch) -> None:
    """S19: gate.sh deselects two wall-time tests that also failed in the map build; as unsure
    tests they pulled their whole files (the forty reference runs) into every selected gate."""
    root, base, map_dir = repo
    _with_map_rows(map_dir, ("UPDATE tests SET outcome = 'failed' WHERE nodeid = ?", (T4,)))
    _edit(root, "src/pkg/mod.py", "    y = x + 1", "    y = x + 2")
    assert ti.select(base, map_dir, cwd=root, deselected=frozenset({T4})).nodes == {T1}
    monkeypatch.setenv("PYTEST_ADDOPTS", f"-q --deselect {T4} --deselect=tests/x.py::t")
    assert ti._deselected(["--timeout=9", "--deselect", "tests/y.py::u"]) == {
        T4,
        "tests/x.py::t",
        "tests/y.py::u",
    }
    seen: list[list[str]] = []

    def fake_call(command: list[str], *, stdout, **_: object) -> int:
        seen.append(Path(command[-1].removeprefix("@")).read_text().split())
        stdout.write("1 passed in 0.1s\n")
        stdout.flush()
        return 0

    monkeypatch.setattr(ti.subprocess, "call", fake_call)
    assert ti.run(base, map_dir, root.parent / "run.log", [], root) == 0
    assert seen == [["tests/test_a.py"]]
    monkeypatch.delenv("PYTEST_ADDOPTS")
    assert ti.run(base, map_dir, root.parent / "run.log", [], root) == 0
    assert seen[-1] == ["tests/test_a.py", "tests/test_b.py"]


def test_an_unlinked_fixture_selects_its_test_module_or_falls_back(repo) -> None:
    """B-17: a module's fixture requested through `request.getfixturevalue` links no test in a map
    built before B-17; its module is known, a conftest fixture's users are not."""
    root, base, map_dir = repo
    data = ti.MapData()
    data.meta = {"base": base, "tree": ti.tree_of(base, root)}
    data.tests = {T1: "passed"}
    data.add_lines(
        "src/pkg/mod.py",
        "fixture:tests/test_c.py::real",
        ti.numbits([_lines(MODULE, "        return count")[0]]),
    )
    data.add_lines(
        "src/pkg/mod.py", "fixture:tests::orphan", ti.numbits(_lines(MODULE, "    return 0"))
    )
    data.write(map_dir / "map.sqlite")
    _edit(root, "src/pkg/mod.py", "        return count", "        return count + 0")
    assert _select(repo).nodes == {"tests/test_c.py"}
    _edit(root, "src/pkg/mod.py", "    return 0", "    return -1")
    assert "which no test uses" in (_select(repo).fallback or "")


def test_runtime_links_fixtures_requested_while_a_test_runs(tmp_path: Path) -> None:
    """B-17: `_shared_fixtures` sees a module fixture a test requests via `getfixturevalue`."""
    (tmp_path / "test_dyn.py").write_text(
        "import pytest\n\n\n"
        "@pytest.fixture(scope='module')\ndef shared():\n    return 1\n\n\n"
        "@pytest.fixture(scope='session')\ndef named():\n    return 2\n\n\n"
        "@pytest.fixture\ndef local():\n    return 3\n\n\n"
        "def test_static(named, local):\n    pass\n\n\n"
        "def test_dynamic(request):\n    assert request.getfixturevalue('shared') == 1\n"
    )
    (tmp_path / "recorder.py").write_text(
        "import importlib.util, json, os, pytest\n"
        "spec = importlib.util.spec_from_file_location('rt', os.environ['RUNTIME'])\n"
        "rt = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(rt)\n"
        "seen = {}\n\n\n"
        "@pytest.hookimpl(wrapper=True)\n"
        "def pytest_runtest_teardown(item, nextitem):\n"
        "    seen[item.nodeid] = sorted(rt._shared_fixtures(item))\n"
        "    return (yield)\n\n\n"
        "def pytest_sessionfinish(session):\n"
        "    open('seen.json', 'w').write(json.dumps(seen))\n"
    )
    environment = dict(
        os.environ,
        RUNTIME=str(ROOT / "scripts" / "test_impact_runtime.py"),
        PYTHONPATH=str(tmp_path),
    )
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-p",
            "recorder",
            "test_dyn.py",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert json.loads((tmp_path / "seen.json").read_text()) == {
        "test_dyn.py::test_static": ["fixture:test_dyn.py::named"],
        "test_dyn.py::test_dynamic": ["fixture:test_dyn.py::shared"],
    }


# -- fallbacks -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("old", "new", "reason"),
    [
        ("LIMIT = 3", "LIMIT = 4", "import-time code changed"),
        ("def f(x):", "def f(x, z=0):", "import-time code changed"),
        ('    return "import time"', '    return "boot"', "import or collection time"),
        (
            "        return 2\n",
            "        return 2\n\n    def method(self):\n        return 9\n",
            "import-time",
        ),
    ],
    ids=["module-constant", "def-header", "collection", "override"],
)
def test_import_time_changes_fall_back(repo, old: str, new: str, reason: str) -> None:
    _edit(repo[0], "src/pkg/mod.py", old, new)
    assert reason in (_select(repo).fallback or "")


@pytest.mark.parametrize(
    ("name", "reason"),
    [
        ("tests/conftest.py", "conftest.py"),
        ("tests/a_support.py", "support module"),
        ("tests/support/helper.py", "support module"),
        ("tests/data.json", "not a test module"),
        ("data/unseen.txt", "never seen"),
        ("src/pkg/unseen.py", "never seen"),
        ("data/boot.json", "import or collection time"),
    ],
)
def test_path_rules_fall_back(repo, name: str, reason: str) -> None:
    (repo[0] / name).write_text((repo[0] / name).read_text() + "\n# changed\n")
    assert reason in (_select(repo).fallback or "")


def test_the_pytest_section_of_pyproject_falls_back(repo) -> None:
    _edit(repo[0], "pyproject.toml", 'testpaths = ["tests"]', 'testpaths = ["t"]')
    assert "pytest section" in (_select(repo).fallback or "")


def test_another_pyproject_section_maps_through_the_open_record(repo) -> None:
    _edit(repo[0], "pyproject.toml", 'name = "x"', 'name = "y"')
    assert _select(repo).nodes == {T3}


@pytest.mark.parametrize("kind", ["new", "deleted", "untracked"])
def test_new_or_deleted_files_fall_back(repo, kind: str) -> None:
    root = repo[0]
    if kind == "deleted":
        (root / "data/table.yaml").unlink()
    else:
        (root / "src/pkg/new.py").write_text("x = 1\n")
        if kind == "new":
            _git(root, "add", "src/pkg/new.py")
    assert "new or deleted file" in (_select(repo).fallback or "")


def test_a_base_that_is_not_an_ancestor_falls_back(repo) -> None:
    root, base, map_dir = repo
    _git(root, "checkout", "-q", "--orphan", "other")
    _git(root, "commit", "-q", "-m", "unrelated")
    assert "not an ancestor" in (_select(repo).fallback or "")


def test_a_missing_or_foreign_map_falls_back(repo, tmp_path: Path) -> None:
    root, base, map_dir = repo
    assert "no map" in (ti.select(base, tmp_path / "nowhere", cwd=root).fallback or "")
    (root / "docs/guide.md").write_text("changed\n")
    _git(root, "commit", "-q", "-am", "next")
    head = _git(root, "rev-parse", "HEAD").strip()
    assert "is not of base" in (ti.select(head, map_dir, cwd=root).fallback or "")


def test_a_partial_map_falls_back(repo) -> None:
    root, base, map_dir = repo
    data = ti.MapData(meta={"base": base, "tree": ti.tree_of(base, root), "pytest_args": "x"})
    data.write(map_dir / "map.sqlite")
    assert "partial run" in (_select(repo).fallback or "")


# -- test modules and the open record --------------------------------------------------------------


def test_a_changed_test_body_selects_its_module(repo) -> None:
    _edit(repo[0], "tests/test_a.py", "    assert True", "    assert 1")
    assert _select(repo).nodes == {"tests/test_a.py"}


def test_module_level_code_of_a_test_module_falls_back(repo) -> None:
    _edit(repo[0], "tests/test_a.py", "CONSTANT = 1", "CONSTANT = 2")
    assert "import-time code changed" in (_select(repo).fallback or "")


def test_a_data_file_selects_the_tests_that_opened_it(repo) -> None:
    _edit(repo[0], "data/table.yaml", "a: 1", "a: 2")
    assert _select(repo).nodes == {T2}


def test_docs_select_only_their_readers(repo) -> None:
    root = repo[0]
    _edit(root, "docs/other.md", "other", "changed")
    assert _select(repo).nodes == set() and _select(repo).fallback is None
    _edit(root, "docs/guide.md", "guide", "changed")
    assert _select(repo).nodes == {T1}


@pytest.mark.parametrize("kind", ["added", "deleted"])
def test_an_added_or_deleted_docs_file_falls_back(repo, kind: str) -> None:
    """B-16: tests glob the docs tree (test_t02_identity.py reads docs/adr/0007-*.md)."""
    root = repo[0]
    if kind == "added":
        (root / "docs/new.md").write_text("new\n")
    else:
        (root / "docs/other.md").unlink()
    assert "new or deleted file" in (_select(repo).fallback or "")


@pytest.mark.parametrize("kind", ["modified", "added", "deleted"])
@pytest.mark.parametrize("tree", [".codehealth", ".claude"])
def test_campaign_tooling_neither_falls_back_nor_selects(repo, tree: str, kind: str) -> None:
    """S19: a change under .codehealth/ or .claude/ is ignored; other changes still select."""
    root = repo[0]
    existing = {".codehealth": ".codehealth/config.toml", ".claude": ".claude/skills/s/SKILL.md"}
    if kind == "modified":
        _edit(root, existing[tree], "\n", "\nchanged\n")
    elif kind == "deleted":
        (root / existing[tree]).unlink()
    else:
        (root / tree / "new.toml").write_text("new = 1\n")
    assert _select(repo).nodes == set() and _select(repo).fallback is None
    _edit(root, "docs/guide.md", "guide", "changed")
    assert _select(repo).nodes == {T1}


# -- a step-relative selection (S19, `--since`) ---------------------------------------------------


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD").strip()


def _since(repo_fixture: tuple[Path, str, Path], since: str) -> object:
    repo, base, map_dir = repo_fixture
    return ti.select(base, map_dir, cwd=repo, since=since)


def _gated_history(root: Path) -> str:
    """An earlier, gated commit with every sticky cause: a new file, import-time code, a file read
    at collection time and a body change in another module."""
    (root / "src/pkg/new.py").write_text("x = 1\n")
    _edit(root, "src/pkg/mod.py", "LIMIT = 3", "LIMIT = 4")
    (root / "data/boot.json").write_text((root / "data/boot.json").read_text() + "\n")
    _edit(root, "src/pkg/twins.py", '        return "second"', '        return "2nd"')
    return _commit(root, "an earlier gated step")


def test_since_judges_only_the_step_and_not_what_it_inherits(repo) -> None:
    root = repo[0]
    earlier = _gated_history(root)
    assert _select(repo).fallback is not None
    assert _since(repo, earlier).nodes == set() and _since(repo, earlier).fallback is None
    _edit(root, "docs/guide.md", "guide", "changed")
    assert _since(repo, earlier).nodes == {T1} and _since(repo, earlier).fallback is None
    # Committed or not, the step is HEAD's working tree against `since`.
    _commit(root, "the step")
    assert _since(repo, earlier).nodes == {T1}


def test_since_selects_a_file_by_its_cumulative_change_from_the_base(repo) -> None:
    """The map's lines are the base's: a file the step touches brings its earlier hunks along (a
    superset); a file only earlier steps touched brings nothing."""
    root = repo[0]
    _edit(root, "src/pkg/mod.py", "    total = 0\n", "    total = 0\n    total -= 1\n")
    _edit(root, "src/pkg/twins.py", '        return "second"', '        return "2nd"')
    earlier = _commit(root, "an earlier gated step in g and in twins")
    _edit(root, "src/pkg/mod.py", "    y = x + 1", "    y = x + 2")
    assert _since(repo, earlier).nodes == {T1, T2}
    assert _select(repo).nodes == {T1, T2}


@pytest.mark.parametrize(
    ("kind", "reason"),
    [
        ("new-file", "new or deleted file"),
        ("deleted-file", "new or deleted file"),
        ("import-time", "import-time code changed"),
        ("collection", "import or collection time"),
        ("conftest", "conftest.py"),
        ("edits-a-file-the-map-never-saw", "new or deleted file"),
        ("restores-the-base", "restores the base's content"),
    ],
)
def test_since_still_falls_back_on_the_steps_own_causes(repo, kind: str, reason: str) -> None:
    root = repo[0]
    earlier = _gated_history(root)
    if kind == "new-file":
        (root / "src/pkg/newer.py").write_text("y = 1\n")
    elif kind == "deleted-file":
        (root / "data/table.yaml").unlink()
    elif kind == "import-time":
        _edit(root, "src/pkg/mod.py", "def f(x):", "def f(x, z=0):")
    elif kind == "collection":
        _edit(root, "src/pkg/mod.py", '    return "import time"', '    return "boot"')
    elif kind == "conftest":
        (root / "tests/conftest.py").write_text((root / "tests/conftest.py").read_text() + "\n#\n")
    elif kind == "edits-a-file-the-map-never-saw":
        (root / "src/pkg/new.py").write_text("x = 2\n")
    else:
        _edit(root, "src/pkg/twins.py", '        return "2nd"', '        return "second"')
    assert reason in (_since(repo, earlier).fallback or "")


def test_since_keeps_an_inherited_import_time_change_in_the_steps_own_file_quiet(repo) -> None:
    """One file, two hunks: the earlier step's module constant (import-time) and this step's body
    line. The inherited hunk does not fall back; next to the step's line it does."""
    root = repo[0]
    earlier = _gated_history(root)  # LIMIT = 3 -> 4 in src/pkg/mod.py
    _edit(root, "src/pkg/mod.py", "    total = 0\n", "    total = 0\n    total -= 1\n")
    assert _select(repo).fallback is not None
    assert _since(repo, earlier).nodes == {T2} and _since(repo, earlier).fallback is None
    _edit(root, "src/pkg/mod.py", "LIMIT = 4\n", "LIMIT = 4\nOTHER = 5\n")
    assert "import-time code changed" in (_since(repo, earlier).fallback or "")


def test_import_time_by_file_selects_the_tests_that_ran_the_file(repo) -> None:
    """The approximate rule: the step's own import-time change selects every test that executed a
    line of the file; collection-time code, a file no test ran and a new file still fall back."""
    root, base, map_dir = repo
    earlier = _gated_history(root)

    def by_file() -> object:
        return ti.select(base, map_dir, cwd=root, since=earlier, by_file=True)

    _edit(root, "src/pkg/mod.py", "def f(x):", "def f(x, z=0):")
    assert "import-time code changed" in (_since(repo, earlier).fallback or "")
    assert by_file().fallback is None and by_file().nodes == {T1, T2, T3, T4}
    _edit(root, "src/pkg/mod.py", '    return "import time"', '    return "boot"')
    assert "import or collection time" in (by_file().fallback or "")
    _git(root, "checkout", "-q", "--", "src/pkg/mod.py")
    (root / "src/pkg/newer.py").write_text("y = 1\n")
    assert "new or deleted file" in (by_file().fallback or "")
    # Without --since the rule is off: the cumulative selection stays exact.
    assert ti.select(base, map_dir, cwd=root, by_file=True).fallback is not None
    with pytest.raises(SystemExit):
        ti.main(["select", "--base", base, "--import-time-by-file"])


def test_since_must_lie_between_the_base_and_head(repo) -> None:
    root, base, _ = repo
    earlier = _gated_history(root)
    _git(root, "checkout", "-q", "-b", "side", base)
    (root / "side.txt").write_text("side\n")
    side = _commit(root, "not an ancestor of the step")
    _git(root, "checkout", "-q", "main")
    assert "not between the base and HEAD" in (_since(repo, side).fallback or "")
    _git(root, "checkout", "-q", "side")
    assert "not between the base and HEAD" in (_since(repo, earlier).fallback or "")


def test_since_on_the_command_line(repo, capsys: pytest.CaptureFixture[str]) -> None:
    root, base, map_dir = repo
    earlier = _gated_history(root)
    _edit(root, "docs/guide.md", "guide", "changed")
    arguments = ["--repo", str(root), "select", "--base", base, "--map", str(map_dir)]
    assert ti.main(arguments) == ti.EXIT_FULL
    capsys.readouterr()
    assert ti.main([*arguments, "--since", earlier]) == 0
    assert capsys.readouterr().out.split() == ["tests/test_a.py"]


#: A string literal naming a campaign-tooling tree as a path component.
TOOLING_PATH = re.compile(r"(^|/)\.(codehealth|claude)(/|$)")
#: The selector and its tests name the prefixes; they do not read the trees.
TOOLING_NAMERS = ("scripts/test_impact.py", "tests/test_s16_test_impact.py")


def _tooling_readers(root: Path) -> list[str]:
    """Python files under tests/, src/, scripts/ and benchmarks/ with a string literal that names
    .codehealth or .claude as a path component (`root / ".claude"` included)."""
    found = []
    for directory in ("tests", "src", "scripts", "benchmarks"):
        for path in sorted((root / directory).rglob("*.py")):
            where = path.relative_to(root).as_posix()
            if where in TOOLING_NAMERS:
                continue
            text = path.read_text(encoding="utf-8")
            if ".codehealth" not in text and ".claude" not in text:
                continue  # the literal cannot be there; parsing every file costs seconds
            tree = ast.parse(text, where)
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if TOOLING_PATH.search(node.value):
                        found.append(f"{where}:{node.lineno}")
    return found


def test_no_test_reads_campaign_tooling(tmp_path: Path) -> None:
    """The premise of TOOLING_PREFIXES: no code a test runs names .codehealth/ or .claude/.

    String literals in the Python of tests/, src/, scripts/ and benchmarks/ are scanned, not data
    files: two fixtures record absolute worktree paths (".../.claude/worktrees/...") that no test
    opens. Falsifier, checked below: a test module that opens ".codehealth/config.toml" is found.
    A path assembled from fragments ('".clau" + "de"') is not seen; the map's open record is.
    """
    assert _tooling_readers(ROOT) == []
    (tmp_path / "tests").mkdir()
    planted = 'open(".codehealth/config.toml")\nP = ".claude.json"\n'
    (tmp_path / "tests/test_x.py").write_text(planted)
    assert _tooling_readers(tmp_path) == ["tests/test_x.py:1"]


def test_a_docs_script_maps_like_source_once_the_map_measures_docs(repo) -> None:
    """B-16: a map without `source_dirs` did not measure docs/*.py, so a change there falls back."""
    root, base, map_dir = repo
    _edit(root, "docs/tool.py", "return 1", "return 2")
    assert "does not measure its directory" in (_select(repo).fallback or "")
    data = ti.MapData()
    data.meta = {"base": base, "tree": ti.tree_of(base, root), "source_dirs": "src,tests,docs"}
    data.tests = {T1: "passed", T3: "passed"}
    data.add_lines("docs/tool.py", T3, ti.numbits([2]))
    data.add_lines("docs/tool.py", ti.COLLECTION, ti.numbits([1]))
    data.write(map_dir / "map.sqlite")
    assert _select(repo).nodes == {T3}


# -- the command line ------------------------------------------------------------------------------


def test_exit_codes_and_output(repo, capsys: pytest.CaptureFixture[str], monkeypatch) -> None:
    root, base, map_dir = repo
    monkeypatch.setattr(ti, "ROOT", root)
    monkeypatch.chdir(root)
    _edit(root, "src/pkg/mod.py", "    y = x + 1", "    y = x + 2")
    assert ti.main(["select", "--base", base, "--map", str(map_dir), "--nodes"]) == 0
    assert capsys.readouterr().out == f"{T1}\n"
    # B-11: the default output is the whole test file of every selected node id.
    assert ti.main(["select", "--base", base, "--map", str(map_dir)]) == 0
    assert capsys.readouterr().out == "tests/test_a.py\n"
    _edit(root, "src/pkg/mod.py", "LIMIT = 3", "LIMIT = 4")
    assert ti.main(["select", "--base", base, "--map", str(map_dir)]) == ti.EXIT_FULL == 3
    assert "full suite: src/pkg/mod.py:" in capsys.readouterr().err


def test_whole_files_widens_node_ids_and_keeps_a_fallback() -> None:
    """B-11: a module-scoped fixture or cache makes a file's later tests depend on lines only the
    first test records, so a selected node id runs its whole file."""
    widened = ti.Selection({T1, T3, T4, "tests/test_c.py"}).whole_files()
    assert widened.nodes == {"tests/test_a.py", "tests/test_b.py", "tests/test_c.py"}
    assert widened.fallback is None
    assert ti.Selection(fallback="why").whole_files() == ti.Selection(fallback="why")


def test_select_lines(repo, capsys: pytest.CaptureFixture[str]) -> None:
    root, base, map_dir = repo
    line = _lines(MODULE, '    return "fixture work"')[0]
    selection = ti.select_lines(f"src/pkg/mod.py:{line}-{line}", base, map_dir, cwd=root)
    assert selection.nodes == {T3, T4}
    collection = ti.select_lines(f"src/pkg/mod.py:{line - 1}-{line + 30}", base, map_dir, cwd=root)
    assert "import or collection time" in (collection.fallback or "")


# -- run (B-12) ------------------------------------------------------------------------------------


def test_runs_keep_the_xdist_serial_files_out_of_the_xdist_call(monkeypatch) -> None:
    serial = "tests/test_serial.py"
    monkeypatch.setattr(ti, "XDIST_SERIAL", (serial,))
    fallback = ti.Selection(fallback="why")
    assert ti._runs(fallback, 0) == [([], [])]
    assert ti._runs(fallback, 4) == [(["-n", "4", f"--ignore={serial}"], []), ([serial], [])]
    mixed = ti.Selection({"tests/test_a.py", serial})
    assert ti._runs(mixed, 0) == [([], ["tests/test_a.py", serial])]
    assert ti._runs(mixed, 4) == [(["-n", "4"], ["tests/test_a.py"]), ([], [serial])]
    assert ti._runs(ti.Selection({serial}), 4) == [([], [serial])]
    assert ti._runs(ti.Selection({"tests/test_a.py"}), 4) == [(["-n", "4"], ["tests/test_a.py"])]


@pytest.mark.parametrize(
    ("codes", "expected"), [((0, 0), 0), ((0, 1), 1), ((1, 0), 1), ((0, 5), 0)]
)
def test_run_with_workers_makes_two_calls_and_one_line(
    repo, tmp_path: Path, monkeypatch, capsys, codes: tuple[int, int], expected: int
) -> None:
    root, base, map_dir = repo
    monkeypatch.setattr(ti, "XDIST_SERIAL", ("tests/test_a.py",))
    _edit(root, "src/pkg/mod.py", "LIMIT = 3", "LIMIT = 4")  # a fallback: both calls run
    calls: list[list[str]] = []

    def fake_call(command: list[str], *, stdout, **_: object) -> int:
        calls.append(command)
        first = len(calls) == 1
        stdout.write("..\n2 passed, 1 skipped in 0.5s\n" if first else "1 failed in 0.1s\n")
        stdout.flush()
        return codes[len(calls) - 1]

    monkeypatch.setattr(ti.subprocess, "call", fake_call)
    log = tmp_path / "run.log"
    assert ti.run(base, map_dir, log, ["--timeout=9"], root, workers=3) == expected
    assert len(calls) == 2
    assert calls[0][-4:] == ["--timeout=9", "-n", "3", "--ignore=tests/test_a.py"]
    assert calls[1][-2:] == ["--timeout=9", "tests/test_a.py"]
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 1 and "2 passed, 1 skipped, 1 failed" in out[0]
    assert ("PASS" if expected == 0 else f"FAIL (exit {expected})") in out[0]


@pytest.mark.parametrize(
    ("codes", "killed"),
    [((0, -9), "call 1 signal 9"), ((1, -11), "call 1 signal 11"), ((-9, 5), "call 0 signal 9")],
)
def test_a_killed_call_fails_the_run_as_exit_3_naming_it(
    repo, tmp_path: Path, monkeypatch, capsys, codes: tuple[int, int], killed: str
) -> None:
    """A call killed by a signal (subprocess returns -signal) was read by `max`: [0, -9] passed
    and [1, -11] exited 1. Any killed call makes the run exit 3, pytest's INTERNAL_ERROR."""
    root, base, map_dir = repo
    monkeypatch.setattr(ti, "XDIST_SERIAL", ("tests/test_a.py",))
    _edit(root, "src/pkg/mod.py", "LIMIT = 3", "LIMIT = 4")  # a fallback: both calls run
    calls: list[list[str]] = []

    def fake_call(command: list[str], *, stdout, **_: object) -> int:
        calls.append(command)
        if codes[len(calls) - 1] >= 0:
            stdout.write("2 passed in 0.5s\n")
            stdout.flush()
        return codes[len(calls) - 1]

    monkeypatch.setattr(ti.subprocess, "call", fake_call)
    assert ti.run(base, map_dir, tmp_path / "run.log", [], root, workers=3) == ti.INTERNAL_ERROR
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 1 and "FAIL (exit 3)" in out[0] and f"killed: {killed}," in out[0]


def test_run_full_runs_the_suite_and_since_reaches_the_selection(
    repo, tmp_path: Path, monkeypatch, capsys
) -> None:
    """`--full` selects nothing (a merge check); `--since` and `--import-time-by-file` reach
    `select` from the command line."""
    root, base, map_dir = repo
    earlier = _gated_history(root)
    _edit(root, "docs/guide.md", "guide", "changed")
    calls: list[list[str]] = []

    def fake_call(command: list[str], *, stdout, **_: object) -> int:
        calls.append(command)
        stdout.write("1 passed in 0.1s\n")
        stdout.flush()
        return 0

    monkeypatch.setattr(ti.subprocess, "call", fake_call)
    common = ["--repo", str(root), "run", "--base", base, "--map", str(map_dir)]
    log = ["--log", str(tmp_path / "run.log")]
    assert ti.main([*common, *log, "--since", earlier, "--import-time-by-file"]) == 0
    assert "selected 1, fallback no" in capsys.readouterr().out
    assert calls[-1][-1].startswith("@")
    assert ti.main([*common, *log, "--since", earlier, "--full"]) == 0
    captured = capsys.readouterr()
    assert "selected all, fallback yes" in captured.out and "full suite: --full" in captured.err
    assert not calls[-1][-1].startswith("@")


def test_run_exclude_from_thins_a_selection_and_names_what_it_left_out(
    repo, tmp_path: Path, monkeypatch, capsys
) -> None:
    """S19 (Decision Desk card ofs-s19-gate-proposal-2): a step gate leaves the listed files to the
    merge check and says so; `--full` and a fallback run everything; the list is checked."""
    root, base, map_dir = repo
    _edit(root, "docs/guide.md", "guide", "changed")
    (selected,) = ti.select(base, map_dir, cwd=root).whole_files().nodes
    other = "tests/test_b.py"  # in the map, on disk here as a file git ignores
    (root / other).write_text("def test_three():\n    pass\n")
    (root / ".git" / "info" / "exclude").write_text("tests/test_b.py\n")
    calls: list[list[str]] = []

    def fake_call(command: list[str], *, stdout, **_: object) -> int:
        calls.append(command)
        stdout.write("1 passed in 0.1s\n")
        stdout.flush()
        return 0

    monkeypatch.setattr(ti.subprocess, "call", fake_call)
    listing = tmp_path / "excluded.txt"
    common = ["--repo", str(root), "run", "--base", base, "--map", str(map_dir)]
    common += ["--log", str(tmp_path / "run.log"), "--exclude-from", str(listing)]

    listing.write_text(f"# heavy files\n{other}  # not selected here\n")
    assert ti.main(common) == 0
    out = capsys.readouterr().out
    assert f"excluded {other}: not selected" in out and "selected 1, fallback no" in out
    assert len(calls) == 1

    listing.write_text(f"{selected}\n{other}\n")
    assert ti.main(common) == 0
    out = capsys.readouterr().out
    assert "2 files listed, 1 of them selected and not run here" in out
    assert f"excluded {selected}: selected, not run" in out
    assert "selected 0, fallback no, nothing to run" in out
    assert len(calls) == 1  # pytest was not called again

    assert ti.main([*common, "--full"]) == 0  # the merge check: the list is not read
    out = capsys.readouterr().out
    assert "excluded" not in out and "selected all, fallback yes" in out
    assert not calls[-1][-1].startswith("@")

    (root / "tests" / "test_added.py").write_text("def test_new():\n    pass\n")
    assert ti.main(common) == 0  # a fallback to the full suite keeps every file
    out = capsys.readouterr().out
    assert "not applied, the full suite runs" in out and "selected all, fallback yes" in out
    (root / "tests" / "test_added.py").unlink()

    listing.write_text("tests/test_no_such_file.py\n")
    with pytest.raises(SystemExit, match="is not a test file"):
        ti.main(common)
    (root / "tests" / "test_doc_examples.py").write_text("def test_docs():\n    pass\n")
    listing.write_text("tests/test_doc_examples.py\n")
    with pytest.raises(SystemExit, match="stays at step cadence"):
        ti.main(common)


def test_run_refuses_workers_after_the_separator(repo, tmp_path: Path) -> None:
    root, base, map_dir = repo
    for extra in (["-n", "4"], ["-n4"], ["--numprocesses=4"]):
        with pytest.raises(SystemExit, match="--workers"):
            ti.run(base, map_dir, tmp_path / "run.log", extra, root)


# -- the recall driver -----------------------------------------------------------------------------


def test_recall_cases_cover_the_review_rules_and_apply_their_edits(tmp_path: Path) -> None:
    """S6 of docs/reviews/S16-review.md: a case per rule B-13 to B-16, shared state, a refactor."""
    recall = _load("s16_recall")
    ids = {case for case, _, _ in recall.CASES}
    wanted = {"s1-shadow-import", "s2-render-twin", "s3-nonlocal", "s4-docs-added"}
    assert wanted | {"shared-catalogue", "refactor-extract-authz"} <= ids
    (tmp_path / "a.py").write_text("x = 1\ny = 2\n")
    (tmp_path / "docs").mkdir()
    recall._apply("c", tmp_path, [("a.py", "y = 2", "y = 3"), ("docs/n.md", "", "new\n")])
    assert (tmp_path / "a.py").read_text() == "x = 1\ny = 3\n"
    assert (tmp_path / "docs/n.md").read_text() == "new\n"
    with pytest.raises(SystemExit, match="exists at the base"):
        recall._apply("c", tmp_path, [("a.py", "", "z\n")])
    with pytest.raises(SystemExit, match="occurs 0 times"):
        recall._apply("c", tmp_path, [("a.py", "y = 2", "y = 4")])
