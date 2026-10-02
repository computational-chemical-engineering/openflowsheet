"""K02: the exact property cache and the warm-start cache, against blueprint §6.4.

§6.4 is nine sentences and each is a rule a cache can break silently. A cache that returns a result
from a key missing one of its inputs, or that satisfies a tighter request with a looser entry, or
that quantizes the state so two different states collide, produces a *plausible wrong number* and
nothing downstream can tell. So every rule below is tested as a **miss**, not as a hit: the
assertion that matters is "this must go to the provider", and the counter proves it did.

The provider underneath is wrapped in a call-counting spy, so a cache claiming a hit that it did
not have is caught by the spy rather than by the cache's own bookkeeping — a cache is not allowed
to be the only witness to its own behaviour.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from openflowsheet.compiled import EvaluationContext
from openflowsheet.thermo import (
    FlashRequest,
    FlashResult,
    PropertyCapabilities,
    PropertyProvider,
    PropertyRequest,
    PropertyResult,
    StreamState,
)
from openflowsheet.thermo.cache import (
    ExactPropertyCache,
    FlashGuess,
    WarmStartCache,
)
from openflowsheet.thermo.syn001 import P_REF, Syn001Provider

CONTEXT = EvaluationContext(model_version="k02-cache", constants_sha256="0" * 64)
STATE = StreamState(n=(1.0, 1.0, 1.0), temperature=360.0, pressure=P_REF)


class SpyProvider:
    """Counts what actually reached the provider. The cache does not get to be its own witness."""

    def __init__(self, inner: PropertyProvider | None = None) -> None:
        self.inner = inner or Syn001Provider()
        self.phase_calls = 0
        self.flash_calls = 0

    def describe(self) -> PropertyCapabilities:
        return self.inner.describe()

    def evaluate_phase(
        self, request: PropertyRequest, context: EvaluationContext
    ) -> PropertyResult:
        self.phase_calls += 1
        return self.inner.evaluate_phase(request, context)

    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult:
        self.flash_calls += 1
        return self.inner.flash(request, context)


@pytest.fixture
def spy() -> SpyProvider:
    return SpyProvider()


@pytest.fixture
def cache(spy: SpyProvider) -> ExactPropertyCache:
    return ExactPropertyCache(spy)


def phase_request(state: StreamState = STATE, **kwargs: object) -> PropertyRequest:
    base = {"state": state, "phase": "LIQUID", "properties": ("h",), "derivatives": ()}
    base.update(kwargs)
    return PropertyRequest(**base)  # type: ignore[arg-type]


# -- the cache is a provider, and is transparent -------------------------------------------------


def test_the_cache_is_itself_a_property_provider(cache: ExactPropertyCache) -> None:
    """So a caller cannot tell it from the provider beneath, and cannot bypass it by accident."""
    assert isinstance(cache, PropertyProvider)


def test_a_hit_returns_exactly_what_the_provider_returned(
    cache: ExactPropertyCache, spy: SpyProvider
) -> None:
    first = cache.evaluate_phase(phase_request(), CONTEXT)
    second = cache.evaluate_phase(phase_request(), CONTEXT)
    assert spy.phase_calls == 1
    assert second == first
    assert cache.counters.cache_hits == 1


def test_the_cache_does_not_change_the_declared_capabilities(
    cache: ExactPropertyCache, spy: SpyProvider
) -> None:
    assert cache.describe() == spy.describe()


# -- every key input must be part of the key (§6.4 sentence 1) -----------------------------------


@pytest.mark.parametrize(
    ("label", "mutate"),
    [
        ("phase", lambda r: replace(r, phase="VAPOR")),
        ("properties", lambda r: replace(r, properties=("lnK",))),
        ("property order", lambda r: replace(r, properties=("lnK", "h"))),
        ("derivative order", lambda r: replace(r, derivatives=("T",))),
        ("temperature", lambda r: replace(r, state=replace(r.state, temperature=361.0))),
        ("pressure", lambda r: replace(r, state=replace(r.state, pressure=110_000.0))),
        ("composition", lambda r: replace(r, state=replace(r.state, n=(1.0, 1.0, 2.0)))),
    ],
)
def test_changing_any_keyed_input_misses(
    cache: ExactPropertyCache, spy: SpyProvider, label: str, mutate: object
) -> None:
    """Each is one of §6.4's key inputs; a hit here would answer a different question."""
    cache.evaluate_phase(phase_request(), CONTEXT)
    cache.evaluate_phase(mutate(phase_request()), CONTEXT)  # type: ignore[operator]
    assert spy.phase_calls == 2, f"{label} was not part of the key"


