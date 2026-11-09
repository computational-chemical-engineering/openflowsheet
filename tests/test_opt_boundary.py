"""OPT §9 A-1 (WO-5c): V1 on the phase-boundary form. Gates G10a–G10d (design §9.5), default env.

- **G10a** anchor: B with A = ∅ is the certificate's own matrix — its screen document equals the
  certificate's `regularity` document byte for byte (canonical JSON) at OPT-A1's and OPT-A3's V1
  states and at the certified starts of TH-R1, M1 and C-MW;
- **G10b** mechanism: along Q* − ΔQ on OPT-A3's flowsheet the certificate's rcond₁ is
  proportional to ΔQ (within 5 % of its ratio at 1 W) while B with A = {U-PHF} stays
  `NO_RANK_LOSS_DETECTED` with rcond₁ within 1 % of its value at 1 W;
- **G10c** negatives: a TWO_PHASE re-solve fails at (e2), a non-registered check policy at (e6),
  an empty boundary set at (e3), and no module under `verify/` or `orchestrator/` imports the
  boundary module;
- **G10d** VAPOR symmetry (OPT-A3v): a vapour feed cooled to its dew point — the certificate is
  rank-limited and (e1)–(e6) hold with A = {U-PHF} held VAPOR.

Q* and the dew point are mpmath roots (`benchmarks/opt/analytic.py`), independent of the code.
"""

from __future__ import annotations

import ast
import json
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from openflowsheet.application.policies import DEFAULT_POLICY_ID, resolve_policy
from openflowsheet.application.revision_routes import REVISION_ROUTES
from openflowsheet.canonical import canonical_json
from openflowsheet.orchestrator.revision import instances_of
from openflowsheet.orchestrator.splits import region_splits
from openflowsheet.studies.nlp import revision_host
from openflowsheet.studies.nlp.boundary import (
    BoundaryForm,
    CertificateTarget,
    boundary_form,
    certificate_target,
)
from openflowsheet.studies.nlp.host import CertifiedPoint
from openflowsheet.studies.nlp.revision_host import (
    DecisionBox,
    DecisionMap,
    RevisionNlpHost,
    decision_map,
)
from openflowsheet.studies.nlp.verification import TAU_ACTIVE
from openflowsheet.verify.certificate import CheckPolicy

REPO = Path(__file__).resolve().parents[1]
OPT = REPO / "benchmarks" / "opt"
S11 = REPO / "benchmarks" / "s11"
EXPECTED = json.loads((OPT / "expected.json").read_bytes())
POLICY = resolve_policy(DEFAULT_POLICY_ID, "revision_eo")
assert POLICY is not None
#: OPT-A3's bubble-point duty (mpmath) and Ipopt's candidate there (WO-5 gate log, D-37).
Q_STAR = float(EXPECTED["OPT-A3"]["Q"])
Q_HAT = 14232.354594159335
#: G10a's two V1 states on OPT-A1's flowsheet: OPT-A1's optimum (G7) and OPT-A3's candidate.
A1_OPTIMUM = 9000.00000009091
#: The perf flowsheets (G17) by case.
PERF = {"TH-R1": "thermal/TH-R1.json", "M1": "flowsheets/M1.json", "C-MW": "flowsheets/C-MW.json"}


def _host(
    document: Mapping[str, Any], boxes: list[DecisionBox], policy: CheckPolicy | None = None
) -> RevisionNlpHost:
    found = decision_map(document, boxes, routes=REVISION_ROUTES)
    assert isinstance(found, DecisionMap), found
    assert POLICY is not None
    return RevisionNlpHost(
        document,
        found,
        solve_policy=POLICY,
        check_policy=policy or CheckPolicy(),
        routes=REVISION_ROUTES,
    )


def _flowsheet(name: str) -> dict[str, Any]:
    return json.loads((OPT / "flowsheets" / f"{name}.json").read_bytes())  # type: ignore[no-any-return]


