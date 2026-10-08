// #/compare/run/{job_a}/{job_b} — the scenario view: two finished solves side by side
// (M06 design note §6.7, R-174; F4: a scenario in v0.2 is one revision solved under one policy).
//
// Per job: `get_job_result`, the bundle listing, and through the raw export the run manifest,
// solution state, solve events and the certificate or failure bundle. Shows outcome,
// verification, solve path, policy, structural SHA-256 (the same string or not), model version
// (the same string: "same equation structure"), elapsed seconds, final counters, certificate
// summaries and the state table (rule 4: Δ = b − a and |Δ| / max(|a|, |b|), sorted descending).
// Differences are displayed, never judged: no tolerance or allowance is applied and the screen
// has no agreement vocabulary.

import { h } from "../h.js";
import { certificateSummary, runIdentity, stateTable } from "../model/compare.js";
import { link } from "../router.js";
import { DASH } from "../text.js";
import {
  digestBanner,
  heading,
  id,
  jobLink,
  none,
  numCell,
  pill,
  readMember,
  runBundle,
  section,
  table,
  text,
} from "./common.js";

export const name = "compare-runs";
export const pattern = "/compare/run/{job_a}/{job_b}";

export const BANNER =
  "Differences are displayed, not judged: no registered comparison or allowance is applied.";
const COUNTERS = ["property_calls", "residual_calls", "jacobian_calls", "factorizations"];

async function side(api, jobId, signal) {
  const bundle = await runBundle(api, jobId, { signal });
  const read = (member) => readMember(api, bundle, member, { signal });
  const manifest = await read("run-manifest.json");
  const state = await read("solution-state.json");
  const events = await read("solve-events.json");
  const certificate = await read("solution-certificate.json");
  const failure = certificate === null ? await read("failure-bundle.json") : null;
  return { job: jobId, run: bundle.run, manifest, state, events, certificate, failure };
}

export async function load(params, api) {
  const { job_a: a, job_b: b, signal } = params;
  return { a: await side(api, a, signal), b: await side(api, b, signal) };
}

function finalCounters(events) {
  const list = events?.document ?? [];
  return list.length > 0 ? (list[list.length - 1].counters ?? null) : null;
}

function same(equal) {
  return equal ? "same" : "different";
}

export function view(data) {
  const { a, b } = data;
  const identity = runIdentity(
    { result: a.run, manifest: a.manifest?.document },
    { result: b.run, manifest: b.manifest?.document },
  );
  const countersA = finalCounters(a.events);
  const countersB = finalCounters(b.events);
  const summaryA = certificateSummary(a.certificate?.document);
  const summaryB = certificateSummary(b.certificate?.document);
  const rows = stateTable(a.state?.document ?? null, b.state?.document ?? null);
  const banners = [a, b].flatMap((run) =>
    [run.manifest, run.state, run.events, run.certificate, run.failure]
      .filter(Boolean)
      .map((read) => digestBanner(`${run.job} ${read.name}`, read.digest)),
  );
  const pair = (label, left, right, note = null) => [label, left, right, note ?? ""];
  return h(
    "div",
    { "data-ofs-screen": "compare-runs" },
    heading("Scenario view (run comparison)", jobLink(a.job), jobLink(b.job)),
    h("p", { class: "notice", "data-ofs-banner": "not-judged" }, BANNER),
    banners,
    section(
      "Runs",
      table(
        ["", `a: ${a.job}`, `b: ${b.job}`, ""],
        [
          pair("revision", text(a.run?.revision_id), text(b.run?.revision_id)),
          pair("outcome", a.run ? pill(a.run.outcome) : DASH, b.run ? pill(b.run.outcome) : DASH),
          pair(
            "verification",
            a.run ? pill(a.run.verification_status) : DASH,
            b.run ? pill(b.run.verification_status) : DASH,
          ),
          pair("solve path", text(a.run?.solve_path), text(b.run?.solve_path)),
          pair("policy", text(a.run?.policy_id), text(b.run?.policy_id)),
          pair(
            "structural sha256",
            id(identity.structural.a),
            id(identity.structural.b),
            `${same(identity.structural.equal)} string`,
          ),
          pair("model version", id(identity.model_version.a), id(identity.model_version.b), identity.model_version.text),
          pair("elapsed seconds", numCell(a.manifest?.document?.elapsed_seconds), numCell(b.manifest?.document?.elapsed_seconds)),
          ...COUNTERS.map((counter) =>
            pair(`final ${counter}`, numCell(countersA?.[counter]), numCell(countersB?.[counter])),
          ),
          pair("certificate status", summaryA ? pill(summaryA.status) : "no certificate", summaryB ? pill(summaryB.status) : "no certificate"),
          pair("certificate checks", summaryA ? numCell(summaryA.checks) : DASH, summaryB ? numCell(summaryB.checks) : DASH),
          pair(
            "certificate limitations",
            summaryA ? String(summaryA.limitations.length) : DASH,
            summaryB ? String(summaryB.limitations.length) : DASH,
          ),
        ],
      ),
    ),
    section(
      "State",
      a.state === null || b.state === null
        ? h(
            "p",
            { class: "notice" },
            `no solution state recorded for ${[a, b].filter((run) => run.state === null).map((run) => run.job).join(" and ")}`,
          )
        : null,
      rows.length === 0
        ? none("no state recorded for either run")
        : table(
            [
              "variable",
              { text: "a", num: true },
              { text: "b", num: true },
              { text: "Δ = b − a", num: true },
              { text: "|Δ| / max(|a|, |b|)", num: true },
            ],
            rows.map((row) => [id(row.id), numCell(row.a), numCell(row.b), numCell(row.delta), numCell(row.relative)]),
          ),
    ),
    section(
      "Compare other runs",
      h(
        "p",
        { class: "muted" },
        "Pick two runs on the ",
        h("a", { href: link("/") }, "project screen"),
        ".",
      ),
    ),
  );
}
