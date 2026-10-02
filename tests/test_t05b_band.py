"""T05b W1: the saturation band and the degeneracy test, in the unit layer and in the verifier.

B05 (spec §14): for the 8 grid compositions `T_b` and `T_d` within 1e-10 K of
`ref.kernel_grid.*.band`; `δ` at NP-1…NP-G's roots within 1e-10 K of `ref`; the degenerate
classification of every state of §12.4 and §12.7 equal to `ref`'s — each in both layers, which
share no code (R-016; `test_t05_table_independence.py` pins the verifier's imports). Plus the
primitive's own properties from spec §4.1–§4.2 (split nonnegative and conserving, `T(β)`
nondecreasing, the pure limit) and its typed failures.

The 1e-10 K tolerance is B05's: both bisections close to adjacent doubles (a few 1e-14 K near
360 K), and the 40-digit ends are registered to 20 digits.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Callable, Mapping
from typing import Any

import pytest
from t05_support import CONTEXT, PROVIDER
from t05_support import REF as T05_REF
from t05b_support import REF, error, number

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.syn001 import saturation_band as unit
from openflowsheet.thermo import (
    FlashRequest,
    FlashResult,
    PropertyCapabilities,
    PropertyProvider,
    PropertyRequest,
    PropertyResult,
)
from openflowsheet.verify import saturation as verifier

#: B05's tolerance on a band end and on `δ`, K.
BAND_TOLERANCE = 1e-10

Flows = tuple[float, ...]


def unit_ends(n: Flows, pressure: float) -> tuple[float | None, float | None]:
    bubble = unit.band_temperature(PROVIDER, n, pressure, 0.0, CONTEXT)
    dew = unit.band_temperature(PROVIDER, n, pressure, 1.0, CONTEXT)
    return bubble.temperature, dew.temperature


def verifier_ends(n: Flows, pressure: float) -> tuple[float | None, float | None]:
    return verifier.band_ends(PROVIDER, n, pressure, CONTEXT)


def unit_distance(n: Flows, temperature: float, pressure: float) -> float:
    return unit.degeneracy_distance(PROVIDER, n, temperature, pressure, CONTEXT)


def verifier_distance(n: Flows, temperature: float, pressure: float) -> float:
    return verifier.degeneracy_distance(PROVIDER, n, temperature, pressure, CONTEXT)


LAYERS: Mapping[str, tuple[Callable[..., Any], Callable[..., float], Callable[[float], bool]]] = {
    "unit": (unit_ends, unit_distance, unit.is_temperature_degenerate),
    "verifier": (verifier_ends, verifier_distance, verifier.is_temperature_degenerate),
}


def flows(values: list[str]) -> Flows:
    return tuple(number(value) for value in values)


# ------------------------------------------------------------------------------------- B05


def _grid_compositions() -> dict[str, tuple[Flows, float, Mapping[str, str]]]:
    """The 8 distinct `(n, P)` of `ref.kernel_grid` with their registered band."""
    found: dict[str, tuple[Flows, float, Mapping[str, str]]] = {}
    for state_id, state in REF["kernel_grid"].items():
        composition = state_id.rsplit("-", 1)[0]  # NPK-<trace>-<eps>
        n = flows(state["inputs"]["n_mol_per_s"])
        entry = (n, number(state["inputs"]["P_Pa"]), state["band"])
        if composition in found:
            assert found[composition] == entry, state_id
        found[composition] = entry
    assert len(found) == 8
    return found


GRID = _grid_compositions()


@pytest.mark.parametrize("layer", LAYERS)
@pytest.mark.parametrize("composition", GRID)
def test_b05_the_band_ends_of_the_grid_compositions(layer: str, composition: str) -> None:
    n, pressure, band = GRID[composition]
    t_bubble, t_dew = LAYERS[layer][0](n, pressure)
    assert t_bubble is not None and t_dew is not None
    assert error(t_bubble, band["T_bubble_K"]) <= BAND_TOLERANCE, (t_bubble, band)
    assert error(t_dew, band["T_dew_K"]) <= BAND_TOLERANCE, (t_dew, band)


def _near_pure_roots() -> dict[str, tuple[Flows, float, Mapping[str, Any]]]:
    roots: dict[str, tuple[Flows, float, Mapping[str, Any]]] = {}
    for case_id, case in REF["near_pure_cases"].items():
        # The flowsheet line carries the feed; the registered root is S2's (T, split).
        feed = case["flowsheet"].split("[", 1)[1].split("]", 1)[0]
        n = tuple(float(value.strip().strip("'")) for value in feed.split(","))
        roots[case_id] = (n, number(case["root"]["T_K"]), case)
    return roots


NEAR_PURE = _near_pure_roots()


@pytest.mark.parametrize("layer", LAYERS)
@pytest.mark.parametrize("case_id", NEAR_PURE)
def test_b05_the_degeneracy_distance_at_the_near_pure_roots(layer: str, case_id: str) -> None:
    n, temperature, case = NEAR_PURE[case_id]
    _, distance, degenerate = LAYERS[layer]
    delta = distance(n, temperature, 1.0e5)
    assert error(delta, case["degeneracy_K"]) <= BAND_TOLERANCE, (delta, case["degeneracy_K"])
    assert degenerate(delta) is case["degenerate"]


@pytest.mark.parametrize("layer", LAYERS)
@pytest.mark.parametrize("state_id", list(REF["r007_states"]))
def test_b05_the_r007_states_are_classified_as_registered(layer: str, state_id: str) -> None:
    """§12.7's R7-1…R7-4: `δ` to 1e-12 K (B19's), except R7-4's, registered to 12 digits."""
    state = REF["r007_states"][state_id]
    n = flows(state["n_mol_per_s"])
    _, distance, degenerate = LAYERS[layer]
    delta = distance(n, number(state["T_K"]), number(state["P_Pa"]))
    tolerance = 1e-12 if number(state["degeneracy_K"]) < 1.0 else 1e-9
    assert error(delta, state["degeneracy_K"]) <= tolerance, (delta, state["degeneracy_K"])
    # R7-1 and R7-3 are the degenerate ones; R7-2 and R7-4 are not (spec §10).
    assert degenerate(delta) is (number(state["degeneracy_K"]) <= 1e-6)
    assert degenerate(delta) is (state_id in {"R7-1", "R7-3"})


