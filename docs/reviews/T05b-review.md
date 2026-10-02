# T05b review — the saturation band, the v2 phase contract with `ZERO_FLOW` and dormancy forms, the verifier's degeneracy and zero-flow forms, and T04 F9's projection, against `docs/derivations/T05b-limitations-spec.md` (ADR 0012) and `docs/derivations/K04-F9-spec.md` (ADR 0013)

**Reviewer:** design lane, `reviewer` (Claude Opus 5.5), 2026-09-25. Plan §1.3 requires a design-lane
review because T05b touches residuals, phase logic, certificates and replay identity.
**Brief:** `docs/briefs/T05b-implementation-review.md`.
**Reviewed at:** `wp/T05b` = `e4e4990`. I reviewed the build lane's `src/`, `scripts/` and `tests/`
changes in `1ba973b..HEAD`. The documents in that range belong to the design lane: I read them but
did not review them.
**Run here:**
- The full suite gives **3000 passed, 2 xfailed** in 158 s. The two xfails are X26 at NP-GC and X21
  at NP-1, which the `specifier` is ruling on (Q-S1, Q-S2).
- I ran pytest only, not ruff, format or mypy.

**Environment:** x86-64 Linux 6.12.86, the repository's `.venv`. I did not examine a CI artefact.
**Measured:** a finding marked *measured* comes from a probe I ran against this tree in this
session. The probes use the tests' own helpers:
- `tests/t05b_support.py`: `revision`, `instance`, `Source`, `Link`, `Product`, `solve_from_v2`
  and `POLICY_V2`;
- `tests/t05_w12_support.py`: `bind` and `duty_pin`;
- `orchestrator.revision.initial_state`.

§8 describes each probe (P1–P6) so that it can be re-run. The probe scripts lived only in the
session scratchpad.
**Amendments made in this commit:** none. The `specifier` is ruling concurrently on
`docs/briefs/T05b-rulings.md` (Q-S1…Q-S8). This review does not re-rule those questions. Where a
finding here supplies evidence for one of them, the finding says so.

---

## 1. Verdict

**Not ready to merge. One must-fix.** On the registered cases the package is implemented as
specified. The verifier side (ADR 0013's projection, the degeneracy and unresolved routing, and the
zero-flow and dormancy reductions) is sound by reading and by the gate. The solver side has one
defect: a flowsheet topology that SC-4 registers as supported can crash with an untyped exception.

- **v1 is unchanged on every path I read.**
  - `ph_units` is empty under v1.
  - `v2` gates the dormancy agreement, the `ZERO_FLOW` start, the band-route records, the items and
    the swapped-row test.
  - `_attempt_screen` calls T03's `_screen` exactly as before.
  - `_signature(…, opened)` appends `_items((), …) == ()`.
  - `_reopened` returns a copy when there are no forms.
  - `restart_message` without fallbacks is `phase_update(<cause>)`.
  - `_region_problem` without labels is the pre-T05b problem.
  - `kernel_disagrees` still asks the TP flash twice, as v1 always did.

  The only v1-visible change is ADR 0012 D6's `branch_found` arm, with its `ZERO_FLOW` admissibility
  (spec §8 applies it under both literals). This agrees with the identity evidence.
