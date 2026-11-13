"""S16: test-impact selection (scripts/test_impact.py, docs/test-impact.md).

Every rule runs on a synthetic repository and a synthetic map, so these tests need neither coverage
nor a built map: they run in the main venv and in CI. The map build itself needs the test-map venv
(requirements-testmap.lock) and is exercised by the recall check (docs/S16_DECISIONS.md).
"""

from __future__ import annotations

import importlib.util
import os
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

FILES = {
    "src/pkg/mod.py": MODULE,
    "src/pkg/unseen.py": "def u():\n    return 1\n",
    "tests/test_a.py": TEST_MODULE,
    "tests/conftest.py": "",
    "tests/a_support.py": "X = 1\n",
    "tests/support/helper.py": "Y = 1\n",
    "tests/data.json": "{}\n",
    "docs/guide.md": "guide\n",
    "docs/other.md": "other\n",
    "data/table.yaml": "a: 1\n",
    "data/boot.json": "{}\n",
    "data/unseen.txt": "x\n",
    "pyproject.toml": PYPROJECT,
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
    (root / "docs/new.md").write_text("new\n")
    assert _select(repo).nodes == set() and _select(repo).fallback is None
    _edit(root, "docs/guide.md", "guide", "changed")
    assert _select(repo).nodes == {T1}


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


def test_run_refuses_workers_after_the_separator(repo, tmp_path: Path) -> None:
    root, base, map_dir = repo
    for extra in (["-n", "4"], ["-n4"], ["--numprocesses=4"]):
        with pytest.raises(SystemExit, match="--workers"):
            ti.run(base, map_dir, tmp_path / "run.log", extra, root)
