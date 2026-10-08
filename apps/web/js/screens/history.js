// #/history — the agent history (M06 design note §6.8, §4.3).
//
// Reads `list_audit` (descending; the caller's own rows by default — `?principal=all` or another
// principal needs the policy right, and the selector greys those choices without it; a refusal
// is shown as the server's code). `?row=<seq>` adds that row's detail: for a commit, its expected
// revision (= the revision's parent, rule 6), the element diff from the parent and the
// revision's validation as the server computes it now; for a job, the request, status, outcome
// and verification. The screen shows what the project recorded, never what an agent said.

import { h } from "../h.js";
import { revisionComparison } from "../model/compare.js";
import { detailOf, expectedRevision, historyRows, principalsOf } from "../model/history.js";
import { link } from "../router.js";
import { DASH } from "../text.js";
import {
  facts,
  heading,
  id,
  jobLink,
  none,
  PAGE,
  pill,
  revisionLink,
  section,
  table,
  TERMINAL,
  text,
} from "./common.js";

export const name = "history";
export const pattern = "/history";

export const STATEMENT =
  "This is what the project recorded — every effect and every refusal — not what an agent said.";

async function commitDetail(api, revisionId, signal) {
  const revision = await api.readWhole("get_revision", { revision_id: revisionId }, { signal });
  const parent = expectedRevision(revision);
  let diff = null;
  let before = null;
  if (parent !== null) {
    diff = await api.call("diff_revisions", { from_revision: parent, to_revision: revisionId }, { signal });
    before = await api.readWhole("get_revision", { revision_id: parent }, { signal });
  }
  const validation = await api.call(
    "validate",
    { revision_id: revisionId, task: "simulation" },
    { signal },
  );
  return {
    kind: "commit",
    revisionId,
    parent,
    comparison: diff ? revisionComparison(diff, before, revision) : null,
    validation,
  };
}

async function jobDetail(api, jobId, signal) {
  const job = await api.call("get_job", { job_id: jobId }, { signal });
  const result = TERMINAL.has(job.status)
    ? await api.call("get_job_result", { job_id: jobId }, { signal })
    : null;
  return { kind: "job", jobId, job, run: result?.run_result ?? null };
}

export async function load(params, api) {
  const { signal, query, project } = params;
  const own = project?.principal_id ?? null;
  const chosen = query?.get("principal") || own;
  const cursor = query?.get("cursor") || null;
  const args = { order: "descending", limit: PAGE.audit };
  if (chosen !== "all") args.principal_id = chosen;
  if (cursor) args.cursor = cursor;
  let page = null;
  let refused = null;
  try {
    page = await api.call("list_audit", args, { signal });
  } catch (error) {
    if (error?.status === 403 && error.document) refused = error.document;
    else throw error;
  }
  const rows = historyRows(page);
  const seq = query?.get("row");
  const selected = seq ? (rows.find((row) => String(row.seq) === seq) ?? null) : null;
  const wanted = detailOf(selected);
  let detail = null;
  if (wanted?.kind === "commit") detail = await commitDetail(api, wanted.revision, signal);
  else if (wanted?.kind === "job") detail = await jobDetail(api, wanted.job, signal);
  return {
    own,
    chosen,
    canSeeOthers: (project?.rights ?? []).includes("policy"),
    rows,
    next: page?.next_cursor ?? null,
    refused,
    selected,
    detail,
    serverVersion: project?.server?.package_version ?? null,
    go: params.go,
  };
}

function hereLink(data, changes) {
  return link("/history", {}, {
    principal: data.chosen === data.own ? null : data.chosen,
    ...changes,
  });
}

function selector(data) {
  const choices = principalsOf(data.rows, data.own);
  const onChange = (event) => {
    const value = event.currentTarget.value;
    data.go(link("/history", {}, { principal: value === data.own ? null : value }));
  };
  return h(
    "p",
    null,
    h("label", { for: "ofs-history-principal" }, "principal "),
    h(
      "select",
      { id: "ofs-history-principal", name: "principal", on: { change: onChange } },
      h("option", { value: data.own, selected: data.chosen === data.own }, `${data.own} (own)`),
      h(
        "option",
        { value: "all", selected: data.chosen === "all", disabled: !data.canSeeOthers },
        "all principals",
      ),
      choices
        .filter((principal) => principal !== data.own)
        .map((principal) =>
          h("option", { value: principal, selected: data.chosen === principal, disabled: !data.canSeeOthers }, principal),
        ),
    ),
    data.canSeeOthers ? null : h("span", { class: "muted" }, " other principals need the policy right"),
  );
}

