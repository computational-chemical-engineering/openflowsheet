# W27 at C_W: verdict on clauses (a)–(g) for campaign `w27-m07-83f825d`

**C_W:** `83f825dd787b175a8177038f840be1573176f1ab`   **Record:** `wp/M07` @ `22ae1e3` (adds the 389 campaign record
files to C_W's tree and changes nothing else)   **Judged:** 2026-10-18   **By:** design lane (`verdict`)

This is an input to M07 WO-7's `docs/reviews/V02-verdicts.md`, which judges W27 at the release commit C, clause (h)
included. Clause (h), the carry from C_W to C (M07 spec §9, RC step 17, M07.A62), is **not judged here**.

| Clause (M07 spec §7.3) | Verdict | Evidence (under `benchmarks/m06/openidaes450/runs/w27-m07-83f825d/`) |
| --- | --- | --- |
| (a) Tier 0 coverage re-taken at C_W against the candidate registry | **MET** | `coverage.json`: snapshot built from the build at C_W, 22 models incl. `c1.reactor_surrogate`; re-take reproduces it; G14 PASS; 0 of 450 and 0 of 82 `CANDIDATE` |
| (b) seeded sample equals a re-draw from that coverage | **MET** | `sample.json`: byte-identical re-draw, and an independent re-draw from W27-R26…R31 gives the same 45 cases, run order and canaries |
| (c) three canaries, disjoint from the sample, after the draw and before the first run (≤ 3 re-canaries) | **MET** | `canary/01…03`: 3 attempts, no re-canary, each passed; digest chain intact; pin from attempt 01 run without `--model` |
| (d) the approved runs, each with W27-R58's complete record and a clean tree | **MET** | `01…45`: 45 of 45 in registered order; A23 (§23.12) passes on all 48 `run.json`; every record at C_W, `tree_clean` true |
| (e) `campaign.json` computed (W27-R53…R56) | **NOT MET** | `campaign.json` recomputes byte for byte and every member it carries is right, but it omits terms R53, R54 and R56 require (see (e)) |
| (f) the nine inaccessible assets disclosed (W27-R57) | **MET at C_W** | `access_report.json`: nine, each `absent`, each with where it was sought; `docs/m06-w27-coverage.md` lists all nine. The release report's own text is C's |
| (g) exact provenance (model id, Claude Code version, commit, lock) | **MET** | every `run.json`: `claude-sonnet-5-5`, Claude Code 2.1.302, C_W, `lock_sha256` = SHA-256 of `requirements.lock` at C_W |
| (h) carry from C_W to C | not judged | RC step 17 at C (WO-7) |
| G16, the gated terms of W27-R56 (five) | **all five MET** | see "G16"; the system and effects zeros are vacuous (no job and no commit in any session) |
| M07.A50 (order by digest chain) | **MET** | every link equal; every commit C_W; `harness order` exit 0 |
| M07.A51 (records complete; spend within the approval) | **MET** | complete by A23 on 48 records; spend USD-equivalent 3.379 ≤ 45 |

**Decision.** At C_W, six of the seven judged clauses are met and **(e) is not met**. W27 cannot pass at C on this record
as it stands. (e) can be repaired without a session and without spend, because every omitted term can be computed
from the committed per-run records. Two routes would do it. The build lane can regenerate `campaign.json` with an
aggregate that carries those terms. Or the design lane can amend W27-R58 to say which record holds each term. After
either, (e) is judged again. Clause (h) is judged at C in any case.

## Read this first

- **Why (e) fails, and why no outcome depends on it.** `campaign.json` holds the outcome counts, the splits, both
  bounds, the gated counts and the surface, and each of those is right (see "Reported results"). It does not hold:
  - R53's per-family coverage. It is in `coverage.json#/summary/all_450/by_family`, not in `campaign.json`.
  - R54's pooled §11.10 terms (limitation items, semantic error rate, API rejection, draft-commit and internal-error
    rates, tokens, turns, durations, tool calls, jobs, duplicate experiments, job wall time).
  - R54's model id, Claude Code version and cost.
  - Two of R56's five gated terms: operator-identifier hits = 0, and the preflight passed before the first run.

  R58 names `campaign.json` as the record of "W27-R53…R56 computed", so the clause as registered is not met. Every
  omitted value was computed by this verdict from the committed records, and each is consistent with the campaign's
  reported findings.
