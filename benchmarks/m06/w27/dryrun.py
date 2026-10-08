"""W27's dry run: G14 and G15 with a stub session, no model call, nothing spent (M06 WO-16g).

Normative text: design note §11 G14 ("every case classified") and G15 ("preflight passes;
`run.json` carries commit, tree-clean, lock hash, interpreter environment, model id, Claude Code
version; scorer classifies the stub runs as registered"); registration §14.3. In order, at the
committed checkout:

1. `coverage.json` for this build (snapshot rebuilt at HEAD) and G14 on it;
2. `sample.json`, the registered draw from it;
3. three canaries — stub sessions through the production harness, as WO-17's real ones will be;
4. the preflight P1–P8 against that campaign directory (P1 cannot pass until Frank approves the
   spend; it is reported, not bypassed);
5. the eighteen scorer states (`stubs.run_states`) and G15's judgement of them;
6. W27-A23 on every harness run's `run.json`.

Everything is written under `--out` (git-ignored `evidence/**/artifacts/`); `summary.json` holds
the verdicts. Run:
`python -m benchmarks.m06.w27.dryrun --out evidence/M06/W27/artifacts/dry-run/<commit>`.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from benchmarks.m06.w27 import coverage as classifier
from benchmarks.m06.w27 import facts, harness, preflight, registration, sample, snapshot, stubs

CAMPAIGN = "dry-run"


def run(out: Path) -> dict[str, Any]:
    if out.exists():
        raise harness.HarnessError(f"{out} exists; a dry run is never repeated in place")
    inputs = out / "inputs"
    inputs.mkdir(parents=True)
    coverage = classifier.coverage_document(facts.load_facts(), snapshot.build_snapshot())
    coverage_path = inputs / "coverage.json"
    coverage_path.write_bytes(registration.dump(coverage))
    data = coverage_path.read_bytes()
    drawn = sample.sample_document(json.loads(data), data)
    sample_path = inputs / "sample.json"
    sample_path.write_bytes(registration.dump(drawn))

    canary = stubs.State("canary", "", "", text="Stub canary: no model, no answer.")
    config = harness.agent_config(
        stubs.STUB_MODEL, claude=str(stubs.write_fake_claude(out / "bin", canary))
    )
    runs_root = out / "runs"
    canaries = harness.canaries(
        CAMPAIGN,
        drawn,
        work=out / "work",
        config=config,
        coverage_path=coverage_path,
        runs_root=runs_root,
        operator=stubs.stub_operator(out),
        run_one=lambda *a, **k: harness.run(
            *a, **k, environment={"HOME": str(out / "home"), "PATH": "/usr/bin:/bin"}
        ),
    )
    context = preflight.Campaign(
        name=CAMPAIGN,
        runs_root=runs_root,
        coverage_path=coverage_path,
        sample_path=sample_path,
        model=stubs.STUB_MODEL,
        claude_code_version=stubs.STUB_VERSION,
    )
    checks = preflight.run_all(context)
    results = stubs.run_states(out / "states")
    g15 = stubs.g15(results)
    records = {
        k: json.loads((Path(v["run_dir"]) / "run.json").read_bytes())
        for k, v in results.items()
        if v["scores"]["case_class"] != "CANDIDATE"
    }
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
        "preflight": checks,
        "preflight_passed_except_p1": all(v["passed"] for k, v in checks.items() if k != "P1"),
        "g15_states": g15,
        "a23": a23,
        "a23_passed": bool(a23) and all(v["passed"] for v in a23.values()),
    }
    (out / "summary.json").write_bytes(registration.dump(summary))
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="W27 dry run (G14, G15), no model call")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    summary = run(args.out)
    print(f"commit {summary['commit']}")
    print(f"G14 {'PASS' if summary['g14']['passed'] else 'FAIL'}: {summary['coverage']}")
    for name, verdict in summary["preflight"].items():
        print(f"{name} {'PASS' if verdict['passed'] else 'FAIL'}")
    for state, verdict in summary["g15_states"]["states"].items():
        print(f"{state} {'PASS' if verdict['passed'] else 'FAIL'} {verdict['outcome']}")
    print(f"G15 states {'PASS' if summary['g15_states']['passed'] else 'FAIL'}")
    print(f"A23 {'PASS' if summary['a23_passed'] else 'FAIL'}")
    ok = (
        summary["g14"]["passed"]
        and summary["g15_states"]["passed"]
        and summary["a23_passed"]
        and summary["preflight_passed_except_p1"]
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
