"""T06 W8: this project's side of the reference comparisons (spec §9.2, §9.5 rule 3, A47).

Solves each fixture's revision, certifies it, and writes one record per fixture to
`benchmarks/t06/references/results/ours-<fixture>.json`: the outcome, the certificate's verdict,
its non-passing checks and limitations, the certified state, and the compared quantities (spec
§9.2, by `t06_fixtures.COMPARED`'s names). The comparison (`scripts/t06_reference_comparison.py`)
reads these records, never this module; the gate test (`tests/test_t06_w8_references.py`) solves
again live and checks that the committed record is what a solve produces today.

Which solve is ours, per fixture (spec §9.2; §3.2's NET-01 and A1.7):

* REF-01 … REF-07 and PC-2 — their revisions `benchmarks/t06/cases/SYN-001-T06-REF0k.yaml` and
  `SYN-001-T06-PC2.yaml` on the revision path (`bind_revision_flowsheet` → `plan_revision` →
  `execute_plan` → `verify_revision`) under `T06-revision-v2`, the policy the spec runs the
  revision path under (A1.7);
* REF-08 — SYN-001-nominal itself (`benchmarks/syn001/cases/SYN-001-nominal.yaml`) on the tear
  path (`solve_tear` under `SYN-001-K03` → `verify`), NET-01's registered solve;
* PC-1 is REF-04 with DWSIM's unmapped latent heat, so its "ours" is REF-04's record (no file).

Usage (from the repository root):
    PYTHONPATH=src:. .venv/bin/python scripts/t06_references_ours.py [--out DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "spikes" / "references"))

import t06_fixtures as fx  # noqa: E402
from t06_support import T06_REVISION_POLICY  # noqa: E402

from openflowsheet.application.binding import Binding, bind_revision_or_reason  # noqa: E402
from openflowsheet.application.revision_binding import (  # noqa: E402
    RevisionBinding,
    bind_revision_flowsheet,
)
from openflowsheet.orchestrator.execution import ExecutionPlan  # noqa: E402
from openflowsheet.orchestrator.executor import execute_plan  # noqa: E402
from openflowsheet.orchestrator.revision import plan_revision  # noqa: E402
from openflowsheet.orchestrator.tear import solve_tear  # noqa: E402
from openflowsheet.verify.certificate import (  # noqa: E402
    SolutionCertificate,
    verify,
    verify_revision,
)

RESULTS = ROOT / "benchmarks" / "t06" / "references" / "results"

#: Our revision per fixture with a record of its own, and the path it is solved on.
SOURCES: dict[str, tuple[str, str]] = {
    **{
        f"REF-0{k}": (f"benchmarks/t06/cases/SYN-001-T06-REF0{k}.yaml", "revision")
        for k in range(1, 8)
    },
    "REF-08": ("benchmarks/syn001/cases/SYN-001-nominal.yaml", "tear"),
    "PC-2": ("benchmarks/t06/cases/SYN-001-T06-PC2.yaml", "revision"),
}


def _certificate_summary(certificate: SolutionCertificate) -> dict[str, Any]:
    """What the comparison reads from the certificate, as fields of their own (spec §9.6 (A5)):
    the verdict, the non-passing checks and the limitations. No certificate hash: A50 compares
    every field across machines, and a certificate's roundoff-level floats are not a cross-machine
    promise (ADR 0007); REF-01…07's certificate R0 is checked by K05's `t06` key (A45)."""
    return {
        "verification_status": certificate.verification_status,
        "check_policy_id": certificate.check_policy_id,
        "non_passing_checks": sorted(
            f"{c.id}: {c.result}"
            for c in certificate.checks
            if c.result not in ("pass", "not_applicable")
        ),
        "limitations": [str(entry) for entry in certificate.limitations],
    }


def solve(fixture: str) -> dict[str, Any]:
    """Our record for `fixture` (a key of `SOURCES`): solve, certify, read the compared values."""
    relative, path = SOURCES[fixture]
    source = ROOT / relative
    document: dict[str, Any] = yaml.safe_load(source.read_text(encoding="utf-8"))
    record: dict[str, Any] = {
        "fixture": fixture,
        "side": "ours",
        "revision": relative,
        "revision_id": document["revision_id"],
        "revision_file_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "path": path,
    }
    state: dict[str, float] | None = None
    if path == "tear":
        binding = bind_revision_or_reason(document)
        if not isinstance(binding, Binding):
            return {**record, "outcome": f"UNBOUND: {binding}"}
        result, _ = solve_tear(binding.flowsheet)
        record["policy_id"] = "SYN-001-K03"
        record["outcome"] = result.outcome
        if result.outcome == "CONVERGED":
            record.update(_certificate_summary(verify(binding.flowsheet, result)))
            state = dict(result.final_state)
    else:
        revision = bind_revision_flowsheet(document)
        if not isinstance(revision, RevisionBinding):
            return {**record, "outcome": f"UNBOUND: {revision}"}
        policy = T06_REVISION_POLICY
        record["policy_id"] = policy.policy_id
        plan, _ = plan_revision(revision, policy)
        if not isinstance(plan, ExecutionPlan):
            return {**record, "outcome": f"PLAN_REFUSED: {plan}"}
        run = execute_plan(
            plan=plan, flowsheet=revision.flowsheet, spec=revision.spec, policy=policy
        )
        record["outcome"] = run.outcome
        if run.outcome == "CONVERGED":
            certificate = verify_revision(
                revision, document, run, solve_plan=plan.steps[-1].solve_plan
            )
            record.update(_certificate_summary(certificate))
            state = dict(run.steps[-1].detail.state)
    if state is not None:
        record["state"] = {key: float(value) for key, value in sorted(state.items())}
        record["compared_quantities"] = {q: float(state[q]) for q in fx.COMPARED[fixture]}
    return record


def write(record: dict[str, Any], out: Path) -> Path:
    path = out / f"ours-{record['fixture']}.json"
    path.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=RESULTS)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    status = 0
    for fixture in SOURCES:
        record = solve(fixture)
        path = write(record, args.out)
        verdict = record.get("verification_status")
        status |= 0 if verdict == "VERIFIED" else 1
        print(f"ours {fixture}: {record['outcome']} {verdict} -> {path.name}")
    return status


if __name__ == "__main__":
    sys.exit(main())
