# T06 — decisions log

Append-only; grepped, never read whole. Scientific choices are the design lane's (spec, ADR 0014,
register); this log holds Frank's answers and the build lane's decisions.

## 2026-09-25/26

**DECISION (build lane):** run the `architect` on F4 (recovery for a revision region that ends
`BOUND_BLOCKED`) inside T06 — the spec's Q1 — because it decides whether the 95% gate is reachable
and follows Frank's robustness steer. Brief `docs/briefs/T06-F4-recovery.md`.

**Frank (question tool):** spec Q3 — **support** permuted component order (map it; STA-04 becomes a
solved case, not a refusal); Q4 — **convert** non-SI units (kg/s → mol/s via molar masses, °C → K,
recorded; unknown units still refused) instead of a typed refusal; Q7 — the 95% gate on the
**point estimate** (≥ 418/440 on both architectures), the Clopper–Pearson bound reported. Q2
(validate revision flowsheets) and Q6 (K05 bundles for revision flowsheets) stay at their defaults
(T07/T08). Q3/Q4 change the spec (STA-03, STA-04, W1) → design-lane amendment.

**Phase M merged (`527f0e5`, `f140533`, `3e62ec4`).** M1: §2's pilot reproduced exactly (22
revisions under `benchmarks/t06/cases/`); M2: 20 of 22 eligible cases `VERIFIED` from their
initializers (NET-02 `BOUND_BLOCKED`, NET-11 `VerifierError`), medians ≤ 0.375 s; M3: F1, F2
reproduced; M4: ADV-06's hook needs no frozen change (L `VERIFIED`, M `UNVERIFIED` witness-only,
H `INITIALIZATION_FAILED`); M5: 460 `onenormest` calls on 258 matrices, no status/R0 change over 20
seeds, seed 20260925 gives the exact norm at all 258; M6: DWSIM and IDAES rebuilt (36 s) in the M6
worktree `.claude/worktrees/agent-ac0157a12bdd6640c` (kept: it holds the git-ignored environments
W8 needs), all 20 runs accepted/converged/self-consistent, one IDAES setting adjusted
(`constr_viol_tol` 1e-10 → 1e-9 on REF-04/05/06, the Pa-row double floor) — for the design lane.

**F4 design (`docs/design/T06-F4-recovery.md`, `b836796`):** edge 3 gains a sequential restart from
`traversal-G0-pass8-v1` for revision regions with no continuation parameter; probe: NET-02
`CONVERGED`/`VERIFIED`, 20/20 perturbed starts (9/20 without). **Frank (question tool, 2026-09-26):
approves** the two additive enum widenings (solve-policy `globalization.eo_recovery` +
`homotopy_or_sequential_restart`; solve-event `eo_recovery_unsupported` + `no_restart_initializer`,
`restart_start_unchanged`, `restart_initializer_failed`) → ADR 0015; **yes** to counting
restart-rescued starts as gate successes (rescued count reported per case) and to the restart as the
T07 product default. The architect's other defaults stand (Q4 G6 expected to pass; Q5
`LINEAR_SOLVE_FAILED` not a trigger; Q6 F6 — Rachford–Rice non-convergence in U-MIX's liquid
enthalpy at C3 pass 4 / NET-02 pass 29 — the build lane diagnoses; Q7 restart passes unmetered; Q8 no
restart after a stalled homotopy; Q9 pass count in the initializer id).

**Frank (question tool, 2026-09-26): spec Q11 — yes, in T06:** specifications (and parameters) accept
other common units (kPa, bar, kW, %, …) by recorded conversion; this widens ADR 0001 D1 (frozen) →
a new ADR (design lane); unknown units still refused.

