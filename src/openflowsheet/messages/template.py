"""The catalogue's template grammar (MSG design note §4.2.4, normative).

- `{name}` renders a param by its declared type; `{name!raw}` gives the raw value; `{name!title}`
  (type `code` only) gives that code's catalogue title.
- `[ … ]` is an optional segment: it renders iff every param referenced *directly* inside it (not
  in a nested segment) is present. Segments nest.
- `{{`, `}}`, `[[` and `]]` are literals, except that `]]` inside an open segment closes two
  segments (§4.13.1 writes `[, an outlet of unit {unit}[ ({unit_model})]]`); a literal `]` can
  therefore be written only outside every segment.

Nothing else: no attribute access, no indexing, no format specs, no code. A template is parsed
once into a tree of `Text`, `Param` and `Segment` nodes; rendering is `render.py`'s.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

Conversion = Literal["raw", "title"] | None

_PARAM = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)(?:!(raw|title))?\}")


class TemplateError(ValueError):
    """A template that does not parse under §4.2.4."""


@dataclass(frozen=True)
class Text:
    text: str


@dataclass(frozen=True)
class Param:
    name: str
    conversion: Conversion


@dataclass(frozen=True)
class Segment:
    nodes: tuple[Node, ...]

    @property
    def direct_names(self) -> tuple[str, ...]:
        return tuple(node.name for node in self.nodes if isinstance(node, Param))


Node = Text | Param | Segment


@lru_cache(maxsize=4096)
def parse(template: str) -> tuple[Node, ...]:
    """The node tree of `template`; raises `TemplateError`."""
    stack: list[list[Node]] = [[]]
    text: list[str] = []
    i = 0

    def flush() -> None:
        if text:
            stack[-1].append(Text("".join(text)))
            text.clear()

    while i < len(template):
        pair = template[i : i + 2]
        # `]]` inside an open segment closes segments (`[ ({unit_model})]]`, the note's own
        # worked entry); it is the literal `]` only where no segment is open.
        if pair in ("{{", "}}", "[[") or (pair == "]]" and len(stack) == 1):
            text.append(pair[0])
            i += 2
            continue
        char = template[i]
        if char == "{":
            match = _PARAM.match(template, i)
            if match is None:
                raise TemplateError(f"bad placeholder at {i} in {template!r}")
            flush()
            stack[-1].append(Param(match.group(1), match.group(2)))  # type: ignore[arg-type]
            i = match.end()
            continue
        if char == "}":
            raise TemplateError(f"unmatched '}}' at {i} in {template!r}")
        if char == "[":
            flush()
            stack.append([])
        elif char == "]":
            if len(stack) == 1:
                raise TemplateError(f"unmatched ']' at {i} in {template!r}")
            flush()
            nodes = stack.pop()
            stack[-1].append(Segment(tuple(nodes)))
        else:
            text.append(char)
        i += 1
    if len(stack) != 1:
        raise TemplateError(f"unclosed '[' in {template!r}")
    flush()
    return tuple(stack[0])


def params(nodes: tuple[Node, ...]) -> Iterator[Param]:
    """Every placeholder of the tree, depth first."""
    for node in nodes:
        if isinstance(node, Param):
            yield node
        elif isinstance(node, Segment):
            yield from params(node.nodes)


def literal(nodes: tuple[Node, ...]) -> str:
    """The template's literal text with every placeholder removed (the jargon lint's input)."""
    out: list[str] = []
    for node in nodes:
        if isinstance(node, Text):
            out.append(node.text)
        elif isinstance(node, Segment):
            out.append(literal(node.nodes))
        else:
            out.append(" ")
    return "".join(out)


def display(nodes: tuple[Node, ...]) -> str:
    """The display form of §4.9: `{p}` → `<p>`, optional brackets removed."""
    out: list[str] = []
    for node in nodes:
        if isinstance(node, Text):
            out.append(node.text)
        elif isinstance(node, Segment):
            out.append(display(node.nodes))
        else:
            out.append(f"<{node.name}>")
    return "".join(out)
