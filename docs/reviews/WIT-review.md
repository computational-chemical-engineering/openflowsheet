# WIT review — the derivative witness at small and dormant flows (single reviewer pass)

Status: review, 2026-11-08. Design lane (`reviewer`). Brief `docs/briefs/WIT-reviewer.md`. Reviewed: `wp/WIT` at
`c32e3e4b` (worktree `.claude/worktrees/wit`, read only) against K04 §4.8.1–§4.8.9, ADR 0073 (Proposed),
`WIT_DECISIONS.md` D-1…D-4 and E-1. This review does not set `reviewed` on anything.

## Verdict

**Not mergeable as it stands; one must-fix, then mergeable.** The implementation follows the spec faithfully. The
class-5 identity argument holds by construction, and the escalation never reads the AD Jacobian. But the escalation
can turn a correctly failing witness into a pass on a wrong Jacobian entry. A round-off plateau does it (F-1), which is
the case the brief asked about. I reproduced it on the branch's own code. The fix is one rule plus one assertion. E-1's
new verdict is honest and should be adopted as M-6. Its manifest sentence moves three registered byte identities, and
that is Frank's decision.

## Must fix

**F-1. A quantization plateau resolves a column to 0 and passes a dropped term** (`checks.py` `escalate_column`, the
resolution test; spec §4.8.3 derivation item 2).

- *The flaw.* The spec argues that "where roundoff dominates, `|D̂_k − f′| ≲ r_k ≲ e_k`". That is false when roundoff
  quantizes a row's stencil flat. If all four values of level k are bitwise equal, its estimate is 0, up to the
  accumulation's rounding (~1e-22). Two consecutive flat levels then agree (`e_k ≈ 0`) on a wrong value. A non-flat
  quantized numerator cannot do this, because the same numerator at half the step doubles the estimate. So the flat
  case is the systematic one.
- *When it happens.* A row whose intermediate magnitude `|A_i|` is large against its scale hides a scaled derivative
  `d̂ ≲ 5.5e-12 · 2^(k−1) · |A_i|/S_F,i` at level k. At k* = 8, a defect just above `τ_D` hides once
  `|A_i|/S_F,i ≳ 140`. At k* = 5 that becomes `≳ 1.1e3`. I estimate that large-flow enthalpy rows and 1e7 Pa pressure
  rows on the registered scales lie at 1e2–1e3; that is an estimate, not a measurement.
