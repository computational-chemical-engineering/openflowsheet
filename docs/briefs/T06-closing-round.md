# Brief — T06 closing ruling round

**To:** `specifier` (design lane). **From:** build lane, 2026-09-27. **Branch:** `wp/T06`.
**Deliverable:** dated amendments (spec `docs/derivations/T06-corpus-spec.md`, ADR 0018, ADR 0014, the
register), twin re-emitted only if a registered value changes (`--check`, SHA), and a ruling list in §2
with each build-lane change and acceptance test. No code; do not commit. Sources:
`docs/reviews/T06-review.md` (M1, S1–S5, notes), `docs/reviews/T06-verdicts.md` (qualifications,
evidence gaps), `docs/T06_DECISIONS.md` (last entry: Frank's answers).

1. **M1:** amend ADR 0018 D4 and its docstring text: the refinement spends budget like any iteration;
   a refusal in it, or in the closure after it, is `BUDGET_EXHAUSTED` (reproduced: THM-09 start 1 at a
   365-call cap: `newton` CONVERGED, `newton_refined` BUDGET_EXHAUSTED, closing message `abandoned:
   EVALUATION_ERROR`); the plan-level test to add; the message wording. Also update ADR 0018's header and
   R-085: Frank approved the widening (2026-09-26) and kept `newton_refined` as T07's default knowing M1
   (2026-09-27).
2. **A50 erratum** ("exact" → floats to 1e-12 relative across machines, as the build lane implemented;
   reviewer: legitimate) and **S2**: the committed `certificate_sha256` in `ours-*` records is checked
   nowhere and went stale at W19 — drop the field, or specify a machine-independent certificate digest.
3. **S3 / A92's floor:** replace 9.5e-4 K (text) / 9.4e-4 K (test) with a principled registered floor
   (reviewer suggests ≥ 100 τ_T), on states that move ~30 % between machines.
4. **§7.3's contradiction** ("nothing in §6 may be changed after any ensemble solve has been seen" vs
   Amendment 4's §6.6 policy change after run 1): amend so run 2's legitimacy under R-087 / plan §6.5 is
   stated in the spec (the verdict decided under the later amendment).
5. **Holdout ensemble (Frank: yes, in T06):** a fresh draw of 440 starts under the same law with a new
   registered key prefix (never the gate's keys), generated and committed before any solve, run on both
   architectures under `T06-revision-v2`, reported (per-case, clustered, CP bound) and **not gated**;
   say where the starts file and report live and how it enters the manifest.
6. **Run-record evidence (verdict's gaps):** A90 needs the harness to record whether the terminal
   refinement fired (and kept/reverted) per start; the record's machine class must come from the host
   (not hard-coded `ref-x86-64`, `generator.py:695`); commit id and `cache_condition` fields; where run
   files are kept (committed under `evidence/T06/…` by hash, or as committed JSON). Say whether an
   instrumented re-run of run 2's starts (same code, same starts) is required to meet A90 on both
   architectures, and that its S must equal run 2's or be reported as a discrepancy.
7. **T07 questions to register** (no T06 change): S1 (closure at `x_final` when the projection is refused
   is stricter than the rows — a state within the row-implied bound becomes `FAILED`
   `false_success_detected`; should it be `UNVERIFIED`?), S4 (the W2 shift `997·(j+1)` by position makes
   certificates systematically `UNVERIFIED` from ~20 streams; ordinal among pressures?), and the
   reviewer's notes (W14 refusal cannot fire on the production path; W3 seeding not thread-safe;
   refinement message floats vs R0).
8. **S5** is build-lane (typed refusal of `10**400`-scale inputs on six paths) — confirm the refusal code.

## 2. Rulings (the design lane fills this in)

**Ruled by the design lane (`specifier`), 2026-09-27, on `wp/T06` at `66861d5`.**

- **Normative text:** T06 spec Amendment 5 (every passage marked **(A5)**), ADR 0018 Amendment 1 (D4′, D5′), ADR 0014 Amendment 5 (D14, D15), and register entries R-088…R-090, with R-085…R-087 annotated.
- **The twin is not re-emitted.** No registered value changes. *Measured:* `--check` 347 of 347, and a fresh `--emit` is `cmp`-identical to `e97f61ce…`.
- **Probes** (this host, scratchpad `closing/`, not committed): the M1 caps sweep; B34 (a)'s ten closure values; the S5 reader matrix. No ensemble was run.

### 2.1 The eight rulings

1. **M1: the text moves, not the code.** ADR 0018 D4′ says that the refinement never changes an *attempt's* outcome but spends the solve's property budget like any iteration. A refusal in it, in the converged closure after it, or later in the solve is that step's `BUDGET_EXHAUSTED(property_calls)`.
   - **A second route.** A refined state that the region's closure converts opens a different later path (D4′ (ii)). This was identified here and has not been observed; A90 (A5) makes it visible.
   - **The message stays** `terminal_refinement(abandoned: EVALUATION_ERROR): …`, the core's word for a refused kernel call (D5′). The step carries the cause: its outcome, the meter's message, and `property_calls = max_property_calls`.
   - **Tests.** The plan-level test is **A96**. A88 (e)'s budget case is re-worded as a Newton-layer evaluation failure.
   - **Measured:** THM-09/1 `newton` needs 365 calls; `newton_refined` ends `BUDGET_EXHAUSTED` at caps 365, 366, 375 and 385 and converges at 386.
   - **Recorded:** ADR 0018's header and R-085 record Frank's approvals of 2026-09-26 (`bc45345`) and 2026-09-27 (`66861d5`). Q19 and Q20 are closed.
2. **A50 and S2.**
   - **The erratum is ratified:** A50 (b) is non-floats exact and floats 1e-12 relative, with `abs_tol = 0`, over **every** field, none exempt. The measured cross-machine difference is 1.2e-15 relative; every §9.4 tolerance is ≥ 1e6× wider.
   - **`certificate_sha256` is dropped** from the `ours-*` records, not replaced by a digest. The comparison reads the verdict, the limitations and the non-passing checks, which are fields of their own and compared exactly; the `t06` key already checks REF-01…07's certificate R0 across architectures (A45).
3. **A92's floor is `100 τ_T = 1e-4 K`, computed as `NEAR_THRESHOLD_MARGIN**2 * τ_T`,** a decade beyond K04's near-threshold band `(τ_T/10, 10 τ_T]`. The four moved values are recorded, not asserted.
   - *Measured:* the ten `FAILED` sit at 9.494e-4 K (×2), 3.209e-2 K (×2), 3.331e-2 K (×2), 23.78 K (×2) and 30.70 K (×2), none near threshold, so the minimum is 9.49× the floor.
   - §8.8 and §11 are corrected: "9.5e-4" was a rounded-up minimum, and it belongs to a state that was already `FAILED`, not to the four moved states.
4. **§7.3 (A5)** now states R-087's rule. After a solve has been seen, nothing that *scores* a start changes. A solver or verifier remedy, named by a design-lane amendment, re-runs the full gate on both classes (plan §6.5). Earlier runs stay on record. Run 2 is such a re-run. Run 2r and the holdout are records, not new gate results.
5. **The holdout, `holdout1`** (§7.6 (A5), A99, R-089): the nominal law at **start indices 20…39**. Its keys are `T06-ens-v1|nominal|<fixture>|20…39|<joint>|<coord>|<attempt>`, and no key is a gate key.
   - **Why start indices rather than a new first field.** `generator.py` is frozen with the nominal file (its SHA-256 is in the file, and A25 regenerates the file byte for byte), and its draw loop passes no prefix. `generator.generate_start(setup, i)` already takes the index.
   - **Generation.** On `ref-x86-64` only (`generate --holdout`), into `benchmarks/t06/ensemble/starts-nominal-holdout1.json`, committed **alone** with the registry's `ensemble.holdout` entry before any holdout solve.
   - **Runs.** At the closing commit, under run 2's policies, on `ref-x86-64`, `ci-x86-64` and `ci-aarch64`.
   - **Where it lives.** Run files, reports and the comparison go to `benchmarks/t06/ensemble/runs/holdout1-<class>.json`, `holdout1-<class>.report.txt` and `holdout1.compare.txt`, with `SHA256SUMS`.
   - **The report** carries the `HOLDOUT … never gated` header, no gate line, both CP bounds, A90's counts and `S_holdout − S_run2`.
   - **Manifest:** the starts file and run files as artifacts, the checks `T06.A99.*`, and a limitation stating `S`, `S^first` and the bounds per class, not gated.
   - **Failures.** An `F-GEN` counts as a failure and is not re-drawn. An `F-CRASH` is a defect. An `F-OTHER-ROOT` goes to the design lane.
6. **Run records** (§6.6 (A5), §7.5 (A5), A97, R-090). Format `t06-ensemble-results-v2` adds:
   - `run_id`, `commit`, `tree_clean`, `environment_lock_sha256`, and `cache_condition` from the registry;
   - `host.machine_class` from a harness function `machine_class()`: `GITHUB_ACTIONS=true` gives `ci-<arch>`; x86-64 with the registered CPU model gives `ref-x86-64`; anything else is `unregistered(<machine>)`. It is never `generator.py`'s literal, and `generator.py` is **not** edited;
   - per attempt, `refinements` parsed from D5's message.

   **Where run files live.** They are **committed JSON** under `benchmarks/t06/ensemble/runs/`, with `SHA256SUMS` and the registry's `ensemble.runs`, not in git-ignored artifacts. The judged run-1 and run-2 bytes are committed unedited with the verdicts' §0 hashes.

   **The instrumented re-run is required.** **Run 2r** re-runs run 2's 440 starts at the closing commit on every class to meet A90. Its per-start classes and `S` must equal run 2's per class (434 everywhere). Any difference is a discrepancy, reported to the design lane and the `verdict` agent before V20 is cited, and never resolved by editing a record. On `ref-x86-64` its refinement counts must equal the verdicts' reconstruction: 17 fired, 17 kept, 0 reverted, 0 abandoned, at the 17 listed starts (A98).
7. **T07 questions** are registered (R-088; spec Q24–Q29), each with a default in force:
   - S1: `FAILED` stays;
   - S4: the shift is unchanged;
   - N6 (W14): defence in depth;
   - N6 (W3): no concurrent verification within one process;
   - N2: messages stay outside R0;
   - Q29, new and found measuring S5: a non-canonical number in an unread field escapes as `CanonicalizationError`.
8. **S5: the codes are confirmed** as `specification_value_unsupported(<id>)` and `parameter_quantity_invalid(<instance>.<name>)`. That is `Unbound("unsupported", …)` from both bindings, and `DIM-01` `FAIL`, making `validate()` `INVALID`.
   - **The rule is wider than the review measured:** any JSON integer with `|n| > 2⁵³` (ADR 0002 D3.3), not only one beyond binary64's range. It applies to a specification's `value` and to a parameter Quantity's `value`, `bounds` and `nominal`. Such an integer gets exactly the result a same-signed non-finite float gets in that field on that path.
   - *Measured:* `2⁵³ + 1` raises `CanonicalizationError` on both bindings and the legacy `validate()`, and passes `DIM-01` on a revision-built document. ±∞ is typed everywhere, and `2⁵³` ≡ `2.0**53` everywhere. The test is **A100**.

### 2.2 Build-lane checklist, in order (spec §17 (A5))

| # | Chunk | Change | Acceptance test |
| --- | --- | --- | --- |
| 1 | **W24** (M1) | `numerics/newton.py`'s docstring sentence gets ADR 0018 Amendment 1 C5's exact text. A88 (e)'s budget test is renamed (its body unchanged). A96 is added as a plan-level test | A96 (a)–(c) on `ref-x86-64` and both CI architectures, with caps measured in the test; `git diff` touches a docstring and tests only |
| 2 | **W25** (S5) | One number-reading function for every specification and parameter-Quantity number (§8.5 (A5)) | A100 (a)–(b) over the path × field matrix; every registered revision's report, binding, label and key unchanged |
| 3 | **W26** (S2) | `scripts/t06_references_ours.py` drops `certificate_sha256`. The nine `ours-*.json`, then `SHA256SUMS` and `comparison.json`, are regenerated by their generators. A50's test loses its exemption | A50 (A5). `comparison.json` differs only in the nine `ours-*` `inputs_sha256` entries. Adding or editing any field of a committed record fails A50 |
| 4 | **W27** (S3) | The B34 floor becomes `NEAR_THRESHOLD_MARGIN**2 * τ_T`, with a comment citing A92 (A5) | A92 (A5): all ten `FAILED` ≥ 1e-4 K on every machine; the constructed values 5e-4 K and 5e-5 K pass and fail respectively |
| 5 | **W28** (harness) | The v2 record, `machine_class()` with the registry's `ensemble.machine_classes`, per-attempt `refinements`, `generate --holdout` and `check --holdout` (`generate` refusing off `ref-x86-64`), the report's A90 counts and holdout mode, v1 files read as "not recorded", `replay` defaulting to each case's first start, and the CI dispatch for run 2r and `holdout1`. **`generator.py` untouched** | A97 (a)–(d); A25 still byte-identical; A21–A36 unchanged |
| 6 | **W29** (P1) — **urgent** (the run-1 and run-2 files live only in `/tmp`; the CI artifacts expire 2026-12-25) | Commit, unedited, `run1-ref-x86-64.json` (`b82964be…`), `run2-ref-x86-64.json` (`c15924e6…`), `run2-ci-x86-64.json` (`8768b150…`), `run2-ci-aarch64.json` (`c1f89ee8…`, from CI 36270294833's artifacts), and `judged/run2-ref-x86-64.report.txt` (`eb24251e…`) and `judged/run2-ref-x86-64.replay.txt` (`b1a41a44…`); `SHA256SUMS`; the registry's `ensemble.runs` | A97 (e): hashes equal to the verdicts' §0, and the headlines recompute (run 1 431, FAIL; run 2 434 at 370 + 64 or 367 + 67, PASS). A differing hash is a stop-and-report |
| 7 | **W30** (holdout starts) | `generate --holdout` on `ref-x86-64`; commit the file alone with `ensemble.holdout` | A99 (a): indices 20…39, key prefixes disjoint, the generator and provider blocks equal to the nominal file's, byte-identical regeneration, A22–A24, A85 (a)–(b) |
| 8 | **W31** (runs) | At the closing commit (W24–W30 merged): run 2r and `holdout1` on `ref-x86-64`, and one CI dispatch for `ci-x86-64` and `ci-aarch64`; commit the run files, reports, replays and comparisons | A98 (a)–(d), A99 (b)–(d), A90 (A5). A discrepancy, a fired refinement in a non-final attempt, or a holdout `F-CRASH` or `F-OTHER-ROOT` comes back to the design lane |
| 9 | **W32** (manifest) | `evidence/T06/<closing commit>/manifest.json`: runs 1, 2, 2r and `holdout1` as separate records (A95 (A5)), the holdout in `limitations`; `docs/progress.md` | the manifest test; `status: tested` only with A96–A100 passing and A98 without discrepancy |

W24–W27 are mutually independent. W28 precedes W29 and W30. W30 is committed before any holdout solve. W31 runs once, at one commit.

### 2.3 Not ruled here

- The review's N5, N7 and N8 (a host-keyed A75 control; `np.float64` inputs to `convert_input_value`; X26's exact zeros). None blocks T06, and none is required.
- The stress profiles (§6.7). They are unchanged, and they are not part of this round.

### 2.4 For Frank (information, no decision needed)

ADR 0018 D4′ (ii) was found while making M1's text exact. A kept refinement's state feeds the region's converged closure. If that closure converts a phase, the next attempt starts from the refined state, so the later path can differ from `newton`'s. This has not been observed: in run 2, every fired refinement was the final iteration of its start's final attempt. It does not change the case for the T07 default you kept, and run 2r's records will show whether it ever happens.
