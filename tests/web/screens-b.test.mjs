// M06 WO-10: screens B on the W26 fixtures (design note §6.3, §6.5, §6.7, §6.8; G5, G6, G7).
//
// As screens A: each `load` runs against api.js over the recorded answers, each `view` is
// asserted on the plain tree. The live run (a job that has not ended) and the Cancel action use a
// stand-in API, since every fixture job has ended.

import { test } from "node:test";
import assert from "node:assert/strict";

import { body, fixtureApi, JOB, REV } from "./fixture-transport.mjs";
import { byAttr, byTag, hrefs, pills, tableRows, textOf } from "./tree.mjs";
import * as compareRevisions from "../../apps/web/js/screens/compare-revisions.js";
import * as compareRuns from "../../apps/web/js/screens/compare-runs.js";
import { GUARD_TEXT, jobRow, revisionRow } from "../../apps/web/js/screens/equation.js";
import * as file from "../../apps/web/js/screens/file.js";
import * as history from "../../apps/web/js/screens/history.js";
import * as job from "../../apps/web/js/screens/job.js";
import { mount } from "../../apps/web/js/h.js";
import { FakeDocument } from "./fake-dom.mjs";

async function render(screen, values, { principal = "agent-a", query = "", api = fixtureApi(principal), project } = {}) {
  const gone = [];
  const data = await screen.load(
    {
      ...values,
      query: new URLSearchParams(query),
      signal: undefined,
      project: project ?? body(principal, "get_project", {}),
      go: (hash) => gone.push(hash),
    },
    api,
  );
  const tree = screen.view(data);
  pills(tree);
  mount(tree, new FakeDocument().body);
  return { data, tree, text: textOf(tree), api, gone };
}

const calls = (api) => [...new Set(api.log.map((entry) => entry.name))];

// ------------------------------------------------------------------------------------ the run

test("G7: the NET-02 run — summary, 2 attempts with deltas and totals, 27 trace rows, files", async () => {
  const { tree, text, api, data } = await render(job, { jid: JOB.NET02 });
  assert.deepEqual(calls(api), ["get_job", "list_job_events", "get_job_result", "get_artifact", "artifact_bytes"]);
  assert.deepEqual(Object.keys(data.members), job.RUN_MEMBERS);
  assert.ok(Object.values(data.members).every((read) => read.digest === "match"));
  assert.ok(text.includes("revision_eo") && text.includes("T06-revision-v2"));
  const attempts = tableRows(tree, "step").slice(0, 2); // then "outside attempts" and totals
  assert.deepEqual(
    attempts.map((row) => [row[1], row[3], ...row.slice(-4)]),
    [
      ["0", "✕BOUND_BLOCKED", "54", "2", "2", "2"],
      ["1", "◐CONVERGED", "135", "7", "4", "4"],
    ],
  );
  assert.deepEqual(byAttr(tree, "data-ofs-row", "totals").map((tr) => tr.c.slice(1).map(textOf)), [["338", "9", "6", "6"]]);
  assert.deepEqual(byAttr(tree, "data-ofs-row", "outside").map((tr) => tr.c.slice(1).map(textOf)), [["149", "0", "0", "0"]]);
  const trace = tableRows(tree, "residual_inf_unscaled");
  assert.equal(trace.length, 27);
  assert.ok(text.includes("rows 1–27 of 27 (27 events)"));
  assert.equal(tableRows(tree, "name").length, data.bundle.listing.files.length);
  assert.ok(hrefs(tree).includes(`#/job/${JOB.NET02}/file/solve-events.json`));
  assert.equal(tableRows(tree, "opening source").length, 2); // the recovery path
  assert.equal(byAttr(tree, "data-ofs-action", "cancel").length, 0); // ended: no Cancel
  assert.equal(tree.p["data-ofs-live"], "0");
});

