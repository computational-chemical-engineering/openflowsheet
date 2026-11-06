"""The standing RC job's own records (`docs/derivations/release-procedure.md` §6; ADR 0055 WO-R6).

RP replaces the per-release `scripts/v03_rc.py` and the RC runner `tools/run_local.sh` with this
script. Each record is `t08-rc-v1`, written through `t08_rc.finish` with `commit` = C,
`tree_clean`, the lock's SHA-256 and the machine class; every subcommand but `surface` refuses a
checkout that is not at `--commit`. With D2 deferred, nothing runs under `strace`.

- **surface** (step 8, §6.1): `scripts/m07a_rc.py surface` unchanged, the alpha's surface chain
  and G16-b. CI's `rc-steps` runs it under the `release_rc` dispatch; locally it is step 8 too.
- **step1** (§6.2, REL.A17): CI's push run at C, read with `gh`. The record
  `<rc>/step1/rc-step1.json` holds exactly `s1.push_run`, `s1.check.x86_64`, `s1.check.aarch64`
  and `s1.junit`; it fails, never skips, when no completed push run at C exists or a leg is not
  green. Each leg's skips, read from its junit, go to `<rc>/step1-skips/<arch>.txt` (R-376); the
  S07 A31 and S11 thermal lines of each `check` log are recorded, not judged (RP.S15). The record
  lists every `ci.yml` run at C (`runs_at_c`: id, event, attempt, conclusion; A-4), and without a
  push run at C, `s1.push_run` names the remedy: C pushed on its own, as a branch head.
- **items** (step 17, §6.7): each `rc_items` entry of `release/lines/<line>.json`, in order, into
  `<rc>/step17/rc-step17-<id>.json` with exactly one check, `<id>`. A `local:` item runs its
  `command` from the repository root with the environment's interpreter for `python` and `$C`,
  `$RC_OUT`, `$NLP_PREFIX`, `$NLP_CACHE` substituted; a `ci:` item is that job of the
  `release_rc` dispatch `--ci-run`, `pass` iff it concluded `success` on every leg and its
  artifacts were fetched into `<rc>/step17/<id>/` (the download's exit status and file count are
  recorded; S-7). `items` and `ci` refuse (exit 2) a `--ci-run` that is not C's `release_rc`
  dispatch: the greatest run id of the `workflow_dispatch` runs at C (§6.10, A-4). An environment,
  a value or a dispatch that is not given makes the item `unsupported`, which is not a pass
  (RP.S13).

    python scripts/release_rc.py surface --out RC/surface
    python scripts/release_rc.py step1 --rc RC --commit C
- **local** (steps 2, 6–17 at C, RP §6.1 "How the steps run"): 0.3.0's RC runner, ported in
  `scripts/release_rc_local.py`. It runs the line's `rc_steps` that have a local leg from this
  checkout, which must be at C and clean, writes the records under `--rc`
  (`evidence/<pkg>/<C>/artifacts/rc`) and its logs and environments under `--work`, and exits 0
  iff every record it wrote passed. A selected step whose input is not given is refused before
  anything runs (exit 2).
- **record** (steps 11–16): one step's `t08-rc-v1` record from the runner's summary and logs
  (`local` calls it; it can be re-run alone).
- **ci** (steps 1–8's CI legs): the `release_rc` dispatch at C's artifacts and job logs into
  `<rc>/ci/` (0.3.0's `fetch_ci.sh`).
- **records** (§6.9): the cited records into `evidence/<pkg>/<C>/rc/` and `rc/records.json`
  (format `m07a-rc-records-v1`), a record over 1 MB gzip-compressed beside its path.

    python scripts/release_rc.py items --line 0.4 --rc RC --commit C \
        [--python ENV=INTERPRETER ...] [--nlp-prefix P] [--nlp-cache D] [--nlp-root WT] \\
        [--ci-run ID]
    python scripts/release_rc.py local --line 0.4 --rc RC --commit C --work W \
        [--steps 2,6,...] [--nlp-prefix P --nlp-cache D] [--journey J] [--w27-artifacts DIR] \
        [--ci-run ID] [--base-python PY]
    python scripts/release_rc.py record step12 --rc RC --commit C --line 0.4 --summary S --logs L
    python scripts/release_rc.py ci --rc RC --commit C --ci-run ID
    python scripts/release_rc.py records --rc RC --commit C --to evidence/PKG/C/rc \
        --cited CITED.txt --rc-record docs/REL040-rc-record.md --package PKG
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent
#: RP §6.2: the `check` job's two legs, by runner and by the architecture names of the record.
LEGS = {"x86_64": "ubuntu-latest", "aarch64": "ubuntu-24.04-arm"}
#: RP.S15: the `check` steps whose lines carry the class ratios (S07 A31, R-627; S11, R-843).
RATIO_STEPS = ("S07 A31 line", "S11 thermal reference line")
#: §6.7: the `local:` environments, and the runner values an argv element `$NAME` may name.
ENVIRONMENTS = ("project", "coolprop", "reactor", "nlp", "lca")
VALUES = ("C", "RC_OUT", "NLP_PREFIX", "NLP_CACHE")
THREADS = {"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
_TIMESTAMP = re.compile(r"^\d{4}-\d\d-\d\dT[0-9:.]+Z ")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _t08_rc() -> Any:
    sys.path.insert(0, str(ROOT / "scripts"))
    import t08_rc  # noqa: PLC0415

    return t08_rc


def _finish(out: Path, step: str, checks: list[dict[str, Any]], **body: Any) -> int:
    t08_rc = _t08_rc()
    provenance = {**t08_rc.provenance(), "machine_class": t08_rc.machine_class()}
    return int(t08_rc.finish(out, step, checks, provenance=provenance, **body))


def _check(checks: list[dict[str, Any]], check_id: str, result: str | bool, **value: Any) -> None:
    if isinstance(result, bool):
        result = "pass" if result else "fail"
    checks.append({"id": check_id, "result": result, **value})


# -- step 1: the push run at C (§6.2) --------------------------------------------------------------


def push_run(runs: Sequence[Mapping[str, Any]], commit: str) -> Mapping[str, Any] | None:
    """§6.2: of the `ci.yml` runs whose event is `push` and whose head is C, the greatest run id."""
    found = [run for run in runs if run.get("event") == "push" and run.get("headSha") == commit]
    return max(found, key=lambda run: int(run["databaseId"])) if found else None


def rc_dispatch(runs: Sequence[Mapping[str, Any]], commit: str) -> Mapping[str, Any] | None:
    """§6.10 (amendment A-4): of the `ci.yml` runs whose event is `workflow_dispatch` and whose
    head is C, the greatest run id: the `release_rc` dispatch at C (`gh run view` reads its
    latest attempt)."""
    found = [
        run
        for run in runs
        if run.get("event") == "workflow_dispatch" and run.get("headSha") == commit
    ]
    return max(found, key=lambda run: int(run["databaseId"])) if found else None


def dispatch_problem(run_id: int, runs: Sequence[Mapping[str, Any]], commit: str) -> str | None:
    """Why `run_id` is not C's `release_rc` dispatch (A-4), or `None`."""
    selected = rc_dispatch(runs, commit)
    if selected is None:
        return f"run {run_id}: there is no workflow_dispatch run of ci.yml at {commit}"
    if int(selected["databaseId"]) != int(run_id):
        return (
            f"run {run_id} is not the release_rc dispatch at {commit}: that is run "
            f"{selected['databaseId']}, the greatest run id (RP §6.10, A-4)"
        )
    return None


