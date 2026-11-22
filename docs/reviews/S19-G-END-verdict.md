# S19 G-END: verdict at the wp/S19 tip 043879a4

**Judged:** `043879a41de0525fc86d6d79f271165855b11a09` (tree `5942b946`), the `wp/S19` tip after lane DUP; `main` =
`d29f1a50` is an ancestor. **Date:** 2026-11-21. **By:** design lane, `verdict` agent (Opus 5.5), brief
`<git-common-dir>/codehealth/briefs/S19-V-GEND.md`. Agent verdict: numerical and procedural only. No human numerical
or process-modelling sign-off is claimed, and nothing here sets `reviewed`.

**Criterion, as registered** (`docs/S19_STATE.md`, gates table, row G-END; fixed at 3d3eebe3, F0 clause amended by
ADR 0077 D7, card `ofs-s19-w5-fr3-gend-clause` A, 2026-11-18): repo scan (scope `src/openflowsheet/*`): debt <= 1900;
health >= 9.0 (binding); brain functions 0; no file below health 7.0; no `huge_file`; `codehealth arch`: 0 cycles at
depth 4, 0 violations on every rule; F0 and MCP digest by E1 to E5 (`docs/briefs/S19-W5-ruling.md` section 7); full
suite and CI green on both legs.

## Verdict

| # | Clause | Verdict | Measured at the tip | Evidence class |
| --- | --- | --- | --- | --- |
| 1 | debt <= 1900 | met | 1878.4 | code-health measurement |
| 2 | health >= 9.0 (binding) | met | 9.06 (NLOC-weighted 9.0642) | code-health measurement |
| 3 | brain functions 0 | met | 0 | code-health measurement |
| 4 | no file below 7.0 | met | lowest 7.0, `models/syn001/column.py` | code-health measurement |
| 5 | no `huge_file` | met | none; one `large_file` (`assessment/cost/contributor.py`, 1111 NLOC) | code-health measurement |
| 6 | 0 cycles at depth 4 | met | 0 (353 files, 4292 imports) | code-health measurement |
| 7 | 0 violations on every rule | met | 0 (2 layer rules, 3 forbid rules) | code-health measurement |
| 8 | E1 F0 PASS 9/9 at the tip | met | `F0 PASS`, M7 52/52, M9 42/42 | numerical identity (regression identity) |
| 9 | E2 identity paths changed only by the two kinds | met, with the ruling below on 68abf467 and 30f705d9 | 11 commits, all classed | provenance |
| 10 | E3 W5-S3 every step, W5-K2 every close, W5-K5 for P | met (WO-N4's S3 closed by this verdict's rerun) | 74 gated steps + WO-N4; 3 closes | numerical identity, procedural |
| 11 | E4 M7's 52 values identical to d90b498f | met | 52 x (`MATCH`, `exact_replay`, integrity true) | numerical identity |
| 12 | E5 mcp_digest passes; files as d90b498f unless changed by a merge of main | met | 44 passed; files equal to `main` d29f1a50 | tested, provenance |
| 13 | full suite green | met | 20926 passed, 107 skipped, 3 xfailed, 0 failed | tested |
| 14 | CI green on both legs | met | run 44909075689 at 043879a4: both `check` legs success | tested |

**Decision: G-END is PASSED at 043879a4 (tree 5942b946).** Every clause is met. Two clauses needed a ruling or an
added measurement, both recorded below; neither relaxes a threshold or drops a case.

## Basis per clause

**Clauses 1 to 5 (scan).** Re-run by this verdict: `.venv-codehealth/bin/codehealth scan --repo . --json OUT` in the
`s19` worktree at 8b48cd42, whose diff to 043879a4 is `docs/S19_DECISIONS.md` and `docs/S19_STATE.md` only (outside
the scope). Summary line: `353 files, 107493 NLOC, debt 1878.4 (17.47/kNLOC), health 9.06, functions with debt
503/5707, brain 0, file smells 48, errors 0`. Totals and all 353 per-file records equal the orchestrator's
`scan-043879a4.json`. File smells: 47 `duplication`, 1 `large_file`; no `huge_file`; no file errors; every file
under `src/openflowsheet`. Margins: debt 21.6 under, health 0.06 over.

