# ADR 0004 — Explicit SuperLU options and the recorded linear residual

**Status:** Accepted (K03 default; pre-allocated by plan §4.1 "Phase-0 ADRs": *0004 explicit SuperLU options*; decision register R-A04)  
**Date:** 2026-09-21  
**Author:** Fable 5.1 (Fable owns every ADR and the scaling/globalization policy, plan §1.3)  
**Affected requirements:** D03 (sparse solver — "explicit SuperLU configuration and linear residual evidence": this is the configuration), D01 (interchangeable numerical interfaces: the solve is one recorded code path), D20 and blueprint §8.3 R1 (the options are part of the recorded numerical policy that a controlled replay reproduces)  
**Affected packages:** K03 (every linear solve: the 44 × 44 inner block of the tear Schur complement, the 3 × 3 reduced tear system, NUM-02), K04 (the regularity screen's own factorization of the final unregularized Jacobian uses the same options and the same recorded evidence), K05 (the options are in the RunManifest's solver policy), T02/T04 (the full EO and PTC linear systems inherit D1–D3)  
**Blueprint authority:** §3.1 "Default linear factorization uses `scipy.sparse.linalg.splu` with explicit options and CSC assembly. Record ordering, pivoting, and linear residuals. Its public interface supplies factorization and solves; persistent symbolic-analysis reuse is not assumed." §7.3 "Check linear-system residuals". §8.1 [A08] "LU pivot/U-diagonal information is an inexpensive warning screen, not a rank-revealing test or a condition-number estimate."  
**Companions:** ADR 0003 D4.2 (the linear solve stays in SciPy SuperLU; no CasADi `Linsol` on a default path); ADR 0006 D2.4 (the same, now a distribution constraint: `linsol:mumps` is in the METIS closure); `docs/derivations/K03-solver-spec.md` §6 (where the solve sits in the Newton) and §14 A25 (the assertion).  
**Evidence for the numbers below:** P02 §9 (`benchmarks/p02/linear_solve.py`, 17 × 17), and Fable's K03 probe of 2026-09-21 on the SYN-001 44 × 44 inner block through the K02 flowsheet and the K01 compiler (recorded in the K03 specification as *measured*).

## Context

Blueprint §3.1 fixes the factorization library and says the options must be explicit and the linear residual recorded, and leaves the values open. P02 §9 chose values for a 17 × 17 comparator and measured a scaled residual of 3.8e-17. K03 is the first package that solves linear systems on a production path, at three sizes (3, 44, and whatever T02 brings), inside a Newton whose trace must be reproducible under blueprint §8.3 R1 ("same locked environment … reproduce within the declared numerical policy"). Two facts were measured today that the decision must not ignore: SciPy's *implicit* defaults for the two supernodal blocking parameters are **not** the values `relax = 1, panel_size = 10`, and the two configurations are **not bit-identical** on the 44 × 44 block (solutions differ by 3.6e-15 in the ∞-norm); and the `Equil` option has **no effect at all on the `splu` path** (factors and solutions bit-identical with `Equil` true or false, on the scaled and on the unscaled matrix), because equilibration lives in SuperLU's driver routine, which `splu` does not call. An ADR that recorded `Equil: False` as the reason the registered scales are "the only scaling in play" would be recording a false reason; the true reason is that no equilibration is performed on this path at all.

## Decision

### D1. The configuration, verbatim

1. **Call.** `scipy.sparse.linalg.splu(A, permc_spec="COLAMD", diag_pivot_thresh=1.0, relax=1, panel_size=10, options={"Equil": False, "IterRefine": "NOREFINE", "SymmetricMode": False})`, with `A` a `scipy.sparse.csc_matrix` of the **scaled** matrix `Ĵ = S_F⁻¹ J S_x` (K03 spec §4). The dictionary is passed exactly as written; SciPy 1.15.3 accepts every key (`IterRefine` takes `"NOREFINE"`, not `"NO"`; measured).
2. **Why each value.**
   - `permc_spec="COLAMD"`: approximate minimum-degree column ordering for a nonsymmetric matrix; deterministic for a given pattern; on the 44 × 44 block it gives `nnz(L) = 111, nnz(U) = 160` against `129/93` for `NATURAL`, and unlike `NATURAL` it does not force `SymmetricMode` on (SciPy sets `SymmetricMode = True` whenever `ColPerm = NATURAL`, a silent coupling that `COLAMD` avoids).
   - `diag_pivot_thresh=1.0`: full partial pivoting — accuracy over sparsity, at sizes where sparsity is not a cost. A lower threshold trades pivot growth for fill and would make the recorded `|U_ii|` screen less meaningful.
   - `relax=1, panel_size=10`: **explicit because they are load-bearing for bit reproducibility**, not because they are optimal. Supernodal blocking changes the order of floating-point operations; the implicit defaults are different values and give a different last bit. R1 replay reproduces "within the declared numerical policy", and a parameter left implicit is not declared.
   - `Equil=False`: recorded so that the configuration is complete and so that a future move to `spsolve`/`gssv` (which *do* equilibrate) cannot introduce an unrecorded, iterate-dependent rescaling that would contradict K03 spec §4.4 (scales frozen within an attempt). See D1.3.
   - `IterRefine="NOREFINE"`: the recorded residual must be the factorization's own. Refinement would hide a poor factorization behind a corrected solve; D3 makes a poor factorization a typed result instead.
   - `SymmetricMode=False`: the Jacobians are not symmetric.
