# v0.2 — campaign state

Position, not history. Rewritten in place. Read after `CLAUDE.md` and `docs/progress.md`. History:
`docs/V02_DECISIONS.md` (append-only).

| | |
| --- | --- |
| Objective | Plan v1.2 §4.4: M01–M07, the scientific reactor replacement; release gate W21–W27; release `0.2.0` |
| Chemistry | C1, the ammonia synthesis loop (ADR 0022, R-120); `docs/v02-real-chemistry-dossier.md`; reactor `ammonia_synthesis_reactor` `main` @ `6089593` (MIT) |
| Order | R-153: M01 design first; M06 built alongside; M03 when the critical path allows; pre-release `0.2.0a1` after M02 `tested`; `0.2.0` after M07 |
| Concurrency | **At most 2 agents at a time** (Frank, 2026-10-09; was 4). Agent budget rules: `CLAUDE.md` "Agent budget" |
| Repository | Public `origin` only (R-150); pre-push guard installed; pushing to `origin` authorised (Frank, 2026-10-08) |

## Packages

| ID | Lead | Depends | Gate | Status |
| --- | --- | --- | --- | --- |
| M01 | Design | T08 | W22, W21 (part) | **tested, reviewed by the design lane (closure `9098f14`), merged into main `997c7da`**; ADR 0026 Accepted; ADR 0027 Proposed until M02's adapter halves |
| M02 | Build | M01 | W21 | **tested, reviewed by the design lane (`docs/reviews/M02-review.md`), merged into main `9f6a9be`** (manifest `evidence/M02/ba90619…/manifest.json`; main gate 8371 passed). Reactor v3 on V5. Unruled build choices D130–D132 for a later design read; G12 cross-architecture reproduce not run (stated limitation) |
| M03 | Design | T08 | W24 (part) | complete; **N1 answered: Frank accepted the licences (2026-10-16)**. Closeout part 1 done (`b074d57`: R-450, main merged, inventory re-taken: +libssl/_ssl, same licences). **tested, merged into main `0bdb80d`** (manifest `evidence/M03/a35885b…` 52/0/0; CI green both runners; N1 accepted R-450) |
| M04 | Design | M02 | W23 | **tested, reviewed by the design lane (`docs/reviews/M04-review.md`, §20 Am. 3), merged into main `78685cc`** (manifest `evidence/M04/8df0ea7…`, 60/61, A33 n/a; main gate 8670). Real b2-it1 on v3 NOT_PROMOTABLE (26/632 certificate refusals; finding to the reactor's owner); M05 uses the parent model (N6). MF1/MF2 fixed (A48, A24 mutations), BLAS pin A49 (`d65bb022…` at 1 and 48 threads). Later design read: E36 in-tree OpenBLAS pin vs threadpoolctl (lock hash), E37 backlog id B10, E38 A48–A50 W23 placement; Q-A2.1 open |
| M05 | Design | M03, M04 | W24 | WO-1…7, 2b, 2c, 3b, 4a, 5c, 6b, 7b done; S33 (basis inside holders' run, bitwise), S36; main merged (`d65a9a4`); gate 8889 pre-merge; S44 (`a5927b4`): services injected into `C1Parent`, gate 9187, nlp 167/1, bitwise dumps identical. Pre-WO-8 ruling §19 `4c83d15` (R-383…389): coupling digest exact, compared by shape between runs, records saved and file-checked; fd_check float classes; no job entry needed (scripts are the composition root). Was: S40 `coupling_record_sha256` exact_sha256 (replay identity), float rule for `fd_check`; **WO-8 partial (`6a9d29d`, gate 9212): G10 PASS (3 replays, 0 diffs); G5 FAIL (F-15: TR-E2 TRF_MAX_ITERATIONS, θ saw-tooth min 1.03e-5 never ≤ 1e-5, T* Δ 0.024 K); G6 FAIL (same exit; FD vs exact ΔT* 1.1e-5 K); G9 FAIL by a hair (LOOP-R |T*−653.15| 1.067e-6 K vs 1e-6); G7 partial; G8 not run (stage-A surrogate truth/basis missing, S52); S51 budget charged on store hits (TR-E2 record parked); S50 FD check charged to no budget.** F-15 diagnosis `04454d7`: affine basis → start at box corner; every step = radius, θ = C·Δ²; radius rules hold θ ≈ 1e-4 so 30 iterations spent travelling; ≤1e-5 termination is luck (k=28 near-false at 0.66 K off); 150 iterations reach θ 9.72e-6. Ruling §20 `a9d05d3` (R-400…409): basis `M05-basis-v2` (affine + truth curvature, scratch TR-E2 0.0074 K off), `TRF_EXIT_UNVERIFIED` for radius-limited exits, TRF config unchanged, G5/G6 restated + new G5b (start 663.15 K), G9 bound = 1e-6 scaled (2e-5 K), store hits refund budget, FD check on study budget, WO-8b = SurrogateTruth/LOOP-S/G8 (stage A uses promoted quadratic, R-408). WO-8a/8c/8d done (`f72a875`, gate 9238, nlp 177/1): TR-E2 TRF_EXIT_WITHOUT_STEP θ 3.0e-6 T* 0.00734 K off; TR-E2-FD converged k=1; LOOP-R converged k=2; v1 runs bit-identical; S51 resolved (47 = 31+16); committed v1 records drift ~1e-15 across environments. WO-8e done (`5961915`, gate 9257): v2 records; G5, G5b, G6, G7, G9, G10 PASS; drift was the OpenBLAS thread count, runs now pinned to 1 thread (S59–S61). WO-8b committed `55250e1` (gate 9273 + 1 xfail, nlp 180/1): **G8 FAIL** at the bound (|d*−d_lb| 1.0965e-6 scaled vs 1e-6; R-408 premise θ≈1e-14 measured 6.55e-3), strict xfail, for the review batch (S64). WO-9 REAL done `7350684` (gate 9287 + 1 xfail): G11, G10-REAL PASS; REAL T* at the bound by 1.76e-6 scaled (same question as G8); FD-3 provenance added, AQ2 no. Review `f0693d8` (§21, R-430…435): fix first, MF1 `noise_ratio` formula; G8/G9 restated (within δ_T 0.5 K of the bound and P5 evaluates the bound). WO-10a done `748f8cf` (gate 9289, nlp 186): MF1 fixed, 3 re-takes identical except noise_ratio/timings, G8 PASS, nlp replay test. WO-10b done (`1032ed0`): N2 fixed, **manifest `evidence/M05/cfecb15…` tested (14/14)**, harvest, W24 table. Main merged into wp/M05 (`eb17f79`; inventory re-take 181 objects `33b03b6` S76; five G10 in-process records re-taken digest-only after D134 changed the fingerprint `56fb2fa` S77), gate 9319, nlp 186/1, CI 39018247132 green both runners. **Merged into main `defa458`** (manifest `evidence/M05/56fb2fa…` tested; main gate 9325). Open for the next design touch: review N1, S75, S77 (re-take vs fingerprint scope; default: keep the re-take) |
| M06 | Build | T08 | W26, W27 | **tested, reviewed by the design lane, merged into main `7473f35`**; ADR 0030 + ADR 0019 Amendment 3 Accepted; WO-17 (3 canaries + 45-run campaign) at M07 — needs v0.2 binder reading in `snapshot.READINGS`, M01/M02 id rows, U14 rewrite for campaign records, `specifier` read of registration §20 |
| M07 | Design | M05, M06 | W25, W21–W27 | **spec written** (`wp/M07` `48d4112`, `docs/derivations/M07-spec.md`; ADR 0041 journey/W25, ADR 0042 0.2.0 policy, Proposed; R-331…339; 40 assertions; journey = inlet T on C1-LOOP-M02-v1 at R0 stand-in grid / R1 PyMRM v3 grid / R2 surrogate not promotable / R3 M05 on parent; budget 460 cold runs/6 h). WO-1/WO-2 done (`53ba75f`, gate 8731; A00–A08, A10–A15 tested; R0 live: 9 stand-in solves VERIFIED, INDIFFERENT, J = 0.46705958492513017; spec issues J3–J9 for ruling round; ruling round 1 done `9ef4543` (spec §18 Am. 1, R-420…427); WO-2b done `6e2640d` (gate 8751; R0 unchanged except as ruled: experiments in_process 2, extrapolated 0); FD-3 in M05 WO-9 brief). WO-4 part 1 `6996507` (gate 9412): journey at J ran, check OK, R3 = M05's T*/J* bitwise; WO-4b done `d8ae8c1` (record at J=`1623633`, numbers bitwise = part 1; replay bitwise 13.4 s; A20–A26 tested; gate 9435, nlp 186/1). Review `0ad726a` (fix first; spec §19 Am. 2, R-452…455): MF1 at-bound tolerance δ_T 0.5 K (headline must read BOUND_LOWER), MF2 carry file list incomplete (split r3/journey files, GC-CARRY-1); SF1–SF3; J22 stands, J25 → M02 follow-up (`env.py:347`), J27 OK. WO-4c done `9d2d072` (J′ `974c395`: every number bitwise = old record; R3 + journey now BOUND_LOWER; check ACCEPT; replay bitwise 17.7 s; gate 9454/31 each commit; nlp 186/1). Next: WO-3 after the alpha merge, then WO-5 (cut C_W on main, paid W27). Alpha → main merge running on `wp/V02-alpha-main` (unblocks WO-3). Blocked: WO-3 (gate entry, after alpha merge), WO-5 = M06 WO-17 (paid), WO-6…8. Finding: ADRs 0036/0037 Proposed on main (0.2.0 gate needs Accepted); 0033–0035 Accepted only on alpha branch |

## Milestone 0 (housekeeping)

- [x] Web-shell design inputs ported from `design/web-shell-brief` (pre-0.1.0 base, cannot be pushed) onto `main`
- [x] Frank's K_NH₃ decision (R-152), the order (R-153), the dossier statement
- [x] `ci.yml` actions pinned by SHA (`67029fa`; 44 lines; inputs checked against the new majors; test added)
- [x] T08 close-out review (`docs/reviews/T08-closeout-review.md`): all five confirmed, no must-fix; F1/F2/N1/N2/N5 applied as T08 spec Amendment R8
- [x] **F3 hand-on:** T08's own manifest (58 limitations, 16 without L/U id; A70, B23) is an input to v0.2's support-envelope harvest. Closed since the alpha: the manifest is in the harvest (`tests/test_m07a_harvest.py:1-10`, `:28`, `:85`; `scripts/t08_support_matrix.py:478-482`). Ticked by C3 (d)
- [ ] Schema `$id` move (R-149, `docs/decision-register.md:3470`; R-185, `:4245`) — not done in v0.2 and not in C3: it changes every schema's identity, a frozen interface (CLAUDE.md: only by a design-lane ADR). v0.3 backlog; trigger: the first v0.3 schema change, with the ADR written then

## Open inputs (M01, dossier `needs_fact`)

PR parameter set (T_c, P_c, ω, c_p, ΔH_f per value from open, cited sources: `chemicals`/`thermo`, cross-checked
with CoolProp or Cantera; group database a cross-check only); a cited k_ij source; high-pressure NH₃–H₂–N₂ VLE data;
the loop's pressure-drop convention (ADR 0022 D2); whether the reactor keeps its own fugacity correlations or takes
PR's. K_NH₃ settled (R-152: the code's 7000 cal/mol).

## Needs Frank

- **Answered 2026-10-18 (Frank):** N1 claim all seventeen; N3 no equilibrium rung; N5 carry V17 across R-192/R-234/R-295.
  Still to answer after the 0.2.0 verdict (dated acceptances): N4 V14 (b), N6 M02 N1; N7 only if the W27 surface differs.
- **For 0.2.0 later (M07 spec, defaults set, not urgent):** claim all 17 gates (yes); M03 N1 licences accepted 2026-10-16; add an equilibrium-reactor fidelity level (no); re-accept the PTC failure, the agent-evidence carry and "not a sandbox" for 0.2.0 (yes); if the agent-facing surface changes after the paid W27 run, stop and ask.
- **`0.2.0a1` RELEASED 2026-10-17** (tag `v0.2.0a1` → `423ae9c` on the alpha branch; run 39045791146 all green; on PyPI and as a GitHub pre-release). Nothing open for Frank on the alpha.
- **M03 N1:** answered 2026-10-16 (accepted).

- **M01 (defaults set, work proceeds):** Q-F1 the reactor's inlet heat loss (23–33 % of reaction heat through the
  inlet face) — intended, or Danckwerts? default: as pinned, reported; Q-N1 c_p source — default NASA TM-4513, not
  Poling; Q-N2 fix F-R1/F-R2 upstream at a new pin? default: keep `6089593` + subclass/overlay; Q-N3 design grid —
  default num_z = 800 (~9 s/solve); Q-N4 ship the real C1 records in the wheel — default yes, with citations; Q-N5
  a structured `synthetic` field in ModelManifest — default no schema change in v0.2.

