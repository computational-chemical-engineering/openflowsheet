// Comparisons for display (M06 design note §6.7, §5.6 rules 4 and 7; R-174).
//
// Revision comparison: the server's diff (`diff_revisions`, coarse members and `elements`), with
// the before and after values of each changed path read from the two revision documents by
// element id and path tokens — nothing is compared here. Run comparison (the scenario view): two
// finished solves side by side, and a state table whose only arithmetic is rule 4,
// Δ = b − a and |Δ| / max(|a|, |b|) (0 when both are 0). Differences are displayed, never judged:
// no tolerance, allowance or agreement is applied, and this module returns no such verdict.

export const ABSENT = Symbol("absent");

// The value at `path` (tokens) under `node`, or ABSENT.
export function valueAt(node, path) {
  let here = node;
  for (const token of path) {
    if (here === null || typeof here !== "object" || !(token in here)) return ABSENT;
    here = here[token];
  }
  return here;
}

function elementOf(revision, member, id) {
  const entries = revision?.[member];
  if (!Array.isArray(entries)) return ABSENT;
  return entries.find((entry) => entry?.id === id) ?? ABSENT;
}

// `{added, removed, changed, elements, orderOnly}` of a `diff_revisions` answer read against
// the two revisions: each element `{member, id, change, paths: [{path, before, after}]}`
// (`before`/`after` ABSENT where a revision has no such value), and `orderOnly` the coarse
// `changed` members with no element entry ("order changed only").
export function revisionComparison(diff, before, after) {
  const elements = (diff?.elements ?? []).map((element) => {
    const old = elementOf(before, element.member, element.id);
    const now = elementOf(after, element.member, element.id);
    return {
      member: element.member,
      id: element.id,
      change: element.change,
      paths: (element.paths ?? []).map((path) => ({
        path,
        before: old === ABSENT ? ABSENT : valueAt(old, path),
        after: now === ABSENT ? ABSENT : valueAt(now, path),
      })),
    };
  });
  const withElements = new Set(elements.map((element) => element.member));
  return {
    added: [...(diff?.added ?? [])],
    removed: [...(diff?.removed ?? [])],
    changed: [...(diff?.changed ?? [])],
    elements,
    orderOnly: (diff?.changed ?? []).filter((member) => !withElements.has(member)),
  };
}

// Rule 4 for one variable: `{delta, relative}`, both null unless a and b are finite numbers.
export function difference(a, b) {
  if (typeof a !== "number" || typeof b !== "number" || !Number.isFinite(a + b)) {
    return { delta: null, relative: null };
  }
  const delta = b - a;
  const scale = Math.max(Math.abs(a), Math.abs(b));
  return { delta, relative: scale === 0 ? 0 : Math.abs(delta) / scale };
}

function variableOrder(state) {
  if (!state) return [];
  if (Array.isArray(state.variable_ids)) return state.variable_ids;
  return Object.keys(state.variables ?? {});
}

// The state table of two `solution-state.json` documents (either may be null: no state
// recorded): the union of variable ids (a's order, then b's others), each
// `{id, a, b, delta, relative}` (`a`/`b` undefined where that run has no such variable), sorted
// by `relative` descending; rows without a relative difference last, in union order.
export function stateTable(stateA, stateB) {
  const ids = [...variableOrder(stateA)];
  for (const id of variableOrder(stateB)) if (!ids.includes(id)) ids.push(id);
  const rows = ids.map((id, order) => {
    const a = stateA?.variables?.[id];
    const b = stateB?.variables?.[id];
    return { id, a, b, ...difference(a, b), order };
  });
  rows.sort((x, y) => {
    if (x.relative === null && y.relative === null) return x.order - y.order;
    if (x.relative === null) return 1;
    if (y.relative === null) return -1;
    return y.relative - x.relative || x.order - y.order;
  });
  return rows.map(({ order, ...row }) => row);
}

// §6.7's identity rows of two runs, each `{result, manifest}` (`get_job_result`'s `run_result`
// and the bundle's `run-manifest.json`): whether `structural_sha256` is the same string, and the
// equation-structure statement read off `model_version` string equality.
export function runIdentity(a, b) {
  const sha = (run) => run?.result?.structural_sha256 ?? run?.manifest?.structural_sha256 ?? null;
  const version = (run) => run?.manifest?.model_version ?? null;
  const shaA = sha(a);
  const shaB = sha(b);
  const versionA = version(a);
  const versionB = version(b);
  const sameVersion = versionA !== null && versionA === versionB;
  return {
    structural: { a: shaA, b: shaB, equal: shaA !== null && shaA === shaB },
    model_version: {
      a: versionA,
      b: versionB,
      equal: sameVersion,
      text: sameVersion
        ? "same equation structure"
        : versionA === null || versionB === null
          ? "equation structure not recorded for both runs — variables compared by id only"
          : "different structure — variables compared by id only",
    },
  };
}

// The certificate summary of §6.7: status, check count, limitations; null without a certificate.
export function certificateSummary(certificate) {
  if (!certificate) return null;
  return {
    status: certificate.verification_status ?? null,
    checks: (certificate.checks ?? []).length,
    limitations: [...(certificate.limitations ?? [])],
  };
}