*Like with like.* The thresholds were fixed at 3d3eebe3 under cce-code-health `d542005`; the measurement uses the
current pin `34a30bf` (0.4.1.dev18, complexipy 8.3.0), after several re-pins logged in `S19_DECISIONS`. This verdict ran
the `d542005` source (`git archive d542005` of `~/Code/cce-code-health`, imported ahead of the installed package)
over the same tree: debt 1878.4, health 9.06, brain 0, none below 7.0, no `huge_file`, file smells 49. Only three
files differ, all by the duplication smell (`syn001/component_separator.py` 8.1 vs 9.1, `thermal/flash.py` 8.7 vs
9.7, `verify/flowsheet_rows.py` 9.8 vs 8.8). Every clause has the same verdict under both instruments.

**Clauses 6, 7 (arch).** Re-run: `codehealth arch --depth 4`: `353 files, 4292 imports, 0 violation(s), 0 cycle(s)
at depth 4`; the same under `d542005`. Rules at the tip: `application-layers` (55 entries), `repo-layers` (34), forbid
`verifier-not-through-the-solver`, `transports-through-operations`, `engine-not-persistence`; `cycle_depth = 4`,
`type_checking = false`, as at 3d3eebe3 (entry lists grew with ADR 0076's moves: 39 to 55, 29 to 34; forbid targets
11 to 17, 29 to 38, 2 to 3). Every top-level package and module of `src/openflowsheet`, F3's `records` included, is
named in `repo-layers`, so no package escapes the layer rule.

**Clause 8 (E1).** Merge-check 702 (`gate_queue.py`, full suite, behaviour-only) at 43a073d5, whose diff to 043879a4
is 11 added lines in `docs/S19_DECISIONS.md`: `F0 PASS: M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61, M6 85/85,
M7 52/52, M8 105/105, M9 42/42` (`runs/s19-gates/20261121T130519-dup-mc.tiers.log:468`). `corpus_identity.py`
names `docs/` only in comments, so the log file is not an F0 input. Corroboration, not read by this verdict: CI's
`check (ubuntu-latest)` at 043879a4 runs `tests/test_f0_corpus_identity.py::test_the_gate_passes` on the reference
class `ref-x86-64`. The brief's F0 at 2aaa5d3f is superseded by this direct measurement.

What E1 pins: for M1, M4, M5, M7, M8 the registered values are d90b498f's (clause 11's comparison), so PASS means
identity with pre-S19 behaviour. For M2, M3, M6, M9 the registered values were re-recorded inside the campaign (W5 K
commits), so PASS pins the tip to those values; that they moved only by identity bytes rests on E3's K2 and K5, not
on E1.

**Clause 9 (E2).** `git log d90b498f..043879a4 -- benchmarks/f0/ tests/fixtures/registry/
src/openflowsheet/registry/builtin/` lists eleven commits:

| Commit | What | Kind |
| --- | --- | --- |
| 4178e4bc | batch N close K | W5 re-registration, K2 PASS |
| bfc6f84b | batch L close K | W5 re-registration, K2 PASS |
| 2a5f0322 | batch P close K | W5 re-registration, K2 PASS, K5 PASS |
| 30f705d9 | WO-N4, units' factory module (legacy.json 30 pointers, tables.sha256) | W5 re-registration of batch N (ruling below) |
| d49198df, dcd428dd, e050aed8, bfd2d7e6, 04a119e3, ebdff46f | F3 | arrived through the merge of main; ancestors of d29f1a50, not of 4881224c; judged in F3 (manifest at 6c82b535 `tested`, merged into main on card `ofs-f3-merge-main` A) |
| 68abf467 | merge of main d29f1a50 into wp/S19 | arrived through a merge of main (ruling below) |

No commit after 68abf467 touches these paths. The post-K commits 43dccc21 and b1d2ae6a touch identity-bearing files
outside E2's three paths (limitation T3).

