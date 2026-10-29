"""`wilson-ig-v2`: `wilson-ig-v1` and its molar entropy `s` in closed form (S11 units design §4.6).

**Every v1 answer, bit for bit.** The provider holds a `WilsonIdealGasProvider` on the same record
file and forwards to it: a request without `s` returns v1's result, `flash` is v1's and `stability`
is v1's report, and a request with `s` makes one v1 call for the other properties (and the
`lnphi_<c>` the entropy needs) and returns v1's values and derivatives for them untouched, with `s`
added. Every `PropertyResult` and `FlashResult` is labelled `provider_id = "wilson-ig-v2"`
(orchestrator ruling, S11D_DECISIONS); nothing else in it differs from v1's. v1's module is not
edited (its `implementation_sha256` hashes it).

**The entropy** follows from the potential v1 already implements (S10's γ–φ-IG,
`g = Σ x_i [μ_i^ig(T, P₀) + RT ln(x_i φ_i P/P₀)]`, `h^E = 0`, constant Λ, and
`h^L = Σ x_i (h_i^ig − Δh_i)`), as `s = (h − g)/T`. With θ = T/1000 K, θ₀ = 0.29815,
P₀ = 101 325 Pa, the records' c_p^ig/R coefficients b₀…b₄ and vapour-pressure coefficients b, c, d:

- σ_i = b₀ ln(θ/θ₀) + Σ_{k=1..4} b_k (θ^k − θ₀^k)/k, so dσ_i/dT = (c_p,i^ig/R)/T;
- λ_i = Δh_i/(RT) = T d ln P_i^sat/dT = −b/θ + c + 2dθ²;
- VAPOR: s/R = Σ y_i σ_i − Σ′ y_i ln y_i − ln(P/P₀) (v1's vapour ln φ ≡ 0);
- LIQUID: s/R = Σ x_i (σ_i − λ_i − ln φ_i^L) − Σ′ x_i ln x_i − ln(P/P₀), ln φ^L being v1's.

Σ′ skips zero fractions (0 ln 0 = 0). The datum is s_i^ig(298.15 K, P₀) = 0 for every component:
the records carry no entropy constant, and every S11 use is an entropy difference at fixed
composition (ADR 0051, Q22).

**Derivatives** (order 1 in `T`, `P` and every `n_<c>`, as v1 declares): ∂s/∂T is
R Σ x_i (c_p,i^ig/R)/T for the vapour and R Σ x_i [(c_p,i^ig/R)/T − dλ_i/dT − ∂ ln φ_i^L/∂T]
(v1's T-derivative) for the liquid, which is c_p^L/T; ∂s/∂P is −R/P for the vapour and the model
identity `0.0` for the liquid (the method's liquid g does not depend on P); ∂s/∂n_j, projected as
v1 projects, is R (a_j − ln x_j − ln(P/P₀) − s/R)/n_tot with a_j = σ_j − [λ_j for the liquid] −
ln φ_j, by Gibbs–Duhem (Σ_i x_i ∂ ln φ_i/∂n_j = 0). At a zero mole fraction ∂s/∂n of that component
is singular, and a request for any n-derivative of `s` there is refused `unsupported` with
"derivative_singular: ds/dn_<c> at n_<c> = 0"; its T and P derivatives are answered.

**Not offered: `v` or `Z`.** The method's liquid has no molar volume (S10 §3.4); a declared v^L = 0
would make a pump compute W = 0 silently.
"""

from __future__ import annotations

import hashlib
import math
import os
from dataclasses import replace
from pathlib import Path
from typing import Final

from openflowsheet.compiled import EvaluationContext
from openflowsheet.thermo import (
    FlashRequest,
    FlashResult,
    Phase,
    PropertyCapabilities,
    PropertyRequest,
    PropertyResult,
    StreamState,
)
from openflowsheet.thermo.stability import StabilityReport
from openflowsheet.thermo.wilson_ig import (
    T_UNIT,
    THETA_0,
    R,
    WilsonIdealGasProvider,
    WilsonRecords,
)

PROVIDER_ID: Final = "wilson-ig-v2"
#: Pa, the entropy's reference pressure P₀ (S11 units design §4.6).
P_0: Final = 101_325.0

#: The sentence `describe()` adds to v1's `uncertainty`, `data_provenance` and
#: `numerical_limitations` (S11 units design §4.6).
UNCERTAINTY_ADDED: Final = (
    "The molar entropy s carries the records' uncertainty through the same c_p and vapour-pressure "
    "coefficients; its datum (s_i^ig = 0 at 298.15 K and 101325 Pa) is a convention, not data."
)
PROVENANCE_ADDED: Final = (
    "wilson-ig-v2 adds the molar entropy s in closed form from the same records (S11 units "
    "design section 4.6, ADR 0051); every other answer is wilson-ig-v1's, unchanged."
)
LIMITATION_ADDED: Final = (
    "s is offered with the datum s_i^ig(298.15 K, 101325 Pa) = 0 for every component, so only "
    "entropy differences at fixed composition are meaningful; d s/d n is refused at a zero mole "
    "fraction (derivative_singular); no v or Z is offered."
)


