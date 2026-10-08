// M06 WO-6: the header, the error panel, the not-found screen.

import { test } from "node:test";
import assert from "node:assert/strict";

import { textOf } from "../../apps/web/js/h.js";
import { ApiError } from "../../apps/web/js/api.js";
import { errorView, fatalText, headerView, nextTheme, notFoundView } from "../../apps/web/js/frame.js";

const PROJECT = {
  project_id: "m06-fixture",
  principal_id: "agent-a",
  capability_id: "cap-agent-a",
  rights: ["read", "execute", "draft"],
  server: { package_version: "0.2.0.dev0", git_commit: "0123456789abcdef0123", store_schema: "t07-store-v1" },
};

test("the header names project, principal, rights and server version", () => {
  const text = textOf(headerView(PROJECT, { theme: "dark", onTheme() {}, onSignOut() {} }));
  for (const part of ["OpenFlowsheet", "m06-fixture", "agent-a", "draft, execute, read", "0.2.0.dev0 (0123456789ab)", "theme: dark", "sign out"]) {
    assert.ok(text.includes(part), part);
  }
  const anonymous = textOf(headerView(null, { theme: "system" }));
  assert.ok(!anonymous.includes("sign out") && anonymous.includes("theme: system"));
});

test("the theme cycles system, light, dark", () => {
  assert.equal(nextTheme("system"), "light");
  assert.equal(nextTheme("light"), "dark");
  assert.equal(nextTheme("dark"), "system");
  assert.equal(nextTheme("bogus"), "system");
});

test("the error panel shows the server's ApiError as it came", () => {
  const error = new ApiError(404, {
    code: "not_found",
    message: "no revision rev-9",
    retryable: false,
    detail: { revision_id: "rev-9" },
  });
  const tree = errorView(error);
  assert.equal(tree.p.id, "ofs-error");
  assert.equal(tree.p["data-ofs-error-code"], "not_found");
  const text = textOf(tree);
  for (const part of ["not_found", "no revision rev-9", "HTTP 404", '"revision_id": "rev-9"']) {
    assert.ok(text.includes(part), part);
  }
  assert.ok(textOf(errorView(new Error("boom"))).includes("boom"));
});

test("an unknown route says so; fatal text names the error", () => {
  assert.ok(textOf(notFoundView("/nowhere")).includes("/nowhere"));
  assert.ok(fatalText(new TypeError("x is undefined")).startsWith("TypeError: x is undefined"));
  assert.equal(fatalText("plain"), "Uncaught: plain");
});
