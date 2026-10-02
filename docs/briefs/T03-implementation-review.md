# Brief — T03 implementation review

**To:** `reviewer` (design lane)
**From:** the session (build lane), 2026-09-24
**Design under review:** `docs/derivations/T03-phase-controller-spec.md` (A00–A26) and
`docs/adr/0005-phase-attempt-contract.md` (Proposed), written by the `specifier` at `c799ad9`
**Commit range:** `c799ad9..HEAD` on branch `wp/T03`
**Evidence:** `evidence/T03/<commit>/manifest.json` is being generated in parallel; you will be told
its path if it lands while you work.
**Deliverable:** `docs/reviews/T03-review.md` in the shape of `docs/reviews/T02-review.md`
(must-fix / should-fix / notes, each with `file:line` and a falsifiable test that would catch it), and
rulings on §5 below. Commit on `wp/T03`, staging named paths only; messages end with
`Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_01QMQnXcFna3j5D6Ai9Ja9AE`. Never set `reviewed`.

## 1. What was built (work order §17)

| Item | Where |
| --- | --- |
| W0 measurement (Q1: no stop) | `spikes/t03/w0_screen_measurement.py` + `.json`: A21 attempt 2 worst 0.9623, A22 0.9078 / 0.3281 |
| W1 `phase_contract` | `orchestrator/trace.py`, `schemas/solve-policy.schema.json` |
| W2 one decision function | `orchestrator/phase_contract.py` (`adjacent`, `WallObserver`, `check_opening`, `decide`, `jacobian_pattern`); `attempts.py` and `region.py` both call it |
| W3 the screen | `region.py` `_screen`, `_region_problem(screen=, opening=)` |
| W4 block-not-landing | `region.py` `_LiftedOps.blocked`, `_watched_variables` (TWO_PHASE units only); `_LandingWatch` removed |
| W5 closure by branch found | `region.py` `_LiftedOps.converged`, `_branch_found`; `kernel_disagrees` at the end state |
| W6 opening checks | `phase_contract.check_opening`; outcome `CHECKPOINT_INCOMPATIBLE` (trace, schema, `verify/failure.py`) |
| W7 contexts, pattern, records | per-attempt `EvaluationContext` objects (tear: `tear.as_newton_problem(attempt)`); `AttemptContext.jacobian_pattern` from `CasadiCompiledProblem.structural_pattern()` (declared sparsity, no evaluation); `attempt_opened` hash/alpha/message |
| W8 provenance | `attempts.provenance_item`, `orchestrator/roots.py` (`root_fingerprint`, `same_root`), `merge.py`, `verify/certificate.py`, `schemas/solution-certificate.schema.json` |
| W9 no guess | `application/binding.py` (`missing_guesses`), `orchestrator/executor.py` (`_missing_guess`) |
| W10 cases | four revisions under `benchmarks/syn001/cases/`, `benchmarks/registry.yaml` |
| W11 identity | `scripts/t03_identity.py` in `scripts/k05_structural_identity.py` |
| Tests | `tests/test_t03_phase.py` (A06–A12, A24), `tests/test_t03_contract.py` (A02–A05, A13–A18, A23), `tests/test_t03_roots.py` (A19–A22) |

## 2. What I ran and measured

Gate green at **1579** (1539 before T03). PHS-01…05 reproduce the twin **trial by trial**: every
iteration, halving, verdict, reported regime, trial temperature (1e-9 rel), opening α, cause, end
temperature, landing `α_max` (~1e-15 rel), phase-rejection and invalid counts. PHS-SYN-1/2 match in
exact dyadic arithmetic. Ablating the adjacency rule turns PHS-01/02 back into `ACTIVE_SET_CYCLING`
(spec §6.7). REC-05: MR-A/MR-C `SAME` on `S1`, MR-A/MR-B `DISTINCT`; SYN-001 one root, three
histories `SAME`. K03's OFF-B restart point unchanged.

## 3. Decisions I took that you should check

1. **A removed row's orphaned parameter is dropped** from the declaration (`binding.py`, using the new
   `graph.trace.parameters_read`, which records builder lookups and evaluates nothing). Found by A20:
   the guess reached `constants_sha256` through `HEAT-T`'s parameter, so the A02-360 revisions from
   different guesses were `NOT_COMPARABLE`.
2. **No-guess (W9):** the specification schema requires `value` or `bounds`, so the no-guess revision
   gives `bounds` (the provider domain). The binding assembles the declaration with the flowsheet's
   declared default for that coordinate (then dropped by 1) and records `missing_guesses`; the
   executor refuses before any pre-solve.
3. **`branch_provenance.decision`** for an attempt whose proposed restart the gate refused is
   `restart` with its cause — the convention `benchmarks/t03/reference_values.yaml` uses for PHS-05 —
   not `terminal`; spec §8.1's table does not say.
4. **`delta_scaled_inf`** is a float on the fingerprint (spec §10 says no float is added); registered
   as an ADR 0007 D1 exact field through the K04 generator.
5. **The cycling `solve_closed` message** follows §4.10's grammar; §10 lists only OFF-B's
   `attempt_opened` message as a re-registration, but `test_k03_attempts.py`'s cycling test changed
   with it.
6. **The region records no `solve_closed`**; its terminal decision is `RegionResult.message` (the
   executor's `solve_closed` carries it in a plan run).
7. **`_LiftedOps.at_candidate`** takes the changed units' regimes from the kernel at the candidate
   state (equal to the candidate's by construction) and builds the signature from them.
8. **`jacobian_pattern`** counts `{rows, columns}` as integers plus the id-list hash (spec §5.2's
   "`{rows, columns, nnz, sha256}`"); the tear path records the plan's inner block.

## 4. Where I am least sure

- `decide`'s precedence when a lifted attempt ends `BOUND_BLOCKED` with no watched blocker *and* a
  wall inside the stall window (rows 3–5 of §4.8).
- The screen's kernel-refusal mapping (`invalid_trial_state` unless the provider says `error`).
- Counters: the screen's K-value and flash calls go through the region's `PropertyMeter` (metered and
  budgeted since T02 S4); the spec says "through the exact property cache", which the region path
  does not have.

## 5. Questions for your ruling

- **Q1** — decision 3 above: is `restart` the intended `decision` for a gate-refused restart?
- **Q2** — decision 1: is dropping orphaned parameters from the declaration's identity sound
  (it changes `constants_sha256` of every A02 revision)?
- **Q3** — the spec's §14 Q2–Q5 defaults were applied as written (no far-restart refusal;
  `phase-controller case` outside the denominator; `δ_root = 1e-4`; `alpha` kept on
  `attempt_opened`). Confirm or amend.

## 6. Not worth your time

Formatting, the registry prose, schema JSON layout, fixture regeneration, the manifest script.
