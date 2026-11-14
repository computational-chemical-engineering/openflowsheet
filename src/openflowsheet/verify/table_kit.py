"""The check table's kit: what an entry reads and returns (T05 design note §4, register R-046).

`Unit` is one instance as an entry reads it, `ModelChecks` one model's rows by category (each a
`Rule`), `blocked_check` and `stream_notes` the rows on a stream whose enthalpy the state does
not determine, and the four notes the suffixes a qualification carries. The family tables
(`verify.unit_checks`, `verify.thermal`, `verify.gamma_phi_units`) build on it; `verify.table`
re-exports its public names."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import flow_id
from openflowsheet.models.revision_flowsheet import InstanceView
from openflowsheet.thermo import PropertyProvider
from openflowsheet.verify import (
    NEAR_THRESHOLD_MARGIN,
    CheckCategory,
    CheckResult,
    dormant,
    evaluated,
    unsupported,
)
from openflowsheet.verify.checks import COMPONENTS, KIND_REFERENCE, VerifierError, stream_of

#: §4.3: appended to `qualification(provider)` on a reacting unit's energy balance and on the
#: envelope's when a reactor is present. `{convention}` is the provider's reference convention.
REACTION_DATUM_NOTE: Final = (
    "; reacting unit: this balance is meaningful only under ADR 0011 D2, the provider's "
    "reference convention {convention} declared a formation datum, so the heat of reaction is "
    "carried by Hdot and never added separately"
)


#: T05b spec §9.1 (ADR 0012 D7): appended to the qualification of every energy and declared-port
#: check that reads the enthalpy of a stream of a temperature-degenerate split.
SPLIT_ENTHALPY_NOTE: Final = (
    "; enthalpy of {stream} from the state's split: temperature-degenerate (ADR 0012 D7)"
)


#: §9.2: the same, for a degenerate stream outside any split, evaluated in its declared phase.
DECLARED_ENTHALPY_NOTE: Final = (
    "; enthalpy of {stream} in its declared phase {phase}: temperature-degenerate (ADR 0012 D7)"
)


#: ADR 0013 D3 (K04-F9 spec §5.3): the same, for a stream of an unresolved two-phase split.
UNRESOLVED_ENTHALPY_NOTE: Final = (
    "; enthalpy of {stream} from the state's split: fresh flash unresolved (ADR 0013 D3)"
)


@dataclass(frozen=True)
class Unit:
    """One instance as a table entry reads it: its revision view, the state being judged, each
    stream's fresh-flash enthalpy flow, the tolerances, and the qualification its energy rows
    carry. Ids are `<category>.<unit>.<item>` (spec §12.1)."""

    view: InstanceView
    state: Mapping[str, float]
    #: `Ḣ(S)` by stream, computed once per stream in allocation order.
    enthalpy: Mapping[str, float]
    tolerances: Mapping[str, float]
    #: `qualification(provider)`, plus `REACTION_DATUM_NOTE` on a reacting unit.
    energy_note: str
    #: The fresh provider and the declaration's context, for a rule that evaluates a phase
    #: property of its own (the pump's work relation); `None` where no rule needs one.
    provider: PropertyProvider | None = None
    context: EvaluationContext | None = None
    #: T05b spec §9.1–§9.2: the qualification suffix of each stream whose enthalpy the state's
    #: split or its declared phase supplies (a temperature-degenerate stream).
    notes: Mapping[str, str] = field(default_factory=dict)
    #: §9.2: flowing, temperature-degenerate `vapor_liquid` streams outside any split, whose
    #: enthalpy the state does not determine; a check reading one is `unsupported`.
    unlifted: frozenset[str] = frozenset()
    #: The order a stream's flows are read in: the revision's view's (M02 design note §14.2 B15
    #: item 1); SYN-001's by default.
    components: tuple[str, ...] = COMPONENTS

    @property
    def id(self) -> str:
        return self.view.unit_id

    def streams(self, port: str) -> tuple[str, ...]:
        """A port's streams in connection order (R1)."""
        return tuple(self.view.ports.get(port, ()))

    def stream(self, port: str) -> str:
        """A single-stream port's stream."""
        connected = self.streams(port)
        if len(connected) != 1:
            raise VerifierError(f"port_not_single({self.id}.{port})")
        return connected[0]

    def inlets(self) -> tuple[str, ...]:
        return tuple(
            stream
            for port, direction in self.view.directions.items()
            if direction == "inlet"
            for stream in self.view.ports[port]
        )

    def n(self, stream: str, component: str) -> float:
        return self.state[flow_id(stream, component)]

    def pinned(self, *columns: str) -> str | None:
        """The one of `columns` the revision pins, or `None` (the builder allows exactly one)."""
        found = [column for column in columns if column in self.view.pins]
        if len(found) > 1:
            raise VerifierError(f"pin_conflict({self.id}, {', '.join(found)})")
        return found[0] if found else None

    def pin(self, column: str) -> float:
        """The revision's value for a pinned column (R5)."""
        if column not in self.view.pins:
            raise VerifierError(f"pin_missing({self.id}, {column})")
        return self.view.pins[column]

    def parameter(self, name: str) -> float:
        """The revision's value of an instance parameter (R6)."""
        if name not in self.view.parameters:
            raise VerifierError(f"parameter_missing({self.id}.{name})")
        return self.view.parameters[name]

    def check(
        self,
        category: CheckCategory,
        item: str,
        value: float,
        kind: str,
        *,
        reads: Sequence[str] | None = None,
    ) -> CheckResult:
        """A two-sided check, `|value| <= tolerances[kind]`; `item` empty names the unit's
        balance itself (`energy_balance.<U>`). Every energy row carries the qualification.

        An energy row names the streams whose enthalpy (from `Unit.enthalpy`) it `reads`: each
        temperature-degenerate one appends its note (T05b spec §9.1), and an unlifted degenerate
        one makes the check `unsupported` (§9.2). A rule that reads no enthalpy says `()`."""
        identifier = f"{category}.{self.id}.{item}" if item else f"{category}.{self.id}"
        note: str | None = None
        if category == "energy_balance":
            if reads is None:
                raise VerifierError(f"energy_reads_undeclared({identifier})")
            blocked = _unlifted_read(reads, self.unlifted)
            if blocked is not None:
                return blocked_check(identifier, category, self.id, blocked)
            note = self.energy_note + stream_notes(reads, self.notes)
        return evaluated(
            id=identifier,
            category=category,
            subject=self.id,
            value=value,
            tolerance=self.tolerances[kind],
            reference=KIND_REFERENCE[kind],
            independence_qualification=note,
        )

    def one_sided(
        self, item: str, value: float, kind: str, *, judged_at_dormancy: bool = False
    ) -> CheckResult:
        """A `bounds_and_domain` check: passes iff `value <= τ`, near threshold iff
        `τ/10 < value <= 10τ`; not applicable when any inlet of the unit is dormant, unless the
        check reads nothing a dormant stream's label decides (`judged_at_dormancy`)."""
        identifier = f"bounds_and_domain.{self.id}.{item}"
        if not judged_at_dormancy and any(
            stream_of(self.state, stream, self.components).is_dormant for stream in self.inlets()
        ):
            return dormant(id=identifier, category="bounds_and_domain", subject=self.id)
        tolerance = self.tolerances[kind]
        return CheckResult(
            id=identifier,
            category="bounds_and_domain",
            subject=self.id,
            result="pass" if value <= tolerance else "fail",
            value=value,
            tolerance=tolerance,
            reference=KIND_REFERENCE[kind],
            near_threshold=(
                tolerance / NEAR_THRESHOLD_MARGIN < value <= tolerance * NEAR_THRESHOLD_MARGIN
            ),
        )


