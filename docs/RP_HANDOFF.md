# RP handoff (ADR 0055 WO-R4 / WO-R6, build lane)

Branch `wp/RP`, worktree `.claude/worktrees/rp`. Brief `docs/briefs/REL-build-WO-R4-R6.md`; choices C-1…C-17 and
questions Q-C1…Q-C4 in `docs/RP_DECISIONS.md` (with the measured numbers).

## Done

- WO-R4 (`ci.yml`, REL.A17) and WO-R6 items 1–2: `b69dc0f1`, `bd672ff7` (step 1, step 8, step 17's wrapper,
  WHEEL-DATA, E01-A48); WO-R6b `6beaf53d`, `88045740`, `df30b36e`: `release_rc.py local` (steps 2, 6–17 at C, the
  line's `rc_steps`), `record` (steps 11–16 and step 12's `r375.audit`), `ci` (the dispatch's artifacts and logs),
  `records` (`rc/records.json`); `scripts/release_rc_local.py` (the port of 0.3.0's runner and record writers);
  `scripts/m07_rc_keep.py` (G11/G12 keep wrappers and G11's collector, promoted, R-909 A3-3).
- Tests `tests/test_rel_rc_local.py` (20). Real run: steps 2, 7, 8, 9, 10, 13 pass at C (see the decisions file).

## Not done (next agent, in order)

1. `scripts/release_evidence_manifest.py`: RP.S01–S22 (§11.1) + one check per `rc_items` entry; REL.A20 (§11.2):
   over 0.3.0's records the 13 same-form assertions equal S13's `pass`; the 9 changed-form ones decided and recorded
   with the exclusion reason. Model: `scripts/s13_evidence_manifest.py` (read-only). Fixtures for S10, S13, S17,
   S20, S21 (a passing record and one control per changed rule). The records the runner writes are 0.3.0's paths
   and ids, so S13's `evidence/S13/a3e508e3…/rc/` reads directly.
2. Full gate once (`scripts/gate.sh`, background), evidence manifest `evidence/RP/<commit>/manifest.json` (F0
   format; status `tested` only if supported; never `reviewed`); its limitations: steps 6, 11, 12, 14–16 and the
   nlp item not run locally at this head (environments), no dispatch at this head. Push, report the CI run id.
   Do not merge.
3. The one `reviewer` pass over WO-R2…R6 takes Q-B1…B5 and Q-C1…C4.

## How to run the RC locally at C

`python scripts/release_rc.py local --line 0.4 --commit C --rc evidence/<pkg>/C/artifacts/rc --work W
--nlp-prefix P --nlp-cache D --journey J --w27-artifacts A [--ci-run ID]`, then `release_rc.py step1`, `ci`, and
`records --cited` once the RC record's citations are known.
