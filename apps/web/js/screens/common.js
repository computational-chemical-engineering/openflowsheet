// What the screens share (M06 design note §5.4, §5.5, §6): the page sizes they ask for, the
// reads several screens make (every page of a list, a run's bundle and its members), and the
// view pieces every screen draws the same way — numbers, ids, links, pills, empty sections,
// the digest banner, a JSON tree. Loads take `api` (js/api.js); views stay pure trees.

import { h } from "../h.js";
import { link } from "../router.js";
import { DASH, fmt, pill } from "../text.js";

// The page sizes the screens ask for; scripts/m06_web_fixtures.py records the same requests.
export const PAGE = Object.freeze({
  revisions: 200,
  projectJobs: 50,
  jobs: 200,
  events: 500,
  audit: 200,
});
// §6: the project screen reads at most 50 pages of revisions.
export const MAX_PAGES = 50;
export const TERMINAL = new Set(["completed", "failed", "cancelled", "timed_out"]);

// ------------------------------------------------------------------------------------ reads

// Every item of a cursor-paged list, at most `max` pages: `{items, complete}`.
export async function allPages(api, name, args, { signal, max = MAX_PAGES } = {}) {
  const items = [];
  let cursor = null;
  for (let pages = 0; pages < max; pages += 1) {
    const page = await api.call(name, cursor === null ? args : { ...args, cursor }, { signal });
    items.push(...page.items);
    if (page.next_cursor === null || page.next_cursor === undefined) {
      return { items, complete: true };
    }
    cursor = page.next_cursor;
  }
  return { items, complete: false };
}

// Every event of a job (`list_job_events`, continued by `after_sequence`).
export async function allEvents(api, jobId, { signal } = {}) {
  const items = [];
  let after = -1;
  for (;;) {
    const page = await api.call(
      "list_job_events",
      { job_id: jobId, after_sequence: after, limit: PAGE.events },
      { signal },
    );
    items.push(...page.items);
    if (page.next_cursor === null || page.next_cursor === undefined) return items;
    after = Number(page.next_cursor);
  }
}

// A run's result and bundle listing: `{result, run, bundle, listing, files}`. `run` is the
// result's `run_result` (null for a job that produced none); `bundle` the replay-bundle output
// (null without one); `files` the listing's members by name (empty without a bundle).
export async function runBundle(api, jobId, { signal } = {}) {
  const result = await api.call("get_job_result", { job_id: jobId }, { signal });
  const run = result.run_result ?? null;
  const bundle = (run?.outputs ?? []).find((output) => output.kind === "replay_bundle") ?? null;
  const listing = bundle
    ? await api.readWhole("get_artifact", { artifact_id: bundle.artifact_id }, { signal })
    : null;
  const files = new Map((listing?.files ?? []).map((member) => [member.name, member]));
  return { result, run, bundle, listing, files };
}

// Bundle member `name` read whole and digest-checked: `{name, member, document, digest}`, or
// null when the bundle has no such member.
export async function readMember(api, bundle, name, { signal } = {}) {
  const member = bundle.files.get(name);
  if (!member) return null;
  const read = await api.rawJson(member.artifact_id, member.sha256, { signal });
  return { name, member, document: read.document, digest: read.digest };
}

// ------------------------------------------------------------------------------------ views

// §5.5's global number mode: "short" or "full". Set by the frame's toggle before a render.
let numberMode = "short";
export function setNumberMode(mode) {
  numberMode = mode === "full" ? "full" : "short";
}
export function getNumberMode() {
  return numberMode;
}

// A numeric table cell: right-aligned, the current mode's text, the full value as its title.
export function numCell(x) {
  const full = x === null || x === undefined ? DASH : String(x);
  return h("td", { class: "num", title: full }, fmt(x, numberMode));
}

// A number in running text, with the full value as its title.
export function num(x) {
  return h("span", { class: "num", title: x === null || x === undefined ? DASH : String(x) }, fmt(x, numberMode));
}

// An id in monospace, cut by CSS with the whole id as its title.
export function id(text) {
  if (text === null || text === undefined) return DASH;
  return h("span", { class: "id", title: String(text) }, String(text));
}

export function revisionLink(revisionId, suffix = "") {
  if (!revisionId) return DASH;
  return h("a", { href: link(`/rev/{rid}${suffix}`, { rid: revisionId }) }, id(revisionId));
}

export function jobLink(jobId, suffix = "") {
  if (!jobId) return DASH;
  return h("a", { href: link(`/job/{jid}${suffix}`, { jid: jobId }) }, id(jobId));
}

