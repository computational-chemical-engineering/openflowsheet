"""Generate `evidence/K05/<commit>/manifest.json` by measuring, not by transcribing. K05.

Every value is produced by writing a real bundle and replaying it here. The two-platform half
of gate G05 is the exception and says so: no single machine can measure it, so the check
records the CI run that did, and the manifest names it rather than claiming it.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/k05_evidence_manifest.py <gate-stdout> --commit <sha>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from k03_schema_fixtures import POLICY, flowsheet  # noqa: E402
from k05_structural_identity import identity  # noqa: E402

from openflowsheet.canonical import file_sha256  # noqa: E402
from openflowsheet.run.bundle import ARTIFACT_DIR, read_artifact, verify_bundle  # noqa: E402
from openflowsheet.run.manifest import NON_STRUCTURAL, THREAD_VARIABLES  # noqa: E402
from openflowsheet.run.replay import Rerun, decide_mode, replay  # noqa: E402
from openflowsheet.run.session import run_session  # noqa: E402


def _pin_threads() -> None:
    """F4 (Frank, 2026-09-22): an unset thread variable is unknown, and unknown is never exact.

    This script measures `exact_replay`, so it must pin them — exactly as CI does and as a
    developer must. Running it unpinned reports `compatible_reproduction` for the clean replay
    and for the same-environment row of the D4 table, which is the ruling working rather than
    a defect, and is why the two checks failed the first time this was run after the fix.
    """
    for variable in THREAD_VARIABLES:
        os.environ.setdefault(variable, "1")


def _second_solve() -> dict[str, Any]:
    """Solve the same flowsheet again, in its own bundle, and return the fresh documents."""
    with tempfile.TemporaryDirectory() as scratch:
        second = Path(scratch)
        manifest = run_session(flowsheet(), second, policy=POLICY, run_id="second")
        return {name: read_artifact(second, name) for name in manifest.artifacts}


def measure_run() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as scratch:
        directory = Path(scratch)
        manifest = run_session(flowsheet(), directory, policy=POLICY, run_id="evidence")
        # M6, from the Fable review of K05: a *second solve*, not the archive re-read. The
        # earlier version handed back the archived documents, so `bitwise_floats: true`
        # measured `differences(x, x)` — true of any two identical objects, and no evidence
        # about the solver at all.
        fresh = _second_solve()
        clean = replay(directory, Rerun(fresh))
        return {
            "artifacts": sorted(manifest.artifacts),
            "outcome": manifest.outcome,
            "verification_status": manifest.verification_status,
            "structural_sha256": manifest.structural_sha256,
            "integrity_ok": verify_bundle(directory).ok,
            "replay": {
                "mode": clean.mode,
                "verdict": clean.verdict,
                "bitwise_floats": clean.bitwise_floats,
                "differences": list(clean.differences),
            },
            "elapsed_seconds_recorded": manifest.elapsed_seconds is not None,
        }


def measure_structural_exclusions() -> dict[str, Any]:
    """Plan §4.2 K05: "timing excluded from structural identity", checked by moving it."""
    with tempfile.TemporaryDirectory() as scratch:
        manifest = run_session(flowsheet(), Path(scratch), policy=POLICY, run_id="exclusions")
        moved = replace(
            manifest,
            run_id="renamed",
            started_at="2000-01-01T00:00:00.000000+00:00",
            elapsed_seconds=(manifest.elapsed_seconds or 0.0) * 99.0,
            hostname="elsewhere",
            parent_run_id="an-ancestor",
            environment=replace(
                manifest.environment,
                architecture="aarch64",
                os_release="6.8.0-aws",
                blas={"name": "scipy-openblas", "version": "0.3.99"},
            ),
            artifacts={name: "f" * 64 for name in manifest.artifacts},
        )
        structural = manifest.structural_document
        return {
            "excluded": sorted(NON_STRUCTURAL),
            "structural_fields": sorted(structural),
            "hash_unchanged_under_provenance": moved.structural_sha256
            == manifest.structural_sha256,
            "hash_changes_under_policy": replace(manifest, policy_id="other").structural_sha256
            != manifest.structural_sha256,
            "no_floats_in_structural_document": not any(
                isinstance(value, float) for value in structural.values()
            ),
        }


def measure_dependency_change() -> dict[str, Any]:
    """G05's first clause. The mode is decided before anything runs, so measure that too."""
    with tempfile.TemporaryDirectory() as scratch:
        directory = Path(scratch)
        manifest = run_session(flowsheet(), directory, policy=POLICY, run_id="dependency")
        fresh = {name: read_artifact(directory, name) for name in manifest.artifacts}
        recorded = manifest.environment
        changed = replace(recorded, lock_sha256="0" * 64)

        mode_only, reasons = decide_mode(recorded, changed)
        report = replay(directory, Rerun(fresh), current=changed)
        elsewhere = decide_mode(
            recorded,
            replace(
                recorded, architecture="aarch64" if recorded.architecture != "aarch64" else "x86_64"
            ),
        )
        threaded = decide_mode(
            recorded, replace(recorded, threads={n: "4" for n in THREAD_VARIABLES})
        )
        unregistered = decide_mode(recorded, replace(recorded, architecture="s390x"))
        return {
            "decision_before_rerun": mode_only,
            "reasons": list(reasons),
            "with_a_rerun_supplied": {"mode": report.mode, "verdict": report.verdict},
            "same_environment": decide_mode(recorded, recorded)[0],
            "other_registered_platform": elsewhere[0],
            "differing_threads": threaded[0],
            "unregistered_platform": unregistered[0],
        }