**Merged (gate 3378):** W2/W3 (`5de724b`: NET-11 `VERIFIED`; typed verifier failures; seeded
`onenormest`; 562 certificates byte-identical under a fixed seed), F4 WO1–WO8 (`9d7f2ab`: ADR 0015,
R-075, enum widenings; NET-02 `VERIFIED` via the restart; G6 all cyclic cases; G7 20/20), W1a/W1b/W11
(`16f7919`: `unit-conversion-v1`, `canonical_components`, `InitializerFailedError`; A55–A62).
Merge fix `125f774`: G6 now includes STA-03 ×2 and STA-04 (they bind after W1), against independent
twin roots. **For the design lane (round 2):** F6 — the TP flash misclassifies a saturated liquid
(Σz·K rounds to 1+ulp while RR's f(0) rounds negative; `_rachford_rice` returns not_converged at
iteration 0; measured on 760 feeds: re-flashing the liquid product not_converged 6×, the vapour 15×);
the fix sits in `thermo/syn001.py` (identity, R-009/ADR 0011 D3) or in a unit-layer wrapper. W2:
seed 20260925 is not always the exact norm (A42 fixture). F4: δ = (2u−1)/5 vs literal `0.2*x`
differ by one ulp at some keys — clarify §6.3 before the generator. Pre-existing: the K03 fixture
`syn001_off_b_restart_trace.json` regenerates with 116 vs 115 property calls (R-015 gap); the K05
run-manifest fixture carries wall-clock fields. W1 choices: `declared_components` always recorded;
kg/s on a component outside the table `unit_unsupported`; empty component list
`components_unsupported`; DIM-01 order specs-then-parameters. W2 choices: reason spellings; rows
still eliminated when the shift fails; no alias check → can stay `VERIFIED`.

## 2026-09-26 — W4/W5 (build lane, worktree off `a01a9d4`)

