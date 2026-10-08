// Queries over the plain trees `h` builds (`{t, p, c}`; text leaves are strings), for view tests.

import { textOf } from "../../apps/web/js/h.js";

export { textOf };

// Every node of `tree` (depth first) for which `match(node)` holds.
export function findAll(tree, match) {
  const out = [];
  const walk = (node) => {
    if (typeof node === "string") return;
    if (match(node)) out.push(node);
    for (const child of node.c) walk(child);
  };
  walk(tree);
  return out;
}

export function byTag(tree, tag) {
  return findAll(tree, (node) => node.t === tag);
}

export function byAttr(tree, name, value) {
  return findAll(tree, (node) => node.p[name] !== undefined && (value === undefined || node.p[name] === value));
}

export function hrefs(tree) {
  return byTag(tree, "a").map((node) => node.p.href);
}

// Every status pill of the tree: `{tone, glyph, word}`, asserting each carries glyph and word.
export function pills(tree) {
  return findAll(tree, (node) => typeof node.p.class === "string" && /(^| )pill( |$)/.test(node.p.class)).map(
    (node) => {
      const [glyph, word] = node.c;
      if (!glyph || !word || glyph.p.class !== "pill-glyph" || word.p.class !== "pill-word") {
        throw new Error(`a pill without glyph and word: ${JSON.stringify(node)}`);
      }
      return { tone: node.p["data-tone"], glyph: textOf(glyph), word: textOf(word) };
    },
  );
}

// The text of each row of the first table under `tree` whose header row includes `header`.
export function tableRows(tree, header) {
  const tables = byTag(tree, "table").filter((table) =>
    byTag(table, "th").some((th) => textOf(th).startsWith(header)),
  );
  if (tables.length === 0) throw new Error(`no table with a ${header} column`);
  return byTag(byTag(tables[0], "tbody")[0], "tr").map((tr) =>
    tr.c.filter((cell) => typeof cell !== "string").map((cell) => textOf(cell)),
  );
}
