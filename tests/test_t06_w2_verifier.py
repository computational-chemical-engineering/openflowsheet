"""T06 W2: the verifier's constructed states stay typed (spec §8.2; ADR 0014 D5; register R-070).

The alias certificate's shifted state moves a pressure column down where moving it up would leave
the provider's domain, and is `unsupported` where neither direction stays in it or two distinct
pressures coincide; a witness stencil point or a projection the verifier cannot evaluate makes the
check it serves `unsupported`. No `VerifierError` leaves `verify_revision` for a `CONVERGED` solve
carrying its full state. Assertions T6-A39, A40, A42; A41 (every registered certificate
bit-identical) is the inertness measurement of the W2 commit, recorded in its message.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml
from t05b_support import POLICY_V2
from test_t05b_contract import Solved, solve
from test_t06_m1_cases import case_document

import openflowsheet.verify.certificate as certificate_module
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.numerics.scaling import REGISTERED_NOMINALS
from openflowsheet.thermo import FlashRequest, FlashResult, PropertyRequest, PropertyResult
from openflowsheet.thermo.syn001 import P_MAX, P_MIN, Syn001Provider, _flash_failure
from openflowsheet.verify.checks import FD_RELATIVE_STEP
from openflowsheet.verify.projection import PROJECTED_CATEGORIES, Projection

Document = dict[str, Any]

REFERENCE = load_yaml(REPO_ROOT / "benchmarks" / "t06" / "reference_values.yaml")
#: T02 §6.4's allowances (spec §11, S3), by the column's suffix.
ALLOWANCE = {"n": 3.1e-7, "T": 1e-5, "P": 0.1, "Q": 1e-2, "W": 1e-2, "xi": 3.1e-7}
SHIFT = certificate_module.BoundDeclaration.PRESSURE_SHIFT


def registered(case: str) -> dict[str, tuple[str, float]]:
    """Every registered coordinate of a corpus case: column -> (20-digit value, allowance)."""
    entry = REFERENCE["closed_form"]["corpus_cases"][case]
    out: dict[str, tuple[str, float]] = {}
    for stream, state in entry["streams"].items():
        for component, value in zip("ABC", state["n_mol_per_s"], strict=True):
            out[f"{stream}.n.{component}"] = (value, ALLOWANCE["n"])
        out[f"{stream}.T"] = (state["T_K"], ALLOWANCE["T"])
        out[f"{stream}.P"] = (state["P_Pa"], ALLOWANCE["P"])
        for key, phase in (("vapor_mol_per_s", "vap"), ("liquid_mol_per_s", "liq")):
            for component, value in zip("ABC", state.get(key) or (), strict=False):
                out[f"{stream}.{phase}.{component}"] = (value, ALLOWANCE["n"])
    for field, suffix in (("duty_W", "Q"), ("work_W", "W"), ("extent_mol_per_s", "xi")):
        for unit, value in (entry.get(field) or {}).items():
            out[f"{unit}.{suffix}"] = (value, ALLOWANCE[suffix])
    return out


def final_state(solved: Solved) -> Mapping[str, float]:
    state: Mapping[str, float] = solved.region.state
    return state


def pressure_columns(solved: Solved) -> list[tuple[int, str]]:
    kinds = solved.binding.spec.variable_kinds
    return [
        (index, name)
        for index, name in enumerate(solved.binding.spec.variable_ids)
        if kinds.get(name) == "pressure"
    ]


def shifted_state(solved: Solved) -> tuple[dict[str, float], str]:
    spec = solved.binding.spec
    target = certificate_module.BoundDeclaration(spec, compile_problem(spec), final_state(solved))
    return target._shifted(final_state(solved))


def not_passed(solved: Solved) -> dict[str, str]:
    assert solved.certificate is not None
    return {
        check.id: f"{check.result}:{check.reason}"
        for check in solved.certificate.checks
        if check.result not in ("pass", "not_applicable")
    }


# -- A39: NET-11, the defect that motivated the rule -------------------------------------------


@pytest.fixture(scope="module")
def net11() -> Solved:
    return solve(case_document("SYN-001-T06-NET11"), POLICY_V2)


def test_a39_net11_is_verified_at_the_twin(net11: Solved) -> None:
    """Spec §0 F3: `CONVERGED`, then `VerifierError` before W2; now `VERIFIED`, and every
    registered coordinate within S3's allowances of the twin's 20-digit root."""
    assert net11.run.outcome == "CONVERGED", net11.run.message
    assert net11.certificate is not None
    assert net11.certificate.verification_status == "VERIFIED", not_passed(net11)
    state = final_state(net11)
    expected = registered("SYN-001-T06-NET11")
    assert set(expected) <= set(state)
    worst = max(
        (float(abs(Decimal(state[k]) - Decimal(v)) / Decimal(a)), k)
        for k, (v, a) in expected.items()
    )
    assert worst[0] <= 1.0, worst


def test_a39_only_s4p_moves_down_and_its_alias_certificate_passes(net11: Solved) -> None:
    """The rule fires once, at `S4.P` (index 24: 1.8e5 + 24 925 Pa leaves `[5e4, 2e5]`), which
    moves down by the same distinct amount; every other pressure moves up, as before W2."""
    shifted, reason = shifted_state(net11)
    assert reason == ""
    state = final_state(net11)
    moved_down = []
    for index, name in pressure_columns(net11):
        step = SHIFT * (index + 1)
        if shifted[name] == state[name] - step:
            moved_down.append((index, name))
        else:
            assert shifted[name] == state[name] + step, name
        assert P_MIN <= shifted[name] <= P_MAX, name
    assert moved_down == [(24, "S4.P")]
    assert state["S4.P"] + SHIFT * 25 > P_MAX
    assert net11.certificate is not None
    aliases = [c for c in net11.certificate.checks if c.category == "alias_certificate"]
    assert aliases and all(c.result == "pass" for c in aliases), aliases


# -- A40: a pressure neither direction keeps in the domain ------------------------------------

#: A pressure in the middle of the domain whose column sits at index `j ≥ 75` has
#: `997 (j + 1) > 75 000 Pa` both ways out of `[5e4, 2e5]`.
P_MID = 1.25e5
#: Fifteen feed → sink branches of five columns each put THM-01's `S1.P` at index 79.
BRANCHES = 15


def _padded() -> Document:
    """THM-01 with feed and flash at `P_MID` (the flash's inlet pressure row repeats the feed's
    pin: an eliminated alias row), behind fifteen independent feed → sink branches declared
    first, `(1, 1, 1)` mol/s at 300 K and `P_r`. The branches carry only their pinned columns;
    they move THM-01's pressure columns past index 75."""
    document = copy.deepcopy(case_document("SYN-001-T06-THM01"))
    document["revision_id"] = "T06-W2-A40-padded-r1"
    feed, flash, sink_v, sink_l = document["instances"]
    s1 = document["connections"][0]
    feed_pins = [s for s in document["specifications"] if s["target"]["object_id"] == "S1"]
    padding: list[Document] = []
    branches: list[Document] = []
    pins: list[Document] = []
    for k in range(1, BRANCHES + 1):
        stream = f"SP{k}"
        padding += [
            dict(copy.deepcopy(feed), id=f"U-FEED-P{k}"),
            dict(copy.deepcopy(sink_l), id=f"U-SINK-P{k}"),
        ]
        branch = copy.deepcopy(s1)
        branch.update(id=stream, to={"instance": f"U-SINK-P{k}", "port": "inlet"})
        branch["from"] = {"instance": f"U-FEED-P{k}", "port": "outlet"}
        branches.append(branch)
        for entry in feed_pins:
            pin = copy.deepcopy(entry)
            pin["id"] = entry["id"].replace("S1", stream)
            pin["target"]["object_id"] = stream
            if pin["target"]["path"] == "state.P":
                pin["value"] = 1.0e5
            pins.append(pin)
    for entry in document["specifications"]:
        if entry["id"] in ("SPEC-S1-P", "SPEC-flash-P"):
            entry["value"] = P_MID
    document["instances"] = [*padding, feed, flash, sink_v, sink_l]
    document["connections"] = [*branches, *document["connections"]]
    document["specifications"] = [*pins, *document["specifications"]]
    return document