def _refused_stream(case_id: str) -> tuple[Flows, float, float]:
    """The stream T05's registered R-007 refusal names (the twin's `registered_refusals`)."""
    case = T05_REF["unit_cases"][case_id]
    port = case["expected"]["code"].removeprefix("inadmissible_phase(").split(",")[0]
    if port == "top":
        inlet = case["inputs"]["inlet"]
        n = tuple(
            number(value) * number(fraction)
            for value, fraction in zip(inlet["n_mol_per_s"], case["inputs"]["split"], strict=True)
        )
        return n, number(inlet["T_K"]), number(inlet["P_Pa"])
    document = case["inputs"].get(port) or case["expected"][port]
    return flows(document["n_mol_per_s"]), number(document["T_K"]), number(document["P_Pa"])


@pytest.mark.parametrize("layer", LAYERS)
@pytest.mark.parametrize("case_id", list(REF["t05_registered_refusals_degeneracy_K"]))
def test_b05_t05s_registered_refusals_are_not_degenerate(layer: str, case_id: str) -> None:
    """§12.7's T05 refusals: `δ ≥ 14.27 K`, registered to 1e-6 K (six decimals)."""
    n, temperature, pressure = _refused_stream(case_id)
    _, distance, degenerate = LAYERS[layer]
    delta = distance(n, temperature, pressure)
    registered = REF["t05_registered_refusals_degeneracy_K"][case_id]
    assert error(delta, registered) <= 1e-6, (delta, registered)
    assert not degenerate(delta)


@pytest.mark.parametrize("composition", GRID)
def test_the_two_layers_agree_to_the_last_bits(composition: str) -> None:
    """Independent code, one function: the ends agree far inside B05's tolerance."""
    n, pressure, _ = GRID[composition]
    for ours, theirs in zip(unit_ends(n, pressure), verifier_ends(n, pressure), strict=True):
        assert ours is not None and theirs is not None
        assert abs(ours - theirs) <= 1e-12


# ------------------------------------------------------------ the primitive (spec §4.1–§4.2)

BETAS = [index / 20 for index in range(21)]


@pytest.mark.parametrize("composition", GRID)
def test_t_of_beta_is_nondecreasing_and_the_split_conserves(composition: str) -> None:
    n, pressure, _ = GRID[composition]
    temperatures: list[float] = []
    for beta in BETAS:
        answer = unit.band_temperature(PROVIDER, n, pressure, beta, CONTEXT)
        assert answer.position == "inside" and answer.temperature is not None
        assert answer.evaluations <= unit.MAX_TEMPERATURE_EVALUATIONS
        temperatures.append(answer.temperature)
        vapor, liquid = unit.band_split(n, answer.k_values, beta)
        for v, liq, flow in zip(vapor, liquid, n, strict=True):
            assert v >= 0.0 and liq >= 0.0
            if flow == 0.0:
                assert v == 0.0 and liq == 0.0
            assert abs(v + liq - flow) <= 4 * math.ulp(max(flow, 1e-300))
        if beta == 0.0:
            assert sum(vapor) == 0.0
        if beta == 1.0:
            assert sum(liquid) == 0.0
    assert temperatures == sorted(temperatures)


