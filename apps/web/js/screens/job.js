// #/job/{jid} — a run: summary, attempts, trace, plan, bundle files; live while it runs
// (M06 design note §6.3, §5.4 "Live jobs").
//
// Reads `get_job` and every job event (`list_job_events`); for an ended job `get_job_result`,
// the bundle listing, and through the raw export (digest-checked) the solve events, run manifest,
// execution plan, solve path and, when listed, the certificate (its `branch_provenance` is the
// recovery path). For a job that has not ended, `follow` loops `wait_job` — one outstanding call,
// ended on navigation — appending events, and loads the screen again once the job has ended.
// Attempt counters are rule 1's deltas; every other value is shown as recorded.

import { h, replace } from "../h.js";
import { attemptsOf, signatureText } from "../model/attempts.js";
import { filterTrace, pageOf, TRACE_COLUMNS, traceChoices, traceRows } from "../model/trace.js";
import { link } from "../router.js";
import { DASH } from "../text.js";
import {
  allEvents,
  digestBanner,
  facts,
  heading,
  id,
  none,
  num,
  numCell,
  pill,
  readMember,
  revisionLink,
  runBundle,
  runLinks,
  section,
  table,
  TERMINAL,
  text,
} from "./common.js";

export const name = "job";
export const pattern = "/job/{jid}";

// The members of a run's bundle the run screen reads (§6).
export const RUN_MEMBERS = [
  "solve-events.json",
  "run-manifest.json",
  "execution-plan.json",
  "solve-path.json",
  "solution-certificate.json",
];
const COUNTERS = ["property_calls", "residual_calls", "jacobian_calls", "factorizations"];

export async function load(params, api) {
  const { jid, signal, query } = params;
  const job = await api.call("get_job", { job_id: jid }, { signal });
  const events = await allEvents(api, jid, { signal });
  const ended = TERMINAL.has(job.status);
  let bundle = null;
  const members = {};
  if (ended) {
    bundle = await runBundle(api, jid, { signal });
    if (bundle.listing) {
      for (const member of RUN_MEMBERS) members[member] = await readMember(api, bundle, member, { signal });
    }
  }
  return {
    jid,
    job,
    events,
    ended,
    bundle,
    members,
    filter: {
      kind: query?.get("kind") ?? "",
      attempt: query?.get("attempt") ?? "",
      page: Number(query?.get("page") ?? 0) || 0,
    },
    rights: params.project?.rights ?? [],
    cancel: () => api.call("cancel_job", { job_id: jid }, { signal }),
    download: async (member) => {
      const read = await api.raw(member.artifact_id, member.sha256);
      return { bytes: read.bytes, digest: read.digest };
    },
    go: params.go,
  };
}

// §5.4: follow a job that has not ended — `wait_job` from the last event seen, each answer's
// events appended and the view drawn again by `render(view(data))`; once the job has ended, the
// screen is loaded again (`go` to the same route). Returns when the job ends or on abort.
export async function follow(data, api, { signal, render }) {
  if (data.ended) return;
  const last = data.events.length > 0 ? data.events[data.events.length - 1].sequence : -1;
  await api.followJob(data.jid, {
    afterSequence: last,
    signal,
    onWait: (waited) => {
      data.events = [...data.events, ...waited.events];
      data.job = waited.job;
      if (!signal?.aborted) render(view(data));
    },
  });
  if (!signal?.aborted) data.go(link("/job/{jid}", { jid: data.jid }));
}

function eventDetail(event) {
  if (event.progress) {
    const { stage, completed, total } = event.progress;
    return `${stage} ${completed}/${total}`;
  }
  if (event.output) return event.output.name;
  if (event.ending) return `${event.ending.status} (${event.ending.reason})`;
  if (event.error) return `${event.error.code}: ${event.error.message}`;
  return DASH;
}

