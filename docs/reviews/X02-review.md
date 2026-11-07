# X02 review — declared warm starts (ADR 0070, ADR 0019 Amendment 15), WO-1…WO-5 on `wp/X02`

**By:** design lane (`reviewer`), 2026-11-07. **Brief:** `docs/briefs/X02-reviewer.md` (`e2520a93`). **Reviewed:**
`git diff main...wp/X02` at head `005d206f` (the application, orchestrator, adapter and identity code, the schemas, the
surface link, the X02 tests and the touched T07/T08/M02/M04 tests), against `docs/design/X02-warm-starts.md` and ADR
0070 (both on `main`), with `docs/X02_DECISIONS.md` (D-1…D-29), `docs/X02_HANDOFF.md` and the G5 records
`evidence/X02/69c4a24d…/`. This review sets no manifest status, and `reviewed` is not claimed anywhere.

## Verdict

**`wp/X02` is sound for identity, and no code defect blocks the merge.** Cold runs are unchanged, warm runs are keyed,
recorded and replay `MATCH`, and forged starts do not `MATCH`. Every new branch in a cold path is guarded by an
`is None` test that leaves the old expression intact: `build_request`, `_request`, `_exported`, `_export`, admission
step 6a, the one changed line in `execute_plan`, `couple(initial=None)` and `solve_coupled`'s cold call. I checked
this by reading the code and by measurement. A cold stand-in coupled run (`run_revision_session`, all nine artifacts
plus the R0 projection) is **identical on `main` and on the branch: 0 differences**, against 0 for `main` against
itself. Part A works on the real loop: G5e on v3 restarted in 1 outer iteration with 1 call, 24.9 s, against 174.9 s
cold.

All the must-fixes are in the documents. ADR 0070 and the note still say a warm variant gets registered and saves
11–15 % per call, and G5 disproved both (M-1). E9's inventory row misstates when it is enabled (M-2). The package can
become `tested` and merge after M-1, M-2, ruling 1's retirement, and WO-6's full gate, F0 and CI at the final head.
Merge without squashing, because the evidence pins commits `69c4a24d` and `005d206f`.

## Must fix before `tested` / merge

- **M-1 — Bring the authorities in line with G5 (D-29).** ADR 0070 D4 names `…-s123w-v1` with `child_warm.py` as "the
  first" start-capable variant. Its Consequences promise "about 11–15 % per call". Its acceptance evidence requires
  G5 to pass, and register draft D registers the variant. The note's §3.1, §3.2, §4 D4, §5.6, §6 WO-5 and §7 G5 say
  the same. G5 measured the opposite on both counts: (b) max rel 1.92e-7 against the decade rule's limit of 1e-7,
  and (c) about 21 % slower overall. G5b's "pass with a manifest note" band also contradicts I3 inside the note
  itself. If ADR 0070 is accepted as written, it records a false fact. Apply amendments A-1…A-9 below, which are
  docs only.
- **M-2 — `docs/recovery-edges.yaml` E9 (`:336-378` on the branch) is no longer `policy-only`.** The header defines
  `policy-only` as "only a policy that is not a route's default" takes the edge. A declared start takes it under the
  route's `default` policy, on both producers:
  - `_reject_initializer`, in G2's tampered source, `tests/test_x02_wo2_contract.py:199`;
  - `solve_coupled`, in G3 (c) and (d), both run under `default`.

  The `precondition` ("the policy's `initializer_chain` names a further source"), the `trigger` (x₀ checks only) and
  `max_count` are stale too. Minimal correction:
  - `enabled: default`;
  - precondition: "a start is declared in the solve request (`warm_start`), or the policy's chain names
    `compatible_warm_start`; no `user_start`";
  - trigger: add the `coupling_*` and `external_*` checks;
  - max_count: "once per declared or chained source: x₀, w₀, and each unit's k = 0 child start".

  `test_t08_w2_recovery_edges.py` allows `default` for E9. Only E12 and E13 are pinned by value. Re-run both T08
  edge tests after the change.

## Should fix

