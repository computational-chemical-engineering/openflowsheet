// #/rev/{rid}/row/{row} and #/job/{jid}/row/{row} — the equation view (M06 design note §6.5).
//
// One equation row of `inspect_structure`'s index: what it is, the columns it is incident on
// (the column matched to it highlighted), its BTF block, the redundancy certificates naming it,
// whether it is a candidate specification row, and its unit's degrees of freedom — structure
// only, no symbolic text. At a run the columns carry the run's values and the certificate checks
// whose subject is the row are shown — but only when the server's current analysis of the run's
// revision has the bundle's `model_version` (the consistency guard); otherwise the view says so
// and shows no equation index. `?column=` lists the rows incident on that column, matched first.

import { h, isTree } from "../h.js";
import { checksForSubject, scaledResidual } from "../model/certificate.js";
import { structureIndex } from "../model/structure.js";
import { link } from "../router.js";
import { DASH } from "../text.js";
import { runStructure } from "./certificate.js";
import {
  digestBanner,
  facts,
  heading,
  id,
  none,
  num,
  numCell,
  pill,
  readMember,
  rowLink,
  runBundle,
  runLinks,
  section,
  table,
  text,
} from "./common.js";

export const GUARD_TEXT =
  "this run used a different equation structure than the server's current analysis of its revision";

export const revisionRow = {
  name: "revision-row",
  pattern: "/rev/{rid}/row/{row}",
  async load(params, api) {
    const { rid, row, signal, query } = params;
    const structure = await api.readWhole("inspect_structure", { revision_id: rid }, { signal });
    return {
      scope: "rev",
      owner: rid,
      revisionId: rid,
      row,
      column: query?.get("column") ?? null,
      index: structureIndex(structure),
      consistent: true,
      state: null,
      certificate: null,
    };
  },
  view: (data) => view(data),
};

export const jobRow = {
  name: "job-row",
  pattern: "/job/{jid}/row/{row}",
  async load(params, api) {
    const { jid, row, signal, query } = params;
    const bundle = await runBundle(api, jid, { signal });
    const state = await readMember(api, bundle, "solution-state.json", { signal });
    const certificate = await readMember(api, bundle, "solution-certificate.json", { signal });
    const rows = await runStructure(api, bundle, bundle.run, { signal });
    return {
      scope: "job",
      owner: jid,
      revisionId: bundle.run?.revision_id ?? null,
      row,
      column: query?.get("column") ?? null,
      index: rows.index,
      consistent: rows.consistent,
      state,
      certificate,
    };
  },
  view: (data) => view(data),
};

function columnRowsLink(data, columnId, label) {
  const matched = data.index.matchedRow(columnId);
  const target = matched ?? data.index.incidentRows(columnId)[0];
  if (!target) return label;
  const pattern = data.scope === "job" ? "/job/{jid}/row/{row}" : "/rev/{rid}/row/{row}";
  const values = data.scope === "job" ? { jid: data.owner, row: target } : { rid: data.owner, row: target };
  return h("a", { href: link(pattern, values, { column: columnId }) }, label);
}

function incidentSection(data) {
  if (!data.column) return null;
  const rows = data.index.incidentRows(data.column);
  const matched = data.index.matchedRow(data.column);
  return section(
    `Rows incident on ${data.column}`,
    rows.length === 0
      ? none("no row of the index is incident on this column")
      : h(
          "ol",
          { "data-ofs-incident": data.column },
          rows.map((rowId) =>
            h(
              "li",
              null,
              rowLink(data.scope, data.owner, rowId),
              rowId === matched ? h("small", { class: "muted" }, " (matched to the column)") : null,
            ),
          ),
        ),
  );
}

