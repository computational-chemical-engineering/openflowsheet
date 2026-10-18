# W27 rulings before the first canary — design lane (`specifier`), one pass

Worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m07-w27`, branch `wp/M07-w27` @ `273ab0f` (pushed; from
`wp/M07` @ `958b983`). Registration `docs/derivations/M06-W27-registration.md` (§17 Q3/Q5, §20–§22; W27-R31, R56, R58,
U14 / R-194), M07 spec `docs/derivations/M07-spec.md` §9 and M07.A50 (l.381). Runbook `docs/briefs/W27-runbook.md`; the M06
build-decisions log's latest entry (readiness WO). Frank approved the registered 45-run campaign, USD 15–45
(`docs/V02_DECISIONS.md:191`). Nothing has been spent; no real session has run.

## Measured readiness (`273ab0f`)
Live snapshot = `hypothetical_v02_a3` model for model, route for route; live coverage = committed `coverage.json`
(0 CANDIDATE of 450, 0 class/reason differences); 22 `model_functions`, the three reactors perform none
(`fixed_design_reactor`, `synthetic_stand_in`, `surrogate_model`). Stub dry run exits 0: P1–P5, P8 pass; P6, P7 need real
canaries; G14, G15 (20 states), A23 pass. New CLI `python -m benchmarks.m06.w27.harness {canaries,preflight,campaign,spend}`
(`27fb4b8`); spend ceiling (`8e6d80b`): campaign stops before a run whose USD 5 cap could take recorded spend past USD 45.

## Rule on (the engineer stopped on each; the registration does not settle them)
1. **U14 rewrite for campaign records:** `benchmarks/t08/support_envelope.yaml:439-442` U14 reads "No comparison is run
   (W27's campaign is M07's, R-175)" (R-194 text); `test_u14_…` fails on any path under `runs/`, so campaign records cannot
   be committed. Write U14's new text and what its test asserts.
2. **Order:** M07.A50 = coverage at C_W, canaries, draw, runs (checked by record timestamps). W27-R31 defines canaries as
   cases not in the sample, so the draw must precede the canaries. Which order; restate A50 or R31.
3. **Records without a writer/format:** W27-R58's `confirmation/` record of an empty candidate set (coverage has 0
   candidates), and the record that preflight passed (W27-R56). Specify path, members, and which check reads them.
4. **Re-canaries:** §9 allows up to three re-canaries (Q3); P6 counts exactly three canary directories. Specify layout and
   P6's rule with re-canaries.
5. Model (for the record, no ruling needed unless you disagree): registration l.378 — the most recent model is read from
   the first canary's `init` message (the CLI's default, no `--model`) and pinned by exact id for every later run.

## Deliverable
Registration Amendment 4 (dated section, before any W27 run), register entries (next free numbers above R-466 unused on
`origin/main`, `origin/wp/M07` and here), generator + regenerated `registration.json` if its members change (pre-existing
members byte-identical; update preflight P2 pins in the same commit as the build lane would — or list them for the
engineer), restated assertions. Commit, push `wp/M07-w27`. Use `PYTHONPATH=$PWD/src` for any test. Report ≤ 200 words.
Keep context under ~100k; read narrowly.
