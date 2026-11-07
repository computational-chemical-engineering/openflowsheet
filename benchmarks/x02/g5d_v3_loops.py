"""X02 G5 (d) on v3: Part A's real-loop evidence with cold experiments (design note §7 G5 (d),
X02 review S-2; ADR 0070 D2, D3).

Opt-in evidence, never part of the default gate: it needs the pinned reactor environment
`pymrm-6089593-032a050c6cf3` (``python -m openflowsheet.adapters.pymrm.env build``). The record is a
measurement (``judged: false``, with the gate's criteria evaluated beside it); the experiment
store it was made in goes under ``evidence/X02/<commit>/artifacts/`` (ignored) and is referenced
by its tree hash.

No start-capable variant is registered (review ruling 1), so G5 (d) runs on the real loop
``benchmarks/m02/c1-loop-real.json`` as registered (v3), every experiment cold:

- (i) cold: VERIFIED, iterates reported;
- (ii) restarted from (i) as a `job_id` source resolves (``job_coupling_start`` +
  ``external_starts`` over the project's store), same revision: VERIFIED, 1 outer iteration, w₀ =
  (i)'s final w bitwise, at most 1 call, no ``start`` member;
- (iii) a neighbour (one parameter edit, ``--neighbour``/``--value``), cold and warm from (i): both
  VERIFIED, the Δû bound holds, the warm run takes fewer outer iterations than the cold one, and
  the edit moves w by more than 10× the bound.

The run helpers are those of the retired G5 campaign script (``benchmarks/x02/g5_warm_reactor.py``
at ``005d206f``), minus everything that loaded the warm child.

Usage (from a checkout; the three thread pins are required)::

    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src \\
        python benchmarks/x02/g5d_v3_loops.py --store DIR --work DIR --value 675.15 --out FILE
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

from openflowsheet.adapters import variants
from openflowsheet.adapters.experiments.runner import ExperimentRunner
from openflowsheet.adapters.experiments.store import ExperimentStore, ListArtifactSink
from openflowsheet.application.coupled_run import (
    LiveExperiments,
    external_starts,
    job_coupling_start,
)
from openflowsheet.application.policies import T06_REVISION_V2
from openflowsheet.application.revision_run import Route, run_revision_session, select_route
from openflowsheet.compiled import EvaluationContext
from openflowsheet.run.bundle import read_artifact
from openflowsheet.thermo.pr_c1 import PrC1Provider
from openflowsheet.verify.certificate import CheckPolicy

REPO = Path(__file__).resolve().parents[2]
V3_ID = "pymrm-6089593-g2-nz800-s123-v3"
LOOP_V3 = REPO / "benchmarks" / "m02" / "c1-loop-real.json"
THREAD_PINS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
CONTEXT = EvaluationContext(model_version="x02-g5", constants_sha256="0" * 64)
#: §7 G5 (d)(iii): the edit must move w by more than this many Δû bounds.
MOVE_OVER_BOUND_MIN = 10.0


def runner_in(store: Path, job: str) -> ExperimentRunner:
    return ExperimentRunner(
        ExperimentStore(store, ListArtifactSink()), PrC1Provider(), CONTEXT, job_id=job
    )


def pinned(document: Mapping[str, Any], variant: variants.Variant) -> dict[str, Any]:
    pinned_document: dict[str, Any] = copy.deepcopy(dict(document))
    for item in pinned_document["instances"]:
        if item["id"] == "reactor":
            item["model"] = {
                "id": variant.model_id,
                "version": variant.variant_id,
                "artifact_ref": variant.sha256,
            }
    return pinned_document


class Counted(LiveExperiments):
    """`LiveExperiments` that keeps each call's facts."""

    def __init__(self, runner: ExperimentRunner) -> None:
        super().__init__(runner)
        self.calls: list[dict[str, Any]] = []

    def evaluate(self, unit: Any, variant: Any, inlet: Any, start: str | None = None) -> Any:
        started = time.perf_counter()
        answer = super().evaluate(unit, variant, inlet, start=start)
        self.calls.append(
            {
                "start": start,
                "span_s": round(time.perf_counter() - started, 3),
                "status": answer.status,
            }
        )
        return answer


