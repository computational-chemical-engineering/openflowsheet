"""S05.A29: the mutation battery of spec §6.1 (`docs/derivations/S05-IAPWS95-spec.md`). S05.

Each mutation is a textual edit of `src/openflowsheet/thermo/iapws95.py`; every edit's old text
must occur in the module exactly once, or the battery refuses (a stale mutation is not a pass).
The battery runs the named assertion's test nodes once per mutation, in a fresh pytest process
that loads this file as a plugin (`-p s05_mutations`): `pytest_configure` executes the mutated
source in the imported module's namespace before any test module imports it. A mutation is
caught iff that run fails (exit code 1) and, where a mutation names one, the failure text holds
the expected substring (m7: the cp derivative). A control run of every named node with the
unmutated source executed the same way must pass, so the mechanism itself breaks nothing.

The module file on disk is never written; each run's output goes to `<logs>/s05-mutation-<id>.log`
and the summary, with each log's SHA-256, to `<logs>/s05-mutations.json`.

Usage:
    PYTHONPATH=src .venv/bin/python scripts/s05_mutations.py --logs DIR
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
MODULE = ROOT / "src" / "openflowsheet" / "thermo" / "iapws95.py"
TESTS = "tests/test_s05_iapws95.py"
#: The environment variable the plugin half reads: a mutation id, or `none` for the control.
ENV = "OFS_S05_MUTATION"
CONTROL = "none"


@dataclass(frozen=True)
class Mutation:
    id: str
    description: str
    #: The spec §6.1 assertion that must catch it, and the test nodes that judge that assertion.
    assertion: str
    nodes: tuple[str, ...]
    edits: tuple[tuple[str, str], ...]
    #: A substring the failing run's output must hold (empty: any failure of the nodes).
    expect: str = ""


MUTATIONS: tuple[Mutation, ...] = (
    Mutation(
        "m1",
        "drop Gaussian term 54 (the third of terms 52-54)",
        "A03",
        (f"{TESTS}::test_a03_phi_jet_orders_up_to_two[R6_647]",),
        (
            (
                "for n, d, t, alpha, beta, gamma, epsilon in coefficients.gaussian:",
                "for n, d, t, alpha, beta, gamma, epsilon in coefficients.gaussian[:2]:",
            ),
        ),
    ),
    Mutation(
        "m2",
        "flip the sign of n°₃",
        "A03",
        (f"{TESTS}::test_a03_phi_jet_orders_up_to_two",),
        (
            (
                "    n = coefficients.ideal_n\n",
                "    n = (*coefficients.ideal_n[:2], -coefficients.ideal_n[2], "
                "*coefficients.ideal_n[3:])\n",
            ),
        ),
    ),
    Mutation(
        "m3",
        "CODATA R (8.314462618 J/(mol K)) in place of R_s·M",
        "A05",
        (f"{TESTS}::test_a05_values",),
        (("R: Final = R_S * M", "R: Final = 8.314462618"),),
    ),
    Mutation(
        "m4",
        "ε_σ = 0",
        "A13",
        (f"{TESTS}::test_a13_band_probes",),
        (("EPS_SIGMA: Final = 1.0e-6", "EPS_SIGMA: Final = 0.0"),),
    ),
    Mutation(
        "m5",
        "T_c replaced by 647.0 K in step 2 of the phase rule (R-598)",
        "A15",
        (f"{TESTS}::test_a15_supercritical_label_and_the_647_edge",),
        (("    if temperature >= T_C:\n", "    if temperature > T_SIGMA_MAX:\n"),),
    ),
    Mutation(
        "m6",
        "omit the n_H2O derivative",
        "A07",
        (f"{TESTS}::test_a07_n_derivatives_are_exactly_zero",),
        (
            (
                "                    for wanted in request.derivatives\n",
                "                    for wanted in request.derivatives\n"
                "                    if wanted in slot\n",
            ),
        ),
    ),
    Mutation(
        "m7",
        "a zero third-order jet (every third partial of φ° and φʳ is 0.0)",
        "A06",
        (f"{TESTS}::test_a06_t_and_p_derivatives",),
        (
            (
                "    return _ideal_jet(tau, delta, coefficients), "
                "_residual_jet(tau, delta, coefficients)\n",
                "    zero = {'ddd': 0.0, 'ddt': 0.0, 'dtt': 0.0, 'ttt': 0.0}\n"
                "    return (\n"
                "        _ideal_jet(tau, delta, coefficients)._replace(**zero),\n"
                "        _residual_jet(tau, delta, coefficients)._replace(**zero),\n"
                "    )\n",
            ),
        ),
        expect="dcp/d",
    ),
    Mutation(
        "m8",
        "take ln((δ−1)²) at δ = 1 in place of the zero jet",
        "A03",
        (f"{TESTS}::test_a03_phi_jet_orders_up_to_two[delta_one]",),
        (
            (
                "    if x == 0.0:\n        return 0.0, 0.0, 0.0, 0.0\n",
                "    if x == 0.0:\n"
                "        return math.exp(0.5 * e * math.log(x * x)), 0.0, 0.0, 0.0\n",
            ),
        ),
    ),
)
BY_ID = {mutation.id: mutation for mutation in MUTATIONS}


def mutated_source(mutation: Mutation | None, source: str | None = None) -> str:
    """The module's source with `mutation`'s edits; each old text must occur exactly once."""
    text = MODULE.read_text(encoding="utf-8") if source is None else source
    for old, new in mutation.edits if mutation is not None else ():
        count = text.count(old)
        if count != 1:
            raise ValueError(f"{mutation.id}: {old!r} occurs {count} times in {MODULE.name}")
        text = text.replace(old, new)
    return text


# -- the plugin half (`pytest -p s05_mutations`) -------------------------------------------------


def pytest_configure(config: Any) -> None:
    """Execute the mutated module source in the imported module's namespace (before collection)."""
    del config
    name = os.environ.get(ENV)
    if not name:
        return
    import openflowsheet.thermo.iapws95 as module

    mutation = None if name == CONTROL else BY_ID[name]
    code = compile(mutated_source(mutation), str(MODULE), "exec")
    exec(code, module.__dict__)  # noqa: S102 (the battery's purpose)


