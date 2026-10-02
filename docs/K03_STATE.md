# K03 — campaign state

**Rewritten in place, never appended.** A position, not a diary. History goes to
`docs/K03_DECISIONS.md` (append-only) and to the git log.

| | |
| --- | --- |
| Objective | The nonlinear solver: physical scales, damped Newton on the recycle residual, bounded line search, phase attempts (plan §4.2 row K03) |
| Branch | `wp/K03`, merged and pushed to `main` at each milestone per Frank's standing instruction |
| Gate | `PATH=.venv/bin:$PATH ./scripts/check.sh` — **green at 1183 tests** (1019 when K03 began) |
| Lead | **Fable / Opus.** Fable specified the scaling and globalization policy and the phase-attempt contract; Opus implemented |
| Manifest | `evidence/K03/c806f83fd3fb0e71967235000fb517fc1c26efd4/manifest.json` — `status: tested`, 15 pass / 0 fail / 1 unsupported / 1 not applicable, both reviews `pending`. It supersedes the pre-review manifest at `19764e1`, whose linear-solve evidence measured SuperLU beside the solver rather than the solver |
| Requirements | D01, D03, D06, D09, A01 — all five `implemented` in the ledger, each with the later package that owns the rest named in its row |

## Where we are now

**M1–M6 are done, G00 is closed, and the Fable review has been returned and acted on.**
Verdict: *matches the specification with five must-fixes*, all five confirmed by measurement
before anything changed and all five now closed — see "What the review changed".

 The SYN-001 flowsheet solves end to end: three variables,
`R(t) = G(t) − t` over K02's sequential traversal, the exact Schur complement of the assembled
49x47 Jacobian for `dR/dt`, one SuperLU factorization per iteration, and bounded phase attempts
around the whole thing.

Measured at the manifest commit, all five registered variants, from the registered initializer:

| | Worst | Against |
| --- | --- | --- |
| Tear `\|t − t*\|` | 3.9e-14 mol/s | Fable's 20-digit recycle |
| Vapour product | 2.7e-15 mol/s | the registered products |
| Duty | 1.8e-9 W | `Q_heater`, `Q_flash` |
| Overall balance | 2.0e-15 mol/s | feed = product + purge |
| `dR/dt` vs closed form | 1.6e-15 | 40-digit mpmath, at `t*` and OFF-A |
| `dR/dt` vs finite difference | 3.3e-11 | an oracle sharing no route |
| Affine-ray identity | 1.9e-16 | `J(t*) t* = −(1−r) t*` |
| Inner consistency η | 2.0e-16 | registered 1e-10 |
| Linear residual | 1.4e-16 | ADR 0004 D3.2's 1e-12 |
| `min\|U_ii\| / max\|U_ii\|` | 3.99e-2 | the 1e-10 screen (D3.4), which never decides |

Both linear numbers are read off `linear_solve` events of real solves. The ratio is **not** ADR
0004 D3.4's 7.1e-3 and is not meant to be: that is Fable's probe of the block at a reference
state with a random right-hand side, this is the states the solver visits. The pre-review
manifest reported the probe as though it were the solve.

Each variant takes **one attempt**, because derivation §9 proves the tear map affine along the
ray through its fixed point. That is a limitation as much as a result and the manifest records it
as one: these variants exercise the derivative and the convergence test, not the globalization.
OFF-A and OFF-B and the seven synthetic seeds of §13.7 do that.

**OFF-B, the registered phase restart, matches §13.3 number for number**: attempt 1 opens LIQUID
and closes `PHASE_UPDATE_REQUIRED` after 2 iterations, attempt 2 opens TWO_PHASE from a
phase-rejected trial and converges in 2.

## What the review changed

Five must-fixes, each reproduced before it was touched, each closed with a test; all fifteen
mutations of the fixes are caught. None changed a G00 figure — they were omissions and one
wrong predicate, not wrong numbers.

