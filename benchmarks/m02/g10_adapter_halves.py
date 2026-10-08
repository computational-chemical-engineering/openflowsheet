"""M02 G10: the adapter halves of M01.A41-A48, through M02's adapter (design note §10.2 G10; M01
spec §8.15, §9.9).

Opt-in evidence, never part of the default gate: it needs the pinned reactor environment, built
from pins by ``python -m openflowsheet.adapters.pymrm.env build --variant
pymrm-6089593-g2-nz800-s123-v1``. It runs in this project's environment (the worker side) and
reaches the reactor only through ``adapters.experiments`` and ``adapters.external`` — the child
in its own venv, one per attempt. Its record, ``benchmarks/m02/g10-adapter-halves.json``, is a
measurement (``judged: false``); ``tests/test_m02_g10_record.py`` checks the record's form and
numbers in the default gate, which never runs the reactor.

**Runs.** The registered variant, N_tubes = 1, the probe record's nominal point
(``benchmarks/m01/reactor-probe.json`` → ``pinned``):

- *direct* — the evaluation seam (``OutOfProcessBackend.evaluate``) with the record's tube inputs
  exactly: F_ret_in, y_in, T_in, p_ret_out = P_in and §8.3's coolant (A47 (a)); the same with the
  evidence-only switches S2 ``dt_init`` = 10⁻¹ (A42) and the backflow inflow ``[0, 0, 0, 1, 0]``
  (A44), each in a backend of its own (its own handshake, so its fingerprint differs);
- *boundary* — ``ExperimentRunner.run`` through M01's ``Boundary`` with the process inlet n =
  ``pinned.inlet_n_mol_s`` at T_in ∈ {653.15, 673.15, 693.15} K (A41; 673.15 K is A47 (b)), then
  two runs of the nominal request with the cache bypassed (A43).

Usage (from a checkout)::

    PYTHONPATH=src python benchmarks/m02/g10_adapter_halves.py \\
        --out benchmarks/m02/g10-adapter-halves.json
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import yaml

from openflowsheet.adapters import variants
from openflowsheet.adapters.experiments.backends import (
    Execution,
    OutOfProcessBackend,
    external_root,
)
from openflowsheet.adapters.experiments.runner import ExperimentRunner
from openflowsheet.adapters.experiments.store import ExperimentStore, ListArtifactSink
from openflowsheet.adapters.external.launcher import LaunchProgress
from openflowsheet.adapters.pymrm import child
from openflowsheet.canonical import document_sha256, file_sha256
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.c1 import COMPONENTS
from openflowsheet.models.c1.boundary import PERMEATE_OUTLET_PRESSURE, TubeInlet
from openflowsheet.thermo import StreamState
from openflowsheet.thermo.pr_c1 import PrC1Provider

REPO = Path(__file__).resolve().parents[2]
VARIANT_ID = "pymrm-6089593-g2-nz800-s123-v1"
PROBE = REPO / "benchmarks" / "m01" / "reactor-probe.json"
REFERENCE = REPO / "benchmarks" / "m01" / "reference_values.yaml"
TEMPERATURES = (653.15, 673.15, 693.15)
#: M01.A42's and A47 (b)'s bound (§10.3), A45's and A46's.
REL_BOUND = 1e-6
ELEMENT_BOUND = 1e-7
EPS_P = 1e-3
CONTEXT = EvaluationContext(model_version="m02-g10", constants_sha256="0" * 64)


def _rel(first: dict[str, Any], second: dict[str, Any]) -> float:
    """The largest relative difference over the five flows and T_out."""
    pairs = [*zip(first["flows"], second["flows"], strict=True)]
    pairs.append((first["temperature"], second["temperature"]))
    return float(max(abs(a - b) / abs(b) for a, b in pairs))


def _bitwise(outlet: dict[str, Any], flows: list[float], temperature: float) -> bool:
    same = [float(a).hex() == float(b).hex() for a, b in zip(outlet["flows"], flows, strict=True)]
    return all(same) and float(outlet["temperature"]).hex() == float(temperature).hex()


def _summary(label: str, execution: dict[str, Any], timing: dict[str, Any]) -> dict[str, Any]:
    diagnostics = execution.get("diagnostics") or {}
    defects = diagnostics.get("element_defect_rel") or {}
    return {
        "label": label,
        "status": execution["status"],
        "stage": execution.get("stage"),
        "stages_accepted": {
            name: stage["accepted"] for name, stage in (diagnostics.get("stages") or {}).items()
        },
        "stage_steps": {
            name: stage["steps"] for name, stage in (diagnostics.get("stages") or {}).items()
        },
        "tube_outlet": execution.get("tube_outlet"),
        "element_defect_max": max(map(abs, defects.values())) if defects else None,
        "dP_over_P": diagnostics.get("dP_over_P"),
        "u_ret_min": diagnostics.get("u_ret_min"),
        "min_axial_flow_mol_s": diagnostics.get("min_axial_flow_mol_s"),
        "wall_s": timing.get("wall_s"),
        "certificate_wall_s": (diagnostics.get("certificate") or {}).get("wall_s"),
        "startup_s": timing.get("startup_s"),
        "solve_s": timing.get("solve_s"),
    }


def _direct(
    variant: variants.Variant, tube: TubeInlet, work: Path, label: str, switches: dict[str, str]
) -> tuple[Execution, dict[str, Any]]:
    backend = OutOfProcessBackend(variant, test_environment=switches or None)
    environment = backend.environment(work / f"{label}-handshake")
    if environment.failure is not None:
        raise SystemExit(f"{label}: handshake failed: {environment.failure.message}")
    execution = backend.evaluate(tube, work / label, LaunchProgress(), None)
    if execution.status != "completed":
        raise SystemExit(f"{label}: {execution.status}: {execution.message}")
    assert environment.fingerprint is not None
    return execution, dict(environment.fingerprint)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args()
    variant = variants.registered_variant(VARIANT_ID)
    probe = json.loads(PROBE.read_text(encoding="utf-8"))
    pinned = probe["pinned"]
    estimate = yaml.safe_load(REFERENCE.read_text(encoding="utf-8"))["derived_from_measured"][
        "discretization_estimate"
    ]
    flow, t_in, p_in = pinned["F_ret_in_mol_s"], pinned["T_in_K"], pinned["P_in_Pa"]
    tube = TubeInlet(
        flow=flow,
        composition=tuple(pinned["y_in"]),
        temperature=t_in,
        outlet_pressure=p_in,
        coolant_flow=variant.sweep_ratio * flow,
        coolant_composition=(0.0, 1.0, 0.0, 0.0, 0.0),
        coolant_temperature=t_in,
        coolant_outlet_pressure=PERMEATE_OUTLET_PRESSURE,
    )
    runs: list[dict[str, Any]] = []
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="m02-g10-") as scratch:
        work = Path(scratch)
        # -- direct: A47 (a), A42, A44 ---------------------------------------------------------
        nominal, fingerprint = _direct(variant, tube, work, "nominal", {})
        alt_dt, _ = _direct(variant, tube, work, "s2-dt-1e-1", {child.S2_DT_INIT_VARIABLE: "0.1"})
        alt_backflow, _ = _direct(
            variant, tube, work, "backflow-alt", {child.BACKFLOW_ALT_VARIABLE: "1"}
        )
        for label, direct in (
            ("direct nominal", nominal),
            ("direct S2 dt_init 1e-1", alt_dt),
            ("direct backflow [0,0,0,1,0]", alt_backflow),
        ):
            document = {
                "status": direct.status,
                "stage": direct.stage,
                "tube_outlet": direct.tube_outlet,
                "diagnostics": direct.diagnostics,
            }
            runs.append(_summary(label, document, dict(direct.timing)))
        # -- boundary: A41 (A47 (b) at 673.15 K), A43 ---------------------------------------
        records = ExperimentStore(work / "project", ListArtifactSink())
        runner = ExperimentRunner(records, PrC1Provider(), CONTEXT, job_id="m02-g10")
        results: dict[float, Any] = {}
        for temperature in TEMPERATURES:
            inlet = StreamState(tuple(pinned["inlet_n_mol_s"]), temperature, p_in)
            outcome = runner.run(variant, inlet, COMPONENTS, 1.0)
            results[temperature] = outcome
            (attempt,) = outcome.attempts
            execution = attempt["execution"]
            summary = _summary(f"boundary T_in {temperature}", execution, execution["timing"])
            summary["envelope_status"] = outcome.envelope["status"]
            summary["envelope_code"] = outcome.envelope["code"]
            summary["discretization_estimate"] = outcome.envelope.get("discretization_estimate")
            summary["experiment_key"] = outcome.key
            runs.append(summary)
        inlet = StreamState(tuple(pinned["inlet_n_mol_s"]), t_in, p_in)
        repeats = []
        for number in (1, 2):
            outcome = runner.run(variant, inlet, COMPONENTS, 1.0, cache="bypass")
            (attempt,) = outcome.attempts
            execution = attempt["execution"]
            summary = _summary(f"boundary bypass repeat {number}", execution, execution["timing"])
            summary["repeat_bitwise_equal"] = attempt["repeat_bitwise_equal"]
            repeats.append(attempt["repeat_bitwise_equal"])
            runs.append(summary)
    elapsed = time.perf_counter() - started

    a47b_outlet = runs[3 + TEMPERATURES.index(t_in)]["tube_outlet"]
    probe_outlet = {"flows": pinned["outlet_n_mol_s"], "temperature": pinned["T_out_K"]}
    accepted = [run for run in runs if run["status"] == "completed" and run["stage"] is None]
    environment_block = {
        "python": fingerprint["python"],
        "platform": fingerprint["platform"],
        "packages": {
            name: fingerprint["packages"].get(name)
            for name in ("pymrm", "numpy", "scipy", "pandas")
        },
        "threads": "OMP/OPENBLAS/MKL_NUM_THREADS=1"
        if all(fingerprint["thread_env"].get(name) == "1" for name in child.THREAD_VARIABLES[:3])
        else "other",
    }
    record = {
        "record": "m02-g10-adapter-halves",
        "version": 1,
        "status": "measured",
        "judged": False,
        "specification": (
            "docs/design/M02-pymrm-adapter.md §10.2 G10; docs/derivations/M01-spec.md §8.15"
        ),
        "probe_record_sha256": file_sha256(PROBE),
        "variant": {"variant_id": variant.variant_id, "sha256": variant.sha256},
        "environment": {
            **environment_block,
            "cpu_model": fingerprint["cpu_model"],
            "machine": fingerprint["machine"],
            "numba": fingerprint["packages"].get("numba"),
            "llvmlite": fingerprint["packages"].get("llvmlite"),
            "env_id": variant.evaluation["environment"]["env_id"],
            "external_root_default": str(external_root())
            == str(Path.home() / ".cache" / "openflowsheet" / "external"),
            "fingerprint_sha256": document_sha256(fingerprint),
            "lock_sha256": fingerprint["lock_sha256"],
            "export_tree_sha256": fingerprint["export_tree_sha256"],
            "merged_database_sha256": fingerprint["merged_database_sha256"],
            "runner_sha256": fingerprint["runner_sha256"],
            "worker_python": platform.python_version(),
        },
        "probe_environment": probe["environment"],
        "assertions": {
            "A41": {
                "T_in_K": list(TEMPERATURES),
                "accepted": [
                    results[t].envelope["status"] == "ok"
                    and runs[3 + i]["stages_accepted"] == {"S1": True, "S2": True, "S3": True}
                    for i, t in enumerate(TEMPERATURES)
                ],
            },
            "A42": {
                "s2_dt_init": [1e-6, 1e-1],
                "max_rel_diff": _rel(
                    dict(alt_dt.tube_outlet or {}), dict(nominal.tube_outlet or {})
                ),
                "bound": REL_BOUND,
                "probe_max_rel_diff": probe["path_independence"]["max_rel_diff"],
            },
            "A43": {"bypassed_runs": len(repeats), "repeat_bitwise_equal": repeats},
            "A44": {
                "alternative_backflow": child.BACKFLOW_ALT,
                "bitwise_identical": _bitwise(
                    dict(alt_backflow.tube_outlet or {}),
                    list((nominal.tube_outlet or {})["flows"]),
                    (nominal.tube_outlet or {})["temperature"],
                ),
                "u_ret_min": [run["u_ret_min"] for run in runs],
            },
            "A45": {
                "element_defect_max": [run["element_defect_max"] for run in accepted],
                "bound": ELEMENT_BOUND,
            },
            "A46": {"dP_over_P": [run["dP_over_P"] for run in runs], "bound": EPS_P},
            "A47": {
                "a_environment_block_equal": environment_block == probe["environment"],
                "a_bitwise": _bitwise(
                    dict(nominal.tube_outlet or {}), pinned["outlet_n_mol_s"], pinned["T_out_K"]
                ),
                "b_max_rel_diff": _rel(a47b_outlet, probe_outlet),
                "b_bound": REL_BOUND,
            },
            "A48": {
                "estimates_equal_reference": [
                    run["discretization_estimate"] == estimate
                    for run in runs
                    if run.get("envelope_status") == "ok"
                ],
            },
        },
        "runs": runs,
        "elapsed_s": round(elapsed, 1),
    }
    for value in record["assertions"]["A45"]["element_defect_max"]:
        assert value is not None and math.isfinite(value)
    arguments.out.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", "utf-8")
    print(json.dumps(record["assertions"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
