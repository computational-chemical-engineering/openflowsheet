"""S19 W5: the gate mode's verdicts (`docs/briefs/S19-W5-ruling.md` sections 5, 6.2 and 9, WO-1).

The orchestrator writes one batch file per W5 batch. `gate_queue.py enqueue --mode M --batch FILE`
validates it, keeps a copy, and the runner passes the copy's absolute path to the gate as
`S19_W5_BATCH`. The tiers of `.codehealth/config.toml` call this script only when that variable is
set; unset, every tier and the frozen list behave as before the W5 mode. B below is the batch
file's `base`, not the step's `{base}`.

    w5_gate.py validate FILE --head REV   the enqueue check: the schema, B an ancestor of REV,
                                          `admitted` a subset of R at B with no tier 4 file and
                                          none above `max_tier` (`w5_identity.py sets --base B`),
                                          and no `generator` or `retarget` path in R unless admitted
    w5_gate.py batch FILE                 gate.sh's check: the schema, B an ancestor of HEAD and
                                          a clean tree (validate and batch print FILE's sha256,
                                          which the queue stores)
    w5_gate.py batch-check --queue-dir DIR --base B
                                          one batch file per B: the distinct `batch_sha256` of
                                          the queue's pending, running and done jobs whose batch
                                          base is B; exit 1 if there is more than one
    w5_gate.py f0                         W5-S3: `corpus_identity.py --check --log L`, then
                                          `w5_identity.py predict --base B --max-tier T
                                          --against-log L`, and the summary line fails no
                                          measure but M9
    w5_gate.py registry                   W5-S4: `predict --base B --max-tier T --against-tables`
    w5_gate.py scope [--plans GLOB ...]   W5-S1: `git diff --name-only B..HEAD` is a subset of
                                          admitted + generator + retarget, with no tier 4 file;
                                          also allowed, if absent at B: a .py file in the directory
                                          of an admitted tier 1 file (a split, ruling R4) and a
                                          file matching a GLOB (a restructure or interface step's
                                          plan; --plans repeats). A plan file that exists at B is
                                          in scope only if the batch admits it or names it
    w5_gate.py coverage                   W5-S7: `w5_identity.py coverage --base B --head HEAD`
    w5_gate.py tests --log L -- CMD ...   W5-S6: CMD (test_impact.py run, which writes L and
                                          reports with -rfE); on exit 1 the failed and errored
                                          node ids of L's short summaries must lie in
                                          expected_failures + standing_failures. It prints the
                                          failures outside that set and which expected failures
                                          failed (the batch close reads them: L_B is not vacuous).
                                          Each pytest call of L (a `$ ` header) must end in its
                                          closing counts line, else FAIL naming the call. An
                                          expected failure that did not fail is reported as
                                          EXPECTED-NOT-SELECTED (not in the calls' `@<log>.N.args`
                                          listings) or EXPECTED-NOT-FAILED (selected, passed)

The batch file: `{"batch": "N", "base": "<40-hex B>", "max_tier": 2, "admitted": [...],
"generator": [...], "retarget": [...], "expected_failures": [...], "standing_failures": [...]}`.
Batch P needs W5-S2 (the identity pin), which is not implemented: it is refused. A refusal
exits 2; a tier verdict exits 0 (pass) or 1 (fail), or the code of the command it ran.
Standard library only: gate.sh runs `batch` under any Python 3.
"""

from __future__ import annotations

import argparse
import contextlib
import fnmatch
import hashlib
import json
import os
import posixpath
import re
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final

