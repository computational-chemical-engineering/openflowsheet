"""M02 G12: the real loop — `C1-LOOP-M02-v1` with `c1.reactor` (design note §10.2 G12, §8.1,
§4.2-§4.4, §7.2).

Opt-in evidence, never part of the default gate: it needs the pinned reactor environment (see
``g10_adapter_halves.py``). Its record, ``benchmarks/m02/g12-real-loop.json``, is a measurement
(``judged: false``).

**Runs**, each through the route the `solve` job runs (``run_revision_session`` with
``LiveExperiments`` over an experiment store, as ``application/jobs/runner.py`` wires it, minus the
job wrapper, so each experiment call can be timed):

1. *solve* — ``benchmarks/m02/c1-loop-real.json``; outcome, outer iterations, ρ, certificate,
   the coupling checks, floor ratios, the reactor inlet against the variant's hard domain
   (Q-F5's per-tube flow bound included) and the kinetics' data domain; wall time, each
   experiment's wall time, and the gaps between experiments (the driver's compile + inner solve
   per outer step).
2. *reproduce* — ``reproduce_bundle`` on the solve's bundle (the `reproduce` job's function):
   R3, the results replayed from the record (§7.2).
3. *live rerun* — the same route again in a new directory, over the same experiment store,
   every experiment with the cache **bypassed** (a bypass switch local to this script, build log
   D66): the runner re-executes each request and compares the new attempt with the producing one
   (``repeat_bitwise_equal``, §5.3). The script also compares each re-executed tube outlet with
   the solve's own, by bits, in call order.

**Under v3** (§14.5 G12v3-1, §14.6, §14.7 G12v3-2; RP-1 of §14.5 D8) the record also states
which experiments ran the polish round (round 2), the RP-1 recomputation of the final inner
model's `constants_sha256`, and, with ``--compare``, whether the iterate sequence (k, w_k, ρ_k)
equals a previous variant's record bitwise (G12v3-1 requires it when no experiment ran round 2).
With ``--t-in`` (repeatable) the script runs G12v3-2 instead: the loop with SPEC-S3-T (the
reactor-inlet temperature) set to each value, solve only, as D87 ran it, recording the outcome,
every reactor request's refusal and inert fraction y_Ar + y_CH4, and its minimum.

Usage (from a checkout)::

    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src \\
        python benchmarks/m02/g12_real_loop.py --out benchmarks/m02/g12-real-loop-v3.json \\
        --compare benchmarks/m02/g12-real-loop.json
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src \\
        python benchmarks/m02/g12_real_loop.py --t-in 653.15 --t-in 693.15 \\
        --out benchmarks/m02/g12-real-loop-v3-edges.json

The three thread pins are required (the replay compares the worker's pins, as CI sets them); the
script refuses to run without them. The experiment runner's job ids are `job-000001` (solve) and
`job-000002` (live rerun): the coupling record's schema admits only job-shaped ids.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from openflowsheet.adapters import variants
from openflowsheet.adapters.experiments.runner import CacheMode, ExperimentRunner
from openflowsheet.adapters.experiments.store import ExperimentStore, ListArtifactSink
from openflowsheet.application.coupled_run import LiveExperiments, answer_of, final_constants
from openflowsheet.application.policies import T06_REVISION_V2
from openflowsheet.application.revision_run import (
    Route,
    reproduce_bundle,
    run_revision_session,
    select_route,
)
from openflowsheet.canonical import document_sha256, file_sha256
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.c1 import COMPONENTS
from openflowsheet.models.c1.boundary import data_domain_violations, hard_domain_violations
from openflowsheet.run.bundle import BundleError, read_artifact
from openflowsheet.thermo import StreamState
from openflowsheet.thermo.pr_c1 import PrC1Provider
from openflowsheet.verify.certificate import CheckPolicy

REPO = Path(__file__).resolve().parents[2]
LOOP = REPO / "benchmarks" / "m02" / "c1-loop-real.json"
F_NOM = 0.007146961299302104
THREAD_PINS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
CONTEXT = EvaluationContext(model_version="m02-g12", constants_sha256="0" * 64)


class TimedExperiments(LiveExperiments):
    """`LiveExperiments` that times each call and keeps its outcome; `cache` is the runner's
    mode ("bypass" for the live rerun)."""

    def __init__(self, runner: ExperimentRunner, cache: CacheMode = "use") -> None:
        super().__init__(runner)
        self.cache = cache
        self.calls: list[dict[str, Any]] = []

    def evaluate(self, unit: Any, variant: Any, inlet: Any) -> Any:
        started = time.perf_counter()
        outcome = self.runner.run(
            variant,
            StreamState(n=inlet.n, temperature=inlet.T, pressure=inlet.P),
            unit.components,
            unit.n_tubes,
            cache=self.cache,
        )
        ended = time.perf_counter()
        attempt = outcome.attempts[-1] if outcome.attempts else {}
        execution = attempt.get("execution") or {}
        stages = (execution.get("diagnostics") or {}).get("stages") or {}
        self.calls.append(
            {
                "started": started,
                "ended": ended,
                "key": outcome.key,
                "cache_hit": outcome.cache_hit,
                "envelope_status": outcome.envelope["status"],
                "envelope_code": outcome.envelope["code"],
                "attempts": len(outcome.attempts),
                "execution_status": execution.get("status"),
                "wall_s": (execution.get("timing") or {}).get("wall_s"),
                "tube_outlet": execution.get("tube_outlet"),
                "repeat_bitwise_equal": attempt.get("repeat_bitwise_equal"),
                "repeat_of": attempt.get("repeat_of"),
                "y_inert": (inlet.n[3] + inlet.n[4]) / sum(inlet.n),
                "inlet": {"n_mol_s": list(inlet.n), "T_K": inlet.T, "P_Pa": inlet.P},
                "round2": (stages.get("S3") or {}).get("round2"),
            }
        )
        return answer_of(
            outcome.request, outcome.result, outcome.envelope, outcome.attempts, outcome.cache_hit
        )


def runner_in(root: Path, job: str) -> ExperimentRunner:
    return ExperimentRunner(
        ExperimentStore(root, ListArtifactSink()), PrC1Provider(), CONTEXT, job_id=job
    )


def solve(
    document: Mapping[str, Any], directory: Path, run_id: str, experiments: TimedExperiments
) -> tuple[Any, float, float]:
    route = select_route(document)
    assert isinstance(route, Route) and route.solve_path == "revision_coupled", route
    started = time.perf_counter()
    manifest = run_revision_session(
        route,
        document,
        directory,
        run_id=run_id,
        policy=T06_REVISION_V2,
        check_policy=CheckPolicy(),
        policy_requested="default",
        experiments=experiments,
    )
    return manifest, started, time.perf_counter()


def _bits(outlet: Mapping[str, Any] | None) -> list[str] | None:
    if outlet is None:
        return None
    return [float(v).hex() for v in outlet["flows"]] + [float(outlet["temperature"]).hex()]


def _calls(calls: list[dict[str, Any]], started: float, ended: float) -> list[dict[str, Any]]:
    """Each call's facts with the gap before it (driver + compile + inner solve) and its span."""
    found = []
    previous = started
    for number, call in enumerate(calls):
        item = {k: v for k, v in call.items() if k not in ("started", "ended", "tube_outlet")}
        item["call"] = number
        item["gap_before_s"] = round(call["started"] - previous, 3)
        item["span_s"] = round(call["ended"] - call["started"], 3)
        found.append(item)
        previous = call["ended"]
    if found:
        found[-1]["tail_after_s"] = round(ended - previous, 3)
    return found


