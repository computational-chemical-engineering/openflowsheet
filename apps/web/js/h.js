// The shell's only way to make DOM (M06 design note §5.1, ADR 0030 D1).
//
// `h(tag, props, ...children)` returns a plain tree `{t, p, c}`; a text child stays a string.
// `mount(tree, parent)` turns a tree into nodes under `parent`. Text reaches the document only
// through `document.createTextNode(sanitize(text))`; attributes only from the whitelists below,
// with sanitized string values; `href` only as a `#` fragment; event handlers only on
// interactive elements. There is no way through here to write markup, a style, a source URL or
// an inline handler, and `h` refuses anything else by throwing, so a mistake fails a Node test
// instead of reaching a browser. `view()` functions return trees, so they run in Node too.

import { sanitize } from "./text.js";

export const SVG_NS = "http://www.w3.org/2000/svg";

const HTML_TAGS = new Set([
  "a", "abbr", "article", "aside", "br", "button", "caption", "code", "col", "colgroup", "dd",
  "details", "dialog", "div", "dl", "dt", "em", "fieldset", "footer", "form", "h1", "h2", "h3",
  "h4", "header", "hr", "input", "kbd", "label", "legend", "li", "main", "nav", "ol", "option",
  "output", "p", "pre", "section", "select", "small", "span", "strong", "sub", "summary", "sup",
  "table", "tbody", "td", "textarea", "tfoot", "th", "thead", "time", "tr", "ul",
]);
const SVG_TAGS = new Set(["svg", "g", "defs", "marker", "path", "rect", "line", "polyline", "text"]);

const HTML_ATTRIBUTES = new Set([
  "class", "id", "title", "href", "role", "tabindex", "type", "value", "disabled", "colspan",
  "rowspan", "scope", "for", "name", "checked", "selected", "autocomplete",
]);
const SVG_ATTRIBUTES = new Set([
  "class", "id", "role", "viewBox", "x", "y", "x1", "y1", "x2", "y2", "width", "height", "d", "rx",
  "points", "transform", "text-anchor", "marker-end", "refX", "refY", "markerWidth",
  "markerHeight", "orient",
]);
const BOOLEAN_ATTRIBUTES = new Set(["disabled", "checked", "selected"]);
const PREFIXED = /^(aria|data)-[a-z][a-z0-9-]*$/;

const EVENT_ELEMENTS = new Set(["button", "a", "input", "select", "textarea", "form", "summary"]);
const EVENTS = new Set(["click", "change", "input", "keydown", "submit"]);

function refuse(message) {
  throw new Error(`h: ${message}`);
}

function checkProps(tag, props) {
  const svg = SVG_TAGS.has(tag);
  for (const [name, value] of Object.entries(props)) {
    if (name === "on") {
      if (!EVENT_ELEMENTS.has(tag)) refuse(`no event handler on <${tag}>`);
      for (const [event, handler] of Object.entries(value ?? {})) {
        if (!EVENTS.has(event)) refuse(`event ${event} is not allowed`);
        if (typeof handler !== "function") refuse(`the ${event} handler is not a function`);
      }
      continue;
    }
    const allowed = svg ? SVG_ATTRIBUTES : HTML_ATTRIBUTES;
    if (!allowed.has(name) && !PREFIXED.test(name)) refuse(`attribute ${name} on <${tag}>`);
    if (name === "href" && value != null && !String(value).startsWith("#")) {
      refuse("href is a # fragment");
    }
    if (value !== null && value !== undefined && typeof value === "object") {
      refuse(`attribute ${name} is an object`);
    }
  }
}

function children(list, into) {
  for (const child of list) {
    if (child === null || child === undefined || child === false || child === true) continue;
    if (Array.isArray(child)) children(child, into);
    else if (typeof child === "string") into.push(child);
    else if (typeof child === "number" || typeof child === "bigint") into.push(String(child));
    else if (typeof child === "object" && typeof child.t === "string") into.push(child);
    else refuse(`a child of type ${typeof child}`);
  }
  return into;
}

// A tree node. `props` may be null; children may be strings, numbers, trees, arrays of them,
// or null/undefined/booleans (skipped, for conditional children).
export function h(tag, props, ...kids) {
  if (!HTML_TAGS.has(tag) && !SVG_TAGS.has(tag)) refuse(`element <${tag}> is not allowed`);
  const p = { ...(props ?? {}) };
  checkProps(tag, p);
  return { t: tag, p, c: children(kids, []) };
}

// All text of a tree, concatenated, as `mount` would render it (for tests and titles).
export function textOf(tree) {
  if (typeof tree === "string") return sanitize(tree);
  return tree.c.map(textOf).join("");
}

function create(tree, document, inSvg) {
  if (typeof tree === "string") return document.createTextNode(sanitize(tree));
  const svg = inSvg || tree.t === "svg";
  const node = svg ? document.createElementNS(SVG_NS, tree.t) : document.createElement(tree.t);
  for (const [name, value] of Object.entries(tree.p)) {
    if (name === "on") {
      for (const [event, handler] of Object.entries(value ?? {})) {
        node.addEventListener(event, handler);
      }
    } else if (BOOLEAN_ATTRIBUTES.has(name)) {
      if (value) node.setAttribute(name, "");
    } else if (value !== null && value !== undefined && value !== false) {
      node.setAttribute(name, sanitize(String(value)));
    }
  }
  for (const child of tree.c) node.appendChild(create(child, document, svg));
  return node;
}

// Append the nodes of `tree` to `parent`; returns the created node.
export function mount(tree, parent) {
  const document = parent.ownerDocument;
  return parent.appendChild(create(tree, document, parent.namespaceURI === SVG_NS));
}

// Replace everything under `parent` with `tree`.
export function replace(tree, parent) {
  parent.replaceChildren();
  return mount(tree, parent);
}
