# S08 review (WO-1 to WO-4; the package's single `reviewer` pass)

**Reviewer:** design lane (`reviewer`), 2026-10-26. **Reviewed:** `wp/S08` at `2ae64c2b`, range `390e0af5..2ae64c2b`
(`column_solve.py`, `column_blocks.py`, `tests/test_s08_*.py`, `tests/test_s02_column_wo3.py`, `scripts/s08_identity.py`),
read against `docs/derivations/S08-design.md` (`943276d8`), ADR 0048 and `docs/S08_DECISIONS.md` W1-1 to W4-8.
**Brief:** `docs/briefs/S08-review.md`. **Rulings:** S08-design §13 (Amendment 1), register R-733 to R-736, S03 §10.1 and §14
(applied in this commit).

## Verdict

**The route is right, and the implementation follows §5 step for step.** Stage A is today's path. `target_attempt` is the old
`solve_target` body with its two raises moved to the callers, in the same order. G1 is a sufficient proof for the registered
configurations. Item 6 is implemented as specified. The block endpoint matches §5.3, including the exact `+0.0` pins and the
exact L-block mass balance. That balance follows because the Thomas rows with `S = 0` divide by exactly −1.

**Before `reviewed`, fix three things in the tests and one in the code.** One registered mutation, A14 (b), does not test what
it claims. Four rows of §5.4's candidate table are never exercised. One builder error path can turn a typed Stage-A answer into
an unhandled exception.

The design's premise is also misattributed in §3 F1. It has no effect on the route, and is corrected in §13.1.

None of this changes a registered state, an outcome or a digest.

**What I ran** (scratch only, nothing committed). I ran A14 (b) as the design states it: x⁰'s L-block vapour set to `K(T_s) ρ_s l`
after the energy solve.
- P3: candidate `(0, 2)` is **built**, converges, and is recorded `near_trivial_split(4,5)`. Stage A's `HOMOTOPY_STALLED` is
  returned, so A08 fails, for the intended reason.
- F1: `AcceptanceDefectError`, with the note "tried: (0, 2) near_trivial_split(4,5)".
- I also measured SYN-001's `∂ln K/∂T`: 0.019–0.036 K⁻¹ over 340–400 K, and 0.026 K⁻¹ at 370 K.

## Findings, most severe first

1. **Must fix. A14 (b) does not test exact zeros.** `tests/test_s08_roots.py:253`, W4-5.
   - The mutant feeds the L-block into `_core_flows` as core. But `_build` step 5 (`column_blocks.py:462`) then resets every
     L-block vapour to `+0.0`.
   - So x⁰ still has exact zeros. The mutant only breaks the L-block mass balance, and the candidate is refused
     `block_energy_outside_domain` for that reason.
   - The docstring's "its vapour is no longer exactly zero" is false.
   - Replace it with the mutation of §13.5, which W4-5 listed as its alternative. Assert the candidate record
     `(0, 2, "built", "CONVERGED", "near_trivial_split(4,5)")`, and that A08 fails. That also covers §5.4's third row.

2. **Should fix. §5.4's candidate rows are untested** (`column_solve.py:1464–1558`).
   - No test makes a built candidate end typed, end `unsupported(…)`, or fail a non-item-6 §8 item.
   - No test has more than one candidate, so neither "the next candidate is tried after a failed solve" nor `accepted > 0` is
     pinned.
   - A mutant that returns after the first built candidate, or that swallows a candidate's defect, passes every test today.
   - Add A17 (§13.6).

3. **Should fix. W2-4 is reversed: a `BandError` in the builder must refuse the candidate** (`column_blocks.py:195–203`).
   - Today, a provider refusal or an exhausted bisection in steps 3c or 7 propagates out of `solve_column`. It does so after
     Stage A has already produced a typed answer.
   - Stage B can therefore turn `HOMOTOPY_STALLED` into an exception. That breaks §5.3's "a refusal never ends the solve by
     itself" and §2 item 7.
   - Stage A's `bubble_point_endpoint` may keep propagating, because that is unchanged pre-S08 behaviour. The two paths have
     different contracts.
   - Fix: catch `BandError` in `_bubble` and refuse with `bubble_point_refused` (§13.3). Test it as an A04 row.
   - SYN-001 does not reach this path on any registered case, so G1 is unaffected.

4. **Should fix (docs, done here). The premise in §3 F1 is not what the evidence shows** (brief §5, last question).
   - Every failing restart in `measured.txt` uses a signature with no regular root:
     - P1's closure `(2P, L, L, L, L)` has no vapour source under stage 1. §4 (c) itself says P1's only regular signatures are
       2P×5 and L×5.
     - P3's `(2P, 2P, 2P, 2P, L)` has no vapour source at stage 4. Its inflows are a cold liquid feed, `Q_4 = 0`, and liquid
       from stage 3 at `P_4 > P_3`.
     - P2's restart does not conform to the block rule at all.
   - Rebuilding the opening at the same signature (`S08_SWEEP=1`) could not help.
   - No measurement opens a source-valid signature from Stage A's failed end state. So "restarts fail because they open from the
     failed state" is not established.
   - What is established is that the contract proposes signatures without the column's source structure. That reason supports
     the route and rejection (a) even more directly. §13.1 rewrites F1, §4 and rejections (a)/(b); R-733 records it.

