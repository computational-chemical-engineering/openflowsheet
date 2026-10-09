// M06 WO-8: the view models on the W26 fixtures (design note §5.6, §6; gate G7 numeric rows).
//
// Every model is pure and runs on records the server wrote (tests/web/fixtures/w26). The G7
// numbers are the design note's, written before this code; the attempt model is also held to
// the server's own attempt tree (the failure bundle's `attempt_tree`, built by verify/failure.py
// from the same events), an expectation independent of this module.

import { test } from "node:test";
import assert from "node:assert/strict";

import { body, fixtureApi, JOB, rawJson, REV } from "./fixture-transport.mjs";
import { attemptsOf, counterDelta, signatureText } from "../../apps/web/js/model/attempts.js";
import {
  checkGroups,
  checksForSubject,
  nearThresholdCount,
  phaseBranches,
  scaledResidual,
} from "../../apps/web/js/model/certificate.js";
import {
  ABSENT,
  certificateSummary,
  difference,
  revisionComparison,
  runIdentity,
  stateTable,
} from "../../apps/web/js/model/compare.js";
import {
  detailOf,
  effectOf,
  expectedRevision,
  historyRows,
  jobsOfRevision,
  principalsOf,
} from "../../apps/web/js/model/history.js";
import { BOX_H, BOX_W, layout } from "../../apps/web/js/model/layout.js";
import { modelSignature, streamTable, unitPanel } from "../../apps/web/js/model/streams.js";
import { reportOf, sameStructure, structureIndex } from "../../apps/web/js/model/structure.js";
import { filterTrace, pageOf, traceChoices, traceRows } from "../../apps/web/js/model/trace.js";
import { fmt } from "../../apps/web/js/text.js";

const member = (job, name) => rawJson(`${job}:bundle/${name}`);
const COUNTERS = ["property_calls", "residual_calls", "jacobian_calls", "factorizations"];
const pick = (counters) => COUNTERS.map((name) => counters[name]);

async function whole(name, args) {
  return fixtureApi().readWhole(name, args);
}

// ---------------------------------------------------------------------------- attempts, trace

test("G7: the NET-02 run has 27 trace events and two attempts with their counter deltas", () => {
  const events = member(JOB.NET02, "solve-events.json");
  assert.equal(events.length, 27);
  assert.equal(traceRows(events).length, 27);
  const { attempts, totals, outside } = attemptsOf(events);
  assert.equal(attempts.length, 2);
  assert.deepEqual(
    attempts.map((a) => [a.attempt, a.outcome, ...pick(a.deltas)]),
    [
      [0, "BOUND_BLOCKED", 54, 2, 2, 2],
      [1, "CONVERGED", 135, 7, 4, 4],
    ],
  );
  assert.deepEqual(pick(totals), [338, 9, 6, 6]);
  assert.deepEqual(pick(outside), [338 - 54 - 135, 9 - 2 - 7, 6 - 2 - 4, 6 - 2 - 4]);
});

test("the attempt model reproduces the server's attempt tree, correctors excluded", () => {
  for (const job of [JOB.NET02, JOB["A02-352"]]) {
    const { attempts } = attemptsOf(member(job, "solve-events.json"));
    if (job === JOB["A02-352"]) {
      const tree = member(job, "failure-bundle.json").attempt_tree;
      assert.deepEqual(
        attempts.map((a) => ({
          attempt: a.attempt,
          signature: a.signature,
          outcome: a.outcome,
          iterations: a.iterations,
        })),
        tree,
      );
      assert.equal(attempts.length, 5); // 18 corrector closings inside attempt 4 are not attempts
    }
    for (const attempt of attempts) assert.ok(attempt.opened && attempt.deltas);
  }
});

test("an attempt opened and never closed is listed with no outcome; counters subtract by name", () => {
  const events = [
    { kind: "attempt_opened", attempt: 0, step_index: 0, counters: { property_calls: 1 } },
    { kind: "attempt_closed", attempt: 0, step_index: 0, counters: { property_calls: 5 } },
    { kind: "attempt_opened", attempt: 1, step_index: 0, counters: { property_calls: 6 } },
    { kind: "trial", attempt: 1, counters: { property_calls: 9 } },
  ];
  const { attempts, outside } = attemptsOf(events);
  assert.deepEqual(
    attempts.map((a) => [a.attempt, a.outcome, a.deltas]),
    [
      [0, null, { property_calls: 4 }],
      [1, null, null],
    ],
  );
  assert.deepEqual(outside, { property_calls: 5 });
  assert.equal(counterDelta(null, {}), null);
  assert.equal(signatureText([["U-HEAT", "VAPOR"], ["U-PHF", "TWO_PHASE"]]), "U-HEAT VAPOR · U-PHF TWO_PHASE");
});

