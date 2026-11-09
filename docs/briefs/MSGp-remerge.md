# Engineer brief: re-base `wp/MSGp` on main after RRC, regenerate, manifest

Status: brief, 2026-11-09. Bounded build-lane item. **Do not spawn sub-agents yourself.** Start only when the
orchestrator says RRC has merged into main.

## Where

Branch `wp/MSGp`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/msgp`, head `8906f870` (one commit,
"MSG: catalogue prose for X02/OPT codes, C12 amended"). It was built on main `9295f0fc` on purpose, to prove the
ruling's exact numbers (`docs/reviews/MSG-catalogue-X02-OPT.md` §6 A1–A9; A2 digest `5e5026c5…`, review count 138 →
129). Those were proved; the commit body records them. Worktrees have no `.venv`: run
`/home/frankp/Codes/OpenFlowsheet/.venv/bin/python` with `PYTHONPATH=src` (CLI pin writer: `PYTHONPATH=src:.`) and
confirm `openflowsheet.__file__` is the worktree's copy. Serial tests (no xdist), `OMP_NUM_THREADS=1`.

## What changed on main since

RRC merged (`wp/RRC`, ADR 0072). Files both sides touched: `src/openflowsheet/messages/catalogue/scan-allow.yaml`
(RRC: allow-list labels added), `limitations.yaml`, `benchmarks/t08/support_envelope.yaml` (RRC: harvest entries),
`docs/support-matrix.md`, `docs-site/messages/limitations.md`, the two `message_entry` fixtures carrying the catalogue
digest (main after RRC: `14921a20…`).

## Do

1. `git merge origin/main` (no rebase; history is shared). Resolve conflicts:
   - **hand-written sources** (`scan-allow.yaml`, `support_envelope.yaml`, `refusals.yaml`, `corpus.yaml`, tests):
     keep **both** sides — RRC's added entries plus the ruling's rewritten lines. Never drop an entry from either side.
     If a conflict is anything other than "both added/changed different entries", stop and report.
   - **generated files** (`docs/support-matrix.md`, `limitations.yaml`, `docs-site/messages/*`, `message_entry`
     fixtures, `tests/fixtures/t07/cli-existing-commands.json`): take either side, then regenerate (step 2).
2. Regenerate, in the ruling's §5 order: `scripts/t08_support_matrix.py --emit` then `--check`;
   `scripts/msg_catalogue.py sync-limitations` then `--check`; `scripts/doc_pages.py` then `--check`;
   `scripts/t07_schema_fixtures.py --write`; `PYTHONPATH=src:. python tests/test_t07_w5b_cli.py --write-pins`. Do **not**
   touch `tests/fixtures/opt/pre_opt_u05.json` or `tests/fixtures/opt/pre_opt_descriptions/`.
3. Re-measure A1–A9 on the merged tree. Expected: A1's entry/complete counts and A2's digest **move** by exactly RRC's
   additions (record the new values; the digest is neither `5e5026c5…` nor `14921a20…`); review count = main's count
   after RRC minus 9; A3–A9 hold as stated. Any other movement: stop and report.
4. Tests: §5 step 10's list plus `tests/test_rrc_*.py tests/test_m07a_harvest.py tests/test_t08*.py
   tests/test_evidence_manifests.py`; `scripts/msg_catalogue.py check`; F0 `scripts/corpus_identity.py --check` PASS;
   `ruff check`, `ruff format --check`. 0 failures.
5. In `docs/OPT_DECISIONS.md`, amend the D-number added in `8906f870` with one line: re-based on main after RRC, digest
   `7bbe3d65…` → the new value, commit.
6. Commit (named paths; message `MSG: re-base catalogue prose ruling on main after RRC; regenerate`), push `wp/MSGp`,
   and report the head sha. The orchestrator watches CI.
7. **After the orchestrator gives you the green CI run id** (or in the same go if told): write
   `evidence/MSG/<full head sha>/manifest.json` in the pattern of `evidence/MSG/5e9274db…/manifest.json`: package MSG
   follow-up (ruling `docs/reviews/MSG-catalogue-X02-OPT.md`); checks = A1–A9 with measured values, the CI run (all four
   jobs), the tests of step 4; `status: "tested"`; review pending/pending (never `reviewed`); limitations from the
   ruling's §7 and the §8 findings left open (F1: G1 misses `OPT.*` check ids). No angle-bracket text (write "at most /
   at least"). Run `tests/test_evidence_manifests.py`; commit `MSG: evidence manifest at <short sha> (tested)`; push.
   No merge into main.

Trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`. TRS2 shared: `uptime` first; targeted tests only. Never read
or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`, `~/.cache/seider3/`, `~/.cache/seider4/`.

## Report (≤ 15 lines)

Merge conflicts and how resolved; A1–A9 measured (new digest, counts); test counts; F0 line; commit sha(s); anything
stopped on.
