# RP review — ADR 0055 parts 1–3 (WO-R1 design text; WO-R2, R3, R4, R6 on `wp/RP`)

**By:** design lane (`reviewer`), 2026-11-06. **Brief:** `docs/briefs/RP-reviewer.md` (`27a32e6a`). **Reviewed:** RP
(`docs/derivations/release-procedure.md`, WO-R1 `6714958d`), `release/lines/{0.3,0.4}.json`, ADR 0055, and
`git diff main...wp/RP` at head `05e3e069` (`release_gate.py`, `release_evidence_manifest.py`, `release_rc.py`,
`release_rc_local.py` in part, `ci.yml`, `release.yml`, `check.sh`, the `test_rel_*` modules), with
`docs/RP_DECISIONS.md`. This review sets no manifest status, and `reviewed` is not claimed anywhere.

## Verdict

**RP is sound as the standing release procedure once the amendments in §17 below are made, and `wp/RP` implements
it, with one gap in the evidence.** The line-file loader, the inheritance rule, the role-based resolution, the scope
fingerprints (P1–P4, E1–E4, F1) and the standing rule are correct as written and as built. The dated path is
equivalent to the legacy gate: REL.A03 compares the whole report dict, the text and the markdown over YES, all twelve
NO items, A07's three states and A08. Because the dated path is `engine.main` with a `ReleaseLine` that REL.A02 shows
equal field by field, comparing on fixtures only is enough. The gap is in standing mode, the path 0.4.0 will actually
use: nothing pins its twelve decision items (M-1, demonstrated by mutation). REL.A20 fails as written, but the cause is
a classification error in RP §11.2, not in the code (M-2). The package can become `tested` and merge once M-1 to M-3
hold and the full gate and CI pass at the final head (ruling 8). K-1 and K-2 must hold before 0.4.0's K3, not before
the merge.

## Must fix before `tested` / merge

- **M-1 Nothing pins standing mode's decision items 1–12.** `release_gate._build_standing` (`scripts/release_gate.py`
  878–998) recomposes `engine.build` by hand. The standing tests have one YES fixture plus A06–A10. RP.S06 ("one NO
  fixture per item, with the line's values") is decided by `SPECS["S06"]`, which runs V03's `a06_` (the legacy gate)
  and REL.A03 (dated mode). Neither of those runs standing mode. *Measured:* with `engine.rc_record_problems`,
  `manifest_problems`, `envelope_problems`, `adr_problems` and `links_problems` all blanked to `[]`,
  `tests/test_rel_standing_acceptances.py` still passes 40 of 40, the same as the unmutated baseline. So if the
  composition dropped an item, or the version or tree check, nothing would catch it. *Fix:* add 0.4-line,
  standing-mode NO fixtures for items 1–12 through `release_gate.build`, each flipping only its item and asserting
  that item's reason. Add them to `SPECS["S06"]`.
- **M-2 REL.A20.** Apply amendment A-1 (ruling 3) in `release_evidence_manifest.rel_a20` and in the REL.A20 test. Then
  REL.A20 must read `PASS` over 0.3.0's records.
- **M-3 ADR 0055.** Append the restated acceptance condition and the notes of ruling 2 to ADR 0055 (text below, for
  the build lane to paste).

## Must fix before 0.4.0's K3 (not merge blockers)

- **K-1 (Q-C6)** The schema ADR of ruling 4 has been applied, so that `evidence/REL040/<C>/manifest.json` can pass
  `t08.problems`.
- **K-2** ADR 0055 is marked Accepted on its restated condition (M-3), so that P3 holds without a
  manifest-conditioned ADR.

## Should fix (before 0.4.0's cut)

- **S-1 (Q-B4)** `row_state` evaluates a row only at C. A replacing row that keeps the old `Accepted at` and carries
  C's fingerprint, which is an easy copy-paste error, is then treated as standing, and §8.4's date bound is skipped.
  *Fix:* A-2. A row stands only if its scope also reproduces `Fingerprint` at `Accepted at`. `_differing` already
  makes that evaluation.
- **S-2 The line file can change after C.** The gate reads it at the candidate H2 and the manifest at G. Both are
  outside D2.4, so an `rc_items` or `gates` edit after C changes what is judged, and no check sees it. A claim-set
  edit lapses `Claim set`; nothing else is caught. This was equally open for `v0_3_gate.py`, so it is not a
  regression. *Fix:* A-3, and the gate refuses (exit 2) when the chain's bytes differ between C and the candidate.
- **S-3 CI run selection in the manifest.** `t08._jobs` takes `success` from *any* run at C. It checks neither the
  event nor the attempt, so one red dispatch plus one green dispatch passes RP.S11. `items --ci-run` also accepts any
  dispatch at C. *Fix:* A-4's rule. Exactly one push run (§6.2's rule) and one `release_rc` dispatch (greatest id,
  latest attempt). Every other run at C is listed in the step-1 record with its attempt and conclusion, so that a
  retry is visible to the verdict.
