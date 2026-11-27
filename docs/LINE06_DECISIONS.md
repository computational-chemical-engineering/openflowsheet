# LINE06 decisions log (append-only; grep it, never read it whole)

Each entry: date, what, the evidence or numbers, and for a choice `DECISION: <question> -> <choice>. Alternative: <x>.
Reversible by: <how>.` Package build decisions go in the package's own file (`docs/F2_DECISIONS.md`,
`docs/F8_DECISIONS.md`, `docs/X06_DECISIONS.md`).

## 2026-11-26, planning (orchestrator, OpenFlowsheet-TR09)

- The user asked how big 0.6 is. Answer given: about 80 work orders, 6 to 9 weeks, 25 to 45M tokens (extrapolated from
  F1 7 WOs in 14 h and F3 6 WOs in 2.5 days); the cut 0.6 = F2 + F8 + X06 offered. The user: "Clean up before you
  start. Remove worktrees that are not more needed anymore and stale background tasks. Then let's go for 0.6 = F2 + F8
  + X06. Update plans for this, create release/lines/0.6.json, prepare the campaign. Post decisions you need on the
  Decision Desk."
- Cleanup: 20 secondary worktrees removed (12 under `.claude/worktrees/`, the codehealth base `799f81c9`, 7 detached
  scratchpad checkouts), each clean (`git status --porcelain` empty) and its HEAD in `main` or on a kept branch
  (wp/REL050 6 commits, wp/S19 4, wp/S19-g1o8 3, wp/S19-g3 1, wp/SP 4 ahead of main; branches kept). No process had its
  cwd in one except the S19 gate queue. Stopped: shells bl74emye7, b38vr9tj3, b5mg2pgtc, b2l7k77a7 (S19 waits, 5 days
  old) and the gate-queue runner PID 4039086 (queue idle since job 702, 2026-11-21; runner.log "RUNNER stop").
- Merged into main (docs only, no conflict by `git merge-tree`): wp/REL050 (754cd194: REL050_DECISIONS, REL050_STATE)
  and wp/S19 (e85424c1: S19 close note, log, state, rules).
- DECISION: campaign name -> LINE06. Alternative: V06 or L06 (both already used as labels in the repo). Reversible by:
  renaming the files.
- DECISION: F8's 0.6 share -> WO1 to WO3 and WO5. Reason: ADR 0067's table, WO4 after F4-WO4, WO6 after F6-WO4, WO7 in
  TX. Alternative: F8 whole (needs F4 and F6). Reversible by: an R-1070 amendment.
- DECISION: X06's ADR number -> 0078 (next free after 0077). Reversible by: renumbering before it is written.
- DECISION: the packages that leave 0.6 -> a heading "After 0.6" with their numbers unchanged until card
  `ofs-line06-rest`. Alternative: apply default A (renumber 0.7 to 0.9) now. Reversible by: one roadmap edit.
- Line file: `release/lines/0.6.json` generated from 0.5's; `changed` = 9 fields; `load_line` + `line_problems`: no
  problems; `line_release('0.6', covers)` = 0.6.0. Tests: test_rel_release_gate, test_rel_evidence_manifest,
  test_rel050_ledger, test_rel051_ledger, test_v02_main_version, test_readme_current 135 passed; test_m07a_rc_records,
  test_m07a_v0_2_gate, test_msg_docs, test_rel_standing_acceptances, test_m03_schemas 271 passed.
- F0 on main d00f659a (after the two log merges and the planning commit): PASS, M1 50/50, M2 61/61, M3 61/61, M4
  61/61, M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 42/42 (`~/.cache/line06/f0-main.log`).
- hub filed the three cards (ofs-line06-rest, ofs-line06-adr-clause, ofs-line06-x06-scope), open; hub agrees with A
  on each. A correction sent first: x06-scope B no longer claims a work-order count (X06 has no ADR).
