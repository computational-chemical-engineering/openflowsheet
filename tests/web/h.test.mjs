// M06 WO-5: the DOM builder (design note §5.1). `h` builds plain trees and refuses anything
// outside its whitelists; `mount` makes text nodes of sanitized text only.

import { test } from "node:test";
import assert from "node:assert/strict";

import { h, mount, replace, SVG_NS, textOf } from "../../apps/web/js/h.js";
import { FakeDocument, HTML_NS } from "./fake-dom.mjs";

test("h returns a plain tree; strings stay strings, numbers become text, nulls vanish", () => {
  const tree = h("td", { class: "num", title: "1.5" }, "a", 2, null, undefined, false, [
    "b",
    h("span", null, "c"),
  ]);
  assert.deepEqual(tree, {
    t: "td",
    p: { class: "num", title: "1.5" },
    c: ["a", "2", "b", { t: "span", p: {}, c: ["c"] }],
  });
  assert.equal(textOf(tree), "a2bc");
});

test("h refuses elements, attributes and links outside the whitelists", () => {
  for (const tag of ["script", "style", "iframe", "img", "object", "embed", "link", "base"]) {
    assert.throws(() => h(tag, null), /not allowed/, tag);
  }
  for (const name of ["style", "src", "onclick", "onerror", "innerHTML", "srcdoc", "action"]) {
    assert.throws(() => h("div", { [name]: "x" }), /attribute/, name);
  }
  assert.throws(() => h("a", { href: "javascript:alert(1)" }), /# fragment/);
  assert.throws(() => h("a", { href: "https://example.org/" }), /# fragment/);
  assert.throws(() => h("a", { href: "/v1/project" }), /# fragment/);
  assert.doesNotThrow(() => h("a", { href: "#/rev/rev-000001" }));
  assert.throws(() => h("div", { title: { toString: () => "x" } }), /object/);
  assert.throws(() => h("div", null, { toString: () => "<b>" }), /child/);
  assert.throws(() => h("div", { "data-X": "1" }), /attribute/);
  assert.doesNotThrow(() => h("div", { "data-ofs-ready": "1", "aria-label": "x", role: "row" }));
});

test("event handlers only on interactive elements and only the five events", () => {
  const click = () => {};
  for (const tag of ["button", "a", "input", "select", "textarea", "form", "summary"]) {
    assert.doesNotThrow(() => h(tag, { on: { click } }), tag);
  }
  for (const tag of ["div", "span", "td", "tr", "svg", "rect"]) {
    assert.throws(() => h(tag, { on: { click } }), /no event handler/, tag);
  }
  assert.throws(() => h("button", { on: { mouseover: click } }), /not allowed/);
  assert.throws(() => h("button", { on: { click: "alert(1)" } }), /not a function/);
});

test("SVG elements take the SVG attribute list and nothing from HTML's event rules", () => {
  assert.doesNotThrow(() =>
    h(
      "svg",
      { viewBox: "0 0 10 10", width: 10, height: 10 },
      h("rect", { x: 1, y: 1, width: 4, height: 4, rx: 1 }),
      h("path", { d: "M0 0L1 1", "marker-end": "url-free" }),
    ),
  );
  assert.throws(() => h("rect", { href: "#x" }), /attribute/);
  assert.throws(() => h("svg", { onload: "x" }), /attribute/);
});

test("mount creates elements, sanitized text nodes and sanitized attributes", () => {
  const document = new FakeDocument();
  const evil = "<img src=x onerror=alert(1)>‮evil";
  const clicked = [];
  const node = mount(
    h(
      "div",
      { class: "panel", title: evil, "data-id": "a\u0000b" },
      h("h1", null, evil),
      h("button", { type: "button", disabled: false, on: { click: () => clicked.push(1) } }, "Go"),
      h("input", { type: "checkbox", checked: true }),
    ),
    document.body,
  );
  assert.equal(node.tagName, "div");
  assert.equal(node.namespaceURI, HTML_NS);
  assert.equal(node.getAttribute("title"), "<img src=x onerror=alert(1)>�evil");
  assert.equal(node.getAttribute("data-id"), "a�b");
  const [heading, button, box] = node.childNodes;
  assert.equal(heading.childNodes.length, 1);
  assert.equal(heading.childNodes[0].nodeType, 3);
  assert.equal(heading.textContent, "<img src=x onerror=alert(1)>�evil");
  assert.equal(document.created.filter((n) => n.tagName === "img").length, 0);
  assert.equal(button.getAttribute("disabled"), null);
  button.dispatch("click");
  assert.deepEqual(clicked, [1]);
  assert.equal(box.getAttribute("checked"), "");
});

test("SVG trees are created in the SVG namespace, children included", () => {
  const document = new FakeDocument();
  const svg = mount(h("svg", { viewBox: "0 0 4 4" }, h("g", null, h("text", { x: 1 }, "S6"))), document.body);
  assert.equal(svg.namespaceURI, SVG_NS);
  assert.equal(svg.childNodes[0].namespaceURI, SVG_NS);
  assert.equal(svg.childNodes[0].childNodes[0].namespaceURI, SVG_NS);
  assert.equal(svg.textContent, "S6");
});

test("replace empties the parent first", () => {
  const document = new FakeDocument();
  mount(h("p", null, "old"), document.body);
  replace(h("p", null, "new"), document.body);
  assert.equal(document.body.childNodes.length, 1);
  assert.equal(document.body.textContent, "new");
});