test("trace rows read the recorded members; absent members stay absent; filters and pages", () => {
  const rows = traceRows(member(JOB.NET02, "solve-events.json"));
  const trial = rows.find((row) => row.kind === "trial");
  assert.equal(trial.rejection_reason, "armijo");
  assert.equal(trial.linear_residual_normalized, undefined);
  assert.equal(fmt(trial.linear_residual_normalized), "—");
  const linear = rows.find((row) => row.kind === "linear_solve");
  assert.equal(typeof linear.linear_residual_normalized, "number");
  assert.equal(linear.state.length, 12);
  const { kinds, attempts } = traceChoices(rows);
  assert.ok(kinds.includes("attempt_closed") && attempts.includes(1));
  assert.equal(filterTrace(rows, { kind: "trial" }).every((row) => row.kind === "trial"), true);
  assert.equal(filterTrace(rows, { attempt: "1" }).every((row) => row.attempt === 1), true);
  assert.equal(filterTrace(rows, {}).length, 27);
  const a02 = traceRows(member(JOB["A02-352"], "solve-events.json"));
  assert.equal(a02.length, 249);
  const page = pageOf(a02, 0, 100);
  assert.deepEqual([page.rows.length, page.pages, page.first, page.last], [100, 3, 1, 100]);
  const end = pageOf(a02, 9, 100);
  assert.deepEqual([end.page, end.first, end.last], [2, 201, 249]);
  assert.deepEqual(pageOf([], 0).first, 0);
});

// -------------------------------------------------------------------------------- certificate

test("G7: the NET-02 certificate is VERIFIED with 144 checks and 3 near-threshold limitations", () => {
  const certificate = member(JOB.NET02, "solution-certificate.json");
  assert.equal(certificate.verification_status, "VERIFIED");
  assert.equal(certificate.checks.length, 144);
  const near = certificate.limitations.filter((entry) => entry.kind === "near_threshold");
  assert.equal(near.length, 3);
  assert.equal(nearThresholdCount(certificate.checks), 3);
  const groups = checkGroups(certificate.checks);
  assert.equal(groups.reduce((total, group) => total + group.count, 0), 144);
  const residual = groups.find((group) => group.category === "residual");
  assert.deepEqual(
    residual.results.map((bucket) => [bucket.result, bucket.count]),
    [["pass", 48]],
  );
  assert.deepEqual(certificateSummary(certificate), {
    status: "VERIFIED",
    checks: 144,
    limitations: certificate.limitations,
  });
});

test("rule 2: the scaled residual is value / reference of a residual check only", () => {
  const certificate = member(JOB.NET02, "solution-certificate.json");
  const [duty] = checksForSubject(certificate, "U-HEAT:HEAT-duty");
  assert.equal(duty.category, "residual");
  assert.equal(scaledResidual(duty), duty.value / duty.reference);
  const other = certificate.checks.find((check) => check.category !== "residual");
  assert.equal(scaledResidual(other), null);
  assert.equal(scaledResidual({ category: "residual", value: 1, reference: 0 }), null);
});

test("rule 3: a phase split's vapour fraction is vapor_total / (vapor_total + liquid_total)", () => {
  const certificate = member(JOB.NET02, "solution-certificate.json");
  const components = body("agent-a", "get_revision", {
    revision_id: REV.NET02,
    pointer: "",
    depth: 12,
    limit: 200,
  }).value.component_set.components;
  const entries = phaseBranches(certificate.phase_branch, components);
  const split = entries.find((entry) => entry.key === "U-PHF:S3");
  const recorded = certificate.phase_branch["U-PHF:S3"];
  assert.equal(
    split.vapour_fraction,
    recorded.vapor_total / (recorded.vapor_total + recorded.liquid_total),
  );
  assert.deepEqual(split.components, ["A", "B", "C"]);
  assert.deepEqual(
    entries.filter((entry) => !entry.split).map((entry) => [entry.key, entry.state]),
    [["S1", "FLOWING"], ["S2", "FLOWING"], ["S3", "FLOWING"], ["S4", "FLOWING"], ["S5", "FLOWING"], ["S6", "FLOWING"], ["S7", "FLOWING"]],
  );
  assert.equal(phaseBranches({ X: { liquid_total: 0, vapor_total: 0 } })[0].vapour_fraction, null);
});