@pytest.fixture(scope="module")
def chain() -> Solved:
    return solve(_padded(), POLICY_V2)


def test_a40_the_construction_puts_a_pressure_out_of_reach_both_ways(chain: Solved) -> None:
    state = final_state(chain)
    stuck = [
        name
        for index, name in pressure_columns(chain)
        if not P_MIN <= state[name] + SHIFT * (index + 1) <= P_MAX
        and not P_MIN <= state[name] - SHIFT * (index + 1) <= P_MAX
    ]
    assert stuck, "no pressure column is out of the domain both ways; the fixture tests nothing"
    assert chain.certificate is not None
    assert chain.certificate.transformations["eliminated_rows"], "no alias row to certify"


def test_a40_both_directions_out_is_unsupported_and_unverified(chain: Solved) -> None:
    """Before W2 this raised `VerifierError` (the upward shift's residual is
    `invalid_trial_state`). Now each alias claim is `unsupported(pressure_shift_outside_domain)`,
    the verdict `UNVERIFIED`, and every other check passes."""
    assert chain.run.outcome == "CONVERGED", chain.run.message
    assert chain.certificate is not None
    assert chain.certificate.verification_status == "UNVERIFIED"
    assert not chain.certificate.false_success_detected
    rows = [row["row_id"] for row in chain.certificate.transformations["eliminated_rows"]]
    expected = {
        f"alias_certificate.{claim}.{row}": "unsupported:pressure_shift_outside_domain"
        for row in rows
        for claim in ("identity", "satisfied")
    }
    assert not_passed(chain) == expected
    limitations = {
        limitation.detail["check"]
        for limitation in chain.certificate.limitations
        if limitation.kind == "unsupported_check"
    }
    assert limitations == set(expected)


