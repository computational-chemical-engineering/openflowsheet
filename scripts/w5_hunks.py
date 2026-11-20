"""S19 W5: which of a step's changed hunks F0's registered runs execute (review R-W5-P0-pin, 5).

W5-S2 (`w5_identity.py pin`) judges a batch P step by the pinned F0: a hunk no F0 run executes
cannot move a pinned F0 value, so the pin is blind to it. This tool tells the batch P reviewer
where. It is not a gate and judges nothing; it reports.

    PYTHONPATH=src .venv/bin/python scripts/w5_hunks.py --base B [--head REV] [--run SET/NAME ...]

The hunks are `git diff -U0 --no-renames B [REV] -- src/` (default: B against the working tree,
which is also the code that runs, so REV must be checked out when given). Python's line events
(`sys.monitoring`, the technique of W5-T4's `M02_TRACE`) are installed before F0 is imported,
then `corpus_identity.measure_all()` runs every measure (`--run`: only `runs()` of the named
runs). Per hunk, one line:

    EXECUTED <file>:<first>-<last> k/n   k of the hunk's n executable lines ran
    NOT EXECUTED <file>:<first>-<last> 0/n
    NO CODE <file>:<first>-<last>        no executable line (comments, blank lines)
    DELETION <file>:<line>               lines removed after head line <line>; not traceable

then a summary line. Executable lines are those of the head file's compiled code objects. A
module-level line (a `def`, a constant) runs on import, so EXECUTED there means imported, not
that a run used the value. Only in-process code is seen: the measures F0 runs in a subprocess
(M8's test nodes, any CLI run that forks) are not, so NOT EXECUTED is an upper bound on S2's
blindness only for in-process runs. The runs' identities are the head's (no pin): a run reads
the same code either way.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path
from types import CodeType
from typing import Any, Final

ROOT: Final = Path(__file__).resolve().parent.parent
TOOL: Final = sys.monitoring.DEBUGGER_ID
HUNK: Final = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")

Hunk = tuple[str, int, int]  # (file, first head line, count); count 0 is a deletion


def hunks(base: str, head: str | None, cwd: Path = ROOT) -> list[Hunk]:
    """The hunks of `git diff -U0 base [head] -- src/` of the `.py` files, in head lines."""
    done = subprocess.run(
        ["git", "diff", "-U0", "--no-renames", base, *([head] if head else []), "--", "src/"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    found: list[Hunk] = []
    file: str | None = None
    for line in done.stdout.splitlines():
        if line.startswith("+++ "):
            name = line[4:]
            file = name[2:] if name.startswith("b/") and name.endswith(".py") else None
        elif file is not None and (match := HUNK.match(line)):
            found.append((file, int(match[1]), 1 if match[2] is None else int(match[2])))
    return found


def _codes(code: CodeType) -> Iterator[CodeType]:
    yield code
    for constant in code.co_consts:
        if isinstance(constant, CodeType):
            yield from _codes(constant)


def executable(source: str, name: str) -> set[int]:
    """The lines of `source` that its compiled code objects can execute."""
    return {
        line
        for code in _codes(compile(source, name, "exec"))
        for _, _, line in code.co_lines()
        if line is not None
    }


def trace(files: set[str], run: Sequence[str]) -> set[tuple[str, int]]:
    """(file, line) of every line of `files` that F0's measures execute in this process."""
    targets = {str((ROOT / file).resolve()): file for file in files}
    hit: set[tuple[str, int]] = set()
    monitoring = sys.monitoring

    def line_event(code: CodeType, line: int) -> Any:
        file = targets.get(code.co_filename)
        if file is not None:
            hit.add((file, line))
        return monitoring.DISABLE

    monitoring.use_tool_id(TOOL, "w5-hunks")
    monitoring.register_callback(TOOL, monitoring.events.LINE, line_event)
    monitoring.set_events(TOOL, monitoring.events.LINE)
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import corpus_identity as f0  # noqa: PLC0415  (after the events: import-time lines count)

        if run:
            f0.runs([tuple(name.split("/", 1)) for name in run])  # type: ignore[misc]
        else:
            f0.measure_all()
    finally:
        monitoring.set_events(TOOL, monitoring.events.NO_EVENTS)
        monitoring.free_tool_id(TOOL)
    return hit


def report(
    found: Sequence[Hunk], lines: dict[str, set[int]], hit: set[tuple[str, int]]
) -> list[str]:
    """One line per hunk and the summary line."""
    out: list[str] = []
    counts = {"EXECUTED": 0, "NOT EXECUTED": 0, "NO CODE": 0, "DELETION": 0}
    for file, first, count in found:
        if count == 0:
            out.append(f"DELETION {file}:{first}")
            counts["DELETION"] += 1
            continue
        last = first + count - 1
        code = {n for n in range(first, last + 1) if n in lines[file]}
        ran = {n for n in code if (file, n) in hit}
        kind = "NO CODE" if not code else "EXECUTED" if ran else "NOT EXECUTED"
        counts[kind] += 1
        out.append(f"{kind} {file}:{first}-{last}" + (f" {len(ran)}/{len(code)}" if code else ""))
    out.append(
        f"hunks {len(found)}: executed {counts['EXECUTED']}, not executed "
        f"{counts['NOT EXECUTED']}, no code {counts['NO CODE']}, deletions {counts['DELETION']} "
        "(in-process F0 code only)"
    )
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", help="the step's commit, checked out (default: the working tree)")
    parser.add_argument(
        "--run", action="append", default=[], help="only this F0 run, SET/NAME; repeatable"
    )
    arguments = parser.parse_args(argv)
    found = hunks(arguments.base, arguments.head)
    files = {file for file, _, count in found if count}
    lines = {
        file: executable((ROOT / file).read_text(encoding="utf-8"), file)
        for file in files
        if (ROOT / file).is_file()
    }
    found = [h for h in found if h[2] == 0 or h[0] in lines]
    hit = trace(set(lines), arguments.run) if lines else set()
    print("\n".join(report(found, lines, hit)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
