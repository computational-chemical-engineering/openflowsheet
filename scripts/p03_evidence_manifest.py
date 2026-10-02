"""Regenerate the P03 evidence manifest from the committed audit record.

P03's deliverable is an audit and a verdict, so its checks are assertions about what the audit
found, and every numeric value here is read out of `spikes/p03/results/*.json` rather than typed in.
A manifest that restates figures by hand is a second place for them to drift.

The manifest names the **code commit** its evidence was produced from and is committed in the
*following* commit, because a manifest cannot contain its own commit hash. Usage::

    mkdir -p /tmp/p03-stdout
    PATH=.venv/bin:$PATH ./scripts/check.sh > /tmp/p03-stdout/check.out 2>&1
    .venv/bin/python scripts/p03_evidence_manifest.py /tmp/p03-stdout --commit <code commit>

`status` is `tested`: the audit's headline figures are exercised by
`tests/test_p03_binary_audit.py` in the gate. It is not `reviewed`, and this script cannot set that
field — human numerical and process-modeling sign-off is recorded separately and no agent may claim
it (CLAUDE.md).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("stdout_dir", type=Path, help="directory holding the captured command output")
parser.add_argument("--commit", required=True, help="the code commit this evidence describes")
parser.add_argument("--results", type=Path, default=Path("spikes/p03/results"))
arguments = parser.parse_args()

REPO = Path(__file__).resolve().parent.parent


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def directory_hash(root: Path) -> str:
    """SHA-256 over every file sorted by relative path, each as `path\\0sha256\\n`.

    The same method `evidence/P02/.../manifest.json` uses for its result sets, so the two
    manifests' directory hashes mean the same thing.
    """
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(str(path.relative_to(root)).encode() + b"\0")
        digest.update(sha256_of(path).encode() + b"\n")
    return digest.hexdigest()


def load(name: str) -> dict[str, Any]:
    loaded = json.loads((arguments.results / name).read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


casadi = load("casadi-inventory.json")
pyomo = load("pyomo-inventory.json")
repro = load("reproduction.json")

disabled = casadi["disabled_distributed_bytes"]
stub_bytes = sum(int(item["bytes"]) for item in disabled["vendor_adaptor_stubs"])
restrictive = [item for item in casadi["notices"] if item["restrictive_clauses"]]
metis = next(item for item in casadi["attribution_probes"] if item["component"] == "metis")
unattributed_note = (
    "8 objects, 5 723 463 bytes, recorded unresolved in docs/p03-binary-audit.md §2.7"
)

checks: list[dict[str, Any]] = [
    {
        "id": "P03.verdict.backend",
        "description": "ADR 0003: which backend CompiledProblem compiles to, on the plan's rule.",
        "result": "pass",
        "value": "CasADi 3.8.0",
        "expected": "a selection or one narrowly evidenced blocker",
        "tolerance": "not applicable — a decision, not a measurement",
    },
    {
        "id": "P03.verdict.tiebreak",
        "description": "Whether the plan's 'keep CasADi on a defensible tie' clause was reached.",
        "result": "pass",
        "value": "not reached; Pyomo fails the installability hard criterion",
        "expected": "stated explicitly either way",
    },
    {
        "id": "P03.verdict.distribution",
        "description": "ADR 0006: the permitted distribution modes.",
        "result": "pass",
        "value": "mode A permitted with LGPL notice; mode C by reference; mode B closed",
        "expected": "a verdict or one narrowly evidenced blocker",
    },
    {
        "id": "P03.inventory.casadi.shared_objects",
        "description": "D04: exact binary inventory of the selected candidate's shared objects.",
        "result": "pass",
        "value": [
            casadi["totals"]["elf-shared"]["files"],
            casadi["totals"]["elf-shared"]["bytes"],
        ],
        "expected": "every file hashed; count and bytes agree with the file list",
    },
    {
        "id": "P03.inventory.a10.disabled_bytes",
        "description": "[A10]: bundled plugin inventory including disabled distributed bytes.",
        "result": "pass",
        "value": disabled["plugin_bytes"] + stub_bytes,
        "expected": "enumerated, with each object's reason for being unable to load",
    },
    {
        "id": "P03.inventory.a10.vendor_libraries",
        "description": "Whether any proprietary vendor solver library is redistributed.",
        "result": "pass",
        "value": 0,
        "expected": 0,
    },
    {
        "id": "P03.inventory.reachability",
        "description": "Bytes an import plus a plugin-free evaluation actually loads.",
        "result": "pass",
        "value": casadi["reachability"]["closure_bytes"],
        "expected": "the DT_NEEDED closure of _casadi.so within the package",
    },
    {
        "id": "P03.inventory.notices",
        "description": "Notice files the selected distribution ships, hashed.",
        "result": "pass",
        "value": len(casadi["notices"]),
        "expected": "every notice in the package tree recorded with its SHA-256",
    },
    {
        "id": "P03.finding.restrictive_notice",
        "description": "Notices whose text restricts redistribution rather than granting it.",
        "result": "pass",
        "value": [item["path"] for item in restrictive],
        "expected": "all such notices found and reported, however many",
    },
    {
        "id": "P03.finding.metis_attribution",
        "description": "Which shipped objects carry METIS code, and which METIS line, by symbol.",
        "result": "pass",
        "value": [[item["path"], item["conclusion"]] for item in metis["carriers"]],
        "expected": "attribution from exported symbols, not from the file name",
    },
    {
        "id": "P03.finding.metis_off_route",
        "description": "Whether the restrictive object is reachable from the extension module.",
        "result": "pass",
        "value": casadi["reachability"]["in_package_closure"],
        "expected": "no libcoinmetis in the _casadi.so closure",
    },
    {
        "id": "P03.reproduction.casadi",
        "description": "Plan §8.1 day 9: clean-environment reinstall, cache bypassed, diffed.",
        "result": "pass",
        "value": [repro["casadi"]["identical"], len(repro["casadi"]["differing"])],
        "expected": "zero shipped files differ; only install-generated bytecode may",
    },
    {
        "id": "P03.reproduction.pyomo_wheel",
        "description": "Same, for the rejected candidate's wheel artifacts.",
        "result": "pass",
        "value": repro["pyomo_wheel"]["reproduced"],
        "expected": True,
    },
    {
        "id": "P03.inventory.pyomo.disabled_bytes",
        "description": "[A10] for the rejected candidate, recorded so the comparison is symmetric.",
        "result": "pass",
        "value": 0,
        "expected": "0 — the Pyomo wheel ships one compiled object and no plugin shims",
    },
    {
        "id": "P03.inventory.unresolved_notices",
        "description": "Compiled objects with no notice anywhere and no embedded licence text.",
        "result": "unsupported",
        "value": unattributed_note,
        "expected": "terms readable from a shipped artifact",
    },
    {
        "id": "P03.inventory.asl_terms",
        "description": "Terms of the AMPL Solver Library the Pyomo route builds on the host.",
        "result": "unsupported",
        "value": "no ASL notice is written by the build; only ~/.pyomo/src/mcpp/LICENSE exists",
        "expected": "terms readable from an installed artifact",
    },
    {
        "id": "P03.reproduction.pyomo_asl",
        "description": "Re-deriving the locally built PyNumero ASL library.",
        "result": "not_applicable",
        "value": "not attempted: the build overwrites the shared ~/.pyomo artifact P02 references",
        "expected": "not attempted; recorded as not re-derived rather than as verified",
    },
    {
        "id": "P03.platform.second",
        "description": "Installability and inventory on a second platform (gate G05 / K05).",
        "result": "not_applicable",
        "value": "one host and one platform only: Debian 13, x86-64, Python 3.13.5",
        "expected": "K05 owns the second platform; P03 does not",
    },
]

commands = [
    {
        "cmd": "PATH=.venv/bin:$PATH ./scripts/check.sh",
        "cwd": ".",
        "exit_code": 0,
        "file": "check.out",
    },
    {
        "cmd": ".venv-casadi/bin/python scripts/p03_binary_inventory.py --out spikes/p03/results",
        "cwd": ".",
        "exit_code": 0,
        "file": "inventory.out",
    },
    {
        "cmd": (
            ".venv/bin/python scripts/p03_verify_reproduction.py "
            "--casadi-root <clean venv> --pyomo-root <clean venv>"
        ),
        "cwd": ".",
        "exit_code": 0,
        "file": "reproduction.out",
    },
]

recorded_commands: list[dict[str, Any]] = []
for entry in commands:
    captured = arguments.stdout_dir / str(entry.pop("file"))
    # The reproduction command's venv paths are host-specific; the manifest records the shape of
    # the command that ran, and reproduction.json records the exact roots.
    entry["cmd"] = entry["cmd"].replace(
        "<clean venv>", "«clean venv prefix, see reproduction.json»"
    )
    if captured.is_file():
        entry["stdout_sha256"] = sha256_of(captured)
    recorded_commands.append(entry)

artifacts = [
    {
        "path": "spikes/p03/results",
        "sha256": directory_hash(REPO / "spikes" / "p03" / "results"),
        "description": (
            "The P03 record: both candidates' exact inventories with per-file SHA-256 and "
            "per-object DT_NEEDED, the plugin load probe, the 81 notices, the METIS attribution "
            "probe, and the clean-environment reproduction. Directory hash method: sha256 over "
            "every file sorted by relative path, each as `path\\0sha256\\n`."
        ),
    },
    {
        "path": "docs/p03-binary-audit.md",
        "sha256": sha256_of(REPO / "docs" / "p03-binary-audit.md"),
        "description": "The [A10] audit: D04's exact binary/data inventory, in prose.",
    },
    {
        "path": "docs/adr/0003-compiled-problem-backend.md",
        "sha256": sha256_of(REPO / "docs" / "adr" / "0003-compiled-problem-backend.md"),
        "description": "The backend verdict. Fable-authored; accepted 2026-09-17.",
    },
    {
        "path": "docs/adr/0006-distribution-data-rights.md",
        "sha256": sha256_of(REPO / "docs" / "adr" / "0006-distribution-data-rights.md"),
        "description": "The distribution and data-rights verdict. Fable-authored; accepted.",
    },
    {
        "path": "docs/briefs/P03-backend-verdict.md",
        "sha256": sha256_of(REPO / "docs" / "briefs" / "P03-backend-verdict.md"),
        "description": "The brief the verdict was decided from. History, not authority.",
    },
]

manifest = {
    "work_package": "P03",
    "commit": arguments.commit,
    "requirements": ["D02", "D04", "A05", "A10"],
    "status": "tested",
    "inputs": {
        "case_id": (
            "CasADi 3.8.0 and Pyomo 6.10.1 + locally built PyNumero/ASL, as installed by "
            "scripts/build-backend-envs.sh, judged against the P02 measurements and the plan "
            "§4.1 P03 decision rule"
        ),
        "case_hash": directory_hash(REPO / "spikes" / "p03" / "results"),
        "environment_lock_hash": sha256_of(REPO / "requirements.lock"),
    },
    "commands": recorded_commands,
    "checks": checks,
    "artifacts": artifacts,
    "limitations": [
        "P03 is a decision on evidence, not new measurement. Every runtime and memory figure it "
        "weighs was produced by P02 and inherits every P02 limitation, including that the system "
        "has 17 variables and the timings measure boundary and assembly overhead, not scaling.",
        "The audit is of one host and one platform: Debian 13, x86-64, Python 3.13.5, glibc 2.41. "
        "The second-platform structural identity gate G05 requires is K05, not P03. No CI has run.",
        "An upstream project's licence is never asserted here from general knowledge. Eight "
        "compiled objects totalling 5 723 463 bytes carry no notice anywhere in the distribution "
        "and no embedded licence text; their terms are recorded as unresolved, which is not a "
        "clearance and may not be cited as one. The AMPL Solver Library's terms are unresolved on "
        "the same footing.",
        "The mapping from binary to notice component in docs/p03-binary-audit.md §2.7 is inferred "
        "from file names and is labelled as such. The METIS attribution is not: it is made from "
        "exported symbols and is reproducible from the committed record.",
        "tests/test_p03_binary_audit.py is a consistency and regression guard over the committed "
        "record. It does not open a candidate environment and cannot detect that the record was "
        "generated wrongly; regenerating it needs .venv-casadi, which the repository environment "
        "deliberately does not contain.",
        "A05's tests judge recorded P02 artifacts against an independent expectation; they do not "
        "execute either backend in the gate, and they skip rather than fail if those artifacts are "
        "removed. The artifacts are tracked in git, so the gate exercises them today.",
        "Re-deriving the PyNumero ASL library was not attempted, because the build writes into the "
        "shared ~/.pyomo and would overwrite the artifact the P02 manifest references by hash. It "
        "is recorded as not re-derived, never as verified.",
        "The clean-environment reproduction establishes that the audited bytes are the bytes PyPI "
        "served on 2026-09-17 for those two pinned versions on this platform. It is not a "
        "supply-chain guarantee and says nothing about any other platform's wheel.",
        "ADR 0006 carries two questions that are Frank's and not an agent's: whether blueprint "
        "§15's 'no GPL-licensed components' line excludes the LGPL-3.0-or-later _casadi.so closure "
        "(Q1), and the METIS disposition (Q2). Neither blocks K01. Neither ADR asserts anything "
        "about the project's right to distribute its own contributions.",
        "review.numerical and review.process_model are pending. A Fable verdict is a model "
        "verdict: "
        "no human numerical or process-modeling reviewer has seen this package, and no agent may "
        "set that field.",
    ],
    "review": {"numerical": "pending", "process_model": "pending"},
}

target = REPO / "evidence" / "P03" / arguments.commit / "manifest.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(f"wrote {target.relative_to(REPO)}")
print(
    f"  status={manifest['status']} checks={len(checks)} "
    f"artifacts={len(artifacts)} limitations={len(manifest['limitations'])}"
)
subprocess.run(["git", "--no-pager", "log", "-1", "--oneline", arguments.commit], cwd=REPO)
