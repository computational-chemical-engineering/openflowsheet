"""Capability tokens, their spaces and satisfaction (ADR 0060 D4).

A token is `<space>:<name>` or `<space>:<name>:<level>`; an absent level is 0, and normalisation
drops a stated `:0`, so equal tokens have one spelling. A required `s:n:L` is satisfied by a
provision set holding `s:n:L'` with `L' >= L`. `requires` is a conjunction of clauses, a clause a
disjunction of tokens.

The spaces are a closed table. `vocab`, `flash`, `convention` and `legacy` are **static**: a name
outside the space's fixed source is `capability_unknown`. The others are **registry-derived**: a
name is checked by grammar only when a package is validated, and is *resolved* only when a
registered descriptor gives it (an id of the space's kind; for `x`, a name some descriptor
provides). An unresolved token is never satisfied, and every admission naming one carries the
notice `capability_unresolved`.

This module is the lowest layer of `openflowsheet.registry`: standard library only.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Final, NamedTuple

#: D4's token grammar.
TOKEN_PATTERN: Final = re.compile(r"^[a-z_]+:[A-Za-z0-9][A-Za-z0-9_.+-]*(:(0|[1-9][0-9]*))?$")
#: D2's id grammar (the registry-derived spaces' names are ids, so this is their name grammar).
ID_PATTERN: Final = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*(\.[A-Za-z0-9][A-Za-z0-9_-]*)*$")
#: D7's namespace grammar, the first segment of an `x:` name.
NAMESPACE_PATTERN: Final = re.compile(r"^[a-z][a-z0-9_]*$")

#: The seven legacy provider ids (D6), the `legacy` space's static source. Frozen.
LEGACY_PROVIDERS: Final = frozenset(
    {
        "syn001",
        "pr-c1-v1",
        "pr-lib-v1",
        "iapws95-v1",
        "coolprop-heos-v1",
        "wilson-ig-v1",
        "wilson-ig-v2",
    }
)
#: The flash specifications ADR-F2/F5 own; `TP` today.
FLASHES: Final = frozenset({"TP"})
#: The reference conventions of `docs/interfaces-frozen.md` §3 (ADR 0001 D5 and its amendments);
#: ADR-F4 adds to this table.
CONVENTIONS: Final = frozenset(
    {"SYN-001-ref-v1", "PR-C1-ref-v1", "IAPWS95-ref-v1", "COOLPROP-DEF-ref-v1"}
)
#: F4's vocabulary registry. Empty until ADR-F4 installs its validator, so every `vocab:` token is
#: `capability_unknown` until then (F1 build decision, `docs/F1_DECISIONS.md`).
VOCABULARY: Final[frozenset[str]] = frozenset()

#: The static spaces and the fixed source of their names.
STATIC_SPACES: Final[Mapping[str, frozenset[str]]] = MappingProxyType(
    {"vocab": VOCABULARY, "flash": FLASHES, "convention": CONVENTIONS, "legacy": LEGACY_PROVIDERS}
)
#: The registry-derived spaces and the descriptor kind whose ids name them; `x` names are those a
#: descriptor of the namespace provides, so it has no kind.
REGISTRY_SPACES: Final[Mapping[str, str | None]] = MappingProxyType(
    {
        "conn": "connection_definition",
        "phase": "phase_family",
        "attr": "attribute_kind",
        "derived": "derived_quantity",
        "kinetics": "kinetics_kind",
        "trial_set": "stability_trial_set",
        "x": None,
    }
)
SPACES: Final = frozenset(STATIC_SPACES) | frozenset(REGISTRY_SPACES)


@dataclass(frozen=True)
class Coded:
    """A typed refusal, quarantine reason or notice: a catalogued code and its params."""

    code: str
    params: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))

    def as_document(self) -> dict[str, Any]:
        return {"code": self.code, "params": dict(self.params)}

    def sort_key(self) -> tuple[bytes, tuple[tuple[bytes, bytes], ...]]:
        """UTF-8 order of the code, then of the params by name."""
        return (
            _utf8(self.code),
            tuple((_utf8(name), _utf8(self.params[name])) for name in sorted(self.params)),
        )


class Token(NamedTuple):
    """A parsed token. `spelling` is the normalised text (`:0` dropped)."""

    space: str
    name: str
    level: int

    @property
    def spelling(self) -> str:
        return (
            f"{self.space}:{self.name}"
            if self.level == 0
            else f"{self.space}:{self.name}:{self.level}"
        )


def parse(text: str) -> Token:
    """The token `text` spells; `ValueError` when it does not match D4's grammar."""
    if TOKEN_PATTERN.match(text) is None:
        raise ValueError(f"not a capability token: {text!r}")
    parts = text.split(":")
    return Token(parts[0], parts[1], int(parts[2]) if len(parts) == 3 else 0)


