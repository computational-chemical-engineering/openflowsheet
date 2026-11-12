"""S16: the recall check of test-impact selection (docs/S16_DECISIONS.md, "Recall").

    s16_recall.py --base SHA --map DIR --out FILE [--workers N] [--cases ID,...]

For each seeded change: a scratch worktree at the base, the change committed there (so the tree is
clean, as a full-suite run expects), `test_impact.py select` against the map, then the full
default-marker suite with the change. Recall holds for a case when every test that fails with the
change (and passes at the base) is in the selection, or when `select` fell back to the full suite.
Refactor cases and the F0-blind case also `run` their selection; the F0-blind case runs F0 too.
One line per case on stdout; the record (JSON) goes to `--out`. Run it in the test-map venv.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "scripts" / "test_impact.py"
APP = "src/openflowsheet/application"
#: Files pytest-xdist cannot run (their node ids differ between processes); see test_impact.py.
XDIST_SERIAL = ("tests/test_t07_w2d_noncanonical.py",)

#: (id, kind, [(path, old, new), ...]); kind is "behaviour", "data" or "refactor". `old` occurs
#: exactly once in its file at the base.
CASES: list[tuple[str, str, list[tuple[str, str, str]]]] = [
    (
        "app-owner-instance",
        "behaviour",
        [
            (
                f"{APP}/local.py",
                "root=self.files_root, owner_instance=self.owner_instance",
                "root=self.files_root, owner_instance=None",
            )
        ],
    ),
    (
        "app-projection-cursor",
        "behaviour",
        [
            (
                f"{APP}/projection.py",
                "if offset + limit < len(target):",
                "if offset + limit <= len(target):",
            )
        ],
    ),
    (
        "app-projection-nested",
        "behaviour",
        [
            (
                f"{APP}/projection.py",
                "if len(node) > NESTED_ARRAY_ITEMS:",
                "if len(node) >= NESTED_ARRAY_ITEMS:",
            )
        ],
    ),
    (
        "app-transactions-diff",
        "behaviour",
        [(f"{APP}/transactions.py", "            if old != new:", "            if old == new:")],
    ),
    (
        "app-authz-revoke",
        "behaviour",
        [
            (
                f"{APP}/authz.py",
                "if len(kept) == len(policy.capabilities):",
                "if len(kept) != len(policy.capabilities):",
            )
        ],
    ),
    (
        "app-admission-budget",
        "behaviour",
        [
            (
                f"{APP}/admission.py",
                "if body.max_property_calls > policy.max_property_calls:",
                "if body.max_property_calls >= policy.max_property_calls:",
            )
        ],
    ),
    (
        "app-binding-candidates",
        "behaviour",
        [(f"{APP}/binding.py", "if len(candidates) != 1:", "if len(candidates) > 1:")],
    ),
    (
        "app-stream-table-status",
        "behaviour",
        [
            (
                f"{APP}/stream_table.py",
                'if instance.directions.get(port) != "outlet":',
                'if instance.directions.get(port) == "inlet":',
            )
        ],
    ),
    (
        "app-store-page",
        "behaviour",
        [
            (
                f"{APP}/store.py",
                "return summaries[:limit], len(summaries) > limit",
                "return summaries[:limit], len(summaries) >= limit",
            )
        ],
    ),
    (
        "app-structure-index",
        "behaviour",
        [(f"{APP}/structure_index.py", "if position < count:", "if position <= count:")],
    ),
    (
        "mixer-inlets",
        "behaviour",
        [
            (
                "src/openflowsheet/models/syn001/mixer.py",
                "if len(inlets) < 2:",
                "if len(inlets) < 3:",
            )
        ],
    ),
    (
        "mixer-bracket",
        "behaviour",
        [
            (
                "src/openflowsheet/models/syn001/mixer.py",
                "if f_low > 0.0 or f_high < 0.0:",
                "if f_low > 0.0 and f_high < 0.0:",
            )
        ],
    ),
    (
        "pr-lib-root",
        "behaviour",
        [
            (
                "src/openflowsheet/thermo/pr_lib.py",
                "key=lambda z: abs((3.0 * z + 2.0 * c2) * z + c1))",
                "key=lambda z: -abs((3.0 * z + 2.0 * c2) * z + c1))",
            )
        ],
    ),
    (
        "msg-template",
        "behaviour",
        [
            (
                "src/openflowsheet/messages/template.py",
                '        if char == "{":',
                '        if char == "<":',
            )
        ],
    ),
    ("data-catalogue-yaml", "data", []),  # filled from the file at run time (first message text)
    ("data-schema-json", "data", []),
    ("data-mcp-description", "data", []),
    (
        "refactor-rename-local",
        "refactor",
        [
            (
                f"{APP}/projection.py",
                "        page = target[offset : offset + limit]",
                "        window = target[offset : offset + limit]",
            ),
            (
                f"{APP}/projection.py",
                "                for index, item in enumerate(page)",
                "                for index, item in enumerate(window)",
            ),
        ],
    ),
    (
        "refactor-extract-function",
        "refactor",
        [
            (
                f"{APP}/projection.py",
                "        if offset + limit < len(target):",
                "        if _has_more(offset, limit, target):",
            ),
            (
                f"{APP}/projection.py",
                "    return len(canonical_json(bound_document(document)))\n",
                "    return len(canonical_json(bound_document(document)))\n\n\n"
                "def _has_more(offset: int, limit: int, target: Any) -> bool:\n"
                "    return offset + limit < len(target)\n",
            ),
        ],
    ),
]


def _data_edits(case: str, tree: Path) -> list[tuple[str, str, str]]:
    """The data cases' edits: one value each, in a file the tests read."""
    if case == "data-catalogue-yaml":
        path = "src/openflowsheet/messages/catalogue/jobs.yaml"
        old = "title: The job was cancelled on request"
        return [(path, old, old + " (seeded)")]
    if case == "data-schema-json":
        path = "schemas/api-error.schema.json"
        text = (tree / path).read_text()
        line = next(x for x in text.splitlines() if '"description": "' in x)
        return [(path, line, line.replace('"description": "', '"description": "Seeded. ', 1))]
    path = "src/openflowsheet/application/bindings/descriptions/wait_job.md"
    text = (tree / path).read_text()
    line = next(x for x in text.splitlines() if x.strip())
    return [(path, line, line + " Seeded.")]


