"""Equilibrium forms: which K a unit-layer kernel may assume of a provider (S10-C §4.1, ADR 0049).

SYN-001's K depends on `(T, P)` only, and every procedural kernel and compiled block written for it
encodes that. `wilson-ig-v1` (γ–φ, Wilson liquid, ideal-gas vapour) has `K_i = γ_i(x) P_i^sat(T)/P`,
a function of the **liquid** composition. A kernel that dispatches on the form computes K in the
way the form needs; one that does not would answer a composition-dependent provider silently
wrong.

**Identity, not capability.** The form is resolved from `describe()`'s `(provider_id,
reference_convention)` against an allow-list. A capability rule ("declares ∂/∂n") cannot see the
model class: `pr-c1-v1` and `pr-lib-v1` declare composition derivatives too, and they are φ–φ, so a
γ–φ K-block would ignore their `ln φ^V(y)` (design note D1). Every provider outside the list
resolves to `None`, and the procedural kernels treat `None` exactly as SYN-001 — today's code path
— so a non-admitted provider behaves as before S10-C everywhere except at the column's admission.

**No adapter.** `wilson-ig-v1` does not offer `lnK` or `h_<c>`, and nothing here makes it: its
refusal of `lnK` (`unknown_property`) and its missing `h_<c>` keys are a tripwire that makes any
call site not yet migrated fail loudly (design note §4.12).

This module reads metadata only; the γ–φ-IG primitives are `gamma_phi`'s.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.syn001 import PROVIDER_ID, REFERENCE_CONVENTION
from openflowsheet.thermo import (
    PropertyCapabilities,
    PropertyProvider,
    PropertyRequest,
    StreamState,
)

if TYPE_CHECKING:
    from openflowsheet.models.syn001.cascade import CascadeFailure

__all__ = [
    "ADMITTED",
    "FORM_GAMMA_PHI_IG",
    "FORM_SYN001",
    "EquilibriumForm",
    "admission",
    "composition_dependent",
    "equilibrium_form",
    "form_of",
]

#: SYN-001: `ln K_i(T, P)` from the provider's `lnK`, enthalpies from `h_<c>` (today's code).
FORM_SYN001: Final = "syn001-lnK-TP"
#: γ–φ with an ideal-gas vapour: `ln K_i = ln φ_i^L(T, P, x)` from `lnphi_<c>`, `ln φ^V ≡ 0`,
#: mixture enthalpy `h` (design note D2).
FORM_GAMMA_PHI_IG: Final = "gamma-phi-ig-v1"

#: The allow-list (design note D1): `(provider_id, reference_convention)` → form id.
ADMITTED: Final[Mapping[tuple[str, str], str]] = {
    (PROVIDER_ID, REFERENCE_CONVENTION): FORM_SYN001,
    ("wilson-ig-v1", "WILSON-IG-ref-v1"): FORM_GAMMA_PHI_IG,
    ("wilson-ig-v1", "S10-VER-ref-v1"): FORM_GAMMA_PHI_IG,
    # S11 units design §4.6: v2 is v1 with `s`; its h, lnphi, flash and stability are v1's.
    ("wilson-ig-v2", "WILSON-IG-ref-v1"): FORM_GAMMA_PHI_IG,
    ("wilson-ig-v2", "S10-VER-ref-v1"): FORM_GAMMA_PHI_IG,
}

#: The column's supported scope, as its refusal names it (design note §4.1 admission step 1).
_SCOPE: Final = (
    f"SYN-001 (provider_id {PROVIDER_ID!r}, reference_convention {REFERENCE_CONVENTION!r}) and "
    "wilson-ig-v1 (reference conventions 'WILSON-IG-ref-v1', 'S10-VER-ref-v1')"
)


@dataclass(frozen=True)
class EquilibriumForm:
    """A provider's equilibrium form and the metadata a dispatching kernel reads; no behaviour."""

    form_id: str
    #: `True` when K depends on a phase composition (`FORM_GAMMA_PHI_IG`).
    composition_dependent: bool
    components: tuple[str, ...]
    #: The provider's declared inclusive bounds, `{"T": (lo, hi), "P": (lo, hi)}`.
    domain: Mapping[str, tuple[float, float]]
    provider_id: str
    reference_convention: str