- **S-1 — One form for a record's `reason` (ruling 5).** Today one `solve-path.json` member carries both forms. On
  `legacy_eo`, x₀ reads `reason: "route"` (`revision_run.py:873`) while its `coupling` sub-record reads
  `"warm_start_rejected(route)"`. R0 projects `reason`, so this choice is frozen at merge. Use ADR 0024's convention:
  the record holds the bare check name (`coupling_integrity|coupling_compatibility|coupling_opening|route|
  external_integrity|external_compatibility`), and the trace message holds `warm_start_rejected(<check>)`. The places
  to change:
  - `coupled_run.py:777, 836, 848, 856, 895, 1109, 1120`: the records;
  - `:1101` and `:1130`: wrap the reason for the trace;
  - the tests' expected strings;
  - note §5.2, §5.7 and §5.9 (A-7).
- **S-2 — Part A's neighbour claim has no real-loop evidence.** G3b runs on the stand-in, where X̂ = 0.25 is constant:
  it converges in 2 outer iterations from the start or cold, so the Δû bound holds trivially. G5d (iii) was the only
  real-loop test of the bound and of "warm takes fewer outer iterations", and it was dropped together with the
  variant. It needs no warm variant. Run G5d (i)–(iii) on **v3**, with cold experiments and the neighbour edit
  SPEC-S3-T +2 K: about 10 reactor calls, one workstation run, inside the load rule. Otherwise, qualify ADR 0070's
  Consequences: "a neighbouring revision restarts near its fixed point (measured on the stand-in only)".
- **S-3 — G3f is not pinned to its cause.** `test_g3f_a_forged_declared_iterate_does_not_match` (`:350`) asserts only
  `!= MATCH`. I ran it as a probe. It gives `MISMATCH` (`compatible_reproduction`), with the difference
  `external_request(0, reactor).inputs<root>.n[0]: 2.3046633724521355 against 2.7156113537118047`, so it fails for
  the right reason today. Assert `MISMATCH` and the `external_request(0` difference, as G4e already does.
- **S-4 — Disclose the replay change for pre-X02 bundles in ADR 0070's Migration proof.** Take a coupled `T08-warm-v1`
  bundle written before X02 with K ≥ 1. Its candidate was `absent` or `rejected`, so it carries no `warm_start`
  member. Before X02 it reproduced `MATCH`. Under Part C its rerun writes the k = 0 member (`absent`), so it reproduces
  `MISMATCH` on R0. Bundles of this kind whose candidate was *accepted* already reproduced `MISMATCH`: that is the
  Part C defect. F0 holds no such bundle. The behaviour is correct, but the ADR's "no existing document gains a
  member" should state this consequence for reproduction.

## Notes

- `g5a_v3_keys_recomputed_equal` is `false` at all 8 inlets while the inputs are equal. That is consistent with the
  engineer's explanation and not caused by X02. The fingerprint includes `thread_env` and `cpu_model`
  (`child.py:420, 432`), and the campaign pinned `OMP/OPENBLAS/MKL_NUM_THREADS=1`.
- D8's disclosure also fires when the warm chain fell back (`used: false`). The final request carries `start`, but the
  answer was cold. That is conservative, so leave it.
- The trace emits external `initializer_rejected` events before the `coupling_warm_start(...)` candidate event
  (`coupled_run.py:1099-1103`). Only the order looks odd, and trace events are outside identity. Optional: reorder.
- G5e does not record whether the v3 restart's k = 0 was a cache hit (24.9 s). F1 on the real loop stays unanswered.
  R5 is unchanged.

## Rulings

