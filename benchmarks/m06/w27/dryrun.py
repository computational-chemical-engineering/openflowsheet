"""W27's dry run: G14 and G15 with a stub session, no model call, nothing spent (M06 WO-16g).

Normative text: design note §11 G14 ("every case classified") and G15 ("preflight passes;
`run.json` carries commit, tree-clean, lock hash, interpreter environment, model id, Claude Code
version; scorer classifies the stub runs as registered"); registration §14.3, and §23's order
(Amendment 4, WO-17a item 7). In order, at the committed, clean checkout, under
`runs/<campaign>/`:

1. `coverage.json` for this build (snapshot rebuilt at HEAD) and G14 on it;
2. `sample.json`, the registered draw from it;
3. `confirmation/confirmation.json` (`harness.confirm`, W27-R66);
4. the canaries (`harness.canaries`, W27-R68): stub sessions through the production harness, as
   WO-17's real ones will be, attempt 01 without `--model` and pinning the stub's default;
5. the standalone preflight P1–P8, which writes nothing; then the stub campaign
   (`harness.campaign`): P1–P8 again, `preflight.json` (W27-R67) and the 45 runs, then
   `campaign.json`;
6. `harness.order_check` on the campaign directory (M07.A50, W27-A78);
7. the twenty scorer states (`stubs.run_states`; S19, S20 by Amendment 2) and G15's judgement;
8. W27-A23 (restated, registration §23.12) on every scorer-state harness run's `run.json` and on
   every `run.json` under the campaign directory, the canary attempts' included.

Everything is written under `--out`, outside the tree or git-ignored (P8 needs a clean tree);
`summary.json` holds the verdicts. Run:
`python -m benchmarks.m06.w27.dryrun --out <directory>`.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from benchmarks.m06.w27 import coverage as classifier
from benchmarks.m06.w27 import facts, harness, preflight, registration, sample, snapshot, stubs

CAMPAIGN = "dry-run"
#: The stand-in `claude` of the canary attempts: a session with the stub's model and no answer.
CANARY = stubs.State("canary", "", "", text="Stub canary: no model, no answer.")


def run(out: Path, work: Path) -> dict[str, Any]:
    """The dry run into `out`; sessions run in `work`, outside the repository (V17 §14.1)."""
    out, work = out.resolve(), work.resolve()
    if out.exists():
        raise harness.HarnessError(f"{out} exists; a dry run is never repeated in place")
    runs_root = out / "runs"
    directory = runs_root / CAMPAIGN
    directory.mkdir(parents=True)
    coverage = classifier.coverage_document(facts.load_facts(), snapshot.build_snapshot())
    coverage_path = directory / "coverage.json"
    coverage_path.write_bytes(registration.dump(coverage))
    data = coverage_path.read_bytes()
    drawn = sample.sample_document(json.loads(data), data)
    sample_path = directory / "sample.json"
    sample_path.write_bytes(registration.dump(drawn))
    harness.confirm(CAMPAIGN, runs_root=runs_root)

    claude = str(stubs.write_fake_claude(out / "bin", CANARY))
    operator = stubs.stub_operator(out)
    environment = {"HOME": str(out / "home"), "PATH": "/usr/bin:/bin"}

    def run_one(*arguments: Any, **keywords: Any) -> Path:
        return harness.run(*arguments, **keywords, environment=environment)

    canaries = harness.canaries(
        CAMPAIGN,
        work=work / "canaries",
        claude=claude,
        runs_root=runs_root,
        operator=operator,
        run_one=run_one,
    )
    pin = harness.model_pin(harness.canary_attempts(directory))
    context = preflight.Campaign(
        name=CAMPAIGN,
        runs_root=runs_root,
        coverage_path=coverage_path,
        sample_path=sample_path,
        model=str(pin),
        claude_code_version=stubs.STUB_VERSION,
    )
    checks = preflight.run_all(context)
    standalone_wrote = (directory / harness.PREFLIGHT_FILE).exists()
    campaign_error = None
    try:
        harness.campaign(
            CAMPAIGN,
            work=work / "campaign",
            config=harness.agent_config(pin, claude=claude),
            claude_code_version=stubs.STUB_VERSION,
            coverage_path=coverage_path,
            sample_path=sample_path,
            runs_root=runs_root,
            operator=operator,
            preflight=lambda: preflight.require(context),
            run_one=run_one,
        )
    except harness.HarnessError as error:
        campaign_error = f"{type(error).__name__}: {error}"
    record_path = directory / harness.PREFLIGHT_FILE
    record = json.loads(record_path.read_bytes()) if record_path.is_file() else None
    members = sorted(harness.campaign_records()["preflight"]["members"])
    order = harness.order_check(directory)
    runs = sorted(p for p in directory.iterdir() if p.is_dir() and p.name[:2].isdigit())
    results = stubs.run_states(out / "states", work=work / "states")
    g15 = stubs.g15(results)
    records = {
        k: json.loads((Path(v["run_dir"]) / "run.json").read_bytes())
        for k, v in results.items()
        if v["scores"]["case_class"] != "CANDIDATE"
    }
    records.update(
        {
            str(p.parent.relative_to(directory)): json.loads(p.read_bytes())
            for p in directory.glob("**/run.json")
        }
    )
    a23 = {k: harness.a23(r) for k, r in sorted(records.items())}
    summary = {
        "commit": coverage["snapshot"]["git_commit"],
        "g14": classifier.g14(coverage),
        "coverage": {
            "snapshot_sha256": coverage["snapshot_sha256"],
            "list_models_sha256": coverage["list_models_sha256"],
            "all_450": coverage["summary"]["all_450"]["classes"],
            "full82": coverage["summary"]["full82"]["classes"],
        },
        "sample": {"cases": len(drawn["cases"]), "canaries": drawn["canaries"]},
        "canaries": canaries,
        "pin": pin,
        "preflight": checks,
        "preflight_passed": all(v["passed"] for v in checks.values()),
        "standalone_preflight_wrote_nothing": not standalone_wrote,
        "campaign_error": campaign_error,
        "campaign_runs": len(runs),
        "campaign_json": (directory / "campaign.json").is_file(),
        "preflight_record": {
            "written": record is not None,
            "members_as_registered": record is not None and sorted(record) == members,
            "passed": record is not None and record["passed"] is True,
        },
        "order_check": order,
        "g15_states": g15,
        "a23": a23,
        "a23_passed": bool(a23) and all(v["passed"] for v in a23.values()),
    }
    (out / "summary.json").write_bytes(registration.dump(summary))
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="W27 dry run (G14, G15), no model call")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--work", type=Path, help="session work directory (default: a temp dir)")
    args = parser.parse_args(argv)
    work = args.work or Path(tempfile.mkdtemp(prefix="w27-dry-run-"))
    summary = run(args.out, work)
    print(f"commit {summary['commit']}")
    print(f"G14 {'PASS' if summary['g14']['passed'] else 'FAIL'}: {summary['coverage']}")
    for name, verdict in summary["preflight"].items():
        print(f"{name} {'PASS' if verdict['passed'] else 'FAIL'}")
    record = summary["preflight_record"]
    print(f"preflight.json {'PASS' if all(record.values()) else 'FAIL'}: {record}")
    print(f"campaign runs {summary['campaign_runs']} error {summary['campaign_error']}")
    order = summary["order_check"]
    print(f"order_check {'PASS' if order['passed'] else 'FAIL'}: {order['problems'][:5]}")
    for state, verdict in summary["g15_states"]["states"].items():
        print(f"{state} {'PASS' if verdict['passed'] else 'FAIL'} {verdict['outcome']}")
    print(f"G15 states {'PASS' if summary['g15_states']['passed'] else 'FAIL'}")
    print(f"A23 {'PASS' if summary['a23_passed'] else 'FAIL'} ({len(summary['a23'])} records)")
    ok = (
        summary["g14"]["passed"]
        and summary["g15_states"]["passed"]
        and summary["a23_passed"]
        and summary["preflight_passed"]
        and summary["standalone_preflight_wrote_nothing"]
        and summary["campaign_error"] is None
        and summary["campaign_json"]
        and all(record.values())
        and order["passed"]
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
