# T04 — campaign state

Position, not history. Rewritten in place. Read after `CLAUDE.md` and `docs/progress.md`.

| | |
| --- | --- |
| Objective | Typed adaptive homotopy, one PTC family with safeguarded SER, recovery edge 3 (plan §4.3 row T04; gate V14) |
| Lead | Design / Build — `specifier` specified; the session implements (delegating to `opus-engineer`); `reviewer` reviews |
| Branch | `wp/T04`, from `main` at `fc8e0ca` |
| Gate | `PATH=.venv/bin:$PATH ./scripts/check.sh` — green at **1892, 0 xfailed** (78 s) at `26aeb0c` |

## Where we are

**Specification landed.** Brief `docs/briefs/T04-homotopy-ptc.md`.
- Spec `docs/derivations/T04-globalization-spec.md` (A00–A33 after the rulings of `35fb7c5`, `9a0025c`).
- Twin `docs/derivations/scripts/t04_reference.py` (`--check` 152), YAML
  `benchmarks/t04/reference_values.yaml` (SHA `4dda7ebe…`).
- ADR 0010 **Proposed** (D9 certificate of a bound declaration); register R-030…R-035. Commits `f303b6e`, `2664c56`.

**Design verdict.**
- The typed homotopy (specification continuation) rescues PHS-05 via edge 3: HOM-01 `CONVERGED`
  in 3 λ-trials. HOM-02 is rescued too, HOM-03 and HOM-04 stall with a registered bracket, and
  HOM-05 is rescued.
- The PTC flash/heater family is derived (route a) but **not qualified**. It improves no tested
  basin: at r = 0.95 all 37 starts converge under both methods, and PTC costs 1.9–11×. It cannot
  rescue PHS-05 by structure. PTC is therefore **experimental**, and V14's "qualified PTC" clause is
  recorded incomplete.

## Work order (spec §18) — status

| Item | What | Status |
| --- | --- | --- |
| W0.1, W0.4 | compile 6 ms/level → recompile per level; edge 3 on changes **no** test (spec §11.2's premise false) | done |
| W1 | `SolvePolicy.globalization` | done `4ad432f` |
| W2 | homotopy core + records | done `03d8e32`, `1ea4fad`, `6a5d4f2`, `713a5ac` |
| W3 | edge 3 in the executor | done `f96314d` (A04–A12, A28 half; all registered values exact) |
| W4 | mass-mapping registry, validator, `PTC_ROW_SIGN` | done `9602e60` |
| W5 | generic PTC core + SER + polish | done `7f35c55`, `b7461ce`, `a22c43f` |
| W6 | contract integration | done `9602e60` (Newton/Anderson/homotopy bit-identical, 100 runs) |
| W7 | pencil, ×8, accumulation identity | done `9602e60` |
| W8 | basin harness | done `feb6ebc`; A23 passes after the admission ruling (18 admitted, experimental) |
| W0.2, W0.3 | named runs exact; basin stop resolved by ruling (a); W0.3 narrowed to the PTC stops | done / via W12 |
| retire xfails | A15, A17, A19, A21 at the amended tolerances; ruling (h) pinned | done `20ba72e` |
| W12 | verifier on the bound declaration (ADR 0010 D9; A30–A33); tear certificates bit-identical | done `a6e2d6e` |
| W9 | schemas, fixtures, taxonomy, `continuation_level` refusal | done `dd930e8` |
| W10 | registry, revisions; PHS-05 re-registered `CONVERGED` (`resolved_by: T04`) | done `26aeb0c` |
| W11 | identity, CI, manifest generator | in progress |

## Open decisions (defaults in force; for Frank, non-blocking)

- F1: PTC experimental, V14 incomplete for v0.1 (default a).
- F2/Q4: edge 3 on by default (PHS-05 → `CONVERGED`).
- Q5: the reactor case (PTC-R1) is deferred. Q6: the tear-path budget shape goes to a K03 follow-up
  before T06. Q7: registry class `globalization case`.

## Homotopy-track decisions (build lane; for the reviewer)

Provenance `iterations` = total corrector iterations; checkpoint at λ "0" when only the easy
endpoint is accepted; corrector `attempt_closed` events stamped `homotopy_level` (bundle_for filters);
recovery opens from item 0's opening (no re-projection); easy-endpoint stall `stalled_at=easy_endpoint`;
HOM-02/03 and family revisions built in memory from the A02 base.

**K04 ruling (R-035, ADR 0010 D9):** every `CONVERGED` solve is certified against the declaration it
solved, behind an identity guard. Today's `verify()` calls HOM-01's correct root `FAILED`. Handed to a
K04 follow-up (F9, Q8): the fresh-flash tolerances are tighter than the lifted rows imply, so 15 of
179 family roots would be `FAILED`. A33 registers A02-355 `near_threshold`. Decide before T06
certifies EO solves in bulk.

## Closed

Manifest `evidence/T04/53cd23b29d3701e3a464fa1edaa455a9a1d6fbf5/manifest.json`: `tested`, 34/34 (CI run 36063188633). Review `docs/reviews/T04-review.md` (`0ef71d7`)
fixed in `0b4ceb4..7fba4ce`; design rulings `da4a859`. CI caught a float-derived `certificate_id`
on aarch64 (fixed `53cd23b`, comparator rule). ADR 0010 **Accepted**. Merged to `main` 2026-09-24.

## Next action

None in T04. Handed on: K04 F9 (before T06), K05 policy validation on replay, K03 tear budget shape.