ROOT: Final = Path(__file__).resolve().parent.parent
VARIABLE: Final = "S19_W5_BATCH"
LISTS: Final = ("admitted", "generator", "retarget", "expected_failures", "standing_failures")
KEYS: Final = ("batch", "base", "max_tier", *LISTS)
#: The batches this mode gates. P (tier 3 and B7) needs the pin, W5-S2.
BATCHES: Final = ("N", "L")
MAX_TIERS: Final = (1, 2)
SHA: Final = re.compile(r"[0-9a-f]{40}")
REFUSED: Final = 2
#: F0's summary line parts (`corpus_identity.summary`): a passing and a failing measure.
F0_PASS: Final = re.compile(r"M[1-9] (\d+)/\1")
F0_FAIL: Final = re.compile(r"(M[1-9]) FAIL \d+/\d+")
#: pytest's `-r` section and the section rule that ends it.
SHORT_SUMMARY: Final = re.compile(r"^=+ short test summary info =+$")
SECTION: Final = re.compile(r"^=+ .* =+$")
#: test_impact.py's header of each pytest call in its log, and pytest's closing counts line
#: (test_impact's SUMMARY, or a call that collected nothing).
CALL: Final = "$ "
CLOSING: Final = re.compile(
    r"^=*\s*(?:\d+ (?:passed|failed|error|skipped|deselected)|no tests ran)\b.* in [\d.]+s"
)


class BatchRefusedError(Exception):
    """A batch file this mode does not gate."""


# -- the batch file --------------------------------------------------------------------------------


def structure(document: Any) -> list[str]:
    """The schema's problems of a batch document (no repository access)."""
    if not isinstance(document, dict):
        return ["the batch file is not a JSON object"]
    problems = [f"missing key {key!r}" for key in KEYS if key not in document]
    problems += [f"unknown key {key!r}" for key in sorted(set(document) - set(KEYS))]
    batch = document.get("batch")
    if batch == "P":
        problems.append(
            "batch P needs W5-S2 (the identity pin, `w5_identity.py pin`), which is not implemented"
        )
    elif "batch" in document and batch not in BATCHES:
        problems.append(f"batch {batch!r}: not one of {', '.join(BATCHES)} (ruling R3)")
    base = document.get("base")
    if "base" in document and not (isinstance(base, str) and SHA.fullmatch(base)):
        problems.append(f"base {base!r}: not a 40-hex commit sha")
    tier = document.get("max_tier")
    if "max_tier" in document and (type(tier) is not int or tier not in MAX_TIERS):
        problems.append(f"max_tier {tier!r}: not one of {MAX_TIERS} (tier 3 is batch P's)")
    for key in LISTS:
        value = document.get(key, [])
        if not (isinstance(value, list) and all(isinstance(item, str) for item in value)):
            problems.append(f"{key}: not a list of strings")
        elif len(set(value)) != len(value):
            problems.append(f"{key}: duplicate entries")
    return problems


def membership(document: Mapping[str, Any], sets: Mapping[str, Any]) -> list[str]:
    """The admitted set against `w5_identity.py sets --json` at B: in R, not tier 4, at most
    `max_tier`; a generator or retarget path in R must be admitted too."""
    r_set = set(sets["R"])
    tier_of = {file: int(tier) for tier, files in sets["tiers"].items() for file in files}
    problems = []
    for path in document["admitted"]:
        tier = tier_of.get(path)
        if path not in r_set or tier is None:
            problems.append(f"admitted {path}: not in R at the base")
        elif tier == 4:
            problems.append(f"admitted {path}: tier 4 (excluded, ruling R1)")
        elif tier > document["max_tier"]:
            problems.append(f"admitted {path}: tier {tier}, above max_tier {document['max_tier']}")
    admitted = set(document["admitted"])
    for key in ("generator", "retarget"):
        problems += [
            f"{key} {path}: in R at the base but not admitted"
            for path in document[key]
            if path in r_set and path not in admitted
        ]
    return problems


def _git(*arguments: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *arguments], cwd=cwd, capture_output=True, text=True)


def ancestry(base: str, head: str, cwd: Path = ROOT) -> list[str]:
    if _git("cat-file", "-e", f"{base}^{{commit}}", cwd=cwd).returncode != 0:
        return [f"base {base}: no such commit"]
    if _git("merge-base", "--is-ancestor", base, head, cwd=cwd).returncode != 0:
        return [f"base {base[:12]}: not an ancestor of the head {head}"]
    return []


def read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise BatchRefusedError(f"{path}: {error}") from None


