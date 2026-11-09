"""ST: the stream table's three printed forms and the assembly of a paged one (design note
`docs/design/ST-stream-table.md` §6.3; ADR 0068).

`openflowsheet streams` prints a `stream-table-v1` document as `json` (its canonical JSON), `csv`
(RFC 4180, one row per stream, substream and phase-or-total) or `text` (a header, stream blocks of
up to six columns, the energy table and the footnotes of the absent values). The forms live here,
not in the CLI, so a Python caller gets the same text the command prints (blueprint D15).

`assemble` rebuilds the whole document from `get_stream_table` projections: the first view, then
every part it elided (an object deeper than `depth`, an array cut after its first items, a view
cut to fit the size cap), each array paged with `limit` and `cursor`. Every view must carry the
first one's `sha256`; a differing one is refused `internal_error` (the document changed while it
was read).
"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import Any, Final

from openflowsheet.application.contract import api_error
from openflowsheet.application.projection import ELIDED, MAX_PAGE, escape_token
from openflowsheet.canonical import canonical_json

#: `fetch(pointer, depth, cursor, limit)`: one `get_stream_table` projection, as its document.
Fetch = Callable[[str, int, str | None, int], Mapping[str, Any]]

#: §6.3: the CSV columns before the per-component ones, in order.
CSV_COLUMNS: Final[tuple[str, ...]] = (
    "stream",
    "substream",
    "phase_family",
    "phase_qualifier",
    "phase_ordinal",
    "T_K",
    "P_Pa",
    "n_total_mol_s",
    "m_total_kg_s",
    "phase_fraction_molar",
    "vapor_fraction_molar",
    "vapor_fraction_mass",
    "h_J_mol",
    "h_J_kg",
    "s_J_molK",
    "s_J_kgK",
    "v_m3_mol",
    "rho_kg_m3",
    "H_flow_W",
    "S_flow_W_K",
    "V_flow_m3_s",
)
#: The document member each quantity column reads (on a substream for a total row, on a phase
#: for a phase row); `T_K` and `P_Pa` are the stream's.
_CSV_MEMBERS: Final[Mapping[str, str]] = {
    "n_total_mol_s": "n_total",
    "m_total_kg_s": "m_total",
    "phase_fraction_molar": "phase_fraction_molar",
    "vapor_fraction_molar": "vapor_fraction_molar",
    "vapor_fraction_mass": "vapor_fraction_mass",
    "h_J_mol": "h",
    "h_J_kg": "h_mass",
    "s_J_molK": "s",
    "s_J_kgK": "s_mass",
    "v_m3_mol": "v",
    "rho_kg_m3": "rho",
    "H_flow_W": "H_flow",
    "S_flow_W_K": "S_flow",
    "V_flow_m3_s": "V_flow",
}
#: §6.3: the text form's stream blocks — columns per block, and the label and value widths.
TEXT_COLUMNS: Final[int] = 6
LABEL_WIDTH: Final[int] = 18
VALUE_WIDTH: Final[int] = 14
#: The text rows after `x[<c>]`: label, the member, and whether it is the stream's (else the
#: substream's).
_TEXT_ROWS_BEFORE_X: Final[tuple[tuple[str, str, bool], ...]] = (
    ("T [K]", "T", True),
    ("P [Pa]", "P", True),
    ("n [mol/s]", "n_total", False),
    ("m [kg/s]", "m_total", False),
)
_TEXT_ROWS_AFTER_X: Final[tuple[tuple[str, str, bool], ...]] = (
    ("vf molar", "vapor_fraction_molar", False),
    ("vf mass", "vapor_fraction_mass", False),
    ("h [J/mol]", "h", False),
    ("h [J/kg]", "h_mass", False),
    ("s [J/(mol K)]", "s", False),
    ("s [J/(kg K)]", "s_mass", False),
    ("rho [kg/m3]", "rho", False),
    ("H [W]", "H_flow", False),
)
_ENERGY_HEADER: Final[tuple[str, ...]] = ("H_in", "H_out", "Q", "W", "closure")


# -- assembly --------------------------------------------------------------------------------------


def _elided(value: Any) -> Mapping[str, Any] | None:
    """The `$elided` marker's body when `value` is one, else `None`."""
    if isinstance(value, Mapping) and set(value) == {ELIDED}:
        marker = value[ELIDED]
        return marker if isinstance(marker, Mapping) else None
    return None