def test_a_one_ulp_change_of_temperature_misses(
    cache: ExactPropertyCache, spy: SpyProvider
) -> None:
    """§6.4: quantizing state coordinates is forbidden in exact evaluation.

    A cache that rounded the state to make more hits would make the evaluated function piecewise
    constant while its derivative path still reported a nonzero slope — the two paths would then
    describe different functions, which is the failure §6.4 names.
    """
    cache.evaluate_phase(phase_request(), CONTEXT)
    nudged = replace(STATE, temperature=math.nextafter(360.0, math.inf))
    assert nudged.temperature != STATE.temperature
    cache.evaluate_phase(phase_request(nudged), CONTEXT)
    assert spy.phase_calls == 2


def test_a_negative_zero_component_hits_because_it_is_the_same_state(
    cache: ExactPropertyCache, spy: SpyProvider
) -> None:
    """The other side of the same rule: −0.0 and +0.0 *are* the same state (ADR 0001 D1.5).

    Without this the "no quantization" rule could be satisfied by a cache that never hits at all,
    which is why it is asserted alongside the one-ulp test rather than separately.
    """
    plus = StreamState(n=(0.0, 1.0, 1.0), temperature=360.0, pressure=P_REF)
    minus = StreamState(n=(-0.0, 1.0, 1.0), temperature=360.0, pressure=P_REF)
    cache.evaluate_phase(phase_request(plus), CONTEXT)
    cache.evaluate_phase(phase_request(minus), CONTEXT)
    assert spy.phase_calls == 1


def test_a_different_accuracy_policy_misses(cache: ExactPropertyCache, spy: SpyProvider) -> None:
    """§6.4 lists the accuracy policy among the key inputs, so changing it is an ordinary miss."""
    cache.evaluate_phase(phase_request(), CONTEXT)
    tighter = EvaluationContext(
        model_version=CONTEXT.model_version,
        constants_sha256=CONTEXT.constants_sha256,
        accuracy_policy="exact-quad",
    )
    cache.evaluate_phase(phase_request(), tighter)
    assert spy.phase_calls == 2


def test_an_entry_whose_achieved_accuracy_is_looser_than_the_request_misses() -> None:
    """§6.4's *second* accuracy rule, which the key alone does not enforce.

    The policy is in the key, so two requests under different policies never share an entry. But a
    provider may *achieve* something other than what was asked for — it says so in
    `achieved_accuracy` — and an entry recorded that way must not then satisfy a request at the
    policy it failed to reach. Without this the cache would serve a number the provider itself
    declined to stand behind. An unranked achieved accuracy is *incomparable*, not loose, so it
    misses: the cache cannot prove the entry is good enough, and guessing permissively is how a
    cache returns a number nobody computed.
    """

    class Understating(SpyProvider):
        def evaluate_phase(
            self, request: PropertyRequest, context: EvaluationContext
        ) -> PropertyResult:
            self.phase_calls += 1
            result = self.inner.evaluate_phase(request, context)
            return replace(result, achieved_accuracy="degraded-single")

    provider = Understating()
    cache = ExactPropertyCache(provider)
    cache.evaluate_phase(phase_request(), CONTEXT)
    cache.evaluate_phase(phase_request(), CONTEXT)

    assert provider.phase_calls == 2, "an entry achieved at a looser accuracy satisfied the request"
    assert cache.counters.accuracy_misses == 1