**Clause 10 (E3).** Per-step W5-S3 is the `f0` tier under `S19_W5_BATCH` (`w5_gate.py f0`, "w5 f0 (W5-S3) PASS: the
prediction at B holds both ways"). Every commit of B..K in the three batches was mapped to the queue's done records
(`<git-common-dir>/codehealth/queue/done/`): batch N 47 commits, 43 with a passing gate whose W5 tiers (scope,
coverage, registry, f0, pin, mcp_digest) all passed; the other four are two plan commits (89527267, 8ac4511c; no
`src/` change), K, and WO-N4 30f705d9. Batch L 20 commits: 18 gated, a plan commit, K. Batch P 16 commits: 13 gated
(B7 a5b8fb11 by merge-check 557 with all W5 tiers passing, after no-gain 556 failed on static checks only), two
test-only commits, K. Jobs 402 and 403 are gate PASS 19/19 with a bookkeeping `LOG-ERROR` only.

WO-N4 passed no queue gate (512 gate-error, 513 static checks, 514 `w5_scope` at K, 515 plain merge-check without W5
tiers); its S3 was the engineer's report. This verdict re-ran it in a detached worktree at 30f705d9 with the batch N
document (`briefs/S19-W5-batchN.json`, base 605d332f, max_tier 2):

```
w5 f0 (W5-S3) PASS: the prediction at 605d332fc062 holds both ways; F0 FAIL: M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 FAIL 1/35
predict --against-tables PASS: M9 1; tables 30 pointer(s)
w5 registry (W5-S4) PASS: exit 0
```

K2, re-run by this verdict with `w5_identity.py judge` at the tip's tool:

```
judge PASS: 605d332fc062..4178e4bcd508, |E| 11; predicted M9 1; tables 30 pointer(s)
judge PASS: 69806a5a52f3..bfc6f84bd6e0, |E| 8; predicted M9 8
judge PASS: 69806a5a52f3..0d38cb7034f7, |E| 8; predicted M9 8
judge PASS: 2eae72a8be67..2a5f032282b2, |E| 5; predicted M2 9, M3 9, M6 8, M9 12; tables 1 pointer(s)
```

K5 for batch P: the queue's tool-written record `queue/batches/closed-2eae72a8*.json` (written only after K1 and K5
pass, `w5_gate.py:560-592`), batch document sha `91d97ce0` equal to `briefs/S19-W5-batchP.json`. Re-run by this
verdict at K in a detached worktree into a scratch queue directory (the real queue untouched):

```
w5 pin (W5-K5) PASS: pinned 3, unpinned 2 (CoolProp), the pinned F0 is the prediction at 2eae72a8be67 for 9 file(s); F0 FAIL: M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61, M6 FAIL 2/85, M7 52/52, M8 105/105, M9 FAIL 9/35
W5-K1 PASS: K 2a5f032282b2 of batch P (base 2eae72a8be67), 8 fixture path(s)
```

The unpinned keys are exactly the CoolProp keys the ruling allows (section 6.2, W5-S2).

**Clause 11 (E4).** `benchmarks/f0/corpus.json` at 043879a4 against d90b498f, per measure: M1, M4, M5, M7, M8
JSON-equal; `format`, `reference_platform` (`ref-x86-64`), `corpus`, `archived_outputs` equal; M2, M3, M6, M9 differ
(the K commits of clause 9; M9 35 to 42 keys by B7). M7: 52 entries, all (`MATCH`, `exact_replay`, integrity true).
For string and boolean values with equal key sets, JSON equality is identity of every registered value.

**Clause 12 (E5).** `tests/test_t08_w2_surface_digest.py` and `tests/test_m07a_surface_chain.py`: `git diff d29f1a50
043879a4` empty; against d90b498f they differ only through 0ae27230, e2e3675f, a66116d9 (F3, ancestors of d29f1a50,
not of 4881224c). The exception "unless changed by a merge of main" applies. Tier at 43a073d5 (merge-check 702): `44
passed`, `tier mcp_digest: PASS`.

**Clause 13 (full suite).** Merge-check 702, tests tier `--full` ("selected all"): `20926 passed, 107 skipped, 3
xfailed`, no failure. The default collection is `-m 'not nlp and not pymrm'` (`pyproject.toml` addopts); the gate
deselects two wall-time budget tests (`gate.sh:63`: `test_t07_v17_reference.py::test_f6_...`,
`test_t07_conformance.py::test_the_budget_of_the_scenario_runs`), which CI's `scripts/check.sh` does not deselect.

**Clause 14 (CI).** One `gh run view` by this verdict: run 44909075689, `push` on `wp/S19`, headSha
`043879a41de0525fc86d6d79f271165855b11a09`, conclusion success; `check (ubuntu-latest)`, `check (ubuntu-24.04-arm)`,
`default-install`, `codehealth`, `identity` success; the twelve other jobs skipped (branch push). The `check`
job installs the CoolProp extra and sets `OPENFLOWSHEET_REQUIRE_COOLPROP=1` (`ci.yml:106-140`), so batch P's
CoolProp tests run on both legs.

## Rulings on E2

**68abf467 counts as "arrived through a merge of main".** It differs from both parents in two lines: the `legacy`
line of `tables.sha256` (`1bd31223`; S19 parent `c31cc880`, main `4ac7d6eb`) and `builtin-sha256.txt` (`6a7550d4`;
S19 `2eb3c86b`, main `fc0af96b`). Everything else it carries in these paths is main's bytes verbatim (`records.json`,
the `core` and `records` lines). The two new values are forced, not chosen:

