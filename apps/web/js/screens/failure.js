// #/job/{jid}/failure — the failure bundle (M06 design note §6.4).
//
// Reads the run's result and bundle listing, then `failure-bundle.json` through the raw export
// (digest-checked). Observations and inferred causes are kept apart, each cause with its
// recorded `kind` (e.g. "hypothesis"): the bundle's inference is shown as the bundle labels it,
// never promoted to a finding. Every empty section reads "none recorded".

import { h } from "../h.js";
import { signatureText } from "../model/attempts.js";
import { link } from "../router.js";
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
  runBundle,
  runLinks,
  section,
  table,
  text,
} from "./common.js";

export const name = "failure";
export const pattern = "/job/{jid}/failure";

export async function load(params, api) {
  const { jid, signal } = params;
  const bundle = await runBundle(api, jid, { signal });
  const failure = await readMember(api, bundle, "failure-bundle.json", { signal });
  return { jid, run: bundle.run, failure };
}

const OBSERVED = ["attempts", "closing_event", "iterations", "message", "residual_inf_unscaled"];

function counters(values) {
  if (!values) return none();
  return table(
    ["counter", { text: "value", num: true }],
    Object.entries(values).map(([counter, value]) => [counter, numCell(value)]),
  );
}

export function view(data) {
  const { failure, run } = data;
  const head = heading(`Failure bundle — ${data.jid}`, ...runLinks(data.jid));
  if (failure === null) {
    return h(
      "div",
      { "data-ofs-screen": "failure" },
      head,
      section(
        "Failure bundle",
        none(`no failure bundle recorded for this run (outcome ${run?.outcome ?? "not recorded"})`),
      ),
    );
  }
  const bundle = failure.document;
  const observations = bundle.observations ?? {};
  const identity = bundle.replay_identity ?? {};
  const checkpoint = bundle.best_checkpoint ?? null;
  const revisionId = run?.revision_id ?? null;
  return h(
    "div",
    { "data-ofs-screen": "failure" },
    head,
    digestBanner("failure-bundle.json", failure.digest),
    section(
      "Outcome",
      h("p", null, pill(bundle.outcome)),
      facts([["taxonomy", text(bundle.taxonomy)]]),
    ),
    section(
      "Observations",
      h("p", { class: "muted" }, "What the solve recorded."),
      facts(
        OBSERVED.filter((key) => key in observations).map((key) => [
          key,
          typeof observations[key] === "number" ? num(observations[key]) : text(observations[key]),
        ]),
      ),
      h("h3", null, "counters"),
      counters(observations.counters),
      h("h3", null, "last linear solve"),
      observations.last_linear ? jsonTree(observations.last_linear) : none(),
    ),
    section(
      "Inferred causes",
      h("p", { class: "muted" }, "What the bundle infers from the observations, labelled by kind."),
      table(
        ["kind", "cause", "rule"],
        (bundle.inferred_causes ?? []).map((cause) => [
          h("strong", { "data-ofs-cause-kind": text(cause.kind) }, text(cause.kind)),
          text(cause.cause),
          text(cause.rule),
        ]),
      ),
    ),
    section(
      "Implicated sources",
      (bundle.implicated_sources ?? []).length === 0
        ? none()
        : h(
            "ul",
            { class: "inline-list" },
            bundle.implicated_sources.map((source) => {
              const label = id(typeof source === "string" ? source : JSON.stringify(source));
              return h(
                "li",
                null,
                revisionId ? h("a", { href: link("/rev/{rid}", { rid: revisionId }) }, label) : label,
              );
            }),
          ),
    ),
    section(
      "Attempt tree",
      table(
        ["attempt", "phase signature", "outcome", { text: "iterations", num: true }],
        (bundle.attempt_tree ?? []).map((attempt) => [
          num(attempt.attempt),
          text(signatureText(attempt.signature)),
          pill(attempt.outcome),
          numCell(attempt.iterations),
        ]),
      ),
    ),
    section(
      "Replay identity",
      facts([
        ["model_version", id(identity.model_version || null)],
        ["constants_sha256", id(identity.constants_sha256 || null)],
        ["policy_id", text(identity.policy_id)],
        ["plan_id", id(identity.plan_id || null)],
      ]),
    ),
    section(
      "Best checkpoint",
      checkpoint === null
        ? none()
        : facts([
            ["state_sha256", id(checkpoint.state_sha256)],
            ["verification_scope", text(checkpoint.verification_scope)],
            ["label", text(checkpoint.label)],
            ["checkpoint", id(checkpoint.checkpoint_id)],
            ["residual_inf_unscaled", num(checkpoint.residual_inf_unscaled)],
          ]),
    ),
    section("Check report", bundle.check_report ? jsonTree(bundle.check_report) : none()),
    section(
      "Suggested actions",
      table(
        ["action", "preconditions", "requires permission"],
        (bundle.suggested_actions ?? []).map((action) => [
          text(action.action),
          text(action.preconditions),
          action.requires_permission === undefined ? DASH : String(action.requires_permission),
        ]),
      ),
    ),
  );
}