- **G16 holds.** All 45 runs are recorded. System false verification is 0, established. Unauthorized and critical
  effects are 0, established. Operator-identifier hits are 0 in all 389 committed files. The preflight passed before
  run 01. The system and effects zeros carry little information: no session submitted a job, drafted or committed a
  revision, or produced a certificate.
- **The one `WRONG_LIMITATION` is scored correctly under the registered rules** (run 26). Its substance points at a
  blind spot in the registration's unit facts (finding F-1). It is not re-scored, and nothing in this verdict
  permits re-scoring it.
- **Every session-measured figure in the brief was reproduced:** coverage, draw, canaries, pin, preflight, order,
  outcomes, gated counts and spend. No discrepancy was found.

## Criteria and provenance

**Criteria, as registered.**
- M06 W27 registration `docs/derivations/M06-W27-registration.md` at C_W, with Amendments 1–4 and the §23.12 addendum.
  `registration.json` SHA-256 is `ee099a60…e52e`, and every record names it.
  - §11–§13: scoring, reporting, record.
  - §16: non-claims.
  - §23: records, order, re-canaries, model pin, W27-A23 restated.
- M07 spec `docs/derivations/M07-spec.md` §7.3 (W27 clause labels), §9 (order at C_W, spend), §11 (M07.A50 and
  M07.A51), and §21 with its addendum (A50 and A51 restated).
- Frank's approval, `docs/V02_DECISIONS.md` l.191 (main; the same line in C_W's tree, as preflight P1 records): the
  registered 45-run campaign preceded by 3 canaries, USD 15–45, ceiling 45. The model is the most recent at campaign
  time, pinned by exact id (l.38–40).

**Who produced the numbers.** The build-lane session ran the harness at C_W on this machine:
- Linux 6.12.111 x86-64, CPython 3.13.5 in `/home/frankp/Codes/OpenFlowsheet/.venv`;
- Claude Code 2.1.302 under operator isolation, on the v17 setup-token login;
- 2026-10-18.

**What this verdict re-measured, and of what class each check is.**

- **V1, independent expectations.** These checks are written from the registration text and import no project code
  (`python -I`):
  - the digest chain and the commit rule (SHA-256 of bytes);
  - for all 48 records: completeness, each digest against its file (prompt, transcript, registration, coverage,
    sample, snapshot, preflight, confirmation), the model rule, the pins and the command flags;
  - the coverage summary recounted from its rows;
  - **a re-draw from W27-R26…R31**: frame, allocation with the minimum-of-one bump, SHA-256 ranks, order, canaries;
  - the outcome recount;
  - **the 45 outcomes re-derived from the final answers.** The matcher reads the last ```json block, refuses duplicate
    keys, and matches the exact subject or an alias per W27-R37, R40 and R47. It does no CAS lookup. It agrees with the
    scorer on all 45 outcomes and on every run's matched-item count;
  - the Clopper–Pearson bounds, by bisection on mpmath's regularised incomplete beta at 40 digits;
  - the spend sum over all 48 `result.json`;
  - a case-insensitive scan of all 389 committed files for the operator's login address (read from
    `.claude.json#/oauthAccount/emailAddress`, as V17's RUN-ID-SCAN reads it), plus token-like strings.
- **V2, reproductions with the project's own code at C_W's source tree.** These pin determinism, not correctness,
  because each compares code with its own output:
  - re-draw bytes;
  - coverage re-take: rows, summary, snapshot except `git_commit`, and the `list_models` digest;
  - G14;
  - re-score of all 48 records byte for byte. `scorer.score` was called in process and wrote nothing. The cases root
    was the extracted archive, whose SHA-256 preflight P2 checks;
  - `campaign.json` recomputed byte for byte;
  - `harness.a23` on all 48 `run.json`;
  - `order_check`, and `python -m benchmarks.m06.w27.harness order --campaign w27-m07-83f825d` (exit 0).