- **DECISION:** the corpus is registered in its own sections (`policies`, `corpus`, `ensemble`,
  `reference_fixtures`, family `SYN-001-T06`), and `cases` is untouched. Alternative: one `cases`
  row per T06 fixture (T05's pattern), which moves the registry's own outside-denominator set and
  outcome vocabulary. Reversible by moving the entries. The corpus vocabulary is its own closed
  set (`CORPUS_OUTCOMES`, the twin's 14 spellings).
- **DECISION:** NET-05's "registered A02 policy" is `SolvePolicy` defaults under id `T04-W12`
  (`1f7d1172…`), the policy M2 registered its solve under; the reference fixtures' our-side
  policy is `T06-revision-v1` (W8 may revise). Reversible: one registry key each.
- **DECISION:** A02's tear and legacy-EO cases (NET-01, THM-03, THM-04, STA-03 tear, NET-05,
  ADV-01) are mapped to the K03/K04/T02/T04/W1a tests that measure them, not re-run; the 20
  revision-built cases are run under `T06-revision-v1` because no earlier test used it.
- **Stop-and-report:** VER-02/VER-03 — `INCONCLUSIVE(identity_mismatch)` has no path
  (measurements, W5 A19); strict xfail. Needs a design-lane decision: implement K04 A24's refusal
  in `screen`, or re-register VER-02/VER-03 against the verifier's `state_mismatch` guard.
- **For the design lane:** A20 names two exceptions (STR-05's twin, ADV-06 L), but §3.2 also
  registers VER-01's twin and VER-04's SQ-1 `VERIFIED`; W5 lists all four. W1a's A56 test runs
  STA-03's revision path under `T05b-v2` although A56 says `T06-revision-v1`; W5's A02 covers
  `T06-revision-v1` (VERIFIED, 2.09e-9). ADV-06 (A16–A18) is W7's and still pending.

**Merged (gate 3537 + 1 strict xfail):** W8 (`98ae08e`: DWSIM 8/8 AGREE; IDAES REF-03/REF-08
DISAGREE — IDAES's smoothed VLE places a bubble-point stream slightly two-phase, ≈7 W; PC-1/PC-2
DISAGREE as designed; nothing tuned) and W4/W5 (`6b16588`: registry 49/30/22; A02 23 revision runs
`VERIFIED`; VER-02/03 held — `screen` never compares `jacobian_identity`, so J + εI masks rank loss).
Both sent to the running round 2 (items 7, 8). Merge fix: PC-2 registered under
`reference_fixtures.positive_controls`.

**Frank (question tool, 2026-09-26): approves ADR 0017** — the F6 fix in `thermo/syn001.py`,
re-registering SYN-001's identity hash-only (every `model_version`, `plan_id`, K05 structural hash,
`t02`…`t05b` keys get new values; every number, outcome, trace and certificate stays the same). To land
as W13, one isolated commit after W15, with ADR 0017's two-step proof (A78, A79) and A77.

**Merged:** W8b (IDAES `eps = 1e-8 K`, rule 2b; blind re-run: IDAES 8/8 AGREE, table 16 AGREE / 3
DISAGREE (the positive controls) / 1 n/a; nothing for `verdict`), W14 (`screen` identity refusal,
VER-02/03 pass, 651 certificates byte-identical), W15 (b) docstrings. **DECISION:** W15 (a)'s K03
re-baseline committed although it changes 22 events' `property_calls`/`requested_evaluations`
(both forgiven counters), not one value as A81 (a) says → design lane amends A81.
**Information (another session, 2026-09-26):** OpenIDAES-450 (CRAFTS) audited on branch
`study/openidaes450` (`docs/openidaes450-audit.md`, `100a8ab`; MIT + written redistribution/
comparison permission) — candidate real-chemistry references (BTX flash, HDA, methanol/NRTL, …) with an
idaes-pse 2.11.0 vs 2.13.0 version gap; not used by T06's synthetic comparisons; relevant to T08's
real-chemistry selection. Do not merge that branch; cherry-pick the note if needed.

**W12 merged (gate 3681, 0 xfail).** `unit-conversion-v2` (ADR 0016) for specifications and
parameters; A67–A74 pass (A71's solve comparison cannot run — see Q2). All 44 registered revisions'
reports bit-identical except three DIM-01 messages (STA-03 ×2 prefix v1 → v2 as A55 (A2) requires;
STR-06's message per A72 (a), contradicting the W12 row's "every registered report unchanged").
**For the design lane (next touch):** Q1 — the twin's `registered_si_value` for five parameter pairs
is not the case files' (C1 efficiency 0.751 vs 0.75; C2 conversion.A 0.51 vs 0.5; split.C 0.051 vs
0.05; C3 split_fraction 0.61 vs 0.6; C2 drop 2500 Pa vs 0) — the generator hard-codes them; tests pin
the five mismatches. Q2 — C2 with any nonzero `U-RX.pressure_drop` is refused by `plan_revision`
(T01 `SPECIFICATION_CONFLICT`: a recycle loop with a pressure drop and no pressure-raising unit
over-determines its pressures — physically right; predates W12). Q3 — mutating a Quantity's unit in a
test rewrites its bounds in the same unit. A81 (a)'s wording (W15). W12's STR-06 message.

## 2026-09-26 — M7 and W6 (build lane; worktree `agent-ad00a0dccbbca61cd`, base `1f07cdc`)

- **DECISION:** the draw key's `<case id>` is the case's registered **fixture** id (the KATs'
  spelling: `SYN-001-nominal`, `SYN-001-A02-360`, `SYN-001-UL-C1`, `T05b:DZ-3`, …), not the corpus
  id. Alternative: the corpus id (`NET-01`), which no KAT uses. Reversible by: regenerating the
  starts before any scoring solve (design-lane amendment, §6.4).
- **DECISION:** step 5 on a perturbed revision start re-splits every outlet-style split by the TP
  flash of its perturbed stream, with no PH closure (`revision.lifted_split_values(…)` with every
  closure `None`) — "the split is a function of the stream" (§6.2). It equals the closure's split
  bit for bit on the bracket route (STR-01, NET-11: zero-perturbation assembly == `traversal-G0-v1`'s
  start); it differs on THM-08/THM-09, whose valve closed by the saturation route at `T_sat`, where
  the perturbed `S2.T` is off `T_sat` and the stream single-phase. Alternatives: keep the unperturbed
  closure's split (not a function of the perturbed stream), or re-run the unit's PH closure (would
  override the perturbed outlet). Reversible by: regenerating the starts before any scoring solve.
  **For design-lane confirmation.**
- **DECISION:** the generator (`benchmarks/t06/generator.py`, hashed into the starts file) is split
  from the harness (`benchmarks/t06/ensemble.py`: runner, scorer, reports, replay), so a harness
  edit never moves the recorded generator hash. Alternative: one module as §17 W6 names it.
- **DECISION:** the starts file carries per case what its 20 starts share (`x_init`, coordinates with
  scales and boxes, `held_zero`) and per start the rest of §6.5's list. Conditioning (`‖F̂‖∞`, exact
  `rcond₁`) is on the declaration's rows less the plan's eliminated alias rows; `null` with a reason
  for NET-05, whose region start is the pre-solve's output (§6.2). Reversible: regeneration.
