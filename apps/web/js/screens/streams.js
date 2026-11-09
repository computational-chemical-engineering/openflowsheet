// #/job/{jid}/streams — streams and units at a run's state (M06 design note §6.6).
//
// Reads the run's bundle listing and, through the raw export, the revision as solved, the
// solution state, the structural report and the certificate (or, without a state, the failure
// bundle's best checkpoint); `inspect_structure` of the run's revision and `list_models`. Every
// value is shown in the SI unit its column names (no conversion). Each value links to the rows
// incident on its column when the run's equation structure is the server's current one (§6.5).
// Below the streams, ST's stream table (`get_stream_table`, ADR 0068; Frank's O3): phase
// fractions, per-phase flows and enthalpy flows as the operation returns them, each null shown
// with the operation's reason for it; a refusal is shown, and the rest of the screen stays.
// The stream table is read in the viewer's display units (`units.js`; X04 A38): a converted
// value shows its display unit in the column heading and its SI value and unit in its title.
// The as-solved state above it stays SI (L-X04-2) and says so.

import { h } from "../h.js";
import { ENERGY_COLUMNS, QUANTITY_COLUMNS, streamTableView } from "../model/stream-table.js";
import { modelSignature, streamTable, unitPanel } from "../model/streams.js";
import { link } from "../router.js";
import { displayRequest, textUnit } from "../units.js";
import { DASH, explained, fmt, pill } from "../text.js";
import { phaseSection, runStructure } from "./certificate.js";
import {
  digestBanner,
  facts,
  getNumberMode,
  heading,
  id,
  none,
  numCell,
  readMember,
  runBundle,
  runLinks,
  section,
  table,
  text,
} from "./common.js";

export const name = "streams";
export const pattern = "/job/{jid}/streams";

export async function load(params, api) {
  const { jid, signal, units } = params;
  const bundle = await runBundle(api, jid, { signal });
  const revision = await readMember(api, bundle, "revision.json", { signal });
  const state = await readMember(api, bundle, "solution-state.json", { signal });
  const certificate = await readMember(api, bundle, "solution-certificate.json", { signal });
  const failure =
    state === null ? await readMember(api, bundle, "failure-bundle.json", { signal }) : null;
  const rows = await runStructure(api, bundle, bundle.run, { signal });
  const models = await api.call("list_models", {}, { signal });
  const stream = await streamTableOf(api, jid, signal, units);
  return { jid, run: bundle.run, revision, state, certificate, failure, rows, models, stream };
}

// `get_stream_table` read whole (the operation pages its document; `readWhole` follows every
// cursor and elision): `{document}`, or `{refused}` with the server's `ApiError` document when it
// gives none for this run (no solution state, a basis this installation cannot evaluate, …).
async function streamTableOf(api, jid, signal, units) {
  const request = { job_id: jid, ...displayRequest(units) };
  try {
    return { document: await api.readWhole("get_stream_table", request, { signal }), refused: null };
  } catch (error) {
    if (error?.document && error.status !== 401) return { document: null, refused: error.document };
    throw error;
  }
}

// A value cell: the number in the current mode (full value as title), the unit, and — when the
// equation links are usable — a "rows" link to the rows incident on the column.
export function valueCell(data, cell) {
  if (cell === null) return h("td", { class: "num muted" }, "not applicable");
  const full = cell.value === undefined ? DASH : String(cell.value);
  const matched = data.rows.consistent ? data.rows.index.matchedRow(cell.column) : null;
  return h(
    "td",
    { class: "num", title: `${cell.column} = ${full} ${cell.si_unit ?? ""}`.trim(), "data-column": cell.column },
    fmt(cell.value, getNumberMode()),
    matched
      ? [
          " ",
          h(
            "a",
            {
              class: "rows-link",
              href: link("/job/{jid}/row/{row}", { jid: data.jid, row: matched }, { column: cell.column }),
            },
            "rows",
          ),
        ]
      : null,
  );
}

function unitOf(rows, pick) {
  for (const row of rows) {
    const cell = pick(row);
    if (cell?.si_unit) return cell.si_unit;
  }
  return null;
}

function listed(values, render) {
  if (values === null) return h("span", { class: "muted" }, "not applicable");
  return h("ul", { class: "inline-list" }, values.map((value) => h("li", null, render(value))));
}