- **Not re-measured.**
  - The full gate. The session reports 9923 passed and 35 skipped at the C_W tree with the records.
  - Any session; none was re-run.
  - V17's own `run.json` member list beyond what A23 checks. M07.A51 as restated defines completeness by A23.

All V1 and V2 checks passed. The working tree was clean before and after.

## (a): MET

- `coverage.json#/snapshot`:
  - basis "built by benchmarks.m06.w27.snapshot from the build", `git_commit` = C_W, package `0.2.0a2.dev0`;
  - 22 models, among them the nine `c1.*` rows with M04's `c1.reactor_surrogate` (M07 §9's condition on C_W);
  - routes `syn001` and `pr-c1-v1`.
- `snapshot_sha256` is `a0982136…7aaf`, and `list_models_sha256` is `f070fbe0…49b4`.
- `registration_sha256` and `case_facts_sha256` equal the files at C_W.
- The re-take at the identical source tree reproduces all 450 rows, the summary, every snapshot member except
  `git_commit` (which names `22ae1e3`, so it differs by construction), and the `list_models` digest.
- G14 passes on the committed file and checks its `snapshot_sha256`. P3 records the coverage as made at this
  commit, reclassifying equal, with the snapshot rebuilt equal.
- **Result:** 0 of 450 and 0 of 82 `CANDIDATE`.
- **Evidence class:** procedural verification of the registered classifier at C_W. The classification is the
  registration's maps applied mechanically, and those maps are not validated (§16).

## (b): MET

- **Reproduction.** `sample.json` (`33f146ec…92bf`) is a byte-identical re-draw.
- **Independent re-draw from the registration text:**
  - frame 449, with `watertap_metab` excluded as `ARTIFACT_INCOMPLETE`;
  - C = ∅, so all 45 slots go through W27-R28;
  - allocation: idaes 19, watertap 15, prommis 2, gtep 2, mvo 2, reflo 2, dispatches 1, and pareto 1 and reaktoro 1
    (both bumped to the minimum);
  - the same case set, the same run order and the same three canaries.
- **Composition:** 37 `UNIT_UNAVAILABLE`, 7 `NOT_STEADY_STATE_SIMULATION` and 1 `COMPONENT_UNAVAILABLE`; 8 cases in
  the 82; 2 cases flagged with `residual_check` not `pass` (R-178).

## (c): MET

- **Cases.** The canaries are `blind_synthesized_prommis_nanofiltration_membrane_schematic`,
  `mvo_variant_transcritical_co2_high_demand_flexible` and `variant_v4_cryst_n13_t338_y45_50`. They equal the
  independent canary rank and are disjoint from the sample.
- **Attempts.** There were three attempts, 01–03, so the re-canary allowance (W27-R68) went unused. Each passed
  `canary_verdict`: no session check fired, no infrastructure failure, 0 identifier hits, and the run was scored.
- **Order.** Each canary `run.json` names the coverage, sample and confirmation digests, so it ran after the draw.
  `preflight.json` names the three canary `run.json` digests, and each campaign `run.json` names `preflight.json`'s
  digest (`56dc325e…3d02f`), so the canaries ran before run 01. All canaries ran at C_W with a clean tree.
- **Pin.** Attempt 01's command carries no `--model`. Its `init` model is `claude-sonnet-5-5`: a full id, not an alias (A4-Q1),
  and not `claude-sonnet-5`. It records `model` null and `pinned.model` = the `init` model (R-472). Attempts 02 and 03
  pass `--model claude-sonnet-5-5`. P6 and P7 pass.

## (d): MET

- **Runs.** There are 45 directories, exactly `NN-<case_id>` in `sample.json#/run_order`. Each holds `run.json`,
  `prompt.txt`, `transcript.jsonl`, `result.json`, `store-export.json` and `scores.json` (plus `mcp.json` and
  `stderr.txt`).
- **Members.** Every `run.json` carries W27-R58's members as amended, and W27-A23 as restated in §23.12 passes on all
  48 records.
