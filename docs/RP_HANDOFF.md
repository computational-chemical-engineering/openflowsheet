# RP handoff (ADR 0055 WO-R4 / WO-R6, build lane)

Branch `wp/RP`, worktree `.claude/worktrees/rp`. Brief `docs/briefs/REL-build-WO-R4-R6.md`; choices C-1…C-8 and
questions Q-C1, Q-C2 in `docs/RP_DECISIONS.md`. Stopped at the ~150k context cap.

## Done (commits `b69dc0f1`, `bd672ff7`)

- `scripts/wheel_data_check.py` (WHEEL-DATA) and `e01_evidence_manifest.py --a48-release-check` (E01-A48). RP.L01–L10
  pass on `release/lines/0.4.json` (`test_rel_release_gate.py`, L08 control kept). Real run at `b69dc0f1`:
  `wheel data check: PASS`, 11/11 checks.
- `ci.yml` WO-R4 (input `release_rc`, `check`'s `if`, `junit-<arch>`, RC job list incl. `rc-ensemble`, `ptc-r1`;
  no `release-audit`, no strace). REL.A17 tests in `tests/test_rel_ci_release_rc.py` (17 pass).
- `scripts/release_rc.py`: `surface` (step 8), `step1` (§6.2 record), `items` (§6.7 step-17 wrapper).
- Dispatch (the one allowed): run 42156856877 at `bd672ff7`; push run at the same head 42156850745.

## Not done (next agent, in order)

1. Read the dispatch's outcome: `gh run view 42156856877 --json jobs` — `check`/`identity`/`default-install`
   skipped, the 8 RC jobs run; `ptc-r1` wall time on both legs vs 360 min (Q-13/N-2). Push run 42156850745: `check`
   green on both legs, artifacts `junit-x86_64`, `junit-aarch64` present (C-8). Do NOT dispatch again.
2. `release_rc.py` steps 2–7, 9–16 locally (RP §6.1 "How the steps run"): port of 0.3.0's runner
   `evidence/S13/a3e508e3…/tools/run_local.sh`, the step 11–16 record writers of `tools/m07_rc_external.py.txt`,
   `run_step14.sh` (with §6.5's selection: `a60.w24.nlp_selection`), step 12's keep-and-audit (§6.4: promote
   `g11keep.py.txt`/`g11collect.py.txt` into a tracked script; record `r375.audit` only), step 16 per §6.6, and
   `rc/records.json`. Keep 0.3.0's record paths and check ids (§6.1).
3. `scripts/release_evidence_manifest.py`: RP.S01–S22 (§11.1) + one check per `rc_items` entry; REL.A20 (§11.2):
   over 0.3.0's records the 13 same-form assertions equal S13's `pass`; the 9 changed-form ones decided and recorded
   with the exclusion reason. Model: `scripts/s13_evidence_manifest.py` (read-only). Fixtures for S10, S13, S17,
   S20, S21 (a passing record and one control per changed rule).
4. Full gate once, evidence manifest `evidence/RP/<commit>/manifest.json` (F0 format; status `tested` only if
   supported; never `reviewed`), push, report CI run id. Do not merge.

## Gate at `bd672ff7`
`GATE PASS bd672ff7: 14995 passed, 3206 skipped, 197 deselected` (8527 s). Dispatch and push run: see `docs/RP_DECISIONS.md` "Measured (WO-R4/R6)"; step 1 of "Not done" is therefore done.