3. **`Equil` is inert on this path — measured, and recorded as such.** With `Equil` true or false, `splu` returns bit-identical `L`, `U`, permutations and solutions on the 44 × 44 scaled block and on the unscaled one. The registered scales are the only scaling in play because `splu` performs none, not because of this flag. Any package that switches to a SuperLU *driver* routine must re-measure this.

### D2. One code path

Every linear solve on a K03 path — the inner block of the Schur complement, the reduced tear system (converted to CSC even at 3 × 3), NUM-02 — goes through one function that applies D1, records D3 and returns the solution. There is no dense fallback, no `spsolve`, and no path that skips the record. A K04 regularity screen calls the same function on the final unregularized Jacobian and, per [A08], **does not reuse** a Newton factorization unless it belongs to that Jacobian (the K03 spec makes the identity checkable, A35).

### D3. The recorded evidence and its threshold

1. **Per solve, recorded on the `SolveEvent`:** the normalized linear residual

       ρ_lin = ‖Ĵ Δ − b‖_∞ / ( ‖Ĵ‖_max ‖Δ‖_∞ + ‖b‖_∞ ),

   with `‖Ĵ‖_max` the largest absolute entry; the extremes `min |U_ii|`, `max |U_ii|`; `nnz(L)`, `nnz(U)`; and the options of D1 (once per plan, by reference on later events).