- P1 (F2 premise check) PASS: every existing file and symbol ADR 0062's work orders name resolves on main after S19
  and F3: `schemas/units.json`, `thermo/__init__.py` (`Phase` :58, `StreamState` :105, `PropertyRequest` :133),
  `thermo/cache.py`, `registry/builtin/`, `scripts/registry_builtin.py`, `run/solution_state.py`, `run/identity.py`
  (`r0_projection` :65), `application/revisions.py` (`content_hash` :51), `models/revision_flowsheet.py`
  (`ComponentBasis` :104), `docs/interfaces-frozen.md`, `records/model.py:30` and `records/validate.py:135` (the `kg`
  gate). New modules (`material/`, `revision_v2/`, `tests/f2/`) do not exist yet, as expected. Open for WO6's brief:
  "dispatch in the application layer" names no file; locate it then (recon).
- Worktree `.claude/worktrees/f2`, branch wp/F2 at d00f659a. Brief `docs/briefs/LINE06-F2-WO1.md`.
- 2026-11-26: the user: "go". opus-engineer launched on F2-WO1 (background, worktree f2).
- 2026-11-26 ~20:50Z: hub's doorbell; the three cards fetched (decisions/<id>, keys) and verified with
  `decision_desk_verify.py` against the exact action texts sent: ofs-line06-rest VERIFIED A (signed 20:39:40Z),
  ofs-line06-adr-clause VERIFIED A (20:39:05Z), ofs-line06-x06-scope VERIFIED A (20:39:22Z), key 032ee0a5ae620a90.
  Applied: roadmap.md (0.7 multiphase core, 0.8 dynamics with ADR 0066, 0.9 toolkit, 0.10 batch; 0.7 acceptance ADR
  0063-0065; freeze point end of 0.7; "Swap 0.8 and 0.9"), ADR 0057 D6 note and Amendment 3 "Settled", R-1070
  "Settled", ADR 0062/0067 line notes "0.7". `executed` written on the three cards (versions 3, 3, 4).
- D1 brief `docs/briefs/LINE06-X06-architect.md`; worktree `.claude/worktrees/x06`, branch wp/X06 at aa5822ac;
  `architect` launched (background). Facts given: R-110, C1/C6/C7, the note's "resume of long jobs through F7" (F7 now
  0.8, so resume is the expected deferral argument), F0 counts, no record or identity change.
- D1 judged PASS (2026-11-26): `architect` committed ADR 0078 Proposed alone on wp/X06 (`dcbab9b7`, 436 lines),
  worktree clean; 244,895 tokens, 88 tool uses, 18 min. All five parts designed; resume deferral to F7 D14 (0.8)
  argued (D3); 5 WOs (4 Opus, 1 Sonnet), 24 exits. Spot-checks: `refs` table exists (`application/store.py:90`);
  `mcp==1.30.0` in requirements.lock:21. Open: Q1-Q6 (user), Q4 fact (MCP clients), Q7-Q9 facts measured by WOs.
  Applied: R-1071 (Proposed), roadmap X06 row. Held until Q1 is answered: R-110 status line, roadmap resume move,
  target-architecture X06 row.
- X06-WO1 brief `docs/briefs/LINE06-X06-WO1.md`; opus-engineer launched (background, worktree x06). Cards requested: ofs-x06-accept-adr0078 (A: accept with Q1-Q3, Q5, Q6 defaults), ofs-x06-mcp-clients (A: static bearer, OAuth later).
- hub filed ofs-x06-accept-adr0078 and ofs-x06-mcp-clients (open; hub agrees with A). Card 1 A's action text is pinned
  to the commit; verify with exactly: "Accept ADR 0078 as written at dcbab9b7 with its defaults: Q1 job resume deferred
  to F7 D14 (0.8); Q2 in-band administration off by default behind a per-project operator switch; Q3 administration
  writes refused on a server bound beyond loopback, no override in 0.6; Q5 registering a solve policy needs the draft
  right; Q6 the seven benchmark-registered policies stay unsupported." If ADR 0078 changes after dcbab9b7 (an X06 WO
  must not edit it), tell hub before it is signed.
- F2-WO1 judged PASS (2026-11-26): 7 commits on wp/F2 (9431853b..ed5fb6c0), worktree clean; 238,800 tokens, 31 min.
  E-F2-1: 99,538 StreamStates from F0's 61 corpus runs (21,903 distinct) round-trip bitwise; phase-id E-F2-5: 10^4
  generated, 7,169 distinct renderings, render/parse inverse; kg branches flipped; battery 2440 passed, 1 skipped, 3
  xfailed; ruff, mypy src clean. Orchestrator re-runs: tests/test_f2_material_types.py 44 passed; F0 on wp/F2 PASS,
  M1 50/50, M2-M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 42/42 (unchanged from main).