def dirty(cwd: Path = ROOT) -> str:
    """`git status --porcelain` of a tree (as the gate queue reads a worktree's state)."""
    return _git("status", "--porcelain", cwd=cwd).stdout.strip()


def load(path: Path, head: str = "HEAD", cwd: Path = ROOT) -> dict[str, Any]:
    """The batch document, refused unless its schema holds and B is an ancestor of `head`."""
    document = read(path)
    problems = structure(document)
    if not problems:
        problems = ancestry(document["base"], head, cwd)
    if problems:
        raise BatchRefusedError("; ".join(problems))
    return dict(document)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def batch_files(queue: Path, base: str) -> dict[str, list[str]]:
    """The labels of the queue's pending, running and done jobs with batch base `base` (a sha or
    a prefix of one), by their batch file's sha256 (`none` for a job without one)."""
    found: dict[str, list[str]] = {}
    for state in ("pending", "running", "done"):
        for path in sorted((queue / state).glob("*.json")):
            job = read(path)
            if isinstance(job, dict) and str(job.get("batch_base") or "").startswith(base):
                found.setdefault(job.get("batch_sha256") or "none", []).append(str(job["label"]))
    return found


def from_environment() -> dict[str, Any]:
    name = os.environ.get(VARIABLE)
    if not name:
        raise BatchRefusedError(f"{VARIABLE} is not set")
    return load(Path(name))


# -- the identity tool -----------------------------------------------------------------------------


def identity(*arguments: str, capture: bool = False) -> subprocess.CompletedProcess[str]:
    """`w5_identity.py` of this tree, under this interpreter."""
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "w5_identity.py"), *arguments],
        cwd=ROOT,
        capture_output=capture,
        text=True,
    )


