// M06 WO-6: the token store, the boot token, the sign-in view (design note §7).

import { test } from "node:test";
import assert from "node:assert/strict";

import { createTokenStore, loginView, takeBootToken, TOKEN_KEY } from "../../apps/web/js/auth.js";
import { textOf } from "../../apps/web/js/h.js";
import { withoutToken } from "../../apps/web/js/router.js";

function storage() {
  const items = new Map();
  return {
    items,
    getItem: (key) => (items.has(key) ? items.get(key) : null),
    setItem: (key, value) => items.set(key, String(value)),
    removeItem: (key) => items.delete(key),
  };
}

const refusing = {
  getItem() {
    throw new Error("SecurityError");
  },
  setItem() {
    throw new Error("QuotaExceededError");
  },
  removeItem() {
    throw new Error("SecurityError");
  },
};

test("the token lives in sessionStorage, and in localStorage only when remembered", () => {
  const session = storage();
  const local = storage();
  const tokens = createTokenStore({ session, local });
  assert.equal(tokens.get(), null);
  tokens.set("prt_a");
  assert.equal(session.items.get(TOKEN_KEY), "prt_a");
  assert.equal(local.items.has(TOKEN_KEY), false);
  tokens.set("prt_b", true);
  assert.equal(local.items.get(TOKEN_KEY), "prt_b");
  assert.equal(tokens.remembered(), true);
  tokens.set("prt_c", false);
  assert.equal(local.items.has(TOKEN_KEY), false, "un-ticking forgets the remembered copy");
  tokens.clear();
  assert.equal(tokens.get(), null);
  assert.equal(session.items.size + local.items.size, 0);
  // A remembered token from an earlier visit is found.
  local.setItem(TOKEN_KEY, "prt_old");
  assert.equal(createTokenStore({ session: storage(), local }).get(), "prt_old");
});

test("storage that refuses or is missing leaves the token in memory for the page", () => {
  for (const options of [{ session: refusing, local: refusing }, {}]) {
    const tokens = createTokenStore(options);
    assert.equal(tokens.get(), null);
    tokens.set("prt_x", true);
    assert.equal(tokens.get(), "prt_x");
    tokens.clear();
    assert.equal(tokens.get(), null);
  }
});

test("the boot token is stored and removed from the address", () => {
  const tokens = createTokenStore({ session: storage(), local: storage() });
  const replaced = [];
  const history = { replaceState: (state, title, url) => replaced.push(url) };
  const location = { pathname: "/ui/", search: "", hash: "#/rev/r1?token=prt_boot&x=1" };
  assert.equal(takeBootToken(location, history, tokens, withoutToken), true);
  assert.equal(tokens.get(), "prt_boot");
  assert.deepEqual(replaced, ["/ui/#/rev/r1?x=1"]);
  assert.equal(takeBootToken({ ...location, hash: "#/rev/r1" }, history, tokens, withoutToken), false);
  assert.equal(replaced.length, 1);
});

test("the sign-in view: a password field without autocomplete, remember opt-in, the message", () => {
  const submitted = [];
  const tree = loginView({ message: "token unknown", onSubmit: (...args) => submitted.push(args) });
  const nodes = [];
  const walk = (node) => {
    if (typeof node === "string") return;
    nodes.push(node);
    node.c.forEach(walk);
  };
  walk(tree);
  const field = nodes.find((node) => node.p.name === "token");
  assert.deepEqual([field.t, field.p.type, field.p.autocomplete], ["input", "password", "off"]);
  const remember = nodes.find((node) => node.p.name === "remember");
  assert.equal(remember.p.type, "checkbox");
  assert.equal(remember.p.checked, undefined);
  assert.ok(textOf(tree).includes("token unknown"));
  const form = nodes.find((node) => node.t === "form");
  let prevented = false;
  form.p.on.submit({
    preventDefault: () => (prevented = true),
    target: { elements: { token: { value: "  prt_typed  " }, remember: { checked: true } } },
  });
  assert.ok(prevented);
  assert.deepEqual(submitted, [["prt_typed", true]]);
});
