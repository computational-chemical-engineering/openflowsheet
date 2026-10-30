# E01b brief: rule the Seider-check differences in E01's cost set (design lane, `architect`)

Branch `wp/E01b` from `wp/E01` head `84d71df8` (worktree `.claude/worktrees/e01b`; E01 is gated and in CI and merges into
`main` unchanged). Docs-only deliverable; commit on `wp/E01b`, do not push.

## 1. The question
Rule each difference QA1 found between E01's cost set and Seider et al., precisely enough that **one** build-lane engineer can
make the corrections, set `verified: true` where it is now earned, and update the tests, in one batch before 0.3.0.

## 2. Why the architect
Each item changes registered numbers in `assessment/cost/sslw-idaes-v1.json` (a transcription of IDAES 2.13.0 `SSLW.py`, BSD,
with `source_line` per number) and E01's independent expectations (`benchmarks/e01/cost_hand/`). You wrote E01's design
(`docs/derivations/E01-design.md`, ADR 0052; §9.2 is the set grammar, the seven deliberate departures and §9.2.4 ranges;
A48 at ~1688/~1885; QA1 row ~1903).

## 3. The facts (measured; read these first)
- **The comparison:** `/tmp/claude-1003/-home-frankp-Codes-OpenFlowsheet/4eb41cce-83fd-4812-8ebc-a76f78cb2117/scratchpad/QA1-comparison.md`
  (124 lines; checked against the **4th edition**, Seider, Lewin, Seader, Widagdo, Gani, Ng, Wiley 2017, Zotero
  `seider2017product`, ch. 16; Table 16.32 pp. 481-485, CE 567). Book text for checking (a Wiley evaluation copy: never
  commit it or long tables; page + table citations and the individual numbers needed are fine):
  `/home/frankp/.cache/seider4/ch16_449_485.md` (PDF page = printed + 36).
- Summary: 5 primary ranges match exactly (exchanger 150–12 000 ft² p. 462; centrifugal pump S 400–100 000 p. 452; gear
  pump 10–900 gpm p. 454; reciprocating pump 1–200 BHp p. 454; motor 1–700 Hp p. 453). The 4th ed. **refitted** the
  centrifugal pump, gear pump and motor correlations (reciprocating pump: same, intercept shifted by ln(567/500)).
  Compressors 200–30 000 / 100–20 000 / 10–750 hp p. 460 match in number, but the book's size variable is **consumed power
  P_C (motor included)**; IDAES feeds **brake power**; p. 460 also says the compressor base cost includes the motor (QA6).
  Turbine: IDAES's 530·P^0.81 is Table 16.32's gas expander, 600·P^0.81 at CE 567, 20–5 000 Hp p. 483 (no range in the set).
  Vessel weights (`SSLW.py:534`): the set's vertical `weight_limit` "1" carries the **horizontal** range; the book's
  vertical range is 4 200–1 000 000 lb. `weight_limit` "2" (intercept 7.2756) is not in the 4th ed.; the 4th-ed. tower fit
  is (10.5449, −0.4672, 0.05482), 9 000–2.5 M lb. U-tube exchanger α1 0.040 below the book (book 4.1 % higher); fixed-head
  α2 0.8228 (IDAES) vs 0.9228 (book); reciprocating pump labelled CE 394 by IDAES but the book's intercept implies CE 500
  (inference); horizontal-platform exponent and tower-platform coefficient differ.
- **Frank-approved patch** for the five matches: `.../scratchpad/QA1.patch` (59 lines; `verified: true` + 4th-ed. page in
  `citation`; the grammar allows only `kind`, `citation`, `verified`). Applied alone it fails 7 tests:
  `tests/test_e01_a48_tripwire.py` (pinned count 8 → 3), `tests/test_e01_a_cost.py:132` (asserts all primary unverified),
  `tests/test_t08_w2_inventory.py:399` + `docs/e01-data-licences.json:23` + `docs/E01A_DECISIONS.md:170` (file sha256),
  `tests/test_e01_a_report.py` (three golden reports; regenerate with its `_write()`).
- The 3rd edition (which IDAES cites, ch. 22) is **requested, not in hand** (Zotero `seider2009product`).

## 4. Already decided (Frank, 2026-10-29)
- The five ranges count as checked, cited to the 4th-ed. page; their coefficients stay IDAES's 3rd-ed. ones, **stated** in
  the set/report. Apply QA1.patch as part of the batch.
- **The differences are fixed before 0.3.0** (the release waits): correct the compressor size variable to the book's
  definition; settle the coefficients with the 3rd ed. when it arrives, **or adopt the 4th edition's**.
- Frank's standing directives: as few limitations as possible; batch, then test once; independent expectations only (B4's
  hand transcription does not import `openflowsheet`); post-solve functionals only; nothing outside E01's files moves.

## 5. Open — decide each
1. Compressors: the exact correction (P_C from brake power and which motor efficiency — the book's, a set parameter, the
   motor entry's?), and how it interacts with the separate motor entry (no double counting, QA6).
2. Coefficients that differ: the rule now, without the 3rd ed. — e.g. a second set file transcribed from the 4th ed. (CE
   567) for the affected entries and made the default, keeping `sslw-idaes-v1` as the IDAES transcription; or keep IDAES
   values labelled and re-check on arrival; or a typed refusal. State which entries, and what happens when the 3rd ed.
   arrives. Treat fixed-head α2 0.8228/0.9228 specifically (copying error or edition?) on the evidence available.
3. Vertical-vessel range and `weight_limit` "2"; the turbine range (Frank: few limitations).
4. Register entries (next free id after the highest on `wp/E01` and `main`), the dated amendment section in E01-design,
   and the work order for one engineer: files, tests (which fixtures regenerate, which expectations move and by how
   much), the A48 count after the batch, and the acceptance commands.

## 6. Deliverable and rules
Dated amendment in `docs/derivations/E01-design.md`; register entries; one docs-only commit on `wp/E01b` including this
brief. No production code. Do not start subagents. Do not send personal identifiers to any external service. Temp files
under `/home/frankp/.cache/`. Context cap ~150k. Report in at most 15 lines; list any new literature reference.