@pytest.mark.parametrize("beta", [0.0, 0.25, 0.5, 1.0])
def test_one_flowing_component_has_a_point_band_at_t_sat(beta: float) -> None:
    """Spec §4.2's pure limit: `T(β) = T_sat` for every `β` (B at `P_r`: 360 K exactly)."""
    answer = unit.band_temperature(PROVIDER, (0.0, 2.0, 0.0), 1.0e5, beta, CONTEXT)
    assert answer.temperature == 360.0
    assert unit_distance((0.0, 2.0, 0.0), 360.0, 1.0e5) == 0.0
    assert verifier_distance((0.0, 2.0, 0.0), 360.0, 1.0e5) == 0.0


@dataclasses.dataclass(frozen=True)
class ShiftedLnK:
    """A provider test double: the real one with every `ln K_i` moved by `shift`.

    SYN-001's pure-component boiling points all lie inside the domain at every domain pressure
    (A 298–345 K, B 337–387 K, C 375–428 K), so a band off the domain needs a different
    provider: `+10` makes every component volatile enough to boil below 280 K, `-10` above 440 K.
    """

    inner: PropertyProvider
    shift: float

    def describe(self) -> PropertyCapabilities:
        return self.inner.describe()

    def evaluate_phase(
        self, request: PropertyRequest, context: EvaluationContext
    ) -> PropertyResult:
        result = self.inner.evaluate_phase(request, context)
        if "lnK" not in request.properties:
            return result
        values = {
            name: value + self.shift if name.startswith("lnK_") else value
            for name, value in result.values.items()
        }
        return dataclasses.replace(result, values=values)

    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult:
        return self.inner.flash(request, context)


@pytest.mark.parametrize(("shift", "position"), [(10.0, "below"), (-10.0, "above")])
def test_a_band_off_the_domain_is_the_sign_oracle_and_not_degenerate(
    shift: float, position: str
) -> None:
    provider = ShiftedLnK(PROVIDER, shift)
    n = (1.0, 1.0, 1.0)
    for beta in (0.0, 0.5, 1.0):
        answer = unit.band_temperature(provider, n, 1.0e5, beta, CONTEXT)
        assert (answer.position, answer.temperature) == (position, None)
    assert verifier.band_ends(provider, n, 1.0e5, CONTEXT) == (None, None)
    assert math.isinf(unit.degeneracy_distance(provider, n, 360.0, 1.0e5, CONTEXT))
    assert math.isinf(verifier.degeneracy_distance(provider, n, 360.0, 1.0e5, CONTEXT))
    assert not unit.is_temperature_degenerate(math.inf)
    assert not verifier.is_temperature_degenerate(math.inf)


def test_an_exhausted_bisection_is_typed_in_both_layers(monkeypatch: pytest.MonkeyPatch) -> None:
    n = (1.0, 1.0, 1.0)
    with pytest.raises(unit.BandError) as raised:
        unit.band_temperature(PROVIDER, n, 1.0e5, 0.5, CONTEXT, budget=5)
    assert raised.value.status == "not_converged"
    monkeypatch.setattr(verifier, "BISECTION_BUDGET", 5)
    with pytest.raises(verifier.SaturationError) as refused:
        verifier.band_ends(PROVIDER, n, 1.0e5, CONTEXT)
    assert refused.value.status == "not_converged"


@dataclasses.dataclass(frozen=True)
class RefusingLnK:
    """A provider test double: the real one, refusing every `lnK` request."""

    inner: PropertyProvider

    def describe(self) -> PropertyCapabilities:
        return self.inner.describe()

    def evaluate_phase(
        self, request: PropertyRequest, context: EvaluationContext
    ) -> PropertyResult:
        if "lnK" in request.properties:
            return PropertyResult(
                status="unsupported", phase_signature=None, values={}, message="refused"
            )
        return self.inner.evaluate_phase(request, context)

    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult:
        return self.inner.flash(request, context)


def test_a_provider_refusal_is_surfaced_with_its_status_in_both_layers() -> None:
    refusing = RefusingLnK(PROVIDER)
    with pytest.raises(unit.BandError) as raised:
        unit.band_temperature(refusing, (1.0, 1.0, 1.0), 1.0e5, 0.5, CONTEXT)
    assert raised.value.status == "unsupported"
    with pytest.raises(verifier.SaturationError) as refused:
        verifier.band_ends(refusing, (1.0, 1.0, 1.0), 1.0e5, CONTEXT)
    assert refused.value.status == "unsupported"


def test_a_dormant_stream_has_no_band() -> None:
    with pytest.raises(ValueError, match="dormant"):
        unit.band_temperature(PROVIDER, (0.0, 0.0, 0.0), 1.0e5, 0.5, CONTEXT)
    with pytest.raises(ValueError, match="dormant"):
        verifier.band_ends(PROVIDER, (0.0, 0.0, 0.0), 1.0e5, CONTEXT)
