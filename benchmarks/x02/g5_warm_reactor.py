"""X02 G5: the warm reactor `pymrm-6089593-g2-nz800-s123w-v1` (design note §5.6, §7 G5; ADR 0070
D4, D7, D8, D10).

Opt-in evidence, never part of the default gate: it needs the pinned reactor environment
`pymrm-6089593-032a050c6cf3` (``python -m openflowsheet.adapters.pymrm.env build``). Its records
are measurements (``judged: false``); the experiment stores they were made in go under
``evidence/X02/<commit>/artifacts/`` (ignored) and are referenced by their manifests' hashes.

**The variant** (``variant``): v3's registered document with the new id, profile `PROFILE_W`
(`adapters/pymrm/child_warm.py`), `child_warm.py`'s hash as `runner_sha256`, and
`accuracy.measured_path_independence_rel` set — v3's value in the provisional document
(``benchmarks/x02/variant-s123w-provisional.json``), G5b's ``max(measured, 1.56e-8)`` in the
registered one.

**G5a-c** (``inlets``), on the provisional variant, through ``ExperimentRunner.run`` as the coupled
route calls it (per tube scaling, `PrC1Provider`), per sequence of four v3 inlets with a recorded
v3 outlet (build decision D-22: g12's four calls and M05's ``cand-C1-P1`` iterations):

- (a) each inlet cold: ``tube_outlet`` bitwise v3's recorded one (canonical bytes); a control
  recomputes v3's request key at each inlet, so the inlet is the recorded one bit for bit;
- (b) warm k from the cold profile at k - 1 (k = 1..3) and warm k = 0 from the cold profile at
  k = 3; rel = max over ξ (by N2 and by NH3), T_out and every outlet flow with |n| > 1e-12·n_tot
  of |a_w - a_c| / |a_c|; ``start.used`` and each fallback;
- (c) wall_warm / wall_cold per inlet (the child's measured wall), with its S1 and S2 times.

**G5d-e** (``loops``), on the registered variant: the real loop pinned to it
(``benchmarks/x02/c1-loop-real-s123w.json``), (i) cold, (ii) restarted from (i) as a `job_id`
source resolves (``job_coupling_start`` + ``external_starts`` over the project's store), (iii) a
neighbour (one parameter edit, ``--neighbour``) cold and warm from (i), with the Δû bound; (e) the
v3 loop cold, then restarted from it (no `start` member anywhere).

Usage (from a checkout; the three thread pins are required)::

    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src \\
        python benchmarks/x02/g5_warm_reactor.py variant --provisional
    ... g5_warm_reactor.py inlets --sequence g12 --store DIR --out FILE
    ... g5_warm_reactor.py loops --store DIR --out FILE
"""

from __future__ import annotations

import argparse
import copy
import hashlib
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
from openflowsheet.adapters.experiments.runner import ExperimentOutcome, ExperimentRunner
from openflowsheet.adapters.experiments.store import ExperimentStore, ListArtifactSink
from openflowsheet.application.coupled_run import (
    LiveExperiments,
    external_starts,
    job_coupling_start,
)
from openflowsheet.application.policies import T06_REVISION_V2
from openflowsheet.application.revision_run import Route, run_revision_session, select_route
from openflowsheet.canonical import document_sha256
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.c1 import COMPONENTS
from openflowsheet.run.bundle import read_artifact
from openflowsheet.thermo import StreamState
from openflowsheet.thermo.pr_c1 import PrC1Provider
from openflowsheet.verify.certificate import CheckPolicy

