"""M02 G11v3: coverage and timing of the real reactor under v3's child (design note §14.5 D1-D4,
G11v3-1 to -5; §10.3 as amended).

Opt-in evidence, never part of the default gate: it needs the pinned reactor environment (see
``g10_adapter_halves.py``). Its record, ``benchmarks/m02/g11-coverage-v3.json``, is a measurement
(``judged: false``); the G11v3 statements are computed from its own numbers.

**Variant.** The provisional evidence variant of D4 (``--variant-file``, never registered): v3's
child and profile ``M01-S123-v2``, v2's boundary block (so every point below is inside its hard
domain and goes through the boundary), a 600 s timeout. N_tubes = 1 unless stated.

**Points** (each in a fresh store and backend, in a process pool):

- *old corners* — G11's 16 Q-F4 corners (573.15/773.15 K), built as G11 built them (G11v3-3);
  one ``nonfinite`` corner is then asked again in its own store: a cache hit (G11v3-3);
- *centre* — G11's centre (673.15 K, 10⁷ Pa, 2.5, 0.1) at 1, 0.5 and 2 × F_nom through the
  boundary, and 0.25 and 4 × directly (Q-F5, for information);
- *ΔP ramp* — the nominal composition, 673.15 K, 5 MPa, 0.5-16 × F_nom, directly;
- *boxes* — B1, B2 and B3 (D3): each box's 16 corners (T × P × H₂/N₂ × inerts {0, 0.2}, nudged
  inward into the *box* by at most 2⁻⁴⁰), its centre at 1, 0.5 and 2 × F_nom, and for B1 M05's
  two edge points (643.15 and 733.15 K at 10⁷ Pa, G12's reactor-inlet n over 1000 tubes); all
  through the boundary. B2's centre is G11's centre and is evaluated once per run.

Every point runs in each of ``--runs`` full runs (two); then five timing repeats of the probe's
nominal tube through one backend. The box selection (D3): the first of B1, B2, B3 whose
registered points all end ``ok`` in every run. The timeout rule (D4): max(120, 3 × the slowest
``wall_s`` over every evaluation whose inlet lies in the selected box, any outcome, all runs),
rounded up to 10 s.

Usage (from a checkout)::

    PYTHONPATH=src python benchmarks/m02/g11_coverage_v3.py \\
        --variant-file benchmarks/m02/variant-v3-provisional.json \\
        --compare benchmarks/m02/g11-coverage.json --out benchmarks/m02/g11-coverage-v3.json
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
from dataclasses import replace
from pathlib import Path
from typing import Any

from openflowsheet.adapters import variants
from openflowsheet.adapters.experiments.backends import OutOfProcessBackend
from openflowsheet.adapters.experiments.runner import ExperimentRunner
from openflowsheet.adapters.experiments.store import ExperimentStore, ListArtifactSink
from openflowsheet.adapters.external.launcher import LaunchProgress
from openflowsheet.canonical import document_sha256, file_sha256
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
from benchmarks.m02.g10_adapter_halves import (  # noqa: E402
    PROBE,
    _summary,
    load_variant,
    outlet_bits,
)
from benchmarks.m02.g11_coverage import (  # noqa: E402
    CENTRE,
    CORNER_INERT,
    CORNER_P,
    CORNER_RATIO,
    CORNER_T,
    F_NOM,
    NOMINAL_Y,
    RAMP_MULTIPLES,
    _log_tails,
    inlet_inside,
)

CONTEXT = EvaluationContext(model_version="m02-g11v3", constants_sha256="0" * 64)
TIMING_REPEATS = 5
#: D3's candidate boxes: T_in (K), P_in (Pa), H2/N2, and the centre (T, P, H2/N2, y_inert).
BOXES: dict[str, dict[str, Any]] = {
    "B1": {"T": (643.15, 733.15), "P": (5e6, 1.5e7), "r": (1.0, 4.0), "c": (688.15, 1e7, 2.5, 0.1)},
    "B2": {"T": (653.15, 693.15), "P": (5e6, 1.5e7), "r": (1.0, 4.0), "c": (673.15, 1e7, 2.5, 0.1)},
    "B3": {
        "T": (653.15, 693.15),
        "P": (7.5e6, 1.25e7),
        "r": (2.0, 4.0),
        "c": (673.15, 1e7, 3, 0.1),
    },
}
#: D3: G12's reactor-inlet n (mol/s, over 1000 tubes), M05's two edge points at 10^7 Pa.
M05_N = (
    4.033380311567345,
    1.3444601038557868,
    0.16913270331830627,
    0.09999999999999991,
    0.14999999999999986,
)
M05_TUBES = 1000.0
M05_T = (643.15, 733.15)
#: G11v3-1 and G11v3-2's points (labels of this script and of G11's record alike).
G11V3_1 = ("centre-x0.5", "ramp-x0.5", "ramp-x2")
G11V3_2 = ("centre", "centre-x2", "centre-x4", "ramp-x1", "ramp-x4", "ramp-x8", "ramp-x16")

_VARIANT: variants.Variant | None = None


def _initialise(path: str) -> None:
    global _VARIANT
    _VARIANT = load_variant(Path(path))


def box_domain(variant: variants.Variant, box: dict[str, Any]) -> HardDomain:
    """The variant's hard domain with the box's T, P and H2/N2 (inerts and flow bound kept)."""
    return replace(
        variants.hard_domain(variant), temperature_k=box["T"], pressure_pa=box["P"], h2_n2=box["r"]
    )


def _point(label: str, group: str, path: str, **fields: Any) -> dict[str, Any]:
    return {"label": label, "group": group, "path": path, "n_tubes": 1.0, **fields}


def points() -> list[dict[str, Any]]:
    """Every point once, in a fixed order; box membership is `boxes` (a list of names)."""
    found: dict[str, dict[str, Any]] = {}

    def add(point: dict[str, Any], box: str | None = None) -> None:
        entry = found.setdefault(point["label"], {**point, "boxes": []})
        if box is not None:
            entry["boxes"].append(box)

    for t in CORNER_T:
        for p in CORNER_P:
            for r in CORNER_RATIO:
                for i in CORNER_INERT:
                    label = f"corner-T{t}-P{p:g}-r{r:g}-i{i:g}"
                    sweep = {"T_in_K": t, "P_in_Pa": p, "H2_N2": r, "y_inert": i}
                    add(_point(label, "old-corner", "boundary", construction="sweep", **sweep))
    t, p, r, i = CENTRE
    centre = {"T_in_K": t, "P_in_Pa": p, "H2_N2": r, "y_inert": i, "construction": "sweep"}
    for multiple in (1.0, 0.5, 2.0, 0.25, 4.0):
        label = "centre" if multiple == 1.0 else f"centre-x{multiple:g}"
        path = "boundary" if 0.5 <= multiple <= 2.0 else "direct"
        add(_point(label, "centre", path, multiple=multiple, **centre))
    for multiple in RAMP_MULTIPLES:
        nominal = {"T_in_K": 673.15, "P_in_Pa": 5e6, "construction": "nominal"}
        add(_point(f"ramp-x{multiple:g}", "dP-ramp", "direct", multiple=multiple, **nominal))
    for name, box in BOXES.items():
        for t in box["T"]:
            for p in box["P"]:
                for r in box["r"]:
                    for i in CORNER_INERT:
                        label = f"{name}-corner-T{t}-P{p:g}-r{r:g}-i{i:g}"
                        sweep = {"T_in_K": t, "P_in_Pa": p, "H2_N2": r, "y_inert": i}
                        add(
                            _point(label, "box", "boundary", construction="box", box=name, **sweep),
                            name,
                        )
        t, p, r, i = box["c"]
        middle = {"T_in_K": t, "P_in_Pa": p, "H2_N2": r, "y_inert": i}
        for multiple in (1.0, 0.5, 2.0):
            suffix = "" if multiple == 1.0 else f"-x{multiple:g}"
            if (t, p, r, i) == CENTRE:
                label = f"centre{suffix}"  # B2's centre is G11's
            else:
                label = f"{name}-centre{suffix}"
            fields = {"construction": "box", "box": name, "multiple": multiple, **middle}
            add(_point(label, "box", "boundary", **fields), name)
    for t in M05_T:
        fields = {"T_in_K": t, "P_in_Pa": 1e7, "construction": "m05", "n_tubes": M05_TUBES}
        add(_point(f"B1-m05-T{t}", "box", "boundary", **fields), "B1")
    return list(found.values())


def build_inlet(variant: variants.Variant, point: dict[str, Any]) -> tuple[StreamState, Any]:
    construction = point["construction"]
    if construction == "nominal":
        flow = F_NOM * point["multiple"]
        return StreamState(
            tuple(flow * v for v in NOMINAL_Y), point["T_in_K"], point["P_in_Pa"]
        ), {}
    if construction == "m05":
        return StreamState(M05_N, point["T_in_K"], point["P_in_Pa"]), {}
    domain = None
    if construction == "box":
        domain = box_domain(variant, BOXES[point["box"]])
    else:
        domain = variants.hard_domain(variant)
    return inlet_inside(
        point["T_in_K"],
        point["P_in_Pa"],
        point["H2_N2"],
        point["y_inert"],
        point.get("multiple", 1.0),
        domain,
    )


def run_point(point: dict[str, Any]) -> dict[str, Any]:
    """One point in a fresh store and backend (a worker of the pool)."""
    variant = _VARIANT
    assert variant is not None
    inlet, nudged = build_inlet(variant, point)
    n_tubes = point["n_tubes"]
    entry: dict[str, Any] = {
        **point,
        "nudged": nudged,
        "inlet_n_mol_s": list(inlet.n),
        "T_in_K": inlet.temperature,
        "P_in_Pa": inlet.pressure,
        "F_ret_in_mol_s": inlet.total_flow / n_tubes,
        "data_domain_violations": list(data_domain_violations(inlet)),
        "in_box": [
            name
            for name, box in BOXES.items()
            if not hard_domain_violations(inlet, box_domain(variant, box), n_tubes)
        ],
    }
    with tempfile.TemporaryDirectory(prefix=f"m02-g11v3-{point['label']}-") as scratch:
        work = Path(scratch)
        if point["path"] == "boundary":
            runner = ExperimentRunner(
                ExperimentStore(work / "records", ListArtifactSink()),
                PrC1Provider(),
                CONTEXT,
                job_id=f"m02-g11v3-{point['label']}",
            )
            outcome = runner.run(variant, inlet, COMPONENTS, n_tubes)
            envelope = outcome.envelope
            entry["envelope_status"] = envelope["status"]
            entry["envelope_code"] = envelope["code"]
            entry["envelope_defect_rel"] = envelope.get("defect_rel")
            entry["accepted"] = envelope["status"] == "ok"
            entry["attempts"] = len(outcome.attempts)
            execution: dict[str, Any] = {}
            if outcome.attempts:
                execution = dict(outcome.attempts[-1]["execution"])
                summary = _summary(point["label"], execution, execution.get("timing") or {})
                summary.pop("label")
                summary["execution_status"] = summary.pop("status")
                entry.update(summary)
                entry["exit_code"] = execution.get("exit_code")
                entry["message"] = execution.get("message")
                if execution.get("status") not in ("completed", None):
                    entry["log_tails"] = _log_tails(work / "records", execution.get("logs"))
            if entry.get("tube_outlet") is not None:
                raw = [n_tubes * value for value in entry["tube_outlet"]["flows"]]
                entry["projection_defect_rel"] = project(inlet.n, raw).defect_rel
            if point.get("repeat_check"):
                again = runner.run(variant, inlet, COMPONENTS, n_tubes)
                entry["repeat"] = {
                    "cache_hit": again.cache_hit,
                    "attempts": len(again.attempts),
                    "envelope_code": again.envelope["code"],
                }
            return entry
        backend = OutOfProcessBackend(variant)
        environment = backend.environment(work / "handshake")
        if environment.failure is not None:
            entry["accepted"] = False
            entry["execution_status"] = environment.failure.status
            entry["message"] = environment.failure.message
            return entry
        tube = tube_inlet(inlet, n_tubes, variant.sweep_ratio)
        direct = backend.evaluate(tube, work / "evaluation", LaunchProgress(), None)
        document = {
            "status": direct.status,
            "stage": direct.stage,
            "tube_outlet": direct.tube_outlet,
            "diagnostics": direct.diagnostics,
        }
        summary = _summary(point["label"], document, dict(direct.timing))
        summary.pop("label")
        summary["execution_status"] = summary.pop("status")
        entry.update(summary)
        if direct.status != "completed":
            entry["message"] = direct.message
        accepted = direct.status == "completed" and direct.stage is None
        outlet = direct.tube_outlet
        if accepted and outlet is not None:
            entry["boundary_dP_over_P"] = abs(outlet["pressure_drop"]) / inlet.pressure
            raw = [n_tubes * value for value in outlet["flows"]]
            entry["projection_defect_rel"] = project(inlet.n, raw).defect_rel
            accepted = (
                entry["boundary_dP_over_P"] <= EPS_PRESSURE
                and entry["projection_defect_rel"] <= DEFECT_LIMIT
            )
        entry["child_accepted"] = direct.status == "completed" and direct.stage is None
        entry["accepted"] = accepted
        return entry


def timing(variant: variants.Variant) -> list[dict[str, Any]]:
    """Five evaluations of the probe's nominal tube through one backend, serial."""
    pinned = json.loads(PROBE.read_text(encoding="utf-8"))["pinned"]
    inlet = StreamState(
        tuple(pinned["F_ret_in_mol_s"] * v for v in pinned["y_in"]),
        pinned["T_in_K"],
        pinned["P_in_Pa"],
    )
    tube = tube_inlet(inlet, 1.0, variant.sweep_ratio)
    repeats = []
    with tempfile.TemporaryDirectory(prefix="m02-g11v3-timing-") as scratch:
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
                    "in_box": [
                        name
                        for name, box in BOXES.items()
                        if not hard_domain_violations(inlet, box_domain(variant, box), 1.0)
                    ],
                    "round2": ((execution.diagnostics or {}).get("stages") or {})
                    .get("S3", {})
                    .get("round2"),
                }
            )
    return repeats