def test_a40_distinct_pressures_that_coincide_after_the_shift_are_not_generic() -> None:
    """SC-1 (feed 1.8e5 Pa, valve) with the valve's outlet at `1.8e5 − 997·5` Pa: `S1.P` (index
    4) and `S2.P` (index 9) both move up to 184 985 Pa, so the second state no longer tells the
    two apart."""
    from t05b_support import sc1

    document = sc1()
    (valve_pin,) = (s for s in document["specifications"] if s["id"] == "SPEC-valve-P")
    valve_pin["value"] = 1.8e5 - SHIFT * 5
    solved = solve(document, POLICY_V2)
    assert solved.run.outcome == "CONVERGED", solved.run.message
    state = final_state(solved)
    assert [name for _, name in pressure_columns(solved)] == ["S1.P", "S2.P"]
    assert [index for index, _ in pressure_columns(solved)] == [4, 9]
    assert state["S1.P"] != state["S2.P"]
    shifted, reason = shifted_state(solved)
    assert shifted["S1.P"] == shifted["S2.P"]
    assert reason == "pressure_shift_not_generic"
    # SC-1 eliminates no row, so there is no alias certificate to withhold: the verdict stands.
    assert solved.certificate is not None
    assert solved.certificate.transformations["eliminated_rows"] == []
    assert solved.certificate.verification_status == "VERIFIED", not_passed(solved)


# -- A42: a witness stencil point outside the domain ------------------------------------------


def _feed_at_the_edge() -> Document:
    """REF-03 (feed → TP heater → sink) with the feed at `P_MAX − 0.5` Pa and the heater to
    310 K: the witness's central difference in a pressure column steps `1e-5 × 1e5 = 1` Pa, past
    `P_MAX`."""
    document = copy.deepcopy(case_document("SYN-001-T06-REF03"))
    document["revision_id"] = "T06-W2-A42-feed-at-the-edge-r1"
    for entry in document["specifications"]:
        if entry["id"] == "SPEC-S1-P":
            entry["value"] = P_MAX - 0.5
        if entry["id"] == "SPEC-heater-outlet-T":
            entry["value"] = 310.0
    return document


@pytest.fixture(scope="module")
def edge() -> Solved:
    return solve(_feed_at_the_edge(), POLICY_V2)