def runs_at_c(runs: Sequence[Mapping[str, Any]], commit: str) -> list[dict[str, Any]]:
    """Step 1's list of every `ci.yml` run at C (A-4), by run id: a retry is visible."""
    keys = ("databaseId", "event", "attempt", "status", "conclusion")
    return sorted(
        ({key: run.get(key) for key in keys} for run in runs if run.get("headSha") == commit),
        key=lambda run: int(run["databaseId"]),
    )


def junit_skips(xml: bytes) -> list[str]:
    """Each skipped testcase of a junit file as `<classname>::<name>: <message>`, sorted."""
    skips = []
    for case in ElementTree.fromstring(xml).iter("testcase"):
        for child in case:
            if child.tag == "skipped":
                name = f"{case.get('classname', '')}::{case.get('name', '')}"
                skips.append(f"{name}: {child.get('message', '')}")
    return sorted(skips)


def ratio_lines(log: str) -> list[str]:
    """RP.S15: the lines of a `gh run view --log` job log printed by `RATIO_STEPS`."""
    lines = []
    for row in log.splitlines():
        parts = row.split("\t", 2)
        if len(parts) == 3 and parts[1].startswith(RATIO_STEPS):
            lines.append(_TIMESTAMP.sub("", parts[2]))
    return lines


