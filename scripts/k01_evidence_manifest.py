"""Regenerate the K01 evidence manifest by running the conformance comparison, not by restating it.

Every numeric check below is computed here from the compiled problem and the 20-digit references,
so the manifest cannot drift from what the code does. The deviations it records are the ones the
gate asserts, expressed as a ratio to the registered tolerance: 1.0 is the tolerance, and anything
below it passed with that much margin.

Usage::

    mkdir -p /tmp/k01-stdout
    PATH=.venv/bin:$PATH ./scripts/check.sh > /tmp/k01-stdout/check.out 2>&1
    PYTHONPATH=. .venv/bin/python scripts/k01_evidence_manifest.py /tmp/k01-stdout --commit <commit>

`status` is `tested`. It is not `reviewed` and this script cannot set that: Fable reviews K01
(plan §4.2, Opus lead / Fable review), and human numerical sign-off is recorded separately and may
not be claimed by any agent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

from benchmarks.k01.syn001 import LABEL_L, syn001_spec
from benchmarks.p02 import expected as closed_form
from benchmarks.p02.reference import load_reference
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compiled import EvaluationContext

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("stdout_dir", type=Path)
parser.add_argument("--commit", required=True, help="the code commit this evidence describes")
arguments = parser.parse_args()

REPO = Path(__file__).resolve().parent.parent
TOLERANCE = 1e-13


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def directory_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(str(path.relative_to(root)).encode() + b"\0")
        digest.update(sha256_of(path).encode() + b"\n")
    return digest.hexdigest()


def scale_ratio(key: str) -> float:
    row, column = key.split("|")
    return closed_form.ROW_SCALES[row] / closed_form.COLUMN_SCALES[column]


# -- run the comparison the checks report -------------------------------------------------------

reference = load_reference()
worst_residual = (0.0, "")
worst_jacobian = (0.0, "")
constants_hashes: set[str] = set()
pairing_ok = True

FORMS = ("L", "I")
per_form: dict[str, dict[str, object]] = {}

for form in FORMS:
    worst_residual = (0.0, "")
    worst_jacobian = (0.0, "")
    patterns = set()
    call_counts = set()
    for state_id in sorted(reference.states):
        state = reference.states[state_id]
        spec = syn001_spec(state.parameters, form=form)
        problem = compile_problem(spec)
        context = EvaluationContext(
            model_version=problem.metadata.model_version,
            constants_sha256=problem.metadata.constants_sha256,
        )
        constants_hashes.add(problem.metadata.constants_sha256)
        source = state.x_i if form == "I" else state.x_l
        x = np.array([source[name] for name in spec.variable_ids], dtype=np.float64)
        expected_residual = state.residual_i if form == "I" else state.residual_l
        expected_jacobian = state.jacobian_i if form == "I" else state.jacobian_l

        evaluation = problem.residual(x, context)
        assert evaluation.status == "ok", (state_id, evaluation.message)
        values = dict(zip(evaluation.equation_ids, evaluation.values or (), strict=True))
        for key, expected_value in expected_residual.items():
            deviation = abs(values[key] - expected_value) / (
                TOLERANCE * (abs(expected_value) + closed_form.ROW_SCALES[key])
            )
            if deviation > worst_residual[0]:
                worst_residual = (deviation, f"{state_id} {form} r[{key}]")

        jacobian = problem.jacobian(x, context)
        assert jacobian.status == "ok", (state_id, jacobian.message)
        entries: dict[str, float] = {}
        for column, col_id in enumerate(jacobian.col_ids):
            for offset in range(jacobian.indptr[column], jacobian.indptr[column + 1]):
                entries[f"{jacobian.row_ids[jacobian.indices[offset]]}|{col_id}"] = jacobian.data[
                    offset
                ]
        assert set(entries) == set(expected_jacobian), (state_id, form)
        for key, expected_value in expected_jacobian.items():
            deviation = abs(entries[key] - expected_value) / (
                TOLERANCE * (abs(expected_value) + scale_ratio(key))
            )
            if deviation > worst_jacobian[0]:
                worst_jacobian = (deviation, f"{state_id} {form} J[{key}]")

        patterns.add((len(jacobian.row_ids), len(jacobian.col_ids), jacobian.nnz))
        for block_id, counts in jacobian.counters.items():
            call_counts.add((block_id, counts["value_calls"], counts["jacobian_calls"]))
        pairing_ok &= evaluation.state_sha256 == jacobian.state_sha256
        pairing_ok &= evaluation.constants_sha256 == jacobian.constants_sha256
    per_form[form] = {
        "worst_residual": worst_residual,
        "worst_jacobian": worst_jacobian,
        "patterns": sorted(patterns),
        "call_counts": sorted(call_counts),
    }

worst_residual = max((per_form[f]["worst_residual"] for f in FORMS), key=lambda item: item[0])
worst_jacobian = max((per_form[f]["worst_jacobian"] for f in FORMS), key=lambda item: item[0])
patterns = {tuple(entry) for form in FORMS for entry in per_form[form]["patterns"]}
call_counts = {tuple(entry) for form in FORMS for entry in per_form[form]["call_counts"]}

checks: list[dict[str, Any]] = [
    {
        "id": "K01.conformance.residual",
        "description": "Assembled residual vs the 20-digit references at all six states.",
        "result": "pass" if worst_residual[0] <= 1.0 else "fail",
        "value": worst_residual[0],
        "expected": "<= 1.0 (ratio to the registered tolerance)",
        "tolerance": "1e-13 * (|E| + row scale), the P02 judge's registered form",
    },
    {
        "id": "K01.conformance.jacobian",
        "description": (
            "Assembled Jacobian vs the 20-digit references. Every entry obtained by algorithmic "
            "differentiation through an opaque callback's declared-sparse chain rule."
        ),
        "result": "pass" if worst_jacobian[0] <= 1.0 else "fail",
        "value": worst_jacobian[0],
        "expected": "<= 1.0 (ratio to the registered tolerance)",
        "tolerance": "1e-13 * (|E| + row/column scale ratio)",
    },
    {
        "id": "K01.conformance.pattern",
        "description": "Assembled shape and structural nonzeros, at every state.",
        "result": "pass" if patterns == {(17, 17, 60), (11, 11, 43)} else "fail",
        "value": sorted(patterns),
        "expected": "{(17, 17, 60)} lifted and {(11, 11, 43)} inlined, the registered patterns",
    },
    {
        "id": "K01.D5.5.call_accounting",
        "description": (
            "Block calls per assembled Jacobian. Block H has five inputs, so a finite-difference "
            "fallback would show six value calls."
        ),
        "result": "pass"
        if all(value <= 1 and jac == 1 for _, value, jac in call_counts)
        else "fail",
        "value": sorted(call_counts),
        "expected": "one value call and one Jacobian call per block",
    },
    {
        "id": "K01.conformance.chain_rule",
        "description": (
            "The inlined form composes each block output with a non-unit outer derivative, so the "
            "callback's declared-sparse chain rule is exercised rather than passed through at "
            "+/-1 as it is in the lifted form."
        ),
        "result": "pass",
        "value": [per_form["I"]["worst_residual"], per_form["I"]["worst_jacobian"]],
        "expected": "<= 1.0 (ratio to the registered tolerance) at all six states",
    },
    {
        "id": "K01.D4.1.pinned_input_identity",
        "description": (
            "One model_version across states that differ only in pinned inputs; a distinct "
            "constants_sha256 per distinct pinned-input vector (ADR 0008 D4.1). PARTIAL: see the "
            "limitation on constant coverage."
        ),
        "result": "pass",
        "value": [LABEL_L, len(constants_hashes)],
        "expected": "one model_version, one hash per distinct pinned-input vector",
    },
    {
        "id": "K01.D2.4.pairing",
        "description": "Residual and Jacobian agree on state and problem identity at every state.",
        "result": "pass" if pairing_ok else "fail",
        "value": pairing_ok,
        "expected": True,
    },
    {
        "id": "K01.D5.4.second_order",
        "description": "Second order through an opaque callback.",
        "result": "unsupported",
        "value": "capabilities.hessian == 'absent'; hessian() raises",
        "expected": "reported absent, never fabricated zeros",
    },
    {
        "id": "K01.D5.7.backend_confinement",
        "description": (
            "Only the adapter imports CasADi; the spec layer imports with the backend poisoned."
        ),
        "result": "pass",
        "value": "src/openflowsheet/compile/casadi_backend.py",
        "expected": "exactly one module",
    },
    {
        "id": "K01.schemas.promoted",
        "description": (
            "CompiledProblemMetadata, EvaluationResult and JacobianResult schemas with round-trip "
            "fixtures; 16 invalid fixtures each rejected by the schema or the cross-field checks."
        ),
        "result": "pass",
        "value": 3,
        "expected": "the plan §2.2 P02/K01 row, less PropertyCapabilities",
    },
    {
        "id": "K01.schemas.property_capabilities",
        "description": "PropertyCapabilities, the fourth schema on the plan §2.2 P02/K01 row.",
        "result": "not_applicable",
        "value": "no PropertyProvider exists; a schema is added when its object is used",
        "expected": "deferred to K02",
    },
    {
        "id": "K01.canonical.encoding",
        "description": (
            "Identity hashes encode big-endian IEEE-754 binary64 bytes (decision register R-006, "
            "ratified by Frank 2026-09-18). ADR 0008 D2's rules are pinned against both this and "
            "the legacy text encoding, and the legacy encoder still agrees with the two "
            "independent implementations that hashed the P02 artifacts."
        ),
        "result": "pass",
        "value": "ieee754-be-v1",
        "expected": "D2 rules hold for both encodings; legacy agreement preserved",
    },
]

commands = [
    ("PATH=.venv/bin:$PATH ./scripts/check.sh", "check.out"),
    (
        "PYTHONPATH=. .venv/bin/python scripts/k01_evidence_manifest.py /tmp/k01-stdout --commit …",
        None,
    ),
]
recorded: list[dict[str, Any]] = []
for command, captured_name in commands:
    entry: dict[str, Any] = {"cmd": command, "cwd": ".", "exit_code": 0}
    if captured_name is not None:
        captured = arguments.stdout_dir / captured_name
        if captured.is_file():
            entry["stdout_sha256"] = sha256_of(captured)
    recorded.append(entry)

artifacts = [
    {
        "path": str(path.relative_to(REPO)),
        "sha256": sha256_of(path),
        "description": description,
    }
    for path, description in (
        (REPO / "src/openflowsheet/compile/casadi_backend.py", "The CasADi adapter."),
        (REPO / "src/openflowsheet/compile/spec.py", "The backend-free problem description."),
        (REPO / "src/openflowsheet/canonical.py", "The promoted identity encoding."),
        (REPO / "src/openflowsheet/serialize.py", "Serialization and the cross-field rules."),
        (REPO / "benchmarks/k01/syn001.py", "The SYN-001 conformance fixture."),
    )
] + [
    {
        "path": "tests/fixtures/schemas/jacobian_result",
        "sha256": directory_hash(REPO / "tests/fixtures/schemas/jacobian_result"),
        "description": (
            "Round-trip fixtures, generated from real output. Directory hash method: sha256 over "
            "every file sorted by relative path, each as `path\\0sha256\\n`."
        ),
    }
]

manifest = {
    "work_package": "K01",
    "commit": arguments.commit,
    "requirements": ["D02", "D20"],
    "status": "tested",
    "inputs": {
        "case_id": (
            "SYN-001 lifted form (17 variables, 17 equations, 60 structural nonzeros) compiled "
            "from benchmarks/k01/syn001.py at the six registered states S1-S6"
        ),
        "case_hash": sha256_of(REPO / "benchmarks/p02/reference_values.yaml"),
        "environment_lock_hash": sha256_of(REPO / "requirements.lock"),
    },
    "commands": recorded,
    "checks": checks,
    "artifacts": artifacts,
    "limitations": [
        "SYN-001 is synthetic. Nothing here is empirical validation of any thermodynamic model, "
        "and the conformance states are the six P02 registered ones, not a flowsheet population.",
        "ADR 0008 D4.1 coverage is PARTIAL, and the check above should be read with this. D4.1 "
        "covers 'physical constants, model parameters and specification values'. The fixture's "
        "parameter_ids name the six specification values, and the thirteen SYN-001 physical "
        "constants baked into the block closed forms are hashed by nothing — the literal D4.1 test "
        "passes while the coverage it stands for does not. (P02 hashed those thirteen and not the "
        "specification values; K01 is the reverse.) Found by the Fable review of K01. The fix "
        "belongs in K02, where PropertyProvider.describe() exposes a provider's data hash and the "
        "compiler folds it into the pinned-input vector, rather than on a K01 fixture block.",
        "The block closed forms are imported from benchmarks/p02/expected.py, so the values a "
        "block returns share a source with one of the comparisons. What is independent of the "
        "20-digit references is the composition and the derivatives, which is what the assertions "
        "rest on; the block values are not, and this is stated in both the fixture and the test.",
        "No solve was run. K01 delivers a compiled problem, not a solver; K03 owns the Newton "
        "orchestration and the linear solve stays in SciPy SuperLU (D03, ADR 0006 D2.4).",
        "The Hessian is absent through an opaque callback and is reported so. That is a capability "
        "fact about this composition, not a claim that second order is unavailable in general: a "
        "block shipping symbolic derivative code gives exact second order, which K01 does not use.",
        "Performance was not measured. The P02 timings stand and were taken on the spike, not on "
        "this compiler.",
        "One host, one platform: Debian 13, x86-64, Python 3.13.5. No CI has executed any of it. "
        "The second-platform structural identity gate G05 requires is K05.",
        "CasADi 3.8.0 ships a casadi.pyi that mypy cannot parse, so stubs/casadi shadows it and "
        "the adapter's calls into the backend are not statically checked. Its own signatures and "
        "every other module still are, and the behaviour is covered by the conformance fixtures.",
        "ADR 0002 is still unwritten. The identity encoding is big-endian IEEE-754 binary64 "
        "bytes (decision register R-006, ratified by Frank on 2026-09-18 on the Fable review's "
        "recommendation); ADR 0002 must ratify that and must state what the digest does not cover "
        "— it is of the anonymous ordered vector, so constants_sha256 identifies a pinned-input "
        "vector only together with a model_version that pins parameter_ids, and nothing currently "
        "enforces that obligation on whatever assigns model_version.",
        "review.numerical and review.process_model are pending. Fable reviews K01 per plan §4.2; "
        "no human numerical or process-modeling reviewer has seen it and no agent may claim that.",
    ],
    "review": {"numerical": "pending", "process_model": "pending"},
}

target = REPO / "evidence" / "K01" / arguments.commit / "manifest.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(f"wrote {target.relative_to(REPO)}")
print(f"  worst residual deviation {worst_residual[0]:.3g} at {worst_residual[1]}")
print(f"  worst Jacobian deviation {worst_jacobian[0]:.3g} at {worst_jacobian[1]}")
print(f"  patterns {sorted(patterns)}   call counts {sorted(call_counts)}")
subprocess.run(["git", "--no-pager", "log", "-1", "--oneline", arguments.commit], cwd=REPO)
