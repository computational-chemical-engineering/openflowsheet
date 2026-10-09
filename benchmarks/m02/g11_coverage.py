"""M02 G11: coverage and timing of the real reactor through M02's adapter (design note §10.2 G11,
§5.2, §10.3; M01 spec §8.15 "Q-F4's sweep, defined", Q-F4, Q-F5).

Opt-in evidence, never part of the default gate: it needs the pinned reactor environment (see
``g10_adapter_halves.py``). Its record, ``benchmarks/m02/g11-coverage.json``, is a measurement
(``judged: false``); the rules of §10.3 and §5.2 act on its numbers, by hand, as register entries.

**Points.** The registered variant, N_tubes = 1 (so the process inlet is the tube inlet):

- *(a) Q-F4* — the 16 corners of T_in × P_in × H₂/N₂ × y_inert = {573.15, 773.15} K ×
  {5e6, 1.5e7} Pa × {1, 4} × {0, 0.2} and the centre (673.15 K, 1e7 Pa, 2.5, 0.1); y_NH₃ = 0.03,
  Ar:CH₄ = 3:4, the nominal per-tube flow F_nom; through ``ExperimentRunner.run`` (the boundary,
  S1-S3). A corner whose exact construction rounds outside a bound has that coordinate moved
  inward by 2⁻⁴⁰ relative (§8.15), recorded as ``nudged``.
- *(b) Q-F5* — the centre at 0.25, 0.5, 2 and 4 × F_nom: 0.5 and 2 through the boundary (the
  variant's flow bound's edges), 0.25 and 4 through the evaluation seam directly (the variant
  refuses them).
- *(c) ΔP ramp* — the nominal composition, 673.15 K, 5e6 Pa, 0.5-16 × F_nom (doubling), the
  evaluation seam directly: |ΔP|/P_in and the smallest multiple at which it exceeds ε_P.
- *(d) timing* — the probe's nominal tube inputs, five evaluations through one backend (one
  handshake), serial and alone after the pool: ``startup_s``, ``solve_s`` and the start-up share.

A direct point is ``accepted`` when the child accepted (completed, no failed stage) and the
boundary's own checks would pass: |ΔP|/P_in ≤ ε_P and the projection's defect ≤ the defect limit
(the boundary's path after the hard-domain check, ``models/c1/boundary.py``). Points (a)-(c) run
in a process pool (``--workers``); each worker has its own experiment store and backend, so no
result depends on the order. Wall times are measured under that concurrency (recorded).

Usage (from a checkout)::

    PYTHONPATH=src python benchmarks/m02/g11_coverage.py --out benchmarks/m02/g11-coverage.json
"""

from __future__ import annotations

import argparse
import json
import math
import multiprocessing
import os
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from openflowsheet.adapters import variants
from openflowsheet.adapters.experiments.backends import OutOfProcessBackend
from openflowsheet.adapters.experiments.runner import ExperimentRunner
from openflowsheet.adapters.experiments.store import ExperimentStore, ListArtifactSink
from openflowsheet.adapters.external.launcher import LaunchProgress
from openflowsheet.canonical import document_sha256
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.c1 import COMPONENTS
from openflowsheet.models.c1.boundary import (
    DEFECT_LIMIT,
    EPS_PRESSURE,
    HardDomain,
    data_domain_violations,
    hard_domain_violations,
    project,
    tube_inlet,
)
from openflowsheet.thermo import StreamState
from openflowsheet.thermo.pr_c1 import PrC1Provider

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmarks.m02.g10_adapter_halves import PROBE, VARIANT_ID, _summary  # noqa: E402

F_NOM = 0.007146961299302104
NUDGE = 2.0**-40
CONTEXT = EvaluationContext(model_version="m02-g11", constants_sha256="0" * 64)
NOMINAL_Y = (0.70, 0.235, 0.03, 0.015, 0.02)
CORNER_T = (573.15, 773.15)
CORNER_P = (5e6, 1.5e7)
CORNER_RATIO = (1.0, 4.0)
CORNER_INERT = (0.0, 0.2)
CENTRE = (673.15, 1e7, 2.5, 0.1)
QF5_MULTIPLES = (0.25, 0.5, 2.0, 4.0)
RAMP_MULTIPLES = (0.5, 1.0, 2.0, 4.0, 8.0, 16.0)
TIMING_REPEATS = 5


