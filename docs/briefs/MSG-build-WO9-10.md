# Build brief: MSG WO-9 (corpus, complete entries) and WO-10 (web shell display) — 0.4

Status: brief, 2026-11-06. Spec: `docs/design/MSG-messages.md` — WO-9/WO-10 at lines 1325–1334, gate table §7
(MSG-G4, G5, G6, G8; lines ~1340–1356), corpus cases C01–C12 and §3.6 (read by grep). ADR 0058 Accepted (R-932…R-937).
Branch `wp/MSG`, worktree `.claude/worktrees/msg`. WO-0…4, 6, 7, 8 done; read `docs/MSG_HANDOFF.md` and
`docs/MSG_DECISIONS.md` (D0-1…D8-3) first.

## WO-5 is parked (orchestrator decision 2026-11-06)

WO-5 (the diagnostic sidecar) must edit `models/thermal/{flash,heater,machines,mixer,valve}.py`, which F0 (now on main)
freezes byte-for-byte (M9, R-940). That is a design-lane question; do **not** edit those files. Consequence for WO-9:
the C01/C02 *numbers* (`value`, `saturated_vapour`, `pressure`; `s_star`, `s_saturated`) come from WO-5. Assert
everything else of C01/C02 now (code, kind, elements, surfaces, limitation); put the number assertions in a separate
test marked `pytest.mark.xfail(strict=True, reason="MSG WO-5 parked: thermal modules frozen by F0 M9 (R-940)")`, so the
test fails loudly the day the numbers appear. Log this as a D9 decision. No other case may be weakened.

## Scope

- **WO-9:** `tests/fixtures/msg/corpus.yaml`, `tests/test_msg_corpus.py` (MSG-G6, cases C01–C12 on the surfaces the
  table names; for C06–C09 first record the actually emitted code, §3.6), and complete catalogue entries for every
  corpus code (prose drafted per the spec's style rules, then checked; MSG-G4 lint on every complete entry). Call
  `tests/test_msg_docs.docs_url_problems` on every explanation the corpus renders. A catalogue edit needs
  `scripts/doc_pages.py` and `scripts/t07_schema_fixtures.py --write` (both have `--check` tests).
- **WO-10:** the web shell's error and outcome display: a refused request shows `explanation.summary` and `action`; a
  failed run shows `failure.explanation.summary`. The existing web-shell tests plus those two.

## Rules

- Start with `git merge main` on `wp/MSG` (brings F0: `scripts/corpus_identity.py --check`, M1–M9, and W1's docs).
  Resolve conflicts, if any, in favour of main's F0 files; report them.
- Identity: both WOs are identity: no. At the end, MSG-G0 (a–d) and `scripts/corpus_identity.py --check` must PASS. On
  any difference, stop and report. Never adjust a gate to pass; a gate change gets its own commit, a logged reason, and
  is flagged.
- Build choices: decide, isolate, log in `docs/MSG_DECISIONS.md` (D9-…, D10-…). A choice that changes numerics,
  identity or a frozen interface beyond ADR 0058: stop and report. Design-lane questions are batched — list them.
- Run the tests you touch. Run the full gate once at the end in the background
  (`PYTHONPATH=$PWD/src PATH=/home/frankp/Codes/OpenFlowsheet/.venv/bin:$PATH ./scripts/gate.sh`, logs under
  `/tmp/claude-1003/-home-frankp-Codes-OpenFlowsheet/fd59d98d-797a-4da8-93d6-9c61c6d4bdc7/scratchpad/msg-wo9/`) and
  wait for its notification. Known reds, not yours: `test_t08_w2_description_reviews` (waits for the reviews of
  `explain.md`, D7-8) and wall-time budget tests under host load (`test_f6_the_forty_runs_fit_their_budget`,
  `test_the_budget_of_the_scenario_runs`; re-run alone, report both timings, never change a budget).
- Then write the evidence manifest `evidence/MSG/<commit>/manifest.json` (status `tested` only if every gate result
  supports it; follow the format of `evidence/F0/eba4bcb4c338c2968e3ed63891cdca91ef7c01f8/manifest.json` on main, and
  classify its limitations in the support-envelope harvest as F0's D22/D23 did — `docs/F0_DECISIONS.md` on main), and
  re-run the harvest and evidence-manifest tests. Never set `reviewed`.
- Commit on `wp/MSG` only, named paths, messages `MSG WO-<n>: …`. You may push `wp/MSG` to origin at the end (not main);
  report the CI run id. Do not merge.
- Context cap about 150k tokens: commit what is complete, update `docs/MSG_HANDOFF.md` (≤ 40 lines), stop.
- Never read, stat or touch `~/.config/procsim/`; do not read `/home/frankp/s10-papers/`, `~/.cache/seider3/`,
  `~/.cache/seider4/`. Do not start subagents.

## Report (≤ 30 lines)

Commits per WO; MSG-G4/G5/G6/G8 and G0 a–d, F0 summary lines; corpus results per case; gate result; manifest path and
status; CI run id; choices logged; design-lane questions.