- STOP WO1-4 accepted as correct: widening `PropertyRequest.state`/`.phase` (ADR 0062 D2) gives 51 mypy errors in 7
  M9-frozen legacy providers; not applied. Batched for F2's ruling round with the engineer's flags WO1-1 (only
  `segment_molar_mass` bounded > 0), WO1-9 (formation kinds per amount basis) and "M = 1 for kg records in reaction
  checks". Defaults: (a) a v2 request type in F4; the rest as built.
- F2-WO2 brief `docs/briefs/LINE06-F2-WO2.md`; opus-engineer launched (background, worktree f2).
- **MISS, F2-WO1 (found by WO2's engineer, 2026-11-26):** WO1's 14 quantity kinds moved the served interface; 16 tests
  fail at ed5fb6c0 (5 test_t07_w5e: list_models 854fab33 vs snapshot 12d88245; 11 test_t08_w2_surface_digest: served
  9a4b4eb3 vs registered f7ec3c94). Confirmed by the orchestrator: 16 failed, 33 passed. Cause: the WO1 brief's
  acceptance named no surface suite and the orchestrator's judgment did not run one; F0 does not read the served
  digest. WO1's verdict stands corrected: PASS on its five items, FAIL on "existing suites green". Fix: F2-WO2b
  (register the move, F3 pattern). Rule added to LINE06_RULES: every WO runs tests/test_t07_*.py and
  tests/test_t08_w2_*.py and registers any served-digest move itself.
- F2-WO2 judged PASS on its four items (2026-11-26): commits 1529859b, 88cc22b8, worktree clean; 276,450 tokens, 28
  min. E-F2-7: tests/test_f2_basis.py 41 tests against an independent generator
  (docs/derivations/scripts/f2_basis_reference.py, 67 claims; Q3.R7 worst 0.43 eps, margin 9.2x); 9 template/family
  SHA pins (nTP-v1 d0a6d025 unchanged); registry_builtin --check clean, 57 descriptors in 4 tables, registry_sha256
  6a7550d4 -> 844d9ba7 (by design; legacy/core/records tables byte-identical); 938 passed; F0 unchanged. Orchestrator
  re-runs: tests/test_f2_*.py 186 passed; registry_builtin --check clean. Design-lane flags batched for F2's ruling
  round: WO2-1 (Q3.R1 (iii) rational lambda per group row), WO2-7 (templates in a new table material.json, payload
  {instance_schema}); WO2-8 kinds not marked core while ADR 0062 is Proposed.
- F2-WO2b brief docs/briefs/LINE06-F2-WO2b.md; opus-engineer launched (background, worktree f2).
- X06-WO1 judged PASS (2026-11-26): 7 commits on wp/X06 (ce0efbdd..203f7e97), worktree clean; 276,592 tokens, 62 min.
  E-X06-1 (six-client conformance, 36 passed, McpHttpClient 80 steps 11.3 s), E-X06-2..5 (test_x06_mcp_http 25
  passed); battery 2501 passed, 28 skipped, 3 xfailed (incl. t07, mcp/http, MSG, surface digest); catalogue sha
  re-taken 9ac09855 -> a767cab0 for origin_refused (F3 precedent). Q9 on mcp 1.30.0: batch 400/-32602; wrong Accept
  406/-32600; text/plain 400; bad protocol version 400/-32600; non-JSON 400/-32700; notification 202; tools/call
  without initialize 200 and runs (stateless, authenticated). Orchestrator: ADR 0078 unchanged since dcbab9b7 (card
  pin holds); test_x06_mcp_http + t08_w2_surface_digest + t07_w5e 74 passed; F0 on wp/X06 PASS, counts as main.
  For the X06 reviewer: WO1-1 (http.serve and web.serve no longer used by the CLI: remove?), the uninitialized
  tools/call in stateless mode.
- X06-WO2 brief docs/briefs/LINE06-X06-WO2.md; opus-engineer launched (background, worktree x06).
- F2-WO2b judged PASS on its brief (2026-11-26): 7b2a995c; 132,096 tokens, 31 min; the 16 tests green
  (test_t07_w5e + test_t08_w2_surface_digest 51/51 with two decomposition tests); families 4017 passed, 0 failed; F0
  unchanged. Pins: F2_SERVED_SHA256 9a4b4eb3 (without_f2 -> F3's f7ec3c94), SNAPSHOT_F2 list_models 854fab33 (-> 12d88245).
  Found: tests/test_m07a_surface_chain.py 18 failed (confirmed: 18 failed, 65 passed across the three files), a
  third surface suite the WO1 rule did not name.
- DECISION: chain links -> F2 c_11 (R-1072), X06 c_12 (R-1073), reserved now in the register; renumbered in the
  second merge if X06 merges first. Alternative: allocate at merge time. Reversible by: renumbering in m07a_rc.py.
  Rule widened to tests/test_m07a_surface_chain.py. X06-WO2's engineer told by message to add c_12 in WO2.
- F2-WO3 brief docs/briefs/LINE06-F2-WO3.md (first commit c_11, then D7/D8); opus-engineer launched (background).
- F2-WO3 report (2026-11-27): commits ee0e145d, 70c1aaec, baf4bd11, 41177bcf; 221,708 tokens, 55 min. Chain suite 34
  passed (18 failed before); E-F2-5 ids 10^4 structures, 8,756 distinct, none equal to 37,457 legacy ids; E-F2-6 3,514
  states / 59,935 slots bitwise, three planted orderings caught; WO2b residue fixed in test_m02_schemas g1c and
  test_m04_study_job a42. The engineer did not rerun the whole named set after that fix: the orchestrator runs it
  (battery-f2-wo3, with F0). DECISION WO3-1 (R-1072 copied onto wp/F2 with evidence, ee0e145d): accepted; at F2's
  merge the register block is resolved to main's R-1071..R-1073 plus wp/F2's evidence row. WO3-6 joins the ruling
  batch. F2-WO4 brief written (docs/briefs/LINE06-F2-WO4.md), launch after the battery.
- 2026-11-27: hub's doorbell; cards verified: ofs-x06-accept-adr0078 VERIFIED A (signed 2026-11-26T23:14:33Z, the
  pinned text "at dcbab9b7"; ADR 0078 unchanged at wp/X06 head, `git diff dcbab9b7 HEAD` empty), ofs-x06-mcp-clients
  VERIFIED A (23:15:29Z). Applied on main: R-1071 Accepted with both action texts, R-110 status line, roadmap X06 row
  (resume removed) and F7 row (resume from X06), target-architecture X06 row. `executed` written (versions 3, 3).
  Pending: ADR 0078's status line on wp/X06 after X06-WO2 ends (no commit into a worktree an engineer is using).
- X06-WO2 judged PASS (2026-11-27): commits 30f3aac2, 8e7b818d, 2213296b, 46001a81; worktree clean; 393,571 tokens,
  80 min. test_x06_branches 22 passed (E-X06-6, 8 with 20 trials x 3 races in threads and two processes, falsifier
  shown, 9, 10); test_x06_change_set_golden 3 passed over 303 recorded ChangeSet requests (WO2-1: from benchmarks/
  transcripts at aa5822ac, no tests/fixtures file validates as a ChangeSet); E-X06-22 X06_SERVED_SHA256 7e8393a5 ->
  without_x06 = F3's f7ec3c94; chain c_12 (R-1073) 37 passed; battery 3321 passed, 1 failed = the description-review
  gate test_t08_w2_description_reviews (T08.A18: design-lane AND human review of every MCP text, red until recorded):
  five texts (commit_change, preview_change, list_branches, create_branch, delete_branch). Orchestrator re-run:
  test_x06_branches + golden + chain + t08_w2_surface_digest 73 passed; F0 on wp/X06 at 7ca42a0e running
  (f0-x06-wo2). For the X06 reviewer (ruling): WO2-4 (commit_change re-prepares when a commit on another ref took its
  auto-assigned id; a commit-path behaviour change), WO2-7 (commit_change.md tightened to fit 1500 chars).
- DECISION: description reviews -> batched once at X06 close-out (design lane in X06's reviewer pass; the user's
  review by one card listing every new or changed text with its hash). Alternative: per WO. Reversible: anytime.
- ADR 0078 status line set Accepted on wp/X06 (7ca42a0e, status line only). R-1073 evidence row filled on main.
- X06-WO3 brief docs/briefs/LINE06-X06-WO3.md written.
- 2026-11-27: f0-x06-wo2 PASS on wp/X06 7ca42a0e (F0 PASS: M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61,
  M6 85/85, M7 52/52, M8 105/105, M9 42/42). X06-WO3 launched (opus-engineer, brief docs/briefs/LINE06-X06-WO3.md).
- 2026-11-27: F2-WO3 judged PASS at wp/F2 41177bcf: battery 5070 passed, 28 skipped, 3 xfailed, 0 failed; F0 PASS
  (M1 50/50 ... M9 42/42, unchanged). F2-WO4 launched (opus-engineer, docs/briefs/LINE06-F2-WO4.md).
- 2026-11-27: X06-WO3 judged MISS on two acceptance items, both correctly stopped (no check relaxed): E-X06-13
  (xfail strict: `run.bundle._cross_check_solve_path` resolves `policy_requested` by name, Q7) and
  `test_t07_q26_no_external_state` (`register_solve_policy` `policy/scales` numeric map, no R-088 Q26 exception).
  Rest: E-X06-11, -12, -14, -15, -22 pass (17 passed, 1 xfailed); surface battery 2696 passed / 5 failed at 7dd78915,
  3 fixed in 6562cc1a; description-review gate red by design (7 texts); ruff, mypy clean; F0 PASS at 7dd78915.
  Head wp/X06 c526de6a. Both touch replay identity / an R-088 exception, so not batched:
  DECISION: one fresh `architect` pass for both rulings now (brief docs/briefs/LINE06-X06-R1.md), then a small fix
  WO; X06-WO4 waits for it. Alternative: batch into X06's reviewer pass. Reversible by: none needed (advice only).
- 2026-11-27: X06-R1 (architect) ruled, wp/X06 313907cd: Q7 -> a `user.` bundle judged on its own
  solve-policy.json, store never consulted (R-1074); Q26 -> `policy/scales` admitted by full path, 39 scalars pinned
  (R-1075). Both clarify Accepted ADR 0078; no user card (F3's R-1058 form). New find: `is_project_policy_id` needs
  fullmatch. X06-WO3b brief written (docs/briefs/LINE06-X06-WO3b.md), launched on opus-engineer.
- 2026-11-27: X06-WO3b judged PASS at wp/X06 4ca7ce3c: test_x06_solve_policies 22 passed 0 xfailed; test_t07_q26
  6 passed (spot-check rerun of both files: 28 passed); bundle gate 63/60/b42b1ec439d1683c unchanged; surface 2619
  passed, 1 failed (description-review gate, by design), 3 xfailed (pre-existing); ruff, mypy clean; F0 PASS.
  WO3b-1 (40th scalar `policy/admissibility_epsilon`, the ruling counted 39) goes to X06's reviewer batch; R-1075 text
  amended to say so. For WO5: E-X06-13 optimize half `not run` (no nlp extra). Code-health item S2: an
  AttributeError escapes `reproduce` on a named bundle (to file with code_health). X06-WO4 brief written, launched.
- 2026-11-27: X06-WO4 stopped at the context cap (not a miss; incomplete): wp/X06 ac15a44a, code in a84e9b14, CLI
  audit fixture a9038f7b, DECISIONs WO4-1..7, handoff "Where WO4 stopped". Q26 STOP (batched to X06 reviewer):
  grant_capability limits/{default_wall_time_s,max_wall_time_s,max_active_jobs}, set_ambient_pressure value. Found:
  render_error prints explain's "no message code" text when a message lacks its code prefix (WO2-WO4 carry it; check
  in review). X06-WO4b (continuation) brief written, launched.
- 2026-11-27: F2-WO4 judged PASS with one recorded exception, wp/F2 d14e7ce7: E-F2-2 pass; E-F2-8 pass; E-F2-9
  19 of 20 codes (`state_degenerate_in_definition` needs F5/F6 property evaluation, WO4-9; named in the coverage
  test) -> recorded as a partial miss, to F2's ruling batch; battery 5596 passed, 0 failed; F0 PASS. Orchestrator
  spot-check: test_f2_revision_v2 107 passed, F0 PASS (same counts). Design-lane items for F2's batch: WO4-7 (D10 vs
  Q7.R5, mass input on a mol amount refused), WO4-8 (Q8.A6's code), WO4-9, WO4-15 (which substream fixes T).
  WO4-16: 18 minimal catalogue entries added ahead of WO7 (doc pages and two message_entry digests re-pinned).
  Incident: F2-WO4 and X06-WO4b shared the prior session's scratchpad; X06-WO4b warned to re-run any result from
  battery.sh/pytest.log/f0.log there. Rule for briefs from now: logs under ~/.cache/line06/<wo>/.
  F2-WO5 brief written (docs/briefs/LINE06-F2-WO5.md), launched.
- 2026-11-27: F2-WO5 judged PASS, wp/F2 f4c5cd7a (no src change): E-F2-4 13 tests (worst conservation 3.39e-16;
  Q6.A5 worst deficit 6.27e-16; O-9 worst moment deficit 4.86e-14, margin 20.6x to tau_mono 1e-12, above 10x);
  Q7.A2 and E-F2-6 on 300+ probe states bitwise; battery 5609 passed 0 failed; F0 PASS. Spot-check:
  test_f2_probes 13 passed. To F2's ruling batch: Q-WO5-a (Q6.A2 registration half untestable: no lambda1 field,
  no F1 check) -> recorded partial; Q-WO5-b (`validate.py` one_definition_rules compares definition ids, refuses
  equal-bodied distinct ids as attribute_grid_mismatch; possible src defect); Q-WO5-c (underflowed flowing stream,
  for ADR-F6); WO5-1 (probe kind scopes swapped in WO3/WO4 test data). Process: run.sh PIDs are invisible to kill -0
  from another shell; wait on the log line.
