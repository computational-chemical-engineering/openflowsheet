"""The exact property cache and the separate warm-start cache (blueprint §6.4).

Two caches, deliberately not one, and deliberately not interchangeable.

**The exact cache** returns a result only for a request whose every identifying input is *equal* to
one already answered. Its key covers what §6.4 lists: provider implementation and data hashes,
ordered components, reference convention, state-definition id, the exact canonical numerical
inputs, the phase or branch policy, the requested properties, the derivative order, and the
accuracy policy. It is a `PropertyProvider` itself, so a caller cannot tell it from the provider it
wraps and nothing downstream needs to know a cache exists.

**The warm-start cache** returns a *starting guess* for a nearby state and nothing else. Its lookup
is approximate — that is its whole purpose — and §6.4 permits it exactly because a guess is
followed by a fresh converged calculation.

**Why they are different types rather than one cache with a flag.** The rule that matters is
"approximate lookup may only suggest initial guesses"; a flag makes obeying it a matter of
remembering to check the flag. Here the warm-start cache returns a `FlashGuess`, which has no
status, no outlet streams and no vapour fraction a caller could mistake for an answer — the type
system carries the rule instead of a convention.

**Quantization is forbidden and is not merely avoided.** §6.4: "Quantizing state coordinates can
make that function piecewise constant while returning nonzero derivatives; it is forbidden in exact
evaluation." The exact key therefore hashes the state through `openflowsheet.canonical`, which is
one-ulp sensitive by construction (ADR 0008 D2.6), and `tests/test_k02_cache.py` asserts that a
one-ulp change misses. The *warm-start* cache does look up approximately, which is allowed
precisely because what it returns cannot be used as a result.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from openflowsheet.canonical import document_sha256, state_sha256
from openflowsheet.compiled import EvaluationContext
from openflowsheet.thermo import (
    FlashRequest,
    FlashResult,
    PropertyCapabilities,
    PropertyProvider,
    PropertyRequest,
    PropertyResult,
    PropertyStatus,
    StreamState,
)

#: Accuracy policies, loosest first. A cached entry satisfies a request only when its achieved
#: accuracy is at least as tight as the one asked for (§6.4: "cache entries record achieved
#: accuracy and cannot satisfy a tighter request without evidence"). A policy absent from this
#: ranking is *incomparable*, not loose: the cache cannot prove the entry is good enough, so it
#: misses. That is the conservative direction, and it is the one that cannot produce a wrong number.
ACCURACY_RANK: Final[Mapping[str, int]] = {"exact-double": 100}

#: Statuses that are a property of the *request against the declared contract*, and so will be the
#: same however many times they are retried with whatever strategy. These may be cached.
_DETERMINISTIC_FAILURES: Final[frozenset[str]] = frozenset({"out_of_domain", "unsupported"})


@dataclass
class CacheCounters:
    """What §6.4 requires be reported **separately**, rather than folded into one cost.

    "Whether properties dominate total cost is measured, not assumed" — which needs the provider
    calls and the cache hits to be distinguishable, and the derivative calls and flash iterations
    distinguishable from both.
    """

    requested_evaluations: int = 0
    provider_calls: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    accuracy_misses: int = 0
    derivative_calls: int = 0
    flash_iterations: int = 0
    entries: int = 0
    memory_bytes: int = 0

    def as_mapping(self) -> dict[str, int]:
        return {
            "requested_evaluations": self.requested_evaluations,
            "provider_calls": self.provider_calls,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "accuracy_misses": self.accuracy_misses,
            "derivative_calls": self.derivative_calls,
            "flash_iterations": self.flash_iterations,
            "entries": self.entries,
            "memory_bytes": self.memory_bytes,
        }


@dataclass(frozen=True)
class FlashGuess:
    """A *starting guess* from the warm-start cache. Deliberately not a `FlashResult`.

    It carries no status, no outlet streams and no vapour fraction that a caller could return as an
    answer — only the numbers a flash can be started from, and the distance from the state they
    were converged at, so a caller can judge how much of a guess it is. §6.4 permits approximate
    lookup for exactly this and nothing more: "nearby states may retrieve flash starting guesses,
    followed by a fresh converged property calculation."
    """

    #: Vapour fraction to start from.
    vapor_fraction: float
    #: K-values to start from, by component id.
    k_values: Mapping[str, float]
    #: Relative distance in (T, P) between the stored state and the requested one. Zero means the
    #: guess came from an exactly equal state — which still makes it a guess, not a result.
    distance: float
    source_state_sha256: str


def _state_document(state: StreamState, components: Sequence[str]) -> dict[str, object]:
    """The exact numerical inputs of a state, hashed at full precision and never quantized."""
    names = (*(f"n_{component}" for component in components), "T", "P")
    values = (*state.n, state.temperature, state.pressure)
    return {"order": list(names), "vector_sha256": state_sha256(list(values), names)}


class ExactPropertyCache:
    """A `PropertyProvider` that answers from an exact-input cache, or from the provider beneath.

    Wrapping rather than being called by the provider means the cache is invisible to every caller:
    a unit model asks a `PropertyProvider` and does not know or care whether one is present. It
    also means the cache cannot be bypassed by accident, because there is no second path.
    """

    def __init__(self, provider: PropertyProvider, *, capacity: int | None = None) -> None:
        self._provider = provider
        self._capabilities = provider.describe()
        self._entries: dict[str, tuple[object, str]] = {}
        self._capacity = capacity
        self.counters = CacheCounters()

    # -- the PropertyProvider surface ----------------------------------------------------------

    def describe(self) -> PropertyCapabilities:
        """The wrapped provider's capabilities, unchanged. A cache adds none and removes none."""
        return self._capabilities

    def evaluate_phase(
        self, request: PropertyRequest, context: EvaluationContext
    ) -> PropertyResult:
        key = self._property_key(request, context)
        cached = self._lookup(key, context)
        if cached is not None:
            assert isinstance(cached, PropertyResult)
            return cached

        self.counters.provider_calls += 1
        if request.derivatives:
            self.counters.derivative_calls += 1
        result = self._provider.evaluate_phase(request, context)
        self._store(key, result, result.status, result.achieved_accuracy)
        return result

    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult:
        key = self._flash_key(request, context)
        cached = self._lookup(key, context)
        if cached is not None:
            assert isinstance(cached, FlashResult)
            return cached

        self.counters.provider_calls += 1
        result = self._provider.flash(request, context)
        self.counters.flash_iterations += result.iterations
        self._store(key, result, result.status, result.achieved_accuracy)
        return result

    # -- keys ------------------------------------------------------------------------------------

    def _identity(self, context: EvaluationContext) -> dict[str, object]:
        """The part of the key that is the same for every request to this provider.

        Every member is one of blueprint §6.4's listed inputs. They are in the key rather than
        assumed constant because a cache that outlives a provider swap, a data change or a
        reference-convention change would answer for a function it never evaluated.
        """
        return {
            "provider_id": self._capabilities.provider_id,
            "implementation_sha256": self._capabilities.implementation_sha256,
            "data_sha256": self._capabilities.data_sha256,
            "components": list(self._capabilities.components),
            "reference_convention": self._capabilities.reference_convention,
            "state_definition": self._capabilities.state_definition,
            "accuracy_policy": context.accuracy_policy,
            "phase_signature": context.phase_signature,
        }

    def _property_key(self, request: PropertyRequest, context: EvaluationContext) -> str:
        return document_sha256(
            {
                **self._identity(context),
                "kind": "evaluate_phase",
                "state": _state_document(request.state, self._capabilities.components),
                "phase": request.phase,
                "properties": list(request.properties),
                "derivatives": list(request.derivatives),
            }
        )

    def _flash_key(self, request: FlashRequest, context: EvaluationContext) -> str:
        return document_sha256(
            {
                **self._identity(context),
                "kind": "flash",
                "state": _state_document(request.state, self._capabilities.components),
                "specification": request.specification,
                "derivatives": list(request.derivatives),
            }
        )

    # -- storage -----------------------------------------------------------------------------

    def _lookup(self, key: str, context: EvaluationContext) -> object | None:
        self.counters.requested_evaluations += 1
        entry = self._entries.get(key)
        if entry is None:
            self.counters.cache_misses += 1
            return None

        result, achieved = entry
        if not _satisfies(achieved, context.accuracy_policy):
            # §6.4: an entry cannot satisfy a *tighter* request than the one it was computed for.
            # Counted separately from an ordinary miss, because the two say different things about
            # whether the cache is sized right or the policies are mixed.
            self.counters.accuracy_misses += 1
            self.counters.cache_misses += 1
            return None

        self.counters.cache_hits += 1
        return result

    def _store(self, key: str, result: object, status: PropertyStatus, achieved: str) -> None:
        if status != "ok" and status not in _DETERMINISTIC_FAILURES:
            # §6.4: "Negative cache entries cannot permanently hide a retry with a different
            # authorized strategy." `not_converged` and `error` are properties of an *attempt*, so
            # a different strategy may succeed and they are never stored. `out_of_domain` and
            # `unsupported` are properties of the request against the declared contract and will
            # be the same however often they are retried, so they may be.
            return
        if self._capacity is not None and len(self._entries) >= self._capacity:
            # Deterministic eviction: oldest first. A randomized or recency policy would make the
            # provider-call count depend on history, and that count is evidence (§6.4).
            self._entries.pop(next(iter(self._entries)))
        self._entries[key] = (result, achieved)
        self.counters.entries = len(self._entries)
        self.counters.memory_bytes += sys.getsizeof(key) + sys.getsizeof(result)