- `table_sha256` (`registry/discovery.py:102-107`) hashes the table name, the table's bytes and the descriptor
  schema's bytes. F3 changed the schema (`schemas/extension-descriptor.schema.json` `cb368c6b` to `0f938901`); W5
  changed `legacy.json` (`f64043de` to `fff61b28`). Recomputed by this verdict from the committed bytes with that
  formula: every line at 4881224c, d29f1a50 and 68abf467 matches, the merge's legacy line included. It is a function
  of W5-judged table bytes and F3-judged schema bytes.
- `registry_sha256` is `Registry.build` over the merged tables. `registry_builtin.py --check` at the tip: `clean, 49
  descriptors in 3 tables ...; table digests held; registry_sha256 6a7550d4...`.

Any other resolution, either parent's value included, fails `registry_builtin.py --check` and E-F1-5. The merge was
gated: merge-check 606 failed one tooling test (W5-S2's records table, fixed in da6e4e82, not in these paths), 615
passed 11/11. Reading the second kind so that the only correct merge of main fails it would make E2 unreachable after
any merge of main that touches the registry, which E2 and E5 expressly provide for. **The ruling's limit:** it admits
a merge-commit change in these paths only where each changed value is reproduced by the committed generator's
`--check` from bytes that each arrived by one of the two kinds. A hand-chosen resolution would not qualify.

**30f705d9 (WO-N4) counts as a W5 re-registration commit of batch N.** Ruling R1 item 2 names "the factory switch of
WO-N4" as part of batch N's re-registration of the built-in registry identity; WO-N5 predicted the change in K's diff;
K2 at 4178e4bc judges B..K and counts its "tables 30 pointer(s)"; R-W5-N-close logged the early commit as a
deviation with the net B..K unchanged. Its own W5-S3 and W5-S4 pass (re-run above).

## Alternatives rejected

1. *E2 not met on 68abf467, reading "a commit that arrived through a merge of main" as authored on main only.*
   Rejected: the resolution has no degree of freedom (above), and the literal reading fails the only correct merge.
2. *Require a W5-K2 for 68abf467.* Rejected: K2 judges a W5 batch's corpus moves for its edited set E; 68abf467
   changes no `corpus.json` value and belongs to no batch, so K2 has nothing to judge.
3. *E2 not met on 30f705d9 because it is not the K commit.* Rejected: R1 item 2 and K2's table count cover it.
4. *E3 met on the engineer's report for WO-N4.* Rejected as insufficient alone: no gate ever ran its f0 tier. The
   gap is closed by the rerun, not by the report.
5. *Judge clauses 1 to 7 under the current pin only.* Rejected as incomplete: the thresholds predate several re-pins.
   Both instruments give the same verdicts at this tree.
6. *Re-run F0 at the exact tip.* Not needed: 702 measured a tree that differs from the tip only in a log file F0
   does not read.
7. *Count the nlp-marked suite into "full suite".* Rejected: the repository's default collection excludes it, no
   gate or CI job runs it, and the S19 state handles it by a separate rule (rule 3).
8. *Count the two gate-deselected budget tests as a miss.* Rejected: they are wall-time assertions deselected under
   concurrent gate load (G-SELF, 2026-11-14); CI's `check` runs the collection without that deselection.

## What would change the verdict

- `main` moving past d29f1a50 before wp/S19 merges into it: the merged tree is then not 5942b946. Re-measure clauses
  1 to 8, 12 to 14; under E2, each new main commit in the three paths must be judged in its own package and any new
  merge resolution must again be generator-forced.
- Any commit on wp/S19 after 043879a4 that touches `src/`, `scripts/`, `benchmarks/f0/`, `tests/fixtures/registry/`
  or the two digest test files.
- F0 failing on `main` after the merge (G-END-CI, W5-K8).
- Evidence that `registry_sha256` or `table_sha256` is not a deterministic function of the committed bytes: voids
  the 68abf467 ruling.
- A finding that a W5 re-registered value (M2, M3, M6, M9) moved for a reason other than identity bytes: voids E3's
  basis for those measures.
- Not a reason to reopen: a later cce-code-health version scoring this tree differently. This verdict records the
  scores under both the registering and the current instrument.

## What this verdict does not establish

- Behavioural identity beyond its instruments: F0's nine measures, the default test collection and the MCP digest.
  S19's rules leave the rest to reading reviewers.
- For M2, M3, M6, M9: identity with pre-S19 behaviour by F0. It rests on K2 (only predicted identity keys moved) and
  K5 (pinned F0 PASS for tier 3); for `coolprop-heos-v1` on B7-C1 to C4, since no F0 run exercises CoolProp.
- Numerical verification against analytic or independent references, empirical validation, or optimality. G-END
  is a code-health and identity gate; the digests and `registry_sha256` have no independent expectation and are
  self-consistency checks.
- Correctness of the code from its health scores: they measure structure.
- A portable result: F0 is judged on `ref-x86-64`; aarch64 ran its own CI checks; macOS and Windows are outside G-END
  (known F0 M7 `NOT_RUN` there, X07a Q-2).
- The nlp-marked suite at the tip: last measured at 607dee3e (211 passed, 2 failed: `test_opt_cost_lca_nlp` g19, g20,
  base failures); `studies/` is unchanged since, other modules changed.
- Closure of S19's open items (`docs/S19_STATE.md`): build-lane (the no-op patch at `test_s01_cascade_wo1.py:262`,
  the unguarded `c1_reactor_surrogate_of`, the nlp lock's `mpmath`, the dead `ValueError` branch in `mass.py`, three
  non-W5 retarget rows), design round 2 items (i) to (iv), and ADR 0077's FR-1 obligations before the 0.5.0 RC cut.