// ---------------------------------------------------------------------------------- structure

test("the structure index joins rows, columns, matching, blocks and certificates", async () => {
  const structure = await whole("inspect_structure", { revision_id: REV.NET02 });
  const index = structureIndex(structure);
  assert.equal(index.routed, true);
  assert.equal(index.matchedRow("U-HEAT.Q"), "U-HEAT:HEAT-duty");
  assert.equal(index.matchedColumn("U-HEAT:HEAT-duty"), "U-HEAT.Q");
  const incident = index.incidentRows("U-HEAT.Q");
  assert.equal(incident[0], "U-HEAT:HEAT-duty");
  for (const row of incident) assert.ok(index.row(row).columns.includes("U-HEAT.Q"));
  const all = [...index.rows.values()].filter((row) => row.columns.includes("U-HEAT.Q"));
  assert.equal(incident.length, all.length);
  const block = index.block("U-HEAT:HEAT-duty");
  assert.ok(block.rows.includes("U-HEAT:HEAT-duty"));
  assert.equal(block.size, block.rows.length);
  assert.deepEqual(
    index.certificatesWith("U-SPLIT:SPLIT-P:recycle").map((c) => c.row_id),
    ["U-SPLIT:SPLIT-P:recycle"],
  );
  assert.equal(index.certificatesWith("U-HEAT:HEAT-pressure").length, 1);
  assert.equal(index.unitDof("U-FEED").degrees_of_freedom, 5);
  assert.equal(index.isCandidateRow("U-HEAT:HEAT-duty"), false);
  const recorded = member(JOB.NET02, "structural-report.json");
  assert.equal(sameStructure(structure, recorded), true);
  assert.equal(sameStructure(structure, { model_version: "other" }), false);
});

test("an unroutable revision carries the validation's structural report", async () => {
  const structure = await whole("inspect_structure", { revision_id: REV.STR03 });
  const index = structureIndex(structure);
  assert.equal(index.routed, false);
  assert.equal(reportOf(structure), structure.validation_structural_report);
  assert.equal(index.report.excess, 1);
  assert.equal(index.isCandidateRow("SPEC:SPEC-heater-duty"), true);
  assert.equal(sameStructure(structure, { model_version: "x" }), false);
});

// ------------------------------------------------------------------------------------ streams

test("G7: the stream and unit tables join the revision, the column index and the run's state", async () => {
  const revision = await whole("get_revision", { revision_id: REV.NET02 });
  const structure = await whole("inspect_structure", { revision_id: REV.NET02 });
  const state = member(JOB.NET02, "solution-state.json");
  const table = streamTable(revision, structure.columns, state.variables);
  assert.deepEqual(
    table.rows.map((row) => row.connection),
    revision.connections.map((connection) => connection.id),
  );
  assert.ok(table.rows.every((row) => row.inRevision));
  const s1 = table.rows[0];
  assert.deepEqual(
    [s1.n.A.value, s1.n.B.value, s1.n.C.value, s1.T.value, s1.P.value],
    [1, 1, 1, 300, 100000],
  );
  assert.deepEqual([s1.n.A.si_unit, s1.T.si_unit, s1.P.si_unit], ["mol/s", "K", "Pa"]);
  const heat = table.units.find((unit) => unit.instance === "U-HEAT");
  const duty = heat.columns.find((cell) => cell.column === "U-HEAT.Q");
  assert.equal(duty.si_unit, "W");
  assert.equal(fmt(duty.value, "short"), "31487.6");
  assert.equal(fmt(duty.value, "full"), "31487.641739605908");
  // Every column of the index is shown once: in a stream row or under its owner.
  const shown = [
    ...table.rows.flatMap((row) => [...Object.values(row.n), row.T, row.P]),
    ...table.units.flatMap((unit) => unit.columns),
  ].filter(Boolean);
  assert.equal(shown.length, structure.columns.length);
  assert.equal(new Set(shown.map((cell) => cell.column)).size, structure.columns.length);
});

