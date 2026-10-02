"""K04 §9: the injected false successes, and their twins just below threshold.

Every injection is paired with a state below its threshold (§1 invariant 3). Without the twin,
"the verifier rejects this" is satisfied by a verifier that rejects everything, and the pair is
the only thing that shows the tolerance is neither zero nor infinite.

Each test also asserts what must **pass**, not only what must fail. A detection that cannot be
attributed to a particular check is not a detection: it is a verifier with a bad mood.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml
from test_k04_checks import flowsheet_for

from openflowsheet.orchestrator.tear import solve_tear
from openflowsheet.verify.certificate import CheckPolicy, verify


@pytest.fixture(scope="module")
def reference() -> Mapping[str, Any]:
    return load_yaml(REPO_ROOT / "benchmarks" / "k04" / "reference_values.yaml")


@pytest.fixture(scope="module")
def variants() -> dict[str, Mapping[str, Any]]:
    loaded = load_yaml(REPO_ROOT / "benchmarks" / "syn001" / "reference_values.yaml")
    return {entry["case_id"]: entry for entry in loaded["variants"]}


def solved(variants: dict[str, Mapping[str, Any]], case_id: str) -> tuple[Any, Any, dict]:
    flowsheet = flowsheet_for(variants[case_id])
    result, _ = solve_tear(flowsheet)
    assert result.outcome == "CONVERGED" and result.final_state is not None
    return flowsheet, result, dict(result.final_state)


def failing(certificate: Any) -> set[str]:
    return {check.id for check in certificate.checks if check.result == "fail"}


# ---------------------------------------------------------------------------------------------
# **Resolved 2026-09-22.** An earlier version of this file recorded a conflict between §7.4's
# solution-error bound and §9's below-threshold twins: `||J^-1||_1 = 144.8` at the nominal
# state, so a state converged *to tolerance* rather than to roundoff has `b ~ 145 tau_min` and
# every twin failed the bound. Fable ruled that the defect was in the promise, not the twins.
#
# A certificate certifies **residual** accuracy. Blueprint §8.1's acceptance rule is on
# residuals and balances; nothing in the authority promises solution accuracy. So `b` is
# recorded evidence and a disclosure — with a third required statement saying what it does and
# does not mean — and never a check. Making it one would have tightened the registered residual
# tolerances by ~500x through the back door.
#
# What replaced it is the **absolute** conditioning limit, `||J^-1||_1 <= tau_min / (n eps)`,
# which is what [A08]'s "derivative/evaluation uncertainty" clause means and what a scale-free
# `rcond_1` cannot see. It is tested in `test_k04_regularity.py`.
# ---------------------------------------------------------------------------------------------


def assert_twin(certificate: Any) -> None:
    """A twin is inside every registered tolerance, so nothing fails and the verdict is clean.

    The bound is still *recorded* at the twin — 1.45e-7 to 7.2e-7, one to two orders above
    `tau_min` — which is exactly the disclosure §7.4 is for: the residuals are certified, and
    the solution is determined to within that.
    """
    assert certificate.verification_status == "VERIFIED"
    assert failing(certificate) == set()
    assert certificate.solution_error_bound_scaled is not None
    assert certificate.regularity.ill_conditioned_reason is None


def test_a17_inj1_wrong_energy_bookkeeping(
    variants: dict[str, Mapping[str, Any]], reference: Mapping[str, Any]
) -> None:
    """§9.1 (VER-01): a duty off by 1 W. The twin at 5e-4 W must be `VERIFIED`."""
    registered = reference["injections"]["INJ-1-energy-bookkeeping"]
    flowsheet, result, base = solved(variants, "SYN-001-nominal")

    poisoned = dict(base)
    poisoned["U-HEAT.Q"] += float(registered["fails_at_W"])
    certificate = verify(flowsheet, result, state=poisoned)
    assert certificate.verification_status == "FAILED"
    assert certificate.false_success_detected is True
    assert failing(certificate) == {
        "residual.U-HEAT:HEAT-duty",
        "energy_balance.heater",
        "energy_balance.envelope",
    }, "A17's set exactly: the bound is recorded evidence and never appears in a failing set"
    # Regularity *is* untouched, which is the point of naming it: the duty column does not
    # enter the conditioning, so a wrong duty is invisible to the rank screen.
    assert certificate.regularity.status == "NO_RANK_LOSS_DETECTED"
    # And the bound is recorded, large, and decides nothing.
    assert certificate.solution_error_bound_scaled == pytest.approx(1.4481555e-3, rel=1e-3)

    twin = dict(base)
    twin["U-HEAT.Q"] += float(registered["passes_at_W"])
    assert_twin(verify(flowsheet, result, state=twin))


def test_a27_inj6_one_perturbed_coordinate(
    variants: dict[str, Mapping[str, Any]], reference: Mapping[str, Any]
) -> None:
    """§9.6: `S6.n.A + 1e-6`, detected by two independent evaluators, and the 1e-8 twin."""
    registered = reference["injections"]["INJ-6-one-coordinate"]
    flowsheet, result, base = solved(variants, "SYN-001-nominal")

    poisoned = dict(base)
    poisoned["S6.n.A"] += float(registered["fails_at_mol_per_s"])
    certificate = verify(flowsheet, result, state=poisoned)
    assert certificate.verification_status == "FAILED"

    failures = failing(certificate)
    for row in registered["rows_shifted_by_delta"]:
        assert f"residual.{row}" in failures, row
    assert f"residual.{registered['row_shifted_by_delta_h']}" in failures
    # The same defect found again by the independent summation of §4.3.
    assert "material_balance.mixer.A" in failures
    assert "material_balance.ratio.A" in failures
    assert "energy_balance.mixer" in failures

    twin = dict(base)
    twin["S6.n.A"] += float(registered["passes_at_mol_per_s"])
    assert_twin(verify(flowsheet, result, state=twin))


def test_a28_inj7_a_tampered_specification(
    variants: dict[str, Mapping[str, Any]], reference: Mapping[str, Any]
) -> None:
    """§9.7: `S3.T + 1e-5 K` against a 1e-6 K tolerance, with the duty shifts it implies."""
    registered = reference["injections"]["INJ-7-tampered-specification"]
    flowsheet, result, base = solved(variants, "SYN-001-nominal")

    poisoned = dict(base)
    poisoned["S3.T"] += float(registered["fails_at_K"])
    certificate = verify(flowsheet, result, state=poisoned)
    assert certificate.verification_status == "FAILED"

    failures = failing(certificate)
    assert "specification.S3.T" in failures
    assert "residual.U-HEAT:HEAT-T" in failures
    assert "energy_balance.heater" in failures

    by_id = {check.id: check for check in certificate.checks}
    expected = float(registered["HEAT_duty_shift_per_K_W"]) * float(registered["fails_at_K"])
    assert by_id["residual.U-HEAT:HEAT-duty"].value == pytest.approx(expected, rel=1e-6)

    twin = dict(base)
    twin["S3.T"] += float(registered["passes_at_K"])
    assert_twin(verify(flowsheet, result, state=twin))


def inj3_state(variants: dict[str, Mapping[str, Any]], reference: Mapping[str, Any]) -> Any:
    """§9.3: nominal `t* + 1e-6 e_C`, reconstructed through the tear map.

    Every inner row is satisfied — the traversal admits the state, mixer margin 4.2e-7 — and
    only the tear is not. So it is a state that is *internally consistent* and simply not the
    answer, which is the hardest kind to catch and the kind a residual check is actually for.
    """
    from openflowsheet.orchestrator.tear import Syn001TearProblem

    flowsheet = flowsheet_for(variants["SYN-001-nominal"])
    result, _ = solve_tear(flowsheet)
    tear = Syn001TearProblem(flowsheet)
    registered = reference["injections"]["INJ-3-consistent-near-state"]
    point = [float(value) for value in registered["t_mol_per_s"]]
    return flowsheet, result, tear.reconstruct(tear.tear_state(point)), registered


def test_a19_inj3_an_internally_consistent_state_that_is_not_the_answer(
    variants: dict[str, Mapping[str, Any]], reference: Mapping[str, Any]
) -> None:
    """§9.3: only the tear rows and the ratio rows fail — two evaluators, one defect."""
    flowsheet, result, state, registered = inj3_state(variants, reference)
    certificate = verify(flowsheet, result, state=state)
    assert certificate.verification_status == "FAILED"

    by_id = {check.id: check for check in certificate.checks}
    expected = [float(value) for value in registered["R_mol_per_s"]]
    for component, value in zip(("A", "B", "C"), expected, strict=True):
        # K03 §3.1: the compiled `SPLIT-recycle` rows evaluate `-R`.
        assert by_id[f"residual.U-SPLIT:SPLIT-recycle:{component}"].value == pytest.approx(
            -value, abs=1e-12
        )
        assert by_id[f"residual.U-SPLIT:SPLIT-recycle:{component}"].result == "fail"
        assert by_id[f"material_balance.ratio.{component}"].result == "fail"
    assert len(set(expected)) == 3, "the three rows are pairwise distinct (§9.3)"

    # Everything that is not the tear passes: the state really is internally consistent.
    for category in ("energy_balance", "specification", "alias_certificate", "phase_admissibility"):
        assert not [
            c.id for c in certificate.checks if c.category == category and c.result == "fail"
        ], category


def test_a16_inj4_a_relaxed_policy_is_never_verified(
    variants: dict[str, Mapping[str, Any]], reference: Mapping[str, Any]
) -> None:
    """§9.4 (VER-05). A loosened policy is an input with a hash, and it caps the verdict.

    Plan §6.2: a `RELAXED` certificate is never counted as verified success. The same state
    under a *tightened* policy is `FAILED`, not `RELAXED` — relaxation is about the policy
    being looser than the registered one, not merely different from it.
    """
    from openflowsheet.verify.checks import KIND_TOLERANCE

    flowsheet, result, state, _ = inj3_state(variants, reference)
    assert verify(flowsheet, result, state=state).verification_status == "FAILED"

    loosened = CheckPolicy(
        policy_id="supplied-loose", tolerances={**KIND_TOLERANCE, "molar_flow": 1e-6}
    )
    certificate = verify(flowsheet, result, state=state, policy=loosened)
    assert certificate.verification_status == "RELAXED", (
        "every check passes under this policy, and the verdict must still not be VERIFIED"
    )
    assert certificate.check_policy_sha256 != CheckPolicy().sha256
    relaxations = {
        limitation.detail["check"]: limitation.detail
        for limitation in certificate.limitations
        if limitation.kind == "relaxation"
    }
    assert "residual.molar_flow" in relaxations
    assert relaxations["residual.molar_flow"]["registered"] == KIND_TOLERANCE["molar_flow"]
    assert relaxations["residual.molar_flow"]["applied"] == 1e-6

    tightened = CheckPolicy(
        policy_id="supplied-tight", tolerances={**KIND_TOLERANCE, "molar_flow": 1e-9}
    )
    assert verify(flowsheet, result, state=state, policy=tightened).verification_status == "FAILED"


def test_a_policy_that_names_an_unknown_kind_is_refused() -> None:
    """A supplied policy is validated, not absorbed: a typo must not silently widen nothing."""
    from openflowsheet.verify import CheckPolicyError

    with pytest.raises(CheckPolicyError, match="do not exist"):
        CheckPolicy(policy_id="typo", tolerances={"molar_flowe": 1.0})
    with pytest.raises(CheckPolicyError, match="positive"):
        CheckPolicy(policy_id="zero", tolerances={"molar_flow": 0.0})


def test_a30_every_check_result_is_completely_populated(
    variants: dict[str, Mapping[str, Any]],
) -> None:
    """A30: an evaluated check reports all three of value, tolerance and reference.

    Blueprint §8.1 requires `|e_i| <= a_i + r_i s_i` with all three visible. A tolerance
    without its reference cannot be audited, and a check with neither is an opinion.
    """
    import math

    flowsheet, result, _ = solved(variants, "SYN-001-nominal")
    certificate = verify(flowsheet, result)
    document = certificate.as_document()

    for check in certificate.checks:
        if check.scope == "evaluated":
            assert check.value is not None, check.id
            assert check.tolerance is not None, check.id
            if check.category not in ("bounds_and_domain",):
                assert check.reference is not None, check.id
        else:
            assert check.reason, check.id

    def finite(node: Any) -> None:
        if isinstance(node, dict):
            for value in node.values():
                finite(value)
        elif isinstance(node, list):
            for value in node:
                finite(value)
        elif isinstance(node, float):
            assert math.isfinite(node), node

    finite(document)
    assert "<" not in repr(document).replace("<class", ""), "no angle-bracket placeholder"
    assert len(certificate.statements) >= 2
    assert any("not an experimental validation" in s for s in certificate.statements)
    assert any("no finite test suite" in s.lower() for s in certificate.statements)