- Human review of any kind.

## Limitations that travel into the S19 manifest and the release report

- T1. E2 ruling on 68abf467: the merge-generated legacy digest `1bd31223` and `registry_sha256` `6a7550d4`, admitted
  as generator-forced, with the recomputation above.
- T2. WO-N4 (30f705d9) passed no queue gate; its W5-S3 and W5-S4 evidence is this verdict's rerun (lines quoted above).
- T3. Identity-bearing files changed outside E2's three paths after K: 43dccc21 (four capability fixtures) and the
  merge b1d2ae6a (five m05 G10 records at batch P's provider identity). Name them in the manifest (design round 2,
  item (iv)).
- T4. User-visible identity changes (ADR 0077 migration): `registry_sha256` in `list_capabilities` and inspection
  responses; `model_version` of runs on the four batch P providers; v1 bundles from 0.4.x on them replay `MISMATCH`
  on `model_version` (CHANGELOG `## Unreleased`).
- T5. Local full suite = default collection minus two wall-time budget tests; nlp-marked suite outside G-END (above).
- T6. Code-health scores with tool pin `34a30bf`, cross-checked with `d542005`; `docs/S19_RULES.md` "Settled" still
  names `d542005` (stale).
- T7. 48 file smells remain (47 duplication, 1 `large_file`). G-END does not bound them; CI's `codehealth diff --base
  origin/main` passed.

## Findings on the criterion (separate from the verdict)

- C1. E2 does not say how a merge of main that must regenerate a digest of both sides is classed. Suggested
  amendment: the ruling's limit above, as text.
- C2. The G-END row names no instrument version, and the tool was re-pinned several times after the thresholds were set.
  Future gates should record the pin in the row.
- C3. G-END's scan clauses do not bound file smells; the region.py duplication of 2aaa5d3f was caught only by CI's
  ratchet. Whether the end gate should carry "no new file smell against CB" is a design-lane question.
- C4. "Full suite" is not defined against the nlp marker or the gates' budget deselections. Name the collection.

## Commands this verdict ran

All in `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/s19` (at 8b48cd42) unless a worktree is named;
temporary worktrees were removed afterwards, and the real queue and evidence were not written.

- `codehealth scan --repo . --json <scratch>`; `codehealth arch --depth 4`; both again with the `d542005` source.
- `git log` and `git diff` over the E2 paths and the digest files; `git merge-base --is-ancestor` for F3 and
  mcp-digest commits; per-measure JSON comparison of `corpus.json` (d90b498f vs 043879a4).
- `table_sha256` recomputation from committed bytes at 4881224c, d29f1a50, 68abf467.
- `PYTHONPATH=src .venv/bin/python scripts/registry_builtin.py --check`.
- `scripts/w5_identity.py judge` for the four (B, K) pairs above.
- Detached worktree at 30f705d9: `w5_gate.py f0` and `w5_gate.py registry` with `S19_W5_BATCH` = batch N document.
- Detached worktree at 2a5f0322: `w5_gate.py close --k 2a5f0322 --batch <batch P document> --queue-dir <scratch>`
  with the eight fixture paths of the closed record.
- A mapping of every B..K commit to `queue/done/*.json` and its gate JSON checks.
- `gh run view 44909075689 --json headSha,headBranch,status,conclusion,event,jobs` (one call).
