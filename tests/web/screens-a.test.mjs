// M06 WO-9: screens A on the W26 fixtures (design note §6.1, §6.2, §6.4, §6.6; G7 view rows).
//
// Each screen's `load` runs against the shell's own api.js over the recorded server answers
// (an unrecorded request fails the test), and its `view` is asserted on the plain tree: the
// records' text and numbers, pills with glyph and word, link targets, and the statements a
// screen must make when a record is absent.

import { test } from "node:test";
import assert from "node:assert/strict";

import { body, fixtureApi, FIXTURE, JOB, REV } from "./fixture-transport.mjs";
import { byAttr, byTag, findAll, hrefs, pills, tableRows, textOf } from "./tree.mjs";
import * as certificate from "../../apps/web/js/screens/certificate.js";
import { setNumberMode } from "../../apps/web/js/screens/common.js";
import * as failure from "../../apps/web/js/screens/failure.js";
import * as project from "../../apps/web/js/screens/project.js";
import * as revision from "../../apps/web/js/screens/revision.js";
import * as streams from "../../apps/web/js/screens/streams.js";
import * as validation from "../../apps/web/js/screens/validation.js";
import { mount } from "../../apps/web/js/h.js";
import { FakeDocument } from "./fake-dom.mjs";

const projectOf = (principal) => body(principal, "get_project", {});

async function render(screen, values, { principal = "agent-a", api = fixtureApi(principal) } = {}) {
  const gone = [];
  const data = await screen.load(
    { ...values, query: new URLSearchParams(), signal: undefined, project: projectOf(principal), go: (hash) => gone.push(hash) },
    api,
  );
  const tree = screen.view(data);
  pills(tree); // every pill carries glyph and word, or this throws
  mount(tree, new FakeDocument().body); // every node mounts through h.js's whitelist
  return { data, tree, text: textOf(tree), api, gone };
}

const calls = (api) => [...new Set(api.log.map((entry) => entry.name))];

// ------------------------------------------------------------------------------------ project

test("project: every revision and the first page of jobs, hostile text as text", async () => {
  const { tree, text, api } = await render(project, {});
  assert.deepEqual(calls(api), ["list_revisions", "list_jobs"]);
  for (const id of Object.values(REV)) assert.ok(hrefs(tree).includes(`#/rev/${id}`), id);
  for (const id of Object.values(JOB)) assert.ok(hrefs(tree).includes(`#/job/${id}`), id);
  assert.ok(text.includes("<img src=x onerror=alert(1)>�evil"));
  assert.equal(byTag(tree, "img").length, 0);
  assert.deepEqual(
    pills(tree).map((p) => p.word),
    ["completed", "completed", "completed"],
  );
  assert.equal(byAttr(tree, "data-ofs-form").length, 2);
  assert.ok(hrefs(tree).includes("#/history"));
});

// --------------------------------------------------------------------------- revision overview

test("revision overview: header, validation, runs, flowsheet, tables as written", async () => {
  const { tree, text, api } = await render(revision, { rid: REV.NET02 });
  assert.deepEqual(calls(api), [
    "get_revision",
    "validate",
    "list_revisions",
    "list_jobs",
    "get_job_result",
    "list_models",
  ]);
  const summary = body("agent-a", "list_revisions", { limit: 200 }).items[0];
  assert.ok(text.includes(summary.content_sha256.slice(0, 12)));
  assert.ok(text.includes(summary.created_at));
  const words = pills(tree).map((p) => p.word);
  assert.deepEqual(words.slice(0, 4), ["READY_FOR_SIMULATION", "completed", "CONVERGED", "VERIFIED"]);
  assert.deepEqual(tableRows(tree, "created").map((row) => row[1]), [JOB.NET02]);
  // G7: the flowsheet's layers (§6.1) and its back edge S6.
  const layers = Object.fromEntries(byAttr(tree, "data-node").map((g) => [g.p["data-node"], g.p["data-layer"]]));
  assert.deepEqual(layers, {
    "U-FEED": "0", "U-MIX": "1", "U-HEAT": "2", "U-PHF": "3", "U-SPLIT": "4", "U-SINK-V": "4", "U-SINK-P": "5",
  });
  const back = findAll(tree, (node) => node.t === "g" && node.p.class === "edge edge-back");
  assert.deepEqual(back.map((g) => g.p["data-edge"]), ["S6"]);
  assert.ok(text.includes("U-SPLIT.recycle") && text.includes("nTP-v1"));
  assert.ok(hrefs(tree).includes(`#/rev/${REV.NET02}/validation`));
  const solve = byAttr(tree, "data-ofs-action", "solve");
  assert.equal(solve.length, 1);
  const options = byTag(solve[0], "option").map((option) => option.p.value);
  assert.deepEqual(options, ["default", "T04-W12", "T06-revision-v2", "T08-ptc-v1", "T08-warm-v1"]);
});

