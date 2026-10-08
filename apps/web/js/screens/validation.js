// #/rev/{rid}/validation — validation and degrees of freedom (M06 design note §6.2).
//
// Reads `validate` (task "simulation") and `inspect_structure` whole. Shows the ordered checks
// and the structural report — the routed analysis, or for an unroutable revision the
// validation's report under its `not_run_reason` and `hint` — exactly as recorded: no
// arithmetic beyond display (Q1), every count and flag the server's.

import { h } from "../h.js";
import { reportOf, structureIndex } from "../model/structure.js";
import { link } from "../router.js";
import { DASH } from "../text.js";
import {
  facts,
  heading,
  id,
  jsonTree,
  none,
  num,
  numCell,
  pill,
  rowLink,
  section,
  table,
  text,
} from "./common.js";

export const name = "validation";
export const pattern = "/rev/{rid}/validation";

export async function load(params, api) {
  const { rid, signal } = params;
  const validation = await api.call(
    "validate",
    { revision_id: rid, task: "simulation" },
    { signal },
  );
  const structure = await api.readWhole("inspect_structure", { revision_id: rid }, { signal });
  return { rid, validation, structure };
}

// An implicated object: a specification links to its row's equation view, an instance to the
// revision overview, anything else is its id as text.
function implicated(rid, index, objectId) {
  const row = [...index.rows.values()].find((entry) => entry.specification_id === objectId);
  if (row) return rowLink("rev", rid, row.row_id, objectId);
  return h("a", { href: link("/rev/{rid}", { rid }) }, id(objectId));
}

function rowList(rid, rows) {
  if (!rows || rows.length === 0) return none();
  return h(
    "ul",
    { class: "inline-list" },
    rows.map((row) => h("li", null, rowLink("rev", rid, row))),
  );
}

function specificationList(rid, index, ids) {
  if (!ids || ids.length === 0) return none();
  return h(
    "ul",
    { class: "inline-list" },
    ids.map((objectId) => h("li", null, implicated(rid, index, objectId))),
  );
}

export function view(data) {
  const { rid, validation, structure } = data;
  const index = structureIndex(structure);
  const report = reportOf(structure);
  const btf = report?.block_triangular_form ?? null;
  return h(
    "div",
    { "data-ofs-screen": "validation" },
    heading(
      `Validation and degrees of freedom — ${rid}`,
      h("a", { href: link("/rev/{rid}", { rid }) }, "revision"),
    ),
    section(
      "Checks",
      h("p", null, "status: ", pill(validation.status), ` (task ${text(validation.task)})`),
      table(
        ["id", "stage", "result", "message", "implicated"],
        (validation.checks ?? []).map((check) => [
          id(check.id),
          text(check.stage),
          pill(check.result),
          text(check.message),
          (check.implicated_objects ?? []).length === 0
            ? DASH
            : h(
                "ul",
                { class: "inline-list" },
                check.implicated_objects.map((objectId) =>
                  h("li", null, implicated(rid, index, objectId)),
                ),
              ),
        ]),
      ),
      facts(
        Object.entries(validation.structural_counts ?? {}).map(([key, value]) => [key, num(value)]),
      ),
    ),
    report === null
      ? section("Structural report", none("no structural report recorded"))
      : reportSections(rid, index, structure, report, btf),
  );
}

function reportSections(rid, index, structure, report, btf) {
  return [
    section(
      index.routed ? "Structural report (routed analysis)" : "Structural report (validation)",
      index.routed
        ? null
        : h(
            "div",
            { class: "notice", "data-ofs-unroutable": "1" },
            h("p", null, "This revision has no solve route; the validation's analysis is shown."),
            h("p", null, "not run: ", text(structure.not_run_reason)),
            h("p", null, "hint: ", text(structure.hint)),
          ),
      facts([
        ["finding", text(report.finding)],
        ["excess", num(report.excess)],
        ["deficit", num(report.deficit)],
        ["model version", id(report.model_version)],
        ["nnz", num(report.nnz)],
      ]),
    ),
    section(
      "Certified redundant rows",
      table(
        ["row", "kind", "equals", { text: "tolerance", num: true }, "consistent"],
        (report.certificates ?? []).map((certificate) => [
          rowLink("rev", rid, certificate.row_id),
          text(certificate.kind),
          h(
            "ul",
            { class: "inline-list" },
            (certificate.equals ?? []).map(([row, sign]) =>
              h("li", null, `${sign > 0 ? "+" : "−"} `, rowLink("rev", rid, row)),
            ),
          ),
          numCell(certificate.tolerance),
          text(certificate.consistent),
        ]),
      ),
    ),
    section(
      "Candidates",
      h("h3", null, "Candidate specifications"),
      specificationList(rid, index, report.candidate_specifications),
      h("h3", null, "Candidate specification rows"),
      rowList(rid, report.candidate_specification_rows),
    ),
    section(
      "Unit degrees of freedom",
      table(
        [
          "instance",
          { text: "columns", num: true },
          { text: "model rank", num: true },
          { text: "DOF", num: true },
          { text: "specifications", num: true },
          "over-specified",
          { text: "local excess", num: true },
        ],
        (report.unit_degrees_of_freedom ?? []).map((unit) => [
          id(unit.instance_id),
          numCell(unit.columns),
          numCell(unit.model_rank),
          numCell(unit.degrees_of_freedom),
          numCell(unit.specifications),
          unit.over_specified ? pill("over_specified") : "no",
          numCell(unit.local_excess),
        ]),
      ),
    ),
    section(
      "Block-triangular form",
      btf === null
        ? none("not recorded")
        : facts([
            ["block count", num(btf.block_count)],
            ["sizes (sorted)", (btf.block_sizes_sorted ?? []).join(", ") || DASH],
            ["largest block fraction", num(btf.largest_block_fraction)],
          ]),
    ),
    section("Tear", report.tear ? jsonTree(report.tear) : none("not recorded")),
    section(
      "Unsupported",
      table(
        ["kind", "detail"],
        (report.unsupported ?? []).map((entry) => [text(entry.kind), text(entry.detail)]),
      ),
    ),
  ];
}