function portText(port) {
  return `${port.name} (${port.direction}, ${port.kind}, ×${port.multiplicity})`;
}

export function view(data) {
  const revision = data.revision?.document ?? null;
  const variables = data.state?.document?.variables ?? null;
  const columns = data.rows.structure?.columns ?? [];
  const streams = streamTable(revision, columns, variables);
  const head = heading(`Streams and units — ${data.jid}`, ...runLinks(data.jid));
  const noState =
    data.state === null
      ? section(
          "Solution state",
          h("p", { class: "notice", "data-ofs-no-state": "1" }, "no solution state recorded for this run"),
          data.failure?.document?.best_checkpoint
            ? facts([
                ["best checkpoint state_sha256", id(data.failure.document.best_checkpoint.state_sha256)],
                ["verification_scope", text(data.failure.document.best_checkpoint.verification_scope)],
                ["label", text(data.failure.document.best_checkpoint.label)],
              ])
            : none("no best checkpoint recorded"),
        )
      : null;
  const headers = [
    "connection",
    "from → to",
    ...streams.components.map((component) => ({
      text: `n.${component} (${unitOf(streams.rows, (row) => row.n[component]) ?? DASH})`,
      num: true,
    })),
    { text: `T (${unitOf(streams.rows, (row) => row.T) ?? DASH})`, num: true },
    { text: `P (${unitOf(streams.rows, (row) => row.P) ?? DASH})`, num: true },
  ];
  return h(
    "div",
    { "data-ofs-screen": "streams" },
    head,
    data.revision ? digestBanner("revision.json", data.revision.digest) : null,
    data.state ? digestBanner("solution-state.json", data.state.digest) : null,
    data.rows.consistent || data.rows.structure === null
      ? null
      : h(
          "p",
          { class: "notice" },
          "this run used a different equation structure than the server's current analysis of its revision",
        ),
    noState,
    section(
      "Streams",
      h(
        "p",
        { class: "muted", "data-ofs-si-only": "1" },
        "As solved, in SI units: this table is never converted to display units.",
      ),
      table(
        headers,
        streams.rows.map((row) => [
          row.inRevision
            ? id(row.connection)
            : h("span", null, id(row.connection), h("small", { class: "muted" }, " (binder id; not a connection of the revision)")),
          row.from ? `${row.from.instance}.${row.from.port} → ${row.to.instance}.${row.to.port}` : DASH,
          ...streams.components.map((component) => valueCell(data, row.n[component] ?? null)),
          valueCell(data, row.T),
          valueCell(data, row.P),
        ]),
      ),
    ),
    streamTableSection(data.stream),
    section(
      "Units",
      (revision?.instances ?? []).map((instance) => {
        const panel = unitPanel(instance, modelSignature(data.models, instance.model?.id));
        const own = streams.units.find((unit) => unit.instance === instance.id);
        return h(
          "div",
          { class: "unit-panel", "data-ofs-unit": instance.id },
          h("h3", null, instance.id, " ", h("small", { class: "muted" }, text(panel.model))),
          panel.listed ? null : h("p", { class: "notice" }, "the server lists no such model"),
          facts([
            ["ports", listed(panel.ports, portText)],
            ["pins", listed(panel.pins, (pin) => (typeof pin === "string" ? pin : JSON.stringify(pin)))],
            ["required", listed(panel.required, String)],
            ["zero", listed(panel.zero, String)],
          ]),
          own
            ? table(
                ["variable", { text: "value", num: true }, "unit"],
                own.columns.map((cell) => [id(cell.column), valueCell(data, cell), text(cell.si_unit)]),
              )
            : none("no unit variables"),
        );
      }),
      streams.units
        .filter((unit) => !(revision?.instances ?? []).some((instance) => instance.id === unit.instance))
        .map((unit) =>
          h(
            "div",
            { class: "unit-panel" },
            h("h3", null, text(unit.instance), " ", h("small", { class: "muted" }, "(not an instance of the revision)")),
            table(
              ["variable", { text: "value", num: true }, "unit"],
              unit.columns.map((cell) => [id(cell.column), valueCell(data, cell), text(cell.si_unit)]),
            ),
          ),
        ),
    ),
    section(
      "Phase splits",
      data.certificate ? phaseSection(data.certificate.document, data.revision) : none(),
    ),
  );
}

