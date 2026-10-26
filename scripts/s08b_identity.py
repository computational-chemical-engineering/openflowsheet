"""S08b gate G1, identity in two families (design note `docs/derivations/S08b-design.md` §9 G1;
R-794). S08b.

- **Family A, the 52 configurations** (`s08_identity.column_configurations()` and S01 C1–C5):
  S08's G1 digest (`column_fields` / `cascade_fields`, and `stage_a_fields` wherever an answer
  carries `reentry`) must be equal for all 52. The **texts** — every `RegionResult.message`
  reachable from the answer (`result`, `recovered_from`, `presolve`, `reentry.stage_a.result`,
  `reentry.stage_a.recovered_from`, each candidate's `result` and `recovered_from`) and every
  attempt's `reason` — must be equal except exactly §6.1's eleven (configuration, path) pairs
  (`MOVED`), where the base string contains `phase_wall(stall, )` and the branch string equals it
  with that substring replaced by `phase_wall(stall, <§6.1's list>)`.
- **Family B, the decision log of the whole suite:** both trees run every `tests/test_*.py` in
  `SHARDS` pytest processes, the files dealt round-robin from the **base tree's** sorted list
  (files only on the branch run in one extra shard), with `s08b_identity_recorder` logging every
  `phase_contract.decide` call by (test node id, call index). Over the keys both trees share every
  structural field must be equal, and `message` and `cause` equal except where the base string
  contains `phase_wall(stall, )` or `phase_wall(patience, )` and the branch string equals it with
  that empty list replaced by a non-empty list whose every entry is `<id>:<a>-><b>` with `.stage.`
  in `<id>`. Every shard must exit 0 in both trees. Keys in one tree only are reported, not judged.

With `--no-change` the expected differences are none (family A's texts all equal, no family B
move): the control that the gate sees two equal trees as equal.

The two trees are the merge base (default `a13203b8`) in a detached worktree this script creates
and removes (or `--base-tree`), and this checkout; each subprocess imports `openflowsheet`, the
tests and `scripts/` from its own tree only (the recorder, which the base tree does not have, is
copied to a directory of its own). One line is printed:

    S08B-IDENTITY PASS a=52 a_texts=11 b_keys=<N> b_moved=<M> b_only=<base>/<branch>

and the exit code is 0 on PASS, 1 on FAIL (the line then names what differed).

Usage:
    PYTHONPATH=src .venv/bin/python scripts/s08b_identity.py [--no-change] [--base a13203b8]
        [--base-tree PATH] [--keep DIR] [--shards 16]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
#: The merge base of `wp/S08b` with `main` after WO-0's merge (main `a13203b8`, S10-C merged).
MERGE_BASE = "a13203b8"
#: S08's configurations: 47 columns (S08 §3 F3) and S01 C1–C5.
CONFIGURATIONS = 52
#: The whole-suite shards per tree (family B).
SHARDS = 16
#: §6.1: the eleven (configuration, path) texts S08b moves, with the change list each gains.
MOVED: Mapping[tuple[str, str], str] = {
    ("S02.P1", "reentry.stage_a.recovered_from.message"): "S02.stage.2:LIQUID->TWO_PHASE",
    ("S02.M1", "recovered_from.message"): "S02.stage.7:VAPOR->TWO_PHASE",
    ("S02.V-M2.distillate_rate+boilup_ratio", "recovered_from.message"): (
        "S02.stage.7:VAPOR->TWO_PHASE"
    ),
    **{
        (f"S03.{case}", "recovered_from.message"): "S03.stage.7:VAPOR->TWO_PHASE"
        for case in ("PC-L", "PC-LI", "PC-P", "RC1", "RC1-BR", "RC1-RR", "RC1-z", "RC7")
    },
}
_STALL_EMPTY = "phase_wall(stall, )"
_WALL_EMPTY = re.compile(r"phase_wall\((stall|patience), \)")
_ENTRY = re.compile(r"(?P<id>[^\s:,]+):(?P<a>[A-Z_]+)->(?P<b>[A-Z_]+)")
_RECORDER = "s08b_identity_recorder"


# -- family A (run inside one tree) --------------------------------------------------------------


def _result_texts(prefix: str, result: Any, into: dict[str, str]) -> None:
    if result is None:
        return
    into[f"{prefix}.message"] = result.message
    for index, attempt in enumerate(result.attempts):
        into[f"{prefix}.attempts[{index}].reason"] = attempt.reason


def texts(answer: Any) -> dict[str, str]:
    """§9 G1: every region message reachable from an answer and every attempt's reason, by path."""
    found: dict[str, str] = {}
    for name in ("presolve", "result", "recovered_from"):
        _result_texts(name, getattr(answer, name, None), found)
    reentry = getattr(answer, "reentry", None)
    if reentry is not None:
        _result_texts("reentry.stage_a.result", reentry.stage_a.result, found)
        _result_texts("reentry.stage_a.recovered_from", reentry.stage_a.recovered_from, found)
        for index, candidate in enumerate(reentry.candidates):
            prefix = f"reentry.candidates[{index}]"
            _result_texts(f"{prefix}.result", candidate.result, found)
            _result_texts(f"{prefix}.recovered_from", candidate.recovered_from, found)
    return found


