# ADR 0037 — M04: the surrogate is a native extent-fixed unit pinned by its manifest's hash, promoted and rolled back through ADR 0035's checked commit with one new facet

**Status:** Proposed, 2026-10-08. Accepted when M04's evidence manifest is `tested` for M04.A12–A15, A25–A30 and A35,
the design-lane review of WO-7 and WO-8 is recorded, and ADR 0035 is Accepted (this ADR amends it and is void if it is
withdrawn).
**Author:** design lane (`specifier`), M04; brief `docs/briefs/M04-specification.md`.
**Normative text:** `docs/derivations/M04-spec.md` §3.2–§3.3, §3.5–§3.7, §8, §10.
**Amends:** ADR 0035 D2 (the replacement check also applies when a side is surrogate-backed; a new facet
`surrogate_evidence`; one exception in `derivatives`) and D1 (pinning by hash, extended to surrogate manifests);
ADR 0019 (Amendment 5: the job operation `surrogate_study`, the artifact kinds `surrogate_manifest` and
`model_evidence`); plan §2.2's schema list is delivered for `SurrogateManifest` and `ModelEvidence`. Pointer
paragraphs are added at merge.
**Affected requirements:** W23; blueprint §5.3 (replacement checks), §9.3 (frozen surrogate during a solve, promote
a new version to refine).
**Affected packages:** M04; M02 (its replacement check and schema gain members); M05, M07 (consume the unit).
**Register:** R-240 (D1), R-248 (D3).

## Context

M02 embeds the external reactor as rows with pinned conversion and temperature rise and matches them to experiments in
an outer coupling that refuses every sensitivity (ADR 0034 D1–D4). M02's replacement check (ADR 0035) has no facet for
a fitted model, and its `derivatives` facet would refuse a rollback from a surrogate (which declares an analytic
outlet-w.r.t.-inlet derivative) to its parent (which declares it unavailable). M04 must say how a surrogate enters a
revision, what makes it promotable, and how it is rolled back.

## Decision

**D1. A native unit.** `c1.reactor_surrogate` is M02's embedded unit with (X̂, ΔT̂) replaced by the frozen quadratic
of the scaled inlet: same ports, components, accumulation declarations, rows and DOF; `execution_class`
`explicit_reduced`; residual and Jacobian analytic; outlet w.r.t. inlet `analytic` (of the surrogate). A revision bound
to it solves on `revision_eo`, with no experiment and no coupling.

**D2. Pinned by the manifest's hash.** `model.version` is the surrogate id, `model.artifact_ref` the SHA-256 of the
canonical SurrogateManifest, resolved from the project's artifact store by an injected resolver; an unknown id, a
mismatched hash or a manifest that fails its checker is `revision_unsupported`,
`surrogate_manifest_mismatch(<instance>)`.

**D3. The replacement check for a surrogate side.** The check runs when either side is variant- or
surrogate-backed. A surrogate side's boundary block is its manifest's verbatim copy of the parent variant's; its
validity is the parent's hard domain. The new facet `surrogate_evidence` passes for a new surrogate iff its verdict,
re-derived by the manifest checker, is PROMOTABLE and the old model is its parent or a surrogate of the same parent; for
a new non-surrogate replacing a surrogate iff the new model is that surrogate's parent exactly. `derivatives` does not
count the parent's `unavailable` outlet-w.r.t.-inlet declaration as a loss when the new model is the old surrogate's
own parent (detail `restores_parent_declaration`).

**D4. Invalidation unchanged.** ADR 0035 D4's rule applies to promotion and rollback commits. `surrogate_study` is
scoped to a variant and is not registered in `EVIDENCE_OPERATIONS`; experiment records and surrogate studies survive
every revision change, so a rollback reuses them.

**D5. What a surrogate-backed certificate carries — no schema change.** A `bounds_and_domain` check
`SURROGATE-DOMAIN:<unit>` and the limitations `surrogate_model` (band, coverage numbers, Q0–Q7) and, when outside the
box, `surrogate_outside_reference_domain` (open objects keyed by `kind`).

