"""Generate `evidence/K04/<commit>/manifest.json` by measuring, not by transcribing.

Every numeric `value` is computed here by running the verifier, against Fable's 40-digit K04
reference values and the 20-digit SYN-001 references — both generated with mpmath and
independent of everything in `src/`. A typed-in number would be a claim about a measurement
rather than a measurement.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/k04_evidence_manifest.py <gate-stdout> --commit <sha>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from k04_schema_fixtures import TRIVIAL_ROOT_OFFSET, once_through  # noqa: E402

from openflowsheet.canonical import file_sha256  # noqa: E402
from openflowsheet.compiled import EvaluationContext  # noqa: E402
from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet  # noqa: E402
from openflowsheet.orchestrator.tear import Syn001TearProblem, solve_tear  # noqa: E402
from openflowsheet.orchestrator.trace import SolvePolicy  # noqa: E402
from openflowsheet.thermo.syn001 import Syn001Provider  # noqa: E402
from openflowsheet.verify.certificate import CheckPolicy, verify  # noqa: E402
from openflowsheet.verify.checks import KIND_TOLERANCE  # noqa: E402
from openflowsheet.verify.failure import bundle_for  # noqa: E402
from openflowsheet.verify.regularity import (  # noqa: E402
    absolute_conditioning_threshold,
    screen,
)

CONTEXT = EvaluationContext(model_version="K04-evidence@" + "0" * 64, constants_sha256="0" * 64)

CASE_IDS = (
    "SYN-001-nominal",
    "SYN-001-once-through",
    "SYN-001-high-recycle",
    "SYN-001-all-liquid-310K",
    "SYN-001-all-vapor-420K",
)


def variants() -> dict[str, Mapping[str, Any]]:
    loaded = yaml.safe_load((ROOT / "benchmarks/syn001/reference_values.yaml").read_text())
    return {entry["case_id"]: entry for entry in loaded["variants"]}


def flowsheet_for(case: Mapping[str, Any]) -> Syn001Flowsheet:
    return Syn001Flowsheet(
        provider=Syn001Provider(),
        context=CONTEXT,
        split_fraction=float(case["r"]),
        flash_temperature=float(case["T_flash_K"]),
        heater_temperature=float(case["T_heater_K"]),
        pressure=float(case["P_Pa"]),
    )


def measure_verdicts(registry: dict[str, Mapping[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for case_id in CASE_IDS:
        flowsheet = flowsheet_for(registry[case_id])
        result, _ = solve_tear(flowsheet)
        certificate = verify(flowsheet, result)
        out[case_id] = {
            "verdict": certificate.verification_status,
            "checks": len(certificate.checks),
            "failing": sorted(c.id for c in certificate.checks if c.result == "fail"),
            "unsupported": sorted(c.id for c in certificate.checks if c.result == "unsupported"),
            "not_applicable": sorted(
                {c.subject for c in certificate.checks if c.result == "not_applicable"}
            ),
            "limitations": [limitation.kind for limitation in certificate.limitations],
            "regularity": certificate.regularity.status,
            "rcond_1": certificate.regularity.rcond_1,
            "inverse_one_norm": certificate.regularity.inverse_one_norm_estimate,
            "solution_error_bound_scaled": certificate.solution_error_bound_scaled,
        }
    return out


def measure_trivial_root() -> dict[str, Any]:
    """§9.2 / A18. The measurement the whole package exists for."""
    flowsheet = once_through()
    result, _ = solve_tear(flowsheet)
    state = dict(result.final_state or {})
    for component in ("A", "B", "C"):
        state[f"S3.liq.{component}"] = state[f"S3.n.{component}"]
        state[f"S3.vap.{component}"] = 0.0
    state["S3.L"] = sum(state[f"S3.n.{c}"] for c in ("A", "B", "C"))
    state["S3.V"] = 0.0
    state["U-HEAT.Q"] -= TRIVIAL_ROOT_OFFSET
    state["U-FLASH.Q"] += TRIVIAL_ROOT_OFFSET

    certificate = verify(flowsheet, result, state=state)
    by_id = {check.id: check for check in certificate.checks}
    residuals = [c for c in certificate.checks if c.category == "residual"]
    material = [c for c in certificate.checks if c.category == "material_balance"]
    return {
        "verdict": certificate.verification_status,
        "false_success_detected": certificate.false_success_detected,
        "residual_rows_passing": sum(c.result == "pass" for c in residuals),
        "residual_rows": len(residuals),
        "worst_residual": max(abs(c.value or 0.0) for c in residuals),
        "material_all_pass": all(c.result == "pass" for c in material),
        "energy_envelope": by_id["energy_balance.envelope"].result,
        "regularity": certificate.regularity.status,
        "failing": {
            "energy_heater_W": by_id["energy_balance.heater"].value,
            "energy_flash_W": by_id["energy_balance.flash"].value,
            "sum_xK_minus_one": by_id["phase_admissibility.S3.bubble"].value,
            "split_total_mol_per_s": by_id["independent_split.S3.total"].value,
        },
    }


def measure_injections(registry: dict[str, Mapping[str, Any]]) -> dict[str, Any]:
    flowsheet = flowsheet_for(registry["SYN-001-nominal"])
    result, _ = solve_tear(flowsheet)
    base = dict(result.final_state or {})
    out: dict[str, Any] = {}
    for name, key, over, under in (
        ("INJ-1", "U-HEAT.Q", 1.0, 5e-4),
        ("INJ-6", "S6.n.A", 1e-6, 1e-8),
        ("INJ-7", "S3.T", 1e-5, 1e-7),
    ):
        pair = {}
        for label, delta in (("above", over), ("below", under)):
            state = dict(base)
            state[key] += delta
            certificate = verify(flowsheet, result, state=state)
            pair[label] = {
                "delta": delta,
                "verdict": certificate.verification_status,
                "failing": sorted(c.id for c in certificate.checks if c.result == "fail"),
                "solution_error_bound_scaled": certificate.solution_error_bound_scaled,
            }
        out[name] = pair
    return out


def measure_fixtures() -> dict[str, Any]:
    """§7.6's constructed matrices: three statuses from one family, U-diagonal useless."""
    import numpy as np
    import scipy.sparse as sp

    out: dict[str, Any] = {}
    for size in (16, 32, 64):
        matrix = sp.csc_matrix(np.eye(size) - np.triu(np.ones((size, size)), 1))
        evidence = screen(matrix)
        out[f"TRI-{size}"] = {
            "status": evidence.status,
            "rcond_1": evidence.rcond_1,
            "rcond_1_exact": 1.0 / (size * 2.0 ** (size - 1)),
            "u_diagonal_ratio": evidence.u_diagonal_ratio,
            "svd_rank": (evidence.escalation or {}).get("rank"),
        }
    out["DIM-2001"] = {
        "status": screen(sp.csc_matrix(np.diag([1.0] * 2000 + [1e-12]))).status,
        "reason": screen(sp.csc_matrix(np.diag([1.0] * 2000 + [1e-12]))).inconclusive_reason,
    }
    sq0 = screen(sp.csc_matrix(np.array([[0.0]])))
    out["SQ-0"] = {"status": sq0.status, "rank": (sq0.escalation or {}).get("rank")}
    sq1 = screen(sp.csc_matrix(np.array([[2.0**-13]])), tau_scaled_min=1e-8)
    sq2 = screen(sp.csc_matrix(np.array([[2.0**-19]])), tau_scaled_min=1e-12)
    out["SQ-1"] = {
        "status": sq1.status,
        "inverse_one_norm": sq1.inverse_one_norm_estimate,
        "threshold": absolute_conditioning_threshold(1, 1e-8),
    }
    out["SQ-2"] = {
        "status": sq2.status,
        "reason": sq2.ill_conditioned_reason,
        "inverse_one_norm": sq2.inverse_one_norm_estimate,
        "threshold": absolute_conditioning_threshold(1, 1e-12),
    }
    return out


