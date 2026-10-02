"""The property-call budget, enforced where the calls happen. K03 specification §11.2.

The budget is on **actual provider calls** — exact-cache misses — and not on requested
evaluations, because a budget that a cache could change would measure the cache rather than the
work. Requested evaluations and hits are recorded beside it (blueprint §6.4) and consume
nothing.

**The guard refuses the call that would exceed the cap**, rather than noticing afterwards that
it did. That is what makes `counters.property_calls == max_property_calls` exactly true on
exhaustion (assertion A15), and it is the difference between a budget and a report: a solver
that discovered it had overspent would already have spent it.

The guard is a `PropertyProvider` and sits *under* the exact cache, so a cached repeat costs
nothing and the count is the count of work actually done. It passes `describe()` through
unchanged, so wrapping is invisible to model identity — the flowsheet label, and therefore
`model_version`, name the wrapped provider exactly as if the guard were not there.
"""

from __future__ import annotations

from typing import Final

from openflowsheet.compiled import EvaluationContext
from openflowsheet.thermo import (
    FlashRequest,
    FlashResult,
    PropertyCapabilities,
    PropertyProvider,
    PropertyRequest,
    PropertyResult,
)

#: §11.2 and §13.6's registered cap for the SYN-001 capped-budget case.
REGISTERED_MAX_PROPERTY_CALLS: Final = 20_000


class BudgetExhaustedError(RuntimeError):
    """`BUDGET_EXHAUSTED` with `budget = property_calls`. Raised *instead of* the call.

    Not a `PropertyStatus` value: adding one would widen a K02 result type that the plan §2.1
    freeze covers, and a budget is a property of the solve rather than of the property package.
    """

    def __init__(self, cap: int, attempted: str) -> None:
        super().__init__(
            f"the property-call budget of {cap} is spent; the call to {attempted} was refused "
            "rather than made, so the recorded count is exactly the cap"
        )
        self.cap = cap
        self.budget = "property_calls"


class BudgetedProvider:
    """A `PropertyProvider` that refuses the call that would take it past the cap."""

    def __init__(self, provider: PropertyProvider, cap: int) -> None:
        if cap < 0:
            raise ValueError(f"a property-call budget must not be negative, got {cap}")
        self._provider = provider
        self.cap = cap
        self.calls = 0

    def describe(self) -> PropertyCapabilities:
        """Unchanged, and *uncounted*: describing a provider does no thermodynamic work."""
        return self._provider.describe()

    def _spend(self, what: str) -> None:
        if self.calls >= self.cap:
            raise BudgetExhaustedError(self.cap, what)
        self.calls += 1

    def evaluate_phase(
        self, request: PropertyRequest, context: EvaluationContext
    ) -> PropertyResult:
        self._spend(f"evaluate_phase({request.phase})")
        return self._provider.evaluate_phase(request, context)

    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult:
        self._spend("flash")
        return self._provider.flash(request, context)


class PropertyMeter:
    """A `PropertyProvider` that counts every call and refuses none (T02 E).

    A region's property blocks capture the provider when the declaration is built, so a solve
    that wants to count their calls cannot wrap the provider afterwards, as `solve_tear` wraps its
    own. The meter is installed where the flowsheet is built (`bind_revision` does), and a plan
    run reads it around each region solve: an exact count of provider calls, where summing the
    backend's block counters would not be (a dormant stream's value makes no provider call).
    Inside a region it also enforces the plan's remaining budget (`limit`, review S4).
    """

    def __init__(self, provider: PropertyProvider) -> None:
        self._provider = provider
        self.calls = 0
        #: Review S4: while a region solve runs, the plan sets the count at which the next call is
        #: refused (the policy's cap less what the plan has spent) and the cap to report; `None`
        #: outside a region, where `solve_tear`'s own guard enforces K03 §11.2.
        self.limit: int | None = None
        self.cap = 0
        #: The refusal, once made. The compiled residual turns a block's exception into an
        #: `error` evaluation, so the plan reads this rather than trusting the exception to arrive.
        self.refused: BudgetExhaustedError | None = None

    def refusal(self) -> BudgetExhaustedError | None:
        """The refusal made since the limit was last set, if any."""
        return self.refused

    def _spend(self, what: str) -> None:
        if self.limit is not None and self.calls >= self.limit:
            self.refused = BudgetExhaustedError(self.cap, what)
            raise self.refused
        self.calls += 1

    def describe(self) -> PropertyCapabilities:
        """Unchanged and uncounted, as `BudgetedProvider.describe` — identity does not move."""
        return self._provider.describe()

    def evaluate_phase(
        self, request: PropertyRequest, context: EvaluationContext
    ) -> PropertyResult:
        self._spend(f"evaluate_phase({request.phase})")
        return self._provider.evaluate_phase(request, context)

    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult:
        self._spend("flash")
        return self._provider.flash(request, context)