**D6. Contract additions (ADR 0019 Amendment 5).** Job operation `surrogate_study` (right `execute`); `job`
`artifact_ref.kind` gains `surrogate_manifest` and `model_evidence`; schemas `surrogate-manifest.schema.json` and
`model-evidence.schema.json` (spec §10) join `schemas/registry.json`; `model-replacement.schema.json`'s facet enum gains
`surrogate_evidence`. All additive.

**D7. The seam.** M04 delivers the unit, its evidence, promotion and rollback. Whether and how a trust region uses the
surrogate, and every parent-model check at a candidate (`targeted_check`), are M05's.

## Alternatives considered

- **The surrogate as the experiment inside M02's coupling.** Rejected: the coupled route refuses sensitivities, so the
  surrogate's analytic derivative would be wasted; a fixed-point loop around an analytic map is what Newton does
  directly.
- **A surrogate as a new kind of model variant.** Rejected: variants are shipped, append-only package data describing
  how to *run* a parent; a surrogate is a study product of a project, and making it a variant would route it to the
  coupled path (ADR 0034 D2's selection rule).
- **A separate `promote_surrogate` operation.** Rejected for ADR 0035's own reason: `commit_change` could still swap the
  model unchecked.
- **Reading the verdict from the manifest's field.** Rejected: the facet re-derives it from the stored scores, so a
  hand-edited manifest cannot be promoted.
- **Embedding the coefficients in the revision's parameters.** Rejected: 72 coefficients and the band in revision
  content, a second record of the surrogate, and no resolution path for its evidence.
- **Clipping or smoothly saturating inadmissible predictions.** Rejected: a fabricated output with a kink, or a
  representation change no measurement asked for.

## Consequences

- A surrogate-backed revision costs no experiment to solve and has an analytic Jacobian; its certificate says it is a
  surrogate, with what band, at what coverage, and whether the solution's inlet is inside the reference box.
- A rollback to the parent restores the coupled route and the parent's refusal of sensitivities (ADR 0034 D4).
- M02's replacement module and schema gain members; nothing existing changes meaning.

## Migration

None for existing revisions, bundles or stores. Released 0.1.x clients that validate `job` or `model-replacement`
against earlier schemas would reject the new enum values (J5).

## Acceptance evidence

M04.A12–A15, A25–A30, A35 `tested`; A33 recorded if the real surrogate is PROMOTABLE; the design-lane review of
WO-7 and WO-8.

## Amendment 1 (2026-10-09): the evidence names the manifest; outputs, refusals and concurrency

**Normative text:** `docs/derivations/M04-spec.md` §18 (A1.4–A1.7). **Register:** R-292, R-293, R-294, R-295.

**D6, amended.** The SurrogateManifest has no `evidence_sha256`. ModelEvidence's `subject.artifact_ref` is the
manifest's SHA-256, required. The job's outputs are the manifest, then the evidence, and experiment records are
artifacts but not outputs. A budget refusal writes nothing and answers with `cache_misses`. Plan and parent refusals,
including `iteration_not_permitted`, are `invalid_request` at admission with the guard's code in `detail.reason`.
Each split carries an `incomplete` list, and gradient centres carry the statuses `ok | parent_failed | incomplete |
not_evaluated`. The manifest gains `domain.admissibility_margin`. *Rejected:* a `null` subject reference (spec
§18 A1.4).

**D8 (new). Concurrency is outside the study.** `surrogate_study` stays sequential. Many cold experiments are run
concurrently only by pre-warming the cache with `experiment` jobs (`executor.max_workers` ≤ the physical cores,
R-250; 16 on the 24-core host). No bit changes, because each record is a function of its exact key. Concurrency is
telemetry: never in the manifest or the evidence, recorded in the package evidence manifest. *Rejected:* a
`max_workers` member on the study request.

**D9 (new). The served surface.** M04's additions are additive, and stripping them gives M02's surface exactly
(R-234's pattern). `max_cold_experiments` is a Q26 pinned scalar.
