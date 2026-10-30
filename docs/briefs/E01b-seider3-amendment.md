# E01b brief: amend ruling B (§10) against the Seider 3rd edition (design lane, `architect`)

Worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/e01b`, branch `wp/E01b`. Docs-only; commit, do not push.

## 1. The question
§10 of `docs/derivations/E01-design.md` (R-890…R-894) ruled QA1's differences using only the **4th edition**, because the
3rd edition — the one IDAES 2.13.0 `SSLW.py` cites, and therefore the true source of `assessment/cost/sslw-idaes-v1.json`
— was not in hand. Frank has now supplied it. Compare every number the set takes from SSLW (coefficients, size ranges, CE
basis, size variables, weight fits, platform/ladder terms, tray cost, factor tables) with the **3rd edition**, classify
each, and amend §10 (a dated "Amendment 1 to §10") so that the work order C3–C7 is right.

## 2. Sources
- 3rd ed.: Seider, Seader, Lewin, Widagdo, Wiley 2009 (Zotero `seider2009product`). Ch. 22 text, by PDF page (PDF page =
  printed + 38): `/home/frankp/.cache/seider3/ch22_534_595.md`; §22.5 (pumps, motors, compressors, exchangers, vessels,
  towers) pp. 558-580; Table 22.32 (other equipment, CE 500) pp. 591-595; whole book `/home/frankp/.cache/seider3/seider3.md`
  (grep only).
- 4th ed. (already used by §10): `/home/frankp/.cache/seider4/ch16_449_485.md` (PDF = printed + 36), Zotero `seider2017product`.
- QA1's 4th-ed. comparison: `/tmp/claude-1003/-home-frankp-Codes-OpenFlowsheet/4eb41cce-83fd-4812-8ebc-a76f78cb2117/scratchpad/QA1-comparison.md`.
- IDAES source with line numbers: `source_line` in the set file; the unpacked wheel path is in `docs/E01A_DECISIONS.md`
  (grep "unpacked").
- Both books are evaluation/licensed copies: never commit their text or tables; individual numbers with page/table only.

## 3. Already decided (Frank, 2026-10-29)
- The five ranges matched against the 4th ed. count as checked (`QA1.patch`, being applied as C1); add the 3rd-ed. page to
  their citation if it confirms them.
- The set's coefficients follow IDAES's **3rd-edition** values where the 4th ed. refitted them; differences are fixed
  **before 0.3.0**, settled with the 3rd ed.
- Frank was asked whether 4th-ed. numbers may ship in the wheel; instead he supplied the 3rd ed. — so prefer the 3rd ed.
  everywhere, and use a 4th-ed. number only where the 3rd ed. cannot settle it (list each such number: it becomes a
  question for Frank).

## 4. Rule to apply (amend if the evidence says otherwise, with reasons)
- IDAES = 3rd ed. → keep; cite the 3rd-ed. page; a range that matches becomes `verified`-eligible.
- IDAES ≠ 3rd ed. → an IDAES transcription error: correct to the 3rd-ed. value, cite page, record IDAES's value.
- 3rd ed. ≠ 4th ed. but IDAES = 3rd → an edition refit: keep 3rd (note it).
- Revisit each §10 ruling in this light: R-890 (compressor consumed power P_C — confirm in the 3rd ed. and its motor-efficiency
  relation), R-891 (fixed-head α2, U-tube α1, reciprocating pump CE basis, platform terms), R-892 (vessel/tower weight fits
  and `weight_limit` "2"), R-893 (turbine range), R-894 (verification protocol), Q-B1, Q-B10 (trays, factor tables).

## 5. Deliverable
"Amendment 1 to §10" in E01-design (the per-number table: entry / IDAES value / 3rd ed. value + page / 4th ed. value /
class / action), amended register entries (new ids from **R-895**, each superseding the §10 entry it changes, never editing
R-890…R-894 in place except a dated "Amended by" line), a revised §10.6 work order (C3–C7, what moves and by how much, the A48
count after C6), the list of `verified` flags C7 may set, and the remaining questions for Frank (ideally none). One docs-only
commit including this brief. Do not touch code.

State of the branch: `wp/E01b` = C1 (`f72af0c1`), C2 loader (`acc75185`), pins for C1 (`15307c6a`; A48 tripwire 3). The
previous engineer built C3–C6 on the 4th-ed. §10 numbers and parked them on local branch `wip/E01b-held` (`e37dacb1` C3,
`c73a0721` C4, `02477928` C5, `f43f7dab` C6 WIP) — say in the revised work order which of these the next engineer may
cherry-pick and what must be redone. Facts from that build (end of `docs/E01B_DECISIONS.md`): A49's six `index_log` gaps sit at
0.976 of their half-unit bound (ln(567/500) = 0.1258 offset); under M1 the P2 drum floors (~237 lb), so every P2 capital row is
floored; the scratch IDAES 2.13.0 env is at `/home/frankp/.cache/idaes-2.13/venv`; the S12b manifest needs
`scripts/e01_evidence_manifest.py` extended (add it to §10.6.2's file list if you agree).

## 6. Rules
No production code. Do not start subagents. Do not send personal identifiers to any external service. Temp files under
`/home/frankp/.cache/`. Context cap ~150k: grep the book text, read narrow page ranges. Report in at most 15 lines.
