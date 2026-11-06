"""The legacy grammar (MSG design note §4.3, normative): a machine text as a chain of codes.

Every existing machine message (`code(a, b): inner(c): detail…`) maps into the explanation model
through this parser, so no producer changes its text (I1). `parse_chain` is lexical; `resolve`
then names each code's positional args by its catalogue entry, expands `code`-typed args into
further chain codes, and applies the entries' `detail_pattern`s.
"""

from __future__ import annotations

import math
import re
from collections.abc import Container, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from openflowsheet.messages.catalogue import Catalogue

SEPARATOR: Final[str] = ": "
_SEGMENT: Final = re.compile(
    r"^(?P<code>[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)*)(?:\((?P<args>[^()]*)\))?$"
)
#: `thermo.PropertyStatus`'s literals (rule 3), restated so that this module imports nothing from
#: the solver; `tests/test_msg_engine.py` holds the two equal.
PROPERTY_STATUSES: Final[frozenset[str]] = frozenset(
    {"ok", "out_of_domain", "unsupported", "not_converged", "error"}
)


@dataclass(frozen=True)
class Segment:
    """One code of a chain, with its positional args as written."""

    code: str
    args: tuple[str, ...] = ()


@dataclass(frozen=True)
class Chain:
    """The lexical parse of a machine text: its codes outer → inner, the `PropertyStatus` that
    preceded a code (if any), and the rest as `detail` text (or `None`)."""

    segments: tuple[Segment, ...]
    status: str | None = None
    detail: str | None = None

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(segment.code for segment in self.segments)


def _code_segment(text: str, keys: Container[str]) -> Segment | None:
    match = _SEGMENT.match(text)
    if match is None:
        return None
    code, args = match.group("code"), match.group("args")
    if "_" not in code and args is None and code not in keys:
        return None
    parsed = () if args is None else tuple(arg.strip() for arg in args.split(","))
    return Segment(code, parsed)


def parse_chain(text: str, keys: Container[str] = ()) -> Chain:
    """Rules 1–4: the first line split on `": "`, parsed left to right into code segments until
    the first segment that is neither a code nor a status; that segment, the rest of the line and
    lines 2 and after are the `detail` text. `keys` are the catalogue's (rule 2's third clause)."""
    first, _, rest = text.partition("\n")
    parts = first.split(SEPARATOR)
    segments: list[Segment] = []
    status: str | None = None
    detail_parts: list[str] = []
    i = 0
    while i < len(parts):
        part = parts[i]
        if (
            part in PROPERTY_STATUSES
            and i + 1 < len(parts)
            and _code_segment(parts[i + 1], keys) is not None
        ):
            status = status or part
            i += 1
            continue
        segment = _code_segment(part, keys)
        if segment is None:
            detail_parts = parts[i:]
            break
        segments.append(segment)
        i += 1
    detail_lines = [SEPARATOR.join(detail_parts)] if detail_parts else []
    if rest:
        detail_lines.append(rest)
    detail = "\n".join(detail_lines) if detail_lines else None
    return Chain(tuple(segments), status, detail)


@dataclass
class Link:
    """A resolved chain code: its params (named args, expansion, detail-pattern groups)."""

    code: str
    params: dict[str, Any] = field(default_factory=dict)
    expanded: bool = False


def resolve(chain: Chain, catalogue: Catalogue) -> list[Link]:
    """Rule 5: name each code's args by its entry, expand `code`-typed args, and apply each
    entry's `detail_pattern` to the `detail` text; groups go to the innermost resolved code."""
    links: list[Link] = []
    for segment in chain.segments:
        entry = catalogue.entry(segment.code)
        link = Link(segment.code)
        links.append(link)
        if entry is None:
            continue
        expansions: list[Link] = []
        for name, value in zip(entry.args, segment.args, strict=False):
            link.params[name] = value
            declared = entry.params.get(name)
            if (
                declared is not None
                and declared.type == "code"
                and "(" not in value
                and _SEGMENT.match(value)
            ):
                expansions.append(Link(value, expanded=True))
        links.extend(expansions)
    if chain.detail is not None:
        _apply_detail(links, chain.detail, catalogue)
    return links


def _apply_detail(links: list[Link], detail: str, catalogue: Catalogue) -> None:
    resolved = [link for link in links if catalogue.entry(link.code) is not None]
    if not resolved:
        return
    innermost = resolved[-1]
    innermost.params.setdefault("detail", detail)
    for link in resolved:
        entry = catalogue.entry(link.code)
        assert entry is not None
        pattern = entry.detail_pattern
        if pattern is None:
            continue
        match = re.search(pattern, detail)
        if match is None:
            continue
        groups = {k: v for k, v in match.groupdict().items() if v is not None}
        innermost_entry = catalogue.entry(innermost.code)
        assert innermost_entry is not None
        declarations = {**entry.params, **innermost_entry.params}
        for name, value in groups.items():
            if name.endswith("_unit") and name[: -len("_unit")] in groups:
                continue
            innermost.params[name] = _typed(name, value, groups, declarations)


def _typed(
    name: str, value: str, groups: Mapping[str, str], declarations: Mapping[str, Any]
) -> Any:
    try:
        number = float(value)
    except ValueError:
        return value
    if not math.isfinite(number):
        # `float` reads "nan" and "inf"; a params document holds finite numbers only (§4.5).
        return value
    declared = declarations.get(name)
    if declared is not None and declared.type == "quantity":
        unit: str | None = groups.get(f"{name}_unit", declared.unit)
        if unit is None:
            return number
        return {"value": number, "unit": unit, "kind": declared.quantity_kind}
    return number