def test_an_entry_achieved_at_the_requested_accuracy_still_hits() -> None:
    """Anti-vacuity for the test above: the rule must not simply disable the cache."""
    spy = SpyProvider()
    cache = ExactPropertyCache(spy)
    cache.evaluate_phase(phase_request(), CONTEXT)
    cache.evaluate_phase(phase_request(), CONTEXT)
    assert spy.phase_calls == 1
    assert cache.counters.accuracy_misses == 0


def test_a_different_phase_policy_misses(cache: ExactPropertyCache, spy: SpyProvider) -> None:
    """§6.4 lists the phase/branch policy among the key inputs."""
    cache.flash(FlashRequest(state=STATE), CONTEXT)
    other = EvaluationContext(
        model_version=CONTEXT.model_version,
        constants_sha256=CONTEXT.constants_sha256,
        phase_signature="LIQUID",
    )
    cache.flash(FlashRequest(state=STATE), other)
    assert spy.flash_calls == 2


def test_a_different_provider_identity_cannot_share_a_cache() -> None:
    """Provider implementation and data hashes are in the key, so a swap cannot be answered stale.

    Constructed by mutating the declared `data_sha256`, which is what a constants change would do.
    """

    class Relabelled(SpyProvider):
        def describe(self) -> PropertyCapabilities:
            return replace(self.inner.describe(), data_sha256="f" * 64)

    first, second = SpyProvider(), Relabelled()
    cache_a, cache_b = ExactPropertyCache(first), ExactPropertyCache(second)
    key_a = cache_a._property_key(phase_request(), CONTEXT)  # noqa: SLF001
    key_b = cache_b._property_key(phase_request(), CONTEXT)  # noqa: SLF001
    assert key_a != key_b


# -- negative entries (§6.4 sentence 6) ----------------------------------------------------------


def test_an_out_of_domain_answer_is_cached(cache: ExactPropertyCache, spy: SpyProvider) -> None:
    """A property of the request against the declared contract; retrying cannot change it."""
    outside = StreamState(n=(1.0, 1.0, 1.0), temperature=270.0, pressure=P_REF)
    first = cache.flash(FlashRequest(state=outside), CONTEXT)
    second = cache.flash(FlashRequest(state=outside), CONTEXT)
    assert first.status == second.status == "out_of_domain"
    assert spy.flash_calls == 1


def test_a_not_converged_answer_is_never_cached(spy: SpyProvider) -> None:
    """§6.4: "negative cache entries cannot permanently hide a retry with a different authorized
    strategy". A convergence failure is a property of the *attempt*, so a later attempt with a
    different strategy must reach the provider rather than be answered from the failure.
    """

    class Failing:
        def describe(self) -> PropertyCapabilities:
            return Syn001Provider().describe()

        def evaluate_phase(
            self, request: PropertyRequest, context: EvaluationContext
        ) -> PropertyResult:
            raise NotImplementedError

        def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult:
            self.calls = getattr(self, "calls", 0) + 1
            return FlashResult(
                status="not_converged",
                phase_signature=None,
                vapor_fraction=None,
                vapor=None,
                liquid=None,
                message="ran out of iterations",
            )

    failing = Failing()
    cache = ExactPropertyCache(failing)
    for _ in range(3):
        assert cache.flash(FlashRequest(state=STATE), CONTEXT).status == "not_converged"
    assert failing.calls == 3, "a convergence failure was cached and hid the retries"


# -- counters are reported separately (§6.4 sentence 9) ------------------------------------------


