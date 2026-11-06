# Reviewer brief: RP — ADR 0055 parts 1–3 (WO-R1…R4, R6), the single review pass

Status: brief, 2026-11-06. ADR 0055 (`docs/adr/0055-standing-release-procedure.md`; Frank: parts 1–3 now, D2 — the
fingerprint carry, `release-audit`, `strace` — later). Normative design text: RP `docs/derivations/release-procedure.md`
(WO-R1, `6714958d`, specifier-written, not yet reviewed), line files `release/lines/{0.3,0.4}.json`, schema
`release/lines/release-line-v1.schema.json`, `release/acceptances.md`. Build briefs `docs/briefs/REL-build-WO-R2-R3.md`,
`REL-build-WO-R4-R6.md`. Branch `wp/RP`, worktree `.claude/worktrees/rp`, head `05e3e069` (13 commits over main).
Build log `docs/RP_DECISIONS.md` (B-1…B-15, C-1…C-22, questions), handoff `docs/RP_HANDOFF.md` (both in the worktree).
Manifest `evidence/S15/3e7ccf00…/manifest.json` (status `implemented`).

## The question

Is RP sound as the standing release procedure, does `wp/RP` implement it, and what are the rulings on the open items
below — including the RP amendments needed — so the package can become `tested` and merge before 0.4.0's cut?

## What was built and measured (engineers' numbers; re-run what you doubt)

- `scripts/release_gate.py` (generic gate over line files, imports `v0_2_gate.py`'s engine; standing acceptances §8):
  REL.A01–A10 PASS; A03 byte-identical stdout vs `scripts/v0_3_gate.py --rc a3e508e3` on the 17 committed fixtures
  only (the checkout's version is a dev version). RP.L01–L10 PASS on `release/lines/0.4.json` (L08 control refused).
- `ci.yml` (WO-R4): REL.A17 17/17. One `release_rc` dispatch 42156856877 at `bd672ff7`: `check`/`identity`/
  `default-install` skipped, all 8 RC jobs green (`ptc-r1` ~2 min per leg vs 360 min). junit artifacts came from push
  run 42156850745 (the dispatch skips `check`, Q-C2). `release-audit` not added (C-1, Q-C1).
- `scripts/release_rc.py` + `release_rc_local.py` (port of 0.3.0's runner): steps 2, 7, 8, 9, 10, 13 ran for real at C
  (13 after a basetemp fix: 696 tests, 0 fail); steps 6, 11, 12, 14–16 and the nlp item not run locally (multi-hour envs
  / archives in other worktrees). `scripts/wheel_data_check.py` PASS 11/11; `scripts/m07_rc_keep.py` promoted.
- `scripts/release_evidence_manifest.py`: over 0.3.0's records 22 checks: 16 pass, 5 fail, 1 unsupported. Same form:
  12/13 equal S13's `pass`; **RP.S18 fails** (its rule "every other check passes" sees the changed-form fails S10, S15,
  S17, S21 and S13 unsupported) → **REL.A20 FAIL as written** (Q-C5).
- Full gate at `bd672ff7`: PASS 14995. At `3e7ccf00`: 29 failed + 1 error, all `tests/test_m06_browser_smoke.py`
  (headless browser BrokenPipe under host load ~80); alone 31 passed in 43.7 s; the branch touches no web file.
- F0 `corpus_identity.py --check` PASS. Manifest filed as S15 because the frozen schema's package-id pattern refuses
  `RP` (C-22, after R-878's E01→S12, V03→S13, DOC→S14) — and also refuses `REL040` (Q-C6).

## Rule on each (default in brackets where one exists)

1. **RP's own design** — the specifier's findings F-1…F-3 (RP §16) and open questions Q-1…Q-15 (RP §15, each with a
   default); the `gates[*]` table of the 0.3/0.4 line files against `docs/reviews/V03-verdicts.md`'s Basis column.
2. **ADR 0055's acceptance condition** restated for the D2 deferral (F-3 / Q-12): write the restatement.
3. **Q-C5** REL.A20: move RP.S18 to §11.2's changed-form list, or compare S18 over same-form checks only? (RP amendment)
4. **Q-C6 / C-22** package ids: S15 for RP's manifest; and `REL040` for 0.4.0's release manifest — schema ADR or an
   S-id rule in RP?
5. **Q-B1…Q-B5** (standing acceptances: new vs standing row, decision-item bounds, reason strings, fingerprint at
   `Accepted at`, `C` only in `release/rc-trees/`).
6. **Q-C1** `release-audit` (ADR 0055 WO-R4 row vs RP §6.10); **Q-C2** junit evidence from the push run; **Q-C3** step
   12's archived `bd446ab` inputs as a constant not registered; **Q-C4** step 16's W27 archive as `--w27-artifacts`.
7. The build choices that depart from the brief's literal text: C-1, C-2 (step 8 as a new `rc-steps` step), C-5
   (`wheel_data_check.py` copies 17e's functions), C-12 (nlp items from the nlp worktree), C-20, C-21.
8. Whether the local-run limitations (steps 6, 11, 12, 14–16, nlp) plus the browser-smoke load failure allow `tested`
   after a gate re-run, or what more evidence is needed.

## Least sure of

RP itself (no review yet; 1053 lines — read §3, §6, §8, §11, §15, §16 closely, skim the rest); A03 on fixtures only;
whether `release_evidence_manifest.py` decides anything independently of the records it reads; the step-12/16 ports
that never ran.

## Deliverable

`docs/reviews/RP-review.md`: verdict, must-fix (M*), should-fix (S*), one ruling per item above (`<id>: ruling —
reason`), the RP amendment text where a ruling needs one (as a numbered §17 amendment block the build lane can paste),
and what the review did not establish. Commit it on **main** (docs-only, named path, message `docs: RP review`, with the
session's Co-Authored-By / Claude-Session lines from your prompt). Do not edit `wp/RP`. Never set `reviewed`.
Report ≤ 30 lines.

## Out of scope

MSG, ST; D2 (fingerprint carry, `release-audit`, `strace`); wall-time budgets; style.