def normalise_token(text: str) -> str:
    """D2: one spelling per token, the level `:0` dropped."""
    return parse(text).spelling


def _utf8(text: str) -> bytes:
    return text.encode("utf-8")


def normalise_requires(requires: Iterable[Iterable[str]]) -> tuple[tuple[str, ...], ...]:
    """D2: each clause's tokens normalised, sorted (UTF-8 bytes) and deduplicated; the clauses
    deduplicated and sorted by their token tuples."""
    clauses = {
        tuple(sorted({normalise_token(token) for token in clause}, key=_utf8))
        for clause in requires
    }
    return tuple(sorted(clauses, key=lambda clause: tuple(_utf8(t) for t in clause)))


def normalise_provides(provides: Iterable[str]) -> tuple[str, ...]:
    """D2: per (space, name) the highest level kept; sorted by UTF-8 bytes."""
    best: dict[tuple[str, str], Token] = {}
    for text in provides:
        token = parse(text)
        held = best.get((token.space, token.name))
        if held is None or token.level > held.level:
            best[(token.space, token.name)] = token
    return tuple(sorted((token.spelling for token in best.values()), key=_utf8))


def render(clause: Sequence[str]) -> str:
    """D5: the token of a one-token clause, else the tokens joined by `|`."""
    return "|".join(clause)


#: Answers whether a token's (space, name) is resolved in the registry at hand (D4).
Resolver = Callable[[Token], bool]


def satisfied(required: str, provisions: Iterable[str], resolved: Resolver) -> bool:
    """D4: `s:n:L` is satisfied iff it is resolved and the provisions hold `s:n:L'`, `L' >= L`."""
    token = parse(required)
    if not resolved(token):
        return False
    return any(
        held.space == token.space and held.name == token.name and held.level >= token.level
        for held in map(parse, provisions)
    )


def x_namespace(name: str) -> str | None:
    """The `<namespace>` of an `x:<namespace>.<name>` name, or `None` when it has no such form."""
    head, dot, rest = name.partition(".")
    if not dot or not rest or NAMESPACE_PATTERN.match(head) is None:
        return None
    return head


def token_problem(
    text: str, *, providing: bool, builtin: bool, namespace: str | None
) -> Coded | None:
    """D4's validation of one declared token, reading only the token, the declaring side and the
    static tables: `capability_unknown` for an unknown space, a name outside a static space's
    source, or a registry-derived name outside its grammar; `reserved_capability` for a `legacy:`
    token of a non-built-in, or an `x:` token provided outside the provider's namespace (a
    built-in has no namespace and provides none). `None` when the token is valid."""
    token = parse(text)
    spelling = token.spelling
    if token.space not in SPACES:
        return Coded("capability_unknown", {"token": spelling})
    if token.space == "legacy" and not builtin:
        return Coded("reserved_capability", {"token": spelling})
    if token.space in STATIC_SPACES:
        if token.name not in STATIC_SPACES[token.space]:
            return Coded("capability_unknown", {"token": spelling})
        return None
    if token.space == "x":
        owner = x_namespace(token.name)
        if owner is None:
            return Coded("capability_unknown", {"token": spelling})
        if providing and (builtin or owner != namespace):
            return Coded("reserved_capability", {"token": spelling})
        return None
    if ID_PATTERN.match(token.name) is None:
        return Coded("capability_unknown", {"token": spelling})
    return None


def is_static(token: Token) -> bool:
    return token.space in STATIC_SPACES
