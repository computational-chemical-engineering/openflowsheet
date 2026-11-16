#!/usr/bin/env python3
"""S19 gate queue: gates run outside the agents, one wake per result (Frank, 2026-11-15).

State in <git-common-dir>/codehealth/queue/: pending/, running/, done/<label>.json, results.log
(one line per finished job), runner.pid, runner.log. Python 3 standard library only.

  enqueue --worktree W --base SHA --mode {step,no-gain,restructure,interface,revert} [--plan P] --label L
          --target T --recipe R --model M [--reason TEXT] [--rerun-of N]
      W must be clean; its HEAD is recorded as the job's head. A job is one step, or a chain of
      commits base..head gated as one. --base is gate.sh's sha argument: the last accepted commit,
      or for --mode revert the rejected commit (HEAD exactly undoes it); for --mode restructure and
      interface (ADR 0076 W4) the plan commit, with --plan the plan file. --reason is required for
      no-gain, restructure, revert and --rerun-of: it goes to `codehealth log` where log needs one.
  enqueue --snapshot [--head SHA] ... (as above; --head alone implies --snapshot)
      The job gates the commit --head (default: W's HEAD) in a scratch worktree of its own, so W
      may move on at once and need not be clean: commit a step, enqueue it with --base at the
      previous step's commit, carry on with the next step. Jobs of one worktree run in queue
      order. When a snapshot job fails, the pending snapshot jobs of that worktree whose head
      descends from the failed commit are finished as SKIPPED, not gated: the first failing step
      of a chain is the one reported FAIL.
  enqueue --worktree W --base SHA --mode merge-check --label L [--head SHA] [--snapshot]
      The check before a lane merges: the full suite (S19_GATE_FULL=1, read by the tests tier),
      F0 and the MCP digest over base..head, no gain check, nothing written to the run log. It
      closes the holes of the step-relative selection (docs/test-impact.md).
  run [--detach] [--log-out JSONL]
      The runner: FIFO, at most SLOTS jobs at a time, one job per worktree at a time. It refuses a
      job whose worktree HEAD or tree changed since enqueue, runs gate.sh in the worktree, then
      `codehealth log`. It never resets or retries: a failure is reported, not handled. --detach
      starts it in its own session (log runner.log, PID runner.pid). Stop it with
      `kill "$(cat <queue>/runner.pid)"`: running gates are interrupted and reported, not logged.
      --log-out sends the log records to another file than codehealth's default (a dry run).
  wait [--since N] [--idle W]
      Blocks until results.log has more than N lines (default: its count now), prints the new
      lines and `COUNT <n>`, exits 0. Run it in the background to wake once per result. With
      --idle W it also waits until no job of worktree W is pending or running: one wake per
      delivered chain.
  status
      Runner, pending, running and the last results, one screen.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
GATE = HERE / "gate.sh"
CAMPAIGN = "s19"
SLOTS = 2  # gate.sh holds one of the clone's two gate slots per run
MODES = ("step", "no-gain", "restructure", "interface", "revert", "merge-check")
PLAN_MODES = ("restructure", "interface")
SCRATCH = "gq-"  # scratch worktrees of snapshot jobs: <repo>/.claude/worktrees/gq-<label>
LABEL = re.compile(r"[A-Za-z0-9._-]+")
GATE_LINE = re.compile(r"^GATE \S+ rc=(-?\d+) \| (.*) \| json (\S+) \| log (\S+)$")
LOG_LINE = re.compile(r"^LOG \S+ step (\d+) (\S+) ")
EPS = 1e-9  # cce_code_health.cli.EPS
POLL = 5.0


def git(*args: str, cwd: Path) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if done.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} in {cwd}: {done.stderr.strip()}")
    return done.stdout.strip()


COMMON = Path(git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=HERE))
QUEUE = COMMON / "codehealth" / "queue"
CODEHEALTH = COMMON.parent / ".venv-codehealth" / "bin" / "codehealth"
PENDING, RUNNING, DONE = QUEUE / "pending", QUEUE / "running", QUEUE / "done"
RESULTS, PIDFILE, RUNLOG = QUEUE / "results.log", QUEUE / "runner.pid", QUEUE / "runner.log"


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def setup() -> None:
    for directory in (PENDING, RUNNING, DONE):
        directory.mkdir(parents=True, exist_ok=True)


@contextlib.contextmanager
def locked():
    with open(QUEUE / "lock", "w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def write_json(path: Path, data: dict) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(data, indent=1) + "\n")
    os.replace(temporary, path)


def worktree_state(worktree: Path) -> tuple[str, str]:
    """(HEAD, porcelain status) of a worktree."""
    return git("rev-parse", "HEAD", cwd=worktree), git("status", "--porcelain", cwd=worktree)


def is_ancestor(older: str, newer: str, cwd: Path) -> bool:
    done = subprocess.run(
        ["git", "merge-base", "--is-ancestor", older, newer], cwd=cwd, capture_output=True
    )
    return done.returncode == 0


def labels_in_use() -> set[str]:
    return {
        json.loads(p.read_text())["label"] for d in (PENDING, RUNNING) for p in d.glob("*.json")
    } | {p.stem for p in DONE.glob("*.json")}


def result_count() -> int:
    try:
        with open(RESULTS) as handle:
            return sum(1 for _ in handle)
    except FileNotFoundError:
        return 0


def runner_pid() -> int | None:
    try:
        pid = int(PIDFILE.read_text())
        os.kill(pid, 0)
        return pid
    except (FileNotFoundError, ValueError, ProcessLookupError):
        return None


# -- enqueue ---------------------------------------------------------------------------------------


def enqueue(a: argparse.Namespace) -> int:
    setup()
    worktree = Path(a.worktree).resolve()
    if Path(git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=worktree)) != COMMON:
        raise SystemExit(f"{worktree} is not a worktree of {COMMON.parent}")
    if not LABEL.fullmatch(a.label):
        raise SystemExit(f"--label must match {LABEL.pattern}")
    if a.mode in PLAN_MODES and not a.plan:
        raise SystemExit(f"--mode {a.mode} needs --plan")
    if a.plan and a.mode not in PLAN_MODES:
        raise SystemExit("--plan is only for --mode restructure or interface")
    if a.mode == "merge-check":
        if a.rerun_of is not None:
            raise SystemExit("--mode merge-check is not logged: no --rerun-of")
    elif not (a.target and a.recipe and a.model):
        raise SystemExit(f"--mode {a.mode} needs --target, --recipe and --model")
    if a.head:  # an earlier commit can only be gated in a scratch worktree (S19 W4 briefs use --head alone)
        a.snapshot = True
    if not a.reason and (a.mode in ("no-gain", "restructure", "revert") or a.rerun_of is not None):
        raise SystemExit(
            f"--mode {a.mode}{' with --rerun-of' if a.rerun_of is not None else ''} needs --reason"
        )
    head, dirty = worktree_state(worktree)
    if a.snapshot:
        head = git("rev-parse", "--verify", f"{a.head or 'HEAD'}^{{commit}}", cwd=worktree)
    elif dirty:
        raise SystemExit(f"{worktree} is not clean:\n{dirty}")
    base = git("rev-parse", "--verify", f"{a.base}^{{commit}}", cwd=worktree)
    if a.snapshot and not is_ancestor(base, head, worktree):
        raise SystemExit(f"--base {base[:10]} is not an ancestor of the head {head[:10]}")
    with locked():
        if a.label in labels_in_use():
            raise SystemExit(f"label {a.label} is already queued, running or done")
        seq_file = QUEUE / "seq"
        seq = int(seq_file.read_text()) + 1 if seq_file.exists() else 1
        seq_file.write_text(f"{seq}\n")
        job = {
            "seq": seq,
            "label": a.label,
            "worktree": str(worktree),
            "base": base,
            "head": head,
            "head_tree": git("rev-parse", f"{head}^{{tree}}", cwd=worktree),
            "snapshot": bool(a.snapshot),
            "detached": bool(a.snapshot),  # read by a runner started before 37307ab0
            "mode": a.mode,
            "plan": a.plan,
            "target": a.target,
            "recipe": a.recipe,
            "model": a.model,
            "reason": a.reason,
            "rerun_of": a.rerun_of,
            "enqueued": now(),
        }
        write_json(PENDING / f"{seq:06d}-{a.label}.json", job)
    print(
        f"QUEUED {seq} {a.label} {a.mode} {worktree.name} {base[:10]}..{head[:10]} "
        f"(pending {len(list(PENDING.glob('*.json')))})"
    )
    return 0


# -- run -------------------------------------------------------------------------------------------


def gate_command(job: dict) -> list[str]:
    mode, base, label = job["mode"], job["base"], job["label"]
    if mode == "step":
        return ["bash", str(GATE), base, label]
    if mode in PLAN_MODES:
        return ["bash", str(GATE), f"--{mode}", base, job["plan"], label]
    if mode == "merge-check":  # behaviour tiers over base..head, the tests tier on the full suite
        return ["bash", str(GATE), "--no-gain", base, label]
    return ["bash", str(GATE), f"--{mode}", base, label]


def gained(meta: dict) -> bool:
    """cce_code_health.cli._gained: a debt drop, or in restructure mode no debt rise with fewer
    size smells."""
    if meta["debt_after"] < meta["debt_before"] - EPS:
        return True
    smells = meta.get("size_smells")
    return (
        meta["mode"] == "restructure"
        and meta["debt_after"] <= meta["debt_before"] + EPS
        and isinstance(smells, list)
        and len(smells) == 2
        and smells[1] < smells[0]
    )


def log_command(
    job: dict, gate_json: Path, report: dict, moved: bool, log_out: str | None
) -> list[str]:
    """`codehealth log` for one gate run, with --result/--reason where log needs them (S17 D15)."""
    command = [str(CODEHEALTH), "log", "--gate-json", str(gate_json), "--campaign", CAMPAIGN]
    command += ["--target", job["target"], "--recipe", job["recipe"], "--model", job["model"]]
    if moved:  # the worktree moved on during the gate; log takes --head for kept results only
        command += ["--head", job["head"]]
    passed = all(check["ok"] for check in report["checks"])
    if job["rerun_of"] is not None:
        command += ["--rerun-of", str(job["rerun_of"]), "--reason", job["reason"]]
    elif job["mode"] == "revert":
        command += ["--reason", job["reason"]]
    elif passed and job["mode"] in ("no-gain", "restructure") and not gained(report["meta"]):
        command += ["--result", "accepted-neutral", "--reason", job["reason"]]
    if log_out:
        command += ["--out", log_out]
    return command


class Runner:
    def __init__(self, log_out: str | None) -> None:
        self.log_out = log_out
        self.lock = threading.Lock()
        self.threads: dict[str, threading.Thread] = {}  # worktree -> its job's thread
        self.gates: dict[str, subprocess.Popen] = {}
        self.failed: dict[str, list[str]] = {}  # worktree -> heads of its failed snapshot jobs
        self.stopping = False

    def say(self, line: str) -> None:
        print(f"{now()} {line}", flush=True)

    def finish(self, job: dict, running: Path, outcome: dict, summary: str) -> None:
        record = {**job, **outcome, "finished": now()}
        write_json(DONE / f"{job['label']}.json", record)
        running.unlink(missing_ok=True)
        line = f"{job['seq']} {job['label']} {summary} | done {DONE / (job['label'] + '.json')}"
        with self.lock, open(RESULTS, "a") as handle:
            handle.write(line + "\n")
        self.say(line)

    def job(self, job: dict, running: Path) -> None:
        try:
            self._job(job, running)
        except (Exception, SystemExit) as error:  # reported, never swallowed: the job leaves running/
            self.finish(
                job,
                running,
                {"status": "runner-error", "error": repr(error)},
                f"RUNNER-ERROR {error!r}",
            )

    def _job(self, job: dict, running: Path) -> None:
        if not (job.get("snapshot") or job.get("detached")):
            self._gate(job, running, Path(job["worktree"]))
            return
        scratch = COMMON.parent / ".claude" / "worktrees" / f"{SCRATCH}{job['label']}"
        try:
            git("worktree", "add", "--detach", str(scratch), job["head"], cwd=COMMON.parent)
        except SystemExit as error:
            self.finish(job, running, {"status": "refused", "why": str(error)}, f"REFUSED {error}")
            return
        try:
            self._gate(job, running, scratch)
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(scratch)],
                cwd=COMMON.parent,
                capture_output=True,
            )

    def _gate(self, job: dict, running: Path, worktree: Path) -> None:
        started = now()
        try:
            head, dirty = worktree_state(worktree)
            tree = git("rev-parse", "HEAD^{tree}", cwd=worktree)
        except SystemExit as error:
            head, dirty, tree = "", str(error), ""
        if head != job["head"] or tree != job["head_tree"] or dirty:
            why = (
                f"HEAD {head[:10]} (queued {job['head'][:10]})"
                if head != job["head"]
                else "tree not clean"
            )
            self.finish(
                job,
                running,
                {"status": "refused", "started": started, "why": why},
                f"REFUSED {why}",
            )
            return
        environment = dict(os.environ)
        if job["mode"] == "merge-check":
            environment["S19_GATE_FULL"] = "1"
        gate = subprocess.Popen(
            gate_command(job),
            cwd=worktree,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        self.gates[job["label"]] = gate
        output, _ = gate.communicate()
        del self.gates[job["label"]]
        lines = output.strip().splitlines()
        match = GATE_LINE.match(lines[-1]) if lines else None
        outcome = {
            "started": started,
            "gate_rc": gate.returncode,
            "gate_line": lines[-1] if lines else "",
        }
        if self.stopping:
            self.finish(
                job,
                running,
                {**outcome, "status": "interrupted"},
                f"INTERRUPTED rc={gate.returncode}",
            )
            return
        if match is None or not Path(match.group(3)).is_file():
            tail = " / ".join(lines[-3:])
            self.fail(job)
            self.finish(
                job,
                running,
                {**outcome, "status": "gate-error"},
                f"GATE-ERROR rc={gate.returncode} {tail}",
            )
            return
        gate_json, gate_log = Path(match.group(3)), match.group(4)
        report = json.loads(gate_json.read_text())
        failed = [c["name"] for c in report["checks"] if not c["ok"]]
        outcome |= {"gate_json": str(gate_json), "gate_log": gate_log, "failed_checks": failed}
        if gate.returncode != 0 or failed:
            self.fail(job)
        if job["mode"] == "merge-check":  # not a step: nothing for the run log
            verdict = "PASS" if gate.returncode == 0 and not failed else f"FAIL {','.join(failed)}"
            outcome["status"] = "checked"
            self.finish(
                job,
                running,
                outcome,
                f"merge-check {verdict} rc={gate.returncode} | {match.group(2)}",
            )
            return
        moved = git("rev-parse", "HEAD", cwd=worktree) != job["head"]
        logged = subprocess.run(
            log_command(job, gate_json, report, moved, self.log_out),
            cwd=worktree,
            capture_output=True,
            text=True,
        )
        log_line = (logged.stdout.strip().splitlines() or [""])[-1]
        error_line = (logged.stderr.strip().splitlines() or [""])[-1]
        step = LOG_LINE.match(log_line)
        outcome |= {"log_rc": logged.returncode, "log_line": log_line or error_line}
        outcome |= {
            "step": int(step.group(1)) if step else None,
            "result": step.group(2) if step else None,
        }
        verdict = (
            "PASS" if gate.returncode == 0 and not failed else f"FAIL {','.join(failed) or 'rc'}"
        )
        if logged.returncode != 0 or step is None:
            outcome["status"] = "log-error"
            summary = f"{verdict} rc={gate.returncode} | LOG-ERROR {error_line or log_line}"
        else:
            outcome["status"] = "logged"
            summary = f"{verdict} rc={gate.returncode} | step {step.group(1)} {step.group(2)}"
        self.finish(job, running, outcome, f"{job['mode']} {summary} | {match.group(2)}")

    def fail(self, job: dict) -> None:
        if (job.get("snapshot") or job.get("detached")):
            with self.lock:
                self.failed.setdefault(job["worktree"], []).append(job["head"])

    def skipped(self, job: dict) -> str | None:
        """The failed commit a pending snapshot job is built on, if any."""
        if not (job.get("snapshot") or job.get("detached")):
            return None
        with self.lock:
            heads = list(self.failed.get(job["worktree"], []))
        for head in heads:
            if is_ancestor(head, job["head"], COMMON.parent):
                return head
        return None

    def stop(self, *_: object) -> None:
        self.stopping = True
        for gate in list(self.gates.values()):
            with contextlib.suppress(ProcessLookupError):
                os.killpg(gate.pid, signal.SIGINT)  # gate.sh's codehealth and its pytest workers

    def loop(self) -> int:
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        for stale in sorted(RUNNING.glob("*.json")):  # a runner died with these running
            job = json.loads(stale.read_text())
            self.finish(
                job, stale, {"status": "abandoned"}, "ABANDONED: the runner stopped while it ran"
            )
        self.say(f"RUNNER start pid {os.getpid()} slots {SLOTS} queue {QUEUE}")
        while not (self.stopping and not self.threads):
            for worktree, thread in list(self.threads.items()):
                if not thread.is_alive():
                    del self.threads[worktree]
            busy = set(self.threads)
            for pending in sorted(PENDING.glob("*.json")):
                if self.stopping or len(self.threads) >= SLOTS:
                    break
                job = json.loads(pending.read_text())
                if job["worktree"] in busy:
                    continue
                running = RUNNING / pending.name
                os.replace(pending, running)
                below = self.skipped(job)
                if below is not None:
                    self.finish(
                        job,
                        running,
                        {"status": "skipped", "why": f"built on failed {below}"},
                        f"SKIPPED built on the failed step {below[:10]}",
                    )
                    continue
                self.say(
                    f"START {job['seq']} {job['label']} {job['mode']} {Path(job['worktree']).name}"
                )
                thread = threading.Thread(target=self.job, args=(job, running), name=job["label"])
                self.threads[job["worktree"]] = thread
                busy.add(job["worktree"])
                thread.start()
            time.sleep(POLL)
        self.say("RUNNER stop")
        return 0


def run(a: argparse.Namespace) -> int:
    setup()
    if a.log_out:
        a.log_out = str(Path(a.log_out).resolve())  # codehealth log runs in the job's worktree
    if a.detach:
        command = [sys.executable, str(Path(__file__).resolve()), "run"]
        command += ["--log-out", a.log_out] if a.log_out else []
        with open(RUNLOG, "a") as log:
            child = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        time.sleep(1)
        if child.poll() is not None:
            raise SystemExit(f"runner exited at once ({child.returncode}); see {RUNLOG}")
        print(f"RUNNER pid {child.pid} | log {RUNLOG} | stop: kill {child.pid}")
        return 0
    with open(QUEUE / "runner.lock", "w") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit(f"a runner is already running (pid {runner_pid()})") from None
        PIDFILE.write_text(f"{os.getpid()}\n")
        try:
            return Runner(a.log_out).loop()
        finally:
            PIDFILE.unlink(missing_ok=True)


# -- wait and status -------------------------------------------------------------------------------


def wait(a: argparse.Namespace) -> int:
    setup()
    since = result_count() if a.since is None else a.since
    lane = str(Path(a.idle).resolve()) if a.idle else None

    def busy() -> bool:
        for directory in (PENDING, RUNNING):
            for path in directory.glob("*.json"):
                with contextlib.suppress(FileNotFoundError, ValueError):
                    if json.loads(path.read_text())["worktree"] == lane:
                        return True
        return False

    while result_count() <= since or (lane is not None and busy()):
        time.sleep(POLL)
    with open(RESULTS) as handle:
        lines = handle.read().splitlines()
    print("\n".join(lines[since:]))
    print(f"COUNT {len(lines)}")
    return 0


def status(_: argparse.Namespace) -> int:
    setup()
    pid = runner_pid()
    print(f"runner: {f'pid {pid}' if pid else 'not running'} | queue {QUEUE}")
    for name, directory in (("pending", PENDING), ("running", RUNNING)):
        jobs = [json.loads(p.read_text()) for p in sorted(directory.glob("*.json"))]
        print(f"{name}: {len(jobs)}")
        for job in jobs:
            print(
                f"  {job['seq']} {job['label']} {job['mode']} {Path(job['worktree']).name} "
                f"{job['base'][:10]}..{job['head'][:10]} queued {job['enqueued']}"
            )
    count = result_count()
    print(f"results: {count} (wait --since {count} for the next)")
    if count:
        with open(RESULTS) as handle:
            for line in handle.read().splitlines()[-8:]:
                print(f"  {line}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = parser.add_subparsers(dest="command", required=True)
    e = sub.add_parser("enqueue")
    e.add_argument("--worktree", required=True)
    e.add_argument("--base", required=True)
    e.add_argument("--mode", required=True, choices=MODES)
    e.add_argument("--plan")
    e.add_argument("--label", required=True)
    e.add_argument("--target")
    e.add_argument("--recipe")
    e.add_argument("--model")
    e.add_argument("--snapshot", action="store_true")
    e.add_argument("--head")
    e.add_argument("--rerun-of", type=int)
    e.add_argument("--reason")
    r = sub.add_parser("run")
    r.add_argument("--detach", action="store_true")
    r.add_argument("--log-out")
    w = sub.add_parser("wait")
    w.add_argument("--since", type=int)
    w.add_argument("--idle", metavar="WORKTREE")
    sub.add_parser("status")
    a = parser.parse_args(argv)
    return {"enqueue": enqueue, "run": run, "wait": wait, "status": status}[a.command](a)


if __name__ == "__main__":
    sys.exit(main())
