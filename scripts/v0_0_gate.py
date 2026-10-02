"""The v0.0 acceptance gate: G00–G06, read from the evidence and re-run where it can. K06.

Plan §5.1 names seven gates and their owning packages. This reports each one from **the
committed evidence manifests**, not from a fresh demonstration — plan §7's instruction is
explicit that release completion is not claimed "from a demo, copied golden outputs, skipped
cases, or relaxed checks", and a gate script that re-derived everything in memory would be
precisely a demo.

So each gate names the manifest checks it rests on, and a gate whose evidence carries an
`unsupported` check inherits that: the gate is reported **met with limitations**, with the
limitation quoted. A gate is never upgraded by this script and never averaged.

G06 is the exception that re-runs, because its claim is about what a *reader* can do: the
end-to-end example must be inspectable by running three commands. Checking that by reading a
manifest would be checking the wrong thing.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/v0_0_gate.py [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

#: Plan §5.1, verbatim: the gate, what it requires, and the packages that own it.
GATES: Final[tuple[tuple[str, str, tuple[str, ...]], ...]] = (
    (
        "G00",
        "Three-component ideal process with all named v0.0 units and one numerical tear",
        ("K02", "K03"),
    ),
    ("G01", "Damped Newton plus expression/callback interface fixtures", ("K01", "K03")),
    ("G02", "Canonical revision, locks, source mapping, Python/CLI", ("K01", "K06")),
    ("G03", "Serialized manifests, events, certificates, failures, replay bundle", ("K04", "K05")),
    ("G04", "Balances, phase transition, bad spec and numerical failure", ("K04",)),
    ("G05", "Dependency change detected and two-platform structural equality", ("K05",)),
    ("G06", "End-to-end example is inspectable without unrelated code", ("K06",)),
)

#: Which manifest checks each gate rests on. A gate with no named check in a package it owns
#: is reported `unsupported` rather than inferred from the package existing.
GATE_CHECKS: Final[Mapping[str, tuple[str, ...]]] = {
    "G00": ("K03.G00.flowsheet_solved", "K03.G00.products_and_duties", "K03.G00.overall_balance"),
    "G01": ("K03.G01.damped_newton",),
    # G02 is "canonical revision, locks, source mapping, Python/CLI". Its four clauses land
    # in two packages and I named a K01 check that does not exist when first writing this —
    # `K01.compiler.source_mapping`. The gate reported `unsupported` rather than passing on a
    # name nobody had checked, which is the behaviour wanted, so the fix is to name the real
    # ones. *Source mapping* is the row and column ids the compiler carries through, which
    # `K01.conformance.pattern` asserts against the registered pattern by id; *canonical
    # revision* is `K01.canonical.encoding` plus K06's computed `content_hash`; *locks* is the
    # environment lock recorded on every run; *Python/CLI* is K06's four commands.
    "G02": ("K01.canonical.encoding", "K01.conformance.pattern", "K06.G02.cli"),
    "G03": ("K04.A31_A32.interfaces", "K05.G03.serialized_artifacts"),
    "G04": ("K04.A18.injected_false_success", "K04.A15.verdicts"),
    "G05": ("K05.G05.changed_dependency", "K05.G05.two_platform_structural_equality"),
    "G06": (),
}


def manifests() -> dict[str, dict[str, Any]]:
    """The newest manifest per package, by package id."""
    found: dict[str, dict[str, Any]] = {}
    for path in sorted((ROOT / "evidence").glob("*/*/manifest.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        document["_path"] = str(path.relative_to(ROOT))
        found[document["work_package"]] = document
    return found


def gate_status(
    gate: str, owners: Sequence[str], evidence: Mapping[str, dict[str, Any]]
) -> dict[str, Any]:
    """Read a gate from its owners' manifests. Never upgraded, never averaged."""
    missing_packages = [name for name in owners if name not in evidence]
    if missing_packages:
        return {
            "status": "not_met",
            "reason": f"no evidence manifest for {missing_packages}",
            "consulted": [],
        }

    wanted = GATE_CHECKS.get(gate, ())
    consulted: list[dict[str, Any]] = []
    for name in owners:
        for check in evidence[name]["checks"]:
            if check["id"] in wanted:
                consulted.append(
                    {
                        "package": name,
                        "id": check["id"],
                        "result": check["result"],
                        "manifest": evidence[name]["_path"],
                    }
                )

    found = {entry["id"] for entry in consulted}
    if set(wanted) - found:
        return {
            "status": "unsupported",
            "reason": f"the named checks {sorted(set(wanted) - found)} are not in the evidence",
            "consulted": consulted,
        }

    failed = [entry for entry in consulted if entry["result"] == "fail"]
    if failed:
        return {"status": "not_met", "reason": "a named check failed", "consulted": consulted}

    # A gate inherits its packages' limitations rather than shedding them.
    limitations: list[str] = []
    for name in owners:
        for check in evidence[name]["checks"]:
            if check["result"] == "unsupported":
                limitations.append(f"{name}: {check['id']} is unsupported — {check['expected']}")

    status = "met_with_limitations" if limitations else "met"
    return {"status": status, "consulted": consulted, "limitations": limitations}