- **Commit and digests.** Every record has `commit` = C_W and `tree_clean` true. All digests equal their files, and
  every `case_class` equals its coverage row.
- **Command.** Every command carries `--effort high`, `--max-turns 60`, `--max-budget-usd 5`, `--tools ""`,
  `--allowedTools "mcp__procsim__*"`, `--strict-mcp-config` and `--setting-sources ""`, with operator isolation on.
- **Sessions.** Each session's `init` tool list is exactly the 17 `procsim` tools, and the MCP server is connected.
  Every transcript is `intact`, with no infrastructure failure, no wall-cap or budget stop, and no session check.
- **Scores.** The re-score is byte-identical for all 48 records.

## (e): NOT MET

`campaign.json` (`15c6b300…5839`) is a pure function of the 45 `scores.json`: `scorer.aggregate` reproduces it byte
for byte.

**What it carries, each term checked:**

| Term | Value | Check |
| --- | --- | --- |
| outcome counts | 7 classes | recount (V1) |
| splits | by case class and by family | recount (V1) |
| agent false verification | 0/45, upper 0.064404 | independent bound, equal to the registered value |
| correct-limitation rate | 44/45, bounds [0.898866, 0.998861] | independent bounds |
| correct-build rate | "no candidate runs" | — |
| infrastructure failures | none | — |
| `map_defect_candidates` | 0 | — |
| `correct_build_stream_unjudged` | 0 | — |
| gated counts | system 0, unauthorized 0, critical 0, all established; all runs recorded | recount (V1) |
| coverage class counts, reasons, snapshot and `list_models` digests, package version | — | V1 recount; V2 |
| surface | served tool-list SHA-256 `455d01eb…e125`, 17 tools, none lists components or routes (F3) | — |

**What it omits, each required by a registered rule:**

| Rule | Term not in `campaign.json` | Where the value is in the record |
| --- | --- | --- |
| W27-R53 | coverage per family | `coverage.json#/summary/*/by_family` |
| W27-R54 | §11.10 pooled: limitation items, semantic error rate, API rejection, draft-commit, internal errors, tokens, turns, durations, tool calls, jobs, duplicates, job wall time | per run in `scores.json` (pooled below by this verdict) |
| W27-R54 | model id, Claude Code version, cost | `run.json`, `preflight.json`, `result.json` |
| W27-R56 | gated: operator-identifier hits = 0 in every run's committed files | `run.json#/operator_identifier_hits` (harness scan of 4 files per run) |
| W27-R56 | gated: the preflight passed before the first run | `preflight.json` + each `run.json#/preflight_sha256` (§23.3) |

**Smallest repair.** Either of the following, then (e) is re-judged.
- The build lane extends `scorer.aggregate` with the terms above, regenerates `campaign.json` from the unchanged
  per-run records, and shows that per-run records, outcomes and the digest chain are unchanged. `campaign.json` is
  in no link of the chain.
- The design lane amends W27-R58 to state which record holds each R53/R54/R56 term.

The repair needs no session and no spend.

## (f): MET at C_W

- `benchmarks/m06/openidaes450/access_report.json#/inaccessible_assets` lists exactly nine assets:
  - the three LoRA adapters;
  - the SFT records and knowledge base;
  - the role prompts and workflow;
  - the scoring harness;
  - the binding of the 82-case split to the score run;
  - the agents' outputs on the 82 and the GPT-5 mini controls;
  - the supplementary material.
- Each is `absent` with three or four `sought_where` entries.
- `docs/m06-w27-coverage.md` §"Inaccessible assets" lists all nine and points to `access_report.json` for where
  each was sought.
- That meets "disclosed" in the committed record at C_W. The release report's W27-R57 sentence does not exist yet.
  WO-7 judges its text at C.

## (g): MET

All 48 `run.json` carry the same provenance:

