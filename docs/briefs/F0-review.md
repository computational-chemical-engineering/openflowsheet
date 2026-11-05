# Reviewer brief: F0, the corpus identity gate — review plus one ruling round (0.4)

Status: brief, 2026-11-05. F0's single design-lane pass: an independent review of the finished build **and** rulings on
three open questions (CLAUDE.md "Agent budget": batch the design-lane questions into the package's reviewer pass).

## What F0 is meant to do (the design)

`docs/roadmap/target-architecture.md` §3 F0 (lines 712–736) and the S1 byte-level freeze (§2.4.4, line ~473: "An
identity-bearing legacy module is one whose bytes enter an `implementation_sha256`, or one imported into such a hash
set. Such a module is never edited."). Build brief: `docs/briefs/F0-build.md`. F0 is the gate before every foundation
merge (roadmap "Gates"), so a gate that passes without verifying is the failure that matters most.

## The work

Branch `wp/F0`, worktree `.claude/worktrees/f0`; `git log main..wp/F0` = 87936afa…032105e2 (10 commits, 546 files,
mostly the 52 fixture bundles). Files that matter: `scripts/corpus_identity.py`, `benchmarks/f0/corpus.json`,
`tests/test_f0_corpus_identity.py`, `.gitattributes`, `tests/fixtures/f0/v0.3.0-bundles/`, `docs/F0_DECISIONS.md`
(D1–D16), `docs/F0_HANDOFF.md`.

## What was run, and the numbers

- `corpus_identity.py --check` at ab97a46e: `F0 PASS: M1 50/50, M2 52/52, M3 52/52, M4 52/52, M5 52/52, M6 52/52,
  M7 52/52, M8 105/105, M9 8/8`. F0 test file: 14 tests, ~90 s.
- Exit 2 (one ulp in SYN-001's split fraction, plus the spec pinning it → M2 `constants_sha256`, M3, M4 FAIL), exit 3
  (monkeypatched flipped check → M5 FAIL), exit 4 (one byte in a copy of a frozen module → M9 FAIL naming it): pass.
- `.gitattributes` eol=lf; `git add --renormalize .` a no-op (3739 LF files, 0 CRLF).
- Full gate at ab97a46e: 4 failed / 14849 passed / 3206 skipped (3 h, host load ~50). Three failures are D15 below; the
  fourth is `test_f6_the_forty_runs_fit_their_budget` (450.1 s in the gate, 344.0 s alone, budget 300 s, load ~50 both
  times; not touched).

## Where the build is least sure (look here)

- M4 (`state_sha256`) is judged only on the reference platform; M7's replay *mode* is not judged off it (D12).
- M6 reads cache keys from only 15 of the 52 runs.
- M9's set is 8 thermo files found by an AST scan (D9, D14). Is the scan complete, and does it fail loudly if it cannot
  resolve an import?
- M8 wraps 10 existing round-trip test functions by node id in a subprocess (D13): does a deselected or renamed test turn
  into a silent pass?
- Does `--check` compare against registered expected values from `benchmarks/f0/corpus.json`, with no path where a missing
  measure or an empty corpus reads as PASS?

## Rulings wanted (each: decide, give the reason, and say what the build lane does)

1. **D15 — the fixtures break three guard tests.** `test_t05b_literal::test_b06…`, `test_t06_f4_literals::test_wo1…`,
   `test_t06_w18_literal::test_w18…` scan `tests/fixtures` and `benchmarks` for policy values committed documents must
   not hold; 37 of the bundles' `solve-policy.json` hold them, because they are archived outputs of the 0.3.0 release.
   Options: (1) exempt archived replay bundles by structure (a directory holding `run-manifest.json`) — the engineer's
   default; (1′) the orchestrator's variant: exempt exactly the files registered in `benchmarks/f0/corpus.json` by
   SHA-256, with a test pinning the exemption count (37), so nothing new can enter the exemption unregistered;
   (2) a root the guards do not scan; (3) build the bundles at check time from the tag (fails on shallow CI clones).
   CLAUDE.md forbids relaxed checks to pass a gate: rule on whether (1)/(1′) is a relaxation or a scope correction.
2. **D16 — the evidence schema refuses `F0`.** `schemas/evidence-manifest.schema.json` `work_package` pattern
   `^[PKTMSR][0-9]{2}[a-z]?$` (frozen; schemas change only by a design-lane ADR). Every roadmap package id (F0–F8, MSG,
   ST, X04, X05, X02, OPT, RRC, …) fails it; ADR 0028 once chose a fitting id instead. Default: an additive ADR widening
   the pattern so every existing id stays valid and the roadmap's ids are accepted. If you rule for the ADR, write it
   (`docs/adr/0059-…`, Proposed or Accepted as your authority allows) with the exact new pattern.
3. **D9 — M9's scope.** Currently: modules feeding `implementation_sha256` plus modules imported into such a hash set
   (8 files). Not included: 30+ unit-model modules that hash their own bytes into a model's `artifact_hash` (their edits
   move model identity, which M1–M3 should catch). Default: keep them out. Rule, and if you include them say how M9
   enumerates them.

## Not to spend time on

The fixture bundles' contents (they are the released outputs, byte-checked by M7); ruff/mypy style; the wall-time test
(a host-load question; it will be re-run on a quiet host).

## Deliverable

`docs/reviews/F0-review.md`: findings ranked (must-fix / should-fix / note), each with `file:line` and a failure
scenario; the three rulings; whether F0 may be marked `tested` once the rulings are applied and the gate is green. Plus
the ADR if ruling 2 needs one. Report ≤ 30 lines. Do not commit; do not edit code. Never touch `~/.config/procsim/`.
Do not touch `.claude/worktrees/msg`. Do not start subagents.
