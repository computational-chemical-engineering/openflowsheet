"""K04 amendment WIT (§4.8.2-§4.8.7, ADR 0073): the system cases WIT.A08, A10 (354 K), A11, A12
and A14 (ADV-06).

A09 (G7(c) at δ = 1e-4) is `tests/test_m02_wo8_g7.py::test_g7c_at_delta_1e_4_...` and A10 at
340 K and 345 K `tests/test_s11_gp_solve.py::test_wit_a10_...` (the moves M-2 and M-1); A14's
T06 W2 A42 is `tests/test_t06_w2_verifier.py::test_a42_...`, unchanged. The analytic cases are
`tests/test_wit_witness.py`. The witness is observed through `wit_support.spy`; the certificate
records no escalation (§4.8.3 (g)).
"""

from __future__ import annotations

import json
import platform
from typing import Any

import pytest
from conftest import REPO_ROOT, load_json
from s11_gp_support import gp_c1, gp_c3, solve
from wit_support import Witnessed, spy

from openflowsheet.application.policies import T06_REVISION_V2
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.models.revision_flowsheet import WILSON_BASIS
from openflowsheet.orchestrator.executor import execute_plan
from openflowsheet.orchestrator.revision import plan_revision
from openflowsheet.verify.certificate import SolutionCertificate, verify_revision
from openflowsheet.verify.checks import (
    DERIVATIVE_TOLERANCE,
    ONE_SIDED_BASES,
    WITNESS_CLASSES,
)

WIT: dict[str, Any] = load_json(
    REPO_ROOT / "docs" / "derivations" / "scripts" / "wit_reference.json"
)
SURROGATE = REPO_ROOT / "benchmarks" / "m04" / "c1-surrogate.json"
#: WIT.A08: the surrogate's escalated set (each fails the registered stencil by >= 2.8 tau_D).
ESCALATED = {"S1.n.NH3", "S1.n.N2", "S1.n.Ar", "S1.n.CH4", "S1.n.H2", "S2.n.NH3"}
#: §4.8.6, measured at dda8a6d9 with the prototype (TRS2, x86-64): S11.A71's on-pattern value.
A71_ON_PATTERN = 2.6013065590468898e-09
#: §4.8.6: ADV-06 M under `T06-revision-v2`, on-pattern `fail`, on the reference platform.
ADV06_ON_PATTERN = 1.793495859841966e-05
REFERENCE_PLATFORM = platform.machine() == "x86_64"


def certify_gp_c3(
    monkeypatch: pytest.MonkeyPatch, heater_temperature: float
) -> tuple[SolutionCertificate, Witnessed]:
    runs = spy(monkeypatch)
    document = gp_c3(heater_temperature=heater_temperature)
    binding, plan, run = solve(document)
    assert run.outcome == "CONVERGED", run.message
    certificate = verify_revision(binding, document, run, solve_plan=plan.steps[-1].solve_plan)
    (witnessed,) = runs
    return certificate, witnessed


def assert_classes_partition(witnessed: Witnessed) -> None:
    """WIT.A12: one class per column, covering every column; the witness's sets are classes 1-2
    and 3-4; classes 2-4 empty off the gamma-phi-IG bases."""
    assert witnessed.classes is not None and witnessed.basis is not None
    columns = list(witnessed.target.spec.variable_ids)
    assert list(witnessed.classes) == columns
    assert set(witnessed.classes.values()) <= set(WITNESS_CLASSES)
    sets = [witnessed.of_class(k) for k in WITNESS_CLASSES]
    assert sum(len(s) for s in sets) == len(columns)
    assert set().union(*sets) == set(columns)
    assert witnessed.unstenciled == frozenset(sets[0] | sets[1])
    assert witnessed.one_sided == frozenset(sets[2] | sets[3])
    if witnessed.basis not in ONE_SIDED_BASES:
        assert not (sets[1] or sets[2] or sets[3])
    if witnessed.basis != "pr-c1-v1":
        assert not sets[0]


# -- WIT.A08: L-X10-1, the C1 surrogate ------------------------------------------------------------


