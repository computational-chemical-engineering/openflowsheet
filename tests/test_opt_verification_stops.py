"""S19 WO-V step 0: the full record of `verify_candidate`'s three early stops, pinned.

`verify_candidate` (OPT §4.6, E01 §4.10.3) stops early in three places and returns a record with
the checks it could not judge `not_evaluated`: V1's stop (no simulation, or a revision host's
re-solve that V1 did not admit), the assessment's stop and the phase rows' stop. Each record is
pinned here field for field against an expectation built from the re-solve's own point and, for
the checks evaluated before the stop, from the same candidate's record without the stop (the
re-solve is deterministic, so those checks are the same function at the same state). The stops'
reason texts appear nowhere else in tests, scripts or benchmarks.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from functools import cache
from typing import Any

import pytest
from m03_support import flowsheet, nlp_formulation
from test_e01_b_nlp import bound, m03_readiness, program

from openflowsheet.studies.nlp import verification
from openflowsheet.studies.nlp.boundary import CERTIFICATE, BoundaryVerdict
from openflowsheet.studies.nlp.formulation import NlpFormulation
from openflowsheet.studies.nlp.host import CertifiedPoint, HeldSystem, Syn001NlpHost
from openflowsheet.studies.nlp.phase import PhaseRow, PhaseRows
from openflowsheet.studies.nlp.verification import (
    CHECKS,
    M03_CHECKS,
    CandidateVerification,
    verify_candidate,
)

#: The phase-boundary verdict the not-admitting host returns (a failed clause, OPT §9 A-1).
REFUSED = BoundaryVerdict(
    passed=False, clause="B1", reason="pinned refusal", certificate_status="NOT_VERIFIED"
)


class _Host(Syn001NlpHost):
    """SYN-001's host that records each re-solve point it returns, after `alter` edits it, and
    judges V1's phase-boundary basis as `REFUSED`."""

    def __init__(self, alter: Mapping[str, Any] | None = None) -> None:
        super().__init__(flowsheet({}))
        self.alter = dict(alter or {})
        self.points: list[CertifiedPoint] = []

    def certify(self, decisions: Mapping[str, float]) -> CertifiedPoint:
        point = dataclasses.replace(super().certify(decisions), **self.alter)
        self.points.append(point)
        return point

    def phase_boundary(
        self, point: CertifiedPoint, held: HeldSystem, phase: PhaseRows | None, *, tau_active: float
    ) -> BoundaryVerdict:
        return REFUSED


def _verify(
    host: _Host,
    formulation: NlpFormulation,
    *,
    held: HeldSystem | None = None,
    phase: PhaseRows | None = None,
) -> CandidateVerification:
    record = m03_readiness().starts[0]
    assert record.state is not None and record.regimes is not None
    return verify_candidate(
        host,
        formulation,
        record.start,
        regimes=record.regimes,
        optimizer_state=record.state,
        held=held,
        phase=phase,
    )


@cache
def _assessed() -> NlpFormulation:
    return bound(program(), "tac")


@cache
def _held() -> HeldSystem:
    host = _Host()
    return host.held_system(host.certify(_decisions(nlp_formulation())))


def _decisions(formulation: NlpFormulation) -> dict[str, float]:
    return dict(formulation.decision_values(m03_readiness().starts[0].start))


def _not_evaluated(reason: str) -> dict[str, Any]:
    return {"outcome": "not_evaluated", "reason": reason}


def _documents(result: CandidateVerification) -> dict[str, dict[str, Any]]:
    return {
        item.check: {k: v for k, v in item.as_document().items() if k != "check"}
        for item in result.checks
    }


def _stop_fields(result: CandidateVerification) -> dict[str, Any]:
    """Every field but `checks` and `point`, which the tests compare on their own."""
    fields = {item.name: getattr(result, item.name) for item in dataclasses.fields(result)}
    del fields["checks"], fields["point"]
    return fields


def _expected_stop(
    point: CertifiedPoint, formulation: NlpFormulation, basis: str | None
) -> dict[str, Any]:
    """The record of a stop after V1's stop let `point` pass: no values, the re-solve's identity."""
    assert point.certificate is not None and point.state is not None
    return {
        "decisions": _decisions(formulation),
        "objective": None,
        "constraint_values": {},
        "slacks": {},
        "active_set": (),
        "kkt": None,
        "certificate_id": point.certificate.certificate_id,
        "state_sha256": point.certificate.target_state_sha256,
        "simulation_state": dict(point.state),
        "sensitivity": None,
        "assessment_values": None,
        "basis": basis,
    }


