// The trace table of a solve (M06 design note §6.3, §5.6 rule 7): one row per recorded event,
// the members §6.3 names read as recorded — an absent member is `undefined`, shown as "—" —
// and filtering and client paging of the loaded rows. Nothing is computed from the values.

export const TRACE_PAGE = 500;

// §6.3's columns, in order: `[key, header]`; `key` is the row member.
export const TRACE_COLUMNS = [
  ["sequence", "sequence"],
  ["kind", "kind"],
  ["attempt", "attempt"],
  ["iteration", "iteration"],
  ["residual_inf_unscaled", "residual_inf_unscaled"],
  ["merit", "merit"],
  ["alpha", "alpha"],
  ["step_inf_scaled", "step_inf_scaled"],
  ["trial_status", "trial_status"],
  ["rejection_reason", "rejection_reason"],
  ["linear_residual_normalized", "linear.residual_normalized"],
  ["outcome", "outcome"],
  ["state", "state_sha256[:12]"],
];

// One row per event, in recorded order.
export function traceRows(events) {
  return events.map((event, index) => ({
    sequence: event.sequence ?? index,
    kind: event.kind,
    attempt: event.attempt,
    iteration: event.iteration,
    residual_inf_unscaled: event.residual_inf_unscaled,
    merit: event.merit,
    alpha: event.alpha,
    step_inf_scaled: event.step_inf_scaled,
    trial_status: event.trial_status,
    rejection_reason: event.rejection_reason,
    linear_residual_normalized: event.linear?.residual_normalized,
    outcome: event.outcome,
    state: typeof event.state_sha256 === "string" ? event.state_sha256.slice(0, 12) : undefined,
    state_sha256: event.state_sha256,
  }));
}

// The distinct kinds and attempts of `rows`, in first-seen order (filter choices).
export function traceChoices(rows) {
  const kinds = [];
  const attempts = [];
  for (const row of rows) {
    if (!kinds.includes(row.kind)) kinds.push(row.kind);
    if (row.attempt !== undefined && row.attempt !== null && !attempts.includes(row.attempt)) {
      attempts.push(row.attempt);
    }
  }
  return { kinds, attempts };
}

// The rows of kind `kind` and attempt `attempt` (either null/undefined/"" for any).
export function filterTrace(rows, { kind, attempt } = {}) {
  const anyKind = kind === null || kind === undefined || kind === "";
  const anyAttempt = attempt === null || attempt === undefined || attempt === "";
  return rows.filter(
    (row) =>
      (anyKind || row.kind === kind) && (anyAttempt || String(row.attempt) === String(attempt)),
  );
}

// Page `page` (0-based, clamped) of `rows`: `{rows, page, pages, first, last}`; `first` and
// `last` are 1-based row numbers (0 and 0 when there are no rows).
export function pageOf(rows, page = 0, size = TRACE_PAGE) {
  const pages = Math.max(1, Math.ceil(rows.length / size));
  const at = Math.min(Math.max(0, Math.trunc(Number(page) || 0)), pages - 1);
  const slice = rows.slice(at * size, (at + 1) * size);
  const first = slice.length > 0 ? at * size + 1 : 0;
  return { rows: slice, page: at, pages, first, last: first === 0 ? 0 : first + slice.length - 1 };
}