def family_a(tree: Path) -> dict[str, Any]:
    """The 52 configurations' S08 G1 digests, `stage_a` digests and texts, in this process."""
    import openflowsheet

    if not Path(openflowsheet.__file__).resolve().is_relative_to(tree.resolve()):
        raise SystemExit(f"openflowsheet is imported from {openflowsheet.__file__}, not {tree}")
    import s08_identity as s08
    from test_s01_cascade_wo1 import CASES, REFERENCE, _spec
    from test_s02_column_wo1 import PROVIDER

    from openflowsheet.models.syn001.cascade_solve import CascadeSolution, solve_cascade
    from openflowsheet.models.syn001.column_solve import ColumnSolution, solve_column

    found: dict[str, str] = {}
    stage_a: dict[str, str] = {}
    found_texts: dict[str, dict[str, str]] = {}
    solves: list[tuple[str, Any, Any]] = [
        (name, spec, solve_column) for name, spec in s08.column_configurations().items()
    ]
    solves += [(f"S01.{case}", _spec(REFERENCE["cases"][case]), solve_cascade) for case in CASES]
    for name, spec, solve in solves:
        try:
            answer = solve(spec, PROVIDER)
        except Exception as error:  # a raise is a recorded outcome, compared like any other
            found[name] = s08._hash(("raised", type(error).__name__, str(error)))
            found_texts[name] = {}
            continue
        if isinstance(answer, ColumnSolution):
            found[name] = s08._hash(s08.column_fields(answer))
            if answer.reentry is not None:
                stage_a[name] = s08._hash(s08.stage_a_fields(spec, PROVIDER, answer))
        elif isinstance(answer, CascadeSolution):
            found[name] = s08._hash(s08.cascade_fields(answer))
        else:
            fields = (type(answer).__name__, answer.outcome, getattr(answer, "cause", None))
            found[name] = s08._hash(fields)
        found_texts[name] = texts(answer)
    return {"digests": found, "stage_a": stage_a, "texts": found_texts}


# -- the verdict ---------------------------------------------------------------------------------


def _change_list(text: str) -> bool:
    """A non-empty change list whose every entry is `<id>:<a>-><b>`, `.stage.` in `<id>`."""
    entries = text.split(", ")
    for entry in entries:
        match = _ENTRY.fullmatch(entry)
        if match is None or ".stage." not in match["id"] or match["a"] == match["b"]:
            return False
    return bool(entries)


def stage_list_move(old: str, new: str) -> bool:
    """Family B's one allowed text move: `new` is `old` with each empty `phase_wall(stall|patience,
    )` list filled with a `.stage.` change list (§9 G1)."""
    pieces = _WALL_EMPTY.split(old)
    if len(pieces) == 1:
        return False
    # `split` with one group: text, kind, text, kind, …, text.
    pattern = re.escape(pieces[0])
    for kind, text in zip(pieces[1::2], pieces[2::2], strict=True):
        pattern += re.escape(f"phase_wall({kind}, ") + r"(.+?)" + re.escape(")") + re.escape(text)
    match = re.fullmatch(pattern, new, flags=re.DOTALL)
    return match is not None and all(_change_list(group) for group in match.groups())


