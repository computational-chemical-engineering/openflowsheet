"""L01 review (design lane, `reviewer`): adversarial tests for `pr-lib-v1`'s vapour rule.

`docs/reviews/L01-review.md` M-1 and S-2; register R-540.

* **M-1.** ADR 0026 D2's metastability guard compares two roots of the *same* composition. For a
  mixture that is not a stability test: `pr-lib-v1` answers `ok` VAPOR where PR itself says the
  vapour is unstable to a pure-component liquid trial phase (tangent-plane distance tm_i < 0),
  e.g. a cooled syngas whose water fugacity is ~100x that of pure liquid water. R-540 adds the
  refusal `vapour_unstable`; the provider half of those tests is a strict xfail until the fix
  work order lands it, the independent half (tm from this file's own transcription) passes now.
* **S-2.** The liquid-like guard on a mixture: a pair of states whose classification flips if
  b_mix is replaced by the smallest or the largest b_i of the components present.

The expectations here are an independent float transcription of PR 1976 (records read with
`yaml`, roots by `numpy.roots`); nothing is taken from `pr_lib`'s closed forms or root finder.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from conftest import REPO_ROOT, load_yaml

from openflowsheet.compiled import EvaluationContext
from openflowsheet.thermo import PropertyRequest, StreamState
from openflowsheet.thermo.pr_lib import COMPONENTS, PrLibProvider

R = 8.31446261815324
V_C_OVER_B = 3.951373035591441
RECORDS = load_yaml(REPO_ROOT / "benchmarks" / "l01" / "components.yaml")["components"]
CONTEXT = EvaluationContext(model_version="l01-review", constants_sha256="0" * 64)
PROVIDER = PrLibProvider()


def _param(record: dict, name: str) -> float:
    return float(record["parameters"][name]["value"])


def _a_b(temperature: float) -> tuple[list[float], list[float]]:
    a, b = [], []
    for record in RECORDS:
        tc, pc = _param(record, "critical_temperature"), _param(record, "critical_pressure")
        omega = _param(record, "acentric_factor")
        kappa = 0.37464 + 1.54226 * omega - 0.26992 * omega**2
        alpha = (1.0 + kappa * (1.0 - math.sqrt(temperature / tc))) ** 2
        a.append(0.45724 * (R * tc) ** 2 / pc * alpha)
        b.append(0.07780 * R * tc / pc)
    return a, b


def _phase(
    temperature: float, pressure: float, y: list[float]
) -> tuple[list[float], list[list[float]], float]:
    """(admissible roots ascending, ln phi_i at each root, b_mix): vdW one-fluid, k_ij = 0."""
    a, b = _a_b(temperature)
    nc = len(y)
    s = [sum(y[j] * math.sqrt(a[i] * a[j]) for j in range(nc)) for i in range(nc)]
    a_m = sum(y[i] * s[i] for i in range(nc))
    b_m = sum(y[i] * b[i] for i in range(nc))
    big_a = a_m * pressure / (R * temperature) ** 2
    big_b = b_m * pressure / (R * temperature)
    coefficients = [
        1.0,
        -(1.0 - big_b),
        big_a - 3 * big_b**2 - 2 * big_b,
        -(big_a * big_b - big_b**2 - big_b**3),
    ]
    roots = sorted(r.real for r in np.roots(coefficients) if abs(r.imag) < 1e-12 and r.real > big_b)
    q = 2.0 * math.sqrt(2.0)
    ln_phi = []
    for z in roots:
        log_term = math.log((z + (1 + math.sqrt(2.0)) * big_b) / (z + (1 - math.sqrt(2.0)) * big_b))
        ln_phi.append(
            [
                b[i] / b_m * (z - 1)
                - math.log(z - big_b)
                - big_a / (q * big_b) * (2 * s[i] / a_m - b[i] / b_m) * log_term
                for i in range(nc)
            ]
        )
    return roots, ln_phi, b_m


def _min_tm(temperature: float, pressure: float, n: tuple[float, ...]) -> float:
    """min_i tm_i, tm_i = ln phi_i^pure(min-G root) - ln y_i - ln phi_i(y, largest root): the
    tangent-plane distance of the pure-i trial phase. tm_i < 0 proves the vapour unstable."""
    total = sum(n)
    y = [value / total for value in n]
    _, ln_phi, _ = _phase(temperature, pressure, y)
    vapour = ln_phi[-1]
    worst = math.inf
    for i, yi in enumerate(y):
        if yi == 0.0:
            continue
        pure = [1.0 if k == i else 0.0 for k in range(len(y))]
        _, pure_ln_phi, _ = _phase(temperature, pressure, pure)
        worst = min(worst, min(row[i] for row in pure_ln_phi) - math.log(yi) - vapour[i])
    return worst


def _flows(**named: float) -> tuple[float, ...]:
    return tuple(named.get(c, 0.0) for c in COMPONENTS)


def _evaluate(temperature: float, pressure: float, n: tuple[float, ...]):  # noqa: ANN202
    request = PropertyRequest(
        state=StreamState(n=n, temperature=temperature, pressure=pressure),
        phase="VAPOR",
        properties=("h", "Z", "v"),
        derivatives=("T", "P"),
    )
    return PROVIDER.evaluate_phase(request, CONTEXT)


#: States PR itself declares unstable (tm < 0 by a margin far above rounding), each answered `ok`.
UNSTABLE = {
    # water partial pressure 3.9x PR's P_sat(330 K) = 15 482 Pa; tm_H2O = -1.35
    "H2O_0.6_N2_0.4_330K_1bar": (330.0, 1.0e5, _flows(H2O=0.6, N2=0.4)),
    # a reformer outlet cooled to 40 C at 30 bar; tm_H2O = -4.6 (fugacity ~100x pure liquid's)
    "syngas_313K_30bar": (313.15, 3.0e6, _flows(H2=0.45, N2=0.15, CH4=0.02, H2O=0.30, CO2=0.08)),
    # propane partial pressure 0.5 MPa above PR's P_sat(250 K); tm_C3H8 = -0.62
    "C3H8_0.5_N2_0.5_250K_1MPa": (250.0, 1.0e6, _flows(C3H8=0.5, N2=0.5)),
}

#: Registered admitted mixtures (L01.A14/A15/A19): the new guard must leave them admitted.
ADMITTED = {
    "V1L": (
        700.0,
        5.0e6,
        _flows(
            H2=0.30, N2=0.04, Ar=0.01, CH4=0.18, H2O=0.30, CO2=0.10, O2=0.02, C2H6=0.03, C3H8=0.02
        ),
    ),
    "V2L": (500.0, 1.0e6, _flows(H2O=0.90, CO2=0.05, N2=0.05)),
    "A19_400K": (400.0, 1.0e5, _flows(H2O=0.95, N2=0.05)),
    "C1V": (700.0, 2.0e7, _flows(H2=0.6, N2=0.2, Ar=0.05, CH4=0.15)),
    "C1W": (300.0, 1.0e5, _flows(H2=0.25, N2=0.25, Ar=0.25, CH4=0.25)),
}


@pytest.mark.parametrize("sid", list(UNSTABLE))
def test_m1_the_states_are_unstable_in_pr_itself(sid: str) -> None:
    assert _min_tm(*UNSTABLE[sid]) <= -0.5


@pytest.mark.parametrize("sid", list(ADMITTED))
def test_m1_the_registered_admitted_states_are_stable_to_every_pure_trial_phase(sid: str) -> None:
    assert _min_tm(*ADMITTED[sid]) >= 0.04


@pytest.mark.xfail(
    strict=True,
    reason="L01 review M-1 / R-540: pr-lib-v1 answers ok where PR's own pure-trial tangent-plane "
    "distance is negative; the fix work order adds the refusal vapour_unstable",
)
@pytest.mark.parametrize("sid", list(UNSTABLE))
def test_m1_an_unstable_vapour_is_refused_vapour_unstable(sid: str) -> None:
    result = _evaluate(*UNSTABLE[sid])
    assert result.status == "unsupported", (result.status, result.values)
    assert result.message.startswith("vapour_unstable:"), result.message
    assert result.values == {} and result.phase_signature is None


#: S-2: (T, P, n, expected code); the test derives v/b for b_mix, the smallest and the largest b_i.
LIQUID_LIKE_PAIR = {
    "C2H6_CH4_350K_15MPa": (350.0, 1.5e7, _flows(CH4=0.5, C2H6=0.5), "ok"),
    "C2H6_CH4_350K_20MPa": (350.0, 2.0e7, _flows(CH4=0.5, C2H6=0.5), "vapour_root_liquid_like"),
}


@pytest.mark.parametrize("sid", list(LIQUID_LIKE_PAIR))
def test_s2_the_liquid_like_guard_uses_b_mix(sid: str) -> None:
    temperature, pressure, n, code = LIQUID_LIKE_PAIR[sid]
    total = sum(n)
    y = [value / total for value in n]
    roots, _, b_m = _phase(temperature, pressure, y)
    assert len(roots) == 1
    v = roots[-1] * R * temperature / pressure
    _, b = _a_b(temperature)
    present = [b[i] for i, yi in enumerate(y) if yi > 0.0]
    # Not vacuous: the smallest-b variant admits the refused state, the largest-b variant refuses
    # the admitted one.
    if code == "ok":
        assert v / b_m >= V_C_OVER_B * 1.02 and v / max(present) < V_C_OVER_B
    else:
        assert v / b_m <= V_C_OVER_B * 0.98 and v / min(present) > V_C_OVER_B
    result = _evaluate(temperature, pressure, n)
    if code == "ok":
        assert result.status == "ok", result.message
    else:
        assert result.status == "unsupported" and result.message.startswith(f"{code}:"), (
            result.message
        )
