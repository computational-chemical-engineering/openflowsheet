# Build brief: ADR 0055 WO-R6 and WO-R4 — the standing RC script, the evidence manifest, CI (0.4)

Status: brief, 2026-11-06. ADR 0055 (Frank: parts 1–3 now, D2 later). Normative text: RP
`docs/derivations/release-procedure.md` (§6 the RC job, §6.7 items, §6.9 records, §6.10 CI, §9, §11.2 REL.A20), line
files `release/lines/{0.3,0.4}.json`. Branch `wp/RP`, worktree `.claude/worktrees/rp`; WO-R2/R3 done (`fdc4f9a0`,
`aa73d933`, `2bac7fa9`; read `docs/RP_DECISIONS.md` B-1…B-15 and `docs/RP_HANDOFF.md` if present).

## Scope

- **WO-R6** `scripts/release_rc.py` (the standing RC steps 1–16 of RP §6.1 and the `rc_items` wrapper that runs each
  item command into a `t08-rc-v1` record; **no `strace` wrapping** — deferred with D2) and
  `scripts/release_evidence_manifest.py` (RP's standing assertion catalogue RP.S01–S22 plus the line file's items).
  Also the missing item scripts RP names for 0.4's `rc_items`, starting with `scripts/wheel_data_check.py --commit <C>`
  (RP §3.6, lines ~225–240: it moves V03.A17's ship-set and E01-data checks), so that `release_gate.py --line 0.4`
  passes RP.L08. Acceptance: **REL.A20** — on 0.3.0's committed records, each standing assertion's status equals
  S13's manifest; RP.L01–L10 all pass on `release/lines/0.4.json`.
- **WO-R4** `.github/workflows/ci.yml`: junit on both legs, `release_rc` (workflow_dispatch input), `check`'s `if`,
  `release-audit`, `ptc-r1` under `release_rc` (N-2), the `rc-ensemble` job in the dispatch list (RP finding against
  D4.2); **no `strace` parts**. Acceptance: **REL.A17** (ci.yml text: `check`'s `if`, the `junit-<arch>` uploads, the
  `release_rc` job list; step-1 record fixtures: a green push run, a missing run, a red aarch64 leg), and **one
  `release_rc` dispatch at `wp/RP`'s head** that shows `check` skipped, the RC jobs run, and `junit-x86_64` /
  `junit-aarch64` present (N-4's measurement). Dispatching on this repository's own CI is authorised; one dispatch only,
  report its run id and outcome. Normal push CI must still run `check` on both architectures exactly as before.

## Rules

- RP is binding. Where RP leaves a choice, decide, isolate, log in `docs/RP_DECISIONS.md` (C-1…); where RP is silent on
  something that changes what passes, stop and report. Never loosen a check. Legacy release scripts and their tests
  (`scripts/v0_2_gate.py`, `scripts/v0_3_gate.py`, the T08/V03 RC scripts) are not edited.
- Run the tests you touch, the release/workflow suites, ruff, ruff format, mypy. F0 `scripts/corpus_identity.py
  --check` PASS. Then the **full gate once**, in the background:
  `PYTHONPATH=$PWD/src PATH=/home/frankp/Codes/OpenFlowsheet/.venv/bin:$PATH ./scripts/gate.sh`, logs under
  `/tmp/claude-1003/-home-frankp-Codes-OpenFlowsheet/fd59d98d-797a-4da8-93d6-9c61c6d4bdc7/scratchpad/rp-gate/`. Known
  reds not yours: wall-time budget tests under host load (re-run alone, report both timings, never change a budget).
- Then the evidence manifest `evidence/RP/<commit>/manifest.json` (format as `evidence/F0/eba4bcb4…/manifest.json`;
  classify its limitations in the support-envelope harvest as F0's D22/D23 did; status `tested` only if the results
  support it; never `reviewed`), harvest tests re-run. Push `wp/RP`; report the CI run id. Do not merge.
- Commit on `wp/RP` only, named paths, messages `RP WO-R<n>: …`.
- Context cap about 150k tokens: commit what is complete, update `docs/RP_HANDOFF.md` (≤ 40 lines), stop.
- Never read, stat or touch `~/.config/procsim/`; do not read `/home/frankp/s10-papers/`, `~/.cache/seider3/`,
  `~/.cache/seider4/`; nothing under other worktrees. No subagents.

## Report (≤ 25 lines)

Commits; REL.A17, A20 and RP.L01–L10 results; dispatch run id and what it showed; gate result; manifest; push CI run id;
choices logged; design-lane questions.
