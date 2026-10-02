"""T06 W19: the two-phase admissibility closure is the saturation closure (spec §8.8 (A4); ADR 0014
D13; register R-086). Assertion A91; A92's four re-registrations live in their owners' tests
(`test_t05b_candidate_answers.py` B34 (a), `test_t05b_zero_flow.py` B16, `test_t05b_dormancy.py`
B26, the T04 schema fixture `solution_certificate/valid/t04_hom01_bound_verified.json`).

K04 §4.7 wrote K03 §8.2's closure as `Σ(v/V) − Σ(l/L)`, which is `1 − 1` for every `V, L > 0`.
The check is now `max(|T − T_b(l, P)|, |T − T_d(v, P)|)` in kelvin against `τ_T`, from the
verifier's own band (`verify.saturation`): the liquid product at its bubble point and the vapour
product at its dew point, both `T`, at an equilibrium split.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml
from test_k04_checks import CASE_IDS, CONTEXT
from test_k04_checks import solved as solved_legacy
from test_t05b_contract import solved as solved_t05b
from test_t06_w5_corpus import REVISION_RUNS, solved

import openflowsheet.verify.certificate as certificate_module
from openflowsheet.models.syn001 import TEMPERATURE_TOLERANCE
from openflowsheet.thermo import PropertyRequest, PropertyResult
from openflowsheet.thermo.syn001 import Syn001Provider
from openflowsheet.verify import CheckResult
from openflowsheet.verify.certificate import verify_revision
from openflowsheet.verify.checks import KIND_REFERENCE, admissibility_checks
from openflowsheet.verify.saturation import _root, band_ends, saturation_closure

#: A91 (a): 1 000× under `τ_T`, 700× above the measured floor (≤ 1.4e-12 K at judged states).
REGISTERED_ROOT_BOUND = 1e-9
#: A91 (b): NET-11 start 16's closure, the twin's 3.3368 K at the registered liquid heater
#: outlet; ±0.01 K covers the recorded state's difference from the root.
NET11_START16_CLOSURE = 3.34
NET11_START16_WINDOW = 0.01
NET11_START16 = REPO_ROOT / "tests" / "fixtures" / "t06" / "net11_start16_run1_state.json"


def _run(case: str) -> Any:
    (run,) = [run for run in REVISION_RUNS if run.case == case]
    return solved(run)


def _certificate(item: Any, state: Mapping[str, float] | None = None) -> Any:
    return verify_revision(
        item.binding,
        item.document,
        item.run,
        state=state,
        solve_plan=item.plan.steps[-1].solve_plan,
    )


def _closures(checks: list[CheckResult]) -> list[CheckResult]:
    return [check for check in checks if check.id.endswith(".closure")]


# -- the saturation closure itself -------------------------------------------------------------


def test_the_one_ended_helper_returns_band_ends_doubles() -> None:
    """Spec §8.8 (W19): `saturation_closure` bisects the liquid's bubble function and the vapour's
    dew function only, and returns the same doubles `band_ends` gives for those ends."""
    provider = Syn001Provider()
    vapor, liquid, pressure = (0.6, 0.3, 0.1), (0.2, 0.5, 0.8), 1.2e5
    t_bubble = band_ends(provider, liquid, pressure, CONTEXT)[0]
    t_dew = band_ends(provider, vapor, pressure, CONTEXT)[1]
    assert t_bubble is not None and t_dew is not None
    for temperature in (t_bubble, t_dew, 350.0):
        value = saturation_closure(provider, vapor, liquid, temperature, pressure, CONTEXT)
        assert value == max(abs(temperature - t_bubble), abs(temperature - t_dew))


def test_an_end_off_the_domain_is_the_domain_end_on_its_side() -> None:
    """Spec §8.8: the sign of the function at the domain ends says which side the root lies on;
    without `clamp` the bisection's answer is `band_ends`' `None`."""
    assert _root(lambda t: t - 500.0, 280.0, 440.0, clamp=True) == 440.0
    assert _root(lambda t: t - 100.0, 280.0, 440.0, clamp=True) == 280.0
    assert _root(lambda t: t - 500.0, 280.0, 440.0) is None
    assert _root(lambda t: t - 100.0, 280.0, 440.0) is None


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_the_legacy_closure_is_in_kelvin_and_vanishes_at_the_registered_solutions(
    case_id: str,
) -> None:
    """The legacy SYN-001 set (`verify.checks.admissibility_checks`): `S3.closure` against
    `TEMPERATURE_TOLERANCE`, reference 100 K, ≤ 1e-9 K wherever `S3` is two-phase."""
    variants = {
        entry["case_id"]: entry
        for entry in load_yaml(REPO_ROOT / "benchmarks" / "syn001" / "reference_values.yaml")[
            "variants"
        ]
    }
    flowsheet, state = solved_legacy(variants[case_id])
    checks = admissibility_checks(flowsheet.provider, state, CONTEXT)
    for closure in _closures(checks):
        assert closure.id == "phase_admissibility.S3.closure"
        assert (closure.tolerance, closure.reference) == (
            TEMPERATURE_TOLERANCE,
            KIND_REFERENCE["temperature"],
        )
        assert closure.result == "pass" and closure.value is not None
        assert closure.value <= REGISTERED_ROOT_BOUND, closure.value


# -- A91 ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("case", ["THM-01", "NET-03"])
def test_a91a_the_closure_vanishes_at_registered_roots(case: str) -> None:
    """(a) At THM-01's and NET-03's registered roots, on the certificate path: every closure
    ≤ 1e-9 K, `pass`, not near threshold, judged against `τ_T` with reference 100 K."""
    certificate = _certificate(_run(case))
    assert certificate.verification_status == "VERIFIED"
    closures = _closures(certificate.checks)
    assert closures, case
    for closure in closures:
        assert closure.result == "pass" and not closure.near_threshold, closure.id
        assert closure.value is not None and closure.value <= REGISTERED_ROOT_BOUND, closure.id
        assert closure.tolerance == TEMPERATURE_TOLERANCE
        assert closure.reference == KIND_REFERENCE["temperature"]


def _net11_start16() -> dict[str, float]:
    recorded = json.loads(NET11_START16.read_text("utf-8"))
    assert recorded["source"]["verdict_recorded"] == "VERIFIED"
    return {name: float(value) for name, value in recorded["state"]}


def test_a91b_net11_start16s_false_two_phase_label_fails() -> None:
    """(b) Run 1's NET-11 start-16 certified state, replayed through `verify_revision`:
    `U-HEAT` labelled `TWO_PHASE` with `S4.V = 6.3e-11 mol/s` at a liquid 3.34 K below its bubble
    point. The closure fails there at 3.34 K ± 0.01 K (3.3e6 `τ_T`), the verdict is `FAILED`
    with `false_success_detected`, and it is the only check that fails. The pre-A4 formula on the
    same state is ≤ 2.2e-16 — why run 1 certified it `VERIFIED`."""
    item = _run("NET-11")
    state = _net11_start16()
    assert list(state) == list(item.binding.spec.variable_ids)
    certificate = _certificate(item, state)
    assert certificate.verification_status == "FAILED"
    assert certificate.false_success_detected
    failing = [check for check in certificate.checks if check.result == "fail"]
    assert [check.id for check in failing] == ["phase_admissibility.U-HEAT.S4.closure"]
    (closure,) = failing
    assert closure.value == pytest.approx(NET11_START16_CLOSURE, abs=NET11_START16_WINDOW)

    vapor = [state[f"S4.vap.{component}"] for component in "ABC"]
    liquid = [state[f"S4.liq.{component}"] for component in "ABC"]
    before = sum(v / sum(vapor) for v in vapor) - sum(x / sum(liquid) for x in liquid)
    assert abs(before) <= 2.2e-16


class _RefusesProductLnK(Syn001Provider):
    """Refuses `lnK` for a stream whose total flow is below `below` (a split's vapour or liquid
    product, not its feed), except the K-value reference state `(1, 1, 1)` — so the verifier's own
    band of the feed and its K-values are answered, and only the closure's bisection is refused."""

    below = 0.0

    def evaluate_phase(self, request: PropertyRequest, context: Any) -> PropertyResult:
        n = request.state.n
        if "lnK" in request.properties and n != (1.0, 1.0, 1.0) and 0.0 < sum(n) < type(self).below:
            return self._failed(request, "out_of_domain", "test double: a product's lnK")
        return super().evaluate_phase(request, context)


