// Joins over `inspect_structure`'s index (M06 design note §4.1, §5.6 rule 6, §6.2, §6.5).
//
// The server's rows/columns index and its structural report, joined and inverted for display:
// the row matched to a column (`canonical_matching`), the column matched to a row (its
// inverse), the rows incident on a column (the inverse of `rows[].columns`), a row's BTF block,
// the redundancy certificates naming a row, whether a row is a candidate specification row, the
// owning unit's degrees-of-freedom row. No validation, DOF, matching or redundancy is computed.

// The structural report an `inspect_structure` answer carries: the routed analysis
// (`structural_report`), or for an unroutable revision the validation's
// (`validation_structural_report`, with `not_run_reason` and `hint`); null when neither.
export function reportOf(structure) {
  return structure?.structural_report ?? structure?.validation_structural_report ?? null;
}

// Whether the answer is the routed analysis (true) or the unroutable branch (false).
export function isRouted(structure) {
  return structure?.structural_report !== undefined && structure?.structural_report !== null;
}

export function structureIndex(structure) {
  const report = reportOf(structure);
  const rows = new Map((structure?.rows ?? []).map((row) => [row.row_id, row]));
  const columns = new Map((structure?.columns ?? []).map((column) => [column.column_id, column]));
  const matching = report?.canonical_matching ?? {};
  const matchedColumnOf = new Map();
  for (const [column, row] of Object.entries(matching)) matchedColumnOf.set(row, column);
  const incident = new Map();
  for (const row of rows.values()) {
    for (const column of row.columns ?? []) {
      if (!incident.has(column)) incident.set(column, []);
      incident.get(column).push(row.row_id);
    }
  }
  const blocks = report?.block_triangular_form?.blocks ?? [];
  const blockOf = new Map();
  blocks.forEach((block, index) => {
    for (const row of block.rows ?? []) blockOf.set(row, { index, ...block });
  });
  const candidateRows = new Set(report?.candidate_specification_rows ?? []);

  return {
    report,
    routed: isRouted(structure),
    rows,
    columns,
    row: (rowId) => rows.get(rowId) ?? null,
    column: (columnId) => columns.get(columnId) ?? null,
    // The row `canonical_matching` matches to `columnId`, or null.
    matchedRow: (columnId) => matching[columnId] ?? null,
    // The column `canonical_matching` matches to `rowId`, or null.
    matchedColumn: (rowId) => matchedColumnOf.get(rowId) ?? null,
    // The rows whose columns include `columnId`: the matched row first, then in index order.
    incidentRows(columnId) {
      const found = incident.get(columnId) ?? [];
      const matched = matching[columnId];
      if (matched === undefined || !found.includes(matched)) return [...found];
      return [matched, ...found.filter((row) => row !== matched)];
    },
    // `{index, size, rows, cols, depends_on}` of the BTF block holding `rowId`, or null.
    block: (rowId) => blockOf.get(rowId) ?? null,
    // The redundancy certificates naming `rowId`: as the certified row or in `equals`.
    certificatesWith: (rowId) =>
      (report?.certificates ?? []).filter(
        (certificate) =>
          certificate.row_id === rowId ||
          (certificate.equals ?? []).some((entry) => Array.isArray(entry) && entry[0] === rowId),
      ),
    isCandidateRow: (rowId) => candidateRows.has(rowId),
    // The `unit_degrees_of_freedom` row of `instanceId`, or null.
    unitDof: (instanceId) =>
      (report?.unit_degrees_of_freedom ?? []).find((entry) => entry.instance_id === instanceId) ??
      null,
  };
}

// §6.5's consistency guard: the equation index describes a run only when the server's current
// analysis of its revision has the bundle's `model_version` (an exact string comparison).
export function sameStructure(structure, bundleStructuralReport) {
  const current = structure?.structural_report?.model_version;
  const recorded = bundleStructuralReport?.model_version;
  return typeof current === "string" && typeof recorded === "string" && current === recorded;
}
