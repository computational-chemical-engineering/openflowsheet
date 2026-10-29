"""Dump what E01.A3 and A35 compare between two trees. E01 (WO-I1, design §6.1 A3, A35; G9).

Run in the audited NLP environment (`docs/m03-ipopt-audit.md`, `OMP_NUM_THREADS=1`) with the
tree's `src` first on `PYTHONPATH`; `ROOT` is the tree whose `tests` and `scripts` are imported, so
the same file dumps the base tree and this one. It writes one JSON object, keys sorted:

- every M03 NLP fixture document (`m03_schema_fixtures.nlp_documents()`, no assessment named),
  serialized as the fixture generator serializes it, with each `wall_time_s` blanked — the one
  member no two runs share (that module's docstring);
- `components`: the Pyomo model's component list (name, type) for NLP-1's first start, built with
  no assessment (A35's "equals that of `main`");
- `objective`: that model's objective expression.

`scripts/e01_evidence_manifest.py` runs it in a detached worktree of the base and in this tree and
compares the two files byte for byte.

Usage:
    OMP_NUM_THREADS=1 PYTHONNOUSERSITE=1 PYOMO_CONFIG_DIR=<env>/share/pyomo \\
        PYTHONPATH=<ROOT>/src:<nlp-test-tools> <env>/bin/python scripts/e01_m03_dump.py ROOT OUT
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def blank(document: Any) -> Any:
    """`document` with every `wall_time_s` value replaced by `None`."""
    if isinstance(document, dict):
        return {
            key: (None if key == "wall_time_s" else blank(value)) for key, value in document.items()
        }
    if isinstance(document, list):
        return [blank(value) for value in document]
    return document


def main() -> int:
    root, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2])
    sys.path[:0] = [str(root / "tests"), str(root / "scripts")]
    import m03_schema_fixtures
    from m03_support import flowsheet, nlp_formulation

    from openflowsheet.studies.nlp import greybox
    from openflowsheet.studies.nlp.closure import optimization_readiness
    from openflowsheet.studies.nlp.formulation import FullSpaceNlp
    from openflowsheet.studies.syn001 import with_pinned

    serialize = m03_schema_fixtures.serialize
    dumped = {
        name: serialize(blank(json.loads(serialize(document))))
        for name, document in m03_schema_fixtures.nlp_documents().items()
    }
    formulation, sheet = nlp_formulation(), flowsheet({})
    start = optimization_readiness(formulation, sheet).starts[0]
    nlp = FullSpaceNlp(
        with_pinned(sheet, formulation.decision_values(start.start)),
        formulation,
        start.state,
        start.start,
    )
    model = greybox.build_model(nlp, greybox.FullSpaceGreyBox(nlp))
    components = [(c.name, type(c).__name__) for c in model.component_objects(descend_into=True)]
    dumped["components"] = json.dumps(components)
    dumped["objective"] = str(model.objective.expr)
    out.write_text(json.dumps(dumped, sort_keys=True, indent=0), encoding="utf-8")
    print(f"dumped {len(dumped)} entries; components {len(components)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
