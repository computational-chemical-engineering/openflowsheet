"""Record WO-11 — iteration 1 of the real reactor on box v2 (M04 spec §19 A2.4, A2.13): the
checks of M04.A31, A32 and A41 over a project that `scripts/m04_prewarm.py` pre-warmed and
studied, written as a committed record (build decision E30). Never in the default gate.

Read from the project (absolute path; build decision E31: a relative project path changes the
child's environment fingerprint, hence every experiment key):

- **A31.** Every experiment request stored in the project is bitwise a request of the plan (its
  experiment key is one of the plan's keys, computed as the study computes them); the study job's
  outputs are [manifest, evidence]; both validate against their schemas; the evidence names the
  manifest; the checker (A24) accepts the manifest; the verdict and every §7 metric are copied,
  whatever the verdict; `parent_extrapolated` is copied (expected 0).
- **A32.** The study is re-submitted with `max_cold_experiments = 0` under a fresh idempotency key:
  its answer has cold 0, hits = the plan's requests, and the same manifest SHA-256; no attempt is
  written.
- **A41.** The pre-warm report's serial bypass repeats of test requests 0–7, copied.
- **Failures.** Each registered draw whose deterministic result is not `ok`: its inlet, its code.

Usage:
    PYTHONPATH=src .venv/bin/python scripts/m04_wo11_record.py \\
        --artifacts <abs>/evidence/M04/artifacts/wo11 --out benchmarks/m04/wo11-b2-it1-v3
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

ROOT: Final = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from openflowsheet.adapters import variants  # noqa: E402
from openflowsheet.adapters.experiments.runner import ExperimentRunner  # noqa: E402
from openflowsheet.adapters.experiments.store import ExperimentStore  # noqa: E402
from openflowsheet.application.local import LocalApplication  # noqa: E402
from openflowsheet.application.operations import dispatch  # noqa: E402
from openflowsheet.compiled import EvaluationContext  # noqa: E402
from openflowsheet.models.c1 import COMPONENTS  # noqa: E402
from openflowsheet.studies.surrogate.manifest import (  # noqa: E402
    EVIDENCE_SCHEMA,
    MANIFEST_SCHEMA,
    check_manifest,
    derived_verdict,
    schema_errors,
)
from openflowsheet.studies.surrogate.plan import PLAN_N_TUBES  # noqa: E402
from openflowsheet.studies.surrogate.study import prepare  # noqa: E402
from openflowsheet.thermo.pr_c1 import PrC1Provider  # noqa: E402

VARIANT: Final = "pymrm-6089593-g2-nz800-s123-v3"
PLAN: Final = "b2-it1"
WIDTH_X: Final = 0.0025  # spec §6.1, w_X
WIDTH_DT_K: Final = 1.5  # spec §6.1, w_ΔT
RHO_G: Final = 0.25  # spec §7.2


def _count(application: LocalApplication, kind: str) -> int:
    with application.store.reading() as connection:
        (count,) = connection.execute(
            "SELECT COUNT(*) FROM artifacts WHERE kind = ?", (kind,)
        ).fetchone()
    return int(count)


def _artifact_bytes(application: LocalApplication, artifact_id: str) -> bytes:
    stored = application.store.artifact(artifact_id)
    assert stored is not None, artifact_id
    return (application.files_root / stored.relpath).read_bytes()


def _finite(values: Sequence[Any]) -> list[float]:
    return [v for v in values if isinstance(v, float) and math.isfinite(v)]


def record(artifacts: Path) -> tuple[dict[str, Any], bytes, bytes]:
    """The record, the manifest's bytes and the evidence's bytes."""
    project = artifacts / "project"
    prewarm = json.loads((artifacts / "prewarm.json").read_text(encoding="utf-8"))
    variant = variants.registered_variant(VARIANT)
    plan = prepare(variant, PLAN)
    application = LocalApplication.open(project)
    try:
        runner = ExperimentRunner(
            ExperimentStore(application.files_root),
            PrC1Provider(),
            EvaluationContext(model_version=variant.variant_id, constants_sha256=variant.sha256),
        )
        plan_keys = [
            str(runner.request(variant, state, COMPONENTS, PLAN_N_TUBES)["experiment_key"])
            for _, state in plan.requests()
        ]
        with application.store.reading() as connection:
            request_ids = [
                row[0]
                for row in connection.execute(
                    "SELECT artifact_id FROM artifacts WHERE kind = 'experiment_request'"
                )
            ]
        executed = [
            json.loads(_artifact_bytes(application, a))["experiment_key"] for a in request_ids
        ]
        failures = []
        for key in plan_keys:
            result = runner.records.result(key)
            assert result is not None, key
            envelope = result["envelope"]
            if envelope.get("code") != "ok":
                inputs = json.loads(
                    (
                        application.files_root / "experiments" / key[:2] / key / "request.json"
                    ).read_bytes()
                )["inputs"]
                n = inputs["n"]
                total = sum(n)
                failures.append(
                    {
                        "key": key,
                        "outcome_class": result["outcome_class"],
                        "code": envelope["code"],
                        "T_K": inputs["T"],
                        "P_Pa": inputs["P"],
                        "H2_N2": n[0] / n[1],
                        "inert_fraction": (n[3] + n[4]) / total,
                        "tube_flow_mol_s": total,
                    }
                )
        job_id = prewarm["study"]["job_id"]
        outputs = dispatch(application, "get_job", {"job_id": job_id})["outputs"]
        assert [o["kind"] for o in outputs] == ["surrogate_manifest", "model_evidence"], outputs
        manifest_bytes = _artifact_bytes(application, outputs[0]["artifact_id"])
        evidence_bytes = _artifact_bytes(application, outputs[1]["artifact_id"])
        manifest = json.loads(manifest_bytes)
        evidence = json.loads(evidence_bytes)
        attempts_before = _count(application, "experiment_attempt")
        second = dispatch(
            application,
            "submit_job",
            {
                "operation": "surrogate_study",
                "idempotency_key": f"m04-wo11-a32-{uuid.uuid4().hex[:12]}",
                "body": {
                    "parent": {
                        "model_id": variant.model_id,
                        "variant_id": variant.variant_id,
                        "variant_sha256": variant.sha256,
                    },
                    "plan_id": PLAN,
                    "budget": {"max_cold_experiments": 0},
                },
            },
        )["job"]
        again = dispatch(application, "get_job_result", {"job_id": second["job_id"]})[
            "surrogate_study"
        ]
        new_attempts = _count(application, "experiment_attempt") - attempts_before
    finally:
        application.close()

    calibration, evaluation = manifest["calibration"], manifest["evaluation"]
    q_hat = calibration["q_hat"]
    centres = manifest["gradient"]["centres"]
    gradient_e = [max(c["errors"].values()) for c in centres if c["errors"] is not None]
    test_finite = _finite(evaluation["scores"])
    cal_finite = _finite(calibration["scores"])
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    document: dict[str, Any] = {
        "record": "m04-wo11-b2-it1-v3",
        "specification": "docs/derivations/M04-spec.md §19 A2.4, A2.6, A2.13; §18 A1.6",
        "code_commit": commit,
        "parent": prewarm["parent"],
        "plan_id": PLAN,
        "prewarm": {k: v for k, v in prewarm.items() if k not in ("study", "repeats")},
        "study": prewarm["study"],
        "manifest_sha256": outputs[0]["sha256"],
        "evidence_sha256": outputs[1]["sha256"],
        "a31": {
            "plan_requests": len(plan_keys),
            "plan_requests_distinct": len(set(plan_keys)),
            "executed_requests": len(executed),
            "executed_not_in_plan": sum(k not in set(plan_keys) for k in executed),
            "plan_requests_executed": len(set(plan_keys) & set(executed)),
            "manifest_schema_errors": schema_errors(MANIFEST_SCHEMA, manifest),
            "evidence_schema_errors": schema_errors(EVIDENCE_SCHEMA, evidence),
            "evidence_names_manifest": evidence["subject"]["artifact_ref"] == outputs[0]["sha256"],
            "checker_failures": check_manifest(manifest),
            "derived_verdict_equal": derived_verdict(manifest).verdict
            == manifest["promotion"]["verdict"],
            "promotion": manifest["promotion"],
            "n": calibration["n"],
            "k": calibration["k"],
            "m": evaluation["m"],
            "q_hat": q_hat,
            "band_halfwidth": None
            if q_hat is None
            else {"X": q_hat * WIDTH_X, "dT_K": q_hat * WIDTH_DT_K},
            "width_scales": {"X": WIDTH_X, "dT_K": WIDTH_DT_K},
            "calibration_failed": len(calibration["scores"]) - len(cal_finite),
            "calibration_finite_max": max(cal_finite) if cal_finite else None,
            "test_failed": len(evaluation["scores"]) - len(test_finite),
            "test_finite_max": max(test_finite) if test_finite else None,
            "test_scores_le_1": sum(s <= 1 for s in test_finite),
            "hits": evaluation["hits"],
            "h_min": evaluation["h_min"],
            "lower_bound": evaluation["lower_bound"],
            "fraction_within_width": evaluation["fraction_within_width"],
            "errors": evaluation["errors"],
            "gradient_centres": centres,
            "gradient_max_e": max(gradient_e) if gradient_e else None,
            "rho_g": RHO_G,
            "splits": {
                name: {m: v for m, v in block.items() if m in ("count", "failed", "incomplete")}
                for name, block in manifest["splits"].items()
            },
            "domain": manifest["domain"],
        },
        "a32": {
            "job_id": second["job_id"],
            "cold_experiments": again["cold_experiments"],
            "cache_hits": again["cache_hits"],
            "cache_misses": again["cache_misses"],
            "manifest_sha256": again["manifest_sha256"],
            "manifest_bitwise_equal": again["manifest_sha256"] == outputs[0]["sha256"],
            "new_attempts": new_attempts,
        },
        "a41": prewarm["repeats"],
        "failures": failures,
    }
    return document, manifest_bytes, evidence_bytes


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args(argv)
    document, manifest_bytes, evidence_bytes = record(arguments.artifacts.resolve())
    arguments.out.mkdir(parents=True, exist_ok=True)
    (arguments.out / "manifest.json").write_bytes(manifest_bytes)
    (arguments.out / "evidence.json").write_bytes(evidence_bytes)
    (arguments.out / "record.json").write_text(
        json.dumps(document, indent=2) + "\n", encoding="utf-8"
    )
    a31, a32 = document["a31"], document["a32"]
    print(
        f"WO11 verdict={a31['promotion']['verdict']} "
        f"np={a31['promotion']['not_promotable']} ie={a31['promotion']['insufficient']} "
        f"q_hat={a31['q_hat']} grad_max={a31['gradient_max_e']} "
        f"extrapolated={a31['domain']['parent_extrapolated']} "
        f"not_in_plan={a31['executed_not_in_plan']} checker={len(a31['checker_failures'])} "
        f"a32_equal={a32['manifest_bitwise_equal']} a32_cold={a32['cold_experiments']} "
        f"a41={sum(r['repeat_bitwise_equal'] is True for r in document['a41'])}/"
        f"{len(document['a41'])} failures={len(document['failures'])}"
    )
    ok = (
        a31["executed_not_in_plan"] == 0
        and not a31["manifest_schema_errors"]
        and not a31["evidence_schema_errors"]
        and a31["evidence_names_manifest"]
        and not a31["checker_failures"]
        and a32["manifest_bitwise_equal"]
        and a32["cold_experiments"] == 0
        and a32["new_attempts"] == 0
        and all(r["repeat_bitwise_equal"] is True for r in document["a41"])
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
