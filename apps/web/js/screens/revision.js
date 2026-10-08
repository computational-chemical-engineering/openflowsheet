// #/rev/{rid} — the revision overview (M06 design note §6.1).
//
// Reads the revision whole (`get_revision`), its validation (`validate`, task "simulation"), the
// project's jobs (`list_jobs`, every page; the runs of this revision are a filter, rule 6) with
// each ended run's result (`get_job_result`), `list_models`, and the revision's summary row
// (`list_revisions`: principal, creation time and content SHA-256 are not in the document).
// Values are shown as written. **Solve** submits exactly §6.1's body under an idempotency key
// drawn when the dialog opens and reused on a retry.

import { h, replace } from "../h.js";
import { layout } from "../model/layout.js";
import { jobsOfRevision } from "../model/history.js";
import { link } from "../router.js";
import { DASH } from "../text.js";
import {
  allPages,
  facts,
  heading,
  id,
  jobLink,
  jsonTree,
  MAX_PAGES,
  num,
  numCell,
  PAGE,
  pill,
  revisionLink,
  section,
  table,
  TERMINAL,
  text,
} from "./common.js";

export const name = "revision";
export const pattern = "/rev/{rid}";

// `ui-solve-<32 lowercase hex>` from `crypto.getRandomValues` (§6.1).
export function newSolveKey(random = (bytes) => globalThis.crypto.getRandomValues(bytes)) {
  const bytes = random(new Uint8Array(16));
  return `ui-solve-${Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("")}`;
}

// The Solve action of one revision: `open()` draws a fresh key (the dialog opened); `submit(p)`
// sends §6.1's body under the current key — the same key on every retry until the dialog is
// opened again — and resolves `{job}` or `{error}`.
export function solveAction(api, revisionId, { random } = {}) {
  let key = null;
  return {
    open() {
      key = newSolveKey(random);
      return key;
    },
    key: () => key,
    async submit(policyId) {
      if (key === null) key = newSolveKey(random);
      const request = {
        operation: "solve",
        idempotency_key: key,
        body: { revision_id: revisionId, policy_id: policyId },
      };
      try {
        const answer = await api.call("submit_job", request);
        return { job: answer.job };
      } catch (error) {
        return { error };
      }
    },
  };
}

// The policies the Solve dialog offers: the project's default first, then every listed policy.
export function policyChoices(project) {
  const listed = (project?.solve_policies ?? []).map((policy) => policy.policy_id);
  const first = project?.default_policy_id;
  return first && !listed.includes(first) ? [first, ...listed] : listed;
}

export async function load(params, api) {
  const { rid, signal } = params;
  const revision = await api.readWhole("get_revision", { revision_id: rid }, { signal });
  const validation = await api.call(
    "validate",
    { revision_id: rid, task: "simulation" },
    { signal },
  );
  const revisions = await allPages(
    (args) => api.call("list_revisions", args, { signal }),
    { limit: PAGE.revisions },
    { max: MAX_PAGES },
  );
  const jobs = await allPages((args) => api.call("list_jobs", args, { signal }), {
    limit: PAGE.jobs,
  });
  const runs = [];
  for (const job of jobsOfRevision(jobs.items, rid)) {
    const ended = TERMINAL.has(job.status);
    const result = ended ? await api.call("get_job_result", { job_id: job.job_id }, { signal }) : null;
    runs.push({ job, run: result?.run_result ?? null });
  }
  const models = await api.call("list_models", {}, { signal });
  return {
    rid,
    revision,
    summary: revisions.items.find((item) => item.revision_id === rid) ?? null,
    validation,
    runs,
    models,
    project: params.project,
    solve: solveAction(api, rid),
    go: params.go,
  };
}

// ------------------------------------------------------------------------------- flowsheet

export function flowsheetSvg(revision) {
  const drawn = layout(revision);
  return h(
    "svg",
    {
      class: "flowsheet",
      viewBox: `0 0 ${drawn.width} ${drawn.height}`,
      width: String(drawn.width),
      height: String(drawn.height),
      role: "img",
      "aria-label": "flowsheet",
    },
    h(
      "defs",
      null,
      h(
        "marker",
        {
          id: "ofs-arrow",
          viewBox: "0 0 10 10",
          refX: "10",
          refY: "5",
          markerWidth: "6",
          markerHeight: "6",
          orient: "auto",
        },
        h("path", { d: "M 0 0 L 10 5 L 0 10 z", class: "arrow-head" }),
      ),
    ),
    drawn.edges.map((edge) =>
      h(
        "g",
        { class: edge.back ? "edge edge-back" : "edge", "data-edge": edge.id },
        h("path", { d: edge.d, "marker-end": "url(#ofs-arrow)" }),
        edge.label
          ? h("text", { x: String(edge.label.x), y: String(edge.label.y), "text-anchor": "middle" }, edge.label.text)
          : null,
      ),
    ),
    drawn.nodes.map((node) =>
      h(
        "g",
        { class: "node", "data-node": node.id, "data-layer": String(node.layer) },
        h("rect", {
          x: String(node.x),
          y: String(node.y),
          width: String(node.w),
          height: String(node.h),
          rx: "4",
        }),
        h("text", { x: String(node.x + 8), y: String(node.y + 18), class: "node-id" }, node.id),
        h("text", { x: String(node.x + 8), y: String(node.y + 34), class: "node-model" }, node.model ?? DASH),
      ),
    ),
  );
}