def _git(*args: str, cwd: Path) -> str:
    environment = dict(
        os.environ,
        GIT_AUTHOR_NAME="s16-recall",
        GIT_AUTHOR_EMAIL="s16@example.invalid",
        GIT_COMMITTER_NAME="s16-recall",
        GIT_COMMITTER_EMAIL="s16@example.invalid",
    )
    done = subprocess.run(["git", *args], cwd=cwd, env=environment, capture_output=True, text=True)
    if done.returncode:
        raise RuntimeError(f"git {args}: {done.stderr}")
    return done.stdout


#: Per-test limit (pytest-timeout, requirements-testmap.lock). A mutation can leave a job queued
#: and a test waiting forever (app-owner-instance did); it then fails after the limit. The
#: slowest baseline test took 337 s.
TIMEOUT = "--timeout=900"
#: app-owner-instance leaves every job queued: 669 tests execute the mutated line, and each one that
#: waits for its job would sit out 900 s (up to 14 h with 12 workers). Its limit is 60 s. A slow
#: test cut off by it can only add a false miss (checked by hand), never hide a real one.
CASE_TIMEOUT = {"app-owner-instance": "--timeout=60"}
#: Its selected run is serial and only has to show that the selection fails: stop at the first.
CASE_RUN_ARGS = {"app-owner-instance": ("-x",)}
FAILED = re.compile(r"^(?:FAILED|ERROR) (\S+?)(?: - .*)?$")