def composition(ratio: float, inert: float) -> tuple[float, ...]:
    """y with y_NH3 = 0.03, Ar:CH4 = 3:4, H2/N2 = `ratio`, y_Ar + y_CH4 = `inert`."""
    light = 1.0 - 0.03 - inert
    return (
        light * ratio / (1.0 + ratio),
        light / (1.0 + ratio),
        0.03,
        inert * 3.0 / 7.0,
        inert * 4.0 / 7.0,
    )


def inlet_inside(
    temperature: float,
    pressure: float,
    ratio: float,
    inert: float,
    multiple: float,
    domain: HardDomain | None = None,
) -> tuple[StreamState, dict[str, Any]]:
    """The point's process inlet (N_tubes = 1), each coordinate that rounds outside the variant's
    hard domain (or `domain`) moved inward by 2^-40 relative (§8.15); the moves are returned."""
    if domain is None:
        domain = variants.hard_domain(variants.registered_variant(VARIANT_ID))
    flow = F_NOM * multiple
    nudged: dict[str, Any] = {}
    for _ in range(4):
        y = composition(ratio, inert)
        inlet = StreamState(tuple(flow * value for value in y), temperature, pressure)
        bounded = domain if 0.5 <= multiple <= 2.0 else _without_flow_bound(domain)
        violated = hard_domain_violations(inlet, bounded, 1.0)
        if not violated:
            return inlet, nudged
        for message in violated:
            if message.startswith("H2/N2"):
                ratio *= 1.0 + NUDGE if ratio <= domain.h2_n2[0] else 1.0 - NUDGE
                nudged["H2_N2"] = ratio
            elif message.startswith("inert"):
                inert *= 1.0 - NUDGE
                nudged["inert"] = inert
            elif message.startswith("F_ret_in"):
                flow *= 1.0 + NUDGE if multiple <= 0.5 else 1.0 - NUDGE
                nudged["F_ret_in_factor"] = flow / F_NOM
            else:
                raise SystemExit(f"construction error at {temperature, pressure}: {message}")
    raise SystemExit(f"no inside construction at {temperature, pressure, ratio, inert}")


def _without_flow_bound(domain: Any) -> Any:
    from dataclasses import replace

    return replace(domain, tube_flow=None)


def _execution_document(execution: Any) -> dict[str, Any]:
    return {
        "status": execution.status,
        "stage": execution.stage,
        "tube_outlet": execution.tube_outlet,
        "diagnostics": execution.diagnostics,
    }


def _log_tails(base: Path, logs: Any) -> dict[str, str]:
    """The last 600 characters of each log of a failed attempt (the store is a temporary one)."""
    tails: dict[str, str] = {}
    for name, relpath in ((logs or {}).get("relpaths") or {}).items():
        for path in (base / relpath, Path(relpath)):
            if path.is_file():
                tails[name] = path.read_text(encoding="utf-8", errors="replace")[-600:]
                break
    return tails


