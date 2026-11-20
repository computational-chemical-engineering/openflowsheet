# X07a design ruling: replay platforms (Q-2) and per-platform reference values (Q-3)

Design lane, `specifier`. Do not spawn sub-agents yourself. Write the ruling to `docs/X07a-platform-ruling.md` on
branch `wp/X07a` (worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/x07a`), commit it there (docs only),
do not push, and report in about 300 words. No production code, no test edits.

## Question

X07a (roadmap 0.5; ADR 0056 row 5) adds `windows-latest` and `macos-latest` (arm64) CI legs. The build lane left two
classes of failure standing because each needs a ruling, not a choice:

- **Q-2 replay platforms.** `src/openflowsheet/run/replay.py:53` `REGISTERED_PLATFORMS = {(x86_64, Linux), (aarch64,
  Linux)}` (comment at :40-52: macOS arm64 was removed after the K05 review because "an option nobody took is not a
  registered platform"). Off Linux, `decide_mode` (:239) gives `inspected_archived_results`, verdict `NOT_RUN`, for
  every rerun, a same-host rerun included. Effects: F0 M7 fails on macOS (52/52 bundles `NOT_RUN` against registered
  `MATCH`; M1 to M6, M8, M9 equal, so no float difference in F0's runs); about 90 of 144 macOS test failures and 54
  Windows failures (`test_g8_rerun_matches_on_the_same_host`, `test_a16_a17_the_replay_matrix`, `test_g16*`,
  `test_t07_q26_*`, ...).
- **Q-3 floating point.** macOS results differ in the last bits from Linux-recorded fixtures:
  `test_every_registered_call_is_bitwise_the_baseline[kernel_targets]` (1.9163045025588417 vs 1.9163045025588423),
  `test_the_fixtures_are_what_real_runs_emit_today` (a margin 1.3370443359361772e-05 vs 1.33704433897...),
  `test_th_c1_golden[csv,json,text]`.

## What already exists (read these, narrowly)

- ADR 0067 (`docs/adr/0067-F8-identity-replay-evidence.md`) D7 "Per-platform reference records (ADR 0025's pattern;
  X07a)" (:152-190) and E-F8-8 (:263-266): one record per reference platform, a per-platform record only where a float
  exceeds the numerical policy, `platform_reference_used(<platform>)`, R0 identical on every registered platform "(the
  platform ids of ADR 0060 D2)". Nothing of D7 is implemented (`platform_reference_used` occurs nowhere in src or
  tests). ADR 0025 is the pattern it generalises. Find which ADR defines the registered platform ids (the D7 text
  cites ADR 0060 D2, which is the extension descriptor: check whether that citation is wrong).
- `docs/X07a_DECISIONS.md` on wp/X07a: Q-1 to Q-3 text, D-1 to D-19, the platform-limit table, Position.
- CLAUDE.md "Scientific conduct": no relaxed checks, removed cases, or narrowed denominators to pass a gate.

## Rule on (numbered, each with the reason and the evidence it rests on)

1. Q-2: is a platform registered for replay by adding it to `REGISTERED_PLATFORMS` once a CI leg measures it (which
   evidence suffices: a green same-host rerun leg? R0 equality over the registered cases?), or do macOS and Windows
   stay unregistered in 0.5 with the tests' expectations made platform-aware (and then: how F0 M7 states its expected
   verdict per machine class without relaxing it)? Name the replay mode a same-host rerun on an unregistered platform
   should get.
2. Q-3: does ADR 0067 D7 settle it (per-platform records where a float exceeds policy, built in X07a), and which of the
   three named failures are "bitwise baseline" tests that may never take a per-platform record versus policy-bounded
   comparisons? State the rule a build engineer applies to each further failure of this class.
3. Whether this needs an ADR amendment (ADR 0067 D7, or the registered-platforms ADR) or is within existing text; if an
   amendment, draft it in the ruling file as `status: proposed` (Frank accepts ADRs).
4. The work order that follows: an X07a-WO3 acceptance list with numbered, falsifiable checks.

Do not rule on Q-1 (pywin32 licence: rights, Frank).
