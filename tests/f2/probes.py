"""Test-only numeric probes for E-F2-4 (ADR 0062 work order 5; foundation rulings Q1.A5, Q6, O-9).

**Kinds.** The three probe attribute kinds of Q6 ("Probes"), registered for tests only (ADR 0062 D5:
"Built-ins: none in 0.5"): `probe.moments` (component-scoped, non-partition: the chain moments λ0
and λ2 of a `segment_mol` component as classes 1 and 2 of a two-class `order` grid; λ1 is the
segment amount, the parent, and is never an attribute), `probe.classes` (substream-scoped,
non-partition: particle counts per size class) and `probe.partition` (component-scoped partition:
the component's amount per size class, carried instead of its parent, Q6.R2). `PAYLOADS` are their
D5 payloads, `KINDS` the layout's facts of them.

**Units.** A `Flowsheet` of one `mat-v1` definition (`DEFINITION`, thermal coordinate `h_mass`)
with four probe units on `MaterialState`s: a feed, a mixer of at most 8 inlets, a splitter and a
heater in (n, ĥ, P). Every row is division-free and solved for the outlet:

- mixer: `v_out − Σ_k v_k = 0` per carried amount and attribute, summed in inlet order from `+0.0`;
  `ṁ_out ĥ_out − Σ_k ṁ_k ĥ_k = 0`; `P_out = min_k P_k`;
- splitter: `v_j − f_j v = 0` for each outlet but the last, `v − Σ_j v_j = 0` for the last;
  `ĥ_j − ĥ = 0`; `P_j − P = 0`;
- heater: `v_out − v = 0`; `ṁ ĥ_out − ṁ ĥ − Q = 0`; `P_out − P = 0`.

A row that loses rank in `ĥ` at a dormant outlet (the mixer's and the heater's energy row) is in
the zero-flow form `ĥ_out − ĥ_label = 0` (Q1.R4), `ĥ_label` the first inlet's `ĥ`, `+0.0` for a
feed (no inlet); a dormant heater needs `Q = +0.0`. `forms` records, per stream, whether its `ĥ`
row was the balance, the zero-flow form or a copy (the splitter's, which never loses rank).
Dormancy is decided on the carried amounts only (D4), signed zeros normalised first. No property
is ever called: `T` is not evaluated, and `derived` reports only the intensives the probes define
(composition, segments per chain, mean class, class fractions), each undefined iff its denominator
is exactly zero (Q6.R3). A flowing outlet whose ṁ underflows to `0.0` (amounts near 5e-324) has a
rank-deficient energy row that is not a zero-flow form: the probe raises `ProbeUnresolvedError`
rather than choose (ADR-F6's zero-flow forms decide it).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Final

from openflowsheet.material.layout import (
    AttributeKind,
    ComponentFacts,
    ConnectionInput,
    ConnectionLayout,
    MaterialFacts,
    MaterialState,
    SubstreamState,
    draft_connection,
)

#: Q6.R5's rounding allowance on the admissibility inequalities (S10).
TAU_MONO: Final = 1e-12
#: A probe mixer's inlet limit (E-F2-4, Q6.A1).
MAX_INLETS: Final = 8

#: The kinds' D5 payloads. Inequality terms: `n` the parent amount (λ1), `a[k]` class k of the
#: attribute (λ0, λ2); a product of terms is written `x*y` (F2 decision WO5-2).
PAYLOADS: Final[Mapping[str, Mapping[str, Any]]] = {
    "probe.moments": {
        "scope": "component",
        "partition": False,
        "classed": True,
        "quantity_kind": "number_flow",
        "parent_kind": None,
        "inequalities": [
            {"lhs": [[1.0, "a[1]"]], "rhs": [[1.0, "n"]], "allowance": "tau_mono"},
            {"lhs": [[1.0, "n*n"]], "rhs": [[1.0, "a[1]*a[2]"]], "allowance": "tau_mono"},
        ],
    },
    "probe.classes": {
        "scope": "substream",
        "partition": False,
        "classed": True,
        "quantity_kind": "number_flow",
        "parent_kind": None,
        "inequalities": [],
    },
    "probe.partition": {
        "scope": "component",
        "partition": True,
        "classed": True,
        "quantity_kind": "molar_flow",
        "parent_kind": None,
        "inequalities": [],
    },
}
KINDS: Final[Mapping[str, AttributeKind]] = {
    kind: AttributeKind(p["scope"], p["partition"], p["classed"], p["quantity_kind"])
    for kind, p in PAYLOADS.items()
}

#: The probe components: two molar ones, a polymer in segment moles, a crystallising solid.
#: Masses are synthetic test constants (kg per mol or per segment mol).
COMPONENTS: Final[Mapping[str, ComponentFacts]] = {
    "A": ComponentFacts("mol", 0.018015),
    "B": ComponentFacts("mol", 0.04401),
    "P": ComponentFacts("segment_mol", 0.1041),
    "C": ComponentFacts("mol", 0.05844),
}
FACTS: Final = MaterialFacts(tuple(COMPONENTS), COMPONENTS, KINDS)


def _attribute(kind: str, components: list[str] | None, grid: str) -> dict[str, Any]:
    return {"kind": kind, "version": "1.0.0", "components": components, "grid": grid}


def definition(size_edges: Sequence[float] = (0.0, 1e-4, 2e-4, 5e-4, 1e-3)) -> dict[str, Any]:
    """The probe definition: `liq` (mixed: A, B, P with λ0, λ2 of P) and `cryst` (solid: C as a
    size partition, particle counts per size class), on the size grid `L` with `size_edges`."""
    return {
        "template": "mat-v1",
        "thermal_coordinate": "h_mass",
        "substreams": [
            {
                "id": "liq",
                "kind": "mixed",
                "components": ["A", "B", "P"],
                "conserved_basis": {"preset": "true"},
                "grids": [
                    {"id": "order", "quantity_kind": "dimensionless", "edges": [0.0, 1.0, 2.0]}
                ],
                "attributes": [_attribute("probe.moments", ["P"], "order")],
            },
            {
                "id": "cryst",
                "kind": "solid",
                "components": ["C"],
                "conserved_basis": {"preset": "true"},
                "grids": [{"id": "L", "quantity_kind": "dimensionless", "edges": list(size_edges)}],
                "attributes": [
                    _attribute("probe.partition", ["C"], "L"),
                    _attribute("probe.classes", None, "L"),
                ],
            },
        ],
    }


DEFINITION: Final = definition()
#: A stand-in `definition_sha256` (the probes compare SHAs, never compute them).
SHA: Final = "f2" * 32

#: A slot key: (substream, field, index), as `Slot` holds them.
Key = tuple[str | None, str, tuple[str | int, ...]]


class ProbeUnresolvedError(ValueError):
    """A row the probes do not resolve (module docstring)."""


def _plus(value: float) -> float:
    """`value` with a negative zero made `+0.0` (D4: signed zeros normalised first)."""
    return value + 0.0


def layout_of(
    name: str, instance: Mapping[str, Any] = DEFINITION, sha: str = SHA
) -> ConnectionLayout:
    """`name`'s draft layout under `instance` (slot order and molar masses; no variable order)."""
    return draft_connection(ConnectionInput(name, "probe", instance, sha), FACTS)