def sets_at(base: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as directory:
        out = Path(directory) / "sets.json"
        done = identity("sets", "--check", "--base", base, "--json", str(out), capture=True)
        if done.returncode != 0 or not out.is_file():
            raise BatchRefusedError(
                f"w5_identity.py sets --base {base[:12]}: {done.stdout.strip()}"
            )
        sets: dict[str, Any] = json.loads(out.read_text(encoding="utf-8"))
        return sets


# -- the verdicts ----------------------------------------------------------------------------------


def changed(base: str, *, added: bool = False) -> list[str]:
    """The paths `base..HEAD` changes (`added`: only those absent at the base). A rename counts
    as both of its paths."""
    filters = ["--diff-filter=A"] if added else []
    done = _git("diff", "--name-only", "--no-renames", *filters, f"{base}..HEAD")
    if done.returncode != 0:
        raise BatchRefusedError(f"git diff {base[:12]}..HEAD: {done.stderr.strip()}")
    return sorted(done.stdout.split())


def plan_file(path: str, plans: Iterable[str]) -> bool:
    """Whether `path` matches one of the plans' globs, each a file pattern in one directory."""
    return any(
        posixpath.dirname(path) == posixpath.dirname(glob)
        and fnmatch.fnmatchcase(posixpath.basename(path), posixpath.basename(glob))
        for glob in plans
    )


def scope_problems(
    files: Iterable[str],
    document: Mapping[str, Any],
    tiers: Mapping[str, Sequence[str]],
    added: Iterable[str] = (),
    plans: Iterable[str] = (),
) -> list[str]:
    """W5-S1: every changed path is admitted, the generator's or a named retarget, and none is a
    tier 4 file. Also allowed, if new (in `added`, absent at B): a module in the directory of an
    admitted tier 1 file, which a tier 1 split adds (ruling R4: tier 1 files may be split within
    their directory), and a restructure or interface step's plan file (`plans`, the globs
    config.toml passes). A plan file that exists at B is not admitted by the glob."""
    allowed = {path for key in ("admitted", "generator", "retarget") for path in document[key]}
    excluded = set(tiers["4"])
    split_into = {posixpath.dirname(path) for path in set(document["admitted"]) & set(tiers["1"])}
    new = set(added)
    plans = tuple(plans)
    problems = []
    for path in sorted(set(files)):
        if path in excluded:
            problems.append(f"{path}: tier 4 (excluded, ruling R1)")
        elif path in allowed or (path in new and plan_file(path, plans)):
            continue
        elif path in new and path.endswith(".py") and posixpath.dirname(path) in split_into:
            continue
        else:
            problems.append(f"{path}: outside the batch's admitted, generator and retarget sets")
    return problems


def f0_line_problems(line: str) -> list[str]:
    """W5-S3 for batches N and L: `F0 PASS` or `F0 FAIL` with no failing measure but M9."""
    head, _, parts = line.partition(": ")
    if head not in ("F0 PASS", "F0 FAIL") or not parts:
        return [f"summary line {line!r}: not an F0 summary"]
    problems = []
    for part in parts.split(", "):
        failing = F0_FAIL.fullmatch(part)
        if failing and failing.group(1) == "M9":
            continue
        if not F0_PASS.fullmatch(part):
            problems.append(f"summary line: {part!r} (in batches N and L only M9 may fail)")
    return problems


def _node(rest: str) -> str:
    """The node id at the start of a short-summary entry `NODE - MESSAGE` (a parameter id may hold
    ' - ': the id ends at the first separator outside brackets)."""
    start = 0
    while (cut := rest.find(" - ", start)) >= 0:
        if rest.count("[", 0, cut) == rest.count("]", 0, cut):
            return rest[:cut]
        start = cut + 1
    return rest


def failed_nodes(text: str) -> set[str]:
    """The FAILED and ERROR node ids of every pytest short test summary in `text`."""
    found: set[str] = set()
    inside = False
    for line in text.splitlines():
        if SHORT_SUMMARY.match(line):
            inside = True
        elif inside and SECTION.match(line):
            inside = False
        elif inside:
            kind, _, rest = line.partition(" ")
            if kind in ("FAILED", "ERROR") and rest:
                found.add(_node(rest))
    return found


def calls(text: str) -> list[tuple[str, list[str]]]:
    """(header, output lines) of each pytest call in a test_impact.py log."""
    found: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        if line.startswith(CALL):
            found.append((line[len(CALL) :], []))
        elif found:
            found[-1][1].append(line)
    return found


def unclosed_calls(text: str) -> list[str]:
    """The calls of a test_impact.py log without a pytest closing counts line (a crashed or killed
    pytest), as `call N: COMMAND`."""
    return [
        f"call {index}: {header}"
        for index, (header, output) in enumerate(calls(text))
        if not any(CLOSING.match(line) for line in output)
    ]


def selection(text: str) -> set[str] | None:
    """The node ids and test files the calls of a test_impact.py log ran: their `@<log>.N.args`
    listings. None when a call takes no listing: a full suite or a fallback ran everything. An
    unreadable listing adds nothing, so its tests read as not selected, never as run."""
    found: set[str] = set()
    for header, _ in calls(text):
        last = header.rsplit(" ", 1)[-1]
        if not last.startswith("@"):
            return None
        with contextlib.suppress(OSError):
            found.update(Path(last[1:]).read_text(encoding="utf-8").split())
    return found


def selected(node: str, entries: set[str] | None) -> bool:
    """Whether a node id was run: it, its test file or a node id that contains it is listed."""
    if entries is None:
        return True
    return any(node == entry or node.startswith((f"{entry}::", f"{entry}[")) for entry in entries)


def tests_verdict(
    code: int,
    failed: set[str],
    document: Mapping[str, Any],
    unclosed: Sequence[str] = (),
    entries: set[str] | None = None,
) -> tuple[int, list[str]]:
    """W5-S6: (exit code, report lines). Exit 1 passes iff its failures lie in L_B + standing and
    every pytest call closed with its counts line. `entries` is the run's selection (None: all):
    an expected failure that did not fail is reported as not selected or as selected and passed;
    neither fails a step (the batch close reads them: L_B is not vacuous)."""
    expected = set(document["expected_failures"])
    standing = set(document["standing_failures"])
    hit = sorted(failed & expected)
    missed = sorted(expected - failed)
    unselected = [node for node in missed if not selected(node, entries)]
    lines = [f"EXPECTED-FAILED {node}" for node in hit]
    lines += [f"EXPECTED-NOT-SELECTED {node}" for node in unselected]
    lines += [f"EXPECTED-NOT-FAILED {node}" for node in missed if node not in unselected]
    lines += [f"STANDING-FAILED {node}" for node in sorted(failed & standing - expected)]
    lines += [f"NO-PYTEST-SUMMARY {call}" for call in unclosed]
    tally = f"expected failures failed {len(hit)}/{len(expected)}, not selected {len(unselected)}"
    if unclosed:
        return code if code not in (0, 1) else 1, [
            *lines,
            f"w5 tests (W5-S6) FAIL: exit {code}, {len(unclosed)} pytest call(s) without a "
            f"closing counts line ({unclosed[0]}); {tally}",
        ]
    if code == 0:
        return 0, [*lines, f"w5 tests (W5-S6) PASS: exit 0; {tally}"]
    if code != 1:
        return code, [*lines, f"w5 tests (W5-S6) FAIL: exit {code}, not a test failure; {tally}"]
    if not failed:
        return 1, [*lines, "w5 tests (W5-S6) FAIL: exit 1 with no failed node id in the log"]
    outside = sorted(failed - expected - standing)
    lines += [f"UNEXPECTED {node}" for node in outside]
    if outside:
        return 1, [
            *lines,
            f"w5 tests (W5-S6) FAIL: {len(outside)} failure(s) outside L_B and the "
            f"standing failures; {tally}",
        ]
    return 0, [
        *lines,
        f"w5 tests (W5-S6) PASS: {len(failed)} failure(s), all in L_B or standing; {tally}",
    ]


# -- the subcommands -------------------------------------------------------------------------------


def command_validate(arguments: argparse.Namespace) -> int:
    path = Path(arguments.file)
    head = arguments.head
    document = load(path, head)
    problems = membership(document, sets_at(document["base"]))
    if problems:
        raise BatchRefusedError("; ".join(problems))
    print(
        f"W5 batch {document['batch']} valid: base {document['base'][:12]}, max_tier "
        f"{document['max_tier']}, admitted {len(document['admitted'])}, generator "
        f"{len(document['generator'])}, retarget {len(document['retarget'])}, expected failures "
        f"{len(document['expected_failures'])}, standing {len(document['standing_failures'])}, "
        f"sha256 {digest(path)}"
    )
    return 0


def command_batch(arguments: argparse.Namespace) -> int:
    path = Path(arguments.file)
    document = load(path)
    if status := dirty():
        raise BatchRefusedError(f"the tree under test is not clean:\n{status}")
    print(f"W5 batch {document['batch']} base {document['base'][:12]} sha256 {digest(path)}")
    return 0


def command_batch_check(arguments: argparse.Namespace) -> int:
    if not SHA.fullmatch(arguments.base.ljust(40, "0")) or len(arguments.base) < 7:
        raise BatchRefusedError(f"--base {arguments.base!r}: not a commit sha of 7 to 40 hex")
    found = batch_files(Path(arguments.queue_dir), arguments.base)
    for sha256, labels in sorted(found.items()):
        print(f"sha256 {sha256}: {', '.join(sorted(labels))}")
    jobs = sum(map(len, found.values()))
    verdict = "PASS" if len(found) <= 1 else "FAIL"
    print(
        f"w5 batch-check {verdict}: base {arguments.base[:12]}, {jobs} job(s), "
        f"{len(found)} distinct batch file(s)"
    )
    return 0 if len(found) <= 1 else 1


def command_f0(_: argparse.Namespace) -> int:
    document = from_environment()
    base, tier = document["base"], str(document["max_tier"])
    with tempfile.TemporaryDirectory() as directory:
        log = Path(directory) / "f0.log"
        f0 = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "corpus_identity.py"),
                "--check",
                "--log",
                str(log),
            ],
            cwd=ROOT,
        ).returncode
        if f0 not in (0, 1) or not log.is_file():
            print(f"w5 f0 (W5-S3) FAIL: corpus_identity.py --check exit {f0}")
            return f0 or 1
        lines = log.read_text(encoding="utf-8").splitlines()
        if not lines:
            print(f"w5 f0 (W5-S3) FAIL: corpus_identity.py --check exit {f0}, an empty log")
            return 1
        line = lines[0]
        predicted = identity(
            "predict", "--base", base, "--max-tier", tier, "--against-log", str(log)
        )
    problems = f0_line_problems(line)
    for problem in problems:
        print(problem)
    if predicted.returncode != 0 or problems:
        why = [f"predict exit {predicted.returncode}"] if predicted.returncode else []
        print(f"w5 f0 (W5-S3) FAIL: {', '.join(why + problems)}; {line}")
        return 1
    print(f"w5 f0 (W5-S3) PASS: the prediction at {base[:12]} holds both ways; {line}")
    return 0