- **W27 (defaults set):** Q3 up to 3 re-canaries within the approved budget; Q4 agent false verification reported
  with its bound, not gated; Q5 run the approved 45 even if 0 cases are candidates (alternative: 15 runs).

- **M02 (defaults set):** N1 accept "not a sandbox" (`external-subprocess-v1`) for local v0.2 use; N2 no CI job for
  the reactor environment; N3 `v0.2-alpha-gate-v1` = v0.1 gate unchanged + W21, W22 met, no other claims (for
  `0.2.0a1`); N4 ship the synthetic stand-in, listed synthetic; N5 defer the PR LIQUID regime and pure-NH₃ flash;
  N6 no reactor warm start.

- **M03 threading (new):** make single-threaded BLAS/OpenMP (`OMP_NUM_THREADS=1`) a product rule for NLP runs?
  Default: recommended and recorded in every report, not enforced (it is reproducible and faster: 1.7 s vs 3.2–3.9 s).

- **M04 (defaults set):** N1 experiment budget — 632 cold reactor runs for iteration 1 and up to two more. **Corrected
  2026-10-08:** a real evaluation takes 25–45 s (not 9 s), so iteration 1 ≈ 4.4–7.9 h serially — but Amendment 1 pre-warms the cache with 16 parallel
  experiment jobs, ≈ 16–30 min for iteration 1 (bitwise identical); N2 width limits 0.0025 in conversion, 1.5 K; N3 gradient limit 0.25; N6 M04 counts as `tested`
  whatever the real verdict, and M05 uses the parent model if the surrogate is not promotable.

