# ADR 0031 — M03: parameters are pinned inputs, their derivative comes from a bit-identical parametric twin, and a sensitivity is issued only at a qualified regular root; sweeps and the estimation example are studies over those parameters

**Status:** Proposed, 2026-10-08. Accepted when M03's evidence manifest is `tested` for A01–A30 and A42 of the specification and the design-lane review of WO-1 to WO-5 has closed its must-fix items.
**Date:** 2026-10-08
**Author:** design lane (`specifier`); brief `docs/briefs/M03-specification.md`.
**Normative text:** `docs/derivations/M03-studies-spec.md` §2–§7, §10, §11 (A01–A30, A42); machine-readable expectations `benchmarks/m03/reference_values.json` from `docs/derivations/scripts/m03_reference.py`.
**Amends (additively):** `compile/casadi_backend.py` gains a second, separate compiled object (the twin) beside `CasadiCompiledProblem`; `numerics/linear.py`'s `KeptFactorization` gains a transposed back-solve under ADR 0004 D3's record; the schema list of plan §2.2 is delivered for `Study` (one new file). **No frozen interface changes:** `CompiledProblem`, `CompiledProblemMetadata`, `Capabilities` and every existing schema are untouched.
**Reverses:** nothing.
**Affected requirements:** A06 (M03's half: the general NLP bridge consumes these derivatives), D16 (the optimization closure, via ADR 0032 D6), W24 (M03's part), D14/D05 (residual satisfaction is not regularity; a study cannot relabel), D03 (one factorization; ADR 0004).
**Affected packages:** M03 (builds it), M04 (gradient checks of surrogates inherit the qualification vocabulary), M05 (the trust-region adapter may call the same sensitivities), M07 (journey).
**Register:** R-180 (D1, D2), R-181 (D3), R-182 (D4), R-183 (D5), R-184 (D6), R-185 (D7).

## Context

Blueprint §10 asks for sweeps, local sensitivities and parameter estimation before optimization, and for sensitivities "from Fₓ xₚ = −Fₚ using the converged Jacobian, with branch and conditioning qualifications". Nothing in the code computes `Fₚ`: K01 compiles pinned inputs as float constants (`casadi_backend.py:317–334`), and `Capabilities` has no parameter-derivative field. The only implicit derivative is K03's Schur complement for SYN-001's tear (R-010). K04's [A08] screen judges the square simulation Jacobian (R-016, R-084); blueprint §8.1 forbids applying it to free *decision* variables but not to the simulation Jacobian a sensitivity is solved with. SYN-001's structural hash, K05's identity document and every registered T06 value must not move (brief §4).

Measured on 2026-10-08 (specification §3–§4): a twin with the requested pinned inputs as symbols reproduces the base residual and Jacobian **bitwise** at the three registered states; the implicit sensitivities agree with closed forms to 6.5e-15 (scaled, absolute) and 8.4e-14 (relative); the two pressure specifications are each inconsistent with an eliminated alias row (tangent residual exactly 1.0) while the five other parameters' residual is exactly 0.0; near SYN-001's bubble point the target's `rcond₁` falls linearly with the phase margin (`≈ 0.02 m`), so the [A08] screen alone notices a boundary only at `m ≲ 1e-6`.

## Decision

**D1. A study parameter is a pinned input.** It is an element of `CompiledProblemMetadata.parameter_ids`, declared by the study with a finite domain and a scale. Nothing else is a parameter, and a study never turns a variable into a parameter or the reverse.

**D2. `Fₚ` comes from a parametric twin, guarded bit for bit.** `compile/casadi_backend.py` compiles the same `ProblemSpec` a second time with only the requested pinned inputs as `ca.MX` symbols, and exposes the residual and the `x`- and `p`-Jacobians from that one graph, with the base's `model_version`. At every requested state its residual and `x`-Jacobian must equal the base problem's after signed-zero normalization, or the request is refused `TWIN_MISMATCH`. A row builder that cannot take a symbolic parameter refuses the request `PARAMETER_NOT_DIFFERENTIABLE`. The base compiled problem, its metadata, `Capabilities`, `model_version` and `constants_sha256` do not change, so no registered identity moves.

**D3. A sensitivity is issued only at a qualified regular root** under the policy `M03-sensitivity-v1` (specification §3.5): Q0 the context pins the base identity; Q0′ the twin guard; Q0″ known, differentiable parameters; Q1 scaled residual of the kept rows ≤ `τ_root = 1e-10`, and at study level a K04 certificate `VERIFIED` for the same state; Q2 K04's `screen` on the reduced scaled Jacobian (the K04 target) `NO_RANK_LOSS_DETECTED`; Q3 per parameter, the eliminated alias rows' scaled tangent residual ≤ `τ_alias = 1e-8`; Q4 every TP-type phase split's margin (specification §3.4) ≥ `τ_regime = 1e-4`, and every lifted split TP-type. Failures are typed (`IDENTITY_MISMATCH`, `TWIN_MISMATCH`, `UNKNOWN_PARAMETER`, `PARAMETER_NOT_DIFFERENTIABLE`, `ROOT_NOT_CONVERGED`, `ROOT_NOT_VERIFIED`, `RANK_DEFICIENT`, `ILL_CONDITIONED`, `REGULARITY_INCONCLUSIVE`, `INCONSISTENT_WITH_ELIMINATED_ROWS` (per column), `PHASE_BOUNDARY`, `REGIME_MARGIN_UNSUPPORTED`), all failures are listed, and a refused request or column carries `null` values. There is no override: a study may record residual-only evidence but cannot relabel it as sensitivity evidence (blueprint §8.1).