@cache
def _a3(policy_id: str | None = None) -> RevisionNlpHost:
    """OPT-A3's host (OPT-A1's flowsheet, decision `SPEC-Q`), its check policy registered or not."""
    policy = CheckPolicy() if policy_id is None else CheckPolicy(policy_id=policy_id)
    return _host(_flowsheet("OPT-A1"), [DecisionBox("SPEC-Q", 1000.0, 20000.0, "W")], policy)


def _at(host: RevisionNlpHost, value: float) -> CertifiedPoint:
    (parameter,) = host.decisions.parameters.values()
    return host.certify({parameter: value})


@cache
def _start() -> CertifiedPoint:
    """OPT-A3's revision start (Q = 10 500 W, held LIQUID)."""
    host = _a3()
    point = _at(host, host.base_spec().parameters[next(iter(host.decisions.parameters.values()))])
    assert point.verified, point.outcome
    return point


def _target(point: CertifiedPoint) -> CertificateTarget:
    handle = revision_host._handle(point)
    assert handle.route is not None and point.state is not None
    return certificate_target(handle.route.binding, handle.document, point.state)


def _heater(host: RevisionNlpHost, point: CertifiedPoint) -> Any:
    flowsheet = host.bound_flowsheet(point)
    splits = region_splits(instances_of(flowsheet), flowsheet.units(), flowsheet.components)
    (split,) = [split for split in splits.splits if split.unit == "U-PHF"]
    return split


# -- G10a ------------------------------------------------------------------------------------------


def _anchor(point: CertifiedPoint) -> BoundaryForm:
    assert point.certificate is not None and point.certificate.regularity is not None
    form = boundary_form(_target(point), ())
    assert form.splits == () and form.rows_removed == () and form.columns_removed == ()
    assert canonical_json(form.regularity.as_document()) == canonical_json(
        point.certificate.regularity.as_document()
    )
    return form


@pytest.mark.parametrize("value", [A1_OPTIMUM, Q_HAT], ids=["OPT-A1", "OPT-A3"])
def test_g10a_the_empty_boundary_form_is_the_certificates_matrix(value: float) -> None:
    point = _at(_a3(), value)
    form = _anchor(point)
    assert form.regularity.status == point.certificate.regularity.status  # type: ignore[union-attr]


@pytest.mark.parametrize("case", list(PERF))
def test_g10a_the_empty_boundary_form_at_the_certified_perf_starts(case: str) -> None:
    document = json.loads((S11 / PERF[case]).read_bytes())
    request = json.loads((OPT / "requests" / "perf" / f"{case}.json").read_bytes())
    boxes = [
        DecisionBox(item["specification_id"], item["lower"], item["upper"], item["unit"])
        for item in request["decisions"]
    ]
    host = _host(document, boxes)
    spec = host.base_spec()
    point = host.certify(
        {name: spec.parameters[name] for name in host.decisions.parameters.values()}
    )
    assert point.verified, (case, point.outcome)
    _anchor(point)


# -- G10b ------------------------------------------------------------------------------------------


def test_g10b_the_certificate_loses_rank_in_proportion_and_the_boundary_form_does_not() -> None:
    host = _a3()
    found: dict[float, tuple[float, BoundaryForm]] = {}
    for delta in (1.0, 0.1, 0.01, 1e-3, Q_STAR - Q_HAT):
        point = _at(host, Q_STAR - delta if delta != Q_STAR - Q_HAT else Q_HAT)
        assert point.state is not None and point.certificate is not None
        assert point.signature == (("U-PHF", "LIQUID"),), point.signature
        rcond = point.certificate.regularity.rcond_1
        form = boundary_form(_target(point), ((_heater(host, point), "LIQUID"),))
        assert form.regularity.status == "NO_RANK_LOSS_DETECTED", (delta, form.regularity)
        found[delta] = (rcond, form)
    ratio, b_one = found[1.0][0] / 1.0, found[1.0][1].regularity.rcond_1
    assert b_one is not None
    for delta, (rcond, form) in found.items():
        assert abs(rcond / delta - ratio) <= 0.05 * ratio, (delta, rcond / delta, ratio)
        b = form.regularity.rcond_1
        assert b is not None and abs(b - b_one) <= 0.01 * b_one, (delta, b, b_one)
    assert found[Q_STAR - Q_HAT][1].rows_removed == (
        "U-PHF:PHF-equilibrium:A",
        "U-PHF:PHF-equilibrium:B",
        "U-PHF:PHF-equilibrium:C",
        "U-PHF:Ndef:vapor",
    )
    assert found[Q_STAR - Q_HAT][1].columns_removed == ("S2.n.A", "S2.n.B", "S2.n.C", "S2.N")