# -- the battery ---------------------------------------------------------------------------------


def _run(name: str, nodes: tuple[str, ...], log: Path) -> dict[str, Any]:
    environment = {
        **os.environ,
        ENV: name,
        "PYTHONPATH": os.pathsep.join([str(ROOT / "src"), str(ROOT / "scripts")]),
    }
    command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p"]
    completed = subprocess.run(
        [*command, "s05_mutations", *nodes],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    output = completed.stdout + completed.stderr
    log.write_text(output, encoding="utf-8")
    counts = {
        kind: int(number)
        for number, kind in re.findall(r"(\d+) (passed|failed|error|errors)\b", output)
    }
    return {
        "exit_code": completed.returncode,
        "outcomes": counts,
        "output": output,
        "log": log,
        "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
    }


def battery(logs: Path) -> dict[str, Any]:
    """Run the control and every mutation; the summary is JSON-ready (paths as strings)."""
    logs.mkdir(parents=True, exist_ok=True)
    for mutation in MUTATIONS:  # refuse a stale edit before running anything
        mutated_source(mutation)
    every_node = tuple(dict.fromkeys(node for m in MUTATIONS for node in m.nodes))
    control = _run(CONTROL, every_node, logs / "s05-mutation-control.log")
    entries: list[dict[str, Any]] = []
    for mutation in MUTATIONS:
        ran = _run(mutation.id, mutation.nodes, logs / f"s05-mutation-{mutation.id}.log")
        caught = (
            ran["exit_code"] == 1
            and ran["outcomes"].get("failed", 0) >= 1
            and mutation.expect in ran["output"]
        )
        entries.append(
            {
                "id": mutation.id,
                "mutation": mutation.description,
                "assertion": mutation.assertion,
                "nodes": list(mutation.nodes),
                "expect": mutation.expect,
                "exit_code": ran["exit_code"],
                "outcomes": ran["outcomes"],
                "caught": caught,
                "log": ran["log"].name,
                "log_sha256": ran["log_sha256"],
            }
        )
    control_passed = control["exit_code"] == 0
    return {
        "control": {
            "nodes": list(every_node),
            "exit_code": control["exit_code"],
            "outcomes": control["outcomes"],
            "passed": control_passed,
            "log": control["log"].name,
            "log_sha256": control["log_sha256"],
        },
        "mutations": entries,
        "result": "pass" if control_passed and all(e["caught"] for e in entries) else "fail",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--logs", type=Path, required=True, help="directory for logs and summary")
    arguments = parser.parse_args()
    summary = battery(arguments.logs)
    out = arguments.logs / "s05-mutations.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    caught = sum(1 for entry in summary["mutations"] if entry["caught"])
    print(
        f"S05.A29 {summary['result']}: {caught}/{len(MUTATIONS)} mutations caught, control "
        f"{'passed' if summary['control']['passed'] else 'FAILED'}"
    )
    return 0 if summary["result"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