- **`0.2.0a1` (alpha gate, ADR 0028; defaults set):** N3 claim set = V11–V20 re-judged + W21 + W22, W23–W27 not
  claimed; carry the V14(b) FAIL acceptance into this release (dated after the alpha verdict); **carry V17 across the
  surface changes R-192/R-234** as R-133 did (alternative: a new agent campaign, ≈USD 10); accept M02 N1 "not a sandbox"
  for a published release; W21(f) read as adapter-reproduces-standalone + group tests + error travels + published
  validation cited (the stronger reading would BLOCK W21 on the 4TU data statement); publish via release.yml with your
  approval, marked pre-release. Preferences on defaults: cut `C_α` before M03 merges; freeze distribution paths from
  `C_α` to dispatch.

- **M02 N7 (V5 selected by measurement: inerts ≥ 3.5 %, T_in [653.15, 693.15] K, V3's P and H₂/N₂; default R-315: ship the first of V4 (inerts ≥ 3 %), V5 (≥ 3.5 %), V6 (V5 narrowed in P, H₂/N₂) that
  qualifies, all at T_in [653.15, 693.15] K; inlets below the floor refused `out_of_domain`; the loop runs at 4.0–4.5 %):** shipped reactor domain = the box the v3 measurements select (R-304: [643.15, 733.15] K
  if it passes, else [653.15, 693.15] K, else narrowed P and H₂/N₂). Full 573–773 K would need a new start strategy,
  outside M02's plan row.