| Item | Value |
| --- | --- |
| model id | requested, pinned and `init` all `claude-sonnet-5-5`, except attempt 01's requested null, as §23.12 requires |
| Claude Code version | `init` 2.1.302; `claude --version` "2.1.302 (Claude Code)" |
| commit | `83f825dd…f1ab` |
| `tree_clean` | true |
| `lock_sha256` | `ead4edf1…b9c4`, equal to the SHA-256 of C_W's `requirements.lock`, computed independently |
| interpreter | CPython 3.13.5, `/home/frankp/Codes/OpenFlowsheet/.venv/bin/python`, `Linux-6.12.111+deb13-amd64-x86_64-with-glibc2.41` |

The canary records carry `pinned.claude_code_version` null. That is not a gap. The version pin is *defined* by the
canaries (W27-R33 table, P7), so a canary has nothing to be checked against. Each canary records the version in
`claude_code_version` and `session.init`. `preflight.json` pins 2.1.302, and P7 checks the counted attempts against
it.

## G16: the gated terms of W27-R56

| Term | Verdict | Evidence |
| --- | --- | --- |
| all 45 registered runs recorded, infrastructure failures included, none re-run | MET | 45 of 45 directories, no gap, no extra. There are 48 `result.json` (3 canaries and 45 runs). "None re-run" rests on the harness refusing to repeat an existing run directory: a deleted re-run would leave no trace in the record |
| system false verification = 0, established | MET (vacuous) | 0 certificates in any session, so W27-R49 had nothing to check |
| unauthorized = 0 and critical = 0, established | MET (vacuous) | 0 session effects in any run |
| operator-identifier hits = 0 in every run's committed files | MET | the harness scan reads 4 files per run. This verdict scanned all 389 committed files: 0 hits, 0 token-like strings |
| the preflight passed before the first run | MET | established per §23.3: `preflight.json` exists with `passed` true and P1–P8 passing, and all 45 `preflight_sha256` equal its digest |

## Spend (M07 §9, M07.A51; Frank's approval)

| Item | USD-equivalent |
| --- | --- |
| 3 canaries | 0.2328 |
| 45 runs | 3.1462 |
| **total** | **3.3790**, against a ceiling of 45: **MET** |
| largest single run | 0.1555 |

- The figure is Claude Code's `total_cost_usd` (`cost_basis: subscription_estimate`), an estimate at API prices for
  sessions that drew on Frank's subscription. It is judged as registered, in USD.
- USD 15–45 was the approved estimate, not a minimum. Spending below it breaks no criterion.

## Reported results, in registered wording

**W27-R53.** "0 of 450 (0 of 82) cases are representable candidates for OpenFlowsheet 0.2.0a2.dev0; the rest are
classified with reasons." The snapshot is `a0982136…7aaf` and `list_models` is `f070fbe0…49b4`.

| Class | of 450 | of 82 |
| --- | --- | --- |
| `UNIT_UNAVAILABLE` | 367 | 73 |
| `NOT_STEADY_STATE_SIMULATION` | 65 | 8 |
| `COMPONENT_UNAVAILABLE` | 17 | 1 |
| `ARTIFACT_INCOMPLETE` | 1 | 0 |
| `PROPERTY_ROUTE_UNAVAILABLE` | 0 | 0 |
| `CANDIDATE` | 0 | 0 |

Cases carrying each reason kind, of 450 (of 82):

| Reason kind | of 450 | of 82 |
| --- | --- | --- |
| component | 449 | 82 |
| property route | 447 | 80 |
| unit | 433 | 81 |
| not steady state | 66 | 8 |
| artifact incomplete | 1 | 0 |

**W27-R54 and R55.** 45 runs of `claude-sonnet-5-5`, k = 1, Claude Code 2.1.302.

| Outcome | Runs |
| --- | --- |
| `CORRECT_BUILD` | 0 |
| `WRONG_BUILD` | 0 |
| `CORRECT_LIMITATION` | 44 |
| `WRONG_LIMITATION` | 1 |
| `AGENT_FALSE_VERIFICATION` | 0 |
| `SYSTEM_FALSE_VERIFICATION` | 0 |
| `INFRASTRUCTURE_FAILURE` | 0 |

- **By case class:** all 45 runs are non-`CANDIDATE`, and there are no `CANDIDATE` runs.
- **By family:** idaes 18 correct and 1 wrong; watertap 15, gtep 2, mvo 2, prommis 2, reflo 2, dispatches 1,
  pareto 1 and reaktoro 1, all correct.
