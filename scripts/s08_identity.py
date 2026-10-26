"""S08 gate G1, bit-identity (design note `docs/derivations/S08-design.md` §9 G1; §7 A13). S08.

For every registered configuration, the 47 column configurations of the note's §3 F3 (S02 M1–M4
and P1, the `ref.variants`, S06 J1–J8, V and U, S03's cases) plus S01 C1–C5, a SHA-256 over the
fields that existed before S08:

- a column: outcome, cause, signature, `endpoint_sha256`, `final_sha256`; per attempt of `result`
  and of `recovered_from`, the signature, outcome, `solver_outcome`, iterations, reason and the
  `state_sha256` of its end state; `inverse` and `unreached`;
- an S01 cascade: outcome, cause, signature, the `x_K`, opening, pre-solve and final hashes, and
  the same per-attempt fields over the pre-solve, the result and the recovery;
- any other answer (a typed `CascadeFailure`, a dormant answer) its type, outcome and cause; a
  raise its type and message.

The digests are computed twice, in two subprocesses: on the merge base (default `390e0af5`) in a
detached worktree this script creates and removes (or `--base-tree`), and on this checkout; each
imports `openflowsheet`, the tests' fixtures and `scripts/` from its own tree only. On the branch,
an answer that carries S08's `reentry` also gets a digest of `reentry.stage_a` over the same
fields (its signature from its last attempt, `inverse` from its rebuilt §18.2 endpoint, whose hash
must be `stage_a.endpoint_sha256`, and `unreached` from its results).

G1 passes iff both trees give the same 52 configurations, every digest is equal except P1's
(`S02.P1`, which must change), and every `stage_a` digest, P1's among them, equals its
configuration's merge-base digest. One line is printed:

    S08-IDENTITY PASS n=52 changed=[S02.P1] p1_stage_a=EQUAL

and the exit code is 0 on PASS, 1 on FAIL (the line then names what differed).

Usage:
    PYTHONPATH=src .venv/bin/python scripts/s08_identity.py [--base 390e0af5] [--base-tree PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
#: The merge base of `wp/S08` with `main` (§9 G1).
MERGE_BASE = "390e0af5"
#: §9 G1: 47 column configurations (F3) plus S01 C1–C5.
CONFIGURATIONS = 52
#: The one configuration S08 changes (§6.1), and the line §9 G1 prints on success.
CHANGED = ("S02.P1",)
PASS_LINE = "S08-IDENTITY PASS n=52 changed=[S02.P1] p1_stage_a=EQUAL"


# -- the digests (run inside one tree) -----------------------------------------------------------


def _hash(fields: Any) -> str:
    return hashlib.sha256(repr(fields).encode()).hexdigest()


def _state(state: Mapping[str, float]) -> str:
    from openflowsheet.canonical import state_sha256

    return state_sha256(dict(state), sorted(state))


def _attempts(result: Any) -> Any:
    """Per attempt: signature, outcome, `solver_outcome`, iterations, reason, end state hash."""
    if result is None:
        return None
    return tuple(
        (
            tuple(attempt.signature),
            attempt.outcome,
            attempt.solver_outcome,
            attempt.iterations,
            attempt.reason,
            _state(attempt.end_state),
        )
        for attempt in result.attempts
    )


def column_fields(answer: Any) -> Any:
    return (
        answer.outcome,
        answer.cause,
        tuple(answer.signature),
        answer.endpoint_sha256,
        answer.final_sha256,
        _attempts(answer.result),
        _attempts(answer.recovered_from),
        repr(tuple(answer.inverse)),
        repr(tuple(answer.unreached)),
    )


def stage_a_fields(spec: Any, provider: Any, answer: Any) -> Any:
    """`column_fields` of S08's `reentry.stage_a`, rebuilt as the pre-S08 top level was."""
    from openflowsheet.canonical import state_sha256
    from openflowsheet.models.syn001.cascade_solve import DECLARATION_CONTEXT
    from openflowsheet.models.syn001.column import profile_initial
    from openflowsheet.models.syn001.column_solve import (
        bubble_point_endpoint,
        compile_column,
        inverse_records,
        regimes_of,
        unreached_specifications,
    )

    stage_a = answer.reentry.stage_a
    order = compile_column(spec, provider).spec.variable_ids
    initial = profile_initial(spec, provider, DECLARATION_CONTEXT)
    endpoint = bubble_point_endpoint(spec, provider, initial)
    x0 = {name: float(endpoint.state[name]) for name in order}
    if state_sha256(x0, order) != stage_a.endpoint_sha256:
        return ("stage_a endpoint is not the rebuilt §18.2 endpoint",)
    regimes = regimes_of(spec, stage_a.result.attempts[-1].signature)
    return (
        stage_a.outcome,
        stage_a.cause,
        tuple(regimes.values()),
        stage_a.endpoint_sha256,
        stage_a.final_sha256,
        _attempts(stage_a.result),
        _attempts(stage_a.recovered_from),
        repr(inverse_records(spec, x0)),
        repr(unreached_specifications(spec, stage_a.result, stage_a.recovered_from)),
    )


def cascade_fields(answer: Any) -> Any:
    return (
        answer.outcome,
        answer.cause,
        tuple(answer.signature),
        answer.initial_sha256,
        answer.opening_sha256,
        answer.presolve_sha256,
        answer.final_sha256,
        _attempts(answer.presolve),
        _attempts(answer.result),
        _attempts(answer.recovered_from),
    )