def assemble(fetch: Fetch, *, depth: int = 12, limit: int = MAX_PAGE) -> dict[str, Any]:
    """The whole `stream-table-v1` document from its projections (module docstring)."""
    first = fetch("", depth, None, limit)
    sha256 = first["sha256"]

    def checked(view: Mapping[str, Any]) -> Mapping[str, Any]:
        if view["sha256"] != sha256:
            raise api_error(
                "internal_error",
                "the stream table changed while it was read",
                expected=sha256,
                found=view["sha256"],
                pointer=view["pointer"],
            )
        return view

    def load(pointer: str) -> Any:
        view = checked(fetch(pointer, depth, None, limit))
        if not isinstance(view["value"], list):
            return complete(view["value"], pointer)
        items: list[Any] = []
        while True:
            offset = len(items)
            items.extend(
                complete(item, f"{pointer}/{offset + index}")
                for index, item in enumerate(view["value"])
            )
            cursor = view["next_cursor"]
            if cursor is None:
                return items
            view = checked(fetch(pointer, depth, cursor, limit))

    def complete(value: Any, pointer: str) -> Any:
        marker = _elided(value)
        if marker is not None:
            return load(str(marker["pointer"]))
        if isinstance(value, Mapping):
            return {
                key: complete(item, f"{pointer}/{escape_token(key)}") for key, item in value.items()
            }
        if isinstance(value, list):
            last = _elided(value[-1]) if value else None
            if last is not None and last["pointer"] == pointer and "items" in last:
                return load(pointer)  # an array cut after its first items
            return [complete(item, f"{pointer}/{index}") for index, item in enumerate(value)]
        return value

    document = complete(first["value"], "")
    assert isinstance(document, dict)
    return document


# -- json ------------------------------------------------------------------------------------------


def to_json(document: Mapping[str, Any]) -> str:
    """§6.3 `json`: the document's canonical JSON and a newline."""
    return canonical_json(document).decode("utf-8") + "\n"


# -- csv -------------------------------------------------------------------------------------------


def _cell(value: Any) -> str:
    """A CSV cell of a quantity: `repr(float)` (an integral number read back from canonical JSON,
    `10000`, is the float it spells, `10000.0`), an absent value empty."""
    if value is None:
        return ""
    return repr(float(value))


def _text_cell(value: Any) -> str:
    """A CSV cell of an identity member (a qualifier, an ordinal): as text, or empty."""
    return "" if value is None else str(value)


def _per_component(
    components: Sequence[str], holder: Mapping[str, Any], listed: Sequence[str]
) -> list[str]:
    """`n_<c>` then `x_<c>` cells for each declared component, from `holder`'s arrays, which are
    in the order of `listed` (the substream's components)."""
    position = {name: index for index, name in enumerate(listed)}
    cells: list[str] = []
    for member in ("n", "x"):
        values = holder.get(member)
        for name in components:
            index = position.get(name)
            found = values[index] if isinstance(values, list) and index is not None else None
            cells.append(_cell(found))
    return cells


def _csv_rows(document: Mapping[str, Any]) -> Iterator[list[str]]:
    components = [component["id"] for component in document["components"]]
    yield [
        *CSV_COLUMNS,
        *(f"n_{name}_mol_s" for name in components),
        *(f"x_{name}" for name in components),
    ]
    for stream in document["streams"]:
        for substream in stream["substreams"]:
            listed = substream["components"]
            head = [stream["id"], substream["id"]]
            conditions = [_cell(stream["T"]), _cell(stream["P"])]
            total = [
                "" if column == "phase_fraction_molar" else _cell(substream.get(member))
                for column, member in _CSV_MEMBERS.items()
            ]
            yield [
                *head,
                "",
                "",
                "",
                *conditions,
                *total,
                *_per_component(components, substream, listed),
            ]
            for phase in substream["phases"]:
                identity = phase["id"]
                values = [
                    "" if column.startswith("vapor_fraction") else _cell(phase.get(member))
                    for column, member in _CSV_MEMBERS.items()
                ]
                yield [
                    *head,
                    identity["family"],
                    _text_cell(identity["qualifier"]),
                    _text_cell(identity["ordinal"]),
                    *conditions,
                    *values,
                    *_per_component(components, phase, listed),
                ]


def to_csv(document: Mapping[str, Any]) -> str:
    """§6.3 `csv`: RFC 4180 (CRLF line ends), one row per (stream, substream, phase-or-total) in
    document order, the total first. A total row has empty phase columns; a phase row has empty
    vapour-fraction columns and repeats the stream's `T` and `P`; an absent value is empty."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerows(_csv_rows(document))
    return out.getvalue()


# -- text ------------------------------------------------------------------------------------------


class _Footnotes:
    """The absent values' reasons, one mark per distinct (code, params), in first-use order."""

    def __init__(self) -> None:
        self.marks: dict[str, int] = {}

    def mark(self, reason: Mapping[str, Any]) -> str:
        text = _reason_text(reason)
        number = self.marks.setdefault(text, len(self.marks) + 1)
        return f"*{number}"

    def lines(self) -> list[str]:
        return [f"*{number} {text}" for text, number in self.marks.items()]


