# Build brief: X02 WO-7 — close-out after the D-32 ruling

Status: brief, 2026-11-07. Branch `wp/X02`, worktree `.claude/worktrees/x02`, head `8d15e28c`. Read first:
`docs/X02_HANDOFF.md` (where WO-6 stopped), the ruling in main's `docs/roadmap/decisions.md` (entry "X02 WO-6 …
ruling D-32", commit `c054530b`). Review `docs/reviews/X02-review.md` is binding. Never squash; evidence pins
`69c4a24d`, `005d206f`, `dcb499ee`.

## The ruling (D-32), to carry out — do not reinterpret

G5d (iii)'s criterion "the warm run takes fewer outer iterations than the cold one" **failed** (4 = 4). It stays in the
note and in the manifest as failed. It is not removed and not relaxed. The neighbour-speedup claim is withdrawn.

1. Design note `docs/design/X02-warm-starts.md` §7 G5 (d)(iii): append, in the file's existing amendment style:
   *Amended (D-32 ruling, 2026-11-07, A-10):* Measured on v3 (S-2, `dcb499ee`): cold and warm both VERIFIED, the Δû
   bound held (3.76e-4 ≤ 1.64e-3), the edit moved û by 83.7 bounds; warm took 4 outer iterations, as cold did (222.7 s
   against 181.5 s). The iteration criterion is **not met** and stays recorded as failed. The premise (an outer start
   near a neighbour's fixed point saves outer iterations) is false for this edit on the real loop; ADR 0070 withdraws
   the claim. A later design that claims a neighbour speed-up must measure it again.
2. ADR 0070 Consequences bullet 1: keep the same-revision sentence, add the G5d (ii) numbers (1 outer iteration,
   1 call, 24.7 s against 193.7 s cold). Replace "A neighbouring revision restarts near its fixed point." with an
   *Amended (D-32 ruling)* sentence saying that a neighbouring revision starts near its fixed point but is not claimed
   to converge faster: on v3 with SPEC-S3-T +2 K it started about twice as close and took the same 4 outer
   iterations, and took longer (222.7 s against 181.5 s). Acceptance evidence: "G5 (d) ran on v3 per S-2: (i), (ii)
   met; (iii) both VERIFIED, bound held, the iteration criterion not met (D-32 ruling)". The status stays **Proposed**.
3. `docs/X02_DECISIONS.md` D-32: record the ruling and the commit.

## Then

4. `docs/progress.md` X02 line.
5. Full gate **once**, in the background, only when `pgrep -af 'scripts/gate.sh|scripts/check.sh'` is empty and
   `uptime`'s 1-min load is ≤ ~24 (TRS2 rule: the machine stays ≤ ~36 busy cores of 48; one full gate machine-wide; the
   X05 engineer may be running one: wait for it). Command:
   `PYTHONPATH=$PWD/src PATH=/home/frankp/Codes/OpenFlowsheet/.venv/bin:$PATH ./scripts/gate.sh`. Read the log only on
   failure, by grep/tail. F0: `scripts/corpus_identity.py --check` (M1–M9).
6. Manifest `evidence/S16/<head>/manifest.json`: the frozen pattern refuses `X02`, so it is filed as S16 under R-878's
   rule (as RP's S15, C-22); harvest as RP did in `f6f838dd` (support_envelope, support-matrix regeneration,
   `HARVEST_SIZE` in `tests/test_m07a_harvest.py`). Every gate in the note gets a check. G5d (iii)'s iteration criterion
   has its own check with result `fail` and a note citing D-32. G5's warm-variant items stay as WO-6 left them (not
   registered, D-29). Set status `tested` only if every other check is supported. If the repo's manifest validator or
   tests refuse `tested` with a `fail` check, do **not** remove the check: stop and report.
7. Commit (named paths), push `wp/X02`, record the CI run id; check it at most every 10 minutes (GitHub rate limit). CI
   must be green on both architectures.

## Do not

Merge into main (the orchestrator merges after Frank accepts ADR 0070). Set `reviewed`. Change wall-time budgets. Run
any reactor campaign. Touch `wp/MSG` or `wp/X05`. Read `~/.config/procsim/`.

## Report (≤ 30 lines)

Head, gate count, F0, manifest path and status, CI run id and result, anything that failed.