export function rowLink(scope, owner, rowId, label = rowId) {
  const pattern = scope === "job" ? "/job/{jid}/row/{row}" : "/rev/{rid}/row/{row}";
  const values = scope === "job" ? { jid: owner, row: rowId } : { rid: owner, row: rowId };
  return h("a", { href: link(pattern, values) }, id(label));
}

export { pill };

// A table: `headers` are strings or `{text, num: true}`; `rows` are arrays of cells (a `td`
// tree, or anything a `td` may hold). An empty body reads `empty`.
export function table(headers, rows, { empty = "none recorded", caption = null, attrs = {} } = {}) {
  const head = h(
    "tr",
    null,
    headers.map((header) =>
      typeof header === "string"
        ? h("th", { scope: "col" }, header)
        : h("th", { scope: "col", class: header.num ? "num" : null }, header.text),
    ),
  );
  const body =
    rows.length === 0
      ? [h("tr", null, h("td", { colspan: String(headers.length), class: "muted" }, empty))]
      : rows.map((row) =>
          Array.isArray(row)
            ? h("tr", null, row.map((cell) => (cell && cell.t === "td" ? cell : h("td", null, cell))))
            : row,
        );
  return h(
    "table",
    attrs,
    caption ? h("caption", null, caption) : null,
    h("thead", null, head),
    h("tbody", null, body),
  );
}

// A titled panel.
export function section(title, ...children) {
  return h("section", { class: "panel" }, h("h2", null, title), ...children);
}

// The text every empty section reads.
export const NONE = "none recorded";
export function none(text = NONE) {
  return h("p", { class: "muted", "data-ofs-empty": "1" }, text);
}

// A term/description list from `[term, value]` pairs.
export function facts(pairs) {
  return h(
    "dl",
    { class: "facts" },
    pairs.map(([term, value]) =>
      h("div", null, h("dt", null, term), h("dd", null, value ?? DASH)),
    ),
  );
}

// §5.3: the digest of a record read through the raw export, as a banner above it.
export function digestBanner(name, digest) {
  if (digest === "match") return null;
  if (digest === "mismatch") {
    return h(
      "p",
      { class: "notice notice-bad", role: "alert", "data-ofs-digest": "mismatch" },
      `${name}: its bytes do not have the SHA-256 the bundle listing registers.`,
    );
  }
  return h(
    "p",
    { class: "notice", "data-ofs-digest": "unchecked" },
    `${name}: SHA-256 unchecked (this page is not a secure context).`,
  );
}

// The screen's title line: a heading and, optionally, links to related screens.
export function heading(title, ...links) {
  return h(
    "header",
    { class: "screen-head" },
    h("h1", null, title),
    links.length > 0 ? h("nav", { class: "screen-links" }, links) : null,
  );
}

// The sub-screens of a run, for its heading.
export function runLinks(jobId) {
  return [
    h("a", { href: link("/job/{jid}", { jid: jobId }) }, "run"),
    h("a", { href: link("/job/{jid}/certificate", { jid: jobId }) }, "certificate"),
    h("a", { href: link("/job/{jid}/failure", { jid: jobId }) }, "failure bundle"),
    h("a", { href: link("/job/{jid}/streams", { jid: jobId }) }, "streams and units"),
  ];
}

// A JSON value as a tree: the top level shown, every nested object or array a closed
// `<details>` (h.js has no `open` attribute: §5.1's whitelist), leaves as text.
export function jsonTree(value) {
  return h("div", { class: "json-tree" }, node(value, null, true));
}

function leaf(value) {
  if (typeof value === "number") return num(value);
  if (typeof value === "string") return h("span", { class: "json-string" }, JSON.stringify(value));
  return h("span", { class: "json-literal" }, String(value));
}

function node(value, label, top = false) {
  const key = label === null ? null : h("span", { class: "json-key" }, `${label}: `);
  if (value === null || typeof value !== "object") {
    return h("div", { class: "json-leaf" }, key, leaf(value));
  }
  const entries = Array.isArray(value)
    ? value.map((item, index) => [String(index), item])
    : Object.entries(value);
  const summary = Array.isArray(value) ? `[${entries.length}]` : `{${entries.length}}`;
  const children = entries.map(([name, item]) => node(item, name));
  if (top) return h("div", { class: "json-node" }, h("div", null, key, summary), children);
  return h("details", { class: "json-node" }, h("summary", null, key, summary), children);
}

// A recorded value as text, or "—" when it is absent or empty.
export function text(value) {
  if (value === null || value === undefined || value === "") return DASH;
  return String(value);
}