def step1_checks(
    run: Mapping[str, Any] | None,
    junit: Mapping[str, Mapping[str, bytes] | None],
    logs: Mapping[str, str],
    *,
    commit: str = "<C>",
) -> list[dict[str, Any]]:
    """§6.2's four checks over the selected run (`gh run view --json` with `jobs`), each leg's junit
    files (artifact `junit-<arch>`: name → bytes, None when absent) and each leg's `check` log.
    Without a push run at C, `s1.push_run` names A-4's remedy: C pushed on its own."""
    checks: list[dict[str, Any]] = []
    completed = run is not None and run.get("status") == "completed"
    remedy = (
        {}
        if run is not None
        else {
            "remedy": f"push C on its own, as a branch head: git push origin {commit}:refs/heads/"
            f"rc/{commit[:7]} (RP §6.2, A-4)"
        }
    )
    _check(
        checks,
        "s1.push_run",
        completed,
        run_id=None if run is None else run.get("databaseId"),
        attempt=None if run is None else run.get("attempt"),
        status=None if run is None else run.get("status"),
        conclusion=None if run is None else run.get("conclusion"),
        **remedy,
    )
    jobs = {job.get("name"): job for job in (run or {}).get("jobs", [])}
    for arch, runner in LEGS.items():
        job = jobs.get(f"check ({runner})", {})
        log = logs.get(arch, "")
        _check(
            checks,
            f"s1.check.{arch}",
            completed and job.get("conclusion") == "success",
            job=f"check ({runner})",
            conclusion=job.get("conclusion"),
            log_sha256=sha256(log.encode()) if log else None,
            class_ratio_lines=ratio_lines(log),
        )
    files = {
        f"junit-{arch}": {name: sha256(data) for name, data in sorted((found or {}).items())}
        for arch, found in junit.items()
    }
    _check(
        checks,
        "s1.junit",
        completed and all(junit.get(arch) for arch in LEGS),
        files={f"junit-{arch}": files.get(f"junit-{arch}") or None for arch in LEGS},
    )
    return checks