def test_g10b_the_candidate_passes_and_is_admitted_with_q1_on_its_basis() -> None:
    """At Q̂ the clauses hold, the point gains a held system and regimes, and M03's sensitivity
    there passes Q1′ on basis `phase_boundary_form` (D-45) for the UNVERIFIED certificate."""
    host, start = _a3(), _start()
    point = _at(host, Q_HAT)
    assert point.outcome == "CERTIFICATE_NOT_VERIFIED"
    with pytest.raises(ValueError, match="not certified"):
        host.held_system(point)
    verdict = host.phase_boundary(
        point, host.held_system(start), host.phase_rows(start), tau_active=TAU_ACTIVE
    )
    assert verdict.passed, (verdict.clause, verdict.reason)
    detail = verdict.detail()
    assert detail["basis"] == "phase_boundary_form"
    assert detail["target_regularity"]["status"] == "ILL_CONDITIONED"
    assert detail["boundary_form"]["splits"] == ["U-PHF"]
    assert host.basis(point) == "phase_boundary_form"
    assert host.held_system(point).signature == (("U-PHF", "LIQUID"),)
    (split,) = host.regimes(point).splits
    assert split.regime == "LIQUID" and split.margin is not None and 0 < split.margin <= TAU_ACTIVE
    from openflowsheet.studies.sensitivity import OutputFunctional, StudyParameter

    (parameter,) = host.decisions.parameters.values()
    result = host.sensitivity(
        point,
        [StudyParameter(parameter, 10000.0, 1000.0, 20000.0)],
        [OutputFunctional("T", {"S3.T": 1.0}, 100.0)],
        mode="adjoint",
        held=("U-PHF",),
    )
    q1 = result.outcome("Q1'")
    assert q1.outcome == "pass" and q1.detail["basis"] == "phase_boundary_form", q1


# -- G10c ------------------------------------------------------------------------------------------


def test_g10c_i_a_two_phase_resolve_fails_at_e2() -> None:
    host, start = _a3(), _start()
    point = _at(host, Q_STAR + 1e-3)
    assert point.signature == (("U-PHF", "TWO_PHASE"),), point.signature
    verdict = host.phase_boundary(
        point, host.held_system(start), host.phase_rows(start), tau_active=TAU_ACTIVE
    )
    assert (verdict.passed, verdict.clause) == (False, "e2"), verdict
    assert verdict.detail() == {
        "basis": None,
        "phase_boundary_form": {"clause": "e2", "reason": verdict.reason},
    }


def test_g10c_ii_a_non_registered_check_policy_fails_at_e6() -> None:
    """The candidate re-solved under a non-registered policy (whose start would itself be
    `RELAXED`, so it is judged against the registered start's held system and rows)."""
    host, registered, start = _a3("opt-g10c-unregistered"), _a3(), _start()
    assert not host.check_policy.is_registered
    point = _at(host, Q_HAT)
    verdict = host.phase_boundary(
        point, registered.held_system(start), registered.phase_rows(start), tau_active=TAU_ACTIVE
    )
    assert (verdict.passed, verdict.clause) == (False, "e6"), verdict
    assert "RELAXED" in verdict.reason
    assert verdict.form is not None
    assert verdict.form.regularity.status == "NO_RANK_LOSS_DETECTED"