test("the trace filters by kind and attempt and pages the filtered rows", async () => {
  const { tree, text } = await render(job, { jid: JOB["A02-352"] }, { query: "kind=trial&attempt=4" });
  const rows = tableRows(tree, "residual_inf_unscaled");
  assert.ok(rows.length > 0 && rows.every((row) => row[1] === "trial" && row[2] === "4"));
  assert.ok(text.includes(`of ${rows.length} (249 events)`));
  assert.ok(hrefs(tree).includes(`#/job/${JOB["A02-352"]}?attempt=4`)); // "any kind" keeps the attempt
});

function liveApi(log) {
  const running = { ...body("agent-a", "get_job", { job_id: JOB.NET02 }), status: "running", ended_at: null };
  const events = body("agent-a", "list_job_events", { job_id: JOB.NET02, after_sequence: -1, limit: 500 }).items;
  return {
    async call(name, args) {
      log.push({ name, args });
      if (name === "get_job") return running;
      if (name === "list_job_events") return { items: events.slice(0, 3), next_cursor: null };
      if (name === "cancel_job") return { ...running, cancel_requested: true };
      throw new Error(`unexpected ${name}`);
    },
    async followJob(jobId, options) {
      log.push({ name: "followJob", args: { jobId, afterSequence: options.afterSequence } });
      options.onWait({ events: events.slice(3, 5), ended: false, job: running });
      options.onWait({ events: events.slice(5), ended: true, job: { ...running, status: "completed" } });
      return { ...running, status: "completed" };
    },
  };
}

test("a live run follows wait_job from its last event, draws each answer, then reloads", async () => {
  const log = [];
  const { tree, data, gone } = await render(job, { jid: JOB.NET02 }, { api: liveApi(log) });
  assert.equal(tree.p["data-ofs-live"], "1");
  assert.ok(textOf(tree).includes("Job events (live)"));
  assert.equal(byAttr(tree, "data-ofs-action", "cancel")[0].p.disabled, undefined);
  const drawn = [];
  await job.follow(data, liveApi(log), { signal: undefined, render: (next) => drawn.push(next) });
  assert.deepEqual(log.find((entry) => entry.name === "followJob").args, { jobId: JOB.NET02, afterSequence: 2 });
  assert.equal(drawn.length, 2);
  assert.equal(data.events.length, 12);
  assert.deepEqual(gone, [`#/job/${JOB.NET02}`]);
  await data.cancel();
  assert.deepEqual(log.at(-1), { name: "cancel_job", args: { job_id: JOB.NET02 } });
});

test("Cancel is greyed without the execute right", async () => {
  const { tree } = await render(job, { jid: JOB.NET02 }, { principal: "viewer-b", api: liveApi([]) });
  const cancel = byAttr(tree, "data-ofs-action", "cancel")[0];
  assert.equal(cancel.p.disabled, true);
});

// ------------------------------------------------------------------------------ equation view

test("the equation view of a revision row: incidence, matched column, block, DOF", async () => {
  const { tree, text, api } = await render(revisionRow, { rid: REV.NET02, row: "U-HEAT:HEAT-duty" });
  assert.deepEqual(calls(api), ["inspect_structure"]);
  const matched = byAttr(tree, "data-ofs-matched", "1");
  assert.equal(matched.length, 1);
  assert.equal(textOf(matched[0].c[0]), "U-HEAT.Q");
  assert.equal(matched[0].p["aria-selected"], "true");
  assert.equal(tableRows(tree, "column").length, 14);
  assert.ok(text.includes("residual kindheat_rate") && text.includes("residual unit (SI)W"));
  assert.ok(text.includes("candidate specification rowno"));
  assert.ok(text.includes("DOF1"));
  assert.ok(hrefs(tree).some((href) => href.endsWith("?column=U-HEAT.Q")));
});

