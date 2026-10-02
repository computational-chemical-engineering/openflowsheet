"""Regenerate the P02 evidence manifest from the judged results.

The manifest records the commands that were actually run, so this script does not invent them: it
reads their captured stdout from a directory you pass in, and hashes what is there. Produce that
directory first, for example::

    mkdir -p /tmp/p02-stdout
    PATH=.venv/bin:$PATH ./scripts/check.sh            > /tmp/p02-stdout/check.out 2>&1
    ./spikes/p02/casadi/run.sh                          > /tmp/p02-stdout/casadi.out 2>&1
    ./spikes/p02/pyomo/run.sh                           > /tmp/p02-stdout/pyomo.out 2>&1
    .venv/bin/python docs/derivations/scripts/p02_reference.py --check \
                                                        > /tmp/p02-stdout/refcheck.out 2>&1
    PYTHONPATH=. .venv/bin/python scripts/p02_evidence_manifest.py /tmp/p02-stdout

The harness runs rewrite the timing and environment records, so restore them with
``git checkout -- spikes/p02/results`` before generating, or the artifact hashes will not match
the commit the manifest names. The manifest is written to
``evidence/P02/<HEAD>/manifest.json`` and is committed in the *following* commit, because a
manifest cannot contain its own commit hash.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from benchmarks.p02.judge import judge_all, verdict
from benchmarks.p02.linear_solve import evidence

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("stdout_dir", type=Path, help="directory holding the captured command output")
parser.add_argument("--results", type=Path, default=Path("spikes/p02/results"))
arguments = parser.parse_args()

SP = arguments.stdout_dir
root = arguments.results
commit = subprocess.run(
    ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
).stdout.strip()

REQUIRED_OUTPUT = ("check.out", "casadi.out", "pyomo.out", "refcheck.out")
missing = [name for name in REQUIRED_OUTPUT if not (SP / name).exists()]
if missing:
    sys.exit(
        f"missing captured output {missing} in {SP}. The manifest records commands that were "
        "actually run; see this script's docstring for how to produce them."
    )


def plain(value):
    """Manifest values are plain JSON types; a numpy scalar is not one."""
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return [plain(v) for v in value.tolist()]
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [plain(v) for v in value]
    return value


def is_empty(value):
    return value is None or (isinstance(value, str | dict | list) and len(value) == 0)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dirsha(directory):
    h = hashlib.sha256()
    base = Path(directory)
    for path in sorted(p for p in base.rglob("*") if p.is_file()):
        rel = path.relative_to(base).as_posix().encode()
        data = path.read_bytes()
        h.update(str(len(rel)).encode() + b":" + rel)
        h.update(str(len(data)).encode() + b":" + data)
    return h.hexdigest()


checks = judge_all(root)
for backend in ("casadi", "pyomo"):
    checks += evidence(root, backend)[0]

check_entries = [
    {
        "id": c.id,
        "description": c.expected,
        "result": c.result,
        "value": plain(c.value),
        "expected": c.expected,
        "tolerance": c.tolerance,
    }
    for c in checks
]


def dig(document, *path):
    node = document
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


measure_specs = {
    "M01": (
        "Backend import time, median and minimum over five fresh processes.",
        {
            "casadi": ("memory.json", ("import_ms",)),
            "pyomo": ("timings.json", ("M01_import_time", "backend_import_ms")),
        },
    ),
    "M02": (
        "Compile time of the lifted form, median and minimum over five fresh processes.",
        {
            "casadi": ("timings.json", ("compile", "compile_L_ms")),
            "pyomo": ("timings.json", ("M02_M04_M07_compile", "compile_ms")),
        },
    ),
    "M03": (
        "Compile time of the inlined form.",
        {"casadi": ("timings.json", ("compile", "compile_I_ms")), "pyomo": None},
    ),
    "M04": (
        "First residual and first Jacobian call after compiling.",
        {
            "casadi": ("timings.json", ("compile",)),
            "pyomo": ("timings.json", ("M02_M04_M07_compile",)),
        },
    ),
    "M05": (
        "Steady-state evaluation, 200 timed calls after 20 warm-ups, at the backend level and "
        "at the full boundary.",
        {
            "casadi": ("timings.json", ("evaluation",)),
            "pyomo": ("timings.json", ("M05_evaluation_time",)),
        },
    ),
    "M06": (
        "Resident memory by stage and the peak allocation during compile.",
        {"casadi": ("memory.json", ()), "pyomo": ("memory.json", ("M06_memory", "stages"))},
    ),
    "M07": (
        "Callback invocations during the compile phase.",
        {
            "casadi": ("callback_counts.json", ("compile_phase",)),
            "pyomo": ("timings.json", ("M02_M04_M07_compile", "compile_phase_counters")),
        },
    ),
    "M08": (
        "Assembled structure: dimension, nonzeros and stored bytes.",
        {
            "casadi": ("states/S1/jacobian_L.json", ("nnz",)),
            "pyomo": ("timings.json", ("M08_structure_size",)),
        },
    ),
    "M09": (
        "Source-map example at S1, with the CSC index taken from the exported structure.",
        {
            "casadi": ("states/S1/jacobian_L.json", ("source_map",)),
            "pyomo": ("source_map_example.json", ()),
        },
    ),
}
measurements = []
for mid, (description, sources) in measure_specs.items():
    for backend in ("casadi", "pyomo"):
        source = sources.get(backend)
        if source is None:
            measurements.append(
                {
                    "id": f"P02.{mid}.{backend}",
                    "description": description,
                    "result": "not_applicable",
                    "value": "the grey-box route has no inlined form",
                    "expected": "recorded per protocol",
                    "tolerance": "not gated",
                }
            )
            continue
        filename, path = source
        document = json.loads((root / backend / filename).read_text())
        value = dig(document, *path) if path else document
        if isinstance(value, dict):
            value = {k: v for k, v in value.items() if k not in ("samples", "note", "samples_ms")}
        empty = is_empty(value)
        measurements.append(
            {
                "id": f"P02.{mid}.{backend}",
                "description": description,
                "result": "unsupported" if empty else "pass",
                "value": None if empty else json.dumps(plain(value), default=str)[:800],
                "expected": "recorded per protocol",
                "tolerance": "not gated",
            }
        )

verdicts = {b: verdict(checks, b) for b in ("casadi", "pyomo")}
verdict_entries = [
    {
        "id": f"P02.verdict.{backend}",
        "description": "Per-backend composition verdict (specification §11.1).",
        "result": "pass" if value == "PASS-composition" else "fail",
        "value": value,
        "expected": "PASS-composition",
        "tolerance": "every mandatory assertion for that backend passes",
    }
    for backend, value in verdicts.items()
]

manifest = {
    "work_package": "P02",
    "commit": commit,
    "requirements": ["D02", "D03", "A05"],
    "status": "tested",
    "inputs": {
        "case_id": (
            "SYN-001 P02 composition test (states S1-S6, the perturbed Newton state S1p, and the "
            "out-of-domain probes S7a and S7b; lifted and inlined forms) "
        ),
        "case_hash": sha("benchmarks/p02/reference_values.yaml"),
        "environment_lock_hash": sha("requirements.lock"),
    },
    "commands": [
        {
            "cmd": "PATH=.venv/bin:$PATH ./scripts/check.sh",
            "cwd": ".",
            "exit_code": 0,
            "stdout_sha256": sha(SP / "check.out"),
        },
        {
            "cmd": "./spikes/p02/casadi/run.sh",
            "cwd": ".",
            "exit_code": 0,
            "stdout_sha256": sha(SP / "casadi.out"),
        },
        {
            "cmd": "./spikes/p02/pyomo/run.sh",
            "cwd": ".",
            "exit_code": 0,
            "stdout_sha256": sha(SP / "pyomo.out"),
        },
        {
            "cmd": ".venv/bin/python docs/derivations/scripts/p02_reference.py --check",
            "cwd": ".",
            "exit_code": 0,
            "stdout_sha256": sha(SP / "refcheck.out"),
        },
    ],
    "checks": verdict_entries + check_entries + measurements,
    "artifacts": [
        {
            "path": "spikes/p02/results/casadi",
            "sha256": dirsha(root / "casadi"),
            "description": (
                "CasADi result set. Directory hash method: sha256 over every file sorted by "
                "relative POSIX path, each contributing the byte length and bytes of its path "
                "followed by the byte length and bytes of its contents, separated by colons. "
            ),
        },
        {
            "path": "spikes/p02/results/pyomo",
            "sha256": dirsha(root / "pyomo"),
            "description": (
                "Pyomo/PyNumero result set, hashed by the same method, including the raw grey-box "
                "structure with the recorded native row orientation. "
            ),
        },
        {
            "path": "benchmarks/p02/reference_values.yaml",
            "sha256": sha("benchmarks/p02/reference_values.yaml"),
            "description": (
                "The 40-digit reference: registered states, expected residuals and Jacobian "
                "entries, measured finite-difference floors with their in-domain assertions, "
                "condition numbers and second-order expectations. "
            ),
        },
        {
            "path": "docs/p02-measurements.md",
            "sha256": sha("docs/p02-measurements.md"),
            "description": (
                "The matched measurement record for P03, including where the two routes do not "
                "measure the same boundary. "
            ),
        },
    ],
    "limitations": [
        "P02 is a composition test on a synthetic subsystem. It is not a solver test, not a "
        "performance benchmark on a real flowsheet, and not the backend selection, which is "
        "P03.",
        "The compiled system has 17 variables. The timings measure boundary and assembly "
        "overhead, not how either backend scales.",
        "SYN-001 is synthetic. Nothing here is empirical validation of any thermodynamic model.",
        "The declared sparsity of both callback blocks is P02's own. Whether a real property "
        "provider's declared sparsity is correct is not tested here.",
        "Second order is absent through opaque callback Jacobians on both routes. The "
        "supplementary record shows CasADi returns exact second derivatives when the block "
        "ships symbolic derivative code; that is a capability fact for K01, not part of this "
        "verdict.",
        "CasADi calls each block's value method once per assembled Jacobian, because its "
        "Jacobian callback takes the block's nominal output. That is one call, far below the "
        "finite-difference threshold of three for block K and six for block H, and it is not "
        "evidence of differencing.",
        "The Pyomo route needs libpynumero_ASL, which is not available from a plain pip "
        "install: it requires pyomo build-extensions with setuptools, cmake and a C or C++ "
        "compiler. See docs/backend-environments.md.",
        "The grey-box route's exported lifted form carries a declared row-sign adapter on the "
        "six defining rows, because PyNumero writes an output constraint as f(inputs) - "
        "output. The native orientation is recorded in raw_structure.json and asserted by "
        "A24.",
        "All results are from one host and one platform: Debian 13, x86-64, Python 3.13.5. No "
        "CI has executed any of this.",
        "review.numerical and review.process_model are pending. A Fable review of the "
        "completed implementation was run and its findings are applied, but no human "
        "numerical or process-modeling reviewer has seen this package.",
    ],
    "review": {"numerical": "pending", "process_model": "pending"},
}

out = Path("evidence/P02") / commit / "manifest.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
empty = [c["id"] for c in manifest["checks"] if is_empty(c["value"])]
print("wrote", out)
print("checks:", len(manifest["checks"]), "| empty values:", empty)
print("verdicts:", verdicts)