def stream_notes(reads: Sequence[str], notes: Mapping[str, str]) -> str:
    """The degenerate-enthalpy notes of the streams a check reads, in reading order, once each."""
    return "".join(notes[stream] for stream in dict.fromkeys(reads) if stream in notes)


def _unlifted_read(reads: Sequence[str], unlifted: frozenset[str]) -> str | None:
    return next((stream for stream in reads if stream in unlifted), None)


def blocked_check(
    identifier: str, category: CheckCategory, subject: str, stream: str
) -> CheckResult:
    """T05b spec §9.2: a check reading an enthalpy the state does not determine."""
    return unsupported(
        id=identifier,
        category=category,
        subject=subject,
        reason=f"temperature_degenerate_unlifted({stream})",
    )


Rule = Callable[[Unit, Sequence[str]], list[CheckResult]]


def _nothing(unit: Unit, components: Sequence[str]) -> list[CheckResult]:
    return []


@dataclass(frozen=True)
class ModelChecks:
    """One model's rows of §4.3's table, by category, each in the table's row order.

    A rule takes the unit and the component order and returns its checks. `declared_ports` are
    the ports whose declared phase is checked (§4.3's admissibility category), each with whether
    it carries several streams (`phase_admissibility.<U>.<port>.<S>`) or one
    (`phase_admissibility.<U>.<port>`); a port declared `vapor_liquid` is skipped."""

    material: Rule = _nothing
    energy: Rule = _nothing
    specification: Rule = _nothing
    #: One-sided `bounds_and_domain` rows (`Unit.one_sided`), after the generic bounds.
    bounds: Rule = _nothing
    declared_ports: tuple[tuple[str, bool], ...] = ()
    #: The model's own `phase_admissibility` rows, judged where the splits' are, after the
    #: declared ports, on every form (S11 design §4.8: the column's stage items).
    admissibility: Rule = _nothing
