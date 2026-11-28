# LINE06-L1: the 0.6 line file, design-lane fields (specifier, RP §13 (1), once)

Do not spawn sub-agents yourself. Budget about 150k context. Rules: `docs/LINE06_RULES.md` (read it first).
Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/rel060` (branch `wp/REL060`, from main 259bda86 plus
this brief). Edit `release/lines/0.6.json` (the LINE06-L0 DRAFT) and write the design note
`docs/briefs/REL060-line-0.6.md` (why each `changed` entry, what is carried, what is not claimed and why). Commit both
with named paths only; do not push. No production code, no gate script (RP §3.7). Report about 30 lines.

## Question

Finalise the 0.6 line file (`format: release-line-v1`, `line: "0.6"`, `role: "gate"`, `inherits: "0.5"`) per RP §3
(`docs/derivations/release-procedure.md` §3.1 to §3.7, §6.1, §6.7, §10, §13, and the §17 amendments that touch the
line file). Decide the design-lane fields: the claim set (`claimed`, `not_claimed`, `clause`), any change to
`gates[*]` criteria (a criterion change is an RP amendment: say so and stop at the text), `rc_items` (carried,
dropped, new), the phrases (`changelog_what_it_is_not`), `rc_steps`. Check and, where needed, correct the build-lane
fields the L0 draft proposed (`covers`, `envelope_id`, `packages`, `required_adrs`, `evidence_package` REL060,
`verdict_document`, `rc_record`), marked as proposals. List `changed` exactly (RP §3.2), measured against 0.5.json.

The three questions LINE06-L0 left to you (`docs/briefs/LINE06-line-0.6.md` §2, read it whole, about 50 lines):
1. rc item for F2's and F8's new schemas in the wheel (`WHEEL-F2-F8` or `WHEEL-F1-F3` widened), owner
   `scripts/wheel_data_check.py`.
2. The line clause "a v2 revision with store-pinned records solves on the legacy route on all three OSes" (card
   `ofs-line06-adr-clause`, R-1070): an `rc_items` entry read from the candidate's push run on the Linux, Windows and
   macOS legs (`r0_sha256` and `state_sha256` equal to the v1 run's, ADR 0062 D8, E-F2-3), or a gate. A new gate needs
   registered criteria, which 0.5 avoided (REL050-L1 D-3). Name exactly which CI job and test produce the evidence;
   if no CI leg runs that case today, say what the build lane must add (that is the L3 step in the state file).
3. An X06 release check (MCP over HTTP answers `list_capabilities` from the installed wheel), only if ADR 0078's
   exits make one a release check.
Plus the phrases (RP.S10, each once in the notes): whether a v2 solve reads the record store, decided from F2's
built behaviour, not from the ADR text alone.

## Facts

- Scope (R-1070, ADR 0057 Amendment 3, the user 2026-11-26): F2 (ADR 0062), F8 WO1 to WO3 and WO5 (ADR 0067), X06
  (ADR 0078). F4 to F6, F8 WO4 and WO6 are out (0.7 / later). Line acceptance (card `ofs-line06-adr-clause`): ADR
  0062, 0067 and 0078 Accepted; 0063 to 0065 go to 0.7, 0066 to 0.8.
- State: F2 merged into main `f1fdda2b` (ADR 0062 and ADR 0019 Amendment 9 Accepted). X06 merged `9532829b` (ADR 0078
  and ADR 0019 Amendment 18 Accepted). F8 (ADR 0067 and ADR 0019 Amendment 12 Accepted) is reviewed and fixed on
  `wp/F8` `d3846b8d`, full local gate PASS (22056 passed), CI running, not yet merged: read its files with
  `git show d3846b8d:<path>`. If CI forces a change to what F8 ships (schemas, CLI), the orchestrator reruns the
  affected part of your note; say which of your fields depend on F8's tree.
- F2's new schemas: `process-revision-v2`, `specification-v2`, `connection-definition`, payload schemas. F8's:
  `run-manifest`, `replay-report`, `records-index`, `run-evidence`. Verify each name against the trees.
- Exits: ADR 0062 "Exit tests" (E-F2-1 to E-F2-10; E-F2-3 is the lowering case); ADR 0067 "Exit tests" (E-F8-1 to
  E-F8-6, E-F8-8, E-F8-10 in scope); ADR 0078 "Exit tests" (E-X06-1 to E-X06-19, line 298 on). Read the ADRs by
  section (`grep -n '^#'`), not whole.
- Precedent: `release/lines/0.5.json` and its note `docs/briefs/REL050-line-0.5.md` (REL050-L1: claim set unchanged,
  new rc_item WHEEL-F1-F3, Q-F1 and Q-F2 for message 1, defaults stood). 0.5.1 was a patch release on 0.5.json
  (`docs/REL051_STATE.md`, `docs/reviews/REL051-verdicts.md`); say whether anything learnt there (RC step 14, m05
  REAL replay after the TRS2 -> TR09 move) must appear in the 0.6 file.
- Loader: `scripts/release_gate.py` `load_line`, `line_problems`, `line_release`. L0 measured: RP.L01 to RP.L04,
  RP.L06, RP.L07, RP.L09 to RP.L11 clean, `line_release` = 0.6.0; RP.L05 and RP.L08 are checked only at `C`.
- `frank_items`: 0.5's five carry unless the lapse report at C says otherwise (RP §8.4). Write "the user" in any new
  text, not first names.

## Output and acceptance

1. `release/lines/0.6.json` without its DRAFT marker if you finalise it (keep the marker and say why if you cannot),
   and the note. 2. The loader's check on your file, run in the worktree:
   `PYTHONPATH=src /home/eajfpeters/Code/OpenFlowsheet/.venv/bin/python -c 'import sys; sys.path.insert(0,"scripts"); import release_gate as g; ...'`
   or whatever loader-only entry exists (find it; quote the command and its output line): zero problems, `line_release`
   0.6.0. 3. Open questions with their defaults (RP §15 style) and anything that needs the user (a claim-set change
   is message 1). The orchestrator judges on item 2 and on every L0 question being answered with a reason.