test("without a solution state every value is undefined; a binder-only connection is kept", () => {
  const revision = { connections: [{ id: "S1" }], instances: [{ id: "U" }], component_set: { components: ["A"] } };
  const columns = [
    { column_id: "S1.n.A", connection: "S1", coordinate: "n", component: "A", owner_instance: "U", si_unit: "mol/s" },
    { column_id: "S9.T", connection: "S9", coordinate: "T", component: null, owner_instance: "U", si_unit: "K" },
    { column_id: "U.Q", connection: null, coordinate: null, component: null, owner_instance: "U", si_unit: "W" },
  ];
  const table = streamTable(revision, columns, null);
  assert.deepEqual(table.rows.map((row) => [row.connection, row.inRevision]), [["S1", true], ["S9", false]]);
  assert.equal(table.rows[0].n.A.value, undefined);
  assert.equal(table.rows[0].P, null);
  assert.deepEqual(table.units.map((unit) => unit.instance), ["U"]);
});

test("a unit panel lists the model's ports, pins, required and zero; empty is not applicable", () => {
  const models = body("agent-a", "list_models", {});
  const mixer = modelSignature(models, "syn001.adiabatic_mixer");
  const panel = unitPanel({ id: "U-MIX", model: { id: "syn001.adiabatic_mixer" } }, mixer);
  assert.equal(panel.listed, true);
  assert.deepEqual(panel.ports.map((port) => port.name), ["inlet", "outlet"]);
  assert.equal(panel.pins, null);
  assert.equal(panel.required, null);
  assert.deepEqual(panel.zero, ["pressure_drop"]);
  assert.equal(unitPanel({ id: "X", model: { id: "nope" } }, modelSignature(models, "nope")).listed, false);
});

// ------------------------------------------------------------------------------------ compare

test("G5: the revision comparison reads before/after values of each changed path", async () => {
  const diff = body("agent-a", "diff_revisions", {
    from_revision: REV.NET02,
    to_revision: REV["NET02-split-0.90"],
  });
  assert.deepEqual(diff.changed, ["instances"]);
  assert.deepEqual(diff.elements, [
    { member: "instances", id: "U-SPLIT", change: "changed", paths: [["parameters", "split_fraction", "value"]] },
  ]);
  const before = await whole("get_revision", { revision_id: REV.NET02 });
  const after = await whole("get_revision", { revision_id: REV["NET02-split-0.90"] });
  const comparison = revisionComparison(diff, before, after);
  assert.deepEqual(comparison.elements[0].paths, [
    { path: ["parameters", "split_fraction", "value"], before: 0.95, after: 0.9 },
  ]);
  assert.deepEqual(comparison.orderOnly, []);
  const reordered = revisionComparison({ changed: ["connections"], elements: [] }, before, after);
  assert.deepEqual(reordered.orderOnly, ["connections"]);
  const removed = revisionComparison(
    { changed: ["instances"], elements: [{ member: "instances", id: "U-NONE", change: "removed", paths: [["a"]] }] },
    before,
    after,
  );
  assert.equal(removed.elements[0].paths[0].before, ABSENT);
});

test("rule 4: Δ = b − a and |Δ| / max(|a|, |b|), 0 when both are 0, sorted descending", () => {
  assert.deepEqual(difference(2, 3), { delta: 1, relative: 1 / 3 });
  assert.deepEqual(difference(0, 0), { delta: 0, relative: 0 });
  assert.deepEqual(difference(-4, 4), { delta: 8, relative: 2 });
  assert.deepEqual(difference(1, undefined), { delta: null, relative: null });
  const a = member(JOB.NET02, "solution-state.json");
  const b = member(JOB["NET02-split-0.90"], "solution-state.json");
  const rows = stateTable(a, b);
  const ids = new Set([...a.variable_ids, ...b.variable_ids]);
  assert.equal(rows.length, ids.size);
  for (const row of rows) {
    assert.equal(row.delta, row.b - row.a);
    const scale = Math.max(Math.abs(row.a), Math.abs(row.b));
    assert.equal(row.relative, scale === 0 ? 0 : Math.abs(row.b - row.a) / scale);
  }
  for (let i = 1; i < rows.length; i += 1) assert.ok(rows[i - 1].relative >= rows[i].relative);
  const one = stateTable({ variable_ids: ["x", "y"], variables: { x: 1, y: 2 } }, null);
  assert.deepEqual(one.map((row) => [row.id, row.a, row.b, row.relative]), [["x", 1, undefined, null], ["y", 2, undefined, null]]);
});