test("?column= lists the rows incident on a column, the matched row first", async () => {
  const { tree } = await render(revisionRow, { rid: REV.NET02, row: "U-HEAT:HEAT-duty" }, { query: "column=S3.T" });
  const list = byAttr(tree, "data-ofs-incident", "S3.T")[0];
  const items = byTag(list, "li").map(textOf);
  const structure = await fixtureApi().readWhole("inspect_structure", { revision_id: REV.NET02 });
  const matched = structure.structural_report.canonical_matching["S3.T"];
  assert.ok(items[0].startsWith(matched) && items[0].includes("(matched to the column)"));
  const incident = structure.rows.filter((row) => row.columns.includes("S3.T")).length;
  assert.equal(items.length, incident);
});

test("G7: the equation view at a run shows the run's values and the check on its row", async () => {
  const { tree, text, data } = await render(jobRow, { jid: JOB.NET02, row: "U-HEAT:HEAT-duty" });
  assert.equal(data.consistent, true);
  const duty = tableRows(tree, "column").find((row) => row[0] === "U-HEAT.Q");
  assert.equal(duty[7], "31487.6");
  const checks = tableRows(tree, "check");
  assert.equal(checks.length, 1);
  assert.equal(checks[0][0], "residual.U-HEAT:HEAT-duty");
  assert.ok(pills(tree).some((p) => p.word === "near_threshold"));
  assert.ok(text.includes("value (W)"));
});

test("the consistency guard: a different equation structure disables the equation index", () => {
  const tree = jobRow.view({ scope: "job", owner: JOB.NET02, row: "U-HEAT:HEAT-duty", consistent: false });
  assert.equal(byAttr(tree, "data-ofs-guard", "1").length, 1);
  assert.ok(textOf(tree).includes(GUARD_TEXT));
  assert.equal(byTag(tree, "table").length, 0);
});

// ------------------------------------------------------------------------- revision comparison

test("G5: the revision comparison shows the server's diff and the before/after values", async () => {
  const { tree, text, api } = await render(compareRevisions, { a: REV.NET02, b: REV["NET02-split-0.90"] });
  assert.deepEqual(calls(api), ["diff_revisions", "get_revision"]);
  assert.deepEqual(tableRows(tree, "added"), [["—", "—", "instances"]]);
  assert.deepEqual(tableRows(tree, "member"), [
    ["instances", "U-SPLIT", "changed", "parameters › split_fraction › value", "0.95", "0.9"],
  ]);
  assert.ok(!text.includes("order changed only"));
});

test("a coarse change without elements reads 'order changed only'", () => {
  const tree = compareRevisions.view({
    a: "x",
    b: "y",
    diff: { added: [], removed: [], changed: ["connections"], elements: [] },
    before: {},
    after: {},
    go() {},
  });
  assert.equal(byAttr(tree, "data-ofs-order-only", "connections").length, 1);
});

// ------------------------------------------------------------------------------- scenario view

test("the scenario view displays differences and never judges them (R-174)", async () => {
  const { tree, text, data } = await render(compareRuns, { job_a: JOB.NET02, job_b: JOB["NET02-split-0.90"] });
  assert.equal(byAttr(tree, "data-ofs-banner", "not-judged").length, 1);
  assert.ok(text.includes(compareRuns.BANNER));
  assert.ok(text.includes("same equation structure"));
  assert.doesNotMatch(text, /\bAGREE|\bMATCH|\bagree/);
  const state = tableRows(tree, "variable");
  const ids = new Set([...data.a.state.document.variable_ids, ...data.b.state.document.variable_ids]);
  assert.equal(state.length, ids.size);
  const relative = state.map((row) => Number(row[4]));
  for (let i = 1; i < relative.length; i += 1) assert.ok(relative[i - 1] >= relative[i]);
  assert.ok(text.includes("final property_calls"));
});

test("a scenario with a failed run says it has no state and that the structures differ", async () => {
  const { text } = await render(compareRuns, { job_a: JOB.NET02, job_b: JOB["A02-352"] });
  assert.ok(text.includes(`no solution state recorded for ${JOB["A02-352"]}`));
  assert.ok(text.includes("different structure — variables compared by id only"));
  assert.ok(text.includes("different string"));
});