def test_a42_the_stencil_leaves_the_domain(edge: Solved) -> None:
    step = FD_RELATIVE_STEP * REGISTERED_NOMINALS["pressure"]
    assert final_state(edge)["S1.P"] + step > P_MAX


def test_a42_a_stencil_outside_the_domain_is_unsupported_and_unverified(edge: Solved) -> None:
    """Before W2 this raised `VerifierError("the witness stepped outside the evaluable
    domain")`. Now both witness checks are `unsupported`, naming the first column whose stencil
    failed and the status, the verdict `UNVERIFIED`, and nothing else is withheld."""
    assert edge.run.outcome == "CONVERGED", edge.run.message
    assert edge.certificate is not None
    assert edge.certificate.verification_status == "UNVERIFIED"
    reason = "unsupported:witness_stencil_invalid_trial_state(S1.P)"
    assert not_passed(edge) == {
        "derivative_witness.on_pattern": reason,
        "derivative_witness.off_pattern": reason,
    }
    kinds = [limitation.kind for limitation in edge.certificate.limitations]
    assert "derivative_limitation" in kinds
    assert edge.certificate.derivative_provenance["witness_max_diff"] is None


# -- the projection: a fresh evaluation that fails at x̃ ----------------------------------------


class _Gated(Syn001Provider):
    """A SYN-001 provider that records every fresh flash and phase evaluation it answers and,
    once `refuse` is set, answers `not_converged` to any request it has not seen."""

    seen: set[str] = set()
    refuse = False

    def _unseen(self, request: Any) -> bool:
        key = repr(request)
        if not type(self).refuse:
            type(self).seen.add(key)
            return False
        return key not in type(self).seen

    def flash(self, request: FlashRequest, context: Any) -> FlashResult:
        if self._unseen(request):
            return _flash_failure("not_converged", "test double: a request not made at x_final")
        return super().flash(request, context)

    def evaluate_phase(self, request: PropertyRequest, context: Any) -> PropertyResult:
        if self._unseen(request):
            return self._failed(request, "not_converged", "test double: not made at x_final")
        return super().evaluate_phase(request, context)


def test_a_fresh_evaluation_that_fails_at_the_projection_is_unsupported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """THM-01, whose fresh-flash categories are judged at `x̃` (ADR 0013 D1). The provider
    first records every request the check set makes with those categories at `x_final`, then
    refuses every other one — so every request `x̃` makes that `x_final` did not fails. Those
    checks become `unsupported(projection_unevaluable(…))`, the verdict `UNVERIFIED`; every
    other check is the honest certificate's, unchanged."""
    document = case_document("SYN-001-T06-THM01")
    honest = solve(document, POLICY_V2)
    assert honest.certificate is not None
    assert honest.certificate.verification_status == "VERIFIED"
    assert honest.certificate.transformations["projection"]["judged_at"] == "projection"
    solve_plan = honest.plan.steps[-1].solve_plan

    class Gated(_Gated):
        seen: set[str] = set()
        refuse = False

    monkeypatch.setattr(certificate_module, "Syn001Provider", Gated)

    def at_final_state(target: Any, state: Mapping[str, float], *args: Any, **kw: Any) -> Any:
        return Projection(state=state, judged_at="final_state", reason="test_double")

    with monkeypatch.context() as recording:
        recording.setattr(certificate_module, "_project", at_final_state)
        certificate_module.verify_revision(
            honest.binding, document, honest.run, solve_plan=solve_plan
        )
    assert Gated.seen
    Gated.refuse = True
    refused = certificate_module.verify_revision(
        honest.binding, document, honest.run, solve_plan=solve_plan
    )
    assert refused.verification_status == "UNVERIFIED"
    assert refused.transformations["projection"]["judged_at"] == "projection"
    before = {check.id: check for check in honest.certificate.checks}
    after = {check.id: check for check in refused.checks}
    assert list(after) == list(before)
    withheld = {name for name, check in after.items() if check.result == "unsupported"}
    assert withheld, "x̃ made no request x_final did not; the test double refused nothing"
    for name, check in after.items():
        if name in withheld:
            assert check.category in PROJECTED_CATEGORIES, name
            assert check.reason.startswith("projection_unevaluable(the verifier's own"), check
        else:
            assert check == before[name], name
