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
| M03 | Design | T08 | W24 (part) | complete; main merged in (`086bf2b`); CI green on both runners (`2ed3f22`); manifest → `tested` and merge when Frank answers N1 |
| M04 | Design | M02 | W23 | **tested** (manifest `evidence/M04/a9566a6…`, 57/58, A33 n/a); WO-1…20 done; real b2-it1 on v3 NOT_PROMOTABLE (`band_not_finite`, 26/632 certificate refusals; finite |e_X| ≤ 7.3e-4, |e_ΔT| ≤ 0.32 K); E32 relative-path fix in launcher (`f3fd44e`, proved); gate 8653 at `3f99eee`. Review `9c2cb64` (§20 Am. 3, R-360…369): fix first — MF1 added/renamed surrogate instance bypasses promotion check (`replacement.py:240`, A48), MF2 checker doesn't tie failed lists to null scores (`manifest.py:541`); SF1 pin BLAS to 1 thread (A49), SF2 (A50); 4.1 % refusals: no amendment (iteration-1 honest end). Running: engineer Am. 3 fixes + main merge + new manifest. Then merge into main (M05 uses parent per N6) |
| M05 | Design | M03, M04 | W24 | WO-1…7, 2b, 3b, 4a, 5c done; main merged; S3 parent adapter `C1Parent` (`40acf09`, gate 8786; real v3 at 673.15 K CONVERGED/VERIFIED 164 s, P3 passes); REAL box [653.15, 693.15] K. Next: merge `wp/M05-rulings2` (`4cc5956`, §18) → WO-2c/6b/7b → WO-8 runs → `reviewer` (batch Z2, W2, S1–S26: S22 solve_route vs run_revision_session/bundles, S24 P4 regime labels, S23/S25/S26). NLP-1 inventory `--check` fails on 3 unrecorded objects (libssl.so.3, _ssl, _queue) — pre-existing at `71804a6`, M03 inventory stale |
| M06 | Build | T08 | W26, W27 | **tested, reviewed by the design lane, merged into main `7473f35`**; ADR 0030 + ADR 0019 Amendment 3 Accepted; WO-17 (3 canaries + 45-run campaign) at M07 — needs v0.2 binder reading in `snapshot.READINGS`, M01/M02 id rows, U14 rewrite for campaign records, `specifier` read of registration §20 |
| M07 | Design | M05, M06 | W25, W21–W27 | spec not started: branch `wp/M07` (`.claude/worktrees/m07`) holds `docs/briefs/M07-recon-digest.md` + `docs/briefs/M07-specification.md` (`e35b16d`); a `specifier` was launched and stopped at Frank's pause request (left an uncommitted `docs/derivations/scripts/m07_reference.py`, unreviewed) — relaunch fresh with the same brief |

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

- **M03 N1:** accept the licences of an optional, non-default `nlp` extra; the [A10] audit (PASS, `docs/m03-ipopt-audit.md`
  on `wp/M03-audit`) found exactly: EPL-2.0 (Ipopt, cyipopt), CeCILL-C (MUMPS, Scotch), public domain (PORD, SQLite),
  Apache-2.0 (METIS 5, OpenSSL), Apache-2.0 WITH LLVM-exception (libomp), BSD-3 (OpenBLAS, SPRAL, hwloc, libuuid,
  Pyomo), ASL BSD-3 + f2c notice, MIT (libxml2, libffi), **LGPL-2.1-only** (libiconv), **GPL-3.0 WITH GCC RLE from
  conda-forge** (libstdc++, libgcc_s, libgfortran, libquadmath), PSF-2.0, bzip2, 0BSD, BSD-2, Zlib. Default: accept;
  without it W24's M03 optimizer part stays BLOCKED.

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
alt. Frank accepts V18 (c) FAIL, Q-A2-1, not recommended). §18.5 actions 1–2 done (`2e778d3`, gate 8591; Am2.5 inert: G2 dump byte-identical, K05 identity PASS, solution states identical). Design read `eb108c4`: proceed, no must-fix (S2 accepted: §18.4 (b) covers the 2 CI steps; S3 prove machine_class imports in dist/clean venvs before cut; S1 dist-record tests). Running: engineer re-cut C_α¹ + RC steps 1–12 + manifest (actions 4–7) and M04 Am. 3 fixes; then design read of the diff, re-cut, re-run.;
M05 merge main + WO-5c + S3 (`m05`). No new launch until fewer than 2 run.
Stopped at Frank's pace request, work saved on branches (pushed): `wp/test-hardening` `1d90625` (t07_w5b pins the
single-threaded env itself — gate + merge pending); `wp/M06-wo17` WIP commit (ungated); `wp/M07` WIP reference script
(spec still to write). Done in the burst: M02 closeout merged (`2497ec2`); M05 rulings §18 on `wp/M05-rulings2` (`4cc5956`).
Register: alpha R-319…321; M04 R-322…325; M05 R-326…330; M07 from R-331 (continue R-350); M02 closeout R-340…344; alpha Am. 2 R-345…349; M04 review R-360…369.
Queued M02 follow-up (after the alpha RC): C1 inert-floor exact compare (`boundary.py:390`, few-ulp slack), R-341 R0
guard, R-343 L-rows.
After these: cut C_α¹ → RC steps 1–12 → M07a manifest `tested` → alpha verdicts (W21, W22, V11–V20) → step 13 → WO-11 → Frank publishes `0.2.0a1`; M04 merge after review;
M05 WO-8 + `reviewer`; M07 build.

In worktrees run `PYTHONPATH=$PWD/src PATH=<main>/.venv/bin:$PATH ./scripts/gate.sh`. W27 archive for tests: symlink the
directory `.claude/worktrees/m06-w27h/evidence/M06/W27/artifacts` to `evidence/M06/W27/artifacts`, remove after.
Push `main` at milestones (authorised).