def _run(
    document: Mapping[str, Any],
    directory: Path,
    store: Path,
    job: str,
    source: Path | None,
    variant: variants.Variant,
) -> dict[str, Any]:
    route = select_route(document)
    assert isinstance(route, Route) and route.solve_path == "revision_coupled", route
    start = None
    if source is not None:  # as `declared_coupled_start` resolves a `job_id` (§5.2)
        start = job_coupling_start(source)
        profiles = external_starts(source, {"reactor": variant}, ExperimentStore(store).profile)
        start = replace(start, profiles=profiles)
    experiments = Counted(runner_in(store, job))
    started = time.perf_counter()
    manifest = run_revision_session(
        route,
        document,
        directory,
        run_id=f"run-x02-g5-{job}",
        policy=T06_REVISION_V2,
        check_policy=CheckPolicy(),
        policy_requested="default",
        experiments=experiments,
        coupled_start=start,
    )
    wall = time.perf_counter() - started
    record = read_artifact(directory, "external-coupling.json")
    solve_path = read_artifact(directory, "solve-path.json")
    iterations = record["iterations"]
    block = record["coupling_block"]
    scales = np.array([block["scales"]["X"], block["scales"]["dT_K"]])
    final = iterations[-1]
    entry = final["units"]["reactor"]
    matrices = [item["step"]["B"] for item in iterations if item.get("step")]
    known = [matrix for matrix in matrices if matrix is not None]
    requests = [item["units"]["reactor"].get("request") or {} for item in iterations]
    return {
        "outcome": manifest.outcome,
        "verification_status": manifest.verification_status,
        "outer_iterations": len(iterations),
        "w": [item["w"] for item in iterations],
        "w_hex": [[float(v).hex() for v in item["w"]] for item in iterations],
        "u_hat": (np.array(final["w"]) / scales).tolist(),
        "r_hat": (np.array([entry["r_xi"], entry["r_T"]]) / scales).tolist(),
        "B_last": known[-1] if known else None,
        "experiments_evaluated": len(experiments.calls),
        "calls": experiments.calls,
        "request_starts": [
            (request.get("start") or {}).get("profile_sha256") for request in requests
        ],
        "warm_start": solve_path.get("warm_start"),
        "wall_s": round(wall, 1),
        "source": None if source is None else str(source),
        "record_path": str(directory / "artifacts" / "external-coupling.json"),
    }


def _bound(warm: Mapping[str, Any], cold: Mapping[str, Any]) -> dict[str, Any]:
    """§7's Δû bound of `warm` against the cold run `cold`."""
    b_c = np.array(cold["B_last"]) if cold["B_last"] is not None else -np.eye(2)
    bound = (
        2.0
        * float(np.linalg.norm(np.linalg.inv(b_c), np.inf))
        * (
            float(np.linalg.norm(warm["r_hat"], np.inf))
            + float(np.linalg.norm(cold["r_hat"], np.inf))
        )
    )
    distance = float(np.linalg.norm(np.array(warm["u_hat"]) - np.array(cold["u_hat"]), np.inf))
    return {"distance": distance, "bound": bound, "holds": distance <= bound}


def _progress(name: str, run: Mapping[str, Any]) -> None:
    print(json.dumps({name: run["verification_status"], "k": run["outer_iterations"]}), flush=True)