// ------------------------------------------------------------------------------------ views

function solveDialog(data) {
  const rights = data.project?.rights ?? [];
  const allowed = rights.includes("execute");
  if (!allowed) {
    return h(
      "p",
      null,
      h("button", { type: "button", disabled: true, title: "needs the execute right" }, "Solve…"),
      h("span", { class: "muted" }, " needs the execute right"),
    );
  }
  const policies = policyChoices(data.project);
  const onOpen = (event) => {
    const dialog = event.currentTarget.parentNode;
    if (!dialog.open) data.solve.open(); // opening: a fresh key; closing keeps it
  };
  const onSubmit = async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const policy = form.elements.namedItem("policy").value;
    const status = form.querySelector("[data-ofs-slot=solve-status]");
    replace(h("span", null, "submitting…"), status);
    const answer = await data.solve.submit(policy);
    if (answer.job) {
      data.go(link("/job/{jid}", { jid: answer.job.job_id }));
      return;
    }
    const code = answer.error?.document?.code ?? "error";
    const message = answer.error?.document?.message ?? answer.error?.message ?? "";
    replace(
      h("span", null, `refused: ${code} — ${message} (submit again to retry with the same key)`),
      status,
    );
  };
  return h(
    "details",
    { class: "solve", "data-ofs-action": "solve" },
    h("summary", { on: { click: onOpen } }, "Solve…"),
    h(
      "form",
      { on: { submit: onSubmit } },
      h("label", { for: "ofs-solve-policy" }, "policy "),
      h(
        "select",
        { id: "ofs-solve-policy", name: "policy" },
        policies.map((policy) =>
          h("option", { value: policy, selected: policy === data.project.default_policy_id }, policy),
        ),
      ),
      " ",
      h("button", { type: "submit" }, "submit"),
      h("output", { "data-ofs-slot": "solve-status", class: "muted" }),
    ),
  );
}

function endpoint(end) {
  return end ? `${end.instance}.${end.port}` : DASH;
}

function specificationTarget(target) {
  if (!target) return DASH;
  const parts = [target.object_type, target.object_id, target.path, target.component].filter(
    (part) => part !== null && part !== undefined,
  );
  return parts.join(" ");
}

export function view(data) {
  const { revision, summary, validation } = data;
  const counts = Object.entries(validation.structural_counts ?? {});
  return h(
    "div",
    { "data-ofs-screen": "revision" },
    heading(
      text(revision.title),
      h("a", { href: link("/rev/{rid}/validation", { rid: data.rid }) }, "validation and DOF"),
      revision.parent_revision
        ? h(
            "a",
            { href: link("/compare/rev/{a}/{b}", { a: revision.parent_revision, b: data.rid }) },
            "compare with parent",
          )
        : null,
    ),
    section(
      "Revision",
      facts([
        ["revision", id(revision.revision_id ?? data.rid)],
        ["content sha256", id(summary?.content_sha256?.slice(0, 12))],
        ["parent", revisionLink(revision.parent_revision)],
        ["principal", text(summary?.principal_id)],
        ["created", text(summary?.created_at)],
      ]),
      h("p", null, h("span", null, "validation: "), pill(validation.status)),
      counts.length > 0
        ? facts(counts.map(([key, value]) => [key, num(value)]))
        : null,
      solveDialog(data),
    ),
    section(
      "Runs of this revision",
      table(
        ["created", "job", "policy", "status", "outcome", "verification"],
        data.runs.map(({ job, run }) => [
          text(job.created_at),
          jobLink(job.job_id),
          text(job.request?.body?.policy_id),
          pill(job.status),
          run ? pill(run.outcome) : DASH,
          run ? pill(run.verification_status) : DASH,
        ]),
      ),
    ),
    section("Flowsheet", flowsheetSvg(revision)),
    section(
      "Instances",
      table(
        ["id", "model", "semantic role", "parameters (as written)"],
        (revision.instances ?? []).map((instance) => [
          id(instance.id),
          id(instance.model?.id),
          text(instance.semantic_role),
          instance.parameters && Object.keys(instance.parameters).length > 0
            ? h("details", null, h("summary", null, `${Object.keys(instance.parameters).length} parameters`), jsonTree(instance.parameters))
            : DASH,
        ]),
      ),
    ),
    section(
      "Connections",
      table(
        ["id", "from", "to", "state definition"],
        (revision.connections ?? []).map((connection) => [
          id(connection.id),
          endpoint(connection.from),
          endpoint(connection.to),
          text(connection.state_definition),
        ]),
      ),
    ),
    section(
      "Specifications (as written)",
      table(
        ["id", "kind", "role", "target", { text: "value", num: true }, "unit"],
        (revision.specifications ?? []).map((specification) => [
          id(specification.id),
          text(specification.kind),
          text(specification.role),
          specificationTarget(specification.target),
          typeof specification.value === "number"
            ? numCell(specification.value)
            : h("td", null, JSON.stringify(specification.value ?? null)),
          text(specification.unit),
        ]),
      ),
    ),
  );
}