REPO = Path(__file__).resolve().parents[2]
HERE = REPO / "benchmarks" / "x02"
V3_ID = "pymrm-6089593-g2-nz800-s123-v3"
WARM_ID = "pymrm-6089593-g2-nz800-s123w-v1"
V3_FILE = REPO / "src" / "openflowsheet" / "adapters" / "variants" / f"{V3_ID}.json"
WARM_CHILD = REPO / "src" / "openflowsheet" / "adapters" / "pymrm" / "child_warm.py"
PROVISIONAL = HERE / "variant-s123w-provisional.json"
LOOP_V3 = REPO / "benchmarks" / "m02" / "c1-loop-real.json"
LOOP_WARM = HERE / "c1-loop-real-s123w.json"
#: v3's registered path independence: G5b's floor for the registered value (§7 G5b).
PATH_INDEPENDENCE_FLOOR = 1.56e-8
#: The sequences of G5a-b: four v3 inlets each, in call order, with v3's recorded outlets.
SEQUENCES = {
    "g12": REPO / "benchmarks" / "m05" / "records" / "trust-region-study-real.coupling" / "S0.json",
    "cand-C1-P1": REPO
    / "benchmarks"
    / "m05"
    / "records"
    / "trust-region-study-real.coupling"
    / "cand-C1-P1.json",
}
G12_V3 = REPO / "benchmarks" / "m02" / "g12-real-loop-v3.json"
THREAD_PINS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
CONTEXT = EvaluationContext(model_version="x02-g5", constants_sha256="0" * 64)
FLOW_FLOOR = 1e-12


# -- the variant -----------------------------------------------------------------------------------


def _warm_profile() -> dict[str, Any]:
    import importlib.util

    spec = importlib.util.spec_from_file_location("ofs_pymrm_child_warm", WARM_CHILD)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    profile: dict[str, Any] = copy.deepcopy(module.PROFILE_W)
    return profile


def variant_document(path_independence: float) -> dict[str, Any]:
    """§5.6's variant document: v3's with the four changes."""
    document: dict[str, Any] = json.loads(V3_FILE.read_text(encoding="utf-8"))
    document["variant_id"] = WARM_ID
    document["evaluation"]["profile"] = _warm_profile()
    document["evaluation"]["runner_sha256"] = hashlib.sha256(WARM_CHILD.read_bytes()).hexdigest()
    document["accuracy"]["measured_path_independence_rel"] = path_independence
    return document


def _text(document: Mapping[str, Any]) -> str:
    """The variant files' layout (as `variants/*.json`)."""
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False)


# -- G5a-c ---------------------------------------------------------------------------------------


def runner_in(store: Path, job: str) -> ExperimentRunner:
    return ExperimentRunner(
        ExperimentStore(store, ListArtifactSink()), PrC1Provider(), CONTEXT, job_id=job
    )


def recorded(sequence: str) -> list[dict[str, Any]]:
    """The sequence's four v3 inlets, request keys and recorded outlets, in call order."""
    record = json.loads(SEQUENCES[sequence].read_text(encoding="utf-8"))
    assert record["variants"]["reactor"]["variant_id"] == V3_ID
    found = []
    for item in record["iterations"]:
        unit = item["units"]["reactor"]
        execution = unit["attempts"][-1]["execution"]
        assert execution["status"] == "completed" and execution["tube_outlet"] is not None
        found.append(
            {
                "k": item["k"],
                "inlet": unit["inlet"],
                "n_tubes": float(unit["request"]["boundary"]["n_tubes"]),
                "v3_key": unit["request"]["experiment_key"],
                "v3_inputs": unit["request"]["inputs"],
                "v3_tube_outlet": execution["tube_outlet"],
                "v3_wall_s": execution["timing"]["wall_s"],
            }
        )
    if sequence == "g12":  # the note's sequence: g12's calls are these inlets (same keys)
        calls = json.loads(G12_V3.read_text(encoding="utf-8"))["calls"]
        assert [call["key"] for call in calls] == [item["v3_key"] for item in found]
    return found


def _state(inlet: Mapping[str, Any]) -> StreamState:
    return StreamState(
        n=tuple(float(v) for v in inlet["n"]),
        temperature=float(inlet["T"]),
        pressure=float(inlet["P"]),
    )


def _execution(outcome: ExperimentOutcome) -> dict[str, Any]:
    attempt = outcome.attempts[-1] if outcome.attempts else {}
    execution: dict[str, Any] = attempt.get("execution") or {}
    return execution


