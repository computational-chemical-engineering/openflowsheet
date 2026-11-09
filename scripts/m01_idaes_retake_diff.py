"""M01's IDAES conformance record re-taken on the RC host, proved against the committed record
(R-1008; `docs/reviews/REL040-s6-ruling.md` §3 and §8 WO-3; RP §7.1 as amended by A-11).

The differing members are `m01_evidence_manifest._differences(committed, retake)`, the comparator
that RC step 11 uses (W22 (b)), sorted. Each is classified:

- `environment.platform` is admitted iff `--old-platform` is given, the committed side equals it
  and the re-take side equals the running `platform.platform()`;
- `inputs.<name>_sha256` is admitted iff `<name>` is one of `INPUTS`, the re-take value is the
  SHA-256 of that file, and the file is tracked and unmodified in this checkout (K3);
- anything else is other, every numeric member among them: the comparison is exact.

Prints one line, `IDAES-RETAKE PASS|FAIL differing=<members> platform=<0|1> inputs=<n>
other=<n>`, then each problem; exit 0 iff PASS.

    python scripts/m01_idaes_retake_diff.py <committed> <retake> [--old-platform <p>]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

import m01_evidence_manifest

ROOT = Path(__file__).resolve().parents[1]

#: The input files whose SHA-256 the record carries as `inputs.<name>_sha256`.
INPUTS = {
    "components_yaml": "benchmarks/m01/components.yaml",
    "reference_values_yaml": "benchmarks/m01/reference_values.yaml",
}
PLATFORM = "environment.platform"


def _git(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True, text=True)


def _input_problem(name: str, value: Any) -> str | None:
    """Why `inputs.<name>_sha256` = `value` is not admitted, or None."""
    relative = INPUTS.get(name)
    if relative is None:
        return "not a registered input"
    if _git("ls-files", "--error-unmatch", "--", relative).returncode != 0:
        return f"{relative} is not tracked"
    if _git("status", "--porcelain", "--", relative).stdout:
        return f"{relative} is modified in this checkout"
    actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
    if value != actual:
        return f"{value!r} is not the SHA-256 of {relative} ({actual})"
    return None


def retake_diff(
    committed: Any, retake: Any, old_platform: str | None = None
) -> tuple[bool, list[str]]:
    """Whether `retake` differs from `committed` only where R-1008 admits it. Returns (passed,
    lines): the summary line, then each problem."""
    differing = sorted(m01_evidence_manifest._differences(committed, retake, ""))
    admitted = {"platform": 0, "inputs": 0}
    problems: list[str] = []
    for member in differing:
        before = _member(committed, member)
        after = _member(retake, member)
        if member == PLATFORM:
            running = platform.platform()
            if old_platform is None:
                problems.append(f"{member}: {before!r} vs {after!r} (no --old-platform)")
            elif before != old_platform:
                problems.append(f"{member}: committed {before!r} is not --old-platform")
            elif after != running:
                problems.append(f"{member}: re-take {after!r} is not the running {running!r}")
            else:
                admitted["platform"] += 1
            continue
        name = member.removeprefix("inputs.").removesuffix("_sha256")
        if member == f"inputs.{name}_sha256":
            problem = _input_problem(name, after)
            if problem is None:
                admitted["inputs"] += 1
            else:
                problems.append(f"{member}: {problem}")
            continue
        problems.append(f"{member}: {before!r} vs {after!r}")
    passed = not problems
    summary = (
        f"IDAES-RETAKE {'PASS' if passed else 'FAIL'} differing={','.join(differing)} "
        f"platform={admitted['platform']} inputs={admitted['inputs']} other={len(problems)}"
    )
    return passed, [summary, *(f"  other {line}" for line in problems)]


def _member(document: Any, member: str) -> Any:
    """The value at a dotted `member` of nested objects, None where it is absent."""
    for key in member.split("."):
        document = document.get(key) if isinstance(document, dict) else None
    return document


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("committed", type=Path)
    parser.add_argument("retake", type=Path)
    parser.add_argument("--old-platform", help="the committed record's environment.platform")
    args = parser.parse_args(argv)
    passed, lines = retake_diff(
        json.loads(args.committed.read_bytes()),
        json.loads(args.retake.read_bytes()),
        args.old_platform,
    )
    print("\n".join(lines))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
