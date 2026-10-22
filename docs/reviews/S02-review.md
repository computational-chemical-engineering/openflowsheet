# S02 — independent review (design lane, `reviewer`), 2026-10-22

Branch `wp/S02` at `9ceb6eb`. Brief `docs/briefs/S02-review.md`. Read: spec §0–§18, ADR 0044, `docs/S02_DECISIONS.md`,
`column_solve.py` (§18.2 endpoint, solve path, §8), `rows.py` (ratio, fraction, bubble), `scaling.py`, `recovery.py`
and its three call sites, `tests/test_s02_column_wo2b.py`. Ran: `pytest tests/test_s02_column_wo{1,2,2b,3}.py`:
181 passed, 2 xfailed (A14's sha clause), 17 s. Probe (scratch, not committed): the attempts before edge 3 on all ten
S02 paths through `solve_column`.

## Verdict

**Sound with one must-fix.** The bubble-point endpoint is what §18.2 says it is: the algebra checks out (`ρ_1 = 1/RR*`,
`ρ_N = BR*`, `φ = RR*/(1+RR*)`, the total condenser's diagonal), ratio rows are never continued, and A05 plus A13 pin
it (A13 checks that every re-binding names only the continued parameters). The `dimensionless` kind is column-only as
R-536 says. `R2` is registered and asserted. ADR 0044's predicate is wider than its own rationale (M1). That must be
fixed before the ADR is accepted. Counts: must-fix 1, should-fix 3, note 5.

## Findings

**M1 — must fix. ADR 0044's predicate accepts restarts that no globalization failure caused.**
`src/openflowsheet/orchestrator/recovery.py:50-55` is due on `LINEAR_SOLVE_FAILED` whenever `attempts >= 2`. §18.3 and
ADR 0044's rationale are narrower: the final signature was chosen *after a globalization failure of attempt 0*, so
item 0's signature may still be the right one, and that is the only reason edge 3 can help. A restart after an attempt 0
that ended `CONVERGED` is a physical phase correction. Item 0's signature is then known wrong, and ADR 0010 D3's rank
reason applies unchanged. *Scenario:* such solves exist. T05b DZ-12's negative control ends with attempts
`["CONVERGED", "LINEAR_SOLVE_FAILED"]` (`tests/test_t05b_dormancy.py:720`). Run any such region through
`executor._eo_recovery` under `eo_recovery = "homotopy"` with a continuation parameter and edge 3 now fires. The
homotopy reconverges in item 0's signature, the contract makes the same restart, and the step either ends
`LINEAR_SOLVE_FAILED` again, now with `eo_recovery: taken`, doubled attempts and a changed replay record, or ends
`HOMOTOPY_STALLED` in place of the honest `LINEAR_SOLVE_FAILED`. Both contradict the ADR's "keeps the honest terminal
record". *Measured:* on every S02 path that relies on the ADR, attempt 0 ended solver outcome `BOUND_BLOCKED`. The paths
are M2, V-M1 `(RR, B)` and `(D, BR)`, and the 2P×7 attempt of A06b M1, per §18.5. The narrowed predicate therefore moves
no S02 result. *Fix:* due iff `len(attempts) ≥ 2` **and** `attempts[0].solver_outcome` is a core globalization failure
(`LINE_SEARCH_FAILED`, `STAGNATION`, `BOUND_BLOCKED`, `PTC_STALLED`, or `BUDGET_EXHAUSTED` of a core budget). The
predicate stays in `eo_recovery_due`, and the call sites pass the failed result's attempts.

**S1 — should fix (condition on ADR 0044). C2's suite evidence does not cover 240 tests.** ADR 0044 C2 and
`docs/S02_DECISIONS.md:72` ran a git-less snapshot. There, 85 failed and 155 errored on both sides (campaign, ledger and
V17 record tests), and failing identically on both sides shows nothing about whether those tests' outcomes moved.
*Scenario:* a registered campaign step whose region solve ended `LINEAR_SOLVE_FAILED` after a restart would change
outcome and replay identity unseen. *Fix:* `scripts/gate.sh` on the merge candidate (a git checkout), green and recorded
in C2. CI green on both architectures. A workstation scan of the registered step records for `LINEAR_SOLVE_FAILED` with
≥ 2 attempts, logged in `docs/progress.md` as a workstation item.

**S2 — should fix. A14's sha clause asks for an identity that cannot be derived** (`tests/test_s02_column_wo2b.py:309-332`,
strict xfail ×2; the manifest is `implemented` only because of it). See ruling R-552. *Fix:* withdraw the clause and its
xfails. Record the measured values in the build log.

**S3 — should fix. The §18.2 identity has no generator claim.** WO-G left it unemitted (Q-S02-WOG-1). Exactness of `x⁰`
is pinned only at kind tolerance (A05, `test_s02_column_wo2b.py:155-163`). *Scenario:* if §18.2 step 4 is dropped (flows
from `T^(k−1)`), the rows come out at about 1e-11, still under tolerance, so nothing catches it. *Fix:* ruling R-551.

**N1 — note.** `recovery.py:50`'s default `attempts=1` silently keeps the old predicate for a call site that omits the
argument. Fold this into M1: make the argument required and keyword-only, and update the two-argument T04 calls
mechanically (`test_t04_edge3.py:326-342`, `test_t04_review.py:104,127`; expectations unchanged).

**N2 — note.** A21 reads both roots' regularity from the generator JSON (`test_s02_column_wo2b.py:233-234`). That is what
§18.6 asks for, but it says nothing about the implementation's Jacobian at `R2`.

**N3 — note.** `singular_pairs` (`column_solve.py:423`) uses literal adjacency, and §4.3 says "ignoring `ZERO_FLOW`".
Literal adjacency is correct: a dormant stage in between pins `l_j = v_{j+2} = 0` and blocks the circulation, and dormancy
is unclaimed anyway. §19 aligns the text.

**N4 — note.** `region.py:957` gives the `dimensionless` `φ` no step tolerance under `newton_refined`. Its accuracy
follows from `split_i` (`|Δφ| ≤ τ_flow / V_2`; §8.3 requires `V_2 > 0`, and `V_2 ≥ 0.73` at `R2`). `binding.py:812` would turn a
promoted specification on `φ` into a `dimensionless` row, which `Scaling` refuses with a type, as R-536 intends.

**N5 — note.** `solve_column` records the shifted profile (`column_solve.py:929`) but passes `initial.profile` to
`solve_target` (`:933`). That is harmless: the profile only names the withdrawn pre-solve's `T` substitutions, and the
continued ids do not depend on it.

## Rulings (spec §19; register R-550–R-554)

- **Q-S02-WOG-1:** take the default. Generator stop 1e-42 K, claim every non-continued row `< 1e-40` (R-551).
- **Q-S02-WO2b-1:** take the default. Withdraw the sha clause; the shift clause is "`x⁰` within 1e-8 K, `CONVERGED`,
  state tolerance, `SAME`" (R-552).
- **Six variant sets, not five:** six is correct. §18.6 A05 and §18.7 had an erratum (R-553).
- **Q-S02-3 / R-533:** the block rule stays out of S02. P1's measured typed outcome goes to S03 as the fact R-533 was
  waiting for (R-554).
- **ADR 0044:** stays **Proposed**. It becomes Accepted when M1's narrowing has landed with A20 extended, S02's manifest
  is `tested`, and S1's gate, CI and workstation scan are recorded. This review has read it, so that condition is met
  (R-550).

## Build-lane fix work order (`opus-engineer`, about 60k)

1. **M1 + N1.** `recovery.py`: `eo_recovery_due(outcome, budget, *, attempts: Sequence[str])` takes the failed solve's
   attempt solver outcomes. `LINEAR_SOLVE_FAILED` is due iff `len ≥ 2` and `attempts[0]` is in `EO_CORE_FAILURES`
   (new constant, the five above). Pass it at the three call sites (`executor.py:864`, `cascade_solve.py:691`,
   `column_solve.py:876`). Update the T04 calls and the four stubs mechanically. A20's table gains
   `(CONVERGED, LINEAR_SOLVE_FAILED)` → not due, `(BOUND_BLOCKED, LINEAR_SOLVE_FAILED)` → due, and `(LINEAR_SOLVE_FAILED)`
   alone → not due. Acceptance: `pytest tests/test_s02_* tests/test_s01_* tests/test_t04_* tests/test_t03_*
   tests/test_t05b_*` green with no expectation changed outside A20.
2. **S2.** Delete `test_a14_a_shifted_sweep_start_gives_the_same_final_state_sha256` and `SHIFT_MEASURED`, and log
   the values.
3. **S3.** `s02_reference.py`: stop 1e-42 K, plus one identity claim per endpoint (ten). Acceptance: `--check` passes;
   every pre-existing key is byte-identical except the generator-stop `sweeps` values; the old claim list is a prefix.
   Put the new SHA into `REFERENCE_SHA256` and the new claim count into spec §0/§13.
4. **S1.** `scripts/gate.sh` on the merge candidate, CI on both architectures, ADR 0044 C2 updated with that run, and the
   workstation scan entered in `docs/progress.md`. Then regenerate the manifest (`tested` expected) and re-harvest.

## Not examined

The body of `column.py` (validation S1–S10, row declarations, initializer) beyond the tests; the generator's internals;
`scripts/s02_evidence_manifest.py`; the bodies of A10, A11 and A12; the S01, T03 and T04 suites (not run here).
