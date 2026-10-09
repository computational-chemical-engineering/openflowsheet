"""M02 G11v3: coverage and timing of the real reactor under v3's child (design note §14.5 D1-D4 as
amended by §14.6 E1-E4; G11v3-1 to -5 and -8 as §14.6 numbers them; §10.3).

Opt-in evidence, never part of the default gate: it needs the pinned reactor environment (see
``g10_adapter_halves.py``). Its record, ``benchmarks/m02/g11-coverage-v3.json``, is a measurement
(``judged: false``); the G11v3 statements are computed from its own numbers.

**Variant.** The provisional evidence variant of D4 (``--variant-file``, never registered): v3's
child and profile ``M01-S123-v2``, v2's boundary block (so every point below is inside its hard
domain and goes through the boundary), a 600 s timeout. N_tubes = 1 unless stated.

**Points** (each in a fresh store and backend, in a process pool):

- *old corners* — G11's 16 Q-F4 corners (573.15/773.15 K), built as G11 built them (G11v3-3);
  one refused corner is then asked again in its own store: a cache hit (G11v3-3);
- *centre* — G11's centre (673.15 K, 10⁷ Pa, 2.5, 0.1) at 1, 0.5 and 2 × F_nom through the
  boundary, and 0.25 and 4 × directly (Q-F5, for information);
- *ΔP ramp* — the nominal composition, 673.15 K, 5 MPa, 0.5-16 × F_nom, directly;
- *rungs* — V1, V2 and V3 (§14.6 E3): each rung's 16 corners (T × P × H₂/N₂ × inerts
  {0.02, 0.2}, nudged inward into the *rung*, floor included, by at most 2⁻⁴⁰), its centre at 1,
  0.5 and 2 × F_nom, and M05's two edge points (653.15 and 693.15 K at 10⁷ Pa, G12's
  reactor-inlet n over 1000 tubes); all through the boundary. V1's centre is G11's, and V2 and V3
  share B3's: each is evaluated once per run;
- *G11v3-8* — B2's 8 zero-inert corners (B2 as §14.5 registered it, nudged into B2), directly;
- *G11v3-5* — M05's 643.15 K point (D78's ``B1-m05-T643.15``) through the boundary; with the old
  573.15 K corners and G11v3-8's two 653.15 K, 15 MPa corners these are the points that ended
  ``S1`` under D78 (``--d78``), compared with that record.

Every point runs in each of ``--runs`` full runs (two); then five timing repeats of the probe's
nominal tube through one backend. The rung selection (E3): the first of V1, V2, V3 whose 21
registered points all end ``ok`` through the boundary in every run. The timeout rule (§14.5 D4,
E4): max(120, 3 × the slowest ``wall_s`` over every completed evaluation whose inlet lies in the
selected rung, floor included, all runs), rounded up to 10 s.

Usage (from a checkout)::

    PYTHONPATH=src python benchmarks/m02/g11_coverage_v3.py \\
        --variant-file benchmarks/m02/variant-v3-provisional.json \\
        --compare benchmarks/m02/g11-coverage.json \\
        --d78 evidence/M02/wo12a-experiment/artifacts/g11-exp.json \\
        --out benchmarks/m02/g11-coverage-v3.json
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
    NUDGE,
    RAMP_MULTIPLES,
    _log_tails,
    inlet_inside,
)

CONTEXT = EvaluationContext(model_version="m02-g11v3", constants_sha256="0" * 64)
TIMING_REPEATS = 5
#: §14.6 E3's rungs, tried in this order: T_in (K), P_in (Pa), H2/N2, y_inert = y_Ar + y_CH4 (the
#: floor `inert_min` and the corners' two values), and the centre (T, P, H2/N2, y_inert).
RUNGS: dict[str, dict[str, Any]] = {
    "V1": {
        "T": (653.15, 693.15),
        "P": (5e6, 1.5e7),
        "r": (1.0, 4.0),
        "i": (0.02, 0.2),
        "c": (673.15, 1e7, 2.5, 0.1),
    },
    "V2": {
        "T": (653.15, 693.15),
        "P": (7.5e6, 1.25e7),
        "r": (2.0, 4.0),
        "i": (0.02, 0.2),
        "c": (673.15, 1e7, 3.0, 0.1),
    },
    "V3": {
        "T": (653.15, 693.15),
        "P": (9e6, 1.1e7),
        "r": (2.5, 3.5),
        "i": (0.02, 0.2),
        "c": (673.15, 1e7, 3.0, 0.1),
    },
}
#: §14.5 D3's B2, whose 8 zero-inert corners G11v3-8 evaluates directly.
B2: dict[str, Any] = {"T": (653.15, 693.15), "P": (5e6, 1.5e7), "r": (1.0, 4.0), "i": (0.0, 0.2)}
#: The domains a `construction: box` point is nudged into, by name.
DOMAINS: dict[str, dict[str, Any]] = {**RUNGS, "B2": B2}
#: D3: G12's reactor-inlet n (mol/s, over 1000 tubes), M05's two edge points at 10^7 Pa.
M05_N = (
    4.033380311567345,
    1.3444601038557868,
    0.16913270331830627,
    0.09999999999999991,
    0.14999999999999986,
)
M05_TUBES = 1000.0
M05_T = (653.15, 693.15)
#: G11v3-5: M05's 643.15 K point, which ended `S1` under D78 (that record's label).
M05_S1_LABEL = "B1-m05-T643.15"
#: G11v3-3: the corner a repeat asks again (refused under D78 at `certificate`).
REPEAT_LABEL = "corner-T773.15-P5e+06-r1-i0"
#: E2's absent-species diagnostics, carried into the record.
E2_KEYS = ("absent_species", "absent_species_max_abs_flow_mol_s")
#: G11v3-1 and G11v3-2's points (labels of this script and of G11's record alike).
G11V3_1 = ("centre-x0.5", "ramp-x0.5", "ramp-x2")
G11V3_2 = ("centre", "centre-x2", "centre-x4", "ramp-x1", "ramp-x4", "ramp-x8", "ramp-x16")

_VARIANT: variants.Variant | None = None


def _initialise(path: str) -> None:
    global _VARIANT
    _VARIANT = load_variant(Path(path))


def box_domain(variant: variants.Variant, box: dict[str, Any]) -> HardDomain:
    """The variant's hard domain with the box's T, P and H2/N2 (inerts and flow bound kept; the
    floor is `below_floor`'s, which `HardDomain` does not hold before WO-12b)."""
    return replace(
        variants.hard_domain(variant), temperature_k=box["T"], pressure_pa=box["P"], h2_n2=box["r"]
    )


def below_floor(inlet: StreamState, box: dict[str, Any]) -> bool:
    """§14.6 E3's floor y_Ar + y_CH4 ≥ inert_min, as n_Ar + n_CH4 ≥ inert_min Σn."""
    floor = box["i"][0]
    return not (inlet.n[3] + inlet.n[4]) >= floor * inlet.total_flow


def in_rungs(variant: variants.Variant, inlet: StreamState, n_tubes: float) -> list[str]:
    return [
        name
        for name, rung in RUNGS.items()
        if not hard_domain_violations(inlet, box_domain(variant, rung), n_tubes)
        and not below_floor(inlet, rung)
    ]


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
    for name, rung in RUNGS.items():
        for t in rung["T"]:
            for p in rung["P"]:
                for r in rung["r"]:
                    for i in rung["i"]:
                        label = f"{name}-corner-T{t}-P{p:g}-r{r:g}-i{i:g}"
                        sweep = {"T_in_K": t, "P_in_Pa": p, "H2_N2": r, "y_inert": i}
                        add(
                            _point(
                                label, "rung", "boundary", construction="box", box=name, **sweep
                            ),
                            name,
                        )
        t, p, r, i = rung["c"]
        middle = {"T_in_K": t, "P_in_Pa": p, "H2_N2": r, "y_inert": i}
        for multiple in (1.0, 0.5, 2.0):
            suffix = "" if multiple == 1.0 else f"-x{multiple:g}"
            if (t, p, r, i) == CENTRE:
                label = f"centre{suffix}"  # V1's centre is G11's
            else:
                label = f"B3-centre{suffix}"  # V2's and V3's are B3's (D78's label)
            fields = {"construction": "box", "box": name, "multiple": multiple, **middle}
            add(_point(label, "rung", "boundary", **fields), name)
        for t in M05_T:
            fields = {"T_in_K": t, "P_in_Pa": 1e7, "construction": "m05", "n_tubes": M05_TUBES}
            add(_point(f"m05-T{t}", "rung", "boundary", **fields), name)
    for t in B2["T"]:
        for p in B2["P"]:
            for r in B2["r"]:
                label = f"B2-corner-T{t}-P{p:g}-r{r:g}-i0"  # D78's labels
                sweep = {"T_in_K": t, "P_in_Pa": p, "H2_N2": r, "y_inert": 0.0}
                add(_point(label, "G11v3-8", "direct", construction="box", box="B2", **sweep))
    fields = {"T_in_K": 643.15, "P_in_Pa": 1e7, "construction": "m05", "n_tubes": M05_TUBES}
    add(_point(M05_S1_LABEL, "G11v3-5", "boundary", **fields))
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
    if construction != "box":
        return inlet_inside(
            point["T_in_K"],
            point["P_in_Pa"],
            point["H2_N2"],
            point["y_inert"],
            point.get("multiple", 1.0),
            variants.hard_domain(variant),
        )
    box = DOMAINS[point["box"]]
    inert = point["y_inert"]
    for _ in range(4):
        inlet, nudged = inlet_inside(
            point["T_in_K"],
            point["P_in_Pa"],
            point["H2_N2"],
            inert,
            point.get("multiple", 1.0),
            box_domain(variant, box),
        )
        if inert != point["y_inert"]:
            nudged = {**nudged, "inert_floor": inert}
        if not below_floor(inlet, box):
            return inlet, nudged
        inert *= 1.0 + NUDGE  # onto the floor from below (inlet_inside nudges only downward)
    raise SystemExit(f"no construction above the floor at {point['label']}")


def e2_fields(diagnostics: Any) -> dict[str, Any]:
    """§14.6 E2's diagnostics of one evaluation: the absent species, the largest |flow| they carry,
    and the elements `element_defect_rel` holds (None where the child wrote no outlet)."""
    diagnostics = diagnostics or {}
    defects = diagnostics.get("element_defect_rel")
    return {
        **{key: diagnostics.get(key) for key in E2_KEYS},
        "element_defect_keys": None if defects is None else list(defects),
    }


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
        "in_box": in_rungs(variant, inlet, n_tubes),
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
                entry.update(e2_fields(execution.get("diagnostics")))
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
        entry.update(e2_fields(direct.diagnostics))
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
                    "in_box": in_rungs(variant, inlet, 1.0),
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
    runs: list[list[dict[str, Any]]],
    repeats: list[dict[str, Any]],
    previous: dict[str, Any],
    d78: dict[str, Any],
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
    by_run = [{point["label"]: point for point in run} for run in runs]
    then = {point["label"]: point for point in d78["points"]}
    corners = [point for point in runs[0] if point["group"] == "old-corner"]
    g3 = {
        point["label"]: {
            "stages": [run[point["label"]].get("stage") for run in by_run],
            "envelope_status": point.get("envelope_status"),
            "envelope_code": point.get("envelope_code"),
            "nonfinite_paths": point.get("nonfinite_paths"),
            "d78_stage": then[point["label"]].get("stage"),
        }
        for point in corners
    }
    repeat = next((point["repeat"] for point in corners if "repeat" in point), None)
    # E2's diagnosis: D78's three 773.15 K zero-inert `nonpositive_flow` corners must move.
    was_nonpositive = [
        label
        for label, entry in g3.items()
        if label.startswith("corner-T773.15") and entry["d78_stage"] == "nonpositive_flow"
    ]
    still_nonpositive = [
        label for label in was_nonpositive if "nonpositive_flow" in g3[label]["stages"]
    ]
    no_error = all(run[label].get("envelope_status") != "error" for run in by_run for label in g3)
    certificate_corner = all(stage == "certificate" for stage in g3[REPEAT_LABEL]["stages"])
    g3_met = (
        no_error
        and len(was_nonpositive) == 3
        and not still_nonpositive
        and certificate_corner
        and repeat is not None
        and repeat["cache_hit"]
        and repeat["attempts"] == 0
    )
    boxes = {}
    for name in RUNGS:
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
            p["wall_s"]
            for run in runs
            for p in run
            if name in p["in_box"] and p.get("execution_status") == "completed" and p.get("wall_s")
        ]
        walls += [r["wall_s"] for r in repeats if name in r["in_box"] and r.get("wall_s")]
        slowest = max(walls)
        boxes[name] = {
            "points": len(members),
            "qualifies": len(members) == 21 and all(not entry["not_ok"] for entry in per_run),
            "runs": per_run,
            "in_rung_evaluations": len(walls),
            "slowest_in_rung_wall_s": slowest,
            "timeout_rule_s": max(120, int(math.ceil(3.0 * slowest / 10.0)) * 10),
        }
    selected = next((name for name in RUNGS if boxes[name]["qualifies"]), None)
    # G11v3-5's clause: the points that ended `S1` under D78 end `S1` in every run, at D78's steps.
    s1_labels = [
        label
        for label, point in then.items()
        if point.get("stage") == "S1"
        and (
            label.startswith("corner-T573.15")
            or label.startswith("B2-corner-T653.15-P1.5e+07")
            or label == M05_S1_LABEL
        )
    ]
    s1: dict[str, dict[str, Any]] = {
        label: {
            "stages": [run[label].get("stage") for run in by_run],
            "S1_steps": [(run[label].get("stage_steps") or {}).get("S1") for run in by_run],
            "d78_S1_steps": (then[label].get("stage_steps") or {}).get("S1"),
        }
        for label in s1_labels
    }
    s1_met = len(s1_labels) == 10 and all(
        all(stage == "S1" for stage in entry["stages"])
        and all(steps == entry["d78_S1_steps"] for steps in entry["S1_steps"])
        for entry in s1.values()
    )
    # G11v3-8: B2's zero-inert corners, directly.
    g8_points = [point["label"] for point in runs[0] if point["group"] == "G11v3-8"]
    g8 = {}
    for label in g8_points:
        entries = [run[label] for run in by_run]
        passed_s1 = [e for e in entries if (e.get("stages_accepted") or {}).get("S1")]
        g8[label] = {
            "d78_stage": then[label].get("stage"),
            "stages": [e.get("stage") for e in entries],
            "passed_S1": bool(passed_s1),
            "absent_species": [e.get("absent_species") for e in entries],
            "element_defect_keys": [e.get("element_defect_keys") for e in entries],
            "absent_max_over_F_ret_in": [
                None
                if e.get("absent_species_max_abs_flow_mol_s") is None
                else e["absent_species_max_abs_flow_mol_s"] / e["F_ret_in_mol_s"]
                for e in entries
            ],
            "defect_nonfinite_paths": [
                [
                    path
                    for path in e.get("nonfinite_paths") or []
                    if path.startswith("/diagnostics/element_defect_rel")
                ]
                for e in entries
            ],
        }
    moved = [label for label, e in g8.items() if e["d78_stage"] == "nonpositive_flow"]
    g8a = len(moved) == 6 and all("nonpositive_flow" not in g8[label]["stages"] for label in moved)
    s1_through = [e for e in g8.values() if e["passed_S1"]]
    g8b = all(
        all(value == ["Ar", "CH4"] for value in e["absent_species"])
        and all(value == ["H", "N"] for value in e["element_defect_keys"])
        and not any(e["defect_nonfinite_paths"])
        for e in s1_through
    )
    g8c = all(
        all(value is not None and value <= 1e-12 for value in e["absent_max_over_F_ret_in"])
        for e in s1_through
    )
    s1_corners = [label for label in g8 if label.startswith("B2-corner-T653.15-P1.5e+07")]
    g8d = len(s1_corners) == 2 and all(
        all(stage == "S1" for stage in g8[label]["stages"]) for label in s1_corners
    )
    # E1's record: a failed certificate₁ with δ₁ > 10⁻⁷ (expected 0), and failed certificates₂.
    every = [point for run in runs for point in run]
    failed_first_above = [
        p["label"]
        for p in every
        if p.get("stage") == "certificate"
        and p.get("round2") is None
        and p.get("defect_round1") is not None
        and not p["defect_round1"] <= 1e-7
    ]
    failed_second = [
        p["label"] for p in every if p.get("stage") == "certificate" and p.get("round2") is not None
    ]
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
            "no_error": no_error,
            "d78_nonpositive_flow": was_nonpositive,
            "still_nonpositive_flow": still_nonpositive,
            "certificate_corner": {"label": REPEAT_LABEL, "ends_certificate": certificate_corner},
            "nonfinite": [label for label, e in g3.items() if "nonfinite" in e["stages"]],
            "repeat": repeat,
            "met": g3_met,
        },
        "G11v3-4": {"rungs": boxes, "selected": selected},
        "G11v3-5": {
            "runs": len(runs),
            "points_per_run": len(runs[0]),
            "all_equal": all(equal.values()),
            "unequal": [label for label, same in equal.items() if not same],
            "S1_as_D78": {"points": s1, "met": s1_met},
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
        "G11v3-8": {
            "points": g8,
            "a": g8a,
            "b": g8b,
            "c": g8c,
            "d": g8d,
            "met": g8a and g8b and g8c and g8d,
        },
        "E1": {
            "failed_certificate1_with_defect_above_threshold": failed_first_above,
            "failed_certificate2": failed_second,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant-file", type=Path, required=True)
    parser.add_argument("--compare", type=Path, required=True)
    parser.add_argument("--d78", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--runs", type=int, default=2)
    arguments = parser.parse_args()
    variant = load_variant(arguments.variant_file)
    previous = json.loads(arguments.compare.read_text(encoding="utf-8"))
    d78 = json.loads(arguments.d78.read_text(encoding="utf-8"))
    todo = points()
    next(p for p in todo if p["label"] == REPEAT_LABEL)["repeat_check"] = True
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
        "specification": "docs/design/M02-pymrm-adapter.md §14.5 D1-D4 as amended by §14.6 E1-E4; "
        "G11v3-1 to -5 and -8 (§14.6); §10.3",
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
        "d78": {
            "record": arguments.d78.as_posix(),
            "sha256": file_sha256(arguments.d78),
            "variant": d78["variant"],
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
        "rungs": {name: {k: list(v) for k, v in rung.items()} for name, rung in RUNGS.items()},
        "B2": {k: list(v) for k, v in B2.items()},
        "summary": summarise(runs, repeats, previous, d78),
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
                "qualifies": {k: v["qualifies"] for k, v in summary["G11v3-4"]["rungs"].items()},
                "equal": summary["G11v3-5"]["all_equal"],
                "S1_as_D78": summary["G11v3-5"]["S1_as_D78"]["met"],
                "G11v3-8": summary["G11v3-8"]["met"],
                "E1": summary["E1"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