def test_a91c_a_refused_lnk_inside_the_bisection_is_unsupported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(c) THM-01 with a fresh provider that refuses `lnK` for the flash's products: the closure
    is `unsupported`, reason `closure_out_of_domain`, the verdict `UNVERIFIED`, no exception;
    every other check is the honest certificate's."""
    item = _run("THM-01")
    honest = _certificate(item)
    state = item.run.state
    # The flash's feed `S1` is (1, 1, 1) mol/s; its vapour `S2` and liquid `S3` carry 1.18 and
    # 1.82 mol/s.
    feed = sum(state[f"S1.n.{component}"] for component in "ABC")
    products = (state["S2.N"], state["S3.N"])
    assert 0.0 < max(products) < 0.999 * feed, (products, feed)

    class Refusing(_RefusesProductLnK):
        below = 0.999 * feed

    monkeypatch.setattr(certificate_module, "Syn001Provider", Refusing)
    refused = _certificate(item)
    assert refused.verification_status == "UNVERIFIED"
    by_id = {check.id: check for check in refused.checks}
    closure = by_id["phase_admissibility.U-FLASH.S1.closure"]
    assert (closure.result, closure.reason) == ("unsupported", "closure_out_of_domain")
    others = {c.id: c.result for c in refused.checks if c.id != closure.id}
    assert others == {c.id: c.result for c in honest.checks if c.id != closure.id}


@pytest.mark.parametrize("split", ["U-VLV.S2", "U-PHF.S2"])
def test_a91d_a_pure_component_split_at_saturation_keeps_saturation(split: str) -> None:
    """(d) T05b SC-3 (THM-09's flowsheet): each pure-component split within `τ_T` of `T_sat` is
    judged by ADR 0012 D7's `.saturation` and has no `.closure` — D7 keeps precedence."""
    checks = solved_t05b("SC-3").checks()
    assert checks[f"phase_admissibility.{split}.saturation"].result == "pass"
    assert f"phase_admissibility.{split}.closure" not in checks