function cancelControl(data) {
  if (data.ended) return null;
  const allowed = data.rights.includes("execute");
  const onClick = async (event) => {
    const button = event.currentTarget;
    const status = button.parentNode.querySelector("[data-ofs-slot=cancel-status]");
    button.disabled = true;
    try {
      await data.cancel();
    } catch (error) {
      button.disabled = false;
      const code = error?.document?.code ?? "error";
      replace(h("span", null, ` refused: ${code} — ${error?.document?.message ?? error?.message ?? ""}`), status);
      return;
    }
    data.go(link("/job/{jid}", { jid: data.jid }));
  };
  return h(
    "p",
    null,
    h(
      "button",
      allowed
        ? { type: "button", "data-ofs-action": "cancel", on: { click: onClick } }
        : { type: "button", "data-ofs-action": "cancel", disabled: true, title: "needs the execute right" },
      "Cancel",
    ),
    allowed ? null : h("span", { class: "muted" }, " needs the execute right"),
    h("output", { "data-ofs-slot": "cancel-status", class: "muted" }),
  );
}

function attemptsSection(events) {
  const { attempts, totals, outside } = attemptsOf(events);
  const counterCells = (values) => COUNTERS.map((counter) => numCell(values?.[counter]));
  return section(
    "Attempts",
    table(
      [
        "step",
        "attempt",
        "phase signature",
        "outcome",
        { text: "iterations", num: true },
        ...COUNTERS.map((counter) => ({ text: `Δ ${counter}`, num: true })),
      ],
      [
        ...attempts.map((attempt) => [
          num(attempt.step_index),
          num(attempt.attempt),
          text(signatureText(attempt.signature)),
          pill(attempt.outcome),
          numCell(attempt.iterations),
          ...counterCells(attempt.deltas),
        ]),
        ...(totals
          ? [
              h("tr", { "data-ofs-row": "outside" }, h("td", { colspan: "5" }, "outside attempts"), counterCells(outside)),
              h("tr", { "data-ofs-row": "totals" }, h("td", { colspan: "5" }, "totals (final event)"), counterCells(totals)),
            ]
          : []),
      ],
      { empty: "no attempts recorded" },
    ),
    h(
      "p",
      { class: "muted" },
      "Δ = an attempt's closing counters minus its opening counters (homotopy correctors are not attempts).",
    ),
  );
}

function traceSection(data, events) {
  const rows = traceRows(events);
  const { kinds, attempts } = traceChoices(rows);
  const filtered = filterTrace(rows, data.filter);
  const page = pageOf(filtered, data.filter.page);
  const to = (changes) =>
    link("/job/{jid}", { jid: data.jid }, {
      kind: data.filter.kind || null,
      attempt: data.filter.attempt === "" ? null : data.filter.attempt,
      ...changes,
    });
  const choose = (label, key, values) =>
    h(
      "span",
      { class: "inline-list" },
      `${label}: `,
      h("a", { href: to({ [key]: null, page: null }) }, "any"),
      values.map((value) => [" ", h("a", { href: to({ [key]: value, page: null }) }, String(value))]),
    );
  return section(
    "Trace",
    h("p", null, choose("kind", "kind", kinds)),
    h("p", null, choose("attempt", "attempt", attempts)),
    h(
      "p",
      { class: "muted" },
      `rows ${page.first}–${page.last} of ${filtered.length} (${rows.length} events)`,
      page.page > 0 ? [" ", h("a", { href: to({ page: page.page - 1 }) }, "previous")] : null,
      page.page + 1 < page.pages ? [" ", h("a", { href: to({ page: page.page + 1 }) }, "next")] : null,
    ),
    table(
      TRACE_COLUMNS.map(([key, header]) =>
        ["kind", "trial_status", "rejection_reason", "outcome", "state"].includes(key)
          ? header
          : { text: header, num: true },
      ),
      page.rows.map((row) =>
        TRACE_COLUMNS.map(([key]) => {
          const value = row[key];
          if (key === "outcome") return value === undefined ? DASH : pill(value);
          if (key === "state") return value === undefined ? DASH : h("span", { class: "id", title: row.state_sha256 }, value);
          if (typeof value === "string") return value;
          return numCell(value);
        }),
      ),
      { empty: "no trace events" },
    ),
  );
}