- **No path closes `CONVERGED` on a state that violates a declared row.**
  - For a lifted zero-flow form, the rows it drops (equilibrium, split or product-mole rows, total
    definitions) hold *exactly* at an exactly dormant feed with pinned `+0.0` products.
  - The closure checks feed dormancy (`_admissible`'s `ZERO_FLOW` arm).
  - Every swapped energy row, lifted and non-lifted, goes through `_swapped_row_test` against the
    compiled residual before `closed("CONVERGED")` (region.py:1674–1689). Two tests pin this with a
    negative control each.
- **The projection (ADR 0013 D1) matches the specification.**
  - Preconditions are checked in the specified order.
  - Exact zeros are kept by variable kind.
  - The step is taken with the screen's own matrix and factorization.
  - Both engines evaluate energy, admissibility, independent split, declared ports and the D3
    routing at `x̃`. Material, specifications and bounds are evaluated at `x_final`
    (`certificate._check_set`, `table.revision_checks`).
  - The record is free of floats.

  A wrong state cannot pass except as D1 intends: `x̃` must itself pass every compiled row and every
  label, and it lies one screened Newton step from `x_final`.
- **The kernel's acceptance and the band route** are spec §5.1–§5.3 line by line.
  - B02's baseline (`01e4d70`) predates the kernel change (`88d6ba9`) and has not been regenerated,
    so it tests real inertness.
  - The fallback records are deterministic and float-free (B20c, and P2's
    `fallback(U-VLV, tp)`).

**What remains:**
1. **M1 — a crash on a registered topology.** A lifted products-style split whose feed is another
   lifted split's product, or a dormancy-form outlet, opens a restart in a regime that disagrees with
   its feed's dormancy. The region then raises `RuntimeError("defect: …")`. The engineers had logged
   this path as unreachable (W7). SC-4's topology reaches it from any start that needs a restart.
   *Measured* (P1, P4).
2. **S1 — the v2 screen can use up the property budget on a near-pure restart.** It runs the full
   PH closure, band route included, at every flagged trial, and asks again at the candidate.
   *Measured* (P5): 12 598 region-side provider calls for NP-1 from a liquid-form start, against the
   default cap of 10 000.
3. **S2 — near-pure EO from a restart opening ends `BOUND_BLOCKED`.** NP-2 and NP-G, started in the
   liquid form, block on an absent component's exact-zero column (*measured*, P5, P6). NP-G's
   outcome also depends on the unset liquid-product temperature at the opening, which is evidence
   for Q-S3 (2).
4. **S3 — three paths have no end-to-end test:**
   - a lifted split leaving or entering `ZERO_FLOW` at a restart, with its F2 record;
   - a label row under the PTC core;
   - M1's regression.

M1 must land before merge. S1 and S2 each need a design-lane decision first (§7). S3 is small and
cannot move a registered number.

---

## 2. Must-fix

### M1 — A lifted split whose feed is another lifted split's product, or a dormancy-form outlet, opens a restart in the wrong regime and the region raises an untyped `RuntimeError`

**Where.**
- `src/process_runtime/orchestrator/region.py:1457–1467` raises
  `RuntimeError("defect: <U> opens attempt <k> in <regime> with its feed <dormant|flowing>")`.
  Nothing in `solve_region`, the executor or the application catches `RuntimeError`.
- The openings that produce the disagreement:
  - `_LiftedOps._projected` (902);
  - `blocked` (958), through `_pin`;
  - `at_candidate` (996–1036), through `opened.update(answer.values)`;
  - `_reopened` (762–789, spec §7.8 (ii)'s outlet reset).

Each of these changes some lifted split's *product* flows, or a dormancy-form outlet's flows. For a
products-style split (PH flash, TP flash, K02 flash) those columns *are* the feed of the next
products-style split. Nothing re-derives that downstream split's regime at the opening.
- Spec §7.1 requires "`ZERO_FLOW` exactly when every flow of its feed is `+0.0`".
- §7.8 (ii) recomputes the dormancy *items* after the lifted part is set.
- No clause recomputes the downstream *lifted* regimes.

The implementation turns that gap into a crash. `docs/T05_DECISIONS.md` (W7) records
"regime/dormancy disagreement at opening → RuntimeError (unreachable)". It is reachable.

**Measured.**
- **P1 (two PH flashes in series, SC-4's topology).**
  - Flowsheet: feed `(1,1,1)`, 300 K, `P_r`, liquid → `U-PHF` (`Q`) → `S2` vap → `U-PHF2`
    (`Q = 0`) → `S4` vap, `S5` liq; `S3` liq → sink.
  - Start: the traversal state of the `Q = 0` revision (`U-PHF` all liquid, `U-PHF2` dormant).
  - Target `Q = 30 000 W`, policy `T05b-v2`:
    `RuntimeError: defect: U-PHF2 opens attempt 1 in ZERO_FLOW with its feed flowing`.
  - The reverse direction (start at the `Q = 30 kW` traversal, target `Q = 0`):
    `… opens attempt 1 in VAPOR with its feed dormant`.
  - Under v1 the same two runs end typed: `LINEAR_SOLVE_FAILED` and `ACTIVE_SET_CYCLING`.
  - From its own traversal start the `Q = 30 kW` revision closes `CONVERGED`. The registered cases
    pass because they never restart.
- **P4 (through the outlet reset).**
  - Flowsheet: DZ-12's topology, with `U-PHF2` (`Q = 0`) placed on the exchanger's hot outlet `S4`.
  - Same start rule, target `Q = 30 kW`: `RuntimeError: defect: U-PHF2 opens attempt 1 in ZERO_FLOW
    with its feed flowing`. §7.8 (ii)'s reset `S4 := S2` made `U-PHF2`'s feed flow.
- **Control (P2).** A heater-style consumer (flash vapour → valve) is fine in both directions:
  - `CONVERGED` in 3 attempts, the second restart recorded
    `phase_update(phase_wall(stall, U-VLV:ZERO_FLOW->VAPOR); fallback(U-VLV, tp))`;
  - `CONVERGED` entering `ZERO_FLOW` by `phase_wall(patience, U-VLV:VAPOR->ZERO_FLOW)`.

  This works because a heater-style split's feed is its own outlet stream `S.n`, which no opening
  writes.

The same gap exists at attempt 0 for a user or recovery start. There, `_solve_region`'s start loop
(1342–1377) decides a later split's `ZERO_FLOW` before an earlier-declared TP-type split's
projection changes that later split's feed, so the outcome depends on declaration order.

**Why must-fix.** CLAUDE.md requires typed results, never untyped exceptions, on a user-reachable
path. Two paths reach this one:
- `solve_region(…, initializer_source="user_guess")`, the API T05 W12 established;
- any restart on a flowsheet with a products-style split downstream of a lifted product or a
  dormancy-form outlet.

That includes a two-stage flash and a mixer → flash, the ordinary topologies T06 will generate. The
five manifests (W8) now state that dormant outlets are "solved and certified under v2". That is
false for these topologies.

**Minimal correction.**
1. At every restart opening, after the lifted part is set, re-derive every lifted split's
   membership in `ZERO_FLOW` from exact dormancy of its feed:
   - *entering*: `_zero_flow_answer`, i.e. pin its products at `+0.0`;
   - *leaving*: the TP flash at the feed's `(n, T, P)`, recorded `fallback(<U>, tp)` for a PH-type
     split (§7.4).
2. Iterate this jointly with `_reopened` until no split and no item changes, in declaration order.
   A pinned product can be the next split's feed or a form's trigger, and a reset outlet can be a
   split's feed.
3. Apply the same fixed point to attempt 0's start after all projections.
4. Keep the `RuntimeError` as the defect guard behind the fixed point.

This is a rule the spec does not state, so it needs a §7.4/§7.8 (ii) amendment first (§7). The
amendment must say how an opening records a downstream regime change that its cause string does not
name. I would record it only through the signature and a `fallback(<U>, tp)` item, with no new
grammar.

**Falsifiable test.**
- P1 in both directions and P4 as mini-revisions under `T05b-v2`: each ends in a typed outcome,
  never an exception. I expect `CONVERGED` and `VERIFIED` at the P1 target's root.
- The attempt that leaves `ZERO_FLOW` carries `fallback(U-PHF2, tp)` on its `attempt_opened`.
- A three-flash chain exercises the fixed point.
- A variant with `U-PHF2` declared before `U-PHF` exercises the start ordering.
- B07, B21, B22 and B30 stay as they are: no registered case restarts through this path.

---

## 3. Should-fix

### S1 — The v2 screen runs the full PH closure, band route included, at every flagged trial and again at the candidate; a near-pure restart can exceed the region's property cap

**Where.**
- `region._build_screen` (1159–1163) calls `_ph_closure` → `ph_state` for every flagged PH-type
  trial.
- `_LiftedOps.at_candidate` (1020) calls it again at the same state. `kernel_disagrees` avoids the
  second call ("not asked twice"); `at_candidate` does not.
- W0.6 measured up to 3 214 provider calls for one kernel call on the band route, and registered no
  case that runs the band route inside a region.

**Measured (P5).** Each NP case, started in the liquid form (the traversal state with the PH flash's
products all liquid at 300 K), under `T05b-v2`:

| case | outcome | `ph_state` calls (band route) | region-side provider calls |
| --- | --- | --- | --- |
| NP-1 | `CONVERGED` (2 attempts) | 4 (4) | **12 598** |
| NP-2 | `BOUND_BLOCKED` (S2) | 6 (6) | 18 588 |
| NP-3 | `CONVERGED` | 4 (0) | 569 |
| NP-G | `BOUND_BLOCKED` (S2) | 5 (0) | 677 |

These counts exclude the compiled residual's property blocks. The default `max_property_calls` is
10 000, so a metered run of NP-1 would close `BUDGET_EXHAUSTED`. That is an inference: I did not run
it through the executor.

**Needs a decision** (spec §6.2 prescribes `ph_state` for the flagged regime). I would go this way:
- The screen needs a regime, not a split. Because `H(β)` increases (spec §4.2), the PH regime is
  `LIQUID` iff `H_split < H(0)`, `VAPOR` iff `H_split > H(1)`, else `TWO_PHASE`. That comparison
  costs two band temperatures and four enthalpy calls (about 110 calls instead of about 3 100), and
  uses the same sign oracle off the domain.
- Keep `ph_state` for the openings, where the split and the temperature are used.
- Carry the screen's answer on the `Candidate` so that `at_candidate` does not ask twice.

**Falsifiable test.** P5's NP-1 run under the executor's meter closes without `BUDGET_EXHAUSTED`.
The screened regime equals `ph_state`'s regime on KS-1…KS-3 and on the spec §12.1 grid.

### S2 — Near-pure EO from a restart opening ends `BOUND_BLOCKED` on an absent component's structural zero; the liquid product's temperature is left at the trial's value

**Where.**
- Newton's bound handling (pre-existing K03) treats a roundoff direction on an exactly-zero column
  as leaving the feasible set.
- `at_candidate` sets a products-style split's vapour-product temperature only
  (`split.temperature`); the liquid product's `S3.T` keeps the trial's value. This is the subject
  of Q-S3 (2).

**Measured (P5, P6).** NP-2 and NP-G from the liquid-form start:
- Attempt 0 (`LIQUID`) restarts correctly:
  `phase_update(phase_wall(patience, U-PHF:LIQUID->TWO_PHASE)[; fallback(U-PHF, ph-band)])`.
- Attempt 1 closes `BOUND_BLOCKED` at iteration 0 with `blocked_by = ('S2.n.A',)`. A is absent from
  the feed (`S1.n.A = 0`), so the exact Newton direction there is zero.
- The opening carries `S2.T = 360.0000001 K` but `S3.T = 392.81 K` (NP-2) and `393.75 K` (NP-G):
  the heated liquid-form trial.
- With `S3.T := S2.T` imposed at the opening, NP-G `CONVERGED` in one iteration. NP-2, which is
  degenerate, stays `BOUND_BLOCKED` on `S2.n.A`.

Every outcome is typed and none is a false success. But Frank's directive in this package is
near-pure feeds on the EO path, and a restart into `TWO_PHASE` is the contract's designed route
there (SC-3). The registered cases (B12, B13) all start at the traversal root, so nothing in the gate
sees this.

**Needs a decision.**
- (a) Q-S3 (2) is the specifier's to rule. The evidence above says "`PHF-T` closes the liquid's" is
  not harmless: an opening that takes the closure's temperature should set every product's
  temperature column.
- (b) The structural-zero block is a K03 Newton matter. The verifier's projection already keeps
  exact zeros by kind (ADR 0013 D1), and the solver has no counterpart.

I would take (a) in T05b. For (b), I would register a start-dependence limitation for degenerate
near-pure feeds now, with a typed outcome and never `VERIFIED`, pinned by P6's NP-2 run. The Newton
fix would go with T06, where generated starts will hit it. A Newton change can move the last bits of
registered trajectories, so it needs its own inertness proof. Frank may prefer (b) now (§6).

**Falsifiable test.**
- (a) Every product temperature column of a products-style PH split equals the closure's `T` at a
  restart opening, and NP-G from P5's start is `CONVERGED` and `VERIFIED`.
- (b) Either NP-2 from P5's start is `CONVERGED`, or its typed outcome is registered.

### S3 — Three paths have no end-to-end test

- **A lifted split leaving or entering `ZERO_FLOW` at a restart, with its F2 record.**
  - B20's region-level records are tested at kernel level (KS-1…KS-3) and by grammar
    (`test_b20_the_fallback_record_grammar`); W6's log says so.
  - No gate test drives `Conversion.fallbacks` from `_LiftedOps` through `restart_message` into an
    `attempt_opened`.
  - P2 does, heater style. Make P2 a test in both directions, asserting the two records quoted
    in M1.
- **A label row under the PTC core (§7.8 (v)).** No v2 test runs `eo_core = "ptc"`.
  - *Measured* (P3): with the dormant outlet temperature moved 5 K off its label, DZ-1, DZ-6 and
    DZ-9 close `CONVERGED` in one iteration under PTC, the label met exactly.
  - DZ-3, DZ-7, DZ-10 and DZ-12 are `PTC_MAPPING_INVALID`: the PH flash's and the exchanger's mole
    rows have no holdup mapping. That is pre-existing T05 scope, not T05b's.
  - Make the DZ-1/DZ-6/DZ-9 runs a test.
- **Edge 3's homotopy recovery with a `ZERO_FLOW` or item signature.** It is not exercised anywhere,
  and I did not probe it (§9).

---

## 4. Notes (no change required, or a small one)

- **N1. The outlet reset resets each outlet "at most once" (`_reopened`, 762–789).**
  - An outlet reset early in a pass keeps a stale mole balance if a *later* reset in the same
    opening toggles its trigger again. Example: a mixer declared before the pump that feeds it, with
    both toggling in one opening. The mixer then leaves its form with `n_out = 0`: F7's singular
    first Jacobian.
  - It needs two simultaneous changes in one opening, so it is contrived today. After M1's fixed
    point it becomes more reachable.
  - Suggestion: reset whenever the trigger state differs from the one at that outlet's last reset;
    the reset count stays bounded on an acyclic chain.
- **N2. The verifier's degeneracy test has no pre-screen.**
  - It runs two bisections, about 110 `lnK` calls, per flowing stream per certificate
    (`table.degeneracy`, W3 log). The unit layer got the two-call sign pre-screen (W6); the verifier
    did not.
  - The same test in the verifier's own code (`verify/saturation.py`, R-016) would cut certificate
    cost for T06's ensembles.
  - It is not a correctness matter.
- **N3. R-016 for the new verifier modules.**
  - The AST tests pin what matters: direct imports of `saturation.py`, `zero_flow.py` and
    `projection.py`, each with injected violations, and the dormancy table compared with the
    solver's *as data*.
  - The rule is on direct imports only. Transitively `projection.py` reaches `verify.checks`, which
    imports model id helpers and `compile.reference`. That is pre-existing and sanctioned.
  - `zero_flow.PH_TYPE_ENERGY_ROWS` and `PRODUCT_MOLE_ROWS` are the verifier's own transcriptions
    but, unlike `DORMANT_OUTLETS`, are not compared with `SPLIT_RULES`. A one-line data test would
    close it.
- **N4. The projection's `discarded` is returned but not bounded.**
  - A non-structural exact zero, one whose exact step is not zero, is kept at zero silently.
  - Precondition 5 re-checks every row at `x̃`, so this cannot certify a row violation. It only
    means `x̃` is not exactly the Newton point.
  - Acceptable as specified. I mention it only because the discard grows as the matrix nears the
    screen's threshold.
- **N5. The band route's failure precedence.**
  - A provider refusal inside the band route surfaces the provider's status (`_surfaced`), not
    `ph_ill_conditioned` with the temperature route's attempt.
  - Spec §5.1 names only exhaustion (`ph_not_converged`). The result is typed either way.
- **N6. A dormant outlet's temperature off its label is `FAILED`.**
  - The verifier's zero-flow form checks `residual.<U>:zero-flow-label` at `τ_T` (spec §9.3). A
    state that satisfies every declared row, but carries a dormant outlet temperature other than the
    causal label, is therefore `FAILED`. An example is a state supplied by another tool.
  - That is the specification's choice (the label makes the root unique) and is implemented as
    written. I record it because it is visible to users.

---

## 5. Rulings on the brief

### 5.1 Brief §3 ("least sure")

1. **`region.py`.**
   - v1 is unchanged by reading (§1).
   - The `ZERO_FLOW` and dormancy openings are wrong for products-style chains (M1).
   - The outlet reset's fixed point is sound except N1.
   - The closure agreement comes before the swapped-row test, which comes before `CONVERGED`, in
     §7.8 (iv)'s order.
   - I found no path to `CONVERGED` on a violated declared row.
2. **R-016.** The tests test what matters (N3).
3. **The projection.** It is as specified (§1).
   - Checks judged at `x̃`: energy, admissibility, independent split, declared ports and D3's routing.
   - Checks judged at `x_final`: residual rows, labels, aliases, material, specifications, bounds,
     witness, regularity, `b`, `target_state_sha256` and the branch.
   - Exact zeros keep the branch identical between the two points.
4. **Kernel acceptance and the band route.**
   - They are correct by reading.
   - The residual and Jacobian describe the same rows as the evaluator on the band route: acceptance
     is on the EO closure's own rows, and the start is not re-projected.
   - The records are float-free.
   - The region-internal F2 path lacks an end-to-end test (S3).
5. **Tests that verify nothing.** Among those read, none:
   - B02's baseline predates the change;
   - B22 and B30 (d) are declared self-generated regressions;
   - the F6 and F7 negative controls exist;
   - X04 and X25 discriminate raw values from projected ones.

   The gaps are what *no* test covers (S3). One logged decision is falsified: W7's "unreachable"
   (M1).

### 5.2 The engineers' decisions (`docs/T05_DECISIONS.md`, after "Frank reverses")

- **Sound:**
  - an item is recognized by `.` in its key (R1 forbids `.` in unit ids at the reader,
    `revision_flowsheet.py:60`);
  - `declared_phases` is read by `getattr`;
  - `ZeroFlowForm` is kept beside `LiftedSplit`;
  - the pre-screen's proof, for SYN-001's provider (the slope bound is SYN-001's);
  - the v2 refusals until W6 and W7, now removed.
- **Falsified:** the W7 "RuntimeError (unreachable)" decision (M1).
- **Not re-ruled here:** the D2 order (Q-S5 (1)), the guard-4 flow predicate (Q-S5 (2)) and the
  liquid temperature at products-style openings (Q-S3 (2)). S2 supplies evidence for Q-S3 (2).

---

## 6. FOR FRANK

M1 and S3 need no decision from Frank. One scope preference is his to overrule:
- **S2 (b): near-pure feeds whose EO solve must restart into the two-phase regime.** A degenerate
  near-pure case (NP-2) ends `BOUND_BLOCKED` from a liquid-form start. The cause is K03's Newton
  treating a roundoff direction on an absent component's zero flow as a bound violation. The result
  is typed, never a false success, and every registered start converges.
- My recommendation: register it now as a start-dependence limitation and fix the Newton core with
  T06, with its own inertness proof.
- Under "as little limitations as possible" he may want the Newton fix inside T05b instead. It costs
  a K03 change and a full identity re-check.

---

## 7. What the fixes must not do; amendments recommended to the `specifier`

**The fixes.**
- **M1 must not move a registered record.**
  - No registered case restarts through a products-style chain, so B07, B21, B22, B30 and every K05
    key must stay bitwise.
  - The re-derivation must use exact dormancy only (no threshold, ADR 0001 D3.1), and must never
    loosen the defect guard it sits in front of.
- **S1 must not change a regime.**
  - The screen's cheaper answer must equal `ph_state`'s regime wherever `ph_state` answers.
  - Where `ph_state` refuses, the TP fallback stays (`fallback(<U>, tp)` at openings only, as now).
- **S2 (a) must set, not project.**
  - The liquid product's temperature takes the closure's `T`.
  - No other opening value changes.
  - SC-2, SC-4 and the NP cases from the traversal stay bitwise.

**Amendments recommended (design lane; not made here).**
1. **§7.4 and §7.8 (ii) (M1).**
   - At every restart opening, and at attempt 0 after the projections, every lifted split's
     `ZERO_FLOW` membership is re-derived from its feed's exact dormancy, jointly with the item
     recompute, to a fixed point in declaration order.
   - Entering pins the products. Leaving takes the TP flash, recorded `fallback(<U>, tp)` for a
     PH-type split.
   - The downstream change is carried by the signature and needs no new cause grammar.
2. **§6.2 (S1).** The regime of a flagged PH-type trial is decided by comparing `H_split` with the
   band's end enthalpies (spec §4.2's monotonicity). `ph_state` is kept for openings.
3. **§6.2 step 3 (S2 (a); Q-S3 (2)'s evidence).** "An opening takes its split and its temperature":
   every temperature column of the split's products.
4. **§17 (S2 (b)),** if Frank takes the default: near-pure degenerate feeds that must restart into
   `TWO_PHASE` may end `BOUND_BLOCKED` (typed); the registered starts converge.

---

## 8. Probes (re-runnable from the named helpers)

All probes run under `POLICY_V2` unless stated, with `PATH=.venv/bin:$PATH PYTHONPATH=src:.:tests`.

- **P1.**
  - Revision: `U-PHF` (C1's instance) → `S2` vap → `U-PHF2` (C1's `U-PHF` renamed, `Q = 0`); the
    other products go to sinks; one feed `(1,1,1)`, 300 K, `P_r`, liquid.
  - Start: `initial_state` of the `Q_U-PHF = 0` revision. Solved by `solve_from_v2` on the
    `Q = 30 000 W` revision, then the reverse.
  - The same two runs under `T03-phase-contract-v1`.
- **P2.** As P1, with `U-VLV` (C1's instance, `S4.P` pinned `0.9e5 Pa`) in place of `U-PHF2`, and the
  trace's `attempt_opened` messages printed.
- **P3.**
  - DZ-1, DZ-6 and DZ-9 from `initial_state` with the dormant outlet's temperature (the form's
    `label[1]`) raised by 5 K.
  - Policy `POLICY_V2` with `GlobalizationPolicy(eo_core="ptc", eo_recovery="none")`.
  - DZ-3, DZ-10 and DZ-12 from their registered starts under both cores.
- **P4.** DZ-12's revision plus `U-PHF2` (`Q = 0`) on `S4`, products `S7`/`S8` to sinks. Start and
  target as P1.
- **P5.**
  - NP-1…NP-G (`near_pure`), started from `initial_state` with `S3.n := S2.n + S3.n`, `S2.n := 0`,
    totals updated, and `S2.T = S3.T = 300 K`.
  - The flowsheet's provider is wrapped in a call counter; `region.ph_state` is wrapped to count
    calls and band routes.
- **P6.** P5's NP-2 and NP-G with `_LiftedOps.blocked` spied for `blocked_by`, then re-run with
  `at_candidate`'s opening patched to `S3.T := S2.T`.

---

## 9. Not examined

- The internals of `saturation_band.py` and `verify/saturation.py`, beyond the pre-screen and the
  routing: the `T(β)` bisection's derivation, and the sign oracle at the domain's ends.
- `conversion_reactor.py`, `ph_flash.py`, `heat_exchanger.py` beyond the `closure` plumbing; the
  verifier's reactor closure-type rule (`duty_id in pins`) against the solver's
  (`energy_specification`) was not compared.
- `table.py` beyond `degeneracy`, `revision_checks` and `_split_checks`' routing.
- The scripts (`t05b_ph_baseline.py`, `t05b_identity.py`, `t05b_degeneracy_margins.py`,
  `t05_evidence_manifest.py`) beyond their tests.
- Edge 3's homotopy recovery under v2 (S3), and the tear path under v2 beyond its test.
- The schema fixtures, the manifests' texts (Q-S8), the numbers in `docs/t05b-measurements.md`
  beyond the gate count, and the CI run.
- Inputs at the domain's edges.

---

## Re-review of W9 (2026-09-25)

**Reviewer:** design lane, `reviewer`. **Scope:** W9 items 2–6 against `docs/briefs/T05b-rulings.md` §4
(Q-S4 (6), Q-S9, Q-S10, Q-S11), spec §6.2, §7.4, §7.8 and B31–B33, and K03 §5.3 as amended, at
`wp/T05b` = `f2ad079` (`51201d2..f2ad079`). Also in scope: the W9 entries of `docs/T05_DECISIONS.md`
and the one relaxed assertion in `tests/test_t05b_review_s3.py`.
**Run here:**
- The five W9 test files give **79 passed, 3 xfailed**. I did not re-run the full gate or the
  identity hashes; I take the build lane's numbers for those.
- I ran probes P7–P14. The scripts are in the session scratchpad, `review_t05b_w9/`, and they use
  the tests' own helpers.
- To check whether a defect predates W9, I also ran two source snapshots taken with
  `git archive`: `51201d2` (before W9) and `8128d3d` (before item 6).

### Verdict

**Items 2–6 are implemented as ruled, and M1 as filed is closed.**

**The package is still not ready for `main`.** One must-fix remains, M2. It is not a W9 regression:
it was already present at `51201d2`. It is a sibling of M1. I found it by widening P1's sweep, and it
crashes with an untyped `RuntimeError` on the same topology as M1.

**M1 is closed on my reproductions:**
- P1 in both directions (CH-UP, CH-DOWN), P4 (CH-DZ12) and their order variants: each ends
  `CONVERGED`; none raises.
- P7 (new): feed → `U-PHF` → `S3` liq → `U-PUMP1` → `S4` → `U-PHF2` (`Q = 0`), with the duty moving
  30 kW ↔ 125 kW. Both directions and both declaration orders are `CONVERGED` and `VERIFIED`:
  - going to 125 kW, the restart opens with the pump item and `U-PHF2` in `ZERO_FLOW` together;
  - going back, it leaves with `fallback(U-PHF2, tp)`.

  P7 exercises what CH-* does not: a reset feeding a lifted split, end to end.
- P10: in 104 two-flash restarts, the dormancy guard never raised.

### M2 — must fix (needs a decision on the repair): `at_candidate` asks a downstream split's kernel after an upstream answer has rewritten its feed

**Where:** `src/process_runtime/orchestrator/region.py:1248–1284`.

**Reproduction (P10, P11).**
- Flowsheet: CH-UP's, with `U-PHF` declared first. `U-PHF2`'s duty `Q2` is 0, +3 kW or −3 kW.
- Start: `initial_state` of the revision at `Q = 125 kW` (both flashes `VAPOR`).
- Target: `Q = 90 kW` or `30 kW`. The pair 115 kW → 90 kW at `Q2 = 3 kW` fails too.
- The error raised is:

  ```
  RuntimeError: defect: the kernel reports U-PHF2 VAPOR at the candidate the screen reported TWO_PHASE at (iteration 1, halving 0)
  ```

- 15 of the 104 sweep solves raise, all with `U-PHF` declared first. With `U-PHF2` declared first,
  the same pairs end typed (`ACTIVE_SET_CYCLING` or `SPECIFICATION_CONFLICT`). The outcome
  therefore also depends on declaration order.
- The same raise occurs at `51201d2` and at `8128d3d`, so item 6's screen is not involved.

**Mechanism (P11).**
- The candidate reports both units changing (`VAPOR → TWO_PHASE`). At the candidate's own state, the
  band screen and the full PH closure both give `U-PHF2 TWO_PHASE`.
- The loop applies `U-PHF`'s answer first. That answer rewrites `S2.n` and `S2.T`, which are
  `U-PHF2`'s feed.
- `U-PHF2`'s closure is then asked at the rewritten state and answers `VAPOR`.
- So N4's equality check compares a screen at one state with a kernel at another.

**Minimal correction.** This is phase logic, so the design lane picks.

- **(A)** Ask every changed unit's kernel at the unmodified candidate state, which is where the
  screen asked. Check the equality there, then apply all the answers. Each split writes disjoint
  columns, so the result does not depend on order. The fixed point then settles dormancy. Any mole
  mismatch left downstream sits on linear rows that Newton closes.
- **(B)** Apply the answers in order, and skip the check for any unit whose `_closure_key` inputs an
  earlier answer rewrote. That unit's kernel answer at the rewritten state then governs, recorded
  through the signature as Q-S9 records downstream changes.

I would take (A). It keeps N4's check meaningful and removes the order dependence.

**Regression test:** P10's raising pairs, in both declaration orders, end typed and give the same
outcome in both orders.

### Should fix

**S-W1 — The release's "opening" is the call's start, not the attempt's.**
- **Where:** `newton.py:235` sets `opening = x.copy()`.
- **Why it matters:** `_homotopy`'s corrector (`region.py:2364`) calls `solve_newton` from the last
  accepted λ-level. There, a component that reached its bound in an earlier corrector counts as "at
  the opening".
- **Why that is dangerous:** with `equilibrium_row`'s `v_i L − K_i l_i V`, a vanished vapour phase
  (`v = 0`, `V = 0`) has `n` equilibrium rows plus the `V` definition closed on `{v_i, V}` with
  `F = 0`. That set qualifies, and it is exactly the disappearance K03 §5.3 as amended excludes.
- **Why it is latent:** no registered case reaches it. The build lane's 235 events include no
  homotopy release, and v2 has no continuation.
- **Correction:** add an optional `opening=` keyword to `solve_newton`, and have the corrector pass
  the attempt's `x0`.

### Notes

**N-W1 (needs a decision): the leaving TP flash reads a stale temperature.**
- §7.4 says the TP flash is taken "at the feed's `(n, T, P)`". `_kernel` (`region.py:387–396`) uses
  the feed's `n` with the split's own `T` and `P` columns. For a products-style split, those columns
  lag at an opening, because an upstream answer has just rewritten the feed's `T`.
- P9 measured the gap: in CH-UP, CH-DZ12 and CH-3 the flash ran at 400 K while the feed was at
  352.005 K. It cost nothing measurable: P14 patched the flash to the feed's `T` and it still says
  `VAPOR`.
- For a TP-type split, the split's own `T` is the specified flash temperature and is right.
- I would amend §7.4's text to what the code does, and revisit only if a case shows a cost. This
  predates W9; the fixed point reaches it more often.

**N-W2: B31 (b)'s stop-and-report is right.**
- The declared lifted form really is singular at `L = 0` on the dew point.
- That `VERIFIED` clause came from my own "I expect" in M1.
- P13 offers a replacement: with `U-PHF2` at `Q2 = −3 kW`, the same leaving path
  (`fallback(U-PHF2, tp)`, from the `Q = 0` traversal to `Q = 30 kW`) is `CONVERGED` and `VERIFIED`
  in both orders. It could carry B31 (b)'s `VERIFIED` claim.
- The `Q2 = 0` cases should stay as the measured regression: `UNVERIFIED`, `RANK_DEFICIENT`.

**N-W3: the relaxed assertion in `test_t05b_review_s3.py` should also pin the copy.**
- **Where:** `tests/test_t05b_review_s3.py:203–205`.
- The relaxation itself is legitimate. A converged linear copy row is not bitwise-exact, and item 4
  legitimately changed the trajectory.
- The replacement compares `S4.n` with the reference, not with `S2.n`, so the copy is now pinned
  only to twice the allowance.
- Add `abs(S4.n.c − S2.n.c) ≤ τ_flow`, the row's own tolerance.

**N-W4: one branch of the release has no test.**
- B33 (c)'s step tests are all 2×2. None has a non-empty `Z*` together with a blocker outside it.
  That is the branch at `newton.py:634` that returns the original `blocked_by`, and it is untested.
- The algorithm itself checks out: `_released` equals the brute-force union of released sets on
  7 275 random nonsingular cases (2 052 of them non-empty).
- Add one 3×3 case for the untested branch.

**N-W5: `_released`'s `augment` recurses.**
- **Where:** `newton.py:675`. The recursion depth can reach the number of closed rows, against
  Python's default limit of 1 000.
- This is latent. Make it iterative when flowsheets get large.

**N-W6 (for the design lane's list): the release acts only at `α_max = 0`.**
- A `Z*` column whose roundoff direction is positive still leaves its structural zero when
  `α_max > 0`, and the zero then stops being exact.
- This predates W9 and lies outside the ruled scope.

**N-W7: T04 §7.5 cites "K03 §5.3's `α_max`" by reference.**
- The build lane applied the release in the Newton core only, which is W9.5's decision.
- The design lane should say which version of §5.3 the PTC polish means.

### Per item

**Item 2 (Q-S4 (6)) — sound.**
- With `compare_empty` false, `another_signature` keeps the old predicate exactly.
- The region passes `bool(dormancy)` to Newton, to PTC (polish included) and to the homotopy
  corrector. That is §7.8 (iii)'s scope.
- I agree with W9.2 that a keyword is better than changing the default, given K03's tear callers.
  The two meanings of `()` are now documented in the predicate's docstring.

**Item 3 (Q-S9) — sound, with the exceptions above.**
- `_settle`'s bound of `m + 1` passes is right for acyclic propagation. Resets are redone when they
  go stale.
- Keeping the typed refusal in `phase_contract.py` preserves A02. I agree with W9.3.
- Skipping the fixed point for a recovery start is correct: the recovery start is the failed
  solve's item-0 opening, which has already settled.

**Item 4 (Q-S11 (a)) — sound.**
- `split_temperatures` gives the vapour product's `T` and then the liquid product's. Only a PH
  closure's answer sets them, as ruled.
- W9.4's separate map is the right way to keep `LiftedSplit`'s digest unchanged.

**Item 5 (Q-S11 (b)) — the mathematics is sound.**
- `Z*` is the unique largest released set, the maximum matching plus propagation finds it, and the
  count is re-checked.
- The step record zeroes the same columns.
- The original `blocked_by` is kept.
- I accept W9.5's Newton-only scope for T05b; see N-W7 for the open reference.

**Item 6 (Q-S10) — sound.**
- (s1) is `ph_state`'s step-3 test: the same function at `T_min`/`T_max`, and the same comparison
  sign.
- (s2) and (s3) are as ruled.
- The memo is per attempt and keyed on `_ph_closure`'s exact inputs.
- The `sanctioned` relaxation also admits the leaving path's `tp` answer. That is harmless there,
  because the screen and the kernel use the same TP flash.
- I agree with W9.6's choice to assert `CONVERGED` under the meter rather than exact counts.

**Not examined:**
- W9.1 (X26, X21, B24, B29, X02, the K05 fixture);
- the identity hashes and the CI pair;
- PTC on the liquid-form NP starts (`solve_from_v2` passes no mass mapping);
- the band screen at a single flowing component beyond B32's grid.

## Review of W10 (2026-09-25)

**Reviewer:** design lane, `reviewer`.

**Scope:** W10.2 (B34, Q-S12) and W10.4 (B36, Q-S14), at `wp/T05b` = `8427abd`
(`6019d6a..8427abd`), checked against spec §7.4, §7.8 (ii) 5, B34 and B36. I also read the W10 entries
of `docs/T05_DECISIONS.md` and `docs/t05b-measurements.md`. The rulings asked for are Q-S15 (1)–(3)
in `docs/briefs/T05b-rulings.md` §4.

**Run here.** The scripts are in the session scratchpad, `review_t05b_w10/`. They patch the code at
runtime; nothing in `src/` or `tests/` was edited.
- The full gate at HEAD: 3129 passed, 1 xfailed.
- The full gate again with Q-S15 (3) substituted: 3129 passed, 1 xfailed.
- The `t05b` identity document, with and without Q-S15 (3): identical.
- The B34 sweep, with and without Q-S15 (3): counts 82/10/6/4/2, both orders agree.
- `verify_revision` on every `CONVERGED` run of the sweep (W1).
- A log of every answer at a candidate whose regime differs from the screen's report (W2).
- `git archive` snapshots at `6019d6a` (before W10) and `819fd22` (before B36), for W1 and W3.

### Verdict

**W10.2 and W10.4 are implemented as ruled. There is no must-fix, and T05b can merge once the
should-fixes below land (spec §20 W10 (6)).**

**W10.2 is sound.**
- `at_candidate` asks every changed unit at the unmodified candidate: `opened` is not written
  inside the ask loop.
- N4's check runs there. The screen's (s3) memo is keyed on those same inputs, so it now hits where
  before it missed.
- Each answer writes only its own split's columns. For a products-style split that is its
  products; for a heater-style split, its outlet. So the writes are disjoint, and B36's temperature
  write excludes the feed column.
- `_settle` then handles an answer whose feed another answer made dormant.
- B34 (b)'s control does reproduce P11.

**W10.4 is sound, with one consequence** (S-W10-1).
- `_kernel(temperature=temperature_id(split.stream))` is the inlet `T` for a products-style split
  and the outlet `T` (the split's own column) for a heater-style one. The pressure is
  `split.pressure`, the products' `P`.
- The start's `leave` lambda and `_LiftedOps._leave` both pass the split's temperature columns.
- B36 (a) asserts the flash's inputs through a recording provider, not just its answer. That is the
  right test.

### Should fix

**S-W10-1: the screen and the leaving answer now read different temperatures, and the guard
exempts the leaving answer.**
- **Where:** `region.py` `_build_screen.tp_regime` (the split's own `T`) and `at_candidate`'s
  `sanctioned = … answer.fallback == "tp"`.
- My W9 re-review (item 6) accepted that exemption only because "the screen and the kernel use the
  same TP flash". B36 removed that premise.
- **Failure scenario:** a trial where `U-PHF2`'s label is stale (B36 (a)'s state as a trial:
  `S4.T = 300 K`, `S2` at 352.005 K).
  - The screen reports `LIQUID` and the leaving answer `VAPOR`.
  - `tp` exempts the difference.
  - The attempt opens `VAPOR` under a cause string that says `ZERO_FLOW->LIQUID`.
- **Reachability:** at a full-step candidate the label row is linear and closes, so this needs a
  halved candidate from an attempt's first iterate. The W2 log saw it nowhere in the gate. It is a
  latent hole in a checked invariant, not a measured failure.
- **Fix (Q-S15 (3), B36 (d)):** `tp_regime` reads `temperature_id(split.stream)` for a PH-type
  `ZERO_FLOW` split. The exemption excludes an answer whose attempt regime is `ZERO_FLOW`.
- Measured inert, as listed under "Run here".

**S-W10-2: B34 (a)'s `CONVERGED` count hides six false successes, and §16/§17 understate the
dew-point limitation.**
- **Reproduction (W1):**
  - `chain(30 000, 0)` from `_start(115 000, 0)`, either order, ends `CONVERGED` with `U-PHF2`
    `TWO_PHASE`.
  - `S5.N` is 9.81e-5 mol/s and `S4.T − S2.T` is 0.0569 K.
  - `verify_revision` gives `FAILED`, `false_success_detected`: `energy_balance.U-PHF2` at
    −1.384e-3 W against 1.01e-3 W, and `independent_split.U-PHF2.S2.total` at −4.9e-5 mol/s.
  - The same holds from 125 kW. From 90 kW only `independent_split` fails.
- **The whole tally:** 66 `VERIFIED`, 10 `UNVERIFIED`, 6 `FAILED`; the orders agree. Every
  non-`VERIFIED` run has `Q2 = 0` and `Q_t` ∈ {30, 90} kW, which is the dew-point feed.
- **Not a W10 regression:**
  - At `6019d6a` four of the six already ended `CONVERGED` + `FAILED`, and the other two raised
    M2's `RuntimeError`.
  - Option A turned those two raises into a false success that the verifier catches.
- **What is wrong is the text.** §17 says "the solve is unaffected", and the limitation sentence
  says "solved but certified UNVERIFIED". Both are corrected (Q-S15 (1)).
- **Build lane:** pin the tally with the counts, and replace `ph_flash`'s sentence (spec §20 W10 (6)
  (a), (c)).

### Notes

**N-W10-1: the region and the verifier disagree on the energy balance at the same state.**
- At that state the region's per-row test passed: it is the last attempt's end state, and Newton
  returned `CONVERGED`.
- The verifier's `energy_balance.U-PHF2` fails by at least 0.37 mW more than the row allows.
- I did not establish why. It is recorded with §18 Q9's K04 follow-up.
- It matters because "residual and verifier describe the same balance" is assumed elsewhere.

**N-W10-2: §7.8 (ii) 5's "the lag sits on its linear mole rows" was incomplete.**
- The lag also reaches the downstream energy row, through the feed's enthalpy.
- Text made exact; no code change.

**N-W10-3: one move is missing from the B36 before → after table.**
- At `(0, 0, 90 kW)`, `U-PHF2`'s final regime went from `TWO_PHASE` to `VAPOR` (W3: at `819fd22`
  the attempts were (T,V) → (T,T), 7 iterations; now (T,V), 5 iterations).
- This is a dew-point regression value, recorded in B34 (a).
- **W3's trajectory for Q-S15 (1):** at `819fd22`, `(0, 0, 115 kW)` ran
  `(L,Z) → (T,V) → (T,T) → (V,T)` and cycled. Now it runs `(L,Z) → (T,V) → (V,V)` and is
  `CONVERGED`.

**The three questions: ruled as Q-S15 (1)–(3).**
- (1) Ratify 82/10/6/4/2, with the tally added.
- (2) Ratify the build lane's heater-style reading.
- (3) The screen reads the opening's inputs, and the exemption is narrowed.

### Not examined

- W10.1, W10.3 (B35) and W10.5, beyond reading their diffs.
- The identity hashes other than the `t05b` document's equality under Q-S15 (3); I take the build
  lane's protocol numbers.
- Whether the rejected alternative in Q-S15 (2) actually moves registered valve or reactor records.
  That is the build lane's statement, not measured here.

## Review of W10 (6) (b) (2026-09-25)

Design-lane review of `250a783` against ruling Q-S15 (3), as spec §20 W10 (6) (b) requires
before merge. Read: the commit's diff; `_contract_kernel`, `_kernel`, `_LiftedOps._answer` and
`at_candidate`, `_build_screen`/`tp_regime`, `_region_problem`'s `full`, and
`splits._descriptor`. Nothing run; the build lane's gate (3135 passed, 0 xfailed) and unchanged
identity hashes are taken as reported.

### Verdict

**Sound; no must-fix, no should-fix. W10 (6) (b) passes review.**
- The screen's leaving flash is now asked at exactly the leaving answer's inputs: `n` from
  `split.feed`, `T` from `temperature_id(split.stream)`, `P` from `split.pressure`. These are
  the inputs of `_contract_kernel`'s `_kernel(..., temperature=feed)` (region.py:628–629). The
  refusal and phase mapping are unchanged.
- **Temperature column, by style** (`splits._descriptor`, splits.py:265–287):
  - Products-style (PH flash): `stream` is the inlet, so the flash reads the feed's `T`. This is
    the change Q-S15 (3) asks for.
  - Heater-style (valve, duty-mode reactor): `stream` is the outlet, and
    `temperature_id(stream)` is `split.temperature`. So the flash is bitwise the pre-change one.
    That matches Q-S15 (2): the feed is the split's own outlet, and nothing moves.
  - TP-type splits pass `leaving=False` and flash at their own `T`, as `_contract_kernel` does.
- **The guard** (region.py:1305–1309): `at_candidate` asks `_answer` with the attempt regime.
  So `self._regimes[unit] == "ZERO_FLOW"` with a flowing feed is exactly the leaving branch.
  - A dormant feed returns `_zero_flow_answer`, recorded `""`, which was never sanctioned.
  - The exemption now covers only a flowing PH closure's in-domain refusal, as Q-S10 intended.
  - All answers are asked at `opened` before any write (Q-S12). So a leaving disagreement can
    only be a defect, and raising on it is right.

### Notes

- **N-W10.6b-1: the guard now also checks that the screen and the opening agree on the feed
  column's `T`.**
  - The screen reads `full(x)`, which fills the non-free columns from the attempt's `base`.
    `at_candidate` reads `_end` plus `candidate.x`.
  - When a products-style split's feed `T` is not a free column (an inlet from outside the
    region), the two readings agree only if Newton never moves non-free columns.
  - TP-type splits already relied on the same agreement for their own `T`.
  - If it were ever broken, the guard would raise; it would not silently mislead. No action.
- **N-W10.6b-2: the control in (d) (i) (`ph_units = frozenset()`) stands in for the pre-change
  screen.**
  - It is a faithful stand-in only because `U-PHF` is `TWO_PHASE` on that trial and so needs
    no flash. The docstring says so.
  - The decisive evidence that (d) (i) and (d) (ii) are falsifiable is the build lane's run
    against the old `region.py`. Both fail there.
- **N-W10.6b-3: no test pins the heater-style case.** The claim that the flash is unchanged is
  structural, and it holds only while `_descriptor` gives an outlet-style split
  `temperature == temperature_id(stream)`.
  - The unchanged identity hashes cover this today.
  - Optional hardening: assert that equality for every outlet-style rule in the splits tests.

### Not examined

- W10 (6) (a) and (c); the identity hashes and B31/B34 records beyond the build lane's report.
- Whether any registered flowsheet has a products-style PH split whose feed is a non-free column.
  N-W10.6b-1 matters only for such a split.
