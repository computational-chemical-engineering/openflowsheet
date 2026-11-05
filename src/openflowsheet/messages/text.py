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
are indented by 11 spaces. `format_entry` is `openflowsheet explain <code>`'s text for a catalogue
entry (§3.5, §3.7), in the same form.
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


#: §4.12: what a stub's page and entry text say in place of a plain-language explanation.
STUB_NOTE: Final[str] = (
    "No plain-language explanation is written yet; the summary is the technical one."
)


def format_entry(entry: Mapping[str, Any], *, catalogue: Catalogue = CATALOGUE) -> str:
    """`openflowsheet explain <code>`'s text (§3.7): a `message_entry` document (§4.9) — the code
    and title, then its display templates, params, gap, see-also and docs in the layered text's
    11-column form, then each rendered example's layered text, indented by 2."""
    lines = [f"{entry['code']}: {entry['title']}"]
    params = ", ".join(
        f"{param['name']} ({param['type']}{', optional' if param['optional'] else ''})"
        for param in entry["params"]
    )
    gap = entry.get("gap") or {}
    gap_text = "; ".join(
        f"{name} {gap[name]}" for name in ("limitation", "capability") if gap.get(name)
    )
    replaced = entry.get("replaced_by")
    fields = (
        ("  Kind:    ", catalogue.kind(str(entry["kind"])).label),
        ("  Summary: ", entry.get("summary")),
        ("  Note:    ", None if entry["complete"] else STUB_NOTE),
        ("  Context: ", entry.get("context")),
        ("  Where:   ", entry.get("where")),
        ("  Why:     ", entry.get("why")),
        ("  Do:      ", entry.get("action")),
        ("  Params:  ", params),
        ("  Gap:     ", gap_text),
        ("  See:     ", ", ".join(entry["see_also"])),
        (
            "  Status:  ",
            (f"deprecated, replaced by {replaced}" if replaced else "deprecated")
            if entry["deprecated"]
            else None,
        ),
        ("  Docs:    ", entry["docs"]),
    )
    for prefix, value in fields:
        if value:
            lines.extend(_lines(prefix, str(value)))
    for example in entry["examples"]:
        lines.append("")
        lines.append("Example:")
        text = format_text(example, None, catalogue=catalogue)
        lines.extend("  " + line for line in text.split("\n"))
    return "\n".join(lines)
