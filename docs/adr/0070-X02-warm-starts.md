# ADR 0070 — Declared warm starts for coupled and external units: an explicit start in the solve request, a warm-chained reactor variant, and a start-keyed experiment identity

**Status:** **Proposed, 2026-11-07.**
- Takes effect on `main` when X02's manifest is `tested` and the reviewer pass is done. Until then X02 is built on
  `wp/X02`.
- Register entries are added on acceptance (drafts below).

**Author:** design lane (`architect`), X02 design pass. **Brief:** `docs/briefs/X02-architect.md`.

**Design note:** `docs/design/X02-warm-starts.md` holds the normative detail; the § numbers below refer to it.

**Amends:**
- **ADR 0019 D1, as Amendment 15.** Three optional members (§5.1):
  - `job.schema.json#/$defs/solve_body` gains `warm_start: {job_id?, coupling?}`;
  - `experiment.schema.json#/$defs/request` gains `start`;
  - `#/$defs/result` gains `profile_sha256`.

  Amendment 14 is left to X05's Q-F3. On acceptance, a pointer paragraph in the form of Amendment 4 is added to ADR
  0019, and `docs/interfaces-frozen.md` lists the three members.
- **ADR 0024, additively:**
  - D1's precedence gains the explicit source (`explicit-v1`, the "Deferred" form it drafted, now realised) above the
    lineage source;
  - D4 and D5 extend to the coupled route (sub-records `coupling` and `external`), and the coupled route records its
    k = 0 inner start, which it fails to do today (note §3.3);
  - an explicit declaration is its own opt-in under any policy.
- **ADR 0020 D7 (R-088 Q26):** one registered full path accepts a state from outside,
  `submit_job` `body/warm_start/coupling/*/{X,dT_K}`, as a start only, with its W14-path test.
- **ADR 0033 D7 and ADR 0034 (the coupled route):**
  - a start-capable variant chains child starts;
  - the outer iteration may start from a declared w₀;
  - the child program is selected by the variant's `runner_sha256`.

**Reverses, in part:**
- **R-224's "cold S1–S3 only (no reactor warm start)",** for start-capable variants only. v1–v3 stay cold.
- **R-287's "w₀ is the variant's".** It now reads "unless the solve declares a start". R-287's refusal of
  `coupling_initial.*` as a *revision parameter* stands, with its reason restated (D1).

**Does not amend:**
- any item ADR 0060–0067 lists as core;
- `SolvePolicy` or `solve-policy.schema.json` (K03);
- `model-variant.schema.json`;
- the `ApiError` code enum;
- ADR 0007 D4's mode rules;
- `T08-warm-v1`'s behaviour (only its coupled record is completed);
- the `experiment` operation.