@dataclass
class Flowsheet:
    """Probe streams by name, in creation order, with the form of each stream's `ĥ` row."""

    instance: Mapping[str, Any] = field(default_factory=lambda: DEFINITION)
    sha: str = SHA
    streams: dict[str, MaterialState] = field(default_factory=dict)
    forms: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.layout = layout_of("S", self.instance, self.sha)
        self.masses = tuple(s.molar_masses for s in self.layout.substreams)

    # -- states ----------------------------------------------------------------------------

    def keys(self) -> list[list[tuple[Key, ...]]]:
        """Per substream, the slot keys of its carried amounts and of its attributes."""
        slots = self.layout.slots
        return [
            [
                tuple((slots[p].substream, slots[p].field, slots[p].index) for p in s.carried),
                tuple((slots[p].substream, slots[p].field, slots[p].index) for p in s.attributes),
            ]
            for s in self.layout.substreams
        ]

    def mass_flow(self, state: MaterialState) -> float:
        """ṁ = Σ M n in carried order, one rounding per term, no fma (D4)."""
        total = 0.0
        for masses, sub in zip(self.masses, state.substreams, strict=True):
            for mass, amount in zip(masses, sub.carried, strict=True):
                total += mass * amount
        return total

    def enthalpy_flow(self, state: MaterialState) -> float:
        """Ḣ = ṁ ĥ; exactly `+0.0` for a dormant stream, whose `ĥ` is a label (D4)."""
        return 0.0 if state.is_dormant else self.mass_flow(state) * state.thermal

    def forget(self, *names: str) -> None:
        """Drop streams (a recycle's previous iterate)."""
        for name in names:
            del self.streams[name], self.forms[name]

    def _add(self, name: str, state: MaterialState, form: str) -> MaterialState:
        if name in self.streams:
            raise ValueError(f"stream {name!r} exists")
        self.streams[name] = state
        self.forms[name] = form
        return state

    def _state(
        self, name: str, substreams: Sequence[SubstreamState], h: float, pressure: float
    ) -> MaterialState:
        return MaterialState(name, self.sha, "h_mass", tuple(substreams), h, pressure)

    # -- units -----------------------------------------------------------------------------

    def feed(
        self, name: str, values: Mapping[Key, float], h: float, pressure: float
    ) -> MaterialState:
        """A source: the given slot values, every other slot `+0.0`. A dormant feed's `ĥ` is the
        label `+0.0` (no inlet, Q1.R4) whatever `h` says; a non-zero attribute on a dormant
        parent is an invalid state (D4) and raises."""
        known = {key for sub in self.keys() for part in sub for key in part}
        if set(values) - known:
            raise ValueError(f"{name}: unknown slots {sorted(map(str, set(values) - known))}")
        substreams = [
            SubstreamState(
                str(self.layout.substreams[i].substream),
                tuple(_plus(values.get(key, 0.0)) for key in carried),
                tuple(_plus(values.get(key, 0.0)) for key in attributes),
            )
            for i, (carried, attributes) in enumerate(self.keys())
        ]
        state = self._state(name, substreams, h, pressure)
        if state.is_dormant:
            if any(v != 0.0 for sub in substreams for v in sub.attributes):
                raise ValueError(f"{name}: attribute_on_zero_parent")
            return self._add(name, self._state(name, substreams, 0.0, pressure), "zero_flow")
        return self._add(name, state, "specified")

    def mix(self, name: str, inlets: Sequence[str]) -> MaterialState:
        if not 1 <= len(inlets) <= MAX_INLETS:
            raise ValueError(f"{name}: a probe mixer takes 1 to {MAX_INLETS} inlets")
        states = [self.streams[i] for i in inlets]
        if any(s.definition_sha256 != self.sha for s in states):
            raise ValueError(f"{name}: an inlet of another definition (grid or structure)")

        def total(values: Sequence[float]) -> float:
            found = 0.0
            for value in values:
                found += value
            return found

        substreams = [
            SubstreamState(
                subs[0].substream,
                tuple(total(v) for v in zip(*(s.carried for s in subs), strict=True)),
                tuple(total(v) for v in zip(*(s.attributes for s in subs), strict=True)),
            )
            for subs in zip(*(s.substreams for s in states), strict=True)
        ]
        pressure = min(s.pressure for s in states)
        outlet = self._state(name, substreams, 0.0, pressure)
        if outlet.is_dormant:
            return self._add(
                name, self._state(name, substreams, states[0].thermal, pressure), "zero_flow"
            )
        flow = self.mass_flow(outlet)
        if flow == 0.0:
            raise ProbeUnresolvedError(f"{name}: flowing, but ṁ underflows to 0.0")
        enthalpy = total([self.mass_flow(s) * s.thermal for s in states])
        return self._add(name, self._state(name, substreams, enthalpy / flow, pressure), "balance")

    def split(
        self, inlet: str, outlets: Sequence[str], fractions: Sequence[float]
    ) -> list[MaterialState]:
        """`outlets[j]` takes `fractions[j]` of every carried amount and attribute for all but the
        last outlet, which takes the balance; `len(fractions) == len(outlets) - 1`."""
        if len(fractions) != len(outlets) - 1 or any(not 0.0 <= f <= 1.0 for f in fractions):
            raise ValueError(
                "a probe splitter takes one fraction in [0, 1] per outlet but the last"
            )
        state = self.streams[inlet]

        def parts(value: float) -> list[float]:
            taken = [f * value for f in fractions]
            used = 0.0
            for part in taken:
                used += part
            return [*taken, _plus(value - used)]

        per_outlet: list[list[SubstreamState]] = [[] for _ in outlets]
        for sub in state.substreams:
            carried = list(zip(*(parts(v) for v in sub.carried), strict=True)) or [()] * len(
                outlets
            )
            attributes = list(zip(*(parts(v) for v in sub.attributes), strict=True)) or [()] * len(
                outlets
            )
            for j in range(len(outlets)):
                per_outlet[j].append(
                    SubstreamState(sub.substream, tuple(carried[j]), tuple(attributes[j]))
                )
        return [
            self._add(name, self._state(name, subs, state.thermal, state.pressure), "copy")
            for name, subs in zip(outlets, per_outlet, strict=True)
        ]

    def heat(self, name: str, inlet: str, duty: float) -> MaterialState:
        state = self.streams[inlet]
        if state.is_dormant:
            if duty != 0.0:
                raise ValueError(
                    f"{name}: a duty on a dormant stream (the zero-flow form needs Q = 0)"
                )
            return self._add(
                name,
                self._state(name, state.substreams, state.thermal, state.pressure),
                "zero_flow",
            )
        flow = self.mass_flow(state)
        if flow == 0.0:
            raise ProbeUnresolvedError(f"{name}: flowing, but ṁ underflows to 0.0")
        h = (flow * state.thermal + duty) / flow
        return self._add(name, self._state(name, state.substreams, h, state.pressure), "balance")

    # -- derived intensives and moments ----------------------------------------------------

    def value(self, state: MaterialState, key: Key) -> float:
        for (carried, attributes), sub in zip(self.keys(), state.substreams, strict=True):
            for keys, values in ((carried, sub.carried), (attributes, sub.attributes)):
                if key in keys:
                    return values[keys.index(key)]
        raise KeyError(key)

    def classes(
        self, state: MaterialState, substream: str, field_: str, head: tuple[str, ...]
    ) -> list[float]:
        """The class values of one classed slot family, in class order."""
        found = []
        for carried, attributes in self.keys():
            for key in (*carried, *attributes):
                if (
                    key[0] == substream
                    and key[1] == field_
                    and key[2][: len(head)] == head
                    and len(key[2]) == len(head) + 1
                ):
                    found.append(self.value(state, key))
        return found

    def parent(self, state: MaterialState) -> float:
        """C's parent amount: the fixed-order sum of its partition classes (Q6.R2)."""
        total = 0.0
        for amount in self.classes(state, "cryst", "n", ("C",)):
            total += amount
        return total

    def moments(self, state: MaterialState) -> tuple[float, float, float]:
        """(λ0, λ1, λ2) of P: λ1 is P's segment amount, λ0 and λ2 its `probe.moments` classes."""
        lambda0, lambda2 = self.classes(state, "liq", "a", ("probe.moments", "P"))
        return lambda0, self.value(state, ("liq", "n", ("P",))), lambda2

    def derived(self, state: MaterialState) -> dict[str, tuple[float | None, str | None]]:
        """The probes' derived intensives: each `(value, None)`, or `(None, "zero_flow")` iff its
        denominator is exactly zero (Q6.R3). `T` is listed only for a dormant stream (null,
        `zero_flow`, Q1.R4): a flowing one's needs a property call, which probes never make."""
        found: dict[str, tuple[float | None, str | None]] = {}

        def ratio(name: str, numerator: float, denominator: float) -> None:
            found[name] = (
                (None, "zero_flow") if denominator == 0.0 else (numerator / denominator, None)
            )

        if state.is_dormant:
            found["T"] = (None, "zero_flow")
        liquid = [self.value(state, ("liq", "n", (c,))) for c in ("A", "B", "P")]
        liquid_total = 0.0
        for amount in liquid:
            liquid_total += amount
        for component, amount in zip(("A", "B", "P"), liquid, strict=True):
            ratio(f"x[{component}]", amount, liquid_total)
        lambda0, lambda1, _ = self.moments(state)
        ratio("segments_per_chain[P]", lambda1, lambda0)
        counts = self.classes(state, "cryst", "a", ("probe.classes",))
        weighted, number = 0.0, 0.0
        for k, count in enumerate(counts, start=1):
            weighted += k * count
            number += count
        ratio("mean_class[cryst]", weighted, number)
        parent = self.parent(state)
        for k, amount in enumerate(self.classes(state, "cryst", "n", ("C",)), start=1):
            ratio(f"class_fraction[C][{k}]", amount, parent)
        return found