def _call(outcome: ExperimentOutcome, started: float) -> dict[str, Any]:
    execution = _execution(outcome)
    diagnostics = execution.get("diagnostics") or {}
    stages = diagnostics.get("stages") or {}
    return {
        "key": outcome.key,
        "cache_hit": outcome.cache_hit,
        "envelope": [outcome.envelope["status"], outcome.envelope["code"]],
        "attempts": len(outcome.attempts),
        "execution_status": execution.get("status"),
        "stage": execution.get("stage"),
        "wall_s": (execution.get("timing") or {}).get("wall_s"),
        "span_s": round(time.perf_counter() - started, 3),
        "stage_wall_s": {
            name: (stages.get(name) or {}).get("wall_s") for name in ("S1", "S2", "S3")
        },
        "certificate_wall_s": (diagnostics.get("certificate") or {}).get("wall_s"),
        "round2": (stages.get("S3") or {}).get("round2") is not None,
        "start": diagnostics.get("start"),
        "profile_sha256": (outcome.result or {}).get("profile_sha256"),
        "tube_inlet": execution.get("tube_inlet"),
        "tube_outlet": execution.get("tube_outlet"),
    }


def path_independence(
    warm: Mapping[str, Any], cold: Mapping[str, Any], tube: Mapping[str, Any]
) -> dict[str, Any]:
    """§7 G5b's metric between a warm and a cold outlet at one inlet."""
    feed = [float(tube["flow"]) * float(y) for y in tube["composition"]]
    w_flows, c_flows = warm["flows"], cold["flows"]
    quantities: dict[str, tuple[float, float]] = {
        "xi_N2": (feed[1] - w_flows[1], feed[1] - c_flows[1]),
        "xi_NH3": ((w_flows[2] - feed[2]) / 2.0, (c_flows[2] - feed[2]) / 2.0),
        "T_out": (warm["temperature"], cold["temperature"]),
    }
    total = sum(abs(v) for v in c_flows)
    for index, (a_w, a_c) in enumerate(zip(w_flows, c_flows, strict=True)):
        if abs(a_c) > FLOW_FLOOR * total:
            quantities[f"n_out[{COMPONENTS[index]}]"] = (a_w, a_c)
    rel = {name: abs(a_w - a_c) / abs(a_c) for name, (a_w, a_c) in quantities.items()}
    worst = max(rel, key=lambda name: rel[name])
    return {"rel": rel, "max": rel[worst], "argmax": worst}


