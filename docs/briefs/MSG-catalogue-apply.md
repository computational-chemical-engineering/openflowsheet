# Build brief: apply the MSG catalogue prose ruling for X02/OPT codes (branch `wp/MSGp`)

Status: brief, 2026-11-09. **Do not spawn sub-agents yourself.** Ruling: `docs/reviews/MSG-catalogue-X02-OPT.md`
(design lane, `f7da1420`). Its §5 is your work order (10 steps) and §6 the acceptance assertions A1–A9 with exact
values. Apply it verbatim; you decide nothing the ruling settles.

## Where

New branch `wp/MSGp` from main **at `9295f0fc`** (main's catalogue content there equals the ruling's base `c1ced8a7`;
only docs moved since), worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/msgp`
(`git worktree add -b wp/MSGp .claude/worktrees/msgp 9295f0fc`). Worktrees have no `.venv`: run
`/home/frankp/Codes/OpenFlowsheet/.venv/bin/python` with `PYTHONPATH=src` (CLI pin writer: `PYTHONPATH=src:.`) and
confirm `openflowsheet.__file__` is the worktree's copy first. Venv has no xdist: run tests serially.

Why this base: RRC (`wp/RRC`, CI running) will merge into main first and moves the catalogue digest
(`7bbe3d65…` → `14921a20…`, allow-list entries only). Building on the ruling's own base lets you prove §6's exact
numbers (A2's digest `5e5026c5…`, review count 138 → 129) before any re-base. The orchestrator merges main (with RRC)
into `wp/MSGp` afterwards and regenerates the digest-carrying fixtures — not you.

## Do

1. §5 steps 1–10, one commit (message `MSG: catalogue prose for X02/OPT codes, C12 amended (ruling MSG-catalogue-X02-OPT)`),
   step 9's D-number in `docs/OPT_DECISIONS.md`. Step 4 is harness plumbing: keep the mechanism small and local to
   `tests/test_msg_corpus.py`, and make C12's precondition an assertion as the ruling says.
2. Check every §6 assertion A1–A9 and record the measured value next to each in the commit body. **If a number does not
   come out as stated, stop and report** — do not adjust the YAML.
3. Run §5 step 10's tests plus `scripts/msg_catalogue.py check`, `ruff check`, `ruff format --check`; F0
   `scripts/corpus_identity.py --check` PASS.
4. Push `wp/MSGp`. No merge into main, no manifest.

Trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`; named paths only. TRS2 shared: `uptime` first; targeted tests
only. Never read or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`, `~/.cache/seider3/`, `~/.cache/seider4/`.

## Report (≤ 15 lines)

Commit; A1–A9 measured vs stated; test counts; F0 line; anything stopped on.