def _sigma_lambda(
    records: WilsonRecords, temperature: float
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
    """`(σ_i, λ_i, dσ_i/dT, dλ_i/dT)` per component at `temperature` (S11 units design §4.6)."""
    theta = temperature / T_UNIT
    log_ratio = math.log(theta / THETA_0)
    sigma, lam, dsigma, dlam = [], [], [], []
    for (b0, b1, b2, b3, b4), (_, b, c, d) in zip(records.cp, records.vapour_pressure, strict=True):
        cp_over_r = b0 + theta * (b1 + theta * (b2 + theta * (b3 + theta * b4)))
        sigma.append(
            b0 * log_ratio
            + sum(
                bk * (theta**k - THETA_0**k) / k for k, bk in ((1, b1), (2, b2), (3, b3), (4, b4))
            )
        )
        lam.append(-b / theta + c + 2.0 * d * theta * theta)
        dsigma.append(cp_over_r / temperature)
        dlam.append((b / (theta * theta) + 4.0 * d * theta) / T_UNIT)
    return tuple(sigma), tuple(lam), tuple(dsigma), tuple(dlam)


class WilsonIdealGasProviderV2:
    """`wilson-ig-v1` with `s` (S11 units design §4.6). Non-`s` answers: v1's, labelled v2."""

    def __init__(self, records_path: str | os.PathLike[str] | None = None) -> None:
        self._v1 = WilsonIdealGasProvider(records_path)
        self._records = self._v1.records
        ids = self._records.components
        self._lnphi = tuple(f"lnphi_{c}" for c in ids)
        self._flows = tuple(f"n_{c}" for c in ids)
        self._implementation_sha256 = hashlib.sha256(
            Path(__file__).read_bytes() + b"\n" + self._v1.describe().implementation_sha256.encode()
        ).hexdigest()

    @property
    def records(self) -> WilsonRecords:
        return self._records

    @property
    def v1(self) -> WilsonIdealGasProvider:
        """The v1 provider every non-`s` answer comes from."""
        return self._v1

    def describe(self) -> PropertyCapabilities:
        inner = self._v1.describe()
        return replace(
            inner,
            provider_id=PROVIDER_ID,
            implementation_sha256=self._implementation_sha256,
            properties=(*inner.properties, "s"),
            uncertainty=f"{inner.uncertainty} {UNCERTAINTY_ADDED}",
            data_provenance=f"{inner.data_provenance} {PROVENANCE_ADDED}",
            numerical_limitations=(*inner.numerical_limitations, LIMITATION_ADDED),
        )

    def evaluate_phase(
        self, request: PropertyRequest, context: EvaluationContext
    ) -> PropertyResult:
        """v1's answer; with `s` requested, v1's answer for the rest and `s` added (§4.6)."""
        if "s" not in request.properties:
            return replace(self._v1.evaluate_phase(request, context), provider_id=PROVIDER_ID)
        others = tuple(name for name in request.properties if name != "s")
        asked = (*others, *(name for name in self._lnphi if name not in others))
        inner = self._v1.evaluate_phase(replace(request, properties=asked), context)
        if inner.status != "ok":
            return replace(inner, provider_id=PROVIDER_ID)

        state = request.state
        ids = self._records.components
        wants_n = [name for name in request.derivatives if name in self._flows]
        zero = [c for c, value in zip(ids, state.n, strict=True) if value == 0.0]
        if wants_n and zero:
            return PropertyResult(
                status="unsupported",
                phase_signature=None,
                values={},
                provider_id=PROVIDER_ID,
                reference_convention=inner.reference_convention,
                message=f"derivative_singular: ds/dn_{zero[0]} at n_{zero[0]} = 0",
            )

        total = state.total_flow
        x = tuple(value / total for value in state.n)
        liquid = request.phase == "LIQUID"
        sigma, lam, dsigma, dlam = _sigma_lambda(self._records, state.temperature)
        lnphi = tuple(inner.values[name] for name in self._lnphi)
        a = tuple(sigma[i] - (lam[i] if liquid else 0.0) - lnphi[i] for i in range(len(ids)))
        ln_pressure = math.log(state.pressure / P_0)
        mixing = sum(xi * math.log(xi) for xi in x if xi > 0.0)
        s_over_r = sum(xi * ai for xi, ai in zip(x, a, strict=True)) - mixing - ln_pressure

        values = {
            name: R * s_over_r if name == "s" else inner.values[name] for name in request.properties
        }
        derivatives: dict[str, dict[str, float]] = {}
        if request.derivatives:
            entry: dict[str, float] = {}
            for wanted in request.derivatives:
                if wanted == "T":
                    if liquid:
                        by_t = sum(
                            x[i] * (dsigma[i] - dlam[i] - inner.derivatives[self._lnphi[i]]["T"])
                            for i in range(len(ids))
                        )
                    else:
                        by_t = sum(xi * di for xi, di in zip(x, dsigma, strict=True))
                    entry[wanted] = R * by_t
                elif wanted == "P":
                    entry[wanted] = 0.0 if liquid else -R / state.pressure
                else:
                    j = self._flows.index(wanted)
                    entry[wanted] = R * (a[j] - math.log(x[j]) - ln_pressure - s_over_r) / total
            for name in request.properties:
                derivatives[name] = entry if name == "s" else dict(inner.derivatives[name])
        return replace(inner, values=values, derivatives=derivatives, provider_id=PROVIDER_ID)

    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult:
        """v1's TP flash, labelled `wilson-ig-v2`; every value v1's."""
        return replace(self._v1.flash(request, context), provider_id=PROVIDER_ID)

    def stability(
        self, state: StreamState, phase: Phase, context: EvaluationContext
    ) -> StabilityReport:
        """v1's stability report, unchanged."""
        return self._v1.stability(state, phase, context)