- DECISION: F2-WO6 split into WO6a (lower/raise, solution-state-v2 writer, r0_projection for v2, E-F2-3 library half,
  E-F2-10, a dispatch map for WO6b) and WO6b (Amendment 9 application dispatch, run submission, E-F2-3 run half, ADR
  0019 pointer, interfaces-frozen). Alternative: one WO (would exceed the 150k cap). Reversible by: merging briefs.
  F2-WO6a brief written; launched once F2-WO5's own background run in the f2 worktree has ended.
- 2026-11-27: X06-WO4b judged PASS, wp/X06 af8a6c32: test_x06_administration 15 passed (E-X06-16..21; spot-check
  rerun 15 passed); E-X06-22 X06_SERVED_SHA256 = D_12 = d0f0c8b7..., without_x06 = f7ec3c94...; surface 2375 passed,
  2 failed (Q26 STOP: set_ambient_pressure value, grant_capability limits/{max_wall_time_s,max_active_jobs,
  default_wall_time_s}; description-review gate: 11 texts, 22 open reviews), x06/MSG/doc pages 276 passed 3 xfailed;
  ruff, mypy clean; bundle gate 63/60/b42b1ec439d1683c; F0 PASS. For the reviewer: WO4b-1 removed
  test_u08_no_operation_administers_policies (D5 reverses it; WO2-9 precedent); WO4b-2 E-X06-16 on operator-written
  policy files. Test isolation defect (_pin_threads leaks env) -> X06-WO5 item 7. X06-WO5 brief written (Sonnet).