test("revision overview: Solve is greyed without the execute right", async () => {
  const { tree } = await render(revision, { rid: REV.NET02 }, { principal: "viewer-b" });
  assert.equal(byAttr(tree, "data-ofs-action", "solve").length, 0);
  const buttons = byTag(tree, "button").filter((button) => textOf(button) === "Solve…");
  assert.equal(buttons.length, 1);
  assert.equal(buttons[0].p.disabled, true);
});

test("the hostile revision's title renders as text with U+FFFD, never as markup", async () => {
  const { tree } = await render(revision, { rid: REV.hostile });
  const title = byTag(tree, "h1")[0];
  assert.deepEqual(title.c, ["<img src=x onerror=alert(1)>�evil"]);
  assert.equal(byTag(tree, "img").length, 0);
});

test("Solve sends §6.1's body under one key, reused on retry, fresh when the dialog reopens", async () => {
  const recorded = Object.entries(FIXTURE.principals["agent-a"]).find(([key]) => key.startsWith("submit_job"))[1];
  let refuse = true;
  const sent = [];
  const api = fixtureApi("agent-a", {
    extra: (name, args) => {
      if (name !== "submit_job") return undefined;
      sent.push(args);
      if (refuse) {
        refuse = false;
        return { status: 503, body: { code: "unavailable", message: "try again", retryable: true, detail: {} } };
      }
      return recorded;
    },
  });
  let byte = 0;
  const action = revision.solveAction(api, REV.NET02, { random: (bytes) => bytes.map(() => (byte += 1)) });
  const key = action.open();
  assert.match(key, /^ui-solve-[0-9a-f]{32}$/);
  const first = await action.submit("T06-revision-v2");
  assert.equal(first.error.code, "unavailable");
  const second = await action.submit("T06-revision-v2");
  assert.equal(second.job.job_id, recorded.body.job.job_id);
  assert.deepEqual(sent[0], {
    operation: "solve",
    idempotency_key: key,
    body: { revision_id: REV.NET02, policy_id: "T06-revision-v2" },
  });
  assert.deepEqual(sent[1], sent[0]);
  assert.notEqual(action.open(), key);
});

// --------------------------------------------------------------------------------- validation

test("validation: an unroutable revision shows the validation's report under its reason", async () => {
  const { tree, text } = await render(validation, { rid: REV.STR03 });
  assert.equal(byAttr(tree, "data-ofs-unroutable", "1").length, 1);
  assert.ok(text.includes("unsupported(specification_unconsumed(SPEC-heater-duty))"));
  assert.ok(pills(tree).some((p) => p.word === "INVALID"));
  assert.ok(pills(tree).some((p) => p.word === "FAIL" && p.glyph === "✕"));
  assert.ok(pills(tree).some((p) => p.word === "NOT_RUN" && p.tone === "none"));
  // G4's STR-03 row: excess 1 and the nine candidate specifications of the STR-03 message, in order.
  const message = body("agent-a", "validate", { revision_id: REV.STR03, task: "simulation" }).checks.find(
    (check) => check.id === "STR-03",
  ).message;
  const named = /candidate specifications \[([^\]]*)\]/.exec(message)[1].split(", ").map((s) => s.slice(1, -1));
  assert.equal(named.length, 9);
  const lists = findAll(tree, (node) => node.t === "ul" && node.p.class === "inline-list");
  const candidates = lists.map((ul) => ul.c.map(textOf)).find((items) => items[0] === named[0] && items.length === 9);
  assert.deepEqual(candidates, named);
  assert.ok(text.includes("excess1"));
  assert.ok(pills(tree).some((p) => p.word === "over_specified"));
});

test("validation: a routed revision links its certified redundant rows to the equation view", async () => {
  const { tree, text } = await render(validation, { rid: REV.NET02 });
  assert.equal(byAttr(tree, "data-ofs-unroutable").length, 0);
  assert.ok(hrefs(tree).includes(`#/rev/${REV.NET02}/row/U-SPLIT%3ASPLIT-P%3Arecycle`));
  assert.ok(text.includes("STRUCTURALLY_CLOSED"));
  assert.ok(text.includes("block count21"));
});

// -------------------------------------------------------------------------------- certificate

