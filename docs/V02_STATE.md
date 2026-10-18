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
- [ ] **F3 hand-on:** T08's own manifest (58 limitations, 16 without L/U id; A70, B23) is an input to v0.2's support-envelope harvest
- [ ] Schema `$id` move (deferred to v0.2 by ADR; R-149) — with M01's or M06's first schema change

## Open inputs (M01, dossier `needs_fact`)

PR parameter set (T_c, P_c, ω, c_p, ΔH_f per value from open, cited sources: `chemicals`/`thermo`, cross-checked
with CoolProp or Cantera; group database a cross-check only); a cited k_ij source; high-pressure NH₃–H₂–N₂ VLE data;
the loop's pressure-drop convention (ADR 0022 D2); whether the reactor keeps its own fugacity correlations or takes
PR's. K_NH₃ settled (R-152: the code's 7000 cal/mol).

## Needs Frank

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

**2026-10-15: burst over; back to ≤ 2 agents (Frank).** Alpha WO-10 done (`wp/V02-alpha-gate` `4d591c7`, gate 8580): RC steps 1–9, 11, 12 PASS at `C_α`; step 10 FAIL (F1: 5 coupled-route
certificates qualify 4 extra ids — EXT-COUPLING:T/xi, derivative_witness on/off → V18 (b) FAIL by Q5 default); M07a manifest `implemented`
(A39, A43 fail; A43 = 13 t08_rc records lack machine_class). Amendment 2 ruled (`ab80ca5`, R-345…349): F1 = certificate defect (EXT-COUPLING/witness write `None`), failure is V18 (c) not (b);
A43 needs a registered `machine_class`; wrapper output accepted. **`e0e198e` superseded → re-cut C_α¹ and re-run steps 1–13** (R-349;
alt. Frank accepts V18 (c) FAIL, Q-A2-1, not recommended). §18.5 actions 1–2 done (`2e778d3`, gate 8591; Am2.5 inert: G2 dump byte-identical, K05 identity PASS, solution states identical). **C_α¹ = `6fec822`** (branch `wp/V02-alpha-rc1`; e0e198e + Am. 2 fixes). RC steps 1–12 PASS (CI 38772065394/38772054427; step 10: 77 certificates, 0 violations; step 12 cert bound `faa8e4da…`). M07a manifest `implemented` 37/0/6 (A52 + A60–A64 wait on verdicts by design). C_α⁰ record → `docs/v02-alpha-rc-record-e0e198e.md`. **Verdicts `fffb0e4`: 8 PASS (V11, V12, V15, V16, V18, V19, V20, W22); V14 FAIL (b); BLOCKED V13 (e), V17 (a), W21 (c) — on Frank's ADR 0028 answers.** Amendment 3 `6505315` (R-370…379): **re-cut C_α² needed** (A1: frozen envelope claims aarch64 for the reactor); date rule: re-judgement line, Frank's answers must fall between first verdict and re-judgement (Q-A3-1 strict: answers before C_α²'s verdict don't count). §19.8 actions 1–4 + status rule done (`958af67`, gate 8629). **C_α² = `cc73219`** (`wp/V02-alpha-rc2`): RC steps 1–12 PASS (CI 38813135468/38813136015; step 10 0/77), **M07a manifest `tested`** (38/0/6). C_α¹ record/verdicts moved to `*-6fec822.md`. **Verdicts at C_α² `f14f02e`: same as C_α¹ — 8 PASS, V14 FAIL (b), BLOCKED V13 (e)/V17 (a) (V17 carry), W21 (c) (M02 N1).** Frank asked (2026-10-16) for the 4 answers. B6 done (`758a902`, R-380…382): ADRs 0027 (= main), 0033, 0034, 0035 Accepted; gate dry run now refuses only on ADR 0028 + Frank's answers. B5: §20 Amendment 4 applies only if Frank declines M02 N1 (claim set without W21, re-cut C_α³). M02 follow-up merged into main (review `54b7baa`; manifest `evidence/M02/6c3a087…`; D133 R-341 guard, D134 C1 slack 4·2⁻⁵², D135 R-343 L-rows; gates 8672/8675/8675; merge after alpha, expect envelope conflict: take L47/U15 from alpha, [5]→L46 from follow-up; needs a manifest); then design read of the diff, re-cut, re-run.;
M05 merge main + WO-5c + S3 (`m05`). No new launch until fewer than 2 run.
`wp/test-hardening` merged into main (`26b13db`, gate 8670). Saved WIP: `wp/M06-wo17` WIP commit (ungated); `wp/M07` WIP reference script
(spec still to write). Done in the burst: M02 closeout merged (`2497ec2`); M05 rulings §18 on `wp/M05-rulings2` (`4cc5956`).
Register: alpha R-319…321; M04 R-322…325; M05 R-326…330; M07 R-331…339, R-350…359, R-391+; M02 follow-up R-390; M05 WO-8 ruling R-400…409; ADR 0036/0037 acceptance R-410…411; M02 closeout R-340…344; alpha Am. 2 R-345…349; M04 review R-360…369; alpha Am. 3 R-370…379, B6/B5 R-380…382.
Next: alpha on main (merged `93cfbe5`, version 0.2.0a2.dev0) → M07 WO-3 done (`wp/M07` `271f70d`, gate 9876/35, CI green; A30, A32–A38, O1–O3 pass; A31 conflict J40) → ruling round 3 done (`958b983`, spec §20 Am. 3, R-461…466: A31 restated with an ast test vs the tagged file; J39/J41/J42/J43 confirmed; spec A62 right, registration fixed with a `check` allowance for the `gate` member; ADR 0042 headers fixed; journey runs at the 0.2.0 cut commit K and carries K→C) → Am. 3 build actions done (`wp/M07` `bdd2004`; registration hash 85e56dd5…; gate 9887/35; CI 39113895404 green) → **running: W27 WO-17a (registration Am. 4 build actions, no spend; `wp/M07-w27`)**; W27 rulings done `bbf1d01` (registration §23, R-467…471: U14 text, draw before canaries with hash-chained order, confirmation/preflight records, ≤6 canary attempts, model pinning mechanical); W27 readiness done `273ab0f` (ready; P1–P5, P8 pass; CLI + USD 45 spend ceiling; runbook `docs/briefs/W27-runbook.md`) → prerequisites → cut C_W (on `wp/M07`; M07 cannot merge before WO-5…8) → paid W27 (WO-5) → (0.2.0 gate); M07 WO-4c (review fixes, re-take) → M07 manifest; then WO-5 (M06 WO-17, paid, approved), WO-6…8, 0.2.0 RC;
M05 WO-8 + `reviewer`; M07 build.

In worktrees run `PYTHONPATH=$PWD/src PATH=<main>/.venv/bin:$PATH ./scripts/gate.sh`. W27 archive for tests: symlink the
directory `.claude/worktrees/m06-w27h/evidence/M06/W27/artifacts` to `evidence/M06/W27/artifacts`, remove after.
Push `main` at milestones (authorised).