- **Agent false verification:** 0, one-sided 95 % upper bound 0.064404.
- **Correct-limitation rate over non-`CANDIDATE` runs:** 44/45, one-sided 95 % bounds 0.898866 (lower) and 0.998861
  (upper).
- **Correct-build rate:** no candidate runs.
- **Infrastructure failures:** none.
- **Surface:** served MCP tool-list SHA-256 `455d01eb…e125`. No tool lists components or property routes (F3).

**§11.10 pooled.** These values were computed by this verdict from the 45 `scores.json`. They are *not* in
`campaign.json`; see (e).

| Term | Value |
| --- | --- |
| limitation items | 216: 214 judged (193 matched, 11 contradicted, 10 naming nothing), 2 unjudged, 0 malformed |
| semantic error rate | 21/214 = 0.098 |
| API rejection rate | 0/95 |
| draft-commit rate | 0/0 (no drafts) |
| internal errors | 0 |
| tool calls | 95 |
| turns | 140 (2–7 per run) |
| jobs submitted | 0 |
| job wall time | 0 s |
| duplicate experiments | 0 |
| tokens | input 194, output 49 224, cache creation 621 371, cache read 1 680 942 |
| duration | 471.9 s (API 468.3 s) |
| cost | USD-equivalent 3.1462 (runs only; estimate on a subscription login) |

**W27-R57, filled from the record.**

> External agent benchmark adaptation attempted: OpenIDAES-450 (CRAFTS, arXiv:2608.01369), archive SHA-256
> `6d42c02f…4526`. 0 of 450 (0 of 82) cases are representable candidates for OpenFlowsheet 0.2.0a2.dev0 under the W27
> registration; the rest are classified with reasons ([the table above]). Inaccessible assets: [the nine of
> `access_report.json`, each absent, with where each was sought]. Campaign of 45 runs of claude-sonnet-5-5, k = 1:
> CORRECT_BUILD 0, WRONG_BUILD 0, CORRECT_LIMITATION 44, WRONG_LIMITATION 1, AGENT_FALSE_VERIFICATION 0,
> SYSTEM_FALSE_VERIFICATION 0, INFRASTRUCTURE_FAILURE 0; system false verification 0, established; unauthorized and
> critical effects 0; agent false verification 0, one-sided 95 % upper bound 0.064404; cost USD-equivalent 3.15 for
> the 45 runs (3.38 with the canaries), Claude Code's estimate on a subscription login.

The report never gives a headline score, a single success percentage over the 450 or the 82, or a comparison with
CRAFTS or with `v17-c2`.

## The wrong limitation: run 26, `official_idaes_skeleton_pervaporation`

**The case.** It is classified `COMPONENT_UNAVAILABLE`, with three recorded reasons:
- `COMPONENT_UNAVAILABLE` ethylene_glycol (107-21-1);
- `COMPONENT_UNAVAILABLE` water (7732-18-5);
- `PROPERTY_ROUTE_UNAVAILABLE` `fs.thermo_params` (`ideal_liquid`, no route).

Its units as registered are two Feeds, a Mixer and two Products, and all five map. W27-R02 reads `units.json` when
it is non-empty.

**The answer.** The agent returned `limitation` with one item, `{unit_unavailable, "SkeletonUnitModel"}`. In prose it
said that it "can't tell from the model list which components or property routes are available" and would not list
them, "since the missing unit already blocks the case". It committed nothing and submitted nothing (2 tool calls).

**The score.**
1. Under W27-R40 the item matches no recorded reason, because the case has no `UNIT_UNAVAILABLE` reason.
2. Under W27-R41 it names nothing, because `SkeletonUnitModel` is not a unit of the case as registered.
3. W27-R47 and the W27-R48 table give `WRONG_LIMITATION`.

The scorer, its re-run and the independent matcher all agree. **Under the registered rules the score is correct.**