def command_registry(_: argparse.Namespace) -> int:
    document = from_environment()
    done = identity(
        "predict",
        "--base",
        document["base"],
        "--max-tier",
        str(document["max_tier"]),
        "--against-tables",
    )
    print(
        f"w5 registry (W5-S4) {'PASS' if done.returncode == 0 else 'FAIL'}: exit {done.returncode}"
    )
    return done.returncode


def command_coverage(_: argparse.Namespace) -> int:
    document = from_environment()
    done = identity("coverage", "--base", document["base"], "--head", "HEAD")
    print(
        f"w5 coverage (W5-S7) {'PASS' if done.returncode == 0 else 'FAIL'}: exit {done.returncode}"
    )
    return done.returncode


def command_scope(arguments: argparse.Namespace) -> int:
    document = from_environment()
    files = changed(document["base"])
    added = changed(document["base"], added=True)
    tiers = sets_at(document["base"])["tiers"]
    problems = scope_problems(files, document, tiers, added, arguments.plans or ())
    for problem in problems:
        print(problem)
    verdict = f"FAIL: {len(problems)} path(s) outside the batch" if problems else "PASS"
    print(f"w5 scope (W5-S1) {verdict}; {len(files)} path(s) changed since {document['base'][:12]}")
    return 1 if problems else 0


