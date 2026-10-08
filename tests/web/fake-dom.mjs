// A minimal DOM for Node tests of `mount`: elements, text nodes, attributes, listeners. It
// records exactly what `h.js` asks of a document and has no way to parse markup.

class FakeNode {
  constructor(document) {
    this.ownerDocument = document;
    this.childNodes = [];
    this.parentNode = null;
  }

  appendChild(child) {
    child.parentNode = this;
    this.childNodes.push(child);
    return child;
  }

  replaceChildren(...nodes) {
    this.childNodes = [];
    for (const node of nodes) this.appendChild(node);
  }

  get textContent() {
    return this.childNodes.map((child) => child.textContent).join("");
  }
}

export class FakeText extends FakeNode {
  constructor(document, data) {
    super(document);
    this.nodeType = 3;
    this.data = data;
  }

  get textContent() {
    return this.data;
  }
}

export class FakeElement extends FakeNode {
  constructor(document, tagName, namespaceURI) {
    super(document);
    this.nodeType = 1;
    this.tagName = tagName;
    this.namespaceURI = namespaceURI;
    this.attributes = new Map();
    this.listeners = new Map();
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }

  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }

  addEventListener(event, handler) {
    if (!this.listeners.has(event)) this.listeners.set(event, []);
    this.listeners.get(event).push(handler);
  }

  dispatch(event, detail = {}) {
    for (const handler of this.listeners.get(event) ?? []) handler({ type: event, ...detail });
  }
}

export const HTML_NS = "http://www.w3.org/1999/xhtml";

export class FakeDocument {
  constructor() {
    this.created = [];
    this.body = new FakeElement(this, "body", HTML_NS);
  }

  createElement(tagName) {
    const node = new FakeElement(this, tagName, HTML_NS);
    this.created.push(node);
    return node;
  }

  createElementNS(namespaceURI, tagName) {
    const node = new FakeElement(this, tagName, namespaceURI);
    this.created.push(node);
    return node;
  }

  createTextNode(data) {
    return new FakeText(this, data);
  }
}