- 2026-11-27: X06-WO5 judged PASS, wp/X06 020b7b72 (manifest at a657d29d, status tested): surface one process 3318
  passed, 2 failed (exactly Q26 and the description-review gate), 3 xfailed; F0 PASS; ruff clean; E-X06-23 store id
  t07-store-v1, three schemas changed, each justified; E-X06-24 12 codes catalogued. WO5-1 fixed _pin_threads in
  three tests. All X06 WOs done. X06 reviewer brief written (docs/briefs/X06-reviewer.md) with the ruling batch;
  reviewer launched.
- 2026-11-27: X06 reviewer pass (docs/reviews/X06-review.md, main 3f457172): not ready; M1 remote-refusal bypass
  (unused `bindings.http.serve` / `bindings.web.serve` serve in-band writes without `serving_remote`; confirmed
  http.py:456 exists), M2 envelope still says MCP over HTTP unsupported; S1 TOCTOU in in-band writes, S2 token-leak
  test REST only, S3 E-X06-13 optimize half has no test. Rulings: Q26 four scalars admitted by full path; 8 texts
  approved, 3 with exact edits; WO3b-1 keep; WO4b-1 change (restore U08 test re-scoped); WO4b-2, WO1 stateless,
  WO2-4, WO5-1 keep; serve functions removed; render_error -> code health. No Accepted ADR decision changed.
  X06-fix1 brief written (S3 to run in .venv-nlp), launched.
