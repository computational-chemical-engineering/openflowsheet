// #/job/{jid}/streams — streams and units at a run's state (M06 design note §6.6).
//
// Reads the run's bundle listing and, through the raw export, the revision as solved, the
// solution state, the structural report and the certificate (or, without a state, the failure
// bundle's best checkpoint); `inspect_structure` of the run's revision and `list_models`. Every
// value is shown in the SI unit its column names (no conversion). Each value links to the rows
// incident on its column when the run's equation structure is the server's current one (§6.5).

import { h } from "../h.js";
import { modelSignature, streamTable, unitPanel } from "../model/streams.js";
import { link } from "../router.js";
import { DASH, fmt } from "../text.js";
import { phaseSection, runStructure } from "./certificate.js";
import {
  digestBanner,
  facts,
  getNumberMode,
  heading,
  id,
  none,
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
  const { jid, signal } = params;
  const bundle = await runBundle(api, jid, { signal });
  const revision = await readMember(api, bundle, "revision.json", { signal });
  const state = await readMember(api, bundle, "solution-state.json", { signal });
  const certificate = await readMember(api, bundle, "solution-certificate.json", { signal });
  const failure =
    state === null ? await readMember(api, bundle, "failure-bundle.json", { signal }) : null;
  const rows = await runStructure(api, bundle, bundle.run, { signal });
  const models = await api.call("list_models", {}, { signal });
  return { jid, run: bundle.run, revision, state, certificate, failure, rows, models };
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
