// ST's stream table and energy summary in the streams screen (ADR 0068; Frank's O3, 2026-11-08).
//
// Reads a `stream-table-v1` table as `get_stream_table` returns it and lays it out as rows,
// one per stream for its mixed total and one per phase under it — the rows of the operation's own
// CSV form (`stream_table_format.CSV_COLUMNS`). Nothing is computed: every value is the
// table's, in the SI unit its column names, and a value the table leaves null is shown
// with the reason the table gives for it (its `absent` entry), never filled in.

// The quantity columns, in the CSV form's order: the member read (on the stream for T and P, on
// the substream for a total row, on the phase for a phase row) and the SI unit of the schema.
export const QUANTITY_COLUMNS = Object.freeze([
  { member: "T", on: "stream", unit: "K" },
  { member: "P", on: "stream", unit: "Pa" },
  { member: "n_total", unit: "mol/s" },
  { member: "m_total", unit: "kg/s" },
  { member: "phase_fraction_molar", unit: null },
  { member: "vapor_fraction_molar", unit: null },
  { member: "vapor_fraction_mass", unit: null },
  { member: "h", unit: "J/mol" },
  { member: "h_mass", unit: "J/kg" },
  { member: "s", unit: "J/(mol K)" },
  { member: "s_mass", unit: "J/(kg K)" },
  { member: "v", unit: "m3/mol" },
  { member: "rho", unit: "kg/m3" },
  { member: "H_flow", unit: "W" },
  { member: "S_flow", unit: "W/K" },
  { member: "V_flow", unit: "m3/s" },
]);

// The members a total row and a phase row carry (the schema's substream and phase objects); a
// column outside its row's object is not applicable there, which is not an absence.
const TOTAL_MEMBERS = new Set([
  "n_total", "m_total", "vapor_fraction_molar", "vapor_fraction_mass", "h", "h_mass", "s",
  "s_mass", "rho", "H_flow", "S_flow", "V_flow",
]);
const PHASE_MEMBERS = new Set([
  "n_total", "m_total", "phase_fraction_molar", "h", "h_mass", "s", "s_mass", "v", "rho",
  "H_flow", "S_flow", "V_flow",
]);

// The energy table's quantity columns (unit W), as the text form's energy table orders them.
export const ENERGY_COLUMNS = Object.freeze(["H_in", "H_out", "Q", "W", "closure"]);
// The overall row names its two totals after the flowsheet's feeds and products.
const OVERALL_MEMBERS = Object.freeze({ H_in: "H_feeds", H_out: "H_products" });

// A phase id as the text form writes it: the family, `(qualifier)` when there is one, and
// `.ordinal` past the first.
export function phaseLabel(phaseId) {
  const qualifier = phaseId.qualifier === null || phaseId.qualifier === undefined ? "" : `(${phaseId.qualifier})`;
  const ordinal = phaseId.ordinal > 1 ? `.${phaseId.ordinal}` : "";
  return `${phaseId.family}${qualifier}${ordinal}`;
}

// The canonical text of an absent entry, `code(param=value, …)`, params in key order: the key
// under which one reason is footnoted once.
export function entryText(entry) {
  const params = Object.keys(entry.params ?? {})
    .sort()
    .map((name) => {
      const value = entry.params[name];
      return `${name}=${Array.isArray(value) ? value.join(",") : String(value)}`;
    });
  return `${entry.code}(${params.join(", ")})`;
}

function param(entry, name) {
  const value = entry.params?.[name];
  if (value === undefined || value === null) return null;
  return Array.isArray(value) ? value.join(", ") : String(value);
}

function status(entry) {
  const value = param(entry, "status");
  return value === null ? "" : ` (status ${value})`;
}

// The plain-language reading of an absent entry: the summary of its catalogue entry (MSG,
// `messages/catalogue`) for the codes the stream table emits (ST note §6.4), or null for any
// other code (the footnote then shows the code and its parameters only).
export function plainReason(entry) {
  switch (entry.code) {
    case "flash_failed":
      return (
        `The phase split of stream ${param(entry, "stream")} at its temperature and pressure could ` +
        `not be computed${status(entry)}, so its phases and the values per phase are not given; ` +
        "its flows, temperature and pressure are."
      );
    case "zero_flow":
      return `Stream ${param(entry, "stream")} carries no flow, so its temperature, composition and properties per amount are not given.`;
    case "property_not_provided":
      return `The property basis ${param(entry, "provider")} does not provide the property ${param(entry, "property")}, so the values that need it are not given.`;
    case "property_evaluation_failed":
      return `The property ${param(entry, "property")} of the ${param(entry, "phase")} phase of stream ${param(entry, "stream")} could not be evaluated${status(entry)}.`;
    case "value_not_finite":
      return `The value ${param(entry, "quantity")} of ${param(entry, "subject")} is not a finite number, so it is not given.`;
    case "stream_enthalpy_absent":
      return `The energy total of ${param(entry, "subject")} is not given: the enthalpy flow of ${param(entry, "streams")} is missing.`;
    case "energy_balance_undefined":
      return `The energy balance of unit ${param(entry, "unit")} (${param(entry, "model")}) is not given: the solution's certificate holds no energy check for it.`;
    default:
      return null;
  }
}