def test_the_counters_distinguish_hits_from_provider_calls(
    cache: ExactPropertyCache, spy: SpyProvider
) -> None:
    """ "Whether properties dominate total cost is measured, not assumed" needs these apart."""
    cache.evaluate_phase(phase_request(), CONTEXT)
    cache.evaluate_phase(phase_request(), CONTEXT)
    cache.evaluate_phase(phase_request(properties=("lnK",)), CONTEXT)
    counters = cache.counters.as_mapping()

    assert counters["requested_evaluations"] == 3
    assert counters["provider_calls"] == 2 == spy.phase_calls
    assert counters["cache_hits"] == 1
    assert counters["cache_misses"] == 2
    assert counters["entries"] == 2
    assert counters["memory_bytes"] > 0


def test_derivative_calls_and_flash_iterations_are_counted_apart(
    cache: ExactPropertyCache,
) -> None:
    cache.evaluate_phase(phase_request(derivatives=("T", "P")), CONTEXT)
    cache.evaluate_phase(phase_request(), CONTEXT)
    cache.flash(FlashRequest(state=STATE), CONTEXT)
    counters = cache.counters.as_mapping()
    assert counters["derivative_calls"] == 1
    assert counters["flash_iterations"] >= 1


def test_eviction_is_deterministic(spy: SpyProvider) -> None:
    """A recency or random policy would make the provider-call count depend on history, and that
    count is evidence under §6.4."""
    cache = ExactPropertyCache(spy, capacity=2)
    for temperature in (360.0, 361.0, 362.0):
        cache.evaluate_phase(phase_request(replace(STATE, temperature=temperature)), CONTEXT)
    assert cache.counters.entries == 2
    # The oldest went first, so re-asking for it reaches the provider again.
    cache.evaluate_phase(phase_request(replace(STATE, temperature=360.0)), CONTEXT)
    assert spy.phase_calls == 4


# -- the warm-start cache is a different thing (§6.4 sentence 5) ---------------------------------


def test_a_warm_start_hit_is_a_guess_and_cannot_be_returned_as_a_result() -> None:
    """The rule carried by the type system rather than by a convention.

    `FlashGuess` has no status, no outlet streams and no way to be mistaken for a `FlashResult`, so
    "approximate lookup may only suggest initial guesses" cannot be violated by forgetting a check.
    """
    provider = Syn001Provider()
    warm = WarmStartCache(provider.describe())
    warm.record(STATE, provider.flash(FlashRequest(state=STATE), CONTEXT))

    guess = warm.lookup(replace(STATE, temperature=360.5))
    assert isinstance(guess, FlashGuess)
    assert not isinstance(guess, FlashResult)
    assert not hasattr(guess, "status")
    assert not hasattr(guess, "vapor")
    assert 0.0 < guess.distance < 0.05


def test_the_warm_start_cache_misses_outside_its_radius() -> None:
    provider = Syn001Provider()
    warm = WarmStartCache(provider.describe(), radius=0.001)
    warm.record(STATE, provider.flash(FlashRequest(state=STATE), CONTEXT))
    assert warm.lookup(replace(STATE, temperature=400.0)) is None
    assert warm.counters.cache_misses == 1


def test_the_warm_start_cache_returns_the_nearest_entry() -> None:
    provider = Syn001Provider()
    warm = WarmStartCache(provider.describe(), radius=0.5)
    for temperature in (355.0, 360.0, 365.0):
        state = replace(STATE, temperature=temperature)
        warm.record(state, provider.flash(FlashRequest(state=state), CONTEXT))
    guess = warm.lookup(replace(STATE, temperature=361.0))
    nearest = provider.flash(FlashRequest(state=replace(STATE, temperature=360.0)), CONTEXT)
    assert guess is not None
    assert guess.vapor_fraction == pytest.approx(nearest.vapor_fraction)


@pytest.mark.parametrize("temperature", [310.0, 420.0, 270.0])
def test_only_a_converged_two_phase_result_is_worth_starting_from(temperature: float) -> None:
    """A single-phase or failed outcome has no split to start from; storing one would hand back a
    guess derived from a state that never had one."""
    provider = Syn001Provider()
    warm = WarmStartCache(provider.describe())
    state = replace(STATE, temperature=temperature)
    warm.record(state, provider.flash(FlashRequest(state=state), CONTEXT))
    assert warm.counters.entries == 0
    assert warm.lookup(state) is None


