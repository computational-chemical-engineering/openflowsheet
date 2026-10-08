# ADR 0035 — Model replacement and promotion: a checked commit, pinned variants, and invalidation by the existing rule

**Status:** Proposed, 2026-10-08. Accepted when M02's evidence manifest is `tested` (design note gates G6, G9) and the
design-lane review of WO-11 is recorded.
**Author:** design lane (`architect`), M02.
**Normative text:** `docs/design/M02-pymrm-adapter.md` §6. Register R-226, R-228.
**Amends:** ADR 0019 (Amendment 4, part 3: the `api-error` code `model_replacement_incompatible`; the
`transaction-result.invalidations` description). Pointer paragraph added at merge (WO-13).
**Affected requirements:** W21; plan M02 acceptance "model replacement diff and invalidation" and "incompatible pressure
boundary rejected"; blueprint §5.3.
**Affected packages:** M02; M04 (surrogate promotion and rollback reuse this), M05, M07.

## Context

Blueprint §5.3: a replacement must check "ports, components, conserved quantities, reference states, boundary-condition
meaning, degrees of freedom, derivatives, and validity. Matching the label 'reactor' is insufficient. Promotion creates a
new revision and invalidates affected runs and derivative/optimization evidence." Today a revision's
`instances[i].model.version` and `artifact_ref` are not checked by the binder, a model swap through `commit_change` is
unchecked, and every commit already reports `invalidations` — `run-<job_id>` for each solve job of the expected revision
(`local.py:444`).

## Decision

**D1. Pinned by hash.** For a variant-backed model, `model.version` is the variant id and `model.artifact_ref` the
variant's SHA-256; the binder refuses an unknown id or a different hash as `model_variant_mismatch(<instance>)`. Native
models keep today's behaviour.

**D2. Promotion is a checked commit.** A change set that alters any instance's `model.{id, version, artifact_ref}`,
where the old or the new model is variant-backed, runs the replacement check in `commit_change` and `preview_change`:
facets `resolvable`, `ports`, `components`, `conserved_quantities`, `reference_states`, `boundary_condition` (equal
variant boundary contracts — pressure convention, ε_P, projection, defect limit, duty, provider; or equal declared
equation structure for a non-variant side), `degrees_of_freedom` (the new revision binds, is structurally closed, and the
instance contributes the same counts), `derivatives` (no EO-capable derivative lost), `validity` (the new domain
contains the old). `synthetic` is reported, not judged.

**D3. Rejection and record.** Any failed facet rejects the transaction with `model_replacement_incompatible` and the
report (`model-replacement.schema.json`) in `error.detail.report`. A committed promotion stores the report as an artifact
and writes its SHA-256 to the new revision's `provenance.artifact_hashes["model_replacement:<instance>"]` (outside the
content hash).

**D4. Invalidation (ADR 0019 Amendment 4, part 3).** The existing rule stands and is generalized: `invalidations` lists,
for every job operation registered in `EVIDENCE_OPERATIONS` (M02: `solve → run-`), the jobs whose request names the
expected revision. M03–M05 register their evidence-producing operations when they add them. **Experiment records are
never invalidated**: they describe a variant, not a revision; a rollback reuses them through the cache.

## Alternatives considered

- **A separate `promote_model` operation.** Rejected: `commit_change` could still swap a model unchecked; one path is
  simpler and cannot be bypassed.
- **Marking old runs and records as invalidated in place.** Rejected: evidence is immutable; invalidation is a relation
  the transaction reports.
- **Applying the check to native-to-native swaps now.** Rejected for M02: it could reject v0.1 corpus transactions;
  revisit when native models carry real versions (R-228's watch-for).
- **Comparing manifests' prose (equation statements).** Rejected: the stand-in and the real reactor have different
  statements and identical contracts; structure and the variant's boundary block are what carry meaning.

## Consequences

- Replacing the stand-in by the real reactor in a revision is one commit with a full report; replacing it by a model
  with another pressure convention is refused, which is the plan's "incompatible pressure boundary rejected" at the
  replacement level (the evaluation level is ADR 0027 D2's refusal).
- The existing `diff` and, when present, M06's `elements` show the change; nothing is added to `semantic_diff`.

## Migration

None. Released 0.1.x clients that validate `api-error` against 0.1 would reject the new code (J5).

## Acceptance evidence

Design note G6 (a) (hash enforcement) and G9 (a)–(e): a compatible promotion with its report, invalidations and diff;
incompatible pressure convention, narrower validity and renamed port refused; preview without commit; experiments reused
after rollback.
