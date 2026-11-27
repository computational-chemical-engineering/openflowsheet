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
- 2026-11-27: F2-WO6b judged PASS at b417eae3 (orchestrator rerun: tests/test_f2_amendment9.py + test_f1_draft_admission.py 249 passed; F0 PASS M1 50/50, M2-M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 42/42). For WO7: check_admission description re-pin (WO6b-6), an optimization-job-on-v2 test. ADR 0062 D12 replaced per F2-R1 (wp/F2 df796cc2). F2-WO6c launched (opus-engineer, log ~/.cache/line06/f2-wo6c).
- 2026-11-27: P8, F8 premise check on wp/F2 at df796cc2 (ADR 0067 D1-D7, WO1-WO3, WO5):

  | Named | Status |
  | --- | --- |
  | `run/bundle.py`, `run/replay.py`, `run/identity.py`, `run/manifest.py` (`NON_STRUCTURAL` l.65, `verify_bundle`) | exist |
  | `run/{manifest_v2,bundle_v2,replay_v2,platform_refs}.py`; schemas `records-index`, `run-evidence` | absent, to be created by WO1-WO3, WO5 (as designed) |
  | schemas `run-manifest`, `replay-report`, `data-lock`, `registry-snapshot` | exist |
  | ADR 0060 D10 snapshot: `registry/snapshot.py` `snapshot_document`, `registry_sha256`; `Registry.snapshot`, `extensions_used` (l.681), `usage()` (l.824) | exist |
  | ADR 0061 D11 embedding: `records/rights.py` `embeddable` (l.215); `RecordStore.object_bytes/record/add` | exist |
  | catalogue `data_unavailable`, `store_object_corrupt` | exist; F8 codes (`bundle_format_unsupported`, `extension_*`, `platform_reference_used`, `record_referenced`, ...) absent, WO1-WO3 add them |
  | `MaterialModel.entries_read`, `EntryRead` (D6) | absent: F4-WO4 builds it; consumer F8-WO4 is out of 0.6. Not needed |
  | `job_operation: run`, `run_kind`, `documents` (ADR 0066 D10/D11) | absent: ADR 0066 is 0.8. WO1 defines the manifest members as optional schema members only; no 0.6 run fills them |

  Resolved: 0 open rows. Note for the F8 briefs: in 0.6 no production run writes a v2 bundle (v2-compiled runs come with F6/WO6, 0.7); WO2's test-only factory is the only writer, so E-F8-2..6 run on factory bundles.
