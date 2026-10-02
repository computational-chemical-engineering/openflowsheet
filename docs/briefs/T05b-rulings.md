# Brief — T05b ruling round (one batch; build lane → design lane)

**To:** `specifier` (design lane). **From:** build lane, 2026-09-25. **Branch:** `wp/T05b`.
**Deliverable:** rulings written as dated amendments into the documents they touch
(`docs/derivations/T05b-limitations-spec.md`, `docs/derivations/K04-F9-spec.md`, ADR 0012/0013, the
register only for a choice a later session could undo) and a ruling list in §4 of this file: per item
the ruling, the build-lane change (if any) and its acceptance test. No registered number of
`benchmarks/t05b/…` or `benchmarks/k04f9/…` may change without saying so and why (re-emit the twin
if one must; `--check` must pass). Do not edit code; do not commit.

## 1. Where T05b stands (measured; `docs/t05b-measurements.md`, `docs/T05_DECISIONS.md`)

W0–W7b and F9 W1–W6 implemented; gate 2992 + 2 strict xfails; protocol unchanged throughout
(SYN-001 identity, structural hash, check policy, T02 floats, T05 PH baseline). SC-1…SC-4, NP-1…3,
NP-G, NP-GC, DZ-1…DZ-12 as registered, except the two items in Q-S1/Q-S2. A02 family 179/179
`VERIFIED` under ADR 0013.

## 2. Questions

- **Q-S1 (F9 X26 at NP-GC).** Recorded solution-error bound `b = 1.212e-7`, above X26's `1e-7`; NP-GC's
  streams sit 46× inside their allowances. Is NP-GC in X26's scope, or does the rule change? (Strict
  xfail in the gate.)
- **Q-S2 (F9 X21 at NP-1).** Floor ratio 171130.3 against the registered 171213 (4.8e-4 relative); a
  2.14e-11 K band is below double resolution and §7's floor argument does not cover it; NP-1 is
  degenerate so the ratio decides nothing. Amend X21's tolerance/scope? Also: the reference prints
  routing ratios to 6 digits (up to 4.2e-6 off); the test compares against the closed form from the
  20-digit fields — ratify.
- **Q-S3 (W6).** (1) NP-G's bound 7.0e-8 vs T05b §13's `1e-8` — is that now governed by X26's amended
  rule (`b ≤ 1e-7` with a registered state comparison)? (2) A products-style split's opening sets only
  the vapour product's temperature column; `PHF-T` closes the liquid's — confirm. (3) B07's "except
  the policy literal" = except `policy_id` and plan ids containing it — confirm. (4) B11's pre-change
  value is W0.1's measurement — fine?
- **Q-S4 (W7b).** (1) W0.11 (b): T01/K03 remove `U-MIX:MIX-pressure:1` at DZ-9 only when feeds are
  declared before the mixer (else `U-FEED-1:FEED-P`); `dz9()` declares feeds first, as the twin —
  should the spec state the order dependence, and is either removal acceptable? (2) F8's premise was
  false (`hot_end`/`cold_end` already `not_applicable` at a dormant inlet); what changed is that
  `heat_flow` is now judged — amend F8. (3) B29 names `energy_balance.U-HX`; table ids are `.hot`/`.cold`.
  (4) Terminal checks' `not_applicable` reason `ZERO_FLOW` vs the spec's `zero_flow`. (5) The outlet
  reset applied to a fixed point (a pump feeding a pump). (6) Recorded property: with an empty
  signature Newton does not screen trials; on a flowsheet without lifted splits only the closure
  agreement (§7.8 (iv) 1) catches a trigger going dormant — acceptable as stated, or needs a screen?
- **Q-S5 (F9 engineer decisions).** (1) D2 applied only where the provider's flash returns two phases
  (§5.2's literal order would break its own bitwise promise for a stream within `ε_adm` of both
  boundaries — only a degenerate pure stream); (2) guard 4's "every flow" = K04 §4.6's flow columns;
  (3) a row that cannot be evaluated at `x̃` counts as `projection_rows_not_passed`. Ratify or amend.