def test_g10c_iii_an_empty_boundary_set_fails_at_e3() -> None:
    host, start = _a3(), _start()
    point = _at(host, Q_HAT)
    verdict = host.phase_boundary(point, host.held_system(start), None, tau_active=TAU_ACTIVE)
    assert (verdict.passed, verdict.clause) == (False, "e3"), verdict
    with pytest.raises(ValueError, match="not certified"):
        host.held_system(point)


def test_g10c_iv_no_ordinary_certificate_path_imports_the_boundary_module() -> None:
    package = REPO / "src" / "openflowsheet"
    offenders: list[str] = []
    for directory in ("verify", "orchestrator"):
        for path in sorted((package / directory).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    names = [module, *(f"{module}.{alias.name}" for alias in node.names)]
                if any(name.startswith("openflowsheet.studies.nlp.boundary") for name in names):
                    offenders.append(str(path.relative_to(REPO)))
    assert offenders == []


# -- G10d ------------------------------------------------------------------------------------------


def test_g10d_a_vapour_cooled_to_its_dew_point_passes_with_the_split_held_vapor() -> None:
    """OPT-A3v: bisection on the cooler duty between the box's lower end (two-phase) and the
    start (−4000 W, VAPOR) to `0 < a/N0 ≤ 1e-9` (the gate's bound, D-50); there the outlet is the
    dew point within 1e-6 K (mpmath), the certificate rank-limited, and (e1)–(e6) hold with
    A = {U-PHF} held VAPOR (its liquid side pinned and its equilibrium rows dropped)."""
    expected = EXPECTED["OPT-A3v"]
    document = _flowsheet("OPT-A3v")
    host = _host(document, [DecisionBox("SPEC-Q", -20000.0, 0.0, "W")])
    start = _at(host, float(expected["start_Q"]))
    assert start.verified and start.signature == (("U-PHF", "VAPOR"),), start.outcome
    held, phase = host.held_system(start), host.phase_rows(start)
    assert phase.ids == (expected["phase_row"],) and phase.unguarded == ()
    (row,) = phase.ids

    def vapour(value: float) -> tuple[CertifiedPoint, float | None]:
        point = _at(host, value)
        if point.signature != held.signature or point.state is None:
            return point, None
        return point, phase.values(point.state)[row]

    low, high = -20000.0, float(expected["start_Q"])
    assert vapour(low)[1] is None
    for _ in range(80):
        middle = 0.5 * (low + high)
        point, value = vapour(middle)
        if value is not None and value > 0.0:
            high = middle
            if value <= 1e-9:
                break
        else:
            low = middle
    point, value = vapour(high)
    assert value is not None and 0.0 < value <= 1e-9, (high, value)
    assert point.state is not None and point.certificate is not None
    assert abs(point.state["S2.T"] - float(expected["T_dew"])) <= 1e-6, (high, point.state["S2.T"])
    assert point.certificate.verification_status == "UNVERIFIED"
    assert point.certificate.regularity.status in ("ILL_CONDITIONED", "RANK_DEFICIENT")
    verdict = host.phase_boundary(point, held, phase, tau_active=TAU_ACTIVE)
    assert verdict.passed, (high, verdict.clause, verdict.reason)
    assert verdict.form is not None and verdict.form.splits == ("U-PHF",)
    assert verdict.form.rows_removed == (
        "U-PHF:PHF-equilibrium:A",
        "U-PHF:PHF-equilibrium:B",
        "U-PHF:PHF-equilibrium:C",
        "U-PHF:Ndef:liquid",
    )
    assert verdict.form.columns_removed == ("S3.n.A", "S3.n.B", "S3.n.C", "S3.N")
    assert verdict.form.regularity.status == "NO_RANK_LOSS_DETECTED"