test("G7: the certificate shows VERIFIED, 144 checks by category and 3 near-threshold flags", async () => {
  const { tree, text, data } = await render(certificate, { jid: JOB.NET02 });
  assert.equal(data.certificate.digest, "match");
  assert.equal(data.rows.consistent, true);
  const words = pills(tree).map((p) => p.word);
  assert.equal(words[0], "VERIFIED");
  assert.equal(words.filter((word) => word === "pass").length, 144 + 9); // each check, each bucket
  assert.ok(pills(tree).filter((p) => p.word === "pass").every((p) => p.tone === "ok"));
  assert.equal(words.filter((word) => word === "near_threshold").length, 3 + 3); // checks, limitations
  assert.ok(text.includes("checks144") && text.includes("near-threshold checks3"));
  assert.ok(text.includes("residual (48)"));
  assert.ok(text.includes(certificate.NEAR_THRESHOLD_TEXT));
  assert.ok(hrefs(tree).includes(`#/job/${JOB.NET02}/row/U-HEAT%3AHEAT-duty`));
  const near = byAttr(tree, "data-ofs-category", "residual")[0];
  const duty = tableRows(near, "id").find((row) => row[0] === "residual.U-HEAT:HEAT-duty");
  const check = data.certificate.document.checks.find((c) => c.id === "residual.U-HEAT:HEAT-duty");
  assert.equal(duty[5], String(Number((check.value / check.reference).toPrecision(6))).replace("+", ""));
  assert.equal(byAttr(tree, "data-ofs-split", "U-PHF:S3").length, 1);
});

test("a run without a certificate says so", async () => {
  const { tree, text } = await render(certificate, { jid: JOB["A02-352"] });
  assert.ok(text.includes("no certificate recorded for this run (outcome HOMOTOPY_STALLED)"));
  assert.equal(byAttr(tree, "data-ofs-empty", "1").length, 1);
});

// ----------------------------------------------------------------------------- failure bundle

test("G7: the A02-352 failure bundle — outcome, replay identity, counters, a labelled hypothesis", async () => {
  const { tree, text, data } = await render(failure, { jid: JOB["A02-352"] });
  assert.equal(data.failure.digest, "match");
  assert.equal(pills(tree)[0].word, "HOMOTOPY_STALLED");
  assert.ok(text.includes("policy_idT04-W12"));
  const counters = tableRows(tree, "counter");
  assert.deepEqual(counters.find((row) => row[0] === "property_calls"), ["property_calls", "2104"]);
  assert.deepEqual(byAttr(tree, "data-ofs-cause-kind").map((node) => node.p["data-ofs-cause-kind"]), ["hypothesis"]);
  assert.ok(text.includes("phase_boundary_on_path(U-HEAT)"));
  assert.equal(tableRows(tree, "attempt").length, 5);
  assert.ok(text.includes("supply_initial_guess"));
  assert.ok(byAttr(tree, "data-ofs-empty", "1").length >= 2); // implicated sources, check report
});

test("a converged run has no failure bundle and says so", async () => {
  const { text } = await render(failure, { jid: JOB.NET02 });
  assert.ok(text.includes("no failure bundle recorded for this run (outcome CONVERGED)"));
});

// ---------------------------------------------------------------------------- streams, units

test("G7: streams and units show U-HEAT.Q short and full, with its rows link", async () => {
  try {
    const { tree, data } = await render(streams, { jid: JOB.NET02 });
    assert.equal(data.rows.consistent, true);
    const cell = byAttr(tree, "data-column", "U-HEAT.Q")[0];
    assert.equal(cell.c[0], "31487.6");
    assert.ok(cell.p.title.includes("31487.641739605908"));
    assert.ok(hrefs(cell).includes(`#/job/${JOB.NET02}/row/U-HEAT%3AHEAT-duty?column=U-HEAT.Q`));
    const rows = tableRows(tree, "connection");
    assert.deepEqual(rows.map((row) => row[0]), ["S1", "S6", "S2", "S3", "S4", "S5", "S7"]);
    assert.ok(byTag(tree, "th").some((th) => textOf(th) === "n.A (mol/s)"));
    assert.ok(byTag(tree, "th").some((th) => textOf(th) === "T (K)"));
    assert.equal(byAttr(tree, "data-ofs-unit").length, 7);
    assert.ok(textOf(byAttr(tree, "data-ofs-unit", "U-MIX")[0]).includes("not applicable"));
    setNumberMode("full");
    const full = streams.view(data);
    assert.equal(byAttr(full, "data-column", "U-HEAT.Q")[0].c[0], "31487.641739605908");
  } finally {
    setNumberMode("short");
  }
});

test("a run without a solution state says so and shows the best checkpoint's identity", async () => {
  const { tree, text, data } = await render(streams, { jid: JOB["A02-352"] });
  assert.equal(byAttr(tree, "data-ofs-no-state", "1").length, 1);
  assert.ok(text.includes("no solution state recorded for this run"));
  assert.ok(text.includes(data.failure.document.best_checkpoint.state_sha256));
});