// Collects the distinct reasons in the order first met; `mark(entry)` is the entry's footnote
// number (1-based).
function notes() {
  const order = [];
  const index = new Map();
  return {
    mark(entry) {
      const key = entryText(entry);
      if (!index.has(key)) {
        order.push({ mark: order.length + 1, entry, text: key, plain: plainReason(entry) });
        index.set(key, order.length);
      }
      return index.get(key);
    },
    list: order,
  };
}

// A cell of `object`'s `member`: `{value}` when the table gives a number, `{absent: {mark,
// text}}` when it gives null with a reason, `{value: null}` for a null without one, and null when
// the member is not one of the row's (not applicable).
function cell(object, member, applies, footnotes) {
  if (!applies) return null;
  const reason = object.absent?.[member];
  if (reason) return { value: null, absent: { mark: footnotes.mark(reason), text: entryText(reason) } };
  const value = object[member];
  return { value: value === undefined ? null : value };
}

// `{rows, energy, notes, warning}` of a `stream-table-v1` table (the reply of `get_stream_table`):
// - `rows`: per stream, its mixed total, then one row per phase — `{stream, phase, total,
//   phaseSource, nearBoundary, dormant, cells: {member: cell}}` (`phase` "total" on the total row);
// - `energy`: one row per unit, then the overall row — `{subject, model, cells}`;
// - `notes`: the distinct reasons for every null, `{mark, entry, text, plain}`; the flash
//   failures among them are also listed in `flashFailures` for the screen's notice;
// - `warning`: the verification status when it is not VERIFIED (the text form's first line).
export function streamTableView(reply) {
  const footnotes = notes();
  const rows = [];
  for (const stream of reply.streams ?? []) {
    for (const reason of Object.values(stream.absent ?? {})) footnotes.mark(reason);
    for (const substream of stream.substreams ?? []) {
      const base = {
        stream: stream.id,
        phaseSource: substream.phase_source,
        nearBoundary: substream.flash_near_phase_boundary === true,
        dormant: stream.dormant === true,
      };
      const totalCells = {};
      for (const column of QUANTITY_COLUMNS) {
        totalCells[column.member] =
          column.on === "stream"
            ? cell(stream, column.member, true, footnotes)
            : cell(substream, column.member, TOTAL_MEMBERS.has(column.member), footnotes);
      }
      for (const reason of Object.values(substream.absent ?? {})) footnotes.mark(reason);
      rows.push({ ...base, phase: "total", total: true, cells: totalCells });
      for (const phase of substream.phases ?? []) {
        const cells = {};
        for (const column of QUANTITY_COLUMNS) {
          cells[column.member] =
            column.on === "stream" ? null : cell(phase, column.member, PHASE_MEMBERS.has(column.member), footnotes);
        }
        for (const reason of Object.values(phase.absent ?? {})) footnotes.mark(reason);
        rows.push({ ...base, phase: phaseLabel(phase.id), total: false, cells });
      }
    }
  }
  const energy = [];
  const energyRow = (subject, model, object, names) => {
    const cells = {};
    for (const member of ENERGY_COLUMNS) cells[member] = cell(object, names[member] ?? member, true, footnotes);
    for (const reason of Object.values(object.absent ?? {})) footnotes.mark(reason);
    energy.push({ subject, model, cells });
  };
  for (const unit of reply.energy?.units ?? []) energyRow(unit.id, unit.model, unit, {});
  if (reply.energy?.overall) energyRow("overall", null, reply.energy.overall, OVERALL_MEMBERS);
  const status = reply.verification_status ?? null;
  return {
    rows,
    energy,
    notes: footnotes.list,
    flashFailures: footnotes.list.filter((note) => note.entry.code === "flash_failed"),
    warning: status === "VERIFIED" ? null : status,
  };
}