def _gh(*arguments: str) -> str:
    return subprocess.run(
        ["gh", *arguments], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def _gh_runs(commit: str) -> list[dict[str, Any]]:
    fields = "databaseId,headSha,event,status,conclusion,attempt"
    text = _gh("run", "list", "--workflow", "ci.yml", "--commit", commit, "--json", fields)
    return list(json.loads(text))


def _gh_junit(run_id: int, arch: str, into: Path) -> dict[str, bytes] | None:
    target = into / f"junit-{arch}"
    done = subprocess.run(
        ["gh", "run", "download", str(run_id), "-n", f"junit-{arch}", "-D", str(target)],
        cwd=ROOT,
        capture_output=True,
    )
    if done.returncode != 0 or not target.is_dir():
        return None
    return {path.name: path.read_bytes() for path in sorted(target.glob("*.xml"))}


def step1(rc: Path, commit: str) -> int:
    runs = _gh_runs(commit)
    selected = push_run(runs, commit)
    run: dict[str, Any] | None = None
    junit: dict[str, dict[str, bytes] | None] = dict.fromkeys(LEGS)
    logs: dict[str, str] = {}
    if selected is not None:
        run_id = int(selected["databaseId"])
        fields = "databaseId,headSha,event,status,conclusion,attempt,jobs"
        viewed: dict[str, Any] = json.loads(_gh("run", "view", str(run_id), "--json", fields))
        run = viewed
        jobs = {job["name"]: job for job in viewed.get("jobs", [])}
        for arch, runner in LEGS.items():
            junit[arch] = _gh_junit(run_id, arch, rc / "step1")
            job = jobs.get(f"check ({runner})")
            if job is not None:
                logs[arch] = _gh("run", "view", "--job", str(job["databaseId"]), "--log")
                (rc / "step1").mkdir(parents=True, exist_ok=True)
                (rc / "step1" / f"check-{arch}.log").write_text(logs[arch], encoding="utf-8")
    skips_dir = rc / "step1-skips"
    for arch, found in junit.items():
        if found:
            skips_dir.mkdir(parents=True, exist_ok=True)
            skips = [line for data in found.values() for line in junit_skips(data)]
            (skips_dir / f"{arch}.txt").write_text("".join(f"{s}\n" for s in skips), "utf-8")
    checks = step1_checks(run, junit, logs, commit=commit)
    return _finish(
        rc / "step1" / "rc-step1.json", "ci-push-run", checks, runs_at_c=runs_at_c(runs, commit)
    )


# -- step 17: the line's items (§6.7) --------------------------------------------------------------


def substitute(argv: Sequence[str], values: Mapping[str, str | None]) -> list[str] | str:
    """`argv` with each element `$NAME` replaced by its value; the unset name, if any."""
    out = []
    for element in argv:
        if element.startswith("$"):
            value = values.get(element[1:])
            if value is None:
                return element[1:]
            element = value
        out.append(element)
    return out


def ci_item_result(jobs: Sequence[Mapping[str, Any]], job: str) -> tuple[bool, dict[str, Any]]:
    """§6.7: a `ci:<job>` item passes iff the job concluded `success` on every leg it ran on."""
    legs = {
        str(entry["name"]): entry.get("conclusion")
        for entry in jobs
        if entry.get("name") == job or str(entry.get("name", "")).startswith(f"{job} (")
    }
    return bool(legs) and all(value == "success" for value in legs.values()), legs


def _files(directory: Path) -> dict[str, str]:
    if not directory.is_dir():
        return {}
    return {
        str(path.relative_to(directory)): sha256(path.read_bytes())
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def _local_environment(environment: str) -> dict[str, str]:
    if environment == "nlp":  # 0.3.0's 17d: the audited environment from a clean `env -i`
        keep = ("HOME", "PATH", "LANG")
        return {name: os.environ[name] for name in keep if name in os.environ}
    base = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    return {**base, **THREADS, "PYTHONPATH": f"{ROOT / 'src'}{os.pathsep}{ROOT}"}


Runner = Callable[[list[str], Path, dict[str, str]], int]


def _run_to_log(argv: list[str], log: Path, environment: dict[str, str], cwd: Path = ROOT) -> int:
    with log.open("wb") as stream:
        return subprocess.run(
            argv, cwd=cwd, env=environment, stdout=stream, stderr=subprocess.STDOUT
        ).returncode


def item_check(
    item: Mapping[str, Any],
    rc: Path,
    interpreters: Mapping[str, str],
    values: Mapping[str, str | None],
    ci_jobs: Sequence[Mapping[str, Any]] | None,
    run: Runner = _run_to_log,
    download: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """The one check of item `item`'s record (§6.7). A `ci:` item also needs its artifacts:
    `download` is `gh run download`'s exit status and the file count (review S-7); a failed
    download is `fail`."""
    kind, _, where = str(item["where"]).partition(":")
    directory = rc / "step17" / str(item["id"])
    checks: list[dict[str, Any]] = []
    if kind == "ci":
        if ci_jobs is None:
            _check(checks, item["id"], "unsupported", job=where, reason="no --ci-run given")
            return checks[0]
        passed, legs = ci_item_result(ci_jobs, where)
        downloaded = download is not None and download.get("exit_status") == 0
        _check(
            checks,
            item["id"],
            passed and downloaded,
            job=where,
            conclusions=legs,
            download=None if download is None else dict(download),
            artifacts=_files(directory),
        )
        return checks[0]
    argv = substitute([str(element) for element in item["command"]], values)
    interpreter = interpreters.get(where)
    if isinstance(argv, str) or (argv[0] == "python" and interpreter is None):
        missing = f"${argv}" if isinstance(argv, str) else f"the {where} environment"
        _check(checks, item["id"], "unsupported", argv=item["command"], reason=f"{missing} unset")
        return checks[0]
    if argv[0] == "python":
        argv = [str(interpreter), *argv[1:]]
    directory.mkdir(parents=True, exist_ok=True)
    log = rc / "step17" / f"{item['id']}.log"
    before = _files(rc)
    code = run(argv, log, _local_environment(where))
    after = _files(rc)
    wrote = {
        path: digest
        for path, digest in after.items()
        if before.get(path) != digest and path != str(log.relative_to(rc))
    }
    _check(
        checks,
        item["id"],
        code == 0,
        argv=argv,
        environment=where,
        exit_status=code,
        output=str(log.relative_to(rc)),
        output_sha256=sha256(log.read_bytes()),
        records=wrote,
    )
    return checks[0]


def _line_items(line: str) -> list[dict[str, Any]]:
    import release_gate  # noqa: PLC0415

    def read(path: str) -> bytes | None:
        file = ROOT / path
        return file.read_bytes() if file.is_file() else None

    return list(release_gate.load_line(line, read).document.get("rc_items", []))


def items(
    line: str,
    rc: Path,
    commit: str,
    interpreters: Mapping[str, str],
    nlp: tuple[str | None, str | None],
    ci_run: int | None,
    roots: Mapping[str, Path] | None = None,
) -> int:
    """Step 17. `roots` gives an environment's items another checkout at C to run from: the
    runner runs the `nlp` items from its clean nlp worktree, as step 14 (C-12)."""
    ci_jobs = None
    view: dict[str, Any] = {}
    if ci_run is not None:
        view = json.loads(
            _gh("run", "view", str(ci_run), "--json", "jobs,headSha,event,databaseId,attempt")
        )
        if view.get("headSha") != commit or view.get("event") != "workflow_dispatch":
            print(f"refused: run {ci_run} is not a dispatch at {commit}", file=sys.stderr)
            return 2
        ci_jobs = view["jobs"]
    values = {"C": commit, "RC_OUT": str(rc), "NLP_PREFIX": nlp[0], "NLP_CACHE": nlp[1]}
    status = 0
    for item in _line_items(line):
        download = None
        if ci_run is not None and str(item["where"]).startswith("ci:"):
            job = str(item["where"]).removeprefix("ci:")
            target = rc / "step17" / str(item["id"])
            done = subprocess.run(
                ["gh", "run", "download", str(ci_run), "-p", f"{job}-*", "-D", str(target)],
                cwd=ROOT,
                capture_output=True,
            )
            download = {
                "run_id": ci_run,
                "attempt": view.get("attempt"),
                "exit_status": done.returncode,
                "files": len(_files(target)),
            }
        cwd = (roots or {}).get(str(item["where"]).partition(":")[2], ROOT)
        run = functools.partial(_run_to_log, cwd=cwd)
        check = item_check(item, rc, interpreters, values, ci_jobs, run, download)
        out = rc / "step17" / f"rc-step17-{item['id']}.json"
        status |= _finish(out, str(item["id"]), [check], assertion=item["assertion"])
    return status


# -- main ------------------------------------------------------------------------------------------


def _surface(out: Path) -> int:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "m07a_rc.py"), "surface", "--out", str(out)],
        cwd=ROOT,
    ).returncode