- 2026-11-27: F2-WO6c judged PASS at 2d19b5f8 (orchestrator rerun: test_f2_lowering + test_f2_amendment9 220 passed, test_t07_global_state 3 passed; F0 PASS all nine). Raised s10 v2 content_hash moves logged by the engineer (unpinned). F2-WO7 briefed (Sonnet; check_admission.md re-pin kept out, goes with the reviewer pass).
- 2026-11-27: F2-WO7 judged PASS at 9d2fbe6c (orchestrator: test_msg_* + test_t07_w5e 224 passed, 3 xfailed; manifest evidence/F2/a3081770.../manifest.json `tested`). Its finding WO7-3 (optimize_revision did not lower: run ids and revision.json differ, D8) fixed by the orchestrator, wp/F2 39244e80 (WO7-4; nlp 7 passed). Known red on wp/F2: test_v03_semantic_roles a29, a31_a, a31_b (V03 A29/A31 vs D12) -> F2 reviewer batch item 1.
- 2026-11-27: F8-WO1 judged: committed part PASS (wp/F8 6209110b..1b7e1b51; test_f8_manifest_v2 34/34; F0 PASS; 2936 passed, 3 failed = the v03 reds, F2's), STOPs 8 and 9 correct (served digests move). R-1076 registers F8's surface link c_13 (main 2e74d07f). F8-WO1b briefed. F2 reviewer briefed (docs/briefs/F2-reviewer.md). F8-WO1-1 (schema structure via bundle-v2 $ref) is for the F8 reviewer.
- 2026-11-27: F2 review (05dd3392): not ready, one fix round; 2 M (M1 find_source does not lower the ancestor: D8 broken on continuation; M2 V03 red), 9 S, 7 N. Rulings: V03 tests change (code kept); h_mass revision-wide; check_admission.md approved (human review back to pending); 7 catalogue entries corrected; WO2-7, WO4-15, Q-WO5-b changed; WO1-4 kept with D2 amended. F2-WO8 (12 items) briefed. ADR 0062 card line in the review, section "What needs the user".
- 2026-11-27: F8-WO1b judged PASS at ddac950f (orchestrator: surface chain + w5e + surface digest + f8 manifest 123 passed; F0 PASS). D_13 `c11d3877…` decomposes onto F2's `9a4b4eb3…`; 9 R4-G3 snapshots re-pinned with `without_f8`. R-1076 evidence mirrored to main. Note: F2-WO8 item 9 moves F2's c_11 digest, so wp/F8 re-decomposes onto F2's new D_11 when it merges wp/F2's head. Left: ADR 0019 Amendment 12 pointer (F8 close-out).
- 2026-11-27: card ofs-x06-descriptions-human VERIFIED A (key 032ee0a5ae620a90); human review recorded for the 11 texts in REVIEW.json (wp/X06 1b9561a3; test_t08_w2_description_reviews 1 passed); executed written (card v3). wp/X06 pushed for CI (runs ci 45962988409, Site 45962988390; waiter ~/.cache/line06/ci/wait_runs.sh, log ~/.cache/line06/ci/x06-1b9561a3.log). On green on all legs: X06 merge card via hub.
- 2026-11-27: F8-WO2 judged PASS at 886113ea (orchestrator: test_f8_bundle_v2 + manifest_v2 55 passed; F0 PASS). Factory cases GP-C1, TH-C1; E-F8-3 referenced records via the test-only project rights rows (WO2-4). F8-WO3 briefed (step-7 premise check: rerun of a v1 document does not read the store).
- 2026-11-27: F2-WO8 judged PASS at 2bba85c3 (orchestrator: test_f2_* + V03 + surface chain 622 passed; F0 PASS). D_11 moved 9a4b4eb3 -> 8eee5313 (item 9; strip_f2 -> D_10 f7ec3c94). ADR 0062 D2 and D11 edited per the review (wp/F2 a64f93fb). DECISION-REQUESTs to hub: ofs-f2-accept-adr0062 (A: accept as corrected, push wp/F2) and ofs-f2-check-admission-human (A: record human review at f111234f).
- 2026-11-27: F8-WO3 judged PASS at 25e5ed36 (orchestrator: test_f8_replay_v2 + k05_replay + t07_w5e 107 passed; F0 PASS). E-F8-1: 52 bundles byte-identical vs pre-F8 reports at ddac950f (tests/fixtures/f8/v1-replay-reports.json). Step-7 premise DECISION F8-WO3-1 (not STOP): a v1 rerun reads packaged YAML; served_stack serves embedded records first but has no v1 consumer; flagged for the F8 reviewer. Catalogue digest on wp/F8 2b227092 -> 4ca46ea4 (wp/F2 moved it to 3af0a794: conflict at the F2 merge into wp/F8; re-pin then). Ruling batch for the F8 reviewer: WO1-1, WO3-1 to WO3-10.

- 2026-11-27 **F8-WO5 judged PASS** (wp/F8 `dcf4b89f`, `sonnet-implementer`): `tests/test_f8_platform_refs.py` 19
  passed (rerun by the orchestrator), battery 2674 passed / 28 skipped / 3 xfailed, F0 PASS (50/50, 61/61, 85/85,
  52/52, 105/105, 42/42), lint clean; catalogue digest `4ca46ea4...` -> `bbdcfb51...` (t07 w5e + doc pages 42 passed on
  rerun); invariant sweep finds 0 per-platform records in the repository (vacuous; synthetic cases carry it). Four
  mutation controls fail as intended. Before it: DECISION F8-WO5-0 (X07a errata E-D7-1..5 folded into ADR 0067 D7,
  `369150d3`). Open for the Opus review: F8-WO5-4 says a solver-counter change did not move R0 for GP-C1.
- 2026-11-27 **F8-WO5 Opus review judged PASS** (wp/F8 `a4b0ede1`, `opus-engineer`): no must-fix; three should-fix
  fixed (selection test exact, loader refuses misnamed/malformed records, invariant reports a missing reference);
  `tests/test_f8_platform_refs.py` 29 passed (rerun by the orchestrator); 178 passed on the F8/X07a/t07_w5e set; F0
  PASS. R3: `r0_projection` is correct (last-event `residual_calls`, `jacobian_calls`, `factorizations` +1 each move
  R0 on GP-C1; event 0 and property counters do not); no finding. R4: a v2-policy selection test added. For the F8
  reviewer: selection does not re-check `reference_sha256`; departures' values are not checked against the records.
- 2026-11-27 **F8 close-out judged PASS after an orchestrator fix** (wp/F8 `5406f812`): Amendment 12 pointer
  (`32981fb3`), manifest `evidence/F8/32981fb3.../manifest.json` tested (`2c0aed2e`); F0 PASS; f8 122, k05 30, x07a
  18, t07_w5e 39, msg 186 + 3 xfailed. STOP F8-CO-3 (harvest pin; brief forbade tests/) resolved by the orchestrator:
  7 P rows, `HARVEST_SIZE` (109, 1180, 150), DECISION F8-CO-4 (717 passed, 19 skipped). Found: `test_j16` red on
  wp/F2 (green on main): F2-WO4's flow-style fixtures; fixed on wp/F2 `6913c4a0` (DECISION F2-J16; F0 PASS). Hub
  amended card `ofs-f2-accept-adr0062` (v2): push wp/F2 at 6913c4a0 only if the local gate on it passes. Full local
  gate on 6913c4a0 started (log `~/.cache/line06/f2-j16/gate-6913c4a0.log`). F8 reviewer brief `docs/briefs/F8-reviewer.md`.
- 2026-11-27 **X06 CI failed** (run 45962988409 at `1b9561a3`, every check leg, default-install, codehealth, identity;
  Site green): 11 tests (sha256 partition names, literal guards, M02/M04 decompositions vs `list_branches`, q7 replay
  mode) and the codehealth diff (debt 59.30 -> 99.20, six smells). Fix order `docs/briefs/LINE06-X06-CI1.md`
  (opus-engineer). **DECISION (orchestrator): before any further push of a package branch, the full local gate
  (`scripts/gate.sh`) and `codehealth diff --base origin/main` pass on its head.** Reason: gate-by-risk let 11 reds
  through to a 2.5 h four-leg CI run. Alternative: per-risk only (the rule as written). Reversible by: dropping the
  step; it costs compute, not tokens.
- 2026-11-27 Card `ofs-f2-accept-adr0062` (v2, choice A) **VERIFIED** (signed 11:12:54Z, key 032ee0a5ae620a90). Plan:
  when the local gate on 6913c4a0 ends PASS, push wp/F2 at exactly 6913c4a0, start the CI waiter, then commit ADR 0062
  Status Accepted on wp/F2 (local, docs only, after the pushed head), then write `executed`. If the gate fails: no
  push; report to hub; `executed` records the partial result.
- 2026-11-27 **Rule amended (orchestrator): the codehealth diff does not gate a push.** CI's `codehealth` job is
  `continue-on-error: true` (informational, `.github/workflows/ci.yml:385-408`) and reads origin/main's
  `.codehealth/config.toml`, so a package that adds packages to the layer contract shows them as violations until it
  merges (F2: 11 `repo-layers` violations for `material`/`revision_v2`, which F2's own config places). The full local
  gate still gates every push. Codehealth findings are recorded and go to `code_health`: F2 `application/validation.py`
  large_file (nloc 1003); debt 171 -> 422 over F2's touched files. X06-CI1's refactors already made stay if its gate passes.
- 2026-11-27 Card `ofs-f2-check-admission-human` VERIFIED (A) and executed: review recorded on wp/F2 `8edbbaee`.
  Card `ofs-f2-accept-adr0062` executed PARTIAL: ADR 0062 Accepted on wp/F2 `831d6f26`; push withheld (gate on
  6913c4a0: 2 failed). F2 fixes since: `8edbbaee` (description review), `4b820b97` (w5_identity S2, DECISION F2-S2).
  Full gate on `4b820b97` running (log `~/.cache/line06/f2-j16/gate-4b820b97.log`, summary `.summary`).
- 2026-11-27 Card `ofs-f2-push-ci` (A) **VERIFIED** (signed 11:40:07Z, key 032ee0a5ae620a90): "Push wp/F2 at 4b820b97
  for CI, only if the local full gate on 4b820b97 passes." Waiting for the gate (summary
  `~/.cache/line06/f2-j16/gate-4b820b97.summary`); on PASS push exactly 4b820b97 (`git push origin 4b820b97:refs/heads/wp/F2`
  even if wp/F2 has moved), CI waiter, then `executed`.
- 2026-11-27 **F8-FR0 judged PASS** (wp/F8 merge `b3d73fce` of wp/F2 4b820b97, `00d094c0`; opus-engineer): 8 conflicts
  kept both sides; D_13 `c11d3877...` -> `3571c5c3f57abe2a...` (strip_f8 = F2's `8eee5313...`, strip_f2 of that =
  `f7ec3c94...`; only `get_job_result` moves); catalogue `3af0a794`/`bbdcfb51` -> `43687c797072dc45...`;
  HARVEST_SIZE (110, 1184, 154) measured; F0 PASS; all listed suites 0 failed; v03 reds gone. Orchestrator rerun:
  surface chain + digest + harvest 57 passed. Leftover (F2 docs, after F2's gate): ADR 0019 Amendment 9 (l.307) and
  `docs/interfaces-frozen.md:114` still name the old D_11 `9a4b4eb3...`.
- 2026-11-27 **F8-FR judged PASS** (wp/F8 `0c995c97..14409696`, opus-engineer, 9 commits): M1 and M2 fixed with
  tests (8 and 12; controls killed), S1-S6, Amendment 12 text, WO6 row (F8-FR-1), manifest re-taken at `18676313`
  (tested), HARVEST_SIZE (110, 1184, 153) measured; battery 13/13 steps exit 0; F0 PASS; no served digest moved.
  Orchestrator rerun: `test_f8_*` + harvest 165 passed. Not re-reviewed (the review's work order was followed as
  written). Full gate on 14409696 started in a detached worktree `.claude/worktrees/f8-gate` (summary
  `~/.cache/line06/f8-gate/gate-14409696.summary`). ADR 0067 acceptance + push card requested from hub.
- 2026-11-27 **F2 gate PASS on 4b820b97** (21725 passed, 107 skipped, 3 xfailed, 1:31:05). Card `ofs-f2-push-ci`
  executed: pushed origin wp/F2 = 4b820b97 (new branch). CI waiter: `~/.cache/line06/ci/f2-4b820b97.log`. Then on
  wp/F2 (local, docs only, after the pushed head): stale D_11 in ADR 0019 Amendment 9 and `docs/interfaces-frozen.md`
  corrected to `8eee5313...`, ADR 0062 Accepted there; tests reading them 522 passed. wp/F8 picks this up at its merge.
- 2026-11-27 Card `ofs-f8-accept-adr0067` (A) **VERIFIED** (signed 12:53:40Z, key 032ee0a5ae620a90). ADR 0067 and ADR
  0019 Amendment 12 marked Accepted on wp/F8 `4daff37f` (local, after 14409696). Push of exactly 14409696 waits for
  the F8 gate (summary `~/.cache/line06/f8-gate/gate-14409696.summary`; background waiter prints it); then
  `executed`.
- 2026-11-27 **X06-CI1 judged PASS** (wp/X06 `f294bb4e..a514896c`, 13 commits, opus-engineer, about 311k tokens,
  twice the budget): full gate `GATE PASS a514896c: 21303 passed, 107 skipped, 3 xfailed`; codehealth diff PASS
  (debt 61.30 -> 59.40); F0 PASS; `X06_SERVED_SHA256` `7792576e...` unchanged (no digest pin changed in the diff;
  the brief's `d0f0c8b7` was a stale WO4 value). Causes: (1) new `*_sha256` names, classified exact in a new addendum
  `benchmarks/x06/numerical_policy_external.yaml` with the two `$defs` moved to `schemas/solve-policy-results.schema.json`
  (R-1032 / F3 precedent; FOR DESIGN-LANE NOTICE at the merge card); (2) fixtures copied a guarded policy; (3)
  decompositions lacked `without_x06`; (4) CI pins threads to 1 -> `exact_replay` (Amendment 3), the test now follows
  `decide_mode`; (5) refactors, no behaviour change; (6) identity job downstream of the check legs. Pushed origin
  wp/X06 = a514896c (orchestrator lane, as the first X06 push); CI waiter `~/.cache/line06/ci/x06-a514896c.log`.