def _same(first: dict[str, Any], second: dict[str, Any]) -> bool:
    keys = ("envelope_status", "envelope_code", "execution_status", "stage", "accepted")
    return all(first.get(key) == second.get(key) for key in keys) and outlet_bits(
        first.get("tube_outlet")
    ) == outlet_bits(second.get("tube_outlet"))


def summarise(
    runs: list[list[dict[str, Any]]], repeats: list[dict[str, Any]], previous: dict[str, Any]
) -> dict[str, Any]:
    first = {point["label"]: point for point in runs[0]}
    before = {point["label"]: point for point in previous["points"]}
    g1 = {}
    for label in G11V3_1:
        point = first[label]
        g1[label] = {
            "round2": point.get("round2"),
            "ok": point["accepted"],
            "envelope_code": point.get("envelope_code"),
            "projection_defect_rel": point.get("projection_defect_rel"),
            "defect_round1": point.get("defect_round1"),
            "v2_element_defect_max": before[label]["element_defect_max"],
            "defect_round1_bitwise_v2": point.get("defect_round1")
            == before[label]["element_defect_max"],
        }
    g1_met = all(
        entry["round2"] is not None
        and entry["round2"]["converged"]
        and entry["ok"]
        and entry["projection_defect_rel"] is not None
        and entry["projection_defect_rel"] <= DEFECT_LIMIT
        and entry["defect_round1_bitwise_v2"]
        for entry in g1.values()
    )
    g2 = {
        label: {
            "round2_ran": first[label].get("round2") is not None,
            "tube_outlet_bitwise_v2": outlet_bits(first[label].get("tube_outlet"))
            == outlet_bits(before[label].get("tube_outlet")),
        }
        for label in G11V3_2
    }
    g2_met = all(not e["round2_ran"] and e["tube_outlet_bitwise_v2"] for e in g2.values())
    corners = [point for point in runs[0] if point["group"] == "old-corner"]
    g3 = {
        point["label"]: {
            "envelope_status": point.get("envelope_status"),
            "envelope_code": point.get("envelope_code"),
            "stage": point.get("stage"),
            "nonfinite_paths": point.get("nonfinite_paths"),
        }
        for point in corners
    }
    repeat = next((point["repeat"] for point in corners if "repeat" in point), None)
    expected_nonfinite = [
        point["label"] for point in corners if point["T_in_K"] == 773.15 and point["y_inert"] == 0.0
    ]
    g3_met = all(entry["envelope_status"] != "error" for entry in g3.values())
    boxes = {}
    for name in BOXES:
        members = [point["label"] for point in runs[0] if name in point["boxes"]]
        per_run = [
            {
                "ok": sum(1 for p in run if name in p["boxes"] and p["accepted"]),
                "not_ok": [
                    {
                        "label": p["label"],
                        "code": p.get("envelope_code"),
                        "stage": p.get("stage"),
                    }
                    for p in run
                    if name in p["boxes"] and not p["accepted"]
                ],
            }
            for run in runs
        ]
        walls = [
            p["wall_s"] for run in runs for p in run if name in p["in_box"] and p.get("wall_s")
        ]
        walls += [r["wall_s"] for r in repeats if name in r["in_box"] and r.get("wall_s")]
        slowest = max(walls)
        boxes[name] = {
            "points": len(members),
            "qualifies": all(not entry["not_ok"] for entry in per_run),
            "runs": per_run,
            "in_box_evaluations": len(walls),
            "slowest_in_box_wall_s": slowest,
            "timeout_rule_s": max(120, int(math.ceil(3.0 * slowest / 10.0)) * 10),
        }
    selected = next((name for name in BOXES if boxes[name]["qualifies"]), None)
    equal = {
        point["label"]: all(
            _same(point, {p["label"]: p for p in run}[point["label"]]) for run in runs[1:]
        )
        for point in runs[0]
    }
    ramp = [point for point in runs[0] if point["group"] == "dP-ramp"]
    exceeding = [p["multiple"] for p in ramp if (p.get("dP_over_P") or 0.0) > EPS_PRESSURE]
    inside = [p["dP_over_P"] for p in ramp if 0.5 <= p["multiple"] <= 2.0 and p.get("dP_over_P")]
    walls = [r["wall_s"] for r in repeats]
    return {
        "G11v3-1": {"points": g1, "met": g1_met},
        "G11v3-2": {"points": g2, "met": g2_met},
        "G11v3-3": {
            "corners": g3,
            "expected_nonfinite": expected_nonfinite,
            "nonfinite_as_expected": all(
                g3[label]["envelope_code"] == "reactor_not_accepted(nonfinite)"
                for label in expected_nonfinite
            ),
            "repeat": repeat,
            "met": g3_met
            and repeat is not None
            and repeat["cache_hit"]
            and repeat["attempts"] == 0,
        },
        "G11v3-4": {"boxes": boxes, "selected": selected},
        "G11v3-5": {
            "runs": len(runs),
            "points_per_run": len(runs[0]),
            "all_equal": all(equal.values()),
            "unequal": [label for label, same in equal.items() if not same],
            "dP_ramp": {
                "dP_over_P": {str(p["multiple"]): p.get("dP_over_P") for p in ramp},
                "eps_P": EPS_PRESSURE,
                "first_multiple_above_eps_P": min(exceeding, default=None),
                "max_dP_over_P_inside_flow_bound": max(inside, default=None),
            },
            "timing": {
                "wall_s": walls,
                "startup_s": [r["startup_s"] for r in repeats],
                "solve_s": [r["solve_s"] for r in repeats],
                "startup_share_mean": sum(r["startup_share"] for r in repeats) / len(repeats),
                "repeats_bitwise_equal": all(
                    r["tube_outlet"] == repeats[0]["tube_outlet"] for r in repeats
                ),
                "round2_ran": [r["repeat"] for r in repeats if r["round2"] is not None],
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant-file", type=Path, required=True)
    parser.add_argument("--compare", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--runs", type=int, default=2)
    arguments = parser.parse_args()
    variant = load_variant(arguments.variant_file)
    previous = json.loads(arguments.compare.read_text(encoding="utf-8"))
    todo = points()
    repeat = next(
        p
        for p in todo
        if p["group"] == "old-corner" and p["T_in_K"] == 773.15 and p["y_inert"] == 0
    )
    repeat["repeat_check"] = True
    context = multiprocessing.get_context("spawn")
    started = time.perf_counter()
    loads = [list(os.getloadavg())]
    runs: list[list[dict[str, Any]]] = []
    run_s = []
    for _ in range(arguments.runs):
        begun = time.perf_counter()
        with ProcessPoolExecutor(
            max_workers=arguments.workers,
            mp_context=context,
            initializer=_initialise,
            initargs=(str(arguments.variant_file),),
        ) as pool:
            runs.append(list(pool.map(run_point, todo)))
        run_s.append(round(time.perf_counter() - begun, 1))
        loads.append(list(os.getloadavg()))
    raw = arguments.out.with_suffix(".runs.json")
    raw.write_text(
        json.dumps(runs, ensure_ascii=False) + "\n", "utf-8"
    )  # kept if summarising fails
    repeats = timing(variant)
    loads.append(list(os.getloadavg()))
    fingerprint_runner = file_sha256(
        Path(__file__).resolve().parents[2] / "src/openflowsheet/adapters/pymrm/child.py"
    )
    record: dict[str, Any] = {
        "record": "m02-g11-coverage-v3",
        "version": 1,
        "status": "measured",
        "judged": False,
        "specification": "docs/design/M02-pymrm-adapter.md §14.5 D1-D4, G11v3-1 to -5; §10.3",
        "variant": {
            "variant_id": variant.variant_id,
            "sha256": variant.sha256,
            "registered": False,
            "file": arguments.variant_file.as_posix(),
            "timeout_s": variant.execution["timeout_s"],
        },
        "compared": {
            "record": arguments.compare.as_posix(),
            "sha256": file_sha256(arguments.compare),
            "variant": previous["variant"],
        },
        "environment": {
            "runner_sha256": fingerprint_runner,
            "env_id": variant.evaluation["environment"]["env_id"],
            "cpu_count": os.cpu_count(),
            "variant_document_sha256": document_sha256(dict(variant.document)),
        },
        "concurrency": {
            "pool_workers": arguments.workers,
            # The host is shared: wall times scale with its load, the numerics do not (D4).
            "loadavg": loads,
            "run_s": run_s,
        },
        "boxes": {name: {k: list(v) for k, v in box.items()} for name, box in BOXES.items()},
        "summary": summarise(runs, repeats, previous),
        "points": runs[0],
        "runs": [
            {
                p["label"]: {
                    "envelope_status": p.get("envelope_status"),
                    "envelope_code": p.get("envelope_code"),
                    "stage": p.get("stage"),
                    "accepted": p["accepted"],
                    "wall_s": p.get("wall_s"),
                    "tube_outlet": p.get("tube_outlet"),
                }
                for p in run
            }
            for run in runs
        ],
        "timing": repeats,
        "elapsed_s": round(time.perf_counter() - started, 1),
    }
    arguments.out.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", "utf-8")
    summary = record["summary"]
    print(
        json.dumps(
            {
                "G11v3-1": summary["G11v3-1"]["met"],
                "G11v3-2": summary["G11v3-2"]["met"],
                "G11v3-3": summary["G11v3-3"]["met"],
                "selected": summary["G11v3-4"]["selected"],
                "qualifies": {k: v["qualifies"] for k, v in summary["G11v3-4"]["boxes"].items()},
                "equal": summary["G11v3-5"]["all_equal"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