def test_a_zero_radius_is_refused() -> None:
    """A warm-start cache with no radius is an exact cache wearing the wrong type."""
    with pytest.raises(ValueError, match="radius must be positive"):
        WarmStartCache(Syn001Provider().describe(), radius=0.0)


# -- the cache never changes an answer -----------------------------------------------------------


def test_cached_and_uncached_evaluation_agree_everywhere() -> None:
    """The property that makes a cache safe at all, over a grid rather than one point.

    Run the same requests through a cached and an uncached provider and require bit-identical
    results. A cache that returned a *nearly* right answer would pass every test above.
    """
    plain = Syn001Provider()
    cached = ExactPropertyCache(Syn001Provider())
    for temperature in (300.0, 330.0, 360.0, 390.0, 430.0):
        for pressure in (60_000.0, P_REF, 180_000.0):
            state = StreamState(n=(0.5, 1.0, 1.5), temperature=temperature, pressure=pressure)
            for _ in range(2):  # second pass is the cached one
                assert cached.flash(FlashRequest(state=state), CONTEXT) == plain.flash(
                    FlashRequest(state=state), CONTEXT
                )
                assert cached.evaluate_phase(
                    phase_request(state, properties=("h", "lnK"), derivatives=("T", "P")), CONTEXT
                ) == plain.evaluate_phase(
                    phase_request(state, properties=("h", "lnK"), derivatives=("T", "P")), CONTEXT
                )


# -- key composition, asserted directly ----------------------------------------------------------
#
# A mutation sweep found that removing the accuracy policy from the key survived every test above:
# the achieved-accuracy check happened to miss for the *same* pair of requests, so the test passed
# for the wrong reason. A behavioural assertion can be satisfied by a second mechanism; a direct
# one about the key cannot. These compare the keys themselves.


@pytest.mark.parametrize(
    ("label", "left", "right"),
    [
        (
            "accuracy policy",
            EvaluationContext(model_version="m", constants_sha256="0" * 64),
            EvaluationContext(
                model_version="m", constants_sha256="0" * 64, accuracy_policy="exact-quad"
            ),
        ),
        (
            "phase policy",
            EvaluationContext(model_version="m", constants_sha256="0" * 64),
            EvaluationContext(
                model_version="m", constants_sha256="0" * 64, phase_signature="TWO_PHASE"
            ),
        ),
    ],
)
def test_each_context_input_is_actually_in_the_key(
    cache: ExactPropertyCache, label: str, left: EvaluationContext, right: EvaluationContext
) -> None:
    """§6.4 lists these among the key inputs; being in the key is the claim, so test the key."""
    assert cache._property_key(phase_request(), left) != cache._property_key(  # noqa: SLF001
        phase_request(), right
    ), f"{label} is not part of the exact key"
    assert cache._flash_key(  # noqa: SLF001
        FlashRequest(state=STATE), left
    ) != cache._flash_key(FlashRequest(state=STATE), right)


def test_the_warm_start_cache_cannot_return_a_flash_result() -> None:
    """The type rule, asserted as a type rule rather than inferred from behaviour.

    `FlashGuess` is a different class with a disjoint field set; a lookup that returned a
    `FlashResult` would be usable as an answer, which is the one thing §6.4 forbids of approximate
    lookup. Checking the exact class — not `isinstance` — also rejects a subclass smuggled in.
    """
    provider = Syn001Provider()
    warm = WarmStartCache(provider.describe())
    warm.record(STATE, provider.flash(FlashRequest(state=STATE), CONTEXT))

    guess = warm.lookup(STATE)
    assert guess is not None
    assert type(guess) is FlashGuess
    result_only = {"status", "vapor", "liquid", "phase_signature", "message", "iterations"}
    assert not (set(vars(guess)) & result_only), (
        "a guess grew a field a caller could read as an answer"
    )