def run_point(point: dict[str, Any]) -> dict[str, Any]:
    """One point in a fresh store and backend (a worker of the pool)."""
    variant = variants.registered_variant(VARIANT_ID)
    if point["construction"] == "nominal":
        y = NOMINAL_Y
        flow = F_NOM * point["multiple"]
        inlet = StreamState(tuple(flow * v for v in y), point["T_in_K"], point["P_in_Pa"])
        nudged: dict[str, Any] = {}
    else:
        inlet, nudged = inlet_inside(
            point["T_in_K"], point["P_in_Pa"], point["H2_N2"], point["y_inert"], point["multiple"]
        )
    entry: dict[str, Any] = {
        **point,
        "nudged": nudged,
        "inlet_n_mol_s": list(inlet.n),
        "F_ret_in_mol_s": inlet.total_flow,
        "data_domain_violations": list(data_domain_violations(inlet)),
    }
    with tempfile.TemporaryDirectory(prefix=f"m02-g11-{point['label']}-") as scratch:
        work = Path(scratch)
        if point["path"] == "boundary":
            runner = ExperimentRunner(
                ExperimentStore(work / "records", ListArtifactSink()),
                PrC1Provider(),
                CONTEXT,
                job_id=f"m02-g11-{point['label']}",
            )
            outcome = runner.run(variant, inlet, COMPONENTS, 1.0)
            envelope = outcome.envelope
            entry["envelope_status"] = envelope["status"]
            entry["envelope_code"] = envelope["code"]
            entry["accepted"] = envelope["status"] == "ok"
            entry["attempts"] = len(outcome.attempts)
            if outcome.attempts:
                execution = outcome.attempts[-1]["execution"]
                summary = _summary(point["label"], execution, execution.get("timing") or {})
                summary.pop("label")
                summary["execution_status"] = summary.pop("status")
                entry.update(summary)
                entry["exit_code"] = execution.get("exit_code")
                entry["signal"] = execution.get("signal")
                entry["message"] = execution.get("message")
                if execution.get("status") not in ("completed", None):
                    entry["log_tails"] = _log_tails(work / "records", execution.get("logs"))
            if envelope["status"] == "ok":
                entry["discretization_estimate"] = envelope.get("discretization_estimate")
            return entry
        backend = OutOfProcessBackend(variant)
        environment = backend.environment(work / "handshake")
        if environment.failure is not None:
            entry["accepted"] = False
            entry["execution_status"] = environment.failure.status
            entry["message"] = environment.failure.message
            return entry
        tube = tube_inlet(inlet, 1.0, variant.sweep_ratio)
        execution = backend.evaluate(tube, work / "evaluation", LaunchProgress(), None)
        summary = _summary(point["label"], _execution_document(execution), dict(execution.timing))
        summary.pop("label")
        summary["execution_status"] = summary.pop("status")
        entry.update(summary)
        if execution.status != "completed":
            entry["message"] = execution.message
        accepted = execution.status == "completed" and execution.stage is None
        outlet = execution.tube_outlet
        if accepted and outlet is not None:
            entry["boundary_dP_over_P"] = abs(outlet["pressure_drop"]) / inlet.pressure
            entry["projection_defect_rel"] = project(inlet.n, outlet["flows"]).defect_rel
            accepted = (
                entry["boundary_dP_over_P"] <= EPS_PRESSURE
                and entry["projection_defect_rel"] <= DEFECT_LIMIT
            )
        entry["child_accepted"] = execution.status == "completed" and execution.stage is None
        entry["accepted"] = accepted
        return entry


def points() -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for t in CORNER_T:
        for p in CORNER_P:
            for r in CORNER_RATIO:
                for i in CORNER_INERT:
                    found.append(
                        {
                            "group": "Q-F4",
                            "label": f"corner-T{t}-P{p:g}-r{r:g}-i{i:g}",
                            "path": "boundary",
                            "construction": "sweep",
                            "T_in_K": t,
                            "P_in_Pa": p,
                            "H2_N2": r,
                            "y_inert": i,
                            "multiple": 1.0,
                        }
                    )
    t, p, r, i = CENTRE
    centre = {"T_in_K": t, "P_in_Pa": p, "H2_N2": r, "y_inert": i, "construction": "sweep"}
    found.append(
        {"group": "Q-F4", "label": "centre", "path": "boundary", **centre, "multiple": 1.0}
    )
    for multiple in QF5_MULTIPLES:
        path = "boundary" if 0.5 <= multiple <= 2.0 else "direct"
        found.append(
            {"group": "Q-F5", "label": f"centre-x{multiple:g}", "path": path, **centre}
            | {"multiple": multiple}
        )
    for multiple in RAMP_MULTIPLES:
        found.append(
            {
                "group": "dP-ramp",
                "label": f"ramp-x{multiple:g}",
                "path": "direct",
                "construction": "nominal",
                "T_in_K": 673.15,
                "P_in_Pa": 5e6,
                "multiple": multiple,
            }
        )
    return found