2. **Threshold.** `ρ_lin ≤ 1e-12`; above it the solve is `LINEAR_SOLVE_FAILED(reason = "residual")`. Floor and margin: for LU with partial pivoting the backward error is O(n ε ρ_growth); at `n = 44`, `n ε ≈ 1e-14`; **measured** worst `ρ_lin` = 1.3e-16 on the 44 × 44 block over fifteen states and 8.9e-15 in the P02-style unnormalized form; `1e-12` is two decades above the theoretical `n ε` and four above the measurement. A residual above `1e-12` on a matrix this size means the factorization is not a factorization of this matrix (a corrupted pattern, a wrong CSC fill order — ADR 0003 D5.1's hazard — or catastrophic growth), which is exactly what should stop a Newton.
3. **Singularity is a typed result.** `splu` raising `RuntimeError: Factor is exactly singular` is `LINEAR_SOLVE_FAILED(reason = "exactly_singular")`; nothing is regularized or re-solved by least squares in K03 (blueprint §7.7: a regularized step is a later recovery edge and never permission to discard equations). Registered state: NUM-02 at `r = 1`, `dR/dt ≡ 0`. *Amended 2026-09-24 (design lane, on the T04 implementation review's S5).* A matrix whose **structural** rank is below its dimension is refused before `splu` with the same typed result, reason `exactly_singular`, message `structurally singular: rank <r> of <n>`. *Measured by the review (P1c):* SciPy 1.15.3's `splu` under these options **segfaults** on a 42 × 42, structural-rank-8 matrix (the region's `M̂/Δτ` over a zero Jacobian), where SciPy's defaults, or `relax` removed, raise `RuntimeError`. The check is O(nnz √n) and leaves every structurally nonsingular factorization bit-identical. **`relax = 1` stays** (D1: load-bearing for bit reproducibility): the refusal removes the only known route to the crash, and no crash on a structurally nonsingular matrix is known. Reopen if one is found. *Amended 2026-09-25 (design lane, on T05 A28).* "The only known route" was scoped too narrowly: the route is a structurally singular matrix reaching `splu` under D1's options from **any** call site, not `solve_linear` alone. K04's regularity screen and solution-error bound (`verify/regularity.py`) factorize the target Jacobian under the same options and had no refusal; *measured* at T05 A28, SciPy 1.15.3 segfaulted there (4 of 5 runs, and in a fresh process without project code) on the dormant PH flash's 18 × 18 target of structural rank 15 (three equilibrium rows identically zero at zero flow). The refusal is therefore a precondition of every `splu` call under D1, and both call sites now carry it (`regularity._factorize` raises the `RuntimeError` K04 §7.3 already reads as exactly singular: the screen escalates to the SVD, the bound is `None`). `relax = 1` still stays; a new `splu` call site must carry the refusal, preferably by sharing one guarded factorization with `solve_linear`.
4. **The `|U_ii|` screen is a screen.** It is recorded and, if `min |U_ii| / max |U_ii| < 1e-10`, the event is flagged `linear_suspect = true`; it does **not** change the outcome and is **not** a rank statement (blueprint [A08]). Measured on SYN-001: the ratio is ≥ 7.1e-3 at every registered state (worst at r = 0.95), so the flag never fires on a registered case and a test must construct a near-singular matrix to see it fire.

### D4. What the options do not decide

Scaling (K03 spec §4: registered nominals, frozen per attempt); when a Jacobian is evaluated (§5); iterative refinement as a *later* accuracy policy (a new `IterRefine` value is a policy change recorded in `SolvePolicy.linear_solver`, and the recorded residual then becomes the refined one — D3.2's threshold would have to be re-argued); Krylov or matrix-free paths (blueprint §7.3: after profiling, never before).

## Alternatives considered

- **Leave `relax` and `panel_size` implicit** (SciPy's defaults). Rejected: measured not bit-identical to the explicit pair; an undeclared parameter is outside the declared numerical policy of R1.
- **`permc_spec="NATURAL"`** for determinism. Rejected: `COLAMD` is equally deterministic for a fixed pattern, gives less fill, and `NATURAL` silently switches SuperLU into symmetric mode in SciPy's wrapper.
- **`IterRefine="SINGLE"`** by default. Rejected: it makes the recorded residual a property of the refinement rather than of the factorization; the threshold's meaning (D3.2) would be lost.
- **`Equil=True`** (SciPy's default) on the grounds that it is harmless. Rejected: it *is* inert here, and recording it as true would invite a driver-routine path to make it real without anyone noticing.
- **`scipy.sparse.linalg.spsolve`** (one call, no factor object). Rejected: it is the driver route (equilibration, no reusable factor for the three right-hand sides of the Schur complement), and it does not expose `L`, `U` for the screen.
- **UMFPACK via scikit-umfpack.** Rejected: GPL, excluded by blueprint §15; and blueprint §3.1 names SuperLU.
- **CasADi `Linsol`.** Rejected by ADR 0003 D4.2 and ADR 0006 D2.4 (`linsol:mumps` is in the METIS closure; no CasADi plugin on a default path).
- **Dense LAPACK (`numpy.linalg.solve`) for the small systems.** Rejected: two code paths with two kinds of evidence; at 3 × 3 the cost of CSC is nil and the uniformity of the trace is worth more.

## Consequences

- K03 implements one linear-solve function under `process_runtime/numerics/` applying D1–D3; the K03 evidence manifest records `K03.A25`.
- `SolvePolicy.linear_solver` carries D1 verbatim; changing any value changes the policy hash (K05).
- K04's regularity screen (blueprint [A08]) factorizes the final Jacobian with these options and adds its own reciprocal-condition estimate; this ADR does not decide that estimate.
- Blueprint §3.1's "persistent symbolic-analysis reuse is not assumed" stands: every solve factorizes; the three right-hand sides of the Schur complement share one factorization within a Jacobian evaluation and nothing beyond it.

## Acceptance evidence

- **Configuration recorded and applied:** K03.A25 — every `linear_solve` event carries D3's fields and D1's options verbatim; a test that changes one option value changes the recorded policy.
- **Residual threshold with its floor:** K03.A25 (`≤ 1e-12`, measured 1.3e-16); P02 A23.1 (17 × 17, 3.8e-17 in the scaled form) remains the earlier data point.
- **Singularity typed:** K03.A16 (NUM-02, `r = 1`).
- **Screen recorded, non-decisive:** a unit test on a constructed matrix with `min|U_ii|/max|U_ii| = 1e-12` asserts `linear_suspect = true` and an unchanged outcome.
- **`Equil` inert:** a unit test factorizes the nominal 44 × 44 block with `Equil` true and false and asserts bit-identical `L.data`, `U.data`, `perm_c`, `perm_r`; if SciPy ever changes this, the test fails and D1.3 is re-decided.
- **This ADR's own status:** `implemented` when the K03 linear-solve function exists on `wp/K03`; `tested` when K03.A25 and the two unit tests above pass in the gate; `reviewed` requires the human numerical sign-off recorded separately and is not set here.

## What this ADR does not establish

- Anything about conditioning or rank: the screen is a screen ([A08]); K04 owns the estimate.
- Performance at any size beyond the registered 44 × 44 block (ADR 0003 D2.2's caution applies).
- Bit reproducibility across platforms or BLAS vendors (blueprint §8.3: "adaptive floating-point decisions are not included in a cross-platform bitwise promise"); D1's explicit blocking parameters make the *same* environment reproduce, which is R1, not R2.
- Any property of a SuperLU *driver* routine (`gssv`, `spsolve`), where `Equil` is live.

## Changing this ADR

D1–D3 bind every package that solves a linear system on a production path. A new option value, a refinement policy, a second solver or a Krylov path requires a new ADR stating the reason, the re-measured residual floor, and the affected requirements, and a decision-register entry.
