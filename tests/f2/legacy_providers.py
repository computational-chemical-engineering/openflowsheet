"""ADR 0050 D1's provider selection with each provider's native convention, built from the
production registry (`models.revision_flowsheet.component_basis`) and the providers' constants, as
`revision_v2.lower` takes it (F2 decision WO6a-1). Test-only; F2-WO6b builds the same in the
application."""

from __future__ import annotations

from openflowsheet.models.revision_flowsheet import (
    COOLPROP_RECORDS,
    IAPWS95_RECORDS,
    SYN001_BASIS,
    WILSON_RECORDS,
    component_basis,
)
from openflowsheet.revision_v2.lower import LegacyProvider, LegacyProviders, file_components
from openflowsheet.thermo import coolprop_heos, iapws95, pr_c1, syn001, wilson_ig

#: Each legacy provider's native convention (ADR 0001 D5, `interfaces-frozen.md` §3). Wilson v2
#: reports its inner provider's, which for the real records is `WILSON-IG-ref-v1`.
CONVENTIONS = {
    syn001.PROVIDER_ID: syn001.REFERENCE_CONVENTION,
    pr_c1.PROVIDER_ID: pr_c1.REFERENCE_CONVENTION,
    iapws95.PROVIDER_ID: iapws95.REFERENCE_CONVENTION,
    coolprop_heos.PROVIDER_ID: coolprop_heos.REFERENCE_CONVENTION,
    "wilson-ig-v2": next(
        name for name, synthetic in wilson_ig.CONVENTIONS.items() if not synthetic
    ),
}


def _provider(record_source: str) -> LegacyProvider:
    components = list(file_components(record_source))
    if record_source == COOLPROP_RECORDS:
        components = components[:1]
    basis = component_basis(
        {"component_set": {"record_source": record_source, "components": components}}
    )
    return LegacyProvider(basis.provider_id, CONVENTIONS[basis.provider_id])


def legacy_providers() -> LegacyProviders:
    """ADR 0050 D1's registry: the four registered sources and SYN-001's otherwise."""
    registered = (pr_c1.RECORDS_PATH, IAPWS95_RECORDS, WILSON_RECORDS, COOLPROP_RECORDS)
    return LegacyProviders(
        {source: _provider(source) for source in registered},
        LegacyProvider(SYN001_BASIS.provider_id, CONVENTIONS[SYN001_BASIS.provider_id]),
    )
