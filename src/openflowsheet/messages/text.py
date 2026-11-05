"""The text format (MSG design note §4.5): Python `__str__`, CLI stderr and CLI human output.

    <summary>
      Cause:   <cause>
      Why:     <why>
      Do:      <action>
      Hint:    <hint>
      Kind:    <kinds.yaml label>
      Code:    <code>[, in <outer chain codes joined " → ">] (openflowsheet explain <code>)
      Docs:    <docs>
      Details: <machine details>

A line is omitted when its content is absent. There is no wrapping; a field's continuation lines
are indented by 11 spaces.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from openflowsheet.messages.catalogue import CATALOGUE, Catalogue

INDENT: Final[str] = " " * 11


def _lines(prefix: str, text: str) -> list[str]:
    first, *rest = text.split("\n")
    return [prefix + first, *(INDENT + line for line in rest)]


def code_line(explanation: Mapping[str, Any]) -> str:
    code = str(explanation["code"])
    chain = [str(item) for item in explanation.get("chain", ())]
    outer = chain[: chain.index(code)] if code in chain else []
    inside = f", in {' → '.join(outer)}" if outer else ""
    return f"{code}{inside} (openflowsheet explain {code})"


def format_text(
    explanation: Mapping[str, Any], details: str | None, *, catalogue: Catalogue = CATALOGUE
) -> str:
    """The layered text of `explanation`, ending with the machine `details` verbatim."""
    lines = _lines("", str(explanation["summary"]))
    fields = (
        ("  Cause:   ", explanation.get("cause")),
        ("  Why:     ", explanation.get("why")),
        ("  Do:      ", explanation.get("action")),
        ("  Hint:    ", explanation.get("hint")),
        ("  Kind:    ", catalogue.kind(str(explanation["kind"])).label),
        ("  Code:    ", code_line(explanation)),
        ("  Docs:    ", explanation.get("docs")),
        ("  Details: ", details),
    )
    for prefix, value in fields:
        if value:
            lines.extend(_lines(prefix, str(value)))
    return "\n".join(lines)
