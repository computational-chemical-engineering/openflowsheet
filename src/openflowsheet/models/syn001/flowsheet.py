"""The SYN-001 flowsheet: the six units wired together, and a sequential traversal of them.

Seven streams and seven unit instances (the sink appears twice, on the vapour product and on the
purge). Plan §3.2: fresh feed to a mixer with the liquid recycle, heat to 350 K, flash
isothermally at the flash temperature, vapour to product, liquid split into a recycle fraction r
and a purge.

**Two things live here and they answer different questions.**

`syn001_spec` assembles every unit's rows into one `ProblemSpec` — the equation-oriented view,
which K03 will solve and which K01's compiler already accepts. It is assembled exactly as the
manifests declare, including a pressure row that is linearly dependent on the rest; reporting the
rank of that system is K03's structural analysis, and quietly dropping a row here to make a count
come out would hide it from the analysis that is supposed to find it.

`traverse` runs the units causally in flowsheet order from a guess for the recycle, which is the
sequential-modular view. It computes the tear residual `R(t) = G(t) - t` that blueprint §7.2
defines, and *does not solve it* — the damped Newton on that residual is K03's (plan §4.2). What
it does give K02 is the composition test the six units otherwise never get: at the oracle's
converged tear, `R(t*)` must be zero to the registered tolerance, and that is only true if every
unit is right and they are wired together correctly.

**The tear is three variables, not five.** Plan §3.2: "temperature and pressure of this particular
recycle are known from the flash specification". That reduction is a property of *this* flowsheet
and is not to be generalized — T01 must rediscover the tear dimension from the incidence graph,
and a test must confirm it rediscovers this three-variable tear rather than reading it from here.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final

from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.compiled import EvaluationContext, PhaseSignature
from openflowsheet.models import SpecificationError, UnitModel, Wiring, assemble
from openflowsheet.models.syn001 import COMPONENTS
from openflowsheet.models.syn001.feed import FeedSource
from openflowsheet.models.syn001.flash import TPFlash
from openflowsheet.models.syn001.heater import TPHeater
from openflowsheet.models.syn001.mixer import AdiabaticMixer
from openflowsheet.models.syn001.sink import ProductSink
from openflowsheet.models.syn001.splitter import StreamSplitter
from openflowsheet.thermo import PropertyProvider, PropertyStatus, StreamState

#: Stream ids, in the order the derivation names them (§4). Allocation order for the assembled
#: variable vector, so it is fixed here and nowhere else.
STREAMS: Final[tuple[str, ...]] = ("S1", "S2", "S3", "S4", "S5", "S6", "S7")

FEED_UNIT: Final = "U-FEED"
MIXER_UNIT: Final = "U-MIX"
HEATER_UNIT: Final = "U-HEAT"
FLASH_UNIT: Final = "U-FLASH"
SPLITTER_UNIT: Final = "U-SPLIT"
PRODUCT_SINK: Final = "U-PROD"
PURGE_SINK: Final = "U-PURGE"

WIRING: Final[Mapping[str, Wiring]] = {
    FEED_UNIT: Wiring({"outlet": ("S1",)}),
    MIXER_UNIT: Wiring({"inlet": ("S1", "S6"), "outlet": ("S2",)}),
    HEATER_UNIT: Wiring({"inlet": ("S2",), "outlet": ("S3",)}),
    FLASH_UNIT: Wiring({"inlet": ("S3",), "vapor": ("S4",), "liquid": ("S5",)}),
    SPLITTER_UNIT: Wiring({"inlet": ("S5",), "recycle": ("S6",), "purge": ("S7",)}),
    PRODUCT_SINK: Wiring({"inlet": ("S4",)}),
    PURGE_SINK: Wiring({"inlet": ("S7",)}),
}

#: Plan §3.1's fresh feed, and the nominal specifications of plan §3.2.
FRESH_FEED_FLOWS: Final[tuple[float, ...]] = (1.0, 1.0, 1.0)
FEED_TEMPERATURE: Final = 300.0
PRESSURE: Final = 100_000.0
HEATER_TEMPERATURE: Final = 350.0

#: The label half of ADR 0002 D2's `model_version` pattern, applied before `canonical` sees it.
MODEL_LABEL: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class InitializerFailedError(SpecificationError):
    """The once-through pass that defines the registered initializer failed (T06 spec §8.7,
    ADR 0014 D10, register R-078): a feed the provider cannot take, or one a unit refuses.

    A `SpecificationError`, so every existing handler still holds; the tear path catches exactly
    this subclass and returns `INITIALIZATION_FAILED` instead of letting it escape.
    """

    def __init__(self, status: str, message: str) -> None:
        super().__init__(
            f"the once-through pass that defines the registered initializer failed: "
            f"{status}: {message}"
        )
        self.status = status
        #: The first line of the traversal's message.
        self.first_line = (message.splitlines() or [""])[0]


@dataclass(frozen=True)
class Syn001Flowsheet:
    """One parameterization of SYN-001: a recycle fraction and a flash temperature."""

    provider: PropertyProvider
    context: EvaluationContext
    split_fraction: float = 0.5
    flash_temperature: float = 360.0
    heater_temperature: float = HEATER_TEMPERATURE
    pressure: float = PRESSURE
    feed_flows: tuple[float, ...] = FRESH_FEED_FLOWS
    feed_temperature: float = FEED_TEMPERATURE
    components: tuple[str, ...] = COMPONENTS

    @property
    def feed(self) -> FeedSource:
        return FeedSource(
            unit_id=FEED_UNIT,
            flows=self.feed_flows,
            temperature=self.feed_temperature,
            pressure=self.pressure,
            components=self.components,
        )

    @property
    def mixer(self) -> AdiabaticMixer:
        return AdiabaticMixer(
            unit_id=MIXER_UNIT,
            provider=self.provider,
            context=self.context,
            components=self.components,
        )

    @property
    def heater(self) -> TPHeater:
        return TPHeater(
            unit_id=HEATER_UNIT,
            provider=self.provider,
            outlet_temperature=self.heater_temperature,
            context=self.context,
            # S2 is the mixer outlet, which the mixer restricts to the subcooled-liquid domain.
            inlet_phase="LIQUID",
            components=self.components,
        )

    @property
    def flash(self) -> TPFlash:
        return TPFlash(
            unit_id=FLASH_UNIT,
            provider=self.provider,
            temperature=self.flash_temperature,
            pressure=self.pressure,
            context=self.context,
            # S3 is the heater outlet, whose split the heater lifts. The flash reads the same
            # lifted variables rather than declaring a second opinion about the same stream.
            inlet_phase=None,
            components=self.components,
        )

    @property
    def splitter(self) -> StreamSplitter:
        return StreamSplitter(
            unit_id=SPLITTER_UNIT,
            split_fraction=self.split_fraction,
            components=self.components,
        )

    def units(self) -> tuple[UnitModel, ...]:
        return (
            self.feed,
            self.mixer,
            self.heater,
            self.flash,
            self.splitter,
            ProductSink(unit_id=PRODUCT_SINK, components=self.components),
            ProductSink(unit_id=PURGE_SINK, components=self.components),
        )

    @property
    def label(self) -> str:
        """The function family's name, which must name the property package too.

        ADR 0002 D2.7 requires the label to change whenever the equation set changes, and the
        property provider *is* part of the equations: the same rows over a provider with
        different constants are a different function. Those constants cannot reach
        `constants_sha256`, which hashes the pinned inputs and those are floats, so they reach
        identity through the label and hence through `model_version`.

        This closes the K02 half of the gap ADR 0008 D4.1 left open — the thirteen SYN-001
        physical constants were hashed by nothing. Twelve hex digits of each of the provider's
        two declared hashes is 96 bits, which is not a cryptographic claim and is not meant as
        one; it distinguishes property packages in a name a human reads. The full hashes stay in
        `PropertyCapabilities`, where a reader can check them.

        **What must not be here: the pinned inputs.** ADR 0008 D4.1 says `model_version`
        "identifies equation structure and backend form only", and requires two instances
        compiled from the same structure with different specification values to *share* it. The
        first version of this label carried `r`, the flash temperature and the heater
        temperature, which made `model_version` differ across pinned inputs — a direct violation
        that also defeats re-binding without recompilation, and that overflowed the 64-character
        cap at an unremarkable parameterization (`r = 0.123`, `T_f = 360.25`). Found by the Fable
        review of K02. Those three are pinned inputs and belong to `constants_sha256`, which
        already carries them.

        ADR 0002 D2 caps a label at 64 characters of `[A-Za-z0-9._-]` — `model_version` splits on
        `@`, so a label may not contain one — and `canonical.model_version` refuses a label that
        does not fit. The check here fails with the length rather than letting that refusal
        surface from two layers down.
        """
        capabilities = self.provider.describe()
        label = (
            f"SYN001-fs1"
            f"-{capabilities.provider_id}"
            f"-{capabilities.implementation_sha256[:12]}"
            f"-{capabilities.data_sha256[:12]}"
        )
        if not MODEL_LABEL.match(label):
            raise SpecificationError(
                f"the flowsheet label {label!r} ({len(label)} characters) does not fit ADR 0002's "
                "model_version pattern: at most 64 characters of letters, digits, dot, dash and "
                "underscore"
            )
        return label

    def spec(self) -> ProblemSpec:
        """The whole flowsheet as one `ProblemSpec`, assembled exactly as declared."""
        return assemble(
            label=self.label,
            units=list(self.units()),
            wiring=WIRING,
            streams=STREAMS,
            components=self.components,
        )

    # -- sequential traversal ------------------------------------------------------------------

    def initial_recycle(self) -> StreamState:
        """Derivation §9's registered tear initializer `SYN-001-tear-init-v2`: `t0 = G(0)`.

        One sequential traversal from a **dormant** recycle, which every unit accepts (ADR 0001
        D3.4), so the guess is the recycle a once-through pass produces. Closed form `(1 - r) t*`
        — derivation §9 — which is why a Newton started here lands on `t*` in one step and
        exercises no globalization; the off-ray starts that do are registered in
        `docs/derivations/K03-solver-spec.md` §13.

        Its temperature and pressure are the flash specification, which is why the tear is three
        variables rather than five (plan §3.2).

        **This is not `r F_i`.** That guess was registered until 2026-09-21 and is retired
        (decision register R-014): it is an equimolar stream at the flash temperature, above its
        347.44 K bubble point, so the v0.0 mixer refuses it for every `r > 0`. It survives as the
        deliberately inadmissible guess of the registered case `SYN-001-inadmissible-guess`,
        whose purpose is to exercise blueprint §7.4's rule that every candidate is *checked*.
        A guess is not an answer either way: this one is admissible, not converged.
        """
        dormant = StreamState(
            n=tuple(0.0 for _ in self.feed_flows),
            temperature=self.flash_temperature,
            pressure=self.pressure,
        )
        traversal = self.traverse(dormant)
        if traversal.status != "ok" or traversal.computed_recycle is None:
            raise InitializerFailedError(traversal.status, traversal.message)
        return traversal.computed_recycle

    def retired_guess(self) -> StreamState:
        """`r F_i` at the flash specification — the guess retired by R-014.

        Kept as a named constructor because a registered case still uses it: it is the
        deliberately inadmissible candidate of `SYN-001-inadmissible-guess`. Naming it here
        stops a later reader reconstructing it from the retired text in derivation §9.
        """
        return StreamState(
            n=tuple(self.split_fraction * value for value in self.feed_flows),
            temperature=self.flash_temperature,
            pressure=self.pressure,
        )

    def traverse(self, recycle: StreamState) -> Traversal:
        """Run the units in flowsheet order from a guess for the recycle stream.

        Returns the streams, the duties and the tear residual `R(t) = G(t) - t`. Nothing is
        solved: a nonzero residual is reported, not iterated away.
        """
        # Plan §3.2 reduces this tear to three component flows precisely because "temperature
        # and pressure of this particular recycle are known from the flash specification". A
        # guess that disagrees with them is not a tear iterate at all, and accepting one would
        # let a caller silently solve a different problem.
        if recycle.temperature != self.flash_temperature or recycle.pressure != self.pressure:
            return Traversal(
                status="error",
                streams={},
                message=(
                    f"the recycle guess is at ({recycle.temperature} K, {recycle.pressure} Pa) "
                    f"but the flash specification fixes it at ({self.flash_temperature} K, "
                    f"{self.pressure} Pa). The tear is three component flows precisely because "
                    "those two are known (plan §3.2)"
                ),
            )

        streams: dict[str, StreamState] = {"S6": recycle}
        duties: dict[str, float] = {}
        signatures: dict[str, PhaseSignature | None] = {}

        def fail(unit: str, status: PropertyStatus, message: str) -> Traversal:
            return Traversal(
                status=status,
                streams=dict(streams),
                duties=dict(duties),
                phase_signatures=dict(signatures),
                message=f"{unit}: {message}",
            )

        feed_result = self.feed.evaluate({}, self.context)
        if feed_result.status != "ok":
            return fail(FEED_UNIT, feed_result.status, feed_result.message)
        streams["S1"] = feed_result.outlets["outlet"]
        signatures["S1"] = feed_result.phase_signature

        mixed = self.mixer.evaluate({"inlet": (streams["S1"], streams["S6"])}, self.context)
        if mixed.status != "ok":
            return fail(MIXER_UNIT, mixed.status, mixed.message)
        streams["S2"] = mixed.outlets["outlet"]
        signatures["S2"] = mixed.phase_signature

        heated = self.heater.evaluate({"inlet": (streams["S2"],)}, self.context)
        if heated.status != "ok":
            return fail(HEATER_UNIT, heated.status, heated.message)
        streams["S3"] = heated.outlets["outlet"]
        signatures["S3"] = heated.phase_signature
        assert heated.duty is not None
        duties[HEATER_UNIT] = heated.duty

        flashed = self.flash.evaluate({"inlet": (streams["S3"],)}, self.context)
        if flashed.status != "ok":
            return fail(FLASH_UNIT, flashed.status, flashed.message)
        streams["S4"] = flashed.outlets["vapor"]
        streams["S5"] = flashed.outlets["liquid"]
        signatures["S4"] = "ZERO_FLOW" if streams["S4"].is_dormant else "VAPOR"
        signatures["S5"] = "ZERO_FLOW" if streams["S5"].is_dormant else "LIQUID"
        assert flashed.duty is not None
        duties[FLASH_UNIT] = flashed.duty

        split = self.splitter.evaluate({"inlet": (streams["S5"],)}, self.context)
        if split.status != "ok":
            return fail(SPLITTER_UNIT, split.status, split.message)
        computed_recycle = split.outlets["recycle"]
        streams["S7"] = split.outlets["purge"]
        signatures["S6"] = "ZERO_FLOW" if computed_recycle.is_dormant else "LIQUID"
        signatures["S7"] = "ZERO_FLOW" if streams["S7"].is_dormant else "LIQUID"

        accepted_by: list[str] = []
        for unit_id, stream in ((PRODUCT_SINK, streams["S4"]), (PURGE_SINK, streams["S7"])):
            sink = ProductSink(unit_id=unit_id, components=self.components)
            accepted = sink.evaluate({"inlet": (stream,)}, self.context)
            if accepted.status != "ok":
                return fail(unit_id, accepted.status, accepted.message)
            accepted_by.append(unit_id)

        return Traversal(
            status="ok",
            streams=dict(streams),
            duties=dict(duties),
            phase_signatures=dict(signatures),
            accepted_by=tuple(accepted_by),
            computed_recycle=computed_recycle,
            recycle_residual=tuple(
                computed - guess
                for computed, guess in zip(computed_recycle.n, recycle.n, strict=True)
            ),
        )


@dataclass(frozen=True)
class Traversal:
    """One sequential pass through the flowsheet.

    `recycle_residual` is `G(t) - t` on the three component flows, the tear residual of blueprint
    §7.2. It is `None` on any status other than `ok`, because a partial traversal has no residual.
    """

    status: PropertyStatus
    streams: Mapping[str, StreamState]
    duties: Mapping[str, float] = field(default_factory=dict)
    phase_signatures: Mapping[str, PhaseSignature | None] = field(default_factory=dict)
    #: The boundary sinks that accepted their stream. A sink imposes no equation, so this is the
    #: only trace it leaves — and without it, skipping the sinks entirely would be invisible.
    accepted_by: tuple[str, ...] = ()
    computed_recycle: StreamState | None = None
    recycle_residual: tuple[float, ...] | None = None
    message: str = ""

    def __post_init__(self) -> None:
        if self.status != "ok" and self.recycle_residual is not None:
            raise ValueError("a traversal that did not complete has no tear residual")
