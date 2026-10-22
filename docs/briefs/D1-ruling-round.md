# D1 — batched design-lane ruling round after S01/S02/C4/C7 (design lane, `specifier`)

Branch `wp/D1` from `wp/C7` `9b09ed2` (contains S01, S02, C4, C7). Per CLAUDE.md's agent budget, open design
questions are batched into one round. Register numbering: **R-560…R-569**; ADR **0045** if one is needed.

## The questions (rule each with reasons; a frozen interface or schema changes only by ADR)
1. **T05b §6.6 vs later packages' v2 policies.** `tests/test_t05b_literal.py` B06 admits `phase_contract=` keywords only
   in named sources (`T05B_V2_SOURCE`, and now `S01_V2_SOURCE` for `cascade_solve.py`; check whether S02 added one).
   T05b spec §6.6 says every registered policy stays v1 except `T05b-v2`. Amend §6.6 to a registered-list rule, or
   rule otherwise. Anchors: `docs/S01_DECISIONS.md` QUESTION (WO-5, B06); S01 spec §4/§7 (R-505); S02 spec §7.
2. **S01/S02 scope rows.** S01's scope limitations are filed E → `U04` because the cascade/column are library-only
   (not in `MODEL_BUILDERS`); `docs/S01_DECISIONS.md` QUESTION (WO-5, A21). Rule: L-rows now, or when they bind.
3. **C4-Q1** (`docs/C4_DECISIONS.md:33-35`): M07a.A61 (V11–V20 pending) classified S → the alpha verdicts (V14 FAIL
   on (b)); alternative E → L01.
4. **C7-Q1** (`docs/C7_DECISIONS.md:21-`): is v0.3's working envelope a new id (`v0.3-envelope-dev`, release
   `0.3.0.dev0`), given R-475 freezes M07a.A10's edit? C7 set `v0.2-envelope-dev` / `0.2.0.dev0` (R-460's registered form).
5. **C7-Q2** (`docs/C7_DECISIONS.md:40-`): at `0.3.0.dev0`, R-476's predicate makes the four ledger tests in
   `tests/test_m07_ledger.py` skip; scope the ledger to the tag commit now (rulings O1)?
6. **Evidence-manifest ids.** `schemas/evidence-manifest.schema.json:23` `work_package` `^[PKTMSR][0-9]{2}[a-z]?$`
   admits no `C…` or `L…` id, so cloud housekeeping packages (C1–C7) and L01 carry no manifest
   (`docs/C2_DECISIONS.md`, `docs/L01_DECISIONS.md`); L01 cannot merge without one. Options: an ADR widening the
   pattern (frozen schema; plan §2.2), renaming such packages under existing letters, or ruling that C-packages need
   none and L01 is renumbered. Choose.

## Exit test
`docs/reviews/D1-rulings.md` with one ruling per question (decision, reason, what changes, who does it), register
entries, an ADR 0045 draft if needed, and build-lane work orders for any code/test change (do not change production
code; small doc amendments to specs are yours). Commit (`D1:` prefix, trailers). Report ≤ 150 words.

## Out of scope
Rights (L01-Q4), W27 amendment ownership (L01-Q1), the C2 split's Q-5 — those are Frank's.

## Agent rules
Context cap ~120k; at the cap commit, write a ≤ 30-line handoff `docs/briefs/D1-handoff.md`, stop.
