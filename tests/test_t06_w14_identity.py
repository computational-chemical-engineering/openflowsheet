"""T06 W14: the regularity screen refuses a matrix whose identity is not the target's.

Spec §8.4 (A2), assertion T6-A82; register R-084; K04 §7.5, §7.6 REG-ε and A24, whose identity
half K04 registered and never implemented (W5 measured REG-ε at `NO_RANK_LOSS_DETECTED`,
`rcond₁ = 1.0`). `screen(…, target_identity=…)` compares ADR 0008 D2.4's four pairing fields;
a missing or differing `jacobian_identity` is `INCONCLUSIVE(identity_mismatch)` whatever the
matrix would have said, with the matrix's numbers still recorded. The certificate path passes the
residual's identity at `x_final`, equal to the Jacobian's by construction, so no certificate
moves — that half of A82 is measured over the whole suite and recorded in the W14 commit.

VER-02 (REG-ε) is `tests/test_t06_w5_corpus.py::test_a19_…`, the W5 strict xfail this makes a
pass; VER-03 (the stale Jacobian) is here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

import numpy as np
import pytest
import scipy.sparse as sp
from conftest import REPO_ROOT, load_yaml
from test_k04_checks import flowsheet_for
from test_t06_w4_registry import BY_ID

import openflowsheet.verify.regularity as regularity
from openflowsheet.orchestrator.tear import Syn001TearProblem, solve_tear
from openflowsheet.verify.certificate import verify
from openflowsheet.verify.regularity import PAIRING_FIELDS, assemble_target, screen

#: SQ-0's `J = [[0]]` regularized by `1e-6` (K04 §7.6 REG-ε).
REG_EPS = sp.csc_matrix(np.array([[0.0 + 1e-6]]))
IDENTITY = {
    "model_version": "SQ-0@" + "a" * 64,
    "constants_sha256": "b" * 64,
    "state_sha256": "c" * 64,
    "phase_signature": None,
}


def _word(evidence: regularity.RegularityEvidence) -> str:
    return f"{evidence.status}({evidence.inconclusive_reason})"


def test_a82_the_refusal_decides_not_the_matrix() -> None:
    """REG-ε with `I₁ ≠ I₂` in `state_sha256` only is refused; with `I₁ = I₂` the same matrix is
    `NO_RANK_LOSS_DETECTED` — and every number recorded is the same in both."""
    stale = dict(IDENTITY, state_sha256="d" * 64)
    refused = screen(REG_EPS, jacobian_identity=stale, target_identity=IDENTITY)
    accepted = screen(REG_EPS, jacobian_identity=dict(IDENTITY), target_identity=IDENTITY)

    assert _word(refused) == "INCONCLUSIVE(identity_mismatch)"
    assert refused.ill_conditioned_reason is None
    assert accepted.status == "NO_RANK_LOSS_DETECTED"
    assert accepted.inconclusive_reason is None
    assert accepted.rcond_1 == refused.rcond_1 == 1.0
    measured = ("one_norm", "inverse_one_norm_estimate", "u_diagonal_ratio", "dimension", "nnz")
    assert [getattr(refused, name) for name in measured] == [
        getattr(accepted, name) for name in measured
    ]
    assert refused.jacobian_identity == stale, "the matrix's own identity is what is recorded"
    # And without a target nothing is compared: K04's behaviour, unchanged.
    assert screen(REG_EPS, jacobian_identity=stale).status == "NO_RANK_LOSS_DETECTED"


@pytest.mark.parametrize("field", PAIRING_FIELDS)
def test_a82_a_difference_in_any_of_the_four_fields_is_refused(field: str) -> None:
    differing = dict(IDENTITY, **{field: "other"})
    evidence = screen(REG_EPS, jacobian_identity=differing, target_identity=IDENTITY)
    assert _word(evidence) == "INCONCLUSIVE(identity_mismatch)", field


@pytest.mark.parametrize(
    "jacobian_identity",
    [
        pytest.param(None, id="missing"),
        pytest.param({}, id="empty"),
        pytest.param(
            {name: IDENTITY[name] for name in PAIRING_FIELDS if name != "phase_signature"},
            id="lacking-phase_signature",
        ),
    ],
)
def test_a82_a_missing_or_incomplete_identity_is_refused(
    jacobian_identity: dict[str, Any] | None,
) -> None:
    evidence = screen(REG_EPS, jacobian_identity=jacobian_identity, target_identity=IDENTITY)
    assert _word(evidence) == "INCONCLUSIVE(identity_mismatch)"
    assert evidence.rcond_1 == 1.0


def test_a82_the_refusal_overrides_every_status_the_matrix_would_have() -> None:
    """Singular (`RANK_DEFICIENT`), `ILL_CONDITIONED` and past the SVD cap: the refusal decides."""
    stale = dict(IDENTITY, state_sha256="d" * 64)
    singular = screen(sp.csc_matrix(np.array([[0.0]])))
    assert singular.status == "RANK_DEFICIENT"
    refused = screen(
        sp.csc_matrix(np.array([[0.0]])), jacobian_identity=stale, target_identity=IDENTITY
    )
    assert _word(refused) == "INCONCLUSIVE(identity_mismatch)"
    assert refused.escalation == singular.escalation, "the SVD is still performed and recorded"

    ill = sp.csc_matrix(np.diag([1.0, 1e-10]))
    assert screen(ill).ill_conditioned_reason == "relative"
    refused = screen(ill, jacobian_identity=stale, target_identity=IDENTITY)
    assert _word(refused) == "INCONCLUSIVE(identity_mismatch)"
    assert refused.ill_conditioned_reason is None


def test_a82_a_target_identity_without_its_four_fields_is_an_error() -> None:
    incomplete = {name: IDENTITY[name] for name in PAIRING_FIELDS if name != "state_sha256"}
    with pytest.raises(ValueError, match="state_sha256"):
        screen(REG_EPS, jacobian_identity=dict(IDENTITY), target_identity=incomplete)


@pytest.fixture(scope="module")
def nominal() -> tuple[Any, Any, Syn001TearProblem]:
    loaded = load_yaml(REPO_ROOT / "benchmarks" / "syn001" / "reference_values.yaml")
    case = {entry["case_id"]: entry for entry in loaded["variants"]}["SYN-001-nominal"]
    flowsheet = flowsheet_for(case)
    result, _ = solve_tear(flowsheet)
    assert result.outcome == "CONVERGED"
    return flowsheet, result, Syn001TearProblem(flowsheet)


def test_a82_ver03_a_stale_jacobian_is_refused(nominal: tuple[Any, Any, Any]) -> None:
    """VER-03: SYN-001-nominal's target Jacobian at the tear path's last iterate before
    convergence — its one Newton step starts at the registered initializer `t⁰ = G(0)` — screened
    with its own identity against the certified state's: refused, although the stale matrix on
    its own is `NO_RANK_LOSS_DETECTED`."""
    flowsheet, result, tear = nominal
    assert result.iterations == 1, "t⁰ is the last iterate before convergence only for one step"
    stale = assemble_target(tear, tear.reconstruct(flowsheet.initial_recycle()))
    certified = assemble_target(tear, result.final_state)
    assert certified.residual_identity == certified.jacobian_identity
    assert stale.jacobian_identity["state_sha256"] != certified.residual_identity["state_sha256"]

    unchecked = screen(stale.matrix, jacobian_identity=stale.jacobian_identity)
    assert unchecked.status == "NO_RANK_LOSS_DETECTED"
    evidence = screen(
        stale.matrix,
        jacobian_identity=stale.jacobian_identity,
        target_identity=certified.residual_identity,
    )
    assert _word(evidence) == BY_ID["VER-03"]["expected"]["regularity"]
    assert evidence.rcond_1 == unchecked.rcond_1


def test_a82_the_certificate_screens_against_the_residuals_identity(
    nominal: tuple[Any, Any, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The certificate path passes the residual's identity as the target: a residual evaluated at
    another state makes the regularity `INCONCLUSIVE(identity_mismatch)` and the verdict
    `UNVERIFIED` (R-016 (6)). A path that compared the Jacobian with itself would stay
    `VERIFIED` here."""
    flowsheet, result, _ = nominal
    assert verify(flowsheet, result).verification_status == "VERIFIED"

    original = regularity.assemble_target

    def elsewhere(*args: Any, **kwargs: Any) -> regularity.TargetAssembly:
        assembled = original(*args, **kwargs)
        moved: Mapping[str, Any] = dict(assembled.residual_identity, state_sha256="0" * 64)
        return replace(assembled, residual_identity=dict(moved))

    monkeypatch.setattr(regularity, "assemble_target", elsewhere)
    certificate = verify(flowsheet, result)
    assert certificate.regularity is not None
    assert _word(certificate.regularity) == "INCONCLUSIVE(identity_mismatch)"
    assert certificate.verification_status == "UNVERIFIED"
