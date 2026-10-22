"""S05 review (design lane, 2026-10-22): adversarial checks written by the `reviewer`.

`docs/reviews/S05-review.md` F1 (R-595): `_bracketed_density` can return a bisection midpoint as
"converged". When Newton's correction is below half an ulp of ρ, the new iterate equals the bracket
end that was just set, so the safeguard bisects. The step is then far above the previous one, and
`_converged`'s stagnation clause accepts it. The provider answers `ok` with a density that is off by
10-130 %. The strict xfails below are the failing states. They turn into failures (XPASS) once
WO-S05-3 fixes the solver, and the build lane then removes the marks.

The check is the root residual in density units, |p(ρ, T) − P| / (ρ (∂p/∂ρ)_T), where ρ = M/v is
taken from the provider's own answer. p and (∂p/∂ρ)_T come from `phi_jet`, the tested surface (A03).
The measured floor on 10 980 grid states is ≤ 5e-16 wherever the root is right, so the bound 1e-12
leaves 2000x margin and still catches a 1e-9 density error (A05's v bound).
"""

from __future__ import annotations

import pytest

from openflowsheet.compiled import EvaluationContext
from openflowsheet.thermo import Phase, PropertyRequest, StreamState
from openflowsheet.thermo import iapws95 as w

CONTEXT = EvaluationContext(model_version="s05-review", constants_sha256="0" * 64)
PROVIDER = w.Iapws95Provider()
ROOT_TOL = 1e-12

_F1 = "R-595 / review F1: a bisection midpoint accepted as converged; remove when WO-S05-3 lands"


def root_residual(t: float, p: float, phase: Phase) -> float:
    state = StreamState(n=(1.0,), temperature=t, pressure=p)
    result = PROVIDER.evaluate_phase(PropertyRequest(state, phase, ("v",), ()), CONTEXT)
    assert result.status == "ok", result.message
    rho = w.M / result.values["v"]
    delta = rho / w.RHO_C
    _, res = w.phi_jet(w.T_C / t, delta)
    rt = w.R_S * t
    pressure = rho * rt * (1.0 + delta * res.d)
    slope = rt * (1.0 + 2.0 * delta * res.d + delta * delta * res.dd)
    return abs(pressure - p) / (rho * slope)


CASES = [
    # Controls: the same pressure, nearby temperatures, roots solved correctly.
    pytest.param(600.0, 1.0e8, "LIQUID", id="control-600K-1e8-LIQUID"),
    pytest.param(500.0, 1.0e8, "LIQUID", id="control-500K-1e8-LIQUID"),
    pytest.param(660.0, 1.0e8, "VAPOR", id="control-660K-1e8-VAPOR"),
    # A22's own grid: answered ok, (dv/dP)_T < 0 and cp > 0, yet off by 83 % and 53 % in ρ.
    pytest.param(
        700.0,
        1.0e8,
        "VAPOR",
        id="A22grid-700K-1e8",
        marks=pytest.mark.xfail(strict=True, reason=_F1),
    ),
    pytest.param(
        750.0,
        1.0e8,
        "VAPOR",
        id="A22grid-750K-1e8",
        marks=pytest.mark.xfail(strict=True, reason=_F1),
    ),
    # Dense-grid finds (99 of 10 980 states; 97 LIQUID below T_c, 10^3..10^8 Pa).
    pytest.param(
        599.7899159663866,
        1.0e8,
        "LIQUID",
        id="grid-599.79K-1e8-LIQUID",
        marks=pytest.mark.xfail(strict=True, reason=_F1),
    ),
    pytest.param(
        631.1966386554623,
        63095734.44801943,
        "LIQUID",
        id="grid-631.20K-6.3e7-LIQUID",
        marks=pytest.mark.xfail(strict=True, reason=_F1),
    ),
    pytest.param(
        659.0872881355932,
        1.0e8,
        "VAPOR",
        id="grid-659.09K-1e8-VAPOR",
        marks=pytest.mark.xfail(strict=True, reason=_F1),
    ),
]


@pytest.mark.parametrize(("t", "p", "phase"), CASES)
def test_review_f1_density_root_residual(t: float, p: float, phase: Phase) -> None:
    assert root_residual(t, p, phase) <= ROOT_TOL
