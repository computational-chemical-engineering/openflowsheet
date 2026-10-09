// #/compare/rev/{a}/{b} — revision comparison (M06 design note §6.7).
//
// Reads `diff_revisions(a, b)` and both revisions whole. Shows the server's coarse
// added/removed/changed members and its element detail; for each changed path, the before and
// after values are read from the two revisions by element id and path tokens — the browser
// diffs nothing. A coarse change with no element entry reads "order changed only".

import { h } from "../h.js";
import { ABSENT, revisionComparison } from "../model/compare.js";
import { link } from "../router.js";
import { DASH } from "../text.js";
import { heading, id, none, numCell, revisionLink, section, table, text } from "./common.js";

export const name = "compare-revisions";
export const pattern = "/compare/rev/{a}/{b}";

export async function load(params, api) {
  const { a, b, signal } = params;
  const diff = await api.call("diff_revisions", { from_revision: a, to_revision: b }, { signal });
  const before = await api.readWhole("get_revision", { revision_id: a }, { signal });
  const after = await api.readWhole("get_revision", { revision_id: b }, { signal });
  return { a, b, diff, before, after, go: params.go };
}

function valueCell(value) {
  if (value === ABSENT) return h("td", { class: "muted" }, "absent");
  if (typeof value === "number") return numCell(value);
  return h("td", null, value !== null && typeof value === "object" ? JSON.stringify(value) : String(value));
}

function picker(data) {
  const onSubmit = (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const a = form.elements.namedItem("a").value.trim();
    const b = form.elements.namedItem("b").value.trim();
    if (a && b) data.go(link("/compare/rev/{a}/{b}", { a, b }));
  };
  return h(
    "form",
    { class: "pair", "data-ofs-form": "compare revisions", on: { submit: onSubmit } },
    h("label", { for: "ofs-compare-a" }, "revision a "),
    h("input", { id: "ofs-compare-a", name: "a", type: "text", value: data.a }),
    h("label", { for: "ofs-compare-b" }, " revision b "),
    h("input", { id: "ofs-compare-b", name: "b", type: "text", value: data.b }),
    h("button", { type: "submit" }, "compare"),
  );
}

function members(list) {
  return list.length === 0 ? DASH : list.join(", ");
}

export function view(data) {
  const comparison = revisionComparison(data.diff, data.before, data.after);
  return h(
    "div",
    { "data-ofs-screen": "compare-revisions" },
    heading(`Revision comparison`, revisionLink(data.a), revisionLink(data.b)),
    section("Revisions", picker(data)),
    section(
      "Members (server's diff)",
      table(
        ["added", "removed", "changed"],
        [[members(comparison.added), members(comparison.removed), members(comparison.changed)]],
      ),
      comparison.orderOnly.length === 0
        ? null
        : h(
            "ul",
            null,
            comparison.orderOnly.map((member) =>
              h("li", { "data-ofs-order-only": member }, `${member}: order changed only`),
            ),
          ),
    ),
    section(
      "Elements",
      comparison.elements.length === 0
        ? none("no element-level changes recorded")
        : table(
            ["member", "id", "change", "path", { text: `before (${data.a})`, num: true }, { text: `after (${data.b})`, num: true }],
            comparison.elements.flatMap((element) =>
              element.paths.length === 0
                ? [[text(element.member), id(element.id), text(element.change), DASH, h("td", null, DASH), h("td", null, DASH)]]
                : element.paths.map((entry) => [
                    text(element.member),
                    id(element.id),
                    text(element.change),
                    entry.path.join(" › "),
                    valueCell(entry.before),
                    valueCell(entry.after),
                  ]),
            ),
          ),
    ),
  );
}
