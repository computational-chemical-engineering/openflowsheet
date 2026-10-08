// A solution certificate for display (M06 design note §5.6 rules 2, 3 and 7, §6.4).
//
// Grouping and counting of the recorded checks, the scaled residual of a residual check
// (`value / reference`), and the vapour fraction of a `phase_branch` entry
// (`vapor_total / (vapor_total + liquid_total)`). Every verdict — a check's `result`, its
// `near_threshold` flag, the certificate's `verification_status` — is read as recorded, never
// computed or re-judged here.

// The checks grouped by `category` (first-seen order), then by `result` (first-seen order):
// `[{category, count, results: [{result, count, checks}]}]`.
export function checkGroups(checks) {
  const groups = [];
  for (const check of checks ?? []) {
    let group = groups.find((entry) => entry.category === check.category);
    if (!group) {
      group = { category: check.category, count: 0, results: [] };
      groups.push(group);
    }
    group.count += 1;
    let bucket = group.results.find((entry) => entry.result === check.result);
    if (!bucket) {
      bucket = { result: check.result, count: 0, checks: [] };
      group.results.push(bucket);
    }
    bucket.count += 1;
    bucket.checks.push(check);
  }
  return groups;
}

// Rule 2: `value / reference` of a check whose `category` is "residual"; null for any other
// check, or when either number is missing or the reference is 0.
export function scaledResidual(check) {
  if (check?.category !== "residual") return null;
  const { value, reference } = check;
  if (typeof value !== "number" || typeof reference !== "number" || reference === 0) return null;
  return value / reference;
}

// The checks whose `subject` is `subject` (a row id), in recorded order.
export function checksForSubject(certificate, subject) {
  return (certificate?.checks ?? []).filter((check) => check.subject === subject);
}

// How many checks carry the recorded flag `near_threshold: true`.
export function nearThresholdCount(checks) {
  return (checks ?? []).filter((check) => check.near_threshold === true).length;
}

// Rule 3: the entries of `phase_branch`. A split entry (an object with `liquid`/`vapor`
// arrays) becomes `{key, split: true, liquid, vapor, liquid_total, vapor_total,
// vapour_fraction, components}`, `components` the revision's component-set order labelling the
// array columns; any other entry (a stream's flow state) `{key, split: false, state}`.
// `vapour_fraction` is null when the two totals sum to 0 or are missing.
export function phaseBranches(phaseBranch, components = []) {
  const out = [];
  for (const [key, value] of Object.entries(phaseBranch ?? {})) {
    if (value !== null && typeof value === "object" && !Array.isArray(value)) {
      const liquid = value.liquid_total;
      const vapor = value.vapor_total;
      const total = typeof liquid === "number" && typeof vapor === "number" ? vapor + liquid : 0;
      out.push({
        key,
        split: true,
        liquid: value.liquid ?? [],
        vapor: value.vapor ?? [],
        liquid_total: liquid,
        vapor_total: vapor,
        vapour_fraction: total === 0 ? null : vapor / total,
        components,
      });
    } else {
      out.push({ key, split: false, state: value });
    }
  }
  return out;
}