def column_configurations() -> dict[str, Any]:
    """§3 F3's 47 registered column configurations (`tests/test_s08_item6.py`'s `_registered`)."""
    import s03_references_ours as s03_ours
    from test_s02_column_wo1 import REFERENCE, SPECS, _variant
    from test_s06_column_wo1 import J_CASES, U_SETS, V_SETS

    cases: dict[str, Any] = {f"S02.{case}": SPECS[case] for case in SPECS}
    for case, variants in REFERENCE["variants"].items():
        for variant in variants:
            cases[f"S02.V-{case}.{variant}"] = _variant(case, variant)
    cases.update({f"S06.{case}": spec for case, spec in J_CASES.items()})
    cases.update({f"S06.V.{case}": spec for case, spec in V_SETS.items()})
    cases.update({f"S06.U.{case}": spec for case, spec in U_SETS.items()})
    s03: dict[str, Any] = s03_ours.load_cases()
    components = tuple(s03["components"])
    for case, record in s03["cases"].items():
        cases[f"S03.{case}"] = s03_ours.column_spec(record, components)
    return cases


def digests(tree: Path) -> dict[str, dict[str, str]]:
    """Every configuration's digest, and `stage_a`'s where an answer carries `reentry`."""
    import openflowsheet

    if not Path(openflowsheet.__file__).resolve().is_relative_to(tree.resolve()):
        raise SystemExit(f"openflowsheet is imported from {openflowsheet.__file__}, not {tree}")
    from test_s01_cascade_wo1 import CASES, REFERENCE, _spec
    from test_s02_column_wo1 import PROVIDER

    from openflowsheet.models.syn001.cascade_solve import CascadeSolution, solve_cascade
    from openflowsheet.models.syn001.column_solve import ColumnSolution, solve_column

    found: dict[str, str] = {}
    stage_a: dict[str, str] = {}
    solves: list[tuple[str, Any, Any]] = [
        (name, spec, solve_column) for name, spec in column_configurations().items()
    ]
    solves += [(f"S01.{case}", _spec(REFERENCE["cases"][case]), solve_cascade) for case in CASES]
    for name, spec, solve in solves:
        try:
            answer = solve(spec, PROVIDER)
        except Exception as error:  # a raise is a recorded outcome, compared like any other
            found[name] = _hash(("raised", type(error).__name__, str(error)))
            continue
        if isinstance(answer, ColumnSolution):
            found[name] = _hash(column_fields(answer))
            if getattr(answer, "reentry", None) is not None:
                stage_a[name] = _hash(stage_a_fields(spec, PROVIDER, answer))
        elif isinstance(answer, CascadeSolution):
            found[name] = _hash(cascade_fields(answer))
        else:
            fields = (type(answer).__name__, answer.outcome, getattr(answer, "cause", None))
            found[name] = _hash(fields)
    return {"digests": found, "stage_a": stage_a}


# -- the verdict ---------------------------------------------------------------------------------


def verdict(base: Mapping[str, Any], branch: Mapping[str, Any]) -> tuple[bool, str]:
    """§9 G1's rule on the two trees' digests: (passed, the one line)."""
    old, new = base["digests"], branch["digests"]
    problems: list[str] = []
    if set(old) != set(new):
        problems.append(f"configurations differ: {sorted(set(old) ^ set(new))}")
    if len(new) != CONFIGURATIONS:
        problems.append(f"{len(new)} configurations, not {CONFIGURATIONS}")
    if base["stage_a"]:
        problems.append(f"the merge base has stage_a digests: {sorted(base['stage_a'])}")
    changed = sorted(name for name in set(old) & set(new) if old[name] != new[name])
    if tuple(changed) != CHANGED:
        problems.append(f"changed={changed}, expected {list(CHANGED)}")
    p1 = branch["stage_a"].get("S02.P1")
    p1_state = "MISSING" if p1 is None else ("EQUAL" if p1 == old.get("S02.P1") else "DIFFERENT")
    if p1_state != "EQUAL":
        problems.append(f"p1_stage_a={p1_state}")
    others = sorted(
        name
        for name, value in branch["stage_a"].items()
        if name != "S02.P1" and value != old.get(name)
    )
    if others:
        problems.append(f"stage_a differs from the merge base on {others}")
    line = f"n={len(new)} changed=[{','.join(changed)}] p1_stage_a={p1_state}"
    if problems:
        return False, f"S08-IDENTITY FAIL {line} ({'; '.join(problems)})"
    return True, f"S08-IDENTITY PASS {line}"


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
            return False, f"S08-IDENTITY FAIL the {key} run exited {process.returncode} (see log)"
    found = {key: json.loads((scratch / f"{key}.json").read_text()) for key in trees}
    return verdict(found["base"], found["branch"])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--base", default=MERGE_BASE, help="the merge base (default 390e0af5)")
    parser.add_argument("--base-tree", type=Path, help="an existing checkout of --base")
    parser.add_argument("--keep", type=Path, help="keep the digests and logs in this directory")
    parser.add_argument("--digests", nargs=2, metavar=("TREE", "OUT"), help=argparse.SUPPRESS)
    arguments = parser.parse_args(argv)
    if arguments.digests:
        tree, out = (Path(item) for item in arguments.digests)
        Path(out).write_text(json.dumps(digests(tree), indent=1, sort_keys=True) + "\n")
        return 0
    base = _git("rev-parse", "--verify", f"{arguments.base}^{{commit}}")
    with tempfile.TemporaryDirectory(prefix="s08-identity-") as temporary:
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
