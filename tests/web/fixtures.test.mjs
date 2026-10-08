// M06 WO-7: the W26 fixtures answer the shell's own `api.js` (design note §5.4, §8).
//
// Through the fixture transport, `readWhole` reassembles every projected document the screens
// read (each view a recorded server answer), and every raw record digest-checks against the
// SHA-256 the bundle listing registered. A request the fixtures do not hold fails.

import { test } from "node:test";
import assert from "node:assert/strict";

import { decodeRequest, FIXTURE, fixtureApi, JOB, REV } from "./fixture-transport.mjs";
import { buildRequest } from "../../apps/web/js/api.js";

test("a request api.js builds decodes back to its operation and members", () => {
  const cases = [
    ["get_revision", { revision_id: "rev-000001", pointer: "/a~1b", depth: 12, limit: 200 }],
    ["artifact_bytes", { artifact_id: "job-000001:bundle/solve-events.json" }],
    ["list_job_events", { job_id: "job-000001", after_sequence: -1, limit: 500 }],
    ["validate", { revision_id: "rev-000003", task: "simulation" }],
    ["diff_revisions", { from_revision: "rev-000001", to_revision: "rev-000002" }],
    ["list_audit", { order: "descending", limit: 200, principal_id: "agent-a" }],
  ];
  for (const [name, args] of cases) {
    const { url, init } = buildRequest(name, args, "t", undefined);
    assert.deepEqual(decodeRequest(url, init), { name, args });
  }
});

test("every revision, structure and bundle listing reads whole from the recorded views", async () => {
  const api = fixtureApi();
  for (const revision of Object.values(REV)) {
    const document = await api.readWhole("get_revision", { revision_id: revision });
    assert.equal(typeof document.title, "string");
    const structure = await api.readWhole("inspect_structure", { revision_id: revision });
    assert.ok(Array.isArray(structure.rows) && Array.isArray(structure.columns));
  }
  const net02 = await api.readWhole("inspect_structure", { revision_id: REV.NET02 });
  assert.equal(net02.rows.length, 48); // G4
  assert.equal(net02.columns.length, 47);
  for (const job of Object.values(JOB)) {
    const result = await api.call("get_job_result", { job_id: job });
    const bundle = result.run_result.outputs.find((output) => output.kind === "replay_bundle");
    const listing = await api.readWhole("get_artifact", { artifact_id: bundle.artifact_id });
    assert.ok(listing.files.length >= 10);
    for (const member of listing.files) {
      const read = await api.rawJson(member.artifact_id, member.sha256);
      assert.equal(read.digest, "match", member.artifact_id);
    }
  }
});

test("the hostile revision's text arrives as text, its U+202E replaced by the server", async () => {
  const api = fixtureApi();
  const document = await api.readWhole("get_revision", { revision_id: REV.hostile });
  assert.equal(document.title, "<img src=x onerror=alert(1)>�evil");
});

test("an unrecorded request fails, naming it", async () => {
  const api = fixtureApi();
  await assert.rejects(api.call("get_job", { job_id: "job-999999" }), /no record for get_job/);
});

test("a refusal is recorded per principal and arrives as the server's ApiError", async () => {
  const api = fixtureApi("viewer-b");
  await assert.rejects(api.call("list_audit", { order: "descending", limit: 200 }), (error) => {
    assert.equal(error.status, 403);
    assert.equal(error.code, "forbidden");
    return true;
  });
  assert.equal(FIXTURE.principals["supervisor-c"]["get_project {}"].body.principal_id, "supervisor-c");
});