def inlets(sequence: str, store: Path, out: Path) -> int:
    variant = variants.variant_from_document(json.loads(PROVISIONAL.read_text(encoding="utf-8")))
    v3 = variants.registered_variant(V3_ID)
    items = recorded(sequence)
    runner = runner_in(store, "job-000001")
    v3_runner = runner_in(store / "v3", "job-000002")
    rows = []
    for item in items:  # control: the inlet is v3's recorded one, bit for bit
        request = v3_runner.request(v3, _state(item["inlet"]), COMPONENTS, item["n_tubes"])
        item["v3_key_recomputed_equal"] = request["experiment_key"] == item["v3_key"]
        item["v3_inputs_equal"] = document_sha256(request["inputs"]) == document_sha256(
            item.pop("v3_inputs")
        )
    cold: list[dict[str, Any]] = []
    for item in items:  # (a)
        started = time.perf_counter()
        outcome = runner.run(variant, _state(item["inlet"]), COMPONENTS, item["n_tubes"])
        call = _call(outcome, started)
        call["bitwise_v3_recorded"] = call["tube_outlet"] is not None and document_sha256(
            call["tube_outlet"]
        ) == document_sha256(item["v3_tube_outlet"])
        if not call["bitwise_v3_recorded"]:  # §7 G5a: then v3 live at that inlet decides
            live = v3_runner.run(
                v3, _state(item["inlet"]), COMPONENTS, item["n_tubes"], cache="bypass"
            )
            live_outlet = _execution(live).get("tube_outlet")
            call["v3_live_tube_outlet"] = live_outlet
            call["bitwise_v3_live"] = (
                live_outlet is not None
                and call["tube_outlet"] is not None
                and document_sha256(call["tube_outlet"]) == document_sha256(live_outlet)
            )
        cold.append(call)
        print(
            json.dumps(
                {
                    "cold": item["k"],
                    "bitwise": call["bitwise_v3_recorded"],
                    "wall_s": call["wall_s"],
                }
            ),
            flush=True,
        )
    warm: list[dict[str, Any]] = []
    for index, item in enumerate(items):  # (b), (c): k from k - 1; k = 0 from k = 3
        source = cold[index - 1] if index > 0 else cold[-1]
        started = time.perf_counter()
        outcome = runner.run(
            variant,
            _state(item["inlet"]),
            COMPONENTS,
            item["n_tubes"],
            start=source["profile_sha256"],
        )
        call = _call(outcome, started)
        call["start_from_k"] = items[index - 1]["k"] if index > 0 else items[-1]["k"]
        call["path_independence"] = (
            None
            if call["tube_outlet"] is None or cold[index]["tube_outlet"] is None
            else path_independence(
                call["tube_outlet"], cold[index]["tube_outlet"], cold[index]["tube_inlet"]
            )
        )
        call["wall_ratio"] = (
            None
            if call["wall_s"] is None or cold[index]["wall_s"] is None
            else call["wall_s"] / cold[index]["wall_s"]
        )
        warm.append(call)
        print(
            json.dumps(
                {
                    "warm": item["k"],
                    "used": (call["start"] or {}).get("used"),
                    "rel": (call["path_independence"] or {}).get("max"),
                    "ratio": call["wall_ratio"],
                }
            ),
            flush=True,
        )
    rels = [call["path_independence"]["max"] for call in warm if call["path_independence"]]
    for item in items:
        item.pop("v3_tube_outlet")
    for row in [*cold, *warm]:
        row.pop("tube_inlet")
    rows = [
        {
            "k": item["k"],
            "inlet": item["inlet"],
            "v3_key": item["v3_key"],
            "v3_key_recomputed_equal": item["v3_key_recomputed_equal"],
            "v3_inputs_equal": item["v3_inputs_equal"],
            "v3_wall_s": item["v3_wall_s"],
            "cold": cold_call,
            "warm": warm_call,
        }
        for item, cold_call, warm_call in zip(items, cold, warm, strict=True)
    ]
    result = {
        "record": "x02-g5abc-v1",
        "judged": False,
        "specification": "docs/design/X02-warm-starts.md §7 G5 (a)-(c); build decision D-22",
        "sequence": sequence,
        "source": str(SEQUENCES[sequence].relative_to(REPO)),
        "variant": {"variant_id": variant.variant_id, "sha256": variant.sha256},
        "child_warm_sha256": hashlib.sha256(WARM_CHILD.read_bytes()).hexdigest(),
        "summary": {
            "g5a_bitwise_v3_recorded": [row["cold"]["bitwise_v3_recorded"] for row in rows],
            "g5a_v3_keys_recomputed_equal": [row["v3_key_recomputed_equal"] for row in rows],
            "g5a_v3_inputs_equal": [row["v3_inputs_equal"] for row in rows],
            "g5b_rel": rels,
            "g5b_max": max(rels) if rels else None,
            "g5b_used": [(row["warm"]["start"] or {}).get("used") for row in rows],
            "g5b_fallbacks": [
                [row["k"], row["warm"]["start"]["fallback_from"]]
                for row in rows
                if row["warm"]["start"] and not row["warm"]["start"]["used"]
            ],
            "g5b_all_accepted": all(row["warm"]["envelope"][0] == "ok" for row in rows),
            "g5c_wall_ratio": [row["warm"]["wall_ratio"] for row in rows],
            "g5c_saved_s": [
                None
                if row["warm"]["wall_s"] is None or row["cold"]["wall_s"] is None
                else row["cold"]["wall_s"] - row["warm"]["wall_s"]
                for row in rows
            ],
        },
        "rows": rows,
    }
    out.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", "utf-8")
    print(json.dumps(result["summary"]))
    return 0


# -- G5d-e -----------------------------------------------------------------------------------------


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