- **S-4 A push run at C may not exist.** GitHub starts a push run only for the pushed head. If C is pushed together
  with later commits, step 1 fails with no remedy stated. *Fix:* A-4. C is pushed on its own, as a branch head.
- **S-5 (Q-C3)** `release_rc_local.step12` runs `git show bd446ab:…` without a check: a failed `show` writes an empty
  file silently. The id is abbreviated, and the inputs are not registered. *Fix:* A-5.
- **S-6 Rehearse the steps that never ran.** Steps 6, 11, 12 (with step 10 auditing step 12's certificates), 14, 15
  and 16, and `E01-G6-nlp`, have never run. A broken runner found at C forces a re-cut, because the records carry the
  checkout's commit. *Fix:* one background run of `release_rc.py local` with every step, at a `main` commit after the
  merge and before K3. Until then the manifest names each step that has not run (ruling 8).
- **S-7** `release_rc.items` ignores `gh run download`'s exit status. PTC-R1's artifacts are V14's evidence for the
  verdict. *Fix:* record the exit status and the file count in the item's check. A `ci:` item whose download failed
  is `fail`.

## Notes

- **N-1** `gates[*]` against the Basis column of `docs/reviews/V03-verdicts.md`: every T(g), R(g) and criteria entry
  matches. B10–B19 and B40–B49 are in `tests/test_t08_*`, and `a41.g12` exists in 0.3.0's step-12 record. At the
  0.4.0 revisit, consider adding to `documents`: W25 `benchmarks/m07/journey`, W21 `docs/support-matrix.md`, and for
  V13 the two V17 documents (its Basis rests on the V17 carry). This matters only for the verdict brief while D2 is
  deferred.
- **N-2** The manifest decides the D assertions, S09, S10, S16 and S17 itself. S11–S15, S19–S21 and the items re-read
  the RC records' statuses and check ids, as S13's manifest did (R-914). Their strength is the record writers' and
  those writers' unit tests. The manifest should say so in one limitation.
- **N-3** `_m_changelog` counts each phrase with `str.count`, so a phrase that is a substring of another is
  over-counted. Match whole lines.
- **N-4** D1.5's `REL` plus digits collides once a version component reaches 10 (1.10.0 and 11.0.0 both give
  `REL1100`). This is far off; settle it in the ADR of ruling 4.
- **N-5** Step 6 runs concurrently with steps 2 to 15. That affects wall time only: the registered budgets are counts.
- **N-6** `check.sh` expands an empty array under `set -u`, which needs bash 4.4 or later. CI is fine.

## Rulings

**1. RP's own design.**
- F-1 to F-8: each is upheld as RP resolves it and goes into ADR 0055 as a note (ruling 2). F-8 is
  **needs a decision** for Frank. RP plans up to two messages, where ADR D5 says one. My recommendation: keep two, and
  send the first only when it is non-empty. One message after `Judged` would bring back the `BLOCKED` row and
  0.3.0's re-judgement round.
- Q-1 (role): upheld. Q-2: upheld. Q-3: upheld. Q-4: upheld. Q-5: upheld. Q-7: upheld. Q-8: upheld.
  Q-10 (lists sorted): upheld. Q-14: upheld. Q-15: upheld.
- Q-6: upheld (n ≥ 1, recorded). The verdict compares n with the previous release's record.
- Q-9: upheld. The term hashes in `release/acceptances.md` and the shell recomputation in §8.2 are the independent
  expectation, and B measured all eleven term hashes recomputing exactly.
