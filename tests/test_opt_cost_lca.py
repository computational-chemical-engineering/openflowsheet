"""OPT WO-7, G19/G20's default-environment half (design §6): the cost and LCA benchmark's
requests and expectations (`benchmarks/opt/cost_lca.py`) are current, its assessment documents are
E01's own (P1, P4), and its recorded expectations reproduce at their points. The optimiser runs
in `tests/test_opt_cost_lca_nlp.py` (audited environment). The full searches are re-run by
`python benchmarks/opt/cost_lca.py --check`.
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from functools import cache
from pathlib import Path
from types import ModuleType

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_e01_a_report import P1_DOC  # noqa: E402
from test_e01_b_lca import P4_DOC  # noqa: E402

from openflowsheet.application import validation  # noqa: E402
from openflowsheet.application.revision_routes import REVISION_ROUTES
from openflowsheet.application.types import schema_errors  # noqa: E402
from openflowsheet.studies.nlp.closure import SolverAvailability  # noqa: E402
from openflowsheet.studies.nlp.request import static_readiness  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
OPT = REPO / "benchmarks" / "opt"
EXPECTED = json.loads((OPT / "cost_lca.json").read_bytes())


@cache
def _hand() -> ModuleType:
    spec = importlib.util.spec_from_file_location("opt_cost_lca", OPT / "cost_lca.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_assessment_documents_are_e01s_p1_and_p4() -> None:
    hand = _hand()
    assert hand.P1_DOC == P1_DOC
    assert hand.P4_DOC == P4_DOC


@pytest.mark.parametrize("case", ["OPT-C", "OPT-L"])
def test_the_committed_requests_are_current_valid_and_ready(case: str) -> None:
    request = _hand().requests()[case]
    path = OPT / "requests" / f"{case}.json"
    assert path.read_bytes() == _hand()._bytes(request)
    assert schema_errors("optimization-request.schema.json", request) == []
    document = json.loads((REPO / "benchmarks/s11/thermal/TH-C1.json").read_bytes())
    available = SolverAvailability(True, "test double")
    readiness = static_readiness(
        request, document, solver_probe=lambda: available, routes=REVISION_ROUTES
    )
    assert readiness.ready, readiness.codes


@pytest.mark.parametrize("case", ["OPT-C", "OPT-L"])
def test_validate_warns_on_the_assessment_checks_it_defers(case: str) -> None:
    """Review S2 (D-83): with an assessment, the three checks D-18 defers to the first certified
    start are `WARN` ("not established statically"), never `PASS`; readiness stands."""
    request = _hand().requests()[case]
    document = json.loads((REPO / "benchmarks/s11/thermal/TH-C1.json").read_bytes())
    available = SolverAvailability(True, "test double")
    report = validation.validate(
        document, "optimization", optimization=request, solver_probe=lambda: available
    )
    assert report.status == "READY_FOR_OPTIMIZATION"
    deferred = {
        "OPT.ASSESSMENT_OUTPUT_UNKNOWN",
        "OPT.ASSESSMENT_PARAMETER_STRUCTURAL",
        "OPT.ASSESSMENT_PARAMETER_DECISION",
    }
    opt = {check.id: check for check in report.checks if check.id.startswith("OPT.")}
    assert {opt[i].result for i in deferred} == {"WARN"}
    assert all(opt[i].message.startswith("not established statically") for i in deferred)
    assert {check.result for i, check in opt.items() if i not in deferred} == {"PASS"}
    assert schema_errors("validation-report.schema.json", report.as_document()) == []


def test_the_hand_model_reproduces_p1() -> None:
    """The state → sizes → cost_hand chain on P1's own state equals the P1 fixture's sizes and
    operating cost (cost_hand's inputs) to rounding."""
    check = _hand().p1_check()
    assert check["sizes_worst_relative"] <= 1e-13, check
    assert check["opex_total_relative"] <= 1e-13, check


def test_the_recorded_expectations_reproduce_at_their_points() -> None:
    hand = _hand()
    cost, lca = EXPECTED["OPT-C"], EXPECTED["OPT-L"]
    a, b = cost["bracket"]
    assert b - a <= hand.GOLDEN_WIDTH and a <= cost["d_gs"] <= b
    assert hand.C_BOX[0] + 0.1 * (hand.C_BOX[1] - hand.C_BOX[0]) <= cost["d_gs"]
    assert cost["d_gs"] <= hand.C_BOX[1] - 0.1 * (hand.C_BOX[1] - hand.C_BOX[0])
    state = hand.certified_state("SPEC-P-P", cost["d_gs"])
    assert hand.regimes(state) == hand.C_REGIMES
    tac = float(hand.tac_hand(state)["tac"])
    assert math.isclose(tac, cost["tac_at_d_gs"], rel_tol=1e-9), (tac, cost["tac_at_d_gs"])
    a, b = lca["bracket"]
    assert b - a <= hand.BISECTION_WIDTH and lca["d_root"] == b
    assert hand.L_BOX[0] + 0.1 * (hand.L_BOX[1] - hand.L_BOX[0]) <= lca["d_root"]
    state = hand.certified_state("SPEC-B-T", lca["d_root"])
    assert hand.regimes(state) == hand.L_REGIMES
    assert hand.net_power(state) >= hand.W_MIN
    below = hand.certified_state("SPEC-B-T", a)
    assert hand.net_power(below) < hand.W_MIN
    gwp = float(hand.gwp_hand(state))
    assert math.isclose(gwp, lca["gwp_rate_at_d_root"], rel_tol=1e-9)
    assert lca["gwp_slope_per_K"] > 0.0
