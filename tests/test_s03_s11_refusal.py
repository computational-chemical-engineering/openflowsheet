"""S03 WO-S03-1: refusal S11, the column's supported property method (`docs/derivations/S03-spec.md`
§9; assertions A04 and A05 of §11).

S11 reads `provider.describe()` before R1 and before any provider evaluation, in S02's column
`validate` and in S01's cascade `validate` (a separate entry point), and refuses any provider whose
identity is not SYN-001's (`provider_id`, `reference_convention`) with `CAPABILITY_UNAVAILABLE`
`unsupported(column_property_method:<provider_id>)`. `solve_column` and `solve_cascade` return the
failure unchanged. The check is identity, not capability (§9 reason 3), so the spies below declare
exactly what SYN-001 declares except one identity field, and count every evaluation they are asked
for: a refusal decided before any evaluation leaves both counts at zero.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest
from test_s01_cascade_wo1 import CONTEXT as S01_CONTEXT
from test_s01_cascade_wo1 import REFERENCE as S01_REFERENCE
from test_s01_cascade_wo1 import _spec as s01_spec
from test_s02_column_wo1 import CONTEXT, SPECS

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.syn001 import PROVIDER_ID, REFERENCE_CONVENTION
from openflowsheet.models.syn001.cascade import (
    CascadeFailure,
    property_method_refusal,
)
from openflowsheet.models.syn001.cascade import validate as cascade_validate
from openflowsheet.models.syn001.cascade_solve import solve_cascade
from openflowsheet.models.syn001.column import validate
from openflowsheet.models.syn001.column_solve import ColumnSolution, solve_column
from openflowsheet.thermo import (
    FlashRequest,
    PropertyCapabilities,
    PropertyProvider,
    PropertyRequest,
)
from openflowsheet.thermo import _coolprop_heos_fluids as coolprop_table
from openflowsheet.thermo import coolprop_heos as cph
from openflowsheet.thermo import iapws95 as w
from openflowsheet.thermo.cache import ExactPropertyCache
from openflowsheet.thermo.pr_c1 import PrC1Provider
from openflowsheet.thermo.pr_lib import PrLibProvider
from openflowsheet.thermo.syn001 import Syn001Provider

M1 = SPECS["M1"]
SYN001 = Syn001Provider()
#: S01's C1 (`s01_reference.json`): the cascade entry point S11 also guards (§9 "Where it applies").
C1 = s01_spec(S01_REFERENCE["cases"]["C1"])


class _CountingProvider:
    """Delegates every call to `inner` and counts the evaluations (`evaluate_phase`, `flash`).
    `describe()` is metadata, not an evaluation, and is answered by `capabilities`."""

    def __init__(self, inner: PropertyProvider, capabilities: PropertyCapabilities) -> None:
        self._inner = inner
        self._capabilities = capabilities
        self.evaluations = 0
        self.flashes = 0

    def describe(self) -> PropertyCapabilities:
        return self._capabilities

    def evaluate_phase(self, request: PropertyRequest, context: EvaluationContext) -> Any:
        self.evaluations += 1
        return self._inner.evaluate_phase(request, context)

    def flash(self, request: FlashRequest, context: EvaluationContext) -> Any:
        self.flashes += 1
        return self._inner.flash(request, context)


def _spy(**identity: str) -> _CountingProvider:
    """A04's spies: SYN-001's declaration (phases LIQUID and VAPOR, properties `h` and `lnK`)
    with one identity field changed; it would answer every request as SYN-001 does."""
    capabilities = replace(SYN001.describe(), **identity)
    assert capabilities.phases == ("LIQUID", "VAPOR")
    assert {"lnK", "h"} <= set(capabilities.properties)
    return _CountingProvider(SYN001, capabilities)


def _coolprop() -> PropertyProvider:
    """S07's provider as its tests build it (`CoolPropHeosProvider(cid)` over tier A); its
    `describe()` is computed from constants, so it builds without CoolProp installed."""
    tier_a = [row["id"] for row in coolprop_table.FLUIDS if row["tier"] == "A"]
    return cph.CoolPropHeosProvider(tier_a[0])


#: A04: every non-SYN-001 provider in `thermo/` that implements `describe()`, built as its own tests
#: build it (`test_m02_*`/`test_a09_*`, `test_l01_provider`, `test_s05_envelope`,
#: `test_s07_coolprop`), and the two spies. None needs external data to be built.
PROVIDERS: dict[str, Any] = {
    "pr_c1": PrC1Provider,
    "pr_lib": PrLibProvider,
    "iapws95": w.Iapws95Provider,
    "coolprop_heos": _coolprop,
    "spy_provider_id": lambda: _spy(provider_id="s03-spy"),
    "spy_reference_convention": lambda: _spy(reference_convention="spy-ref"),
}


def _counted(name: str) -> _CountingProvider:
    built = PROVIDERS[name]()
    if isinstance(built, _CountingProvider):
        return built
    # A real provider is wrapped so its evaluations are counted too; the wrapper delegates
    # `describe()`, so S11 sees the provider's own identity.
    return _CountingProvider(built, built.describe())


@pytest.mark.parametrize("name", sorted(PROVIDERS))
def test_a04_s11_refuses_every_other_provider_before_any_evaluation(name: str) -> None:
    """A04: M1 with each non-SYN-001 provider: `validate` and `solve_column` return
    `CAPABILITY_UNAVAILABLE` `unsupported(column_property_method:<provider_id>)`, and the provider
    is asked for no evaluation and no flash."""
    provider = _counted(name)
    provider_id = provider.describe().provider_id
    assert (provider_id, provider.describe().reference_convention) != (
        PROVIDER_ID,
        REFERENCE_CONVENTION,
    )
    expected = f"unsupported(column_property_method:{provider_id})"
    refused = validate(M1, provider, CONTEXT)
    assert isinstance(refused, CascadeFailure)
    assert (refused.outcome, refused.cause) == ("CAPABILITY_UNAVAILABLE", expected)
    assert "SYN-001 only" in refused.message and repr(provider_id) in refused.message
    solved = solve_column(M1, provider)
    assert solved == refused
    assert (provider.evaluations, provider.flashes) == (0, 0)


@pytest.mark.parametrize("name", sorted(PROVIDERS))
def test_a04_s11_guards_s01s_cascade_entry_point(name: str) -> None:
    """§9 "Where it applies": S01's cascade validation is a separate entry point, and S11 guards
    it the same way; `solve_cascade` returns the failure unchanged."""
    provider = _counted(name)
    expected = f"unsupported(column_property_method:{provider.describe().provider_id})"
    refused = cascade_validate(C1, provider, S01_CONTEXT)
    assert isinstance(refused, CascadeFailure)
    assert (refused.outcome, refused.cause) == ("CAPABILITY_UNAVAILABLE", expected)
    assert solve_cascade(C1, provider) == refused
    assert (provider.evaluations, provider.flashes) == (0, 0)


def test_a04_s11_precedes_r1() -> None:
    """S11 is decided before R1: a specification R1 refuses (N = 0) is refused by S11 first when
    the provider is not SYN-001, and by R1 when it is."""
    malformed = replace(M1, stage_count=0)
    refused = validate(malformed, _spy(provider_id="s03-spy"), CONTEXT)
    assert refused is not None and refused.cause == "unsupported(column_property_method:s03-spy)"
    by_r1 = validate(malformed, SYN001, CONTEXT)
    assert by_r1 is not None and by_r1.cause == "invalid_spec(stage_count)"


@pytest.mark.parametrize("wrapped", [False, True], ids=["bare", "property_cache"])
def test_a05_syn001_passes_s11(wrapped: bool) -> None:
    """A05 (not vacuous): SYN-001, bare and wrapped in the property cache (which delegates
    `describe()`), passes S11; M1's `validate` returns `None`, and M1 solves to S02's root as
    it does with the bare provider (S02 A06's suite runs unchanged, A15)."""
    provider: PropertyProvider = ExactPropertyCache(Syn001Provider()) if wrapped else SYN001
    assert property_method_refusal(M1.unit_id, provider) is None
    assert validate(M1, provider, CONTEXT) is None
    assert cascade_validate(C1, provider, S01_CONTEXT) is None
    solved = solve_column(M1, provider)
    bare = solve_column(M1, SYN001)
    assert isinstance(solved, ColumnSolution) and isinstance(bare, ColumnSolution)
    assert solved.outcome == bare.outcome == "CONVERGED"
    assert solved.final_sha256 == bare.final_sha256