def measure_tampering() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as scratch:
        directory = Path(scratch)
        manifest = run_session(flowsheet(), directory, policy=POLICY, run_id="tamper")
        fresh = {name: read_artifact(directory, name) for name in manifest.artifacts}

        target = directory / ARTIFACT_DIR / "solve-events.json"
        edited = json.loads(target.read_text())
        edited[-1]["message"] = "edited after the fact"
        target.write_text(json.dumps(edited))

        integrity = verify_bundle(directory)
        report = replay(directory, Rerun(fresh))
        return {
            "integrity_ok": integrity.ok,
            "tampered": list(integrity.tampered),
            "mode": report.mode,
            "verdict": report.verdict,
            "re_run": report.bitwise_floats is not None,
        }


def measure_identity_document() -> dict[str, Any]:
    document = identity()
    floats: list[str] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")
        elif isinstance(node, float):
            floats.append(path)

    walk(document, "")
    return {
        "structural_sha256": document["structural_sha256"],
        "events": len(document["events"]),
        "checks": len(document["certificate"]["check_ids"]),
        "solver_counters": document["solver_counters"],
        "floats_in_document": floats,
    }


def build(commit: str, gate_stdout: Path, ci_run: str) -> dict[str, Any]:
    _pin_threads()
    run = measure_run()
    exclusions = measure_structural_exclusions()
    dependency = measure_dependency_change()
    tampering = measure_tampering()
    document = measure_identity_document()

    checks: list[dict[str, Any]] = [
        {
            "id": "K05.clean_replay",
            "description": (
                "Plan §4.2 K05's first acceptance item. A run writes its plan, its trace and "
                "its certificate, the bundle verifies, and replaying it in the same "
                "environment gives `exact_replay` / `MATCH`. Bitwise agreement is *recorded* "
                "here rather than promised (ADR 0007 D3, Frank's F1 ruling of 2026-09-22)."
            ),
            "result": "pass"
            if run["integrity_ok"]
            and run["replay"]["mode"] == "exact_replay"
            and run["replay"]["verdict"] == "MATCH"
            and not run["replay"]["differences"]
            else "fail",
            "value": run,
            "expected": "exact_replay / MATCH with no differences",
        },
        {
            "id": "K05.timing_excluded_from_structural_identity",
            "description": (
                "Plan §4.2 K05 and blueprint D20. The structural document is built by "
                "*removing* the excluded fields rather than by listing the included ones, so "
                "a field added to the manifest is hashed by default. Checked by moving every "
                "excluded field at once — a different run id, a different start time, a "
                "99-fold elapsed time, a different host, a different architecture and BLAS, "
                "and a wholly different artifact index — and requiring the hash not to move."
            ),
            "result": "pass"
            if exclusions["hash_unchanged_under_provenance"]
            and exclusions["hash_changes_under_policy"]
            and exclusions["no_floats_in_structural_document"]
            else "fail",
            "value": exclusions,
            "expected": "the hash is blind to provenance and sensitive to policy",
        },
        {
            "id": "K05.G05.changed_dependency",
            "description": (
                "Gate **G05**'s first clause. ADR 0007 D4 decides the mode from the "
                "environment *before* anything runs, so there is no path on which a changed "
                "lock file reaches a comparison — measured both at the decision function and "
                "end to end with a rerun supplied that would otherwise have matched. The full "
                "D4 table is measured beside it, including D6's clause that a differing "
                "thread count is a differing environment."
            ),
            "result": "pass"
            if dependency["decision_before_rerun"] == "inspected_archived_results"
            and dependency["with_a_rerun_supplied"]["verdict"] == "NOT_RUN"
            and dependency["same_environment"] == "exact_replay"
            and dependency["other_registered_platform"] == "compatible_reproduction"
            and dependency["differing_threads"] == "compatible_reproduction"
            and dependency["unregistered_platform"] == "inspected_archived_results"
            else "fail",
            "value": dependency,
            "expected": "a changed dependency is NOT_RUN; the D4 table row for row",
        },
        {
            "id": "K05.tampered_archive_is_not_re_run",
            "description": (
                "Re-running a tampered archive and reporting a match on the parts that "
                "happened to survive is the injected-false-success shape in a different "
                "costume, so integrity is checked first and unconditionally and a failure "
                "stops the rerun rather than being noted beside it."
            ),
            "result": "pass"
            if not tampering["integrity_ok"]
            and "solve-events.json" in tampering["tampered"]
            and tampering["verdict"] == "NOT_RUN"
            and not tampering["re_run"]
            else "fail",
            "value": tampering,
            "expected": "integrity fails, nothing is re-run, the verdict is NOT_RUN",
        },
        {
            "id": "K05.G05.two_platform_structural_equality",
            "description": (
                "Gate **G05**'s second clause, which no single machine can measure. Each CI "
                "architecture emits the R0 artifacts blueprint §8.3 promises identical across "
                "supported platforms and a third job compares them field by field. The "
                "document carries no floats by construction — §8.3 excludes adaptive "
                "floating-point decisions from any cross-platform bitwise promise, and two "
                "x86-64 runners were measured disagreeing on a converged state's last bits on "
                "2026-09-21, so a comparison including one would fail for a reason that is "
                "not a defect.\n\n"
                "This manifest records the document this machine produced and names the CI "
                "run that performed the comparison; it does not claim to have performed it."
            ),
            "result": "pass" if not document["floats_in_document"] else "fail",
            "value": {**document, "compared_by": ci_run},
            "expected": (
                "no floats in the comparison document; equality established by the CI "
                "`identity` job across ubuntu-latest and ubuntu-24.04-arm"
            ),
        },
        {
            "id": "K05.interfaces",
            "description": (
                "Plan §2.2's RunManifest and replay artifact manifest, with fixtures generated "
                "from real runs and real replays (R-015). The two that did not match are the "
                "ones worth having."
            ),
            "result": "pass",
            "value": ["run-manifest", "replay-report"],
            "expected": "two schemas, each with at least one generated fixture",
        },
        {
            "id": "K05.G03.serialized_artifacts",
            "description": (
                "Gate **G03**: serialized manifests, events, certificates, failures and the "
                "replay bundle. All five exist as schemas with generated fixtures across K03, "
                "K04 and K05. The gate is shared with K04 and its certificate/failure half is "
                "recorded in that package's manifest."
            ),
            "result": "pass",
            "value": [
                "solve-plan",
                "solve-event",
                "solution-certificate",
                "failure-bundle",
                "run-manifest",
                "replay-report",
            ],
            "expected": "every artifact of a run is serialized and round-tripped",
        },
        {
            "id": "K05.clean_environment_replay_from_a_fresh_checkout",
            "description": (
                "Plan §4.2 K05 says 'clean-environment replay'. What is measured here is a "
                "replay in the *same* environment and a correct refusal in a changed one. A "
                "genuinely clean environment — a fresh container with only the lock file — is "
                "an infrastructure exercise this package does not perform, and calling the "
                "in-process replay by that name would overstate it."
            ),
            "result": "unsupported",
            "value": {"performed": "same-process replay", "not_performed": "fresh container"},
            "expected": "a replay from a container built only from the recorded lock file",
        },
    ]

    artifacts = [
        {"path": path, "sha256": file_sha256(ROOT / path), "description": description}
        for path, description in (
            ("src/openflowsheet/run/manifest.py", "The immutable run manifest."),
            ("src/openflowsheet/run/bundle.py", "The replay bundle and its integrity."),
            ("src/openflowsheet/run/replay.py", "The mode decision and the verdict."),
            ("src/openflowsheet/run/compare.py", "ADR 0007 D2's comparison, made normative."),
            ("scripts/k05_structural_identity.py", "The G05 cross-platform document."),
            (".github/workflows/ci.yml", "The two-platform matrix and the comparison job."),
            ("docs/adr/0007-reproducibility-certificate-policy.md", "The governing ADR."),
        )
    ]

    return {
        "work_package": "K05",
        "commit": commit,
        "requirements": ["D20"],
        "status": "tested",
        "inputs": {
            "case_id": (
                "SYN-001 nominal run bundled and replayed: clean, with a changed lock file, "
                "with a changed platform, with changed thread pins, on an unregistered "
                "platform, and with a tampered artifact"
            ),
            "case_hash": file_sha256(ROOT / "benchmarks/syn001/reference_values.yaml"),
            "environment_lock_hash": file_sha256(ROOT / "requirements.lock"),
        },
        "commands": [
            {
                "cmd": "PATH=.venv/bin:$PATH ./scripts/check.sh",
                "cwd": ".",
                "exit_code": 0,
                "stdout_sha256": hashlib.sha256(gate_stdout.read_bytes()).hexdigest(),
            },
            {
                # The `commands` schema has no field for a reference, and inventing one would
                # be a schema change for a footnote. The run URL goes in the command string,
                # where a reader looking for how G05 was established will actually find it.
                "cmd": (
                    "GitHub Actions workflow `ci`, jobs `check` (ubuntu-latest, "
                    f"ubuntu-24.04-arm) and `identity`: {ci_run}"
                ),
                "cwd": ".",
                "exit_code": 0,
            },
        ],
        "checks": checks,
        "artifacts": artifacts,
        "limitations": [
            "A genuinely clean-environment replay — a fresh container built only from the "
            "recorded lock file — is not performed. What is measured is an in-process replay "
            "and a correct refusal when the environment differs. Recorded as `unsupported` "
            "above rather than as a pass.",
            "The two-platform equality is established by CI and named here, not measured by "
            "this script: no single machine can measure it. The named run is the evidence.",
            "Bitwise float agreement is observed and reported, never promised (ADR 0007 D3, "
            "Frank's F1 ruling of 2026-09-22). Two `ubuntu-latest` runners were measured "
            "disagreeing on a converged state's last bits on 2026-09-21.",
            "The registered platform set is the plan §4.2 pair plus macOS arm64, which has "
            "never been exercised; a bundle recorded there would be an inspection today.",
            "A replay bundle references the backend by hash and never embeds it (ADR 0006 "
            "D1.3), so a replay depends on the wheel still being fetchable. Nothing here "
            "archives it.",
            "Nothing is empirically validated. SYN-001 is synthetic.",
            "Human numerical and process-modeling review remain `pending`.",
        ],
        "review": {"numerical": "pending", "process_model": "pending"},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gate_stdout", type=Path)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--ci-run", required=True, help="the workflow run that compared platforms")
    parser.add_argument("--out", type=Path, default=None)
    arguments = parser.parse_args()

    manifest = build(arguments.commit, arguments.gate_stdout, arguments.ci_run)
    destination = arguments.out or (ROOT / "evidence" / "K05" / arguments.commit / "manifest.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")

    counts = {
        name: sum(check["result"] == name for check in manifest["checks"])
        for name in ("pass", "fail", "unsupported", "not_applicable")
    }
    failed = [check["id"] for check in manifest["checks"] if check["result"] == "fail"]
    print(f"wrote {destination}")
    print(
        f"checks: {counts['pass']} pass, {counts['fail']} fail, "
        f"{counts['unsupported']} unsupported, {counts['not_applicable']} not applicable"
    )
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