**D4. Forward and adjoint share one factorization; finite differences stay test oracles.** The reduced scaled Jacobian is factorized once (ADR 0004's options and record); forward solves take every requested column at once; the adjoint solves `Ĵᵀ Λ̂ = −Ĉᵀ` on the same factorization through a new `KeptFactorization.solve_transposed`, judged and recorded against `Ĵᵀ` exactly as ADR 0004 D3 judges a forward solve. Mode `both` records the consistency `|Ŝ_fwd − Ŝ_adj|` (blueprint §5.2's `vᵀ(Ju) = (Jᵀv)ᵀu`). The count of factorizations does not depend on the number of parameters or outputs. The finite-difference oracle (4th-order central re-solves at `h = 1e-4 · s_p`) exists in test support only (R-010).

**D5. A sweep is independent certified solves; a failed point is a result.** Each point re-solves from the case's registered initializer (`start = "registered_initializer"`, a single-valued literal), is certified, and optionally gets a sensitivity; failures are recorded with typed outcomes and `null` outputs; the result is independent of the order of the points; nothing is claimed between points, and each point's root fingerprint is recorded. M03 sweeps run in the study runtime on the tear path and do not consume ADR 0024's application-level warm start.

**D6. The estimation example is SYN-001's (r, T_f) fitted to seeded synthetic data, with identifiability decided by the weighted, scaled sensitivity matrix.** Weighted least squares by SciPy's `least_squares` (`trf`) with M03's exact forward sensitivities as the Jacobian and a production solve and certificate per evaluation; identifiability by the singular values of `W^{½} J S_θ` with `τ_id = 1e-8`; a covariance only when identifiable (`declared_sigma` basis); undetermined parameters and predictions reported as such, without values. The data come from a SplitMix64 stream and `erfinv` in the reference generator and are stored in the JSON; the implementation reads them. The report's evidence class is `numerical_verification`, stated as not empirical validation. The identifiable fit adds a recycle-flow and a mixer-temperature measurement to the six product flows; the unidentifiable fit uses the product flows alone, which are independent of r by derivation §5.1.

**D7. Schemas: one new file now.** `schemas/study.schema.json` (sensitivity, sweep and estimation `$defs`; ADR 0032 adds `optimization-report`). No existing schema changes. `ExperimentRequest/Result` is left to M04. The `$id` move deferred by R-149 does not ride on M03.

## Alternatives considered

- **Widen `Capabilities` with a parameter-derivative level and add a method to `CompiledProblem`** (blueprint §3.2 lists parameter derivatives as an optional capability). Rejected for M03: it changes a frozen interface and the metadata schema, regenerates every metadata fixture, and buys nothing the twin does not — the twin is negotiated by its own existence and refusal, and the frozen surface stays frozen. A later ADR may fold the twin into the protocol if a second backend needs it.
- **Finite differences of the residual in p.** Rejected: R-010; an FD derivative with a good step can pass a 1e-10 relative tolerance, which is why A03 proves its absence by call counts.
- **Hand-written ∂F/∂p per unit model.** Rejected: a second model of each unit, free to drift from the residual it differentiates (plan L271's objection to hand-authored copies).
- **Compile every pinned input symbolically always** (one twin for all). Rejected: a builder that branches on one parameter's value would make every sensitivity unavailable; per-request subsets keep the twin as close to the base as the request allows.
- **Use the last Newton factorization.** Rejected: blueprint [A08] — a prior Newton factorization need not belong to the final Jacobian (on the tear path it is a 3 × 3).
- **Rely on the [A08] screen alone near phase boundaries.** Rejected: measured, the screen notices only below `m ≈ 1e-6`, two orders after the derivative's validity radius has shrunk below a hundredth of a kelvin; blueprint §6.3 asks for the qualification explicitly.
- **Warm-start chaining in sweeps.** Rejected for M03: results would depend on point order, a failed point would poison its successors, and following a branch is continuation's job (T04) — a later `start` value can add it visibly.
- **Profile likelihood, Bayesian or Fisher-information-only identifiability.** Rejected for M03: the local rank test decides both registered fits unambiguously (ratios 0.32 and exactly 0), at a fraction of the cost; profile likelihood is a natural later addition for practical identifiability.
- **Noise-free synthetic data.** Rejected: χ²/dof and the validation residuals would be degenerate and could not catch a mis-weighted measurement.

## Consequences

- C1. `casadi_backend.py` remains the only CasADi importer; it gains one compiled object and no change to the existing one.
- C2. Every sensitivity consumer (M03's estimation and NLP verification, later M04/M05) inherits one refusal vocabulary and one qualification policy id.
- C3. Sensitivities at PH-type splits, zero-flow splits, revision-built (EO-path) flowsheets and the kinetic CSTR are refused or out of scope until a later ADR defines their margins.
- C4. A pressure specification alone is not a valid sensitivity parameter on SYN-001; directional (combined) requests are a possible later extension.
- C5. One new schema file; plan §2.2's list is partially delivered (`Study`).

## Migration

None. No identity, fixture or registered value moves. `KeptFactorization` gains a method; existing callers are unaffected.

## Acceptance evidence

Specification assertions A01–A30 and A42 recorded `tested` in `evidence/M03/<commit>/manifest.json` with the commands run; the reference generator's `--check` green; the design-lane review of WO-1 to WO-5.
