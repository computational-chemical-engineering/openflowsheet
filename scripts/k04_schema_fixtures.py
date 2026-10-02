"""Generate the K04 round-trip fixtures from real verifier runs. Register R-015.

Every fixture here is emitted by an actual `verify()` or `bundle_for()` call. The rule exists
because K03 shipped six fixtures of which four were hand-assembled and only two regenerated,
and regenerating the other four found one internally impossible — it named a converged
checkpoint as the state a restart opened *from*. A hand-made fixture tests the author's
reading of the schema; an emitted one tests the code.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/k04_schema_fixtures.py [--write]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from k03_schema_fixtures import CONTEXT, POLICY, flowsheet  # noqa: E402

from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet  # noqa: E402
from openflowsheet.orchestrator.tear import solve_tear  # noqa: E402
from openflowsheet.orchestrator.trace import SolvePolicy  # noqa: E402
from openflowsheet.thermo.syn001 import Syn001Provider  # noqa: E402
from openflowsheet.verify.certificate import verify  # noqa: E402
from openflowsheet.verify.failure import bundle_for  # noqa: E402

FIXTURE_DIR = ROOT / "tests" / "fixtures" / "schemas"

#: §9.2's registered offset.
TRIVIAL_ROOT_OFFSET = 8237.8503930694530451


def once_through() -> Syn001Flowsheet:
    return Syn001Flowsheet(provider=Syn001Provider(), context=CONTEXT, split_fraction=0.0)


def documents() -> dict[str, Any]:
    """Every K04 fixture, keyed by its path under `tests/fixtures/schemas/`."""
    nominal_sheet = flowsheet()
    nominal, _ = solve_tear(nominal_sheet, policy=POLICY)
    verified = verify(nominal_sheet, nominal)
    if verified.verification_status != "VERIFIED":
        raise SystemExit(f"the nominal solve verified as {verified.verification_status}")

    # The trivial root: every assembled row satisfied, both duties wrong by 8237.85 W.
    sheet = once_through()
    solved, _ = solve_tear(sheet, policy=POLICY)
    spurious = dict(solved.final_state or {})
    for component in ("A", "B", "C"):
        spurious[f"S3.liq.{component}"] = spurious[f"S3.n.{component}"]
        spurious[f"S3.vap.{component}"] = 0.0
    spurious["S3.L"] = sum(spurious[f"S3.n.{c}"] for c in ("A", "B", "C"))
    spurious["S3.V"] = 0.0
    spurious["U-HEAT.Q"] -= TRIVIAL_ROOT_OFFSET
    spurious["U-FLASH.Q"] += TRIVIAL_ROOT_OFFSET
    rejected = verify(sheet, solved, state=spurious)
    if rejected.verification_status != "FAILED" or not rejected.false_success_detected:
        raise SystemExit("the trivial root was not rejected as a false success")

    capped = SolvePolicy(
        policy_id="SYN-001-capped", residual_tolerances={}, scales={}, max_property_calls=20
    )
    exhausted, trace = solve_tear(flowsheet(), policy=capped)
    bundle = bundle_for(exhausted, trace)

    return {
        "solution_certificate/valid/syn001_nominal_verified.json": verified.as_document(),
        "solution_certificate/valid/syn001_trivial_root_failed.json": rejected.as_document(),
        "regularity_evidence/valid/syn001_nominal.json": verified.regularity.as_document(),
        "failure_bundle/valid/syn001_capped_budget.json": bundle.as_document(),
    }


def serialize(document: Any) -> str:
    return json.dumps(document, indent=1, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()

    differing = []
    for name, document in documents().items():
        path = FIXTURE_DIR / name
        text = serialize(document)
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            differing.append(name)
            if arguments.write:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
    if not differing:
        print("all K04 fixtures match what the code emits")
        return 0
    print(
        f"{'rewrote' if arguments.write else 'differ (rerun with --write)'}: {', '.join(differing)}"
    )
    return 0 if arguments.write else 1


if __name__ == "__main__":
    raise SystemExit(main())