def test_a08_the_c1_surrogate_is_verified_by_the_escalation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WIT.A08 (M-3): `c1-surrogate.json` under `T06-revision-v2` is CONVERGED and VERIFIED, its
    limitations exactly `[near_threshold, surrogate_model]` with the flag on
    `derivative_witness.on_pattern`. The six failing component columns escalate and resolve
    within tau_D / 10; the overall maximum is a registered central column (S2.n.CH4, 3.9e-8).
    Measured on TRS2: k* = 4, 5, 3, 3, 2, 1; escalated <= 4.28e-10; on-pattern 3.9004e-08.
    k* is recorded, not asserted (S1.n.CH4's e_2 is 1.09 eps_res)."""
    from m02_c1_corpus import surrogates  # noqa: PLC0415

    runs = spy(monkeypatch)
    document = json.loads(SURROGATE.read_text(encoding="utf-8"))
    binding = bind_revision_flowsheet(document, surrogates=surrogates)
    assert isinstance(binding, RevisionBinding), binding
    plan, _ = plan_revision(binding, T06_REVISION_V2)
    run = execute_plan(
        plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=T06_REVISION_V2
    )
    assert run.outcome == "CONVERGED", run.message
    certificate = verify_revision(binding, document, run, solve_plan=plan.steps[-1].solve_plan)
    (witnessed,) = runs
    assert certificate.verification_status == "VERIFIED", certificate.limitations
    assert [item.kind for item in certificate.limitations] == ["near_threshold", "surrogate_model"]
    (near,) = (item for item in certificate.limitations if item.kind == "near_threshold")
    assert near.detail["check"] == "derivative_witness.on_pattern"
    on, off = witnessed.check("on_pattern"), witnessed.check("off_pattern")
    assert (on.result, off.result) == ("pass", "pass")
    assert on.value is not None and on.value <= DERIVATIVE_TOLERANCE
    assert set(witnessed.escalations) == ESCALATED
    for column, escalation in witnessed.escalations.items():
        assert escalation.level is not None, column
        assert witnessed.escalated_discrepancy(column) <= DERIVATIVE_TOLERANCE / 10, column
    assert_classes_partition(witnessed)


# -- WIT.A10 at 354 K: S11.A71 unchanged -----------------------------------------------------------


def test_a10_gp_c3_at_354_k_has_no_dormant_side_and_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    certificate, witnessed = certify_gp_c3(monkeypatch, 354.0)
    assert certificate.verification_status == "VERIFIED"
    assert not witnessed.of_class(2) and not witnessed.of_class(4)
    assert not witnessed.escalations
    on = witnessed.check("on_pattern")
    assert on.result == "pass"
    if REFERENCE_PLATFORM:
        assert on.value == A71_ON_PATTERN  # bitwise
    assert_classes_partition(witnessed)


# -- WIT.A11: the dormant liquid side (class 2) ----------------------------------------------------


@pytest.mark.parametrize("heater_temperature", [365.0, 375.0, 385.0])
def test_a11_a_dormant_wilson_liquid_side_is_listed_not_differenced(
    monkeypatch: pytest.MonkeyPatch, heater_temperature: float
) -> None:
    """WIT.A11: GP-C3 with the heater above the dew point: class 2 is the three `S4.liq.<c>`, the
    certificate VERIFIED, and `derivative_witness_partial` lists exactly those, sorted, in
    R-281's record. At 385 K the AD entries and the forward five-point differences of
    (`H:HEAT-equilibrium:<c>`, `S4.liq.<c>`) are G2's closed forms (relative 1e-12): the probe
    convention and the pure-component limit, which differ by 0.075-0.39 (§4.8.5)."""
    certificate, witnessed = certify_gp_c3(monkeypatch, heater_temperature)
    liquid = {f"S4.liq.{c}" for c in WILSON_BASIS.components}
    assert witnessed.of_class(2) == liquid
    assert certificate.verification_status == "VERIFIED", [
        (c.id, c.result, c.reason) for c in certificate.checks if c.result != "pass"
    ]
    (partial,) = (x for x in certificate.limitations if x.kind == "derivative_witness_partial")
    assert partial.detail["columns"] == sorted(liquid)
    assert_classes_partition(witnessed)
    if heater_temperature != 385.0:
        return
    jacobian = witnessed.scaled_jacobian()
    for component, g2 in WIT["GP_C3"]["G2"]["components"].items():
        row, column = f"H:HEAT-equilibrium:{component}", f"S4.liq.{component}"
        ad = float(g2["ad_entry_scaled"])
        forward = float(g2["one_sided_derivative_scaled"])
        assert jacobian[(row, column)] == pytest.approx(ad, rel=1e-12, abs=0.0)
        assert witnessed.forward(column)[row] == pytest.approx(forward, rel=1e-12, abs=0.0)


# -- WIT.A14: ADV-06 M unchanged under escalation --------------------------------------------------


def test_a14_adv06_m_keeps_its_failing_witness_bitwise() -> None:
    """WIT.A14: ADV-06 M (`T06-revision-v2`): `on_pattern` `fail` with its registered value,
    bitwise on the reference platform (T6-A17's band elsewhere, `test_t06_w7_adv06`). Its 21
    component columns escalate and none resolves (smallest e_k 2.99e-7 = 30 eps_res)."""
    from t06_adv06_support import adv06  # noqa: PLC0415

    run = adv06("M", "T06-revision-v2")
    assert run.certificate is not None
    (on,) = (c for c in run.certificate.checks if c.id == "derivative_witness.on_pattern")
    assert on.result == "fail"
    if REFERENCE_PLATFORM:
        assert on.value == ADV06_ON_PATTERN  # bitwise


# -- Review F-4: A1 on a flash-style (products) split ----------------------------------------------


def _pin(document: Any, name: str, value: float) -> None:
    """Set the value of the one specification named `name` in `document`."""
    found = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if name in node.values() and "value" in node:
                node["value"] = value
                found.append(node)
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(document)
    assert len(found) == 1, (name, len(found))


@pytest.mark.parametrize(
    ("flash_temperature", "heater_temperature"),
    [(335.0, 352.0), (340.0, 330.0)],
)
def test_f4_a_dormant_vapour_product_of_a_flash_is_differenced_forward(
    monkeypatch: pytest.MonkeyPatch, flash_temperature: float, heater_temperature: float
) -> None:
    """Review F-4 (§4.8.4, A1 off the outlet style): GP-C1 with its `tp_flash` below the bubble
    point holds LIQUID, so the vapour product `S3.n.<c>` (a stream, read by the flash's own rows
    and the sink) is dormant: class 4. At (340 K, 330 K) the heater's outlet is liquid too, so
    `S2.vap.<c>` is class 4 as well. Each certificate is VERIFIED with no limitation, and every
    class-4 forward difference matches the AD entries within tau_D / 10 (R-831's watch line).
    Measured on TRS2: max |J-hat - D-hat_fwd| 1.31e-10 (335 K) and 1.32e-10 (340 K), at the
    duty rows."""
    runs = spy(monkeypatch)
    document = json.loads(json.dumps(gp_c1()))
    _pin(document, "SPEC-S3-T", flash_temperature)
    _pin(document, "SPEC-S4-T", flash_temperature)
    _pin(document, "SPEC-H-T", heater_temperature)
    binding, plan, run = solve(document)
    assert run.outcome == "CONVERGED", run.message
    certificate = verify_revision(binding, document, run, solve_plan=plan.steps[-1].solve_plan)
    (witnessed,) = runs
    vapour = {f"S3.n.{c}" for c in WILSON_BASIS.components}
    held = {f"S2.vap.{c}" for c in WILSON_BASIS.components}
    expected = vapour | held if heater_temperature < flash_temperature else vapour
    assert witnessed.of_class(4) == expected
    assert not witnessed.of_class(2)
    assert certificate.verification_status == "VERIFIED", certificate.limitations
    assert not certificate.limitations
    jacobian = witnessed.scaled_jacobian()
    for column in expected:
        forward = witnessed.forward(column)
        worst = max(abs(jacobian.get((row, column), 0.0) - value) for row, value in forward.items())
        assert worst <= DERIVATIVE_TOLERANCE / 10, column
    assert_classes_partition(witnessed)