5. **Should fix (test). The end-port reading of §5.2 is unpinned.**
   - `sources()` makes every flowing inlet a source of its declared phase, at any port. So D1's top `VAPOR` inlet is a vapour
     source at stage 1, and F1's bottom `LIQUID` inlet is a liquid source at stage 5.
   - WO-G's transcription defaults to the table's literal reading. It proves that no registered list depends on the
     difference, and so no test can tell the two readings apart.
   - The implementation's reading is the physical one and is now normative (§13.2). Pin it with A18.

6. **Note, needs a decision (Q6), my lean: keep. Item 6 is stricter than the row tolerances on low-traffic stages.**
   - F4's bound gives `|T − T_bub| ≲ Σ tol_i / (L V Σ x_i ∂K_i/∂T) ≈ 1.1e-5/(L V)` K, with `tol = 9.3e-8` and L, V in mol/s.
   - That exceeds `τ₆` when `L·V < ~0.1 (mol/s)²`. Registered stages reach 0.2 mol/s (M3).
   - The 41× margin (Q5) therefore measures where Newton stopped, not a bound.
   - A correct root whose last Newton step lands near tolerance on such a stage fails item 6. With no accepted candidate it then
     raises `AcceptanceDefectError`, where before S08 it returned `CONVERGED`.
   - Keep the raise: a typed alternative needs a frozen `SolveOutcome`. But record the limitation in §11 (§13.4, R-735). Revisit
     if any case ever hits it.

7. **Note. W3-2's prefix test is correct but fragile** (`column_solve.py:1302`).
   - No other failure string starts with `"§8.6: "` today. An item-6 subset computed apart from `acceptance_failures` would be
     sturdier, but there is no action now.
   - Related, from W1-3: a band refusal on a `TWO_PHASE` stage reads as `near_trivial_split(j)`. The failure string,
     "error inf K", still tells the two apart.

8. **Note. Stage B gives each candidate a fresh policy budget, and appends its events to the caller's trace** (W3-7, Q8).
   - When `solve_column` is wired to the application layer, a request-level `max_property_calls` or wall-time budget can be
     exceeded by up to (1 + |candidates|)×.
   - When no candidate is accepted, the trace ends with events from a solve that was not returned.
   - Neither matters while `solve_column` has no `src/` caller.

9. **Note.** `test_a09_…` and `test_a14_the_f1_route_holds_unmutated` (`tests/test_s08_reentry.py:440–446`) run the same check.

**Brief §6, F1 at 2.8e-3 and D1 at 6.0e-3 of the state tolerance: sound.**
- F1's `T` deviation is 2.9e-4 × `T_ABS`, which is 2.9e-8 K. That is exactly A11's P3–F1 core difference (2.9e-8 K,
  1.2e-9 mol/s). The deviation is therefore F1's own Newton stopping point, while P3 happened to stop one quadratic step deeper.
- D1 reaches the same root from two openings at 6.0e-3 and 1.2e-6.
- The 1/10 watch line of R-732 holds with 16× room.

**G1 (brief §5): sufficient.**
- It hashes every field of the attempt record, compares raises as outcomes, imports each tree in isolation, and rebuilds
  `stage_a` the way the pre-S08 top level was built.
- Code reading confirms the remaining Stage-A changes have no effect on registered results:
  - `single_phase_specified_stage` now runs on every `CONVERGED` answer; it is pure.
  - `continued` moved into `_column_answer` with the same expression.
  - Item 6 adds provider calls only after the region result is final.
- Blind spots: non-default `profile_shift`/`ratio_scale` runs, covered by the suites (G3); trace content; and unregistered
  columns, where the behaviour changes by intent.

**Item 6 against existing acceptance (brief §5): no conflict.**
- It cannot reject a registered root (A12).
- Its only false-reject mode is finding 6.
- It is what makes A14 (b) fail in the right way: without item 6, the mutant's near-trivial split would be returned as
  `CONVERGED`.

**Refusals in the block endpoint (brief §5): no refusal hides a success on the registered cases.**
- `inadmissible_endpoint` is judged on the approximate x⁰, so in general it could refuse a candidate whose root is admissible.
- F1, the closest case, is structurally safe. Its stage-4 liquid is stage 3's, and its energy solve gives `T_4 = T_3` exactly
  (constant `C_P`, `Q_4 = 0`). Its margin is therefore the pressure effect alone (≈ 0.37 K), whatever the core's error.
