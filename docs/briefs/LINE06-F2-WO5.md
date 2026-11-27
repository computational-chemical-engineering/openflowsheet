# LINE06 F2-WO5: probe flowsheets (ADR 0062 work order 5, E-F2-4)

Build lane, `opus-engineer`. **Do not spawn sub-agents yourself.** Rules: `docs/LINE06_RULES.md` (read it first,
including the surface-suite rule). Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f2`, branch
`wp/F2` (head `d14e7ce7`: WO1 to WO4 done). Another engineer works on X06 in `.claude/worktrees/x06`; leave it alone.
Budget about 150k context: at the cap, commit what is complete, write where you stopped in `docs/F2_DECISIONS.md`,
and end. Logs and scripts go under `/home/eajfpeters/.cache/line06/f2wo5/` (never a shared scratchpad: F2-WO4 lost a
run to another agent overwriting `battery.sh` there).

## The task

Build ADR 0062 (`docs/adr/0062-F2-material-model.md`) work-order row 5 (line ~362): `tests/f2/probes.py` and the
test-only attribute kinds, so that E-F2-4 (line ~326) runs: test-only numeric probes (mixer with at most 8 inlets,
splitter, heater in `(n, ĥ, P)`, division-free rows solved for the outlet, no property call) on the probe flowsheets
of foundation rulings Q1.A5 (`docs/roadmap/foundation-rulings.md` line ~177: feed -> mixer <- dormant feed; dormant
branch -> heater -> splitter) and Q6.A1 to A5 (lines ~1059-1075, with the third probe `probe.partition`, line ~1342;
τ_mono = 1e-12 per S10, line ~1362, ADR line ~148). Also WO4's left-over: Q7.A2 on the probe streams
(`docs/F2_DECISIONS.md` ~line 340), and extend E-F2-6 (layout equals the independent build, bitwise) to the probe
states (F2_DECISIONS ~line 214, 325). Everything here is test code: no `src/` change unless a probe exposes a defect,
which is a STOP.

## Facts established

- At `d14e7ce7`: battery 5596 passed, 28 skipped, 3 xfailed, 0 failed; `tests/test_f2_revision_v2.py` 107 tests; F0
  PASS M1 50/50, M2-M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 42/42. These counts must hold.
- Layout, ids and bases: `src/openflowsheet/material/{layout,vid,basis,definitions,state}.py` (WO1 to WO3); revision
  v2: `src/openflowsheet/revision_v2/` (WO4). Their decisions: `docs/F2_DECISIONS.md` WO1-* to WO4-*.

## Acceptance (report each)

1. E-F2-4: relative conservation <= 1e-14 per carried amount and attribute (report the worst value); dormant streams
   exactly `+0.0`, `ĥ` bitwise its label; the 5e-324 stream flowing; Q6.A2 to A5 as the rulings state (A5 **[gen]**
   over the listed DP and amounts). O-9: report the worst moment deficit and its margin to τ_mono = 1e-12; a margin
   below 10x is a STOP for the design lane (do not amend τ_mono).
2. Q7.A2 on the probe streams; E-F2-6 extended to the probe states. Test names and counts.
3. Battery: the WO4 brief's suites (`tests/test_f*_*.py`, `tests/test_t07_*.py`, `tests/test_t08_w2_*.py`,
   `tests/test_m07a_surface_chain.py`, `tests/test_m02_*.py`, `tests/test_m04_*.py`, `tests/test_msg_*.py`,
   `tests/test_x0*_*.py`, `tests/test_package_imports.py`, schema tests) plus the new tests: 0 failed, after your
   last commit. ruff, ruff format --check, `mypy src` clean.
4. F0 PASS with the counts above, at your last commit.

## Stops (report rather than choose)

A probe that needs a `src/` change; a conservation, zero-flow or O-9 margin miss; the rulings contradicting the code;
a v1 byte, hash or F0 count moving; a test that passes only by relaxing a check.

## How

Commit named paths on wp/F2, messages `F2-WO5: ...`; DECISIONs in `docs/F2_DECISIONS.md`. Long runs through
`/home/eajfpeters/Code/OpenFlowsheet/.claude/skills/line06/run.sh <name> <command>`. No push, no merge.

## Report (200-300 words)

Per acceptance item: pass/fail and the numbers (worst conservation, worst moment deficit and margin); DECISIONs (one
line each); commits; anything for WO6.