test("the run identity rows compare strings for equality and say what a version mismatch means", () => {
  const run = (job) => ({
    result: body("agent-a", "get_job_result", { job_id: job }).run_result,
    manifest: member(job, "run-manifest.json"),
  });
  const same = runIdentity(run(JOB.NET02), run(JOB["NET02-split-0.90"]));
  assert.equal(same.model_version.text, "same equation structure");
  const other = runIdentity(run(JOB.NET02), run(JOB["A02-352"]));
  assert.equal(other.structural.equal, false);
  assert.equal(other.model_version.text, "different structure — variables compared by id only");
});

// ------------------------------------------------------------------------------------ history

test("history rows link revision, job and cancel effects and read the rest as text", () => {
  const page = body("supervisor-c", "list_audit", { order: "descending", limit: 200 });
  const rows = historyRows(page);
  assert.equal(rows.length, page.items.length);
  const commit = rows.find((row) => row.effect?.id === REV.NET02);
  assert.deepEqual(commit.effect, { kind: "revision", id: REV.NET02, target: { screen: "revision", id: REV.NET02 } });
  assert.deepEqual(detailOf(commit), { kind: "commit", revision: REV.NET02 });
  const solve = rows.find((row) => row.effect?.kind === "job");
  assert.deepEqual(detailOf(solve), { kind: "job", job: solve.effect.id });
  assert.deepEqual(effectOf("cancel:job-000002").target, { screen: "job", id: "job-000002" });
  assert.equal(effectOf("grant:cap-agent-a").target, null);
  const refused = rows.find((row) => row.outcome === "refused");
  assert.equal(refused.code, "forbidden");
  assert.equal(detailOf(refused), null);
  assert.deepEqual(principalsOf(rows, "supervisor-c"), ["supervisor-c", "viewer-b", "agent-a", "local-owner"]);
});

test("rule 6: a revision's expected revision is its parent; its jobs are filtered by request", async () => {
  const second = await whole("get_revision", { revision_id: REV["NET02-split-0.90"] });
  assert.equal(expectedRevision(second), REV.NET02);
  const jobs = body("agent-a", "list_jobs", { limit: 200 }).items;
  assert.deepEqual(jobsOfRevision(jobs, REV.NET02).map((job) => job.job_id), [JOB.NET02]);
  assert.deepEqual(jobsOfRevision(jobs, REV.STR03), []);
});

// ------------------------------------------------------------------------------------- layout

test("G7: the NET-02 layout has §6.1's layers and the recycle S6 as its one back edge", async () => {
  const revision = await whole("get_revision", { revision_id: REV.NET02 });
  const drawn = layout(revision);
  const layers = Object.fromEntries(drawn.nodes.map((node) => [node.id, node.layer]));
  assert.deepEqual(layers, {
    "U-FEED": 0,
    "U-MIX": 1,
    "U-HEAT": 2,
    "U-PHF": 3,
    "U-SINK-V": 4,
    "U-SPLIT": 4,
    "U-SINK-P": 5,
  });
  assert.deepEqual(drawn.edges.filter((edge) => edge.back).map((edge) => edge.id), ["S6"]);
  assert.deepEqual(drawn.dangling, []);
  const split = drawn.nodes.find((node) => node.id === "U-SPLIT");
  const sinkV = drawn.nodes.find((node) => node.id === "U-SINK-V");
  assert.deepEqual([split.index, sinkV.index], [0, 1]); // a barycentre tie: instance order
  assert.equal(sinkV.y - split.y, 90);
  assert.equal(drawn.nodes.find((node) => node.id === "U-PHF").x - drawn.nodes[0].x, 3 * 160);
  for (const node of drawn.nodes) assert.deepEqual([node.w, node.h], [BOX_W, BOX_H]);
  const back = drawn.edges.find((edge) => edge.back);
  assert.equal(back.label.text, "S6");
});

test("layout: a cycle without a source and a dangling connection", () => {
  const drawn = layout({
    instances: [{ id: "A" }, { id: "B" }],
    connections: [
      { id: "x", from: { instance: "A" }, to: { instance: "B" } },
      { id: "y", from: { instance: "B" }, to: { instance: "A" } },
      { id: "z", from: { instance: "B" }, to: { instance: "GONE" } },
    ],
  });
  assert.deepEqual(drawn.nodes.map((node) => [node.id, node.layer]), [["A", 0], ["B", 1]]);
  assert.deepEqual(drawn.edges.map((edge) => [edge.id, edge.back]), [["x", false], ["y", true]]);
  assert.deepEqual(drawn.dangling, ["z"]);
});
