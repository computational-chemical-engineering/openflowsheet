// #/ — the project: header facts, every revision, the first page of jobs (M06 design note §6).
// Reads `list_revisions` (all pages, at most 50) and `list_jobs` (first page); the project
// document is the frame's `get_project`.

import { h } from "../h.js";
import { link } from "../router.js";
import { DASH } from "../text.js";
import {
  allPages,
  facts,
  heading,
  id,
  jobLink,
  MAX_PAGES,
  PAGE,
  pill,
  revisionLink,
  section,
  table,
  text,
} from "./common.js";

export const name = "project";
export const pattern = "/";

export async function load(params, api) {
  const { signal } = params;
  const revisions = await allPages(
    (args) => api.call("list_revisions", args, { signal }),
    { limit: PAGE.revisions },
    { max: MAX_PAGES },
  );
  const jobs = await api.call("list_jobs", { limit: PAGE.projectJobs }, { signal });
  return {
    project: params.project,
    revisions: revisions.items,
    revisionsComplete: revisions.complete,
    jobs: jobs.items,
    moreJobs: jobs.next_cursor !== null && jobs.next_cursor !== undefined,
    go: params.go,
  };
}

function choose(nameAttr, ids, selected) {
  return h(
    "select",
    { name: nameAttr },
    ids.map((value) => h("option", { value, selected: value === selected }, value)),
  );
}

// A two-select form that navigates to `pattern` with the two chosen ids.
export function pairForm(label, ids, pattern_, keys, go, defaults = []) {
  if (ids.length < 2) return null;
  const onSubmit = (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const a = form.elements.namedItem("a").value;
    const b = form.elements.namedItem("b").value;
    go(link(pattern_, { [keys[0]]: a, [keys[1]]: b }));
  };
  return h(
    "form",
    { class: "pair", "data-ofs-form": label, on: { submit: onSubmit } },
    h("span", null, `${label}: `),
    choose("a", ids, defaults[0] ?? ids[0]),
    " → ",
    choose("b", ids, defaults[1] ?? ids[1]),
    h("button", { type: "submit" }, "compare"),
  );
}

export function view(data) {
  const { project, revisions, jobs } = data;
  const counts = Object.entries(project.job_counts ?? {})
    .map(([status, count]) => `${status} ${count}`)
    .join(", ");
  const revisionIds = revisions.map((revision) => revision.revision_id);
  const jobIds = jobs.map((job) => job.job_id);
  return h(
    "div",
    { "data-ofs-screen": "project" },
    heading(
      `Project ${project.project_id}`,
      h("a", { href: link("/history") }, "agent history"),
    ),
    section(
      "Project",
      facts([
        ["head", revisionLink(project.head)],
        ["revisions", String(project.revision_count)],
        ["jobs", counts || DASH],
        ["default policy", text(project.default_policy_id)],
      ]),
    ),
    section(
      "Revisions",
      table(
        ["revision", "title", "parent", "principal", "created", "content sha256"],
        revisions.map((revision) => [
          revisionLink(revision.revision_id),
          text(revision.title),
          revisionLink(revision.parent_revision),
          text(revision.principal_id),
          text(revision.created_at),
          id(revision.content_sha256?.slice(0, 12)),
        ]),
      ),
      data.revisionsComplete
        ? null
        : h("p", { class: "notice" }, `Only the first ${revisions.length} revisions are listed.`),
      pairForm(
        "compare revisions",
        revisionIds,
        "/compare/rev/{a}/{b}",
        ["a", "b"],
        data.go,
        revisionIds.slice(-2),
      ),
    ),
    section(
      "Jobs",
      table(
        ["job", "revision", "policy", "status", "created"],
        jobs.map((job) => [
          jobLink(job.job_id),
          revisionLink(job.request?.body?.revision_id),
          text(job.request?.body?.policy_id),
          pill(job.status),
          text(job.created_at),
        ]),
      ),
      data.moreJobs
        ? h("p", { class: "notice" }, `The first ${jobs.length} jobs in acceptance order.`)
        : null,
      pairForm("compare runs", jobIds, "/compare/run/{job_a}/{job_b}", ["job_a", "job_b"], data.go),
    ),
  );
}