# ------------------------------------------------------------------------------- measurements


def conservation(inlets: Sequence[MaterialState], outlets: Sequence[MaterialState]) -> float:
    """The worst relative residual `|Σ out − Σ in| / Σ |in|` over every carried amount and
    attribute, in exact arithmetic (`math.fsum`). A slot whose inlets are all zero must have all
    outlets exactly `+0.0` (residual 0), else the residual is infinite."""
    worst = 0.0

    def slots(states: Sequence[MaterialState]) -> list[list[float]]:
        return [
            [v for sub in s.substreams for v in (*sub.carried, *sub.attributes)] for s in states
        ]

    ins, outs = slots(inlets), slots(outlets)
    for i in range(len(ins[0])):
        given = [s[i] for s in ins]
        made = [s[i] for s in outs]
        scale = math.fsum(abs(v) for v in given)
        if scale == 0.0:
            if any(math.copysign(1.0, v) < 0.0 or v != 0.0 for v in made):
                return math.inf
            continue
        worst = max(worst, abs(math.fsum([*made, *(-v for v in given)])) / scale)
    return worst


def admissible(lambda0: float, lambda1: float, lambda2: float) -> bool:
    """Q6.R5's inequalities, division-free, with the allowance τ_mono."""
    return (
        lambda0 <= lambda1 * (1.0 + TAU_MONO)
        and lambda1 * lambda1 * (1.0 - TAU_MONO) <= lambda0 * lambda2
    )


def deficit(lambda0: float, lambda1: float, lambda2: float) -> float | None:
    """The worst relative moment deficit of the stored floats, in exact arithmetic:
    max((λ1² − λ0 λ2) / λ1², (λ0 − λ1) / λ1); positive iff a strict inequality fails; `None`
    when λ1 is zero."""
    if lambda1 == 0.0:
        return None
    l0, l1, l2 = Fraction(lambda0), Fraction(lambda1), Fraction(lambda2)
    return float(max((l1 * l1 - l0 * l2) / (l1 * l1), (l0 - l1) / l1))