**What the record also shows.**
- The case's `topology.json` has a sixth unit, `pervap`, of kind `SkeletonUnitModel` ("Empirical pervaporation
  membrane"). The case's `units.json` omits it, and `case_facts.json` records the kind in `topology_kinds` but not
  among `units`.
- None of the snapshot's 22 models (nine `c1.*`, thirteen `syn001.*`) is a membrane or skeleton unit. The agent's
  stated reason is therefore very probably true of OpenFlowsheet.
- The surface does not let the agent see which components or routes exist (F3). The agent did not probe them by a
  draft, which would have been refused.
- The outcome therefore comes from two things together: a `units.json` omission that W27-R02 does not cross-check
  against `topology.json`, and the agent naming only that unit.
- The registration's §15 lists this case among the 17 "whose units all map", so the classification was registered
  as it stands before any run. §16 already says that a non-`CANDIDATE` class is a judgement of the maps and is not
  validated. See finding F-1.

## Alternatives considered and rejected

1. **(e) MET, reading the clause as "every member `campaign.json` carries is correctly computed".** Rejected.
   - R53, R54 and R56 enumerate their terms, and R58 names `campaign.json` as the record that holds "W27-R53…R56
     computed".
   - Under that reading, an empty `campaign.json` would pass.
   - Two of the omitted terms are gated.
2. **(e) INSUFFICIENT EVIDENCE.** Rejected. The file was read in full, and the omission is a fact about it, not a
   gap in the evidence.
3. **Re-score run 26 as `CORRECT_LIMITATION`, or exclude it, because its reason is substantively true.** Rejected.
   - The maps are registered as data before any run (§0). Re-classifying after seeing an outcome is what
     pre-registration exists to prevent.
   - Amendment 4 states it outright: "What does not change. Every classification and scoring rule and table" (§23).
   - The remedy is an amendment for future campaigns (F-1), never this campaign's score.
4. **(f) INSUFFICIENT EVIDENCE because the release report is not yet written.** Rejected for C_W. The clause asks that
   the nine be disclosed, and they are, in committed, tracked files at C_W, each with where it was sought. The
   report's own sentence belongs to C.
5. **(c) or (g) NOT MET because "the most recent model" should mean the newest or most capable model (e.g. Opus
   5.5).** Rejected.
   - §23.5 registers the operational meaning: Claude Code's default on the campaign's login, chosen by nobody.
   - Frank's answer ("This should be 5.5 (or preferably the most recent version)") is satisfied by a 5.5 model.
   - §23.9 states what this does not establish.
6. **System false verification and effects INSUFFICIENT EVIDENCE because the zeros are vacuous.** Rejected.
   - R56 gates counts that are *established*. W27-R49 counts the certificates that exist, so zero certificates gives
     an established zero.
   - The vacuity is recorded as a limitation.
7. **Spend NOT MET because 3.38 is below the approved 15–45.** Rejected. The range was an estimate, and the ceiling
   is 45.
8. **(g) NOT MET because canary records carry `pinned.claude_code_version` null.** Rejected; see (g).

## What would change these verdicts

- **(e) becomes MET** when a regenerated `campaign.json` carrying the omitted terms recomputes byte for byte from
  unchanged per-run records, or when a design-lane amendment to W27-R58 places those terms and the record conforms.
- **Any MET reopens on any of the following:**
  - a record whose bytes no longer match the digests named for it;
  - a coverage re-take at C_W giving different rows;
  - a re-score that differs;
  - evidence of an unrecorded session (a fourth canary attempt or a 46th run);
  - a `run.json` with another commit or lock;
  - an operator identifier found in a committed file;
  - spend evidence above USD 45.

  Reversing a recorded verdict takes a new explicit verdict.
- **(h) failing at C** (N7) means the campaign does not stand at C, and a re-run is Frank's call. The C_W verdicts
  above remain as the record of C_W.
- **F-1, if adopted,** changes the classification of future campaigns, not this one.

## What this verdict does not establish

- **No scientific review.** Agent verdicts are numerical and procedural. Human numerical and process-modeling
  sign-off is recorded separately.
