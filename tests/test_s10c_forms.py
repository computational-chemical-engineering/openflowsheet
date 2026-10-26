"""S10-C WO-1: equilibrium forms, the column's admission, and the dispatch in `saturation_band` and
`tp_state` (design note `docs/derivations/S10C-design.md` §4.1, §4.2, §4.12; ADR 0049 D1–D2).

The SYN-001 path is proved unchanged by gate G1 (`scripts/s10c_identity.py`), not here. These tests
pin what the γ–φ-IG branch answers, against the provider's own `evaluate_phase`, `flash` and
`stability`, and that the allow-list resolves by identity.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest
from conftest import REPO_ROOT

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.syn001.equilibrium_form import (
    FORM_GAMMA_PHI_IG,
    FORM_SYN001,
    admission,
    composition_dependent,
    equilibrium_form,
    form_of,
)
from openflowsheet.models.syn001.gamma_phi import band_point
from openflowsheet.models.syn001.saturation_band import (
    PRESCREEN_MARGIN,
    outside_the_degeneracy_window,
)
from openflowsheet.models.syn001.tp_state import (
    enthalpy_flow,
    single_phase_admissible,
    tp_state,
)
from openflowsheet.thermo import (
    FlashRequest,
    FlashResult,
    PropertyCapabilities,
    PropertyRequest,
    PropertyResult,
    StreamState,
)
from openflowsheet.thermo.syn001 import Syn001Provider
from openflowsheet.thermo.wilson_ig import WilsonIdealGasProvider

CONTEXT = EvaluationContext(model_version="S10C-WO1@" + "0" * 64, constants_sha256="0" * 64)
VERIFICATION = REPO_ROOT / "benchmarks" / "s10" / "verification-records.yaml"
P_ATM = 101325.0
COMPONENTS = ("VA", "VB", "VC")
FEED = (0.5, 0.5, 0.0)


@pytest.fixture(scope="module")
def wilson() -> WilsonIdealGasProvider:
    return WilsonIdealGasProvider(VERIFICATION)


class Spy:
    """Delegates to `inner`, optionally declaring other capabilities or a non-zero vapour ln φ,
    and counts `evaluate_phase` calls."""

    def __init__(
        self, inner: Any, capabilities: PropertyCapabilities | None = None, vapour: float = 0.0
    ) -> None:
        self._inner = inner
        self._capabilities = capabilities
        self._vapour = vapour
        self.evaluations = 0

    def describe(self) -> PropertyCapabilities:
        return self._capabilities or self._inner.describe()

    def evaluate_phase(
        self, request: PropertyRequest, context: EvaluationContext
    ) -> PropertyResult:
        self.evaluations += 1
        result = self._inner.evaluate_phase(request, context)
        if request.phase != "VAPOR" or not self._vapour:
            return result
        values = {
            k: v + self._vapour if k.startswith("lnphi_") else v for k, v in result.values.items()
        }
        return dataclasses.replace(result, values=values)

    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult:
        return self._inner.flash(request, context)


# -- the allow-list -------------------------------------------------------------------------------


def test_the_allow_list_resolves_by_identity(wilson: WilsonIdealGasProvider) -> None:
    syn001 = Syn001Provider()
    form = equilibrium_form(syn001)
    assert form is not None and form.form_id == FORM_SYN001 and not form.composition_dependent
    assert form.domain == {"T": (280.0, 440.0), "P": (50_000.0, 200_000.0)}
    form = equilibrium_form(wilson)
    assert form is not None and form.form_id == FORM_GAMMA_PHI_IG and form.composition_dependent
    assert form.components == COMPONENTS and form.domain["T"] == (300.0, 420.0)
    real = WilsonIdealGasProvider(REPO_ROOT / "benchmarks" / "s10" / "records.yaml")
    form = equilibrium_form(real)
    assert form is not None and form.form_id == FORM_GAMMA_PHI_IG
    assert composition_dependent(wilson) and not composition_dependent(syn001)
    described = syn001.describe()
    for provider_id, convention in (
        ("pr-c1-v1", "SYN-001-ref-v1"),
        ("syn001", "spy-ref"),
        ("wilson-ig-v1", "spy-ref"),
        ("wilson-ig-v1", "SYN-001-ref-v1"),
    ):
        spy = dataclasses.replace(
            described, provider_id=provider_id, reference_convention=convention
        )
        assert form_of(spy) is None


# -- admission ------------------------------------------------------------------------------------


def test_admission_passes_syn001_without_evaluating_and_wilson_with_one_probe(
    wilson: WilsonIdealGasProvider,
) -> None:
    syn001 = Spy(Syn001Provider())
    assert admission("col", syn001, CONTEXT) is None and syn001.evaluations == 0
    spy = Spy(wilson)
    assert admission("col", spy, CONTEXT) is None and spy.evaluations == 1


def test_admission_refuses_by_identity_capability_and_vapour_identity(
    wilson: WilsonIdealGasProvider,
) -> None:
    described = wilson.describe()
    outside = Spy(wilson, dataclasses.replace(described, reference_convention="spy-ref"))
    refused = admission("col", outside, CONTEXT)
    assert refused is not None and outside.evaluations == 0
    assert refused.outcome == "CAPABILITY_UNAVAILABLE"
    assert refused.cause == "unsupported(column_property_method:wilson-ig-v1)"
    assert "wilson-ig-v1 (reference conventions 'WILSON-IG-ref-v1', 'S10-VER-ref-v1')" in (
        refused.message
    )
    lnphi = tuple(p for p in described.properties if p.startswith("lnphi_"))
    stripped = Spy(wilson, dataclasses.replace(described, properties=("h",)))
    refused = admission("col", stripped, CONTEXT)
    assert refused is not None and stripped.evaluations == 0
    assert refused.cause == "unsupported(column_property_method:wilson-ig-v1)"
    assert "declares wilson-ig-v1's identity but not its capabilities" in refused.message
    assert all(name in refused.message for name in lnphi)
    vapour = Spy(wilson, vapour=1e-300)
    refused = admission("col", vapour, CONTEXT)
    assert refused is not None and vapour.evaluations == 1
    assert "vapour ln phi is not identically zero" in refused.message


# -- the dispatch in tp_state ---------------------------------------------------------------------


def _h(provider: WilsonIdealGasProvider, state: StreamState, phase: str) -> PropertyResult:
    result = provider.evaluate_phase(
        PropertyRequest(state=state, phase=phase, properties=("h",), derivatives=("T",)), CONTEXT
    )
    assert result.status == "ok"
    return result


@pytest.mark.parametrize("phase", ["LIQUID", "VAPOR"])
def test_enthalpy_flow_is_the_mixture_flow(wilson: WilsonIdealGasProvider, phase: str) -> None:
    """`Ḣ = n_tot h`, bitwise from one call; a dormant stream is exactly 0.0 and not evaluated."""
    state = StreamState(n=(0.3, 1.2, 0.0), temperature=350.0, pressure=P_ATM)
    status, value, message = enthalpy_flow(wilson, state, phase, COMPONENTS, CONTEXT)
    assert (status, message) == ("ok", "")
    assert value == state.total_flow * _h(wilson, state, phase).values["h"]
    spy = Spy(wilson)
    dormant = StreamState(n=(0.0, 0.0, 0.0), temperature=350.0, pressure=P_ATM)
    assert enthalpy_flow(spy, dormant, phase, COMPONENTS, CONTEXT) == ("ok", 0.0, "")
    assert spy.evaluations == 0


def test_tp_state_totals_the_mixture_enthalpy_of_both_phases(
    wilson: WilsonIdealGasProvider,
) -> None:
    state = StreamState(n=FEED, temperature=344.5, pressure=P_ATM)
    answer = tp_state(wilson, state, CONTEXT)
    assert answer.status == "ok" and answer.phase_signature == "TWO_PHASE"
    assert answer.vapor is not None and answer.liquid is not None
    expected = answer.vapor.total_flow * _h(wilson, answer.vapor, "VAPOR").values["h"]
    expected += answer.liquid.total_flow * _h(wilson, answer.liquid, "LIQUID").values["h"]
    assert answer.enthalpy_flow == expected


def test_single_phase_admissibility_uses_the_mixture_enthalpy_and_slope(
    wilson: WilsonIdealGasProvider,
) -> None:
    """A subcooled liquid is admissible as LIQUID with the mixture `n_tot h`; as VAPOR it is not;
    a two-phase stream is admissible in neither phase."""
    bubble = band_point(wilson, FEED, P_ATM, 0.0, CONTEXT)
    dew = band_point(wilson, FEED, P_ATM, 1.0, CONTEXT)
    assert bubble.temperature is not None and dew.temperature is not None
    cold = StreamState(n=FEED, temperature=bubble.temperature - 10.0, pressure=P_ATM)
    admissible, enthalpy, gap, status, _ = single_phase_admissible(
        wilson, cold, "LIQUID", COMPONENTS, CONTEXT
    )
    assert admissible and status == "ok" and gap == 0.0
    assert enthalpy == cold.total_flow * _h(wilson, cold, "LIQUID").values["h"]
    admissible, _, gap, status, _ = single_phase_admissible(
        wilson, cold, "VAPOR", COMPONENTS, CONTEXT
    )
    assert not admissible and status == "ok" and gap > 1.0
    hot = StreamState(n=FEED, temperature=dew.temperature + 10.0, pressure=P_ATM)
    assert single_phase_admissible(wilson, hot, "VAPOR", COMPONENTS, CONTEXT)[0]
    middle = StreamState(
        n=FEED, temperature=0.5 * (bubble.temperature + dew.temperature), pressure=P_ATM
    )
    for phase in ("LIQUID", "VAPOR"):
        admissible, _, _, status, _ = single_phase_admissible(
            wilson, middle, phase, COMPONENTS, CONTEXT
        )
        assert not admissible and status == "ok"


# -- the dispatch in saturation_band --------------------------------------------------------------


def test_the_degeneracy_prescreen_decides_only_on_the_bubble_side(
    wilson: WilsonIdealGasProvider,
) -> None:
    """For γ–φ-IG only `g(T − 2τ; 0) > 0` with K at the stream decides (`True`); the β = 1 side
    is "not decided" (`False`), where SYN-001 would test it (§4.12)."""
    bubble = band_point(wilson, FEED, P_ATM, 0.0, CONTEXT)
    dew = band_point(wilson, FEED, P_ATM, 1.0, CONTEXT)
    assert bubble.temperature is not None and dew.temperature is not None
    two_phase = 0.5 * (bubble.temperature + dew.temperature)
    assert outside_the_degeneracy_window(wilson, FEED, two_phase, P_ATM, CONTEXT)
    assert outside_the_degeneracy_window(wilson, FEED, dew.temperature + 5.0, P_ATM, CONTEXT)
    # Subcooled: the bubble side is negative and the dew side, which would decide, is not tested.
    assert not outside_the_degeneracy_window(wilson, FEED, bubble.temperature - 5.0, P_ATM, CONTEXT)
    # Within 2τ above the bubble point, g(T − 2τ; 0) < 0: not decided.
    near = bubble.temperature + 0.5 * PRESCREEN_MARGIN
    assert not outside_the_degeneracy_window(wilson, FEED, near, P_ATM, CONTEXT)
    # A provider refusal (T − 2τ off the domain) decides nothing.
    t_min = wilson.describe().domain["T"][0]
    assert not outside_the_degeneracy_window(wilson, FEED, t_min, P_ATM, CONTEXT)