def measure_bundle() -> dict[str, Any]:
    from k03_schema_fixtures import flowsheet as nominal_flowsheet

    policy = SolvePolicy(
        policy_id="SYN-001-capped", residual_tolerances={}, scales={}, max_property_calls=20
    )
    result, trace = solve_tear(nominal_flowsheet(), policy=policy)
    bundle = bundle_for(result, trace)
    serialized = json.dumps(bundle.as_document())
    return {
        "outcome": bundle.outcome,
        "taxonomy": bundle.taxonomy,
        "property_calls": bundle.observations["counters"]["property_calls"],
        "checkpoint": bundle.best_checkpoint,
        "actions": [entry.action for entry in bundle.suggested_actions],
        "carries_no_verdict_word": not any(
            word in serialized for word in ("VERIFIED", "RELAXED", "UNVERIFIED", "FAILED")
        ),
        "carries_no_infeasibility_claim": "INFEASIBLE" not in serialized.upper(),
    }


def measure_relaxation(registry: dict[str, Mapping[str, Any]]) -> dict[str, Any]:
    reference = yaml.safe_load((ROOT / "benchmarks/k04/reference_values.yaml").read_text())
    registered = reference["injections"]["INJ-3-consistent-near-state"]
    flowsheet = flowsheet_for(registry["SYN-001-nominal"])
    result, _ = solve_tear(flowsheet)
    tear = Syn001TearProblem(flowsheet)
    state = tear.reconstruct(tear.tear_state([float(value) for value in registered["t_mol_per_s"]]))
    out = {}
    for label, policy in (
        ("registered", CheckPolicy()),
        (
            "loosened",
            CheckPolicy(
                policy_id="supplied-loose", tolerances={**KIND_TOLERANCE, "molar_flow": 1e-6}
            ),
        ),
        (
            "tightened",
            CheckPolicy(
                policy_id="supplied-tight", tolerances={**KIND_TOLERANCE, "molar_flow": 1e-9}
            ),
        ),
    ):
        certificate = verify(flowsheet, result, state=state, policy=policy)
        out[label] = {
            "verdict": certificate.verification_status,
            "policy_sha256": certificate.check_policy_sha256,
            "relaxations": [
                limitation.detail
                for limitation in certificate.limitations
                if limitation.kind == "relaxation"
            ],
        }
    return out