- **Q-S6 (W3–W6 decisions, ratify as a block or name changes).** The v2 refusal until W6/W7 (now
  removed); the R-007 pre-screen (0 mismatches over 35 540 gate calls and a 126 420-call sweep); W7's
  start rules (`projected(S, <branch>, ZERO_FLOW)`, branch word `zero_flow` under v2); `ZeroFlowForm`
  beside `LiftedSplit` (W1.a's repr digest).
- **Q-S7 (information, build lane will act unless you object).** The K05 `run_manifest` schema
  fixture's certificate hash was already stale at `main` before T05b and the gate does not check it
  (R-015 gap).

- **Q-S8 (W8).** (1) §16 says the manifests "drop" the dormant statement while T05's amendment says it
  is "kept for what T05b does not cover"; the engineer dropped the T05-era texts and stated what still
  holds under the default v1 contract (T05's EO outcomes; the dormant-duty conflict typed) — ratify;
  (2) §16 names an exchanger dormant-inlet EO statement that did not exist; the engineer kept the
  causal refusal and added the EO conflict and "terminal differences not judged at a dormant side";
  (3) W0.7 on the implementation: NP-G and 29 heavy/light trace runs from 3e-8 to 3e-6 mol/s all
  `CONVERGED` and `VERIFIED` — the emulated `FAILED` band is gone; heavy trace degenerate at 3e-8,
  unresolved 5e-8…≈1.3e-6; light degenerate ≤ 7e-8, unresolved 1e-7…≈1.7e-6 — supersede spec Q5's
  default; (4) W0.9: all T05b cases with a state comparison `b ≤ 1e-7` (worst DZ-3/DZ-10 3.679e-8);
  NP-G 6.978e-8 (no comparison); NP-GC 1.212e-7 (Q-S1); unregistered sweep states reach 1.07e-7;
  (5) the `t05b` identity key's certificates carry near-threshold flags compared exactly across the CI
  pair — DZ-3/DZ-10 `PHF-equilibrium:C` at 0.119 τ (19 % above the 0.1 band edge), NP-2 `.saturation`
  0.159 τ — is a flag an R0 field that should be, or is the margin enough?; (6) T05's evidence
  generator run at the T05b head fails A23 (later packages add tests, edit K02–T04 tests for F9, move
  the fixture tree) — T05's evidence stays at `91ac010`; confirm no action.

## 3. Anchors

`docs/T05_DECISIONS.md` entries after "Frank reverses" (W3–W5, W6, W7, W7b, F9) carry each item's
numbers and commit; `docs/t05b-measurements.md` the measurements.

## 4. Rulings (the design lane fills this in)

*Ruled 2026-09-25 by the design lane (`specifier`). Q-S9…Q-S11 were added mid-round from the
implementation review (`docs/reviews/T05b-review.md` M1, S1, S2). Documents amended, each change
dated in place: `docs/derivations/T05b-limitations-spec.md`, `docs/derivations/K04-F9-spec.md`,
`docs/derivations/K03-solver-spec.md` §5.3, ADR 0012, ADR 0013; register R-063, R-064, R-065 new,
R-053, R-058, R-060 amended. **No reference file is re-emitted:** `benchmarks/t05b/reference_values.yaml`
stays `7870bbc9…` (585 claims) and `benchmarks/k04f9/reference_values.yaml` stays `73be8df9…`
(25 claims); neither generator is edited. **What moves, stated:** the `t05b` identity key's SC-3 and
DZ-12 entries (Q-S11 (a)), and possibly SC-2's regression outcome under `T05-W13` (Q-S11 (b)).*

*Amended 2026-09-25 (design lane, `specifier`): the Q-S9 addendum (the build lane's W9.3
stop-and-report) and Q-S12…Q-S14 (the W9 re-review, `docs/reviews/T05b-review.md` M2, S-W1, N-W1,
N-W7) follow Q-S9 below. **The `t05b` reference file is re-emitted by the addendum**, superseding the
sentence above for that file: one section (`downstream_flash_cases`) and 45 claims are added and no
existing value moves — `7870bbc9…` (585 claims) → `cf1a86067f3de92266b1e121ee9711e6e5f235d0bf87657afd231996f5fc807b`
(630 claims, 4 143 lines; `--check` passes, `--emit` byte-identical twice). The K04-F9 file does not move.*

Each item below gives the ruling, the build-lane change, and the acceptance test.

**Q-S1 — X26 at NP-GC.**
- *Ruling.* NP-GC is in X26's scope. It is a T05b EO case with a registered comparison, and
  excluding it after a failure would narrow the denominator. The rule itself was wrong. It
  thresholded `b = ‖Ĵ⁻¹‖₁‖F̂‖∞`, which tracks where Newton (or the kernel's row-tolerance acceptance)
  stopped, not the error. This is K04 §7.4's own lesson of 2026-09-22. `b` overshoots the realized
  scaled deviation 4.5× at DZ-3 and 54× at NP-GC.
- *New X26.* (a) For every registered T05b comparison at T02 §6.4's allowances, the realized
  deviation is `≤ 1/10` of each allowance. That is ADR 0007 D2.4's edge, and T05b §13's margin claim
  made executable. The population is SC-1…4, NP-1…3, DZ-3, DZ-10, DZ-12, NP-GC, plus B31 (b)–(c) and
  B33 (b) (NP-G temperature only). (b) `b` is recorded as a regression value and never thresholded.
  Measured: NP-GC 0.022, DZ-3/DZ-10 0.081. Register R-063.
- *Build lane.* In `tests/test_k04f9_t05b.py`:
  - drop `B_ALLOWANCE`'s assertion, NP-GC's strict xfail and
    `test_x26_np_g_meets_the_allowance_without_being_held_to_it`;
  - keep the `b` regression pins as at `85d4c96`;
  - add the per-case ratio assertion;
  - record the ratios in `docs/t05b-measurements.md`.
- *Acceptance.* X26 passes for every case, with no xfail. Any ratio `> 1/10` is a stop-and-report,
  never a widened allowance.

**Q-S2 — X21 at NP-1; the six-digit ratios.**
- *Ruling.* The tolerance was below NP-1's quantization floor. `2 ulp(T)/w = 5.3e-3` for a band 377
  doubles wide, and the first text argued the floor from NP-G alone. The new tolerance for the
  X09/X10/X21 floor ratio is `max(1e-6, 4 ulp(T)/w)` relative. That is 1.06e-2 at NP-1 and 1e-6
  everywhere else, and gives a margin of at least 2 on the quantization bound by construction; the
  measured error at NP-1 is 4.8e-4. The expectation is the closed form of `ref`'s 20-digit `T`, `N`,
  `T_b`, `T_d`. The printed six-digit value is checked as that value rounded (it alone can be off by
  up to 5e-6). The engineer's closed-form comparison is ratified.
- *Build lane.* In `tests/test_k04f9_rules.py`: apply the per-entry tolerance and retire NP-1's
  strict xfail. X09/X10 are as implemented.
- *Acceptance.* All 51 routing entries pass. NP-1's relative error is recorded.

**Q-S3 — W6 items.**
1. NP-G's `b` is governed by X26 as amended again. NP-G registers no comparison, so its `b` is
   recorded only. The `1e-8` rule is gone for T05b.
   - Build lane: none beyond Q-S1.
2. **Not confirmed**, reversed with Q-S11 (a). An opening writes the closure's `T` to every product
   temperature column (spec §6.2). The review measured the stale liquid temperature costing NP-G's
   restart.
   - Build lane: see Q-S11 (a).
3. Confirmed. "Except the policy literal" means equal after substituting the v1 policy id for the v2
   one in `policy_id` and in the plan ids that embed it; any other difference fails. This is the
   test's substitution (spec B07).
   - Build lane: none.
4. Confirmed. The manifest cites W0.1's measurement at `b8c6442` for B11's pre-change clause. It is
   not re-measured, and no test claims to measure it (spec B11).
   - Build lane: none.

**Q-S4 — W7b items.**
1. The spec now states the order dependence (§12.8, B24, W0.11 (b)). DZ-9 is registered with its
   feeds declared first. Either removal is acceptable: a consistent redundant pressure pair, and a
   square, regular form either way.
   - Build lane: add DZ-9 declared mixer-first to B24.
   - Acceptance: `CONVERGED` at iteration 0; `VERIFIED`; dimension 15; `S3.T == 330.0`; rows equal
     to `ref…zero_flow_form` minus the plan's `eliminated_rows`, which hold exactly the second feed's
     `FEED-P` (regression).
2. F8 is amended (§19). The table never judged `hot_end`/`cold_end` at a dormant inlet; the change
   is that `heat_flow` is now judged.
   - Build lane: none.
3. B29 reads `energy_balance.U-HX.hot`, and `energy_balance.U-HX.cold` must pass.
   - Build lane: B29's test asserts the failing set is a subset of {`residual.U-HX:HX-energy-hot`,
     `energy_balance.U-HX.hot`, `energy_balance.envelope`} that contains the first, and that `.cold`
     passes.
4. Ratified. The reason is K04's existing `ZERO_FLOW` (§9.3, B25, ADR 0012 D7; R-058 amended).
   - Build lane: none (as implemented).
5. Ratified and extended. Items, resets and lifted splits' `ZERO_FLOW` membership now form one fixed
   point (Q-S9), and a reset is redone when a later write makes it stale (review N1). "At most once"
   is withdrawn.
   - Build lane and acceptance: under Q-S9, B31 (f).
6. **Needs a screen.** §7.8 (iii)'s "every trial" includes an empty signature. The `signature and …`
   shortcut in `numerics/newton.py` meant that a trigger going exactly dormant was caught only at
   closure, after the declared form's Jacobian had gone singular.
   - Build lane: screen every trial of a v2 attempt in a region with a dormancy-form outlet. The
     region reports items at trials whatever the frozen signature, and the Newton core flags a
     reported signature that differs from an empty frozen one.
   - Acceptance:
     - (a) A Newton-core test: a stub problem with a frozen signature `()` whose trial evaluation
       reports `((X.outlet, ZERO_FLOW),)` gives a `phase_update_required` rejection.
     - (b) A region-level test: the trial evaluation of a v2 region with a pump, no lifted split and
       no item, at a trial state whose pump inlet is exactly `+0.0`, reports the item.
     - (c) Inertness: the `t05b` key, B07, `t05` `ddbd0f71…`, identity minus both `b364bb3d…`, T02
       floats `9a8a5baf…` and every K03–T04 test are unchanged.

**Q-S5 — F9 engineer decisions.** All three are ratified as implemented (K04-F9 §5.1, §5.2; ADR 0013
note; R-060 amended).
1. The provider decides first. The two `ε_adm` tests replace only a two-phase answer, in
   `admissibility_checks`' arithmetic.
2. Guard 4's "flow" is K04 §4.6's stream-flow predicate. The exact-zero rule keeps the kind.
3. An unevaluable row at `x̃` gives `projection_rows_not_passed`, already tested.
- *Build lane.* Add one X02 case: a molar-flow-kind column that is not a stream flow (a reaction
  extent) stepping negative at `x̃` is **not** `projection_outside_domain`.

**Q-S6 — W3–W6 decisions.** Ratified as a block. Written into the spec:
- W7's start rules (§6.4);
- the R-007 pre-screen, with its argument and measured equivalence (§10).

The v2 refusals are removed. `ZeroFlowForm` beside `LiftedSplit` is the build lane's structural call.
The W7 note "RuntimeError (unreachable)" was falsified by the review; Q-S9 puts a typed fixed point
in front of it.
- *Build lane.* None beyond Q-S9.

**Q-S7 — the K05 `run_manifest` fixture's stale certificate hash.** No objection. This is tooling,
and the build lane acts. It should:
- regenerate the fixture with its generator, never by hand, in its own commit, recording the old and
  new hashes;
- add the missing comparison of the fixture's `solution-certificate.json` hash with the emitted one
  as a test in the gate, closing the R-015 gap.

Acceptance: the new test passes and fails on a one-byte edit of the fixture.

**Q-S8 — W8 items.**
1. and 2. Ratified (§16). "Drop" means replace with what holds now. The exchanger had no EO statement
   to drop, and §16 was wrong to name one.
   - Build lane: none.
3. Q5 is answered by W0.7 (§18, §17, §11, §12.4). There is no `FAILED` band. The unresolved band
   runs to ≈1.33e-6 mol/s (heavy) and ≈1.71e-6 mol/s (light), where the floor ratio ∝ 1/ε crosses
   1/10.
   - Build lane: none.
4. Governed by Q-S1.
5. Flags stay R0 fields (ADR 0007 D2), and the key keeps DZ-3, DZ-10 and NP-2 with their flags.
   - Measured equal on the CI pair at `85d4c96`.
   - The argument: the key's solver counters already force one iteration path. On it, a flagged
     residual moves only by roundoff, orders inside its 0.019 τ_eq to the edge. NP-2's `δ` moves by
     at most one ulp against 5.9e-8 K.
   - NP-G stays outcome-only, for a corrected reason. After ADR 0013 its fresh flash is no lottery,
     but its duty residual is the value at whichever adjacent double of `T` the causal kernel
     returned, where one ulp moves `H` by ≈0.83 τ_E.
   - Recorded in B22.
   - Build lane: none now. A CI disagreement goes to the design lane, and the key is never edited to
     pass.
6. Confirmed: no action (§16).

**Q-S9 — review M1 (must-fix): openings inconsistent with dormancy.**
- *Ruling* (spec §7.4, §7.8 (ii); R-065). At every v2 opening — attempt 0 after the start
  projections and rules, and every restart after the candidate's regimes, pins and kernel answers —
  passes in declaration order do two things until a pass changes nothing:
  - (a) re-derive every lifted split's `ZERO_FLOW` membership from its feed's exact dormancy.
    Entering pins the lifted flows at `+0.0`. Leaving takes the TP flash of the feed, with
    `fallback(<U>, tp)` for a PH-type split.
  - (b) re-derive every item. An outlet whose item differs from its reference (the previous
    attempt's, or at attempt 0 the supplied start's) is reset whenever its flows differ from its mole
    balance.
- The signature is read off the final state. If pass `m + 1` still changes something, the region
  closes `ACTIVE_SET_CYCLING` with `opening_not_settled(<id>)` — typed. The `RuntimeError` guard
  stays behind the fixed point. No new record grammar.
- *Build lane.* Implement it in its own commit, with inertness proved first.
- *Acceptance* (B31 (a)–(h)):
  - CH-UP, CH-DZ12 and CH-3 are `CONVERGED` and `VERIFIED` against DZ-12's registered root and its
    copies. The attempt leaving `ZERO_FLOW` carries `fallback(U-PHF2, tp)`.
  - CH-DOWN is `CONVERGED` and `VERIFIED` with `U-PHF2` exactly dormant and labelled.
  - CH-DORMANT (both orders): attempt 0 is `[[U-PHF, ZERO_FLOW], [U-PHF2, ZERO_FLOW]]` and the run
    is `VERIFIED`.
  - The order variants are equal to their declared-first cases.
  - The two-pump opening gives exact copies (both orders).
  - A stubbed non-settling fixed point gives the typed outcome.
  - The `t05b` key, B07, B21 and B30 are unchanged on this commit.

**Q-S9 addendum (2026-09-25) — the build lane's W9.3 stop-and-report: B31 (b)'s `VERIFIED` is unmet.**
- *Ruling: the diagnosis is confirmed; B31 (b) is amended, not the code.* The closed form puts every
  `Q = 0`, `ΔP = 0` downstream flash exactly on its dew point with its liquid product zero. There the
  lifted equilibrium rows `v_i N_L − K_i l_i N_V` see only the liquid flows and `N_L`, and their block is
  `v 1ᵀ − N_V diag(K)`, of determinant `(−N_V)^n ∏K (1 − Σ y/K) = 0`. So the declared form K04 screens is
  singular (null vector: condensation `δl ∝ y/K`, balanced by `δT`). This is a property of the lifted
  form (P02 §2.4 already registers regularity only "away from the bubble/dew point"), not of the fix.
  The twin now registers it (`ref.downstream_flash_cases`: CH-UP 30 of 31, CH-3 42 of 44, null spaces,
  the determinant identity, the bubble-point mirror). `VERIFIED` was the design lane's error, taken
  from the review's "I expect"; the re-review's N-W2 agrees.
- B31 (b) now asserts `UNVERIFIED` (never `VERIFIED`), `RANK_DEFICIENT`, rank loss one per downstream
  flash (1, 1, 2), and no check `fail`/`unsupported`. The limitation goes into spec §17, and into
  `syn001.ph_flash`'s limitation text (§16, verbatim sentence).
- **B31 (i), new:** CH-UP-DP, CH-DZ12-DP, CH-3-DP — the same cases with every downstream flash at
  `pressure_drop = 10 000 Pa` — must be `CONVERGED`, `VERIFIED`, `NO_RANK_LOSS_DETECTED`, with (b)'s
  attempt outcomes, signatures and messages and (b)'s closed form (products at `P_in − 10 kPa`, `T` unchanged, `VAPOR` determined:
  `Σ y/K − 1 = −0.0997`, `−0.1995`). *Measured by the design lane:* all three pass.
- *Why a pressure drop, not the re-review's `Q2 = −3 kW`:* a duty on a flash whose feed is dormant at
  the start makes the start rule refuse (`duty_into_dormant_stream`, measured). P13 therefore started
  from another revision's traversal, which changes the case. The pressure drop keeps the flowsheet,
  the start rule and the leaving path, and its closed form is a copy.
- *Frank:* §18 Q9 — certify such boundary roots through a regime-reduced screen. The default is not in
  T05b; it is queued as a K04 follow-up beside T04 Q8.
- *Build lane:* spec §20 W10 (1) and (5).

**Q-S12 — re-review M2 (must-fix): `at_candidate` asks a downstream kernel after an upstream answer
rewrote its feed.**
- *Ruling (spec §7.8 (ii) 5; the reviewer's option (A)).* Under both literals: fix the candidate state;
  ask every changed unit's kernel there and check its regime against the reported one there (N4's
  guard, unchanged); only then write all answers (disjoint columns, so order is immaterial); then
  settle dormancy (items 1–4). This is T03 §4.5's "the kernel *there*" taken literally.
- (B) is rejected: it keeps the order dependence and opens with a regime the screen never reported.
- *Measured with (A) substituted (P10's sweep, 104 solves):* no exception, and every pair gives the
  same outcome and final regimes in both declaration orders. The unmodified code raised 15 times.
- *Build lane:* W10 (2). *Acceptance:* B34 (the registered sweep; a function-level test with a
  control that reproduces the raise; inert on every registered record).

**Q-S13 — re-review S-W1 and N-W7: the release's opening; which §5.3 PTC means.**
- *Ruling (K03 §5.3 note).* Confirmed: "the attempt's opening state" is the attempt's. Add an
  `opening=` keyword to `solve_newton`, defaulting to the call's start. `_homotopy`'s corrector
  passes the attempt's `x⁰`. Every other caller is unchanged.
- *N-W7 (T04 §7.5 note).* The PTC core's pseudo-steps and polish mean K03 §5.3's first paragraph,
  without the release; W9.5's Newton-only scope is ratified. The release's proof uses `J`'s
  nonsingular closed-row block, and `J + D/Δt` does not have it as it stands. Extending the release
  to PTC is a T04 amendment on a measured case.
- *Build lane:* W10 (3). *Acceptance:* B35.

**Q-S14 — re-review N-W1: the leaving TP flash reads a stale temperature.**
- *Ruling: the code moves to the text, and the text is made exact (§7.4, §7.8 (ii) 1 (a)).* The
  flash uses the feed's `n` and `T` and the split's outlet `P`. For a PH-type split, its `T` is
  written to every temperature column of the split's streams.
- The reviewer preferred amending the text to the code. That is rejected. The split's own `T` is an
  earlier feed's zero-flow label, i.e. attempt history, and Q-S11 (a) already ruled that history
  must not decide an opening. The change costs nothing measured (P14) and removes a wrong-regime
  opening whenever the label is far from the feed. A TP-type split keeps its specified `T`.
- *Build lane:* W10 (4). *Acceptance:* B36. Only B31's leaving records move (iteration counts), and
  they are re-registered.

**Q-S15 (2026-09-25, design lane, `reviewer`) — the build lane's W10.4 stop-and-report and its two
W10.4 decisions; the review of W10 (`docs/reviews/T05b-review.md`, "Review of W10").**
- *(1) B34 (a)'s counts moved: ratified, with a tally added.*
  - The new regression counts are 82 `CONVERGED`, 10 `ACTIVE_SET_CYCLING`, 6
    `SPECIFICATION_CONFLICT`, 4 `STAGNATION`, 2 `BOUND_BLOCKED`.
  - Why they moved: B36 is the ruled change, and the runs that moved are the leaving path it
    targets (`Q2 = 0`, `Q_s = 0`, both orders, 8 runs). B36 (c)'s list missed them; the stop was
    right.
  - `(0, 0, 115 kW)` goes from cycling to `CONVERGED`, at the same `VERIFIED` root that the other
    three 115 kW starts reach (within 1.14e-8 of the allowances). This is the stale-label restart
    Q-S14 predicted, now measured.
  - Added to B34 (a): the certificate tally of the `CONVERGED` runs, as a regression value — 66
    `VERIFIED`, 10 `UNVERIFIED`, 6 `FAILED` — and each pair's orders agree on it.
  - The six `FAILED` are false successes, and the verifier catches every one
    (`false_success_detected`): `(0, {90, 115, 125} kW, 30 kW)`, both orders.
  - They are §17's dew-point singularity acting on the solve. Before W10, four of them already
    ended this way, and the other two raised M2's error.
  - §17 and §16's limitation sentence are corrected to say so.
  - Why the region's energy row passed while the verifier's balance failed by at least 0.37 mW at
    the same state is not established. It joins §18 Q9's K04 follow-up.
- *(2) "The feed's `T`" for heater-style splits (valve, duty-mode reactor): the build lane's reading
  is ratified.*
  - The feed is §7.1's feed: for a heater-style split, the split's own outlet. That flash is
    unchanged, and nothing is written.
  - Q-S14's hazard needs an opening that writes a feed but not its label. No opening writes a
    heater-style feed except the split's own answer.
  - Where such a split leaves, the linear label row holds its `T` to the label source. The one
    exception is a halved candidate taken from an attempt's first iterate, where both values are
    trial values.
  - Rejected: the label source's `T`. It gives the same value wherever it matters, and it moves
    bits.
- *(3) The screen's leaving report: yes, the feed's `T`, and the guard no longer exempts a leaving
  answer.*
  - At a trial, a PH-type `ZERO_FLOW` split whose feed flows reports the TP flash at the leaving
    answer's inputs: the feed's `n` and `T`, and the split's `P`.
  - `at_candidate`'s `sanctioned` clause no longer covers an answer whose attempt regime is
    `ZERO_FLOW`.
  - Why: B36 broke the premise on which the re-review accepted that exemption ("the screen and the
    kernel use the same TP flash"). Left alone, the cause string could name one regime while the
    signature opened another — the N4 defect in the form Q-S12 rejected.
  - Measured with the change substituted: gate 3129 passed + 1 xfailed; the `t05b` identity
    document identical; the sweep identical; no leaving disagreement anywhere in the suite under
    either screen.
- *Build lane:* spec §20 W10 (6): (a) test-only pins, (b) the screen and guard change, (c) the
  limitation sentence plus an A01 re-run. *Acceptance:* B34 (a) as re-registered, B36 (c) as
  completed, B36 (d).
- *For Frank:* nothing blocks. §18 Q9 (certifying a flash exactly on its dew point) stays his. It
  now also covers these false successes: detected, never certified.

**Q-S10 — review S1: the screen's cost.**
- *Ruling* (spec §6.2; R-053 amended). At a flagged trial:
  - (s1) replicate `ph_state`'s out-of-domain refusal with its own test, which gives TP's regime;
  - (s2) otherwise report `LIQUID` / `TWO_PHASE` / `VAPOR` by comparing `H_split` with the band's end
    enthalpies `H_0`, `H_1`, with a `τ_E` margin;
  - (s3) inside a `τ_E` zone, or on any failed evaluation, ask `ph_state` and carry its answer.
- This is exact wherever `ph_state` answers `ok`: an `ok` answer carries `H_split` to `τ_E`, and the
  phase regions are ordered by enthalpy. The one sanctioned screen/opening difference is when
  `ph_state` refuses inside the domain range. The opening's TP fallback then governs, recorded
  `fallback(<U>, tp)`. This needs a provider outside the class's continuity, or flows above
  ~1e8 mol/s. An `ok` disagreement stays a defect. Openings keep the full closure and reuse the
  screen's answer at the same state.
- *Build lane.* Implement in its own commit.
- *Acceptance* (B32):
  - (a) Regime equality with `ph_state` or its fallback at KS-1…3, and at each grid composition at
    the five targets, `H_0 ± τ_E/2`, `H_0 ± 2τ_E`, `H_1 ± τ_E/2`, `H_1 ± 2τ_E` and the two domain
    ends ± 1 W. (s3) is taken exactly at the `±τ_E/2` points.
  - (b) NP-1…NP-G from the liquid-form start under the region's meter: no `BUDGET_EXHAUSTED`, calls
    recorded.
  - (c) R0 unchanged: the `t05b` key as re-registered by Q-S11 (a), B07, and SC-3's records.

**Q-S11 — review S2: near-pure restarts end `BOUND_BLOCKED`.** This is fixed in T05b, per the build
lane's DECISION under Frank's directive.
- (a) *Ruling* (spec §6.2 step 3). An opening **sets** every temperature column of the split's
  streams to the closure's `T` — for a products-style split, both products. Nothing else changes.
  - Moves: SC-3's and DZ-12's attempt-1 records, and so the `t05b` key. It is re-registered with
    this reason and its new hash, and the CI pair is re-run.
  - Acceptance: B33 (a) — both products' temperatures equal the answer's `T` bitwise at SC-3's,
    DZ-12's and B31's restart openings.
- (b) *Ruling* (K03 §5.3 amended; R-064). When `α_max = 0`, a set `Z` qualifies if its free
  components are exactly on their lower bound at both the attempt's opening and the iterate, and the
  rows closed on it (`F == 0.0` exactly, every nonzero entry in `Z`) number exactly `|Z|`.
  - Then `J` nonsingular forces the exact step on `Z` to be zero. The largest such set gets
    `d := 0` and `α_max` is recomputed.
  - `BOUND_BLOCKED` is declared only if something outside the set still blocks, and then with the
    original `blocked_by`. There is no record.
  - This is threshold-free, never acts on a component that reached its bound during the attempt
    (T02 §6.3.3's disappearance stays), and never acts on `F ≠ 0` (BND-02 stays blocked).
  - Inertness: it acts only where an attempt would otherwise end `BOUND_BLOCKED` with every blocker
    released. Every converging attempt and every registered `BOUND_BLOCKED` whose blockers were
    positive at its opening stay bitwise.
  - Acceptance:
    - B33 (b): NP-1…NP-3 from the liquid-form start are `CONVERGED` and `VERIFIED` within the
      allowances of `ref`. NP-G is `CONVERGED` and `VERIFIED`, with its temperature within 1e-5 K
      and its split not compared (as B13).
    - B33 (c) (i)–(iv) at the step-helper level.
    - B33 (d): SYN-001's identity, T02 floats, T02–T04 fixtures and keys and `t05` are bit-identical.
      SC-2's v1 outcome is reported. If it becomes `VERIFIED`, stop: B09 and the manifests' v1 text
      are the design lane's.
- (c) The review's S3 (three untested paths) is build-lane test work; I do not disagree. It has
  landed (`911d251`).

**Build-lane checklist, in order (spec §20 W9).** One isolated commit each; each proves its
inertness first.

1. Test-only re-registrations:
   - X26 (Q-S1);
   - X21 tolerance (Q-S2);
   - B24's mixer-first DZ-9 (Q-S4 (1));
   - B29 `.hot`/`.cold` (Q-S4 (3));
   - the X02 extent case (Q-S5);
   - the K05 fixture and its comparison test (Q-S7).
2. The screen at an empty signature (Q-S4 (6)).
3. The opening fixed point (Q-S9) → B31.
4. Both product temperatures at openings (Q-S11 (a)) → B33 (a). Re-register the `t05b` key and
   re-run the CI pair.
5. K03 §5.3's structural-zero release (Q-S11 (b)) → B33 (b)–(d).
6. The screen by band-end enthalpies (Q-S10) → B32.
7. Evidence: T05b's manifest carries B31–B33 and X26 as amended. `docs/progress.md` and
   `docs/T05b_STATE.md` are updated.

Items 2–6 touch phase logic and the Newton core, so the design lane (`reviewer`) reviews them before
merge. If any of them needs a frozen type, a checkpoint format or `_region_problem`'s Newton-core
contract to change, stop and report.

**For Frank.** Nothing blocks.
- The Newton change (Q-S11 (b)) is a K03 behaviour change, taken under his directive. It is inert on
  every converging trajectory by construction, and SYN-001 stays bit-identical.
- The only registered record expected to move is the `t05b` key (SC-3, DZ-12), which is not yet in a
  tested manifest.
- K04-F9 §12 Q1 (F10's legacy checks, which would move SYN-001's identity) stays his, unchanged.
