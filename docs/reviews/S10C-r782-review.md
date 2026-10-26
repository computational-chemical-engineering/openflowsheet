# S10-C R-782: focused review (design lane, `reviewer`), 2026-10-26

Branch `wp/S10C`, range `b3151d65..1bc65b86` (WO-R1 `f9122cc7`, WO-R2 `e88f72a9`, run log `1bc65b86`). Brief
`docs/briefs/S10C-r782-review.md`. Built against `docs/derivations/S10C-absent-component.md` (`b3151d65`), the K03 §5.3
amendment of 2026-10-26 and R-782. Build log: `docs/S10C_DECISIONS.md`, "R-782 (absent-component release)".

**What was read.** The whole design note. The whole code diff: `numerics/newton.py`, `scripts/s10c_release_detector.py`,
`tests/test_k03_r782_release.py`, and the A93 and T07 test diffs. Unchanged code it depends on: `_bound_aware_alpha`,
`_released`, `_trial_point`, `solve_newton`'s step section (`newton.py:540–660`), and the PTC step and polish
(`ptc.py:52–62, 425–445, 705–722`). Also A41 in `tests/test_s10c_columns.py`, the R-780 and R-782 entries, and the A93
amendment row in the T06 spec.

**What was run.** Two scratch probes, not committed.
- `_released` on synthetic column-shaped closed blocks: absent components times stages, both row orders, with and
  without one on-bound column left uncovered (F1).
- T07's THM-09 start 4, uncapped and at the test-local cap, with the event kinds counted (F5).

No suite was run. The build log's G-R1, G-R2, G-R4–G-R7 numbers are not repeated here.

## Verdict

**Sound.** No must-fix. The rule implements §4.1 literally. R-064's exactness conditions are unchanged; the code holds
them, not just the text. The code's acting predicate is the theorem's. The §4.4 inertness proof holds for the code as
written. The moved witnesses still test what they were registered for, and nothing registered was edited.

Counts:
- should-fix: 2, both needing a decision (F1, F2);
- notes: 4 (F3, F4, F5, F7);
- erratum: 1 (F6, written into the note as a dated erratum, R-783).

## Findings