// --------------------------------------------------------------------------- stream table

// A column heading: the member and its unit — the display unit when the column is converted.
function headerOf(member, unit) {
  return { text: unit ? `${member} (${textUnit(unit)})` : member, num: true };
}

// A cell of the stream table: a number in the current mode, a null with its reason's footnote
// mark (the reason's code as its title), or "not applicable" where the row has no such member.
function stCell(cell) {
  if (cell === null) return h("td", { class: "num muted", title: "not applicable" }, DASH);
  if (cell.absent) {
    return h(
      "td",
      { class: "num muted", title: cell.absent.text, "data-ofs-absent": cell.absent.text },
      DASH,
      h("sup", null, `*${cell.absent.mark}`),
    );
  }
  if (cell.display) return displayCell(cell);
  return numCell(cell.value);
}

// A converted cell: the server's display value (never computed here) in the current mode, the SI
// value and unit as its title; a display without a value shows its reason's mark.
function displayCell(cell) {
  const si = `${String(cell.value)} ${cell.unit ?? ""}`.trim();
  if (cell.displayAbsent) {
    return h(
      "td",
      { class: "num muted", title: `${si}; ${cell.displayAbsent.text}`, "data-ofs-absent": cell.displayAbsent.text },
      DASH,
      h("sup", null, `*${cell.displayAbsent.mark}`),
    );
  }
  return h(
    "td",
    { class: "num", title: si, "data-ofs-display": cell.display.unit },
    fmt(cell.display.value, getNumberMode()),
  );
}

// `cell` with its column's SI unit (the title of a converted value).
function withUnit(cell, unit) {
  return cell === null || cell.display === undefined ? cell : { ...cell, unit };
}

function refusedNotice(refused) {
  return h(
    "div",
    { class: "notice", "data-ofs-stream-table-refused": String(refused.code ?? "") },
    h("p", null, `The server gives no stream table for this run: ${refused.code}: ${refused.message}`),
    explained(refused.detail?.explanation),
  );
}

export function streamTableSection(stream) {
  if (stream === null || stream === undefined) return null;
  if (stream.document === null) return section("Stream table", refusedNotice(stream.refused));
  const document = stream.document;
  const view = streamTableView(document);
  return section(
    "Stream table",
    h(
      "div",
      { "data-ofs-stream-table": "1" },
      facts([
        ["verification_status", pill(document.verification_status)],
        ["judged_at", text(document.judged_at)],
        ["property basis", id(document.basis?.provider_id)],
        ["convention", text(document.basis?.convention)],
        ["phase rule", text(document.evaluator?.phase_rule)],
      ]),
      view.warning === null
        ? null
        : h(
            "p",
            { class: "notice notice-bad", "data-ofs-stream-table-warning": view.warning },
            `The run's verification status is ${view.warning}: the table shows the stored state as it is.`,
          ),
      view.flashFailures.map((note) =>
        h("p", { class: "notice", "data-ofs-flash-failed": String(note.entry.params?.stream ?? "") }, note.plain),
      ),
      table(
        [
          "stream",
          "phase",
          "phase_source",
          "near phase boundary",
          ...QUANTITY_COLUMNS.map((column) => headerOf(column.member, view.units[column.member] ?? column.unit)),
        ],
        view.rows.map((row) => [
          id(row.stream),
          row.phase,
          row.total ? text(row.phaseSource) : DASH,
          row.total ? (row.nearBoundary ? "yes" : "no") : DASH,
          ...QUANTITY_COLUMNS.map((column) => stCell(withUnit(row.cells[column.member], column.unit))),
        ]),
      ),
      h("h3", null, "Energy"),
      table(
        ["unit", "model", ...ENERGY_COLUMNS.map((member) => headerOf(member, view.energyUnits[member] ?? "W"))],
        view.energy.map((row) => [
          id(row.subject),
          text(row.model),
          ...ENERGY_COLUMNS.map((member) => stCell(withUnit(row.cells[member], "W"))),
        ]),
      ),
      view.notes.length === 0
        ? null
        : h(
            "ol",
            { "data-ofs-stream-table-notes": String(view.notes.length) },
            view.notes.map((note) =>
              h("li", null, `*${note.mark} `, note.plain ? `${note.plain} ` : null, h("code", null, note.text)),
            ),
          ),
    ),
  );
}