def _local_lib() -> Any:
    sys.path.insert(0, str(ROOT / "scripts"))
    import release_rc_local  # noqa: PLC0415

    return release_rc_local


def _steps(line: str, selected: str | None) -> tuple[int, ...]:
    """The line's `rc_steps` with a local leg, narrowed to `--steps` if given."""
    import release_gate  # noqa: PLC0415

    def read(path: str) -> bytes | None:
        file = ROOT / path
        return file.read_bytes() if file.is_file() else None

    claimed = set(release_gate.load_line(line, read).document["gate_set"].get("rc_steps", []))
    local = [step for step in _local_lib().LOCAL_STEPS if step in claimed]
    if selected is None:
        return tuple(local)
    wanted = {int(step) for step in selected.split(",") if step}
    return tuple(step for step in local if step in wanted)


def _local(arguments: argparse.Namespace, head: str) -> int:
    lib = _local_lib()
    plan = lib.Plan(
        line=arguments.line,
        commit=head,
        rc=arguments.rc.resolve(),
        work=arguments.work.resolve(),
        steps=_steps(arguments.line, arguments.steps),
        base_python=arguments.base_python,
        nlp_prefix=arguments.nlp_prefix,
        nlp_cache=arguments.nlp_cache,
        journey=arguments.journey,
        w27_artifacts=arguments.w27_artifacts,
        ci_run=arguments.ci_run,
    )
    missing = lib.missing_inputs(plan)
    if missing:
        print(f"refused: {'; '.join(missing)}", file=sys.stderr)
        return 2
    return int(lib.Runner(plan).run())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    surface = commands.add_parser("surface", help="step 8: m07a_rc.py surface, unchanged")
    surface.add_argument("--out", type=Path, required=True)
    for name in ("step1", "items", "local", "record", "ci", "records"):
        sub = commands.add_parser(name)
        if name == "record":
            sub.add_argument("step", choices=sorted(_local_lib().RECORDS))
        sub.add_argument("--rc", type=Path, required=True, help="the RC record directory")
        sub.add_argument("--commit", required=True, help="C; the checkout must be at it")
        if name in ("items", "local", "record"):
            sub.add_argument("--line", required=True, help="the release line <major>.<minor>")
        if name in ("items", "local"):
            sub.add_argument("--nlp-prefix", type=Path)
            sub.add_argument("--nlp-cache", type=Path)
        if name in ("items", "local", "ci"):
            sub.add_argument(
                "--ci-run", type=int, required=name == "ci", help="the release_rc dispatch at C"
            )
        if name == "items":
            sub.add_argument("--python", action="append", default=[], metavar="ENV=PATH")
            sub.add_argument("--nlp-root", type=Path, help="a clean worktree at C for nlp items")
        if name == "local":
            sub.add_argument("--work", type=Path, required=True, help="logs and environments")
            sub.add_argument("--steps", help="comma-separated subset of the line's local steps")
            sub.add_argument("--journey", help="J, the journey commit (step 15)")
            sub.add_argument("--w27-artifacts", type=Path, help="the pinned W27 archive (step 16)")
            sub.add_argument("--base-python", default="/usr/bin/python3")
        if name == "record":
            sub.add_argument("--summary", type=Path, required=True)
            sub.add_argument("--logs", type=Path, required=True)
            sub.add_argument("--journey", default="")
        if name == "records":
            sub.add_argument("--to", type=Path, required=True, help="evidence/<pkg>/<C>/rc")
            sub.add_argument("--cited", type=Path, required=True, help="one path per line")
            sub.add_argument("--rc-record", required=True)
            sub.add_argument("--package", required=True)
    arguments = parser.parse_args(argv)
    if arguments.command == "surface":
        return _surface(arguments.out)
    head = _t08_rc().git("rev-parse", "HEAD").strip()
    if head != arguments.commit:
        print(f"refused: {ROOT} is at {head}, not at {arguments.commit}", file=sys.stderr)
        return 2
    if arguments.command == "step1":
        return step1(arguments.rc, head)
    if arguments.command in ("ci", "items") and arguments.ci_run is not None:
        problem = dispatch_problem(int(arguments.ci_run), _gh_runs(head), head)
        if problem is not None:
            print(f"refused: {problem}", file=sys.stderr)
            return 2
    if arguments.command == "local":
        return _local(arguments, head)
    if arguments.command == "record":
        return int(
            _local_lib().write_record(
                arguments.step,
                arguments.rc.resolve(),
                head,
                arguments.summary,
                arguments.logs,
                arguments.line,
                arguments.journey,
            )
        )
    if arguments.command == "ci":
        return int(_local_lib().fetch_ci(arguments.ci_run, head, arguments.rc / "ci", _gh))
    if arguments.command == "records":
        cited = [
            line.strip()
            for line in arguments.cited.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        try:
            index = _local_lib().collect_records(
                arguments.rc, arguments.to, cited, head, arguments.rc_record, arguments.package
            )
        except ValueError as error:
            print(f"refused: {error}", file=sys.stderr)
            return 2
        files = index["files"]
        print(f"{len(files)} records, {sum(f['committed'] for f in files)} committed as is")
        return 0
    interpreters = {"project": sys.executable}
    for pair in arguments.python:
        environment, _, interpreter = pair.partition("=")
        if environment not in ENVIRONMENTS or not interpreter:
            parser.error(f"--python {pair!r}: not <environment>=<interpreter>")
        interpreters[environment] = interpreter
    roots = {"nlp": arguments.nlp_root} if arguments.nlp_root is not None else None
    return items(
        arguments.line,
        arguments.rc,
        head,
        interpreters,
        (
            None if arguments.nlp_prefix is None else str(arguments.nlp_prefix),
            None if arguments.nlp_cache is None else str(arguments.nlp_cache),
        ),
        arguments.ci_run,
        roots,
    )


if __name__ == "__main__":
    raise SystemExit(main())