def _verdict_a(
    base: Mapping[str, Any], branch: Mapping[str, Any], moved: Mapping[tuple[str, str], str]
) -> tuple[list[str], int]:
    problems: list[str] = []
    old, new = base["digests"], branch["digests"]
    if set(old) != set(new):
        problems.append(f"family A configurations differ: {sorted(set(old) ^ set(new))}")
    if len(new) != CONFIGURATIONS:
        problems.append(f"family A has {len(new)} configurations, not {CONFIGURATIONS}")
    changed = sorted(name for name in set(old) & set(new) if old[name] != new[name])
    if changed:
        problems.append(f"family A digests differ: {changed}")
    if set(base["stage_a"]) != set(branch["stage_a"]):
        problems.append(
            f"family A stage_a configurations differ: "
            f"{sorted(set(base['stage_a']) ^ set(branch['stage_a']))}"
        )
    stage_a = sorted(
        name
        for name in set(base["stage_a"]) & set(branch["stage_a"])
        if base["stage_a"][name] != branch["stage_a"][name]
    )
    if stage_a:
        problems.append(f"family A stage_a digests differ: {stage_a}")
    moved_texts = 0
    unexpected: list[str] = []
    for name in sorted(set(base["texts"]) & set(branch["texts"])):
        old_texts, new_texts = base["texts"][name], branch["texts"][name]
        for path in sorted(set(old_texts) | set(new_texts)):
            before, after = old_texts.get(path), new_texts.get(path)
            listed = moved.get((name, path))
            if listed is None:
                if before != after:
                    unexpected.append(f"{name} {path}")
                continue
            if (
                before is not None
                and _STALL_EMPTY in before
                and after == before.replace(_STALL_EMPTY, f"phase_wall(stall, {listed})")
            ):
                moved_texts += 1
            else:
                unexpected.append(f"{name} {path} (not the registered move)")
    if unexpected:
        problems.append(f"family A texts differ: {unexpected[:12]}")
    return problems, moved_texts


def _verdict_b(
    base: Mapping[str, Any], branch: Mapping[str, Any], no_change: bool
) -> tuple[list[str], int, int, tuple[int, int]]:
    problems: list[str] = []
    for key, found in (("base", base), ("branch", branch)):
        failed = [index for index, code in enumerate(found["exit"]) if code != 0]
        if failed:
            problems.append(f"family B {key} shards {failed} exited non-zero")
    old, new = base["records"], branch["records"]
    shared = sorted(set(old) & set(new))
    if not shared:
        problems.append("family B recorded no shared decision")
    structural: list[str] = []
    texts_moved: list[str] = []
    bad_texts: list[str] = []
    for key in shared:
        (old_shape, *old_texts), (new_shape, *new_texts) = old[key], new[key]
        if old_shape != new_shape:
            structural.append(key)
        moved = False
        for before, after in zip(old_texts, new_texts, strict=True):
            if before == after:
                continue
            if not no_change and stage_list_move(before, after):
                moved = True
            else:
                bad_texts.append(key)
        if moved:
            texts_moved.append(key)
    if structural:
        problems.append(f"family B structural differences ({len(structural)}): {structural[:5]}")
    if bad_texts:
        problems.append(f"family B text differences ({len(bad_texts)}): {bad_texts[:5]}")
    only = (len(set(old) - set(new)), len(set(new) - set(old)))
    return problems, len(shared), len(texts_moved), only


def verdict(
    base: Mapping[str, Any], branch: Mapping[str, Any], *, no_change: bool = False
) -> tuple[bool, str]:
    """§9 G1's rule on the two trees' records: (passed, the one line)."""
    moved: Mapping[tuple[str, str], str] = {} if no_change else MOVED
    problems_a, a_texts = _verdict_a(base["a"], branch["a"], moved)
    problems_b, b_keys, b_moved, only = _verdict_b(base["b"], branch["b"], no_change)
    if not no_change and a_texts != len(MOVED):
        problems_a.append(f"a_texts={a_texts}, expected {len(MOVED)}")
    line = (
        f"a={len(branch['a']['digests'])} a_texts={a_texts} b_keys={b_keys} b_moved={b_moved} "
        f"b_only={only[0]}/{only[1]}"
    )
    problems = problems_a + problems_b
    if problems:
        return False, f"S08B-IDENTITY FAIL {line} ({'; '.join(problems)})"
    return True, f"S08B-IDENTITY PASS {line}"


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


def _launch_b(
    tree: Path, plugin: Path, files: list[str], index: int, out: Path
) -> subprocess.Popen[bytes]:
    environment = _environment(tree, ("src", ""), plugin)
    environment.update(
        S08B_IDENTITY_TREE=str(tree),
        S08B_IDENTITY_SHARD=str(index),
        S08B_IDENTITY_OUT=str(out / f"shard-{index}.json"),
    )
    command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", _RECORDER]
    with (out / f"shard-{index}.log").open("wb") as sink:
        return subprocess.Popen(
            [*command, *files], cwd=tree, env=environment, stdout=sink, stderr=subprocess.STDOUT
        )