def _round2_ran(calls: list[dict[str, Any]]) -> list[int]:
    """The calls (by number) whose experiment ran the polish round (§14.6 E1, §14.7 F2)."""
    return [number for number, call in enumerate(calls) if call["round2"] is not None]


def _iterates(iterations: list[dict[str, Any]]) -> list[list[Any]]:
    """(k, w_k, ρ_k) with every float as `float.hex`: the G12v3-1 comparison, bit for bit."""
    return [
        [
            item["k"],
            [float(v).hex() for v in item["w"]],
            None if item["rho"] is None else float(item["rho"]).hex(),
        ]
        for item in iterations
    ]


def edges(
    document: dict[str, Any], variant: variants.Variant, temperatures: list[float]
) -> dict[str, Any]:
    """G12v3-2 (§14.7): the loop at each reactor-inlet T (SPEC-S3-T), solve only, as D87 ran it."""
    (reactor,) = [item for item in document["instances"] if item["id"] == "reactor"]
    n_tubes = float(reactor["parameters"]["n_tubes"]["value"])
    (inlet_stream,) = [c["id"] for c in document["connections"] if c["to"]["instance"] == "reactor"]
    domain = variants.hard_domain(variant)
    found = []
    for temperature in temperatures:
        edge = json.loads(json.dumps(document))
        (spec,) = [s for s in edge["specifications"] if s["id"] == "SPEC-S3-T"]
        spec["value"] = temperature
        with tempfile.TemporaryDirectory(prefix="m02-g12v3-2-") as scratch:
            work = Path(scratch)
            experiments = TimedExperiments(runner_in(work / "project", "job-000001"))
            manifest, started, ended = solve(edge, work / "bundle", "run-m02-g12v3-2", experiments)
            record_doc = read_artifact(work / "bundle", "external-coupling.json")
            try:
                state = read_artifact(work / "bundle", "solution-state.json")["variables"]
            except BundleError:
                state = None  # recorded as such; (a) then fails on the outcome
        inlet = (
            None
            if state is None
            else StreamState(
                tuple(state[f"{inlet_stream}.n.{c}"] for c in COMPONENTS),
                state[f"{inlet_stream}.T"],
                state[f"{inlet_stream}.P"],
            )
        )
        calls = experiments.calls
        requests = [
            StreamState(tuple(c["inlet"]["n_mol_s"]), c["inlet"]["T_K"], c["inlet"]["P_Pa"])
            for c in calls
        ]
        found.append(
            {
                "T_in_spec_K": temperature,
                "outcome": manifest.outcome,
                "reason": record_doc.get("reason"),
                "verification_status": manifest.verification_status,
                "outer_iterations": max(item["k"] for item in record_doc["iterations"]),
                "experiments": len(calls),
                "refused_out_of_domain": [
                    n for n, c in enumerate(calls) if c["envelope_status"] == "out_of_domain"
                ],
                "requests_outside_hard_domain": [
                    n
                    for n, request in enumerate(requests)
                    if hard_domain_violations(request, domain, n_tubes)
                ],
                "envelopes": [[c["envelope_status"], c["envelope_code"]] for c in calls],
                "round2_ran": _round2_ran(calls),
                "y_inert_solution": None
                if inlet is None
                else (inlet.n[3] + inlet.n[4]) / inlet.total_flow,
                "y_inert_min_requests": min(c["y_inert"] for c in calls) if calls else None,
                "reactor_inlet": None
                if inlet is None
                else {
                    "stream": inlet_stream,
                    "n_mol_s": list(inlet.n),
                    "T_K": inlet.temperature,
                    "P_Pa": inlet.pressure,
                    "hard_domain_violations": hard_domain_violations(inlet, domain, n_tubes),
                },
                "solve_wall_s": round(ended - started, 1),
                "calls": _calls(calls, started, ended),
            }
        )
    return {
        "record": "m02-g12v3-2-loop-edges",
        "version": 1,
        "status": "measured",
        "judged": False,
        "specification": "docs/design/M02-pymrm-adapter.md §14.7 G12v3-2",
        "loop_sha256": file_sha256(LOOP),
        "variant": {"variant_id": variant.variant_id, "sha256": variant.sha256},
        "summary": {
            "a_converged_verified": all(
                (e["outcome"], e["verification_status"]) == ("CONVERGED", "VERIFIED") for e in found
            ),
            "b_no_out_of_domain": all(not e["refused_out_of_domain"] for e in found),
            "c_y_inert": {
                str(e["T_in_spec_K"]): [e["y_inert_solution"], e["y_inert_min_requests"]]
                for e in found
            },
        },
        "edges": found,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--compare", type=Path, help="G12v3-1: the previous variant's record")
    parser.add_argument("--t-in", type=float, action="append", help="G12v3-2: SPEC-S3-T, K")
    arguments = parser.parse_args()
    unpinned = [name for name in THREAD_PINS if os.environ.get(name) != "1"]
    if unpinned:
        raise SystemExit(f"set {', '.join(unpinned)}=1 (the replay compares the thread pins)")
    document = json.loads(LOOP.read_text(encoding="utf-8"))
    if arguments.t_in:
        (reactor,) = [item for item in document["instances"] if item["id"] == "reactor"]
        variant = variants.registered_variant(reactor["model"]["version"])
        found = edges(document, variant, arguments.t_in)
        arguments.out.write_text(json.dumps(found, indent=1, ensure_ascii=False) + "\n", "utf-8")
        print(json.dumps(found["summary"]))
        return 0
    (reactor,) = [item for item in document["instances"] if item["id"] == "reactor"]
    variant = variants.registered_variant(reactor["model"]["version"])
    n_tubes = float(reactor["parameters"]["n_tubes"]["value"])
    (inlet_stream,) = [c["id"] for c in document["connections"] if c["to"]["instance"] == "reactor"]
    with tempfile.TemporaryDirectory(prefix="m02-g12-") as scratch:
        work = Path(scratch)
        store = work / "project"
        # -- 1. solve --------------------------------------------------------------------------
        first = TimedExperiments(runner_in(store, "job-000001"))
        manifest, started, ended = solve(document, work / "bundle", "run-m02-g12", first)
        bundle = work / "bundle"
        record_doc = read_artifact(bundle, "external-coupling.json")
        certificate = read_artifact(bundle, "solution-certificate.json")
        state = read_artifact(bundle, "solution-state.json")["variables"]
        # -- 2. reproduce (replayed from record) -----------------------------------------------
        replay_started = time.perf_counter()
        reproduction = reproduce_bundle(
            bundle, rerun=True, rerun_directory=work / "replay", run_id="run-m02-g12-replay"
        )
        replay_s = time.perf_counter() - replay_started
        report = reproduction.report
        # -- 3. live rerun, cache bypassed -----------------------------------------------------
        second = TimedExperiments(runner_in(store, "job-000002"), cache="bypass")
        live, live_started, live_ended = solve(document, work / "live", "run-m02-g12-live", second)
        live_state = read_artifact(work / "live", "solution-state.json")["variables"]

    inlet = StreamState(
        tuple(state[f"{inlet_stream}.n.{c}"] for c in COMPONENTS),
        state[f"{inlet_stream}.T"],
        state[f"{inlet_stream}.P"],
    )
    checks = {
        c["id"]: {k: c.get(k) for k in ("result", "value", "tolerance", "near_threshold")}
        for c in certificate["checks"]
        if c["id"].startswith("EXT-COUPLING:")
    }
    iterations = [
        {
            "k": item["k"],
            "w": item["w"],
            "rho": item["rho"],
            "step": item["step"]["kind"],
            "inner_outcome": item["inner"]["outcome"],
            "inner_iterations": item["inner"].get("iterations"),
            "floor_ratio_xi": item["units"]["reactor"].get("floor_ratio_xi"),
            "floor_ratio_T": item["units"]["reactor"].get("floor_ratio_T"),
            "r_xi": item["units"]["reactor"].get("r_xi"),
            "r_T": item["units"]["reactor"].get("r_T"),
        }
        for item in record_doc["iterations"]
    ]
    final = iterations[-1]
    rerun_bits = [
        _bits(a["tube_outlet"]) == _bits(b["tube_outlet"])
        for a, b in zip(first.calls, second.calls, strict=False)
    ]
    rhos = [item["rho"] for item in iterations if item["rho"] is not None]
    route = select_route(document)
    assert isinstance(route, Route), route
    rp1 = final_constants(route.binding, record_doc)
    compared = None
    if arguments.compare is not None:
        previous = json.loads(arguments.compare.read_text(encoding="utf-8"))
        compared = {
            "record_sha256": file_sha256(arguments.compare),
            "variant": previous["variant"],
            "applies": not _round2_ran(first.calls),
            "iterates_bitwise_equal": _iterates(iterations) == _iterates(previous["iterations"]),
        }
    result = {
        "record": "m02-g12-real-loop",
        "version": 2,
        "status": "measured",
        "judged": False,
        "specification": "docs/design/M02-pymrm-adapter.md §10.2 G12, §8.1; §14.5 G12v3-1, D8 RP-1",
        "loop_sha256": file_sha256(LOOP),
        "variant": {"variant_id": variant.variant_id, "sha256": variant.sha256},
        "summary": {
            "outcome": manifest.outcome,
            "reason": record_doc.get("reason"),
            "verification_status": manifest.verification_status,
            "reproducibility_class": manifest.reproducibility_class,
            "outer_iterations": max(item["k"] for item in iterations),
            "rho_final": rhos[-1] if rhos else None,
            "rho_max_after_k0": max(rhos) if rhos else None,
            "floor_ratio_xi_final": final["floor_ratio_xi"],
            "floor_ratio_T_final": final["floor_ratio_T"],
            "coupling_checks": checks,
            "rcond_1": (certificate.get("regularity") or {}).get("rcond_1"),
            "experiments": len(first.calls),
            "round2_ran": _round2_ran(first.calls),
            "rp1_constants_sha256": None
            if rp1 is None
            else {"recorded": rp1[0], "recomputed": rp1[1], "equal": rp1[0] == rp1[1]},
            "g12v3_1_compare": compared,
            "reactor_inlet": {
                "stream": inlet_stream,
                "n_mol_s": list(inlet.n),
                "T_K": inlet.temperature,
                "P_Pa": inlet.pressure,
                "per_tube_multiple_of_F_nom": inlet.total_flow / n_tubes / F_NOM,
                "y_inert": (inlet.n[3] + inlet.n[4]) / inlet.total_flow,
                "hard_domain_violations": hard_domain_violations(
                    inlet, variants.hard_domain(variant), n_tubes
                ),
                "data_domain_violations": list(data_domain_violations(inlet)),
            },
            "solve_wall_s": round(ended - started, 1),
            "experiment_wall_s": [call["wall_s"] for call in first.calls],
            "reproduce": {
                "verdict": report.verdict,
                "bitwise_floats": report.bitwise_floats,
                "reasons": list(report.reasons),
                "differences": list(report.differences)[:10],
                "wall_s": round(replay_s, 1),
            },
            "live_rerun": {
                "outcome": live.outcome,
                "verification_status": live.verification_status,
                "experiments": len(second.calls),
                "repeat_bitwise_equal": [call["repeat_bitwise_equal"] for call in second.calls],
                "tube_outlets_bitwise_equal_in_order": rerun_bits,
                "new_keys": sum(
                    1
                    for a, b in zip(first.calls, second.calls, strict=False)
                    if a["key"] != b["key"]
                ),
                "final_state_bitwise_equal": json.dumps(live_state, sort_keys=True)
                == json.dumps(state, sort_keys=True),
                "wall_s": round(live_ended - live_started, 1),
            },
        },
        "iterations": iterations,
        "calls": _calls(first.calls, started, ended),
        "live_calls": _calls(second.calls, live_started, live_ended),
        "certificate_sha256": document_sha256(certificate),
        "coupling_record_sha256": document_sha256(record_doc),
    }
    arguments.out.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", "utf-8")
    print(json.dumps(result["summary"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