- **M05 (defaults set):** N-F1 objective = maximize liquid NH₃ product, reactor inlet T the only decision (alt: an
  economic objective with your prices, making purge a second decision); N-F2 decision tolerance 0.5 K; N-F3 real-reactor
  budget 400 experiments / 4 h; N-F6 decision box [643.15, 733.15] K.

Otherwise nothing open. Answered 2026-10-08: Amendment 3 approved; W27 spend (45 runs, USD 15–45) approved; pushing to
`origin` authorised. Earlier: F2 agent model = most recent, pinned by ID; F3 fonts system; F4 scenario = run comparison;
F5 education mode deferred.

## Next action

**Position (2026-10-26, workstation; no cloud sessions).** `main` = `77f54168` (wp/R796 merged at `3a2c17ae`, tree identical:
R-795, R-796, T07 report line). Last full gate: PASS at `3a2c17ae`: 13288 passed, 3137 skipped. CI 40403579501 green.
v0.3 packages tested: S01–S05, S07, S08, S08b, S09, S10, S10-C; R01–R03 open. **Way of working (Frank, 2026-10-26):** batch
several items per branch, two engineers in parallel, one gate + one CI per batch.
**S08b** (manifest `evidence/S08b/acbd1266…` tested 18/20, gate/CI unsupported; review `docs/reviews/S08b-review.md` sound,
no must-fix): `S08B-IDENTITY PASS a=52 a_texts=11 b_keys=6075 b_moved=61`; B2 1.6e-6 K. HARVEST_SIZE (59, 832, 101).
**S10-C** (ADR 0049 Proposed; `evidence/S10c/2aedd250…` tested): γ–φ PH flash and column; R-782/R-785/R-786.

