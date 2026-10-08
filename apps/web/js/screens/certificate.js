// #/job/{jid}/certificate — the solution certificate (M06 design note §6.4).
//
// Reads the run's result and bundle listing, then through the raw export (digest-checked) the
// certificate, the revision as solved (its component order labels phase splits) and the
// structural report; `inspect_structure` of the run's revision tells which check subjects are
// equation rows. Every verdict shown — status, each check's result and near-threshold flag —
// is the certificate's own; the scaled residual (rule 2) and vapour fraction (rule 3) are the
// only arithmetic. No tolerance is invented for the solution-error bound.

import { h } from "../h.js";
import {
  checkGroups,
  nearThresholdCount,
  phaseBranches,
  scaledResidual,
} from "../model/certificate.js";
import { sameStructure, structureIndex } from "../model/structure.js";
import { componentsOf } from "../model/streams.js";
import { DASH } from "../text.js";
import {
  digestBanner,
  facts,
  heading,
  id,
  jsonTree,
  none,
  num,
  numCell,
  pill,
  readMember,
  rowLink,
  runBundle,
  runLinks,
  section,
  table,
  text,
} from "./common.js";

export const name = "certificate";
export const pattern = "/job/{jid}/certificate";

export const NEAR_THRESHOLD_TEXT =
  "near-threshold means tol/10 < |v| ≤ 10·tol (ADR 0007 D2.4); the flag is read from each check, never computed here.";

// The rows a run's records describe, and whether the equation links may be used (§6.5's guard).
export async function runStructure(api, bundle, run, { signal } = {}) {
  const recorded = await readMember(api, bundle, "structural-report.json", { signal });
  const structure = run
    ? await api.readWhole("inspect_structure", { revision_id: run.revision_id }, { signal })
    : null;
  const consistent = structure !== null && sameStructure(structure, recorded?.document);
  return { structure, recorded, consistent, index: structureIndex(structure) };
}

export async function load(params, api) {
  const { jid, signal } = params;
  const bundle = await runBundle(api, jid, { signal });
  const certificate = await readMember(api, bundle, "solution-certificate.json", { signal });
  const revision = await readMember(api, bundle, "revision.json", { signal });
  const rows = await runStructure(api, bundle, bundle.run, { signal });
  return { jid, run: bundle.run, certificate, revision, rows };
}

function subjectCell(data, subject) {
  if (subject === null || subject === undefined) return DASH;
  if (data.rows.consistent && data.rows.index.row(subject)) {
    return rowLink("job", data.jid, subject);
  }
  return id(subject);
}

function checkTable(data, checks) {
  return table(
    [
      "id",
      "subject",
      { text: "value", num: true },
      { text: "tolerance", num: true },
      { text: "reference", num: true },
      { text: "scaled", num: true },
      "result",
      "near-threshold",
    ],
    checks.map((check) => [
      id(check.id),
      subjectCell(data, check.subject),
      numCell(check.value),
      numCell(check.tolerance),
      numCell(check.reference),
      check.category === "residual" ? numCell(scaledResidual(check)) : h("td", { class: "num" }, DASH),
      pill(check.result),
      check.near_threshold === true ? pill("near_threshold") : DASH,
    ]),
  );
}

export function phaseSection(certificate, revision) {
  const entries = phaseBranches(certificate.phase_branch, componentsOf(revision?.document));
  if (entries.length === 0) return none();
  const splits = entries.filter((entry) => entry.split);
  const states = entries.filter((entry) => !entry.split);
  return [
    states.length > 0
      ? facts(states.map((entry) => [entry.key, text(entry.state)]))
      : null,
    splits.map((entry) =>
      h(
        "div",
        { class: "phase-split", "data-ofs-split": entry.key },
        h("h3", null, entry.key),
        table(
          ["phase", ...entry.components.map((c) => ({ text: c, num: true })), { text: "total", num: true }],
          [
            ["liquid", ...entry.liquid.map((x) => numCell(x)), numCell(entry.liquid_total)],
            ["vapor", ...entry.vapor.map((x) => numCell(x)), numCell(entry.vapor_total)],
          ],
        ),
        h("p", null, "vapour fraction vapor_total / (vapor_total + liquid_total): ", num(entry.vapour_fraction)),
      ),
    ),
  ];
}

export function view(data) {
  const { certificate, run } = data;
  const head = heading(`Certificate — ${data.jid}`, ...runLinks(data.jid));
  if (certificate === null) {
    return h(
      "div",
      { "data-ofs-screen": "certificate" },
      head,
      section(
        "Certificate",
        none(`no certificate recorded for this run (outcome ${run?.outcome ?? "not recorded"})`),
      ),
    );
  }
  const cert = certificate.document;
  const groups = checkGroups(cert.checks);
  return h(
    "div",
    { "data-ofs-screen": "certificate" },
    head,
    digestBanner("solution-certificate.json", certificate.digest),
    section(
      "Status",
      h("p", null, pill(cert.verification_status)),
      facts([
        ["checks", num((cert.checks ?? []).length)],
        ["near-threshold checks", num(nearThresholdCount(cert.checks))],
        ["certificate", id(cert.certificate_id)],
        ["policy", text(cert.policy_id)],
        ["check policy", text(cert.check_policy_id)],
        ["model version", id(cert.model_version)],
      ]),
      h("p", { class: "muted" }, NEAR_THRESHOLD_TEXT),
      data.rows.consistent
        ? null
        : h(
            "p",
            { class: "notice" },
            "this run used a different equation structure than the server's current analysis of its revision",
          ),
    ),
    section(
      "Checks",
      groups.map((group) =>
        h(
          "div",
          { class: "check-group", "data-ofs-category": group.category },
          h("h3", null, `${group.category} (${group.count})`),
          group.results.map((bucket) =>
            h(
              "div",
              { class: "check-bucket" },
              h("p", null, pill(bucket.result), ` ${bucket.count}`),
              checkTable(data, bucket.checks),
            ),
          ),
        ),
      ),
    ),
    section(
      "Limitations",
      table(
        ["check", "kind", { text: "threshold", num: true }, { text: "value", num: true }],
        (cert.limitations ?? []).map((entry) => [
          id(entry.check),
          entry.kind === "near_threshold" ? pill("near_threshold") : text(entry.kind),
          numCell(entry.threshold),
          numCell(entry.value),
        ]),
      ),
    ),
    section("Regularity", cert.regularity ? jsonTree(cert.regularity) : none()),
    section(
      "Solution-error bound",
      facts([["solution_error_bound_scaled", num(cert.solution_error_bound_scaled)]]),
      (cert.statements ?? []).length === 0
        ? none()
        : h("ul", null, cert.statements.map((statement) => h("li", null, statement))),
    ),
    section(
      "Branch provenance",
      table(
        ["attempt", "core", "core outcome", "opening source", "initializer source", "cause", "decision"],
        (cert.branch_provenance ?? []).map((entry) => [
          num(entry.attempt),
          text(entry.core),
          pill(entry.core_outcome),
          text(entry.opening_source),
          text(entry.initializer_source),
          text(entry.cause),
          text(entry.decision),
        ]),
      ),
    ),
    section("Phase branch", phaseSection(cert, data.revision)),
    section("Transformations", cert.transformations ? jsonTree(cert.transformations) : none()),
  );
}