function effectCell(effect) {
  if (effect === null) return DASH;
  if (effect.target?.screen === "revision") return [`${effect.kind}: `, revisionLink(effect.id)];
  if (effect.target?.screen === "job") return [`${effect.kind}: `, jobLink(effect.id)];
  return `${effect.kind}: ${effect.id}`;
}

function detailSection(data) {
  const { selected, detail } = data;
  if (!selected) return null;
  const title = `Row ${selected.seq}: ${selected.operation}`;
  if (selected.outcome !== "allowed") {
    return section(title, h("p", null, pill(selected.outcome), " ", text(selected.code)));
  }
  if (detail === null) return section(title, none("no detail for this kind of effect"));
  if (detail.kind === "commit") {
    const comparison = detail.comparison;
    return section(
      title,
      facts([
        ["revision", revisionLink(detail.revisionId)],
        ["expected revision (its parent)", detail.parent ? revisionLink(detail.parent) : "none (the first revision)"],
        ["idempotency key", text(selected.key)],
      ]),
      h("h3", null, "Element diff from the parent"),
      comparison === null
        ? none("no parent: nothing to compare")
        : comparison.elements.length === 0
          ? none(comparison.orderOnly.length > 0 ? `order changed only: ${comparison.orderOnly.join(", ")}` : "no element-level changes recorded")
          : table(
              ["member", "id", "change", "paths"],
              comparison.elements.map((element) => [
                text(element.member),
                id(element.id),
                text(element.change),
                element.paths.map((entry) => entry.path.join(" › ")).join("; ") || DASH,
              ]),
            ),
      detail.parent
        ? h("p", null, h("a", { href: link("/compare/rev/{a}/{b}", { a: detail.parent, b: detail.revisionId }) }, "values before and after"))
        : null,
      h("h3", null, `Validation, validated now by server ${data.serverVersion ?? DASH}`),
      h("p", null, pill(detail.validation.status)),
      h(
        "p",
        { class: "muted" },
        "The validation the agent received at commit time is in the ledger, which this contract does not expose; this is the server's validation of the same revision now.",
      ),
    );
  }
  const body = detail.job.request?.body ?? {};
  return section(
    title,
    facts([
      ["job", jobLink(detail.jobId)],
      ["revision", revisionLink(body.revision_id)],
      ["policy", text(body.policy_id)],
      ["idempotency key", text(detail.job.request?.idempotency_key)],
      ["status", pill(detail.job.status)],
      ["outcome", detail.run ? pill(detail.run.outcome) : DASH],
      ["verification", detail.run ? pill(detail.run.verification_status) : DASH],
    ]),
  );
}

export function view(data) {
  return h(
    "div",
    { "data-ofs-screen": "history" },
    heading("Agent history"),
    h("p", { class: "muted" }, STATEMENT),
    selector(data),
    data.refused
      ? section(
          "Refused",
          h("p", { "data-ofs-refused": data.refused.code }, pill("refused"), ` ${data.refused.code}: ${data.refused.message}`),
        )
      : section(
          data.chosen === "all" ? "All principals" : `Principal ${data.chosen}`,
          table(
            ["seq", "time", "principal", "capability", "operation", "outcome", "effect", "idempotency key", ""],
            data.rows.map((row) => [
              String(row.seq),
              text(row.at),
              text(row.principal),
              id(row.capability),
              text(row.operation),
              [pill(row.outcome), row.code ? ` ${row.code}` : null],
              effectCell(row.effect),
              id(row.key),
              h("a", { href: hereLink(data, { row: String(row.seq) }) }, "detail"),
            ]),
          ),
          data.next ? h("p", null, h("a", { href: hereLink(data, { cursor: data.next }) }, "older rows")) : null,
        ),
    detailSection(data),
  );
}