export function view(data) {
  const links = data.scope === "job" ? runLinks(data.owner) : [h("a", { href: link("/rev/{rid}/validation", { rid: data.owner }) }, "validation and DOF")];
  const head = heading(`Equation ${data.row}`, ...links);
  if (!data.consistent) {
    return h(
      "div",
      { "data-ofs-screen": "equation" },
      head,
      h("p", { class: "notice", "data-ofs-guard": "1" }, GUARD_TEXT),
    );
  }
  const row = data.index.row(data.row);
  if (row === null) {
    return h(
      "div",
      { "data-ofs-screen": "equation" },
      head,
      incidentSection(data),
      section("Equation", none("no such row in the structure index of this revision")),
    );
  }
  const variables = data.state?.document?.variables ?? null;
  const matchedColumn = data.index.matchedColumn(row.row_id);
  const block = data.index.block(row.row_id);
  const dof = data.index.unitDof(row.instance_id);
  const certificates = data.index.certificatesWith(row.row_id);
  const checks = data.certificate ? checksForSubject(data.certificate.document, row.row_id) : [];
  const atRun = data.scope === "job";
  return h(
    "div",
    { "data-ofs-screen": "equation" },
    head,
    data.state ? digestBanner("solution-state.json", data.state.digest) : null,
    incidentSection(data),
    section(
      "Equation",
      facts([
        ["row", id(row.row_id)],
        ["instance", id(row.instance_id)],
        ["unit", id(row.unit_id)],
        ["role", text(row.role)],
        [
          "specification",
          row.specification_id && data.revisionId
            ? h("a", { href: link("/rev/{rid}", { rid: data.revisionId }) }, id(row.specification_id))
            : text(row.specification_id),
        ],
        ["residual kind", text(row.kind)],
        ["residual unit (SI)", text(row.si_unit)],
        ["candidate specification row", data.index.isCandidateRow(row.row_id) ? "yes" : "no"],
      ]),
    ),
    section(
      "Incidence",
      table(
        [
          "column",
          "kind",
          "SI unit",
          "owner",
          "connection",
          "coordinate",
          "component",
          ...(atRun ? [{ text: "value", num: true }] : []),
          "rows",
        ],
        (row.columns ?? []).map((columnId) => {
          const column = data.index.column(columnId);
          const matched = columnId === matchedColumn;
          return h(
            "tr",
            matched ? { class: "selected", "aria-selected": "true", "data-ofs-matched": "1" } : null,
            [
              id(columnId),
              text(column?.kind),
              text(column?.si_unit),
              id(column?.owner_instance),
              text(column?.connection),
              text(column?.coordinate),
              text(column?.component),
              ...(atRun ? [variables === null ? "no state recorded" : numCell(variables[columnId])] : []),
              columnRowsLink(data, columnId, "rows"),
            ].map((cell) => (isTree(cell) && cell.t === "td" ? cell : h("td", null, cell))),
          );
        }),
      ),
      matchedColumn ? h("p", { class: "muted" }, `matched column (canonical matching): ${matchedColumn}`) : h("p", { class: "muted" }, "no column is matched to this row"),
    ),
    section(
      "Block-triangular form",
      block === null
        ? none("not in a recorded block")
        : facts([
            ["block", num(block.index)],
            ["size", num(block.size)],
            ["depends on", (block.depends_on ?? []).join(", ") || DASH],
          ]),
    ),
    section(
      "Redundancy certificates naming this row",
      table(
        ["certified row", "kind", "equals"],
        certificates.map((certificate) => [
          rowLink(data.scope, data.owner, certificate.row_id),
          text(certificate.kind),
          (certificate.equals ?? []).map(([rowId, sign]) => `${sign > 0 ? "+" : "−"}${rowId}`).join(" "),
        ]),
      ),
    ),
    section(
      "Unit degrees of freedom",
      dof === null
        ? none()
        : facts([
            ["instance", id(dof.instance_id)],
            ["columns", num(dof.columns)],
            ["model rank", num(dof.model_rank)],
            ["DOF", num(dof.degrees_of_freedom)],
            ["specifications", num(dof.specifications)],
            ["over-specified", dof.over_specified ? pill("over_specified") : "no"],
            ["local excess", num(dof.local_excess)],
          ]),
    ),
    atRun
      ? section(
          "Certificate checks on this row",
          data.certificate === null
            ? none("no certificate recorded for this run")
            : table(
                [
                  "check",
                  { text: `value (${row.si_unit ?? DASH})`, num: true },
                  { text: "reference", num: true },
                  { text: "scaled", num: true },
                  { text: "tolerance", num: true },
                  "result",
                  "near-threshold",
                ],
                checks.map((check) => [
                  id(check.id),
                  numCell(check.value),
                  numCell(check.reference),
                  numCell(scaledResidual(check)),
                  numCell(check.tolerance),
                  pill(check.result),
                  check.near_threshold === true ? pill("near_threshold") : DASH,
                ]),
              ),
        )
      : null,
  );
}