def timing() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """(d): five evaluations of the probe's nominal tube through one backend, serial."""
    variant = variants.registered_variant(VARIANT_ID)
    pinned = json.loads(PROBE.read_text(encoding="utf-8"))["pinned"]
    inlet = StreamState(
        tuple(pinned["F_ret_in_mol_s"] * v for v in pinned["y_in"]),
        pinned["T_in_K"],
        pinned["P_in_Pa"],
    )
    tube = tube_inlet(inlet, 1.0, variant.sweep_ratio)
    repeats = []
    with tempfile.TemporaryDirectory(prefix="m02-g11-timing-") as scratch:
        work = Path(scratch)
        backend = OutOfProcessBackend(variant)
        environment = backend.environment(work / "handshake")
        if environment.failure is not None:
            raise SystemExit(f"timing: handshake failed: {environment.failure.message}")
        for number in range(1, TIMING_REPEATS + 1):
            execution = backend.evaluate(tube, work / f"r{number}", LaunchProgress(), None)
            if execution.status != "completed":
                raise SystemExit(f"timing {number}: {execution.status}: {execution.message}")
            wall = execution.timing.get("wall_s")
            startup = execution.timing.get("startup_s")
            repeats.append(
                {
                    "repeat": number,
                    "wall_s": wall,
                    "startup_s": startup,
                    "solve_s": execution.timing.get("solve_s"),
                    "startup_share": None if not wall else startup / wall,
                    "tube_outlet": execution.tube_outlet,
                }
            )
    assert environment.fingerprint is not None
    return repeats, dict(environment.fingerprint)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=6)
    arguments = parser.parse_args()
    variant = variants.registered_variant(VARIANT_ID)
    load_before = os.getloadavg()
    started = time.perf_counter()
    todo = points()
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=arguments.workers, mp_context=context) as pool:
        results = list(pool.map(run_point, todo))
    pool_s = time.perf_counter() - started
    repeats, fingerprint = timing()
    elapsed = time.perf_counter() - started

    sweep = [r for r in results if r["group"] == "Q-F4"]
    qf5 = {r["multiple"]: r for r in results if r["group"] == "Q-F5"}
    ramp = [r for r in results if r["group"] == "dP-ramp"]
    accepted_walls = [r["wall_s"] for r in results if r["accepted"] and r.get("wall_s")]
    slowest = max(accepted_walls)
    exceeding = [r["multiple"] for r in ramp if (r.get("dP_over_P") or 0.0) > EPS_PRESSURE]
    walls = [r["wall_s"] for r in repeats]
    shares = [r["startup_share"] for r in repeats]
    record = {
        "record": "m02-g11-coverage",
        "version": 1,
        "status": "measured",
        "judged": False,
        "specification": (
            "docs/design/M02-pymrm-adapter.md §10.2 G11, §5.2, §10.3; "
            "docs/derivations/M01-spec.md §8.15, Q-F4, Q-F5"
        ),
        "variant": {"variant_id": variant.variant_id, "sha256": variant.sha256},
        "environment": {
            "cpu_model": fingerprint["cpu_model"],
            "machine": fingerprint["machine"],
            "python": fingerprint["python"],
            "fingerprint_sha256": document_sha256(fingerprint),
            "runner_sha256": fingerprint["runner_sha256"],
            "env_id": variant.evaluation["environment"]["env_id"],
        },
        "concurrency": {
            "pool_workers": arguments.workers,
            "cpu_count": os.cpu_count(),
            # The host is shared: wall times scale with its load, the numerics do not.
            "loadavg_before": list(load_before),
            "loadavg_after": list(os.getloadavg()),
        },
        "summary": {
            "a_Q-F4": {
                "points": len(sweep),
                "accepted": sum(1 for r in sweep if r["accepted"]),
                "not_accepted": [
                    {
                        "label": r["label"],
                        "status": r.get("envelope_status"),
                        "code": r.get("envelope_code"),
                        "stage": r.get("stage"),
                    }
                    for r in sweep
                    if not r["accepted"]
                ],
                "element_defect_max": max(
                    (r["element_defect_max"] for r in sweep if r["accepted"]), default=None
                ),
                "dP_over_P_max": max(
                    (r["dP_over_P"] for r in sweep if r["accepted"]), default=None
                ),
                "wall_s_max": max((r.get("wall_s") or 0.0) for r in sweep),
            },
            "b_Q-F5": {
                str(m): {"path": r["path"], "accepted": r["accepted"]} for m, r in qf5.items()
            },
            "b_widen_rule": bool(qf5[0.25]["accepted"] and qf5[4.0]["accepted"]),
            "c_dP_ramp": {
                "dP_over_P": {str(r["multiple"]): r.get("dP_over_P") for r in ramp},
                "accepted": {str(r["multiple"]): r["accepted"] for r in ramp},
                "eps_P": EPS_PRESSURE,
                "first_multiple_above_eps_P": min(exceeding, default=None),
            },
            "d_timing": {
                "wall_s": walls,
                "startup_s": [r["startup_s"] for r in repeats],
                "solve_s": [r["solve_s"] for r in repeats],
                "startup_share_mean": sum(shares) / len(shares),
                "repeats_bitwise_equal": all(
                    r["tube_outlet"] == repeats[0]["tube_outlet"] for r in repeats
                ),
            },
            "timeout_rule": {
                "slowest_accepted_wall_s": slowest,
                "current_timeout_s": variant.execution["timeout_s"],
                "rule_timeout_s": max(120, int(math.ceil(3.0 * slowest / 10.0)) * 10),
            },
        },
        "points": results,
        "timing": repeats,
        "pool_s": round(pool_s, 1),
        "elapsed_s": round(elapsed, 1),
    }
    arguments.out.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", "utf-8")
    print(json.dumps(record["summary"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