// ------------------------------------------------------------------------------ agent history

test("G6: the history shows the caller's own rows; other principals are greyed without policy", async () => {
  const { tree, text, api } = await render(history, {});
  assert.deepEqual(api.log[0].args, { order: "descending", limit: 200, principal_id: "agent-a" });
  const rows = tableRows(tree, "seq");
  assert.equal(rows.length, 8);
  assert.ok(rows.every((row) => row[2] === "agent-a"));
  assert.deepEqual(rows.map((row) => Number(row[0])), [...rows.map((row) => Number(row[0]))].sort((a, b) => b - a));
  const all = byTag(tree, "option").find((option) => option.p.value === "all");
  assert.equal(all.p.disabled, true);
  assert.ok(text.includes(history.STATEMENT));
  assert.ok(hrefs(tree).includes(`#/rev/${REV.NET02}`) && hrefs(tree).includes(`#/job/${JOB.NET02}`));
  assert.ok(rows.filter((row) => row[4] === "commit_change" || row[4] === "submit_job").every((row) => row[7].startsWith("fixture-")));
});

test("G6: all principals with policy; refused rows show their code", async () => {
  const { tree } = await render(history, {}, { principal: "supervisor-c", query: "principal=all" });
  const rows = tableRows(tree, "seq");
  assert.equal(rows.length, 14); // project_init, three grants, agent-a's eight, viewer-b's two
  const refused = rows.filter((row) => row[5].includes("refused"));
  assert.deepEqual(refused.map((row) => [row[2], row[4], row[5]]), [
    ["viewer-b", "list_audit", "✕refused forbidden"],
    ["viewer-b", "submit_job", "✕refused forbidden"],
  ]);
  assert.equal(byTag(tree, "option").find((option) => option.p.value === "all").p.disabled, false);
});

test("G6: without policy, all principals is refused and the refusal is shown", async () => {
  const { tree } = await render(history, {}, { principal: "viewer-b", query: "principal=all" });
  assert.equal(byAttr(tree, "data-ofs-refused", "forbidden").length, 1);
});

test("history detail: a commit's expected revision, element diff and validation now", async () => {
  const page = body("supervisor-c", "list_audit", { order: "descending", limit: 200 });
  const seq = page.items.find((row) => row.effect === `revision:${REV["NET02-split-0.90"]}`).seq;
  const { text, tree } = await render(history, {}, { principal: "supervisor-c", query: `principal=all&row=${seq}` });
  assert.ok(text.includes(`expected revision (its parent)${REV.NET02}`));
  assert.deepEqual(tableRows(tree, "paths"), [["instances", "U-SPLIT", "changed", "parameters › split_fraction › value"]]);
  assert.ok(text.includes("Validation, validated now by server 0.1.1"));
  assert.ok(hrefs(tree).includes(`#/compare/rev/${REV.NET02}/${REV["NET02-split-0.90"]}`));
});

test("history detail: a solve's request, status, outcome and verification", async () => {
  const page = body("agent-a", "list_audit", { order: "descending", limit: 200, principal_id: "agent-a" });
  const seq = page.items.find((row) => row.effect === `job:${JOB.NET02}`).seq;
  const { text, tree } = await render(history, {}, { query: `row=${seq}` });
  assert.ok(text.includes("idempotency keyfixture-solve-1"));
  const words = pills(tree).map((p) => p.word);
  assert.deepEqual(words.slice(-3), ["completed", "CONVERGED", "VERIFIED"]);
});

// ------------------------------------------------------------------------------- bundle files

test("a bundle member as a JSON tree, digest-checked", async () => {
  const { text, data } = await render(file, { jid: JOB.NET02, name: "solve-path.json" });
  assert.equal(data.digest, "match");
  assert.ok(text.includes('solve_path: "revision_eo"'));
  const missing = await render(file, { jid: JOB.NET02, name: "nope.json" });
  assert.ok(missing.text.includes("the bundle of this run has no such file"));
});