- **DECISION:** `F-BUDGET` is K04's taxonomy class `budget/cancellation outcomes`
  (`BUDGET_EXHAUSTED`, `ATTEMPTS_EXHAUSTED`); `F-UNVERIFIED(<reason>)`'s reason is the regularity
  status when it is not `NO_RANK_LOSS_DETECTED`, else the first non-passing check ids. `RELAXED` (not
  reachable under the default check policy) would fall in `F-UNVERIFIED`: never a success.
- **DECISION:** `acyclic` = T01's structural report (the one the plan is built on) finds no loop. It
  counts **10** (THM-09 is the tenth); §6.2/§15 say nine — A84's finding, the flag unchanged.
- **DECISION:** the four wall times use M2's attribution (timing shims around `compile_problem` and
  the initializers, restored after each run); the numerics are untouched (A34's replay compares).

**W13 merged (`86ddc33`) — ADR 0017 applied (Frank approved).** `thermo/syn001.py` +11/−1: a failed
Rachford–Rice bracket returns the single phase its signs name (β 0 or 1). A78 (old hash substituted):
every certificate (662), fixture, identity key and T02 float byte-identical; only F6's registrations
differ (C3's restart). A79 (new hash): implementation `67e472816d4d…`; K05 structural **`915c97e8…`**
(was `4ce030ca…`), whole identity document `00ff5a9a…`; keys `t02` `0b75311a…`, `t03` `1b8a5b2e…`,
`t04` `c0b9bee7…`, `t05` `24199c7e…`, `t05b` `3f2feee2…` (full values `docs/t06-measurements.md`).
Re-flash failures 21 → 0 over 2 940 re-flashes. Fixtures regenerated (11 label-carrying schema
fixtures, nine `ours-*` reference records' certificate hashes). Closed packages' historical records of
`75c9d5ba…` left as they are (ADR 0017 C3). **W7 merged (`bc8cf32`)**: ADV-06 A16–A18 as registered.
Gate 3848.

**CI pair green at `cd6c501`:** SYN-001's new structural hash `915c97e8…` equal on x86-64 and
aarch64 (ADR 0017 D3 (3)). Two cross-machine test defects fixed on the way (A50: the certificate hash
is machine provenance; REF-08's iterated state differs in its last bits — floats compared to 1e-12
relative, with a guard test). **Amendment 3 (`docs/briefs/T06-amendment-3.md` §2):** TP re-split of
perturbed starts kept (A85); ten acyclic cases; draw key and F-BUDGET ratified; A70/A71/A81/W12-row
text amended (A71's solve half moved to NET-06); the starts file re-emits once under W13's provider
hash (W16 → `3a7bd49c…`; ADR 0017 D6 erratum recommended: the file does record the provider hash).

**Information (another session, 2026-09-26):** ADR 0008 Amendment 1 (Proposed; branch
`adr/transient-readiness-2`, `5d4da9a`/`41e2904`) adds Job-schema rules J1–J6 for T07; advisory until
Frank accepts it. It edits `docs/interfaces-frozen.md` §2's K06/T07 row; T06 edits §3 (ADR 0014–0017
notes) — expect a small textual merge when both land. No T06 action.

**W9 — the `t06` key (build lane, 2026-09-26).**
- **DECISION:** every `t06` entry runs under its **registered** policy (registry corpus row,
  `reference_fixtures.policy`, ADV-06's revision path `T06-revision-v1`); NET-02's `T05b-v2` control
  is a separate entry (`controls["NET-02|T05b-v2"]`, `BOUND_BLOCKED`). Alternative: every base entry
  under `T05b-v2` (M1's contract, which §10 was written against before A1) plus NET-02 under
  `T06-revision-v1`. Both readings satisfy §10's NET-02 sentence; the chosen one records what the
  registry registers. Reversible by: the policy constants in `scripts/t06_identity.py`.
- **DECISION:** §8.7's 400 K message is recorded verbatim (first line), although it carries one
  computed `{:.3g}` number (`… by 300 K …`); every other entry's message is float-free (tested).
  Alternative: truncate at A62's registered prefix. Reversible by: `_initializer_failures`.

**Scoring run 1 (local x86-64, 2026-09-26, HEAD `dfa7d09`, starts `3a7bd49c…`, 54 s):** **S = 431 of
440** (first 367, rescued 64; Clopper–Pearson lower bound 0.9646 on S, 0.8021 on S^first). Classes:
SUCCESS 431, F-BUDGET 3 (THM-08 ×2, THM-09 ×1), F-FALSE-SUCCESS-CAUGHT 2 (THM-09), F-OTHER-ROOT 4
(THM-09). **Gate: FAIL** — the count clears 418, but the gate's "no unexplained F-OTHER-ROOT" clause
fails (4, THM-09). Also reported: A33 failures 137 (certificate qualification statements). Replay
matched. A failed gate stays failed; nothing tuned. Run file kept in the scratchpad (`scoring/`);
diagnosis delegated (measurement only), then a design-lane ruling.

**Scoring-round rulings (amendment 4, `fee8df5`):** run 1's FAIL stands (not re-judged). THM-09's four
F-OTHER-ROOT are the registered root stopped early; remedy ADR 0018 (one terminal Newton refinement
when the exit's own first-order error estimate exceeds S3's allowance/10; outcome never changes;
policy `T06-revision-v2`). Two-phase closure corrected (max distance to bubble/dew temperature vs
τ_T; the old form was identically 0) — moves four closed-package expectations (T05b B34 (a), B16,
B26; one T04 fixture) and catches NET-11 start 16's false TWO_PHASE label. Counter recorded from the
meter. A33 wording. No budget or allowance change; SYN-001 identity unchanged. **Frank (question
tool, 2026-09-26): approves ADR 0018's enum widening** (`solve-policy globalization.eo_core` +
`newton_refined`) **and** `newton_refined` as T07's application default.

**W19/W20/W22 merged.** Corrected closure (A91: NET-11 start 16 `FAILED` at 3.3368 K, old form 0.0;
673 closure evaluations); exactly four re-registrations (A92: T05b B34 (a) 66/10/6 → 66/6/10 — the four
`(0, 115|125 kW, 90 kW)` pairs now `FAILED` with closure 30.70/23.78 K; B16/B26 gain `U-PHF.S1.closure`
1.0055e-6 K in their at-stop list, still `VERIFIED`; the T04 HOM-01 fixture's tolerance/reference);
counter equals the meter (A93; two T04 trace fixtures +1/+2 property counters); A33 amended wording
(W22). Identity: everything unchanged. Engineer's decisions: `unsupported(closure_nonpositive_phase)`
for a non-positive phase total (never occurs); "charged" = calls made while a region's budget is set;
`COMPOSITION_TOLERANCE` removed (unused). **For the design lane:** A92's text says dew-point closures
"≥ 9.5e-4 K", measured minimum 9.494e-4 K — the engineer registered 9.4e-4 in the test; a registered
number must not be lowered by the build lane → amend or confirm (next design touch). Note: a restart's
budget now comes from the correct count, so a start exhausting right at the boundary could differ in
run 2.

**W18 merged (`f636452`):** ADR 0018 (enum widening isolated `9e5a7d2`; refinement; `T06-revision-v2`
`c03d7205…`); THM-09's four run-1 F-OTHER-ROOT now ≤ 2.17e-5 of the allowance; identity minus `t06`
unchanged, `t06` key `e0e871f6…`, whole document `9a7b4e6d…`. W21: cost attributed (band route 39–62 %
of calls), no fix landed. **For the design lane:** a budget run-out inside a refinement is marked
`BUDGET_EXHAUSTED` by the executor (contradicts "never changes an outcome"; not hit); "rejected trial"
read as a failed line search; a chord back-solve failing ADR 0004's residual test abandons with
`terminal_refinement(abandoned: chord residual)`; committed `certificate_sha256` of REF-03/04/05, PC-2
were stale since W19 (A50 skips that field).

**Scoring run 2 — gate PASS on both architectures.** Local x86-64 (HEAD `f636452`, 55 s): S = 434/440
(first 370, rescued 64; F-BUDGET 3, F-FALSE-SUCCESS-CAUGHT 3); no F-CRASH, no F-OTHER-ROOT; A32 clean;
A33 0 failures; replay 28/28 MATCH. CI dispatch run **36270294833**: `ensemble (ubuntu-latest)` S =
434/440 PASS (first 370, rescued 64), `ensemble (ubuntu-24.04-arm)` S = 434/440 PASS (first 367, rescued
67; F-BUDGET 4, caught 2), `ensemble-compare` success (21–22 differences under the numerical policy,
reported). Clopper–Pearson lower bound on S 0.9733. Run files in the scratchpad `scoring/run2_*`.
**Test fix:** T05b B34 (a)'s pinned closure values of two caught false successes are x86-64-only
(aarch64 lands one 16.16 K vs 23.78 K from saturation — roundoff-sensitive beside a singular dew
point); every platform still asserts `FAILED` on the closure alone by ≥ the floor (`8f84dc0`) —
for the design lane's review.

**Review (`bc9ef84`) and verdicts (`167bfd4`).** Review: ready once M1 is closed (ADR 0018's "never
changes an outcome" is false under the property budget — a refinement can turn CONVERGED into
BUDGET_EXHAUSTED; fix = amend the sentence + a plan-level test); S1–S5; the four weakened tests judged
legitimate (two need spec text). Verdicts: references met; gate met on run 2 (both architectures;
legitimate re-score); no false verification met for run 2 and the corpus, **not for run 1** (four
F-OTHER-ROOT and the missed NET-11 start-16 false success — the record stands). Evidence gaps: A90
(refinement firing not recorded), CI records mislabel their machine class (`generator.py:695`), run
records lack commit id and `cache_condition`, run files only in the scratchpad/CI artifacts; §7.3
self-contradiction to amend. **Frank (question tool, 2026-09-27): yes — run a fresh-draw holdout
ensemble in T06** (440 new starts, same law, reported not gated); **keep `newton_refined` as T07's
default** despite M1.

**W24–W27 merged (gate 4080; protocol unchanged).** A96: `newton_refined` exhausts at caps 365–385
where `newton` converges, converges at 386 (M1 documented, not changed). A100: `units.read_number`
reads |n| > 2⁵³ as ±∞ everywhere (64/64). A50: our-side records without `certificate_sha256`;
verdicts unchanged. A92: floor `NEAR_THRESHOLD_MARGIN²·τ_T` (1e-4 K); minimum closure 9.49× it.
**T07 gap (with R-088's questions):** the legacy binding (R1) accepts `True` as 1.0 and `"300"` as a
specification value and raises an untyped `ValueError` on `"abc"`; R1/R3 keep `float()` for
non-numbers. `units` imports `canonical._MAX_EXACT_INTEGER` (private) to keep ADR 0002 D3.3's bound
in one place.

**W31 (at `6018ebc`; ref-x86-64 local and CI dispatch 36278604955):** run 2r S = 434 on ref-x86-64,
ci-x86-64 and ci-aarch64 (370 + 64 / 370 + 64 / 367 + 67), A98 0 discrepancies, 0 final states
differing bitwise on ref-x86-64, refinements 17 fired / 17 kept / 0 reverted / 0 abandoned (= the
reconstruction); **holdout1 S = 436 of 440 on all three** (364 + 72 / … / 367 + 69; reported, never
gated; CP lower bound 0.9793), refinements 16/16/0/0; no F-CRASH, no F-OTHER-ROOT; A32/A33 clean;
replays MATCH. Cross-platform per-start class differences on THM-09 only (run 2r start 03; holdout
35, 37) — per-start outcomes are not portable (verdict qualification). Test fix: A97 (c)'s absolute
counts pinned on ref-x86-64 only (`7ec1b59`; NET-05/0 430 on aarch64). Files committed under
`benchmarks/t06/ensemble/runs/`.
