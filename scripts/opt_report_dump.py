"""Dump OPT's analytic-case reports for a byte comparison of two trees (OPT design §9.5 G23 (c)).

Runs `optimize_revision` on OPT-A1, A2, A2b, A3, C0 and N1 (`benchmarks/opt/requests`, the
flowsheets `benchmarks/opt/expected.json` names) with a record directory, and writes one JSON object
`{case: report}` with every `wall_time_s` blanked — the one member no two runs share (G2's mask,
`scripts/opt_m03_dump.py`). Run once with the base tree's `src` first on `PYTHONPATH` and once with
the changed tree's, then `cmp` the two files. Audited NLP environment only (`OMP_NUM_THREADS=1`).

Usage:
    PYTHONPATH=<TREE>/src:<nlp-test-tools> OMP_NUM_THREADS=1 <nlp python> \\
        scripts/opt_report_dump.py OUT [CASE ...]
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

OPT = Path(__file__).resolve().parents[1] / "benchmarks" / "opt"
CASES = ("OPT-A1", "OPT-A2", "OPT-A2b", "OPT-A3", "OPT-C0", "OPT-N1")


def blank(document: Any) -> Any:
    """`document` with every `wall_time_s` value replaced by `None`."""
    if isinstance(document, dict):
        return {
            key: (None if key == "wall_time_s" else blank(value)) for key, value in document.items()
        }
    if isinstance(document, list):
        return [blank(value) for value in document]
    return document


def report(case: str, directory: Path) -> Any:
    from openflowsheet.application.policies import DEFAULT_POLICY_ID, resolve_policy
    from openflowsheet.studies.nlp.revision import optimize_revision
    from openflowsheet.verify.certificate import CheckPolicy

    expected = json.loads((OPT / "expected.json").read_bytes())
    flowsheet = expected["flowsheets"][case]
    document = json.loads((OPT / "flowsheets" / f"{flowsheet}.json").read_bytes())
    request = json.loads((OPT / "requests" / f"{case}.json").read_bytes())
    policy = resolve_policy(DEFAULT_POLICY_ID, "revision_eo")
    assert policy is not None
    outcome = optimize_revision(
        document,
        request,
        directory=directory / case,
        solve_policy=policy,
        check_policy=CheckPolicy(),
    )
    return blank(outcome.report.as_document())


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    out, cases = Path(argv[0]), tuple(argv[1:]) or CASES
    with tempfile.TemporaryDirectory() as scratch:
        dumped = {case: report(case, Path(scratch)) for case in cases}
    out.write_text(json.dumps(dumped, indent=1, sort_keys=True) + "\n")
    print(f"wrote {out}: {', '.join(cases)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