def part_a_on_v3(store: Path, work: Path, out: Path) -> int:
    """§7 G5e alone: the v3 loop cold, then restarted from it as a `job_id` source."""
    v3 = variants.registered_variant(V3_ID)
    loop = pinned(json.loads(LOOP_V3.read_text(encoding="utf-8")), v3)
    cold = _run(loop, work / "e-cold", store, "job-000015", None, v3)
    restart = _run(loop, work / "e-restart", store, "job-000016", Path(cold["record_path"]), v3)
    summary = {
        "cold": [cold["verification_status"], cold["outer_iterations"], cold["wall_s"]],
        "restart": [restart["verification_status"], restart["outer_iterations"], restart["wall_s"]],
        "w0_equals_cold_final_bitwise": restart["w_hex"][0] == cold["w_hex"][-1],
        "experiments_evaluated": restart["experiments_evaluated"],
        "any_start_member": any(
            item is not None for item in cold["request_starts"] + restart["request_starts"]
        ),
    }
    result = {
        "record": "x02-g5e-v1",
        "judged": False,
        "specification": "docs/design/X02-warm-starts.md §7 G5 (e)",
        "variant": {"variant_id": v3.variant_id, "sha256": v3.sha256},
        "summary": summary,
        "runs": {"cold": cold, "restart": restart},
    }
    out.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", "utf-8")
    print(json.dumps(summary))
    return 0


