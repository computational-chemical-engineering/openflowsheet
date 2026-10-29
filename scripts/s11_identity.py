"""S11 gate G1, identity in three families (design note `docs/derivations/S11-design.md` §6.2 G1,
§2.2). S11.

- **Family A, the 52 configurations** (`s08_identity.column_configurations()` and S01 C1–C5) with
  S08's fields (`column_fields` / `cascade_fields`, and S08's `stage_a` digest wherever an answer
  carries `reentry`): `s10c_identity.column_digests`'s rule.
- **Family B, the PH kernel:** every `ph_state` call of the T05/T05b test modules, run
  in-process: `s10c_identity.ph_digests`'s rule (S10-C's family). That pytest run must exit 0.
- **Family C, the binder:** every `bind_revision_flowsheet` call of the whole suite. Both trees
  run every `tests/test_*.py` in `SHARDS` pytest processes, the files dealt round-robin from the
  **base tree's** sorted list (files only on the branch run in one extra shard), with
  `s11_identity_recorder` logging each call by (test node id, call index): a SHA-256 over the
  document's SHA-256, the outcome kind, code and hint, and for a binding the `ProblemSpec` ids,
  kinds and parameters (`float.hex`). Every shard must exit 0 in both trees.

The verdict: every key present in both trees has an equal digest, and no key is present in the
base tree only — except the keys of the tests §8.3 amends on purpose (`AMENDED_TESTS`), which are
not judged. Keys on the branch only (new tests) are counted, not judged. Families A and B must
have the same keys in both trees, and family A all 52 configurations.

The two trees are the base (default `8c34ecb0`, §6) in a detached worktree this script creates and
removes (or `--base-tree`), and this checkout; each subprocess imports `openflowsheet`, the tests
and `scripts/` from its own tree only. Families A and B run this script's `s10c_identity`
(the copy beside it) in both trees; the recorder, which the base tree may lack, is copied to a
directory of its own. One line is printed:

    S11-IDENTITY PASS n=<N> changed=[]

`n` counts the keys compared (A, `stage_a`, B, and C's shared keys outside `AMENDED_TESTS`); the
exit code is 0 on PASS, 1 on FAIL (the line then names the keys and what else differed). The S08
and S10-C lines (S11.A23) and the older `tests/test_*identity*.py` gates run on their own.

Usage:
    PYTHONPATH=src .venv/bin/python scripts/s11_identity.py [--base 8c34ecb0] [--base-tree PATH]
        [--keep DIR] [--shards 16]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
#: The base of every S11 identity comparison (§6): `main` after S08b's merge.
MERGE_BASE = "8c34ecb0"
#: S08's configurations: 47 columns (S08 §3 F3) and S01 C1–C5.
CONFIGURATIONS = 52
#: The whole-suite shards per tree (family C).
SHARDS = 16
_RECORDER = "s11_identity_recorder"
#: §8.3: the tests whose assertions S11 reverses on purpose, as node-id prefixes. A test function
#: (`<file>::<name>`, its parametrisations included) where §8.3 gives lines — the functions that
#: span them at the base, or that read the constant there — and the whole file where §8.3 names
#: only the file. Family C does not judge their keys.
AMENDED_TESTS: tuple[str, ...] = (
    # tests/test_m02_join.py:88-102 (A1, I1)
    "tests/test_m02_join.py::test_the_registry_holds_the_twenty_one_models_each_on_its_own_basis",
    "tests/test_m02_join.py::test_the_selectable_bases_are_what_component_basis_returns",
    # tests/test_t08_w2_support_envelope.py:61-80 (A5, I1)
    "tests/test_t08_w2_support_envelope.py::test_a20_the_axes_equal_the_code",
    # tests/test_t08_w2_support_envelope.py:335-342, `LIBRARY_ONLY_PROVIDERS` (A5, I1)
    "tests/test_t08_w2_support_envelope.py::"
    "test_c3_the_library_only_providers_are_unselectable_with_their_u02_items",
    "tests/test_t08_w2_support_envelope.py::test_c3_each_broken_condition_is_one_problem",
    # tests/test_s05_envelope.py:216-221 (A5; S05 A25)
    "tests/test_s05_envelope.py::test_a25_library_only_registration",
    # tests/test_s07_registration.py:157-165 (A5)
    "tests/test_s07_registration.py::test_a30_library_only_registration",
    # tests/test_s10_provider.py:688-696 (A5; S10 A27)
    "tests/test_s10_provider.py::test_a27_library_only_registration",
    # tests/test_t05_w1b_revision.py:84 (I1: 14 `syn001.*`)
    "tests/test_t05_w1b_revision.py::test_builders_hold_the_thirteen_models_of_the_table",
    # tests/test_t08_kinetic_cstr.py:217-218 (I1)
    "tests/test_t08_kinetic_cstr.py::test_b10_the_model_is_the_thirteenth_builder_with_its_signature",
    # tests/test_t08_w2_unsupported.py (the U04 column test; I1)
    "tests/test_t08_w2_unsupported.py",
    # tests/test_t07_w5c_signatures.py and tests/test_t08_w2_edge_identity.py sample tables (I1)
    "tests/test_t07_w5c_signatures.py",
    "tests/test_t08_w2_edge_identity.py",
    # tests/test_m07a_harvest.py:56, `HARVEST_SIZE` (I2)
    "tests/test_m07a_harvest.py::test_m07a_a50_the_harvest_size_is_the_quoted_one",
    # any test_l01_* assertion of len(SELECTABLE_BASES) == 2 (A1)
    "tests/test_l01_records.py::test_a22_the_live_build_does_not_select_pr_lib_v1",
    "tests/test_l01_retake.py::test_a27_1_the_installed_binder_has_no_library_basis",
    # tests/test_t08_b50_surface_content.py, its `list_models` surface (I1)
    "tests/test_t08_b50_surface_content.py::test_the_fixture_is_c7bbc98s_served_content",
    "tests/test_t08_b50_surface_content.py::test_b50_list_models_differs_by_the_kinetic_cstr_only",
    # R-841 (S11.A13 restated): the syn001/c1 refusals of models that gained an S11 basis name
    # every basis the model binds on.
    "tests/test_m02_join.py::test_syn001s_feed_to_sink_is_refused_on_the_c1_basis",
    "tests/test_m02_join.py::test_syn001s_splitter_is_refused_on_the_c1_basis",
    "tests/test_m02_join.py::test_a_model_with_no_same_function_model_on_the_other_basis_names_none",
)


def amended(key: str) -> bool:
    """Whether a family C key (`<node id>#<index>`) belongs to a test of `AMENDED_TESTS`."""
    node = key.rsplit("#", 1)[0]
    for prefix in AMENDED_TESTS:
        if "::" not in prefix:
            if node.startswith(f"{prefix}::"):
                return True
        elif node == prefix or node.startswith((f"{prefix}[", f"{prefix}::")):
            return True
    return False


# -- families A and B (run inside one tree) ------------------------------------------------------


def _s10c() -> ModuleType:
    """The `s10c_identity` beside this script, whichever tree the process imports from."""
    path = Path(__file__).resolve().with_name("s10c_identity.py")
    spec = importlib.util.spec_from_file_location("s10c_identity", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["s10c_identity"] = module
    spec.loader.exec_module(module)
    return module


def families_ab(tree: Path) -> dict[str, Any]:
    """Family A's digests and `stage_a` digests, family B's and its pytest exit, in this process."""
    import openflowsheet

    if not Path(openflowsheet.__file__).resolve().is_relative_to(tree.resolve()):
        raise SystemExit(f"openflowsheet is imported from {openflowsheet.__file__}, not {tree}")
    s10c = _s10c()
    columns, stage_a = s10c.column_digests()
    ph, exit_code = s10c.ph_digests(tree)
    return {"columns": columns, "stage_a": stage_a, "ph_state": ph, "pytest_exit": exit_code}


# -- the verdict ---------------------------------------------------------------------------------


def _verdict_ab(
    base: Mapping[str, Any], branch: Mapping[str, Any]
) -> tuple[list[str], list[str], int]:
    problems: list[str] = []
    changed: list[str] = []
    total = 0
    for family, label in (("columns", "A"), ("stage_a", "A.stage_a"), ("ph_state", "B")):
        old, new = base[family], branch[family]
        if set(old) != set(new):
            difference = sorted(set(old) ^ set(new))
            problems.append(f"{label} keys differ ({len(difference)}): {difference[:5]}")
        shared = set(old) & set(new)
        changed += sorted(f"{label}:{key}" for key in shared if old[key] != new[key])
        total += len(shared)
    if len(branch["columns"]) != CONFIGURATIONS:
        problems.append(f"A has {len(branch['columns'])} configurations, not {CONFIGURATIONS}")
    if not branch["ph_state"]:
        problems.append("B recorded no ph_state call")
    for key, found in (("base", base), ("branch", branch)):
        if found["pytest_exit"] != 0:
            problems.append(f"the {key} T05/T05b pytest run exited {found['pytest_exit']}")
    return problems, changed, total


def _verdict_c(
    base: Mapping[str, Any], branch: Mapping[str, Any]
) -> tuple[list[str], list[str], int]:
    problems: list[str] = []
    for key, found in (("base", base), ("branch", branch)):
        failed = [index for index, code in enumerate(found["exit"]) if code != 0]
        if failed:
            problems.append(f"C {key} shards {failed} exited non-zero")
    old, new = base["records"], branch["records"]
    judged = sorted(key for key in set(old) & set(new) if not amended(key))
    if not judged:
        problems.append("C recorded no shared binding")
    changed = [f"C:{key}" for key in judged if old[key] != new[key]]
    base_only = sorted(key for key in set(old) - set(new) if not amended(key))
    if base_only:
        problems.append(f"C base-only keys ({len(base_only)}): {base_only[:5]}")
    return problems, changed, len(judged)


def verdict(base: Mapping[str, Any], branch: Mapping[str, Any]) -> tuple[bool, str]:
    """§6.2 G1's rule on the two trees' records: (passed, the one line)."""
    problems_ab, changed_ab, total_ab = _verdict_ab(base["ab"], branch["ab"])
    problems_c, changed_c, total_c = _verdict_c(base["c"], branch["c"])
    changed = changed_ab + changed_c
    problems = problems_ab + problems_c
    if changed:
        problems.append(f"{len(changed)} digests differ")
    line = f"n={total_ab + total_c} changed=[{','.join(changed[:10])}]"
    if problems:
        return False, f"S11-IDENTITY FAIL {line} ({'; '.join(problems)})"
    return True, f"S11-IDENTITY PASS {line}"


# -- the driver ----------------------------------------------------------------------------------


def _git(*argv: str, cwd: Path = ROOT) -> str:
    return subprocess.run(
        ["git", *argv], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout.strip()


def _environment(tree: Path, parts: Sequence[str], *extra: Path) -> dict[str, str]:
    """`PYTHONPATH` from `tree` only (`parts` of it), then `extra` (the copied recorder)."""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        [*(str(tree / part) for part in parts), *map(str, extra)]
    )
    return environment


def shards(base_tree: Path, tree: Path, count: int) -> list[list[str]]:
    """The base tree's sorted test files dealt round-robin into `count` shards (dropping files
    `tree` lacks), then, when `tree` has files the base lacks, one extra shard of those."""

    def listed(where: Path) -> list[str]:
        return sorted(f"tests/{path.name}" for path in (where / "tests").glob("test_*.py"))

    base_files, files = listed(base_tree), set(listed(tree))
    dealt = [[name for name in base_files[index::count] if name in files] for index in range(count)]
    extra = sorted(files - set(base_files))
    return dealt + ([extra] if extra else [])


def _launch_c(
    tree: Path, plugin: Path, files: list[str], index: int, out: Path
) -> subprocess.Popen[bytes]:
    environment = _environment(tree, ("src", ""), plugin)
    environment.update(
        S11_IDENTITY_TREE=str(tree),
        S11_IDENTITY_SHARD=str(index),
        S11_IDENTITY_OUT=str(out / f"shard-{index}.json"),
    )
    command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", _RECORDER]
    with (out / f"shard-{index}.log").open("wb") as sink:
        return subprocess.Popen(
            [*command, *files], cwd=tree, env=environment, stdout=sink, stderr=subprocess.STDOUT
        )


def _launch_ab(tree: Path, out: Path) -> subprocess.Popen[bytes]:
    """This script's `--families-ab` mode on `tree` (`-P`: the script's own directory is not put
    on `sys.path`)."""
    with (out.with_suffix(".log")).open("wb") as sink:
        return subprocess.Popen(
            [
                sys.executable,
                "-P",
                str(Path(__file__).resolve()),
                "--families-ab",
                str(tree),
                str(out),
            ],
            cwd=tree,
            env=_environment(tree, ("src", "tests", "scripts", "")),
            stdout=sink,
            stderr=subprocess.STDOUT,
        )


def compare(base_tree: Path, scratch: Path, *, count: int) -> tuple[bool, str]:
    trees = {"base": base_tree, "branch": ROOT}
    plugin = scratch / "plugin"
    plugin.mkdir(exist_ok=True)
    shutil.copy2(Path(__file__).resolve().with_name(f"{_RECORDER}.py"), plugin)
    running: dict[str, tuple[subprocess.Popen[bytes], dict[int, subprocess.Popen[bytes]]]] = {}
    for key, tree in trees.items():
        (scratch / key).mkdir(exist_ok=True)
        dealt = shards(base_tree, tree, count)
        running[key] = (
            _launch_ab(tree, scratch / key / "families-ab.json"),
            {
                index: _launch_c(tree, plugin, files, index, scratch / key)
                for index, files in enumerate(dealt)
                if files
            },
        )
    found: dict[str, Any] = {}
    failure: str | None = None
    for key, (ab_run, c_runs) in running.items():
        ab_code = ab_run.wait()
        records: dict[str, str] = {}
        exits: list[int] = []
        for index, process in c_runs.items():
            code = process.wait()
            shard = scratch / key / f"shard-{index}.json"
            if not shard.exists():
                exits.append(code if code != 0 else -1)
                continue
            data = json.loads(shard.read_text())
            exits.append(code if code != 0 else int(data["exit"]))
            duplicated = set(records) & set(data["records"])
            if duplicated and failure is None:
                failure = f"S11-IDENTITY FAIL {key} keys in two shards: {sorted(duplicated)[:3]}"
            records.update(data["records"])
        if ab_code != 0 and failure is None:
            failure = f"S11-IDENTITY FAIL the {key} families A/B run exited {ab_code} (see log)"
        if failure is None:
            found[key] = {
                "ab": json.loads((scratch / key / "families-ab.json").read_text()),
                "c": {"records": records, "exit": exits},
            }
    if failure is not None:
        return False, failure
    return verdict(found["base"], found["branch"])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--base", default=MERGE_BASE, help=f"the base (default {MERGE_BASE})")
    parser.add_argument("--base-tree", type=Path, help="an existing checkout of --base")
    parser.add_argument("--keep", type=Path, help="keep the records and logs in this directory")
    parser.add_argument("--shards", type=int, default=SHARDS, help="whole-suite shards per tree")
    parser.add_argument("--families-ab", nargs=2, metavar=("TREE", "OUT"), help=argparse.SUPPRESS)
    arguments = parser.parse_args(argv)
    if arguments.families_ab:
        tree, out = (Path(item) for item in arguments.families_ab)
        out.write_text(json.dumps(families_ab(tree), indent=1, sort_keys=True) + "\n")
        return 0
    base = _git("rev-parse", "--verify", f"{arguments.base}^{{commit}}")
    with tempfile.TemporaryDirectory(prefix="s11-identity-") as temporary:
        scratch = (arguments.keep or Path(temporary)).resolve()
        scratch.mkdir(parents=True, exist_ok=True)
        if arguments.base_tree is not None:
            if _git("rev-parse", "HEAD", cwd=arguments.base_tree) != base:
                raise SystemExit(f"{arguments.base_tree} is not checked out at {base}")
            passed, line = compare(arguments.base_tree.resolve(), scratch, count=arguments.shards)
        else:
            tree = Path(temporary) / "base"
            _git("worktree", "add", "--detach", "--quiet", str(tree), base)
            try:
                passed, line = compare(tree, scratch, count=arguments.shards)
            finally:
                _git("worktree", "remove", "--force", str(tree))
    print(line)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
