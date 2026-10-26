"""S08b design-time driver: the test suite in shards, plain or under `s08b_probe`. NOT a gate.

    python docs/derivations/scripts/s08b_design/run_suite.py MODE OUT [--shards 16]

`MODE` is `plain` (no plugin), `observe` or `fix` (`s08b_probe`'s modes). Every `tests/test_*.py`
file is dealt round-robin into the shards; each shard is one pytest process writing a JUnit file
under `OUT`. One line is printed — the mode, the counts and the file of failed test ids
(`OUT/failed.txt`); the shard logs stay in `OUT`.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("plain", "observe", "fix"))
    parser.add_argument("out", type=Path)
    parser.add_argument("--shards", type=int, default=16)
    arguments = parser.parse_args()
    out: Path = arguments.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    files = sorted(str(path.relative_to(ROOT)) for path in (ROOT / "tests").glob("test_*.py"))
    shards = [files[index :: arguments.shards] for index in range(arguments.shards)]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT / "src"), str(ROOT), str(HERE), environment.get("PYTHONPATH", "")]
    )
    environment["S08B_MODE"] = arguments.mode
    environment["S08B_OUT"] = str(out)
    plugin = [] if arguments.mode == "plain" else ["-p", "s08b_probe"]
    running = []
    for index, shard in enumerate(shards):
        junit = out / f"shard-{index}.xml"
        command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *plugin]
        command += [f"--junitxml={junit}", *shard]
        log = (out / f"shard-{index}.log").open("wb")
        running.append(subprocess.Popen(command, cwd=ROOT, env=environment, stdout=log, stderr=log))
    for process in running:
        process.wait()
    counts = {"passed": 0, "failed": 0, "skipped": 0}
    failed: list[str] = []
    for index in range(len(shards)):
        junit = out / f"shard-{index}.xml"
        if not junit.exists():
            failed.append(f"shard {index}: no JUnit file")
            continue
        for case in ET.parse(junit).getroot().iter("testcase"):
            name = f"{case.get('classname')}::{case.get('name')}"
            if case.find("failure") is not None or case.find("error") is not None:
                counts["failed"] += 1
                failed.append(name)
            elif case.find("skipped") is not None:
                counts["skipped"] += 1
            else:
                counts["passed"] += 1
    (out / "failed.txt").write_text("".join(f"{name}\n" for name in sorted(failed)))
    print(
        f"S08B-SUITE mode={arguments.mode} passed={counts['passed']} failed={counts['failed']} "
        f"skipped={counts['skipped']} (failed ids: {out / 'failed.txt'})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