- Q-11: the default stands. This is Frank's preference.
- Q-12: upheld, subject to ruling 2 and K-2.
- Q-13: upheld. Measured at 1 min 54 s and 1 min 28 s against 360 min, so PTC-R1 stays. Whether it reproduces V14
  (b)'s registered outcome is the verdict's call, from the artifacts (S-7).
- `gates[*]`: upheld (N-1).

**2. ADR 0055's acceptance condition, restated for the D2 deferral (F-3, Q-12).** Paste this under ADR 0055 §10:

> **Acceptance, restated 2026-11-06 for Frank's "1–3 now, 4 later" (RP review, ruling 2).** Proposed → Accepted for
> D1, D3, D4, D5 and D6 when: REL.A01–A10 and REL.A17–A20 hold in a `tested` manifest of the migration package (filed
> as `S15`, R-878's rule), with REL.A20 as RP §11.2 and RP amendment A-1 define it; the `reviewer` pass on WO-R2–R4 and
> WO-R6 is recorded (`docs/reviews/RP-review.md`) and its must-fix items are closed; and N-3 and N-6 stand on their
> defaults (N-1, N-4 and N-5 lapsed with D2). D2 is not part of this acceptance: R-916, R-917, WO-R5, REL.A11–A16 and
> A21, `release-audit`, the `strace` parts of WO-R4 and WO-R6, gate item 13 and `gate_row:`. Adopting D2 is a new
> decision recorded the same way, with its own acceptance condition and an RP amendment. Until then, D3.6's V14 (b)
> scope is the path fallback. **Notes:** D1.3 resolves by the line file's `role` (RP §3.5, F-1). D3.2's `paths:`
> selection is RP §8.2 P1–P4, because `git ls-tree -- <globs>` does no glob matching (F-2). D4.2's job list includes
> `rc-ensemble` (F-4) and, while D2 is deferred, excludes `release-audit` (Q-C1). The wrapper writes each item's
> record (F-5). D3.4's "carry report" is RP §8.5's lapse report (F-6). REL.A20 is defined by RP §11.2 (F-7). A
> failure-clause row is asked after `Judged`, in a second message (F-8). WO-R4's junit measurement is read on the push
> run at the dispatch's commit, because the dispatch skips `check` (Q-C2).

**3. Q-C5 (REL.A20).** Move RP.S18 to the changed-form list, with a comparable sub-check. Its rule quantifies over
the catalogue, whose changed-form members cannot pass on 0.3.0's records, so V03.A27's status has no same-form
counterpart. This is F-7's own reasoning applied to S18, which the specifier misfiled. It does not relax anything:
A-1 keeps the part that can be compared. Comparing S18 over the same-form checks only is rejected, because it
introduces a second definition of S18 that holds only inside REL.A20.

**4. Q-C6 and C-22 (package ids).** The id goes through a schema ADR, not an S-id rule. R-938 (ADR 0059) reversed
R-878's rejection of widening, because picking ids does not scale, and RP needs one id per release forever. Proposed
ADR (next free number): widen the `work_package` pattern additively by `|REL[0-9]{3,}`, apply it alone, and test it
as `test_work_package_pattern_widening_is_additive` does. N-4's collision is settled there. **RP's own manifest stays
`S15`** (C-22 upheld). It is already harvested, and moving it would churn `HARVEST_SIZE` for nothing. `S15` is free
in the roadmap, and C-22 needs a register line.

**5. Standing acceptances.**
- Q-B1 (`Accepted at` = C means new): upheld, together with A-2 (S-1).
- Q-B2 (Table T7's upper bound kept for decision items): upheld.
- Q-B3 (wording): kept with no engine edit. The `D3` and `D4` suffixes are the engine's section labels. A-8 says so.
- Q-B4: amend (A-2, S-1).
- Q-B5 (C only in `release/rc-trees/`): refusal upheld. RP §5.1 merges C with a merge commit, so C is always in the
  repository.

**6. CI and the RC runner.**
- Q-C1: C-1 upheld. `release-audit` is D2's, and ruling 2 aligns the WO-R4 row.
- Q-C2: upheld. The push run at the dispatch's commit is the only run that can show junit.
- Q-C3: register the constant (A-5, S-5).
- Q-C4: `--w27-artifacts DIR` upheld. The archive's identity is the pinned digest that the W27 tests check, and
  without the archive, (c) fails visibly (A-6).

**7. Build choices.**
- C-1: upheld.
- C-2: upheld. A new `rc-steps` step, with `rc` and `rc_alpha` left untouched as RP §6.10 requires.
- C-5: upheld. Copying the functions, with `test_the_moved_functions_judge_as_17e_did` pinning that both decide the
  same, is what §3.3's ownership rule requires. That test is permanent.
- C-12: upheld. The runner must verify that the nlp worktree's HEAD is C and that the tree is clean, and record it.
- C-20: upheld (S16 `--manifest-adr`, none by default; S17's rows; S20's two checks "pass"; S13 `unsupported` without
  items; S22's stated `pass`).
- C-21: upheld.

**8. Can the package be `tested`?** Yes, after M-1 to M-3. The local runs are not required for this package: WO-R6's
acceptance is REL.A20. The manifest's limitations must name each port that has not run (steps 6, 11, 12, 14, 15 and
16, and `E01-G6-nlp`) verbatim, until S-6's rehearsal. The browser-smoke failure is a red gate, not a pass. The branch
touches no web file, and the module passes alone, but the full gate must be re-run at the final head and be green,
under lower load if needed. The module is never skipped or deselected, and its failures are never re-baselined. CI
must be green on both architectures at the same head. If browser-smoke fails again under load, report it as red and
escalate it; do not merge on it.

## §17 amendment block (paste into RP; each one gets a register line)

- **A-1 (§11.2, REL.A20; Q-C5).** Move RP.S18 from the same-form list to the changed-form list. REL.A20 also
  requires, over 0.3.0's records, that RP.S18's `not_pass` is a subset of the changed-form assertions, and that
  commands were run. RP.S18's own acceptance is the generator's fixtures: every other check passes, giving `pass`;
  one check fails, giving `fail`; zero commands, giving `fail`.
- **A-2 (§8.3; Q-B4).** Add a condition (d). The scope, evaluated at `Accepted at`, has a fingerprint equal to
  `Fingerprint`. If it does not, the row is `unsupported (not reproduced at <Accepted at>)` and counts as absent.
- **A-3 (§5.1).** The line file and its inherited chain are byte-equal at C and at the candidate. The gate refuses
  with exit 2 otherwise, and a change after C needs a new C.
- **A-4 (§6.2, §6.10).** C is pushed on its own, as the head of a branch ref (`git push origin <C>:refs/heads/rc/<C7>`
  if it would otherwise be pushed beneath later commits). The `release_rc` dispatch at C is the one with the greatest
  run id, at its latest attempt. Step 1's record lists every `ci.yml` run at C with its event, attempt and conclusion.
  The manifest reads exactly those two runs and refuses any other.
- **A-5 (§6.4; Q-C3).** Step 12's archived inputs are `benchmarks/m02/g10-adapter-halves-v3.json` and
  `g11-coverage-v3.json` at `bd446abab1bcc26b286ae4a287d1de131d87ceac`, registered by their SHA-256. A failed read, or
  a hash that differs, stops the RC (§12).
- **A-6 (§6.6; Q-C4).** The pinned W27 archive is supplied to the runner by `--w27-artifacts`. Without it, (c) fails.
- **A-7 (§3.1, D1.5; Q-C6).** The release package id is admitted by the schema ADR of ruling 4. RP's own package
  manifest is filed as `S15`.
- **A-8 (status).** These are notes, not changes. RP.L08 now passes: `scripts/wheel_data_check.py` exists
  (`bd672ff7`). Q-13 is measured, so PTC-R1 stays. F-4 is done in `ci.yml`. The standing-mode reason suffixes `D3`
  and `D4` are the engine's labels (Q-B3).

## What this review did not establish

- I read about half of `release_rc_local.py` (1465 lines), including its order, steps 12 and 16 and the archive
  link. I did not check its record writers against 0.3.0's records line by line; REL.A20's equalities and
  `test_rel_rc_local.py` stand in for that.
- I did not check `wheel_data_check.py` beyond C-5's equivalence test, the nlp worktree mechanics, or `m07_rc_keep.py`.
- I re-ran no gate, CI or RC step. The only run was the mutation probe: `tests/test_rel_standing_acceptances.py`, 40
  passed both unmutated and mutated. The engineers' numbers are quoted, not reproduced.
- This review gives no verdict on any 0.4.0 gate. It is not a numerical review: RP changes no numerics.
