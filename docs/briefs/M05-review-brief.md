# M05 review brief (one `reviewer` pass, with the batched build-lane rulings)

**Subject.** `wp/M05` @ `7350684` (worktree `.claude/worktrees/m05`). WO-1…WO-9 done; WO-10 (manifest, support
matrix, progress, ADR 0039 note) follows this review. Authority: `docs/design/M05-trust-region.md` (1964 lines; §6
composition, §7 study and loop, §8 accounting, §9 records/replay, §12 work orders, §13 gates; rulings §16–§20, of
which §20 (l.1730–) is the latest: basis v2, `TRF_EXIT_UNVERIFIED`, G5b, at-the-bound R-404, accounting, WO-8b).
Build log `docs/design/M05-build-decisions.md` (681 lines, S1–S69). src diff vs base:
`git diff 32ceea50..7350684 -- src` (25 files, +12379); the trust-region core is `src/openflowsheet/studies/trust_region/`
(projection, study, holders, checks, trf_state, trf, truths, parent, basis), plus `studies/sensitivity.py`,
`studies/estimation.py`, `studies/nlp/*`. Tests `tests/test_m05_*`. Records `benchmarks/m05/records/`.

**What was run.** Full gate before every commit; last at `7350684`: 9287 passed, 31 skipped, 1 xfailed (G8); nlp tier 180
passed, 1 skipped; pymrm tier (M05) 1 passed. All runs `OMP_NUM_THREADS=1` (S59: OpenMP OpenBLAS changes digits with the
thread count; each record has `<stem>.environment.json`). Records and gates:
- TR-E2 G5 PASS: `TRF_EXIT_WITHOUT_STEP` k=0, θ_recheck 2.998e-6, |T*−T_ref| 0.00734 K.
- TR-E2-FAR G5b PASS: C1 `TRF_EXIT_UNVERIFIED(radius_limited)` k=7, C2 converged k=1, |ΔT| 0.0107 K.
- TR-E2-FD G6 PASS: converged k=1, |T*_FD − T*_E2| 0.0213 K, fd_check `truncation_dominated` at 2⁻¹⁴.
- G7 store bijection PASS on all records; G10 replay 0 differences on all six.
- LOOP-R G9 PASS: |d*−d_lb| 5.29e-8 scaled, P5 inward only.
- **LOOP-S G8 FAIL** (S64, strict xfail): stage A converged k=1 (θ_k0 6.55e-3, θ_recheck 8.88e-9), P2_A passed
  (objective error 5.95e-14), `DECISION_STABLE`, but T* 653.150021930406 K = **1.0965e-6 scaled** from d_lb (> 1e-6),
  so §7.4 classifies it interior and P5 polled both sides. R-408 expected `TRF_EXIT_WITHOUT_STEP` with θ_PMP ≈ 1e-14;
  measured 6.55e-3 because the property EFs' affine basis is not exact.
- **REAL** G11 PASS, G10-REAL PASS (S65–S69): fd_check `clean` at 2⁻¹⁴ (τ̂ 3.1e-3, ν̂ 6.9e-4); C1 converged k=1, θ_recheck
  2.33e-6, P2 passed; 48/400 cold, 1454 s of 14400 s; no cap hit (32/250). **T* = 653.1500352 K, 1.76e-6 scaled** above the
  lower bound — again interior by §7.4, both sides polled (reported, not gated). `extrapolated` 12 of 61 reactor requests
  (counted from the ledger; no record field, S69); the inlet H2/N2 sits on the kinetics' data edge, so the flag flips
  between solves 3.5e-5 K apart.

**Review the implementation against the design** — the TRF loop and its exits (R-401), basis v2 and the promoted basis
(S63), P2/P2_A references, P5 polling and §7.4's bound rule, accounting (store refunds, FD-check budget, ledger), record
identity and replay (G10, S68's REAL comparator: is it a real content check or does it excuse too much?), and whether
the gate tests verify anything (mutations: would a wrong T*, a wrong exit label or a broken bijection fail them?).

**Rule on these (batched; each a short ruling with the build action it implies):**
1. **At the bound (G8, REAL, §7.4, R-404).** R-404's rationale: the interior-point offset from an active bound is
   ≈ μ_final/z_L; LOOP-R's 5.3e-8 is that offset. LOOP-S (1.10e-6) and REAL (1.76e-6) both have a small objective slope
   (P5 plus-poll improvement ≈ −8.5e-5), hence small z_L and a larger offset. Is a fixed distance the right "at the
   bound" test, or should §7.4 use the solver's bound multiplier / an offset bound derived from μ_final and z_L (or
   solve with the bound active)? Give the evidence independent of the measured outcome for any change; never move a
   tolerance on the outcome alone. Say what G8 becomes and whether LOOP-S and REAL must be re-taken.
2. **R-408's premise** (θ_PMP ≈ 1e-14 expected, 6.55e-3 measured): does it change G8's other rows or the promoted basis?
3. **Unruled build choices:** S53, S56–S69, plus any earlier S-item the build log marks "for the review batch" or OPEN
   that §16–§20 did not rule (grep the log: e.g. S33, S37, S38). Confirm or reverse each.
4. **`extrapolated` (S69):** a record count field, or the ledger count suffices for W24 and M07 (M07 R-424 counts only the
   final coupling iteration)? And the data-edge flip: limitation wording only, or a finding to the reactor's owner?

**Rules.** No production-code edits. Write `docs/reviews/M05-review.md` (must-fix / should-fix / note with file:line, then
the rulings). Rulings that change the design go in a short §21 of the design note plus register entries **R-430…R-449**
(`docs/decision-register.md`; R-400…411 and M07's R-420…427 are taken). Commit on `wp/M05`, named paths only, trailer
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` / `Claude-Session: https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`;
push. Report ≤ 300 words: merge verdict (merge / fix first), must-fix list, one line per ruling, re-takes needed.