| # | What was wrong | Now |
| --- | --- | --- |
| M1 | The two eliminated pressure rows were never in the inner-consistency check, so the claim made when they were removed was asserted once, at the initial guess, and never again | 46 rows checked; an eliminated row by its **certificate identity** `\|F_e − m_e\|/S_e`, since §7.2 tolerates a mismatch five decades above `eta_inner` |
| M2 | `stalled_at_the_wall` read `a >= a − window`, always true, so §9.3's second restart trigger was unimplemented and one overshoot at iteration 0 made every later failure restart from a stale trial | Compares the closing iteration to the most recent wall |
| M3 | On `ACTIVE_SET_CYCLING`/`ATTEMPTS_EXHAUSTED` the result carried the restart trial while its residual came from the last Newton result | `last.x`. With the defect restored: `x = −2.0` reported with `residual_inf = 3.28` where the residual at −2.0 is −5.0 |
| M4 | `max_property_calls` was read nowhere and the three property counters had no writer, so every event carried three zeros | A guard under K02's exact cache **refuses** the call that would exceed the cap, which is what makes A15's `property_calls == 20` exact. Nominal solve: 154 calls, 445 hits, 599 requests |
| M5 | The Schur complement factorized the 44×44 block once per column and discarded all three records, so ADR 0004 D3's "recorded on the `SolveEvent`" held for the 3×3 system and nothing else | One factorization, multi-column right-hand side, **proved bit-identical** at all five variants; the record reaches the trace. Nominal solve: 4 `splu` down to 2, both recorded |

Three should-fixes closed with them: η reaches the `jacobian` event, so A24's trace clause is
readable (S1); `FLASH_REGIME`'s unregistered fourth entry is gone, because §9.1 registers three
and a regime that fires on no reachable state reads as coverage (S8); and S4's suggested exact
coefficient identity was **not** added — under the ±1 two-node guards that run first the path
telescopes and the check can never fail, so it would have been the same defect as S8. The
argument is recorded in `rank.py` and held by
`test_a_path_of_two_node_edges_telescopes_exactly`.

## Next action

**K04** — certificates, the [A08] regularity screen, structured failures. Fable-led. Two of the
four open review findings below are its inheritance.

## Gates and their current numbers

| Gate | Now |
| --- | --- |
| `scripts/check.sh` | green, 1183 tests |
| G00 — three-component process, all v0.0 units, one numerical tear | **closed** — see the table above |
| G01 — damped Newton plus expression/callback fixtures | **met with limitations**, per the review: the callback half is K01's and the damping's *failure* modes are pinned by §13.7's seven seeds, but no registered assertion has an Armijo-rejected step **followed by convergence**, so the line search's success mode is exercised and not registered (review S6) |
| Second platform (G05) | **not run** — K05 owns it |
| CI | **runs on every push and always has** — the earlier "never executed" line in this file was wrong. Since 2026-09-22 the matrix is `ubuntu-latest` + `ubuntu-24.04-arm` |

## What K03 does not do, and says so

Every one of these is in the manifest's `limitations`, and the initializer chain is recorded as
an `unsupported` check rather than as a pass:

- **Blueprint §7.4's initializer chain is specified (§10.1) and not implemented.** Only the
  registered local initializer is wired, so `SYN-001-inadmissible-guess` exercises the mixer's
  refusal but not the chain's fall-through.
- **One recovery edge of blueprint §7.7's eight** — the phase restart.
- **No certificate, no verified state.** Every checkpoint is `unverified`; K04 owns the verdict.
- **The finite-difference derivative is an oracle and cannot be used at `t*`**, where the
  central stencil leaves the mixer's domain on two of three columns.
- **The gate is not portable.** Two `ubuntu-latest` runners disagree on the converged state's last bits, so the committed trace fixtures encode machine-specific floats and the byte-exact regeneration test cannot hold across machines. Blueprint §8.3 already excludes floats from a cross-platform bitwise promise, so this is a defect in the test; where the line falls is ADR 0007's. See `docs/progress.md`, "Reproducibility".
- **Four review findings are open**, recorded as manifest limitations rather than left unsaid:
  `Checkpoint.full_state_sha256` and `jacobian_identity` have no writer, so A35's
  factorization-identity check — which [A08] needs so K04 cannot reuse a factorization
  belonging to a different Jacobian — is specified and unimplemented; §8.2's admissibility
  check on the converged answer (A26, A27) is unimplemented, and it is the only guard on the
  branch the flash-only signature deliberately does not freeze; several registered assertions
  have no test, notably A20/A21/A23 at the 365 K Jacobian state and A03; and a solve that
  fails before its plan exists raises rather than returning a `SolveResult`, except on the
  budget path.

## Open decisions, with their defaults

| # | Question | Default taken |
| --- | --- | --- |
| 1 | Which residual does Newton run on? | **Closed.** The three-variable tear over the traversal, not the lifted 47-variable system: in the lifted form both trivial phase splits are exact roots of every row (K02 finding 3). Register R-011 |
| 2 | ADR 0005, the general phase-attempt contract | Deferred to T03. K03 §9 is the interim normative text (R-012) |
| 3 | `PropertyCapabilities` schema | Still deferred. No document carries one yet; `SolvePolicy` did not need it |
| 4 | ADR 0006 Q2 — METIS disposition | **Awaiting Frank.** Not blocking: the 44x44 inner block needs no graph partitioner |