function filesSection(data) {
  const files = data.bundle?.listing?.files ?? [];
  const onDownload = (member) => async () => {
    const read = await data.download(member);
    const url = URL.createObjectURL(new Blob([read.bytes], { type: "application/json" }));
    const anchor = globalThis.document.createElement("a");
    anchor.href = url;
    anchor.download = member.name;
    anchor.click();
    URL.revokeObjectURL(url);
  };
  return section(
    "Bundle files",
    table(
      ["name", "kind", { text: "bytes", num: true }, "sha256", "digest", "view", "download"],
      files.map((member) => {
        const read = data.members[member.name];
        return [
          id(member.name),
          text(member.kind),
          numCell(member.size_bytes),
          id(member.sha256.slice(0, 12)),
          read ? read.digest : "not read here",
          h("a", { href: link("/job/{jid}/file/{name}", { jid: data.jid, name: member.name }) }, "JSON"),
          h("button", { type: "button", on: { click: onDownload(member) } }, "download"),
        ];
      }),
    ),
  );
}

export function view(data) {
  const { job } = data;
  const run = data.bundle?.run ?? null;
  const manifest = data.members["run-manifest.json"]?.document ?? null;
  const solvePath = data.members["solve-path.json"]?.document ?? null;
  const plan = data.members["execution-plan.json"]?.document ?? null;
  const certificate = data.members["solution-certificate.json"]?.document ?? null;
  const solveEvents = data.members["solve-events.json"]?.document ?? null;
  const banners = Object.values(data.members)
    .filter(Boolean)
    .map((read) => digestBanner(read.name, read.digest));
  return h(
    "div",
    { "data-ofs-screen": "job", "data-ofs-live": data.ended ? "0" : "1" },
    heading(`Run ${data.jid}`, ...runLinks(data.jid)),
    banners,
    section(
      "Summary",
      facts([
        ["job", id(job.job_id)],
        ["status", pill(job.status)],
        ["run", id(run?.run_id)],
        ["revision", revisionLink(job.request?.body?.revision_id)],
        ["policy requested", text(job.request?.body?.policy_id)],
        ["policy", text(run?.policy_id)],
        ["solve path", text(run?.solve_path ?? solvePath?.solve_path)],
        ["route reason", text(solvePath?.route_reason)],
        ["outcome", run ? pill(run.outcome) : DASH],
        ["verification", run ? pill(run.verification_status) : DASH],
        ["created", text(job.created_at)],
        ["started", text(job.started_at)],
        ["ended", text(job.ended_at)],
        ["elapsed seconds (run manifest)", num(manifest?.elapsed_seconds)],
      ]),
      job.error ? h("p", { class: "notice notice-bad" }, `${job.error.code}: ${job.error.message}`) : null,
      cancelControl(data),
    ),
    section(
      data.ended ? "Job events" : "Job events (live)",
      table(
        [{ text: "sequence", num: true }, "kind", "recorded", "detail"],
        data.events.map((event) => [numCell(event.sequence), event.kind, text(event.recorded_at), eventDetail(event)]),
      ),
    ),
    solveEvents ? attemptsSection(solveEvents) : section("Attempts", none(data.ended ? "no solve events recorded" : "the job has not ended")),
    section(
      "Recovery path",
      certificate
        ? table(
            ["attempt", "opening source", "initializer source", "cause", "decision"],
            (certificate.branch_provenance ?? []).map((entry) => [
              num(entry.attempt),
              text(entry.opening_source),
              text(entry.initializer_source),
              text(entry.cause),
              text(entry.decision),
            ]),
          )
        : none("no certificate recorded for this run"),
    ),
    solveEvents ? traceSection(data, solveEvents) : null,
    section(
      "Execution plan",
      plan
        ? [
            facts([
              ["plan", id(plan.plan_id)],
              ["policy", text(plan.policy_id)],
              ["steps", num((plan.steps ?? []).length)],
            ]),
            table(
              ["index", "kind", "signature units"],
              (plan.steps ?? []).map((step) => [num(step.index), text(step.kind), text((step.signature_units ?? []).join(", "))]),
            ),
          ]
        : none(),
    ),
    data.bundle ? filesSection(data) : null,
  );
}