def loops(store: Path, work: Path, neighbour: str, value: float, out: Path) -> int:
    warm_variant = variants.registered_variant(WARM_ID)
    v3 = variants.registered_variant(V3_ID)
    base = json.loads(LOOP_V3.read_text(encoding="utf-8"))
    loop = pinned(base, warm_variant)
    expected = json.loads(LOOP_WARM.read_text(encoding="utf-8"))
    assert loop == expected, "c1-loop-real-s123w.json is not the v3 loop pinned to the variant"
    edited = copy.deepcopy(loop)
    (spec,) = [s for s in edited["specifications"] if s["id"] == neighbour]
    original = spec["value"]
    spec["value"] = value
    found: dict[str, Any] = {}
    found["i_cold"] = _run(loop, work / "i", store, "job-000011", None, warm_variant)
    print(
        json.dumps({"i": found["i_cold"]["outcome"], "k": found["i_cold"]["outer_iterations"]}),
        flush=True,
    )
    source = Path(found["i_cold"]["record_path"])
    found["ii_restart"] = _run(loop, work / "ii", store, "job-000012", source, warm_variant)
    print(
        json.dumps(
            {"ii": found["ii_restart"]["outcome"], "k": found["ii_restart"]["outer_iterations"]}
        ),
        flush=True,
    )
    found["iii_cold"] = _run(edited, work / "iii-cold", store, "job-000013", None, warm_variant)
    print(
        json.dumps(
            {"iii_cold": found["iii_cold"]["outcome"], "k": found["iii_cold"]["outer_iterations"]}
        ),
        flush=True,
    )
    found["iii_warm"] = _run(edited, work / "iii-warm", store, "job-000014", source, warm_variant)
    print(
        json.dumps(
            {"iii_warm": found["iii_warm"]["outcome"], "k": found["iii_warm"]["outer_iterations"]}
        ),
        flush=True,
    )
    v3_loop = pinned(base, v3)
    found["e_v3_cold"] = _run(v3_loop, work / "e-cold", store, "job-000015", None, v3)
    v3_source = Path(found["e_v3_cold"]["record_path"])
    found["e_v3_restart"] = _run(v3_loop, work / "e-restart", store, "job-000016", v3_source, v3)
    print(
        json.dumps(
            {"e": found["e_v3_restart"]["outcome"], "k": found["e_v3_restart"]["outer_iterations"]}
        ),
        flush=True,
    )
    i, ii = found["i_cold"], found["ii_restart"]
    iii_c, iii_w = found["iii_cold"], found["iii_warm"]
    moved = float(np.linalg.norm(np.array(iii_c["u_hat"]) - np.array(i["u_hat"]), np.inf))
    bound_iii = _bound(iii_w, iii_c)
    e_c, e_r = found["e_v3_cold"], found["e_v3_restart"]
    summary = {
        "d_i": {
            "verification_status": i["verification_status"],
            "outer_iterations": i["outer_iterations"],
            "w_final": i["w"][-1],
        },
        "d_ii": {
            "verification_status": ii["verification_status"],
            "outer_iterations": ii["outer_iterations"],
            "w0_equals_i_final_bitwise": ii["w_hex"][0] == i["w_hex"][-1],
            "experiments_evaluated": ii["experiments_evaluated"],
            "k0_start": ii["request_starts"][0],
        },
        "d_iii": {
            "edit": {"specification": neighbour, "from": original, "to": value},
            "cold": [iii_c["verification_status"], iii_c["outer_iterations"]],
            "warm": [iii_w["verification_status"], iii_w["outer_iterations"]],
            "moved_u_hat_inf": moved,
            "moved_over_bound": moved / bound_iii["bound"] if bound_iii["bound"] > 0 else None,
            "bound": bound_iii,
            "warm_fewer_outer_iterations": iii_w["outer_iterations"] < iii_c["outer_iterations"],
            "wall_s": [iii_c["wall_s"], iii_w["wall_s"]],
        },
        "e": {
            "cold": [e_c["verification_status"], e_c["outer_iterations"]],
            "restart": [e_r["verification_status"], e_r["outer_iterations"]],
            "experiments_evaluated": e_r["experiments_evaluated"],
            "any_start_member": any(
                s is not None for s in e_c["request_starts"] + e_r["request_starts"]
            ),
        },
    }
    result = {
        "record": "x02-g5de-v1",
        "judged": False,
        "specification": "docs/design/X02-warm-starts.md §7 G5 (d)-(e)",
        "variant": {"variant_id": warm_variant.variant_id, "sha256": warm_variant.sha256},
        "summary": summary,
        "runs": found,
    }
    out.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", "utf-8")
    print(json.dumps(summary))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("variant")
    group = make.add_mutually_exclusive_group(required=True)
    group.add_argument("--provisional", action="store_true")
    group.add_argument("--registered", type=float, metavar="MEASURED_REL")
    group.add_argument("--loop", action="store_true")
    measure = commands.add_parser("inlets")
    measure.add_argument("--sequence", choices=sorted(SEQUENCES), required=True)
    measure.add_argument("--store", type=Path, required=True)
    measure.add_argument("--out", type=Path, required=True)
    run = commands.add_parser("loops")
    run.add_argument("--store", type=Path, required=True)
    run.add_argument("--work", type=Path, required=True)
    run.add_argument("--neighbour", default="SPEC-S3-T")
    run.add_argument("--value", type=float, required=True)
    run.add_argument("--out", type=Path, required=True)
    part_a = commands.add_parser("part-a-v3")
    part_a.add_argument("--store", type=Path, required=True)
    part_a.add_argument("--work", type=Path, required=True)
    part_a.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args(argv)
    if arguments.command == "variant":
        if arguments.provisional:
            document = variant_document(
                json.loads(V3_FILE.read_text(encoding="utf-8"))["accuracy"][
                    "measured_path_independence_rel"
                ]
            )
            PROVISIONAL.write_text(_text(document), "utf-8")
        elif arguments.loop:
            warm = variants.registered_variant(WARM_ID)
            LOOP_WARM.write_text(
                json.dumps(
                    pinned(json.loads(LOOP_V3.read_text(encoding="utf-8")), warm),
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                "utf-8",
            )
        else:
            document = variant_document(max(arguments.registered, PATH_INDEPENDENCE_FLOOR))
            target = V3_FILE.with_name(f"{WARM_ID}.json")
            target.write_text(_text(document), "utf-8")
            print(document_sha256(document))
        return 0
    missing = [name for name in THREAD_PINS if os.environ.get(name) != "1"]
    if missing:
        print(f"set {', '.join(missing)}=1", file=sys.stderr)
        return 2
    if arguments.command == "part-a-v3":
        return part_a_on_v3(arguments.store, arguments.work, arguments.out)
    if arguments.command == "inlets":
        return inlets(arguments.sequence, arguments.store, arguments.out)
    return loops(
        arguments.store, arguments.work, arguments.neighbour, arguments.value, arguments.out
    )


if __name__ == "__main__":
    sys.exit(main())
