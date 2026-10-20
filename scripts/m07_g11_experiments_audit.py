"""M07 WO-8d: the audit of G11's kept experiment records at C′ (W21 (e); R-375; V02 alpha release
spec §19.6 A6).

R-375 registers that 0.2.0's RC keeps G11's experiment results under `rc/step12/experiments/` and
that an audit checks blueprint §9.1's six items in each, against `schemas/experiment.schema.json`,
as R-348 did for step 12's certificates (`t08_rc.py:audit_certificate`). §9.1: "PyMRM results
include boundary mapping, version, discretization settings, convergence evidence, conserved
fluxes, and cost." The 0.2.0 verdict (W21 (e)) names where each lives in an experiment's records;
this script checks, for every result and its attempts:

- **schema** — the request, the result and every attempt validate against the schema's
  `request`, `result` and `attempt` definitions (the precondition of every item), except in the
  `job_id` of the result's `produced_by` and of each attempt (`CONTEXT_FIELDS`): the requesting job
  is context, not one of §9.1's items, and a violation there is reported apart, as `context`,
  without failing the audit (build decision J78; G11 names its jobs `m02-g11v3-<label>`, which the
  schema's `^job-[0-9]{6,}$` refuses);
- **boundary** (boundary mapping) — the request's `boundary` block names the provider, its identity
  hash, `n_tubes` > 0 and the sweep ratio; the request's key is the `document_sha256` of the request
  without it, the result's `request_sha256` is that of the stored request and its key is the
  request's, every attempt is of that key, and every completed attempt records the `tube_inlet`
  it sent; where G11's runs file is given, the request's inlet and `n_tubes` are the point's,
  exactly;
- **version** (variant id, SHA-256 and reactor commit) — `provenance.variant_id` and
  `variant_sha256` are the variant's and the request's `model.version` and `model.artifact_ref`;
  `provenance.reactor` is the variant's reactor block (its `commit` included); a full envelope
  identity names the same `reactor_commit`;
- **discretization** (num_z and the estimate) — `accuracy` is the variant's accuracy block, copied,
  with its estimate's `num_z` the variant's grid; the envelope's estimate is that estimate on `ok`
  and null otherwise; every completed attempt's diagnostics record the same `num_z`;
- **convergence** (stage and certificate) — `produced_by.attempt` names a recorded attempt whose
  status is deterministic (`completed` or `not_executed`); an `ok` envelope was produced by a
  completed attempt with no stage; a completed attempt with no stage carries the deciding KPI-drift
  certificate with `kpi_drift_ok` true, and one that ended at `certificate` carries it false
  (`child.py`'s `s3_certificate`);
- **fluxes** (element defects) — an `ok` envelope carries the projection defect, one finite entry
  per component, and a finite `defect_rel` ≥ 0; a refusal carries neither (the envelope's own rule);
  every completed attempt with no stage records `element_defect_rel`, finite, keyed by exactly the
  elements present in the `composition` it sent (M02 design note §14.6 E2, `child.py`'s
  `element_defects`: element e is present iff E_e · y > 0);
- **cost** (wall time) — every attempt's `timing.wall_s` is finite and > 0, `startup_s` and
  `solve_s` null or finite ≥ 0; the result's `provider_calls` is an integer ≥ 0 (R-233).

An experiment with attempts and no result (a transient failure) is audited on what it has: its
attempts' schema, key, `tube_inlet`, stage and certificate, defects and wall time.

    python scripts/m07_g11_experiments_audit.py <g11-experiments-run<k>.json[.gz]>... \\
        --variant-file benchmarks/m02/variant-v3-provisional.json [--runs <runs.json>]

Prints one summary line and exits 0 only if every item of every experiment holds; `context`
findings are counted on that line and listed in `--out`.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from openflowsheet.adapters import variants
from openflowsheet.canonical import document_sha256

ROOT: Final = Path(__file__).resolve().parents[1]
SCHEMA: Final = ROOT / "schemas" / "experiment.schema.json"
FORMAT: Final = "m07-g11-experiments-v1"
ITEMS: Final = ("schema", "boundary", "version", "discretization", "convergence", "fluxes", "cost")
DETERMINISTIC: Final = ("completed", "not_executed")
#: `child.py`'s `ELEMENTS` over its `SPECIES` (H2, N2, NH3, Ar, CH4), the order of `composition`.
ELEMENTS: Final = {
    "H": (2, 0, 3, 0, 4),
    "N": (0, 2, 1, 0, 0),
    "C": (0, 0, 0, 0, 1),
    "Ar": (0, 0, 0, 1, 0),
}
#: Schema paths (relative to the record) that hold the requesting job: context, reported apart.
CONTEXT_FIELDS: Final = (("produced_by", "job_id"), ("job_id",))


def validators() -> dict[str, Draft202012Validator]:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    registry = Registry().with_resource(
        schema["$id"], Resource(contents=schema, specification=DRAFT202012)
    )
    return {
        name: Draft202012Validator({"$ref": f"{schema['$id']}#/$defs/{name}"}, registry=registry)
        for name in ("request", "result", "attempt")
    }


def _finite(value: Any, minimum: float | None = None) -> bool:
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(value)
        and (minimum is None or value >= minimum)
    )


def _sha256_hex(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= set("0123456789abcdef")


def audit_experiment(
    experiment: Mapping[str, Any],
    variant: variants.Variant,
    checkers: Mapping[str, Draft202012Validator],
    point: Mapping[str, Any] | None = None,
) -> dict[str, list[str]]:
    """The problems of one experiment's records, per item, and its `context` findings; every
    list empty if all hold."""
    problems: dict[str, list[str]] = {item: [] for item in (*ITEMS, "context")}
    request = experiment.get("request") or {}
    result = experiment.get("result")
    attempts: Sequence[Mapping[str, Any]] = experiment.get("attempts") or []
    executions = [a.get("execution") or {} for a in attempts]

    # schema
    documents = [("request", request)] + ([("result", result)] if result is not None else [])
    documents += [("attempt", a) for a in attempts]
    for name, document in documents:
        for error in checkers[name].iter_errors(document):
            where = "/".join(str(p) for p in error.absolute_path)
            kind = "context" if tuple(error.absolute_path) in CONTEXT_FIELDS else "schema"
            problems[kind].append(f"{name} {where}: {error.message}")
    if not attempts:
        problems["schema"].append("no attempt recorded")

    # boundary mapping
    boundary = request.get("boundary") or {}
    if not (isinstance(boundary.get("provider_id"), str) and boundary["provider_id"]):
        problems["boundary"].append("request.boundary.provider_id")
    if not _sha256_hex(boundary.get("provider_identity_sha256")):
        problems["boundary"].append("request.boundary.provider_identity_sha256")
    if not (_finite(boundary.get("n_tubes")) and boundary["n_tubes"] > 0):
        problems["boundary"].append("request.boundary.n_tubes")
    if not _finite(boundary.get("sweep_ratio")):
        problems["boundary"].append("request.boundary.sweep_ratio")
    key = request.get("experiment_key")
    unkeyed = {k: v for k, v in request.items() if k != "experiment_key"}
    if key != document_sha256(unkeyed):
        problems["boundary"].append("request.experiment_key is not the request's document_sha256")
    if result is not None:
        if result.get("request_sha256") != document_sha256(dict(request)):
            problems["boundary"].append("result.request_sha256 is not the stored request's")
        if result.get("experiment_key") != key:
            problems["boundary"].append("result.experiment_key")
    for attempt, execution in zip(attempts, executions, strict=True):
        if attempt.get("experiment_key") != key:
            problems["boundary"].append(f"attempt {attempt.get('attempt')}: experiment_key")
        if execution.get("status") == "completed" and not isinstance(
            execution.get("tube_inlet"), Mapping
        ):
            problems["boundary"].append(f"attempt {attempt.get('attempt')}: no tube_inlet")
    if point is not None:
        inputs = request.get("inputs") or {}
        if (
            inputs.get("n") != point.get("inlet_n_mol_s")
            or inputs.get("T") != point.get("T_in_K")
            or inputs.get("P") != point.get("P_in_Pa")
            or boundary.get("n_tubes") != point.get("n_tubes")
        ):
            problems["boundary"].append("request inlet or n_tubes is not the point's")

    # version: variant id, SHA-256 and reactor commit
    model = request.get("model") or {}
    if model.get("version") != variant.variant_id or model.get("artifact_ref") != variant.sha256:
        problems["version"].append("request.model is not the variant")
    reactor = variant.evaluation.get("reactor")
    if result is not None:
        provenance = result.get("provenance") or {}
        if provenance.get("variant_id") != variant.variant_id:
            problems["version"].append("result.provenance.variant_id")
        if provenance.get("variant_sha256") != variant.sha256:
            problems["version"].append("result.provenance.variant_sha256")
        recorded = provenance.get("reactor")
        if recorded != (None if reactor is None else dict(reactor)):
            problems["version"].append("result.provenance.reactor is not the variant's")
        commit = (recorded or {}).get("commit")
        if reactor is not None and not commit:
            problems["version"].append("result.provenance.reactor.commit")
        identity = (result.get("envelope") or {}).get("identity") or {}
        if identity and identity.get("reactor_commit") != commit:
            problems["version"].append("envelope.identity.reactor_commit")

    # discretization: num_z and the estimate
    accuracy = variant.accuracy
    estimate = accuracy.get("discretization_estimate") or {}
    num_z = variant.evaluation.get("configuration", {}).get("num_z")
    if estimate.get("num_z") != num_z or not isinstance(num_z, int):
        problems["discretization"].append("the variant's estimate is not of its grid")
    envelope = (result or {}).get("envelope") or {}
    if result is not None:
        recorded_accuracy = result.get("accuracy") or {}
        if recorded_accuracy != dict(accuracy):
            problems["discretization"].append("result.accuracy is not the variant's")
        if (recorded_accuracy.get("discretization_estimate") or {}).get("num_z") != num_z:
            problems["discretization"].append("result.accuracy.discretization_estimate.num_z")
        expected = (
            recorded_accuracy.get("discretization_estimate")
            if envelope.get("status") == "ok"
            else None
        )
        if envelope.get("discretization_estimate") != expected:
            problems["discretization"].append("envelope.discretization_estimate")
    for attempt, execution in zip(attempts, executions, strict=True):
        if execution.get("status") == "completed":
            if (execution.get("diagnostics") or {}).get("num_z") != num_z:
                problems["discretization"].append(
                    f"attempt {attempt.get('attempt')}: diagnostics.num_z"
                )

    # convergence: stage and certificate
    by_number = {a.get("attempt"): e for a, e in zip(attempts, executions, strict=True)}
    if result is not None:
        number = (result.get("produced_by") or {}).get("attempt")
        producer = by_number.get(number)
        if producer is None:
            problems["convergence"].append(f"produced_by.attempt {number} is not recorded")
        elif producer.get("status") not in DETERMINISTIC:
            problems["convergence"].append(f"produced_by attempt status {producer.get('status')}")
        elif envelope.get("status") == "ok" and (
            producer.get("status") != "completed" or producer.get("stage") is not None
        ):
            problems["convergence"].append("ok envelope from a staged or unexecuted attempt")
    for attempt, execution in zip(attempts, executions, strict=True):
        if execution.get("status") != "completed":
            continue
        stage = execution.get("stage")
        certificate = (execution.get("diagnostics") or {}).get("certificate")
        if stage is None or stage == "certificate":
            passed = stage is None
            if (
                not isinstance(certificate, Mapping)
                or certificate.get("kpi_drift_ok") is not passed
            ):
                problems["convergence"].append(
                    f"attempt {attempt.get('attempt')}: stage {stage} without its certificate"
                )

    # conserved fluxes: element defects
    if result is not None:
        components = (request.get("inputs") or {}).get("components") or []
        defect, relative = envelope.get("defect"), envelope.get("defect_rel")
        if envelope.get("status") == "ok":
            if not (
                isinstance(defect, list)
                and len(defect) == len(components)
                and all(_finite(d) for d in defect)
            ):
                problems["fluxes"].append("envelope.defect")
            if not _finite(relative, 0.0):
                problems["fluxes"].append("envelope.defect_rel")
        elif defect is not None or relative is not None:
            problems["fluxes"].append("a refusal carries a defect")
    for attempt, execution in zip(attempts, executions, strict=True):
        if execution.get("status") == "completed" and execution.get("stage") is None:
            defects = (execution.get("diagnostics") or {}).get("element_defect_rel")
            composition = (execution.get("tube_inlet") or {}).get("composition") or []
            present = {
                element
                for element, weights in ELEMENTS.items()
                if len(composition) == len(weights)
                and sum(w * y for w, y in zip(weights, composition, strict=True)) > 0
            }
            if not (
                isinstance(defects, Mapping)
                and present
                and set(defects) == present
                and all(_finite(defects[e]) for e in present)
            ):
                problems["fluxes"].append(
                    f"attempt {attempt.get('attempt')}: diagnostics.element_defect_rel"
                )

    # cost: wall time
    for attempt, execution in zip(attempts, executions, strict=True):
        timing = execution.get("timing") or {}
        if not (_finite(timing.get("wall_s")) and timing["wall_s"] > 0):
            problems["cost"].append(f"attempt {attempt.get('attempt')}: timing.wall_s")
        for name in ("startup_s", "solve_s"):
            if timing.get(name) is not None and not _finite(timing.get(name), 0.0):
                problems["cost"].append(f"attempt {attempt.get('attempt')}: timing.{name}")
    if result is not None:
        calls = result.get("provider_calls")
        if not (isinstance(calls, int) and not isinstance(calls, bool) and calls >= 0):
            problems["cost"].append("result.provider_calls")
    return problems


def load(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if path.suffix == ".gz":
        raw = gzip.decompress(raw)
    document = json.loads(raw)
    assert isinstance(document, dict)
    return document


def audit(
    records: Sequence[Mapping[str, Any]],
    variant: variants.Variant,
    runs: Sequence[Sequence[Mapping[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Every experiment of every run record: the counts, the first problems per item, and the
    `context` findings (all of them, with the distinct messages they reduce to)."""
    checkers = validators()
    counts = {
        "runs": 0,
        "points": 0,
        "boundary_points": 0,
        "direct_points": 0,
        "experiments": 0,
        "results": 0,
        "attempts": 0,
        "without_result": 0,
    }
    failed: dict[str, list[str]] = {item: [] for item in ITEMS}
    context: list[str] = []
    kinds: set[str] = set()
    structural: list[str] = []
    for record in records:
        if record.get("format") != FORMAT:
            structural.append(f"run {record.get('run')}: format {record.get('format')}")
            continue
        counts["runs"] += 1
        k = record.get("run")
        by_label: dict[str, Mapping[str, Any]] = {}
        if runs is not None:
            if not isinstance(k, int) or not 1 <= k <= len(runs):
                structural.append(f"run {k}: not in the runs file")
                continue
            by_label = {p["label"]: p for p in runs[k - 1]}
            if [p["label"] for p in record["points"]] != [p["label"] for p in runs[k - 1]]:
                structural.append(f"run {k}: points are not the runs file's")
        for point in record["points"]:
            counts["points"] += 1
            if point["experiments"] is None:
                counts["direct_points"] += 1
                if point["path"] == "boundary":
                    structural.append(f"run {k} {point['label']}: boundary point without a store")
                continue
            counts["boundary_points"] += 1
            if len(point["experiments"]) != 1:
                structural.append(
                    f"run {k} {point['label']}: {len(point['experiments'])} experiments, not 1"
                )
            for experiment in point["experiments"]:
                counts["experiments"] += 1
                counts["attempts"] += len(experiment.get("attempts") or [])
                if experiment.get("result") is None:
                    counts["without_result"] += 1
                else:
                    counts["results"] += 1
                found = audit_experiment(
                    experiment, variant, checkers, by_label.get(point["label"])
                )
                for message in found.pop("context"):
                    context.append(f"run {k} {point['label']}: {message}")
                    kinds.add(message.split(":", 1)[0])
                for item, messages in found.items():
                    failed[item].extend(f"run {k} {point['label']}: {m}" for m in messages)
    return {
        "counts": counts,
        "items": {item: {"problems": len(m), "first": m[:5]} for item, m in failed.items()},
        "context": {
            "findings": len(context),
            "where": sorted(kinds),
            "all": context,
        },
        "structural": structural,
        "passed": counts["experiments"] > 0 and not structural and not any(failed.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records", type=Path, nargs="+")
    parser.add_argument("--variant-file", type=Path, required=True)
    parser.add_argument("--runs", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    arguments = parser.parse_args()
    variant = variants.variant_from_document(
        json.loads(arguments.variant_file.read_text(encoding="utf-8"))
    )
    runs = None if arguments.runs is None else json.loads(arguments.runs.read_text("utf-8"))
    report = audit([load(p) for p in arguments.records], variant, runs)
    if arguments.out is not None:
        arguments.out.write_text(json.dumps(report, indent=1) + "\n", "utf-8")
    c = report["counts"]
    problems = sum(v["problems"] for v in report["items"].values()) + len(report["structural"])
    print(
        f"G11 experiments audit: {c['runs']} runs, {c['boundary_points']} boundary points, "
        f"{c['results']} results, {c['attempts']} attempts, {c['without_result']} without a "
        f"result, {c['direct_points']} direct points (no records); {len(ITEMS) - 1} items + "
        f"schema: {problems} problems; context (job_id): {report['context']['findings']} "
        f"findings: {'PASS' if report['passed'] else 'FAIL'}"
    )
    if not report["passed"]:
        print(json.dumps({"structural": report["structural"][:5], "items": report["items"]}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
