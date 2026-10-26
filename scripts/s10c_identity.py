"""S10-C gate G1, bit-identity of SYN-001 (design note `docs/derivations/S10C-design.md` §6 G1).

Two families of digests, each a SHA-256 over fields that existed before S10-C:

- **columns and cascades**: S08's 52 configurations (`s08_identity.column_configurations` and
  S01 C1–C5) with S08's fields (`s08_identity.column_fields` / `cascade_fields`), and S08's
  `reentry.stage_a` digest wherever an answer carries one;
- **the PH kernel**: every `ph_state` call made while the T05 and T05b test modules
  (`tests/test_t05*.py`, which include `test_t05b*`) run in-process, keyed by the test's node id
  and the call's index within it: the inputs (provider class, flows, P, H*, budget, all `float.hex`)
  and the answer — status, code, `float.hex(T)`, route, evaluations, residual, message, and the
  split's signature, vapour fraction, enthalpy flow and both outlets' flows (hex); a raise is its
  type and message. The pytest run's exit code is part of the digest and must be 0.

The digests are computed twice, in two subprocesses: on the merge base (default `ffcb387f`) in a
detached worktree this script creates and removes (or `--base-tree`), and on this checkout; each
imports `openflowsheet`, the tests and `scripts/` from its own tree only. G1 passes iff both trees
give the same keys and every digest is equal. One line is printed:

    S10C-IDENTITY PASS n=<N> changed=[]

and the exit code is 0 on PASS, 1 on FAIL (the line then names what differed). The older
`scripts/*_identity.py` gates run as their own tests (`tests/test_*identity*.py`).

Usage:
    PYTHONPATH=src .venv/bin/python scripts/s10c_identity.py [--base ffcb387f] [--base-tree PATH]
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
#: The merge base of `wp/S10C` with `main` (§6 G1).
MERGE_BASE = "ffcb387f"
#: S08's configurations: 47 columns (S08 §3 F3) and S01 C1–C5.
CONFIGURATIONS = 52


def _hash(fields: Any) -> str:
    return hashlib.sha256(repr(fields).encode()).hexdigest()


# -- the digests (run inside one tree) -----------------------------------------------------------


def column_digests() -> tuple[dict[str, str], dict[str, str]]:
    """S08's 52 configurations and their `stage_a` digests (`s08_identity.digests`'s rule)."""
    import s08_identity as s08
    from test_s01_cascade_wo1 import CASES, REFERENCE, _spec
    from test_s02_column_wo1 import PROVIDER

    from openflowsheet.models.syn001.cascade_solve import CascadeSolution, solve_cascade
    from openflowsheet.models.syn001.column_solve import ColumnSolution, solve_column

    found: dict[str, str] = {}
    stage_a: dict[str, str] = {}
    solves: list[tuple[str, Any, Any]] = [
        (name, spec, solve_column) for name, spec in s08.column_configurations().items()
    ]
    solves += [(f"S01.{case}", _spec(REFERENCE["cases"][case]), solve_cascade) for case in CASES]
    for name, spec, solve in solves:
        try:
            answer = solve(spec, PROVIDER)
        except Exception as error:  # a raise is a recorded outcome, compared like any other
            found[name] = _hash(("raised", type(error).__name__, str(error)))
            continue
        if isinstance(answer, ColumnSolution):
            found[name] = _hash(s08.column_fields(answer))
            if getattr(answer, "reentry", None) is not None:
                stage_a[name] = _hash(s08.stage_a_fields(spec, PROVIDER, answer))
        elif isinstance(answer, CascadeSolution):
            found[name] = _hash(s08.cascade_fields(answer))
        else:
            fields = (type(answer).__name__, answer.outcome, getattr(answer, "cause", None))
            found[name] = _hash(fields)
    return found, stage_a


def _hex(value: float | None) -> str | None:
    return None if value is None else float(value).hex()


def _stream(stream: Any) -> Any:
    if stream is None:
        return None
    return (tuple(_hex(v) for v in stream.n), _hex(stream.temperature), _hex(stream.pressure))


def ph_fields(answer: Any) -> Any:
    split = answer.split
    return (
        answer.status,
        answer.code,
        _hex(answer.temperature),
        answer.route,
        answer.evaluations,
        _hex(answer.residual),
        answer.message,
        None
        if split is None
        else (
            split.status,
            split.phase_signature,
            _hex(split.vapor_fraction),
            _hex(split.enthalpy_flow),
            _stream(split.vapor),
            _stream(split.liquid),
        ),
    )


def ph_digests(tree: Path) -> tuple[dict[str, str], int]:
    """Every `ph_state` call of the T05/T05b test modules, run in-process with a recorder."""
    import pytest

    from openflowsheet.models.syn001 import ph_kernel

    original: Callable[..., Any] = ph_kernel.ph_state
    calls: dict[str, int] = {}
    found: dict[str, str] = {}

    @functools.wraps(original)
    def recorded(
        provider: Any, flows: Any, pressure: Any, target: Any, *args: Any, **kw: Any
    ) -> Any:
        test = os.environ.get("PYTEST_CURRENT_TEST", "<outside a test>").rsplit(" ", 1)[0]
        index = calls[test] = calls.get(test, -1) + 1
        inputs = (
            type(provider).__name__,
            tuple(_hex(v) for v in flows),
            _hex(pressure),
            _hex(target),
            args,
            sorted(kw.items()),
        )
        try:
            answer = original(provider, flows, pressure, target, *args, **kw)
        except Exception as error:
            found[f"{test}#{index}"] = _hash((inputs, "raised", type(error).__name__, str(error)))
            raise
        found[f"{test}#{index}"] = _hash((inputs, ph_fields(answer)))
        return answer

    ph_kernel.ph_state = recorded
    for module in list(sys.modules.values()):  # rebind the importers already loaded
        if getattr(module, "ph_state", None) is original:
            module.ph_state = recorded  # type: ignore[attr-defined]
    modules = sorted(str(path) for path in (tree / "tests").glob("test_t05*.py"))
    code = pytest.main(["-q", "-p", "no:cacheprovider", "--rootdir", str(tree), *modules])
    return found, int(code)


def digests(tree: Path) -> dict[str, Any]:
    import openflowsheet

    if not Path(openflowsheet.__file__).resolve().is_relative_to(tree.resolve()):
        raise SystemExit(f"openflowsheet is imported from {openflowsheet.__file__}, not {tree}")
    columns, stage_a = column_digests()
    ph, exit_code = ph_digests(tree)
    return {"columns": columns, "stage_a": stage_a, "ph_state": ph, "pytest_exit": exit_code}


# -- the verdict ---------------------------------------------------------------------------------


def verdict(base: Mapping[str, Any], branch: Mapping[str, Any]) -> tuple[bool, str]:
    """§6 G1's rule on the two trees' digests: (passed, the one line)."""
    problems: list[str] = []
    changed: list[str] = []
    total = 0
    for family in ("columns", "stage_a", "ph_state"):
        old, new = base[family], branch[family]
        if set(old) != set(new):
            difference = sorted(set(old) ^ set(new))
            problems.append(f"{family} keys differ ({len(difference)}): {difference[:5]}")
        changed += sorted(f"{family}:{k}" for k in set(old) & set(new) if old[k] != new[k])
        total += len(new)
    if len(branch["columns"]) != CONFIGURATIONS:
        problems.append(f"{len(branch['columns'])} configurations, not {CONFIGURATIONS}")
    if not branch["ph_state"]:
        problems.append("no ph_state call was recorded")
    for key, found in (("base", base), ("branch", branch)):
        if found["pytest_exit"] != 0:
            problems.append(f"the {key} T05/T05b pytest run exited {found['pytest_exit']}")
    if changed:
        problems.append(f"{len(changed)} digests differ")
    line = f"n={total} changed=[{','.join(changed[:10])}]"
    if problems:
        return False, f"S10C-IDENTITY FAIL {line} ({'; '.join(problems)})"
    return True, f"S10C-IDENTITY PASS {line}"


# -- the driver ----------------------------------------------------------------------------------


def _git(*argv: str, cwd: Path = ROOT) -> str:
    return subprocess.run(
        ["git", *argv], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout.strip()


def _launch(tree: Path, out: Path, log: Path) -> subprocess.Popen[bytes]:
    """This script's `--digests` mode on `tree`, importing from that tree only (`-P`: the
    script's own directory is not put on `sys.path`)."""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        str(tree / part) for part in ("src", "tests", "scripts", "")
    )
    with log.open("wb") as sink:
        return subprocess.Popen(
            [sys.executable, "-P", str(Path(__file__).resolve()), "--digests", str(tree), str(out)],
            cwd=tree,
            env=environment,
            stdout=sink,
            stderr=subprocess.STDOUT,
        )