def _satisfies(achieved: str, requested: str) -> bool:
    """Is an entry computed at `achieved` good enough for a request at `requested`?

    Only when both are ranked and the entry is at least as tight. An unranked policy on either side
    is *incomparable*, so the answer is no — the cache cannot prove the entry is good enough, and
    guessing in the permissive direction is how a cache returns a number nobody computed.
    """
    if achieved == requested:
        return True
    achieved_rank = ACCURACY_RANK.get(achieved)
    requested_rank = ACCURACY_RANK.get(requested)
    if achieved_rank is None or requested_rank is None:
        return False
    return achieved_rank >= requested_rank


class WarmStartCache:
    """Starting guesses for a flash at a *nearby* state. Never a result.

    Keyed on the identity inputs that make two states comparable at all — provider, data,
    components, reference convention — and looked up by relative distance in `(T, P)` within a
    declared radius. Composition is deliberately **not** part of the distance: two states with the
    same `(T, P)` and different compositions have the same K-values in this fixture's ideal package,
    and a guess is only a guess. A provider for which that is false would need its own policy, and
    `radius` exists so that policy has somewhere to live.
    """

    def __init__(self, capabilities: PropertyCapabilities, *, radius: float = 0.05) -> None:
        if not radius > 0.0:
            raise ValueError("radius must be positive; a zero radius is an exact cache, not a hint")
        self._capabilities = capabilities
        self._radius = radius
        self._entries: list[tuple[float, float, str, float, Mapping[str, float]]] = []
        self.counters = CacheCounters()

    def record(self, state: StreamState, result: FlashResult) -> None:
        """Remember a *converged* two-phase result as a future starting point.

        Only a converged two-phase result is worth starting from, so nothing else is stored: a
        single-phase or failed outcome carries no vapour fraction to start from, and storing one
        would mean handing back a guess derived from a state that never had a split.
        """
        if result.status != "ok" or result.vapor_fraction is None or not result.k_values:
            return
        if result.phase_signature != "TWO_PHASE":
            return
        self._entries.append(
            (
                state.temperature,
                state.pressure,
                state_sha256(
                    [*state.n, state.temperature, state.pressure],
                    [*(f"n_{c}" for c in self._capabilities.components), "T", "P"],
                ),
                result.vapor_fraction,
                dict(result.k_values),
            )
        )
        self.counters.entries = len(self._entries)

    def lookup(self, state: StreamState) -> FlashGuess | None:
        """The nearest stored state within the radius, as a guess. `None` when there is none."""
        self.counters.requested_evaluations += 1
        best: tuple[float, FlashGuess] | None = None
        for temperature, pressure, digest, beta, k_values in self._entries:
            distance = max(
                abs(state.temperature - temperature) / max(abs(temperature), 1.0),
                abs(state.pressure - pressure) / max(abs(pressure), 1.0),
            )
            if distance > self._radius:
                continue
            if best is None or distance < best[0]:
                best = (
                    distance,
                    FlashGuess(
                        vapor_fraction=beta,
                        k_values=k_values,
                        distance=distance,
                        source_state_sha256=digest,
                    ),
                )
        if best is None:
            self.counters.cache_misses += 1
            return None
        self.counters.cache_hits += 1
        return best[1]
