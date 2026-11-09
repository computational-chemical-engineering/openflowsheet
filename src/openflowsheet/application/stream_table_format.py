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

A document produced under a display preference (ADR 0075 D7.3: `display` members and the root
`display_units`) prints in its display units (D7.6): the text header names the preference (and
the ambient pressure when a gauge unit is used), each converted row label, energy header and CSV
column names its display unit, and each converted value is its display value. A display value out
of range prints as an absent value with its reason (`text`) or an empty cell (`csv`). Without a
preference, or with `si`, every form is ST's.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import Any, Final

from openflowsheet.application.contract import api_error
from openflowsheet.application.projection import ELIDED, MAX_PAGE, escape_token
from openflowsheet.application.stream_table import SITES
from openflowsheet.canonical import canonical_json
from openflowsheet.units import DISPLAY_KINDS
from openflowsheet.units.display import csv_suffix

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
#: The display kind of each quantity column (ADR 0075 D7.6), and of the per-component `n` and `x`;
#: a substream's member and a phase's of one name have one kind.
_CSV_KINDS: Final[Mapping[str, str | None]] = {
    "T_K": SITES["stream"]["T"],
    "P_Pa": SITES["stream"]["P"],
    **{column: {**SITES["substream"], **SITES["phase"]}[m] for column, m in _CSV_MEMBERS.items()},
    "n": SITES["substream"]["n"],
    "x": SITES["substream"]["x"],
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
#: The energy kinds whose conversion puts a `[unit]` on every energy header (ADR 0075 D7.6).
_ENERGY_KINDS: Final = frozenset({"enthalpy_flow", "heat_rate", "power"})


# -- display (ADR 0075 D7.6) -----------------------------------------------------------------------


def _display_units(document: Mapping[str, Any]) -> Mapping[str, str]:
    """The resolved map kind → display unit the document was produced under (its root
    `display_units` echo); empty for an SI document and for `si`."""
    echo = document.get("display_units")
    return {} if echo is None else echo["units"]


def _shown(
    holder: Mapping[str, Any], site: str, member: str, units: Mapping[str, str]
) -> tuple[Any, Mapping[str, Any] | None]:
    """`holder[member]` as printed: the display value when its kind is converted, else the SI
    value; and the reason when it has none (an absent value's, or `display_out_of_range`)."""
    value = holder.get(member)
    if value is None:
        return None, holder.get("absent", {}).get(member)
    if SITES[site].get(member) not in units:
        return value, None
    item = holder["display"][member]
    return item["value"], item.get("reason")


def _converted_unit(site: str, member: str, units: Mapping[str, str]) -> str | None:
    """The display unit of `member` of a `site` object, `None` when it is printed in SI."""
    kind = SITES[site].get(member)
    return None if kind is None else units.get(kind)


def _label(label: str, unit: str | None) -> str:
    """A text row label naming its display unit: `T [K]` → `T [degC]`, `vf molar` →
    `vf molar [%]`; unchanged when the row is printed in SI."""
    if unit is None:
        return label
    base = label.split(" [", 1)[0]
    return f"{base} [{unit}]"


def _column(column: str, kind: str | None, units: Mapping[str, str]) -> str:
    """A CSV column named in its display unit: the SI unit's suffix replaced by the display
    unit's (`T_K` → `T_degC`), a suffix appended to a fraction column (`x_<c>` → `x_<c>_pct`);
    unchanged when the column is printed in SI."""
    if kind is None or kind not in units:
        return column
    si = DISPLAY_KINDS[kind].si_unit
    base = column
    if si != "1":
        suffix = f"_{csv_suffix(si)}"
        assert column.endswith(suffix), (column, suffix)
        base = column[: -len(suffix)]
    return f"{base}_{csv_suffix(units[kind])}"


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
    components: Sequence[str],
    holder: Mapping[str, Any],
    listed: Sequence[str],
    site: str,
    units: Mapping[str, str],
) -> list[str]:
    """`n_<c>` then `x_<c>` cells for each declared component, from `holder`'s arrays, which are
    in the order of `listed` (the substream's components); display values where converted."""
    position = {name: index for index, name in enumerate(listed)}
    cells: list[str] = []
    for member in ("n", "x"):
        values = holder.get(member)
        if values is not None and SITES[site][member] in units:
            values = [None if item is None else item["value"] for item in holder["display"][member]]
        for name in components:
            index = position.get(name)
            found = values[index] if isinstance(values, list) and index is not None else None
            cells.append(_cell(found))
    return cells


