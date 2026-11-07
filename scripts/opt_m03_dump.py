"""Dump what OPT's gate G2 compares between two trees (OPT design §6 G2, §2.3; WO-1, WO-4, WO-5).

M03's SYN-001 path and E01's assessment-bound path through it, as documents and exact bytes, so
that a structural change (the NLP host, WO-1) is *measured* inert: run once in the base tree and
once in the changed tree, then `cmp` the two files. It writes one JSON object, keys sorted, every
float by `repr` (round-trips exactly) and every array as the hex of its float64 bytes:

- `readiness/<problem>`: `optimization_readiness` of NLP-1, NLP-INF and the E01 TAC binding, with
  the solver probe a test double (so the default install reaches every start);
- `verify/a32`: `verify_candidate` at NLP-1's reference optimum (M03 A32); `verify/<problem>/<k>`
  at every readiness start, with the start's state as the optimizer's (V2 evaluated);
- `unsupported/<problem>`: `optimize()` with an unavailable solver probe (the typed report);
- `full_space/<problem>`: `FullSpaceNlp` at start 0 built as the M03 and E01 tests build it — its
  document, initial point, bounds, scalings, equality residual and Jacobian, outputs and their
  Jacobian, at the start and at a perturbed point;
- with `--nlp` (the audited NLP environment, `OMP_NUM_THREADS=1`): `report/<problem>` — the solved
  `OptimizationReport` of NLP-1, NLP-INF and the E01 TAC binding with every `wall_time_s` blanked,
  the one member no two runs share (`scripts/e01_m03_dump.py`).

Usage (ROOT is the tree whose `tests` are imported; its `src` must be first on `PYTHONPATH`):
    PYTHONPATH=<ROOT>/src python scripts/opt_m03_dump.py ROOT OUT [--nlp]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np


def blank(document: Any) -> Any:
    """`document` with every `wall_time_s` value replaced by `None`."""
    if isinstance(document, dict):
        return {
            key: (None if key == "wall_time_s" else blank(value)) for key, value in document.items()
        }
    if isinstance(document, list):
        return [blank(value) for value in document]
    return document


def exact(value: Any) -> Any:
    """`value` as JSON with exact floats: arrays as the hex of their float64 bytes."""
    if isinstance(value, np.ndarray):
        return {"shape": list(value.shape), "hex": np.ascontiguousarray(value).tobytes().hex()}
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, dict):
        return {str(key): exact(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [exact(item) for item in value]
    return value


def matrix(value: Any) -> dict[str, Any]:
    csc = value.tocsc()
    return {
        "shape": list(csc.shape),
        "data": exact(np.asarray(csc.data, dtype=np.float64)),
        "indices": csc.indices.tolist(),
        "indptr": csc.indptr.tolist(),
    }


def full_space(nlp: Any) -> dict[str, Any]:
    z = nlp.initial_point()
    moved = z * (1.0 + 1e-6)
    out = {
        "document": exact(nlp.as_document()),
        "initial_point": exact(z),
        "bounds": exact(list(nlp.bound_arrays())),
        "primal_scaling": exact(nlp.primal_scaling()),
        "equality_scaling": exact(nlp.equality_scaling()),
        "output_ids": list(nlp.output_ids),
        "output_scaling": exact(nlp.output_scaling()),
    }
    for name, point in (("start", z), ("moved", moved)):
        out[f"residual/{name}"] = exact(nlp.equality_residual(point))
        out[f"jacobian/{name}"] = matrix(nlp.equality_jacobian(point))
        if nlp.output_ids:
            out[f"outputs/{name}"] = exact(nlp.output_values(point))
            out[f"output_jacobian/{name}"] = matrix(nlp.output_jacobian(point))
    out["counters"] = dict(nlp.counters)
    return out


def main() -> int:
    root, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2])
    with_nlp = "--nlp" in sys.argv[3:]
    sys.path[:0] = [str(root / "tests"), str(root / "scripts")]
    import test_e01_b_nlp as e01
    from m03_support import flowsheet, nlp_formulation, number, reference

    from openflowsheet.studies.nlp.closure import (
        SolverAvailability,
        optimization_readiness,
        optimize,
    )
    from openflowsheet.studies.nlp.formulation import FullSpaceNlp
    from openflowsheet.studies.nlp.verification import verify_candidate
    from openflowsheet.studies.syn001 import with_pinned

    def available() -> SolverAvailability:
        return SolverAvailability(True, "test double: the audited extra is present")

    def absent() -> SolverAvailability:
        return SolverAvailability(False, "test double: no extra")

    formulations = {
        "NLP-1": nlp_formulation("NLP-1"),
        "NLP-INF": nlp_formulation("NLP-INF"),
        "E01-TAC": e01.bound(e01.program(), "tac"),
    }
    dumped: dict[str, Any] = {}
    for name, formulation in formulations.items():
        readiness = optimization_readiness(formulation, flowsheet({}), solver_probe=available)
        dumped[f"readiness/{name}"] = exact(readiness.as_document())
        for index, start in enumerate(readiness.starts):
            assert start.state is not None and start.regimes is not None
            verification = verify_candidate(
                flowsheet({}),
                formulation,
                start.start,
                regimes=start.regimes,
                optimizer_state=start.state,
            )
            dumped[f"verify/{name}/{index}"] = exact(verification.as_document())
        unsupported = optimize(formulation, flowsheet({}), solver_probe=absent)
        dumped[f"unsupported/{name}"] = exact(unsupported.as_document())
        first = readiness.starts[0]
        assert first.state is not None
        pinned = with_pinned(flowsheet({}), formulation.decision_values(first.start))
        dumped[f"full_space/{name}"] = full_space(
            FullSpaceNlp(pinned, formulation, first.state, first.start)
        )
        if name == "NLP-1":
            optimum = reference()["nlp"]["NLP-1"]["reference_optimum"]
            decisions = (
                number(optimum["U-SPLIT.split_fraction"]),
                number(optimum["U-FLASH.T_spec"]),
            )
            assert readiness.declared_regimes is not None
            dumped["verify/a32"] = exact(
                verify_candidate(
                    flowsheet({}), formulation, decisions, regimes=readiness.declared_regimes
                ).as_document()
            )
        if with_nlp:
            report = optimize(formulation, flowsheet({}))
            dumped[f"report/{name}"] = exact(blank(report.as_document()))
    out.write_text(json.dumps(dumped, sort_keys=True, indent=0) + "\n", encoding="utf-8")
    print(f"dumped {len(dumped)} entries{' (with solved reports)' if with_nlp else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