**Next actions (in order):**
1. **S11 — the binding package** (Frank, 2026-10-26: "I want the binding package"; supersedes the library-only defaults S05
   Q-8, S10 Q-F2/R-709, S10-C Q1/Q3). wp/S11, worktree `s11`; brief `docs/briefs/S11-binding-design.md`, recon
   `docs/briefs/S11-binding-recon.md`. Architect design + ADR 0050 running (register from R-800). Then tracks A and B in
   parallel, one review, one gate, one CI. Fold in: the two stale S10 limitation sentences; R-796's limitation into the
   S08b/S10-C manifests at their next regeneration.
2. **After S11 merges: revision-region continuation** (edge 3 for flowsheet regions; Frank 2026-10-27 "plan for it at the
   appropriate time"; removes S11's L-COL-9, R-827). Design pass first.
3. **PrISMa rework as a test case** (Frank, 2026-10-27: "get OpenFlowsheet to the level that it can rework PrISMa analysis
   as one of the test cases"). Target: Charalambous et al., Nature 632 (2024), doi 10.1038/s41586-024-07683-8; data Zenodo
   10.5281/zenodo.11244258 (cifs, simulated isotherms, heat capacities, all case results); layer software on request only.
   Needs: adsorption-isotherm property model (CO2/N2/H2O), TSA/TVSA cycle unit (PrISMa's "ideal" model first), TEA (nCAC, CCC)
   and LCA adapters, MEA reference, CO2 compression (S11). Scoping/design pass after S11.
4. Ternary column claims need a methanol+ethanol refit (S10 S-4).
5. Design-lane leftovers: S07 B-42, F-20.2, Q-A1-2; ADR 0046–0049 acceptance; S03 B6-1..B6-4; S10 B-86, B-87, B-90, B-91,
   verdict F1/F2; S08 W5-7 (X31 in `evidence` not `requirements`, schema takes D/A ids), W5-9 classes; S10-C W5-1/W5-2;
   the two stale S10 limitation sentences (Frank "Do it later", at the next S10 change).
6. S07b cryogenic liquids; crosscheck re-take; pr-lib-v1 clean-up.
7. Workstation backlog: M05 N1/S75/S77 (L2), M04 off-Haswell / J25 (L3), L1.
8. For Frank (defaults set, `docs/FRANK_QUESTIONS.md`): S10-C Q1–Q4 (Wilson in flowsheets: no; IDAES column comparison:
   deferred; cascade/other units: no; purity/recovery/temperature specs: refused); S10-C F2 (theorem premises at admission,
   deferred to the binding package, R-781); S08b Q1 (v3 feed-band rule: not now); S08 Q1/Q3/Q4/Q6; Q-S09-2; Q-A6.2/Q-A6.3;
   S10 Q-F3 (ship after rights check; RC-05/06/08 unresolved). Remote scratch branches `wp/S08`, `wp/S09`, `wp/S10C`,
   `wp/S10C-diag`, `wp/S10C-diag2` may be deleted by Frank.


**History — W27 campaign running (2026-10-18):** C_W = `wp/M07` `83f825d` (WO-17b `d0307d8` + merge; gate 9923/35; CI 39136157258
green). Records `benchmarks/m06/openidaes450/runs/w27-m07-83f825d/` in worktree `m07` (uncommitted until (d) ends).
(a) coverage 0/450 CANDIDATE, G14 PASS; (b) 45 drawn, canaries prommis NF / mvo CO2 / cryst n13; (b′) confirmation written;
(c) canaries 3/3 passed first attempt (pin `claude-sonnet-5-5`, the login's CLI default; Claude Code 2.1.302; USD-eq 0.23);
(d) preflight P1–P8 pass; 45 runs done: CORRECT_LIMITATION 44, WRONG_LIMITATION 1 (26 pervaporation), 0 false verification /
unauthorized / critical; order exit 0; spend USD-eq 3.38. Records committed `wp/M07` `22ae1e3` (gate 9923/35). Verdict `14d4527`
(`docs/reviews/W27-verdict-83f825d.md`): (a)–(d), (f), (g) MET; (e) NOT MET, repaired (`89cd931`, campaign.json
`4812910a…`), **re-judged MET** (`c50e6fb`). WO-6 merged (`10ae324`, gate 9935/35). Rulings 4 and 5 merged into `wp/M07` (`73d0b72`, `d3c72cb`; gate 9935/35): R-473 step 17, R-474; R-475 test_a10 the fourth exempt alpha function, R-476 ledger tests skip at a covered version while the verdict doc is absent (step 18 YES only where the ledger gives 5 passed), R-477 K = A + G10 records after the test commit F (spec §23.4). WO-8a done: F `48db2d3`, A `0fcf1ad` (0.2.0), K `2c508b5` (G10 re-take = E6 counts, digest-only), journey record `9f880e7` (T* 653.1500351610193 K, BOUND_LOWER, bitwise = J′; check ACCEPT; carried; gate 9956/35; CI 39215524713). Design-lane note J55: opt-in pymrm replay of J′'s old record fails since the alpha lineage (not default gate/CI). WO-8b part 1 (J56–J59, `0335573`): C = `c899c85` (WO-10 done; gate 9956/35; CI 39224213490/39224203477 green). RC steps PASS 1–8, 10, 11, 13, 15, 16, 17 (17d campaign.json `4812910a…9e28`, diff empty); step 9 FAIL locally (A30 imports `greybox.py` → `cyipopt`; CI says pass); step 12 G11 BLOCKED (`--d78`, `--previous-runs` inputs lost with `worktrees/m02`); step 14 needs a re-run minus `test_m03_reference.py`. ADRs 0031, 0032, 0038, 0039 still Proposed. WO-8b part 2 (J60–J66, `8547e96`): step 14 PASS (640/2; w24-nlp-trf 4/4); step 9 fails on CI too (A30 workload imports the `nlp` extra's modules; `ci.yml:812-821` `set +e` hides it); G11 inputs unrecoverable, not byte-reproducible; step 1 skip lines extracted. Ruling round 6 merged (`bc7d8e9`, R-478…R-484): A30 workload skips the three registered `nlp` modules, the `nlp` extra judged by `mr12_extras_v02`; CI fails `rc-steps` on a failing A30; G11 re-taken with a registered D78 extract; ADRs 0031, 0032, 0038, 0039 Accepted; J′ replay skips; C superseded, all steps 1–17 re-run at C′; K stays. WO-8c part 1 done (J67–J73, `ef86fb3`): C′ = `ce99365` (A30 workload 182 walked/179 imported; `mr12_extras_v02`; CI fails rc-steps on failing A30, proved on run 39252474979; D78 extract test; A24 skip; gate 9982/35; CI 39276061202). WO-8c part 2 done (J74–J77): RC steps 1–17 ALL PASS at C′ `ce99365`; records commit `2fd23a6` (gate 9982/35; CI 39291243747 dispatch, 39311681016 push). **0.2.0 RELEASED 2026-10-20** (tag `v0.2.0` → `5c82b4c`, release run 39412610914; PyPI + GitHub release). M07 merged into main `8a06b91`. Verdict `docs/reviews/V02-verdicts.md` (Judged and re-judged 2026-10-20): 16 PASS, V14 (b) FAIL accepted under D3. Frank's five ADR 0042 answers 2026-10-20; ADR 0041/0042 Accepted; M07 manifest `evidence/M07/ce99365…` tested; `v0_2_gate.py --rc ce99365 --candidate 38935b2`: "v0.2.0 tag may be proposed: YES". CI on main 39399661594 green. Main-checkout gate: 10013 passed, 1 failed (`test_v02a_r347_machine_class` — the install check strips sys.path under the repo root, and the main checkout's `.venv` is inside it; passes in worktrees and CI). A8-Q1 deferred (M07a's ~42 envelope rows unclassified). Findings for later: verdict F7 (G11 job_id pattern), F8 (audit accepts a point relabelled `direct`), J55. **Next: the queued readiness re-check (ADR 0008 A2) and the OpenIDAES-450 split registration — on Frank's go.**

**Queued for the 0.2.0 cut (Frank, 2026-10-18):** transient-readiness re-check (ADR 0008 Amendment 2), `architect`, brief
`docs/briefs/ADR-0008-A2-readiness-recheck.md`; after M07 merges into main.
Also queued (Frank, 2026-10-18): OpenIDAES-450 development/held-out split registration, `specifier`, brief
`docs/briefs/OpenIDAES-split-registration.md`; before any OpenIDAES-targeted scope.

**2026-10-15: burst over; back to ≤ 2 agents (Frank).** Alpha WO-10 done (`wp/V02-alpha-gate` `4d591c7`, gate 8580): RC steps 1–9, 11, 12 PASS at `C_α`; step 10 FAIL (F1: 5 coupled-route
certificates qualify 4 extra ids — EXT-COUPLING:T/xi, derivative_witness on/off → V18 (b) FAIL by Q5 default); M07a manifest `implemented`
(A39, A43 fail; A43 = 13 t08_rc records lack machine_class). Amendment 2 ruled (`ab80ca5`, R-345…349): F1 = certificate defect (EXT-COUPLING/witness write `None`), failure is V18 (c) not (b);
A43 needs a registered `machine_class`; wrapper output accepted. **`e0e198e` superseded → re-cut C_α¹ and re-run steps 1–13** (R-349;
alt. Frank accepts V18 (c) FAIL, Q-A2-1, not recommended). §18.5 actions 1–2 done (`2e778d3`, gate 8591; Am2.5 inert: G2 dump byte-identical, K05 identity PASS, solution states identical). **C_α¹ = `6fec822`** (branch `wp/V02-alpha-rc1`; e0e198e + Am. 2 fixes). RC steps 1–12 PASS (CI 38772065394/38772054427; step 10: 77 certificates, 0 violations; step 12 cert bound `faa8e4da…`). M07a manifest `implemented` 37/0/6 (A52 + A60–A64 wait on verdicts by design). C_α⁰ record → `docs/v02-alpha-rc-record-e0e198e.md`. **Verdicts `fffb0e4`: 8 PASS (V11, V12, V15, V16, V18, V19, V20, W22); V14 FAIL (b); BLOCKED V13 (e), V17 (a), W21 (c) — on Frank's ADR 0028 answers.** Amendment 3 `6505315` (R-370…379): **re-cut C_α² needed** (A1: frozen envelope claims aarch64 for the reactor); date rule: re-judgement line, Frank's answers must fall between first verdict and re-judgement (Q-A3-1 strict: answers before C_α²'s verdict don't count). §19.8 actions 1–4 + status rule done (`958af67`, gate 8629). **C_α² = `cc73219`** (`wp/V02-alpha-rc2`): RC steps 1–12 PASS (CI 38813135468/38813136015; step 10 0/77), **M07a manifest `tested`** (38/0/6). C_α¹ record/verdicts moved to `*-6fec822.md`. **Verdicts at C_α² `f14f02e`: same as C_α¹ — 8 PASS, V14 FAIL (b), BLOCKED V13 (e)/V17 (a) (V17 carry), W21 (c) (M02 N1).** Frank asked (2026-10-16) for the 4 answers. B6 done (`758a902`, R-380…382): ADRs 0027 (= main), 0033, 0034, 0035 Accepted; gate dry run now refuses only on ADR 0028 + Frank's answers. B5: §20 Amendment 4 applies only if Frank declines M02 N1 (claim set without W21, re-cut C_α³). M02 follow-up merged into main (review `54b7baa`; manifest `evidence/M02/6c3a087…`; D133 R-341 guard, D134 C1 slack 4·2⁻⁵², D135 R-343 L-rows; gates 8672/8675/8675; merge after alpha, expect envelope conflict: take L47/U15 from alpha, [5]→L46 from follow-up; needs a manifest); then design read of the diff, re-cut, re-run.;
M05 merge main + WO-5c + S3 (`m05`). No new launch until fewer than 2 run.
`wp/test-hardening` merged into main (`26b13db`, gate 8670). Saved WIP: `wp/M06-wo17` WIP commit (ungated); `wp/M07` WIP reference script
(spec still to write). Done in the burst: M02 closeout merged (`2497ec2`); M05 rulings §18 on `wp/M05-rulings2` (`4cc5956`).
Register: alpha R-319…321; M04 R-322…325; M05 R-326…330; M07 R-331…339, R-350…359, R-391+; M02 follow-up R-390; M05 WO-8 ruling R-400…409; ADR 0036/0037 acceptance R-410…411; M02 closeout R-340…344; alpha Am. 2 R-345…349; M04 review R-360…369; alpha Am. 3 R-370…379, B6/B5 R-380…382.
Next: alpha on main (merged `93cfbe5`, version 0.2.0a2.dev0) → M07 WO-3 done (`wp/M07` `271f70d`, gate 9876/35, CI green; A30, A32–A38, O1–O3 pass; A31 conflict J40) → ruling round 3 done (`958b983`, spec §20 Am. 3, R-461…466: A31 restated with an ast test vs the tagged file; J39/J41/J42/J43 confirmed; spec A62 right, registration fixed with a `check` allowance for the `gate` member; ADR 0042 headers fixed; journey runs at the 0.2.0 cut commit K and carries K→C) → Am. 3 build actions done (`wp/M07` `bdd2004`; registration hash 85e56dd5…; gate 9887/35; CI 39113895404 green) → W27 WO-17a done (`wp/M07-w27` `1219636`; A70–A78 pass; stub dry run end to end OK; gate 9910/35) → unpinned-record ruling `a230156` (R-472: `model` null only in canary attempts, `pinned.model` = init model; A23/A51 restated; A79) → **running: WO-17b + merge `wp/M07-w27` into `wp/M07` (no spend)** → C_W = that merge → paid run; W27 rulings done `bbf1d01` (registration §23, R-467…471: U14 text, draw before canaries with hash-chained order, confirmation/preflight records, ≤6 canary attempts, model pinning mechanical); W27 readiness done `273ab0f` (ready; P1–P5, P8 pass; CLI + USD 45 spend ceiling; runbook `docs/briefs/W27-runbook.md`) → prerequisites → cut C_W (on `wp/M07`; M07 cannot merge before WO-5…8) → paid W27 (WO-5) → (0.2.0 gate); M07 WO-4c (review fixes, re-take) → M07 manifest; then WO-5 (M06 WO-17, paid, approved), WO-6…8, 0.2.0 RC;
M05 WO-8 + `reviewer`; M07 build.

In worktrees run `PYTHONPATH=$PWD/src PATH=<main>/.venv/bin:$PATH ./scripts/gate.sh`. W27 archive for tests: symlink the
directory `.claude/worktrees/m06-w27h/evidence/M06/W27/artifacts` to `evidence/M06/W27/artifacts`, remove after.
Push `main` at milestones (authorised).