**F1 — should fix, needs a decision. `_released` is recursive and superlinear, and R-782 puts it on the per-iteration
path** (`newton.py:873–891`, R-064's code, unchanged).

`augment` is a recursive Kuhn matching. The propagation of `outside` is a fixed-point loop over `matched`. Before R-782
the function ran only at `α_max = 0`. Under R-782 it runs at every iteration with `C ≠ ∅`, which for an absent component
is every iteration. The probe measured the cost per call on a closed block shaped like a column. Each absent component
contributes 2 rows and 2 columns per stage; rows are in stage order, and the timings in parentheses are for reversed
rows.

| `\|Z₀\|` | Time per call | Result |
| --- | --- | --- |
| 60 (C-MW) | 0.4 ms | |
| 1 000 | 21 ms (5 ms) | |
| 2 000 | 60 ms (7 ms) | |
| 4 000 | 213 ms (18 ms) | |
| 10 000 | 1.5 s (38 ms) | |
| 2 000 (one component, 1 000 stages) | | `RecursionError` |

The `RecursionError` is a hard failure in the Newton core. The exposure is R-064's: on such a system the first step
almost surely blocks, so R-064 calls `_released` too. R-782 multiplies the calls and makes the cost per iteration.

No registered case comes near this. The suite's largest `|Z*|` is 60, and SYN-001 never calls `_released` (§4.6).

*Minimal correction:* an iterative maximum matching (for example `scipy.sparse.csgraph.maximum_bipartite_matching` on
the closed-row × `Z₀` incidence) and a breadth-first worklist from the unmatched columns for `outside`. This is inert by
construction: `Z*` is the unique largest tight set, so the sorted tuple does not depend on which maximum matching is
found. Prove it with the following.
- An old-versus-new equivalence probe over random closed blocks.
- B33c i–v and G-R1.
- `S10C-IDENTITY` and `S08-IDENTITY`.

*Decision:* I would make it one separate, inert K03 commit after this merge. It should land before any case with a long
absent chain is registered (a discretized reactor, a long column), and a "Watch for" line goes on R-782 (done, R-783).
It need not block R-782.

**F2 — should fix, needs a decision. The invariant R-782 exists for is recorded but not asserted.**
`tests/test_s10c_columns.py:222` records `absent_flows_exactly_zero` under R-780, which says exact zeros are not
required.

§4.3's claim is that `Z*` stays at `+0.0` for the whole attempt, on every machine. This is platform-independent: the
rows close by IEEE products with exact zeros. On x86-64, C-MW reached `CONVERGED` with the lift too. A partial regression,
where the rule misses some iterations, therefore passes A40–A42 on x86-64 and is caught only indirectly, if it moves
A93-uncapped or T07's 94.

*Correction:* assert the 60 absent flows exactly `+0.0` in A41 for C-MW and C-EW. This needs a new register entry that
supersedes R-780's "not required" for these two cases (§4.7 item 1 kept it). *Decision:* I would assert it. It is the
direct witness of §4.3, and G-R2 already uses it as a pass criterion.

**F3 — note. Two cheap G-R1 gaps** (`tests/test_k03_r782_release.py`).
- (a) No case has `Z* ≠ ∅` and `Z* ∩ supp(d) = ∅`. That is the second early return (`newton.py:820–821`). Some of the
  204 non-acting calls among the suite's 384 go through it, the rest through `Z* = ∅`; that branch is what keeps those
  calls bit-identical.
- (b) "`α` and the landing unchanged" is tested only at `α = 1` with an empty landing, so `(α, L) == unmodified`
  compares `(1.0, ())` with itself. A third component that limits `α < 1` and lands would pin §4.2's actual content.

**F4 — note. The detector sees in-process solves only.** It patches the `newton` module of the pytest process. Solves
in `ProcessExecutor`'s spawned workers (`application/jobs/executor.py`) or in CLI subprocesses are invisible to it. So D
is acting-by-test for in-process solves, which is a lower bound in general. That WO-R1's D equals §4.6's scratch D (an
in-tree instrumentation that children inherit) is the evidence that no spawned solve acts today. *Correction:* one
sentence in the module docstring.

**F5 — note. The capped witnesses refuse earlier than the old ones.** Probe, THM-09 start 4:
- uncapped: `CONVERGED`, 94 records, 49 events, 4 attempts in 1 region;
- capped at 100: `BUDGET_EXHAUSTED`, 24 records, 14 events, inside attempt 1 of 1.

The every-record leg still covers regions and recovery (uncapped) and the budget refusal (capped). It no longer covers
a refusal after recovery. A93's cap clause, `property_calls == requested_evaluations == cap`, does not depend on where
the refusal falls. A cap tuned to land in a later attempt would be fragile across platforms. No action; worth one line
in the decisions log.

**F6 — erratum (written: note §4.5 erratum 2026-10-26, R-783).** §4.5 says the common path "allocates nothing". The mask
allocates about six `n`-length boolean temporaries per iteration; negligible (G-R6 −1.2 %), but the sentence is
false. §4.5 also gives `_released`'s cost as "one CSR conversion of `J` and one pass over the rows", which leaves out
the matching and the propagation (F1).

**F7 — note (residual risk; a "Watch for" on R-782, done).** Consider an absent set whose only source rows are products
with other members of `Z*`: autocatalysis, or a recycle seeded only by itself. Before R-782 roundoff could, depending on
the platform, seed it off the trivial root. Now it is held there deterministically. That is exact Newton and the right
behaviour. A case that needs the seed must get it from its initializer, never from roundoff. §7 Q2 covers the measured
part: none in the suite or in 880 starts.

## Rulings on "Look hardest at"

1. **The exactness conditions are literally unchanged.**
   - `moving` (`newton.py:816`) is `_released`'s `on_bound` (`:854`) plus `d ≠ 0`, so `C ⊆ Z₀`.
   - `_released` itself is untouched: exact `F_r != 0.0` skip, exact `J` nonzeros, support ⊆ `Z₀`, exact squareness
     count.
   - The `α_max = 0` branch (`:826–835`) is byte-identical.
   - The scaled factorization and the unscaled `J` given to `_released` have the same zero pattern. A scale underflow
     can only add nonzeros seen by `_released`, which is the conservative side.
2. **The predicate matches the theorem.** `Z* ⊆ Z₀` gives `Z* ∩ supp(d) ⊆ C`, so the `C` test is a pure
   short-circuit and the code acts exactly when `α > 0 ∧ Z* ∩ supp(d) ≠ ∅`.
3. **No freezing of a component that must leave.**
   - `d_Z = 0` is exact for the evaluated `F`, `J` (§4.2 is correct). `Z*` is recomputed every step.
   - `opening == lower` still excludes T02 §6.3.3 disappearance: a component that reaches its bound inside the attempt
     is never in `Z₀`.
   - Across attempts, a component vanished earlier can be held at its bound, but only where exact Newton holds it too.
     Re-appearance is the phase controller's job (F7).
4. **The inertness proof is sound for the code.** A non-acting call returns the very objects `(direction, alpha_max,
   landing, ())`. The caller's `if released:` (`:590`) is not entered. `_released` has no side effects (the CSR form is a
   new matrix).
5. **The detector is a faithful witness, in-process (F4).** It replaces the module global that `solve_newton` resolves at
   call time. It evaluates the same predicate, in §4.5's order, with the captured originals, and returns the wrapped
   result untouched.
6. **The witnesses test what they were registered for.**
   - A93 capped runs the same three starts and asserts the registry budget is still 10 000. The cap is a test-local
     `replace` to 100, and the cap clause is held exactly.
   - A93 uncapped uses `ensemble.classify`, which includes the false-success check, and is stronger than
     `outcome == CONVERGED`.
   - T07's THM-09 pin is 94, every `k ∈ K` is ≤ 89, and the capped leg asserts `BUDGET_EXHAUSTED`.
   - No tolerance, budget constant, registry entry, case or recorded run is in the diff.
7. **PTC is outside, enforced by structure.** `ptc.py` imports `_bound_aware_alpha` and `_trial_point` only. Its
   pseudo-step and polish call those directly, never `_bound_aware_step` or `_released`. No test pins this; R-782's
   "Watch for" does.

## Not examined

- CI: G-R3, the aarch64 T07 length (§7 Q6) and G-R7's CI half are pending.
- The G-R2 scratch harness and the local T06 comparisons; I took their numbers from the build log.
- The full suite (the orchestrator's gate is running).
- The Dulmage–Mendelsohn logic of `_released`, beyond the alternating-path argument (R-064's code, reviewed then).

## Before merge

- CI green on x86-64, aarch64 and default-install.
- G-R3 on aarch64, with the T07 pin as a machine-class map if aarch64 differs.
- WO-R4's manifest.
- Decisions on F1 and F2 recorded (defaults above). F3 and F4 are optional and cheap.