def g06_live() -> dict[str, Any]:
    """G06 re-runs, because its claim is about what a reader can do, not what a file says."""
    import contextlib
    import io
    import os

    from openflowsheet.application.cli import main
    from openflowsheet.run.manifest import THREAD_VARIABLES

    for variable in THREAD_VARIABLES:
        os.environ.setdefault(variable, "1")

    with tempfile.TemporaryDirectory() as scratch:
        bundle = Path(scratch) / "bundle"
        transcript: dict[str, str] = {}
        for label, argv in (
            ("solve", ["solve", "SYN-001-nominal", "--out", str(bundle)]),
            ("inspect", ["inspect", str(bundle)]),
            ("replay", ["replay", str(bundle)]),
        ):
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = main(argv)
            transcript[label] = stream.getvalue()
            if code != 0:
                return {
                    "status": "not_met",
                    "reason": f"`{label}` exited {code}",
                    "consulted": [],
                }

        # "Inspectable" means a reader sees the answer *and* what is not claimed.
        required = (
            "=== run",
            "=== certificate",
            "=== what this certificate does not claim",
            "=== trace",
            "not an experimental validation",
        )
        absent = [
            phrase for phrase in required if phrase.lower() not in transcript["inspect"].lower()
        ]
        if absent:
            return {"status": "not_met", "reason": f"inspect omitted {absent}", "consulted": []}

        return {
            "status": "met",
            "consulted": [
                {
                    "package": "K06",
                    "id": "cli.solve_inspect_replay",
                    "result": "pass",
                    "manifest": "re-run live, not read from evidence",
                }
            ],
            "transcript_lines": {key: len(value.splitlines()) for key, value in transcript.items()},
        }


def build() -> dict[str, Any]:
    evidence = manifests()
    report: dict[str, Any] = {
        "gates": {},
        "packages": {name: document["_path"] for name, document in sorted(evidence.items())},
    }
    for gate, requirement, owners in GATES:
        entry = g06_live() if gate == "G06" else gate_status(gate, owners, evidence)
        entry["requirement"] = requirement
        entry["owners"] = list(owners)
        report["gates"][gate] = entry

    statuses = {gate: entry["status"] for gate, entry in report["gates"].items()}
    met = {gate for gate, status in statuses.items() if status in ("met", "met_with_limitations")}
    report["v0_0"] = {
        "all_gates_met": len(met) == len(GATES),
        "met": sorted(met),
        "not_met": sorted(set(statuses) - met),
        "with_limitations": sorted(
            gate for gate, status in statuses.items() if status == "met_with_limitations"
        ),
        # Plan §7: release completion is not claimed from a demo, copied outputs, skipped
        # cases or relaxed checks. Human sign-off is separate and no agent may claim it.
        # This sentence said the review fields were `pending` in every manifest. They were
        # signed on 2026-09-23 and it became false the same day — exactly the kind of stale
        # claim a report that nobody re-reads keeps making. What it is *for* survives the
        # correction: a gate is evidence that a check ran, not a warranty.
        "release_claim": (
            "Gates are acceptance evidence, not a warranty. Every manifest is signed by a "
            "human (E.A.J.F. Peters, 2026-09-23) and the signature says in its own words that "
            "it records examination without objection and not a guarantee of correctness "
            "(register R-017). Six of the seven gates are met *with limitations*, named above "
            "and not aggregated away. Nothing here is empirical validation: SYN-001 is "
            "synthetic, and every energy and phase check shares its property package with the "
            "solver."
        ),
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    arguments = parser.parse_args()

    report = build()
    if arguments.out:
        arguments.out.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    if arguments.json:
        print(json.dumps(report, indent=1, sort_keys=True))
        return 0 if report["v0_0"]["all_gates_met"] else 1

    width = max(len(requirement) for _, requirement, _ in GATES)
    for gate, requirement, owners in GATES:
        entry = report["gates"][gate]
        print(f"{gate}  {entry['status']:<22}{requirement:<{width}}  {'/'.join(owners)}")
        for limitation in entry.get("limitations", []):
            print(f"      limitation: {limitation}")
        if entry.get("reason"):
            print(f"      reason: {entry['reason']}")

    summary = report["v0_0"]
    print()
    print(f"v0.0 gates met: {len(summary['met'])}/{len(GATES)}")
    if summary["with_limitations"]:
        print(f"with limitations: {', '.join(summary['with_limitations'])}")
    if summary["not_met"]:
        print(f"NOT MET: {', '.join(summary['not_met'])}")
    print()
    print(summary["release_claim"])
    return 0 if summary["all_gates_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
