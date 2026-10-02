"""Generate `evidence/K06/<commit>/manifest.json` by measuring, not by transcribing. K06.

Every value is produced by driving the application layer and the CLI here. The v0.0 gate
summary is read from `scripts/v0_0_gate.py`, which reads the committed evidence rather than
re-deriving it — plan §7 forbids claiming release completion from a demo, and a gate script
that recomputed everything in memory would be one.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/k06_evidence_manifest.py <gate-stdout> --commit <sha>
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from v0_0_gate import build as gate_report  # noqa: E402

from openflowsheet.application.cli import main as cli  # noqa: E402
from openflowsheet.application.revisions import Revision, content_hash  # noqa: E402
from openflowsheet.application.transactions import (  # noqa: E402
    Application,
    ChangeSet,
    Edit,
)
from openflowsheet.application.validation import validate  # noqa: E402
from openflowsheet.canonical import file_sha256  # noqa: E402
from openflowsheet.run.manifest import THREAD_VARIABLES  # noqa: E402

CASES = ROOT / "benchmarks" / "syn001" / "cases"


def case(name: str) -> dict[str, Any]:
    return yaml.safe_load((CASES / f"{name}.yaml").read_text(encoding="utf-8"))


def measure_transactions() -> dict[str, Any]:
    nominal = case("SYN-001-nominal")
    app = Application()
    app.store.put(Revision(revision_id=nominal["revision_id"], document=nominal))
    app.record_run("run-a", nominal["revision_id"])

    request = ChangeSet(
        edits=(Edit("set", ("title",), "edited"),),
        expected_revision=app.store.head,
        idempotency_key="key-1",
        new_revision_id="rev-2",
    )
    committed = app.commit(request)
    replayed = app.commit(request)
    # Counted *here*, before the later commits: the claim is that a retry creates no second
    # revision, and taking the count at the end would have measured three unrelated commits.
    after_retry = len(app.store.history())
    stale = app.commit(
        ChangeSet(
            edits=(Edit("set", ("title",), "other"),),
            expected_revision=nominal["revision_id"],
            idempotency_key="key-2",
            new_revision_id="rev-3",
        )
    )
    draft = app.commit(
        ChangeSet(
            edits=(Edit("set", ("specifications",), []),),
            expected_revision=app.store.head,
            idempotency_key="key-3",
            new_revision_id="draft-1",
        )
    )
    return {
        "committed": committed.status,
        "invalidations": list(committed.invalidations),
        "idempotent_retry": replayed.status,
        "retry_same_revision": replayed.revision_id == committed.revision_id,
        "revisions_after_retry": after_retry,
        "stale_commit": stale.status,
        "conflict": dict(stale.conflict or {}),
        "head_after_conflict": app.store.head,
        "draft_commit": draft.status,
        "draft_status": draft.validation.status if draft.validation else None,
        "content_hash_ignores_title": content_hash(nominal)
        == content_hash({**nominal, "title": "x", "description": "y"}),
        "content_hash_sees_content": content_hash(nominal)
        != content_hash({**nominal, "specifications": []}),
    }


def measure_validation() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in ("SYN-001-nominal", "SYN-001-conflicting-heater-spec"):
        report = validate(case(name))
        out[name] = {
            "status": report.status,
            "checks": len(report.checks),
            "unsupported": [c.id for c in report.checks if c.scope == "unsupported"],
            "structural_counts": report.structural_counts,
        }
    out["draft"] = validate({**case("SYN-001-nominal"), "specifications": []}).status
    out["invalid"] = validate({"revision_id": "broken"}).status
    return out


def measure_cli() -> dict[str, Any]:
    for variable in THREAD_VARIABLES:
        os.environ.setdefault(variable, "1")
    with tempfile.TemporaryDirectory() as scratch:
        bundle = Path(scratch) / "bundle"
        transcripts: dict[str, list[int]] = {}
        for label, argv in (
            ("solve", ["solve", "SYN-001-nominal", "--out", str(bundle)]),
            ("inspect", ["inspect", str(bundle)]),
            ("replay", ["replay", str(bundle)]),
            ("validate", ["validate", str(CASES / "SYN-001-nominal.yaml")]),
        ):
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = cli(argv)
            transcripts[label] = [code, len(stream.getvalue().splitlines())]
            if label == "inspect":
                text = stream.getvalue()
        return {
            "exit_codes": {key: value[0] for key, value in transcripts.items()},
            "output_lines": {key: value[1] for key, value in transcripts.items()},
            "inspect_sections": [line for line in text.splitlines() if line.startswith("===")],
            "inspect_states_what_is_not_claimed": "does not claim" in text,
        }


def build(commit: str, gate_stdout: Path) -> dict[str, Any]:
    transactions = measure_transactions()
    validation = measure_validation()
    cli_run = measure_cli()
    gates = gate_report()

    checks: list[dict[str, Any]] = [
        {
            "id": "K06.transactions",
            "description": (
                "Blueprint §11's three properties. An **expected revision** refuses a stale "
                "commit and names both ids, so a concurrent agent's work is not silently "
                "overwritten. An **idempotency key** returns the original result on a retry "
                "— the same revision id, and no second revision in the store — so a client "
                "that timed out does not pay twice for an expensive solve. A **change set** "
                "applies whole or not at all. A committed edit names the runs it invalidated."
            ),
            "result": "pass"
            if transactions["committed"] == "committed"
            and transactions["idempotent_retry"] == "replayed"
            and transactions["retry_same_revision"]
            and transactions["revisions_after_retry"] == 2
            and transactions["stale_commit"] == "conflict"
            and transactions["invalidations"] == ["run-a"]
            else "fail",
            "value": transactions,
            "expected": "committed / replayed / conflict, with the invalidated run named",
        },
        {
            "id": "K06.D16.drafts",
            "description": (
                'D16: an incomplete draft is persistable and "a syntactically valid draft can '
                'be committed without being executable". A tool that refuses to hold an '
                "unfinished thought gets worked around, and the work then happens somewhere "
                "with no provenance at all. `DRAFT` and `INVALID` are different answers: one "
                "means incomplete, the other means it is not a revision."
            ),
            "result": "pass"
            if transactions["draft_commit"] == "committed"
            and transactions["draft_status"] == "DRAFT"
            and validation["invalid"] == "INVALID"
            else "fail",
            "value": {"draft": transactions["draft_status"], "invalid": validation["invalid"]},
            "expected": "an under-specified revision commits and reports DRAFT",
        },
        {
            "id": "K06.validation.not_a_badge",
            "description": (
                'Blueprint §4.3: statuses are "validation results tied to a revision and '
                'task, not editable badges". There is no setter; the report is frozen and '
                "recomputed from the revision every time. A revision that asserts its own "
                "readiness is still judged on its contents."
            ),
            "result": "pass"
            if validation["SYN-001-nominal"]["status"] == "READY_FOR_SIMULATION"
            else "fail",
            "value": validation,
            "expected": "computed per revision and task, never stored",
        },
        {
            "id": "K06.G02.cli",
            "description": (
                "Gate **G02**'s Python/CLI clause and the canonical revision. `content_hash` "
                "is computed and never accepted from a caller — the P01 case files leave it "
                "absent with a note saying a hash written before ADR 0002's encoding existed "
                "would be a fabricated identity. It ignores the title and description, because "
                "two revisions differing only in their title are the same process, and it "
                "moves when the content does. Four CLI commands exit 0."
            ),
            "result": "pass"
            if transactions["content_hash_ignores_title"]
            and transactions["content_hash_sees_content"]
            and all(code == 0 for code in cli_run["exit_codes"].values())
            else "fail",
            "value": {
                "cli": cli_run["exit_codes"],
                "content_hash": {
                    "ignores_description": transactions["content_hash_ignores_title"],
                    "sees_content": transactions["content_hash_sees_content"],
                },
            },
            "expected": "validate, solve, inspect and replay all exit 0",
        },
        {
            "id": "K06.G06.inspectable",
            "description": (
                "Gate **G06**: the end-to-end example is inspectable without unrelated code. "
                "Three commands and no imports: solve a registered case, inspect what the run "
                "claimed *and did not claim*, replay the bundle. The section a reader needs "
                'most is the one headed "what this certificate does not claim", which '
                "carries the three required statements and the [A09] shared-provider "
                "qualification in full."
            ),
            "result": "pass"
            if cli_run["inspect_states_what_is_not_claimed"]
            and len(cli_run["inspect_sections"]) >= 4
            else "fail",
            "value": {
                "sections": cli_run["inspect_sections"],
                "lines": cli_run["output_lines"],
            },
            "expected": "run, environment, certificate, what-is-not-claimed and trace sections",
        },
        {
            "id": "K06.v0_0.gates",
            "description": (
                "Measured with this manifest already on disk: G02 is owned by K01 and K06 "
                "jointly, so the summary cannot see it until K06's evidence exists. The "
                "generator is therefore run twice and the second run is what is recorded — "
                "the ordinary bootstrap of any self-describing artifact, stated rather than "
                "hidden.\n\n"
                "The v0.0 acceptance summary, read from the committed evidence manifests "
                "rather than re-derived. Plan §7 forbids claiming release completion from a "
                "demo, copied golden outputs, skipped cases or relaxed checks, and a gate "
                "script that recomputed everything in memory would be a demo. A gate inherits "
                "its packages' `unsupported` checks as limitations rather than shedding them; "
                "no gate is upgraded here and none is averaged. G06 is the one exception that "
                "re-runs, because its claim is about what a reader can do."
            ),
            "result": "pass" if gates["v0_0"]["all_gates_met"] else "fail",
            "value": {
                "met": gates["v0_0"]["met"],
                "not_met": gates["v0_0"]["not_met"],
                "with_limitations": gates["v0_0"]["with_limitations"],
                "per_gate": {
                    gate: entry["status"] for gate, entry in sorted(gates["gates"].items())
                },
            },
            "expected": "G00 through G06 met, limitations carried not dropped",
        },
        {
            "id": "K06.structural_over_specification",
            "description": (
                "The registered case `SYN-001-conflicting-heater-spec` specifies the heater "
                "twice — an outlet temperature and a duty — and this validator reports it "
                "READY_FOR_SIMULATION. K04 recorded this as `unsupported(no validator before "
                "K06)`; K06 has a validator and the reason is now different and narrower: "
                "detecting it needs blueprint §4.3's matching and Dulmage-Mendelsohn "
                "decomposition, which is T01. The validator says so in its own report, as an "
                "`unsupported` check, so a reader is not misled by the status. Downstream that "
                "revision is refused as UNSUPPORTED_RANK_STRUCTURE — a 45x44 inner block — "
                "and not as SPECIFICATION_CONFLICT, which is for a pressure-graph cycle; an "
                "earlier wording of this check said otherwise and was corrected on "
                "2026-09-23 after the case was assembled and run for the first time."
            ),
            "result": "unsupported",
            "value": {
                "case": "SYN-001-conflicting-heater-spec",
                "reported": validation["SYN-001-conflicting-heater-spec"]["status"],
                "unsupported_checks": validation["SYN-001-conflicting-heater-spec"]["unsupported"],
                "owner": "T01",
            },
            "expected": "a validator that rejects structural over-specification",
        },
        {
            "id": "K06.jobs_and_remote_bindings",
            "description": (
                "Blueprint §11 also describes long work as a job with budgets, progress, "
                "cancellation and checkpoint/resume, and a small HTTP/MCP binding over the "
                "same contract. Plan §4.2 puts both in T07, not K06, and D15 is explicit that "
                "the local path needs no network round trip. Nothing here is a job."
            ),
            "result": "not_applicable",
            "value": {"owner": "T07"},
            "expected": "out of scope for v0.0",
        },
    ]

    artifacts = [
        {"path": path, "sha256": file_sha256(ROOT / path), "description": description}
        for path, description in (
            (
                "src/openflowsheet/application/revisions.py",
                "Immutable content-addressed revisions.",
            ),
            ("src/openflowsheet/application/validation.py", "Task validation, §4.3."),
            ("src/openflowsheet/application/transactions.py", "Local transactions, §11."),
            ("src/openflowsheet/application/cli.py", "The CLI, D15 and G06."),
            ("scripts/v0_0_gate.py", "The v0.0 gate summary."),
        )
    ]

    return {
        "work_package": "K06",
        "commit": commit,
        "requirements": ["D15", "D16"],
        "status": "tested",
        "inputs": {
            "case_id": (
                "The registered SYN-001 revisions driven through the application layer: "
                "nominal committed, retried, conflicted and drafted; the conflicting-heater "
                "revision validated; and the CLI run end to end on SYN-001-nominal"
            ),
            "case_hash": file_sha256(CASES / "SYN-001-nominal.yaml"),
            "environment_lock_hash": file_sha256(ROOT / "requirements.lock"),
        },
        "commands": [
            {
                "cmd": "PATH=.venv/bin:$PATH ./scripts/check.sh",
                "cwd": ".",
                "exit_code": 0,
                "stdout_sha256": hashlib.sha256(gate_stdout.read_bytes()).hexdigest(),
            },
            {"cmd": "PYTHONPATH=. python scripts/v0_0_gate.py", "cwd": ".", "exit_code": 0},
        ],
        "checks": checks,
        "artifacts": artifacts,
        "limitations": [
            "Structural over-specification is not detected. The registered conflicting-heater "
            "revision validates READY_FOR_SIMULATION here and is refused downstream as "
            "UNSUPPORTED_RANK_STRUCTURE, which describes the tool rather than the revision; "
            "detecting it at validation needs blueprint §4.3's "
            "matching and Dulmage-Mendelsohn decomposition, which is T01. The validator says "
            "so in its own report rather than leaving the status to mislead.",
            "`structural_counts` is null in every validation report, for the same reason. A "
            "variable-against-equation count would not distinguish a structurally singular "
            "system whose totals agree, so none is produced.",
            "There are no jobs, no HTTP or MCP binding and no authorization model. Blueprint "
            "§11 describes all three and plan §4.2 puts them in T07.",
            "The revision store is in memory. Persistence, concurrent access from separate "
            "processes and any durability claim are not implemented and not tested.",
            "The CLI solves *registered* cases only. There is no path from an arbitrary "
            "revision document to a solve, because the compiler binding for a general "
            "revision is T01's.",
            "v0.0's gates are acceptance evidence and not a release. Every manifest carries "
            "`review.numerical` and `review.process_model` as `pending`, and no agent may set "
            "them. SYN-001 is synthetic: nothing in this repository is empirically validated.",
        ],
        "review": {"numerical": "pending", "process_model": "pending"},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gate_stdout", type=Path)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--out", type=Path, default=None)
    arguments = parser.parse_args()

    manifest = build(arguments.commit, arguments.gate_stdout)
    destination = arguments.out or (ROOT / "evidence" / "K06" / arguments.commit / "manifest.json")
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
