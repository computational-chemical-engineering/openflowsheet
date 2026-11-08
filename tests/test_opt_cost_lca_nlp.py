"""OPT WO-7 gates G19 (OPT-C, cost) and G20 (OPT-L, LCA), design §6: `optimize_revision` on S11's
TH-C1 under E01's TAC program and under P4's climate impact.

The expectations are `benchmarks/opt/cost_lca.json`, computed by `benchmarks/opt/cost_lca.py`
from certified production re-solves of TH-C1 (the simulation path) and E01's hand models
(`benchmarks/e01/cost_hand`, `benchmarks/e01/lca_hand`), by a golden-section search (G19) and a
bisection (G20) — never by the optimiser or the assessment code under test. The candidate's
assessment values (V6, the float path at V1's certified state) are compared with the hand models
at a fresh certified re-solve of the candidate (`cost_lca.py --at`, run in an interpreter with
mpmath: the audited environment has none — `OPENFLOWSHEET_HAND_PYTHON`, else the main checkout's
`.venv`). Audited NLP environment only (`scripts/m03_nlp_check.sh`, `OMP_NUM_THREADS=1`).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from openflowsheet.application.policies import DEFAULT_POLICY_ID, resolve_policy
from openflowsheet.application.types import schema_errors
from openflowsheet.studies.nlp.revision import OptimizationOutcome, optimize_revision
from openflowsheet.verify.certificate import CheckPolicy

pytestmark = pytest.mark.nlp

REPO = Path(__file__).resolve().parents[1]
OPT = REPO / "benchmarks" / "opt"
EXPECTED = json.loads((OPT / "cost_lca.json").read_bytes())
POLICY = resolve_policy(DEFAULT_POLICY_ID, "revision_eo")
assert POLICY is not None


def _python() -> str:
    """An interpreter with mpmath for the hand models: this one if it has it, else
    `OPENFLOWSHEET_HAND_PYTHON`, else `<main checkout>/.venv/bin/python`."""
    try:
        import mpmath  # type: ignore[import-untyped]  # noqa: F401
    except ModuleNotFoundError:
        pass
    else:
        return sys.executable
    if os.environ.get("OPENFLOWSHEET_HAND_PYTHON"):
        return os.environ["OPENFLOWSHEET_HAND_PYTHON"]
    common = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    python = Path(common).parent / ".venv" / "bin" / "python"
    if not python.is_file():
        pytest.fail(f"no interpreter with mpmath for the hand models (tried {python})")
    return str(python)


def _hand_at(spec_id: str, value: float) -> dict[str, float]:
    """`cost_lca.py --at`: the hand TAC and GWP rate at a certified re-solve of TH-C1."""
    done = subprocess.run(
        [_python(), str(OPT / "cost_lca.py"), "--at", spec_id, repr(value)],
        env={**os.environ, "PYTHONPATH": str(REPO / "src")},
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    result: dict[str, float] = json.loads(done.stdout.splitlines()[-1])
    return result


@pytest.fixture(scope="module")
def records(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("opt-cost-lca")


@cache
def _run(case: str, directory: Path) -> OptimizationOutcome:
    document = json.loads((REPO / "benchmarks/s11/thermal/TH-C1.json").read_bytes())
    request = json.loads((OPT / "requests" / f"{case}.json").read_bytes())
    return optimize_revision(
        document,
        request,
        directory=directory / case,
        solve_policy=POLICY,
        check_policy=CheckPolicy(),
    )


def _report(case: str, records: Path) -> dict[str, Any]:
    report = _run(case, records).report.as_document()
    assert schema_errors("optimization-report.schema.json", report) == []
    assert report["status"] == "KKT_POINT_VERIFIED", report["reasons"]
    return report


def _checks(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {check["check"]: check for check in report["candidate"]["checks"]}


def test_g19_opt_c_reaches_the_golden_section_optimum_of_the_hand_tac(records: Path) -> None:
    """G19: KKT_POINT_VERIFIED, V7 passed, the decision interior (no bound active) and within
    1e-5·scale of the golden-section optimum; TAC at the candidate (V6) equals the hand TAC at
    the certified candidate state within 1e-9 relative."""
    report = _report("OPT-C", records)
    expected = EXPECTED["OPT-C"]
    candidate = report["candidate"]
    checks = _checks(report)
    assert checks["V7"]["outcome"] == "pass", checks["V7"]
    assert candidate["active_set"] == [], candidate["active_set"]
    pressure = candidate["decisions"][expected["decision"]]
    assert abs(pressure - expected["d_gs"]) <= expected["tolerance_decision"], (
        pressure,
        expected["d_gs"],
    )
    tac = _hand_at("SPEC-P-P", pressure)["tac"]
    reported = checks["V6"]["assessment_values"]["tac"]
    assert abs(reported - tac) <= 1e-9 * abs(tac), (reported, tac)
    assert reported >= expected["tac_at_d_gs"] * (1 - 1e-9), (reported, expected["tac_at_d_gs"])


def test_g20_opt_l_reaches_the_bisection_root_of_the_power_constraint(records: Path) -> None:
    """G20: KKT_POINT_VERIFIED, the power constraint active, the decision within 1e-6·scale of
    the bisection root W(T) = W_min; the GWP rate at the candidate (V6) equals the hand GWP at the
    certified candidate state within 1e-9 relative; its multiplier positive (GWP rises with T)."""
    report = _report("OPT-L", records)
    expected = EXPECTED["OPT-L"]
    candidate = report["candidate"]
    checks = _checks(report)
    assert checks["V7"]["outcome"] == "pass", checks["V7"]
    assert [item["name"] for item in candidate["active_set"]] == ["W-net-min"]
    temperature = candidate["decisions"][expected["decision"]]
    assert abs(temperature - expected["d_root"]) <= expected["tolerance_decision"], (
        temperature,
        expected["d_root"],
    )
    gwp = _hand_at("SPEC-B-T", temperature)["gwp"]
    reported = checks["V6"]["assessment_values"]["impact.climate_change_test.rate"]
    assert abs(reported - gwp) <= 1e-9 * abs(gwp), (reported, gwp)
    assert expected["gwp_slope_per_K"] > 0.0
    assert candidate["kkt"]["multipliers"]["W-net-min"] > 0.0, candidate["kkt"]