def _suite(
    tree: Path, workers: int, log: Path, timeout: str = TIMEOUT
) -> tuple[set[str], str, float]:
    """The full default-marker suite: failing node ids, the summary lines, wall seconds."""
    environment = dict(os.environ, PYTHONPATH="src", OMP_NUM_THREADS="1")
    environment.update(OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
    base = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rfE", timeout]
    ignored = [f"--ignore={name}" for name in XDIST_SERIAL]
    runs = [base + ["-n", str(workers), *ignored], base + list(XDIST_SERIAL)]
    failures: set[str] = set()
    summaries: list[str] = []
    started = time.monotonic()
    with log.open("w") as stream:
        for index, command in enumerate(runs):
            junit = f"--junitxml={log.with_suffix(f'.{index}.xml')}"
            done = subprocess.run(
                [*command, junit], cwd=tree, env=environment, capture_output=True, text=True
            )
            stream.write(done.stdout + done.stderr)
            lines = done.stdout.splitlines()
            failures |= {m.group(1) for m in map(FAILED.match, lines) if m}
            summaries.append(next((x for x in reversed(lines) if " in " in x), "no summary"))
    return failures, " | ".join(summaries), time.monotonic() - started


def _tool(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--map", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--cases", default="")
    args = parser.parse_args()
    base = _git("rev-parse", args.base, cwd=ROOT).strip()
    wanted = set(filter(None, args.cases.split(",")))
    work = Path(tempfile.mkdtemp(prefix="s16-recall-"))
    logs = args.out.parent / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    baseline_tree = work / "baseline"
    _git("worktree", "add", "--detach", str(baseline_tree), base, cwd=ROOT)
    baseline, summary, wall = _suite(baseline_tree, args.workers, logs / "baseline.log")
    _git("worktree", "remove", "--force", str(baseline_tree), cwd=ROOT)
    print(f"baseline: {len(baseline)} failing; {summary}; {wall:.0f}s", flush=True)
    records.append({"case": "baseline", "failures": sorted(baseline), "summary": summary})
    for case, kind, edits in CASES:
        if wanted and case not in wanted:
            continue
        tree = work / case
        _git("worktree", "add", "--detach", str(tree), base, cwd=ROOT)
        edits = edits or _data_edits(case, tree)
        for path, old, new in edits:
            text = (tree / path).read_text()
            if text.count(old) != 1:
                raise SystemExit(f"{case}: {old!r} occurs {text.count(old)} times in {path}")
            (tree / path).write_text(text.replace(old, new))
        _git("commit", "-qam", f"S16 recall case {case}", cwd=tree)
        chosen = _tool("--repo", str(tree), "select", "--base", base, "--map", str(args.map))
        nodes = chosen.stdout.split()
        fallback = chosen.stderr.strip() if chosen.returncode == 3 else None
        if chosen.returncode not in (0, 3):
            raise SystemExit(f"{case}: select exit {chosen.returncode}: {chosen.stderr}")
        failures, summary, wall = _suite(
            tree, args.workers, logs / f"{case}.log", CASE_TIMEOUT.get(case, TIMEOUT)
        )
        new = failures - baseline
        files = {n for n in nodes if "::" not in n}
        missed = sorted(
            n for n in new if fallback is None and n not in nodes and n.split("::")[0] not in files
        )
        record: dict[str, object] = {
            "case": case,
            "kind": kind,
            "edits": [{"path": p, "old": o, "new": n} for p, o, n in edits],
            "selected": len(nodes),
            "fallback": fallback,
            "full_suite_failures": sorted(new),
            "missed": missed,
            "full_suite_summary": summary,
            "full_suite_seconds": round(wall),
        }
        if kind == "refactor" or case == "app-owner-instance":
            ran = _tool(
                "--repo",
                str(tree),
                "run",
                "--base",
                base,
                "--map",
                str(args.map),
                "--log",
                str(logs / f"{case}.run.log"),
                "--",
                CASE_TIMEOUT.get(case, TIMEOUT),
                *CASE_RUN_ARGS.get(case, ()),
            )
            record["run"] = {"exit": ran.returncode, "summary": ran.stdout.strip()}
        if case == "app-owner-instance":
            f0 = subprocess.run(
                [sys.executable, "scripts/corpus_identity.py", "--check"],
                cwd=tree,
                env=dict(os.environ, PYTHONPATH="src"),
                capture_output=True,
                text=True,
            )
            record["f0"] = {"exit": f0.returncode, "summary": f0.stdout.strip().splitlines()[-1:]}
        records.append(record)
        _git("worktree", "remove", "--force", str(tree), cwd=ROOT)
        print(
            f"{case}: selected {len(nodes)}, fallback {'yes' if fallback else 'no'}, "
            f"new failures {len(new)}, missed {len(missed)}"
            + (f", run exit {record['run']['exit']}" if "run" in record else "")  # type: ignore[index]
            + (f", F0 exit {record['f0']['exit']}" if "f0" in record else ""),  # type: ignore[index]
            flush=True,
        )
        args.out.write_text(json.dumps({"base": base, "cases": records}, indent=1) + "\n")
    args.out.write_text(json.dumps({"base": base, "cases": records}, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