def loops(store: Path, work: Path, neighbour: str, value: float, out: Path) -> int:
    v3 = variants.registered_variant(V3_ID)
    loop = pinned(json.loads(LOOP_V3.read_text(encoding="utf-8")), v3)
    edited = copy.deepcopy(loop)
    (spec,) = [s for s in edited["specifications"] if s["id"] == neighbour]
    original = spec["value"]
    spec["value"] = value
    found: dict[str, Any] = {}
    found["i_cold"] = _run(loop, work / "i", store, "job-000021", None, v3)
    _progress("i", found["i_cold"])
    source = Path(found["i_cold"]["record_path"])
    found["ii_restart"] = _run(loop, work / "ii", store, "job-000022", source, v3)
    _progress("ii", found["ii_restart"])
    found["iii_cold"] = _run(edited, work / "iii-cold", store, "job-000023", None, v3)
    _progress("iii_cold", found["iii_cold"])
    found["iii_warm"] = _run(edited, work / "iii-warm", store, "job-000024", source, v3)
    _progress("iii_warm", found["iii_warm"])
    i, ii = found["i_cold"], found["ii_restart"]
    iii_c, iii_w = found["iii_cold"], found["iii_warm"]
    moved = float(np.linalg.norm(np.array(iii_c["u_hat"]) - np.array(i["u_hat"]), np.inf))
    bound_iii = _bound(iii_w, iii_c)
    moved_over_bound = moved / bound_iii["bound"] if bound_iii["bound"] > 0 else None
    any_start = any(s is not None for run in found.values() for s in run["request_starts"])
    summary = {
        "d_i": {
            "verification_status": i["verification_status"],
            "outer_iterations": i["outer_iterations"],
            "w_final": i["w"][-1],
            "wall_s": i["wall_s"],
        },
        "d_ii": {
            "verification_status": ii["verification_status"],
            "outer_iterations": ii["outer_iterations"],
            "w0_equals_i_final_bitwise": ii["w_hex"][0] == i["w_hex"][-1],
            "experiments_evaluated": ii["experiments_evaluated"],
            "wall_s": ii["wall_s"],
        },
        "d_iii": {
            "edit": {"specification": neighbour, "from": original, "to": value},
            "cold": [iii_c["verification_status"], iii_c["outer_iterations"]],
            "warm": [iii_w["verification_status"], iii_w["outer_iterations"]],
            "moved_u_hat_inf": moved,
            "moved_over_bound": moved_over_bound,
            "bound": bound_iii,
            "warm_fewer_outer_iterations": iii_w["outer_iterations"] < iii_c["outer_iterations"],
            "wall_s": [iii_c["wall_s"], iii_w["wall_s"]],
        },
        "any_start_member": any_start,
    }
    criteria = {
        "i_verified": i["verification_status"] == "VERIFIED",
        "ii_verified_one_iteration": ii["verification_status"] == "VERIFIED"
        and ii["outer_iterations"] == 1,
        "ii_w0_bitwise": summary["d_ii"]["w0_equals_i_final_bitwise"],
        "ii_at_most_one_call": ii["experiments_evaluated"] <= 1,
        "iii_both_verified": iii_c["verification_status"] == "VERIFIED"
        and iii_w["verification_status"] == "VERIFIED",
        "iii_bound_holds": bound_iii["holds"],
        "iii_warm_fewer_outer_iterations": summary["d_iii"]["warm_fewer_outer_iterations"],
        "iii_edit_moves_w_beyond_10_bounds": moved_over_bound is not None
        and moved_over_bound > MOVE_OVER_BOUND_MIN,
        "all_experiments_cold": not any_start,
    }
    result = {
        "record": "x02-g5d-v3-v1",
        "judged": False,
        "specification": "docs/design/X02-warm-starts.md §7 G5 (d), on v3 (X02 review S-2)",
        "variant": {"variant_id": v3.variant_id, "sha256": v3.sha256},
        "summary": summary,
        "criteria": criteria,
        "runs": found,
    }
    out.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", "utf-8")
    print(json.dumps({"criteria": criteria, "all": all(criteria.values())}))
    return 0 if all(criteria.values()) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--neighbour", default="SPEC-S3-T")
    parser.add_argument("--value", type=float, required=True)
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args(argv)
    missing = [name for name in THREAD_PINS if os.environ.get(name) != "1"]
    if missing:
        print(f"set {', '.join(missing)}=1", file=sys.stderr)
        return 2
    return loops(
        arguments.store, arguments.work, arguments.neighbour, arguments.value, arguments.out
    )


if __name__ == "__main__":
    sys.exit(main())