def command_tests(arguments: argparse.Namespace) -> int:
    document = from_environment()
    command = list(arguments.command)
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        raise BatchRefusedError("tests: no command after --")
    log = Path(arguments.log)
    code = subprocess.call(command, cwd=ROOT)
    text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
    result, lines = tests_verdict(
        code, failed_nodes(text), document, unclosed_calls(text), selection(text)
    )
    print("\n".join(lines))
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    commands = parser.add_subparsers(dest="command_name", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("file")
    validate.add_argument("--head", required=True)
    batch = commands.add_parser("batch")
    batch.add_argument("file")
    batch_check = commands.add_parser("batch-check")
    batch_check.add_argument("--queue-dir", required=True)
    batch_check.add_argument("--base", required=True)
    for name in ("f0", "registry", "coverage"):
        commands.add_parser(name)
    scope = commands.add_parser("scope")
    scope.add_argument(
        "--plans",
        action="append",
        help="a glob of the plan files a W5 step may add (restructure, interface); repeatable",
    )
    tests = commands.add_parser("tests")
    tests.add_argument("--log", required=True)
    tests.add_argument("command", nargs=argparse.REMAINDER)
    arguments = parser.parse_args(argv)
    handlers = {
        "validate": command_validate,
        "batch": command_batch,
        "batch-check": command_batch_check,
        "f0": command_f0,
        "registry": command_registry,
        "scope": command_scope,
        "coverage": command_coverage,
        "tests": command_tests,
    }
    try:
        return handlers[arguments.command_name](arguments)
    except BatchRefusedError as error:
        print(f"W5 batch REFUSED: {error}", flush=True)
        return REFUSED


if __name__ == "__main__":
    raise SystemExit(main())