def compare(base_tree: Path, scratch: Path) -> tuple[bool, str]:
    trees = {"base": base_tree, "branch": ROOT}
    running = {
        key: _launch(tree, scratch / f"{key}.json", scratch / f"{key}.log")
        for key, tree in trees.items()
    }
    for key, process in running.items():
        if process.wait() != 0:
            return False, f"S10C-IDENTITY FAIL the {key} run exited {process.returncode} (see log)"
    found = {key: json.loads((scratch / f"{key}.json").read_text()) for key in trees}
    return verdict(found["base"], found["branch"])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--base", default=MERGE_BASE, help="the merge base (default ffcb387f)")
    parser.add_argument("--base-tree", type=Path, help="an existing checkout of --base")
    parser.add_argument("--keep", type=Path, help="keep the digests and logs in this directory")
    parser.add_argument("--digests", nargs=2, metavar=("TREE", "OUT"), help=argparse.SUPPRESS)
    arguments = parser.parse_args(argv)
    if arguments.digests:
        tree, out = (Path(item) for item in arguments.digests)
        Path(out).write_text(json.dumps(digests(tree), indent=1, sort_keys=True) + "\n")
        return 0
    base = _git("rev-parse", "--verify", f"{arguments.base}^{{commit}}")
    with tempfile.TemporaryDirectory(prefix="s10c-identity-") as temporary:
        scratch = arguments.keep or Path(temporary)
        scratch.mkdir(parents=True, exist_ok=True)
        if arguments.base_tree is not None:
            if _git("rev-parse", "HEAD", cwd=arguments.base_tree) != base:
                raise SystemExit(f"{arguments.base_tree} is not checked out at {base}")
            passed, line = compare(arguments.base_tree.resolve(), scratch)
        else:
            tree = Path(temporary) / "base"
            _git("worktree", "add", "--detach", "--quiet", str(tree), base)
            try:
                passed, line = compare(tree, scratch)
            finally:
                _git("worktree", "remove", "--force", str(tree))
    print(line)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