- *Reproduced* (scratch probe on the branch's analytic doubles; not committed). Column `S1.n.A` (scale 3) has two rows:
  - W1's curved `R1`, with a correct AD entry, so the column needs deep levels;
  - `R2 = (BIG + c·n_A) − BIG − c·x0`, whose true scaled slope is 2e-7 = 2 `τ_D`, and whose AD entry is declared
    0.0: a dropped term.

  The registered stencil fails, which is correct. For `BIG` ∈ {1e4, 3e4, 1e5} × `x0` ∈ {2, 2.5, 3}e-4, 8 of 9
  configurations resolve at k* = 3–5 with `|D̂(R2)|` ≤ 2.2e-22 (exactly 0.0 in seven of them), and the witness
  reports **pass**, on-pattern ≤ 1.8e-10. Before WIT the same tear was `fail`.
- *Minimal correction (design lane, one sentence in §4.8.3 (c)).* A level whose four values in some row are bitwise
  equal (a flat stencil) cannot be `k*` or `k*−1` when a coarser stencil of that row was not flat, whether the
  registered pair or an evaluated level. Test the values, not the estimate: the accumulated estimate of a flat stencil
  is not always exactly 0.0. A row that is independent of the column is flat at every level and is unaffected.
- *Then.* Add the probe as WIT.A15 (expected: unresolved, `fail`, value bitwise the registered one, as in A05).
  Re-measure A08 and A09 and E-1's window under the rule; I expect no change there, but that is unmeasured. Until the
  rule is in, §4.8.8's "a false pass would need that accident to coincide with an AD error" is not true.

## Should fix

**F-2. Classes 2 and 4 apply to a `ZERO_FLOW` split, contrary to §4.8.8** (`checks.py` `witness_classes`).

- §4.8.8 states: "A `ZERO_FLOW` split on a γ–φ-IG basis … the feed's `<S>.n.<c>` stays central and refused, so the
  witness stays `unsupported`."
- The code classifies every dormant side of every split. When both sides are dormant, the liquid side becomes class 2
  and the vapour side class 4.
- The feed stays refused only if some block refuses a negative feed flow, and that is assumed, not shown.
  - For a flash-style split (`splits.py` `_descriptor`, `style != "outlet"`), the feed is the inlet stream. That inlet
    can itself be an upstream split's dormant vapour product, which is class 4, so it is differenced forward and never
    refused.
  - For an outlet-style split, the feed is `<S>.n.<c>`, which only linear split rows may read.
- Either way the unmeasured case of Q-WIT-2 can be certified `VERIFIED` silently, instead of "recorded and returned"
  as Q-WIT-2 intends.
- *Minimal correction.* In `witness_classes`, skip a split whose `feed` tuple is all exactly 0.0. Its sides then fall
  to class 5 at `x = 0`, as today. Add an A12 case or a unit case with a both-sides-dormant split asserting that
  classes 2 and 4 are empty.
- *Alternative, which I would not take.* Change §4.8.8's text and accept the case unmeasured.

**F-3. The path "a refused registered point, escalated and unresolved" has no test** (§4.8.3 (d), second bullet).

- I probed it: W2's residual at `n_A = 1e-9` makes all nine levels inadmissible. Both checks come out `unsupported` with
  `witness_stencil_invalid_trial_state(S1.n.A)`, which is correct.
- Add that as a test. Also add one for §4.8.3 (f): a resolved refused column followed by a refused non-component
  column must name the later column.

**F-4. A1 is measured only on an outlet-style split.**

- On a flash-style split the vapour tuple is the vapour product stream's own `<S>.n.<c>`. Every downstream unit reads
  it, so it is outside §4.8.4's affinity argument, which covers the split's own rows.
- I found no false-pass mechanism. The forward stencil is a true one-sided derivative, so a pass means the AD equals
  it. A non-affine reader gives `fail`, which is conservative, but `derivative_limitation` then blames the AD for a
  missing derivative.
- Before ADR 0073 is accepted, measure one flash-style dormant-vapour case where one exists on Wilson (OPT's M-4 state
  is the candidate), or record that one is missing under Q-WIT-4.

## Rulings

1. **E-1 — adopt as M-6.**
   - *The new verdict is an honest VERIFIED.*
     - The measured TWO_PHASE edge lies between δ = 2.4e-4 and 2.6e-4. That is exactly the absolute-conditioning edge
       already registered: R-282's amendment gives |δ| ≈ 2.48e-4, and the manifest gives "the absolute limit at
       [L/n_tot =] 1.5e-5", i.e. δ ≈ 2.43e-4. The witness was simply the binding limit before; the next registered
       limit now binds.
     - Along `S3.n.NH3` the liquid is pure NH3 (x ≡ 1), so the column is near-affine (`e_5` = 8.9e-16 at δ = 1e-4).
       F-1's rule will not touch it, but re-measure it.
   - *M-6, part a (no identity move; may merge).*
     - Re-bracket the TWO_PHASE edge at (2.4e-4, UNVERIFIED) and (2.6e-4, VERIFIED).
     - Keep 5.3e-4 as a VERIFIED case that asserts `S3.n.NH3` escalated, so the move stays pinned.
     - Update the two G7(c) docstrings.
     - Add M-6 to §4.8.6.
     - Add a dated note to R-282's amendment: the witness stencil is no longer one of the three limits, and the window
       ends at |δ| ≈ 2.5e-4 on both sides.
   - *M-6, part b (the `c1.tp_flash` manifest sentence, `flash.py:343-349`) — **needs Frank**.* Any byte change to
     `flash.py` moves:
     - c1.tp_flash's `implementation_artifact.artifact_hash` (`file_sha256(__file__)`, `flash.py:243-246, 367`);
     - F0 M9's entry `src/openflowsheet/models/c1/flash.py` = `f228a4a3…` (`benchmarks/f0/corpus.json:1894`), so F0
       `--check` fails until M9 is re-recorded for that file;
     - L01.A22's byte pin (`tests/test_l01_records.py:410-412`, "byte-identical to the L01 base"). That pin needs an
       L01 amendment, not a silent re-pin.

     `model_version` does not move: it is the label plus the structure digest (`canonical.py:496`). Per R-940,
     `artifact_hash` enters none of M1–M8. No other copy of the sentence is registered.

     I would correct the sentence in its own commit with those three moves, because as written it misstates where
     VERIFIED begins. The alternative: leave it stale, record that in the register, and fold it into the next c1
     identity move.
2. **Independence and soundness.**
   - Independence holds. `escalate_column` reads only `compiled.residual`, the state, the step and the scales. A07's
     residual-only double proves it.
   - Selection is not independent of soundness, though: see F-1.
   - Kinks are safe:
     - at a kink, central stencils agree on the symmetric mean, and the AD's one-sided branch then fails, which is
       conservative (a mean-valued AD is the status quo);
     - a kink or jump inside the stencil makes levels disagree by O(Δ) or O(jump/h) until `2h_k` clears it, after which
       the levels resolve to the true derivative.
   - The round-off plateau is the hole (F-1). NaN handling under D-4 is sound.
3. **A1 / A2.**
   - A1: accept with Q-WIT-4's default; F-4 is the measurement gap.
   - A2: accept, recorded as `derivative_witness_partial`. On flash-style splits the listed columns also carry
     downstream units' entries, which go unwitnessed. That is disclosed by the listing, and §4.8.5's "the same unit
     witnesses those" does not cover it (note).
   - **D-1 — needs a decision.** The literal reading complies with ADR 0073 D5, but a Wilson certificate that says
     `pr_c1_zero_flow_columns` states something false. No registered certificate carries a class-2 record yet, so a
     distinct reason (e.g. `gamma_phi_dormant_liquid_side`) costs one D5 sentence now and a record move later. I
     would amend D5 before acceptance.
4. **D-2, D-3, D-4, and the no-move claim.**
   - D-2 accepted. The `escalations` out-parameter is test-only, and no certificate caller passes it.
   - D-3 accepted. Class 1 is equal on every variable column, and F0 confirms it.
   - D-4 accepted.
   - The no-move claim for passing certificates holds by construction for class 5. A passing column runs the same
     arithmetic, in the same order and number of evaluations, and the maximum of per-column maxima equals the old
     running maximum, NaN rows included.
   - For classes 2 and 4 the claim rests on providers refusing negative flows (ADR 0001 D2). It is checked on F0 (A13)
     and the 2717-test sweep, not on the full suite.

## Notes

- *A12's "pairwise disjoint" is a tautology for a dict.* The useful part is the check that `unstenciled` and
  `one_sided` match the classes.
- *A pre-existing hole, not WIT's:* the witness maxima drop a NaN row with status `ok`, because Python's
  `max(0.0, nan)` returns 0.0.
- *Cost:* up to 36 evaluations per escalated column, including ADV-06 M's 21 unresolved columns. This was not timed.

## What this review did not establish

- I read the source diff (`checks.py`, `certificate.py`), the WIT tests, the spec and the ADR.
- I ran `tests/test_wit_witness.py` (9 passed) and two scratch probes, single-threaded at load ≈ 32.
- I did not run the system tests, F0, X10 `--check` or the full suite. The "exactly M-1…M-3 + E-1" claim still needs
  the full gate before merge.
- I did not check `wit_reference.py`'s 49 claims, the X10, envelope and support-matrix re-records, the S11
  cross-references, `wit_support.spy`, or the reference-platform bitwise values.
- I did not verify F-2's scenario on a real flowsheet. It is an argument from `splits.py` and the class table.