**Affected packages:** X02 (builds it); T08 and M02 (new branches only); M03 and M05 (consumers later, Q4); F7 (the
`simulation` kind's options should mirror `warm_start` when F7-WO5 lands, since ADR 0066 D11 says that kind "creates
exactly the job `submit_job({operation: "solve", …})` creates").

## Context

ADR 0056 row 2 (R-925) lifts "external models start cold every call; the coupled reactor's initial iterate is
refused", with this text: "a declared warm start (previous converged state, or a user iterate) for external and
coupled units; the certificate checks the converged answer independently; bitwise identity across warm/cold is not
claimed and the cache key states whether a warm start was used".

The earlier rejections (ADR 0033:106-107, R-224, R-287, M02 N6) were identity rejections: a history-dependent result
in an exact cache. Measured (note §3):
- a reactor call takes a median of 48 s, of which S1 is 11 % and the start-independent certificate 37 %;
- the registered real loop takes 4 outer iterations and 162 s of calls from the variant's w₀.

## Decision

- **D1. A start is declared in the solve request.** `warm_start.job_id` names any solve job of the project that has a
  solution state. `warm_start.coupling` declares w₀ per coupled unit.
  - A start is method, not problem, so it does not belong in the revision. `coupling_initial.*` therefore stays
    `parameter_unsupported`.
  - A start is an input, not a policy, so no `SolvePolicy` member is added.
  - Admission: `invalid_request` for a missing source (`warm_start_source_missing(<job>)`) and for an unknown unit
    (`warm_start_unit_unknown(<unit>)`).
- **D2. Precedence** (note §4 D2).
  - x₀: internal `user_start` > `job_id` (when declared, it replaces the lineage lookup) > `T08-warm-v1`
    lineage > `traversal-G0-v1`. *Amended (X02 review, 2026-11-07):* if a declared job is rejected, `traversal-G0-v1` follows (note D-7).
  - w₀: `coupling` > `job_id`'s final iterate > the variant's `coupling.initial`.
  - Child at k = 0: `job_id`'s final profile (same variant) > cold.
  - Child at k ≥ 1: the unit's most recent `ok` experiment in the run.
- **D3. Outer-start checks.** Integrity, compatibility, bounds (clip and log), then opening (the k = 0 inner solve
  converges). A rejection is recorded, and the coupling starts from the variant's w₀. Nothing falls back after
  acceptance. B₀ = −I.
- **D4. A child start is a variant property.** A variant whose `evaluation.profile.start` is present is
  start-capable. *Amended (X02 review, 2026-11-07):* X02 registers no start-capable variant. The measured candidate
  `pymrm-6089593-g2-nz800-s123w-v1` (`child_warm.py`, `69c4a24d`) failed D6's decade rule (1.92e-7 against 1e-6)
  and was about 21 % slower than the cold chain (note §3.1). It is not registered and its runner is not shipped. The
  behaviour below is the contract for a future start-capable runner, which loads the hash-pinned `child.py` and
  never edits it (note §5.6):
  - S1 is skipped and S2 is seeded from the start profile;
  - S3, the certificate and the acceptance criteria are unchanged;
  - on any refusal of the warm chain, the cold chain runs in the same attempt;
  - the converged profile is exported after every outlet answer.
- **D5. Experiment identity.**
  - A warm request carries `start: {kind: "profile", profile_sha256}` inside its key. It is content-addressed and
    present only when used.
  - `experiment-request-v1` is unchanged, so every cold key is byte-identical.
  - Profiles live in a content-addressed store under the project's experiment records. Bundles carry hashes only.
- **D6. The certificate judges the converged answer.**
  - Its checks are functions of the final inner state, the final iterate and the external answer at the final inlet,
    and of nothing from the start.
  - A warm external answer differs from a cold one by at most the variant's registered
    `measured_path_independence_rel`, which must be at least one decade below its `precision_floor_rel`.
  - The `external_model` limitation discloses a warm final answer.
  - No cold re-evaluation is made.
- **D7. Records, R0 and replay.**
  - The `warm_start` member of `solve-path.json` gains optional `coupling` and `external` sub-records.
  - R0 takes statuses, reasons, selections and unit ids, never values, digests or ids of jobs and experiments.
  - The rerun takes every start from the record, makes no lookup, re-runs the checks, and recomputes chained starts
    from the recorded results.
  - *Amended (X02 review, 2026-11-07):* the sub-records' `reason` members are bare check names
    (`coupling_integrity|coupling_compatibility|coupling_opening|route|external_integrity|external_compatibility`);
    `warm_start_rejected(<check>)` is the trace message only (ADR 0024's convention).
- **D8. The child program is selected by `runner_sha256`**, among the packaged child scripts (today `child.py`
  alone; amended by the X02 review). For v1–v3 this is the same file as today.

## Alternatives rejected

- **`coupling_initial` as revision parameters.** Rejected: it moves `content_hash` and `constants_sha256` with a
  start, and needs an optional signature member on a frozen surface (R-287).
- **An instance-level `initialization_hint`.** Rejected: it changes two frozen grammars and stores a start in the
  problem.
- **A `SolvePolicy.warm_scope` member and a new policy.** Rejected: it is a K03 schema change, and a policy cannot
  carry an iterate.
- **Extending `T08-warm-v1` on the coupled route.** Rejected: it changes a registered policy's behaviour (Q2).
- **Editing `child.py`.** Rejected: it moves v1–v3's identity.
- **Copying `child.py`.** Rejected: it duplicates frozen code.
- **The source experiment key in the identity.** Rejected: it keys on history, not content.
- **Bumping `experiment-request-v1`.** Rejected: it moves every key.
- **Profiles in results, in a new artifact kind, or in bundles.** Rejected: they bloat records, or are a surface move,
  or have no consumer.
- **A cold re-check at the final inlet.** Rejected: it costs a full call and cancels the gain. The registered bound
  is enough.
- **Falling back to cold after an accepted outer start.** Rejected for the reason ADR 0024 gives.
- **Including the k = 0 experiment in the opening check.** Rejected: it would need a second replay path.
- **Carrying the Broyden matrix.** Rejected: it adds state for little.
- **Cold-first or same-inlet cache lookups.** Deferred until measured (note §8 R5).

## Consequences

- A coupled flowsheet restarted from a converged run of the same revision converges at k = 0: one call, or none on an
  exact-inlet hit. On v3 (G5 (d)(ii)) it took 1 outer iteration and 1 call, 24.7 s against 193.7 s cold.
  ~~A neighbouring revision restarts near its fixed point.~~
  *Amended (D-32 ruling, 2026-11-07):* A neighbouring revision starts near its fixed point but is not claimed to
  converge faster: on v3 with SPEC-S3-T +2 K it started about twice as close and took the same 4 outer iterations as
  the cold run, and took longer (222.7 s against 181.5 s).
- ~~A start-capable variant saves S1 on every call after the first: about 11–15 % per call (note §3.1).~~
  *Amended (X02 review, 2026-11-07):* No start-capable variant is registered. The measured warm reactor chain was slower (G5c). Part B
  ships as plumbing, tested in CI.
- A warm-started run may reach another certified answer than a cold one: another fixed point within the coupling
  tolerance, or another steady state where the model has several. This is a change of method, recorded in the bundle
  and disclosed in the certificate, never a change of problem (ADR 0024 Consequences). It is a declared limitation
  (R-924).
- The `submit_job` schema digest moves: one surface-chain link. V17 is re-established at the next RC.

## Migration proof

- No existing document gains a member.
- *Amended (X02 review, 2026-11-07):* replay of pre-X02 coupled `T08-warm-v1` bundles (S-4). A coupled `T08-warm-v1` bundle written before
  X02 with K ≥ 1 whose candidate was `absent` or `rejected` carries no `warm_start` member and reproduced `MATCH`.
  Under Part C its rerun writes the k = 0 member (`absent`), so it reproduces `MISMATCH` on R0. Such bundles whose
  candidate was *accepted* already reproduced `MISMATCH`: that is the Part C defect. F0 holds no such bundle. The
  behaviour is correct; the stored documents are unchanged, only their reproduction verdict moves.
- v1–v3, the stand-in and every registered policy behave as today. The only exception is `T08-warm-v1` bundles on
  `revision_coupled`, which gain the record they should have had.
- F0 M1–M9 PASS.
- Recomputing every recorded experiment key gives 0 differences (note §7 G0).

## Acceptance evidence

- G0–G6 of note §7 pass on `wp/X02` (G5 on the workstation, numbers in `evidence/X02/<C>/`).
- G5 (d) ran on v3 per S-2: (i), (ii) met; (iii) both VERIFIED, bound held, the iteration criterion not met (D-32
  ruling).
- One `reviewer` pass.
- `review.numerical` and `review.process_model` are not set by this ADR.

## Register drafts (numbers assigned on acceptance; R-942…R-949 are held by `wp/MSG` and `wp/RP`)

**A — declared starts.**
- **Decision:**
  - starts are declared in `solve_body.warm_start` (`job_id`, `coupling`; ADR 0019 Am. 15);
  - an explicit declaration is its own opt-in;
  - `T08-warm-v1` is unchanged;
  - `coupling_initial.*` stays refused as a parameter.
- **Rejected:** revision parameters; instance hints; a `SolvePolicy` member; extending `T08-warm-v1`.
- **Watch for:** a start smuggled into a revision or a policy.

**B — the start-keyed experiment identity.**
- **Decision:**
  - a warm request carries `start.profile_sha256` inside its key, only when used;
  - content-addressed profile store;
  - bundles carry hashes only.
- **Rejected:** the source key in the identity; a request-version bump; lookups that ignore the start.
- **Watch for:** any change that moves a cold key.

**C — certificate independence.**
- **Decision:**
  - verdicts are functions of the final state alone;
  - a warm external answer is bounded by the registered path independence, a decade below the floor;
  - disclosure in `external_model`;
  - the child falls back to the cold chain within the attempt.
- **Rejected:** a cold re-check; failing on a warm refusal.

**D — the warm reactor variant** (*Amended (X02 review, 2026-11-07):*).
- **Decision:** no warm reactor variant is registered (G5b 1.92e-7 > floor/10; G5c −21 %). Programs are selected by
  `runner_sha256`. R-224 is lifted only for start-capable variants, and none is registered.
- **Rejected:** registering with a raised floor, because the real loop's T floor ratio would drop from 13 to about
  6.8; registering in the manifest-note band, because it contradicts D6; editing or copying `child.py`.
- **Evidence:** `evidence/X02/69c4a24d…/`.

**E — Q26 exception and coupled record.**
- **Decision:**
  - `body/warm_start/coupling/*/{X,dT_K}` is the registered state-from-outside path, with its W14-path test (amends
    R-088 Q26 and R-287);
  - the coupled route records its k = 0 inner start.
- **Watch for:** a second numeric path admitted without a registered exception.