1. **D-29 / the warm variant: do not register it** (this agrees with the orchestrator; Frank's Q1 can still overrule).
   The reasons:
   - G5b: 1.92e-7 is 0.72 decades below 1e-6, and I3 requires one.
   - Raising the floor is not free. The floors scale with `precision_floor_rel` (`coupled_run.py:423-428`). A floor
     high enough to register 1.92e-7 (≥ 1.92e-6) would drop the real loop's T floor ratio from 13 (§3.2) to about
     6.8, below `FLOOR_RATIO_MIN` = 10.
   - G5c removes the motive: S1 was saved, but round 2 ran at 6 of 8 warm inlets against 4 of 8 cold.

   **`child_warm.py`, `tests/test_x02_wo5_warm_child.py`, `benchmarks/x02/variant-s123w-provisional.json` and
   `benchmarks/x02/g5_warm_reactor.py` leave the package at WO-6.** The campaign script imports the child, so it
   cannot stay without it. They remain reproducible at `69c4a24d`/`005d206f` in the merged history. `evidence/X02/
   69c4a24d…/` stays, including G5e as Part A's real-loop record. WO-4's plumbing stays. D10 stays as well: set
   `CHILD_SCRIPTS = ("child.py",)` and rewrite D-21's allowlist justification for one entry. The count stays 36. The
   note needs amending: yes (A-1…A-3, A-8, A-9).
2. **D-11 (G3 (c) on a loop with H₂ make-up lowered to 0.725): accepted.** The premise was falsified on a 12-point grid
   that included all four corners. The test proves both inner outcomes before it uses the feature, so the gate cannot
   pass vacuously (A-6).
3. **The ulp through u = w₀/s: acceptable as disclosed.** The bounds are compared in u-space as bound/s
   (`coupling.py:311-322`), so a projected start stays inside them. The record keeps the declared value and
   `iterations[0].w` the one used. A rerun recomputes both identically. I measured the round trip:
   fl(fl(w/s)·s) = w held for 600 000 values w = fl(u·s), s ∈ {0.1, 50, 100}. A job source's w₀ is therefore bitwise
   the source's w, even though fl(w/s) ≠ u in about 12 % of cases. That is harmless, because r is evaluated at w.
   **D-13** (integrity = the note's three checks, no key recomputation) is also accepted: the keys play no part in w₀.
4. **Register numbers.** `main` holds R-942…R-949 from RP. `wp/MSG`'s R-942 and R-943 already collide with them, so
   MSG renumbers in any case. Whichever of X02 and MSG merges second does three things:
   - renumbers its register entries to the next free numbers;
   - becomes `c_5` with the digest of the combined tree, measured after its rebase;
   - re-takes the R4-G3 job-operation snapshots.

   R-950 is free on `main` today. ADR 0070's drafts A–E take numbers at acceptance.
5. **The form of the x₀ rejection reason: not "keep both".** Unify on bare check names in records, with
   `warm_start_rejected(<check>)` as trace messages only (S-1). Pre-merge is the only time this is free.
6. **The other build decisions.**
   - D-14: accepted. E9 is the right row, because the edge is the same: a start is rejected and the next source runs.
     It needs M-2's correction.
   - D-20: accepted. `start=None` is forwarded, so nothing changes.
   - D-21: accepted, with ruling 1's wording.
   - D-7: accepted. When a declared source is rejected, the run must not silently fall to a different job's state.
     The note's D2 table says otherwise, so amend it (A-4).
   - D-5, D-6, D-9, D-10, D-12 and D-15…D-19: accepted.
   - D-22…D-28 leave with the child. D-22's finding stands: the note's two G5 sequences are the same four keys.
7. **ADR 0020 D7: the registered full-path test is sufficient.** The evidence:
   - G6 runs through `submit_job` at both corners of the bounds. A `VERIFIED` outcome requires both EXT-COUPLING checks
     to pass at the converged state.
   - G3a shows that even an exact converged start re-evaluates its experiment and is re-certified.
   - G3f and G4e show that a forged recorded start does not `MATCH`.
   - Q26 pins exactly the two scalar paths.

   The verifier never receives the start, so K04's W14 identity refusal has nothing to refuse. Here the W14 property
   is "only ever a start", and G6 pins it. With S-3 the forged case is pinned to its cause.

## Amendment text

Design note (`docs/design/X02-warm-starts.md`):

- **A-1 (§3.1, after the table):** "*Measured (G5c, `evidence/X02/69c4a24d…/`):* the gain did not materialise. At 8
  inlets the warm chain took 287 s against 133 s (g12) and 383 s against 420 s (cand-C1-P1): about 21 % slower
  overall, with per-inlet ratios from 0.37 to 4.60. S1 was saved, but the KPI-drift certificate's round 2 ran at 6 of
  8 warm inlets against 4 of 8 cold. The certificate's cost is not independent of the start."
- **A-2 (§3.2, last sentence):** "**The outer start (Part A) is the lever:** G5e on v3 restarted in 1 outer iteration
  and 1 call (24.9 s) against 4 iterations cold (174.9 s). The child start (Part B) gave no gain (§3.1)."
- **A-3 (§2 I3 and §7 G5b):** "Strike the band 1e-7 < max ≤ 1e-6, which contradicts I3. Pass iff max ≤
  `precision_floor_rel`/10; otherwise the variant is not registered. Raising the floor is a separate decision: the
  EXT-COUPLING floors scale with it."
- **A-4 (§4 D2, x₀ row):** "A declared `job_id` replaces the lineage lookup. If it is rejected, `traversal-G0-v1`
  follows (D-7)."
- **A-5 (§2 I8):** "The run never fails because of a start that fails a check. A start that passes its checks is the
  run's start: from (0, −50) the stand-in ends `COUPLING_NOT_CONVERGED` (`external_refused(nh3_below_trace)` at
  k = 0), where the cold run verifies (G6). That is recorded, not a fallback case (D3)."
- **A-6 (§7 G3 (c)):** "The registered stand-in opens everywhere in its bounds (D-11). (c) uses that loop with H₂
  make-up 0.725 mol/s, from (0.95, −50), and first proves the inner outcomes. The byte reference for (c) and (d) is a
  second cold run under the same cache state (D-10)."
- **A-7 (§5.2, §5.7, §5.9):** "The `reason` members of the `coupling` and `external` sub-records are bare check names.
  `warm_start_rejected(<check>)` is the trace message only."
- **A-8 (§4 D4, §5.6, §6 WO-5, §8 Q1/Q6):** "*Outcome:* `…-s123w-v1` was built and measured (G5, `69c4a24d`) and is
  not registered: G5b fails I3, and G5c shows no gain. Its runner, tests, variant and campaign script left the package
  at WO-6. The Part B plumbing (§5.5) stays with no start-capable variant registered, and the synthetic child (G4)
  tests it in CI. A future start-capable runner needs a new design and its own G5. Candidates: seeding S3, a larger
  warm S2 `dt_init` (F4), a cheaper certificate."
- **A-9 (§4 D10):** "Kept: the selection is among the packaged scripts, today `child.py` alone."

ADR 0070:

- **D2:** "x₀: internal `user_start` > `job_id` (when declared, it replaces the lineage lookup) > `T08-warm-v1`
  lineage > `traversal-G0-v1`."
- **D4**, replacing its second sentence: "X02 registers no start-capable variant. The measured candidate
  `pymrm-6089593-g2-nz800-s123w-v1` (`child_warm.py`, `69c4a24d`) failed D6's decade rule (1.92e-7 against 1e-6)
  and was about 21 % slower than the cold chain (note §3.1). It is not registered and its runner is not shipped. The
  behaviour below is the contract for a future start-capable runner."
- **D7:** the sub-record reasons are bare check names (S-1).
- **D8:** "…among the packaged child scripts (today `child.py` alone)."
- **Consequences**, bullet 2: "No start-capable variant is registered. The measured warm reactor chain was slower
  (G5c). Part B ships as plumbing, tested in CI." Qualify bullet 1 as S-2 requires.
- **Migration proof:** add S-4's sentence.
- **Acceptance evidence:** "G0–G4 and G6 pass. G5 (a) and (e) pass. G5 (b) and (c) decided against registration.
  G5 (d) [ran on v3 per S-2 | was not run]."
- **Register draft D:** "*Decision:* no warm reactor variant is registered (G5b 1.92e-7 > floor/10; G5c −21 %).
  Programs are selected by `runner_sha256`. R-224 is lifted only for start-capable variants, and none is registered.
  *Rejected:* registering with a raised floor, because the real loop's T floor ratio would drop from 13 to about 6.8;
  registering in the manifest-note band, because it contradicts D6. *Evidence:* `evidence/X02/69c4a24d…/`."

## What was run (head `005d206f`; load about 22 of 48; one job at a time; logs in the session scratchpad)

| What | Result |
| --- | --- |
| The six X02 test modules (WO-1…WO-5, G0 keys) | 88 passed |
| The G0-listed tests plus every touched T07/T08/M02/M04 test (Q26, global state, surface chain, R4-G3, recovery edges, edge identity) | 294 passed |
| G3f probe | `MISMATCH` for the reason S-3 cites |
| Cold stand-in coupled run, `main` against branch | 0 differences over all artifacts and R0 |

## Not established by this review

- The full gate, F0, the batteries' D-14 and D-21 fixes in full, and CI. These belong to WO-6.
- G5 itself. I did not re-run any reactor campaign; I took the numbers from the records and checked their summaries.
- The cold identity of `revision_eo` and `legacy_eo` against `main`. I measured only the coupled stand-in; the rest
  rests on code reading and the passing tests.
- `child_warm.py` beyond `WarmReactor`, because it leaves the package.
- The CLI, HTTP and MCP transport code beyond the WO-2 transport test.
- Budget accounting across a rejected opening.
- How MSG absorbs the tokens.