def form_of(capabilities: PropertyCapabilities) -> EquilibriumForm | None:
    """The form `capabilities` declares by identity, or `None` outside the allow-list."""
    form_id = ADMITTED.get((capabilities.provider_id, capabilities.reference_convention))
    if form_id is None:
        return None
    return EquilibriumForm(
        form_id=form_id,
        composition_dependent=form_id == FORM_GAMMA_PHI_IG,
        components=capabilities.components,
        domain={"T": capabilities.domain["T"], "P": capabilities.domain["P"]},
        provider_id=capabilities.provider_id,
        reference_convention=capabilities.reference_convention,
    )


def equilibrium_form(provider: PropertyProvider) -> EquilibriumForm | None:
    """`provider`'s form from one `describe()` (metadata, not an evaluation), or `None`."""
    return form_of(provider.describe())


def composition_dependent(provider: PropertyProvider) -> bool:
    """The dispatch test at the top of a kernel: `True` only for a composition-dependent form.

    `None` (a provider outside the allow-list) and SYN-001 are `False`: today's code path.
    """
    form = equilibrium_form(provider)
    return form is not None and form.composition_dependent


def admission(
    unit: str, provider: PropertyProvider, context: EvaluationContext
) -> CascadeFailure | None:
    """The column's replacement of S03 §9 S11 (design note §4.1): `None` when admitted.

    Every refusal is `CAPABILITY_UNAVAILABLE` with cause `unsupported(column_property_method:<id>)`:
    a provider outside the allow-list (no evaluation); a `wilson-ig-v1` identity without its
    declared capabilities (no evaluation); a vapour `ln φ` that is not identically zero at one probe
    (one evaluation, which turns the allow-list's premise `ln φ^V ≡ 0` into a checked fact).
    """
    # Imported here: `cascade` imports the kernels that import this module.
    from openflowsheet.models.syn001.cascade import CascadeFailure  # noqa: PLC0415

    described = provider.describe()
    form = form_of(described)
    cause = f"unsupported(column_property_method:{described.provider_id})"
    if form is None:
        return CascadeFailure(
            "CAPABILITY_UNAVAILABLE",
            cause,
            f"{unit}: provider {described.provider_id!r} (reference convention "
            f"{described.reference_convention!r}) is outside the supported scope; a column "
            f"supports {_SCOPE} (S03 §9, ADR 0049 D1)",
        )
    if not form.composition_dependent:
        return None
    components = described.components
    lnphi = tuple(f"lnphi_{c}" for c in components)
    inputs = ("T", "P", *(f"n_{c}" for c in components))
    missing = [
        *(phase for phase in ("LIQUID", "VAPOR") if phase not in described.phases),
        *(name for name in ("h", *lnphi) if name not in described.properties),
        *(["TP"] if "TP" not in described.flashes else []),
        *(
            f"derivative_order[{name}]"
            for name in inputs
            if described.derivative_order.get(name, 0) < 1
        ),
    ]
    if missing:
        return CascadeFailure(
            "CAPABILITY_UNAVAILABLE",
            cause,
            f"{unit}: {described.provider_id} declares wilson-ig-v1's identity but not its "
            f"capabilities: missing {missing}",
        )
    (t_min, t_max), (p_min, p_max) = form.domain["T"], form.domain["P"]
    probe = provider.evaluate_phase(
        PropertyRequest(
            state=StreamState(
                n=(1.0,) * len(components),
                temperature=(t_min + t_max) / 2.0,
                pressure=(p_min + p_max) / 2.0,
            ),
            phase="VAPOR",
            properties=lnphi,
            derivatives=inputs,
        ),
        context,
    )
    identical = probe.status == "ok" and all(
        probe.values.get(name) == 0.0
        and all(probe.derivatives.get(name, {}).get(wrt) == 0.0 for wrt in inputs)
        for name in lnphi
    )
    if not identical:
        return CascadeFailure(
            "CAPABILITY_UNAVAILABLE",
            cause,
            f"{unit}: {described.provider_id}: vapour ln phi is not identically zero"
            + ("" if probe.status == "ok" else f" (the probe returned {probe.status!r})"),
        )
    return None
