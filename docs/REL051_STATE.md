# REL051 state: the 0.5.1 patch release (X32's grant fix + README status rewrite)

Rewritten in place; history in `docs/REL051_DECISIONS.md` (append-only). Branch `wp/REL051`, worktree
`.claude/worktrees/rel051`, from main = v0.5.0 = 63b00504. Rules: `docs/REL050_RULES.md` (they apply, with the two
changes under "Authority" below). Procedure: the `rel050` skill (on wp/REL050) and RP; 0.5.0's log
`docs/REL050_DECISIONS.md` on wp/REL050 (`git show origin/wp/REL050:docs/REL050_DECISIONS.md | grep ...`) holds every
command used at 0.5.0.

## Authority (the user, in the REL050 chat, 2026-11-23)

- "I would prefer to do the 5.1.0 release now (also with the readme) ... without much agent work" and, asked, "Yes,
  go; chat answers replace the cards": for 0.5.1, **the user's answers in this session's chat replace the Decision Desk
  cards** for merges into main and the release dispatch. The user approves the PyPI upload in GitHub.
- This overrides, for 0.5.1 only, hub's relayed pause (no new agents until Thu 2026-11-26 13:00): **at most one
  agent**, a narrow `verdict` pass. Everything else is done by this session itself, with the 0.5.0 drivers in
  `~/.cache/rel050-cut/bin/` (copy them to `~/.cache/rel051-cut/bin/` and edit C/K3/J/paths; gh is now the system
  gh 2.105.0, which has `--json attempt`; the private gh folder is deleted).
- Scope: X32 (origin/wp/X32 2725fa7d + manifest 7cf27880: grant prints the token alone on stdout) and the README
  Status rewrite (the table, "What 0.x claims", the quickstart tag). Nothing else (only X32 is a ready unmerged fix).

## Position

- Step 1 done (68982da7, X32 merged). Step 2 done (87e28c64, README + test). Step 3 done (42bafc14): RP amendment
  A-14 (RP.L11 takes `<line>.Z`'s id), line file with evidence_package **REL051** (R-1069, the user chose "Option 1"
  in chat; "Keep REL050" was withdrawn because RP.S22 fails on `evidence/REL050/`). Pushed 42bafc14; CI watched by
  `~/.cache/rel051-cut/bin/ci_wait.sh <sha>` (polls every 300 s).
- K3' done: 2b74e60d (REL050 harvested), **K3' = 8f7ce045** (0.5.1, envelope v0.5-envelope-2). K3' tests 1982
  passed; F0 PASS; P1, P3, P4, P6 hold. Next: push, CI at 8f7ce045, then step 5 (J': re-takes from a clean detached
  worktree at K3', drivers in `~/.cache/rel051-cut/bin/` adapted from rel050's; `<briefs>/REL050-J.md`).
- CHANGELOG `## v0.5.1` (moving Unreleased's two Fixed bullets under it) is written at step 9 (notes), as 0.5.0 did.

## Plan (each step logged in REL051_DECISIONS with real numbers)

1. **Merge origin/wp/X32** into wp/REL051 (merge commit). Conflicts at test-merge: CHANGELOG.md,
   benchmarks/t08/support_envelope.yaml, docs/decision-register.md, docs/support-matrix.md, tests/test_m07a_harvest.py
   (harvest bookkeeping; cli.py auto-merges). Resolve as the int/0.5 merges did (2daf92b9 "harvest union,
   HARVEST_SIZE"): union the rows, `scripts/t08_support_matrix.py --emit` then `--check` 0 problems, HARVEST_SIZE
   measured. Tests: `tests/test_tok_grant_token_file.py tests/test_t07_authz.py tests/test_t07_w5b_cli.py
   tests/test_m07a_harvest.py tests/test_t08*.py tests/test_rel_*.py`.
2. **README Status** rewritten for 0.5.1 from CHANGELOG `## v0.5.0` (+ X32): the table's "Released in" row, the
   claims line, the quickstart tag; `docs/RELEASING.md` "Per release" step 1 says the whole Status section; widen
   `tests/test_readme_current.py` so the table row and quickstart tag must name the current release. CHANGELOG
   `## v0.5.1` (X32 + README).
3. **Line file** `release/lines/0.5.json`: DECISION (default): same line file; `gate_set.covers` widened to admit
   0.5.1; `evidence_package` REL051, `verdict_document` `docs/reviews/REL051-verdicts.md`, `rc_record`
   `docs/REL051-rc-record.md`; `packages` + X32. Check `RP.L01-L11` (loader) and `tests/test_rel_*.py`. If the loader
   or a test refuses a second release on one line, that is an RP §12 stop: report to the user.
4. Push, CI green. **K3'** as 0.5.0's K3 (`<briefs>/REL050-K3.md`, commits 8aaed3f2 and a6d1bea8): version 0.5.1,
   envelope pinned (id/release for 0.5.1), A10 pairs, RELEASE_PINS, harvest REL050's manifest if any; F0; P1-P6.
5. **J'**: re-takes at K3' (five G10, M05 REAL, M01 IDAES) with proofs (`<briefs>/REL050-J.md`, drivers
   retakes.sh, proofs_g10_idaes.sh); **journey** at J' (journey.sh, `PYTHONPATH=src`); C' = the journey commit.
6. Push C' as `rc/<C7>`; CI push run; `release_rc` dispatch; RC local steps 2, 6-16 (rc_local.sh, at most 8
   threads), then ci/step1/items (rc2.sh), records, RC record, tree record, `--lapses`. Full gate at C' in its own
   clean worktree (`PATH=$R/.venv/bin:$PATH PYTHONPATH=src scripts/gate.sh`; never commit in that worktree).
7. Lapses: expected V14 (b) lapsed (src changed) -> ask the user in chat AFTER the verdict (failure clause, §8.4);
   any decision item lapsed -> ask in chat before the verdict.
8. **One narrow verdict agent**: brief = 0.5.0's `<briefs>/REL050-verdict.md` adapted, plus "0.5.0's verdict
   121d7b32 is the baseline; judge at C' with the records, focusing on what changed (X32's cli.py, README)".
9. Rows, ledger, notes `## v0.5.1`, H1, H2, step 18 YES, H3 (0.5.0's REL050-H commits 8c661099, 6f9ccbe3, ee519d46,
   77d20401 as templates); CI; merge into main (fast-forward if main unmoved) with F0; dry run; dispatch (version
   0.5.1, rc C'); the user approves PyPI; then the 0.6.0.dev0 working form (RP §7.4) and lift the freeze (tell hub).

## Open decisions

- Line-file handling for a second release on one line (step 3): default as stated; stop if the machinery refuses.