- No success hides a refusal: every refusal path returns `CascadeFailure` before any solve.

**Independence (brief §5): yes.** WO-G imports nothing from `src/`, its JSON is SHA-pinned in the tests, and its roots come
from core decoupling plus exact energy passes.

## Rulings (brief §4)

**1. Build decisions.** Confirmed as logged unless stated otherwise.

- **W1-1 to W1-5:** confirmed.
- **W2-1, W2-2, W2-3, W2-5, W2-6:** confirmed. Their refusal reasons are now listed in §5.3 (§13.3).
- **W2-4: reversed** (finding 3).
- **W3-1 to W3-4:** confirmed.
- **W3-5: confirmed.**
  - An exception note keeps `failures` and `str(error)` exactly S02 §8's, and still names the candidates in the traceback.
  - A subclass would buy nothing while no `src/` caller catches the error.
- **W3-6: confirmed. Correct the log's reason.**
  - Before S08, such a state returned `CAPABILITY_UNAVAILABLE`, not a defect.
  - Running Stage B is right, because that unsupported answer described a near-trivial false root. §13.7 states it.
- **W3-7: confirmed** (finding 8).
- **W3-8: confirmed.** P1's Stage-B root has no `TWO_PHASE` stage, so item 6 holds vacuously there. §13.9 records the count.
- **W4-1 to W4-4, W4-6:** confirmed.
- **W4-5: reversed** (finding 1).
- **W4-7, W4-8:** ruled below.

**2. Stale S03 sentences (applied in this commit, exact text).**

§10.1's limitation list now reads:
- *the column has no phase-transition robustness* beyond S08's block re-entry;
- the column converges to a block root `V^a 2P^b L^c` that §5.2 of S08-design generates (S08); other one-phase-section roots
  may still end typed;
- P1's all-two-phase path (S08's Stage A) still ends that way (`HOMOTOPY_STALLED`; attempt 1 `(2P, L, 2P, 2P, 2P)` breaks the
  rule), and S08's Stage B then converges P1 to `LIQUID ×5`, the closed form (S08-design §6.1);
- that typed outcome is recorded as `reentry.stage_a` (S02 A12 as amended by S02 Amendment 4), never returned as a success.

The "Reopening" paragraph gains: *Reopened by S08 (ADR 0048): block openings from the column's sources in its initializer;
ADR 0005 D4 unchanged.*

In §14, "A later package is queued for it (Q-S03-4, §17.7); S03 neither depends on it nor anticipates it." becomes: "That
package is S08 (Q-S03-4, §17.7; ADR 0048); S03's own cases and verdicts do not depend on it."

**3. Requirements.**
- S08 evidences **X31**'s "invalid specs/phases" clause, because it changes the expected outcome of S02's phase case P1 and adds
  P2, P3, F1, D1 and item 6. It does not touch X31's reference clause.
- Add S08 to X31's `owner_packages`. Set the manifest's `requirements: [X31]`. The verdict stays `null`.
- `depends_on` stays `[S02, S03]`. S06 is not a ledger package and cannot be listed; a YAML comment names it, as the source of
  G1's and A16's S06 cases.

**4. Frank's questions.** These are technical opinions; the decisions stay Frank's.
- **Q1 (block roots from sources only): the default is sound.**
  - (V2) is a necessary condition in the ordinary cases.
  - It is not universal: mixing two saturated vapours can condense, so a core top need not be a liquid source.
  - Every other one-phase root still ends typed, honestly, and §11 already disclaims it.
- **Q3 (dotted ids, F5 → follow-up): the default is sound.** S08's candidates never use contract adjacency.
  - The follow-up will re-baseline A06 and G1's P1 `stage_a`, because they pin `phase_wall(stall, )` strings.
  - It may also move Stage-A restart points, and with them whether Stage B triggers on a registered case.
- **Q4 (near-trivial splits in flash units and S01 cascades → follow-up): the default is sound, but it is a correctness exposure,
  not only a scope choice.** A false `CONVERGED` there is possible today. A cheap first step for whoever takes it is F4's scan:
  saturation errors on every registered `CONVERGED` flash and cascade root.

## Work for the build lane before `reviewed` (one WO, tests and one guard; no numerics change)

1. A14 (b) as §13.5.
2. A17 and A18 as §13.6.
3. `_bubble` refuses on `BandError` (§13.3), with its A04 row.
4. W3-6's log line corrected.
5. X31 mapping and the ledger comment (ruling 3).
6. Re-run G1 and the manifest, expecting no digest change, then the T08 harvest, the full gate and CI.

## Not examined

- `scripts/s08_evidence_manifest.py` beyond its A13 rule.
- WO-G's 50-digit mathematics (brief §7).
- The probes' history.
- How `_k_values` and `_initial_state` behave on provider refusal.
- Trace consumers.
- aarch64 (CI pending).
- Lint and typing.
