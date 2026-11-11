# Specifier brief: RP amendment A-12 — the V17 chain for n links (0.4.0 verdict findings F-3, F-4, F-5)

Status: brief, 2026-11-10. Design lane, `specifier`. **Do not spawn sub-agents yourself.** One docs-only commit on
`wp/REL040` in `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/rel040`. No D2.4 path (`src/ schemas/ benchmarks/
requirements*.lock pyproject.toml MANIFEST.in README.md LICENSE NOTICE`), no script, no test. Do not push.

## The question

How should RP §4.4 and RP.S14 read, so that the 0.4.0 release manifest (§9.2 step 4) judges step 8 on text that fits an
eight-link chain? And what are the rulings for 0.4.0 on F-4 and F-5?

## Facts (measured at C = `84c665477b512548f38a6335f51648732b1fe5bb`)

- RP §4.4 (`docs/derivations/release-procedure.md` l.308–316) and RP.S14 (l.938–939) name 0.3.0's chain literally:
  - three links, c_1 R-192, c_2 R-234 and c_3 R-295;
  - D_3 = `455d01eb…e125`;
  - rows `[(1,c_3),(2,c_3),(2,c_2),(2,c_1),(3,None)]`.
- `LINKS` in `scripts/m07a_rc.py` at C has eight links: R-192, R-234, R-295, R-934, R-950, R-960, R-1000 and R-1010.
  Each was added by its package (MSG, OPT/X02, RRC, X04) with a register entry, a strip function and a registered
  digest.
- Step 8 passed at C locally and on both CI architectures:
  - the served digest `6be1c002…ba57` equals D_8, the R-1010 link's;
  - the rows are `(1,c_8)`, `(2,c_8)` … `(2,c_1)`, `(3,None)`;
  - `test_m07a_a37_the_chain_holds_on_the_served_list` checks the general form.
- The verdict document `docs/reviews/REL040-verdicts.md` (commit 3e6f0d80) reads RP.S14 in its general form. Its
  findings F-3, F-4 and F-5 are at l.360–375. Read them.
- §4.4's last sentence ("A new link then needs a register entry, a strip function, a registered digest, and Frank's
  `V17 carry` row replaced, or else a new V17 campaign") is already what happened at 0.4.0. Frank is being asked for
  the replacement row now.
- F-4: envelope row L-WS-2 in `benchmarks/t08/support_envelope.yaml` is out of date, because ADR 0070 (X02) added an
  explicit warm-start source. That file is D2.4 and frozen at C.
- F-5: `scripts/v0_2_gate.py:129` `LIMITATION = re.compile(r"\bL(?:\d{2}|-[A-Z]+-\d+)\b")` rejects `L-X04-1..3`,
  `L-S11-1..3` and `L-E01-1`. Changing a gate tool after C would change what step 18 runs at C.

## Do

1. Write amendment **A-12** as `### 17.5 Amendment A-12 (REL040 verdict F-3, 2026-11-10)`, in the style of §17.2–17.4.
   - Restate §4.4 and RP.S14 for a chain of n links: rows from `LINKS` in order, served digest = the last link's
     registered digest.
   - Give 0.3.0's (n = 3) and 0.4.0's (n = 8) as instances.
   - Edit §4.4 and RP.S14 in place only as A-12 says, citing it.
   - Nothing else in RP changes.
2. Rule on F-4 and F-5 for 0.4.0, inside A-12 or as a short ruling note in the same commit.
   - Orchestrator default (DECISION): **no change to the envelope or the gate tool before the tag.** Both go to the
     first post-tag change (0.5.0.dev0).
   - For 0.4.0, `CHANGELOG.md`'s `## v0.4.0` carries:
     - L-X04-1..3 by text, under V11;
     - a sentence saying that 0.4.0 adds an explicit warm-start source (ADR 0070), which L-WS-2's text predates.
   - Overrule this default only with a reason that is in the evidence.
3. Check whether any test or line file pins RP's bytes or §4.4's text, e.g. `grep -rn "release-procedure" tests scripts
   release`. If one does, stop and report rather than edit.
4. Add the register line(s) in `docs/decision-register.md`, as A-9–A-11 did, and commit with the message `REL040: RP
   amendment A-12 — the V17 chain for n links (verdict F-3); F-4/F-5 rulings`.

Trailers: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`. Cap ~150k context. Never read or touch `~/.config/procsim/`,
`/home/frankp/s10-papers/`, `~/.cache/seider3/` or `~/.cache/seider4/`.

## Report (at most 15 lines)

The commit sha, A-12's restated RP.S14 sentence, the F-4 and F-5 rulings, and any pin found.