def _csv_rows(document: Mapping[str, Any]) -> Iterator[list[str]]:
    units = _display_units(document)
    components = [component["id"] for component in document["components"]]
    yield [
        *(_column(column, _CSV_KINDS.get(column), units) for column in CSV_COLUMNS),
        *(_column(f"n_{name}_mol_s", _CSV_KINDS["n"], units) for name in components),
        *(_column(f"x_{name}", _CSV_KINDS["x"], units) for name in components),
    ]
    for stream in document["streams"]:
        for substream in stream["substreams"]:
            listed = substream["components"]
            head = [stream["id"], substream["id"]]
            conditions = [_cell(_shown(stream, "stream", m, units)[0]) for m in ("T", "P")]
            total = [
                ""
                if column == "phase_fraction_molar"
                else _cell(_shown(substream, "substream", member, units)[0])
                for column, member in _CSV_MEMBERS.items()
            ]
            yield [
                *head,
                "",
                "",
                "",
                *conditions,
                *total,
                *_per_component(components, substream, listed, "substream", units),
            ]
            for phase in substream["phases"]:
                identity = phase["id"]
                values = [
                    ""
                    if column.startswith("vapor_fraction")
                    else _cell(_shown(phase, "phase", member, units)[0])
                    for column, member in _CSV_MEMBERS.items()
                ]
                yield [
                    *head,
                    identity["family"],
                    _text_cell(identity["qualifier"]),
                    _text_cell(identity["ordinal"]),
                    *conditions,
                    *values,
                    *_per_component(components, phase, listed, "phase", units),
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


def _value(
    holder: Mapping[str, Any],
    site: str,
    member: str,
    notes: _Footnotes,
    units: Mapping[str, str],
) -> str:
    """A number as `{:.6g}` (its display value where converted); an absent one, or one whose
    display value is out of range, as `-` and its footnote mark."""
    value, reason = _shown(holder, site, member, units)
    if value is None:
        return "-" if reason is None else f"-{notes.mark(reason)}"
    if isinstance(value, float | int) and not isinstance(value, bool):
        return f"{value:.6g}"
    return str(value)


def _row(label: str, cells: Sequence[str]) -> str:
    return (
        f"{label:<{LABEL_WIDTH}}" + "".join(f"{cell:>{VALUE_WIDTH}}" for cell in cells)
    ).rstrip()


def _x_cell(
    substream: Mapping[str, Any], name: str, notes: _Footnotes, units: Mapping[str, str]
) -> str:
    values = substream.get("x")
    if values is None:
        reason = substream.get("absent", {}).get("x")
        return "-" if reason is None else f"-{notes.mark(reason)}"
    listed = substream["components"]
    if name not in listed:
        return "-"
    index = listed.index(name)
    if SITES["substream"]["x"] not in units:
        return f"{values[index]:.6g}"
    item = substream["display"]["x"][index]
    if item["value"] is None:
        return f"-{notes.mark(item['reason'])}"
    return f"{item['value']:.6g}"


def _stream_block(
    streams: Sequence[Mapping[str, Any]],
    components: Sequence[str],
    notes: _Footnotes,
    units: Mapping[str, str],
) -> list[str]:
    substreams = [stream["substreams"][0] for stream in streams]  # v1: one, `mixed`
    lines = [_row("stream", [stream["id"] for stream in streams])]

    def rows(table: Sequence[tuple[str, str, bool]]) -> None:
        for label, member, own in table:
            holders, site = (streams, "stream") if own else (substreams, "substream")
            shown = _label(label, _converted_unit(site, member, units))
            lines.append(_row(shown, [_value(h, site, member, notes, units) for h in holders]))

    rows(_TEXT_ROWS_BEFORE_X)
    x_label = _converted_unit("substream", "x", units)
    for name in components:
        cells = [_x_cell(sub, name, notes, units) for sub in substreams]
        lines.append(_row(_label(f"x[{name}]", x_label), cells))
    rows(_TEXT_ROWS_AFTER_X)
    phases = [
        "+".join(phase["id"]["family"] for phase in sub["phases"]) or "-" for sub in substreams
    ]
    lines.append(_row("phases", phases))
    return lines


def _verifier(checks: Sequence[Mapping[str, Any]]) -> str:
    return ",".join(str(check["result"]) for check in checks) or "-"


def _energy_row(
    name: str,
    model: str,
    holder: Mapping[str, Any],
    site: str,
    members: Sequence[str],
    notes: _Footnotes,
    units: Mapping[str, str],
) -> str:
    cells = "".join(
        f"{_value(holder, site, member, notes, units):>{VALUE_WIDTH}}" for member in members
    )
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
    ]
    units = _display_units(document)
    if units:
        canonical = ",".join(f"{kind}={unit}" for kind, unit in sorted(units.items()))
        lines.append(f"display units:       {canonical}")
        ambient = document["display_units"]["ambient_pressure"]
        if ambient is not None:
            lines.append(f"ambient pressure:    {ambient['value']:.6g} Pa")
    else:
        lines.append("SI units")
    components = [component["id"] for component in document["components"]]
    streams = document["streams"]
    for start in range(0, len(streams), TEXT_COLUMNS):
        lines.append("")
        lines += _stream_block(streams[start : start + TEXT_COLUMNS], components, notes, units)
    energy = document["energy"]
    lines.append("")
    names: Sequence[str] = _ENERGY_HEADER
    if _ENERGY_KINDS & set(units):
        kinds = (SITES["unit"][name] for name in _ENERGY_HEADER)
        names = [
            f"{name} [{units.get(kind, DISPLAY_KINDS[kind].si_unit)}]"
            for name, kind in zip(_ENERGY_HEADER, kinds, strict=True)
            if kind is not None
        ]
    header = "".join(f"{name:>{VALUE_WIDTH}}" for name in names)
    lines.append(f"{'unit':<{LABEL_WIDTH}}{'model':<{LABEL_WIDTH}}{header}  verifier")
    for unit in energy["units"]:
        members = ("H_in", "H_out", "Q", "W", "closure")
        lines.append(_energy_row(unit["id"], unit["model"], unit, "unit", members, notes, units))
    overall = energy["overall"]
    members = ("H_feeds", "H_products", "Q", "W", "closure")
    lines.append(_energy_row("overall", "", overall, "overall", members, notes, units))
    footnotes = notes.lines()
    if footnotes:
        lines.append("")
        lines += footnotes
    return "\n".join(lines) + "\n"
