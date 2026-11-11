"""The admission function (ADR 0060 D5).

`admit(unit, method, definition)` is a pure, deterministic function of three registered
descriptors. It reads no platform, file, clock or environment, so the admission set is identical on
every platform (R0). The steps, in order, stop at the first refusal:

```
0. unit.payload.bindable is false               -> model_unsupported(<unit id>)
1. P_m = provides(method), P_d = provides(definition)
   "conn:<definition id>" not satisfied by P_m  -> capability_missing(U, M, conn:<definition id>)
2. for clause in normalised unit.requires:
       no token t of clause satisfied by S(t)   -> capability_missing(U, M, <render(clause)>)
       where S(t) = P_d if t is a conn: token, else P_m ∪ P_d
3. for clause in normalised method.requires:
       no token of clause satisfied by P_d      -> capability_missing(U, M, <render(clause)>)
4. admitted; notices = sorted(evidence notices of unit, method, definition)   (D9)
```

`capability_unresolved(<token>)` notices (D4) are attached whether the pair is admitted or
refused. Admission checks no platform, component coverage, parameter or revision content: factory
resolution and validation do. The frozen core is D5 for **single-side units** (D12); ADR-F6 may add
per-side `requires` additively.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from openflowsheet.registry.descriptor import Registered
from openflowsheet.registry.tokens import Coded, Token, parse, render, satisfied


@dataclass(frozen=True)
class Admission:
    """D5's verdict on one (unit, method, definition) triple."""

    admitted: bool
    refusal: Coded | None
    notices: tuple[Coded, ...]

    def as_document(self) -> dict[str, Any]:
        return {
            "admitted": self.admitted,
            "refusal": None if self.refusal is None else self.refusal.as_document(),
            "notices": [notice.as_document() for notice in self.notices],
        }


def _sorted_notices(notices: Iterable[Coded]) -> tuple[Coded, ...]:
    unique = {notice.sort_key(): notice for notice in notices}
    return tuple(unique[key] for key in sorted(unique))


def _expect(descriptor: Registered, kind: str) -> None:
    if descriptor.kind != kind:
        raise ValueError(f"{descriptor.id!r} is a {descriptor.kind}, not a {kind}")


def admit(unit: Registered, method: Registered, definition: Registered) -> Admission:
    """D5 over three registered descriptors (`unit_model`, `property_method`,
    `connection_definition`). A token is resolved unless one of the three lists it in its
    `unresolved` (D4: an unregistered name is never satisfied)."""
    _expect(unit, "unit_model")
    _expect(method, "property_method")
    _expect(definition, "connection_definition")
    unresolved_tokens = (*unit.unresolved, *method.unresolved, *definition.unresolved)
    unresolved = {(token.space, token.name) for token in map(parse, unresolved_tokens)}

    def resolved(token: Token) -> bool:
        return (token.space, token.name) not in unresolved

    flags = tuple(Coded("capability_unresolved", {"token": token}) for token in unresolved_tokens)

    def refuse(capability: str) -> Admission:
        refusal = Coded(
            "capability_missing", {"unit": unit.id, "method": method.id, "capability": capability}
        )
        return Admission(False, refusal, _sorted_notices(flags))

    if unit.payload.get("bindable") is False:
        return Admission(
            False, Coded("model_unsupported", {"model": unit.id}), _sorted_notices(flags)
        )
    p_m = method.provides
    p_d = definition.provides
    own = f"conn:{definition.id}"
    if not satisfied(own, p_m, resolved):
        return refuse(own)
    for clause in unit.requires:
        if not any(
            satisfied(token, p_d if parse(token).space == "conn" else (*p_m, *p_d), resolved)
            for token in clause
        ):
            return refuse(render(clause))
    for clause in method.requires:
        if not any(satisfied(token, p_d, resolved) for token in clause):
            return refuse(render(clause))
    evidence = (
        *unit.evidence_notices(),
        *method.evidence_notices(),
        *definition.evidence_notices(),
    )
    return Admission(True, None, _sorted_notices((*evidence, *flags)))


class RegistryView(Protocol):
    """What `admission_matrix` reads of a registry: its registered descriptors, sorted."""

    def descriptors(self, kinds: Sequence[str] | None = None) -> tuple[Registered, ...]: ...


@dataclass(frozen=True)
class Verdict:
    """One row of the admission matrix."""

    unit: Registered
    method: Registered
    admission: Admission


def admission_matrix(registry: RegistryView, definition: Registered) -> tuple[Verdict, ...]:
    """D5: every (unit, method) verdict over the registered `unit_model` × `property_method`
    descriptors on `definition`, sorted by (unit id, unit version, method id, method version):
    the input of §2.4.3's coverage matrix (F6)."""
    units = registry.descriptors(("unit_model",))
    methods = registry.descriptors(("property_method",))
    return tuple(
        Verdict(unit, method, admit(unit, method, definition))
        for unit in units
        for method in methods
    )