- 2026-11-27: X06-fix1 judged (wp/X06 487609e7), pending the orchestrator's battery rerun: items 1-7 done (M1 serve
  functions deleted; M2 envelope/U08 re-scoped, ruling 4 test restored; Q26 6 passed; three text edits at the
  review's hashes, design-lane reviews recorded, human pending; S1 caller re-resolved in the transaction, 8 hook
  cases; S2 per-carrier grant; S3 optimize half run in .venv-nlp: 1 passed, KKT_POINT_VERIFIED, MATCH). New served
  digest 7792576e...; without_x06 f7ec3c94...; bundle gate unchanged; F0 PASS. Engineer's battery at 1a2782d1 had
  two extra failures (A21, A50, from WO5's manifest lacking harvest rows), fixed in 487609e7 but not re-run in full:
  orchestrator reruns surface suites + F0 at 487609e7 (log ~/.cache/line06/x06-fix1-battery.log).
- DECISION-REQUEST to hub: card for the user's review of the 11 X06 description texts at their hashes
  (docs/reviews/X06-descriptions-for-user.md). CI and the merge card follow it (the review gate is red until then).
- 2026-11-27: X06-fix1 judged PASS on the orchestrator's rerun at wp/X06 487609e7: surface suites + doc pages +
  evidence manifests in one process 3333 passed, 47 skipped, 1 deselected (nlp-marked), 3 xfailed, 1 failed (only
  the description-review gate, the user's 11 items); F0 PASS (M1 50/50 ... M9 42/42). Card
  ofs-x06-descriptions-human filed by hub (open). Next for X06: on VERIFIED A, record the human reviews in REVIEW.json,
  rerun that test, push wp/X06 for CI, merge card.
- 2026-11-27: F2-WO6a judged PASS, wp/F2 f9a415f1: E-F2-3 library half 59/59 (M1's 50 + F0's 9 basis cases),
  construct refusals 93 tests; E-F2-10 35 tests; battery 5737 passed 0 failed; F0 PASS. Spot-check: both new files
  128 passed. WO6a-2 (D12 component-order reading; literal reading refuses STA04 and every CoolProp revision) and
  WO6a-3 (unclassified D11 fields refused) touch D12, frozen core (D13): not batched.
  DECISION: one fresh architect ruling pass F2-R1 now (brief docs/briefs/LINE06-F2-R1.md) beside F2-WO6b (brief
  docs/briefs/LINE06-F2-WO6b.md), which builds on the current reading. Alternative: hold WO6b. Reversible by: a fix
  WO after the ruling.

- 2026-11-27: resumed after self-reset; launched architect F2-R1 (D12 rulings) and opus-engineer F2-WO6b in .claude/worktrees/f2 (logs ~/.cache/line06/f2-r1, f2-wo6b). Card ofs-x06-descriptions-human still open.
- 2026-11-27: F2-R1 judged PASS (2781db50 touches only docs/F2_DECISIONS.md; rulings WO6a-2 keep, WO6a-3 keep + parameter_sets/thermal_coordinate amendments, WO6a-4 confirmed). Fix WO F2-WO6c briefed (docs/briefs/LINE06-F2-WO6c.md), launches after WO6b. D12 text to apply to ADR 0062 after WO6b (F2_DECISIONS.md "D12 text to apply"). ADR 0062 card gets the R1 line (open item 2); validate/h_mass to the F2 reviewer (item 1).
