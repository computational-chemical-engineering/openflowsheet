// The project's record for display (M06 design note §6.8, §6.1, §5.6 rule 6).
//
// Audit rows as the agent history shows them, the effect of a row read as a link target, a
// revision's expected revision (its `parent_revision`: exact, because `commit_change` requires
// `expected_revision == head`), and the runs of a revision (a filter of `list_jobs` items by
// `request.body.revision_id`). The history shows what the project recorded; nothing here reads
// or judges what an agent said.

// An audit row's `effect` (`<kind>:<id>`) as `{kind, id, target}`: `target` is
// `{screen: "revision"|"job", id}` for `revision:`, `job:` and `cancel:` effects, null for every
// other kind (shown as text). A null effect is null.
export function effectOf(effect) {
  if (typeof effect !== "string") return null;
  const mark = effect.indexOf(":");
  const kind = mark < 0 ? effect : effect.slice(0, mark);
  const id = mark < 0 ? "" : effect.slice(mark + 1);
  let target = null;
  if (kind === "revision" && id) target = { screen: "revision", id };
  else if ((kind === "job" || kind === "cancel") && id) target = { screen: "job", id };
  return { kind, id, target };
}

// The table rows of a `list_audit` page, in the order the server gave them.
export function historyRows(page) {
  return (page?.items ?? []).map((row) => ({
    seq: row.seq,
    at: row.at,
    principal: row.principal_id,
    capability: row.capability_id,
    operation: row.operation,
    outcome: row.outcome,
    code: row.code ?? null,
    effect: effectOf(row.effect),
    key: row.idempotency_key ?? null,
  }));
}

// What a row's detail needs read: `{kind: "commit", revision}` for an allowed `commit_change`
// with a revision effect, `{kind: "job", job}` for a job or cancel effect, else null.
export function detailOf(row) {
  const target = row?.effect?.target;
  if (row?.outcome !== "allowed" || !target) return null;
  if (target.screen === "revision" && row.operation === "commit_change") {
    return { kind: "commit", revision: target.id };
  }
  if (target.screen === "job") return { kind: "job", job: target.id };
  return null;
}

// Rule 6: the expected revision of a commit — its revision's `parent_revision`.
export function expectedRevision(revision) {
  return revision?.parent_revision ?? null;
}

// Rule 6: the jobs of `revisionId`, in the order `list_jobs` gave them.
export function jobsOfRevision(jobs, revisionId) {
  return (jobs ?? []).filter((job) => job?.request?.body?.revision_id === revisionId);
}

// The principals a history page names, own principal first (selector choices beyond "all").
export function principalsOf(rows, own) {
  const out = own ? [own] : [];
  for (const row of rows) if (row.principal && !out.includes(row.principal)) out.push(row.principal);
  return out;
}