def test_the_assessment_stop_keeps_v1_v2_v4_v7_and_names_its_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    formulation = _assessed()
    full = _verify(_Host(), formulation)
    monkeypatch.setattr(verification, "_assessment", lambda *args: "PINNED(tac)")
    host = _Host()
    result = _verify(host, formulation)
    [point] = host.points
    assert result.point is point
    assert [item.check for item in result.checks] == list(CHECKS)
    documents = _documents(result)
    reference = _documents(full)
    for check in ("V1", "V2", "V4", "V7"):
        assert documents[check] == reference[check], check
    for check in ("V3", "V5", "V6"):
        assert documents[check] == _not_evaluated("assessment_not_evaluable: PINNED(tac)"), check
    assert _stop_fields(result) == _expected_stop(point, formulation, None)
    assert type(result.simulation_state) is dict and result.simulation_state is not point.state
    assert result.as_document() == {
        "decisions": _decisions(formulation),
        "checks": [item.as_document() for item in result.checks],
        "objective": None,
        "constraint_values": {},
        "slacks": {},
        "active_set": [],
        "kkt": None,
        "certificate_id": _expected_stop(point, formulation, None)["certificate_id"],
        "state_sha256": _expected_stop(point, formulation, None)["state_sha256"],
    }


def test_the_phase_rows_stop_keeps_v1_v2_v4_and_the_certificate_basis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    formulation = nlp_formulation()
    held = _held()
    full = _verify(_Host(), formulation, held=held)
    row = PhaseRow(row_id="phase:PINNED", unit="PINNED", kind="split_liquid", nominal=1.0)
    phase = PhaseRows(rows=(row,), undefined=(), spec=None)
    monkeypatch.setattr(verification, "_phase_terms", lambda *args: "PINNED(phase)")
    host = _Host()
    result = _verify(host, formulation, held=held, phase=phase)
    [point] = host.points
    assert result.point is point
    assert [item.check for item in result.checks] == list(M03_CHECKS)
    documents = _documents(result)
    reference = _documents(full)
    assert reference["V1"]["basis"] == CERTIFICATE
    for check in ("V1", "V2", "V4"):
        assert documents[check] == reference[check], check
    for check in ("V3", "V5", "V6"):
        assert documents[check] == _not_evaluated("phase_rows_not_evaluable: PINNED(phase)"), check
    assert _stop_fields(result) == _expected_stop(point, formulation, CERTIFICATE)
    assert type(result.simulation_state) is dict and result.simulation_state is not point.state


def test_v1s_stop_without_a_simulation_is_no_simulation() -> None:
    formulation = _assessed()
    full = _verify(_Host(), formulation)
    host = _Host({"state": None})
    result = _verify(host, formulation)
    [point] = host.points
    assert result.point is point
    assert [item.check for item in result.checks] == list(CHECKS)
    documents = _documents(result)
    assert documents["V1"] == _documents(full)["V1"]
    assert documents["V1"]["outcome"] == "pass"
    for check in CHECKS[1:]:
        assert documents[check] == _not_evaluated("no_simulation"), check
    assert _stop_fields(result) == {
        "decisions": _decisions(formulation),
        "objective": None,
        "constraint_values": {},
        "slacks": {},
        "active_set": (),
        "kkt": None,
        "certificate_id": None,
        "state_sha256": None,
        "simulation_state": None,
        "sensitivity": None,
        "assessment_values": None,
        "basis": None,
    }


def test_v1s_stop_on_a_resolve_it_did_not_admit_is_resolve_not_certified() -> None:
    formulation = nlp_formulation()
    host = _Host({"outcome": "PINNED_NOT_CONVERGED"})
    result = _verify(host, formulation, held=_held())
    [point] = host.points
    assert result.point is point
    assert point.state is not None and point.certificate is not None
    assert [item.check for item in result.checks] == list(M03_CHECKS)
    documents = _documents(result)
    assert documents["V1"] == {
        "outcome": "fail",
        "resolve_outcome": "PINNED_NOT_CONVERGED",
        "message": point.message,
        "certificate_status": point.certificate.verification_status,
        **REFUSED.detail(),
    }
    for check in M03_CHECKS[1:]:
        assert documents[check] == _not_evaluated("resolve_not_certified"), check
    assert _stop_fields(result) == {
        "decisions": _decisions(formulation),
        "objective": None,
        "constraint_values": {},
        "slacks": {},
        "active_set": (),
        "kkt": None,
        "certificate_id": None,
        "state_sha256": None,
        "simulation_state": None,
        "sensitivity": None,
        "assessment_values": None,
        "basis": None,
    }