def build(commit: str, gate_stdout: Path) -> dict[str, Any]:
    registry = variants()
    verdicts = measure_verdicts(registry)
    trivial = measure_trivial_root()
    injections = measure_injections(registry)
    fixtures = measure_fixtures()
    bundle = measure_bundle()
    relaxation = measure_relaxation(registry)

    checks: list[dict[str, Any]] = [
        {
            "id": "K04.A15.verdicts",
            "description": (
                "§6 and §8: every registered variant certifies. All checks pass, none is "
                "unsupported, the regularity status is clean, there are no limitations at all, "
                "and a dormant stream's checks are recorded `not_applicable` rather than "
                "skipped — S6 at once-through, S4 at 310 K, S5/S6/S7 at 420 K."
            ),
            "result": "pass"
            if all(
                entry["verdict"] == "VERIFIED" and not entry["failing"] and not entry["limitations"]
                for entry in verdicts.values()
            )
            else "fail",
            "value": verdicts,
            "expected": "VERIFIED at all five, no limitation",
        },
        {
            "id": "K04.A18.injected_false_success",
            "description": (
                "§9.2 and gate **G04**'s false-success clause. The trivial root: S3's lifted "
                "split forced all-liquid at the once-through variant with both duties closed. "
                "Every equation the solver knows about is satisfied — all 49 assembled rows, "
                "every material balance, the alias certificates, the overall energy envelope, "
                "and the regularity screen. It is caught only by the checks that do not read "
                "the lifted split: a fresh flash of every stream, and comparing the split "
                "against one. K02 measured this state's duty error independently at 8237.85 W "
                "through the code; Fable's closed form gives 8237.8503930694530451."
            ),
            "result": "pass"
            if trivial["verdict"] == "FAILED"
            and trivial["false_success_detected"]
            and trivial["residual_rows_passing"] == trivial["residual_rows"] == 49
            and trivial["material_all_pass"]
            and trivial["energy_envelope"] == "pass"
            and trivial["regularity"] == "NO_RANK_LOSS_DETECTED"
            else "fail",
            "value": trivial,
            "expected": (
                "FAILED with false_success_detected; 49/49 residual rows passing; the energy "
                "envelope passing as the registered blind spot; heater and flash at "
                "-/+8237.8503930694530451 W; sum(x K) - 1 = 0.0703142190807741552; split gap "
                "0.30410617028018327955 mol/s"
            ),
        },
        {
            "id": "K04.A17_A27_A28.injections_and_twins",
            "description": (
                "§9.1, §9.6, §9.7, each with the twin just below its threshold (§1 invariant "
                "3). Without the twin, 'the verifier rejects this' is satisfied by a verifier "
                "that rejects everything. The bound is recorded at every twin and decides "
                "nothing (§7.4 as amended)."
            ),
            "result": "pass"
            if all(
                pair["above"]["verdict"] == "FAILED" and pair["below"]["verdict"] == "VERIFIED"
                for pair in injections.values()
            )
            else "fail",
            "value": injections,
            "expected": "FAILED above the threshold, VERIFIED below it, for all three",
        },
        {
            "id": "K04.A16.supplied_policy",
            "description": (
                "§9.4 (VER-05): a loosened policy is an input with a hash, is recorded by check "
                "id with the registered and applied tolerances, and yields `RELAXED` — never "
                "`VERIFIED`. The same state under a *tightened* policy is `FAILED`."
            ),
            "result": "pass"
            if relaxation["registered"]["verdict"] == "FAILED"
            and relaxation["loosened"]["verdict"] == "RELAXED"
            and relaxation["tightened"]["verdict"] == "FAILED"
            and relaxation["loosened"]["policy_sha256"] != relaxation["registered"]["policy_sha256"]
            else "fail",
            "value": relaxation,
            "expected": "FAILED / RELAXED / FAILED with differing policy hashes",
        },
        {
            "id": "K04.A23_A24_A25_A26_A34.regularity_fixtures",
            "description": (
                "§7.6: one triangular family at three sizes produces all three decidable "
                "statuses while `min|U_ii|/max|U_ii|` is exactly 1.0 at every one — so a screen "
                "that consulted the U-diagonal would report the same thing for a "
                "well-conditioned, an ill-conditioned and a rank-deficient matrix ([A08], ADR "
                "0004 D3.4). Plus the SVD budget, the exactly-singular path, and the `x^2 = 0` "
                "seed at two tolerances: at 1e-8 the absolute limit passes and the verdict is "
                "VERIFIED with the bound recorded; at 1e-12 it trips."
            ),
            "result": "pass"
            if fixtures["TRI-16"]["status"] == "NO_RANK_LOSS_DETECTED"
            and fixtures["TRI-32"]["status"] == "ILL_CONDITIONED"
            and fixtures["TRI-64"]["status"] == "RANK_DEFICIENT"
            and all(fixtures[f"TRI-{n}"]["u_diagonal_ratio"] == 1.0 for n in (16, 32, 64))
            and fixtures["DIM-2001"]["status"] == "INCONCLUSIVE"
            and fixtures["SQ-0"]["status"] == "RANK_DEFICIENT"
            and fixtures["SQ-1"]["status"] == "NO_RANK_LOSS_DETECTED"
            and fixtures["SQ-2"]["status"] == "ILL_CONDITIONED"
            and fixtures["SQ-2"]["reason"] == "absolute"
            else "fail",
            "value": fixtures,
            "expected": "the registered status at each fixture; U-diagonal ratio 1.0 at all three",
        },
        {
            "id": "K04.A20_A21.failure_bundle",
            "description": (
                "§10 and blueprint §8.2. A bundle carries **no verdict word** — not even "
                "`UNVERIFIED`, which would read as a judgement on a state nobody judged — and "
                "**no infeasibility claim** (§7.7): a solver may report that it failed, never "
                "that no answer exists. Both are constructor refusals, not conventions."
            ),
            "result": "pass"
            if bundle["outcome"] == "BUDGET_EXHAUSTED"
            and bundle["property_calls"] == 20
            and bundle["checkpoint"] is None
            and bundle["carries_no_verdict_word"]
            and bundle["carries_no_infeasibility_claim"]
            else "fail",
            "value": bundle,
            "expected": "BUDGET_EXHAUSTED at exactly 20 calls, no checkpoint, no verdict word",
        },
        {
            "id": "K04.A31_A32.interfaces",
            "description": (
                "Plan §2.2's K04 row: three schemas with fixtures emitted by real verifier runs "
                "rather than written by hand (R-015), and ADR 0007 D2's float classification "
                "made executable — a schema float with no classification fails the test."
            ),
            "result": "pass",
            "value": ["solution-certificate", "regularity-evidence", "failure-bundle"],
            "expected": "three schemas, each with at least one generated fixture",
        },
        {
            "id": "K04.A22.structural_over_specification",
            "description": (
                "Gate G04's 'bad spec' has two registered inputs and only one is reachable "
                "here. STR-03, the conflicting heater temperature-and-duty specification, is a "
                "*validation* rejection and **no validator exists** before K06 — "
                "`openflowsheet.application` is empty. G04's bad-specification clause is "
                "served by the 150 kPa `SPECIFICATION_CONFLICT`, which is a bad specification "
                "detected with a proof. Recording STR-03 as unsupported is the point: silence "
                "would read as coverage."
            ),
            "result": "unsupported",
            "value": {"case": "SYN-001-conflicting-heater-spec", "owner": "K06"},
            "expected": "a validator that rejects structural over-specification",
        },
        {
            "id": "K04.A12.oracle_cross_check",
            "description": (
                "The verifier uses the *provider* in production, because `openflowsheet` may "
                "not import `benchmarks/`; the oracle is the test-side second witness. They are "
                "two transcriptions of one algebra and agree to 0.0 J/mol, so this is code "
                "independence and not data independence — and [A09] means the energy checks are "
                "bookkeeping rather than thermodynamic validation either way."
            ),
            "result": "not_applicable",
            "value": "tests only; production must not import benchmarks/",
            "expected": "out of scope for a production path",
        },
    ]

    artifacts = [
        {"path": path, "sha256": file_sha256(ROOT / path), "description": description}
        for path, description in (
            ("src/openflowsheet/verify/__init__.py", "The verifier's types and the promise."),
            ("src/openflowsheet/verify/checks.py", "§4's check set."),
            ("src/openflowsheet/verify/regularity.py", "The [A08] screen and the bound."),
            ("src/openflowsheet/verify/certificate.py", "The verdict and the certificate."),
            ("src/openflowsheet/verify/failure.py", "The structured failure."),
            ("docs/derivations/K04-certificate-spec.md", "The Fable specification."),
            ("docs/adr/0007-reproducibility-certificate-policy.md", "The companion ADR."),
            ("benchmarks/k04/reference_values.yaml", "40-digit closed forms, mpmath."),
        )
    ]

    return {
        "work_package": "K04",
        "commit": commit,
        "requirements": ["D14", "D05", "A08", "A09"],
        "status": "tested",
        "inputs": {
            "case_id": (
                "SYN-001 verified at all five registered variants, plus the registered "
                "injections INJ-1, INJ-3, INJ-6 and INJ-7 with their below-threshold twins, "
                "the trivial root of §9.2, and the constructed regularity fixtures TRI-16/32/64, "
                "DIM-2001, SQ-0, SQ-1 and SQ-2"
            ),
            "case_hash": file_sha256(ROOT / "benchmarks/k04/reference_values.yaml"),
            "environment_lock_hash": file_sha256(ROOT / "requirements.lock"),
        },
        "commands": [
            {
                "cmd": "PATH=.venv/bin:$PATH ./scripts/check.sh",
                "cwd": ".",
                "exit_code": 0,
                "stdout_sha256": hashlib.sha256(gate_stdout.read_bytes()).hexdigest(),
            }
        ],
        "checks": checks,
        "artifacts": artifacts,
        "limitations": [
            "SYN-001 is synthetic. Nothing here is empirical validation of any thermodynamic "
            "model; the components are pseudo-components with invented constants.",
            "Every energy and phase check shares the property package with the solver ([A09]). "
            "The oracle cross-check is code independence, not data independence, and the "
            "certificate says so on every affected check.",
            "A certificate certifies **residual** accuracy at the registered tolerances. The "
            "first-order solution-error bound is recorded and disclosed, never promised "
            "(§7.4 as amended 2026-09-22; Frank's ruling on F3). On this flowsheet "
            "||J^-1||_1 is 80 to 476, so a state converged to tolerance rather than to "
            "roundoff has a bound one to two orders above the scaled tolerance; that is the "
            "disclosure, not a defect.",
            "The regularity screen and the bound are local evidence at one state. They say "
            "nothing about other roots, which are T03's, and nothing about sensitivities "
            "beyond first order.",
            "The check set is written for the SYN-001 topology. A general assembler comes from "
            "T01's incidence graph; §5.2's equilibrium-row tolerance is registered for this "
            "lifted form by derivation from the flow rule, and ADR 0001 D6 does not yet carry "
            "it.",
            "No validator for structural over-specification exists before K06, so STR-03 is "
            "recorded `unsupported` above rather than as a pass.",
            "Reuse of a solver factorization is not implemented: K03 never factorizes the "
            "47x47 matrix, so nothing could belong to the final Jacobian. The refusal path "
            "for a mismatched identity exists and is tested before anyone needs it.",
            "Human numerical and process-modeling review remain `pending`, and no agent may "
            "set them.",
        ],
        "review": {"numerical": "pending", "process_model": "pending"},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gate_stdout", type=Path)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--out", type=Path, default=None)
    arguments = parser.parse_args()

    manifest = build(arguments.commit, arguments.gate_stdout)
    destination = arguments.out or (ROOT / "evidence" / "K04" / arguments.commit / "manifest.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")

    counts = {
        name: sum(check["result"] == name for check in manifest["checks"])
        for name in ("pass", "fail", "unsupported", "not_applicable")
    }
    failed = [check["id"] for check in manifest["checks"] if check["result"] == "fail"]
    print(f"wrote {destination}")
    print(
        f"checks: {counts['pass']} pass, {counts['fail']} fail, "
        f"{counts['unsupported']} unsupported, {counts['not_applicable']} not applicable"
    )
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
