# Brief — T04 implementation review

**To:** `reviewer` (design lane)
**From:** the session (build lane), 2026-09-24
**Design under review:**
- `docs/derivations/T04-globalization-spec.md` (A00–A33, as amended by the design lane's rulings
  `35fb7c5`, `9a0025c`, `0a9b69c`);
- `docs/adr/0010-globalization-homotopy-ptc.md` (Proposed);
- reference `benchmarks/t04/reference_values.yaml` (SHA `146406e6…`), from the twin
  `docs/derivations/scripts/t04_reference.py` (`--check` 149).

**Implementation:** `wp/T04`, commits `4ad432f..26aeb0c` (build lane). Spec and design commits in
that range are the design lane's own and are not under review.
**Deliverable:** `docs/reviews/T04-review.md` in the shape of `docs/reviews/T03-review.md`:
- a verdict;
- must-fix, should-fix and notes, each with a `file:line` anchor and a falsifiable test that would
  catch it;
- rulings on §5 below;
- a "FOR FRANK" section if anything needs him.

Commit it on `wp/T04`, staging named paths only; messages end with
`Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_01QMQnXcFna3j5D6Ai9Ja9AE`. Never set `reviewed`. A
build-lane engineer is concurrently adding **only** `scripts/t04_evidence_manifest.py` and the
identity script (W11) in the same checkout; do not edit those, and do not edit `src/` or `tests/`.

## 1. What was built

| Item | Commits | Where |
| --- | --- | --- |
| W1 policy | `4ad432f` | `orchestrator/trace.py` (`SolvePolicy.globalization`), `schemas/solve-policy.schema.json` |
| W2 homotopy | `03d8e32`, `1ea4fad`, `6a5d4f2`, `713a5ac` | `orchestrator/homotopy.py`; `region.py` (`solve_region(recovery=…, compile_level=…)`); records in `trace.py`, schemas |
| W3 edge 3 | `f96314d` | `orchestrator/executor.py`, `orchestrator/recovery.py` |
| W5 PTC core | `7f35c55`, `b7461ce`, `a22c43f` | `numerics/ptc.py` |
| W4/W6/W7 mapping, contract, pencil | `9602e60` | `orchestrator/mass.py`, `region.py`, `phase_contract.py` (rows 4–5, stall list) |
| W8 basin | `feb6ebc` | `benchmarks/t04/basin.py` |
| rulings applied | `20ba72e` | four amended tolerances; ruling (h) |
| W12 K04 on the bound declaration | `a6e2d6e` | `verify/certificate.py`, `verify/checks.py`, `application/binding.py` (`specification_targets`) |
| W9 | `dd930e8` | λ<1 refusal `continuation_level(p/q)`, `verify/failure.py` `region_bundle`, `scripts/t04_schema_fixtures.py` |
| W10 | `26aeb0c` | `benchmarks/registry.yaml`, two revisions; PHS-05 re-registered `CONVERGED` |
| Tests | — | `tests/test_t04_{policy,homotopy,edge3,ptc,ptc_region,basin,certificate,schemas,registry}.py` |

## 2. What was run and measured

- Gate green at **1892 passed, 0 xfailed** (78 s; 1617 before implementation).
- Every registered homotopy value matched the YAML exactly on the first run:
  - HOM-01…05: λ-trials, correctors, stall λ 23/256 and 909/1024;
  - the 180-run family scan: 170 converge unaided, 9 rescued, 1 stalled.
- Named PTC runs are exact for both cores: [5]/[39], [5]/[30], [2,1,3]/[4,26], [1,2]/[1,11].
- PHS-05 under PTC is exact. The basin comparison is exact after the admission ruling (18 admitted).
- A30–A33: the bound-declaration certificates are `VERIFIED` for HOM-01/02/05 and A02-360/365. The
  norms match the twin to ≤ 2.2e-15.
- **Path identity:** Newton, Anderson and homotopy paths are bit-identical before and after the PTC
  integration (100 runs dumped as hex).
- **Tear certificates:** the 20 nominal tear certificates are bit-identical before and after W12,
  except for the new empty `transformations.declaration`.
- No pre-existing K03/T02/T03 test changed its expectation. Three schema-guard tests count the new
  fixture files, and `test_schemas_p01.py` gains six ids outside the denominator.

## 3. Build-lane decisions to check

Homotopy track:
1. A homotopy provenance item's `iterations` = total corrector iterations, accepted and rejected.
2. A checkpoint at λ "0" when only the easy endpoint is accepted.
3. Corrector `attempt_closed` events are stamped `homotopy_level`. The attempt pairing holds among
   unstamped events only, and `bundle_for` filters accordingly.
4. The recovery opens from item 0's in-memory opening (no re-projection).
5. After a recovery, the step's checkpoint is the recovery's, or the failed solve's if none.
6. An easy-endpoint stall records `stalled_at = easy_endpoint`.
7. HOM-02/03 and the family revisions are built in memory. Family Q values for 345/370/375 K come
   from the SYN-001 oracle (≤ 7.6e-11 W from every registered Q).

PTC track:

8. Each level is recompiled (6 ms); λ = 1 always uses the target instance.
9. Patience is checked only after an accepted pseudo-step (confirmed by ruling g).
10. The validator runs V1→V4 over all rows, and V1 covers `absent` rows (confirmed).
11. Recovery solves never run PTC (confirmed by ruling i).
12. The ablation seams `tau_start` and `sign` in `solve_ptc` exist for tests only.

W12 and W9:

13. The identity guard runs before the absent-state path. `continuation_level` is refused before
    the outcome check.
14. Identity is read from the root fingerprint, then the result's `SolvePlan`, then an optional
    `solve_plan=` argument. For a plan result, it comes from the last step with a solve result.
15. The state hash is computed without a residual call.
16. Alias equality ignores term order.
17. A new inert `Binding.specification_targets` field.
18. A new `region_bundle(result, trace, step_index=)`.
19. PHS-05's registry entry: class `globalization case`, `resolved_by: T04`, and a
    `without_recovery` block that keeps T03's expectation.

## 4. Where I am least sure

- **The executor's edge-3 insertion** (`executor.py`, `recovery.py`): the trigger set,
  preconditions, the fresh contract state, and the dense provenance continuation after a merged
  region (reported `unsupported`).
- **The PTC core's stop, polish and SER bookkeeping** against §7, especially that rejected trials
  never enter the ratio and that the reset happens per attempt.
- **The verifier's identity guard.** Can any caller path certify a state against the wrong
  declaration, or skip the guard (the `state=` override skips the hash check by design)?
- **Whether the xfail-to-pass retirements assert exactly the amended bounds**, and nothing looser.
- **Findings handed on, not fixed.**
  - A Jacobian that raises during the polish is uncaught (as in Newton).
  - PHS-05's base revision cites the 360 K sweep for its 355 K Q.
  - F9: K04's fresh-flash tolerances call 15 of 179 correct family roots `FAILED`. A33 registers
    this `near_threshold`; it is handed to a K04 follow-up.

## 5. Questions for your ruling

- **Q1** — Decisions 1, 2, 5 and 13–15 above: sound, or amend?
- **Q2** — Is A26's cross-platform half adequately served by adding the T04 R0 fields to the K05
  identity document? W11 is doing this now, following T03's `scripts/t03_identity.py`.
- **Q3** — Gate runtime rose from 38 s to 78 s, about 19 s of it the family scan. Keep it in the
  gate, or move it to a slower tier?

## 6. Not worth your time

Formatting, registry prose, schema JSON layout, fixture regeneration mechanics, the manifest script.
