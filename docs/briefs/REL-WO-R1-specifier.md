# Specifier brief: ADR 0055 WO-R1 — the standing release procedure (RP), line files, acceptances table

Status: brief, 2026-11-06. ADR 0055 (`docs/adr/0055-standing-release-procedure.md`, 412 lines, Accepted; Frank's answer
2026-10-31 at 403–412: parts 1–3 now, D2 (the evidence-fingerprint carry, R-916/R-917, WO-R5) later). WO-R1 is the
design-lane deliverable the build work orders WO-R2…R4, R6 implement before 0.4.0's cut (§6, lines 292–318).

## The question

Write the three standing artefacts WO-R1 names (§6 row WO-R1, line 299) so that 0.4.0 is cut by one generic procedure
with a line file, no per-release spec and no policy ADR (D1, lines 58–102).

## Deliverables

1. **RP** — `docs/derivations/release-procedure.md`: D1.1's normative text. Fold `docs/derivations/V03-release-spec.md`
   §2–§7 and §10.1, plus `docs/derivations/V02-alpha-release-spec.md` §8.2's steps as `docs/derivations/M07-spec.md` §8
   reads them, into standing text; write R-902, R-903, R-906, R-907, R-909, R-911, R-913, R-914, R-875, R-460 into the
   step each governs (read each register entry in `docs/decision-register.md` by grep). Include the coverage table
   (REL.A18). **D2 is deferred:** RP describes no fingerprint carry; where ADR 0055 places a D2 step, RP states that
   every claimed gate is judged and names D2 as a later amendment. Same for the `strace` parts of WO-R4/R6 and
   REL.A11–A16, A21.
2. **Line files** — `release/lines/0.3.json` (a transcription of 0.3.0's gate set; inheritance only; REL.A02: `gate_set`
   equal field by field to `scripts/v0_3_gate.py` `GATE_SETS[0]`, `policy_adr` ↔ `acceptances` = ADR 0053's path) and
   `release/lines/0.4.json` (`inherits: "0.3"`, `changed` exact; `gates[*]` with T(g), R(g), criteria, documents seeded
   from `docs/reviews/V03-verdicts.md`'s Basis column; `rc_items`; format `release-line-v1` per D1.2). Where 0.4's claim
   set is not known yet (it depends on what 0.4 ships: MSG, ST, X04, X05, …), seed it from 0.3.0's and list what the
   0.4.0 cut must revisit; do not invent claims.
3. **Acceptances** — `release/acceptances.md`: D3.6's six rows (D3 at 157–212), answer cells verbatim from ADR 0053,
   `Accepted at` `a3e508e3…`, fingerprints as D3 states (REL.A19); plus N-7's row (Frank's coolprop and lca licence
   acceptances of 2026-10-30, verbatim from `V03-release-spec.md` §11, N-11).
4. A machine-readable schema for `release-line-v1` if D1.2 needs one for WO-R2's loader (`schemas/` draft or
   `release/lines/release-line-v1.schema.json`; say which), and the list of REL.A* assertions each artefact satisfies.

## Read narrowly

ADR 0055 §1–§3 (16–262), §6 (292–318), §9 open items (343–368), §10 assertions (369–402); the V03 spec and verdicts by
section with grep/sed ranges; `scripts/v0_3_gate.py` for `GATE_SETS` only. Do not read whole large files.

## Constraints

No claim, criterion or acceptance changes meaning in transcription; anything that would is listed as a question with a
default, not decided. Answer cells are verbatim. Self-generated outputs are not evidence. Lines ≤ 120 columns.

## Rules

Report ≤ 20 lines: files written, assertions each satisfies, questions with defaults, anything that needs Frank. Do not
commit; no git state changes (other agents work concurrently); no production code (JSON/Markdown data files are fine);
no subagents; nothing under `.claude/worktrees/`; never read, stat or touch `~/.config/procsim/`; do not read
`/home/frankp/s10-papers/`, `~/.cache/seider3/`, `~/.cache/seider4/`; no web fetches.
