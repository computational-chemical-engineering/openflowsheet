# Implementer brief: X04 — evidence manifest and T08 harvest

Status: brief, 2026-11-09. Bounded build-lane item. **Do not spawn sub-agents yourself.**

## Where

Branch `wp/X04`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/x04`. CI-green head `0f7d9b87` (full
sha `0f7d9b87467456f89c6c541e167c7c59b2dfc413`), **CI run `42659368086`** (`ci.yml`; `check (ubuntu-latest)`,
`check (ubuntu-24.04-arm)`, `default-install` success). The branch head is `1d456c46`, a docs-only commit on top
(ADR 0075 note for D-22 and an `interfaces-frozen.md` clause, design lane, `docs/reviews/REL040-s6-ruling.md` §11.5);
the manifest is at `0f7d9b87` and names `1d456c46` as docs only. Worktrees have no `.venv`: run
`/home/frankp/Codes/OpenFlowsheet/.venv/bin/python` with `PYTHONPATH=src`; confirm `openflowsheet.__file__` points
into the worktree. Serial tests (no xdist), `OMP_NUM_THREADS=1`.

**TRS2 must stay quiet** (it reset twice under load; a hardware fault is suspected). `uptime` first; one process at a
time, targeted tests only, never a full suite, never parallel runs.

## What was run (exact facts for `commands` / `checks`)

- Merge condition (CLAUDE.md "Gate by risk", Frank 2026-11-08): the CI run above. No CI-equivalent local full gate is
  claimed: the CI fix round ran `scripts/check.sh` once at `9446a592` (1 failed — the stale notices doc page, fixed in
  `e33a95e4`, `test_doc_pages` 3 passed — 16583 passed); FULLGATE is `unsupported` as in RRC/OPT/ST.
- Spec: ADR 0075 Accepted (Frank, 2026-11-09, decision board `adr-0075`) with its notes; test specification
  `docs/derivations/X04-test-specification.md` A1–A40 (§4 site table, §8 FQ4 amendment); generator
  `docs/derivations/scripts/x04_reference.py`; review `docs/reviews/X04-review.md` (sound, no must-fix; S1–S4 applied
  in the fix round; N1–N6); build decisions D-1…D-22 in `docs/X04_DECISIONS.md`; state `docs/X04_HANDOFF.md`;
  register R-1010…R-1016. Surface: c_8, D_8 `6be1c002592524126617af8dd65d331513f4a96355f5381dba020ad561a2ba57`,
  `without_x04` = ST's D_7 `553b7612…`. Description reviews of `get_job_result` and `get_stream_table`: design lane
  approved (reviewer), human approved (recorded by Frank's own script, `a39ebfff`; never edit it).
  Frank's board answers: FQ1–FQ3 default, FQ4 alt1 (°C/°F in human text: D-19…D-22).

## Do

1. `evidence/X04/0f7d9b87467456f89c6c541e167c7c59b2dfc413/manifest.json`, `work_package: "X04"`, in the pattern of
   `evidence/ST/451225195aa30af51de139452c66f462904fa84e/manifest.json` (on main). `requirements`: only ids the schema
   accepts (`^[DA][0-9]{2}$`; ADR 0075 names D08). One check per assertion A1–A40 (or per assertion group where the
   spec groups them), each with its recorded result and where it is recorded (test file / decision id); one with no
   recorded result is `unsupported` with the reason — never inferred. Add the CI run, F0, and FULLGATE (`unsupported`).
   `status: "tested"` only if every check is pass or an accepted, documented unsupported; otherwise `implemented`,
   stop and report. `review` pending/pending (never `reviewed`).
2. `limitations`: evidence class (software verification of display arithmetic at the boundary; SI stays the computed
   quantity); the review's Notes N1–N6 not acted on (N4: `eng` page cost not measured on the largest example); D-22's
   catalogue-schema note; no local full gate at the head. No new claims; no angle-bracket text (write "at most / at
   least").
3. If `origin/main` moved since X04's last merge of it only by `docs/` commits, merge it; any non-docs commit: stop and
   report.
4. **Harvest (required):** classify every new manifest item (each limitation, each non-pass check) in
   `benchmarks/t08/support_envelope.yaml` in ST's form (`manifest`, `item`, `sha256` = `text_sha256` of the item,
   `class`, `to`, `note`); `scripts/t08_support_matrix.py --emit`, then `--check` = 0 problems; `HARVEST_SIZE` in
   `tests/test_m07a_harvest.py` with one comment line in the existing style (at most 120 chars). Run, one at a time:
   `tests/test_m07a_harvest.py tests/test_t08*.py tests/test_evidence_manifests.py tests/test_x04_*.py` — 0 failures;
   F0 `scripts/corpus_identity.py --check` PASS; `ruff check`, `ruff format --check`.
5. Commit named paths only, message `X04: evidence manifest at 0f7d9b87 (tested); T08 harvest (...), HARVEST_SIZE
   (...)`, trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
   https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`. Push `wp/X04`. Do not merge into main.

Never read or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`, `~/.cache/seider3/`, `~/.cache/seider4/`.

## Report (at most 15 lines)

Manifest path and status, checks summary (pass / unsupported counts, any non-pass named), harvest counts and
HARVEST_SIZE move, test counts, F0 line, commit sha(s), anything stopped on.
