// M06 WO-6: hash routes (design note §6).

import { test } from "node:test";
import assert from "node:assert/strict";

import { link, matchRoute, parseHash, withoutToken } from "../../apps/web/js/router.js";

const ROUTES = [
  { name: "project", pattern: "/" },
  { name: "revision", pattern: "/rev/{rid}" },
  { name: "validation", pattern: "/rev/{rid}/validation" },
  { name: "file", pattern: "/job/{jid}/file/{name}" },
  { name: "compare-rev", pattern: "/compare/rev/{a}/{b}" },
];

test("parseHash splits the route path from its query", () => {
  const parsed = parseHash("#/history?principal=agent-a&x=1");
  assert.equal(parsed.path, "/history");
  assert.equal(parsed.params.get("principal"), "agent-a");
  assert.equal(parseHash("").path, "/");
  assert.equal(parseHash("#").path, "/");
  assert.equal(parseHash("#/").path, "/");
  assert.equal(parseHash("#rev/r1").path, "/rev/r1");
});

test("matchRoute matches whole patterns and decodes values", () => {
  assert.deepEqual(matchRoute(ROUTES, "/"), { name: "project", values: {} });
  assert.deepEqual(matchRoute(ROUTES, "/rev/rev-000001"), {
    name: "revision",
    values: { rid: "rev-000001" },
  });
  assert.deepEqual(matchRoute(ROUTES, "/rev/rev-000001/validation").name, "validation");
  assert.deepEqual(matchRoute(ROUTES, "/job/job-1/file/a%2Fb.json").values, {
    jid: "job-1",
    name: "a/b.json",
  });
  assert.equal(matchRoute(ROUTES, "/rev"), null);
  assert.equal(matchRoute(ROUTES, "/rev/"), null);
  assert.equal(matchRoute(ROUTES, "/rev/a/b/c"), null);
  assert.equal(matchRoute(ROUTES, "/rev/%E0%A4%A"), null);
});

test("link encodes values and query; withoutToken strips the boot token", () => {
  assert.equal(link("/rev/{rid}", { rid: "rev 1/2" }), "#/rev/rev%201%2F2");
  assert.equal(link("/compare/rev/{a}/{b}", { a: "x", b: "y" }, { n: null, k: 2 }), "#/compare/rev/x/y?k=2");
  assert.throws(() => link("/rev/{rid}", {}), /needs rid/);
  assert.equal(withoutToken("#/rev/r1?token=prt_secret&x=1"), "#/rev/r1?x=1");
  assert.equal(withoutToken("#/?token=prt_secret"), "#/");
  for (const entry of ROUTES) {
    const values = { rid: "r/1", jid: "j", name: "n", a: "a", b: "b" };
    const target = link(entry.pattern, values);
    assert.equal(matchRoute(ROUTES, parseHash(target).path).name, entry.name);
  }
});