def _param_text(value: Any) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(str(item) for item in value) + "]"
    return repr(value) if isinstance(value, float) else str(value)


def _reason_text(reason: Mapping[str, Any]) -> str:
    params = ", ".join(f"{key}={_param_text(value)}" for key, value in reason["params"].items())
    return f"{reason['code']}({params})"


def _value(holder: Mapping[str, Any], member: str, notes: _Footnotes) -> str:
    """A number as `{:.6g}`; an absent one as `-` and its footnote mark."""
    value = holder.get(member)
    if value is None:
        reason = holder.get("absent", {}).get(member)
        return "-" if reason is None else f"-{notes.mark(reason)}"
    if isinstance(value, float | int) and not isinstance(value, bool):
        return f"{value:.6g}"
    return str(value)


def _row(label: str, cells: Sequence[str]) -> str:
    return (
        f"{label:<{LABEL_WIDTH}}" + "".join(f"{cell:>{VALUE_WIDTH}}" for cell in cells)
    ).rstrip()


def _x_cell(substream: Mapping[str, Any], name: str, notes: _Footnotes) -> str:
    values = substream.get("x")
    if values is None:
        reason = substream.get("absent", {}).get("x")
        return "-" if reason is None else f"-{notes.mark(reason)}"
    listed = substream["components"]
    if name not in listed:
        return "-"
    return f"{values[listed.index(name)]:.6g}"


def _stream_block(
    streams: Sequence[Mapping[str, Any]], components: Sequence[str], notes: _Footnotes
) -> list[str]:
    substreams = [stream["substreams"][0] for stream in streams]  # v1: one, `mixed`
    lines = [_row("stream", [stream["id"] for stream in streams])]
    for label, member, own in _TEXT_ROWS_BEFORE_X:
        holders = streams if own else substreams
        lines.append(_row(label, [_value(holder, member, notes) for holder in holders]))
    for name in components:
        lines.append(_row(f"x[{name}]", [_x_cell(sub, name, notes) for sub in substreams]))
    for label, member, own in _TEXT_ROWS_AFTER_X:
        holders = streams if own else substreams
        lines.append(_row(label, [_value(holder, member, notes) for holder in holders]))
    phases = [
        "+".join(phase["id"]["family"] for phase in sub["phases"]) or "-" for sub in substreams
    ]
    lines.append(_row("phases", phases))
    return lines


def _verifier(checks: Sequence[Mapping[str, Any]]) -> str:
    return ",".join(str(check["result"]) for check in checks) or "-"


def _energy_row(
    name: str, model: str, holder: Mapping[str, Any], members: Sequence[str], notes: _Footnotes
) -> str:
    cells = "".join(f"{_value(holder, member, notes):>{VALUE_WIDTH}}" for member in members)
    return f"{name:<{LABEL_WIDTH}}{model:<{LABEL_WIDTH}}{cells}  {_verifier(holder['checks'])}"


def to_text(document: Mapping[str, Any]) -> str:
    """§6.3 `text`: a warning when the status is not `VERIFIED`, the header, the stream blocks,
    the energy table and the footnotes, each line without trailing blanks, ending in a newline."""
    notes = _Footnotes()
    source, basis = document["source"], document["basis"]
    status = document["verification_status"]
    lines: list[str] = []
    if status != "VERIFIED":
        lines.append(f"WARNING: verification_status is {status}")
    lines += [
        f"job:                 {source['job_id'] or '-'}",
        f"run:                 {source['run_id'] or '-'}",
        f"revision:            {source['revision_id']}",
        f"basis:               {basis['provider_id']}",
        f"convention:          {basis['convention']}",
        f"verification status: {status}",
        f"judged_at:           {document['judged_at'] or '-'}",
        "SI units",
    ]
    components = [component["id"] for component in document["components"]]
    streams = document["streams"]
    for start in range(0, len(streams), TEXT_COLUMNS):
        lines.append("")
        lines += _stream_block(streams[start : start + TEXT_COLUMNS], components, notes)
    energy = document["energy"]
    lines.append("")
    header = "".join(f"{name:>{VALUE_WIDTH}}" for name in _ENERGY_HEADER)
    lines.append(f"{'unit':<{LABEL_WIDTH}}{'model':<{LABEL_WIDTH}}{header}  verifier")
    for unit in energy["units"]:
        members = ("H_in", "H_out", "Q", "W", "closure")
        lines.append(_energy_row(unit["id"], unit["model"], unit, members, notes))
    overall = energy["overall"]
    members = ("H_feeds", "H_products", "Q", "W", "closure")
    lines.append(_energy_row("overall", "", overall, members, notes))
    footnotes = notes.lines()
    if footnotes:
        lines.append("")
        lines += footnotes
    return "\n".join(lines) + "\n"
