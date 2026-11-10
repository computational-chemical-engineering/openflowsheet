# Implementer brief: REL040 prep — evidence manifest and T08 harvest

Status: brief, 2026-11-10. Bounded build-lane item. **Do not spawn sub-agents yourself.** Start only when the
orchestrator gives you the CI run id.

## Where

Branch `wp/REL040p`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/rel040p`, CI-green head `829aadf4`
(full sha `829aadf40a2601413e7e1771d87d606b9f8a5d14`). `/home/frankp/Codes/OpenFlowsheet/.venv/bin/python` with
`PYTHONPATH=src`; confirm `openflowsheet.__file__` points into the worktree. Serial tests, `OMP_NUM_THREADS=1`.
TRS2 (reset twice under load): `uptime` first; one test process at a time; never a full suite. Do not touch the
git-ignored `.cache/s6r/` there.

## Evidence form (orchestrator decision, 2026-11-10)

`evidence/REL040/829aadf40a2601413e7e1771d87d606b9f8a5d14/manifest.json`, `work_package: "REL040"`. This is the 0.4
line's own evidence package (`release/lines/0.4.json` `gate_set.evidence_package`, RP.L11). This manifest is the
**prep** manifest; the RC cut adds the candidate's later. Say so in `limitations`. Pattern:
`evidence/S15a/d7cb4dbb77adeafab943959966e7269a17ca29f3/manifest.json`. `requirements`: `[]` unless the RP or ADR
0074 names schema-valid ids.

## What was done and run (facts for `commands` / `checks`; the log is `docs/RP_DECISIONS.md` on the branch)

One check per item. Each states its recorded result and where it is recorded (commit, test file, log section):

- x05 gate entry `c46ef9fc`;
- RP.L11 `9743871e` (R-1007);
- S-6 rehearsal `a1a00e17`;
- S6dbg F-A `3e25b294`;
- S-6 ruling WO-1–WO-5 (A-11, R-1008);
- WO-6 / fresh rerun proof;
- Q-S6d `0282e4d6`;
- WO-8 `d7258775`;
- WO-7 `26ad9d7f` with its live proof line;
- A-11 item 7 `0b62c12d`;
- S6R-29 (default tier at J′: head 16007/0, J′ 3 failures = Q-S6e cases);
- Q-S6e `c8be15dc`;
- reviewer pass `docs/reviews/REL040-review.md` (sound, S-1);
- WO-R1 `5b8575a4`, N-1 `cfa46e70`, N-3 `c95288f4`, N-5 `a385a417`;
- the live REAL proof line `RETAKE-DIGEST-ONLY PASS trust-region-study-real: changed-digests=103 digest=504 timing=528 path=128 version=0 platform=4 other=0 environment=equal`;
- S77 42/80/71/92/38;
- F0;
- the CI run (id from the orchestrator);
- FULLGATE `unsupported` (as in RRC/OPT/ST/X04).

A check with no recorded result is `unsupported` with the reason, never inferred. Status is `tested` only if every
check passes or is an accepted, documented unsupported; review is pending/pending.

## Limitations (no new claims; no angle-bracket text)

- Evidence class: release-procedure software verification; the re-takes are rehearsals, not records.
- Prep manifest, not the release evidence: K3 re-takes and journey J come at the cut.
- N-2 left as ruled; N-4 not done.
- O-6 settled for the default tier only (the review's O-6 note).
- No local full gate.

## Do

1. Write the manifest. If `origin/main` moved since the branch's last merge of it only by `docs/` commits, merge it.
   If any non-docs commit came in, stop and report.
2. **Harvest (required):** classify every new manifest item (each limitation, each non-pass check) in
   `benchmarks/t08/support_envelope.yaml` in X04's form. Run `scripts/t08_support_matrix.py --emit`, then `--check`,
   which must report 0 problems. Update `HARVEST_SIZE` in `tests/test_m07a_harvest.py` with one comment line.
3. Run `tests/test_m07a_harvest.py tests/test_t08*.py tests/test_evidence_manifests.py tests/test_rel_*.py` (0
   failures), F0 `scripts/corpus_identity.py --check` (PASS), `ruff check` and `ruff format --check`.
4. Commit named paths only, message `REL040: prep evidence manifest at 829aadf4 (tested); T08 harvest (...),
   HARVEST_SIZE (...)`, with trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
   https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`. Push `wp/REL040p`. Do not merge into main.

Never read or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`, `~/.cache/seider3/`, `~/.cache/seider4/`.

## Report (at most 15 lines)

Manifest path and status, checks summary, harvest counts and HARVEST_SIZE move, test counts, F0 line, commit sha(s),
anything stopped on.