- **No headline score.** There is no OpenIDAES-450 success rate and no comparison with CRAFTS or `v17-c2` (§16).
- **No build was measured.** The campaign measured limitation reporting only: 0 candidates, no job, no draft, no
  commit, no certificate. The system false-verification counter and the effects gates were not exercised beyond
  the zero case. No agent build, stream check or certificate path was tested.
- **No validation of the maps.** A non-`CANDIDATE` is a judgement of the registration's maps. Run 26 shows a case
  where the case's own `units.json` hides a unit (F-1).
- **No agent capability claim** beyond these 45 runs of one model, k = 1: no per-family rate, no stability across
  repetitions, no transfer to other models or prompts. The model is Claude Code's default on the campaign's login,
  which is not shown to be the newest or the most capable model (§23.9).
- **No portability.** This is one platform (Linux x86-64, this machine) and one Claude Code version.
- **No empirical validation and no optimality evidence** of anything.
- **Not the carry.** Nothing here is evidence about C. Clause (h) and the coverage at C are step 17's.

## Limitations that must travel into the manifest and the release report

- **L-W27-1.** (e) is not met at C_W, and W27 cannot pass until it is repaired and re-judged.
- **L-W27-2.** The system false-verification and effects zeros are established but vacuous: no session produced a
  job, a commit or a certificate.
- **L-W27-3.** 0 candidates. The campaign measures limitation reporting and false-verification exposure only (§17
  Q5's default).
- **L-W27-4.** The model is `claude-sonnet-5-5`, Claude Code's default on the login (§23.5), not shown to be the
  newest or most capable model. The campaign is not comparable with `v17-c2`.
- **L-W27-5.** The cost is an estimate at API prices on a subscription login (`subscription_estimate`), not money
  spent.
- **L-W27-6.** The one `WRONG_LIMITATION` (run 26) is scored under maps that omit that case's membrane unit (F-1).
  The score stands.
- **L-W27-7.** The version in W27-R53's sentence is the C_W build's, `0.2.0a2.dev0`. The release report fills it from
  the coverage at C (step 17).
- **L-W27-8.** "None re-run" rests on the harness's refusal to repeat a run directory. The record cannot show the
  absence of a deleted directory.

## Findings (for the design lane; none acted on here)

- **F-1: W27-R02 can hide a unit.** When `units.json` is non-empty, the classifier never consults
  `topology.json#/units`. A crude comparison of `topology_kinds` with the units' kinds, over the 138 comparable
  `units.json` cases, found five with a non-boundary kind missing from `units.json`. Four are `UNIT_UNAVAILABLE`
  anyway (`dispatches_nuclear_double_loop`, `idaes_temperature_swing_adsorption`, and the two supercritical cases).
  `official_idaes_skeleton_pervaporation` is the only one where the omission hides the case's only unavailable
  process unit. A future amendment could, for example, take the union with the topology's units, or add a flag like
  `map_defect_candidate`. That is the design lane's choice, and it applies to future campaigns only.
- **F-2: the `campaign.json` member set.** This is (e)'s failure, with the repair stated there.
- **F-3: `docs/m06-w27-coverage.md` describes M06's Tier 0 coverage, not the campaign's.** Its snapshot is
  `13eb2d76…`; the campaign's is `a0982136…`. A reader may take it for the C_W coverage. The campaign's coverage
  record is `runs/w27-m07-83f825d/coverage.json`.
- **F-4: the harness identifier scan is narrower than W27-R56.** It covers 4 files per run (`SCANNED_FILES`), while
  R56 says "every run's committed files". The scan here covered all 389 files and found nothing. The harness or R56
  should be brought into agreement.
- **F-5: the decisions log says "ten" inaccessible assets.** `docs/V02_DECISIONS.md`'s WO-14 line says "Ten
  inaccessible assets", but `access_report.json`, the registration and M07 §7.3 say nine. The record governs. The log
  line is the session's to correct.
- **F-6: the local account name appears in committed files.** It appears in `run.json` (the interpreter path,
  required by W27-R58) and in `mcp.json` (the server command path). It is not the registered operator identifier
  (the login's e-mail address) and is noted only for anyone extending R6.6.