def _launch_a(tree: Path, out: Path) -> subprocess.Popen[bytes]:
    """This script's `--family-a` mode on `tree` (`-P`: the script's own directory is not put on
    `sys.path`)."""
    with (out.with_suffix(".log")).open("wb") as sink:
        return subprocess.Popen(
            [
                sys.executable,
                "-P",
                str(Path(__file__).resolve()),
                "--family-a",
                str(tree),
                str(out),
            ],
            cwd=tree,
            env=_environment(tree, ("src", "tests", "scripts", "")),
            stdout=sink,
            stderr=subprocess.STDOUT,
        )


def compare(base_tree: Path, scratch: Path, *, no_change: bool, count: int) -> tuple[bool, str]:
    trees = {"base": base_tree, "branch": ROOT}
    plugin = scratch / "plugin"
    plugin.mkdir(exist_ok=True)
    shutil.copy2(Path(__file__).resolve().with_name(f"{_RECORDER}.py"), plugin)
    running: dict[str, tuple[subprocess.Popen[bytes], dict[int, subprocess.Popen[bytes]]]] = {}
    for key, tree in trees.items():
        (scratch / key).mkdir(exist_ok=True)
        dealt = shards(base_tree, tree, count)
        running[key] = (
            _launch_a(tree, scratch / key / "family-a.json"),
            {
                index: _launch_b(tree, plugin, files, index, scratch / key)
                for index, files in enumerate(dealt)
                if files
            },
        )
    found: dict[str, Any] = {}
    for key, (family_a_run, family_b_runs) in running.items():
        if family_a_run.wait() != 0:
            for _, group in running.values():
                for process in group.values():
                    process.wait()
            return False, f"S08B-IDENTITY FAIL the {key} family A run exited (see {scratch})"
        records: dict[str, Any] = {}
        exits: list[int] = []
        for index, process in family_b_runs.items():
            code = process.wait()
            shard = scratch / key / f"shard-{index}.json"
            if not shard.exists():
                exits.append(code if code != 0 else -1)
                continue
            data = json.loads(shard.read_text())
            exits.append(code if code != 0 else int(data["exit"]))
            duplicated = set(records) & set(data["records"])
            if duplicated:
                return (
                    False,
                    f"S08B-IDENTITY FAIL {key} keys in two shards: {sorted(duplicated)[:3]}",
                )
            records.update(data["records"])
        found[key] = {
            "a": json.loads((scratch / key / "family-a.json").read_text()),
            "b": {"records": records, "exit": exits},
        }
    return verdict(found["base"], found["branch"], no_change=no_change)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--no-change", action="store_true", help="expect no difference at all")
    parser.add_argument("--base", default=MERGE_BASE, help=f"the merge base (default {MERGE_BASE})")
    parser.add_argument("--base-tree", type=Path, help="an existing checkout of --base")
    parser.add_argument("--keep", type=Path, help="keep the records and logs in this directory")
    parser.add_argument("--shards", type=int, default=SHARDS, help="whole-suite shards per tree")
    parser.add_argument("--family-a", nargs=2, metavar=("TREE", "OUT"), help=argparse.SUPPRESS)
    arguments = parser.parse_args(argv)
    if arguments.family_a:
        tree, out = (Path(item) for item in arguments.family_a)
        out.write_text(json.dumps(family_a(tree), indent=1, sort_keys=True) + "\n")
        return 0
    base = _git("rev-parse", "--verify", f"{arguments.base}^{{commit}}")
    options = {"no_change": arguments.no_change, "count": arguments.shards}
    with tempfile.TemporaryDirectory(prefix="s08b-identity-") as temporary:
        scratch = (arguments.keep or Path(temporary)).resolve()
        scratch.mkdir(parents=True, exist_ok=True)
        if arguments.base_tree is not None:
            if _git("rev-parse", "HEAD", cwd=arguments.base_tree) != base:
                raise SystemExit(f"{arguments.base_tree} is not checked out at {base}")
            passed, line = compare(arguments.base_tree.resolve(), scratch, **options)
        else:
            tree = Path(temporary) / "base"
            _git("worktree", "add", "--detach", "--quiet", str(tree), base)
            try:
                passed, line = compare(tree, scratch, **options)
            finally:
                _git("worktree", "remove", "--force", str(tree))
    print(line)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
